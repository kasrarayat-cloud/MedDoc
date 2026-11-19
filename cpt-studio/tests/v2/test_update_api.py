"""FINAL-V2 amendment 1 (docs/gemini-migration/AMENDMENT-1.md, adopted as DECISIONS D208): the codes are updated
automatically after a save - step 5d's half: the customer API (studio/api.py, cptstudio/urls.py), the details flow
(studio/answers.py), and the page's payload (studio/customer_api.py's update keys, applied by the integration owner on
5d's request, amendment 10). TEXT-ONLY and SYNTHETIC: the v2 and legacy fixtures of tests/v2/test_update_pipeline.py
(design v2's own InterpreterV2 with its one exchange answered there, the in-process Corti, the installed release's own
chain for a legacy encounter), the test-only v1 chain's recorded office note where a code must be decidable after the
update (tests.test_pipeline_api.RecordedInterpretation: event_coding@1, which the review overlay reads), and hand-made
assessments for "what changed" (tests/support/pipeline_factories.py). Nothing is sent anywhere.

11.1's tests whose subject lies in step 5d's files, by id (the rest are named in the step's NOTES): U1's API half (200
unchanged, 201 updating, 201 restored; /details reassessing and restored); U10's API half (decisions and exports 409, no
action offered, the second review refused, a decision 201 after completion); U11 what changed; U14's API half (the
duplicates, the addendum refusals); U15's page (the earlier codes read under their own label); U18's withdrawal; U19's
details half (the saved values while a case-B update is pending); U21's server half (the payload while pending).
"""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from studio import answers, customer_api, interpretation, jobs, models, progress, review
from studio.interpretation import sentinel
from studio.models import Decision, DecisionInvalidation
from studio.types import sha256_json
from tests.legacy_chain import legacy_chain
from tests.support import pipeline_factories as pf
from tests.test_pipeline_api import PipelineApiCase, RecordedInterpretation, drain
from tests import v2_documents, v2_replay  # DECISIONS D243: the u10 test's rows (step q02)
from tests.v2.test_jobs import BARE_429, EXTRACTION, HTTP_500, POLYP, answered
from tests.v2.test_update_pipeline import D1, D2, D3, HOSPITAL, OFFICE, UNDATED, UpdateCase, corti_refusal

Run, Job = models.ProviderRun, models.Job
ROOT = Path(settings.BASE_DIR)
APP = (ROOT / 'studio' / 'static' / 'studio' / 'app.js').read_text(encoding='utf-8')


def rows_now():
    """The row counts a save that changes nothing must leave as they are (1.2: not even an audit row)."""
    return {model.__name__: model.objects.count() for model in (models.EncounterContext, Job, models.AuditEvent, Run)}


class ApiCase(UpdateCase):
    """The amendment's fixtures, driven through the customer API by a reviewer of the workspace."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def membership(self):
        return models.Membership.objects.get(workspace=self.ws, user=self.user)

    def post(self, path, data=None):
        return self.client.post(path, json.dumps(data or {}), content_type='application/json')

    def context(self, encounter, **values):
        return self.post(f'/api/encounters/{encounter.pk}/context', values)

    def details(self, encounter, *answers_):
        return self.post(f'/api/encounters/{encounter.pk}/details',
                         {'answers': [{'id': ident, 'fact': fact, 'value': value} for ident, fact, value in answers_]})

    def doc(self, encounter):
        response = self.client.get(f'/api/encounters/{encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def row_of(self, encounter, fact):
        found = [row for row in self.doc(encounter)['details_needed'] if row['fact'] == fact]
        self.assertTrue(found, f'no {fact} row')
        return found[0]

    def drained(self, encounter):
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row), progress.encounter_progress(row))
        return row


# --- the page's copies of the server's sentences -----------------------------------------------------------------------

def js_string(name):
    found = re.search(rf"^const {name} = '((?:[^'\\]|\\.)*)';$", APP, re.M)
    if found is None:
        raise AssertionError(f'app.js has no {name}')
    return found.group(1).replace("\\'", "'")


def js_notes(name):
    found = re.search(rf'^const {name} = \{{\n((?:.|\n)*?)^\}};', APP, re.M)
    if found is None:
        raise AssertionError(f'app.js has no {name}')
    return dict(re.findall(r"^  (updating|other): '((?:[^'\\]|\\.)*)',$", found.group(1), re.M))


class PageTextTests(SimpleTestCase):
    """The page draws step 3c's sentences, never re-worded: app.js's copies equal customer_api's, and the details flow's
    copy of the answer sentence equals the server's (customer_api imports answers, so answers holds an equal literal)."""

    def test_the_page_holds_the_servers_update_sentences_verbatim(self):
        for name in ('UPDATE_TITLE', 'UPDATE_TITLE_CHECK', 'CHANGE_SAVED_BY', 'EARLIER_CODES_HEADING',
                     'EARLIER_CODES_HEADING_CHECK', 'EARLIER_CODES_MADE', 'EARLIER_CODES_MADE_CHECK', 'ANSWER_AFTER_UPDATE',
                     'RESULTS_UPDATING', 'RESULTS_NOT_UPDATED', 'RESULTS_EARLIER_SHOWN', 'RESULTS_NO_EARLIER_CODE',
                     'TALLY_BEFORE', 'TALLY_NO_EARLIER_CODE', 'RESULTS_UPDATING_CHECK', 'RESULTS_NOT_UPDATED_CHECK',
                     'RESULTS_EARLIER_SHOWN_CHECK', 'RESULTS_NO_EARLIER_CODE_CHECK', 'TALLY_BEFORE_CHECK',
                     'TALLY_NO_EARLIER_CODE_CHECK', 'RESTORED_TOAST', 'WHAT_CHANGED_COMPARED', 'WHAT_CHANGED_UNCHANGED',
                     'WHAT_CHANGED_UNCHANGED_ONE', 'EARLIER_DOWNLOAD', 'RETRY_UPDATE_ASKED'):
            with self.subTest(name=name):
                self.assertEqual(js_string(name), getattr(customer_api, name))
        self.assertEqual(js_notes('UPDATE_EXPORT_NOTE'), customer_api.UPDATE_EXPORT_NOTE)
        self.assertEqual(js_notes('UPDATE_EXPORT_NOTE_CHECK'), customer_api.UPDATE_EXPORT_NOTE_CHECK)
        self.assertIn(f"updating: '{customer_api.STATE_LABELS['updating']}'", APP)
        self.assertIn(f"  updating: '{customer_api.UPDATE_TITLE}',", APP)  # PHASE_TITLES
        self.assertEqual(answers.ANSWER_AFTER_UPDATE, customer_api.ANSWER_AFTER_UPDATE)
        self.assertIn("retry_update: ['retry-update', 'Try updating again']", APP)
        self.assertEqual(customer_api.UPDATE_ACTION_LABELS['retry_update'], 'Try updating again')

    def test_every_refusal_this_step_raises_reaches_the_member_in_its_own_words(self):
        for text in (answers.ANSWER_AFTER_UPDATE, customer_api.UPDATE_ANSWER_WITHDRAW, customer_api.UPDATE_DECISION,
                     customer_api.UPDATE_EXPORT, customer_api.UPDATE_EXPORT_CHECK, customer_api.ADDENDUM_TOO_LONG,
                     customer_api.ADDENDUM_UNPREPARED, customer_api.ADDENDUM_DOCUMENT_TOO_LONG,
                     customer_api.ADDENDUM_DOCUMENT_UNPREPARED, customer_api.ADDENDUM_DUPLICATE.format(n=7),
                     customer_api.RETRY_UPDATE_NOTHING, customer_api.RETRY_UPDATE_HELD, customer_api.RETRY_UPDATE_READING,
                     customer_api.RETRY_UPDATE_REFUSED_BEFORE, jobs.RETRY_BUSY):
            with self.subTest(text=text):
                self.assertEqual(customer_api.customer_error(text), text)
                self.assertIsNone(customer_api.FORBIDDEN.search(text))

    def test_the_pages_own_update_sentences_pass_the_customer_scan(self):
        """refute-5d-r1 P4: every sentence the page draws for an update is the server's, and none names a provider, a
        model or a held fact's cause - the retry toast and the removed-choice lines included."""
        names = re.findall(r"^const ([A-Z_]+) = '", APP, re.M)
        drawn = [js_string(name) for name in names if name.startswith(('UPDATE_', 'EARLIER_', 'RESULTS_', 'TALLY_',
                                                                         'WHAT_CHANGED_', 'RETRY_', 'RESTORED_',
                                                                         'ANSWER_AFTER', 'CHANGE_'))]
        self.assertIn(customer_api.RETRY_UPDATE_ASKED, drawn)
        drawn += [customer_api.CHANGE_CHOICE_REMOVED.format(label=label)
                  for label in customer_api.WHAT_CHANGED_DETAIL_LABELS.values()]
        for text in drawn:
            with self.subTest(text=text):
                self.assertIsNone(customer_api.FORBIDDEN.search(text))
                for cause in customer_api.HELD_FACT_CAUSES:
                    self.assertNotIn(cause, text)

    def test_the_retry_update_route_names_the_view(self):
        from django.urls import resolve

        match = resolve('/api/encounters/0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f/retry-update')
        self.assertEqual(match.func.__name__, 'retry_update')


