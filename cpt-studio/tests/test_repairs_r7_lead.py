"""Round 7 findings the lead owns (the final round): report truth, one API status and two missing pins.

bypass:0 — a decision invalidated after a context change was reported as "the evidence or checks for X changed" when
  neither had; the reason now names the part of the fingerprint that differs, or the context value the fingerprint
  binds and a row does not keep.
bypass:1 — a provider response refused whole (over a count cap) was reported as "returned no selected CPT-labelled
  code", and the readiness blocker said "No CPT code was proposed": the provider's codes were never read.
bypass:3 — an unknown or non-string review action answered 409, a state conflict; it is invalid input (400).
bypass:4 — a draft generated after a complete review titled its provisional approvals "UNDECIDED — REVIEW NOT
  COMPLETE".
pipeline:1 — no test dated an undated note, so a guard that let a routing for no date count for any date stayed green.
pipeline:2 — no cap test nested alternatives under candidates, so a count that skipped them stayed green.
Synthetic data only; no network.
"""
import importlib.util
import json
import sys
import time
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from studio import models, reports, review
from studio.gi import detect
from studio.providers import CortiProvider
from studio.providers import corti as corti_module
from studio.types import Fact
from studio.validation import checks
from tests.support import pipeline_factories as pf
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.test_repairs_r4d_lead import DEADLINES, LIVE, NEW_DATE, LiveEncounter, NOTE, SNARE

_ROUTE = detect.route
UNDATED_NOTE = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', '')
E_M_QUOTE = 'Total time on the date of the encounter was 24 minutes.'


