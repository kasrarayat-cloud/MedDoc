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
import ast
import base64
import datetime as dt
import fcntl
import getpass
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
import threading
import time
import traceback
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
APP = 'cpt-studio'
SELF = Path(__file__).resolve()

DOMAIN = 'cpt.quillmd.com'
PUBLIC_IPV4 = '147.189.172.8'
WEB_PORT = 9150  # the web's port on a fresh host, where nothing is served through the vhost yet
# Blue/green (ops/INSTALL.md, app): an install starts the incoming web on the other of these two loopback ports beside
# the serving one, switches the vhost's upstream to it with a graceful nginx reload, and stops the old web only once it
# is drained. The port therefore alternates from install to install.
WEB_PORTS = (9150, 9151)
DB_PORT = 55451
UPSTREAM = f'127.0.0.1:{WEB_PORT}'  # upstream(WEB_PORT): the fresh-host rendering
APP_HEALTH_HOST = 'app.quillmd.com'

NETWORK = 'cpt-studio-net'
DB_VOLUME = 'cpt-studio-pg'
FILES_VOLUME = 'cpt-studio-files'
DB_CONTAINER = 'cpt-studio-db'
SERVICES = {'web': 'cpt-studio-web', 'worker': 'cpt-studio-worker'}
# A stopped worker finishes the stage it is in (run_worker), which may be inside a harness participant phase's tool
# loop: that ends by settings.PARTICIPANT_LOOP_DEADLINE_SECONDS (540 s for at most 4 exchanges; one send by 330 s,
# Corti's by 150 s) and must be recorded before Docker kills the worker, or a request that reached the vendor is left
# 'sending' (HARNESS.md 8, 11.2). 600 s is settings.STALE_RUNNING_SECONDS, the stale-stage sweep's bound: a stage still
# running when the stop timeout passes is one that sweep settles as cut short anyway, so waiting longer buys nothing.
STOP_SECONDS = {'web': 30, 'worker': 600}
# The incoming web of a blue/green install, renamed to SERVICES['web'] once the old web is drained and stopped.
INCOMING_WEB = SERVICES['web'] + '-next'
# The old web's drain after the switch (drain_web): at least DRAIN_MIN_SECONDS, above gunicorn's 120 s request timeout
# (deploy/gunicorn.conf.py), so every request it accepted before the switch has ended; then until DRAIN_QUIET_SECONDS
# consecutive one-second samples show no connection to its port and no nginx worker still shutting down from the
# reload; never longer than DRAIN_MAX_SECONDS (a co-tenant's long-lived connection keeps an old nginx worker alive).
DRAIN_MIN_SECONDS, DRAIN_QUIET_SECONDS, DRAIN_MAX_SECONDS = 130, 10, 600
# The availability record of a blue/green switch: https://cpt.quillmd.com/health/ through the public path, this often.
AVAILABILITY_INTERVAL_SECONDS = 0.5
AVAILABILITY_KEPT = 200  # non-200 samples kept in the receipt (all are counted)
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
# The harness participants' credentials (HARNESS.md 8), optional and kept apart from the all-or-nothing set above:
# adding them to it would read every existing install as partial. Each is copied unread from the source the owner
# places (root 0600 in a root 0700 directory) when it exists, checked by key NAME only, and mounted read-only into the
# worker alone, for a live participant only; the web is given the path and no file, as for Corti. A missing source
# leaves that participant disabled. Models and endpoints are the adapters' constants, never the installer's.
PROVIDER_SOURCES = '/etc/cpt-studio-provider-sources'
PARTICIPANTS = {
    'astra': {'source': f'{PROVIDER_SOURCES}/openai.env', 'target': f'{ETC_DIR}/openai-credentials.env',
              'mounted': '/run/cpt-studio/openai-credentials.env', 'file_env': 'CPT_STUDIO_OPENAI_CREDENTIALS_FILE',
              'mode_env': 'CPT_STUDIO_ASTRA_MODE', 'loader': 'load_openai_credentials',
              'setting': 'OPENAI_CREDENTIALS_FILE', 'required': ('OPENAI_API_KEY',), 'optional': ('OPENAI_PROJECT',)},
    'fable': {'source': f'{PROVIDER_SOURCES}/anthropic.env', 'target': f'{ETC_DIR}/anthropic-credentials.env',
              'mounted': '/run/cpt-studio/anthropic-credentials.env',
              'file_env': 'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE', 'mode_env': 'CPT_STUDIO_FABLE_MODE',
              'loader': 'load_anthropic_credentials', 'setting': 'ANTHROPIC_CREDENTIALS_FILE',
              'required': ('ANTHROPIC_API_KEY',), 'optional': ('ANTHROPIC_WORKSPACE_ID',)},
}
PARTICIPANT_FILE_LIMIT = 32_000  # the size the application's loaders accept (HARNESS.md 8)
# The interpreter's credential (the Gemini migration: design/FINAL.md 13, DECISIONS D14), beside the participants' and
# never one of them: it has its own mode (--interpreter-mode, CPT_STUDIO_GEMINI_MODE) and no access check. The owner's
# source is root 0600, one line GEMINI_API_KEY=<key>; it is copied unread, by the participants' own helper and rules
# (H_PARTICIPANT_SECRETS: key NAMES only), to /etc/cpt-studio/gemini.env (10150:10150 0400), and mounted read-only into
# the WORKER alone when the interpreter is live. The web is given the mode and the path and no file, as for Corti and
# the participants (a web that builds what the worker would send needs the worker's configuration, and only the worker
# sends; service_problems refuses any bind in a web). A missing source leaves the interpreter installable only disabled
# or replayed. Replay reads the recordings the image ships (tests/fixtures/interpretation/gemini/, kept in the image by
# deploy/.dockerignore) and sends nothing. The model and the endpoint are the adapter's constants, never the
# installer's.
INTERPRETER = {'name': 'gemini', 'source': f'{PROVIDER_SOURCES}/gemini.env', 'target': f'{ETC_DIR}/gemini.env',
               'mounted': '/run/cpt-studio/gemini.env', 'file_env': 'CPT_STUDIO_GEMINI_CREDENTIALS_FILE',
               'mode_env': 'CPT_STUDIO_GEMINI_MODE', 'replay_env': 'CPT_STUDIO_GEMINI_REPLAY_DIR',
               'replay_dir': '/app/tests/fixtures/interpretation', 'module': 'studio.interpretation.adapter',
               'loader': 'load_gemini_credentials', 'setting': 'GEMINI_CREDENTIALS_FILE',
               'required': ('GEMINI_API_KEY',), 'optional': ()}
INTERPRETER_MODES = ('disabled', 'live', 'replay')  # FINAL 13: --interpreter-mode live|replay|disabled
# An access check sends one coding request (Corti, after the OAuth token request its adapter sends first) or one run of
# the pipeline's tool loop, one request per exchange and at most PARTICIPANT_MAX_EXCHANGES (Astra, Fable): its deadline is the participant send deadline (330 s), plus the container's
# start.
ACCESS_CHECK_SECONDS = 420
ACCESS_CHECK_OUTPUT_LIMIT = 64 * 1024
# The CMS passage files the revision commits (HARNESS.md 5), in the repository and as the image ships them (/app is the
# image's copy of cpt-studio/, built from git archive of the revision).
PASSAGE_DATA = f'{APP}/studio/reference/data'
PASSAGE_DATA_IN_IMAGE = '/app/studio/reference/data'
INITIAL_CREDENTIALS = 'initial-credentials.json'
AGENT_CREDENTIALS = Path('/home/claude/.cpt-studio/agent-credentials.json')
# The operators phase's two platform-operator accounts (ops/INSTALL.md, operators): no workspace membership, a grant
# from `manage grant_operator`. The agent's login is a user file like AGENT_CREDENTIALS; the human's is root-only.
OPERATOR_ACCOUNTS_SPEC = (('ops-agent', 'agent', 'CPT Studio operations agent'),
                          ('platform-operator', 'human', 'CPT Studio platform operator'))
OPERATOR_CREDENTIALS = 'operator-credentials.json'
OPS_AGENT_CREDENTIALS = Path('/home/claude/.cpt-studio/ops-agent-credentials.json')
REASSESS_LIMIT = 20  # encounters per reassess phase
REASSESS_SECONDS = 300
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

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
# CPT Studio's own note on every CMS reference source it imports (ReferenceSource.license_note, written from
# studio.reference.importers.LICENSE_NOTE). The owner, 2026-11-01 (HARNESS.md 11.6): CPT Studio's own wording must not
# imply a licensing exemption, so the note states a fact, never a permission. The license-note phase replaces exactly
# the old text with exactly the new one on the rows imported before the importer changed; any other note is left alone.
LICENSE_NOTE_OLD = ('CPT codes are copyright the American Medical Association; descriptors are not imported or '
                    'displayed. Used for internal synthetic evaluation only; commercial CPT use requires an AMA '
                    'license.')
LICENSE_NOTE_NEW = ('CPT codes are copyright the American Medical Association; descriptors are not imported or '
                    'displayed. CPT Studio holds no AMA licence; whether its use of CPT content needs one is an open '
                    'owner decision.')

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


def utc_now_ms() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


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
    'provider_mode': {'app', 'switch-back'}, 'authorization_ref': {'app', 'switch-back'},
    'astra_mode': {'app', 'switch-back'}, 'fable_mode': {'app', 'switch-back'}, 'access_check': {'app'},
    'interpreter_mode': {'app', 'switch-back'},
    'owner_username': {'provision'}, 'owner_display_name': {'provision'}, 'agent_username': {'provision'},
    'agent_display_name': {'provision'}, 'workspace_name': {'provision'},
    'reset_passwords': {'provision', 'operators'},
    'encounter': {'reassess'}, 'dry_run': {'reassess'},
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
    parser.add_argument('--astra-mode', choices=('disabled', 'live'), help='Astra (OpenAI); disabled when not given')
    parser.add_argument('--fable-mode', choices=('disabled', 'live'), help='Fable (Anthropic); disabled when not given')
    parser.add_argument('--interpreter-mode', choices=INTERPRETER_MODES,
                        help='the interpreter (Gemini; design/FINAL.md 13): disabled when not given, which pauses '
                             "every upload's reading (verify reports an app phase that did not give it); live sends "
                             'under --authorization-ref; replay reads the recordings the image ships and sends nothing')
    parser.add_argument('--access-check', action='store_true', default=None,
                        help='after the app phase, check each live participant with real requests: one coding '
                             'request for Corti, and for Astra and for Fable one run of the tool loop, one request '
                             'per exchange and at most PARTICIPANT_MAX_EXCHANGES (4)')
    parser.add_argument('--owner-username')
    parser.add_argument('--owner-display-name')
    parser.add_argument('--agent-username')
    parser.add_argument('--agent-display-name')
    parser.add_argument('--workspace-name')
    parser.add_argument('--reset-passwords', action='store_true', default=None)
    parser.add_argument('--encounter', action='append',
                        help='reassess: an encounter id to re-assess from its retained responses (repeatable)')
    parser.add_argument('--dry-run', action='store_true', default=None,
                        help='reassess: pass --dry-run to reassess_retained (nothing is queued)')
    args = parser.parse_args(argv)
    problem = argument_problem(args)
    if problem:
        parser.error(problem)
    args.astra_mode = args.astra_mode or 'disabled'
    args.fable_mode = args.fable_mode or 'disabled'
    # --interpreter-mode stays None when it is not given (interpreter_mode reads that as disabled), so the app receipt
    # can say whether it was given: verify does not call an interpreter left disabled by default verified (the review of
    # S14, finding 2; design/FINAL.md 13: the install uses live)
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
    if args.phase == 'reassess':
        encounters = args.encounter or []
        if not encounters:
            return '--phase reassess needs at least one --encounter <id>.'
        if len(encounters) > REASSESS_LIMIT:
            return f'--phase reassess takes at most {REASSESS_LIMIT} --encounter ids per run.'
        if len(set(encounters)) != len(encounters):
            return '--encounter ids must not repeat.'
        for value in encounters:
            if not UUID_RE.fullmatch(value):
                return f'--encounter {value!r} is not a lowercase encounter id (UUID).'
    if args.phase in ('app', 'switch-back'):
        if args.provider_mode is None:
            return f'--phase {args.phase} needs an explicit --provider-mode (disabled or live).'
        if args.provider_mode == 'live' and not args.authorization_ref:
            return '--provider-mode live needs --authorization-ref (a ruling file tracked at the revision).'
        # A live participant sends under the same recorded authority as Corti (HARNESS.md 8; jobs._live_gate).
        participants = [name for name in PARTICIPANTS if getattr(args, f'{name}_mode') == 'live']
        for name in participants:
            if not args.authorization_ref:
                return f'--{name}-mode live needs --authorization-ref (a ruling file tracked at the revision).'
        # The interpreter sends under the same recorded authority (jobs._live_gate; design/FINAL.md 6.3).
        interpreting = getattr(args, 'interpreter_mode', None) == 'live'
        if interpreting and not args.authorization_ref:
            return '--interpreter-mode live needs --authorization-ref (a ruling file tracked at the revision).'
        if args.authorization_ref and args.provider_mode == 'disabled' and not participants and not interpreting:
            return ('--authorization-ref only applies to --provider-mode live, --astra-mode live, --fable-mode live or '
                    '--interpreter-mode live.')
        if args.access_check and args.provider_mode != 'live' and not participants:
            return ('--access-check checks each live participant: give --provider-mode live, --astra-mode live or '
                    '--fable-mode live.')
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

# The harness participants' credentials (HARNESS.md 8), beside the set above and never part of it. Every check runs
# before anything is written, and a refusal writes nothing for either participant. A source is read through a
# descriptor that followed no link, and must be a root-owned 0600 regular file in the root-owned 0700 sources directory.
# Only key NAMES are read, and only the expected names are ever reported: a line setting any other key is counted, never
# echoed (a key pasted without its name would otherwise be printed as one). A copy is written once, byte for byte,
# 10150:10150 0400, and read back; a copy already there must equal its source (to rotate: remove the copy by hand, run
# the secrets phase, then the app phase, whose new worker mounts the new file). Values never leave the helper.
H_PARTICIPANT_SECRETS = '''
T, S = '/target', '/sources'
EXPECTED = {'regular': True, 'uid': P['uid'], 'gid': P['uid'], 'mode': '0o400'}

def names(raw):
    out = []
    for line in raw.decode('utf-8', 'replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('export '):
            s = s[7:].lstrip()
        name, sep, _ = s.partition('=')
        out.append(name.strip() if sep else '')
    return out

def opened(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None, {'exists': False}
    except OSError:  # a link (O_NOFOLLOW), a socket: not a regular file
        return None, {'exists': True, 'regular': False}
    try:
        i = os.fstat(fd)
        facts = {'exists': True, 'regular': stat.S_ISREG(i.st_mode), 'uid': i.st_uid, 'gid': i.st_gid,
                 'mode': oct(stat.S_IMODE(i.st_mode))}
        if not facts['regular']:
            return None, facts
        data = b''
        while len(data) <= P['limit']:
            chunk = os.read(fd, P['limit'] + 1 - len(data))
            if not chunk:
                break
            data += chunk
        return data, facts
    finally:
        os.close(fd)

def key_problems(label, raw, required, optional):
    found, known = names(raw), required + optional
    problems = []
    others = sum(1 for name in found if name not in known)
    if others:
        problems.append(label + ' has ' + str(others) + ' line(s) setting no key of ' + ', '.join(known))
    problems += [label + ' sets ' + name + ' more than once' for name in known if found.count(name) > 1]
    missing = [name for name in required if name not in found]
    if missing:
        problems.append(label + ' lacks key name(s): ' + ', '.join(missing))
    return problems, [name for name in known if name in found]

def stage(name, data):
    tmp = os.path.join(T, '.' + name + '.new')
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
    os.link(tmp, os.path.join(T, name))
    os.unlink(tmp)

problems, copies, report = [], [], {}
if P['sources_mounted']:
    d = os.lstat(S)
    if not (stat.S_ISDIR(d.st_mode) and d.st_uid == 0 and d.st_gid == 0 and stat.S_IMODE(d.st_mode) == 0o700):
        problems.append(P['sources'] + ' is not a root-owned 0700 directory')
for p in P['participants']:
    if P['sources_mounted']:
        source, found = opened(os.path.join(S, p['source']))
    else:
        source, found = None, {'exists': False}
    copy, held = opened(os.path.join(T, p['target']))
    entry = {'source': 'present' if found['exists'] else 'absent', 'key_names': []}
    if os.path.lexists(os.path.join(T, '.' + p['target'] + '.new')):
        problems.append('a staged copy of ' + p['target_path'] + ' from an interrupted run exists; resolve it by hand')
    if found['exists']:
        if not found.get('regular') or (found['uid'], found['gid'], found['mode']) != (0, 0, '0o600'):
            problems.append(p['source_path'] + ' is not a root-owned 0600 regular file')
        elif len(source) > P['limit']:
            problems.append(p['source_path'] + ' is larger than ' + str(P['limit']) + ' bytes')
        else:
            wrong, entry['key_names'] = key_problems(p['source_path'], source, p['required'], p['optional'])
            problems += wrong
    if held['exists']:
        entry['state'] = 'present'
        if {key: held.get(key) for key in EXPECTED} != EXPECTED:
            problems.append(p['target_path'] + ' is not the ' + str(P['uid']) + ':' + str(P['uid'])
                            + ' 0400 regular file this phase writes')
        elif len(copy) > P['limit']:
            problems.append(p['target_path'] + ' is larger than ' + str(P['limit']) + ' bytes')
        elif found['exists'] and copy != source:
            problems.append(p['target_path'] + ' differs from its source; to rotate, remove it by hand, then run '
                            'the secrets phase and the app phase')
        else:
            wrong, entry['key_names'] = key_problems(p['target_path'], copy, p['required'], p['optional'])
            problems += wrong
    elif found['exists']:
        entry['state'] = 'to copy'
        copies.append((p['name'], p['target'], source))
    else:
        entry['state'] = 'not provided'
    report[p['name']] = entry
if not problems:
    for name, target, data in copies:
        stage(target, data)
    if copies:
        d = os.open(T, os.O_RDONLY | os.O_DIRECTORY)
        os.fsync(d)
        os.close(d)
    for name, target, data in copies:
        written, facts = opened(os.path.join(T, target))
        report[name]['state'] = 'created'
        if written != data or {key: facts.get(key) for key in EXPECTED} != EXPECTED:
            problems.append(target + ' was written but does not read back as its source with its owner and mode')
else:
    for entry in report.values():
        if entry['state'] == 'to copy':
            entry['state'] = 'not written'
R = {'participants': report}
if problems:
    R['error'] = '; '.join(problems)
print(json.dumps(R, sort_keys=True))
'''

