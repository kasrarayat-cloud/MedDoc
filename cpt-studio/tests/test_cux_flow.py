"""P5 FLOW (owner directive 2026-11-03, sections 4-6; DESIGN section 6): the document's own date recorded beside the
member's, the "A few details needed" rows and their one save, the member's answers and their withdrawal, the progress
fold, the upload key, and the re-assessment from retained answers. DB-backed; synthetic data only; nothing is sent (the
pipeline's provider is disabled, or the in-process fakes of the harness suites).
"""
import collections
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
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import answers, intake, jobs, models, progress, review
from studio.gi import context as gi_context
from studio.types import ExtractionResult, PageSpan, sha256_json
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_harness2_pipeline import TWO_EXTENTS, ColonCase
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


@applied
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
        """The row asking ``fact`` of ``code``: a code's own question, or its service's question for a service fact
        (asked once for the service, its code '': refutation r2, L7-08) whose affects list the code."""
        family = (COLON if code else '') if family is None else family
        ids = {answers.detail_id(fact, family, code), answers.detail_id(fact, family, '')}
        return next(r for r in self.rows(assessment) if r['id'] in ids and (not code or code in r['affects']))

    def post(self, items, client=None, raw=None, encounter=None):
        body = json.dumps(raw if raw is not None else {'answers': items})
        return (client or self.client).post(f'/api/encounters/{(encounter or self.s.encounter).pk}/details', data=body,
                                            content_type='application/json')

    def context_for(self, text, entered):
        """Another encounter of the workspace whose current context was made from ``text`` with ``entered`` as the
        member's date - as analyze makes it: with the document's own date recorded beside it."""
        encounter = f.encounter(self.s.workspace, self.s.reviewer)
        revision = f.pasted_revision(encounter, self.s.reviewer, text)
        encounter.user_values = {'service_date': entered} if entered else {}
        encounter.save(update_fields=['user_values'])
        context = jobs._record_context(encounter, revision, gi_context.extract_context(revision.text))
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context)
        encounter.refresh_from_db()
        return encounter

    def answer(self, row, value):
        return {'id': row['id'], 'fact': row['fact'], 'value': value}

    def counts(self):
        return {'contexts': models.EncounterContext.objects.count(), 'jobs': models.Job.objects.count(),
                'assessments': models.Assessment.objects.count(), 'answers': models.MemberAnswer.objects.count(),
                'revocations': models.MemberAnswerRevocation.objects.count(),
                'audit': models.AuditEvent.objects.filter(event__startswith='detail.').count()}


