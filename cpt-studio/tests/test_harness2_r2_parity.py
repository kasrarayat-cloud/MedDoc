"""Refutation round 2, R2-PARITY (HARNESS.md 9, I1; the round-2 repair plan's D6): Corti-only parity where the harness
and the round-4 head (80f2f2dc8) could differ and no earlier proof looked.

parity-r2-1. I1's one declared exception: the licence note studio.reference.importers.LICENSE_NOTE writes on every CMS
source it imports was corrected after the round-4 head (the owner's 11.6 correction, ad025537c), and the installer's
license-note phase rewrites the installed rows, so every Corti-only assessment listing such a source differs from the
round-4 head's in those entries and in its sha256. No earlier proof loaded a source through the importers (the engine
parity test builds its sources in memory, the pipeline tests by hand, H1 reads the retained fixtures' sources), so none
could see it. Here the CMS tables are loaded through the importers and both digests are pinned: with the note reset to
the round-4 text, the round-4 head's; with the importer's own, the harness's.

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
import ast
import hashlib
import json
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, participants, review
from studio.reference import importers, passages
from studio.types import RawExchange
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support.operator import OperatorReads
from tests.test_harness_pipeline import BOTH, HarnessCase, installed_reader_labels, served_reader_labels
from tests.test_pipeline_api import FakeProvider, RecordedInterpretation, drain
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
class CortiOnlyCase(OperatorReads, AssessedTwiceMixin, ArchiveMixin, TestCase):
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
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
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


@applied
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


@applied
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
class ConfiguredRepersistTests(RecordedInterpretation, OperatorReads, AssessedTwiceMixin, ArchiveMixin, HarnessCase):
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


@applied
@override_settings(**LIVE, **BOTH)
class ConfiguredSameAssessmentTests(OperatorReads, SameAssessmentMixin, HarnessCase):
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


# --- parity-r2-1: I1's one declared exception, the CMS sources' licence note -----------------------------------------

# The note the round-4 head's importer wrote on every CMS source it imported (80f2f2dc8, studio/reference/importers.py),
# which the owner's 11.6 correction (ad025537c) replaced; the installer's license-note phase rewrites the installed rows
# that hold it (ops/install.py, LICENSE_NOTE_OLD).
ROUND_4_LICENSE_NOTE = ('CPT codes are copyright the American Medical Association; descriptors are not imported or '
                        'displayed. Used for internal synthetic evaluation only; commercial CPT use requires an AMA '
                        'license.')
# The sha256 of the Corti-only assessment of COLON, Corti selecting 45385 (the hot snare) and 45378 (the cecum
# sentence), the CMS PFS and MUE tables loaded through the importers from the synthetic fixtures: as an export of the
# round-4 head made it with its own note (measured by the refutation lens, by its verifier and again for this repair),
# and as the harness makes it with the importer's own note. The round-4 head makes HEAD_SHA256 with the harness's note,
# and the harness ROUND_4_SHA256 with the round-4 note: the note is the only difference.
ROUND_4_SHA256 = '07315c45fbdaed9668696efea28795e9e29f0ac4be8c72548b15ffa3832ee9ff'
HEAD_SHA256 = 'c961e7e69c35ad1e9b22b5b4b88d4284fb649145a17d9dd945a2638a0246d3e7'
# The core repair (2026-11-03) moved the routing, inventory and engine labels by one (feace7606), and the assessment
# records them, so both digests move with the labels alone: with the four labels put back to installed 41e03656df61's
# (installed_reader_labels) this head makes exactly the two above - the I1 proof stands - and at its own labels these.
CORE_REPAIR_HEAD_SHA256 = 'a71679b8af53c478c99b56a58a5a0cc020f7e985bceb5415127eae8f92cc6687'
CORE_REPAIR_ROUND_4_SHA256 = 'ab443cf120172659e3a0ddcd3e8dac9a9ec403dca8166fc97dd07475622d3f69'
# The harness repair (2026-11-05) moved the three labels by one again: with them put back to installed b0dc3446c64c's
# (served_reader_labels) this head makes exactly the two above, and at its own labels these.
HARNESS_REPAIR_HEAD_SHA256 = '04acca1307703c13ad36c7c60468853cae183167db411f35d30c82f9c8076a16'
HARNESS_REPAIR_ROUND_4_SHA256 = 'b9687931fc58141c70fd3c67f2a355403ea55ec6047e1f9b85eddf845a0a1ae5'
# Harness repair 3 (2026-11-06) moved the three labels by one again: with them put back to installed e6d451f03d86's
# (harness_repair_reader_labels) this head makes exactly the two above, and at its own labels these.
HARNESS_REPAIR_3_HEAD_SHA256 = 'b3add93bbc2ad3991c1bccb8d91bc741f9c1ad0042b20cc0a1fdf12d36b51ad6'
HARNESS_REPAIR_3_ROUND_4_SHA256 = '3ff6ec5e45479d45f396b81fda06ec70229f3a49ad270831d99c003d0e4bde97'
# The completion repair (2026-11-06) moved the routing, inventory, engine and catalogue labels: with them put back to
# installed fd8040d71e44's (completion_reader_labels) this head makes exactly the two above, and at its own labels these.
COMPLETION_HEAD_SHA256 = '6a631b87128532ea8b3254e1d8f287428f22378e76ea7c9540692c77dc07e6a1'
COMPLETION_ROUND_4_SHA256 = 'a850ca98983b71589a6cc1cea3343eeee3fa9e3daee9af540276c7144d6b41b1'
# The walk round (2026-11-07) moved the routing and engine labels (the inventory is installed's again: its two repairs
# were dropped under the two-cycle rule): with them put back to installed 6f306af1b030's (walk_round_reader_labels)
# this head makes exactly the two above, and at its own labels these.
WALK_ROUND_HEAD_SHA256 = '0a979442f7e49a52cd6d365d5fb50279ee02f0dca0f41d9bb52d528ab78ef984'
WALK_ROUND_ROUND_4_SHA256 = 'f2272ea57ad68313abf2ec498aaf309870845f85bb35133ead947b66311c8e5a'
# The structure round (2026-11-08) moved the routing and inventory labels (and the inventory's source): with them put
# back to installed aeae34bebbe5's (structure_round_reader_labels) this head makes exactly the two above, and at its own
# labels these.
STRUCTURE_ROUND_HEAD_SHA256 = '1eb4c2ae20726b6c877dada9c81c342d32daf7de0ceb51b01c5cc756c37e9a1a'
STRUCTURE_ROUND_ROUND_4_SHA256 = '7c05d952dd720e6ecc745e6e6ba4f50d7ba6b0a23d5cbb763fa7d7f8362c893b'
IMPORTED = ('cms-mue-practitioner-2026q4', 'cms-pfs-rvu26d')
SELECTIONS = (('45385', SNARE), ('45378', REACHED))
# What a proposal row and a clarification row hold, compared field by field (every field but its ids and its row).
PROPOSAL_FIELDS = ('key', 'bucket', 'code', 'code_kind', 'family', 'profile_version', 'status', 'exclusion_reason',
                   'reinstatable', 'provider_display', 'evidence', 'rationale', 'checks', 'modifier_considerations',
                   'units', 'fingerprint', 'position', 'support')
CLARIFICATION_FIELDS = ('scope', 'family', 'fact', 'question', 'reason', 'state')
ASSESSMENT_FIELDS = ('profiles_version', 'engine_version', 'encounter_checks', 'unsupported', 'summary', 'services',
                     'completeness', 'participants')


@applied
@override_settings(**LIVE)
class ImportedReferenceParityTests(OperatorReads, ArchiveMixin, TestCase):
    """I1's one declared exception, pinned through the importers: Corti alone on COLON, the CMS PFS and practitioner
    MUE tables loaded by studio.reference.importers. Re-pin only with a declaration of the change (HARNESS.md 9): a
    moved digest is a change to every Corti-only assessment on an installed system."""

    def setUp(self):
        super().setUp()
        self.assertEqual(participants.configured(), ())
        self.provider = FakeProvider(selections=list(SELECTIONS))
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        sources = [self.load_pfs(), self.load_mue()]
        self.assertEqual(sorted(source.key for source in sources), list(IMPORTED))
        self.assertEqual({source.license_note for source in sources}, {importers.LICENSE_NOTE})

    def assess(self, note=None):
        """The Corti-only assessment of COLON in a workspace of its own, the imported sources' note set to ``note``
        first when one is given."""
        if note is not None:
            self.assertEqual(models.ReferenceSource.objects.filter(key__in=IMPORTED).update(license_note=note), 2)
        client = Client(enforce_csrf_checks=False)
        client.force_login(f.member(f.workspace()))
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post('/api/encounters', {'text': COLON, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        assessment = models.Encounter.objects.get(pk=response.json()['id']).current_assessment
        self.assertEqual([(p.key, p.code, p.bucket) for p in assessment.proposals.order_by('position')],
                         [('sel:0', '45385', 'selected'), ('sel:1', '45378', 'selected')])
        return assessment

    def notes(self, assessment):
        return {entry['key']: entry['license_note'] for entry in assessment.reference_sources}

    def test_with_the_importers_note_it_is_the_declared_head_digest(self):
        assessment = self.assess()
        self.assertEqual(assessment.sha256, STRUCTURE_ROUND_HEAD_SHA256)
        notes = self.notes(assessment)
        self.assertEqual({key: notes.pop(key) for key in IMPORTED}, dict.fromkeys(IMPORTED, importers.LICENSE_NOTE))
        self.assertTrue(notes)  # the AMA CPT and NCCI PTP entries: their own notes, neither of the two
        self.assertFalse({importers.LICENSE_NOTE, ROUND_4_LICENSE_NOTE} & set(notes.values()), notes)

    def test_with_the_round_4_note_it_is_the_round_4_heads_assessment(self):
        assessment = self.assess(ROUND_4_LICENSE_NOTE)
        self.assertEqual(assessment.sha256, STRUCTURE_ROUND_ROUND_4_SHA256)
        self.assertEqual({key: self.notes(assessment)[key] for key in IMPORTED},
                         dict.fromkeys(IMPORTED, ROUND_4_LICENSE_NOTE))

    def test_at_the_structure_round_installed_labels_the_head_makes_both_walk_round_digests_exactly(self):
        # the structure round (2026-11-08): the labels apart, this head reads this colonoscopy as installed aeae34bebbe5
        # does
        from tests.test_harness_pipeline import structure_round_reader_labels
        with structure_round_reader_labels():
            self.assertEqual((self.assess().sha256, self.assess(ROUND_4_LICENSE_NOTE).sha256),
                             (WALK_ROUND_HEAD_SHA256, WALK_ROUND_ROUND_4_SHA256))

    def test_at_the_walk_round_installed_labels_the_head_makes_both_completion_digests_exactly(self):
        # the walk round (2026-11-07): the labels apart, this head reads this colonoscopy as installed 6f306af1b030 does
        from tests.test_harness_pipeline import walk_round_reader_labels
        with walk_round_reader_labels():
            self.assertEqual((self.assess().sha256, self.assess(ROUND_4_LICENSE_NOTE).sha256),
                             (COMPLETION_HEAD_SHA256, COMPLETION_ROUND_4_SHA256))

    def test_at_the_completion_installed_labels_the_head_makes_both_harness_repair_3_digests_exactly(self):
        # the completion repair (2026-11-06): the labels apart, this head reads this colonoscopy as installed
        # fd8040d71e44 does
        from tests.test_harness_pipeline import completion_reader_labels
        with completion_reader_labels():
            self.assertEqual((self.assess().sha256, self.assess(ROUND_4_LICENSE_NOTE).sha256),
                             (HARNESS_REPAIR_3_HEAD_SHA256, HARNESS_REPAIR_3_ROUND_4_SHA256))

    def test_at_the_harness_repairs_labels_the_head_makes_both_of_its_digests_exactly(self):
        # harness repair 3 (2026-11-06): the labels apart, this head reads this colonoscopy as served e6d451f03d86 does
        from tests.test_harness_pipeline import harness_repair_reader_labels
        with harness_repair_reader_labels():
            self.assertEqual((self.assess().sha256, self.assess(ROUND_4_LICENSE_NOTE).sha256),
                             (HARNESS_REPAIR_HEAD_SHA256, HARNESS_REPAIR_ROUND_4_SHA256))

    def test_at_the_served_labels_the_head_makes_both_core_repair_digests_exactly(self):
        # the harness repair (2026-11-05): the labels apart, this head reads this colonoscopy as served b0dc3446c64c does
        with served_reader_labels():
            self.assertEqual((self.assess().sha256, self.assess(ROUND_4_LICENSE_NOTE).sha256),
                             (CORE_REPAIR_HEAD_SHA256, CORE_REPAIR_ROUND_4_SHA256))

    def test_at_the_installed_labels_the_head_makes_both_declared_digests_exactly(self):
        # I1 (HARNESS.md): the labels apart, the core repair's head reads this colonoscopy as the round-4 head did
        with installed_reader_labels():
            self.assertEqual((self.assess().sha256, self.assess(ROUND_4_LICENSE_NOTE).sha256), (HEAD_SHA256, ROUND_4_SHA256))

    def test_the_note_is_the_only_difference(self):
        """Every proposal (its fingerprint included, so decisions carry by it as before), every question and every
        record of the result is the same, and the reference-source entries are once the note is mapped back."""
        harness = self.assess()
        round_4 = self.assess(ROUND_4_LICENSE_NOTE)
        self.assertEqual((harness.sha256, round_4.sha256),
                         (STRUCTURE_ROUND_HEAD_SHA256, STRUCTURE_ROUND_ROUND_4_SHA256))
        for name in ASSESSMENT_FIELDS:
            self.assertEqual(getattr(harness, name), getattr(round_4, name), name)
        mapped = [dict(entry, license_note=ROUND_4_LICENSE_NOTE) if entry['key'] in IMPORTED else entry
                  for entry in harness.reference_sources]
        self.assertNotEqual(harness.reference_sources, round_4.reference_sources)
        self.assertEqual(mapped, round_4.reference_sources)

        def rows(assessment):
            proposals = [{name: getattr(p, name) for name in PROPOSAL_FIELDS} for p in assessment.proposals.order_by(
                'position')]
            questions = sorted((tuple(str(getattr(c, name)) for name in CLARIFICATION_FIELDS),
                                c.proposal.key if c.proposal_id else '') for c in assessment.clarifications.all())
            return proposals, questions
        self.assertEqual(rows(harness), rows(round_4))
        self.assertTrue(rows(harness)[1])  # 45378's question about its endoscopic base is asked in both


class DeclaredExceptionTests(SimpleTestCase):
    """HARNESS.md 9 declares the exception ImportedReferenceParityTests pins (parity-r2-1: the difference was real and
    undeclared, so I1 claimed more than was true): I1 names the licence note, quotes the round-4 head's text and the
    importer's own, names both digests and this proof. And the installer's license-note phase replaces exactly the
    round-4 text with exactly the importer's (ops/install.py), so an installed system holds what I1 declares."""

    def i1(self):
        text = (Path(settings.BASE_DIR) / 'HARNESS.md').read_text(encoding='utf-8')
        start = text.index('- **I1 Corti-only parity.**')
        return ' '.join(text[start:text.index('- **I2 ', start)].split())

    def test_i1_declares_the_licence_note_as_its_one_exception(self):
        i1 = self.i1()
        for needed in ('`ReferenceSource.license_note`', '`studio.reference.importers.LICENSE_NOTE`', '`ad025537c`',
                       '`license-note`', f'"{ROUND_4_LICENSE_NOTE}"', f'"{importers.LICENSE_NOTE}"',
                       f'`{ROUND_4_SHA256[:12]}`', f'`{HEAD_SHA256[:12]}`', '`tests/test_harness2_r2_parity.py`'):
            self.assertIn(needed, i1)

    def test_the_installer_replaces_exactly_the_round_4_note_with_the_importers(self):
        tree = ast.parse((Path(settings.BASE_DIR) / 'ops' / 'install.py').read_text(encoding='utf-8'))
        found = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                 if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in ('LICENSE_NOTE_OLD', 'LICENSE_NOTE_NEW')}
        self.assertEqual(found, {'LICENSE_NOTE_OLD': ROUND_4_LICENSE_NOTE, 'LICENSE_NOTE_NEW': importers.LICENSE_NOTE})
        self.assertNotEqual(ROUND_4_LICENSE_NOTE, importers.LICENSE_NOTE)
