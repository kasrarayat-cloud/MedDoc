"""Mutation proofs for the R1 repair (ops/sonnet5_qa.py). Baseline unmutated first; each mutant: anchor count asserted,
application read back, run under a deadline, restored in `finally`, restoration asserted by sha256."""
import hashlib, os, re, signal, subprocess, sys
from pathlib import Path

TARGET = Path('/opt/meddoc-pro/.worktrees/v1-sonnet5-campaign/rebuild/ops/sonnet5_qa.py')
RUNNER = '/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/qa-test.sh'
LABELS = ['ops.tests.test_sonnet5_qa']
DEADLINE = 600

ORIGINAL_R1_BLOCK = """        problems = ['the authenticated export failed'] if response.status_code != 200 else []
        if exported and export_sha != encounter.export_sha256:
            problems.append('the export is not the finalized record\\'s export')
        if exported:
            pc.write_new(evidence / 'export.docx', exported, raw=True)
            problems += export_checks(form, exported, EXPECTED)
"""
NEW_BLOCK_RE = re.compile(r"        problems = \[\]\n        if response\.status_code != 200:\n.*?            problems \+= export_checks\(form, exported, EXPECTED\)\n", re.S)

MUTANTS = [
    ('M1 R1 shape: the original `if exported:`-guarded export block', 'regex', NEW_BLOCK_RE, ORIGINAL_R1_BLOCK),
    ('M2 no emptiness problem', 'str',
     "            if not exported:\n                problems.append('the authenticated export is empty: no export evidence was retained')\n", ''),
    ('M3 no finalized-record hash comparison', 'str',
     "            if export_sha != encounter.export_sha256:\n                problems.append('the export is not the finalized record\\'s export')\n", ''),
    ('M4 no non-200 problem', 'str',
     "            problems.append(f'the authenticated export failed ({response.status_code})')\n", "            pass\n"),
    ('M5 retained-evidence gate not applied in _decide', 'str',
     "    if not reasons:\n        # (only a stage about to pass", "    if False:\n        # (only a stage about to pass"),
    ('M6 gate ignores an empty file', 'str', "        elif info.st_size == 0:\n", "        elif False:\n"),
    ('M7 gate ignores a link / non-regular file', 'str', "        if not stat.S_ISREG(info.st_mode):\n", "        if False:\n"),
    ('M8 export.docx not in RETAINED_EVIDENCE', 'str', "'answers-reviewed.json', 'export.docx',\n", "'answers-reviewed.json',\n"),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(tag):
    proc = subprocess.Popen([RUNNER, 'quillmd_qa_repair_r1', *LABELS], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True, text=True)
    try:
        out, _ = proc.communicate(timeout=DEADLINE)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return 'TIMEOUT', [], out
    failed = re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)
    ran = re.search(r'^Ran (\d+) tests', out, re.M)
    status = 'OK' if proc.returncode == 0 else 'FAILED'
    return f'{status} rc={proc.returncode} ran={ran.group(1) if ran else "?"}', failed, out


original = TARGET.read_bytes()
original_sha = sha(original)
print('target sha256 before:', original_sha)
status, failed, out = run('baseline')
print('BASELINE (unmutated):', status, failed)
if not status.startswith('OK'):
    print(out[-3000:]); sys.exit('baseline is not green: every kill below would be vacuous')

results = []
for name, kind, anchor, replacement in MUTANTS:
    text = original.decode()
    if kind == 'regex':
        count = len(anchor.findall(text))
        assert count == 1, (name, 'anchor count', count)
        mutated = anchor.sub(lambda m: replacement, text, count=1)
    else:
        count = text.count(anchor)
        assert count == 1, (name, 'anchor count', count)
        mutated = text.replace(anchor, replacement, 1)
    assert mutated != text, name
    try:
        TARGET.write_text(mutated)
        now = TARGET.read_text()
        applied = now == mutated and sha(now.encode()) != original_sha
        print(f'\n{name}\n  mutation applied: {applied}')
        if not applied:
            results.append((name, 'NOT APPLIED')); continue
        status, failed, out = run(name)
        verdict = 'KILLED' if (status.startswith('FAILED') and failed) else ('TIMEOUT' if status == 'TIMEOUT' else 'SURVIVED')
        print(f'  run: {status}; failing tests: {failed}')
        results.append((name, verdict, failed))
    finally:
        TARGET.write_bytes(original)
        restored = sha(TARGET.read_bytes())
        print(f'  restored sha256: {restored} equal={restored == original_sha}')
        assert restored == original_sha, 'RESTORE FAILED'

print('\nSUMMARY')
for row in results:
    print(' ', row[0], '->', row[1], row[2] if len(row) > 2 else '')
print('target sha256 after:', sha(TARGET.read_bytes()), 'equal=', sha(TARGET.read_bytes()) == original_sha)
