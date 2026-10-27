"""The bounded second review (ARCHITECTURE 5.11), end to end through the pipeline with an in-process provider.

Once per revision and service date, only for a documented service left without a supported proposal, under the same
send discipline as the primary request; its codes fill only unresolved items. Synthetic data, no network.
"""
import hashlib
import json
from unittest import mock

from django.test import Client, TestCase, override_settings

from studio import jobs, models, reports
from studio.providers.corti import ADAPTER_VERSION
from studio.types import ProviderRequest, RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import drain

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')

REPORT = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Colonoscopy report (fictional)
Date of service: 2026-10-16
Place of service: Hospital outpatient department
The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
A separate 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps; it was not removed.
"""


def response(context, quotes):
    codes = []
    for code, quote in quotes:
        start = context.index(quote)
        codes.append({'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING',
                      'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}],
                      'alternatives': []})
    return json.dumps({'codes': codes, 'candidates': [], 'usageInfo': {'creditsConsumed': 0.02}}).encode()


class TwoPassProvider:
    """The live adapter's name and version (so the real normaliser reads the stored runs). The first request gets
    ``first``; any later request gets ``later``. Each outcome can be scripted."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self, first, later, outcomes=()):
        self.first, self.later, self.outcomes, self.requests = first, later, list(outcomes), []

    def build_request(self, text, service_date):
        contexts = [text] + ([f'Date of service: {service_date.isoformat()}'] if service_date else [])
        body = {'system': ['icd10cm-outpatient', 'cpt'], 'context': [{'type': 'text', 'text': c} for c in contexts]}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False).encode()).hexdigest()
        return ProviderRequest(provider=self.name, adapter_version=self.adapter_version, body=body,
                               canonical_sha256=digest, contexts=tuple(contexts))

    def send(self, request, *, deadline_s):
        quotes = self.first if not self.requests else self.later
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if self.outcomes else 'succeeded'
        if outcome == 'unknown':
            return RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent.')
        data = response(request.contexts[0], quotes)
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


