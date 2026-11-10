"""Refutation round 10, the narrow pass over round 9's repair commit (d9383aae4..6a77e7af2): the findings it reproduced
(refute-harness-r10, each verified in verify-harness-r10), on their own inputs.

- wording-1: a service a participant quotes twice, in two different quotes, had one quote's reading printed beside the
  other quote ("the upper endoscopy as cancelled and the snare removal ... as performed" beside the snare sentence).
  Each quote's own places are read alone, and the entry is the first quote whose places name a reading.
- wording-2 to wording-5: naming an act read as performed in the quote was false where the act's mention lay outside
  the quote though its words were in it, where its service was named by its family's label and not its own (an
  esophagoscopy as "the upper endoscopy"), where the inventory had dropped the act (an indwelling stent's state), and
  where the act kept no passage for the quoted restatement; and the fallback, "does not read as performed", was false
  beside a quote of an act's words. No act is named now, and the fallback says only what makes the service missing:
  the documented-service reading reads no performed service of that kind - true of every input by construction.
- page-1: a highlight split across paragraphs gave each of its pieces the whole highlight's title, so a piece was
  titled as holding a passage it does not hold. Each piece is titled by the passages whose own span overlaps it.
- page-2: the round-9 title pins held one two-code shape only; two more are pinned.

retrieval-1 (blocking, pre-existing on the installed path: a diagnostic base is not held again when a reviewer
reinstates a therapeutic code of its family) and retrieval-2 (the page draws no retrieval for an exclusion) are
recorded in HARNESS.md 12.18, not repaired in this release; page-3 was not reproduced. The page's branches are pinned
in the `// refutation round 10` block of tests/frontend/app.test.cjs. With no participant configured the engine's
result is unchanged (I1). Synthetic data only; nothing is sent.
"""
from django.test import SimpleTestCase

from studio import review
from tests import test_harness2_pipeline as hp
from tests import test_harness2_r6_meaning as r6m
from tests import test_harness2_r7 as r7
from tests import test_harness2_r9 as r9
from tests.legacy_chain import applied

ACK = review.ACKNOWLEDGEMENTS['human']
SNARE_LINE = 'A 6 mm polyp in the rectum was removed with a cold snare.'
CANCELLED = r7.IN_QUOTE[2][1]
MANOMETRY_PLAN = 'Plan: anorectal manometry next month.'
LABELLED = 'Cold snare polypectomy: a 6 mm polyp in the rectum was removed.'
REMOVED = 'a 6 mm polyp in the rectum was removed.'
ESOPHAGOSCOPY = (hp.HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
                 'Procedure: Esophagoscopy\nThe esophagoscope was advanced to the gastroesophageal junction.\n')
REACHED_GEJ = 'The esophagoscope was advanced to the gastroesophageal junction.'
DILATED = 'Balloon dilation of the esophagus to 18 mm was performed.'
REDUCTION = 'The existing stent was in good position and draining when a second plastic stent was placed beside it.'
EXISTING = 'The existing stent was in good position and draining'
BANDS = [f'A band was placed on a varix at {n} cm.' for n in range(38, 31, -1)]


def entry(result):
    (item,) = result.completeness['participant_services']
    return item


