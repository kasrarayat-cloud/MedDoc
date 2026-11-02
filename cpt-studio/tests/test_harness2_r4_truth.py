"""Refutation round 4, R4-TRUTH (HARNESS.md 5, 7, 11.1, 12.6, 12.9, 12.11; I4, I9): what the page, the API, the owner's
trace and the reports state must be true of the record - a first reading's code with no quote found in the document,
whether or not its peer review then proposed it (truth-2) - and round 3's own repair left the rule's other half: one
account of one frozen first reading.

Each class reproduces one finding of the round (refute-harness-r4/findings.json, verified in
verify-harness-r4/results.json) through the real pipeline - the real jobs, engine, readers, tool executor and tool loop,
the vendors' HTTP replaced by scripted bytes in their own envelopes (tests.test_harness2_pipeline) - then the real API,
the real report renderers and the real app.js run by node. Synthetic data only; nothing is sent.
"""
import json
import re
from types import SimpleNamespace

from django.test import Client

from studio import models, review
from tests import test_harness2_pipeline as hp
from tests.support import factories as f
from tests.test_harness2_pipeline import BIOPSY, SNARE, TWO_EXTENTS
from tests.test_harness2_r2_wording import R2WordingCase, browser
from tests.test_pipeline_api import drain


def _owner(case, name):
    client = Client()
    client.force_login(f.member(case.ws, f.user(name), role=models.Membership.OWNER))
    return client


# --- truth-2: a first reading's code with no located quote is "not proposed" there, whatever peer review did --------

UNLOCATED = 'a hot snare removed it completely without any trouble at all'  # in no document: never located
# What the first reading's position says of a code it listed with no quote found in the document: the same sentence
# whether or not peer review then proposed the code (refutation round 4, truth-2), and where it did, one more sentence.
LISTED = ('Astra listed this code in its first reading, but none of its quotes was found in the document, so that '
          'reading did not propose it.')
LATER = ' It proposed it after peer review.'
# The card's positions (participantPositions: "<label> <position words>: <detail>").
POSITION_LINE = re.compile(r'Astra (proposed it|did not propose it|advised not to code it|gave no reading)\b')


