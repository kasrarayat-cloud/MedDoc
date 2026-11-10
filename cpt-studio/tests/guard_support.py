"""The call-guard matrices' shared machinery (Gemini migration slice S12; design/FINAL.md 10.4, as
design/ADJUDICATION.md R-3, R-5 and R-6 amend it; DECISIONS D17 and D22). Synthetic data only; nothing is sent: Gemini
is the replay interpreter over a recording written for each request, Corti an in-process fake, Astra and Fable the
scripted replay adapters of tests/test_pipeline_assess_events.py.

WHAT THE MATRIX IS GENERATED FROM (FINAL 10.4(1)), never hand-listed: every pattern of cptstudio/urls.py
(``url_routes``), every key of jobs.STAGES (``stage_kinds``) and every in-image installer script - read from
ops/install.py's own source (``in_image``): each body it runs by app_script (RECOMPUTE_STATES, CLOSE_STAGES,
UNDO_HAZARDS_READ = UNDO_HAZARDS + its print, ...), each ``manage shell -c`` script and each management command it runs
in an image, in whatever form the call names it, and a form it cannot read raises naming its line (fail-closed) - and
the worker's own entry, mark_stale (``WORKER``). A generated item with no observation fails the matrix, unless it is
pinned in IN_IMAGE_EXEMPT with why it reads no encounter row; a pin naming nothing the installer runs fails too.

THE RECORDER (``observing``) reads what the sentinel counted while one matrix entry ran, under the labels production
gives it - a request's web scope and its readers' row labels, a stage's own scope, nothing for an in-image script (its
executions count as 'unscoped') - from the sentinel's process totals (the counts of every closed outermost scope, and
every execution outside one), and keeps each outermost scope's entry points (the first new-path frame before each
denied code) before it closes. Nothing here opens a scope around an entry: an enclosing scope would relabel what the
entry runs outside its own.

THE WORLD (``World``) is built through the product's own doors - POST /api/encounters (a .txt upload and pasted text),
the worker (claim_next, run_job), the customer and operator APIs, mark_stale, the in-image scripts and commands - and
every one of those acts is a matrix entry (``Matrix``). Its new-path encounters cover the states FINAL 10.4(1) names:
participants configured and not; a held code, an excluded code and a reinstated one; an approved code with a modifier; a
member answer, its recompute and its withdrawal; a second review; a failed reading and its retries; an unknown outcome
and its reconciliation; a dead worker's stale stage; a context save that re-checks and one that re-predicts on a new
date; an addendum; a Stop and a Resume; an interpreter hold and its release; and two members' answers left standing,
so the in-image scripts, which run last, meet new-path encounters holding a member answer (UNDO_HAZARDS names exactly
the standing answers, CLOSE_STAGES' written_since those given since the world began). ``FACETS`` names FINAL 10.4(1)'s
list, each satisfied by the observations that exercised it. With ``legacy_rows`` the database also holds encounters the
legacy reader read (through the test-only legacy chain, tests/legacy_chain.py; ``LegacyWorld``), so the list, session
and operator-list loops and the in-image scripts meet both kinds of row.

THE LEGACY CHAIN: ``legacy_chain()`` is tests/legacy_chain.py's, with jobs._legacy_reading_allowed patched True as well
- the seam slice S15 adds to that module (S10 named it); patching it here too changes nothing once S15's lands.
"""
from __future__ import annotations

import ast
import base64
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import Client, override_settings
from django.urls import resolve
from django.utils import timezone

from studio import bounded, interpretation, jobs, models
from studio.interpretation import adapter, holds, sentinel
from tests import legacy_chain as legacy_chain_module
from tests.support import factories as f
from tests.support import operator as ops
from tests.test_change_context_events import refused_answer, undated
from tests.test_interpretation_events import COLONOSCOPE, exam, reached
from tests.test_interpretation_identity import a, act, les, sc, snare, tg
from tests.test_pipeline_assess_events import (ACK, AUTH, PRIMARY_45378, SECOND_45385, TWO_CODES, USAGE, EventsCase,
                                               document, envelope, one_colonoscopy, two_procedures)
from tests.test_pipeline_interpret import UNKNOWN, ScriptedInterpreter
from tests.test_readers_dispatch import DENIED_CODES, denied_removal

APP = Path(__file__).resolve().parents[1]
INSTALL = APP / 'ops' / 'install.py'
LABELS = sentinel.LABELS
NEW, LEGACY, OTHER, UNSCOPED = sentinel.NEW_PATH, sentinel.LEGACY_RECORD, sentinel.OTHER, sentinel.UNSCOPED
CODE, REGEX, CACHE = sentinel.CODE, sentinel.REGEX, sentinel.CACHE
Job = models.Job
Run = models.ProviderRun
SUCCEEDED = (Job.SUCCEEDED,)
WORKER = ('mark_stale',)  # the worker's entry that is neither a stage nor a URL (FINAL 10.4(1): "mark_stale")
NOTE = 'Synthetic call-guard matrix: the vendor log shows this request was not answered.'
OPERATOR_PASSWORD = 'synthetic-s12-operator-passphrase-7'
# the sign-in page and the shells render with the static files as a fresh checkout has them (no manifest)
PLAIN_STATIC = {**settings.STORAGES,
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


# --- the synthetic documents the world uploads ----------------------------------------------------------------------

LESION_25 = 'In the sigmoid colon a 6 mm polyp at 25 cm was removed with a cold snare.'
LESION_30 = 'In the sigmoid colon a 3 mm polyp at 30 cm was biopsied with cold forceps; it was not removed.'
MODIFIER_CODES = (('45385', LESION_25), ('45380', LESION_30))  # Corti's on two_lesions()
SIGMOIDOSCOPY = 'Flexible sigmoidoscopy: the sigmoidoscope was advanced to 40 cm.'


def two_lesions():
    """Two polyps at one site, distinct by their distance literals (tests/test_interpretation_cases.py's v1): the snare
    removal of L1 supports 45385 and the biopsy of L2 45380, both ready - and the separate-lesion modifier review is
    offered, so an approval can carry the reviewer's chosen modifier."""
    l1 = les('L1', '6 mm polyp at 25 cm', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='6 mm')
    l2 = les('L2', '3 mm polyp at 30 cm', 'P3', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='3 mm')
    removal = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm polyp at 25 cm', ['P2']))
    biopsy = act('E3', 'P3', 'biopsy', 'biopsied', status_words='was biopsied',
                 technique=a('cold_forceps', 'cold forceps', ['P3']),
                 target=tg('L2', 'sigmoid_colon', '3 mm polyp at 30 cm', ['P3']))
    denial = act('E4', 'P3', 'removal', 'removed', status='not_performed', status_words='it was not removed',
                 scope=sc('single_target', 'it', ['P3']), target=tg('L2', 'sigmoid_colon', 'it', ['P3']))
    return document({'P1': COLONOSCOPE, 'P2': LESION_25, 'P3': LESION_30}, lesions=[l1, l2],
                    events=[exam(), removal, biopsy, denial], reach=[reached()])


PAIR_BIOPSY = 'A 3 mm sessile polyp in the ascending colon was biopsied with cold forceps.'
PAIR_SNARE = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
PAIR_CODES = (('45380', PAIR_BIOPSY), ('45385', PAIR_SNARE))  # Corti's on legacy_pair()


def legacy_pair():
    """A colonoscopy to the cecum with a biopsy of one polyp and the snare removal of another, at two sites (tests/
    test_cux_review.py's 'pair' shape): the LEGACY reading holds both codes ready and offers the separate-lesion
    modifier review, so an approval on a legacy record can carry the reviewer's modifier. Read by the legacy chain
    only, which interprets nothing: no interpretation answer is recorded for it (its answer is an empty one)."""
    lines = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Colonoscopy report (fictional)',
             'Date of service: 11/09/2026.', 'Place of service: Ambulatory surgery center', 'Procedure: Colonoscopy',
             'The colonoscope was advanced to the cecum and the examination was completed.', PAIR_BIOPSY, PAIR_SNARE)
    return {}, '\n'.join(lines) + '\n'


def sigmoidoscopy():
    """A document whose recorded answer the reading refuses whole (the failed-reading encounter's)."""
    lines = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Date of service: 11/09/2026.',
             SIGMOIDOSCOPY)
    return {}, '\n'.join(lines) + '\n'


def tagged(scenario, tag):
    """``scenario`` with one line of its own after the synthetic head: a distinct text, so each encounter's
    interpretation request is its own (an identical request in the workspace would reuse the first one's answer)."""
    def made():
        value, text = scenario()
        head, _, rest = text.partition('\n')
        return value, f'{head}\nSynthetic call-guard matrix document {tag}.\n{rest}'
    return made


# --- what the matrix is generated from (FINAL 10.4(1)) --------------------------------------------------------------

def url_routes() -> list:
    """Every pattern of cptstudio/urls.py, as its route string."""
    from cptstudio import urls

    return [str(pattern.pattern) for pattern in urls.urlpatterns]


def stage_kinds() -> list:
    """Every key of jobs.STAGES."""
    return sorted(jobs.STAGES)


def installer():
    from ops import install

    return install


