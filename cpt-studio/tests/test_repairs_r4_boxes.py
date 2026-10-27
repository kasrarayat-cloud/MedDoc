"""Regressions for refutation round 4, BOXES lens: check boxes, unread marks, form-field lines and the separately
identifiable E/M attestation, as routing reads them.

Each class reproduces one confirmed finding (routing:N, release:N, structure:N, contract:N or evidence:N in the round-4
triage) from its exact input, adds the variants the finding and its verifier list, and pins the positive controls an
over-correction would break. Routing runs for real, for the document's own service date and through the JSON round
trip the pipeline applies; the real validation engine assesses provider-shaped selections.

The hold-only rule (round-4b contract, section 1) governs every rule here: a wording or layout rule may move a reading
only to uncertain (a hold with a non-silent cue). The one box vocabulary (section 2) is defined once, in
studio.ingest.symbols, and every reader derives its patterns from it. Synthetic text only.
"""
import time
import unittest

from studio.gi import detect, sections
from studio.gi.detect import route, status_for_span
from studio.ingest import symbols
from tests.test_repairs_status_r2_routing import (BOXED, HEADER, SILENT, clarified, fact_value, family, read, routed,
                                                  run_engine, span)
from tests.test_repairs_r3_forms_routing import not_silent, outcome

NBSP, EN_SPACE, NARROW_NBSP = chr(0xA0), chr(0x2002), chr(0x202F)
NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')


def cues_of(text, phrase, occurrence=0):
    return read(text, phrase, occurrence)[1]


def pick(text, code, phrase, occurrence=0):
    proposals, _ = run_engine(text, [(code, phrase, occurrence)])
    return proposals[code]


class BoxCase(unittest.TestCase):
    maxDiff = None

    def assert_outcome(self, text, code, phrase, wanted, occurrence=0):
        proposal = pick(text, code, phrase, occurrence)
        got = outcome(proposal)
        if isinstance(wanted, (tuple, list)):
            self.assertIn(got, wanted, (code, phrase, proposal.exclusion_reason,
                                        [c.detail for c in proposal.checks], text[-200:]))
        else:
            self.assertEqual(got, wanted, (code, phrase, proposal.exclusion_reason,
                                           [c.detail for c in proposal.checks], text[-200:]))
        return proposal

    def assert_held_reading(self, text, phrase, occurrence=0):
        status, cues = read(text, phrase, occurrence)
        self.assertEqual(status, 'uncertain', (phrase, cues, text[-200:]))
        self.assertTrue(not_silent(cues), cues)
        return cues


# --- the one vocabulary ------------------------------------------------------------------------------------------

class OneBoxVocabularyTests(unittest.TestCase):
    """Contract section 2: routing, the section reader and the PDF reader build their box patterns from
    studio.ingest.symbols, so a spelling one of them reads is never a spelling another passes over."""

    def test_routing_reads_every_box_shape_symbols_lists(self):
        """Its established box glyphs as boxes; the other unchecked shapes, a bullet as often as a box, as unread."""
        for glyph, box in symbols._BOX_SHAPES.items():
            with self.subTest(glyph=hex(ord(glyph))):
                if glyph in symbols.BOX_HELD_GLYPHS:
                    self.assertIsNone(detect._BOX.fullmatch(glyph))
                    self.assertIsNotNone(detect._BOX_UNREAD.fullmatch(glyph))
                    continue
                match = detect._BOX.fullmatch(glyph)
                self.assertIsNotNone(match)
                self.assertEqual('off' if match.group('off') else 'on', 'off' if box == symbols.UNCHECKED_BOX else 'on')

    def test_every_typed_box_routing_reads_is_a_printed_box_when_unchecked(self):
        from studio.ingest.pdf import PRINTED_BOX
        for typed in ('[ ]', '[  ]', '[\t]', '[' + NBSP + ']', '[]', '[_]', '( )', '(  )', '(\t)', '☐', '□', '❑', '◻', '◽'):
            with self.subTest(typed=typed):
                self.assertEqual(detect._BOX.fullmatch(typed).group('off'), typed)
                self.assertEqual(PRINTED_BOX.fullmatch(typed).group('off'), typed)
        for typed in symbols.BOX_HELD_GLYPHS:  # unread when typed, replaced by a widget's state when printed under one
            with self.subTest(typed=hex(ord(typed))):
                self.assertTrue(detect._BOX_UNREAD.fullmatch(typed))
                self.assertEqual(PRINTED_BOX.fullmatch(typed).group('off'), typed)
        for typed in ('☒', '[x]', '[X]'):
            self.assertEqual(PRINTED_BOX.fullmatch(typed).group('on'), typed)

    def test_the_unread_mark_extraction_writes_is_read_as_unread(self):
        self.assertTrue(detect._BOX_UNREAD.fullmatch(symbols.BOX_UNREAD_MARK))
        self.assertIsNone(detect._BOX.fullmatch(symbols.BOX_UNREAD_MARK))
        text = BOXED + symbols.BOX_UNREAD_MARK + ' Biopsy\n☒ Cold snare polypectomy\n'
        self.assertEqual(read(text, 'Biopsy')[1], (detect.BOX_UNREAD,))

    def test_the_option_row_guard_reads_every_routing_box(self):
        for mark in ('[' + NBSP + ']', '[ x ]', '(' + EN_SPACE + ')', '(•)', '[?]', '(*)', '[N]', '{ }', '○', '◉',
                     '▢', '⬜', '☑'):
            with self.subTest(mark=mark):
                self.assertTrue(sections._OPTION_ROW.search(f'Biopsy taken [x] Yes {mark} No'))


# --- routing:0 / release:0 -- a status line with a checked cancel option is a statement -------------------------------

EUS_NOTE = (HEADER + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\n{row}\nIndication: Pancreatic '
            'head mass on CT.\n')
EUS_LINE = 'EUS with fine-needle biopsy of the pancreatic head mass.'
RELEASE0_NOTE = (HEADER + 'Procedure: EUS of the pancreatic head mass with fine-needle biopsy\n{row}\nIndication: 3 cm '
                 'pancreatic head mass on CT.\n{tail}')
RELEASE0_LINE = 'EUS of the pancreatic head mass with fine-needle biopsy'