@override_settings(**LIVE)
class SecondReviewTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = TwoPassProvider(first=[('45385', 'was removed with a cold snare')],
                                        later=[('45380', 'was sampled with cold biopsy forceps'),
                                               ('45385', 'was removed with a cold snare')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, text=REPORT):
        reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def test_one_second_review_fills_the_unresolved_biopsy(self):
        encounter_id = self.create()
        drain()
        runs = list(models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at'))
        self.assertEqual([(r.purpose, r.state) for r in runs], [('primary', 'succeeded'), ('second_review', 'succeeded')])
        second = runs[1]
        excerpt = second.contexts[0]
        self.assertNotEqual(excerpt, REPORT)  # only the text that documents the service
        self.assertIn('cold biopsy forceps', excerpt)
        self.assertEqual(second.scope['primary_run'], str(runs[0].pk))
        encounter = models.Encounter.objects.get(pk=encounter_id)
        assessment = encounter.current_assessment
        self.assertEqual(assessment.second_run_id, second.pk)
        codes = {p.code: p for p in assessment.proposals.filter(bucket='selected')}
        self.assertEqual(sorted(codes), ['45380', '45385'])
        self.assertEqual(codes['45380'].support['origin'], 'second_review')
        text = encounter.current_revision.text
        for span in codes['45380'].evidence:  # moved from the excerpt to the revision, and exact there
            self.assertEqual(text[span['start']:span['end']], span['text'])
        self.assertEqual(assessment.completeness['unresolved_items'], [])
        drain()
        self.assertEqual(len(self.provider.requests), 2)  # bounded: never a third

    def test_a_refused_second_review_response_is_a_failed_check_and_never_reported_used(self):
        """A second-review response the adapter refuses whole (here over its selection cap) decides nothing: its check
        fails, as provider.status does for a refused primary (round 7 bypass:1), and the report never calls it used."""
        self.provider.later = [('45380', 'was sampled with cold biopsy forceps')] * 65
        encounter_id = self.create()
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        assessment = encounter.current_assessment
        check = next(c for c in assessment.encounter_checks if c['id'] == 'provider.second_review')
        self.assertEqual(check['status'], 'fail')
        self.assertIn('was not used', check['detail'])
        self.assertEqual([p.code for p in assessment.proposals.filter(bucket='selected')], ['45385'])
        draft = reports.render_txt(reports.snapshot(encounter, 'draft')).decode()
        usage = draft[draft.index('\nPROVIDER USAGE\n'):draft.index('\nREFERENCE SOURCES\n')]
        runs = [line for line in usage.split('\n') if line.startswith('  - ')]
        self.assertEqual(len(runs), 2)
        self.assertTrue(runs[0].endswith(' · used by this assessment'), runs[0])
        self.assertIn(' · bounded second review', runs[1])
        self.assertTrue(runs[1].endswith(' · read by this assessment; its response was not used'), runs[1])

    def test_no_second_review_after_a_primary_response_refused_whole(self):
        """A primary response the adapter refuses whole (over its selection cap) was not used: nothing was proposed,
        so there is nothing a second review could fill, and none is sent."""
        self.provider.first = [('45385', 'was removed with a cold snare')] * 65
        encounter_id = self.create()
        drain()
        runs = list(models.ProviderRun.objects.filter(encounter_id=encounter_id))
        self.assertEqual([(r.purpose, r.state) for r in runs], [('primary', 'succeeded')])
        self.assertEqual(len(self.provider.requests), 1)

    def test_no_second_review_without_a_known_service_date(self):
        """With no service date every proposal waits on the date question and a dated passage cannot be placed in
        time: no second review is paid for until the date is known."""
        encounter_id = self.create(REPORT.replace('Date of service: 2026-10-16\n', ''))
        drain()
        runs = list(models.ProviderRun.objects.filter(encounter_id=encounter_id))
        self.assertEqual([(r.purpose, r.service_date) for r in runs], [('primary', None)])
        self.assertEqual(len(self.provider.requests), 1)

    def test_no_second_review_once_one_was_made_for_the_revision_and_date(self):
        encounter_id = self.create()
        drain()
        reply = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps({'setting': 'asc'}),
                                 content_type='application/json')
        self.assertIn(reply.status_code, (200, 201), reply.content)
        drain()
        self.assertEqual(len(self.provider.requests), 2)

    def test_a_stop_before_it_runs_sends_nothing_and_resume_runs_it_once(self):
        encounter_id = self.create()
        while True:  # through the first assess, which queues the second review
            job = jobs.claim_next()
            jobs.run_job(job)
            if job.kind == models.Job.ASSESS:
                break
        self.assertTrue(models.Job.objects.filter(encounter_id=encounter_id, kind='review2', state='queued').exists())
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'stopped')
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.requests), 2)

    def test_an_unknown_second_review_blocks_every_further_send(self):
        self.provider.outcomes = ['succeeded', 'unknown']
        encounter_id = self.create()
        drain()
        runs = list(models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at'))
        self.assertEqual([r.state for r in runs], ['succeeded', 'unknown'])
        encounter = models.Encounter.objects.get(pk=encounter_id)
        # the assessment that followed read the primary run only; the unknown outcome is shown and must be reconciled
        self.assertIsNone(encounter.current_assessment.second_run_id)
        reply = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps({'setting': 'asc'}),
                                 content_type='application/json')
        drain()
        self.assertEqual(len(self.provider.requests), 2)

    def test_no_second_review_that_repeats_the_primary_request(self):
        """A report that opens with its title is documented from its first character, so the excerpt is the whole text
        and the request would be byte-identical to the primary's (refutation r1, lenses sends and migrate)."""
        text = REPORT[REPORT.index('Colonoscopy report'):]
        encounter_id = self.create(text)
        drain()
        self.assertEqual(len(self.provider.requests), 1)
        runs = list(models.ProviderRun.objects.filter(encounter_id=encounter_id).values_list('purpose', 'sent'))
        self.assertEqual(runs, [('primary', True)])

    def test_an_excerpt_pasted_as_its_own_note_reuses_the_answered_request(self):
        first = self.create()
        drain()
        excerpt = models.ProviderRun.objects.get(encounter_id=first, purpose='second_review').contexts[0]
        self.assertEqual(len(self.provider.requests), 2)
        second = self.create(excerpt)
        drain()
        self.assertEqual(len(self.provider.requests), 2)  # the identical request is reused, never resent
        run = models.ProviderRun.objects.get(encounter_id=second, purpose='primary')
        self.assertEqual((run.sent, run.state), (False, models.ProviderRun.SUCCEEDED))
        self.assertIsNotNone(run.reused_from_id)

    def test_clearing_a_member_date_conflict_keeps_the_paid_second_review(self):
        """Refutation r1 (context lens): the recovery interpretation 19 prescribes - clear the member's date - reuses the
        identical primary result; the second review made for it is used again, never lost and never paid twice."""
        import json
        encounter_id = self.create()
        drain()
        self.assertEqual(len(self.provider.requests), 2)
        for value in ('2026-10-22', ''):
            with self.captureOnCommitCallbacks(execute=True):
                reply = self.client.post(f'/api/encounters/{encounter_id}/context',
                                         data=json.dumps({'service_date': value}), content_type='application/json')
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
        self.assertEqual(len(self.provider.requests), 2)
        assessment = models.Encounter.objects.get(pk=encounter_id).current_assessment
        codes = {p.code: p.support.get('origin') for p in assessment.proposals.filter(bucket='selected')}
        self.assertEqual(codes, {'45380': 'second_review', '45385': 'primary'})
        self.assertEqual(assessment.completeness['unresolved_items'], [])

    def test_no_second_review_when_every_documented_service_is_accounted_for(self):
        self.provider.first = [('45385', 'was removed with a cold snare'),
                               ('45380', 'was sampled with cold biopsy forceps')]
        self.create()
        drain()
        self.assertEqual(len(self.provider.requests), 1)

    def test_reconciling_the_unknown_second_review_allows_one_more(self):
        self.provider.outcomes = ['succeeded', 'unknown']
        encounter_id = self.create()
        drain()
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state='unknown')
        self.assertEqual(unknown.purpose, 'second_review')
        reply = self.client.post(f'/api/encounters/{encounter_id}/reconcile',
                                 data=json.dumps({'provider_run_id': str(unknown.pk),
                                                  'note': 'Checked the provider console: no response was recorded.'}),
                                 content_type='application/json')
        self.assertIn(reply.status_code, (200, 201), reply.content)
        drain()
        runs = list(models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at'))
        sent = [r for r in runs if r.sent]
        self.assertEqual([(r.purpose, r.state) for r in sent],
                         [('primary', 'succeeded'), ('second_review', 'unknown'), ('second_review', 'succeeded')])
        self.assertEqual(len(self.provider.requests), 3)
        drain()
        self.assertEqual(len(self.provider.requests), 3)


OFFICE_LIST = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-21\n'
               'Place of service: Office\nEstablished patient office visit for rectal bleeding.\nChief complaint: Rectal '
               'bleeding.\nMedical decision making: moderate.\n{block}\n')
