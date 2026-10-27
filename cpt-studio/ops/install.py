#!/usr/bin/env python3
"""CPT Studio installer. Runs ONLY through the ruled-mutation door:

    bash scripts/run-ruled-mutation.sh --declaration <committed declaration> -- \\
        python3 -B cpt-studio/ops/install.py --phase <phase> --revision <40-char sha> \\
        --receipts <absolute 0700 dir outside the repository> [phase arguments]

One phase per invocation. Each phase checks its own preconditions, is bounded,
writes one JSON receipt (0600) and prints one summary line. Secrets are
generated inside root helpers or passed through stdin; they never appear in
argv, receipts or output. Writes under /etc go through a pinned helper image;
nginx is validated and reloaded only with the two proven `sudo -n` commands.
Standard library only. Phase-by-phase effects: ops/INSTALL.md.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import http.client
import io
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
APP = 'cpt-studio'
SELF = Path(__file__).resolve()

DOMAIN = 'cpt.quillmd.com'
PUBLIC_IPV4 = '147.189.172.8'
WEB_PORT = 9150
DB_PORT = 55451
UPSTREAM = f'127.0.0.1:{WEB_PORT}'
APP_HEALTH_HOST = 'app.quillmd.com'

NETWORK = 'cpt-studio-net'
DB_VOLUME = 'cpt-studio-pg'
FILES_VOLUME = 'cpt-studio-files'
DB_CONTAINER = 'cpt-studio-db'
SERVICES = {'web': 'cpt-studio-web', 'worker': 'cpt-studio-worker'}
STOP_SECONDS = {'web': 30, 'worker': 150}  # a worker may be inside a 120 s provider read
DB_NAME = DB_USER = 'cptstudio'
APP_UID = 10150  # must equal the Dockerfile's USER; unique on this host (10001 is a co-tenant's)
POSTGRES_UID = 70
STATE_DIR = '/var/lib/cpt-studio'
CREDENTIALS_IN_CONTAINER = '/run/cpt-studio/corti-credentials.env'

LABEL = 'org.quillmd.cpt-studio'
ROLE_LABEL = 'org.quillmd.cpt-studio.role'
REVISION_LABEL = 'org.opencontainers.image.revision'
HELPER_LABEL = 'org.quillmd.cpt-studio.helper'

DOCKER = '/usr/bin/docker'
HELPER_IMAGE = 'sha256:9b84b0c75adf7a34fb1b00b406a50dc9f7bebd3bfbe3e7fd9ff168a6f9d0dfb9'
POSTGRES_IMAGE = 'postgres:17.11-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'

ETC_DIR = '/etc/cpt-studio'
APP_ENV = f'{ETC_DIR}/app.env'
DB_ENV = f'{ETC_DIR}/db.env'
APP_ENV_KEYS = ('CPT_STUDIO_SECRET_KEY', 'CPT_STUDIO_DB_PASSWORD')
DB_ENV_KEYS = ('POSTGRES_PASSWORD',)
CORTI_SOURCE = '/etc/quillmd-corti-test/credentials.env'
CORTI_TARGET = f'{ETC_DIR}/corti-credentials.env'
CORTI_KEYS = ('CORTI_CLIENT_ID', 'CORTI_CLIENT_SECRET', 'CORTI_ENVIRONMENT', 'CORTI_TENANT_NAME')
INITIAL_CREDENTIALS = 'initial-credentials.json'
AGENT_CREDENTIALS = Path('/home/claude/.cpt-studio/agent-credentials.json')

NGINX_AVAILABLE = Path('/etc/nginx/sites-available')
NGINX_ENABLED = Path('/etc/nginx/sites-enabled')
VHOST_NAME = 'quillmd-cpt'
VHOST_LINK_TARGET = f'{NGINX_AVAILABLE}/{VHOST_NAME}'
QUILLMD_VHOST_SHA256 = 'e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638'
NGINX_TEST = ['sudo', '-n', '/usr/sbin/nginx', '-t']
NGINX_RELOAD = ['sudo', '-n', '/usr/bin/systemctl', 'reload', 'nginx']
TEMPLATES = {'http': f'{APP}/deploy/nginx/cpt-quillmd-http.conf', 'https': f'{APP}/deploy/nginx/cpt-quillmd-https.conf'}
ACME_CHALLENGE_DIR = '/var/www/certbot/.well-known/acme-challenge'
LE_ACCOUNTS = 'accounts/acme-v02.api.letsencrypt.org/directory'
LE_DIRS = ('/etc/letsencrypt', '/var/lib/letsencrypt', '/var/log/letsencrypt', '/var/www/certbot')

# The two CMS public files the reference importer loads (it drops descriptors).
# Identity is pinned by size and sha256. Release and window are read from the
# archives (PPRRVU2026_Oct_* tables; MCR_MUE_PractitionerServices_Eff_10-01-2026).
# URLs are the files' own download links: RVU26D as recorded by the 2026-10-16
# reassessment's download receipt (rvu26d-download.json: url == final_url, same
# sha256), and the MUE file link on the CMS MUE page. Retrieval times are the
# operator's to state from those receipts.
REFERENCE_FILES = {
    'cms-pfs': {'name': 'rvu26d-updated-08-26-2026.zip', 'size': 6181360,
                'sha256': '521ff0f4ecbf13b5d99dc1dc04d9f82e5361e55c6b4b6b3033043598bf8406e6',
                'release': 'RVU26D', 'effective_start': '2026-10-01', 'effective_end': '2026-12-31',
                'url': 'https://www.cms.gov/files/zip/rvu26d-updated-08-26-2026.zip'},
    'cms-mue-practitioner': {'name': 'medicare-ncci-2026-q4-practitioner-services-mue-table.zip', 'size': 407831,
                             'sha256': '4574336755ba4e49b7c8ec07de5b74d3f0b8593e3e6192013631724981180d00',
                             'release': '2026-Q4', 'effective_start': '2026-10-01', 'effective_end': '2026-12-31',
                             'url': 'https://www.cms.gov/files/zip/'
                                    'medicare-ncci-2026-q4-practitioner-services-mue-table.zip'},
}

COMMAND_ENV = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
               'HOME': os.environ.get('HOME', '/home/claude'), 'DOCKER_HOST': 'unix:///run/docker.sock'}
SHA_RE = re.compile(r'[0-9a-f]{40}')
USERNAME_RE = re.compile(r'[a-z][a-z0-9_.-]{2,39}')
DISPLAY_RE = re.compile(r"[A-Za-z0-9 .,'()-]{0,80}")
AUTH_REF_RE = re.compile(r'[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*')
ENV_VALUE_RE = re.compile(r'[A-Za-z0-9_-]{32,256}')
PLACEHOLDER_RE = re.compile(r'@@([A-Z_]+)@@')
PROVISION_LINE_RE = re.compile(r'(created|kept) (human|agent) account (\S+) \((owner|reviewer|viewer)\)')
UNMATCHED_HOST = 'cpt-studio-unmatched.invalid'


class InstallError(Exception):
    """A refusal or failure. Messages never carry secret values."""

    def __init__(self, message, *, output=b'', details=None):
        super().__init__(message)
        self.output = output
        self.details = details


# --- small utilities -------------------------------------------------------------

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def run(argv, *, input=None, timeout=60, check=True, quiet=False):
    """Run a command with a fixed environment. ``quiet`` keeps its output out of errors."""
    try:
        proc = subprocess.run(argv, input=input, capture_output=True, timeout=timeout, env=COMMAND_ENV)
    except subprocess.TimeoutExpired:
        raise InstallError(f'{command_label(argv)} did not finish within {timeout} s.') from None
    if check and proc.returncode != 0:
        raise InstallError(f'{command_label(argv)} failed with exit {proc.returncode}.',
                           output=b'' if quiet else proc.stdout[-8192:] + proc.stderr[-8192:])
    return proc


def command_label(argv) -> str:
    words, skip = [Path(argv[0]).name], False
    for part in argv[1:]:
        if skip or part.startswith('-'):
            skip = part == '-C'
            continue
        words.append(part)
        if len(words) == 3:
            break
    return ' '.join(words)


def docker(*args, **kwargs):
    return run([DOCKER, *args], **kwargs)


def git(*args, check=True) -> str:
    return run(['git', '-C', str(ROOT), *args], check=check).stdout.decode().strip()


def write_private(directory: Path, name: str, data: bytes) -> Path:
    path = directory / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def assert_no_secret(outputs, values):
    for output in outputs:
        for value in values:
            if value and value.encode() in output:
                raise InstallError('A generated secret appeared in command output; nothing was recorded.')


# --- door, tree, arguments, receipts ---------------------------------------------

def check_door(environ, revision) -> dict:
    declaration = environ.get('RULED_MUTATION_DECLARATION', '')
    commit = environ.get('RULED_MUTATION_DECL_COMMIT', '')
    if not declaration or not commit:
        raise InstallError('Run through scripts/run-ruled-mutation.sh: RULED_MUTATION_DECLARATION and '
                           'RULED_MUTATION_DECL_COMMIT must both be set.')
    if not SHA_RE.fullmatch(commit):
        raise InstallError('RULED_MUTATION_DECL_COMMIT is not a full commit sha.')
    named = Path(declaration)
    # '..' is refused before any normalisation: the OS applies it AFTER following a link, os.path.abspath
    # collapses it lexically, so 'linkdir/../x' can open a file outside the tree that the checks never see.
    if '..' in named.parts:
        raise InstallError("The declaration path contains '..'; name the committed file itself.")
    absolute = Path(os.path.abspath(named if named.is_absolute() else ROOT / named))
    try:
        rel = absolute.relative_to(ROOT).as_posix()
    except ValueError:
        raise InstallError('The declaration is not a file inside this repository.') from None
    # The bytes are read from the repository path the git checks below run on, never from the raw value.
    path = ROOT / rel
    try:
        data = path.read_bytes()
        text = data.decode('utf-8')
    except (OSError, UnicodeDecodeError):
        raise InstallError('The declaration named by RULED_MUTATION_DECLARATION cannot be read.') from None
    if '<REVISION>' in text:
        raise InstallError('The declaration still carries the <REVISION> placeholder.')
    if revision not in text:
        raise InstallError('The declaration does not name the revision being installed.')
    rel = committed_declaration(path, commit, data)
    # The receipt names the repository path that was actually checked, never the raw environment value.
    return {'declaration': rel, 'declaration_commit': commit, 'declaration_sha256': sha256(data)}


def committed_declaration(path: Path, commit: str, data: bytes) -> str:
    """The phase is bound to a COMMITTED declaration, as the door's strict gate requires: inside this repository,
    tracked, unmodified, last touched by ``commit``, and byte-identical to that commit's copy. Two exported
    variables naming an arbitrary file and an arbitrary ancestor are refused."""
    if '..' in Path(path).parts:
        raise InstallError("The declaration path contains '..'; name the committed file itself.")
    absolute = Path(os.path.abspath(path))  # the path as named, links NOT followed
    try:
        rel = absolute.relative_to(ROOT.resolve()).as_posix()
        if absolute.resolve(strict=True) != absolute:
            raise InstallError('The declaration path passes through a symbolic link; name the committed file itself.')
    except (OSError, ValueError):
        raise InstallError('The declaration is not a file inside this repository.') from None
    if run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', '--', rel], check=False, quiet=True).returncode:
        raise InstallError('The declaration is not tracked; commit it and run through the door.')
    if run(['git', '-C', str(ROOT), 'diff', '--quiet', 'HEAD', '--', rel], check=False, quiet=True).returncode:
        raise InstallError('The declaration differs from its committed copy.')
    if git('log', '-1', '--format=%H', '--', rel) != commit:
        raise InstallError('RULED_MUTATION_DECL_COMMIT is not the commit that last touched the declaration.')
    if run(['git', '-C', str(ROOT), 'show', f'{commit}:{rel}'], check=False, quiet=True).stdout != data:
        raise InstallError("The declaration's bytes differ from the copy in RULED_MUTATION_DECL_COMMIT.")
    return rel


def check_tree(revision, declaration_commit) -> dict:
    if git('rev-parse', '--verify', '--quiet', f'{revision}^{{commit}}', check=False) != revision:
        raise InstallError('The revision is not a commit in this repository.')
    if git('status', '--porcelain', '--untracked-files=no'):
        raise InstallError('The tree has tracked modifications; refusing.')
    head = git('rev-parse', 'HEAD')
    for ancestor, what in ((revision, 'revision'), (declaration_commit, 'declaration commit')):
        if run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', ancestor, head], check=False).returncode:
            raise InstallError(f'The {what} is not HEAD or an ancestor of HEAD.')
    if head == revision:
        return {'head': head, 'mode': 'exact'}
    # A docs-only descendant (the declaration naming the merge commit) runs the same program.
    changed = git('diff', '--name-only', revision, head, '--', f'{APP}/', 'scripts/run-ruled-mutation.sh',
                  'scripts/lib/')
    if changed:
        raise InstallError(f'{len(changed.splitlines())} file(s) under {APP}/ or the ruled-mutation door changed '
                           'between the revision and HEAD; refusing.')
    return {'head': head, 'mode': 'descendant-without-runtime-change'}


PHASE_ARGUMENTS = {
    'pfs_zip': {'reference'}, 'mue_zip': {'reference'},
    'pfs_retrieved_at': {'reference'}, 'mue_retrieved_at': {'reference'},
    'provider_mode': {'app'}, 'authorization_ref': {'app'},
    'owner_username': {'provision'}, 'owner_display_name': {'provision'}, 'agent_username': {'provision'},
    'agent_display_name': {'provision'}, 'workspace_name': {'provision'}, 'reset_passwords': {'provision'},
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='CPT Studio ruled-mutation installer (one phase per run).')
    parser.add_argument('--phase', required=True, choices=list(PHASES))
    parser.add_argument('--revision', required=True)
    parser.add_argument('--receipts', required=True)
    parser.add_argument('--pfs-zip')
    parser.add_argument('--mue-zip')
    parser.add_argument('--pfs-retrieved-at', help='when the operator downloaded the PFS zip, ISO-8601 with offset')
    parser.add_argument('--mue-retrieved-at', help='when the operator downloaded the MUE zip, ISO-8601 with offset')
    parser.add_argument('--provider-mode', choices=('disabled', 'live'))
    parser.add_argument('--authorization-ref')
    parser.add_argument('--owner-username')
    parser.add_argument('--owner-display-name')
    parser.add_argument('--agent-username')
    parser.add_argument('--agent-display-name')
    parser.add_argument('--workspace-name')
    parser.add_argument('--reset-passwords', action='store_true', default=None)
    args = parser.parse_args(argv)
    problem = argument_problem(args)
    if problem:
        parser.error(problem)
    args.agent_username = args.agent_username or 'review-agent'
    args.agent_display_name = args.agent_display_name or 'CPT Studio review agent'
    args.owner_display_name = args.owner_display_name or ''
    args.workspace_name = args.workspace_name or 'Gastroenterology'
    return args


def argument_problem(args) -> str:
    if not SHA_RE.fullmatch(args.revision):
        return '--revision must be a full 40-character lowercase commit sha.'
    for name, phases in PHASE_ARGUMENTS.items():
        if getattr(args, name) is not None and args.phase not in phases:
            return f'--{name.replace("_", "-")} is not used by --phase {args.phase}.'
    if args.phase == 'reference':
        if not (args.pfs_zip and args.mue_zip and args.pfs_retrieved_at and args.mue_retrieved_at):
            return '--phase reference needs --pfs-zip, --mue-zip, --pfs-retrieved-at and --mue-retrieved-at.'
        for value in (args.pfs_retrieved_at, args.mue_retrieved_at):
            problem = retrieved_at_problem(value)
            if problem:
                return problem
    if args.phase == 'app':
        if args.provider_mode is None:
            return '--phase app needs an explicit --provider-mode (disabled or live).'
        if args.provider_mode == 'live' and not args.authorization_ref:
            return '--provider-mode live needs --authorization-ref (a ruling file tracked at the revision).'
        if args.provider_mode == 'disabled' and args.authorization_ref:
            return '--authorization-ref only applies to --provider-mode live.'
        reference = args.authorization_ref
        if reference and (not AUTH_REF_RE.fullmatch(reference) or '..' in reference.split('/') or len(reference) > 200):
            return '--authorization-ref must be a relative repository path.'
    if args.phase == 'provision':
        if not args.owner_username:
            return '--phase provision needs --owner-username.'
        agent = args.agent_username or 'review-agent'
        for value in (args.owner_username, agent):
            if not USERNAME_RE.fullmatch(value):
                return f'Username {value!r} must match {USERNAME_RE.pattern}.'
        if args.owner_username == agent:
            return 'The owner and agent usernames must differ.'
        for value in (args.owner_display_name, args.agent_display_name, args.workspace_name):
            if value is not None and not DISPLAY_RE.fullmatch(value):
                return 'Display and workspace names may use letters, digits, spaces and .,\'()- only (80 max).'
    return ''


def retrieved_at_problem(value) -> str:
    try:
        moment = dt.datetime.fromisoformat(value)
    except ValueError:
        return f'{value!r} is not an ISO-8601 date and time.'
    if moment.tzinfo is None:
        return f'{value!r} has no UTC offset.'
    if moment > dt.datetime.now(dt.timezone.utc):
        return f'{value!r} is in the future.'
    return ''


def prepare_receipts(text) -> Path:
    path = Path(text)
    if not path.is_absolute() or Path(os.path.normpath(path)) != path:
        raise InstallError('--receipts must be a normalised absolute path.')
    if path == ROOT or ROOT in path.parents:
        raise InstallError('--receipts must be outside the repository.')
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        os.mkdir(path, 0o700)
        info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise InstallError('--receipts must be a directory owned by this user with mode 0700.')
    if path.resolve() != path:
        raise InstallError('--receipts must not pass through a symbolic link.')
    return path


def write_receipt(directory: Path, phase: str, record: dict) -> Path:
    data = (json.dumps(record, indent=2, sort_keys=True) + '\n').encode()
    return write_private(directory, f'{phase}-{stamp()}.json', data)


def latest_receipt(directory: Path, phase: str, revision: str):
    """The newest successful receipt of ``phase`` for ``revision``, or None."""
    for path in sorted(directory.glob(f'{phase}-*.json'), reverse=True):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('phase') == phase and record.get('ok') and record.get('revision') == revision:
            return record
    return None


def require_receipt(ctx, phase):
    record = latest_receipt(ctx.receipts, phase, ctx.revision)
    if record is None:
        raise InstallError(f'No successful --phase {phase} receipt for this revision in {ctx.receipts}.')
    return record


class Context:
    def __init__(self, args, receipts):
        self.args = args
        self.phase = args.phase
        self.revision = args.revision
        self.receipts = receipts
        self.stamp = stamp()
        self._logs = 0

    def log(self, label, data: bytes) -> str:
        self._logs += 1
        return str(write_private(self.receipts, f'{self.phase}-{self.stamp}-{self._logs:02d}-{label}.log', data))


# --- root helper (pinned image, fixed code, verified cleanup) --------------------

HELPER_SOURCE_LIMIT = 256 * 1024
HELPER_PRELUDE = ('import base64,hashlib,json,os,secrets,stat,subprocess,sys\n'
                  'def read(path, limit=-1):\n'
                  '    with open(path, "rb") as handle:\n'
                  '        return handle.read(limit)\n')


def helper_bootstrap(deadline: float) -> str:
    # Armed before stdin is read, so a stalled pipe cannot outlive the deadline.
    return ('import os,signal,sys,time\n'
            'signal.signal(signal.SIGALRM,lambda *_: os._exit(124))\n'
            f'signal.setitimer(signal.ITIMER_REAL,max(0.001,{deadline!r}-time.time()))\n'
            f'source=sys.stdin.buffer.read({HELPER_SOURCE_LIMIT + 1})\n'
            f'if len(source)>{HELPER_SOURCE_LIMIT}: os._exit(125)\n'
            'exec(compile(source,"<cpt-studio-helper>","exec"))\n')


def helper_argv(name, token, mounts, network, deadline):
    argv = [DOCKER, 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', network,
            '--name', name, '--label', f'{HELPER_LABEL}={token}']
    for mount in mounts:
        argv += ['--mount', mount]
    return argv + [HELPER_IMAGE, 'python', '-I', '-B', '-c', helper_bootstrap(deadline)]


def helper_source(body: str, params: dict) -> str:
    payload = base64.b64encode(json.dumps(params).encode()).decode()
    return HELPER_PRELUDE + f'P=json.loads(base64.b64decode({payload!r}))\n' + body


def run_helper(body, params, *, mounts, network='none', timeout=60, sensitive=False) -> dict:
    """Run fixed helper code as root; return its final JSON line. ``sensitive`` drops stderr."""
    token = secrets.token_hex(12)
    name = f'cpt-studio-helper-{token}'
    source = helper_source(body, params).encode()
    proc = None
    try:
        proc = subprocess.run(helper_argv(name, token, mounts, network, time.time() + timeout), input=source,
                              capture_output=True, timeout=timeout + 15, env=COMMAND_ENV)
    except subprocess.TimeoutExpired:
        pass
    finally:
        remove_helper(name, token)
    if proc is None:
        raise InstallError(f'A root helper did not finish within {timeout} s; its container was removed.')
    if proc.returncode != 0:
        raise InstallError(f'A root helper failed with exit {proc.returncode}.',
                           output=b'' if sensitive else proc.stderr[-8192:])
    lines = proc.stdout.decode('utf-8', 'replace').strip().splitlines()
    try:
        result = json.loads(lines[-1])
    except (IndexError, ValueError):
        raise InstallError('A root helper returned no result.') from None
    if result.get('error'):
        raise InstallError(f'Root helper refused: {result["error"]}', details=result)
    return result


def remove_helper(name, token):
    """Return only once the named helper is gone; never touch a container we did not label."""
    template = '{{.Id}}|{{index .Config.Labels "' + HELPER_LABEL + '"}}'
    for _ in range(50):
        found = docker('container', 'inspect', '--format', template, name, check=False, timeout=15)
        if found.returncode:
            listed = docker('container', 'ls', '--all', '--quiet', '--filter', f'name=^/{name}$', check=False,
                            timeout=15)
            if listed.returncode == 0 and not listed.stdout.strip():
                return
        else:
            container_id, _, label = found.stdout.decode().strip().partition('|')
            if label != token:
                raise InstallError(f'{name} carries another label; refusing to remove it.')
            docker('rm', '--force', container_id, check=False, timeout=30)
        time.sleep(0.2)
    raise InstallError(f'Helper container {name} could not be confirmed removed.')


ROOT_MOUNT = 'type=bind,src=/,dst=/host,readonly'

H_STAT = '''
R = {}
for p in P['paths']:
    try:
        i = os.lstat('/host' + p)
    except FileNotFoundError:
        R[p] = {'exists': False}
        continue
    m = i.st_mode
    kind = 'link' if stat.S_ISLNK(m) else 'dir' if stat.S_ISDIR(m) else 'file' if stat.S_ISREG(m) else 'other'
    R[p] = {'exists': True, 'kind': kind, 'uid': i.st_uid, 'gid': i.st_gid, 'mode': oct(stat.S_IMODE(m))}
print(json.dumps({'paths': R}, sort_keys=True))
'''

# Path presence only: key material is never opened. Renewal configs hold paths
# and an account id, so their hashes show whether another lineage changed.
H_LE_STATE = '''
le = '/host/etc/letsencrypt'
R = {'dirs': {d: os.path.isdir('/host' + d) for d in P['dirs']}, 'live': {}, 'renewal': {}, 'accounts': []}
live = os.path.join(le, 'live')
if os.path.isdir(live):
    for name in sorted(os.listdir(live)):
        d = os.path.join(live, name)
        if os.path.isdir(d):
            R['live'][name] = {f: os.path.lexists(os.path.join(d, f))
                               for f in ('cert.pem', 'chain.pem', 'fullchain.pem', 'privkey.pem')}
renewal = os.path.join(le, 'renewal')
if os.path.isdir(renewal):
    for name in sorted(os.listdir(renewal)):
        if name.endswith('.conf'):
            with open(os.path.join(renewal, name), 'rb') as f:
                R['renewal'][name] = hashlib.sha256(f.read()).hexdigest()
accounts = os.path.join(le, P['accounts'])
if os.path.isdir(accounts):
    R['accounts'] = sorted(n for n in os.listdir(accounts) if os.path.isdir(os.path.join(accounts, n)))
print(json.dumps(R, sort_keys=True))
'''

H_ACME_WRITE = '''
path = os.path.join('/acme', P['name'])
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
try:
    os.fchmod(fd, 0o644)
    os.write(fd, P['content'].encode())
    os.fsync(fd)
finally:
    os.close(fd)
print(json.dumps({'written': True}))
'''

H_ACME_REMOVE = '''
path = os.path.join('/acme', P['name'])
if not os.path.lexists(path):
    R = {'removed': False, 'reason': 'absent'}
elif read(path) != P['content'].encode():
    R = {'error': 'the ACME probe file changed; left in place'}
else:
    os.unlink(path)
    R = {'removed': True}
print(json.dumps(R))
'''

H_ETC_DIR = '''
d = '/host-etc/cpt-studio'
try:
    i = os.lstat(d)
except FileNotFoundError:
    os.mkdir(d, 0o700)
    os.chown(d, 0, 0)
    os.chmod(d, 0o700)
    R = {'etc_dir': 'created'}
else:
    if stat.S_ISDIR(i.st_mode) and i.st_uid == 0 and i.st_gid == 0 and stat.S_IMODE(i.st_mode) == 0o700:
        R = {'etc_dir': 'present'}
    else:
        R = {'error': '/etc/cpt-studio exists but is not a root-owned 0700 directory'}
print(json.dumps(R))
'''

# Secrets are generated here, inside the helper; only names and modes leave it.
H_SECRETS = '''
T = '/target'
FILES = {'app': 'app.env', 'db': 'db.env', 'corti': 'corti-credentials.env'}

def names(raw):
    out = []
    for line in raw.decode('utf-8', 'replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('export '):
            s = s[7:].lstrip()
        name, sep, _ = s.partition('=')
        if sep and name.strip():
            out.append(name.strip())
    return out

def describe(name):
    i = os.lstat(os.path.join(T, name))
    return {'regular': stat.S_ISREG(i.st_mode), 'uid': i.st_uid, 'gid': i.st_gid, 'mode': oct(stat.S_IMODE(i.st_mode))}

def stage(name, data, uid, mode):
    tmp = os.path.join(T, '.' + name + '.new')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, uid, uid)
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return tmp

source = read('/source/credentials.env')
present = {k: os.path.lexists(os.path.join(T, v)) for k, v in FILES.items()}
missing = [k for k in P['corti_keys'] if k not in names(source)]
expected = {'app.env': {'regular': True, 'uid': 0, 'gid': 0, 'mode': '0o600'},
            'db.env': {'regular': True, 'uid': 0, 'gid': 0, 'mode': '0o600'},
            'corti-credentials.env': {'regular': True, 'uid': P['uid'], 'gid': P['uid'], 'mode': '0o400'}}
if missing:
    R = {'error': 'the Corti credentials file lacks key name(s): ' + ', '.join(missing)}
elif all(present.values()):
    found = {name: describe(name) for name in expected}
    problems = [name for name in expected if found[name] != expected[name]]
    if names(read(os.path.join(T, 'app.env'))) != P['app_keys']:
        problems.append('app.env keys')
    if names(read(os.path.join(T, 'db.env'))) != P['db_keys']:
        problems.append('db.env keys')
    if read(os.path.join(T, 'corti-credentials.env')) != source:
        problems.append('corti-credentials.env differs from its source')
    if problems:
        R = {'error': 'existing secrets are not as installed: ' + ', '.join(problems)}
    else:
        R = {'state': 'present', 'files': found}
elif any(present.values()):
    found = ', '.join(FILES[k] for k, v in present.items() if v)
    R = {'error': 'partial secrets present (' + found + '); resolve by hand'}
else:
    key = secrets.token_urlsafe(50)
    password = secrets.token_urlsafe(32)
    app_env = 'CPT_STUDIO_SECRET_KEY=' + key + '\\nCPT_STUDIO_DB_PASSWORD=' + password + '\\n'
    staged = [(stage('app.env', app_env.encode(), 0, 0o600), 'app.env'),
              (stage('db.env', ('POSTGRES_PASSWORD=' + password + '\\n').encode(), 0, 0o600), 'db.env'),
              (stage('corti-credentials.env', source, P['uid'], 0o400), 'corti-credentials.env')]
    for tmp, name in staged:
        os.link(tmp, os.path.join(T, name))
        os.unlink(tmp)
    d = os.open(T, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(d)
    os.close(d)
    found = {name: describe(name) for name in expected}
    R = {'state': 'created', 'files': found, 'corti_key_names_present': list(P['corti_keys'])}
    if any(found[name] != expected[name] for name in expected):
        R = {'error': 'secrets were written but their ownership or mode is wrong'}
print(json.dumps(R, sort_keys=True))
'''

H_READ_FILE = '''
data = read('/in/file', P['limit'] + 1)
print(json.dumps({'error': 'file too large'} if len(data) > P['limit'] else {'b64': base64.b64encode(data).decode()}))
'''

H_ROOT_FILE = '''
T = '/target'
staged = os.path.join(T, P['staged'])
final = os.path.join(T, P['final'])
op = P['op']
if op == 'state':
    R = {'final_exists': os.path.lexists(final), 'staged_exists': os.path.lexists(staged)}
elif op == 'stage':
    raw = base64.b64decode(P['content'])
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o600)
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    R = {'staged': True}
elif op == 'commit':
    if not os.path.lexists(staged):
        R = {'error': 'nothing staged'}
    elif os.path.lexists(final) and not P['replace']:
        R = {'error': 'the credentials file already exists'}
    else:
        if P['replace']:
            os.replace(staged, final)
        else:
            os.link(staged, final)
            os.unlink(staged)
        R = {'committed': True}
elif op == 'discard':
    if os.path.lexists(staged) and hashlib.sha256(read(staged)).hexdigest() == P['sha256']:
        os.unlink(staged)
        R = {'discarded': True}
    else:
        R = {'discarded': False}
else:
    R = {'error': 'unknown operation'}
print(json.dumps(R))
'''

# Writes only the quillmd-cpt file and link; asserts the quillmd vhost before and after.
H_VHOST = '''
A, E, name = '/available', '/enabled', P['name']
f, l = os.path.join(A, name), os.path.join(E, name)

def digest(path):
    with open(path, 'rb') as h:
        return hashlib.sha256(h.read()).hexdigest()

def state():
    regular = os.path.isfile(f) and not os.path.islink(f)
    return {'file_exists': os.path.lexists(f), 'file_sha256': digest(f) if regular else None,
            'link_exists': os.path.lexists(l), 'link_target': os.readlink(l) if os.path.islink(l) else None}

def put(path, raw, exclusive):
    target = path if exclusive else os.path.join(A, '.' + name + '.new')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o644)
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    if not exclusive:
        os.replace(target, path)

def sync(d):
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)

s = state()
op = P['op']
if digest(os.path.join(A, 'quillmd')) != P['quillmd_sha256']:
    R = {'error': 'the quillmd vhost sha256 is not the expected one'}
elif op == 'state':
    R = {}
elif op == 'install':
    if s['file_exists'] or s['link_exists']:
        R = {'error': 'quillmd-cpt is already present'}
    else:
        put(f, base64.b64decode(P['content']), True)
        os.symlink(P['link_target'], l)
        sync(A)
        sync(E)
        R = {'done': 'installed'}
elif op == 'replace':
    if s['file_sha256'] != P['expected_sha256'] or s['link_target'] != P['link_target']:
        R = {'error': 'quillmd-cpt is not in the expected state'}
    else:
        put(f, base64.b64decode(P['content']), False)
        sync(A)
        R = {'done': 'replaced'}
elif op == 'remove':
    if s['file_exists'] and s['file_sha256'] not in P['allowed_sha256']:
        R = {'error': 'quillmd-cpt holds content this installer did not write'}
    elif s['link_exists'] and s['link_target'] != P['link_target']:
        R = {'error': 'the quillmd-cpt link points somewhere else'}
    else:
        if s['link_exists']:
            os.unlink(l)
            sync(E)
        if s['file_exists']:
            os.unlink(f)
            sync(A)
        R = {'done': 'removed'}
else:
    R = {'error': 'unknown operation'}
if 'error' not in R and digest(os.path.join(A, 'quillmd')) != P['quillmd_sha256']:
    R = {'error': 'the quillmd vhost changed during the operation'}
R['state'] = state()
print(json.dumps(R, sort_keys=True))
'''

# Host certbot through a chroot. No --agree-tos or e-mail: it cannot register a
# new ACME account, so a missing account fails instead of creating one.
H_CERTBOT = '''
os.chroot('/host')
os.chdir('/')
cmd = ['/usr/bin/certbot', 'certonly', '--webroot', '-w', '/var/www/certbot', '-d', P['domain'],
       '--cert-name', P['domain'], '--non-interactive', '--keep-until-expiring', '--account', P['account']]
r = subprocess.run(cmd, capture_output=True, timeout=P['timeout'],
                   env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/root'})
print(json.dumps({'returncode': r.returncode, 'output': (r.stdout + r.stderr).decode('utf-8', 'replace')[-6000:]}))
'''

H_FILES_VOLUME = '''
root = '/files'
os.chown(root, P['uid'], P['uid'])
os.chmod(root, 0o700)
R = {'root': 'owned'}
if P.get('sha256'):
    d = os.path.join(root, 'reference')
    os.makedirs(d, mode=0o700, exist_ok=True)
    os.chown(d, P['uid'], P['uid'])
    os.chmod(d, 0o700)
    data = read('/in/source.zip')
    dest = os.path.join(d, P['sha256'] + '.zip')
    if hashlib.sha256(data).hexdigest() != P['sha256']:
        R = {'error': 'the mounted reference file does not match its pinned sha256'}
    elif os.path.lexists(dest):
        same = hashlib.sha256(read(dest)).hexdigest() == P['sha256']
        R = {'copied': False} if same else {'error': 'an existing reference copy differs from its name'}
    else:
        tmp = dest + '.new'
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchown(fd, P['uid'], P['uid'])
            os.fchmod(fd, 0o400)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.link(tmp, dest)
        os.unlink(tmp)
        R = {'copied': True}
print(json.dumps(R))
'''


def helper_stat(paths) -> dict:
    return run_helper(H_STAT, {'paths': list(paths)}, mounts=[ROOT_MOUNT])['paths']


def le_state() -> dict:
    return run_helper(H_LE_STATE, {'dirs': list(LE_DIRS) + [ACME_CHALLENGE_DIR], 'accounts': LE_ACCOUNTS},
                      mounts=[ROOT_MOUNT])


def read_protected_env(path, keys) -> bytes:
    """A root-only env file's bytes, validated; they go to docker on stdin and nowhere else."""
    result = run_helper(H_READ_FILE, {'limit': 4096}, mounts=[f'type=bind,src={path},dst=/in/file,readonly'],
                        sensitive=True)
    data = base64.b64decode(result['b64'])
    validate_env_text(data.decode('utf-8'), keys)
    return data


