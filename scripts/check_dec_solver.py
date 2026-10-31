"""Check gradients, fixed-spec controls and dependency sensitivity on saved panels.

Only local generated/ inputs and new outputs are accepted. No downloading or
training-set changes. A dependency directory, if given, must also be local.
"""
from pathlib import Path
import argparse, os, sys, json


def main():
    root=Path(__file__).resolve().parents[1]
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--dependency-path',type=Path)
    a=ap.parse_args(); inp=a.input.resolve();out=a.output.resolve()
    for p in [inp,out]+([a.dependency_path.resolve()] if a.dependency_path else []):
        if not p.is_relative_to(root/'generated'):ap.error('All paths must be inside generated/.')
    if out.exists() and any(out.iterdir()):ap.error('Use an empty output directory.')
    out.mkdir(parents=True,exist_ok=True)
    os.environ['MPLCONFIGDIR']=str(root/'generated/matplotlib')
    if a.dependency_path:sys.path.insert(0,str(a.dependency_path.resolve()))
    import numpy as np,pandas as pd,scipy,statsmodels
    import csi300_epu_final_from_oldcode as ex
    from dec_stable import estimate_stable,make_objective,weights_and_jacobian,projected_gradient
    (out/'runtime.json').write_text(json.dumps(dict(numpy=np.__version__,scipy=scipy.__version__,pandas=pd.__version__,statsmodels=statsmodels.__version__),indent=2))
    spec=json.loads((root/'configs/experiments.json').read_text()); legacy=ex.estimate_midas_profiled_ols
    records=[];tests=[];diffs=[]
    for market in ['csi300','sse50','nasdaq']:
        data=pd.read_csv(inp/market/'all_model_predictions.csv',parse_dates=['date'])
        cfg=ex.ExperimentConfig(**spec['common'],n_train=spec['markets'][market]['n_train'],verbose=False)
        def audited(y,lag_matrix,controls,weight_type='beta'):
            old=legacy(y,lag_matrix,controls,weight_type)
            new=estimate_stable(y,lag_matrix,controls,weight_type)
            f=make_objective(y,lag_matrix,controls);val,g=f(new.theta,weight_type)
            bounds=[(.05,20.)]*2 if weight_type=='beta' else [(-5.,5.)]*2
            h=1e-4;gn=[]
            for j,(lo,hi) in enumerate(bounds):
                left=new.theta.copy();right=new.theta.copy();left[j]=max(lo,left[j]-h);right[j]=min(hi,right[j]+h)
                gn.append((f(right,weight_type)[0]-f(left,weight_type)[0])/(right[j]-left[j]))
            sse=float(new.sse);objective_delta=sse-old.sse
            if objective_delta>1e-7:raise AssertionError('Stable solver raised training SSE')
            assert abs(sse-val*len(y))<1e-7
            records.append(dict(market=market,n_train=len(y),K=lag_matrix.shape[1],family=weight_type,
                                legacy_SSE=old.sse,stable_SSE=sse,training_SSE_delta=objective_delta,
                                analytic_projected_gradient=projected_gradient(new.theta,g,bounds),
                                finite_difference_projected_gradient=projected_gradient(new.theta,np.array(gn),bounds)))
            return new
        ex.estimate_midas_profiled_ols=audited
        pred,info=ex.run_xgb_midas_epu_dec(data,'yhat_xgb_market',cfg)
        mask=data.sample_flag.eq('test'); delta=(pred-data.yhat_xgb_midas_dec).loc[mask]
        diffs.append(dict(market=market,n=int(mask.sum()),K=info['best_spec']['K'],family=info['best_spec']['weight_type'],max_prediction_delta=float(abs(delta).max()),rmse_prediction_delta=float(np.sqrt((delta**2).mean()))))
        pd.DataFrame({'date':data.date,'yhat_stable':pred}).to_csv(out/f'{market}_stable.csv',index=False)
        if market=='nasdaq':
            # Historical selected family held fixed, independent of revised test losses.
            cfg.midas_k_grid=(12,);cfg.midas_weight_types=('beta',)
            ex.estimate_midas_profiled_ols=estimate_stable
            frozen,finfo=ex.run_xgb_midas_epu_dec(data,'yhat_xgb_market',cfg)
            tests.append(dict(market=market,variant='stable_historical_spec_K12_Beta',**ex.point_metrics(data.loc[mask,'y'].to_numpy(),frozen.loc[mask].to_numpy(),cfg.eps)))
            pd.DataFrame({'date':data.date,'yhat_stable_fixed_beta':frozen}).to_csv(out/'nasdaq_fixed_beta.csv',index=False)
        print(market,diffs[-1],flush=True)
    pd.DataFrame(records).to_csv(out/'training_objective_checks.csv',index=False)
    pd.DataFrame(diffs).to_csv(out/'prediction_sensitivity.csv',index=False)
    pd.DataFrame(tests).to_csv(out/'fixed_spec_metrics.csv',index=False)


if __name__=='__main__':main()
