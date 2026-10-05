"""Drawn signing bands, signing-caption holds, and the withdrawn paragraph relaxations' counterexamples.

Pure XML/parser controls on project-authored synthetic documents; no corpus content, no app resources.
"""
import io
import json
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

    def test_other_drawings_or_no_drawing_are_not_a_drawn_band(self):
        # Only the exact inline line pair is a drawn band; every other shape keeps the engine's existing reading.
        shapes = {'anchored': {'anchored': True}, 'rectangle': {'prst': 'rect'}, 'text box': {'textbox': True},
                  'tall': {'height': 50800}, 'diagonal': {'drawn_height': 100}, 'one line': {'lines': 1},
                  'three lines': {'lines': 3}, 'no drawing': {'lines': 0}}
        for name, options in shapes.items():
            with self.subTest(name):
                fields = word.inspect(drawn_band(**options))['fields']
                self.assertFalse([f for f in fields if any(r.get('relation') == 'protected_inline_signing_lines'
                                                           for r in f.get('source_questions', []))])

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

    def test_a_spacer_that_anchors_a_text_box_is_not_part_of_the_band(self):
        # Refutation 2026-10-05 (round 3): an empty-looking spacer that anchors a floating text box was claimed,
        # so the text box's own field was offered and then every export refused.
        box = ('<w:r><w:drawing><wp:anchor behindDoc="0" distT="0" distB="0" distL="0" distR="0" simplePos="0" '
               'locked="0" layoutInCell="1" allowOverlap="1" relativeHeight="9"><wp:simplePos x="0" y="0"/>'
               '<wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset></wp:positionH>'
               '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
               '<wp:extent cx="2286000" cy="457200"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapSquare wrapText="bothSides"/>'
               '<wp:docPr id="9" name="Box 9"/><wp:cNvGraphicFramePr/><a:graphic><a:graphicData '
               'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp><wps:cNvSpPr/>'
               '<wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="2286000" cy="457200"/></a:xfrm>'
               '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></wps:spPr><wps:txbx><w:txbxContent><w:p><w:r>'
               '<w:t xml:space="preserve">Office use - reference number: ________</w:t></w:r></w:p></w:txbxContent>'
               '</wps:txbx><wps:bodyPr/></wps:wsp></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>')
        raw = drawn_band(spacer_xml=box)
        fields = word.inspect(raw)['fields']
        band = [f for f in fields if any(r.get('relation') == 'protected_inline_signing_lines'
                                         for r in f.get('source_questions', []))]
        self.assertEqual(len(band), 2)
        writable = [f for f in fields if not f.get('write_protected') and f['kind'] not in ('signature', 'initials')]
        self.assertIn('word/document.xml#b/p[3]/txbx[0]/p[0]',
                      [f['locator']['part'] + '#' + f['locator']['slot'] for f in writable])
        answers = {f['key']: '14/03/2026' if f['kind'] == 'date' else 'REF-123' for f in writable}
        final = word.fill(raw, fields, answers)
        self.assertIn('REF-123', ''.join(word.text_of(n) for n in
                      word.SlotIndex(word.open_package(final)).by_id[BODY + 'b/p[3]'].el.iter(word.TXBX)))

    def test_a_bare_date_caption_under_its_line_is_not_promoted_to_a_signing_event(self):
        raw = drawn_band(caption='Date', lines=1)
        fields = word.inspect(raw)['fields']
        self.assertFalse([f for f in fields if f.get('write_protected')])

    def test_a_drawn_band_inside_a_table_cell_leaves_the_table_log_writable(self):
        # A protected region inside a table makes its table_rows writer refuse, so the drawn band is read at body
        # level only (refutation 2026-10-05). The in-cell signing date stays held by its own caption.
        doc = Document()
        doc.add_paragraph('Synthetic medication record')
        table = doc.add_table(rows=4, cols=3)
        for n, text in enumerate(('Medication', 'Dose', 'Route')):
            table.cell(0, n).text = text
        cell = table.cell(3, 0).merge(table.cell(3, 2))
        lines = cell.paragraphs[0]
        lines._p.append(line_run(1, fallback=False))
        lines.add_run('\t\t')
        lines._p.append(line_run(2, fallback=False))
        cell.add_paragraph('Signature of Patient or Representative\t\t\tDate')
        cell.add_paragraph('')
        doc.add_paragraph('Neighbor findings: ______')
        raw = data(doc)
        fields = word.inspect(raw)['fields']
        self.assertFalse([f for f in fields if any(r.get('relation') == 'protected_inline_signing_lines'
                                                   for r in f.get('source_questions', []))])
        log = [f for f in fields if f['kind'] == 'table_rows']
        self.assertEqual(len(log), 1)
        final = word.fill(raw, fields, {log[0]['key']: [['Synthetic drug A', '5 mg', 'oral']]})
        self.assertEqual([c.text for c in Document(io.BytesIO(final)).tables[0].rows[1].cells],
                         ['Synthetic drug A', '5 mg', 'oral'])


