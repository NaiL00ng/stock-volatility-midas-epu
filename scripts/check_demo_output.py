"""Validate synthetic demo outputs without third-party dependencies.

No training, network access or writes. Checks the recorded execution platform;
foreign-platform dependency resolution alone cannot satisfy this check.
"""
from pathlib import Path
import argparse
import csv
from datetime import date, timedelta
import json
import math


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def validate(folder, expected_platform):
    run=json.loads((folder/'synthetic_run.json').read_text(encoding='utf-8'))
    platform=run['runtime'].get('system')
    if expected_platform and platform != expected_platform:
        raise ValueError(f'Expected a recorded {expected_platform} run; found {platform!r}.')
    if platform not in {'Darwin','Linux','Windows'}:
        raise ValueError('Missing or unsupported recorded execution platform.')
    if run['data_kind']!='synthetic_demo' or run['is_empirical_evidence'] is not False:
        raise ValueError('Outputs must be explicitly marked as synthetic, not empirical evidence.')
    if run['raw_price_rows']!=640 or run['prepared_rows']!=617 or run['split']!={'train':200,'valid':200,'test':217}:
        raise ValueError('Unexpected synthetic sample counts.')
    if run['stage2_selection']!={'usable_validation_residuals':199,'train':119,'score':80}:
        raise ValueError('Unexpected second-stage sample counts.')
    predictions=read_csv(folder/'synthetic_predictions.csv')
    metrics=read_csv(folder/'synthetic_metrics.csv')
    search=read_csv(folder/'synthetic_spec_search.csv')
    models={'XGB_Market':'yhat_xgb_market','XGB_Residual_AR':'yhat_ar','XGB_MIDAS_EPU_DEC':'yhat_dec'}
    if len(predictions)!=217 or len(metrics)!=3 or {r['model'] for r in metrics}!=set(models):
        raise ValueError('Expected 217 predictions and exactly three distinct model summaries.')
    if len(search)!=6 or {(int(r['K']),r['weight_type']) for r in search}!={(k,w) for k in [6,12,24] for w in ['beta','expalmon']}:
        raise ValueError('Expected all six MIDAS candidates.')
    if any(int(r['n_stage2_train'])!=119 or int(r['n_stage2_valid'])!=80 for r in search):
        raise ValueError('Unexpected candidate selection split.')
    diagnostics=run['optimization_diagnostics']
    if len(diagnostics)!=10 or any(not row.get('gradient_tolerance_met',False) or
                                  not math.isfinite(float(row['projected_gradient_inf'])) or
                                  float(row['projected_gradient_inf'])>1e-6 for row in diagnostics):
        raise ValueError('Incomplete or nonstationary optimization diagnostics.')
    dates=[date.fromisoformat(row['date'][:10]) for row in predictions]
    if dates!=sorted(set(dates)) or dates[0].isoformat()!=run['first_test_origin'] or dates[-1].isoformat()!=run['last_test_origin']:
        raise ValueError('Invalid prediction origin dates.')
    for origin,row in zip(dates,predictions):
        target=origin+timedelta(days=1)
        while target.weekday()>=5:
            target+=timedelta(days=1)
        if date.fromisoformat(row['target_date'][:10])!=target or row['data_kind']!='synthetic_demo':
            raise ValueError('Invalid next-business-day target or data label.')
        if any(not math.isfinite(float(row[col])) for col in ['y',*models.values()]):
            raise ValueError('Nonfinite prediction or target.')
    max_error=0.
    for row in metrics:
        if int(row['n_test'])!=217 or row['data_kind']!='synthetic_demo':
            raise ValueError('Invalid metric sample count or label.')
        pairs=[(float(p['y']),float(p[models[row['model']]])) for p in predictions]
        diffs=[y-p for y,p in pairs]
        ratios=[max(math.exp(y)-1e-8,1e-12)/max(math.exp(p)-1e-8,1e-12) for y,p in pairs]
        values={'MSE':math.fsum(d*d for d in diffs)/217,
                'MAE':math.fsum(abs(d) for d in diffs)/217,
                'Bias':math.fsum(diffs)/217,
                'QLIKE':math.fsum(r-math.log(r)-1 for r in ratios)/217}
        for key,value in values.items():
            recorded=float(row[key]);max_error=max(max_error,abs(value-recorded))
            if not math.isclose(value,recorded,rel_tol=1e-10,abs_tol=1e-10):
                raise ValueError(f'Inconsistent {key} for {row["model"]}.')
    print(f'PASS: recorded platform={platform}; 217 dates; 3 models; 6 candidates; 10 stationary fits.')
    print(f'Independent metric maximum difference: {max_error:.3g}. Synthetic evidence only.')


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=root/'generated/synthetic-demo')
    parser.add_argument('--expected-platform',choices=['Darwin','Linux','Windows'])
    args=parser.parse_args()
    try:
        validate(args.input,args.expected_platform)
    except (OSError,KeyError,ValueError,OverflowError,TypeError) as error:
        parser.exit(1,f'Demo output validation failed: {error}\n')


if __name__=='__main__':
    main()