# --- U1: triggers, through the API --------------------------------------------------------------------------------------

class TriggerApiTests(ApiCase):
    """U1's API half (1.3 [R:truth-T13]): an identical save, through /context and through /details, answers 200
    unchanged and writes nothing; each real change answers 201 updating and records one context.changed row; a save back
    to the earlier codes' own values answers restored."""

    def test_u1_identical_and_empty_saves_answer_200_unchanged_and_write_nothing(self):
        encounter = self.v2_fixture(UNDATED)
        before = rows_now()
        response = self.context(encounter, setting='')  # clearing an absent value
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'context_id': str(encounter.current_context_id), 'unchanged': True,
                                           'updating': False})
        self.assertEqual(rows_now(), before)
        response = self.context(encounter, service_date=D2)
        self.assertEqual((response.status_code, response.json()['updating']), (201, True))
        self.drained(encounter)
        before = rows_now()
        response = self.context(encounter, service_date=D2)  # the same value again: a double submission
        self.assertEqual((response.status_code, response.json()['unchanged']), (200, True))
        self.assertEqual(rows_now(), before)
        row = self.row_of(encounter, 'service_date')
        response = self.details(encounter, (row['id'], 'service_date', D2))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'saved': 0, 'unchanged': 1, 'answer_ids': [], 'reassessing': False,
                                           'restored': False})
        self.assertEqual(rows_now(), before)

    def test_u1_each_real_change_records_one_context_changed_row_and_a_restore_answers_restored(self):
        encounter = self.v2_fixture(UNDATED)
        changed = models.AuditEvent.objects.filter(encounter=encounter, event='context.changed')
        for count, values in enumerate(({'service_date': D2}, {'setting': OFFICE}, {'billing_context': 'facility'}),
                                       start=1):
            with self.subTest(values=values):
                response = self.context(encounter, **values)
                self.assertEqual(response.status_code, 201, response.content)
                self.assertEqual(response.json(), {'context_id': str(self.fresh_row(encounter).current_context_id),
                                                   'updating': True})
                self.assertEqual(changed.count(), count)
                self.drained(encounter)
        response = self.context(encounter, billing_context='professional')
        self.assertEqual(response.json()['updating'], True)
        restored = self.context(encounter, billing_context='facility')  # the earlier codes' own value, while pending
        self.assertEqual(restored.status_code, 201, restored.content)
        self.assertEqual(restored.json(), {'context_id': str(self.fresh_row(encounter).current_context_id),
                                           'updating': False, 'restored': True})
        self.assertTrue(review.fresh(self.fresh_row(encounter)))
        self.assertEqual(changed.filter(data__has_key='restored').count(), 1)

    def test_u1_a_details_save_answers_reassessing_from_the_update_and_restored_for_a_restore(self):
        encounter = self.v2_fixture(UNDATED)
        row = self.row_of(encounter, 'service_date')
        response = self.details(encounter, (row['id'], 'service_date', D2))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()['reassessing'], response.json()['restored']), (True, False))
        self.drained(encounter)
        row = self.row_of(encounter, 'service_date')
        moved = self.details(encounter, (row['id'], 'service_date', D3))
        self.assertEqual((moved.status_code, moved.json()['reassessing']), (201, True))
        row = self.row_of(encounter, 'service_date')
        back = self.details(encounter, (row['id'], 'service_date', D2))  # the earlier codes' own date: a restore
        self.assertEqual(back.status_code, 201, back.content)
        self.assertEqual((back.json()['reassessing'], back.json()['restored']), (False, True))
        self.assertTrue(review.fresh(self.fresh_row(encounter)))


class TriggerV1ApiTests(RecordedInterpretation, PipelineApiCase):
    """U1's patient status half: the one coding-context field only the details panel saves (the office note asks it, on
    the test-only v1 chain), one context.changed row; and U10's last clause - after the update completes, a decision on
    the updated codes answers 201 (u10 runs on design v2's path in replay, whose codes the review overlay reads from
    event_coding@2: DECISIONS D243 class C)."""

    def test_u1_a_patient_status_saved_in_the_details_panel_is_one_context_changed_row(self):
        encounter_id = self.create()
        drain()
        doc = self.client.get(f'/api/encounters/{encounter_id}').json()
        [row] = [item for item in doc['details_needed'] if item['fact'] == 'patient_status']
        changed = models.AuditEvent.objects.filter(encounter_id=encounter_id, event='context.changed')
        response = self.post(f'/api/encounters/{encounter_id}/details',
                             {'answers': [{'id': row['id'], 'fact': 'patient_status', 'value': 'established'}]})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(changed.count(), 1)
        self.assertEqual(response.json()['reassessing'], True)

    @v2_replay.applied  # DECISIONS D243 class C
    def test_u10_during_the_update_a_decision_is_refused_and_after_it_one_answers_201(self):
        # DECISIONS D243 (step q02, by agreement with 5d): the review overlay reads event_coding@2 only (FINAL-V2 6.5), so
        # the codes that must be decidable after the update are design v2's, read in replay (tests/v2_replay.py) from the
        # office note with its clinician named (tests/v2_documents.OFFICE_NOTE) - never the v1 chain's
        encounter_id = self.create(v2_documents.OFFICE_NOTE)
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual((response.status_code, response.json()['updating']), (201, True))
        doc = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertEqual(doc['codes'], [])
        [earlier] = doc['earlier_codes']
        self.assertEqual(earlier['allowed_actions'], [])
        refused = self.post(f'/api/encounters/{encounter_id}/decisions',
                            {'proposal_id': earlier['id'], 'action': 'reject', 'note': 'Synthetic.'})
        self.assertEqual(refused.status_code, 409, refused.content)
        self.assertEqual(refused.json()['error'], customer_api.UPDATE_DECISION)
        self.assertFalse(Decision.objects.filter(encounter_id=encounter_id).exists())
        drain()
        doc = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertIsNone(doc['update'])
        [code] = doc['codes']
        self.assertTrue(code['allowed_actions'], code)
        action = 'approve' if 'approve' in code['allowed_actions'] else code['allowed_actions'][0]
        decided = self.post(f'/api/encounters/{encounter_id}/decisions',
                            {'proposal_id': code['id'], 'action': action, 'note': 'Synthetic.',
                             'acknowledgement': review.ACKNOWLEDGEMENTS['human'] if action == 'approve' else ''})
        self.assertEqual(decided.status_code, 201, decided.content)


# --- U10: binding and refusals, through the API -------------------------------------------------------------------------

