"""Recompute archived scores and interval construction without training models.

Inputs are local archive files described in docs/reproduction.md.
Outputs are reports only; input files and historical release results are never edited.
"""
from pathlib import Path
import numpy as np, pandas as pd, math, json
import argparse
parser = argparse.ArgumentParser(description='Independently audit archived predictions; raw archive is not distributed.')
parser.add_argument('--archive', type=Path, required=True, help='Local archive with outputs/, res/, data source/, and the original paper image snapshots')
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'generated' / 'verification')
args = parser.parse_args()
b = args.archive
o = args.output
if not b.is_dir():
    parser.error('Archive directory does not exist')
o.mkdir(parents=True, exist_ok=True)
rows = []

def check(group, key, actual, expected, tol=1e-08):
    rows.append(dict(group=group, item=key, recomputed=float(actual), stored=float(expected), abs_error=abs(float(actual) - float(expected)), passed=bool(abs(float(actual) - float(expected)) <= tol * max(1, abs(float(expected))))))
cols = {'HAR': 'yhat_har', 'GARCH': 'yhat_garch', 'XGB_Market': 'yhat_xgb_market', 'XGB_MIDAS_EPU_DEC': 'yhat_xgb_midas_dec'}
for market in ['csi300', 'SSE50', 'NASDAQZH']:
    root = b / 'outputs' / f'{market}_epu_final_outputs'
    p = pd.read_csv(root / 'all_model_predictions.csv')
    test = p[p.sample_flag == 'test']
    y = test.y.to_numpy()
    metrics = pd.read_csv(root / 'metrics_summary.csv').set_index('model')
    loss = {}
    for (m, c) in cols.items():
        yh = test[c].to_numpy()
        e = y - yh
        ratio = np.maximum(np.exp(y) - 1e-08, 1e-12) / np.maximum(np.exp(yh) - 1e-08, 1e-12)
        q = ratio - np.log(ratio) - 1
        loss[m] = q
        for (k, v) in {'MSE': np.mean(e * e), 'MAE': np.mean(abs(e)), 'Bias': np.mean(e), 'QLIKE': np.mean(q), 'n_test': len(y)}.items():
            check(market, m + '/' + k, v, metrics.loc[m, k])
    tests = pd.read_csv(b / '论文主体/GD2025TempLatex20250922/images' / f'{market}_epu_final_outputs' / 'hypothesis_tests.csv')
    for (i, r) in tests.iterrows():
        if r['test'] == 'DM-HAC':
            d = loss[r.model_A] - loss[r.model_B]
            n = len(d)
            lag = int(r.hac_lag)
            z = d - d.mean()
            s = z @ z / n
            for k in range(1, lag + 1):
                s += 2 * (1 - k / (lag + 1)) * np.dot(z[k:], z[:-k]) / n
            t = d.mean() / math.sqrt(s / n)
            pv = math.erfc(abs(t) / math.sqrt(2))
            check(market, 'DM' + str(i), t, r.DM_t)
            check(market, 'DMp' + str(i), pv, r.DM_p_two_sided)
        else:
            a = test[cols[r.model_A]].to_numpy()
            bb = test[cols[r.model_B]].to_numpy()
            d = (y - a) ** 2 - (y - bb) ** 2 + (a - bb) ** 2
            t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
            check(market, 'CW-statistic', t, r.CW_t)
    spec = pd.read_csv(root / 'midas_dec_best_spec.csv').iloc[0]
    w = pd.read_csv(root / 'midas_dec_weights.csv')
    K = int(spec.K)
    a = spec.theta1
    bb = spec.theta2
    if spec.weight_type == 'expalmon':
        x = np.arange(K, 0, -1) / K
        v = a * x + bb * x * x
        ww = np.exp(v - v.max())
    else:
        x = np.arange(K, 0, -1) / (K + 1)
        ww = np.maximum(x ** (a - 1) * (1 - x) ** (bb - 1), 1e-12)
    ww /= ww.sum()
    check(market, 'weights-max-error', np.max(abs(ww - w.weight.to_numpy())), 0)
root = b / 'res/csi300_epu_interval_outputs'
summary = pd.read_csv(root / 'interval_summary_all.csv')
tests = pd.read_csv(root / 'christoffersen_coverage_tests.csv')
frames = {}

