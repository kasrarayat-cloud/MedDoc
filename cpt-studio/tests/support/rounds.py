"""Synthetic scenarios for the customer API, decisions, exports and the operator console (lane B of the Fable coding
build). Synthetic text only; no real document, no network: a round is either coded through the real pipeline with a
fake coder (tests.support.coding) or written directly in the shape studio.jobs stores."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import Client, override_settings
from django.utils import timezone

from studio import audit, jobs, models, state
from studio.fable import client as fable_client
from tests.support import coding as f

Round = models.CodingRound
ROOT = Path(settings.BASE_DIR)


def scan_customer():
    """ops/scan_customer.py, the shipped reader of the contract and the denylist (loaded from its file: ops is no
    package)."""
    name = 'laneb_scan_customer'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / 'ops' / 'scan_customer.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def denylist():
    return json.loads((ROOT / 'ops' / 'verification' / 'customer-denylist.json').read_text(encoding='utf-8'))


# A reader and checker pair for a done round: a ready code, a code needing an answer, a code the checker disputes and
# a code the checker added; quotes cited on pages 1 and 2.
READER = f.reader_result(
    [f.code('45385', 'ready', reason='A 6 mm sigmoid polyp was removed by cold snare.'),
     f.code('45380', 'needs_answer', question='Was a biopsy taken from a separate site?',
            reason='A biopsy may have been taken.'),
     f.code('43239', 'ready', reason='An upper endoscopy with biopsy is documented.'),
     f.code('43251', 'not_supported', reason='No snare was used in the upper tract.')],
    questions=[{'question': 'Was a biopsy taken from a separate site?', 'affects': ['45380']}],
    problems=['The note is not signed.'])
CHECKER = f.checker_result(
    [f.review('45385', 'agree', reason='The snare removal is documented.'),
     f.review('45380', 'agree', status='needs_answer'),
     f.review('43239', 'disagree', reason='The biopsy site is not stated.'),
     f.review('43251', 'agree', status='not_supported')],
    missed=[{'code': '45378', 'units': 1, 'modifiers': [], 'status': 'ready',
             'reason': 'A diagnostic colonoscopy is documented.', 'evidence': [{'quote': 'colonoscopy to the cecum',
                                                                                'page': 1}], 'question': None}],
    questions=[{'question': 'Which site was biopsied during the upper endoscopy?', 'affects': ['43239']}])


class CustomerCase:
    """Mixin for a TestCase: an originals directory of its own, a workspace with a reviewer, a viewer and an agent, and
    a member of another workspace."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._originals = tempfile.TemporaryDirectory()
        cls._override = override_settings(ORIGINALS_DIR=Path(cls._originals.name))
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._originals.cleanup()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.ws = f.workspace('Gastroenterology')
        self.reviewer = f.member(self.ws)
        self.viewer = f.member(self.ws, role=models.Membership.VIEWER)
        self.agent = f.member(self.ws)
        models.User.objects.filter(pk=self.agent.pk).update(actor_kind=models.User.AGENT, display_name='Reviewbot')
        self.agent.refresh_from_db()
        self.other_ws = f.workspace('Another practice')
        self.outsider = f.member(self.other_ws)

    def client_for(self, user, **kwargs):
        client = Client(**kwargs)
        client.force_login(user)
        return client

    def use(self, fake):
        patcher = mock.patch.object(fable_client, 'coder', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def run_next(self):
        job = jobs.claim_next()
        assert job is not None, 'no job was queued'
        jobs.run_job(job)
        return job

    def code_round(self, encounter, reader=READER, checker=CHECKER):
        """Run the encounter's queued round through the real stage with a fake coder answering ``reader`` and
        ``checker``; the round, read again."""
        self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(reader)),
                             checker=f.succeeded(f.checker_message(checker))))
        self.run_next()
        return state.latest_round(encounter)

    def encounter(self, *, user=None, title='Synthetic colonoscopy note', service_date='2026-11-02',
                  insurance='medicare', pdf=True):
        """An encounter with revision 1 (an uploaded PDF, or pasted text) and NO round yet."""
        user = user or self.reviewer
        enc = f.encounter(self.ws, user, service_date=service_date, insurance=insurance, title=title)
        revision = f.upload(enc, user) if pdf else f.paste(enc, user)
        audit.record(self.ws, 'encounter.created', encounter=enc, actor=user, kind=revision.kind)  # as intake does
        return enc

    def started(self, **kwargs):
        """An encounter whose round 1 is queued (trigger upload)."""
        enc = self.encounter(**kwargs)
        jobs.start_round(enc, enc.current_revision, Round.UPLOAD, enc.created_by)
        return enc

    def done(self, **kwargs):
        """An encounter whose round 1 was coded (READER and CHECKER) through the pipeline."""
        enc = self.started(**kwargs)
        self.code_round(enc)
        enc.refresh_from_db()
        return enc


def write_round(encounter, *, state_=Round.DONE, codes=(), questions=(), problems=(), citations=None, trigger=None,
                failure_kind='', error=''):
    """A round written directly in the shape studio.jobs stores, the encounter's state refreshed."""
    last = Round.objects.filter(encounter=encounter).order_by('-number').first()
    number = last.number + 1 if last else 1
    now = timezone.now()
    round_ = Round.objects.create(
        encounter=encounter, revision=encounter.current_revision, number=number,
        trigger=trigger or (Round.UPLOAD if number == 1 else Round.ANSWERS),
        context=jobs.context_snapshot(encounter), state=state_, codes=list(codes), questions=list(questions),
        problems=list(problems), citations=citations or {}, failure_kind=failure_kind, error=error,
        started_at=now, finished_at=now if state_ in (Round.DONE, Round.FAILED, Round.CANCELLED) else None)
    state.refresh(encounter)
    return round_


def row(code, status, *, reason='Documented.', units=1, modifiers=(), question=None, agrees=True,
        check_reason='Agreed.', evidence=None, listed_by='reader'):
    """One combined code row as studio.fable.result.combine stores it."""
    check = None if listed_by == 'checker' else {
        'agrees': agrees, 'verdict': None if agrees is None else ('agree' if agrees else 'disagree'),
        'reason': check_reason if agrees is not None else None, 'question': None, 'correct_code': code,
        'correct_units': units, 'correct_modifiers': list(modifiers), 'correct_status': status, 'evidence': []}
    return {'code': code, 'units': units, 'modifiers': list(modifiers), 'listed_status': status, 'reason': reason,
            'question': question, 'evidence': evidence if evidence is not None else [{'quote': 'evidence quote',
                                                                                     'page': 1}],
            'status': status, 'listed_by': listed_by, 'second_check': check}
