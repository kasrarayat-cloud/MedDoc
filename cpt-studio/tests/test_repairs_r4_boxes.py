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
from tests.test_repairs_status_r2_routing import (BOXED, HEADER, SILENT, clarified, fact_value, family, read, ready,
                                                  routed, run_engine, span)
from tests.test_repairs_r3_forms_routing import excluded, held, not_silent, outcome

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
        for glyph, box in symbols._BOX_SHAPES.items():
            with self.subTest(glyph=hex(ord(glyph))):
                match = detect._BOX.fullmatch(glyph)
                self.assertIsNotNone(match)
                self.assertEqual('off' if match.group('off') else 'on', 'off' if box == symbols.UNCHECKED_BOX else 'on')

    def test_every_typed_box_routing_reads_is_a_printed_box_when_unchecked(self):
        from studio.ingest.pdf import PRINTED_BOX
        for typed in ('[ ]', '[  ]', '[\t]', '[' + NBSP + ']', '[]', '[_]', '( )', '(  )', '(\t)', '☐', '□', '▢', '⬜',
                      '❑', '◻', '◽'):
            with self.subTest(typed=typed):
                self.assertEqual(detect._BOX.fullmatch(typed).group('off'), typed)
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


# --- structure:13 -- a status option answered No holds, never cancels -------------------------------------------------

COLON_NOTE = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n{rows}\nFindings: The colonoscope was advanced to '
              'the cecum. A 6 mm polyp was removed with a cold snare.\n')
POLYP = 'A 6 mm polyp was removed with a cold snare.'


# --- structure:15 -- a yes/no pair with both options checked holds ----------------------------------------------------


# --- structure:0 -- a remark after the last box never makes the boxes lead ----------------------------------------------

S0_NOTE = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm sigmoid polyp was '
           'found.\n{row}\n')


# --- structure:16 -- a trailing box after a label joined by 'with', ';' or 'plus' --------------------------------------


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
        for row in ('Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed',
                    'Colonoscopy ☒ Biopsy ☐ Cold snare polypectomy ☒ clip placed'):
            with self.subTest(row=row):
                text = S0_NOTE.format(row=row)
                self.assertEqual(read(text, 'Colonoscopy', 1)[0], 'performed')
                self.assertEqual(read(text, 'clip')[0], 'performed')

    def test_the_egd_row(self):
        text = S0_NOTE.format(row='EGD: Biopsy ☐ Balloon dilation ☒ dilation to 15 mm')
        self.assertNotEqual(read(text, 'Biopsy')[0], 'performed')
        self.assertNotEqual(read(text, 'Balloon dilation')[0], 'negated')

    def test_rows_with_one_reading_are_unchanged(self):
        for row, biopsy, snare in (('Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒', 'negated', 'performed'),
                                   ('Colonoscopy: [ ] biopsy [x] cold snare', 'negated', 'performed'),
                                   ('Colonoscopy with ☐ biopsy ☒ cold snare', 'negated', 'performed'),
                                   ('Polypectomy: [ ] biopsy [x] cold snare', 'negated', 'performed'),
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
        for rows in ('▢ | Biopsy\n☑ | Cold snare polypectomy', '⬜ Biopsy\n✔ Cold snare polypectomy', 'Biopsy | ▢\n'
                     'Cold snare polypectomy | ☒', '\U0001f78e Biopsy\n\U0001f5f9 Cold snare polypectomy'):
            with self.subTest(rows=rows):
                text = BOXED + rows + '\n'
                self.assert_outcome(text, '45380', 'Biopsy', 'excluded')
                self.assert_outcome(text, '45385', 'Cold snare polypectomy', 'ready')


# --- form-field lines: structure:6, structure:7, contract:2, evidence:4 -------------------------------------------

OFFICE_FLEX = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit for rectal bleeding.\nChief '
               'complaint: Rectal bleeding.\nAssessment: Hematochezia.\nMedical decision making: moderate.\nTotal time: 32 '
               'minutes.\nProcedure: Flexible sigmoidoscopy with biopsy. The sigmoidoscope was advanced to 40 cm.\nBiopsies '
               'were taken from the rectum.\n{printed}\n[PDF form fields on page 1]\n{field}')
VISIT = 'Established patient office visit for rectal bleeding.'


def unproposed(result):
    return next(c for c in result.encounter_checks if c.id == 'services.unproposed')


EV4_PAGE = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp was '
            'removed with a cold snare.\n{printed}\n\n[PDF form fields on page 1]\n{field}')
EV4_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


# --- contract:4 -- a status field that says the procedure was not done holds its page -----------------------------

C4_NOTE = (HEADER + 'Procedure: EUS with fine-needle biopsy of a pancreatic cyst.\nIndication: Pancreatic cyst on CT.\nHistory '
           'reviewed.\nConsent obtained.\nASA class II.\nAirway assessed.\nAllergies: none known.\nAnticoagulants: none.\nNPO '
           'since midnight.\n{printed}\n\n[PDF form fields on page 1]\n{field}')
C4_LINE = 'EUS with fine-needle biopsy of a pancreatic cyst.'


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
