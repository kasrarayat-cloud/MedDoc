"""Drawn signing bands, optional response bands, wrapped insertions and paired heading captions.

Pure XML/parser controls on project-authored synthetic documents; no corpus content, no app resources.
"""
import io
import unittest

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from lxml import etree

from . import word_v3 as word

NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'v': 'urn:schemas-microsoft-com:vml',
}
DECLARED = ' '.join('xmlns:%s="%s"' % item for item in NAMESPACES.items())
BODY = 'word/document.xml#'


def data(document):
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def line_run(number, *, width=2286000, height=0, prst='line', anchored=False, textbox=False, fallback=True,
             drawn_height=0):
    """One drawn line as Word writes it: modern DrawingML with an optional VML fallback."""
    container = 'anchor' if anchored else 'inline'
    attributes = (' behindDoc="0" distT="0" distB="0" distL="0" distR="0" simplePos="0" locked="0"'
                  ' layoutInCell="1" allowOverlap="1" relativeHeight="%d"' % number) if anchored else \
        ' distT="0" distB="0" distL="0" distR="0"'
    position = ('<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset>'
                '</wp:positionH><wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
                if anchored else '')
    text = '<wps:txbx><w:txbxContent><w:p><w:r><w:t>x</w:t></w:r></w:p></w:txbxContent></wps:txbx>' if textbox else ''
    drawing = (
        '<w:drawing><wp:{c}{attrs}>{pos}<wp:extent cx="{w}" cy="{h}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        '{wrap}<wp:docPr id="{n}" name="Line {n}" descr="blank line"/><wp:cNvGraphicFramePr/><a:graphic>'
        '<a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp>'
        '<wps:cNvCnPr/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{w}" cy="{dh}"/></a:xfrm>'
        '<a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom><a:ln w="6350"><a:solidFill><a:srgbClr val="000000"/>'
        '</a:solidFill></a:ln></wps:spPr>{text}<wps:bodyPr/></wps:wsp></a:graphicData></a:graphic></wp:{c}>'
        '</w:drawing>').format(c=container, attrs=attributes, pos=position, w=width, h=height, n=number,
                               prst=prst, dh=drawn_height, text=text, wrap='<wp:wrapNone/>' if anchored else '')
    if fallback:
        drawing = ('<mc:AlternateContent><mc:Choice Requires="wps">%s</mc:Choice><mc:Fallback><w:pict>'
                   '<v:line id="Line %d" style="position:absolute" from="0,0" to="180pt,0" strokeweight=".5pt"/>'
                   '</w:pict></mc:Fallback></mc:AlternateContent>') % (drawing, number)
    return etree.fromstring('<w:r %s>%s</w:r>' % (DECLARED, drawing))


def drawn_band(caption='Signature of Patient or Representative\t\t\tDate', *, lines=2, spacer=True, **shape):
    """Clinical summary / drawn lines / caption below / spacer / ordinary visit date."""
    doc = Document()
    doc.add_paragraph('Clinical summary: ________')
    paragraph = doc.add_paragraph()
    for number in range(lines):
        if number:
            paragraph.add_run('\t\t')
        paragraph._p.append(line_run(number + 1, **shape))
    doc.add_paragraph(caption)
    if spacer:
        doc.add_paragraph()
    doc.add_paragraph('Visit date: ________')
    return data(doc)


def slot_bytes(raw, slot):
    return word.fingerprint(word.SlotIndex(word.open_package(raw)).by_id[BODY + slot].el)


