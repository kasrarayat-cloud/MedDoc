"""Refutation round 2, R2-PARITY (HARNESS.md 9, I1; the round-2 repair plan's D6): Corti-only parity where the harness
and the round-4 head (80f2f2dc8) could differ and no earlier proof looked.

parity-r2-2. Re-persisting an identical result on identical inputs returns the current assessment unchanged
(review.persist_assessment). The harness had made what is recorded beside the result - the participants record and the
reference retrieval traces - decide it, so an identical re-assessment made after the CMS passages were imported (the
installer's passages phase runs after its app phase; a later release can add a passage file) recorded a second
assessment with the same sha256, carried the reviewer's decisions onto it and opened its questions again. With no model
participant configured, review._same_assessment now compares exactly what the round-4 head compared; with one
configured, also the participant runs each entry names, and never the retrieval traces.

Synthetic data only. Corti is the in-process FakeProvider read by the real normalizer (and, with participants
configured, the pipeline tests' fakes); the CMS tables are loaded through the importers from the synthetic fixtures in
the real CMS layouts (tests.test_reference). Nothing is sent anywhere.
"""
import hashlib
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.db import connection
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, participants, review
from studio.reference import passages
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_harness_pipeline import BOTH, HarnessCase
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_reference import ArchiveMixin
from tests.test_repairs_pipeline import LIVE

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
REACHED = 'The colonoscope was advanced to the cecum and the examination was completed.'
SNARE = 'was removed with a hot snare'
# The refutation lens's colonoscopy (parity-r2-1, parity-r2-2): the cecum reached, a polyp removed with a hot snare and
# a lesion biopsied with cold forceps, dated 2026-10-21, inside the fixtures' 2026-Q4 window.
COLON = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-21\n'
         'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n' + REACHED + '\n'
         'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
         'A separate 12 mm flat lesion in the ascending colon was biopsied with cold forceps.\n')
FAILED_BODY = b'{"error": "synthetic"}'


def import_passages():
    """The bundled CMS passage files, imported as the installer's passages phase imports them; the passage count."""
    for path in passages.bundled_files():
        passages.import_data_file(path)
    return models.ReferencePassage.objects.count()


def passage_count(retrieval):
    return sum(len(entry.get('passages') or []) for entry in retrieval or [] if isinstance(entry, dict))


class Persisted:
    """Every call of review.persist_assessment from here on: the records passed beside its result and the assessment it
    returned, so a test shows what the second assess retrieved (it is not vacuous) and which assessment it was given."""

    def __init__(self, case):
        self.calls, real = [], review.persist_assessment

        def persist(**kwargs):
            assessment = real(**kwargs)
            self.calls.append({'participants': json.loads(json.dumps(list(kwargs.get('participants') or []))),
                               'retrieval': json.loads(json.dumps(list(kwargs.get('retrieval') or []))),
                               'returned': assessment.pk})
            return assessment
        patcher = mock.patch('studio.review.persist_assessment', side_effect=persist)
        patcher.start()
        case.addCleanup(patcher.stop)


class AssessedTwiceMixin:
    """What an encounter holds after a second assess of the same inputs (the round-4 head's answer: one assessment, the
    decisions where they were, one 'assessment.created', the questions it raised)."""

    def holdings(self, encounter_id):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        decisions = models.Decision.objects.filter(encounter_id=encounter_id)
        return {'assessments': models.Assessment.objects.filter(encounter_id=encounter_id).count(),
                'current': encounter.current_assessment_id,
                'decisions': decisions.count(), 'carried': decisions.filter(carried_from__isnull=False).count(),
                'created': models.AuditEvent.objects.filter(encounter_id=encounter_id,
                                                            event='assessment.created').count(),
                'open': sorted(str(pk) for pk in models.Clarification.objects.filter(
                    encounter_id=encounter_id, state=models.Clarification.OPEN).values_list('pk', flat=True))}

    def kill_after_persisting(self, encounter_id):
        """The worker died after the assess recorded its assessment and before the job was marked: the stale sweep
        settles it (cancelled, resumable)."""
        job = (models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.ASSESS)
               .order_by('-created_at', '-pk').first())
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.RUNNING, finished_at=None, result={},
                                                    started_at=timezone.now() - timedelta(seconds=3600))
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.CANCELLED)


# --- parity-r2-2 with Corti alone (I1) --------------------------------------------------------------------------------

