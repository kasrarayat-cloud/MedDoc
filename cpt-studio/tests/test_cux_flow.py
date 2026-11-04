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

from studio import answers, intake, jobs, models, review
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


# --- the "A few details needed" rows and their one save (answers.py; POST /api/encounters/<id>/details) --------------

COLON, OFFICE = 'gi.colonoscopy', 'gi.office_em'


def asks(key, code, passage, *facts, family=COLON):
    """A selected proposal held on ``facts`` (proposal-scoped questions)."""
    return pf.proposal(key, code, [passage], status='needs_clarification', clarifications=tuple(
        pf.clarification(fact, scope='proposal', family=family, proposal_key=key) for fact in facts))


def ready(key, code, passage):
    return pf.proposal(key, code, [passage])


class DetailsCase(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.s.reviewer)

    def assess(self, *proposals, questions=()):
        return pf.assess(self.s.encounter, pf.result(*proposals, clarifications=questions))

    def rows(self, assessment=None):
        self.s.encounter.refresh_from_db()
        return answers.details_needed(self.s.encounter, assessment or self.s.encounter.current_assessment)

    def row(self, fact, code='', family=None, assessment=None):
        family = (COLON if code else '') if family is None else family
        return next(r for r in self.rows(assessment) if r['id'] == answers.detail_id(fact, family, code))

    def post(self, items, client=None, raw=None):
        body = json.dumps(raw if raw is not None else {'answers': items})
        return (client or self.client).post(f'/api/encounters/{self.s.encounter.pk}/details', data=body,
                                            content_type='application/json')

    def answer(self, row, value):
        return {'id': row['id'], 'fact': row['fact'], 'value': value}

    def counts(self):
        return {'contexts': models.EncounterContext.objects.count(), 'jobs': models.Job.objects.count(),
                'assessments': models.Assessment.objects.count(), 'answers': models.MemberAnswer.objects.count(),
                'revocations': models.MemberAnswerRevocation.objects.count(),
                'audit': models.AuditEvent.objects.filter(event__startswith='detail.').count()}