class Routing0CheckedCancelOptionTests(BoxCase):
    """routing:0 and release:0 (critical, new in 82e9692c9). _unchecked_option judged a status line by its first box,
    so a line whose 'Cancelled' option is checked read as an option nobody selected, and the cancelled EUS was a ready
    43242. A line is an unselected option only when every denying option on it has its own unchecked box."""
    ROWS = ('Procedure status: ☐ Completed ☒ Cancelled', 'Completed ☐ | Cancelled ☒', 'Completed: ☐ Cancelled: ☒',
            'Procedure status: [ ] Completed [x] Cancelled [ ] Aborted', 'Procedure status: [ ] Completed [x] Cancelled',
            'Status: ☐ Completed ☒ Cancelled', 'Status: [ ] Done [x] Cancelled', '[ ] Completed [x] Cancelled [ ] Aborted')

    def test_the_claimed_rows_never_ready_the_eus(self):
        for row in self.ROWS:
            with self.subTest(row=row):
                text = EUS_NOTE.format(row=row)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                self.assert_outcome(text, '43242', EUS_LINE, ('held', 'excluded'))

    def test_release0_surroundings(self):
        for row in ('Procedure status: ☐ Completed ☒ Cancelled', 'Procedure status: [ ] Completed [x] Cancelled'):
            for tail in ('Plan: Follow pathology.\n', '', 'Plan: Rebook the EUS after NPO instructions.\n',
                         'Reason: Patient had eaten breakfast.\n'):
                with self.subTest(row=row, tail=tail):
                    text = RELEASE0_NOTE.format(row=row, tail=tail)
                    self.assert_outcome(text, '43242', RELEASE0_LINE, ('held', 'excluded'))
        fna = (HEADER + 'Procedure: EUS of the pancreatic head mass with fine-needle aspiration\nProcedure status: ☐ '
               'Completed ☒ Cancelled\nIndication: 3 cm pancreatic head mass on CT.\n')
        self.assert_outcome(fna, '43242', 'EUS of the pancreatic head mass with fine-needle aspiration', ('held', 'excluded'))
        below = (HEADER + 'Procedure: EUS of the pancreatic head mass with fine-needle biopsy\nIndication: 3 cm pancreatic '
                 'head mass on CT.\nProcedure status: ☐ Completed ☒ Cancelled\n')
        self.assert_outcome(below, '43242', RELEASE0_LINE, ('held', 'excluded'))

    def test_a_status_line_read_both_ways_is_a_statement(self):
        """Its first option comes before its first box and its last after its last: which box is whose cannot be told."""
        self.assert_outcome(EUS_NOTE.format(row='Cancelled ☐ Completed ☒ Postponed'), '43242', EUS_LINE, 'held')

    def test_a_status_field_answered_with_a_denial_is_a_statement(self):
        """release:0's form-field line: a neutral label answered 'Not performed' was skipped as an unselected option."""
        text = (HEADER + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\nProcedure status:\n\n'
                '[PDF form fields on page 1]\nProcedure status: Not performed')
        self.assertNotEqual(family(text, 'gi.eus'), 'performed')
        self.assert_outcome(text, '43242', EUS_LINE, 'held')

    def test_a_trailing_status_row_beyond_the_further_denials_is_held(self):
        """Only the reference reader sees a status row more than six sentences down; its trailing boxes are read
        against its option words, so the checked 'Procedure cancelled ☒' is never taken for the unchecked one before."""
        text = (HEADER + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\nIndication: Pancreatic head mass '
                'on CT.\nHistory reviewed.\nConsent obtained.\nASA class II.\nAirway assessed.\nAllergies: none known.\n'
                'Anticoagulants: none.\nNPO since midnight.\nProcedure completed ☐ | Procedure cancelled ☒\n')
        self.assertNotEqual(family(text, 'gi.eus'), 'performed')
        self.assert_outcome(text, '43242', EUS_LINE, 'held')

    def test_the_three_option_row_is_held_through_its_unchecked_abort(self):
        """'[ ] Aborted' is an unchecked reference, skipped as no statement; its line's checked 'Cancelled' holds."""
        text = EUS_NOTE.format(row='Procedure status: [ ] Completed [x] Cancelled [ ] Aborted')
        reference = next(m for m in routed(text).finding('gi.eus').mentions if m.span.text == 'Aborted')
        self.assertEqual(reference.status, 'uncertain', reference.cues)
        self.assertTrue(not_silent(reference.cues), reference.cues)

    def test_controls(self):
        # a checked cancel option first, as before
        self.assert_outcome(EUS_NOTE.format(row='Procedure status: ☒ Cancelled ☐ Completed'), '43242', EUS_LINE, 'held')
        # the mirror row stays at most held (a medium over-hold the hold-only repair leaves in place), never excluded
        for row in ('Procedure status: ☒ Completed ☐ Cancelled', '☒ Procedure completed ☐ Procedure cancelled'):
            with self.subTest(row=row):
                self.assert_outcome(EUS_NOTE.format(row=row), '43242', EUS_LINE, ('ready', 'held'))
        # unchecked cancel options on lines of their own still state nothing
        for row in ('Procedure completed | ☒\nProcedure cancelled | ☐', '☒ Procedure completed\n☐ Procedure cancelled',
                    'Procedure completed: ☒\nProcedure cancelled: not checked', 'Procedure cancelled: [ ] Yes [x] No'):
            with self.subTest(row=row):
                text = EUS_NOTE.format(row=row)
                self.assertEqual(family(text, 'gi.eus'), 'performed')
                self.assert_outcome(text, '43242', EUS_LINE, 'ready')


# --- structure:13 -- a status option answered No holds, never cancels -------------------------------------------------

COLON_NOTE = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n{rows}\nFindings: The colonoscope was advanced to '
              'the cecum. A 6 mm polyp was removed with a cold snare.\n')
POLYP = 'A 6 mm polyp was removed with a cold snare.'


class Structure13StatusAnswerTests(BoxCase):
    """structure:13 (critical). A typed status answer 'Procedure cancelled: No' cancelled a completed colonoscopy (45385
    excluded) and 'Procedure aborted: No' marked it incomplete. A status option answered with a denial holds the family;
    it never cancels or aborts it."""
    ANSWERED = ('Procedure completed: Yes\nProcedure cancelled: No', 'Procedure cancelled: No', 'Procedure cancelled? No',
                'Procedure cancelled - no', 'Procedure cancelled  No', 'Procedure cancelled: N', 'Procedure cancelled: No.',
                'Procedure cancelled: None', 'Procedure cancelled | No', 'Was the procedure cancelled? No',
                'Procedure aborted: No', 'Procedure completed: Yes\nProcedure aborted: No', '- Procedure cancelled: No')

    def test_the_claimed_answers_hold(self):
        for rows in self.ANSWERED:
            with self.subTest(rows=rows):
                text = COLON_NOTE.format(rows=rows)
                self.assertNotIn(family(text, 'gi.colonoscopy'), ('cancelled', 'negated', 'incomplete'))
                self.assert_outcome(text, '45385', POLYP, ('held', 'ready'))

    def test_an_abort_answered_no_after_the_scope_went_in(self):
        """'Case aborted' is a bare abort with its subject before it: answered No it holds, never reads incomplete."""
        text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: A 6 mm polyp was removed with a cold '
                'snare. The colonoscope was advanced to the cecum.\nCase aborted: No\n')
        self.assertNotIn(family(text, 'gi.colonoscopy'), ('cancelled', 'negated', 'incomplete'))
        self.assert_outcome(text, '45385', POLYP, ('held', 'ready'))

    def test_a_form_block_answer_holds_never_cancels(self):
        text = COLON_NOTE.format(rows='') + '\n[PDF form fields on page 1]\nProcedure cancelled: No'
        self.assertNotIn(family(text, 'gi.colonoscopy'), ('cancelled', 'negated'))
        self.assert_outcome(text, '45385', POLYP, ('held', 'ready'))

    def test_real_cancellations_still_cancel(self):
        for rows in ('Procedure cancelled: Yes', 'Procedure cancelled.', 'Procedure cancelled, no sedation given.',
                     'Procedure cancelled - no IV access.', 'Procedure cancelled: no driver available.'):
            with self.subTest(rows=rows):
                self.assertEqual(family(COLON_NOTE.format(rows=rows), 'gi.colonoscopy'), 'cancelled')

    def test_the_boxed_and_block_forms_are_unchanged(self):
        for rows in ('Procedure cancelled: [ ] Yes [x] No', 'Procedure cancelled: [ ]', 'Procedure cancelled: not checked'):
            with self.subTest(rows=rows):
                text = COLON_NOTE.format(rows=rows)
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assert_outcome(text, '45385', POLYP, 'ready')