@override_settings(**LIVE)
class CortiOnlyCase(AssessedTwiceMixin, ArchiveMixin, TestCase):
    """Corti alone (Astra and Fable disabled, the settings' defaults), selecting only 45378 (the cecum sentence), so the
    polypectomy and the biopsy are left for a second review; the CMS PFS and MUE tables loaded through the importers."""

    def setUp(self):
        super().setUp()
        self.assertEqual(participants.configured(), ())
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('45378', REACHED)])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.load_pfs()
        self.load_mue()

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def create(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': COLON, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def decide(self, encounter_id):
        """The reviewer's decision on 45378, whichever the encounter offers (its endoscopic-base question leaves only a
        rejection)."""
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        proposal = next(p for p in detail['assessment']['proposals'] if p['code'] == '45378')
        if 'approve' in proposal['allowed_actions']:
            data = {'proposal_id': proposal['id'], 'action': 'approve',
                    'acknowledgement': review.ACKNOWLEDGEMENTS['human']}
        else:
            data = {'proposal_id': proposal['id'], 'action': 'reject', 'note': 'Synthetic rejection note.'}
        response = self.post(f'/api/encounters/{encounter_id}/decisions', data)
        self.assertEqual(response.status_code, 201, response.content)

    def failed_second_review(self, encounter_id):
        """A reviewer asks for a second review and its Corti request FAILS (HTTP 500): the assess its stage queues reads
        exactly the first assessment's inputs (the same context, routing and Corti run, and no second answer)."""
        failed = RawExchange(outcome='failed', sent=True, http_status=500, response_bytes=FAILED_BODY,
                             response_sha256=hashlib.sha256(FAILED_BODY).hexdigest(), latency_ms=3.0,
                             error='Corti answered HTTP 500 (synthetic).')
        with mock.patch.object(FakeProvider, 'send', lambda provider, request, *, deadline_s: failed):
            response = self.post(f'/api/encounters/{encounter_id}/second-review', {})
            self.assertEqual(response.status_code, 201, response.content)
            drain()
        self.assertEqual([(run.purpose, run.state) for run in models.ProviderRun.objects.filter(
            encounter_id=encounter_id).order_by('created_at')], [('primary', 'succeeded'), ('second_review', 'failed')])

    def assert_the_same_inputs_kept_the_assessment(self, recorded, before, encounter_id):
        """The second assess read the same inputs with more passages retrieved (so the test is not vacuous), and the
        encounter holds exactly what it held before it."""
        self.assertEqual(len(recorded.calls), 1)
        call = recorded.calls[0]
        self.assertEqual([(entry['name'], entry['state']) for entry in call['participants']],
                         [('astra', 'not_configured'), ('fable', 'not_configured')])
        first = models.Assessment.objects.get(pk=before['current'])
        self.assertGreater(passage_count(call['retrieval']), passage_count(first.retrieval))
        self.assertEqual(call['returned'], before['current'])
        self.assertEqual(self.holdings(encounter_id), before)


class CortiOnlyRepersistTests(CortiOnlyCase):
    """A reviewer decides 45378; then the passages are imported; then an assess reads exactly the first assessment's
    inputs again: the round-4 head's answer, one assessment with everything where it was."""

    def test_a_failed_second_review_after_the_passages_were_imported_keeps_the_recorded_assessment(self):
        encounter_id = self.create()
        self.decide(encounter_id)
        before = self.holdings(encounter_id)
        self.assertEqual((before['assessments'], before['decisions'], before['created']), (1, 1, 1))
        self.assertGreater(import_passages(), 0)
        recorded = Persisted(self)
        self.failed_second_review(encounter_id)
        self.assert_the_same_inputs_kept_the_assessment(recorded, before, encounter_id)

    def test_a_resume_after_the_stale_sweep_keeps_the_recorded_assessment(self):
        encounter_id = self.create()
        self.decide(encounter_id)
        before = self.holdings(encounter_id)
        self.kill_after_persisting(encounter_id)
        self.assertGreater(import_passages(), 0)
        recorded = Persisted(self)
        response = self.post(f'/api/encounters/{encounter_id}/resume', {})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assert_the_same_inputs_kept_the_assessment(recorded, before, encounter_id)

    def test_a_round_4_row_is_the_same_assessment_as_its_identical_reassessment(self):
        """An assessment as migration 0007 leaves one the round-4 release recorded (participants and retrieval both
        []), even with the passages imported before it: its identical re-assessment is that assessment."""
        self.assertGreater(import_passages(), 0)
        encounter_id = self.create()
        with connection.cursor() as cursor:
            cursor.execute("UPDATE studio_assessment SET participants='[]'::jsonb, retrieval='[]'::jsonb")
        self.decide(encounter_id)
        before = self.holdings(encounter_id)
        recorded = Persisted(self)
        self.failed_second_review(encounter_id)
        self.assert_the_same_inputs_kept_the_assessment(recorded, before, encounter_id)

    def test_control_the_passages_imported_first(self):
        """The control both trees agree on: nothing between the two assesses changed."""
        self.assertGreater(import_passages(), 0)
        encounter_id = self.create()
        self.decide(encounter_id)
        before = self.holdings(encounter_id)
        recorded = Persisted(self)
        self.failed_second_review(encounter_id)
        self.assertEqual(recorded.calls[0]['retrieval'],
                         models.Assessment.objects.get(pk=before['current']).retrieval)
        self.assertEqual(self.holdings(encounter_id), before)


def stand_in():
    """Another row for one of the inputs _same_assessment compares (it reads only the primary key)."""
    return SimpleNamespace(pk=uuid.uuid4())


class SameAssessmentMixin:
    def common(self, assessment):
        return (assessment, assessment.sha256, assessment.revision, assessment.context, assessment.routing,
                assessment.provider_run, assessment.second_run)

    def assert_round_4_inputs_decide(self, assessment, record):
        """Each input the round-4 head compared still decides it, whatever is recorded beside the result."""
        common = self.common(assessment)
        self.assertTrue(review._same_assessment(*common, record, []))
        for position, other in ((1, '0' * 64), (2, stand_in()), (3, stand_in()), (4, stand_in()), (5, stand_in()),
                                (6, stand_in())):
            changed = list(common)
            changed[position] = other
            self.assertFalse(review._same_assessment(*changed, record, []), position)
        self.assertFalse(review._same_assessment(None, *common[1:], record, []))


@override_settings(**LIVE)
class CortiOnlySameAssessmentTests(SameAssessmentMixin, CortiOnlyCase):
    """review._same_assessment with no model participant configured: exactly the round-4 head's comparison (I1)."""

    def test_the_record_beside_the_result_never_decides_it(self):
        assessment = models.Assessment.objects.get(pk=self.holdings(self.create())['current'])
        common = self.common(assessment)
        self.assertEqual([(entry['name'], entry['state']) for entry in assessment.participants],
                         [('astra', 'not_configured'), ('fable', 'not_configured')])
        other_retrieval = [{'code': '45378', 'passages': [{'passage_key': 'synthetic'}]}]
        self.assertTrue(review._same_assessment(*common, assessment.participants, assessment.retrieval))
        self.assertTrue(review._same_assessment(*common, assessment.participants, other_retrieval))
        self.assertTrue(review._same_assessment(*common, assessment.participants, None))
        reworded = [dict(entry, reason='Not configured on this installation (another wording).')
                    for entry in assessment.participants]
        self.assertTrue(review._same_assessment(*common, reworded, other_retrieval))
        # a row the round-4 release recorded (migration 0007: participants [], retrieval [])
        assessment.participants, assessment.retrieval = [], []
        self.assertTrue(review._same_assessment(*common, jobs_records(), other_retrieval))
        self.assert_round_4_inputs_decide(assessment, jobs_records())

    def test_a_participant_recorded_on_either_side_is_compared(self):
        """Fail closed: a record that names a configured participant on either side is compared by its runs."""
        assessment = models.Assessment.objects.get(pk=self.holdings(self.create())['current'])
        common = self.common(assessment)
        configured = [dict(jobs_records()[0], state='failed', run=str(uuid.uuid4())), jobs_records()[1]]
        self.assertFalse(review._same_assessment(*common, configured, assessment.retrieval))
        assessment.participants = configured
        self.assertFalse(review._same_assessment(*common, jobs_records(), assessment.retrieval))
        self.assertTrue(review._same_assessment(*common, configured, assessment.retrieval))
        for malformed in ('not a list', [['astra', 'not_configured']], [None], {'name': 'astra'}):
            assessment.participants = malformed
            self.assertFalse(review._same_assessment(*common, jobs_records(), []), malformed)


def jobs_records():
    """The participants record of an assess with no model participant configured (I1: 'not configured')."""
    return [jobs.not_configured_record(name) for name in participants.PARTICIPANTS]


# --- parity-r2-2 with participants configured (HARNESS.md 12.3) -------------------------------------------------------

@override_settings(**LIVE, **BOTH)
class ConfiguredRepersistTests(AssessedTwiceMixin, ArchiveMixin, HarnessCase):
    """Astra and Fable configured (the pipeline tests' fakes) and both of their first requests failed, so assess #1 owes
    no peer stage and is the final assessment (I10). The same assess, resumed after the stale sweep with the passages
    imported in between, reads the same participant runs: it is the same assessment."""

    def setUp(self):
        super().setUp()
        for adapter in self.adapters.values():
            adapter.outcome = 'failed'
        self.load_pfs()
        self.load_mue()

    def test_a_resume_after_the_stale_sweep_keeps_the_recorded_final_assessment(self):
        encounter_id = self.create()
        drain()
        self.assertEqual([(r['name'], r['state']) for r in self.records(encounter_id).values()],
                         [('astra', 'failed'), ('fable', 'failed')])
        assessment = self.encounter(encounter_id).current_assessment
        self.assertTrue(review.is_final(assessment))
        proposal = assessment.proposals.get(code='99213')
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': str(proposal.pk), 'action': 'reject', 'note': 'Synthetic rejection note.'})
        self.assertEqual(response.status_code, 201, response.content)
        before = self.holdings(encounter_id)
        self.kill_after_persisting(encounter_id)
        self.assertGreater(import_passages(), 0)
        recorded, sent = Persisted(self), (len(self.adapters['astra'].sent), len(self.adapters['fable'].sent))
        self.assertEqual(sent, (1, 1))
        response = self.post(f'/api/encounters/{encounter_id}/resume', {})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), sent)
        self.assertEqual(len(recorded.calls), 1)
        call = recorded.calls[0]
        self.assertEqual([(entry['name'], entry['state'], entry['run']) for entry in call['participants']],
                         [(entry['name'], entry['state'], entry['run']) for entry in assessment.participants])
        self.assertGreater(passage_count(call['retrieval']), passage_count(assessment.retrieval))
        self.assertEqual(call['returned'], before['current'])
        self.assertEqual(self.holdings(encounter_id), before)


