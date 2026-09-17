#!/usr/bin/env python3
"""Guarded, one-shot private application identity and storage cutover.

No database schema/data mutation, provider calls, old-system import or cleanup.
Default mode verifies prerequisites without stopping or changing anything.
"""
import argparse
from datetime import datetime, timezone
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import time
from urllib.request import build_opener, HTTPRedirectHandler

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
RUNTIME = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
ACCOUNT = 'quillmd-app'
DECLARATION = '20260917-quillmd-os-identity.md'
UNITS = ['quillmd-fresh-' + name + '.service' for name in ('doctor', 'admin', 'worker')]
PSQL = ['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh',
        '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


def require(value, message):
    if not value:
        raise RuntimeError(message)


def output(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_write(path, document):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def private_bytes(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
            'Expected an operator-owned regular private file.')
    return path.read_bytes()


def database_fingerprints():
    tables = output(PSQL + ["SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"]).splitlines()
    require(len(tables) == 33 and all(re.fullmatch('[a-z_][a-z_0-9]*', item) for item in tables),
            'Expected all 33 current fresh database tables, including schema history.')
    result = {}
    for table in tables:
        data = subprocess.check_output(PSQL + [
            f'COPY (SELECT to_jsonb(t)::text AS value FROM "{table}" t ORDER BY value) TO STDOUT'])
        result[table] = {'sha256': hashlib.sha256(data).hexdigest(), 'rows': len(data.splitlines())}
    return result


def source_inventory(root):
    """Inspect every inactive storage object; reject links and unusual files."""
    require(root.is_absolute() and root.resolve() == root and root.is_dir()
            and root.stat().st_uid == os.getuid(), 'Invalid source storage root.')
    result = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode), 'Source storage contains a symlink.')
        if stat.S_ISDIR(info.st_mode):
            require(info.st_uid == os.getuid(), 'Source directory is not operator owned.')
            continue
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 256 * 1024 * 1024,
                'Unexpected source storage object or permissions.')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            digest = hashlib.sha256()
            count = 0
            while chunk := os.read(fd, 65536):
                count += len(chunk)
                digest.update(chunk)
            after = os.fstat(fd)
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                    == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                    and count == before.st_size, 'Source file changed while reading.')
            result[str(path.relative_to(root))] = {'sha256': digest.hexdigest(), 'size': count, 'mode': 0o600}
        finally:
            os.close(fd)
    return result


def static_sources():
    otp = Path(importlib.util.find_spec('django_otp').origin).parent
    return {'app.css': APP / 'static/app.css', 'app.js': APP / 'static/app.js',
            'django_otp/css/login.css': otp / 'static/django_otp/css/login.css',
            'otp_totp/css/qrcode.css': otp / 'plugins/otp_totp/static/otp_totp/css/qrcode.css',
            'otp_totp/js/qrcode.js': otp / 'plugins/otp_totp/static/otp_totp/js/qrcode.js'}


