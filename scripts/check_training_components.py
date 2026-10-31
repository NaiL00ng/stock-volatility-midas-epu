"""Check XGBoost parameter probes and isolate MIDAS using archived base predictions.

This is a forensic comparison, not parameter tuning on forecasting performance.
The early-stop probe assumes the older script's 15% inner holdout; that protocol
is not established for the final historical experiment.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import xgboost
import csi300_epu_final_from_oldcode as experiment


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=root / 'generated/components')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(root / 'generated'):
        parser.error('Output must be inside this project\'s generated directory.')
    output.mkdir(parents=True, exist_ok=True)
    folder = args.archive / 'outputs/csi300_epu_final_outputs'
    data = pd.read_csv(folder / 'prepared_master_data.csv')
    old = pd.read_csv(folder / 'all_model_predictions.csv')
    assert data.date.tolist() == old.date.tolist()
    parameters = experiment.XGB_PARAMS.copy()
    trials = [('candidate',parameters,False),('appendix_no_early_stop',{**parameters,'max_depth':3,'min_child_weight':5,'reg_alpha':0.0},False),('appendix_assumed_15pct_early_stop',{**parameters,'max_depth':3,'min_child_weight':5,'reg_alpha':0.0,'early_stopping_rounds':50,'eval_metric':'rmse','tree_method':'hist'},True)]
    for method, base in [('hist',0.5),('exact',0.5),('exact',None),('approx',0.5)]:
        trials.append((f'default_probe_{method}_{base}',{**parameters,'tree_method':method,'base_score':base},False))
    rows = []
    for label, params, early in trials:
        model = xgboost.XGBRegressor(**params)
        features = experiment.BASE_FEATURES
        if early:
            model.fit(data.iloc[:1275][features],data.y.iloc[:1275],eval_set=[(data.iloc[1275:1500][features],data.y.iloc[1275:1500])],verbose=False)
        else:
            model.fit(data.iloc[:1500][features],data.y.iloc[:1500])
        difference = model.predict(data.iloc[1500:1520][features]) - old.yhat_xgb_market.iloc[1500:1520].to_numpy()
        rows.append(dict(configuration=label,xgboost_version=xgboost.__version__,n=20,max_abs_error=float(np.max(np.abs(difference))),rmse=float(np.sqrt(np.mean(difference ** 2)))))
    pd.DataFrame(rows).to_csv(output / 'xgboost_probes.csv',index=False)
    rows = []
    for market,train in [('csi300',1500),('SSE50',1500),('NASDAQZH',2000)]:
        folder = args.archive / 'outputs' / (market + '_epu_final_outputs')
        data = pd.read_csv(folder / 'prepared_master_data.csv')
        original = pd.read_csv(folder / 'all_model_predictions.csv')
        assert data.date.tolist() == original.date.tolist()
        data['yhat_xgb_market'] = original.yhat_xgb_market
        new, spec = experiment.run_xgb_midas_epu_dec(data,'yhat_xgb_market',experiment.ExperimentConfig(n_train=train,verbose=False))
        mask = original.yhat_xgb_midas_dec.notna()
        difference = new[mask].to_numpy() - original.loc[mask,'yhat_xgb_midas_dec'].to_numpy()
        rows.append(dict(market=market,n=int(mask.sum()),max_abs_error=float(np.max(np.abs(difference))),rmse=float(np.sqrt(np.mean(difference ** 2))),K=spec['best_spec']['K'],weight_type=spec['best_spec']['weight_type']))
    pd.DataFrame(rows).to_csv(output / 'stage2_comparison.csv',index=False)
    print('Component checks saved. Isolated stage 2 uses historical base predictions and is not end-to-end reproduction.')


if __name__ == '__main__':
    main()
