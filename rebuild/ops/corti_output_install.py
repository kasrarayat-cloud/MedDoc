"""Scoped source update of the already installed synthetic HTTPS candidate.

No build, provider request, ingress edit or native service/database change.
Requires the prospectively committed ruled-mutation declaration.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import urllib.request

from ops import managed_helper

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path('/home/claude/quillmd-corti-test/workflow-runtime-20261016')
OUT = Path('/home/claude/quillmd-corti-test/bounded-output-repair-20261016/installation')
OLD = '40f78febd847b79efce3c13912d2edccc51eee16'
CANDIDATE = '/opt/quillmd-corti-candidate'
STATE = '/var/lib/private/quillmd-corti-candidate'
UNITS = ['quillmd-corti-candidate.service', 'quillmd-corti-candidate-worker.service']


def command(args, **kwargs):
    return subprocess.check_output(args, timeout=60, **kwargs)


def identities():
    return {unit: command(['systemctl', 'show', unit, '-p', 'MainPID', '-p', 'ActiveState',
                          '-p', 'ExecMainStartTimestamp']).decode()
            for unit in ['quillmd-fresh-doctor', 'quillmd-fresh-admin', 'quillmd-fresh-worker']}


def helper(code, *, writable=False):
    argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none', '--pid=host',
            '--mount', 'type=bind,src=/,dst=/host,readonly',
            '--mount', f'type=bind,src={OUT},dst=/payload,readonly']
    if writable:
        for path in [CANDIDATE, STATE, '/etc/systemd/system']:
            argv += ['--mount', f'type=bind,src={path},dst=/host{path}']
    argv += [managed_helper.IMAGE, 'python', '-B', '-']
    return managed_helper.run_helper(argv, input=code.encode(), timeout=60, failure_directory=OUT)


DB_SNAPSHOT = '''
import json
from django.db import connection
with connection.cursor() as c:
 c.execute("SET default_transaction_read_only=on")
 result={}
 for table in ['core_encounter','core_patient','core_codingrun','core_codingdecision','core_codingcontext','core_codeset','core_code','core_job']:
  c.execute("SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text,'|' ORDER BY id),'')) FROM "+table+" t")
  result[table]=c.fetchone()
 print('BOUND_SNAPSHOT='+json.dumps(result,sort_keys=True))
'''


def db_snapshot():
    raw = command(['python3', str(RUNTIME / 'run.py'), 'manage.py', 'shell', '-c', DB_SNAPSHOT]).decode()
    return json.loads(next(line.split('=', 1)[1] for line in raw.splitlines() if line.startswith('BOUND_SNAPSHOT=')))


def main():
    assert os.environ.get('RULED_MUTATION_DECLARATION') and os.environ.get('RULED_MUTATION_DECL_COMMIT')
    assert not command(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no']).strip()
    revision = command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip()
    assert len(revision) == 40 and revision != OLD
    os.umask(0o077)
    OUT.mkdir(mode=0o700)  # One-shot receipt; failures remain, no implicit retry.
    before = identities()
    ingress = hashlib.sha256(Path('/etc/nginx/sites-available/quillmd').read_bytes()).hexdigest()
    db_before = db_snapshot()
    (OUT / 'baseline.json').write_text(json.dumps({'native': before, 'ingress_sha256': ingress,
        'database': db_before, 'from_revision': OLD, 'to_revision': revision}, indent=2))
    (OUT / 'source.tar').write_bytes(command(['git', '-C', str(ROOT), 'archive', '--format=tar', revision, 'rebuild']))
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'HOME', 'USER')}
    env.update(json.loads((RUNTIME / 'environment.json').read_text()))
    assert env['QUILLMD_DB_NAME'] == 'test_quillmd_corti_workflow' and env['QUILLMD_DB_PORT'] == '55449'
    assert env['QUILLMD_AI_MODE'] == 'fixture'
    env['QUILLMD_STATE_DIR'] = str(OUT / 'static-stage')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    command([str(ROOT / 'rebuild/.venv/bin/python'), 'manage.py', 'collectstatic', '--noinput', '--verbosity', '0'],
            cwd=ROOT / 'rebuild', env=env)
    with tarfile.open(OUT / 'static.tar', 'w') as target:
        target.add(OUT / 'static-stage/staticfiles', arcname='staticfiles')
    pre = '''import pathlib,hashlib,json
r=pathlib.Path('/host/opt/quillmd-corti-candidate'); state=pathlib.Path('/host/var/lib/private/quillmd-corti-candidate')
units=[pathlib.Path('/host/etc/systemd/system')/name for name in UNITS]
for p in units: assert 'WorkingDirectory=/opt/quillmd-corti-candidate/releases/'+OLD+'/rebuild' in p.read_text()
assert 'QUILLMD_RELEASE_SHA='+repr(OLD) in (r/'environment').read_text()
files={str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'files').rglob('*') if p.is_file()}
assert files and not (r/'releases'/REVISION).exists()
print(json.dumps(files,sort_keys=True))
'''.replace('UNITS', repr(UNITS)).replace('OLD', repr(OLD)).replace('REVISION', repr(revision))
    file_before = json.loads(helper(pre).stdout)
    (OUT / 'files-before.json').write_text(json.dumps(file_before, indent=2))
    # Only this isolated synthetic database gets the additive, append-only table.
    migration = command(['python3', str(RUNTIME / 'run.py'), 'manage.py', 'migrate', 'core',
                         '0029_bounded_output_decision', '--noinput'])
    (OUT / 'migration.txt').write_bytes(migration)
    assert db_snapshot() == db_before
    publish = '''import pathlib,os,tarfile,subprocess,hashlib,json,shutil
r=pathlib.Path('/host/opt/quillmd-corti-candidate'); state=pathlib.Path('/host/var/lib/private/quillmd-corti-candidate')
release=r/'releases'/REVISION
backup=r/'rollback'/REVISION
backup.parent.mkdir(mode=0o700,exist_ok=True);backup.mkdir(mode=0o700)
for name in UNITS: shutil.copyfile(pathlib.Path('/host/etc/systemd/system')/name,backup/name)
shutil.copyfile(r/'environment',backup/'environment');os.chmod(backup/'environment',0o600)
with tarfile.open(backup/'static-before.tar','w') as t: t.add(state/'staticfiles',arcname='staticfiles')
(backup/'complete').write_text('backups complete')
release.mkdir(mode=0o755)
with tarfile.open('/payload/source.tar') as t:
 for m in t.getmembers():
  assert (m.isfile() or m.isdir()) and not m.issym() and not m.islnk() and not m.name.startswith('/') and '..' not in pathlib.PurePosixPath(m.name).parts
 t.extractall(release,filter='data')
for p in [release,*release.rglob('*')]: os.chown(p,0,0);os.chmod(p,0o755 if p.is_dir() else 0o644)
units=[pathlib.Path('/host/etc/systemd/system')/n for n in UNITS]
old_units={p:p.read_bytes() for p in units}; ep=r/'environment'; old_env=ep.read_bytes()
for p in units: assert 'WorkingDirectory=/opt/quillmd-corti-candidate/releases/'+OLD+'/rebuild' in p.read_text()
assert old_env.count(OLD.encode())==1
# Publish static files while retaining all existing clinical and export files.
static=state/'staticfiles'; owner=static.stat()
with tarfile.open('/payload/static.tar') as t:
 for m in t.getmembers():
  assert (m.isfile() or m.isdir()) and not m.issym() and not m.islnk() and m.name.startswith('staticfiles') and '..' not in pathlib.PurePosixPath(m.name).parts
 t.extractall(state,filter='data')
for p in [static,*static.rglob('*')]: os.chown(p,owner.st_uid,owner.st_gid);os.chmod(p,0o700 if p.is_dir() else 0o600)
for p,raw in old_units.items(): p.write_bytes(raw.replace(OLD.encode(),REVISION.encode()));os.chmod(p,0o644)
ep.write_bytes(old_env.replace(OLD.encode(),REVISION.encode()));os.chmod(ep,0o600)
files={str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/'files').rglob('*') if p.is_file()}
assert files==EXPECTED_FILES
os.chroot('/host');os.chdir('/')
subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True,timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['/usr/bin/systemctl','restart',*UNITS],check=True,timeout=25,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('candidate_source_updated')
'''.replace('UNITS', repr(UNITS)).replace('OLD', repr(OLD)).replace('REVISION', repr(revision)).replace('EXPECTED_FILES', repr(file_before))
    rollback = """import pathlib,os,tarfile,subprocess,shutil
