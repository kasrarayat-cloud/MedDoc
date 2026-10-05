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


def drawn_band(caption='Signature of Patient or Representative\t\t\tDate', *, lines=2, spacer=True, spacer_xml='',
               **shape):
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
        blank = doc.add_paragraph()
        if spacer_xml:
            for node in etree.fromstring('<w:wrap %s>%s</w:wrap>' % (DECLARED, spacer_xml)):
                blank._p.append(node)
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

    def test_a_blank_under_the_drawn_caption_stays_held_whatever_its_empty_formatting(self):
        variants = {'tab only': '<w:r><w:tab/></w:r>',
                    'empty underlined run': '<w:r><w:rPr><w:u w:val="single"/></w:rPr></w:r>',
                    'underlined paragraph mark': '<w:pPr><w:rPr><w:u w:val="single"/></w:rPr></w:pPr>'}
        for name, xml in variants.items():
            with self.subTest(name):
                raw = drawn_band(spacer_xml=xml)
                fields = word.inspect(raw)['fields']
                self.assertFalse([f for f in fields if f['locator']['slot'] == 'b/p[3]'])
                blank = word.SlotIndex(word.open_package(raw)).by_id[BODY + 'b/p[3]']
                stored = {'key': 'v3_9', 'kind': 'date', 'label': 'Signature of Patient or Representative Date',
                          'context': '', 'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[3]',
                                                     'fingerprint': word.fingerprint(blank.el),
                                                     'target': {'type': 'paragraph'}}}
                with self.assertRaises(word.V3Failure):
                    word.fill(raw, [stored], {'v3_9': '14/03/2026'})
                with self.assertRaises(word.V3Failure):
                    word.locate(raw, [{'kind': 'date', 'label': 'Date', 'slot': BODY + 'b/p[3]'}])

    def test_a_bare_date_caption_under_its_line_is_not_promoted_to_a_signing_event(self):
        raw = drawn_band(caption='Date', lines=1)
        fields = word.inspect(raw)['fields']
        self.assertFalse([f for f in fields if f.get('write_protected')])


def caption_over_blank(caption, style=None):
    doc = Document()
    doc.add_paragraph('Clinical summary: ________')
    doc.add_paragraph(caption, style=style) if style else doc.add_paragraph(caption)
    doc.add_paragraph()
    doc.add_paragraph('Plan: ____________')
    return data(doc)


class SigningCaptionHold(unittest.TestCase):
    """The blank below a printed signing caption belongs to that signing act."""

    def below(self, raw):
        return [f for f in word.inspect(raw)['fields'] if f['locator']['slot'] == 'b/p[2]']

    def test_signing_event_captions_hold_the_blank_below(self):
        for caption in ('Signature of Patient or Representative\t\t\tDate', 'Patient signature\t\t\tDate',
                        'Date of signing:', 'Date participant signs:', 'Date witness initials:',
                        'Date consent granted:', 'Date of signatures:'):
            with self.subTest(caption):
                raw = caption_over_blank(caption)
                fields = word.inspect(raw)['fields']
                below = [f for f in fields if f['locator']['slot'] == 'b/p[2]']
                for field in below:
                    self.assertTrue(field.get('write_protected') or field['kind'] in ('signature', 'initials'), field)
                    if field.get('write_protected'):
                        with self.assertRaises(word.V3Failure):
                            word.fill(raw, fields, {field['key']: '14/03/2026'})

    def test_ordinary_date_captions_keep_their_writable_blank(self):
        for caption in ('Date of assessment:', 'Visit date:', 'Date of birth:', 'Date of procedure:',
                        'Date signed report received:', 'Date received signed report:',
                        'Date nurse received the signed report:', 'Review date:'):
            with self.subTest(caption):
                raw = caption_over_blank(caption)
                fields = word.inspect(raw)['fields']
                below = [f for f in fields if f['locator']['slot'] == 'b/p[2]']
                self.assertEqual([f.get('write_protected', False) for f in below], [False] * len(below))
                if below:
                    final = word.fill(raw, fields, {below[0]['key']: '14/03/2026'})
                    index = word.SlotIndex(word.open_package(final))
                    self.assertIn('14/03/2026', word.paragraph_text(index.by_id[BODY + 'b/p[2]'].el)[0])


class WithdrawnRelaxationsKeepTheirReading(unittest.TestCase):
    """Independent refutation (2026-10-05) showed three paragraph relaxations wrote into section titles, deleted
    line breaks or blocked generation for ordinary forms; they were withdrawn. These are its counterexamples."""

    def test_heading_section_titles_with_field_words_stay_fixed(self):
        for text, style in (('Patient Details:\t\t\t\tNext of Kin Details:', 'Heading 2'),
                            ('Clinical Notes:\t\t\t\tNursing Notes:', 'Heading 2'),
                            ('Patient name:\t\t\t\t\tPatient number:', 'Heading 2')):
            with self.subTest(text):
                doc = Document()
                doc.add_paragraph(text, style=style)
                doc.add_paragraph('Name: ____________________\t\tName: ____________________')
                fields = word.inspect(data(doc))['fields']
                self.assertFalse([f for f in fields if f['locator']['slot'] == 'b/p[0]'])

    def test_a_request_wrapped_by_a_line_break_is_never_written_across_the_break(self):
        doc = Document()
        doc.add_paragraph('Notice to the patient.')
        paragraph = doc.add_paragraph()
        paragraph._p.append(etree.fromstring('<w:r %s><w:t>Enter</w:t><w:br/><w:t xml:space="preserve">the referring '
                                             'clinician here</w:t></w:r>' % DECLARED))
        doc.add_paragraph('Fixed following text.')
        found = word.inspect(data(doc))
        self.assertFalse([f for f in found['fields'] if f['locator']['slot'] == 'b/p[1]'])

    def test_optional_caption_over_irregular_blanks_keeps_its_own_answer_and_generation(self):
        doc = Document()
        doc.add_paragraph('Patient number: ________')
        doc.add_paragraph('Allergies (optional):')
        for _ in range(3):
            doc.add_paragraph().add_run('\t')
        doc.add_paragraph('Visit date: ________')
        raw = data(doc)
        found = word.inspect(raw)
        self.assertFalse([i for i in found['coverage_issues'] if i['code'] == 'unresolved_narrative_band'])
        caption = [f for f in found['fields'] if f['label'].startswith('Allergies')]
        self.assertEqual(len(caption), 1)
        word.fill(raw, found['fields'], {caption[0]['key']: 'Synthetic answer text'})


if __name__ == '__main__':
    unittest.main()
