"""Refutation round 6, R6-TRACE: the D12 account (HARNESS.md 11.1, 12.6, 12.9 truth-8, 12.12, 12.13 D12; I4, I9) -
"proposed" is said only of an entry with a located quote, entry by entry, on every surface that words one, and no
phrase is given two meanings.

- account-1: the owner's trace headed a peer review's additional codes "Codes proposed after peer review" and a first
  reading's codes "Codes proposed", over items whose only quote is unverified and which the same trace says were not
  proposed. The headings are now neutral ("Additional codes", "Codes it listed"); each item carries its own words.
- account-3: the engine's support['participants'] detail counted every entry of a code as one of its proposals - "Astra
  proposed 45385 2 times" beside one located entry - and said "again in peer review" of a peer-review entry none of
  whose quotes was found. It now counts only the entries that located a quote and names each other entry as a listing
  in its phase.
- account-4: the reports and the trace gave every entry of an additional code the code's one phase, so an entry whose
  quote was not found, beside another entry of the code that located one, was "proposed after peer review, never
  independent" in the TXT (twice, the second with no passage), the CSV (two such rows) and the trace. Each entry is now
  worded by its own quotes: one with none located is never 'peer_review'. codes_added stays per code.
- account-5: the trace served '' - D12's "listed in peer review", no entry located - for every additional code of a
  peer review the current assessment did not read, so a context change made the original run's located code "listed"
  while its reuse, the same bytes, was "proposed after peer review". Such a review's codes are now served phase None
  and the page says "not read by the current assessment".

Each pipeline class runs the real pipeline (tests.test_harness2_pipeline: the real jobs, loop, tool executor, readers
and engine, the vendors' HTTP replaced by scripted bytes in their own envelopes), then the real API, the owner's trace,
the reports through the reports endpoint and the real app.js under node. Synthetic data only; nothing is sent.
"""
from django.test import SimpleTestCase

from studio import reports
from tests import test_harness2_pipeline as hp
from tests import test_harness_engine as he
from tests.legacy_chain import applied
from tests.test_harness2_pipeline import BIOPSY, LAND, SNARE, TWO_EXTENTS, TWO_EXTENTS_INTERPRETATIONS
from tests.test_harness2_r2_wording import R2WordingCase, browser
from tests.test_harness2_r4_truth import UNLOCATED, _block, _section
from tests.test_harness2_r5_account import UNLOCATED_DIAG, Surfaces, csv_rows
from tests.test_pipeline_api import RecordedInterpretation, drain

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


@applied
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


# --- account-4: each additional-code entry is worded by its own quotes ------------------------------------------------