class FirstReadingPositionTests(R2WordingCase):
    """Astra's frozen first reading lists 45385 with a quote the document does not hold (and 45380 on the biopsy).
    The engine counts no first-reading entry whose quotes were not found (refutation round 1, EV-2 = IND-3): Astra is
    not among 45385's proposers. Where its peer review proposes nothing, the card said "Astra proposed it: Astra
    proposed this code; none of its quotes was found in the document." beside "Proposed by: Corti, Fable (independent
    reading)"; where its peer review proposed 45385 on the snare passage, the same frozen reading was "not proposed"
    there (refutation round 4, truth-2: one frozen reading, two positions). It is now "not proposed" in both, in one
    sentence, and only the variant whose peer review proposed it says so after it."""

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', UNLOCATED), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]

    def run_variant(self, peer_codes=None):
        """One encounter of TWO_EXTENTS through the pipeline; ``peer_codes``, what Astra's peer review proposes (None:
        the peer loop already scripted)."""
        if peer_codes is not None:
            self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=peer_codes), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        self.assertEqual(detail['harness']['phase'], 2)
        [snare] = self.proposals(detail, '45385', bucket='selected')
        record = self.records(self.encounter(encounter_id).current_assessment)['astra']
        self.assertIn({'code': '45385', 'quote': ''}, record['codes'])  # the frozen first reading listed it, unlocated
        return encounter_id, detail, snare, record

    def card_positions(self, detail, proposal):
        lines = browser(f'visible(cardOf(page(), {json.dumps(proposal["id"])})).split("\\n")', detail)
        return [line for line in lines if POSITION_LINE.match(line)]

    def test_a_first_reading_s_unlocated_code_that_peer_review_did_not_propose_is_not_proposed(self):
        encounter_id, detail, snare, _ = self.run_variant([])
        # the record: Astra proposed 45385 in no phase (the engine names no proposer and no phase for it)
        self.assertEqual((snare['proposed_by'], snare['phases']), (['corti', 'fable'], {'fable': 'independent'}))
        self.assertEqual(snare['participant_positions']['astra'],
                         {'position': 'not_proposed', 'quote': '', 'detail': LISTED})
        self.assertEqual(self.card_positions(detail, snare), [f'Astra did not propose it: {LISTED}'])
        self.assertEqual(browser(f'statusLine(cardOf(page(), {json.dumps(snare["id"])}), "Proposed by")', detail),
                         'Corti, Fable (independent reading)')
        for said in self.card_positions(detail, snare):
            self.assertNotIn('Astra proposed', said)
        # the owner's trace reconciliation says the same
        trace = _owner(self, 'owner_r4truth2').get(f'/api/encounters/{encounter_id}/trace').json()
        (row,) = [item for item in trace['reconciliation'] if item['code'] == '45385'
                  and item['proposed_by'] == snare['proposed_by']]
        self.assertEqual(row['positions']['astra'], {'position': 'not_proposed', 'quote': '', 'detail': LISTED})
        # control: a located first reading keeps its own wording (Astra's 45380, Fable's 45385)
        [biopsy] = self.proposals(detail, '45380', bucket='selected')
        self.assertEqual(biopsy['participant_positions']['astra'],
                         {'position': 'proposed', 'quote': BIOPSY,
                          'detail': 'Astra proposed this code with evidence located in the document.'})
        self.assertEqual(snare['participant_positions']['fable']['detail'],
                         'Fable proposed this code with evidence located in the document.')

    def test_one_frozen_first_reading_gets_one_position_whatever_peer_review_did(self):
        # variant A: Astra's peer review proposes 45385 on the snare passage (refutation round 3, truth-2's case);
        # variant B, a second encounter of the same note in the same workspace: its peer review proposes nothing
        self.adapters['astra'].peer_loops = [[hp.answered('astra', hp.peer_answer(codes=[('45385', SNARE)]), number=2)],
                                             [hp.answered('astra', hp.peer_answer(), number=2)]]
        first, detail_a, snare_a, record_a = self.run_variant()
        self.assertEqual((snare_a['proposed_by'], snare_a['phases'].get('astra')),
                         (['corti', 'astra', 'fable'], 'peer_review'))
        second, detail_b, snare_b, record_b = self.run_variant()
        self.assertNotIn('astra', snare_b['phases'])
        self.assertEqual(self.adapters['astra'].peer_loops, [])  # each variant's peer review was its own loop
        # the same frozen first reading: variant B's first reading reuses variant A's retained run, recorded identically
        (retained,) = self.runs_of(first, 'astra', 'independent')
        (reuse,) = self.runs_of(second, 'astra', 'independent')
        self.assertEqual(reuse.reused_from_id, retained.pk)
        self.assertEqual((record_a['reading_sha256'], record_a['codes']), (record_b['reading_sha256'], record_b['codes']))
        position_a, position_b = (snare_a['participant_positions']['astra'], snare_b['participant_positions']['astra'])
        self.assertEqual((position_a['position'], position_a['quote']), (position_b['position'], position_b['quote']))
        self.assertEqual((position_a['detail'], position_b['detail']), (LISTED + LATER, LISTED))
        self.assertEqual(self.card_positions(detail_a, snare_a), [f'Astra did not propose it: {LISTED}{LATER}'])
        self.assertEqual(self.card_positions(detail_b, snare_b), [f'Astra did not propose it: {LISTED}'])

    def test_every_record_reads_a_first_reading_s_unlocated_code_as_not_proposed(self):
        # with no phase recorded for the participant (an independent proposer named by another quote, no phases at all,
        # a harness@1 record), and with one: the first reading's entry with no located quote proposed nothing there
        records = [{'name': 'astra', 'state': 'read', 'codes': [{'code': '45385', 'quote': ''}], 'not_coded': []}]
        for support in ({'proposed_by': ['corti', 'fable'], 'phases': {'fable': 'independent'}},
                        {'proposed_by': ['astra'], 'phases': {'astra': 'independent'}}, {}, None):
            with self.subTest(support=support):
                position = review.participant_positions(SimpleNamespace(code='45385', support=support), records)
                self.assertEqual(position['astra'], {'position': 'not_proposed', 'quote': '', 'detail': LISTED})
        later = review.participant_positions(SimpleNamespace(code='45385', support={
            'proposed_by': ['astra'], 'phases': {'astra': 'peer_review'}}), records)
        self.assertEqual(later['astra'], {'position': 'not_proposed', 'quote': '', 'detail': LISTED + LATER})
        # control: a located quote is a proposal, with or without a later phase
        located = [{'name': 'astra', 'state': 'read', 'codes': [{'code': '45385', 'quote': SNARE}], 'not_coded': []}]
        plain = review.participant_positions(SimpleNamespace(code='45385', support={}), located)
        self.assertEqual(plain['astra'], {'position': 'proposed', 'quote': SNARE,
                                          'detail': 'Astra proposed this code with evidence located in the document.'})