# Whether output from a container that held participants' credentials files (P['files'], mounted at /scan/<name>)
# carries a value from them: read here, answered with key names only (HARNESS.md I9). A value is matched as written,
# without an inline comment and unquoted; one under P['min_length'] characters is not matched (it would by chance).
H_CREDENTIAL_SCAN = '''
blob = base64.b64decode(P['blob'])
found = []
for name in P['files']:
    for line in read('/scan/' + name, P['limit'] + 1).decode('utf-8', 'replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('export '):
            s = s[7:].lstrip()
        key, sep, value = s.partition('=')
        value = value.strip()
        forms = {value, value.split(' #')[0].strip(), value.split('\\t#')[0].strip()}
        forms |= {form[1:-1] for form in list(forms) if len(form) >= 2 and form[0] == form[-1] and form[0] in '\\'"'}
        if sep and any(len(form) >= P['min_length'] and form.encode() in blob for form in forms):
            found.append(key.strip())
print(json.dumps({'found': sorted(set(found))}))
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


def participant_secrets() -> dict:
    """The harness participants' credentials (H_PARTICIPANT_SECRETS): each source the owner placed is copied once into
    /etc/cpt-studio (10150:10150 0400), checked by key name only; a missing source leaves its participant 'not
    provided'. The sources directory is mounted only once it is seen to be a root-owned 0700 directory (and the helper
    looks again); anything else refuses with nothing written. {participant: {state, source, key_names}}."""
    return copied_credentials(PARTICIPANTS, 'participant')


def interpreter_secrets() -> dict:
    """The interpreter's credential (design/FINAL.md 13, D14), copied by the same helper and rules as the participants'
    - unread, checked by key name only, 10150:10150 0400 - in a run of its own, so the participants' set is exactly as
    it was and a refusal of either writes nothing for it. {'gemini': {state, source, key_names}}."""
    return copied_credentials({INTERPRETER['name']: INTERPRETER}, 'interpreter')


def copied_credentials(specs, what) -> dict:
    """H_PARTICIPANT_SECRETS over ``specs`` ({name: spec with source, target, required and optional}); ``what`` names
    them in a refusal. {name: {state, source, key_names}}."""
    folder = helper_stat([PROVIDER_SOURCES])[PROVIDER_SOURCES]
    mounted = bool(folder.get('exists'))
    if mounted and folder != {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}:
        raise InstallError(f'{PROVIDER_SOURCES} is not a root-owned 0700 directory; no {what} credentials file '
                           'was copied.', details={'sources': folder})
    mounts = [f'type=bind,src={ETC_DIR},dst=/target']
    if mounted:
        mounts.append(f'type=bind,src={PROVIDER_SOURCES},dst=/sources,readonly')
    params = {'uid': APP_UID, 'limit': PARTICIPANT_FILE_LIMIT, 'sources_mounted': mounted, 'sources': PROVIDER_SOURCES,
              'participants': [{'name': name, 'source': PurePosixPath(spec['source']).name,
                                'source_path': spec['source'], 'target': PurePosixPath(spec['target']).name,
                                'target_path': spec['target'], 'required': list(spec['required']),
                                'optional': list(spec['optional'])} for name, spec in specs.items()]}
    return run_helper(H_PARTICIPANT_SECRETS, params, mounts=mounts, sensitive=True)['participants']


def credentials_target(name) -> str:
    """The installed credentials file of 'corti', of a harness participant, or of the interpreter ('gemini')."""
    if name == 'corti':
        return CORTI_TARGET
    return INTERPRETER['target'] if name == INTERPRETER['name'] else PARTICIPANTS[name]['target']


def credential_free(outputs, participants) -> bool:
    """Whether no value from the credentials files of ``participants`` ('corti' included) occurs in ``outputs`` (bytes),
    read inside a root helper that answers with key names only (H_CREDENTIAL_SCAN). Output from a container that held
    such a file is recorded only when this says so; when it cannot be told, it is not (HARNESS.md I9)."""
    names = sorted(set(participants))
    if not names:
        return True
    blob = base64.b64encode(b'\n\0\n'.join(outputs)).decode()
    mounts = [f'type=bind,src={credentials_target(name)},dst=/scan/{name},readonly' for name in names]
    try:
        found = run_helper(H_CREDENTIAL_SCAN, {'blob': blob, 'files': names, 'limit': PARTICIPANT_FILE_LIMIT,
                                               'min_length': 8}, mounts=mounts, sensitive=True)['found']
    except (InstallError, KeyError):
        return False
    return found == []


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


def upstream(port) -> str:
    if port not in WEB_PORTS:
        raise InstallError(f'The web port must be one of {", ".join(map(str, WEB_PORTS))}, not {port!r}.')
    return f'127.0.0.1:{port}'


def rendered_vhosts(revision, port=WEB_PORT) -> dict:
    """The revision's two vhost stages: HTTP (no upstream) and HTTPS proxying to 127.0.0.1:``port``."""
    texts = {kind: run(['git', '-C', str(ROOT), 'show', f'{revision}:{path}']).stdout.decode('utf-8')
             for kind, path in TEMPLATES.items()}
    http_conf = render(texts['http'], {'DOMAIN': DOMAIN})
    https_conf = render(texts['https'], {'DOMAIN': DOMAIN, 'UPSTREAM': upstream(port)})
    if not https_conf.startswith(http_conf):
        raise InstallError('The HTTPS vhost must begin with the HTTP stage byte-for-byte (renewals depend on it).')
    for conf in (http_conf, https_conf):
        if any(set(args[1:]) & {'default_server', 'default'} for block in parse_server_blocks(conf)
               for args in block['listen']):
            raise InstallError('The vhost must never claim default_server.')
    return {'http': http_conf, 'https': https_conf}


def vhost_renderings(revision) -> dict:
    """{sha256: {'kind', 'port', 'text'}} of every stage this installer writes for ``revision``: the HTTP stage (port
    None; it names no upstream, so one rendering serves both ports) and the HTTPS stage for each of WEB_PORTS."""
    found = {}
    for port in WEB_PORTS:
        confs = rendered_vhosts(revision, port)
        found.setdefault(sha256(confs['http'].encode()), {'kind': 'http', 'port': None, 'text': confs['http']})
        found[sha256(confs['https'].encode())] = {'kind': 'https', 'port': port, 'text': confs['https']}
    return found


def nginx_statements(text):
    """Every directive as its word list, in order (comments and quoted strings as nginx_tokens reads them)."""
    statements, words = [], []
    for kind, value in nginx_tokens(text):
        if kind == 'punct':
            if words:
                statements.append(words)
            words = []
        else:
            words.append(value)
    return statements


def proxied_port(text):
    """The port of the single ``proxy_pass http://127.0.0.1:<port>;`` in ``text`` when it is one of WEB_PORTS, else
    None: no proxy_pass (the HTTP stage), more than one, another host, another form or another port."""
    passes = [words[1:] for words in nginx_statements(text or '') if words and words[0] == 'proxy_pass']
    if len(passes) != 1 or len(passes[0]) != 1:
        return None
    match = re.fullmatch(r'http://127\.0\.0\.1:([0-9]{1,5})', passes[0][0])
    port = int(match.group(1)) if match else None
    return port if port in WEB_PORTS else None


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
          timeout=5.0, keep_body=False):
    """One request with SNI/Host = ``host``; never follows redirects. Errors become data. ``keep_body`` also returns
    the body read (at most 64 KiB + 1 byte) under 'body'."""
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
        if keep_body:
            result['body'] = body
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


def tcp_entries(proc_texts):
    """(local port, remote port, state) of every socket line of /proc/net/tcp and tcp6 texts (header line skipped)."""
    for text in proc_texts:
        for line in text.splitlines()[1:]:
            fields = line.split()
            if len(fields) > 3:
                yield int(fields[1].rsplit(':', 1)[1], 16), int(fields[2].rsplit(':', 1)[1], 16), fields[3]


def listening_ports(proc_texts) -> set:
    return {local for local, _, state in tcp_entries(proc_texts) if state == '0A'}


# A request can be in flight on a connection only in these states: established, or opening (SYN sent / received).
TCP_ACTIVE_STATES = ('01', '02', '03')


def active_connections(port, proc_texts) -> int:
    """Sockets with ``port`` at either end in a state a request can be in flight on: nginx's side of a proxied
    request (remote port) and the publishing proxy's side (local port) both count."""
    return sum(1 for local, remote, state in tcp_entries(proc_texts)
               if state in TCP_ACTIVE_STATES and port in (local, remote))


def proc_net_texts() -> list:
    return [Path(f'/proc/net/{name}').read_text() for name in ('tcp', 'tcp6') if Path(f'/proc/net/{name}').exists()]


def host_listening_ports() -> set:
    return listening_ports(proc_net_texts())


def established_to(port) -> int:
    return active_connections(port, proc_net_texts())


NGINX_PID_FILE = Path('/run/nginx.pid')


def _nginx_scan(proc_root, pid_file):
    """(master pid or None, [(pid, cmdline)] of the nginx processes counted): the host master read from its pid file and
    its children; every nginx process on the host when there is no readable pid file."""
    try:
        master = int(Path(pid_file).read_text().strip())
    except (OSError, ValueError):
        master = None
    found = []
    for entry in os.scandir(proc_root):
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (Path(proc_root) / entry.name / 'cmdline').read_bytes()
            if master is not None and int(entry.name) != master:
                parent = (Path(proc_root) / entry.name / 'stat').read_text().rsplit(')', 1)[1].split()[1]
                if int(parent) != master:
                    continue
        except (OSError, ValueError, IndexError):  # the process ended mid-scan
            continue
        if cmdline.startswith(b'nginx: '):
            found.append((int(entry.name), cmdline))
    return master, found


def nginx_processes(proc_root=Path('/proc'), pid_file=NGINX_PID_FILE) -> dict:
    """{'visible', 'shutting_down'}: the host nginx's processes this user can see, and how many are workers still
    'shutting down' from a reload (each finishes the requests it accepted under its old configuration). The host
    master is read from its pid file and only its children count; without a readable pid file every nginx process
    on the host counts (a co-tenant's too), which can only lengthen a drain. Seeing none at all is not read as 'none
    shutting down': the caller cannot tell."""
    master, found = _nginx_scan(proc_root, pid_file)
    return {'visible': len(found), 'shutting_down': sum(b'shutting down' in cmdline for _, cmdline in found),
            'master': master}


# Refutation r2, L6-1 and L6-7: which configuration nginx runs is not what `systemctl reload nginx` answered. systemd runs
# a reload job it took even when its client is interrupted (Ctrl-C) or times out, and a master that cannot apply a
# configuration (a listen on an address in use passes `nginx -t`) keeps the one it has while the signaller exits 0.
# nginx applies a reload by starting NEW worker processes (and asking the old ones to finish), and refuses one by keeping
# its workers - so a worker pid absent from an earlier reading is a configuration loaded after that reading.
RELOAD_SEEN_ATTEMPTS, RELOAD_SEEN_INTERVAL = 40, 0.25  # up to 10 s for the master to start its new workers


def nginx_generation(proc_root=Path('/proc'), pid_file=NGINX_PID_FILE):
    """(master pid, frozenset of its worker pids not shutting down) of the host nginx, or None when that cannot be told
    (no readable pid file, no such worker seen, or /proc unreadable). Never raises."""
    try:
        master, found = _nginx_scan(proc_root, pid_file)
    except Exception:  # noqa: BLE001 — cannot tell
        return None
    if master is None:
        return None
    workers = frozenset(pid for pid, cmdline in found if pid != master
                        and cmdline.startswith(b'nginx: worker process') and b'shutting down' not in cmdline)
    return (master, workers) if workers else None


def nginx_moved(before, after):
    """Whether nginx loaded a configuration between two nginx_generation readings: True (another master, or a worker
    ``before`` did not have), False (the same workers), None (either reading is missing: it cannot be told)."""
    if before is None or after is None:
        return None
    return before[0] != after[0] or bool(after[1] - before[1])


def nginx_applied(before):
    """After a reload: whether nginx was seen starting workers with a configuration loaded since ``before`` (an
    nginx_generation reading), observed for up to RELOAD_SEEN_ATTEMPTS x RELOAD_SEEN_INTERVAL; None when it cannot be
    told. Never raises."""
    try:
        passed, observations = poll(lambda: ((lambda moved: (moved is True, {'moved': moved}))(
            nginx_moved(before, nginx_generation()))), attempts=RELOAD_SEEN_ATTEMPTS, interval=RELOAD_SEEN_INTERVAL)
    except Exception:  # noqa: BLE001 — an unreadable /proc is "cannot tell", never a pass
        return None
    if passed:
        return True
    return None if observations[-1]['moved'] is None else False


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


def service_names(role) -> tuple:
    """Every name a CPT Studio container of ``role`` can carry: its own, the parked '-previous' and, for the web, the
    incoming '-next' of a blue/green install."""
    name = SERVICES[role]
    return (name, name + '-previous') + ((INCOMING_WEB,) if role == 'web' else ())


def own_service_ids() -> list:
    return [container['Id'] for role in SERVICES for name in service_names(role)
            if (container := inspect('container', name)) is not None and owned(container, role)]


def published_port(container):
    """The one 127.0.0.1 host port ``container`` publishes for 8000/tcp when it is one of WEB_PORTS, else None."""
    bindings = ((container or {}).get('HostConfig') or {}).get('PortBindings') or {}
    entries = bindings.get('8000/tcp') or []
    if len(bindings) != 1 or len(entries) != 1 or entries[0].get('HostIp') != '127.0.0.1':
        return None
    port = str(entries[0].get('HostPort') or '')
    return int(port) if port.isdigit() and int(port) in WEB_PORTS else None


def other_port(port) -> int:
    (idle,) = [candidate for candidate in WEB_PORTS if candidate != port]
    return idle


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


def participant_modes(args) -> dict:
    """{participant: mode} from --astra-mode and --fable-mode; a participant not given (or an args object that names
    neither) is disabled."""
    return {name: getattr(args, f'{name}_mode', None) or 'disabled' for name in PARTICIPANTS}


def interpreter_mode(args) -> str:
    """The interpreter's mode from --interpreter-mode; 'disabled' when not given (or for an args object that does not
    name it), as every one-shot runs it (design/FINAL.md 13)."""
    mode = getattr(args, 'interpreter_mode', None) or 'disabled'
    if mode not in INTERPRETER_MODES:
        raise InstallError(f'The interpreter mode must be one of {", ".join(INTERPRETER_MODES)}, not {mode!r}.')
    return mode


def participant_mount(name) -> str:
    """A participant's credentials file, read-only at the worker's path (HARNESS.md 8)."""
    spec = PARTICIPANTS[name]
    return f'type=bind,src={spec["target"]},dst={spec["mounted"]},readonly'


def interpreter_mount() -> str:
    """The interpreter's credentials file, read-only at the worker's path (design/FINAL.md 13, D14)."""
    return f'type=bind,src={INTERPRETER["target"]},dst={INTERPRETER["mounted"]},readonly'


def runtime_env(provider_mode, authorization_ref, *, credentials=False, participants=None, files=(), interpreter=None,
                interpreter_file=False):
    """-e flags. Each harness participant is named with its mode - ``participants`` maps them; one not given is
    disabled, as in every one-shot - and a live one (or one in ``files``) with its credentials path. The interpreter is
    named with its mode (``interpreter``; disabled when not given, as in every one-shot), its credentials path when it
    is live (or ``interpreter_file``), and the recordings the image ships when it replays."""
    values = {'CPT_STUDIO_DB_HOST': DB_CONTAINER, 'CPT_STUDIO_DB_PORT': '5432', 'CPT_STUDIO_DB_NAME': DB_NAME,
              'CPT_STUDIO_DB_USER': DB_USER, 'CPT_STUDIO_HTTPS': '1', 'CPT_STUDIO_TRUST_PROXY': '1',
              'CPT_STUDIO_PROVIDER_MODE': provider_mode, 'CPT_STUDIO_AUTHORIZATION_REF': authorization_ref}
    if credentials:
        values['CPT_STUDIO_CORTI_CREDENTIALS_FILE'] = CREDENTIALS_IN_CONTAINER
    for name, spec in PARTICIPANTS.items():
        mode = (participants or {}).get(name) or 'disabled'
        values[spec['mode_env']] = mode
        if mode == 'live' or name in files:
            values[spec['file_env']] = spec['mounted']
    interpreting = interpreter or 'disabled'
    if interpreting not in INTERPRETER_MODES:
        raise InstallError(f'The interpreter mode must be one of {", ".join(INTERPRETER_MODES)}, not {interpreting!r}.')
    values[INTERPRETER['mode_env']] = interpreting
    if interpreting == 'live' or interpreter_file:
        values[INTERPRETER['file_env']] = INTERPRETER['mounted']
    if interpreting == 'replay':
        values[INTERPRETER['replay_env']] = INTERPRETER['replay_dir']
    flags = []
    for name, value in values.items():
        flags += ['-e', f'{name}={value}']
    return flags


def service_args(role, image_id, revision, provider_mode, authorization_ref, participants=None, *, name=None,
                 port=WEB_PORT, interpreter=None):
    """docker run arguments for a long-running role; secrets arrive on stdin as an env-file. ``participants`` maps each
    harness participant to its mode (disabled when not given), and ``interpreter`` is the interpreter's (disabled when
    not given). A web is named ``name`` (the incoming web of a blue/green install: INCOMING_WEB) and publishes
    127.0.0.1:``port``; every other argument is the same."""
    live = provider_mode == 'live'
    modes = {name: (participants or {}).get(name) or 'disabled' for name in PARTICIPANTS}
    interpreting = interpreter or 'disabled'
    container = name or SERVICES[role]
    if container not in ((SERVICES['web'], INCOMING_WEB) if role == 'web' else (SERVICES['worker'],)):
        raise InstallError(f'{container} is not a name a CPT Studio {role} is started under.')
    upstream(port)  # one of WEB_PORTS, or refused
    common = ['--name', container, '--pull=never', '--restart', 'unless-stopped', '--network', NETWORK,
              '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}={role}', '--label', f'{REVISION_LABEL}={revision}',
              '--log-opt', 'max-size=10m', '--log-opt', 'max-file=5', '--stop-timeout', str(STOP_SECONDS[role]),
              '--mount', f'type=volume,src={FILES_VOLUME},dst={STATE_DIR}', '--env-file', '/dev/stdin']
    environment = runtime_env(provider_mode, authorization_ref, credentials=live, participants=modes,
                              interpreter=interpreting)
    if role == 'web':
        # The path, never the file. A context change in the web builds the request it would send to tell a
        # re-check from a re-send (jobs._run_answers); building a request opens nothing, and only the worker
        # sends. Without the path, live mode had no provider in the web, so every setting or billing save
        # re-predicted and the worker re-sent a failed or not-sent request (pre-install review, 2026-10-26).
        # A live harness participant alike: its adapter builds requests without credentials (HARNESS.md 8). And the
        # interpreter alike (design/FINAL.md 13; its adapter reads the key only to send, interpretation.adapter).
        return [*common, *hardening('768m', 128, '256m'), '-p', f'127.0.0.1:{port}:8000', *environment,
                image_id, 'web']
    extra = ['--mount', f'type=bind,src={CORTI_TARGET},dst={CREDENTIALS_IN_CONTAINER},readonly'] if live else []
    for name, mode in modes.items():
        if mode == 'live':
            extra += ['--mount', participant_mount(name)]
    if interpreting == 'live':  # the worker alone holds the interpreter's key (D14)
        extra += ['--mount', interpreter_mount()]
    return [*common, *hardening('1536m', 256, '1g'), '--no-healthcheck', *extra, *environment, image_id, 'worker']


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
            network=None, credentials=False, participant_files=(), environment=None, interpreter_file=False):
    """A --rm container of the app image with provider calls disabled - Corti's, every participant's and the
    interpreter's (design/FINAL.md 13) - unless ``environment`` gives its -e flags; returns the completed process.
    ``credentials``, ``participant_files`` (participant names) and ``interpreter_file`` mount those credentials files
    read-only at the worker's paths."""
    name = f'cpt-studio-oneshot-{secrets.token_hex(8)}'
    if credentials:
        mounts = [*mounts, f'type=bind,src={CORTI_TARGET},dst={CREDENTIALS_IN_CONTAINER},readonly']
    mounts = [*mounts, *(participant_mount(participant) for participant in participant_files)]
    if interpreter_file:
        mounts = [*mounts, interpreter_mount()]
    if environment is None:
        environment = runtime_env('disabled', '', credentials=credentials, files=participant_files,
                                  interpreter_file=interpreter_file)
    argv = [DOCKER, 'run', '--rm', '--name', name, '--pull=never', '--network', network or NETWORK,
            '--no-healthcheck', '--log-driver=none', '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=oneshot',
            *hardening('768m', 128, '256m', user=user), '--env-file', '/dev/stdin', *environment,
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
# A live participant's credentials file, read by the application's own loader as CREDENTIALS_CHECK reads Corti's: in the
# worker's mount layout (the path from its setting), offline, the participant itself disabled - format and permissions.
PARTICIPANT_CREDENTIALS_CHECKS = {
    name: ('from django.conf import settings\n'
           f'from studio.participants.credentials import {spec["loader"]}\n'
           f'{spec["loader"]}(settings.{spec["setting"]})\n'
           f"print('{name}-credentials-parse-ok')\n")
    for name, spec in PARTICIPANTS.items()}
# The interpreter's, likewise (design/FINAL.md 13: "the offline loader check follows the existing pattern"): its own
# loader (interpretation.adapter.load_gemini_credentials, by the participants' rules with GEMINI_API_KEY its one key),
# in the worker's mount layout, offline, with the interpreter itself disabled.
INTERPRETER_CREDENTIALS_CHECK = ('from django.conf import settings\n'
                                 f'from {INTERPRETER["module"]} import {INTERPRETER["loader"]}\n'
                                 f'{INTERPRETER["loader"]}(settings.{INTERPRETER["setting"]})\n'
                                 f"print('{INTERPRETER['name']}-credentials-parse-ok')\n")

# Run by `manage shell -c` in an image of the app (APP_SCRIPT_PRELUDE gives it P, the parameters, and ANSWER); each
# prints one ANSWER line. UNRUNNABLE_STAGES uses only what every revision's models have (057a7d39's included): it is
# also run in the image of the pair an undo restores (stage_kinds_of). The others run in this revision's own image.
APP_SCRIPT_ANSWER = 'cpt-studio-answer '
APP_SCRIPT_PRELUDE = 'import base64, json\nP = json.loads(base64.b64decode({payload!r}))\nANSWER = {answer!r}\n'
# The stage kinds every revision's worker runs (the installed revision 057a7d39's STAGES). An undo keeps open stages of
# the kinds the next worker runs - read from that worker's own image (stage_kinds_of) - and only these when it has no
# image to ask (refutation p1, security-0).
COMMON_STAGE_KINDS = ('analyze', 'assess', 'extract', 'predict')
# The Gemini migration's stage kind 'interpret' (interpretation.JOB_KIND) is not among them (design/FINAL.md 12.1,
# 13): no worker before it runs one, so CLOSE_STAGES closes an open interpret stage on every undo whose next worker
# lacks it, settling the Gemini run it had in flight as any other (sending: unknown, reserved: not sent), and an older
# revision's app phase refuses while one is open (UNRUNNABLE_STAGES), as for the participants' stages.
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
#   second_review - the current assessment's decision set (selected or excluded) holds a code only the bounded second
#              review selected: its re-assessment - after a metadata save, a Resume or a reconciliation - reads the
#              primary answer alone, so the code leaves the decision set without a reviewer's decision (round-7c8
#              skeptic, sk:3; must-fix class 4).
#   second_review_refused - the current assessment read a bounded second review whose response it refused whole (its
#              provider.second_review check failed on a succeeded run: review._refused_run) while its succeeded primary
#              answer leaves nothing to decide. 057a7d39 recognises a refusal of the primary answer only (its readiness
#              and its page read the provider.status check), so whatever state it is handed it says that no code was
#              proposed beside a response it never read: no_codes lists 'No CPT codes proposed', provider_failed
#              'Provider request failed', and its blocker is 'No CPT code was proposed' either way. No state can be put
#              back for it, and a stopped worker does not keep a web from showing it (SHOWN_HAZARDS; the skeptic of
#              refutation p2's install2:1 repair; must-fix class 3).
#   second_review_unread - the current assessment did not read a bounded second review made for the answer it reads
#              (review._unread_second_reviews: every one, not only the newest - refutation P2FR, ROLLBACK 0) and that
#              review may hold codes nobody read - sent with an outcome still
#              unknown or reconciled as unknown, or answered and not read yet - while that succeeded answer leaves
#              nothing to decide. This revision states that review's outcome ('Second review outcome unknown'); 057a7d39
#              reads no second review, so whatever state it is handed it says that no code was proposed: 'No CPT codes
#              proposed', its blocker 'No CPT code was proposed', its page 'No CPT codes were proposed for this
#              document.' (SHOWN_HAZARDS; refutation P2RA, ROLLBACK lens 0; must-fix class 3). One that failed or was
#              not sent proposed nothing, so that statement is true of its rows: it is put back like any other state.
#   participant - the current assessment's decision set (selected or excluded) holds a code only a harness participant
#              proposed (HARNESS.md 5: support origin 'participant'). No revision before the harness (80df1831d168 and
#              older) reads a participant: its page and both reports show the code as the provider's own proposal,
#              naming no other proposer (I4), and its re-assessment reads Corti's answer alone, so the code leaves the
#              decision set without a reviewer's decision - the 'second_review' case again. No state can be put back for
#              it (SHOWN_HAZARDS). Its stages - kinds astra and fable, and harness@2's peer reviews astra_peer and
#              fable_peer (HARNESS.md 11.1) - are closed like a second review's whenever the next worker has no stage
#              for them: no worker before the harness has any of the four, and none before harness@2 a peer review
#              (CLOSE_STAGES, given the next worker's own kinds).
#   member_answer - the current assessment has a member's answer that stands (MemberAnswer, not revoked: "Not
#              documented" or "Cannot confirm", core repair 2026-11-03). No revision before it reads one: its page asks
#              that question again and shows the code held, where this revision shows it Excluded with the answer and
#              who gave it. The answer row stays; no state can be put back for it (SHOWN_HAZARDS). Completion repair
#              (2026-11-06, U11): an answer now re-makes the assessment (jobs.recompute_after_answers), whose answered
#              code is stored Excluded with the answer as its reason (support 'answered') while it still holds the codes
#              it held (the base code of a therapeutic code answered away: decision (e)). A revision before the
#              completion repair reads that row as an ordinary exclusion, which holds nothing, so its page may show such
#              a base code READY. Such an assessment is named by this same reason whether or not the answer that made
#              it still stands (refutation cycle 1, answers F6: withdrawn, and the recompute it queued stopped or
#              failed, the stored marker stays): a current or shown assessment with a proposal carrying support
#              'answered' is named too. No state can be put back for it either. Only a worker since the completion
#              repair makes such an assessment, so it is this revision's write: written_since counts it as written
#              since the switch when no standing answer explains it, and when it was made since then, whenever the
#              answer that made it was given (refutation cycle 2, answers W3: timed by standing answers alone, a marker
#              with none - or one re-made in the window from an answer given before it - read as written before the
#              switch, so the undo did not hold the old worker and its receipt said the record predated the new web).
#   modifier - a current decision of the current assessment carries the reviewer's chosen modifier (Decision.modifiers,
#              core repair 2026-11-03). No revision before it reads one: its page and both reports show that approval
#              without the modifier. The decision row stays; no state can be put back for it (SHOWN_HAZARDS).
UNDO_HAZARDS = '''
def standing_answers(revision_id):  # the answers that stand on a revision, as the review overlay reads them
    from studio import models
    try:
        from studio import answers as member_answers
    except ImportError:
        member_answers = None
    if member_answers is not None and hasattr(member_answers, 'standing_answers'):
        return member_answers.standing_answers(revision_id)
    return list(models.MemberAnswer.objects.filter(revision_id=revision_id, revocation__isnull=True))


def answer_revisions(encounter, assessment):  # whose standing answers 'member_answer' reads: the shown and the current
    return sorted(str(pk) for pk in {encounter.current_revision_id, getattr(assessment, 'revision_id', None)} if pk)


def answer_markers(encounter, assessment):  # the shown and current assessments the engine re-made with an answer
    # refutation cycle 3 (answers C3-2): a proposal the answer excluded ('answered' support), or a documented service's
    # question the answer closed (Clarification.answer: engine close_service), each marks this revision's write
    shown = {item.pk: item for item in (assessment, getattr(encounter, 'current_assessment', None)) if item is not None}
    return [shown[pk] for pk in sorted(shown, key=str)
            if any(isinstance(proposal.support, dict) and proposal.support.get('answered')
                   for proposal in shown[pk].proposals.all())
            or shown[pk].clarifications.filter(answer__isnull=False).exists()]


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
        if encounter.current_assessment_id is not None and models.Proposal.objects.filter(
                assessment_id=encounter.current_assessment_id, support__origin='second_review',
                bucket__in=(models.Proposal.SELECTED, models.Proposal.EXCLUDED)).exists():
            found.setdefault(str(encounter.pk), set()).add('second_review')
        # a code only a harness participant proposed, in that decision set: no older revision reads a participant, so
        # it shows the code as the provider's and its re-assessment drops it without a reviewer's decision
        if encounter.current_assessment_id is not None and models.Proposal.objects.filter(
                assessment_id=encounter.current_assessment_id, support__origin='participant',
                bucket__in=(models.Proposal.SELECTED, models.Proposal.EXCLUDED)).exists():
            found.setdefault(str(encounter.pk), set()).add('participant')
        # the assessment its page shows (the current one, whatever its revision) read a second review refused whole
        # beside a succeeded primary answer with nothing to decide - where 057a7d39 says that no code was proposed
        assessment = encounter.current_assessment if encounter.current_assessment_id is not None else None
        if (assessment is not None and assessment.second_run_id is not None
                and assessment.provider_run_id is not None and assessment.provider_run.state == Run.SUCCEEDED):
            refused = review._refused_run(assessment)
            decisions = review.current_decisions(assessment)
            if (refused is not None and refused.pk == assessment.second_run_id
                    and not any(review._reviewable(proposal, decisions.get(proposal.pk))
                                for proposal in assessment.proposals.all())):
                found.setdefault(str(encounter.pk), set()).add('second_review_refused')
        # or did not read a second review made for that answer which may hold codes nobody read (unknown, or answered
        # and not read yet), beside that answer with nothing to decide - where 057a7d39, which reads no second review,
        # says that no code was proposed (refutation P2RA, ROLLBACK lens 0). One that failed or was never sent proposed
        # nothing, and 057a7d39's statement is true of it - but every such review is read, not only the newest: a
        # reconciled unknown one releases another ask, and a retry that then failed or was not sent hid it (refutation
        # P2FR, ROLLBACK 0).
        if (assessment is not None and assessment.provider_run_id is not None
                and assessment.provider_run.state == Run.SUCCEEDED
                and Run.objects.filter(encounter_id=encounter.pk, purpose=Run.SECOND_REVIEW).exists()):
            if any(unread.state not in (Run.FAILED, Run.NOT_SENT, Run.CANCELLED)
                   for unread in review._unread_second_reviews(assessment)):
                decisions = review.current_decisions(assessment)
                if not any(review._reviewable(proposal, decisions.get(proposal.pk))
                           for proposal in assessment.proposals.all()):
                    found.setdefault(str(encounter.pk), set()).add('second_review_unread')
        # core repair 2026-11-03: a member's answer that stands, or a chosen modifier on a current decision - no older
        # revision reads either, so its page asks the answered question again, or shows the approval without the
        # modifier (read only where this image has them). A standing answer belongs to its REVISION, not to the
        # assessment it was given on, and the overlay applies it to every assessment of that revision (refutation r2,
        # L3-4: after a context change re-assessed the revision, an assessment_id filter missed it): read as the overlay
        # reads them (answers.standing_answers), for the shown assessment's revision and the current one.
        if hasattr(models, 'MemberAnswer'):
            if any(standing_answers(revision_id) for revision_id in answer_revisions(encounter, assessment)):
                found.setdefault(str(encounter.pk), set()).add('member_answer')
            # refutation cycle 1 (answers F6): an assessment the engine re-made with an answer carries its marker
            # (support 'answered') even once that answer is withdrawn and its recompute stopped or failed
            elif answer_markers(encounter, assessment):
                found.setdefault(str(encounter.pk), set()).add('member_answer')
        if assessment is not None and any(f.name == 'modifiers' for f in models.Decision._meta.get_fields()) and any(
                decision.modifiers for decision in review.current_decisions(assessment).values()):
            found.setdefault(str(encounter.pk), set()).add('modifier')
    return {pk: sorted(reasons) for pk, reasons in sorted(found.items())}


def written_since(since, pks):
    """{encounter id: reasons}: of the encounters ``pks`` names, each 'member_answer' or 'modifier' whose record - read
    as undo_hazards reads it - was written at or after ``since``: a standing answer given since then, a current decision
    carrying a chosen modifier recorded since then (refutation r3, D-2: an undo holds the old worker only for these, the
    records its own window wrote; the older ones were there before the install). An assessment the engine re-made with
    a member's answer (answer_markers) is this revision's write - only a worker since the completion repair makes one -
    and is written since when no standing answer explains it, or when it was made since then (refutation cycle 2,
    answers W3)."""
    from studio import models, review
    found = {}
    for encounter in models.Encounter.objects.filter(pk__in=sorted(pks)).order_by('pk'):
        assessment = encounter.current_assessment if encounter.current_assessment_id is not None else None
        reasons = []
        if hasattr(models, 'MemberAnswer'):
            standing = [answer for revision_id in answer_revisions(encounter, assessment)
                        for answer in standing_answers(revision_id)]
            marked = answer_markers(encounter, assessment)
            if (any(answer.answered_at >= since for answer in standing) or (marked and not standing)
                    or any(item.created_at >= since for item in marked)):
                reasons.append('member_answer')
        if assessment is not None and any(f.name == 'modifiers' for f in models.Decision._meta.get_fields()) and any(
                decision.modifiers and decision.created_at >= since
                for decision in review.current_decisions(assessment).values()):
            reasons.append('modifier')
        if reasons:
            found[str(encounter.pk)] = reasons
    return found
'''
UNDO_HAZARDS_READ = UNDO_HAZARDS + "print(ANSWER + json.dumps({'hazards': undo_hazards()}))\n"
# Close what a pair being undone left open since it started (refutation r1, migrate-3/-4): every stage it queued, ran
# or left resumable (cancelled) becomes FAILED with P['note'] - failed, not cancelled, so no revision's web offers a
# Resume for it - and every provider run it left unsettled is settled as the stale-stage sweep settles one (sending:
# unknown, reserved: not sent). A run left sending is also recorded sent when its record shows it may have reached the
# vendor, by the sweep's own rule (jobs.may_have_reached_vendor: an exchange of it recorded in any state but not_sent,
# never a replay's; refutation round 3, sends-3 - the close had left sent false beside an answered exchange); an image
# with no such rule, a revision before harness@2's exchanges, records none. So, whichever pair created it, does every
# stage of a kind the next worker does not run (P['kinds'] are those it runs) that is queued, running, or cancelled as
# its encounter's latest stage (what a Resume runs again): that worker ends on it (refutation p1, security-0: a second
# review stopped under an earlier pair of a revision that runs it outlived the window). Nothing finished is touched and
# no row is removed. The answer names, after the close, what the next pair would still act on wrongly (UNDO_HAZARDS).
CLOSE_STAGES = UNDO_HAZARDS + f'COMMON_STAGE_KINDS = {list(COMMON_STAGE_KINDS)!r}\n' + '''
import datetime
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from studio import jobs, models, review
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
    reached = getattr(jobs, 'may_have_reached_vendor', None)  # the stale sweep's rule for sent (sends-3)
    if reached is not None:
        reached(runs.filter(state=Run.SENDING)).update(sent=True)
    unknown = runs.filter(state=Run.SENDING).update(
        state=Run.UNKNOWN, finished_at=now, error='The worker stopped while the request was in flight.')
    not_sent = runs.filter(state=Run.RESERVED).update(
        state=Run.NOT_SENT, finished_at=now, error='The worker stopped before sending.')
    closed = stages.update(state=Job.FAILED, error=P['note'], finished_at=now)
for pk in encounters:
    review.refresh_state(models.Encounter.objects.get(pk=pk))
# Refutation p2, install2:1: the encounters whose stored state this revision labels from more than the state (worded from
# the run it reads: a response refused whole is provider_failed, 'Provider response not used'). An older revision labels
# a state by its name alone ('Provider request failed', for a request that succeeded): put_back_states gives each the
# state the older revision derives for its rows before the rows are handed over. Never one on the review queue (the
# states serializers.session_json counts, 057a7d39's alike): a put-back never takes an encounter off it. That state is
# truthful only for the PRIMARY answer's refusal, which 057a7d39 reads (its blocker 'The provider response was not
# used'); a second review's response refused whole is 'second_review_refused' in the hazards above, a second review the
# shown assessment did not read 'second_review_unread', and an undo hands no older pair the rows while one is named
# (SHOWN_HAZARDS).
REVIEW_QUEUE = ('needs_clarification', 'ready_for_review', 'provider_unknown')
relabel = []
for encounter in models.Encounter.objects.exclude(state__in=REVIEW_QUEUE).order_by('created_at', 'pk').iterator():
    if review.encounter_state_label(encounter) != review.state_label(encounter.state):
        relabel.append(str(encounter.pk))
hazards = undo_hazards()
answer = {'closed': closed, 'kinds': kinds, 'encounters': len(encounters), 'runs_unknown': unknown,
          'runs_not_sent': not_sent, 'hazards': hazards, 'relabel': relabel}
# Refutation r3, D-2: when it names a member's answer or a chosen modifier, the answer says which were written since
# P['since'] ({} for none); the installer reads a 'member_answer' or 'modifier' it names without this as written then.
written = [pk for pk, reasons in hazards.items() if 'member_answer' in reasons or 'modifier' in reasons]
if written:
    answer['written_since'] = written_since(since, written)
print(ANSWER + json.dumps(answer))
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
# Every encounter's stored list state recomputed with the derivation of the image it runs in (refutation p1, migrate-2:
# no action recomputes it until one touches the encounter, and the revision replaced may have derived it otherwise - an
# unreconciled unknown outcome it listed as reviewed is on this revision's review queue) - or only P['encounters'] when
# given: an undo runs it so in the image of the pair it hands the rows to (put_back_states, refutation p2, install2:1),
# so it uses only what every revision has (057a7d39's review.refresh_state included). review.refresh_state writes only a
# state that changed; nothing is sent. The answer names each encounter whose state changed (as read, as derived).
RECOMPUTE_STATES = '''
from studio import models, review
changed, rows = {}, models.Encounter.objects.order_by('created_at', 'pk')
if P.get('encounters') is not None:
    rows = rows.filter(pk__in=P['encounters'])
for encounter in rows:
    read = encounter.state
    derived = review.refresh_state(encounter)
    if derived != read:
        changed[str(encounter.pk)] = [read, derived]
print(ANSWER + json.dumps({'encounters': rows.count(), 'changed': changed}))
'''
# ADJUDICATION P-1 (design/FINAL.md 12.3 as amended): the new-path encounters an earlier image is handed - the
# assessments made from event inventories (every one the events engine made, an engine_version of the
# cpt-studio-events@ family, interpretation.is_new_assessment's rule, or that names an inventory) and their encounters;
# and the encounters that hold a context derived from an inventory (a version of the gemini-context@ family,
# interpretation.is_new_context's rule, or one that names an inventory) and no such assessment, 'context_only' - one
# stopped between analyze and assess, whose gemini context is current (the review of S14, finding 1: FINAL 12.1's row
# "declared by the hazard", which this note replaced). An earlier image reads the assessments fail-closed: its overlay
# cannot read their records, so it keeps every stored hold and releases none (FINAL 12.1-12.2). It reads such a context
# as current and keeps its holds (its held rows carry the legacy notes, FINAL 4.3), and an explicit act reads the
# document again with its own reader (12.1). An inventory alone is not named: no earlier image reads one (12.1), nor a
# routing stand-in (its operator console only shows it). None of it is EVER a refusing reason (not an UNDO_HAZARDS or
# SHOWN_HAZARDS one): switch-back and rollback-app write it as a declared note in their receipts and go on. Read in
# this revision's own image; an image with no event inventories answers None. Nothing is written or sent.
INTERPRETATION_MADE = '''
from django.db.models import Q
from studio import models
try:
    from studio import interpretation
except ImportError:
    interpretation = None
made = None
if interpretation is not None and all(any(f.name == 'event_inventory' for f in model._meta.get_fields())
                                      for model in (models.Assessment, models.EncounterContext)):
    family = interpretation.ENGINE_VERSION.partition('@')[0] + '@'
    encounters = list(models.Assessment.objects.filter(Q(event_inventory__isnull=False)
                                                       | Q(engine_version__startswith=family))
                      .values_list('encounter_id', flat=True))
    derived = interpretation.CONTEXT_VERSION.partition('@')[0] + '@'
    holding = (models.EncounterContext.objects.filter(Q(event_inventory__isnull=False)
                                                      | Q(version__startswith=derived))
               .order_by().values_list('encounter_id', flat=True).distinct())
    assessed = {str(pk) for pk in encounters}
    context_only = {str(pk) for pk in holding} - assessed
    made = {'assessments': len(encounters), 'encounters': sorted(assessed | context_only),
            'context_only': sorted(context_only)}
print(ANSWER + json.dumps({'interpretation': made}))
'''
# The list state the installed revision 057a7d39 derives for each encounter of P['encounters'], written where it differs
# (refutation p2, install2:1), for an undo with no older image to ask: rollback-app with no pair parked, after which the
# older revision is installed by its own installer - 057a7d39's never recomputes a stored state, so it shows what it is
# handed. installed_state is 057a7d398's review._derive_state with its _failed_stage_state, as they are there; the helpers
# it calls are this revision's and byte-identical to 057a7d39's (_active_jobs, live_assessment), so a change to any of
# them ports 057a7d39's here first. Two did change in the core repair (2026-11-03) and are ported below as they are at
# 057a7d39: _unreconciled_unknown (which now also reads a run left 'sending' by a stage that no longer runs, decision
# (k)) and _review_state (which now reads the review overlay's statuses). _review_state's readiness is this revision's:
# its _assessment_blockers already differed from 057a7d39's before the core repair (main c9f20a148 and the installed
# 41e03656df61 carry the same one), and now also reads the overlay - so for an encounter with a reinstatement, a
# member's answer or an approval the overlay no longer supports, whether it is 'reviewed' is this revision's reading.
# Only an undo to 057a7d39 itself reads this script: a revision since then recomputes the states its own app phase
# hands it (RECOMPUTE_STATES). Run in this revision's image; nothing is sent.
INSTALLED_STATES = '''
from django.db import transaction
from django.utils import timezone
from studio import models, review


def unreconciled_unknown(encounter):  # 057a7d39's review._unreconciled_unknown, as it is there
    return encounter.provider_runs.filter(state=models.ProviderRun.UNKNOWN, reconciled_at__isnull=True).exists()


def review_state(encounter, assessment):  # 057a7d39's review._review_state, as it is there
    if review.readiness(encounter)['reviewed']:
        return 'reviewed'
    current = review.current_decisions(assessment)
    reviewable = [item for item in assessment.proposals.all() if review._reviewable(item, current.get(item.pk))]
    encounter_question = assessment.clarifications.filter(
        state=models.Clarification.OPEN, scope='encounter', proposal__isnull=True).exists()
    if not reviewable:
        return 'needs_clarification' if encounter_question else 'no_codes'
    if encounter_question or any(item.status == models.Proposal.NEEDS_CLARIFICATION and item.pk not in current
                                 for item in reviewable):
        return 'needs_clarification'
    return 'ready_for_review'


def installed_state(encounter):
    Job, Run, Revision = models.Job, models.ProviderRun, models.SourceRevision
    revision = encounter.current_revision
    if revision is None or review._active_jobs(encounter):
        return 'processing'
    if revision.extraction_status == Revision.FAILED:
        return 'extraction_failed'
    latest = encounter.jobs.filter(revision=revision).order_by('-created_at', '-pk').first()
    if latest is not None and latest.state == Job.CANCELLED:
        return 'stopped'
    if revision.extraction_status == Revision.PENDING:
        return 'processing' if latest is None else 'extraction_failed'
    if latest is not None and latest.state in (Job.FAILED, Job.UNKNOWN):
        if latest.kind == Job.EXTRACT:
            return 'extraction_failed'
        if latest.kind != Job.PREDICT:
            return 'processing_failed'
        if latest.state == Job.UNKNOWN:
            return 'provider_unknown'
        run = (encounter.provider_runs.filter(revision=revision, created_at__gte=latest.created_at)
               .order_by('-created_at', '-pk').first())
        if run is None:
            return 'provider_not_run'
        if run.state in review.UNSETTLED_RUN_STATES:
            return 'provider_unknown'
        return 'processing_failed' if run.state == Run.SUCCEEDED else 'provider_failed'
    assessment = review.live_assessment(encounter)
    if assessment is None or assessment.context_id != encounter.current_context_id:
        return 'provider_unknown' if unreconciled_unknown(encounter) else 'processing'
    run = assessment.provider_run
    if run is None:
        return 'provider_not_run'
    if run.state in review.UNSETTLED_RUN_STATES:
        return 'provider_unknown'
    if run.state != Run.SUCCEEDED:
        return 'provider_failed'
    return review_state(encounter, assessment)


changed = {}
for pk in P['encounters']:
    with transaction.atomic():
        encounter = review._lock(models.Encounter.objects.get(pk=pk))
        read, derived = encounter.state, installed_state(encounter)
        if derived != read:
            models.Encounter.objects.filter(pk=encounter.pk).update(state=derived, updated_at=timezone.now())
            changed[str(encounter.pk)] = [read, derived]
print(ANSWER + json.dumps({'encounters': len(P['encounters']), 'changed': changed}))
'''
# The license-note phase's correction (HARNESS.md 11.6), run in this revision's own image. It refuses, changing nothing,
# unless that image's importer writes exactly P['new']: the rows would otherwise hold another note than its next import
# writes. Then, in one transaction holding the table against writers (SHARE ROW EXCLUSIVE: readers are not blocked),
# every ReferenceSource row whose license_note is exactly P['old'] gets exactly P['new'], and nothing else changes: the
# rows are read before and after, and any other difference raises, so the transaction is rolled back. Assessments and
# reports are never touched (they record what was shown); the answer counts the assessments that recorded the old note.
LICENSE_NOTE_FIX = '''
from django.db import connection, transaction
from studio import models
from studio.reference import importers


def counts(rows):
    found = {'old': 0, 'new': 0, 'other': 0}
    for row in rows:
        note = row['license_note']
        found['old' if note == P['old'] else 'new' if note == P['new'] else 'other'] += 1
    return found


Source = models.ReferenceSource
if getattr(importers, 'LICENSE_NOTE', None) != P['new']:
    answer = {'refused': 'this image writes another note on a source it imports (studio.reference.importers.'
                         'LICENSE_NOTE is not the corrected text), so its next import would undo the correction'}
else:
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '30s'")
            cursor.execute('LOCK TABLE ' + connection.ops.quote_name(Source._meta.db_table)
                           + ' IN SHARE ROW EXCLUSIVE MODE')
        before = list(Source.objects.order_by('pk').values())
        old = [row['id'] for row in before if row['license_note'] == P['old']]
        updated = Source.objects.filter(pk__in=old, license_note=P['old']).update(license_note=P['new'])
        after = list(Source.objects.order_by('pk').values())
        if updated != len(old) or after != [dict(row, license_note=P['new']) if row['id'] in old else row
                                            for row in before]:
            raise RuntimeError('correcting the licence note would have changed more than the old notes; nothing '
                               'was changed')
    answer = {'rows': len(before), 'before': counts(before), 'after': counts(after), 'updated': updated,
              'updated_keys': sorted(row['key'] for row in before if row['id'] in old),
              'other_keys': sorted(row['key'] for row in after if row['license_note'] not in (P['old'], P['new'])),
              'assessments_with_old_note': models.Assessment.objects.filter(
                  reference_sources__contains=[{'license_note': P['old']}]).count()}
print(ANSWER + json.dumps(answer))
'''


