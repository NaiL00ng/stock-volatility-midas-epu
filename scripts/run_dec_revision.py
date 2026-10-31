"""Re-estimate DEC with a checked solver and a residual-only ablation.

Writes only a new local generated directory. Source data are read only. With
--reuse-local-first-stage, previously verified local XGB predictions are reused
only after date, flag and target checks; SHA256 identifies each cache. Default
re-estimates XGB with the documented sampling-compatible build.
"""
from pathlib import Path
import argparse, hashlib, importlib.metadata, json, os, sys, warnings


def main():
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    sources = ap.add_mutually_exclusive_group()
    sources.add_argument('--archive', type=Path, help='Local archive containing data source/')
    sources.add_argument('--data-dir', type=Path, help='Directory containing the five documented input workbooks')
    ap.add_argument('--xgboost-python-path', type=Path, required=True)
    ap.add_argument('--output', type=Path, default=root/'generated/dec-revision')
    ap.add_argument('--reuse-local-first-stage', action='store_true')
    args = ap.parse_args()
    out, package = args.output.resolve(), args.xgboost_python_path.resolve()
    if not out.is_relative_to(root/'generated') or not package.is_relative_to(root/'generated'):
        ap.error('Output and package must stay inside generated/.')
    if out.exists() and any(out.iterdir()):
        ap.error('Choose a new empty output directory.')
    out.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(root/'generated/matplotlib')
    os.environ['FORENSIC_MSVC_SHUFFLE'] = '1'
    sys.path.insert(0, str(package))
    import numpy as np
    import pandas as pd
    import xgboost
    from scipy.stats import norm
    from statsmodels.stats.multitest import multipletests
    import csi300_epu_final_from_oldcode as ex
    from dec_stable import estimate_stable, residual_only_predictions
    if xgboost.__version__ != '2.0.3':
        raise ValueError('Use the documented XGBoost 2.0.3 build.')
    data_dir = (args.archive/'data source') if args.archive else (args.data_dir or root/'data')
    spec = json.loads((root/'configs/experiments.json').read_text())
    protocol = json.loads((root/'configs/dec-revision.json').read_text())
    (out/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    runtime = {n:importlib.metadata.version(n) for n in ['numpy','scipy','pandas','statsmodels']}
    runtime.update(xgboost=xgboost.__version__, xgboost_binary_sha256=hashlib.sha256(Path(xgboost.core._LIB._name).read_bytes()).hexdigest())
    (out/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    models = {'HAR':'yhat_har', 'GARCH':'yhat_garch', 'XGB_Market':'yhat_xgb_market',
              'XGB_Residual_AR':'yhat_xgb_ar', 'XGB_MIDAS_EPU_DEC':'yhat_xgb_midas_dec'}
    rows, checks, tests, cache_records = [], [], [], []
    legacy_solver = ex.estimate_midas_profiled_ols
    for market, case in spec['markets'].items():
        prices = pd.read_excel(data_dir/case['prices'])
        epu = pd.read_excel(data_dir/case['epu'], sheet_name='Monthly')
        variants = ['historical_input','calendar_corrected'] if market == 'sse50' else ['historical_input']
        for variant in variants:
            key = market + ('_historical_input' if market=='sse50' and variant=='historical_input' else '')
            folder = out/key; folder.mkdir()
            p = prices
            if variant == 'calendar_corrected':
                exclude = pd.to_datetime(prices.date).eq(pd.Timestamp('2018-06-18'))
                assert exclude.sum()==1
                p = prices.loc[~exclude].copy()
            cfg = ex.ExperimentConfig(**spec['common'], n_train=case['n_train'], verbose=False, output_dir=str(folder))
            with warnings.catch_warnings(record=True) as notices:
                warnings.simplefilter('always')
                data = ex.add_sample_flags(ex.prepare_main_dataframe(p,epu,cfg),cfg)
                if args.reuse_local_first_stage:
                    if variant=='calendar_corrected':
                        cache = root/'generated/training-forensics/calendar-sensitivity/calendar_corrected/all_model_predictions.csv'
                    else:
                        cache = root/f'generated/training-forensics/public-run-verified/{market}/predictions.csv'
                    saved = pd.read_csv(cache)
                    assert data.date.dt.strftime('%Y-%m-%d').tolist()==saved.date.tolist()
                    assert data.sample_flag.equals(saved.sample_flag)
                    assert np.max(abs(data.y-saved.y))<2e-14
                    data['yhat_xgb_market'] = saved.yhat_xgb_market.to_numpy()
                    cache_records.append(dict(market=market,variant=variant, cache=str(cache.relative_to(root)),sha256=hashlib.sha256(cache.read_bytes()).hexdigest()))
                else:
                    data['yhat_xgb_market'] = ex.expanding_xgb_market(data,ex.BASE_FEATURES,cfg,{**spec['xgboost'],'n_jobs':4})
                ex.estimate_midas_profiled_ols = legacy_solver
                data['yhat_dec_legacy'], old_info = ex.run_xgb_midas_epu_dec(data,'yhat_xgb_market',cfg)
                ex.estimate_midas_profiled_ols = estimate_stable
                try:
                    data['yhat_xgb_midas_dec'], info = ex.run_xgb_midas_epu_dec(data,'yhat_xgb_market',cfg)
                    if len(info['search_results']) != 6 or any(not d.get('gradient_tolerance_met',False) for d in info['optimization_diagnostics']):
                        raise RuntimeError('Incomplete specification search or failed stationarity; stop the revision.')
                finally:
                    ex.estimate_midas_profiled_ols = legacy_solver
                data['yhat_xgb_ar'] = residual_only_predictions(data,cfg)
                data['yhat_har'] = ex.expanding_har(data,cfg)
                data['yhat_garch'] = ex.expanding_garch(data,cfg)
            (folder/'warnings.json').write_text(json.dumps([str(n.message) for n in notices],indent=2)+'\n')
            data.to_csv(folder/'all_model_predictions.csv',index=False)
            info['search_results'].to_csv(folder/'midas_dec_search_results.csv',index=False)
            pd.DataFrame([info['best_spec']]).to_csv(folder/'midas_dec_best_spec.csv',index=False)
            (folder/'optimizer_diagnostics.json').write_text(json.dumps(info['optimization_diagnostics'],indent=2)+'\n')
            summary = ex.evaluate_all_models(data,models,cfg); summary.to_csv(folder/'metrics_summary.csv',index=False)
            test = data.loc[data.sample_flag.eq('test')]
            for model,col in {**models,'DEC_legacy_current':'yhat_dec_legacy'}.items():
                rows.append(dict(market=market,input_variant=variant,model=model,**ex.point_metrics(test.y.to_numpy(),test[col].to_numpy(),cfg.eps)))
            for i,d in enumerate(info['optimization_diagnostics']):
                checks.append(dict(market=market,input_variant=variant,refit=i,**{k:v for k,v in d.items() if k!='starts'}))
            loss_panel=ex.build_loss_panel(data,models,cfg)
            loss_panel.to_csv(folder/'loss_panel.csv',index=False)
            ex.plot_metrics_bar(summary,str(folder/'fig_metrics_bar.png'),cfg)
            ex.plot_cumulative_qlike_diff(loss_panel,str(folder/'fig_cumulative_qlike_diff.png'),cfg)
            ex.plot_prediction_series(loss_panel,str(folder/'fig_prediction_series_recent.png'),cfg)
            ex.plot_midas_weights(info['best_spec'],str(folder/'fig_midas_weights.png'),cfg)
            if key != 'sse50_historical_input':
                y = test.y.to_numpy(); dec = test.yhat_xgb_midas_dec.to_numpy()
                for comparator,col in [('XGB_Market','yhat_xgb_market'),('XGB_Residual_AR','yhat_xgb_ar')]:
                    a = test[col].to_numpy()
                    for metric,la,lb in [('MSE',(y-a)**2,(y-dec)**2),('MAE',abs(y-a),abs(y-dec)),('QLIKE',ex.qlike_loss_from_logvar(y,a,cfg.eps),ex.qlike_loss_from_logvar(y,dec,cfg.eps))]:
                        d=la-lb;lag=ex.auto_hac_lag(len(d));se=ex.hac_se_mean(d,lag);z=float(d.mean()/se)
                        tests.append(dict(market=market,comparator=comparator,model='DEC',loss=metric,n=len(d),hac_lag=lag,mean_A_minus_DEC=float(d.mean()),HAC_se=se,z=z,p_two_sided=float(2*norm.sf(abs(z)))))
            print(key,info['best_spec'],flush=True)
            print(summary.to_string(index=False),flush=True)
            pd.DataFrame(rows).to_csv(out/'point_metrics.csv',index=False)
            pd.DataFrame(checks).to_csv(out/'optimizer_checks.csv',index=False)
    stats=pd.DataFrame(tests);stats['p_holm_18']=multipletests(stats.p_two_sided,method='holm')[1];stats.to_csv(out/'loss_difference_diagnostics.csv',index=False)
    (out/'first_stage_cache.json').write_text(json.dumps(cache_records,indent=2)+'\n')
    print('Completed. Numerical correction is not guaranteed to improve forecast losses.',flush=True)


if __name__ == '__main__':
    main()