class OneQuoteAtATimeTests(SimpleTestCase):
    def test_wording_1_each_quote_s_own_reading_in_either_order(self):
        """wording-1: Astra's performed upper endoscopy quotes the snare sentence and the cancelled line. Only the
        cancelled line's own reading is named, beside that line, whichever quote comes first."""
        text = r6m.doc(r6m.COLON, SNARE_LINE, CANCELLED)
        for quotes in ((SNARE_LINE, CANCELLED), (CANCELLED, SNARE_LINE)):
            with self.subTest(first=quotes[0]):
                result = r9.he.run(text, r9.he.corti(('45385', r9.he.span(text, SNARE_LINE))),
                                   [r9.he.read('astra', [r9.he.code(text, '45378', r6m.CECUM)],
                                               services=[r9.he.service(text, 'colonoscopy', r6m.CECUM),
                                                         r9.he.service(text, 'egd', *quotes)])])
                item = entry(result)
                self.assertEqual(item['reason'], 'Astra reads a performed upper endoscopy where the documented-service '
                                                 f'reading reads the upper endoscopy as cancelled (“{CANCELLED}”)')
                self.assertEqual((item['start'], item['end']), (text.index(CANCELLED), text.index(CANCELLED)
                                                                 + len(CANCELLED)))
                self.assertNotIn('snare', item['reason'])

    def test_wording_1_two_quotes_each_with_its_own_reading(self):
        """wording-1 where both quotes name a reading: another GI service quoting a capsule plan and a manometry not
        performed - only the first quote's reading is named, beside it, never the other's, in either order."""
        capsule, manometry = 'Plan: capsule endoscopy in 6 months.', 'Esophageal manometry was not performed.'
        text = r6m.doc(r6m.COLON, capsule, manometry)
        for quotes, read_as in (((capsule, manometry), 'the capsule endoscopy as planned'),
                                ((manometry, capsule), 'the manometry as negated')):
            with self.subTest(first=quotes[0]):
                result = r9.he.run(text, r9.he.corti(('45378', r9.he.span(text, r6m.CECUM))),
                                   [r9.he.read('astra', [r9.he.code(text, '45378', r6m.CECUM)],
                                               services=[r9.he.service(text, 'colonoscopy', r6m.CECUM),
                                                         r9.he.service(text, 'other_gi', *quotes)])])
                item = entry(result)
                self.assertEqual((item['read_as'], item['quote']), (read_as, quotes[0]))
                self.assertNotIn(' and ', item['read_as'])

    def test_wording_1_a_plan_is_never_printed_beside_a_banding_quote(self):
        """wording-1's engine variant: another GI service quoting a banding line and a plan line - the plan's reading
        is named beside the plan line, never beside the banding."""
        text = r6m.doc(r6m.COLON, r7.BANDED, MANOMETRY_PLAN)
        result = r9.he.run(text, r9.he.corti(('45378', r9.he.span(text, r6m.CECUM))),
                           [r9.he.read('astra', [r9.he.code(text, '45378', r6m.CECUM)],
                                       services=[r9.he.service(text, 'colonoscopy', r6m.CECUM),
                                                 r9.he.service(text, 'other_gi', r7.BANDED, MANOMETRY_PLAN)])])
        item = entry(result)
        self.assertEqual(item['quote'], MANOMETRY_PLAN)
        self.assertTrue(item['reason'].endswith(f'as planned (“{MANOMETRY_PLAN}”)'), item['reason'])
        self.assertNotIn(r7.BANDED, item['reason'])


class NoActIsNamedTests(SimpleTestCase):
    """wording-2 to wording-5: each input's reason is only what makes the service missing - never an act "as performed",
    never "does not read as performed"."""

    def assert_fallback(self, result, label='other GI service', status='a performed'):
        item = entry(result)
        self.assertEqual(item['read_as'], '')
        self.assertEqual(item['reason'], f'Astra reads {status} {label} {r7.NOT_READ} (“{item["quote"]}”)')
        self.assertNotIn('does not read as performed', item['reason'])
        return item

    def test_wording_2_an_act_s_words_without_its_mention(self):
        text = r6m.doc(r6m.COLON, LABELLED)
        self.assert_fallback(r9.engine(text, REMOVED, corti_code=[('45385', LABELLED)]))

    def test_wording_3_an_esophagoscopy_s_act_is_never_said_of_the_upper_endoscopy(self):
        text = r6m.doc(ESOPHAGOSCOPY, DILATED)
        item = self.assert_fallback(r9.engine(text, DILATED, head_code='43220', anchor=REACHED_GEJ, head_family='egd',
                                              corti_code=[('43220', DILATED)]))
        self.assertNotIn('upper endoscopy', item['reason'])

    def test_wording_4_a_stent_the_inventory_drops(self):
        text = r6m.doc(r6m.ERCP, REDUCTION)
        item = self.assert_fallback(r9.engine(text, EXISTING, head_code='43274', anchor=r6m.ERCP.splitlines()[-1],
                                              head_family='ercp', corti_code=[('43274', REDUCTION)]))
        self.assertNotIn('stent placement', item['reason'])

    def test_wording_5_a_seventh_restatement(self):
        text = r6m.doc(r6m.EGD, *BANDS)
        self.assert_fallback(r9.engine(text, BANDS[-1], head_code='43235', anchor=r6m.D2, head_family='egd',
                                       corti_code=[('43244', BANDS[0])]))