def app_script(image_id, env_bytes, body, params, *, what, timeout=180, mounts=(), user=None) -> dict:
    """Run ``body`` in a one-shot container of ``image_id`` (provider disabled) and return its ANSWER line's JSON.
    ``mounts`` and ``user`` are the one-shot's (the operators phase mounts RAM-only password files it owns)."""
    payload = base64.b64encode(json.dumps(params).encode()).decode()
    source = APP_SCRIPT_PRELUDE.format(payload=payload, answer=APP_SCRIPT_ANSWER) + body
    extra = {'mounts': list(mounts)} if mounts else {}
    if user:
        extra['user'] = user
    result = oneshot(image_id, ['manage', 'shell', '-c', source], env_bytes, timeout=timeout, **extra)
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


def service_problems(container, role, image_id, port=None) -> list:
    """What makes ``container`` not the hardened ``role`` of ``image_id``; a web must publish exactly 127.0.0.1:
    ``port`` (any one of WEB_PORTS when ``port`` is None)."""
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
    ports = (port,) if port is not None else WEB_PORTS
    expected = ([{'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(each)}]} for each in ports] if role == 'web'
                else [{}])
    if bindings not in expected:
        problems.append('unexpected published ports')
    # Only the worker holds a credentials file, read-only (HARNESS.md 8): Corti's, a live participant's and the live
    # interpreter's (design/FINAL.md 13, D14). A web holds none, whatever it is configured for.
    binds = [(mount.get('Source'), mount.get('Destination'), mount.get('RW'))
             for mount in container.get('Mounts') or [] if mount.get('Type') == 'bind']
    allowed = ({(CORTI_TARGET, CREDENTIALS_IN_CONTAINER), (INTERPRETER['target'], INTERPRETER['mounted'])}
               | {(spec['target'], spec['mounted']) for spec in PARTICIPANTS.values()})
    if role == 'web' and binds:
        problems.append('the web holds a bind-mounted file (only the worker holds credentials)')
    if role == 'worker' and any((source, destination) not in allowed or writable is not False
                                for source, destination, writable in binds):
        problems.append('a bind mount other than a read-only credentials file')
    return problems


def wait_service(role, revision, image_id, *, name=None, port=WEB_PORT) -> dict:
    """Readiness of the ``role`` container ``name`` (its canonical name unless given) of ``image_id``: a web answers
    health_ok for ``revision`` on 127.0.0.1:``port``; a worker stays up. Either must pass service_problems."""
    name = name or SERVICES[role]
    if role == 'web':
        def check():
            container = inspect('container', name)
            if container is None or not container['State'].get('Running'):
                return False, {'running': False}
            result = probe('http', DOMAIN, '/health/', port=port, connect_ip='127.0.0.1',
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
    problems = (service_problems(container, role, image_id, port=port if role == 'web' else None) if container
                else ['container vanished'])
    if not passed or problems or container.get('RestartCount'):
        raise InstallError(f'{name} did not become ready: {problems or "readiness not observed"}.',
                           details={'observations': observations[-5:]})
    return {'id': container['Id'], 'observations': len(observations)}


def park(role):
    name, parked = SERVICES[role], SERVICES[role] + '-previous'
    if inspect('container', parked) is not None:
        raise InstallError(f'{parked} is left from an interrupted replacement; resolve it before reinstalling.')
    if role == 'web' and inspect('container', INCOMING_WEB) is not None:
        raise InstallError(f'{INCOMING_WEB} is left from an interrupted blue/green install; resolve it before '
                           'reinstalling (ops/INSTALL.md, Recovery notes).')
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
    # 'running': whether it ran when it was parked (None when Docker did not say), so an undo puts it back as it was
    # (restore_parked_worker; refutation r3, D-2: a worker an earlier undo held stays held)
    return {'id': container['Id'], 'image': container['Image'], 'revision': labels_of(container).get(REVISION_LABEL),
            'running': (container.get('State') or {}).get('Running')}


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
    """{encounter id: reasons} - what ``revision`` recorded that an older revision would act on, or show, wrongly under
    its own rules (UNDO_HAZARDS, read with ``revision``'s own image)."""
    return app_script(image_id, env_bytes, UNDO_HAZARDS_READ, {},
                      what=f'Reading what an older revision would act on wrongly (revision {revision[:12]})')['hazards']


def interpretation_note(image_id, env_bytes, revision) -> dict:
    """ADJUDICATION P-1: the declared, NON-REFUSING note a switch-back or rollback-app receipt carries - the assessments
    ``revision`` made from event inventories, and the new-path encounters (INTERPRETATION_MADE, read with ``image_id``,
    this revision's own image): those with such an assessment, which the earlier image reads fail-closed, and those that
    hold only a context derived from an inventory ('context_only'; the review of S14, finding 1), which it reads as
    current, keeping its holds. {'assessments', 'encounters', 'context_only', 'note'}. It never stops an undo: a read
    that fails, or an answer that says nothing it read, is recorded as not counted (an interrupt is never
    swallowed)."""
    def uncounted(why):
        return {'assessments': None, 'encounters': None, 'context_only': None,
                'note': f'the assessments made from event inventories and the contexts derived from them were not '
                        f'counted ({why}); the earlier image reads any such assessment fail-closed and any such '
                        'context as current, keeping its holds'}
    try:
        answer = app_script(image_id, env_bytes, INTERPRETATION_MADE, {},
                            what=f'Counting the assessments and contexts revision {revision[:12]} made from event '
                                 'inventories')
    except Exception as error:  # noqa: BLE001 — a declared note never stops an undo; it says it was not read
        return uncounted(str(error) or type(error).__name__)
    made = answer.get('interpretation', _UNREAD) if isinstance(answer, dict) else _UNREAD
    if made is None:
        return {'assessments': 0, 'encounters': [], 'context_only': [],
                'note': 'this image keeps no event inventory, so no assessment or context was made from one'}
    named = made.get('encounters') if isinstance(made, dict) else None
    context_only = made.get('context_only') if isinstance(made, dict) else None
    # what it read, said consistently: every id once, the context-only encounters among those named, and an assessment
    # for each other named encounter - at least one, and no more encounters than assessments
    if not (isinstance(made, dict) and type(made.get('assessments')) is int and made['assessments'] >= 0
            and isinstance(named, list) and all(isinstance(pk, str) for pk in named) and len(set(named)) == len(named)
            and isinstance(context_only, list) and all(isinstance(pk, str) for pk in context_only)
            and len(set(context_only)) == len(context_only) and set(context_only) <= set(named)
            and (len(named) - len(context_only) == 0) == (made['assessments'] == 0)
            and len(named) - len(context_only) <= made['assessments']):
        return uncounted('the count did not say what it read')
    count, held = made['assessments'], len(context_only)
    note = (f'{count} {"assessment was" if count == 1 else "assessments were"} made from event inventories; the '
            'earlier image reads them fail-closed')
    if held:
        note += (f'; {held} {"encounter holds" if held == 1 else "encounters hold"} a context derived from an event '
                 'inventory and no assessment made from one: the earlier image reads that context as current, keeping '
                 'its holds, and an explicit act reads the document again with the earlier reader')
    return {'assessments': count, 'encounters': list(named), 'context_only': list(context_only), 'note': note}


def hazard_summary(hazards) -> str:
    counts = {}
    for reasons in hazards.values():
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
    return f'{len(hazards)} encounter(s): ' + ', '.join(f'{reason} {count}' for reason, count in sorted(counts.items()))


# Refutation p2, the skeptic of the install2:1 repair: the UNDO_HAZARDS reasons about what an older revision's web SAYS,
# not what its worker does. No stored state can be put back for them - it says the same thing whatever state it is
# handed - and a worker left stopped does not keep its web from saying it. Refutation P2RA, ROLLBACK lens 0: a second
# review the shown assessment did not read is one too (it says that no code was proposed of a response nobody read).
# The harness: a code only a participant proposed is one too (the older web shows it as the provider's proposal).
# The core repair (2026-11-03): a member's answer that stands, and a chosen modifier, are two more (the older web reads
# neither: it asks the answered question again, and shows the approval without its modifier).
SHOWN_HAZARDS = ('second_review_refused', 'second_review_unread', 'participant', 'member_answer', 'modifier')
# The Gemini migration (ADJUDICATION P-1, which governs design/FINAL.md 13): an assessment made from an event inventory
# is NOT a hazard of either kind - not here and not in UNDO_HAZARDS. An earlier image reads it fail-closed (it keeps
# every stored hold and releases none), so naming it would only make switch-back and rollback-app refuse. They write it
# as a declared note in their receipts instead (INTERPRETATION_MADE, interpretation_note) and go on.


def hazards_by_kind(hazards):
    """(shown, acting): the close's ``hazards`` split into the encounters named for a SHOWN_HAZARDS reason and those
    named for another (what an older worker would act on); (None, None) when the answer names nothing it read, which is
    not read as "none"."""
    if not isinstance(hazards, dict) or not all(isinstance(reasons, list) for reasons in hazards.values()):
        return None, None
    shown = {pk: [r for r in reasons if r in SHOWN_HAZARDS] for pk, reasons in hazards.items()}
    acting = {pk: [r for r in reasons if r not in SHOWN_HAZARDS] for pk, reasons in hazards.items()}
    return {pk: r for pk, r in shown.items() if r}, {pk: r for pk, r in acting.items() if r}


def same_revision(previous, revision) -> bool:
    """Whether the parked pair ``previous`` (park's answer) is a pair of ``revision`` itself, by its revision label."""
    label = (previous or {}).get('revision')
    return isinstance(label, str) and bool(SHA_RE.fullmatch(label)) and label == revision


def put_back_states(closed, older_image, image_id, env_bytes) -> dict:
    """Refutation p2, install2:1: before an undo hands the rows to an older revision, each encounter the close names in
    'relabel' - a stored state this revision labels from more than the state, which the older revision labels by its
    name alone (a response refused whole: provider_failed, which it shows as 'Provider request failed' although the
    request succeeded) - is given the state the older revision derives for it: with ``older_image``'s own derivation
    (RECOMPUTE_STATES for those encounters, run in that image) when there is an image to ask, else as the installed
    revision 057a7d39 derives it (INSTALLED_STATES, in ``image_id``). Every other stored state is one both revisions
    label alike, and stays: the older derivation of a hold or of a second review closed by the undo is a request that
    failed or a failed stage, off its review queue. A second review closed by the undo that had sent nothing (stopped
    before sending, or not sent) leaves the assessment's own state (review._failed_stage_state), never provider_failed:
    labelled from its run where nothing is left to decide ('Second review not sent'), it is put back here to the older
    derivation (057a7d39: processing_failed, 'Processing failed'), and on the review queue it stays (refutation P2FR,
    ROLLBACK 1: left provider_failed, 057a7d39 listed 'Provider request failed' beside a request that succeeded).
    An answer that names nothing it read is not read as "none".
    The state put back is truthful for the PRIMARY answer's refusal only: 057a7d39 reads that one (no_codes, with its
    blocker 'The provider response was not used'). Beside a second review's response refused whole, or a second review
    the shown assessment did not read whose outcome is unknown or that was answered, it says that no code was proposed
    whatever state it is handed, so the close names that encounter as a hazard (second_review_refused,
    second_review_unread) and no undo reaches this step for it, unless the pair it hands the rows to is this same
    revision (the failure path of a same-revision re-run), whose own derivation keeps it. A second review that failed or
    was not sent proposed nothing: put back to 057a7d39's no_codes, 'No CPT codes proposed' is true of its rows."""
    relabel = closed.get('relabel') if isinstance(closed, dict) else None
    if not isinstance(relabel, list) or not all(isinstance(pk, str) for pk in relabel):
        raise InstallError('The close did not say which list states an older revision labels otherwise.')
    if not relabel:
        return {'encounters': 0, 'changed': {}}
    if isinstance(older_image, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', older_image):
        return app_script(older_image, env_bytes, RECOMPUTE_STATES, {'encounters': relabel},
                          what='Putting back the list states the older revision derives (its own image)')
    return app_script(image_id, env_bytes, INSTALLED_STATES, {'encounters': relabel},
                      what='Putting back the list states the installed revision 057a7d39 derives')


def replace_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants=None, *,
                     interpreter=None) -> dict:
    """Replace the web and worker (``participants``: each harness participant's mode, disabled when not given;
    ``interpreter``: the interpreter's, disabled when not given) the way
    replacement_plan reads the host - after migrate, as before, and right before anything is started or stopped (a
    refusal starts and stops nothing; preflight has refused the same states before the install began): a served site
    is switched blue/green (switch_services, which never stops its web; it needs this install's preflight receipt, the
    baseline the switch is verified against); a host where nothing is served through the vhost is swapped as it always
    was (swap_services). The receipt's 'replacement' says which, and why."""
    plan = replacement_plan(ctx)
    summary = {key: plan[key] for key in ('mode', 'why', 'vhost', 'vhost_sha256', 'live', 'idle', 'port') if key in plan}
    # named only when it is not the default, so a stand-in of either keeps the arguments it always had
    interpreting = {'interpreter': interpreter} if (interpreter or 'disabled') != 'disabled' else {}
    if plan['mode'] == 'blue-green':
        preflight = require_receipt(ctx, 'preflight')
        services = switch_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants,
                                   preflight=preflight, plan=plan, **interpreting)
    else:
        services = swap_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants,
                                 port=plan['port'], **interpreting)
    return {**services, 'replacement': summary}


def swap_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants=None, *,
                  port=WEB_PORT, interpreter=None) -> dict:
    """The swap of a host where nothing is served through the vhost (replacement_plan's 'fresh'). Park
    the old pair, start the new pair, its web on 127.0.0.1:``port`` (``participants``: each harness participant's
    mode, disabled when not given); on any failure stop what was started, close every stage it left open
    and every open stage of a kind the old worker does not run (close_undone_stages), put back the list states the old
    revision labels otherwise (put_back_states, with the old pair's own image), and only then restore exactly the old
    pair - its worker left stopped while the close names records it would act on wrongly. A pair whose stages cannot be
    closed, whose states cannot be put back, or whose web would show a state wrongly whatever it is handed (the close
    names it for a SHOWN_HAZARDS reason, and the old pair is not this same revision) is never restored over them: the
    new pair is left stopped and the old one parked, for rollback-app. On success the old pair is left parked: phase_app
    removes it (retire_parked) once the stored list states are recomputed. 'worker_started_at' is when the new worker
    was started (ADJUDICATION P-7: the verify one-shot's window begins there, as blue/green's begins at S4)."""
    parked, launched, started = {}, [], {}
    swapped_at = worker_started_at = None
    try:
        for role in ('worker', 'web'):  # the worker first, so no stage runs across the switch
            parked[role] = park(role)
        swapped_at = dt.datetime.now(dt.timezone.utc)  # every stage created from here on is the new pair's
        for role in ('web', 'worker'):
            launched.append(role)
            if role == 'worker':
                worker_started_at = utc_now_ms()
            docker('run', '-d', *service_args(role, image_id, ctx.revision, provider_mode, authorization_ref,
                                              participants, port=port, interpreter=interpreter),
                   input=env_bytes, quiet=True)
            # WEB_PORT is wait_service's own default, and is left to it (callers' stand-ins keep its three arguments)
            started[role] = wait_service(role, ctx.revision, image_id, **({'port': port} if port != WEB_PORT else {}))
    except BaseException as failure:
        for role in reversed(launched):
            name = SERVICES[role]
            container = inspect('container', name)
            if container is not None and owned(container, role):
                tail = docker('logs', '--tail', '40', name, check=False, timeout=30)
                ctx.log(f'{role}-failed', tail.stdout[-8192:] + tail.stderr[-8192:])
            stop_service_container(name, role)
        closed, put_back, hold_worker = None, None, False
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
            hazards = closed.get('hazards')
            shown, acting = hazards_by_kind(hazards)
            # Refutation p2, the skeptic of the install2:1 repair: a state the restored web would show wrongly whatever
            # it is handed (SHOWN_HAZARDS: a second review's response refused whole, or one the shown assessment did not
            # read - refutation P2RA, ROLLBACK lens 0 - beside which an older revision says that no code was proposed)
            # has no state to be put back to, so the previous pair is not restored over it - as when the states cannot
            # be put back. A pair of this same revision (a same-revision re-run) shows those states as this revision
            # does, and is restored as usual.
            if (shown is None or shown) and not same_revision(previous, ctx.revision):
                named = hazard_summary(shown) if shown is not None else 'the close did not say which encounters'
                raise InstallError(
                    f'{failure}; {named} hold states the previous revision would show wrongly whatever it is handed '
                    '(a bounded second review whose response was refused whole, or whose outcome is unknown or not '
                    'read yet: it reads neither and would say that no code was proposed; a code only a harness '
                    'participant proposed: it would show it as the provider\'s), so the new pair was left '
                    'stopped and the previous pair parked '
                    '(*-previous). To keep this revision, remove the parked pair by hand and run --phase app again '
                    'once its failure is fixed; to go back, start this pair again, clear them on its web '
                    '(ops/INSTALL.md, Reinstalling an older revision), run --phase rollback-app, then rename the '
                    'parked pair back.', details={'hazards': hazards, 'stages_closed': closed}) from failure
            # Refutation p2, install2:1: the restored pair shows a stored state by its own labels - a response this
            # revision refused whole would read 'Provider request failed' - so it is handed its own derivation of those.
            try:
                put_back = put_back_states(closed, previous['image'], image_id, env_bytes)
            except BaseException as error:
                raise InstallError(f'{failure}; the list states the previous revision labels otherwise could not then '
                                   f'be put back ({error}), so the new pair was left stopped and the previous pair '
                                   'parked (*-previous): run --phase rollback-app, then rename the parked pair '
                                   'back.') from error
            ctx.log('undo', json.dumps({**closed, 'states_put_back': put_back}).encode())
            # Refutation p1, migrate-0/-1: this path cannot refuse, so while the close names records the restored
            # revision would act on under its own rules (a send without a date, an identical re-send of a request that
            # failed), its worker - the only holder of the provider credentials - is left stopped: nothing can be sent.
            # An answer that names nothing it read is not read as "none". (A SHOWN_HAZARDS reason reaches here only for
            # a pair of this same revision, which shows it as this revision does: it holds nothing.)
            hold_worker = acting is None or bool(acting)
        for role in reversed(launched):
            remove_service_container(SERVICES[role], role)
        for role, previous in parked.items():
            if previous:
                docker('rename', SERVICES[role] + '-previous', SERVICES[role])
                if role != 'worker' or not hold_worker:
                    docker('start', SERVICES[role])
        if hold_worker:
            hazards = closed.get('hazards')
            named = hazard_summary(acting) if acting is not None else 'the close did not say which'
            raise InstallError(
                f'{failure}; the previous web was restored and its worker ({SERVICES["worker"]}) left stopped, so '
                f'nothing can be sent: {named} hold records it would act on under its own rules (ops/INSTALL.md, '
                'Reinstalling an older revision). Install this revision again once its failure is fixed: its worker '
                'reads them under its own rules.', details={'hazards': hazards, 'stages_closed': closed,
                                                            'states_put_back': put_back}) from failure
        raise
    return {'started': started, 'replaced': parked, 'worker_started_at': worker_started_at}


def retire_parked(parked):
    """Remove the parked old pair (replace_services' 'replaced') - once the new pair runs and the stored list states are
    recomputed (phase_app)."""
    for role, previous in (parked or {}).items():
        if previous:
            docker('rm', '--force', previous['id'], timeout=60)


# --- blue/green: the switch that never stops the serving web (ops/INSTALL.md, app) --------------------------------------
#
# Invariants (each asserted after every fake call by ops/test_install_bluegreen.py):
#   I-web    after every step the vhost's proxy_pass port - the file's and the one nginx routes to - is published by a
#            running web that answered health_ok for its revision; the old web is never stopped before the switch is
#            verified, nor while a verified switch could still be undone.
#   I-worker at most one worker runs; the old one is stopped before any new-revision web takes traffic, and the new one
#            starts only after the old one has exited (no stale-stage sweep races a live stage).
#   I-jobs   the old worker's current stage finishes (docker stop --time 600); queued stages wait for the new worker.
#   I-state  the stored list states are recomputed only once both old containers have stopped (phase_app).
#   I-undo   every failure leaves the site served by a healthy web; today's hazard semantics are kept, and switching
#            back replaces restarting a stopped web.

def replacement_plan(ctx) -> dict:
    """How replace_services replaces the pair, read right before anything is started or stopped. A state it cannot
    read as one of these is refused, and nothing is started or stopped.

    'blue-green': the running cpt-studio-web publishes one of WEB_PORTS and quillmd-cpt is this revision's HTTPS stage
        proxying to it - the site is served - so switch_services starts the incoming web on the other port and stops
        the serving one only after the switch and its drain.
    'fresh': nothing is served through the vhost - there is no quillmd-cpt, it is the HTTP stage (which proxies
        nothing), it is an HTTPS stage no running web answers now, or the running web publishes neither web port (no
        web this installer started: the vhost cannot reach it) - so swap_services swaps the pair on <port>: the port
        that HTTPS stage proxies to, else WEB_PORT. The containers are read first, and the vhost only when it can
        decide the mode or the port."""
    web = inspect('container', SERVICES['web'])
    if web is not None and not owned(web, 'web'):
        raise InstallError(f'{SERVICES["web"]} exists but is not a CPT Studio web container; nothing was started or '
                           'stopped.')
    running = bool(web is not None and (web.get('State') or {}).get('Running'))
    facts = {'vhost': None, 'vhost_sha256': None, 'web': None}
    if web is not None:
        facts['web'] = {'id': web['Id'], 'image': web.get('Image'), 'running': running, 'port': published_port(web),
                        'revision': labels_of(web).get(REVISION_LABEL)}
    if running and facts['web']['port'] is None:
        return {**facts, 'mode': 'fresh', 'port': WEB_PORT,
                'why': f'the running {SERVICES["web"]} publishes neither web port, so nothing reaches it through the '
                       'vhost'}
    state = vhost_state()
    facts['vhost_sha256'] = state['file_sha256']
    if not state['file_exists'] and not state['link_exists']:
        return {**facts, 'mode': 'fresh', 'port': WEB_PORT, 'vhost': 'absent',
                'why': 'there is no quillmd-cpt vhost, so nothing is served through it'}
    if not (state['file_exists'] and state['file_sha256'] and state['link_target'] == VHOST_LINK_TARGET):
        raise InstallError('quillmd-cpt is not the regular file and sites-enabled link this installer writes; nothing '
                           'was started or stopped. Resolve it by hand (ops/INSTALL.md, Recovery notes).')
    live_bytes = live_vhost_bytes()
    if live_bytes is None or sha256(live_bytes) != state['file_sha256']:
        raise InstallError('quillmd-cpt changed while it was being read; nothing was started or stopped.')
    known = vhost_renderings(ctx.revision).get(state['file_sha256'])
    recorded = recorded_vhosts(ctx).get(state['file_sha256']) if known is None else None
    if known is not None:
        kind, port = known['kind'], known['port']
    elif recorded is not None:
        kind = recorded[1]
        port = proxied_port(live_bytes.decode('utf-8', 'replace')) if kind == 'https' else None
        if kind == 'https' and port is None:
            raise InstallError('quillmd-cpt is a recorded HTTPS stage whose upstream is not 127.0.0.1:9150 or 9151; '
                               'nothing was started or stopped.')
    else:
        raise InstallError('quillmd-cpt holds content this installer did not write and no successful receipt here '
                           'records; nothing was started or stopped.')
    facts['vhost'] = kind
    if kind == 'http':
        return {**facts, 'mode': 'fresh', 'port': WEB_PORT, 'why': 'quillmd-cpt is the HTTP stage, which proxies nothing'}
    facts['proxied_port'] = port
    if not running:
        return {**facts, 'mode': 'fresh', 'port': port,
                'why': f'no running {SERVICES["web"]} answers the HTTPS stage on {port} now, so nothing is interrupted'}
    if facts['web']['port'] != port:
        raise InstallError(f'quillmd-cpt proxies to 127.0.0.1:{port} but the running {SERVICES["web"]} publishes '
                           f'{facts["web"]["port"]}; nothing was started or stopped. Resolve it by hand '
                           '(ops/INSTALL.md, Recovery notes).')
    if known is None:
        raise InstallError(f'quillmd-cpt is the HTTPS stage an earlier revision ({recorded[0][:12]}) wrote, which this '
                           'revision does not render for its port (deploy/nginx changed): the switch would change more '
                           'than its upstream, so nothing was started or stopped. Republish the vhost under this '
                           'revision first (ops/INSTALL.md, Reinstalling a new revision).')
    if not SHA_RE.fullmatch(str(facts['web']['revision'] or '')):
        raise InstallError(f'The running {SERVICES["web"]} carries no revision label, so its health cannot be told '
                           'apart from the incoming one\'s; nothing was started or stopped.')
    plan = {**facts, 'mode': 'blue-green', 'live': port, 'idle': other_port(port),
            'why': f'the site is served by {SERVICES["web"]} on {port}: the incoming web starts on {other_port(port)}'}
    problems = switch_problems(plan)
    if problems:
        raise InstallError('A blue/green switch cannot start, so nothing was started or stopped: '
                           + '; '.join(problems) + '.', details={'plan': plan})
    return plan


def switch_problems(plan) -> list:
    """What keeps a blue/green switch from starting: read when it is planned and again right before it starts."""
    problems = []
    if plan['idle'] in host_listening_ports():
        problems.append(f'port {plan["idle"]}, the incoming web\'s, is already in use')
    for name in (INCOMING_WEB, SERVICES['web'] + '-previous', SERVICES['worker'] + '-previous'):
        if inspect('container', name) is not None:
            problems.append(f'{name} is left from an interrupted install (ops/INSTALL.md, Recovery notes)')
    web = inspect('container', SERVICES['web'])
    if (web is None or web['Id'] != plan['web']['id'] or not (web.get('State') or {}).get('Running')
            or published_port(web) != plan['live']):
        problems.append(f'{SERVICES["web"]} is no longer the running web on {plan["live"]} that was read')
    worker = inspect('container', SERVICES['worker'])
    if worker is not None and not owned(worker, 'worker'):
        problems.append(f'{SERVICES["worker"]} exists but is not a CPT Studio worker container')
    return problems


def live_web_port() -> int:
    """The port the live HTTPS stage proxies to, which the running cpt-studio-web must publish; refused otherwise."""
    live = live_vhost_bytes()
    port = proxied_port(live.decode('utf-8', 'replace')) if live is not None else None
    if port is None:
        raise InstallError('quillmd-cpt is not an HTTPS stage proxying to 127.0.0.1:9150 or 9151.')
    web = inspect('container', SERVICES['web'])
    if (web is None or not owned(web, 'web') or not (web.get('State') or {}).get('Running')
            or published_port(web) != port):
        raise InstallError(f'quillmd-cpt proxies to 127.0.0.1:{port}, which the running {SERVICES["web"]} does not '
                           'publish.')
    return port


def serving_web_port() -> int:
    """The port the running cpt-studio-web publishes (one of WEB_PORTS), else WEB_PORT (a fresh host)."""
    web = inspect('container', SERVICES['web'])
    if web is not None and owned(web, 'web') and (web.get('State') or {}).get('Running'):
        return published_port(web) or WEB_PORT
    return WEB_PORT


def web_port_layout() -> dict:
    """Preflight's view of the two web ports. The active one - the port cpt-studio-web publishes, else the one the
    live HTTPS stage proxies to, else WEB_PORT - may be held by cpt-studio-web alone; the other must be free, since the
    next app starts the incoming web there; and no incoming web may be left from an interrupted app."""
    web = inspect('container', SERVICES['web'])
    active = published_port(web) if web is not None else None
    if active is None:
        live = live_vhost_bytes()
        active = (proxied_port(live.decode('utf-8', 'replace')) if live is not None else None) or WEB_PORT
    problems = []
    for port in WEB_PORTS:
        problem = port_problem(port, SERVICES['web'] if port == active else None)
        if problem:
            problems.append(problem + ('' if port == active else ' (the incoming web\'s port must be free)'))
    if inspect('container', INCOMING_WEB) is not None:
        problems.append(f'{INCOMING_WEB} is left from an interrupted app (ops/INSTALL.md, Recovery notes)')
    return {'active': active, 'idle': other_port(active), 'problems': problems}


STATIC_REFERENCE_RE = re.compile(r'''(?:href|src)=["'](/static/[^"'?#\s]+)["']''')