# deploy/entrypoint.sh's roles a one-shot may be given other than `manage <command>`, each with what it runs (a test
# reads the entrypoint, so the pin cannot drift from it): `migrate` execs `python manage.py migrate --noinput`
ENTRYPOINT_ROLES = {'migrate': ('command', 'migrate')}
DOORS = ('app_script', 'oneshot')  # the installer's ways into an image of the app


def in_image(source: str = None) -> dict:
    """What ops/install.py runs in an image of the app, read from its source (``source``: its text, by default the
    file's): {('script', name): how} for every module-level script body it hands app_script (its third argument, or
    ``body=``) or ``manage shell -c`` (the fourth item of the command list), and {('command', name): how} for every
    management command a one-shot runs - a ['manage', name, ...] list, or an entrypoint role (ENTRYPOINT_ROLES) -
    whether the call spells the list out, names a local the function assigns one to, or calls a function of the module
    that returns one.

    FAIL-CLOSED (the review of S12, finding 3): an app_script or oneshot call, or a list that begins 'manage', that does
    not resolve to a module-level script or a literal command - a concatenated body, a starred or computed command, a
    role the entrypoint pin does not know, a command passed in or bound by a loop, an alias or a partial of either
    door - raises ValueError naming its line. What the generator cannot read the matrix cannot drive, and a dropped
    item would leave the matrix green over a script it never ran. The one exception is app_script's own `manage shell
    -c <source>`: the wrapper's plumbing, whose scripts are read at each call of it."""
    module = installer()
    tree = ast.parse(source if source is not None else INSTALL.read_text(encoding='utf-8'))
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    owner = {item: fn for fn in functions.values() for item in ast.walk(fn)}  # a node -> its module-level function
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found = {}

    def refuse(node, what):
        raise ValueError(f'ops/install.py:{getattr(node, "lineno", "?")}: {what} - the matrix cannot tell what it runs '
                         f'in an image ({ast.unparse(node)[:160]})')

    def script(node, call):
        """The module-level script ``node`` names: one of the module's strings, or an entry of a dict of them."""
        target, kind = (node.value, dict) if isinstance(node, ast.Subscript) else (node, str)
        if isinstance(target, ast.Name) and isinstance(getattr(module, target.id, None), kind):
            return target.id
        refuse(call, "a script body that is not one of the module's own scripts")

    def argument(call, position, keyword):
        if any(isinstance(item, ast.Starred) for item in call.args[:position + 1]):
            refuse(call, 'a starred argument')
        if len(call.args) > position:
            return call.args[position]
        for item in call.keywords:
            if item.arg == keyword:
                return item.value
        refuse(call, f'no {keyword} the call names')

    def assigned(name, scope, call):
        """What the module-level function ``scope`` assigns ``name`` (every plain assignment); a name bound any other
        way - a parameter, a loop, a with, an unpacking, a walrus - or never assigned cannot be read."""
        args = scope.args
        if name in {item.arg for item in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg)
                    if item is not None}:
            refuse(call, f'a command passed in ({name})')
        values = []
        for item in ast.walk(scope):
            other = ((item.asname or item.name).split('.')[0] if isinstance(item, ast.alias)
                     else item.name if isinstance(item, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar, ast.FunctionDef,
                                                         ast.AsyncFunctionDef, ast.ClassDef))
                     else item.rest if isinstance(item, ast.MatchMapping) else None)
            if other == name and item is not scope:  # bound by a handler, an import, a pattern or a definition
                refuse(call, f'a command bound otherwise than by an assignment ({name})')
            if not (isinstance(item, ast.Name) and item.id == name and isinstance(item.ctx, ast.Store)):
                continue
            parent = parents.get(item)
            if isinstance(parent, ast.Assign) and item in parent.targets:
                values.append(parent.value)
            elif isinstance(parent, ast.AnnAssign) and parent.value is not None:
                values.append(parent.value)
            elif not isinstance(parent, ast.AugAssign):  # `command += [...]` keeps the command it extends
                refuse(call, f'a command bound otherwise than by an assignment ({name})')
        if not values:
            refuse(call, f'a command {scope.name} never assigns ({name})')
        return values

    def lists(node, scope, call, seen=frozenset()):
        """The list displays a command expression evaluates to (``seen``: the names and returns being read, so a
        `command = command + [...]` extends what the name's other assignments spell out instead of recursing)."""
        if isinstance(node, ast.List):
            return [node]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):  # [...] + [...]: the head decides
            return lists(node.left, scope, call, seen)
        if isinstance(node, ast.Name) and scope is not None:
            key = (scope.name, node.id)
            if key in seen:
                return []
            return [item for value in assigned(node.id, scope, call)
                    for item in lists(value, scope, call, seen | {key})]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions:
            fn = functions[node.func.id]
            if (fn.name, None) in seen:
                return []
            values = [item.value for item in ast.walk(fn) if isinstance(item, ast.Return) and item.value is not None]
            if not values:
                refuse(call, f'{fn.name} returns no command')
            return [item for value in values for item in lists(value, fn, call, seen | {(fn.name, None)})]
        refuse(call, 'a command that is not a list the installer spells out')

    def command(display, call):
        """What one command list runs, recorded."""
        head = display.elts[0] if display.elts else None
        if not (isinstance(head, ast.Constant) and isinstance(head.value, str)):
            refuse(call, 'a command whose entrypoint role is not spelled out')
        if head.value != 'manage':
            if head.value not in ENTRYPOINT_ROLES:
                refuse(call, f'an entrypoint role the pin does not know ({head.value})')
            found.setdefault(ENTRYPOINT_ROLES[head.value], 'oneshot')
            return
        name = display.elts[1] if len(display.elts) > 1 else None
        if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
            refuse(call, 'a management command that is not spelled out')
        if name.value != 'shell':
            found.setdefault(('command', name.value), 'manage')
            return
        body = display.elts[3] if len(display.elts) > 3 else None
        inside = owner.get(display)
        if inside is not None and inside.name == 'app_script' and isinstance(body, ast.Name):
            return  # app_script's own `manage shell -c <source>`: the wrapper's plumbing
        if body is None or any(isinstance(item, ast.Starred) for item in display.elts[:4]):
            refuse(call, 'a shell script that is not spelled out')
        found.setdefault(('script', script(body, call)), 'manage shell -c')

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in DOORS and isinstance(node.ctx, ast.Load):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                refuse(node, f'{node.id} named but not called (an alias or a partial runs what is never read)')
        if isinstance(node, ast.Call):
            door = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if door == 'app_script':
                found.setdefault(('script', script(argument(node, 2, 'body'), node)), 'app_script')
            elif door == 'oneshot':
                displays = lists(argument(node, 1, 'command'), owner.get(node), node)
                if not displays:
                    refuse(node, 'a command the installer never spells out')
                for display in displays:
                    command(display, node)
        elif isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Constant) \
                and node.elts[0].value == 'manage':
            command(node, node)
    return found


# What the installer runs in an image that the matrix does not run, each with why it reads no encounter row (and so
# no reader, legacy or new): a new script or command is driven, or pinned here deliberately.
IN_IMAGE_EXEMPT = {
    ('script', 'CREDENTIALS_CHECK'): "parses Corti's credential file in the worker's mount layout, the network off; "
                                     'reads no encounter row',
    ('script', 'PARTICIPANT_CREDENTIALS_CHECKS'): "parses a participant's credential file, the network off; reads no "
                                                  'encounter row',
    ('script', 'INTERPRETER_CREDENTIALS_CHECK'): "parses the interpreter's credential file, the network off; reads no "
                                                 'encounter row',
    ('command', 'participant_access_check'): "a participant's live access check against its vendor (a network call, "
                                             'never made here); reads no encounter row',
    ('command', 'import_reference'): 'imports a pinned reference archive; reads no encounter row',
    ('command', 'import_passages'): 'imports the pinned reference passages; reads no encounter row',
    ('command', 'provision'): 'creates a workspace and its accounts; reads no encounter row',
    ('command', 'grant_operator'): "records an operator's grant from a reason file; reads no encounter row",
}


def generated(source: str = None) -> list:
    """Every matrix item: ('url', route), ('stage', kind), ('script' | 'command', name), ('worker', name)."""
    return ([('url', route) for route in url_routes()] + [('stage', kind) for kind in stage_kinds()]
            + sorted(in_image(source)) + [('worker', name) for name in WORKER])


# --- the recorder ----------------------------------------------------------------------------------------------------

def _totals() -> dict:
    with sentinel._LOCK:
        return {label: dict(sentinel._TOTALS.get(label, {})) for label in LABELS}


