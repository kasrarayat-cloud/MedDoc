"""Regressions for refutation round 3, FORMS lens: how routing reads check boxes and form-field lines.

Each class reproduces one confirmed finding (routing:N or contract:N in the round-3 triage) from its exact input,
adds the variants its verifier listed, and pins positive controls. Routing runs for real, for the document's own
service date and through the JSON round trip the pipeline applies; the real validation engine assesses
provider-shaped selections. The shared check-box contract (round 3b, section 2):

- unchecked: ☐ □ ◻ ◽ ❏ ❐ ❑ ❒, '[ ]' / '( )' with any inner whitespace, '[_]'; checked: ☑ ☒ ✓ ✔ ■ ⌧,
  '[x]' / '(x)' with optional inner whitespace, '[*]', '[v]';
- a box governs the item(s) on its own line or table cell, before or after them; a label naming several items is
  governed as a whole; remarks after the last box do not flip the orientation; a cell ending in a period stays one
  cell; boxes that disagree about one item hold it; an unchecked status option is not a statement;
- a denying form-field line negates the printed line or cell its label names on the same page, and holds that
  page's items when it names none.

Synthetic text only.
"""
import time
import unittest

from studio.gi.detect import route, status_for_span
from tests.test_repairs_status_r2_routing import (BOXED, HEADER, SILENT, fact_value, family, read, ready, routed,
                                                  run_engine, span)


def excluded(proposal):
    return proposal.bucket == 'excluded'


def held(proposal):
    return (proposal.bucket, proposal.status) == ('selected', 'needs_clarification')


def outcome(proposal):
    return 'ready' if ready(proposal) else 'excluded' if excluded(proposal) else 'held' if held(proposal) else (
        proposal.bucket, proposal.status)


def not_silent(cues):
    return bool(cues) and not any(cue.startswith(SILENT) for cue in cues)


class BoxCase(unittest.TestCase):
    maxDiff = None

    def assert_items(self, text, expected, picks=None):
        """expected: {phrase: status}; picks: {code: (phrase, outcome)} through the real engine."""
        for phrase, status in expected.items():
            got = read(text, phrase)
            self.assertEqual(got[0], status, (phrase, got, text[-160:]))
        for code, (phrase, want) in (picks or {}).items():
            proposals, _ = run_engine(text, [(code, phrase)])
            self.assertEqual(outcome(proposals[code]), want, (code, phrase, proposals[code].exclusion_reason,
                                                              [c.detail for c in proposals[code].checks]))


# --- routing:5 -- a remark after the last box never flips the orientation ----------------------------------------