class DetailRowsTests(DetailsCase):
    def test_one_row_per_open_question_a_service_fact_once_for_its_service(self):
        """De-duplicated by (fact, family, code), where a service fact's question - the profiles' required facts - is
        its service's, asked once whichever of its codes holds on it (refutation r2, L7-08: two codes of one colonoscopy
        each had an identical "How far was the instrument advanced?" row); a question about one code stays its own."""
        first = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'), ready('sel:1', '45380', pf.CECUM_PASSAGE),
                            questions=[pf.clarification('setting', scope='service', family=OFFICE)])
        # the re-assessment asks the same 45385 question twice (two proposals of one code), the same service fact of
        # 45380, a question of each code's own, the date and the service question again: the first assessment's
        # re-raised rows stay open and are not read twice
        second = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent', 'base_included'),
                             asks('sel:1', '45385', pf.SNARE_PASSAGE, 'extent'),
                             asks('sel:2', '45380', pf.CECUM_PASSAGE, 'extent', 'base_included'),
                             questions=[pf.clarification('service_date', scope='encounter'),
                                        pf.clarification('setting', scope='service', family=OFFICE)])
        self.assertNotEqual(first, second)
        self.assertGreater(models.Clarification.objects.filter(state='open', assessment=first).count(), 0)
        rows = self.rows()
        self.assertEqual([(r['fact'], r['affects']) for r in rows],
                         [('service_date', ['45385', '45380']), ('setting', []), ('extent', ['45385', '45380']),
                          ('base_included', ['45385']), ('base_included', ['45380'])])
        self.assertEqual(len({r['id'] for r in rows}), 5)
        self.assertEqual(rows[2]['id'], answers.detail_id('extent', COLON, ''))
        self.assertEqual(rows[3]['id'], answers.detail_id('base_included', COLON, '45385'))
        # completion repair (2026-11-06, U10): the fact named, what CPT Studio could not confirm, and the passages
        self.assertEqual(set(rows[0]), {'id', 'fact', 'family_label', 'prompt', 'control', 'choices', 'allow',
                                        'document_value', 'entered_value', 'quote', 'affects', 'saved',
                                        'addendum_allowed', 'missing', 'statement', 'passages'})

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

    def test_with_the_overlay_s_view_a_released_question_goes_an_added_one_comes_an_answered_one_stays(self):
        """The review overlay (review.effective_view) holds each proposal's questions after the decisions: the rows
        follow it - and a question a standing answer answers stays, so the member sees it and can withdraw it."""
        assessment = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'),
                                 asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'),
                                 questions=[pf.clarification('setting', scope='service', family=OFFICE)])
        View = collections.namedtuple('View', 'questions')
        # the overlay's own question shape (review_view._question): a dict, as review.effective_view's View holds it
        added = {'id': '', 'scope': 'proposal', 'family': COLON, 'fact': 'base_included', 'question': 'stored wording',
                 'reason': 'r'}
        view = {'sel:0': View(questions=()), 'sel:1': View(questions=(added,))}  # both extents released
        rows = answers.details_needed(self.s.encounter, assessment, view)
        self.assertEqual([(r['fact'], r['affects']) for r in rows], [('setting', []), ('base_included', ['45380'])])
        # the stored rows ask the colonoscopy's extent once for both codes: one answer stands for each of them
        answers.save_details(self.s.encounter, self.s.reviewer, [
            self.answer(self.row('extent', '45385'), 'not_documented')])
        rows = answers.details_needed(self.s.encounter, assessment, view)
        self.assertEqual([(r['fact'], r['affects'], r['saved'] is not None) for r in rows],
                         [('setting', [], False), ('extent', ['45385', '45380'], True),
                          ('base_included', ['45380'], False)])

    def test_use_document_date_only_for_a_single_documented_value_and_never_a_prefilled_unsupported_date(self):
        cases = {
            # Mara's shape: one date of the note's own, a member's that differs
            'single': (pf.GI_NOTE, '1998-01-01', [answers.USE_DOCUMENT], '2026-10-21', True),
            # the document itself states two dates: each is offered as the document's, none is chosen for the member
            'two_own_dates': (TWO_DATES, '1998-01-01', ['2026-10-20', '2026-10-21'], None, False),
            # only another occurrence's date, which the member entered: nothing is offered as the document's; the
            # member's date can be removed (refutation r2, L7-03), and the document's wording is quoted as it stands
            'another_occurrence': (ELSEWHERE, '2026-11-04', [answers.CLEAR], None, False),
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
                elif name == 'another_occurrence':  # what the document says, never offered as its date (L7-07)
                    quote = row['quote']
                    self.assertEqual(quote['text'], 'Next procedure date: 11/04/2026')
                    self.assertEqual(encounter.current_revision.text[quote['start']:quote['end']], quote['text'])
                    self.assertIsNone(block['document_quote'])
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


@applied
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

    def test_a_value_already_in_effect_makes_nothing_while_its_detail_is_still_asked(self):
        encounter = self.context_for(pf.GI_NOTE, '1998-01-01')  # the member's date conflicts: the date row stays
        pf.routing(encounter.current_revision)  # routed, so a context change would run
        (row,) = answers.details_needed(encounter, None)
        before = self.counts()
        with mock.patch.object(jobs, 'change_context', wraps=jobs.change_context) as change:
            response = self.post([self.answer(row, '1998-01-01')], encounter=encounter)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['saved'], response.json()['unchanged'], change.call_count), (0, 1, 0))
        self.assertEqual(self.counts(), before)  # no context, no re-assessment, nothing recorded
        self.assertEqual(answers.details_needed(encounter, None), [row])

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
        (answer_id,) = response.json()['answer_ids']  # only 45385 asked it: the answer is 45385's
        # the re-assessment swaps the keys: 45380 is now sel:0 and asks the extent too; 45385 is sel:1
        later = self.assess(asks('sel:0', '45380', pf.CECUM_PASSAGE, 'extent'),
                            asks('sel:1', '45385', pf.SNARE_PASSAGE, 'extent'))
        # one row for the colonoscopy's extent (refutation r2, L7-08), asked again: 45380 has no answer of its own, and
        # the one saved for 45385 is never read for it - by its position or otherwise
        row = self.row('extent', '45385', assessment=later)
        self.assertEqual((row['affects'], row['saved']), (['45380', '45385'], None))
        views = review.effective_view(later)
        self.assertEqual(views['sel:1'].reason, review.DETAIL_UNAVAILABLE)  # 45385: its answer stands
        self.assertNotEqual(views['sel:0'].reason, review.DETAIL_UNAVAILABLE)
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


@applied
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


# --- the progress fold (progress.py) -------------------------------------------------------------------------------------

PROGRESS_KEYS = {'phase', 'busy', 'steps', 'active_detail', 'started_at', 'finished_at', 'server_time', 'slow', 'message',
                 'can_stop', 'can_resume', 'can_leave', 'error'}
STEP_KEYS = {'key', 'label', 'state', 'started_at', 'finished_at'}
# never a percentage, a remaining time or an estimate, and none of the words the customer surface never carries
UNSAID = re.compile(r'%|\beta\b|remaining|estimat|percent|minutes? left|\bcorti\b|\bastra\b|\bfable\b|openai|anthropic|'
                    r'claude|provider|participant|peer|\btokens?\b|credit|trace|sha256|request id', re.I)
