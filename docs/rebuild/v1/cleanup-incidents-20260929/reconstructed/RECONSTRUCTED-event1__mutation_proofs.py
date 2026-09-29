"""Mutation proofs: baseline green first; each mutant applied (anchor asserted exactly once, marker read back), the
targeted tests run and MUST fail, the file restored from its saved bytes and the restore verified by sha256."""
import hashlib, os, subprocess, sys
from pathlib import Path

REBUILD = Path('/opt/meddoc-pro/.worktrees/v1-sonnet5-campaign/rebuild')
PY = str(REBUILD / '.venv/bin/python')
PLAIN = {'PATH': '/usr/bin:/bin', 'HOME': os.environ['HOME'], 'TMPDIR': '/tmp', 'LANG': 'C.UTF-8'}
QA = dict(os.environ)          # the sourced QA test environment (password read from its file by the caller)

def unit(*tests):
    return ([PY, '-B', '-m', 'unittest', *tests], PLAIN)

def django(*tests):
    return ([PY, '-B', 'manage.py', 'test', '--noinput', *tests], QA)

P = 'ops.tests.test_provider_campaign.'
Q = 'ops.tests.test_sonnet5_qa.ModelCheckTests.'
MUTANTS = [
    ('admission: stage limit', 'ops/provider_campaign.py',
     "        require(spent + bound <= stage.limit,\n", "        require(True or spent + bound <= stage.limit,\n",
     unit(P + 'AdmissionTests.test_over_the_stage_cap_is_refused')),
    ('admission: total limit', 'ops/provider_campaign.py',
     "        require(total + bound <= declaration.total_limit,\n", "        require(True or total + bound <= declaration.total_limit,\n",
     unit(P + 'AdmissionTests.test_over_the_total_cap_is_refused_even_when_the_stage_fits')),
    ('admission: request count', 'ops/provider_campaign.py',
     "            require(len(here) + 1 <= stage.max_requests,", "            require(True or len(here) + 1 <= stage.max_requests,",
     unit(P + 'AdmissionTests.test_over_the_stage_request_count_is_refused')),
    ('admission: open attempt', 'ops/provider_campaign.py',
     "        require(all(outcome is not None for _, outcome in rows), 'An attempt has no outcome; reconcile before admitting.')\n",
     "        require(True or all(outcome is not None for _, outcome in rows), 'An attempt has no outcome; reconcile before admitting.')\n",
     unit(P + 'AdmissionTests.test_an_open_attempt_is_refused')),
    ('admission: prerequisite', 'ops/provider_campaign.py',
     "            require('passed' in records.get(stage.requires, {}),", "            require(True or 'passed' in records.get(stage.requires, {}),",
     unit(P + 'AdmissionTests.test_a_stage_before_its_prerequisite_passed_is_refused')),
    ('served model check', 'ops/sonnet5_qa.py',
     "    if outcome['served_model'] != declaration.model:\n", "    if False and outcome['served_model'] != declaration.model:\n",
     django(Q + 'test_a_wrong_served_model_stops_the_campaign')),
    ('.env refusal: credential path', 'ops/provider_campaign.py',
     "            require(not env_name(part.name), 'An environment file is never read.')\n",
     "            require(True or not env_name(part.name), 'An environment file is never read.')\n",
     unit(P + 'CredentialTests.test_an_env_path_is_refused_before_anything_is_opened')),
    ('.env refusal: checkout rebuild/.env', 'ops/sonnet5_qa.py',
     "    require(not env_file_present(rebuild), 'The candidate checkout has a rebuild/.env; the campaign never runs beside one.')\n",
     "    require(True or not env_file_present(rebuild), 'The candidate checkout has a rebuild/.env; the campaign never runs beside one.')\n",
     django(Q + 'test_a_checkout_with_an_env_file_refuses_before_any_send')),
]

def run(command):
    argv, env = command
    return subprocess.run(argv, cwd=REBUILD, env=env, capture_output=True, text=True, timeout=600)

def verdict(result):
    tail = [line for line in (result.stdout + result.stderr).splitlines() if line.startswith(('Ran ', 'OK', 'FAILED'))]
    return result.returncode, ' | '.join(tail)

ok = True
print('BASELINE (unmutated, every targeted test must pass):')
for name, path, old, new, command in MUTANTS:
    code, summary = verdict(run(command))
    print(f'  {name}: exit {code} :: {summary}')
    ok &= code == 0
if not ok:
    sys.exit('baseline is not green; no mutation result is meaningful')
print('MUTANTS (each must make its targeted test FAIL):')
for name, path, old, new, command in MUTANTS:
    file = REBUILD / path
    original = file.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode()
    count = text.count(old)
    assert count == 1, f'{name}: anchor found {count} times (expected 1); nothing applied'
    try:
        file.write_text(text.replace(old, new))
        applied = new in file.read_text() and old not in file.read_text()
        print(f'  {name}: mutation applied: {applied}')
        assert applied, 'mutation did not apply; proof aborted'
        code, summary = verdict(run(command))
        killed = code != 0 and 'FAILED' in summary
        print(f'    targeted test exit {code} :: {summary} -> {"KILLED" if killed else "SURVIVED"}')
        ok &= killed
    finally:
        file.write_bytes(original)
        after = hashlib.sha256(file.read_bytes()).hexdigest()
        print(f'    restored: {after == before} (sha256 {before[:16]}… -> {after[:16]}…)')
        assert after == before, 'RESTORE FAILED'
print('ALL MUTANTS KILLED AND RESTORED' if ok else 'A MUTANT SURVIVED')
sys.exit(0 if ok else 1)