def smoke_web(port) -> dict:
    """Before the incoming web takes traffic: its sign-in page answers 200 text/html on 127.0.0.1:``port``, and every
    static file that page names (hashed names, from the web's own manifest) answers 200 from the same web. Read-only (a
    GET of the sign-in page writes nothing). Refused when the page names no static file: nothing would be checked."""
    headers = {'X-Forwarded-Proto': 'https'}
    login = probe('http', DOMAIN, '/login/', port=port, connect_ip='127.0.0.1', headers=headers, timeout=5,
                  keep_body=True)
    content_type = (login.get('headers', {}).get('content-type') or [''])[0]
    record = {'login': {'status': login.get('status'), 'content_type': content_type, 'error': login.get('error')},
              'assets': {}}
    problems = []
    if login.get('status') != 200 or not content_type.startswith('text/html'):
        problems.append(f'/login/ answered {login.get("status") or login.get("error")} {content_type}'.strip())
    else:
        paths = sorted(set(STATIC_REFERENCE_RE.findall((login.get('body') or b'').decode('utf-8', 'replace'))))
        if not paths:
            problems.append('the sign-in page names no static file, so none could be checked')
        for path in paths[:20]:
            asset = probe('http', DOMAIN, path, port=port, connect_ip='127.0.0.1', headers=headers, timeout=5)
            record['assets'][path] = asset.get('status') or asset.get('error')
            if asset.get('status') != 200:
                problems.append(f'{path} answered {asset.get("status") or asset.get("error")}')
    if problems:
        raise InstallError('The incoming web did not serve its own pages: ' + '; '.join(problems) + '.',
                           details={'smoke': record})
    return record


class AvailabilityRecorder:
    """https://cpt.quillmd.com/health/ through the public path - DNS, this host's nginx and whichever web it routes to,
    as a customer reaches it - every AVAILABILITY_INTERVAL_SECONDS in a daemon thread, from start() to stop(), which
    returns {'samples', 'statuses' (count per status, 'error' for no answer), 'releases_seen' (in the order first
    seen), 'non_200' (the first AVAILABILITY_KEPT, each {at, status, error}), 'non_200_count', 'started_at',
    'finished_at', 'interval_seconds'}. One request per sample (Connection: close), so each lands on the configuration
    nginx holds at that moment. A sample that raises is recorded as an error; nothing here raises into the phase."""

    def __init__(self, *, interval=AVAILABILITY_INTERVAL_SECONDS, check=None):
        self.interval = interval
        self.check = check or (lambda: probe('https', DOMAIN, '/health/', timeout=3))
        self.record = {'samples': 0, 'statuses': {}, 'releases_seen': [], 'non_200': [], 'non_200_count': 0,
                       'started_at': None, 'finished_at': None, 'interval_seconds': interval}
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None

    def sample(self):
        at = utc_now_ms()
        try:
            result = self.check()
        except Exception as error:  # noqa: BLE001 — a sample that cannot be taken is a non-200, never a crash
            result = {'error': type(error).__name__}
        status = result.get('status') if isinstance(result, dict) else None
        body = result.get('json') if isinstance(result, dict) and isinstance(result.get('json'), dict) else {}
        with self._lock:
            record = self.record
            record['samples'] += 1
            key = str(status) if status is not None else 'error'
            record['statuses'][key] = record['statuses'].get(key, 0) + 1
            release = body.get('release')
            if isinstance(release, str) and release not in record['releases_seen']:
                record['releases_seen'].append(release)
            if status != 200:
                record['non_200_count'] += 1
                if len(record['non_200']) < AVAILABILITY_KEPT:
                    record['non_200'].append({'at': at, 'status': status,
                                              'error': result.get('error') if isinstance(result, dict) else None})

    def _run(self):
        due = time.monotonic()
        while not self._stop.is_set():
            self.sample()
            due = max(due + self.interval, time.monotonic())
            self._stop.wait(max(0.0, due - time.monotonic()))

    def start(self):
        self.record['started_at'] = utc_now_ms()
        self._thread = threading.Thread(target=self._run, name='cpt-studio-availability', daemon=True)
        self._thread.start()
        return self

    def stop(self) -> dict:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        with self._lock:
            self.record['finished_at'] = utc_now_ms()
            return json.loads(json.dumps(self.record))


def drain_web(port, *, clock=time.monotonic, sleep=time.sleep, sample=None, nginx=None,
              minimum=DRAIN_MIN_SECONDS, quiet=DRAIN_QUIET_SECONDS, maximum=DRAIN_MAX_SECONDS) -> dict:
    """Wait, once nginx routes elsewhere, until the web on ``port`` can stop without cutting a request: at least
    ``minimum`` seconds (above gunicorn's request timeout, so every request it accepted before the switch has ended),
    then until ``quiet`` consecutive one-second samples see no connection to ``port`` a request can be in flight on
    (active_connections, /proc/net/tcp and tcp6) and no host nginx worker still shutting down from the reload
    (nginx_processes) - never longer than ``maximum``, after which it returns bounded_out (ops/INSTALL.md, Known limits:
    an upload an old nginx worker is still reading from its client reaches the stopped port). A sample that cannot be
    read, or no nginx process seen at all, counts as busy: it can only lengthen the drain."""
    sample = sample or (lambda: established_to(port))
    nginx = nginx or nginx_processes
    start, samples, run = clock(), 0, 0
    most = {'connections': 0, 'shutting_down': 0, 'unreadable': 0, 'nginx_unseen': 0}
    while True:
        try:
            connections = int(sample())
        except Exception:  # noqa: BLE001 — cannot tell: busy
            connections = None
            most['unreadable'] += 1
        try:
            workers = nginx()
            shutting = int(workers['shutting_down']) if workers.get('visible') else None
        except Exception:  # noqa: BLE001 — cannot tell: busy
            shutting = None
        if shutting is None:
            most['nginx_unseen'] += 1
        samples += 1
        most['connections'] = max(most['connections'], connections or 0)
        most['shutting_down'] = max(most['shutting_down'], shutting or 0)
        busy = connections is None or connections > 0 or shutting is None or shutting > 0
        run = 0 if busy else run + 1
        elapsed = clock() - start
        if elapsed >= minimum and run >= quiet:
            return {'port': port, 'seconds': round(elapsed, 1), 'samples': samples, 'bounded_out': False, **most}
        if elapsed >= maximum:
            return {'port': port, 'seconds': round(elapsed, 1), 'samples': samples, 'bounded_out': True,
                    'last': {'connections': connections, 'shutting_down': shutting}, **most}
        sleep(1)


PREFLIGHT_REMEDY = 'Run --phase preflight again (it records the baseline afresh), then rerun this phase.'


def baseline_problem(drifted, what, remedy=PREFLIGHT_REMEDY, *, baseline=None) -> str:
    """The refusal when co-tenant routing or app.quillmd.com no longer answer as the baseline recorded - this install's
    preflight (refutation r2, L6-4), or the one rollback-app reads itself in an undo's layout (``baseline`` is that
    record; refutation r3, D-1): the switch is verified against it, so it would fail after nginx moved - and after an
    undo had closed members' stages - for a reason the switch did not cause. ``remedy`` is the way on in the caller's
    layout."""
    source = ('the baseline rollback-app read for this switch back' if (baseline or {}).get('phase') == 'rollback-app'
              else 'this install\'s preflight baseline')
    return f'{"; ".join(drifted)} since {source}, which the switch is verified against, so {what}. {remedy}'


def switch_upstream(ctx, preflight, from_port, to_port, *, revision, progress, from_revision=None,
                    remedy=PREFLIGHT_REMEDY) -> dict:
    """The vhost's upstream from 127.0.0.1:``from_port`` to ``to_port``, through publish_vhost. The live file must be
    this revision's HTTPS rendering for ``from_port``, and co-tenant routing and app.quillmd.com must still answer as the
    preflight baseline recorded (refutation r2, L6-4) - refused otherwise, before anything changes; it is replaced
    atomically by the rendering for ``to_port`` - the two differ in their proxy_pass line alone - validated (nginx -t,
    no new warning), reloaded gracefully (old nginx workers finish what they accepted), and verified through the
    public path: /health/ serves ``revision`` (the web's on ``to_port``), and the co-tenants and app.quillmd.com answer
    as the preflight baseline recorded. When the web on ``from_port`` is the same revision (``from_revision``, the same
    when not given), /health/ cannot tell the two apart, so nginx must also be seen loading the switched file - new
    workers since it was written (nginx_applied; refutation r2, L6-7: a reload that exits 0 while the master keeps its
    old configuration). On any failure publish_vhost puts the exact previous bytes back and reloads again - whenever a
    reload was asked for, whatever it answered (L6-1). ``progress`` gets 'generation_at_apply' (nginx_generation) and
    'applied_at' (a UTC datetime) once the file is being replaced, and publish_vhost's 'reload_attempted', 'reloaded'
    and 'restore_reloaded': an undo closes what the incoming side may have started from that moment, and reads from them
    whether nginx may run the switched file (nginx_may_have_read). ``remedy`` ends a baseline refusal (baseline_problem)."""
    before = rendered_vhosts(ctx.revision, from_port)['https'].encode()
    after = rendered_vhosts(ctx.revision, to_port)['https'].encode()
    sha_before, sha_after = sha256(before), sha256(after)
    same = (from_revision or revision) == revision
    state = vhost_state()
    if state['file_sha256'] != sha_before or state['link_target'] != VHOST_LINK_TARGET:
        raise InstallError(f'quillmd-cpt is not this revision\'s HTTPS stage for port {from_port}; the upstream was '
                           'not switched.')
    drifted = ingress_checks(ctx, preflight)
    if drifted:
        raise InstallError(baseline_problem(drifted, 'the upstream was not switched', remedy, baseline=preflight),
                           details={'baseline': drifted})

    def apply():
        progress['generation_at_apply'] = nginx_generation()
        progress['applied_at'] = dt.datetime.now(dt.timezone.utc)
        vhost_operation('replace', expected_sha256=sha_before, content=base64.b64encode(after).decode())

    def undo():
        if vhost_state()['file_sha256'] == sha_after:
            vhost_operation('replace', expected_sha256=sha_after, content=base64.b64encode(before).decode())

    def verify():
        problems, evidence = https_checks(ctx, revision)
        if same:
            evidence['nginx_applied'] = applied = nginx_applied(progress.get('generation_at_apply'))
            if applied is not True:
                problems.append(f'nginx was not seen loading the switched vhost (no new worker since it was written: '
                                f'{"cannot be told" if applied is None else "none"}), and both webs are revision '
                                f'{revision[:12]}, so /health/ cannot tell which one answers')
        problems += ingress_checks(ctx, preflight)
        if problems:
            raise InstallError('; '.join(problems) + '.', details=evidence)
        return {'https': evidence}
    result = publish_vhost(ctx, apply, undo, verify, progress=progress)
    return {'from': from_port, 'to': to_port, 'vhost_sha_before': sha_before, 'vhost_sha_after': sha_after,
            'applied_at': progress['applied_at'].isoformat(), 'nginx_t_log': result.get('nginx_t_log'),
            'https_observations': (result.get('https') or {}).get('observations'),
            'https_final_status': ((result.get('https') or {}).get('final') or {}).get('status'),
            'nginx_applied': (result.get('https') or {}).get('nginx_applied')}


def nginx_may_have_read(progress) -> bool:
    """Whether nginx may run the vhost a switch wrote, after publish_vhost put the previous bytes back (switch_upstream's
    ``progress``): a reload of it was asked for - whatever the call answered (refutation r2, L6-1) - or nginx loaded a
    configuration since the file was written (anyone's reload: the TLS renewal hook's, a co-tenant's), or that cannot
    be told. Only a file that was never replaced, or one nginx is seen never to have reloaded since, is not."""
    if progress.get('applied_at') is None:
        return False
    if progress.get('reload_attempted') or progress.get('reloaded'):
        return True
    try:
        return nginx_moved(progress.get('generation_at_apply'), nginx_generation()) is not False
    except Exception:  # noqa: BLE001 — cannot tell: it may have
        return True


def settle_vhost(ctx, *, port, revision, other_revision) -> dict:
    """After a switch's previous vhost was put back while nginx may have run the switched one (nginx_may_have_read):
    nginx reloaded with the file once more and PROVEN to route to the web on ``port`` (refutation r2, L6-1) - the file
    is this revision's rendering for ``port``, nginx -t passes, a reload is seen applied (new workers) and the public
    /health/ is answered by ``revision``, that web's; health alone proves it only when the other web is another
    revision (``other_revision``), the new workers alone when it is the same (L6-7). {'proven', ...}; never raises
    (a Ctrl-C here too is 'not proven'): what is not proven keeps both webs running."""
    record = {'port': port, 'proven': False}
    try:
        expected = sha256(rendered_vhosts(ctx.revision, port)['https'].encode())
        state = vhost_state()
        if state['file_sha256'] != expected or state['link_target'] != VHOST_LINK_TARGET:
            record['problem'] = f'quillmd-cpt is not this revision\'s HTTPS stage for port {port}'
            return record
        test = nginx_test()
        record['nginx_t_ok'] = test['ok']
        if not test['ok']:
            record['problem'] = 'nginx -t does not pass'
            return record
        generation = nginx_generation()
        nginx_reload()
        record['reloaded'] = True
        record['nginx_applied'] = applied = nginx_applied(generation)
        served, observations = public_health(revision)
        record['health'] = {'revision': revision, 'served': served, 'observations': observations[-3:]}
        record['proven'] = bool(served) and (applied is True or revision != other_revision)
        if not record['proven']:
            record['problem'] = ('the public /health/ did not answer revision ' + revision[:12] if not served else
                                 'nginx was not seen loading the restored vhost, and both webs are revision '
                                 + revision[:12])
    except BaseException as error:  # noqa: BLE001 — what is not proven keeps both webs; the caller says so
        record['problem'] = f'{type(error).__name__}: {error}'
    return record


def serving_summary() -> dict:
    """What serves the site now, for a receipt (never raises): the port quillmd-cpt names and each CPT Studio service
    container's state, port and image."""
    summary = {}
    try:
        live = live_vhost_bytes()
        summary['vhost_port'] = proxied_port(live.decode('utf-8', 'replace')) if live is not None else None
    except Exception as error:  # noqa: BLE001
        summary['vhost_port'] = f'unreadable ({type(error).__name__})'
    found = {}
    for role in SERVICES:
        for name in service_names(role):
            try:
                container = inspect('container', name)
            except Exception as error:  # noqa: BLE001
                found[name] = f'unreadable ({type(error).__name__})'
                continue
            if container is not None:
                found[name] = {'id': str(container.get('Id'))[:12], 'image': str(container.get('Image'))[:19],
                               'running': bool((container.get('State') or {}).get('Running')),
                               'port': published_port(container)}
    summary['containers'] = found
    return summary


def log_tail(ctx, name, role, label):
    container = inspect('container', name)
    if container is not None and owned(container, role):
        tail = docker('logs', '--tail', '40', name, check=False, timeout=30)
        ctx.log(label, tail.stdout[-8192:] + tail.stderr[-8192:])


def retire_live_web(old_id) -> dict:
    """S5, once the old web is drained: stop it (graceful, 30 s), park it as cpt-studio-web-previous, and give the
    incoming web the canonical name - Docker renames a running container in place, nothing restarts."""
    name, parked = SERVICES['web'], SERVICES['web'] + '-previous'
    container = inspect('container', name)
    if container is None or container['Id'] != old_id or not owned(container, 'web'):
        raise InstallError(f'{name} is not the web the switch moved traffic from; it was left as it is.')
    if inspect('container', parked) is not None:
        raise InstallError(f'{parked} exists, so the old web was left running under its name.')
    docker('stop', '--time', str(STOP_SECONDS['web']), name, timeout=STOP_SECONDS['web'] + 60)
    docker('rename', name, parked)
    docker('rename', INCOMING_WEB, name)
    return {'id': container['Id'], 'image': container['Image'], 'revision': labels_of(container).get(REVISION_LABEL)}


def worker_after_failed_park() -> str:
    """After park('worker') failed or was interrupted: the old worker back under its own name and running again
    (park restarts it itself when only its rename failed; a '-previous' here is park's own, none being left before S1)."""
    name, parked = SERVICES['worker'], SERVICES['worker'] + '-previous'
    current, renamed = inspect('container', name), inspect('container', parked)
    if current is None and renamed is not None and owned(renamed, 'worker'):
        docker('rename', parked, name)
        current = inspect('container', name)
    if current is None:
        return 'not there (there was no worker)'
    if not owned(current, 'worker'):
        return f'{name}, which is not a CPT Studio worker, so it was left as it is'
    if (current.get('State') or {}).get('Running'):
        return f'still running (its stop did not finish; if it exits, start it again: docker start {name})'
    docker('start', name)
    return 'started again'


def restore_parked_worker(previous, *, start=True) -> str:
    """The worker park() parked (``previous``, park's answer) back under its name; started unless held, or unless it was
    not running when it was parked (park's 'running' False: refutation r3, D-2 - a worker an earlier undo held, or one
    stopped by hand, is put back as it was, never started by this install's undo)."""
    name, parked = SERVICES['worker'], SERVICES['worker'] + '-previous'
    if not previous:
        return 'there was no worker to put back'
    if inspect('container', name) is not None:
        raise InstallError(f'{name} exists, so the parked worker was left parked ({parked}).')
    docker('rename', parked, name)
    if not start:
        return f'put back under its name and left stopped ({name})'
    if previous.get('running') is False:
        return (f'put back under its name and left stopped ({name}), as it was: it was not running when this install '
                'parked it')
    docker('start', name)
    return 'put back and started'


def remove_incoming_web() -> str:
    """Stop and remove INCOMING_WEB: 'was removed', or what kept it (reported: the site does not depend on it). An
    interrupt is never swallowed (refutation r3, D-4: a Ctrl-C here had ended rollback-app as a success)."""
    try:
        remove_service_container(INCOMING_WEB, 'web')
    except Exception as error:  # noqa: BLE001 — reported; a KeyboardInterrupt goes on to the phase's own handler
        return f'could not be removed ({error}); remove it by hand'
    return 'was removed'


def stop_incoming_web() -> str:
    """Stop INCOMING_WEB (graceful, 30 s) before an undo's last close (refutation r3, D-6: a request an old nginx worker
    still held to it - a drain that ended bounded_out - could queue a stage after that close, which the old worker then
    ran): '' once it is seen stopped, or gone; otherwise what keeps it from being known stopped. An interrupt is never
    swallowed."""
    container = inspect('container', INCOMING_WEB)
    if container is None:
        return ''
    if not owned(container, 'web'):
        return f'{INCOMING_WEB} is not a CPT Studio web container, so it was not stopped'
    failure = ''
    try:
        docker('stop', '--time', str(STOP_SECONDS['web']), INCOMING_WEB, timeout=STOP_SECONDS['web'] + 60)
    except Exception as error:  # noqa: BLE001 — read back below: only a container seen stopped counts as stopped
        failure = str(error) or type(error).__name__
    after = inspect('container', INCOMING_WEB)
    if after is None or not (after.get('State') or {}).get('Running'):
        return ''
    return f'the incoming web ({INCOMING_WEB}) could not be stopped ({failure or "it still runs after docker stop"})'


def switch_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants=None, *, preflight,
                    plan, interpreter=None) -> dict:
    """The blue/green replacement (replacement_plan's 'blue-green'): the serving web is never stopped before the switch
    is verified and drained.

      S1  start the incoming web, INCOMING_WEB, on the idle port; it must answer health_ok for this revision and serve
          its own sign-in page and static files (smoke_web) - the old web still serves everything
      S2  park the old worker (docker stop --time 600: its current stage finishes; nothing new is claimed) - the old web
          still serves, and what members start waits in the queue
      S3  switch the vhost's upstream to the idle port (switch_upstream: atomic replace, nginx -t, graceful reload,
          /health/ = this revision through the public path, co-tenants unchanged)
      S4  start the new worker - processing resumes under the new rules
      S5  drain the old web (drain_web), stop it, park it as cpt-studio-web-previous and rename the incoming web to
          cpt-studio-web
    An AvailabilityRecorder probes the public /health/ from before S1 to the end (an undo included). Any failure is
    undone by undo_switch without interrupting the site; the InstallError it raises says what is left. phase_app then
    recomputes the stored list states and removes the parked pair (S6)."""
    live, idle = plan['live'], plan['idle']
    problems = switch_problems(plan)
    if problems:
        raise InstallError('The blue/green switch cannot start, so nothing was started or stopped: '
                           + '; '.join(problems) + '.', details={'plan': plan})
    drifted = ingress_checks(ctx, preflight)  # refutation r2, L6-4: before anything starts, not only after S3's reload
    if drifted:
        raise InstallError(baseline_problem(drifted, 'nothing was started or stopped'),
                           details={'plan': plan, 'baseline': drifted})
    steps, parked, started, progress = {}, {}, {}, {}
    record = {'mode': 'blue-green', 'ports': {'from': live, 'to': idle}, 'steps': steps}
    reached = [None]

    def step(name):
        reached[0] = name
        steps[name] = utc_now_ms()
    recorder = AvailabilityRecorder().start()
    try:
        step('S1')
        docker('run', '-d', *service_args('web', image_id, ctx.revision, provider_mode, authorization_ref, participants,
                                          name=INCOMING_WEB, port=idle, interpreter=interpreter),
               input=env_bytes, quiet=True)
        started['web'] = wait_service('web', ctx.revision, image_id, name=INCOMING_WEB, port=idle)
        record['smoke'] = smoke_web(idle)
        step('S2')
        parked['worker'] = park('worker')
        step('S3')
        record['switch'] = switch_upstream(ctx, preflight, live, idle, revision=ctx.revision, progress=progress,
                                           from_revision=plan['web']['revision'])
        step('S4')
        docker('run', '-d', *service_args('worker', image_id, ctx.revision, provider_mode, authorization_ref,
                                          participants, interpreter=interpreter), input=env_bytes, quiet=True)
        started['worker'] = wait_service('worker', ctx.revision, image_id)
        step('S5')
        record['drain'] = drain_web(live)
        parked['web'] = retire_live_web(plan['web']['id'])
        step('done')
        record['availability'] = recorder.stop()
    except BaseException as failure:
        details = {}  # written into as the undo goes, so a receipt after a second interrupt still says what it did
        try:
            message, details = undo_switch(ctx, failure, reached[0], image_id=image_id, env_bytes=env_bytes, plan=plan,
                                           preflight=preflight, parked=parked, progress=progress, details=details)
        except BaseException as second:  # noqa: BLE001 — the undo itself stopped: say so, with what is there now
            message = (f'{str(failure) or type(failure).__name__}; the undo at {reached[0]} stopped too '
                       f'({str(second) or type(second).__name__}): read "left" in this receipt, then ops/INSTALL.md, '
                       'Recovery notes')
        raise InstallError(message, details={**record, **details, 'failed_at': reached[0], 'started': started,
                                             'replaced': parked, 'availability': stop_recorder(recorder),
                                             'left': left_summary()}) from failure
    return {'started': started, 'replaced': parked, **record}


def stop_recorder(recorder) -> dict:
    """The availability record, even when the stop itself is interrupted (a second Ctrl-C)."""
    try:
        return recorder.stop()
    except BaseException as error:  # noqa: BLE001 — the receipt says so rather than losing the undo's message
        return {'error': f'the availability record could not be read ({type(error).__name__})'}


def left_summary() -> dict:
    try:
        return serving_summary()
    except BaseException as error:  # noqa: BLE001 — as stop_recorder
        return {'error': f'what is left could not be read ({type(error).__name__})'}


def undo_switch(ctx, failure, reached, *, image_id, env_bytes, plan, preflight, parked, progress,
                details=None) -> tuple:
    """(message, details) after a blue/green step failed, with the site kept served (the failure matrix, ops/INSTALL.md
    app). S1, S2: the incoming web is removed and the old worker runs again - nothing reached the new pair. S3: the vhost
    is already back (publish_vhost); when nginx may have run the switched file it is proven to run the restored one
    before anything else (undo_switch_s3; refutation r2, L6-1) - both webs stay otherwise, nothing closed, for
    rollback-app (refutation r3, D-3); what the incoming web may have started since the file changed is closed, and
    closed again once it was drained and stopped (L6-3; refutation r3, D-6), the list states the old revision labels
    otherwise are put back, the incoming web is removed, and the old worker is put back as it was - held while a close
    names records it would act on, or ones only a revision since the core repair writes that were written since the
    file changed (L6-6; refutation r3, D-2). S4: the new worker is stopped and what the new pair started is closed; when
    the close names a state the old web would SHOW wrongly that was not there before the switch (and the pair is
    another revision) the NEW web keeps serving, with the old worker parked and the new one stopped; otherwise
    return_to_old_web switches the vhost back (a graceful reload, /health/ = the old revision), drains and stops the
    incoming web, closes again, removes it and puts the old worker back (or holds it). A way back that cannot finish
    leaves the incoming web beside the old web and the old worker parked, for rollback-app (finish_back). S5: the new
    pair serves and nothing is undone."""
    cause = str(failure) or type(failure).__name__
    live, idle = plan['live'], plan['idle']
    web, worker = SERVICES['web'], SERVICES['worker']
    old_revision = plan['web']['revision']
    previous = parked.get('worker') or {'image': plan['web']['image'], 'revision': old_revision}
    details = {} if details is None else details
    if reached in (None, 'S1'):
        log_tail(ctx, INCOMING_WEB, 'web', 'incoming-web-failed')
        removed = remove_incoming_web()
        return (f'{cause}; the incoming web ({INCOMING_WEB}, port {idle}) {removed}, and nothing else changed: {web} '
                f'kept serving on {live} and the worker kept running. Migrations already applied are not reversed.',
                details)
    if reached == 'S2':
        state = worker_after_failed_park()
        removed = remove_incoming_web()
        return (f'{cause}; the old worker is {state}, the incoming web ({INCOMING_WEB}) {removed}, and nothing else '
                f'changed: {web} kept serving on {live}. Migrations already applied are not reversed.', details)
    if reached == 'done':
        return (f'{cause}; the switch had finished - the incoming pair serves on {idle} and the old pair is parked - '
                'but its availability record could not be read and the stored list states were not recomputed: '
                f'remove {web}-previous and {worker}-previous by hand, then rerun --phase app, which recomputes them.',
                details)
    if reached == 'S5':
        return (f'{cause}; the incoming pair serves (the vhost names {idle}, the new worker runs) and nothing was '
                'undone, but the old web was not retired and the stored list states were not recomputed: read "left" in '
                'this receipt, stop and remove what is left of the old web by hand (once it has no connection), rename '
                f'{INCOMING_WEB} to {web} if it still carries that name, remove {worker}-previous, then rerun --phase '
                'app, which recomputes them (ops/INSTALL.md, Recovery notes).', details)
    kinds = stage_kinds_of(previous.get('image'), env_bytes)
    reason = (f'its switch to revision {ctx.revision[:12]} failed and revision {old_revision[:12]} kept serving'
              if reached == 'S3' else
              f'the new worker of revision {ctx.revision[:12]} failed and revision {old_revision[:12]} was switched back')
    if reached == 'S3':
        return undo_switch_s3(ctx, cause, image_id=image_id, env_bytes=env_bytes, plan=plan, parked=parked,
                              progress=progress, previous=previous, kinds=kinds, reason=reason, details=details)
    return undo_switch_s4(ctx, cause, image_id=image_id, env_bytes=env_bytes, plan=plan, preflight=preflight,
                          parked=parked, progress=progress, previous=previous, kinds=kinds, reason=reason,
                          details=details)


def close_did_not_finish(what, error) -> str:
    """A close that raised may have committed before it stopped (CLOSE_STAGES commits its update, then reads every
    encounter: refutation r3, D-5), so it is never reported as having closed nothing."""
    return (f'the close of {what} did not finish ({str(error) or type(error).__name__}): it may have closed some or all '
            'of them before it stopped, and a stage it closed stays closed (failed, with the installer\'s note)')


def close_and_put_back(image_id, env_bytes, since, revision, reason, kinds, previous) -> dict:
    """The undo's close (close_undone_stages, with the old worker's kinds) and put-back (put_back_states, with the old
    pair's own image), each failure recorded rather than raised: {'closed', 'put_back', 'shown', 'acting',
    'problems', 'since'}. A close that did not answer, or answered no hazard list it read, holds the old worker (never
    read as 'none')."""
    out = {'closed': None, 'put_back': None, 'shown': None, 'acting': None, 'problems': [], 'since': since}
    try:
        out['closed'] = close_undone_stages(image_id, env_bytes, since, revision, reason, kinds)
    except BaseException as error:  # noqa: BLE001
        out['problems'].append(close_did_not_finish('the stages the new pair may have left open', error))
        return out
    out['shown'], out['acting'] = hazards_by_kind(out['closed'].get('hazards'))
    try:
        out['put_back'] = put_back_states(out['closed'], previous.get('image'), image_id, env_bytes)
    except BaseException as error:  # noqa: BLE001
        out['problems'].append(f'the list states the old revision labels otherwise could not be put back ({error})')
    return out


def undo_switch_s3(ctx, cause, *, image_id, env_bytes, plan, parked, progress, previous, kinds, reason,
                   details=None) -> tuple:
    """S3's undo (publish_vhost has put the previous vhost back): the incoming web is removed only once nginx is known
    not to route to it - it never read the switched file, or it was reloaded with the restored one and that was proven
    (settle_vhost; refutation r2, L6-1: an attempted reload may have been applied whatever its call answered) -
    otherwise both webs are left running, the old worker parked and nothing closed, and the receipt sends the operator
    to rollback-app, which finishes the undo before any older worker runs (refutation r3, D-3: the recovery note had
    the old worker started by hand over what the new web queued). What the incoming web may have started is closed
    from the moment the file was replaced, and closed again once it has been drained and stopped (L6-3; refutation r3,
    D-6: the stop comes before that close, so nothing it queues escapes it); the old worker is held while either close
    names a record it would act on, or one only a revision since the core repair writes that was written since the
    file was replaced (WEB_WRITTEN_HAZARDS; L6-6, refutation r3 D-2), and is put back as it was (restore_parked_worker).
    A close or put-back that does not finish, or an incoming web that cannot be stopped, leaves the incoming web beside
    the old web and the old worker parked, for rollback-app (finish_back)."""
    live, idle = plan['live'], plan['idle']
    worker = SERVICES['worker']
    web = SERVICES['web']
    old_revision = plan['web']['revision']
    applied = progress.get('applied_at') is not None
    halfway = (f'both webs were left running and the old worker parked ({worker}-previous), and nothing was closed: '
               f'{ROLLBACK_APP_GOES_BACK}. Read "left" in this receipt, then ops/INSTALL.md, Recovery notes (a switch '
               'that stopped half way)')
    details = {} if details is None else details
    if applied and vhost_state()['file_sha256'] == sha256(rendered_vhosts(ctx.revision, idle)['https'].encode()):
        # publish_vhost could not put the previous vhost back: the file still names the incoming web
        return (f'{cause}; quillmd-cpt still names the incoming web ({INCOMING_WEB}, port {idle}), so {halfway}.',
                details)
    touched = nginx_may_have_read(progress)
    if touched:
        details['settle'] = settle_vhost(ctx, port=live, revision=old_revision, other_revision=ctx.revision)
        if not details['settle']['proven']:
            return (f'{cause}; the previous vhost was put back, but nginx may still route to the incoming web '
                    f'({INCOMING_WEB}, port {idle}): a reload of the switched vhost was asked for, or nginx loaded '
                    'one since it was written, and nginx was not proven to run the previous one again '
                    f'({details["settle"].get("problem")}), so {halfway}.', details)
    closes, first_at = [], dt.datetime.now(dt.timezone.utc)
    if applied:
        closes.append(close_and_put_back(image_id, env_bytes, progress['applied_at'], ctx.revision, reason, kinds,
                                         previous))
        details.update(stages_closed=closes[0]['closed'], states_put_back=closes[0]['put_back'])
    vhost = ('the vhost was put back and nginx proven to run it again' if touched else
             'the vhost was put back before nginx read it' if applied else 'the vhost was not changed')
    same = same_revision(previous, ctx.revision)
    if touched:
        done = finish_back(ctx, image_id=image_id, env_bytes=env_bytes, idle=idle, previous=previous,
                           parked_worker=parked.get('worker'), kinds=kinds, reason=reason, since=first_at,
                           closes=closes, details=details,
                           hold=lambda every: undo_hold(every, same=same, window='the vhost file was replaced'))
        if done['outcome'] == 'back':
            return (f'{cause}; {vhost}, so {web} kept serving on {live}; {done["problem"]}. {left_for_rollback_app()} '
                    'Migrations already applied are not reversed.', details)
        removed, worker_note, hold, notes = done['removed'], done['worker_note'], done['hold'], done['notes']
    else:  # nginx never read the switched file: the incoming web took no request
        removed = remove_incoming_web()
        hold, notes = undo_hold(closes, same=same, window='the vhost file was replaced')
        worker_note = restore_parked_worker(parked.get('worker'), start=not hold)
    return (f'{cause}; {vhost}, so {web} kept serving on {live}; the incoming web ({INCOMING_WEB}) {removed}; the old '
            f'worker was {worker_note}.{held_sentence(hold, notes)} Migrations already applied are not reversed.',
            details)