CHAIN = ('extract', 'analyze', 'predict')


def strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


class ProgressCase(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.enc, self.rev = self.s.encounter, self.s.revision
        self.t0 = timezone.now() - timedelta(minutes=30)

    def job(self, kind, state, at, *, length=3, key=None, run=None, result=None):
        """A job of the current revision queued ``at`` seconds after t0, started then (unless queued) and finished
        ``length`` seconds later (when terminal) - a successor queued at its predecessor's start + 2 s joins its run."""
        created = self.t0 + timedelta(seconds=at)
        job = models.Job.objects.create(encounter=self.enc, revision=self.rev, kind=kind, state=state,
                                        idempotency_key=key or f'{kind}:{uuid.uuid4()}',
                                        deadline_at=created + jobs.QUEUE_DEADLINE, context=self.s.context,
                                        provider_run=run, result=result or {})
        models.Job.objects.filter(pk=job.pk).update(
            created_at=created, started_at=None if state == 'queued' else created,
            finished_at=created + timedelta(seconds=length) if state in models.Job.TERMINAL else None)
        job.refresh_from_db()
        return job

    def chain(self, *kinds, last='succeeded', at=0):
        """A run of stages, each queued 2 s after its predecessor started (so while it ran); all succeeded but the last."""
        made = []
        for index, kind in enumerate(kinds):
            key = None
            if isinstance(kind, tuple):
                kind, key = kind
            made.append(self.job(kind, last if index == len(kinds) - 1 else 'succeeded', at + 2 * index, key=key))
        return made

    def set(self, job, state, *, started=None):
        fields = {'state': state}
        if state in models.Job.TERMINAL:
            fields['finished_at'] = job.created_at + timedelta(seconds=3)
        if started is not None:
            fields['started_at'] = started
        models.Job.objects.filter(pk=job.pk).update(**fields)

    def progress(self, now=None):
        self.enc.refresh_from_db()
        out = progress.encounter_progress(self.enc, now or timezone.now())
        self.assertEqual(set(out), PROGRESS_KEYS)
        self.assertEqual([step['key'] for step in out['steps']], ['reading', 'identifying', 'checking', 'preparing'])
        for step in out['steps']:
            self.assertEqual(set(step), STEP_KEYS)
            self.assertIn(step['state'], progress.STEP_STATES)
        self.assertIn(out['phase'], progress.PHASES)
        said = [text for text in strings(out) if UNSAID.search(text)]
        self.assertEqual(said, [], 'a percentage, an estimate or an internal word in the progress block')
        if out['phase'] in ('failed', 'stopped'):  # no step animates once the job failed or stopped
            self.assertFalse({step['state'] for step in out['steps']} & {'active', 'waiting'})
        self.assertTrue(out['can_leave'])
        return out

    def states(self, out):
        return [step['state'] for step in out['steps']]

    def final(self, *proposals, **kwargs):
        return pf.assess(self.enc, pf.result(*(proposals or (ready('sel:0', '45380', pf.CECUM_PASSAGE),)), **kwargs))


class ProgressFoldTests(ProgressCase):
    def test_queued_then_each_step_as_its_job_runs(self):
        extract = self.job('extract', 'queued', 0)
        out = self.progress(now=extract.created_at + timedelta(seconds=5))
        self.assertEqual((out['phase'], out['busy'], out['can_stop'], out['can_resume'], out['error']),
                         ('queued', True, True, False, None))
        self.assertEqual(self.states(out), ['waiting', 'not_started', 'not_started', 'not_started'])
        self.assertEqual((out['message'], out['active_detail']), (progress.MESSAGES['queued'], ''))
        self.assertEqual(out['started_at'], extract.created_at.isoformat())
        self.set(extract, 'running', started=extract.created_at)
        self.assertEqual(self.states(self.progress()), ['active', 'not_started', 'not_started', 'not_started'])
        self.set(extract, 'succeeded')
        analyze = self.job('analyze', 'running', 2)
        out = self.progress()
        self.assertEqual((out['phase'], self.states(out)), ('processing', ['done', 'active', 'not_started',
                                                                           'not_started']))
        self.assertEqual(out['steps'][0]['finished_at'], (extract.created_at + timedelta(seconds=3)).isoformat())
        self.set(analyze, 'succeeded')
        self.job('predict', 'running', 4)
        out = self.progress()
        self.assertEqual((self.states(out), out['active_detail']), (['done', 'done', 'active', 'not_started'],
                                                                    'Document review'))
        self.assertIsNone(out['finished_at'])
        self.assertEqual(progress.checks_summary(self.enc), [
            {'key': 'document_review', 'label': 'Document review', 'state': 'running'},
            {'key': 'independent_checks', 'label': 'Independent checks', 'state': 'not_run'},  # none configured
            {'key': 'coding_validation', 'label': 'Coding validation', 'state': 'waiting'}])

    def test_checking_spans_the_independent_checks_assess_one_and_the_peer_reviews(self):
        jobs_ = self.chain(*CHAIN, 'astra', 'fable', ('assess', 'assess:ctx:run:p:0123456789ab'), 'astra_peer',
                           last='running')
        out = self.progress()
        self.assertEqual((self.states(out), out['active_detail']), (['done', 'done', 'active', 'not_started'],
                                                                    'Independent checks'))
        self.set(jobs_[-1], 'succeeded')
        self.job('fable_peer', 'succeeded', 14)  # queued while astra_peer ran (12-15), as its stage queues it
        final = self.job('assess', 'running', 16, key='assess:ctx:run:p:0123456789ab:q:ba9876543210')
        out = self.progress()
        self.assertEqual((self.states(out), out['active_detail']), (['done', 'done', 'done', 'active'],
                                                                    'Coding validation'))
        self.assertEqual(out['steps'][2]['started_at'], jobs_[2].created_at.isoformat())  # predict began the step
        self.set(final, 'succeeded')
        self.final()
        out = self.progress()
        self.assertEqual((out['phase'], self.states(out), out['busy']), ('completed', ['done'] * 4, False))
        self.assertEqual(out['finished_at'], (final.created_at + timedelta(seconds=3)).isoformat())

    def test_a_re_assessment_run_keeps_what_was_read_and_checked_before(self):
        self.chain(*CHAIN, 'assess')
        self.final()
        again = self.job('assess', 'queued', 600)  # a member's save, long after: a run of its own
        out = self.progress()
        self.assertEqual((out['phase'], self.states(out)), ('queued', ['done', 'done', 'done', 'waiting']))
        self.assertEqual(out['started_at'], again.created_at.isoformat())

    def test_awaiting_detail_until_every_detail_is_answered_then_completed(self):
        self.chain(*CHAIN, 'assess')
        self.final(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'))
        out = self.progress()
        self.assertEqual((out['phase'], out['message']), ('awaiting_detail', progress.MESSAGES['awaiting_detail']))
        (row,) = answers.details_needed(self.enc, self.enc.current_assessment)
        answers.save_details(self.enc, self.s.reviewer, [{'id': row['id'], 'fact': 'extent',
                                                          'value': 'not_documented'}])
        self.assertEqual(self.progress()['phase'], 'completed')

    def test_partial_when_an_independent_check_or_the_reading_is_incomplete(self):
        self.chain(*CHAIN, 'assess')
        records = [{'name': 'astra', 'state': 'failed', 'run': None, 'reason': 'synthetic failure'},
                   {'name': 'fable', 'state': 'read', 'run': None, 'peer_state': 'read', 'peer_run': None}]
        review.persist_assessment(encounter=self.enc, revision=self.rev, context=self.s.context,
                                  routing_run=pf.routing(self.rev), provider_run=pf.provider_run(self.enc, self.rev),
                                  result=pf.result(ready('sel:0', '45380', pf.CECUM_PASSAGE)), participants=records)
        out = self.progress()
        self.assertEqual((out['phase'], out['message']), ('partial', progress.MESSAGES['partial']))
        self.assertEqual([c['state'] for c in progress.checks_summary(self.enc)], ['done', 'unavailable', 'not_run'])
        other = pf.scenario()
        partial = f.pasted_revision(other.encounter, other.reviewer, pf.GI_NOTE, extract=False)
        f.record(partial, ExtractionResult(status='partial', method='paste', text=pf.GI_NOTE,
                                           pages=(PageSpan(page=1, start=0, end=len(pf.GI_NOTE)),)))
        pf.context(other.encounter, partial)
        self.enc, self.rev, self.s = other.encounter, partial, other
        self.s.context = other.encounter.current_context
        self.chain(*CHAIN, 'assess')
        self.final()
        self.assertEqual(self.progress()['phase'], 'partial')

    def test_failed_phases_say_what_to_do_and_never_a_job_s_own_words(self):
        noise = 'The analyze stage failed unexpectedly; Corti answered HTTP 503 (req_synthetic_1).'
        cases = []
        failed = pf.scenario()
        unread = f.pasted_revision(failed.encounter, failed.reviewer, pf.GI_NOTE, extract=False)
        f.record(unread, ExtractionResult(status='failed', method='paste', text=''))
        cases.append(('extraction_failed', failed.encounter, unread, ('extract',)))
        for state, kinds in (('processing_failed', ('extract', 'analyze')), ('provider_failed', CHAIN)):
            scenario = pf.scenario()
            cases.append((state, scenario.encounter, scenario.revision, kinds))
        for state, encounter, revision, kinds in cases:
            with self.subTest(state):
                self.enc, self.rev = encounter, revision
                self.s = mock.Mock(context=encounter.current_context)
                made = self.chain(*kinds, last='succeeded' if state == 'extraction_failed' else 'failed')
                models.Job.objects.filter(pk=made[-1].pk).update(error=noise)
                if state == 'provider_failed':
                    pf.provider_run(encounter, revision, state='failed')
                out = self.progress()
                self.assertEqual(out['phase'], 'failed')
                text, action = progress.ERRORS[state]
                self.assertEqual((out['error'], out['message']), ({'text': text, 'action': action}, text))
                self.assertNotIn('req_synthetic', json.dumps(out))
                self.assertEqual(out['steps'][len(kinds) - 1]['state'], 'failed')
        not_run = pf.scenario()
        self.enc, self.rev, self.s = not_run.encounter, not_run.revision, not_run
        self.chain(*CHAIN, 'assess')
        pf.assess(self.enc, pf.result(ready('sel:0', '45380', pf.CECUM_PASSAGE)), no_provider=True)
        out = self.progress()
        self.assertEqual((out['phase'], out['error']), ('failed', {'text': progress.ERRORS['provider_not_run'][0],
                                                                   'action': 'none'}))

    def test_stopped_and_being_confirmed(self):
        made = self.chain(*CHAIN, last='cancelled')
        models.Encounter.objects.filter(pk=self.enc.pk).update(stopped_at=timezone.now(), stopped_by=self.s.reviewer)
        out = self.progress()
        self.assertEqual((out['phase'], out['error'], out['can_resume']),
                         ('stopped', {'text': progress.STOPPED_BY_MEMBER, 'action': 'resume'}, True))
        self.assertEqual(self.states(out), ['done', 'done', 'stopped', 'not_started'])
        models.Encounter.objects.filter(pk=self.enc.pk).update(stopped_at=None, stopped_by=None)  # an expiry instead
        self.assertEqual(self.progress()['error']['text'], progress.STOPPED_BY_SYSTEM)
        self.set(made[-1], 'succeeded')
        pf.provider_run(self.enc, self.rev, state='unknown')
        out = self.progress()
        self.assertEqual((out['phase'], out['message'], out['error'], out['can_resume']),
                         ('being_confirmed', progress.MESSAGES['being_confirmed'], None, False))

    def test_reading_progress_details_the_date_and_the_checks_writes_nothing(self):
        """Polling, reloading or opening results reads rows only (directive 5: never a duplicate request)."""
        self.chain(*CHAIN, 'assess')
        self.final(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'))
        self.job('assess', 'queued', 600)
        self.enc.refresh_from_db()
        with CaptureQueriesContext(connection) as queries:
            progress.encounter_progress(self.enc)
            progress.checks_summary(self.enc)
            answers.details_needed(self.enc, self.enc.current_assessment)
            answers.service_date_block(self.enc)
            answers.saved_answers(self.enc.current_assessment)
        written = [q['sql'] for q in queries.captured_queries
                   if not q['sql'].lstrip().upper().startswith(('SELECT', 'SAVEPOINT', 'RELEASE SAVEPOINT'))]
        self.assertEqual(written, [])
        self.assertGreater(len(queries.captured_queries), 0)

    def test_slow_only_from_the_stage_s_own_bound(self):
        self.chain('extract', 'analyze')
        predict = self.job('predict', 'running', 4)
        # the coding service's send deadline, the bound that is enforced (150 s; JOB_DEADLINE_SECONDS['predict'], 180 s,
        # is read nowhere: critic C4)
        bound = progress.stage_bound('predict')
        self.assertEqual(bound, progress.settings.PROVIDER_READ_TIMEOUT_SECONDS + 30)
        for share, slow, message in ((0.5, False, progress.MESSAGES['processing']),
                                     (0.7, True, progress.SLOW_MESSAGES['predict']),
                                     (1.1, True, progress.OVERDUE)):
            with self.subTest(share):
                out = self.progress(now=predict.started_at + timedelta(seconds=share * bound))
                self.assertEqual((out['slow'], out['message']), (slow, message))
        self.set(predict, 'succeeded')
        astra = self.job('astra', 'running', 6)
        out = self.progress(now=astra.started_at + timedelta(seconds=0.7 * 580))
        self.assertEqual((out['slow'], out['message']), (True, progress.SLOW_MESSAGES['astra']))
        self.set(astra, 'succeeded')
        waiting = self.job('fable', 'queued', 8)
        out = self.progress(now=waiting.created_at + timedelta(seconds=0.7 * jobs.QUEUE_DEADLINE.total_seconds()))
        self.assertEqual((out['phase'], out['slow'], out['message']), ('queued', True, progress.QUEUE_SLOW))
        models.Job.objects.filter(pk=waiting.pk).update(result={'requeued': 'the provider lock is busy'})
        out = self.progress(now=waiting.created_at + timedelta(seconds=5))
        self.assertEqual((out['slow'], out['message']), (False, progress.TAKING_TURN))


@applied
@override_settings(**LIVE)
class DateHoldProgressTests(TestCase):
    def setUp(self):
        self.provider = FakeProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_action_needed_right_after_analyze_never_implying_processing_began(self):
        encounter = pasted(MARA, service_date='1998-01-01', title='Mara (synthetic)')
        run_stages(2)  # extract, analyze: the hold is recorded and only its assess is queued
        encounter.refresh_from_db()
        out = progress.encounter_progress(encounter)
        self.assertEqual((out['phase'], out['busy'], out['message']),
                         ('action_needed', True, progress.MESSAGES['action_needed']))
        self.assertEqual([s['state'] for s in out['steps']], ['done', 'done', 'skipped', 'waiting'])
        self.assertEqual([c['state'] for c in progress.checks_summary(encounter)], ['not_run', 'not_run', 'waiting'])
        drain()
        encounter.refresh_from_db()
        out = progress.encounter_progress(encounter)
        self.assertEqual((out['phase'], out['busy']), ('action_needed', False))
        self.assertEqual([s['state'] for s in out['steps']], ['done', 'done', 'skipped', 'done'])
        self.assertEqual([c['state'] for c in progress.checks_summary(encounter)][:2], ['not_run', 'not_run'])
        self.assertEqual(self.provider.sent, [])
        (row,) = [r for r in answers.details_needed(encounter, encounter.current_assessment)
                  if r['fact'] == 'service_date']
        answers.save_details(encounter, encounter.created_by, [{'id': row['id'], 'fact': 'service_date',
                                                                'value': 'use_document'}])
        encounter.refresh_from_db()
        self.assertEqual(progress.encounter_progress(encounter)['phase'], 'queued')  # the request is made now
        drain()
        encounter.refresh_from_db()
        self.assertIn(progress.encounter_progress(encounter)['phase'], ('awaiting_detail', 'completed', 'partial'))
        self.assertEqual(len(self.provider.sent), 1)


# --- upload idempotency (POST /api/encounters with client_key) ---------------------------------------------------------

class UploadKeyTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('uploader'))
        self.other = f.member(self.ws, f.user('colleague'))
        self.client = self.login(self.reviewer)

    def login(self, user):
        client = Client(enforce_csrf_checks=False)
        client.force_login(user)
        return client

    def upload(self, key, *, client=None, text=pf.GI_NOTE, **extra):
        data = {'text': text, 'synthetic_attestation': 'yes', **extra}
        if key is not None:
            data['client_key'] = key
        return (client or self.client).post('/api/encounters', data)

    def counts(self):
        return (models.Encounter.objects.count(), models.SourceRevision.objects.count(), models.Job.objects.count(),
                models.AuditEvent.objects.filter(event='encounter.created').count())

    def test_the_same_key_twice_is_one_encounter_with_the_same_id(self):
        key = str(uuid.uuid4())
        first = self.upload(key)
        self.assertEqual(first.status_code, 201, first.content)
        before = self.counts()
        second = self.upload(key)
        self.assertEqual((second.status_code, second.json()), (201, first.json()))
        self.assertEqual(self.counts(), before)  # nothing created: no encounter, revision, stage or audit row
        encounter = models.Encounter.objects.get(pk=first.json()['id'])
        self.assertEqual((encounter.client_key, encounter.created_by), (uuid.UUID(key), self.reviewer))
        # a file upload the same: one encounter, one stored original
        from django.core.files.uploadedfile import SimpleUploadedFile
        file_key = str(uuid.uuid4())
        made = [self.client.post('/api/encounters', {'file': SimpleUploadedFile('note.txt', pf.GI_NOTE.encode()),
                                                     'synthetic_attestation': 'yes', 'client_key': file_key})
                for _ in range(2)]
        self.assertEqual([r.status_code for r in made], [201, 201])
        self.assertEqual(made[0].json(), made[1].json())
        self.assertEqual(models.SourceFile.objects.filter(encounter_id=made[0].json()['id']).count(), 1)

    def test_another_member_s_same_key_is_a_new_encounter_and_no_key_is_as_before(self):
        key = str(uuid.uuid4())
        mine = self.upload(key).json()['id']
        theirs = self.upload(key, client=self.login(self.other))
        self.assertEqual(theirs.status_code, 201, theirs.content)
        self.assertNotEqual(theirs.json()['id'], mine)
        before = models.Encounter.objects.count()
        self.assertNotEqual(self.upload(None).json()['id'], self.upload(None).json()['id'])
        self.assertEqual(models.Encounter.objects.count(), before + 2)

    def test_a_key_is_never_reused_for_another_document_or_after_its_window(self):
        key = str(uuid.uuid4())
        encounter_id = self.upload(key).json()['id']
        before = self.counts()
        other = self.upload(key, text=pf.GI_NOTE + 'A second paragraph.\n')
        self.assertEqual((other.status_code, other.json()['error']), (409, intake.KEY_OTHER_DOCUMENT))
        models.Encounter.objects.filter(pk=encounter_id).update(created_at=timezone.now() - timedelta(hours=25))
        late = self.upload(key)
        self.assertEqual((late.status_code, late.json()['error']), (409, intake.KEY_USED))
        for bad in ('not-a-uuid', '12345678123456781234567812345678', '{%s}' % uuid.uuid4()):
            with self.subTest(bad):
                response = self.upload(bad)
                self.assertEqual((response.status_code, response.json()['error']),
                                 (400, 'The upload key must be a UUID.'))
        self.assertEqual(self.counts(), before)

    def test_a_concurrent_post_of_the_same_attempt_answers_with_the_first_encounter(self):
        key = str(uuid.uuid4())
        encounter_id = self.upload(key).json()['id']
        before = self.counts()
        real, calls = intake.find_upload, []

        def first_misses(**kwargs):  # the second POST read before the first committed
            calls.append(kwargs['client_key'])
            return None if len(calls) == 1 else real(**kwargs)
        with mock.patch('studio.intake.find_upload', side_effect=first_misses):
            response = self.upload(key)
        self.assertEqual((response.status_code, response.json()), (201, {'id': encounter_id}))
        self.assertEqual(len(calls), 2)  # the database's unique index refused the second row, then it was read
        self.assertEqual(self.counts(), before)

    def test_the_index_is_unique_per_member_and_key_and_ignores_rows_with_no_key(self):
        key = uuid.uuid4()
        models.Encounter.objects.create(workspace=self.ws, title='a', created_by=self.reviewer, client_key=key)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Encounter.objects.create(workspace=self.ws, title='b', created_by=self.reviewer, client_key=key)
        models.Encounter.objects.create(workspace=self.ws, title='c', created_by=self.other, client_key=key)
        for title in ('d', 'e'):  # every row an older release writes has no key: never refused
            models.Encounter.objects.create(workspace=self.ws, title=title, created_by=self.reviewer)


# --- the re-assessment from retained answers (manage.py reassess_retained; jobs.reassess_retained) ---------------------

@applied
class ReassessRetainedTests(ColonCase):
    """R6 6.4: ONE assess in the re-assessment mode, which re-reads the final assessment's retained answers by id - the
    Corti run, every phase-1 run and peer run its entries name - creates no ProviderRun and sends nothing. Corti is the
    harness suite's in-process fake; Astra and Fable are the replay adapters on the real tool loop."""

    def chain(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        return encounter_id

    def sends(self):
        return (models.ProviderRun.objects.count(), models.ProviderExchange.objects.count(),
                models.ToolCall.objects.count(), [len(adapter.loops) for adapter in self.adapters.values()],
                len(self.corti.requests))

    def command(self, *args):
        out = io.StringIO()
        call_command('reassess_retained', *args, stdout=out)
        return json.loads(out.getvalue())

    def refused(self, encounter_id, message):
        before = (models.Job.objects.count(), models.AuditEvent.objects.filter(event='assessment.refreshed').count())
        with self.assertRaisesMessage(CommandError, message):
            self.command('--encounter', str(encounter_id), '--tag', 'cux-flow-refused')
        self.assertEqual((models.Job.objects.count(),
                          models.AuditEvent.objects.filter(event='assessment.refreshed').count()), before)

    def test_one_assess_re_reads_the_final_s_runs_by_id_and_sends_nothing(self):
        encounter_id = self.chain()
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(jobs.assessment_phase(final), 2)
        made = models.Job.objects.get(encounter_id=encounter_id, kind='assess', result__assessment=str(final.pk))
        records, before = self.records(final), self.sends()
        dry = self.command('--encounter', encounter_id, '--tag', 'cux-flow-r1', '--dry-run')
        self.assertEqual((dry['action'], dry['job']), ('dry_run', None))
        self.assertFalse(models.AuditEvent.objects.filter(event='assessment.refreshed').exists())
        out = self.command('--encounter', encounter_id, '--tag', 'cux-flow-r1', '--username', self.reviewer.username)
        key = f'{made.idempotency_key}:c:{hashlib.sha256(b"cux-flow-r1").hexdigest()[:12]}'
        self.assertEqual((out['action'], out['key'], dry['key']), ('queued', key, key))
        job = models.Job.objects.get(pk=out['job'])
        self.assertEqual((job.kind, job.state, job.context_id, job.provider_run_id, job.requested_by),
                         ('assess', 'queued', final.context_id, final.provider_run_id, self.reviewer))
        self.assertEqual(jobs._assess_mode(job), jobs.AGAIN)
        self.assertEqual(out['document_review_run'], str(final.provider_run_id))
        self.assertEqual(out['participants'], [{'name': name, 'run': records[name]['run'],
                                                'peer_run': records[name]['peer_run']} for name in ('astra', 'fable')])
        # while it waits, the steps read and checked before stand and the results are being prepared again
        waiting = progress.encounter_progress(self.encounter(encounter_id))
        self.assertEqual((waiting['phase'], [step['state'] for step in waiting['steps']]),
                         ('queued', ['done', 'done', 'done', 'waiting']))
        real = jobs.run_assessment

        def newer(*args, **kwargs):  # a newer reading, as the upgraded engine makes (an identical one keeps the final)
            result = real(*args, **kwargs)
            return dataclasses.replace(result, engine_version=result.engine_version + '+cux-flow')
        with mock.patch('studio.jobs.run_assessment', side_effect=newer):
            drain()
        again = self.encounter(encounter_id).current_assessment
        self.assertNotEqual(again, final)
        self.assertEqual(self.sends(), before)  # no ProviderRun, exchange or tool call: nothing was sent to anyone
        self.assertEqual(self.kinds(encounter_id)[-1], 'assess')  # and no peer stage was queued
        after = self.records(again)
        for name in ('astra', 'fable'):
            for field in ('state', 'run', 'reading_sha256', 'peer_state', 'peer_run', 'peer_sha256'):
                self.assertEqual(after[name][field], records[name][field], (name, field))
            self.assertNotIn('frozen', after[name])
        self.assertEqual((again.provider_run_id, again.context_id, jobs.assessment_phase(again), review.is_final(again)),
                         (final.provider_run_id, final.context_id, 2, True))
        (event,) = models.AuditEvent.objects.filter(event='assessment.refreshed')
        self.assertEqual((event.actor, event.data['job'], event.data['tag'], event.data['assessment']),
                         (self.reviewer, out['job'], 'cux-flow-r1', str(final.pk)))
        # the same release again queues nothing
        jobs_before = models.Job.objects.count()
        repeat = self.command('--encounter', encounter_id, '--tag', 'cux-flow-r1')
        self.assertEqual((repeat['action'], repeat['job'], repeat['key']), ('already_queued', out['job'], key))
        self.assertEqual(models.Job.objects.count(), jobs_before)
        self.assertEqual(models.AuditEvent.objects.filter(event='assessment.refreshed').count(), 1)

    def test_refused_while_busy_or_stopped_and_when_the_final_assessment_is_not_current(self):
        encounter_id = self.create(TWO_EXTENTS)
        self.refused(encounter_id, jobs.REASSESS_BUSY)  # its pipeline is still queued
        drain()
        encounter = self.encounter(encounter_id)
        final, first = encounter.current_assessment, self.assessments(encounter_id)[0]
        models.Encounter.objects.filter(pk=encounter_id).update(current_assessment=first)  # assess #1: peers owed
        self.refused(encounter_id, jobs.RETAINED_NOT_FINAL)
        models.Encounter.objects.filter(pk=encounter_id).update(current_assessment=final)
        stale = jobs.make_context(encounter, encounter.current_revision)  # the context changed since the final
        models.Encounter.objects.filter(pk=encounter_id).update(current_context=stale)
        self.refused(encounter_id, jobs.REASSESS_CONTEXT)
        models.Encounter.objects.filter(pk=encounter_id).update(current_context=final.context)
        jobs.stop_encounter(self.encounter(encounter_id), self.reviewer)
        self.refused(encounter_id, jobs.RETAINED_STOPPED)
        jobs.clear_stop(self.encounter(encounter_id))
        with override_settings(FABLE_MODE='disabled'):  # the re-assessment would read other answers than the final
            self.refused(encounter_id, 'The participants configured here are not the ones the final assessment read')
        astra = models.ProviderRun.objects.get(pk=self.records(final)['astra']['run'])
        kept = bytes(astra.response_bytes)
        models.ProviderRun.objects.filter(pk=astra.pk).update(response_bytes=b'{}')
        self.refused(encounter_id, jobs.RETAINED_BYTES.format(run=astra.pk))
        models.ProviderRun.objects.filter(pk=astra.pk).update(response_bytes=kept)
        # everything put back, the plan is accepted
        self.assertEqual(self.command('--encounter', encounter_id, '--tag', 'cux-flow-r2', '--dry-run')['action'],
                         'dry_run')
        for args, message in ((['--encounter', str(uuid.uuid4()), '--tag', 'x'], 'No document has that id.'),
                              (['--encounter', encounter_id, '--tag', 'two words'], jobs.RETAINED_TAG),
                              (['--encounter', encounter_id, '--tag', 'ok', '--username', 'nobody'],
                               'No active account has that username.')):
            with self.subTest(args), self.assertRaisesMessage(CommandError, message):
                self.command(*args)
        self.assertFalse(models.Job.objects.filter(idempotency_key__contains=':c:').exists())