class DetailRowsTests(DetailsCase):
    def test_one_row_per_open_question_de_duplicated_by_fact_family_and_code(self):
        first = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'), ready('sel:1', '45380', pf.CECUM_PASSAGE),
                            questions=[pf.clarification('setting', scope='service', family=OFFICE)])
        # the re-assessment asks the same 45385 question twice (two proposals of one code), a new one about 45380, the
        # date and the service question again: the first assessment's re-raised rows stay open and are not read twice
        second = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'),
                             asks('sel:1', '45385', pf.SNARE_PASSAGE, 'extent'),
                             asks('sel:2', '45380', pf.CECUM_PASSAGE, 'extent'),
                             questions=[pf.clarification('service_date', scope='encounter'),
                                        pf.clarification('setting', scope='service', family=OFFICE)])
        self.assertNotEqual(first, second)
        self.assertGreater(models.Clarification.objects.filter(state='open', assessment=first).count(), 0)
        rows = self.rows()
        self.assertEqual([(r['fact'], r['affects']) for r in rows],
                         [('service_date', ['45385', '45380']), ('setting', []), ('extent', ['45385']),
                          ('extent', ['45380'])])
        self.assertEqual(len({r['id'] for r in rows}), 4)
        self.assertEqual(rows[2]['id'], answers.detail_id('extent', COLON, '45385'))
        self.assertEqual(set(rows[0]), {'id', 'fact', 'family_label', 'prompt', 'control', 'choices', 'allow',
                                        'document_value', 'entered_value', 'quote', 'affects', 'saved',
                                        'addendum_allowed'})

    def test_the_control_follows_the_fact(self):
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent', 'conflict:biopsy', 'billing_context'),
                    asks('sel:1', '45380', pf.CECUM_PASSAGE, 'base_included', 'performed_status'),
                    questions=[pf.clarification('service_date', scope='encounter'),
                               pf.clarification('setting', scope='service', family=OFFICE),
                               pf.clarification('patient_status', scope='service', family=OFFICE),
                               pf.clarification('em_basis', scope='service', family=OFFICE)])
        rows = {(r['fact'], r['affects'][0] if r['affects'] and r['fact'] != 'service_date' else ''): r
                for r in self.rows()}
        self.assertEqual({key: r['control'] for key, r in rows.items()}, {
            ('service_date', ''): 'date', ('setting', ''): 'choice', ('patient_status', ''): 'choice',
            ('em_basis', ''): 'confirm', ('extent', '45385'): 'confirm', ('conflict:biopsy', '45385'): 'confirm',
            ('billing_context', '45385'): 'choice', ('base_included', '45380'): 'confirm',
            ('performed_status', '45380'): 'confirm'})
        setting = rows[('setting', '')]
        self.assertEqual([c['value'] for c in setting['choices']], list(gi_context.SETTINGS))
        self.assertEqual(setting['allow'], ['not_documented'])  # "Not documented", never "Cannot confirm" here
        self.assertEqual(setting['family_label'], 'Office / outpatient evaluation and management')
        self.assertFalse(setting['addendum_allowed'])
        self.assertEqual([c['value'] for c in rows[('billing_context', '45385')]['choices']],
                         list(gi_context.BILLING_CONTEXTS))
        for key in (('em_basis', ''), ('extent', '45385'), ('conflict:biopsy', '45385'), ('base_included', '45380'),
                    ('performed_status', '45380')):
            row = rows[key]
            self.assertEqual((row['choices'], row['allow'], row['addendum_allowed'], row['document_value']),
                             ([], ['not_documented', 'cannot_confirm'], True, None), key)
        self.assertEqual(rows[('conflict:biopsy', '45385')]['prompt'],
                         'The record has conflicting statements about the forceps biopsy. Which is right for this date?')
        self.assertEqual(rows[('service_date', '')]['allow'], [])
        # every prompt is CPT Studio's fixed wording: no stored question or reason text is passed through
        stored = set(models.Clarification.objects.values_list('question', flat=True))
        self.assertFalse(stored & {r['prompt'] for r in rows.values()})

    def context_for(self, text, entered):
        encounter = f.encounter(self.s.workspace, self.s.reviewer)
        revision = f.pasted_revision(encounter, self.s.reviewer, text)
        encounter.user_values = {'service_date': entered} if entered else {}
        encounter.save(update_fields=['user_values'])
        context = jobs._record_context(encounter, revision, gi_context.extract_context(revision.text))
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context)
        encounter.refresh_from_db()
        return encounter

    def test_use_document_date_only_for_a_single_documented_value_and_never_a_prefilled_unsupported_date(self):
        cases = {
            # Mara's shape: one date of the note's own, a member's that differs
            'single': (pf.GI_NOTE, '1998-01-01', [answers.USE_DOCUMENT], '2026-10-21', True),
            # the document itself states two dates: each is offered as the document's, none is chosen for the member
            'two_own_dates': (TWO_DATES, '1998-01-01', ['2026-10-20', '2026-10-21'], None, False),
            # only another occurrence's date, which the member entered: nothing is offered, nothing is the document's
            'another_occurrence': (ELSEWHERE, '2026-11-04', [], None, False),
        }
        for name, (text, entered, choices, document_value, usable) in cases.items():
            with self.subTest(name):
                encounter = self.context_for(text, entered)
                self.assertTrue(gi_context.is_member_conflict(encounter.current_context.facts['service_date']))
                (row,) = answers.details_needed(encounter, None)  # at once, before any assessment exists
                self.assertEqual((row['fact'], row['control'], row['allow'], row['saved']),
                                 ('service_date', 'date', [], None))
                self.assertEqual([c['value'] for c in row['choices']], choices)
                self.assertEqual((row['document_value'], row['entered_value']), (document_value, entered))
                block = answers.service_date_block(encounter)
                self.assertEqual((block['can_use_document_date'], block['document_value'], block['entered_value'],
                                  block['conflict'], block['value'], block['source']),
                                 (usable, document_value, entered, True, None, 'conflict'))
                if document_value:
                    quote = row['quote']
                    self.assertEqual(encounter.current_revision.text[quote['start']:quote['end']], quote['text'])
                    self.assertEqual(quote, block['document_quote'])
                else:
                    self.assertIsNone(row['quote'])
                # no date the document does not state as its own is in the row, but the one the member typed
                shown = json.dumps({k: v for k, v in row.items() if k != 'entered_value'})
                for day in re.findall(r'\d{4}-\d{2}-\d{2}', shown):
                    self.assertIn(day, gi_context.document_service_date_fact(text)['values'], name)

    def test_a_legacy_context_shows_a_document_date_only_where_no_member_value_was_merged(self):
        self.assertIsNone(self.s.context.document_date)  # made as a context before the field existed
        block = answers.service_date_block(self.s.encounter)
        self.assertEqual((block['value'], block['source'], block['document_value'], block['can_use_document_date']),
                         ('2026-10-21', 'document', '2026-10-21', False))
        conflict = pf.facts(service_date=pf.Fact(name='service_date', value=None, origin='conflict', note=(
            gi_context.USER_CONFLICT_NOTE.format(user='1998-01-01', document='2026-10-21'))))
        pf.context(self.s.encounter, self.s.revision, fact_values=conflict, user_values={'service_date': '1998-01-01'})
        self.s.encounter.refresh_from_db()
        block = answers.service_date_block(self.s.encounter)
        self.assertEqual((block['document_value'], block['can_use_document_date'], block['entered_value']),
                         (None, False, '1998-01-01'))  # never read back from the note's prose


