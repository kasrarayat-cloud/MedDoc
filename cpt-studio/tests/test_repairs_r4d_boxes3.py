"""Regressions for refutation round 6, the BOXES3 items repaired in round 4d (contract-r4d section 4: strict check-box
rows). Each class reproduces its finding from the exact input round 6 confirmed at aaf517e88, adds the variants the
finding and its verifier name, and pins the positive controls an over-correction would break.

The predicate (studio.gi.detect._B3_row / _B3_hold) decides once whether a row's check boxes can be read: its marks
and its entries pair in exactly one way and every reader of the row pairs them so. On any other row of two or more
marks (or one with an unread mark), a passage the row's marks may govern is held (uncertain, a doubt, _B3_ROW_HOLD's
cue): never ready, never newly negated or excluded. Every box reader consults it first.

Routing runs for real on the document's own date; the engine runs through tests.test_repairs_r3_validation_b.real()
(the JSON round trip, the real span reader) with in-memory reference rows for every code cited here, so a held code is
held by its documentation, never by a missing reference row. Synthetic text only.
"""
import unittest
from datetime import date

from studio.gi import detect
from studio.reference.store import InMemoryReferenceLookup
from tests.test_repairs_r3_validation_b import HEAD, ROWS, real
from tests.test_validation import MUE_INFO, PFS_INFO, pfs

D = date(2026, 10, 21)
B3_ROWS = dict(ROWS)
B3_ROWS.update({('43235', ''): pfs(), ('43242', ''): pfs(mult='3', base='43235'),
                ('43249', ''): pfs(mult='3', base='43235')})
REFERENCE = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {PFS_INFO.key: B3_ROWS, MUE_INFO.key: {}})
HOLD = 'uncertain: the check boxes on the line '  # detect._B3_ROW_HOLD's prefix (a cue's text is part of the contract)
NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')

EUS = HEAD + 'Procedure: EUS with fine-needle aspiration of the pancreatic head mass\n{row}\n'
EUS_PHRASE = 'EUS with fine-needle aspiration'
EGD = HEAD + 'Procedure: EGD\nTechnique: The gastroscope was advanced to the second part of the duodenum.\n{row}\n'
COLO_T = HEAD + 'Procedure: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n{row}\n'
COLO_F = (HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm sigmoid polyp was '
          'seen.\n{row}\n')
OFFICE = (HEAD + 'Place of service: Office (POS 11)\nChief complaint: Heartburn.\nHistory of present illness: Heartburn '
          'for 3 months.\nAssessment and plan: PPI.\nTotal time: 32 minutes.\nMedical decision making: moderate.\n{row}\n')


def outcome(text, code, *phrases):
    proposals, _ = real(text, (code, *phrases), reference=REFERENCE)
    proposal = proposals[code]
    if proposal.bucket == 'excluded':
        return 'excluded'
    return 'ready' if proposal.status == 'ready' else 'held' if proposal.status == 'needs_clarification' else (
        proposal.bucket, proposal.status)


def family(text, slug):
    finding = detect.route(text, D).finding(slug)
    return finding.status if finding else None


def read(text, phrase, within=None):
    """status_for_span of ``phrase`` (inside ``within`` when given, else its only occurrence after the frame)."""
    start = text.index(within) + within.index(phrase) if within else text.rindex(phrase)
    return detect.status_for_span(text, start, start + len(phrase), D)


class Case(unittest.TestCase):
    maxDiff = None

    def assert_held(self, text, code, *phrases):
        self.assertEqual(outcome(text, code, *phrases), 'held', (code, phrases, text[-160:]))

    def assert_strict_hold(self, text, phrase, within=None):
        status, cues = read(text, phrase, within)
        self.assertEqual(status, 'uncertain', cues)
        self.assertTrue(any(c.startswith(HOLD) or c.startswith('uncertain: this item is marked with a box') for c in cues),
                        cues)


# --- regression:0 -- a trailing status row whose first entry is no option, read as leading ------------------------

class Regression0TrailingStatusRowTests(Case):
    """regression:0 (critical, a regression against 9a9f403 and 4347acd). _box_own_option_off read "Consent signed ☒ |
    Completed ☐ | Procedure cancelled ☒" by its option words alone: the first box comes before the first option word,
    so the row read as leading, "Completed" took Consent's ☒ and the checked "Procedure cancelled" took Completed's ☐:
    the reference was dropped and 43242 was READY (held at 9a9f403 and 4347acd, excluded at d05326ef). Read with every
    word run between the boxes as an entry, the row trails: the two readings disagree, so the row cannot be paired and
    everything its boxes may govern is held."""

    ROWS = ('Consent signed ☒ | Completed ☐ | Procedure cancelled ☒',
            'Fine-needle aspiration ☒ | Completed ☐ | Procedure cancelled ☒',
            'Status: Time out ☒ Completed ☐ Procedure cancelled ☒',
            'Consent signed ☒ | Completed ☐ | Procedure postponed ☒',
            'Consent signed ☒ | Completed ☐ | Procedure rescheduled ☒',
            'H&P reviewed ☒ | Performed ☐ | Exam cancelled ☒',
            'Patient identified ☒ Completed ☐ Procedure cancelled ☒',
            'Consent signed [x] | Completed [ ] | Procedure cancelled [x]',
            'Consent signed ☑ Completed ☐ Procedure cancelled ☑')

    def test_the_claimed_rows_never_ready_the_cancelled_eus(self):
        for row in self.ROWS:
            with self.subTest(row=row):
                text = EUS.format(row=row)
                self.assertEqual(family(text, 'gi.eus'), 'uncertain')
                self.assert_held(text, '43242', EUS_PHRASE)

    def test_the_colonoscopy_and_egd_frames(self):
        for frame, slug, code, phrase in ((COLO_T, 'gi.colonoscopy', '45378', 'Procedure: Colonoscopy'),
                                          (EGD, 'gi.egd', '43235', 'Procedure: EGD')):
            for row in self.ROWS[:4]:
                with self.subTest(frame=slug, row=row):
                    text = frame.format(row=row)
                    self.assertEqual(family(text, slug), 'uncertain')
                    self.assert_held(text, code, phrase)

    def test_the_reference_is_held_never_dropped_or_read_as_cancelled(self):
        text = EUS.format(row=self.ROWS[0])
        self.assert_strict_hold(text, 'Procedure cancelled')
        mentions = [(m.span.text, m.status) for m in detect.route(text, D).finding('gi.eus').mentions]
        self.assertIn(('Procedure cancelled', 'uncertain'), mentions)

    def test_controls_read_as_before(self):
        """A readable row reads as the declared box contract reads it: a trailing two-option row with its completion
        checked and its cancellation unchecked says it was done (round 5 regression:4); the checked cancellation
        holds; an unselected option alone says nothing."""
        for row, wanted in (('Procedure completed ☒ | Procedure cancelled ☐', 'ready'),
                            ('Procedure completed ☐ | Procedure cancelled ☒', 'held'),
                            ('Fine-needle aspiration ☐ | Procedure cancelled ☐', 'ready'),
                            ('Procedure cancelled ☒', 'held'),
                            ('Consent signed ☒ | Completed ☒ | Procedure cancelled ☐', 'held')):
            with self.subTest(row=row):
                self.assertEqual(outcome(EUS.format(row=row), '43242', EUS_PHRASE), wanted)


