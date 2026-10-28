"""Round 6 findings the lead owns (repair round 4d): cost and the provider-send guard.

bounded:1 — every cited span's family lookup scanned every routed service, so a long report cited span by span was
  quadratic (a 400,000-character status-row report overran the assess stage).
Synthetic data only; no network.
"""
import os
import time
from datetime import date

from django.test import SimpleTestCase

from studio.gi import detect

DAY = date(2026, 10, 21)
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n\n'


def scan_family(an, start, end):
    """The pre-round-4d lookup, kept here as the oracle: a scan of every routed service."""
    named = {m.family for m in an.services if detect._overlaps(m.start, m.end, start, max(end, start + 1))}
    if named:
        return named.pop() if len(named) == 1 else None
    index = detect._sentence_index(an, start)
    return an.attributed[index] if index >= 0 and an.attributed else None


class FamilyOfSpanIsPositionalTests(SimpleTestCase):
    TEXTS = (
        HEAD + 'Procedure: Colonoscopy and EGD\nFindings: The colonoscope was advanced to the cecum. EGD was normal.\n'
               'Flexible sigmoidoscopy was planned. Esophagogastroduodenoscopy with biopsy.\n',
        HEAD + 'Procedure: EUS with fine-needle aspiration, then ERCP with sphincterotomy.\nColonoscopy declined.\n',
        HEAD + ''.join(f'Line {n}: colonoscopy, EGD, EUS and ERCP were reviewed.\n' for n in range(40)),
    )

    def test_it_answers_exactly_as_a_scan_of_every_service(self):
        for text in self.TEXTS:
            detect._analysis.cache_clear()
            an = detect._analysis(text, DAY)[0]
            detect._route(an)  # sets an.attributed, as a span read after routing sees it
            bounds = sorted({m.start for m in an.services} | {m.end for m in an.services}
                            | {s for s, _ in an.lay.sentences} | {e for _, e in an.lay.sentences} | {0, len(text)})
            spans = [(s, e) for s in bounds for e in bounds if s < e]
            # also spans cutting through every service name, and one-character spans
            spans += [(m.start + 1, m.end - 1) for m in an.services if m.end - m.start > 2]
            spans += [(p, p + 1) for p in range(0, len(text) - 1, 7)]
            for start, end in spans:
                with self.subTest(text=text[len(HEAD):][:30], span=(start, end)):
                    self.assertEqual(detect._family_of_span(an, start, end), scan_family(an, start, end))

    def test_a_long_report_read_span_by_span_stays_linear(self):
        # 5,000 performed lines: every mention span read once, as validation reads a provider citing each of them.
        text = HEAD + 'Procedure: Colonoscopy\nFindings:\n' + 'Colonoscopy was performed.\n' * 5000
        detect._analysis.cache_clear()
        an = detect._analysis(text, DAY)[0]
        detect._route(an)
        started = time.perf_counter()
        for m in an.services:
            detect._family_of_span(an, m.start, m.end)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0, f'{len(an.services)} span lookups took {elapsed:.2f} s')


# --- bounded:5: candidates and alternatives are capped, and proposals are written in one INSERT ----------------------

import json  # noqa: E402
from pathlib import Path  # noqa: E402

from django.db import connection  # noqa: E402
from django.test import TestCase  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from studio import models  # noqa: E402
from studio.providers import CortiProvider  # noqa: E402
from studio.providers import corti as corti_module  # noqa: E402
from tests.support import pipeline_factories as pf  # noqa: E402

NOTE = HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold snare.\n'
SNARE = 'A 6 mm polyp was removed with a cold snare.'


def corti_response(candidates=0, alternatives=0):
    start = NOTE.index(SNARE)
    selected = {'system': 'cpt', 'code': '45385', 'display': 'x',
                'evidences': [{'contextIndex': 0, 'text': SNARE, 'start': start, 'end': start + len(SNARE)}],
                'alternatives': [{'code': '45380'} for _ in range(alternatives)]}
    return json.dumps({'codes': [selected],
                       'candidates': [{'system': 'cpt', 'code': '45378'} for _ in range(candidates)]}).encode()