# What the receipts of a way back that could not finish say (refutation r3, D-3 and D-6): the only safe next step is
# this revision's rollback-app, which closes everything the incoming web could have queued before the old worker runs.
ROLLBACK_APP_GOES_BACK = ('to go back, run this revision\'s --phase rollback-app: it proves nginx runs the vhost when '
                          'that names the old web, or switches the vhost back when it names the incoming web, and '
                          'closes everything the incoming web could have queued since it was created before it puts the '
                          'old worker back. Never start the old worker by hand: it would run that work under its own '
                          'rules')


def left_for_rollback_app() -> str:
    """The sentence of a way back that stopped before anything was removed (finish_back's 'back')."""
    web, worker = SERVICES['web'], SERVICES['worker']
    return (f'The incoming web ({INCOMING_WEB}) was left beside the old web ({web}) and the old worker parked '
            f'({worker}-previous): run this revision\'s --phase rollback-app, which stops the incoming web, closes '
            'everything it could have queued since it was created and puts the old worker back (ops/INSTALL.md, '
            'Recovery notes). Never start the old worker by hand: it would run that work under its own rules.')


def held_sentence(hold, notes) -> str:
    """The receipt's sentence on the old worker's hold (undo_hold, return_hold): why it is held and how it is released,
    or what is only named."""
    if not hold:
        return (' ' + '; '.join(notes) + '.') if notes else ''
    reads = (' A revision since the core repair reads a member\'s answer and a chosen modifier as this one does: if the '
             'old revision is one, those alone need no clearing.') if any(WEB_WRITTEN_NOTE in note for note in notes) else ''
    return (' It is held - nothing can be sent - because ' + '; '.join(notes) + ': install this revision again once its '
            'failure is fixed (its web and worker read them under its own rules), or start the old worker by hand once '
            f'they are cleared (ops/INSTALL.md, Reinstalling an older revision).{reads}')


# Refutation r2, L6-6, as refutation r3 (D-2) corrected it: the SHOWN_HAZARDS only a revision since the core repair
# writes - a member's answer, a reviewer's chosen modifier; no worker makes either, but for the assessment a worker since
# the completion repair re-makes with a member's answer, which UNDO_HAZARDS' written_since times as this revision's own
# write (refutation cycle 2, answers W3). Which web wrote one cannot be read
# (a revision since the core repair writes them too, and reads them as this one does), but WHEN it was written can: one
# written in an undo's window (CLOSE_STAGES' 'written_since') holds the old worker - a revision before the core repair
# shows it wrongly, and its worker's re-assessment would drop a chosen modifier (its carry has no such column) - while
# one written before the switch began was there before this install, beside the old pair, and is named only. A pair of
# this same revision reads them as this revision does.
WEB_WRITTEN_HAZARDS = ('member_answer', 'modifier')
WEB_WRITTEN_NOTE = 'hold records only a revision since the core repair writes'
WEB_WRITTEN_SHOWN = ('a revision before the core repair shows them wrongly - it asks the answered question again, and '
                     'shows the approval without its modifier - and its worker would drop a chosen modifier when it '
                     're-assesses; a revision before the completion repair also reads an assessment re-made with an '
                     'answer as an ordinary exclusion, so a base code that answer still held may show READY')


def merge_hazards(*answers) -> dict:
    """{encounter id: sorted reasons} of every hazards dict given (None and {} skipped)."""
    merged = {}
    for answer in answers:
        for pk, reasons in (answer or {}).items():
            merged.setdefault(pk, set()).update(reasons)
    return {pk: sorted(reasons) for pk, reasons in sorted(merged.items())}


def without(hazards, taken) -> dict:
    """``hazards`` less the reasons ``taken`` names for the same encounter (empty entries dropped)."""
    left = {pk: [reason for reason in reasons if reason not in (taken.get(pk) or ())] for pk, reasons in hazards.items()}
    return {pk: reasons for pk, reasons in left.items() if reasons}


def web_written_by_time(closed) -> tuple:
    """(since, before, unplaced): the WEB_WRITTEN_HAZARDS a close's answer (CLOSE_STAGES) names, split into those whose
    records were written since that close's 'since' - its 'written_since' names them - and those written before it
    (refutation r3, D-2); 'unplaced' holds every one when the answer names them without a readable 'written_since',
    which its caller holds as written since (a record whose time is not known is never read as older)."""
    hazards = closed.get('hazards') if isinstance(closed, dict) else None
    if not isinstance(hazards, dict):
        return {}, {}, {}
    named = {pk: [reason for reason in reasons if reason in WEB_WRITTEN_HAZARDS]
             for pk, reasons in hazards.items() if isinstance(reasons, list)}
    named = {pk: reasons for pk, reasons in named.items() if reasons}
    told = closed.get('written_since')
    if not (isinstance(told, dict) and all(isinstance(reasons, list) for reasons in told.values())):
        return {}, {}, named
    since = {pk: [reason for reason in reasons if reason in (told.get(pk) or ())] for pk, reasons in named.items()}
    since = {pk: reasons for pk, reasons in since.items() if reasons}
    return since, without(named, since), {}


def written_note(written, when) -> str:
    return (f'{hazard_summary(written)} {WEB_WRITTEN_NOTE} (a member\'s answer, a reviewer\'s chosen modifier), written '
            f'{when}: {WEB_WRITTEN_SHOWN}')


def before_note(before, when) -> str:
    return (f'{hazard_summary(before)} hold such records written {when}, while only the old web could take requests: '
            'they were beside the old pair before the new web took any, so they are named only (a revision before the '
            'core repair shows them wrongly)')


def undo_hold(closes, *, same, strict=False, window='this switch began') -> tuple:
    """(hold, notes) from an undo's closes (close_and_put_back's answers): a close that failed, or named nothing it
    read, holds the old worker; so does a record it would act on under its own rules, and one only a revision since the
    core repair writes (WEB_WRITTEN_HAZARDS) that was written since its close's 'since' - unless the old pair is this
    same revision (refutation r3, D-2: one written before the switch began was beside the old pair before this
    install, and is named only; it had held the old worker of a pair that reads it, and the receipt had said the new web
    wrote it). ``strict`` (rollback-app, which did not run the install and cannot tell whether the old worker ran
    beside one before it) holds for those written before too. ``window`` names what the earliest close's 'since' is.
    The other shown states are named only: the old web never stopped showing them, and no new worker ran."""
    notes = [problem for close in closes for problem in close['problems']]
    unread = any(close['closed'] is not None and close['acting'] is None for close in closes)
    acting = merge_hazards(*(close['acting'] for close in closes))
    shown = merge_hazards(*(close['shown'] for close in closes))
    written, before, unplaced = {}, {}, {}
    if not same:
        split = [web_written_by_time(close['closed']) for close in closes if close['closed'] is not None]
        written = merge_hazards(*(three[0] for three in split))
        unplaced = without(merge_hazards(*(three[2] for three in split)), written)
        before = without(without(merge_hazards(*(three[1] for three in split)), written), unplaced)
    others = without(shown, {pk: list(WEB_WRITTEN_HAZARDS) for pk in shown}) if not same else shown
    begun = min((close['since'] for close in closes if close.get('since') is not None), default=None)
    when = f'{window} ({begun.isoformat()})' if begun is not None else window
    if unread:
        notes.append('the close did not say which encounters it named, which holds records the old revision would act '
                     'on under its own rules')
    if acting:
        notes.append(hazard_summary(acting) + ' hold records the old revision would act on under its own rules')
    if written:
        notes.append(written_note(written, f'since {when}'))
    if unplaced:
        notes.append(written_note(unplaced, f'at a time the close did not say, so held as written since {when}'))
    if strict and before:
        notes.append(written_note(before, f'before {when}, which rollback-app holds too: it cannot tell whether the '
                                          'old worker ran beside them before this install'))
        before = {}
    hold = bool(notes)
    if before:
        notes.append(before_note(before, f'before {when}'))
    if others:
        notes.append(hazard_summary(others) + ' hold states an older revision shows wrongly; the old web never stopped '
                     'showing them and no new worker ran, so the receipt names them only')
    return hold, notes


def finish_back(ctx, *, image_id, env_bytes, idle, previous, parked_worker, kinds, reason, since, closes, details,
                hold, worker=False) -> dict:
    """The end of every way back to the old web, once nginx is proven to route to it - the S3 undo after its proof,
    return_to_old_web after its switch back, rollback-app in the 'back' layout (refutation r3, D-3 and D-6): the
    incoming web on ``idle`` drained while it runs and STOPPED, and only then everything since ``since`` closed and the
    list states put back; then this revision's worker (``worker``) and the incoming web removed, and the old worker put
    back - started unless ``hold`` (called with every close: ``closes`` and the last) holds it, and as it was
    (restore_parked_worker). Before anything is removed it stops, outcome 'back' with its 'problem', when a close or
    put-back of ``closes`` did not finish, when the incoming web cannot be stopped, or when the last close or put-back
    does not finish: the incoming web stays beside the old web and the old worker parked, for rollback-app, which
    closes again from the incoming web's creation ('back' layout). {'outcome': 'back', 'held' or 'switched',
    'problem', 'removed', 'left', 'worker_removed', 'worker_note', 'hold', 'notes'}; what it did is written into
    ``details`` as it goes. An interrupt is never swallowed."""
    out = {'outcome': 'back', 'problem': '', 'removed': None, 'left': True, 'worker_removed': False,
           'worker_note': None, 'hold': True, 'notes': []}
    failed = [problem for close in closes for problem in close['problems']]
    if failed:
        out['problem'] = '; '.join(failed)
        return out
    incoming = inspect('container', INCOMING_WEB)
    if incoming is not None and (incoming.get('State') or {}).get('Running'):
        details['incoming_drain'] = drain_web(idle)
    problem = stop_incoming_web()
    details['incoming_stopped'] = not problem
    if problem:
        out['problem'] = problem + ', so nothing more was closed: what it may still queue would escape a close'
        return out
    last = close_and_put_back(image_id, env_bytes, since, ctx.revision, reason, kinds, previous)
    details.update(stages_closed_after_drain=last['closed'], states_put_back_after_drain=last['put_back'])
    if last['problems']:
        out['problem'] = '; '.join(last['problems'])
        return out
    if worker and inspect('container', SERVICES['worker']) is not None:
        remove_service_container(SERVICES['worker'], 'worker')
        out['worker_removed'] = details['worker_removed'] = True
    out['removed'] = remove_incoming_web()
    out['left'] = details['incoming_left'] = inspect('container', INCOMING_WEB) is not None
    out['hold'], out['notes'] = hold([*closes, last])
    out['worker_note'] = restore_parked_worker(parked_worker, start=not out['hold'])
    out['outcome'] = 'held' if out['hold'] else 'switched'
    return out


def keep_note(live, idle) -> str:
    web, worker = SERVICES['web'], SERVICES['worker']
    return (f'the new web keeps serving on {idle} ({INCOMING_WEB}); its worker ({worker}) is stopped and the old '
            f'worker parked ({worker}-previous), so nothing is processed until a person decides; the old web is still '
            f'running on {live} with no traffic. Read "left" in this receipt, then ops/INSTALL.md, Recovery notes')


# return_to_old_web's switch back is verified against the baseline it is given; when that no longer holds, the remedy is
# rollback-app in the keep layout, which reads its own (refutation r3, D-1: preflight refuses while a -next exists).
KEEP_BASELINE_REMEDY = ('To switch back, run --phase rollback-app: in this layout it reads co-tenant routing and '
                        'app.quillmd.com afresh, right before it acts.')


def return_hold(first, last, *, same, first_at) -> tuple:
    """(hold, notes) of return_to_old_web: held while either close names a record the old worker would act on, or
    named nothing it read, or while the close after the drain (``last``, close_and_put_back's answer) names a state the
    old web shows wrongly - a worker's, or a member's answer or chosen modifier written since the first close
    (``first_at``; refutation r3, D-2: one written before the switch began, which the first close let through, was beside
    the old pair before this install, and is named only). A pair of this same revision reads them as this one does."""
    notes = []
    _, first_acting = hazards_by_kind(first.get('hazards'))
    if first_acting is None:  # never read as "none" (a same-revision pair reaches here with it)
        notes.append('the first close did not say which encounters it named')
    if last['closed'] is not None and last['acting'] is None:
        notes.append('the close after the drain did not say which encounters it named')
    acting = merge_hazards(first_acting, last['acting'])
    if acting:
        notes.append(hazard_summary(acting) + ' hold records it would act on under its own rules')
    named = []
    if last['shown'] and not same:
        written, before, unplaced = web_written_by_time(last['closed'])
        others = without(last['shown'], {pk: list(WEB_WRITTEN_HAZARDS) for pk in last['shown']})
        since = f'the first close ({first_at.isoformat()})'
        if others:
            notes.append(hazard_summary(others) + ' hold states the old web shows wrongly whatever it is handed (a '
                         'bounded second review refused whole or not read, a code only a harness participant proposed)')
        if written:
            notes.append(written_note(written, f'since {since}') + '; install this revision again to show them as they '
                         'are')
        if unplaced:
            notes.append(written_note(unplaced, f'at a time the close did not say, so held as written since {since}')
                         + '; install this revision again to show them as they are')
        if before:
            named.append(before_note(before, 'before this switch began'))
    return bool(notes), notes + named


def return_to_old_web(ctx, cause, *, image_id, env_bytes, preflight, live, idle, old_revision, previous,
                      parked_worker, kinds, reason, first, first_at, details=None) -> tuple:
    """The switch back of an undone switch whose new web serves on ``idle`` (as INCOMING_WEB) and whose old web still
    runs on ``live`` - the S4 undo, and rollback-app in the S4 'keep' layout - from its first close ``first`` on (it
    named no state the old web shows wrongly that it would not have shown before the install): the list states put
    back, the upstream switched back (a graceful reload, /health/ = ``old_revision``), then finish_back: the incoming
    web drained and stopped, closed again from ``first_at`` (refutation r2, L6-3: the new web took every request until
    the reload, and finished those in flight during the drain; refutation r3, D-6: after its stop), the states put back
    again, the new worker and the incoming web removed, and the old worker put back (return_hold) as it was. A switch
    back whose reload was asked for and that then failed leaves both webs running unless nginx is proven to run the new
    web's vhost again (settle_vhost, L6-1). (message, details, outcome): outcome 'kept' (the new web keeps serving),
    'halfway' (nginx may route to either web), 'back' (finish_back stopped: the old web serves, the incoming web beside
    it, the old worker parked, for rollback-app), 'held' or 'switched'; details['incoming_left'] says whether the
    incoming web could not be removed. ``details``, when given, is written into as it goes."""
    web, worker = SERVICES['web'], SERVICES['worker']
    keep = keep_note(live, idle)
    details = {} if details is None else details
    same = same_revision(previous, ctx.revision)
    try:
        details['states_put_back'] = put_back_states(first, previous.get('image'), image_id, env_bytes)
    except BaseException as error:  # noqa: BLE001
        return (f'{cause}; the list states the old revision labels otherwise could not be put back ({error}), so '
                f'{keep}.', details, 'kept')
    back = {}
    try:
        details['switch_back'] = switch_upstream(ctx, preflight, idle, live, revision=old_revision, progress=back,
                                                 from_revision=ctx.revision, remedy=KEEP_BASELINE_REMEDY)
    except BaseException as failure:  # noqa: BLE001
        error = str(failure) or type(failure).__name__
        if nginx_may_have_read(back):
            details['settle'] = settle_vhost(ctx, port=idle, revision=ctx.revision, other_revision=old_revision)
            if not details['settle']['proven']:
                return (f'{cause}; the switch back to the old web failed ({error}) after nginx was asked to reload with '
                        'it, and nginx was not proven to run the new web\'s vhost again '
                        f'({details["settle"].get("problem")}), so nginx may route to either web: both webs were left '
                        f'running ({INCOMING_WEB} on {idle}, {web} on {live}), the new worker stopped ({worker}) and '
                        f'the old worker parked ({worker}-previous). Remove neither before reading which one nginx '
                        'serves: read "left" in this receipt, then ops/INSTALL.md, Recovery notes (a switch that '
                        'stopped half way). The list states were put back to the old revision\'s: rerun --phase app, '
                        'which recomputes them.', details, 'halfway')
        return (f'{cause}; the switch back to the old web failed ({error}) and the vhost was left on the new one, so '
                f'{keep}. The list states were put back to the old revision\'s: rerun --phase app, which recomputes '
                'them.', details, 'kept')
    done = finish_back(ctx, image_id=image_id, env_bytes=env_bytes, idle=idle, previous=previous,
                       parked_worker=parked_worker, kinds=kinds, reason=reason, since=first_at, closes=[],
                       details=details, worker=True,
                       hold=lambda every: return_hold(first, every[-1], same=same, first_at=first_at))
    switched = f'{cause}; the vhost was switched back, so {web} (revision {old_revision[:12]}) serves on {live} again'
    if done['outcome'] == 'back':
        return (f'{switched}; {done["problem"]}. {left_for_rollback_app()} Migrations already applied are not '
                'reversed.', details, 'back')
    held = (f' It is held - nothing can be sent - because {"; ".join(done["notes"])} (ops/INSTALL.md, Reinstalling an '
            'older revision).') if done['hold'] else ((' ' + '; '.join(done['notes']) + '.') if done['notes'] else '')
    removed = 'the new worker was removed' if done['worker_removed'] else 'there was no new worker to remove'
    return (f'{switched}; {removed} and the incoming web {done["removed"]}; the old worker was {done["worker_note"]}.'
            f'{held} Migrations already applied are not reversed.', details, done['outcome'])


def undo_switch_s4(ctx, cause, *, image_id, env_bytes, plan, preflight, parked, progress, previous, kinds,
                   reason, details=None) -> tuple:
    live, idle = plan['live'], plan['idle']
    worker = SERVICES['worker']
    log_tail(ctx, worker, 'worker', 'worker-failed')
    stop_service_container(worker, 'worker')  # its current stage finishes (600 s)
    keep = keep_note(live, idle)
    details = {} if details is None else details
    first_at = dt.datetime.now(dt.timezone.utc)
    try:
        closed = close_undone_stages(image_id, env_bytes, progress['applied_at'], ctx.revision, reason, kinds)
    except BaseException as error:  # noqa: BLE001
        return (f'{cause}; {close_did_not_finish("the stages the new pair left open", error)}, so {keep}.', details)
    details['stages_closed'] = closed
    shown, acting = hazards_by_kind(closed.get('hazards'))
    if shown is not None and not same_revision(previous, ctx.revision):
        # refutation r3, D-2: a member's answer or a chosen modifier written before the switch began was beside the old
        # pair before this install: it does not keep the new web serving (return_to_old_web names it)
        _, before, _ = web_written_by_time(closed)
        shown = without(shown, before)
    if (shown is None or shown) and not same_revision(previous, ctx.revision):
        named = hazard_summary(shown) if shown is not None else 'the close did not say which encounters'
        return (f'{cause}; {named} hold states the old revision would show wrongly whatever it is handed (a bounded '
                'second review refused whole or not read, a code only a harness participant proposed, a member\'s '
                'answer or a chosen modifier written since this switch began), and this revision shows them as they '
                f'are: {keep}.', details)
    message, _, _ = return_to_old_web(ctx, cause, image_id=image_id, env_bytes=env_bytes, preflight=preflight,
                                      live=live, idle=idle, old_revision=plan['web']['revision'],
                                      previous=previous, parked_worker=parked.get('worker'), kinds=kinds,
                                      reason=reason, first=closed, first_at=first_at, details=details)
    return message, details


# --- phases ------------------------------------------------------------------------

def participant_source_problems(paths) -> list:
    """The participants' sources are optional - a missing one leaves its participant disabled - but one that is there
    must be root-only, in a root-only directory, or the secrets phase refuses it (HARNESS.md 8). ``paths``:
    helper_stat's answer for PROVIDER_SOURCES and each source."""
    problems = []
    folder = paths[PROVIDER_SOURCES]
    if folder.get('exists') and folder != {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}:
        problems.append(f'{PROVIDER_SOURCES} is not a root-owned 0700 directory')
    for spec in PARTICIPANTS.values():
        found = paths[spec['source']]
        if found.get('exists') and found != {'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o600'}:
            problems.append(f'{spec["source"]} is not a root-owned 0600 regular file')
    return problems


def interpreter_source_problems(paths) -> list:
    """The interpreter's source (design/FINAL.md 13), read as a participant's: optional here - preflight does not know
    the mode the app phase will be given, and the app phase refuses --interpreter-mode live without its copy - but one
    that is there must be a root-owned 0600 regular file, or the secrets phase refuses it. ``paths``: helper_stat's
    answer, the source included (its directory is participant_source_problems')."""
    found = paths[INTERPRETER['source']]
    if found.get('exists') and found != {'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o600'}:
        return [f'{INTERPRETER["source"]} is not a root-owned 0600 regular file']
    return []


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
    # The web's two ports: the active one held by cpt-studio-web alone, the other free for the next incoming web.
    details['web_ports'] = web_port_layout()
    problems += details['web_ports']['problems']
    problem = port_problem(DB_PORT, DB_CONTAINER)
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
    participant_paths = [path for spec in PARTICIPANTS.values() for path in (spec['source'], spec['target'])]
    details['paths'] = helper_stat([CORTI_SOURCE, ETC_DIR, *LE_DIRS, ACME_CHALLENGE_DIR, PROVIDER_SOURCES,
                                    *participant_paths, INTERPRETER['source'], INTERPRETER['target']])
    if not details['paths'][CORTI_SOURCE].get('exists'):
        problems.append(f'{CORTI_SOURCE} is missing')
    problems += participant_source_problems(details['paths'])
    problems += interpreter_source_problems(details['paths'])
    details['participant_sources'] = {name: 'present' if details['paths'][spec['source']].get('exists') else 'absent'
                                      for name, spec in PARTICIPANTS.items()}
    details['interpreter_source'] = 'present' if details['paths'][INTERPRETER['source']].get('exists') else 'absent'
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
    # The harness participants' credentials, after the set above and never part of it (HARNESS.md 8).
    participants = participant_secrets()
    states = ', '.join(f'{name} {entry["state"]}' for name, entry in participants.items())
    # Then the interpreter's (design/FINAL.md 13, D14), in a run of its own: copied unread, by key name only.
    interpreter = interpreter_secrets()
    copied = ', '.join(f'{name} {entry["state"]}' for name, entry in interpreter.items())
    return {'etc_dir': etc['etc_dir'], **result, 'participant_credentials': participants,
            'interpreter_credentials': interpreter,
            'summary': f'secrets {result["state"]}; participant credentials: {states}; interpreter credentials: '
                       f'{copied}; values never left the helper'}


# --- migrations ----------------------------------------------------------------------
# The app phase migrates while the previous pair still runs (it replaces the pair afterwards), a failed replacement
# restores that pair on the migrated schema, rollback-app hands an older pair the rows, and no migration is ever
# reversed. So every migration after the oldest revision a rollback goes back to must leave that revision's code
# working: additive, with a database default for every NOT NULL column it adds (an older pair's insert names none).
# 0005 is the leaf of 057a7d39, that oldest revision (UNDO_HAZARDS); 0006 is in every revision installed since 2b82889f.
ROLLING_BASELINE = 5
MIGRATION_FILE_RE = re.compile(r'(\d{4})_\w+\.py')
SET_DEFAULT_RE = re.compile(r'\s*ALTER\s+TABLE\s+"?(\w+)"?\s+ALTER\s+COLUMN\s+"?(\w+)"?\s+SET\s+DEFAULT\s+\S.*',
                            re.IGNORECASE | re.DOTALL)
_UNREAD = object()


def _literal(node):
    try:
        return ast.literal_eval(node) if node is not None else None
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _UNREAD


def _call(node):
    """(callee's last name, {keyword: node}) of a call such as migrations.AddField(...); (None, {}) for anything else.
    A positional argument is not read, so the operation is named but its keywords are left unread (None)."""
    if not isinstance(node, ast.Call):
        return None, {}
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        return name, None
    return name, {keyword.arg: keyword.value for keyword in node.keywords}


def _statements(value):
    """RunSQL's forward SQL as a list of strings, or None when it is anything else (SQL with parameters included)."""
    sql = _literal(value)
    if isinstance(sql, str):
        return [sql]
    if isinstance(sql, (list, tuple)) and all(isinstance(item, str) for item in sql):
        return list(sql)
    return None


# Refutation r2, L6-8: an index is safe for an older pair only when it can refuse none of its writes - Django's own
# (non-unique) Index; any index on a table this migration creates; or a UNIQUE index (studio.models.UniqueIndex) that is
# partial over rows whose column, one this migration adds as nullable with no database default, is set - an older pair
# never writes that column, so its rows hold NULL there and stay outside the index. Every other index - a unique one on
# an existing table otherwise, or a class this check does not read - is refused like a constraint on an existing table.
NON_UNIQUE_INDEXES = ('django.db.models.Index', 'django.db.models.indexes.Index')
UNIQUE_INDEXES = ('studio.models.UniqueIndex',)


def _imports(tree) -> dict:
    """{name: what it is bound to} by the module's top-level imports: 'models' -> 'django.db.models' for
    `from django.db import models`, 'studio' -> 'studio' for `import studio.models`."""
    names = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                names[alias.asname or alias.name] = f'{node.module}.{alias.name}'
    return names


def _dotted(node, imports):
    """The dotted name a call's callee resolves to through ``imports`` (None for anything but a name or attributes)."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.insert(0, node.attr)
        node = node.value
    if not isinstance(node, ast.Name) or node.id not in imports:
        return None
    return '.'.join([imports[node.id], *parts])


def _not_null_condition(node, imports):
    """The field F of an index condition that is exactly Q(F__isnull=False) or Q(('F__isnull', False)); else None."""
    if not isinstance(node, ast.Call) or _dotted(node.func, imports) != 'django.db.models.Q':
        return None
    if node.args and not node.keywords and len(node.args) == 1:
        pair = _literal(node.args[0])
        lookup = pair[0] if isinstance(pair, tuple) and len(pair) == 2 and pair[1] is False else None
    elif node.keywords and not node.args and len(node.keywords) == 1 and _literal(node.keywords[0].value) is False:
        lookup = node.keywords[0].arg
    else:
        return None
    if not isinstance(lookup, str) or not lookup.endswith('__isnull'):
        return None
    field = lookup[:-len('__isnull')]
    return field if re.fullmatch(r'[a-z_][a-z0-9_]*', field) and '__' not in field else None


def _unique_field(field_kind, field) -> bool:
    """Whether an added field makes its column unique - unique=True, primary_key=True, or a OneToOneField (Django
    gives each a UNIQUE constraint) - reading a value of either keyword this check cannot read as unique (refutation
    r3, D-7: the AddField branch never read `unique`)."""
    if field_kind == 'OneToOneField':
        return True
    return any(_literal(field[name]) is not False for name in ('unique', 'primary_key') if name in field)


def migration_verdict(source: str) -> dict:
    """{'safe', 'why'} of one migration file, read with ast (nothing imported or run). Safe operations: CreateModel (a
    table no older revision reads); AddField to a table this migration creates, or nullable, or with db_default, or
    whose column this migration's SQL gives a default - but a unique column (unique, a primary key, a one-to-one field)
    on an existing table only when it is nullable with no database default, so that an older pair's inserts leave it
    NULL, which a unique constraint never refuses (refutation r3, D-7: with a default, each of its inserts gets that one
    value and the second is refused); AddIndex of Django's own non-unique Index, on a table this
    migration creates, or a unique index that is partial over rows whose column - one this migration adds as nullable,
    with no database default - is set (NON_UNIQUE_INDEXES, UNIQUE_INDEXES); AddConstraint on a table this migration
    creates; and RunSQL that only sets column defaults. Anything else - a removed, renamed or altered column or table,
    a constraint or another unique index on an existing table, an index of a class this check does not read,
    RunPython, other SQL, a form this reader does not read - is not."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {'safe': False, 'why': ['the file does not parse']}
    imports = _imports(tree)
    operations = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Migration':
            for item in node.body:
                if (isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name)
                        and item.targets[0].id == 'operations' and isinstance(item.value, (ast.List, ast.Tuple))):
                    operations = [_call(element) for element in item.value.elts]
    if operations is None:
        return {'safe': False, 'why': ['no operations list was read']}
    created, defaults, nullable = set(), set(), {}
    for kind, keywords in operations:
        if kind == 'CreateModel' and keywords is not None and isinstance(_literal(keywords.get('name')), str):
            created.add(_literal(keywords['name']).lower())
        if kind == 'AddField' and keywords is not None:  # (model, field) -> its column, for the unique-index rule
            model, name = _literal(keywords.get('model_name')), _literal(keywords.get('name'))
            field_kind, field = _call(keywords.get('field'))
            if (isinstance(model, str) and isinstance(name, str) and field is not None and field_kind != 'ManyToManyField'
                    and _literal(field.get('null')) is True and 'db_default' not in field and 'db_column' not in field):
                nullable[(model.lower(), name)] = f'{name}_id' if field_kind in ('ForeignKey', 'OneToOneField') else name
        if kind == 'RunSQL' and keywords is not None:
            for statement in _statements(keywords.get('sql')) or ():
                match = SET_DEFAULT_RE.fullmatch(statement)
                if match:
                    defaults.add((match.group(1).lower(), match.group(2).lower()))
    why, unsafe = [], []
    for kind, keywords in operations:
        if keywords is None:
            unsafe.append(f'{kind or "an operation"} whose arguments are not keywords this check reads')
        elif kind == 'CreateModel':
            why.append(f'{_literal(keywords.get("name"))}: a new table no older revision reads')
        elif kind == 'AddField':
            model, name = _literal(keywords.get('model_name')), _literal(keywords.get('name'))
            field_kind, field = _call(keywords.get('field'))
            if not (isinstance(model, str) and isinstance(name, str)) or field_kind is None or field is None:
                unsafe.append('AddField whose model, name or field this check cannot read')
                continue
            label, column = f'{model}.{name}', name
            if 'db_column' in field:
                column = _literal(field['db_column'])
            elif field_kind in ('ForeignKey', 'OneToOneField'):
                column = f'{name}_id'
            sql_default = isinstance(column, str) and (f'studio_{model.lower()}', column.lower()) in defaults
            if model.lower() in created:
                why.append(f'{label}: a column of a table this migration creates')
            elif field_kind == 'ManyToManyField':
                unsafe.append(f'{label}: a many-to-many field, which this check does not read')
            elif _unique_field(field_kind, field) and (
                    _literal(field.get('null')) is not True or 'db_default' in field or sql_default):
                unsafe.append(f'{label}: a unique column added to an existing table that is NOT NULL or has a '
                              'database default: an older pair\'s insert names no value for it, so it is refused, or '
                              'gets the one default and its second insert is refused')
            elif _unique_field(field_kind, field):
                why.append(f'{label}: a nullable unique column with no database default: an older pair leaves it '
                           'NULL, which no unique constraint refuses')
            elif _literal(field.get('null')) is True:
                why.append(f'{label}: nullable')
            elif 'db_default' in field:
                why.append(f'{label}: NOT NULL with a database default (db_default)')
            elif sql_default:
                why.append(f'{label}: NOT NULL, given a database default by this migration\'s SQL')
            else:
                unsafe.append(f'{label}: NOT NULL with no database default, so an older pair\'s insert is refused')
        elif kind == 'AddIndex':
            model, index = _literal(keywords.get('model_name')), keywords.get('index')
            index_class = _dotted(index.func, imports) if isinstance(index, ast.Call) else None
            _, index_keywords = _call(index)
            if index_class in NON_UNIQUE_INDEXES:
                why.append(f'{model}: an index (writes are not refused)')
            elif isinstance(model, str) and model.lower() in created and index_class is not None:
                why.append(f'{model}: an index on a table this migration creates')
            elif index_class in UNIQUE_INDEXES and isinstance(model, str) and index_keywords is not None:
                fields = _literal(index_keywords.get('fields'))
                column = _not_null_condition(index_keywords.get('condition'), imports)
                added = nullable.get((model.lower(), column)) if column else None
                if (added and isinstance(fields, (list, tuple)) and column in fields
                        and (f'studio_{model.lower()}', added.lower()) not in defaults):
                    why.append(f'{model}: a unique index only over rows whose {column} is set, a column this migration '
                               'adds as nullable: an older pair leaves it NULL, so none of its writes is refused')
                else:
                    unsafe.append(f'{model}: a unique index on an existing table that is not partial over a column '
                                  'this migration adds as nullable, which can refuse an older pair\'s rows')
            else:
                unsafe.append(f'{model}: an index of a class this check does not read ({index_class or "unread"}), '
                              'which may be unique and refuse an older pair\'s rows')
        elif kind == 'AddConstraint':
            model = _literal(keywords.get('model_name'))
            if isinstance(model, str) and model.lower() in created:
                why.append(f'{model}: a constraint on a table this migration creates')
            else:
                unsafe.append(f'{model}: a constraint on an existing table, which can refuse an older pair\'s rows')
        elif kind == 'RunSQL':
            statements = _statements(keywords.get('sql'))
            if statements and all(SET_DEFAULT_RE.fullmatch(statement) for statement in statements):
                why.append(f'SQL that only sets column defaults ({len(statements)} statement(s))')
            else:
                unsafe.append('SQL other than ALTER TABLE ... ALTER COLUMN ... SET DEFAULT')
        else:
            unsafe.append(f'{kind or "an operation"}: not an additive operation this check reads')
    return {'safe': not unsafe, 'why': unsafe or why}