# --- regression:5 -- a checked cancellation after an unchecked first entry ------------------------------------------

class Regression5CheckedCancelAfterAnUncheckedEntryTests(Case):
    """regression:5 (critical, against d05326ef). "Fine-needle aspiration ☐ | Procedure cancelled ☒": the reference took
    the first entry's ☐ (the option words read as leading) and was dropped, so the cancelled EUS was READY at aaf517e,
    9a9f403 and 4347acd (cancelled at d05326ef). The row cannot be paired: held, never ready."""

    ROWS = ('Fine-needle aspiration ☐ | Procedure cancelled ☒', 'Status: Specimens sent ☐ Procedure cancelled ☒',
            'Outcome: Tolerated well ☐ | Procedure cancelled ☒', 'Outcome: Tolerated well ☐ | Procedure aborted ☒',
            'Fine-needle aspiration [ ] | Procedure cancelled [x]', 'Fine-needle aspiration | ☐ | Procedure cancelled | ☒',
            'Specimens sent | ☐ | Procedure cancelled | ☒', 'Fine-needle aspiration ☐ | Procedure postponed ☒')

    def test_the_claimed_rows_never_ready(self):
        for row in self.ROWS:
            with self.subTest(row=row):
                text = EUS.format(row=row)
                self.assertNotIn(family(text, 'gi.eus'), ('performed',))
                self.assert_held(text, '43242', EUS_PHRASE)


# --- regression:1 -- an unchecked item beside an unchecked "Not done" option ---------------------------------------

class Regression1UncheckedItemBesideAnOptionTests(Case):
    """regression:1 (critical, against 9a9f403, 4347acd and d05326ef). box2:I dropped the unchecked "Not done" option's
    words, and the item the box reader gave no box (or another entry's box) read performed: 43249 and 45380 READY. The
    rows cannot be paired: the unchecked item is held, never ready; the checked one is never excluded."""

    def test_the_claimed_rows(self):
        for frame, row, unchecked, checked in (
                (EGD, 'EGD: ☐ Not done ☒ Biopsy ☐ Balloon dilation', ('43249', 'Balloon dilation'), ('43239', 'Biopsy')),
                (COLO_T, 'Colonoscopy: ☐ Not done ☒ Cold snare polypectomy ☐ Biopsy', ('45380', 'Biopsy'),
                 ('45385', 'Cold snare polypectomy')),
                (COLO_T, 'Interventions: Photos ☒ | Biopsy ☐ | Not done ☐', ('45380', 'Biopsy'), None),
                (COLO_T, 'Interventions: Photos ☒ | Biopsy ☐ | Not performed ☐', ('45380', 'Biopsy'), None),
                (COLO_T, 'Interventions: Photos ☒ | Biopsy ☐ | None ☐', ('45380', 'Biopsy'), None),
                (COLO_T, 'Photos ☒ | Biopsy ☐ | Not done ☐', ('45380', 'Biopsy'), None),
                (EGD, 'EGD: ☐ Not performed ☒ Biopsy ☐ Balloon dilation', ('43249', 'Balloon dilation'), ('43239', 'Biopsy')),
                (EGD, 'EGD: [ ] Not done [x] Biopsy [ ] Balloon dilation', ('43249', 'Balloon dilation'), ('43239', 'Biopsy'))):
            with self.subTest(row=row):
                text = frame.format(row=row)
                self.assert_strict_hold(text, unchecked[1], row)
                self.assert_held(text, *unchecked)
                if checked:
                    self.assertNotEqual(outcome(text, *checked), 'excluded')


# --- regression:2 -- an unchecked hold-word option releasing an unchecked item --------------------------------------

class Regression2UncheckedHoldWordOptionTests(Case):
    """regression:2 (critical, against 9a9f403 and 4347acd). "EGD: ☒ Biopsy | ☐ Pending pathology | ☐ Balloon dilation":
    the non-item entry turned the box reader's row to trailing, the last item got no box, and box2:I's section-silent
    target skipped the unchecked "Pending" stop word: 43249 READY (held at 9a9f403 and 4347acd, excluded at d05326ef).
    The row cannot be paired: held."""

    def test_the_claimed_rows(self):
        for frame, row, code, phrase in (
                (EGD, 'EGD: ☒ Biopsy | ☐ Pending pathology | ☐ Balloon dilation', '43249', 'Balloon dilation'),
                (EGD, 'EGD: ☒ Biopsy ☐ Pending pathology ☐ Balloon dilation', '43249', 'Balloon dilation'),
                (EGD, 'EGD: ☒ Biopsy | ☐ On hold | ☐ Balloon dilation', '43249', 'Balloon dilation'),
                (EGD, 'EGD: ☒ Biopsy | ☐ TBD | ☐ Balloon dilation', '43249', 'Balloon dilation'),
                (EGD, 'Upper endoscopy: ☒ Biopsy | ☐ Pending pathology | ☐ Balloon dilation', '43249', 'Balloon dilation'),
                (EGD, 'EGD: ☒ Biopsy | ☐ Pending | ☐ Balloon dilation', '43249', 'Balloon dilation'),
                (COLO_T, 'Colonoscopy: ☒ Biopsy ☐ Pending pathology ☐ Cold snare polypectomy', '45385',
                 'Cold snare polypectomy'),
                (COLO_T, 'Colonoscopy: ☒ Biopsy ☐ TBD ☐ Cold snare polypectomy', '45385', 'Cold snare polypectomy')):
            with self.subTest(row=row):
                text = frame.format(row=row)
                self.assert_strict_hold(text, phrase, row)
                self.assert_held(text, code, phrase)
                self.assertNotEqual(family(text, 'gi.egd' if frame is EGD else 'gi.colonoscopy'), 'performed')


