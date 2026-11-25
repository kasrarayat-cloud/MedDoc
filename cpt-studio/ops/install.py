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
import ipaddress
import json
import os
import re
import secrets
import shutil
import signal
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
import zipfile
from inspect import getsource
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
APP = 'cpt-studio'
SELF = Path(__file__).resolve()

DOMAIN = 'cpt.quillmd.com'
# The operator console's own host (owner direction 2026-11-23, DECISIONS D396; release 2 of the move): served by the same
# server block, certificate and upstream as DOMAIN (deploy/nginx/cpt-quillmd-https.conf), so the blue/green switch moves
# both together. Its :80 stays the quillmd vhost's (QuillMD's file), which answers its HTTP-01 challenge.
ADMIN_HOST = 'admin.quillmd.com'
# The lineage both names are served with: one webroot order for DOMAIN and ADMIN_HOST, never an --expand. DOMAIN's own
# lineage (named DOMAIN) stays and keeps renewing, unused; the cert and verify phases count both as this installer's.
CERT_NAME = 'cpt-studio'
CPT_LINEAGES = (DOMAIN, CERT_NAME)
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
# A stopped worker finishes the stage it is in (run_worker: each of its threads finishes its current job), which may be
# inside a send. The Fable coding build's one stage (studio.jobs.stage_code, DECISIONS D351-D353) prepares the document
# - a Word file is converted in a bounded child of at most 70 s (studio.fable.document.CONVERT_SECONDS) - then makes two
# streamed sends one after the other, the reader's and the checker's, each of up to 96,000 output tokens at effort max:
# about 1,000 s each at the slowest rate measured (studio.jobs.CODE_STALE_SECONDS' own reckoning), so one round can run
# past 2,000 s and the 1,800 s of the pipeline before it would cut the checker's send into an UNKNOWN outcome. The stage
# must be recorded before Docker kills the worker, or a request that reached the vendor is left 'sending' (HARNESS.md 8,
# 11.2). So 3,600 s outlasts the stage, and it is studio.jobs.CODE_STALE_SECONDS, the age at which the stale-stage sweep
# takes a running code job for a dead worker's: a stage still running when the stop timeout passes is one that sweep
# would settle as cut short anyway, so waiting longer buys nothing. A deploy may so wait up to 60 minutes for a worker
# to stop (before the Fable coding build 1,800 s: round r3's question stage, DECISIONS D322 (4)); a worker of the
# earlier pipeline, parked by this installer on the way in or started again by a switch-back, stops as soon as its own
# stage (1,588 s at the longest) ends.
STOP_SECONDS = {'web': 30, 'worker': 3600}
# The incoming web of a blue/green install, renamed to SERVICES['web'] once the old web is drained and stopped.
INCOMING_WEB = SERVICES['web'] + '-next'
# Release 1 (RELEASE-1-SPEC A7, E3): Word files are converted by a container of their own, cpt-studio-converter, with no
# network, no secret, no files volume and its own uid (CONVERTER_UID, unused on this host [TO CONFIRM]); the group is
# the application's, so the socket on CONVERT_VOLUME - the only thing that volume holds - is shared with the worker
# without sharing any file. It runs outside the blue/green switch (--phase converter, idempotent); a worker of a
# revision that has the converter (has_converter) mounts the volume and is told the socket and that the converter is
# required, so it never converts in-process in production; an older revision's worker is started exactly as before.
CONVERTER = 'cpt-studio-converter'
CONVERT_VOLUME = 'cpt-studio-convert'
CONVERT_DIR = '/run/cpt-convert'
CONVERTER_SOCKET = f'{CONVERT_DIR}/convert.sock'
CONVERTER_UID = 10151
CONVERTER_LIMITS = ('1536m', 128, '1g')  # memory and swap, pids, the /tmp tmpfs (owner decision D9)
CONVERTER_CPUS = '2'  # [TO CONFIRM] (D9)
# A conversion in progress finishes before the old converter stops (Lane 5: LibreOffice's own limit is 55 s and the
# parent's conversion limit 70 s, so a running conversion needs up to 80 s; Lane 5 confirms the figure at
# integration, and this one constant carries it to the container's --stop-timeout and the replacement's stop).
CONVERTER_STOP_SECONDS = 80
CONVERTER_FILES = (f'{APP}/studio/converter_server.py',)  # the revisions that have the converter service
CONVERTER_HEALTH = 'python -m studio.converter_server --ping'
CONVERTER_SELF_TEST = ('-m', 'studio.converter_server', '--self-test')
# the line the converter's self-test prints when it made a PDF (Lane 5's interface); exit 0 without it is a failure
CONVERTER_SELF_TEST_OK = 'cpt-studio converter self-test: ok, a PDF of'
# The convert volume's root is prepared by phase_converter alone (H_CONVERT_VOLUME: CONVERTER_UID, the application's
# group, CONVERT_ROOT_MODE), never by the image: every mount of the volume says volume-nocopy, so Docker never copies an
# image's mount point - its contents or its ownership - over that preparation when the volume is empty.
CONVERT_ROOT_MODE = 0o750
# Environment variable names a converter must never be given (its Config.Env): secrets and credentials files.
CONVERTER_FORBIDDEN_ENV_RE = re.compile(r'(?i)SECRET|PASSWORD|CREDENTIALS|API_KEY|_KEK\b|TOKEN|AUTHORIZATION')
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
# Corti's installed copy, which the Fable coding build (DECISIONS D351-D353) neither requires, copies nor mounts for its
# own pair: the secrets phase no longer reads Corti's source, and an app phase starts its pair with Corti disabled. The
# copy an earlier install wrote stays on the host, untouched (deleting a key copy is the owner's decision, class d), and
# only a switch-back to an earlier revision's pair given --provider-mode live mounts it, as that pair's own app did.
CORTI_TARGET = f'{ETC_DIR}/corti-credentials.env'
# The harness participants' credentials (HARNESS.md 8), optional and kept apart from the all-or-nothing set above:
# adding them to it would read every existing install as partial. Each is copied unread from the source the owner
# places (root 0600 in a root 0700 directory) when it exists, checked by key NAME only, and mounted read-only into the
# worker alone, for a live participant only; the web is given the path and no file, as for Corti. A missing source
# leaves that participant disabled. Models and endpoints are the adapters' constants, never the installer's.
# The Fable coding build drops the participants (D351): an app phase starts its pair with both disabled, and the secrets
# phase copies the Anthropic source alone (CODER). Their entries stay for a switch-back to an earlier revision's pair,
# which is started with the modes its own app phase was given (--astra-mode, --fable-mode), from the copies already on
# the host.
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
# The interpreter's credential (AMENDMENT-2 1.11; DECISIONS D275: the interpreter is Claude Fable 5.2 and reads CPT
# Studio's existing Anthropic credential; D14's rule, the key in the worker only, is unchanged): the Fable participant's
# file - the same source, target and mount as PARTICIPANTS[INTERPRETER_SHARES] - so the participants' run of the secrets
# phase copies it, once (unread, by key NAME only: H_PARTICIPANT_SECRETS), and the WORKER alone binds it read-only,
# once, whenever the Fable participant or the interpreter is live (one bind target: worker_credential_mounts). The
# interpreter keeps its own mode (--interpreter-mode, CPT_STUDIO_GEMINI_MODE: the historical name, which sets the
# interpreter whatever its provider) and has no access check of its own. The web is given the mode and the path and no
# file, as for Corti and the participants (a web that builds what the worker would send needs the worker's
# configuration, and only the worker sends; service_problems refuses any bind in a web). A missing source leaves the
# interpreter installable only disabled or replayed. Replay sends nothing and answers a reading only from a recording
# in the replay directory the image ships (tests/fixtures/interpretation/, kept in the image by deploy/.dockerignore),
# and the image ships no Fable recording: the Fable replay folder (anthropic/, its .sse streams) is not in the tree
# (AMENDMENT-2 8.3: the connector's replay fixtures were to be made from D2/D3's frozen streams, which D277 does not
# run), and the directory's gemini/ holds the v1 FRESH recordings (D274), which the Fable interpreter never reads - so
# an interpreter installed replayed fails every reading unsent ("The replay directory is not available."). The model
# and the endpoint are the adapter's constants (studio/interpretation/fable_adapter.py), never the installer's. The
# installer no longer copies or mounts the earlier interpreter's key copy, LEGACY_INTERPRETER_COPY: one left on a host
# stays untouched and is reported (preflight, secrets), because deleting a key copy is the owner's decision (class d).
# The Fable coding build has no interpreter (D351): an app phase starts its pair with it disabled, and
# --interpreter-mode is a switch-back's alone, for an earlier revision's pair that runs one.
INTERPRETER = {'name': 'anthropic', 'source': f'{PROVIDER_SOURCES}/anthropic.env',
               'target': f'{ETC_DIR}/anthropic-credentials.env', 'mounted': '/run/cpt-studio/anthropic-credentials.env',
               'file_env': 'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE', 'mode_env': 'CPT_STUDIO_GEMINI_MODE',
               'replay_env': 'CPT_STUDIO_GEMINI_REPLAY_DIR', 'replay_dir': '/app/tests/fixtures/interpretation',
               'module': 'studio.interpretation.fable_adapter', 'loader': 'load_anthropic_credentials',
               'setting': 'ANTHROPIC_CREDENTIALS_FILE', 'required': ('ANTHROPIC_API_KEY',),
               'optional': ('ANTHROPIC_WORKSPACE_ID',)}
INTERPRETER_SHARES = 'fable'  # the participant whose credentials file the interpreter reads (AMENDMENT-2 1.11)
LEGACY_INTERPRETER_COPY = f'{ETC_DIR}/gemini.env'  # the Gemini interpreter's own key copy, never written or read now
INTERPRETER_MODES = ('disabled', 'live', 'replay')  # FINAL 13: --interpreter-mode live|replay|disabled
# The Fable coder's credential (DECISIONS D351-D353; the build specification, sections 4.1 and 11): CPT Studio's
# existing Anthropic credential - the same source, copy and worker path as PARTICIPANTS['fable'] and INTERPRETER, so one
# bind serves whichever of them holds it (worker_credential_mounts) - and the only credentials file an app phase
# requires or mounts. The secrets phase copies it, once, unread and checked by key NAME only (H_PARTICIPANT_SECRETS:
# ANTHROPIC_API_KEY and an optional ANTHROPIC_WORKSPACE_ID); --coding-mode live needs that copy, which the application's
# own loader (studio.fable.credentials.load_anthropic_credentials) must read in the worker's mount layout, offline,
# before anything changes; the WORKER alone binds it, read-only, at /run/cpt-studio/anthropic-credentials.env. The web
# is given the mode and the path and no file (service_problems refuses any bind in a web). The model, its effort and its
# endpoint are the application's constants and settings; the installer writes the mode (CPT_STUDIO_CODING_MODE:
# --coding-mode, live on the live install), the effort (CPT_STUDIO_CODING_EFFORT: CODING_EFFORT, the owner's setting)
# and the two owner figures (coding_figures) into every container it starts. No access check: an install sends nothing.
CODER = {'name': 'anthropic', 'source': f'{PROVIDER_SOURCES}/anthropic.env',
         'target': f'{ETC_DIR}/anthropic-credentials.env', 'mounted': '/run/cpt-studio/anthropic-credentials.env',
         'file_env': 'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE', 'mode_env': 'CPT_STUDIO_CODING_MODE',
         'effort_env': 'CPT_STUDIO_CODING_EFFORT', 'module': 'studio.fable.credentials',
         'loader': 'load_anthropic_credentials', 'setting': 'ANTHROPIC_CREDENTIALS_FILE',
         'required': ('ANTHROPIC_API_KEY',), 'optional': ('ANTHROPIC_WORKSPACE_ID',)}
CODING_MODES = ('disabled', 'live')  # --coding-mode: the installer never starts a pair replaying
CODING_EFFORT = 'max'  # the owner's setting (the build specification, section 4.1)
# The CMS passage files the revision commits (HARNESS.md 5), in the repository and as the image ships them (/app is the
# image's copy of cpt-studio/, built from git archive of the revision).
PASSAGE_DATA = f'{APP}/studio/reference/data'
PASSAGE_DATA_IN_IMAGE = '/app/studio/reference/data'
INITIAL_CREDENTIALS = 'initial-credentials.json'
AGENT_CREDENTIALS = Path('/home/claude/.cpt-studio/agent-credentials.json')
# The specialties a workspace may be provisioned for (owner direction 2026-11-22, DECISIONS D390), as manage.py
# provision names them. Gastroenterology keeps its credentials files; each other specialty has its own pair, so
# provisioning one never touches another's. A review agent is opt-in since release 1 (A6): --agent-username names one
# (the names earlier installs gave them were review-agent, review-agent-neuro and review-agent-ortho; one login serves
# one workspace until a switcher exists).
SPECIALTY_NAMES = {'gastroenterology': 'Gastroenterology', 'neurosurgery': 'Neurosurgery',
                   'orthopedic-surgery': 'Orthopedic Surgery'}


def credentials_files(specialty: str) -> tuple:
    """(the root-only file's name in /etc/cpt-studio, the agent's user file) of a specialty's provisioning."""
    if specialty == 'gastroenterology':
        return INITIAL_CREDENTIALS, AGENT_CREDENTIALS
    return f'initial-credentials-{specialty}.json', AGENT_CREDENTIALS.with_name(f'agent-credentials-{specialty}.json')
# The operators phase's platform-operator account (ops/INSTALL.md, operators): no workspace membership, a grant from
# `manage grant_operator`. Release 1 (RELEASE-1-SPEC A6; TEC-4, AUTH-1): the human operator ALONE - no automated account
# is an operator again (the release walk needs none: A11), and no operator login is written to a file (TEC-16 (2)): the
# operator sets a password with a single-use setup code instead (phase_operators, issue_setup_code).
OPERATOR_ACCOUNTS_SPEC = (('platform-operator', 'human', 'CPT Studio platform operator'),)
# Every operator account name this installer has made, today's and an earlier install's (ops-agent, revoked by a ruled
# act): none is ever provisioned as a practice's owner or agent (refutation, installer lens A-4).
OPERATOR_NAMES = frozenset({name for name, _, _ in OPERATOR_ACCOUNTS_SPEC} | {'ops-agent'})

NGINX_AVAILABLE = Path('/etc/nginx/sites-available')
NGINX_ENABLED = Path('/etc/nginx/sites-enabled')
VHOST_NAME = 'quillmd-cpt'
VHOST_LINK_TARGET = f'{NGINX_AVAILABLE}/{VHOST_NAME}'
# The quillmd vhost (/etc/nginx/sites-available/quillmd) is QuillMD's file. This installer writes it only in the ingress
# and ingress-rollback phases, and only between these two states (ops/INSTALL.md, the coupling invariant):
#   BEFORE  the file as QuillMD keeps it, admin.quillmd.com named on its :80 block (line 13) and its :443 block (line 26);
#   AFTER   BEFORE with line 26 replaced whole: QUILLMD_ADMIN_LINE becomes QUILLMD_FREED_LINE (that full line once,
#           asserted; line 13 - the :80 block that answers admin's HTTP-01 challenge for both lineages naming it -
#           byte-identical, as every other line). Derivation (quillmd_bytes): AFTER was computed on 2026-11-23 from the
#           live file, read only, whose sha256 was BEFORE, by exactly that replacement; quillmd_bytes asserts both shas
#           before anything is written, either way.
# The coupling invariant replaces the single pin and any "accept either": the quillmd vhost is BEFORE exactly when
# quillmd-cpt names no admin host on 443, and AFTER exactly when it does; anything else refuses (coupling).
QUILLMD_VHOST_BEFORE = 'e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638'
QUILLMD_VHOST_AFTER = 'b3ab66023547790e861c3d12b39d8b268de8748ba6453f830194a4df6e4a3dbb'
QUILLMD_ADMIN_LINE = b'    server_name quillmd.com www.quillmd.com admin.quillmd.com;'
QUILLMD_FREED_LINE = b'    server_name quillmd.com www.quillmd.com;'
QUILLMD_ADMIN_LINE_NUMBER = 26  # 1-based: the :443 block's server_name
QUILLMD_ACME_LINE_NUMBER = 13   # 1-based: the :80 block's server_name, never changed
# QuillMD's Caddy, which answers admin.quillmd.com's maintenance notice while the quillmd vhost names admin on 443 (its
# dormant block after ingress; ingress-rollback reads it before it writes anything: refutation INGRESS-9).
CADDY_ADDRESS = ('127.0.0.1', 8443)
# QuillMD's deliberate answer on admin.quillmd.com before the move (its Caddyfile's admin block: 503 with this sentence).
# ingress-rollback gives admin back to Caddy only when it answers a deliberate state - this notice, or a non-error
# status - never an error (refutation R2 round 1, COTENANT-3).
QUILLMD_NOTICE_MARKER = b'QuillMD administration is temporarily unavailable'
# The hosts scripts/check-cotenants.sh is told not to judge (CPT_INSTALLER_SKIP_HOSTS, exact host names): the
# installer's own, which it judges itself (admin_checks). Passed by cotenant_check alone, never read from an environment.
COTENANT_SKIP_HOSTS = (ADMIN_HOST,)
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


def run(argv, *, input=None, timeout=60, check=True, quiet=False, env=None):
    """Run a command with a fixed environment (``env``: variables the caller adds to COMMAND_ENV; the operator's own
    environment never reaches it). ``quiet`` keeps its output out of errors."""
    try:
        proc = subprocess.run(argv, input=input, capture_output=True, timeout=timeout,
                              env={**COMMAND_ENV, **(env or {})})
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


# Once an act has run, its record is never discarded for what its output holds (refutation round 1, phileak-1 and
# dataloss-3: a disposal's certificate repeated the plan's reason, assert_no_secret refused the output after the
# destruction had run, and no log or receipt kept the certificate). Each secret value - and each value of the reason
# (reason_values) - is replaced by REDACTED_MARK before the log and the receipt are written, and the receipt counts how
# many were (redact_output; never a value). A secret is replaced wherever it occurs (a long random value cannot occur by
# chance); a value of the reason as written and as JSON writes it inside a string (a ledger line's), and one shorter than
# REDACT_BOUNDED_BELOW only where no letter or digit adjoins it. Since refutation round 2 (installer-5: '-' bounds every
# group of an id, so a 4-digit reason altered a plan id) an operator's reason is refused before the act unless every
# value of it is in words (reason_words_problem), so that last rule is reached only by none of them.
REDACTED_MARK = b'[redacted by the installer]'
REDACT_BOUNDED_BELOW = 12
_ALNUM = b'0-9A-Za-z'


def redaction_forms(value) -> list:
    """``value`` as written and as JSON writes it inside a string (escaped, ASCII or not), as UTF-8 bytes."""
    forms = [value.encode('utf-8')]
    for ascii_only in (True, False):
        forms.append(json.dumps(value, ensure_ascii=ascii_only)[1:-1].encode('utf-8'))
    return list(dict.fromkeys(form for form in forms if form))


def redact_output(output: bytes, secrets=(), reasons=()) -> tuple:
    """(``output`` with every secret and every value of the reason replaced by REDACTED_MARK, {'secret': how many
    secret occurrences, 'reason': how many of the reason}) - in one pass, the longest value first, so no replacement is
    read again."""
    kinds = {}
    for kind, values in (('reason', reasons), ('secret', secrets)):  # a secret's kind wins a value both name
        for value in values:
            if value:
                for form in redaction_forms(value) if kind == 'reason' else [value.encode('utf-8')]:
                    kinds[form] = kind
    counts = {'secret': 0, 'reason': 0}
    if not kinds or not output:
        return output, counts
    patterns = []
    for form in sorted(kinds, key=len, reverse=True):
        pattern = re.escape(form)
        if kinds[form] == 'reason' and len(form) < REDACT_BOUNDED_BELOW:
            if re.match(rb'[0-9A-Za-z]', form[:1]):
                pattern = rb'(?<![' + _ALNUM + rb'])' + pattern
            if re.match(rb'[0-9A-Za-z]', form[-1:]):
                pattern += rb'(?![' + _ALNUM + rb'])'
        patterns.append(pattern)

    def replace(match):
        counts[kinds.get(match.group(0), 'reason')] += 1
        return REDACTED_MARK
    return re.sub(b'|'.join(patterns), replace, output), counts


def redaction_summary(redacted) -> str:
    """The summary's clause for a receipt's 'redacted' ('' when nothing was): a secret printed is a FINDING."""
    if not isinstance(redacted, dict) or not any(redacted.values()):
        return ''
    said = []
    if redacted.get('reason'):
        said.append(f'{redacted["reason"]} occurrence(s) of the reason')
    if redacted.get('secret'):
        said.append(f'{redacted["secret"]} of a secret (FINDING: the command printed one)')
    return '; its output was kept with ' + ' and '.join(said) + ' redacted'


def raise_after_act(error, record, what):
    """An act ran (``record`` holds its exit, its log and its output), and what follows it - its RAM folder's wipe, an
    export's seal - failed or was interrupted: the record is never lost to that (refutation round 1, phileak-1's class,
    builder D's point: once the act ran, nothing may make its record vanish). A failure is raised as an InstallError
    carrying the record; a signal or a Ctrl-C is raised as itself, the record in its ``details``, which main writes into
    the receipt beside the interrupt."""
    if isinstance(error, Exception):
        said = str(error) or type(error).__name__
        raise InstallError(f'{what} ran (exit {record.get("exit")}) and its record is kept (its log: '
                           f'{record.get("log") or "none kept"}), '
                           f'but what follows the act did not finish: {said}. If it was the RAM folder\'s wipe, a '
                           f'/dev/shm/cpt-studio-* folder may be left: overwrite and remove it as root, never read it.',
                           details={**record, 'after_act': said}) from error
    cause = error.__cause__  # signals_deferred raises a held signal from what its body raised: a wipe that failed
    if isinstance(cause, Exception):  # (refutation round 2, installer-4: the receipt had said neither)
        record = {**record, 'after_act': f'{str(cause) or type(cause).__name__}; then the {str(error) or "Ctrl-C"} held '
                                         'meanwhile was acted on. If it was the RAM folder\'s wipe, a '
                                         '/dev/shm/cpt-studio-* folder may be left: overwrite and remove it as root, '
                                         'never read it.'}
    error.details = record
    raise error


def redaction_record(*counted) -> dict:
    """The receipt's 'redacted' of one act: the occurrences replaced, by kind, summed over ``counted``
    (redact_output's counts) - {} when there were none, so a receipt without the key had nothing redacted."""
    total = {'secret': sum(c.get('secret', 0) for c in counted), 'reason': sum(c.get('reason', 0) for c in counted)}
    return {'redacted': total} if any(total.values()) else {}


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


# The door's wall-clock ceiling (scripts/lib/run-watched.sh: RULED_ACT_MAX_SECS, DOOR_CEILING_DEFAULT when it is not set;
# a value that is not a positive base-10 integer - read in bash's signed 64-bit arithmetic, which wraps - reads as the
# default, and the ceiling can be raised, never switched off). At it the door kills the command it runs, wherever it is
# - mid-switch included. A phase that stops a worker may
# wait STOP_SECONDS['worker'] for each one it stops - the old one parked on the way in and, on an undo, the new one
# stopped - and drains a web or two besides, so it refuses to start, changing nothing, unless the ceiling allows two
# such stops and WORKER_PHASE_MARGIN more (9,000 s at this revision's bound). The door's default fitted the bound before
# the Fable coding build; it does not fit this one.
DOOR_CEILING_DEFAULT = 3600
WORKER_PHASE_MARGIN = 1800
WORKER_PHASES = ('app', 'switch-back', 'rollback-app')


def door_ceiling(environ) -> int:
    """The door's wall-clock ceiling as the door reads RULED_ACT_MAX_SECS (run-watched.sh _watch_int): a value of
    anything but the bytes 0-9 is the default; the digits are read as bash's $((10#$v)) reads them - in signed 64-bit
    arithmetic, which wraps (2**63 reads as -2**63, 2**64 + 2 as 2) - and the result is kept only when it is 1 or more,
    else the default (install-1: Python's unbounded int read a value of 2**63 or more as itself, so a 19-nines ceiling
    the door runs at its default passed the check of WORKER_PHASES). Read digit by digit, so no length raises."""
    value = environ.get('RULED_ACT_MAX_SECS', '')
    if not value or any(char not in '0123456789' for char in value):
        return DOOR_CEILING_DEFAULT
    wrapped = 0
    for char in value:
        wrapped = (wrapped * 10 + ord(char) - ord('0')) % 2 ** 64
    if wrapped >= 2 ** 63:
        wrapped -= 2 ** 64
    return wrapped if wrapped >= 1 else DOOR_CEILING_DEFAULT


def check_door_ceiling(environ, phase) -> dict:
    """Refuses a phase that stops a worker (WORKER_PHASES) under a door ceiling it could outrun; {'ceiling', 'needed'}."""
    needed = 2 * STOP_SECONDS['worker'] + WORKER_PHASE_MARGIN if phase in WORKER_PHASES else 0
    ceiling = door_ceiling(environ)
    if ceiling < needed:
        raise InstallError(f'--phase {phase} may wait up to {STOP_SECONDS["worker"]} s for each worker it stops, and the '
                           f'door kills it at {ceiling} s (RULED_ACT_MAX_SECS), mid-switch included; nothing was '
                           f'changed. Run it through the door with RULED_ACT_MAX_SECS={needed} or more.')
    return {'ceiling': ceiling, 'needed': needed}


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
    'coding_mode': {'app', 'switch-back'}, 'authorization_ref': {'app', 'switch-back'},
    # an earlier revision's modes, which only a switch-back to its pair is given (the Fable coding build has none)
    'provider_mode': {'switch-back'}, 'astra_mode': {'switch-back'}, 'fable_mode': {'switch-back'},
    'interpreter_mode': {'switch-back'},
    'owner_username': {'provision'}, 'owner_display_name': {'provision'}, 'agent_username': {'provision'},
    'agent_display_name': {'provision'}, 'workspace_name': {'provision'}, 'specialty': {'provision'},
    'reset_passwords': {'provision', 'operators'},
    # release 1 (A6): the operators phase's grant and re-grant, provisioning's --by, and the manage phase's ruled acts
    'by': {'provision', 'operators', 'manage'}, 'review_by': {'operators', 'manage'},
    'regrant': {'operators', 'manage'},
    'command': {'manage'}, 'username': {'manage'}, 'reason_file': {'manage'}, 'approved_by': {'manage'},
    'workspace_id': {'manage'}, 'encounter_id': {'manage'}, 'dispose_step': {'manage'}, 'plan_id': {'manage'},
    'all_human_accounts': {'manage'}, 'ledger_file': {'manage'}, 'execute': {'manage'},
    # refutation round 1, installer-1's class: --address (clear-signin-failures') was refused by no other phase
    'address': {'manage'},
}


def parse_args(argv=None):
    # no abbreviations: an option is named in full or refused (release 1: '--encounter' must never be taken for
    # '--encounter-id', nor any other prefix for an option of a ruled act)
    parser = argparse.ArgumentParser(description='CPT Studio ruled-mutation installer (one phase per run).',
                                     allow_abbrev=False)
    parser.add_argument('--phase', required=True, choices=list(PHASES))
    parser.add_argument('--revision', required=True)
    parser.add_argument('--receipts', required=True)
    parser.add_argument('--pfs-zip')
    parser.add_argument('--mue-zip')
    parser.add_argument('--pfs-retrieved-at', help='when the operator downloaded the PFS zip, ISO-8601 with offset')
    parser.add_argument('--mue-retrieved-at', help='when the operator downloaded the MUE zip, ISO-8601 with offset')
    parser.add_argument('--coding-mode', choices=CODING_MODES,
                        help='the Fable coder (DECISIONS D351-D353; CPT_STUDIO_CODING_MODE): required by app - live on '
                             'the live install, sending under --authorization-ref with the Anthropic credentials file '
                             'mounted into the worker alone, or disabled; a switch-back gives the previous pair\'s '
                             '(disabled when not given)')
    parser.add_argument('--authorization-ref')
    parser.add_argument('--provider-mode', choices=('disabled', 'live'),
                        help='switch-back only, and required there: Corti\'s mode for the previous pair (the Fable '
                             'coding build has no Corti); release 1 refuses live (A8: no BAA)')
    parser.add_argument('--astra-mode', choices=('disabled', 'live'),
                        help='switch-back only: Astra (OpenAI) for the previous pair; disabled when not given; '
                             'release 1 refuses live (A8)')
    parser.add_argument('--fable-mode', choices=('disabled', 'live'),
                        help='switch-back only: the Fable participant (Anthropic) for the previous pair; disabled when '
                             'not given; release 1 refuses live (A8)')
    parser.add_argument('--interpreter-mode', choices=INTERPRETER_MODES,
                        help='switch-back only: the previous pair\'s interpreter (Claude Fable 5.2, AMENDMENT-2: the '
                             'Fable participant\'s Anthropic key; design/FINAL.md 13), disabled when not given; live '
                             'sends under --authorization-ref; replay sends nothing and answers only from a recording '
                             'in the image, which ships no Fable recording, so every reading fails unsent')
    parser.add_argument('--owner-username')
    parser.add_argument('--owner-display-name')
    parser.add_argument('--agent-username')
    parser.add_argument('--agent-display-name')
    parser.add_argument('--workspace-name')
    parser.add_argument('--specialty', choices=sorted(SPECIALTY_NAMES),
                        help='provision: the workspace\'s specialty (default gastroenterology; D390)')
    parser.add_argument('--reset-passwords', action='store_true', default=None)
    # release 1 (A6): who runs an act (a person, never a role), a grant's review date, a re-grant of a revoked
    # operator, and the manage phase's allow-listed ruled acts (MANAGE_COMMANDS)
    parser.add_argument('--by', help='provision, operators, manage: the person who runs this act (never a role)')
    parser.add_argument('--review-by', help='operators, manage grant-operator: the date the grant is reviewed by')
    parser.add_argument('--regrant', help='operators: grant this revoked account again (its declaration names it)')
    parser.add_argument('--command', choices=sorted(MANAGE_COMMANDS), help='manage: the ruled act to run')
    parser.add_argument('--username', help='manage: the account the act is for')
    parser.add_argument('--address', help='manage clear-signin-failures: in place of --username, an IPv4 address or an '
                                          'IPv6 address or /64 whose sign-in refusal to clear (B1)')
    parser.add_argument('--reason-file', help='manage: an absolute path to the reason, a short UTF-8 text file')
    parser.add_argument('--approved-by', help='manage dispose --dispose-step execute, or replay-ledger --execute: the '
                                              'approving person (D14)')
    parser.add_argument('--execute', action='store_true', default=None,
                        help='manage dispose --dispose-step replay-ledger: replay it (without: a dry run that changes '
                             'nothing); needs --approved-by')
    parser.add_argument('--workspace-id', help='manage dispose, export-workspace: the practice (a UUID)')
    parser.add_argument('--encounter-id', help='manage dispose --dispose-step plan: one document (a UUID)')
    parser.add_argument('--dispose-step', choices=DISPOSE_STEPS, help='manage dispose: the step')
    parser.add_argument('--ledger-file', help='manage dispose --dispose-step replay-ledger: the ledger to replay')
    parser.add_argument('--plan-id', help='manage dispose --dispose-step execute: the plan to carry out (a UUID)')
    parser.add_argument('--all-human-accounts', action='store_true', default=None,
                        help='manage require-password-change: every human account (D22; never an automated one)')
    args = parser.parse_args(argv)
    problem = argument_problem(args)
    if problem:
        parser.error(problem)
    args.astra_mode = args.astra_mode or 'disabled'
    args.fable_mode = args.fable_mode or 'disabled'
    # --interpreter-mode and --coding-mode stay None when they are not given (interpreter_mode and coding_mode read that
    # as disabled); app refuses to run without an explicit --coding-mode (argument_problem)
    args.specialty = args.specialty or 'gastroenterology'
    # release 1 (A6; TEC-4 (5), ORG-20 (5)): a review agent is opt-in - created only when --agent-username names one
    args.agent_display_name = args.agent_display_name or 'CPT Studio review agent'
    args.owner_display_name = args.owner_display_name or ''
    # an absent name is the specialty's; an explicit empty one is refused (argument_problem), never read as absent: an
    # unset shell variable must not land accounts in the default workspace (refutation N6-1-4)
    args.workspace_name = SPECIALTY_NAMES[args.specialty] if args.workspace_name is None else args.workspace_name
    return args


def repeated_options(argv, args) -> list:
    """The options ``argv`` gives more than once, sorted (refutation round 2, installer-2: argparse keeps an option's
    last value and drops the others without a word, so a command line edited from an earlier one closed the practice
    named last, for good, and the first was in no receipt). Each is '--' and its destination with '-' for '_', as
    parse_args names every option, counted as '--name value' or '--name=value', up to a bare '--' (argparse reads no
    value that starts with '--' as a value, so none is counted for another option)."""
    names = {'--' + name.replace('_', '-') for name in vars(args)}
    counts = {}
    for token in argv:
        if token == '--':
            break
        name = str(token).split('=', 1)[0]
        if name in names:
            counts[name] = counts.get(name, 0) + 1
    return sorted(name for name, count in counts.items() if count > 1)


# Release 1 (RELEASE-1-SPEC A8; VEN-8): no way back to a vendor that has no BAA. The earlier pipelines' live modes - Corti
# (--provider-mode), the harness participants Astra (OpenAI) and the old Fable participant, and the Gemini-era interpreter
# - are refused in app and in switch-back, so an earlier pair is started only with no provider of those (disabled, or the
# interpreter replayed). The Fable coder (--coding-mode) is not one of them. Their key copies stay untouched on the host:
# deleting them is the owner's decision (D21, an accepted capability loss).
LEGACY_LIVE_MODES = {'provider_mode': 'Corti', 'astra_mode': 'Astra (OpenAI)',
                     'fable_mode': 'the earlier Fable participant', 'interpreter_mode': 'the earlier interpreter'}


def legacy_live_problem(args) -> str:
    """The refusal of a live legacy mode (A8), or ''."""
    for name, vendor in LEGACY_LIVE_MODES.items():
        if getattr(args, name, None) == 'live':
            flag = '--' + name.replace('_', '-')
            return (f'{flag} live is refused: it would start an earlier pair sending to {vendor}, a vendor with no '
                    f'business associate agreement (RELEASE-1-SPEC A8). Give {flag} disabled'
                    + (' or replay' if name == 'interpreter_mode' else '') + '; nothing was changed.')
    return ''


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
    if args.phase == 'manage':
        problem = manage_problem(args)
        if problem:
            return problem
    if args.phase == 'operators':
        for name in ('by',):
            if getattr(args, name, None) is not None:
                problem = person_problem(getattr(args, name), '--by')
                if problem:
                    return problem
        if getattr(args, 'review_by', None) is not None:
            problem = review_by_problem(args.review_by)
            if problem:
                return problem
        if getattr(args, 'regrant', None) is not None and not USERNAME_RE.fullmatch(args.regrant):
            return f'--regrant must match {USERNAME_RE.pattern}.'
    if args.phase in ('app', 'switch-back'):
        coding = getattr(args, 'coding_mode', None)
        if args.phase == 'app' and coding is None:
            return '--phase app needs an explicit --coding-mode (disabled or live).'
        if args.phase == 'switch-back' and args.provider_mode is None:
            return ("--phase switch-back needs an explicit --provider-mode (disabled): the previous pair's, which "
                    'release 1 starts with no provider that has no business associate agreement (A8).')
        problem = legacy_live_problem(args)
        if problem:
            return problem
        # The Fable coder sends under the recorded authority every live mode needs (jobs._live_gate).
        if coding == 'live' and not args.authorization_ref:
            return '--coding-mode live needs --authorization-ref (a ruling file tracked at the revision).'
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
        if (args.authorization_ref and coding != 'live' and args.provider_mode != 'live' and not participants
                and not interpreting):
            return '--authorization-ref only applies to --coding-mode live.'
        reference = args.authorization_ref
        if reference and (not AUTH_REF_RE.fullmatch(reference) or '..' in reference.split('/') or len(reference) > 200):
            return '--authorization-ref must be a relative repository path.'
    if args.phase == 'provision':
        if not args.owner_username:
            return '--phase provision needs --owner-username.'
        agent = args.agent_username  # release 1 (A6): opt-in, no default
        for value in (args.owner_username, *([agent] if agent is not None else [])):
            if not USERNAME_RE.fullmatch(value):
                return f'Username {value!r} must match {USERNAME_RE.pattern}.'
        if args.owner_username == agent:
            return 'The owner and agent usernames must differ.'
        # refutation, installer lens A-4: an operator account is never a practice's owner or agent - its password
        # would then be written to a credentials file (phase_provision also refuses one that holds or held a grant)
        for value in (args.owner_username, *([agent] if agent is not None else [])):
            if value in OPERATOR_NAMES:
                return (f'{value} is an operator account: an operator is never a practice\'s owner or agent, and its '
                        'password is never written to a file.')
        problem = person_problem(args.by, '--by')  # C3: provisioning records who ran it
        if problem:
            return problem
        if args.workspace_name is not None and not args.workspace_name.split():
            return '--workspace-name is empty.'
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


def latest_receipt_entry(directory: Path, phase: str, revision: str):
    """(path, record) of the newest successful receipt of ``phase`` for ``revision``, or None."""
    for path in sorted(directory.glob(f'{phase}-*.json'), reverse=True):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('phase') == phase and record.get('ok') and record.get('revision') == revision:
            return path, record
    return None


def latest_receipt(directory: Path, phase: str, revision: str):
    """The newest successful receipt of ``phase`` for ``revision``, or None."""
    entry = latest_receipt_entry(directory, phase, revision)
    return None if entry is None else entry[1]


def require_receipt_entry(ctx, phase):
    """(path, record) of require_receipt's receipt: the one latest_receipt gives, else refused."""
    entry = latest_receipt_entry(ctx.receipts, phase, ctx.revision)
    if entry is None:
        raise InstallError(f'No successful --phase {phase} receipt for this revision in {ctx.receipts}.')
    return entry


def require_receipt(ctx, phase):
    return require_receipt_entry(ctx, phase)[1]


def receipt_moments(record) -> list:
    """DECISIONS D59: the times ``record`` (a receipt main wrote) records for its phase, as aware datetimes - main's
    'started_at', taken before anything of the phase ran, and each step its swap stamped ('details' 'steps': S1-S6 of a
    blue/green app). A value that is not such a time is left out."""
    if not isinstance(record, dict):
        return []
    details = record.get('details')
    steps = details.get('steps') if isinstance(details, dict) else None
    values = [record.get('started_at')] + (list(steps.values()) if isinstance(steps, dict) else [])
    return [moment for moment in (utc_moment(value) for value in values if isinstance(value, str))
            if moment is not None]


def written_moment(path: Path):
    """When write_receipt wrote the receipt at ``path``: the stamp() its name carries, as an aware datetime, or None."""
    text = receipt_stamp(path)
    if text is None:
        return None
    return dt.datetime.strptime(text, '%Y%m%dT%H%M%S%fZ').replace(tzinfo=dt.timezone.utc)


def receipt_stamp(path: Path):
    """The stamp() write_receipt put in the name of the receipt at ``path`` ('<phase>-<stamp>.json'), or None. Phases
    run one at a time on one receipts directory (main's lock), so it orders receipts of different phases."""
    match = re.fullmatch(r'.+-(\d{8}T\d{12}Z)\.json', path.name)
    return None if match is None else match[1]


def written_after(path: Path, bound):
    """DECISIONS D82, D83: whether the receipt at ``path`` was written after the receipt ``bound`` ((path, record); None:
    after nothing), by the stamps their names carry - None when either carries none, so the order cannot be told."""
    if bound is None:
        return True
    mine, theirs = receipt_stamp(path), receipt_stamp(bound[0])
    if mine is None or theirs is None:
        return None
    return mine > theirs


def replaced_web_entry(record) -> dict:
    """What an app receipt records of the web its phase replaced ('details' 'replaced' 'web'), or {}."""
    details = record.get('details') if isinstance(record, dict) else None
    replaced = details.get('replaced') if isinstance(details, dict) else None
    web = replaced.get('web') if isinstance(replaced, dict) else None
    return web if isinstance(web, dict) else {}


def replaced_web(record) -> tuple:
    """(image, revision) of the web an app receipt says its phase replaced (the pair a switch-back returns to), when it
    names both well formed; else (None, None). A receipt that failed records one only once its switch had finished -
    the old web parked and this revision's pair serving (S5, or a swap's park; then the recompute, the removal of the
    parked pair or an access check failed) - never after an undo."""
    web = replaced_web_entry(record)
    image, revision = web.get('image'), web.get('revision')
    if (isinstance(image, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', image) and isinstance(revision, str)
            and SHA_RE.fullmatch(revision)):
        return image, revision
    return None, None


def last_switch_back(ctx, target=None):
    """DECISIONS D82, D83: (path, record) of the newest successful switch-back receipt of this revision - one that
    returned to ``target`` (a revision) when it is given ('details' 'previous') - or None."""
    for path in sorted(ctx.receipts.glob('switch-back-*.json'), reverse=True):
        record = json.loads(path.read_text(encoding='utf-8'))
        if not (isinstance(record, dict) and record.get('phase') == 'switch-back' and record.get('ok')
                and record.get('revision') == ctx.revision):
            continue
        details = record.get('details')
        previous = details.get('previous') if isinstance(details, dict) else None
        if target is None or (isinstance(previous, dict) and previous.get('revision') == target):
            return path, record
    return None


class Context:
    def __init__(self, args, receipts):
        self.args = args
        self.phase = args.phase
        self.revision = args.revision
        self.receipts = receipts
        self.stamp = stamp()
        self._logs = 0
        self.door = None  # main's check_door record: the declaration this run is bound to (door_of)

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


def run_helper(body, params, *, mounts, network='none', timeout=60, sensitive=False, journal_run=True,
               own_session=False) -> dict:
    """Run fixed helper code as root; return its final JSON line. ``sensitive`` drops stderr. Release 1 (A13): each run
    is one line of the one-shot journal (its name and exit code, never a value or its output) - except the journal's own
    write (``journal_run`` False), which the receipt records instead. ``own_session``: its docker CLI runs in a session
    of its own, which no signal sent to the installer's process group reaches (the RAM folder's wipe: RamFiles)."""
    token = secrets.token_hex(12)
    name = f'cpt-studio-helper-{token}'
    source = helper_source(body, params).encode()
    proc = None
    try:
        proc = subprocess.run(helper_argv(name, token, mounts, network, time.time() + timeout), input=source,
                              capture_output=True, timeout=timeout + 15, env=COMMAND_ENV, start_new_session=own_session)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            if journal_run:
                journal('helper', helper_name(body), 'timeout' if proc is None else proc.returncode)
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

# --- release 1 (A13): the application's logs are kept, ids only --------------------------------------------------------
# Docker keeps a container's output only while the container exists (json-file, 10 MB x 5), and a deploy removes the
# parked pair (retire_parked). So before a container this installer removes is removed, its output is copied - ONLY the
# lines in a format whose variable parts hold ids, numbers, times, addresses and fixed words (KEPT_LOG_FORMATS; every
# other line, a traceback for one, is counted and dropped: a database DETAIL line or an error's text can carry document
# text, FLOW-12) - into a root-only file, LOG_DIR/containers/<role>-<revision12>-<UTC>.log (folder 0700, file 0600),
# written through the root helper. One-shots and helpers run with no log driver; each run is one line of the one-shot
# journal, LOG_DIR/oneshots-<UTC date>.log (root-only): when, the phase, what ran (a fixed label) and its exit code, the
# declaration and its commit, and a --by name - never an argument's value and never the output. Copies and journals
# older than LOG_KEEP_DAYS are deleted at each run (plain deletion: they hold ids only). Never into a receipt: a receipt
# records a copy's name, sha256 and counts. [TO CONFIRM the folder on this host.] On the new server an off-host store
# takes over (TEC-11 (5)).
LOG_DIR = '/var/log/cpt-studio'
LOG_KEEP_DAYS = 14  # owner decision D7: about two weeks on the current host
LOG_MOUNT = 'type=bind,src=/var/log,dst=/host-log'
JOURNAL = {'phase': '', 'declaration': '', 'commit': '', 'lines': [], 'overflow': 0}
JOURNAL_LIMIT = 2000  # lines one phase keeps for its journal; any more are counted (overflow), never dropped silently
JOURNAL_LABEL_RE = re.compile(r'[^A-Za-z0-9 _.:/()-]')
DOCKER_TIMESTAMP_RE = re.compile(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z ')
_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
_ADDRESS = r'(?:\d{1,3}(?:\.\d{1,3}){3}|[0-9a-f:]{2,39}(?:\.\d{1,3}){0,3}|-)'
# The fixed words of the application's routes (cptstudio/urls.py and urls_admin.py: a test holds this list to them) and
# of its static files: a path is copied only when each of its segments is one of them, an id, or a static file's name
# as the manifest names it (with its 12-hex content hash: an unhashed name is dropped).
ROUTE_WORDS = ('access', 'account', 'activity', 'add', 'answers', 'api', 'bundle', 'content', 'decisions', 'download',
               'encounters', 'enrol', 'everywhere', 'health', 'holds', 'login', 'logout', 'members', 'new', 'ops',
               'options', 'original', 'password', 'people', 'reads', 'reconcile', 'recovery', 'release', 'reports',
               'resume', 'retry', 'role', 'second-factor', 'security', 'session', 'sign-ins', 'spending', 'static',
               'stop', 'studio', 'unlock', 'workspaces', 'fonts', 'lib')
_SEGMENT = (r'(?:' + '|'.join(re.escape(word) for word in ROUTE_WORDS) + rf'|{_UUID}'
            r'|[a-z0-9_-]{1,64}\.[0-9a-f]{12}\.(?:css|js|mjs|svg|png|ico|woff2?|ttf|txt|map|json)(?:\.gz|\.br)?)')
_PATH = rf'/(?:{_SEGMENT}(?:/{_SEGMENT})*/?)?'
_METHOD = r'(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)'
# A fixed word of a worker message: a failure kind or a stage kind, never text an exception carries.
_WORD = r'[a-z][a-z_]{0,39}'
KEPT_LOG_FORMATS = {
    'web': tuple(re.compile(pattern) for pattern in (
        # gunicorn's access line in release 1's format (deploy/gunicorn.conf.py: A2)
        rf'\[\d\d/[A-Z][a-z]{{2}}/\d{{4}}:\d\d:\d\d:\d\d [+-]\d{{4}}\] {_ADDRESS} "{_METHOD} {_PATH} HTTP/\d(?:\.\d)?" '
        rf'\d{{3}} (?:\d+|-) \d+ms (?:[0-9a-f]{{32}}|-) (?:{_UUID}|-)',
        # and in the format before it (36e550ab's deploy/gunicorn.conf.py: no request id, no actor), which the retired
        # web of the release-1 install and of any switch-back to such a revision wrote (refutation round 1,
        # installer-6): its address, path, status, size and time, nothing more
        rf'\[\d\d/[A-Z][a-z]{{2}}/\d{{4}}:\d\d:\d\d:\d\d [+-]\d{{4}}\] {_ADDRESS} "{_METHOD} {_PATH} HTTP/\d(?:\.\d)?" '
        rf'\d{{3}} (?:\d+|-) \d+ms',
        # gunicorn's own life cycle
        r'\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}\] \[\d+\] \[(?:INFO|WARNING|ERROR|CRITICAL)\] '
        r'(?:Starting gunicorn [\d.]+|Listening at: http://0\.0\.0\.0:8000 \(\d+\)|Using worker: sync|'
        r'Booting worker with pid: \d+|Handling signal: [a-z0-9]+|Worker exiting \(pid: \d+\)|Shutting down: Master|'
        r'Worker \(pid:\d+\) was sent SIG[A-Z]+!?|WORKER TIMEOUT \(pid:\d+\)|Autorestarting worker after current request\.)',
        # django.request's warning and error lines name the path alone (its traceback lines are dropped)
        rf'(?:Not Found|Forbidden|Bad Request|Unauthorized|Method Not Allowed|Gone|Conflict|Payload Too Large|'
        rf'Too Many Requests|Internal Server Error|Service Unavailable): {_PATH}',
    )),
    # the worker's own messages (studio/jobs.py and run_worker's log calls), each with its ids, numbers and fixed words
    'worker': tuple(re.compile(pattern) for pattern in (
        r'CPT Studio worker (?:started|stopped)\.',
        rf'round {_UUID}: the document was not sent \({_WORD}\)',
        rf'round {_UUID}: the (?:reader|checker) answer was not readable \({_WORD}\)',
        rf'round {_UUID}: the stored conversion of round {_UUID} could not be read back; converting again',
        rf'round {_UUID}: the converted PDF could not be stored for the viewer',
        rf'round {_UUID}: coding_(?:reader|checker) refused at the ceiling \(spent \d+(?:\.\d+)?, worst case '
        rf'\d+(?:\.\d+)?\)',
        rf'round {_UUID}: the coding_(?:reader|checker) request could not be counted; nothing was sent',
        rf'the coding stage failed unexpectedly for round {_UUID}',
        rf'the coder raised while sending coding run {_UUID}',
        rf'the outcome of coding run {_UUID} could not be recorded',
        r'the token count of a coding request raised; nothing is sent',
        rf'coding run {_UUID} could not be settled (?:as not sent after its stage failed|after its outcome failed to '
        rf'record)',
        r'provider slot \d+ (?:could not be released|was no longer held when its send ended): the database session '
        r'that held it ended during the send',
        rf'stage {_WORD} failed for job {_UUID}',
        r'the worker heartbeat could not be recorded',
        r'a worker thread met an unexpected error',
        r'the stale sweep failed',
    )),
    # the converter's own messages are Lane 5's and not yet listed: every line is counted and dropped (fail closed)
    'converter': (),
}


def journal_begin(phase, door=None):
    """A13: a phase's one-shot journal starts empty, naming the phase and the declaration it runs under."""
    door = door or {}
    JOURNAL.update(phase=phase, declaration=str(door.get('declaration') or ''),
                   commit=str(door.get('declaration_commit') or ''), lines=[], overflow=0)


def journal(kind, what, exit_code, by=''):
    """A13: one journal line for a one-shot or helper run - when, the phase, what ran (a fixed label, characters
    outside JOURNAL_LABEL_RE's set replaced), its exit code, the declaration and its commit, and a --by name. Never an
    argument's value, never the output."""
    entry = {'at': utc_now(), 'phase': JOURNAL['phase'], 'kind': kind,
             'what': JOURNAL_LABEL_RE.sub('?', str(what))[:120], 'exit': exit_code,
             'declaration': JOURNAL['declaration'], 'commit': JOURNAL['commit']}
    if by:
        entry['by'] = JOURNAL_LABEL_RE.sub('?', str(by))[:80]
    if len(JOURNAL['lines']) < JOURNAL_LIMIT:
        JOURNAL['lines'].append(json.dumps(entry, sort_keys=True))
    else:
        JOURNAL['overflow'] += 1


# The root helper's writers of LOG_DIR (A13), under /var/log mounted at /host-log: each makes LOG_DIR and its
# containers/ folder root 0700 when they are missing, and refuses either when it is anything else.
_LOG_DIRS = r'''
def log_dirs():
    made = []
    for d in ('/host-log/' + P['dir'], '/host-log/' + P['dir'] + '/containers'):
        try:
            i = os.lstat(d)
        except FileNotFoundError:
            os.mkdir(d, 0o700)
            os.chown(d, 0, 0)
            os.chmod(d, 0o700)
            i = os.lstat(d)
            made.append(d[len('/host-log'):])
        if not (stat.S_ISDIR(i.st_mode) and i.st_uid == 0 and i.st_gid == 0 and stat.S_IMODE(i.st_mode) == 0o700):
            return None, made
    return '/host-log/' + P['dir'], made
'''
# One ids-only copy (the RAM-only file the installer mounted at /in/kept), written once - O_EXCL, root 0600, fsynced -
# and read back by its sha256.
H_KEEP_LOG = _LOG_DIRS + r'''
base, made = log_dirs()
if base is None:
    R = {'error': P['dir'] + ' or its containers folder is not a root-owned 0700 directory'}
else:
    data = read('/in/kept')
    if hashlib.sha256(data).hexdigest() != P['sha256']:
        R = {'error': 'the copy to keep is not the one the installer made'}
    else:
        path = os.path.join(base, 'containers', P['name'])
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchown(fd, 0, 0)
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        d = os.open(os.path.join(base, 'containers'), os.O_RDONLY | os.O_DIRECTORY)
        os.fsync(d)
        os.close(d)
        R = {'written': P['name'], 'bytes': len(data), 'sha256': hashlib.sha256(read(path)).hexdigest(), 'made': made}
print(json.dumps(R, sort_keys=True))
'''
# The one-shot journal's lines appended, each to its own UTC date's file (root 0600, append only, a regular file this
# helper made); then every copy and journal whose date is before P['cutoff'] deleted, and counted.
H_JOURNAL = _LOG_DIRS + r'''
import re
base, made = log_dirs()
if base is None:
    R = {'error': P['dir'] + ' or its containers folder is not a root-owned 0700 directory'}
else:
    files = {}
    for date, lines in sorted(P['lines'].items()):
        path = os.path.join(base, 'oneshots-' + date + '.log')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            i = os.fstat(fd)
            if not (stat.S_ISREG(i.st_mode) and i.st_uid == 0 and stat.S_IMODE(i.st_mode) == 0o600):
                os.fchown(fd, 0, 0)
                os.fchmod(fd, 0o600)
            os.write(fd, ''.join(line + '\n' for line in lines).encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        files[date] = len(lines)
    pruned = {'oneshots': 0, 'containers': 0}
    for folder, kind, pattern in ((base, 'oneshots', r'oneshots-(\d{8})\.log'),
                                  (os.path.join(base, 'containers'), 'containers',
                                   r'[a-z]+-[0-9a-z]{1,12}-(\d{8})T\d{6}Z\.log')):
        for name in sorted(os.listdir(folder)):
            match = re.fullmatch(pattern, name)
            if match and match.group(1) < P['cutoff'] and os.path.isfile(os.path.join(folder, name)):
                os.unlink(os.path.join(folder, name))
                pruned[kind] += 1
    R = {'appended': files, 'pruned': pruned, 'made': made}
print(json.dumps(R, sort_keys=True))
'''


# A static file's name in a kept path (refutation, installer lens A-7): its name part is up to 64 characters of free text,
# so a kept line carries a fixed token in its place - the 12-hex content hash and the extension stay.
STATIC_NAME_RE = re.compile(r'(?<=/)[a-z0-9_-]{1,64}(?=\.[0-9a-f]{12}\.(?:css|js|mjs|svg|png|ico|woff2?|ttf|txt|map|json)'
                            r'(?:\.gz|\.br)?(?:[/ "]|$))')
STATIC_TOKEN = 'static-file'


def ids_only_lines(role, *streams) -> tuple:
    """(kept, dropped) of a container's output (``streams``: `docker logs --timestamps` stdout and stderr): the lines in
    one of the role's KEPT_LOG_FORMATS, each with its timestamp, in time order; every other line - a traceback, a DETAIL
    line, a line with no timestamp - counted in ``dropped`` and never copied (A13)."""
    patterns = KEPT_LOG_FORMATS.get(role, ())
    kept, dropped = [], 0
    for stream in streams:
        for line in (stream or b'').decode('utf-8', 'replace').splitlines():
            stamp_match = DOCKER_TIMESTAMP_RE.match(line)
            body = line[stamp_match.end():] if stamp_match else None
            if body is not None and any(pattern.fullmatch(body) for pattern in patterns):
                kept.append(((stamp_match.group(1), (stamp_match.group(2) or '').ljust(9, '0')),
                             STATIC_NAME_RE.sub(STATIC_TOKEN, line)))
            else:
                dropped += 1
    return [line for _, line in sorted(kept, key=lambda item: item[0])], dropped


def write_root_log(name, data: bytes) -> dict:
    """``data`` into LOG_DIR/containers/``name`` through the root helper (H_KEEP_LOG), handed over as a RAM-only file
    under /dev/shm that is wiped whatever happens (the pattern of the operators phase's password files)."""
    scratch = Path(tempfile.mkdtemp(prefix='cpt-studio-logs-', dir='/dev/shm'))
    try:
        kept = write_private(scratch, 'kept', data)
        return run_helper(H_KEEP_LOG, {'dir': PurePosixPath(LOG_DIR).name, 'name': name, 'sha256': sha256(data)},
                          mounts=[LOG_MOUNT, f'type=bind,src={kept},dst=/in/kept,readonly'])
    finally:
        for path in scratch.iterdir():
            path.write_bytes(b'\0' * min(path.stat().st_size, 1 << 20))
            path.unlink()
        scratch.rmdir()


def keep_container_log(container, role, revision=None) -> dict:
    """A13: the ids-only copy of a container this installer is about to remove - `docker logs --timestamps`, filtered by
    ids_only_lines, written root-only (write_root_log) as <role>-<revision12>-<UTC>.log. {'file', 'sha256', 'kept',
    'dropped', 'bytes'}: never a line. Raises when the output cannot be read or the copy cannot be written: the caller
    then leaves the container in place."""
    container_id = (container or {}).get('Id')
    if not container_id:
        raise InstallError(f'The {role} container to keep the log of has no id; it was left in place.')
    revision = revision or labels_of(container).get(REVISION_LABEL) or ''
    label = revision[:12] if SHA_RE.fullmatch(revision) else 'unlabelled'
    done = docker('logs', '--timestamps', container_id, check=False, timeout=120)
    if done.returncode:
        raise InstallError(f'docker logs of the {role} container {container_id[:12]} failed (exit {done.returncode}); '
                           'its log was not kept, so it was left in place.')
    kept, dropped = ids_only_lines(role, done.stdout, done.stderr)
    data = ''.join(line + '\n' for line in kept).encode()
    name = f'{role}-{label}-{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.log'
    written = write_root_log(name, data)
    if written.get('sha256') != sha256(data):
        raise InstallError(f'The {role} log copy did not read back as written; the container was left in place.')
    return {'file': f'{LOG_DIR}/containers/{name}', 'sha256': sha256(data), 'kept': len(kept), 'dropped': dropped,
            'bytes': len(data)}


def flush_journal() -> Any:
    """A13: the phase's one-shot journal appended to LOG_DIR/oneshots-<UTC date>.log and the copies and journals older
    than LOG_KEEP_DAYS deleted, through one root helper run (the one run the journal does not list: the receipt records
    it). None when the phase ran no one-shot or helper; never raises - a journal that could not be written is said in
    the receipt, and the phase's own outcome stands."""
    lines, overflow = list(JOURNAL['lines']), JOURNAL['overflow']
    JOURNAL.update(lines=[], overflow=0)
    if not lines and not overflow:
        return None
    by_date = {}
    for line in lines:
        by_date.setdefault(json.loads(line)['at'][:10].replace('-', ''), []).append(line)
    if overflow:
        by_date.setdefault(dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d'), []).append(json.dumps(
            {'at': utc_now(), 'phase': JOURNAL['phase'], 'kind': 'overflow', 'what': f'{overflow} more run(s)',
             'exit': None}, sort_keys=True))
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=LOG_KEEP_DAYS)).strftime('%Y%m%d')
    try:
        result = run_helper(H_JOURNAL, {'dir': PurePosixPath(LOG_DIR).name, 'lines': by_date, 'cutoff': cutoff},
                            mounts=[LOG_MOUNT], journal_run=False)
    except Exception as error:  # noqa: BLE001 - recorded in the receipt, never a refusal
        return {'written': False, 'why': str(error) or type(error).__name__, 'lines': len(lines),
                'overflow': overflow}
    appended, pruned = (result.get('appended'), result.get('pruned')) if isinstance(result, dict) else (None, None)

    def counts(value, keys=None):
        return (isinstance(value, dict) and (keys is None or set(value) == set(keys))
                and all(isinstance(key, str) and type(n) is int and n >= 0 for key, n in value.items()))
    # an answer that does not say what it wrote is never read as written (D66)
    if not (counts(appended) and set(appended) == set(by_date)
            and all(appended[date] == len(entries) for date, entries in by_date.items())
            and counts(pruned, ('oneshots', 'containers'))):
        return {'written': False, 'why': 'the journal helper gave no answer it could be judged by', 'lines': len(lines),
                'overflow': overflow}
    return {'written': True, 'files': {f'{LOG_DIR}/oneshots-{date}.log': count for date, count in appended.items()},
            'lines': len(lines), 'overflow': overflow, 'sha256': sha256('\n'.join(lines).encode()),
            'pruned': pruned, 'kept_days': LOG_KEEP_DAYS}


def helper_name(body) -> str:
    """The name of a root helper's fixed code (its H_* constant, lower case), for the journal."""
    for name, value in globals().items():
        if name.startswith('H_') and value is body:
            return name[2:].lower().replace('_', '-')
    for name, value in globals().items():
        if name.startswith('H_') and value == body:
            return name[2:].lower().replace('_', '-')
    return 'unnamed'

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

# Secrets are generated here, inside the helper; only names and modes leave it. The Fable coding build's set is the two
# files below: Corti's copy is no longer part of it, read or written (an earlier install's stays as it is).
H_SECRETS = '''
T = '/target'
FILES = {'app': 'app.env', 'db': 'db.env'}

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

present = {k: os.path.lexists(os.path.join(T, v)) for k, v in FILES.items()}
expected = {'app.env': {'regular': True, 'uid': 0, 'gid': 0, 'mode': '0o600'},
            'db.env': {'regular': True, 'uid': 0, 'gid': 0, 'mode': '0o600'}}
if all(present.values()):
    found = {name: describe(name) for name in expected}
    problems = [name for name in expected if found[name] != expected[name]]
    if names(read(os.path.join(T, 'app.env'))) != P['app_keys']:
        problems.append('app.env keys')
    if names(read(os.path.join(T, 'db.env'))) != P['db_keys']:
        problems.append('db.env keys')
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
              (stage('db.env', ('POSTGRES_PASSWORD=' + password + '\\n').encode(), 0, 0o600), 'db.env')]
    for tmp, name in staged:
        os.link(tmp, os.path.join(T, name))
        os.unlink(tmp)
    d = os.open(T, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(d)
    os.close(d)
    found = {name: describe(name) for name in expected}
    R = {'state': 'created', 'files': found}
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
# the secrets phase, then the app phase, whose new worker mounts the new file). Values never leave the helper. The Fable
# coding build runs it over the coder's Anthropic file alone (coding_secrets): the rules are the participants', kept.
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

# The root helper's vhost operations (H_VHOST, assembled below with the installer's own nginx reader). They write only
# quillmd-cpt (its file and sites-enabled link) and - in the two-file operations alone - the quillmd vhost's file, to one
# of its two pinned states and nothing else. Every operation holds the coupling invariant (ops/INSTALL.md): the quillmd
# vhost is QUILLMD_VHOST_BEFORE exactly when quillmd-cpt names no admin host on 443, and QUILLMD_VHOST_AFTER exactly when
# it does. A single-file operation (install, replace, remove) starts only from a coupled state and refuses, before
# writing, a quillmd-cpt the quillmd vhost would not be coupled with. A two-file operation moves both files in the one
# safe order (refutation INGRESS-4, INSTALLER-6): couple renames quillmd-cpt FIRST and the quillmd vhost SECOND,
# decouple the quillmd vhost FIRST and quillmd-cpt SECOND, so the only state between the two renames is both files
# naming the admin host - where nginx keeps the quillmd vhost's (it loads first) and warns 'conflicting server name' -
# never a state in which nothing claims it; each accepts that state as its start, so an undo completes from wherever
# its operation stopped. Afterwards both files are read again: the quillmd vhost against the digest read at the start
# (a single-file operation; never a set membership) or the state written (a two-file operation).
_VHOST_OPS = r'''
A, E, name = '/available', '/enabled', P['name']
f, l, q = os.path.join(A, name), os.path.join(E, name), os.path.join(A, 'quillmd')
BEFORE, AFTER = P['quillmd_before'], P['quillmd_after']

def digest(path):
    with open(path, 'rb') as h:
        return hashlib.sha256(h.read()).hexdigest()

def regular(path):
    return os.path.isfile(path) and not os.path.islink(path)

def state():
    return {'file_exists': os.path.lexists(f), 'file_sha256': digest(f) if regular(f) else None,
            'link_exists': os.path.lexists(l), 'link_target': os.readlink(l) if os.path.islink(l) else None,
            'quillmd_sha256': digest(q) if regular(q) else None}

def admin_in(raw):
    return names_host_on(raw.decode('utf-8', 'replace'), P['admin_host'])

def admin_now():
    # quillmd-cpt claims the admin host only as nginx loads it: no file or no sites-enabled link claims nothing; a link
    # that is not the installer's own (another target, or not a link) cannot be told (check, round R2-1)
    if not os.path.lexists(f) or not os.path.lexists(l):
        return False
    if not os.path.islink(l) or os.readlink(l) != P['link_target']:
        return None
    return admin_in(read(f)) if regular(f) else None

def coupling(quillmd, admin):
    if admin is None or quillmd not in (BEFORE, AFTER):
        return 'uncoupled'
    if quillmd == BEFORE:
        return 'both' if admin else 'before'
    return 'after' if admin else 'uncoupled'

def write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o644)
        view = memoryview(raw)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)

def staged(path):
    return os.path.join(A, '.' + os.path.basename(path) + '.new')

def put(path, raw, exclusive):
    if exclusive:
        write(path, raw)
    else:
        write(staged(path), raw)
        os.replace(staged(path), path)

def sync(d):
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)

def pair(steps):
    # a staged file a stopped operation left (this helper's own name, in a root-only directory) is cleared first, so an
    # undo completes from where its operation stopped; then each (path, raw) not already holding raw is staged and
    # fsynced, and only then renamed, in the order given
    cleared = []
    for path, raw in steps:
        if os.path.lexists(staged(path)) and regular(staged(path)):
            os.unlink(staged(path))
            cleared.append(os.path.basename(staged(path)))
    if cleared:
        sync(A)
    todo = [(path, raw) for path, raw in steps
            if not (regular(path) and digest(path) == hashlib.sha256(raw).hexdigest())]
    made = []
    try:
        for path, raw in todo:
            write(staged(path), raw)
            made.append(staged(path))
    except BaseException:
        for path in made:
            os.unlink(path)
        raise
    renamed = []
    for path, raw in todo:
        os.replace(staged(path), path)
        sync(A)
        renamed.append(os.path.basename(path))
    return renamed, cleared

s = state()
op = P['op']
start = coupling(s['quillmd_sha256'], admin_now())
if op == 'state':
    R = {}
elif op in ('install', 'replace', 'remove') and start not in ('before', 'after'):
    R = {'error': 'the quillmd vhost and quillmd-cpt are not coupled (' + start + '); nothing was written'}
elif op == 'install':
    raw = base64.b64decode(P['content'])
    if s['file_exists'] or s['link_exists']:
        R = {'error': 'quillmd-cpt is already present'}
    elif coupling(s['quillmd_sha256'], admin_in(raw)) != start:
        R = {'error': 'the quillmd vhost would not be coupled with this quillmd-cpt; nothing was written'}
    else:
        put(f, raw, True)
        os.symlink(P['link_target'], l)
        sync(A)
        sync(E)
        R = {'done': 'installed'}
elif op == 'replace':
    raw = base64.b64decode(P['content'])
    if s['file_sha256'] != P['expected_sha256'] or s['link_target'] != P['link_target']:
        R = {'error': 'quillmd-cpt is not in the expected state'}
    elif coupling(s['quillmd_sha256'], admin_in(raw)) != start:
        R = {'error': 'the quillmd vhost would not be coupled with this quillmd-cpt; nothing was written'}
    else:
        put(f, raw, False)
        sync(A)
        R = {'done': 'replaced'}
elif op == 'remove':
    if s['file_exists'] and s['file_sha256'] not in P['allowed_sha256']:
        R = {'error': 'quillmd-cpt holds content this installer did not write'}
    elif s['link_exists'] and s['link_target'] != P['link_target']:
        R = {'error': 'the quillmd-cpt link points somewhere else'}
    elif start != 'before':
        R = {'error': 'the quillmd vhost is the after state: without quillmd-cpt nothing would claim the admin host on '
                      '443; nothing was removed'}
    else:
        if s['link_exists']:
            os.unlink(l)
            sync(E)
        if s['file_exists']:
            os.unlink(f)
            sync(A)
        R = {'done': 'removed'}
elif op in ('couple', 'decouple'):
    forward = op == 'couple'
    raw, quillmd_raw = base64.b64decode(P['content']), base64.b64decode(P['quillmd_content'])
    target_sha, target_q = hashlib.sha256(raw).hexdigest(), (AFTER if forward else BEFORE)
    admin_stage = target_sha if forward else P['expected_sha256']
    starts = [((BEFORE if forward else AFTER), P['expected_sha256']),  # the full start
              (BEFORE, admin_stage),                                  # the only state between the two renames
              (target_q, target_sha)]                                 # already written
    if hashlib.sha256(quillmd_raw).hexdigest() != target_q:
        R = {'error': 'the quillmd vhost content is not its pinned ' + ('after' if forward else 'before')
                      + ' state; nothing was written'}
    elif admin_in(raw) is not forward:
        R = {'error': 'the quillmd-cpt content ' + ('does not name' if forward else 'names')
                      + ' the admin host on 443; nothing was written'}
    elif not regular(f) or s['link_target'] != P['link_target']:
        R = {'error': 'quillmd-cpt is not the regular file and link this installer writes; nothing was written'}
    elif (s['quillmd_sha256'], s['file_sha256']) not in starts:
        R = {'error': 'the quillmd vhost and quillmd-cpt are in no state this write starts from (' + start
                      + '); nothing was written'}
    else:
        order = [(f, raw), (q, quillmd_raw)] if forward else [(q, quillmd_raw), (f, raw)]
        renamed, cleared = pair(order)
        R = {'done': 'coupled' if forward else 'decoupled', 'renamed': renamed, 'cleared': cleared}
else:
    R = {'error': 'unknown operation'}
if 'error' not in R and op != 'state':
    now = state()
    end = coupling(now['quillmd_sha256'], admin_now())
    if op in ('couple', 'decouple'):
        if (now['quillmd_sha256'], now['file_sha256'], end) != (target_q, target_sha,
                                                               'after' if forward else 'before'):
            R = {'error': 'the two files did not read back as written'}
    elif now['quillmd_sha256'] != s['quillmd_sha256'] or end != start:
        R = {'error': 'the quillmd vhost changed during the operation'}
R['state'] = state()
R['coupling'] = coupling(R['state']['quillmd_sha256'], admin_now())
print(json.dumps(R, sort_keys=True))
'''

# Host certbot through a chroot. No --agree-tos or e-mail: it cannot register a
# new ACME account, so a missing account fails instead of creating one. One order
# for every name in P['domains'], all by the one webroot, under P['cert_name'];
# never --expand (a new lineage is named, never an existing one widened).
H_CERTBOT = '''
os.chroot('/host')
os.chdir('/')
cmd = ['/usr/bin/certbot', 'certonly', '--webroot', '-w', '/var/www/certbot']
for domain in P['domains']:
    cmd += ['-d', domain]
cmd += ['--cert-name', P['cert_name'], '--non-interactive', '--keep-until-expiring', '--account', P['account']]
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

# Release 1 (A7): the convert volume's root, owned by the converter's uid with the application's group, 0750 - the
# converter makes its socket there (0660, group 10150) and the worker, of that group, can reach it; no other file.
H_CONVERT_VOLUME = '''
root = '/convert'
os.chown(root, P['uid'], P['gid'])
os.chmod(root, P['mode'])
i = os.lstat(root)
print(json.dumps({'root': {'uid': i.st_uid, 'gid': i.st_gid, 'mode': oct(stat.S_IMODE(i.st_mode))}}))
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


def coding_secrets() -> dict:
    """The Fable coder's credential (CODER; H_PARTICIPANT_SECRETS, the participants' rules): its source, when the owner
    placed it, is copied once into /etc/cpt-studio (10150:10150 0400), checked by key name only; a missing source leaves
    it 'not provided', and the coder can then only be installed disabled. The sources directory is mounted only once it
    is seen to be a root-owned 0700 directory (and the helper looks again); anything else refuses with nothing written.
    No other source is copied: the Astra (OpenAI) one is no longer read. {CODER['name']: {state, source, key_names}}. An
    answer that does not say what was done with the file refuses (DECISIONS D66: never read as "none")."""
    copied = copied_credentials({CODER['name']: CODER}, 'coding')
    entry = copied.get(CODER['name']) if isinstance(copied, dict) else None
    if not (isinstance(entry, dict) and isinstance(entry.get('state'), str)):
        raise InstallError("The copy of the coding credentials did not say what it did with the Anthropic file.",
                           details={'coding_credentials': copied})
    return {CODER['name']: entry}


LEGACY_COPY_NOTE = (f"{LEGACY_INTERPRETER_COPY}, the earlier Gemini interpreter's key copy, is left untouched: "
                    "nothing copies, mounts or reads it now, and deleting it is the owner's decision (class d)")


def legacy_copy_state(paths: object) -> Any:
    """What ``paths`` (helper_stat's answer) says of LEGACY_INTERPRETER_COPY (AMENDMENT-2 1.11): {'path', 'state':
    'present' | 'absent' | 'not read', and LEGACY_COPY_NOTE's 'note' when it is present}. Reported, never a problem:
    the installer neither writes nor removes it."""
    found = paths.get(LEGACY_INTERPRETER_COPY) if isinstance(paths, dict) else None
    if not isinstance(found, dict):
        return {'path': LEGACY_INTERPRETER_COPY, 'state': 'not read'}
    if not found.get('exists'):
        return {'path': LEGACY_INTERPRETER_COPY, 'state': 'absent'}
    return {'path': LEGACY_INTERPRETER_COPY, 'state': 'present', 'note': LEGACY_COPY_NOTE}


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
    """The installed credentials file of 'corti', of a harness participant, or of the interpreter (INTERPRETER['name'],
    'anthropic': the Fable participant's file, AMENDMENT-2 1.11)."""
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


def names_host_on(text, host, port=443):
    """Whether a server block of ``text`` that listens on ``port`` names ``host`` (an exact server_name); None when its
    braces do not balance, so it cannot be told."""
    try:
        blocks = parse_server_blocks(text)
    except ValueError:
        return None
    return any(host in block['server_names'] and any((parse_listen(args) or {}).get('port') == port
                                                     for args in block['listen'])
               for block in blocks)


# The root helper reads quillmd-cpt with the installer's own reader - the same source text, never a second copy, which
# would drift from the first the day either is fixed.
H_NGINX_READER = 'import re\n' + ''.join(getsource(function) for function in (
    nginx_tokens, parse_server_blocks, parse_listen, names_host_on))
H_VHOST = H_NGINX_READER + _VHOST_OPS


def coupling(quillmd_sha256, names_admin) -> str:
    """The coupling invariant (ops/INSTALL.md), as H_VHOST reads it: 'before' - the quillmd vhost is
    QUILLMD_VHOST_BEFORE and quillmd-cpt names no ADMIN_HOST on 443 (``names_admin`` False; an absent quillmd-cpt names
    none); 'after' - it is QUILLMD_VHOST_AFTER and quillmd-cpt names it; 'both' - BEFORE while quillmd-cpt names it, the
    only state between the two renames of the two-file write (nginx keeps the quillmd vhost's admin and warns), never
    left behind by a phase; 'uncoupled' - anything else: AFTER with no claim on admin's :443 (it would fall to a
    co-tenant's default server), a quillmd vhost in neither pinned state, or a quillmd-cpt that cannot be read
    (``names_admin`` None)."""
    if names_admin is None or quillmd_sha256 not in (QUILLMD_VHOST_BEFORE, QUILLMD_VHOST_AFTER):
        return 'uncoupled'
    if quillmd_sha256 == QUILLMD_VHOST_BEFORE:
        return 'both' if names_admin else 'before'
    return 'after' if names_admin else 'uncoupled'


def quillmd_vhost_bytes() -> bytes:
    """The quillmd vhost as it is now (world-readable; read only - only the root helper writes it)."""
    return (NGINX_AVAILABLE / 'quillmd').read_bytes()


def quillmd_bytes(raw: bytes, target: str) -> bytes:
    """The quillmd vhost's bytes in the pinned state ``target`` ('before' or 'after'), from ``raw``, its bytes in either
    pinned state: unchanged when ``raw`` already is ``target``; else line QUILLMD_ADMIN_LINE_NUMBER replaced whole
    (QUILLMD_ADMIN_LINE <-> QUILLMD_FREED_LINE) - that full line exactly once in ``raw``, at that line, every other line
    (line QUILLMD_ACME_LINE_NUMBER, admin's HTTP-01 route, among them) byte-identical - and the result's sha256 the
    pinned value of ``target``, all asserted before anything is written (refutation INGRESS-6: a substring edit would
    take admin out of the :80 block first, which serves the challenge of every lineage naming it)."""
    pinned = {'before': QUILLMD_VHOST_BEFORE, 'after': QUILLMD_VHOST_AFTER}
    if sha256(raw) == pinned[target]:
        return raw
    if sha256(raw) != pinned['after' if target == 'before' else 'before']:
        raise InstallError('The quillmd vhost is in neither pinned state (its sha256 is neither the before nor the after '
                           'one); nothing was written.')
    old, new = ((QUILLMD_ADMIN_LINE, QUILLMD_FREED_LINE) if target == 'after'
                else (QUILLMD_FREED_LINE, QUILLMD_ADMIN_LINE))
    lines = raw.split(b'\n')
    found = [index for index, line in enumerate(lines) if line == old]
    if found != [QUILLMD_ADMIN_LINE_NUMBER - 1]:
        raise InstallError(f'The quillmd vhost carries its :443 server_name line {len(found)} time(s), not once at line '
                           f'{QUILLMD_ADMIN_LINE_NUMBER}; nothing was written.')
    edited = list(lines)
    edited[found[0]] = new
    changed = [index for index, (a, b) in enumerate(zip(lines, edited)) if a != b]
    if (changed != found or len(edited) != len(lines)
            or edited[QUILLMD_ACME_LINE_NUMBER - 1] != lines[QUILLMD_ACME_LINE_NUMBER - 1]):
        raise InstallError('The quillmd vhost edit would change more than its :443 server_name line; nothing was written.')
    result = b'\n'.join(edited)
    if sha256(result) != pinned[target]:
        raise InstallError(f'The quillmd vhost edit does not give the pinned {target} sha256; nothing was written.')
    return result


def read_coupling(quillmd_sha256=None, vhost=None) -> dict:
    """{'quillmd_sha256', 'names_admin', 'coupling'} as the host files are now: the quillmd vhost by its sha256 (given,
    as a phase's nginx_file_state read it, or read here), quillmd-cpt by its bytes (absent: it names nothing; there but
    not a regular file: it cannot be told) as nginx loads it - without its sites-enabled link it names nothing, behind a
    link that is not this installer's it cannot be told. ``vhost`` is vhost_state() when the caller has read it."""
    if quillmd_sha256 is None:
        try:
            quillmd_sha256 = sha256(quillmd_vhost_bytes())
        except OSError:
            quillmd_sha256 = None
    vhost = vhost if vhost is not None else vhost_state()
    # as nginx loads it (check, round R2-1): no file or no sites-enabled link claims nothing; a link that is not this
    # installer's own cannot be told
    if not vhost['file_exists'] or not vhost['link_exists']:
        admin = False
    elif vhost['link_target'] != VHOST_LINK_TARGET:
        admin = None
    else:
        live = live_vhost_bytes()
        admin = None if live is None else names_host_on(live.decode('utf-8', 'replace'), ADMIN_HOST)
    return {'quillmd_sha256': quillmd_sha256, 'names_admin': admin, 'coupling': coupling(quillmd_sha256, admin)}


def coupling_problem(found, *, expected=('before', 'after'), remedy='') -> str:
    """The refusal when read_coupling's ``found`` is not one of ``expected``, or ''."""
    if found['coupling'] in expected:
        return ''
    said = {'before': 'the quillmd vhost names admin.quillmd.com on 443 and quillmd-cpt does not',
            'after': 'quillmd-cpt names admin.quillmd.com on 443 and the quillmd vhost no longer does',
            'both': 'both name admin.quillmd.com on 443 (a two-file write stopped half way; nginx keeps the quillmd '
                    "vhost's)",
            'uncoupled': 'the quillmd vhost and quillmd-cpt are not coupled (ops/INSTALL.md, the coupling invariant): '
                         f'the quillmd vhost sha256 is {str(found["quillmd_sha256"])[:12]}, and quillmd-cpt '
                         + {True: 'names', False: 'does not name', None: 'cannot be read for'}[found['names_admin']]
                         + ' admin.quillmd.com on 443'}[found['coupling']]
    return said + (f'; {remedy}' if remedy else '')


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
    """One H_VHOST operation as root (state, install, replace, remove; couple and decouple, the two-file write and its
    way back), under the coupling invariant it holds itself."""
    params.update(op=op, name=VHOST_NAME, link_target=VHOST_LINK_TARGET, admin_host=ADMIN_HOST,
                  quillmd_before=QUILLMD_VHOST_BEFORE, quillmd_after=QUILLMD_VHOST_AFTER)
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
    the body read (at most 64 KiB + 1 byte) under 'body'. A verified https probe also returns the DNS names of the
    certificate served ('cert_names', sorted): which lineage answered."""
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
            if verify:
                result['cert_names'] = sorted(value for kind, value in (connection.sock.getpeercert() or {}).get(
                    'subjectAltName', ()) if kind == 'DNS')
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


def own_route(key) -> bool:
    """Whether a routing_snapshot key is a route this installer answers and judges itself: every one of DOMAIN's, and
    ADMIN_HOST's on 443 alone (admin_checks). ADMIN_HOST's :80 is the quillmd vhost's block - QuillMD's, which answers
    admin's HTTP-01 challenge for every lineage naming it - so it stays a co-tenant route, watched like any other
    (refutation INSTALLER-1, INGRESS-5)."""
    return f'://{DOMAIN}:' in key or key.startswith(f'https://{ADMIN_HOST}:443@')


def routing_diff(before: dict, after: dict):
    keys = {key for key in set(before) | set(after) if not own_route(key)}
    return sorted(key for key in keys if before.get(key) != after.get(key))


# Release 1 (RELEASE-1-SPEC B7): /health/ answers a request that came through nginx (it carries X-Forwarded-For) with
# 'release_digest' - the first 16 hex characters of sha256(HEALTH_DIGEST_PREFIX + the release) - instead of 'release';
# a direct probe of the web's own port (wait_service, the container's health check) still gets 'release'. An earlier
# revision answers 'release' on both paths. HEALTH_DIGEST_PREFIX is cptstudio/settings.py's (a test pins the two).
HEALTH_DIGEST_PREFIX = 'cpt-studio-release:'


def release_digest(revision) -> str:
    """The digest a release-1 web answers through nginx for ``revision`` (B7)."""
    return sha256((HEALTH_DIGEST_PREFIX + str(revision)).encode())[:16]


# B7 is a revision's own (refutation, rollback lens B-8): it is in force exactly when the revision's health view answers
# the digest - its tree's studio/views.py names 'release_digest' - read as has_converter reads the converter. Cached:
# a revision's tree never changes.
HEALTH_DIGEST_FILE = f'{APP}/studio/views.py'
HEALTH_DIGEST_MARK = b'release_digest'
_HEALTH_DIGEST_SEEN = {}


def has_health_digest(revision) -> bool:
    """Whether ``revision``'s web answers /health/ through nginx with 'release_digest' and no 'release' (B7). A revision
    this checkout cannot read is refused, never taken for an older one (fail closed)."""
    if revision in _HEALTH_DIGEST_SEEN:
        return _HEALTH_DIGEST_SEEN[revision]
    if not SHA_RE.fullmatch(str(revision)):
        raise InstallError(f'Cannot tell whether {str(revision)[:40]!r} answers the health digest: it is not a '
                           '40-character revision.')
    done = run(['git', '-C', str(ROOT), 'cat-file', '-p', f'{revision}:{HEALTH_DIGEST_FILE}'], check=False, quiet=True)
    if done.returncode:
        raise InstallError(f'Cannot tell whether {revision[:12]} answers the health digest: this checkout cannot read '
                           f'its {HEALTH_DIGEST_FILE}. Fetch it into the act checkout, then rerun.')
    _HEALTH_DIGEST_SEEN[revision] = HEALTH_DIGEST_MARK in done.stdout
    return _HEALTH_DIGEST_SEEN[revision]


def health_ok(body, revision, *, through_nginx=False) -> bool:
    """Whether a /health/ answer is a healthy ``revision`` (B7; refutation, rollback lens B-8). Through nginx a revision
    that has B7 (has_health_digest) answers 'release_digest' equal to its digest and no 'release' - a release-bearing
    answer means B7 is not in force, and is refused; an older revision (R0, a switch-back's target) answers 'release'
    and no digest. A direct probe of the web's own port (wait_service) answers 'release' whatever the revision."""
    if not (isinstance(body, dict) and body.get('status') == 'ok' and body.get('service') == 'cpt-studio'
            and body.get('data_mode') == 'synthetic-only' and body.get('database') == 'ok'):
        return False
    if through_nginx and has_health_digest(revision):
        return 'release' not in body and body.get('release_digest') == release_digest(revision)
    return 'release_digest' not in body and body.get('release') == revision


def health_release(body):
    """What a /health/ answer names of its build, for a record: its 'release', else its 'release_digest' (B7), else
    None. A 40-character value is a release, a 16-character one a digest."""
    if not isinstance(body, dict):
        return None
    for key in ('release', 'release_digest'):
        if isinstance(body.get(key), str):
            return body[key]
    return None


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
    """scripts/check-cotenants.sh, told not to judge the installer's own hosts: CPT_INSTALLER_SKIP_HOSTS holds the exact
    host names of COTENANT_SKIP_HOSTS - an installer constant passed here alone (run never hands the script the
    operator's environment), so nobody's variable can silence a co-tenant (refutation INSTALLER-9). 'judged_skipped'
    names a skipped host the script judged anyway (a row naming it with two codes): a checkout whose script does not
    honour the skip, which preflight refuses."""
    proc = run(['bash', str(ROOT / 'scripts' / 'check-cotenants.sh')], check=False, timeout=120,
               env={'CPT_INSTALLER_SKIP_HOSTS': ' '.join(COTENANT_SKIP_HOSTS)})
    # a judged row is a verdict mark, the host, its expectation in any shape (a code, alternatives, a redirect or body
    # mark) and what it observed; a skipped row is marked otherwise and never read as judged (refutation R2 round 1,
    # CHECKS-4: a row whose expectation was not a bare code was invisible here, so an unhonoured skip went unseen)
    rows = re.findall(r'^\s+[\U0001F7E2\U0001F534\U0001F7E1]\s+(\S+)\s+(\S+)\s+(\S+)',
                      proc.stdout.decode('utf-8', 'replace'), re.M)
    observed = {host: got for host, _want, got in rows}
    return {'returncode': proc.returncode, 'observed': observed, 'skipped': list(COTENANT_SKIP_HOSTS),
            'judged_skipped': sorted(set(observed) & set(COTENANT_SKIP_HOSTS))}


def cpt_probes() -> dict:
    return {'http': probe('http', DOMAIN, '/', connect_ip='127.0.0.1', method='HEAD'),
            'https': probe('https', DOMAIN, '/', connect_ip='127.0.0.1', verify=False, method='HEAD')}


# --- docker objects ----------------------------------------------------------------

def inspect(kind, name):
    """What docker inspects ``name`` as (one object), or None when docker answers that there is no such one. An answer
    that is not one object raises, never read as none (refutation round 3, installer-0: no pair at all is a reading a
    disposal step acts on)."""
    proc = docker(kind, 'inspect', name, check=False, timeout=30)
    if proc.returncode == 0:
        try:
            found = json.loads(proc.stdout)[0]
        except (ValueError, LookupError, TypeError):
            found = None
        if not isinstance(found, dict):
            raise InstallError(f'docker {kind} inspect {name} answered something that is not one {kind}.')
        return found
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


# The worker's container limits (memory and swap, pids, the /tmp tmpfs): service_args starts it with them, and the image
# phase's conversion gate (image_conversion) converts a Word file under the same ones, so the gate is the worker's case.
WORKER_LIMITS = ('1536m', 256, '1g')


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


def coding_mode(args) -> str:
    """The Fable coder's mode from --coding-mode; 'disabled' when not given (or for an args object that does not name
    it), as every one-shot runs it. app refuses to run without it given (argument_problem)."""
    mode = getattr(args, 'coding_mode', None) or 'disabled'
    if mode not in CODING_MODES:
        raise InstallError(f'The coding mode must be one of {", ".join(CODING_MODES)}, not {mode!r}.')
    return mode


def participant_mount(name) -> str:
    """A participant's credentials file, read-only at the worker's path (HARNESS.md 8)."""
    spec = PARTICIPANTS[name]
    return f'type=bind,src={spec["target"]},dst={spec["mounted"]},readonly'


def interpreter_mount() -> str:
    """The interpreter's credentials file, read-only at the worker's path (D14; AMENDMENT-2 1.11: the Fable
    participant's file, so this is participant_mount(INTERPRETER_SHARES) to the byte)."""
    return f'type=bind,src={INTERPRETER["target"]},dst={INTERPRETER["mounted"]},readonly'


def coder_mount() -> str:
    """The Fable coder's credentials file, read-only at the worker's path (CODER: the same file and path as the Fable
    participant's and the interpreter's, so this is interpreter_mount() to the byte)."""
    return f'type=bind,src={CODER["target"]},dst={CODER["mounted"]},readonly'


def worker_credential_mounts(participants: list[str] | tuple[str, ...], interpreter: bool,
                             coder: bool = False) -> list[str]:
    """The credentials binds of a worker - or of a one-shot in its layout - that holds the files of ``participants``
    (participant names) and, when ``interpreter`` is true, the interpreter's, and when ``coder`` is true, the Fable
    coder's: each file bound ONCE (AMENDMENT-2 1.11: the interpreter's file is the Fable participant's, and the coder's
    is that same file, so a worker with more than one of them live binds it one time; Docker refuses a container that
    names one destination twice). The participants' come first, in their order, then the interpreter's and the coder's
    when each is a file of its own."""
    binds = ([participant_mount(name) for name in participants] + ([interpreter_mount()] if interpreter else [])
             + ([coder_mount()] if coder else []))
    return list(dict.fromkeys(binds))


# The Fable coding build's two owner figures (the build specification, sections 3.1 and 3.2; DECISIONS D325 (3)'s rule,
# class d, which made the question stage's two figures settings) - the spending ceiling of one document, its revision,
# over every round (DOCUMENT_CEILING_USD: a send whose worst case would pass it fails its round, never sent) and the
# documents coded at once (CONCURRENT_DOCUMENTS: the worker's threads, each holding one provider slot) - are settings,
# never constants of this script: every container this installer starts (the web, the worker and each one-shot:
# runtime_env) is given both, at the values the revision's own cptstudio/settings.py gives them (coding_figures reads
# its defaults - 25 US dollars a document and 4 documents at once, the specification's - without running it), so the
# installed environment states them and settings.py stays their one copy. They replace the question stage's pair
# (QUESTION_DOCUMENT_CEILING_USD, QUESTION_ROUND_CONCURRENCY), which no container is given now: an earlier revision's
# pair a switch-back starts reads its own defaults for them, the values this installer gave before.
CODING_FIGURES = ('DOCUMENT_CEILING_USD', 'CONCURRENT_DOCUMENTS')
SETTINGS_SOURCE = SELF.parents[1] / 'cptstudio' / 'settings.py'


def coding_figures(source: str | None = None) -> dict[str, str]:
    """{'CPT_STUDIO_<name>': value} for each of CODING_FIGURES: the default the revision's cptstudio/settings.py gives
    it (its one ``_env('<name>', '<value>')`` call, read with ast - nothing is imported or run; ``source``: that file's
    text, read from SETTINGS_SOURCE when not given), checked as a setting of its kind is checked - the ceiling a
    non-negative amount of US dollars, the concurrency a whole number of documents, at least 1. InstallError when a
    figure is missing, given more than once or malformed: no container is started without both."""
    from decimal import Decimal, InvalidOperation

    text = source if source is not None else SETTINGS_SOURCE.read_text(encoding='utf-8')
    found: dict[str, list[str]] = {name: [] for name in CODING_FIGURES}
    for node in ast.walk(ast.parse(text)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_env'
                and len(node.args) == 2 and not node.keywords):
            continue
        named, given = node.args
        if (isinstance(named, ast.Constant) and isinstance(named.value, str) and named.value in found
                and isinstance(given, ast.Constant) and isinstance(given.value, str)):
            found[named.value].append(given.value)
    figures: dict[str, str] = {}
    for name, values in found.items():
        if len(values) != 1:
            raise InstallError(f'cptstudio/settings.py gives {name} {len(values)} defaults, not one; nothing was '
                               'started.')
        value = values[0]
        if name == 'DOCUMENT_CEILING_USD':
            try:
                amount = Decimal(value)
            except InvalidOperation:
                amount = None
            good = amount is not None and amount.is_finite() and amount >= 0
        else:
            good = value.isascii() and value.isdigit() and int(value) >= 1
        if not good:
            raise InstallError(f'cptstudio/settings.py gives {name} the default {value!r}, which it would refuse; '
                               'nothing was started.')
        figures[f'CPT_STUDIO_{name}'] = value
    return figures


def runtime_env(provider_mode, authorization_ref, *, credentials=False, participants=None, files=(), interpreter=None,
                interpreter_file=False, coding=None, coding_file=False):
    """-e flags. Each harness participant is named with its mode - ``participants`` maps them; one not given is
    disabled, as in every one-shot - and a live one (or one in ``files``) with its credentials path. The interpreter is
    named with its mode (``interpreter``; disabled when not given, as in every one-shot), its credentials path when it
    is live (or ``interpreter_file``), and the replay directory when it replays (tests/fixtures/interpretation/; the
    image ships no Fable recording, so a replayed interpreter fails every reading unsent). Those are an earlier
    revision's modes, which only a switch-back gives anything but disabled. The Fable coder is named with its mode
    (``coding``: CODING_MODES; disabled when not given, as in every one-shot) and its credentials path when it is live
    (or ``coding_file``). Every container is given the coder's effort (CODING_EFFORT) and the two owner figures
    (CODING_FIGURES, at the revision's settings values)."""
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
    coder = coding or 'disabled'
    if coder not in CODING_MODES:
        raise InstallError(f'The coding mode must be one of {", ".join(CODING_MODES)}, not {coder!r}.')
    values[CODER['mode_env']] = coder
    values[CODER['effort_env']] = CODING_EFFORT
    if coder == 'live' or coding_file:
        values[CODER['file_env']] = CODER['mounted']
    values.update(coding_figures())  # the owner's two figures, as settings
    flags = []
    for name, value in values.items():
        flags += ['-e', f'{name}={value}']
    return flags


def service_args(role, image_id, revision, provider_mode, authorization_ref, participants=None, *, name=None,
                 port=WEB_PORT, interpreter=None, coding=None):
    """docker run arguments for a long-running role; secrets arrive on stdin as an env-file. ``participants`` maps each
    harness participant to its mode (disabled when not given), ``interpreter`` is the interpreter's and ``coding`` the
    Fable coder's (each disabled when not given). A web is named ``name`` (the incoming web of a blue/green install:
    INCOMING_WEB) and publishes 127.0.0.1:``port``; every other argument is the same."""
    live = provider_mode == 'live'
    modes = {name: (participants or {}).get(name) or 'disabled' for name in PARTICIPANTS}
    interpreting = interpreter or 'disabled'
    coder = coding or 'disabled'
    container = name or SERVICES[role]
    if container not in ((SERVICES['web'], INCOMING_WEB) if role == 'web' else (SERVICES['worker'],)):
        raise InstallError(f'{container} is not a name a CPT Studio {role} is started under.')
    upstream(port)  # one of WEB_PORTS, or refused
    common = ['--name', container, '--pull=never', '--restart', 'unless-stopped', '--network', NETWORK,
              '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}={role}', '--label', f'{REVISION_LABEL}={revision}',
              '--log-opt', 'max-size=10m', '--log-opt', 'max-file=5', '--stop-timeout', str(STOP_SECONDS[role]),
              '--mount', f'type=volume,src={FILES_VOLUME},dst={STATE_DIR}', '--env-file', '/dev/stdin']
    environment = runtime_env(provider_mode, authorization_ref, credentials=live, participants=modes,
                              interpreter=interpreting, coding=coder)
    if role == 'web':
        # The path, never the file. A context change in the web builds the request it would send to tell a
        # re-check from a re-send (jobs._run_answers); building a request opens nothing, and only the worker
        # sends. Without the path, live mode had no provider in the web, so every setting or billing save
        # re-predicted and the worker re-sent a failed or not-sent request (pre-install review, 2026-10-26).
        # A live harness participant alike: its adapter builds requests without credentials (HARNESS.md 8). And the
        # interpreter alike (design/FINAL.md 13; its adapter reads the key only to send, interpretation.fable_adapter),
        # and the Fable coder (CODER: only the worker sends).
        return [*common, *hardening('768m', 128, '256m'), '-p', f'127.0.0.1:{port}:8000', *environment,
                image_id, 'web']
    # release 1 (A7): a revision that has the converter mounts its socket's volume (read-only: connecting needs no write)
    # and is told the socket and that it is required, so it never converts in-process; an older revision's worker - a
    # switch-back to the pair before release 1 - is started exactly as before
    extra = (['--mount', f'type=volume,src={CONVERT_VOLUME},dst={CONVERT_DIR},readonly,volume-nocopy',
              '-e', f'CPT_STUDIO_CONVERTER_SOCKET={CONVERTER_SOCKET}', '-e', 'CPT_STUDIO_CONVERTER_REQUIRED=1']
             if has_converter(revision) else [])
    extra += ['--mount', f'type=bind,src={CORTI_TARGET},dst={CREDENTIALS_IN_CONTAINER},readonly'] if live else []
    # the worker alone holds a live participant's key, the live interpreter's (D14) and the live coder's, each file
    # once: the interpreter's and the coder's are the Fable participant's (AMENDMENT-2 1.11; CODER), one bind target
    # whichever of them is live
    for bind in worker_credential_mounts([name for name, mode in modes.items() if mode == 'live'],
                                         interpreting == 'live', coder == 'live'):
        extra += ['--mount', bind]
    return [*common, *hardening(*WORKER_LIMITS), '--no-healthcheck', *extra, *environment, image_id, 'worker']


# The database container's limits (db_args) and what db_container_problems holds an existing one to (RELEASE-1-SPEC A3):
# memory and memory + swap equal, so the database never swaps to the host's unencrypted swap file, its own cgroup
# agreeing (memory.swap.max 0); core dumps off; every capability dropped; a 128 MiB /dev/shm.
DB_MEMORY = '512m'
DB_MEMORY_BYTES = 512 * 2 ** 20
DB_SHM_BYTES = 128 * 2 ** 20
# A3: an existing container whose limits differ is updated in place (docker update: no restart, no connection dropped)
# only while its memory peak stays below this share of DB_MEMORY_BYTES; otherwise the db phase refuses and prints the
# numbers, so the owner can choose a larger limit (a database that needs more than 512 MiB without swap would be killed).
DB_PEAK_SHARE = 0.8
# The container's own cgroup (v2) files, read inside it (/sys/fs/cgroup is the container's cgroup there). memory.swap.peak
# is the swap's high-water mark (refutation round 1, installer-2: swap used earlier and since paged back counts too).
DB_CGROUP_FILES = ('memory.max', 'memory.swap.max', 'memory.peak', 'memory.swap.current', 'memory.swap.peak')
# A5 (FLOW-13): the database's own log never holds statement text - a failed statement is logged without the statement
# (log_min_error_statement panic) and without DETAIL, which can quote values (log_error_verbosity terse). Set with ALTER
# SYSTEM (postgresql.auto.conf on the data volume, applied by a reload: no restart) on an existing cluster, and given as
# server flags to a new one (db_args). server_side_binding stays off (FLOW-13 (2)).
DB_LOG_SETTINGS = (('log_min_error_statement', 'panic'), ('log_error_verbosity', 'terse'))


def db_args() -> list:
    return ['--name', DB_CONTAINER, '--pull=never', '--restart', 'unless-stopped', '--network', NETWORK,
            '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=db', '-p', f'127.0.0.1:{DB_PORT}:5432',
            '--user', f'{POSTGRES_UID}:{POSTGRES_UID}', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', DB_MEMORY, '--memory-swap', DB_MEMORY, '--pids-limit', '256', '--shm-size', '128m',
            '--ulimit', 'core=0', '--log-opt', 'max-size=10m', '--log-opt', 'max-file=5', '--stop-timeout', '60',
            '--mount', f'type=volume,src={DB_VOLUME},dst=/var/lib/postgresql/data',
            '-e', f'POSTGRES_USER={DB_USER}', '-e', f'POSTGRES_DB={DB_NAME}', '--env-file', '/dev/stdin',
            POSTGRES_IMAGE, *[part for name, value in DB_LOG_SETTINGS for part in ('-c', f'{name}={value}')]]


# A one-shot whose run timed out is sent its own SIGTERM and this long to record before it is removed (builder d2's
# point, repair round 2: a dispose stopped so records its run 'failed'; a command with no handler of its own - the
# entrypoint execs python as PID 1, which ignores a SIGTERM it does not handle - is removed when the time is up).
ONESHOT_STOP_SECONDS = 10


def oneshot(image_id, command, env_bytes, *, mounts=(), user=f'{APP_UID}:{APP_UID}', timeout=600,
            network=None, credentials=False, participant_files=(), environment=None, interpreter_file=False,
            coding_file=False, what=None, by=''):
    """A --rm container of the app image with provider calls disabled - Corti's, every participant's, the
    interpreter's (design/FINAL.md 13) and the Fable coder's - unless ``environment`` gives its -e flags; returns the
    completed process. ``credentials``, ``participant_files`` (participant names), ``interpreter_file`` and
    ``coding_file`` mount those credentials files read-only at the worker's paths, each file once
    (worker_credential_mounts). Release 1 (A13): it runs with no log driver, so each run is one line of the one-shot
    journal - ``what`` (a fixed label: app_script's, the manage phase's command name; else the command's own words
    without a value, oneshot_label), its exit code and ``by`` (a --by name) - never an argument's value or the output."""
    name = f'cpt-studio-oneshot-{secrets.token_hex(8)}'
    if credentials:
        mounts = [*mounts, f'type=bind,src={CORTI_TARGET},dst={CREDENTIALS_IN_CONTAINER},readonly']
    mounts = [*mounts, *worker_credential_mounts(participant_files, interpreter_file, coding_file)]
    if environment is None:
        environment = runtime_env('disabled', '', credentials=credentials, files=participant_files,
                                  interpreter_file=interpreter_file, coding_file=coding_file)
    argv = [DOCKER, 'run', '--rm', '--name', name, '--pull=never', '--network', network or NETWORK,
            '--no-healthcheck', '--log-driver=none', '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=oneshot',
            *hardening('768m', 128, '256m', user=user), '--env-file', '/dev/stdin', *environment,
            *[part for mount in mounts for part in ('--mount', mount)], image_id, *command]
    result, timed_out = None, False
    try:
        result = run(argv, input=env_bytes, timeout=timeout, check=False)
        return result
    except InstallError:  # with check=False, run raises one only for its own timeout
        timed_out = True
        raise
    finally:
        journal('oneshot', what or oneshot_label(command), 'timeout' if result is None else result.returncode, by=by)
        # refutation round 2, installer-1: once the act answered, a daemon error or a signal in this check replaced the
        # return, so the act's answer, and its whole record, were lost after it ran. A run that gave no answer (a
        # timeout, an interrupt) is looked for here; one that answered is looked for only when docker may have left
        # its container (round 3, installer-3: its --rm removal failed, 125, or its CLI died while it ran on), and
        # nothing there takes the answer away (remove_answered_oneshot)
        if result is not None:
            if oneshot_may_be_left(result):
                remove_answered_oneshot(name, result)
        else:
            leftover = inspect('container', name)
            if leftover is not None and owned(leftover, 'oneshot'):
                if timed_out:  # its own SIGTERM first; never after an interrupt, where the door's SIGKILL follows
                    try:  # its SIGTERM by 15 s, which the RAM folder's wipe and the receipt need
                        docker('stop', '--time', str(ONESHOT_STOP_SECONDS), leftover['Id'], check=False,
                               timeout=ONESHOT_STOP_SECONDS + 30)
                    except InstallError:  # the stop's own timeout: the removal below forces it
                        pass
                docker('rm', '--force', leftover['Id'], check=False)


# The docker CLI's own failure, as `docker run` answers it: among others, a --rm removal that failed once the container
# had ended (the act may have answered whole first), and a wait on the daemon that broke while the container ran on.
DOCKER_RUN_FAILED = 125


def oneshot_may_be_left(result) -> bool:
    """Whether a one-shot that answered ``result`` may have left its container (refutation round 3, installer-3): the
    CLI's own failure (DOCKER_RUN_FAILED), or a CLI killed by a signal (a negative return code; its container runs on).
    Every other answer is the act's own exit, after which `docker run --rm` has removed the container."""
    return result.returncode == DOCKER_RUN_FAILED or result.returncode < 0


def remove_answered_oneshot(name, result) -> None:
    """The one-shot ``name``, which answered ``result`` yet may be left (oneshot_may_be_left): looked for, sent its own
    SIGTERM with ONESHOT_STOP_SECONDS to record (a disposal still running records its run 'failed'), then removed - so
    no act runs on outside the receipts' lock, nor keeps the secrets of its --env-file, once the installer has its
    answer. The act answered, so nothing here takes the answer away (refutation round 2, installer-1): a daemon error or
    a timeout here is left at that (the answer's own exit says the run failed), and a signal or a Ctrl-C - the one-shot
    then removed at once, as an interrupted run's is - is raised carrying the answer (oneshot_answer_of)."""
    found = None
    try:
        found = inspect('container', name)
        if found is not None and owned(found, 'oneshot'):
            try:
                docker('stop', '--time', str(ONESHOT_STOP_SECONDS), found['Id'], check=False,
                       timeout=ONESHOT_STOP_SECONDS + 30)
            except InstallError:  # the stop's own timeout: the removal below forces it
                pass
            docker('rm', '--force', found['Id'], check=False)
    except Exception:  # noqa: BLE001 — the answer stands (installer-1)
        pass
    except BaseException as error:  # a signal or a Ctrl-C: raised once the one-shot is removed, carrying the answer
        error.oneshot_answer = result
        if found is None or owned(found, 'oneshot'):  # the name is this run's own (random): never another's container
            try:
                with signals_deferred():
                    docker('rm', '--force', name if found is None else found['Id'], check=False)
            except BaseException:  # noqa: BLE001 — the signal that stopped the check is the one raised
                pass
        raise


def oneshot_answer_of(error):
    """The answer a one-shot gave before a signal or a Ctrl-C reached its leftover check (remove_answered_oneshot),
    carried by ``error`` or by an error it was raised over (its context: the RAM folder's wipe failing as the signal
    went by), else None - for the acts that keep their record once they answered."""
    for _ in range(8):  # a short chain: the act's one-shot, then its RAM folder's wipe or an export's seal
        if error is None:
            return None
        answer = getattr(error, 'oneshot_answer', None)
        if answer is not None:
            return answer
        error = error.__context__
    return None


def oneshot_label(command) -> str:
    """A one-shot's journal label from its command, never an argument's value: the role, and for 'manage' the
    management command's name ('manage provision', 'manage migrate')."""
    words = [str(word) for word in command[:2]]
    return ' '.join(words) if words[:1] == ['manage'] else (words[0] if words else '')


# The credentials checks run in the image whose worker will read the file (check_credential_parsing). Corti's, a
# participant's and the interpreter's exist only in a pair before the Fable coding build, so only a switch-back to such
# a pair runs them, in ITS image, which has those modules (this revision's image has none: its app phase starts every
# one of them disabled, so none of these three is run in it). The coder's runs in this revision's image (app,
# --coding-mode live) or in the image of a later pair of this design a switch-back returns to.
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
# The interpreter's, likewise (design/FINAL.md 13: "the offline loader check follows the existing pattern"): the loader
# its adapter reads the key with (AMENDMENT-2 1.11: interpretation.fable_adapter.load_anthropic_credentials, the
# participants' own loader of the shared Fable file, ANTHROPIC_API_KEY required and ANTHROPIC_WORKSPACE_ID optional), in
# the worker's mount layout, offline, with the interpreter itself disabled. It proves, too, that this revision's image
# imports the adapter the interpreter sends through; an earlier image that has none fails it, so a switch-back to a
# revision before AMENDMENT-2 runs its interpreter disabled or replayed only.
INTERPRETER_CREDENTIALS_CHECK = ('from django.conf import settings\n'
                                 f'from {INTERPRETER["module"]} import {INTERPRETER["loader"]}\n'
                                 f'{INTERPRETER["loader"]}(settings.{INTERPRETER["setting"]})\n'
                                 f"print('{INTERPRETER['name']}-credentials-parse-ok')\n")
# The Fable coder's, likewise: its own loader (CODER: studio.fable.credentials.load_anthropic_credentials, the strict
# reader moved from the participants - a regular file, not a link, owner-only, at most 32,000 bytes, KEY=VALUE,
# ANTHROPIC_API_KEY required and ANTHROPIC_WORKSPACE_ID optional), in the worker's mount layout, offline, with the coder
# itself disabled: format and permissions only, before anything changes. It proves, too, that the image imports the
# package the coder sends through; an image before the Fable coding build has none and fails it, so a switch-back to
# such a revision gives --coding-mode disabled (its pair reads no coding mode).
CODING_CREDENTIALS_CHECK = ('from django.conf import settings\n'
                            f'from {CODER["module"]} import {CODER["loader"]}\n'
                            f'{CODER["loader"]}(settings.{CODER["setting"]})\n'
                            "print('coding-credentials-parse-ok')\n")

# Run by `manage shell -c` in an image of the app (APP_SCRIPT_PRELUDE gives it P, the parameters, and ANSWER); each
# prints one ANSWER line. Which image runs each one (ops/INSTALL.md, "Which image runs each in-image script"):
#   this revision's own image - INSTALL_COUNTS, V1_ROWS and RECOMPUTE_STATES (app), UNDO_HAZARDS_READ,
#       TOUCHED_SINCE_READ, CLOSE_STAGES and CODING_MADE (every undo of this revision's pair: switch-back, rollback-app,
#       the app phase's own undos), LICENSE_NOTE_FIX, OPERATOR_ACCOUNTS and OPERATOR_CHECK: they import only modules
#       of the Fable coding build (studio.jobs, studio.models, studio.state, studio.operator, studio.reference);
#   the image of the pair the rows are handed to - PUT_BACK_STATES (put_back_states), which reads that image's own
#       derivation (studio.state in an image of the Fable coding build, studio.review in one before it);
#   any revision's image - UNRUNNABLE_STAGES (the app phase's read, and stage_kinds_of for the worker an undo starts
#       next) and TARGET_MODEL_READS (the revision a switch-back returns to), which use only what every revision's
#       studio.jobs and studio.models have.
APP_SCRIPT_ANSWER = 'cpt-studio-answer '
APP_SCRIPT_PRELUDE = 'import base64, json\nP = json.loads(base64.b64decode({payload!r}))\nANSWER = {answer!r}\n'
# The stage kinds every revision of the pipeline before the Fable coding build runs (the installed revision 057a7d39's
# STAGES): the kinds an undo assumes the next worker runs when it has no image to ask (refutation p1, security-0), so it
# closes more, never less. The Fable coding build's worker runs one kind, CODE_KIND (studio.jobs.CODE), which no worker
# before it runs: every undo whose next worker is one of those closes this revision's open coding jobs (CLOSE_STAGES).
COMMON_STAGE_KINDS = ('analyze', 'assess', 'extract', 'predict')
CODE_KIND = 'code'
# The reading stage kinds of the pipeline before the Fable coding build (the Gemini migration's interpret, design v2's
# appraise, round r3's question). This revision's close never names them as reading stages it closed, nor any pending
# update or set-back value (CLOSE_STAGES has no 'reading_closed', 'update_pending' or 'reverted'), so the undo's note
# plumbing below that reads them (with_update_note, _undo_parts) always finds nothing to add; the kinds stay named so
# a close answer that names one is still judged, never read as none.
APPRAISE_KIND = 'appraise'
QUESTION_KIND = 'question'
READING_STAGE_KINDS = ('interpret', APPRAISE_KIND, QUESTION_KIND)
# What this revision recorded that an earlier revision's web and worker would act on wrongly under their own rules,
# read in this revision's image (undo_hazards). {encounter id: reasons}:
#   unknown - a coding run (studio.jobs.PURPOSES: the reader's and the checker's sends) whose outcome is still unknown and
#             not reconciled. The earlier revision reads every unknown run of an encounter as an outcome its member must
#             reconcile there, and its reconcile allows "one new attempt" by its own rules - a paid Corti predict for an
#             encounter of its own with a context - for a request it never made. It is reconciled on this revision's
#             operator console (studio.jobs.reconcile) before the rows are handed back.
# Release 1's disposal rows are read by an earlier revision too, and shown wrongly (a closed practice takes uploads, a
# destroyed document's tombstone is listed): they are no undo hazard - they are never undone - but refuse every way back
# to a revision without disposal (disposal_refusal; refutation round 1, rollback-1 and rollback-2).
# Nothing else this revision writes is read by an earlier revision: it never writes an assessment, a proposal, a
# clarification, a decision, a member's answer, a context or an event inventory, so none of the earlier pipeline's own
# reasons (a second review, a participant, a member's answer, a modifier, a reinstatement, a request it would send
# again, a member date conflict) can be this revision's record. Its own records - coding rounds, answers, code decisions
# and exports - are in tables no earlier revision reads (no row of the four new tables is deleted; closed rounds are
# marked cancelled - failed as unknown when a request was in flight - and CODING_MADE's declared note says what is not
# carried back), and the earlier revision recomputes the stored state of every encounter this revision coded
# with its own derivation (PUT_BACK_STATES). CLOSE_STAGES adds one more reason to its own answer, read after it closed:
#   open_stage - a stage the next worker cannot run is still queued or running (a coding job made after the close's
#             transaction by this revision's web, still serving before a switch-back's B6). It is closed again by the
#             next close (B7, once that web is drained); the previous worker is held while one stands.
UNDO_HAZARDS = '''
def undo_hazards():
    """{encounter id: reasons}: the coding runs whose outcome is still unknown and not reconciled ('unknown')."""
    from studio import jobs, models
    Run = models.ProviderRun
    found = {}
    for pk in (Run.objects.filter(state=Run.UNKNOWN, reconciled_at__isnull=True, purpose__in=list(jobs.PURPOSES))
               .values_list('encounter_id', flat=True)):
        found.setdefault(str(pk), set()).add('unknown')
    return {pk: sorted(reasons) for pk, reasons in sorted(found.items())}


def touched_since(since):
    """DECISIONS D51: the encounters (ids, as strings) with a record CREATED at or after ``since`` - an encounter, a
    revision, a provider run (or its reconciliation), a stage, a coding round, an answer, a code decision, an export,
    or one of the earlier pipeline's records. Only creations and members' and operators' acts count: an installer's own
    close and put-back write finish times and stored states, never these. An encounter with none holds only what the
    pair before this one left there."""
    from studio import models
    out = set()
    rows = [(models.Encounter, 'created_at', 'pk'), (models.SourceRevision, 'created_at', 'encounter_id'),
            (models.ProviderRun, 'created_at', 'encounter_id'), (models.ProviderRun, 'reconciled_at', 'encounter_id'),
            (models.Job, 'created_at', 'encounter_id'), (models.CodingRound, 'created_at', 'encounter_id'),
            (models.CodingAnswer, 'answered_at', 'encounter_id'), (models.CodeDecision, 'created_at', 'encounter_id'),
            (models.ExportArtifact, 'created_at', 'encounter_id'),
            # the earlier pipeline's records, which this revision never writes: a member of the earlier web could
            (models.EncounterContext, 'created_at', 'encounter_id'), (models.Assessment, 'created_at', 'encounter_id'),
            (models.Clarification, 'created_at', 'encounter_id'), (models.Decision, 'created_at', 'encounter_id'),
            (models.MemberAnswer, 'answered_at', 'encounter_id'), (models.ReportArtifact, 'generated_at', 'encounter_id')]
    for model, field, key in rows:
        out.update(str(pk) for pk in model.objects.filter(**{f'{field}__gte': since}).values_list(key, flat=True)
                   if pk is not None)
    return out
'''
UNDO_HAZARDS_READ = UNDO_HAZARDS + "print(ANSWER + json.dumps({'hazards': undo_hazards()}))\n"
# DECISIONS D51: the encounters with a record created since this revision's pair (P['since']), in this revision's image.
TOUCHED_SINCE_READ = (UNDO_HAZARDS + "import datetime as _dt\n"
                      "print(ANSWER + json.dumps({'touched': sorted(touched_since(_dt.datetime.fromisoformat("
                      "P['since'])))}))\n")
# DECISIONS D51: what the PREVIOUS revision reads of the records the earlier pipeline's hazard reasons named - run in the
# previous image, with what every revision's studio.jobs and studio.models have. A member's answer as the completion
# repair reads it (its re-made assessment, support 'answered'; jobs.recompute_after_answers), and a chosen modifier
# (Decision.modifiers). This revision names neither (UNDO_HAZARDS), so what it answers removes nothing from a
# switch-back's refusal; it stays the read target_reads makes of the revision a switch-back returns to.
TARGET_MODEL_READS = '''
from studio import jobs, models
reads = []
if hasattr(models, 'MemberAnswer') and hasattr(jobs, 'recompute_after_answers'):
    reads.append('member_answer')
if any(f.name == 'modifiers' for f in models.Decision._meta.get_fields()):
    reads.append('modifier')
print(ANSWER + json.dumps({'reads': reads}))
'''
# The close of an undo (close_undone_stages), in this revision's image, before any other pair's worker runs on this
# database: the switch-back's B4 and B7, rollback-app, and the app phase's own undos. In one transaction:
#   - every coding job (CODE_KIND) still queued or running is closed when the next worker does not run that kind
#     (P['kinds'] are the kinds it runs: an earlier revision's worker has no coding stage and would end on one), or,
#     when it does (a worker of this design), each one this pair queued or started since P['since']. Its round is closed
#     as this revision's worker closes a stage it stopped (mark_stale's rule: studio.jobs.abandoned_outcome): a send
#     left sending has its request recorded UNKNOWN (sent when it called a vendor) and a reservation never sent
#     is recorded not sent; then a round with a send that may have reached the vendor with no outcome known and no
#     operator's reconcile (in flight now, or left unknown before) is failed as unknown and its job UNKNOWN, never sent
#     again (a member's retry or Resume waits for an operator's reconcile); a round with a send that failed (answered
#     and billed, or refused) is failed with that send's own kind and its job FAILED with P['failed_note']; and only a
#     round with nothing it sent unsettled is cancelled, so it reads stopped and a Resume continues it - reusing every
#     read the round already paid for - whenever this revision serves again, its job FAILED with P['code_note']. A job
#     row closed is never left cancelled: a cancelled coding job that is its revision's latest stage (a
#     member's Stop) is failed with the note too, its round left stopped, since an earlier revision counts such a job as
#     a stage it cannot run (its UNRUNNABLE_STAGES), and its installer's app refuses on one (the rollback rehearsal on
#     e426c747c7b7's own code, ops/INSTALL.md);
#   - every coding run still reserved or sending whose round has no open job (an orphan its stage left) is settled the
#     same way, so the next pair never meets a coding run in flight;
#   - every stage of another kind the next worker does not run that is queued, running, or cancelled as its encounter's
#     latest stage (what a Resume runs again) - the earlier pipeline's stages only, when the next worker cannot be asked
#     (COMMON_STAGE_KINDS) - is closed as before: FAILED with P['note'], so no earlier web offers a Resume for it, and the
#     runs it left unsettled are settled as the stale sweep settles them (sending: unknown, reserved: not sent). Nothing
#     else is touched: this revision queues no stage but a coding job, so a stage of the earlier pipeline the next
#     worker runs is that pipeline's own, and it is left to it.
# Nothing finished is touched and no row is removed: no row of the four new tables is deleted; closed rounds are marked
# cancelled (failed, as above, when a send of it is unknown or failed) - the only rows of those tables written. Then
# each encounter it closed a stage of has its stored state recomputed with this revision's derivation (studio.state),
# and the answer names, after the close: 'relabel', every encounter whose stored state this revision derived (each one
# with a coding round) or whose earlier stage this revision's worker settled since P['since'] - put_back_states gives
# each the state the pair the rows go to derives, in that pair's image; and 'hazards', what the next pair would still act
# on wrongly (UNDO_HAZARDS, with 'open_stage' for a stage it cannot run that is still queued or running).
CLOSE_STAGES = UNDO_HAZARDS + f'COMMON_STAGE_KINDS = {list(COMMON_STAGE_KINDS)!r}\n' + '''
import datetime
import uuid
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from studio import jobs, models, state
Job, Run, Round = models.Job, models.ProviderRun, models.CodingRound
CODE = jobs.CODE
since, now = datetime.datetime.fromisoformat(P['since']), timezone.now()
kept = set(P.get('kinds') or COMMON_STAGE_KINDS)
code_note = P.get('code_note') or P['note']
failed_note = P.get('failed_note') or code_note  # a coding job whose round the close fails rather than cancels


def job_round(job):  # the round a coding job names ('code:<round>' and an optional ':resume:<uuid>')
    parts = job.idempotency_key.split(':')
    try:
        return Round.objects.filter(pk=uuid.UUID(parts[1]), encounter_id=job.encounter_id).first()
    except (IndexError, ValueError):
        return None


def settle(runs):  # (sending, not sent): a send in flight becomes UNKNOWN, a reservation is recorded not sent
    sending = list(runs.filter(state=Run.SENDING))
    for run in sending:
        run.state, run.error, run.finished_at = Run.UNKNOWN, 'The worker stopped while the request was in flight.', now
        run.sent = run.sent or bool(run.endpoint)
        run.save(update_fields=['state', 'error', 'finished_at', 'sent'])
    return len(sending), runs.filter(state=Run.RESERVED).update(state=Run.NOT_SENT, error='The worker stopped before '
                                                                'sending.', finished_at=now)


def latest_stage(job):  # its revision's newest stage, of its encounter's current revision: what a Resume runs again
    return (Job.objects.filter(revision_id=job.revision_id).order_by('-created_at', '-pk').values_list('pk', flat=True)
            .first() == job.pk
            and models.Encounter.objects.filter(pk=job.encounter_id, current_revision_id=job.revision_id).exists())


closed, kinds, encounters, counted = 0, set(), set(), {'unknown': 0, 'not_sent': 0}
stopped, failed, unknown_jobs, retired, rounds = 0, 0, 0, 0, {'cancelled': 0, 'failed': 0}
code_failed = 0  # coding jobs whose round a send of it failed: the round failed with that send's kind
with transaction.atomic():
    coding = Job.objects.select_for_update().filter(kind=CODE, state__in=(Job.QUEUED, Job.RUNNING))
    if CODE in kept:  # the next worker runs coding jobs: only this pair's own are closed
        coding = coding.filter(Q(created_at__gte=since) | Q(started_at__gte=since))
    for job in coding.order_by('created_at', 'pk'):
        round_ = job_round(job)
        if round_ is not None:
            runs = Run.objects.filter(purpose__in=list(jobs.PURPOSES), scope__round=str(round_.pk))
        else:
            runs = Run.objects.filter(revision_id=job.revision_id, purpose__in=list(jobs.PURPOSES),
                                      created_at__gte=job.started_at or job.created_at)
        sent, unsent = settle(runs)
        counted['unknown'] += sent
        counted['not_sent'] += unsent
        # how the round ends is how its own stage would have ended it (studio.jobs.abandoned_outcome, the stale sweep's
        # rule, MONEY-2): unknown while a send of it may have reached the vendor with no outcome known and no
        # operator's reconcile - in flight now, or left unknown before; failed with a send's own kind when a send of it
        # failed; cancelled, for a Resume that reuses its paid reads, only when nothing it sent is unsettled
        kind = jobs.abandoned_outcome(round_) if round_ is not None else (jobs.UNKNOWN if sent else '')
        if kind == jobs.UNKNOWN:
            job.state, job.error = Job.UNKNOWN, failed_note + (' A request was in flight; its outcome is unknown.'
                                                               if sent else '')
            unknown_jobs += 1
        elif kind:
            job.state, job.error = Job.FAILED, failed_note
            code_failed += 1
        else:
            job.state, job.error = Job.FAILED, code_note
            stopped += 1
        if round_ is not None and round_.state in (Round.QUEUED, Round.RUNNING):
            Round.objects.filter(pk=round_.pk).update(**{**jobs._abandoned_fields(round_, kind), 'finished_at': now})
            rounds['failed' if kind else 'cancelled'] += 1
        job.finished_at = now
        job.save(update_fields=['state', 'error', 'finished_at'])
        closed, encounters = closed + 1, encounters | {str(job.encounter_id)}
        kinds.add(job.kind)
    if CODE not in kept:
        # a coding job a member stopped (cancelled) that is its revision's latest stage is one an earlier revision counts
        # as a stage it cannot run (its UNRUNNABLE_STAGES), and its installer's app refuses on one: failed too, with the
        # note; its round is left as it is (stopped, and resumable whenever this revision serves again)
        for job in Job.objects.select_for_update().filter(kind=CODE, state=Job.CANCELLED).order_by('created_at', 'pk'):
            if latest_stage(job):
                Job.objects.filter(pk=job.pk).update(state=Job.FAILED, error=code_note)
                retired, encounters = retired + 1, encounters | {str(job.encounter_id)}
                kinds.add(job.kind)
        closed += retired
    unrunnable, in_flight = [], Q(pk__in=())
    for pk, kind, job_state, revision_id, encounter_id, started in (
            Job.objects.exclude(kind__in=kept).exclude(kind=CODE)
            .filter(state__in=(Job.QUEUED, Job.RUNNING, Job.CANCELLED))
            .values_list('pk', 'kind', 'state', 'revision_id', 'encounter_id', 'started_at')):
        if job_state != Job.CANCELLED or (
                Job.objects.filter(revision_id=revision_id).order_by('-created_at', '-pk').values_list('pk', flat=True)
                .first() == pk
                and models.Encounter.objects.filter(pk=encounter_id, current_revision_id=revision_id).exists()):
            unrunnable.append(pk)
            kinds.add(kind)
            encounters.add(str(encounter_id))
            if job_state == Job.RUNNING and started is not None:  # what it was sending is settled with it
                in_flight |= Q(revision_id=revision_id, created_at__gte=started)
    if unrunnable:
        sent, unsent = settle(Run.objects.filter(in_flight))
        counted['unknown'] += sent
        counted['not_sent'] += unsent
        failed = Job.objects.filter(pk__in=unrunnable).update(state=Job.FAILED, error=P['note'], finished_at=now)
        closed += failed
    # a coding run still reserved or sending whose round has no open job is an orphan - its stage ended without
    # recording it (studio.jobs.mark_stale's own sweep of such runs): settled now, so the next pair never meets a run in
    # flight that no stage of its own made; the runs of a coding job left open (a next worker of this design) are its own
    open_rounds = [str(round_.pk) for round_ in (job_round(job) for job in Job.objects.filter(
        kind=CODE, state__in=(Job.QUEUED, Job.RUNNING))) if round_ is not None]
    sent, unsent = settle(Run.objects.filter(purpose__in=list(jobs.PURPOSES), state__in=(Run.SENDING, Run.RESERVED))
                          .exclude(scope__round__in=open_rounds))
    counted['unknown'] += sent
    counted['not_sent'] += unsent
for pk in sorted(encounters):
    state.refresh(models.Encounter.objects.get(pk=pk))
coded = {str(pk) for pk in Round.objects.values_list('encounter_id', flat=True)}
swept = {str(pk) for pk in Job.objects.exclude(kind=CODE).filter(finished_at__gte=since)
         .values_list('encounter_id', flat=True)}
hazards = undo_hazards()
for pk in (Job.objects.filter(state__in=(Job.QUEUED, Job.RUNNING)).exclude(kind__in=kept)
           .values_list('encounter_id', flat=True)):
    hazards[str(pk)] = sorted(set(hazards.get(str(pk), [])) | {'open_stage'})
print(ANSWER + json.dumps({'closed': closed, 'kinds': sorted(kinds), 'encounters': len(encounters),
                           'runs_unknown': counted['unknown'], 'runs_not_sent': counted['not_sent'],
                           'stopped': stopped, 'unknown': unknown_jobs, 'code_failed': code_failed,
                           'retired': retired, 'failed': failed,
                           'rounds': rounds,
                           'hazards': dict(sorted(hazards.items())), 'relabel': sorted(coded | swept)}))
'''
# The stages this image's worker cannot run (a kind its STAGES does not know) that are queued, running, or cancelled
# as their encounter's latest stage (what a Resume runs again). An earlier revision's worker, which claims a job of any
# kind, ends on one (migrate-3): stage_kinds_of reads its kinds from its own image with this. This revision's own app
# phase reads it before the switch and refuses nothing for it (phase_app): its worker claims only the kinds of its own
# STAGES (studio.jobs.claim_next), its startup sweep settles every running stage of any kind, and a member's Review
# again retires a stage of the earlier pipeline left queued (studio.decisions.retry).
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
# The stored state of every encounter this revision codes, recomputed with its own derivation (studio.state.refresh)
# once its pair has replaced the one before (phase_app; refutation p1, migrate-2: no action recomputes it until one
# touches the encounter). studio.state derives a state only for an encounter with a coding round (studio.state.compute
# is None for one without: a record of the earlier pipeline, whose stored state is left exactly as it is - the customer
# page reads it as an earlier review), so only those are read; P['encounters'], when given, narrows them. state.refresh
# writes only a state that changed; nothing is sent. The answer names each encounter whose state changed (as read, as
# derived) and counts the encounters left as they are ('kept').
RECOMPUTE_STATES = '''
from studio import models, state
coded = models.Encounter.objects.filter(rounds__isnull=False).distinct()
if P.get('encounters') is not None:
    coded = coded.filter(pk__in=P['encounters'])
changed, read = {}, 0
for encounter in coded.order_by('created_at', 'pk'):
    before, read = encounter.state, read + 1
    derived = state.refresh(encounter)
    if derived != before:
        changed[str(encounter.pk)] = [before, derived]
kept = models.Encounter.objects.exclude(pk__in=models.CodingRound.objects.values('encounter_id')).count()
print(ANSWER + json.dumps({'encounters': read, 'changed': changed, 'kept': kept}))
'''
# The stored states an undo hands to the pair the rows go to (put_back_states: CLOSE_STAGES' 'relabel'), each set to the
# state THAT pair derives, run in ITS image with its own derivation: studio.state.refresh in an image of the Fable coding
# build or later (a same-revision undo), studio.review.refresh_state in an image before it (the earlier pipeline, whose
# derivation reads its own records and never a coding round). Without it the earlier web would show a state this
# revision wrote by a name it does not know ('awaiting_answer', 'needs_review', 'ready', 'failed') or by a name it
# knows with another meaning ('processing', 'stopped', 'reviewed', 'no_codes'), until something touched the encounter.
# Only P['encounters'] (every one when it is None); each derivation writes only a state that changed; nothing is sent.
# The answer names each encounter whose state changed (as read, as derived) and the derivation it used.
PUT_BACK_STATES = '''
from studio import models
try:
    from studio import state as derivation
    refresh = derivation.refresh
except ImportError:  # an image before the Fable coding build
    from studio import review as derivation
    refresh = derivation.refresh_state
changed, rows = {}, models.Encounter.objects.order_by('created_at', 'pk')
if P.get('encounters') is not None:
    rows = rows.filter(pk__in=P['encounters'])
for encounter in rows:
    read = encounter.state
    derived = refresh(encounter)
    if derived != read:
        changed[str(encounter.pk)] = [read, derived]
print(ANSWER + json.dumps({'encounters': rows.count(), 'changed': changed, 'derivation': derivation.__name__}))
'''
# The declared note of an undo (coding_note), read in this revision's image: what this revision coded, and what of it an
# earlier revision is not handed. An earlier revision reads none of the Fable coding build's four tables, so the coding
# rounds, the members' answers, the reviewers' code decisions (approvals, rejections and revocations) and the exports
# made here stay in them - no row of the four new tables is deleted; closed rounds are marked cancelled (CLOSE_STAGES)
# - and are NOT carried back: the earlier web shows no code, answer or decision of this revision. That is the accepted
# loss of a rollback (declared before the act), never a refusing reason. Counted:
# 'encounters' (each with a coding round), of them 'created' (none of the earlier pipeline's records: no stage of
# another kind, no context, no assessment - the earlier revision holds no reading of it), 'rounds', 'answers',
# 'decisions' (rows by action), 'approved' (codes whose current decision on their encounter's latest round is an
# approval) and 'exports' (by kind). Nothing is written or sent.
CODING_MADE = '''
from studio import models, state
Round = models.CodingRound
coded = sorted({str(pk) for pk in Round.objects.values_list('encounter_id', flat=True)})
earlier = ({str(pk) for pk in models.Job.objects.exclude(kind='code').values_list('encounter_id', flat=True)}
           | {str(pk) for pk in models.EncounterContext.objects.values_list('encounter_id', flat=True)}
           | {str(pk) for pk in models.Assessment.objects.values_list('encounter_id', flat=True)})
approved = 0
for encounter in models.Encounter.objects.filter(pk__in=coded):
    latest = state.latest_round(encounter)
    approved += sum(1 for decision in state.current_decisions(latest).values()
                    if decision.action == models.CodeDecision.APPROVE)
decisions = {action: models.CodeDecision.objects.filter(action=action).count()
             for action, _ in models.CodeDecision.ACTIONS}
exports = {kind: models.ExportArtifact.objects.filter(kind=kind).count()
           for kind in (models.ExportArtifact.DRAFT, models.ExportArtifact.APPROVED)}
print(ANSWER + json.dumps({'coding': {
    'encounters': coded, 'created': sorted(set(coded) - earlier), 'rounds': Round.objects.count(),
    'answers': models.CodingAnswer.objects.count(), 'decisions': decisions, 'approved': approved,
    'exports': exports}}))
'''
# Design v2 (FINAL-V2 6.2 [R:MO-1]; step 6b): the app phase asserts on the target, before the switch, that NO DESIGN V1
# ROW exists - no Assessment whose engine_version is V1_ENGINE_VERSION and no EventInventory row whose
# interpretation_version is V1_INTERPRETATION_VERSION - and refuses otherwise. v1 rows only, by exact version: v2's own
# rows (cpt-studio-events@2, gemini-events@2/appraisal@1, read as stored), AMENDMENT-2's that the Fable interpreter
# writes (8.5: cpt-studio-events@3, gemini-events@3/appraisal@2 with gemini-inventory@3) and every legacy row never trip
# it, so a fix release after the walk, the re-install after a switch-back and a same-revision app re-run (a
# provider-mode switch, the access check run again, the recovery of a failed app: D83) all pass. (The pre-refutation
# predicate, the family cpt-studio-events@% and
# any EventInventory row, refused every install after v2's first row, on append-only tables only a deletion could
# clear.) The branch was never installed, so live holds no v1 row; a test instance's v1 rows are read as stored by
# EventReader's V1 branch and are never deleted here. The versions are the design's literals, given as P (the script
# reads no label of the image's). Read in this revision's image, after migrate (0014 makes EventInventory); nothing is
# written or sent. The Fable coding build reads neither table (both stay as legacy records, read by nothing in the
# coding path); the assertion is kept as it was, so this revision installs exactly where the one before it did.
V1_ENGINE_VERSION = 'cpt-studio-events@1'
V1_INTERPRETATION_VERSION = 'gemini-events@1'
NAMED_LIMIT = 200  # encounter ids an in-image count names (its count is complete)
V1_ROWS = '''
from studio import models
assessments = models.Assessment.objects.filter(engine_version=P['engine_version'])
inventories = models.EventInventory.objects.filter(interpretation_version=P['interpretation_version'])
named = sorted({str(pk) for pk in (*assessments.values_list('encounter_id', flat=True),
                                   *inventories.values_list('encounter_id', flat=True))})
print(ANSWER + json.dumps({'engine_version': P['engine_version'], 'interpretation_version': P['interpretation_version'],
                           'assessments': assessments.count(), 'inventories': inventories.count(),
                           'encounter_count': len(named), 'encounters': named[:P['limit']]}))
'''
# The install counts of the Fable coding build, read-only, on the target, before the switch (the app phase, after
# migrate), printed into the receipt and NEVER a refusal (a refusal on them would refuse a fix release, the re-install
# after a switch-back and a same-revision app; amendment 1, 9.5's rule). In this revision's image:
#   encounters  every encounter, and those with a coding round ('coded');
#   jobs        every stage by kind and state ({kind: {state: count}}): a stage of the earlier pipeline's kinds still
#               queued is never run by this revision's worker (studio.jobs.claim_next takes only its own kind; a member's
#               Review again retires it, studio.decisions.retry), and one still running is settled by its startup sweep;
#   runs        every provider run by purpose and state ({purpose: {state: count}});
#   unknown     the provider runs whose outcome is still unknown and not reconciled (with up to P['limit'] of their
#               encounters named), and 'in_flight': the runs left reserved or sending;
#   tables      the rows of the four tables of the Fable coding build (CodingRound, CodingAnswer, CodeDecision,
#               ExportArtifact): 0 on the first install over a revision before it;
#   holds       the standing holds (studio.jobs.standing_holds: InterpreterHold rows no release names), each of which
#               refuses every coding send until an operator releases it.
# Nothing is written or sent.
INSTALL_COUNTS = '''
from django.db.models import Count
from studio import jobs, models
Run, Job, limit = models.ProviderRun, models.Job, P['limit']


def nested(queryset, outer, inner):
    found = {}
    for row in queryset.values(outer, inner).annotate(n=Count('pk')).order_by(outer, inner):
        found.setdefault(str(row[outer]), {})[str(row[inner])] = row['n']
    return found


unknown = Run.objects.filter(state=Run.UNKNOWN, reconciled_at__isnull=True)
named = sorted({str(pk) for pk in unknown.values_list('encounter_id', flat=True)})
print(ANSWER + json.dumps({
    'encounters': {'count': models.Encounter.objects.count(),
                   'coded': models.CodingRound.objects.values('encounter_id').distinct().count()},
    'jobs': nested(Job.objects.all(), 'kind', 'state'),
    'runs': nested(Run.objects.all(), 'purpose', 'state'),
    'unknown': {'count': unknown.count(), 'encounter_count': len(named), 'encounters': named[:limit],
                'in_flight': {'reserved': Run.objects.filter(state=Run.RESERVED).count(),
                              'sending': Run.objects.filter(state=Run.SENDING).count()}},
    'tables': {'CodingRound': models.CodingRound.objects.count(), 'CodingAnswer': models.CodingAnswer.objects.count(),
               'CodeDecision': models.CodeDecision.objects.count(),
               'ExportArtifact': models.ExportArtifact.objects.count()},
    'holds': {'standing': jobs.standing_holds().count()}}))
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
    result = oneshot(image_id, ['manage', 'shell', '-c', source], env_bytes, timeout=timeout, what=what, **extra)
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


def no_core_dumps(host) -> bool:
    """Whether a container's HostConfig sets core dumps off (--ulimit core=0: soft and hard 0)."""
    return any(isinstance(item, dict) and item.get('Name') == 'core' and item.get('Soft') == 0 and item.get('Hard') == 0
               for item in host.get('Ulimits') or [])


def db_memory_problems(container, cgroup=None) -> list:
    """A3: what makes the database's memory limits other than db_args' - memory and memory + swap equal at
    DB_MEMORY_BYTES (swap off) - in its HostConfig and, when ``cgroup`` (db_cgroup's reading) is given, in its own
    cgroup: memory.swap.max 'max' is a database that swaps whatever its HostConfig says."""
    host = container.get('HostConfig') or {}
    problems = []
    if host.get('Memory') != DB_MEMORY_BYTES or host.get('MemorySwap') != DB_MEMORY_BYTES:
        problems.append(f'its memory and swap limits are {host.get("Memory")!r}/{host.get("MemorySwap")!r}, not '
                        f'{DB_MEMORY}/{DB_MEMORY} (no swap)')
    return problems + (db_cgroup_problems(cgroup) if cgroup is not None else [])


def db_cgroup_problems(cgroup) -> list:
    """A3: what makes the database's own cgroup (db_cgroup's reading) allow swap or another memory limit."""
    problems = []
    if cgroup.get('memory.swap.max') != '0':
        problems.append(f'its cgroup allows swap (memory.swap.max {cgroup.get("memory.swap.max")!r}, not 0)')
    if cgroup.get('memory.max') != str(DB_MEMORY_BYTES):
        problems.append(f'its cgroup memory limit is {cgroup.get("memory.max")!r}, not {DB_MEMORY_BYTES}')
    return problems


def db_container_problems(container, postgres_image_id, cgroup=None, *, memory=True) -> list:
    """What makes ``container`` not the CPT Studio database db_args starts. Release 1 (A3) adds its hardening -
    every capability dropped, core dumps off, a 128 MiB /dev/shm - and, unless ``memory`` is False (the db phase's
    read before it updates them in place), its memory limits (db_memory_problems, with ``cgroup``), so drift fails a
    later install."""
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
    if host.get('CapDrop') != ['ALL']:
        problems.append('does not drop every capability')
    if not no_core_dumps(host):
        problems.append('does not set core dumps off (core=0)')
    if host.get('ShmSize') != DB_SHM_BYTES:
        problems.append(f'its /dev/shm is {host.get("ShmSize")!r} bytes, not 128 MiB')
    if memory:
        problems += db_memory_problems(container, cgroup)
    return problems


def db_cgroup() -> dict:
    """The database container's own cgroup files (DB_CGROUP_FILES), read inside it with its own cat - {name: the
    file's text}; a file that cannot be read is left out, so it reads as not as installed (A3)."""
    script = ('for f in ' + ' '.join(DB_CGROUP_FILES) + '; do v=$(cat /sys/fs/cgroup/$f 2>/dev/null) && '
              'printf "%s=%s\\n" "$f" "$v"; done; true')
    done = docker('exec', DB_CONTAINER, 'sh', '-c', script, check=False, timeout=30)
    found = {}
    for line in done.stdout.decode('utf-8', 'replace').splitlines():
        name, sep, value = line.partition('=')
        if sep and name in DB_CGROUP_FILES and name not in found:
            found[name] = value.strip()
    return found


def cgroup_bytes(cgroup, name):
    """A cgroup file's value as a whole number of bytes, or None ('max', unread, malformed)."""
    value = (cgroup or {}).get(name, '')
    return int(value) if value.isascii() and value.isdigit() else None


# A3 (refutation, installer lens A-6): memory.peak is the cgroup's high-water mark since the container last started, so
# it says what the database needs only once it has seen the practices' use - a week holds every weekday's clinic load,
# the heaviest coding rounds and the report exports. A younger peak (after a host reset, say) may have seen no busy day
# at all, and turning swap off on it would be a guess: the change is skipped, and the receipt says why.
DB_PEAK_MIN_UPTIME_DAYS = 7


def started_seconds_ago(container):
    """How long ago Docker last started ``container`` (State.StartedAt, UTC, nanoseconds cut), or None when it does not
    say - Docker's zero time (never started) included."""
    match = re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?Z',
                         str(((container or {}).get('State') or {}).get('StartedAt', '')))
    if not match:
        return None
    started = dt.datetime.strptime(match.group(1), '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc)
    if started.year < 2000:
        return None
    return (dt.datetime.now(dt.timezone.utc) - started).total_seconds()


def db_memory(container) -> dict:
    """A3, on an existing database container: as installed, or - when its HostConfig or its cgroup differ from
    db_args' 512m/512m (swap off) - updated in place with `docker update --memory 512m --memory-swap 512m` (applied to
    the running container: no restart, no connection dropped), but only once it has run DB_PEAK_MIN_UPTIME_DAYS (a
    younger memory.peak is skipped, and said) and while its memory.peak plus its swap's high-water mark
    (memory.swap.peak, never below what it has in swap now) stays below DB_PEAK_SHARE of 512 MiB; otherwise refused
    with the numbers, its limits left as they are. A cgroup whose memory.swap.peak cannot be read skips the change, and
    says so: the swap it used earlier could not be counted (refutation round 1, installer-2).
    {'state', 'before', 'after'}."""
    def reading(found, cgroup):
        host = found.get('HostConfig') or {}
        return {'memory': host.get('Memory'), 'memory_swap': host.get('MemorySwap'), 'cgroup': cgroup}
    cgroup = db_cgroup()
    before = reading(container, cgroup)
    if not db_memory_problems(container, cgroup):
        return {'state': 'as installed', 'before': before}
    uptime = started_seconds_ago(container)
    if uptime is None or uptime < DB_PEAK_MIN_UPTIME_DAYS * 86400:
        ran = 'an unknown time' if uptime is None else f'{uptime / 86400:.1f} days'
        return {'state': 'skipped', 'before': before, 'uptime_seconds': uptime,
                'why': f'{DB_CONTAINER} has run {ran} since it last started, under {DB_PEAK_MIN_UPTIME_DAYS}: its '
                       'memory.peak has not yet seen a week of the practices\' use, so turning swap off at '
                       f'{DB_MEMORY} would be a guess. Its limits were left as they are; rerun --phase db once it has '
                       f'run {DB_PEAK_MIN_UPTIME_DAYS} days (verify reports the swap until then).'}
    peak, swapped = cgroup_bytes(cgroup, 'memory.peak'), cgroup_bytes(cgroup, 'memory.swap.current')
    if peak is None or swapped is None:
        raise InstallError(f'{DB_CONTAINER}\'s memory limits are not {DB_MEMORY}/{DB_MEMORY} (no swap), and its cgroup\'s '
                           'memory.peak and memory.swap.current cannot be read, so it cannot be told whether turning swap '
                           'off in place is safe; its limits were left as they are.', details={'before': before})
    swap_peak = cgroup_bytes(cgroup, 'memory.swap.peak')
    if swap_peak is None:  # refutation round 1, installer-2: never judged on what sits in swap now alone
        return {'state': 'skipped', 'before': before, 'uptime_seconds': uptime,
                'why': f'{DB_CONTAINER}\'s cgroup has no readable memory.swap.peak, so the swap it used earlier and has '
                       'since paged back cannot be counted, and turning swap off at '
                       f'{DB_MEMORY} would be a guess. Its limits were left as they are (verify reports the swap).'}
    limit = int(DB_PEAK_SHARE * DB_MEMORY_BYTES)
    # the swap it used at its high-water mark is memory it needed and could need again once swap is off (refutation
    # A-6: what sits in swap now; refutation round 1, installer-2: what sat there earlier and has since paged back)
    swap_used = max(swap_peak, swapped)
    used = peak + swap_used
    if used >= limit:
        raise InstallError(f'{DB_CONTAINER} has used up to {peak} bytes ({peak / 2 ** 20:.1f} MiB) and up to {swap_used} '
                           f'bytes ({swap_used / 2 ** 20:.1f} MiB) of swap (memory.swap.peak; {swapped} bytes in swap '
                           f'now), {used / 2 ** 20:.1f} MiB together, not below {DB_PEAK_SHARE:.0%} of {DB_MEMORY} '
                           f'({limit} bytes): turning swap off at {DB_MEMORY} could get it killed, so its limits were '
                           'left as they are. The owner decides on a larger limit (RELEASE-1-SPEC A3).',
                           details={'before': before, 'peak': peak, 'swap': swapped, 'swap_peak': swap_peak})
    docker('update', '--memory', DB_MEMORY, '--memory-swap', DB_MEMORY, DB_CONTAINER, timeout=60)
    updated = inspect('container', DB_CONTAINER) or {}
    after = reading(updated, db_cgroup())
    return {'state': 'updated', 'before': before, 'after': after, 'peak': peak, 'swap_before': swapped,
            'swap_peak': swap_peak}


def db_settings_shown() -> dict:
    """A5: SHOW of each of DB_LOG_SETTINGS on a fresh connection (psql as the bootstrap user over the database
    container's own socket) - {name: value}, a value that is not read left out."""
    done = docker('exec', DB_CONTAINER, 'psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-U', DB_USER, '-d',
                  DB_NAME, *[part for name, _ in DB_LOG_SETTINGS for part in ('-c', f'SHOW {name}')], check=False,
                  timeout=30)
    values = [line.strip() for line in done.stdout.decode('utf-8', 'replace').splitlines() if line.strip()]
    if done.returncode or len(values) != len(DB_LOG_SETTINGS):
        return {}
    return {name: value for (name, _), value in zip(DB_LOG_SETTINGS, values)}


def db_statement_logging(attempts=10, interval=0.5) -> dict:
    """A5: ALTER SYSTEM SET each of DB_LOG_SETTINGS, pg_reload_conf() (no restart), then SHOW them on fresh connections
    until they read as set (a reload is asynchronous) - refused unless they do. The statements are fixed text; psql
    runs as the bootstrap user over the container's own socket, as wait_db_ready probes it. {'shown', 'reads'}."""
    statements = [f"ALTER SYSTEM SET {name} = '{value}'" for name, value in DB_LOG_SETTINGS] + ['SELECT pg_reload_conf()']
    done = docker('exec', DB_CONTAINER, 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-U', DB_USER, '-d', DB_NAME,
                  *[part for statement in statements for part in ('-c', statement)], check=False, timeout=60)
    if done.returncode:
        raise InstallError(f'Setting the database\'s statement logging (ALTER SYSTEM) failed (exit {done.returncode}); '
                           'nothing else was changed.', output=(done.stdout + done.stderr)[-2048:])
    expected = dict(DB_LOG_SETTINGS)
    shown = {}
    for read in range(1, attempts + 1):
        shown = db_settings_shown()
        if shown == expected:
            return {'shown': shown, 'reads': read}
        time.sleep(interval)
    raise InstallError(f'The database\'s statement logging does not read as set after its reload ({shown or "not read"}, '
                       f'not {expected}): a failed statement could still be logged with its values (FLOW-13).',
                       details={'shown': shown})


def service_problems(container, role, image_id, port=None) -> list:
    """What makes ``container`` not the hardened ``role`` of ``image_id``; a web must publish exactly 127.0.0.1:
    ``port`` (any one of WEB_PORTS when ``port`` is None). Release 1 (A7) adds the role 'converter' (converter_problems:
    no network, no file, no secret, its own uid, init on)."""
    host = container.get('HostConfig') or {}
    problems = []
    if not owned(container, role) or container.get('Image') != image_id:
        problems.append('not the installed image with the CPT Studio label')
    if not host.get('ReadonlyRootfs'):
        problems.append('root filesystem is writable')
    if host.get('CapDrop') != ['ALL'] or 'no-new-privileges' not in (host.get('SecurityOpt') or []):
        problems.append('capabilities or privilege escalation not locked down')
    user = f'{CONVERTER_UID}:{APP_UID}' if role == 'converter' else f'{APP_UID}:{APP_UID}'
    if (container.get('Config') or {}).get('User') != user:
        problems.append('not running as the application user' if role != 'converter'
                        else f'not running as the converter\'s own user ({user})')
    # release 1 (A3): hardening() sets both; the check keeps them set - no swap (memory + swap equal to the memory
    # limit, which is set), and no core dump, which would write process memory to disk
    if not host.get('Memory') or host.get('MemorySwap') != host.get('Memory'):
        problems.append('its memory limit allows swap (memory and memory + swap are not equal)')
    if not no_core_dumps(host):
        problems.append('core dumps are not off (core=0)')
    bindings = host.get('PortBindings') or {}
    ports = (port,) if port is not None else WEB_PORTS
    expected = ([{'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(each)}]} for each in ports] if role == 'web'
                else [{}])
    if bindings not in expected:
        problems.append('unexpected published ports')
    # Only the worker holds a credentials file, read-only (HARNESS.md 8): the live Fable coder's (CODER) - or, in an
    # earlier revision's pair, Corti's, a live participant's and the live interpreter's (design/FINAL.md 13, D14). A web
    # holds none, whatever it is configured for.
    binds = [(mount.get('Source'), mount.get('Destination'), mount.get('RW'))
             for mount in container.get('Mounts') or [] if mount.get('Type') == 'bind']
    allowed = ({(CODER['target'], CODER['mounted']), (CORTI_TARGET, CREDENTIALS_IN_CONTAINER),
                (INTERPRETER['target'], INTERPRETER['mounted'])}
               | {(spec['target'], spec['mounted']) for spec in PARTICIPANTS.values()})
    if role == 'web' and binds:
        problems.append('the web holds a bind-mounted file (only the worker holds credentials)')
    if role == 'worker' and any((source, destination) not in allowed or writable is not False
                                for source, destination, writable in binds):
        problems.append('a bind mount other than a read-only credentials file')
    if role == 'converter':
        problems += converter_problems(container)
    return problems


def converter_problems(container) -> list:
    """A7: what makes ``container`` other than the sealed converter: its network 'none', no bind mount, the convert
    volume alone mounted (no files volume, no credentials), no secret or credentials variable in its environment, and
    init on (leftover LibreOffice processes are reaped). service_problems holds the rest (read-only root, every
    capability dropped, its own user, no swap, no core dump, no published port)."""
    host, config = container.get('HostConfig') or {}, container.get('Config') or {}
    problems = []
    if host.get('NetworkMode') != 'none':
        problems.append(f'its network is {host.get("NetworkMode")!r}, not none')
    mounts = container.get('Mounts') or []
    if [mount for mount in mounts if mount.get('Type') == 'bind']:
        problems.append('it holds a bind-mounted path')
    volumes = [(mount.get('Type'), mount.get('Name'), mount.get('Destination')) for mount in mounts
               if mount.get('Type') != 'bind']
    if volumes != [('volume', CONVERT_VOLUME, CONVERT_DIR)]:
        problems.append(f'it mounts {volumes or "nothing"}, not the convert volume alone at {CONVERT_DIR}')
    named = sorted({str(item).partition('=')[0] for item in config.get('Env') or []
                    if CONVERTER_FORBIDDEN_ENV_RE.search(str(item).partition('=')[0])})
    if named:
        problems.append(f'its environment names {", ".join(named)} (a secret or a credentials file)')
    if host.get('Init') is not True:
        problems.append('init is off (leftover LibreOffice processes would not be reaped)')
    return problems


def converter_args(image_id, revision) -> list:
    """docker run arguments of cpt-studio-converter (A7): no network, no env-file, no files volume, no credential;
    its own uid with the application's group (the socket is shared, no file); the worker's limits of memory and /tmp,
    two CPUs, init, a restart policy, the CPT and role labels and the revision; the convert volume at CONVERT_DIR; the
    entrypoint role 'converter'; a health check that pings the socket."""
    return ['--name', CONVERTER, '--pull=never', '--restart', 'unless-stopped', '--network', 'none',
            '--label', f'{LABEL}=1', '--label', f'{ROLE_LABEL}=converter', '--label', f'{REVISION_LABEL}={revision}',
            '--log-opt', 'max-size=10m', '--log-opt', 'max-file=5', '--stop-timeout', str(CONVERTER_STOP_SECONDS),
            *hardening(*CONVERTER_LIMITS, user=f'{CONVERTER_UID}:{APP_UID}'), '--cpus', CONVERTER_CPUS, '--init',
            '--mount', f'type=volume,src={CONVERT_VOLUME},dst={CONVERT_DIR},volume-nocopy',
            '--health-cmd', CONVERTER_HEALTH, '--health-interval', '10s', '--health-timeout', '5s',
            '--health-retries', '3', '--health-start-period', '20s', image_id, 'converter']


def converter_state(container) -> dict:
    """What a converter container is, for a receipt and the checks: its id, image, revision, running and health."""
    state = (container or {}).get('State') or {}
    return {'id': (container or {}).get('Id'), 'image': (container or {}).get('Image'),
            'revision': labels_of(container or {}).get(REVISION_LABEL), 'running': bool(state.get('Running')),
            'health': (state.get('Health') or {}).get('Status')}


def converter_problem(image_id, revision=None) -> str:
    """Why the converter cannot serve a worker of ``image_id`` (A7: running, healthy, from that image and revision -
    or, when ``revision`` is None, from any CPT Studio image: a switch-back's older worker uses the one that runs), or
    ''."""
    container = inspect('container', CONVERTER)
    if container is None:
        return f'{CONVERTER} is not there'
    found = converter_state(container)
    if not owned(container, 'converter'):
        return f'{CONVERTER} is not a CPT Studio converter container'
    if not found['running'] or found['health'] != 'healthy':
        return f'{CONVERTER} is not running and healthy (running {found["running"]}, health {found["health"]})'
    if revision is not None and (found['image'] != image_id or found['revision'] != revision):
        return (f'{CONVERTER} runs image {str(found["image"])[:19]} of revision {str(found["revision"])[:12]}, not this '
                'revision\'s')
    return ''


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
    """Stop and remove the ``role`` container ``name``, its log first kept ids only (A13: keep_container_log) - on every
    path that removes one: an undo at S1, S3 or S4, a switch-back's, rollback-app's (refutation, installer lens A-2).
    A copy that fails raises and leaves the container in place, stopped. Its copy's record, or None when it is gone."""
    container = inspect('container', name)
    if container is None:
        return None
    if not owned(container, role):
        raise InstallError(f'{name} is not a CPT Studio {role} container; refusing to remove it.')
    docker('stop', '--time', str(STOP_SECONDS[role]), name, check=False, timeout=STOP_SECONDS[role] + 60)
    kept = keep_container_log(container, role)
    docker('rm', '--force', container['Id'], timeout=60)
    return kept


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
    """Undo, before any other pair's worker runs on this database (CLOSE_STAGES, run with this revision's own image -
    the revision being undone): every coding job still queued or running is closed when the next worker runs no coding
    stage (``kinds`` are the kinds it runs: an earlier revision's worker would end on one), or, when it does, each one
    this pair queued or started since ``since`` - failed with the installer's note and its round cancelled, so it reads
    stopped and a Resume continues it whenever this revision serves again; one left sending is recorded unknown, never
    sent again, and a round with a send unknown (not reconciled) or failed is failed as its own stage would have failed
    it (studio.jobs.abandoned_outcome); a coding job a member stopped that is its revision's latest stage is failed too
    (an earlier revision's installer refuses on one) - and every open stage of another kind the next worker does not
    run is closed as failed with the revision named; the provider runs they left unsettled are settled. The answer's
    'hazards' name what the next pair would still act on wrongly (UNDO_HAZARDS), and its 'relabel' the encounters whose
    stored state that pair is to derive (put_back_states)."""
    note = (f'Closed by the installer: {reason} (revision {revision[:12]}), so this stage will not run. Upload the '
            'document again to process it.')
    code_note = (f'Stopped by the installer: {reason} (revision {revision[:12]}). Its round reads stopped; a Resume '
                 f'continues it, reusing every read already paid for, whenever revision {revision[:12]} serves again.')
    failed_note = (f'Stopped by the installer: {reason} (revision {revision[:12]}). Its round is closed as failed, as '
                   'the worker would have closed it: a request of it had failed, or may have reached the vendor with '
                   'its outcome unknown - an operator reconciles that one before anyone sends the round again.')
    return app_script(image_id, env_bytes, CLOSE_STAGES, {'since': since.isoformat(), 'note': note,
                                                          'code_note': code_note, 'failed_note': failed_note,
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


# What an undo does to the four tables of migration 0016, as the receipt's declared note says it (install-2): the close
# (CLOSE_STAGES) removes no row and writes only the rounds it closes.
FOUR_TABLES_KEPT = ('no row of the four new tables is deleted; closed rounds are marked cancelled (a round whose '
                    'request was in flight, or whose send is unknown or failed, is marked failed, as the worker\'s own '
                    'stale sweep marks it); answers, code decisions, exports and finished rounds are not written')


def coding_note(image_id, env_bytes, revision) -> dict:
    """The declared, NON-REFUSING note every undo that hands the rows to an earlier pair writes in its receipt
    ('not_carried_back'): what ``revision`` coded and what of it the earlier revision is not handed (CODING_MADE, read
    with ``image_id``, this revision's own image). The earlier revision reads none of the four tables of the Fable coding
    build, so the coding rounds, the members' answers, the reviewers' code decisions and the exports made here stay in
    them (FOUR_TABLES_KEPT: no row is deleted; the close marks the rounds it closes) and are not carried back - the
    accepted loss of a rollback, declared before the act. {'encounters',
    'created', 'rounds', 'answers', 'decisions', 'approved', 'exports', 'note'}. It never stops an undo: a read that
    fails, or an answer that does not say what it read, is recorded as not counted (an interrupt is never swallowed)."""
    def uncounted(why):
        return {'encounters': None, 'created': None, 'rounds': None, 'answers': None, 'decisions': None,
                'approved': None, 'exports': None,
                'note': f'what this revision coded was not counted ({why}): its coding rounds, answers, code decisions '
                        'and exports are in tables no earlier revision reads, so none of them is carried back - an '
                        'accepted loss of a rollback - and the earlier revision shows its own records only; '
                        f'{FOUR_TABLES_KEPT}'}
    try:
        answer = app_script(image_id, env_bytes, CODING_MADE, {},
                            what=f'Counting what revision {revision[:12]} coded, which is not carried back')
    except Exception as error:  # noqa: BLE001 — a declared note never stops an undo; it says it was not read
        return uncounted(str(error) or type(error).__name__)
    made = answer.get('coding') if isinstance(answer, dict) else None

    def count(value):
        return type(value) is int and value >= 0
    if not (isinstance(made, dict) and _is_ids(made.get('encounters')) and _is_ids(made.get('created'))
            and set(made['created']) <= set(made['encounters']) and count(made.get('rounds'))
            and (made['rounds'] == 0) == (not made['encounters']) and len(made['encounters']) <= made['rounds']
            and count(made.get('answers'))
            and isinstance(made.get('decisions'), dict) and set(made['decisions']) == {'approve', 'reject', 'revoke'}
            and all(count(value) for value in made['decisions'].values())
            and count(made.get('approved')) and made['approved'] <= made['decisions']['approve']
            and isinstance(made.get('exports'), dict) and set(made['exports']) == {'draft', 'approved'}
            and all(count(value) for value in made['exports'].values())):
        return uncounted('the count did not say what it read')
    coded, created = len(made['encounters']), len(made['created'])
    decided, exported = sum(made['decisions'].values()), sum(made['exports'].values())
    if not coded:
        note = ('this revision coded no encounter: there is nothing of its own to carry back, and the earlier revision '
                f'shows its own records only; {FOUR_TABLES_KEPT}')
    else:
        note = (f'this revision coded {coded} {"encounter" if coded == 1 else "encounters"} in {made["rounds"]} '
                f'round{"" if made["rounds"] == 1 else "s"} ({created} created here, {coded - created} of the earlier '
                f'review coded again); {made["answers"]} answer{"" if made["answers"] == 1 else "s"}, {decided} code '
                f'decision{"" if decided == 1 else "s"} ({made["approved"]} code{"" if made["approved"] == 1 else "s"} '
                f'approved now) and {exported} export{"" if exported == 1 else "s"} made here are not carried back: the '
                f'earlier revision reads none of these tables ({FOUR_TABLES_KEPT}), so it shows no code, answer or '
                'decision of this revision - an accepted loss of a rollback, declared before it')
        if created:
            note += (f'; the {created} {"encounter" if created == 1 else "encounters"} created here '
                     f'{"holds" if created == 1 else "hold"} no reading the earlier revision made: it shows each by its '
                     'own derivation (states_put_back) and processes none of them unless the document is uploaded again '
                     'there')
    return {key: made[key] for key in ('encounters', 'created', 'rounds', 'answers', 'decisions', 'approved',
                                       'exports')} | {'note': note}


def _is_ids(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value) \
        and len(set(value)) == len(value)


def _undo_parts(closes) -> tuple:
    """(update_pending, reverted, reading_closed, without_update) merged over the close answers ``closes``
    (CLOSE_STAGES'; without_update: no close said the next worker has the update), or None when
    an answer that names any of them does not say what it read. A close that names none of them (an image with no
    update, or nothing pending) adds nothing; a None or a missing close is skipped (its own receipt says why)."""
    pending, reverted, reading, reverts = {}, {}, {}, set()
    for close in closes or ():
        if not isinstance(close, dict):
            continue
        if close.get('update_pending') or close.get('reading_closed'):
            reverts.add(close.get('update_revert') is not False)  # unsaid: the earlier image is read as having no update
        named, values, counted = close.get('update_pending', {}), close.get('reverted', {}), close.get('reading_closed', {})
        if not (isinstance(named, dict) and all(isinstance(pk, str) and isinstance(reasons, list) and reasons
                                                and all(reason in UNDO_PENDING_REASONS for reason in reasons)
                                                for pk, reasons in named.items())):
            return None
        if not (isinstance(values, dict) and all(
                isinstance(pk, str) and pk in named and 'values_saved' in named[pk] and isinstance(fields, dict)
                and fields and all(isinstance(name, str) and isinstance(pair, dict) and set(pair) == {'saved', 'restored'}
                                   for name, pair in fields.items())
                for pk, fields in values.items())):
            return None
        if not (isinstance(counted, dict) and all(kind in READING_STAGE_KINDS and type(count) is int and count > 0
                                                  for kind, count in counted.items())):
            return None
        for pk, reasons in named.items():
            pending[pk] = sorted(set(pending.get(pk, [])) | set(reasons))
        for pk, fields in values.items():
            reverted.setdefault(pk, {}).update(fields)
        for kind, count in counted.items():
            reading[kind] = reading.get(kind, 0) + count
    return (dict(sorted(pending.items())), dict(sorted(reverted.items())), dict(sorted(reading.items())),
            all(reverts) if reverts else True)


# design v2's update_pending reasons, read back by the note; this revision's close names none (CLOSE_STAGES)
UNDO_PENDING_REASONS = ('values_saved', 'assessment_off_context', 'reconciled_unknown')


def _update_reads(closes, pending):
    """Refutation w7r 6b-r1 R2: what each pending update of ``pending`` reads after the closes ``closes``, as the image
    of the close read its page (CLOSE_STAGES' 'update_reads', given for a next worker that runs appraise): {encounter:
    {'phase', 'action'} or None (not read)}, a later close's reading over an earlier one's; an encounter no close read
    is None. None when an answer that gives it does not say what it read (never read as any state)."""
    reads = {}
    for close in closes or ():
        if not isinstance(close, dict) or 'update_reads' not in close:
            continue
        given = close['update_reads']
        if not (isinstance(given, dict) and all(
                isinstance(pk, str) and pk in pending and (shown is None or (
                    isinstance(shown, dict) and set(shown) == {'phase', 'action'}
                    and all(isinstance(value, str) and value for value in shown.values())))
                for pk, shown in given.items())):
            return None
        reads.update(given)
    return {pk: reads.get(pk) for pk in sorted(pending)}


def _reads_said(reads) -> str:
    """The note's clauses for what each pending update reads (_update_reads), grouped by the action its page offers:
    each says what a member can do there, and none promises an action the page does not offer (D247 F2)."""
    groups = {}
    for pk, shown in reads.items():
        key = ('unread', '') if shown is None else (shown['action'], shown['phase'].replace('_', ' '))
        groups.setdefault(key, []).append(pk)
    clauses = []
    for (action, phase), ids in sorted(groups.items()):
        count = f'{len(ids)} {"reads" if len(ids) == 1 else "read"}'
        if action == 'retry_update':
            clauses.append(f'{count} {phase}, and its member\'s "Try updating again" queues the failed stage again')
        elif action == 'retry_reading':
            clauses.append(f'{count} {phase}, and its member\'s "Try reading again" queues its reading again')
        elif action == 'resume':
            clauses.append(f'{count} {phase}, and its member\'s "Resume processing" runs it again')
        elif action == 'none' and phase == 'paused':
            clauses.append(f'{count} paused, with nothing to resume or retry, until its member saves a change of a '
                           'detail, which queues the update again')
        elif action == 'none':
            clauses.append(f'{count} {phase}, with nothing offered on its page')
        elif action == 'unread':
            clauses.append(f'{len(ids)} could not be read after the close')
        else:
            clauses.append(f'{count} {phase}, offering {action}')
    return '; '.join(clauses)


def with_update_note(note, closes) -> dict:
    """Design v2 (FINAL-V2 6.4; amendment 1, 9.4; step 6b): the undo's declared note (coding_note's ``note``)
    with what the closes ``closes`` did for the amendment's update: 'reading_closed' (the interpret and appraise stages
    failed with the installer's note, which no earlier worker runs), 'update_pending' (the encounters that read an update
    of their codes pending - a stated rollback limit like D59's 'reinstatable', never a refusal) and 'reverted' (the
    unapplied values each such save had, set back to the current context's, with the saved and restored values), each
    key given only when there is one, and each said in the note's sentence with what the operator does. D59's
    reinstatable clause stays as the note wrote it. The Fable coding build's close names none of these keys, so its
    note is returned as it was counted. An answer that does not say what it read is said so,
    never read as none. Refutation 6b-r2 F2 (DECISIONS D247): every sentence says what is so - an earlier revision that
    runs both reading stages offers no retry and no resume of a reading stage the installer closed, and nothing is
    queued for an update there (D247 DQ1's 'otherwise'). Refutation w7r 6b-r1 R2: what such an update then reads depends
    on the stage the close left (a closed reading or document review reads paused, with nothing to resume, until its
    member saves a change of a detail; a closed analysis or assessment reads failed, and "Try updating again" queues it
    again), so the note words each pending update by what it reads after the close, as the close's image read its page
    ('update_reads', grouped by the action offered) - never one reading for all, and no retry promised where none is
    offered; one the close did not read is said so."""
    out = dict(note) if isinstance(note, dict) else {'note': ''}
    sentence = out.get('note') if isinstance(out.get('note'), str) else ''
    parts = _undo_parts(closes)
    reads = _update_reads(closes, parts[0]) if parts is not None else None
    if parts is None or (reads is None and not parts[3]):
        out['update_pending'] = None
        out['note'] = (sentence + '; ' if sentence else '') + (
            'the encounters with an update of their codes pending were not read (a close did not say what it read): '
            'read each close in this receipt before anyone reviews on the earlier web')
        return out
    pending, reverted, reading, without_update = parts
    clauses = []
    if reading:
        total = sum(reading.values())
        said = (': the earlier image runs neither interpret nor appraise, and a context save there reads the document '
                'with its own reader' if without_update else
                ': each was failed with the installer\'s note, and nothing queues it again - the earlier revision runs '
                'both, but offers no retry and no resume of a stage the installer closed')
        clauses.append(f'{total} reading stage{"s were" if total != 1 else " was"} closed '
                       f'({", ".join(f"{kind} {count}" for kind, count in reading.items())}){said}')
        out['reading_closed'] = reading
    if pending:
        out['update_pending'] = sorted(pending)
        if without_update:
            said = (': the earlier image has no update and shows the codes from before the change, so tell those '
                    'encounters\' members that the codes shown predate their change')
        else:
            # refutation w7r 6b-r1 R2: each update worded by what it reads after the close, never one reading for all
            out['update_reads'] = reads
            said = (': the earlier revision reads an update itself (its worker runs appraise), but each stage of it '
                    'this revision\'s pair left open was closed with the others (failed, with the installer\'s '
                    'note) and nothing queues it again; as this revision\'s page reads each after the close '
                    '(update_reads; an earlier design v2 revision reads an update by the same amendment, 7.1 and '
                    '7.2): ' + _reads_said(reads) + ' - tell those encounters\' members so')
        clauses.append(f'{len(pending)} {"encounter reads" if len(pending) == 1 else "encounters read"} an update of '
                       f'their codes pending (update_pending){said}')
        checked = [pk for pk, reasons in pending.items() if 'reconciled_unknown' in reasons]
        if checked:
            clauses.append(f'{len(checked)} of them read an update no save started (a reconciled document review, '
                           'A21)' + (': the earlier image reads that reconciled run as an outcome still being '
                                     'confirmed, with nothing pending' if without_update else ''))
    if reverted:
        out['reverted'] = reverted
        clauses.append(f'the unapplied details of {len(reverted)} {"encounter were" if len(reverted) == 1 else "encounters were"} '
                       'set back to their current context\'s values (context.rollback_reverted; each field\'s saved '
                       'and restored value is in reverted): ask each member to save the change again on the earlier web')
    if clauses:
        out['note'] = '; '.join(([sentence] if sentence else []) + clauses)
    return out


def named_ids(ids) -> str:
    """Encounter ids for a message (refutation 6b-r2 F1: the message names them): sorted, NAMED_LIMIT at most, then
    how many more - every one is in the receipt."""
    ordered = sorted(ids)
    shown = ', '.join(ordered[:NAMED_LIMIT])
    return shown + (f' and {len(ordered) - NAMED_LIMIT} more' if len(ordered) > NAMED_LIMIT else '')


# reapply_reverted's 'problem' for a close that names a value it set back: this revision's own close (CLOSE_STAGES)
# changes no member's details, so such a close was not this revision's, and nothing is put back.
NO_PUT_BACK = ('this revision has no put-back: its own close sets nothing back, so a close that names a value it set '
               'back was not its close')


def reapply_reverted(image_id, env_bytes, closes) -> dict:
    """Design v2 (amendment 1, 9.4; refutation 6b-r1 P2) had a close set a pending save's unapplied values back for an
    earlier image and, when the undo then left this revision's pair to serve again, put them back. The Fable coding
    build's close sets nothing back (CLOSE_STAGES: no 'reverted'), so there is never anything to put back and nothing is
    run: {'asked', 'reapplied', 'not_reapplied', 'requeued', 'coalesced', 'not_requeued', 'problem', 'sentence'} with the
    sentence '' when no close names a set-back value. A close that does not say what it set back, or one that names a
    set-back value (not this revision's close: NO_PUT_BACK), is the 'problem', said in the sentence with the encounters
    named and what the operator does - never read as nothing to put back, nor as put back. ``image_id`` and
    ``env_bytes`` are kept for its callers: nothing runs in an image here."""
    out = {'asked': {}, 'reapplied': {}, 'not_reapplied': {}, 'requeued': {}, 'coalesced': {}, 'not_requeued': {},
           'problem': '', 'sentence': ''}
    parts = _undo_parts(closes)
    if parts is None:
        out['problem'] = 'a close did not say what it set back'
        out['sentence'] = ('the unapplied details a close may have set back to their context\'s values were not put '
                           'back (a close did not say what it set back): read each close in this receipt, and ask '
                           'the members of the encounters it names to check their details')
        return out
    reverted = parts[1]
    if not reverted:
        return out
    out['asked'] = {pk: sorted(fields) for pk, fields in reverted.items()}
    out['problem'] = NO_PUT_BACK
    out['sentence'] = (f'a close names values it set back on {len(reverted)} '
                       f'{"encounter" if len(reverted) == 1 else "encounters"} ({named_ids(reverted)}), which this '
                       'revision\'s own close never does, so nothing was put back: read that close in this receipt, '
                       'and ask those members to check their details on this revision\'s web')
    return out


def may_not_have_been_put_back(reverted, problem, where) -> str:
    """The sentence for saves a put-back may or may not have put back - it failed, did not say what it did, or was
    interrupted: design v2's put-back put each encounter back in its own transaction - naming the encounters
    (``reverted``: CLOSE_STAGES' set-back fields by encounter) and saying neither "put back" nor "not put back"
    (refutation 6b-r2 F1/F2); ``where`` is the web the members check their details on."""
    return (f'the unapplied details the close set back on {len(reverted)} '
            f'{"encounter" if len(reverted) == 1 else "encounters"} ({named_ids(reverted)}; context.rollback_reverted) '
            f'may not have been put back ({problem}): context.rollback_reapplied names each one that was, so ask each '
            f'of those members to check their details on {where}')


def interrupted_put_back(closes, error) -> dict:
    """reapply_reverted's answer for a put-back that raised before it answered - an interrupt (a Ctrl-C), or any error
    reapply_reverted does not answer itself (refutation w7r 6b-r1 R1): any encounter asked may or may not have been put
    back (each in its own transaction) - the 'problem', with 'interrupted' True, and the sentence naming them; what each
    field was saved and restored as stays in the close's own record."""
    parts = _undo_parts(closes)
    reverted = parts[1] if parts is not None else {}
    problem = (f'the put-back {"stopped on an error" if isinstance(error, Exception) else "was interrupted"} '
               f'({str(error) or type(error).__name__})')
    return {'asked': {pk: sorted(fields) for pk, fields in reverted.items()}, 'reapplied': {}, 'not_reapplied': {},
            'requeued': {}, 'coalesced': {}, 'not_requeued': {}, 'problem': problem, 'interrupted': True,
            'sentence': may_not_have_been_put_back(reverted, problem, 'whichever web serves next') if reverted else ''}


def kept_serving(image_id, env_bytes, closes, details) -> str:
    """reapply_reverted for an undo whose close set pending saves back and that then leaves this revision's pair to
    serve again - its web keeps serving, neither pair runs for the operator to choose, or rollback-app stopped with this
    pair to be started again (refutation 6b-r1 P2; refutation 6b-r2 F1, DECISIONS D247: before the message that says
    so): recorded in ``details`` as 'reapplied' when anything was asked or went wrong; the sentence for the undo's
    message (' ...' or '').

    Refutation w7r 6b-r1 R1: an interrupt while the put-back runs is recorded here (interrupted_put_back: 'reapplied'
    says so, and the sentence names the encounters the close set back as possibly not put back), never lost with the
    message that was being built - the close's record of what each member saved is in ``details`` or the caller's
    receipt. The phase still stops on it: every caller raises its message right after (rollback-app and the swap), or
    returns it to an undo that raises it (the S4 undo, return_to_old_web, rollback-app in the keep layout)."""
    try:
        done = reapply_reverted(image_id, env_bytes, closes)
    except BaseException as error:  # noqa: BLE001 — recorded and said; the caller's InstallError stops the phase
        done = interrupted_put_back(closes, error)
    if done['asked'] or done['problem']:
        details['reapplied'] = done
    return f' {done["sentence"][:1].upper()}{done["sentence"][1:]}.' if done['sentence'] else ''


def not_put_back(closes, why, where='stages_closed.reverted') -> str:
    """The sentence for an undo's message that may leave this revision's pair to serve again when the put-back could
    not run (refutation 6b-r2 F1, DECISIONS D247) - an interrupt, or an undo left half way, which puts nothing back while
    the earlier web may serve (F3): it names the encounters whose saves the close set back (context.rollback_reverted;
    ``where`` names the receipt's field) and says they were not put back ' ...', or '' when nothing was set back."""
    parts = _undo_parts(closes)
    if parts is None:
        return (' A close did not say which unapplied details it set back to their context\'s values, and nothing was '
                f'put back ({why}): read each close in this receipt, and ask the members of the encounters it names to '
                'check their details.')
    reverted = parts[1]
    if not reverted:
        return ''
    return (f' The unapplied details the close set back on {len(reverted)} '
            f'{"encounter" if len(reverted) == 1 else "encounters"} ({named_ids(reverted)}; context.rollback_reverted, '
            f'each field\'s saved and restored value in {where}) were not put back '
            f'({why}): whichever web serves next, ask each of those members to save the change again there.')


def possibly_set_back(started_at) -> str:
    """The clause (refutation r3, D-5), its subject the close, for a close that was started and gave no answer -
    CLOSE_STAGES commits its close, then recomputes states and reads the hazards, so it may have closed stages with
    nothing said - carried by every undo whose close may have raised after its commit (refutation 6b-r2 F4, DECISIONS
    D247). The Fable coding build's close changes no member's details, so it is never said to have set any back."""
    return (f'may have closed stages since {started_at} before it stopped ({CLOSED_STAGES_SAID}) and set no '
            'member\'s details back (this revision\'s close changes none)')


def set_back_clause(closes) -> str:
    """The sentence for an undo's message whose closes set pending saves back and that hands the rows to the earlier
    pair (refutation 6b-r1 P2: a message that omitted the revert): ' ...' or '' when nothing was set back."""
    parts = _undo_parts(closes)
    if parts is None:
        return (' A close did not say which unapplied details it set back to their context\'s values: read each close '
                'in this receipt before anyone reviews on the earlier web.')
    reverted = parts[1]
    if not reverted:
        return ''
    return (f' The close set the unapplied details of {len(reverted)} '
            f'{"encounter" if len(reverted) == 1 else "encounters"} back to their context\'s values for the earlier pair '
            '(stages_closed.reverted names each field\'s saved and restored value): once it serves, ask each of those '
            'members to save the change again there.')


def undone_note(note, served=None, kept=None) -> dict:
    """The declared note of an undo that handed the site to NO earlier pair after its close (refutation 6b-r1 P2): a
    switch-back undone before its switch, or a way back that kept this revision's web serving. coding_note's
    ``note`` as it was counted (D59's 'reinstatable' clause kept), with 'handed': False and a first clause saying no
    earlier web read the rows - never with_update_note's instructions for an earlier web's members, which no earlier web
    served (what the close set back, and what was put back, is in the receipt's close and 'reapplied').

    Refutation 6b-r2 F5 (DECISIONS D247): ``served`` - {'from', 'until', 'update_pending'} - when nginx may have routed to
    the earlier web before the undo settled the vhost back (a B5 undo whose nginx_may_have_read was true): the note then
    says that earlier web may have served from the switch until the settle, what members who used it saw there, and
    names the encounters with an update pending ('update_pending'; 'served' records the window). ``kept`` says why no
    earlier web read the rows when it is not that the undo kept this revision's web serving (rollback-app whose removal
    stopped after a put-back, refutation 6b-r2 F1).

    Refutation w7r 6b-r1 R5: ``served['reconciled_unknown']`` names the encounters among them whose only reason is A21's
    (an update no save started): no change of their members was pending, so they are worded apart, as with_update_note
    words them - never said to have seen "the codes from before their change"."""
    out = dict(note) if isinstance(note, dict) else {'note': ''}
    sentence = out.get('note') if isinstance(out.get('note'), str) else ''
    out['handed'] = False
    if served:
        unread = served.get('update_pending') is None  # the close did not say what it read: never read as none
        pending = [] if unread else sorted(served['update_pending'])
        unstarted = sorted(set(served.get('reconciled_unknown') or ()) & set(pending))
        changed = [pk for pk in pending if pk not in unstarted]
        out['served'] = {'from': served.get('from'), 'until': served.get('until')}
        out['update_pending'] = None if unread else pending
        saw = []
        if changed:
            saw.append(f'the members of the {len(changed)} {"encounter" if len(changed) == 1 else "encounters"} with '
                       'an update of their codes pending (update_pending) who used it in that window saw the codes '
                       'from before their change there (AMENDMENT-1 9.4 says what the earlier web shows for each)')
        if unstarted:
            saw.append(f'{len(unstarted)} {"encounter" if len(unstarted) == 1 else "encounters"} with an update '
                       'pending read an update no save started (a reconciled document review, A21), so no change of '
                       'their members was pending: an earlier image with no update reads that reconciled run as an '
                       'outcome still being confirmed, with nothing pending (AMENDMENT-1 9.4)')
        first = (f'the earlier web may have served from the switch ({served.get("from")}) until the settle '
                 f'({served.get("until")}): nginx was asked to reload with the vhost naming it and was proven to route to '
                 'this revision\'s web again only at the settle, the requests it had taken by then finishing during its '
                 'drain, and the undo then kept this revision\'s web serving'
                 + ('; the encounters with an update of their codes pending were not read (the close did not say what '
                    'it read): read it in this receipt, tell the members of those it names that they may have seen the '
                    'codes from before their change there, and check any decision or export made there in that window'
                    if unread else
                    '; ' + '; '.join(saw) + ': tell those members, and check any decision or export made there in that '
                    'window' if saw else '')
                 + '; what follows is what that web read')
    else:
        why = kept or 'the undo kept this revision\'s web serving'
        first = f'handed to no earlier web: {why}, so what follows is what an earlier web would have read'
    out['note'] = '; '.join([first] + ([sentence] if sentence else []))
    return out


def v1_rows(image_id, env_bytes) -> dict:
    """FINAL-V2 6.2 [R:MO-1]: the design v1 rows on the target (V1_ROWS, in this revision's image)."""
    return app_script(image_id, env_bytes, V1_ROWS, {'engine_version': V1_ENGINE_VERSION,
                                                     'interpretation_version': V1_INTERPRETATION_VERSION,
                                                     'limit': NAMED_LIMIT},
                      what='Reading the target for design v1 rows')


def v1_rows_refusal(answer):
    """None when ``answer`` (V1_ROWS') says no design v1 row exists; otherwise the refusal's message. An answer that
    does not say what it read, or counted other versions, refuses (D66: never read as "none")."""
    if not (isinstance(answer, dict) and answer.get('engine_version') == V1_ENGINE_VERSION
            and answer.get('interpretation_version') == V1_INTERPRETATION_VERSION
            and all(type(answer.get(key)) is int and answer[key] >= 0
                    for key in ('assessments', 'inventories', 'encounter_count'))
            and _is_ids(answer.get('encounters')) and len(answer['encounters']) <= answer['encounter_count']
            and (answer['encounter_count'] == 0) == (answer['assessments'] == answer['inventories'] == 0)):
        return ('the read of the target for design v1 rows gave no answer it could be judged by; nothing was replaced '
                '(FINAL-V2 6.2: the install refuses unless it is shown that no v1 row exists)')
    if answer['encounter_count'] == 0:
        return None
    shown = ', '.join(answer['encounters'])
    more = answer['encounter_count'] - len(answer['encounters'])
    return (f'the target holds design v1 rows - {answer["assessments"]} assessment(s) of engine {V1_ENGINE_VERSION} and '
            f'{answer["inventories"]} event inventor{"y" if answer["inventories"] == 1 else "ies"} of '
            f'{V1_INTERPRETATION_VERSION}, on {answer["encounter_count"]} encounter(s): {shown}'
            + (f' and {more} more' if more > 0 else '') + '; nothing was replaced (FINAL-V2 6.2 [R:MO-1]: this '
            'release is installed only where no v1 row exists - live never held one; a test instance\'s are read as '
            'stored and retired with that instance, never deleted by the installer)')


# What the owner is told when the counts could not be read (RELEASE-1-SPEC 1.3, TEC-8 (5)): never to read them on a
# restored copy of live - live is never restored or copied for an install - but where the install was tried first.
COUNTS_NOT_READ = ('report them to the owner as not counted; the install was tried first in the synthetic rehearsal on '
                   'the test instance (RELEASE-1-SPEC 6.4), and no copy of live is restored to count them')


def install_counts(image_id, env_bytes) -> dict:
    """The install counts of the Fable coding build (INSTALL_COUNTS, in this revision's image), with 'report' - the
    sentences the owner is told before the switch. NEVER a refusal: a read that fails, or an answer that does not say
    what it read, is recorded as not counted (an interrupt is never swallowed), and the install goes on."""
    try:
        answer = app_script(image_id, env_bytes, INSTALL_COUNTS, {'limit': NAMED_LIMIT},
                            what='Counting what the owner is told before the switch')
    except Exception as error:  # noqa: BLE001 — printed, never a refusal
        return {'counted': False, 'why': str(error) or type(error).__name__,
                'report': [f'the install counts were not read: {COUNTS_NOT_READ}']}
    problem = counts_problem(answer)
    if problem:
        return {'counted': False, 'why': problem, 'answer': answer,
                'report': [f'the install counts did not say what they read: {COUNTS_NOT_READ}']}
    return {'counted': True, **answer, 'report': counts_report(answer)}


COUNTED_TABLES = ('CodingRound', 'CodingAnswer', 'CodeDecision', 'ExportArtifact')  # migration 0016's four tables


def counts_problem(answer) -> str:
    """'' when ``answer`` is INSTALL_COUNTS' answer in its shape; otherwise what is wrong with it."""
    def count(value):
        return type(value) is int and value >= 0

    def nested(value):
        return isinstance(value, dict) and all(
            isinstance(outer, str) and isinstance(inner, dict) and inner
            and all(isinstance(name, str) and count(n) and n > 0 for name, n in inner.items())
            for outer, inner in value.items())
    if not isinstance(answer, dict):
        return 'no answer'
    encounters, unknown, tables, holds = (answer.get(key) for key in ('encounters', 'unknown', 'tables', 'holds'))
    if not (isinstance(encounters, dict) and count(encounters.get('count')) and count(encounters.get('coded'))
            and encounters['coded'] <= encounters['count']):
        return 'the encounter count is not in its shape'
    if not (nested(answer.get('jobs')) and nested(answer.get('runs'))):
        return 'the stage or run count is not in its shape'
    in_flight = unknown.get('in_flight') if isinstance(unknown, dict) else None
    if not (isinstance(unknown, dict) and count(unknown.get('count')) and count(unknown.get('encounter_count'))
            and _is_ids(unknown.get('encounters')) and len(unknown['encounters']) <= unknown['encounter_count']
            and unknown['encounter_count'] <= unknown['count'] and (unknown['count'] == 0) == (unknown['encounter_count'] == 0)
            and isinstance(in_flight, dict) and set(in_flight) == {'reserved', 'sending'}
            and all(count(n) for n in in_flight.values())):
        return 'the unknown-outcome count is not in its shape'
    if not (isinstance(tables, dict) and set(tables) == set(COUNTED_TABLES) and all(count(n) for n in tables.values())):
        return 'the table count is not in its shape'
    if not (isinstance(holds, dict) and count(holds.get('standing'))):
        return 'the hold count is not in its shape'
    return ''


def counts_report(answer) -> list:
    """The sentences the owner is told before the switch, from INSTALL_COUNTS' ``answer``: what this install leaves as
    it is and what it changes for the members, each only when there is one; [] when there is nothing to report."""
    report = []
    earlier = {kind: states for kind, states in answer['jobs'].items() if kind != CODE_KIND}
    queued = sum(states.get('queued', 0) for states in earlier.values())
    running = sum(states.get('running', 0) for states in earlier.values())
    if queued or running:
        report.append(f'{queued} stage(s) of the earlier pipeline queued and {running} running: this revision\'s worker '
                      'never runs one (it claims coding jobs only); a running one is settled by its startup sweep '
                      '(cancelled, or unknown when it was sending), and each such document reads as an earlier review '
                      'until a member asks for it to be reviewed again, which retires a stage left queued')
    unknown = answer['unknown']
    if unknown['count']:
        report.append(f'{unknown["count"]} provider outcome(s) still unknown and not reconciled, on '
                      f'{unknown["encounter_count"]} encounter(s): they stay unknown; one of the earlier pipeline '
                      'touches no coding send, and a coding run\'s counts at its worst case against its document\'s '
                      'spending ceiling (studio.jobs.spent_usd)')
    in_flight = unknown['in_flight']
    if in_flight['reserved'] or in_flight['sending']:
        report.append(f'{in_flight["reserved"]} provider run(s) reserved and {in_flight["sending"]} sending before the '
                      'switch: a worker\'s startup or stale sweep settles each (sending: unknown, reserved: not sent)')
    made = {name: n for name, n in answer['tables'].items() if n}
    if made:
        report.append('the tables of the Fable coding build already hold rows (' + ', '.join(
            f'{name} {n}' for name, n in sorted(made.items())) + '): expected 0 on the first install over a revision '
            'before it, so this is a reinstall or a same-revision run')
    if answer['holds']['standing']:
        report.append(f'{answer["holds"]["standing"]} hold(s) standing: every coding send is refused until an operator '
                      'releases them on the operator console')
    return report


def counts_summary(counts) -> str:
    """One clause of the app receipt's summary for the install counts."""
    if not isinstance(counts, dict) or counts.get('counted') is not True:
        return '; install counts NOT read: see the receipt'
    encounters, unknown, tables = counts['encounters'], counts['unknown'], counts['tables']
    return (f'; install counts: {encounters["count"]} encounter(s), {encounters["coded"]} coded; '
            f'{unknown["count"]} unknown outcome(s) not reconciled; {sum(tables.values())} row(s) in the coding '
            f'tables; {counts["holds"]["standing"]} hold(s) standing'
            + (f'; {len(counts["report"])} item(s) for the owner' if counts['report'] else ''))


def target_reads(prev_image, env_bytes, kinds) -> frozenset:
    """DECISIONS D51: the hazard reasons the revision a switch-back returns to reads as this revision wrote them, so
    they are no hazard to it: 'participant' when its worker runs a participant stage (astra or fable), the three second
    review reasons when it runs review2 (``kinds``: stage_kinds_of its image), and 'member_answer' and 'modifier' as its
    own models say (TARGET_MODEL_READS, in its image). Never 'unknown', 'outcome', 'conflict' or 'reinstatement'."""
    reads = set()
    if {'astra', 'fable'} & set(kinds):
        reads.add('participant')
    if 'review2' in kinds:
        reads.update(('second_review', 'second_review_refused', 'second_review_unread'))
    answer = app_script(prev_image, env_bytes, TARGET_MODEL_READS, {},
                        what='Reading which review records the previous revision reads')
    reads.update(reason for reason in answer.get('reads') or () if reason in ('member_answer', 'modifier'))
    return frozenset(reads)


def touched_encounters(image_id, env_bytes, since) -> set:
    """DECISIONS D51: the encounters with a record created since ``since`` (TOUCHED_SINCE_READ, in this image)."""
    answer = app_script(image_id, env_bytes, TOUCHED_SINCE_READ, {'since': since.isoformat()},
                        what='Reading what this revision wrote since its pair was created')
    return set(answer['touched'])


def switch_back_hazards(hazards, reads, touched) -> dict:
    """DECISIONS D51 (the S17 rollback test, D15 assertion 5): of ``hazards`` (undo_hazards' {encounter id: reasons},
    read as the oldest revision reads the rows), those a switch-back must refuse on. A switch-back returns to the pair
    this revision replaced: a reason that revision reads (``reads``: target_reads) is no hazard to it, and an encounter
    with no record created since this revision's pair (``touched``) holds only what that pair itself left there - its
    status quo before the switch, as it served it. On live data the unfiltered read named 23 such legacy encounters
    (participant, member_answer, modifier), so the switch-back refused whatever this revision had done. A hazards value
    that is not a dict is returned as it is (the caller refuses on it)."""
    if not isinstance(hazards, dict):
        return hazards
    out = {}
    for pk, reasons in hazards.items():
        left = [reason for reason in (reasons or ()) if reason not in reads]
        if left and pk in touched:
            out[pk] = left
    return out


def hazard_summary(hazards) -> str:
    counts = {}
    for reasons in hazards.values():
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
    return f'{len(hazards)} encounter(s): ' + ', '.join(f'{reason} {count}' for reason, count in sorted(counts.items()))


# Refutation p2, the skeptic of the install2:1 repair: the hazard reasons about what an older revision's web SAYS, not
# what its worker does. No stored state can be put back for them, and a worker left stopped does not keep its web from
# saying it. These are the earlier pipeline's reasons (a second review, a participant, a member's answer, a modifier, a
# reinstatement), which this revision's UNDO_HAZARDS never names: it writes none of the records they read. Its own
# reasons - 'unknown' and the close's 'open_stage' - are both about what an older worker would act on.
SHOWN_HAZARDS = ('second_review_refused', 'second_review_unread', 'participant', 'member_answer', 'modifier',
                 'reinstatement')


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
    """Before an undo hands the rows to the pair it starts next (refutation p2, install2:1), each encounter the close
    names in 'relabel' - every encounter this revision coded, whose stored state is its own derivation's (state names
    the earlier revision does not know, such as 'awaiting_answer', or knows with another meaning, such as 'reviewed'),
    and every one whose earlier stage this revision's worker settled - is given the state that pair derives for it, with
    its own derivation, run in ITS image (PUT_BACK_STATES in ``older_image``: the earlier pipeline's
    studio.review.refresh_state, or studio.state.refresh in an image of this design). With no image to ask (rollback-app
    with no pair parked: an older revision is installed afterwards by its own installer) nothing is put back and the
    answer says so ('put_back': False): every revision since 057a7d39 recomputes every stored state in its own app phase
    (an install of 057a7d39 itself, which does not, is no rollback this revision supports - go back through the
    revision this one replaced). ``image_id`` (this revision's) runs nothing here. An answer that names nothing it read
    is not read as "none"."""
    relabel = closed.get('relabel') if isinstance(closed, dict) else None
    if not isinstance(relabel, list) or not all(isinstance(pk, str) for pk in relabel):
        raise InstallError('The close did not say which list states an older revision labels otherwise.')
    if not relabel:
        return {'encounters': 0, 'changed': {}}
    if isinstance(older_image, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', older_image):
        return app_script(older_image, env_bytes, PUT_BACK_STATES, {'encounters': relabel},
                          what='Putting back the list states the next pair derives (its own image)')
    return {'encounters': len(relabel), 'changed': {}, 'put_back': False,
            'why': 'no image of the next pair to ask: the revision installed next recomputes every stored state in its '
                   'own app phase'}


def replace_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants=None, *,
                     interpreter=None, coding=None) -> dict:
    """Replace the web and worker (``participants``: each harness participant's mode, disabled when not given;
    ``interpreter``: the interpreter's, and ``coding``: the Fable coder's, each disabled when not given) the way
    replacement_plan reads the host - after migrate, as before, and right before anything is started or stopped (a
    refusal starts and stops nothing; preflight has refused the same states before the install began): a served site
    is switched blue/green (switch_services, which never stops its web; it needs this install's preflight receipt, the
    baseline the switch is verified against); a host where nothing is served through the vhost is swapped as it always
    was (swap_services). The receipt's 'replacement' says which, and why."""
    plan = replacement_plan(ctx)
    summary = {key: plan[key] for key in ('mode', 'why', 'vhost', 'vhost_sha256', 'live', 'idle', 'port') if key in plan}
    # named only when it is not the default, so a stand-in of either keeps the arguments it always had
    interpreting = {'interpreter': interpreter} if (interpreter or 'disabled') != 'disabled' else {}
    interpreting.update({'coding': coding} if (coding or 'disabled') != 'disabled' else {})
    if plan['mode'] == 'blue-green':
        preflight = require_receipt(ctx, 'preflight')
        services = switch_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants,
                                   preflight=preflight, plan=plan, **interpreting)
    else:
        services = swap_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants,
                                 port=plan['port'], **interpreting)
    return {**services, 'replacement': summary}


def swap_services(ctx, image_id, env_bytes, provider_mode, authorization_ref, participants=None, *,
                  port=WEB_PORT, interpreter=None, coding=None) -> dict:
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
    was started (ADJUDICATION P-7: the verify one-shot's window begins there, as blue/green's begins at S4). When the
    pair it replaces and this revision do not share release 1's session policy (sessions_end_needed, read before
    anything is stopped), every session is ended once both old containers are stopped, before the new web starts
    (end_every_session; refutation round 1, rollback-0 and rollback-3); a failure there restores the old pair."""
    parked, launched, started, sessions = {}, [], {}, {}
    swapped_at = worker_started_at = None
    # the revisions of the pair it replaces (one park() refuses as not ours is left to park's own refusal)
    replaced = [labels_of(container).get(REVISION_LABEL)
                for role, container in ((role, inspect('container', SERVICES[role])) for role in ('web', 'worker'))
                if container is not None and owned(container, role)]
    try:
        ends_sessions = [revision for revision in dict.fromkeys(replaced)
                         if sessions_end_needed(revision, ctx.revision)]
    except InstallError as error:
        raise InstallError(f'{error} Nothing was started or stopped.') from error
    try:
        for role in ('worker', 'web'):  # the worker first, so no stage runs across the switch
            parked[role] = park(role)
        if ends_sessions:  # both old containers are stopped: none of their sessions can be made any more
            end_every_session(image_id, env_bytes, ends_sessions[0], ctx.revision, sessions)
        swapped_at = dt.datetime.now(dt.timezone.utc)  # every stage created from here on is the new pair's
        for role in ('web', 'worker'):
            launched.append(role)
            if role == 'worker':
                worker_started_at = utc_now_ms()
            docker('run', '-d', *service_args(role, image_id, ctx.revision, provider_mode, authorization_ref,
                                              participants, port=port, interpreter=interpreter,
                                              **({'coding': coding} if coding else {})),
                   input=env_bytes, quiet=True)
            # WEB_PORT is wait_service's own default, and is left to it (callers' stand-ins keep its three arguments)
            started[role] = wait_service(role, ctx.revision, image_id, **({'port': port} if port != WEB_PORT else {}))
    except BaseException as failure:
        for role in reversed(launched):
            name = SERVICES[role]
            log_tail(ctx, name, role, f'{role}-failed')  # ids only (refutation A-2)
            stop_service_container(name, role)
        closed, put_back, hold_worker = None, None, False
        if launched and any(parked.values()):
            previous = parked.get('worker') or parked.get('web')
            kinds = stage_kinds_of(previous['image'], env_bytes)  # what the restored worker runs (p1, security-0)
            close_started = utc_now_ms()  # refutation 6b-r2 F4's class: a close that raises may have committed first
            try:
                closed = close_undone_stages(image_id, env_bytes, swapped_at, ctx.revision,
                                             'its installation failed and the previous revision was restored', kinds)
            except BaseException as error:
                raise InstallError(f'{failure}; the stages the new pair left open could not then be closed ({error}), '
                                   'so the new pair was left stopped and the previous pair parked (*-previous): run '
                                   '--phase rollback-app, then rename the parked pair back. The close was started and '
                                   f'gave no answer: it {possibly_set_back(close_started)}.'
                                   + sessions_ended_said(sessions),
                                   details={'close_started_at': close_started,
                                            **sessions_ended_of(sessions)}) from error
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
                # refutation 6b-r1 P2: neither pair runs and the operator chooses - keeping this revision reads the
                # saves the close set back as its own update, going back sets them back again (rollback-app's close)
                left = {'hazards': hazards, 'stages_closed': closed}
                said = kept_serving(image_id, env_bytes, [closed], left)
                raise InstallError(
                    f'{failure}; {named} hold states the previous revision would show wrongly whatever it is handed '
                    '(a bounded second review whose response was refused whole, or whose outcome is unknown or not '
                    'read yet: it reads neither and would say that no code was proposed; a code only a harness '
                    'participant proposed: it would show it as the provider\'s), so the new pair was left '
                    'stopped and the previous pair parked '
                    '(*-previous). To keep this revision, remove the parked pair by hand and run --phase app again '
                    'once its failure is fixed; to go back, start this pair again, clear them on its web '
                    '(ops/INSTALL.md, Reinstalling an older revision), run --phase rollback-app, then rename the '
                    'parked pair back. While admin.quillmd.com is moved that way back is not open (rollback-app never '
                    'removes the pair quillmd-cpt proxies to): keep this revision as above, then --phase switch-back '
                    'returns the previous pair.' + said + sessions_ended_said(sessions),
                    details={**left, **sessions_ended_of(sessions)}) from failure
            # Refutation p2, install2:1: the restored pair shows a stored state by its own labels - a response this
            # revision refused whole would read 'Provider request failed' - so it is handed its own derivation of those.
            try:
                put_back = put_back_states(closed, previous['image'], image_id, env_bytes)
            except BaseException as error:
                # refutation 6b-r1 P2: the only way on is back to the previous pair, which reads the saves the close
                # set back as set back - so they stay so, and the message and the receipt say it
                raise InstallError(f'{failure}; the list states the previous revision labels otherwise could not then '
                                   f'be put back ({error}), so the new pair was left stopped and the previous pair '
                                   'parked (*-previous): run --phase rollback-app, then rename the parked pair '
                                   'back.' + set_back_clause([closed]) + sessions_ended_said(sessions),
                                   details={'stages_closed': closed, **sessions_ended_of(sessions)}) from error
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
        # refutation w7r 6b-r1 (its observation, 6b-r1 P2's class): the previous pair was handed the rows, so a close
        # that set pending saves back is said in the message - and recorded in the receipt, not only in the undo log
        set_back = set_back_clause([closed]) if closed is not None else ''
        if hold_worker:
            hazards = closed.get('hazards')
            named = hazard_summary(acting) if acting is not None else 'the close did not say which'
            raise InstallError(
                f'{failure}; the previous web was restored and its worker ({SERVICES["worker"]}) left stopped, so '
                f'nothing can be sent: {named} hold records it would act on under its own rules (ops/INSTALL.md, '
                'Reinstalling an older revision). Install this revision again once its failure is fixed: its worker '
                'reads them under its own rules.' + set_back + sessions_ended_said(sessions),
                details={'hazards': hazards, 'stages_closed': closed, 'states_put_back': put_back,
                         **sessions_ended_of(sessions)}) from failure
        if set_back or sessions.get('started_at'):  # refutation round 1, rollback-0: the end may have committed
            raise InstallError(f'{str(failure) or type(failure).__name__}; the previous pair was restored.' + set_back
                               + sessions_ended_said(sessions),
                               details={**(failure.details if isinstance(getattr(failure, 'details', None), dict)
                                           else {}),
                                        **({'stages_closed': closed, 'states_put_back': put_back} if set_back else {}),
                                        **sessions_ended_of(sessions)}) from failure
        raise
    return {'started': started, 'replaced': parked, 'worker_started_at': worker_started_at,
            **sessions_ended_of(sessions)}


def retire_parked(parked) -> dict:
    """Remove the parked old pair (replace_services' 'replaced') - once the new pair runs and the stored list states are
    recomputed (phase_app), or the previous pair serves again (switch-back's B9). Release 1 (A13): each container's log
    is first kept, ids only (keep_container_log); every copy is made before anything is removed, and a copy that fails
    removes nothing - the parked pair stays, the new pair already serves, and the error says so. {role: the copy}."""
    kept = {}
    for role, previous in (parked or {}).items():
        if previous:
            try:
                kept[role] = keep_container_log({'Id': previous['id']}, role, previous.get('revision'))
            except InstallError as error:
                raise InstallError(f'the parked {role}\'s log could not be kept ({error}), so the parked pair was left in '
                                   'place: keep its log, then remove it (ops/INSTALL.md, Recovery notes)',
                                   details={'kept': kept}) from error
    for role, previous in (parked or {}).items():
        if previous:
            docker('rm', '--force', previous['id'], timeout=60)
    return kept


# --- blue/green: the switch that never stops the serving web (ops/INSTALL.md, app) --------------------------------------
#
# Invariants (each asserted after every fake call by ops/test_install_bluegreen.py):
#   I-web    after every step the vhost's proxy_pass port - the file's and the one nginx routes to - is published by a
#            running web that answered health_ok for its revision; the old web is never stopped before the switch is
#            verified, nor while a verified switch could still be undone.
#   I-worker at most one worker runs; the old one is stopped before any new-revision web takes traffic, and the new one
#            starts only after the old one has exited (no stale-stage sweep races a live stage).
#   I-jobs   the old worker's current stage finishes (docker stop --time 3600, STOP_SECONDS['worker']); queued stages
#            of a kind the new worker runs wait for it. One of a kind it does not run - every kind of the pipeline
#            before the Fable coding build - is never claimed by it (studio.jobs.claim_next takes only the kinds of its
#            STAGES), and a member's Review again retires it (studio.decisions.retry).
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
                           'than its upstream, so nothing was started or stopped. Publish this revision\'s stage first '
                           '(ops/INSTALL.md, Reinstalling a new revision: --phase ingress over a stage that names no '
                           'admin host, --phase https-vhost over one that does).')
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
# The files only a revision that serves the admin host has (release 1 of D396 on): its urlconf and the middleware that
# chooses it. A revision without them answers Host admin.quillmd.com with Django's 400 (DisallowedHost).
ADMIN_HOST_FILES = (f'{APP}/cptstudio/urls_admin.py', f'{APP}/studio/hosts.py')


def serves_admin_host(revision) -> bool:
    """Whether ``revision``'s web serves ADMIN_HOST: its tree holds ADMIN_HOST_FILES. The admin checks are revision-aware
    (refutation INSTALLER-5, APP-1): such a web is judged on the answers only the admin urlconf gives; an older one -
    after a switch-back to a revision before release 1, say - answers the admin host 400, which is recorded, never a
    failure. A revision this checkout cannot read is refused, not taken for an older one: that answer would leave the
    admin answers unjudged on the switch paths (check, round R2-3)."""
    if not SHA_RE.fullmatch(str(revision)):
        raise InstallError(f'Cannot tell whether {str(revision)[:40]!r} serves {ADMIN_HOST}: it is not a 40-character '
                           'revision. Nothing was decided on it.')
    if run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}^{{commit}}'], check=False, quiet=True).returncode:
        raise InstallError(f'Cannot tell whether {revision[:12]} serves {ADMIN_HOST}: this checkout cannot read that '
                           'revision. Fetch it into the act checkout, then rerun. Nothing was decided on it.')
    return all(run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}:{path}'], check=False,
                   quiet=True).returncode == 0 for path in ADMIN_HOST_FILES)


def has_converter(revision) -> bool:
    """Whether ``revision`` has the converter service (A7): its tree holds CONVERTER_FILES, read as serves_admin_host
    reads the admin host's. A worker of such a revision mounts the converter's socket and requires it; an older one is
    started exactly as before. A revision this checkout cannot read is refused, never taken for an older one: that
    answer would start a release-1 worker converting in-process (fail closed)."""
    if not SHA_RE.fullmatch(str(revision)):
        raise InstallError(f'Cannot tell whether {str(revision)[:40]!r} has the converter service: it is not a '
                           '40-character revision. Nothing was decided on it.')
    if run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}^{{commit}}'], check=False, quiet=True).returncode:
        raise InstallError(f'Cannot tell whether {revision[:12]} has the converter service: this checkout cannot read '
                           'that revision. Fetch it into the act checkout, then rerun. Nothing was decided on it.')
    return all(run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}:{path}'], check=False,
                   quiet=True).returncode == 0 for path in CONVERTER_FILES)


# Release 1's session policy (B5, B6; studio/sessions.py) and a switch between a revision before it and one with it
# (refutation round 1, rollback-0 and rollback-3). Release 1 names its session and CSRF cookies __Host-... under HTTPS,
# so across such a switch a browser holds two independent sessions: neither web ever reads the other's cookie, release 1
# only tells a browser that calls it to delete the old cookie, and nothing ended either revision's rows. So a release-1
# session outlived a switch-back (an explicit sign-out on the older web ends only that web's session) and came back for
# whoever used that browser next at the second switch forward; and an older session left in a browser nobody used during
# release 1 was valid again after a switch-back. Whenever the site moves between such revisions, every session is ended
# in this revision's image, in one transaction with one SecurityEvent (SESSIONS_ENDED_EVENT: a count and the two
# revisions, the installer as the actor label) - none of them can be used across the switch anyway (the cookie rename):
#   - an app's blue/green switch (switch_services) from a serving web of a revision before the policy: after S2 (the old
#     worker parked) and before S3 (the upstream switch); a failure there is undone as at S2;
#   - an app's swap (swap_services) of such a pair: once both old containers are stopped, before the new web starts;
#   - a switch-back (switch_back_services) to such a revision: at B4, before B5, while this revision's web still serves
#     (the older web reads none of its cookies once it serves).
# Never when both revisions have the policy: a later release over release 1 signs no one out. Whether a revision has it
# is read from its tree (SESSION_POLICY_FILES), as has_converter reads the converter; one this checkout cannot read is
# refused, nothing started or stopped (fail closed).
SESSION_POLICY_FILES = (f'{APP}/studio/sessions.py',)
SESSIONS_ENDED_EVENT = 'sessions.ended_at_install'
SESSIONS_ENDED_ACTOR = 'installer'
# (the lock timeout: a session row a web is saving holds the delete back at most that long, as LICENSE_NOTE_FIX's)
END_EVERY_SESSION = '''
from django.contrib.sessions.models import Session
from django.db import connection, transaction
from studio import security_events
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '30s'")
    ended = Session.objects.all().delete()[0]
    event = security_events.record(P['event'], actor_label=P['actor_label'], count=ended,
                                   from_revision=P['from_revision'], to_revision=P['to_revision'])
print(ANSWER + json.dumps({'ended': ended, 'event': str(event.pk)}))
'''


def has_session_policy(revision) -> bool:
    """Whether ``revision`` has release 1's session policy (B5, B6): its tree holds SESSION_POLICY_FILES, read as
    has_converter reads the converter. A revision this checkout cannot read is refused, never taken for one with or
    without it (fail closed): either answer could leave a session to come back across a switch, or sign everyone out of
    a later release for nothing."""
    if not SHA_RE.fullmatch(str(revision)):
        raise InstallError(f'Cannot tell whether {str(revision)[:40]!r} has release 1\'s session policy: it is not a '
                           '40-character revision. Nothing was decided on it.')
    if run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}^{{commit}}'], check=False, quiet=True).returncode:
        raise InstallError(f'Cannot tell whether {revision[:12]} has release 1\'s session policy: this checkout cannot '
                           'read that revision. Fetch it into the act checkout, then rerun. Nothing was decided on it.')
    return all(run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}:{path}'], check=False,
                   quiet=True).returncode == 0 for path in SESSION_POLICY_FILES)


def sessions_end_needed(from_revision, to_revision) -> bool:
    """Whether a move of the site from ``from_revision`` to ``to_revision`` ends every session: exactly one of the two
    has release 1's session policy. Raises (has_session_policy) when either cannot be read."""
    return has_session_policy(from_revision) != has_session_policy(to_revision)


def end_every_session(image_id, env_bytes, from_revision, to_revision, sessions) -> dict:
    """END_EVERY_SESSION in ``image_id`` (this revision's): every django_session row deleted and SESSIONS_ENDED_EVENT
    recorded, in one transaction. ``sessions`` is the caller's record, written into as it goes - 'started_at' before
    the script runs (it may commit whatever its call then answers), then 'ended' and 'event' - so a receipt after a
    failure or an interrupt says what may have happened. An answer it cannot judge raises, never read as none."""
    sessions.update(from_revision=from_revision, to_revision=to_revision, started_at=utc_now_ms())
    answer = app_script(image_id, env_bytes, END_EVERY_SESSION,
                        {'event': SESSIONS_ENDED_EVENT, 'actor_label': SESSIONS_ENDED_ACTOR,
                         'from_revision': from_revision, 'to_revision': to_revision}, what='Ending every session')
    ended, event = (answer.get('ended'), answer.get('event')) if isinstance(answer, dict) else (None, None)
    if isinstance(ended, bool) or not isinstance(ended, int) or ended < 0 or not UUID_RE.fullmatch(str(event)):
        raise InstallError('The end of every session gave no answer it could be judged by.', details={'answer': answer})
    sessions.update(ended=ended, event=event)
    return sessions


def sessions_ended_said(sessions) -> str:
    """The sentence a receipt's message adds once the end of every session was started ('' when it was not)."""
    if not isinstance(sessions, dict) or not sessions.get('started_at'):
        return ''
    if isinstance(sessions.get('ended'), int) and not isinstance(sessions.get('ended'), bool):
        return (f' Every session was ended ({sessions["ended"]}; SecurityEvent {SESSIONS_ENDED_EVENT}): everyone '
                'signs in again.')
    return (' The end of every session was started and gave no answer: it may have ended every session (and recorded '
            f'{SESSIONS_ENDED_EVENT}), so everyone may have to sign in again.')


# Release 1's disposal (D1) and a way back to a revision before it (refutation round 1, rollback-1 and rollback-2): a
# closed practice (Workspace.closed_at) and a destroyed document's tombstone (Encounter.destroyed_at: title '', no
# revision, its PHI-free decision trail kept) are rows only release 1's own code reads. A revision without disposal lists
# and counts each tombstone again (its kept activity on its page and its console), and takes uploads into a closed
# practice and sends them for coding. So every way back to one - a switch-back to a revision whose tree has no
# DISPOSAL_FILES, rollback-app returning an older web (the keep layout), and rollback-app's removal when the pair that
# runs next is such a revision or is not known (no parked pair: an older revision installed afterwards) - refuses,
# starting and stopping nothing, while any practice is closed or any document destroyed, read in this revision's image
# (DISPOSAL_COUNTS: counts only). Neither is ever undone, so the way on is a fix forward (ops/INSTALL.md, switch-back).
DISPOSAL_FILES = (f'{APP}/studio/disposal.py',)
DISPOSAL_COUNTS = '''
from studio import models
print(ANSWER + json.dumps({'closed': models.Workspace._base_manager.filter(closed_at__isnull=False).count(),
                           'destroyed': models.Encounter._base_manager.filter(destroyed_at__isnull=False).count()}))
'''


def has_disposal(revision) -> bool:
    """Whether ``revision`` has release 1's disposal (D1): its tree holds DISPOSAL_FILES, read as has_converter reads
    the converter. A revision this checkout cannot read is refused, never taken for one with it (fail closed)."""
    if not SHA_RE.fullmatch(str(revision)):
        raise InstallError(f'Cannot tell whether {str(revision)[:40]!r} has release 1\'s disposal: it is not a '
                           '40-character revision. Nothing was decided on it.')
    if run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}^{{commit}}'], check=False, quiet=True).returncode:
        raise InstallError(f'Cannot tell whether {revision[:12]} has release 1\'s disposal: this checkout cannot read '
                           'that revision. Fetch it into the act checkout, then rerun. Nothing was decided on it.')
    return all(run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{revision}:{path}'], check=False,
                   quiet=True).returncode == 0 for path in DISPOSAL_FILES)


def disposal_counts(image_id, env_bytes) -> dict:
    """DISPOSAL_COUNTS in ``image_id`` (this revision's): {'closed': practices, 'destroyed': documents}. An answer it
    cannot judge raises, never read as none."""
    answer = app_script(image_id, env_bytes, DISPOSAL_COUNTS, {},
                        what='Reading the closed practices and destroyed documents')
    counts = {name: answer.get(name) if isinstance(answer, dict) else None for name in ('closed', 'destroyed')}
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
        raise InstallError('The read of the closed practices and destroyed documents gave no answer it could be judged '
                           'by.', details={'answer': answer})
    return counts


def disposal_refusal(image_id, env_bytes, target_revision) -> tuple:
    """(the refusal, the counts) of a way back to ``target_revision`` - the revision that serves next, None when it is
    not known - while a practice is closed or a document destroyed and that revision has no disposal: ('', None) when
    it has disposal, ('', counts) when there is nothing to refuse on."""
    if target_revision is not None and has_disposal(target_revision):
        return '', None
    counts = disposal_counts(image_id, env_bytes)
    if not counts['closed'] and not counts['destroyed']:
        return '', counts
    which = (f'revision {target_revision[:12]} has no disposal (its tree has no {DISPOSAL_FILES[0]})'
             if target_revision is not None else
             'the revision that runs next is not known (no parked pair names one) and one before release 1 has no '
             'disposal')
    return (f'{counts["closed"]} practice(s) are closed and {counts["destroyed"]} document(s) destroyed (release 1, '
            f'D1), and {which}: it would list and count each destroyed document again, its kept decision trail on its '
            'page and its console, and take uploads into a closed practice and send them for coding. Neither is ever '
            'undone, so fix forward instead: a revision with disposal (ops/INSTALL.md, switch-back)'), counts


def sessions_ended_of(sessions) -> dict:
    """{'sessions_ended': the record} once the end of every session was started, else {} (a receipt's details)."""
    return {'sessions_ended': sessions} if isinstance(sessions, dict) and sessions.get('started_at') else {}


def sessions_summary(sessions) -> str:
    """'; every session ended (12): ...' for a receipt's summary ('' when none was ended)."""
    if not isinstance(sessions, dict) or not isinstance(sessions.get('ended'), int):
        return ''
    if sessions.get('to_revision') is None:  # rollback-app's removal with no parked pair: what runs next is not known
        return (f'; every session ended ({sessions["ended"]}: the revision that runs after '
                f'{str(sessions.get("from_revision"))[:12]} is not known, and one before release 1 has no session '
                'policy)')
    return (f'; every session ended ({sessions["ended"]}: {str(sessions.get("from_revision"))[:12]} and '
            f'{str(sessions.get("to_revision"))[:12]} do not share release 1\'s session policy)')


def admin_answers(fetch) -> tuple:
    """(problems, record): the answers the admin urlconf gives and the full urlconf does not (refutation APP-2, APP-5,
    APP-6), each fetched by ``fetch(path, method, keep_body)`` - one request naming ADMIN_HOST: /api/session 404 (the
    full urlconf answers 401: the host was not routed); an anonymous GET and HEAD of / 302 to exactly /login/ (the full
    urlconf: /login/?next=/; a method guard: 405); the operator sign-in 200 text/html naming static files by href or
    src (STATIC_REFERENCE_RE, as smoke_web reads the doctors' sign-in), each answering 200."""
    problems, record = [], {}
    api = fetch('/api/session', 'GET', False)
    record['api_session'] = api.get('status') or api.get('error')
    if api.get('status') != 404:
        problems.append(f'{ADMIN_HOST}/api/session answered {record["api_session"]}, not 404 (the admin host has no API)')
    for method in ('GET', 'HEAD'):
        home = fetch('/', method, False)
        location = (home.get('headers') or {}).get('location')
        record[f'{method.lower()}_root'] = {'status': home.get('status') or home.get('error'), 'location': location}
        if home.get('status') != 302 or location != ['/login/']:
            problems.append(f'an anonymous {method} of {ADMIN_HOST}/ answered {home.get("status") or home.get("error")} '
                            f'to {location}, not 302 to exactly /login/')
    login = fetch('/login/', 'GET', True)
    content_type = ((login.get('headers') or {}).get('content-type') or [''])[0]
    record['login'] = {'status': login.get('status') or login.get('error'), 'content_type': content_type, 'assets': {}}
    if login.get('status') != 200 or not content_type.startswith('text/html'):
        problems.append(f'{ADMIN_HOST}/login/ answered {record["login"]["status"]} {content_type}'.strip())
    else:
        paths = sorted(set(STATIC_REFERENCE_RE.findall((login.get('body') or b'').decode('utf-8', 'replace'))))
        if not paths:
            problems.append(f'the {ADMIN_HOST} sign-in page names no static file, so none could be checked')
        for path in paths[:20]:
            asset = fetch(path, 'GET', False)
            record['login']['assets'][path] = asset.get('status') or asset.get('error')
            if asset.get('status') != 200:
                problems.append(f'{ADMIN_HOST}{path} answered {asset.get("status") or asset.get("error")}')
    return problems, record


def smoke_web(port, *, admin=False) -> dict:
    """Before the incoming web takes traffic: its sign-in page answers 200 text/html on 127.0.0.1:``port``, and every
    static file that page names (hashed names, from the web's own manifest) answers 200 from the same web. Read-only (a
    GET of the sign-in page writes nothing). Refused when the page names no static file: nothing would be checked.
    ``admin`` (serves_admin_host of the web's revision): the same web also gives the admin host's own answers
    (admin_answers, Host admin.quillmd.com on the loopback port), before any switch routes the admin host to it."""
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
    if admin:
        def fetch(path, method, keep_body):
            return probe('http', ADMIN_HOST, path, port=port, connect_ip='127.0.0.1', headers=headers, method=method,
                         timeout=5, keep_body=keep_body)
        admin_problems, record['admin'] = admin_answers(fetch)
        problems += admin_problems
    else:
        record['admin'] = 'not judged: this revision does not serve the admin host (it answers it 400)'
    if problems:
        raise InstallError('The incoming web did not serve its own pages: ' + '; '.join(problems) + '.',
                           details={'smoke': record})
    return record


class AvailabilityRecorder:
    """https://cpt.quillmd.com/health/ through the public path - DNS, this host's nginx and whichever web it routes to,
    as a customer reaches it - every AVAILABILITY_INTERVAL_SECONDS in a daemon thread, from start() to stop(), which
    returns {'samples', 'statuses' (count per status, 'error' for no answer), 'releases_seen' (in the order first
    seen: each answer's release, or the release digest a release-1 web answers through nginx - health_release, B7),
    'non_200' (the first AVAILABILITY_KEPT, each {at, status, error}), 'non_200_count', 'started_at',
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
            release = health_release(body)  # B7: the release, or its digest through nginx
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


LOG_TAIL_LINES = 200


def log_tail(ctx, name, role, label):
    """A failed container's last lines, for the receipts folder: ids only (ids_only_lines) - a traceback or a DETAIL line
    that can hold document text is dropped and counted, never copied (refutation, installer lens A-2: the raw last 40
    lines were kept there)."""
    container = inspect('container', name)
    if container is not None and owned(container, role):
        tail = docker('logs', '--timestamps', '--tail', str(LOG_TAIL_LINES), name, check=False, timeout=30)
        kept, dropped = ids_only_lines(role, tail.stdout, tail.stderr)
        ctx.log(label, (f'# the last {LOG_TAIL_LINES} lines of {name}, ids only: {len(kept)} kept, {dropped} dropped '
                        '(ops/INSTALL.md, A13)\n' + ''.join(line + '\n' for line in kept)).encode())


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
                    plan, interpreter=None, coding=None) -> dict:
    """The blue/green replacement (replacement_plan's 'blue-green'): the serving web is never stopped before the switch
    is verified and drained.

      S1  start the incoming web, INCOMING_WEB, on the idle port; it must answer health_ok for this revision and serve
          its own sign-in page and static files (smoke_web) - the old web still serves everything
      S2  park the old worker (docker stop --time 3600, STOP_SECONDS['worker']: its current stage finishes; nothing
          new is claimed) - the old web still serves, and what members start waits in the queue
      S3  switch the vhost's upstream to the idle port (switch_upstream: atomic replace, nginx -t, graceful reload,
          /health/ = this revision through the public path, co-tenants unchanged)
      S4  start the new worker - processing resumes under the new rules
      S5  drain the old web (drain_web), stop it, park it as cpt-studio-web-previous and rename the incoming web to
          cpt-studio-web
    When the serving web's revision and this one do not share release 1's session policy (sessions_end_needed), every
    session is ended at S2, once the old worker is parked and before S3 (end_every_session; refutation round 1,
    rollback-0 and rollback-3): none can be used across the switch (the cookie rename), and the receipt says how many.
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
    try:  # refutation round 1, rollback-0 and rollback-3: decided before anything starts, from both revisions' trees
        ends_sessions = sessions_end_needed(plan['web']['revision'], ctx.revision)
    except InstallError as error:
        raise InstallError(f'The blue/green switch cannot start, so nothing was started or stopped: {error}',
                           details={'plan': plan}) from error
    steps, parked, started, progress, sessions = {}, {}, {}, {}, {}
    record = {'mode': 'blue-green', 'ports': {'from': live, 'to': idle}, 'steps': steps}
    reached = [None]

    def step(name):
        reached[0] = name
        steps[name] = utc_now_ms()
    recorder = AvailabilityRecorder().start()
    try:
        step('S1')
        docker('run', '-d', *service_args('web', image_id, ctx.revision, provider_mode, authorization_ref, participants,
                                          name=INCOMING_WEB, port=idle, interpreter=interpreter,
                                          **({'coding': coding} if coding else {})),
               input=env_bytes, quiet=True)
        started['web'] = wait_service('web', ctx.revision, image_id, name=INCOMING_WEB, port=idle)
        record['smoke'] = smoke_web(idle, admin=serves_admin_host(ctx.revision))
        step('S2')
        parked['worker'] = park('worker')
        if ends_sessions:  # S2, once the old worker is parked and before S3: undone as at S2
            record['sessions_ended'] = sessions
            end_every_session(image_id, env_bytes, plan['web']['revision'], ctx.revision, sessions)
        step('S3')
        record['switch'] = switch_upstream(ctx, preflight, live, idle, revision=ctx.revision, progress=progress,
                                           from_revision=plan['web']['revision'])
        step('S4')
        docker('run', '-d', *service_args('worker', image_id, ctx.revision, provider_mode, authorization_ref,
                                          participants, interpreter=interpreter,
                                          **({'coding': coding} if coding else {})), input=env_bytes, quiet=True)
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
                                           preflight=preflight, parked=parked, progress=progress, details=details,
                                           sessions=sessions)
        except BaseException as second:  # noqa: BLE001 — the undo itself stopped: say so, with what is there now
            message = (f'{str(failure) or type(failure).__name__}; the undo at {reached[0]} stopped too '
                       f'({str(second) or type(second).__name__}): read "left" in this receipt, then ops/INSTALL.md, '
                       'Recovery notes')
        raise InstallError(message + sessions_ended_said(sessions),
                           details={**record, **details, 'failed_at': reached[0], 'started': started,
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
                details=None, sessions=None) -> tuple:
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
        # refutation round 1, rollback-0: the end of every session (S2) may have committed - said by the caller
        changed = ('nothing else changed but the sessions (below)' if (sessions or {}).get('started_at')
                   else 'nothing else changed')
        return (f'{cause}; the old worker is {state}, the incoming web ({INCOMING_WEB}) {removed}, and {changed}: '
                f'{web} kept serving on {live}. Migrations already applied are not reversed.', details)
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


# What a stage the close closed reads afterwards (CLOSE_STAGES): said wherever an undo says a close may have closed one -
# the switch-back that refuses after B4's close, and every close that raised or gave no answer. A coding job ends as its
# own stage would have ended it (studio.jobs.abandoned_outcome, the stale sweep's rule), so the sentence says each way
# (install-2): only a round with nothing it sent unsettled reads stopped for a Resume; one whose request was in flight
# or whose send's outcome is unknown is failed as unknown and waits for an operator's reconcile; one whose send failed is
# failed with that send's kind.
CLOSED_STAGES_SAID = ('a coding job it closed ends as its own stage would have ended it, with the installer\'s note: with '
                      'nothing it sent unsettled, the job reads failed and its round stopped, and a Resume continues '
                      'that round whenever this revision serves again; with a request in flight or a send whose unknown '
                      'outcome no operator has reconciled, the job reads unknown and its round failed as unknown, so no '
                      'Resume continues it and a retry waits for an operator\'s reconcile; with a send that failed, the '
                      'job reads failed and its round failed with that send\'s kind, so no Resume continues it and a '
                      'retry starts a new round; a stage of another kind it closed stays failed, with the installer\'s '
                      'note')


def close_did_not_finish(what, error) -> str:
    """A close that raised may have committed before it stopped (CLOSE_STAGES commits its close, then recomputes states
    and reads the hazards: refutation r3, D-5), so it is never reported as having closed nothing."""
    return (f'the close of {what} did not finish ({str(error) or type(error).__name__}): it may have closed some or all '
            f'of them before it stopped, and {CLOSED_STAGES_SAID}')


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
        # refutation 6b-r1 P2: the new web keeps serving, so the saves the first close set back are put back
        return (f'{cause}; the list states the old revision labels otherwise could not be put back ({error}), so '
                f'{keep}.' + kept_serving(image_id, env_bytes, [first], details), details, 'kept')
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
                        'which recomputes them.'
                        # refutation 6b-r2 F3: nothing is put back half way; F1: the saves set back are named
                        + not_put_back([first], 'an undo left half way puts nothing back while the earlier web may '
                                                'serve'), details, 'halfway')
        # refutation 6b-r1 P2: nginx never read the switched vhost, so the old web served nothing and the new web
        # keeps serving: the saves the first close set back are put back
        return (f'{cause}; the switch back to the old web failed ({error}) and the vhost was left on the new one, so '
                f'{keep}. The list states were put back to the old revision\'s: rerun --phase app, which recomputes '
                'them.' + kept_serving(image_id, env_bytes, [first], details), details, 'kept')
    done = finish_back(ctx, image_id=image_id, env_bytes=env_bytes, idle=idle, previous=previous,
                       parked_worker=parked_worker, kinds=kinds, reason=reason, since=first_at, closes=[],
                       details=details, worker=True,
                       hold=lambda every: return_hold(first, every[-1], same=same, first_at=first_at))
    switched = f'{cause}; the vhost was switched back, so {web} (revision {old_revision[:12]}) serves on {live} again'
    # the old web is handed the rows, so what the closes set back for it is said in the message (refutation w7r 6b-r1's
    # observation, 6b-r1 P2's class: a message that omitted the revert)
    set_back = set_back_clause([first, details.get('stages_closed_after_drain')])
    if done['outcome'] == 'back':
        return (f'{switched}; {done["problem"]}. {left_for_rollback_app()} Migrations already applied are not '
                'reversed.' + set_back, details, 'back')
    held = (f' It is held - nothing can be sent - because {"; ".join(done["notes"])} (ops/INSTALL.md, Reinstalling an '
            'older revision).') if done['hold'] else ((' ' + '; '.join(done['notes']) + '.') if done['notes'] else '')
    removed = 'the new worker was removed' if done['worker_removed'] else 'there was no new worker to remove'
    return (f'{switched}; {removed} and the incoming web {done["removed"]}; the old worker was {done["worker_note"]}.'
            f'{held} Migrations already applied are not reversed.' + set_back, details, done['outcome'])


def undo_switch_s4(ctx, cause, *, image_id, env_bytes, plan, preflight, parked, progress, previous, kinds,
                   reason, details=None) -> tuple:
    live, idle = plan['live'], plan['idle']
    worker = SERVICES['worker']
    log_tail(ctx, worker, 'worker', 'worker-failed')
    stop_service_container(worker, 'worker')  # its current stage finishes (STOP_SECONDS['worker'], 3,600 s)
    keep = keep_note(live, idle)
    details = {} if details is None else details
    first_at = dt.datetime.now(dt.timezone.utc)
    try:
        closed = close_undone_stages(image_id, env_bytes, progress['applied_at'], ctx.revision, reason, kinds)
    except BaseException as error:  # noqa: BLE001
        # refutation 6b-r2 F4 (DECISIONS D247): the close may have committed its revert before it raised, and the new
        # web keeps serving: the switch-back's clause names the context.rollback_reverted rows since it started
        details['close_started_at'] = first_at.isoformat()
        return (f'{cause}; {close_did_not_finish("the stages the new pair left open", error)}, so {keep}. The close '
                f'{possibly_set_back(first_at.isoformat())}.', details)
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
                f'are: {keep}.' + kept_serving(image_id, env_bytes, [closed], details), details)  # 6b-r1 P2
    message, _, _ = return_to_old_web(ctx, cause, image_id=image_id, env_bytes=env_bytes, preflight=preflight,
                                      live=live, idle=idle, old_revision=plan['web']['revision'],
                                      previous=previous, parked_worker=parked.get('worker'), kinds=kinds,
                                      reason=reason, first=closed, first_at=first_at, details=details)
    return message, details


# --- phases ------------------------------------------------------------------------

def coding_source_problems(paths) -> list:
    """The Fable coder's source (CODER) is optional here - preflight does not know the mode the app phase will be given,
    and the app phase refuses --coding-mode live without its copy - but one that is there must be root-only, in a
    root-only directory, or the secrets phase refuses it (HARNESS.md 8's rules). No other source is judged: the secrets
    phase reads no other now (Corti's and Astra's are no longer read). ``paths``: helper_stat's answer for
    PROVIDER_SOURCES and CODER's source."""
    problems = []
    folder = paths[PROVIDER_SOURCES]
    if folder.get('exists') and folder != {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}:
        problems.append(f'{PROVIDER_SOURCES} is not a root-owned 0700 directory')
    found = paths[CODER['source']]
    if found.get('exists') and found != {'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o600'}:
        problems.append(f'{CODER["source"]} is not a root-owned 0600 regular file')
    return problems


def phase_preflight(ctx) -> dict:
    """The baseline every later phase compares against (ops/INSTALL.md, preflight). Since release 2 of the admin move it
    takes either state of the coupling invariant - before the ingress, or after it (the act runs it again then, as the
    baseline app and verify read) - and refuses any other; it also proves admin.quillmd.com's DNS and its HTTP-01 route
    (the quillmd vhost's :80 block), and that scripts/check-cotenants.sh honours the installer's own-host skip."""
    problems, details = [], {'docker_server': docker_positive_control()}
    files = nginx_file_state()
    details['nginx_files'] = files
    details['vhost'] = vhost_state()
    details['coupling'] = read_coupling(files['available'].get('quillmd'), details['vhost'])
    problem = coupling_problem(details['coupling'])
    if problem:
        problems.append(problem)
    test = nginx_test()
    details['nginx_test'] = {'ok': test['ok'], 'warnings': test['warnings'],
                             'log': ctx.log('nginx-t', test['output'].encode())}
    if not test['ok']:
        problems.append('sudo -n nginx -t did not pass')
    details['routing'] = routing_snapshot(routing_targets(enabled_config_texts()))
    details['cpt_before'] = cpt_probes()
    details['app_health'] = app_health()
    if details['app_health']['status'] != 200 or not isinstance(details['app_health']['json'], dict):
        problems.append('app.quillmd.com /health/ did not answer 200 JSON')
    details['cotenants'] = cotenant_check()
    if details['cotenants']['returncode'] != 0:
        problems.append('scripts/check-cotenants.sh did not pass')
    if details['cotenants']['judged_skipped']:
        problems.append(f'scripts/check-cotenants.sh judged {", ".join(details["cotenants"]["judged_skipped"])}, which '
                        'the installer told it to skip (CPT_INSTALLER_SKIP_HOSTS): this checkout\'s script does not '
                        'honour the skip')
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
    # release 1 (A7): the converter's own uid must be CPT Studio's alone too
    converter = inspect('container', CONVERTER)
    details['foreign_converter_uid_tasks'] = foreign_uid_tasks(
        CONVERTER_UID, [converter['Id']] if converter is not None and owned(converter, 'converter') else [])
    if details['foreign_converter_uid_tasks']:
        problems.append(f'uid {CONVERTER_UID}, the converter\'s, already runs {details["foreign_converter_uid_tasks"]} '
                        'task(s) outside CPT Studio')
    details['dns'] = {}
    for host in (DOMAIN, ADMIN_HOST):
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except socket.gaierror:
            infos = []
        found = {'a': sorted({info[4][0] for info in infos if info[0] == socket.AF_INET}),
                 'aaaa': sorted({info[4][0] for info in infos if info[0] == socket.AF_INET6})}
        details['dns'][host] = found
        if found != {'a': [PUBLIC_IPV4], 'aaaa': []}:
            problems.append(f'{host} must resolve to A {PUBLIC_IPV4} only')
    details['images'] = {ref: bool(inspect('image', ref)) for ref in (HELPER_IMAGE, POSTGRES_IMAGE)}
    if not all(details['images'].values()):
        problems.append('a pinned image (helper or postgres) is not present locally')
    # the Fable coder's source and copy are the only credentials paths read (CODER; Corti's source is no longer
    # required), and the earlier interpreter's own key copy is stat'd only to be reported (LEGACY_INTERPRETER_COPY;
    # never a problem)
    details['paths'] = helper_stat(list(dict.fromkeys([
        ETC_DIR, *LE_DIRS, ACME_CHALLENGE_DIR, PROVIDER_SOURCES, CODER['source'], CODER['target'],
        LEGACY_INTERPRETER_COPY])))
    problems += coding_source_problems(details['paths'])
    details['coding_source'] = 'present' if details['paths'][CODER['source']].get('exists') else 'absent'
    details['legacy_interpreter_copy'] = legacy_copy_state(details['paths'])
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
    # admin.quillmd.com's HTTP-01 route - the quillmd vhost's :80 block, QuillMD's file - which every lineage naming
    # admin renews through, the cpt-studio one included (ops/INSTALL.md, Known limits; refutation INGRESS-5)
    details['admin_acme'] = acme_probe(ctx, 'preflight', ADMIN_HOST)
    problems += acme_problems({ADMIN_HOST: details['admin_acme']})
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
    result = run_helper(H_SECRETS, {'app_keys': list(APP_ENV_KEYS), 'db_keys': list(DB_ENV_KEYS)},
                        mounts=[f'type=bind,src={ETC_DIR},dst=/target'], sensitive=True)
    # The Fable coder's credentials, after the set above and never part of it (CODER: the participants' rules). Corti's
    # source is no longer read and Astra's no longer copied; copies an earlier install wrote are left as they are, and
    # the earlier interpreter's own key copy is only reported.
    coding = coding_secrets()
    states = ', '.join(f'{name} {entry["state"]}' for name, entry in coding.items())
    legacy = legacy_copy_state(helper_stat([LEGACY_INTERPRETER_COPY]))
    return {'etc_dir': etc['etc_dir'], **result, 'coding_credentials': coding, 'legacy_interpreter_copy': legacy,
            'summary': f'secrets {result["state"]}; coding credentials: {states}; values never left the helper'
                       + (f'; {legacy["note"]}' if legacy['state'] == 'present' else '')}


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


# The image checks of the Fable coding build (DECISIONS D351-D353; the build specification, section 11), run with the
# other image gates' options (as the image's own user, on its read-only root, without a network). The image reads no
# PDF and runs no OCR now (the coding step sends the original file), so the earlier PDF gate and OCR version checks are
# gone. Two checks replace them:
#   soffice   LibreOffice converts an uploaded DOCX to PDF (`soffice --headless --convert-to pdf`, in a bounded child):
#             `soffice --version` must run and name LibreOffice; its version line is reported in the receipt, never
#             pinned (Debian's package moves with the pinned base image). HOME is the container's tmpfs, so a profile it
#             may want is written nowhere else.
#   anthropic the official SDK the coder sends through must import and be exactly the pinned release
#             (ANTHROPIC_SDK_VERSION; requirements.txt pins the same): another one would send differently than the
#             build was proven with.
# A failure of either refuses the image, with what the command printed in the failure log; so does a failure of the
# conversion gate below, which converts a Word file as the worker does.
ANTHROPIC_SDK_VERSION = '2.11.0'
ANTHROPIC_SDK_SCRIPT = 'import anthropic; print(anthropic.__version__)'


def image_soffice(smoke, image_id) -> str:
    """The image's `soffice --version` line (image checks above); refuses unless it ran and names LibreOffice."""
    done = docker(*smoke, '-e', 'HOME=/tmp', '--entrypoint', 'soffice', image_id, '--version', check=False,
                  timeout=120)
    journal('oneshot', 'image soffice version', done.returncode)  # A13
    named = [line.strip() for line in done.stdout.decode('utf-8', 'replace').splitlines()
             if line.strip().startswith('LibreOffice ')]
    if done.returncode or not named:
        raise InstallError(f'The image cannot run `soffice --version` (exit {done.returncode}), so every Word upload '
                           'would fail its conversion.', output=(done.stdout + done.stderr)[-8192:])
    return named[0]


def image_anthropic(smoke, image_id) -> str:
    """The anthropic SDK release the image imports (image checks above); refuses unless it is ANTHROPIC_SDK_VERSION."""
    done = docker(*smoke, '--entrypoint', 'python', image_id, '-c', ANTHROPIC_SDK_SCRIPT, check=False, timeout=120)
    journal('oneshot', 'image anthropic version', done.returncode)  # A13
    lines = [line.strip() for line in done.stdout.decode('utf-8', 'replace').splitlines() if line.strip()]
    found = lines[-1] if lines else ''
    if done.returncode or found != ANTHROPIC_SDK_VERSION:
        raise InstallError(f'The image does not import anthropic {ANTHROPIC_SDK_VERSION} (exit {done.returncode}, '
                           f'printed {found[:40]!r}).', output=(done.stdout + done.stderr)[-8192:])
    return found


# The conversion gate (the build specification, section 11): a real Word-to-PDF conversion inside the built image, as
# the worker runs one - the application's own entry point (studio.fable.document.convert_docx: LibreOffice in its
# bounded child, 60 s, a throwaway HOME and profile, no inherited environment), under the worker's runtime constraints
# (its user 10150:10150, a read-only root, /tmp a tmpfs, WORKER_LIMITS) and with no network - of a tiny synthetic Word
# document built here (synthetic_docx). It must answer one line whose PDF starts with %PDF-, or the image is refused:
# every Word upload would fail its conversion. The PDF's own bytes are recorded (size and sha256), never pinned:
# LibreOffice stamps a creation time in it.
CONVERSION_ANSWER = 'cpt-studio-conversion '
CONVERSION_TEXT = 'SYNTHETIC CONVERSION CHECK - FICTIONAL - NO PATIENT DATA'
CONVERSION_GATE = '''
import base64, hashlib, json
from studio.fable import document
pdf = document.convert_docx(base64.b64decode(DOCX))
print(ANSWER + json.dumps({'head': pdf[:5].decode('latin-1'), 'bytes': len(pdf),
                           'sha256': hashlib.sha256(pdf).hexdigest()}))
'''
DOCX_PARTS = {
    '[Content_Types].xml': (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'),
    '_rels/.rels': (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'),
    'word/document.xml': (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        '<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'),
}


def synthetic_docx(text=CONVERSION_TEXT) -> bytes:
    """A minimal Word document - the three parts a .docx needs (its content types, the package relationship and the
    main document part) - holding one paragraph of ``text`` (letters, digits, spaces and hyphens only, so nothing needs
    escaping), built with a fixed timestamp: the same bytes every time. Synthetic; no patient data."""
    if not re.fullmatch(r'[A-Za-z0-9 -]+', text):
        raise ValueError('the conversion check text is letters, digits, spaces and hyphens only')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in DOCX_PARTS.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content.replace('{text}', text).encode('utf-8'))
    return buffer.getvalue()


def image_conversion(image_id) -> dict:
    """The conversion gate (above): {'head', 'bytes', 'sha256'} of the PDF the image made of synthetic_docx(); refuses
    unless the conversion ran and its PDF starts with %PDF-."""
    source = (f'DOCX = {base64.b64encode(synthetic_docx()).decode("ascii")!r}\nANSWER = {CONVERSION_ANSWER!r}\n'
              + CONVERSION_GATE)
    done = docker('run', '--rm', '--pull=never', '--network', 'none', '--no-healthcheck', *hardening(*WORKER_LIMITS),
                  '-e', 'CPT_STUDIO_SECRET_KEY=image-smoke-check-only', image_id, 'manage', 'shell', '-c', source,
                  check=False, timeout=180)
    journal('oneshot', 'image conversion gate', done.returncode)  # A13
    answers = [line[len(CONVERSION_ANSWER):] for line in done.stdout.decode('utf-8', 'replace').splitlines()
               if line.startswith(CONVERSION_ANSWER)]
    try:
        found = json.loads(answers[0]) if len(answers) == 1 else None
    except ValueError:
        found = None
    if (done.returncode or not isinstance(found, dict) or found.get('head') != '%PDF-'
            or type(found.get('bytes')) is not int or found['bytes'] <= 5
            or not re.fullmatch(r'[0-9a-f]{64}', str(found.get('sha256')))):
        raise InstallError(f'The image cannot convert a Word document to PDF as its worker would (exit '
                           f'{done.returncode}: as {APP_UID}:{APP_UID}, on a read-only root with /tmp a tmpfs and no '
                           'network), so every Word upload would fail its conversion.',
                           output=(done.stdout + done.stderr)[-8192:])
    return {'head': found['head'], 'bytes': found['bytes'], 'sha256': found['sha256']}


def image_converter_self_test(image_id) -> dict:
    """The converter's own self-test in the built image (A7: it converts a Word file it builds in memory and checks
    the PDF header), as the converter runs - its user, its limits, a read-only root, a noexec /tmp - with no network.
    Refuses unless it exits 0 AND prints its success line (CONVERTER_SELF_TEST_OK): an exit 0 that says nothing is not a
    PDF made. {'exit', 'said'}: that line, at most 200 characters (synthetic text only)."""
    done = docker('run', '--rm', '--pull=never', '--network', 'none', '--no-healthcheck',
                  *hardening(*CONVERTER_LIMITS, user=f'{CONVERTER_UID}:{APP_UID}'), '--entrypoint', 'python', image_id,
                  *CONVERTER_SELF_TEST, check=False, timeout=180)
    journal('oneshot', 'image converter self-test', done.returncode)  # A13
    lines = [line.strip() for line in done.stdout.decode('utf-8', 'replace').splitlines() if line.strip()]
    said = [line for line in lines if line.startswith(CONVERTER_SELF_TEST_OK)]
    if done.returncode or not said:
        raise InstallError(f'The image\'s converter fails its self-test (exit {done.returncode}'
                           + ('' if said else f', no line starting "{CONVERTER_SELF_TEST_OK}"') + ') with no network, '
                           'so every Word round would fail.', output=(done.stdout + done.stderr)[-8192:])
    return {'exit': done.returncode, 'said': said[-1][:200]}


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
    check = docker(*smoke, '-e', 'CPT_STUDIO_SECRET_KEY=image-smoke-check-only', image['Id'], 'manage', 'check',
                   '--fail-level', 'ERROR', check=False, timeout=120)
    # Loading the WSGI application runs the middleware, which reads every static
    # file: as the image's own user on a read-only root, exactly as the web role.
    wsgi = docker(*smoke, '-e', 'CPT_STUDIO_SECRET_KEY=image-smoke-check-only', '--entrypoint', 'python',
                  image['Id'], '-c', 'import cptstudio.wsgi', check=False, timeout=120)
    journal('oneshot', 'image manage check', check.returncode)  # A13
    journal('oneshot', 'image wsgi load', wsgi.returncode)
    if check.returncode or wsgi.returncode:
        raise InstallError('The image fails Django system checks, or cannot load the web application as its own '
                           'user.', output=(check.stdout + check.stderr + wsgi.stdout + wsgi.stderr)[-8192:])
    office = image_soffice(smoke, image['Id'])
    sdk = image_anthropic(smoke, image['Id'])
    conversion = image_conversion(image['Id'])
    converter = image_converter_self_test(image['Id']) if has_converter(ctx.revision) else None  # A7
    return {'image_id': image['Id'], 'tag': tag, 'base': base, 'size_bytes': image.get('Size'),
            'source_archive_sha256': sha256(archive), 'build_log': build_log, 'soffice': office, 'anthropic': sdk,
            'conversion': conversion, 'converter_self_test': converter,
            'migrations': {'baseline': f'{ROLLING_BASELINE:04d}', 'after_baseline': migrations},
            'summary': f'built {tag} = {image["Id"][:19]}'}


def wait_converter(image_id, revision, *, attempts=60, interval=2.0) -> dict:
    """Readiness of the converter just started (A7): running and healthy (its health check pings the socket), then
    service_problems' role 'converter' holds, with no restart. Refused otherwise; the receipt says what was seen."""
    def check():
        found = converter_state(inspect('container', CONVERTER))
        return found['running'] and found['health'] == 'healthy', {'running': found['running'], 'health': found['health']}
    passed, observations = poll(check, attempts=attempts, interval=interval)
    container = inspect('container', CONVERTER) or {}
    problems = service_problems(container, 'converter', image_id) if container else ['container vanished']
    if labels_of(container).get(REVISION_LABEL) != revision:
        problems.append('it does not carry this revision\'s label')
    if not passed or problems or container.get('RestartCount'):
        raise InstallError(f'{CONVERTER} did not become ready: {problems or "health not observed"}. Every Word round '
                           'fails as busy until it is (ops/INSTALL.md, converter).',
                           details={'observations': observations[-5:]})
    return {'id': container['Id'], 'observations': len(observations)}


def phase_converter(ctx) -> dict:
    """Release 1 (A7, E3): cpt-studio-converter from this revision's image, outside the blue/green switch and
    idempotent: the convert volume (the socket alone) is ensured and owned as the converter needs it; a converter of
    this revision that runs healthy and sealed is kept; any other is stopped with CONVERTER_STOP_SECONDS - a conversion
    in progress finishes - and replaced (a conversion asked for in the few seconds between fails as busy, and can be
    retried). The worker of an older revision never uses it; the app phase refuses until it runs (converter_problem)."""
    image_id = installed_image(ctx)
    if not has_converter(ctx.revision):
        raise InstallError(f'Revision {ctx.revision[:12]} has no converter service ({", ".join(CONVERTER_FILES)}): '
                           'there is nothing to start.')
    current = inspect('container', CONVERTER)
    if current is not None and not owned(current, 'converter'):  # before the volume is touched (refutation A-7)
        raise InstallError(f'{CONVERTER} exists but is not a CPT Studio converter container; nothing was changed.')
    details = {'volume': ensure_volume(CONVERT_VOLUME, 'convert')}
    root = details['volume_root'] = run_helper(
        H_CONVERT_VOLUME, {'uid': CONVERTER_UID, 'gid': APP_UID, 'mode': CONVERT_ROOT_MODE},
        mounts=[f'type=volume,src={CONVERT_VOLUME},dst=/convert,volume-nocopy'])['root']
    # read back before anything starts: a root the converter's uid cannot write, or the worker's group cannot traverse,
    # would leave the converter unable to make its socket
    if root != {'uid': CONVERTER_UID, 'gid': APP_UID, 'mode': oct(CONVERT_ROOT_MODE)}:
        raise InstallError(f'The convert volume\'s root reads {root}, not {CONVERTER_UID}:{APP_UID} '
                           f'{oct(CONVERT_ROOT_MODE)}; nothing was started.', details=details)
    current = inspect('container', CONVERTER)
    if current is not None:
        if not owned(current, 'converter'):
            raise InstallError(f'{CONVERTER} exists but is not a CPT Studio converter container; nothing was changed.')
        found = converter_state(current)
        if (found['image'] == image_id and found['revision'] == ctx.revision and found['running']
                and found['health'] == 'healthy' and not service_problems(current, 'converter', image_id)):
            return {**details, 'state': 'present', 'converter': found,
                    'summary': f'{CONVERTER} already runs {image_id[:19]}, sealed and healthy'}
        details['replaced'] = found
        details['replaced_log'] = keep_container_log(current, 'converter')  # A13: ids only, before it is removed
        docker('stop', '--time', str(CONVERTER_STOP_SECONDS), CONVERTER, timeout=CONVERTER_STOP_SECONDS + 60)
        docker('rm', '--force', current['Id'], timeout=60)
    docker('run', '-d', *converter_args(image_id, ctx.revision), quiet=True)
    details['started'] = wait_converter(image_id, ctx.revision)
    details['state'] = 'replaced' if 'replaced' in details else 'started'
    return {**details, 'summary': f'{CONVERTER} running {image_id[:19]} with no network ({details["state"]})'}


def phase_db(ctx) -> dict:
    postgres = inspect('image', POSTGRES_IMAGE)
    if postgres is None:
        raise InstallError('The pinned postgres image is not present locally.')
    details = {'network': ensure_network(), 'db_volume': ensure_volume(DB_VOLUME, 'db-data'),
               'files_volume': ensure_volume(FILES_VOLUME, 'files')}
    files_volume_helper({})
    container = inspect('container', DB_CONTAINER)
    if container is not None and not (container.get('State') or {}).get('Running'):
        # refutation, installer lens A-6: never started here - a database that stopped did so for a reason, and the
        # memory.peak a start begins would describe minutes, not its use
        raise InstallError(f'{DB_CONTAINER} exists but is stopped. The db phase never starts it: find out why it stopped, '
                           f'start it by hand (docker start {DB_CONTAINER}), then rerun. It was not started and its '
                           'limits and settings were not changed.')
    if container is None:
        problem = port_problem(DB_PORT, DB_CONTAINER)
        if problem:
            raise InstallError(problem)
        docker('run', '-d', *db_args(), input=read_protected_env(DB_ENV, DB_ENV_KEYS), quiet=True)
        details['container'] = 'created'
    else:
        # its memory limits are read below, where an existing container's are updated in place (A3); everything else
        # that differs refuses before anything changes - it cannot be updated without recreating the container
        problems = db_container_problems(container, postgres['Id'], memory=False)
        if problems:
            raise InstallError(f'{DB_CONTAINER} exists but ' + '; '.join(problems) + '. Nothing was changed: recreating '
                               'it would interrupt the site, which is the owner\'s call (ops/INSTALL.md, db).')
        details['container'] = 'present'
    wait_db_ready()
    details['memory'] = db_memory(inspect('container', DB_CONTAINER) or {})  # A3
    container = inspect('container', DB_CONTAINER)
    cgroup = db_cgroup()
    skipped = details['memory']['state'] == 'skipped'  # its memory limits stay as they are, and said
    problems = db_container_problems(container, postgres['Id'], cgroup, memory=not skipped)
    if problems:
        raise InstallError(f'{DB_CONTAINER} ' + '; '.join(problems) + '.', details={**details, 'cgroup': cgroup})
    details['statement_logging'] = db_statement_logging()  # A5
    memory = (f'memory limits left as they are ({details["memory"]["why"]})' if skipped
              else f'memory {DB_MEMORY} with no swap ({details["memory"]["state"]})')
    details.update(container_id=container['Id'], image_id=postgres['Id'], cgroup=cgroup,
                   summary=f'{DB_CONTAINER} ready on 127.0.0.1:{DB_PORT} ({details["container"]}); {memory}; '
                           'statement text kept out of its log')
    return details


def pair_modes(mode, participants=None, interpreter=None, coding=None) -> str:
    """'provider live, astra disabled, fable live': how the pair was started; ', interpreter live' follows when the
    caller names the interpreter's mode (``interpreter``), and ', coding live' when it names the Fable coder's
    (``coding``)."""
    return ', '.join([f'provider {mode}'] + [f'{name} {(participants or {}).get(name) or "disabled"}'
                                             for name in PARTICIPANTS]
                     + ([f'interpreter {interpreter}'] if interpreter is not None else [])
                     + ([f'coding {coding}'] if coding is not None else []))


def coding_summary(mode) -> str:
    """'coding live, effort max': how an app phase starts its pair (the Fable coding build runs no other provider)."""
    return f'coding {mode}, effort {CODING_EFFORT}'


def after_swap_failure(image_id, mode, states, error, parked) -> str:
    """The receipt of an app phase stopped once its new pair runs (refutation p2, install2:2): whether the stored list
    states were recomputed (``states``, RECOMPUTE_STATES' answer, or None), what stopped it, and what is left to do.
    ``mode``: the coding mode the pair runs with."""
    cause = str(error) or type(error).__name__
    running = f'web and worker running {image_id[:19]} ({coding_summary(mode)}), but '
    back = 'or, to go back, run --phase rollback-app, then rename the parked pair back.'
    if states is None:
        if any((parked or {}).values()):
            return (running + f'the stored list states were not recomputed ({cause}) and the previous pair is still '
                    'parked (*-previous): remove it by hand, then rerun --phase app, which recomputes them; ' + back)
        return running + f'the stored list states were not recomputed ({cause}): rerun --phase app.'
    return (running + f'the stored list states were recomputed ({len(states.get("changed") or {})} changed) and the '
            f'previous pair (*-previous) could not be removed ({cause}): remove what is left of it by hand; ' + back)


def check_credential_files(mode, live, interpreter='disabled', coding='disabled'):
    """Every credentials file a live provider, participant, interpreter or Fable coder needs, before anything changes:
    a missing source leaves no file, and its holder is installed disabled or not at all (HARNESS.md 8); a live
    interpreter or coder needs the file the secrets phase copied (design/FINAL.md 13; CODER). An app phase names the
    coder alone; a switch-back names the previous pair's modes. Release 1 (A8): a live legacy mode - Corti, a harness
    participant, the earlier interpreter - is refused here too, whatever the arguments said: none of them has a BAA."""
    problem = legacy_live_problem(SimpleNamespace(provider_mode=mode, interpreter_mode=interpreter,
                                                  **{f'{name}_mode': 'live' for name in live}))
    if problem:
        raise InstallError(problem)
    wanted = (([CORTI_TARGET] if mode == 'live' else []) + [PARTICIPANTS[name]['target'] for name in live]
              + ([INTERPRETER['target']] if interpreter == 'live' else [])
              + ([CODER['target']] if coding == 'live' else []))
    found = helper_stat(list(dict.fromkeys(wanted))) if wanted else {}
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
    if coding == 'live' and found[CODER['target']] != {'exists': True, 'kind': 'file', 'uid': APP_UID, 'gid': APP_UID,
                                                       'mode': '0o400'}:
        raise InstallError(f'--coding-mode live: {CODER["target"]} is not the {APP_UID}:{APP_UID} 0400 file the '
                           f'secrets phase copies from {CODER["source"]}; nothing was changed. Place the source and '
                           'run --phase secrets first.')


def check_credential_parsing(image_id, env, mode, live, interpreter='disabled', coding='disabled'):
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
    if coding == 'live':
        # And the live Fable coder's (CODER): its own loader, the coder itself disabled; its error is kept only once a
        # root helper found no value from the file in it.
        parsed = oneshot(image_id, ['manage', 'shell', '-c', CODING_CREDENTIALS_CHECK], env, network='none',
                         coding_file=True, timeout=120)
        if parsed.returncode or b'coding-credentials-parse-ok' not in parsed.stdout:
            output = parsed.stderr[-2048:]
            raise InstallError(f'The application cannot load {CODER["target"]} as mounted for the worker '
                               '(--coding-mode live; format and permissions only; nothing was sent or changed).',
                               output=output if credential_free([output], [CODER['name']]) else b'')


# Release 1 (RELEASE-1-SPEC 6.2): the migrate one-shot waits at most MIGRATE_LOCK_TIMEOUT for a table's lock, so an
# ALTER TABLE never queues behind a long transaction - holding every later reader of that table behind itself - for
# longer than that. It is libpq's PGOPTIONS in the one-shot's environment: the migration files, which migration_verdict
# reads, are untouched (a RunSQL setting it would be refused there). Django applies each migration in a transaction of
# its own on PostgreSQL (none of this app's sets atomic = False), so an attempt the timeout cancels leaves that
# migration unapplied, and the one-shot is run again, up to MIGRATE_LOCK_RETRIES more times, after MIGRATE_RETRY_PAUSE
# seconds. Any other failure is not retried.
MIGRATE_LOCK_TIMEOUT = '5s'
MIGRATE_LOCK_RETRIES = 3
MIGRATE_RETRY_PAUSE = 10
LOCK_TIMEOUT_RE = re.compile(rb'canceling statement due to lock timeout|LockNotAvailable|\b55P03\b')


def migrate_bounded(image_id, env_bytes) -> tuple:
    """(the last migrate one-shot, every attempt's output joined, the attempts made): migrate with a lock timeout,
    again on a lock timeout alone (MIGRATE_LOCK_RETRIES)."""
    environment = [*runtime_env('disabled', ''), '-e', f'PGOPTIONS=-c lock_timeout={MIGRATE_LOCK_TIMEOUT}']
    outputs = []
    for attempt in range(1, MIGRATE_LOCK_RETRIES + 2):
        done = oneshot(image_id, ['migrate'], env_bytes, environment=environment)
        output = done.stdout + done.stderr
        outputs.append(f'--- migrate attempt {attempt} (exit {done.returncode})\n'.encode() + output)
        if not done.returncode or not LOCK_TIMEOUT_RE.search(output) or attempt > MIGRATE_LOCK_RETRIES:
            return done, b''.join(outputs), attempt
        time.sleep(MIGRATE_RETRY_PAUSE)
    raise AssertionError('unreachable')


def phase_app(ctx) -> dict:
    """The Fable coding build's app phase (DECISIONS D351-D353): the new pair runs the Fable coder in the mode
    --coding-mode gives (live on the live install, under --authorization-ref) and every earlier provider disabled -
    Corti, the participants and the interpreter - so the Anthropic copy is the only credentials file it requires, and
    its worker alone mounts it. Everything else is as it always was: the migration, the reads before the switch, the
    blue/green replacement and the recompute of the stored list states. No access check: nothing is sent."""
    mode, reference = coding_mode(ctx.args), ctx.args.authorization_ref or ''
    if reference and run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{ctx.revision}:{reference}'],
                         check=False).returncode:
        raise InstallError('--authorization-ref is not a file tracked at the revision.')
    # the coupling as it is now, before the migration (refutation R2 round 1, WAYBACK-5: the newest successful preflight
    # can be older than a half-written two-file write, which the root helper refused only at the switch)
    problem = coupling_problem(read_coupling()) or unrecorded_ingress_problem(ctx)  # round 2, INTENT-1, GUARDS-3
    if problem:
        raise InstallError(f'{problem}; nothing was started.')
    image_id = installed_image(ctx)
    # release 1 (A7): a revision that has the converter starts a worker that requires it, so it must already run,
    # healthy, from this revision's image, and sealed as phase_converter starts it (refutation round 1, installer-5) -
    # before anything changes
    if has_converter(ctx.revision):
        problem = converter_problem(image_id, ctx.revision) or '; '.join(
            f'{CONVERTER}: {each}' for each in service_problems(inspect('container', CONVERTER) or {}, 'converter',
                                                                image_id))
        if problem:
            raise InstallError(f'{problem}: run --phase converter first. Nothing was started.')
    require_db()
    check_credential_files('disabled', [], coding=mode)
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    check_credential_parsing(image_id, env, 'disabled', [], coding=mode)
    migrate, migrate_output, attempts = migrate_bounded(image_id, env)
    migrate_log = ctx.log('migrate', migrate_output)
    if migrate.returncode:
        timed_out = bool(LOCK_TIMEOUT_RE.search(migrate.stdout + migrate.stderr))
        raise InstallError(f'Migrations failed (exit {migrate.returncode}'
                           + (f'; a table\'s lock was not free within {MIGRATE_LOCK_TIMEOUT}, {attempts} times: a long '
                              'transaction holds it - try again once it has ended' if timed_out else '')
                           + f'); see {migrate_log}.', details={'migrate_attempts': attempts})
    # The open stages of a kind this revision's worker does not run - every kind of the pipeline before the Fable coding
    # build, and any a newer revision added - are read and recorded, never refused on (an earlier revision's worker, which
    # claims a job of any kind, ended on one: refutation r1, migrate-3). This revision's worker claims only the kinds of
    # its own STAGES (studio.jobs.claim_next), its startup sweep settles every running stage of any kind (cancelled, or
    # unknown when it was sending), and a member's Review again retires a stage of the earlier pipeline left queued
    # (studio.decisions.retry); one cancelled as its encounter's latest stage is never resumed by it (a Resume continues
    # a coding round). Refusing here would refuse every install over a site where one stage was ever stopped.
    unrunnable = app_script(image_id, env, UNRUNNABLE_STAGES, {},
                            what='Reading the queue for stages this revision does not run')
    # Design v2 (FINAL-V2 6.2 [R:MO-1]): on the target, before the switch, no design v1 row - v1 rows only, so v2's own
    # rows never trip it: a fix release, the re-install after a switch-back and a same-revision re-run all pass.
    v1 = v1_rows(image_id, env)
    refusal = v1_rows_refusal(v1)
    if refusal:
        raise InstallError(refusal[:1].upper() + refusal[1:] + '.', details={'v1_rows': v1,
                                                                            'unrunnable_stages': unrunnable})
    # Amendment 1, 9.5: the install counts, read-only, before the switch, printed into this receipt - never a refusal.
    counts = install_counts(image_id, env)
    try:
        result = _app_after_counts(ctx, image_id, env, mode, reference, migrate_log, unrunnable, v1, counts)
    except InstallError as error:  # the receipt of a failure after the read carries the counts too
        if error.details is None or isinstance(error.details, dict):
            error.details = {**(error.details or {}), 'install_counts': counts, 'migrate_attempts': attempts}
        raise
    return {**result, 'migrate_attempts': attempts}  # each attempt's output is in migrate_log


def _app_after_counts(ctx, image_id, env, mode, reference, migrate_log, unrunnable, v1, counts) -> dict:
    """phase_app once the target is known to hold no design v1 row and the install counts are read: the replacement
    and the recompute of the stored list states, as they always were."""
    # The coder's mode is named only when it is not the default, as swap_services leaves WEB_PORT to wait_service: a
    # stand-in of replace_services keeps the six arguments it always had. Corti, the participants and the interpreter
    # are started disabled (replace_services' defaults).
    left = retire_left_parked(ctx)  # refutation B-11: a switch-back's parked pair, kept, then removed first
    services = replace_services(ctx, image_id, env, 'disabled', reference, None,
                                **({'coding': mode} if mode != 'disabled' else {}))
    if left is not None:
        services['parked_retired'] = left
    coding = {'mode': mode, 'effort': CODING_EFFORT, 'credentials_loaded': mode == 'live',
              'figures': coding_figures()}
    # Refutation p1, migrate-2: the stored list states are recomputed with this revision's derivation (RECOMPUTE_STATES)
    # - once this pair has replaced the old one, never before, so a failure path restores the old pair over the states
    # it derived. Blue/green (I-state): only once the drained old web has stopped too (switch_services' S5). Nothing is
    # refused for it (round-7c8 skeptic, sk:2: refusing while an outcome was unknown also refused a same-revision re-run
    # - a mode switch during an incident - and the reinstall the failure path's receipt asks for, until a member
    # reconciled on the running web: a released, paid send, and on a restored older web one its own rules make).
    # Nothing is sent.
    # Refutation p2, install2:2: and before the parked pair is removed (retire_parked), so the documented recovery for a
    # parked pair left in place (a `docker rm` that fails, an installer interrupted) finds them recomputed; whatever
    # stops this phase once the new pair runs - the recompute, the removal, a Ctrl-C - leaves a receipt that says
    # whether they were, and what is left to do.
    states, parked = None, services.get('replaced')
    if isinstance(services.get('steps'), dict):
        services['steps']['S6'] = utc_now_ms()  # blue/green: the recompute and the removal of the parked pair
    try:
        states = app_script(image_id, env, RECOMPUTE_STATES, {}, what='Recomputing the stored list states')
        services['logs_kept'] = retire_parked(parked)  # A13: ids-only copies, then the removal
    except BaseException as error:  # noqa: BLE001 — the pair is installed: the receipt says what is left to do
        raise InstallError(after_swap_failure(image_id, mode, states, error, parked)
                           + sessions_ended_said(services.get('sessions_ended')),
                           details={**services, 'states_recomputed': states, 'coding': coding}) from error
    return {'image_id': image_id, 'coding': coding, 'authorization_ref': reference, 'migrate_log': migrate_log,
            'unrunnable_stages': unrunnable, 'states_recomputed': states, **services, 'v1_rows': v1,
            'install_counts': counts,
            'summary': f'web and worker running {image_id[:19]} ({coding_summary(mode)})'
                       + switched_summary(services) + sessions_summary(services.get('sessions_ended'))
                       + '; no design v1 row' + counts_summary(counts)}


def retire_left_parked(ctx):
    """The parked pair a switch-back left in place because its log could not be kept (its receipt's 'parked_left';
    refutation, rollback lens B-11): the copy retried, then the pair removed - before this app plans its switch, which a
    parked pair would refuse. Only the containers that receipt names; any other '*-previous' is refused, nothing started
    or stopped. None when no switch-back left one; raises when the copy fails again."""
    entry = latest_receipt_entry(ctx.receipts, 'switch-back', ctx.revision)
    left = ((entry[1].get('details') or {}).get('parked_left') or {}) if entry is not None else {}
    if not left:
        return None
    parked = {}
    for role in ('web', 'worker'):
        container = inspect('container', SERVICES[role] + '-previous')
        if container is None:
            continue
        wanted = (left.get('pair') or {}).get(role)
        if container.get('Id') != wanted or not owned(container, role):
            raise InstallError(f'{SERVICES[role]}-previous is not the {role} the switch-back left in place '
                               f'({str(wanted)[:12]}); nothing was started or stopped (ops/INSTALL.md, Recovery notes).')
        parked[role] = {'id': container['Id'], 'revision': labels_of(container).get(REVISION_LABEL)}
    if not parked:
        return {'retired': {}, 'why': 'the pair the switch-back left was gone already'}
    try:
        return {'retired': retire_parked(parked), 'switch_back_receipt': entry[0].name}
    except InstallError as error:
        raise InstallError(f'The parked pair the switch-back left in place could not be kept and removed ({error}); '
                           'nothing was started or stopped.') from error


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
    removed; after a same-revision re-run, the pair switch_back_target reads, DECISIONS D83), by the blue/green switch
    in reverse. rollback-app's checks run first and refuse, stopping nothing, while
    this revision recorded what an older revision would act on, or show, wrongly (undo_hazards). ``--provider-mode``,
    the participant modes, ``--interpreter-mode`` and ``--coding-mode`` are the previous pair's, as its own app phase
    was given them (a revision before the Gemini migration has no interpreter: leave it disabled; one before AMENDMENT-2
    has no Fable adapter, so its interpreter's loader check fails live: give it disabled or replay; one before the Fable
    coding build has no coder, so its coder's loader check fails live: give --coding-mode disabled). What this revision
    made from event
    inventories is never a refusing reason: the receipt declares it in a note and the switch goes on (ADJUDICATION
    P-1). DECISIONS D59, D65, D82, D95 and D110: it refuses only on encounters with a record created since
    replaced_since's time - the earliest time recorded by the app receipt the pair is read from and by every app
    receipt of this revision written after its last successful switch-back to that pair, whatever each replaced and
    however it ended (that switch-back's own start when the receipt the pair is read from is older than it) - never
    across that switch-back and never the current containers' creation."""
    problem = coupling_problem(read_coupling()) or unrecorded_ingress_problem(ctx)
    if problem:
        raise InstallError(f'{problem}; nothing was started or stopped.')
    mode, reference = ctx.args.provider_mode, ctx.args.authorization_ref or ''
    modes = participant_modes(ctx.args)
    live = [name for name in PARTICIPANTS if modes[name] == 'live']
    interpreter = interpreter_mode(ctx.args)
    coding = coding_mode(ctx.args)  # disabled unless given: a pair before the Fable coding build reads none
    # D83: the receipt the target is read from - the newest successful app receipt, or after a same-revision re-run the
    # newest since the last switch-back naming another revision whose image is present - and the since is read from it
    entry, prev_image, prev_revision = switch_back_target(ctx, require_receipt_entry(ctx, 'app'))
    if reference and run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{prev_revision}:{reference}'],
                         check=False).returncode:
        raise InstallError('--authorization-ref is not a file tracked at the previous revision.')
    image = inspect('image', prev_image)
    if image is None or labels_of(image).get(REVISION_LABEL) != prev_revision or not owned(image, 'app-image'):
        raise InstallError(f'The previous image {prev_image[:19]} is not present with revision {prev_revision[:12]} and '
                           'the CPT Studio label; nothing was changed.')
    image_id = installed_image(ctx)
    # release 1 (A7): a previous revision that has the converter gets a worker that requires it (any CPT Studio
    # converter that runs healthy: the protocol is the converter's own); an older one converts in-process as before
    if has_converter(prev_revision):
        problem = converter_problem(prev_image)
        if problem:
            raise InstallError(f'{problem}: the previous revision\'s worker requires it; run --phase converter first. '
                               'Nothing was started or stopped.')
    require_db()
    plan = replacement_plan(ctx)
    if plan['mode'] != 'blue-green' or plan['web']['revision'] != ctx.revision or plan['web']['image'] != image_id:
        raise InstallError(f'The site is not served by this revision\'s web through its HTTPS stage, so there is '
                           'nothing to switch back from; nothing was changed.', details={'plan': plan})
    preflight = require_receipt(ctx, 'preflight')
    check_credential_files(mode, live, interpreter, coding)
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    check_credential_parsing(prev_image, env, mode, live, interpreter, coding)
    since = replaced_since(ctx, entry)  # D59, D82: the touched filter's since, read once for every check of this phase
    reads = target_reads(prev_image, env, stage_kinds_of(prev_image, env))
    hazards = switch_back_hazards(undo_hazards(image_id, env, ctx.revision), reads,
                                  touched_encounters(image_id, env, since))  # D51
    if not isinstance(hazards, dict):  # D66: an answer that does not say what it read is never read as "none"
        raise InstallError('The read of what an older revision would act on wrongly gave no answer it could be judged by; '
                           'nothing was started or stopped.', details={'hazards': hazards})
    if hazards:
        raise InstallError(f'{hazard_summary(hazards)} hold records an older revision would act on, or show, wrongly '
                           'under its own rules; nothing was started or stopped. Clear them on this revision\'s web '
                           '(ops/INSTALL.md, Reinstalling an older revision), then rerun --phase switch-back.',
                           details={'hazards': hazards, 'touched_since': since.isoformat()})
    # refutation round 1, rollback-1 and rollback-2: no way back to a revision without release 1's disposal while a
    # practice is closed or a document destroyed (read again at B4, before anything is closed)
    refusal, disposed = disposal_refusal(image_id, env, prev_revision)
    if refusal:
        raise InstallError(f'{refusal[:1].upper()}{refusal[1:]}; nothing was started or stopped.',
                           details={'disposal': disposed})
    services = switch_back_services(ctx, image_id, env, prev_image, prev_revision, mode, reference, modes,
                                    preflight=preflight, plan=plan, interpreter=interpreter, reads=reads,
                                    touched_since=since, **({'coding': coding} if coding != 'disabled' else {}))
    availability = services.get('availability') or {}
    note = (services.get('not_carried_back') or {}).get('note')
    named = pair_modes(mode, modes, interpreter, coding if coding != 'disabled' else None)
    # refutation INSTALLER-5, INGRESS-8: a previous revision from before release 1 of D396 answers the admin host 400,
    # which this revision's stage still routes to it - declared, never a failure, until ingress-rollback runs
    admin = (None if serves_admin_host(prev_revision) else
             f'{ADMIN_HOST} answers {prev_revision[:12]}\'s 400 (that revision does not serve the admin host) until '
             '--phase ingress-rollback gives it back to the quillmd vhost')
    return {'image_id': image_id, 'previous': {'image': prev_image, 'revision': prev_revision},
            'provider_mode': mode, 'authorization_ref': reference, 'participants': modes,
            'interpreter_mode': interpreter, 'coding_mode': coding, **services, 'admin_host': admin,
            'summary': f'switched back to {prev_revision[:12]} ({named}) on '
                       f'{plan["idle"]}: {availability.get("samples", 0)} availability samples, '
                       f'{availability.get("non_200_count", 0)} not 200' + (f'; {note}' if note else '')
                       + sessions_summary(services.get('sessions_ended')) + (f'; {admin}' if admin else '')
                       + ('; FINDING: this revision\'s parked pair was left in place (its log could not be kept): '
                          'the next app keeps it, then removes it' if services.get('parked_left') else '')}


def switch_back_target(ctx, entry) -> tuple:
    """DECISIONS D83 (refutation round 3, finding 14): (the app receipt the switch-back reads its target from, as (path,
    record); the target web's image; its revision). ``entry`` is the newest successful app receipt of this revision
    (require_receipt_entry), and the target is the web it replaced. When that web is this same revision - a
    same-revision re-run: a provider-mode switch, an access check run again, the re-run a failed app's receipt asks for
    once its parked pair is removed - the target is read instead from the newest app receipt of this revision written
    since its last successful switch-back that names ANOTHER revision whose image is still present (newest first; a
    receipt whose image is gone is passed over). That receipt is a successful one, or one that failed once its switch
    had finished: it records the web it replaced (replaced_web) only when the old web was parked and this revision's
    pair served - its recompute, the removal of the parked pair or an access check failed after it (finding 14 (b):
    the first app over the target, failed so, then recovered and run again). With none, there is nothing to switch back
    to: an app whose receipt records no replaced web (the S4 keep layout, an S5 failure, an undo) leaves none. The
    receipt returned is the one replaced_since reads the since from."""
    image, revision = replaced_web(entry[1])
    if image is None:
        raise InstallError("This revision's app receipt names no previous web (image and revision) to switch back to; "
                           'nothing was changed.')
    if revision != ctx.revision:
        return entry, image, revision
    bound = last_switch_back(ctx)
    for path in sorted(ctx.receipts.glob('app-*.json'), reverse=True):
        if written_after(path, bound) is not True:  # before that switch-back, or the order cannot be told
            continue
        record = json.loads(path.read_text(encoding='utf-8'))
        if not (isinstance(record, dict) and record.get('phase') == 'app' and record.get('revision') == ctx.revision):
            continue
        image, revision = replaced_web(record)
        if image is None or revision == ctx.revision:
            continue
        found = inspect('image', image)
        if found is not None and labels_of(found).get(REVISION_LABEL) == revision and owned(found, 'app-image'):
            return (path, record), image, revision
    raise InstallError('The pair the app phase replaced is this same revision, and no app receipt of this revision '
                       'since its last switch-back names another revision whose image is present: there is nothing to '
                       'switch back to.')


def pair_created_at():
    """When this revision's pair was created: the earliest creation time of its web and worker containers (the 'since'
    every close of an undo reads)."""
    current = [inspect('container', SERVICES[role]) for role in SERVICES]
    return min(created_at(container) for container in current if container is not None)


def replaced_since(ctx, entry) -> dt.datetime:
    """DECISIONS D59 (the S17 refutation round 2, finding 12), D65, D82, D95 and D110: the 'since' of a switch-back's
    touched filter (touched_encounters; D51) - when this revision's first app phase began since it last returned to the
    pair the switch-back returns to, whatever that app replaced and however it ended. ``entry`` is the app receipt the
    switch-back reads that pair from (switch_back_target, D83: the newest successful one, or after a same-revision
    re-run the one it reads instead). The bound is this revision's newest successful switch-back to that target
    (last_switch_back; D82, refutation round 3, finding 13): that switch-back completed, so what the target wrote while
    it served again, until this revision's next app began, is its own status quo, and the since never reaches across it.
    A switch-back that did not complete (refused at B7: D65's recovery), one to another target and another revision's
    set no bound; nor is there one when ``entry`` names no target revision. Counted: ``entry`` and every app receipt of
    this revision written after the bound, whatever it replaced and however it ended (D95, the round-3 review of
    D82/D83; D110, refutation round 4, finding 21) - a successful one, over the target or another revision (D65: the app
    run again after a switch-back refused at B7 names the same target, and what this revision wrote under its earlier
    pair is no more the target's than before); one that failed once its switch had finished (D83 may read it as the
    target); one undone after it parked a role (replaced={'worker'}); a swap undone after its web had served, whose
    receipt records no 'replaced' (finding 21: hazards, stages_closed and states_put_back); one interrupted, or refused
    before anything changed. Most of them may have put this revision's pair in front of traffic without the receipt
    saying so (one refused before anything changed did not, and says so); the rule reads no receipt's account of that,
    so none is asked whether it served: an earlier since names more encounters, which only refuses more
    (fail-closed). Receipts are ordered by the stamps their names carry (written_after); one whose order cannot be told
    is counted (fail-closed). The since is the earliest time those receipts record for their phases (receipt_moments:
    main's started_at, taken before anything of that phase ran, and the steps a blue/green switch stamped); a counted
    receipt that records none counts from when it was written (written_moment). When ``entry`` itself is older than the
    bound (no successful app has replaced the target since: a later app failed, or replaced another revision), the since
    is the earliest of that switch-back's own start and the receipts counted after it - never across it, and fail-closed
    after it. Never the current containers' creation: a later app phase of this same revision that installed a pair and
    then failed (its receipt not ok - a recompute that failed, or an access check: the pair stays installed) created
    them, and what this revision wrote under its earlier pair is not the target's status quo. When ``entry`` records no
    time (and is not older than the bound), the since is the earliest creation time of this revision's containers
    (pair_created_at), of the receipts counted, and of every app receipt of this revision written after ``entry`` (the
    earliest time each records, else when it was written). The closes of B4 and B7 keep their own since (they close this
    pair's stages)."""
    path, record = entry
    target = replaced_web_entry(record).get('revision')
    bound = last_switch_back(ctx, target) if target else None  # D82
    earlier = []
    for other_path in sorted(ctx.receipts.glob('app-*.json')):
        if other_path.name == path.name or written_after(other_path, bound) is False:
            continue  # D82: a receipt written before the switch-back that last returned to this target is never read
        other = json.loads(other_path.read_text(encoding='utf-8'))
        # D95, D110 (refutation round 4, finding 21): every app receipt of this revision written after that bound
        # counts, whatever it replaced and however it ended. D95 counted a successful one, or one that parked a role
        # ('replaced' non-empty); a swap undone after its web had served records no 'replaced', so its window was
        # dropped and a record written in it was handed to the target. A receipt cannot always say whether its phase
        # put this revision's pair in front of traffic, so none is asked: an earlier since names more encounters
        # (fail-closed)
        if isinstance(other, dict) and other.get('phase') == 'app' and other.get('revision') == ctx.revision:
            earlier += receipt_moments(other) or [moment for moment in (written_moment(other_path),) if moment]
    if written_after(path, bound) is False:  # D82: ``entry`` is older than the switch-back that returned to its target
        # (that receipt's stamp is told, so written_moment gives a time when it records none)
        return min(earlier + (receipt_moments(bound[1]) or [written_moment(bound[0])]))
    own = receipt_moments(record)
    if own:
        return min(own + earlier)
    moments = [pair_created_at()] + earlier
    for later in sorted(ctx.receipts.glob('app-*.json')):
        if later.name <= path.name:
            continue
        other = json.loads(later.read_text(encoding='utf-8'))
        if isinstance(other, dict) and other.get('phase') == 'app' and other.get('revision') == ctx.revision:
            moments += receipt_moments(other) or [moment for moment in (written_moment(later),) if moment is not None]
    return min(moments)


def switch_back_services(ctx, image_id, env_bytes, prev_image, prev_revision, provider_mode, authorization_ref,
                         participants, *, preflight, plan, interpreter=None, reads=None, touched_since=None,
                         coding=None) -> dict:
    """The switch in reverse, never stopping the serving web first:

      B2  start the previous revision's web, INCOMING_WEB, on the idle port; health_ok for ITS revision; smoke_web
      B3  park this revision's worker (its current stage finishes)
      B4  read again that co-tenant routing and app.quillmd.com answer as the preflight baseline (the switch is verified
          against it) and that this revision recorded nothing an older revision would act on, or show, wrongly - so
          nothing is closed for a switch that cannot pass (refutation r2, L6-4) - then close every stage this
          revision's pair queued, ran or left resumable since it was created, and every open stage of a kind the
          previous worker does not run (close_undone_stages, rollback-app's rule); refuse to go on while the close
          names a record; put back the list states the previous revision labels otherwise; count what this revision
          coded that is not carried back, the receipt's declared note, which never refuses (coding_note)
      B5  switch the vhost's upstream to the idle port (/health/ = the previous revision through the public path)
      B6  drain this revision's web, stop it and park it; the previous web takes the canonical name
      B7  close again what this revision's web started between B4 and the end of its drain (requests it accepted
          before the switch); this also closes what a member started on the previous web during that window
          (ops/INSTALL.md, Known limits); count again what this revision coded - before any refusal, so a receipt
          that stops here carries it too (D59); put back again; hold the previous worker while the close names a
          record
      B8  start the previous worker
      B9  remove this revision's parked pair (its image is kept)
    When the previous revision and this one do not share release 1's session policy (sessions_end_needed, read before
    anything starts), every session is ended at B4, after its close and before B5 (end_every_session; refutation round
    1, rollback-0 and rollback-3). The baseline is read before anything starts too. Before B5 every failure resumes
    this revision's pair; from B5 on the previous web serves and the receipt says what is left. ``touched_since``: the
    since of every touched filter (replaced_since, D59 and D82; read from the app receipt switch_back_target gives, D83,
    when not given) - the closes keep their own, this pair's creation and B4's close."""
    live, idle = plan['live'], plan['idle']
    current = {role: inspect('container', SERVICES[role]) for role in SERVICES}
    since = min(created_at(container) for container in current.values() if container is not None)
    if touched_since is None:
        touched_since = replaced_since(ctx, switch_back_target(ctx, require_receipt_entry(ctx, 'app'))[0])
    kinds = stage_kinds_of(prev_image, env_bytes)
    reads = target_reads(prev_image, env_bytes, kinds) if reads is None else reads  # D51

    def hazards_now(hazards):  # D51: what this switch-back refuses on, read again whenever hazards are read
        return switch_back_hazards(hazards, reads, touched_encounters(image_id, env_bytes, touched_since))  # D59
    reason = f'revision {ctx.revision[:12]} was switched back to {prev_revision[:12]} (switch-back)'
    drifted = ingress_checks(ctx, preflight)
    if drifted:
        raise InstallError(baseline_problem(drifted, 'nothing was started or stopped'), details={'baseline': drifted})
    try:  # refutation round 1, rollback-0 and rollback-3: decided before anything starts, from both revisions' trees
        ends_sessions = sessions_end_needed(ctx.revision, prev_revision)
    except InstallError as error:
        raise InstallError(f'{error} Nothing was started or stopped.') from error
    steps, parked, started, progress, closes, put_back, sessions = {}, {}, {}, {}, {}, [], {}
    counted = {}  # design v2 (refutation 6b-r1 P2): B4's note as counted, before the update's clauses were added
    record = {'mode': 'switch-back', 'ports': {'from': live, 'to': idle}, 'steps': steps, 'closes': closes,
              'states_put_back': put_back, 'since': since.isoformat(), 'touched_since': touched_since.isoformat()}
    reached = [None]

    def step(name):
        reached[0] = name
        steps[name] = utc_now_ms()

    def refuse_on_hazards(closed, when, checked):
        hazards = closed.get('hazards') if isinstance(closed, dict) else None
        if isinstance(hazards, dict):
            hazards = hazards_now(hazards)  # D51
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
                                          participants, name=INCOMING_WEB, port=idle, interpreter=interpreter,
                                          **({'coding': coding} if coding else {})),
               input=env_bytes, quiet=True)
        started['web'] = wait_service('web', prev_revision, prev_image, name=INCOMING_WEB, port=idle)
        record['smoke'] = smoke_web(idle, admin=serves_admin_host(prev_revision))
        step('B3')
        parked['worker'] = park('worker')
        step('B4')
        drifted = ingress_checks(ctx, preflight)
        if drifted:
            raise InstallError(baseline_problem(drifted, 'nothing was closed or switched'),
                               details={'baseline': drifted})
        checked = dt.datetime.now(dt.timezone.utc)
        hazards = hazards_now(undo_hazards(image_id, env_bytes, ctx.revision))  # D51
        if not isinstance(hazards, dict):  # D66: never read as "none"
            raise InstallError('before anything was closed, the read of what an older revision would act on wrongly gave '
                               'no answer it could be judged by', details={'hazards': hazards})
        if hazards:
            raise InstallError(f'before anything was closed, {hazard_summary(hazards)} hold records an older revision '
                               'would act on, or show, wrongly under its own rules', details={'hazards': hazards})
        refusal, disposed = disposal_refusal(image_id, env_bytes, prev_revision)  # refutation round 1, rollback-1
        if refusal:
            raise InstallError(f'before anything was closed, {refusal}', details={'disposal': disposed})
        first = dt.datetime.now(dt.timezone.utc)
        # refutation r3, D-5: the close may take effect whatever its call then answers (CLOSE_STAGES commits, then reads
        # every encounter), so the undo is told it started
        closes['first_started_at'] = first.isoformat()
        closes['first'] = close_undone_stages(image_id, env_bytes, since, ctx.revision, reason, kinds)
        refuse_on_hazards(closes['first'], 'after this revision\'s worker stopped and its stages were closed', checked)
        put_back.append(put_back_states(closes['first'], prev_image, image_id, env_bytes))
        # no worker of this revision runs from B3 on, so this is what the previous image is handed: the declared note
        # of what this revision coded that is not carried back (coding_note)
        counted['b4'] = coding_note(image_id, env_bytes, ctx.revision)
        record['not_carried_back'] = with_update_note(counted['b4'], [closes['first']])
        if ends_sessions:  # B4, before B5: the previous web reads none of this revision's cookies once it serves
            record['sessions_ended'] = sessions
            end_every_session(image_id, env_bytes, ctx.revision, prev_revision, sessions)
        step('B5')
        record['switch'] = switch_upstream(ctx, preflight, live, idle, revision=prev_revision, progress=progress,
                                           from_revision=ctx.revision)
        step('B6')
        record['drain'] = drain_web(live)
        parked['web'] = retire_live_web(plan['web']['id'])
        step('B7')
        closes['second'] = close_undone_stages(image_id, env_bytes, first, ctx.revision, reason, kinds)
        # D51 (the S17 refutation, finding 14): this revision's web served until B6's drain, so a context save there
        # could make a new-path context after B4's count; the note is read again once that web is stopped - the final
        # count of what the previous image is handed (B4's stays in the record). D59 (round 2, finding 14): read
        # before the close's refusal, which leaves the previous web serving these rows with its worker held, so the
        # receipt that stops here carries B7's count too
        record['not_carried_back_at_b4'] = record.get('not_carried_back')
        record['not_carried_back'] = with_update_note(coding_note(image_id, env_bytes, ctx.revision),
                                                    [closes['first'], closes['second']])
        refuse_on_hazards(closes['second'], 'after the switch', checked)
        put_back.append(put_back_states(closes['second'], prev_image, image_id, env_bytes))
        step('B8')
        docker('run', '-d', *service_args('worker', prev_image, prev_revision, provider_mode, authorization_ref,
                                          participants, interpreter=interpreter,
                                          **({'coding': coding} if coding else {})), input=env_bytes, quiet=True)
        started['worker'] = wait_service('worker', prev_revision, prev_image)
        step('B9')
        try:
            record['logs_kept'] = retire_parked(parked)  # A13: ids-only copies, then the removal
        except InstallError as error:
            # refutation, rollback lens B-11: the previous pair serves already - a log copy (or the removal) that fails
            # leaves this revision's parked pair in place, a recorded finding and never a failed switch-back; the next
            # app retries the copy, then removes the pair (retire_left_parked)
            record['parked_left'] = {'why': str(error) or type(error).__name__,
                                     'pair': {role: previous['id'] for role, previous in parked.items() if previous}}
        step('done')
        record['availability'] = recorder.stop()
    except BaseException as failure:
        try:
            message = undo_switch_back(ctx, failure, reached[0], image_id=image_id, env_bytes=env_bytes, plan=plan,
                                       parked=parked, progress=progress, put_back=put_back, closes=closes,
                                       prev_revision=prev_revision)
        except BaseException as second:  # noqa: BLE001 — the undo itself stopped: say so, with what is there now
            interrupted = closes.get('reapplied') if isinstance(closes.get('reapplied'), dict) else {}
            message = (f'{str(failure) or type(failure).__name__}; the undo at {reached[0]} stopped too '
                       f'({str(second) or type(second).__name__}): read "left" in this receipt, then ops/INSTALL.md, '
                       'Recovery notes'
                       # refutation w7r 6b-r1 R1: a put-back that the stop interrupted names the saves it may have left
                       + (f'. {interrupted["sentence"][:1].upper()}{interrupted["sentence"][1:]}'
                          if interrupted.get('interrupted') and interrupted.get('sentence') else ''))
        if closes.get('undone_before_switch') and 'b4' in counted:
            # refutation 6b-r1 P2: no previous web was handed the site, so B4's note was handed to none - its
            # instructions for the previous web's members are not left standing in the receipt; refutation 6b-r2 F5: one
            # that nginx may have routed to until the settle is said to have served in that window
            record['not_carried_back'] = undone_note(counted['b4'], served=closes.get('served'))
        raise InstallError(message + sessions_ended_said(sessions),
                           details={**record, 'failed_at': reached[0], 'started': started, 'replaced': parked,
                                    'availability': stop_recorder(recorder), 'left': left_summary()}) from failure
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
        # refutation 6b-r2 F3: left half way, the previous web may serve, so nothing is put back; F1: the message names
        # the encounters whose saves B4's close set back, as not put back (the recovery may keep this revision)
        first_close = [closes.get('first')] if isinstance(closes, dict) else []
        kept_back = not_put_back(first_close, 'an undo left half way puts nothing back while the earlier web may serve',
                                 where='closes.first.reverted')
        if switched_file and vhost_state()['file_sha256'] == sha256(rendered_vhosts(ctx.revision, idle)['https']
                                                                     .encode()):
            return (f'{cause}; quillmd-cpt still names the previous revision\'s web ({INCOMING_WEB}, port {idle}), '
                    + halfway + kept_back)
        touched = reached == 'B5' and nginx_may_have_read(progress)
        notes = []
        closed = closes if isinstance(closes, dict) else {}
        if touched:
            settled = settle_vhost(ctx, port=live, revision=ctx.revision, other_revision=prev_revision or '')
            if not settled['proven']:
                return (f'{cause}; the vhost was put back, but nginx may still route to the previous revision\'s web '
                        f'({INCOMING_WEB}, port {idle}): a reload of the switched vhost was asked for, or nginx loaded '
                        f'one since it was written, and nginx was not proven to run this revision\'s again '
                        f'({settled.get("problem")}), ' + halfway + kept_back)
            # refutation 6b-r2 F5 (DECISIONS D247): nginx may have routed to the previous web from the switch until
            # this settle, so the receipt's note says that web may have served in that window (undone_note's served)
            parts = _undo_parts([closed.get('first')]) if closed.get('first') is not None else None
            closed['served'] = {'from': progress['applied_at'].isoformat(),
                                'until': dt.datetime.now(dt.timezone.utc).isoformat(),
                                'update_pending': sorted(parts[0]) if parts is not None else None,
                                # refutation w7r 6b-r1 R5: A21's own (an update no save started), worded apart
                                'reconciled_unknown': sorted(pk for pk, reasons in parts[0].items()
                                                             if reasons == ['reconciled_unknown'])
                                if parts is not None else None}
            drain_web(idle)
        removed = remove_incoming_web()
        # design v2 (amendment 1, 9.4; refutation 6b-r1 P2): B4's close set the pending saves back for the previous
        # image, which now never serves - this revision's web serves on and its worker reads the update - so they are put
        # back, once the previous web is gone and before this revision's worker resumes (closes is the receipt's)
        closed['undone_before_switch'] = True
        if closed.get('first') is not None:
            try:
                closed['reapplied'] = reapplied = reapply_reverted(image_id, env_bytes, [closed['first']])
            except BaseException as error:  # noqa: BLE001 — recorded, then raised again: the undo stops
                # refutation w7r 6b-r1 R1: recorded in the receipt's closes before the interrupt stops the undo (this
                # worker is not resumed after a Ctrl-C), so the undo's message names those encounters
                closed['reapplied'] = interrupted_put_back([closed['first']], error)
                raise
            if reapplied['sentence']:
                notes.append(reapplied['sentence'])
        if put_back:  # once no previous-revision container runs (I-state), before this revision's worker resumes
            try:
                app_script(image_id, env_bytes, RECOMPUTE_STATES, {}, what='Recomputing the stored list states')
                notes.append('the list states were recomputed with this revision\'s derivation')
            except BaseException as error:  # noqa: BLE001
                notes.append(f'the list states put back to the previous revision\'s could not be recomputed ({error}): '
                             'rerun --phase app, which recomputes them')
        worker_note = restore_parked_worker(parked.get('worker'))
        if closed.get('first') is not None:
            closing = f'. As for what the close already closed: {CLOSED_STAGES_SAID}.'
        elif closed.get('first_started_at'):  # refutation r3, D-5: it was started, and may have committed
            closing = ('. The close was started and gave no answer, so it '
                       f'{possibly_set_back(closed["first_started_at"])}.')
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


# The accounts a provision names (refutation, installer lens A-4): whether each exists and whether it holds or ever
# held an operator grant - read before any password is set, so an operator account is never a practice's owner or
# agent, and its password never reaches a credentials file.
PROVISION_CHECK = '''
from studio import models
found = {}
for username in P['usernames']:
    user = models.User.objects.filter(username=username).first()
    found[username] = {'exists': user is not None,
                       'grants': models.OperatorGrant.objects.filter(user=user).count() if user is not None else 0}
print(ANSWER + json.dumps({'accounts': found}))
'''


def provision_problem(image_id, env, usernames) -> dict:
    """PROVISION_CHECK's reading of ``usernames``, refused when any holds or held an operator grant, or does not read
    back (fail closed)."""
    answer = app_script(image_id, env, PROVISION_CHECK, {'usernames': sorted(usernames)},
                        what='Reading the accounts to provision')
    found = answer.get('accounts') if isinstance(answer, dict) else None
    if not isinstance(found, dict) or sorted(found) != sorted(usernames) or not all(
            isinstance(state, dict) and type(state.get('grants')) is int for state in found.values()):
        raise InstallError('The accounts to provision did not read back; no password was set.',
                           details={'check': found})
    operators = sorted(name for name, state in found.items() if state['grants'])
    if operators:
        raise InstallError(f'{", ".join(operators)} holds or held an operator grant: an operator is never a practice\'s '
                           'owner or agent, and its password is never written to a file. No password was set.',
                           details={'check': found})
    return found


def phase_provision(ctx) -> dict:
    """A specialty's workspace, its owner and - only when --agent-username names one (release 1, A6; TEC-4 (5), ORG-20
    (5)) - a review agent. Passwords are made here and travel to the one-shot as RAM-only files; the owner's login is
    the root-only initial credentials file, an agent's (when there is one) this user's 0600 file. The owner's password is
    one staff set, so provision is given --require-password-change (B4): the owner chooses a new one at the first
    sign-in, within STAFF_PASSWORD_UNUSED_SECONDS. --by names the person who ran it (C3)."""
    args, reset = ctx.args, bool(ctx.args.reset_passwords)
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    specialty = getattr(args, 'specialty', None) or 'gastroenterology'
    final, agent_credentials = credentials_files(specialty)
    agent = getattr(args, 'agent_username', None) or None
    names = {'final': final}
    state = root_file('state', **names)
    agent_staged = agent_credentials.with_name(f'.{agent_credentials.name}.new')
    if state['staged_exists'] or agent_staged.exists():
        raise InstallError(f'Staged credentials from an interrupted run exist ({ETC_DIR}/.{final}.new or {agent_staged}); '
                           f'resolve them by hand first.')
    if not reset and (state['final_exists'] or (agent is not None and agent_credentials.exists())):
        raise InstallError(f'Credentials files already exist ({ETC_DIR}/{final}'
                           + (f', {agent_credentials}' if agent is not None else '') + '); use --reset-passwords to '
                           'rotate them - for this specialty\'s accounts only: the installer keeps one workspace per '
                           'specialty.')
    expected = {args.owner_username: ('human', 'owner')}
    if agent is not None:
        expected[agent] = ('agent', 'reviewer')
    if set(expected) & OPERATOR_NAMES:  # argument_problem refused these already; never through another path either
        raise InstallError('An operator account is never a practice\'s owner or agent; nothing was provisioned.')
    checked = provision_problem(image_id, env, list(expected))
    passwords = {user: secrets.token_urlsafe(24) for user in expected}
    accounts = [{'username': user, 'actor_kind': kind, 'role': role, 'password': passwords[user]}
                for user, (kind, role) in expected.items()]
    root_bytes = json.dumps(credentials_document(ctx, accounts), indent=2).encode()
    agent_bytes = (json.dumps(credentials_document(ctx, [item for item in accounts if item['username'] == agent]),
                              indent=2).encode() if agent is not None else None)
    if agent is not None:
        agent_credentials.parent.mkdir(mode=0o700, exist_ok=True)
        folder = agent_credentials.parent.lstat()
        if not stat.S_ISDIR(folder.st_mode) or folder.st_uid != os.getuid() or stat.S_IMODE(folder.st_mode) != 0o700:
            raise InstallError(f'{agent_credentials.parent} must be a directory owned by this user with mode 0700.')
    # Password files live in RAM only (/dev/shm: RamFiles) and are wiped whatever happens.
    ram = RamFiles('cpt-studio-provision-')
    completed, after_act = False, None
    try:
        root_file('stage', content=base64.b64encode(root_bytes).decode(), **names)
        if agent is not None:
            write_private(agent_staged.parent, agent_staged.name, agent_bytes)
        mounts = [ram.add(f'{user}.pw', passwords[user].encode(), f'/run/cpt-provision/{user}.pw') for user in expected]
        # a name is one item, '--option=value', so a name the installer accepted that starts with '-' reaches provision
        # as that name (refutation N7-1-7)
        command = ['manage', 'provision', '--specialty', specialty, f'--workspace-name={args.workspace_name}',
                   '--owner-username', args.owner_username, f'--owner-display-name={args.owner_display_name}',
                   '--owner-password-file', f'/run/cpt-provision/{args.owner_username}.pw']
        if agent is not None:
            command += ['--agent-username', agent, f'--agent-display-name={args.agent_display_name}',
                        '--agent-password-file', f'/run/cpt-provision/{agent}.pw']
        # release 1: the password is one staff set, which the owner replaces at the first sign-in (B4), and the run
        # names who ran it (C3)
        command += ['--require-password-change', f'--by={args.by}']
        if reset:
            command.append('--reset-passwords')
        hidden = [*passwords.values(), *env_values(env)]
        try:
            result = oneshot(image_id, command, env, mounts=mounts, user=f'{os.getuid()}:{os.getgid()}', by=args.by)
        except BaseException as error:  # noqa: BLE001 — refutation round 4, installer-1: a signal or a Ctrl-C that
            answered = oneshot_answer_of(error)  # reached the leftover check after the act answered keeps its record,
            if answered is None:  # as the manage acts' and the operators' grant do: the act's output is kept (every
                raise  # password and secret redacted) and named in the receipt beside the interrupt; nothing is handed
            out, out_counts = redact_output(answered.stdout, hidden)  # over (the staged credentials are discarded)
            err, err_counts = redact_output(answered.stderr, hidden)
            raise_after_act(error, {'log': ctx.log('provision', out + err), **redaction_record(out_counts, err_counts),
                                    'exit': answered.returncode, 'credentials_handed_over': False, 'by': args.by},
                            'provision')
        # refutation round 1, phileak-1's class: the act ran, so its output is kept, every password and the
        # application's secrets redacted; a password it printed is never handed over (the staged files are discarded)
        stdout, stdout_counts = redact_output(result.stdout, hidden)
        stderr, stderr_counts = redact_output(result.stderr, hidden)
        log = ctx.log('provision', stdout + stderr)
        redacted = redaction_record(stdout_counts, stderr_counts)
        printed = [user for user in expected
                   if passwords[user].encode() in result.stdout or passwords[user].encode() in result.stderr]
        if printed:
            raise InstallError(f'provision printed the password of {len(printed)} account(s) (exit '
                               f'{result.returncode}), so no password was handed over: the credentials files were '
                               f'discarded, and its output is kept in {log} with them redacted. Rerun with '
                               '--reset-passwords for new ones.', details={'log': log, **redacted,
                                                                           'exit': result.returncode})
        if result.returncode:
            raise InstallError(f'provision failed (exit {result.returncode}); see {log}.',
                               details={'log': log, **redacted})
        outcome = provision_outcome(stdout.decode('utf-8', 'replace'), expected)
        if not reset and set(outcome.values()) != {'created'}:
            raise InstallError('An account already existed, so its password was not set; nothing was saved. '
                               'Rerun with --reset-passwords to rotate.')
        root_file('commit', replace=reset, **names)
        if agent is not None:
            if reset:
                os.replace(agent_staged, agent_credentials)
            else:
                os.link(agent_staged, agent_credentials)
                agent_staged.unlink()
        completed = True
    except BaseException:
        root_file('discard', sha256=sha256(root_bytes), **names)
        agent_staged.unlink(missing_ok=True)
        raise
    finally:
        try:
            ram.__exit__(None, None, None)
        except BaseException as error:  # noqa: BLE001 — refutation round 1 (builder D's point): once the act ran and
            if not completed:  # its files were handed over, a wipe that failed or was interrupted keeps its record
                raise
            after_act = error
    record = {'accounts': outcome, 'specialty': specialty, 'root_credentials': f'{ETC_DIR}/{final}', 'checked': checked,
              'agent_credentials': str(agent_credentials) if agent is not None else None, 'log': log, **redacted,
              'exit': result.returncode, 'reset_passwords': reset, 'require_password_change': True, 'by': args.by,
              'summary': 'accounts ' + ', '.join(f'{user} {state}' for user, state in outcome.items())
                         + ('' if agent is not None else '; no review agent (opt-in: --agent-username)')
                         + redaction_summary(redacted.get('redacted'))}
    if after_act is not None:
        raise_after_act(after_act, record, 'provision')
    return record


# The operators phase's in-image scripts (run by `manage shell -c` in this revision's image, as app_script runs them).
# Release 1 (RELEASE-1-SPEC A6; TEC-4, TEC-16 (2)): the human platform operator alone, and no operator password is ever
# written to a file. OPERATOR_ACCOUNTS creates each OPERATOR_ACCOUNTS_SPEC account with NO workspace membership - an
# operator's access is the grant alone (studio.operator), never a workspace role - and an UNUSABLE password, or keeps
# it as it is; with reset (--reset-passwords) it makes the existing password unusable. Either way the operator then
# sets a password, with a single-use setup code the installer issues, on admin.quillmd.com (B2, B4). It refuses,
# changing nothing, an account that exists with another actor kind or holds any membership (a member account is never
# made an operator by the installer). No value is printed. One transaction: a refusal leaves every account as it was.
OPERATOR_ACCOUNTS = '''
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
            user.set_unusable_password()
            user.save()
        done[spec['username']] = 'created' if created else ('reset' if P['reset'] else 'kept')
print(ANSWER + json.dumps({'accounts': done}))
'''
# Read before and after the grants: each account's operator state by studio.operator.is_operator (the grant, never a
# membership), its memberships, actor kind and whether it is active, and - release 1 (A6; ADM-10 3(i)) - whether any
# grant of it was ever revoked: a revoked account stays revoked unless a run passes --regrant under a declaration that
# names that grant.
OPERATOR_CHECK = '''
from studio import models
from studio.operator import is_operator
found = {}
for username in P['usernames']:
    user = models.User.objects.get(username=username)
    found[username] = {'operator': bool(is_operator(user)), 'memberships': user.memberships.count(),
                       'actor_kind': user.actor_kind, 'active': user.is_active,
                       'revoked': models.OperatorRevocation.objects.filter(grant__user=user).exists()}
print(ANSWER + json.dumps({'accounts': found}))
'''
# The account a manage grant-operator names (refutation, installer lens A-1): whether it exists, is an operator now,
# and whether any of its grants was ever revoked - read before the act, so the door holds A6's rule as the operators
# phase does: a revoked account stays revoked unless --regrant names it and the declaration names that re-grant.
GRANT_CHECK = '''
from studio import models
from studio.operator import is_operator
user = models.User.objects.filter(username=P['username']).first()
found = {'exists': user is not None}
if user is not None:
    found.update(operator=bool(is_operator(user)),
                 revoked=models.OperatorRevocation.objects.filter(grant__user=user).exists())
print(ANSWER + json.dumps(found))
'''
# Release 1 (A6, B2): the single-use setup code an operator enrols with - generated here, handed to the application's
# command as a RAM-only file (only its sha256 reaches the database), kept root-only in OPERATOR_ENROLMENT through the
# root helper, never printed, logged or put in a receipt. ENROLMENT_CODE_SECONDS is cptstudio/settings.py's (a test pins
# the two). Today's operator password file (LEGACY_OPERATOR_CREDENTIALS) and ops-agent's login (LEGACY_AGENT_LOGIN) are
# no longer written; one left on the host stays untouched and is reported: deleting either is the owner's decision
# (D11, D12).
OPERATOR_ENROLMENT = 'operator-enrolment.json'
ENROLMENT_CODE_SECONDS = 1800
# The setup code's shape is Lane 2's (studio.second_factor.new_code(SETUP_CODE_GROUPS)), the only one its plain_code()
# reads from a --code-file: SETUP_CODE_GROUPS groups of CODE_GROUP characters of CODE_ALPHABET (no 0/o, 1/i/l), joined by
# hyphens - 25 characters of 31, about 124 bits (refutation, installer lens A-5a; a test pins the three).
CODE_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'
CODE_GROUP = 5
SETUP_CODE_GROUPS = 5


def new_setup_code() -> str:
    """A setup code in Lane 2's shape, from the operating system's random source."""
    return '-'.join(''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_GROUP)) for _ in range(SETUP_CODE_GROUPS))

LEGACY_OPERATOR_CREDENTIALS = f'{ETC_DIR}/operator-credentials.json'
LEGACY_AGENT_LOGIN = Path('/home/claude/.cpt-studio/ops-agent-credentials.json')
MANAGE_MOUNT = '/run/cpt-manage'  # where a ruled act's RAM-only reason and code files are mounted
REASON_LIMIT = 4096
# A --by name is a person, never a role (C3): the words a role would be named by are refused here too.
ROLE_WORDS = frozenset({'operator', 'operators', 'admin', 'administrator', 'root', 'installer', 'agent', 'ops-agent',
                        'system', 'owner', 'reviewer', 'viewer', 'platform-operator'})
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def operator_reason(ctx, username, kind) -> str:
    return (f'Platform-operator diagnostics access for the CPT Studio {kind} account {username} (owner directive '
            '2026-11-03, section 2: operator diagnostics stay available to authenticated platform operators and are '
            'never conferred by a workspace role). Granted by ops/install.py --phase operators for revision '
            f'{ctx.revision} under the ruled-mutation declaration {door_of(ctx)["declaration"]} '
            f'({door_of(ctx)["declaration_commit"]}).\n')


# The one line a declaration approves a re-grant with (declaration_names; ops/INSTALL.md, operators): 'Approved: ' and
# the words - in backticks or not - as the whole of a line that starts with it, outside any fenced block and any HTML
# comment. Nothing else approves: refutation round 2, installer-3 found that a list of re-grants NOT approved holds
# exactly the lines round 1 read as approval (the words alone on a line, under 'NOT approved:', in a fence, an indented
# block, a comment), and any reading of the words around such a line would be a list of refusing phrases, which the
# next wording passes. So a refusal, however its lines break, names nothing - and a declaration that also mentions the
# words anywhere else approves nothing (fail closed: it says two things of one re-grant).
REGRANT_APPROVAL_FORMS = ('Approved: {words}', 'Approved: `{words}`')
DECLARATION_FENCES = ('```', '~~~')
DECLARATION_COMMENT_RE = re.compile(r'<!--.*?(?:-->|\Z)', re.S)


def door_of(ctx) -> dict:
    """The declaration this run is bound to - main's check_door record, else (a phase called directly) the door's two
    variables."""
    door = getattr(ctx, 'door', None)
    if isinstance(door, dict) and door.get('declaration') and door.get('declaration_commit'):
        return door
    return {'declaration': os.environ.get('RULED_MUTATION_DECLARATION', ''),
            'declaration_commit': os.environ.get('RULED_MUTATION_DECL_COMMIT', '')}


def authorization_of(ctx) -> str:
    """The approval a grant rests on (C3; ADM-13): '<declaration>@<its commit>', the committed ruled-act declaration
    this run is bound to."""
    door = door_of(ctx)
    if not door['declaration'] or not SHA_RE.fullmatch(door['declaration_commit']):
        raise InstallError('A grant names its approval - the declaration this run is bound to - and none is known.')
    return f'{door["declaration"]}@{door["declaration_commit"]}'


def declaration_names(ctx, words) -> bool:
    """Whether the committed declaration this run is bound to approves ``words`` (A6: a re-grant is approved there):
    some line of it is exactly one of REGRANT_APPROVAL_FORMS (trailing white space aside) - not indented, not inside a
    fenced block or an HTML comment - and the words are mentioned nowhere else in it. A mention is the words not
    followed by a character a username may go on with, so '--regrant alice' is no mention of '--regrant ali' (refutation
    round 1, installer-0) while 'do not --regrant ali.' is one."""
    try:
        text = (ROOT / door_of(ctx)['declaration']).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    approvals = {form.format(words=words) for form in REGRANT_APPROVAL_FORMS}
    mention = re.compile(re.escape(words) + r'(?![a-z0-9_-])(?!\.[a-z0-9_.-])')
    comments = [match.span() for match in DECLARATION_COMMENT_RE.finditer(text)]
    approved, elsewhere, fenced, start = False, False, False, 0
    for line in text.split('\n'):
        fence = line.strip().startswith(DECLARATION_FENCES)
        for found in mention.finditer(line):
            at = start + found.start()
            if (line.rstrip() in approvals and not fenced and not fence
                    and not any(begin <= at < end for begin, end in comments)):
                approved = True
            else:
                elsewhere = True
        fenced = fenced != fence
        start += len(line) + 1
    return approved and not elsewhere


def person_problem(value, flag) -> str:
    """'' when ``value`` names a person (C3: --by and --approved-by name people, never a role), else the refusal."""
    if not value or not value.strip():
        return f'{flag} must name the person who runs this act.'
    if not DISPLAY_RE.fullmatch(value) or len(value) > 80:
        return f'{flag} may use letters, digits, spaces and .,\'()- only (80 at most).'
    if value.strip().casefold() in ROLE_WORDS:
        return f'{flag} names a role ({value.strip()!r}), not a person.'
    return ''


def review_by_problem(value) -> str:
    """'' when ``value`` is a review date (C3: an ISO date after today, at most 12 months away), else the refusal."""
    try:
        date = dt.date.fromisoformat(value or '')
    except ValueError:
        return '--review-by must be a date, YYYY-MM-DD.'
    today = dt.datetime.now(dt.timezone.utc).date()
    if not today < date <= today + dt.timedelta(days=366):
        return '--review-by must be after today and at most 12 months away.'
    return ''


def env_values(env: bytes) -> list:
    """The values of a protected environment file's lines (validate_env_text's form), for redact_output: the
    application's secret key and database password never reach a log or a receipt from what a one-shot printed."""
    values = []
    for line in env.decode('utf-8', 'replace').splitlines():
        name, sep, value = line.partition('=')
        if sep and value:
            values.append(value)
    return values


def read_bounded_file(given: Path, limit, flag) -> bytes:
    """A regular file's bytes, read through one descriptor that never follows a link, at most ``limit`` bytes counted
    as read - never by the size a file reports - and refused when what it holds differs from that size, as /proc's and
    /sys's files do (refutation, installer lens A-7: /proc/cpuinfo passed, reporting 0 bytes)."""
    try:
        fd = os.open(given, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise InstallError(f'{flag} cannot be read (a link, or no such file).') from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise InstallError(f'{flag} must be a regular file of at most {limit} bytes.')
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, limit + 1 - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    finally:
        os.close(fd)
    data = b''.join(chunks)
    if len(data) > limit:
        raise InstallError(f'{flag} must be a regular file of at most {limit} bytes.')
    if len(data) != info.st_size:
        raise InstallError(f'{flag} holds {len(data)} bytes but says {info.st_size}: not an ordinary file (/proc, /sys); '
                           'nothing was run.')
    return data


def reason_values(reason) -> list:
    """What of a reason no command output may echo (refutation, installer lens A-7): its whole text and each of its lines
    of 12 characters or more (a shorter line could match ordinary output by chance)."""
    if not reason:
        return []
    text = reason.decode('utf-8', 'replace').strip()
    return [text, *[line.strip() for line in text.splitlines() if len(line.strip()) >= 12]]


# A reason the redaction can never alter an id or a count with (refutation round 2, installer-5: a reason under 12
# characters - a bare ticket number, '4521' - was redacted wherever no letter or digit stood beside it, and '-' bounds
# every group of an id: it changed a group of the plan id execute needs, which the receipt then no longer showed, and hid
# a count). Every text redact_output replaces of a reason (reason_values: its whole text, and each of its lines of 12
# characters or more) is replaced wherever it stands, so each must hold a word: the whole text REASON_MIN_CHARACTERS
# characters or more that are not white space, and neither it nor any such line made of ids, links and numbers alone
# (reason_part_is_an_id). Anything else is refused before the act. Refutation round 3, installer-2: round 2 asked for
# three words and refused every line of one word, so a heading, a label, a specialty, a compound, a sign-off, a reason
# of two words and one written in a language without spaces were refused as ids; a word is never refused.
REASON_MIN_CHARACTERS = 12


def reason_part_is_an_id(part: str) -> bool:
    """Whether ``part`` - a run of a reason between white space - is an id, a link or a number, so that its redaction
    could alter one the act prints. Every id, count, digest, date, path and link the act prints is ASCII, so a part
    holding any other character (a letter of another script: a German compound, a Japanese sentence and a date in it),
    or no letter or digit at all (a line of dashes), is never one. A part written in ASCII is one when it holds a digit
    (a number, a date, an id or a digest with digits), a '/', '\\' or '@' (a link, a path, an address), or a '.', '_'
    or '=' between two letters or digits (a host, a file, a name in the code, a key and its value), or is 12 or more
    hexadecimal letters and '-' once its punctuation at either end is set aside (an id or a digest without a digit).
    Any other is a word: letters, with hyphens, apostrophes and punctuation."""
    if not part.isascii() or not re.search(r'[A-Za-z0-9]', part):
        return False
    return bool(re.search(r'[0-9/\\@]|[A-Za-z0-9][._=][A-Za-z0-9]', part)
                or re.fullmatch(r'[A-Fa-f-]{12,}', re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9]+$', '', part)))


def reason_holds_a_word(text: str) -> bool:
    """Whether one of ``text``'s parts (its runs between white space) is a word (reason_part_is_an_id)."""
    return any(not reason_part_is_an_id(part) for part in text.split())


def reason_words_problem(reason: bytes) -> str:
    """'' when ``reason`` is in words (above), else the refusal - which never repeats the reason."""
    whole, *lines = reason_values(reason)
    if len(''.join(whole.split())) < REASON_MIN_CHARACTERS or not reason_holds_a_word(whole):
        return (f'--reason-file must give the reason in words - {REASON_MIN_CHARACTERS} characters or more that are not '
                'white space, a word among them: a shorter one, or one of ids, links and numbers alone (a ticket '
                "number alone), would be redacted from the act's output wherever it stands, inside an id or a count "
                'too')
    if not all(reason_holds_a_word(line) for line in lines):
        return ('--reason-file has a line of 12 characters or more that is an id, a link or a number alone, with no '
                'word in it (a part written in ASCII that holds a digit, a /, \\ or @, or a ., _ or = between two '
                'letters or digits, or is 12 or more hexadecimal letters): each such line is redacted on its own '
                "wherever it stands in the act's output, inside an id or a count too; put a word beside it")
    return ''


def read_reason_file(path) -> bytes:
    """A ruled act's reason (A6): a regular file, never a link, of UTF-8 text, not empty, at most REASON_LIMIT bytes. Its
    bytes go to the command as a RAM-only file; the receipt keeps its sha256 and size, never its text."""
    given = Path(path or '')
    if not given.is_absolute():
        raise InstallError('--reason-file must be an absolute path.')
    data = read_bounded_file(given, REASON_LIMIT, '--reason-file')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise InstallError('--reason-file is not UTF-8 text.') from None
    if not text.strip():
        raise InstallError('--reason-file is empty.')
    problem = reason_words_problem(data)  # refutation round 2, installer-5: in words, before the act
    if problem:
        raise InstallError(f'{problem}; nothing was run.')
    return data


RAM_NAME_RE = re.compile(r'cpt-studio-[a-z]+-[0-9a-f]{32}')
SHM_MOUNT = 'type=bind,src=/dev/shm,dst=/host-shm'
# A RAM folder handed to the uid a one-shot runs as (RamFiles.give): the folder and its files chowned, their modes
# (0700, 0600) and this user's ownership checked first, nothing else touched.
H_RAM_GIVE = '''
path = '/host-shm/' + P['name']
i = os.lstat(path)
if not (stat.S_ISDIR(i.st_mode) and i.st_uid == P['from'] and stat.S_IMODE(i.st_mode) == 0o700):
    R = {'error': 'the RAM folder is not a 0700 folder of the installer user; nothing was changed'}
else:
    names, odd = sorted(os.listdir(path)), 0
    for name in names:
        f = os.lstat(os.path.join(path, name))
        if not (stat.S_ISREG(f.st_mode) and f.st_uid == P['from'] and stat.S_IMODE(f.st_mode) == 0o600):
            odd += 1
    if odd:
        R = {'error': str(odd) + ' file(s) in the RAM folder are not 0600 files of the installer user; nothing was changed'}
    else:
        for name in names:
            os.chown(os.path.join(path, name), P['uid'], P['gid'])
        os.chown(path, P['uid'], P['gid'])
        R = {'given': len(names), 'uid': P['uid']}
print(json.dumps(R))
'''
# ... and wiped and removed afterwards: each file overwritten, unlinked, then the folder (anything but a file refuses).
H_RAM_WIPE = '''
path = '/host-shm/' + P['name']
names = sorted(os.listdir(path))
if [name for name in names if not stat.S_ISREG(os.lstat(os.path.join(path, name)).st_mode)]:
    R = {'error': 'the RAM folder holds something that is not a file; nothing was removed'}
else:
    for name in names:
        full = os.path.join(path, name)
        size = os.lstat(full).st_size
        with open(full, 'r+b') as handle:
            handle.write(bytes(max(64, size)))
        os.unlink(full)
    os.rmdir(path)
    R = {'wiped': len(names)}
print(json.dumps(R))
'''


class RamFiles:
    """A RAM-only folder under /dev/shm for a ruled act's files, wiped and removed whatever happens (a SIGTERM too:
    Interrupted). The folder is 0700 and every file 0600, under an unguessable name (32 random hex characters); a
    one-shot that runs as another uid (``owner``, the application's: a disposal or an export) gets the folder handed to
    it by the root helper (give), modes kept, so no other local user can read a reason while the act runs (refutation,
    installer lens A-3c), and the root helper wipes it afterwards."""

    def __init__(self, prefix, *, owner=None):
        name = f'{prefix}{secrets.token_hex(16)}'
        if not RAM_NAME_RE.fullmatch(name):
            raise InstallError(f'A RAM folder prefix {prefix!r} is not cpt-studio-<word>-.')
        self.path = Path('/dev/shm') / name
        os.mkdir(self.path, 0o700)
        os.chmod(self.path, 0o700)
        self.owner, self.given = owner, False

    def add(self, name, data: bytes, destination) -> str:
        if self.given:
            raise InstallError('A RAM folder already handed to the one-shot takes no more files.')
        written = write_private(self.path, name, data)
        return f'type=bind,src={written},dst={destination},readonly'

    def give(self):
        """The folder and its files handed to ``owner`` (uid, gid) by the root helper, for a one-shot of that uid."""
        if self.owner is None or self.given:
            return None
        self.given = True  # from here on only the root helper can wipe it, whatever give answers
        return run_helper(H_RAM_GIVE, {'name': self.path.name, 'uid': self.owner[0], 'gid': self.owner[1],
                                       'from': os.getuid()}, mounts=[SHM_MOUNT])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        # refutation round 1, installer-3: a SIGTERM, SIGHUP or Ctrl-C that lands while the folder is wiped is acted on
        # once the wipe has finished (signals_deferred), never in the middle of it, which left the reason in /dev/shm.
        # Round 2, installer-4: that holds the signal in this process only, and the door's ceiling (`timeout`, which
        # signals the whole process group) also reached the docker CLI running the wipe, which died before the wipe
        # began: so that CLI runs in a session of its own (own_session), which a signal to the group never reaches
        with signals_deferred():
            if self.given:
                run_helper(H_RAM_WIPE, {'name': self.path.name}, mounts=[SHM_MOUNT], own_session=True)
                return False
            for path in self.path.iterdir():
                path.write_bytes(b'\0' * max(64, path.stat().st_size))
                path.unlink()
            self.path.rmdir()
        return False


def issue_setup_code(ctx, image_id, env, username, *, command, by, reason, extra=()) -> dict:
    """A6/B2: a single-use setup code for ``username`` - generated here; passed to the application's ``command``
    (issue_enrolment, or reset_second_factor, which issues a new one) as a RAM-only --code-file so that only its sha256
    reaches the database; committed root-only to /etc/cpt-studio/OPERATOR_ENROLMENT through the root helper (staged
    first, discarded if the command fails). The code never appears in an argument, the output kept, a log or a
    receipt: the output is kept with it, the application's secrets and the reason redacted (redact_output; refutation
    round 1, phileak-1's class: the act ran, so its record is kept), and a command that printed the code fails with
    that record and no code kept. {'command', 'exit', 'log', 'file', 'valid_seconds'}."""
    code = new_setup_code()
    document = json.dumps({'service': 'cpt-studio', 'url': f'https://{ADMIN_HOST}/login/enrol', 'username': username,
                           'code': code, 'issued_at': utc_now(), 'valid_seconds': ENROLMENT_CODE_SECONDS,
                           'revision': ctx.revision, 'synthetic_only': True}, indent=2).encode()
    names = {'final': OPERATOR_ENROLMENT, 'staged': f'.{OPERATOR_ENROLMENT}.new'}
    if root_file('state', **names)['staged_exists']:
        raise InstallError(f'A staged {OPERATOR_ENROLMENT} from an interrupted run exists; resolve it by hand first.')
    root_file('stage', content=base64.b64encode(document).decode(), **names)
    committed, result, after_act = False, None, None
    try:
        try:
            with RamFiles('cpt-studio-manage-') as ram:
                mounts = [ram.add('code', code.encode(), f'{MANAGE_MOUNT}/code'),
                          ram.add('reason', reason, f'{MANAGE_MOUNT}/reason')]
                argv = ['manage', command, '--username', username, '--code-file', f'{MANAGE_MOUNT}/code',
                        '--reason-file', f'{MANAGE_MOUNT}/reason', '--by', by, *extra]
                result = oneshot(image_id, argv, env, mounts=mounts, user=f'{os.getuid()}:{os.getgid()}',
                                 timeout=act_timeout(600), what=f'manage {command}', by=by)
        except BaseException as error:  # noqa: BLE001 — refutation round 1 (builder D's point): once the act ran, a
            if result is None:  # wipe that failed or was interrupted keeps its record; the code is never kept
                result = oneshot_answer_of(error)  # (round 3: so does a leftover check a signal reached)
            if result is None:
                raise
            after_act = error
        hidden = [code, *env_values(env)]
        stdout, stdout_counts = redact_output(result.stdout, hidden, reason_values(reason))
        stderr, stderr_counts = redact_output(result.stderr, hidden, reason_values(reason))
        printed_code = code.encode() in result.stdout or code.encode() in result.stderr
        log = ctx.log(command.replace('_', '-'), stdout + stderr)
        record = {'command': command, 'exit': result.returncode, 'log': log,
                  **redaction_record(stdout_counts, stderr_counts), **kept_stdout(stdout)}
        if after_act is not None:  # its RAM folder (which holds the code) was not wiped: the code is not kept
            raise_after_act(after_act, {**record, 'setup_code_kept': False}, f'manage {command}')
        if printed_code:
            raise InstallError(f'manage {command} printed the setup code (exit {result.returncode}), so no setup code '
                               f'was kept: the act ran, and its output is kept in {log} with the code redacted. Run '
                               'it again for a new code.', details=record)
        if result.returncode:
            raise InstallError(f'manage {command} failed (exit {result.returncode}); see {log}. No setup code was '
                               'kept.', details=record)
        root_file('commit', replace=True, **names)
        committed = True
    finally:
        if not committed:
            root_file('discard', sha256=sha256(document), **names)
    return {**record, 'file': f'{ETC_DIR}/{OPERATOR_ENROLMENT}', 'valid_seconds': ENROLMENT_CODE_SECONDS}


def legacy_operator_files() -> dict:
    """D11, D12: the operator password file and ops-agent's login today's installer wrote - left untouched (deleting a
    credential is the owner's decision) and reported: {'path': 'present' | 'absent' | 'not read'}."""
    found = {}
    try:
        stat_answer = helper_stat([LEGACY_OPERATOR_CREDENTIALS])
        entry = stat_answer.get(LEGACY_OPERATOR_CREDENTIALS) if isinstance(stat_answer, dict) else None
        found[LEGACY_OPERATOR_CREDENTIALS] = ('not read' if not isinstance(entry, dict)
                                             else 'present' if entry.get('exists') else 'absent')
    except InstallError:
        found[LEGACY_OPERATOR_CREDENTIALS] = 'not read'
    found[str(LEGACY_AGENT_LOGIN)] = 'present' if os.path.lexists(LEGACY_AGENT_LOGIN) else 'absent'
    return found


def phase_operators(ctx) -> dict:
    """The human platform operator (ops/INSTALL.md, operators; release 1, A6): OPERATOR_ACCOUNTS_SPEC holds no
    automated account, and no operator password is written to a file. The account is created with no workspace
    membership and an unusable password - or kept as it is; --reset-passwords makes its password unusable - and is then
    granted by the application's own command, `manage grant_operator` with --by (a person), --review-by and the
    declaration as its --authorization-ref (C3), when it is not an operator already. An account any of whose grants was
    revoked is never granted again unless the run passes --regrant <username> and the declaration names that re-grant.
    It is read back (OPERATOR_CHECK): an active human operator with no membership. An account created or reset then gets
    a single-use setup code (issue_setup_code): the operator sets a password and enrols a security key with it on
    admin.quillmd.com (B2, B4)."""
    args = ctx.args
    reset, regrant = bool(getattr(args, 'reset_passwords', None)), getattr(args, 'regrant', None)
    by, review_by = getattr(args, 'by', None), getattr(args, 'review_by', None)
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    # Refutation r2, L6-2: the operator grant is this revision's table (migration 0010), so the phase refuses -
    # creating no account - until the app phase has applied this revision's migrations.
    pending = oneshot(image_id, ['manage', 'migrate', '--check'], env, timeout=120)
    if pending.returncode:
        raise InstallError(f'This revision\'s migrations are not all applied (manage migrate --check exited '
                           f'{pending.returncode}): run --phase app first. No account was created.')
    spec = {username: (kind, display) for username, kind, display in OPERATOR_ACCOUNTS_SPEC}
    if regrant is not None and regrant not in spec:
        raise InstallError(f'--regrant names {regrant!r}, which is not an operator account of this installer.')
    answer = app_script(image_id, env, OPERATOR_ACCOUNTS, {'reset': reset, 'accounts': [
        {'username': username, 'kind': kind, 'display_name': display} for username, (kind, display) in spec.items()]},
        what='Creating the operator accounts')
    outcome = answer.get('accounts') if isinstance(answer, dict) else None
    if not isinstance(outcome, dict) or sorted(outcome) != sorted(spec):
        raise InstallError('The operator accounts script did not name every account.', details={'answer': answer})
    before = app_script(image_id, env, OPERATOR_CHECK, {'usernames': sorted(spec)}, what='Reading the operator accounts')
    before = before.get('accounts') if isinstance(before, dict) else None
    if not isinstance(before, dict) or sorted(before) != sorted(spec):
        raise InstallError('The operator accounts did not read back.', details={'accounts': outcome, 'check': before})
    grants = {}
    for username, (kind, _) in spec.items():
        if before[username].get('operator') is True:
            grants[username] = 'already an operator'
            continue
        if before[username].get('revoked') is not False:
            # revoked stays revoked (A6; ADM-10 3(i)), and an answer that does not say is never read as "not revoked"
            if regrant != username or not declaration_names(ctx, f'--regrant {username}'):
                raise InstallError(f'{username} was revoked as an operator, and a revoked grant stays revoked: '
                                   f'nothing was granted. To grant it again, run with --regrant {username} under a '
                                   f'committed declaration with the line "Approved: --regrant {username}", which '
                                   'names it nowhere else.',
                                   details={'accounts': outcome, 'check': before})
        problem = person_problem(by, '--by') or review_by_problem(review_by)
        if problem:
            raise InstallError(f'Granting {username} needs --by (the person running it) and --review-by (C3): '
                               f'{problem} Nothing was granted.', details={'accounts': outcome})
        result, after_act = None, None
        try:
            with RamFiles('cpt-studio-operators-') as ram:
                mount = ram.add(f'{username}.reason', operator_reason(ctx, username, kind).encode(),
                                f'{MANAGE_MOUNT}/{username}.reason')
                # a re-grant the run and its declaration approved (above) is said to the command, which refuses a
                # revoked account without it (Lane 3's grant)
                again = ['--regrant'] if before[username].get('revoked') is not False else []
                result = oneshot(image_id, ['manage', 'grant_operator', '--username', username, '--reason-file',
                                            f'{MANAGE_MOUNT}/{username}.reason', '--by', by, '--authorization-ref',
                                            authorization_of(ctx), '--review-by', review_by, *again], env,
                                 user=f'{os.getuid()}:{os.getgid()}', mounts=[mount], what='manage grant_operator',
                                 by=by)
        except BaseException as error:  # noqa: BLE001 — refutation round 1 (builder D's point): once the grant ran, a
            if result is None:  # wipe that failed or was interrupted keeps its record
                result = oneshot_answer_of(error)  # (round 3: so does a leftover check a signal reached)
            if result is None:
                raise
            after_act = error
        # refutation round 1, phileak-1's class: the grant ran, so its record is kept, the application's secrets redacted
        stdout, stdout_counts = redact_output(result.stdout, env_values(env))
        stderr, stderr_counts = redact_output(result.stderr, env_values(env))
        grants[username] = {'exit': result.returncode, 'log': ctx.log(f'grant-{username}', stdout + stderr),
                            **redaction_record(stdout_counts, stderr_counts)}
        if after_act is not None:
            raise_after_act(after_act, {'accounts': outcome, 'grants': grants, 'exit': result.returncode,
                                        'log': grants[username]['log']}, f'manage grant_operator for {username}')
        if result.returncode:
            raise InstallError(f'manage grant_operator failed for {username} (see the log); the account is in place: '
                               'rerun --phase operators once it is fixed.', details={'accounts': outcome,
                                                                                    'grants': grants})
    check = app_script(image_id, env, OPERATOR_CHECK, {'usernames': sorted(spec)}, what='Reading the operator accounts')
    found = check.get('accounts') if isinstance(check, dict) else None
    problems = [username for username, (kind, _) in spec.items()
                if not isinstance(found, dict) or not isinstance(found.get(username), dict)
                or found[username].get('operator') is not True or found[username].get('memberships') != 0
                or found[username].get('actor_kind') != kind or found[username].get('active') is not True]
    if problems:
        raise InstallError(f'{", ".join(problems)} did not read back as an active operator with no membership.',
                           details={'accounts': outcome, 'grants': grants, 'check': found})
    codes = {}
    for username, state in outcome.items():
        if state in ('created', 'reset'):
            problem = person_problem(by, '--by')
            if problem:
                raise InstallError(f'{username} has no usable password until its setup code is issued, which names who '
                                   f'issued it: {problem} Run --phase manage --command issue-enrolment.',
                                   details={'accounts': outcome, 'grants': grants})
            codes[username] = issue_setup_code(
                ctx, image_id, env, username, command='issue_enrolment', by=by,
                reason=f'The setup code of {username}, {state} by ops/install.py --phase operators (A6).\n'.encode())
    return {'accounts': outcome, 'grants': grants, 'check': found, 'reset_passwords': reset, 'setup_codes': codes,
            'legacy_files': legacy_operator_files(),
            'summary': 'operator accounts ' + ', '.join(f'{username} {state}' for username, state in outcome.items())
                       + '; read back as operators with no membership; no password written to a file'
                       + (f'; setup code kept root-only for {", ".join(codes)}' if codes else '')}


# --- the manage phase: one allow-listed ruled act (release 1, A6) ----------------------------------------------------
# Each runs one management command in a one-shot of the installed image, through the ruled-mutation door, with its reason
# (and the setup code an enrolment or a second-factor reset issues) as RAM-only files under /dev/shm. The commands are
# the application's (Lanes 2, 3 and 4 of release 1); this table is the installer's half of their contract: the
# arguments each takes from the operator, and the command line each is given. Nothing else runs.
MANAGE_COMMANDS = {
    'revoke-operator': {'command': 'revoke_operator', 'needs': ('username', 'reason_file', 'by')},
    'grant-operator': {'command': 'grant_operator', 'needs': ('username', 'reason_file', 'by', 'review_by')},
    'issue-enrolment': {'command': 'issue_enrolment', 'needs': ('username', 'reason_file', 'by'), 'code': True},
    'reset-second-factor': {'command': 'reset_second_factor', 'needs': ('username', 'reason_file', 'by'), 'code': True},
    # B1: one username's delay and pair refusals (--username), or one network's refusal (--address: an IPv4 address,
    # or an IPv6 address or /64), never both (manage_problem)
    'clear-signin-failures': {'command': 'clear_signin_failures', 'needs': ('reason_file', 'by')},
    'require-password-change': {'command': 'require_password_change', 'needs': ('reason_file', 'by')},
    'dispose': {'command': 'dispose', 'needs': ('dispose_step', 'by'), 'files': True},
    'export-workspace': {'command': 'export_workspace', 'needs': ('workspace_id', 'reason_file', 'by'), 'files': True},
}
MANAGE_ARGUMENTS = ('command', 'username', 'reason_file', 'by', 'review_by', 'approved_by', 'workspace_id',
                    'encounter_id', 'dispose_step', 'plan_id', 'all_human_accounts', 'ledger_file', 'execute')
# dispose's steps (Lane 4's command, D1): close the practice, plan (a dry run), execute a plan (run by one named person and
# approved by another), print the ledger (the MAC-signed list of disposals, keyed by the application's SECRET_KEY), and
# replay a ledger after a database restore, so destroyed data stays destroyed
DISPOSE_STEPS = ('close', 'plan', 'execute', 'ledger', 'replay-ledger')
# The steps whose command reads a reason (studio/management/commands/dispose.py reads --reason-file at --close and
# --plan, and refuses either without one; --execute carries out the plan with the plan's own reason, and --ledger and
# --replay-ledger read none): each requires --reason-file, and every other step refuses it (refutation round 1, builder
# D's point on installer-1's rule: execute and replay-ledger required a file their command never read).
DISPOSE_REASON_REQUIRED = ('close', 'plan')
# What each dispose step passes to the command (manage_argv) beyond --command, --dispose-step and --by - and so the only
# arguments it takes: any other is refused before anything runs, so what was typed is what ran (refutation round 1,
# installer-1: execute took --workspace-id and --encounter-id, then dropped them from the command line).
DISPOSE_STEP_ARGUMENTS = {
    'close': ('workspace_id', 'reason_file'),
    'plan': ('workspace_id', 'encounter_id', 'reason_file'),
    'execute': ('plan_id', 'approved_by'),
    'ledger': (),
    'replay-ledger': ('ledger_file', 'execute', 'approved_by'),
}
DISPOSE_ARGUMENTS = ('workspace_id', 'encounter_id', 'plan_id', 'approved_by', 'reason_file', 'ledger_file', 'execute')
# A ledger's one limit (refutation round 2, installer-0: the replay refused, at 1 MiB, the ledger the ledger step had kept
# "whole"): what --dispose-step replay-ledger reads (read_ledger_file) and so what --dispose-step ledger keeps as a ledger
# (ledger_problem) - one name, read by both. It is sized for the largest practice this release serves: at the owner's
# figure (1,000 practices at 50 uploads a day) a practice reaches 18,250 documents in a year, and its whole-practice
# disposal adds about 209 bytes of ledger a document with one file, 92 more for each further file, and about 5 KB
# (round 2's measurement): about 3.8 MB for that year at one file a document, 8.9 MB at four. 16 MiB holds that with
# room - four such one-file practice-years in one ledger. Where the ledger travels none is smaller: the ledger step's
# one-shot prints it whole (its stdout read whole), its log is written whole, its receipt keeps STDOUT_KEPT characters
# and its sha256, size and lines; a replay hands it over in the RAM folder (/dev/shm: a tmpfs of half the host's
# memory, 16 GiB here) to a one-shot of 768 MiB, whose reading of a 16 MiB ledger (the text, its lines, each line's JSON
# and MAC: studio.disposal.read_ledger) peaks under 90 MiB (measured, repair round 2).
LEDGER_LIMIT = 16 * 1024 * 1024
# D2: a practice's export is written into a NEW folder of its own under EXPORTS_DIR on the host (root 0700), which the
# one-shot writes as the application's user; afterwards the root helper makes everything in it root-only. [TO CONFIRM
# the path on this host.]
EXPORTS_DIR = '/var/lib/cpt-studio-exports'
EXPORT_MOUNT = '/run/cpt-export'
STDOUT_KEPT = 16000  # characters of an act's stdout a receipt keeps (ids and counts only; the log keeps all of it)


def kept_stdout(stdout: bytes) -> dict:
    """What a receipt keeps of an act's stdout: its last STDOUT_KEPT characters, how many it had, and whether it was cut
    (refutation round 1, dataloss-1: a cut copy carried no mark of the cut)."""
    text = stdout.decode('utf-8', 'replace')
    return {'stdout': text[-STDOUT_KEPT:], 'stdout_chars': len(text), 'stdout_cut': len(text) > STDOUT_KEPT}


def manage_problem(args) -> str:
    """'' when the manage phase's arguments make one allow-listed act, else the refusal (argument_problem)."""
    entry = MANAGE_COMMANDS.get(args.command or '')
    if entry is None:
        return f'--phase manage needs --command, one of {", ".join(MANAGE_COMMANDS)}.'
    for name in entry['needs']:
        if getattr(args, name, None) in (None, ''):
            return f'--command {args.command} needs --{name.replace("_", "-")}.'
    for name in ('username', 'address', 'workspace_id', 'encounter_id', 'plan_id', 'review_by', 'approved_by',
                 'dispose_step', 'all_human_accounts', 'reason_file', 'ledger_file', 'regrant', 'execute'):
        value = getattr(args, name, None)
        if value not in (None, '') and name not in entry['needs'] and not allowed_extra(args.command, name):
            return f'--{name.replace("_", "-")} is not used by --command {args.command}.'
    if args.username is not None and not USERNAME_RE.fullmatch(args.username):
        return f'--username must match {USERNAME_RE.pattern}.'
    if getattr(args, 'regrant', None) is not None and args.regrant != args.username:
        return '--regrant names the account --command grant-operator grants (--username).'
    for name in ('workspace_id', 'encounter_id', 'plan_id'):
        value = getattr(args, name, None)
        if value is not None and not UUID_RE.fullmatch(value):
            return f'--{name.replace("_", "-")} must be a lowercase UUID.'
    for name in ('by', 'approved_by'):
        if getattr(args, name, None) is not None:
            problem = person_problem(getattr(args, name), f'--{name.replace("_", "-")}')
            if problem:
                return problem
    if args.review_by is not None:
        problem = review_by_problem(args.review_by)
        if problem:
            return problem
    for name in ('reason_file', 'ledger_file'):
        if getattr(args, name, None) is not None and not Path(getattr(args, name)).is_absolute():
            return f'--{name.replace("_", "-")} must be an absolute path.'
    if args.command == 'clear-signin-failures':
        if bool(args.username) == bool(getattr(args, 'address', None)):
            return '--command clear-signin-failures needs --username or --address (B1), not both.'
        if getattr(args, 'address', None) is not None and address_problem(args.address):
            return address_problem(args.address)
    if args.command == 'require-password-change' and bool(args.username) == bool(args.all_human_accounts):
        return '--command require-password-change needs --username or --all-human-accounts (D22), not both.'
    if args.command == 'dispose':
        step = args.dispose_step
        if step not in DISPOSE_STEPS:
            return f'--dispose-step must be one of {", ".join(DISPOSE_STEPS)}.'
        if step in DISPOSE_REASON_REQUIRED and not args.reason_file:
            return f'--dispose-step {step} needs --reason-file.'
        if step in ('close', 'plan') and not (args.workspace_id or (step == 'plan' and args.encounter_id)):
            return f'--dispose-step {step} needs --workspace-id' + (' or --encounter-id.' if step == 'plan' else '.')
        if step == 'close' and args.encounter_id:
            return '--dispose-step close closes a whole practice: --encounter-id is not used.'
        if step == 'plan' and args.workspace_id and args.encounter_id:  # the command refuses both, so does this
            return ('--dispose-step plan takes --workspace-id (a whole practice) or --encounter-id (one document), not '
                    'both.')
        if args.execute and step != 'replay-ledger':
            return ('--execute belongs to --dispose-step replay-ledger (a replay is a dry run without it); '
                    '--dispose-step execute carries out a plan.')
        if step == 'execute' or (step == 'replay-ledger' and args.execute):
            # a disposal and a replay that destroys data again are both carried out by two different named people
            if not args.approved_by or (step == 'execute' and not args.plan_id):
                return (f'--dispose-step {step}' + (' --execute' if step == 'replay-ledger' else '') + ' needs '
                        + ('--plan-id and ' if step == 'execute' else '') + '--approved-by.')
            if args.approved_by.strip().casefold() == (args.by or '').strip().casefold():
                return ('The person who approves a disposal is not the one who runs it (D14): --by and --approved-by '
                        'differ.')
            if step == 'replay-ledger' and args.plan_id:
                return '--plan-id belongs to --dispose-step execute.'
        elif args.plan_id or args.approved_by:
            return ('--plan-id and --approved-by belong to --dispose-step execute; --approved-by also to '
                    'replay-ledger --execute.')
        if (step == 'replay-ledger') != bool(args.ledger_file):
            return '--ledger-file is the ledger --dispose-step replay-ledger replays, and only it takes one.'
        if step in ('ledger', 'replay-ledger') and (args.workspace_id or args.encounter_id):
            return f'--dispose-step {step} reads the whole ledger: no --workspace-id or --encounter-id.'
        unused = [name for name in DISPOSE_ARGUMENTS
                  if getattr(args, name, None) not in (None, '') and name not in DISPOSE_STEP_ARGUMENTS[step]]
        if unused:
            return (f'--{unused[0].replace("_", "-")} is not used by --dispose-step {step}, which takes '
                    + ', '.join(f'--{name.replace("_", "-")}' for name in ('by', *DISPOSE_STEP_ARGUMENTS[step]))
                    + ': nothing was run.')
    return ''


def allowed_extra(command, name) -> bool:
    """The arguments a command takes beyond those it needs (MANAGE_COMMANDS 'needs')."""
    return {('require-password-change', 'username'), ('require-password-change', 'all_human_accounts'),
            ('dispose', 'workspace_id'), ('dispose', 'encounter_id'), ('dispose', 'plan_id'),
            ('dispose', 'approved_by'), ('dispose', 'reason_file'), ('dispose', 'ledger_file'),
            ('grant-operator', 'regrant'), ('dispose', 'execute'), ('clear-signin-failures', 'username'),
            ('clear-signin-failures', 'address')}.__contains__((command, name))


def address_problem(text) -> str:
    """'' when ``text`` is what clear_signin_failures --address takes - an IPv4 address, or an IPv6 address or /64 - in
    its canonical spelling, else the refusal."""
    refusal = ('--address must be an IPv4 address, or an IPv6 address or /64, written canonically (for example '
               '203.0.113.7 or 2001:db8:1:2::/64).')
    try:
        if '/' in text:
            network = ipaddress.ip_network(text)  # strict: a prefix with host bits set is refused
            return '' if network.version == 6 and network.prefixlen == 64 and str(network) == text else refusal
        return '' if str(ipaddress.ip_address(text)) == text else refusal
    except ValueError:
        return refusal


# What a manage act leaves for after its one-shot (refutation, installer lens A-3b): the one-shot's removal, the RAM
# files' wipe, an export's seal, the receipt and the journal's flush - so the act's own timeout ends well before the
# door's ceiling (RULED_ACT_MAX_SECS), whose kill would otherwise land first and skip them.
MANAGE_CLEANUP_SECONDS = 300
MANAGE_MIN_ACT_SECONDS = 60


def act_timeout(default) -> int:
    """A manage act's one-shot timeout: ``default``, or less when the door's ceiling leaves less after
    MANAGE_CLEANUP_SECONDS; refused when that leaves under MANAGE_MIN_ACT_SECONDS."""
    budget = door_ceiling(os.environ) - MANAGE_CLEANUP_SECONDS
    if budget < MANAGE_MIN_ACT_SECONDS:
        raise InstallError(f'The door\'s ceiling ({door_ceiling(os.environ)} s, RULED_ACT_MAX_SECS) leaves the act less '
                           f'than {MANAGE_MIN_ACT_SECONDS} s after {MANAGE_CLEANUP_SECONDS} s for its cleanup and '
                           'receipt; nothing was run. Raise RULED_ACT_MAX_SECS.')
    return min(default, budget)


def export_name(args) -> str:
    """The export's folder name, <workspace>-<UTC>: made once per run (the host folder and Lane 4's --out subfolder
    inside it share it)."""
    if getattr(args, '_export_name', None) is None:
        args._export_name = f'{args.workspace_id}-{stamp()}'
    return args._export_name


DECISION_NEEDED = "needs a person's decision"
# Lane 4's contract: `dispose --replay-ledger ... --execute` exits DISPOSE_DECISION_EXIT when an entry needs a person's
# decision (its commit's outcome was unknown) and nothing else failed; any other non-zero exit is a failure.
DISPOSE_DECISION_EXIT = 3


def dispose_mode(args) -> str:
    """What a dispose step did, for its receipt (refutation, installer lens A-5b): a plan and a replay without
    --execute are dry runs that change nothing - never read as done."""
    step = args.dispose_step
    if step == 'plan' or (step == 'replay-ledger' and not args.execute):
        return 'dry run'
    return 'read' if step == 'ledger' else 'executed'


def install_in_progress() -> list:
    """The containers an install or switch-back leaves while it runs (switch_problems' names): their presence refuses a
    disposal (D1; INSTALL.md: the installer assumes no row is ever deleted)."""
    return [name for name in (INCOMING_WEB, SERVICES['web'] + '-previous', SERVICES['worker'] + '-previous')
            if inspect('container', name) is not None]


def serving_disposal_problem(*, replay=False) -> str:
    """'' when the pair under the canonical names - the one that serves, or serves once started: cpt-studio-web and
    cpt-studio-worker, running or stopped - has release 1's disposal, else why not (refutation round 2, switchback-0: a
    switch-back to a revision without disposal, refused once anything is closed or destroyed, was passed by switching
    back first and then closing and destroying while that revision served). Read as the switch-back's refusal reads a
    revision (has_disposal: its tree's DISPOSAL_FILES). No web there, a container that is not this installer's, or one
    with no revision label is not known, and never read as one with disposal (fail closed) - except, for ``replay``
    (replay-ledger --execute alone), no pair at all: docker answers that neither container exists (inspect's None; an
    answer it cannot read raises, and refuses), so nothing serves, and the ledger is replayed before a pair is started
    (refutation round 3, installer-0: a restore onto a fresh host could not replay before `app` started its worker,
    whose beat the replay itself refuses)."""
    revisions = {}
    for role in ('web', 'worker'):
        container = inspect('container', SERVICES[role])
        if container is None:
            continue
        if not owned(container, role):
            return f'{SERVICES[role]} is not a CPT Studio {role} container, so what serves is not known'
        revision = labels_of(container).get(REVISION_LABEL)
        if not SHA_RE.fullmatch(str(revision or '')):
            return f'{SERVICES[role]} carries no revision label, so what serves is not known'
        revisions[role] = revision
    if replay and not revisions:
        return ''
    if 'web' not in revisions:
        return f'there is no {SERVICES["web"]}, so the revision that serves next is not known'
    for role, revision in revisions.items():
        if not has_disposal(revision):
            return (f'{SERVICES[role]} is revision {revision[:12]}, which has no disposal (its tree has no '
                    f'{DISPOSAL_FILES[0]}): it takes uploads into a closed practice and sends them for coding, and lists '
                    'each destroyed document again')
    return ''


def manage_argv(ctx, args, entry) -> list:
    """The command line of the act (the installer's half of each command's contract; RAM-only files at MANAGE_MOUNT)."""
    command, reason = ['manage', entry['command']], ['--reason-file', f'{MANAGE_MOUNT}/reason']
    if args.command == 'revoke-operator':
        return [*command, '--username', args.username, *reason, '--by', args.by]
    if args.command == 'clear-signin-failures':
        who = ['--username', args.username] if args.username else ['--address', args.address]
        return [*command, *who, *reason, '--by', args.by]
    if args.command == 'grant-operator':
        return [*command, '--username', args.username, *reason, '--by', args.by, '--authorization-ref',
                authorization_of(ctx), '--review-by', args.review_by,
                *(['--regrant'] if getattr(args, 'regrant', None) else [])]
    if args.command == 'require-password-change':
        # Lane 2's command names every human account --all (the installer's own flag stays --all-human-accounts)
        who = ['--username', args.username] if args.username else ['--all']
        return [*command, *who, *reason, '--by', args.by]
    if args.command == 'export-workspace':
        # Lane 4's export_workspace writes into a folder it makes itself: a NEW subfolder of the mounted export
        # folder, never the mount point (which it refuses)
        return [*command, '--workspace', args.workspace_id, '--out', f'{EXPORT_MOUNT}/{export_name(args)}', *reason,
                '--by', args.by, '--authorization-ref', authorization_of(ctx)]
    if args.command == 'dispose':
        step, authority = args.dispose_step, ['--authorization-ref', authorization_of(ctx)]
        given = reason if args.reason_file else []
        if step == 'close':
            return [*command, '--close', '--workspace', args.workspace_id, *given, '--by', args.by, *authority]
        if step == 'plan':
            scope = (['--workspace', args.workspace_id] if args.workspace_id else []) + (
                ['--encounter', args.encounter_id] if args.encounter_id else [])
            return [*command, '--plan', *scope, *given, '--by', args.by, *authority]
        # execute, ledger and replay-ledger read no reason (DISPOSE_REASON_REQUIRED), so none is passed to them
        if step == 'execute':
            return [*command, '--execute', '--plan', args.plan_id, '--by', args.by, '--approved-by', args.approved_by,
                    *authority]
        if step == 'ledger':
            return [*command, '--ledger', '--by', args.by, *authority]
        # without --execute Lane 4's replay is a dry run; with it, two named people carry it out
        execute = ['--execute', '--approved-by', args.approved_by] if args.execute else []
        return [*command, '--replay-ledger', f'{MANAGE_MOUNT}/ledger', *execute, '--by', args.by, *authority]
    raise InstallError(f'--command {args.command} has no command line here.')


# D2: a practice's export folder - made new (never reused) under EXPORTS_DIR, root 0700, the folder itself the
# application's user's for the one-shot to write; then, export done or not, everything in it made root-only (folders
# 0700, files 0600) and counted - never named in a receipt. A link or anything but a folder or a regular file in it
# refuses, and nothing is changed.
H_EXPORT_DIR = '''
base = '/host-var-lib/' + P['dir']
try:
    i = os.lstat(base)
except FileNotFoundError:
    os.mkdir(base, 0o700)
    os.chown(base, 0, 0)
    os.chmod(base, 0o700)
    i = os.lstat(base)
if not (stat.S_ISDIR(i.st_mode) and i.st_uid == 0 and i.st_gid == 0 and stat.S_IMODE(i.st_mode) == 0o700):
    R = {'error': '/var/lib/' + P['dir'] + ' is not a root-owned 0700 directory'}
else:
    path = os.path.join(base, P['name'])
    os.mkdir(path, 0o700)
    os.chown(path, P['uid'], P['uid'])
    os.chmod(path, 0o700)
    R = {'made': P['name']}
print(json.dumps(R))
'''
H_SEAL_EXPORT = '''
path = os.path.join('/host-var-lib/' + P['dir'], P['name'])
entries, odd = [], 0
for top, folders, names in os.walk(path):
    entries.append((top, True))
    for name in folders + names:
        full = os.path.join(top, name)
        mode = os.lstat(full).st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            odd += 1
        elif stat.S_ISREG(mode):
            entries.append((full, False))
if odd:
    R = {'error': str(odd) + ' entr' + ('y is' if odd == 1 else 'ies are') + ' neither a folder nor a regular file; nothing was changed'}
else:
    size = 0
    for full, folder in entries:
        os.chown(full, 0, 0)
        os.chmod(full, 0o700 if folder else 0o600)
        size += 0 if folder else os.lstat(full).st_size
    R = {'sealed': P['name'], 'folders': sum(1 for _, folder in entries if folder),
         'files': sum(1 for _, folder in entries if not folder), 'bytes': size}
print(json.dumps(R))
'''
EXPORTS_MOUNT = 'type=bind,src=/var/lib,dst=/host-var-lib'


def ledger_problem(data: bytes) -> str:
    """'' when ``data`` is a ledger --dispose-step replay-ledger reads (read_ledger_file: at most LEDGER_LIMIT bytes, and
    UTF-8), else why not - so the ledger step keeps no ledger the replay would refuse (refutation round 2, installer-0)."""
    if len(data) > LEDGER_LIMIT:
        return f'it is {len(data)} bytes, more than the {LEDGER_LIMIT} --dispose-step replay-ledger reads (LEDGER_LIMIT)'
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return 'it is not UTF-8 text'
    return ''


def read_ledger_file(path) -> bytes:
    """The ledger a replay re-applies (D1): a regular file, never a link, at most LEDGER_LIMIT bytes, UTF-8 (the rules
    ledger_problem states, which the ledger step keeps a ledger by). Its MAC is the command's to check (keyed by the
    application's SECRET_KEY, so a restore keeps the same key)."""
    given = Path(path or '')
    if not given.is_absolute():
        raise InstallError(f'--ledger-file must be an absolute path to a regular file of at most {LEDGER_LIMIT} bytes.')
    data = read_bounded_file(given, LEDGER_LIMIT, '--ledger-file')
    if ledger_problem(data):
        raise InstallError(f'--ledger-file is not a ledger --dispose-step replay-ledger reads: {ledger_problem(data)}.')
    return data


def grant_problem(ctx, image_id, env) -> dict:
    """The account a manage grant-operator names, read (GRANT_CHECK) and judged before the act: it must exist; one any of
    whose grants was ever revoked - or whose answer does not say - is refused unless --regrant names it and the committed
    declaration approves it, with the line "Approved: --regrant <username>" (declaration_names; A6; ADM-10 3(i);
    refutation, installer lens A-1). Returns what was read."""
    args = ctx.args
    found = app_script(image_id, env, GRANT_CHECK, {'username': args.username}, what='Reading the account to grant')
    if not isinstance(found, dict) or found.get('exists') is not True:
        raise InstallError(f'{args.username} is not an account here (or did not read back): nothing was granted.',
                           details={'grant_check': found})
    if found.get('revoked') is not False:
        if args.regrant != args.username or not declaration_names(ctx, f'--regrant {args.username}'):
            raise InstallError(f'{args.username} was revoked as an operator, and a revoked grant stays revoked: nothing '
                               f'was granted. To grant it again, run with --regrant {args.username} under a committed '
                               f'declaration with the line "Approved: --regrant {args.username}", which names it '
                               'nowhere else.', details={'grant_check': found})
    elif args.regrant is not None:
        raise InstallError(f'--regrant {args.regrant}: that account was never revoked, so there is nothing to grant '
                           'again; nothing was granted.', details={'grant_check': found})
    return found


def phase_manage(ctx) -> dict:
    """One allow-listed ruled act (MANAGE_COMMANDS; release 1, A6) in a one-shot of the installed image, once this
    revision's migrations are applied. The reason (and a setup code) travel as RAM-only files; a disposal is refused
    while an install or switch-back is in progress; the receipt names the act, the reason's sha256 and size, who ran it
    and the command's exit code and log - every output kept with the application's secrets and the reason redacted
    (redact_output, counted in 'redacted'), never a code."""
    args = ctx.args
    entry = MANAGE_COMMANDS[args.command]
    image_id = installed_image(ctx)
    require_db()
    env = read_protected_env(APP_ENV, APP_ENV_KEYS)
    pending = oneshot(image_id, ['manage', 'migrate', '--check'], env, timeout=120)
    if pending.returncode:
        raise InstallError(f'This revision\'s migrations are not all applied (manage migrate --check exited '
                           f'{pending.returncode}): run --phase app first. Nothing was run.')
    environment = None
    if args.command == 'grant-operator':
        record_grant = grant_problem(ctx, image_id, env)
    if args.command == 'dispose':
        busy = install_in_progress()
        if busy:
            raise InstallError(f'An install or switch-back is in progress ({", ".join(busy)}), and the installer assumes '
                               'no row is deleted during one: nothing was disposed of (RELEASE-1-SPEC D1).')
        # refutation round 2, switchback-0: a step that changes a row (close, execute, a replay with --execute: the
        # receipt's mode 'executed') runs only while the serving pair has disposal; the dry runs (plan, a replay
        # without --execute) and the ledger change no row such a revision reads, and stay open. Round 3, installer-0:
        # a replay with --execute also runs with no pair at all (nothing serves: a restore onto a fresh host)
        if dispose_mode(args) == 'executed':
            try:
                problem = serving_disposal_problem(replay=args.dispose_step == 'replay-ledger')
            except InstallError as error:
                raise InstallError(f'{error} Nothing was disposed of.') from error
            if problem:
                raise InstallError(f'--dispose-step {args.dispose_step}' + (' --execute' if args.execute else '')
                                   + f' changes rows, and {problem}: nothing was disposed of. A practice is closed, and '
                                   'a document destroyed, only while a revision with disposal (release 1 or later) '
                                   'serves (RELEASE-1-SPEC 6.3): install one (--phase app), then run this step again. '
                                   'The plan, the ledger and a replay without --execute stay open meanwhile: they '
                                   'change no row an older revision reads; a replay with --execute runs too when there '
                                   'is no pair at all (ops/INSTALL.md, Restoring the database).')
        # only now, the reading above made: Lane 4's dispose refuses unless it is told no switch is in progress (this
        # phase holds the receipts' lock, so no install starts on them while it runs)
        environment = runtime_env('disabled', '') + ['-e', 'CPT_STUDIO_SWITCH_STATE=idle']
    reason = read_reason_file(args.reason_file) if args.reason_file else None
    ledger = read_ledger_file(args.ledger_file) if getattr(args, 'ledger_file', None) else None
    record = {'command': args.command, 'by': args.by, 'username': args.username,
              'reason': ({'sha256': sha256(reason), 'bytes': len(reason)} if reason is not None else None)}
    if args.command == 'grant-operator':
        record['grant_check'] = record_grant
    if args.command == 'dispose':
        record.update(step=args.dispose_step, mode=dispose_mode(args),
                      ledger=({'sha256': sha256(ledger), 'bytes': len(ledger)} if ledger is not None else None))
    if entry.get('code'):
        record['setup_code'] = issue_setup_code(ctx, image_id, env, args.username, command=entry['command'], by=args.by,
                                                reason=reason)
        return {**record, 'summary': f'{args.command} {args.username}: done; the setup code is kept root-only in '
                                     f'{ETC_DIR}/{OPERATOR_ENROLMENT}, valid {ENROLMENT_CODE_SECONDS // 60} minutes'}
    argv = manage_argv(ctx, args, entry)
    files = entry.get('files')
    export = None
    if args.command == 'export-workspace':  # D2: a new folder of its own, root-only on the host
        export = export_name(args)
        run_helper(H_EXPORT_DIR, {'dir': PurePosixPath(EXPORTS_DIR).name, 'name': export, 'uid': APP_UID},
                   mounts=[EXPORTS_MOUNT])
        record['export'] = {'folder': f'{EXPORTS_DIR}/{export}', 'out': f'{EXPORTS_DIR}/{export}/{export}'}
    # refutation round 1 (builder D's point): once the act ran, what follows it - the RAM folder's wipe, the export's
    # seal - never takes its record with it; the record is written below, then that failure or interrupt is raised
    result, after_act = None, None
    try:
        with RamFiles('cpt-studio-manage-', owner=(APP_UID, APP_UID) if files else None) as ram:
            mounts = [ram.add('reason', reason, f'{MANAGE_MOUNT}/reason')] if reason is not None else []
            if ledger is not None:
                mounts.append(ram.add('ledger', ledger, f'{MANAGE_MOUNT}/ledger'))
            if files:
                ram.give()  # 0600 in 0700, the application's uid's for the act alone
                # a disposal deletes files (read-write); an export reads them and writes its own folder - as the
                # application's user, whose files they are
                mounts.append(f'type=volume,src={FILES_VOLUME},dst={STATE_DIR}' + (',readonly' if export else ''))
                if export:
                    mounts.append(f'type=bind,src={EXPORTS_DIR}/{export},dst={EXPORT_MOUNT}')
                result = oneshot(image_id, argv, env, mounts=mounts, timeout=act_timeout(3600),
                                 what=f'manage {entry["command"]}', by=args.by,
                                 **({'environment': environment} if environment else {}))
            else:
                result = oneshot(image_id, argv, env, mounts=mounts, user=f'{os.getuid()}:{os.getgid()}',
                                 timeout=act_timeout(600), what=f'manage {entry["command"]}', by=args.by)
    except BaseException as error:  # noqa: BLE001 — raised again below, with the act's record when it ran
        if result is None:  # an answer a signal reached in its one-shot's leftover check is the act's (round 3)
            result = oneshot_answer_of(error)
        if result is None:  # the act gave no answer, or never ran: there is no record of it to keep
            raise
        after_act = error
    finally:
        if export:  # done or not, everything in it is made root-only
            try:
                record['export'].update(run_helper(H_SEAL_EXPORT, {'dir': PurePosixPath(EXPORTS_DIR).name,
                                                                   'name': export}, mounts=[EXPORTS_MOUNT]))
            except BaseException as error:  # noqa: BLE001 — as the wipe's, once the act ran
                if result is None:
                    raise
                after_act = after_act or error
    # the application's own secrets, and the reason's text, never reach a log or a receipt (refutation A-7); and the act
    # has run, so its record is never discarded for them either (refutation round 1, phileak-1 and dataloss-3): each is
    # redacted before the log and the receipt are written, and the receipt counts them
    hidden, reasons = env_values(env), reason_values(reason)
    stdout, stdout_counts = redact_output(result.stdout, hidden, reasons)
    stderr, stderr_counts = redact_output(result.stderr, hidden, reasons)
    record.update(redaction_record(stdout_counts, stderr_counts))
    unkept = ''
    if args.command == 'dispose' and args.dispose_step == 'ledger':
        # refutation round 1, dataloss-1: the ledger is the act's whole stdout, kept whole in a log of its own - the
        # receipt's copy is cut to STDOUT_KEPT - and recorded by sha256, size and line count, to check the kept copy by.
        # Refutation round 2, installer-0: only a ledger the replay step reads is kept as one (ledger_problem); another
        # is written to no file, and the step fails below saying why
        unkept = ledger_problem(stdout)
        log = None if unkept else ctx.log('dispose-ledger', stdout)
        record['ledger_printed'] = {'log': log, 'sha256': sha256(stdout), 'bytes': len(stdout),
                                    'lines': sum(1 for line in stdout.splitlines() if line.strip()),
                                    'redacted': bool(sum(stdout_counts.values())),
                                    **({'not_kept': unkept} if unkept else {})}
        if stderr:
            record['stderr_log'] = ctx.log('dispose-ledger-stderr', stderr)
    else:
        log = ctx.log(args.command, stdout + stderr)
    record.update(exit=result.returncode, log=log, argv=argv, **kept_stdout(stdout))  # ids and counts only
    if after_act is not None:
        raise_after_act(after_act, record, f'manage {entry["command"]}')
    if unkept:
        raise InstallError(f'dispose ledger (exit {result.returncode}): the ledger it printed is not kept, since {unkept}, '
                           'so --dispose-step replay-ledger could not replay it after a restore. Nothing was changed: '
                           'this step only reads, and the database keeps every row the ledger is printed from. '
                           'LEDGER_LIMIT is sized for one whole-practice disposal of the largest practice this release '
                           'serves (ops/INSTALL.md, Disposal, returns and the ledger); a ledger past it needs a release '
                           'that raises it, printed again with that release. Until then, never restore the database '
                           'from a backup older than its newest disposal: no ledger could destroy that data again.',
                           details=record)
    if (result.returncode == DISPOSE_DECISION_EXIT and args.command == 'dispose'
            and args.dispose_step == 'replay-ledger' and args.execute):
        # Lane 4: a replay exits DISPOSE_DECISION_EXIT when an entry needs a person's decision - one whose commit's
        # outcome was unknown - and nothing else failed. Never done, and never an installer failure: recorded so, with
        # the command's ids-only output; a person decides by planning that scope again, with two people. Every other
        # non-zero exit is the failure below, its ids-only output in the receipt too.
        record['mode'] = DECISION_NEEDED
        return {**record, 'summary': f'dispose replay-ledger: {DECISION_NEEDED} (exit {result.returncode}): an entry '
                                     'whose outcome was unknown is left to a person - plan that scope again and '
                                     'execute it with two people (ops/INSTALL.md, Disposal, returns and the ledger)'
                                     + redaction_summary(record.get('redacted'))}
    if result.returncode:
        raise InstallError(f'manage {entry["command"]} failed (exit {result.returncode}); see {record["log"]}.',
                           details=record)
    done = 'done'
    if record.get('ledger_printed'):
        printed = record['ledger_printed']
        done = (f'read; the ledger ({printed["lines"]} line(s), sha256 {printed["sha256"][:12]}) is kept whole in '
                f'{printed["log"]}' + ('; FINDING: a secret it printed was redacted, so the line holding it no longer '
                                       'verifies - print the ledger again once that is fixed (the database\'s own '
                                       'is unchanged)' if printed['redacted'] else ''))
    elif args.command == 'dispose' and record['mode'] == 'dry run':  # a dry run never reads as done
        done = ('dry run, nothing was changed' + ('; to replay it, run again with --execute and --approved-by'
                                                   if args.dispose_step == 'replay-ledger' else ''))
    elif args.command == 'dispose':
        done = record['mode']
    if record.get('stdout_cut'):
        done += f'; the receipt keeps the last {STDOUT_KEPT} of its {record["stdout_chars"]} characters of output'
    return {**record, 'summary': f'{args.command}' + (f' {args.dispose_step}' if args.command == 'dispose' else '')
                                 + (f' {args.username}' if args.username else '') + f': {done}'
                                 + (f'; the export is root-only in {EXPORTS_DIR}/{export}' if export else '')
                                 + redaction_summary(record.get('redacted'))}


def acme_probe(ctx, label, host=DOMAIN) -> dict:
    """Prove the ACME path for ``host`` is served by this host's nginx from the shared webroot, then remove the probe.
    For ADMIN_HOST that path is the quillmd vhost's :80 block - QuillMD's file, which this installer never changes
    there (line QUILLMD_ACME_LINE_NUMBER) - and it answers the challenge of both lineages naming admin, QuillMD's and
    the cpt-studio one (ops/INSTALL.md, Known limits; refutation INGRESS-5, INSTALLER-10)."""
    token, content = secrets.token_urlsafe(24), secrets.token_hex(16)
    mount = f'type=bind,src={ACME_CHALLENGE_DIR},dst=/acme'
    run_helper(H_ACME_WRITE, {'name': token, 'content': content}, mounts=[mount])
    try:
        def check():
            result = probe('http', host, f'/.well-known/acme-challenge/{token}', connect_ip='127.0.0.1')
            served = result.get('status') == 200 and result.get('body_sha256') == sha256(content.encode())
            return served, {'status': result.get('status'), 'error': result.get('error')}
        passed, observations = poll(check, attempts=30, interval=0.25)
    finally:
        removed = run_helper(H_ACME_REMOVE, {'name': token, 'content': content}, mounts=[mount])
    return {'passed': passed, 'observations': observations[-3:], 'probe_removed': removed['removed'], 'label': label,
            'host': host}


def acme_problems(found) -> list:
    """The refusals of acme_probe answers ({host: answer})."""
    return [f'the ACME challenge path of {host} did not serve the probe (or it was not removed): renewal would fail'
            for host, answer in found.items() if not (answer.get('passed') and answer.get('probe_removed'))]


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
    """The HTTP stage (a fresh host's first ingress step). It writes quillmd-cpt only while the quillmd vhost still
    claims admin.quillmd.com's :443 (the before state): while it is the after state, quillmd-cpt is what claims it, and
    this phase refuses - run --phase ingress-rollback first (refutation INSTALLER-1, INGRESS-3)."""
    preflight = require_receipt(ctx, 'preflight')
    conf = rendered_vhosts(ctx.revision)['http']
    state = vhost_state()
    if state['file_exists'] or state['link_exists']:
        if state['file_sha256'] != sha256(conf.encode()) or state['link_target'] != VHOST_LINK_TARGET:
            raise InstallError('quillmd-cpt already exists and is not this HTTP stage; refusing. While an HTTPS stage '
                               "claims admin.quillmd.com's :443 (the after state), " + AFTER_STATE_REMEDY + '.')
    found = read_coupling(vhost=state)
    problem = coupling_problem(found, expected=('before',), remedy=AFTER_STATE_REMEDY)
    if problem:
        raise InstallError(f'{problem}; nothing was written.', details={'coupling': found})

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
            'coupling': found, 'summary': 'HTTP stage live; ACME path proven'}


# The way back while quillmd-cpt claims admin.quillmd.com's :443 (the after state): a phase that would leave the quillmd
# vhost the after state with no quillmd-cpt naming admin refuses and names it.
AFTER_STATE_REMEDY = ('run --phase ingress-rollback first: it gives admin.quillmd.com back to the quillmd vhost and '
                      'quillmd-cpt the stage the ingress replaced, in one act (ops/INSTALL.md, ingress-rollback)')


def cert_stage(ctx) -> dict:
    """What the cert phase stands on, read before certbot is asked for anything (refutation INGRESS-7, INSTALLER-3): on
    a fresh host, this revision's http-vhost receipt and a stage this revision renders ('fresh'); on a served site, with
    no http-vhost receipt of this revision, the stage the running web is served through ('served') - an HTTPS stage a
    successful receipt here recorded, whichever revision wrote it, proxying to the port the running web publishes
    (live_web_port). Without any receipt recording a stage it refuses before reading the host."""
    fresh = latest_receipt(ctx.receipts, 'http-vhost', ctx.revision)
    recorded = recorded_vhosts(ctx)
    if fresh is None and not recorded:
        raise InstallError(f'No successful --phase http-vhost receipt for this revision in {ctx.receipts}, and no '
                           'receipt there records the stage a served site runs; refusing to request a certificate.')
    current = vhost_state()['file_sha256']
    renderings = vhost_renderings(ctx.revision)
    if fresh is not None and current in renderings:
        return {'site': 'fresh', 'vhost_sha256': current, 'kind': renderings[current]['kind']}
    if current in recorded and recorded[current][1] == 'https':
        return {'site': 'served', 'vhost_sha256': current, 'kind': 'https', 'port': live_web_port(),
                'recorded_by': recorded[current][0]}
    raise InstallError('quillmd-cpt is not a stage this installer wrote; refusing to request a certificate.')


def phase_cert(ctx) -> dict:
    """The cpt-studio lineage for both hosts the HTTPS stage serves, DOMAIN and ADMIN_HOST (D396 release 2): one certbot
    run, webroot /var/www/certbot for both names - DOMAIN's HTTP-01 challenge answered by quillmd-cpt's :80 block,
    ADMIN_HOST's by the quillmd vhost's (QuillMD's file, unchanged: ops/INSTALL.md, Known limits) - the one existing
    ACME account, never --expand. Both challenge paths are proven first (acme_probe), and DNS for both names. DOMAIN's
    own lineage stays and keeps renewing, unused; neither CPT lineage counts as another lineage (other_lineages)."""
    stage = cert_stage(ctx)
    problem = coupling_problem(read_coupling())  # refutation R2 round 1, WAYBACK-5
    if problem:
        raise InstallError(f'{problem}; no certificate was requested.')
    for host in (DOMAIN, ADMIN_HOST):
        infos = socket.getaddrinfo(host, 80, type=socket.SOCK_STREAM)
        if {info[4][0] for info in infos} != {PUBLIC_IPV4}:
            raise InstallError(f'{host} no longer resolves to {PUBLIC_IPV4} alone.')
    before = le_state()
    if len(before['accounts']) != 1:
        raise InstallError(f'Exactly one existing ACME account is required, found {len(before["accounts"])}; '
                           'this installer never registers one.')
    acme = {host: acme_probe(ctx, 'cert', host) for host in (DOMAIN, ADMIN_HOST)}
    failed = acme_problems(acme)
    if failed:
        raise InstallError('; '.join(failed) + '; no certificate was requested.', details={'acme': acme})
    mounts = [ROOT_MOUNT, 'type=tmpfs,dst=/host/tmp'] + [f'type=bind,src={path},dst=/host{path}' for path in LE_DIRS]
    result = run_helper(H_CERTBOT, {'domains': [DOMAIN, ADMIN_HOST], 'cert_name': CERT_NAME,
                                    'account': before['accounts'][0], 'timeout': 240},
                        mounts=mounts, network='host', timeout=300)
    log = ctx.log('certbot', result['output'].encode())
    after = le_state()
    lineage = after['live'].get(CERT_NAME) or {}
    problems = []
    if result['returncode']:
        problems.append(f'certbot exited {result["returncode"]}')
    if not (lineage.get('fullchain.pem') and lineage.get('privkey.pem') and f'{CERT_NAME}.conf' in after['renewal']):
        problems.append(f'the {CERT_NAME} lineage paths are not all present')
    if other_lineages(before) != other_lineages(after):
        problems.append('another lineage changed')
    if after['accounts'] != before['accounts']:
        problems.append('the ACME account set changed')
    if problems:
        raise InstallError('; '.join(problems) + f'; see {log}.')
    return {'lineage': lineage, 'cert_name': CERT_NAME, 'domains': [DOMAIN, ADMIN_HOST],
            'renewal_conf': f'{CERT_NAME}.conf', 'stage': stage, 'acme': acme, 'account_reused': True,
            'certbot_log': log,
            'summary': f'lineage {CERT_NAME} for {DOMAIN} and {ADMIN_HOST} present (paths only recorded)'}


def public_health(revision) -> tuple:
    """(passed, observations): https://cpt.quillmd.com/health/ through the public path answers health_ok for
    ``revision``, polled (reloads are asynchronous) - which says which web nginx routes to only when the two webs are
    different revisions."""
    def check():
        result = probe('https', DOMAIN, '/health/', timeout=3)
        return result.get('status') == 200 and health_ok(result.get('json'), revision, through_nginx=True), {
            'status': result.get('status'), 'error': result.get('error')}
    return poll(check, attempts=30, interval=0.25)


# The edge's policy headers (deploy/nginx/cpt-quillmd-https.conf), one copy each on every answer of either host.
POLICY_HEADERS = (('strict-transport-security', 'max-age=31536000'), ('x-content-type-options', 'nosniff'),
                  ('referrer-policy', 'same-origin'), ('x-robots-tag', 'noindex, nofollow'))
ADMIN_CERT_NAMES = sorted((DOMAIN, ADMIN_HOST))  # the cpt-studio lineage's certificate names exactly these


def admin_checks(revision) -> tuple:
    """(problems, evidence): admin.quillmd.com's :443 judged positively through the public path (refutation
    INSTALLER-1, INSTALLER-5, INGRESS-10, APP-2): first, polled (reloads are asynchronous), it is served with the
    cpt-studio lineage's certificate - which names exactly the two hosts, so quillmd-cpt's block answered, never the
    quillmd vhost's (the quillmd.com lineage) or a co-tenant's - with the edge's four policy headers once each. Then,
    when ``revision``'s web serves the admin host (serves_admin_host: release 1 of D396 on), the answers only the admin
    urlconf gives (admin_answers) and its /health/ for ``revision``; an older web answers the admin host 400, which is
    recorded and never a problem (after a switch-back to a revision before release 1, until ingress-rollback)."""
    def check():
        found = probe('https', ADMIN_HOST, '/health/', timeout=3)
        return found.get('cert_names') == ADMIN_CERT_NAMES, {
            'status': found.get('status'), 'error': found.get('error'), 'cert_names': found.get('cert_names')}
    served, observations = poll(check, attempts=30, interval=0.25)
    edge = probe('https', ADMIN_HOST, '/health/', timeout=5)
    problems = []
    if not served or edge.get('cert_names') != ADMIN_CERT_NAMES:
        problems.append(f'{ADMIN_HOST} was not served with the {CERT_NAME} certificate (it named '
                        f'{edge.get("cert_names") or edge.get("error")})')
    headers = edge.get('headers') or {}
    for name, value in POLICY_HEADERS:
        if headers.get(name) != [value]:
            problems.append(f'{ADMIN_HOST}: {name} is not exactly one {value!r}')
    evidence = {'observations': observations[-3:],
                'edge': {key: edge.get(key) for key in ('status', 'error', 'cert_sha256', 'cert_names', 'headers')}}
    if serves_admin_host(revision):
        if not (edge.get('status') == 200 and health_ok(edge.get('json'), revision, through_nginx=True)):
            problems.append(f'https://{ADMIN_HOST}/health/ did not serve revision {revision[:12]}')

        def fetch(path, method, keep_body):
            return probe('https', ADMIN_HOST, path, method=method, timeout=5, keep_body=keep_body)
        answer_problems, evidence['answers'] = admin_answers(fetch)
        problems += answer_problems
    else:
        evidence['answers'] = {'judged': False, 'status': edge.get('status'),
                               'why': f'revision {str(revision)[:12]} does not serve the admin host (400 expected)'}
    return problems, evidence


def https_checks(ctx, revision=None) -> tuple:
    """Through the public path, both hosts of the HTTPS stage (ops/INSTALL.md, own-host checks): /health/ serves
    ``revision`` (this phase's revision unless given: a switch-back expects the previous one) with the four policy
    headers once each; admin_checks (revision-aware), polled until the reloaded configuration answers the admin host;
    the two hosts served the same certificate; a request for either host on a connection opened for app.quillmd.com -
    whose certificate also covers admin.quillmd.com, so a browser may reuse it - answered 421 Misdirected Request, never
    the application (refutation INGRESS-1, INSTALLER-7: a 444 would end in a browser error page; a 421 makes it retry on
    a fresh connection); and a request for either host on a connection opened for the other served (one certificate
    covers both), the admin host's revision-aware."""
    expected = revision or ctx.revision
    passed, observations = public_health(expected)
    admin_problems, admin = admin_checks(expected)
    final = probe('https', DOMAIN, '/health/', timeout=5)
    headers = final.get('headers', {})
    problems = [] if passed else [f'https://{DOMAIN}/health/ did not serve revision {expected[:12]}']
    for name, value in POLICY_HEADERS:
        if headers.get(name) != [value]:
            problems.append(f'{name} is not exactly one {value!r}')
    problems += admin_problems
    # by the names they carry, not their bytes: a renewal between the two probes changes the bytes of a right
    # certificate (refutation R2 round 1, CERT-4); a wrong lineage still differs by its names
    if admin['edge'].get('cert_names') != final.get('cert_names') or not final.get('cert_names'):
        problems.append(f'{ADMIN_HOST} and {DOMAIN} were not served certificates naming the same hosts')
    # nginx picks the server by Host, so SNI app.quillmd.com with Host cpt.quillmd.com (or admin.quillmd.com) reaches
    # this vhost on another name's connection: its $ssl_server_name guard must answer 421.
    misdirected = {host: probe('https', APP_HEALTH_HOST, '/health/', headers={'Host': host}, timeout=5)
                   for host in (DOMAIN, ADMIN_HOST)}
    for host, answer in misdirected.items():
        if answer.get('status') != 421 or 'json' in answer:
            problems.append(f'a request for {host} on a connection opened for {APP_HEALTH_HOST} was answered '
                            f'{answer.get("status") or answer.get("error")}, not 421 Misdirected Request')
    cross = {(sni, host): probe('https', sni, '/health/', headers={'Host': host}, timeout=5)
             for sni, host in ((ADMIN_HOST, DOMAIN), (DOMAIN, ADMIN_HOST))}
    serving = serves_admin_host(expected)
    for (sni, host), answer in cross.items():
        if host == ADMIN_HOST and not serving:
            continue  # recorded: an older web answers the admin host 400
        if not (answer.get('status') == 200 and health_ok(answer.get('json'), expected, through_nginx=True)):
            problems.append(f'a request for {host} on a connection opened for {sni} was answered '
                            f'{answer.get("status") or answer.get("error")}, not {expected[:12]}\'s /health/')
    return problems, {'observations': observations[-3:], 'final': final, 'admin': admin,
                      'sni_mismatch': {host: {key: answer.get(key) for key in ('status', 'error')}
                                       for host, answer in misdirected.items()},
                      'cross_name': {f'{sni} > {host}': {key: answer.get(key) for key in ('status', 'error')}
                                     for (sni, host), answer in cross.items()}}


# --- release 1 (A4): what the shared TLS listener actually negotiates for CPT's names ----------------------------------
# The HTTPS stage sets AES-GCM suites only (ssl_ciphers, ssl_conf_command Ciphersuites), but CPT shares the 443 listener
# with co-tenant server blocks, and whether a non-default block's TLS settings apply once SNI has chosen it is the TLS
# library's business. So it is measured: the host's openssl, against 127.0.0.1:443 with each name as the server name,
# offers one family at a time that the policy refuses, and each must end in an alert FROM THE SERVER - a client that
# cannot offer the family ("no ciphers available") never counts as a refusal (TEC-18 (2)); and a default client must
# negotiate an AES-GCM suite. A difference is a finding: https-vhost records it without undoing the publish, and verify
# reports it (owner decision D27); the fix is CPT's own nginx on the new server.
OPENSSL = '/usr/bin/openssl'
TLS_REFUSED_PROBES = (
    ('TLSv1.3 ChaCha20', ('-tls1_3', '-ciphersuites', 'TLS_CHACHA20_POLY1305_SHA256')),
    ('TLSv1.2 ChaCha20', ('-tls1_2', '-cipher', 'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305')),
    ('TLSv1.2 ARIA-GCM', ('-tls1_2', '-cipher', 'ECDHE-ECDSA-ARIA256-GCM-SHA384:ECDHE-ECDSA-ARIA128-GCM-SHA256:'
                                               'ECDHE-ARIA256-GCM-SHA384:ECDHE-ARIA128-GCM-SHA256')),
    ('TLSv1.2 Camellia', ('-tls1_2', '-cipher', 'ECDHE-ECDSA-CAMELLIA256-SHA384:ECDHE-ECDSA-CAMELLIA128-SHA256:'
                                               'ECDHE-RSA-CAMELLIA256-SHA384:ECDHE-RSA-CAMELLIA128-SHA256')),
    ('TLSv1.2 AES-CBC-SHA', ('-tls1_2', '-cipher', 'ECDHE-ECDSA-AES256-SHA:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA:'
                                                  'ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:'
                                                  'ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA256')),
    ('TLSv1.1', ('-tls1_1', '-cipher', 'DEFAULT@SECLEVEL=0')),
    ('TLSv1.0', ('-tls1', '-cipher', 'DEFAULT@SECLEVEL=0')),
)
TLS_NEGOTIATED_RE = re.compile(r'New, (\S+), Cipher is (\S+)')
TLS_SESSION_CIPHER_RE = re.compile(r'^\s*Cipher\s*:\s*(\S+)\s*$', re.M)
# the client refused to offer: never the server's refusal (TEC-18 (2))
TLS_CLIENT_SIDE_RE = re.compile(r'(?i)no ciphers available|no protocols available|no cipher match|'
                                r'unsupported protocol|unknown option|error with command|bad cipher')
# an alert the server sent ("SSL alert number N" names the alert received from the peer)
TLS_SERVER_ALERT_RE = re.compile(r'(?i)(?:sslv3|tlsv1) alert [a-z ]+|SSL alert number \d+')
TLS_APPROVED_RE = re.compile(r'(?:ECDHE-(?:ECDSA|RSA)-AES(?:128|256)-GCM-SHA(?:256|384)|TLS_AES_(?:128|256)_GCM_SHA(?:256|384))')


def tls_probe_verdict(returncode, output) -> dict:
    """What one `openssl s_client` run says (A4): {'verdict': 'accepted' (with 'protocol' and 'cipher'), 'refused'
    (the server sent an alert), 'client' (the client could not offer what was asked: never a refusal) or 'unknown'}.
    A cipher actually negotiated wins over everything; a client-side failure over an alert."""
    text = output.decode('utf-8', 'replace') if isinstance(output, bytes) else str(output)
    found = TLS_NEGOTIATED_RE.search(text)
    session = TLS_SESSION_CIPHER_RE.search(text)
    cipher = found.group(2) if found else (session.group(1) if session else None)
    if cipher and cipher not in ('(NONE)', '0000'):
        return {'verdict': 'accepted', 'protocol': found.group(1) if found else None, 'cipher': cipher}
    client = TLS_CLIENT_SIDE_RE.search(text)
    if client:
        return {'verdict': 'client', 'why': client.group(0).lower()}
    alert = TLS_SERVER_ALERT_RE.search(text)
    if alert:
        return {'verdict': 'refused', 'alert': alert.group(0).lower()}
    return {'verdict': 'unknown', 'exit': returncode}


def tls_probe(host, options) -> dict:
    """One `openssl s_client` run against this host's nginx (127.0.0.1:443) with ``host`` as the server name and
    ``options`` (a protocol and a cipher family), judged by tls_probe_verdict; openssl missing, a timeout or anything
    else that keeps it from answering is 'unknown', never a pass."""
    try:
        done = run([OPENSSL, 's_client', '-connect', '127.0.0.1:443', '-servername', host, *options], input=b'',
                   timeout=20, check=False)
    except (InstallError, OSError) as error:
        return {'verdict': 'unknown', 'why': (str(error) or type(error).__name__)[:200]}
    return tls_probe_verdict(done.returncode, done.stdout + done.stderr)


def tls_policy_problems(hosts=(DOMAIN, ADMIN_HOST), probe=None) -> tuple:
    """(findings, probes) of the TLS policy for each of ``hosts`` (A4): a default client must negotiate an AES-GCM suite,
    and each TLS_REFUSED_PROBES family must end in the server's alert - 'accepted' is a suite outside the policy, and
    'client' or 'unknown' a probe that could not tell, which is never counted as a refusal. Never raises."""
    probe = probe or tls_probe
    findings, probes = [], {}
    for host in hosts:
        seen = probes[host] = {}
        default = seen['default'] = probe(host, ())
        if default.get('verdict') != 'accepted' or not TLS_APPROVED_RE.fullmatch(str(default.get('cipher'))):
            findings.append(f'{host}: a default client did not negotiate an AES-GCM suite ({default.get("verdict")}'
                            + (f', {default.get("cipher")}' if default.get('cipher') else '') + ')')
        for label, options in TLS_REFUSED_PROBES:
            answer = seen[label] = probe(host, options)
            if answer.get('verdict') == 'accepted':
                findings.append(f'{host}: {label} negotiated {answer.get("cipher")} ({answer.get("protocol")}), '
                                'outside the policy')
            elif answer.get('verdict') != 'refused':
                findings.append(f'{host}: the {label} probe could not tell ({answer.get("verdict")}: '
                                f'{answer.get("why") or answer.get("exit")}); a refusal the client made is never '
                                'counted as the server\'s')
    return findings, probes


def tls_policy_report() -> dict:
    """tls_policy_problems as a receipt records it (A4; D27): {'findings', 'probes'}. Never raises: a failure to probe is
    itself a finding."""
    try:
        findings, probes = tls_policy_problems()
    except Exception as error:  # noqa: BLE001 - recorded, never an undo or a refusal
        findings, probes = [f'the TLS probes did not run ({type(error).__name__})'], {}
    return {'findings': findings, 'probes': probes}


def running_web() -> dict:
    """The running cpt-studio-web this installer started: {'id', 'image', 'revision', 'port'}; refused otherwise."""
    web = inspect('container', SERVICES['web'])
    if web is None or not owned(web, 'web') or not (web.get('State') or {}).get('Running'):
        raise InstallError(f'{SERVICES["web"]} is not a running CPT Studio web; nothing was written.')
    return {'id': web.get('Id'), 'image': web.get('Image'), 'revision': labels_of(web).get(REVISION_LABEL),
            'port': published_port(web)}


def phase_https_vhost(ctx) -> dict:
    """This revision's HTTPS stage for the port the running web publishes, written in place over the HTTPS stage an
    earlier revision's phase wrote there: the republish of a deploy/nginx change (ops/INSTALL.md, Reinstalling a new
    revision; refutation INSTALLER-1). Since release 2 of the admin move every HTTPS stage this installer renders names
    admin.quillmd.com, so the stage it replaces must too: the quillmd vhost stays the after state (the coupling
    invariant), and one file is replaced in one reload - both hosts served throughout, never a removal. The first such
    stage - over a fresh host's HTTP stage, or over an earlier stage that names no admin host - moves admin's :443 off
    the quillmd vhost, which --phase ingress alone does (both files in one act): this phase refuses it and names that
    phase. Run with this revision's stage already live, it verifies and changes nothing."""
    preflight = require_receipt(ctx, 'preflight')
    require_receipt(ctx, 'cert')
    problem = unrecorded_ingress_problem(ctx)  # round 2, INTENT-1: no stage moves under an unrecorded ingress
    if problem:
        raise InstallError(f'{problem}; nothing was written.')
    state = vhost_state()
    current = state['file_sha256']
    renderings = vhost_renderings(ctx.revision)
    recorded = recorded_vhosts(ctx).get(current)
    if (state['link_target'] != VHOST_LINK_TARGET or current is None
            or (current not in renderings and (recorded or (None, None))[1] != 'https')):
        raise InstallError('quillmd-cpt is not a stage this installer wrote and no successful receipt here records; '
                           'refusing.')
    # The HTTPS stage proxies to the port the running web publishes (it alternates with each blue/green install).
    port = serving_web_port()
    confs = rendered_vhosts(ctx.revision, port)
    http_sha, https_sha = sha256(confs['http'].encode()), sha256(confs['https'].encode())
    if current == http_sha:
        raise InstallError("quillmd-cpt is the HTTP stage: its first HTTPS stage moves admin.quillmd.com's :443 off the "
                           'quillmd vhost, which --phase ingress does (both files in one act); run it instead. Nothing '
                           'was written.')
    if current in renderings and current != https_sha:
        raise InstallError(f'quillmd-cpt holds the HTTPS stage for another port than {port}, the one '
                           f'{SERVICES["web"]} publishes; refusing.')
    replaced = live = None
    if current != https_sha:
        live = live_vhost_bytes()
        if live is None or sha256(live) != current:
            raise InstallError('quillmd-cpt changed while it was being read; refusing.')
        text = live.decode('utf-8', 'replace')
        if proxied_port(text) != port:
            raise InstallError(f'quillmd-cpt is an earlier HTTPS stage proxying to another port than {port}, the one '
                               f'{SERVICES["web"]} publishes; refusing.')
        if names_host_on(text, ADMIN_HOST) is not True:
            raise InstallError('quillmd-cpt is an earlier HTTPS stage that names no admin host: --phase ingress moves '
                               "admin.quillmd.com's :443 onto this revision's stage (both files in one act); run it "
                               'instead. Nothing was written.')
        replaced = {'sha256': current, 'recorded_by': recorded[0]}
    found = read_coupling(vhost=state)
    problem = coupling_problem(found, expected=('after',))
    if problem:
        raise InstallError(f'{problem}; nothing was written.', details={'coupling': found})
    lineage = le_state()['live'].get(CERT_NAME) or {}
    if not (lineage.get('fullchain.pem') and lineage.get('privkey.pem')):
        raise InstallError(f'The {CERT_NAME} lineage is not present.')
    web = running_web()

    def apply():
        vhost_operation('replace', expected_sha256=current, content=base64.b64encode(confs['https'].encode()).decode())

    def undo():
        if vhost_state()['file_sha256'] == https_sha:
            vhost_operation('replace', expected_sha256=https_sha, content=base64.b64encode(live).decode())

    def verify():
        problems, evidence = https_checks(ctx, web['revision'])
        redirect = probe('http', DOMAIN, '/', connect_ip='127.0.0.1')
        if redirect.get('status') != 301 or redirect.get('headers', {}).get('location') != [f'https://{DOMAIN}/']:
            problems.append(f'http://{DOMAIN}/ did not redirect to https')
        acme = {host: acme_probe(ctx, 'https-vhost', host) for host in (DOMAIN, ADMIN_HOST)}
        problems += acme_problems(acme)
        problems += ingress_checks(ctx, preflight)
        if problems:
            raise InstallError('; '.join(problems) + '.', details=evidence)
        # release 1 (A4): what the shared listener negotiates is recorded, never a reason to undo the publish (D27)
        return {**evidence, 'redirect': redirect, 'acme': acme, 'tls_policy': tls_policy_report()}
    already = current == https_sha
    result = verify() if already else publish_vhost(ctx, apply, undo, verify)
    tls = (result.get('tls_policy') or {}).get('findings') or []
    return {**result, 'vhost_sha256': https_sha, 'upstream_port': port, 'already_installed': already,
            'replaced': replaced, 'coupling': found,
            'summary': f'https://{DOMAIN}/ and https://{ADMIN_HOST}/ served through {ctx.revision[:12]}\'s stage'
                       + (f'; TLS policy: {len(tls)} finding(s) recorded (D27)' if tls else '; TLS policy as set')}


def write_intent(ctx, phase: str, record: dict) -> Path:
    """A phase's write-ahead record (refutation R2 round 1, COTENANT-1, CERT-1, WAYBACK-2): what it is about to replace,
    byte for byte, written (0600, fsynced) BEFORE anything changes, so a run killed between the change and its receipt
    (SIGKILL, an OOM kill, a host reset, the door's ceiling) still leaves the way back on disk. Named intent-<phase>-*,
    never matched by a receipt's glob."""
    return write_private(ctx.receipts, f'intent-{phase}-{stamp()}.json',
                         (json.dumps({'phase': f'{phase}-intent', **record}, indent=2, sort_keys=True) + '\n').encode())


def unrecorded_ingress(ctx):
    """(path, record) of this revision's newest ingress intent that no successful moved ingress receipt of this revision
    was written after (refutation R2 rounds 1 and 2), or None. Only a recorded move resolves it: a failed receipt does not
    (a completion refused before it reloaded writes one, and the move is still unrecorded). Whether it matters is read from
    the files, not the receipts: only while the coupling is not the before state (unrecorded_ingress_problem; ingress's
    completion and ingress-rollback check it so). A torn intent file is skipped: the intent is written and fsynced before
    either file changes, so a run killed while writing it changed nothing (round 2, INTENT-7). Any stage: the stage may
    have moved since (INTENT-1)."""
    moved = latest_ingress_move(ctx)
    for path in sorted(ctx.receipts.glob('intent-ingress-*.json'), reverse=True):
        record = read_json_or_none(path)
        if not (isinstance(record, dict) and record.get('revision') == ctx.revision):
            continue
        if moved is not None and written_after(moved[0], (path, record)) is not False:
            return None  # the move was recorded after this intent (or the order cannot be told: a move is on record)
        return path, record
    return None


def read_json_or_none(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def unrecorded_ingress_problem(ctx) -> str:
    """'' unless an ingress of this revision changed the two files and its move is not recorded, the files not back in
    the before state: then no phase may move the stage until ingress runs again and records the move (round 2,
    INTENT-1, GUARDS-3)."""
    pending = unrecorded_ingress(ctx)
    if pending is None or read_coupling()['coupling'] == 'before':
        return ''
    return (f'an ingress of this revision changed the two files and stopped before it recorded the move '
            f'({pending[0].name}): run --phase ingress again first; it completes and records the move')


def latest_ingress_move(ctx, *, any_revision=False):
    """(path, record) of the newest successful ingress receipt of this revision - of any revision with
    ``any_revision`` - that moved admin.quillmd.com's :443 (its 'moved'; a rerun on the after state moves nothing), or
    None."""
    for path in sorted(ctx.receipts.glob('ingress-*.json'), reverse=True):
        record = json.loads(path.read_text(encoding='utf-8'))
        if (isinstance(record, dict) and record.get('phase') == 'ingress' and record.get('ok')
                and (any_revision or record.get('revision') == ctx.revision)
                and (record.get('details') or {}).get('moved') is True):
            return path, record
    return None


def loopback_admin_answers(port) -> tuple:
    """admin_answers of the web on 127.0.0.1:``port`` (Host admin.quillmd.com, as nginx will send it)."""
    def fetch(path, method, keep_body):
        return probe('http', ADMIN_HOST, path, port=port, connect_ip='127.0.0.1', method=method,
                     headers={'X-Forwarded-Proto': 'https'}, timeout=5, keep_body=keep_body)
    return admin_answers(fetch)


def read_back_problems(quillmd, vhost) -> list:
    """Both files read again after a two-file write (nginx_file_state): the quillmd vhost's sha256 ``quillmd`` and
    quillmd-cpt's ``vhost``."""
    available = nginx_file_state()['available']
    found = {'quillmd': available.get('quillmd'), VHOST_NAME: available.get(VHOST_NAME)}
    if found == {'quillmd': quillmd, VHOST_NAME: vhost}:
        return []
    return [f'the two files did not read back as written (quillmd {str(found["quillmd"])[:12]}, quillmd-cpt '
            f'{str(found[VHOST_NAME])[:12]})']


def phase_ingress(ctx) -> dict:
    """admin.quillmd.com's :443 moved from the quillmd vhost onto quillmd-cpt in one act (D396 release 2; ops/INSTALL.md,
    ingress): this revision's HTTPS stage - both hosts in one server block - for the port the running web publishes,
    and the quillmd vhost without admin on its :443 line (quillmd_bytes), written by one root-helper operation in the
    safe order (couple: quillmd-cpt first, the quillmd vhost second), validated together (nginx -t, no new warning),
    reloaded once and verified; on any failure both are written back, the quillmd vhost first (decouple, which accepts
    each partial state). It starts only from the before state of the coupling invariant, quillmd-cpt being the stage
    the running web is served through - an HTTPS stage a successful receipt here recorded (or this revision renders),
    proxying to the port that web publishes, or this revision's HTTP stage on a fresh host - and only when that web
    already answers the admin host (release 1 of D396 on: serves_admin_host, then its own answers on the loopback port),
    so the admin host is answered by the application from the reload on: no window. The receipt keeps the stage it
    replaced, byte for byte, for ingress-rollback. On the after state with this revision's stage for the live port
    already there it verifies and changes nothing."""
    preflight = require_receipt(ctx, 'preflight')
    require_receipt(ctx, 'cert')
    state = vhost_state()
    if not state['file_exists'] or state['file_sha256'] is None or state['link_target'] != VHOST_LINK_TARGET:
        raise InstallError('quillmd-cpt is not the regular file and sites-enabled link this installer writes; nothing '
                           'was written.')
    current = state['file_sha256']
    live = live_vhost_bytes()
    if live is None or sha256(live) != current:
        raise InstallError('quillmd-cpt changed while it was being read; nothing was written.')
    renderings = vhost_renderings(ctx.revision)
    known, recorded = renderings.get(current), recorded_vhosts(ctx).get(current)
    web = running_web()
    if known is not None and known['kind'] == 'http':
        if latest_receipt(ctx.receipts, 'http-vhost', ctx.revision) is None:
            raise InstallError(f'No successful --phase http-vhost receipt for this revision in {ctx.receipts}.')
        if web['port'] is None:
            raise InstallError(f'{SERVICES["web"]} publishes neither web port; nothing was written.')
        port, source = web['port'], {'kind': 'http', 'port': None, 'recorded_by': ctx.revision}
    elif (known or {}).get('kind') == 'https' or (recorded or (None, None))[1] == 'https':
        port = live_web_port()  # the stage's upstream, which the running web must publish
        source = {'kind': 'https', 'port': port, 'recorded_by': (recorded or (ctx.revision,))[0]}
    else:
        raise InstallError('quillmd-cpt holds content this installer did not write and no successful receipt here '
                           'records; nothing was written.')
    target = rendered_vhosts(ctx.revision, port)['https'].encode()
    target_sha = sha256(target)
    found = read_coupling(vhost=state)
    already = found['coupling'] == 'after' and current == target_sha
    if not already:
        problem = coupling_problem(found, expected=('before',))
        if problem:
            raise InstallError(f'{problem}; nothing was written.', details={'coupling': found})
        if names_host_on(target.decode('utf-8'), ADMIN_HOST) is not True:
            raise InstallError("This revision's HTTPS stage names no admin host on 443; nothing was written.")
        if not serves_admin_host(web['revision']):
            raise InstallError(f'The running web, {str(web["revision"])[:12]}, does not answer the admin host (release 1 '
                               'of D396 and later do): install one with an ordinary blue/green app first, then rerun; '
                               'nothing was written.')
        answer_problems, answers = loopback_admin_answers(port)
        if answer_problems:
            raise InstallError(f'The running web on {port} does not answer the admin host yet: '
                               + '; '.join(answer_problems) + '. Nothing was written.', details={'answers': answers})
        lineage = le_state()['live'].get(CERT_NAME) or {}
        if not (lineage.get('fullchain.pem') and lineage.get('privkey.pem')):
            raise InstallError(f'The {CERT_NAME} lineage is not present (run --phase cert first); nothing was written.')
        quillmd_before = quillmd_vhost_bytes()
        quillmd_after = quillmd_bytes(quillmd_before, 'after')
        if sha256(quillmd_before) != QUILLMD_VHOST_BEFORE:
            raise InstallError('The quillmd vhost changed while it was being read; nothing was written.')
        drifted = ingress_checks(ctx, preflight)
        if drifted:
            raise InstallError(baseline_problem(drifted, 'nothing was written'), details={'baseline': drifted})

    def apply():
        vhost_operation('couple', expected_sha256=current, content=base64.b64encode(target).decode(),
                        quillmd_content=base64.b64encode(quillmd_after).decode())

    def undo():
        vhost_operation('decouple', expected_sha256=target_sha, content=base64.b64encode(live).decode(),
                        quillmd_content=base64.b64encode(quillmd_before).decode())

    def verify():
        problems, evidence = https_checks(ctx, web['revision'])
        acme = {host: acme_probe(ctx, 'ingress', host) for host in (DOMAIN, ADMIN_HOST)}
        problems += acme_problems(acme)
        redirect = probe('http', DOMAIN, '/', connect_ip='127.0.0.1')
        if redirect.get('status') != 301 or redirect.get('headers', {}).get('location') != [f'https://{DOMAIN}/']:
            problems.append(f'http://{DOMAIN}/ did not redirect to https')
        problems += ingress_checks(ctx, preflight)
        problems += read_back_problems(QUILLMD_VHOST_AFTER, target_sha)
        if problems:
            raise InstallError('; '.join(problems) + '.', details={**evidence, 'acme': acme})
        return {**evidence, 'acme': acme, 'redirect': redirect}
    quillmd_pins = {'before': QUILLMD_VHOST_BEFORE, 'after': QUILLMD_VHOST_AFTER, 'line': QUILLMD_ADMIN_LINE_NUMBER}
    if already:
        pending = unrecorded_ingress(ctx)
        if pending is None:
            return {**verify(), 'moved': False, 'already_installed': True, 'vhost_sha256': target_sha,
                    'upstream_port': port, 'web': web, 'coupling': found,
                    'summary': f'admin.quillmd.com already served through {ctx.revision[:12]}\'s stage for {port}; '
                               'verified, nothing written'}
        # an ingress of this revision wrote the two files and stopped before any receipt (refutation R2 rounds 1 and 2):
        # completed exactly as the move itself runs - co-tenant routing checked first, nginx tested against the warnings
        # the intent recorded before the write, reloaded and verified, written back to the intent's stage on any failure
        intent = pending[1]
        if intent.get('vhost_sha256') != target_sha:  # round 2, INTENT-1: the stage moved since (an app or a switch-back)
            found_web = intent.get('web') or {}
            raise InstallError(f'An ingress of this revision stopped before it recorded its move ({pending[0].name}), '
                               'for a stage that is no longer live: the stage moved since. Switch back until '
                               f'{str(found_web.get("revision"))[:12]} serves on {intent.get("upstream_port")} with this '
                               'revision\'s stage for that port, then rerun --phase ingress. Nothing was written.',
                               details={'intent': str(pending[0])})
        saved = base64.b64decode(intent['from']['b64'])
        if sha256(saved) != intent['from']['sha256'] or names_host_on(saved.decode('utf-8', 'replace'), ADMIN_HOST):
            raise InstallError('The intent\'s saved stage is not the one it names (or names the admin host); nothing was '
                               'written.', details={'intent': str(pending[0])})
        drifted = ingress_checks(ctx, preflight)  # round 2, INTENT-4: before the reload, as the move checks before it
        if drifted:
            raise InstallError(baseline_problem(drifted, 'nothing was reloaded'), details={'baseline': drifted})
        tested = nginx_test()
        known = set(intent.get('nginx_warnings_before') or [])  # round 2, INTENT-9: the move's own baseline
        added = sorted(set(tested['warnings']) - known)
        if not tested['ok'] or added:
            raise InstallError(f'nginx -t on the files an interrupted ingress left failed or added warnings {added}; '
                               'nothing was reloaded.', details={'intent': pending[0].name})
        quillmd_back = quillmd_bytes(quillmd_vhost_bytes(), 'before')

        def recovery_undo():
            vhost_operation('decouple', expected_sha256=target_sha, content=base64.b64encode(saved).decode(),
                            quillmd_content=base64.b64encode(quillmd_back).decode())
        result = publish_vhost(ctx, lambda: None, recovery_undo, verify)
        return {**result, 'moved': True, 'recovered': True, 'already_installed': True, 'vhost_sha256': target_sha,
                'upstream_port': port, 'from': intent['from'], 'quillmd': quillmd_pins,
                'web': intent.get('web') or web, 'web_now': web,  # round 2, INTENT-6: the web the move found
                'coupling': found, 'intent': pending[0].name,
                'summary': f'an interrupted ingress ({pending[0].name}) completed: reloaded, verified and recorded; '
                           f'admin.quillmd.com served through {ctx.revision[:12]}\'s stage for {port}'}
    source_record = {'sha256': current, **source, 'b64': base64.b64encode(live).decode()}
    warnings_before = nginx_test()['warnings']  # recorded with the intent: a completion compares against these
    intent = write_intent(ctx, 'ingress', {'revision': ctx.revision, 'vhost_sha256': target_sha, 'upstream_port': port,
                                           'from': source_record, 'quillmd': quillmd_pins, 'web': web,
                                           'nginx_warnings_before': warnings_before})
    result = publish_vhost(ctx, apply, undo, verify)
    return {**result, 'moved': True, 'already_installed': False, 'vhost_sha256': target_sha, 'upstream_port': port,
            'from': source_record, 'intent': intent.name,
            'quillmd': quillmd_pins, 'web': web, 'coupling': found, 'admin_answers': answers,
            'summary': f'admin.quillmd.com moved onto quillmd-cpt ({ctx.revision[:12]}\'s stage for {port}, served by '
                       f'{str(web["revision"])[:12]}); the quillmd vhost is the after state'}


def caddy_notice() -> dict:
    """QuillMD's Caddy answering admin.quillmd.com directly (CADDY_ADDRESS, SNI admin.quillmd.com; its certificate is
    its own internal one, so not verified): a completed handshake and the answer it gives, by status and body sha256."""
    found = probe('https', ADMIN_HOST, '/', port=CADDY_ADDRESS[1], connect_ip=CADDY_ADDRESS[0], verify=False,
                  timeout=10, keep_body=True)
    return {**{key: found.get(key) for key in ('status', 'error', 'body_sha256')},
            'notice': QUILLMD_NOTICE_MARKER in (found.get('body') or b'')}


def missing_stage_certificates(raw: bytes) -> list:
    """The certificate files an HTTPS stage loads (ssl_certificate, ssl_certificate_key) that Let's Encrypt's live
    directory does not hold, read through le_state (refutation R2 round 1, CERT-5); [] for a stage that loads none."""
    paths = re.findall(r'^\s*ssl_certificate(?:_key)?\s+(\S+);', raw.decode('utf-8', 'replace'), re.M)
    if not paths:
        return []
    live = le_state()['live']
    missing = []
    for path in paths:
        match = re.fullmatch(r'/etc/letsencrypt/live/([^/]+)/([^/]+)', path)
        if not match or not (live.get(match[1]) or {}).get(match[2]):
            missing.append(path)
    return missing


def caddy_problem(caddy) -> str:
    """'' when QuillMD's Caddy answers admin.quillmd.com with a deliberate state - its maintenance notice (503 with
    QUILLMD_NOTICE_MARKER) or a 2xx or 3xx answer - else why giving admin back to it would serve an error (refutation R2
    round 1, COTENANT-3: a completed handshake alone let a Caddy 502 pass, and verify then compared 502 with 502; round 2,
    GUARDS-6: a 404 is an error page too)."""
    status = caddy.get('status')
    if caddy.get('error') or not status:
        return f'did not complete a handshake and answer ({caddy.get("error")})'
    if status == 503 and caddy.get('notice'):
        return ''
    if 200 <= status < 400:
        return ''
    return f'answered {status}' + (' without its maintenance notice' if status == 503 else '')


def phase_ingress_rollback(ctx) -> dict:
    """admin.quillmd.com's :443 given back to the quillmd vhost - QuillMD's Caddy notice - and quillmd-cpt given back
    the stage this revision's ingress replaced, byte for byte, from its receipt (ops/INSTALL.md, ingress-rollback;
    refutation INGRESS-2, INSTALLER-2, INGRESS-9): one root-helper operation, the quillmd vhost FIRST (decouple),
    validated together, reloaded once, verified; on any failure both are written forward again (couple, which accepts
    each partial state). It runs only while the web the ingress found serving - the revision its receipt recorded -
    serves again on the port the saved stage proxies to (before app, or after a switch-back to that revision), with
    this revision's HTTPS stage for that port live and the after state: the saved stage would otherwise send
    cpt.quillmd.com to a port nothing answers, so it refuses and names switch-back. Before it writes anything it
    completes a handshake with QuillMD's Caddy for admin.quillmd.com and reads its notice (caddy_notice); afterwards
    cpt.quillmd.com/health/ must answer that web's revision (a fresh host's saved HTTP stage: cpt's :443 routes like an
    unknown host again) and admin.quillmd.com, through nginx, the same notice with the quillmd.com lineage's
    certificate. On the before state with the saved stage live it verifies and changes nothing."""
    preflight = require_receipt(ctx, 'preflight')
    coupled_now = read_coupling()
    coupled = coupled_now['coupling']
    if coupled not in ('before', 'after'):  # round 2, GUARDS-1, INTENT-2: no switch-back or rerun can pass meanwhile
        raise InstallError(f'{coupling_problem(coupled_now)}; nothing was written. Recover that state first (ops/INSTALL.md, '
                           'Recovery notes): neither this phase, nor a switch-back, nor a rerun of ingress can pass while '
                           'it lasts.', details={'coupling': coupled_now})
    pending = unrecorded_ingress(ctx)
    if pending is not None and coupled == 'after':  # round 2, INTENT-3, INTENT-8, GUARDS-4: this revision's own first
        raise InstallError(f'An ingress of this revision changed the two files and stopped before it recorded the '
                           f'move ({pending[0].name}): run --phase ingress again first - it completes and records the '
                           'move with the stage that intent saved, or says how to make that stage live again - then '
                           'rerun this phase. Nothing was written.', details={'intent': str(pending[0])})
    entry = latest_ingress_move(ctx)
    newest = latest_ingress_move(ctx, any_revision=True)
    if newest is not None and (entry is None or newest[0] != entry[0]) and coupled != 'before':
        # the move to roll back was another revision's: its receipt holds the stage to give back, and only its installer
        # can switch back to the web it found serving (check, round R2-2); a later revision's web stands between, so the
        # way back runs through each revision's own switch-back first (refutation R2 round 1, WAYBACK-4)
        mover = str(newest[1].get('revision'))
        found_web = str(((newest[1].get('details') or {}).get('web') or {}).get('revision'))
        raise InstallError(f'admin.quillmd.com was moved by revision {mover[:12]}\'s --phase ingress ({newest[0].name}), '
                           'not by this revision\'s, and that receipt holds the stage to give back. The way back: switch '
                           'back revision by revision, newest first, each with its own installer (--phase switch-back), '
                           f'until {found_web[:12]} - the web that ingress found serving - serves; then run '
                           f'{mover[:12]}\'s --phase ingress-rollback from its act checkout. Nothing was written.',
                           details={'ingress_receipt': str(newest[0])})
    if entry is None:
        if coupled != 'before':
            raise InstallError(f'No successful --phase ingress receipt in {ctx.receipts} records a move of '
                               'admin.quillmd.com, yet the quillmd vhost and quillmd-cpt are not in the before state: '
                               'this installer cannot tell what to give back. Nothing was written.')
        raise InstallError(f'No successful --phase ingress receipt of this revision in {ctx.receipts} records a move of '
                           'admin.quillmd.com; nothing to roll back.')
    moved = entry[1]['details']
    saved = base64.b64decode(moved['from']['b64'])
    if sha256(saved) != moved['from']['sha256'] or names_host_on(saved.decode('utf-8', 'replace'), ADMIN_HOST):
        raise InstallError('The ingress receipt\'s saved stage is not the one it names (or names the admin host); '
                           'nothing was written.')
    saved_sha, saved_kind, recorded_web = sha256(saved), moved['from']['kind'], moved['web']['revision']
    state = vhost_state()
    if not state['file_exists'] or state['file_sha256'] is None or state['link_target'] != VHOST_LINK_TARGET:
        raise InstallError('quillmd-cpt is not the regular file and sites-enabled link this installer writes; nothing '
                           'was written.')
    found = read_coupling(vhost=state)
    web = running_web()
    saved_port = proxied_port(saved.decode('utf-8', 'replace')) if saved_kind == 'https' else None
    if web['revision'] != recorded_web:
        raise InstallError(f'ingress-rollback runs only while {str(recorded_web)[:12]}, the web this revision\'s ingress '
                           f'found serving, serves again; the running web is {str(web["revision"])[:12]} on '
                           f'{web["port"]}. Switch back to it first (--phase switch-back; revision by revision, newest '
                           'first, each with its own installer), then rerun. Nothing was written.')
    # the stage to give back: the saved one while that web serves on the port it proxies to; otherwise that revision's
    # own stage rendered for the port it serves on now - trusted only when this installer renders the saved stage byte
    # for byte (refutation R2 round 1, WAYBACK-3: an even number of app runs since the ingress leaves it on the other port)
    give_back, give_kind, rendered_for = saved, saved_kind, None
    if saved_kind == 'https' and web['port'] != saved_port:
        if web['port'] is None:
            raise InstallError(f'{SERVICES["web"]} publishes neither web port; nothing was written.')
        if rendered_vhosts(recorded_web, saved_port)['https'].encode() != saved:
            raise InstallError(f'{str(recorded_web)[:12]} serves on {web["port"]}, not on {saved_port} where the saved '
                               'stage proxies, and this installer does not render the saved stage byte for byte, so it '
                               f'cannot give back a stage for {web["port"]}. Nothing was written.')
        give_back, rendered_for = rendered_vhosts(recorded_web, web['port'])['https'].encode(), web['port']
        if names_host_on(give_back.decode('utf-8', 'replace'), ADMIN_HOST):
            raise InstallError(f'{str(recorded_web)[:12]}\'s stage for {web["port"]} names the admin host; nothing was '
                               'written.')
    give_sha = sha256(give_back)
    already = found['coupling'] == 'before' and state['file_sha256'] == give_sha
    missing = missing_stage_certificates(give_back)
    if missing:  # refutation R2 round 1, CERT-5: the way back loads the earlier lineage's files
        raise InstallError(f'The stage to give back loads {", ".join(missing)}, which is not present: re-issue that '
                           'lineage first, by hand (this installer\'s cert phase orders the cpt-studio lineage alone; '
                           'ops/INSTALL.md, Recovery notes), then rerun. Nothing was written.', details={'missing': missing})
    caddy = caddy_notice()
    problem = caddy_problem(caddy)
    if problem:
        raise InstallError(f'QuillMD\'s Caddy {problem} for {ADMIN_HOST} on {CADDY_ADDRESS[0]}:{CADDY_ADDRESS[1]}: '
                           'giving admin back to it would serve an error. Nothing was written.', details={'caddy': caddy})
    port = web['port']
    if not already:
        problem = coupling_problem(found, expected=('after',))
        if problem:
            raise InstallError(f'{problem}; nothing was written.', details={'coupling': found})
        if port is None or state['file_sha256'] != sha256(rendered_vhosts(ctx.revision, port)['https'].encode()):
            raise InstallError(f'quillmd-cpt is not this revision\'s HTTPS stage for {port}, the port the running web '
                               'publishes; nothing was written.')
        live = live_vhost_bytes()
        if live is None or sha256(live) != state['file_sha256']:
            raise InstallError('quillmd-cpt changed while it was being read; nothing was written.')
        quillmd_after = quillmd_vhost_bytes()
        quillmd_before = quillmd_bytes(quillmd_after, 'before')
        if sha256(quillmd_after) != QUILLMD_VHOST_AFTER:
            raise InstallError('The quillmd vhost changed while it was being read; nothing was written.')
        drifted = ingress_checks(ctx, preflight)
        if drifted:
            raise InstallError(baseline_problem(drifted, 'nothing was written'), details={'baseline': drifted})

    def apply():
        vhost_operation('decouple', expected_sha256=sha256(live), content=base64.b64encode(give_back).decode(),
                        quillmd_content=base64.b64encode(quillmd_before).decode())

    def undo():
        vhost_operation('couple', expected_sha256=give_sha, content=base64.b64encode(live).decode(),
                        quillmd_content=base64.b64encode(quillmd_after).decode())

    def verify():
        problems, evidence = [], {}
        if give_kind == 'https':
            served, observations = public_health(web['revision'])
            evidence['cpt'] = observations[-3:]
            if not served:
                problems.append(f'https://{DOMAIN}/health/ did not serve revision {str(web["revision"])[:12]}')
        else:  # a fresh host's HTTP stage: cpt's :443 is claimed by nothing again, as before the ingress
            cpt = probe('https', DOMAIN, '/', connect_ip='127.0.0.1', verify=False, method='HEAD')
            unmatched = probe('https', UNMATCHED_HOST, '/', connect_ip='127.0.0.1', verify=False, method='HEAD')
            evidence['cpt'] = {'cpt': cpt, 'unmatched': unmatched}
            if cpt.get('cert_sha256') != unmatched.get('cert_sha256'):
                problems.append(f'{DOMAIN} does not route like an unknown host on 443 again')

        def check():
            answer = probe('https', ADMIN_HOST, '/', timeout=5)
            same = (answer.get('status'), answer.get('body_sha256')) == (caddy['status'], caddy['body_sha256'])
            return same and 'quillmd.com' in (answer.get('cert_names') or []), {
                key: answer.get(key) for key in ('status', 'error', 'body_sha256', 'cert_names')}
        notice, observations = poll(check, attempts=30, interval=0.25)
        evidence['admin'] = observations[-3:]
        if not notice:
            problems.append(f'{ADMIN_HOST} did not answer QuillMD\'s Caddy notice with the quillmd.com certificate')
        problems += ingress_checks(ctx, preflight)
        problems += read_back_problems(QUILLMD_VHOST_BEFORE, give_sha)
        if problems:
            raise InstallError('; '.join(problems) + '.', details=evidence)
        return evidence
    record = {'vhost_sha256': give_sha, 'vhost_kind': give_kind, 'saved_sha256': saved_sha,
              'rendered_for_port': rendered_for, 'caddy': caddy, 'web': web,
              'ingress_receipt': entry[0].name, 'coupling': found}
    if already:
        tested = nginx_test()
        if not tested['ok']:
            raise InstallError('nginx -t does not pass on the files as they are; nothing was reloaded.')
        nginx_reload()  # files already given back; a run killed before its reload left nginx on the after state
        return {**verify(), **record, 'already_rolled_back': True, 'reloaded': True,
                'summary': 'admin.quillmd.com already answered by the quillmd vhost; verified, nothing written'}
    result = publish_vhost(ctx, apply, undo, verify)
    return {**result, **record, 'already_rolled_back': False,
            'quillmd': {'before': QUILLMD_VHOST_BEFORE, 'after': QUILLMD_VHOST_AFTER},
            'summary': f'admin.quillmd.com given back to the quillmd vhost (QuillMD\'s notice); quillmd-cpt is the stage '
                       f'the ingress replaced ({give_sha[:12]}{" re-rendered for " + str(rendered_for) if rendered_for else ""}), cpt.quillmd.com served by '
                       f'{str(web["revision"])[:12]}'}


def other_lineages(le: dict) -> tuple:
    """Let's Encrypt state without this installer's own lineages (CPT_LINEAGES: DOMAIN's, and cpt-studio, which both
    hosts are served with), on both sides of any comparison: a reinstall's preflight baseline already holds them, and
    the cert phase creates cpt-studio (refutation INSTALLER-3, INGRESS-7)."""
    own = {f'{name}.conf' for name in CPT_LINEAGES}
    return ({name: digest for name, digest in le['renewal'].items() if name not in own},
            set(le['live']) - set(CPT_LINEAGES))


def utc_moment(value):
    """An ISO 8601 date and time with its offset ('Z' or '+00:00') as an aware datetime; None otherwise."""
    try:
        moment = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None and moment.utcoffset() is not None else None


def phase_verify(ctx) -> dict:
    """Everything compared with the newest preflight receipt (ops/INSTALL.md, verify). After the ingress it accepts the
    coupled state, whichever side of the ingress that preflight was taken on (the act takes one after it, as the
    baseline app reads): quillmd-cpt this revision's HTTPS stage for the port the running web publishes, the quillmd
    vhost exactly the state that stage couples it to (the after state: it names admin.quillmd.com), every other file
    as the baseline recorded it; admin.quillmd.com's :443 judged by https_checks, not as a co-tenant; neither CPT
    lineage counted as another lineage; and both HTTP-01 routes proven (refutation INGRESS-7, INSTALLER-4)."""
    preflight = require_receipt(ctx, 'preflight')['details']
    image_id = installed_image(ctx)
    problems = []
    files = nginx_file_state()
    # quillmd-cpt must be this revision's HTTPS stage for the port the running web publishes (blue/green alternates it).
    try:
        port = live_web_port()
    except InstallError as error:
        port = None
        problems.append(str(error))
    stage = rendered_vhosts(ctx.revision, port or WEB_PORT)['https']
    coupled = QUILLMD_VHOST_AFTER if names_host_on(stage, ADMIN_HOST) else QUILLMD_VHOST_BEFORE
    if files['available'].get('quillmd') != coupled:
        problems.append(f'the quillmd vhost is not the {"after" if coupled == QUILLMD_VHOST_AFTER else "before"} state '
                        'this revision\'s stage couples it to')
    expected_available = {**preflight['nginx_files']['available'], 'quillmd': coupled,
                          VHOST_NAME: sha256(stage.encode())}
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
    db, db_evidence = inspect('container', DB_CONTAINER), None
    if db is None or db_container_problems(db, postgres.get('Id')) or not db['State'].get('Running'):
        problems.append(f'{DB_CONTAINER} is not the running, labelled, loopback-only database')
    else:
        # release 1 (A3, A5): its own cgroup allows no swap, and its log keeps no statement text
        db_evidence = {'cgroup': db_cgroup(), 'settings': db_settings_shown()}
        problems += [f'{DB_CONTAINER}: {problem}' for problem in db_cgroup_problems(db_evidence['cgroup'])]
        if db_evidence['settings'] != dict(DB_LOG_SETTINGS):
            problems.append(f'{DB_CONTAINER}: its statement logging reads {db_evidence["settings"] or "nothing"}, not '
                            f'{dict(DB_LOG_SETTINGS)} (run --phase db)')
    pair = {}
    for role, name in SERVICES.items():
        container = pair[role] = inspect('container', name)
        if container is None or not container['State'].get('Running'):
            problems.append(f'{name} is not running')
        else:
            problems += [f'{name}: {problem}' for problem in service_problems(
                container, role, image_id, port=port if role == 'web' else None)]
    # release 1 (A7): the converter of this revision runs sealed - no network, no secret, no files volume - and healthy
    converter = None
    if has_converter(ctx.revision):
        found = inspect('container', CONVERTER)
        converter = converter_state(found)
        problem = converter_problem(image_id, ctx.revision)
        problems += [problem] if problem else []
        if found is not None:
            problems += [f'{CONVERTER}: {each}' for each in service_problems(found, 'converter', image_id)]
    # What an app phase parks or starts beside the pair is gone once it succeeded.
    for name in (INCOMING_WEB, SERVICES['web'] + '-previous', SERVICES['worker'] + '-previous'):
        if inspect('container', name) is not None:
            problems.append(f'{name} is left beside the installed pair')
    https_problems, evidence = https_checks(ctx)
    problems += https_problems
    tls = tls_policy_report()  # A4: a finding, reported, never a failure of verify (D27)
    acme = {host: acme_probe(ctx, 'verify', host) for host in (DOMAIN, ADMIN_HOST)}
    problems += acme_problems(acme)
    foreign = foreign_uid_tasks(APP_UID, own_service_ids())
    if foreign:
        problems.append(f'uid {APP_UID} now runs {foreign} task(s) outside CPT Studio')
    appeared = sorted(set(now) - set(preflight['containers']) - {DB_CONTAINER, CONVERTER, *SERVICES.values()})
    details = {'evidence': evidence, 'acme': acme, 'containers_appeared_elsewhere': appeared, 'image_id': image_id,
               'web_port': port, 'database': db_evidence, 'converter': converter, 'tls_policy': tls}
    if problems:
        raise InstallError(f'verify found {len(problems)} difference(s): ' + '; '.join(problems) + '.',
                           details={**details, 'problems': problems})
    return {**details, 'summary': f'installed {ctx.revision[:12]} verified; co-tenants and app.quillmd.com unchanged'
                                  + (f'; TLS policy: {len(tls["findings"])} finding(s) (D27)' if tls['findings'] else '')}


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
    refusal, disposed = disposal_refusal(image_id, env, old_revision)  # refutation round 1, rollback-1 and rollback-2
    if refusal:
        raise InstallError(f'{refusal[:1].upper()}{refusal[1:]}; nothing was stopped or removed.',
                           details={'disposal': disposed})
    try:  # refutation round 2, sessions-2: decided before anything is stopped, from both revisions' trees
        ends_sessions = sessions_end_needed(ctx.revision, old_revision)
    except InstallError as error:
        raise InstallError(f'{error} Nothing was stopped or removed.') from error
    sessions = {}
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
        record['close_started_at'] = first_at.isoformat()  # refutation 6b-r2 F4: a close that raises may have committed
        record['stages_closed'] = first = close_undone_stages(image_id, env, since, ctx.revision, reason, kinds)
        shown, acting = hazards_by_kind(first.get('hazards'))
        if shown is None or shown or acting:
            named = (hazard_summary(merge_hazards(shown, acting)) if shown is not None
                     else 'the close did not say which encounters')
            # refutation 6b-r1 P2: this revision's web keeps serving, so the saves the close set back are put back
            message, outcome = (f'{cause}: after the close, {named} hold records an older revision would act on, or '
                                f'show, wrongly under its own rules, so nothing more was done: {keep_note(live, idle)}. '
                                'Clear them on this revision\'s web, then rerun --phase rollback-app.'
                                + kept_serving(image_id, env, [first], record)), 'kept'
        else:
            # this revision's worker is stopped, so this is what the old pair is handed: the declared note of what this
            # revision coded that is not carried back (coding_note)
            base = coding_note(image_id, env, ctx.revision)
            record['not_carried_back'] = with_update_note(base, [first])
            ended = None
            if ends_sessions:
                # refutation round 2, sessions-2: the old web reads its own rows again once it serves - a sign-in made
                # on it in the seconds of the switch to this revision that this revision could not end (its sign-out
                # everywhere reads only its own) - so every session is ended first, as a switch-back's B4 does before
                # B5; one that does not finish leaves this revision's web serving, never the old one over them
                record['sessions_ended'] = sessions
                try:
                    end_every_session(image_id, env, ctx.revision, old_revision, sessions)
                except Exception as error:  # noqa: BLE001 — an interrupt goes on to the handler below, which says it
                    ended = str(error) or type(error).__name__
            if ended is None:
                message, _, outcome = return_to_old_web(
                    ctx, cause, image_id=image_id, env_bytes=env, preflight=baseline, live=live, idle=idle,
                    old_revision=old_revision, previous=previous, parked_worker=parked, kinds=kinds, reason=reason,
                    first=first, first_at=first_at, details=record)
            else:
                message, outcome = (f'{cause}: the end of every session did not finish ({ended}), so nothing more was '
                                    f'done: {keep_note(live, idle)}. Rerun --phase rollback-app once it can end them.'
                                    + kept_serving(image_id, env, [first], record)), \
                    'kept'
            if record.get('stages_closed_after_drain') is not None:
                record['not_carried_back'] = with_update_note(base, [first, record['stages_closed_after_drain']])
            if outcome == 'kept':  # refutation 6b-r1 P2: the old web served nothing, so the note was handed to none
                record['not_carried_back'] = undone_note(base)
        record['availability'] = recorder.stop()  # inside: a Ctrl-C here fails the phase too (D-4)
    except BaseException as failure:
        # refutation 6b-r2 F4 (DECISIONS D247): a close that raised may have committed its revert first, and this
        # layout keeps this revision's web serving: the switch-back's clause names the rows since it started
        unanswered = record.get('close_started_at') and 'stages_closed' not in record
        raise InstallError(f'{cause}: {str(failure) or type(failure).__name__}; read "left" in this receipt, then '
                           'ops/INSTALL.md, Recovery notes.'
                           + (f' The close was started and gave no answer: it '
                              f'{possibly_set_back(record["close_started_at"])}.' if unanswered else '')
                           + sessions_ended_said(sessions),
                           details={**record, 'availability': stop_recorder(recorder),
                                    'left': left_summary()}) from failure
    if outcome != 'switched' or record.get('incoming_left'):
        raise InstallError(message + sessions_ended_said(sessions),
                           details={**record, 'outcome': outcome, 'left': left_summary()})
    availability = record['availability']
    note = (record.get('not_carried_back') or {}).get('note')
    return {**record, 'outcome': outcome, 'message': message,
            'summary': f'switched back to {old_revision[:12]} on {live} (the S4 keep layout): '
                       f'{availability.get("samples", 0)} availability samples, '
                       f'{availability.get("non_200_count", 0)} not 200; {removal_summary(record, keep)}; database, '
                       'volumes, images and secrets kept' + (f'; {note}' if note else '')
                       + sessions_summary(record.get('sessions_ended'))}


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
            # no worker of this revision runs in this layout, so this is what the old pair is handed (coding_note)
            base = record['not_carried_back'] = coding_note(image_id, env, ctx.revision)
            done = finish_back(ctx, image_id=image_id, env_bytes=env, idle=idle, previous=previous,
                               parked_worker=parked_of(parked_worker), kinds=kinds, reason=reason, since=since,
                               closes=[], details=record, worker=True,
                               hold=lambda every: undo_hold(every, same=False, strict=True,
                                                            window='the incoming web was created'))
            # design v2 (amendment 1, 9.4): the note with what the close after the drain did for the update
            if record.get('stages_closed_after_drain') is not None:
                record['not_carried_back'] = with_update_note(base, [record['stages_closed_after_drain']])
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
    note = (record.get('not_carried_back') or {}).get('note')
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
    removed. Refutation 6b-r2 F1 (DECISIONS D247): when that message has this pair started again (a record named after
    the close) or offers to keep this revision (a removal that failed), the saves the close set back are put back first
    (kept_serving), or, when that cannot run (an interrupt), named as not put back; a Ctrl-C while the put-back runs is
    recorded and said by kept_serving, so the receipt keeps the close's record of what each member saved (refutation
    w7r 6b-r1 R1), as it does for a close that raised or was interrupted. Refutation r2, L6-5: in the S4 'keep'
    layout (keep_layout) it acts on this revision's web and worker, with
    this revision's image, and switches back to the old web without interrupting the site (rollback_from_keep), and in
    the 'back' layout it finishes the way back (rollback_back; refutation r3, D-3); with a cpt-studio-web-next in any
    other layout, or a web and a worker of different images, it refuses, stopping nothing: which web serves, and whose
    records to read, cannot be told from the names. Refutation r3 (the recovery notes send undos here): it removes only
    this revision's own pair - a web or worker under the canonical names that carries another revision is refused,
    stopping nothing (it would stop the old web an undo had just put back in service). What this revision coded is
    never a reason to refuse: every arm that hands the rows to an older pair declares what is not carried back in its
    receipt ('not_carried_back': coding_note) and goes on. While admin.quillmd.com is moved (the coupling invariant's
    after state) it refuses, before stopping anything, to remove the pair quillmd-cpt proxies to: both hosts would be left
    on a port nothing answers (refutation R2 round 1, WAYBACK-1); in a coupling neither before nor after it refuses
    outright. The S4 'keep' layout's rollback is not this removal and is unaffected."""
    problem = coupling_problem(read_coupling()) or unrecorded_ingress_problem(ctx)  # round 2, REFUSALS-2: the keep arm too
    if problem:
        raise InstallError(f'{problem}; nothing was stopped or removed.')
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
    # refutation R2 round 1, WAYBACK-1: the routing refusal, after the pair is known to be this revision's own
    found = read_coupling()
    if found['coupling'] != 'before':
        live = live_vhost_bytes()
        served = proxied_port(live.decode('utf-8', 'replace')) if live is not None else None
        web = {'port': published_port(pair['web']) if 'web' in pair else None}  # running or stopped
        running = 'web' in pair and bool((pair['web'].get('State') or {}).get('Running'))
        if found['coupling'] != 'after' or served is None or (running and web['port'] == served):
            problem = coupling_problem(found, expected=('before',), remedy=AFTER_STATE_REMEDY)
            raise InstallError(f'{problem}; nothing was stopped. While admin.quillmd.com is moved, the pair quillmd-cpt '
                               f'proxies to ({served}) is never removed: keep it, or go back with --phase switch-back.',
                               details={'coupling': found, 'proxied_port': served, 'web_port': web['port']})
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
        # refutation round 1, rollback-1 and rollback-2: the pair that runs next is the parked one when one is parked,
        # else not known (an older revision installed afterwards) - neither may be handed closed practices or destroyed
        # documents without disposal
        parked_next = next((labels_of(container).get(REVISION_LABEL) for container in
                            (inspect('container', SERVICES[role] + '-previous') for role in ('worker', 'web'))
                            if container is not None), None)
        refusal, disposed = disposal_refusal(first['Image'], env, parked_next)
        if refusal:
            raise InstallError(f'{refusal[:1].upper()}{refusal[1:]}; nothing was stopped or removed.',
                               details={'disposal': disposed})
        # refutation round 2, sessions-2: so may neither be handed a session this revision could not end - a sign-in
        # made on an older web in the seconds of the switch to this revision, which its sign-out everywhere never
        # reads and the older web honours again - so every session is ended before the pair is removed, when the
        # parked pair has no session policy or none is parked (fail closed: the next is not known)
        try:
            ends_sessions = parked_next is None or sessions_end_needed(ctx.revision, parked_next)
        except InstallError as error:
            raise InstallError(f'{error} Nothing was stopped or removed.') from error
    sessions = {}
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
        try:  # refutation w7r 6b-r1 R4: a database that refuses here means the close never started - said so
            require_db()
        except InstallError as error:
            raise InstallError(f'Web and worker stopped, not removed: the stages they left open could not be closed '
                               f'({error}): the close was not started, so nothing was closed or set back. Rerun '
                               '--phase rollback-app once that is resolved.') from error
        started = utc_now_ms()  # refutation 6b-r2 F4: a close that raises may have committed its revert first
        try:
            closed = close_undone_stages(first['Image'], env,
                                         min(created_at(container) for container in pair.values()), revision,
                                         'its web and worker were removed (rollback-app)', kinds)
        except BaseException as error:  # noqa: BLE001 — refutation w7r 6b-r1 R1: a Ctrl-C there is said too
            raise InstallError(f'Web and worker stopped, not removed: '
                               f'{close_did_not_finish("the stages they left open", error)}; and it '
                               f'{possibly_set_back(started)}. Rerun --phase rollback-app once that is resolved.',
                               details={'close_started_at': started}) from error
        hazards = closed.get('hazards')
        if not isinstance(hazards, dict) or hazards:
            named = hazard_summary(hazards) if isinstance(hazards, dict) else 'the close did not say which encounters'
            left = {'hazards': hazards, 'stages_closed': closed}
            # refutation 6b-r2 F1 (DECISIONS D247): this message leaves this revision's pair to serve again (started
            # again to clear the records), so the saves the close set back are put back first, as kept_serving does
            # on every way that keeps this revision's web serving - or, when that cannot run, it names them
            raise InstallError(f'Web and worker stopped, not removed: after the close, {named} hold records an older '
                               'revision would act on, or show, wrongly under its own rules. Start them again '
                               f'(docker start {SERVICES["worker"]} {SERVICES["web"]}), clear them on this '
                               'revision\'s web (ops/INSTALL.md, Reinstalling an older revision), then rerun --phase '
                               'rollback-app.' + kept_serving(first['Image'], env, [closed], left), details=left)
        # Refutation p2, install2:1: the next pair - the parked one renamed back, or an older revision installed by its
        # own installer, which never recomputes a stored state - shows each state by its own labels, so a response
        # refused whole would read 'Provider request failed'. Each state this revision labels otherwise is given the
        # state that pair derives (the parked image's own derivation, else 057a7d39's), while this pair is stopped.
        try:
            put_back = put_back_states(closed, next_image, first['Image'], env)
        except BaseException as error:  # noqa: BLE001 — refutation w7r 6b-r1 R1's class: a Ctrl-C keeps the record too
            # the only way on is back to the older pair, which reads the saves the close set back as set back: they
            # stay so, and the message says it (refutation 6b-r2 F2: what is so)
            raise InstallError(f'Web and worker stopped, not removed: the list states an older revision labels '
                               f'otherwise could not be put back ({str(error) or type(error).__name__}). Rerun --phase '
                               'rollback-app once that is resolved.' + set_back_clause([closed]),
                               details={'stages_closed': closed}) from error
        # the pair is stopped, so this is what the next pair is handed - the declared note of what this revision coded
        # that is not carried back (coding_note), never a refusal
        try:
            base = coding_note(first['Image'], env, revision)
        except BaseException as error:  # noqa: BLE001 — it answers every failure itself; an interrupt keeps the record
            changed = (put_back or {}).get('changed') or {}
            raise InstallError(f'Web and worker stopped, not removed: the count of what this revision coded was '
                               f'interrupted ({str(error) or type(error).__name__})'
                               + (f', after the list states of {len(changed)} encounter(s) were put back to what the '
                                  'older revision derives' if changed else '')
                               + '. Rerun --phase rollback-app.' + set_back_clause([closed]),
                               details={'stages_closed': closed, 'states_put_back': put_back}) from error
        made = with_update_note(base, [closed])
        if ends_sessions:  # the pair is stopped and nothing else serves: no sign-in can follow the end
            try:
                end_every_session(first['Image'], env, ctx.revision, parked_next, sessions)
            except BaseException as error:  # noqa: BLE001 — an interrupt is said too; nothing is removed
                raise InstallError(f'Web and worker stopped, not removed: the end of every session did not finish '
                                   f'({str(error) or type(error).__name__}), and no earlier pair may serve over '
                                   'the sessions it would honour again. Rerun --phase rollback-app once it can end '
                                   'them.' + sessions_ended_said(sessions) + set_back_clause([closed]),
                                   details={'stages_closed': closed, 'states_put_back': put_back,
                                            'not_carried_back': made, 'sessions_ended': sessions}) from error
    else:
        made = None
    removed = {}
    try:
        for role in ('worker', 'web'):
            name = SERVICES[role]
            removed[name] = role in pair
            remove_service_container(name, role)
    except BaseException as error:  # noqa: BLE001 — states were put back for the older revision: the receipt says so
        changed = (put_back or {}).get('changed')
        parts = _undo_parts([closed]) if closed is not None else None
        if not changed and not (closed is not None and (parts is None or parts[1])):
            if sessions.get('started_at'):  # refutation round 2, sessions-2: the receipt says they were ended
                ended_record = {'stages_closed': closed, 'not_carried_back': made, 'sessions_ended': sessions}
                if not isinstance(error, Exception):
                    error.details = ended_record
                    raise
                raise InstallError(f'{str(error) or type(error).__name__}: rerun --phase rollback-app.'
                                   + sessions_ended_said(sessions), details=ended_record) from error
            raise
        details = {'stages_closed': closed, 'states_put_back': put_back, 'not_carried_back': made,
                   **sessions_ended_of(sessions)}
        states = (f'; before it, the list states of {len(changed)} encounter(s) were put back to what the older '
                  'revision derives, which this revision labels otherwise' if changed else '')
        # refutation 6b-r2 F1 (DECISIONS D247): the message offers to keep this revision, so the saves the close set
        # back are put back first; an interrupt runs nothing more, and the message names them as not put back. Once
        # any is put back, no earlier pair was handed them, so the note carries none of its members' instructions
        if isinstance(error, Exception):
            said = kept_serving(first['Image'], env, [closed], details)
        else:
            said = not_put_back([closed], 'the phase was interrupted before they could be')
        if (details.get('reapplied') or {}).get('reapplied'):
            details['not_carried_back'] = undone_note(base, kept='the removal of this revision\'s pair stopped before '
                                                               'any earlier pair was started, and the saves the close '
                                                               'set back were put back (reapplied)')
        raise InstallError(f'{str(error) or type(error).__name__}{states}: rerun --phase rollback-app; or, to keep '
                           'this revision, rerun --phase app' + (', which recomputes them' if changed else '') + '.'
                           + said + sessions_ended_said(sessions), details=details) from error
    parked = [name + '-previous' for name in SERVICES.values() if inspect('container', name + '-previous')]
    return {'removed': removed, 'stages_closed': closed, 'states_put_back': put_back, 'parked_left_in_place': parked,
            'not_carried_back': made, **sessions_ended_of(sessions),
            'summary': 'web and worker removed after closing their open stages; database, volumes, images and '
                       'secrets kept' + (f'; {made["note"]}' if made else '') + sessions_summary(sessions)}


def recorded_vhosts(ctx) -> dict:
    """sha256 -> (revision, kind) of every vhost stage an earlier successful phase installed, any revision: the vhost
    phases' stages, the HTTPS stage a blue/green app or switch-back phase switched the upstream to, the stage an ingress
    wrote and the stage an ingress-rollback put back (its 'vhost_kind': the HTTP stage of a fresh host, else HTTPS;
    refutation INSTALLER-11). The revision is the one whose phase wrote it."""
    found = {}
    for phase, kind, field in (('http-vhost', 'http', None), ('https-vhost', 'https', None),
                               ('app', 'https', 'switch'), ('switch-back', 'https', 'switch'),
                               ('ingress', 'https', None), ('ingress-rollback', None, None)):
        for path in sorted(ctx.receipts.glob(f'{phase}-*.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            details = record.get('details') or {}
            digest = ((details.get(field) or {}).get('vhost_sha_after') if field else details.get('vhost_sha256'))
            stage_kind = kind or details.get('vhost_kind')
            if (record.get('phase') == phase and record.get('ok') and isinstance(digest, str)
                    and re.fullmatch(r'[0-9a-f]{64}', digest) and SHA_RE.fullmatch(str(record.get('revision')))
                    and stage_kind in ('http', 'https')):
                found.setdefault(digest, (record['revision'], stage_kind))
    return found


def phase_rollback_vhost(ctx) -> dict:
    """Remove quillmd-cpt when it holds a stage this installer wrote: this revision's, or one an earlier
    successful vhost receipt recorded. The removal is undone with the exact bytes it removed, re-rendered from the
    revision that installed them. Only in the before state of the coupling invariant: while quillmd-cpt claims
    admin.quillmd.com's :443 (the after state) a removal would leave nothing claiming it - admin would fall to a
    co-tenant's default server and certificate - so it refuses and names ingress-rollback (refutation INSTALLER-1,
    INGRESS-3)."""
    preflight = require_receipt(ctx, 'preflight')
    state = vhost_state()
    found = read_coupling(vhost=state)
    problem = coupling_problem(found, expected=('before',), remedy=AFTER_STATE_REMEDY)
    if problem:
        raise InstallError(f'{problem}; nothing was removed.', details={'coupling': found})
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
    'converter': phase_converter, 'app': phase_app, 'reference': phase_reference, 'passages': phase_passages, 'license-note': phase_license_note,
    'provision': phase_provision, 'operators': phase_operators, 'manage': phase_manage,
    'http-vhost': phase_http_vhost, 'cert': phase_cert, 'https-vhost': phase_https_vhost, 'ingress': phase_ingress,
    'verify': phase_verify, 'switch-back': phase_switch_back, 'rollback-app': phase_rollback_app,
    'rollback-vhost': phase_rollback_vhost, 'ingress-rollback': phase_ingress_rollback,
}


class Interrupted(BaseException):
    """A SIGTERM or SIGHUP - the door's `timeout -k 15` at its ceiling, a closed terminal - raised where the phase is, so
    every finally and __exit__ runs (RAM files wiped, a one-shot removed, an undo) and the receipt says so (refutation,
    installer lens A-3a). Python's default ends the process without either."""


def interrupt(signum, frame):
    # later ones are ignored while the cleanup runs (the door's SIGKILL follows 15 s after its SIGTERM)
    for each in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(each, signal.SIG_IGN)
    if SIGNALS_HELD['depth']:  # inside signals_deferred: acted on once its body has finished
        SIGNALS_HELD['pending'] = SIGNALS_HELD['pending'] or signal.Signals(signum).name
        return
    raise Interrupted(signal.Signals(signum).name)


# What signals_deferred holds: how deep its bodies run, and the first signal that landed in one (its name).
SIGNALS_HELD = {'depth': 0, 'pending': None}


class signals_deferred:  # noqa: N801 - used as a context manager, as contextlib's are
    """A body no signal stops half way (refutation round 1, installer-3: a RAM folder's wipe): a SIGTERM or SIGHUP that
    lands in it (interrupt, main's handler) is raised as Interrupted once the outermost such body has finished, and a
    Ctrl-C as KeyboardInterrupt (when Python's own handler was the one in place) - the first that landed, chained to
    whatever the body raised, which it replaces. The door's SIGKILL, 15 s after its SIGTERM, cannot be held."""

    def __enter__(self):
        self.outermost, self.handler = SIGNALS_HELD['depth'] == 0, None
        SIGNALS_HELD['depth'] += 1
        if self.outermost:
            try:  # the main thread alone can set a handler; anywhere else a Ctrl-C is not held
                if signal.getsignal(signal.SIGINT) is signal.default_int_handler:
                    self.handler = signal.signal(signal.SIGINT, held_ctrl_c)
            except ValueError:
                self.handler = None
        return self

    def __exit__(self, kind, error, trace):
        SIGNALS_HELD['depth'] -= 1
        if not self.outermost:
            return False
        if self.handler is not None:
            signal.signal(signal.SIGINT, self.handler)
        pending, SIGNALS_HELD['pending'] = SIGNALS_HELD['pending'], None
        if pending == 'SIGINT':
            raise KeyboardInterrupt() from error
        if pending:
            raise Interrupted(pending) from error
        return False


def held_ctrl_c(signum, frame):
    """A Ctrl-C inside signals_deferred: held, as interrupt holds a SIGTERM there."""
    SIGNALS_HELD['pending'] = SIGNALS_HELD['pending'] or 'SIGINT'


def rewrite_receipt(path: Path, record: dict) -> Path:
    """``path`` replaced in one step (a temporary file, then rename) by ``record``."""
    data = (json.dumps(record, indent=2, sort_keys=True) + '\n').encode()
    temporary = write_private(path.parent, f'.{path.name}.tmp', data)
    os.replace(temporary, path)
    return path


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
    journal_begin(args.phase)
    handlers = {each: signal.signal(each, interrupt) for each in (signal.SIGTERM, signal.SIGHUP)}
    try:
        # refutation round 2, installer-2: an option given twice is refused before anything runs, the receipt naming it
        repeated = repeated_options(sys.argv[1:] if argv is None else list(argv), args)
        if repeated:
            raise InstallError(f'{", ".join(repeated)} given more than once: the installer would run with the last '
                               'value of each and drop the others without a word, so nothing was run. Give each option '
                               'once.', details={'given_more_than_once': repeated})
        record['door'] = check_door(os.environ, args.revision)
        ctx.door = record['door']
        journal_begin(args.phase, record['door'])
        record['door']['ceiling'] = check_door_ceiling(os.environ, args.phase)
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
    except Interrupted as error:  # the phase's cleanup has run; the receipt says what stopped it
        record.update(ok=False, interrupted=str(error), error=f'interrupted by {error} before the phase finished',
                      **({'details': error.details} if getattr(error, 'details', None) is not None else {}))
        code = 128 + getattr(signal, str(error), signal.SIGTERM)
    except KeyboardInterrupt as error:  # an act that ran keeps its record (raise_after_act) beside the interrupt
        record.update(ok=False, interrupted='SIGINT', error='interrupted (Ctrl-C) before the phase finished',
                      **({'details': error.details} if getattr(error, 'details', None) is not None else {}))
        raise
    finally:
        record.setdefault('ok', False)
        record['finished_at'] = utc_now()
        # the receipt first (refutation, rollback lens B-10): a second Ctrl-C or a SIGTERM while the journal's
        # helper runs below must never cost a finished phase its receipt, which the next phase reads
        record['oneshot_log'] = {'written': False, 'why': 'pending: the receipt is written before the journal'}
        path = write_receipt(receipts, args.phase, record)
        try:
            record['oneshot_log'] = flush_journal()  # A13: one line per one-shot and helper run, root-only
        except BaseException as error:  # noqa: BLE001 — the receipt stands; this one says why the journal did not
            record['oneshot_log'] = {'written': False,
                                     'why': f'interrupted while it was written ({type(error).__name__})'}
        try:
            rewrite_receipt(path, record)
        except BaseException:  # noqa: BLE001 — the receipt written above stands, its journal said pending
            pass
        for each, handler in handlers.items():
            signal.signal(each, handler)
        summary = (record.get('details') or {}).get('summary') if record['ok'] else record.get('error')
        print(json.dumps({'phase': args.phase, 'ok': record['ok'], 'summary': summary, 'receipt': str(path)}))
    return code


if __name__ == '__main__':
    sys.exit(main())
