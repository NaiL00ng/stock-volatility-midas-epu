"""Audit shifted targets and retained-row residual lags in the historical pipeline.

This is not a complete exchange-calendar audit. The SSE50 date 2018-06-18 is a
confirmed closure in the SSE's 2018 holiday notice; zero volume alone does not
establish that any other date is a holiday.
"""
from pathlib import Path
import argparse
import json
import pandas as pd
import csi300_epu_final_from_oldcode as experiment


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=root / 'generated/method-timing')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(root / 'generated'):
        parser.error('Output must be inside this project\'s generated directory.')
    output.mkdir(parents=True, exist_ok=True)
    spec = json.loads((root / 'configs/experiments.json').read_text())
    rows, details = [], []
    for market, case in spec['markets'].items():
        raw = pd.read_excel(args.archive / 'data source' / case['prices'])
        raw['date'] = pd.to_datetime(raw.date)
        raw = raw.sort_values('date').drop_duplicates('date').reset_index(drop=True)
        targets = dict(zip(raw.date, raw.date.shift(-1)))
        original = pd.read_csv(args.archive / 'outputs' / (case['archive_prefix'] + '_epu_final_outputs') / 'all_model_predictions.csv', parse_dates=['date'])
        target_dates = original.date.map(targets)
        lag_target = target_dates.shift(1)
        dec = original.yhat_xgb_midas_dec.notna()
        gaps = dec & lag_target.ne(original.date)
        future = dec & lag_target.gt(original.date)
        zero_dates = set(raw.loc[raw.volume.eq(0), 'date'])
        rows.append(dict(market=market, retained_rows=len(original), zero_volume_source_rows=len(zero_dates),
                         targets_on_zero_volume_rows=int(target_dates.isin(zero_dates).sum()),
                         dec_stale_lag_count=int(gaps.sum()), dec_future_lag_count=int(future.sum()),
                         confirmed_holiday_target_count=int(target_dates.eq(pd.Timestamp('2018-06-18')).sum()) if market == 'sse50' else 0))
        for i in original.index[gaps]:
            details.append(dict(market=market, issue='retained_row_lag_is_not_current_day_error',
                                origin_date=original.at[i, 'date'].strftime('%Y-%m-%d'),
                                referenced_target_date=lag_target.at[i].strftime('%Y-%m-%d')))
        if market == 'sse50':
            for i in original.index[target_dates.eq(pd.Timestamp('2018-06-18'))]:
                details.append(dict(market=market, issue='confirmed_holiday_shifted_target',
                                    origin_date=original.at[i, 'date'].strftime('%Y-%m-%d'),
                                    referenced_target_date='2018-06-18'))
            cleaned = raw.loc[~raw.date.eq(pd.Timestamp('2018-06-18'))].copy()
            epu = pd.read_excel(args.archive / 'data source' / case['epu'], sheet_name='Monthly')
            config = experiment.ExperimentConfig(n_train=case['n_train'], verbose=False)
            prepared = experiment.add_sample_flags(experiment.prepare_main_dataframe(cleaned, epu, config), config)
            prepared.to_csv(output / 'sse50_calendar_corrected_prepared.csv', index=False)
            (output / 'sse50_correction_summary.json').write_text(json.dumps(dict(
                excluded_date='2018-06-18', original_rows=len(original), corrected_rows=len(prepared),
                corrected_split=prepared.sample_flag.value_counts().to_dict(),
                status='New input variant only; historical model outputs are unchanged; models must be re-estimated before evaluation.'), indent=2) + '\n')
    pd.DataFrame(rows).to_csv(output / 'method_timing_checks.csv', index=False)
    pd.DataFrame(details).to_csv(output / 'method_timing_exceptions.csv', index=False)
    print('Timing audit and a separately labeled SSE50 corrected input saved locally.')


if __name__ == '__main__':
    main()