# --- structure:15 -- a yes/no pair with both options checked holds ----------------------------------------------------

class Structure15BothOptionsCheckedTests(BoxCase):
    """structure:15 (high). A yes/no pair with both options checked was negated with the false cue 'negated: an unchecked
    box'. Both options marked are boxes that disagree: the item is held (BOXES_DISAGREE)."""

    def test_the_claimed_rows_hold(self):
        for row in ('Biopsy taken: ☒ Yes ☒ No', 'Biopsy taken: Yes ☒ No ☒', 'Biopsy taken: [x] Yes [x] No',
                    'Biopsy: ☒ Done ☒ Not done', 'Biopsy taken: ☒ No ☒ Yes'):
            with self.subTest(row=row):
                text = BOXED + row + '\nCold snare polypectomy ☒\n'
                self.assertEqual(self.assert_held_reading(text, 'Biopsy'), (detect.BOXES_DISAGREE,))
                self.assert_outcome(text, '45380', 'Biopsy', 'held')

    def test_a_cancel_option_with_both_answers_checked_holds_the_procedure(self):
        text = COLON_NOTE.format(rows='Procedure cancelled: ☒ Yes ☒ No')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
        self.assert_outcome(text, '45385', POLYP, 'held')

    def test_single_marked_pairs_are_unchanged(self):
        self.assert_outcome(BOXED + 'Biopsy taken: ☒ Yes ☐ No\nCold snare polypectomy ☒\n', '45380', 'Biopsy', 'ready')
        self.assert_outcome(BOXED + 'Biopsy taken: ☐ Yes ☒ No\nCold snare polypectomy ☒\n', '45380', 'Biopsy', 'excluded')


# --- structure:0 -- a remark after the last box never makes the boxes lead ----------------------------------------------

S0_NOTE = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm sigmoid polyp was '
           'found.\n{row}\n')


class Structure0RemarkAfterTheLastBoxTests(BoxCase):
    """structure:0 (critical). Under a service or a label, a remark written after the last box made the boxes lead, so the
    unchecked biopsy was ready and the checked polypectomy excluded. Where the boxes can be read both as leading and as
    trailing their items, an item the two readings disagree about is held (BOXES_DISAGREE)."""
    ROWS = ('Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed',
            'colonoscopy: biopsy [ ] cold snare polypectomy [x] clip placed',
            'Colonoscopy - Biopsy ☐ Cold snare polypectomy ☒ clip placed',
            'Colonoscopy ☒ Biopsy ☐ Cold snare polypectomy ☒ clip placed',
            'Colonoscopy\tBiopsy ☐\tCold snare polypectomy ☒\tclip placed',
            'Colonoscopy: Biopsy ☐ Cold snare polypectomy [x] tattoo placed distal to the site',
            'Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒  polypectomy site clipped',
            'Colonoscopy with Biopsy ☐ Cold snare polypectomy ☒ clip placed')

    def test_the_claimed_rows(self):
        for row in self.ROWS:
            with self.subTest(row=row):
                text = S0_NOTE.format(row=row)
                biopsy = 'biopsy' if 'biopsy [' in row else 'Biopsy'
                snare = 'cold snare polypectomy' if 'cold snare' in row else 'Cold snare polypectomy'
                self.assertNotEqual(read(text, biopsy)[0], 'performed')
                self.assertNotEqual(read(text, snare)[0], 'negated')
                self.assert_outcome(text, '45380', biopsy, ('held', 'excluded'))
                self.assert_outcome(text, '45385', snare, ('held', 'ready'))

    def test_items_both_readings_agree_on_are_not_held(self):
        """Round 4d BOXES3 (contract-r4d section 4, strict check-box rows): a row whose boxes can be read leading or
        trailing cannot be paired in exactly one way, so what its boxes may govern is held: the remark after the last
        box too ("clip", which the leading reading gives the last box), and a service before the first box with no
        separator ("Colonoscopy ☒", which the trailing reading gives the first box). A service label ended by its colon
        before the first entry is no reading's entry, so it reads as before."""
        text = S0_NOTE.format(row='Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed')
        self.assertEqual(read(text, 'Colonoscopy', 1)[0], 'performed')
        self.assertEqual(read(text, 'clip')[0], 'uncertain')
        text = S0_NOTE.format(row='Colonoscopy ☒ Biopsy ☐ Cold snare polypectomy ☒ clip placed')
        self.assertEqual(read(text, 'Colonoscopy', 1)[0], 'uncertain')
        self.assertEqual(read(text, 'clip')[0], 'uncertain')

    def test_the_egd_row(self):
        text = S0_NOTE.format(row='EGD: Biopsy ☐ Balloon dilation ☒ dilation to 15 mm')
        self.assertNotEqual(read(text, 'Biopsy')[0], 'performed')
        self.assertNotEqual(read(text, 'Balloon dilation')[0], 'negated')

    def test_rows_with_one_reading_are_unchanged(self):
        for row, biopsy, snare in (('Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒', 'negated', 'performed'),
                                   ('Colonoscopy: [ ] biopsy [x] cold snare', 'negated', 'performed'),
                                   ('Colonoscopy with ☐ biopsy ☒ cold snare', 'negated', 'performed'),
                                   # round 4d BOXES3 (strict rows; round 6 declared:8): an item's label pairs both ways
                                   ('Polypectomy: [ ] biopsy [x] cold snare', 'uncertain', 'uncertain'),
                                   ('☐ Biopsy ☒ Cold snare polypectomy | clip placed', 'negated', 'performed'),
                                   ('Biopsy | ☐ | Cold snare polypectomy | ☒ | clip placed', 'negated', 'performed'),
                                   ('Biopsy: [ ] Cold snare polypectomy: [x] clip placed', 'negated', 'performed'),
                                   ('Colonoscopy: ☐ biopsy: sigmoid ☒ cold snare', 'negated', 'performed'),
                                   ('Colonoscopy, ☐ biopsy ☒ cold snare', 'negated', 'performed')):
            with self.subTest(row=row):
                text = S0_NOTE.format(row=row)
                b = 'biopsy' if 'biopsy' in row and 'Biopsy' not in row else 'Biopsy'
                s = 'cold snare' if 'cold snare' in row else 'Cold snare polypectomy'
                self.assertEqual((read(text, b)[0], read(text, s)[0]), (biopsy, snare))


