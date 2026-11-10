#!/usr/bin/env python3
"""D15: the rollback runtime test of the Gemini migration, run before the install on a TEST instance (design/FINAL.md
12.3, as design/ADJUDICATION.md P-1 amends it). Synthetic data only; nothing here ever reaches the live host.

    python3 -B cpt-studio/ops/rollback_check.py --db cptg_d15 --candidate cpt-studio-test:<sha12> \\
        --previous cpt-studio:<sha12> --port 9173 --out <new directory> --since 2026-11-10T13:19:00+00:00 \\
        --renderer <the legacy-parity directory holding parity_render.py> --db-env-file <0600 env file> \\
        --member-credentials <json> --operator-credentials <json> [--declared <json>]

The question: if the candidate is installed and the site is then switched back to the image it replaced, does the
previous image read everything the candidate wrote, fail closed, and never come out LESS held? The runner answers it on a
copy of the data, in this order:

  1. the established switch-back's own in-image scripts, imported from the CANDIDATE revision's ops/install.py (read
     with `git show`, so a later edit of the working tree changes nothing) and run as its app_script runs them - one
     `manage shell -c` one-shot per script, the prelude with P and ANSWER, the one ANSWER line read - with only the
     transport swapped for a one-shot on the test database: the hazard read the switch-back refuses on, the stage
     kinds of the previous worker (UNRUNNABLE_STAGES, in the PREVIOUS image), the close (CLOSE_STAGES, in the CANDIDATE
     image), the list states put back (RECOMPUTE_STATES for the close's 'relabel', in the PREVIOUS image) and the
     declared note (INTERPRETATION_MADE, P-1). The installer's own functions build every parameter and read every
     answer (close_undone_stages, stage_kinds_of, put_back_states, interpretation_note, undo_hazards);
  2. the candidate's and the previous image's view of every encounter, rendered on the same rows by the legacy-parity
     renderer (parity_render.py; one transaction rolled back, the same frozen instant), each with its own
     RECOMPUTE_STATES run and rolled back;
  3. the declared RECOMPUTE_STATES change set (from the previous image's own derivation, written down before the
     script is applied), then the previous revision's RECOMPUTE_STATES applied on a COPY of the database;
  4. the previous image's web on 127.0.0.1:--port, then its worker - started only once no stage it cannot run is left
     open - and over HTTP: the session, the list and every encounter's detail as a member and as an operator, the
     downloads of every report the candidate made on a new-path encounter, a draft and an approved export and both
     operator reports made by the previous web, the probes of Resume on every new-path encounter, and one Resume of a
     stage the previous web stopped (--resume names the encounter);
  5. the six assertions (FINAL 12.3, as P-1 amends the fifth), each with its evidence, in --out/d15.json and a short
     --out/D15-SUMMARY.txt.

Refused before anything runs: a web port of the live blue/green pair (9150, 9151), the live database port (55451) or
container, a database not named cptg_*, or an --out that exists. Every container it starts is named cptg-d15-*, logs
nothing (--log-driver=none), publishes on the loopback only, and is stopped and removed before it returns. No password,
cookie or token is printed or written: the credentials files are read when signing in and the database env file is passed
to Docker on stdin.

The comparison is pure and unit-tested (ops/test_rollback_check.py, no Docker and no database): held_move, compare_rows,
compare_encounter, note_problems, marker_problems, recompute_problems, declared_changes and target_problems.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import datetime as dt
import hashlib
import http.client
import json
import re
import secrets
import subprocess
import sys
import time
import types
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

SCHEMA = 'cpt-studio-d15-rollback@1'
WORKTREE = Path(__file__).resolve().parents[2]
INSTALLER_PATH = 'cpt-studio/ops/install.py'
CLIENT_CONTRACT_PATH = 'cpt-studio/studio/client_contract.py'
REVISION_LABEL = 'org.opencontainers.image.revision'
REFUSED_WEB_PORTS = (9150, 9151)  # the live web's blue/green ports (install.WEB_PORTS)
LIVE_DB_PORT = 55451  # the live database (install.DB_PORT)
LIVE_CONTAINERS = ('cpt-studio-web', 'cpt-studio-web-next', 'cpt-studio-worker', 'cpt-studio-db')
TEST_DB = re.compile(r'cptg_[a-z0-9_]{1,40}')
NAME = 'cptg-d15'
APP_UID = 10150
MODES_DISABLED = ('-e', 'CPT_STUDIO_PROVIDER_MODE=disabled', '-e', 'CPT_STUDIO_ASTRA_MODE=disabled',
                  '-e', 'CPT_STUDIO_FABLE_MODE=disabled', '-e', 'CPT_STUDIO_GEMINI_MODE=disabled')
READ_ONLY_SESSION = ('-e', 'PGOPTIONS=-c default_transaction_read_only=on')
SESSION_COOKIE, CSRF_COOKIE, CSRF_FIELD = 'cptstudio_session', 'cptstudio_csrf', 'csrfmiddlewaretoken'

# --- what "held" means (pure) -------------------------------------------------------------------------------------------
# Lower releases more. A code the customer page shows approved is released; ready waits on a reviewer; needs_detail waits
# on a detail; excluded is not offered for approval at all. A state that releases nothing (processing, failed, stopped,
# being confirmed) shares the top rank HELD: a move between two of them is a move between held states.
HELD = 3
PROPOSAL_HELD = {'approved': 0, 'ready': 1, 'needs_detail': 2, 'excluded': HELD}  # customer_api._status
MEMBER_STATUS_HELD = {'ready': 1, 'needs_clarification': 2, 'excluded': HELD, 'informational': HELD}  # Proposal.status
CUSTOMER_STATE_HELD = {'reviewed': 0, 'no_codes': 0, 'ready': 1, 'awaiting_detail': 2, 'action_needed': 2,
                       'being_confirmed': HELD, 'processing': HELD, 'stopped': HELD, 'failed': HELD}
STORED_STATE_HELD = {'reviewed': 0, 'no_codes': 0, 'ready_for_review': 1, 'needs_clarification': 2,
                     'provider_unknown': HELD, 'processing': HELD, 'stopped': HELD, 'extraction_failed': HELD,
                     'processing_failed': HELD, 'provider_not_run': HELD, 'provider_failed': HELD}
ACCEPTED_MOVES = ('same', 'toward_held', 'held_to_held')
# Boolean offers an encounter payload carries: True after where False before is an action the candidate did not allow.
CUSTOMER_OFFERS = (('readiness', 'draft'), ('readiness', 'approved'), ('recheck', 'available'),
                   ('recheck', 'can_request'), ('progress', 'can_resume'), ('progress', 'can_stop'))
MEMBER_OFFERS = (('readiness', 'draft'), ('readiness', 'reviewed'))


def held_move(ranks: dict, before, after) -> str:
    """How ``after`` stands to ``before`` on ``ranks``: 'same'; 'toward_held' (it releases less); 'held_to_held' (two
    states that release nothing); 'lateral' (another state of the same rank that releases something - a different
    meaning, never accepted); 'toward_release'; or 'unknown' (a state ``ranks`` does not know, never accepted)."""
    if before == after:
        return 'same'
    if before not in ranks or after not in ranks:
        return 'unknown'
    if ranks[after] > ranks[before]:
        return 'toward_held'
    if ranks[after] < ranks[before]:
        return 'toward_release'
    return 'held_to_held' if ranks[after] == HELD else 'lateral'


def compare_rows(before_rows, after_rows, ranks: dict, *, where: str) -> list:
    """Per proposal (rows keyed by 'id'): the previous image's status must equal the candidate's or be more held, and
    it may allow no action the candidate did not allow. A row only one side lists is a finding: one the previous
    image does not list cannot be compared, and one only it lists is an offer the candidate did not make."""
    findings = []
    before = {str(row.get('id')): row for row in before_rows or () if isinstance(row, dict)}
    after = {str(row.get('id')): row for row in after_rows or () if isinstance(row, dict)}
    for pk in sorted(set(before) | set(after)):
        b, a = before.get(pk), after.get(pk)
        base = {'where': where, 'proposal': pk, 'code': (b or a).get('code'),
                'before': b.get('status') if b else None, 'after': a.get('status') if a else None}
        if a is None:
            findings.append({**base, 'finding': 'not_listed_after'})
            continue
        if b is None:
            findings.append({**base, 'finding': 'listed_only_after', 'actions': sorted(a.get('allowed_actions') or ())})
            continue
        move = held_move(ranks, b.get('status'), a.get('status'))
        if move not in ACCEPTED_MOVES:
            findings.append({**base, 'finding': move})
        new = sorted(set(a.get('allowed_actions') or ()) - set(b.get('allowed_actions') or ()))
        if new:
            findings.append({**base, 'finding': 'action_not_allowed_before', 'actions': new})
    return findings


def _flag(payload, path) -> bool:
    value = payload
    for part in path:
        value = value.get(part) if isinstance(value, dict) else None
    return value is True


def _offers(before, after, offers, where) -> list:
    return [{'where': where, 'finding': 'offer_not_made_before', 'offer': '.'.join(path)}
            for path in offers if _flag(after, path) and not _flag(before, path)]


def is_error(value) -> bool:
    return isinstance(value, dict) and '__error__' in value


def compare_encounter(before: dict, after: dict) -> dict:
    """{'findings', 'errors', 'compared'}: one encounter's views as parity_render.py wrote them, the candidate's
    (``before``) against the previous image's (``after``), over what a reader can act on - every membership's customer
    detail (the encounter's state, each code's status and allowed actions, the export, re-check, Resume and Stop
    offers), every member's and the operator's detail (each proposal's status and allowed actions, the readiness), the
    list rows, the derived list state and the review readiness. A view that raised in either image is an error."""
    findings, errors, compared = [], [], 0
    for name in sorted(set(before) | set(after)):
        for side, doc in (('before', before), ('after', after)):
            if is_error(doc.get(name)):
                errors.append({'view': name, 'side': side, 'error': doc[name]['__error__'][:300]})
    for name in sorted(set(before) & set(after)):
        b, a = before[name], after[name]
        if is_error(b) or is_error(a) or not isinstance(b, dict) or not isinstance(a, dict):
            continue
        if name.startswith('customer.detail['):
            compared += 1
            move = held_move(CUSTOMER_STATE_HELD, b.get('state'), a.get('state'))
            if move not in ACCEPTED_MOVES:
                findings.append({'where': name, 'finding': f'state_{move}', 'before': b.get('state'),
                                 'after': a.get('state')})
            findings += _offers(b, a, CUSTOMER_OFFERS, name)
            findings += compare_rows(b.get('codes'), a.get('codes'), PROPOSAL_HELD, where=name)
        elif name.startswith('member.detail[') or name == 'operator.detail':
            compared += 1
            findings += _offers(b, a, MEMBER_OFFERS, name)
            findings += compare_rows((b.get('assessment') or {}).get('proposals'),
                                     (a.get('assessment') or {}).get('proposals'), MEMBER_STATUS_HELD, where=name)
        elif name == 'list.customer_row':
            move = held_move(CUSTOMER_STATE_HELD, b.get('state'), a.get('state'))
            if move not in ACCEPTED_MOVES:
                findings.append({'where': name, 'finding': f'state_{move}', 'before': b.get('state'),
                                 'after': a.get('state')})
        elif name == 'state':
            move = held_move(STORED_STATE_HELD, b.get('derived'), a.get('derived'))
            if move not in ACCEPTED_MOVES:
                findings.append({'where': 'state.derived', 'finding': move, 'before': b.get('derived'),
                                 'after': a.get('derived')})
        elif name == 'readiness':
            review_b, review_a = b.get('review') or {}, a.get('review') or {}
            if review_a.get('reviewed') is True and review_b.get('reviewed') is not True:
                findings.append({'where': 'readiness.review', 'finding': 'offer_not_made_before',
                                 'offer': 'reviewed'})
            findings += _offers(b.get('customer') or {}, a.get('customer') or {},
                                (('draft',), ('approved',)), 'readiness.customer')
    return {'findings': findings, 'errors': errors, 'compared': compared}


def declared_changes(states: dict) -> dict:
    """The RECOMPUTE_STATES change set to declare before it is applied: {encounter: [stored, derived]} for every
    encounter whose stored list state differs from the previous image's own derivation (``states``: {encounter: the
    'state' view the previous image rendered})."""
    return {pk: [view.get('stored'), view.get('derived')] for pk, view in sorted(states.items())
            if isinstance(view, dict) and not is_error(view) and view.get('stored') != view.get('derived')}


def recompute_problems(read_only, applied, declared: dict, new_path) -> list:
    """Assertion 3: the read-only run and the applied run (each RECOMPUTE_STATES's answer) both change exactly the
    declared set, and every new-path encounter it changes moves toward held."""
    problems = []
    for label, answer in (('read_only', read_only), ('applied', applied)):
        changed = answer.get('changed') if isinstance(answer, dict) else None
        if not isinstance(changed, dict):
            problems.append(f'{label}: no change set was answered')
            continue
        if {pk: list(pair) for pk, pair in changed.items()} != declared:
            problems.append(f'{label}: changed {sorted(changed)} is not the declared {sorted(declared)}')
        for pk, pair in sorted(changed.items()):
            if pk in set(new_path):
                move = held_move(STORED_STATE_HELD, pair[0], pair[1])
                if move not in ('toward_held', 'held_to_held'):
                    problems.append(f'{label}: new-path encounter {pk} moved {pair[0]} -> {pair[1]} ({move})')
    return problems


def note_problems(note, independent: dict, declared=None) -> list:
    """Assertion 5: the switch-back's note (interpretation_note) counted what it read, and names exactly the new-path
    encounters - the same encounters, context-only encounters and assessment count as the set computed independently
    over the tables (``independent``) and, when given, as the set the test instance was built with (``declared``)."""
    if not isinstance(note, dict) or not isinstance(note.get('encounters'), list):
        return ['the note did not count what it read']
    problems = []
    named = {'encounters': sorted(note['encounters']), 'context_only': sorted(note.get('context_only') or ()),
             'assessments': note.get('assessments')}
    for label, other in (('independent', independent), ('declared', declared)):
        if other is None:
            continue
        for key in ('encounters', 'context_only'):
            want = sorted(other.get(key) or ())
            if named[key] != want:
                problems.append(f'{key}: the note names {named[key]}, the {label} set {want}')
        if 'assessments' in other and other['assessments'] != named['assessments']:
            problems.append(f'assessments: the note counts {named["assessments"]}, the {label} count '
                            f'{other["assessments"]}')
    if not isinstance(note.get('note'), str) or 'not counted' in note['note']:
        problems.append('the note sentence says it did not count')
    return problems


def marker_problems(items) -> list:
    """Assertion 4: every approved export the candidate made reads the same marker digest in both images, is current
    in both alike, and the previous web's download answers it as current (200 with the stored bytes) or stale (409)."""
    problems = []
    if not items:
        problems.append('no approved export made by the candidate was checked')
    for item in items or ():
        pk = item.get('id')
        before, after, download = item.get('before') or {}, item.get('after') or {}, item.get('download') or {}
        if before.get('not_rendered') or after.get('not_rendered'):
            problems.append(f'{pk}: its encounter was not rendered by both images')
            continue
        if not before.get('marker_digest') or before.get('marker_digest') != after.get('marker_digest'):
            problems.append(f'{pk}: marker digest {before.get("marker_digest")} != {after.get("marker_digest")}')
        if before.get('current') != after.get('current'):
            problems.append(f'{pk}: current {before.get("current")} before, {after.get("current")} after')
        want = 200 if after.get('current') else 409
        if download.get('status') != want:
            problems.append(f'{pk}: the download answered {download.get("status")}, not {want}')
        if download.get('status') == 200 and download.get('sha256') != item.get('stored_sha256'):
            problems.append(f'{pk}: the downloaded bytes are not the stored bytes')
    return problems


def target_problems(port, pg_port, pg_container, db) -> list:
    """Why this target is not a test instance this check may write to ([] when it is)."""
    problems = []
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        problems.append(f'the web port {port!r} is not a port above 1023')
    elif port in REFUSED_WEB_PORTS:
        problems.append(f'port {port} is a port of the live web')
    if pg_port == LIVE_DB_PORT or str(pg_port) == str(LIVE_DB_PORT):
        problems.append(f'port {pg_port} is the live database')
    if pg_container in LIVE_CONTAINERS:
        problems.append(f'{pg_container} is a live container')
    if not (isinstance(db, str) and TEST_DB.fullmatch(db)):
        problems.append(f'{db!r} is not a test database (cptg_*)')
    return problems


def pg_time(value):
    """A timestamp as psql prints one (2026-11-10 14:18:11.803978+00) or as ISO, as an aware datetime; None if not."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace(' ', 'T', 1)
    if re.search(r'[+-]\d\d$', text):
        text += ':00'
    try:
        moment = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def settled_before(rows, started_at) -> bool:
    """Assertion 6: among the interpret stages read when the previous worker started ([id, state, finished_at, error]),
    at least one was closed by the installer (failed, its error the close's note) and finished before ``started_at``,
    and none is queued or running."""
    start = pg_time(started_at)
    rows = [row for row in rows or () if isinstance(row, (list, tuple)) and len(row) >= 4]
    if start is None or any(row[1] in ('queued', 'running') for row in rows):
        return False
    return any(row[1] == 'failed' and str(row[3] or '').startswith('Closed by the installer')
               and pg_time(row[2]) is not None and pg_time(row[2]) < start for row in rows)


def assertion(number, title, problems, evidence) -> dict:
    return {'assertion': number, 'title': title, 'result': 'PASS' if not problems else 'FAIL',
            'problems': problems, 'evidence': evidence}


# --- the test instance (Docker and the test PostgreSQL) -------------------------------------------------------------

class Refused(Exception):
    """A precondition failed before anything was written."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def git_show(revision: str, path: str) -> str:
    return subprocess.run(['git', '-C', str(WORKTREE), 'show', f'{revision}:{path}'], capture_output=True,
                          check=True).stdout.decode('utf-8')


def load_installer(revision: str):
    """ops/install.py of ``revision`` as a module (its definitions only: the file runs nothing at import), read with
    `git show` so the working tree's later edits change nothing."""
    name = f'install_{revision[:12]}'
    module = types.ModuleType(name)
    module.__file__ = str(WORKTREE / INSTALLER_PATH)
    sys.modules[name] = module
    exec(compile(git_show(revision, INSTALLER_PATH), f'{revision[:12]}:{INSTALLER_PATH}', 'exec'),  # noqa: S102
         module.__dict__)
    return module


def literal(revision: str, path: str, name: str):
    """A module-level string assignment of ``path`` at ``revision``, read without running the file."""
    import ast
    for node in ast.parse(git_show(revision, path)).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name):
            return ast.literal_eval(node.value)
    raise Refused(f'{path} at {revision[:12]} has no {name}')


class Instance:
    """One test database on the test PostgreSQL, and the one-shots, pair and SQL this check runs against it."""

    def __init__(self, *, db, pg_container, pg_port, env_bytes, files_volume, log):
        self.db, self.pg_container, self.pg_port = db, pg_container, int(pg_port)
        self.env_bytes, self.files_volume, self.log = env_bytes, files_volume, log
        self.db_user = self._env_value('CPT_STUDIO_DB_USER')
        self.calls = []
        self.started = []

    def _env_value(self, key):
        for line in self.env_bytes.decode('utf-8').splitlines():
            if line.startswith(f'{key}='):
                return line.split('=', 1)[1]
        raise Refused(f'the database env file names no {key}')

    # SQL, on the test PostgreSQL only (psql in its own container)
    def sql(self, statement, *, db=None, write=False) -> list:
        argv = ['docker', 'exec', '-i']
        if not write:
            argv += ['-e', 'PGOPTIONS=-c default_transaction_read_only=on']
        argv += [self.pg_container, 'psql', '-X', '-q', '-At', '-F', '\t', '-v', 'ON_ERROR_STOP=1',
                 '-U', self.db_user, '-d', db or self.db, '-c', statement]
        done = subprocess.run(argv, capture_output=True, timeout=300)
        if done.returncode:
            raise RuntimeError(f'psql failed: {done.stderr.decode("utf-8", "replace")[-400:]}')
        return [line.split('\t') for line in done.stdout.decode('utf-8').splitlines()]

    def copy_database(self, source, target):
        if not TEST_DB.fullmatch(target) or self.sql(f"select count(*) from pg_database where datname = '{target}'",
                                                     db=source)[0][0] != '0':
            raise Refused(f'{target} is not a new test database name')
        subprocess.run(['docker', 'exec', self.pg_container, 'createdb', '-U', self.db_user, '-T', source, target],
                       check=True, capture_output=True, timeout=300)

    def common(self, db, *, network_host=True):
        """The hardening of testinst/manage.sh's one-shots, the database settings on stdin's env file."""
        args = ['--pull=never', '--log-driver=none', '--user', f'{APP_UID}:{APP_UID}', '--read-only', '--tmpfs', '/tmp',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '2048m', '--pids-limit', '256',
                '--label', 'cptg-test=1', '--env-file', '/dev/stdin', '-e', f'CPT_STUDIO_DB_NAME={db}', *MODES_DISABLED]
        if network_host:
            args += ['--network', 'host', '-e', 'CPT_STUDIO_DB_HOST=127.0.0.1', '-e', f'CPT_STUDIO_DB_PORT={self.pg_port}']
        return args

    def oneshot(self, image, command, *, what, db=None, read_only=False, mounts=(), env=(), timeout=900):
        name = f'{NAME}-oneshot-{secrets.token_hex(4)}'
        argv = ['docker', 'run', '--rm', '--name', name, '--no-healthcheck', *self.common(db or self.db)]
        if read_only:
            argv += list(READ_ONLY_SESSION)
        for mount in mounts:
            argv += ['--mount', mount]
        for item in env:
            argv += ['-e', item]
        started = time.monotonic()
        try:
            done = subprocess.run([*argv, image, *command], input=self.env_bytes, capture_output=True, timeout=timeout)
        finally:
            subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=60)
        self.calls.append({'what': what, 'image': image[:19], 'db': db or self.db, 'read_only_session': read_only,
                           'exit': done.returncode, 'seconds': round(time.monotonic() - started, 1)})
        return done

    def app_script(self, installer, image, body, params, *, what, db=None, read_only=False, timeout=900):
        """``body`` run as the installer's app_script runs it (APP_SCRIPT_PRELUDE with P and ANSWER, then the body,
        by `manage shell -c`), in a one-shot of ``image`` on the test database; the one ANSWER line's JSON."""
        payload = base64.b64encode(json.dumps(params).encode()).decode()
        source = installer.APP_SCRIPT_PRELUDE.format(payload=payload, answer=installer.APP_SCRIPT_ANSWER) + body
        done = self.oneshot(image, ['manage', 'shell', '-c', source], what=what, db=db, read_only=read_only,
                            timeout=timeout)
        answers = [line for line in done.stdout.decode('utf-8', 'replace').splitlines()
                   if line.startswith(installer.APP_SCRIPT_ANSWER)]
        if done.returncode or len(answers) != 1:
            tail = done.stderr.decode('utf-8', 'replace')[-1500:]
            self.calls[-1]['error'] = tail
            raise installer.InstallError(f'{what} failed (exit {done.returncode}).', output=tail.encode())
        answer = json.loads(answers[0][len(installer.APP_SCRIPT_ANSWER):])
        self.calls[-1]['answer'] = answer
        return answer

    def transport(self, installer, images: dict):
        """A stand-in for ``installer.app_script`` with the installer's own signature: the image id it is given is run
        as a one-shot on the test database (``images`` maps each image id this check runs to the tag it names)."""
        def app_script(image_id, env_bytes, body, params, *, what, timeout=180, mounts=(), user=None):  # noqa: ARG001
            if image_id not in images:
                raise Refused(f'{what}: {image_id} is not an image of this check')
            return self.app_script(installer, image_id, body, params, what=what, timeout=max(timeout, 900))
        return app_script

    # the previous image's web and worker (testinst/stack.sh's pair)
    def pg_bridge_ip(self):
        out = subprocess.run(['docker', 'inspect', self.pg_container, '--format',
                              '{{.NetworkSettings.Networks.bridge.IPAddress}}'], capture_output=True, check=True)
        ip = out.stdout.decode().strip()
        if not re.fullmatch(r'[0-9.]{7,15}', ip):
            raise Refused(f'{self.pg_container} has no bridge address')
        return ip

    def start(self, role, image, port):
        name = f'{NAME}-{role}-{port}'
        args = ['--pull=never', '--log-driver=none', '--user', f'{APP_UID}:{APP_UID}', '--read-only', '--tmpfs', '/tmp',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '1536m', '--pids-limit', '256',
                '--label', 'cptg-test=1', '--mount', f'type=volume,src={self.files_volume},dst=/var/lib/cpt-studio',
                '--env-file', '/dev/stdin', '-e', f'CPT_STUDIO_DB_NAME={self.db}',
                '-e', f'CPT_STUDIO_DB_HOST={self.pg_bridge_ip()}', '-e', 'CPT_STUDIO_DB_PORT=5432', *MODES_DISABLED]
        if role == 'web':
            args += ['-p', f'127.0.0.1:{port}:8000']
        done = subprocess.run(['docker', 'run', '-d', '--name', name, *args, image, role], input=self.env_bytes,
                              capture_output=True, timeout=120)
        if done.returncode:
            raise RuntimeError(f'{name} did not start: {done.stderr.decode("utf-8", "replace")[-300:]}')
        self.started.append(name)
        self.log(f'started {name} ({image[:19]})')
        return name

    def present_originals(self, image) -> tuple:
        """({encounter: True} for each stored original the test file volume holds, [encounters whose original it does
        not hold]): a restored dump brings the rows, never the live volume's files, so a legacy encounter's original
        is absent here by construction and its download is not a test of the switch-back."""
        rows = self.sql('select encounter_id, storage_name from studio_sourcefile')  # '<workspace>/<name>'
        listing = subprocess.run(['docker', 'run', '--rm', '--name', f'{NAME}-files-{secrets.token_hex(4)}',
                                  '--pull=never', '--network', 'none', '--log-driver=none', '--user', f'{APP_UID}:{APP_UID}',
                                  '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                                  '--entrypoint', '/bin/sh', '--mount',
                                  f'type=volume,src={self.files_volume},dst=/var/lib/cpt-studio,readonly', image, '-c',
                                  'cd /var/lib/cpt-studio/originals 2>/dev/null && find . -type f'],
                                 capture_output=True, timeout=120)
        held = {line[2:] for line in listing.stdout.decode('utf-8', 'replace').splitlines() if line.startswith('./')}
        present = {pk for pk, name in rows if name in held}
        return present, sorted({pk for pk, _ in rows} - present)

    def inspect(self, name) -> dict:
        out = subprocess.run(['docker', 'inspect', name, '--format',
                              '{{json .State}} {{.RestartCount}} {{.Image}}'], capture_output=True)
        if out.returncode:
            return {'present': False}
        state, restarts, image = out.stdout.decode().strip().rsplit(' ', 2)
        state = json.loads(state)
        return {'present': True, 'running': state.get('Running'), 'exit_code': state.get('ExitCode'),
                'oom_killed': state.get('OOMKilled'), 'started_at': state.get('StartedAt'),
                'restarts': int(restarts), 'image': image[:19]}

    def stop_all(self):
        stopped = []
        for name in reversed(self.started):
            subprocess.run(['docker', 'stop', '-t', '30', name], capture_output=True, timeout=120)
            subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=60)
            stopped.append(name)
        self.started = []
        return stopped