@override_settings(**LIVE, **BOTH)
class ConfiguredSameAssessmentTests(SameAssessmentMixin, HarnessCase):
    """review._same_assessment while a model participant is configured, on a final assess #2 (both participants read,
    both peer reviews read): the participant runs each entry names decide it with the round-4 inputs, and nothing else
    recorded beside the result does - never the retrieval traces."""

    def final(self):
        encounter_id = self.create()
        drain()
        assessment = self.encounter(encounter_id).current_assessment
        self.assertEqual(jobs.assessment_phase(assessment), 2)
        self.assertTrue(all(entry.get('peer_run') for entry in assessment.participants))
        return assessment

    def test_the_participant_runs_decide_it_never_the_retrieval(self):
        assessment = self.final()
        common, record = self.common(assessment), assessment.participants
        self.assertTrue(review._same_assessment(*common, record, assessment.retrieval))
        other_retrieval = [{'code': '99213', 'passages': [{'passage_key': 'synthetic'}]}]
        self.assertTrue(review._same_assessment(*common, record, other_retrieval))
        self.assertTrue(review._same_assessment(*common, record, None))
        # what an entry records about a run it names, beside the run itself, is not an input of its own
        described = [dict(entry, reason='Another wording.', exchanges=9, tool_calls=9, unverified_quotes=9,
                          reading_sha256='f' * 64, frozen=[['revision', '0' * 64]], codes=[], not_coded=[],
                          peer_reason='Another wording.', peer_sha256='e' * 64) for entry in record]
        self.assertTrue(review._same_assessment(*common, described, []))
        self.assert_round_4_inputs_decide(assessment, record)

    def test_another_run_or_phase_is_another_assessment(self):
        assessment = self.final()
        common, record = self.common(assessment), assessment.participants
        for key in ('run', 'peer_run'):
            for position in range(len(record)):
                changed = [dict(entry) for entry in record]
                changed[position][key] = str(uuid.uuid4())
                self.assertFalse(review._same_assessment(*common, changed, assessment.retrieval), (key, position))
                changed[position][key] = None
                self.assertFalse(review._same_assessment(*common, changed, assessment.retrieval), (key, position))
        for key in ('state', 'peer_state'):
            changed = [dict(entry, **{key: 'refused'}) for entry in record]
            self.assertFalse(review._same_assessment(*common, changed, assessment.retrieval), key)
        # assess #1's record of the same phase-1 runs (no peer review) is not assess #2's
        first = [{k: v for k, v in entry.items() if not k.startswith('peer_')} for entry in record]
        self.assertFalse(review._same_assessment(*common, first, assessment.retrieval))
        self.assertFalse(review._same_assessment(*common, record[:1], assessment.retrieval))
        self.assertFalse(review._same_assessment(*common, jobs_records(), assessment.retrieval))
        for malformed in ('not a list', [['astra', 'read']], [None], record[0]):
            self.assertFalse(review._same_assessment(*common, malformed, assessment.retrieval), malformed)
            assessment.participants = malformed
            self.assertFalse(review._same_assessment(*common, record, assessment.retrieval), malformed)
            assessment.participants = record