# --- structure:16 -- a trailing box after a label joined by 'with', ';' or 'plus' --------------------------------------

class Structure16TrailingBoxAfterAJoinedLabelTests(BoxCase):
    """structure:16 (critical). A trailing box after 'Polypectomy with cold snare' governed only 'cold snare', so the
    polypectomy under the unchecked box was ready. An intervention with no box of its own, joined by 'with', 'w/', ';' or
    'plus' to a later item whose box is not checked, is held (the box later on its line may govern it)."""
    ROWS = (('Polypectomy with cold snare | ☐', 'Polypectomy', '45385'),
            ('Cold snare polypectomy with clip placement | ☐', 'Cold snare polypectomy', '45385'),
            ('Hot snare polypectomy with hemoclip: [ ]', 'Hot snare polypectomy', '45385'),
            ('Polypectomy with cold snare: ☐', 'Polypectomy', '45385'),
            ('Polypectomy with cold snare ☐', 'Polypectomy', '45385'),
            ('Biopsy; polypectomy | ☐', 'Biopsy', '45380'),
            ('Biopsy plus polypectomy: ☐', 'Biopsy', '45380'),
            ('Polypectomy w/ cold snare | ☐', 'Polypectomy', '45385'))

    def test_the_claimed_rows_never_ready_the_first_item(self):
        for row, phrase, code in self.ROWS:
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                self.assertEqual(self.assert_held_reading(text, phrase), (detect.BOX_LATER,))
                self.assert_outcome(text, code, phrase, 'held')

    def test_a_checklist_of_joined_labels(self):
        text = BOXED + 'Biopsy with cold forceps: ☐\nPolypectomy with cold snare: ☐\nNone: ☒\n'
        self.assert_outcome(text, '45385', 'Polypectomy', 'held')
        self.assert_outcome(text, '45380', 'Biopsy', ('held', 'excluded'))  # 'cold forceps' is no item: the box is its

    def test_controls(self):
        self.assert_outcome(BOXED + 'Polypectomy with cold snare | ☒\n', '45385', 'Polypectomy', 'ready')
        self.assert_outcome(BOXED + 'Polypectomy | ☐\n', '45385', 'Polypectomy', 'excluded')
        self.assert_outcome(BOXED + 'Polypectomy with cold snare\n', '45385', 'Polypectomy', 'ready')
        # a service name opening the line is described with its intervention, as round 3b pinned
        text = HEADER + 'Procedure: Colonoscopy with biopsy ☐\nFindings: The colonoscope was advanced to the cecum.\n'
        self.assertEqual((read(text, 'Colonoscopy')[0], read(text, 'biopsy')[0]), ('performed', 'negated'))
        for row in ('Biopsy | ☐ | Cold snare polypectomy | ☒ | clip placed', 'Colonoscopy: ☒ Biopsy: ☐'):
            with self.subTest(row=row):
                self.assertEqual(read(BOXED + row + '\n', 'Biopsy')[0], 'negated')


# --- structure:10 / contract:6 -- a mark outside both lists is unread, never passed over --------------------------------

class Structure10UnreadMarkTests(BoxCase):
    """structure:10 and contract:6 (critical). Marks outside both declared lists ('[-]', '[N]', '[Y]', '{ }', '< >', a
    pair of bare radio glyphs) were passed over: an unchecked biopsy was ready, or a checked polypectomy took the
    biopsy's empty box. Such a mark is unread: it holds the item it marks and is never passed over."""

    def test_the_claimed_rows_hold_the_biopsy(self):
        for rows in ('Interventions: [-] Biopsy [x] Cold snare polypectomy', '○ Biopsy ● Cold snare polypectomy',
                     '{ } Biopsy {x} Cold snare polypectomy', '< > Biopsy <x> Cold snare polypectomy',
                     'Biopsy [N] Cold snare polypectomy [Y]', 'Interventions:\n[N] Biopsy\n[Y] Cold snare polypectomy',
                     'Interventions:\n[-] Biopsy\n[x] Cold snare polypectomy', '[n] Biopsy [y] Cold snare polypectomy',
                     'Biopsy: [N]', 'Biopsy taken: [Y] [N]', 'Biopsy [-]'):
            with self.subTest(rows=rows):
                text = BOXED + rows + '\n'
                self.assertNotEqual(read(text, 'Biopsy')[0], 'performed')
                self.assert_outcome(text, '45380', 'Biopsy', 'held')
                self.assertNotIn('biopsy', fact_value(text, 'gi.colonoscopy', 'interventions') or '')

    def test_a_neighbours_empty_box_is_never_handed_over(self):
        for rows in ('[ ] Biopsy [Y] Cold snare polypectomy', '[ ] Biopsy [+] Cold snare polypectomy',
                     '[ ] Biopsy {x} Cold snare polypectomy', '[ ] Biopsy <x> Cold snare polypectomy',
                     '( ) Biopsy (Y) Cold snare polypectomy'):
            with self.subTest(rows=rows):
                text = BOXED + rows + '\n'
                self.assertEqual(read(text, 'Biopsy')[0], 'negated')
                self.assertNotEqual(read(text, 'Cold snare polypectomy')[0], 'negated')
                self.assert_outcome(text, '45385', 'Cold snare polypectomy', 'held')

    def test_ordinary_brackets_and_bullets_are_not_marks(self):
        for row in ('Biopsy (x2) of the sigmoid colon', 'Biopsy (sigmoid) [sic]', 'Biopsy (1) and polypectomy (2)',
                    'Biopsy for H. pylori (-)', 'Cold snare polypectomy (+) margin', 'Biopsy(s) of the sigmoid',
                    'Biopsy (a) and (b)', 'Biopsy (or brushing) of the sigmoid', '● Biopsy', '○ Biopsy', '• Biopsy',
                    'Biopsy [1]', 'Biopsy (N=2)', 'Biopsy, size <5 mm', 'Biopsy {sigmoid}'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                phrase = 'Biopsy' if 'Biopsy' in row else 'Cold snare polypectomy'
                self.assertEqual(read(text, phrase)[0], 'performed')

    def test_bulleted_lists_are_unchanged(self):
        for bullet in ('●', '○', '•', '-'):
            with self.subTest(bullet=bullet):
                text = BOXED + f'{bullet} Biopsy\n{bullet} Cold snare polypectomy\n'
                self.assert_outcome(text, '45380', 'Biopsy', 'ready')
                # a bullet before an item with a trailing box is no mark: the box decides
                boxed = BOXED + f'{bullet} Biopsy ☐\n{bullet} Cold snare polypectomy ☒\n'
                self.assertEqual((read(boxed, 'Biopsy')[0], read(boxed, 'Cold snare polypectomy')[0]),
                                 ('negated', 'performed'))
        # an answer in parentheses on a bulleted line with no box is ordinary text
        self.assertEqual(read(BOXED + '● Biopsy for H. pylori (-)\n', 'Biopsy')[0], 'performed')


# --- structure:14 -- an option row never runs on, whatever box or mark it uses -------------------------------------

S14_NOTE = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope was advanced to the '
            'cecum.\n{row}\nCold snare polypectomy of a 6 mm sigmoid polyp was performed.\n')