@applied
class EntryWordingTests(Surfaces, R2WordingCase):
    """account-4: Fable's peer review gives 45378 twice, one entry quoting the landmarks line and one with a quote no
    document holds, in either order. Per code, as before, Fable first proposed 45378 in its peer review (codes_added,
    the engine's phases); per entry, the one whose quote was not found is listed in peer review, in the TXT, the CSV
    and the trace. Both orders, so a rule that let the first or the last entry of a code decide fails (falsegreen-1's
    pipeline half). The engine's own count of the same input is account-3's (PositionCountPipelineTests)."""

    def surfaces(self, *codes, answer=None):
        self.adapters['fable'].peer = [hp.answered('fable', answer or hp.peer_answer(codes=list(codes)), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        block = _block(_section(self.download(encounter_id), reports.PEER_TITLE), '  - Fable · ')
        start = next(index for index, line in enumerate(block) if line.startswith('    Additional code '))
        added = [line for line in block[start:] if line.startswith(('    Additional code ', '      "'))]
        rows = [(row['code'], row['status'], bool(row['evidence'])) for row in csv_rows(self.download(encounter_id,
                                                                                                         fmt='csv'))
                if row['item_list'] == 'peer_additional_code' and row['proposed_by'] == 'fable']
        trace = self.trace(encounter_id)
        self.last_trace = trace
        runs = next(item for item in trace['participants'] if item['name'] == 'fable')['runs']
        served = [[(c['code'], c['phase']) for c in run['review']['additional_codes']] for run in runs
                  if run.get('review')]
        head = '45378 · units 1 · confidence high · '
        lines = [line for line in self.trace_lines(trace) if line.startswith(head)]
        return detail, added, rows, served, lines

    def assertPerCode(self, detail):
        self.assertEqual(self.rows(detail)['fable']['peer']['codes_added'], ['45378'])
        [proposal] = self.proposals(detail, '45378')
        self.assertEqual((proposal['proposed_by'], proposal['phases']), (['fable'], {'fable': 'peer_review'}))
        self.assertIn('Codes it proposed after peer review, never independent: 45378.', self.peer_row(detail, 'fable'))

    def test_the_located_entry_first(self):
        detail, added, rows, served, lines = self.surfaces(('45378', LAND), ('45378', UNLOCATED_DIAG))
        self.assertPerCode(detail)
        self.assertEqual(added, [f'    Additional code 45378 · units 1 — {PROPOSED_AFTER}',
                                 f'      "{LAND}" [chars 354–418, page 1]',
                                 f'    Additional code 45378 · units 1 — {LISTED_IN_PEER}'])
        self.assertEqual(rows, [('45378', 'proposed_after_peer_review', True),
                                ('45378', 'listed_in_peer_review', False)])
        self.assertEqual(served, [[('45378', 'peer_review'), ('45378', '')]])
        self.assertEqual(lines, [f'45378 · units 1 · confidence high · {PROPOSED_AFTER} {FOUND_LAND}',
                                 f'45378 · units 1 · confidence high · {LISTED_IN_PEER} {UNVERIFIED_DIAG}'])

    def test_the_located_entry_last(self):
        detail, added, rows, served, lines = self.surfaces(('45378', UNLOCATED_DIAG), ('45378', LAND))
        self.assertPerCode(detail)
        self.assertEqual(added, [f'    Additional code 45378 · units 1 — {LISTED_IN_PEER}',
                                 f'    Additional code 45378 · units 1 — {PROPOSED_AFTER}',
                                 f'      "{LAND}" [chars 354–418, page 1]'])
        self.assertEqual(rows, [('45378', 'listed_in_peer_review', False),
                                ('45378', 'proposed_after_peer_review', True)])
        self.assertEqual(served, [[('45378', ''), ('45378', 'peer_review')]])
        self.assertEqual(lines, [f'45378 · units 1 · confidence high · {LISTED_IN_PEER} {UNVERIFIED_DIAG}',
                                 f'45378 · units 1 · confidence high · {PROPOSED_AFTER} {FOUND_LAND}'])

    def one_entry(self, evidence):
        """Refutation round 7, falsegreen-2: every entry above holds one quote, so neither surface's per-entry rule was
        pinned against an every-quote, first-quote or last-quote rule (serializers._trace_review reads any quote found;
        reports._peer_items likewise). One entry of 45378 quoting the landmarks line and a passage no document holds is
        proposed after peer review on all three surfaces, in either order (one order per test: a workspace reuses an
        identical peer request's answer)."""
        answer = {**hp.peer_answer(), 'additional_codes': [hp.code('45378', service_ids=[], evidence=evidence)]}
        detail, added, rows, served, lines = self.surfaces(answer=answer)
        self.assertPerCode(detail)
        self.assertEqual(added[0], f'    Additional code 45378 · units 1 — {PROPOSED_AFTER}')
        self.assertIn(f'      "{LAND}" [chars 354–418, page 1]', added)
        self.assertFalse(any(LISTED_IN_PEER in line for line in added), added)
        self.assertEqual(rows, [('45378', 'proposed_after_peer_review', True)])
        self.assertEqual(served, [[('45378', 'peer_review')]])
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f'45378 · units 1 · confidence high · {PROPOSED_AFTER} '), lines)
        # the entry's quotes, in its order: the first on its line, the next on the line after
        every = self.trace_lines(self.last_trace)
        at = every.index(lines[0])
        quotes = [FOUND_LAND, UNVERIFIED_DIAG] if evidence[0] == LAND else [UNVERIFIED_DIAG, FOUND_LAND]
        self.assertEqual([lines[0].endswith(quotes[0]), every[at + 1]], [True, quotes[1]], every[at:at + 2])

    def test_one_entry_its_located_quote_first(self):
        self.one_entry([LAND, UNLOCATED_DIAG])

    def test_one_entry_its_located_quote_last(self):
        self.one_entry([UNLOCATED_DIAG, LAND])

    def test_an_unlocated_entry_of_a_code_its_first_reading_proposed_is_still_repeated(self):
        # control: 'independent' claims no proposal in peer review, so it stays, located or not (ColonCase: Astra's
        # first reading locates 45380 on the biopsy line)
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=[('45380', UNLOCATED_DIAG)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        block = _block(_section(self.download(encounter_id), reports.PEER_TITLE), '  - Astra · ')
        self.assertIn(f'    Additional code 45380 · units 1 — {REPEATED}', block)
        rows = [(row['code'], row['status']) for row in csv_rows(self.download(encounter_id, fmt='csv'))
                if row['item_list'] == 'peer_additional_code' and row['proposed_by'] == 'astra']
        self.assertEqual(rows, [('45380', 'repeated_in_peer_review')])
        runs = next(item for item in self.trace(encounter_id)['participants'] if item['name'] == 'astra')['runs']
        self.assertEqual([[(c['code'], c['phase']) for c in run['review']['additional_codes']] for run in runs
                          if run.get('review')], [[('45380', 'independent')]])


# --- account-5: a peer review the current assessment did not read is marked so, never "listed" ------------------------

class UnreadReviewTests(RecordedInterpretation, Surfaces, R2WordingCase):
    """account-5: after a member's context change the new chain reuses the identical peer request, so the current
    assessment reads the reuse run, not the run that holds the bytes. The trace served '' for every additional code of
    that original run - "listed in peer review" beside a quote found in the document - while the reuse, the same bytes,
    was "proposed after peer review". The original's codes are now served phase None, and the page says the current
    assessment did not read them."""
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation.
    interpretations = TWO_EXTENTS_INTERPRETATIONS

    def fable_reviews(self, encounter_id):
        runs = next(item for item in self.trace(encounter_id)['participants'] if item['name'] == 'fable')['runs']
        return {run['id']: [(c['code'], c['phase']) for c in run['review']['additional_codes']] for run in runs
                if run.get('review')}

    def test_the_original_of_a_reused_review_is_not_read_by_the_current_assessment(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        [original] = self.runs_of(encounter_id, 'fable', 'peer_review')
        # control: read by the assessment then current, its located code is proposed after peer review
        self.assertEqual(self.fable_reviews(encounter_id), {str(original.pk): [('45378', 'peer_review')]})
        response = self.post(f'/api/encounters/{encounter_id}/context', {'billing_context': 'professional'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        runs = self.runs_of(encounter_id, 'fable', 'peer_review')
        self.assertEqual([(run.sent, run.reused_from_id) for run in runs], [(True, None), (False, original.pk)])
        record = self.records(self.encounter(encounter_id).current_assessment)['fable']
        self.assertEqual((record['peer_state'], record['peer_run']), ('read', str(runs[1].pk)))
        self.assertEqual(self.fable_reviews(encounter_id), {str(original.pk): [('45378', None)],
                                                            str(runs[1].pk): [('45378', 'peer_review')]})
        trace = self.trace(encounter_id)
        head = '45378 · units 1 · confidence high · '
        self.assertEqual([line for line in self.trace_lines(trace) if line.startswith(head)],
                         [f'{head}not read by the current assessment {FOUND_LAND}',
                          f'{head}{PROPOSED_AFTER} {FOUND_LAND}'])
        self.assertFalse([line for line in self.trace_lines(trace) if LISTED_IN_PEER in line])


# --- account-1: the trace's headings are neutral; each item carries its own words -----------------------------------

@applied
class TraceHeadingTests(Surfaces, R2WordingCase):
    """account-1, on the account lens's inputs: Astra's first reading lists 45385 with a quote no document holds (and
    locates 45380), and Fable's peer review lists 45378 with a quote no document holds. The trace headed them "Codes
    proposed" and "Codes proposed after peer review", while its reconciliation says neither was proposed."""

    def test_no_trace_heading_says_proposed_over_a_code_whose_only_quote_is_unverified(self):
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', UNLOCATED), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(codes=[('45378', UNLOCATED_DIAG)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        trace = self.trace(encounter_id)
        headings = browser(HEADINGS, trace)
        self.assertFalse([heading for heading in headings if 'propos' in heading.lower()], headings)
        astra, fable = (next(item for item in trace['participants'] if item['name'] == name)['runs']
                        for name in ('astra', 'fable'))
        self.assertEqual([len(run['reading']['codes']) for run in astra if run.get('reading')], [2])
        self.assertEqual([len(run['review']['additional_codes']) for run in fable if run.get('review')], [1])
        self.assertIn('Codes it listed · 2', headings)
        self.assertIn('Additional codes · 1', headings)
        lines = self.trace_lines(trace)
        # each item still says what it is
        self.assertIn(f'45378 · units 1 · confidence high · {LISTED_IN_PEER} {UNVERIFIED_DIAG}', lines)
        self.assertIn(f'45385 · units 1 · confidence high “{UNLOCATED}” — unverified (not found); never used as '
                      'evidence', lines)
        self.assertIn('Proposed by: no participant; listed by Fable with no quote found verbatim in the document, so '
                      'not proposed', lines)

    def test_an_empty_list_says_none_was_listed(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        trace = self.trace(encounter_id)
        headings = browser(HEADINGS, trace)
        self.assertIn('Additional codes · 0', headings)  # Astra's peer review (ColonCase) adds no code
        self.assertIn('No additional code.', self.trace_lines(trace))
        self.assertFalse([heading for heading in headings if 'propos' in heading.lower()], headings)
