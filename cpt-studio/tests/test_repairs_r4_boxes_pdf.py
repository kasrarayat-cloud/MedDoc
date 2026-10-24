"""Regressions for refutation round 4, BOXES lens, real files: PDF forms and Word documents through the sandboxed
extract_document, then routing for the document's own date and the real validation engine.

- structure:12: a checklist typed with boxes routing reads ('[  ]', '(  )', '( )', '[_]') or drawn with a box glyph
  in a text font, made fillable: the widget over the printed box replaces it with its own state, so a checked
  polypectomy is never excluded;
- release:12 (b): a Word document whose box cell or paragraph is a plain box character (U+25A2, U+2B1C) in a text font:
  the unchecked biopsy is never ready (held as an unread mark);
- structure:6, evidence:4, contract:2 and contract:4: fillable PDFs whose fields answer 'No' or 'None' to a question
  that names no item, to one that names an item among other words, or give the procedure a status: an ordinary field
  holds nothing, a qualified one holds only itself, and a status field that says the procedure was not done holds it;
- release:0: a fillable EUS form whose 'Procedure status' radio group has Cancelled selected never readies 43242;
- contract:0, release:5, routing:11: an unchecked attestation box right of the separately identifiable E/M sentence
  (its glyph not placed, only its field line written), or a Word yes/no pair under it answered No, attests nothing.

Synthetic documents only, built here from raw PDF syntax or WordprocessingML.
"""
import unittest

from tests.support import docgen
from tests.test_repairs_r3_forms_docx import control, docx_result, note_paragraphs, paragraph
from tests.test_repairs_r3_forms_pdf import (BIOPSY_ROW, FONTS, SNARE_ROW, Form, codes, extracted, text_line, to_unicode,
                                             widget_rect)
from tests.test_repairs_r3_forms_routing import outcome
from tests.test_repairs_status_r2_routing import clarified, family, read, routed, run_engine

SNARE = 'Cold snare polypectomy'

# A text font whose ToUnicode gives box characters that no symbol font maps (as a Word document saved as PDF writes a
# box typed in Segoe UI Symbol): code 23 U+25A1, 24 U+25A2, 25 U+2B1C, 26 U+2751.
GLYPH_FONT = (f'<< /Type /Font /Subtype /TrueType /BaseFont /Segoe-UI-Symbol /FirstChar 32 /LastChar 255 /Widths ['
              + ' '.join(['1000'] * 224) + '] /ToUnicode 31 0 R >>').encode()
GLYPHS = {'□': '23', '▢': '24', '⬜': '25', '❑': '26'}


class GlyphForm(Form):
    """The FORMS test page, with a text font whose glyphs are box characters (/SG)."""

    def __init__(self, lines=None):
        super().__init__(lines)
        self.objects[30] = GLYPH_FONT
        self.objects[31] = to_unicode([(int(code, 16), glyph) for glyph, code in GLYPHS.items()])

    def build(self) -> bytes:
        data = super().build()
        return data.replace(FONTS.encode(), FONTS.replace('>>', '/SG 30 0 R >>').encode())


def glyph_line(x, y, glyph, label):
    return f'BT /SG 11 Tf {x} {y} Td <{GLYPHS[glyph]}> Tj /F1 11 Tf 18 0 Td ({label}) Tj ET'