S14_SNARE = 'Cold snare polypectomy of a 6 mm sigmoid polyp was performed.'


class Structure14OptionRowTests(BoxCase):
    """structure:14 (critical). The section reader's option-row guard had its own, narrower box list, so an option row
    padded with other spaces or marked with an unread mark ran on into the next line, and its 'No' negated the performed
    polypectomy there. The guard is built from the one vocabulary."""

    def test_the_claimed_rows(self):
        for row in ('Biopsy taken [x] Yes [' + NBSP + '] No', 'Biopsy taken ( ) Yes (•) No', 'Biopsy taken ☐ Yes ◉ No',
                    'Biopsy taken [ x ] Yes [' + NBSP + '] No', 'Biopsy taken (x) Yes (' + EN_SPACE + ') No',
                    'Biopsy taken: [x] Yes [' + NARROW_NBSP + '] No', 'Biopsy taken ( ) Yes (*) No',
                    'Biopsy taken ( ) Yes (o) No', 'Biopsy taken [ ] Yes [?] No', 'Biopsy taken [ ] Yes [/] No',
                    'Biopsy taken ( ) Yes (●) No', 'Biopsy taken ○ Yes ● No', 'Biopsy taken [x] Yes [ ]' + NBSP + 'No',
                    'Biopsy taken [ ] Yes [N] No'):
            with self.subTest(row=row):
                text = S14_NOTE.format(row=row)
                self.assertEqual(read(text, S14_SNARE)[0], 'performed')
                self.assert_outcome(text, '45385', S14_SNARE, 'ready')

    def test_a_line_that_is_no_option_row_still_runs_on(self):
        self.assertTrue(sections._soft_wrap('There were no\nPolyps seen.', (0, 13), (14, 26)))
        self.assertFalse(sections._soft_wrap('Biopsy taken [ ] Yes [?] No\nPolyps seen.', (0, 27), (28, 40)))


# --- release:12 -- box shapes symbols lists, and N / 0 answers -----------------------------------------------------

class Release12BoxShapesAndShortAnswersTests(BoxCase):
    """release:12 (critical). Box glyphs that symbols.py lists (U+25A2, U+2B1C), pasted or typed, read as no state, and
    a form field answered 'N' or '0' read silent: the biopsy not taken was a ready 45380."""

    def test_pasted_box_shapes(self):
        """Never ready: held as unread marks (typed, these shapes are a bullet as often as a box)."""
        for rows in ('▢ | Biopsy\n☑ | Cold snare polypectomy', '⬜ Biopsy\n✔ Cold snare polypectomy', 'Biopsy | ▢\n'
                     'Cold snare polypectomy | ☒', '\U0001f78e Biopsy\n\U0001f5f9 Cold snare polypectomy'):
            with self.subTest(rows=rows):
                text = BOXED + rows + '\n'
                self.assertEqual(read(text, 'Biopsy')[1], (detect.BOX_UNREAD,))
                self.assert_outcome(text, '45380', 'Biopsy', 'held')
                self.assert_outcome(text, '45385', 'Cold snare polypectomy', 'ready')

    def test_a_decorative_square_bullet_never_excludes(self):
        text = (HEADER + 'Procedure:\n⬜ Colonoscopy with cold snare polypectomy\nFindings: The colonoscope was advanced to '
                'the cecum.\n')
        self.assertNotIn(family(text, 'gi.colonoscopy'), NOT_TODAY)
        self.assert_outcome(text, '45385', 'Colonoscopy with cold snare polypectomy', ('held', 'ready'))

    def test_short_answers_hold(self):
        page = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 5 mm polyp was '
                'found.\n{printed}\n\n[PDF form fields on page 1]\n{field}')
        for printed, field in (('Biopsy (Y/N):', 'Biopsy (Y/N): N'), ('Number of biopsies:', 'Number of biopsies: 0'),
                               ('Biopsy:', 'Biopsy: N'), ('Biopsy:', 'Biopsy: N/A')):
            with self.subTest(field=field):
                text = page.format(printed=printed, field=field)
                for phrase in (printed, field):
                    self.assert_held_reading(text, phrase)
                    self.assert_outcome(text, '45380', phrase, 'held')

    def test_a_yes_and_ordinary_values_stay_silent(self):
        page = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 5 mm polyp was '
                'biopsied.\nBiopsy (Y/N):\n\n[PDF form fields on page 1]\nBiopsy (Y/N): {value}')
        for value in ('Y', 'Yes'):
            with self.subTest(value=value):
                self.assert_outcome(page.format(value=value), '45380', 'A 5 mm polyp was biopsied.', 'ready')


# --- form-field lines: structure:6, structure:7, contract:2, evidence:4 -------------------------------------------

OFFICE_FLEX = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit for rectal bleeding.\nChief '
               'complaint: Rectal bleeding.\nAssessment: Hematochezia.\nMedical decision making: moderate.\nTotal time: 32 '
               'minutes.\nProcedure: Flexible sigmoidoscopy with biopsy. The sigmoidoscope was advanced to 40 cm.\nBiopsies '
               'were taken from the rectum.\n{printed}\n[PDF form fields on page 1]\n{field}')
VISIT = 'Established patient office visit for rectal bleeding.'


def unproposed(result):
    return next(c for c in result.encounter_checks if c.id == 'services.unproposed')


def missed_flex_sig(case, result):
    """Engine @4: a performed service of a family the documented-service inventory reconciles is reported missing by
    services.unresolved (services.unproposed leaves those families to it: engine._missed), so the office note's
    same-day flexible sigmoidoscopy with no proposal keeps its warning there."""
    unresolved = next(c for c in result.encounter_checks if c.id == 'services.unresolved')
    case.assertEqual(unresolved.status, 'warn', unresolved.detail)
    case.assertEqual([(u['family'], u['act'], u['reason']) for u in result.completeness['unresolved_items']],
                     [('gi.flex_sig', '', 'no_proposal')])


def held_for_its_interventions_only(case, proposal):
    """Engine @4 (services.base_included): the diagnostic 45378 beside the documented snare removal is held for that
    question alone. The field holds nothing: the documented colonoscopy passes its status check, no performed-status
    question is asked (as a page hold would ask), and a field's denial is never read as a done intervention."""
    case.assertEqual([c.fact for c in proposal.clarifications], ['base_included'])
    case.assertEqual(next(c for c in proposal.checks if c.id == 'service.status').status, 'pass')
    included = next(c for c in proposal.checks if c.id == 'services.base_included')
    case.assertIn('includes snare removal, which', included.detail)