def loglike(x, n, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return x * np.log(p) + (n - x) * np.log(1 - p)
for (_, r) in summary.iterrows():
    f = root / f'interval_{r.model}_a{round(r.alpha * 100):02d}_m{int(r.calibration_window)}.csv'
    d = pd.read_csv(f)
    d = d[(d.sample_flag == 'test') & d.lower_y.notna()]
    frames[r.model, r.alpha, int(r.calibration_window)] = d
    y = d.y.to_numpy()
    lo = d.lower_y.to_numpy()
    hi = d.upper_y.to_numpy()
    cov = (y >= lo) & (y <= hi)
    width = hi - lo
    score = width + 2 / r.alpha * np.maximum(lo - y, 0) + 2 / r.alpha * np.maximum(y - hi, 0)
    for (key, value) in {'n_eval': len(d), 'empirical_coverage': cov.mean(), 'avg_width_y': width.mean(), 'avg_interval_score': score.mean()}.items():
        check('interval', f'{r.model}/{r.alpha}/{r.calibration_window}/{key}', value, r[key])
    v = 1 - cov.astype(int)
    n = len(v)
    cnt = v.sum()
    a = v[:-1]
    bb = v[1:]
    ns = [int(np.sum((a == i) & (bb == j))) for (i, j) in [(0, 0), (0, 1), (1, 0), (1, 1)]]
    (n00, n01, n10, n11) = ns
    uc = max(0, 2 * (loglike(cnt, n, cnt / n) - loglike(cnt, n, r.alpha)))
    pi = (n01 + n11) / (n - 1)
    ind = max(0, 2 * (loglike(n01, n00 + n01, n01 / (n00 + n01)) + loglike(n11, n10 + n11, n11 / (n10 + n11)) - loglike(n01 + n11, n - 1, pi)))
    tr = tests[(tests.model == r.model) & (tests.alpha == r.alpha) & (tests.calibration_window == r.calibration_window)].iloc[0]
    for (key, val) in {'LR_uc': uc, 'LR_ind': ind, 'LR_cc': uc + ind, 'p_uc': math.erfc(math.sqrt(uc / 2)), 'p_ind': math.erfc(math.sqrt(ind / 2)), 'p_cc': math.exp(-(uc + ind) / 2)}.items():
        check('coverage', f'{r.model}/{r.alpha}/{r.calibration_window}/{key}', val, tr[key])
common = set.intersection(*(set(frames[m, 0.1, 250].date) for m in cols))
cr = []
for m in cols:
    d = frames[m, 0.1, 250]
    d = d[d.date.isin(common)]
    y = d.y.to_numpy()
    lo = d.lower_y.to_numpy()
    hi = d.upper_y.to_numpy()
    width = hi - lo
    cr.append(dict(model=m, n=len(d), start=d.date.min(), end=d.date.max(), coverage=np.mean((y >= lo) & (y <= hi)), width=width.mean(), interval_score=np.mean(width + 20 * np.maximum(lo - y, 0) + 20 * np.maximum(y - hi, 0))))
pd.DataFrame(cr).to_csv(o / 'interval_common_dates.csv', index=False)
df = pd.read_excel(b / 'data source/CSI300_daily_20100104_20260331.xlsx', sheet_name='data')
df = df.sort_values('date').drop_duplicates('date')
r = np.log(df.close / df.close.shift(1)).dropna()
desc = {'Observations': len(r), 'Mean': r.mean(), 'Std. Dev.': r.std(ddof=1), 'Min': r.min(), 'Max': r.max(), 'Skewness': r.skew(), 'Excess Kurtosis': r.kurt()}
old = pd.read_csv(b / 'outputs/descriptive_statistics.csv').set_index('Statistic')
for (key, val) in desc.items():
    check('raw_descriptive', key, val, old.loc[key, 'Value'])
pd.DataFrame(rows).to_csv(o / 'calculation_checks.csv', index=False)
panel = pd.read_csv(b / 'outputs/csi300_epu_final_outputs/all_model_predictions.csv').sort_values('date').reset_index(drop=True)
construction = []
for (model, col) in cols.items():
    yy = panel.y.to_numpy()
    pp = panel[col].to_numpy()
    flags = panel.sample_flag.to_numpy()
    for alpha in [0.1, 0.05]:
        for window in [120, 250, 500]:
            lows = np.full(len(panel), np.nan)
            highs = np.full(len(panel), np.nan)
            past = []
            for i in range(len(panel)):
                if flags[i] == 'test' and np.isfinite(pp[i]) and (len(past) >= 60):
                    scores = np.asarray(past[-window:])
                    rank = min(len(scores), math.ceil((len(scores) + 1) * (1 - alpha)))
                    q = np.partition(scores, rank - 1)[rank - 1]
                    (lows[i], highs[i]) = (pp[i] - q, pp[i] + q)
                if flags[i] in ['valid', 'test'] and np.isfinite(yy[i] - pp[i]):
                    past.append(abs(yy[i] - pp[i]))
            saved = pd.read_csv(b / 'res/csi300_epu_interval_outputs' / f'interval_{model}_a{round(alpha * 100):02d}_m{window}.csv')
            same_dates = saved.date.tolist() == panel.date.tolist()
            low_ok = same_dates and np.allclose(lows, saved.lower_y, atol=1e-10, rtol=1e-10, equal_nan=True)
            high_ok = same_dates and np.allclose(highs, saved.upper_y, atol=1e-10, rtol=1e-10, equal_nan=True)
            construction.append(dict(model=model, alpha=alpha, calibration_window=window, n_intervals=int(np.isfinite(lows).sum()), dates_match=same_dates, lower_match=low_ok, upper_match=high_ok))
pd.DataFrame(construction).to_csv(o / 'interval_construction_checks.csv', index=False)
print(f"Interval constructions matched: {sum((r['lower_match'] and r['upper_match'] for r in construction))}/{len(construction)}")
print(f"Checks: {len(rows)}; mismatches: {sum((not r['passed'] for r in rows))}")
print('Reports written to the requested output directory. A mismatch is retained as evidence, not silently fixed.')
