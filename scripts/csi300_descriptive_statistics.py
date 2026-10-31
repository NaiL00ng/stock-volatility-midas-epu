
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from scipy.stats import jarque_bera, norm
from statsmodels.graphics.gofplots import qqplot
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch


def configure_style():
    """统一图形风格，适合论文插图。"""
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update({
        "figure.dpi": 160,
        "savefig.dpi": 400,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.unicode_minus": False,
        "font.sans-serif": [
            "Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
            "Arial Unicode MS", "DejaVu Sans"
        ],
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "legend.fontsize": 10,
    })


def load_and_prepare_data(file_path: str, sheet_name: str = "data") -> tuple[pd.DataFrame, pd.Series]:
    """
    读取 CSI 300 日线数据，并构造日对数收益率。
    要求表中至少包含 date 和 close 两列。
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name)

    required_cols = {"date", "close"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise KeyError(f"缺少必要列: {missing_cols}")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date")
    df = df.drop_duplicates(subset=["date"]).reset_index(drop=True)

    # 构造日对数收益率
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))
    df["sq_return"] = df["log_return"] ** 2

    # 删除第一行缺失收益率
    df = df.dropna(subset=["log_return"]).reset_index(drop=True)

    return df, df["log_return"]


def descriptive_statistics(ret: pd.Series) -> pd.DataFrame:
    """计算日对数收益率的基本统计量。"""
    result = pd.DataFrame({
        "Statistic": [
            "Observations", "Mean", "Std. Dev.", "Min", "25%",
            "Median", "75%", "Max", "Skewness", "Excess Kurtosis"
        ],
        "Value": [
            int(ret.count()),
            ret.mean(),
            ret.std(ddof=1),
            ret.min(),
            ret.quantile(0.25),
            ret.median(),
            ret.quantile(0.75),
            ret.max(),
            ret.skew(),
            ret.kurt(),  # 超额峰度
        ],
    })
    return result


def diagnostic_tests(ret: pd.Series, lags_lb=(10, 20), lag_arch=10):
    """计算 Jarque–Bera、Ljung–Box 和 ARCH-LM 检验。"""
    sq_ret = ret ** 2

    jb_stat, jb_p = jarque_bera(ret)
    jb_df = pd.DataFrame({
        "Test": ["Jarque-Bera"],
        "Statistic": [jb_stat],
        "p-value": [jb_p],
    })

    lb_ret = acorr_ljungbox(ret, lags=list(lags_lb), return_df=True).reset_index()
    lb_ret = lb_ret.rename(columns={"index": "Lag", "lb_stat": "Statistic", "lb_pvalue": "p-value"})
    lb_ret["Series"] = "Log return"

    lb_sq = acorr_ljungbox(sq_ret, lags=list(lags_lb), return_df=True).reset_index()
    lb_sq = lb_sq.rename(columns={"index": "Lag", "lb_stat": "Statistic", "lb_pvalue": "p-value"})
    lb_sq["Series"] = "Squared return"

    lb_df = pd.concat([lb_ret, lb_sq], ignore_index=True)[["Series", "Lag", "Statistic", "p-value"]]

    arch_lm_stat, arch_lm_p, arch_f_stat, arch_f_p = het_arch(ret, nlags=lag_arch)
    arch_df = pd.DataFrame({
        "Test": [f"ARCH-LM (lag={lag_arch})", f"ARCH-F (lag={lag_arch})"],
        "Statistic": [arch_lm_stat, arch_f_stat],
        "p-value": [arch_lm_p, arch_f_p],
    })

    return jb_df, lb_df, arch_df


def plot_return_series(df: pd.DataFrame, output_dir: Path):
    """绘制日对数收益率时序图。"""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sns.lineplot(
        data=df, x="date", y="log_return",
        linewidth=0.7, ax=ax, color="#4C72B0"
    )
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_title("CSI 300 Daily Log Returns")
    ax.set_xlabel("")
    ax.set_ylabel("Log return")

    fig.tight_layout()
    fig.savefig(output_dir / "figure_1_log_return_series.png", bbox_inches="tight")
    plt.close(fig)


def plot_hist_qq(ret: pd.Series, output_dir: Path):
    """绘制直方图和 QQ 图。"""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))

    sns.histplot(
        x=ret, bins=60, stat="density", kde=True,
        ax=axes[0], alpha=0.70, edgecolor="white", color="#4C72B0"
    )
    x = np.linspace(ret.min(), ret.max(), 500)
    axes[0].plot(
        x,
        norm.pdf(x, loc=ret.mean(), scale=ret.std(ddof=1)),
        linestyle="--", linewidth=1.3, color="#C44E52",
        label="Normal density"
    )
    axes[0].set_title("Histogram of Daily Log Returns")
    axes[0].set_xlabel("Log return")
    axes[0].set_ylabel("Density")
    axes[0].legend(frameon=False)

    qqplot(
        ret, line="45", fit=True, ax=axes[1],
        markerfacecolor="#4C72B0", markeredgecolor="white", alpha=0.75
    )
    axes[1].set_title("Q-Q Plot")
    axes[1].grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(output_dir / "figure_2_histogram_qq.png", bbox_inches="tight")
    plt.close(fig)


def save_results_to_excel(
    desc_df: pd.DataFrame,
    jb_df: pd.DataFrame,
    lb_df: pd.DataFrame,
    arch_df: pd.DataFrame,
    output_dir: Path
):
    """保存检验结果。"""
    with pd.ExcelWriter(output_dir / "csi300_descriptive_results.xlsx", engine="openpyxl") as writer:
        desc_df.to_excel(writer, sheet_name="Descriptive Stats", index=False)
        jb_df.to_excel(writer, sheet_name="Jarque-Bera", index=False)
        lb_df.to_excel(writer, sheet_name="Ljung-Box", index=False)
        arch_df.to_excel(writer, sheet_name="ARCH-LM", index=False)


def main():
    # Numerical warnings remain visible.

    # ====== 1. 输入与输出路径：按需修改 ======
    file_path = str(PROJECT_ROOT / "data" / "CSI300_daily_20100104_20260331.xlsx")
    output_dir = PROJECT_ROOT / "generated" / "descriptive"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ====== 2. 统一图形风格 ======
    configure_style()

    # ====== 3. 读入数据并构造收益率 ======
    df, ret = load_and_prepare_data(file_path=file_path, sheet_name="data")

    # ====== 4. 描述性统计与检验 ======
    desc_df = descriptive_statistics(ret)
    jb_df, lb_df, arch_df = diagnostic_tests(ret, lags_lb=(10, 20), lag_arch=10)

    # ====== 5. 输出结果 ======
    print("\n" + "=" * 80)
    print("Descriptive Statistics of Daily Log Returns")
    print("=" * 80)
    print(desc_df.to_string(index=False))

    print("\n" + "=" * 80)
    print("Jarque-Bera Test")
    print("=" * 80)
    print(jb_df.to_string(index=False))

    print("\n" + "=" * 80)
    print("Ljung-Box Tests")
    print("=" * 80)
    print(lb_df.to_string(index=False))

    print("\n" + "=" * 80)
    print("ARCH-LM Test")
    print("=" * 80)
    print(arch_df.to_string(index=False))

    # ====== 6. 保存表格结果 ======
    desc_df.to_csv(output_dir / "descriptive_statistics.csv", index=False, encoding="utf-8-sig")
    jb_df.to_csv(output_dir / "jarque_bera_test.csv", index=False, encoding="utf-8-sig")
    lb_df.to_csv(output_dir / "ljung_box_tests.csv", index=False, encoding="utf-8-sig")
    arch_df.to_csv(output_dir / "arch_lm_test.csv", index=False, encoding="utf-8-sig")
    save_results_to_excel(desc_df, jb_df, lb_df, arch_df, output_dir)

    # ====== 7. 绘图 ======
    plot_return_series(df, output_dir)
    plot_hist_qq(ret, output_dir)

    print("\n结果表和图片已保存至：", output_dir.resolve())


if __name__ == "__main__":
    main()
