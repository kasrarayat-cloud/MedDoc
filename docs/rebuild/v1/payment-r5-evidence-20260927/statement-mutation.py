"""One finite statement-trigger admission mutant; scratch copy only, restore asserted."""
import hashlib
import subprocess
import sys
from pathlib import Path

root = Path('/opt/meddoc-pro/.worktrees/v1-blockers/rebuild')
scratch = Path(__file__).resolve().parent
source = root/'core/billing.py'
original = source.read_bytes()
digest = hashlib.sha256(original).hexdigest()
target = scratch/'billing-copy.py'
label = ('core.tests.test_v1_payment_refutation_r5.GuardDefinitionPins.'
         'test_extra_before_and_after_statement_triggers_are_reported_without_printing_their_names')

def run(name):
    result = subprocess.run([sys.executable, '-B', str(scratch/'mutation-tests.py'), label],
                            cwd=root, capture_output=True, text=True, timeout=180)
    output = result.stdout+'\n'+result.stderr
    (scratch/(name+'.txt')).write_text(output)
    return result.returncode, output

target.write_bytes(original)
try:
    code, output = run('statement-mutation-baseline')
    assert code == 0, output
    print('baseline pass:', True, flush=True)
    old = '        if statements: failed.append('
    assert original.decode().count(old) == 1
    changed = original.decode().replace(old, '        if False: failed.append(')
    target.write_text(changed)
    assert target.read_text() == changed and target.read_bytes() != original
    code, output = run('statement-mutant')
    killed = code != 0 and 'FAIL:' in output and 'FAILED (failures=6)' in output and 'ERROR:' not in output
    print('applied:', True, 'killed:', killed, 'exit:', code, flush=True)
    assert killed, output
finally:
    target.write_bytes(original)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    print('scratch restored; worktree untouched:', digest, flush=True)
