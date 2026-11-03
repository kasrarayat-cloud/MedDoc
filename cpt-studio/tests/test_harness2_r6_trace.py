"""Refutation round 6, R6-TRACE: the D12 account (HARNESS.md 11.1, 12.6, 12.9 truth-8, 12.12, 12.13 D12; I4, I9) -
"proposed" is said only of an entry with a located quote, entry by entry, on every surface that words one, and no
phrase is given two meanings.

- account-3: the engine's support['participants'] detail counted every entry of a code as one of its proposals - "Astra
  proposed 45385 2 times" beside one located entry - and said "again in peer review" of a peer-review entry none of
  whose quotes was found. It now counts only the entries that located a quote and names each other entry as a listing
  in its phase.

Each pipeline class runs the real pipeline (tests.test_harness2_pipeline: the real jobs, loop, tool executor, readers
and engine, the vendors' HTTP replaced by scripted bytes in their own envelopes), then the real API, the owner's trace,
the reports through the reports endpoint and the real app.js under node. Synthetic data only; nothing is sent.
"""
from django.test import SimpleTestCase

from studio import reports
from tests import test_harness2_pipeline as hp
from tests import test_harness_engine as he
from tests.test_harness2_pipeline import BIOPSY, LAND, SNARE, TWO_EXTENTS
from tests.test_harness2_r2_wording import R2WordingCase, browser
from tests.test_harness2_r4_truth import UNLOCATED, _block, _section
from tests.test_harness2_r5_account import UNLOCATED_DIAG, Surfaces, csv_rows
from tests.test_pipeline_api import drain

STATED_ONE = 'stated units 1; modifiers none; confidence high'
STATED_TWO = 'stated units 1, 1; modifiers none; confidence high'
ONE_PASSAGE = 'quoting the document verbatim in 1 passage.'
NOT_IN_TEXT = 'nowhere in this document at all, verbatim or otherwise'  # in no document: never located
PROPOSED_AFTER = 'proposed after peer review, never independent'
REPEATED = 'repeated in peer review; first proposed in its independent reading'
LISTED_IN_PEER = 'listed in peer review'
FOUND_LAND = f'“{LAND}” — found in the document (1 place)'
UNVERIFIED_DIAG = f'“{UNLOCATED_DIAG}” — unverified (not found); never used as evidence'
# the headings the owner's trace draws (app.js groupLabel)
HEADINGS = '[...app.traceView(data).matchAll(/<div class="evidence-label">([^<]*)<\\/div>/g)].map(match => match[1])'


# --- account-3: the engine counts as proposals only the entries that located a quote ----------------------------------

