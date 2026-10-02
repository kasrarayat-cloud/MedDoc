import hashlib, json, subprocess, datetime as dt
from pathlib import Path
ROOT = Path('/opt/meddoc-pro/.worktrees/v1-sonnet5-diagnostics')
DIAG = ROOT / 'docs/rebuild/v1/sonnet5-campaign/diagnostics'
RUNTIME = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a): return subprocess.check_output(['git', '-C', str(ROOT), *a], text=True).strip()
files = {str(p.relative_to(DIAG)): sha(p) for p in sorted(DIAG.rglob('*')) if p.is_file() and p.name != 'FREEZE.json'
         and '__pycache__' not in p.parts}
runtime = {str(p.relative_to(RUNTIME)): sha(p) for sub in ('mapping', 'notes') for p in sorted((RUNTIME / sub).glob('*.docx'))}
rec = lambda name: json.loads((DIAG / name).read_text())
base = rec('mapping/baseline-deterministic.json'); st = rec('mapping/app-path-selftest.json')
la = rec('mapping/long-answer-readback.json'); wc = rec('mapping/wording-check.json')
obs = rec('notes/offline-observations.json'); walk = rec('notes/app-path-walk.json'); cases = rec('notes/cases.json')
manifest = (DIAG / 'mapping/EXPECTED-SHA256SUMS').read_text().split('\n')
freeze = {
    'schema': 'quillmd-sonnet5-diagnostics-freeze/1',
    'written_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'candidate': {'sha': '8e3dcfd07a5946430e7291b520faf35c8055127b', 'short': '8e3dcfd0',
                  'rebuild_equals_candidate': subprocess.run(['git', '-C', str(ROOT), 'diff', '--quiet',
                      '8e3dcfd07a5946430e7291b520faf35c8055127b', '--', 'rebuild']).returncode == 0},
    'order_of_work': [
        {'step': 'checked sets (defects included)', 'commit': '00a423a956b3a95bc41efdb7ede4ad72668443e7',
         'committed_at': git('log', '-1', '--format=%cI', '00a423a9')},
        {'step': 'expectations, graders, generators and notes cases re-frozen (EXPECTED-SHA256SUMS)',
         'commit': git('rev-parse', '0beaf2b2'), 'committed_at': git('log', '-1', '--format=%cI', '0beaf2b2')},
        {'step': 'deterministic mapping baseline recorded', 'recorded_at': base['recorded_at']},
        {'step': 'app-path grader self-test recorded', 'recorded_at': st['recorded_at']},
        {'step': 'long-answer fill and read-back recorded', 'recorded_at': la['recorded_at']},
        {'step': 'wording check recorded', 'recorded_at': wc['recorded_at']},
        {'step': 'notes offline observations recorded', 'recorded_at': obs['recorded_at']},
        {'step': 'notes app-path walk recorded', 'recorded_at': walk['completed_at']},
        {'step': 'this manifest', 'recorded_at': None}],
    'expected_sha256sums': [l for l in manifest if l],
    'records_match_the_freeze': {
        'baseline_expectations_match_frozen': base['expectations']['match_frozen'],
        'baseline_graders_frozen_with_maps': base['expectations']['frozen_with_them'],
        'observations_cases_sha256': obs['cases_sha256'],
        'walk_cases_sha256': walk['cases_sha256'],
        'cases_sha256_now': sha(DIAG / 'notes/cases.json'),
        'selftest_script_sha256': st['script_sha256'], 'selftest_checks_passed': all(c['passed'] for c in st['checks'])},
    'results': {
        'baseline_totals': base['totals'],
        'app_path_selftest_totals': st['totals'],
        'long_answer': la['verdict'] + ' (%d characters)' % la['answer_characters'],
        'wording_check': wc['verdict'], 'wording_check_positive_control': wc['positive_control'],
        'notes_reference_verdicts_on_sent_paths': obs['reference_verdicts_on_sent_paths'],
        'notes_entries_depending_on_other_fields': obs['entries_depending_on_other_fields'],
        'notes_walk_summary': walk['summary'],
        'notes_budget': cases['budget']},
    'positive_controls_run_offline': {
        'check_expected': 'a copy with f2b.A2 option 0, one control slot and f4.A7 label altered: 4 mismatches, exit 1',
        'measure_baseline': 'a copy with f5.C2 altered: refused (map differs from EXPECTED-SHA256SUMS), exit 1',
        'offline_replay_record': 'a cases.json copy differing by one space: --record refused, nothing written, exit 1',
        'offline_replay_drift': 'an observations copy with N09 v3_1 default status changed: drift on cases, exit 1',
        'offline_replay_repeat': 'two unmodified drift checks after recording: exit 0 both',
        'wording_check': 'the checked sets read from git 00a423a9: %d gated hits in 4 files' % wc['positive_control']['gated_hits'],
        'grade_app_path': '%d of %d stated checks passed' % (sum(c['passed'] for c in st['checks']), len(st['checks']))},
    'files_sha256': files,
    'runtime_forms_sha256': runtime,
    'runtime_dir': str(RUNTIME),
    'not_in_this_manifest': 'REPAIR.md (written by the lead from this pass\'s report after this manifest)',
}
(DIAG / 'FREEZE.json').write_text(json.dumps(freeze, indent=1, ensure_ascii=False) + '\n')
print(json.dumps({k: freeze[k] for k in ('written_at', 'candidate', 'order_of_work', 'records_match_the_freeze')}, indent=1))
print(len(files), 'files', len(runtime), 'runtime forms')
