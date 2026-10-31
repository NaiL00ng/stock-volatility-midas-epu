# -*- coding: utf-8 -*-
"""
CSI 300 Volatility Forecasting Main Experiment
Based on the user's old MIDAS-EPU code, with two added benchmark models:
    1) HAR
    2) GARCH(1,1)

Archived-model candidate; training provenance is incomplete.
See docs/research-review.md before interpreting statistical significance.

Models compared in the paper:
    - HAR
    - GARCH
    - XGB-Market
    - XGB-MIDAS-EPU-DEC

Key design inherited from the old code:
    - One-step-ahead target: y_t = log(r_{t+1}^2 + eps), implemented by shift(-1)
    - Initial train window: n_train = 1500
    - Validation window: n_valid = 500
    - Test period: all observations after train + valid
    - XGBoost parameters unchanged
    - MIDAS K grid and weight functions unchanged
    - Second-stage MIDAS specification selected using validation-set OOS residuals

Outputs:
    output_dir/
        prepared_master_data.csv
        predictions_HAR.csv
        predictions_GARCH.csv
        predictions_XGB_Market.csv
        predictions_XGB_MIDAS_EPU_DEC.csv
        all_model_predictions.csv
        metrics_summary.csv
        loss_panel.csv
        hypothesis_tests.csv
        midas_dec_search_results.csv
        midas_dec_best_spec.csv
        midas_dec_weights.csv
        fig_metrics_bar.png
        fig_cumulative_qlike_diff.png
        fig_prediction_series_recent.png
        fig_midas_weights.png
"""

from __future__ import annotations

import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import warnings
# Keep numerical and convergence warnings visible for research users.

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import statsmodels.api as sm
from scipy.optimize import minimize
from scipy import stats
from xgboost import XGBRegressor

try:
    from arch import arch_model
    ARCH_AVAILABLE = True
except Exception:
    ARCH_AVAILABLE = False

import matplotlib.pyplot as plt


# =========================================================
# 0. Configuration
# =========================================================

@dataclass
class ExperimentConfig:
    eps: float = 1e-8
    n_train: int = 1500
    n_valid: int = 500
    refit_every: int = 20
    random_state: int = 2026

    midas_refit_every: int = 60
    midas_k_grid: Tuple[int, ...] = (6, 12, 24)
    midas_weight_types: Tuple[str, ...] = ("beta", "expalmon")

    # Stage-2 MIDAS specification selection inside validation sample
    stage2_valid_train_frac: float = 0.6
    stage2_min_train_obs: int = 80
    stage2_min_valid_obs: int = 40

    # GARCH settings
    garch_dist: str = "t"       # "normal" or "t"
    garch_refit_every: int = 20

    # DM-HAC settings
    dm_hac_lag: Optional[int] = None  # None = automatic lag

    # Output and plotting
    output_dir: str = str(PROJECT_ROOT / "generated" / "csi300_epu_final_outputs")
    recent_plot_n: int = 250
    figure_dpi: int = 160
    verbose: bool = True


XGB_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=4,
    min_child_weight=3,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    objective="reg:squarederror",
    random_state=2026,
    n_jobs=-1,
)

# Explicit values equal to the SciPy defaults used in the recorded reproduction.
# This freezes the stopping rules, not the historical BLAS or floating-point path.
MIDAS_OPTIMIZER_OPTIONS = dict(
    maxcor=10, ftol=2.220446049250313e-9, gtol=1e-5, eps=1e-8,
    maxfun=15000, maxiter=15000, maxls=20,
)


# =========================================================
# 1. Utilities
# =========================================================

def log(msg: str, config: Optional[ExperimentConfig] = None):
    if config is None or config.verbose:
        print(msg, flush=True)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _as_float_scalar(x) -> float:
    return float(np.asarray(x).reshape(-1)[0])


def auto_hac_lag(n: int) -> int:
    """A conservative automatic lag for one-step financial forecast loss differences."""
    if n <= 1:
        return 0
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


# =========================================================
# 2. Data preparation, inherited from old code
# =========================================================