def caption_over_blank(caption, style=None):
    doc = Document()
    doc.add_paragraph('Clinical summary: ________')
    doc.add_paragraph(caption, style=style) if style else doc.add_paragraph(caption)
    doc.add_paragraph()
    doc.add_paragraph('Plan: ____________')
    return data(doc)


class BelowCaptionReading(unittest.TestCase):
    """The blank below a printed caption keeps the engine's existing reading: ordinary answers stay writable and a
    source action keeps the guard's own review. A wording-based signing-caption hold was withdrawn after three
    refutation rounds (2026-10-05): every reader over- or under-held, and a hold could change the import route."""

    def below(self, raw):
        return [f for f in word.inspect(raw)['fields'] if f['locator']['slot'] == 'b/p[2]']

    def test_ordinary_date_captions_keep_their_writable_blank(self):
        for caption in ('Date of assessment:', 'Visit date:', 'Date of birth:', 'Date of procedure:',
                        'Date signed report received:', 'Date received signed report:',
                        'Date nurse received the signed report:', 'Review date:',
                        # A clinical 'signature', 'signs' or 'initial' is not a signing act (refutation 2026-10-05).
                        'Gene expression signature result date:', 'Date of vital signs:',
                        'Date of onset of signs and symptoms:', 'Troponin (initial) date:',
                        'Date of initial or repeat test:', 'Date of troponin (initial):',
                        'Signed copy given date:', 'Signed report received date:'):
            with self.subTest(caption):
                raw = caption_over_blank(caption)
                fields = word.inspect(raw)['fields']
                below = [f for f in fields if f['locator']['slot'] == 'b/p[2]']
                self.assertEqual([f.get('write_protected', False) for f in below], [False] * len(below))
                if below:
                    final = word.fill(raw, fields, {below[0]['key']: '14/03/2026'})
                    index = word.SlotIndex(word.open_package(final))
                    self.assertIn('14/03/2026', word.paragraph_text(index.by_id[BODY + 'b/p[2]'].el)[0])


    def test_the_source_action_guard_keeps_its_own_reading_and_review(self):
        # The hold runs after guard_source_actions: an action the guard reads keeps its coverage issue, so the
        # import still needs the clinician's exclusion review before generation (refutation 2026-10-05).
        for caption, code in (('Date of next review:', 'ambiguous_source_action'),
                              ('Date of approval:', 'ambiguous_source_action'),
                              ('Date of consent:', 'human_signing_action')):
            with self.subTest(caption):
                found = word.inspect(caption_over_blank(caption))
                below = [f for f in found['fields'] if f['locator']['slot'] == 'b/p[2]']
                self.assertEqual([bool(f.get('write_protected')) for f in below], [True])
                self.assertEqual([i['code'] for i in found['coverage_issues'] if i['slot'] == 'b/p[2]'], [code])


class DrawnBandRoute(unittest.TestCase):
    """A drawn band is v3-only knowledge: it keeps the import on v3 where e0 did (via its old inferred date)."""

    def form(self, *, band=True):
        doc = Document()
        doc.add_paragraph('Synthetic intake')
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = 'Patient name'
        table.cell(1, 0).text = 'Diagnosis'
        doc.add_paragraph('Please circle [yes/no] where the form asks.')
        if band:
            lines = doc.add_paragraph()
            lines._p.append(line_run(1, fallback=False))
            lines.add_run('\t\t')
            lines._p.append(line_run(2, fallback=False))
            doc.add_paragraph('Signature of Patient or Representative\t\t\tDate')
            doc.add_paragraph()
        doc.add_paragraph('End of form.')
        return data(doc)

    def test_band_keeps_the_reviewable_v3_route(self):
        import tempfile
        from pathlib import Path
        from django.test import override_settings
        from .service import inspect_template
        with tempfile.TemporaryDirectory() as tmp, override_settings(QUILLMD_WORD_AUTO_PREFER_V3=True):
            path = Path(tmp) / 'original.docx'
            path.write_bytes(self.form())
            result = inspect_template(path, engine='auto')
        coverage = result['import_manifest']['coverage']
        self.assertEqual(result['import_manifest']['engine'], 'v3')
        self.assertEqual(len(coverage['v3_only_signing_bands']), 2)
        self.assertTrue(coverage['selected_engine_issues'])
        self.assertFalse(coverage.get('advanced_unresolved_areas'))

    def test_without_a_band_the_route_rule_is_unchanged(self):
        from . import import_selection
        self.assertNotIn('protected_inline_signing_lines', json.dumps(word.inspect(self.form(band=False))['fields']))
        legacy = {'fields': [], 'warnings': []}
        self.assertEqual(import_selection.choose(legacy, {'fields': []}, [], None)[0], 'legacy')


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
