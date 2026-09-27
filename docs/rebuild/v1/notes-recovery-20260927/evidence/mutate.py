"""Mutation proofs for the round-3 repair: each mutant applied (asserted: anchor count 1, new text present, sha changed),
the suite run under a deadline, generation.py restored in `finally`, and the restore proved by sha256 per mutant.
Baseline (unmutated) first: a failing baseline makes every kill vacuous.
usage: mutate.py BATCH.py [test,labels] [M01,M02]"""
import hashlib, json, os, re, subprocess, sys, time
ROOT = '/opt/meddoc-pro/.worktrees/v1-notes/rebuild'
GEN = ROOT + '/core/generation.py'
ENV = dict(os.environ)
for line in open('/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/env/notes-testenv.sh'):
    m = re.match(r'export (\w+)=(.*)$', line.strip())
    if m: ENV[m.group(1)] = m.group(2)
ENV['PYTHONPATH'] = '.'
BATCH = sys.argv[1]
LABELS = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else ['core.tests.test_v3_ordinary_notes']
ONLY = set(sys.argv[3].split(',')) if len(sys.argv) > 3 and sys.argv[3] else None
def lines_with(src, needle, count=1):
    """The exact source line(s) holding `needle` (with their newlines), `count` consecutive lines from the first."""
    found = [i for i, l in enumerate(src.splitlines(True)) if needle in l]
    assert len(found) == 1, (needle, len(found))
    return ''.join(src.splitlines(True)[found[0]:found[0] + count])
M = {'SRC': open(GEN).read(), 'HEAD_SRC': open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generation-1d66c798.py')).read(),
     'lines_with': lines_with}
exec(open(BATCH).read(), M)
M = M['MUTANTS']

def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()

def run_suite(labels):
    started = time.monotonic()
    try:
        done = subprocess.run(['.venv/bin/python', 'manage.py', 'test', *labels, '--noinput'], cwd=ROOT, env=ENV,
                              capture_output=True, text=True, timeout=1200)
    except subprocess.TimeoutExpired:
        return 'TIMEOUT', time.monotonic() - started, ''
    out = done.stdout + done.stderr
    ran = re.search(r'Ran (\d+) tests?', out)
    fails = re.search(r'FAILED \(([^)]*)\)', out)
    status = 'OK' if (done.returncode == 0 and re.search(r'^OK', out, re.M)) else 'FAILED'
    first = [re.sub(r'\(core\.tests[^)]*\)', '', l) for l in out.splitlines() if l.startswith(('FAIL:', 'ERROR:'))][:3]
    return status, time.monotonic() - started, (ran.group(1) if ran else '?') + ' ' + (fails.group(1) if fails else '') + ' | ' + ' ; '.join(first)

original = open(GEN).read(); original_sha = sha(GEN)
print('batch', BATCH, 'labels', LABELS, 'sha', original_sha[:16], flush=True)
status, took, detail = run_suite(LABELS)
print(f'BASELINE {status} {took:.0f}s {detail}', flush=True)
if status != 'OK':
    sys.exit('baseline is not green: every kill would be vacuous')
rows = []
for mutant in M:
    name, edits = mutant[0], mutant[1]
    labels = mutant[2] if len(mutant) > 2 else LABELS
    if ONLY and name.split()[0] not in ONLY: continue
    try:
        text = original
        for old, new in edits:
            count = text.count(old)
            assert count == 1, f'{name}: anchor count {count} for {old[:60]!r}'
            text = text.replace(old, new)
        open(GEN, 'w').write(text)
        now = open(GEN).read()
        applied = all(new in now for _, new in edits) and sha(GEN) != original_sha
        print(f'  {name.split()[0]} mutation applied: {applied}', flush=True)
        assert applied, f'{name}: mutation not applied'
        status, took, detail = run_suite(labels)
    finally:
        open(GEN, 'w').write(original)
    restored = sha(GEN) == original_sha
    verdict = 'KILLED' if status in ('FAILED', 'TIMEOUT') else 'SURVIVED'
    rows.append((name, verdict, status, restored, round(took), detail))
    print(f'{name:70.70} {verdict:8} restored={restored} {took:.0f}s {detail[:260]}', flush=True)
    if not restored: sys.exit('RESTORE FAILED')
json.dump(rows, open(os.path.join(os.path.dirname(BATCH), 'mutants-%s-%s.json' % (os.path.basename(BATCH)[:-3], time.strftime('%H%M%S'))), 'w'), indent=1)
print('final sha', sha(GEN)[:16], 'equal', sha(GEN) == original_sha)