class Structure12TypedBoxUnderAWidgetTests(unittest.TestCase):
    """structure:12 (critical, new in 686d60b11). Routing read '[  ]', '(  )', '( )' and '[_]' as boxes, but the PDF reader
    replaced only '[ ]' and '[x]' with a widget's state, so a checked widget over '[  ] Cold snare polypectomy' left the
    printed empty box and the checked polypectomy was excluded. Both readers now build their boxes from the one
    vocabulary (studio.ingest.symbols)."""
    TYPED = ('[  ]', '(  )', '( )', '[_]', '[\t]', '[ ]')

    def form(self, typed, biopsy, snare, tooltips):
        form = Form()
        form.line(text_line(72, BIOPSY_ROW, f'{typed} Biopsy')).line(text_line(72, SNARE_ROW, f'{typed} {SNARE}'))
        form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), biopsy, tu='Biopsy' if tooltips else None)
        form.checkbox('Check Box2', widget_rect(SNARE_ROW), snare, tu=SNARE if tooltips else None)
        return form.build()

    def test_the_widget_decides_the_typed_box(self):
        for typed in self.TYPED:
            for tooltips in (False, True):
                for biopsy, snare in ((False, True), (True, True), (False, False)):
                    with self.subTest(typed=typed, tooltips=tooltips, biopsy=biopsy, snare=snare):
                        result = extracted(self.form(typed, biopsy, snare, tooltips))
                        self.assertEqual(result.status, 'ok', result.messages)
                        glyph = {True: '☒', False: '☐'}
                        self.assertIn(f'Interventions:\n{glyph[biopsy]} Biopsy\n{glyph[snare]} {SNARE}\n', result.text)
                        biopsy_code, snare_code = codes(result.text, ('45380', 'Biopsy'), ('45385', SNARE))
                        self.assertEqual(snare_code == 'excluded', not snare, (biopsy_code, snare_code))
                        self.assertNotEqual(biopsy_code, 'ready' if not biopsy else 'excluded')

    def test_a_box_glyph_in_a_text_font(self):
        for glyph in GLYPHS:
            with self.subTest(glyph=hex(ord(glyph))):
                form = GlyphForm()
                form.line(glyph_line(72, BIOPSY_ROW, glyph, 'Biopsy')).line(glyph_line(72, SNARE_ROW, glyph, SNARE))
                form.checkbox('Check Box1', widget_rect(BIOPSY_ROW), False, tu='Biopsy')
                form.checkbox('Check Box2', widget_rect(SNARE_ROW), True, tu=SNARE)
                result = extracted(form.build())
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertIn(f'☐ Biopsy\n☒ {SNARE}', result.text.replace('☐Biopsy', '☐ Biopsy'))
                self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', SNARE)), ('excluded', 'ready'))

    def test_a_trailing_typed_box_whose_position_cannot_be_read_is_reported(self):
        form = Form()
        form.line(text_line(90, BIOPSY_ROW, 'Biopsy [  ]')).line(text_line(90, SNARE_ROW, f'{SNARE} [  ]'))
        form.checkbox('Check Box1', (124, BIOPSY_ROW - 3, 136, BIOPSY_ROW + 9), False)
        form.checkbox('Check Box2', (214, SNARE_ROW - 3, 226, SNARE_ROW + 9), True)
        result = extracted(form.build())
        self.assertEqual(result.status, 'partial', result.messages)
        self.assertTrue(any('form check box over a printed box' in m for m in result.messages), result.messages)


def glyph_docx(layout, glyph):
    """BOXED, then the biopsy marked with a plain ``glyph`` run in Segoe UI Symbol and the polypectomy with U+2612."""
    def run(text, font=None):
        props = f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}"/></w:rPr>' if font else ''
        return f'<w:r>{props}<w:t xml:space="preserve">{text}</w:t></w:r>'
    if layout == 'table':
        rows = [(glyph, 'Biopsy'), ('☒', SNARE)]
        body = '<w:tbl>' + ''.join(f'<w:tr><w:tc><w:p>{run(box, "Segoe UI Symbol")}</w:p></w:tc><w:tc>{paragraph(label)}'
                                   '</w:tc></w:tr>' for box, label in rows) + '</w:tbl>'
    else:
        body = ''.join(f'<w:p>{run(box, "Segoe UI Symbol")}{run(" " + label)}</w:p>'
                       for box, label in ((glyph, 'Biopsy'), ('☒', SNARE)))
    return docgen.make_docx_from_body(note_paragraphs() + body)


class Release12PlainBoxCharactersInWordTests(unittest.TestCase):
    """release:12 (b) (critical). A Word document whose box is the plain character U+25A2 or U+2B1C in a text font (not
    a content control) was passed over, so the unchecked biopsy was a ready 45380. It is now an unread mark: held."""

    def test_the_unchecked_biopsy_is_never_ready(self):
        for layout in ('table', 'paragraphs'):
            for glyph in ('▢', '⬜'):
                with self.subTest(layout=layout, glyph=hex(ord(glyph))):
                    result = docx_result(glyph_docx(layout, glyph))
                    self.assertEqual(result.status, 'ok', result.messages)
                    self.assertIn(glyph, result.text)
                    self.assertEqual(read(result.text, 'Biopsy')[0], 'uncertain')
                    self.assertEqual(codes(result.text, ('45380', 'Biopsy'), ('45385', SNARE)), ('held', 'ready'))