# --- regression:4 -- a non-item entry misplacing the box reader's boxes ---------------------------------------------

class Regression4NonItemEntryTests(Case):
    """regression:4 (critical, against d05326ef; present since 4347acd and left open by box2:K). A non-item entry ("None",
    "Photos") turned the box reader's orientation, so an unchecked item read performed and a checked one was excluded
    by another entry's box. The rows cannot be paired: neither is ever ready by another entry's box nor excluded."""

    def test_the_claimed_rows(self):
        for row in ('Colonoscopy: ☐ None ☒ Cold snare polypectomy ☐ Biopsy',
                    'Colonoscopy: ☐ None | ☒ Cold snare polypectomy | ☐ Biopsy',
                    'Colonoscopy: [ ] None [x] Cold snare polypectomy [ ] Biopsy',
                    'Colonoscopy: ☒ Cold snare polypectomy | ☒ Photos | ☐ Biopsy',
                    'Colonoscopy: ☒ Cold snare polypectomy ☒ Other ☐ Biopsy'):
            with self.subTest(row=row):
                text = COLO_T.format(row=row)
                self.assert_held(text, '45380', 'Biopsy')
                self.assertNotEqual(outcome(text, '45385', 'Cold snare polypectomy'), 'excluded')
                self.assertNotEqual(read(text, 'Cold snare polypectomy', row)[0], 'negated')
        text = COLO_T.format(row='Interventions: Photos ☒ | Biopsy ☐ | None ☐')
        self.assert_held(text, '45380', 'Biopsy')

    def test_rows_both_readings_agree_on_read_as_before(self):
        for row, item, status in (('Tattoo ☐ | Biopsy ☒ | Cold snare polypectomy ☐', 'Biopsy', 'performed'),
                                  ('Tattoo ☐ | Biopsy ☒ | Cold snare polypectomy ☐', 'Cold snare polypectomy', 'negated'),
                                  ('☐ Photos ☒ Biopsy ☐ Cold snare polypectomy', 'Biopsy', 'performed'),
                                  ('Colonoscopy: ☐ biopsy ☒ cold snare polypectomy', 'cold snare polypectomy', 'performed'),
                                  ('Colonoscopy: ☐ biopsy ☒ cold snare polypectomy', 'biopsy', 'negated'),
                                  ('Biopsy | ☐ | Cold snare polypectomy | ☒', 'Biopsy', 'negated'),
                                  ('Biopsy | ☐ | Cold snare polypectomy | ☒', 'Cold snare polypectomy', 'performed'),
                                  ('Colonoscopy: ☐ EGD: ☒ dilation to 15 mm', 'EGD', 'performed')):
            with self.subTest(row=row, item=item):
                self.assertEqual(read(COLO_T.format(row=row), item, row)[0], status)


# --- declared:0 -- the unread mark on an option or on an item's own box ---------------------------------------------

class Declared0UnreadMarkTests(Case):
    """declared:0 (critical, against 9a9f403, 4347acd and d05326ef). Once the unread mark's "?" was no hedge, nothing
    held an unread hold-word option on a service-labelled row ("Colonoscopy: ☒ Completed [?] Pending") or an item whose
    own trailing box is the unread mark ("Photos ☐ | Biopsy ☒ | Cold snare polypectomy [?]"): the codes were READY. The
    label of a row of options is read by every option, so an unread one holds it; an item the readers give another
    entry's box is held."""

    def test_an_unread_option_holds_the_label(self):
        for word in ('Pending', 'Incomplete', 'Unknown', 'On hold', 'TBD', 'Requested'):
            for row in (f'Colonoscopy: ☒ Completed [?] {word}', f'Colonoscopy status: ☒ Completed [?] {word}',
                        f'Colonoscopy: Completed ☒ | {word} [?]', f'Colonoscopy: ☒ Completed | [?] {word}'):
                with self.subTest(row=row):
                    text = COLO_F.format(row=row)
                    self.assert_strict_hold(text, 'Colonoscopy', row)
                    self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
                    self.assert_held(text, '45378', row)
                    self.assert_held(text, '45378', 'Procedure: Colonoscopy')

    def test_an_item_whose_own_box_is_unread(self):
        for row, code, phrase in (('Interventions: Photos ☐ | Biopsy ☒ | Cold snare polypectomy [?]', '45385',
                                   'Cold snare polypectomy'),
                                  ('Photos ☐ | Biopsy ☒ | Cold snare polypectomy [?]', '45385', 'Cold snare polypectomy'),
                                  ('Interventions: Photos ☒ | Biopsy [?]', '45380', 'Biopsy'),
                                  ('Photos ☒ | Biopsy [?]', '45380', 'Biopsy'),
                                  ('Photos ☒ Biopsy [?]', '45380', 'Biopsy'),
                                  ('Photos ☒\tBiopsy [?]', '45380', 'Biopsy')):
            with self.subTest(row=row):
                text = COLO_F.format(row=row)
                self.assertEqual(read(text, phrase, row)[0], 'uncertain')
                self.assert_held(text, code, phrase)

    def test_controls_read_as_before(self):
        for row in ('Colonoscopy: ☒ Completed (•) Pending', 'Status: ☒ Completed [?] Pending'):
            with self.subTest(row=row):
                self.assert_held(COLO_F.format(row=row), '45378', 'Procedure: Colonoscopy')
        text = COLO_F.format(row='Colonoscopy: ☒ Completed ☐ Pending')  # an unchecked hold word says nothing
        self.assertEqual(outcome(text, '45378', 'Procedure: Colonoscopy'), 'ready')


