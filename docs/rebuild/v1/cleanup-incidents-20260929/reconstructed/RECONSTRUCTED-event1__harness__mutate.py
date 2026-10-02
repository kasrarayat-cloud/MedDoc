"""Scratch mutation harness: apply one mutant (asserting exactly one occurrence), run the named tests, restore, prove the
restore by sha256. Usage: mutate.py <spec.json>; the spec is a list of {id, file, old, new, tests[]} objects."""
import hashlib, json, subprocess, sys, pathlib
ROOT = pathlib.Path('/opt/meddoc-pro/.worktrees/v1-residuals/rebuild')
RUN = str(pathlib.Path(__file__).with_name('run.sh'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
results = []
for m in json.load(open(sys.argv[1])):
    path = ROOT / m['file']
    original = path.read_bytes(); before = sha(path)
    text = original.decode()
    count = text.count(m['old'])
    print(f"[{m['id']}] expected 1 / measured {count}", flush=True)
    if count != 1:
        results.append({'id': m['id'], 'applied': False, 'error': f'anchor count {count}'}); continue
    try:
        path.write_text(text.replace(m['old'], m['new']))
        applied = m['new'] in path.read_text() and sha(path) != before
        print(f"[{m['id']}] mutation applied: {applied}", flush=True)
        if not applied:
            results.append({'id': m['id'], 'applied': False}); continue
        proc = subprocess.run([RUN, str(ROOT), 'test', *m['tests'], '--noinput', '--keepdb'], capture_output=True, text=True, timeout=1200)
        out = proc.stdout + proc.stderr
        summary = [l for l in out.splitlines() if l.startswith(('Ran ', 'OK', 'FAILED'))]
        failing = sorted({l.split(' (')[0].replace('FAIL: ', '').replace('ERROR: ', '') for l in out.splitlines() if l.startswith(('FAIL: ', 'ERROR: '))})
        results.append({'id': m['id'], 'applied': True, 'exit': proc.returncode, 'summary': summary, 'failing': failing,
                        'killed': proc.returncode != 0})
    finally:
        path.write_bytes(original)
        after = sha(path)
        print(f"[{m['id']}] restored: {after == before} (sha256 {before[:16]}… before, {after[:16]}… after)", flush=True)
        results[-1]['restored_sha256_equal'] = after == before
        results[-1]['sha256'] = before
        assert after == before, 'restore failed'
print(json.dumps(results, indent=1))