class BindingApiTests(ApiCase):
    """U10's API half (5.3, A7): while an update is pending every decision answers 409 UPDATE_DECISION and writes no
    Decision; each export answers 409 UPDATE_EXPORT and writes no ReportArtifact; the earlier codes offer no action;
    the second review is neither offered nor accepted."""

    def test_u10_each_decision_answers_409_update_decision_and_writes_nothing(self):
        encounter = self.legacy_fixture()
        proposal = encounter.current_assessment.proposals.get(code='45378')
        self.assertIn('approve', review.allowed_actions(proposal, encounter.current_assessment, self.membership()))
        self.save(encounter, setting=OFFICE)
        for action in ('approve', 'reject', 'revoke', 'reinstate', 'confirm'):
            with self.subTest(action=action):
                response = self.post(f'/api/encounters/{encounter.pk}/decisions',
                                     {'proposal_id': str(proposal.pk), 'action': action, 'note': 'Synthetic.',
                                      'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
                self.assertEqual(response.status_code, 409, response.content)
                self.assertEqual(response.json()['error'], customer_api.UPDATE_DECISION)
        self.assertFalse(Decision.objects.filter(encounter=encounter).exists())

    def test_u10_both_exports_answer_409_update_export_and_write_nothing(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        for kind in ('draft', 'approved', 'reviewed'):
            for fmt in ('txt', 'csv'):
                with self.subTest(kind=kind, fmt=fmt):
                    response = self.post(f'/api/encounters/{encounter.pk}/reports', {'kind': kind, 'fmt': fmt})
                    self.assertEqual(response.status_code, 409, response.content)
                    self.assertEqual(response.json()['error'], customer_api.UPDATE_EXPORT)
                    self.assertEqual(response.json()['details']['blockers'],
                                     [customer_api.UPDATE_BLOCKER_WORDS[('updating', 'details')]])  # the state's words
        self.assertFalse(models.ReportArtifact.objects.filter(encounter=encounter).exists())

    def test_u10_the_earlier_codes_offer_no_action_and_the_second_review_is_refused_during_an_idle_update(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        jobs.stop_encounter(self.fresh_row(encounter), self.user)  # idle: nothing serves the update
        doc = self.doc(encounter)
        self.assertEqual(doc['codes'], [])
        self.assertTrue(doc['earlier_codes'])
        self.assertTrue(all(code['allowed_actions'] == [] for code in doc['earlier_codes']))
        self.assertEqual(doc['recheck'], {'available': False, 'can_request': False})
        self.assertEqual(doc['readiness'], {'draft': False, 'approved': False,
                                            'blockers': [customer_api.UPDATE_BLOCKER_WORDS[('other', 'details')]]})
        response = self.post(f'/api/encounters/{encounter.pk}/second-review')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], customer_api.UPDATE_DECISION)
        self.assertFalse(Job.objects.filter(encounter=encounter, kind=Job.REVIEW2).exists())
        self.assertFalse(models.AuditEvent.objects.filter(encounter=encounter,
                                                          event='provider.second_review_requested').exists())


    def test_u10_the_second_review_is_neither_offered_nor_accepted_on_a_v2_revision_read_at_an_older_version(self):
        """U10's T15 clause as 11.1 writes it [R:truth-T15]: an idle case-B update on a v2 revision whose inventory is of
        an older version. The save keeps the context, a gemini context (only the values change), so nothing but the
        pending update keeps the bounded second review from being offered and accepted: with something left for it to
        ask, it is offered while the codes are fresh (the control), and during the idle update it is neither offered nor
        accepted - the decision sentence, no review2 job, no provider.second_review_requested row."""
        encounter = self.v2_fixture()
        context = encounter.current_context
        inventory = models.EventInventory.objects.get(pk=context.event_inventory_id)
        # an install that bumped the inventory version: the stored inventory (immutable) is now of an older version
        newer = (inventory.interpretation_version, f'{inventory.inventory_version}-synthetic-next')
        left = ([{'label': 'Synthetic documented service left without a supported code'}], (0, 24))
        with mock.patch.object(jobs, 'current_versions', return_value=newer), \
                mock.patch.object(jobs, '_second_review_items', return_value=left):
            row = self.fresh_row(encounter)
            self.assertTrue(interpretation.is_new_context(row.current_context))
            self.assertTrue(review.reading_owed(row))
            self.assertTrue(review.fresh(row))
            self.assertEqual(self.doc(encounter)['recheck'], {'available': True, 'can_request': True})  # the control
            self.save(encounter, setting=OFFICE)  # case B: the values saved, the context kept until the update's analyze
            row = self.fresh_row(encounter)
            self.assertEqual(row.current_context_id, context.pk)
            self.assertTrue(review.update_pending(row))
            jobs.stop_encounter(row, self.user)  # idle: nothing serves the update
            self.assertFalse(review.busy_targets(self.fresh_row(encounter)))
            doc = self.doc(encounter)
            self.assertEqual((doc['update']['state'], doc['recheck']), ('stopped', {'available': False,
                                                                                    'can_request': False}))
            response = self.post(f'/api/encounters/{encounter.pk}/second-review')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], customer_api.UPDATE_DECISION)
        self.assertFalse(Job.objects.filter(encounter=encounter, kind=Job.REVIEW2).exists())
        self.assertFalse(models.AuditEvent.objects.filter(encounter=encounter,
                                                          event='provider.second_review_requested').exists())


# --- U14: duplicates, and the addendum refusals ---------------------------------------------------------------------------

class DuplicateApiTests(ApiCase):
    """U14's API half (3.9, A12, A13 [R:truth-T7][R2:truth-RT7]): duplicates write nothing; an addendum whose update
    could never finish is refused before anything is written, its sentence naming where the cause is; no addendum
    refusal says the codes shown stay."""

    def addendum(self, encounter, text='Synthetic addendum: the scope was withdrawn without a biopsy.'):
        return self.post(f'/api/encounters/{encounter.pk}/addenda', {'text': text, 'synthetic_attestation': 'yes'})

    def assertNothingWritten(self, encounter, response, sentence, counts):  # noqa: N802 - unittest's naming
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], sentence)
        self.assertNotIn('stay as they are', sentence)
        self.assertEqual((models.SourceRevision.objects.filter(encounter=encounter).count(),
                          DecisionInvalidation.objects.count(), Job.objects.filter(encounter=encounter).count()), counts)

    def counts(self, encounter):
        return (models.SourceRevision.objects.filter(encounter=encounter).count(), DecisionInvalidation.objects.count(),
                Job.objects.filter(encounter=encounter).count())

    def test_u14_two_identical_details_posts_and_two_tabs_saving_different_fields(self):
        encounter = self.v2_fixture(UNDATED)
        row = self.row_of(encounter, 'service_date')
        first = self.details(encounter, (row['id'], 'service_date', D2))
        self.assertEqual(first.status_code, 201, first.content)
        before = rows_now()
        second = self.details(encounter, (row['id'], 'service_date', D2))
        self.assertEqual((second.status_code, second.json()['saved'], second.json()['unchanged']), (200, 0, 1))
        self.assertEqual(rows_now(), before)
        # two tabs, two different fields, before the worker runs: both stored, the newer supersedes the older's chain
        self.assertEqual(self.context(encounter, setting=OFFICE).status_code, 201)
        self.assertEqual(self.context(encounter, billing_context='facility').status_code, 201)
        row = self.drained(encounter)
        self.assertEqual(review.values(row.current_assessment.context),
                         {'service_date': D2, 'setting': OFFICE, 'billing_context': 'facility'})

    def test_u14_a_repeated_addendum_answers_409_addendum_duplicate_and_adds_no_revision(self):
        encounter = self.v2_fixture()
        response = self.addendum(encounter)
        self.assertEqual((response.status_code, response.json()), (201, {'revision': 2}))
        counts = self.counts(encounter)
        again = self.addendum(encounter)  # the double click, or a second tab
        self.assertNothingWritten(encounter, again, customer_api.ADDENDUM_DUPLICATE.format(n=2), counts)
        # another text is no duplicate, and once the first one's text is read an addendum is accepted while its
        # processing runs (A1: no busy refusal)
        self.run_next(Job.EXTRACT)
        self.assertTrue(jobs.busy(self.fresh_row(encounter)))
        other = self.addendum(encounter, 'Synthetic addendum: the preparation was adequate.')
        self.assertEqual((other.status_code, other.json()), (201, {'revision': 3}))

    def test_u14_an_addendum_over_the_character_bound_or_that_cannot_be_framed_adds_nothing(self):
        encounter = self.v2_fixture()
        counts = self.counts(encounter)
        with override_settings(INTERPRET_MAX_CHARS=len(encounter.current_revision.text) + 40):
            self.assertNothingWritten(encounter, self.addendum(encounter, 'Synthetic addendum. ' * 4),
                                      customer_api.ADDENDUM_TOO_LONG, counts)
        self.assertNothingWritten(encounter, self.addendum(encounter, 'As stated in [S2], the cecum was reached.'),
                                  customer_api.ADDENDUM_UNPREPARED, counts)

    def test_u14_a_cause_in_the_document_itself_is_named_as_the_documents(self):
        framed = POLYP.replace('Findings:', 'Findings [S2]:')
        with legacy_chain():
            encounter, _ = self.upload(framed)
            self.drain()
        encounter.refresh_from_db()
        counts = self.counts(encounter)
        self.assertNothingWritten(encounter, self.addendum(encounter), customer_api.ADDENDUM_DOCUMENT_UNPREPARED, counts)
        self.new_workspace()
        plain = self.legacy_fixture(POLYP)
        counts = self.counts(plain)
        with override_settings(INTERPRET_MAX_PAGES=0):
            self.assertNothingWritten(plain, self.addendum(plain), customer_api.ADDENDUM_DOCUMENT_TOO_LONG, counts)
        with override_settings(INTERPRET_MAX_CHARS=len(plain.current_revision.text) - 1):
            self.assertNothingWritten(plain, self.addendum(plain), customer_api.ADDENDUM_DOCUMENT_TOO_LONG, counts)

    def test_u14_an_over_bound_addendum_during_a_first_processing_is_refused_and_an_in_bound_one_accepted(self):
        encounter, _ = self.upload()
        self.run_next(Job.EXTRACT)  # the text is read; the reading is queued: a first processing, no codes shown
        encounter.refresh_from_db()
        self.assertTrue(jobs.busy(encounter))
        counts = self.counts(encounter)
        with override_settings(INTERPRET_MAX_CHARS=len(encounter.current_revision.text) + 40):
            self.assertNothingWritten(encounter, self.addendum(encounter, 'Synthetic addendum. ' * 4),
                                      customer_api.ADDENDUM_TOO_LONG, counts)
        accepted = self.addendum(encounter)
        self.assertEqual(accepted.status_code, 201, accepted.content)

    def test_u14_a_double_retry_is_refused(self):
        encounter = self.v2_fixture(UNDATED)
        self.corti.outcomes = [corti_refusal(500)]
        self.save(encounter, service_date=D2)
        self.drain()
        self.assertEqual(review._derive_state(self.fresh_row(encounter)), 'provider_failed')
        first = self.post(f'/api/encounters/{encounter.pk}/retry-update')
        self.assertEqual((first.status_code, first.json()), (201, {'retrying': True}))
        second = self.post(f'/api/encounters/{encounter.pk}/retry-update')
        self.assertEqual(second.status_code, 409, second.content)
        self.assertEqual(second.json()['error'], jobs.RETRY_BUSY)
        self.assertEqual(models.AuditEvent.objects.filter(encounter=encounter, event='update.retry').count(), 1)
        self.drain()
        self.assertTrue(review.fresh(self.fresh_row(encounter)))
        nothing = self.post(f'/api/encounters/{encounter.pk}/retry-update')
        self.assertEqual((nothing.status_code, nothing.json()['error']), (409, customer_api.RETRY_UPDATE_NOTHING))

    def test_a_viewer_cannot_retry_an_update(self):
        encounter = self.v2_fixture(UNDATED)
        viewer = models.User.objects.create_user('synthetic-viewer', password='synthetic-pass-123!')
        models.Membership.objects.create(user=viewer, workspace=self.ws, role=models.Membership.VIEWER)
        client = Client()
        client.force_login(viewer)
        response = client.post(f'/api/encounters/{encounter.pk}/retry-update', '{}', content_type='application/json')
        self.assertEqual(response.status_code, 403, response.content)


