"""Run the documented candidate pipeline for one or all three indices.

The current-environment results are new experiments. They must not overwrite or
be described as exact reproductions of the historical results without comparison.
"""
from pathlib import Path
import argparse
import importlib.metadata
import json
import warnings
import numpy as np
import pandas as pd
import csi300_epu_final_from_oldcode as experiment


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=root / 'data')
    parser.add_argument('--market', choices=['all', 'csi300', 'sse50', 'nasdaq'], default='all')
    parser.add_argument('--reference-archive', type=Path, help='Optional local original archive for prediction-by-prediction comparison')
    parser.add_argument('--output', type=Path, default=root / 'generated/runs')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(root / 'generated'):
        parser.error('Output must be inside this project\'s generated directory.')
    spec = json.loads((root / 'configs/experiments.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    versions = {name: importlib.metadata.version(name) for name in ['numpy','pandas','scipy','statsmodels','arch','xgboost','scikit-learn']}
    (output / 'runtime_versions.json').write_text(json.dumps(versions, indent=2) + '\n')
    comparisons = []
    selected = spec['markets'] if args.market == 'all' else [args.market]
    for market in selected:
        case = spec['markets'][market]
        prices = pd.read_excel(args.data_dir / case['prices'])
        epu = pd.read_excel(args.data_dir / case['epu'], sheet_name='Monthly')
        config = experiment.ExperimentConfig(**spec['common'], n_train=case['n_train'], output_dir=str(output / market), verbose=True)
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always')
            predictions, metrics, tests, meta = experiment.run_final_experiment(prices, epu, config, xgb_params=spec['xgboost'])
        (output / market / 'runtime_warnings.json').write_text(json.dumps([{'category':type(n.message).__name__,'message':str(n.message)} for n in notices], indent=2) + '\n')
        print(f'{market}: {len(notices)} runtime warnings saved for inspection.')
        if args.reference_archive:
            original = pd.read_csv(args.reference_archive / 'outputs' / (case['archive_prefix'] + '_epu_final_outputs') / 'all_model_predictions.csv')
            if predictions.date.dt.strftime('%Y-%m-%d').tolist() != original.date.tolist():
                raise ValueError('Prediction dates differ from the reference; do not compare rows by position.')
            for model, column in {'HAR':'yhat_har','GARCH':'yhat_garch','XGB_Market':'yhat_xgb_market','XGB_MIDAS_EPU_DEC':'yhat_xgb_midas_dec'}.items():
                same_missing = predictions[column].isna().equals(original[column].isna())
                mask = predictions[column].notna() & original[column].notna()
                difference = predictions.loc[mask, column].to_numpy() - original.loc[mask, column].to_numpy()
                comparisons.append(dict(market=market,model=model,n=int(mask.sum()),same_missing=same_missing,max_abs_error=float(np.max(np.abs(difference))),rmse=float(np.sqrt(np.mean(difference ** 2))),matched_at_1e_6=bool(same_missing and np.allclose(predictions.loc[mask,column],original.loc[mask,column],atol=1e-6,rtol=0))))
            pd.DataFrame(comparisons).to_csv(output / 'training_comparison.csv', index=False)
    print('Completed candidate runs. Historical training identity still requires the comparison evidence.')


if __name__ == '__main__':
    main()
