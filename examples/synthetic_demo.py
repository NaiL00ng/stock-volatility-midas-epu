"""Run the current DEC solver on generated data; no empirical claims or private inputs.

Run from the repository root: python examples/synthetic_demo.py
Outputs stay in a new directory under generated/. No downloads or workbook reads.
"""
from pathlib import Path
import argparse
import importlib.metadata
import json
import os
import platform
import struct
import sys
import sysconfig


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=root/'generated/synthetic-demo')
    parser.add_argument('--seed', type=int, default=2026)
    args = parser.parse_args()
    output = args.output.resolve()
    generated = root/'generated'
    if generated.is_symlink() or not output.is_relative_to(generated) or output == generated:
        parser.error('Output must be a child directory inside this package generated/.')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error('Choose a new empty output directory; previous runs are preserved.')
    if args.seed < 0 or args.seed > 2**32 - 1:
        parser.error('Seed must be between 0 and 2**32 - 1.')
    output.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(output/'matplotlib-cache')
    os.environ['MPLBACKEND'] = 'Agg'
    # The demo uses an ordinary installed XGBoost; never enables the forensic patch.
    os.environ.pop('FORENSIC_MSVC_SHUFFLE', None)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root/'scripts'))
    try:
        import numpy as np
        import pandas as pd
        import csi300_epu_final_from_oldcode as ex
        from dec_stable import estimate_stable, residual_only_predictions
    except ImportError as error:
        parser.exit(1, f'Missing demo dependency: {error.name}. Install requirements-demo.txt.\n')

    print('SYNTHETIC DEMO ONLY - not paper results, no private data.', flush=True)
    rng = np.random.default_rng(args.seed)
    dates = pd.bdate_range('2021-01-04', periods=640)
    months = pd.date_range('2018-01-01', '2023-12-01', freq='MS')
    monthly_log = np.empty(len(months))
    monthly_log[0] = 4.5
    for i in range(1, len(months)):
        monthly_log[i] = 4.5 + .65*(monthly_log[i-1]-4.5) + rng.normal(0, .25)
    monthly = pd.DataFrame({'observation_date': months, 'CHNMAINLANDEPU': np.exp(monthly_log)})
    # A deliberately artificial variance process, not fitted to any market.
    lagged_signal = pd.Series(monthly_log, index=months.to_period('M')).reindex(dates.to_period('M')-1).to_numpy()
    sigma = .01 * np.exp(.35*(lagged_signal-4.5))
    returns = sigma * rng.normal(size=len(dates))
    close = 100 * np.exp(np.cumsum(returns))
    opening = np.r_[100., close[:-1]]
    spread = rng.uniform(.001, .01, len(dates))
    prices = pd.DataFrame({'date': dates, 'open': opening,
                           'high': np.maximum(opening, close)*np.exp(spread),
                           'low': np.minimum(opening, close)*np.exp(-spread),
                           'close': close, 'volume': np.exp(rng.normal(12, .2, len(dates)))})
    cfg = ex.ExperimentConfig(n_train=200, n_valid=200, verbose=False,
                              output_dir=str(output), random_state=args.seed)
    params = {**ex.XGB_PARAMS, 'n_estimators': 40, 'max_depth': 2,
              'subsample': 1., 'colsample_bytree': 1., 'n_jobs': 1,
              'tree_method': 'hist', 'random_state': args.seed}
    data = ex.add_sample_flags(ex.prepare_main_dataframe(prices, monthly, cfg), cfg)
    if len(data) != 617 or not data.date.is_unique or not data.date.is_monotonic_increasing:
        raise RuntimeError('Synthetic preparation changed; review the documented sample counts.')
    data['yhat_xgb_market'] = ex.expanding_xgb_market(data, ex.BASE_FEATURES, cfg, params)
    legacy_solver = ex.estimate_midas_profiled_ols
    ex.estimate_midas_profiled_ols = estimate_stable
    try:
        data['yhat_dec'], info = ex.run_xgb_midas_epu_dec(data, 'yhat_xgb_market', cfg)
    finally:
        ex.estimate_midas_profiled_ols = legacy_solver
    if len(info['search_results']) != 6 or any(not d.get('gradient_tolerance_met', False)
                                               for d in info['optimization_diagnostics']):
        raise RuntimeError('Incomplete specification search or failed stationarity check.')
    data['yhat_ar'] = residual_only_predictions(data, cfg)
    models = {'XGB_Market': 'yhat_xgb_market', 'XGB_Residual_AR': 'yhat_ar',
              'XGB_MIDAS_EPU_DEC': 'yhat_dec'}
    test = data.loc[data.sample_flag.eq('test')].copy()
    if len(test) != 217 or not np.isfinite(test[['y', *models.values()]].to_numpy()).all():
        raise RuntimeError('Expected 217 complete test rows for every model.')
    metrics = []
    for name, column in models.items():
        metrics.append({'data_kind': 'synthetic_demo', 'model': name,
                        **ex.point_metrics(test.y.to_numpy(), test[column].to_numpy(), cfg.eps)})
    metrics = pd.DataFrame(metrics)
    # Dates identify forecast origins; targets refer to the following synthetic business day.
    target_dates = pd.Series(dates[1:], index=dates[:-1])
    panel = test[['date', 'y', *models.values()]].copy()
    panel.insert(0, 'data_kind', 'synthetic_demo')
    panel.insert(2, 'target_date', test.date.map(target_dates))
    panel.to_csv(output/'synthetic_predictions.csv', index=False)
    metrics.to_csv(output/'synthetic_metrics.csv', index=False)
    info['search_results'].to_csv(output/'synthetic_spec_search.csv', index=False)
    metadata = {
        'data_kind': 'synthetic_demo', 'is_empirical_evidence': False,
        'seed': args.seed, 'raw_price_rows': 640, 'prepared_rows': len(data),
        'split': {'train': 200, 'valid': 200, 'test': 217},
        'stage2_selection': {'usable_validation_residuals': 199, 'train': 119, 'score': 80},
        'calendar': 'Synthetic weekdays; no exchange holiday calendar or real EPU release schedule',
        'target': 'log(next synthetic business-day squared log return + 1e-8)',
        'first_test_origin': str(test.date.iloc[0].date()),
        'last_test_origin': str(test.date.iloc[-1].date()),
        'xgboost_params': params, 'best_spec': info['best_spec'],
        'solver': 'scripts/dec_stable.py:estimate_stable',
        'optimization_diagnostics': info['optimization_diagnostics'],
        'runtime': {'python': sys.version.split()[0], 'system': platform.system(),
                    'machine': platform.machine(), 'python_platform': sysconfig.get_platform(),
                    'pointer_bits': struct.calcsize('P') * 8, **{name: importlib.metadata.version(name)
                     for name in ['numpy', 'pandas', 'scipy', 'statsmodels', 'xgboost', 'scikit-learn', 'matplotlib']}},
    }
    (output/'synthetic_run.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'README.md').write_text(
        '# Synthetic demo output\n\nGenerated artificial inputs only. These scores do not reproduce '
        'or validate the paper. Do not merge them into results/revised/.\n', encoding='utf-8')
    print(metrics.to_string(index=False), flush=True)
    print('PASS: 640 synthetic price rows -> 617 prepared -> 200 / 200 / 217.', flush=True)
    print('Outputs:', output.relative_to(root), flush=True)


if __name__ == '__main__':
    main()