def wait_health(port, seconds=90) -> int:
    status = None
    for _ in range(seconds):
        try:
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            connection.request('GET', '/health/')
            status = connection.getresponse().status
            connection.close()
            if status == 200:
                return status
        except OSError:
            pass
        time.sleep(1)
    return status


# --- HTTP, as a member and as an operator ------------------------------------------------------------------------------

class Browser:
    """One signed-in account on the previous web (127.0.0.1:port): cookies kept, no redirect followed, every request
    recorded by method, path, status, size and - for a download - the sha256 of its bytes; never a password, cookie or
    token. A request that cannot complete is recorded with status None."""

    def __init__(self, port, who, client):
        self.port, self.who, self.client = port, who, client
        self.cookies, self.requests = {}, []

    def _send(self, method, path, body=None, headers=None):
        sent = {'Host': f'127.0.0.1:{self.port}', 'User-Agent': 'cpt-studio-rollback-check/1 (D15, synthetic)'}
        if self.cookies:
            sent['Cookie'] = '; '.join(f'{name}={value}' for name, value in sorted(self.cookies.items()))
        sent.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=300)
        try:
            connection.request(method, path, body=body, headers=sent)
            response = connection.getresponse()
            data = response.read()
            for value in response.headers.get_all('Set-Cookie') or ():
                jar = SimpleCookie()
                try:
                    jar.load(value)
                except CookieError:
                    continue
                for name, morsel in jar.items():
                    if morsel.value in ('', '""') or morsel['max-age'] == '0':
                        self.cookies.pop(name, None)
                    else:
                        self.cookies[name] = morsel.value
            return response.status, response.getheader('Location'), data
        except OSError as exc:
            return None, None, str(exc).encode()
        finally:
            connection.close()

    def login(self, credentials_path) -> dict:
        status, _, page = self._send('GET', '/login/')
        match = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page or b'')
        self.requests.append({'who': self.who, 'method': 'GET', 'path': '/login/', 'status': status})
        if status != 200 or match is None:
            return {'signed_in': False, 'form': status}
        credentials = json.loads(Path(credentials_path).read_text(encoding='utf-8'))
        form = urlencode({CSRF_FIELD: match.group(1).decode(), 'username': credentials.get('username', ''),
                          'password': credentials.get('password', ''), 'next': '/'}).encode()
        username = credentials.get('username')
        del credentials
        status, location, _ = self._send('POST', '/login/', form,
                                         {'Content-Type': 'application/x-www-form-urlencoded'})
        del form
        self.requests.append({'who': self.who, 'method': 'POST', 'path': '/login/', 'status': status,
                              'location': location})
        return {'signed_in': status == 302 and SESSION_COOKIE in self.cookies, 'username': username,
                'redirect': location}

    def call(self, method, path, payload=None, *, label=None, contract=True, download=False):
        headers = {'Accept': 'application/json'}
        if contract:
            headers[self.client[0]] = self.client[1]
        body = None
        if method == 'POST':
            headers['X-CSRFToken'] = self.cookies.get(CSRF_COOKIE, '')
            headers['Content-Type'] = 'application/json'
            body = json.dumps(payload or {}).encode()
        status, _, data = self._send(method, path, body, headers)
        row = {'who': self.who, 'method': method, 'path': label or path, 'status': status, 'bytes': len(data or b'')}
        if download:
            row['sha256'] = hashlib.sha256(data or b'').hexdigest()
        self.requests.append(row)
        parsed = None
        if not download and data:
            try:
                parsed = json.loads(data)
            except ValueError:
                parsed = None
        return status, parsed, row

    def logout(self):
        status, location, _ = self._send('POST', '/logout/', b'', {'X-CSRFToken': self.cookies.get(CSRF_COOKIE, ''),
                                                                  'Content-Type': 'application/x-www-form-urlencoded'})
        self.requests.append({'who': self.who, 'method': 'POST', 'path': '/logout/', 'status': status,
                              'location': location})


