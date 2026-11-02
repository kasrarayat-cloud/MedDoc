"""Refutation round 2, R2-TRUTH (HARNESS.md 5-7, 11.1-11.3, 12.6, 12.7; I4): what the page, the API, the owner's trace and
the reports state about the participants' positions and references, reference validation, a retrieval that failed,
the reviewer's confirmations and a run's estimated cost must be true of the record.

Synthetic data only; nothing is sent. The encounters are carried through the real pipeline (tests.test_harness2_pipeline:
ScriptedCorti, the real replay adapters and tool loop with CPT Studio's CMS tool executor, the readers, the engine, the
API and the report renderers), as the round's verifiers reproduced each finding.
"""
from types import SimpleNamespace

from django.test import Client

from studio import models, review
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