class Observation:
    """One run of one matrix entry: what the sentinel counted, by label and by what ran (``hits``), the outermost scopes
    that counted something with their entry points (``entries``: (scope entry, label, ['caller -> denied code'])), the
    callback failures meanwhile (``errors``), and what the entry did (``detail``: a status, a stage's state, its mode).
    """

    def __init__(self, key, what, tag=''):
        self.key, self.what, self.tag = key, what, tag
        self.hits = {label: {} for label in LABELS}
        self.entries = []
        self.errors = 0
        self.detail = {}

    def count(self, labels=LABELS) -> int:
        labels = (labels,) if isinstance(labels, str) else labels
        return sum(sum(self.hits[label].values()) for label in labels)

    def kinds(self, labels=LABELS) -> dict:
        labels = (labels,) if isinstance(labels, str) else labels
        out = {CODE: 0, REGEX: 0, CACHE: 0}
        for label in labels:
            for key, n in self.hits[label].items():
                out[sentinel._KINDS.get(key, CODE)] += n
        return out

    def names(self, labels=LABELS) -> list:
        """'<label>: <file:line qualname, or pattern, or cache> x<n>' for everything counted under ``labels``."""
        labels = (labels,) if isinstance(labels, str) else labels
        named = sentinel.names()
        return [f'{label}: {named.get(key, f"id {key}")} x{n}' for label in labels
                for key, n in sorted(self.hits[label].items(), key=lambda item: -item[1])]

    def describe(self, labels=LABELS) -> str:
        lines = [f'{self.what} [{self.key[0]} {self.key[1]!r}]' + (f' ({self.tag})' if self.tag else '')
                 + (f' {self.detail}' if self.detail else '')]
        lines += [f'    {line}' for line in self.names(labels)]
        for entry, label, points in self.entries:
            lines += [f'    scope {entry} [{label}] entered: {point}' for point in points]
        if self.errors:
            lines.append(f'    {self.errors} callback failure(s): the count cannot be vouched for')
        return '\n'.join(lines)


@contextlib.contextmanager
def observing(observation: Observation):
    """Record into ``observation`` what the sentinel counts while the block runs (see the module docstring)."""
    before, errors = _totals(), sentinel._STATE.errors
    real_close = sentinel.Scope._close

    def close(scope_):
        if scope_.parent is None and not scope_.private and scope_.counts():
            observation.entries.append((scope_.entry, scope_.label, list(scope_.entries)))
        return real_close(scope_)

    try:
        with mock.patch.object(sentinel.Scope, '_close', close):
            yield observation
    finally:
        after = _totals()
        for label in LABELS:
            found = {key: n - before[label].get(key, 0) for key, n in after[label].items()}
            for key, n in found.items():
                if n:
                    observation.hits[label][key] = observation.hits[label].get(key, 0) + n
        observation.errors += sentinel._STATE.errors - errors


class Red(Exception):
    """A matrix entry went red while the matrix was asked to stop at the first one (a mutation proof)."""

    def __init__(self, observation):
        super().__init__(observation.describe())
        self.observation = observation


# --- the matrix ------------------------------------------------------------------------------------------------------

class Matrix:
    """The observations of one world. ``stop_on``: a predicate over an observation; when it holds, Red is raised once
    that entry has finished (the mutation proofs stop at the first red entry)."""

    def __init__(self, case, *, stop_on=None):
        self.case = case
        self.observations = []
        self.stop_on = stop_on

    def observe(self, key, what, fn, *, tag=''):
        observation = Observation(key, what, tag)
        with observing(observation):
            result = fn()
        self.observations.append(observation)
        if self.stop_on is not None and self.stop_on(observation):
            raise Red(observation)
        return result, observation

    def _commits(self):
        capture = getattr(self.case, 'captureOnCommitCallbacks', None)
        return capture(execute=True) if capture is not None else contextlib.nullcontext()

    def request(self, client, method, path, body=None, *, files=None, tag='', expect=None):
        """One request through the URL map (its route is the matrix item), its JSON ``body`` or multipart ``files``."""
        route = resolve(path.split('?', 1)[0]).route

        def send():
            with self._commits():
                if method == 'GET':
                    return client.get(path)
                if files is not None:
                    return client.post(path, files)
                return client.generic(method, path, json.dumps(body if body is not None else {}),
                                      content_type='application/json')

        response, observation = self.observe(('url', route), f'{method} /{route}', send, tag=tag)
        observation.detail['status'] = response.status_code
        for name in ('action', 'kind', 'fmt'):
            if isinstance(body, dict) and name in body:
                observation.detail[name] = body[name]
        if expect is not None:
            self.case.assertIn(response.status_code, expect, f'{method} {path} ({tag}): {response.content[:600]!r}')
        return response

    def drain(self, *, before=None, tag='', expect=SUCCEEDED, until=None):
        """The worker: claim_next and run_job, one matrix entry per stage, until nothing is queued (or a stage of kind
        ``until`` has run). ``before``: called with the queued jobs before each claim (the replay recordings)."""
        ran = []
        while True:
            queued = list(Job.objects.filter(state=Job.QUEUED).order_by('created_at', 'pk'))
            if not queued:
                return ran
            if before is not None:
                before(queued)

            def work():
                job = jobs.claim_next()
                return job if job is None else jobs.run_job(job)

            observation = Observation(('stage', '?'), 'the worker: claim_next, run_job', tag)
            with observing(observation):
                job = work()
            if job is None:
                return ran
            observation.key, observation.what = ('stage', job.kind), f'stage {job.kind}'
            observation.detail.update(state=job.state, mode=(job.result or {}).get('mode', ''),
                                      key=job.idempotency_key, encounter=str(job.encounter_id))
            if job.error:
                observation.detail['error'] = job.error[:200]
            self.observations.append(observation)
            if self.stop_on is not None and self.stop_on(observation):
                raise Red(observation)
            if expect is not None:
                self.case.assertIn(job.state, expect, f'{job.kind} ({tag}): {job.error}')
            ran.append(job)
            if until is not None and job.kind == until:
                return ran

    def script(self, name, params, *, tag=''):
        """An in-image script as the installer runs it (APP_SCRIPT_PRELUDE + body; ``manage shell -c`` runs it with no
        scope open), compiled under the installer's file name so its own calls are the app's to the CALL checks; its one
        ANSWER line, read as JSON."""
        install = installer()
        body = getattr(install, name)
        payload = base64.b64encode(json.dumps(params).encode()).decode()
        source = install.APP_SCRIPT_PRELUDE.format(payload=payload, answer=install.APP_SCRIPT_ANSWER) + body
        code = compile(source, f'{INSTALL}#{name}', 'exec')
        out = io.StringIO()

        def run():
            with contextlib.redirect_stdout(out):
                exec(code, {'__name__': f'cpt_studio_app_script_{name.lower()}'})

        _, observation = self.observe(('script', name), f'in-image {name}', run, tag=tag)
        answers = [line for line in out.getvalue().splitlines() if line.startswith(install.APP_SCRIPT_ANSWER)]
        self.case.assertEqual(len(answers), 1, out.getvalue()[-2000:])
        answer = json.loads(answers[0][len(install.APP_SCRIPT_ANSWER):])
        observation.detail['answer'] = sorted(answer)
        return answer

    def command(self, name, *args, tag=''):
        """A management command as the installer runs it in an image (no scope open); its output and exit code."""
        out, err = io.StringIO(), io.StringIO()

        def run():
            try:
                call_command(name, *args, stdout=out, stderr=err)
                return 0
            except SystemExit as exc:
                return exc.code if isinstance(exc.code, int) else 1
            except CommandError as exc:  # what `manage` prints and exits 1 on
                err.write(str(exc))
                return 1

        code, observation = self.observe(('command', name), f'manage {name} {" ".join(args)}', run, tag=tag)
        observation.detail['exit'] = code
        if code:
            observation.detail['error'] = err.getvalue()[-300:]
        return code, out.getvalue()

    def call(self, key, what, fn, *, tag=''):
        return self.observe(key, what, fn, tag=tag)[0]

    # --- reading the matrix ----------------------------------------------------------------------------------------

    def keys(self) -> set:
        return {observation.key for observation in self.observations}

    def missing(self, source: str = None) -> list:
        """Generated items with no observation and no pinned exemption (``source``: the installer's text, as
        in_image)."""
        seen = self.keys()
        return [item for item in generated(source) if item not in seen and item not in IN_IMAGE_EXEMPT]

    def unknown(self) -> list:
        """Observed keys that are not generated items (a route typo would hide a missing one)."""
        items = set(generated())
        return sorted(key for key in self.keys() if key not in items)

    def red(self, labels=(NEW,)) -> list:
        return [item for item in self.observations if item.count(labels) or item.errors]

    def report(self, labels=(NEW,)) -> str:
        found = self.red(labels)
        return f'{len(found)} of {len(self.observations)} matrix entries counted denied executions under ' \
               f'{", ".join(labels)}:\n' + '\n'.join(item.describe(labels) for item in found)

    def satisfied(self) -> dict:
        """{facet: [the observations that exercised it]} for FINAL 10.4(1)'s list (FACETS)."""
        return {name: [item for item in self.observations if test(item)] for name, test in FACETS}


def _url(route, status=None, **detail):
    def test(item):
        return (item.key == ('url', route) and (status is None or item.detail.get('status') in status)
                and all(item.detail.get(name) == value for name, value in detail.items()))
    return test


def _stage(kind, *, mode=None, tag=None):
    def test(item):
        return (item.key == ('stage', kind) and item.detail.get('state') == Job.SUCCEEDED
                and (mode is None or item.detail.get('mode') == mode) and (tag is None or tag in item.tag))
    return test


def _tagged(test, tag):
    return lambda item: test(item) and tag in item.tag