# --- U18 and 1.4: answers while an update is pending ----------------------------------------------------------------------

class AnswerApiTests(ApiCase):
    """1.4's narrowed refusal and U18's withdrawal [R:truth-T12]: an answer is never recorded while a stage runs or an
    update is pending, and never withdrawn while an update is pending; a context save is accepted then."""

    def answered(self):
        """A legacy encounter (POLYP: its base_included question) whose question was answered "Not documented"."""
        encounter = self.legacy_fixture(POLYP)
        row = self.row_of(encounter, 'base_included')
        response = self.details(encounter, (row['id'], 'base_included', 'not_documented'))
        self.assertEqual(response.status_code, 201, response.content)
        [answer] = models.MemberAnswer.objects.filter(encounter=encounter)
        return encounter, answer

    def test_u18_a_withdrawal_during_an_idle_update_answers_409_and_writes_no_revocation(self):
        encounter, answer = self.answered()
        self.save(encounter, setting=OFFICE)
        jobs.stop_encounter(self.fresh_row(encounter), self.user)  # idle: the update waits
        self.assertTrue(review.update_pending(self.fresh_row(encounter)))
        response = self.post(f'/api/encounters/{encounter.pk}/details/{answer.pk}/revoke')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], customer_api.UPDATE_ANSWER_WITHDRAW)
        self.assertFalse(models.MemberAnswerRevocation.objects.filter(answer=answer).exists())
        self.assertNotIn('revoke-detail', json.dumps(self.doc(encounter)['earlier_answers']))

    def test_an_answer_while_an_update_is_pending_is_refused_and_a_context_save_accepted(self):
        encounter = self.legacy_fixture(POLYP)
        row = self.row_of(encounter, 'base_included')
        self.save(encounter, setting=OFFICE)  # an update pending, its reading queued
        response = self.details(encounter, (row['id'], 'base_included', 'not_documented'))
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], answers.ANSWER_AFTER_UPDATE)
        self.assertFalse(models.MemberAnswer.objects.filter(encounter=encounter).exists())
        saved = self.context(encounter, billing_context='facility')  # a rapid successive edit: accepted (A1)
        self.assertEqual((saved.status_code, saved.json()['updating']), (201, True))

    def test_an_answer_while_a_stage_runs_outside_an_update_is_refused_busy_and_a_context_save_accepted(self):
        encounter = self.legacy_fixture(POLYP)
        row = self.row_of(encounter, 'base_included')
        revision = encounter.current_revision
        pf.job(encounter, revision, Job.ASSESS, Job.RUNNING, context=encounter.current_context)  # a stage at work
        self.assertFalse(review.update_pending(self.fresh_row(encounter)))
        response = self.details(encounter, (row['id'], 'base_included', 'not_documented'))
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], answers.BUSY)
        self.assertFalse(models.MemberAnswer.objects.filter(encounter=encounter).exists())
        saved = self.context(encounter, setting=OFFICE)
        self.assertEqual(saved.status_code, 201, saved.content)


# --- U19: the saved values while a case-B update is pending ---------------------------------------------------------------

class CaseBDetailsTests(ApiCase):
    """U19's details half [R:truth-T3]: while a case-B update is pending the date block and the rows show the saved
    values, assert no member conflict, keep the document's own date and quote; the customer state and the list row agree
    with the update's own state; a reload shows the same."""

    def held(self):
        with legacy_chain():
            encounter, _ = self.upload(values={'service_date': D2})  # NOTE states D1: a member date conflict
            self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(progress.date_held(row))
        return encounter

    def list_row(self, encounter):
        [found] = [item for item in self.client.get('/api/encounters').json()['encounters']
                   if item['id'] == str(encounter.pk)]
        return found

    def test_u19_use_document_date_shows_the_saved_value_and_follows_the_update_not_the_kept_conflict(self):
        encounter = self.held()
        date = self.row_of(encounter, 'service_date')
        self.assertIn('use_document', [choice['value'] for choice in date['choices']])
        self.assertEqual(self.list_row(encounter)['state'], 'action_needed')
        response = self.details(encounter, (date['id'], 'service_date', 'use_document'))
        self.assertEqual(response.status_code, 201, response.content)
        row = self.fresh_row(encounter)
        self.assertNotEqual(review.values(row), review.values(row.current_context))  # case B: the context kept
        for _ in range(2):  # and again on a reload: derived from rows
            doc = self.doc(encounter)
            self.assertEqual(doc['service_date'], {
                'value': D1, 'source': 'document', 'document_value': D1,
                'document_quote': answers.service_date_block(row)['document_quote'], 'entered_value': None,
                'conflict': False, 'can_use_document_date': False})
            self.assertIsNotNone(doc['service_date']['document_quote'])
            self.assertEqual((doc['state'], doc['progress']['phase']), ('updating', 'updating'))
            for item in doc['details_needed']:  # the earlier codes' own date question, if any, reads the saved values
                if item['fact'] == 'service_date':
                    self.assertEqual((item['entered_value'], item['prompt']), (None, answers.DATE_PROMPTS['asked']))
                    self.assertNotIn('use_document', [choice['value'] for choice in item['choices']])
            listed = self.list_row(encounter)
            self.assertEqual((listed['state'], listed['service_date'], listed['date_conflict']), ('updating', D1, False))
        # the reading then fails: the update's own state, never the kept context's conflict
        self.interpreter.script = {EXTRACTION: [answered(HTTP_500, status=500)]}
        self.drain()
        doc = self.doc(encounter)
        self.assertEqual((doc['state'], doc['progress']['phase'], doc['progress']['error']['action']),
                         ('failed', 'failed', 'retry_reading'))
        self.assertEqual(self.list_row(encounter)['state'], 'failed')
        self.assertEqual(doc['update']['state'], 'failed')
        # then pausing under a hold: Try reading again meets a bare 429
        self.interpreter.script = {EXTRACTION: [answered(BARE_429, status=429)]}
        self.assertEqual(self.post(f'/api/encounters/{encounter.pk}/retry-reading').status_code, 201)
        self.drain()
        doc = self.doc(encounter)
        self.assertEqual((doc['progress']['phase'], doc['update']['state']), ('paused', 'paused'))
        self.assertEqual(doc['state'], 'stopped')
        self.assertNotEqual(self.list_row(encounter)['state'], 'action_needed')

    def test_u19_a_case_b_date_change_with_no_conflict_shows_the_saved_date(self):
        with legacy_chain():
            encounter, _ = self.upload(UNDATED)
            self.drain()
        self.save(encounter, service_date=D2)  # case B: stored, the context kept
        row = self.fresh_row(encounter)
        block = answers.service_date_block(row)
        self.assertEqual((block['value'], block['source'], block['entered_value'], block['conflict']),
                         (D2, 'member', D2, False))
        [date] = [item for item in self.doc(encounter)['details_needed'] if item['fact'] == 'service_date']
        self.assertEqual(date['entered_value'], D2)
        self.assertEqual(date['saved']['value'], D2)  # the saved date, attributed to the save that stored it
        self.assertEqual(date['saved']['by'], self.user.label())