def migration_safety(directory: Path) -> dict:
    """{migration name: migration_verdict} for every migration in ``directory`` after ROLLING_BASELINE; a file there
    that is not a migration (or __init__.py) is refused, never skipped."""
    verdicts = {}
    for path in sorted(directory.iterdir()):
        if path.name == '__init__.py' or path.name == '__pycache__':
            continue
        match = MIGRATION_FILE_RE.fullmatch(path.name)
        if not match or not path.is_file() or path.is_symlink():
            verdicts[path.name] = {'safe': False, 'why': ['not a migration file this check reads']}
        elif int(match.group(1)) > ROLLING_BASELINE:
            verdicts[path.stem] = migration_verdict(path.read_text(encoding='utf-8'))
    return verdicts


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
        # Refused before anything is built: the app phase would apply it while the previous pair runs, and a rollback
        # would leave an older pair on it (ROLLING_BASELINE).
        migrations = migration_safety(context / 'studio' / 'migrations')
        unsafe = {name: verdict['why'] for name, verdict in migrations.items() if not verdict['safe']}
        if unsafe:
            raise InstallError(f'{len(unsafe)} migration(s) after {ROLLING_BASELINE:04d} are not additive for a pair '
                               'that does not know them, so nothing was built: ' + '; '.join(
                                   f'{name}: {", ".join(reasons)}' for name, reasons in sorted(unsafe.items())) + '.',
                               details={'migrations': migrations})
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
            'migrations': {'baseline': f'{ROLLING_BASELINE:04d}', 'after_baseline': migrations},
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


def pair_modes(mode, participants=None, interpreter=None) -> str:
    """'provider live, astra disabled, fable live': how the pair was started; ', interpreter live' follows when the
    caller names the interpreter's mode (``interpreter``)."""
    return ', '.join([f'provider {mode}'] + [f'{name} {(participants or {}).get(name) or "disabled"}'
                                             for name in PARTICIPANTS]
                     + ([f'interpreter {interpreter}'] if interpreter is not None else []))


def after_swap_failure(image_id, mode, states, error, parked, participants=None, interpreter=None) -> str:
    """The receipt of an app phase stopped once its new pair runs (refutation p2, install2:2): whether the stored list
    states were recomputed (``states``, RECOMPUTE_STATES' answer, or None), what stopped it, and what is left to do."""
    cause = str(error) or type(error).__name__
    running = f'web and worker running {image_id[:19]} ({pair_modes(mode, participants, interpreter)}), but '
    back = 'or, to go back, run --phase rollback-app, then rename the parked pair back.'
    if states is None:
        if any((parked or {}).values()):
            return (running + f'the stored list states were not recomputed ({cause}) and the previous pair is still '
                    'parked (*-previous): remove it by hand, then rerun --phase app, which recomputes them; ' + back)
        return running + f'the stored list states were not recomputed ({cause}): rerun --phase app.'
    return (running + f'the stored list states were recomputed ({len(states.get("changed") or {})} changed) and the '
            f'previous pair (*-previous) could not be removed ({cause}): remove what is left of it by hand; ' + back)


def access_receipt(stdout: bytes):
    """The access check's JSON receipt - its whole stdout, else its last non-empty line - as a JSON object, or None."""
    text = stdout.decode('utf-8', 'replace').strip()
    for candidate in (text, text.splitlines()[-1] if text else ''):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def participant_access_check(ctx, image_id, env_bytes, name, authorization_ref) -> dict:
    """``manage participant_access_check --participant <name>`` sends real requests to the participant's vendor
    ('corti', 'astra' or 'fable'): one coding request for Corti, after its OAuth token request, and for Astra or Fable one
    run of the pipeline's tool loop, one request
    per exchange and at most PARTICIPANT_MAX_EXCHANGES. So it runs only with --access-check, once the new pair runs. A one-shot with the
    worker's mount and network for that participant: its credentials file read-only at the worker's path and
    cpt-studio-net, that participant live under the authorization the worker has, every other one disabled. What the
    container wrote is recorded (its JSON receipt here; its stdout and the last 8 KiB of its stderr in a log) only once
    a root helper found no credential value in it (credential_free). {ok, exit, recorded, receipt, log, problem}.

    A check that exits non-zero is reported by what its output says (refutation round 5, sends-1), never by its exit
    status alone and never with a cause the installer does not know: its receipt's error, else the last non-empty line
    of its stderr, each scanned with the rest and repeated only whole and only up to 300 characters (otherwise named,
    never cut). Only the end of stderr is kept and scanned, so a line that began before it is never taken for a whole
    one."""
    if name == 'corti':
        environment = runtime_env('live', authorization_ref, credentials=True)
        files = {'credentials': True}
    else:
        environment = runtime_env('disabled', authorization_ref, participants={name: 'live'})
        files = {'participant_files': (name,)}
    try:
        result = oneshot(image_id, ['manage', 'participant_access_check', '--participant', name], env_bytes,
                         network=NETWORK, environment=environment, timeout=ACCESS_CHECK_SECONDS, **files)
    except InstallError as error:  # it did not finish: whether its request reached the vendor is not known
        return {'ok': False, 'recorded': False, 'problem': f'{error} Whether its request reached the vendor is not '
                                                           'known; nothing it wrote was recorded.'}
    stdout, stderr = result.stdout, result.stderr[-8192:]
    entry = {'ok': False, 'exit': result.returncode, 'recorded': False}
    if len(stdout) > ACCESS_CHECK_OUTPUT_LIMIT:
        return {**entry, 'problem': f'it wrote more than {ACCESS_CHECK_OUTPUT_LIMIT} bytes; nothing it wrote was '
                                    'recorded.'}
    if not credential_free([stdout, stderr], [name]):
        return {**entry, 'problem': 'what it wrote carries a value from its credentials file, or that could not be '
                                    'told; nothing it wrote was recorded.'}
    receipt = access_receipt(stdout)
    entry.update(recorded=True, receipt=receipt, log=ctx.log(f'access-check-{name}', stdout + stderr))
    if result.returncode:
        limit = 300
        error = receipt.get('error') if receipt is not None else None
        error = error.strip() if isinstance(error, str) else ''
        pieces = stderr.decode('utf-8', 'replace').split('\n')
        cut = len(result.stderr) > len(stderr)
        if cut and result.stderr[-len(stderr) - 1:-len(stderr)] != b'\n':
            pieces = pieces[1:]  # the end of a line that began before what was kept: never taken for a whole line
        lines = [piece.strip() for piece in pieces if piece.strip()]
        if error:
            said = (f'its receipt says: {error}' if len(error) <= limit
                    else f"its receipt's error is longer than {limit} characters, so it is not repeated here.")
        elif lines:
            said = (f'the last line of text on its stderr says: {lines[-1]}' if len(lines[-1]) <= limit
                    else f'the last line of text on its stderr is longer than {limit} characters, so it is not '
                         'repeated here.')
        elif cut:
            said = 'only the end of its stderr was kept, with no whole line of text in it, so no line is repeated here.'
        else:
            said = ('there is no text on its stderr.' if receipt is not None
                    else 'there is no JSON receipt and no text on its stderr.')
        entry['problem'] = f'it exited {result.returncode}, and {said}'
    elif receipt is None:
        entry['problem'] = 'its output was not one JSON receipt.'
    else:
        entry['ok'] = True
    return entry


def access_check_failure(image_id, mode, participants, states, checks, error=None) -> str:
    """The receipt of an app phase whose pair is installed and whose access check did not pass, or stopped. A check
    that did not pass is named with what its output says (participant_access_check's problem), and no cause is added
    to it (refutation round 5, sends-1: every failure was told to fix the credentials or the vendor account, beside a
    receipt recording that the vendor had answered and CPT Studio had stopped the loop, or a refusal that sent
    nothing)."""
    done = f'web and worker running {image_id[:19]} ({pair_modes(mode, participants)}), the stored list states ' \
           f'recomputed ({len((states or {}).get("changed") or {})} changed) and the previous pair removed, but '
    if error is not None:
        cause = str(error) or type(error).__name__
        return (done + f'the access check stopped ({cause}) after {", ".join(checks) or "none"}: the pair stays '
                'installed; run --phase app again with --access-check to check again.')
    failed = {name: check.get('problem', '') for name, check in checks.items() if not check.get('ok')}
    return (done + 'the access check did not pass for ' + '; '.join(f'{name} ({problem})'
                                                                  for name, problem in failed.items())
            + ' The pair stays installed with those participants live. Under access_checks, this phase\'s receipt '
              'records each check and, where what it wrote was recorded, its JSON receipt (if it wrote one) and the '
              'path of its log. Once the cause is known, run --phase app again with --access-check, or install with '
              'that participant disabled.')


def check_credential_files(mode, live, interpreter='disabled'):
    """Every credentials file a live provider, participant or interpreter needs, before anything changes: a missing
    participant source leaves no file, and that participant is installed disabled or not at all (HARNESS.md 8); a live
    interpreter needs the file the secrets phase copied (design/FINAL.md 13)."""
    wanted = (([CORTI_TARGET] if mode == 'live' else []) + [PARTICIPANTS[name]['target'] for name in live]
              + ([INTERPRETER['target']] if interpreter == 'live' else []))
    found = helper_stat(wanted) if wanted else {}
    if mode == 'live':
        target = found[CORTI_TARGET]
        if target != {'exists': True, 'kind': 'file', 'uid': APP_UID, 'gid': APP_UID, 'mode': '0o400'}:
            raise InstallError(f'{CORTI_TARGET} is not the {APP_UID}:{APP_UID} 0400 file the secrets phase writes.')
    for name in live:
        spec = PARTICIPANTS[name]
        if found[spec['target']] != {'exists': True, 'kind': 'file', 'uid': APP_UID, 'gid': APP_UID, 'mode': '0o400'}:
            raise InstallError(f'--{name}-mode live: {spec["target"]} is not the {APP_UID}:{APP_UID} 0400 file the '
                               f'secrets phase copies from {spec["source"]}; nothing was changed. Place the source and '
                               f'run --phase secrets, or install with --{name}-mode disabled.')
    if interpreter == 'live' and found[INTERPRETER['target']] != {'exists': True, 'kind': 'file', 'uid': APP_UID,
                                                                  'gid': APP_UID, 'mode': '0o400'}:
        raise InstallError(f'--interpreter-mode live: {INTERPRETER["target"]} is not the {APP_UID}:{APP_UID} 0400 file '
                           f'the secrets phase copies from {INTERPRETER["source"]}; nothing was changed. Place the '
                           'source and run --phase secrets first.')


def check_credential_parsing(image_id, env, mode, live, interpreter='disabled'):
    """The application's own loaders read each live credentials file in ``image_id``, in the worker's mount layout,
    with no network: format and permissions only, before anything changes."""
    if mode == 'live':
        # The application's own loader, in the worker's mount layout, with no network: format only.
        parsed = oneshot(image_id, ['manage', 'shell', '-c', CREDENTIALS_CHECK], env, network='none',
                         credentials=True, timeout=120)
        if parsed.returncode or b'corti-credentials-parse-ok' not in parsed.stdout:
            raise InstallError('The application cannot load the Corti credentials file as mounted for the worker '
                               '(format and permissions only; nothing was sent).', output=parsed.stderr[-2048:])
    for name in live:
        # Likewise each live participant's (studio.participants.credentials). Its error is kept only once a root helper
        # found no value from the file in it.
        parsed = oneshot(image_id, ['manage', 'shell', '-c', PARTICIPANT_CREDENTIALS_CHECKS[name]], env,
                         network='none', participant_files=(name,), timeout=120)
        if parsed.returncode or f'{name}-credentials-parse-ok'.encode() not in parsed.stdout:
            output = parsed.stderr[-2048:]
            raise InstallError(f'The application cannot load {PARTICIPANTS[name]["target"]} as mounted for the worker '
                               f'(--{name}-mode live; format and permissions only; nothing was sent or changed).',
                               output=output if credential_free([output], [name]) else b'')
    if interpreter == 'live':
        # And the live interpreter's (design/FINAL.md 13): its own loader, the interpreter itself disabled; its error is
        # kept only once a root helper found no value from the file in it.
        parsed = oneshot(image_id, ['manage', 'shell', '-c', INTERPRETER_CREDENTIALS_CHECK], env, network='none',
                         interpreter_file=True, timeout=120)
        if parsed.returncode or f'{INTERPRETER["name"]}-credentials-parse-ok'.encode() not in parsed.stdout:
            output = parsed.stderr[-2048:]
            raise InstallError(f'The application cannot load {INTERPRETER["target"]} as mounted for the worker '
                               '(--interpreter-mode live; format and permissions only; nothing was sent or changed).',
                               output=output if credential_free([output], [INTERPRETER['name']]) else b'')


def phase_app(ctx) -> dict:
    mode, reference = ctx.args.provider_mode, ctx.args.authorization_ref or ''
    modes = participant_modes(ctx.args)
    live = [name for name in PARTICIPANTS if modes[name] == 'live']
    interpreter = interpreter_mode(ctx.args)  # design/FINAL.md 13: --interpreter-mode; disabled when not given
    access = bool(getattr(ctx.args, 'access_check', None))
    if reference and run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{ctx.revision}:{reference}'],
                         check=False).returncode:
        raise InstallError('--authorization-ref is not a file tracked at the revision.')
    image_id = installed_image(ctx)
    require_db()
    check_credential_files(mode, live, interpreter)
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    check_credential_parsing(image_id, env, mode, live, interpreter)
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
    # The interpreter's mode is named only when it is not the default, as swap_services leaves WEB_PORT to
    # wait_service: a stand-in of replace_services keeps the six arguments it always had.
    services = replace_services(ctx, image_id, env, mode, reference, modes,
                                **({'interpreter': interpreter} if interpreter != 'disabled' else {}))
    # ADJUDICATION P-7: the verify one-shot counts legacy-engine assessments made since the NEW WORKER started - S4 of a
    # blue/green switch, the worker's start of a swap - never since the install began (until S2 the old worker runs).
    # 'given': whether --interpreter-mode was given at all - verify reports an interpreter left disabled only because it
    # was not (the review of S14, finding 2: FINAL 13's install is live, and a disabled mode pauses every upload's
    # reading, 11.2).
    steps = services.get('steps') if isinstance(services.get('steps'), dict) else {}
    interpreting = {'mode': interpreter, 'given': getattr(ctx.args, 'interpreter_mode', None) is not None,
                    'credentials_loaded': interpreter == 'live',
                    'worker_started_at': steps.get('S4') or services.get('worker_started_at')}
    # Refutation p1, migrate-2: the stored list states are recomputed with this revision's derivation (RECOMPUTE_STATES)
    # - once this pair has replaced the old one, never before, so a failure path restores the old pair over the states
    # it derived. Blue/green (I-state): only once the drained old web has stopped too (switch_services' S5). Nothing is refused for it (round-7c8 skeptic, sk:2: refusing while an outcome was unknown also refused
    # a same-revision re-run - a provider-mode switch during an incident - and the reinstall the failure path's receipt
    # asks for, until a member reconciled on the running web: a released, paid send, and on a restored older web one
    # its own rules make). Nothing is sent.
    # Refutation p2, install2:2: and before the parked pair is removed (retire_parked), so the documented recovery for a
    # parked pair left in place (a `docker rm` that fails, an installer interrupted) finds them recomputed; whatever
    # stops this phase once the new pair runs - the recompute, the removal, a Ctrl-C - leaves a receipt that says
    # whether they were, and what is left to do.
    states, parked = None, services.get('replaced')
    if isinstance(services.get('steps'), dict):
        services['steps']['S6'] = utc_now_ms()  # blue/green: the recompute and the removal of the parked pair
    try:
        states = app_script(image_id, env, RECOMPUTE_STATES, {}, what='Recomputing the stored list states')
        retire_parked(parked)
    except BaseException as error:  # noqa: BLE001 — the pair is installed: the receipt says what is left to do
        raise InstallError(after_swap_failure(image_id, mode, states, error, parked, modes, interpreter),
                           details={**services, 'states_recomputed': states, 'interpreter': interpreting}) from error
    # Opt-in, last: each live participant - Corti too, when the provider is live (checklist 1.3: all three) - is
    # checked once with real requests (participant_access_check), never without the flag.
    checks, checked = None, (['corti'] if mode == 'live' else []) + live
    if access:
        checks = {}
        try:
            for name in checked:
                checks[name] = participant_access_check(ctx, image_id, env, name, reference)
        except BaseException as error:  # noqa: BLE001 — the pair is installed: the receipt says what is left to do
            raise InstallError(access_check_failure(image_id, mode, modes, states, checks, error),
                               details={**services, 'states_recomputed': states, 'access_checks': checks}) from error
        if not all(check['ok'] for check in checks.values()):
            raise InstallError(access_check_failure(image_id, mode, modes, states, checks),
                               details={**services, 'states_recomputed': states, 'access_checks': checks})
    return {'image_id': image_id, 'provider_mode': mode, 'authorization_ref': reference, 'participants': modes,
            'participant_credentials_loaded': live, 'migrate_log': migrate_log, 'unrunnable_stages': unrunnable,
            'states_recomputed': states, 'access_checks': checks if access else 'not run (no --access-check)',
            **services, 'interpreter': interpreting,
            'summary': f'web and worker running {image_id[:19]} ({pair_modes(mode, modes, interpreter)})'
                       + switched_summary(services)
                       + (f'; access checked: {", ".join(checked)}' if access else '')}


def switched_summary(services) -> str:
    """'; switched blue/green 9150 -> 9151: 812 availability samples, 0 not 200' for a blue/green replacement."""
    if services.get('mode') != 'blue-green':
        return ''
    availability = services.get('availability') or {}
    return (f'; switched blue/green {services["ports"]["from"]} -> {services["ports"]["to"]}: '
            f'{availability.get("samples", 0)} availability samples, {availability.get("non_200_count", 0)} not 200')


def phase_switch_back(ctx) -> dict:
    """Post-success rollback without interruption (ops/INSTALL.md, switch-back): back to the pair this revision's last
    successful app phase replaced (its receipt's 'replaced': the previous web's image and revision - images are never
    removed), by the blue/green switch in reverse. rollback-app's checks run first and refuse, stopping nothing, while
    this revision recorded what an older revision would act on, or show, wrongly (undo_hazards). ``--provider-mode``,
    the participant modes and ``--interpreter-mode`` are the previous pair's, as its own app phase was given them (a
    revision before the Gemini migration has no interpreter: leave it disabled). What this revision made from event
    inventories is never a refusing reason: the receipt declares it in a note and the switch goes on (ADJUDICATION
    P-1)."""
    mode, reference = ctx.args.provider_mode, ctx.args.authorization_ref or ''
    modes = participant_modes(ctx.args)
    live = [name for name in PARTICIPANTS if modes[name] == 'live']
    interpreter = interpreter_mode(ctx.args)
    app = require_receipt(ctx, 'app')
    previous = ((app.get('details') or {}).get('replaced') or {}).get('web') or {}
    prev_image, prev_revision = previous.get('image'), previous.get('revision')
    if not (isinstance(prev_image, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', prev_image)
            and isinstance(prev_revision, str) and SHA_RE.fullmatch(prev_revision)):
        raise InstallError("This revision's app receipt names no previous web (image and revision) to switch back to; "
                           'nothing was changed.')
    if prev_revision == ctx.revision:
        raise InstallError('The pair the app phase replaced is this same revision: there is nothing to switch back to.')
    if reference and run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{prev_revision}:{reference}'],
                         check=False).returncode:
        raise InstallError('--authorization-ref is not a file tracked at the previous revision.')
    image = inspect('image', prev_image)
    if image is None or labels_of(image).get(REVISION_LABEL) != prev_revision or not owned(image, 'app-image'):
        raise InstallError(f'The previous image {prev_image[:19]} is not present with revision {prev_revision[:12]} and '
                           'the CPT Studio label; nothing was changed.')
    image_id = installed_image(ctx)
    require_db()
    plan = replacement_plan(ctx)
    if plan['mode'] != 'blue-green' or plan['web']['revision'] != ctx.revision or plan['web']['image'] != image_id:
        raise InstallError(f'The site is not served by this revision\'s web through its HTTPS stage, so there is '
                           'nothing to switch back from; nothing was changed.', details={'plan': plan})
    preflight = require_receipt(ctx, 'preflight')
    check_credential_files(mode, live, interpreter)
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    check_credential_parsing(prev_image, env, mode, live, interpreter)
    hazards = undo_hazards(image_id, env, ctx.revision)
    if hazards:
        raise InstallError(f'{hazard_summary(hazards)} hold records an older revision would act on, or show, wrongly '
                           'under its own rules; nothing was started or stopped. Clear them on this revision\'s web '
                           '(ops/INSTALL.md, Reinstalling an older revision), then rerun --phase switch-back.',
                           details={'hazards': hazards})
    services = switch_back_services(ctx, image_id, env, prev_image, prev_revision, mode, reference, modes,
                                    preflight=preflight, plan=plan, interpreter=interpreter)
    availability = services.get('availability') or {}
    note = (services.get('interpretation') or {}).get('note')
    return {'image_id': image_id, 'previous': {'image': prev_image, 'revision': prev_revision},
            'provider_mode': mode, 'authorization_ref': reference, 'participants': modes,
            'interpreter_mode': interpreter, **services,
            'summary': f'switched back to {prev_revision[:12]} ({pair_modes(mode, modes, interpreter)}) on '
                       f'{plan["idle"]}: {availability.get("samples", 0)} availability samples, '
                       f'{availability.get("non_200_count", 0)} not 200' + (f'; {note}' if note else '')}


def switch_back_services(ctx, image_id, env_bytes, prev_image, prev_revision, provider_mode, authorization_ref,
                         participants, *, preflight, plan, interpreter=None) -> dict:
    """The switch in reverse, never stopping the serving web first:

      B2  start the previous revision's web, INCOMING_WEB, on the idle port; health_ok for ITS revision; smoke_web
      B3  park this revision's worker (its current stage finishes)
      B4  read again that co-tenant routing and app.quillmd.com answer as the preflight baseline (the switch is verified
          against it) and that this revision recorded nothing an older revision would act on, or show, wrongly - so
          nothing is closed for a switch that cannot pass (refutation r2, L6-4) - then close every stage this
          revision's pair queued, ran or left resumable since it was created, and every open stage of a kind the
          previous worker does not run (close_undone_stages, rollback-app's rule); refuse to go on while the close
          names a record; put back the list states the previous revision labels otherwise; count what this revision
          made from event inventories, the receipt's declared note, which never refuses (ADJUDICATION P-1)
      B5  switch the vhost's upstream to the idle port (/health/ = the previous revision through the public path)
      B6  drain this revision's web, stop it and park it; the previous web takes the canonical name
      B7  close again what this revision's web started between B4 and the end of its drain (requests it accepted
          before the switch); this also closes what a member started on the previous web during that window
          (ops/INSTALL.md, Known limits); put back again; hold the previous worker while the close names a record
      B8  start the previous worker
      B9  remove this revision's parked pair (its image is kept)
    The baseline is read before anything starts too. Before B5 every failure resumes this revision's pair; from B5 on
    the previous web serves and the receipt says what is left."""
    live, idle = plan['live'], plan['idle']
    current = {role: inspect('container', SERVICES[role]) for role in SERVICES}
    since = min(created_at(container) for container in current.values() if container is not None)
    kinds = stage_kinds_of(prev_image, env_bytes)
    reason = f'revision {ctx.revision[:12]} was switched back to {prev_revision[:12]} (switch-back)'
    drifted = ingress_checks(ctx, preflight)
    if drifted:
        raise InstallError(baseline_problem(drifted, 'nothing was started or stopped'), details={'baseline': drifted})
    steps, parked, started, progress, closes, put_back = {}, {}, {}, {}, {}, []
    record = {'mode': 'switch-back', 'ports': {'from': live, 'to': idle}, 'steps': steps, 'closes': closes,
              'states_put_back': put_back, 'since': since.isoformat()}
    reached = [None]

    def step(name):
        reached[0] = name
        steps[name] = utc_now_ms()

    def refuse_on_hazards(closed, when, checked):
        hazards = closed.get('hazards') if isinstance(closed, dict) else None
        if not isinstance(hazards, dict) or hazards:
            named = hazard_summary(hazards) if isinstance(hazards, dict) else 'the close did not say which encounters'
            written = ({pk: [r for r in reasons if r in WEB_WRITTEN_HAZARDS] for pk, reasons in hazards.items()}
                       if isinstance(hazards, dict) else {})
            written = {pk: reasons for pk, reasons in written.items() if reasons}
            # refutation r3, D-2: which web wrote them cannot be read - the previous web writes them too when it is a
            # revision since the core repair - but none stood at B4's own check (``checked``), so they were written since
            raise InstallError(f'{when}, {named} hold records the previous revision would act on, or show, wrongly '
                               'under its own rules' + (
                                   f' ({hazard_summary(written)}: a member\'s answer or a chosen modifier, written since '
                                   f'this switch-back read none standing ({checked.isoformat()}): a revision before the '
                                   'core repair shows them wrongly; run --phase app again to come back to this revision, '
                                   'whose web shows them as they are)' if written else ''), details={'hazards': hazards})
    recorder = AvailabilityRecorder().start()
    try:
        step('B2')
        docker('run', '-d', *service_args('web', prev_image, prev_revision, provider_mode, authorization_ref,
                                          participants, name=INCOMING_WEB, port=idle, interpreter=interpreter),
               input=env_bytes, quiet=True)
        started['web'] = wait_service('web', prev_revision, prev_image, name=INCOMING_WEB, port=idle)
        record['smoke'] = smoke_web(idle)
        step('B3')
        parked['worker'] = park('worker')
        step('B4')
        drifted = ingress_checks(ctx, preflight)
        if drifted:
            raise InstallError(baseline_problem(drifted, 'nothing was closed or switched'),
                               details={'baseline': drifted})
        checked = dt.datetime.now(dt.timezone.utc)
        hazards = undo_hazards(image_id, env_bytes, ctx.revision)
        if hazards:
            raise InstallError(f'before anything was closed, {hazard_summary(hazards)} hold records an older revision '
                               'would act on, or show, wrongly under its own rules', details={'hazards': hazards})
        first = dt.datetime.now(dt.timezone.utc)
        # refutation r3, D-5: the close may take effect whatever its call then answers (CLOSE_STAGES commits, then reads
        # every encounter), so the undo is told it started
        closes['first_started_at'] = first.isoformat()
        closes['first'] = close_undone_stages(image_id, env_bytes, since, ctx.revision, reason, kinds)
        refuse_on_hazards(closes['first'], 'after this revision\'s worker stopped and its stages were closed', checked)
        put_back.append(put_back_states(closes['first'], prev_image, image_id, env_bytes))
        # ADJUDICATION P-1: no worker of this revision runs from B3 on, so this is what the previous image is handed
        record['interpretation'] = interpretation_note(image_id, env_bytes, ctx.revision)
        step('B5')
        record['switch'] = switch_upstream(ctx, preflight, live, idle, revision=prev_revision, progress=progress,
                                           from_revision=ctx.revision)
        step('B6')
        record['drain'] = drain_web(live)
        parked['web'] = retire_live_web(plan['web']['id'])
        step('B7')
        closes['second'] = close_undone_stages(image_id, env_bytes, first, ctx.revision, reason, kinds)
        refuse_on_hazards(closes['second'], 'after the switch', checked)
        put_back.append(put_back_states(closes['second'], prev_image, image_id, env_bytes))
        step('B8')
        docker('run', '-d', *service_args('worker', prev_image, prev_revision, provider_mode, authorization_ref,
                                          participants, interpreter=interpreter), input=env_bytes, quiet=True)
        started['worker'] = wait_service('worker', prev_revision, prev_image)
        step('B9')
        retire_parked(parked)
        step('done')
        record['availability'] = recorder.stop()
    except BaseException as failure:
        try:
            message = undo_switch_back(ctx, failure, reached[0], image_id=image_id, env_bytes=env_bytes, plan=plan,
                                       parked=parked, progress=progress, put_back=put_back, closes=closes,
                                       prev_revision=prev_revision)
        except BaseException as second:  # noqa: BLE001 — the undo itself stopped: say so, with what is there now
            message = (f'{str(failure) or type(failure).__name__}; the undo at {reached[0]} stopped too '
                       f'({str(second) or type(second).__name__}): read "left" in this receipt, then ops/INSTALL.md, '
                       'Recovery notes')
        raise InstallError(message, details={**record, 'failed_at': reached[0], 'started': started, 'replaced': parked,
                                             'availability': stop_recorder(recorder),
                                             'left': left_summary()}) from failure
    return {'started': started, 'replaced': parked, **record}