def _verify_downloads():
    """ops/verify_downloads.py, the download verifier the install's walk runs (not a package; loaded by path)."""
    if 'r7_verify_downloads' in sys.modules:
        return sys.modules['r7_verify_downloads']
    path = Path(__file__).resolve().parents[1] / 'ops' / 'verify_downloads.py'
    spec = importlib.util.spec_from_file_location('r7_verify_downloads', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['r7_verify_downloads'] = module  # dataclasses resolve their module while the class is built
    spec.loader.exec_module(module)
    return module


# --- bypass:0: the invalidation reason names what differs ---------------------------------------------------------

class InvalidationReasonTests(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        pf.assess(self.s.encounter, pf.standard_result())
        self.approved = self.s.decide('sel:0', 'approve', note='EGD biopsy documented.')

    def reassess(self, first, *, engine_version=pf.ENGINE_VERSION, **user_values):
        """A member's context change, then a re-assessment whose first proposal is ``first``."""
        overrides = {name: Fact(name=name, value=value, origin='user') for name, value in user_values.items()}
        ctx = pf.context(self.s.encounter, self.s.revision, fact_values=pf.facts(**overrides), user_values=user_values)
        items = pf.standard_result().proposals
        pf.assess(self.s.encounter, pf.result(first, *items[1:], engine_version=engine_version), ctx=ctx)
        return models.DecisionInvalidation.objects.get(decision=self.approved).reason

    def egd(self):
        return pf.standard_result().proposals[0]

    def test_only_the_context_the_fingerprint_binds_changed(self):
        reason = self.reassess(pf.with_fingerprint(self.egd(), 'f' * 64), billing_context='facility')
        self.assertIn('billing context', reason)
        self.assertTrue(reason.endswith(': the decision on 43239 depends on a context value that changed.'), reason)
        self.assertNotIn('evidence', reason)
        self.assertNotIn('checks', reason)

    def test_a_check_whose_result_changed_is_named(self):
        changed = tuple(replace(c, status='warn') if c.id == 'pfs.presence' else c for c in self.egd().checks)
        reason = self.reassess(replace(self.egd(), checks=changed, fingerprint='e' * 64), billing_context='facility')
        self.assertTrue(reason.endswith(': the checks for 43239 changed.'), reason)

    def test_a_check_whose_wording_alone_changed_is_not_named(self):
        # the fingerprint reads a check's id and status, never its wording
        changed = tuple(replace(c, detail='Reworded.') for c in self.egd().checks)
        reason = self.reassess(replace(self.egd(), checks=changed, fingerprint='d' * 64), billing_context='facility')
        self.assertTrue(reason.endswith(': the decision on 43239 depends on a context value that changed.'), reason)

    def test_evidence_whose_passage_changed_is_named(self):
        spans = (pf.evidence(pf.GI_NOTE, pf.DATE_PASSAGE),)
        reason = self.reassess(replace(self.egd(), evidence=spans, fingerprint='c' * 64), billing_context='facility')
        self.assertTrue(reason.endswith(': the evidence for 43239 changed.'), reason)

    def test_units_that_changed_are_named_with_both_values(self):
        reason = self.reassess(replace(self.egd(), units=2, fingerprint='b' * 64), billing_context='facility')
        self.assertTrue(reason.endswith(': the units of 43239 changed from 1 to 2.'), reason)

    def test_another_engine_never_blames_the_context(self):
        reason = self.reassess(pf.with_fingerprint(self.egd(), 'a' * 64), engine_version='test-engine@2',
                               billing_context='facility')
        self.assertIn('engine test-engine@1 → test-engine@2', reason)
        self.assertTrue(reason.endswith(': 43239 was re-assessed by another engine version.'), reason)

    def test_the_audit_section_of_the_report_says_what_the_record_says(self):
        self.reassess(pf.with_fingerprint(self.egd(), 'f' * 64), billing_context='facility')
        text = reports.render_txt(reports.snapshot(self.s.encounter, 'draft')).decode('utf-8')
        self.assertIn('the decision on 43239 depends on a context value that changed', text)
        self.assertNotIn('the evidence or checks for 43239 changed', text)


@override_settings(**LIVE)
class RealEngineDateChangeReasonTests(LiveEncounter, TestCase):
    def test_an_approved_em_invalidated_by_a_new_date_is_never_blamed_on_its_evidence_or_checks(self):
        # a note with no date of its own, dated by the member and then re-dated: a member's date beside a documented
        # one would be a conflict instead (session interpretation 11)
        encounter_id = self.finished_encounter(UNDATED_NOTE, service_date='2026-10-20')
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        em = next(p for p in detail['assessment']['proposals'] if p['code'] == '99213')
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': em['id'], 'action': 'approve',
                              'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
        self.assertEqual(response.status_code, 201, response.content)
        before = models.Proposal.objects.get(pk=em['id'])
        self.change_date(encounter_id)
        drain()
        invalidation = models.DecisionInvalidation.objects.get(decision__proposal_id=em['id'])
        after = models.Encounter.objects.get(pk=encounter_id).current_assessment.proposals.get(code='99213')
        self.assertNotEqual(before.fingerprint, after.fingerprint, 'the date did not change the fingerprint')
        # what the engine's fingerprint reads beside the context: equal here, so only the date may be named
        self.assertEqual(review._evidence_texts(before), review._evidence_texts(after))
        self.assertEqual(review._check_results(before), review._check_results(after))
        self.assertIn('service date: 2026-10-20 [member-supplied] → 2026-10-22 [member-supplied]', invalidation.reason)
        self.assertTrue(invalidation.reason.endswith(
            ': the decision on 99213 depends on a context value that changed.'), invalidation.reason)


# --- bypass:1: a refused response is never "no code proposed" ----------------------------------------------------

class RefusedResponseCheckTests(SimpleTestCase):
    def setUp(self):
        self.request = CortiProvider(Path('/nonexistent/never-read.env')).build_request(NOTE, date(2026, 10, 21))

    def response(self, selected):
        start = NOTE.index(SNARE)
        code = {'system': 'cpt', 'code': '45385', 'display': 'x',
                'evidences': [{'contextIndex': 0, 'text': SNARE, 'start': start, 'end': start + len(SNARE)}]}
        return json.dumps({'codes': [code] * selected, 'candidates': []}).encode()

    def test_a_response_over_the_selection_cap_is_reported_as_not_used(self):
        normalized = corti_module.normalize_coding_response('corti', self.request, self.response(65))
        self.assertTrue(normalized.refused)
        status, problems = checks.provider_checks('succeeded', normalized)
        self.assertEqual((status.id, status.status), ('provider.status', 'fail'))
        self.assertIn('was not used, so there are no CPT proposals', status.detail)
        self.assertIn(checks.NO_PROPOSALS, status.detail)
        self.assertNotIn('returned no selected', status.detail)
        self.assertIn('it selects 65 codes, more than the 64 this adapter accepts', problems.detail)

    def test_controls_a_response_at_the_cap_and_an_empty_one_are_read(self):
        at_cap = corti_module.normalize_coding_response('corti', self.request, self.response(64))
        self.assertFalse(at_cap.refused)
        self.assertEqual(checks.provider_checks('succeeded', at_cap)[0].status, 'pass')
        empty = corti_module.normalize_coding_response('corti', self.request, self.response(0))
        self.assertFalse(empty.refused)
        status = checks.provider_checks('succeeded', empty)
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0].status, 'warn')
        self.assertIn('returned no selected CPT-labelled code', status[0].detail)