# --- U21, U15, U22: the payload while an update is pending ----------------------------------------------------------------

class PayloadTests(ApiCase):
    """U21's server half [R:truth-T4][R:truth-T5][R:truth-T6]: while an update is pending ``codes`` is [] and every
    assessment-derived key is the earlier codes', none from an assessment of the update that is not final; the update
    block in each state and kind; U15's page: the earlier codes of a legacy encounter read under their own label."""

    def test_u21_every_assessment_derived_key_is_the_earlier_codes_and_the_update_block_says_what_was_saved(self):
        encounter = self.legacy_fixture(POLYP)
        earlier = encounter.current_assessment
        fresh = customer_api.encounter_json(self.fresh_row(encounter), self.membership())
        self.assertIsNone(fresh['update'])
        self.save(encounter, setting=HOSPITAL)
        doc = self.doc(encounter)
        self.assertEqual(doc['codes'], [])
        self.assertEqual([code['id'] for code in doc['earlier_codes']], [code['id'] for code in fresh['codes']])
        self.assertEqual([code['allowed_actions'] for code in doc['earlier_codes']], [[]] * len(fresh['codes']))
        for key in ('other_codes', 'not_separately_coded', 'unresolved', 'limitations', 'earlier_answers'):
            self.assertEqual(doc[key], fresh[key], key)
        update = doc['update']
        self.assertEqual({key: update[key] for key in ('pending', 'state', 'kind', 'restorable', 'changes', 'saved_by')},
                         {'pending': True, 'state': 'updating', 'kind': 'details', 'restorable': True,
                          'changes': ['Place of service: Hospital outpatient department'], 'saved_by': self.user.label()})
        self.assertEqual(update['started_at'], update['saved_at'])
        self.assertEqual(update['earlier'], {
            'made_at': earlier.created_at.isoformat(), 'revision': 1, 'service_date': '14 March 2031',
            'details': ['Date of service: 14 March 2031', 'Place of service: not documented', 'Patient: not documented',
                        'Claim: not documented']})
        self.assertIsNone(doc['what_changed'])
        self.save(encounter, billing_context='facility')  # a second save: the same update, its first save's time
        later = self.doc(encounter)['update']
        self.assertEqual(later['started_at'], update['started_at'])
        self.assertEqual(later['changes'], ['Place of service: Hospital outpatient department', 'Claim: Facility claim'])
        self.save(encounter, service_date=D2)
        self.assertEqual(self.doc(encounter)['update']['changes'][0], 'Date of service: 15 March 2031')
        self.save(encounter, service_date='')
        self.assertEqual(self.doc(encounter)['update']['changes'][0], 'Place of service: Hospital outpatient department')
        for text in later['changes'] + later['earlier']['details']:
            self.assertIsNone(customer_api.FORBIDDEN.search(text), text)

    def test_u21_nothing_is_read_from_the_updates_assess_1_that_is_not_final(self):
        encounter = self.v2_fixture()
        earlier = encounter.current_assessment
        before = self.doc(encounter)
        self.save(encounter, setting=OFFICE)
        real = jobs.owed_peer_stages

        def owes(assessment):
            return ('astra_peer',) if assessment.pk != earlier.pk else real(assessment)
        with mock.patch.object(jobs, 'owed_peer_stages', side_effect=owes), \
                mock.patch.object(jobs, '_queue_peers', return_value=None):
            self.drain()
        made = models.Assessment.objects.filter(encounter=encounter).exclude(pk=earlier.pk).get()
        with mock.patch.object(jobs, 'owed_peer_stages', side_effect=owes):
            row = self.fresh_row(encounter)
            self.assertEqual(row.current_assessment_id, earlier.pk)  # A17: recorded, never current
            doc = customer_api.encounter_json(row, self.membership())
        self.assertTrue(doc['update']['pending'])
        self.assertEqual([code['id'] for code in doc['earlier_codes']], [code['id'] for code in before['codes']])
        made_ids = {str(pk) for pk in made.proposals.values_list('pk', flat=True)}
        self.assertFalse(made_ids & {code['id'] for code in doc['earlier_codes'] + doc['codes']})

    def test_u21_the_update_state_follows_the_update_and_every_text_is_true_for_it(self):
        encounter = self.v2_fixture(UNDATED)
        self.corti.outcomes = [corti_refusal(500)]
        self.save(encounter, service_date=D2)
        doc = self.doc(encounter)
        self.assertEqual((doc['update']['state'], doc['state']), ('updating', 'updating'))
        self.drain()
        doc = self.doc(encounter)
        self.assertEqual((doc['update']['state'], doc['progress']['phase'], doc['progress']['error']['action']),
                         ('failed', 'failed', 'retry_update'))
        self.assertEqual(doc['progress']['error']['text'], customer_api.update_text('review_failed', 'details', True))
        self.assertEqual(doc['readiness']['blockers'], [customer_api.UPDATE_BLOCKER_WORDS[('other', 'details')]])
        self.assertNotIn('being updated', json.dumps(doc))
        self.assertEqual(self.post(f'/api/encounters/{encounter.pk}/retry-update').status_code, 201)
        jobs.stop_encounter(self.fresh_row(encounter), self.user)
        doc = self.doc(encounter)
        self.assertEqual((doc['update']['state'], doc['state']), ('stopped', 'stopped'))
        self.assertNotIn('being updated', json.dumps(doc))

    def test_u21_documentation_and_check_updates(self):
        encounter = self.v2_fixture()
        response = self.post(f'/api/encounters/{encounter.pk}/addenda',
                             {'text': 'Synthetic addendum: the preparation was adequate.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        update = self.doc(encounter)['update']
        self.assertEqual((update['kind'], update['restorable'], update['changes']),
                         ('documentation', False, ['Documentation added (revision 2)']))
        # A21: an operator's reconciliation of a legacy encounter's own unknown document review - no save started it
        self.new_workspace()
        legacy = self.legacy_fixture()
        run = Run.objects.get(pk=legacy.current_assessment.provider_run_id)
        Run.objects.filter(pk=run.pk).update(state=Run.UNKNOWN, error='Read timed out after the request was sent.')
        jobs.reconcile(legacy, Run.objects.get(pk=run.pk), self.user, 'Synthetic: no answer arrived.')
        update = self.doc(legacy)['update']
        self.assertEqual((update['kind'], update['restorable'], update['saved_by'], update['saved_at']),
                         ('check', False, None, None))
        self.assertEqual(update['changes'], [customer_api.saved_changes_line('check', update['state'])])
        self.assertIsNotNone(update['started_at'])

    def test_u21_a_save_of_the_earlier_details_that_cannot_be_a_restore_shows_the_same_details_line(self):
        """A19 [R3:binding-R3B-2]: one details save answers a question "Not documented" and changes the date; the save of
        the earlier date back is no restore (that answer had no recompute of the earlier codes) but an update whose saved
        details are the earlier codes' own - the panel says why the codes are made again."""
        encounter = self.v2_fixture(UNDATED)
        date, asked = self.row_of(encounter, 'service_date'), self.row_of(encounter, 'event_time')
        response = self.details(encounter, (date['id'], 'service_date', D2), (asked['id'], 'event_time', 'not_documented'))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(review.restorable(self.fresh_row(encounter)))
        back = self.context(encounter, service_date='')
        self.assertEqual((back.status_code, back.json().get('restored')), (201, None))
        update = self.doc(encounter)['update']
        self.assertEqual(update['changes'], [customer_api.saved_changes_line('same_details', update['state'])])
        self.assertFalse(update['restorable'])

    def test_p9_a_removed_choice_reads_its_entered_value_removed_never_not_documented(self):
        """refute-5d-r1 P9: a save that removes the member's place of service (an empty value, as "Use what the document
        states" saves for a choice) lists "Place of service: entered value removed" - the update applies what the
        document states, which "not documented" would deny."""
        encounter = self.v2_fixture(UNDATED)
        self.assertEqual(self.context(encounter, setting=OFFICE).status_code, 201)
        self.drained(encounter)
        response = self.context(encounter, setting='')
        self.assertEqual((response.status_code, response.json()['updating']), (201, True))
        changes = self.doc(encounter)['update']['changes']
        self.assertEqual(changes, ['Place of service: entered value removed'])
        self.assertNotIn(customer_api.WHAT_CHANGED_NOT_DOCUMENTED, ' '.join(changes))

    def assertClean(self, doc):  # noqa: N802 - unittest's naming
        """The customer scan over every string of the payload but the document's own text: no provider or model name
        (customer_api.FORBIDDEN, the joined forms included) and no held-fact cause (FINAL-V2 4.12 [R:MO-2])."""
        own = doc['document']['text']

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
        for text in strings({key: value for key, value in doc.items() if key != 'document'}):
            if text and text in own:
                continue  # a quotation of the document is the member's own words
            self.assertIsNone(customer_api.FORBIDDEN.search(text), text)
            for cause in customer_api.HELD_FACT_CAUSES:
                self.assertNotIn(cause, text)

    def test_the_customer_scan_finds_no_provider_model_or_cause_on_any_update_string(self):
        encounter = self.legacy_fixture(POLYP)  # its question and its earlier answers' section
        self.assertClean(self.doc(encounter))
        self.save(encounter, setting=OFFICE)
        self.assertClean(self.doc(encounter))  # updating
        jobs.stop_encounter(self.fresh_row(encounter), self.user)
        self.assertClean(self.doc(encounter))  # stopped
        self.new_workspace()
        done = self.legacy_fixture()
        proposal = done.current_assessment.proposals.get(code='45378')
        review.record_decision(encounter=self.fresh_row(done), proposal=proposal, action=review.APPROVE, user=self.user,
                               membership=self.membership(), acknowledgement=review.ACKNOWLEDGEMENTS['human'])
        self.save(done, setting=HOSPITAL)
        self.drained(done)
        doc = self.doc(done)
        self.assertIsNotNone(doc['what_changed'])
        self.assertTrue(doc['decision_history'])  # the legacy approval, cleared by the new reading (D7)
        self.assertEqual(doc['decision_history'][0]['why'], customer_api.CLEARED_NEW_READING)
        self.assertIn(customer_api.WHAT_CHANGED_READ_AGAIN, doc['what_changed']['details'])
        self.assertClean(doc)  # fresh: what changed, the earlier decisions
        self.new_workspace()
        failing = self.v2_fixture(UNDATED)
        self.corti.outcomes = [corti_refusal(500)]
        self.save(failing, service_date=D2)
        self.drain()
        doc = self.doc(failing)
        self.assertEqual(doc['update']['state'], 'failed')
        self.assertClean(doc)

    def test_u15_a_legacy_encounters_earlier_codes_are_read_under_their_own_label(self):
        encounter = self.legacy_fixture(POLYP)
        earlier = encounter.current_assessment
        self.save(encounter, setting=OFFICE)
        real = jobs.owed_peer_stages

        def owes(assessment):
            return ('astra_peer',) if assessment.pk != earlier.pk else real(assessment)
        with mock.patch.object(jobs, 'owed_peer_stages', side_effect=owes), \
                mock.patch.object(jobs, '_queue_peers', return_value=None):
            self.drain()
            row = self.fresh_row(encounter)
            self.assertEqual(row.current_assessment_id, earlier.pk)  # the update's assess #1 recorded, never current
            with sentinel.call_checks(), sentinel.scope(sentinel.NEW_PATH, entry='U15: the label forced') as opened:
                doc = customer_api.encounter_json(row, self.membership())
        self.assertTrue(doc['earlier_codes'])
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0, '\n'.join(opened.describe(sentinel.NEW_PATH)))
        self.assertGreater(opened.count(sentinel.LEGACY_RECORD), 0)  # the legacy overlay's own read, under its label


class AnswerAfterUpdateTests(ApiCase):
    """U11's RT5 row [R2:truth-RT5], through the API: an answer given after the update to a question the updated codes
    ask, read while its recompute is queued and after a Stop of it, draws no answers line - it was not given before the
    change; the same answer dated before the update's context draws it (the control)."""

    def test_u11_an_answer_given_after_the_update_draws_no_answers_line_while_its_recompute_is_queued_or_stopped(self):
        encounter = self.v2_fixture(UNDATED)
        self.save(encounter, setting=OFFICE)
        row = self.drained(encounter)
        context = row.current_context
        changed = self.doc(encounter)['what_changed']
        self.assertIsNotNone(changed)
        self.assertIsNone(changed['answers'])
        asked = self.row_of(encounter, 'event_time')  # a question the updated codes ask
        response = self.details(encounter, (asked['id'], 'event_time', 'not_documented'))
        self.assertEqual((response.status_code, response.json()['reassessing']), (201, True))
        recompute = Job.objects.get(encounter=encounter, kind=Job.ASSESS, state=Job.QUEUED,
                                    idempotency_key__contains=jobs.AGAIN_MARK)
        [answer] = models.MemberAnswer.objects.filter(encounter=encounter, fact='event_time')
        self.assertGreater(answer.answered_at, context.created_at)
        changed = self.doc(encounter)['what_changed']
        self.assertIsNotNone(changed)
        self.assertIsNone(changed['answers'])  # its recompute queued
        jobs.stop_encounter(self.fresh_row(encounter), self.user)
        self.assertEqual(Job.objects.get(pk=recompute.pk).state, Job.CANCELLED)
        changed = self.doc(encounter)['what_changed']
        self.assertIsNotNone(changed)
        self.assertIsNone(changed['answers'])  # and after a Stop of it
        # the control: the same answer recorded before the update's context (the clock set back for its insert: answers
        # are immutable) is an answer from before the change that the updated codes' stored rows do not read
        with mock.patch.object(timezone, 'now', return_value=context.created_at - timedelta(seconds=1)):
            models.MemberAnswer.objects.create(encounter=answer.encounter, revision=answer.revision,
                                               assessment=answer.assessment, fact=answer.fact, family=answer.family,
                                               code=answer.code, value=answer.value, answered_by=self.user,
                                               question=answer.question)
        self.assertEqual(self.doc(encounter)['what_changed']['answers'], customer_api.WHAT_CHANGED_ANSWERS)


class SavedChangesWordingTests(SimpleTestCase):
    """refute-5d-r1 P9: update.changes (customer_api._change_lines) never words a removed choice as "not documented"."""

    def test_a_removed_choice_reads_entered_value_removed_and_a_removed_date_date_of_service_removed(self):
        before = {'service_date': D1, 'setting': OFFICE, 'patient_status': 'new', 'billing_context': 'facility'}
        for name, label in (('setting', 'Place of service'), ('patient_status', 'Patient'), ('billing_context', 'Claim')):
            with self.subTest(name=name):
                now = {key: value for key, value in before.items() if key != name}
                self.assertEqual(customer_api._change_lines(now, before), [f'{label}: entered value removed'])
        self.assertEqual(customer_api._change_lines({}, before), [
            'Date of service removed', 'Place of service: entered value removed', 'Patient: entered value removed',
            'Claim: entered value removed'])
        self.assertEqual(customer_api._change_lines({'setting': HOSPITAL}, {'setting': OFFICE}),
                         ['Place of service: Hospital outpatient department'])
        self.assertEqual(customer_api._change_lines({'setting': OFFICE}, {}), ['Place of service: Office'])


# --- U11: what changed, from stored rows -----------------------------------------------------------------------------------

class WhatChangedCase(TestCase):
    """Hand-made assessments (tests/support/pipeline_factories.py, the legacy engine's: decidable) persisted through
    review.persist_assessment, an update modelled as the pipeline makes one: a new context of the saved values recording
    the earlier codes (EncounterContext.earlier_assessment, 4.5), then the update's final on it."""

    def setUp(self):
        self.sc = pf.scenario()
        self.encounter = self.sc.encounter
        self.earlier = pf.assess(self.encounter, self.result())

    @staticmethod
    def result(*items, engine_version=pf.ENGINE_VERSION):
        items = items or (pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                          pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE]),
                          pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                                      exclusion_reason='The colonoscopy is planned, not performed on this date.'),
                          pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative'))
        return pf.result(*items, engine_version=engine_version)

    def update(self, result, user_values, *, revision=None):
        """A save of ``user_values`` and its update's final ``result``: the new context records the earlier codes."""
        encounter = models.Encounter.objects.get(pk=self.encounter.pk)
        revision = revision or encounter.current_revision
        earlier = encounter.current_assessment
        data = pf.facts(revision.text, **user_values)
        context = models.EncounterContext.objects.create(
            encounter=encounter, revision=revision, facts=data, user_values=dict(user_values),
            version=pf.CONTEXT_VERSION, earlier_assessment=earlier,
            sha256=pf.sha256_json({'facts': data, 'user_values': user_values, 'revision': str(revision.pk)}))
        encounter.current_context, encounter.user_values = context, dict(user_values)
        encounter.save(update_fields=['current_context', 'user_values', 'updated_at'])
        return pf.assess(encounter, result, rev=revision, ctx=context)

    def again(self, result):
        """A final on the current context with the same details (an answer's recompute, a re-check's follow-up)."""
        encounter = models.Encounter.objects.get(pk=self.encounter.pk)
        return pf.assess(encounter, result, ctx=encounter.current_context)

    def changed(self):
        return customer_api.what_changed(models.Encounter.objects.get(pk=self.encounter.pk))

    @contextmanager
    def unfinished_first(self):
        """Assessments recorded through first_of_chain owe a peer stage (jobs.owed_peer_stages, the rule review.is_final
        reads): an assess #1, never final - the participants' configuration that rule reads, stood in for here."""
        self.unfinished = set()
        with mock.patch.object(jobs, 'owed_peer_stages',
                               side_effect=lambda found: ('astra_peer',) if found.sha256 in self.unfinished else ()):
            yield

    def first_of_chain(self, result):
        """A participant reconciliation's re-run of the chain on the current context after a completed update (4.5
        [R2:binding-R2B-3]): its assess #1, recorded while the codes are fresh, becomes current as today and carries
        nothing; the approvals stay on the previous final."""
        self.unfinished.add(sha256_json(result))
        return self.again(result)

    def row(self):
        return models.Encounter.objects.select_related('current_assessment', 'current_context').get(pk=self.encounter.pk)

    def decide(self, key, action, assessment=None):
        return self.sc.decide(key, action, assessment=assessment)