class PositionCountEngineTests(SimpleTestCase):
    """account-3 in the engine itself (tests.test_harness_engine's document and helpers): a participant that gave a
    code in more than one entry, some located and some not."""

    @staticmethod
    def detail(participants, value, name, *corti):
        result = he.run(he.COLON, he.corti(*corti), participants)
        return he.proposal(result, value).support['participants'][name]

    def test_a_first_reading_s_located_code_listed_again_in_peer_review_is_proposed_once(self):
        # the account lens's mirror: the first reading locates 45380, its peer review lists it with a quote not found
        colon = he.COLON
        astra = he.reviewed('astra', [he.code(colon, '45380', he.BIOPSY)],
                            he.peer('astra', additional=[he.code(colon, '45380', NOT_IN_TEXT)]))
        position = self.detail([astra], '45380', 'astra', ('45385', he.span(colon, he.SNARE)))
        self.assertEqual((position['position'], position['quote']), ('proposed', he.BIOPSY))
        self.assertEqual(position['detail'],
                         f'Astra proposed 45380 in its independent reading, and also listed it in peer review with no '
                         f'quote found verbatim in the document ({STATED_TWO}), {ONE_PASSAGE}')

    def test_a_first_reading_s_listing_that_peer_review_proposed_is_one_proposal(self):
        # falsegreen-5's variant A: the first reading lists 45385 with a quote not found, its peer review locates it
        colon = he.COLON
        astra = he.reviewed('astra', [he.code(colon, '45385', NOT_IN_TEXT)],
                            he.peer('astra', additional=[he.code(colon, '45385', he.SNARE)]))
        position = self.detail([astra], '45385', 'astra', ('45385', he.span(colon, he.SNARE)))
        self.assertEqual((position['position'], position['quote']), ('proposed', he.SNARE))
        self.assertEqual(position['detail'],
                         'Astra proposed 45385, listed in its independent reading with no quote found verbatim there, '
                         f'and proposed after peer review ({STATED_TWO}), {ONE_PASSAGE}')

    def test_two_entries_of_one_reading_one_located_are_one_proposal_and_one_listing(self):
        colon = he.COLON
        astra = he.read('astra', [he.code(colon, '45385', he.SNARE), he.code(colon, '45385', NOT_IN_TEXT)])
        position = self.detail([astra], '45385', 'astra', ('45385', he.span(colon, he.SNARE)))
        self.assertEqual(position['detail'],
                         'Astra proposed 45385 in its independent reading, and also listed it in its independent '
                         f'reading with no quote found verbatim in the document ({STATED_TWO}), {ONE_PASSAGE}')

    def test_two_entries_of_one_peer_review_one_located_are_one_proposal_and_one_listing(self):
        # account-4's input in the engine: Fable's peer review gives 45380 twice, located once
        colon = he.COLON
        fable = he.reviewed('fable', [he.code(colon, '45385', he.SNARE)], he.peer('fable', additional=[
            he.code(colon, '45380', he.BIOPSY), he.code(colon, '45380', NOT_IN_TEXT)]))
        position = self.detail([fable], '45380', 'fable', ('45385', he.span(colon, he.SNARE)))
        self.assertEqual(position['detail'],
                         'Fable proposed 45380 after peer review, not in its independent reading, and also listed it '
                         f'in peer review with no quote found verbatim in the document ({STATED_TWO}), {ONE_PASSAGE}')

    def test_located_entries_are_counted_and_listings_are_not(self):
        colon = he.COLON
        astra = he.reviewed('astra', [he.code(colon, '45380', he.BIOPSY), he.code(colon, '45380', NOT_IN_TEXT)],
                            he.peer('astra', additional=[he.code(colon, '45380', he.BIOPSY),
                                                         he.code(colon, '45380', NOT_IN_TEXT)]))
        position = self.detail([astra], '45380', 'astra', ('45385', he.span(colon, he.SNARE)))
        self.assertEqual(position['detail'],
                         'Astra proposed 45380 2 times, in its independent reading and again in peer review, and also '
                         'listed it in its independent reading and in peer review with no quote found verbatim in the '
                         'document (stated units 1, 1, 1, 1; modifiers none; confidence high), quoting the document '
                         'verbatim in 1 passage.')

    def test_a_listing_in_both_phases_beside_a_peer_review_s_proposal(self):
        # the first reading lists 45385 unlocated, the peer review gives it twice, located once: the first reading's
        # listing keeps round 3's words, and the peer review's own listing is named after it
        colon = he.COLON
        astra = he.reviewed('astra', [he.code(colon, '45385', NOT_IN_TEXT)], he.peer('astra', additional=[
            he.code(colon, '45385', he.SNARE), he.code(colon, '45385', NOT_IN_TEXT)]))
        position = self.detail([astra], '45385', 'astra', ('45385', he.span(colon, he.SNARE)))
        self.assertEqual(position['detail'],
                         'Astra proposed 45385, listed in its independent reading with no quote found verbatim there, '
                         'and proposed after peer review, and also listed it in peer review with no quote found '
                         'verbatim in the document (stated units 1, 1, 1; modifiers none; confidence high), quoting '
                         'the document verbatim in 1 passage.')

    def test_entries_that_all_located_read_as_before(self):
        # controls: every entry located - the sentences round 5 served, unchanged
        colon = he.COLON
        corti = ('45385', he.span(colon, he.SNARE))
        self.assertEqual(self.detail([he.read('astra', [he.code(colon, '45380', he.BIOPSY)])], '45380', 'astra',
                                     corti)['detail'], f'Astra proposed 45380 ({STATED_ONE}), {ONE_PASSAGE}')
        twice = he.read('astra', [he.code(colon, '45380', he.BIOPSY), he.code(colon, '45380', he.BIOPSY)])
        self.assertEqual(self.detail([twice], '45380', 'astra', corti)['detail'],
                         f'Astra proposed 45380 2 times ({STATED_TWO}), {ONE_PASSAGE}')
        again = he.reviewed('astra', [he.code(colon, '45380', he.BIOPSY)],
                            he.peer('astra', additional=[he.code(colon, '45380', he.BIOPSY)]))
        self.assertEqual(self.detail([again], '45380', 'astra', corti)['detail'],
                         f'Astra proposed 45380 2 times, in its independent reading and again in peer review '
                         f'({STATED_TWO}), {ONE_PASSAGE}')
        later = he.reviewed('fable', [he.code(colon, '45385', he.SNARE)],
                            he.peer('fable', additional=[he.code(colon, '45380', he.BIOPSY)]))
        self.assertEqual(self.detail([later], '45380', 'fable', corti)['detail'],
                         f'Fable proposed 45380 after peer review, not in its independent reading ({STATED_ONE}), '
                         f'{ONE_PASSAGE}')
        # and no entry located at all: listed, never proposed (round 4, truth-2)
        listed = he.reviewed('astra', [he.code(colon, '45385', NOT_IN_TEXT)],
                             he.peer('astra', additional=[he.code(colon, '45385', NOT_IN_TEXT)]))
        position = self.detail([listed], '45385', 'astra', corti)
        self.assertEqual((position['position'], position['detail']),
                         ('not_proposed', f'Astra listed 45385 2 times ({STATED_TWO}); none of its quotes was found '
                                          'verbatim in the document, so it did not propose it and is not counted as a '
                                          'proposer.'))