def prepare_main_dataframe(
    csi_df: pd.DataFrame,
    epu_df: pd.DataFrame,
    config: ExperimentConfig,
    max_month_lag: int = 24,
) -> pd.DataFrame:
    """
    Construct the daily main dataframe.

    Target is strictly one-step ahead:
        y_t = log(rv1_{t+1} + eps)
    where rv1_{t+1} = r_{t+1}^2.
    """
    eps = config.eps

    # ---------- CSI ----------
    df = csi_df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    required_cols = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSI 数据缺少字段: {missing}")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    zero_volume = int(df['volume'].eq(0).sum())
    if zero_volume:
        warnings.warn(f"Market input contains {zero_volume} zero-volume rows. "
                      "Historical target shifting precedes feature-row deletion; "
                      "audit target dates against the trading calendar before new research.", RuntimeWarning)

    # returns and one-step-ahead target
    df["ret"] = np.log(df["close"] / df["close"].shift(1))
    df["rv1"] = df["ret"] ** 2
    df["y"] = np.log(df["rv1"].shift(-1) + eps)

    # high-frequency market variables at time t
    df["log_rv1"] = np.log(df["rv1"] + eps)
    df["log_rv5"] = np.log(df["rv1"].rolling(5).mean() + eps)
    df["log_rv22"] = np.log(df["rv1"].rolling(22).mean() + eps)

    df["ret_pos"] = df["ret"].clip(lower=0.0)
    df["ret_neg"] = df["ret"].clip(upper=0.0)

    df["range_log"] = np.log(df["high"] / df["low"])
    df["range_log_5"] = df["range_log"].rolling(5).mean()

    df["log_volume"] = np.log(df["volume"].replace(0, np.nan))
    df["dlog_volume"] = df["log_volume"].diff()

    # ---------- EPU ----------
    epu = epu_df.copy()
    epu.columns = [str(c).lower().strip() for c in epu.columns]
    if "observation_date" not in epu.columns or "chnmainlandepu" not in epu.columns:
        raise ValueError("EPU 数据缺少 observation_date 或 CHNMAINLANDEPU 字段。")

    epu["observation_date"] = pd.to_datetime(epu["observation_date"])
    epu = epu.sort_values("observation_date").reset_index(drop=True)
    epu["month"] = epu["observation_date"].dt.to_period("M")
    epu["chnmainlandepu"] = pd.to_numeric(epu["chnmainlandepu"], errors="coerce")
    epu["log_epu"] = np.log(epu["chnmainlandepu"].astype(float))

    epu_month = epu[["month", "log_epu"]].dropna().copy()
    for k in range(1, max_month_lag + 1):
        # lag1 = previous month's EPU
        epu_month[f"epu_lag{k}"] = epu_month["log_epu"].shift(k)

    df["month"] = df["date"].dt.to_period("M")
    merge_cols = ["month"] + [f"epu_lag{k}" for k in range(1, max_month_lag + 1)]
    df = df.merge(epu_month[merge_cols], on="month", how="left")

    keep_cols = [
        "date", "open", "high", "low", "close", "volume",
        "y", "ret", "rv1",
        "log_rv1", "log_rv5", "log_rv22",
        "ret_pos", "ret_neg",
        "range_log", "range_log_5",
        "log_volume", "dlog_volume",
    ] + [f"epu_lag{k}" for k in range(1, max_month_lag + 1)]

    df = df[keep_cols].dropna().reset_index(drop=True)
    return df


def add_sample_flags(df: pd.DataFrame, config: ExperimentConfig) -> pd.DataFrame:
    out = df.copy()
    n = len(out)
    train_end = config.n_train
    valid_end = config.n_train + config.n_valid
    if valid_end >= n:
        raise ValueError("样本长度不足以按当前 train/valid/test 规则切分。")

    out["sample_flag"] = "test"
    out.loc[:train_end - 1, "sample_flag"] = "train"
    out.loc[train_end:valid_end - 1, "sample_flag"] = "valid"
    return out


# =========================================================
# 3. Metrics and tests
# =========================================================

def qlike_loss_from_logvar(y_true: np.ndarray, y_pred: np.ndarray, eps: float) -> np.ndarray:
    """
    Standardized QLIKE loss:
        ratio - log(ratio) - 1,
    where ratio = RV_true / RV_pred.

    This form is non-negative and smaller is better.
    """
    rv_true = np.exp(y_true) - eps
    rv_pred = np.exp(y_pred) - eps
    rv_true = np.clip(rv_true, 1e-12, None)
    rv_pred = np.clip(rv_pred, 1e-12, None)
    ratio = rv_true / rv_pred
    return ratio - np.log(ratio) - 1.0


def point_metrics(y_true: np.ndarray, y_pred: np.ndarray, eps: float) -> Dict[str, float]:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    mse = float(np.mean((y_true - y_pred) ** 2))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    qlike = float(np.mean(qlike_loss_from_logvar(y_true, y_pred, eps)))
    bias = float(np.mean(y_true - y_pred))

    return {
        "n_test": int(len(y_true)),
        "MSE": mse,
        "MAE": mae,
        "QLIKE": qlike,
        "Bias": bias,
    }


def per_observation_losses(y_true: np.ndarray, y_pred: np.ndarray, eps: float) -> pd.DataFrame:
    e = y_true - y_pred
    return pd.DataFrame({
        "error": e,
        "squared_error": e ** 2,
        "abs_error": np.abs(e),
        "qlike_loss": qlike_loss_from_logvar(y_true, y_pred, eps),
    })


def hac_se_mean(x: np.ndarray, lag: Optional[int] = None) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n <= 1:
        return np.nan
    if lag is None:
        lag = auto_hac_lag(n)
    lag = max(0, int(lag))

    xc = x - np.mean(x)
    gamma0 = np.dot(xc, xc) / n
    var = gamma0
    for l in range(1, lag + 1):
        weight = 1.0 - l / (lag + 1.0)
        gamma_l = np.dot(xc[l:], xc[:-l]) / n
        var += 2.0 * weight * gamma_l
    return float(np.sqrt(max(var / n, 1e-18)))