@override_settings(**LIVE)
class RefusedResponseReadinessTests(LiveEncounter, TestCase):
    def encounter_with(self, selections):
        self.provider.selections = selections
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def test_a_refused_response_is_named_in_the_checks_the_blockers_and_the_draft(self):
        encounter_id = self.encounter_with([('99213', E_M_QUOTE)] * 65)
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        status = next(c for c in detail['assessment']['encounter_checks'] if c['id'] == 'provider.status')
        self.assertEqual(status['status'], 'fail')
        self.assertIn('was not used', status['detail'])
        self.assertEqual(detail['assessment']['proposals'], [])
        self.assertIn('The provider response was not used', detail['readiness']['blockers'])
        self.assertNotIn('No CPT code was proposed', detail['readiness']['blockers'])
        draft = reports.render_txt(reports.snapshot(models.Encounter.objects.get(pk=encounter_id), 'draft'))
        draft = draft.decode('utf-8')
        self.assertIn('  - The provider response was not used', draft)
        self.assertIn('it selects 65 codes, more than the 64 this adapter accepts', draft)
        self.assertNotIn('No CPT code was proposed', draft)
        self.assertNotIn('returned no selected CPT-labelled code', draft)
        usage = draft[draft.index('\nPROVIDER USAGE\n'):draft.index('\nREFERENCE SOURCES\n')]
        self.assertIn('read by this assessment; its response was not used', usage)
        self.assertNotIn('used by this assessment', usage.replace('its response was not used', ''))

    def test_controls_a_response_with_no_code_still_says_none_was_proposed(self):
        encounter_id = self.encounter_with([])
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        status = next(c for c in detail['assessment']['encounter_checks'] if c['id'] == 'provider.status')
        self.assertEqual(status['status'], 'warn')
        self.assertIn('No CPT code was proposed', detail['readiness']['blockers'])
        self.assertNotIn('The provider response was not used', detail['readiness']['blockers'])
        draft = reports.render_txt(reports.snapshot(models.Encounter.objects.get(pk=encounter_id), 'draft'))
        self.assertIn(' · used by this assessment', draft.decode('utf-8'))
        self.assertNotIn('its response was not used', draft.decode('utf-8'))


# --- bypass:3: an unknown action is invalid input ----------------------------------------------------------------

@override_settings(**LIVE)
class UnknownActionTests(LiveEncounter, TestCase):
    def test_an_unknown_missing_or_non_string_action_answers_400_and_records_nothing(self):
        encounter_id = self.finished_encounter()
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        proposal_id = detail['assessment']['proposals'][0]['id']
        url = f'/api/encounters/{encounter_id}/decisions'
        for action in ('approved', 'APPROVE', '', ' approve', 7, None, ['approve'], {'action': 'approve'}, True):
            body = {'proposal_id': proposal_id, 'acknowledgement': review.ACKNOWLEDGEMENTS['human']}
            if action is not None:
                body['action'] = action
            with self.subTest(action=action):
                response = self.post(url, body)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json()['error'], 'Unknown review action.')
        self.assertFalse(models.Decision.objects.filter(encounter_id=encounter_id).exists())

    def test_controls_a_known_action_unavailable_now_is_still_a_409(self):
        encounter_id = self.finished_encounter()
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': detail['assessment']['proposals'][0]['id'], 'action': 'revoke'})
        self.assertEqual(response.status_code, 409, response.content)


# --- bypass:4: the draft's list title after a complete review ----------------------------------------------------

class DraftListTitleTests(TestCase):
    INCOMPLETE = 'UNDECIDED — REVIEW NOT COMPLETE'
    COMPLETE = 'UNDECIDED OR PROVISIONAL — THE REVIEWED REPORT IS AVAILABLE'

    def setUp(self):
        self.s = pf.scenario()
        pf.assess(self.s.encounter, pf.standard_result())

    def draft(self):
        return reports.render_txt(reports.snapshot(self.s.encounter, 'draft')).decode('utf-8')

    def test_a_draft_after_a_complete_review_never_says_the_review_is_not_complete(self):
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:1', 'reject', note='Not supported as documented.')
        self.s.decide('exc:0', 'confirm', note='Planned; not performed on this date.')
        self.assertTrue(review.readiness(self.s.encounter)['reviewed'])
        draft = self.draft()
        self.assertNotIn('REVIEW NOT COMPLETE', draft)
        self.assertIn('Review status: complete — a reviewed report is available; this file is a draft.', draft)
        lines = draft.split('\n')
        body = '\n'.join(lines[lines.index(self.COMPLETE) + 1:lines.index('', lines.index(self.COMPLETE))])
        self.assertIn('1. 43239 · Upper GI endoscopy', body)
        self.assertIn('provisional; this draft is not a reviewed report', body)
        # the download verifier still finds the list by its prefix, and only one
        vd = _verify_downloads()
        headings = [heading for heading, _ in vd.txt_sections(draft, set())
                    if heading.startswith(vd.TXT_LIST_SECTIONS['undecided'])]
        self.assertEqual(headings, [self.COMPLETE])

    def test_controls_a_draft_of_an_incomplete_review_keeps_its_title(self):
        self.s.decide('sel:0', 'approve')
        self.assertFalse(review.readiness(self.s.encounter)['reviewed'])
        draft = self.draft()
        self.assertIn(self.INCOMPLETE, draft.split('\n'))
        self.assertNotIn(self.COMPLETE, draft)


