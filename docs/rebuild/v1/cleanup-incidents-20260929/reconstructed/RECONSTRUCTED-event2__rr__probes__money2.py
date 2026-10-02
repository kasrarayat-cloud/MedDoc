"""RR-MONEY-2: reopen accepts an empty repair commit (no runner or engine file changes)."""
import io, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / 'rebuild'))
from ops import provider_campaign as pc
GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic',
       '-c', 'user.email=synthetic@test.invalid']
def git(root, *a): return subprocess.run([*GIT, '-C', str(root), *a], capture_output=True, check=True).stdout.decode().strip()

work = Path(tempfile.mkdtemp(prefix='rr-money2-', dir=os.environ.get('SCRATCH')))
repo = work / 'repo'; repo.mkdir(); git(repo, 'init', '-q')
decl = repo / 'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md'; decl.parent.mkdir(parents=True)
decl.write_bytes((TREE / 'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md').read_bytes())
(repo / 'rebuild/ops').mkdir(parents=True)
for name in ('provider_campaign.py', 'sonnet5_qa.py'):
    shutil.copy(TREE / 'rebuild/ops' / name, repo / 'rebuild/ops' / name)
git(repo, 'add', '-A'); git(repo, 'commit', '-q', '-m', 'A: declaration and runner'); A = git(repo, 'rev-parse', 'HEAD')
d = pc.declared(decl, repository=repo, out=io.StringIO())
root = work / 'root'; root.mkdir()
c = pc.Campaign(d, root); c.ledger.acquire()
c.ledger.write_attempt({'number': 1, 'campaign': d.campaign, 'authority_id': d.authority_id, 'stage': 'model_check',
                        'maximum_cost': '0.104896', 'rates': d.rates.as_dict(), 'limits': d.limits().record(),
                        'runner_commit': A, 'started_at': pc.now()})
c.ledger.write_outcome(1, {'class': 'uncertain'})
c.ledger.write_stage('model_check', 'failed', {'attempt': 1, 'reasons': ['synthetic']})
git(repo, 'commit', '--allow-empty', '-q', '-m', 'repair'); B = git(repo, 'rev-parse', 'HEAD')
diag = repo / 'docs/rebuild/diagnosis-1.md'; diag.parent.mkdir(parents=True)
diag.write_text(f'# Diagnosis\n\nreopen_stage: model_check\nfailed_attempts: 1\nrepair_commit: {B}\n')
git(repo, 'add', '-A'); git(repo, 'commit', '-q', '-m', 'C: diagnosis'); C = git(repo, 'rev-parse', 'HEAD')
print('repair commit touches files:', repr(git(repo, 'show', '--name-only', '--format=', B)))
print('git diff --name-only A C -- rebuild:', repr(git(repo, 'diff', '--name-only', A, C, '--', 'rebuild')))
print('rebuild tree A == C:', git(repo, 'rev-parse', f'{A}:rebuild') == git(repo, 'rev-parse', f'{C}:rebuild'))
try:
    rec = c.reopen('model_check', diag, runner_commit=C)
    print('reopen WROTE:', sorted(n for n in os.listdir(c.ledger.dir) if 'reopened' in n),
          'runner', rec['runner_commit'] == C, 'failed_runners', rec['failed_runner_commits'] == [A], 'repair', rec['repair_commit'] == B)
except pc.Refused as r:
    print('reopen REFUSED:', r)
try:
    print('admit model_check on C:', c.admit('model_check', '0.104896', runner_commit=C))
except pc.Refused as r:
    print('admit REFUSED:', r)
# control: the failed runner itself is refused
try:
    c.admit('model_check', '0.104896', runner_commit=A); print('admit on A: ADMITTED')
except pc.Refused as r:
    print('control admit on A refused:', r)
c.ledger.release(); shutil.rmtree(work)
