"""Exact candidate, existing offline originals, isolated real fixture workflows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import sys

from run_dev_application_gate import database_presence

BASE = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/word')
WRAPPER = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/independent-product-20261003T183045Z/integration/qa_test_with_artifacts.py')
SOURCE = None
PY = '/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python'
ORIGINAL = BASE / 'development_renderer_numeric_autoruled_archive_v3.py'
HISTORICAL = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/word/development_renderer_workflow_v2.py')
ORIGINAL_SHA = '29a9a174e6e33f086513490091945907120eed190fe73ea7966facce0a4fc760'
HISTORICAL_SHA = '20473e634375e9da023447015ed617385b46895e2992f1a8e27e81a944c13353'


def write(path, value):
    with path.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
    path.chmod(0o600)


def main():
    if sys.executable != PY:
        os.execv(PY, [PY, '-B', str(Path(__file__).resolve()), *sys.argv[1:]])
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('commit')
    args = parser.parse_args()
    global SOURCE
    SOURCE = args.source.resolve()
    commit = args.commit
    assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit)
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA
    assert hashlib.sha256(HISTORICAL.read_bytes()).hexdigest() == HISTORICAL_SHA
    out = BASE / ('numeric-autoruled-archived-original-word-' + commit[:12] + '-' + str(time.time_ns()))
    out.mkdir(mode=0o700)

    def proof():
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE).decode().strip() == commit
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE).strip()
        assert not (SOURCE / 'rebuild/.env').exists()
        paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, 'rebuild'], cwd=SOURCE).decode().splitlines()
        expected = {}
        for name in paths:
            if not name.endswith('.py'):
                continue
            original = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=SOURCE)
            assert (SOURCE / name).read_bytes() == original, name
            expected[name] = hashlib.sha256(original).hexdigest()
        assert expected
        return expected

    started = time.monotonic()
    before = proof()
    database_name = 'quillmd_qa_sol_word_autoruled1004'
    database_before = database_presence(SOURCE, database_name)
    write(out / 'database-before.json', database_before)
    assert database_before['all_absent'], 'Prospective task database exists; no process launched'
    write(out / 'source-before.json', before)
    socket_dir = Path('/tmp') / ('quillmd-independent-product-' + str(os.getpid()))
    socket_dir.mkdir(mode=0o700)
    socket_path = socket_dir / 'layout.sock'
    assert len(str(socket_path).encode()) < 108
    assert not socket_path.exists()
    source = ORIGINAL.read_text().replace('ROOT=Path('+repr(str(BASE))+')', 'ROOT=Path('+repr(str(out))+')')
    source = source.replace("QUILLMD_LAYOUT_SOCKET=str(ROOT/'e.sock')", 'QUILLMD_LAYOUT_SOCKET='+repr(str(socket_path)))
    workflow = out / 'workflow.py'
    with workflow.open('x') as f:
        f.write(source)
    workflow.chmod(0o600)
    write(out / 'harness-provenance.json', {'candidate': commit, 'original_harness': str(ORIGINAL),
        'original_sha256': ORIGINAL_SHA, 'derived_sha256': hashlib.sha256(workflow.read_bytes()).hexdigest(),
        'changes': ['Fresh exclusive output directory and owned socket', 'Retain initial D10 import before assertions', 'Reuse only exact freshly compiled complete automatic A198; otherwise retain the original explicit manual recovery', 'All fixed scoring, answers, numeric/Other corrections and archive-before-assertion behavior remain unchanged'],
        'historical_harness': str(HISTORICAL), 'historical_sha256': HISTORICAL_SHA,
        'changes_from_historical': ['Archive actual final export/hash/mapping/reviewed answers before readback assertions; previous raw-export-loss limitation retained', 'Use exact source-prefix/added-visible-plain-paragraph readback for cell_append only; generic constrained scalar contract unchanged', 'Explicit original numeric-band human labels and numbered-part review through actual v3_save/v3_add; automatic GT198 score retained before all manual corrections', 'Actual simultaneous numeric readback and slash/caption/neighbor preservation; no automatic clinical association inferred', 'Retain unchanged first imports and historical count assertion as evidence', 'Score actual automatic and manually reviewed maps against immutable original ground truth', 'Use D10 actual A198 complete ruled destination and D30 A20 complete eight-option group through mapping POST', 'Preserve first provider-shaped fixture answers; explicit clinician corrections separate', 'Select only original D10 method, preserve all original inputs and prior a7 D10/D30 results', 'Explicit clinician corrections at A191/A194/A196; verify actual original caption, neighbor, part preservation and complete answer readback', 'Keep fixed original A92/A96 ground-truth match and layout holds; exercise qualified Palpable destinations only with explicit clinician answers and actual option readback'],
        'expected_groundtruth_denominators_unchanged': True, 'provider_calls_authorized': 0})
    log = (out / 'renderer.log').open('xb')
    server = subprocess.Popen([PY, '-I', '-B', str(SOURCE / 'rebuild/documents/layout_server.py'),
        '--socket', str(socket_path), '--client-uid', str(os.getuid()), '--evidence', str(out / 'layout-evidence')],
        cwd=SOURCE / 'rebuild', env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC'},
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    write(out / 'renderer-identity.json', {'pid': server.pid, 'argv': server.args, 'candidate': commit,
        'deadline_seconds': 1200, 'owned_socket': str(socket_path)})
    result = None
    try:
        while not socket_path.exists():
            assert server.poll() is None and time.monotonic() - started < 15
            time.sleep(0.1)
        command = ['python3', '-B', str(WRAPPER), str(SOURCE),
            'quillmd_qa_sol_word_autoruled1004', str(out / 'qa'), 'manage.py', 'shell', '-c',
            'import runpy; runpy.run_path(' + repr(str(workflow)) + ")"]
        print('retained workflow evidence: ' + str(out), flush=True)
        timed_out = False
        with (out / 'workflow.log').open('xb') as child_log:
            result = subprocess.Popen(command, cwd=SOURCE, stdout=child_log, stderr=subprocess.STDOUT, start_new_session=True)
            try: result.wait(timeout=max(1, 1200 - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                timed_out = True; os.killpg(result.pid, signal.SIGTERM)
                try: result.wait(timeout=10)
                except subprocess.TimeoutExpired: os.killpg(result.pid, signal.SIGKILL); result.wait(timeout=10)
        write(out / 'result.json', {'candidate': commit, 'exit_code': result.returncode, 'timed_out': timed_out,
            'elapsed_seconds': round(time.monotonic() - started, 3), 'provider_calls': 0,
            'scope': 'Original eligible offline D10; actual fixture HTTP/worker/review/finalization/export; explicit manual corrections, no broad, live-model or native Word acceptance.'})
        print((out / 'workflow.log').read_text()[-7000:], flush=True)
    finally:
        if server.poll() is None:
            server.send_signal(signal.SIGINT)
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGKILL)
                server.wait(timeout=5)
        log.close()
        write(out / 'renderer-exit.json', {'returncode': server.returncode, 'socket_removed': not socket_path.exists()})
        try:
            database_after = database_presence(SOURCE, database_name)
        except Exception as error:
            database_after = {'verified': False, 'all_absent': False, 'error_type': type(error).__name__}
        write(out / 'database-after.json', database_after)
        after = proof()
        assert before == after
        write(out / 'source-after.json', after)
    raise SystemExit(result.returncode if result and database_after['all_absent'] else 2)


if __name__ == '__main__':
    main()