ENC = 'api/encounters/<uuid:encounter_id>'
OPS_ENC = 'ops/api/encounters/<uuid:encounter_id>'
OK, CREATED = (200,), (201,)
# FINAL 10.4(1)'s list: "The matrix must include ..." - each satisfied by an observation that exercised it.
FACETS = (
    ('interpret', _stage('interpret')),
    ('analyze', _stage('analyze')),
    ('predict with a new date', _stage('predict', tag='new date')),
    ('assess FIRST', _stage('assess', mode='first')),
    ('assess FINAL', _stage('assess', mode='final')),
    ('assess AGAIN', _stage('assess', mode='again')),
    ('the review2 follow-up', _stage('assess', mode='review2')),
    ('answer save', _url(f'{ENC}/details', CREATED)),
    ('answer recompute', _stage('assess', mode='again', tag='answer')),
    ('answer withdrawal', _url(f'{ENC}/details/<uuid:answer_id>/revoke', CREATED)),
    ('context save that re-checks', _tagged(_url(f'{ENC}/context', CREATED), 're-check')),
    ('context save that re-predicts', _tagged(_url(f'{ENC}/context', CREATED), 'new date')),
    ('the review view', _url(ENC, OK)),
    ('decision: approve', _url(f'{ENC}/decisions', CREATED, action='approve')),
    ('decision: reject', _url(f'{ENC}/decisions', CREATED, action='reject')),
    ('decision: reinstate', _url(f'{ENC}/decisions', CREATED, action='reinstate')),
    ('decision: confirm', _url(f'{ENC}/decisions', CREATED, action='confirm')),
    ('decision: revoke', _url(f'{ENC}/decisions', CREATED, action='revoke')),
    ('an approval with a modifier', _tagged(_url(f'{ENC}/decisions', CREATED, action='approve'), 'modifier')),
    ('reload: customer_state and detail', _url(ENC, OK)),
    ('reload: list', _url('api/encounters', OK)),
    ('reload: session', _url('api/session', OK)),
    ('reload: the operator detail', _url(OPS_ENC, OK)),
    ('export: draft', _url(f'{ENC}/reports', CREATED, kind='draft')),
    ('export: approved', _url(f'{ENC}/reports', CREATED, kind='approved')),
    ('export: operator TXT', _url(f'{OPS_ENC}/reports', CREATED, fmt='txt')),
    ('export: operator CSV', _url(f'{OPS_ENC}/reports', CREATED, fmt='csv')),
    ('export: download', _url('api/reports/<uuid:report_id>/download', OK)),
    ('export: operator download', _url('ops/api/reports/<uuid:report_id>/download', OK)),
    ('the peer request build', _stage('astra_peer')),
    ('the second-review offer', lambda item: _url(ENC, OK)(item) and item.detail.get('offered') is True),
    ('the second-review ask', _url(f'{ENC}/second-review', CREATED)),
    ('the second-review stage', _stage('review2')),
    ('reconcile', _url(f'{OPS_ENC}/reconcile', CREATED)),
    ('Resume', _url(f'{ENC}/resume', CREATED)),
    ('Stop', _url(f'{ENC}/stop', OK)),
    ('mark_stale', lambda item: item.key == ('worker', 'mark_stale')),
    ('reviewed_completeness with a reinstated code', _tagged(_url(ENC, OK), 'reinstated')),
    ('a retry of a failed reading', _url(f'{ENC}/retry-reading', CREATED)),
    ('an operator retry of a failed reading', _url(f'{OPS_ENC}/retry-reading', CREATED)),
    ('an addendum read', _stage('assess', tag='addendum')),
    ('the interpreter hold released', _url('ops/api/interpreter', CREATED)),
    ('participants configured', _stage('astra')),
    ('RECOMPUTE_STATES', lambda item: item.key == ('script', 'RECOMPUTE_STATES')),
    ('CLOSE_STAGES', lambda item: item.key == ('script', 'CLOSE_STAGES')),
    ('UNDO_HAZARDS', lambda item: item.key == ('script', 'UNDO_HAZARDS_READ')),
    ('the in-image scripts beside a standing member answer',
     lambda item: item.key == ('script', 'UNDO_HAZARDS_READ') and item.detail.get('standing answers', 0) > 0),
)


# --- the legacy chain (tests/legacy_chain.py, with S10's seam) -------------------------------------------------------

@contextlib.contextmanager
def legacy_chain():
    """tests/legacy_chain.py's legacy_chain(), with jobs._legacy_reading_allowed patched True too (module docstring)."""
    with legacy_chain_module.legacy_chain(), mock.patch.object(jobs, '_legacy_reading_allowed', return_value=True):
        yield


# --- the test case and the world -------------------------------------------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class GuardCase(EventsCase):
    """EventsCase (tests/test_pipeline_assess_events.py: Gemini replayed, Corti faked, Astra and Fable scripted) whose
    Corti answers every document the world uploads: the first group whose quotes all appear in its request."""
    corti_groups = (TWO_CODES, DENIED_CODES, MODIFIER_CODES, PRIMARY_45378, SECOND_45385, PAIR_CODES)
    participant_codes = (('45378', 'The colonoscope was advanced to the cecum'),)

    def setUp(self):
        super().setUp()
        self.membership = models.Membership.objects.get(user=self.user, workspace=self.ws)


