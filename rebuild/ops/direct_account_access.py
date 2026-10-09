"""Exact owner-authorized replacement of QuillMD's shared preview gate.

Pure transition helpers do not touch the host. Native publication remains behind
the committed mutation declaration, exact-candidate CI and preservation checks.
Historical declarations and evidence are retained; old gate controllers refuse
after the direct-account marker is installed instead of silently restoring them.
"""
import base64
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import stat

from dotenv import dotenv_values
from dotenv.parser import parse_stream

ORIGIN = 'https://app.quillmd.com'
ROOT = Path('/opt/meddoc-pro')
DECISION = ROOT / 'rebuild/.runtime/direct-account-signin-20261009/owner-direct-account-access-decision-v1.json'
DECISION_SHA256 = 'de60ffef89828163607f26d8b32ed1d6d1fde0e3c948442e30bc30738cec1db7'
MARKER = 'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED'
REMOVED_KEYS = frozenset({'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME', 'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD'})
ENVIRONMENT_KEYS = frozenset({'QUILLMD_RELEASE_SHA', MARKER, 'QUILLMD_PREVIEW_AUTH_ENABLED',
    'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', 'QUILLMD_APP_BASE_URL'}) | REMOVED_KEYS
INGRESS_PATHS = ('/etc/nginx/sites-available/quillmd', '/etc/nginx/sites-available/quillmd-email-preview')
ASSIGNMENT = re.compile(rb'[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=')