# --- the run ----------------------------------------------------------------------------------------------------------

# RECOMPUTE_STATES as the previous image runs it, inside a transaction that is rolled back: its answer, nothing kept.
ROLLED_BACK = '''
from django.db import transaction as _d15_transaction
with _d15_transaction.atomic():
    exec(compile({body!r}, 'RECOMPUTE_STATES', 'exec'))
    _d15_transaction.set_rollback(True)
'''
RENDER = "exec(open('/rec/parity_render.py').read())"


def image_info(tag: str) -> dict:
    out = subprocess.run(['docker', 'image', 'inspect', tag, '--format',
                          '{{.Id}} {{index .Config.Labels "' + REVISION_LABEL + '"}}'], capture_output=True)
    if out.returncode:
        raise Refused(f'no image {tag}')
    image_id, revision = out.stdout.decode().split()
    if not (re.fullmatch(r'sha256:[0-9a-f]{64}', image_id) and re.fullmatch(r'[0-9a-f]{40}', revision)):
        raise Refused(f'{tag} carries no revision label')
    return {'tag': tag, 'id': image_id, 'revision': revision}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def independent_new_path(instance) -> dict:
    """The new-path encounters read by SQL over the tables, never through an image or the installer: those with an
    assessment made from an event inventory, and those holding a context derived from one but no such assessment."""
    rows = instance.sql("select encounter_id, (event_inventory_id is not null)::int, "
                        "(engine_version like 'cpt-studio-events@%')::int from studio_assessment "
                        "where event_inventory_id is not null or engine_version like 'cpt-studio-events@%'")
    holding = {row[0] for row in instance.sql(
        "select distinct encounter_id from studio_encountercontext "
        "where event_inventory_id is not null or version like 'gemini-context@%'")}
    assessed = {row[0] for row in rows}
    return {'assessments': len(rows), 'encounters': sorted(assessed | holding),
            'context_only': sorted(holding - assessed),
            'assessments_label_without_inventory': sum(1 for row in rows if row[1] != row[2])}


