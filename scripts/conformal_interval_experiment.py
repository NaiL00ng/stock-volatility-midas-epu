"""
Rolling conformal prediction intervals for CSI 300 volatility forecasting.

This script is designed to be run AFTER the main point-forecast experiment.
It reads the saved point predictions and constructs rolling sequential conformal
prediction intervals for:
    - HAR
    - GARCH
    - XGB_Market
    - XGB_MIDAS_EPU_DEC

Academic design choices implemented here:
1. Intervals are evaluated on the log-volatility scale y = log(RV_{t+1}+eps).
   RV-scale intervals are saved only for interpretation/visualization.
2. Calibration is rolling and sequential: for test date t, only past OOS residuals
   from the validation period and previously realized test observations are used.
3. Interval Score is the primary interval-quality metric. Coverage is treated as
   a validity constraint; average width is auxiliary.
4. HAR and GARCH use the same rolling conformal construction as XGB-based models,
   using the same construction; compare on common evaluation dates for fairness.

Expected input from the main experiment:
    csi300_epu_final_outputs/all_model_predictions.csv
with at least:
    date, sample_flag, y,
    yhat_har, yhat_garch, yhat_xgb_market, yhat_xgb_midas_dec

Project author: Boursin Nickel. Original script developed with AI assistance.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt


# =========================================================
# 0. Configuration
# =========================================================

@dataclass
class IntervalConfig:
    input_predictions_path: str = str(PROJECT_ROOT / "generated" / "csi300_epu_final_outputs" / "all_model_predictions.csv")
    output_dir: str = str(PROJECT_ROOT / "generated" / "csi300_epu_interval_outputs")
    eps: float = 1e-8

    # Main conformal settings
    alpha_list: Tuple[float, ...] = (0.10, 0.05)      # 90% and 95% intervals
    calibration_windows: Tuple[int, ...] = (120, 250, 500)
    main_alpha: float = 0.10
    main_window: int = 250

    # If fewer past residuals than this are available, interval is not reported.
    # Archived DEC has no validation predictions and needs 60 realized test residuals.
    min_calibration_obs: int = 60

    # Legacy heuristic alert threshold, NOT a statistical validity test.
    # Flagged if coverage < nominal_coverage - coverage_tolerance; not a validity theorem.
    coverage_tolerance: float = 0.10

    # Plot settings
    recent_n_plot: int = 250
    rolling_coverage_window: int = 60
    figure_dpi: int = 300

    # Candidate column names for robust compatibility with previous scripts
    model_col_candidates: Dict[str, Tuple[str, ...]] = None

    def __post_init__(self):
        if self.model_col_candidates is None:
            self.model_col_candidates = {
                "HAR": ("yhat_har", "yhat_HAR", "HAR"),
                "GARCH": ("yhat_garch", "yhat_GARCH", "GARCH"),
                "XGB_Market": ("yhat_xgb_market", "yhat_XGB_Market", "yhat_XGB-Market", "XGB_Market"),
                "XGB_MIDAS_EPU_DEC": (
                    "yhat_xgb_midas_dec",
                    "yhat_XGB_MIDAS_EPU_DEC",
                    "yhat_XGB-MIDAS-EPU-DEC",
                    "XGB_MIDAS_EPU_DEC",
                ),
            }


# =========================================================
# 1. Utility functions
# =========================================================

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def safe_log_likelihood_binomial(k_success: float, n_total: float, p: float) -> float:
    """Log likelihood for k successes in n Bernoulli trials with prob p."""
    if n_total <= 0:
        return 0.0
    p = float(np.clip(p, 1e-12, 1.0 - 1e-12))
    k_success = float(k_success)
    return k_success * np.log(p) + (n_total - k_success) * np.log(1.0 - p)


def resolve_model_columns(df: pd.DataFrame, config: IntervalConfig) -> Dict[str, str]:
    """Find prediction columns for the four paper models."""
    resolved = {}
    existing = set(df.columns)
    for model, candidates in config.model_col_candidates.items():
        found = None
        for col in candidates:
            if col in existing:
                found = col
                break
        if found is None:
            raise ValueError(
                f"Cannot find prediction column for {model}. Tried: {candidates}. "
                f"Available columns: {list(df.columns)}"
            )
        resolved[model] = found
    return resolved


def load_prediction_panel(config: IntervalConfig) -> Tuple[pd.DataFrame, Dict[str, str]]:
    if not os.path.exists(config.input_predictions_path):
        raise FileNotFoundError(f"Input file not found: {config.input_predictions_path}")

    df = pd.read_csv(config.input_predictions_path)
    df.columns = [str(c).strip() for c in df.columns]

    required = ["date", "y"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Input predictions file is missing required columns: {missing}")

    if "sample_flag" not in df.columns:
        raise ValueError(
            "Input predictions file must contain sample_flag = train/valid/test. "
            "This is needed to avoid using test information during calibration."
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["sample_flag"] = df["sample_flag"].astype(str).str.lower()

    model_cols = resolve_model_columns(df, config)
    return df, model_cols


# =========================================================
# 2. Rolling conformal interval construction
# =========================================================

def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """
    Split-conformal finite-sample quantile.

    For n calibration scores, use order statistic at ceil((n+1)*(1-alpha)).
    Legacy behavior caps the index at n. This is not a general coverage guarantee.
    The paper settings (n >= 60, alpha in {0.05, 0.10}) never hit this boundary.
    """
    scores = np.asarray(scores, dtype=float)
    scores = scores[np.isfinite(scores)]
    n = len(scores)
    if n == 0:
        return np.nan
    sorted_scores = np.sort(scores)
    rank = int(np.ceil((n + 1) * (1.0 - alpha)))
    rank = min(max(rank, 1), n)
    return float(sorted_scores[rank - 1])


def interval_score(y: np.ndarray, lower: np.ndarray, upper: np.ndarray, alpha: float) -> np.ndarray:
    """
    Interval Score on the same scale as y.
    Lower is better. This is the primary interval-quality metric.
    """
    y = np.asarray(y, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    width = upper - lower
    below = y < lower
    above = y > upper
    score = width.copy()
    score += (2.0 / alpha) * (lower - y) * below
    score += (2.0 / alpha) * (y - upper) * above
    return score


def rolling_conformal_intervals_for_model(
    df: pd.DataFrame,
    model_name: str,
    pred_col: str,
    alpha: float,
    window: int,
    config: IntervalConfig,
) -> pd.DataFrame:
    """
    Construct rolling sequential conformal prediction intervals for one model.

    Calibration rule:
    For each test index i, use only rows with index < i and sample_flag in {valid, test}.
    This means validation residuals and already realized test residuals are allowed;
    future test residuals are never used.
    """
    out = df[["date", "sample_flag", "y", pred_col]].copy().rename(columns={pred_col: "yhat"})
    out["model"] = model_name
    out["alpha"] = alpha
    out["nominal_coverage"] = 1.0 - alpha
    out["calibration_window"] = window

    # Absolute residual scores on log-volatility scale.
    out["resid"] = out["y"] - out["yhat"]
    out["abs_resid"] = np.abs(out["resid"])

    for c in ["qhat", "lower_y", "upper_y", "covered", "width_y", "interval_score"]:
        out[c] = np.nan

    # RV-scale columns are saved for interpretation/visualization only, not evaluation.
    for c in ["rv_true", "rv_pred", "lower_rv", "upper_rv", "width_rv"]:
        out[c] = np.nan

    test_indices = out.index[out["sample_flag"].eq("test")].to_numpy()

    for i in test_indices:
        if not np.isfinite(out.at[i, "yhat"]):
            continue

        hist = out.loc[: i - 1].copy()
        hist = hist[hist["sample_flag"].isin(["valid", "test"])]
        hist = hist[np.isfinite(hist["abs_resid"])]
        if len(hist) < config.min_calibration_obs:
            continue

        recent_scores = hist["abs_resid"].tail(window).to_numpy()
        if len(recent_scores) < min(config.min_calibration_obs, window):
            continue

        qhat = conformal_quantile(recent_scores, alpha=alpha)
        yhat = float(out.at[i, "yhat"])
        lower_y = yhat - qhat
        upper_y = yhat + qhat
        y_i = float(out.at[i, "y"])

        out.at[i, "qhat"] = qhat
        out.at[i, "lower_y"] = lower_y
        out.at[i, "upper_y"] = upper_y
        out.at[i, "covered"] = float(lower_y <= y_i <= upper_y)
        out.at[i, "width_y"] = upper_y - lower_y
        out.at[i, "interval_score"] = interval_score(
            np.array([y_i]), np.array([lower_y]), np.array([upper_y]), alpha
        )[0]

        # Original RV scale for visualization only.
        rv_true = max(float(np.exp(y_i) - config.eps), 0.0)
        rv_pred = max(float(np.exp(yhat) - config.eps), 0.0)
        lower_rv = max(float(np.exp(lower_y) - config.eps), 0.0)
        upper_rv = max(float(np.exp(upper_y) - config.eps), 0.0)
        out.at[i, "rv_true"] = rv_true
        out.at[i, "rv_pred"] = rv_pred
        out.at[i, "lower_rv"] = lower_rv
        out.at[i, "upper_rv"] = upper_rv
        out.at[i, "width_rv"] = upper_rv - lower_rv

    return out


# =========================================================
# 3. Interval evaluation and coverage tests
# =========================================================

def christoffersen_tests(covered: np.ndarray, alpha: float) -> Dict[str, float]:
    """
    Christoffersen-style coverage diagnostics for interval violations.

    Input:
        covered: 1 if y is inside interval, 0 otherwise.
        alpha: nominal violation probability.

    Returns:
        UC: unconditional coverage test
        IND: independence test
        CC: conditional coverage test
    """
    covered = np.asarray(covered, dtype=float)
    covered = covered[np.isfinite(covered)]
    if len(covered) < 5:
        return {
            "n_eval": int(len(covered)),
            "n_violations": np.nan,
            "violation_rate": np.nan,
            "LR_uc": np.nan,
            "p_uc": np.nan,
            "LR_ind": np.nan,
            "p_ind": np.nan,
            "LR_cc": np.nan,
            "p_cc": np.nan,
        }

    # Violation indicator: 1 = interval miss.
    v = 1.0 - covered
    T = len(v)
    x = int(np.sum(v))
    phat = x / T

    # UC test.
    ll_null = safe_log_likelihood_binomial(x, T, alpha)
    ll_alt = safe_log_likelihood_binomial(x, T, phat)
    LR_uc = max(-2.0 * (ll_null - ll_alt), 0.0)
    p_uc = 1.0 - stats.chi2.cdf(LR_uc, df=1)

    # IND test based on transition counts.
    v0 = v[:-1].astype(int)
    v1 = v[1:].astype(int)
    n00 = int(np.sum((v0 == 0) & (v1 == 0)))
    n01 = int(np.sum((v0 == 0) & (v1 == 1)))
    n10 = int(np.sum((v0 == 1) & (v1 == 0)))
    n11 = int(np.sum((v0 == 1) & (v1 == 1)))

    n0 = n00 + n01
    n1 = n10 + n11
    pi = (n01 + n11) / max(n0 + n1, 1)
    pi0 = n01 / n0 if n0 > 0 else pi
    pi1 = n11 / n1 if n1 > 0 else pi

    ll_ind_null = safe_log_likelihood_binomial(n01 + n11, n0 + n1, pi)
    ll_ind_alt = safe_log_likelihood_binomial(n01, n0, pi0) + safe_log_likelihood_binomial(n11, n1, pi1)
    LR_ind = max(-2.0 * (ll_ind_null - ll_ind_alt), 0.0)
    p_ind = 1.0 - stats.chi2.cdf(LR_ind, df=1)

    LR_cc = LR_uc + LR_ind
    p_cc = 1.0 - stats.chi2.cdf(LR_cc, df=2)

    return {
        "n_eval": int(T),
        "n_violations": int(x),
        "violation_rate": float(phat),
        "transition_n00": n00,
        "transition_n01": n01,
        "transition_n10": n10,
        "transition_n11": n11,
        "LR_uc": float(LR_uc),
        "p_uc": float(p_uc),
        "LR_ind": float(LR_ind),
        "p_ind": float(p_ind),
        "LR_cc": float(LR_cc),
        "p_cc": float(p_cc),
    }


def summarize_interval_result(interval_df: pd.DataFrame, config: IntervalConfig) -> Dict[str, float]:
    tmp = interval_df[interval_df["sample_flag"].eq("test")].dropna(
        subset=["y", "yhat", "lower_y", "upper_y", "covered", "width_y", "interval_score"]
    ).copy()

    if tmp.empty:
        return {
            "model": interval_df["model"].iloc[0],
            "alpha": float(interval_df["alpha"].iloc[0]),
            "nominal_coverage": float(interval_df["nominal_coverage"].iloc[0]),
            "calibration_window": int(interval_df["calibration_window"].iloc[0]),
            "n_eval": 0,
            "empirical_coverage": np.nan,
            "avg_width_y": np.nan,
            "median_width_y": np.nan,
            "avg_interval_score": np.nan,
            "coverage_valid": False,
        }

    alpha = float(tmp["alpha"].iloc[0])
    nominal = 1.0 - alpha
    coverage = float(tmp["covered"].mean())
    valid_cutoff = nominal - config.coverage_tolerance

    return {
        "model": tmp["model"].iloc[0],
        "alpha": alpha,
        "nominal_coverage": nominal,
        "calibration_window": int(tmp["calibration_window"].iloc[0]),
        "n_eval": int(len(tmp)),
        "empirical_coverage": coverage,
        "coverage_valid_cutoff": valid_cutoff,
        "coverage_valid": bool(coverage >= valid_cutoff),
        "avg_width_y": float(tmp["width_y"].mean()),
        "median_width_y": float(tmp["width_y"].median()),
        "avg_interval_score": float(tmp["interval_score"].mean()),
        "median_interval_score": float(tmp["interval_score"].median()),
    }


# =========================================================
# 4. Visualization
# =========================================================

def plot_main_interval_scores(summary: pd.DataFrame, output_path: str, config: IntervalConfig) -> None:
    plot_df = summary[
        (summary["alpha"] == config.main_alpha) &
        (summary["calibration_window"] == config.main_window)
    ].copy()
    plot_df = plot_df.sort_values("avg_interval_score")

    fig, ax = plt.subplots(figsize=(9, 5), dpi=config.figure_dpi)
    ax.bar(np.arange(len(plot_df)), plot_df["avg_interval_score"].to_numpy())
    ax.set_xticks(np.arange(len(plot_df)))
    ax.set_xticklabels(plot_df["model"], rotation=25, ha="right")
    ax.set_ylabel("Average Interval Score (log-volatility scale)")
    ax.set_title(f"Interval Score Comparison: {int((1-config.main_alpha)*100)}% intervals, m={config.main_window}")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_coverage_width_tradeoff(summary: pd.DataFrame, output_path: str, config: IntervalConfig) -> None:
    plot_df = summary[
        (summary["alpha"] == config.main_alpha) &
        (summary["calibration_window"] == config.main_window)
    ].copy()

    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=config.figure_dpi)
    ax.scatter(plot_df["avg_width_y"], plot_df["empirical_coverage"], s=80)
    for _, row in plot_df.iterrows():
        ax.annotate(row["model"], (row["avg_width_y"], row["empirical_coverage"]), xytext=(4, 4), textcoords="offset points", fontsize=9)
    ax.axhline(1.0 - config.main_alpha, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Average interval width (log-volatility scale)")
    ax.set_ylabel("Empirical coverage")
    ax.set_title(f"Coverage--Width Tradeoff: {int((1-config.main_alpha)*100)}% intervals, m={config.main_window}")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_interval_series(interval_df: pd.DataFrame, output_path: str, config: IntervalConfig, model_name: str) -> None:
    tmp = interval_df[interval_df["sample_flag"].eq("test")].dropna(
        subset=["y", "yhat", "lower_y", "upper_y"]
    ).copy()
    tmp = tmp.tail(config.recent_n_plot)
    if tmp.empty:
        return

    fig, ax = plt.subplots(figsize=(11, 5), dpi=config.figure_dpi)
    x = tmp["date"]
    ax.plot(x, tmp["y"], label="Actual y", linewidth=1.1)
    ax.plot(x, tmp["yhat"], label="Point forecast", linewidth=1.1)
    ax.fill_between(x, tmp["lower_y"].to_numpy(), tmp["upper_y"].to_numpy(), alpha=0.25, label="Prediction interval")
    ax.set_title(f"Rolling Conformal Prediction Interval: {model_name}")
    ax.set_ylabel("Log-volatility target")
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_rolling_coverage(all_main_intervals: pd.DataFrame, output_path: str, config: IntervalConfig) -> None:
    fig, ax = plt.subplots(figsize=(11, 5), dpi=config.figure_dpi)

    for model, tmp in all_main_intervals.groupby("model"):
        tmp = tmp[tmp["sample_flag"].eq("test")].dropna(subset=["date", "covered"]).copy()
        if tmp.empty:
            continue
        tmp["rolling_coverage"] = tmp["covered"].rolling(config.rolling_coverage_window).mean()
        ax.plot(tmp["date"], tmp["rolling_coverage"], label=model, linewidth=1.1)

    ax.axhline(1.0 - config.main_alpha, linestyle="--", linewidth=1.2, label="Nominal coverage")
    ax.set_title(f"{config.rolling_coverage_window}-day Rolling Empirical Coverage")
    ax.set_ylabel("Rolling coverage")
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


# =========================================================
# 5. Main experiment wrapper
# =========================================================

def run_interval_experiment(config: IntervalConfig) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ensure_dir(config.output_dir)
    df, model_cols = load_prediction_panel(config)

    # Save a clean copy of the input used by this interval experiment.
    df.to_csv(os.path.join(config.output_dir, "input_prediction_panel_used.csv"), index=False, encoding="utf-8-sig")

    interval_frames: List[pd.DataFrame] = []
    summary_rows: List[Dict[str, float]] = []
    coverage_test_rows: List[Dict[str, float]] = []

    for alpha in config.alpha_list:
        for window in config.calibration_windows:
            for model_name, pred_col in model_cols.items():
                print(f"[Interval] model={model_name}, alpha={alpha}, m={window}")
                interval_df = rolling_conformal_intervals_for_model(
                    df=df,
                    model_name=model_name,
                    pred_col=pred_col,
                    alpha=alpha,
                    window=window,
                    config=config,
                )

                interval_frames.append(interval_df)
                summary_rows.append(summarize_interval_result(interval_df, config))

                eval_tmp = interval_df[interval_df["sample_flag"].eq("test")].dropna(subset=["covered"])
                cov_test = christoffersen_tests(eval_tmp["covered"].to_numpy(), alpha=alpha)
                cov_test.update({
                    "model": model_name,
                    "alpha": alpha,
                    "nominal_coverage": 1.0 - alpha,
                    "calibration_window": window,
                })
                coverage_test_rows.append(cov_test)

                # Save individual interval file.
                alpha_tag = f"a{int(round(alpha * 100)):02d}"
                filename = f"interval_{model_name}_{alpha_tag}_m{window}.csv"
                interval_df.to_csv(os.path.join(config.output_dir, filename), index=False, encoding="utf-8-sig")

    all_intervals = pd.concat(interval_frames, ignore_index=True)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["alpha", "calibration_window", "avg_interval_score"], na_position="last"
    ).reset_index(drop=True)
    coverage_tests = pd.DataFrame(coverage_test_rows).sort_values(
        ["alpha", "calibration_window", "model"]
    ).reset_index(drop=True)

    all_intervals.to_csv(os.path.join(config.output_dir, "interval_all_models_all_settings.csv"), index=False, encoding="utf-8-sig")
    summary.to_csv(os.path.join(config.output_dir, "interval_summary_all.csv"), index=False, encoding="utf-8-sig")
    coverage_tests.to_csv(os.path.join(config.output_dir, "christoffersen_coverage_tests.csv"), index=False, encoding="utf-8-sig")

    # Main-setting combined file for tables and figures.
    main_intervals = all_intervals[
        (all_intervals["alpha"] == config.main_alpha) &
        (all_intervals["calibration_window"] == config.main_window)
    ].copy()
    main_intervals.to_csv(os.path.join(config.output_dir, "interval_main_setting_all_models.csv"), index=False, encoding="utf-8-sig")

    # Figures.
    plot_main_interval_scores(summary, os.path.join(config.output_dir, "fig_interval_score_main.png"), config)
    plot_coverage_width_tradeoff(summary, os.path.join(config.output_dir, "fig_coverage_width_tradeoff_main.png"), config)
    plot_rolling_coverage(main_intervals, os.path.join(config.output_dir, "fig_rolling_coverage_main.png"), config)

    # Show interval series for the core model; this is usually the best figure for the thesis text.
    core = main_intervals[main_intervals["model"].eq("XGB_MIDAS_EPU_DEC")].copy()
    plot_interval_series(
        core,
        os.path.join(config.output_dir, "fig_interval_series_XGB_MIDAS_EPU_DEC.png"),
        config,
        model_name="XGB_MIDAS_EPU_DEC",
    )

    print("\n[Done] Interval experiment outputs saved to:")
    print(os.path.abspath(config.output_dir))
    print("\n[Main summary: alpha=%.2f, m=%d]" % (config.main_alpha, config.main_window))
    print(summary[(summary["alpha"] == config.main_alpha) & (summary["calibration_window"] == config.main_window)])

    return all_intervals, summary, coverage_tests


# =========================================================
# 6. Example call
# =========================================================

if __name__ == "__main__":
    cfg = IntervalConfig(
        input_predictions_path=str(PROJECT_ROOT / "generated" / "csi300_epu_final_outputs" / "all_model_predictions.csv"),
        output_dir=str(PROJECT_ROOT / "generated" / "csi300_epu_interval_outputs"),
        eps=1e-8,
        alpha_list=(0.10, 0.05),
        calibration_windows=(120, 250, 500),
        main_alpha=0.10,
        main_window=250,
    )
    run_interval_experiment(cfg)
