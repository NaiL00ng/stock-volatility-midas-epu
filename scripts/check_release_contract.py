"""Check recorded sample definitions against public summaries; standard library only.

Optionally check a locally reproduced prediction directory. No training, downloads
or writes. The expected counts refer to the recorded inputs, not arbitrary data.
"""
from pathlib import Path
import argparse
import csv
import json


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, help='Optional run_dec_revision.py output directory')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/'configs/sample-splits.json').read_text())
    config = json.loads((root/'configs/experiments.json').read_text())
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    metrics = read_csv(root/manifest['current_results'])
    models = set(manifest['models'])
    check(len(models) == 5, 'Expected five distinct headline models.')
    check(len(metrics) == 24, 'Expected four input cases with six diagnostic model rows each.')
    for case in manifest['cases']:
        key = case['case']
        check(case['n_prepared'] == sum(case['n_'+flag] for flag in ('train', 'valid', 'test')),
              key+': split does not sum to prepared rows.')
        check(case['n_train'] == config['markets'][case['market']]['n_train'] and
              case['n_valid'] == config['common']['n_valid'], key+': split disagrees with training config.')
        rows = [r for r in metrics if r['market'] == case['market'] and r['input_variant'] == case['input_variant']]
        check(len(rows) == 6 and {r['model'] for r in rows} == models | {'DEC_legacy_current'},
              key+': missing or duplicate diagnostic model rows.')
        check(all(int(r['n_test']) == case['n_test'] for r in rows), key+': diagnostic test count differs.')
        if case['role'] == 'current_paper':
            folder = root/'results/revised'/case['market']
            table = read_csv(folder/'metrics_summary.csv')
            check(len(table) == 5 and {r['model'] for r in table} == models,
                  key+': headline model set differs.')
            check(all(int(r['n_test']) == case['n_test'] for r in table), key+': headline test count differs.')
            search = read_csv(folder/'midas_dec_search_results.csv')
            expected = {(str(k), family) for k in config['common']['midas_k_grid']
                        for family in config['common']['midas_weight_types']}
            check(len(search) == 6 and {(r['K'], r['weight_type']) for r in search} == expected,
                  key+': expected six distinct MIDAS specifications.')
            stage = manifest['stage2_selection']
            check(all(int(r['n_stage2_train']) == stage['train'] and int(r['n_stage2_valid']) == stage['score']
                      for r in search), key+': second-stage selection counts differ.')
        if args.predictions:
            panel = read_csv(args.predictions/key/'all_model_predictions.csv')
            check(len(panel) == case['n_prepared'], key+': reproduced prepared count differs.')
            for flag in ('train', 'valid', 'test'):
                check(sum(r['sample_flag'] == flag for r in panel) == case['n_'+flag], key+': '+flag+' count differs.')
            dates = [r['date'][:10] for r in panel if r['sample_flag'] == 'test']
            check(bool(dates) and dates[0] == case['test_origin_start'] and dates[-1] == case['test_origin_end'],
                  key+': reproduced test origin dates differ.')
            check(dates == sorted(set(dates)), key+': duplicate or unordered test dates.')
    stage = manifest['stage2_selection']
    check(stage['validation_rows'] == config['common']['n_valid'] and
          stage['usable_residual_pairs'] == stage['validation_rows']-1 and
          stage['train'] == int(stage['usable_residual_pairs']*config['common']['stage2_valid_train_frac']) and
          stage['train']+stage['score'] == stage['usable_residual_pairs'], 'Second-stage split is inconsistent.')
    intervals = read_csv(root/'results/revised/intervals/interval_common_dates.csv')
    expected_settings = {(m, a, w) for m in models for a in (.1, .05) for w in (120, 250, 500)}
    check(len(intervals) == manifest['csi300_intervals']['settings'] == 30 and
          {(r['model'], float(r['alpha']), int(r['calibration_window'])) for r in intervals} == expected_settings,
          'Expected 30 distinct interval settings.')
    check(all(int(r['n_eval']) == manifest['csi300_intervals']['common_dates'] for r in intervals),
          'Interval common-date sample size differs.')
    check((root/manifest['current_entry']).is_file(), 'Current entry is missing.')
    if errors:
        parser.exit(1, '\n'.join(errors)+'\n')
    print('PASS: four input cases, five headline models, six MIDAS specifications per market, 30 interval settings.')
    print('Current test counts: CSI300=1919, SSE50=1919, Nasdaq=1554; interval common dates=1859.')
    print('Local prediction counts and test origin dates checked.' if args.predictions else
          'Public-summary consistency only; private data, date membership and training were not revalidated.')


if __name__ == '__main__':
    main()
