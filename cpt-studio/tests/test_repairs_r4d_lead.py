"""Round 6 findings the lead owns (repair round 4d): cost and the provider-send guard.

bounded:1 — every cited span's family lookup scanned every routed service, so a long report cited span by span was
  quadratic (a 400,000-character status-row report overran the assess stage).
Synthetic data only; no network.
"""
import time
from datetime import date

from django.test import SimpleTestCase

from studio.gi import detect

DAY = date(2026, 10, 21)
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'


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


@override_settings(**LIVE)
class DateChangeRoutesBeforeSendingTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def finished_encounter(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
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

    def test_a_new_date_the_document_cannot_be_routed_for_in_time_sends_nothing(self):
        encounter_id = self.finished_encounter()
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
        encounter_id = self.finished_encounter()
        self.change_date(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        # the routing reads run in forked children, so the record is the evidence: the analysis of the first date and
        # the guard's routing of the new one are both recorded with their dates
        dates = set(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id)
                    .values_list('service_date', flat=True))
        self.assertEqual(dates, {date(2026, 10, 20), NEW_DATE})