def validate_env_text(text, keys):
    seen = []
    for line in text.splitlines():
        if not line.strip():
            continue
        name, sep, value = line.partition('=')
        if not sep or name not in keys:
            raise InstallError('A protected environment file has an unexpected line.')
        if name in seen:
            raise InstallError(f'A protected environment file repeats {name}.')
        if not ENV_VALUE_RE.fullmatch(value):
            raise InstallError(f'{name} in a protected environment file has an unexpected form.')
        seen.append(name)
    if sorted(seen) != sorted(keys):
        raise InstallError('A protected environment file lacks: ' + ', '.join(k for k in keys if k not in seen) + '.')


# --- nginx -------------------------------------------------------------------------

def render(template: str, values: dict) -> str:
    """Substitute every @@NAME@@ exactly; refuse unknown, unused or invalid values."""
    names = PLACEHOLDER_RE.findall(template)
    if set(names) != set(values):
        raise InstallError(f'Template placeholders {sorted(set(names))} do not match values {sorted(values)}.')
    if not re.fullmatch(r'[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+', values.get('DOMAIN', '')):
        raise InstallError('DOMAIN must be a lowercase host name.')
    if 'UPSTREAM' in values and not re.fullmatch(r'127\.0\.0\.1:[1-9][0-9]{1,4}', values['UPSTREAM']):
        raise InstallError('UPSTREAM must be a loopback host:port.')
    rendered, count = PLACEHOLDER_RE.subn(lambda match: values[match.group(1)], template)
    if count != len(names) or '@@' in rendered:
        raise InstallError('Template substitution did not apply exactly once per placeholder.')
    return rendered


