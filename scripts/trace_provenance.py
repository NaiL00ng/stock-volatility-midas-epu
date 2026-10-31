"""Trace archived inputs and the extra-zero descriptive-statistics fingerprint.

Read-only with respect to --archive. Outputs are aggregate evidence and corrected
summary figures; no raw records are copied. This does not reconstruct missing
historical XGBoost binaries or assert that a synthetic zero was a real observation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
import csi300_descriptive_statistics as descriptive
import csi300_epu_final_from_oldcode as experiment


def stats_vector(series):
    desc = descriptive.descriptive_statistics(pd.Series(series))
    jb, lb, arch = descriptive.diagnostic_tests(pd.Series(series))
    result = {"descriptive/" + row.Statistic: row.Value for row in desc.itertuples()}
    for name, frame in [("JB", jb), ("ARCH", arch)]:
        for _, row in frame.iterrows():
            result[name + "/" + row["Test"] + "/statistic"] = row["Statistic"]
            result[name + "/" + row["Test"] + "/p"] = row["p-value"]
    for _, row in lb.iterrows():
        key = "LB/" + row.Series + "/" + str(int(row.Lag))
        result[key + "/statistic"] = row["Statistic"]
        result[key + "/p"] = row["p-value"]
    return result


def historical_vector(archive):
    folder = archive / "outputs"
    result = {"descriptive/" + row.Statistic: row.Value for row in pd.read_csv(folder / "descriptive_statistics.csv").itertuples()}
    for name, file in [("JB", "jarque_bera_test.csv"), ("ARCH", "arch_lm_test.csv")]:
        for _, row in pd.read_csv(folder / file).iterrows():
            result[name + "/" + row["Test"] + "/statistic"] = row["Statistic"]
            result[name + "/" + row["Test"] + "/p"] = row["p-value"]
    for _, row in pd.read_csv(folder / "ljung_box_tests.csv").iterrows():
        key = "LB/" + row.Series + "/" + str(int(row.Lag))
        result[key + "/statistic"] = row["Statistic"]
        result[key + "/p"] = row["p-value"]
    return result


def lb_fingerprint(x):
    n = len(x)
    centered = x - x.mean()
    denominator = centered @ centered
    rho = np.array([centered[k:] @ centered[:-k] / denominator for k in range(1, 21)])
    terms = rho ** 2 / (n - np.arange(1, 21))
    return n * (n + 2) * np.array([terms[:10].sum(), terms.sum()])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "generated/provenance")
    args = parser.parse_args()
    archive, output = args.archive.resolve(), args.output.resolve()
    if not output.is_relative_to(Path(__file__).resolve().parents[1] / "generated"):
        parser.error("Output must be inside this project's generated directory.")
    output.mkdir(parents=True, exist_ok=True)
    rawfile = archive / "data source/CSI300_daily_20100104_20260331.xlsx"
    prepared, returns = descriptive.load_and_prepare_data(rawfile, sheet_name="data")
    target = pd.read_csv(archive / "outputs/ljung_box_tests.csv")["Statistic"].to_numpy()
    candidates = []
    x = returns.to_numpy()
    for k in range(len(x) + 1):
        z = np.insert(x, k, 0.0)
        values = np.r_[lb_fingerprint(z), lb_fingerprint(z * z)]
        candidates.append((k, float(np.max(np.abs(values - target)))))
    candidates.sort(key=lambda value: value[1])
    position, error = candidates[0]
    synthetic = np.insert(x, position, 0.0)
    old, current, reconstructed = historical_vector(archive), stats_vector(x), stats_vector(synthetic)
    rows = []
    for key in old:
        # For tiny p-values use relative accuracy, not a large absolute tolerance.
        tolerance = 1e-8 * abs(old[key]) if key.endswith('/p') and old[key] else 1e-9 * max(1, abs(old[key]))
        rows.append(dict(item=key, archived=old[key], corrected=current[key], extra_zero_reconstruction=reconstructed[key], reconstruction_matches=abs(old[key] - reconstructed[key]) <= tolerance))
    pd.DataFrame(rows).to_csv(output / "descriptive_lineage.csv", index=False)
    pd.DataFrame(candidates[:5], columns=["insertion_position", "max_lb_stat_error"]).to_csv(output / "zero_insertion_candidates.csv", index=False)
    fingerprint = dict(position_before_return_index=int(position), preceding_return_date=str(prepared.date.iloc[position - 1].date()), following_return_date=str(prepared.date.iloc[position].date()), max_lb_error=error, current_return_count=len(x), synthetic_count=len(synthetic), synthetic_is_evidence_only=True)
    (output / "zero_fingerprint.json").write_text(json.dumps(fingerprint, indent=2) + "\n")
    corrected_dir = output / "descriptive-corrected"
    corrected_dir.mkdir(exist_ok=True)
    frames = [descriptive.descriptive_statistics(returns), *descriptive.diagnostic_tests(returns)]
    for name, frame in zip(["descriptive_statistics.csv", "jarque_bera_test.csv", "ljung_box_tests.csv", "arch_lm_test.csv"], frames):
        frame.to_csv(corrected_dir / name, index=False)
    descriptive.configure_style()
    descriptive.plot_return_series(prepared, corrected_dir)
    descriptive.plot_hist_qq(returns, corrected_dir)
    reconciliation, splits, fingerprints = [], [], []
    for market, price, epu, train in [
        ("csi300", "CSI300_daily_20100104_20260331.xlsx", "epu_newVersion_2000-2026.xlsx", 1500),
        ("sse50", "SSE50_daily_20100104_20260331.xlsx", "epu_newVersion_2000-2026.xlsx", 1500),
        ("nasdaq", "NASDAQZH_daily_20100101_20260331.xlsx", "US_Policy_Uncertainty_Data.xlsx", 2000),
    ]:
        old_market = {"csi300": "csi300", "sse50": "SSE50", "nasdaq": "NASDAQZH"}[market]
        raw = pd.read_excel(archive / "data source" / price)
        monthly = pd.read_excel(archive / "data source" / epu, sheet_name="Monthly")
        config = experiment.ExperimentConfig(n_train=train, verbose=False)
        data = experiment.add_sample_flags(experiment.prepare_main_dataframe(raw, monthly, config), config)
        original_path = archive / "outputs" / (old_market + "_epu_final_outputs") / "prepared_master_data.csv"
        original = pd.read_csv(original_path)
        original.date = pd.to_datetime(original.date)
        dates_match = data.date.tolist() == original.date.tolist()
        columns = [c for c in data if c not in ["date", "sample_flag"]]
        matched = dates_match and np.allclose(data[columns], original[columns], atol=1e-10, rtol=1e-10)
        error = float(np.max(np.abs(data[columns].to_numpy() - original[columns].to_numpy()))) if dates_match else np.nan
        reconciliation.append(dict(market=market,price_file=price,epu_file=epu,raw_rows=len(raw),prepared_rows=len(data),archived_rows=len(original),dates_match=dates_match,numeric_columns=len(columns),all_numeric_match=matched,max_abs_error=error,flags_match=dates_match and data.sample_flag.equals(original.sample_flag)))
        for flag, group in data.groupby("sample_flag"):
            splits.append(dict(market=market,sample=flag,n=len(group),start=str(group.date.min().date()),end=str(group.date.max().date())))
        for path, role in [(archive / "data source" / price,"prices"),(archive / "data source" / epu,"monthly_epu"),(original_path,"archived_prepared")]:
            fingerprints.append(dict(market=market,role=role,file_name=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    pd.DataFrame(reconciliation).to_csv(output / "input_reconciliation.csv", index=False)
    pd.DataFrame(splits).to_csv(output / "sample_splits.csv", index=False)
    pd.DataFrame(fingerprints).to_csv(output / "input_fingerprints.csv", index=False)
    print(f"Extra-zero fingerprint: {sum(r['reconstruction_matches'] for r in rows)}/{len(rows)} matched; input matrices: {sum(r['all_numeric_match'] for r in reconciliation)}/3 matched.")


if __name__ == "__main__":
    main()
