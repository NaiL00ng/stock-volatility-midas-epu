"""Re-estimate all four SSE50 models before/after removing a confirmed holiday row.

This is a NEW controlled data-cleaning experiment, not the historical thesis run.
It uses the documented local sampling-compatible XGBoost 2.0.3 build. Other source
data problems, real-time EPU vintages and numerical estimation limits remain.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import warnings


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--xgboost-python-path', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=root / 'generated/calendar-sensitivity')
    args = parser.parse_args()
    output, package = args.output.resolve(), args.xgboost_python_path.resolve()
    if not output.is_relative_to(root / 'generated') or not package.is_relative_to(root / 'generated'):
        parser.error('Output and package must be inside this project\'s generated directory.')
    if output.exists() and any(output.iterdir()):
        parser.error('Use a new empty output directory.')
    output.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(root / 'generated/matplotlib')
    os.environ['FORENSIC_MSVC_SHUFFLE'] = '1'
    sys.path.insert(0, str(package))
    import numpy as np
    import pandas as pd
    import xgboost
    import csi300_epu_final_from_oldcode as experiment
    if xgboost.__version__ != '2.0.3':
        raise ValueError('Use the documented diagnostic build.')
    spec = json.loads((root / 'configs/experiments.json').read_text())
    case = spec['markets']['sse50']
    prices = pd.read_excel(args.archive / 'data source' / case['prices'])
    epu = pd.read_excel(args.archive / 'data source' / case['epu'], sheet_name='Monthly')
    exclusion = pd.to_datetime(prices.date).eq(pd.Timestamp('2018-06-18'))
    assert int(exclusion.sum()) == 1, 'Unexpected source version.'
    metrics, panels = [], {}
    for variant in ['historical_input', 'calendar_corrected']:
        data = prices if variant == 'historical_input' else prices.loc[~exclusion].copy()
        config = experiment.ExperimentConfig(**spec['common'], n_train=case['n_train'],
                                             output_dir=str(output / variant), verbose=False)
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always')
            panel, summary, tests, meta = experiment.run_final_experiment(data, epu, config,
                                                                         xgb_params={**spec['xgboost'], 'n_jobs': 4})
        panels[variant] = panel.loc[panel.sample_flag.eq('test')].set_index('date')
        summary.insert(0, 'input_variant', variant)
        metrics.append(summary)
        (output / variant / 'warnings.json').write_text(json.dumps([str(n.message) for n in notices], indent=2) + '\n')
    pd.concat(metrics, ignore_index=True).to_csv(output / 'all_dates_metrics.csv', index=False)
    old, new = panels['historical_input'], panels['calendar_corrected']
    dates = old.index.intersection(new.index)
    columns = {'HAR': 'yhat_har', 'GARCH': 'yhat_garch', 'XGB_Market': 'yhat_xgb_market', 'XGB_MIDAS_EPU_DEC': 'yhat_xgb_midas_dec'}
    rows = []
    for variant, panel in panels.items():
        for model, column in columns.items():
            result = experiment.point_metrics(new.loc[dates, 'y'].to_numpy(), panel.loc[dates, column].to_numpy(), spec['common']['eps'])
            rows.append(dict(input_variant=variant, model=model, evaluation_target='calendar_corrected', **result))
    pd.DataFrame(rows).to_csv(output / 'common_dates_metrics.csv', index=False)
    (output / 'comparison_scope.json').write_text(json.dumps(dict(
        excluded_source_date='2018-06-18', historical_test_n=len(old), corrected_test_n=len(new),
        common_dates=len(dates), changed_targets_on_common_dates=int((abs(new.loc[dates,'y']-old.loc[dates,'y'])>1e-12).sum()),
        status='New data-cleaning sensitivity experiment; common-date scores use the corrected target for both prediction sets.'), indent=2) + '\n')
    print('Calendar sensitivity complete. Historical archive files remain unchanged.')


if __name__ == '__main__':
    main()
