"""Refutation round 2, R2-TRUTH (HARNESS.md 5-7, 11.1-11.3, 12.6, 12.7; I4): what the page, the API, the owner's trace and
the reports state about the participants' positions and references, reference validation, a retrieval that failed,
the reviewer's confirmations and a run's estimated cost must be true of the record.

Synthetic data only; nothing is sent. The encounters are carried through the real pipeline (tests.test_harness2_pipeline:
ScriptedCorti, the real replay adapters and tool loop with CPT Studio's CMS tool executor, the readers, the engine, the
API and the report renderers), as the round's verifiers reproduced each finding.
"""
import json
from types import SimpleNamespace

from django.test import Client, override_settings

from studio import jobs, models, reports, review, serializers
from tests.support import factories as f
from tests.test_harness2_pipeline import TWO_EXTENTS, ColonCase
from tests.test_pipeline_api import drain


def _proposal(detail, code):
    return next(item for item in detail['assessment']['proposals'] if item['code'] == code)


# --- truth-2: a code first proposed in peer review is never said to be one its proposer did not propose ----------------

PEER_ONLY = 'Fable did not propose this code in its first reading. It proposed it after peer review.'


class PeerProposedPositionTests(ColonCase):
    """The default colon chain: Fable's peer review adds 45378 (support proposed_by ['fable'], phases {'fable':
    'peer_review'}). participant_positions reads the frozen first readings, so its position there is 'not_proposed' -
    and its detail says that is its first reading's, and that it proposed the code after peer review, in the API and in
    the owner's reconciliation table alike (refutation round 2, truth-2: both said "Fable did not propose this code.")."""

    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, f.user('owner_r2truth'), role=models.Membership.OWNER)

    def test_its_proposer_is_never_said_not_to_have_proposed_a_code_it_proposed_after_peer_review(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        added = self.encounter(encounter_id).current_assessment.proposals.get(code='45378')
        self.assertEqual((added.support.get('proposed_by'), added.support.get('phases')),
                         (['fable'], {'fable': 'peer_review'}))
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        positions = _proposal(detail, '45378')['participant_positions']
        self.assertEqual(positions['fable'], {'position': 'not_proposed', 'detail': PEER_ONLY, 'quote': ''})
        # a participant that proposed it in neither phase says so as before
        self.assertEqual(positions['astra'], {'position': 'not_proposed', 'detail': 'Astra did not propose this code.',
                                              'quote': ''})
        owner = Client()
        owner.force_login(self.owner)
        trace = owner.get(f'/api/encounters/{encounter_id}/trace').json()
        row = next(item for item in trace['reconciliation'] if item['code'] == '45378')
        self.assertEqual((row['proposed_by'], row['positions']['fable']['detail']), (['fable'], PEER_ONLY))
        # a code a first reading proposed keeps its first reading's own wording
        self.assertEqual(_proposal(detail, '45385')['participant_positions']['fable']['detail'],
                         'Fable proposed this code with evidence located in the document.')

    def test_each_first_reading_position_says_it_is_the_first_reading_s_beside_a_later_proposal(self):
        later = SimpleNamespace(code='45378', support={'proposed_by': ['astra', 'fable'],
                                                       'phases': {'astra': 'peer_review', 'fable': 'peer_review'}})
        records = [{'name': 'astra', 'state': 'read', 'codes': [{'code': '45378', 'quote': ''}], 'not_coded': []},
                   {'name': 'fable', 'state': 'read', 'codes': [],
                    'not_coded': [{'code': '45378', 'reason': 'not_performed_at_this_encounter', 'quote': 'Q.'}]}]
        positions = review.participant_positions(later, records)
        self.assertEqual(positions['astra'], {
            'position': 'proposed', 'quote': '',
            'detail': 'Astra proposed this code in its first reading; none of its quotes was found in the document. '
                      'It proposed it again after peer review.'})
        self.assertEqual(positions['fable'], {
            'position': 'advised_not_to_code', 'quote': 'Q.',
            'detail': 'Fable advised not to code it in its first reading: not performed at this encounter. It '
                      'proposed it after peer review.'})
        # an independent proposer, and a record with no phases (harness@1), read exactly as before
        for support in ({'proposed_by': ['astra'], 'phases': {'astra': 'independent'}}, {}, None):
            plain = review.participant_positions(SimpleNamespace(code='45378', support=support), records)
            self.assertEqual(plain['astra']['detail'], 'Astra proposed this code; none of its quotes was found in the '
                                                       'document.')
            self.assertEqual(plain['fable']['detail'], 'Fable advised not to code it: not performed at this encounter.')


# --- truth-3: reference validation never says codes were checked against the CMS files when no file applied ----------

NOT_CONNECTED = list(review.NOT_CONNECTED)
NO_DATE = TWO_EXTENTS.replace('Date of service: 2026-10-14\n', '')
OUTSIDE = TWO_EXTENTS.replace('Date of service: 2026-10-14', 'Date of service: 2025-03-02')  # before every release held
NO_SOURCE_NO_DATE = ('No code was checked against the CMS reference files: no service date is established for this '
                     'encounter, so no dated CMS reference file applies.')
NO_SOURCE_FOR_DATE = ('No code was checked against the CMS reference files: no installed CMS reference file applies '
                      'to the service date, {date}.')


class ReferenceValidationTruthMixin:
    """harness.reference_validation is 'done', with its codes counted as checked against the CMS reference files, only
    when an installed CMS reference file applied to the assessment's service date (Assessment.reference_sources, the
    engine's record of the lookup the retrieval traced); when none did - no service date established, or none covering
    it - it is 'not_verified', counts no code and says why (refutation round 2, truth-3: "Done - 2 codes checked
    against the CMS reference files" beside cards whose every CMS check was "not verified")."""

    def block(self, encounter_id):
        return self.client.get(f'/api/encounters/{encounter_id}').json()['harness']['reference_validation']

    def assertNoCodeChecked(self, encounter_id, detail):
        self.assertEqual(self.block(encounter_id), {'state': 'not_verified', 'detail': detail, 'codes_checked': 0,
                                                    'passages': 0, 'sources': [], 'not_connected': NOT_CONNECTED})
        self.assertEqual((serializers.NO_SOURCE_NO_DATE, serializers.NO_SOURCE_FOR_DATE),
                         (NO_SOURCE_NO_DATE, NO_SOURCE_FOR_DATE))
        for proposal in self.encounter(encounter_id).current_assessment.proposals.exclude(bucket='alternative'):
            statuses = {check['id']: check['status'] for check in proposal.checks}
            self.assertEqual((statuses['pfs.presence'], statuses['mue.units']), ('not_verified', 'not_verified'),
                             proposal.code)


class ReferenceValidationTruthTests(ReferenceValidationTruthMixin, ColonCase):
    def test_a_member_date_conflict_leaves_every_code_unchecked_and_the_row_says_so(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        block = self.block(encounter_id)  # the control: the documented date's release applied
        self.assertEqual((block['state'], block['detail'], block['codes_checked']), ('done', '', 3))
        self.assertTrue(block['passages'] and block['sources'], block)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-20'}).status_code, 201)
        drain()
        self.assertNoCodeChecked(encounter_id, NO_SOURCE_NO_DATE)


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyReferenceValidationTruthTests(ReferenceValidationTruthMixin, ColonCase):
    def test_no_documented_date(self):
        encounter_id = self.create(NO_DATE)
        drain()
        self.assertEqual(self.kinds(encounter_id), ['extract', 'analyze', 'predict', 'assess'])  # I1's chain
        self.assertNoCodeChecked(encounter_id, NO_SOURCE_NO_DATE)

    def test_a_documented_date_no_installed_release_covers(self):
        encounter_id = self.create(OUTSIDE)
        drain()
        self.assertNoCodeChecked(encounter_id, NO_SOURCE_FOR_DATE.format(date='2025-03-02'))

    def test_the_documented_date_s_release_applies(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        block = self.block(encounter_id)
        self.assertEqual((block['state'], block['detail'], block['codes_checked']), ('done', '', 2))


# --- truth-4: a retrieval that failed says what failed, never that the CMS checks did not run ------------------------

# The plan's shared wording (verify-harness-r2/REPAIR-PLAN.md): what failed is the record of the CMS facts and passages
# retrieved; each code's checks read the CMS facts before that (jobs.run_assess looks them up first), and stand.
RETRIEVAL_FAILED = ("Reference validation failed: CPT Studio could not record which CMS reference facts and passages it "
                    "retrieved for this assessment's codes ({error}, logged), so none is listed here. Each code's checks "
                    "read the CMS facts before that and stand as shown; retrieval only informs the reviewer and decides "
                    "no status, so the assessment stands as made.")
REFERENCE_FAILED = ("Reference validation failed: CPT Studio could not record which CMS reference facts and passages it "
                    "retrieved for this assessment's codes, so none is listed here. Each code's checks read the CMS facts "
                    "before that and stand as shown.")


def tamper_one_passage():
    """The integrity failure the passages module anticipates: a stored passage changed after import, which
    load_passages refuses ("does not match its sha256; it was changed after import")."""
    row = models.ReferencePassage.objects.order_by('pk').first()
    models.ReferencePassage.objects.filter(pk=row.pk).update(text=row.text + ' (changed after import)')


class RetrievalFailureWordingMixin:
    """A retrieval whose passages cannot be loaded is recorded as failed (HARNESS.md 5, refutation round 1 parity-1)
    after every proposal was checked against the CMS facts: its note, the API's detail, the page's fallbacks and the
    TXT say what failed and never that no proposal was checked (refutation round 2, truth-4)."""

    def assertSaysWhatFailed(self, encounter_id):
        note = RETRIEVAL_FAILED.format(error='ValueError')
        self.assertEqual(jobs.RETRIEVAL_FAILED.format(error='ValueError'), note)
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(final.retrieval, [{'code': '', 'service_date': '2026-10-14', 'facts': [], 'passages': [],
                                            'lookups': [], 'notes': [note], 'failed': True}])
        decidable = list(final.proposals.exclude(bucket='alternative'))
        self.assertTrue(decidable)
        for proposal in decidable:  # what the note says: each code's checks read the CMS facts, and stand
            statuses = {check['id']: check['status'] for check in proposal.checks}
            self.assertEqual((statuses['pfs.presence'], statuses['mue.units']), ('pass', 'pass'), proposal.code)
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['detail'], block['codes_checked']), ('failed', note, 0))
        text = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        self.assertIn(f'  - {note}', text.split('\nREFERENCE RETRIEVAL\n', 1)[1].split('\n\n', 1)[0].splitlines())
        self.assertIn('[PASS] pfs.presence', text)
        for served in (json.dumps(detail), text):
            self.assertNotIn('no proposal was checked against them', served)
        # the fallback where a failed entry carries no note says the same facts
        self.assertEqual(serializers.REFERENCE_FAILED, REFERENCE_FAILED)
        self.assertEqual(serializers.failure_note({'code': '', 'failed': True, 'notes': []}), REFERENCE_FAILED)

    def run_tampered(self):
        tamper_one_passage()
        encounter_id = self.create(TWO_EXTENTS)
        with self.assertLogs('studio.jobs', level='ERROR') as caught:
            drain()
        self.assertTrue(any('does not match its sha256' in line for line in caught.output), caught.output)
        return encounter_id


class RetrievalFailureWordingTests(RetrievalFailureWordingMixin, ColonCase):
    def test_with_both_participants_after_peer_review(self):
        encounter_id = self.run_tampered()
        self.assertEqual(self.client.get(f'/api/encounters/{encounter_id}').json()['harness']['phase'], 2)
        self.assertSaysWhatFailed(encounter_id)


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyRetrievalFailureWordingTests(RetrievalFailureWordingMixin, ColonCase):
    def test_corti_only(self):
        encounter_id = self.run_tampered()
        self.assertEqual(self.kinds(encounter_id), ['extract', 'analyze', 'predict', 'assess'])  # I1's chain
        self.assertSaysWhatFailed(encounter_id)


# --- truth-5: one reading of what the current assessment made of a confirmation, for the page and the reports --------

class ConfirmationEffectTests(ColonCase):
    """review.confirmation_effect states what the current assessment made of each reviewer-confirmed finding - read,
    or not read with why - and the API's confirmations (current_effect) and the reports' CONFIRMED FINDINGS ("Effect:")
    both state it. The round's s12: the extent of 45385 confirmed and read, then a member's conflicting date makes an
    assessment that lists it in confirmations.ignored (refutation round 2, truth-5: the page still said "The
    assessment reads it as documented by this passage")."""

    def detail(self, encounter_id):
        return self.client.get(f'/api/encounters/{encounter_id}').json()

    def verified_extent(self, encounter_id):
        detail = self.detail(encounter_id)
        proposals = {item['id']: item for item in detail['assessment']['proposals']}
        for question in detail['clarifications']:
            proposal = proposals.get(question['proposal_id'] or '')
            if question['fact'] == 'extent' and proposal and proposal['key'] == 'sel:0' and question['state'] == 'open':
                return question, next(item for item in question['candidates'] if item['verified'])
        raise AssertionError('no verified extent candidate for sel:0')

    def report_effects(self, encounter_id):
        text = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        lines = text.split('\nCONFIRMED FINDINGS\n', 1)[1].split('\n\n', 1)[0].splitlines()
        return [line[len('    Effect: '):] for line in lines if line.startswith('    Effect: ')]

    def test_what_the_current_assessment_made_of_a_confirmation_is_stated_once_for_the_page_and_the_reports(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        question, candidate = self.verified_extent(encounter_id)
        response = self.post(f'/api/encounters/{encounter_id}/clarifications/{question["id"]}/confirm',
                             {'candidate_id': candidate['id'], 'attestation': candidate['attestation']})
        self.assertEqual((response.status_code, response.json()['effect']), (201, 'reassessment'))
        made_before = {'state': 'not_read', 'detail': 'not read by this assessment, which was made before it'}
        self.assertEqual(response.json()['current_effect'], made_before)  # the assessment it was made on
        drain()
        read = {'state': 'read', 'detail': 'read by this assessment'}
        (served,) = self.detail(encounter_id)['confirmations']
        self.assertEqual((served['current_effect'], self.report_effects(encounter_id)), (read, [read['detail']]))
        self.assertEqual(self.encounter(encounter_id).current_assessment.proposals.get(key='sel:0').status, 'ready')
        # a member's date that conflicts with the document's: the next assessment does not read it, and says why
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-20'}).status_code, 201)
        drain()
        final = self.encounter(encounter_id).current_assessment
        (ignored,) = final.completeness['confirmations']['ignored']
        self.assertEqual(ignored['id'], served['id'])
        expected = {'state': 'not_read', 'detail': f'not read by this assessment: {ignored["why"]}'}
        detail = self.detail(encounter_id)
        (served,) = detail['confirmations']
        self.assertEqual((served['current_effect'], self.report_effects(encounter_id)), (expected, [expected['detail']]))
        checks = {check['id']: check for check in detail['assessment']['encounter_checks']}
        self.assertEqual(checks['confirmations.ignored']['status'], 'warn')
        self.assertNotIn('confirmations.applied', checks)
        self.assertEqual(final.proposals.get(key='sel:0').status, 'needs_clarification')
        self.assertFalse(models.Decision.objects.exists())  # I4: a confirmation is no decision
