"""F1-unreadable-archive / F2-compressed-content / F3-manifest-opens-env: the REAL sonnet5_qa._decide on a temporary root."""
import io, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
TREE = Path(sys.argv[1]); MODE = sys.argv[2]
sys.path.insert(0, str(TREE / 'rebuild')); sys.path.insert(0, str(Path(__file__).parent))
from ops import provider_campaign as pc
from ops import sonnet5_qa as sq
import archives
KEY = archives.KEY
GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic',
       '-c', 'user.email=synthetic@test.invalid']
def git(root, *a): return subprocess.run([*GIT, '-C', str(root), *a], capture_output=True, check=True).stdout.decode().strip()

work = Path(tempfile.mkdtemp(prefix=f'rr-decide-{MODE}-', dir=os.environ.get('SCRATCH')))
repo = work / 'repo'; repo.mkdir(); git(repo, 'init', '-q')
decl = repo / 'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md'; decl.parent.mkdir(parents=True)
decl.write_bytes((TREE / 'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md').read_bytes())
(repo / 'rebuild/ops').mkdir(parents=True); (repo / 'rebuild/ops/runner.py').write_text('v = 1\n')
git(repo, 'add', '-A'); git(repo, 'commit', '-q', '-m', 'A'); A = git(repo, 'rev-parse', 'HEAD')
import dataclasses
root = work / 'root'; root.mkdir(mode=0o700)
cred = pc.private_directory(root / 'credential') / 'anthropic-api-key'; cred.write_text(KEY + '\n'); os.chmod(cred, 0o600)
d = dataclasses.replace(pc.declared(decl, repository=repo, out=io.StringIO()), credential_file=str(cred))
c = pc.Campaign(d, root); c.ledger.acquire()
attempt = {'number': 1, 'campaign': d.campaign, 'authority_id': d.authority_id, 'stage': 'model_check', 'maximum_cost': '0.104896',
           'rates': d.rates.as_dict(), 'limits': d.limits().record(), 'runner_commit': A, 'started_at': pc.now()}
c.ledger.write_attempt(attempt)
c.ledger.write_outcome(1, {'class': 'completed', 'usage': {'input_tokens': 840, 'output_tokens': 118, 'inference_geo': 'global'}})
evidence = pc.private_directory(root / 'evidence' / '001'); pc.private_directory(evidence / 'case')
form = sq.build_form()
for name in sq.RETAINED_EVIDENCE:
    data = form if name.endswith('.docx') else b'{"synthetic": true}\n'
    (evidence / name).write_bytes(data)

opened_env = []
if MODE == 'deflate':
    data, err = archives.corrupt_deflate(); print('reading the member raises', type(err).__module__, type(err).__name__, err)
    (evidence / 'export.docx').write_bytes(data)
elif MODE == 'lzma':
    data, err = archives.corrupt_lzma(); print('reading the member raises', type(err).__name__, err)
    (evidence / 'export.docx').write_bytes(data)
elif MODE == 'utf8':
    (evidence / 'export.docx').write_bytes(archives.bad_utf8_name())
elif MODE == 'fifo':
    os.mkfifo(evidence / 'stray.fifo')
elif MODE == 'nested':
    (evidence / 'export.docx').write_bytes(archives.nested_docx(form))
elif MODE == 'gzip':
    (evidence / 'provider-result.json').write_bytes(archives.gz())
elif MODE == 'env':
    # a file NAMED .env with synthetic, empty content; the audit hook BLOCKS every open of an env-named path and records it,
    # so the file is never actually opened by anyone
    (evidence / '.env').touch(mode=0o600)
    class EnvOpenBlocked(Exception): pass
    def hook(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            p = os.fsdecode(args[0])
            if any(pc.env_name(part) for part in Path(p).parts):
                import traceback
                opened_env.append((p, [f'{f.name}:{f.lineno}' for f in traceback.extract_stack()[-6:-1]]))
                raise EnvOpenBlocked(p)
    sys.addaudithook(hook)

if MODE in ('deflate', 'lzma', 'utf8', 'fifo', 'nested', 'gzip'):
    try:
        print('leaked() ->', pc.leaked(root, KEY, exclude=(str(cred),)))
    except BaseException as e:
        print('leaked() raises', type(e).__module__ + '.' + type(e).__name__, 'is Refused:', isinstance(e, pc.Refused), '|', str(e)[:120])

result = None
try:
    result = sq._decide(c, attempt, evidence, KEY, [], {'stage': 'model_check', 'attempt': 1}, {'runner_commit': A}, {})
    print('_decide returned verdict', result['verdict'], 'reasons', result['reasons'])
except BaseException as error:
    print('_decide RAISED', type(error).__module__ + '.' + type(error).__name__, '| is Refused:', isinstance(error, pc.Refused))
    sq._record_interruption(c.ledger, attempt, error)        # (what run_model_check's except BaseException does)
print('ledger files:', sorted(n for n in os.listdir(c.ledger.dir) if n != 'runner.lock'))
print('campaign_stop():', c.ledger.campaign_stop())
st = c.ledger.stage_record('model_check', 'passed')
if st: print('passed checks:', st['checks'])
if opened_env:
    print('ENV-NAMED OPEN ATTEMPTS (blocked):', opened_env)
    m = evidence / 'manifest.json'
    print('manifest.json exists:', m.exists())
# reopen: after a repair and a committed diagnosis
if c.ledger.stage_state('model_check')['state'] == 'failed':
    (repo / 'rebuild/ops/runner.py').write_text('v = 2\n'); git(repo, 'commit', '-q', '-am', 'repair'); B = git(repo, 'rev-parse', 'HEAD')
    diag = repo / 'docs/rebuild/diagnosis-1.md'; diag.parent.mkdir(parents=True, exist_ok=True)
    diag.write_text(f'reopen_stage: model_check\nfailed_attempts: 1\nrepair_commit: {B}\n')
    git(repo, 'add', '-A'); git(repo, 'commit', '-q', '-m', 'diag'); C = git(repo, 'rev-parse', 'HEAD')
    try:
        rec = c.reopen('model_check', diag, runner_commit=C)
        print('reopen WROTE stage-model_check-reopened-%d.json' % rec['number'])
    except pc.Refused as r:
        print('reopen REFUSED:', r)
c.ledger.release()
shutil.rmtree(work, ignore_errors=True)