def open_stages(instance, kinds) -> dict:
    """What the previous worker would meet: interpret stages queued or running, and every stage of a kind it does not
    run that is queued, running, or cancelled as the latest of its revision (UNRUNNABLE_STAGES' rule, read by SQL)."""
    known = ','.join(f"'{kind}'" for kind in sorted(kinds))
    interpret = instance.sql("select id, state from studio_job where kind = 'interpret' and state in ('queued', 'running')")
    unknown = instance.sql(
        f"select j.id, j.kind, j.state from studio_job j join studio_encounter e on e.id = j.encounter_id "
        f"where j.kind not in ({known}) and (j.state in ('queued', 'running') or (j.state = 'cancelled' "
        f"and e.current_revision_id = j.revision_id and j.id = (select k.id from studio_job k where "
        f"k.revision_id = j.revision_id order by k.created_at desc, k.id desc limit 1)))")
    return {'interpret_open': [row[0] for row in interpret], 'unrunnable_open': [row[:3] for row in unknown]}


def load_views(directory: Path) -> tuple:
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    views = {path.stem: json.loads(path.read_text(encoding='utf-8'))
             for path in sorted((directory / 'encounters').glob('*.json'))}
    return manifest, views


def render_summary(manifest) -> dict:
    meta = manifest.get('meta') or {}
    return {'release': (meta.get('release') or '')[:12], 'leaf': meta.get('studio_leaf'),
            'encounters': meta.get('encounters'), 'seconds': meta.get('seconds'), 'errors': manifest.get('errors'),
            'render_writes': len(manifest.get('render_writes') or ()), 'integrity': manifest.get('integrity'),
            'recompute': manifest.get('recompute')}