class Structure6QualifiedFieldLabelTests(BoxCase):
    """structure:6 (critical, new in 686d60b11). A form field answering 'No' or 'None' to another question whose label
    names the service ('Flexible sigmoidoscopy in the last 10 years: No', '... complications: None') negated the family,
    releasing the office E/M beside a same-day flexible sigmoidoscopy. Such a denial is about another time or attribute:
    the field holds the item, never negates it."""
    FIELDS = (('Flexible sigmoidoscopy in the last 10 years:\n', 'Flexible sigmoidoscopy in the last 10 years: No'),
              ('', 'Flexible sigmoidoscopy in the last 10 years: No'),
              ('Flexible sigmoidoscopy complications:\n', 'Flexible sigmoidoscopy complications: None'),
              ('Prior flexible sigmoidoscopy:\n', 'Prior flexible sigmoidoscopy: No'))

    def test_the_office_e_m_stays_held(self):
        for printed, field in self.FIELDS:
            with self.subTest(field=field, printed=bool(printed)):
                text = OFFICE_FLEX.format(printed=printed, field=field)
                self.assertNotIn(family(text, 'gi.flex_sig'), NOT_TODAY)
                proposals, result = run_engine(text, [('99214', VISIT)])
                self.assertEqual(outcome(proposals['99214']), 'held')
                self.assertIn('separate_em', clarified(proposals['99214']))
                self.assertNotEqual(read(text, field)[0], 'negated')
                if printed:  # tied to its printed label: only the field's own passages are held, as at d05326ef
                    self.assertEqual(family(text, 'gi.flex_sig'), 'performed')
                    missed_flex_sig(self, result)

    def test_a_colonoscopy_reports_complications_field(self):
        text = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp '
                'was removed with a cold snare.\nColonoscopy complications:\n\n[PDF form fields on page 1]\nColonoscopy '
                'complications: None')
        self.assertNotIn(family(text, 'gi.colonoscopy'), NOT_TODAY)
        self.assert_outcome(text, '45385', 'A 6 mm sigmoid polyp was removed with a cold snare.', ('ready', 'held'))

    def test_a_yes_and_an_item_answer_are_unchanged(self):
        text = OFFICE_FLEX.format(printed='Flexible sigmoidoscopy in the last 10 years:\n',
                                  field='Flexible sigmoidoscopy in the last 10 years: Yes')
        self.assertEqual(family(text, 'gi.flex_sig'), 'performed')
        page = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp '
                'was seen.\nInterventions:\nBiopsy\nCold snare polypectomy\n\n[PDF form fields on page 1]\n{field}\nCold '
                'snare polypectomy: checked')
        for field in ('Biopsy: No', 'Biopsy: None', 'Biopsy: Not done', 'Biopsy: not checked'):
            with self.subTest(field=field):
                text = page.format(field=field)
                self.assertEqual(read(text, 'Biopsy')[0], 'negated')
                self.assert_outcome(text, '45380', 'Biopsy', 'excluded')


EV4_PAGE = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp was '
            'removed with a cold snare.\n{printed}\n\n[PDF form fields on page 1]\n{field}')
EV4_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


class Evidence4AndStructure7PageHoldTests(BoxCase):
    """evidence:4, structure:7 (medium, over-correction) and contract:2 (high, new in 686d60b11). The unmatched-field page
    hold fired on an ordinary text field whose value is 'None' or 'No' ('Complications: None', 'EBL: None', a radio
    'Procedure cancelled: No'), and on a shared option row whose labels the field names, holding every code on the page,
    explicitly cued passages included. A 'No' or 'None' holds the page only when its label names a service or an
    intervention, or is a generic widget name; a field label is also tied to the box-delimited items of a printed row and
    to a printed row it opens."""

    def test_ordinary_text_fields_hold_nothing(self):
        for printed, field in (('Complications (if any):', 'Complications: None'),
                               ('Complications (if any):', 'Complications: No'),
                               ('Estimated blood loss:', 'EBL: None'), ('Specimens:', 'Specimens: None'),
                               ('Complications (if any):', 'Complications (if any): None'),
                               ('Sedation:', 'Sedation: None')):
            with self.subTest(field=field):
                text = EV4_PAGE.format(printed=printed, field=field)
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assertEqual(read(text, EV4_POLYP)[0], 'performed')
                self.assert_outcome(text, '45385', EV4_POLYP, 'ready')
                held_for_its_interventions_only(self, self.assert_outcome(text, '45378', 'Colonoscopy', 'held'))

    def test_the_report_whose_text_is_all_fields(self):
        text = (HEADER + 'COLONOSCOPY REPORT\nProcedure:\nIndication:\nFindings:\nComplications (if any):\n\n[PDF form '
                'fields on page 1]\nProcedure: Colonoscopy with cold snare polypectomy\nIndication: Positive FIT\nFindings: '
                'The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold snare.\nComplications: '
                'None')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assert_outcome(text, '45385', 'A 6 mm polyp was removed with a cold snare.', 'ready')
        self.assert_outcome(text, '45385', 'Colonoscopy with cold snare polypectomy', 'ready')

    def test_generic_and_item_fields_still_hold_the_page(self):
        for field in ('Text7: None', 'Check Box1: not checked', 'Text 3: No'):
            with self.subTest(field=field):
                text = EV4_PAGE.format(printed='Complications (if any):', field=field)
                self.assert_held_reading(text, 'Colonoscopy')
                self.assert_outcome(text, '45378', 'Colonoscopy', 'held')
        text = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp '
                'was seen.\nInterventions:\nBiopsy  Cold snare polypectomy\n\n[PDF form fields on page 1]\nBiopsy taken: No')
        self.assert_held_reading(text, 'Cold snare polypectomy')

    def test_a_shared_option_row_ties_its_labels(self):
        text = (HEADER + 'Procedure: ☐ EGD ☒ Colonoscopy ☐ Flexible sigmoidoscopy\nFindings: The colonoscope was advanced to '
                'the cecum. A 6 mm polyp was removed with a cold snare.\n\n[PDF form fields on page 1]\nEGD: not checked\n'
                'Colonoscopy: checked\nFlexible sigmoidoscopy: not checked')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assertNotEqual(family(text, 'gi.egd'), 'performed')
        self.assert_outcome(text, '45385', 'A 6 mm polyp was removed with a cold snare.', 'ready')
        self.assertTrue(all(c.startswith(SILENT) for c in cues_of(text, 'Colonoscopy: checked')))
        row = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp '
               'was seen.\nInterventions:\n☐ Biopsy ☒ Cold snare polypectomy\n\n[PDF form fields on page 1]\nBiopsy: not '
               'checked\nCold snare polypectomy: checked')
        self.assertEqual(read(row, 'Biopsy')[0], 'negated')
        self.assert_outcome(row, '45385', 'Cold snare polypectomy', 'ready')
        held_for_its_interventions_only(self, self.assert_outcome(row, '45378', 'Colonoscopy', 'held'))

    def test_a_checked_field_line_is_silent_on_a_held_page(self):
        """structure:7: 'Colonoscopy: checked' read the untied field's hold; a checked line says nothing of its page."""
        text = EV4_PAGE.format(printed='Complications (if any):', field='Check Box1: not checked\nColonoscopy: checked')
        self.assertTrue(all(c.startswith(SILENT) for c in cues_of(text, 'Colonoscopy: checked')))
        self.assert_held_reading(text, 'Colonoscopy')

    def test_a_printed_row_its_field_opens_is_tied(self):
        for row, field in (('Complications: ☐ Yes ☒ No', 'Complications: No'),
                           ('Biopsy taken: ☐ Yes ☒ No', 'Biopsy taken: No'),
                           ('Biopsy taken:   Yes   No', 'Biopsy taken: No')):  # a radio row whose glyphs were not placed
            with self.subTest(field=field):
                text = EV4_PAGE.format(printed=row, field=field)
                self.assert_outcome(text, '45385', EV4_POLYP, 'ready')
                held_for_its_interventions_only(self, self.assert_outcome(text, '45378', 'Colonoscopy', 'held'))

    def test_an_egd_report_with_an_ordinary_field(self):
        egd = (HEADER + 'Procedure: EGD with biopsy.\nFindings: The endoscope was advanced to the second part of the duodenum. '
               'Biopsies were taken from the gastric antrum.\nComplications:\n\n[PDF form fields on page 1]\n{field}')
        for field in ('Complications (if any): None', 'EBL: None'):
            with self.subTest(field=field):
                self.assert_outcome(egd.format(field=field), '43239', 'EGD with biopsy.', 'ready')
        held_egd = egd.format(field='Text1: None')  # a generic text field may answer an item: still held, truthfully
        cues = self.assert_held_reading(held_egd, 'EGD with biopsy.')
        self.assertNotIn('says its item was not done', cues[0])

    def test_the_office_note_keeps_its_missed_service_warning(self):
        text = OFFICE_FLEX.format(printed='', field='Complications: None')
        proposals, result = run_engine(text, [('99214', VISIT)])
        missed_flex_sig(self, result)
        self.assertEqual(family(text, 'gi.flex_sig'), 'performed')