def static_inventory():
    """Only compiled public assets may receive public read permissions."""
    root = APP / 'staticfiles'
    require(root.resolve() == root, 'Static output path must be canonical.')
    rows = {}
    for path in [root, *sorted(root.rglob('*'))]:
        info = path.lstat()
        require(info.st_uid == os.getuid() and not stat.S_ISLNK(info.st_mode),
                'Static output must be operator-owned and free of symlinks.')
        relative = '.' if path == root else str(path.relative_to(root))
        row = {'mode': stat.S_IMODE(info.st_mode), 'device': info.st_dev, 'inode': info.st_ino}
        if stat.S_ISDIR(info.st_mode):
            row['kind'] = 'directory'
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 16 * 1024 * 1024,
                    'Static output contains a nonregular, linked or oversized object.')
            row.update(kind='file', size=info.st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        rows[relative] = row
        require(len(rows) <= 10000, 'Static output inventory exceeds the bounded scope.')
    manifest = json.loads((root / 'staticfiles.json').read_bytes())
    inputs = static_sources()
    require(isinstance(manifest.get('paths'), dict) and set(manifest['paths']) == set(inputs),
            'Static manifest differs from reviewed application and installed OTP assets.')
    allowed = {'staticfiles.json'}
    allowed_dirs = {'.'}
    for source, compiled in manifest['paths'].items():
        original = Path(source)
        pattern = re.escape(str(original.with_suffix(''))) + r'\.[a-f0-9]{12}' + re.escape(original.suffix)
        require(isinstance(compiled, str) and re.fullmatch(pattern, compiled),
                'Static manifest includes an unexpected path.')
        require((root / source).read_bytes() == inputs[source].read_bytes(),
                'Collected static input differs from current application source.')
        require(compiled in rows and rows[compiled]['kind'] == 'file', 'Compiled static asset is missing.')
        for path in (source, compiled):
            allowed.update((path, path + '.gz', path + '.br'))
            allowed_dirs.update(str(parent) for parent in Path(path).parents)
    require(all(name in (allowed_dirs if row['kind'] == 'directory' else allowed) for name, row in rows.items()),
            'Static output contains an object outside the reviewed public asset set.')
    return rows


def make_static_readable():
    before = static_inventory()
    root = APP / 'staticfiles'
    for relative, expected in before.items():
        path = root if relative == '.' else root / relative
        flags = os.O_RDONLY | os.O_NOFOLLOW
        if expected['kind'] == 'directory':
            flags |= os.O_DIRECTORY
        fd = os.open(path, flags)
        try:
            actual = os.fstat(fd)
            require((actual.st_dev, actual.st_ino, actual.st_uid) ==
                    (expected['device'], expected['inode'], os.getuid()),
                    'Static output changed before its scoped permission update.')
            os.fchmod(fd, 0o755 if expected['kind'] == 'directory' else 0o644)
        finally:
            os.close(fd)
    after = static_inventory()
    def content(rows):
        return {name: {key: value for key, value in row.items() if key != 'mode'}
                for name, row in rows.items()}
    require(content(after) == content(before), 'Static content or identity changed during permission update.')
    require(all(row['mode'] == (0o755 if row['kind'] == 'directory' else 0o644)
                for row in after.values()), 'Static permissions differ from reviewed policy.')
    return {'before': before, 'after': after, 'all_content_identical': True}


def source_readability(helper_image):
    """Read-only preflight as an unrelated nonroot UID, without operator groups."""
    # The venv's only expected symlinks point to the system interpreter and lib.
    # Their host targets must be traversable/readable without operator membership.
    for relative in ('.venv/bin/python', '.venv/bin/python3', '.venv/bin/python3.12', '.venv/lib64'):
        path = APP / relative
        require(path.exists(), 'Expected Python runtime entry is missing.')
        target = path.resolve(strict=True)
        for parent in (target, *target.parents):
            info = parent.stat()
            require(info.st_mode & (0o001 if stat.S_ISDIR(info.st_mode) else 0o004),
                    'Python runtime target is not readable by the application identity.')
    code = r'''import os,json,pathlib,stat,sys
try:
 assert os.getuid()==65534 and os.getgid()==65534 and not(set(os.getgroups())-{65534})
 root=pathlib.Path('/application'); count=0
 allowed_links={'.venv/lib64','.venv/bin/python','.venv/bin/python3','.venv/bin/python3.12'}
 def check(path):
  global count
  info=path.lstat(); relative=str(path.relative_to(root))
  if stat.S_ISLNK(info.st_mode):
   assert relative in allowed_links
   return
  assert stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|(os.O_DIRECTORY if stat.S_ISDIR(info.st_mode) else 0))
  try:
   if stat.S_ISREG(info.st_mode): os.read(fd,1)
  finally: os.close(fd)
  count+=1
  assert count<=100000
 def fail(error): raise RuntimeError('unreadable application tree')
 for name in ('manage.py','core','quillmd','documents','templates','static','ops','.venv'):
  path=root/name; check(path)
  if path.is_dir():
   for parent,dirs,files in os.walk(path,followlinks=False,onerror=fail):
    for name in dirs+files: check(pathlib.Path(parent)/name)
 print(json.dumps({'readable':True,'checked_entries':count,'uid':65534,'gid':65534,'provider_calls':0}))
except Exception:
 sys.exit(1)
'''
    result = subprocess.run(['docker', 'run', '--rm', '-i', '--pull=never', '--network=none',
                             '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                             '--user', '65534:65534', '--pids-limit=32', '--memory=256m',
                             '--mount', f'type=bind,src={APP},dst=/application,readonly',
                             helper_image, 'python', '-B', '-'], input=code, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    require(result.returncode == 0, 'Application source or Python environment is unreadable by an unrelated UID.')
    report = json.loads(result.stdout)
    require(report.get('readable') is True and report.get('uid') == 65534 and report.get('gid') == 65534
            and report.get('provider_calls') == 0, 'Source readability proof is incomplete.')
    return report


def verify_interfaces():
    manifest = json.loads((APP / 'staticfiles/staticfiles.json').read_bytes())
    css = manifest['paths']['app.css']
    require(re.fullmatch(r'app\.[a-f0-9]{12}\.css', css), 'Unexpected compiled stylesheet path.')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, newurl):
            return None
    opener = build_opener(NoRedirect)
    def fetch(url, expected_type):
        with opener.open(url, timeout=10) as response:
            body = response.read(2 * 1024 * 1024 + 1)
            require(response.status == 200 and response.headers.get_content_type() == expected_type
                    and 0 < len(body) <= 2 * 1024 * 1024, 'Private interface response is incomplete.')
            return body
    results = {}
    for surface, port in (('doctor', 9130), ('admin', 9131)):
        origin = f'http://127.0.0.1:{port}'
        html = fetch(origin + '/login/', 'text/html').decode()
        require(f'href="/static/{css}"' in html and 'name="csrfmiddlewaretoken"' in html,
                'Login form or compiled stylesheet reference is missing.')
        body = fetch(origin + '/static/' + css, 'text/css')
        require(hashlib.sha256(body).hexdigest() ==
                hashlib.sha256((APP / 'staticfiles' / css).read_bytes()).hexdigest(),
                'Served stylesheet differs from collected static output.')
        results[surface] = {'login_status': 200, 'login_form_present': True,
                            'stylesheet_status': 200, 'stylesheet_type': 'text/css',
                            'stylesheet_bytes': len(body), 'stylesheet_hash_matched': True}
    return results


def check_account_if_present():
    try:
        account = pwd.getpwnam(ACCOUNT)
    except KeyError:
        try:
            grp.getgrnam(ACCOUNT)
        except KeyError:
            return {'present': False}
        raise RuntimeError('A preexisting unpaired application group requires investigation.')
    require(0 < account.pw_uid < 1000 and account.pw_dir == str(STATE)
            and account.pw_shell == '/usr/sbin/nologin', 'Preexisting account does not match the reviewed system identity.')
    group = grp.getgrnam(ACCOUNT)
    require(account.pw_gid == group.gr_gid and not group.gr_mem
            and set(os.getgrouplist(ACCOUNT, account.pw_gid)) <= {account.pw_gid},
            'Preexisting account has unexpected memberships.')
    return {'present': True, 'uid': account.pw_uid, 'gid': account.pw_gid}


def stamp_environment(target, expected_bytes):
    env = APP / '.env'
    require(private_bytes(env) == expected_bytes, 'Fresh configuration changed concurrently.')
    keys = ('QUILLMD_STATE_DIR', 'QUILLMD_RELEASE_SHA')
    lines = expected_bytes.decode().splitlines()
    for key in keys:
        require(sum(line.startswith(key + '=') for line in lines) <= 1, 'Duplicate cutover configuration key.')
    retained = [line for line in lines if not any(line.startswith(key + '=') for key in keys)]
    updated = ('\n'.join(retained) + '\nQUILLMD_STATE_DIR=' + str(STATE)
               + '\nQUILLMD_RELEASE_SHA=' + target + '\n').encode()
    pending = RUNTIME / 'os-identity-env.pending'
    fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(updated)
        stream.flush()
        os.fsync(stream.fileno())
    require(private_bytes(env) == expected_bytes, 'Fresh configuration changed before replacement.')
    pending.replace(env)
    require([line for line in private_bytes(env).decode().splitlines()
             if not any(line.startswith(key + '=') for key in keys)] == retained,
            'Unrelated configuration changed during replacement.')


def root_cutover(target, inventories, expected_units, helper_image):
    # Independent writable binds cannot support atomic rename between them.
    # Copy into private staging children, verify, then rename within /var/lib.
    # Existing operator copies remain untouched and inactive after cutover.
    parameters = {'target': target, 'inventories': inventories, 'unit_hashes': expected_units,
                  'operator_uid': os.getuid(), 'operator_gid': os.getgid()}
    code = r'''import os,sys,json,hashlib,pathlib,pwd,grp,stat,subprocess,shutil
P=PARAMETERS
def require(value,label):
 if not value: raise RuntimeError(label)
def inventory(root):
 result={}
 require(root.is_dir() and not root.is_symlink(),'source root')
 for item in sorted(root.rglob('*')):
  s=item.lstat()
  require(not stat.S_ISLNK(s.st_mode),'source symlink')
  if stat.S_ISDIR(s.st_mode): continue
  require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=256*1024*1024,'source object')
  result[str(item.relative_to(root))]={'sha256':hashlib.sha256(item.read_bytes()).hexdigest(),'size':s.st_size,'mode':0o600}
 return result
def main():
 os.chroot('/host'); os.chdir('/'); os.umask(0o077)
 app=pathlib.Path('/opt/meddoc-pro/rebuild'); state=pathlib.Path('/var/lib/quillmd'); account='quillmd-app'
 require(not state.exists() and not state.is_symlink(),'state already exists')
 for name in ('files','mail'):
  require(inventory(app/'.runtime'/name)==P['inventories'][name],'source changed before cutover')
 for unit,expected in P['unit_hashes'].items():
  source=app/'deploy'/unit
  require(source.is_file() and not source.is_symlink() and hashlib.sha256(source.read_bytes()).hexdigest()==expected,'unit bytes changed')
  require(subprocess.check_output(['systemctl','show',unit,'--property=ActiveState','--value'],text=True).strip()=='inactive','unit active')
 try: identity=pwd.getpwnam(account)
 except KeyError:
  try: grp.getgrnam(account)
  except KeyError: pass
  else: raise RuntimeError('unpaired account group')
  subprocess.run(['useradd','--system','--user-group','--no-create-home','--home-dir',str(state),
                  '--shell','/usr/sbin/nologin','--no-log-init',account],check=True,
                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  identity=pwd.getpwnam(account)
 group=grp.getgrnam(account)
 require(0<identity.pw_uid<1000 and identity.pw_gid==group.gr_gid and identity.pw_dir==str(state)
         and identity.pw_shell=='/usr/sbin/nologin' and not group.gr_mem
         and set(os.getgrouplist(account,identity.pw_gid))<={identity.pw_gid},'account privileges')
 state.mkdir(mode=0o710)
 os.chown(state,0,identity.pw_gid); os.chmod(state,0o710)
 roots={}
 for name in ('files','mail','proofs'):
  pending=state/('.'+name+'.pending-'+P['target'])
  pending.mkdir(mode=0o700)
  if name!='proofs':
   source=app/'.runtime'/name
   for item in sorted(source.rglob('*')):
    rel=item.relative_to(source); destination=pending/rel; info=item.lstat()
    require(not stat.S_ISLNK(info.st_mode),'copy symlink')
    if stat.S_ISDIR(info.st_mode): destination.mkdir(mode=0o700)
    else:
     require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'copy type')
     with item.open('rb') as src, destination.open('xb') as dst:
      shutil.copyfileobj(src,dst,65536); dst.flush(); os.fsync(dst.fileno())
     os.chmod(destination,0o600)
   require(inventory(pending)==P['inventories'][name],'copied bytes differ')
   require(inventory(source)==P['inventories'][name],'old bytes changed')
  for item in [pending,*pending.rglob('*')]:
   info=item.lstat(); require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),'copied type')
   os.chown(item,identity.pw_uid,identity.pw_gid,follow_symlinks=False)
   os.chmod(item,0o700 if stat.S_ISDIR(info.st_mode) else 0o600,follow_symlinks=False)
  destination=state/name
  require(not destination.exists() and not destination.is_symlink(),'destination collision')
  pending.rename(destination)
  info=destination.lstat(); roots[str(destination)]={'device':info.st_dev,'inode':info.st_ino}
 for unit,expected in P['unit_hashes'].items():
  source=app/'deploy'/unit; data=source.read_bytes()
  require(hashlib.sha256(data).hexdigest()==expected,'unit changed at install')
  destination=pathlib.Path('/etc/systemd/system')/unit
  require(destination.is_file() and not destination.is_symlink(),'unit target')
  pending=destination.with_name('.'+unit+'.os-identity-pending')
  fd=os.open(pending,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
  with os.fdopen(fd,'wb') as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.chmod(pending,0o644);os.chown(pending,0,0);pending.replace(destination)
 subprocess.run(['systemctl','daemon-reload'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 print(json.dumps({'version':1,'account':{'name':account,'uid':identity.pw_uid,'gid':identity.pw_gid},'roots':roots}))
try: main()
except Exception as error:
 print(json.dumps({'error_kind':type(error).__name__,'check':str(error) if type(error) is RuntimeError else 'root operation failed'}))
 sys.exit(1)
'''.replace('PARAMETERS', repr(parameters))
    command = ['docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--pid=host',
               '--mount', 'type=bind,src=/,dst=/host,readonly',
               '--mount', 'type=bind,src=/etc,dst=/host/etc',
               '--mount', 'type=bind,src=/var/lib,dst=/host/var/lib',
               helper_image, 'python', '-B', '-']
    result = subprocess.run(command, input=code, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        identity = json.loads(result.stdout)
    except json.JSONDecodeError:
        private_write(RUNTIME / 'os-identity-root-result.json', {'exit_code': result.returncode,
                      'error_kind': 'RootResultUnavailable', 'stderr_suppressed': True})
        raise RuntimeError('Root cutover did not return its installation identity.') from None
    # The fixed helper emits only identity metadata or fixed error labels; never
    # copy unfiltered container stderr (which can include host details) to logs.
    require(isinstance(identity, dict), 'Root cutover returned an unexpected result shape.')
    private_write(RUNTIME / 'os-identity-root-result.json', {'exit_code': result.returncode, 'result': identity})
    require(result.returncode == 0, 'Bounded root cutover failed; inspect its private result before any retry.')
    require(identity.get('version') == 1 and identity.get('account', {}).get('name') == ACCOUNT,
            'Unexpected state installation identity.')
    return identity


def verify_live(target, storage):
    proofs = {}
    for surface, unit in zip(('doctor', 'admin', 'worker'), UNITS):
        require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'active',
                'A private service is not active.')
        pid = int(output(['systemctl', 'show', unit, '--property=MainPID', '--value']))
        proof = json.loads(storage.read_file(STATE / 'proofs', surface + '.json'))
        require(proof.get('passed') is True and proof.get('pid') == pid and proof.get('surface') == surface
                and proof.get('release') == target and proof.get('provider_calls') == 0,
                'Boundary proof does not describe the current service.')
        identity = pwd.getpwnam(ACCOUNT)
        require(proof.get('identity', {}).get('uid') == identity.pw_uid
                and proof['identity'].get('gid') == identity.pw_gid
                and set(proof['identity'].get('supplementary_groups', [])) <= {identity.pw_gid}
                and proof['identity'].get('all_capability_sets_empty') is True
                and proof['identity'].get('no_new_privileges') is True,
                'Boundary identity proof is incomplete.')
        status = {}
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                status[key] = value.strip()
        require([int(value) for value in status['Uid'].split()] == [identity.pw_uid] * 4
                and [int(value) for value in status['Gid'].split()] == [identity.pw_gid] * 4
                and {int(value) for value in status['Groups'].split()} <= {identity.pw_gid}
                and all(int(status[key], 16) == 0 for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'))
                and status['NoNewPrivs'] == '1', 'Actual running process privileges differ from startup proof.')
        required_denials = {'shared_environment', 'fresh_environment', 'operator_runtime',
                           'bootstrap_database_secret', 'synthetic_account_credentials',
                           'retained_credentials', 'code_write', 'launcher_write', 'docker_socket'}
        require(all(proof.get('checks', {}).get(name, {}).get('denied') is True for name in required_denials),
                'Boundary denial proof is incomplete.')
        require(all(proof['checks'].get('state_' + name, {}).get('read_write_delete') is True
                    for name in ('files', 'mail', 'proofs')), 'State positive control is incomplete.')
        proofs[surface] = proof
    return proofs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Run only from the shared main directory.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full reviewed merge SHA.')
    require(output(['git', 'branch', '--show-current']) == 'main', 'Shared deploy tree must remain main.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    require(output(['git', 'show', args.target + ':scripts/activate-os-identity.py']) == Path(__file__).read_text().strip(),
            'Activator bytes do not match the reviewed target.')
    require(output(['git', 'rev-parse', 'origin/main']) == args.target, 'Target is not current origin/main.')
    run(['git', 'merge-base', '--is-ancestor', 'HEAD', args.target])
    require(output(['git', 'diff', '--name-only', 'HEAD', args.target, '--', 'rebuild/core/migrations']) == '',
            'Identity cutover must not contain a schema change.')
    require(output(['git', 'remote', 'get-url', 'origin']) == 'https://github.com/kasrarayat-cloud/MedDoc.git',
            'Unexpected origin repository.')
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'Target lacks a merged PR into main.')
    require(RUNTIME.resolve() == RUNTIME and stat.S_IMODE(RUNTIME.stat().st_mode) == 0o700,
            'Operator runtime must remain its private real directory.')
    require(STATE.parent.resolve() == STATE.parent and STATE.parent.stat().st_uid == 0
            and not (stat.S_IMODE(STATE.parent.stat().st_mode) & 0o022),
            'State parent must remain a real root-owned directory without group/world writes.')
    require(not STATE.exists() and not STATE.is_symlink() and not (RUNTIME / 'state-identity.json').exists(),
            'State cutover was already begun; inspect partial state instead of repeating it.')
    require(not (RUNTIME / 'os-identity-activation.json').exists()
            and not (RUNTIME / '.os-identity.lock').exists(), 'Existing cutover evidence or lock requires inspection.')
    check_account_if_present()
    # Import only these already reviewed read-only/three-service primitives.
    previous = module_at('reviewed_private_updater', ROOT / 'scripts/update-private-beta.py')
    previous.validate_restore_report(args.backup_report)
    previous.protected()
    helper_image = output(['docker', 'image', 'inspect', 'python:3-slim', '--format', '{{.Id}}'])
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper_image), 'Pin the already present helper image.')
    source_readability(helper_image)
    static_inventory()
    baseline_environment = private_bytes(APP / '.env')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('running','queued')"]) == '0',
            'Active jobs must finish or be reconciled before identity cutover.')
    for name in ('files', 'mail'):
        source_inventory(RUNTIME / name)
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Verified scoped identity candidate, merged PR, private storage, restore and shared services.', flush=True)
    if not args.execute:
        return
    require(Path(os.environ.get('RULED_MUTATION_DECLARATION', '')).name == DECLARATION
            and re.fullmatch('[a-f0-9]{40}', os.environ.get('RULED_MUTATION_DECL_COMMIT', '')),
            'Use the committed identity declaration through the ruled-mutation runner.')
    private_write(RUNTIME / '.os-identity.lock', {'pid': os.getpid(), 'target': args.target})
    result = {'started_at': datetime.now(timezone.utc).isoformat(), 'previous_head': output(['git', 'rev-parse', 'HEAD']),
              'target': args.target, 'complete': False, 'provider_calls': 0, 'schema_changes': 0,
              'old_state_retained': True, 'helper_image': helper_image}
    stopped = False
    try:
        print('Stopping exactly the three private services; preserving every application row and file.', flush=True)
        stopped = True
        result['stage'] = 'stopping_services'
        previous.systemd('stop')
        require(all(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                    for unit in UNITS), 'A private unit did not stop.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('running','queued')"]) == '0',
                'Unresolved jobs remain; no provider retry or release attempted.')
        result['database_before'] = database_fingerprints()
        inventories = {name: source_inventory(RUNTIME / name) for name in ('files', 'mail')}
        result['storage_before'] = inventories
        result['stage'] = 'advancing_reviewed_main'
        run(['git', 'merge', '--ff-only', args.target])
        expected_units = {}
        for unit in UNITS:
            source = APP / 'deploy' / unit
            data = source.read_bytes()
            require(data == subprocess.check_output(['git', 'show', args.target + ':rebuild/deploy/' + unit]),
                    'Unit bytes differ from reviewed target.')
            require(b'User=quillmd-app\n' in data and b'Group=quillmd-app\n' in data
                    and b'CapabilityBoundingSet=\n' in data and b'EnvironmentFile=/opt/meddoc-pro/rebuild/.env\n' in data
                    and b'ops/service_launcher.py --surface ' in data, 'Required private identity unit policy missing.')
            expected_units[unit] = hashlib.sha256(data).hexdigest()
        run(['systemd-analyze', 'verify', *[str(APP / 'deploy' / unit) for unit in UNITS]])
        result['source_readability'] = source_readability(helper_image)
        result['stage'] = 'making_compiled_public_assets_readable'
        result['static_permissions'] = make_static_readable()
        result['stage'] = 'installing_identity_state_and_units'
        identity = root_cutover(args.target, inventories, expected_units, helper_image)
        private_write(RUNTIME / 'state-identity.json', identity)
        result['state_identity'] = identity
        sys.path.insert(0, str(APP / 'ops'))
        storage = module_at('private_storage_for_cutover', APP / 'ops/private_storage.py')
        for name in ('files', 'mail'):
            require(storage.inventory(STATE / name) == inventories[name], 'New private storage differs from original.')
            require(source_inventory(RUNTIME / name) == inventories[name], 'Retained inactive storage changed.')
        result['database_after'] = database_fingerprints()
        require(result['database_after'] == result['database_before'], 'Application or schema-history rows changed.')
        result['stage'] = 'stamping_private_environment'
        stamp_environment(args.target, baseline_environment)
        for unit, expected in expected_units.items():
            require(hashlib.sha256((Path('/etc/systemd/system') / unit).read_bytes()).hexdigest() == expected,
                    'Installed unit differs from reviewed source.')
        run([str(APP / '.venv/bin/python'), 'manage.py', 'check'], cwd=APP)
        result['stage'] = 'starting_and_verifying_private_services'
        previous.systemd('start')
        for attempt in range(30):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', f'http://127.0.0.1:{port}/health/']))
                          for port in (9130, 9131)]
                if all(row.get('release') == args.target and row.get('data_mode') == 'synthetic-only' for row in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Private health did not match the reviewed synthetic release.')
        result['proofs'] = verify_live(args.target, storage)
        result['interfaces'] = verify_interfaces()
        require(database_fingerprints() == result['database_before'], 'Unexpected database mutation during startup checks.')
        require(all(storage.inventory(STATE / name) == inventories[name] for name in ('files', 'mail')),
                'Unexpected application file mutation during startup checks.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, health=health, protected_containers=previous.protected(),
                      all_tables_identical=True, all_active_files_identical=True, all_inactive_files_identical=True,
                      installed_unit_hashes=expected_units, stage='complete')
    except BaseException as error:
        result['failure_kind'] = type(error).__name__
        # Do not leave a partially verified runtime accepting requests. Never
        # reapply, recopy, restart providers or roll back automatically.
        if stopped:
            try:
                previous.systemd('stop')
                result['failure_services_stopped'] = True
            except BaseException:
                result['failure_services_stopped'] = False
        raise
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        private_write(RUNTIME / 'os-identity-activation.json', result)
        if result['complete']:
            (RUNTIME / '.os-identity.lock').unlink()
        print('Private identity activation evidence: ' + str(RUNTIME / 'os-identity-activation.json'), flush=True)
    print('Dedicated application identity verified; public maintenance and synthetic-only controls preserved.', flush=True)


if __name__ == '__main__':
    main()