class PositionCountPipelineTests(Surfaces, R2WordingCase):
    """account-3 through the pipeline and the API (the proposal's support): the account lens's case C - Astra's first
    reading lists 45385 with a quote no document holds and locates 45380; its peer review locates 45385 and lists 45380
    with a quote no document holds. The same encounter's peer row says Astra listed 45380 again in peer review and
    first proposed it in its independent reading, and its summary that Astra proposed one code."""

    def test_the_detail_counts_one_proposal_of_each_code_as_the_peer_row_and_the_summary_do(self):
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', UNLOCATED), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=[('45385', SNARE),
                                                                                  ('45380', UNLOCATED_DIAG)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        said = {p['code']: p['support']['participants']['astra']['detail'] for p in detail['assessment']['proposals']
                if p['bucket'] == 'selected' and p['code'] in ('45385', '45380')}
        self.assertEqual(said, {
            '45385': 'Astra proposed 45385, listed in its independent reading with no quote found verbatim there, and '
                     f'proposed after peer review ({STATED_TWO}), {ONE_PASSAGE}',
            '45380': 'Astra proposed 45380 in its independent reading, and also listed it in peer review with no quote '
                     f'found verbatim in the document ({STATED_TWO}), {ONE_PASSAGE}'})
        for text in said.values():
            self.assertNotIn(' 2 times', text)
            self.assertNotIn('again in peer review', text)
        astra = self.rows(detail)['astra']
        self.assertEqual(astra['peer']['codes_added'], ['45385'])
        self.assertIn('It listed 45380 again in peer review; it first proposed it in its independent reading.',
                      astra['peer']['detail'])
        self.assertIn('It proposed 1 code (45380), 1 quoting the document verbatim.', self.summary(detail))

    def test_a_peer_review_that_gives_a_code_twice_located_once_proposed_it_once(self):
        # account-4's input: the engine said "Fable proposed 45378 2 times after peer review" of one located entry and
        # one listing, while the same encounter's summary says Fable listed 1 additional code, 1 quoting the document
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(codes=[('45378', LAND),
                                                                                  ('45378', UNLOCATED_DIAG)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        [proposal] = self.proposals(detail, '45378')
        self.assertEqual(proposal['support']['participants']['fable']['detail'],
                         'Fable proposed 45378 after peer review, not in its independent reading, and also listed it '
                         f'in peer review with no quote found verbatim in the document ({STATED_TWO}), {ONE_PASSAGE}')
        self.assertIn('It listed 1 additional code (45378), 1 quoting the document verbatim', self.summary(detail))