class DetailSaveTests(DetailsCase):
    def setUp(self):
        super().setUp()
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'billing_context', 'extent'),
                    ready('sel:1', '45380', pf.CECUM_PASSAGE),
                    questions=[pf.clarification('setting', scope='service', family=OFFICE),
                               pf.clarification('service_date', scope='encounter')])

    def test_one_save_is_one_context_change_and_a_repeated_identical_save_makes_nothing(self):
        items = [self.answer(self.row('setting', family=OFFICE), 'hospital_outpatient'),
                 self.answer(self.row('billing_context', '45385'), 'professional'),
                 self.answer(self.row('extent', '45385'), 'not_documented')]
        before = self.counts()
        with mock.patch.object(jobs, 'change_context', wraps=jobs.change_context) as change:
            response = self.post(items)
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()['saved'], 3)
            self.assertTrue(response.json()['reassessing'])
            self.assertEqual(change.call_count, 1)
            self.assertEqual(change.call_args.args[2], {'setting': 'hospital_outpatient',
                                                        'billing_context': 'professional'})
            after = self.counts()
            self.assertEqual({k: after[k] - before[k] for k in after},
                             {'contexts': 1, 'jobs': 1, 'assessments': 0, 'answers': 1, 'revocations': 0, 'audit': 3})
            drain()
            assessed = self.counts()
            self.assertEqual(assessed['assessments'] - after['assessments'], 1)  # the one re-assessment the save made
            again = self.post(items)
            self.assertEqual(again.status_code, 200, again.content)
            self.assertEqual((again.json()['saved'], again.json()['unchanged']), (0, 3))
            self.assertEqual(self.counts(), assessed)
            self.assertEqual(change.call_count, 1)
        self.s.encounter.refresh_from_db()
        self.assertEqual(self.s.encounter.user_values, {'setting': 'hospital_outpatient',
                                                        'billing_context': 'professional'})
        answer = models.MemberAnswer.objects.get()
        self.assertEqual((answer.code, answer.family, answer.fact, answer.value, answer.answered_by),
                         ('45385', COLON, 'extent', 'not_documented', self.s.reviewer))
        self.assertEqual(sorted(e.data.get('kind', e.data.get('value')) for e in
                                models.AuditEvent.objects.filter(event='detail.answered')),
                         ['context', 'context', 'not_documented'])

    def test_a_clinical_fact_takes_only_not_documented_or_cannot_confirm(self):
        extent, date_row = self.row('extent', '45385'), self.row('service_date')
        setting = self.row('setting', family=OFFICE)
        before = self.counts()
        for items, message in (
                ([self.answer(extent, 'cecum')], answers.CLINICAL),
                ([self.answer(extent, 'hospital_outpatient')], answers.CLINICAL),
                ([self.answer(date_row, 'not_documented')], answers.NOT_OFFERED),
                ([self.answer(setting, 'cannot_confirm')], answers.NOT_OFFERED),
                ([self.answer(setting, 'garage')], answers.NOT_OFFERED),
                ([self.answer(date_row, 'yesterday')], answers.BAD_DATE),
                ([self.answer(extent, 'not_documented'), self.answer(extent, 'cannot_confirm')], answers.TWICE),
                ([{'id': extent['id'], 'fact': 'extent'}], answers.SHAPE),
                ([{'id': 7, 'fact': 'extent', 'value': 'not_documented'}], answers.SHAPE),
                ([], answers.SHAPE)):
            with self.subTest(items=items):
                response = self.post(items)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json(), {'error': message, 'details': {}})
        response = self.post(None, raw={'answers': 'not a list'})
        self.assertEqual((response.status_code, response.json()['error']), (400, answers.SHAPE))
        self.assertEqual(self.counts(), before)  # nothing was stored, nothing was queued

    def test_an_answer_binds_to_code_family_and_fact_and_survives_a_re_assessment(self):
        response = self.post([self.answer(self.row('extent', '45385'), 'not_documented')])
        self.assertEqual(response.status_code, 201, response.content)
        (answer_id,) = response.json()['answer_ids']
        # the re-assessment swaps the keys: 45380 is now sel:0 and asks the extent; 45385 is sel:1
        later = self.assess(asks('sel:0', '45380', pf.CECUM_PASSAGE, 'extent'),
                            asks('sel:1', '45385', pf.SNARE_PASSAGE, 'extent'))
        self.assertEqual(self.row('extent', '45385', assessment=later)['saved']['answer_id'], answer_id)
        self.assertIsNone(self.row('extent', '45380', assessment=later)['saved'])  # never by its position
        (saved,) = answers.saved_answers(later)
        self.assertEqual({k: saved[k] for k in ('code', 'family', 'fact', 'value', 'answer_id', 'by')},
                         {'code': '45385', 'family': COLON, 'fact': 'extent', 'value': 'not_documented',
                          'answer_id': answer_id, 'by': self.s.reviewer.label()})
        # a new revision is new documentation: no answer of the earlier one stands for it
        pf.context(self.s.encounter, pf.addendum(self.s.encounter, self.s.reviewer, 'The cecum was reached.'))
        renewed = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'))
        self.assertEqual(answers.saved_answers(renewed), [])

    def test_a_later_answer_supersedes_and_revoke_withdraws_it(self):
        extent = self.row('extent', '45385')
        first = self.post([self.answer(extent, 'not_documented')]).json()['answer_ids'][0]
        second = self.post([self.answer(extent, 'cannot_confirm')]).json()['answer_ids'][0]
        self.assertEqual(models.MemberAnswerRevocation.objects.get(answer_id=first).reason, 'superseded')
        self.assertEqual([a['answer_id'] for a in answers.saved_answers(self.s.encounter.current_assessment)], [second])
        self.assertEqual(self.row('extent', '45385')['saved']['label'], 'Cannot confirm')
        url = f'/api/encounters/{self.s.encounter.pk}/details/{second}/revoke'
        response = self.client.post(url)
        self.assertEqual((response.status_code, response.json()), (201, {'revoked': second}))
        self.assertIsNone(self.row('extent', '45385')['saved'])  # asked again
        self.assertEqual(answers.saved_answers(self.s.encounter.current_assessment), [])
        self.assertEqual(models.MemberAnswerRevocation.objects.get(answer_id=second).reason, 'withdrawn')
        self.assertEqual(models.AuditEvent.objects.filter(event='detail.revoked').count(), 1)
        again = self.client.post(url)
        self.assertEqual((again.status_code, again.json()['error']), (409, answers.ALREADY_WITHDRAWN))
        self.assertEqual(self.client.post(f'/api/encounters/{self.s.encounter.pk}/details/{uuid.uuid4()}/revoke')
                         .status_code, 404)
        viewer = Client(enforce_csrf_checks=False)
        viewer.force_login(self.s.viewer)
        self.assertEqual(viewer.post(url).status_code, 403)
        self.assertEqual(self.post([self.answer(extent, 'not_documented')], client=viewer).status_code, 403)
        stranger = Client(enforce_csrf_checks=False)
        stranger.force_login(f.member(f.workspace('Elsewhere'), f.user('stranger')))
        self.assertEqual(stranger.post(url).status_code, 404)

    def test_saving_and_withdrawing_wait_while_processing_runs(self):
        extent = self.row('extent', '45385')
        answer_id = self.post([self.answer(extent, 'not_documented')]).json()['answer_ids'][0]
        pf.job(self.s.encounter, self.s.revision, models.Job.ASSESS, models.Job.QUEUED)
        before = self.counts()
        response = self.post([self.answer(extent, 'cannot_confirm')])
        self.assertEqual((response.status_code, response.json()['error']), (409, answers.BUSY))
        response = self.client.post(f'/api/encounters/{self.s.encounter.pk}/details/{answer_id}/revoke')
        self.assertEqual((response.status_code, response.json()['error']), (409, answers.BUSY))
        self.assertEqual(self.counts(), before)