# --- contract:4 -- a status field that says the procedure was not done holds its page -----------------------------

C4_NOTE = (HEADER + 'Procedure: EUS with fine-needle biopsy of a pancreatic cyst.\nIndication: Pancreatic cyst on CT.\nHistory '
           'reviewed.\nConsent obtained.\nASA class II.\nAirway assessed.\nAllergies: none known.\nAnticoagulants: none.\nNPO '
           'since midnight.\n{printed}\n\n[PDF form fields on page 1]\n{field}')
C4_LINE = 'EUS with fine-needle biopsy of a pancreatic cyst.'


class Contract4StatusFieldTests(BoxCase):
    """contract:4 (critical). Extraction writes every form field after the page's text, beyond the six sentences the
    status readers look at, so a 'Procedure status: Cancelled' or 'Not performed' field never reached routing and the
    cancelled EUS was a ready 43242. A status field whose value is no completion holds the service mentions of its page
    that carry no explicit performance cue."""

    def test_the_claimed_fields(self):
        for printed, field in (('Procedure status:', 'Procedure status: Cancelled - the patient had eaten breakfast'),
                               ('Procedure status:', 'Procedure status: Not performed'),
                               ('Procedure status: ☐ Completed ☒ Cancelled', 'Procedure status: Cancelled'),
                               ('Procedure performed:', 'Procedure performed: No'),
                               ('Status:', 'Status: Rescheduled to next week'),
                               ('Procedure status:', 'Procedure status: Aborted before sedation')):
            with self.subTest(field=field):
                text = C4_NOTE.format(printed=printed, field=field)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                self.assertNotIn('FNB', str(fact_value(text, 'gi.eus', 'tissue_sampling')))
                self.assert_outcome(text, '43242', C4_LINE, 'held')

    def test_a_completed_status_stays_ready(self):
        for field in ('Procedure status: Completed', 'Procedure performed: Yes', 'Status: Done',
                      'Procedure status: Completed - recall planned', 'Status: Completed; follow-up scheduled'):
            with self.subTest(field=field):
                text = C4_NOTE.format(printed=field.split(':')[0] + ':', field=field)
                self.assertEqual(family(text, 'gi.eus'), 'performed')
                self.assert_outcome(text, '43242', C4_LINE, 'ready')


# --- contract:0 / release:5 / routing:11 / structure:10 -- the separately identifiable E/M attestation -------------

ATTEST_NOTE = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit for rectal bleeding.\nMedical '
               'decision making: Moderate.\nTotal time on the date of the encounter was 32 minutes.\nProcedure: Flexible '
               'sigmoidoscopy with biopsy was performed. The sigmoidoscope was advanced to 40 cm.\n{tail}')
ATTESTATION = 'I performed a significant, separately identifiable E/M service on the same day as the procedure.'
STATEMENT = 'A significant, separately identifiable E/M service was provided'
ATTEST_PICKS = [('99214', 'Total time on the date of the encounter was 32 minutes.'),
                ('45331', 'Flexible sigmoidoscopy with biopsy was performed.')]


def separate_em(text):
    finding = routed(text).finding('gi.office_em')
    return next((f for f in finding.facts if f.name == 'separate_em'), None)


class AttestationCase(BoxCase):
    def assert_refused(self, tail):
        text = ATTEST_NOTE.format(tail=tail)
        self.assertIsNone(separate_em(text), tail)
        proposals, _ = run_engine(text, ATTEST_PICKS)
        self.assertEqual(outcome(proposals['99214']), 'held', tail)
        self.assertIn('separate_em', clarified(proposals['99214']), tail)

    def assert_documented(self, tail):
        text = ATTEST_NOTE.format(tail=tail)
        fact = separate_em(text)
        self.assertIsNotNone(fact, tail)
        self.assertEqual(fact.value, 'documented')
        proposals, _ = run_engine(text, ATTEST_PICKS)
        self.assertNotIn('separate_em', clarified(proposals['99214']), tail)


class Contract0AttestationFieldTests(AttestationCase):
    """contract:0 and release:5 (critical). An unchecked attestation box that only the form-field block reports (its
    widget right of the sentence, beside line 2, on page 2) was accepted as the separately identifiable E/M statement,
    releasing the same-day E/M. The statement is refused when its page's form block has a denying field line that names
    nothing printed, or a field line naming it that is not checked."""

    def test_an_untied_denying_field_on_its_page_refuses_it(self):
        for field in ('Separate E/M attestation: not checked', 'Modifier 25 attestation: not checked',
                      'Check Box1: not checked', 'Check Box 7: not checked', 'Check Box3: not checked',
                      'Separate E/M attestation: No', 'Separate E/M attestation: no option selected'):
            with self.subTest(field=field):
                self.assert_refused(ATTESTATION + '\n\n[PDF form fields on page 1]\n' + field)
        self.assert_refused('I performed a significant, separately identifiable E/M service\non the same day as the '
                            'procedure.\n\n[PDF form fields on page 1]\nCheck Box1: not checked')
        self.assert_refused('A significant, separately identifiable E/M service was provided.\n\n[PDF form fields on page '
                            '1]\nCheck Box 7: not checked')

    def test_a_named_field_on_a_page_that_cannot_be_bounded_refuses_it(self):
        self.assert_refused('\n\nOther text.\n' + ATTESTATION + '\n\n[PDF form fields on page 2]\n' + ATTESTATION + ': not '
                            'checked')

    def test_checked_fields_and_other_pages_still_attest(self):
        for field in ('Separate E/M attestation: checked', 'Check Box1: checked', 'Separate E/M attestation: Yes'):
            with self.subTest(field=field):
                self.assert_documented(ATTESTATION + '\n\n[PDF form fields on page 1]\n' + field)
        self.assert_documented(ATTESTATION + '\n')
        # an addendum after the form page attests: the hold can be cleared
        self.assert_documented('\n[PDF form fields on page 1]\nCheck Box1: not checked\n\nADDENDUM (revision 2, added '
                               '2026-10-22 09:00 UTC)\n' + ATTESTATION + '\n')


