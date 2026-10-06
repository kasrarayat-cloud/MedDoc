import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

OUT = Path(__file__).parent
WT = Path('/opt/meddoc-pro/.worktrees/v1-elicited-quality-87628551')
PY = '/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python'
paths = ['rebuild/core/generation.py', 'rebuild/core/v3_field_relations.py',
         'rebuild/core/tests/test_elicited_assertion_quality.py', 'rebuild/core/tests/test_elicited_passive_reference.py', 'rebuild/core/tests/test_elicited_proof_transport.py', 'rebuild/core/tests/test_elicited_source_reference.py']
def hashes():
    return {p: hashlib.sha256((WT / p).read_bytes()).hexdigest() for p in paths}
before = hashes()
start = time.monotonic()
timed = False
with (OUT / 'stdout-r1.log').open('wb') as stdout, (OUT / 'stderr-r1.log').open('wb') as stderr:
    child = subprocess.Popen([PY, '-B', str(OUT / 'child.py')], cwd=WT / 'rebuild',
                             stdout=stdout, stderr=stderr, start_new_session=True)
    try:
        child.wait(timeout=105)
    except subprocess.TimeoutExpired:
        timed = True
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=10)
after = hashes()
result = {'base': '876285516c1aae1607e5355640720bb902d8f367', 'writer': str(WT),
          'child_pid': child.pid, 'exit_code': child.returncode, 'timed_out': timed,
          'reaped': child.poll() is not None, 'source_before': before, 'source_after': after,
          'source_unchanged': before == after, 'elapsed_seconds': time.monotonic() - start}
(OUT / 'result-r1.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
raise SystemExit(0 if child.returncode == 0 and not timed and before == after else 1)