def rendered_vhosts(revision) -> dict:
    texts = {kind: run(['git', '-C', str(ROOT), 'show', f'{revision}:{path}']).stdout.decode('utf-8')
             for kind, path in TEMPLATES.items()}
    http_conf = render(texts['http'], {'DOMAIN': DOMAIN})
    https_conf = render(texts['https'], {'DOMAIN': DOMAIN, 'UPSTREAM': UPSTREAM})
    if not https_conf.startswith(http_conf):
        raise InstallError('The HTTPS vhost must begin with the HTTP stage byte-for-byte (renewals depend on it).')
    for conf in (http_conf, https_conf):
        if any(set(args[1:]) & {'default_server', 'default'} for block in parse_server_blocks(conf)
               for args in block['listen']):
            raise InstallError('The vhost must never claim default_server.')
    return {'http': http_conf, 'https': https_conf}


def nginx_tokens(text):
    """(kind, value) tokens: word | quoted | punct. Comments start only at a token boundary."""
    tokens, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '#':
            end = text.find('\n', i)
            i = n if end < 0 else end
        elif c in '{};':
            tokens.append(('punct', c))
            i += 1
        elif c in '"\'':
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == '\\' else 1
            tokens.append(('quoted', text[i + 1:j]))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '{};':
                if text[j] == '$' and j + 1 < n and text[j + 1] == '{':
                    j = text.find('}', j) + 1 or n
                else:
                    j += 1
            tokens.append(('word', text[i:j]))
            i = j
    return tokens


def parse_server_blocks(text):
    """Each top-level-or-nested ``server { }`` block's listen arguments and server names."""
    blocks, stack, words = [], [], []
    for kind, value in nginx_tokens(text):
        if kind == 'punct' and value == '{':
            block = {'listen': [], 'server_names': []} if words[:1] == ['server'] else None
            if block is not None:
                blocks.append(block)
            stack.append(block)
            words = []
        elif kind == 'punct' and value == '}':
            if not stack:
                raise ValueError('unbalanced braces')
            stack.pop()
            words = []
        elif kind == 'punct':
            if words and stack and stack[-1] is not None:
                if words[0] == 'listen':
                    stack[-1]['listen'].append(words[1:])
                elif words[0] == 'server_name':
                    stack[-1]['server_names'].extend(words[1:])
            words = []
        else:
            words.append(value)
    if stack:
        raise ValueError('unbalanced braces')
    return blocks


def parse_listen(args):
    match = re.fullmatch(r'(?:(\[[0-9a-fA-F:.]+\]|[0-9.]+|\*):)?([0-9]{1,5})', args[0]) if args else None
    if not match:
        return None
    address = match.group(1)
    if address in (None, '*', '0.0.0.0'):
        connect = '127.0.0.1'
    elif address == '[::]':
        connect = '::1'
    else:
        connect = address.strip('[]')
    return {'port': int(match.group(2)), 'ssl': 'ssl' in args[1:], 'connect': connect}


def routing_targets(config_texts):
    """Every (name, port, tls, connect address) the enabled vhosts answer, plus unmatched probes."""
    targets = set()
    for text in config_texts:
        for block in parse_server_blocks(text):
            listens = [item for item in (parse_listen(args) for args in block['listen']) if item]
            for name in block['server_names']:
                if name in ('_', '') or name.startswith('~') or '*' in name or name.startswith('$'):
                    continue
                for listen in listens:
                    targets.add((name, listen['port'], listen['ssl'], listen['connect']))
    for port, tls in ((80, False), (443, True)):
        targets.add((UNMATCHED_HOST, port, tls, '127.0.0.1'))
    return sorted(targets)


NGINX_WARNING_RE = re.compile(r'(?:nginx: \[warn\] |\d{4}/\d\d/\d\d \d\d:\d\d:\d\d \[warn\] \d+#\d+: )(.+)')


def nginx_warnings(text):
    """The warning messages of `nginx -t`, which prints 'nginx: [warn] <message>' or, when its startup log is
    stderr (this host's Ubuntu build), '<date> <time> [warn] <pid>#<tid>: <message>'. Only the message (it names
    file:line) is kept: the timestamp and pid differ on every run and would make every warning look new."""
    found = (NGINX_WARNING_RE.fullmatch(line.strip()) for line in text.splitlines())
    return sorted({match.group(1) for match in found if match})


def nginx_test() -> dict:
    proc = run(NGINX_TEST, check=False, timeout=30)
    text = (proc.stdout + proc.stderr).decode('utf-8', 'replace')
    return {'ok': proc.returncode == 0 and 'test is successful' in text, 'warnings': nginx_warnings(text),
            'output': text}


def nginx_reload():
    run(NGINX_RELOAD, timeout=30)


def live_vhost_bytes():
    """The bytes of sites-available/quillmd-cpt as they are now (a regular file only), or None."""
    available = NGINX_AVAILABLE / VHOST_NAME
    if not available.is_file() or available.is_symlink():
        return None
    return available.read_bytes()


def vhost_state() -> dict:
    available, enabled = NGINX_AVAILABLE / VHOST_NAME, NGINX_ENABLED / VHOST_NAME
    regular = available.is_file() and not available.is_symlink()
    return {'file_exists': os.path.lexists(available),
            'file_sha256': sha256(available.read_bytes()) if regular else None,
            'link_exists': os.path.lexists(enabled),
            'link_target': os.readlink(enabled) if enabled.is_symlink() else None}


def vhost_operation(op, **params) -> dict:
    params.update(op=op, name=VHOST_NAME, quillmd_sha256=QUILLMD_VHOST_SHA256, link_target=VHOST_LINK_TARGET)
    return run_helper(H_VHOST, params, mounts=[f'type=bind,src={NGINX_AVAILABLE},dst=/available',
                                               f'type=bind,src={NGINX_ENABLED},dst=/enabled'])


def nginx_file_state() -> dict:
    available = {}
    for path in sorted(NGINX_AVAILABLE.iterdir()):
        try:
            available[path.name] = sha256(path.read_bytes())
        except PermissionError:
            available[path.name] = 'unreadable'
    enabled = {path.name: os.readlink(path) if path.is_symlink() else 'file:' + sha256(path.read_bytes())
               for path in sorted(NGINX_ENABLED.iterdir())}
    conf_d = Path('/etc/nginx/conf.d')
    return {'available': available, 'enabled': enabled,
            'nginx_conf_sha256': sha256(Path('/etc/nginx/nginx.conf').read_bytes()),
            'conf_d': sorted(path.name for path in conf_d.iterdir()) if conf_d.is_dir() else []}


def enabled_config_texts():
    return [path.read_text(encoding='utf-8', errors='replace')
            for path in sorted(NGINX_ENABLED.iterdir()) if path.name != VHOST_NAME]


# --- HTTP probes -------------------------------------------------------------------

