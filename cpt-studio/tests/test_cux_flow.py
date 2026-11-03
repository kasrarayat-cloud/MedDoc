"""P5 FLOW (owner directive 2026-11-03, sections 4-6; DESIGN section 6): the document's own date recorded beside the
member's, the "A few details needed" rows and their one save, the member's answers and their withdrawal, the progress
fold, the upload key, and the re-assessment from retained answers. DB-backed; synthetic data only; nothing is sent (the
pipeline's provider is disabled, or the in-process fakes of the harness suites).
"""
import dataclasses
import hashlib
import io
import json
import re
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import answers, intake, jobs, models, progress, review
from studio.gi import context as gi_context
from studio.types import ExtractionResult, PageSpan, sha256_json
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_pipeline_api import FakeProvider, drain

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
MARA = (FIXTURES / 'cux' / 'mara' / 'rev1.txt').read_text(encoding='utf-8')
H208 = (FIXTURES / 'gi3' / 'live-text' / 'h2-08__e084b793__2026-10-29.txt').read_text(encoding='utf-8')
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
TWO_DATES = (HEAD + 'Office visit\nDate of service: 2026-10-20\nPlace of service: office\nDate of service: 2026-10-21\n'
             'Assessment: reflux.\n')
ELSEWHERE = HEAD + 'Office visit\nNext procedure date: 11/04/2026\nAssessment: reflux.\n'
LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')


def run_stages(count):
    """Claim and run the next ``count`` queued stages (the worker's loop, in process)."""
    for _ in range(count):
        job = jobs.claim_next()
        assert job is not None, 'no stage was queued'
        jobs.run_job(job)


def pasted(text, *, service_date='', title='Synthetic note'):
    """An encounter made through intake, as an upload makes it (its extract stage queued)."""
    ws = f.workspace()
    user = f.member(ws, f.user(f'reviewer{uuid.uuid4().hex[:8]}'))
    membership = models.Membership.objects.get(user=user, workspace=ws)
    return intake.create_encounter(membership=membership, user=user, title=title, service_date=service_date, text=text)


class DocumentDateTests(TestCase):
    """EncounterContext.document_date: the document's own service date fact before a member's value is merged (R2 4.4,
    Q-6), from the facts the bounded child returned; never a date the document does not state as its own."""

    def test_the_analyze_stage_records_mara_s_own_date_beside_a_conflicting_member_date(self):
        encounter = pasted(MARA, service_date='1998-01-01')
        run_stages(2)  # extract, analyze
        encounter.refresh_from_db()
        context, revision = encounter.current_context, encounter.current_revision
        self.assertTrue(gi_context.is_member_conflict(context.facts['service_date']))
        document = context.document_date
        self.assertEqual((document['origin'], document['value'], document['single'], document['values'],
                          document['asked']), ('document', '2026-11-03', True, ['2026-11-03'], False))
        quote = document['quote']
        self.assertEqual(quote['text'], 'Date of service 2026-11-03')
        self.assertEqual(revision.text[quote['start']:quote['end']], quote['text'])
        self.assertEqual(len(document['evidence']), 3)  # the page header's three "Date of service 2026-11-03"
        # beside the context, outside its sha256: the hash is exactly the one its facts, member values and revision make
        self.assertEqual(context.sha256, sha256_json({'facts': context.facts, 'user_values': context.user_values,
                                                      'revision': str(revision.pk)}))
        # the same reading as reading the text itself
        self.assertEqual(document, gi_context.document_service_date_fact(revision.text))

    def test_only_dates_the_document_states_as_its_own_are_values(self):
        cases = {
            'two_own_dates': (TWO_DATES, ('conflict', None, False, ['2026-10-20', '2026-10-21'], False)),
            'another_occurrence_only': (ELSEWHERE, ('missing', None, False, [], False)),
            'charge_block_question': (H208, ('conflict', None, False, ['2026-10-05'], True)),
            'no_date': (HEAD + 'Office visit\nAssessment: reflux.\n', ('missing', None, False, [], False)),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(name):
                document = gi_context.document_service_date_fact(text, facts=gi_context.extract_context(text))
                self.assertEqual(tuple(document[k] for k in ('origin', 'value', 'single', 'values', 'asked')), expected)
                self.assertIsNone(document['quote'])
        # "Next procedure date: 11/04/2026" is another occurrence's date: never a value, whatever a member enters
        self.assertNotIn('2026-11-04', json.dumps(gi_context.document_service_date_fact(ELSEWHERE)['values']))

    def test_every_context_the_pipeline_makes_records_it_and_a_member_s_save_too(self):
        encounter = pasted(pf.GI_NOTE)
        drain()
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_context.document_date['value'], '2026-10-21')
        reviewer = encounter.created_by
        saved = jobs.change_context(encounter, reviewer, {'service_date': '1998-01-01'})
        self.assertEqual(saved.document_date['value'], '2026-10-21')  # the document's own, not the member's
        self.assertTrue(gi_context.is_member_conflict(saved.facts['service_date']))