def undo_switch_back(ctx, failure, reached, *, image_id, env_bytes, plan, parked, progress, put_back, closes=None,
                     prev_revision=None) -> str:
    """What a failed switch-back step leaves (ops/INSTALL.md, switch-back): before the switch, this revision's pair
    resumes (its worker put back and started, its list states recomputed with its own derivation when the previous
    ones were put back, the previous web drained when it may have taken traffic and removed - only once nginx is
    proven to run this revision's vhost again when a reload of the switched one was asked for, whatever it answered:
    refutation r2, L6-1; both webs are left running otherwise); from the switch on the previous web serves and nothing
    is undone."""
    cause = str(failure) or type(failure).__name__
    live, idle = plan['live'], plan['idle']
    web, worker = SERVICES['web'], SERVICES['worker']
    halfway = (f'so both webs were left running and this revision\'s worker parked ({worker}-previous): read "left" in '
               'this receipt, then ops/INSTALL.md, Recovery notes (a switch that stopped half way).')
    if reached in (None, 'B2'):
        log_tail(ctx, INCOMING_WEB, 'web', 'incoming-web-failed')
        return (f'{cause}; the previous revision\'s web ({INCOMING_WEB}, port {idle}) {remove_incoming_web()}, and '
                f'nothing else changed: {web} kept serving on {live} and its worker kept running.')
    if reached == 'B3':
        state = worker_after_failed_park()
        return (f'{cause}; this revision\'s worker is {state} and the previous revision\'s web ({INCOMING_WEB}) '
                f'{remove_incoming_web()}; {web} kept serving on {live}.')
    if reached in ('B4', 'B5'):
        switched_file = reached == 'B5' and progress.get('applied_at') is not None
        if switched_file and vhost_state()['file_sha256'] == sha256(rendered_vhosts(ctx.revision, idle)['https']
                                                                     .encode()):
            return (f'{cause}; quillmd-cpt still names the previous revision\'s web ({INCOMING_WEB}, port {idle}), '
                    + halfway)
        touched = reached == 'B5' and nginx_may_have_read(progress)
        notes = []
        if touched:
            settled = settle_vhost(ctx, port=live, revision=ctx.revision, other_revision=prev_revision or '')
            if not settled['proven']:
                return (f'{cause}; the vhost was put back, but nginx may still route to the previous revision\'s web '
                        f'({INCOMING_WEB}, port {idle}): a reload of the switched vhost was asked for, or nginx loaded '
                        f'one since it was written, and nginx was not proven to run this revision\'s again '
                        f'({settled.get("problem")}), ' + halfway)
            drain_web(idle)
        removed = remove_incoming_web()
        if put_back:  # once no previous-revision container runs (I-state), before this revision's worker resumes
            try:
                app_script(image_id, env_bytes, RECOMPUTE_STATES, {}, what='Recomputing the stored list states')
                notes.append('the list states were recomputed with this revision\'s derivation')
            except BaseException as error:  # noqa: BLE001
                notes.append(f'the list states put back to the previous revision\'s could not be recomputed ({error}): '
                             'rerun --phase app, which recomputes them')
        worker_note = restore_parked_worker(parked.get('worker'))
        closed = closes or {}
        if closed.get('first') is not None:
            closing = '. A stage the close already closed stays closed (failed, with the installer\'s note).'
        elif closed.get('first_started_at'):  # refutation r3, D-5: it was started, and may have committed
            closing = ('. The close was started and gave no answer, so it may have closed some or all of this '
                       'revision\'s open stages before it stopped: a stage it closed stays closed (failed, with the '
                       'installer\'s note).')
        else:
            closing = '. Nothing was closed.'
        return (f'{cause}; nothing was switched: {web} kept serving on {live}, this revision\'s worker was '
                f'{worker_note} and the previous revision\'s web ({INCOMING_WEB}) {removed}'
                + (f'; {"; ".join(notes)}' if notes else '') + closing)
    if reached == 'B8':
        log_tail(ctx, worker, 'worker', 'worker-failed')
        stop_service_container(worker, 'worker')
    return (f'{cause}; the previous revision\'s web serves on {idle} and nothing was undone, but '
            + {'B6': 'this revision\'s web was not retired and no worker runs',
               'B7': 'the previous revision\'s worker was not started, so nothing is processed',
               'B8': 'the previous revision\'s worker did not become ready and was stopped, so nothing is processed',
               'B9': 'this revision\'s parked pair could not be removed',
               'done': 'its availability record could not be read'}.get(reached, 'the switch-back did not finish')
            + ': read "left" in this receipt, then ops/INSTALL.md, Recovery notes.')


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


def passage_files(revision) -> dict:
    """{path under studio/reference/data/: git blob id} of every file the revision commits there - what its image ships,
    built from git archive of the revision. A link or a submodule there is refused, never skipped."""
    listing = run(['git', '-C', str(ROOT), 'ls-tree', '-r', '-z', '--full-tree', revision, '--', f'{PASSAGE_DATA}/'],
                  timeout=60).stdout.decode('utf-8')
    files = {}
    for entry in filter(None, listing.split('\0')):
        meta, _, path = entry.partition('\t')
        mode, kind, blob = meta.split()
        relative = PurePosixPath(path).relative_to(PASSAGE_DATA).as_posix()
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise InstallError(f'{path} is not a regular file at the revision; refusing to import passages.')
        files[relative] = blob
    return dict(sorted(files.items()))


def phase_passages(ctx) -> dict:
    """After migrate (the app phase): each CMS passage file the revision commits under studio/reference/data/ - shipped
    in its image - imported by the application's own importer, one file per one-shot (HARNESS.md 5). The importer is
    idempotent, so this phase is too: a file already loaded changes nothing, and its output says so."""
    image_id = installed_image(ctx)
    require_db()
    files = passage_files(ctx.revision)
    if not files:
        raise InstallError(f'The revision commits no file under {PASSAGE_DATA}/; there is nothing to import.')
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    # The passage tables are this revision's (migration 0007): every migration it has must be applied first.
    pending = oneshot(image_id, ['manage', 'migrate', '--check'], env, timeout=120)
    if pending.returncode:
        raise InstallError(f'This revision\'s migrations are not all applied (manage migrate --check exited '
                           f'{pending.returncode}): run --phase app first. Nothing was imported.')
    results = {}
    for number, (relative, blob) in enumerate(files.items(), start=1):
        command = ['manage', 'import_passages', '--data', f'{PASSAGE_DATA_IN_IMAGE}/{relative}']
        imported = oneshot(image_id, command, env)
        log = ctx.log(f'passages-{number:02d}', imported.stdout + imported.stderr)
        if imported.returncode:
            raise InstallError(f'import_passages {relative} failed (exit {imported.returncode}); see {log}. Files '
                               'imported before it stay imported (a rerun leaves them as they are).',
                               details={'imported': results, 'failed': relative})
        results[relative] = {'git_blob': blob, 'log': log,
                             'output': imported.stdout.decode('utf-8', 'replace').strip()[-4000:]}
    return {'files': results, 'summary': f'passages imported from {len(results)} file(s); the importer is idempotent'}


LICENSE_NOTE_COUNTS = ('old', 'new', 'other')
LICENSE_NOTE_ANSWER = ('rows', 'before', 'after', 'updated', 'updated_keys', 'other_keys', 'assessments_with_old_note')


def license_note_problem(answer) -> str:
    """'' when LICENSE_NOTE_FIX's answer adds up - exactly the old notes became the new one and every other count stayed
    - else what does not. An answer that is not the counts this phase reads is never read as 'nothing to correct'."""
    try:
        before, after, updated, rows = answer['before'], answer['after'], answer['updated'], answer['rows']
        shaped = (set(answer) >= set(LICENSE_NOTE_ANSWER) and set(before) == set(after) == set(LICENSE_NOTE_COUNTS)
                  and all(type(value) is int for value in (*before.values(), *after.values(), updated, rows,
                                                            answer['assessments_with_old_note']))
                  and all(isinstance(answer[name], list) and all(isinstance(key, str) for key in answer[name])
                          for name in ('updated_keys', 'other_keys')))
    except (KeyError, TypeError, AttributeError):
        shaped = False
    if not shaped:
        return 'its answer is not the counts this phase reads'
    if (updated != before['old'] or len(answer['updated_keys']) != updated
            or after != {'old': 0, 'new': before['new'] + updated, 'other': before['other']}
            or not rows == sum(before.values()) == sum(after.values())
            or len(answer['other_keys']) != after['other']):
        return f'its counts do not add up (before {before}, after {after}, {updated} updated of {rows} row(s))'
    return ''


def phase_license_note(ctx) -> dict:
    """After app (and reference): CPT Studio's own licence note on the CMS reference sources already imported, corrected
    in place (owner, 2026-11-01; HARNESS.md 11.6) by LICENSE_NOTE_FIX in a one-shot of this revision's image, as the
    passages phase runs its importer. Exactly LICENSE_NOTE_OLD becomes exactly LICENSE_NOTE_NEW; nothing else changes.
    Idempotent: with no row left holding the old note it changes nothing, and its receipt says so."""
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    # The image's models must be the schema's, as for the passages phase: every migration this revision has applied.
    pending = oneshot(image_id, ['manage', 'migrate', '--check'], env, timeout=120)
    if pending.returncode:
        raise InstallError(f'This revision\'s migrations are not all applied (manage migrate --check exited '
                           f'{pending.returncode}): run --phase app first. Nothing was changed.')
    answer = app_script(image_id, env, LICENSE_NOTE_FIX, {'old': LICENSE_NOTE_OLD, 'new': LICENSE_NOTE_NEW},
                        what='Correcting the reference licence note')
    if isinstance(answer, dict) and 'refused' in answer:
        raise InstallError(f'{answer["refused"]}; nothing was changed. Install a revision whose importer writes the '
                           'corrected note, then run this phase.', details=answer)
    problem = license_note_problem(answer)
    if problem:
        raise InstallError(f'The licence note correction answered, but {problem}. Run --phase license-note again: it '
                           'changes nothing more and records the counts as they are.', details={'answer': answer})
    counts = {name: answer[name] for name in LICENSE_NOTE_ANSWER}
    summary = (f'licence note corrected on {counts["updated"]} reference source(s): {", ".join(counts["updated_keys"])}'
               if counts['updated'] else 'no reference source holds the old licence note; nothing changed')
    return {'image_id': image_id, 'old_note': LICENSE_NOTE_OLD, 'new_note': LICENSE_NOTE_NEW,
            'old_note_sha256': sha256(LICENSE_NOTE_OLD.encode()), 'new_note_sha256': sha256(LICENSE_NOTE_NEW.encode()),
            **counts, 'summary': summary}


def credentials_document(ctx, accounts) -> dict:
    return {'service': 'cpt-studio', 'url': f'https://{DOMAIN}/', 'synthetic_only': True,
            'workspace': ctx.args.workspace_name, 'revision': ctx.revision, 'created_at': utc_now(),
            'accounts': accounts}


def root_file(op, *, final=INITIAL_CREDENTIALS, staged=None, **params) -> dict:
    """H_ROOT_FILE on /etc/cpt-studio/``final`` (staged as '.<final>.new'): the initial credentials, or the operators
    phase's operator-credentials.json."""
    params.update(op=op, final=final, staged=staged or f'.{final}.new')
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


# The operators phase's in-image scripts (run by `manage shell -c` in this revision's image, as app_script runs them).
# OPERATOR_ACCOUNTS creates each platform-operator account with NO workspace membership - an operator's access is the
# grant alone (studio.operator), never a workspace role - or keeps it; it refuses, changing nothing, an account that
# exists with another actor kind or holds any membership (a member account is never made an operator by the installer).
# A password is set from its mounted RAM-only file when the account is created, or for every account with reset; no
# value is printed. One transaction: a refusal leaves every account as it was.
OPERATOR_ACCOUNTS = '''
from pathlib import Path
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from studio import models
done = {}
with transaction.atomic():
    for spec in P['accounts']:
        user = models.User.objects.select_for_update().filter(username=spec['username']).first()
        created = user is None
        if created:
            user = models.User(username=spec['username'], actor_kind=spec['kind'], display_name=spec['display_name'])
        elif user.actor_kind != spec['kind']:
            raise SystemExit('account ' + spec['username'] + ' exists with another actor kind; nothing was changed')
        elif user.memberships.exists():
            raise SystemExit('account ' + spec['username'] + ' holds a workspace membership, so the installer does '
                             'not make it an operator; nothing was changed')
        if created or P['reset']:
            password = Path(spec['password_file']).read_text(encoding='utf-8').strip()
            if not password:
                raise SystemExit('a password file is empty; nothing was changed')
            validate_password(password, user)
            user.set_password(password)
            user.save()
        done[spec['username']] = 'created' if created else ('reset' if P['reset'] else 'kept')
print(ANSWER + json.dumps({'accounts': done}))
'''
# Read back after the grants: each account an operator by studio.operator.is_operator (the grant, never a membership),
# with no membership, of its actor kind.
OPERATOR_CHECK = '''
from studio import models
from studio.operator import is_operator
found = {}
for username in P['usernames']:
    user = models.User.objects.get(username=username)
    found[username] = {'operator': bool(is_operator(user)), 'memberships': user.memberships.count(),
                       'actor_kind': user.actor_kind, 'active': user.is_active}
print(ANSWER + json.dumps({'accounts': found}))
'''
# The reassess phase's read of each named encounter's jobs, before and after `manage reassess_retained`.
REASSESS_JOBS = '''
from studio import models
found = {}
for pk in P['encounters']:
    encounter = models.Encounter.objects.filter(pk=pk).first()
    if encounter is None:
        found[pk] = None
        continue
    found[pk] = {'state': encounter.state,
                 'jobs': [[str(job.pk), job.kind, job.state, job.idempotency_key]
                          for job in models.Job.objects.filter(encounter_id=pk).order_by('created_at', 'pk')]}
print(ANSWER + json.dumps({'encounters': found}))
'''


def operator_document(ctx, username, kind, password) -> dict:
    """One operator account's login: top-level username and password (what the verification tools read)."""
    return {'service': 'cpt-studio', 'url': f'https://{DOMAIN}/', 'operator_url': f'https://{DOMAIN}/ops/',
            'synthetic_only': True, 'revision': ctx.revision, 'created_at': utc_now(), 'username': username,
            'password': password, 'actor_kind': kind, 'access': 'platform operator: an operator grant, no workspace '
                                                                'membership'}


def operator_granted_by() -> str:
    """Who records the operator grants (grant_operator --by): this installer and the host login that ran it. Passed
    explicitly (refutation r2, L6-2): the one-shot runs as this user's uid so it can read the 0600 reason file, and the
    image has no passwd entry for it, where the command's own default once looked the login up and failed."""
    try:
        login = getpass.getuser()
    except Exception:  # noqa: BLE001 — no passwd entry here either: the uid says who
        login = f'uid {os.getuid()}'
    return f'ops/install.py --phase operators ({login})'[:120]


def operator_reason(ctx, username, kind) -> str:
    return (f'Platform-operator diagnostics access for the CPT Studio {kind} account {username} (owner directive '
            '2026-11-03, section 2: operator diagnostics stay available to authenticated platform operators and are '
            'never conferred by a workspace role). Granted by ops/install.py --phase operators for revision '
            f'{ctx.revision} under the ruled-mutation declaration '
            f'{os.environ.get("RULED_MUTATION_DECLARATION", "")} ({os.environ.get("RULED_MUTATION_DECL_COMMIT", "")}).'
            '\n')


def phase_operators(ctx) -> dict:
    """The two platform-operator accounts (ops/INSTALL.md, operators): ops-agent, an automated agent (the verification
    tools' operator session), and platform-operator, a human - each with no workspace membership and an operator grant.
    Passwords are made and kept as the initial credentials are (phase_provision): generated here, travelling only as
    RAM-only files under /dev/shm into one-shots of this revision's image, never in argv, output or receipts. The agent's
    login is this user's 0600 OPS_AGENT_CREDENTIALS (top-level username and password); the human's is the root-only 0600
    /etc/cpt-studio/operator-credentials.json, written through the root helper. Both files are committed once the
    accounts hold their passwords; each account is then granted by the application's own command, `manage
    grant_operator --username U --reason-file F`, and read back (OPERATOR_CHECK): an operator, with no membership."""
    reset = bool(ctx.args.reset_passwords)
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    # Refutation r2, L6-2: the operator grant is this revision's table (migration 0010), so the phase refuses -
    # creating no account and no file - until the app phase has applied this revision's migrations.
    pending = oneshot(image_id, ['manage', 'migrate', '--check'], env, timeout=120)
    if pending.returncode:
        raise InstallError(f'This revision\'s migrations are not all applied (manage migrate --check exited '
                           f'{pending.returncode}): run --phase app first. No account or file was created.')
    names = {'final': OPERATOR_CREDENTIALS, 'staged': f'.{OPERATOR_CREDENTIALS}.new'}
    state = root_file('state', **names)
    agent_staged = OPS_AGENT_CREDENTIALS.with_name(f'.{OPS_AGENT_CREDENTIALS.name}.new')
    if state['staged_exists'] or agent_staged.exists():
        raise InstallError('Staged operator credentials from an interrupted run exist; resolve them by hand first.')
    if not reset and (state['final_exists'] or OPS_AGENT_CREDENTIALS.exists()):
        raise InstallError('Operator credentials files already exist; use --reset-passwords to rotate them.')
    spec = {username: (kind, display) for username, kind, display in OPERATOR_ACCOUNTS_SPEC}
    passwords = {username: secrets.token_urlsafe(24) for username in spec}
    documents = {username: json.dumps(operator_document(ctx, username, kind, passwords[username]), indent=2).encode()
                 for username, (kind, _) in spec.items()}
    agent = next(username for username, (kind, _) in spec.items() if kind == 'agent')
    human = next(username for username, (kind, _) in spec.items() if kind == 'human')
    OPS_AGENT_CREDENTIALS.parent.mkdir(mode=0o700, exist_ok=True)
    folder = OPS_AGENT_CREDENTIALS.parent.lstat()
    if not stat.S_ISDIR(folder.st_mode) or folder.st_uid != os.getuid() or stat.S_IMODE(folder.st_mode) != 0o700:
        raise InstallError(f'{OPS_AGENT_CREDENTIALS.parent} must be a directory owned by this user with mode 0700.')
    user = f'{os.getuid()}:{os.getgid()}'
    committed = False
    # Password and reason files live in RAM only (/dev/shm) and are wiped whatever happens.
    scratch = Path(tempfile.mkdtemp(prefix='cpt-studio-operators-', dir='/dev/shm'))
    try:
        root_file('stage', content=base64.b64encode(documents[human]).decode(), **names)
        write_private(agent_staged.parent, agent_staged.name, documents[agent])
        mounts, accounts = [], []
        for username, (kind, display) in spec.items():
            write_private(scratch, f'{username}.pw', passwords[username].encode())
            mounts.append(f'type=bind,src={scratch / (username + ".pw")},dst=/run/cpt-operators/{username}.pw,readonly')
            accounts.append({'username': username, 'kind': kind, 'display_name': display,
                             'password_file': f'/run/cpt-operators/{username}.pw'})
        try:
            answer = app_script(image_id, env, OPERATOR_ACCOUNTS, {'accounts': accounts, 'reset': reset},
                                what='Creating the operator accounts', mounts=mounts, user=user)
        except InstallError as error:
            assert_no_secret([error.output, str(error).encode()], passwords.values())
            raise
        outcome = answer.get('accounts') if isinstance(answer, dict) else None
        if not isinstance(outcome, dict) or sorted(outcome) != sorted(spec):
            raise InstallError('The operator accounts script did not name both accounts; nothing was saved.')
        if not reset and set(outcome.values()) != {'created'}:
            raise InstallError('An operator account already existed, so its password was not set; nothing was saved. '
                               'Rerun with --reset-passwords to rotate.', details={'accounts': outcome})
        root_file('commit', replace=reset, **names)
        if reset:
            os.replace(agent_staged, OPS_AGENT_CREDENTIALS)
        else:
            os.link(agent_staged, OPS_AGENT_CREDENTIALS)
            agent_staged.unlink()
        committed = True
        grants, granted_by = {}, operator_granted_by()
        for username, (kind, _) in spec.items():
            write_private(scratch, f'{username}.reason', operator_reason(ctx, username, kind).encode())
            result = oneshot(image_id, ['manage', 'grant_operator', '--username', username, '--reason-file',
                                        f'/run/cpt-operators/{username}.reason', '--by', granted_by], env, user=user,
                             mounts=[f'type=bind,src={scratch / (username + ".reason")},'
                                     f'dst=/run/cpt-operators/{username}.reason,readonly'])
            assert_no_secret([result.stdout, result.stderr], passwords.values())
            grants[username] = {'exit': result.returncode, 'log': ctx.log(f'grant-{username}',
                                                                          result.stdout + result.stderr)}
        failed = [username for username, grant in grants.items() if grant['exit']]
        if failed:
            raise InstallError(f'manage grant_operator failed for {", ".join(failed)} (see the logs); the accounts and '
                               'their credentials files are in place, so rerun --phase operators --reset-passwords '
                               'once it is fixed.', details={'accounts': outcome, 'grants': grants})
        check = app_script(image_id, env, OPERATOR_CHECK, {'usernames': sorted(spec)},
                           what='Reading the operator accounts back')
        found = check.get('accounts') if isinstance(check, dict) else None
        problems = [username for username, (kind, _) in spec.items()
                    if not isinstance(found, dict) or not isinstance(found.get(username), dict)
                    or found[username].get('operator') is not True or found[username].get('memberships') != 0
                    or found[username].get('actor_kind') != kind or found[username].get('active') is not True]
        if problems:
            raise InstallError(f'{", ".join(problems)} did not read back as an active operator with no membership; '
                               'the accounts and their credentials files are in place.',
                               details={'accounts': outcome, 'grants': grants, 'check': found})
    except BaseException:
        if not committed:
            root_file('discard', sha256=sha256(documents[human]), **names)
            agent_staged.unlink(missing_ok=True)
        raise
    finally:
        for path in scratch.iterdir():
            path.write_bytes(b'\0' * 64)
            path.unlink()
        scratch.rmdir()
    return {'accounts': outcome, 'grants': grants, 'check': found, 'reset_passwords': reset,
            'operator_credentials': f'{ETC_DIR}/{OPERATOR_CREDENTIALS}', 'agent_credentials': str(OPS_AGENT_CREDENTIALS),
            'summary': 'operator accounts ' + ', '.join(f'{username} {state}' for username, state in outcome.items())
                       + '; granted and read back as operators with no membership'}


def phase_reassess(ctx) -> dict:
    """Re-assess the named encounters from what is already recorded (ops/INSTALL.md, reassess): for each, in its own
    one-shot of this revision's image (provider disabled), the application's command `manage reassess_retained
    --encounter <id> --tag <revision>`, which queues the re-assessment of the retained responses and never sends;
    `--dry-run` is passed through. Each encounter's jobs are read before and after (REASSESS_JOBS), so the receipt
    names the jobs that appeared as measured, not as said; a dry run after which one appeared fails the phase."""
    encounters, dry = list(ctx.args.encounter), bool(ctx.args.dry_run)
    # The worker makes the re-assessment, so the participants it must read are the worker's: this revision's app
    # receipt names the modes its pair runs with. The one-shot below runs with every participant disabled, and the
    # command would otherwise compare the final's participants with that (refusing every harness encounter).
    app = require_receipt(ctx, 'app')
    modes = (app.get('details') or {}).get('participants')
    if not isinstance(modes, dict) or not all(isinstance(mode, str) for mode in modes.values()):
        raise InstallError("This revision's app receipt names no participant modes; nothing was re-assessed.")
    running = sorted(name for name, mode in modes.items() if mode != 'disabled')
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    pending = oneshot(image_id, ['manage', 'migrate', '--check'], env, timeout=120)
    if pending.returncode:
        raise InstallError(f'This revision\'s migrations are not all applied (manage migrate --check exited '
                           f'{pending.returncode}): run --phase app first. Nothing was re-assessed.')
    before = app_script(image_id, env, REASSESS_JOBS, {'encounters': encounters},
                        what='Reading the named encounters\' jobs')['encounters']
    missing = [pk for pk in encounters if before.get(pk) is None]
    if missing:
        raise InstallError(f'{len(missing)} named encounter(s) do not exist ({", ".join(missing)}); nothing was '
                           're-assessed.')
    results = {}
    for number, pk in enumerate(encounters, start=1):
        command = (['manage', 'reassess_retained', '--encounter', pk, '--tag', ctx.revision,
                    '--participants', ','.join(running) or 'none'] + (['--dry-run'] if dry else []))
        result = oneshot(image_id, command, env, timeout=REASSESS_SECONDS)
        log = ctx.log(f'reassess-{number:02d}', result.stdout + result.stderr)
        results[pk] = {'exit': result.returncode, 'log': log, 'receipt': access_receipt(result.stdout),
                       'output': result.stdout.decode('utf-8', 'replace').strip()[-2000:]}
        if result.returncode:
            done = [key for key in results if key != pk]
            raise InstallError(f'reassess_retained for {pk} failed (exit {result.returncode}); see {log}. '
                               + (f'It ran before for {", ".join(done)}.' if done else 'It ran for no encounter before.'),
                               details={'encounters': results})
    after = app_script(image_id, env, REASSESS_JOBS, {'encounters': encounters},
                       what='Reading the named encounters\' jobs again')['encounters']
    for pk in encounters:
        known = {job[0] for job in before[pk]['jobs']}
        results[pk].update(jobs_appeared=[job for job in (after.get(pk) or {}).get('jobs', []) if job[0] not in known],
                           state_before=before[pk]['state'], state_after=(after.get(pk) or {}).get('state'))
    appeared = sum(len(entry['jobs_appeared']) for entry in results.values())
    if dry and appeared:
        raise InstallError(f'A dry run was followed by {appeared} new job(s) on the named encounters; read them in '
                           'this receipt.', details={'encounters': results})
    return {'tag': ctx.revision, 'dry_run': dry, 'participants': running, 'encounters': results,
            'summary': f'reassess_retained {"(dry run) " if dry else ""}for {len(encounters)} encounter(s): '
                       f'{appeared} job(s) appeared'}


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


def publish_vhost(ctx, apply, undo, verify, progress=None) -> dict:
    """Apply a vhost change, validate, reload, verify; restore exactly on any failure. ``progress`` (a dict, when
    given) records 'reload_attempted' right before nginx is asked to reload with the change, 'reloaded' once that call
    returned, and 'restore_reloaded' once nginx was reloaded again with the restored file, for a caller that must know
    which configuration nginx may run. A reload that was asked for is treated as applied whatever its call answered
    (refutation r2, L6-1: systemd runs a reload job it took even when its client is interrupted by a Ctrl-C or gives up
    at the 30 s timeout), so the restored file is reloaded then too."""
    progress = {} if progress is None else progress
    before = nginx_test()
    if not before['ok']:
        raise InstallError('nginx -t does not pass before the change; refusing.')
    log = None
    try:
        apply()
        after = nginx_test()
        log = ctx.log('nginx-t', after['output'].encode())
        new_warnings = sorted(set(after['warnings']) - set(before['warnings']))
        if not after['ok'] or new_warnings:
            raise InstallError(f'nginx -t after the change failed or added warnings {new_warnings}; see {log}.')
        progress['reload_attempted'] = True
        nginx_reload()
        progress['reloaded'] = True
        result = verify()
    except BaseException as failure:
        try:
            undo()
        except BaseException as restore_failure:
            raise InstallError(f'The change failed ({failure}) and restoring the previous vhost also failed '
                               f'({restore_failure}); nginx may hold an unverified vhost. Investigate now.') from None
        restored = nginx_test()
        ctx.log('nginx-t-restored', restored['output'].encode())
        if progress.get('reload_attempted') and restored['ok']:
            nginx_reload()
            progress['restore_reloaded'] = True
        if not restored['ok']:
            raise InstallError('The restored nginx configuration does not pass nginx -t; investigate now.')
        raise
    return {**result, 'nginx_warnings_unchanged': True, 'nginx_t_log': log}


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
    # Any stage this revision renders: the HTTP stage, or the HTTPS stage for either web port (blue/green).
    if vhost_state()['file_sha256'] not in vhost_renderings(ctx.revision):
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


def public_health(revision) -> tuple:
    """(passed, observations): https://cpt.quillmd.com/health/ through the public path answers health_ok for
    ``revision``, polled (reloads are asynchronous) - which says which web nginx routes to only when the two webs are
    different revisions."""
    def check():
        result = probe('https', DOMAIN, '/health/', timeout=3)
        return result.get('status') == 200 and health_ok(result.get('json'), revision), {
            'status': result.get('status'), 'error': result.get('error')}
    return poll(check, attempts=30, interval=0.25)


def https_checks(ctx, revision=None) -> tuple:
    """Through the public path: /health/ serves ``revision`` (this phase's revision unless given: a switch-back
    expects the previous one), the four policy headers once each, and a mismatched SNI is closed."""
    expected = revision or ctx.revision
    passed, observations = public_health(expected)
    final = probe('https', DOMAIN, '/health/', timeout=5)
    headers = final.get('headers', {})
    problems = [] if passed else [f'https://{DOMAIN}/health/ did not serve revision {expected[:12]}']
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
    state = vhost_state()
    if state['link_target'] != VHOST_LINK_TARGET or state['file_sha256'] not in vhost_renderings(ctx.revision):
        raise InstallError('quillmd-cpt is not the HTTP stage this installer wrote; refusing.')
    # The HTTPS stage proxies to the port the running web publishes (it alternates with each blue/green install).
    port = serving_web_port()
    confs = rendered_vhosts(ctx.revision, port)
    http_sha, https_sha = sha256(confs['http'].encode()), sha256(confs['https'].encode())
    if state['file_sha256'] not in (http_sha, https_sha):
        raise InstallError(f'quillmd-cpt holds the HTTPS stage for another port than {port}, the one '
                           f'{SERVICES["web"]} publishes; refusing.')
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
    return {**result, 'vhost_sha256': https_sha, 'upstream_port': port, 'already_installed': already,
            'summary': f'https://{DOMAIN}/ serves {ctx.revision[:12]}'}


def other_lineages(le: dict) -> tuple:
    """Let's Encrypt state without this domain's own lineage, on both sides of any comparison: a reinstall's
    preflight baseline already holds that lineage."""
    return ({name: digest for name, digest in le['renewal'].items() if name != f'{DOMAIN}.conf'},
            set(le['live']) - {DOMAIN})


# Verify's one-shot of the D22 report (design/FINAL.md 13; DECISIONS D22; ADJUDICATION P-7): `manage
# interpretation_report --since <the new worker's start> --self-test --json` in this revision's image, the interpreter
# disabled as in every one-shot (a one-shot's mode is its own, so the worker's is read from the worker's configuration).
# Nothing is written or sent. Every check of its self-test named here must have run and passed - one that ran fewer
# checks proves less than it says - and the hold state is reported beside it, never judged here (a standing hold is the
# operator's to release, with `manage interpreter_hold --release`).
INTERPRETATION_SELF_TEST = ('sentinel installed', 'deny set as pinned', 'positive control', 'positive control trips',
                            'model constant', 'no new-path legacy execution recorded',
                            'every new-path assessment carries its record', 'no sentinel trip',
                            'no legacy-engine assessment')
INTERPRETATION_REPORT_SECONDS = 180
INTERPRETATION_REPORT_LIMIT = 1024 * 1024  # bytes of the report's JSON that are read; more is refused, never cut


def worker_interpreter_mode(container):
    """The interpreter mode ``container`` was started with: its one CPT_STUDIO_GEMINI_MODE, read from Docker's record
    of its environment, and nothing else of that record is read out (the env-file's values are there too). None when it
    names none, or more than one."""
    env = ((container or {}).get('Config') or {}).get('Env') or []
    found = [entry.split('=', 1)[1] for entry in env
             if isinstance(entry, str) and entry.startswith(INTERPRETER['mode_env'] + '=')]
    return found[0] if len(found) == 1 else None


def holds_interpreter_key(container) -> bool:
    """Whether ``container`` holds the interpreter's credentials file, read-only, at the worker's path."""
    return any(mount.get('Type') == 'bind'
               and (mount.get('Source'), mount.get('Destination'), mount.get('RW'))
               == (INTERPRETER['target'], INTERPRETER['mounted'], False)
               for mount in (container or {}).get('Mounts') or [])


def utc_moment(value):
    """An ISO 8601 date and time with its offset ('Z' or '+00:00') as an aware datetime; None otherwise."""
    try:
        moment = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None and moment.utcoffset() is not None else None