def dm_hac_test(loss_a: np.ndarray, loss_b: np.ndarray, hac_lag: Optional[int] = None) -> Dict[str, float]:
    """
    Diebold-Mariano test based on loss difference:
        d_t = loss_a_t - loss_b_t.
    Positive statistic means model B has lower average loss than model A.
    """
    d = np.asarray(loss_a, dtype=float) - np.asarray(loss_b, dtype=float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n <= 2:
        return {"DM_t": np.nan, "DM_p_two_sided": np.nan, "DM_p_one_sided_B_better": np.nan,
                "mean_loss_diff_A_minus_B": np.nan, "n": n, "hac_lag": np.nan}

    lag = auto_hac_lag(n) if hac_lag is None else int(hac_lag)
    se = hac_se_mean(d, lag=lag)
    t_stat = float(np.mean(d) / se)
    p_two = float(2.0 * (1.0 - stats.norm.cdf(abs(t_stat))))
    p_one = float(1.0 - stats.norm.cdf(t_stat))
    return {
        "DM_t": t_stat,
        "DM_p_two_sided": p_two,
        "DM_p_one_sided_B_better": p_one,
        "mean_loss_diff_A_minus_B": float(np.mean(d)),
        "n": int(n),
        "hac_lag": int(lag),
    }


def clark_west_test(y_true: np.ndarray, f_small: np.ndarray, f_big: np.ndarray) -> Dict[str, float]:
    """
    Clark-West test for nested models under MSPE.
    H1: the larger model improves MSPE relative to the small model.
    This follows the simple t-statistic form.
    """
    y_true = np.asarray(y_true, dtype=float)
    f_small = np.asarray(f_small, dtype=float)
    f_big = np.asarray(f_big, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(f_small) & np.isfinite(f_big)
    y_true = y_true[mask]
    f_small = f_small[mask]
    f_big = f_big[mask]

    e1 = y_true - f_small
    e2 = y_true - f_big
    f_adj = e1**2 - (e2**2 - (f_small - f_big)**2)

    n = len(f_adj)
    if n <= 2:
        return {"CW_t": np.nan, "CW_p_one_sided": np.nan, "CW_mean_adjusted_diff": np.nan, "n": n}
    mean_f = float(np.mean(f_adj))
    std_f = float(np.std(f_adj, ddof=1))
    t_stat = mean_f / (std_f / np.sqrt(n))
    p_value = float(1.0 - stats.t.cdf(t_stat, df=n - 1))
    return {"CW_t": float(t_stat), "CW_p_one_sided": p_value, "CW_mean_adjusted_diff": mean_f, "n": int(n)}


# =========================================================
# 4. MIDAS weights and estimation, inherited from old code
# =========================================================

@dataclass
class MidasResult:
    K: int
    weight_type: str
    theta: np.ndarray
    coef: np.ndarray
    sse: float
    optimizer: dict


def beta_weights(K: int, theta: np.ndarray) -> np.ndarray:
    a, b = theta
    x = np.array([(K - k + 1) / (K + 1) for k in range(1, K + 1)], dtype=float)
    w = np.power(x, a - 1.0) * np.power(1.0 - x, b - 1.0)
    w = np.clip(w, 1e-12, None)
    return w / w.sum()


def expalmon_weights(K: int, theta: np.ndarray) -> np.ndarray:
    """
    Numerically stable exponential Almon MIDAS weights.
    Convention:
        first weight -> epu_lag1, the most recent month
        K-th weight -> epu_lagK, the farthest month
    """
    a, b = theta
    x = np.array([(K - k + 1) / K for k in range(1, K + 1)], dtype=float)
    g = a * x + b * (x ** 2)
    g = g - np.max(g)
    z = np.exp(g)
    return z / np.sum(z)


def get_midas_weights(K: int, theta: np.ndarray, weight_type: str) -> np.ndarray:
    if weight_type == "beta":
        return beta_weights(K, theta)
    elif weight_type == "expalmon":
        return expalmon_weights(K, theta)
    else:
        raise ValueError(f"未知权重类型: {weight_type}")


def compute_midas_factor(lag_matrix: np.ndarray, theta: np.ndarray, weight_type: str) -> np.ndarray:
    K = lag_matrix.shape[1]
    w = get_midas_weights(K, theta, weight_type)
    return lag_matrix @ w


def estimate_midas_profiled_ols(
    y: np.ndarray,
    lag_matrix: np.ndarray,
    controls: Optional[np.ndarray],
    weight_type: str = "beta",
) -> MidasResult:
    K = lag_matrix.shape[1]

    if weight_type == "beta":
        x0 = np.array([1.5, 2.0])
        bounds = [(0.05, 20.0), (0.05, 20.0)]
    elif weight_type == "expalmon":
        x0 = np.array([-0.2, -0.02])
        bounds = [(-5.0, 5.0), (-5.0, 5.0)]
    else:
        raise ValueError("weight_type 必须是 beta 或 expalmon")

    def objective(theta):
        z = compute_midas_factor(lag_matrix, np.array(theta), weight_type).reshape(-1, 1)
        if controls is None:
            X = z
        else:
            X = np.column_stack([controls, z])
        X = sm.add_constant(X, has_constant="add")
        try:
            model = sm.OLS(y, X).fit()
            return float(np.sum(model.resid ** 2))
        except Exception:
            return 1e18

    res = minimize(objective, x0=x0, bounds=bounds, method="L-BFGS-B",
                   options=MIDAS_OPTIMIZER_OPTIONS.copy())
    theta_hat = res.x
    projected_gradient = np.asarray(res.jac, dtype=float).copy()
    for i, (lower, upper) in enumerate(bounds):
        if (theta_hat[i] <= lower and projected_gradient[i] > 0) or (theta_hat[i] >= upper and projected_gradient[i] < 0):
            projected_gradient[i] = 0.0
    gradient_norm = float(np.max(np.abs(projected_gradient)))
    diagnostics = dict(success=bool(res.success), message=str(res.message),
                       iterations=int(res.nit), projected_gradient_inf=gradient_norm,
                       gradient_tolerance_met=bool(np.isfinite(gradient_norm) and gradient_norm <= MIDAS_OPTIMIZER_OPTIONS['gtol']))
    # A relative-objective stopping condition is not a stationarity certificate.
    # Preserve the legacy estimate while making material numerical concerns visible.
    if not res.success or not np.isfinite(gradient_norm) or gradient_norm > 1e-3:
        warnings.warn(f"MIDAS numerical review: success={res.success}, "
                      f"projected gradient={gradient_norm:.6g}; {res.message}", RuntimeWarning)

    z_hat = compute_midas_factor(lag_matrix, theta_hat, weight_type).reshape(-1, 1)
    if controls is None:
        X_hat = z_hat
    else:
        X_hat = np.column_stack([controls, z_hat])
    X_hat = sm.add_constant(X_hat, has_constant="add")
    ols = sm.OLS(y, X_hat).fit()

    return MidasResult(
        K=K,
        weight_type=weight_type,
        theta=theta_hat,
        coef=ols.params,
        sse=float(np.sum(ols.resid ** 2)),
        optimizer=diagnostics,
    )


def fit_select_midas_spec_for_resid(
    df: pd.DataFrame,
    resid_col: str,
    resid_lag_col: str,
    config: ExperimentConfig,
) -> Dict:
    """
    Select second-stage MIDAS specification using true OOS residuals in the validation sample.
    """
    pool = df[df["sample_flag"] == "valid"].copy()
    best = None
    results = []
    diagnostics = []

    for K in config.midas_k_grid:
        lag_cols = [f"epu_lag{k}" for k in range(1, K + 1)]
        sub = pool.dropna(subset=[resid_col, resid_lag_col] + lag_cols).copy()
        if len(sub) < (config.stage2_min_train_obs + config.stage2_min_valid_obs):
            continue

        split_idx = int(len(sub) * config.stage2_valid_train_frac)
        split_idx = max(split_idx, config.stage2_min_train_obs)
        split_idx = min(split_idx, len(sub) - config.stage2_min_valid_obs)
        if split_idx <= 0 or split_idx >= len(sub):
            continue

        train_sub = sub.iloc[:split_idx].copy()
        valid_sub = sub.iloc[split_idx:].copy()

        if len(train_sub) < config.stage2_min_train_obs or len(valid_sub) < config.stage2_min_valid_obs:
            continue

        y_train = train_sub[resid_col].to_numpy()
        controls = train_sub[[resid_lag_col]].to_numpy()
        lag_train = train_sub[lag_cols].to_numpy()

        for wtype in config.midas_weight_types:
            try:
                midas_res = estimate_midas_profiled_ols(
                    y=y_train,
                    lag_matrix=lag_train,
                    controls=controls,
                    weight_type=wtype,
                )
                diagnostics.append(dict(phase='selection', K=K, weight_type=wtype,
                                        n_train=len(train_sub), **midas_res.optimizer))

                train_sub2 = train_sub.copy()
                valid_sub2 = valid_sub.copy()
                train_sub2["epu_midas"] = compute_midas_factor(
                    train_sub2[lag_cols].to_numpy(), midas_res.theta, wtype
                )
                valid_sub2["epu_midas"] = compute_midas_factor(
                    valid_sub2[lag_cols].to_numpy(), midas_res.theta, wtype
                )

                X_train = sm.add_constant(train_sub2[[resid_lag_col, "epu_midas"]], has_constant="add")
                ols_model = sm.OLS(train_sub2[resid_col], X_train).fit()

                X_valid = sm.add_constant(valid_sub2[[resid_lag_col, "epu_midas"]], has_constant="add")
                valid_pred = ols_model.predict(X_valid)
                mse = np.mean((valid_sub2[resid_col].to_numpy() - np.asarray(valid_pred)) ** 2)

                row = {
                    "K": K,
                    "weight_type": wtype,
                    "theta1": float(midas_res.theta[0]),
                    "theta2": float(midas_res.theta[1]),
                    "valid_MSE": float(mse),
                    "n_stage2_train": len(train_sub2),
                    "n_stage2_valid": len(valid_sub2),
                }
                results.append(row)
                if best is None or mse < best["valid_MSE"]:
                    best = row
            except Exception as error:
                warnings.warn(f"MIDAS specification failed: K={K}, type={wtype}: {error}", RuntimeWarning)
                diagnostics.append(dict(phase='selection', K=K, weight_type=wtype,
                                        success=False, message=str(error)))
                continue

    if best is None:
        raise RuntimeError(
            "没有成功选择出可用的残差修正 MIDAS 规格。请检查："
            "1) 第一阶段样本外预测是否已正确生成；"
            "2) 验证集是否有足够真实残差；"
            "3) EPU 多滞后变量是否存在缺失。"
        )

    return {
        "best_spec": best,
        "search_results": pd.DataFrame(results).sort_values("valid_MSE").reset_index(drop=True),
        "optimization_diagnostics": diagnostics,
    }


# =========================================================
# 5. Forecast models
# =========================================================

BASE_FEATURES = [
    "log_rv1", "log_rv5", "log_rv22",
    "ret_pos", "ret_neg",
    "range_log", "range_log_5",
    "log_volume", "dlog_volume",
]

HAR_FEATURES = ["log_rv1", "log_rv5", "log_rv22"]


def expanding_har(df_in: pd.DataFrame, config: ExperimentConfig) -> pd.Series:
    """HAR-type daily volatility model, estimated by expanding-window OLS."""
    preds = pd.Series(index=df_in.index, dtype=float)
    model = None
    start_pred_idx = config.n_train

    log("[Model] Running HAR ...", config)
    for j in range(start_pred_idx, len(df_in)):
        if model is None or (j - start_pred_idx) % config.refit_every == 0:
            train = df_in.iloc[:j].dropna(subset=HAR_FEATURES + ["y"])
            X_train = sm.add_constant(train[HAR_FEATURES], has_constant="add")
            model = sm.OLS(train["y"], X_train).fit()

        row = df_in.iloc[[j]]
        X_row = sm.add_constant(row[HAR_FEATURES], has_constant="add")
        preds.iloc[j] = _as_float_scalar(model.predict(X_row))

    return preds


def expanding_xgb_market(df_in: pd.DataFrame, features: List[str], config: ExperimentConfig, xgb_params: Dict) -> pd.Series:
    """XGB-Market model, inherited from old code."""
    preds = pd.Series(index=df_in.index, dtype=float)
    model = None
    start_pred_idx = config.n_train

    log("[Model] Running XGB-Market ...", config)
    for j in range(start_pred_idx, len(df_in)):
        if model is None or (j - start_pred_idx) % config.refit_every == 0:
            train = df_in.iloc[:j].dropna(subset=features + ["y"])
            model = XGBRegressor(**xgb_params)
            model.fit(train[features], train["y"])

        row = df_in.iloc[[j]]
        preds.iloc[j] = float(model.predict(row[features])[0])

    return preds


def expanding_garch(df_in: pd.DataFrame, config: ExperimentConfig) -> pd.Series:
    """
    GARCH(1,1) one-step-ahead conditional variance forecast.

    At row j, information through r_j is available, and the target is r_{j+1}^2.
    The forecast is log(h_{j+1} + eps).
    """
    if not ARCH_AVAILABLE:
        raise ImportError("请先安装 arch: pip install arch")

    preds = pd.Series(index=df_in.index, dtype=float)
    start_pred_idx = config.n_train

    omega = alpha = beta = None
    h_current = None  # conditional variance for current day, in percent-return scale

    log("[Model] Running GARCH(1,1) ...", config)
    for j in range(start_pred_idx, len(df_in)):
        refit_now = (j == start_pred_idx) or ((j - start_pred_idx) % config.garch_refit_every == 0)

        if refit_now:
            ret_hist = df_in.iloc[:j + 1]["ret"].dropna() * 100.0
            am = arch_model(ret_hist, mean="Zero", vol="GARCH", p=1, q=1, dist=config.garch_dist)
            res = am.fit(disp="off")
            params = res.params
            omega = float(params.get("omega"))
            alpha = float(params.get("alpha[1]"))
            beta = float(params.get("beta[1]"))
            h_current = float(np.asarray(res.conditional_volatility)[-1] ** 2)

        # h_{j+1} = omega + alpha * r_j^2 + beta * h_j, all in percent-return scale
        ret_j_pct = float(df_in.iloc[j]["ret"] * 100.0)
        h_next_pct = omega + alpha * (ret_j_pct ** 2) + beta * h_current
        h_next = max(h_next_pct / (100.0 ** 2), 1e-12)
        preds.iloc[j] = float(np.log(h_next + config.eps))

        # for the next step, h_{j+1} becomes current conditional variance
        h_current = h_next_pct

    return preds


def run_xgb_midas_epu_dec(
    df: pd.DataFrame,
    base_pred_col: str,
    config: ExperimentConfig,
) -> Tuple[pd.Series, Dict]:
    """
    XGB-MIDAS-EPU-DEC model.
    Stage 2:
        e_t = const + phi * e_{t-1} + gamma * MIDAS_EPU_t + u_t
    """
    log("[Model] Running XGB-MIDAS-EPU-DEC ...", config)

    out = df.copy()
    out["base_resid"] = out["y"] - out[base_pred_col]
    out["base_resid_lag1"] = out["base_resid"].shift(1)

    spec_info = fit_select_midas_spec_for_resid(
        out,
        resid_col="base_resid",
        resid_lag_col="base_resid_lag1",
        config=config,
    )
    best = spec_info["best_spec"]
    K = int(best["K"])
    wtype = best["weight_type"]
    lag_cols = [f"epu_lag{k}" for k in range(1, K + 1)]

    corr_pred = pd.Series(index=out.index, dtype=float)
    start_pred_idx = config.n_train + config.n_valid

    theta_hat = None
    ols_model = None

    for j in range(start_pred_idx, len(out)):
        if (j - start_pred_idx) % config.midas_refit_every == 0:
            train = out.iloc[:j].dropna(subset=["base_resid", "base_resid_lag1"] + lag_cols).copy()
            if len(train) < config.stage2_min_train_obs:
                continue

            midas_res = estimate_midas_profiled_ols(
                y=train["base_resid"].to_numpy(),
                lag_matrix=train[lag_cols].to_numpy(),
                controls=train[["base_resid_lag1"]].to_numpy(),
                weight_type=wtype,
            )
            spec_info['optimization_diagnostics'].append(dict(
                phase='test_refit', origin_date=str(out.iloc[j]['date'])[:10],
                K=K, weight_type=wtype, n_train=len(train), **midas_res.optimizer))
            theta_hat = midas_res.theta

            train["epu_midas"] = compute_midas_factor(train[lag_cols].to_numpy(), theta_hat, wtype)
            X_train = sm.add_constant(train[["base_resid_lag1", "epu_midas"]], has_constant="add")
            ols_model = sm.OLS(train["base_resid"], X_train).fit()

        row = out.iloc[[j]].copy()
        if theta_hat is None or ols_model is None:
            continue
        if row[["base_resid_lag1"] + lag_cols].isna().any(axis=None):
            continue

        row["epu_midas"] = compute_midas_factor(row[lag_cols].to_numpy(), theta_hat, wtype)
        X_row = sm.add_constant(row[["base_resid_lag1", "epu_midas"]], has_constant="add")
        corr_pred.iloc[j] = _as_float_scalar(ols_model.predict(X_row))

    final_pred = out[base_pred_col] + corr_pred
    return final_pred, spec_info


# =========================================================
# 6. Output construction
# =========================================================

def build_model_output(df: pd.DataFrame, pred_col: str, model_name: str, config: ExperimentConfig) -> pd.DataFrame:
    cols = [
        "date", "sample_flag", "open", "high", "low", "close", "volume",
        "ret", "rv1", "y",
        "log_rv1", "log_rv5", "log_rv22", "ret_pos", "ret_neg",
        "range_log", "range_log_5", "log_volume", "dlog_volume",
        pred_col,
    ]
    available = [c for c in cols if c in df.columns]
    out = df[available].copy().rename(columns={pred_col: "yhat"})
    out["model"] = model_name

    mask = out["sample_flag"].eq("test") & out["y"].notna() & out["yhat"].notna()
    losses = per_observation_losses(out.loc[mask, "y"].to_numpy(), out.loc[mask, "yhat"].to_numpy(), config.eps)
    for c in losses.columns:
        out[c] = np.nan
        out.loc[mask, c] = losses[c].to_numpy()

    out["cum_qlike_loss"] = np.nan
    out.loc[mask, "cum_qlike_loss"] = out.loc[mask, "qlike_loss"].cumsum()
    return out


def evaluate_all_models(df: pd.DataFrame, model_cols: Dict[str, str], config: ExperimentConfig) -> pd.DataFrame:
    rows = []
    test_df = df[df["sample_flag"] == "test"].copy()
    for model_name, col in model_cols.items():
        tmp = test_df.dropna(subset=["y", col]).copy()
        metrics = point_metrics(tmp["y"].to_numpy(), tmp[col].to_numpy(), config.eps)
        rows.append({"model": model_name, **metrics})
    return pd.DataFrame(rows).sort_values("QLIKE").reset_index(drop=True)


def build_loss_panel(df: pd.DataFrame, model_cols: Dict[str, str], config: ExperimentConfig) -> pd.DataFrame:
    test_df = df[df["sample_flag"] == "test"].copy()
    panel = test_df[["date", "y"]].copy()
    for model_name, col in model_cols.items():
        panel[f"yhat_{model_name}"] = test_df[col]
        mask = panel["y"].notna() & panel[f"yhat_{model_name}"].notna()
        panel[f"qlike_{model_name}"] = np.nan
        panel.loc[mask, f"qlike_{model_name}"] = qlike_loss_from_logvar(
            panel.loc[mask, "y"].to_numpy(),
            panel.loc[mask, f"yhat_{model_name}"].to_numpy(),
            config.eps,
        )
        panel[f"se_{model_name}"] = (panel["y"] - panel[f"yhat_{model_name}"]) ** 2
    return panel.reset_index(drop=True)


# =========================================================
# 7. Hypothesis tests
# =========================================================

def pairwise_dm_from_loss_panel(
    loss_panel: pd.DataFrame,
    model_a: str,
    model_b: str,
    config: ExperimentConfig,
    note: str = "",
) -> Dict[str, float]:
    """DM-HAC on QLIKE. Positive DM means model B is better than model A."""
    col_a = f"qlike_{model_a}"
    col_b = f"qlike_{model_b}"
    tmp = loss_panel.dropna(subset=[col_a, col_b]).copy()
    res = dm_hac_test(tmp[col_a].to_numpy(), tmp[col_b].to_numpy(), hac_lag=config.dm_hac_lag)
    return {
        "comparison": f"{model_b} vs {model_a}",
        "model_A": model_a,
        "model_B": model_b,
        "test": "DM-HAC",
        "loss": "QLIKE",
        "interpretation": "positive statistic means model_B has lower QLIKE than model_A",
        "note": note,
        **res,
    }


def pairwise_cw_from_loss_panel(
    loss_panel: pd.DataFrame,
    small_model: str,
    big_model: str,
    note: str = "",
) -> Dict[str, float]:
    """Clark-West on MSPE. Positive CW means big model improves over small model."""
    y_col = "y"
    fs_col = f"yhat_{small_model}"
    fb_col = f"yhat_{big_model}"
    tmp = loss_panel.dropna(subset=[y_col, fs_col, fb_col]).copy()
    res = clark_west_test(tmp[y_col].to_numpy(), tmp[fs_col].to_numpy(), tmp[fb_col].to_numpy())
    return {
        "comparison": f"{big_model} vs {small_model}",
        "model_A": small_model,
        "model_B": big_model,
        "test": "Clark-West",
        "loss": "MSPE",
        "interpretation": "positive statistic means model_B improves MSPE over nested small model_A",
        "note": note,
        **res,
    }


def run_default_hypothesis_tests(loss_panel: pd.DataFrame, config: ExperimentConfig) -> pd.DataFrame:
    """
    Main tests for the four-paper-model setup.
    DM-HAC uses QLIKE for non-nested comparisons.
    Clark-West uses MSPE for the nested comparison XGB_MIDAS_EPU_DEC vs XGB_Market.
    """
    rows = []

    # 1. Traditional benchmarks
    rows.append(pairwise_dm_from_loss_panel(
        loss_panel, "HAR", "GARCH", config,
        note="Traditional benchmark comparison."
    ))

    # 2. Machine learning vs traditional benchmarks
    rows.append(pairwise_dm_from_loss_panel(
        loss_panel, "HAR", "XGB_Market", config,
        note="Does XGB-Market outperform HAR under QLIKE?"
    ))
    rows.append(pairwise_dm_from_loss_panel(
        loss_panel, "GARCH", "XGB_Market", config,
        note="Does XGB-Market outperform GARCH under QLIKE?"
    ))

    # 3. Final model vs traditional benchmarks
    rows.append(pairwise_dm_from_loss_panel(
        loss_panel, "HAR", "XGB_MIDAS_EPU_DEC", config,
        note="Does the final model outperform HAR under QLIKE?"
    ))
    rows.append(pairwise_dm_from_loss_panel(
        loss_panel, "GARCH", "XGB_MIDAS_EPU_DEC", config,
        note="Does the final model outperform GARCH under QLIKE?"
    ))

    # 4. Core nested comparison: final model vs XGB-Market
    rows.append(pairwise_cw_from_loss_panel(
        loss_panel, "XGB_Market", "XGB_MIDAS_EPU_DEC",
        note="Core nested comparison. Clark-West is reported under MSPE."
    ))

    # Optional descriptive QLIKE-DM for the same pair; not used as primary nested evidence.
    rows.append(pairwise_dm_from_loss_panel(
        loss_panel, "XGB_Market", "XGB_MIDAS_EPU_DEC", config,
        note="Supplementary QLIKE loss-difference description for the nested pair; not the primary nested-model evidence."
    ))

    return pd.DataFrame(rows)


# =========================================================
# 8. Visualization
# =========================================================

def plot_metrics_bar(metrics: pd.DataFrame, output_path: str, config: ExperimentConfig):
    plot_df = metrics.copy().sort_values("QLIKE")
    x = np.arange(len(plot_df))

    fig, ax = plt.subplots(figsize=(9, 5), dpi=config.figure_dpi)
    ax.bar(x, plot_df["QLIKE"].to_numpy())
    ax.set_xticks(x)
    ax.set_xticklabels(plot_df["model"], rotation=25, ha="right")
    ax.set_ylabel("Average QLIKE Loss")
    ax.set_title("Out-of-sample QLIKE Comparison")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def plot_cumulative_qlike_diff(loss_panel: pd.DataFrame, output_path: str, config: ExperimentConfig):
    """
    Cumulative QLIKE loss difference:
        cumulative(QLIKE_benchmark - QLIKE_final)
    Upward trend means the final model is cumulatively better.
    """
    final = "XGB_MIDAS_EPU_DEC"
    benchmarks = ["HAR", "GARCH", "XGB_Market"]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=config.figure_dpi)
    for b in benchmarks:
        cols = ["date", f"qlike_{b}", f"qlike_{final}"]
        tmp = loss_panel[cols].dropna().copy()
        if tmp.empty:
            continue
        diff = tmp[f"qlike_{b}"] - tmp[f"qlike_{final}"]
        ax.plot(tmp["date"], diff.cumsum(), label=f"{b} - {final}", linewidth=1.4)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_title("Cumulative QLIKE Loss Difference")
    ax.set_ylabel("Cumulative loss difference")
    ax.legend(frameon=False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def plot_prediction_series(loss_panel: pd.DataFrame, output_path: str, config: ExperimentConfig):
    n = min(config.recent_plot_n, len(loss_panel))
    tmp = loss_panel.tail(n).copy()

    fig, ax = plt.subplots(figsize=(11, 5), dpi=config.figure_dpi)
    ax.plot(tmp["date"], tmp["y"], label="Actual", linewidth=1.5)
    for m in ["HAR", "GARCH", "XGB_Market", "XGB_MIDAS_EPU_DEC"]:
        ax.plot(tmp["date"], tmp[f"yhat_{m}"], label=m, linewidth=1.0, alpha=0.9)

    ax.set_title(f"Actual and Forecasted Log Volatility: Recent {n} Test Days")
    ax.set_ylabel(r"$\log(r_{t+1}^2+\varepsilon)$")
    ax.legend(frameon=False, ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def plot_midas_weights(best_spec: Dict, output_path: str, config: ExperimentConfig):
    K = int(best_spec["K"])
    wtype = best_spec["weight_type"]
    theta = np.array([best_spec["theta1"], best_spec["theta2"]], dtype=float)
    weights = get_midas_weights(K, theta, wtype)

    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=config.figure_dpi)
    ax.bar(np.arange(1, K + 1), weights)
    ax.set_xlabel("Monthly EPU lag")
    ax.set_ylabel("MIDAS weight")
    ax.set_title(f"Selected MIDAS Weights for Residual Correction ({wtype}, K={K})")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


# =========================================================
# 9. Main experiment
# =========================================================

def run_final_experiment(
    csi_df: pd.DataFrame,
    epu_df: pd.DataFrame,
    config: ExperimentConfig,
    xgb_params: Dict = XGB_PARAMS,
    max_month_lag: int = 24,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
    ensure_dir(config.output_dir)

    log("=" * 80, config)
    log("Preparing data ...", config)
    df = prepare_main_dataframe(csi_df, epu_df, config, max_month_lag=max_month_lag)
    df = add_sample_flags(df, config)

    log(f"Final usable sample size: {len(df)}", config)
    log(f"Train: {sum(df['sample_flag']=='train')}, Valid: {sum(df['sample_flag']=='valid')}, Test: {sum(df['sample_flag']=='test')}", config)
    log(f"Date range: {df['date'].min().date()} -> {df['date'].max().date()}", config)
    df.to_csv(os.path.join(config.output_dir, "prepared_master_data.csv"), index=False, encoding="utf-8-sig")

    log("=" * 80, config)
    log("Running models ...", config)

    df["yhat_har"] = expanding_har(df, config)
    df["yhat_garch"] = expanding_garch(df, config)
    df["yhat_xgb_market"] = expanding_xgb_market(df, BASE_FEATURES, config, xgb_params)
    df["yhat_xgb_midas_dec"], spec_dec = run_xgb_midas_epu_dec(df, "yhat_xgb_market", config)

    model_cols = {
        "HAR": "yhat_har",
        "GARCH": "yhat_garch",
        "XGB_Market": "yhat_xgb_market",
        "XGB_MIDAS_EPU_DEC": "yhat_xgb_midas_dec",
    }

    log("=" * 80, config)
    log("Saving per-model prediction files ...", config)
    for model_name, col in model_cols.items():
        out = build_model_output(df, col, model_name, config)
        out.to_csv(
            os.path.join(config.output_dir, f"predictions_{model_name}.csv"),
            index=False,
            encoding="utf-8-sig",
        )

    all_pred_cols = ["date", "sample_flag", "y"] + list(model_cols.values())
    df[all_pred_cols].to_csv(os.path.join(config.output_dir, "all_model_predictions.csv"), index=False, encoding="utf-8-sig")

    metrics = evaluate_all_models(df, model_cols, config)
    metrics.to_csv(os.path.join(config.output_dir, "metrics_summary.csv"), index=False, encoding="utf-8-sig")
    log("\nMetrics summary:", config)
    print(metrics)

    loss_panel = build_loss_panel(df, model_cols, config)
    loss_panel.to_csv(os.path.join(config.output_dir, "loss_panel.csv"), index=False, encoding="utf-8-sig")

    tests = run_default_hypothesis_tests(loss_panel, config)
    tests.to_csv(os.path.join(config.output_dir, "hypothesis_tests.csv"), index=False, encoding="utf-8-sig")
    log("\nHypothesis tests:", config)
    print(tests)

    # MIDAS metadata
    search_results = spec_dec["search_results"]
    best_spec = spec_dec["best_spec"]
    search_results.to_csv(os.path.join(config.output_dir, "midas_dec_search_results.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([best_spec]).to_csv(os.path.join(config.output_dir, "midas_dec_best_spec.csv"), index=False, encoding="utf-8-sig")
    Path(config.output_dir, 'midas_optimizer_diagnostics.json').write_text(
        json.dumps(spec_dec['optimization_diagnostics'], indent=2) + '\n', encoding='utf-8')

    K = int(best_spec["K"])
    theta = np.array([best_spec["theta1"], best_spec["theta2"]], dtype=float)
    weights = get_midas_weights(K, theta, best_spec["weight_type"])
    weights_df = pd.DataFrame({"lag_month": np.arange(1, K + 1), "weight": weights})
    weights_df.to_csv(os.path.join(config.output_dir, "midas_dec_weights.csv"), index=False, encoding="utf-8-sig")

    # Figures
    log("=" * 80, config)
    log("Drawing figures ...", config)
    plot_metrics_bar(metrics, os.path.join(config.output_dir, "fig_metrics_bar.png"), config)
    plot_cumulative_qlike_diff(loss_panel, os.path.join(config.output_dir, "fig_cumulative_qlike_diff.png"), config)
    plot_prediction_series(loss_panel, os.path.join(config.output_dir, "fig_prediction_series_recent.png"), config)
    plot_midas_weights(best_spec, os.path.join(config.output_dir, "fig_midas_weights.png"), config)

    meta = {"spec_dec": spec_dec, "midas_dec_weights": weights_df}
    log(f"\nAll outputs saved to: {config.output_dir}", config)
    return df, metrics, tests, meta


# =========================================================
# 10. Example call
# =========================================================

if __name__ == "__main__":
    # 修改为你的本地文件路径
    csi_path = str(PROJECT_ROOT / "data" / "CSI300_daily_20100104_20260331.xlsx")
    epu_path = str(PROJECT_ROOT / "data" / "epu_newVersion_2000-2026.xlsx")

    csi_df = pd.read_excel(csi_path)
    # 若 EPU 文件第一张表不是 monthly，请改成 sheet_name="Monthly"
    epu_df = pd.read_excel(epu_path, sheet_name="Monthly")

    config = ExperimentConfig(
        eps=1e-8,
        n_train=1500,
        n_valid=500,
        refit_every=20,
        random_state=2026,
        midas_refit_every=60,
        midas_k_grid=(6, 12, 24),
        midas_weight_types=("beta", "expalmon"),
        output_dir=str(PROJECT_ROOT / "generated" / "csi300_epu_final_outputs"),
        verbose=True,
    )

    df_out, metrics_summary, hypothesis_tests, meta = run_final_experiment(
        csi_df=csi_df,
        epu_df=epu_df,
        config=config,
        xgb_params=XGB_PARAMS,
        max_month_lag=24,
    )

    print("\nSelected MIDAS residual-correction specification:")
    print(meta["spec_dec"]["best_spec"])