class World:
    """The new-path world (module docstring), every act a matrix entry. ``legacy_rows``: legacy encounters too."""

    def __init__(self, case, matrix, *, legacy_rows=False, operator=None):
        self.case, self.matrix, self.legacy_rows = case, matrix, legacy_rows
        self.member = Client()
        self.member.force_login(case.user)
        if operator is None:
            self.operator_user = f.user('operator-s12-matrix')
            ops.grant(self.operator_user)
            self.operator = Client()
            self.operator.force_login(self.operator_user)
        else:
            self.operator_user, self.operator = operator
        self.recordings = {}  # encounter id -> the 200 body its interpretation requests are answered with
        self.recounts = 0  # reads of a frozen event inventory for a reinstated code's coverage (EventReader.reading)
        self.ids = {}  # name -> encounter id
        self.started = timezone.now()
        self.legacy_ids = []

    # --- plumbing (not matrix entries) ------------------------------------------------------------------------------

    def record(self, queued):
        """Write the replay recording of every queued interpret stage's request, from its encounter's answer."""
        folder = Path(self.case.replay) / adapter.NAME
        folder.mkdir(exist_ok=True)
        for job in queued:
            body = self.recordings.get(str(job.encounter_id))
            if job.kind != jobs.INTERPRET or body is None:
                continue
            revision = models.SourceRevision.objects.get(pk=job.revision_id)
            if not revision.text:
                continue
            request = adapter.build_request(revision.text, jobs._participant_pages(revision),
                                            jobs._participant_document(revision)[0])
            (folder / f'{request.canonical_sha256}.json').write_bytes(body)

    def drain(self, tag='', **kwargs):
        return self.matrix.drain(before=self.record, tag=tag, **kwargs)

    def get(self, path, *, tag='', client=None, expect=OK):
        return self.matrix.request(client or self.member, 'GET', path, tag=tag, expect=expect)

    def post(self, path, body=None, *, tag='', client=None, expect=CREATED, files=None):
        return self.matrix.request(client or self.member, 'POST', path, body, files=files, tag=tag, expect=expect)

    def detail(self, name, tag=''):
        """GET /api/encounters/<id>: the review view, the customer state and the second-review offer."""
        response = self.get(f'/api/encounters/{self.ids[name]}', tag=f'{name} {tag}'.strip())
        payload = response.json()
        self.matrix.observations[-1].detail['offered'] = bool(payload['recheck']['available'])
        return payload

    @staticmethod
    def codes(payload) -> dict:
        return {row['code']: row for row in payload['codes']}

    def upload(self, name, scenario, *, file=False, body=None):
        """POST /api/encounters (a .txt upload or pasted text, attested synthetic); the answer its reading replays."""
        value, text = scenario()
        if file:
            files = {'file': SimpleUploadedFile(f'{name.lower()}.txt', text.encode('utf-8'), content_type='text/plain'),
                     'synthetic_attestation': 'yes', 'title': f'Synthetic {name}'}
        else:
            files = {'text': text, 'synthetic_attestation': 'yes', 'title': f'Synthetic {name}'}
        response = self.post('/api/encounters', files=files, tag=name)
        self.ids[name] = response.json()['id']
        self.recordings[self.ids[name]] = body if body is not None else envelope(value)
        return self.ids[name]

    def encounter(self, name):
        return models.Encounter.objects.get(pk=self.ids[name])

    def decide(self, name, code, action, *, tag='', modifiers=None):
        payload = self.detail(name, tag=f'before {action} {code}')
        row = self.codes(payload)[code]
        self.case.assertIn(action, row['allowed_actions'], (name, code, row['allowed_actions']))
        body = {'proposal_id': row['id'], 'action': action,
                'acknowledgement': ACK if action == 'approve' else ''}
        if modifiers is not None:
            body['modifiers'] = modifiers
        return self.post(f'/api/encounters/{self.ids[name]}/decisions', body, tag=f'{name} {tag}'.strip())

    def reads(self, name, tag=''):
        """Every read of one encounter: the customer's detail, the list and the session, the operator's detail, trace
        and report list."""
        pk = self.ids[name]
        payload = self.detail(name, tag)
        self.get('/api/encounters', tag=name)
        self.get('/api/session', tag=name)
        for path in (f'/ops/api/encounters/{pk}', f'/ops/api/encounters/{pk}/trace',
                     f'/ops/api/encounters/{pk}/reports'):
            self.get(path, client=self.operator, tag=f'{name} {tag}'.strip())
        return payload

    def exports(self, name, *, approved=False):
        """The customer's draft (and approved) exports and the operator's reports, each downloaded."""
        pk = self.ids[name]
        kinds = ('draft', 'approved') if approved else ('draft',)
        for kind in kinds:
            for fmt in ('txt', 'csv'):
                made = self.post(f'/api/encounters/{pk}/reports', {'kind': kind, 'fmt': fmt}, tag=name)
                self.get(made.json()['download_url'], tag=name)
        for kind in (('draft', 'reviewed') if approved else ('draft',)):
            for fmt in ('txt', 'csv'):
                made = self.post(f'/ops/api/encounters/{pk}/reports', {'kind': kind, 'fmt': fmt}, client=self.operator,
                                 tag=name)
                self.get(made.json()['download_url'], client=self.operator, tag=name)

    # --- the world ---------------------------------------------------------------------------------------------------

    def run(self):
        from studio.interpretation import readers

        real = readers.EventReader.reading

        def reading(reader, assessment):
            self.recounts += 1
            return real(reader, assessment)

        with mock.patch.object(readers.EventReader, 'reading', reading):
            return self._run()

    def _run(self):
        self.no_encounter()
        if self.legacy_rows:
            self.legacy_records()
        self.held_and_answered()
        self.participants_and_second_review()
        self.excluded_and_reinstated()
        self.modifier()
        self.new_date()
        self.failed_reading()
        self.unknown_outcome()
        self.stale_stage()
        self.addendum()
        self.interpreter_hold()
        self.standing_answers()
        self.sign_out()
        self.in_image()
        return self

    def no_encounter(self):
        """The URLs that name no encounter (their scope is 'other'), before any encounter exists."""
        anonymous = Client()
        self.get('/health/', client=anonymous)
        self.get('/login/', client=anonymous)
        self.get('/', expect=OK)
        self.get('/api/session')
        self.get('/api/encounters')
        for path in ('/ops/', '/ops/assets/ops.js', '/ops/assets/ops.css', '/ops/api/session', '/ops/api/encounters',
                     '/ops/api/interpreter'):
            self.get(path, client=self.operator)

    def legacy_records(self):
        """Encounters the legacy reader read (LegacyWorld) - fixture rows, never matrix entries: their own stages ran
        the legacy reader, as they did before the migration."""
        legacy = LegacyWorld(self.case, operator=(self.operator_user, self.operator)).build()
        self.legacy_ids = [legacy.ids[name] for name, _ in LegacyWorld.SCENARIOS]

    def held_and_answered(self):
        """E1: an EGD with antral biopsies (43239, ready) and a colonoscopy whose polyp removal is held (45385),
        uploaded as a .txt file; an approval, a member's answer, its recompute and its withdrawal, a context save that
        re-checks, a Stop and a Resume, the doors this state refuses, and the exports."""
        pk = self.upload('E1', tagged(two_procedures, 'E1'), file=True)
        self.drain('E1 first')
        payload = self.reads('E1')
        self.case.assertEqual({code: row['status'] for code, row in self.codes(payload).items()},
                              {'43239': 'ready', '45385': 'needs_detail'})
        self.get(f'/api/encounters/{pk}/original', tag='E1')
        self.get(f'/ops/api/encounters/{pk}/original', client=self.operator, tag='E1')
        self.decide('E1', '43239', 'approve')
        row = next(item for item in self.detail('E1')['details_needed']
                   if '45385' in item['affects'] and 'not_documented' in item['allow'])
        saved = self.post(f'/api/encounters/{pk}/details',
                          {'answers': [{'id': row['id'], 'fact': row['fact'], 'value': 'not_documented'}]}, tag='E1')
        self.drain('E1 answer')
        self.reads('E1', 'answered')
        self.post(f'/api/encounters/{pk}/details/{saved.json()["answer_ids"][0]}/revoke', tag='E1')
        self.drain('E1 answer withdrawn')
        self.post(f'/api/encounters/{pk}/context', {'setting': 'asc'}, tag='E1 re-check')
        self.post(f'/api/encounters/{pk}/stop', expect=OK, tag='E1')
        self.post(f'/api/encounters/{pk}/resume', tag='E1')
        self.drain('E1 re-check')
        clarification = models.Clarification.objects.filter(encounter_id=pk).order_by('created_at').first()
        self.post(f'/api/encounters/{pk}/clarifications/{clarification.pk}/confirm',
                  {'candidate_id': 'c1', 'attestation': 'synthetic'}, expect=(409,), tag='E1 not offered')
        self.post(f'/api/encounters/{pk}/second-review', expect=(409,), tag='E1 nothing open')
        self.post(f'/api/encounters/{pk}/retry-reading', expect=(409,), tag='E1 nothing to retry')
        self.exports('E1')
        self.reads('E1', 'exported')

    def participants_and_second_review(self):
        """E2: a colonoscopy whose polyp removal no proposal covers, read with Astra and Fable configured (assess #1,
        the peer requests, assess #2); the bounded second review offered, asked, run and followed up."""
        with participants():
            pk = self.upload('E2', tagged(one_colonoscopy, 'E2'))
            self.drain('E2 participants')
            payload = self.reads('E2', 'offer')
            self.case.assertTrue(payload['recheck']['available'], payload['recheck'])
            self.post(f'/api/encounters/{pk}/second-review', tag='E2')
            self.drain('E2 second review')
            self.reads('E2', 'second review')
            self.exports('E2')

    def excluded_and_reinstated(self):
        """E3: a colonoscopy to the cecum (45378, ready) and a broad current denial of any removal that 45385 cites
        (excluded, reinstatable): a confirmation of the exclusion and its revocation, the reinstatement (whose reviewed
        coverage re-runs over the frozen inventory), an approval and a rejection, and the approved exports."""
        self.upload('E3', tagged(denied_removal, 'E3'))
        self.drain('E3')
        payload = self.reads('E3')
        self.case.assertEqual(self.codes(payload)['45385']['status'], 'excluded')
        self.decide('E3', '45385', 'confirm')
        self.decide('E3', '45385', 'revoke')
        self.decide('E3', '45385', 'reinstate')
        before = self.recounts
        self.reads('E3', 'reinstated')
        # the read-time path: the reinstated code's coverage re-run over the frozen inventory, in the observed reads
        self.case.assertGreater(self.recounts, before)
        self.decide('E3', '45385', 'approve')
        self.decide('E3', '45378', 'reject')
        self.reads('E3', 'reinstated and decided')
        self.exports('E3', approved=True)

    def modifier(self):
        """E4: two polyps at one site, distinct by their distance literals: an approval carrying the reviewer's chosen
        separate-lesion modifier."""
        self.upload('E4', tagged(two_lesions, 'E4'))
        self.drain('E4')
        payload = self.reads('E4')
        offered = [row for row in payload['codes'] if row.get('modifier_review')]
        self.case.assertTrue(offered, [(row['code'], row['status']) for row in payload['codes']])
        row = offered[0]
        self.decide('E4', row['code'], 'approve', tag='modifier',
                    modifiers=[row['modifier_review']['options'][0]])
        self.reads('E4', 'modifier')
        self.exports('E4')

    def new_date(self):
        """E5: the same procedures with no date of service stated; a context save with the member's date re-predicts on
        that new date (the routing stand-in, never the legacy router)."""
        pk = self.upload('E5', tagged(undated, 'E5'))
        self.drain('E5 undated')
        self.reads('E5')
        self.post(f'/api/encounters/{pk}/context', {'service_date': '2026-11-09'}, tag='E5 new date')
        self.drain('E5 new date')
        self.reads('E5', 'dated')

    def failed_reading(self):
        """E6: an answer the reading refuses whole fails the interpret stage; the member's recorded retry and the
        operator's each release one more attempt (which the replayed answer fails again)."""
        pk = self.upload('E6', tagged(sigmoidoscopy, 'E6'), body=refused_answer())
        self.drain('E6', expect=(Job.SUCCEEDED, Job.FAILED))
        self.reads('E6', 'failed')
        self.post(f'/api/encounters/{pk}/retry-reading', tag='E6')
        self.drain('E6 retry', expect=(Job.SUCCEEDED, Job.FAILED))
        self.post(f'/ops/api/encounters/{pk}/retry-reading', {'override': False}, client=self.operator, tag='E6')
        self.drain('E6 operator retry', expect=(Job.SUCCEEDED, Job.FAILED))
        self.reads('E6', 'failed again')

    def unknown_outcome(self):
        """E7: the interpretation's outcome is unknown (the exchange timed out after the send); the encounter waits; the
        operator reconciles it and the reading is made again."""
        pk = self.upload('E7', tagged(two_procedures, 'E7'))
        self.drain('E7', until=Job.EXTRACT)
        with mock.patch.object(adapter, 'get_interpreter', return_value=ScriptedInterpreter(UNKNOWN)):
            self.drain('E7 unknown', until=jobs.INTERPRET)
        run = Run.objects.get(encounter_id=pk, purpose=interpretation.PURPOSE, state=Run.UNKNOWN)
        self.reads('E7', 'unknown')
        self.post(f'/ops/api/encounters/{pk}/reconcile', {'provider_run_id': str(run.pk), 'note': NOTE},
                  client=self.operator, tag='E7')
        # the stages after an operator's reconciliation are requested by the operator, who is no member of the
        # workspace, so the live gate refuses Corti's send (the reconcile flow as it was before the migration)
        self.drain('E7 reconciled', expect=(Job.SUCCEEDED, Job.FAILED))
        self.reads('E7', 'reconciled')

    def stale_stage(self):
        """E8: the worker died while its interpret stage was sending; the exchange was answered and recorded. mark_stale
        settles the run from that exchange and the settled path reads it, with nothing sent."""
        pk = self.upload('E8', tagged(one_colonoscopy, 'E8'))
        self.drain('E8', until=Job.EXTRACT)
        job = Job.objects.get(encounter_id=pk, kind=jobs.INTERPRET)
        Job.objects.filter(pk=job.pk).update(state=Job.RUNNING, started_at=timezone.now() - timedelta(seconds=700),
                                             attempts=1)
        sending_with_an_answer(job, self.recordings[pk], self.case.user)
        self.matrix.call(('worker', 'mark_stale'), 'jobs.mark_stale', jobs.mark_stale, tag='E8')
        self.drain('E8 settled')
        self.reads('E8', 'settled')

    def addendum(self):
        """E1 again: an addendum makes a new revision, which is read (interpret, analyze, predict, assess)."""
        pk = self.ids['E1']
        self.post(f'/api/encounters/{pk}/addenda',
                  {'text': 'Addendum: the antral biopsy specimens were sent to pathology.',
                   'synthetic_attestation': 'yes'}, tag='E1')
        self.drain('E1 addendum')
        self.reads('E1', 'addendum')

    def interpreter_hold(self):
        """An interpreter hold on the failed reading's run: the operator reads it and releases it."""
        run = Run.objects.filter(encounter_id=self.ids['E6'], purpose=interpretation.PURPOSE).order_by('-created_at')[0]
        models.InterpreterHold.objects.create(reason=models.InterpreterHold.QUOTA, http_status=429, run=run)
        self.case.assertTrue(self.get('/ops/api/interpreter', client=self.operator, tag='held').json()['held'])
        self.post('/ops/api/interpreter', {'note': 'Synthetic release of the call-guard matrix hold.'},
                  client=self.operator, tag='release')
        self.case.assertFalse(holds.state()['held'])
        self.get('/ops/api/session', client=self.operator, tag='released')
        self.get('/ops/api/encounters', client=self.operator, tag='every encounter')

    def standing_answers(self):
        """E5 and E8: a member's answer to a question each still asks - 'cannot confirm' on E5's, 'not documented' on
        E8's - with the recompute it queues, left standing: the in-image scripts then meet new-path encounters holding
        a member answer (FINAL 10.4(1); the review of S12, finding 4: E1's, the world's only other one, is withdrawn
        before they run)."""
        for name, value in (('E5', 'cannot_confirm'), ('E8', 'not_documented')):
            pk = self.ids[name]
            rows = [item for item in self.detail(name, tag='before a standing answer')['details_needed']
                    if value in item['allow']]
            self.case.assertTrue(rows, f'{name} asks nothing a member can answer {value!r}')
            self.post(f'/api/encounters/{pk}/details',
                      {'answers': [{'id': rows[0]['id'], 'fact': rows[0]['fact'], 'value': value}]},
                      tag=f'{name} standing answer')
            self.drain(f'{name} standing answer')
            self.reads(name, 'standing answer')

    def sign_out(self):
        """A sign-in through the form and a sign-out (their own client)."""
        user = f.user('s12-sign-in')
        f.member(self.case.ws, user)
        client = Client()
        self.post('/login/', files={'username': user.username, 'password': 'synthetic-pass-123!'}, client=client,
                  expect=(302,))
        self.post('/logout/', client=client, expect=(302,))

    @staticmethod
    def standing() -> dict:
        """{encounter id: [when each was given]} of the members' answers that stand on an encounter's current revision -
        read from the rows, never through a reader (what the in-image scripts must name)."""
        out = {}
        for pk, revision, current, when in models.MemberAnswer.objects.filter(revocation__isnull=True).values_list(
                'encounter_id', 'revision_id', 'encounter__current_revision_id', 'answered_at'):
            if revision == current:
                out.setdefault(str(pk), []).append(when)
        return out

    def in_image(self, *, reassess='E1', answered=('E5', 'E8')):
        """Every in-image installer script and command the matrix drives (IN_IMAGE_EXEMPT: the others), each as the
        installer runs it; CLOSE_STAGES last, since it closes what is open. ``answered``: the encounters whose member's
        answer stands while they run (FINAL 10.4(1): each script runs on encounters holding 'a member answer'), which
        UNDO_HAZARDS names - exactly the standing answers - and CLOSE_STAGES' written_since names when given since the
        world began."""
        install = installer()
        every = [str(pk) for pk in models.Encounter.objects.order_by('created_at').values_list('pk', flat=True)]
        standing = self.standing()
        for name in answered:
            self.case.assertIn(self.ids[name], standing, f'{name} holds no standing answer when the scripts run')
        # each script read every encounter row (none answers about nothing)
        self.case.assertEqual(self.matrix.script('RECOMPUTE_STATES', {})['encounters'], len(every))
        self.case.assertEqual(self.matrix.script('RECOMPUTE_STATES', {'encounters': every}, tag='named')['encounters'],
                              len(every))
        hazards = self.matrix.script('UNDO_HAZARDS_READ', {})['hazards']
        self.matrix.observations[-1].detail['standing answers'] = len(standing)
        self.case.assertEqual(sorted(pk for pk, reasons in hazards.items() if 'member_answer' in reasons),
                              sorted(standing), hazards)
        self.matrix.script('UNRUNNABLE_STAGES', {})
        made = self.matrix.script('INTERPRETATION_MADE', {})['interpretation']
        derived = {str(pk) for pk in models.EncounterContext.objects.filter(event_inventory__isnull=False)
                   .values_list('encounter_id', flat=True)}
        self.case.assertEqual(set(made['encounters']), derived)  # it named every encounter read on the new path
        self.matrix.script('INSTALLED_STATES', {'encounters': every})
        self.case.assertEqual(len(self.matrix.script('REASSESS_JOBS', {'encounters': every})['encounters']), len(every))
        self.matrix.script('LICENSE_NOTE_FIX', {'old': install.LICENSE_NOTE_OLD, 'new': install.LICENSE_NOTE_NEW})
        folder = Path(tempfile.mkdtemp(prefix='s12-operators-'))
        try:
            (folder / 'op.pw').write_text(OPERATOR_PASSWORD, encoding='utf-8')
            self.matrix.script('OPERATOR_ACCOUNTS', {'accounts': [
                {'username': 's12-operator-account', 'kind': models.User.HUMAN, 'display_name': 'S12 operator',
                 'password_file': str(folder / 'op.pw')}], 'reset': False})
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        self.matrix.script('OPERATOR_CHECK', {'usernames': ['s12-operator-account']})
        self.matrix.command('migrate', '--check')
        self.matrix.command('interpretation_report', '--since', self.started.isoformat(), '--self-test', '--json')
        self.matrix.command('reassess_retained', '--encounter', self.ids[reassess], '--tag', 'synthetic-s12-matrix',
                            '--participants', 'none')
        self.drain('reassess_retained')
        self.post(f'/api/encounters/{self.ids[reassess]}/context', {'setting': 'office'}, tag=f'{reassess} left queued')
        closed = self.matrix.script('CLOSE_STAGES', {'since': self.started.isoformat(),
                                                     'note': 'Closed by the synthetic undo.',
                                                     'kinds': list(install.COMMON_STAGE_KINDS)})
        self.case.assertGreaterEqual(closed['closed'], 1)  # the stage left queued above, at least
        # written_since's member-answer arm on the answers given since the world began (its window), none before
        written = sorted(pk for pk, reasons in (closed.get('written_since') or {}).items()
                         if 'member_answer' in reasons)
        self.case.assertEqual(written, sorted(pk for pk, times in self.standing().items()
                                              if max(times) >= self.started), closed.get('written_since'))


