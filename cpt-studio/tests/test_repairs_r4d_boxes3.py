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


COLO_N = (HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. The colon was normal.\n'
          '{row}\n')
CELL_KEYS = ('Status', 'Procedure status', '- Status')
CELL_SEPARATORS = (': | ', ': - ', ': – ', ': = ', ':: ')
CELL_VALUES = ('Completed? No', 'Performed? No', 'Done? No', 'Completed: No', 'Completed? No - rescheduled.',
               'Done? No - cancelled.', 'Completed, then cancelled.')


class Declared4OldKeyValueKeptTests(Case):
    """Round 4d's verification of declared:4 (critical, a regression against aaf517e, 9a9f403 and 4347acd). A status line
    round 5's key already reads, whose label keeps a second separator after its own colon - a Word table row "Status:" |
    "Completed? No" extracts as "Status: | Completed? No"; also "Status: - ", "Status: = ", "Status:: " - was read
    after the widened key, so its value opened with "Completed" and the completion's early return released the EUS
    (43242) and the colonoscopy (45378), which every older tree held (the value read after round 5's key, "| Completed?
    No", is a short line with an unexplained "No"). Round 5's key is read on its own value exactly as before, and the
    shared grammar's value may only add a hold (_B3_status_value_denies), in _denies and in the form-field reader."""

    def test_a_second_separator_after_the_label_colon_holds_as_before(self):
        for frame, slug, code, phrase in ((EUSB, 'gi.eus', '43242', EUSB_PHRASE),
                                          (COLO_N, 'gi.colonoscopy', '45378', 'Procedure: Colonoscopy')):
            for key in CELL_KEYS:
                for separator in CELL_SEPARATORS:
                    for value in CELL_VALUES:
                        row = key + separator + value
                        with self.subTest(frame=slug, row=row):
                            text = frame.format(row=row)
                            self.assertNotEqual(family(text, slug), 'performed')
                            self.assert_held(text, code, phrase)

    def test_the_word_table_row(self):
        """The real Word path: a two-cell table row under the procedure line, extracted as "Status: | <value>"."""
        from studio.ingest import extract_document
        from tests.support import docgen
        mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        for lines, code, phrase in ((['Procedure: EUS with fine-needle biopsy of the pancreatic head mass'], '43242',
                                     EUSB_PHRASE),
                                    (['Procedure: Colonoscopy', 'Findings: The colonoscope was advanced to the cecum. The '
                                      'colon was normal.'], '45378', 'Procedure: Colonoscopy')):
            for label, value, wanted in (('Status:', 'Performed? No - cancelled.', 'held'),
                                         ('Status:', 'Completed: No - rescheduled.', 'held'),
                                         ('Procedure status:', 'Completed, then cancelled.', 'held'),
                                         ('Status:', 'Completed? No', 'held'), ('Status:', 'Cancelled.', 'held'),
                                         ('Status:', 'Completed.', 'ready'),
                                         ('Status:', 'Performed - tolerated well.', 'ready')):
                with self.subTest(code=code, label=label, value=value):
                    data = docgen.make_docx(['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'Date of service: 2026-10-21']
                                            + lines + [[[label, value]]])
                    result = extract_document(data, 'synthetic.docx', mime, ocr=None)
                    self.assertEqual(result.status, 'ok', result.messages)
                    self.assertIn(f'{label} | {value}', result.text)
                    self.assertEqual(outcome(result.text, code, phrase), wanted)

    def test_a_form_field_status_value_after_a_second_separator(self):
        """The form-field status reader (_box_status_field) read the same widened value: "Status: | Completed? No" or
        "Status: = Performed? No" in a PDF form block, past the status lines' reach, released its page's EUS."""
        filler = ''.join(f'Note {n}: The patient was comfortable.\n' for n in range(8))  # past the status lines' reach
        for key in ('Status', 'Procedure status'):
            for separator in (': | ', ': = '):
                for value in ('Completed? No', 'Performed? No', 'Done? No - cancelled.', 'Completed, then cancelled.'):
                    field = key + separator + value
                    with self.subTest(field=field):
                        text = (HEAD + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\nFindings: '
                                'The pancreatic head mass was sampled.\n' + filler + '[PDF form fields on page 1]\n'
                                + field + '\n')
                        self.assert_held(text, '43242', 'EUS with fine-needle biopsy of the pancreatic head mass')
                        an = detect._analysis(text, D)[0]
                        start = text.index(field)
                        self.assertTrue(detect._box_status_field(an, start, start + len(field)))

    def test_the_status_line_reader_itself(self):
        for line in ('Status: | Completed? No', 'Status: | Performed? No - cancelled.', 'Status:: Done? No',
                     'Procedure status: - Completed: No - rescheduled.', 'Status: = Completed, then cancelled.'):
            with self.subTest(line=line):
                text = EUSB.format(row=line)
                an = detect._analysis(text, D)[0]
                start = text.index(line)
                self.assertTrue(detect._status_line(an, start, start + len(line)))
                self.assertTrue(detect._denies(an, start, start + len(line), bare=False))

    def test_controls(self):
        """A completion after the second separator says it was done, as at every older tree; the plain colon reads as
        before (a completion's value is never read by the short-line tests after it: "Status: Done - not tolerated." is
        done); the declared:4 rows only the shared grammar reads still hold."""
        for row, wanted in (('Status: | Completed.', 'ready'), ('Status: | Performed - tolerated well.', 'ready'),
                            ('Status: - Completed', 'ready'), ('Status:: Done.', 'ready'),
                            ('Procedure status: = Completed - tolerated well.', 'ready'), ('Status: Completed.', 'ready'),
                            ('Status: Done - not tolerated.', 'ready'), ('Status: Completed - not tolerated well.', 'ready'),
                            ('Status: | Cancelled - the patient had eaten breakfast.', 'held'),
                            ('Status: | Cancelled.', 'held'), ('Status | Cancelled - the patient had eaten breakfast', 'held'),
                            ('• Status: Cancelled - the patient had eaten breakfast.', 'held'),
                            ('Status: | Pending.', 'held'), ('Status: | Rescheduled to next week.', 'held')):
            with self.subTest(row=row):
                self.assertEqual(outcome(EUSB.format(row=row), '43242', EUSB_PHRASE), wanted)
                self.assertEqual(outcome(COLO_N.format(row=row), '45378', 'Procedure: Colonoscopy'), wanted)


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


# --- declared:11 -- two denial options on an item's label, the second checked --------------------------------------

class Declared11TwoDenialOptionsTests(Case):
    """declared:11 (low; the three bases excluded it). "Cold snare polypectomy: ☐ Not done ☒ Not performed": _group_state
    read only the first denial option (unchecked) and, with no yes option, nothing; box2:I dropped the unchecked
    option's words, so the item read performed (45385 READY). A denial option after the first, checked while the first
    is not, among the item's own options (_B3_later_denial_checked), makes the item's boxes disagree ('mixed'): held,
    never ready, never newly excluded. With a checked Yes as well it is held too ("☒ Yes ☐ Not done ☒ Not performed",
    READY at aaf517e, excluded at every base); with an unchecked Yes the item stays denied, as before."""

    ROWS = (('Cold snare polypectomy: \u2610 Not done \u2612 Not performed', '45385', 'Cold snare polypectomy'),
            ('Colonoscopy: \u2610 Not done \u2612 Not performed', '45378', 'Procedure: Colonoscopy'),
            ('1. Colonoscopy: \u2610 Not done \u2612 Not performed', '45378', 'Procedure: Colonoscopy'),
            ('- Colonoscopy: \u2610 Not done \u2612 Not performed', '45378', 'Procedure: Colonoscopy'),
            ('Cold snare polypectomy: Not done \u2610 Not performed \u2612', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: [ ] Not done [x] Not performed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy | \u2610 Not done | \u2612 Not performed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 not done \u2612 not performed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 Not done \u2612 Not performed - poor prep', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 None \u2612 Not performed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 No \u2612 Not performed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 Not performed \u2612 None', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 Not done \u2610 Completed \u2612 Not performed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 Not done \u2612 Not performed \u2610 Completed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2612 Yes \u2610 Not done \u2612 Not performed', '45385', 'Cold snare polypectomy'),
            ('Cold snare polypectomy: \u2610 Not done \u2612 Not performed \u2612 Yes', '45385', 'Cold snare polypectomy'))

    def test_the_claimed_rows(self):
        for row, code, phrase in self.ROWS:
            with self.subTest(row=row):
                self.assert_held(COLO_F.format(row=row), code, phrase)

    def test_the_family_is_never_released_by_the_service_row(self):
        for marker in ('', '1. ', '- '):
            with self.subTest(marker=marker):
                text = COLO_F.format(row=marker + 'Colonoscopy: \u2610 Not done \u2612 Not performed')
                self.assertNotEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_controls(self):
        for row, wanted in (('Cold snare polypectomy: \u2612 Not performed', 'excluded'),
                            ('Cold snare polypectomy: \u2610 Yes \u2612 No', 'excluded'),
                            ('Cold snare polypectomy: \u2612 Yes \u2610 No', 'ready'),
                            ('Cold snare polypectomy: \u2612 Not done \u2610 Not performed', 'excluded'),
                            ('Cold snare polypectomy: \u2610 Not done \u2612 Not performed \u2610 Yes', 'excluded'),
                            ('Cold snare polypectomy: \u2610 Yes \u2610 Not done \u2612 Not performed', 'excluded'),
                            ('Cold snare polypectomy: \u2610 Not done \u2610 Not performed \u2612 Completed', 'ready'),
                            ('Cold snare polypectomy: \u2612 Completed \u2610 Not done \u2610 Not performed', 'ready')):
            with self.subTest(row=row):
                self.assertEqual(outcome(COLO_F.format(row=row), '45385', 'Cold snare polypectomy'), wanted)

    def test_the_item_s_own_options_only(self):
        """Another item's options after its label are not the item's own: the passage across both items keeps box2:G's
        cue (the items differ), not the item's own boxes disagreeing."""
        def marks(row):
            group = [(m.start(), m.end(), 'off' if m.group('off') is not None else 'on') for m in detect._BOX.finditer(row)]
            return [(b, detect._OPTION_AFTER.match(row, b[1])) for b in group]
        self.assertTrue(detect._B3_later_denial_checked('\u2610 Not done \u2612 Not performed',
                                                        marks('\u2610 Not done \u2612 Not performed')))
        row = '\u2610 Not done \u2610 Completed \u2612 Not performed'
        self.assertTrue(detect._B3_later_denial_checked(row, marks(row)))
        for row in ('\u2612 Yes \u2610 No  Cold snare polypectomy: \u2610 Yes \u2612 No', '\u2610 Not done \u2610 Biopsy: \u2612 Not performed',
                    '\u2612 Not done \u2612 Not performed', '\u2610 Not done \u2610 Not performed'):
            with self.subTest(row=row):
                self.assertFalse(detect._B3_later_denial_checked(row, marks(row)))


# --- declared:9 -- a done-question named by the service, and a status row outside a positive section ---------------

EUS_I = HEAD + ('Procedure: EUS with fine-needle aspiration of the pancreatic head mass\nIndication: Pancreatic mass.\n'
                '{row}\n')
EUS_ABOVE = HEAD + '{row}\nProcedure: EUS with fine-needle aspiration of the pancreatic head mass\n'
COLO_I = (HEAD + 'Procedure: Colonoscopy\nIndication: Screening.\n{row}\nFindings: The colonoscope was advanced to the cecum. '
          'A 6 mm sigmoid polyp was seen.\n')


class Declared9ServiceNamedDoneQuestionTests(Case):
    """declared:9 (medium, a residual at every base). "Was the EUS performed today? No": the done-question grammar's noun
    names only the procedure's own words (_BOX_Q_NOUN), so the question's EUS read 'uncertain: ?' (a hedge, no doubt)
    and the procedure line's section evidence released the family: 43242 READY. Now a typed done-question whose noun
    names a service and whose whole answer is a denial holds that service's mention with doubt (_B3_asked_no), so the
    family is held wherever the question stands. The status-label form ("Colonoscopy?: ☒ Pending ☐ Completed") is held
    by the strict rows; the same row without the '?' outside a positive section (under "Indication:") read 'no
    performance evidence', and box2:L, read only after a performed reading, never held it: now it does
    (_B3_label_hold_unread). All holds."""

    ASKED = ('Was the EUS performed today? No', 'EUS performed? No', 'EUS completed? No', 'EUS performed today? No',
             'Was EUS done? No', 'EUS done? No', 'EUS performed?: No', '- EUS performed? No', 'Was the EUS performed? No.',
             'EUS performed? Not performed', 'EUS performed? No - the patient had eaten', 'Was the EUS completed today? N/A',
             'EUS performed: No', 'EUS performed - No', 'Was the EUS with FNA performed today? No',
             'Was the endoscopic ultrasound performed today? No', 'EUS performed? No (patient declined)')

    def test_the_claimed_rows(self):
        for frame in (EUS, EUS_I, EUS_ABOVE):
            for row in self.ASKED:
                with self.subTest(row=row, frame=frame[len(HEAD):len(HEAD) + 30]):
                    text = frame.format(row=row)
                    self.assert_held(text, '43242', EUS_PHRASE)
                    self.assertEqual(family(text, 'gi.eus'), 'uncertain')

    def test_the_family_named_by_the_question(self):
        for row in ('Was the colonoscopy performed? No', 'Colonoscopy completed? No', 'Colonoscopy performed? No'):
            with self.subTest(row=row):
                self.assert_held(COLO_F.format(row=row), '45378', 'Procedure: Colonoscopy')
        text = EGD.format(row='Was the EGD performed today? No')
        self.assertEqual(family(text, 'gi.egd'), 'uncertain')

    def test_the_question_s_own_mention_is_a_doubt(self):
        text = EUS.format(row='Was the EUS performed today? No')
        start = text.rindex('EUS')
        status, cues = detect.status_for_span(text, start, start + 3, D)
        self.assertEqual(status, 'uncertain')
        self.assertEqual(cues[0], "uncertain: the line 'Was the EUS performed today? No' asks whether the service it "
                                  "names was done and answers no")
        an = detect._analysis(text, D)[0]
        self.assertTrue(detect._generic_reading(an, start, start + 3).doubt)
        # only a service named in the question's noun: an item's question ("Was the biopsy performed? No") is the
        # item's, and the words after the answer are no part of the question
        for row, phrase in (('Was the biopsy performed? No', 'biopsy'), ('EUS performed? No - the patient had eaten', 'patient')):
            with self.subTest(row=row):
                status, cues = read(EUS.format(row=row), phrase)
                self.assertFalse(any('asks whether the service it names was done' in c for c in cues), cues)

    def test_a_status_row_read_as_history_keeps_its_reading(self):
        """box2:L outside a positive section reads only a passage its words and section leave uncertain with no doubt: a
        dated row under "History:" stays historical, and today's colonoscopy stays performed."""
        text = (HEAD + 'Procedure: Colonoscopy\nHistory: Colonoscopy: \u2612 Incomplete \u2610 Completed in 2019.\nFindings: The '
                'colonoscope was advanced to the cecum.\n')
        start = text.index('History: ') + len('History: ')
        self.assertEqual(detect.status_for_span(text, start, start + len('Colonoscopy'), D)[0], 'historical')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_the_status_label_rows(self):
        for row in ('Colonoscopy?: \u2612 Pending \u2610 Completed', 'Colonoscopy?: \u2612 Incomplete \u2610 Completed',
                    'Colonoscopy status?: \u2612 Pending \u2610 Completed'):
            with self.subTest(row=row):
                self.assert_held(COLO_F.format(row=row), '45378', 'Procedure: Colonoscopy')
        for row in ('Colonoscopy: \u2612 Pending \u2610 Completed', 'Colonoscopy: \u2612 Incomplete \u2610 Completed',
                    'Colonoscopy: [x] On hold [ ] Completed', 'Colonoscopy status: \u2612 Pending \u2610 Completed'):
            with self.subTest(row=row):
                text = COLO_I.format(row=row)
                self.assert_held(text, '45378', 'Procedure: Colonoscopy')
                self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')

    def test_controls(self):
        for row in ('Was the EUS performed today? Yes', 'EUS performed? Yes', 'The EUS was performed today.',
                    'EUS performed: no complications.', 'EUS performed - no complications.', 'EUS performed? Unknown',
                    'Was the EGD performed today? No', 'Was the biopsy performed? No', 'Was the FNA performed? No'):
            with self.subTest(row=row):
                self.assertEqual(outcome(EUS.format(row=row), '43242', EUS_PHRASE), 'ready')
        for frame, row in ((COLO_F, 'Colonoscopy completed? Yes'), (COLO_F, 'Colonoscopy performed: no polyps were seen.'),
                           (COLO_I, 'Colonoscopy: \u2610 Pending \u2612 Completed'),
                           (COLO_I, 'Colonoscopy: \u2610 Incomplete \u2612 Completed')):
            with self.subTest(row=row):
                self.assertEqual(outcome(frame.format(row=row), '45378', 'Procedure: Colonoscopy'), 'ready')

    def test_the_answer_grammar(self):
        for line, noun in (('Was the EUS completed today? N/A', 'EUS'), ('EUS performed? NA', 'EUS'),
                           ('EUS performed? No (patient declined)', 'EUS'), ('EUS done: none.', 'EUS'),
                           ('Was the EUS with FNA performed today? No', 'EUS with FNA'), ('EUS performed - No', 'EUS')):
            with self.subTest(line=line):
                self.assertEqual(detect._B3_SERVICE_ANSWERED_NO.match(line).group('noun'), noun)
        for line in ('EUS performed: no complications', 'EUS performed - no complications.',
                     'Colonoscopy performed: no polyps were seen.', 'EUS performed? Yes', 'EUS performed? Unknown'):
            with self.subTest(line=line):
                self.assertIsNone(detect._B3_SERVICE_ANSWERED_NO.match(line))


# --- declared:10 -- the attestation's own box on the line above the separately identifiable E/M statement -----------

ATTEST_NOTE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nProcedure: Anoscopy with rubber '
               'band ligation of two internal hemorrhoids was performed today.\n{above}A significant, separately '
               'identifiable E/M service was performed today.\n{under}Medical decision making: moderate.\n')


def separate_em_fact(text):
    finding = detect.route(text, D).finding('gi.office_em')
    return next((f.value for f in (finding.facts if finding else ()) if f.name == 'separate_em'), None)


def visit_outcome(text):
    return outcome(text, '99214', 'Established patient office visit.')


class Declared10AttestationBoxAboveTests(Case):
    """declared:10 (medium, a residual at every base). "☐ Separate E/M attestation:" (or "☐ Attested", "Attested: ☐",
    "[ ] Attested", "Attested | [ ]") on the line ABOVE "A significant, separately identifiable E/M service was performed
    today.": only a lone box line above was read, so the statement attested (separate_em documented) and 99214 was
    READY beside the same-day anoscopy. The line above is now read as the line under is, when it is about the
    attestation (_B3_attestation_above_refuses): its own box unchecked, box2:F's refusals, a labelled answer naming the
    attestation that does not say yes ("Separate E/M attested: No": held at d05326ef, ready since 4347acd), a form field
    tied to it unchecked; one blank line may stand between. Only refusals (holds)."""

    UNCHECKED = ('\u2610 Separate E/M attestation:', '\u2610 Attested', 'Attested: \u2610', '[ ] Attested', 'Attested | [ ]',
                 'Notes: \u2610 Attested', '\u2610 Agree', '\u2610 Modifier 25', 'Separate E/M attested: No',
                 'Separate E/M attestation: No', 'Attested: No', 'Attestation: No', 'E/M attestation: Not attested',
                 '\u2612 Not attested', 'Attestation: pending', 'Attested - No', 'Separate E/M: \u2610 Yes \u2612 No',
                 'Attestation: Agree', 'Unattested', 'Not attested', '\u2612 Agree \u2610 Disagree', 'Modifier 25 not appended',
                 # 'Notes: Agree' is no longer here (round 4d integration, the verifier's new problem 2): a bare agree
                 # names no attestation, as "Consent: patient agrees." does not, so it leaves the statement attesting
                 'Notes: Not attested', 'Attestation: I do not attest to a separate service today, see note.',
                 'I cannot confirm that a separate service was provided.', 'The physician declined to attest.')
    CHECKED = ('\u2612 Separate E/M attestation:', '\u2612 Attested', 'Attested: \u2612', '[x] Attested', 'Attested | [x]',
               'Separate E/M attested: Yes', 'Attested - Yes', 'Attested: Yes', 'Separate E/M: \u2612 Yes \u2610 No')

    def test_the_claimed_rows(self):
        for line in self.UNCHECKED:
            for gap in ('\n', '\n\n'):
                with self.subTest(line=line, gap=gap):
                    text = ATTEST_NOTE.format(above=line + gap, under='')
                    self.assertIsNone(separate_em_fact(text))
                    self.assertEqual(visit_outcome(text), 'held')

    def test_the_checked_twins_attest(self):
        for line in self.CHECKED:
            with self.subTest(line=line):
                text = ATTEST_NOTE.format(above=line + '\n', under='')
                self.assertEqual(separate_em_fact(text), 'documented')
                self.assertEqual(visit_outcome(text), 'ready')

    def test_a_form_field_tied_to_the_line_above(self):
        """The printed label above the statement with no glyph, its PDF box in the page's form-field block."""
        for printed, field, attested in (('Attested', 'Attested: not checked', False), ('Attested', 'Attested: No', False),
                                         ('Attested', 'Attested: checked', True), ('Biopsy', 'Biopsy: not checked', True)):
            with self.subTest(printed=printed, field=field):
                text = ATTEST_NOTE.format(above=printed + '\n', under='') + f'\n[PDF form fields on page 1]\n{field}'
                self.assertEqual(separate_em_fact(text), 'documented' if attested else None)
                self.assertEqual(visit_outcome(text), 'ready' if attested else 'held')

    def test_a_line_above_of_no_attestation_stays_as_it_was(self):
        for line in ('\u2610 Labs reviewed', '\u2612 Labs reviewed', 'Allergies: None', 'Smoker: No', 'Attestation:',
                     '\u2610 Biopsy', 'Attested by: Dr. Smith', 'Modifier: 25', 'Significant findings: none.',
                     'E/M: established patient, no new problems.', 'Patient agrees with the plan.', 'Modifier 25 appended.',
                     'Attestation: I saw and examined the patient and agree with the resident note.',
                     'I attest that I personally performed the procedure.',
                     'I attest that I personally performed the procedure and no complications occurred.',
                     'Patient agrees with the plan and has no questions.', 'No other issues and I agree with the plan.'):
            with self.subTest(line=line):
                text = ATTEST_NOTE.format(above=line + '\n', under='')
                self.assertEqual(separate_em_fact(text), 'documented')
                self.assertEqual(visit_outcome(text), 'ready')


class Declared10AttestationBoxAboveFilesTests(unittest.TestCase):
    """declared:10 in real files: a fillable PDF whose 'Attested' check box, beside its printed label, stands on the line
    above the statement, and a Word check-box content control before "Separate E/M attestation:" in the paragraph above
    it; each with its checked twin, through the sandboxed extract_document, routing and the real engine."""

    def assert_attested(self, text, attested):
        from tests.test_repairs_r3_forms_routing import outcome as engine_outcome
        from tests.test_repairs_r4_boxes_pdf import ATTEST_PICKS
        from tests.test_repairs_status_r2_routing import clarified, routed, run_engine
        fact = next((f for f in routed(text).finding('gi.office_em').facts if f.name == 'separate_em'), None)
        proposals, _ = run_engine(text, ATTEST_PICKS)
        if attested:
            self.assertIsNotNone(fact, text[-300:])
            self.assertNotIn('separate_em', clarified(proposals['99214']))
        else:
            self.assertIsNone(fact, text[-300:])
            self.assertEqual(engine_outcome(proposals['99214']), 'held')
            self.assertIn('separate_em', clarified(proposals['99214']))

    def test_a_pdf_box_above_the_statement(self):
        from tests.test_repairs_r3_forms_pdf import extracted, text_line
        from tests.test_repairs_r4_boxes_pdf import ATTEST_OFFICE, ATTESTATION, page_form, row_y
        for checked in (False, True):
            for name, tu in (('Attested', None), ('Check Box1', 'Attested')):
                with self.subTest(checked=checked, name=name):
                    form = page_form(ATTEST_OFFICE)
                    y = row_y(ATTEST_OFFICE, len(ATTEST_OFFICE))
                    form.line(text_line(90, y, 'Attested'))
                    form.checkbox(name, (72, y - 3, 84, y + 9), checked, tu=tu)
                    form.line(text_line(72, row_y(ATTEST_OFFICE, len(ATTEST_OFFICE) + 1), ATTESTATION))
                    result = extracted(form.build())
                    self.assertEqual(result.status, 'ok', result.messages)
                    self.assertLess(result.text.index('Attested'), result.text.index(ATTESTATION))
                    self.assert_attested(result.text, checked)

    def test_a_word_box_above_the_statement(self):
        from tests.support import docgen
        from tests.test_repairs_r3_forms_docx import control, docx_result, paragraph
        from tests.test_repairs_r4_boxes_pdf import ATTEST_OFFICE, ATTESTATION
        for checked in (False, True):
            for label in (' Separate E/M attestation:', ' Attested'):
                with self.subTest(checked=checked, label=label):
                    body = ''.join(paragraph(line) for line in ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT',
                                                                'Date of service: 2026-10-21'] + ATTEST_OFFICE)
                    body += f'<w:p>{control(checked)}<w:r><w:t xml:space="preserve">{label}</w:t></w:r></w:p>'
                    body += paragraph(ATTESTATION)
                    result = docx_result(docgen.make_docx_from_body(body))
                    self.assertEqual(result.status, 'ok', result.messages)
                    self.assertIn(('\u2612' if checked else '\u2610') + label, result.text)
                    self.assert_attested(result.text, checked)


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