# --- pipeline:1: an undated note that a member dates is routed for that date before anything is sent -------------

@override_settings(**LIVE)
class UndatedNoteDatedLaterTests(LiveEncounter, TestCase):
    def undated_encounter(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': UNDATED_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        encounter_id = response.json()['id']
        self.assertEqual(len(self.provider.sent), 1)
        # the premise: the note was routed for no date, and only for no date
        self.assertEqual(set(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id)
                             .values_list('service_date', flat=True)), {None})
        return encounter_id

    def test_a_date_the_note_cannot_be_routed_for_in_time_sends_nothing(self):
        encounter_id = self.undated_encounter()
        runs_before = models.ProviderRun.objects.filter(encounter_id=encounter_id).count()

        def slow_for_the_new_date(text, service_date=None):
            if service_date == NEW_DATE:
                time.sleep(30)
            return _ROUTE(text, service_date)

        with override_settings(JOB_DEADLINE_SECONDS=dict(DEADLINES, analyze=1)), \
                mock.patch.object(detect, 'route', slow_for_the_new_date):
            self.change_date(encounter_id)
            drain()
        predict = models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.PREDICT).order_by('-created_at')[0]
        self.assertEqual(predict.state, models.Job.FAILED)
        self.assertIn('took longer than 1 seconds and was stopped', predict.error)
        self.assertEqual(len(self.provider.sent), 1, 'a request was sent for a date the note was never routed for')
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id).count(), runs_before)

    def test_controls_a_date_that_routes_in_time_is_routed_once_then_sent(self):
        encounter_id = self.undated_encounter()
        self.change_date(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual(set(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id)
                             .values_list('service_date', flat=True)), {None, NEW_DATE})


# --- pipeline:2: alternatives nested under candidates count toward the cap ----------------------------------------

class NestedAlternativeCapTests(SimpleTestCase):
    def setUp(self):
        self.request = CortiProvider(Path('/nonexistent/never-read.env')).build_request(NOTE, date(2026, 10, 21))

    def normalized(self, candidates, alternatives_each):
        start = NOTE.index(SNARE)
        selected = {'system': 'cpt', 'code': '45385', 'display': 'x',
                    'evidences': [{'contextIndex': 0, 'text': SNARE, 'start': start, 'end': start + len(SNARE)}]}
        listed = [{'system': 'cpt', 'code': '45378', 'alternatives': [{'code': '45380'}] * alternatives_each}
                  for _ in range(candidates)]
        data = json.dumps({'codes': [selected], 'candidates': listed}).encode()
        return corti_module.normalize_coding_response('corti', self.request, data)

    def test_alternatives_under_candidates_are_counted(self):
        cap = corti_module.MAX_INFORMATIONAL
        for candidates, each, total in ((cap, 1, 2 * cap), (1, 300, 301), (cap // 2 + 1, 1, cap + 2)):
            with self.subTest(candidates=candidates, each=each):
                normalized = self.normalized(candidates, each)
                self.assertTrue(normalized.refused)
                self.assertEqual(normalized.codes, ())
                self.assertEqual(normalized.problems, (
                    f'The provider response was not used: it lists {total} candidate and alternative codes, more '
                    f'than the {cap} this adapter accepts.',))

    def test_controls_nested_alternatives_at_the_cap_are_read(self):
        cap = corti_module.MAX_INFORMATIONAL
        normalized = self.normalized(cap // 2, 1)
        self.assertFalse(normalized.refused)
        self.assertEqual(normalized.problems, ())
        self.assertEqual(len(normalized.codes), 1 + cap)
        self.assertEqual(sum(1 for code in normalized.codes if code.role == 'alternative'), cap // 2)