class Check:
    """One D15 run (see the module docstring)."""

    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.lines = []
        self.record = {'schema': SCHEMA, 'label': 'D15', 'started_at': utc_now()}

    def log(self, line):
        line = f'{utc_now()} {line}'
        self.lines.append(line)
        print(line, flush=True)

    def write(self):
        self.record['log'] = self.lines
        (self.out / 'd15.json').write_text(json.dumps(self.record, indent=1, sort_keys=True, default=str) + '\n',
                                            encoding='utf-8')

    # 0. what is checked
    def prepare(self):
        args = self.args
        problems = target_problems(args.port, args.pg_port, args.pg_container, args.db)
        if problems:
            raise Refused('; '.join(problems))
        if self.out.exists():
            raise Refused(f'{self.out} exists')
        env_file = Path(args.db_env_file)
        if env_file.stat().st_mode & 0o077:
            raise Refused('the database env file must not be readable by others (0600)')
        for path in (args.member_credentials, args.operator_credentials):
            if Path(path).stat().st_mode & 0o077:
                raise Refused(f'{path} must not be readable by others (0600)')
        if not (Path(args.renderer) / 'parity_render.py').is_file():
            raise Refused('--renderer holds no parity_render.py')
        self.candidate, self.previous = image_info(args.candidate), image_info(args.previous)
        self.since = dt.datetime.fromisoformat(args.since)
        if self.since.tzinfo is None:
            raise Refused('--since needs a UTC offset')
        self.out.mkdir(parents=True)
        (self.out / 'inputs').mkdir()
        self.instance = Instance(db=args.db, pg_container=args.pg_container, pg_port=args.pg_port,
                                 env_bytes=env_file.read_bytes(), files_volume=args.files_volume or f'cptg-files-{args.db}',
                                 log=self.log)
        if self.instance.sql('select 1') != [['1']]:
            raise Refused(f'{args.db} cannot be read')
        # the installer that would run the switch-back is the candidate's own; the previous revision's RECOMPUTE_STATES
        # is what an install of the previous revision runs (its app phase), read from its own ops/install.py
        self.installer = load_installer(self.candidate['revision'])
        self.recompute_previous = literal(self.previous['revision'], INSTALLER_PATH, 'RECOMPUTE_STATES')
        self.recompute_candidate = literal(self.candidate['revision'], INSTALLER_PATH, 'RECOMPUTE_STATES')
        self.client = (literal(self.previous['revision'], CLIENT_CONTRACT_PATH, 'HEADER'),
                       literal(self.previous['revision'], CLIENT_CONTRACT_PATH, 'VERSION'))
        self.declared = json.loads(Path(args.declared).read_text(encoding='utf-8')) if args.declared else None
        self.record.update(
            instance={'db': args.db, 'pg_container': args.pg_container, 'pg_port': args.pg_port, 'port': args.port,
                      'files_volume': self.instance.files_volume, 'since': self.since.isoformat()},
            images={'candidate': self.candidate, 'previous': self.previous},
            installer={'revision': self.candidate['revision'],
                       'scripts_sha256': {name: sha(getattr(self.installer, name)) for name in (
                           'UNDO_HAZARDS_READ', 'CLOSE_STAGES', 'UNRUNNABLE_STAGES', 'RECOMPUTE_STATES',
                           'INTERPRETATION_MADE', 'APP_SCRIPT_PRELUDE')},
                       'previous_recompute_sha256': sha(self.recompute_previous),
                       'recompute_identical_in_both_revisions': self.recompute_previous == self.recompute_candidate},
            declared=self.declared)
        self.log(f'D15 on {args.db}: candidate {args.candidate} ({self.candidate["revision"][:12]}), previous '
                 f'{args.previous} ({self.previous["revision"][:12]}), since {self.since.isoformat()}')

    def census(self):
        tables = ('studio_encounter', 'studio_assessment', 'studio_encountercontext', 'studio_job',
                  'studio_providerrun', 'studio_decision', 'studio_reportartifact', 'studio_eventinventory',
                  'studio_interpreterhold', 'studio_memberanswer')
        rows = self.instance.sql(' union all '.join(f"select '{t}', count(*) from {t}" for t in tables))
        states = self.instance.sql('select state, count(*) from studio_job group by 1 order by 1')
        return {'rows': {name: int(count) for name, count in rows}, 'job_states': {s: int(n) for s, n in states}}

    # 1. the switch-back, as the candidate's installer runs it (P-1)
    def switch_back(self):
        inst, installer = self.instance, self.installer
        cand, prev = self.candidate, self.previous
        images = {cand['id']: cand['tag'], prev['id']: prev['tag']}
        record = self.record.setdefault('switch_back', {})
        record['census_before'] = self.census()
        with mock.patch.object(installer, 'app_script', inst.transport(installer, images)):
            # phase_switch_back's first check: any hazard refuses before anything is started or stopped
            record['precheck_hazards'] = installer.undo_hazards(cand['id'], inst.env_bytes, cand['revision'])
            record['note_before_close'] = installer.interpretation_note(cand['id'], inst.env_bytes, cand['revision'])
            calls = len(inst.calls)
            kinds = installer.stage_kinds_of(prev['id'], inst.env_bytes)
            record['kinds'] = {'previous_worker_runs': kinds,
                               'read_from_previous_image': len(inst.calls) > calls and inst.calls[-1]['exit'] == 0}
            record['open_before_close'] = open_stages(inst, kinds)
            reason = f'revision {cand["revision"][:12]} was switched back to {prev["revision"][:12]} (switch-back)'
            record['close_started_at'] = utc_now()
            close = installer.close_undone_stages(cand['id'], inst.env_bytes, self.since, cand['revision'], reason, kinds)
            record['close'] = close
            record['closed_stages'] = inst.sql(
                "select id, kind, encounter_id, left(error, 60) from studio_job where error like 'Closed by the installer:%' "
                f"and finished_at >= '{record['close_started_at']}' order by kind, id")
            record['put_back'] = installer.put_back_states(close, prev['id'], cand['id'], inst.env_bytes)
            # read as the switch-back reads it: after the close, in this revision's own image
            record['note'] = installer.interpretation_note(cand['id'], inst.env_bytes, cand['revision'])
        record['independent'] = independent_new_path(inst)
        record['open_after_close'] = open_stages(inst, kinds)
        stuck = inst.app_script(installer, prev['id'], installer.UNRUNNABLE_STAGES, {}, read_only=True,
                                what='UNRUNNABLE_STAGES after the close (previous image)')
        record['unrunnable_after_close'] = stuck
        hazards = record['precheck_hazards'] or {}
        record['refusals'] = {
            'precheck (install.py phase_switch_back: any hazard refuses)': bool(hazards),
            'after the close (switch_back_services refuse_on_hazards)': bool((close or {}).get('hazards')),
            'interpretation named as a refusing reason': any(
                'interpretation' in reasons for reasons in list(hazards.values())
                + list(((close or {}).get('hazards') or {}).values()))}
        new_path = set(record['independent']['encounters'])
        record['precheck_hazards_by_class'] = {
            'new_path': {pk: reasons for pk, reasons in hazards.items() if pk in new_path},
            'legacy': {pk: reasons for pk, reasons in hazards.items() if pk not in new_path}}
        self.new_path = sorted(new_path)
        self.kinds = kinds
        record['census_after'] = self.census()
        self.log(f'switch-back: precheck hazards {len(hazards)}, closed {close.get("closed")} stage(s) of kinds '
                 f'{close.get("kinds")}, relabel {len(close.get("relabel") or ())}, note: {record["note"].get("note")}')

    # 2. the two views, on the same rows
    def renders(self):
        inst, args = self.instance, self.args
        inputs = self.out / 'inputs'
        prelude = self.installer.APP_SCRIPT_PRELUDE.format(
            payload=base64.b64encode(json.dumps({}).encode()).decode(), answer=self.installer.APP_SCRIPT_ANSWER)
        (inputs / 'recompute-candidate.py').write_text(prelude + self.recompute_candidate, encoding='utf-8')
        (inputs / 'recompute-previous.py').write_text(prelude + self.recompute_previous, encoding='utf-8')
        for path in inputs.iterdir():
            path.chmod(0o644)
        inputs.chmod(0o755)
        self.freeze = utc_now()
        jobs = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for role, image, snippet in (('before', self.candidate, 'recompute-candidate.py'),
                                         ('after', self.previous, 'recompute-previous.py')):
                out = self.out / f'out-{role}'
                out.mkdir()
                out.chmod(0o777)
                params = json.dumps({'role': role, 'freeze': self.freeze, 'recompute': f'/inputs/{snippet}',
                                     'answer_prefix': self.installer.APP_SCRIPT_ANSWER, 'only': list(args.only or ()),
                                     'configured': False})
                jobs[role] = pool.submit(
                    inst.oneshot, image['id'], ['manage', 'shell', '-c', RENDER], what=f'render {role} ({image["tag"]})',
                    mounts=(f'type=bind,src={Path(args.renderer).resolve()},dst=/rec,readonly',
                            f'type=bind,src={inputs.resolve()},dst=/inputs,readonly',
                            f'type=bind,src={out.resolve()},dst=/out'),
                    env=('PYTHONHASHSEED=0', f'PARITY_PARAMS={params}'), timeout=5400)
            done = {role: job.result() for role, job in jobs.items()}
        record = self.record.setdefault('renders', {'freeze': self.freeze})
        self.views = {}
        for role, result in done.items():
            line = [x for x in result.stdout.decode('utf-8', 'replace').splitlines() if x.startswith('PARITY-RENDER')]
            record[role] = {'exit': result.returncode, 'line': line[-1] if line else None}
            if result.returncode == 0:
                manifest, views = load_views(self.out / f'out-{role}')
                record[role].update(render_summary(manifest))
                self.views[role] = views
            else:
                record[role]['stderr'] = result.stderr.decode('utf-8', 'replace')[-1500:]
        self.log(f'renders: before {record["before"].get("line")}; after {record["after"].get("line")}')

    def compare(self):
        before, after = self.views.get('before') or {}, self.views.get('after') or {}
        per, findings, errors = {}, [], []
        for pk in sorted(set(before) | set(after)):
            if pk not in before or pk not in after:
                errors.append({'encounter': pk, 'error': 'rendered by one image only'})
                continue
            result = compare_encounter(before[pk], after[pk])
            per[pk] = {'new_path': pk in self.new_path, 'compared': result['compared'],
                       'findings': len(result['findings']), 'errors': len(result['errors'])}
            findings += [{'encounter': pk, 'new_path': pk in self.new_path, **item} for item in result['findings']]
            errors += [{'encounter': pk, **item} for item in result['errors']]
        self.record['comparison'] = {'encounters': len(per), 'new_path': sum(1 for v in per.values() if v['new_path']),
                                     'findings': findings, 'errors': errors, 'per_encounter': per}
        self.log(f'compared {len(per)} encounters: {len(findings)} finding(s), {len(errors)} error(s)')

    # 3. RECOMPUTE_STATES: declared, read-only, applied on a copy
    def recompute(self):
        inst = self.instance
        states = {pk: views.get('state') for pk, views in (self.views.get('after') or {}).items()}
        declared = declared_changes(states)
        record = self.record.setdefault('recompute', {})
        record['declared'] = declared
        record['declared_at'] = utc_now()
        (self.out / 'declared-recompute.json').write_text(json.dumps({'declared_at': record['declared_at'],
                                                                      'changed': declared}, indent=1), encoding='utf-8')
        after = (self.record['renders'].get('after') or {}).get('recompute') or {}
        record['read_only'] = {'answer': after.get('answer'), 'rolled_back_statements': len(
            after.get('rolled_back_statements') or ()), 'error': after.get('error')}
        copy = f'{self.args.db}_rc'[:46]
        inst.copy_database(self.args.db, copy)
        record['copy'] = copy
        applied = inst.app_script(self.installer, self.previous['id'], self.recompute_previous, {}, db=copy,
                                  what='RECOMPUTE_STATES applied on the copy (previous image, previous revision)')
        record['applied'] = applied
        changed = sorted((applied or {}).get('changed') or {})
        if changed:
            rows = inst.sql('select id, state from studio_encounter where id in ('
                            + ','.join(f"'{pk}'" for pk in changed) + ')', db=copy)
            record['copy_states'] = {pk: state for pk, state in rows}
        record['problems'] = recompute_problems(record['read_only']['answer'], applied, declared, self.new_path)
        if record.get('copy_states') is not None:
            record['problems'] += [f'the copy holds {state} for {pk}, not {applied["changed"][pk][1]}'
                                   for pk, state in record['copy_states'].items() if state != applied['changed'][pk][1]]
        self.log(f'RECOMPUTE_STATES: declared {len(declared)}, read-only changed '
                 f'{len((record["read_only"]["answer"] or {}).get("changed") or {})}, applied changed {len(changed)}')

    # 4. the previous image's web and worker, over HTTP
    def http(self):
        inst, args = self.instance, self.args
        record = self.record.setdefault('http', {})
        inst.start('web', self.previous['id'], args.port)
        record['health'] = wait_health(args.port)
        member, operator = Browser(args.port, 'member', self.client), Browser(args.port, 'operator', self.client)
        record['member_login'] = member.login(args.member_credentials)
        record['operator_login'] = operator.login(args.operator_credentials)
        everyone = [row[0] for row in inst.sql('select id from studio_encounter order by created_at, id')]
        member.call('GET', '/api/session')
        member.call('GET', '/api/encounters')
        operator.call('GET', '/ops/api/session')
        operator.call('GET', '/ops/api/encounters')
        for pk in everyone:
            member.call('GET', f'/api/encounters/{pk}')
            operator.call('GET', f'/ops/api/encounters/{pk}')
            operator.call('GET', f'/ops/api/encounters/{pk}/trace')
        new_path = self.new_path
        made = inst.sql("select id, encounter_id, audience, kind, fmt, sha256 from studio_reportartifact where "
                        f"generated_at >= '{self.since.isoformat()}' and encounter_id in ("
                        + ','.join(f"'{pk}'" for pk in new_path) + ') order by generated_at, id') if new_path else []
        downloads = {}
        for pk, encounter, audience, kind, fmt, stored in made:
            who, path = ((member, f'/api/reports/{pk}/download') if audience == 'customer'
                         else (operator, f'/ops/api/reports/{pk}/download'))
            status, _, row = who.call('GET', path, contract=False, download=True)
            downloads[pk] = {'encounter': encounter, 'audience': audience, 'kind': kind, 'fmt': fmt,
                             'status': status, 'sha256': row.get('sha256'), 'stored_sha256': stored}
        record['candidate_reports'] = downloads
        created = []
        files, absent = inst.present_originals(self.previous['id'])
        record['originals_absent_from_test_volume'] = absent
        for pk in new_path:
            for kind in ('draft', 'approved'):
                for fmt in ('txt', 'csv'):
                    status, body, _ = member.call('POST', f'/api/encounters/{pk}/reports', {'kind': kind, 'fmt': fmt})
                    item = {'encounter': pk, 'audience': 'customer', 'kind': kind, 'fmt': fmt, 'status': status}
                    if status == 201 and isinstance(body, dict) and body.get('download_url'):
                        got, _, row = member.call('GET', body['download_url'], contract=False, download=True)
                        item.update(download=got, sha256=row.get('sha256'))
                    created.append(item)
            for kind in ('draft', 'reviewed'):
                for fmt in ('txt', 'csv'):
                    status, body, _ = operator.call('POST', f'/ops/api/encounters/{pk}/reports',
                                                    {'kind': kind, 'fmt': fmt})
                    item = {'encounter': pk, 'audience': 'operator', 'kind': kind, 'fmt': fmt, 'status': status}
                    report_id = body.get('id') if isinstance(body, dict) else None
                    if status == 201 and report_id:
                        got, _, row = operator.call('GET', f'/ops/api/reports/{report_id}/download', contract=False,
                                                    download=True)
                        item.update(download=got, sha256=row.get('sha256'))
                    created.append(item)
            if pk in files:
                member.call('GET', f'/api/encounters/{pk}/original', contract=False, download=True)
            status, body, _ = member.call('POST', f'/api/encounters/{pk}/resume')
            record.setdefault('resume_probes', {})[pk] = {'status': status,
                                                          'error': body.get('error') if isinstance(body, dict) else None}
        record['previous_reports'] = created
        # one Resume of a stage the previous web stopped, run by the previous worker - started only now, once the
        # switch-back has closed every stage it cannot run (assertion 6)
        resume = record.setdefault('resume', {'encounter': args.resume})
        if args.resume:
            resume['before'] = self.reading(args.resume)
            status, body, _ = member.call('POST', f'/api/encounters/{args.resume}/context', {'setting': args.resume_setting})
            resume['context_save'] = {'status': status, 'body': body if status != 201 else {'context_id': '<new>'}}
            status, body, _ = member.call('POST', f'/api/encounters/{args.resume}/stop')
            resume['stop'] = {'status': status, 'body': body}
            resume['jobs_after_stop'] = inst.sql(
                f"select kind, state from studio_job where encounter_id = '{args.resume}' and created_at >= "
                f"'{self.record['started_at']}' order by created_at")
        worker = self.record.setdefault('worker', {})
        worker['open_at_start'] = open_stages(inst, self.kinds)
        worker['interpret_jobs_at_start'] = inst.sql(
            "select id, state, finished_at, left(error, 80) from studio_job where kind = 'interpret' "
            "and state <> 'succeeded' order by created_at")
        worker['started_at'] = utc_now()
        inst.start('worker', self.previous['id'], args.port)
        time.sleep(20)
        worker['after_20s'] = inst.inspect(f'{NAME}-worker-{args.port}')
        if args.resume:
            status, body, _ = member.call('POST', f'/api/encounters/{args.resume}/resume')
            resume['resume'] = {'status': status, 'body': body}
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                busy = inst.sql(f"select count(*) from studio_job where encounter_id = '{args.resume}' "
                                "and state in ('queued', 'running')")[0][0]
                if busy == '0':
                    break
                time.sleep(5)
            resume['jobs'] = inst.sql(f"select kind, state, left(error, 120) from studio_job where encounter_id = "
                                      f"'{args.resume}' and created_at >= '{self.record['started_at']}' order by created_at")
            resume['state'] = inst.sql(f"select state from studio_encounter where id = '{args.resume}'")[0][0]
            status, _, _ = member.call('GET', f'/api/encounters/{args.resume}')
            resume['detail_after'] = status
            resume['after'] = self.reading(args.resume)
        member.call('GET', '/api/encounters')
        operator.call('GET', '/ops/api/encounters')
        worker['beats'] = inst.sql('select name, beat_at, revision from studio_workerbeat order by beat_at desc')
        worker['at_end'] = inst.inspect(f'{NAME}-worker-{args.port}')
        worker['web_at_end'] = inst.inspect(f'{NAME}-web-{args.port}')
        member.logout()
        operator.logout()
        record['requests'] = member.requests + operator.requests
        statuses = {}
        for row in record['requests']:
            statuses[str(row['status'])] = statuses.get(str(row['status']), 0) + 1
        record['statuses'] = statuses
        record['server_errors'] = [row for row in record['requests']
                                   if row['status'] is None or row['status'] >= 500]
        # RECOMPUTE_STATES once more, read-only, on the rows the previous web and worker have now written
        record['recompute_after_http'] = inst.app_script(
            self.installer, self.previous['id'], ROLLED_BACK.format(body=self.recompute_previous), {},
            what='RECOMPUTE_STATES read-only after the HTTP checks (previous image)')
        record['stopped'] = inst.stop_all()
        worker['census_end'] = self.census()
        self.log(f'HTTP: {len(record["requests"])} requests {statuses}; worker {worker["at_end"]}')

    def reading(self, encounter) -> dict:
        """An encounter's stored reading by SQL: its state, current context version, current assessment's engine and
        each proposal as code:bucket:status."""
        row = self.instance.sql(
            'select e.state, c.version, a.engine_version, (select string_agg(p.code || \':\' || p.bucket || \':\' || p.status, '
            '\' \' order by p.position) from studio_proposal p where p.assessment_id = a.id) from studio_encounter e '
            'left join studio_encountercontext c on c.id = e.current_context_id left join studio_assessment a on '
            f"a.id = e.current_assessment_id where e.id = '{encounter}'")
        state, context, engine, proposals = row[0] if row else (None, None, None, None)
        return {'state': state, 'context_version': context, 'assessment_engine': engine,
                'proposals': (proposals or '').split()}

    # 5. the six assertions
    def assess(self):
        rec = self.record
        sb, http_rec, comp, rc = rec['switch_back'], rec.get('http') or {}, rec.get('comparison') or {}, rec.get('recompute') or {}
        worker = rec.get('worker') or {}
        failed_calls = [call for call in self.instance.calls if call['exit'] != 0]
        render_errors = [{'side': side, **error} for side in ('before', 'after')
                         for error in ((rec.get('renders') or {}).get(side) or {}).get('errors') or ()]
        integrity = {side: ((rec.get('renders') or {}).get(side) or {}).get('integrity') for side in ('before', 'after')}
        a1 = []
        if failed_calls:
            a1.append(f'{len(failed_calls)} one-shot(s) failed: {[c["what"] for c in failed_calls]}')
        if render_errors or comp.get('errors'):
            a1.append(f'{len(render_errors)} render error(s), {len(comp.get("errors") or ())} view error(s)')
        if http_rec.get('server_errors'):
            a1.append(f'{len(http_rec["server_errors"])} request(s) answered 5xx or did not complete')
        for side in ('after_20s', 'at_end'):
            state = worker.get(side) or {}
            if not (state.get('running') and state.get('restarts') == 0 and not state.get('oom_killed')):
                a1.append(f'the previous worker was not running cleanly ({side}: {state})')
        if http_rec.get('health') != 200:
            a1.append(f'the previous web did not answer /health/ with 200 ({http_rec.get("health")})')
        a2 = [f'{f["encounter"]} {f["where"]}: {f["finding"]} ({f.get("before")} -> {f.get("after")}'
              f'{", " + str(f.get("actions") or f.get("offer")) if f.get("actions") or f.get("offer") else ""})'
              for f in comp.get('findings') or ()]
        if not comp.get('encounters'):
            a2.append('no encounter was compared')
        items = []
        stored_views = {side: {pk: (views.get('reports.stored') or {}) for pk, views in (self.views.get(side) or {}).items()}
                        for side in ('before', 'after')}
        for pk, download in sorted((http_rec.get('candidate_reports') or {}).items()):
            if download['audience'] != 'customer' or download['kind'] != 'approved':
                continue
            enc = download['encounter']
            sides = {}
            for side in ('before', 'after'):
                if enc not in stored_views[side]:
                    sides[side] = {'current': None, 'marker_digest': None, 'not_rendered': True}
                    continue
                view = stored_views[side].get(enc) or {}
                artifact = next((a for a in view.get('artifacts') or () if a.get('id') == pk), {})
                sides[side] = {'current': artifact.get('current'), 'marker_digest': view.get('marker_digest')}
            items.append({'id': pk, 'encounter': enc, 'fmt': download['fmt'], 'stored_sha256': download['stored_sha256'],
                          'download': {'status': download['status'], 'sha256': download['sha256']}, **sides})
        rc_problems = list(rc.get('problems') or ())
        note_issues = note_problems(sb.get('note'), sb.get('independent') or {}, self.declared)
        note_issues += [f'before the close: {p}' for p in note_problems(sb.get('note_before_close'),
                                                                          sb.get('independent') or {}, self.declared)]
        refusals = [name for name, refused in (sb.get('refusals') or {}).items() if refused]
        reasons = {}
        for group, named in (sb.get('precheck_hazards_by_class') or {}).items():
            for pk, listed in named.items():
                for reason in listed:
                    reasons.setdefault(reason, {'legacy': 0, 'new_path': 0})[group] += 1
        a6 = []
        start = worker.get('open_at_start') or {}
        if start.get('interpret_open') or start.get('unrunnable_open'):
            a6.append(f'open when the previous worker started: {start}')
        if (sb.get('unrunnable_after_close') or {}).get('stuck') != 0:
            a6.append(f'UNRUNNABLE_STAGES after the close: {sb.get("unrunnable_after_close")}')
        settled = [row for row in worker.get('interpret_jobs_at_start') or () if row[1] in ('queued', 'running')]
        if settled:
            a6.append(f'interpret stages still open at the worker start: {settled}')
        if not settled_before(worker.get('interpret_jobs_at_start'), worker.get('started_at')):
            a6.append('no interpret stage was settled by CLOSE_STAGES before the previous worker started')
        rec['assertions'] = [
            assertion(1, 'no exception and no HTTP 500 anywhere', a1, {
                'one_shots': len(self.instance.calls), 'failed_one_shots': failed_calls, 'render_errors': render_errors,
                'render_integrity': integrity, 'http_statuses': http_rec.get('statuses'),
                'server_errors': http_rec.get('server_errors'), 'worker': worker.get('at_end'),
                'health': http_rec.get('health')}),
            assertion(2, 'per proposal the previous image is equal or strictly more held; no new action', a2, {
                'encounters_compared': comp.get('encounters'), 'new_path_compared': comp.get('new_path'),
                'findings': len(comp.get('findings') or ())}),
            assertion(3, 'RECOMPUTE_STATES moves new-path encounters only toward held; changed set as declared',
                      rc_problems, {'declared': rc.get('declared'), 'declared_at': rc.get('declared_at'),
                                    'read_only': rc.get('read_only'), 'applied': rc.get('applied'),
                                    'copy': rc.get('copy'), 'copy_states': rc.get('copy_states')}),
            assertion(4, 'every approved export the candidate made downloads with an equal marker digest',
                      marker_problems(items), {'approved_exports': items}),
            assertion(5, "the switch-back's note names exactly the new-path encounters, and nothing refuses",
                      note_issues + [f'the switch-back refuses: {name}' for name in refusals], {
                          'note': sb.get('note'), 'note_before_close': sb.get('note_before_close'),
                          'independent': sb.get('independent'), 'declared': self.declared,
                          'refusals': sb.get('refusals'), 'precheck_hazards_by_class': sb.get('precheck_hazards_by_class'),
                          'parts': {'note_names_exactly_the_new_path': not note_issues, 'switch_back_refuses': refusals,
                                    'refusing_reasons': reasons},
                          'close_hazards': (sb.get('close') or {}).get('hazards')}),
            assertion(6, 'the queued interpret stage was settled by CLOSE_STAGES before the previous worker started',
                      a6, {'open_before_close': sb.get('open_before_close'), 'closed_stages': sb.get('closed_stages'),
                           'open_after_close': sb.get('open_after_close'),
                           'unrunnable_after_close': sb.get('unrunnable_after_close'),
                           'interpret_jobs_at_start': worker.get('interpret_jobs_at_start'),
                           'worker_started_at': worker.get('started_at'), 'worker': worker.get('at_end')}),
        ]
        rec['calls'] = self.instance.calls
        rec['finished_at'] = utc_now()
        summary = [f'D15 rollback runtime test ({SCHEMA}) - {"PASS" if all(a["result"] == "PASS" for a in rec["assertions"]) else "FAIL"}',
                   f'candidate {self.candidate["tag"]} ({self.candidate["revision"][:12]}) -> previous '
                   f'{self.previous["tag"]} ({self.previous["revision"][:12]}), database {self.args.db}, '
                   f'{rec["started_at"]} - {rec["finished_at"]}']
        said = {1: f'{len(self.instance.calls)} one-shots, {sum((http_rec.get("statuses") or {}).values())} requests '
                   f'{http_rec.get("statuses")}, worker {(worker.get("at_end") or {}).get("running")} '
                   f'(restarts {(worker.get("at_end") or {}).get("restarts")})',
                2: f'{comp.get("encounters")} encounters compared ({comp.get("new_path")} new-path), '
                   f'{len(comp.get("findings") or ())} finding(s)',
                3: f'declared {rc.get("declared")}; read-only {((rc.get("read_only") or {}).get("answer") or {}).get("changed")}; '
                   f'applied on {rc.get("copy")} {(rc.get("applied") or {}).get("changed")}',
                4: f'{len(items)} approved export(s) made by the candidate',
                5: f'note {(sb.get("note") or {}).get("assessments")} assessments, '
                   f'{len((sb.get("note") or {}).get("encounters") or ())} encounters, context_only '
                   f'{(sb.get("note") or {}).get("context_only")}; exact: {not note_issues}; refusing reasons {reasons}',
                6: f'closed {[row[1] for row in sb.get("closed_stages") or ()]}; open at the worker start '
                   f'{worker.get("open_at_start")}'}
        for item in rec['assertions']:
            summary.append(f'  {item["assertion"]}. {item["result"]}  {item["title"]}')
            summary.append(f'       evidence: {said[item["assertion"]]}')
            for problem in item['problems'][:12]:
                summary.append(f'       - {problem}')
            if len(item['problems']) > 12:
                summary.append(f'       - ... {len(item["problems"]) - 12} more (d15.json)')
        (self.out / 'D15-SUMMARY.txt').write_text('\n'.join(summary) + '\n', encoding='utf-8')
        print('\n'.join(summary))
        return all(a['result'] == 'PASS' for a in rec['assertions'])