def require(value, label):
    if not value:
        raise ValueError(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def values(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 65536 and b'\0' not in raw,
            'direct_account_bounded_environment')
    decoded = raw.decode()
    seen = set()
    for binding in parse_stream(StringIO(decoded)):
        if binding.key in ENVIRONMENT_KEYS:
            # dotenv also accepts quoted keys and multiline assignments. Keep
            # the systemd/line-editor contract explicit instead of appending a
            # duplicate effective setting or consuming unrelated source bytes.
            binding_line = binding.original.string.lstrip()
            match = ASSIGNMENT.match(binding_line.encode())
            require(not binding.error and match and match[1].decode() == binding.key
                    and len(binding_line.splitlines()) == 1
                    and binding.key not in seen, 'direct_account_ambiguous_controlled_assignment')
            seen.add(binding.key)
    return dotenv_values(stream=StringIO(decoded), interpolate=False)


def reject_legacy_environment(original):
    """An installed direct policy cannot be undone by a historical renderer."""
    require(direct_marker(original) != '1',
            'owner_direct_account_decision_supersedes_shared_preview_gate')


def direct_marker(original):
    parsed = values(original)
    marker_lines = [line for line in original.splitlines() if
        (match := ASSIGNMENT.match(line)) and match[1].decode() == MARKER]
    require(len(marker_lines) <= 1 and parsed.get(MARKER) in (None, '', '0', '1'),
            'direct_account_policy_marker_ambiguous')
    return parsed.get(MARKER)


def protected(path, maximum):
    """No symlink, public permissions, hardlink or unstable read is accepted."""
    path = Path(path)
    require(path.resolve(strict=True) == path, 'direct_account_canonical_evidence_path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_uid == before.st_gid == 1000
                and stat.S_IMODE(before.st_mode) == 0o600 and not os.listxattr(fd),
                'direct_account_protected_evidence_identity')
        raw = b''
        while len(raw) <= maximum:
            block = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not block:
                break
            raw += block
        identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_uid,
            row.st_gid, row.st_nlink, row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        require(len(raw) == before.st_size <= maximum
                and identity(before) == identity(os.fstat(fd)) == identity(path.lstat()),
                'direct_account_protected_evidence_race')
        return raw
    finally:
        os.close(fd)


def owner_decision():
    raw = protected(DECISION, 16384)
    require(sha(raw) == DECISION_SHA256, 'direct_account_exact_owner_decision')
    decision = json.loads(raw)
    require(decision.get('base_installed_revision') == '0042cf7f7f0b437b3baeaf1c40dab66912294fef'
            and decision.get('provider_calls_allowed') == 0
            and decision.get('password_reset_allowed') is False
            and decision.get('public_signup_allowed') is False
            and decision.get('other_projects_changes_allowed') is False,
            'direct_account_owner_decision_scope')
    return {'path': str(DECISION), 'sha256': sha(raw), 'base': decision['base_installed_revision']}


def refuse_legacy_operation():
    """Real historical executors check current policy before any native action.

    A missing or malformed decision never authorizes gate restoration. Before
    the installed marker changes, existing historical rollback remains available.
    """
    original = protected(ROOT / 'rebuild/.env', 65536)
    if direct_marker(original) == '1':
        owner_decision()
        raise ValueError('owner_direct_account_decision_supersedes_shared_preview_gate')


def environment(original, previous, target):
    """Change exactly the seven declared keys; keep all other bytes intact."""
    require(all(type(value) is str and re.fullmatch('[a-f0-9]{40}', value)
                for value in (previous, target)), 'direct_account_exact_release_identifiers')
    before = values(original)
    require(original.endswith(b'\n') and before.get('QUILLMD_RELEASE_SHA') == previous
            and before.get('QUILLMD_DATA_MODE', 'synthetic') == 'synthetic'
            and before.get('QUILLMD_TRUST_PROXY') == '1'
            and before.get('QUILLMD_APP_BASE_URL') in (ORIGIN, ORIGIN + ':9443')
            and before.get(MARKER) in (None, '', '0', '1'),
            'direct_account_current_restricted_environment')
    updates = {'QUILLMD_RELEASE_SHA': target, MARKER: '1', 'QUILLMD_PREVIEW_AUTH_ENABLED': '0',
        'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': '1', 'QUILLMD_APP_BASE_URL': ORIGIN}
    output, unrelated, seen = [], [], set()
    for line in original.splitlines(keepends=True):
        match = ASSIGNMENT.match(line)
        key = match[1].decode() if match else None
        if key not in ENVIRONMENT_KEYS:
            output.append(line)
            unrelated.append(line)
            continue
        require(key not in seen, 'direct_account_duplicate_controlled_setting')
        seen.add(key)
        if key in updates:
            output.append((key + '="' + updates[key] + '"\n').encode())
    output.extend((key + '="' + updates[key] + '"\n').encode() for key in sorted(set(updates) - seen))
    candidate = b''.join(output)
    after = values(candidate)
    require(all(after.get(key) == value for key, value in updates.items())
            and not (REMOVED_KEYS & set(after)), 'direct_account_effective_exact_settings')
    require({key: value for key, value in before.items() if key not in ENVIRONMENT_KEYS}
            == {key: value for key, value in after.items() if key not in ENVIRONMENT_KEYS}
            and [line for line in candidate.splitlines(keepends=True) if not
                ((match := ASSIGNMENT.match(line)) and match[1].decode() in ENVIRONMENT_KEYS)] == unrelated,
            'direct_account_unrelated_environment_values_and_bytes_preserved')
    return candidate


def render_ingress(original, legacy, old_normal, old_legacy, new_normal, new_legacy):
    """Replace only the exact installed Quill suffix and retired preview file."""
    require(all(type(raw) is bytes and 0 < len(raw) <= 131072 and b'\0' not in raw
                for raw in (original, legacy, old_normal, old_legacy, new_normal, new_legacy)),
            'direct_account_ingress_bounded_bytes')
    require(original.endswith(old_normal) and original.count(old_normal) == 1
            and legacy == old_legacy, 'direct_account_exact_previous_ingress_templates')
    require(new_normal.count(b'server_name app.quillmd.com;') == 1
            and new_normal.count(b'proxy_set_header X-QuillMD-Account "1";') == 1
            and b'proxy_set_header Host app.quillmd.com;' in new_normal
            and b'proxy_pass http://127.0.0.1:9130;' in new_normal
            and b'auth_basic' not in new_normal and b'__Host-quillmd_preview' not in new_normal
            and b'X-QuillMD-Preview "1"' not in new_normal,
            'direct_account_only_account_proxy_transport')
    require(new_legacy.count(b'return 303 https://app.quillmd.com/login/;') == 1
            and b'proxy_pass' not in new_legacy and b'auth_basic' not in new_legacy
            and b'$request_uri' not in new_legacy and b'$args' not in new_legacy
            and b'__Host-quillmd_preview' not in new_legacy,
            'direct_account_legacy_origin_drops_paths_and_queries')
    prefix = original[:-len(old_normal)]
    normal = prefix + new_normal
    require(len(normal) <= 131072 and normal[:-len(new_normal)] == prefix,
            'direct_account_other_ingress_bytes_preserved')
    return {INGRESS_PATHS[0]: normal, INGRESS_PATHS[1]: new_legacy}


def ingress_helper_code(originals, candidates, metadata, token):
    """Same reviewed privileged mechanism: two fixed Quill files, one reload.

    The calling installation must preserve the original files first, compare
    all unrelated configuration, and recover any interrupted two-file publish.
    No host action occurs while constructing this bounded helper source.
    """
    require(set(originals) == set(candidates) == set(metadata) == set(INGRESS_PATHS),
            'direct_account_exact_two_ingress_paths')
    require(type(token) is str and re.fullmatch('[a-f0-9]{16}', token),
            'direct_account_ingress_unique_attempt_token')
    fields = {'uid', 'gid', 'mode', 'device', 'inode', 'sha256'}
    for path in INGRESS_PATHS:
        row = metadata[path]
        require(type(row) is dict and set(row) == fields
                and row['uid'] == row['gid'] == 0 and row['mode'] == 0o644
                and row['sha256'] == sha(originals[path])
                and type(candidates[path]) is bytes and 0 < len(candidates[path]) <= 131072,
                'direct_account_ingress_exact_original_identity')
    inputs = {Path(path).name: {'expected': metadata[path],
        'replacement': base64.b64encode(candidates[path]).decode()} for path in INGRESS_PATHS}
    code = """import os,stat,json,hashlib,base64,subprocess,sys
root=os.open('/target',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
os.chroot('/host');os.chdir('/')
inputs=INPUTS
token=TOKEN
assert set(inputs)=={'quillmd','quillmd-email-preview'}
def current(name):
 f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=root)
 try:
  i=os.fstat(f);assert stat.S_ISREG(i.st_mode) and i.st_nlink==1 and not os.listxattr(f)
  raw=b''
  while len(raw)<=131072:
   chunk=os.read(f, min(65536,131073-len(raw)))
   if not chunk:break
   raw+=chunk
  assert len(raw)==i.st_size<=131072
  m={'uid':i.st_uid,'gid':i.st_gid,'mode':stat.S_IMODE(i.st_mode),'device':i.st_dev,'inode':i.st_ino,'sha256':hashlib.sha256(raw).hexdigest()}
  assert os.stat(name,dir_fd=root,follow_symlinks=False).st_ino==i.st_ino
  return raw,m
 finally:os.close(f)
for name,item in inputs.items():assert current(name)[1]==item['expected']
pending={}
try:
 for name,item in inputs.items():
  replacement=base64.b64decode(item['replacement'],validate=True)
  temporary='.quillmd-direct-'+name+'-'+token
  f=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,420,dir_fd=root)
  created=os.fstat(f);pending[name]=(temporary,created.st_dev,created.st_ino)
  try:
   os.fchmod(f,420);offset=0
   while offset<len(replacement):
    written=os.write(f,replacement[offset:]);assert written>0;offset+=written
   os.fsync(f)
  finally:os.close(f)
 for name,item in inputs.items():assert current(name)[1]==item['expected']
 for name,(temporary,device,inode) in pending.items():os.replace(temporary,name,src_dir_fd=root,dst_dir_fd=root)
 os.fsync(root)
finally:
 # Only our own still-attached created inode may be reclaimed. A collision or
 # swapped path is never removed; its refusal is retained by the caller.
 for name,(temporary,device,inode) in pending.items():
  try:f=os.open(temporary,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=root)
  except FileNotFoundError:continue
  try:
   i=os.fstat(f);assert (i.st_dev,i.st_ino)==(device,inode)
   assert stat.S_ISREG(i.st_mode) and i.st_nlink==1 and i.st_uid==i.st_gid==0 and not os.listxattr(f)
   raw=os.read(f,131073);assert len(raw)==i.st_size<=131072
   named=os.stat(temporary,dir_fd=root,follow_symlinks=False)
   assert (named.st_dev,named.st_ino)==(device,inode)
   print(json.dumps({'retained_failed_pending_metadata':{'path':temporary,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'device':device,'inode':inode}}),file=sys.stderr)
   os.unlink(temporary,dir_fd=root);os.fsync(root)
  finally:os.close(f)
subprocess.run(['/usr/sbin/nginx','-t'],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['/usr/bin/systemctl','reload','nginx.service'],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
result={}
for name,item in inputs.items():
 raw,m=current(name);assert raw==base64.b64decode(item['replacement'],validate=True)
 result['/etc/nginx/sites-available/'+name]=m
print(json.dumps(result,sort_keys=True))
"""
    return code.replace('inputs=INPUTS', 'inputs=' + repr(inputs), 1).replace('token=TOKEN', 'token=' + repr(token), 1)