class DrawnSigningBand(unittest.TestCase):
    def test_inline_line_pair_is_one_protected_signing_event(self):
        raw = drawn_band()
        fields = word.inspect(raw)['fields']
        held = [f for f in fields if f.get('write_protected')]
        self.assertEqual([(f['kind'], f['label'], f['locator']['slot'], f['locator']['target']['type']) for f in held],
                         [('signature', 'Signature of Patient or Representative', 'b/p[1]', 'none'),
                          ('date', 'Date', 'b/p[1]', 'none')])
        for field in held:
            relation = field['source_questions'][0]
            self.assertEqual(relation['relation'], 'protected_inline_signing_lines')
            self.assertEqual(relation['source']['slot'], 'b/p[2]')
            self.assertEqual(len(relation['drawings']), 2)
        # Neither the caption nor the spacer below it becomes an answer destination.
        self.assertFalse([f for f in fields if f['locator']['slot'] in ('b/p[2]', 'b/p[3]')])
        for field in held:
            with self.assertRaises(word.V3Failure):
                word.fill(raw, fields, {field['key']: '14/03/2026' if field['kind'] == 'date' else 'Pat Example'})

    def test_ordinary_answers_fill_while_lines_fallbacks_caption_and_spacer_stay_byte_identical(self):
        raw = drawn_band()
        fields = word.inspect(raw)['fields']
        visit = next(f for f in fields if f['label'] == 'Visit date')
        summary = next(f for f in fields if f['label'] == 'Clinical summary')
        final = word.fill(raw, fields, {visit['key']: '14/03/2026', summary['key']: 'Synthetic stable review.'})
        for slot in ('b/p[1]', 'b/p[2]', 'b/p[3]'):
            self.assertEqual(slot_bytes(raw, slot), slot_bytes(final, slot), slot)
        index = word.SlotIndex(word.open_package(final))
        self.assertIn('14/03/2026', word.paragraph_text(index.by_id[BODY + 'b/p[4]'].el)[0])
        drawing = index.by_id[BODY + 'b/p[1]'].el
        self.assertEqual(len(drawing.findall('.//{%s}Fallback' % NAMESPACES['mc'])), 2)

    def test_forged_ordinary_date_on_the_signing_spacer_is_refused(self):
        raw = drawn_band()
        fields = word.inspect(raw)['fields']
        spacer = word.SlotIndex(word.open_package(raw)).by_id[BODY + 'b/p[3]']
        forged = {'key': 'v3_99', 'kind': 'date', 'label': 'Signature of Patient or Representative Date', 'context': '',
                  'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[3]',
                              'fingerprint': word.fingerprint(spacer.el), 'target': {'type': 'paragraph'}}}
        with self.assertRaises(word.V3Failure):
            word.fill(raw, fields + [forged], {'v3_99': '14/03/2026'})
        with self.assertRaises(word.V3Failure):
            word.fill(raw, [forged], {'v3_99': '14/03/2026'})

    def test_every_other_drawn_or_undrawn_signing_caption_holds_the_blank_below(self):
        shapes = {'anchored': {'anchored': True}, 'rectangle': {'prst': 'rect'}, 'text box': {'textbox': True},
                  'tall': {'height': 50800}, 'diagonal': {'drawn_height': 100}, 'one line': {'lines': 1},
                  'three lines': {'lines': 3}, 'no drawing': {'lines': 0},
                  'clinician': {'caption': 'Clinician signature\t\t\tDate', 'anchored': True}}
        for name, options in shapes.items():
            with self.subTest(name):
                raw = drawn_band(**options)
                fields = word.inspect(raw)['fields']
                writable = [f for f in fields if not f.get('write_protected')
                            and f['kind'] not in ('signature', 'initials')]
                self.assertEqual(sorted(f['label'] for f in writable), ['Clinical summary', 'Visit date'])
                for field in fields:
                    if field.get('write_protected') and field['locator']['target']['type'] != 'none':
                        with self.assertRaises(word.V3Failure):
                            word.fill(raw, fields, {field['key']: '14/03/2026'})

    def test_ordinary_captions_under_lines_are_not_signing_events(self):
        raw = drawn_band(caption='Printed name\t\t\tTitle')
        fields = word.inspect(raw)['fields']
        self.assertFalse([f for f in fields if f.get('write_protected')])
        self.assertFalse([f for f in fields if any(r.get('relation') == 'protected_inline_signing_lines'
                                                   for r in f.get('source_questions', []))])

    def test_a_bare_date_caption_under_its_line_is_not_promoted_to_a_signing_event(self):
        raw = drawn_band(caption='Date', lines=1)
        fields = word.inspect(raw)['fields']
        self.assertFalse([f for f in fields if f.get('write_protected')])


def optional_band(caption='Additional information (optional):', blanks=8, *, bold=True, break_at=None,
                  then='Sign below to show you received this notice.'):
    doc = Document()
    doc.add_paragraph('Patient number: ________')
    paragraph = doc.add_paragraph()
    paragraph.add_run(caption).bold = bold
    for number in range(blanks):
        blank = doc.add_paragraph()
        if break_at is not None and number >= break_at:
            blank.paragraph_format.space_after = Pt(18)
    doc.add_paragraph(then)
    return data(doc)


def body_paragraphs(raw):
    package = word.open_package(raw)
    return list(package.tree('word/document.xml').find(word.q('w:body')).iterchildren(word.q('w:p')))