class Routing11AttestationAnswerTests(AttestationCase):
    """routing:11 (high) and contract:0 (d). The statement was accepted although its box said No on the next line, or a
    lone unchecked box sat above or below it. A line under the statement that answers it is read as its answer: only a
    checked 'Yes' (or a checked box alone, or 'Yes') attests."""

    def test_an_answer_that_is_not_yes_refuses_it(self):
        for tail in (ATTESTATION + '\n☐ Yes ☒ No', ATTESTATION + '\n[ ] Yes [x] No', STATEMENT + ':\n☐ Yes ☒ No',
                     STATEMENT + ':\n[ ] Yes [x] No', STATEMENT + ':\nNo', STATEMENT + ':\n☒ No',
                     STATEMENT + ':\nAnswer: No', STATEMENT + ':\n☐ Yes ☐ No', STATEMENT + ':\n☒ Yes ☒ No',
                     STATEMENT + ':\n(•) Yes ( ) No', ATTESTATION + '\n☐', '☐\n' + ATTESTATION, ATTESTATION + '\n[ ]',
                     STATEMENT + ':\n\n☐ Yes ☒ No', STATEMENT + ':', STATEMENT + ':\nPlan: Follow up in 2 weeks.',
                     ATTESTATION + '\nAttested: ☐'):
            with self.subTest(tail=tail):
                self.assert_refused(tail + '\n')

    def test_a_yes_attests(self):
        for tail in (STATEMENT + ':\n☒ Yes ☐ No', STATEMENT + ':\n[x] Yes [ ] No', STATEMENT + ':\nYes',
                     STATEMENT + ':\n☒ Yes', ATTESTATION + '\n☒', ATTESTATION + '\nPlan: Follow up in 2 weeks.',
                     ATTESTATION + '\n☐ Follow-up colonoscopy in 3 years'):
            with self.subTest(tail=tail):
                self.assert_documented(tail + '\n')


class Routing11AnotherEncounterTests(AttestationCase):
    """routing:11 (c). A statement naming another encounter in words the list did not hold ('at the preoperative visit',
    'during the hospital admission', 'in the emergency department') was accepted. The test fails closed: an encounter or
    a setting named after the statement must be this encounter."""

    def test_another_encounter_refuses_it(self):
        for said in ('at the preoperative visit', 'during the hospital admission', 'in the emergency department',
                     'at her preop visit', 'at the pre-procedure consultation', 'at the referral consultation',
                     'at the pre-op evaluation', 'during the inpatient stay', 'in the ED', 'at the telehealth visit',
                     'at the visit', 'during the hospitalization'):
            with self.subTest(said=said):
                self.assert_refused(f'{STATEMENT} {said}.\n')

    def test_this_encounter_attests(self):
        for said in ('today', 'at this visit', "at today's visit", 'on the date of service', 'in the office today',
                     'in clinic today', 'during this encounter', 'during the same visit as the procedure',
                     'in addition to the procedure', 'at the same encounter', 'during today\'s office visit'):
            with self.subTest(said=said):
                self.assert_documented(f'{STATEMENT} {said}.\n')
        self.assert_documented('Separate E/M visit attestation: ' + ATTESTATION + '\n')
        self.assert_documented('A significant, separately identifiable E/M visit was provided.\n')
        self.assert_documented(STATEMENT + ' during the visit today.\n')


class Structure10AttestationMarkTests(AttestationCase):
    """structure:10 (b) (critical). A mark outside both lists in front of the statement ('[-]', '○', '{ }', '[N]', '< >')
    attested it. Any mark on the statement's line that is not a checked box refuses it."""

    def test_unread_marks_refuse_it(self):
        for mark in ('[-]', '○', '{ }', '[N]', '< >', '[Y] [N]', '●', '◉', '(N)', '[n]', '✗', '<x>', '{x}'):
            with self.subTest(mark=mark):
                self.assert_refused('Attestation:\n' + mark + ' A significant, separately identifiable E/M service was '
                                    'performed.\n')
        self.assert_refused(ATTESTATION + ' [N]\n')
        self.assert_refused('Separate E/M attestation: [N] ' + ATTESTATION + '\n')

    def test_a_checked_box_or_a_bullet_attests(self):
        for mark in ('☒', '[x]', '•', '-', '1.', '*'):
            with self.subTest(mark=mark):
                self.assert_documented('Attestation:\n' + mark + ' A significant, separately identifiable E/M service was '
                                       'performed.\n')


# --- bounded cost --------------------------------------------------------------------------------------------------

class ScaleTests(unittest.TestCase):
    """Every changed reader is bounded per span: long lines of the new marks, of status options and of fields."""

    def timed(self, text, budget=10):
        started = time.monotonic()
        route(text)
        status_for_span(text, *span(text, 'iopsy'))
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, budget)
        return elapsed

    def test_long_lines_of_marks(self):
        for name, unit in (('brackets', '[N] biopsy {x} snare < > [-] (Y) '), ('radio', '○ biopsy ● snare ◉ clip '),
                           ('status', 'Procedure status: ☐ Completed ☒ Cancelled biopsy '),
                           ('joined', 'Biopsy with cold snare | ☐ '), ('remark', 'Colonoscopy: Biopsy ☐ snare ☒ clip ')):
            with self.subTest(name):
                self.timed(HEADER + 'Findings: Colonoscopy. ' + (unit * 3000)[:50000])

    def test_many_status_lines_and_answers(self):
        lines = ''.join(f'Procedure cancelled: No\n[ ] Completed [x] Cancelled [ ] Aborted\nBiopsy {n}\n' for n in range(1500))
        self.timed(HEADER + 'Procedure: Colonoscopy.\n' + lines[:60000])

    def test_a_form_block_with_thousands_of_answers(self):
        text = (HEADER + 'Procedure: Colonoscopy with biopsy.\n' + '\n'.join(f'☐ Item {n} ☒ Biopsy {n}' for n in range(2000))
                + '\n\n[PDF form fields on page 1]\n' + '\n'.join(f'Biopsy {n} in the last year: No' if n % 2 else
                                                                 f'Item {n}: N' for n in range(2000)))
        self.timed(text)
        attest = (HEADER + 'Established patient office visit.\n' + ''.join(f'{STATEMENT}:\n☐ Yes ☒ No\n' for _ in range(500)))
        started = time.monotonic()
        route(attest)
        self.assertLess(time.monotonic() - started, 10)


if __name__ == '__main__':
    unittest.main()