def parse(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--db', required=True)
    parser.add_argument('--candidate', required=True, help='the image the install would bring (a tag)')
    parser.add_argument('--previous', required=True, help='the image the switch-back returns to (a tag)')
    parser.add_argument('--port', type=int, required=True, help="the previous web's loopback port")
    parser.add_argument('--out', required=True, help='a new directory for the transcript and the rendered views')
    parser.add_argument('--since', required=True, help='the earliest time the candidate wrote on --db (ISO, with offset)')
    parser.add_argument('--renderer', required=True, help='the directory holding parity_render.py')
    parser.add_argument('--db-env-file', required=True,
                        help='0600 env file: CPT_STUDIO_SECRET_KEY, CPT_STUDIO_DB_USER, CPT_STUDIO_DB_PASSWORD')
    parser.add_argument('--member-credentials', required=True)
    parser.add_argument('--operator-credentials', required=True)
    parser.add_argument('--pg-container', default='gi4-cpt-test-pg')
    parser.add_argument('--pg-port', type=int, default=55461)
    parser.add_argument('--files-volume', default='')
    parser.add_argument('--declared', default='', help='JSON: the new-path set the test instance was built with')
    parser.add_argument('--resume', default='', help='the encounter whose stopped stage the previous worker resumes')
    parser.add_argument('--resume-setting', default='office')
    parser.add_argument('--only', type=lambda value: [x for x in value.split(',') if x], default=[],
                        help='render only these encounters: a smoke run, never a verdict')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse(argv)
    check = Check(args)
    try:
        check.prepare()
    except (Refused, OSError, subprocess.CalledProcessError) as exc:
        print(f'refused: {exc}', file=sys.stderr)
        return 2
    ok = False
    try:
        check.switch_back()
        check.write()
        check.renders()
        check.compare()
        check.write()
        check.recompute()
        check.write()
        check.http()
        check.write()
        ok = check.assess()
    except Exception as exc:  # noqa: BLE001 - recorded, the pair stopped, and the run reported as failed
        check.record['aborted'] = f'{type(exc).__name__}: {exc}'
        check.log(f'aborted: {type(exc).__name__}: {exc}')
        raise
    finally:
        stopped = check.instance.stop_all() if hasattr(check, 'instance') else []
        if stopped:
            check.record.setdefault('stopped_on_exit', stopped)
        if hasattr(check, 'instance'):
            check.write()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
