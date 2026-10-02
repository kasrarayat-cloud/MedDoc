"""RR-MONEY-1: a committed rates-only edit of the declaration, under unchanged pinned USD limits."""
import io, json, os, re, shutil, subprocess, sys, tempfile, hashlib
from decimal import Decimal
from pathlib import Path
TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / 'rebuild'))
from ops import provider_campaign as pc

GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic',
       '-c', 'user.email=synthetic@test.invalid']
def git(root, *a): return subprocess.run([*GIT, '-C', str(root), *a], capture_output=True, check=True).stdout.decode().strip()

work = Path(tempfile.mkdtemp(prefix='rr-money1-', dir=os.environ.get('SCRATCH')))
repo = work / 'repo'; repo.mkdir()
git(repo, 'init', '-q')
folder = repo / 'docs/foundation/mutations'; folder.mkdir(parents=True)
real = (TREE / 'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md').read_bytes()
print('real declaration sha256', hashlib.sha256(real).hexdigest())
path = folder / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
path.write_bytes(real)
git(repo, 'add', '-A'); git(repo, 'commit', '-q', '-m', 'declaration')
commit_a = git(repo, 'rev-parse', 'HEAD')
d0 = pc.declared(path, repository=repo, out=io.StringIO())
print('d0 sha', d0.sha256, 'rates', d0.rates)

root = work / 'root'; root.mkdir()
led = pc.private_directory(root / 'ledger')
ATTEMPT = {'authority_id': d0.authority_id, 'campaign': d0.campaign, 'declaration_commit': commit_a,
           'declaration_sha256': d0.sha256, 'maximum_cost': '0.104896', 'number': 1, 'stage': 'model_check',
           'rates': {'cached': '0.20', 'input': '2', 'output': '10'}, 'runner_commit': '231183b3dc81b9b1566384440158075148ba0a8b',
           'started_at': '2026-09-29T00:56:53+00:00'}
OUTCOME = {'class': 'completed', 'number': 1, 'usage': {'cache_creation': {'ephemeral_1h_input_tokens': 0, 'ephemeral_5m_input_tokens': 0},
           'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0, 'inference_geo': 'global', 'input_tokens': 840, 'output_tokens': 118}}
pc.write_new(led / '001-attempt.json', ATTEMPT)
pc.write_new(led / '001-outcome.json', OUTCOME)
pc.write_new(led / 'stage-model_check-passed.json', {'stage': 'model_check', 'decision': 'passed', 'attempt': 1})

# the ONE edit: the rates line (and the pricing_version hashes the application would compute for them)
text = real.decode()
assert text.count('rates: input 2 output 10 cached 0.20 (USD per million tokens)') == 1
edited = text.replace('rates: input 2 output 10 cached 0.20 (USD per million tokens)',
                      'rates: input 0.02 output 0.10 cached 0.002 (USD per million tokens)')
n1 = edited.count('8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d'); n2 = edited.count('eb280d15cbfc2cf52477c57040c3ff11d60352aac5d9a9894bdae4e6a0594180')
print('pricing hash occurrences', n1, n2)
edited = edited.replace('8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d', '1' * 64)
edited = edited.replace('eb280d15cbfc2cf52477c57040c3ff11d60352aac5d9a9894bdae4e6a0594180', '2' * 64)
path.write_text(edited)
diff = git(repo, 'diff', '--stat'); print('diff:', diff)
limit_lines_changed = [l for l in git(repo, 'diff', '-U0').splitlines() if l.startswith(('+', '-')) and ('limit' in l or 'stage:' in l)]
print('limit lines changed:', limit_lines_changed)
git(repo, 'commit', '-q', '-am', 'rates edit'); commit_b = git(repo, 'rev-parse', 'HEAD')
d1 = pc.declared(path, repository=repo, out=io.StringIO())
print('edited declaration accepted by declared():', d1.rates, 'limits', d1.total_limit, [(s.id, s.limit) for s in d1.stages])

c = pc.Campaign(d1, root); c.ledger.acquire()
pinned = pc.Campaign(d0, root).limits().record()
print('limits() == pinned limits:', c.limits().record() == pinned, c.limits().record()['stages']['mapping'])
admitted = 0
for n in range(2, 12):
    bound = c.admit('mapping', '0.12')
    rec = {'number': n, 'campaign': d1.campaign, 'authority_id': d1.authority_id, 'stage': 'mapping', 'maximum_cost': '0.12',
           'exposure_bound': format(bound, 'f'), 'rates': d1.rates.as_dict(), 'declaration_sha256': d1.sha256,
           'declaration_commit': commit_b, 'limits': c.limits().record(), 'runner_commit': 'f' * 40, 'started_at': pc.now()}
    c.ledger.write_attempt(rec)
    c.ledger.write_outcome(n, {'class': 'completed', 'usage': {'input_tokens': 1000000, 'output_tokens': 1000000,
                                                                'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0,
                                                                'inference_geo': 'global'}})
    admitted += 1
print('mapping requests admitted:', admitted)
t = c.totals('mapping'); print('ledger mapping exposure:', t['exposure'])
same_usage_at_original_rates = sum(pc.usage_cost({'input_tokens': 1000000, 'output_tokens': 1000000, 'inference_geo': 'global'}, d0.rates) for _ in range(admitted))
print('the same usage at the rates in force at ledger start:', same_usage_at_original_rates, 'vs mapping limit', c.limits().stage('mapping').limit)
print('11th admit:', c.admit('mapping', '0.12'))
c.ledger.release()

# control: the original declaration, the same $12 requests (maximum at original rates = 12.00)
root2 = work / 'root2'; shutil.copytree(root / 'ledger', root2 / 'ledger', ignore=shutil.ignore_patterns('0[0-9][0-9]-*', 'runner.lock'))
for name in ('001-attempt.json', '001-outcome.json'):
    shutil.copy(led / name, root2 / 'ledger' / name)
os.chmod(root2 / 'ledger', 0o700)
print('control ledger:', sorted(os.listdir(root2 / 'ledger')))
c0 = pc.Campaign(d0, root2); c0.ledger.acquire()
b = c0.admit('mapping', '12.00'); print('control first admit', b)
c0.ledger.write_attempt({'number': 2, 'campaign': d0.campaign, 'authority_id': d0.authority_id, 'stage': 'mapping', 'maximum_cost': '12.00',
                         'rates': d0.rates.as_dict(), 'declaration_sha256': d0.sha256, 'declaration_commit': commit_a,
                         'limits': c0.limits().record(), 'started_at': pc.now()})
c0.ledger.write_outcome(2, {'class': 'completed', 'usage': {'input_tokens': 1000000, 'output_tokens': 1000000, 'inference_geo': 'global'}})
try:
    print('control second admit', c0.admit('mapping', '12.00'))
except pc.Refused as r:
    print('control second admit REFUSED:', r)
c0.ledger.release()
shutil.rmtree(work)