def sending_with_an_answer(job, body: bytes, user):
    """The run a worker that died mid-send leaves (tests/test_pipeline_interpret.py's StaleSweepTests): SENDING, its one
    exchange recorded succeeded with HTTP 200 and ``body``."""
    revision = job.revision
    request = adapter.build_request(revision.text, jobs._participant_pages(revision),
                                    jobs._participant_document(revision)[0])
    run = Run.objects.create(
        encounter=job.encounter, revision=revision, provider=interpretation.PROVIDER,
        adapter_version=interpretation.ADAPTER_VERSION, request_sha256=request.canonical_sha256,
        request_body=request.body, contexts=list(request.contexts), state=Run.SENDING, sent=True,
        purpose=interpretation.PURPOSE, scope={'mode': 'replay'}, endpoint=ScriptedInterpreter.endpoint,
        requested_model=interpretation.MODEL, started_at=timezone.now(), authorization_ref=AUTH, requested_by=user)
    models.ProviderExchange.objects.create(
        run=run, turn=1, request_body=request.body, request_sha256=request.canonical_sha256, state='succeeded',
        http_status=200, response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest(), usage=dict(USAGE),
        response_id='synthetic-s12', started_at=timezone.now(), finished_at=timezone.now())
    return run


def in_process_children():
    """bounded.run_bounded made to run its function in this process (no fork): what a legacy stage's bounded child runs
    is then counted under the scope its stage runs in (the positive control's legacy chain)."""
    return mock.patch.object(bounded, 'run_bounded', side_effect=lambda fn, *args, seconds, memory_bytes: fn(*args))