# --- declared:1 -- an item with no box of its own beside the unread mark --------------------------------------------

class Declared1BoxlessNeighbourOfTheUnreadMarkTests(Case):
    """declared:1 (critical, against 9a9f403, 4347acd and d05326ef). Extraction writes "[?]" for a box whose place may be
    the text on either side (ARCHITECTURE 5.1): in "Biopsy [?] Cold snare polypectomy" either item may be unchecked, and
    the one the box reader gave no box read performed by its section (45385 READY). The mark can be paired both ways,
    so both items are held; a neighbour with its own checked box still reads checked (round 5 extraction:8)."""

    def test_the_claimed_rows(self):
        for row, code, phrase in (('Biopsy [?] Cold snare polypectomy', '45385', 'Cold snare polypectomy'),
                                  ('Biopsy | [?] | Cold snare polypectomy', '45385', 'Cold snare polypectomy'),
                                  ('Biopsy | [?] Cold snare polypectomy', '45385', 'Cold snare polypectomy'),
                                  ('Biopsy ☒ [?] Cold snare polypectomy', '45385', 'Cold snare polypectomy'),
                                  ('Biopsy: [?] Cold snare polypectomy', '45380', 'Biopsy'),
                                  ('Cold snare polypectomy [?] Biopsy', '45380', 'Biopsy'),
                                  ('Polypectomy: cold snare [?] hot snare', '45385', 'Polypectomy'),
                                  ('Biopsy [?] Argon plasma coagulation', '45380', 'Biopsy')):
            with self.subTest(row=row):
                text = COLO_F.format(row=row)
                self.assertEqual(read(text, phrase, row)[0], 'uncertain')
                self.assert_held(text, code, phrase)

    def test_a_neighbour_with_its_own_checked_box_reads_checked(self):
        for row, code, phrase in (('☒ Biopsy [?] Cold snare polypectomy', '45380', 'Biopsy'),
                                  ('Biopsy [?] Cold snare polypectomy ☒', '45385', 'Cold snare polypectomy'),
                                  ('[?] Biopsy ☒ Cold snare polypectomy', '45385', 'Cold snare polypectomy'),
                                  ('Biopsy [?] | Cold snare polypectomy ☒', '45385', 'Cold snare polypectomy')):
            with self.subTest(row=row):
                text = COLO_F.format(row=row)
                self.assertEqual(outcome(text, code, phrase), 'ready')


# --- declared:3 -- an unread hold-word option on a service- or visit-labelled row ------------------------------------

class Declared3UnreadHoldWordLabelTests(Case):
    """declared:3 (critical through the visit statement: 99214 held at 9a9f403, 4347acd and d05326ef). An unread hold
    word on a service-labelled row never held the family, where the "Status:" reader of the same row does; through the
    visit statement's label the same line made 99214 READY. Held now, with a doubt."""

    def test_the_service_label(self):
        for row in ('Colonoscopy: ☒ Completed [?] Pending', 'Colonoscopy: ☒ Completed [?] Unknown',
                    'Colonoscopy: ☒ Completed [?] Incomplete', 'Colonoscopy status: ☒ Completed [?] Unknown',
                    'Colonoscopy: Completed ☒ | Incomplete [?]'):
            with self.subTest(row=row):
                text = COLO_F.format(row=row)
                self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
                self.assert_held(text, '45378', 'Procedure: Colonoscopy')
        text = EGD.format(row='EGD: ☒ Completed [?] Pending')
        self.assertEqual(family(text, 'gi.egd'), 'uncertain')

    def test_the_visit_statement_label(self):
        for row, phrase in (('Established patient office visit: ☒ Completed [?] Pending', 'Established patient office visit'),
                            ('Established patient office visit: ☒ Completed [?] Unknown', 'Established patient office visit'),
                            ('New patient office visit: ☒ Completed [?] TBD', 'New patient office visit')):
            with self.subTest(row=row):
                self.assert_held(OFFICE.format(row=row), '99214', phrase)
        text = OFFICE.format(row='Established patient office visit: ☒ Completed ☐ Pending')
        self.assertEqual(outcome(text, '99214', 'Established patient office visit'), 'ready')

    def test_a_visit_statement_another_entrys_box_was_read_for(self):
        """The visit statement's reader consults the predicate too: in "Photos ☒ | Established patient office visit ☐ |
        None ☐" the box reader gave the unchecked statement Photos' ☒, and box2:K's check skipped the row for its "None
        ☐" (99214 READY at aaf517e and every base). The row cannot be paired: held."""
        for row in ('Photos ☒ | Established patient office visit ☐ | None ☐',
                    'Photos ☒ Established patient office visit ☐ None ☐'):
            with self.subTest(row=row):
                text = OFFICE.format(row=row)
                self.assertEqual(read(text, 'Established patient office visit', row)[0], 'uncertain')
                self.assert_held(text, '99214', 'Established patient office visit')
        for row in ('Established patient office visit ☒ | Photos ☐', '☐ Photos ☒ Established patient office visit'):
            with self.subTest(control=row):
                self.assertEqual(outcome(OFFICE.format(row=row), '99214', 'Established patient office visit'), 'ready')


# --- the predicate itself ---------------------------------------------------------------------------------------------