def interpretation_evidence(ctx, image_id, worker) -> tuple:
    """(evidence, problems) of verify's D22 one-shot. Its window starts at the newest successful app receipt's
    new-worker start (ADJUDICATION P-7: S4 of a blue/green switch, the worker's start of a swap - never the install's
    start: the old worker runs until S2, and its legacy assessments are not this revision's). The worker's interpreter
    mode must be the one that receipt installed, which is disabled only where --interpreter-mode said so (FINAL 13: the
    install uses live); a live one's worker must hold its key, and no other worker may. A worker that names no
    interpreter mode and holds no key, with no app receipt of this revision beside it, is no pair this installer
    started (every pair it starts names one): there is nothing of the interpreter to read, and the evidence says so.
    With an app receipt, or a worker that names a mode or holds the key, every missing piece is a problem."""
    app = latest_receipt(ctx.receipts, 'app', ctx.revision)
    mode = worker_interpreter_mode(worker)
    evidence = {'worker_mode': mode, 'worker_holds_key': holds_interpreter_key(worker)}
    if app is None:
        if mode is None and not evidence['worker_holds_key']:
            return ({**evidence, 'self_test': 'not run',
                     'summary': 'interpretation self-test not run: the worker names no interpreter mode and no app '
                                'receipt of this revision names its new worker'}, [])
        return ({**evidence, 'self_test': 'not run', 'summary': 'interpretation self-test not run'},
                ["no successful app receipt of this revision names its new worker's start, so the interpretation "
                 'self-test was not read (ADJUDICATION P-7)'])
    installed = (app.get('details') or {}).get('interpreter') or {}
    since = installed.get('worker_started_at')
    evidence.update(app_mode=installed.get('mode'), app_mode_given=installed.get('given'), since=since)
    problems = []
    if mode != installed.get('mode'):
        problems.append(f"the worker's interpreter mode is {mode or 'not named'}, but the app phase installed "
                        f"{installed.get('mode') or 'none'}")
    # The review of S14, finding 2: FINAL 13's install is live, and its D22 evidence shows "mode live". Disabled is the
    # default when --interpreter-mode is not given - as in the app command ops/INSTALL.md documents - and it pauses
    # every upload's reading (FINAL 11.2), so an installation left so by default is not verified; one given disabled
    # is the operator's choice. A receipt that does not say whether it was given is read as not given.
    if installed.get('mode') == 'disabled' and installed.get('given') is not True:
        problems.append('the app phase installed the interpreter disabled only because --interpreter-mode was not '
                        "given, so every upload's reading is paused (design/FINAL.md 11.2; the install uses live, "
                        'FINAL 13): rerun --phase app with --interpreter-mode live, or with --interpreter-mode '
                        'disabled to keep it paused')
    if mode == 'live' and not evidence['worker_holds_key']:
        problems.append(f"the live interpreter's worker does not hold {INTERPRETER['target']} read-only")
    if mode != 'live' and evidence['worker_holds_key']:
        problems.append(f'the worker holds {INTERPRETER["target"]}, but its interpreter is not live')
    asked = utc_moment(since) if isinstance(since, str) else None
    if asked is None:
        problems.append("the app receipt names no new worker's start, so the interpretation self-test was not read "
                        '(ADJUDICATION P-7)')
        return {**evidence, 'self_test': 'not run', 'summary': f'interpreter {mode}: self-test not run'}, problems
    result = oneshot(image_id, ['manage', 'interpretation_report', '--since', since, '--self-test', '--json'],
                     read_protected_env(APP_ENV, APP_ENV_KEYS), timeout=INTERPRETATION_REPORT_SECONDS)
    evidence.update(exit=result.returncode, log=ctx.log('interpretation-report', result.stdout + result.stderr[-8192:]))
    parsed = None
    if len(result.stdout) <= INTERPRETATION_REPORT_LIMIT:
        try:
            parsed = json.loads(result.stdout.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            parsed = None
    report = parsed.get('report') if isinstance(parsed, dict) else None
    test = parsed.get('self_test') if isinstance(parsed, dict) else None
    checks = test.get('checks') if isinstance(test, dict) else None
    if not (isinstance(report, dict) and isinstance(checks, list)
            and all(isinstance(check, dict) and isinstance(check.get('name'), str) for check in checks)):
        problems.append(f'the interpretation report did not answer its JSON report and self-test (exit '
                        f'{result.returncode}); see {evidence["log"]}')
        return {**evidence, 'self_test': 'unread', 'summary': f'interpreter {mode}: self-test unread'}, problems
    evidence.update(self_test=test, report=report)
    named = {check['name']: check for check in checks}
    missing = [name for name in INTERPRETATION_SELF_TEST if name not in named]
    failed = [check for check in checks if check.get('ok') is not True]
    if missing:
        problems.append('the interpretation self-test did not run: ' + ', '.join(missing))
    if failed:
        problems.append('the interpretation self-test failed: ' + '; '.join(
            f'{check["name"]} ({check.get("detail")})' for check in failed))
    if test.get('passed') is not True and not failed:
        problems.append('the interpretation self-test did not say it passed')
    if result.returncode and not failed:
        problems.append(f'the interpretation report exited {result.returncode}; see {evidence["log"]}')
    window = utc_moment((report.get('window') or {}).get('since'))
    if window != asked:
        problems.append(f'the interpretation report read from {window.isoformat() if window else "an unnamed time"}, '
                        f'not from the new worker\'s start ({since})')
    hold = report.get('hold') if isinstance(report.get('hold'), dict) else {}
    standing = [item.get('reason') for item in hold.get('standing') or [] if isinstance(item, dict)]
    held = (f'standing ({", ".join(sorted(set(map(str, standing))))})' if hold.get('held') else
            'none standing' if hold.get('held') is False else 'not read')
    passed = not (missing or failed or result.returncode) and test.get('passed') is True
    evidence['summary'] = (f'interpreter {mode}: self-test {"passed" if passed else "FAILED"} '
                           f'({len(INTERPRETATION_SELF_TEST) - len(missing)} of {len(INTERPRETATION_SELF_TEST)} checks '
                           f'run) since the new worker started ({since}); interpreter hold {held}')
    return evidence, problems


def phase_verify(ctx) -> dict:
    preflight = require_receipt(ctx, 'preflight')['details']
    image_id = installed_image(ctx)
    problems = []
    files = nginx_file_state()
    if files['available'].get('quillmd') != QUILLMD_VHOST_SHA256:
        problems.append('the quillmd vhost sha256 changed')
    # quillmd-cpt must be this revision's HTTPS stage for the port the running web publishes (blue/green alternates it).
    try:
        port = live_web_port()
    except InstallError as error:
        port = None
        problems.append(str(error))
    expected_available = {**preflight['nginx_files']['available'],
                          VHOST_NAME: sha256(rendered_vhosts(ctx.revision, port or WEB_PORT)['https'].encode())}
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
    pair = {}
    for role, name in SERVICES.items():
        container = pair[role] = inspect('container', name)
        if container is None or not container['State'].get('Running'):
            problems.append(f'{name} is not running')
        else:
            problems += [f'{name}: {problem}' for problem in service_problems(
                container, role, image_id, port=port if role == 'web' else None)]
    # What an app phase parks or starts beside the pair is gone once it succeeded.
    for name in (INCOMING_WEB, SERVICES['web'] + '-previous', SERVICES['worker'] + '-previous'):
        if inspect('container', name) is not None:
            problems.append(f'{name} is left beside the installed pair')
    https_problems, evidence = https_checks(ctx)
    problems += https_problems
    foreign = foreign_uid_tasks(APP_UID, own_service_ids())
    if foreign:
        problems.append(f'uid {APP_UID} now runs {foreign} task(s) outside CPT Studio')
    appeared = sorted(set(now) - set(preflight['containers']) - {DB_CONTAINER, *SERVICES.values()})
    # The D22 evidence (design/FINAL.md 13; ADJUDICATION P-7): the interpreter's mode as the worker was started with it,
    # and the interpretation report's self-test since the new worker started.
    interpreting, interpretation_problems = interpretation_evidence(ctx, image_id, pair.get('worker'))
    problems += interpretation_problems
    details = {'evidence': evidence, 'containers_appeared_elsewhere': appeared, 'image_id': image_id,
               'web_port': port, 'interpretation': interpreting}
    if problems:
        raise InstallError(f'verify found {len(problems)} difference(s): ' + '; '.join(problems) + '.',
                           details={**details, 'problems': problems})
    return {**details, 'summary': f'installed {ctx.revision[:12]} verified; co-tenants and app.quillmd.com unchanged; '
                                  + interpreting['summary']}


def keep_layout(ctx):
    """An undo's layout with this revision's incoming web beside the old web, read from the containers and the vhost:
    INCOMING_WEB is this revision's web on one of WEB_PORTS; cpt-studio-web is another revision's web running on the
    other port; cpt-studio-worker, when there, is this revision's worker, stopped; cpt-studio-worker-previous, when
    there, is that other revision's worker, parked; nothing else is parked; and quillmd-cpt is this revision's HTTPS
    stage for one of the two ports. 'routed' says which: 'incoming' is the S4 'keep' layout (ops/INSTALL.md, Recovery
    notes: an S4 failure whose close named a state the old web shows wrongly), where the incoming web serves and so must
    be running; 'old' is the 'back' layout (refutation r3, D-3), where the vhost names the old web - an S3 undo that
    stopped half way, or a way back that could not finish (finish_back) - and the incoming web runs or is stopped. As
    {'incoming', 'web', 'worker', 'parked_worker', 'live', 'idle', 'old_revision', 'image_id', 'routed'}; None when
    there is no INCOMING_WEB. Any other layout with an INCOMING_WEB is refused, stopping nothing: which web serves, and
    whose records to read, cannot be told from the names (refutation r2, L6-5: rollback-app read the records with the
    OLD web's image, where member answers and modifiers do not exist, and removed the old web while the new one went on
    serving as -next)."""
    incoming = inspect('container', INCOMING_WEB)
    if incoming is None:
        return None

    def refused(why):
        return InstallError(f'{INCOMING_WEB} is there and {why}, so rollback-app cannot tell which web serves; nothing '
                            'was stopped or removed. Read the last app or switch-back receipt\'s "left", then '
                            'ops/INSTALL.md, Recovery notes.')
    if not owned(incoming, 'web'):
        raise refused('it is not a CPT Studio web container')
    image_id = installed_image(ctx)
    idle = published_port(incoming)
    if not (incoming.get('Image') == image_id and labels_of(incoming).get(REVISION_LABEL) == ctx.revision
            and idle in WEB_PORTS):
        raise refused('it is not this revision\'s web on a web port')
    live = other_port(idle)
    state, live_bytes = vhost_state(), live_vhost_bytes()
    named = sha256(live_bytes) if live_bytes is not None and state['link_target'] == VHOST_LINK_TARGET else None
    routed = {sha256(rendered_vhosts(ctx.revision, idle)['https'].encode()): 'incoming',
              sha256(rendered_vhosts(ctx.revision, live)['https'].encode()): 'old'}.get(named)
    if routed is None:
        raise refused('quillmd-cpt is not this revision\'s HTTPS stage for either web port')
    if routed == 'incoming' and not (incoming.get('State') or {}).get('Running'):
        raise refused(f'quillmd-cpt names its port ({idle}), but it is not running')
    web = inspect('container', SERVICES['web'])
    if (web is None or not owned(web, 'web') or not (web.get('State') or {}).get('Running')
            or published_port(web) != live):
        raise refused(f'{SERVICES["web"]} is not a web running on the other port ({live})')
    old_revision = labels_of(web).get(REVISION_LABEL)
    if not SHA_RE.fullmatch(str(old_revision or '')) or old_revision == ctx.revision:
        raise refused(f'{SERVICES["web"]} is not another revision\'s web')
    worker = inspect('container', SERVICES['worker'])
    if worker is not None and (not owned(worker, 'worker') or worker.get('Image') != image_id
                               or (worker.get('State') or {}).get('Running')):
        raise refused(f'{SERVICES["worker"]} is not this revision\'s worker, stopped')
    parked_worker = inspect('container', SERVICES['worker'] + '-previous')
    if parked_worker is not None and (not owned(parked_worker, 'worker')
                                      or (parked_worker.get('State') or {}).get('Running')
                                      or labels_of(parked_worker).get(REVISION_LABEL) != old_revision):
        raise refused(f'{SERVICES["worker"]}-previous is not the other revision\'s worker, parked')
    if inspect('container', SERVICES['web'] + '-previous') is not None:
        raise refused(f'{SERVICES["web"]}-previous is there too')
    return {'incoming': incoming, 'web': web, 'worker': worker, 'parked_worker': parked_worker, 'live': live,
            'idle': idle, 'old_revision': old_revision, 'image_id': image_id, 'routed': routed}


def own_baseline() -> dict:
    """rollback-app's own baseline in an undo's layout (refutation r3, D-1: it had refused on a stale preflight baseline
    and sent the operator to run preflight again, which refuses while a cpt-studio-web-next exists - a loop no phase
    left): co-tenant routing and app.quillmd.com, read right before it acts, as preflight records them, in a receipt's
    shape ({'phase': 'rollback-app', 'read_at', 'details': {'routing', 'app_health'}}). The switch back is verified
    against it, as an app's switch is against its preflight. Refused, nothing changed, when app.quillmd.com does not
    answer 200 JSON - as preflight refuses it: a switch verified against a co-tenant that does not answer proves
    nothing about it."""
    health = app_health()
    if health.get('status') != 200 or not isinstance(health.get('json'), dict):
        raise InstallError('app.quillmd.com /health/ did not answer 200 JSON, so no baseline the switch back could be '
                           'verified against was read; nothing was stopped or removed. Rerun --phase rollback-app once '
                           'it answers.', details={'app_health': health})
    return {'phase': 'rollback-app', 'read_at': utc_now_ms(),
            'details': {'routing': routing_snapshot(routing_targets(enabled_config_texts())), 'app_health': health}}


def parked_of(container):
    """park()'s answer for a parked worker read from its container (whether it ran before the install is not known
    there: the restore starts it unless held)."""
    if container is None:
        return None
    return {'id': container['Id'], 'image': container['Image'], 'revision': labels_of(container).get(REVISION_LABEL)}


def removal_summary(record, keep) -> str:
    """What a rollback-app arm removed, read from what finish_back recorded (refutation r3, D-4: the summary had said
    this revision's web and worker were removed while cpt-studio-web-next was left)."""
    worker = (f'{SERVICES["worker"]} (this revision\'s worker)' if record.get('worker_removed')
              else 'no worker of this revision (there was none)')
    return f'removed {INCOMING_WEB} (this revision\'s web) and {worker} after closing their open stages'


def rollback_from_keep(ctx, keep) -> dict:
    """rollback-app in an undo's layout (keep_layout; refutation r2, L6-5): it acts on the right containers, with this
    revision's image, and the site stays served. In the 'back' layout (the vhost names the old web) rollback_back
    finishes the way back. In the S4 'keep' layout it is refused, changing nothing, while this revision recorded what an
    older revision would act on, or show, wrongly (undo_hazards, this image), or while app.quillmd.com does not answer
    (own_baseline: the switch back is verified against co-tenant routing and app.quillmd.com read right before it
    acts - refutation r3, D-1: the preflight receipt's baseline is soon stale, and preflight refuses in this layout).
    Otherwise it finishes the switch back the S4 undo did not make: every stage this revision's pair queued, ran or left
    resumable since its incoming web was created, and every open stage of a kind the old worker does not run, is closed
    (a close that names a record stops there, leaving the layout as it was), then return_to_old_web switches the
    upstream back to the old web, drains and stops this revision's web, closes again, removes this revision's web and
    worker and puts the old worker back - held while a close names a record. It succeeds only when all of that was done
    (refutation r3, D-4: an incoming web left behind, or a Ctrl-C, fails it, with what is left)."""
    if keep['routed'] == 'old':
        return rollback_back(ctx, keep)
    image_id, live, idle, old_revision = keep['image_id'], keep['live'], keep['idle'], keep['old_revision']
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    require_db()
    found = undo_hazards(image_id, env, ctx.revision)
    if found:
        raise InstallError(f'{hazard_summary(found)} hold records an older revision would act on, or show, wrongly '
                           'under its own rules; nothing was stopped or removed. Clear them on this revision\'s web, '
                           f'which serves ({INCOMING_WEB}; ops/INSTALL.md, Reinstalling an older revision), then rerun '
                           '--phase rollback-app.', details={'hazards': found})
    baseline = own_baseline()
    parked_worker = keep['parked_worker']
    previous = {'image': (parked_worker or keep['web'])['Image'], 'revision': old_revision}
    parked = parked_of(parked_worker)
    kinds = stage_kinds_of(previous['image'], env)
    reason = f'revision {ctx.revision[:12]} was rolled back to {old_revision[:12]} (rollback-app)'
    since = created_at(keep['incoming'])
    cause = 'rollback-app in the S4 keep layout'
    record = {'mode': 'keep-switch-back', 'ports': {'from': idle, 'to': live}, 'since': since.isoformat(),
              'baseline': baseline}
    recorder = AvailabilityRecorder().start()
    try:
        if keep['worker'] is not None:
            stop_service_container(SERVICES['worker'], 'worker')
        first_at = dt.datetime.now(dt.timezone.utc)
        record['stages_closed'] = first = close_undone_stages(image_id, env, since, ctx.revision, reason, kinds)
        shown, acting = hazards_by_kind(first.get('hazards'))
        if shown is None or shown or acting:
            named = (hazard_summary(merge_hazards(shown, acting)) if shown is not None
                     else 'the close did not say which encounters')
            message, outcome = (f'{cause}: after the close, {named} hold records an older revision would act on, or '
                                f'show, wrongly under its own rules, so nothing more was done: {keep_note(live, idle)}. '
                                'Clear them on this revision\'s web, then rerun --phase rollback-app.'), 'kept'
        else:
            # ADJUDICATION P-1: this revision's worker is stopped, so this is what the old pair is handed
            record['interpretation'] = interpretation_note(image_id, env, ctx.revision)
            message, _, outcome = return_to_old_web(
                ctx, cause, image_id=image_id, env_bytes=env, preflight=baseline, live=live, idle=idle,
                old_revision=old_revision, previous=previous, parked_worker=parked, kinds=kinds, reason=reason,
                first=first, first_at=first_at, details=record)
        record['availability'] = recorder.stop()  # inside: a Ctrl-C here fails the phase too (D-4)
    except BaseException as failure:
        raise InstallError(f'{cause}: {str(failure) or type(failure).__name__}; read "left" in this receipt, then '
                           'ops/INSTALL.md, Recovery notes.',
                           details={**record, 'availability': stop_recorder(recorder),
                                    'left': left_summary()}) from failure
    if outcome != 'switched' or record.get('incoming_left'):
        raise InstallError(message, details={**record, 'outcome': outcome, 'left': left_summary()})
    availability = record['availability']
    note = (record.get('interpretation') or {}).get('note')
    return {**record, 'outcome': outcome, 'message': message,
            'summary': f'switched back to {old_revision[:12]} on {live} (the S4 keep layout): '
                       f'{availability.get("samples", 0)} availability samples, '
                       f'{availability.get("non_200_count", 0)} not 200; {removal_summary(record, keep)}; database, '
                       'volumes, images and secrets kept' + (f'; {note}' if note else '')}


def rollback_back(ctx, keep) -> dict:
    """rollback-app in the 'back' layout (keep_layout's routed 'old'; refutation r3, D-3): the vhost names the old web
    and this revision's incoming web is beside it - an S3 undo that stopped half way (nothing closed), or a way back
    that could not finish. It finishes the way back, on the right containers with this revision's image, and the old
    worker runs only after everything the incoming web could have queued is closed: nginx is first reloaded with the
    vhost and PROVEN to run it (settle_vhost: new nginx workers, and the public /health/ answered by the old revision) -
    otherwise nothing is stopped, closed or removed - then finish_back: the incoming web drained while it runs and
    stopped; every stage this revision's pair queued, ran or left resumable since the incoming web was created, and
    every open stage of a kind the old worker does not run, closed; the list states put back; this revision's worker
    and the incoming web removed; the old worker put back, held while the close names a record it would act on, or any
    member's answer or chosen modifier (undo_hold, strict: rollback-app did not run the install, and cannot tell whether
    the old worker ran beside one before it). It switches no upstream, so it reads no baseline. It succeeds only when
    all of that was done."""
    image_id, live, idle, old_revision = keep['image_id'], keep['live'], keep['idle'], keep['old_revision']
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    require_db()
    parked_worker = keep['parked_worker']
    previous = {'image': (parked_worker or keep['web'])['Image'], 'revision': old_revision}
    kinds = stage_kinds_of(previous['image'], env)
    reason = f'revision {ctx.revision[:12]} was rolled back to {old_revision[:12]} (rollback-app)'
    since = created_at(keep['incoming'])
    web = SERVICES['web']
    cause = f'rollback-app in the back layout (quillmd-cpt names the old web on {live})'
    record = {'mode': 'back-to-old-web', 'ports': {'from': idle, 'to': live}, 'since': since.isoformat()}
    recorder = AvailabilityRecorder().start()
    try:
        record['settle'] = settle = settle_vhost(ctx, port=live, revision=old_revision, other_revision=ctx.revision)
        if not settle['proven']:
            message, outcome = (f'{cause}: nginx was not proven to run that vhost ({settle.get("problem")}), so nothing '
                                'was stopped, closed or removed: both webs run, and the old worker stays parked. '
                                'Rerun --phase rollback-app once nginx answers (ops/INSTALL.md, Recovery notes); never '
                                'start the old worker by hand.'), 'halfway'
        else:
            # ADJUDICATION P-1: no worker of this revision runs in this layout, so this is what the old pair is handed
            record['interpretation'] = interpretation_note(image_id, env, ctx.revision)
            done = finish_back(ctx, image_id=image_id, env_bytes=env, idle=idle, previous=previous,
                               parked_worker=parked_of(parked_worker), kinds=kinds, reason=reason, since=since,
                               closes=[], details=record, worker=True,
                               hold=lambda every: undo_hold(every, same=False, strict=True,
                                                            window='the incoming web was created'))
            outcome = done['outcome']
            if outcome == 'back':
                message = f'{cause}: {done["problem"]}. {left_for_rollback_app()}'
            else:
                removed = ('this revision\'s worker was removed' if done['worker_removed']
                           else 'there was no worker of this revision to remove')
                message = (f'{cause}: nginx was proven to run it, so {web} (revision {old_revision[:12]}) serves on '
                           f'{live}; {removed} and the incoming web {done["removed"]}; the old worker was '
                           f'{done["worker_note"]}.{held_sentence(done["hold"], done["notes"])}')
        record['availability'] = recorder.stop()
    except BaseException as failure:
        raise InstallError(f'{cause}: {str(failure) or type(failure).__name__}; read "left" in this receipt, then '
                           'ops/INSTALL.md, Recovery notes.',
                           details={**record, 'availability': stop_recorder(recorder),
                                    'left': left_summary()}) from failure
    if outcome != 'switched' or record.get('incoming_left'):
        raise InstallError(message, details={**record, 'outcome': outcome, 'left': left_summary()})
    availability = record['availability']
    note = (record.get('interpretation') or {}).get('note')
    return {**record, 'outcome': outcome, 'message': message,
            'summary': f'went back to {old_revision[:12]} on {live} (the back layout): '
                       f'{availability.get("samples", 0)} availability samples, '
                       f'{availability.get("non_200_count", 0)} not 200; {removal_summary(record, keep)}; database, '
                       'volumes, images and secrets kept' + (f'; {note}' if note else '')}


def phase_rollback_app(ctx) -> dict:
    """Refuse, before stopping anything, while their revision recorded what an older revision would act on, or show,
    wrongly (undo_hazards: a second review's response refused whole, or one the shown assessment did not read, or a code
    only a harness participant proposed, is shown wrongly whatever state it is handed, so it is refused, never put
    back); otherwise stop the web and worker, close
    every stage their revision left open since they were created and every open stage of a kind the next worker does
    not run (close_undone_stages, with their own image), read again, put back the list states the next pair labels
    otherwise (put_back_states), then remove them -
    so a parked pair renamed back or an older revision installed afterwards never runs that work under its own rules,
    nor shows a state it would misread. When the stages cannot be closed, the states cannot be put back, or the second
    read names a record (a send in flight when the worker stopped is an unknown outcome), the pair is left stopped, not
    removed. Refutation r2, L6-5: in the S4 'keep' layout (keep_layout) it acts on this revision's web and worker, with
    this revision's image, and switches back to the old web without interrupting the site (rollback_from_keep), and in
    the 'back' layout it finishes the way back (rollback_back; refutation r3, D-3); with a cpt-studio-web-next in any
    other layout, or a web and a worker of different images, it refuses, stopping nothing: which web serves, and whose
    records to read, cannot be told from the names. Refutation r3 (the recovery notes send undos here): it removes only
    this revision's own pair - a web or worker under the canonical names that carries another revision is refused,
    stopping nothing (it would stop the old web an undo had just put back in service). ADJUDICATION P-1: what this
    revision made from event inventories is never a reason to refuse; every arm that hands the rows to an older pair
    declares it in its receipt ('interpretation': interpretation_note) and goes on."""
    keep = keep_layout(ctx)
    if keep is not None:
        return rollback_from_keep(ctx, keep)
    pair = {}
    for role in ('worker', 'web'):
        container = inspect('container', SERVICES[role])
        if container is not None:
            if not owned(container, role):
                raise InstallError(f'{SERVICES[role]} is not a CPT Studio {role} container; refusing to remove it.')
            pair[role] = container
    if len(pair) == 2 and pair['web'].get('Image') != pair['worker'].get('Image'):
        # refutation r2, L6-5: the two are not one pair, so whose image reads the records cannot be told
        raise InstallError(f'{SERVICES["web"]} and {SERVICES["worker"]} run different images, so they are not one pair '
                           'and whose records to read cannot be told; nothing was stopped or removed. Read the last '
                           'app or switch-back receipt\'s "left", then ops/INSTALL.md, Recovery notes.')
    others = {SERVICES[role]: labels_of(container).get(REVISION_LABEL) for role, container in pair.items()
              if labels_of(container).get(REVISION_LABEL) != ctx.revision}
    if others:
        named = ', '.join(f'{name} is revision {str(label or "unlabelled")[:12]}' for name, label in sorted(others.items()))
        raise InstallError(f'{named}, not this one ({ctx.revision[:12]}): this revision\'s rollback-app removes only '
                           'this revision\'s own pair, so nothing was stopped or removed. If an undo put the old pair '
                           'back, it serves as it should; read the last receipt\'s "left", then ops/INSTALL.md, '
                           'Recovery notes.', details={'revisions': others})
    closed = put_back = None
    if pair:
        first = pair.get('web') or pair['worker']
        revision = labels_of(first).get(REVISION_LABEL) or 'unlabelled'
        env = read_protected_env(APP_ENV, APP_ENV_KEYS)
        require_db()
        # Refutation p1, migrate-0/-1: an older revision's web and worker - a parked pair renamed back, or one
        # reinstalled - would act on these under their own rules (a send without a date, an identical re-send of a
        # request that failed), or show them wrongly whatever state they are handed (p2, the skeptic of the install2:1
        # repair: a second review's response refused whole; P2RA, ROLLBACK lens 0: one the shown assessment did not
        # read); they are cleared on this revision's web, which keeps serving meanwhile.
        found = undo_hazards(first['Image'], env, revision)
        if found:
            raise InstallError(f'{hazard_summary(found)} hold records an older revision would act on, or show, wrongly '
                               'under its own rules; nothing was stopped or removed. Clear them on this revision\'s '
                               'web (ops/INSTALL.md, Reinstalling an older revision), then rerun --phase rollback-app.',
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
                               'revision would act on, or show, wrongly under its own rules. Start them again '
                               f'(docker start {SERVICES["worker"]} {SERVICES["web"]}), clear them on this '
                               'revision\'s web (ops/INSTALL.md, Reinstalling an older revision), then rerun --phase '
                               'rollback-app.',
                               details={'hazards': hazards, 'stages_closed': closed})
        # Refutation p2, install2:1: the next pair - the parked one renamed back, or an older revision installed by its
        # own installer, which never recomputes a stored state - shows each state by its own labels, so a response
        # refused whole would read 'Provider request failed'. Each state this revision labels otherwise is given the
        # state that pair derives (the parked image's own derivation, else 057a7d39's), while this pair is stopped.
        try:
            put_back = put_back_states(closed, next_image, first['Image'], env)
        except InstallError as error:
            raise InstallError(f'Web and worker stopped, not removed: the list states an older revision labels '
                               f'otherwise could not be put back ({error}). Rerun --phase rollback-app once that is '
                               'resolved.', details={'stages_closed': closed}) from error
        # ADJUDICATION P-1: the pair is stopped, so this is what the next pair is handed - a declared note, never a
        # refusal
        made = interpretation_note(first['Image'], env, revision)
    else:
        made = None
    removed = {}
    try:
        for role in ('worker', 'web'):
            name = SERVICES[role]
            removed[name] = role in pair
            remove_service_container(name, role)
    except BaseException as error:  # noqa: BLE001 — states were put back for the older revision: the receipt says so
        if not (put_back or {}).get('changed'):
            raise
        raise InstallError(f'{str(error) or type(error).__name__}; before it, the list states of '
                           f'{len(put_back["changed"])} encounter(s) were put back to what the older revision derives, '
                           'which this revision labels otherwise: rerun --phase rollback-app; or, to keep this '
                           'revision, rerun --phase app, which recomputes them.',
                           details={'stages_closed': closed, 'states_put_back': put_back,
                                    'interpretation': made}) from error
    parked = [name + '-previous' for name in SERVICES.values() if inspect('container', name + '-previous')]
    return {'removed': removed, 'stages_closed': closed, 'states_put_back': put_back, 'parked_left_in_place': parked,
            'interpretation': made,
            'summary': 'web and worker removed after closing their open stages; database, volumes, images and '
                       'secrets kept' + (f'; {made["note"]}' if made else '')}


def recorded_vhosts(ctx) -> dict:
    """sha256 -> (revision, kind) of every vhost stage an earlier successful phase installed, any revision: the vhost
    phases' stages, and the HTTPS stage a blue/green app or switch-back phase switched the upstream to."""
    found = {}
    for phase, kind, field in (('http-vhost', 'http', None), ('https-vhost', 'https', None),
                               ('app', 'https', 'switch'), ('switch-back', 'https', 'switch')):
        for path in sorted(ctx.receipts.glob(f'{phase}-*.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            details = record.get('details') or {}
            digest = ((details.get(field) or {}).get('vhost_sha_after') if field else details.get('vhost_sha256'))
            if (record.get('phase') == phase and record.get('ok') and isinstance(digest, str)
                    and re.fullmatch(r'[0-9a-f]{64}', digest) and SHA_RE.fullmatch(str(record.get('revision')))):
                found.setdefault(digest, (record['revision'], kind))
    return found


def phase_rollback_vhost(ctx) -> dict:
    """Remove quillmd-cpt when it holds a stage this installer wrote: this revision's, or one an earlier
    successful vhost receipt recorded (the documented republish after deploy/nginx changed). The removal is
    undone with the exact bytes it removed, re-rendered from the revision that installed them."""
    preflight = require_receipt(ctx, 'preflight')
    state = vhost_state()
    if not state['file_exists'] and not state['link_exists']:
        return {'state': state, 'summary': 'quillmd-cpt already absent'}
    # Every stage this revision renders: HTTP, and HTTPS for either web port (blue/green alternates it).
    restorable = {digest: info['text'].encode() for digest, info in vhost_renderings(ctx.revision).items()}
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
    'app': phase_app, 'reference': phase_reference, 'passages': phase_passages, 'license-note': phase_license_note,
    'provision': phase_provision, 'operators': phase_operators, 'reassess': phase_reassess,
    'http-vhost': phase_http_vhost, 'cert': phase_cert, 'https-vhost': phase_https_vhost,
    'verify': phase_verify, 'switch-back': phase_switch_back, 'rollback-app': phase_rollback_app,
    'rollback-vhost': phase_rollback_vhost,
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