DATE_LINES = [(72, 740, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'), (72, 720, 'Date of service: 2026-10-21')]


def page_form(lines):
    """A form page with DATE_LINES and then ``lines`` (one Helvetica line each, 20 points apart)."""
    return Form(DATE_LINES + [(72, 700 - 20 * n, line) for n, line in enumerate(lines)])


def row_y(lines, index):
    return 700 - 20 * index


OFFICE_LINES = ['Place of service: Office (POS 11)', 'Established patient office visit for rectal bleeding.',
                'Chief complaint: Rectal bleeding.', 'Assessment: Hematochezia.', 'Medical decision making: moderate.',
                'Total time: 32 minutes.', 'Procedure: Flexible sigmoidoscopy with biopsy. The sigmoidoscope was advanced to '
                '40 cm.', 'Biopsies were taken from the rectum.']
VISIT = 'Established patient office visit for rectal bleeding.'


class Structure6QualifiedFieldInAPdfTests(unittest.TestCase):
    """structure:6 (critical): a text field answering 'No' to 'Flexible sigmoidoscopy in the last 10 years', beside its
    printed label, negated the same-day flexible sigmoidoscopy and released the office E/M."""

    def test_the_office_e_m_stays_held(self):
        for label, value in (('Flexible sigmoidoscopy in the last 10 years:', 'No'),
                             ('Flexible sigmoidoscopy complications:', 'None')):
            with self.subTest(label=label):
                form = page_form(OFFICE_LINES + [label])
                y = row_y(OFFICE_LINES, len(OFFICE_LINES))
                form.textfield(label.rstrip(':'), (330, y - 3, 450, y + 11), value)
                result = extracted(form.build())
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertIn(f'{label.rstrip(":")}: {value}', result.text)
                self.assertEqual(family(result.text, 'gi.flex_sig'), 'performed')
                proposals, _ = run_engine(result.text, [('99214', VISIT)])
                self.assertEqual(outcome(proposals['99214']), 'held')
                self.assertIn('separate_em', clarified(proposals['99214']))


COLON_LINES = ['Procedure: Colonoscopy. The colonoscope was advanced to the cecum.',
               'Findings: A 6 mm sigmoid polyp was removed with a cold snare.', 'Complications (if any):']
POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


class Evidence4OrdinaryTextFieldInAPdfTests(unittest.TestCase):
    """evidence:4 and contract:2 (medium/high, new in 686d60b11): a text field 'Complications' typed 'None' held every
    code on a fillable report; a generic text field may still answer for an item, so it still holds."""

    def form(self, name, value):
        form = page_form(COLON_LINES)
        y = row_y(COLON_LINES, 2)
        form.textfield(name, (220, y - 3, 400, y + 11), value)
        return extracted(form.build()).text

    def test_an_ordinary_field_holds_nothing(self):
        for name, value in (('Complications', 'None'), ('Complications', 'No'), ('Complications if any', 'None'),
                            ('EBL', 'None')):
            with self.subTest(name=name, value=value):
                text = self.form(name, value)
                self.assertEqual(codes(text, ('45385', POLYP), ('45378', 'Colonoscopy')), ('ready', 'ready'))

    def test_a_generic_field_still_holds_truthfully(self):
        text = self.form('Text7', 'None')
        self.assertEqual(codes(text, ('45378', 'Colonoscopy'))[0], 'held')
        self.assertIn('may answer for an item', read(text, 'Colonoscopy')[1][0])


EUS_LINES = ['Procedure: EUS with fine-needle biopsy of a pancreatic cyst.', 'Indication: Pancreatic cyst on CT.',
             'History reviewed.', 'Consent obtained.', 'ASA class II.', 'Airway assessed.', 'Allergies: none known.',
             'Anticoagulants: none.', 'NPO since midnight.']
EUS_LINE = 'EUS with fine-needle biopsy of a pancreatic cyst.'


def status_radio_form(selected, lines_after=0):
    """EUS_LINES' procedure line, the 'Procedure status' radio row (Completed / Cancelled), then the rest."""
    lines = EUS_LINES[:1] + ['Procedure status:'] + EUS_LINES[1:1 + lines_after]
    form = page_form(lines)
    y = row_y(lines, 1)
    form.line(text_line(200, y, 'Completed')).line(text_line(300, y, 'Cancelled'))
    form.group('Procedure status', [(widget_rect(y, 184), '/Completed'), (widget_rect(y, 284), '/Cancelled')],
               f'/{selected}')
    return extracted(form.build())


class Contract4StatusFieldInAPdfTests(unittest.TestCase):
    """contract:4 (critical): every field is written after its page's text, beyond the status readers' reach, so a
    'Procedure status' field saying Cancelled or Not performed never reached routing and the cancelled EUS was a ready,
    approvable 43242. release:0 (critical): the same through a radio group with Cancelled selected."""

    def text_field_form(self, value):
        form = page_form(EUS_LINES + ['Procedure status:'])
        y = row_y(EUS_LINES, len(EUS_LINES))
        form.textfield('Procedure status', (190, y - 3, 560, y + 11), value)
        return extracted(form.build()).text

    def test_a_status_text_field(self):
        for value in ('Cancelled - the patient had eaten breakfast', 'Not performed', 'Rescheduled to next week'):
            with self.subTest(value=value):
                text = self.text_field_form(value)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                self.assertEqual(codes(text, ('43242', EUS_LINE))[0], 'held')
        self.assertEqual(codes(self.text_field_form('Completed'), ('43242', EUS_LINE))[0], 'ready')

    def test_a_status_radio_group(self):
        for lines_after in (0, 8):
            with self.subTest(lines_after=lines_after):
                result = status_radio_form('Cancelled', lines_after)
                self.assertEqual(result.status, 'ok', result.messages)
                self.assertTrue(result.text.rstrip().endswith('Procedure status: Cancelled'), result.text[-80:])
                self.assertEqual(codes(result.text, ('43242', EUS_LINE))[0], 'held')
                # Completed selected writes the mirror row '☒ Completed ☐ Cancelled', which stays at most held (as at
                # HEAD: the hold-only repair keeps the old first-box test as its precondition), never excluded
                completed = status_radio_form('Completed', lines_after)
                self.assertIn(codes(completed.text, ('43242', EUS_LINE))[0], ('ready', 'held'))


class Contract2CancelledNoRadioTests(unittest.TestCase):
    """contract:2 (S5): a radio 'Procedure cancelled' with No selected (the procedure was not cancelled) is a status
    question answered no: held, never excluded, and never with the false 'no printed line on its page names it'."""

    def test_the_colonoscopy_is_never_excluded(self):
        lines = COLON_LINES[:2] + ['Procedure cancelled:']
        form = page_form(lines)
        y = row_y(lines, 2)
        form.line(text_line(200, y, 'Yes')).line(text_line(260, y, 'No'))
        form.group('Procedure cancelled', [(widget_rect(y, 184), '/Yes'), (widget_rect(y, 244), '/No')], '/No')
        result = extracted(form.build())
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertNotIn(family(result.text, 'gi.colonoscopy'), ('cancelled', 'negated'))
        self.assertNotEqual(codes(result.text, ('45385', POLYP))[0], 'excluded')
        for cue in read(result.text, 'Colonoscopy')[1]:
            self.assertNotIn('no printed line on its page names it', cue)


ATTEST_OFFICE = ['Place of service: Office (POS 11)', 'Established patient office visit for rectal bleeding.',
                 'Medical decision making: Moderate.', 'Total time on the date of the encounter was 32 minutes.',
                 'Procedure: Flexible sigmoidoscopy with biopsy was performed. The sigmoidoscope was advanced to 40 cm.']
ATTESTATION = 'I performed a significant, separately identifiable E/M service on the same day as the procedure.'
ATTEST_PICKS = [('99214', 'Total time on the date of the encounter was 32 minutes.'),
                ('45331', 'Flexible sigmoidoscopy with biopsy was performed.')]


def separate_em(text):
    return next((f for f in routed(text).finding('gi.office_em').facts if f.name == 'separate_em'), None)


def attestation_pdf(name, checked, *, tu=None, left=False, two_lines=False):
    """ATTEST_OFFICE, then the attestation in 8-point Helvetica with a check box right of it (or, ``left``, before it)."""
    form = page_form(ATTEST_OFFICE)
    y = row_y(ATTEST_OFFICE, len(ATTEST_OFFICE))
    if two_lines:
        form.line(text_line(72, y, 'I performed a significant, separately identifiable E/M service', size=8))
        form.line(text_line(72, y - 12, 'on the same day as the procedure.', size=8))
        rect = (220, y - 15, 232, y - 3)
    else:
        form.line(text_line(72, y, ATTESTATION, size=8))
        rect = (56, y - 3, 68, y + 9) if left else (470, y - 3, 482, y + 9)
    form.checkbox(name, rect, checked, tu=tu)
    return extracted(form.build())


class Contract0AttestationBoxInAPdfTests(unittest.TestCase):
    """contract:0 and release:5 (critical): an unchecked check box right of the attestation sentence writes no glyph,
    only its form-field line, and the statement was accepted: 99214 was ready and approved beside a same-day flexible
    sigmoidoscopy with biopsy. An untied denying field on the statement's page refuses it."""

    def assert_attested(self, result, attested):
        self.assertEqual(result.status, 'ok', result.messages)
        fact = separate_em(result.text)
        proposals, _ = run_engine(result.text, ATTEST_PICKS)
        if attested:
            self.assertIsNotNone(fact, result.text[-300:])
            self.assertNotIn('separate_em', clarified(proposals['99214']))
        else:
            self.assertIsNone(fact, result.text[-300:])
            self.assertEqual(outcome(proposals['99214']), 'held')
            self.assertIn('separate_em', clarified(proposals['99214']))

    def test_an_unchecked_box_right_of_the_sentence_refuses_it(self):
        for name, tu in (('Check Box1', 'Separate E/M attestation'), ('Check Box1', 'Modifier 25 attestation'),
                         ('Check Box1', None), ('Check Box3', None)):
            with self.subTest(name=name, tu=tu):
                result = attestation_pdf(name, False, tu=tu)
                self.assertIn(f'{tu or name}: not checked', result.text)
                self.assert_attested(result, False)
        self.assert_attested(attestation_pdf('Check Box1', False, two_lines=True), False)

    def test_checked_and_left_boxes(self):
        self.assert_attested(attestation_pdf('Check Box1', True, tu='Separate E/M attestation'), True)
        left = attestation_pdf('Check Box1', False, left=True)
        self.assertIn('\u2610 I performed', left.text)
        self.assert_attested(left, False)


def attestation_docx(yes, no, statement='A significant, separately identifiable E/M service was provided:'):
    lines = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'Date of service: 2026-10-21'] + ATTEST_OFFICE + [statement]
    pair = (f'<w:p>{control(yes)}<w:r><w:t xml:space="preserve"> Yes   </w:t></w:r>{control(no)}'
            '<w:r><w:t xml:space="preserve"> No</w:t></w:r></w:p>')
    return docgen.make_docx_from_body(''.join(paragraph(line) for line in lines) + pair)


class Routing11AttestationAnswerInWordTests(unittest.TestCase):
    """routing:11 and contract:0 (d) (high/critical): the statement followed by a line of two Word check-box controls
    answered No was accepted. The line under it is its answer."""

    def test_the_answer_on_the_next_line_decides(self):
        for yes, no, attested in ((False, True, False), (False, False, False), (True, True, False), (True, False, True)):
            with self.subTest(yes=yes, no=no):
                result = docx_result(attestation_docx(yes, no))
                self.assertEqual(result.status, 'ok', result.messages)
                fact = separate_em(result.text)
                self.assertEqual(fact is not None, attested, result.text[-160:])


if __name__ == '__main__':
    unittest.main()