class StrictRowsPredicateTests(Case):
    """contract-r4d section 4: one predicate, consulted first by every box reader. A row that pairs one way keeps the
    declared contract's reading; a row of one box keeps its reading; any other row holds what its boxes may govern,
    with the row named in a non-silent cue and a doubt."""

    def test_the_hold_names_the_row_and_is_a_doubt(self):
        row = 'Consent signed ☒ | Completed ☐ | Procedure cancelled ☒'
        text = EUS.format(row=row)
        an = detect._analysis(text, D)[0]
        start = text.index('Procedure cancelled')
        reading = detect._generic_reading(an, start, start + len('Procedure cancelled'))
        self.assertEqual(reading.status, 'uncertain')
        self.assertTrue(reading.doubt)
        self.assertEqual(reading.cues, (detect._B3_ROW_HOLD.format(row),))
        self.assertFalse(reading.cues[0].startswith('uncertain: no performance evidence'))

    def test_every_status_row_reader_consults_it(self):
        row = 'Consent signed ☒ | Completed ☐ | Procedure cancelled ☒'
        text = EUS.format(row=row)
        an = detect._analysis(text, D)[0]
        start = text.index('Procedure cancelled')
        end = start + len('Procedure cancelled')
        line_start = text.index(row)
        self.assertFalse(detect._box_own_option_off(an, start, end))
        self.assertTrue(detect._procedure_called_off(an, line_start, line_start + len(row)))
        self.assertFalse(detect._unchecked_option(an, line_start, line_start + len(row)))
        self.assertEqual(detect._box_checked_option(an, start, end).status, 'uncertain')
        word = text.index('cancelled', line_start)
        self.assertEqual(detect._B2_unselected_option(an, word, word + 9, 0, 1), 'unpaired')

    def test_readers_whose_own_answer_the_predicate_overrules(self):
        """Rows whose last box is unchecked: read by their option words alone, every denying option reads unchecked
        (the first box comes before the first option word, so they look as if they lead), while the cancellation's own
        box is checked. Each reader asked on its own would call the row an unselected option; on a row that cannot
        be paired, none may."""
        for row, frame in (('Fine-needle aspiration ☐ | Procedure cancelled ☒ | Photos ☐', EUS),
                           ('Consent signed ☐ | Not performed ☒ | Photos ☐', EUS)):
            with self.subTest(row=row):
                text = frame.format(row=row)
                an = detect._analysis(text, D)[0]
                lo = text.index(row)
                self.assertFalse(detect._unchecked_option(an, lo, lo + len(row)))
                self.assert_held(text, '43242', EUS_PHRASE)
        row = 'Consent signed ☐ | Not performed ☒ | Photos ☐'
        text = EUS.format(row=row)
        an = detect._analysis(text, D)[0]
        lo = text.index(row)
        self.assertTrue(detect._box_selected_denial(an, lo, lo + len(row)))
        row = 'Status: Specimens sent ☐ Procedure cancelled ☒ Photos ☐'
        text = EUS.format(row=row)
        an = detect._analysis(text, D)[0]
        value = text.index('Specimens')
        self.assertTrue(detect._boxed_status_denies(an, value, text.index(row) + len(row)))
        self.assert_held(text, '43242', EUS_PHRASE)

    def test_a_label_ended_by_a_shared_separator_on_a_line_of_one_box(self):
        """round 6 declared:2's sibling: "Colonoscopy - ☒ Incomplete" (one box): the hold word beside the box reads its
        state; an unchecked hold word says nothing."""
        for row in ('Colonoscopy - ☒ Incomplete', 'Colonoscopy\t☒ Pending', 'Colonoscopy = [x] Unknown',
                    'Colonoscopy – Incomplete ☒'):
            with self.subTest(row=row):
                text = COLO_T.format(row=row)
                self.assertIn(read(text, 'Colonoscopy', row)[0], ('uncertain', 'incomplete'))  # box2:L's trailing reading
                self.assertNotEqual(family(text, 'gi.colonoscopy'), 'performed')
        row = 'Colonoscopy - \u2612 Incomplete'
        status, cues = read(COLO_T.format(row=row), 'Colonoscopy', row)
        self.assertIn("uncertain: its status line checks 'Incomplete', which holds it", cues)  # truthful: its box is checked

    def test_readable_rows_keep_the_declared_reading(self):
        for row, item, status in (('☐ Biopsy ☒ Cold snare polypectomy', 'Biopsy', 'negated'),
                                  ('☐ Biopsy ☒ Cold snare polypectomy', 'Cold snare polypectomy', 'performed'),
                                  ('Biopsy ☐ | Cold snare polypectomy ☒', 'Biopsy', 'negated'),
                                  ('Biopsy: [ ] Cold snare polypectomy: [x] clip placed', 'Cold snare polypectomy', 'performed'),
                                  ('Biopsy | ☐ | Cold snare polypectomy | ☒ | clip placed after polypectomy',
                                   'Cold snare polypectomy', 'performed'),
                                  ('Colonoscopy with ☐ biopsy ☒ cold snare', 'cold snare', 'performed'),
                                  ('Colonoscopy, ☐ biopsy ☒ cold snare', 'biopsy', 'negated'),
                                  ('☐ Biopsy ☒ Cold snare polypectomy | clip placed', 'Cold snare polypectomy', 'performed'),
                                  ('Biopsy taken: ☐ Yes ☒ No', 'Biopsy', 'negated'),
                                  ('Biopsy taken ☐ Yes ☒ No', 'Biopsy', 'negated'),
                                  ('Colonoscopy: ☒ Completed ☐ Cancelled', 'Colonoscopy', 'performed'),
                                  ('Colonoscopy | ☒ Completed | ☐ Cancelled', 'Colonoscopy', 'performed'),
                                  ('Colonoscopy: Cancelled ☐ | Completed ☒', 'Colonoscopy', 'performed'),
                                  ('Colonoscopy: ☒ Cancelled ☐ Completed', 'Colonoscopy', 'cancelled')):
            with self.subTest(row=row, item=item):
                self.assertEqual(read(COLO_T.format(row=row), item, row)[0], status)

    def test_single_box_lines_keep_their_reading(self):
        for row, item, status in (('Biopsy: ☐', 'Biopsy', 'negated'), ('☐ Cold snare polypectomy', 'Cold snare polypectomy', 'negated'),
                                  ('☒ Cold snare polypectomy', 'Cold snare polypectomy', 'performed'),
                                  ('Biopsy | ☐', 'Biopsy', 'negated')):
            with self.subTest(row=row):
                self.assertEqual(read(COLO_T.format(row=row), item, row)[0], status)

    def test_rows_that_cannot_be_paired_hold_never_negate(self):
        """Two boxes for one entry, boxes in cells of their own, an item label that pairs both ways, and an entry that
        may be a remark: each can be paired more than one way, so it is held (it read negated or performed before)."""
        for row, item in (('☐ ☐ Biopsy', 'Biopsy'), ('☒ ☒ Biopsy', 'Biopsy'), ('Biopsy ☐ ☐', 'Biopsy'),
                          ('Biopsy | ☒ | ☐', 'Biopsy'), ('Biopsy | ☐ | ☒', 'Biopsy'),
                          ('Polypectomy: [ ] biopsy [x] cold snare', 'biopsy'),
                          ('Photos ☐ Biopsy ☒ Cold snare polypectomy', 'Cold snare polypectomy'),
                          ('Not performed [ ] | Cold snare polypectomy [x]', 'Cold snare polypectomy')):
            with self.subTest(row=row):
                status, cues = read(COLO_T.format(row=row), item, row)
                self.assertEqual(status, 'uncertain', cues)

    def test_a_service_label_before_the_first_entry_is_not_the_rows(self):
        """"Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed" can be paired two ways, so its entries are held;
        its service label is no reading's entry (a service is described by its interventions), so it reads as before."""
        row = 'Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed'
        text = COLO_T.format(row=row)
        self.assertEqual(read(text, 'Colonoscopy', row)[0], 'performed')
        for item in ('Biopsy', 'Cold snare polypectomy', 'clip'):
            with self.subTest(item=item):
                self.assertEqual(read(text, item, row)[0], 'uncertain')