class OptionalResponseBand(unittest.TestCase):
    def band_field(self, raw):
        return [f for f in word.inspect(raw)['fields']
                if any(r.get('relation') == 'narrative_empty_band' for r in f.get('source_questions', []))]

    def test_explicit_optional_caption_owns_its_uniform_blank_band(self):
        raw = optional_band()
        bands = self.band_field(raw)
        self.assertEqual(len(bands), 1)
        field = bands[0]
        self.assertEqual((field['kind'], field['locator']['slot']), ('long_text', 'b/p[2]'))
        self.assertEqual([x['slot'] for x in field['locator']['extra']], ['b/p[%d]' % n for n in range(3, 10)])
        self.assertEqual(field['source_questions'][0]['source']['slot'], 'b/p[1]')
        self.assertFalse([f for f in word.inspect(raw)['fields'] if f['locator']['slot'] == 'b/p[1]'])
        final = word.fill(raw, [field], {field['key']: 'First synthetic line\nSecond synthetic line'})
        old, new = body_paragraphs(raw), body_paragraphs(final)
        self.assertEqual(len(old), len(new))
        for number in (0, 1, 10):
            self.assertEqual(word.fingerprint(old[number]), word.fingerprint(new[number]), number)
        self.assertEqual(word.text_of(new[2]), 'First synthetic line')
        self.assertEqual(word.text_of(new[3]), 'Second synthetic line')

    def test_style_transition_ends_the_band_and_one_blank_is_no_band(self):
        field = self.band_field(optional_band(break_at=3))[0]
        self.assertEqual([x['slot'] for x in field['locator']['extra']], ['b/p[3]', 'b/p[4]'])
        self.assertFalse(self.band_field(optional_band(blanks=1)))

    def test_signature_optional_caption_never_yields_an_ordinary_answer(self):
        raw = optional_band(caption='Representative signature (optional):')
        fields = word.inspect(raw)['fields']
        for field in fields:
            if field['locator']['slot'] in ['b/p[%d]' % n for n in range(1, 10)]:
                self.assertTrue(field['kind'] in ('signature', 'initials') or field.get('write_protected'), field)

    def test_caption_without_the_optional_request_keeps_its_existing_reading(self):
        self.assertFalse(self.band_field(optional_band(caption='Additional information:')))

    def test_a_second_writer_inside_the_band_is_refused(self):
        raw = optional_band()
        field = self.band_field(raw)[0]
        third = word.SlotIndex(word.open_package(raw)).by_id[BODY + 'b/p[4]']
        forged = {'key': 'v3_99', 'kind': 'text', 'label': 'Other note', 'context': '',
                  'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[4]',
                              'fingerprint': word.fingerprint(third.el), 'target': {'type': 'paragraph'}}}
        with self.assertRaises(word.V3Failure):
            word.fill(raw, [field, forged], {field['key']: 'Band answer', 'v3_99': 'Forged'})


def broken_insertion(kind=None):
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run('Coverage of your current {insert type}')
    brk = OxmlElement('w:br')
    if kind:
        brk.set(qn('w:type'), kind)
    paragraph.add_run()._r.append(brk)
    paragraph.add_run('services will end on {insert effective date}')
    doc.add_paragraph('Fixed following text.')
    return data(doc)


class WrappedInsertion(unittest.TestCase):
    def insertions(self, raw):
        return [f for f in word.inspect(raw)['fields']
                if any(r.get('relation') == 'explicit_insertion' for r in f.get('source_questions', []))]

    def test_ordinary_line_break_keeps_both_insertions_and_the_break(self):
        for kind in (None, 'textWrapping'):
            with self.subTest(kind):
                raw = broken_insertion(kind)
                fields = self.insertions(raw)
                self.assertEqual(sorted(f['label'] for f in fields), ['effective date', 'type'])
                answers = {f['key']: ('14/03/2026' if f['kind'] == 'date' else 'home health') for f in fields}
                final = word.fill(raw, fields, answers)
                paragraph = body_paragraphs(final)[0]
                self.assertEqual(word.paragraph_text(paragraph)[0],
                                 'Coverage of your current home health\nservices will end on 14/03/2026')
                self.assertEqual(len(paragraph.findall('.//' + word.q('w:br'))), 1)
                self.assertEqual(word.fingerprint(body_paragraphs(raw)[1]), word.fingerprint(body_paragraphs(final)[1]))

    def test_page_and_column_breaks_are_never_crossed(self):
        for kind in ('page', 'column'):
            with self.subTest(kind):
                self.assertFalse(self.insertions(broken_insertion(kind)))


def heading(text, style='Heading 2'):
    doc = Document()
    doc.add_paragraph(text, style=style)
    doc.add_paragraph('Fixed following text.')
    return data(doc)


class PairedHeadingCaptions(unittest.TestCase):
    def test_two_complete_captions_with_real_gaps_keep_their_destinations(self):
        fields = word.inspect(heading('Patient name:\t\t\t\t\tPatient number:'))['fields']
        self.assertEqual([(f['label'], f['locator']['target'].get('shape')) for f in fields],
                         [('Patient name', 'after_label'), ('Patient number', 'after_label')])
        final = word.fill(heading('Patient name:\t\t\t\t\tPatient number:'), fields,
                          {fields[0]['key']: 'Pat Example', fields[1]['key']: 'SYN-1'})
        text = word.paragraph_text(body_paragraphs(final)[0])[0]
        self.assertLess(text.index('Pat Example'), text.index('Patient number:'))
        self.assertTrue(text.rstrip().endswith('SYN-1'))

    def test_single_heading_caption_and_non_field_headings_stay_fixed(self):
        for text in ('Patient name:', 'Section A:\t\t\tSection B:', 'Summary:\t\t\tDetails:'):
            with self.subTest(text):
                self.assertEqual(word.inspect(heading(text))['fields'], [])


if __name__ == '__main__':
    unittest.main()