class WhatChangedTests(WhatChangedCase):
    def test_u11_codes_added_removed_status_units_and_detail_exactly_and_byte_identically(self):
        earlier_items = (pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                         pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE]),
                         pf.proposal('sel:2', '45380', [pf.CECUM_PASSAGE], status='needs_clarification',
                                     clarifications=()),
                         pf.proposal('sel:3', '43235', [pf.EGD_PASSAGE]))
        self.earlier = self.again(pf.result(*earlier_items, clarifications=(
            pf.clarification('extent', proposal_key='sel:2'),)))
        now = self.update(pf.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification'),   # status
            pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE], units=2),                      # units
            pf.proposal('sel:2', '45380', [pf.CECUM_PASSAGE], status='needs_clarification'),  # detail
            pf.proposal('alt:0', '43235', [pf.EGD_PASSAGE], bucket='alternative'),           # removed: an alternative
            pf.proposal('sel:4', '45378', [pf.CECUM_PASSAGE]),                               # added
            clarifications=(pf.clarification('completion', proposal_key='sel:2'),
                            pf.clarification('target', proposal_key='sel:0'))), {'setting': 'office'})
        self.assertEqual(self.encounter.__class__.objects.get(pk=self.encounter.pk).current_assessment_id, now.pk)
        changed = self.changed()
        self.assertEqual(changed['compared_with'], {'made_at': self.earlier.created_at.isoformat(), 'revision': 1})
        self.assertEqual(changed['details'], ['Place of service: Hospital outpatient department → Office'])
        self.assertEqual(changed['codes'], [
            {'code': '43235', 'change': 'removed',
             'text': '43235 is no longer suggested. Listed as an alternative only; not suggested for approval.'},
            {'code': '43239', 'change': 'status', 'text': '43239: Ready for review → Needs a detail'},
            {'code': '45378', 'change': 'added', 'text': '45378 is now suggested (Ready for review)'},
            {'code': '45380', 'change': 'detail',
             'text': f'45380: the detail needed changed: "{answers.PROMPTS["extent"]}" → '
                     f'"{answers.PROMPTS["completion"]}"'},
            {'code': '45385', 'change': 'units', 'text': '45385: 1 → 2 units'}])
        self.assertEqual(changed['unchanged'], 0)
        self.assertEqual((changed['decisions'], changed['answers']), ([], None))
        self.assertEqual(json.dumps(changed, sort_keys=True), json.dumps(self.changed(), sort_keys=True))
        # never the clock, never the participants configured now
        with mock.patch.object(timezone, 'now', return_value=timezone.now() + timedelta(days=400)), \
                override_settings(ASTRA_MODE='replay', FABLE_MODE='replay'):
            self.assertEqual(self.changed(), changed)

    def test_u11_a_kept_and_a_cleared_approval_and_one_revoked_before_the_change(self):
        self.decide('sel:0', 'approve')
        self.decide('sel:1', 'approve')
        self.decide('exc:0', 'reinstate')
        self.decide('exc:0', 'revoke')  # revoked before the change: not current, not listed
        self.update(self.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
            pf.with_fingerprint(pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE]), 'f' * 64)), {'setting': 'office'})
        changed = self.changed()
        self.assertEqual(changed['decisions'], [
            {'code': '43239', 'action': 'Approval', 'outcome': 'kept', 'text': 'Approval of 43239 kept: the code is unchanged.'},
            {'code': '45385', 'action': 'Approval', 'outcome': 'cleared', 'text': customer_api.CLEARED_DETAILS_CHANGED}])
        self.assertEqual(changed['codes'], [{'code': '45378', 'change': 'removed', 'text': '45378 is no longer suggested'}])
        history = customer_api.decision_history(self.encounter)
        self.assertEqual([(item['code'], item['action'], item['why'], item['revision']) for item in history],
                         [('45385', 'Approval', customer_api.CLEARED_DETAILS_CHANGED, 1)])

    def test_u11_kept_by_the_update_then_cleared_by_a_final_with_the_same_details(self):
        self.decide('sel:0', 'approve')
        self.update(self.result(), {'setting': 'office'})
        self.again(self.result(pf.with_fingerprint(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]), 'e' * 64)))
        [entry] = self.changed()['decisions']
        self.assertEqual((entry['outcome'], entry['text']), ('kept_then_cleared', customer_api.WHAT_CHANGED_KEPT_THEN_CLEARED
                                                             .format(action='Approval', code='43239')))
        [cleared] = customer_api.decision_history(self.encounter)
        self.assertEqual(cleared['why'], customer_api.CLEARED_SAME_DETAILS)  # a final made with the same details

    def test_u11_kept_by_the_update_then_changed_by_a_reviewer(self):
        for second in (None, 'approve'):
            with self.subTest(then=second):
                self.setUp()
                self.decide('sel:0', 'approve')
                now = self.update(self.result(), {'setting': 'office'})
                self.decide('sel:0', 'revoke', assessment=now)
                if second:
                    self.decide('sel:0', second, assessment=now)
                [entry] = self.changed()['decisions']
                self.assertEqual((entry['outcome'], entry['text']), (
                    'kept_then_changed', customer_api.WHAT_CHANGED_KEPT_THEN_CHANGED.format(action='Approval',
                                                                                            code='43239')))

    def test_u11_an_addendum_and_two_addenda_before_the_update_finished(self):
        self.decide('sel:0', 'approve')
        for count in (1, 2):
            with self.subTest(addenda=count):
                if count == 2:
                    self.setUp()
                    self.decide('sel:0', 'approve')
                revision = None
                for number in range(count):
                    revision = pf.addendum(self.encounter, self.sc.reviewer, f'Synthetic addendum {number + 1}.')
                    review.invalidate_for_new_revision(models.Encounter.objects.get(pk=self.encounter.pk), revision)
                self.update(self.result(), {}, revision=revision)
                changed = self.changed()
                self.assertIn(f'Documentation added (revision {revision.number})', changed['details'])
                self.assertEqual(changed['decisions'], [{'code': '43239', 'action': 'Approval', 'outcome': 'cleared',
                                                         'text': 'Cleared when documentation was added (revision 2).'}])

    def test_u11_a_save_during_a_chain_re_run_after_a_completed_update_lists_the_previous_finals_decisions(self):
        """U11 [R2:binding-R2B-3] and U22's payload half: after a completed update, a participant reconciliation re-runs
        the chain - processing, never an update (no update block, no earlier codes); a save during it records the chain's
        assess #1 as its earlier codes, and "what changed" compares with that assess #1 and lists the decisions the
        update acted on: the previous final's approvals, kept or cleared. Recomputed without the stand-in (the rule now
        calls that assess #1 final) nothing changes: the rule never asks which assessment is final."""
        with self.unfinished_first():
            final = self.update(self.result(), {'setting': 'office'})  # a completed update: the previous final
            self.decide('sel:0', 'approve', assessment=final)
            self.decide('sel:1', 'approve', assessment=final)
            first = self.first_of_chain(self.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                                                    pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE])))
            row = self.row()
            self.assertEqual(row.current_assessment_id, first.pk)
            self.assertFalse(review.update_pending(row))  # the chain re-run is processing, as today
            doc = customer_api.encounter_json(row, self.sc.membership(self.sc.reviewer))
            self.assertEqual((doc['update'], doc['earlier_codes'], doc['what_changed']), (None, [], None))
            now = self.update(self.result(
                pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                pf.with_fingerprint(pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE]), 'f' * 64)), {'setting': 'asc'})
            self.assertEqual(now.context.earlier_assessment_id, first.pk)
            self.assertEqual(self.row().current_assessment_id, now.pk)
            changed = self.changed()
        self.assertEqual(changed['compared_with'], {'made_at': first.created_at.isoformat(), 'revision': 1})
        self.assertEqual(changed['details'], ['Place of service: Office → Ambulatory surgery center'])
        self.assertEqual(changed['decisions'], [
            {'code': '43239', 'action': 'Approval', 'outcome': 'kept', 'text': 'Approval of 43239 kept: the code is unchanged.'},
            {'code': '45385', 'action': 'Approval', 'outcome': 'cleared', 'text': customer_api.CLEARED_DETAILS_CHANGED}])
        self.assertEqual(json.dumps(self.changed(), sort_keys=True), json.dumps(changed, sort_keys=True))

    def test_u22_the_chain_re_runs_final_compares_with_the_updates_earlier_codes_as_before(self):
        """U22: after the re-run chain's own final (the same context and details), "what changed" still compares with the
        codes from before the completed update; the approval made on the previous final - after the update, on the
        update's own context - is not one the update acted on, so it is not listed (6.2 step 4)."""
        earlier = self.earlier
        with self.unfinished_first():
            final = self.update(self.result(), {'setting': 'office'})
            self.decide('sel:0', 'approve', assessment=final)
            self.first_of_chain(self.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE])))
            chain = self.again(self.result())  # the re-run chain's final, on the same context
            self.assertEqual(self.row().current_assessment_id, chain.pk)
            changed = self.changed()
        self.assertEqual(changed['compared_with'], {'made_at': earlier.created_at.isoformat(), 'revision': 1})
        self.assertEqual(changed['details'], ['Place of service: Hospital outpatient department → Office'])
        self.assertEqual(changed['decisions'], [])
        self.assertEqual(self.changed(), changed)

    def test_u11_an_addendum_during_a_chain_re_run_compares_with_its_assess_1_and_lists_the_approval_cleared(self):
        """U11 [R3:truth-R3T-5] and U22's payload half: an addendum recorded while a re-run chain's assess #1 is current
        is an update (kind documentation) whose earlier codes are that assess #1, with no restore; on completion "what
        changed" compares with it and lists the previous final's approval as cleared by the documentation."""
        with self.unfinished_first():
            final = self.update(self.result(), {'setting': 'office'})
            self.decide('sel:0', 'approve', assessment=final)
            first = self.first_of_chain(self.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE])))
            revision = pf.addendum(self.encounter, self.sc.reviewer, 'Synthetic addendum recorded during the re-run.')
            self.assertEqual(review.invalidate_for_new_revision(self.row(), revision), 1)  # the previous final's approval
            row = self.row()
            self.assertEqual((review.earlier(row).pk, review.update_kind(row)), (first.pk, review.UPDATE_DOCUMENTATION))
            block = customer_api.update_block(row)
            self.assertEqual((block['kind'], block['restorable'], block['changes'], block['earlier']['made_at'],
                              block['earlier']['revision']),
                             ('documentation', False, ['Documentation added (revision 2)'], first.created_at.isoformat(), 1))
            self.update(self.result(), {'setting': 'office'}, revision=revision)
            changed = self.changed()
        self.assertEqual(changed['compared_with'], {'made_at': first.created_at.isoformat(), 'revision': 1})
        self.assertIn('Documentation added (revision 2)', changed['details'])
        self.assertEqual(changed['decisions'], [{'code': '43239', 'action': 'Approval', 'outcome': 'cleared',
                                                 'text': 'Cleared when documentation was added (revision 2).'}])
        self.assertEqual(self.changed(), changed)

    def test_u11_a_legacy_answer_given_without_a_recompute_and_asked_again_by_the_update_draws_the_answers_line(self):
        """U11: a legacy E (its engine recomputes nothing: recompute_after_answers returns None) whose detail the member
        answered "Not documented" - applied by the review overlay alone, E's stored rows unchanged - then asked again by
        N: the code reads "Needs a detail" on both stored rows, counted unchanged, and the answers line explains it."""
        items = (pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                 pf.proposal('sel:2', '45380', [pf.CECUM_PASSAGE], status='needs_clarification', clarifications=()))
        asked = (pf.clarification('extent', proposal_key='sel:2'),)
        earlier = self.again(pf.result(*items, clarifications=asked))
        self.assertFalse(interpretation.is_new_assessment(earlier))
        proposal = earlier.proposals.get(key='sel:2')
        models.MemberAnswer.objects.create(encounter=self.encounter, revision=self.encounter.current_revision,
                                           assessment=earlier, fact='extent', family=proposal.family, code='45380',
                                           value='not_documented', answered_by=self.sc.reviewer)
        now = self.update(pf.result(*items, clarifications=asked), {'setting': 'office'})  # N asks it again
        self.assertTrue(now.clarifications.filter(fact='extent', answer__isnull=True).exists())
        changed = self.changed()
        self.assertEqual(changed['answers'], customer_api.WHAT_CHANGED_ANSWERS)
        self.assertEqual((changed['codes'], changed['unchanged']), ([], 2))
        self.assertEqual(json.dumps(changed, sort_keys=True), json.dumps(self.changed(), sort_keys=True))

    def test_u11_the_answers_line_for_an_answer_the_updated_codes_do_not_read_and_none_for_one_after_it(self):
        revision = self.encounter.current_revision
        before = models.MemberAnswer.objects.create(encounter=self.encounter, revision=revision,
                                                    assessment=self.earlier, fact='units', family='gi.colonoscopy',
                                                    code='45385', value='not_documented',
                                                    answered_by=self.sc.reviewer)
        self.update(self.result(), {'setting': 'office'})
        self.assertEqual(self.changed()['answers'], customer_api.WHAT_CHANGED_ANSWERS)
        models.MemberAnswerRevocation.objects.create(answer=before, revoked_by=self.sc.reviewer,
                                                     reason=models.MemberAnswerRevocation.WITHDRAWN)
        models.MemberAnswer.objects.create(encounter=self.encounter, revision=revision,
                                           assessment=self.encounter.__class__.objects.get(
                                               pk=self.encounter.pk).current_assessment,
                                           fact='units', family='gi.colonoscopy', code='45385', value='not_documented',
                                           answered_by=self.sc.reviewer)  # given after the update
        self.assertIsNone(self.changed()['answers'])

    def test_u11_null_unless_fresh_with_an_earlier_assessment(self):
        self.assertIsNone(self.changed())  # no earlier assessment recorded: a first processing's codes
        self.update(self.result(), {'setting': 'office'})
        self.assertIsNotNone(self.changed())
        encounter = models.Encounter.objects.get(pk=self.encounter.pk)
        encounter.user_values = {'setting': 'asc'}  # a case-B save: not fresh
        encounter.save(update_fields=['user_values'])
        self.assertIsNone(self.changed())