# --- declared:2 -- a status label ended by a dash, tab, "=" or a completion word -----------------------------------

COLO_S = (HEAD + 'Procedure: Colonoscopy\nIndication: Screening.\nFindings: The colonoscope was advanced to the cecum. No '
          'polyps.\n{row}\n')


class Declared2LabelSeparatorTests(Case):
    """declared:2 (high). box2:L's hold of a service-labelled status row with a hold word checked read the label only to
    ':' or '|', so "Colonoscopy - ☒ Incomplete ☐ Completed" (en dash, tab, '=', "Colonoscopy completed:") read
    PERFORMED (45378 ready, a false complete). The label ends at the shared separators: held, never ready."""

    def test_the_claimed_rows(self):
        for row in ('Colonoscopy - ☒ Incomplete ☐ Completed', 'Colonoscopy – ☒ Incomplete ☐ Completed',
                    'Colonoscopy — ☒ Incomplete ☐ Completed', 'Colonoscopy\t☒ Incomplete ☐ Completed',
                    'Colonoscopy = ☒ Incomplete ☐ Completed', 'Colonoscopy status - Incomplete ☒ Completed ☐',
                    'Colonoscopy - ☒ Unknown ☐ Completed', 'Colonoscopy completed: ☒ Incomplete ☐ Completed',
                    'Colonoscopy performed: ☒ Incomplete ☐ Completed', 'Colonoscopy ☒ Incomplete ☐ Completed',
                    'Colonoscopy - [x] Requested [ ] Completed', 'Colonoscopy - ☒ Unclear ☐ Completed'):
            with self.subTest(row=row):
                text = COLO_S.format(row=row)
                self.assertNotEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assert_held(text, '45378', row)
                self.assert_held(text, '45378', 'Procedure: Colonoscopy')

    def test_controls(self):
        for row, wanted in (('Colonoscopy status - Completed ☒ Incomplete ☐', 'ready'),
                            ('Colonoscopy: ☒ Completed ☐ Incomplete', 'ready'),
                            ('Colonoscopy: ☒ Incomplete ☐ Completed', 'held')):
            with self.subTest(row=row):
                self.assertEqual(outcome(COLO_S.format(row=row), '45378', 'Procedure: Colonoscopy'), wanted)
        # an accepted over-hold: a leading row with a dash, tab or '=' label is read both ways by the status-line
        # reader, whose label ends at ':' or '|' only, so the strict rows hold it; never excluded
        self.assertEqual(outcome(COLO_S.format(row='Colonoscopy - ☒ Completed ☐ Incomplete'), '45378',
                                 'Procedure: Colonoscopy'), 'held')


# --- declared:4 -- a status line after a list marker or in a table row ------------------------------------------------

EUSB = HEAD + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass\n{row}\n'
EUSB_PHRASE = 'EUS with fine-needle biopsy of the pancreatic head mass'