# --- the legacy records (FINAL 10.4(2), 14.6) ------------------------------------------------------------------------

class LegacyWorld:
    """Encounters the legacy reader read, made through the test-only legacy chain (``legacy_chain``): each document
    uploaded through POST /api/encounters and read by the legacy stages - L5 with Astra and Fable configured - then a
    member's acts on the legacy records, the states FINAL 10.4(1) names, each one asserted offered by the legacy reading
    and made (``check``; never skipped where a reading does not offer it): on L1 an approval and a rejection, on L2 the
    reinstatement of its excluded code, on L3 a member's answer that stands, on L4 an answer given and withdrawn, on L6
    an approval carrying the reviewer's modifier, and on L5 the second review its reading offers, asked and run. Built
    through a World over ``matrix`` (an unobserved one by default), with the chain on."""
    SCENARIOS = (('L1', two_procedures), ('L2', denied_removal), ('L3', one_colonoscopy), ('L4', two_lesions),
                 ('L5', one_colonoscopy), ('L6', legacy_pair))
    PARTICIPANTS = ('L5',)  # read with Astra and Fable configured: their readings, peer reviews and a second review
    ANSWERED = ('L3',)  # a member's answer that stands when the reads run
    WITHDRAWN = ('L4',)  # a member's answer given and withdrawn
    MODIFIER = 'L6'  # an approval carrying the reviewer's chosen modifier

    def __init__(self, case, matrix=None, *, operator=None):
        self.world = World(case, matrix if matrix is not None else Matrix(case), operator=operator)

    def build(self):
        world = self.world
        with legacy_chain():
            for name, scenario in self.SCENARIOS:
                with participants() if name in self.PARTICIPANTS else contextlib.nullcontext():
                    world.upload(name, tagged(scenario, name))
                    world.drain(name)
                assessment = world.encounter(name).current_assessment
                world.case.assertIsNotNone(assessment, name)
                world.case.assertFalse(interpretation.is_new_assessment(assessment), name)
            self.act(world)
        self.check(world)
        return world

    def check(self, world):
        """That every act on the legacy records happened (the review of S12, finding 1: an act the reading did not
        offer was skipped in silence): a member's answer that stands and one withdrawn, an approval, a rejection, a
        reinstatement and an approval with the reviewer's modifier, the participants' readings and peer reviews and a
        second review - and every current assessment still the legacy reader's."""
        case, ids = world.case, {name: world.ids.get(name) for name, _ in self.SCENARIOS}
        answers = models.MemberAnswer.objects.filter(encounter_id__in=[pk for pk in ids.values() if pk])
        case.assertEqual(sorted(str(pk) for pk in answers.filter(revocation__isnull=True)
                                .values_list('encounter_id', flat=True)),
                         sorted(ids[name] for name in self.ANSWERED), 'the standing answers on the legacy records')
        case.assertEqual(sorted(str(pk) for pk in answers.filter(revocation__isnull=False)
                                .values_list('encounter_id', flat=True)),
                         sorted(ids[name] for name in self.WITHDRAWN), 'the withdrawn answers on the legacy records')
        decisions = models.Decision.objects.filter(encounter_id__in=[pk for pk in ids.values() if pk])
        case.assertLessEqual({'approve', 'reject', 'reinstate'}, set(decisions.values_list('action', flat=True)))
        case.assertTrue([item for item in decisions.filter(action='approve', encounter_id=ids[self.MODIFIER])
                         if item.modifiers], 'no approval with a modifier on the legacy records')
        purposes = set(Run.objects.filter(encounter_id__in=[ids[name] for name in self.PARTICIPANTS],
                                          state=Run.SUCCEEDED).values_list('purpose', flat=True))
        case.assertLessEqual({Run.PRIMARY, Run.INDEPENDENT, Run.PEER_REVIEW, Run.SECOND_REVIEW}, purposes)
        for name, pk in ids.items():
            assessment = models.Encounter.objects.get(pk=pk).current_assessment
            case.assertIsNotNone(assessment, name)
            case.assertFalse(interpretation.is_new_assessment(assessment), name)

    @staticmethod
    def allowed(world, name, action):
        """The code rows of ``name``'s customer page that allow ``action`` now."""
        payload = world.detail(name, tag=f'legacy {action}')
        return [row for row in payload['codes'] if action in row['allowed_actions']], payload

    def act(self, world):
        case = world.case
        [approvable] = self.allowed(world, 'L1', 'approve')[0]
        world.decide('L1', approvable['code'], 'approve', tag='legacy')
        rejectable = [row for row in self.allowed(world, 'L1', 'reject')[0] if row['code'] != approvable['code']]
        case.assertTrue(rejectable, 'the legacy reading of L1 offers no rejection')
        world.decide('L1', rejectable[0]['code'], 'reject', tag='legacy')
        reinstatable = self.allowed(world, 'L2', 'reinstate')[0]
        case.assertTrue(reinstatable, 'the legacy reading of L2 offers no reinstatement')
        world.decide('L2', reinstatable[0]['code'], 'reinstate', tag='legacy')
        for name in self.ANSWERED + self.WITHDRAWN:
            answer_id = self.answer(world, name)
            if name in self.WITHDRAWN:
                world.post(f'/api/encounters/{world.ids[name]}/details/{answer_id}/revoke', tag=f'{name} legacy')
                world.drain(f'{name} legacy answer withdrawn')
        offered = [row for row in self.allowed(world, self.MODIFIER, 'approve')[0] if row.get('modifier_review')]
        case.assertTrue(offered, f'the legacy reading of {self.MODIFIER} offers no approval with a modifier')
        world.decide(self.MODIFIER, offered[0]['code'], 'approve', tag='legacy modifier',
                     modifiers=[offered[0]['modifier_review']['options'][0]])
        with participants():
            for name in self.PARTICIPANTS:
                payload = world.detail(name, tag='legacy second-review offer')
                case.assertTrue(payload['recheck']['available'], (name, payload['recheck']))
                world.post(f'/api/encounters/{world.ids[name]}/second-review', tag=f'{name} legacy')
                world.drain(f'{name} legacy second review')

    @staticmethod
    def answer(world, name) -> str:
        """A member's 'not documented' to the first question ``name``'s legacy reading asks that takes one, with the
        recompute it queues run; the answer's id."""
        rows = [item for item in world.detail(name, tag='legacy answer')['details_needed']
                if 'not_documented' in item['allow']]
        world.case.assertTrue(rows, f'the legacy reading of {name} asks nothing a member can answer')
        saved = world.post(f'/api/encounters/{world.ids[name]}/details',
                           {'answers': [{'id': rows[0]['id'], 'fact': rows[0]['fact'], 'value': 'not_documented'}]},
                           tag=f'{name} legacy answer')
        world.drain(f'{name} legacy answer')
        [answer_id] = saved.json()['answer_ids']
        return answer_id


def participants():
    """Astra and Fable configured (their scripted replay adapters, GuardCase's participant_codes)."""
    return override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')


# --- a TransactionTestCase with EventsCase's fixtures (the byte-identity test reads committed rows) -------------------

PIPELINE_SETTINGS = dict(GEMINI_MODE='replay', PROVIDER_MODE='live', AUTHORIZATION_REF=AUTH, ASTRA_MODE='disabled',
                         FABLE_MODE='disabled', INTERPRET_MAX_CHARS=20_000, INTERPRET_MAX_PAGES=40,
                         STORAGES=PLAIN_STATIC)


class Pipeline:
    """EventsCase's fixtures - Gemini replayed, Corti faked, Astra and Fable scripted - for a class that cannot be an
    EventsCase (a TransactionTestCase); decorate it with override_settings(**PIPELINE_SETTINGS), EventsCase's own."""
    corti_groups = GuardCase.corti_groups
    participant_codes = GuardCase.participant_codes
    setUp = EventsCase.setUp
    adapter = EventsCase.adapter

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        status = sentinel.install()
        assert status['state'] == 'ok', status


# --- the c2e53f8e code, and the reads both trees make (FINAL 10.4(2), 14.3) ------------------------------------------