class CandidateCapTests(SimpleTestCase):
    def setUp(self):
        self.request = CortiProvider(Path('/nonexistent/never-read.env')).build_request(NOTE, DAY)

    def normalized(self, **counts):
        return corti_module.normalize_coding_response('corti', self.request, corti_response(**counts))

    def test_more_candidates_and_alternatives_than_the_cap_refuse_the_response_by_count(self):
        cap = corti_module.MAX_INFORMATIONAL
        for counts in ({'candidates': cap + 1}, {'alternatives': cap + 1},
                       {'candidates': cap // 2 + 1, 'alternatives': cap // 2}, {'candidates': 70_000}):
            with self.subTest(counts=counts):
                normalized = self.normalized(**counts)
                self.assertEqual(normalized.codes, ())
                total = counts.get('candidates', 0) + counts.get('alternatives', 0)
                self.assertEqual(normalized.problems, (
                    f'The provider response was not used: it lists {total} candidate and alternative codes, more than '
                    f'the {cap} this adapter accepts.',))

    def test_controls_a_response_at_the_cap_and_the_retained_sizes_are_read(self):
        for counts in ({'candidates': corti_module.MAX_INFORMATIONAL},
                       {'candidates': 11, 'alternatives': 5}):
            with self.subTest(counts=counts):
                normalized = self.normalized(**counts)
                self.assertEqual(normalized.problems, ())
                self.assertEqual(len(normalized.codes), 1 + sum(counts.values()))


class BulkProposalTests(TestCase):
    def test_every_proposal_is_written_in_one_insert(self):
        s = pf.scenario()
        alternatives = tuple(pf.proposal(f'alt:{n + 1}', '45380', [pf.CECUM_PASSAGE], bucket='alternative')
                             for n in range(200))
        base = pf.standard_result()
        result = pf.result(*(base.proposals + alternatives))
        with CaptureQueriesContext(connection) as captured:
            assessment = pf.assess(s.encounter, result)
        inserts = [q['sql'] for q in captured.captured_queries
                   if q['sql'].startswith('INSERT INTO "studio_proposal"')]
        self.assertEqual(len(inserts), 1)
        stored = list(models.Proposal.objects.filter(assessment=assessment).order_by('position'))
        self.assertEqual([p.key for p in stored], [item.key for item in result.proposals])
        self.assertEqual([p.position for p in stored], list(range(len(result.proposals))))


# --- pipeline:0: nothing is sent for a service date the revision was never routed for --------------------------------

from unittest import mock  # noqa: E402

from django.test import override_settings  # noqa: E402

from studio import jobs  # noqa: E402
from tests.support import factories as f  # noqa: E402
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain  # noqa: E402

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
DEADLINES = {'extract': 300, 'analyze': 60, 'predict': 180, 'assess': 60}
_ROUTE = detect.route
NEW_DATE = date(2026, 10, 22)  # OFFICE_NOTE documents 2026-10-20
# A note with no date of its own: a member's date supplies it, and a later member date is a date change. A member's
# date beside a documented one is a conflict instead (session interpretation 11), and nothing is routed for it.
UNDATED_NOTE = OFFICE_NOTE.replace('Date of service: 2026-10-20\n\n', '')


class LiveEncounter:
    """A reviewer, a FakeProvider standing in for the live adapter, and the encounter helpers."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def finished_encounter(self, text=OFFICE_NOTE, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        encounter_id = response.json()['id']
        self.assertEqual(models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.ASSESS).state,
                         models.Job.SUCCEEDED)
        self.assertEqual(len(self.provider.sent), 1)
        return encounter_id

    def change_date(self, encounter_id):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/context',
                                        data=json.dumps({'service_date': NEW_DATE.isoformat()}),
                                        content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')


@override_settings(**LIVE)
class DateChangeRoutesBeforeSendingTests(LiveEncounter, TestCase):
    def test_a_new_date_the_document_cannot_be_routed_for_in_time_sends_nothing(self):
        encounter_id = self.finished_encounter(UNDATED_NOTE, service_date='2026-10-20')
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
        self.assertEqual(len(self.provider.sent), 1, 'a request was sent for a date the document was never routed for')
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id).count(), runs_before)
        self.assertFalse(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id,
                                                          service_date=NEW_DATE).exists())

    def test_controls_a_new_date_that_routes_in_time_is_routed_once_then_sent(self):
        encounter_id = self.finished_encounter(UNDATED_NOTE, service_date='2026-10-20')
        self.change_date(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        # the routing reads run in forked children, so the record is the evidence: the analysis of the first date and
        # the guard's routing of the new one are both recorded with their dates
        dates = set(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id)
                    .values_list('service_date', flat=True))
        self.assertEqual(dates, {date(2026, 10, 20), NEW_DATE})

    def test_a_member_date_unlike_the_documented_one_is_never_routed_or_sent(self):
        # OFFICE_NOTE documents 2026-10-20: the member's different date is a conflict with both sides kept, and neither
        # is used until they agree (session interpretation 11; the member's date had been sent to the provider).
        encounter_id = self.finished_encounter()
        self.change_date(encounter_id)
        drain()
        self.assertFalse(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id,
                                                          service_date=NEW_DATE).exists())
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id)
        self.assertFalse(runs.filter(service_date=NEW_DATE).exists())
        self.assertFalse([run.pk for run in runs if f'Date of service: {NEW_DATE.isoformat()}' in run.contexts])
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'conflict')
        self.assertEqual(encounter.state, 'needs_clarification')
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        (question,) = [q for q in detail['clarifications'] if q['fact'] == 'service_date']
        self.assertIn('gives 2026-10-22; the document gives 2026-10-20', question['reason'])

    def test_nothing_is_sent_while_a_member_date_conflicts_and_clearing_it_reuses_the_documented_request(self):
        # Session interpretation 19: while the member's date conflicts with the documented one, nothing is built,
        # reused or sent - not a dateless request either, which would be paid for and then discarded - and the not-sent
        # run says why. Clearing the metadata returns to the documented date, whose retained result is reused.
        encounter_id = self.finished_encounter()
        self.change_date(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        run = models.ProviderRun.objects.filter(encounter_id=encounter_id).latest('created_at')
        self.assertEqual((run.state, run.sent, run.service_date, run.request_sha256),
                         (models.ProviderRun.NOT_SENT, False, None, ''))
        self.assertEqual(run.error, jobs.MEMBER_DATE_CONFLICT_MESSAGE)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')
        # held on purpose, never reported as a failed or a used request (refutation r1, context and report lenses)
        from studio import reports, review
        encounter = models.Encounter.objects.get(pk=encounter_id)
        blockers = review.readiness(encounter)['blockers']
        self.assertIn('Nothing was sent: the service date entered as encounter metadata conflicts with the document',
                      blockers)
        self.assertNotIn('The provider request failed', blockers)
        draft = reports.render_txt(reports.snapshot(encounter, 'draft')).decode('utf-8')
        held_line = next(line for line in draft.splitlines() if ' · not_sent · ' in line)
        self.assertIn('nothing was sent: the service date entered as encounter metadata conflicts', held_line)
        self.assertNotIn('used by this assessment', held_line)
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': ''})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        # the documented request's retained answer is read again; since the ec5 integration the re-check meets that
        # run itself (a held run is no request's outcome) where it queued a predict that reused it
        run = models.Encounter.objects.get(pk=encounter_id).current_assessment.provider_run
        self.assertEqual((run.state, run.service_date, (run.scope or {}).get('held')),
                         (models.ProviderRun.SUCCEEDED, date(2026, 10, 20), None))
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).current_context.facts['service_date']['origin'],
                         'document')


# --- pipeline:1 and pipeline:2: a stopped analysis versus one that overran ------------------------------------------

from datetime import timedelta  # noqa: E402

from django.conf import settings  # noqa: E402
from django.utils import timezone  # noqa: E402



@override_settings(**LIVE)
class StoppedOrOverranAnalysisTests(LiveEncounter, TestCase):
    def extracted_only(self, text=OFFICE_NOTE):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        encounter_id = response.json()['id']
        extract = jobs.claim_next()
        self.assertEqual(extract.kind, models.Job.EXTRACT)
        jobs.run_job(extract)
        return encounter_id, models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.ANALYZE)

    def cancel(self, encounter_id, analyze, cause):
        if cause == 'stop':
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop', {}).status_code, 200)
        elif cause == 'sweep':
            self.assertEqual(jobs.claim_next().pk, analyze.pk)
            models.Job.objects.filter(pk=analyze.pk).update(
                started_at=timezone.now() - timedelta(seconds=settings.STALE_RUNNING_SECONDS + 60))
            jobs.mark_stale()
        else:
            models.Job.objects.filter(pk=analyze.pk).update(deadline_at=timezone.now() - timedelta(seconds=1))
            jobs.claim_next()
        analyze.refresh_from_db()
        self.assertEqual(analyze.state, models.Job.CANCELLED, cause)
        self.assertFalse(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id).exists())

    def test_a_context_change_after_a_stopped_analysis_sends_once_and_only_for_the_members_date(self):
        for cause in ('stop', 'sweep', 'expiry'):
            with self.subTest(cause=cause):
                # a distinct document per cause: an identical request in one workspace is reused, never re-sent; a
                # note with no date of its own, so the member's date supplies it
                encounter_id, analyze = self.extracted_only(UNDATED_NOTE + f'\nReference: {cause}.\n')
                self.cancel(encounter_id, analyze, cause)
                sent_before = len(self.provider.sent)
                response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': NEW_DATE.isoformat()})
                self.assertEqual(response.status_code, 201, response.content)
                drain()
                self.assertEqual(len(self.provider.sent), sent_before + 1)
                run = models.ProviderRun.objects.get(encounter_id=encounter_id)
                self.assertEqual((run.service_date, run.sent), (NEW_DATE, True))
                self.assertIn(f'Date of service: {NEW_DATE.isoformat()}', run.contexts)
                self.assertFalse(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id,
                                                                  service_date__isnull=True).exists(),
                                 'the document was analysed for its own date (none) first')
                assess = models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.ASSESS).get()
                self.assertEqual(assess.state, models.Job.SUCCEEDED, assess.error)

    def test_a_stopped_analysis_whose_new_date_cannot_be_read_in_time_sends_nothing(self):
        encounter_id, analyze = self.extracted_only(UNDATED_NOTE)
        self.cancel(encounter_id, analyze, 'stop')

        def slow_for_the_new_date(text, service_date=None):
            if service_date == NEW_DATE:
                time.sleep(30)
            return _ROUTE(text, service_date)

        with override_settings(JOB_DEADLINE_SECONDS=dict(DEADLINES, analyze=1)), \
                mock.patch.object(detect, 'route', slow_for_the_new_date):
            response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': NEW_DATE.isoformat()})
            self.assertEqual(response.status_code, 201, response.content)
            drain()
        predict = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.PREDICT)
        self.assertEqual(predict.state, models.Job.FAILED)
        self.assertIn('took longer than 1 seconds and was stopped', predict.error)
        self.assertEqual(self.provider.sent, [])
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id).exists())

    def test_an_addendum_whose_analysis_overran_refuses_a_context_change_and_sends_nothing(self):
        encounter_id = self.finished_encounter()

        def slow_for_the_addendum(text, service_date=None):
            if 'ADDENDUM (revision' in text:
                time.sleep(30)
            return _ROUTE(text, service_date)

        with override_settings(JOB_DEADLINE_SECONDS=dict(DEADLINES, analyze=1)), \
                mock.patch.object(detect, 'route', slow_for_the_addendum):
            response = self.post(f'/api/encounters/{encounter_id}/addenda',
                                 {'text': 'Setting confirmed as office.', 'synthetic_attestation': 'yes'})
            self.assertEqual(response.status_code, 201, response.content)
            drain()
        revision = models.Encounter.objects.get(pk=encounter_id).current_revision
        self.assertEqual(revision.number, 2)
        self.assertEqual(models.Job.objects.get(revision=revision, kind=models.Job.ANALYZE).state, models.Job.FAILED)
        for values in ({'setting': 'office'}, {'service_date': NEW_DATE.isoformat()}):
            with self.subTest(values=values):
                response = self.post(f'/api/encounters/{encounter_id}/context', values)
                self.assertEqual(response.status_code, 409, response.content)
                self.assertIn('could not be read to the end', response.json()['error'])
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assertFalse(models.Job.objects.filter(revision=revision, kind=models.Job.PREDICT).exists())
        self.assertFalse(models.ProviderRun.objects.filter(revision=revision).exists())


# --- bypass:2 / pipeline:6: a missing or wrong attestation is invalid input (400), as API.md says ------------------

from studio import review  # noqa: E402


@override_settings(**LIVE)
class AttestationStatusTests(LiveEncounter, TestCase):
    def test_a_missing_or_wrong_acknowledgement_answers_400_and_records_nothing(self):
        encounter_id = self.finished_encounter()
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        approvable = [p['id'] for p in detail['assessment']['proposals'] if 'approve' in p['allowed_actions']]
        self.assertTrue(approvable, 'nothing to approve: the test proves nothing')
        url = f'/api/encounters/{encounter_id}/decisions'
        for acknowledgement in ('I did not read the document.', review.ACKNOWLEDGEMENTS['agent'], '', '   ', None):
            body = {'proposal_id': approvable[0], 'action': 'approve'}
            if acknowledgement is not None:
                body['acknowledgement'] = acknowledgement
            with self.subTest(acknowledgement=acknowledgement):
                response = self.post(url, body)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn('acknowledgement', response.json()['error'])
        self.assertFalse(models.Decision.objects.filter(encounter_id=encounter_id).exists())

    def test_controls_an_unavailable_action_is_still_409_and_the_exact_attestation_approves(self):
        encounter_id = self.finished_encounter()
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        approvable = [p['id'] for p in detail['assessment']['proposals'] if 'approve' in p['allowed_actions']]
        url = f'/api/encounters/{encounter_id}/decisions'
        response = self.post(url, {'proposal_id': approvable[0], 'action': 'revoke'})
        self.assertEqual(response.status_code, 409, response.content)
        response = self.post(url, {'proposal_id': approvable[0], 'action': 'approve',
                                   'acknowledgement': '  ' + review.ACKNOWLEDGEMENTS['human'] + '\n'})
        self.assertEqual(response.status_code, 201, response.content)


# --- bypass:3: whether a reinstated code can be approved is the same answer for every member -----------------------

from studio import reports, serializers  # noqa: E402
from tests.test_repairs_r4c_lead_review import excluded_em_result  # noqa: E402


class ApproveWithheldByTests(TestCase):
    def setUp(self):
        self.s = pf.scenario()

    def field(self, key):
        answers = {}
        for user in (self.s.reviewer, self.s.viewer):
            detail = json.loads(json.dumps(serializers.encounter_detail(self.s.encounter, self.s.membership(user)),
                                           default=str))
            (item,) = [p for p in detail['assessment']['proposals'] if p['key'] == key]
            answers[user.username] = (item['approve_withheld_by'], 'approve' in item['allowed_actions'])
        return answers

    def test_a_reinstated_code_whose_gate_passes_is_approvable_for_every_member_who_asks(self):
        pf.assess(self.s.encounter, pf.standard_result())
        self.assertEqual({value for value, _ in self.field('exc:0').values()}, {None})  # not reinstated yet
        self.s.decide('exc:0', 'reinstate', note='Performed today.')
        answers = self.field('exc:0')
        self.assertEqual(answers[self.s.reviewer.username], (None, True))
        self.assertEqual(answers[self.s.viewer.username], (None, False))

    def test_a_gate_that_does_not_pass_or_a_same_day_hold_is_named_for_every_member(self):
        held = pf.result(pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                                     checks=pf.standard_checks() + (pf.check('review.reinstatement', 'warn'),)))
        pf.assess(self.s.encounter, held)
        self.s.decide('exc:0', 'reinstate')
        self.assertEqual(set(self.field('exc:0').values()), {('review.reinstatement', False)})

        s = self.s = pf.scenario()
        pf.assess(s.encounter, excluded_em_result(), ctx=pf.context(s.encounter, s.revision))
        s.decide('exc:1', 'reinstate')
        s.decide('exc:0', 'reinstate')
        self.assertEqual(set(self.field('exc:0').values()), {('em.same_day_if_reinstated', False)})
        self.assertEqual(set(self.field('exc:1').values()) - {(None, False)}, {(None, True)})


# --- pipeline:4: the reviewed status line counts confirmations, never an exclusion nobody decided -------------------

class ConfirmedCountTests(TestCase):
    def setUp(self):
        self.s = pf.scenario()

    def status_line(self):
        text = bytes(reports.generate(self.s.encounter, models.ReportArtifact.REVIEWED, 'txt',
                                      self.s.reviewer).content).decode('utf-8')
        (line,) = [ln for ln in text.splitlines() if ln.startswith('Review status:')]
        return line

    @staticmethod
    def not_reinstatable(key, code, passage):
        return pf.proposal(key, code, [passage], bucket='excluded', reinstatable=False,
                           exclusion_reason='Excluded from CPT-only results.')

    def test_an_undecided_exclusion_that_cannot_be_reinstated_is_never_counted_as_confirmed(self):
        pf.assess(self.s.encounter, pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                                              self.not_reinstatable('exc:8', '45380', pf.CECUM_PASSAGE)))
        self.s.decide('sel:0', 'approve')
        line = self.status_line()
        self.assertTrue(line.startswith('Review status: complete — 1 approved, 0 rejected, 0 documentation-check '
                                        'exclusions confirmed;'), line)

    def test_one_confirmation_beside_two_undecided_exclusions_counts_one(self):
        pf.assess(self.s.encounter, pf.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
            pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                        exclusion_reason='The colonoscopy is planned, not performed on this date.'),
            self.not_reinstatable('exc:8', '45380', pf.CECUM_PASSAGE),
            self.not_reinstatable('exc:9', '45385', pf.SNARE_PASSAGE)))
        self.s.decide('sel:0', 'approve')
        self.s.decide('exc:0', 'confirm')
        line = self.status_line()
        self.assertTrue(line.startswith('Review status: complete — 1 approved, 0 rejected, 1 documentation-check '
                                        'exclusion confirmed;'), line)


# --- pipeline:5: each stage's child computes the context and the analysis once and reuses them -----------------------

from studio.gi import context as gi_context  # noqa: E402
from tests.test_repairs_r4c_lead_pipeline import Probe  # noqa: E402


@override_settings(**LIVE)
class OneComputationPerChildTests(LiveEncounter, TestCase):
    def test_each_child_computes_the_context_and_the_analysis_once(self):
        # _service_dates runs only inside context._context's cached body and _route only inside detect._analysis's,
        # so each probe line is one real computation, not one public call. A fresh text and empty caches in this
        # process: a child forks with this process's caches, and an inherited entry would read as reuse.
        detect._analysis.cache_clear()
        gi_context._context.cache_clear()
        probe = Probe(self)
        text = OFFICE_NOTE + 'Reference: one computation per child.\n'
        with mock.patch.object(detect, '_route', probe.wrap('analysis', detect._route)), \
                mock.patch.object(gi_context, '_service_dates', probe.wrap('context', gi_context._service_dates)):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
            self.assertEqual(response.status_code, 201, response.content)
            drain()
        encounter_id = response.json()['id']
        self.assertEqual(models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.ASSESS).state,
                         models.Job.SUCCEEDED)
        self.assertEqual(len(self.provider.sent), 1, 'the provider was not reached: validation read no cited span')
        per_child = {}
        for label, pid in probe.calls():
            per_child.setdefault(int(pid), []).append(label)
        self.assertNotIn(os.getpid(), per_child, 'a computation ran in the worker process')
        # routing reads the context itself, so the assess child computes it once too: one of each per child, and a
        # second computation of either in one child is the reuse lost
        self.assertEqual(sorted(sorted(labels) for labels in per_child.values()),
                         [['analysis', 'context'], ['analysis', 'context']],
                         f'expected two children (analyze, assess), each computing the context and the analysis once: '
                         f'{per_child}')