@override_settings(**LIVE)
class DateHoldDetailTests(TestCase):
    """The member date hold (Mara's first run): the date row is there at once, and "Use document date" is the existing
    clear path - one context change, then the request for the document's date."""

    def setUp(self):
        self.provider = FakeProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_use_document_date_clears_the_member_s_date_through_one_context_change(self):
        encounter = pasted(MARA, service_date='1998-01-01', title='Mara (synthetic)')
        run_stages(2)  # extract, analyze: the hold is recorded and only its assess is queued
        encounter.refresh_from_db()
        hold = models.ProviderRun.objects.get(encounter=encounter)
        self.assertEqual((hold.state, hold.scope), ('not_sent', {'held': 'member_date_conflict'}))
        (row,) = answers.details_needed(encounter, review.live_assessment(encounter))  # no assessment yet
        self.assertEqual((row['fact'], row['document_value'], row['entered_value'], row['choices']),
                         ('service_date', '2026-11-03', '1998-01-01',
                          [{'value': 'use_document', 'label': 'Use document date'}]))
        client = Client(enforce_csrf_checks=False)
        client.force_login(encounter.created_by)
        url = f'/api/encounters/{encounter.pk}/details'
        body = json.dumps({'answers': [{'id': row['id'], 'fact': 'service_date', 'value': 'use_document'}]})
        busy = client.post(url, data=body, content_type='application/json')
        self.assertEqual((busy.status_code, busy.json()['error']), (409, answers.BUSY))  # the hold's assess first
        drain()
        self.assertEqual(self.provider.sent, [])  # nothing was sent while the hold stood
        with mock.patch.object(jobs, 'change_context', wraps=jobs.change_context) as change:
            response = client.post(url, data=body, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(change.call_args_list, [mock.call(mock.ANY, encounter.created_by, {'service_date': ''})])
        encounter.refresh_from_db()
        self.assertEqual(encounter.user_values, {})
        self.assertFalse(gi_context.is_member_conflict(encounter.current_context.facts['service_date']))
        self.assertEqual(encounter.current_context.facts['service_date']['value'], '2026-11-03')
        (queued,) = models.Job.objects.filter(encounter=encounter, state='queued')
        self.assertEqual((queued.kind, queued.idempotency_key), ('predict', f'predict:{encounter.current_context_id}'))
        drain()
        self.assertEqual(len(self.provider.sent), 1)  # the one request, for the document's date
