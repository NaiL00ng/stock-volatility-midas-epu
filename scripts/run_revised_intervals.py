"""Evaluate revised CSI300 residual intervals on identical dates for five models.

Same retrospective calibration rules, alpha grid, windows and warm-up as the
historical experiment. No exchangeability or real-time input claim is made.
"""
from pathlib import Path
import argparse,os


def main():
    root=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve();inp=a.input.resolve()
    if not out.is_relative_to(root/'generated') or not inp.is_relative_to(root/'generated'):ap.error('Keep inputs and outputs inside generated/.')
    if out.exists() and any(out.iterdir()):ap.error('Use a new empty output directory.')
    out.mkdir(parents=True,exist_ok=True);os.environ['MPLCONFIGDIR']=str(root/'generated/matplotlib')
    import numpy as np,pandas as pd
    import conformal_interval_experiment as ci
    cfg=ci.IntervalConfig(input_predictions_path=str(inp),output_dir=str(out),figure_dpi=180)
    data,models=ci.load_prediction_panel(cfg);models['XGB_Residual_AR']='yhat_xgb_ar'
    summaries=[];tests=[];main_frames=[];checks=[]
    for alpha in cfg.alpha_list:
        for window in cfg.calibration_windows:
            panels={m:ci.rolling_conformal_intervals_for_model(data,m,c,alpha,window,cfg) for m,c in models.items()}
            dates=set.intersection(*[set(p.loc[p.sample_flag.eq('test')&p.interval_score.notna(),'date']) for p in panels.values()])
            assert len(dates)==1859
            for model,panel in panels.items():
                selected=panel.loc[panel.date.isin(dates)].copy()
                # Independent score calculation and all-period order-statistic check.
                y=selected.y.to_numpy();lo=selected.lower_y.to_numpy();hi=selected.upper_y.to_numpy()
                manual=hi-lo+2/alpha*np.maximum(lo-y,0)+2/alpha*np.maximum(y-hi,0)
                assert np.max(abs(manual-selected.interval_score))<1e-12
                pred=panel.yhat.to_numpy();target=panel.y.to_numpy();flags=panel.sample_flag.to_numpy();max_quantile_error=0.
                for j in selected.index:
                    available=np.flatnonzero(np.isfinite(pred[:j])&np.isin(flags[:j],['valid','test']))[-window:]
                    scores=np.abs(target[available]-pred[available]);rank=min(int(np.ceil((len(scores)+1)*(1-alpha))),len(scores))
                    q=np.partition(scores,rank-1)[rank-1]
                    max_quantile_error=max(max_quantile_error,abs(q-panel.at[j,'qhat']))
                assert max_quantile_error==0
                summaries.append(ci.summarize_interval_result(selected,cfg))
                tests.append(dict(model=model,alpha=alpha,calibration_window=window,**ci.christoffersen_tests(selected.covered.to_numpy(),alpha)))
                checks.append(dict(model=model,alpha=alpha,calibration_window=window,n=len(selected),max_quantile_error=max_quantile_error,max_score_error=float(np.max(abs(manual-selected.interval_score)))))
                selected.to_csv(out/f'interval_{model}_a{round(alpha*100):02d}_m{window}.csv',index=False)
                if alpha==cfg.main_alpha and window==cfg.main_window:main_frames.append(selected)
            print('Completed',alpha,window,flush=True)
    summary=pd.DataFrame(summaries).drop(columns=['coverage_valid','coverage_valid_cutoff']);summary.to_csv(out/'interval_common_dates.csv',index=False)
    pd.DataFrame(tests).to_csv(out/'coverage_common_dates.csv',index=False)
    pd.DataFrame(checks).to_csv(out/'interval_checks.csv',index=False)
    combined=pd.concat(main_frames,ignore_index=True);combined.to_csv(out/'main_common_intervals.csv',index=False)
    ci.plot_main_interval_scores(summary,str(out/'fig_interval_score_main.png'),cfg)
    # Longer labels require more room than the historical scatter template.
    import matplotlib.pyplot as plt
    small=summary.loc[summary.alpha.eq(.10)&summary.calibration_window.eq(250)]
    fig,ax=plt.subplots(figsize=(9,5),dpi=180)
    for _,row in small.iterrows():
        ax.scatter(row.avg_width_y,row.empirical_coverage,s=65,label=row.model)
    ax.axhline(.9,ls='--',color='gray');ax.set(xlabel='Average width (log target)',ylabel='Empirical coverage',title='Common dates: 90% intervals, window 250')
    ax.legend(fontsize=8,loc='upper left',bbox_to_anchor=(1.01,1));ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'fig_coverage_width_tradeoff_main.png');plt.close(fig)
    ci.plot_rolling_coverage(combined,str(out/'fig_rolling_coverage_main.png'),cfg)
    ci.plot_interval_series(combined.loc[combined.model.eq('XGB_MIDAS_EPU_DEC')],str(out/'fig_interval_series_XGB_MIDAS_EPU_DEC.png'),cfg,'XGB_MIDAS_EPU_DEC')
    print(small.to_string(index=False),flush=True)


if __name__=='__main__':main()
