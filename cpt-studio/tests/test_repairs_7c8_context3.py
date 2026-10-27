"""Repair round 7c8, cluster CONTEXT round 3 (studio/gi/context.py): the service date sent to Corti.

Owner decision 2026-10-27 (narrow, install-first), must-fix classes 1 (a wrong or member-supplied service date in a
provider request), 2 (stage time) and 4 (a code excluded on a dated check without a reviewer's decision). The skeptic of
round 2 (0e639e79f, 486763512) demonstrated seven issues, sk:1 .. sk:7 below, each re-checked here at its smallest
input. The rule stays the round-2 rule - the reader may be unsure, but it is never silently wrong - and each repair is a
structural one:

sk:1  a member date agrees only with a date some candidate states as its own value (a date of birth beside it does not);
sk:2  a qualifier in another field before a label that opens its own field still holds the date (it is asked);
sk:3  the service-date fact is linear in the number of the note's labelled dates;
sk:4  a title naming another discipline is never the note's heading, whatever its title word;
sk:5  a field on the line above naming another occurrence, or a phrase attached after the date naming one (also on the
      line it wraps to), holds the date;
sk:6  a dated line naming the service beside a bare "Date:" line makes the date a question;
sk:7  a date label or a "Date:" line may name the time ("DOS/Time", "Date & Time"), and a clock may follow a date.

An over-hold (the date asked although a coder would know it) is a known limit; a wrong or member-supplied date where the
document states another is not. Synthetic text only; no network (the suite's FakeProvider).
"""
import json
import time
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import bounded, jobs, models
from studio.gi import context
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.test_repairs_7c8_context import DateAssertions

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
OFFICE_BODY = OFFICE_NOTE.split('\n', 1)[1].replace('Date of service: 2026-10-20\n', '')
VISIT_BODY = ('Established patient office visit for chronic constipation.\n'
              'Total time on the date of the encounter was 24 minutes.\n')
EGD_BODY = ('PROCEDURE NOTE: EGD\nTechnique: The upper endoscope was advanced to the second portion of the duodenum.\n'
            'Findings: On 10/14/2026 biopsies were taken from the antrum.\n')
COLO_BODY = ('PROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
             'Findings: On 10/14/2026 a 5 mm sigmoid polyp was removed with a cold snare.\n')
COLO_PLAIN = ('PROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
              'Findings: A 5 mm sigmoid polyp was removed with a cold snare.\n')
ELENA_DATE = '1998-01-01'  # a member-entered date far from any documented one (the Elena incident)
BIRTH = '01/01/1998'  # the same day written as a date of birth beside the date of service


def date_fact(text):
    return context.extract_context(text)['service_date']


def evidence_text(text):
    return [' '.join(e.text.split()) for e in date_fact(text).evidence]


class Provider(FakeProvider):
    """FakeProvider whose response names only the selections the request's own text contains."""

    def send(self, request, *, deadline_s):
        every = self.selections
        self.selections = [(code, quote) for code, quote in every if quote in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.selections = every


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class EndToEnd(TestCase):
    """End to end with the suite's FakeProvider: the date each provider request carries, and the dated checks."""

    BIOPSY = ('43239', 'biopsies were taken from the antrum')
    SNARE = ('45385', 'was removed with a cold snare')
    VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(selections=[self.VISIT, self.SNARE, self.BIOPSY])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def finished(self, text, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def set_context(self, encounter_id, values):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps(values),
                                        content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        drain()

    def dates_sent(self, encounter_id):
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id, sent=True).order_by('created_at')
        return [list(run.contexts[1:]) for run in runs]

    def bucket(self, encounter_id, code):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        return encounter.current_assessment.proposals.get(code=code, bucket__in=('selected', 'excluded')).bucket

    def assert_held(self, encounter_id, runs=1):
        """Nothing sent for the member's date: the last run is held as a member date conflict."""
        held = models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at')
        self.assertEqual(held.count(), runs)
        last = held.last()
        self.assertEqual((last.sent, last.state, last.scope),
                         (False, models.ProviderRun.NOT_SENT, {'held': models.ProviderRun.HELD_MEMBER_DATE_CONFLICT}))
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')

    def assert_never_sent(self, encounter_id, *dates):
        sent = [line for run in self.dates_sent(encounter_id) for line in run]
        for value in dates:
            self.assertNotIn(f'Date of service: {value}', sent)


class ManyLabelledDatesCostTests(SimpleTestCase):
    """sk:3 (a cost regression of 0e639e79f, class 2): the service-date fact set the note's own labelled dates apart from
    the others by a list membership test - one dataclass comparison per pair, quadratic in the number of labelled dates:
    'DOS: 10/14/2026' 24,000 times (384,067 characters, under the paste cap) overran the analyze stage's 60 s, and 12,000
    overran a member's POST /context (15 s). Every set is now kept by identity: both children read it in about a second
    (the doubling ratios are in the commit)."""

    TEXT = HEAD + 'DOS: 10/14/2026\n' * 24000

    def test_the_analyze_child_reads_it_within_the_stage_deadline(self):
        started = time.perf_counter()
        out = bounded.run_bounded(jobs._analyze_child, self.TEXT, {}, settings.MAX_SERVICE_MENTIONS,
                                  seconds=settings.JOB_DEADLINE_SECONDS['analyze'],
                                  memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, 20)
        self.assertEqual((out[0]['service_date'].origin, out[0]['service_date'].value), ('document', '2026-10-14'))

    def test_a_member_s_context_child_reads_it_within_its_bound(self):
        started = time.perf_counter()
        facts = bounded.run_bounded(context.extract_context, self.TEXT, seconds=settings.CONTEXT_REQUEST_SECONDS,
                                    memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, settings.CONTEXT_REQUEST_SECONDS)
        self.assertEqual(facts['service_date'].origin, 'document')