REPORT_LIST = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-21\n'
               'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. No polyps were seen.\n'
               '{block}\n')
VISIT_LINE = 'Established patient office visit for rectal bleeding.'
CECUM_LINE = 'The colonoscope was advanced to the cecum.'


class NoSecondReviewForWhatWasNotDoneTests(TestCase):
    """A paid second review is sent only for a documented service or act the document states done (triage round 2
    skeptic, proven end to end: checked boxes under consent, equipment, education and "discussed" lists, a "Yes" field
    answering a printed question, and consent sentences had each queued one). The positive control shows the instrument
    sees a second review when one is due."""

    NOT_DONE = (
        (REPORT_LIST, 'Consent obtained for:\n\n\u2612 Biopsy\n\u2612 Cold snare polypectomy', '45378', CECUM_LINE),
        (REPORT_LIST, 'Consent obtained for:\n\u2612 Biopsy\n(risks: bleeding, perforation)\n\u2612 Cold snare polypectomy',
         '45378', CECUM_LINE),
        (REPORT_LIST, 'Equipment:\n- CF-HQ190 colonoscope\n\u2612 Cold snare\n\u2612 Biopsy forceps', '45378', CECUM_LINE),
        (REPORT_LIST, 'Patient education provided regarding:\n\n\u2612 Biopsy\n\u2612 Cold snare polypectomy', '45378',
         CECUM_LINE),
        (REPORT_LIST, 'Available if needed:\n\n\u2612 Cold snare polypectomy', '45378', CECUM_LINE),
        (REPORT_LIST, 'Interventions:\n(if needed)\n\u2612 Cold snare polypectomy', '45378', CECUM_LINE),
        (REPORT_LIST, 'Consent was obtained for biopsy and cold snare polypectomy.', '45378', CECUM_LINE),
        (REPORT_LIST, 'Written consent for biopsy and cold snare polypectomy was obtained.', '45378', CECUM_LINE),
        (REPORT_LIST, 'Biopsy recommended at follow-up?   Yes   No\n\n[PDF form fields on page 1]\nBiopsy: Yes', '45378',
         CECUM_LINE),
        (REPORT_LIST, 'Discussed with patient: Biopsy\n\n[PDF form fields on page 1]\nBiopsy: checked', '45378',
         CECUM_LINE),
        (OFFICE_LIST, 'Interventions:\n\u2612 Colonoscopy\n\u2612 Cold snare polypectomy', '99214', VISIT_LINE),
        (OFFICE_LIST, 'Discussed today:\n\n\u2612 Colonoscopy\n\u2612 Cold snare polypectomy', '99214', VISIT_LINE),
        (OFFICE_LIST, 'Prior authorization was obtained for colonoscopy.', '99214', VISIT_LINE),
        (OFFICE_LIST, 'Colonoscopy within 10 years:\nLast colonoscopy:', '99214', VISIT_LINE),
        # refutation r1 (release lens): the reader's misreadings of a denied, earlier, planned or possible act; the
        # routing-era reader does not read them as done today, so nothing is sent (engine._routing_agrees)
        (REPORT_LIST, 'On withdrawal, no polyp was snared.', '45378', CECUM_LINE),
        (REPORT_LIST, 'At her most recent colonoscopy the polyp was removed by cold snare.', '45378', CECUM_LINE),
        (REPORT_LIST, 'Snare polypectomy of the polyp, since it appeared deeply invasive, was not performed.', '45378',
         CECUM_LINE),
        (REPORT_LIST, 'The polyp was neither biopsied nor removed.', '45378', CECUM_LINE),
        (REPORT_LIST, 'Hot snare polypectomy can be performed once anticoagulation is held.', '45378', CECUM_LINE),
        (REPORT_LIST, 'Impression: as above.\nPlan:\nProcedure:\n\u2612 Endoscopic mucosal resection\n'
                      '\u2612 Cold snare polypectomy\nReturn in 4 weeks for the above.', '45378', CECUM_LINE),
    )

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)

    def sends(self, text, code, quote):
        provider = TwoPassProvider(first=[(code, quote)], later=[])
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
        purposes = list(models.ProviderRun.objects.filter(encounter_id=reply.json()['id'])
                        .order_by('created_at').values_list('purpose', flat=True))
        return len(provider.requests), purposes

    @override_settings(**LIVE)
    def test_nothing_not_done_is_sent_for_a_second_review(self):
        for template, block, code, quote in self.NOT_DONE:
            with self.subTest(block=block):
                self.assertEqual(self.sends(template.format(block=block), code, quote), (1, ['primary']))

    @override_settings(**LIVE)
    def test_control_a_checked_box_under_interventions_is_sent(self):
        text = REPORT_LIST.format(block='Interventions:\n\u2612 Biopsy')
        self.assertEqual(self.sends(text, '45378', CECUM_LINE), (2, ['primary', 'second_review']))