class Declared4StatusLineLeadTests(Case):
    """declared:4 (high). _STATUS_KEY took no list marker and only [:=–—-] as its separator, so "• Status: Cancelled -
    the patient had eaten breakfast.", "2) Status: ...", "Status | Cancelled - ...", "Procedure status<TAB>Cancelled"
    (a Word table row) never held the EUS line (43242 READY), where the done-question grammar reads those leads. The
    status line's key is read in the shared grammar too (_B3_STATUS_KEY); a line only it reads may hold, never release."""

    def test_the_claimed_rows(self):
        for row in ('• Status: Cancelled - the patient had eaten breakfast.', '* Status: Cancelled - the patient had eaten breakfast.',
                    '2) Status: Cancelled - the patient had eaten breakfast.', '(1) Status: Cancelled - the patient had eaten breakfast.',
                    'Procedure status | Not performed - the patient had eaten', 'Status | Cancelled - the patient had eaten breakfast',
                    'Procedure status\tCancelled - the patient had eaten breakfast',
                    'Status: | Cancelled - the patient had eaten breakfast.',
                    '• Status: Rescheduled to next week because the patient was ill.', 'Status  Cancelled - the patient had eaten'):
            with self.subTest(row=row):
                text = EUSB.format(row=row)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                self.assert_held(text, '43242', EUSB_PHRASE)
        text = EUSB.format(row='Indication: Pancreatic mass.\n• Status: Cancelled - the patient had eaten breakfast.')
        self.assert_held(text, '43242', EUSB_PHRASE)  # from further down, as the unmarked line holds

    def test_controls(self):
        for row in ('• Status: Completed - tolerated well.', 'Status | Completed - tolerated well', '2) Status: Done.',
                    'Procedure status\tCompleted'):
            with self.subTest(row=row):
                self.assertEqual(outcome(EUSB.format(row=row), '43242', EUSB_PHRASE), 'ready')

    def test_a_line_only_the_shared_grammar_reads_never_releases(self):
        """A status line only _B3_STATUS_KEY reads may hold the service; where its value is a completion or its boxed
        options are unchecked, the tests the line had before still decide (a completion with a cancellation, a refusal
        or a rescheduling after it stays held)."""
        for row in ('\u2022 Status | Completed, then cancelled.', '\u2022 Status\tCompleted - patient declined.',
                    '\u2022 Status\tDone - not tolerated.', '\u2022 Status | Completed - rescheduled',
                    '\u2022 Status\tCompleted \u2612 Cancelled \u2610'):
            with self.subTest(row=row):
                self.assertNotEqual(family(HEAD + 'Procedure: EUS\n' + row + '\n', 'gi.eus'), 'performed')

    def test_a_form_field_status_label_with_its_own_question_mark(self):
        """The form-field status reader takes the same key: "Procedure status?: Cancelled" in a PDF form block holds its
        page's EUS (ready at aaf517e: the old key took no "?")."""
        filler = ''.join(f'Note {n}: The patient was comfortable.\n' for n in range(8))  # past the status lines' reach
        for field in ('Procedure status?: Cancelled', 'Status?: Cancelled'):
            with self.subTest(field=field):
                text = (HEAD + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\nFindings: The pancreatic '
                        'head mass was sampled.\n' + filler + '[PDF form fields on page 1]\n' + field + '\n')
                self.assert_held(text, '43242', 'EUS with fine-needle biopsy of the pancreatic head mass')
        text = (HEAD + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\nFindings: The pancreatic head '
                'mass was sampled.\n[PDF form fields on page 1]\nProcedure status?: Completed\n')
        self.assertEqual(outcome(text, '43242', 'EUS with fine-needle biopsy of the pancreatic head mass'), 'ready')


# --- declared:5 -- a spaced checked box pushing a short cancellation past the six-word bound -------------------------

class Declared5SpacedBoxTests(Case):
    """declared:5 (high). "[ x ] Cancelled - patient ate breakfast." under the EUS line counted the bracket and the "x" as
    words, past the six-word bound of a short cancelling line, so 43242 was READY where "☒" or "[x]" holds it. A box of
    any spelling is one word (_B3_words)."""

    def test_the_claimed_rows(self):
        for box in ('[ x ]', '( x )', '[ X ]', '[x ]', '[ x]', '( x)', '(x )', '[  x  ]', '[ x ]', '[ ✓ ]'):
            for line in ('{} Cancelled - patient ate breakfast.', '{} Cancelled due to poor prep.', '{} Rescheduled to next week.',
                         'Cancelled - patient ate breakfast {}'):
                row = line.format(box)
                with self.subTest(row=row):
                    self.assert_held(EUSB.format(row=row), '43242', EUSB_PHRASE)

    def test_a_bare_service_line(self):
        """After a bare service line the short bare-line tests count a box as one word too (_bare_denial)."""
        for row in ('[ x ] Deferred until next week.', '[ x ] Scheduled for next week.'):
            with self.subTest(row=row):
                self.assertNotEqual(family(HEAD + 'Procedure: EUS\n' + row + '\n', 'gi.eus'), 'performed')

    def test_controls(self):
        self.assertEqual(outcome(EUSB.format(row='[ ] Cancelled - patient ate breakfast.'), '43242', EUSB_PHRASE), 'ready')
        self.assertEqual(outcome(EUSB.format(row='[ x ] Completed without difficulty.'), '43242', EUSB_PHRASE), 'ready')
        for row in ('☒ Cancelled - patient ate breakfast.', '[x] Cancelled - patient ate breakfast.'):
            with self.subTest(row=row):
                self.assert_held(EUSB.format(row=row), '43242', EUSB_PHRASE)
        self.assertEqual(detect._B3_words('☒ Cancelled - patient ate breakfast.', 0, 40, 6),
                         detect._B3_words('[ x ] Cancelled - patient ate breakfast.', 0, 40, 6))


# --- declared:8 -- an item's label before one box -----------------------------------------------------------------------

class Declared8ItemLabelBeforeABoxTests(Case):
    """declared:8 (high). "Biopsy: ☐ Cold snare polypectomy" read the box as leading (the colon after an opening label
    was a plain lead): the biopsy READY and the polypectomy EXCLUDED, never held, though "Biopsy: ☐" is the declared
    trailing layout. An item's own label opening the row pairs both ways: both items held, never ready or excluded."""

    def test_the_claimed_rows(self):
        for row in ('Biopsy: ☐ Cold snare polypectomy', 'Biopsy: ☐ Cold snare polypectomy: Yes',
                    'Biopsy: [ ] Cold snare polypectomy', 'Biopsy: ☐ Cold snare polypectomy was performed.',
                    'Biopsy: ☐\tCold snare polypectomy: Yes', 'biopsy: ☐ cold snare polypectomy',
                    'Biopsy:  ☐  Cold snare polypectomy'):
            with self.subTest(row=row):
                text = COLO_F.format(row=row)
                snare = 'cold snare polypectomy' if 'cold' in row else 'Cold snare polypectomy'
                biopsy = 'biopsy' if 'biopsy:' in row else 'Biopsy'
                self.assertEqual(read(text, biopsy, row)[0], 'uncertain')
                self.assertEqual(read(text, snare, row)[0], 'uncertain')
                self.assert_held(text, '45380', biopsy)
                self.assert_held(text, '45385', snare)

    def test_controls(self):
        for row, item, status in (('Biopsy: ☐', 'Biopsy', 'negated'), ('☐ Cold snare polypectomy', 'Cold snare polypectomy', 'negated'),
                                  ('Biopsy: ☒ Cold snare polypectomy', 'Biopsy', 'performed'),
                                  ('Biopsy: ☒ Cold snare polypectomy', 'Cold snare polypectomy', 'performed'),
                                  ('Colonoscopy: [ ] biopsy [x] cold snare', 'biopsy', 'negated'),
                                  ('Biopsy | ☐', 'Biopsy', 'negated')):
            with self.subTest(row=row, item=item):
                self.assertEqual(read(COLO_F.format(row=row), item, row)[0], status)