class Routing5RemarkAfterTheLastBoxTests(BoxCase):
    ROWS = ('Biopsy | ☐ | Cold snare polypectomy | ☒ | clip placed after polypectomy',
            'Biopsy: [ ]  Cold snare polypectomy: [x]  Notes: polypectomy site clipped',
            'Biopsy | ☐ | Cold snare polypectomy | ☒ | clip placed',
            'Biopsy\t☐\tCold snare polypectomy\t☒\tclip placed',
            'Biopsy ☐  Cold snare polypectomy ☒  clip placed')

    def test_the_claimed_rows(self):
        for row in self.ROWS:
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                self.assert_items(text, {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                                  {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})
                interventions = fact_value(text, 'gi.colonoscopy', 'interventions') or ''
                self.assertNotIn('biopsy', interventions)
                self.assertIn('cold snare', interventions)

    def test_a_remark_straight_after_the_last_box(self):
        """Each box follows its own 'label:', so the boxes trail even though every box is followed by an item."""
        for row in ('Biopsy: [ ] Cold snare polypectomy: [x] clip placed', 'Biopsy: ☐ Cold snare polypectomy: ☒ clip'):
            with self.subTest(row=row):
                self.assert_items(BOXED + row + '\n', {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                                  {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})
        text = HEADER + 'Findings: A 6 mm polyp was found.\nColonoscopy: ☐ EGD: ☒ dilation to 15 mm\n'
        self.assertEqual((read(text, 'Colonoscopy')[0], read(text, 'EGD')[0]), ('negated', 'performed'))
        # under a heading an item after a box is followed by the next box with no colon: the boxes still lead
        text = HEADER + 'Findings: A 6 mm polyp was found.\nColonoscopy: ☐ biopsy: sigmoid ☒ cold snare\n'
        self.assertEqual((read(text, 'biopsy')[0], read(text, 'cold snare')[0]), ('negated', 'performed'))

    def test_a_parenthetical_remark(self):
        text = BOXED + 'Biopsy: ☐   Polypectomy: ☒ (cold snare)\n'
        self.assert_items(text, {'Biopsy': 'negated', 'Polypectomy': 'performed'},
                          {'45380': ('Biopsy', 'excluded'), '45385': ('Polypectomy', 'ready')})

    def test_a_word_table_row_with_a_notes_cell(self):
        from tests.test_repairs_r3_forms_docx import box_table_docx, docx_text
        text = docx_text(box_table_docx([['Biopsy', ('box', False), 'Cold snare polypectomy', ('box', True),
                                          'clip placed after polypectomy']]))
        self.assertTrue(text.endswith('Biopsy | ☐ | Cold snare polypectomy | ☒ | clip placed after polypectomy'), text)
        self.assert_items(text, {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                          {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})

    def test_leading_boxes_under_a_label_are_unchanged(self):
        for row in ('Colonoscopy: [ ] biopsy [x] cold snare', 'Colonoscopy with ☐ biopsy ☒ cold snare',
                    'Polypectomy: [ ] biopsy [x] cold snare', '☐ Biopsy ☒ Cold snare polypectomy | clip placed',
                    '[ ] Biopsy [x] Cold snare polypectomy'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                biopsy = 'biopsy' if 'biopsy' in row else 'Biopsy'
                snare = 'cold snare' if 'cold snare' in row else 'Cold snare'
                self.assertEqual(read(text, biopsy)[0], 'negated')
                self.assertEqual(read(text, snare)[0], 'performed')
        self.assertEqual(family(BOXED + 'Colonoscopy: [ ] biopsy [x] cold snare\n', 'gi.colonoscopy'), 'performed')

    def test_trailing_boxes_without_a_remark_are_unchanged(self):
        for row in ('Biopsy | ☐ | Cold snare polypectomy | ☒', 'Biopsy: ☐ Cold snare polypectomy: ☒',
                    'Colonoscopy: ☒ Biopsy: ☐'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                self.assertEqual(read(text, 'Biopsy')[0], 'negated')


# --- routing:6 -- one trailing box after a label naming several items governs all of them ------------------------

class Routing6OneBoxForSeveralItemsTests(BoxCase):
    ROWS = ('Biopsy/polypectomy | ☐', 'Biopsy or polypectomy: ☐', 'Tissue sampling (biopsy or polypectomy): ☐',
            'Biopsy, polypectomy: ☐', 'Biopsy and polypectomy | ☐', 'Biopsy / polypectomy [ ]',
            'Biopsy & polypectomy: ☐')

    def test_the_claimed_rows(self):
        for row in self.ROWS:
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                biopsy = 'biopsy' if 'biopsy' in row else 'Biopsy'
                self.assert_items(text, {biopsy: 'negated', 'polypectomy': 'negated'},
                                  {'45380': (biopsy, 'excluded'), '45385': ('polypectomy', 'excluded')})
                self.assertNotIn('biopsy', fact_value(text, 'gi.colonoscopy', 'interventions') or '')

    def test_the_checked_and_unboxed_rows_stay_ready(self):
        for row in ('Biopsy/polypectomy | ☒', 'Biopsy or polypectomy: ☒', 'Biopsy/polypectomy'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                self.assert_items(text, {'Biopsy': 'performed', 'polypectomy': 'performed'},
                                  {'45380': ('Biopsy', 'ready')})

    def test_a_word_table(self):
        from tests.test_repairs_r3_forms_docx import box_table_docx, docx_text
        for label in ('Biopsy/polypectomy', 'Biopsy or polypectomy'):
            with self.subTest(label=label):
                text = docx_text(box_table_docx([[label, ('box', False)]]))
                self.assertTrue(text.endswith(label + ' | ☐'), text)
                self.assert_items(text, {'Biopsy': 'negated', 'polypectomy': 'negated'},
                                  {'45380': ('Biopsy', 'excluded')})

    def test_a_label_joined_by_a_word_that_is_not_a_joiner_is_not_one_label(self):
        text = HEADER + 'Procedure: Colonoscopy with biopsy ☐\nFindings: The colonoscope was advanced to the cecum.\n'
        self.assertEqual((read(text, 'Colonoscopy')[0], read(text, 'biopsy')[0]), ('performed', 'negated'))


# --- routing:15 and routing:16 -- every spelling of the contract's boxes is read ---------------------------------

class Routing15CheckedBoxSpellingsTests(BoxCase):
    def test_the_claimed_rows(self):
        for row in ('( ) Biopsy ( x ) Cold snare polypectomy', '[ ] Biopsy [ x ] Cold snare polypectomy',
                    '[ ] Biopsy [*] Cold snare polypectomy', '[ ] Biopsy [v] Cold snare polypectomy'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                self.assert_items(text, {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                                  {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'interventions'), 'cold snare')

    def test_the_verified_variants(self):
        for off, on in (('( )', '( X )'), ('( )', '(x )'), ('( )', '( x)'), ('[ ]', '[ X ]'), ('[ ]', '[x ]'),
                        ('[ ]', '[ x]'), ('[_]', '[ x ]'), ('☐', '[ x ]'), ('☐', '( x )')):
            with self.subTest(off=off, on=on):
                text = BOXED + f'{off} Biopsy {on} Cold snare polypectomy\n'
                self.assert_items(text, {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'})

    def test_a_typed_word_line(self):
        from tests.test_repairs_r3_forms_docx import docx_text, paragraphs_docx
        text = docx_text(paragraphs_docx(['( ) Biopsy ( x ) Cold snare polypectomy']))
        self.assert_items(text, {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                          {'45385': ('Cold snare polypectomy', 'ready'), '45380': ('Biopsy', 'excluded')})

    def test_a_box_written_in_a_way_the_reader_cannot_classify_holds_its_item(self):
        """Never the neighbour's box: an unreadable mark holds the item it marks, and leaves the others alone."""
        for mark in ('(•)', '(●)', '[√]', '(✓)', '( ✔ )', '[?]', '(*)', '(o)', '[/]'):
            with self.subTest(mark=mark):
                text = BOXED + f'( ) Biopsy {mark} Cold snare polypectomy\n'
                status, cues = read(text, 'Cold snare polypectomy')
                self.assertEqual(status, 'uncertain', cues)
                self.assertTrue(not_silent(cues), cues)
                self.assertEqual(read(text, 'Biopsy')[0], 'negated')
                proposals, _ = run_engine(text, [('45385', 'Cold snare polypectomy')])
                self.assertEqual(outcome(proposals['45385']), 'held')
        text = BOXED + 'Biopsy taken: (•) Yes ( ) No\n'
        self.assertEqual(read(text, 'Biopsy')[0], 'uncertain')

    def test_ordinary_brackets_are_not_boxes(self):
        for row in ('Biopsy (x2) of the sigmoid colon', 'Biopsy (sigmoid) [sic]', 'Biopsy (1) and polypectomy (2)',
                    'Biopsy for H. pylori (-)', 'Cold snare polypectomy (+) margin', 'Biopsy(s) of the sigmoid',
                    'Biopsy (a) and (b)', 'Biopsy (or brushing) of the sigmoid'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                self.assertEqual(read(text, 'Biopsy' if 'Biopsy' in row else 'Cold snare polypectomy')[0], 'performed')


class Routing16PaddedUncheckedBoxTests(BoxCase):
    def test_the_claimed_rows(self):
        for row in ('[  ] Biopsy [x] Cold snare polypectomy', '(  ) Biopsy (x) Cold snare polypectomy',
                    '[   ] Biopsy [x] Cold snare polypectomy', '[\u00a0] Biopsy [x] Cold snare polypectomy',
                    '[\t] Biopsy [x] Cold snare polypectomy', '[ ] Biopsy [ x ] Cold snare polypectomy'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                self.assert_items(text, {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                                  {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'interventions'), 'cold snare')

    def test_every_layout(self):
        for rows in ('[  ] Biopsy\n[x] Cold snare polypectomy\n', 'Interventions:\n[  ] Biopsy\n(x) Cold snare polypectomy\n',
                     'Biopsy: [  ]\nCold snare polypectomy: [x]\n', 'Biopsy: (  )\nCold snare polypectomy: ( x )\n'):
            with self.subTest(rows=rows):
                self.assert_items(BOXED + rows, {'Biopsy': 'negated'},
                                  {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})

    def test_a_yes_no_pair_with_padded_boxes(self):
        text = BOXED + 'Biopsy taken: [  ] Yes [X] No\nCold snare polypectomy: [X] Yes [  ] No\n'
        self.assert_items(text, {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                          {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})

    def test_typed_word_paragraphs(self):
        from tests.test_repairs_r3_forms_docx import docx_text, paragraphs_docx
        text = docx_text(paragraphs_docx(['Interventions:', '[  ] Biopsy', '[X] Cold snare polypectomy']))
        self.assert_items(text, {'Biopsy': 'negated'}, {'45380': ('Biopsy', 'excluded')})

    def test_an_empty_pair_of_parentheses_is_not_a_box(self):
        self.assertEqual(read(BOXED + 'Biopsy () taken\n', 'Biopsy')[0], 'performed')


# --- contract:7 -- a label cell ending in a period keeps its box -----------------------------------------------------

class Contract7LabelEndingInAPeriodTests(BoxCase):
    def test_the_word_table(self):
        from tests.test_repairs_r3_forms_docx import box_table_docx, docx_text
        for checked in (False, True):
            with self.subTest(checked=checked):
                text = docx_text(box_table_docx([['Cold forceps biopsy of the polyp.', ('box', checked)],
                                                 ['Cold snare polypectomy of the polyp.', ('box', True)]]))
                self.assertTrue(text.endswith(f'Cold forceps biopsy of the polyp. | {"☒" if checked else "☐"}\n'
                                              'Cold snare polypectomy of the polyp. | ☒'), text)
                self.assert_items(text, {'Cold forceps biopsy': 'performed' if checked else 'negated',
                                         'Cold snare polypectomy': 'performed'},
                                  {'45380': ('Cold forceps biopsy', 'ready' if checked else 'excluded'),
                                   '45385': ('Cold snare polypectomy', 'ready')})

    def test_pasted_rows(self):
        text = BOXED + 'Biopsy. | ☐\nCold snare polypectomy | ☒\n'
        self.assert_items(text, {'Biopsy': 'negated'}, {'45380': ('Biopsy', 'excluded')})
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'interventions'), 'cold snare')
        for row in ('Biopsy. | ☐ | Cold snare polypectomy. | ☒', 'Biopsy. ☐ Cold snare polypectomy. ☒',
                    'Biopsy. [ ]\tCold snare polypectomy. [x]'):
            with self.subTest(row=row):
                self.assert_items(BOXED + row + '\n', {'Biopsy': 'negated', 'Cold snare polypectomy': 'performed'},
                                  {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})

    def test_a_box_after_a_later_sentence_or_a_word_is_not_the_items(self):
        text = BOXED + 'Cold snare polypectomy was performed. Retrieval: ☐\n'
        self.assertEqual(read(text, 'Cold snare polypectomy')[0], 'performed')
        text = BOXED + 'Colonoscopy. ☐ Biopsy.\n'
        self.assertEqual((read(text, 'Colonoscopy', 1)[0], read(text, 'Biopsy')[0]), ('performed', 'negated'))
        text = BOXED + '☐ Biopsy. ☒ Cold snare polypectomy.\n'
        self.assertEqual((read(text, 'Biopsy')[0], read(text, 'Cold snare polypectomy')[0]), ('negated', 'performed'))
        text = BOXED + '☒ Biopsy. ☐ Cold snare polypectomy.\n'
        self.assertEqual((read(text, 'Biopsy')[0], read(text, 'Cold snare polypectomy')[0]), ('performed', 'negated'))


# --- contract:3 -- an unchecked status option is not a statement -------------------------------------------------

STATUS_NOTE = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n{options}\nFindings: The colonoscope was '
               'advanced to the cecum. A 6 mm polyp was removed with a cold snare.\n')
POLYP = 'A 6 mm polyp was removed with a cold snare.'


class Contract3UncheckedStatusOptionTests(BoxCase):
    UNCHECKED = ('Procedure completed | ☒\nProcedure cancelled | ☐', '☒ Procedure completed\n☐ Procedure cancelled',
                 '[x] Procedure completed\n[ ] Procedure cancelled', 'Procedure completed: ☒\nProcedure cancelled: [ ]',
                 'Procedure completed: ☒\nProcedure cancelled: ☐', 'Procedure completed: ☒\nProcedure cancelled: not checked',
                 'Procedure completed: ☒\nProcedure cancelled: [ ] Yes [x] No',
                 '☒ Procedure completed\n☐ Procedure aborted\n☐ Procedure cancelled')

    def test_the_claimed_options(self):
        for options in self.UNCHECKED:
            with self.subTest(options=options):
                text = STATUS_NOTE.format(options=options)
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                proposals, _ = run_engine(text, [('45385', POLYP)])
                self.assertEqual(outcome(proposals['45385']), 'ready', proposals['45385'].exclusion_reason)

    def test_options_on_the_line_under_the_procedure_are_held_never_cancelled(self):
        """The next-line denial reader (WORDING's _denies) still reads the option's words; the box keeps it a hold."""
        text = STATUS_NOTE.format(options='☒ Procedure completed ☐ Procedure cancelled')
        self.assertNotIn(family(text, 'gi.colonoscopy'), ('cancelled', 'negated'))
        proposals, _ = run_engine(text, [('45385', POLYP)])
        self.assertNotEqual(outcome(proposals['45385']), 'excluded')

    def test_a_checked_option_is_still_a_statement(self):
        for options, status in (('Procedure completed | ☐\nProcedure cancelled | ☒', 'cancelled'),
                                ('[ ] Procedure completed\n[x] Procedure cancelled', 'cancelled'),
                                ('Procedure completed: ☐\nProcedure cancelled: [x] Yes [ ] No', 'cancelled'),
                                ('☐ Procedure completed\n☒ Procedure aborted\n☐ Procedure cancelled', 'incomplete'),
                                ('Procedure cancelled.', 'cancelled')):
            with self.subTest(options=options):
                self.assertEqual(family(STATUS_NOTE.format(options=options), 'gi.colonoscopy'), status)

    def test_a_status_option_whose_boxes_cannot_be_read_holds(self):
        for options in ('Procedure completed: ☒\nProcedure cancelled: ☒ ☐', 'Procedure completed: ☒\nProcedure cancelled: (•)'):
            with self.subTest(options=options):
                text = STATUS_NOTE.format(options=options)
                self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
                proposals, _ = run_engine(text, [('45385', POLYP)])
                self.assertEqual(outcome(proposals['45385']), 'held')

    def test_a_word_table_of_status_options(self):
        from tests.test_repairs_r3_forms_docx import box_table_docx, docx_text
        text = docx_text(box_table_docx([['Procedure completed', ('box', True)], ['Procedure cancelled', ('box', False)]],
                                        lines=HEADER.strip().split('\n') + ['Procedure: Colonoscopy with cold snare '
                                                                            'polypectomy.'],
                                        after=['Findings: The colonoscope was advanced to the cecum. A 6 mm polyp was '
                                               'removed with a cold snare.']))
        self.assertIn('Procedure cancelled | ☐', text)
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        proposals, _ = run_engine(text, [('45385', POLYP)])
        self.assertEqual(outcome(proposals['45385']), 'ready')


# --- contract:2 (routing) -- two boxes that disagree about one item hold it ---------------------------------------

class Contract2DisagreeingBoxesTests(BoxCase):
    def test_disagreeing_boxes_hold(self):
        for row in ('☒ ☐ Biopsy', '☐ ☒ Biopsy', 'Biopsy ☐ ☒', 'Biopsy: [x] [ ]', '[x] [ ] Biopsy', '☒' + chr(0xA0) + '☐ Biopsy'):
            with self.subTest(row=row):
                text = BOXED + row + '\n'
                status, cues = read(text, 'Biopsy')
                self.assertEqual(status, 'uncertain', cues)
                self.assertTrue(not_silent(cues), cues)
                proposals, _ = run_engine(text, [('45380', 'Biopsy')])
                self.assertEqual(outcome(proposals['45380']), 'held')

    def test_boxes_in_cells_of_their_own_are_options(self):
        """A flattened 'Done | Not done' table (round 2b status:19): the first box after the item governs it."""
        self.assertEqual(read(BOXED + 'Biopsy | ☒ | ☐\n', 'Biopsy')[0], 'performed')
        self.assertEqual(read(BOXED + 'Biopsy | ☐ | ☒\n', 'Biopsy')[0], 'negated')

    def test_agreeing_boxes_read_as_one(self):
        for row, status in (('☐ ☐ Biopsy', 'negated'), ('☒ ☒ Biopsy', 'performed'), ('Biopsy ☐ ☐', 'negated')):
            with self.subTest(row=row):
                self.assertEqual(read(BOXED + row + '\n', 'Biopsy')[0], status)


# --- contract:0 (routing) -- a denying form-field line reaches the printed label ---------------------------------

FORM_PAGE = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nFindings: A 6 mm sigmoid polyp '
             'was seen.\nInterventions:\n{rows}\n\n[PDF form fields on page 1]\n{fields}')


def form_page(rows='Biopsy\nCold snare polypectomy', fields='Biopsy: not checked\nCold snare polypectomy: checked'):
    return FORM_PAGE.format(rows=rows, fields=fields)


class Contract0BlockLineTests(BoxCase):
    def test_a_denying_line_negates_the_printed_label(self):
        for value in ('not checked', 'unchecked', 'no option selected', 'No', 'None', 'Not done', 'Not performed',
                      'Not checked.', 'no'):
            with self.subTest(value=value):
                text = form_page(fields=f'Biopsy: {value}\nCold snare polypectomy: checked')
                self.assert_items(text, {'Biopsy': 'negated', f'Biopsy: {value}': 'negated'},
                                  {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})
                proposals, _ = run_engine(text, [('45380', f'Biopsy: {value}')])
                self.assertEqual(outcome(proposals['45380']), 'excluded')
                self.assertEqual(read(text, 'Biopsy')[1], ('negated: an unchecked box',))

    def test_a_radio_answer_negates_its_printed_question(self):
        text = form_page(rows='Cold snare polypectomy\nBiopsy taken:', fields='Cold snare polypectomy: checked\n'
                                                                            'Biopsy taken: No')
        self.assert_items(text, {'Biopsy': 'negated', 'Biopsy taken: No': 'negated'},
                          {'45380': ('Biopsy', 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})
        twin = form_page(rows='Cold snare polypectomy\nBiopsy taken:', fields='Cold snare polypectomy: checked\n'
                                                                            'Biopsy taken: Yes')
        self.assertEqual(read(twin, 'Biopsy')[0], 'uncertain')  # silent: the rest of the document decides
        self.assert_items(twin, {}, {'45380': ('Biopsy', 'ready')})

    def test_the_label_is_matched_whatever_its_case_marker_or_colon(self):
        for rows in ('BIOPSY:\nCold snare polypectomy', '1. Biopsy\n2. Cold snare polypectomy',
                     '- Biopsy\n- Cold snare polypectomy', '☐ Biopsy\n☒ Cold snare polypectomy',
                     'Biopsy  \nCold snare polypectomy', 'Biopsy | 2026-10-21\nCold snare polypectomy',
                     'Biopsy ☐\nCold snare polypectomy ☒'):
            with self.subTest(rows=rows):
                text = form_page(rows=rows)
                biopsy = 'BIOPSY' if 'BIOPSY' in rows else 'Biopsy'
                self.assert_items(text, {biopsy: 'negated'},
                                  {'45380': (biopsy, 'excluded'), '45385': ('Cold snare polypectomy', 'ready')})

    def test_checked_and_yes_lines_are_silent(self):
        for value in ('checked', 'Yes', 'Done'):
            with self.subTest(value=value):
                text = form_page(fields=f'Biopsy: {value}\nCold snare polypectomy: checked')
                self.assert_items(text, {'Biopsy': 'uncertain'}, {'45380': ('Biopsy', 'ready')})
                self.assertEqual(read(text, f'Biopsy: {value}')[0], 'uncertain')
                self.assertTrue(all(c.startswith(SILENT) for c in read(text, f'Biopsy: {value}')[1]))

    def test_an_unmatched_denying_line_holds_the_page(self):
        for fields in ('Check Box1: not checked\nCheck Box2: checked', 'Biopsy taken: No\nCold snare polypectomy: checked',
                       'Biopsy sampling: no option selected'):
            with self.subTest(fields=fields):
                text = form_page(rows='Biopsy  Cold snare polypectomy', fields=fields)
                for phrase in ('Biopsy', 'Cold snare polypectomy', 'Colonoscopy'):
                    status, cues = read(text, phrase)
                    self.assertEqual(status, 'uncertain', (phrase, cues))
                    self.assertTrue(not_silent(cues), cues)
                    self.assertIn(fields.split('\n')[0].split(':')[0], cues[0])
                self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
                for code, phrase in (('45380', 'Biopsy'), ('45385', 'Cold snare polypectomy')):
                    proposals, _ = run_engine(text, [(code, phrase)])
                    self.assertEqual(outcome(proposals[code]), 'held', (code, phrase))

    def test_an_explicit_statement_or_a_box_on_the_page_still_speaks(self):
        text = (HEADER + 'Procedure: Colonoscopy was performed. The colonoscope was advanced to the cecum.\nFindings: Cold '
                'forceps biopsies were taken from the sigmoid colon.\n☒ Cold snare polypectomy\nHemoclip\n\n[PDF form '
                'fields on page 1]\nCheck Box1: not checked')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assertEqual(read(text, 'biopsies')[0], 'performed')
        self.assertEqual(read(text, 'Cold snare polypectomy')[0], 'performed')
        status, cues = read(text, 'Hemoclip')
        self.assertEqual(status, 'uncertain', cues)
        self.assertTrue(not_silent(cues), cues)
        self.assertEqual(outcome(run_engine(text, [('45385', 'Cold snare polypectomy')])[0]['45385']), 'ready')

    def test_the_page_is_the_text_since_the_previous_block(self):
        """Page 1's block bounds page 2; a label printed only on another page is not this page's."""
        page1 = ('Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\nBiopsy\n\n[PDF form fields on '
                 'page 1]\nBiopsy: checked')
        page2 = 'Interventions:\nBiopsy\nCold snare polypectomy\n\n[PDF form fields on page 2]\nBiopsy: not checked'
        text = HEADER + page1 + '\n\n' + page2
        self.assertEqual(read(text, 'Biopsy')[0], 'performed')  # page 1's printed line
        self.assertEqual(read(text, 'Biopsy', 2)[0], 'negated')  # page 2's printed line

    def test_a_page_that_cannot_be_bounded_holds_instead_of_negating(self):
        """Page 2 has a block but page 1 has none: the printed text before the block may be either page's."""
        text = (HEADER + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\n\nInterventions:\nBiopsy\n'
                'Cold snare polypectomy\n\n[PDF form fields on page 2]\nBiopsy: not checked\nCold snare polypectomy: '
                'checked')
        status, cues = read(text, 'Biopsy')
        self.assertEqual(status, 'uncertain', cues)
        self.assertTrue(not_silent(cues), cues)
        proposals, _ = run_engine(text, [('45380', 'Biopsy')])
        self.assertEqual(outcome(proposals['45380']), 'held')
        self.assertTrue(all(c.startswith(SILENT) for c in read(text, 'Cold snare polypectomy')[1]))

    def test_a_printed_checked_box_and_a_denying_line_disagree(self):
        text = form_page(rows='☒ Biopsy\nCold snare polypectomy')
        status, cues = read(text, 'Biopsy')
        self.assertEqual(status, 'uncertain', cues)
        self.assertTrue(not_silent(cues), cues)

    def test_annotation_text_and_pasted_lines_are_not_form_fields(self):
        text = form_page(fields='Cold snare polypectomy: checked').replace(
            '[PDF form fields on page 1]\nCold snare polypectomy: checked', '[PDF annotation text on page 1]\nBiopsy: No')
        self.assertNotEqual(read(text, 'Biopsy')[0], 'negated')
        text = HEADER + 'Findings: The colonoscope was advanced to the cecum.\nBiopsy\nBiopsy: No\n'
        self.assertEqual(read(text, 'Biopsy')[0], 'performed')


# --- bounded cost ------------------------------------------------------------------------------------------------

class ScaleTests(unittest.TestCase):
    """Every new reading is bounded per span; a form block's labels are matched once per text."""

    def test_long_lines_of_boxes_cells_and_periods(self):
        for name, text in (
                ('brackets', HEADER + 'Findings: Colonoscopy. ' + ('[ ] biopsy ( x ) snare [  ] (  ) (•) ' * 1300)[:50000]),
                ('cells', HEADER + 'Findings: Colonoscopy.\n' + ('Biopsy. | ☐ | Cold snare polypectomy. | ☒ | ' * 1200)[:50000]),
                ('periods', HEADER + 'Findings: Colonoscopy.\n' + ('Biopsy. ☐ ' * 6000)[:50000])):
            with self.subTest(name):
                started = time.monotonic()
                route(text)
                status_for_span(text, *span(text, 'iopsy'))
                self.assertLess(time.monotonic() - started, 10)

    def test_a_form_block_with_thousands_of_fields(self):
        text = (HEADER + 'Procedure: Colonoscopy.\n' + '\n'.join(f'Item {n}' for n in range(3000)) +
                '\n\n[PDF form fields on page 1]\n' + '\n'.join(f'Item {n}: not checked' if n % 2 else f'Item {n}: checked'
                                                               for n in range(3000)))
        started = time.monotonic()
        route(text)
        self.assertLess(time.monotonic() - started, 10)
        many = HEADER + ''.join(f'Procedure: Colonoscopy.\nBiopsy\n\n[PDF form fields on page {n}]\nBiopsy: not '
                                f'checked\n\n' for n in range(1, 400))
        started = time.monotonic()
        result = route(many)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(result.finding('gi.colonoscopy').status, 'performed')


if __name__ == '__main__':
    unittest.main()
