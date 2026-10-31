"""Reconstruct XGB and DEC from raw inputs and compare every archived forecast.

Use the documented local XGBoost 2.0.3 diagnostic build. Native sampling is also
available as a control. Outputs, model files and dependency paths stay local.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import warnings


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--xgboost-python-path', type=Path, required=True)
    parser.add_argument('--sampling', choices=['msvc', 'native'], default='msvc')
    parser.add_argument('--market', choices=['all', 'csi300', 'sse50', 'nasdaq'], default='all')
    parser.add_argument('--output', type=Path, default=root / 'generated/historical-reproduction')
    parser.add_argument('--save-models', action='store_true', help='Save every refitted booster locally as UBJ')
    args = parser.parse_args()
    output = args.output.resolve()
    package = args.xgboost_python_path.resolve()
    if not output.is_relative_to(root / 'generated') or not package.is_relative_to(root / 'generated'):
        parser.error('Output and diagnostic package must be inside this project\'s generated directory.')
    if output.exists() and any(output.iterdir()):
        parser.error('Use a new empty output directory to preserve earlier run evidence.')
    os.environ['MPLCONFIGDIR'] = str(root / 'generated/matplotlib')
    if args.sampling == 'msvc':
        os.environ['FORENSIC_MSVC_SHUFFLE'] = '1'
    else:
        os.environ.pop('FORENSIC_MSVC_SHUFFLE', None)
    sys.path.insert(0, str(package))
    import numpy as np
    import pandas as pd
    import xgboost
    import csi300_epu_final_from_oldcode as experiment
    if xgboost.__version__ != '2.0.3':
        raise ValueError('This diagnostic procedure was verified with XGBoost 2.0.3.')
    output.mkdir(parents=True, exist_ok=True)
    binary = Path(xgboost.core._LIB._name)
    runtime = {name: importlib.metadata.version(name) for name in ['numpy', 'pandas', 'scipy', 'statsmodels', 'scikit-learn']}
    runtime.update(python=platform.python_version(), system=platform.system(), architecture=platform.machine(),
                   xgboost=xgboost.__version__, sampling=args.sampling,
                   binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                   build_info={k: v for k, v in xgboost.build_info().items() if k != 'libxgboost'})
    (output / 'runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
    spec = json.loads((root / 'configs/experiments.json').read_text())
    rows = []
    selected = spec['markets'] if args.market == 'all' else [args.market]
    for market in selected:
        case = spec['markets'][market]
        folder = output / market
        folder.mkdir()
        config = experiment.ExperimentConfig(**spec['common'], n_train=case['n_train'], verbose=False)
        prices = pd.read_excel(args.archive / 'data source' / case['prices'])
        epu = pd.read_excel(args.archive / 'data source' / case['epu'], sheet_name='Monthly')
        data = experiment.add_sample_flags(experiment.prepare_main_dataframe(prices, epu, config), config)
        original = pd.read_csv(args.archive / 'outputs' / (case['archive_prefix'] + '_epu_final_outputs') / 'all_model_predictions.csv')
        if data.date.dt.strftime('%Y-%m-%d').tolist() != original.date.tolist():
            raise ValueError('Dates differ; do not compare rows by position.')
        records = []

        class RecordedXGB(xgboost.XGBRegressor):
            def fit(self, X, y, **kwargs):
                result = super().fit(X, y, **kwargs)
                number = len(records)
                records.append(dict(refit=number, n_train=len(X), features=list(X.columns),
                                    training_float32_sha256=hashlib.sha256(np.ascontiguousarray(X, dtype='<f4').tobytes() + np.asarray(y, dtype='<f4').tobytes()).hexdigest(),
                                    booster_config=json.loads(self.get_booster().save_config())))
                if args.save_models:
                    self.get_booster().save_model(folder / f'xgb-{number:03d}.ubj')
                return result

        experiment.XGBRegressor = RecordedXGB
        params = spec['xgboost'].copy()
        params['n_jobs'] = 4  # Thread probe established unchanged predictions for 1/2/4/8/default.
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always')
            data['yhat_xgb_market'] = experiment.expanding_xgb_market(data, experiment.BASE_FEATURES, config, params)
            data['yhat_xgb_midas_dec'], info = experiment.run_xgb_midas_epu_dec(data, 'yhat_xgb_market', config)
        (folder / 'xgb_refits.json').write_text(json.dumps(records, indent=2) + '\n')
        (folder / 'midas_optimizer_diagnostics.json').write_text(json.dumps(info['optimization_diagnostics'], indent=2) + '\n')
        (folder / 'warnings.json').write_text(json.dumps([str(n.message) for n in notices], indent=2) + '\n')
        (folder / 'selected_spec.json').write_text(json.dumps(info['best_spec'], indent=2) + '\n')
        data[['date', 'sample_flag', 'y', 'yhat_xgb_market', 'yhat_xgb_midas_dec']].to_csv(folder / 'predictions.csv', index=False)
        for model, column in [('XGB', 'yhat_xgb_market'), ('DEC', 'yhat_xgb_midas_dec')]:
            same_missing = data[column].isna().equals(original[column].isna())
            for part in ['valid', 'test', 'all']:
                mask = original[column].notna() & (original.sample_flag.eq(part) if part != 'all' else True)
                if not mask.any():
                    continue
                diff = data.loc[mask, column].to_numpy() - original.loc[mask, column].to_numpy()
                rows.append(dict(market=market, model=model, partition=part, n=int(mask.sum()), same_missing=same_missing,
                                 max_abs_error=float(abs(diff).max()), rmse=float(np.sqrt(np.mean(diff ** 2))),
                                 matched_at_1e_6=int((abs(diff) <= 1e-6).sum()), exactly_equal=int((diff == 0).sum())))
        pd.DataFrame(rows).to_csv(output / 'comparison.csv', index=False)
        print(f'{market}: predictions, {len(records)} booster configurations and {len(notices)} warnings saved.', flush=True)
    print('Compare XGB and DEC separately; a matching run does not identify a unique historical environment.')


if __name__ == '__main__':
    main()
