"""Run app_path_walk.py (CHECK.md N6) on the candidate against the campaign QA PostgreSQL; mocked provider only.

    python -B run_app_path_walk.py TAG [--observations FILE] [--out app-path-walk.json] [--runtime DIR]
                                       [-- test labels...]

Django creates and drops a test database named quillmd_qa_diag_notes_<TAG>; nothing else on that server is touched.
The password is read from the campaign's qa-db file into the child's environment and never printed. Every tracked
and untracked source file under rebuild/ is hashed before and after the run; a change fails the run.

--runtime DIR (2026-09-29): where the per-walk records, the state directory and the log go (default: the campaign's
diagnostics runtime directory). The candidate check compares rebuild/ outside rebuild/ops/ (the campaign runner lives
there and is not the application under test).
"""
from pathlib import Path
import argparse, datetime, hashlib, json, re, subprocess, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
CANDIDATE = '8e3dcfd07a5946430e7291b520faf35c8055127b'
RUNTIME = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics/notes')
PASSWORD = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password')
PYTHON = ROOT / 'rebuild/.venv/bin/python'

ap = argparse.ArgumentParser()
ap.add_argument('tag')
ap.add_argument('--observations', type=Path, default=HERE / 'offline-observations.json')
ap.add_argument('--out', type=Path, default=HERE / 'app-path-walk.json')
ap.add_argument('--runtime', type=Path, default=RUNTIME)
ap.add_argument('labels', nargs='*')
args = ap.parse_args()
assert re.fullmatch(r'[a-z0-9]+', args.tag), 'tag: lowercase letters and digits'
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
engine_diff = subprocess.run(['git', 'diff', '--quiet', CANDIDATE, '--', 'rebuild', ':(exclude)rebuild/ops'],
                             cwd=ROOT).returncode
assert engine_diff == 0, 'rebuild/ (outside rebuild/ops/) differs from the candidate'
database = 'quillmd_qa_diag_notes_' + args.tag
walk_out = args.runtime / ('walk-' + args.tag)
assert not walk_out.exists(), 'choose a new tag: every first result is preserved'
state = args.runtime / ('walk-state-' + args.tag)
env = {'PATH': '/usr/bin:/bin', 'QUILLMD_ENV_MANAGED': '1', 'PYTHONDONTWRITEBYTECODE': '1',
       'QUILLMD_SECRET_KEY': 'synthetic-offline-notes-walk-only', 'QUILLMD_DATA_MODE': 'synthetic',
       'QUILLMD_AI_MODE': 'fixture', 'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55731',
       'QUILLMD_DB_USER': 'quillmd_qa', 'QUILLMD_DB_PASSWORD': PASSWORD.read_text().strip(),
       'QUILLMD_DB_NAME': 'postgres', 'DIAG_TEST_DB': database, 'QUILLMD_STATE_DIR': str(state), 'TMPDIR': '/tmp',
       'DJANGO_SETTINGS_MODULE': 'app_path_settings', 'PYTHONPATH': str(HERE), 'NOTES_DIR': str(HERE),
       'NOTES_OBSERVATIONS': str(args.observations), 'NOTES_WALK_OUT': str(walk_out)}
files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', 'rebuild'],
                                cwd=ROOT, text=True).splitlines()
before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files if (ROOT / p).is_file()}
started = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
args.runtime.mkdir(parents=True, exist_ok=True)
log = args.runtime / ('walk-' + args.tag + '.log')
with log.open('x') as output:
    result = subprocess.run([str(PYTHON), '-B', 'manage.py', 'test', '--noinput', '--verbosity', '2',
                             *(args.labels or ['app_path_walk'])],
                            cwd=ROOT / 'rebuild', env=env, stdout=output, stderr=subprocess.STDOUT, timeout=3600)
walks = {p.stem: json.loads(p.read_text()) for p in sorted(walk_out.glob('*.json'))} if walk_out.exists() else {}
disagree = [{'walk': k, 'field': f} for k, v in walks.items()
            for f, ok in (v.get('agrees_with_generation_layer_replay') or {}).items() if ok is False]
summary = {'walks': len(walks), 'workflow_success': sum(1 for v in walks.values() if v.get('workflow_success')),
           'failure_boundaries': {k: v['failure_boundary'] for k, v in walks.items() if v.get('failure_boundary')},
           'exceptions': {k: v['exception'] for k, v in walks.items() if v.get('exception')},
           'mapping_equals_cases_json': sum(1 for v in walks.values() if v.get('mapping_equals_cases_json')),
           'fields_compared_with_replay': sum(1 for v in walks.values()
                                              for ok in (v.get('agrees_with_generation_layer_replay') or {}).values()
                                              if ok is not None),
           'fields_disagreeing_with_replay': disagree}
record = {'schema': 'quillmd-sonnet5-notes-app-path-walk/1', 'started_at': started,
          'completed_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
          'head': head, 'rebuild_equals_candidate': engine_diff == 0,
          'rebuild_compared': 'rebuild/ outside rebuild/ops/ (the campaign runner)', 'test_database': database,
          'database_server': '127.0.0.1:55731 (campaign QA PostgreSQL)', 'exit_code': result.returncode,
          'harness_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (HERE / 'app_path_walk.py', HERE / 'app_path_steps.py', HERE / 'app_path_settings.py',
                                       Path(__file__))},
          'cases_sha256': hashlib.sha256((HERE / 'cases.json').read_bytes()).hexdigest(),
          'observations_sha256': hashlib.sha256(args.observations.read_bytes()).hexdigest() if args.observations.exists() else None,
          'provider': 'mocked (anthropic.Anthropic patched to return each case\'s reference selection); Python sockets denied',
          'source_unchanged': all((ROOT / p).is_file() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == d
                                  for p, d in before.items()),
          'summary': summary, 'walks': walks}
args.out.write_text(json.dumps(record, indent=1, ensure_ascii=False) + '\n')
print(json.dumps({k: record[k] for k in ('exit_code', 'test_database', 'source_unchanged', 'summary')}, indent=1))
print('\n'.join(log.read_text().splitlines()[-8:]))
assert record['source_unchanged'], 'source changed during the walk'
raise SystemExit(0 if result.returncode == 0 else 1)