class ClearedWhyTests(TestCase):
    """5.4's first-match rules, from the rows (stand-ins: nothing here is persisted)."""

    def test_each_rule(self):
        legacy = models.Assessment(engine_version=pf.ENGINE_VERSION)
        events = models.Assessment(engine_version=interpretation.ENGINE_VERSION_V2)
        own = models.EncounterContext(user_values={'setting': 'office'}, version=pf.CONTEXT_VERSION)
        gemini = models.EncounterContext(user_values={'setting': 'office'}, version=interpretation.CONTEXT_VERSION_V2)
        same = models.EncounterContext(user_values={'setting': 'office'}, version=pf.CONTEXT_VERSION)
        other = models.EncounterContext(user_values={'setting': 'asc'}, version=pf.CONTEXT_VERSION)
        legacy.context = own
        events.context = own

        def why(assessment, **invalidation):
            decision = Decision(assessment=assessment)
            return customer_api.cleared_why(decision, DecisionInvalidation(**invalidation))
        self.assertEqual(why(legacy, by_revision=models.SourceRevision(number=3)), 'Cleared when documentation was added '
                                                                                   '(revision 3).')
        self.assertEqual(why(legacy, by_context=gemini), customer_api.CLEARED_NEW_READING)
        self.assertEqual(why(events, by_context=own), customer_api.CLEARED_SAME_DETAILS)
        self.assertEqual(why(events, by_context=same), customer_api.CLEARED_SAME_DETAILS)  # same values, same reading
        self.assertEqual(why(events, by_context=other), customer_api.CLEARED_DETAILS_CHANGED)
        # the same values over another reading - an update no save started (A21) on a v2 revision whose inventory is of
        # an older version: the document was read again (step 3c's CLEARED_READ_AGAIN, its Q7 option (a))
        import uuid
        events.context = models.EncounterContext(user_values={'setting': 'office'}, version=interpretation.CONTEXT_VERSION_V2,
                                                 event_inventory_id=uuid.uuid4())
        newer = models.EncounterContext(user_values={'setting': 'office'}, version=interpretation.CONTEXT_VERSION_V2,
                                        event_inventory_id=uuid.uuid4())
        self.assertEqual(why(events, by_context=newer), customer_api.CLEARED_READ_AGAIN)