r=pathlib.Path('/host/opt/quillmd-corti-candidate');state=pathlib.Path('/host/var/lib/private/quillmd-corti-candidate')
backup=r/'rollback'/REVISION
assert (backup/'complete').exists(), 'No complete backup; inspect publication before further action.'
for name in UNITS:
 p=pathlib.Path('/host/etc/systemd/system')/name
 p.write_bytes((backup/name).read_bytes());os.chmod(p,0o644)
p=r/'environment';p.write_bytes((backup/'environment').read_bytes());os.chmod(p,0o600)
static=state/'staticfiles'
if static.exists(): shutil.rmtree(static)
with tarfile.open(backup/'static-before.tar') as t: t.extractall(state,filter='fully_trusted')
os.chroot('/host');os.chdir('/')
subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True,timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['/usr/bin/systemctl','restart',*UNITS],check=True,timeout=25,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('candidate_publication_rolled_back')
""".replace('UNITS', repr(UNITS)).replace('REVISION', repr(revision))
    health = None
    expected_health = {'status': 'ok', 'data_mode': 'synthetic-only', 'surface': 'doctor', 'release': revision}
    try:
        helper(publish, writable=True)
        for _ in range(30):
            try:
                with urllib.request.urlopen('https://app.quillmd.com/synthetic/corti/health/', timeout=3) as response:
                    health = json.load(response)
                if health == expected_health:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.25)
        assert health == expected_health, 'New candidate exact health was not confirmed.'
    except BaseException:
        # A fresh helper owns its own deadline. Restore only candidate pointers
        # and assets; retain the additive table, new release and failed evidence.
        helper(rollback, writable=True)
        (OUT / 'rollback.txt').write_text('Candidate units, environment and static assets restored; inspect retained failure.\n')
        raise
    assert identities() == before
    assert hashlib.sha256(Path('/etc/nginx/sites-available/quillmd').read_bytes()).hexdigest() == ingress
    assert db_snapshot() == db_before
    count_raw = command(['python3', str(RUNTIME / 'run.py'), 'manage.py', 'shell', '-c',
        "from core.models import CodingOutputDecision;print('OUTPUT_DECISIONS='+str(CodingOutputDecision.objects.count()))"]).decode()
    assert 'OUTPUT_DECISIONS=0' in count_raw.splitlines()
    receipt = {'installed_revision': revision, 'health': health, 'native_unchanged': True,
               'ingress_unchanged': True, 'clinical_and_original_decisions_unchanged': True,
               'historical_files_unchanged': True, 'new_provider_calls': 0, 'user_decisions_created': 0}
    (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