@applied
class NoActIsNamedPipelineTests(r6m.MeaningCase):
    def test_wording_2_on_the_reviewed_report(self):
        """wording-2, on the reviewed report a reviewer signs, beside the approved 45385 whose evidence is that very
        sentence."""
        text = r6m.doc(r6m.COLON, LABELLED)
        services = [r6m.colon_service(r6m.CECUM), ('u1', 'other_gi', 'performed', REMOVED)]
        encounter_id = self.scenario(text, [('45385', LABELLED)],
                                     astra=hp.reading(codes=[('45378', r6m.CECUM)], services=services))
        (item,) = [p for p in r6m.proposals(self.detail(encounter_id)) if p['code'] == '45385']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        # harness repair 3 (P-ADMIT2): Astra's own 45378 now reaches review, held by the base rule beside the
        # therapeutic code - the reviewer decides it too (reject: the base is included) before the report is reviewed
        for held in [p for p in r6m.proposals(self.detail(encounter_id)) if p['code'] == '45378'
                     and p['bucket'] == 'selected']:
            rejected = self.post(f'/api/encounters/{encounter_id}/decisions',
                                 {'proposal_id': held['id'], 'action': 'reject', 'note': 'Synthetic review.'})
            self.assertEqual(rejected.status_code, 201, rejected.content)
        self.assertTrue(self.detail(encounter_id)['readiness']['reviewed'])
        report = self.download(encounter_id, 'reviewed')
        self.assertIn(f'Astra reads a performed other GI service {r7.NOT_READ} (“{REMOVED}”)', report)
        self.assertNotIn('does not read as performed', report)


# --- page-1, page-2: what each piece of a highlight holds ---------------------------------------------------------

SEEN, SNARED, BIOPSIES = r6m.SEEN, r7.SNARED, r9.BIOPSIES
ACROSS = f'{SEEN}\n\n{SNARED} {BIOPSIES}'
HOLDING = r9.HOLDING
NOT_THE_ACT = 'Passage the provider cited for {code}, which does not show the coded act'


@applied
class PieceTitleTests(r6m.MeaningCase):
    both = r9.TwoCodeHighlightTitleTests.both

    def titles(self, detail):
        return {text: title for _, title, text in r6m.marks(detail)}

    def across(self, corti):
        text = r6m.doc(r6m.COLON, SEEN, '', f'{SNARED} {BIOPSIES}')
        return [self.corti_alone(text, corti), self.detail(self.scenario(text, corti))]

    def test_page_1_a_highlight_split_across_paragraphs_two_codes(self):
        """page-1: 45380's passage runs across the blank line and joins 45385's two separate passages into one
        highlight, drawn as two pieces: the "was seen" piece holds 45385's passage that does not show the act and part of
        45380's, never evidence for 45385; the other holds evidence for both and no passage that does not show the act."""
        for detail in self.across([('45385', SEEN), ('45385', SNARED), ('45380', ACROSS)]):
            self.assertEqual(self.titles(detail), {
                SEEN: f'Evidence for 45380; {NOT_THE_ACT.format(code="45385")}',
                f'{SNARED} {BIOPSIES}': 'Evidence for 45380, 45385'})

    def test_page_1_a_highlight_split_across_paragraphs_one_code(self):
        """page-1's one-code variant: 45385 cites the "was seen" sentence and the passage that runs from it across the
        blank line to the snare sentence: the first piece holds both kinds, the second only the evidence."""
        for detail in self.across([('45385', SEEN), ('45385', f'{SEEN}\n\n{SNARED}')]):
            self.assertEqual(self.titles(detail), {SEEN: HOLDING.format(code='45385'), SNARED: 'Evidence for 45385'})

    def test_page_2_two_codes_each_holding_both_kinds(self):
        """page-2, shape A: 45385 and 45380 each cite a passage that shows their act and one that does not, all in one
        highlight: each code's clause is said."""
        for detail in self.both([('45385', SEEN), ('45385', f'{SEEN} {SNARED}'), ('45380', SNARED),
                                 ('45380', f'{SNARED} {BIOPSIES}')]):
            self.assertEqual(self.titles(detail), {
                r9.LINE: f'{HOLDING.format(code="45385")}; {HOLDING.format(code="45380")}'})

    def test_page_2_another_code_with_only_a_passage_that_does_not_show_its_act(self):
        """page-2, shape B: in the first line's highlight 45385 holds both kinds and 45380 only the snare sentence, which
        does not show its biopsy; the biopsy line is 45380's evidence alone."""
        text_lines = (f'{SEEN} {SNARED}', BIOPSIES)
        text = r6m.doc(r6m.COLON, *text_lines)
        corti = [('45385', SEEN), ('45385', f'{SEEN} {SNARED}'), ('45380', SNARED), ('45380', BIOPSIES)]
        for detail in [self.corti_alone(text, corti), self.detail(self.scenario(text, corti))]:
            self.assertEqual(self.titles(detail), {
                text_lines[0]: f'{NOT_THE_ACT.format(code="45380")}; {HOLDING.format(code="45385")}',
                BIOPSIES: 'Evidence for 45380'})