BASELINE = 'c2e53f8e7d33732d5badd4ce9b681f274eb5c471'  # the rollback image cpt-studio:c2e53f8e7d33 (DECISIONS D15)
# The c2e53f8e app code, whole: the sha256 of its MANIFEST (``manifest``: every file under cpt-studio/studio, cptstudio
# and manage.py, as `git archive` of the commit extracts them, by path and sha256) and its file count, computed once
# from the archive. A tree is that code only when every file it holds there is that code's and nothing else is (the
# review of S12, finding 6: seven pinned files let a tree with a later serializers.py - or a file added, removed or
# linked - pass as that code).
BASELINE_ROOTS = ('studio', 'cptstudio', 'manage.py')
BASELINE_MANIFEST = 'affd84a34c84e8affd7d945eb3965fb7a32e3db2f7135bd5a9066937271a884a'
BASELINE_FILES = 115
# sha256 of the files of the c2e53f8e app the reads lean on most: no longer what decides (BASELINE_MANIFEST is), they
# say WHICH of them differ when a tree is refused
BASELINE_PINS = {
    'studio/models.py': '828129928b9465dc4e024d5f56b0d29429cfaa57dfdec5e2b2fc0d2f095dd5e1',
    'studio/review.py': '227ef6c26e08c5bc1ab7a3ecd2bb8e337037a6247295867a6d2d6b67ccf78014',
    'studio/customer_api.py': '62d54aa775e62a3940a6cf46087c7d4d718606c41ca2f0e0d9bb22ec1e5e80cf',
    'studio/reports.py': 'bc356f5fb739a0acf4648d349cb70a58608c595f8f0ef1268c39d3e176567b31',
    'studio/validation/review_view.py': 'fef41c35bd2ebf7761c90f9918f8951f5ced83def5acaf39a005c787e2047ec1',
    'studio/validation/engine.py': '89a982c19b008270ad19bf303615f374e4a0e1801b7a77ce82fa60652e9c4219',
    'cptstudio/settings.py': '0b243ae820d49414ed790fb03dd03aeb3e6dd0fbb66a8c83ca50a00dc7af8f06',
}


def _pinned(tree: Path) -> list:
    """The pinned files of ``tree`` that are not the c2e53f8e code's."""
    wrong = []
    for name, digest in BASELINE_PINS.items():
        path = tree / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            wrong.append(name)
    return wrong


def manifest(tree: Path):
    """(the sha256 of ``tree``'s manifest, its file count, what it holds that is no file): every regular file under
    BASELINE_ROOTS as one 'sha256  path' line, sorted by path. A link (or anything else that is no file or folder) is
    never a file of the archive: it is listed apart, never followed, so a tree holding one is refused."""
    files, odd = [], []
    for root in BASELINE_ROOTS:
        top = tree / root
        if top.is_symlink() or not top.exists():
            odd += [root] if top.is_symlink() else []
            continue
        if top.is_file():
            files.append((root, hashlib.sha256(top.read_bytes()).hexdigest()))
            continue
        for folder, folders, names in os.walk(top):  # never into a linked folder: os.walk does not follow links
            for name in folders + names:
                path = Path(folder) / name
                relative = path.relative_to(tree).as_posix()
                if path.is_symlink() or not (path.is_dir() or path.is_file()):
                    odd.append(relative)
                elif path.is_file():
                    files.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    text = ''.join(f'{digest}  {name}\n' for name, digest in sorted(files))
    return hashlib.sha256(text.encode()).hexdigest(), len(files), sorted(odd)


def _not_baseline(tree: Path) -> str:
    """'' when ``tree`` is the c2e53f8e code, file for file; else why it is not."""
    digest, count, odd = manifest(tree)
    why = []
    if odd:
        why.append(f'it holds {len(odd)} link(s) or other non-file(s), {odd[:3]}')
    if (digest, count) != (BASELINE_MANIFEST, BASELINE_FILES):
        why.append(f'its {count} files hash to {digest[:16]}, not the c2e53f8e code\'s {BASELINE_FILES} '
                   f'({BASELINE_MANIFEST[:16]})')
    wrong = _pinned(tree) if why else []
    if wrong:
        why.append(f'of the pinned files, these differ: {wrong}')
    return '; '.join(why)


def baseline_tree(scratch: Path):
    """(the c2e53f8e app code as a directory, where it came from), or (None, why not): ``git archive`` of the commit
    when this repository's history holds it, else the tree CPT_STUDIO_BASELINE_TREE names - either one checked whole
    against BASELINE_MANIFEST (every file, nothing missing, nothing added, no link). A CI clone may hold no history:
    then nothing is compared, and the caller says so."""
    repo = APP.parent
    try:
        found = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', '--quiet', f'{BASELINE}^{{commit}}'],
                               capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        found = None
    if found is not None and found.returncode == 0 and found.stdout.strip() == BASELINE:
        archive = subprocess.run(['git', '-C', str(repo), 'archive', BASELINE, 'cpt-studio/studio',
                                  'cpt-studio/cptstudio', 'cpt-studio/manage.py'], capture_output=True, timeout=120)
        if archive.returncode == 0:
            with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
                tar.extractall(scratch, filter='data')
            tree = scratch / 'cpt-studio'
            problem = _not_baseline(tree)
            if problem:
                return None, f'the archive of {BASELINE} is not the c2e53f8e code pinned here: {problem}'
            return tree, f'git archive {BASELINE}'
    named = os.environ.get('CPT_STUDIO_BASELINE_TREE', '')
    if named:
        problem = _not_baseline(Path(named))
        return (Path(named), f'CPT_STUDIO_BASELINE_TREE={named}') if not problem else \
            (None, f'CPT_STUDIO_BASELINE_TREE is not the c2e53f8e code: {problem}')
    return None, (f'this repository holds no commit {BASELINE} and CPT_STUDIO_BASELINE_TREE names no tree (a shallow '
                  'clone): the reads are not compared with the c2e53f8e code here')


# The reads both trees make, in a process of their own over the same committed rows and at the same instant (the
# clock, django.utils.timezone.now, held at params['now'] in both: a page states the server's time): the customer's
# pages (the detail, the list, the session) as served, the review overlay's views, the reviewed coverage and the
# readiness, and both report renderers (the operator's and the customer's, draft and - where the rows allow -
# reviewed or approved). Every value is bytes: a response body, a JSON dump made the same way in both trees, or a
# renderer's output (the customer renderer is handed one fixed 'generated' argument in both).
READS = r"""
import base64, datetime, json, sys
from unittest import mock
import django
django.setup()
from django.test.utils import setup_test_environment
setup_test_environment()
from django.test import Client
from studio import client_contract, models, reports, review
from studio.types import to_jsonable

params = json.loads(sys.argv[1])
mock.patch('django.utils.timezone.now', return_value=datetime.datetime.fromisoformat(params['now'])).start()
out = {}


def dump(value):
    return json.dumps(to_jsonable(value), sort_keys=True, default=repr).encode()


def keep(name, make):
    try:
        out[name] = make()
    except Exception as exc:  # the same refusal in both trees reads the same
        out[name] = f'{type(exc).__name__}: {exc}'.encode()


client = Client(**{client_contract.WSGI_KEY: client_contract.VERSION})
client.force_login(models.User.objects.get(pk=params['user']))
for path in params['paths']:
    response = client.get(path)
    out['GET ' + path] = str(response.status_code).encode() + b' ' + response.content
for pk in params['encounters']:
    encounter = models.Encounter.objects.get(pk=pk)
    assessment = review.live_assessment(encounter)
    current = review.current_decisions(assessment)
    keep('views ' + pk, lambda: dump(review.effective_view(assessment, current)))
    keep('completeness ' + pk, lambda: dump(review.reviewed_completeness(assessment, current)))
    keep('readiness ' + pk, lambda: dump(review.readiness(encounter)))
    for kind in ('draft', 'reviewed'):
        def operator(kind=kind):
            snap = reports.snapshot(encounter, kind)
            return reports.render_txt(snap) + b'\n---\n' + reports.render_csv(snap)
        keep('operator report ' + kind + ' ' + pk, operator)
    for kind in ('draft', 'approved'):
        def customer(kind=kind):
            snap = reports.customer_snapshot(encounter, kind)
            return b'\n---\n'.join(reports.CUSTOMER_RENDERERS[fmt](snap, {'at': 'fixed', 'by': 'fixed'})
                                   for fmt in ('txt', 'csv'))
        keep('customer report ' + kind + ' ' + pk, customer)
print('READS ' + json.dumps({name: base64.b64encode(value).decode() for name, value in out.items()}))
"""


def reads(tree: Path, params: dict) -> dict:
    """{read: bytes} of READS run by the app in ``tree`` over this test database's committed rows."""
    from django.db import connection

    db = connection.settings_dict
    env = {**os.environ, 'PYTHONPATH': str(tree), 'DJANGO_SETTINGS_MODULE': 'cptstudio.settings', 'PYTHONHASHSEED': '0',
           'PYTHONDONTWRITEBYTECODE': '1', 'CPT_STUDIO_DB_NAME': db['NAME'], 'CPT_STUDIO_DB_USER': db['USER'],
           'CPT_STUDIO_DB_PASSWORD': db['PASSWORD'], 'CPT_STUDIO_DB_HOST': db['HOST'],
           'CPT_STUDIO_DB_PORT': str(db['PORT']), 'CPT_STUDIO_STATE_DIR': str(settings.STATE_DIR),
           'CPT_STUDIO_PROVIDER_MODE': 'disabled'}
    completed = subprocess.run([sys.executable, '-B', '-c', READS, json.dumps(params)], cwd=tree, env=env,
                               capture_output=True, text=True, timeout=600)
    lines = [line for line in completed.stdout.splitlines() if line.startswith('READS ')]
    if completed.returncode or len(lines) != 1:
        raise AssertionError(f'the reads failed in {tree} (exit {completed.returncode}):\n{completed.stderr[-4000:]}')
    return {name: base64.b64decode(value) for name, value in json.loads(lines[0][len('READS '):]).items()}