class StrictRowsCostTests(unittest.TestCase):
    """contract-r4d section 6: the predicate is read once per row and per passage (memoised), and a row longer than
    B3_ROW_CHARS is held without being paired, so a long one-line paste of any row stays linear. Each shape was timed at
    about 0.3 s per 50,000 characters; unpaired at length it took 5 to 8 s per 100,000."""

    def test_long_one_line_rows_route_in_bounded_time(self):
        import time
        for unit in ('Consent signed ☒ | Completed ☐ | Procedure cancelled ☒ ',
                     'Colonoscopy: ☐ Cancelled ☒ Completed ', 'Procedure completed ☒ | Procedure cancelled ☐ ',
                     'EGD: ☐ Not done ☒ Biopsy ☐ Balloon dilation '):
            with self.subTest(unit=unit):
                body = (unit * (200000 // len(unit) + 1))[:200000]
                text = HEAD + 'Procedure: Colonoscopy\nFindings: ' + body + '\n'
                started = time.monotonic()
                result = detect.route(text)
                start = text.index(body)
                detect.status_for_span(text, start, start + len(body.rstrip()))
                self.assertLess(time.monotonic() - started, 6.0)
                self.assertNotIn(result.finding('gi.colonoscopy').status, NOT_TODAY)


# --- bounded:0 and bounded:2 -- long one-line status rows ------------------------------------------------------------

class Bounded0And2LongStatusRowTests(unittest.TestCase):
    """bounded:0 (high): status_for_span over a cited passage across a 400,000-character one-line status row read every
    box and option per unchecked option (_B2_label_state), and the assess stage overran its 60 s (9a9f403: 11 s).
    bounded:2 (high): each status reference's hold split and joined the whole line to keep 160 characters, and the
    analyze stage overran (9a9f403: 8 s). Now: the row is past B3_ROW_CHARS, or its line carries more than
    B3_LINE_MARKS marks, so it is held without being read further; a status line is indexed once for its options'
    text (_B3_line_index, _B3_line_remark); the shown line is read once per line (_B3_shown_line). Measured through
    the real stages on the verifiers' inputs: assess 6.5 s, analyze 3.4 s."""

    def long_text(self, unit, chars):
        return HEAD + 'Procedure: Colonoscopy\nFindings: ' + (unit * (chars // len(unit) + 1))[:chars] + '\n'

    def test_a_cited_passage_across_a_long_row_is_read_in_bounded_time(self):
        import time
        for unit in ('Colonoscopy: ☐ Cancelled ☒ Completed ', 'Colonoscopy: ☐ Cancelled ☒ Completed. ',
                     'Procedure completed ☒ | Procedure cancelled ☐ ', 'Procedure completed ☒ | Procedure cancelled ☐. '):
            with self.subTest(unit=unit):
                text = self.long_text(unit, 300000)
                start = text.index('Findings: ') + len('Findings: ')
                started = time.monotonic()
                result = detect.route(text)
                for end in (len(text.rstrip()), start + 200000):
                    self.assertEqual(detect.status_for_span(text, start, end)[0], 'uncertain')
                self.assertLess(time.monotonic() - started, 12.0)
                self.assertNotIn(result.finding('gi.colonoscopy').status, NOT_TODAY)

    def test_a_long_status_line_is_indexed_once(self):
        """The remark check of a 200,000-character status line, read straight (the predicate holds such a passage before
        it is asked): by bisection, once per line (the scan took 0.5 s at 50,000 and grows with the square)."""
        import time
        text = self.long_text('Colonoscopy: ☐ Cancelled ☒ Completed ', 200000)
        an = detect._analysis(text, None)[0]
        lo = text.index('Findings: ') + len('Findings: ')
        hi = len(text.rstrip('\n'))
        line = detect._B2_status_line(an, lo, hi)
        started = time.monotonic()
        self.assertFalse(detect._B3_line_remark(an, line, lo, hi))
        self.assertLess(time.monotonic() - started, 1.0)
        index = detect._B3_line_index(an, line, lo, hi)
        for (s, e), _ in list(zip(line[1], line[2]))[:200]:  # exactly what the scan reads
            self.assertEqual(detect._B2_option_text(line, s, e, hi, index), detect._B2_option_text(line, s, e, hi))

    def test_the_label_state_of_a_long_status_line_is_linear(self):
        """bounded:0's own reader with the predicate out of the way (it holds such a passage first): a passage across a
        200,000-character status row, opening in its label, read by _B2_label_state in well under a second (the loop
        over every unchecked option, each scanning every box and option, took 8.7 s at 200,000)."""
        import time
        from unittest import mock
        text = self.long_text('Colonoscopy: ☐ Cancelled ☒ Completed ', 200000)
        an = detect._analysis(text, None)[0]
        start = text.index('Colonoscopy: ☐')
        end = len(text.rstrip())
        with mock.patch.object(detect, '_B3_hold', return_value=None):
            started = time.monotonic()
            state = detect._B2_label_state(an, start, end)
            self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(state, 'across')

    def test_the_shown_line_is_exact(self):
        text = HEAD + 'Procedure: EUS\n   Procedure  completed ☒ |\tProcedure cancelled ☐   \n'
        an = detect._analysis(text, None)[0]
        start = text.index('Procedure  completed')
        self.assertEqual(detect._B3_shown_line(an, start, start + 5),
                         ' '.join(text[text.index('   Procedure  completed'):len(text) - 1].split())[:160])


if __name__ == '__main__':
    unittest.main()
