"""One bounded installation of the retained synthetic candidate; no provider I/O.

Uses the existing ruled-mutation gate and managed root-helper primitive. The
native dashboard/source/database are not promoted or modified. No build runs.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request

from ops import managed_helper

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path('/home/claude/quillmd-corti-test/workflow-runtime-20261016')
OUT = Path('/home/claude/quillmd-corti-test/https-install-20261016')
INGRESS = Path('/etc/nginx/sites-available/quillmd')
UNIT = 'quillmd-corti-candidate.service'
RELEASE_ROOT = '/opt/quillmd-corti-candidate'
STATE = '/var/lib/quillmd-corti-candidate'
NATIVE_UNITS = ['quillmd-fresh-doctor', 'quillmd-fresh-admin', 'quillmd-fresh-worker']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(args, **kw):
    return subprocess.check_output(args, timeout=30, **kw)


def native_identity():
    return {unit: command(['systemctl', 'show', unit, '-p', 'MainPID', '-p', 'ActiveState', '-p', 'ExecMainStartTimestamp']).decode()
            for unit in NATIVE_UNITS}


def helper(source, mounts):
    argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none', '--pid=host']
    for mount in mounts:
        argv += ['--mount', mount]
    argv += [managed_helper.IMAGE, 'python', '-B', '-']
    return managed_helper.run_helper(argv, input=source.encode(), timeout=60, failure_directory=OUT)


def main():
    assert os.environ.get('RULED_MUTATION_DECLARATION') and os.environ.get('RULED_MUTATION_DECL_COMMIT')
    assert not command(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no']).strip()
    revision = command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip()
    assert len(revision) == 40
    os.umask(0o077)
    assert not OUT.exists(), 'Fresh one-shot installation receipt directory required.'
    OUT.mkdir(mode=0o700)
    before = native_identity()
    original = INGRESS.read_bytes()
    assert sha(original) == 'a6b45d31a328559d8b37de6281683ec60201c880191fef758347827edc5f73eb'
    assert original.count(b'server_name app.quillmd.com;') == 1
    assert b'/synthetic/corti' not in original
    info = INGRESS.stat()
    assert info.st_uid == info.st_gid == 0 and info.st_mode & 0o777 == 0o644
    (OUT / 'nginx-before.conf').write_bytes(original)
    os.chmod(OUT / 'nginx-before.conf', 0o600)
    base = json.loads((RUNTIME / 'environment.json').read_text())
    assert base['QUILLMD_DB_NAME'].startswith('test_') and base['QUILLMD_DB_PORT'] == '55449'
    assert base['QUILLMD_AI_MODE'] == 'fixture'
    base.update(DJANGO_SETTINGS_MODULE='ops.corti_https_settings', QUILLMD_STATE_DIR=STATE,
                QUILLMD_RELEASE_SHA=revision, QUILLMD_HTTPS='1', QUILLMD_TRUST_PROXY='1',
                PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    assert not any(k in base for k in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'CORTI_CLIENT_SECRET'])
    assert all('\n' not in v and '\r' not in v and "'" not in v for v in base.values())
    env = ''.join(k + "='" + v + "'\n" for k, v in base.items()).encode()
    archive = command(['git', '-C', str(ROOT), 'archive', '--format=tar', revision, 'rebuild'])
    (OUT / 'source.tar').write_bytes(archive)
    os.chmod(OUT / 'source.tar', 0o600)
    # Copy only the synthetic documents and already collected static files.
    # Existing retained state, documents, approval, evidence and source are not changed.
    state = io.BytesIO()
    with tarfile.open(fileobj=state, mode='w') as target:
        for name in ['files', 'staticfiles']:
            target.add(RUNTIME / name, arcname=name, recursive=True)
    (OUT / 'state.tar').write_bytes(state.getvalue())
    os.chmod(OUT / 'state.tar', 0o600)
    unit = f'''[Unit]
Description=QuillMD authenticated synthetic Corti replay candidate
After=network-online.target docker.service
Wants=network-online.target
[Service]
Type=simple
DynamicUser=yes
User=quillmd-corti-candidate
StateDirectory=quillmd-corti-candidate
StateDirectoryMode=0700
WorkingDirectory={RELEASE_ROOT}/releases/{revision}/rebuild
EnvironmentFile=/opt/quillmd-corti-candidate/environment
ExecStart=/opt/meddoc-pro/rebuild/.venv/bin/python -m gunicorn quillmd.wsgi:application --bind 127.0.0.1:9146 --workers 1 --threads 2 --timeout 60 --access-logfile /dev/null
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
KillMode=mixed
UMask=0077
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressDeny=any
IPAddressAllow=localhost
InaccessiblePaths=/run/docker.sock /var/lib/quillmd /etc/quillmd-corti-test /opt/meddoc-pro/rebuild/.env /opt/meddoc-pro/rebuild/.runtime /opt/meddoc-pro/.env
LimitCORE=0
MemorySwapMax=0
MemoryMax=512M
TasksMax=64
[Install]
WantedBy=multi-user.target
'''
    worker = unit.replace('Description=QuillMD authenticated synthetic Corti replay candidate', 'Description=QuillMD isolated synthetic Corti replay worker').replace('quillmd.wsgi:application --bind 127.0.0.1:9146 --workers 1 --threads 2 --timeout 60 --access-logfile /dev/null', 'WORKER_MARKER').replace('-m gunicorn WORKER_MARKER', 'manage.py worker')
    (OUT / 'unit.txt').write_text(unit)
    (OUT / 'worker-unit.txt').write_text(worker)
    # Root publication is limited to new candidate directories and one new unit.
    publish = '''import os,io,tarfile,pathlib,base64,subprocess,hashlib
r=pathlib.Path('/host/opt/quillmd-corti-candidate'); s=pathlib.Path('/host/var/lib/quillmd-corti-candidate')
u=pathlib.Path('/host/etc/systemd/system/quillmd-corti-candidate.service'); w=u.with_name('quillmd-corti-candidate-worker.service')
assert not any(p.exists() for p in [r,s,u,w])
r.mkdir(mode=0o755); (r/'releases').mkdir(mode=0o755); release=r/'releases'/REVISION; release.mkdir(mode=0o755)
for archive,dest in [('/payload/source.tar',release),('/payload/state.tar',s)]:
 if dest==s: dest.mkdir(mode=0o700)
 with tarfile.open(archive) as t:
  for m in t.getmembers():
   assert not m.issym() and not m.islnk() and (m.isfile() or m.isdir())
   assert not m.name.startswith('/') and '..' not in pathlib.PurePosixPath(m.name).parts
  t.extractall(dest,filter='data')
for p in [release,*release.rglob('*')]:
 os.chown(p,0,0); os.chmod(p,0o755 if p.is_dir() else 0o644)
(r/'environment').write_bytes(base64.b64decode(ENV)); os.chmod(r/'environment',0o600)
u.write_bytes(base64.b64decode(DOCTOR_UNIT));os.chmod(u,0o644)
w.write_bytes(base64.b64decode(WORKER_UNIT));os.chmod(w,0o644)
print('candidate_files_published')
'''.replace('REVISION', repr(revision)).replace('ENV', repr(base64.b64encode(env).decode())).replace('DOCTOR_UNIT', repr(base64.b64encode(unit.encode()).decode())).replace('WORKER_UNIT', repr(base64.b64encode(worker.encode()).decode()))
    helper(publish, ['type=bind,src=/,dst=/host,readonly', 'type=bind,src=/opt,dst=/host/opt', 'type=bind,src=/var/lib,dst=/host/var/lib', 'type=bind,src=/etc/systemd/system,dst=/host/etc/systemd/system', f'type=bind,src={OUT},dst=/payload,readonly'])
    # Stop only the two verified old isolated processes, never a native service.
    for filename, marker in [('worker.pid', b'manage.py\x00worker'), ('server.pid', b'gunicorn\x00quillmd.wsgi:application')]:
        pid = int((RUNTIME / filename).read_text())
        proc = Path('/proc') / str(pid)
        assert proc.stat().st_uid == os.getuid()
        assert str(ROOT / 'rebuild').encode() in (proc / 'cmdline').read_bytes()
        assert marker in (proc / 'cmdline').read_bytes()
        os.kill(pid, signal.SIGTERM)
    time.sleep(1)
    start = '''import os,subprocess
os.chroot('/host');os.chdir('/')
subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['/usr/bin/systemctl','enable','--now','quillmd-corti-candidate.service','quillmd-corti-candidate-worker.service'],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('candidate_service_started')
'''
    helper(start, ['type=bind,src=/,dst=/host,readonly', 'type=bind,src=/etc/systemd/system,dst=/host/etc/systemd/system'])
    # Current candidate DB alone becomes durable across host reboot.
    command(['docker', 'update', '--restart=unless-stopped', 'quillmd-corti-workflow-postgres-20261016'])
    headers = {'Host': 'app.quillmd.com', 'X-Forwarded-Proto': 'https', 'X-QuillMD-Account': '1',
               'X-QuillMD-Corti-Prefix': '/synthetic/corti'}
    for _ in range(25):
        try:
            with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9146/health/', headers=headers), timeout=2) as response:
                health = json.load(response)
            assert health == {'status': 'ok', 'data_mode': 'synthetic-only', 'surface': 'doctor', 'release': revision}
            break
        except (OSError, ValueError):
            time.sleep(.2)
    else:
        raise RuntimeError('New candidate health was not confirmed; ingress unchanged.')
    location = '''    # Isolated authenticated retained-response replay; no provider credentials.
    location = /synthetic/corti { return 308 /synthetic/corti/; }
    location ^~ /synthetic/corti/ {
        proxy_pass http://127.0.0.1:9146/;
        proxy_http_version 1.1;
        proxy_set_header Host app.quillmd.com;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-QuillMD-Account "1";
        proxy_set_header X-QuillMD-Corti-Prefix "/synthetic/corti";
        proxy_set_header Authorization "";
        proxy_set_header Connection "";
        proxy_hide_header Referrer-Policy;
        proxy_hide_header Cache-Control;
        proxy_hide_header X-Robots-Tag;
        add_header Referrer-Policy "same-origin" always;
        add_header Cache-Control "no-store, private" always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        proxy_cookie_flags ~ secure httponly samesite=strict;
        proxy_redirect off;
        proxy_read_timeout 60s;
    }

'''.encode()
    before_server, server = original.rsplit(b'server {', 1)
    assert b'server_name app.quillmd.com;' in server
    assert server.count(b'    location / {') == 1
    candidate = before_server + b'server {' + server.replace(b'    location / {', location + b'    location / {', 1)
    (OUT / 'nginx-after.conf').write_bytes(candidate)
    ingress = '''import os,pathlib,base64,hashlib,subprocess
os.chroot('/host');os.chdir('/')
p=pathlib.Path('/etc/nginx/sites-available/quillmd');old=p.read_bytes()
assert hashlib.sha256(old).hexdigest()==EXPECTED
replacement=base64.b64decode(REPLACEMENT)
def put(raw):
 q=p.with_name('.quillmd-corti-candidate');fd=os.open(q,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
 try:
  os.fchmod(fd,0o644);os.write(fd,raw);os.fsync(fd)
 finally:os.close(fd)
 os.replace(q,p)
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
put(replacement)
try:
 subprocess.run(['/usr/sbin/nginx','-t'],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['/usr/bin/systemctl','reload','nginx.service'],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
except BaseException:
 put(old)
 subprocess.run(['/usr/sbin/nginx','-t'],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['/usr/bin/systemctl','reload','nginx.service'],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 raise
assert p.read_bytes()==replacement
print('synthetic_https_route_published')
'''.replace('EXPECTED', repr(sha(original))).replace('REPLACEMENT', repr(base64.b64encode(candidate).decode()))
    helper(ingress, ['type=bind,src=/,dst=/host,readonly', 'type=bind,src=/etc/nginx/sites-available,dst=/host/etc/nginx/sites-available'])
    after = native_identity()
    assert after == before, 'Native service identity changed; investigate rather than claim unchanged.'
    receipt = {'revision': revision, 'declaration_commit': os.environ['RULED_MUTATION_DECL_COMMIT'],
        'url': 'https://app.quillmd.com/synthetic/corti/', 'mode': 'synthetic_retained_response_replay',
        'native_units_before': before, 'native_units_after': after, 'native_services_unchanged': True,
        'nginx_before_sha256': sha(original), 'nginx_after_sha256': sha(candidate),
        'source_archive_sha256': sha(archive), 'health': health, 'provider_calls': 0,
        'builds': 0, 'production_source_or_database_modified': False}
    (OUT / 'installation.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({'installed_revision': revision, 'url': receipt['url'], 'receipt': str(OUT / 'installation.json')}))


if __name__ == '__main__':
    main()