class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, *, connect_ip, **kwargs):
        super().__init__(host, **kwargs)
        self._connect_ip = connect_ip

    def connect(self):
        self.sock = socket.create_connection((self._connect_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, *, connect_ip, **kwargs):
        super().__init__(host, **kwargs)
        self._connect_ip = connect_ip

    def connect(self):
        sock = socket.create_connection((self._connect_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


PROBE_HEADERS = ('location', 'content-type', 'strict-transport-security', 'x-content-type-options',
                 'referrer-policy', 'x-robots-tag')


def probe(scheme, host, path='/', *, port=None, connect_ip=None, verify=True, method='GET', headers=None,
          timeout=5.0):
    """One request with SNI/Host = ``host``; never follows redirects. Errors become data."""
    port = port or (443 if scheme == 'https' else 80)
    target = connect_ip or host
    if scheme == 'https':
        context = ssl.create_default_context()
        if not verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        connection = _PinnedHTTPSConnection(host, connect_ip=target, port=port, context=context, timeout=timeout)
    else:
        connection = _PinnedHTTPConnection(host, connect_ip=target, port=port, timeout=timeout)
    result = {}
    try:
        connection.request(method, path, headers={'Host': host, 'User-Agent': 'cpt-studio-installer',
                                                  'Connection': 'close', **(headers or {})})
        if scheme == 'https':
            result['cert_sha256'] = sha256(connection.sock.getpeercert(binary_form=True))
        response = connection.getresponse()
        body = b'' if method == 'HEAD' else response.read(65537)
        result['status'] = response.status
        result['headers'] = {name: response.headers.get_all(name) for name in PROBE_HEADERS
                             if response.headers.get_all(name)}
        if body and (response.headers.get('content-type') or '').startswith('application/json') and len(body) <= 65536:
            result['json'] = json.loads(body)
        elif body:
            result['body_sha256'] = sha256(body)
    except (OSError, http.client.HTTPException, ValueError) as error:
        result['error'] = type(error).__name__
    finally:
        connection.close()
    return result


def routing_snapshot(targets) -> dict:
    snapshot = {}
    for name, port, tls, connect in targets:
        result = probe('https' if tls else 'http', name, '/', port=port, connect_ip=connect, verify=False,
                       method='HEAD')
        snapshot[f'{"https" if tls else "http"}://{name}:{port}@{connect}'] = {
            key: result[key] for key in ('status', 'error', 'cert_sha256') if key in result}
    return snapshot


def routing_diff(before: dict, after: dict, ignore_host=DOMAIN):
    keys = {key for key in set(before) | set(after) if f'://{ignore_host}:' not in key}
    return sorted(key for key in keys if before.get(key) != after.get(key))


def health_ok(body, revision) -> bool:
    return (isinstance(body, dict) and body.get('status') == 'ok' and body.get('service') == 'cpt-studio'
            and body.get('data_mode') == 'synthetic-only' and body.get('database') == 'ok'
            and body.get('release') == revision)


def poll(check, *, attempts, interval):
    """Bounded observation (reloads are asynchronous): the last result and whether it passed."""
    observations = []
    for attempt in range(attempts):
        passed, observed = check()
        observations.append({'attempt': attempt, **observed})
        if passed:
            return True, observations
        time.sleep(interval)
    return False, observations


def app_health() -> dict:
    result = probe('https', APP_HEALTH_HOST, '/health/', timeout=10)
    return {key: result.get(key) for key in ('status', 'json', 'error')}


def cotenant_check() -> dict:
    proc = run(['bash', str(ROOT / 'scripts' / 'check-cotenants.sh')], check=False, timeout=120)
    rows = re.findall(r'^\s+\S+\s+(\S+)\s+(\d{3})\s+(\d{3})', proc.stdout.decode('utf-8', 'replace'), re.M)
    return {'returncode': proc.returncode, 'observed': {host: got for host, _want, got in rows}}


def cpt_probes() -> dict:
    return {'http': probe('http', DOMAIN, '/', connect_ip='127.0.0.1', method='HEAD'),
            'https': probe('https', DOMAIN, '/', connect_ip='127.0.0.1', verify=False, method='HEAD')}


# --- docker objects ----------------------------------------------------------------

def inspect(kind, name):
    proc = docker(kind, 'inspect', name, check=False, timeout=30)
    if proc.returncode == 0:
        return json.loads(proc.stdout)[0]
    if re.search(rb'(?i)no such|not found', proc.stderr):
        return None
    raise InstallError(f'docker {kind} inspect {name} failed (exit {proc.returncode}).')


def labels_of(obj) -> dict:
    return (obj.get('Config') or {}).get('Labels') or obj.get('Labels') or {}


def owned(obj, role) -> bool:
    labels = labels_of(obj)
    return labels.get(LABEL) == '1' and labels.get(ROLE_LABEL) == role


def docker_positive_control() -> str:
    version = docker('version', '--format', '{{.Server.Version}}', timeout=15).stdout.decode().strip()
    if not version:
        raise InstallError('The Docker daemon did not report a version; cannot tell anything about it.')
    return version


def list_json(*args) -> list:
    output = docker(*args, '--format', '{{json .}}', timeout=30).stdout.decode()
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def is_transient(name) -> bool:
    return name.startswith(('cpt-studio-helper-', 'cpt-studio-oneshot-'))


def containers() -> dict:
    return {row['Names']: {'id': row['ID'], 'image': row['Image'], 'state': row['State']}
            for row in list_json('container', 'ls', '--all', '--no-trunc') if not is_transient(row['Names'])}


def volumes() -> list:
    return sorted(row['Name'] for row in list_json('volume', 'ls'))


def networks() -> list:
    return sorted(row['Name'] for row in list_json('network', 'ls'))


def listening_ports(proc_texts) -> set:
    ports = set()
    for text in proc_texts:
        for line in text.splitlines()[1:]:
            fields = line.split()
            if len(fields) > 3 and fields[3] == '0A':
                ports.add(int(fields[1].rsplit(':', 1)[1], 16))
    return ports


def host_listening_ports() -> set:
    return listening_ports(Path(f'/proc/net/{name}').read_text() for name in ('tcp', 'tcp6')
                           if Path(f'/proc/net/{name}').exists())


def published_by(port) -> list:
    return sorted(row['Names'] for row in list_json('container', 'ls', '--no-trunc')
                  if re.search(rf'(^|[ ,]){re.escape("127.0.0.1")}:{port}->', row.get('Ports', '')))


def foreign_uid_tasks(uid, own_container_ids, proc_root=Path('/proc')) -> int:
    """Threads owned by ``uid`` outside our containers. RLIMIT_NPROC counts every one of them."""
    count = 0
    for entry in os.scandir(proc_root):
        if not entry.name.isdigit():
            continue
        try:
            status = (proc_root / entry.name / 'status').read_text()
            cgroup = (proc_root / entry.name / 'cgroup').read_text()
        except OSError:  # the process ended mid-scan
            continue
        fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
        if int(fields['Uid'].split()[0]) == uid and not any(cid in cgroup for cid in own_container_ids):
            count += int(fields['Threads'])
    return count


def own_service_ids() -> list:
    return [container['Id'] for role, name in SERVICES.items()
            if (container := inspect('container', name)) is not None and owned(container, role)]


def port_problem(port, owner) -> str:
    if port not in host_listening_ports():
        return ''
    holders = published_by(port)
    return '' if holders == [owner] else f'port {port} is in use by {holders or "a non-container process"}'


def ensure_network() -> str:
    network = inspect('network', NETWORK)
    if network is None:
        docker('network', 'create', '--driver', 'bridge', '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=network',
               NETWORK)
        return 'created'
    if not owned(network, 'network') or network.get('Driver') != 'bridge' or network.get('Internal'):
        raise InstallError(f'Network {NETWORK} exists but is not the CPT Studio bridge network.')
    return 'present'


def ensure_volume(name, role) -> str:
    volume = inspect('volume', name)
    if volume is None:
        docker('volume', 'create', '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}={role}', name)
        return 'created'
    if not owned(volume, role):
        raise InstallError(f'Volume {name} exists but is not the CPT Studio {role} volume.')
    return 'present'


def files_volume_helper(params, extra_mounts=()) -> dict:
    return run_helper(H_FILES_VOLUME, {'uid': APP_UID, **params},
                      mounts=[f'type=volume,src={FILES_VOLUME},dst=/files', *extra_mounts])


def image_tag(revision) -> str:
    return f'cpt-studio:{revision[:12]}'


def installed_image(ctx) -> str:
    record = require_receipt(ctx, 'image')
    image = inspect('image', record['details']['image_id'])
    if image is None:
        raise InstallError('The image recorded by the image phase is no longer present.')
    labels = labels_of(image)
    if labels.get(REVISION_LABEL) != ctx.revision or not owned(image, 'app-image'):
        raise InstallError('The recorded image does not carry this revision and the CPT Studio label.')
    return image['Id']


def hardening(memory, pids, tmp_size, user=f'{APP_UID}:{APP_UID}'):
    return ['--read-only', '--tmpfs', f'/tmp:rw,noexec,nosuid,nodev,size={tmp_size}', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', user, '--memory', memory, '--memory-swap', memory,
            '--pids-limit', str(pids), '--ulimit', 'core=0']


def runtime_env(provider_mode, authorization_ref, *, credentials=False):
    values = {'CPT_STUDIO_DB_HOST': DB_CONTAINER, 'CPT_STUDIO_DB_PORT': '5432', 'CPT_STUDIO_DB_NAME': DB_NAME,
              'CPT_STUDIO_DB_USER': DB_USER, 'CPT_STUDIO_HTTPS': '1', 'CPT_STUDIO_TRUST_PROXY': '1',
              'CPT_STUDIO_PROVIDER_MODE': provider_mode, 'CPT_STUDIO_AUTHORIZATION_REF': authorization_ref}
    if credentials:
        values['CPT_STUDIO_CORTI_CREDENTIALS_FILE'] = CREDENTIALS_IN_CONTAINER
    flags = []
    for name, value in values.items():
        flags += ['-e', f'{name}={value}']
    return flags


def service_args(role, image_id, revision, provider_mode, authorization_ref):
    """docker run arguments for a long-running role; secrets arrive on stdin as an env-file."""
    live = provider_mode == 'live'
    common = ['--name', SERVICES[role], '--pull=never', '--restart', 'unless-stopped', '--network', NETWORK,
              '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}={role}', '--label', f'{REVISION_LABEL}={revision}',
              '--log-opt', 'max-size=10m', '--log-opt', 'max-file=5', '--stop-timeout', str(STOP_SECONDS[role]),
              '--mount', f'type=volume,src={FILES_VOLUME},dst={STATE_DIR}', '--env-file', '/dev/stdin']
    if role == 'web':
        # The path, never the file. A context change in the web builds the request it would send to tell a
        # re-check from a re-send (jobs._run_answers); building a request opens nothing, and only the worker
        # sends. Without the path, live mode had no provider in the web, so every setting or billing save
        # re-predicted and the worker re-sent a failed or not-sent request (pre-install review, 2026-10-26).
        return [*common, *hardening('768m', 128, '256m'), '-p', f'127.0.0.1:{WEB_PORT}:8000',
                *runtime_env(provider_mode, authorization_ref, credentials=live), image_id, 'web']
    extra = ['--mount', f'type=bind,src={CORTI_TARGET},dst={CREDENTIALS_IN_CONTAINER},readonly'] if live else []
    return [*common, *hardening('1536m', 256, '1g'), '--no-healthcheck', *extra,
            *runtime_env(provider_mode, authorization_ref, credentials=live), image_id, 'worker']


def db_args() -> list:
    return ['--name', DB_CONTAINER, '--pull=never', '--restart', 'unless-stopped', '--network', NETWORK,
            '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=db', '-p', f'127.0.0.1:{DB_PORT}:5432',
            '--user', f'{POSTGRES_UID}:{POSTGRES_UID}', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', '512m', '--memory-swap', '512m', '--pids-limit', '256', '--shm-size', '128m',
            '--ulimit', 'core=0', '--log-opt', 'max-size=10m', '--log-opt', 'max-file=5', '--stop-timeout', '60',
            '--mount', f'type=volume,src={DB_VOLUME},dst=/var/lib/postgresql/data',
            '-e', f'POSTGRES_USER={DB_USER}', '-e', f'POSTGRES_DB={DB_NAME}', '--env-file', '/dev/stdin',
            POSTGRES_IMAGE]


def oneshot(image_id, command, env_bytes, *, mounts=(), user=f'{APP_UID}:{APP_UID}', timeout=600,
            network=None, credentials=False):
    """A --rm container of the app image with provider calls disabled; returns the completed process."""
    name = f'cpt-studio-oneshot-{secrets.token_hex(8)}'
    if credentials:
        mounts = [*mounts, f'type=bind,src={CORTI_TARGET},dst={CREDENTIALS_IN_CONTAINER},readonly']
    argv = [DOCKER, 'run', '--rm', '--name', name, '--pull=never', '--network', network or NETWORK,
            '--no-healthcheck', '--log-driver=none', '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=oneshot',
            *hardening('768m', 128, '256m', user=user), '--env-file', '/dev/stdin',
            *runtime_env('disabled', '', credentials=credentials),
            *[part for mount in mounts for part in ('--mount', mount)], image_id, *command]
    try:
        return run(argv, input=env_bytes, timeout=timeout, check=False)
    finally:
        leftover = inspect('container', name)
        if leftover is not None and owned(leftover, 'oneshot'):
            docker('rm', '--force', leftover['Id'], check=False)


CREDENTIALS_CHECK = ('from django.conf import settings\n'
                     'from studio.providers.credentials import load_corti_credentials\n'
                     'load_corti_credentials(settings.CORTI_CREDENTIALS_FILE)\n'
                     "print('corti-credentials-parse-ok')\n")

# Run by `manage shell -c` in an image of the app (APP_SCRIPT_PRELUDE gives it P, the parameters, and ANSWER); each
# prints one ANSWER line. UNRUNNABLE_STAGES uses only what every revision's models have (057a7d39's included): it is
# also run in the image of the pair an undo restores (stage_kinds_of). The others run in this revision's own image.
APP_SCRIPT_ANSWER = 'cpt-studio-answer '
APP_SCRIPT_PRELUDE = 'import base64, json\nP = json.loads(base64.b64decode({payload!r}))\nANSWER = {answer!r}\n'
# The stage kinds every revision's worker runs (the installed revision 057a7d39's STAGES). An undo keeps open stages of
# the kinds the next worker runs - read from that worker's own image (stage_kinds_of) - and only these when it has no
# image to ask (refutation p1, security-0).
COMMON_STAGE_KINDS = ('analyze', 'assess', 'extract', 'predict')
# What this revision recorded that an older revision's web and worker would act on under their own rules (refutation
# p1, migrate-0/-1), read in this revision's image as the installed revision 057a7d39 reads the rows - the oldest a
# rollback goes back to. {encounter id: reasons}:
#   unknown  - a provider outcome still unknown: its reconcile requests the current context under its rules (a member
#              date conflict read as no date, so a request without one; never asking whether that request failed).
#   outcome  - a request of the current revision that failed, or was not sent though it went through the send, to
#              which no answer is retained that it would reuse, and that its next metadata save or Resume could make
#              again (round-7c8 skeptic, sk:0/sk:1: after a rollback such a request was re-sent byte-identical behind a
#              setting save, which neither revision alone does). A metadata save requests the member's date when one is
#              set, else its own reading of the document's date - which this image cannot know, so any of them - and
#              sends it unless its run in use (the newest finished run, whatever it was made for: a hold and a second
#              review included) carries that request; a Resume of a stopped predict (or of a stopped assess of an
#              earlier context) requests the current context's stored date, and of a stopped extract or analyze what a
#              fresh reading gives, without that comparison.
#   conflict - the current context holds a member date conflict and the latest stage is a stopped predict, or a stopped
#              assess of an earlier context: its Resume requests the current context, which it reads as having no date.
UNDO_HAZARDS = '''
def undo_hazards():
    import datetime
    import re
    from django.db.models import Q
    from studio import models, review
    from studio.gi import context as gi_context
    Run, Job = models.ProviderRun, models.Job
    found = {}
    for pk in Run.objects.filter(state=Run.UNKNOWN, reconciled_at__isnull=True).values_list('encounter_id', flat=True):
        found.setdefault(str(pk), set()).add('unknown')
    finished = (Run.SUCCEEDED, Run.FAILED, Run.NOT_SENT, Run.UNKNOWN)
    swept = Q(state=Run.NOT_SENT) & Q(started_at__isnull=True) & ~Q(request_sha256='')

    def request(run):
        return (run.provider, run.adapter_version, run.request_sha256)

    def day(value, *, member=False):  # a date as 057a7d39 reads one, else None: a member's value must also be
        try:                            # written YYYY-MM-DD (its merge_user_values); a stored one need not be
            if member and not re.fullmatch('[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
                return None
            return datetime.date.fromisoformat(value)
        except (TypeError, ValueError):
            return None
    for encounter in models.Encounter.objects.filter(current_revision__isnull=False).select_related('current_context'):
        runs = (Run.objects.filter(revision_id=encounter.current_revision_id, state__in=finished).exclude(swept)
                .order_by('-created_at', '-pk'))
        in_use = runs.first()  # 057a7d39's run in use: the newest finished run, whatever it was made for
        if in_use is not None and in_use.state == Run.UNKNOWN and in_use.reconciled_at is not None:
            in_use = None  # a reconciled unknown outcome no longer stands: the next request is made, whatever it is
        answered = request(in_use) if in_use is not None and in_use.request_sha256 else None
        # the requests it would send again: failed, or not sent through the send, and no answer retained that its
        # predict reuses (a SUCCEEDED run of the same request anywhere in the workspace, not itself a reuse)
        again = [run for run in runs.filter(purpose=Run.PRIMARY, state__in=(Run.FAILED, Run.NOT_SENT))
                 .exclude(request_sha256='')
                 if not Run.objects.filter(encounter__workspace_id=encounter.workspace_id, provider=run.provider,
                                           adapter_version=run.adapter_version, request_sha256=run.request_sha256,
                                           state=Run.SUCCEEDED, reused_from__isnull=True).exists()]
        member = (encounter.user_values or {}).get('service_date')
        member = day(member.strip(), member=True) if isinstance(member, str) and member.strip() else None
        context, latest = encounter.current_context, review.latest_job(encounter)
        resumed = latest is not None and latest.state == Job.CANCELLED and review.can_resume(encounter)
        current = resumed and context is not None and (
            latest.kind == Job.PREDICT or (latest.kind == Job.ASSESS and latest.context_id != context.pk))
        fact = ((context.facts or {}).get('service_date') or {}) if context is not None else {}
        stored = day(fact.get('value')) if fact.get('origin') in ('document', 'user') else None
        if (any(request(run) != answered and (member is None or run.service_date == member) for run in again)
                or (current and any(run.service_date == stored for run in again))
                or (resumed and latest.kind in (Job.EXTRACT, Job.ANALYZE)
                    and any(member is None or run.service_date == member for run in again))):
            found.setdefault(str(encounter.pk), set()).add('outcome')
        if (current and gi_context.is_member_conflict((context.facts or {}).get('service_date'))):
            found.setdefault(str(encounter.pk), set()).add('conflict')
    return {pk: sorted(reasons) for pk, reasons in sorted(found.items())}
'''
UNDO_HAZARDS_READ = UNDO_HAZARDS + "print(ANSWER + json.dumps({'hazards': undo_hazards()}))\n"
# Close what a pair being undone left open since it started (refutation r1, migrate-3/-4): every stage it queued, ran
# or left resumable (cancelled) becomes FAILED with P['note'] - failed, not cancelled, so no revision's web offers a
# Resume for it - and every provider run it left unsettled is settled as the stale-stage sweep settles one (sending:
# unknown, reserved: not sent). So, whichever pair created it, does every stage of a kind the next worker does not run
# (P['kinds'] are those it runs) that is queued, running, or cancelled as its encounter's latest stage (what a Resume
# runs again): that worker ends on it (refutation p1, security-0: a second review stopped under an earlier pair of a
# revision that runs it outlived the window). Nothing finished is touched and no row is removed. The answer names,
# after the close, what the next pair would still act on wrongly (UNDO_HAZARDS).
CLOSE_STAGES = UNDO_HAZARDS + f'COMMON_STAGE_KINDS = {list(COMMON_STAGE_KINDS)!r}\n' + '''
import datetime
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from studio import models, review
Job, Run = models.Job, models.ProviderRun
since, now = datetime.datetime.fromisoformat(P['since']), timezone.now()
kept = set(P.get('kinds') or COMMON_STAGE_KINDS)
with transaction.atomic():
    unrunnable, in_flight = [], Q(created_at__gte=since)
    for pk, state, revision_id, encounter_id, started in (
            Job.objects.exclude(kind__in=kept).filter(state__in=(Job.QUEUED, Job.RUNNING, Job.CANCELLED))
            .values_list('pk', 'state', 'revision_id', 'encounter_id', 'started_at')):
        if state != Job.CANCELLED or (
                Job.objects.filter(revision_id=revision_id).order_by('-created_at', '-pk').values_list('pk', flat=True)
                .first() == pk
                and models.Encounter.objects.filter(pk=encounter_id, current_revision_id=revision_id).exists()):
            unrunnable.append(pk)
            if state == Job.RUNNING and started is not None:  # what it was sending is settled as the window's is
                in_flight |= Q(revision_id=revision_id, created_at__gte=started)
    stages = Job.objects.filter(Q(created_at__gte=since, state__in=(Job.QUEUED, Job.RUNNING, Job.CANCELLED))
                                | Q(started_at__gte=since, state=Job.RUNNING) | Q(pk__in=unrunnable))
    encounters = sorted({str(pk) for pk in stages.values_list('encounter_id', flat=True)})
    kinds = sorted(set(stages.values_list('kind', flat=True)))
    runs = Run.objects.filter(in_flight)
    unknown = runs.filter(state=Run.SENDING).update(
        state=Run.UNKNOWN, finished_at=now, error='The worker stopped while the request was in flight.')
    not_sent = runs.filter(state=Run.RESERVED).update(
        state=Run.NOT_SENT, finished_at=now, error='The worker stopped before sending.')
    closed = stages.update(state=Job.FAILED, error=P['note'], finished_at=now)
for pk in encounters:
    review.refresh_state(models.Encounter.objects.get(pk=pk))
print(ANSWER + json.dumps({'closed': closed, 'kinds': kinds, 'encounters': len(encounters),
                           'runs_unknown': unknown, 'runs_not_sent': not_sent, 'hazards': undo_hazards()}))
'''
# The stages this image's worker cannot run (a kind its STAGES does not know) that are queued, running, or cancelled
# as their encounter's latest stage (what a Resume runs again): a worker meeting one ends on a KeyError (migrate-3).
UNRUNNABLE_STAGES = '''
from studio import jobs, models
Job, known, stuck = models.Job, sorted(jobs.STAGES), []
rows = (Job.objects.exclude(kind__in=known).filter(state__in=(Job.QUEUED, Job.RUNNING, Job.CANCELLED))
        .values_list('pk', 'kind', 'state', 'revision_id', 'encounter_id'))
for pk, kind, state, revision_id, encounter_id in rows:
    if state == Job.CANCELLED and (
            Job.objects.filter(revision_id=revision_id).order_by('-created_at', '-pk').values_list('pk', flat=True)
            .first() != pk
            or not models.Encounter.objects.filter(pk=encounter_id, current_revision_id=revision_id).exists()):
        continue
    stuck.append(kind)
print(ANSWER + json.dumps({'known': known, 'stuck': len(stuck), 'kinds': sorted(set(stuck))}))
'''
# The encounters with a provider outcome still unknown (not reconciled). The app phase installs no pair over one
# (refutation p1, migrate-2): its list state is the one stored state the installed revision derived otherwise than this
# revision does (an unreconciled unknown outcome keeps an encounter on the review queue), and no stored list state is
# recomputed until an action touches the encounter. Every other difference in the derivation reads rows only this
# revision writes (holds, second reviews and their stages).
UNKNOWN_OUTCOMES = '''
from studio import models
Run = models.ProviderRun
found = sorted({str(pk) for pk in Run.objects.filter(state=Run.UNKNOWN, reconciled_at__isnull=True)
                .values_list('encounter_id', flat=True)})
print(ANSWER + json.dumps({'encounters': found}))
'''


def app_script(image_id, env_bytes, body, params, *, what, timeout=180) -> dict:
    """Run ``body`` in a one-shot container of ``image_id`` (provider disabled) and return its ANSWER line's JSON."""
    payload = base64.b64encode(json.dumps(params).encode()).decode()
    source = APP_SCRIPT_PRELUDE.format(payload=payload, answer=APP_SCRIPT_ANSWER) + body
    result = oneshot(image_id, ['manage', 'shell', '-c', source], env_bytes, timeout=timeout)
    answers = [line for line in result.stdout.decode('utf-8', 'replace').splitlines()
               if line.startswith(APP_SCRIPT_ANSWER)]
    if result.returncode or len(answers) != 1:
        raise InstallError(f'{what} failed (exit {result.returncode}).', output=result.stderr[-2048:])
    return json.loads(answers[0][len(APP_SCRIPT_ANSWER):])


def require_db():
    container = inspect('container', DB_CONTAINER)
    if container is None or not owned(container, 'db'):
        raise InstallError(f'{DB_CONTAINER} is not present; run --phase db first.')
    if not container['State'].get('Running'):
        raise InstallError(f'{DB_CONTAINER} is not running.')
    wait_db_ready()


def wait_db_ready(attempts=60):
    # Over TCP, as the application connects: the image's first-start init server answers on the unix socket only,
    # so a socket probe could call the database ready between initdb and the real server.
    for _ in range(attempts):
        if docker('exec', DB_CONTAINER, 'pg_isready', '-q', '-h', '127.0.0.1', '-p', '5432', '-U', DB_USER,
                  '-d', DB_NAME, check=False, timeout=15).returncode == 0:
            return
        time.sleep(1)
    raise InstallError('The CPT Studio database did not become ready.')


def db_container_problems(container, postgres_image_id) -> list:
    host = container.get('HostConfig') or {}
    problems = []
    if not owned(container, 'db'):
        problems.append('not labelled as the CPT Studio database')
    if container.get('Image') != postgres_image_id:
        problems.append('runs another image')
    if (host.get('PortBindings') or {}).get('5432/tcp') != [{'HostIp': '127.0.0.1', 'HostPort': str(DB_PORT)}]:
        problems.append('is not published on 127.0.0.1 only')
    if (host.get('RestartPolicy') or {}).get('Name') != 'unless-stopped':
        problems.append('has another restart policy')
    if NETWORK not in ((container.get('NetworkSettings') or {}).get('Networks') or {}):
        problems.append(f'is not on {NETWORK}')
    return problems


def service_problems(container, role, image_id) -> list:
    host = container.get('HostConfig') or {}
    problems = []
    if not owned(container, role) or container.get('Image') != image_id:
        problems.append('not the installed image with the CPT Studio label')
    if not host.get('ReadonlyRootfs'):
        problems.append('root filesystem is writable')
    if host.get('CapDrop') != ['ALL'] or 'no-new-privileges' not in (host.get('SecurityOpt') or []):
        problems.append('capabilities or privilege escalation not locked down')
    if (container.get('Config') or {}).get('User') != f'{APP_UID}:{APP_UID}':
        problems.append('not running as the application user')
    bindings = host.get('PortBindings') or {}
    expected = {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(WEB_PORT)}]} if role == 'web' else {}
    if bindings != expected:
        problems.append('unexpected published ports')
    return problems


def wait_service(role, revision, image_id) -> dict:
    name = SERVICES[role]
    if role == 'web':
        def check():
            container = inspect('container', name)
            if container is None or not container['State'].get('Running'):
                return False, {'running': False}
            result = probe('http', DOMAIN, '/health/', port=WEB_PORT, connect_ip='127.0.0.1',
                           headers={'X-Forwarded-Proto': 'https'}, timeout=3)
            return result.get('status') == 200 and health_ok(result.get('json'), revision), {
                'status': result.get('status'), 'error': result.get('error')}
        passed, observations = poll(check, attempts=90, interval=1.0)
    else:
        stable = []

        def check():
            state = (inspect('container', name) or {}).get('State') or {}
            calm = bool(state.get('Running')) and not state.get('Restarting') and state.get('ExitCode') == 0
            stable.append(calm)
            return len(stable) >= 10 and all(stable[-10:]), {'running': bool(state.get('Running'))}
        passed, observations = poll(check, attempts=20, interval=1.0)
    container = inspect('container', name) or {}
    problems = service_problems(container, role, image_id) if container else ['container vanished']
    if not passed or problems or container.get('RestartCount'):
        raise InstallError(f'{name} did not become ready: {problems or "readiness not observed"}.',
                           details={'observations': observations[-5:]})
    return {'id': container['Id'], 'observations': len(observations)}


def park(role):
    name, parked = SERVICES[role], SERVICES[role] + '-previous'
    if inspect('container', parked) is not None:
        raise InstallError(f'{parked} is left from an interrupted replacement; resolve it before reinstalling.')
    container = inspect('container', name)
    if container is None:
        return None
    if not owned(container, role):
        raise InstallError(f'{name} exists but is not a CPT Studio {role} container.')
    docker('stop', '--time', str(STOP_SECONDS[role]), name, timeout=STOP_SECONDS[role] + 60)
    try:
        docker('rename', name, parked)
    except InstallError:
        docker('start', name, check=False)
        raise
    return {'id': container['Id'], 'image': container['Image']}


def remove_service_container(name, role):
    container = inspect('container', name)
    if container is None:
        return
    if not owned(container, role):
        raise InstallError(f'{name} is not a CPT Studio {role} container; refusing to remove it.')
    docker('stop', '--time', str(STOP_SECONDS[role]), name, check=False, timeout=STOP_SECONDS[role] + 60)
    docker('rm', '--force', container['Id'], timeout=60)


def stop_service_container(name, role):
    container = inspect('container', name)
    if container is not None and owned(container, role):
        docker('stop', '--time', str(STOP_SECONDS[role]), name, check=False, timeout=STOP_SECONDS[role] + 60)


def created_at(container) -> dt.datetime:
    """When Docker created ``container``, in UTC (nanoseconds cut to microseconds, which can only move it earlier)."""
    match = re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?Z', str(container.get('Created', '')))
    if not match:
        raise InstallError(f'Docker gave no creation time for {container.get("Id", "a container")}.')
    return dt.datetime.fromisoformat(f'{match[1]}.{(match[2] or "")[:6].ljust(6, "0")}+00:00')


def close_undone_stages(image_id, env_bytes, since, revision, reason, kinds) -> dict:
    """Undo, before any other pair runs on this database: every stage the pair of ``revision`` queued, ran or left
    resumable since ``since``, and every open stage of a kind the next worker does not run (``kinds`` are those it
    runs) whichever pair created it, is closed as failed with the revision named, and the provider runs they left
    unsettled are settled (CLOSE_STAGES). A pair restored or reinstalled afterwards would read that work under its own
    rules: the installed revision's worker ends on a second review it has no stage for, and reads a member date conflict
    as no date at all (refutation r1, migrate-3 and migrate-4; p1, security-0). Run with the undone revision's own
    image. The answer's 'hazards' name what the next pair would still act on wrongly (UNDO_HAZARDS)."""
    note = (f'Closed by the installer: {reason} (revision {revision[:12]}), so this stage will not run. Change the '
            'context, add an addendum or upload the document again to process it.')
    return app_script(image_id, env_bytes, CLOSE_STAGES, {'since': since.isoformat(), 'note': note,
                                                          'kinds': sorted(kinds)},
                      what=f'Closing the stages revision {revision[:12]} left open')


def stage_kinds_of(image_id, env_bytes) -> list:
    """The stage kinds the worker of ``image_id`` runs - its own jobs.STAGES, read by UNRUNNABLE_STAGES in that image -
    or COMMON_STAGE_KINDS when it cannot be asked (no image id, or no answer): an undo then closes more, never less."""
    if isinstance(image_id, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        try:
            return sorted(app_script(image_id, env_bytes, UNRUNNABLE_STAGES, {},
                                     what='Reading the stage kinds the next worker runs')['known'])
        except Exception:  # noqa: BLE001 — an undo never stops on this read; it assumes the fewest kinds instead
            pass
    return list(COMMON_STAGE_KINDS)


def undo_hazards(image_id, env_bytes, revision) -> dict:
    """{encounter id: reasons} - what ``revision`` recorded that an older revision would act on under its own rules
    (UNDO_HAZARDS, read with ``revision``'s own image)."""
    return app_script(image_id, env_bytes, UNDO_HAZARDS_READ, {},
                      what=f'Reading what an older revision would act on wrongly (revision {revision[:12]})')['hazards']


def hazard_summary(hazards) -> str:
    counts = {}
    for reasons in hazards.values():
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
    return f'{len(hazards)} encounter(s): ' + ', '.join(f'{reason} {count}' for reason, count in sorted(counts.items()))


def replace_services(ctx, image_id, env_bytes, provider_mode, authorization_ref) -> dict:
    """Park the old pair, start the new pair; on any failure stop what was started, close every stage it left open
    and every open stage of a kind the old worker does not run (close_undone_stages), and only then restore exactly the
    old pair - its worker left stopped while the close names records it would act on wrongly. A pair whose stages
    cannot be closed is never restored over them: the new pair is left stopped and the old one parked, for
    rollback-app."""
    parked, launched, started = {}, [], {}
    swapped_at = None
    try:
        for role in ('worker', 'web'):  # the worker first, so no stage runs across the switch
            parked[role] = park(role)
        swapped_at = dt.datetime.now(dt.timezone.utc)  # every stage created from here on is the new pair's
        for role in ('web', 'worker'):
            launched.append(role)
            docker('run', '-d', *service_args(role, image_id, ctx.revision, provider_mode, authorization_ref),
                   input=env_bytes, quiet=True)
            started[role] = wait_service(role, ctx.revision, image_id)
    except BaseException as failure:
        for role in reversed(launched):
            name = SERVICES[role]
            container = inspect('container', name)
            if container is not None and owned(container, role):
                tail = docker('logs', '--tail', '40', name, check=False, timeout=30)
                ctx.log(f'{role}-failed', tail.stdout[-8192:] + tail.stderr[-8192:])
            stop_service_container(name, role)
        closed, hold_worker = None, False
        if launched and any(parked.values()):
            previous = parked.get('worker') or parked.get('web')
            kinds = stage_kinds_of(previous['image'], env_bytes)  # what the restored worker runs (p1, security-0)
            try:
                closed = close_undone_stages(image_id, env_bytes, swapped_at, ctx.revision,
                                             'its installation failed and the previous revision was restored', kinds)
            except BaseException as error:
                raise InstallError(f'{failure}; the stages the new pair left open could not then be closed ({error}), '
                                   'so the new pair was left stopped and the previous pair parked (*-previous): run '
                                   '--phase rollback-app, then rename the parked pair back.') from error
            ctx.log('undo', json.dumps(closed).encode())
            # Refutation p1, migrate-0/-1: this path cannot refuse, so while the close names records the restored
            # revision would act on under its own rules (a send without a date, an identical re-send of a request that
            # failed), its worker - the only holder of the provider credentials - is left stopped: nothing can be sent.
            # An answer that names nothing it read is not read as "none".
            hold_worker = not isinstance(closed.get('hazards'), dict) or bool(closed['hazards'])
        for role in reversed(launched):
            remove_service_container(SERVICES[role], role)
        for role, previous in parked.items():
            if previous:
                docker('rename', SERVICES[role] + '-previous', SERVICES[role])
                if role != 'worker' or not hold_worker:
                    docker('start', SERVICES[role])
        if hold_worker:
            hazards = closed.get('hazards')
            named = hazard_summary(hazards) if isinstance(hazards, dict) else 'the close did not say which'
            raise InstallError(
                f'{failure}; the previous web was restored and its worker ({SERVICES["worker"]}) left stopped, so '
                f'nothing can be sent: {named} hold records it would act on under its own rules (ops/INSTALL.md, '
                'Reinstalling an older revision). Install this revision again once its failure is fixed: its worker '
                'reads them under its own rules.', details={'hazards': hazards, 'stages_closed': closed}) from failure
        raise
    for role, previous in parked.items():
        if previous:
            docker('rm', '--force', previous['id'], timeout=60)
    return {'started': started, 'replaced': parked}


# --- phases ------------------------------------------------------------------------

def phase_preflight(ctx) -> dict:
    problems, details = [], {'docker_server': docker_positive_control()}
    files = nginx_file_state()
    details['nginx_files'] = files
    if files['available'].get('quillmd') != QUILLMD_VHOST_SHA256:
        problems.append('the quillmd vhost sha256 is not the pinned one')
    test = nginx_test()
    details['nginx_test'] = {'ok': test['ok'], 'warnings': test['warnings'],
                             'log': ctx.log('nginx-t', test['output'].encode())}
    if not test['ok']:
        problems.append('sudo -n nginx -t did not pass')
    details['routing'] = routing_snapshot(routing_targets(enabled_config_texts()))
    details['cpt_before'] = cpt_probes()
    details['vhost'] = vhost_state()
    details['app_health'] = app_health()
    if details['app_health']['status'] != 200 or not isinstance(details['app_health']['json'], dict):
        problems.append('app.quillmd.com /health/ did not answer 200 JSON')
    details['cotenants'] = cotenant_check()
    if details['cotenants']['returncode'] != 0:
        problems.append('scripts/check-cotenants.sh did not pass')
    details['containers'] = containers()
    details['volumes'] = volumes()
    details['networks'] = networks()
    for port, owner in ((WEB_PORT, SERVICES['web']), (DB_PORT, DB_CONTAINER)):
        problem = port_problem(port, owner)
        if problem:
            problems.append(problem)
    details['foreign_app_uid_tasks'] = foreign_uid_tasks(APP_UID, own_service_ids())
    if details['foreign_app_uid_tasks']:
        problems.append(f'uid {APP_UID} already runs {details["foreign_app_uid_tasks"]} task(s) outside CPT Studio')
    try:
        infos = socket.getaddrinfo(DOMAIN, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        infos = []
    details['dns'] = {'a': sorted({info[4][0] for info in infos if info[0] == socket.AF_INET}),
                      'aaaa': sorted({info[4][0] for info in infos if info[0] == socket.AF_INET6})}
    if details['dns'] != {'a': [PUBLIC_IPV4], 'aaaa': []}:
        problems.append(f'{DOMAIN} must resolve to A {PUBLIC_IPV4} only')
    details['images'] = {ref: bool(inspect('image', ref)) for ref in (HELPER_IMAGE, POSTGRES_IMAGE)}
    if not all(details['images'].values()):
        problems.append('a pinned image (helper or postgres) is not present locally')
    details['paths'] = helper_stat([CORTI_SOURCE, ETC_DIR, *LE_DIRS, ACME_CHALLENGE_DIR])
    if not details['paths'][CORTI_SOURCE].get('exists'):
        problems.append(f'{CORTI_SOURCE} is missing')
    details['letsencrypt'] = le_state()
    if not all(details['letsencrypt']['dirs'].values()):
        problems.append('a Let\'s Encrypt or webroot directory is missing')
    if len(details['letsencrypt']['accounts']) != 1:
        problems.append('exactly one existing ACME account is required')
    token, content = secrets.token_urlsafe(24), secrets.token_hex(16)
    acme = f'type=bind,src={ACME_CHALLENGE_DIR},dst=/acme'
    try:
        run_helper(H_ACME_WRITE, {'name': token, 'content': content}, mounts=[acme])
    finally:
        details['acme_webroot_writable'] = run_helper(H_ACME_REMOVE, {'name': token, 'content': content},
                                                      mounts=[acme])['removed']
    if not details['acme_webroot_writable']:
        problems.append('the ACME webroot probe could not be written and removed')
    usage = shutil.disk_usage('/')
    meminfo = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
    details['resources'] = {'root_free_gib': round(usage.free / 2 ** 30, 1),
                            'mem_available': meminfo.get('MemAvailable', '').strip()}
    if usage.free < 10 * 2 ** 30:
        problems.append('less than 10 GiB free on /')
    if problems:
        raise InstallError(f'Preflight found {len(problems)} problem(s): ' + '; '.join(problems) + '.',
                           details={**details, 'problems': problems})
    details['summary'] = 'baseline recorded; no blocking problem'
    return details


def phase_secrets(ctx) -> dict:
    etc = run_helper(H_ETC_DIR, {}, mounts=['type=bind,src=/etc,dst=/host-etc'])
    result = run_helper(H_SECRETS, {'uid': APP_UID, 'corti_keys': list(CORTI_KEYS), 'app_keys': list(APP_ENV_KEYS),
                                    'db_keys': list(DB_ENV_KEYS)},
                        mounts=[f'type=bind,src={ETC_DIR},dst=/target',
                                f'type=bind,src={CORTI_SOURCE},dst=/source/credentials.env,readonly'],
                        sensitive=True)
    return {'etc_dir': etc['etc_dir'], **result, 'summary': f'secrets {result["state"]}; values never left the helper'}


def extract_archive(data: bytes, destination: Path):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != APP or member.name.startswith('/') or '..' in parts:
                raise InstallError(f'Unexpected path in the source archive: {member.name!r}.')
            if not (member.isfile() or member.isdir()):
                raise InstallError(f'Unexpected member type in the source archive: {member.name!r}.')
        archive.extractall(destination, filter='data')
    # The 'data' filter does not apply directory modes, so under main()'s umask 077 every directory came out
    # 0700, Docker's COPY kept it, and the image user could not enter /app (the first image phase, 2026-10-26).
    # Directories get git's 0755; the filter already gives files the archive's 0644/0755.
    for directory, _, _ in os.walk(destination / APP):
        os.chmod(directory, 0o755)


def phase_image(ctx) -> dict:
    archive = run(['git', '-C', str(ROOT), 'archive', '--format=tar', ctx.revision, APP], timeout=120).stdout
    build_root = Path(tempfile.mkdtemp(prefix=f'build-{ctx.revision[:12]}-', dir=ctx.receipts))
    tag = image_tag(ctx.revision)
    try:
        extract_archive(archive, build_root)
        context = build_root / APP
        shutil.copyfile(context / 'deploy' / '.dockerignore', context / '.dockerignore')
        base = re.search(r'^FROM (\S+)', (context / 'deploy' / 'Dockerfile').read_text(), re.M).group(1)
        build = docker('build', '--file', str(context / 'deploy' / 'Dockerfile'), '--build-arg',
                       f'REVISION={ctx.revision}', '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=app-image',
                       '--tag', tag, str(context), timeout=1800, check=False)
        build_log = ctx.log('docker-build', build.stdout + build.stderr)
        if build.returncode:
            raise InstallError(f'docker build failed (exit {build.returncode}); see {build_log}.')
    finally:
        shutil.rmtree(build_root)
    image = inspect('image', tag)
    config = image['Config']
    if (labels_of(image).get(REVISION_LABEL) != ctx.revision or not owned(image, 'app-image')
            or config.get('User') != f'{APP_UID}:{APP_UID}'
            or f'CPT_STUDIO_RELEASE_SHA={ctx.revision}' not in (config.get('Env') or [])):
        raise InstallError('The built image does not carry the revision, label, user and release it must.')
    smoke = ['run', '--rm', '--pull=never', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
             '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--no-healthcheck']
    languages = docker(*smoke, '--entrypoint', 'tesseract', image['Id'], '--list-langs').stdout.decode().split()
    tesseract = docker(*smoke, '--entrypoint', 'tesseract', image['Id'], '--version').stdout.decode().splitlines()[0]
    pdftoppm = docker(*smoke, '--entrypoint', 'pdftoppm', image['Id'], '-v')
    check = docker(*smoke, '-e', 'CPT_STUDIO_SECRET_KEY=image-smoke-check-only', image['Id'], 'manage', 'check',
                   '--fail-level', 'ERROR', check=False, timeout=120)
    # Loading the WSGI application runs the middleware, which reads every static
    # file: as the image's own user on a read-only root, exactly as the web role.
    wsgi = docker(*smoke, '-e', 'CPT_STUDIO_SECRET_KEY=image-smoke-check-only', '--entrypoint', 'python',
                  image['Id'], '-c', 'import cptstudio.wsgi', check=False, timeout=120)
    if 'eng' not in languages or check.returncode or wsgi.returncode:
        raise InstallError('The image lacks English OCR data, fails Django system checks, or cannot load the '
                           'web application as its own user.',
                           output=(check.stdout + check.stderr + wsgi.stdout + wsgi.stderr)[-8192:])
    return {'image_id': image['Id'], 'tag': tag, 'base': base, 'size_bytes': image.get('Size'),
            'source_archive_sha256': sha256(archive), 'build_log': build_log, 'tesseract': tesseract,
            'tesseract_languages': [item for item in languages if item in ('eng', 'osd')],
            'pdftoppm': (pdftoppm.stdout + pdftoppm.stderr).decode().splitlines()[0],
            'summary': f'built {tag} = {image["Id"][:19]}'}


def phase_db(ctx) -> dict:
    postgres = inspect('image', POSTGRES_IMAGE)
    if postgres is None:
        raise InstallError('The pinned postgres image is not present locally.')
    details = {'network': ensure_network(), 'db_volume': ensure_volume(DB_VOLUME, 'db-data'),
               'files_volume': ensure_volume(FILES_VOLUME, 'files')}
    files_volume_helper({})
    container = inspect('container', DB_CONTAINER)
    if container is None:
        problem = port_problem(DB_PORT, DB_CONTAINER)
        if problem:
            raise InstallError(problem)
        docker('run', '-d', *db_args(), input=read_protected_env(DB_ENV, DB_ENV_KEYS), quiet=True)
        details['container'] = 'created'
    else:
        problems = db_container_problems(container, postgres['Id'])
        if problems:
            raise InstallError(f'{DB_CONTAINER} exists but ' + '; '.join(problems) + '.')
        if not container['State'].get('Running'):
            docker('start', DB_CONTAINER)
        details['container'] = 'present'
    wait_db_ready()
    container = inspect('container', DB_CONTAINER)
    problems = db_container_problems(container, postgres['Id'])
    if problems:
        raise InstallError(f'{DB_CONTAINER} ' + '; '.join(problems) + '.')
    details.update(container_id=container['Id'], image_id=postgres['Id'],
                   summary=f'{DB_CONTAINER} ready on 127.0.0.1:{DB_PORT} ({details["container"]})')
    return details


def phase_app(ctx) -> dict:
    mode, reference = ctx.args.provider_mode, ctx.args.authorization_ref or ''
    if reference and run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{ctx.revision}:{reference}'],
                         check=False).returncode:
        raise InstallError('--authorization-ref is not a file tracked at the revision.')
    image_id = installed_image(ctx)
    require_db()
    if mode == 'live':
        target = helper_stat([CORTI_TARGET])[CORTI_TARGET]
        if target != {'exists': True, 'kind': 'file', 'uid': APP_UID, 'gid': APP_UID, 'mode': '0o400'}:
            raise InstallError(f'{CORTI_TARGET} is not the {APP_UID}:{APP_UID} 0400 file the secrets phase writes.')
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    if mode == 'live':
        # The application's own loader, in the worker's mount layout, with no network: format only.
        parsed = oneshot(image_id, ['manage', 'shell', '-c', CREDENTIALS_CHECK], env, network='none',
                         credentials=True, timeout=120)
        if parsed.returncode or b'corti-credentials-parse-ok' not in parsed.stdout:
            raise InstallError('The application cannot load the Corti credentials file as mounted for the worker '
                               '(format and permissions only; nothing was sent).', output=parsed.stderr[-2048:])
    migrate = oneshot(image_id, ['migrate'], env)
    migrate_log = ctx.log('migrate', migrate.stdout + migrate.stderr)
    if migrate.returncode:
        raise InstallError(f'Migrations failed (exit {migrate.returncode}); see {migrate_log}.')
    # A stage this revision's worker has no handler for ends the worker (refutation r1, migrate-3): an older revision
    # installed over a newer one meets the newer one's open stages. Nothing is replaced while one could be claimed or
    # resumed; the newer revision's rollback-app closes them.
    unrunnable = app_script(image_id, env, UNRUNNABLE_STAGES, {},
                            what='Reading the queue for stages this revision cannot run')
    if unrunnable['stuck']:
        raise InstallError(f'{unrunnable["stuck"]} stage(s) of a kind this revision cannot run '
                           f'({", ".join(unrunnable["kinds"])}) are queued, running or resumable; nothing was '
                           'replaced. Close them with the newer revision\'s --phase rollback-app first.',
                           details=unrunnable)
    # Refutation p1, migrate-2: no pair is installed over a provider outcome still unknown (the install plan requires
    # none). Its stored list state is the one the running revision may have derived otherwise than this one, and nothing
    # recomputes a stored state until an action touches the encounter (UNKNOWN_OUTCOMES says why that is the only one).
    unknown = app_script(image_id, env, UNKNOWN_OUTCOMES, {}, what='Reading the provider outcomes still unknown')
    if unknown['encounters']:
        raise InstallError(f'{len(unknown["encounters"])} encounter(s) have a provider outcome still unknown; nothing '
                           'was replaced. Reconcile each on the running revision\'s web first, then rerun --phase app.',
                           details=unknown)
    services = replace_services(ctx, image_id, env, mode, reference)
    return {'image_id': image_id, 'provider_mode': mode, 'authorization_ref': reference, 'migrate_log': migrate_log,
            'unrunnable_stages': unrunnable, 'unknown_outcomes': unknown, **services,
            'summary': f'web and worker running {image_id[:19]} (provider {mode})'}


def reference_command(kind, path, retrieved_at) -> list:
    pinned = REFERENCE_FILES[kind]
    return ['manage', 'import_reference', '--kind', kind, '--zip', path, '--expected-sha256', pinned['sha256'],
            '--release', pinned['release'], '--url', pinned['url'], '--effective-start', pinned['effective_start'],
            '--effective-end', pinned['effective_end'], '--retrieved-at', retrieved_at]


def phase_reference(ctx) -> dict:
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    results = {}
    for kind, given, retrieved_at in (('cms-pfs', ctx.args.pfs_zip, ctx.args.pfs_retrieved_at),
                                      ('cms-mue-practitioner', ctx.args.mue_zip, ctx.args.mue_retrieved_at)):
        pinned, path = REFERENCE_FILES[kind], Path(given)
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise InstallError(f'{kind}: give an absolute path to a regular file.')
        if path.stat().st_size != pinned['size'] or sha256(path.read_bytes()) != pinned['sha256']:
            raise InstallError(f'{kind}: the file is not the pinned {pinned["name"]} (size/sha256 differ).')
        copy = files_volume_helper({'sha256': pinned['sha256']},
                                   [f'type=bind,src={path},dst=/in/source.zip,readonly'])
        in_volume = f'{STATE_DIR}/reference/{pinned["sha256"]}.zip'
        imported = oneshot(image_id, reference_command(kind, in_volume, retrieved_at), env,
                           mounts=[f'type=volume,src={FILES_VOLUME},dst={STATE_DIR},readonly'])
        log = ctx.log(f'import-{kind}', imported.stdout + imported.stderr)
        if imported.returncode:
            raise InstallError(f'import_reference {kind} failed (exit {imported.returncode}); see {log}.')
        results[kind] = {**pinned, 'retrieved_at': retrieved_at, 'volume_path': in_volume, 'copied': copy['copied'],
                         'log': log}
    return {'sources': results, 'summary': 'imported ' + ', '.join(results)}


def credentials_document(ctx, accounts) -> dict:
    return {'service': 'cpt-studio', 'url': f'https://{DOMAIN}/', 'synthetic_only': True,
            'workspace': ctx.args.workspace_name, 'revision': ctx.revision, 'created_at': utc_now(),
            'accounts': accounts}


def root_file(op, **params) -> dict:
    params.update(op=op, final=INITIAL_CREDENTIALS, staged=f'.{INITIAL_CREDENTIALS}.new')
    params.setdefault('replace', False)
    return run_helper(H_ROOT_FILE, params, mounts=[f'type=bind,src={ETC_DIR},dst=/target'], sensitive=True)


def provision_outcome(stdout: str, expected: dict) -> dict:
    found = {}
    for line in stdout.splitlines():
        match = PROVISION_LINE_RE.fullmatch(line.strip())
        if match:
            found[match.group(3)] = (match.group(1), match.group(2), match.group(4))
    outcome = {}
    for username, (kind, role) in expected.items():
        if username not in found or found[username][1:] != (kind, role):
            raise InstallError(f'provision did not report {username} as a {kind} {role}.')
        outcome[username] = found[username][0]
    return outcome


def phase_provision(ctx) -> dict:
    args, reset = ctx.args, bool(ctx.args.reset_passwords)
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    state = root_file('state')
    agent_staged = AGENT_CREDENTIALS.with_name('.agent-credentials.json.new')
    if state['staged_exists'] or agent_staged.exists():
        raise InstallError('Staged credentials from an interrupted run exist; resolve them by hand first.')
    if not reset and (state['final_exists'] or AGENT_CREDENTIALS.exists()):
        raise InstallError('Credentials files already exist; use --reset-passwords to rotate them.')
    expected = {args.owner_username: ('human', 'owner'), args.agent_username: ('agent', 'reviewer')}
    passwords = {args.owner_username: secrets.token_urlsafe(24), args.agent_username: secrets.token_urlsafe(24)}
    accounts = [{'username': user, 'actor_kind': kind, 'role': role, 'password': passwords[user]}
                for user, (kind, role) in expected.items()]
    root_bytes = json.dumps(credentials_document(ctx, accounts), indent=2).encode()
    agent_bytes = json.dumps(credentials_document(ctx, accounts[1:]), indent=2).encode()
    AGENT_CREDENTIALS.parent.mkdir(mode=0o700, exist_ok=True)
    folder = AGENT_CREDENTIALS.parent.lstat()
    if not stat.S_ISDIR(folder.st_mode) or folder.st_uid != os.getuid() or stat.S_IMODE(folder.st_mode) != 0o700:
        raise InstallError(f'{AGENT_CREDENTIALS.parent} must be a directory owned by this user with mode 0700.')
    # Password files live in RAM only (/dev/shm) and are wiped whatever happens.
    scratch = Path(tempfile.mkdtemp(prefix='cpt-studio-provision-', dir='/dev/shm'))
    try:
        root_file('stage', content=base64.b64encode(root_bytes).decode())
        write_private(agent_staged.parent, agent_staged.name, agent_bytes)
        mounts = []
        for user in expected:
            write_private(scratch, f'{user}.pw', passwords[user].encode())
            mounts.append(f'type=bind,src={scratch / (user + ".pw")},dst=/run/cpt-provision/{user}.pw,readonly')
        command = ['manage', 'provision', '--workspace-name', args.workspace_name,
                   '--owner-username', args.owner_username, '--owner-display-name', args.owner_display_name,
                   '--owner-password-file', f'/run/cpt-provision/{args.owner_username}.pw',
                   '--agent-username', args.agent_username, '--agent-display-name', args.agent_display_name,
                   '--agent-password-file', f'/run/cpt-provision/{args.agent_username}.pw']
        if reset:
            command.append('--reset-passwords')
        result = oneshot(image_id, command, env, mounts=mounts, user=f'{os.getuid()}:{os.getgid()}')
        assert_no_secret([result.stdout, result.stderr], passwords.values())
        log = ctx.log('provision', result.stdout + result.stderr)
        if result.returncode:
            raise InstallError(f'provision failed (exit {result.returncode}); see {log}.')
        outcome = provision_outcome(result.stdout.decode('utf-8', 'replace'), expected)
        if not reset and set(outcome.values()) != {'created'}:
            raise InstallError('An account already existed, so its password was not set; nothing was saved. '
                               'Rerun with --reset-passwords to rotate.')
        root_file('commit', replace=reset)
        if reset:
            os.replace(agent_staged, AGENT_CREDENTIALS)
        else:
            os.link(agent_staged, AGENT_CREDENTIALS)
            agent_staged.unlink()
    except BaseException:
        root_file('discard', sha256=sha256(root_bytes))
        agent_staged.unlink(missing_ok=True)
        raise
    finally:
        for path in scratch.iterdir():
            path.write_bytes(b'\0' * 64)
            path.unlink()
        scratch.rmdir()
    return {'accounts': outcome, 'root_credentials': f'{ETC_DIR}/{INITIAL_CREDENTIALS}',
            'agent_credentials': str(AGENT_CREDENTIALS), 'log': log, 'reset_passwords': reset,
            'summary': 'accounts ' + ', '.join(f'{user} {state}' for user, state in outcome.items())}


def acme_probe(ctx, label) -> dict:
    """Prove the ACME path for the domain is served by this host's nginx, then remove the probe."""
    token, content = secrets.token_urlsafe(24), secrets.token_hex(16)
    mount = f'type=bind,src={ACME_CHALLENGE_DIR},dst=/acme'
    run_helper(H_ACME_WRITE, {'name': token, 'content': content}, mounts=[mount])
    try:
        def check():
            result = probe('http', DOMAIN, f'/.well-known/acme-challenge/{token}', connect_ip='127.0.0.1')
            served = result.get('status') == 200 and result.get('body_sha256') == sha256(content.encode())
            return served, {'status': result.get('status'), 'error': result.get('error')}
        passed, observations = poll(check, attempts=30, interval=0.25)
    finally:
        removed = run_helper(H_ACME_REMOVE, {'name': token, 'content': content}, mounts=[mount])
    return {'passed': passed, 'observations': observations[-3:], 'probe_removed': removed['removed'], 'label': label}


def ingress_checks(ctx, preflight) -> list:
    """Problems with co-tenants or app.quillmd.com relative to the preflight baseline."""
    problems = []
    changed = routing_diff(preflight['details']['routing'], routing_snapshot(routing_targets(enabled_config_texts())))
    if changed:
        problems.append('co-tenant routing changed: ' + ', '.join(changed))
    health = app_health()
    if health != preflight['details']['app_health']:
        problems.append('app.quillmd.com /health/ changed')
    return problems


def publish_vhost(ctx, apply, undo, verify) -> dict:
    """Apply a vhost change, validate, reload, verify; restore exactly on any failure."""
    before = nginx_test()
    if not before['ok']:
        raise InstallError('nginx -t does not pass before the change; refusing.')
    reloaded = False
    try:
        apply()
        after = nginx_test()
        log = ctx.log('nginx-t', after['output'].encode())
        new_warnings = sorted(set(after['warnings']) - set(before['warnings']))
        if not after['ok'] or new_warnings:
            raise InstallError(f'nginx -t after the change failed or added warnings {new_warnings}; see {log}.')
        nginx_reload()
        reloaded = True
        result = verify()
    except BaseException as failure:
        try:
            undo()
        except BaseException as restore_failure:
            raise InstallError(f'The change failed ({failure}) and restoring the previous vhost also failed '
                               f'({restore_failure}); nginx may hold an unverified vhost. Investigate now.') from None
        restored = nginx_test()
        ctx.log('nginx-t-restored', restored['output'].encode())
        if reloaded and restored['ok']:
            nginx_reload()
        if not restored['ok']:
            raise InstallError('The restored nginx configuration does not pass nginx -t; investigate now.')
        raise
    return {**result, 'nginx_warnings_unchanged': True}


def phase_http_vhost(ctx) -> dict:
    preflight = require_receipt(ctx, 'preflight')
    conf = rendered_vhosts(ctx.revision)['http']
    state = vhost_state()
    if state['file_exists'] or state['link_exists']:
        if state['file_sha256'] != sha256(conf.encode()) or state['link_target'] != VHOST_LINK_TARGET:
            raise InstallError('quillmd-cpt already exists and is not this HTTP stage; refusing.')

    def apply():
        vhost_operation('install', content=base64.b64encode(conf.encode()).decode())

    def undo():
        vhost_operation('remove', allowed_sha256=[sha256(conf.encode())])

    def verify():
        acme = acme_probe(ctx, 'http-vhost')
        redirect = probe('http', DOMAIN, '/', connect_ip='127.0.0.1')
        problems = ingress_checks(ctx, preflight)
        if not acme['passed'] or not acme['probe_removed']:
            problems.append('the ACME challenge path did not serve the probe (or it was not removed)')
        if redirect.get('status') != 301 or redirect.get('headers', {}).get('location') != [f'https://{DOMAIN}/']:
            problems.append(f'http://{DOMAIN}/ did not redirect to https')
        if problems:
            raise InstallError('; '.join(problems) + '.', details={'acme': acme, 'redirect': redirect})
        return {'acme': acme, 'redirect': redirect}
    result = verify() if state['file_exists'] else publish_vhost(ctx, apply, undo, verify)
    return {**result, 'vhost_sha256': sha256(conf.encode()), 'already_installed': state['file_exists'],
            'summary': 'HTTP stage live; ACME path proven'}


def phase_cert(ctx) -> dict:
    require_receipt(ctx, 'http-vhost')
    confs = rendered_vhosts(ctx.revision)
    if vhost_state()['file_sha256'] not in {sha256(confs['http'].encode()), sha256(confs['https'].encode())}:
        raise InstallError('quillmd-cpt is not a stage this installer wrote; refusing to request a certificate.')
    infos = socket.getaddrinfo(DOMAIN, 80, type=socket.SOCK_STREAM)
    if {info[4][0] for info in infos} != {PUBLIC_IPV4}:
        raise InstallError(f'{DOMAIN} no longer resolves to {PUBLIC_IPV4} alone.')
    before = le_state()
    if len(before['accounts']) != 1:
        raise InstallError(f'Exactly one existing ACME account is required, found {len(before["accounts"])}; '
                           'this installer never registers one.')
    mounts = [ROOT_MOUNT, 'type=tmpfs,dst=/host/tmp'] + [f'type=bind,src={path},dst=/host{path}' for path in LE_DIRS]
    result = run_helper(H_CERTBOT, {'domain': DOMAIN, 'account': before['accounts'][0], 'timeout': 240},
                        mounts=mounts, network='host', timeout=300)
    log = ctx.log('certbot', result['output'].encode())
    after = le_state()
    lineage = after['live'].get(DOMAIN) or {}
    problems = []
    if result['returncode']:
        problems.append(f'certbot exited {result["returncode"]}')
    if not (lineage.get('fullchain.pem') and lineage.get('privkey.pem') and f'{DOMAIN}.conf' in after['renewal']):
        problems.append('the lineage paths are not all present')
    others_before = {name: digest for name, digest in before['renewal'].items() if name != f'{DOMAIN}.conf'}
    others_after = {name: digest for name, digest in after['renewal'].items() if name != f'{DOMAIN}.conf'}
    if others_before != others_after or set(before['live']) - {DOMAIN} != set(after['live']) - {DOMAIN}:
        problems.append('another lineage changed')
    if after['accounts'] != before['accounts']:
        problems.append('the ACME account set changed')
    if problems:
        raise InstallError('; '.join(problems) + f'; see {log}.')
    return {'lineage': lineage, 'renewal_conf': f'{DOMAIN}.conf', 'account_reused': True, 'certbot_log': log,
            'summary': f'lineage {DOMAIN} present (paths only recorded)'}


def https_checks(ctx) -> tuple:
    def check():
        result = probe('https', DOMAIN, '/health/', timeout=3)
        return result.get('status') == 200 and health_ok(result.get('json'), ctx.revision), {
            'status': result.get('status'), 'error': result.get('error')}
    passed, observations = poll(check, attempts=30, interval=0.25)
    final = probe('https', DOMAIN, '/health/', timeout=5)
    headers = final.get('headers', {})
    problems = [] if passed else [f'https://{DOMAIN}/health/ did not serve the installed revision']
    for name, value in (('strict-transport-security', 'max-age=31536000'), ('x-content-type-options', 'nosniff'),
                        ('referrer-policy', 'same-origin'), ('x-robots-tag', 'noindex, nofollow')):
        if headers.get(name) != [value]:
            problems.append(f'{name} is not exactly one {value!r}')
    # nginx picks the server by Host, so SNI app.quillmd.com + Host cpt.quillmd.com reaches
    # this vhost with the wrong SNI; its $ssl_server_name check must close it (444).
    mismatch = probe('https', APP_HEALTH_HOST, '/health/', headers={'Host': DOMAIN}, timeout=5)
    if 'error' not in mismatch:
        problems.append('a request whose SNI is not the domain was answered instead of closed (444)')
    return problems, {'observations': observations[-3:], 'final': final, 'sni_mismatch': mismatch}


def phase_https_vhost(ctx) -> dict:
    preflight = require_receipt(ctx, 'preflight')
    require_receipt(ctx, 'cert')
    confs = rendered_vhosts(ctx.revision)
    http_sha, https_sha = sha256(confs['http'].encode()), sha256(confs['https'].encode())
    state = vhost_state()
    if state['link_target'] != VHOST_LINK_TARGET or state['file_sha256'] not in (http_sha, https_sha):
        raise InstallError('quillmd-cpt is not the HTTP stage this installer wrote; refusing.')
    lineage = le_state()['live'].get(DOMAIN) or {}
    if not (lineage.get('fullchain.pem') and lineage.get('privkey.pem')):
        raise InstallError(f'The {DOMAIN} lineage is not present.')

    def apply():
        vhost_operation('replace', expected_sha256=http_sha,
                        content=base64.b64encode(confs['https'].encode()).decode())

    def undo():
        if vhost_state()['file_sha256'] == https_sha:
            vhost_operation('replace', expected_sha256=https_sha,
                            content=base64.b64encode(confs['http'].encode()).decode())

    def verify():
        problems, evidence = https_checks(ctx)
        redirect = probe('http', DOMAIN, '/', connect_ip='127.0.0.1')
        if redirect.get('status') != 301 or redirect.get('headers', {}).get('location') != [f'https://{DOMAIN}/']:
            problems.append(f'http://{DOMAIN}/ did not redirect to https')
        acme = acme_probe(ctx, 'https-vhost')
        if not acme['passed'] or not acme['probe_removed']:
            problems.append('the ACME challenge path stopped serving (renewal would fail)')
        problems += ingress_checks(ctx, preflight)
        if problems:
            raise InstallError('; '.join(problems) + '.', details=evidence)
        return {**evidence, 'redirect': redirect, 'acme': acme}
    already = state['file_sha256'] == https_sha
    result = verify() if already else publish_vhost(ctx, apply, undo, verify)
    return {**result, 'vhost_sha256': https_sha, 'already_installed': already,
            'summary': f'https://{DOMAIN}/ serves {ctx.revision[:12]}'}


def other_lineages(le: dict) -> tuple:
    """Let's Encrypt state without this domain's own lineage, on both sides of any comparison: a reinstall's
    preflight baseline already holds that lineage."""
    return ({name: digest for name, digest in le['renewal'].items() if name != f'{DOMAIN}.conf'},
            set(le['live']) - {DOMAIN})


def phase_verify(ctx) -> dict:
    preflight = require_receipt(ctx, 'preflight')['details']
    image_id = installed_image(ctx)
    problems = []
    files = nginx_file_state()
    if files['available'].get('quillmd') != QUILLMD_VHOST_SHA256:
        problems.append('the quillmd vhost sha256 changed')
    expected_available = {**preflight['nginx_files']['available'],
                          VHOST_NAME: sha256(rendered_vhosts(ctx.revision)['https'].encode())}
    if files['available'] != expected_available:
        problems.append('sites-available differs from the baseline plus quillmd-cpt')
    if files['enabled'] != {**preflight['nginx_files']['enabled'], VHOST_NAME: VHOST_LINK_TARGET}:
        problems.append('sites-enabled differs from the baseline plus quillmd-cpt')
    if (files['nginx_conf_sha256'], files['conf_d']) != (preflight['nginx_files']['nginx_conf_sha256'],
                                                         preflight['nginx_files']['conf_d']):
        problems.append('nginx.conf or conf.d changed')
    problems += ingress_checks(ctx, {'details': preflight})
    cotenants = cotenant_check()
    if cotenants != preflight['cotenants']:
        problems.append('scripts/check-cotenants.sh result changed')
    now = containers()
    for name, row in preflight['containers'].items():
        if name.startswith('cpt-studio-') or row['state'] != 'running':
            continue
        if now.get(name, {}).get('id') != row['id'] or now[name]['state'] != 'running':
            problems.append(f'container {name} is no longer the same running container')
    missing_volumes = sorted(set(preflight['volumes']) - set(volumes()))
    if missing_volumes:
        problems.append(f'volumes disappeared: {missing_volumes}')
    if other_lineages(le_state()) != other_lineages(preflight['letsencrypt']):
        problems.append('another Let\'s Encrypt lineage changed')
    postgres = inspect('image', POSTGRES_IMAGE) or {}
    db = inspect('container', DB_CONTAINER)
    if db is None or db_container_problems(db, postgres.get('Id')) or not db['State'].get('Running'):
        problems.append(f'{DB_CONTAINER} is not the running, labelled, loopback-only database')
    for role, name in SERVICES.items():
        container = inspect('container', name)
        if container is None or not container['State'].get('Running'):
            problems.append(f'{name} is not running')
        else:
            problems += [f'{name}: {problem}' for problem in service_problems(container, role, image_id)]
    https_problems, evidence = https_checks(ctx)
    problems += https_problems
    foreign = foreign_uid_tasks(APP_UID, own_service_ids())
    if foreign:
        problems.append(f'uid {APP_UID} now runs {foreign} task(s) outside CPT Studio')
    appeared = sorted(set(now) - set(preflight['containers']) - {DB_CONTAINER, *SERVICES.values()})
    details = {'evidence': evidence, 'containers_appeared_elsewhere': appeared, 'image_id': image_id}
    if problems:
        raise InstallError(f'verify found {len(problems)} difference(s): ' + '; '.join(problems) + '.',
                           details={**details, 'problems': problems})
    return {**details, 'summary': f'installed {ctx.revision[:12]} verified; co-tenants and app.quillmd.com unchanged'}


def phase_rollback_app(ctx) -> dict:
    """Refuse, before stopping anything, while their revision recorded what an older revision would act on wrongly
    (undo_hazards); otherwise stop the web and worker, close every stage their revision left open since they were
    created and every open stage of a kind the next worker does not run (close_undone_stages, with their own image),
    read again, then remove them - so a parked pair renamed back or an older revision installed afterwards never runs
    that work under its own rules. When the stages cannot be closed, or the second read names a record (a send in
    flight when the worker stopped is an unknown outcome), the pair is left stopped, not removed."""
    pair = {}
    for role in ('worker', 'web'):
        container = inspect('container', SERVICES[role])
        if container is not None:
            if not owned(container, role):
                raise InstallError(f'{SERVICES[role]} is not a CPT Studio {role} container; refusing to remove it.')
            pair[role] = container
    closed = None
    if pair:
        first = pair.get('web') or pair['worker']
        revision = labels_of(first).get(REVISION_LABEL) or 'unlabelled'
        env = read_protected_env(APP_ENV, APP_ENV_KEYS)
        require_db()
        # Refutation p1, migrate-0/-1: an older revision's web and worker - a parked pair renamed back, or one
        # reinstalled - would act on these under their own rules (a send without a date, an identical re-send of a
        # request that failed); they are cleared on this revision's web, which keeps serving meanwhile.
        found = undo_hazards(first['Image'], env, revision)
        if found:
            raise InstallError(f'{hazard_summary(found)} hold records an older revision would act on under its own '
                               'rules; nothing was stopped or removed. Clear them on this revision\'s web (ops/INSTALL.md, '
                               'Reinstalling an older revision), then rerun --phase rollback-app.',
                               details={'hazards': found})
    for role in pair:
        stop_service_container(SERVICES[role], role)
    if pair:
        # the next worker: the parked pair's when one is parked (the '*-previous' recovery), else an unknown older one
        next_image = None
        for role in ('worker', 'web'):
            previous = inspect('container', SERVICES[role] + '-previous')
            if previous is not None and owned(previous, role):
                next_image = previous['Image']
                break
        kinds = stage_kinds_of(next_image, env) if next_image else list(COMMON_STAGE_KINDS)
        try:
            require_db()
            closed = close_undone_stages(first['Image'], env,
                                         min(created_at(container) for container in pair.values()), revision,
                                         'its web and worker were removed (rollback-app)', kinds)
        except InstallError as error:
            raise InstallError(f'Web and worker stopped, not removed: the stages they left open could not be closed '
                               f'({error}). Rerun --phase rollback-app once that is resolved.') from error
        hazards = closed.get('hazards')
        if not isinstance(hazards, dict) or hazards:
            named = hazard_summary(hazards) if isinstance(hazards, dict) else 'the close did not say which encounters'
            raise InstallError(f'Web and worker stopped, not removed: after the close, {named} hold records an older '
                               'revision would act on under its own rules. Start them again (docker start '
                               f'{SERVICES["worker"]} {SERVICES["web"]}), clear them on this revision\'s web '
                               '(ops/INSTALL.md, Reinstalling an older revision), then rerun --phase rollback-app.',
                               details={'hazards': hazards, 'stages_closed': closed})
    removed = {}
    for role in ('worker', 'web'):
        name = SERVICES[role]
        removed[name] = role in pair
        remove_service_container(name, role)
    parked = [name + '-previous' for name in SERVICES.values() if inspect('container', name + '-previous')]
    return {'removed': removed, 'stages_closed': closed, 'parked_left_in_place': parked,
            'summary': 'web and worker removed after closing their open stages; database, volumes, images and '
                       'secrets kept'}


def recorded_vhosts(ctx) -> dict:
    """sha256 -> (revision, kind) of every vhost stage an earlier successful vhost phase installed, any revision."""
    found = {}
    for phase, kind in (('http-vhost', 'http'), ('https-vhost', 'https')):
        for path in sorted(ctx.receipts.glob(f'{phase}-*.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            digest = (record.get('details') or {}).get('vhost_sha256')
            if (record.get('phase') == phase and record.get('ok') and isinstance(digest, str)
                    and re.fullmatch(r'[0-9a-f]{64}', digest) and SHA_RE.fullmatch(str(record.get('revision')))):
                found.setdefault(digest, (record['revision'], kind))
    return found


def phase_rollback_vhost(ctx) -> dict:
    """Remove quillmd-cpt when it holds a stage this installer wrote: this revision's, or one an earlier
    successful vhost receipt recorded (the documented republish after deploy/nginx changed). The removal is
    undone with the exact bytes it removed, re-rendered from the revision that installed them."""
    preflight = require_receipt(ctx, 'preflight')
    confs = rendered_vhosts(ctx.revision)
    state = vhost_state()
    if not state['file_exists'] and not state['link_exists']:
        return {'state': state, 'summary': 'quillmd-cpt already absent'}
    restorable = {sha256(confs['http'].encode()): confs['http'].encode(),
                  sha256(confs['https'].encode()): confs['https'].encode()}
    if state['file_exists'] and state['file_sha256'] not in restorable:
        if state['file_sha256'] not in recorded_vhosts(ctx):
            raise InstallError('quillmd-cpt holds content this installer did not write; refusing to remove it.')
        # An earlier install's stage, recorded by an ok vhost receipt: restore exactly the bytes that are live now
        # (re-rendering that revision with this installer's parameters need not reproduce them).
        live = live_vhost_bytes()
        if live is None or sha256(live) != state['file_sha256']:
            raise InstallError('quillmd-cpt changed while it was being read; refusing.')
        restorable[state['file_sha256']] = live
    allowed = sorted(restorable)
    previous = state['file_sha256']

    def apply():
        vhost_operation('remove', allowed_sha256=allowed)

    def undo():
        now = vhost_state()
        if previous in restorable and state['link_exists'] and not now['file_exists'] and not now['link_exists']:
            vhost_operation('install', content=base64.b64encode(restorable[previous]).decode())

    def verify():
        # Without the vhost the domain must land exactly where an unknown host lands.
        problems = ingress_checks(ctx, preflight)
        cpt = cpt_probes()
        unmatched = {'http': probe('http', UNMATCHED_HOST, '/', connect_ip='127.0.0.1', method='HEAD'),
                     'https': probe('https', UNMATCHED_HOST, '/', connect_ip='127.0.0.1', verify=False, method='HEAD')}
        if (cpt['http'].get('status'), cpt['https'].get('cert_sha256')) != (
                unmatched['http'].get('status'), unmatched['https'].get('cert_sha256')):
            problems.append(f'{DOMAIN} does not route like an unknown host after removal')
        if problems:
            raise InstallError('; '.join(problems) + '.')
        return {'cpt_after': cpt, 'unmatched': unmatched}
    result = publish_vhost(ctx, apply, undo, verify)
    return {**result, 'summary': 'quillmd-cpt removed; nginx reloaded; certificate lineage kept'}


PHASES = {
    'preflight': phase_preflight, 'secrets': phase_secrets, 'image': phase_image, 'db': phase_db,
    'app': phase_app, 'reference': phase_reference, 'provision': phase_provision,
    'http-vhost': phase_http_vhost, 'cert': phase_cert, 'https-vhost': phase_https_vhost,
    'verify': phase_verify, 'rollback-app': phase_rollback_app, 'rollback-vhost': phase_rollback_vhost,
}


def main(argv=None) -> int:
    os.umask(0o077)
    args = parse_args(argv)
    try:
        receipts = prepare_receipts(args.receipts)
    except (InstallError, OSError) as error:
        print(json.dumps({'phase': args.phase, 'ok': False, 'error': f'--receipts unusable: {error}'}))
        return 1
    lock = os.open(receipts / '.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        print(json.dumps({'phase': args.phase, 'ok': False, 'error': 'another phase is running on these receipts'}))
        return 1
    ctx = Context(args, receipts)
    record = {'phase': args.phase, 'revision': args.revision, 'started_at': utc_now(),
              'installer_sha256': sha256(SELF.read_bytes())}
    code = 1
    try:
        record['door'] = check_door(os.environ, args.revision)
        record['tree'] = check_tree(args.revision, record['door']['declaration_commit'])
        details = PHASES[args.phase](ctx)
        record.update(ok=True, details=details)
        code = 0
    except InstallError as error:
        record.update(ok=False, error=str(error), details=error.details)
        if error.output:
            record['failure_log'] = ctx.log('failure', error.output)
    except Exception as error:  # noqa: BLE001 — recorded, never swallowed silently
        record.update(ok=False, error=f'unexpected {type(error).__name__}; see failure log')
        record['failure_log'] = ctx.log('failure', traceback.format_exc().encode())
    finally:
        record.setdefault('ok', False)
        record['finished_at'] = utc_now()
        path = write_receipt(receipts, args.phase, record)
        summary = (record.get('details') or {}).get('summary') if record['ok'] else record.get('error')
        print(json.dumps({'phase': args.phase, 'ok': record['ok'], 'summary': summary, 'receipt': str(path)}))
    return code


if __name__ == '__main__':
    sys.exit(main())
