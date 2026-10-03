"""Source ownership controls; synthetic documents are not corpus qualification."""
import copy
import io
import unittest

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE

from . import word_v3 as w
from .test_question_boxes import box, data


def link(paragraph, text='Published guidance', address='https://example.test/guidance'):
    node = OxmlElement('w:hyperlink')
    node.set(qn('r:id'), paragraph.part.relate_to(address, RELATIONSHIP_TYPE.HYPERLINK, is_external=True))
    run = OxmlElement('w:r'); value = OxmlElement('w:t'); value.text = text
    run.append(value); node.append(run); paragraph._p.append(node)


def numbered(doc, values, kind='bullet'):
    abstract = OxmlElement('w:abstractNum'); abstract.set(qn('w:abstractNumId'), '90')
    level = OxmlElement('w:lvl'); level.set(qn('w:ilvl'), '0')
    fmt = OxmlElement('w:numFmt'); fmt.set(qn('w:val'), kind)
    level.append(fmt); abstract.append(level); doc.part.numbering_part.element.append(abstract)
    number = OxmlElement('w:num'); number.set(qn('w:numId'), '10')
    ref = OxmlElement('w:abstractNumId'); ref.set(qn('w:val'), '90'); number.append(ref)
    doc.part.numbering_part.element.append(number)
    for value in values:
        p = doc.add_paragraph(value)
        props = OxmlElement('w:numPr'); num = OxmlElement('w:numId'); num.set(qn('w:val'), '10')
        props.append(num); p._p.get_or_add_pPr().append(props)


class DocumentRelations(unittest.TestCase):
    def test_heading_with_own_digit_destinations_cannot_claim_following_spacers(self):
        doc = Document(); cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        p = cell.paragraphs[0]; p.style = 'Heading 3'
        for label in ('Waist Circumference: ', 'in.  Hip Circumference: '):
            p.add_run(label)
            for _ in range(3):
                run = p.add_run(); symbol = OxmlElement('w:sym')
                symbol.set(qn('w:font'), 'Symbol'); symbol.set(qn('w:char'), 'F0F0')
                run._r.append(symbol)
        p.add_run('in.'); cell.add_paragraph(); cell.add_paragraph()
        raw = data(doc); info = w.inspect(raw); fields = info['fields']
        self.assertEqual([f['label'] for f in fields], ['Waist Circumference', 'Hip Circumference'])
        self.assertTrue(all(f['locator']['slot'] == 'b/tbl[0]/tr[0]/tc[0]/p[0]' for f in fields))
        self.assertEqual([(f['locator']['target']['start'], f['locator']['target']['end']) for f in fields], [(21, 24), (48, 51)])
        out = Document(io.BytesIO(w.fill(raw, fields, {fields[0]['key']: '032', fields[1]['key']: '040'})))
        self.assertEqual(out.tables[0].cell(0, 0).paragraphs[0].text, 'Waist Circumference: 032in.  Hip Circumference: 040in.')
        self.assertTrue(all(not p.text for p in out.tables[0].cell(0, 0).paragraphs[1:]))
        self.assertEqual(w.fill(raw, fields, {}), raw)

    def test_all_recognized_inline_blanks_keep_their_own_heading_destination(self):
        for placeholder in ('|__|__|__|', '{{Findings}}', '[Describe findings]'):
            with self.subTest(placeholder=placeholder):
                doc = Document(); cell = doc.add_table(rows=1, cols=1).cell(0, 0)
                p = cell.paragraphs[0]; p.style = 'Heading 3'; p.text = 'Findings: ' + placeholder
                cell.add_paragraph(); cell.add_paragraph(); raw = data(doc); fields = w.inspect(raw)['fields']
                self.assertEqual(len(fields), 1)
                self.assertEqual(fields[0]['locator']['slot'], 'b/tbl[0]/tr[0]/tc[0]/p[0]')
                self.assertEqual(fields[0]['locator']['target']['type'], 'span')
        # An unfilled underline uses the same precise blank reader. A plain
        # label without its own blank still owns its directly following box.
        for underline in (True, False):
            doc = Document(); cell = doc.add_table(rows=1, cols=1).cell(0, 0)
            p = cell.paragraphs[0]; p.style = 'Heading 3'; p.text = 'Findings:'
            if underline: p.add_run('   ').underline = True
            cell.add_paragraph(); cell.add_paragraph(); fields = w.inspect(data(doc))['fields']
            self.assertEqual(len(fields), 1)
            self.assertEqual(fields[0]['locator']['slot'], 'b/tbl[0]/tr[0]/tc[0]/p[' + ('0' if underline else '1') + ']')

    def test_previous_question_has_complete_local_source(self):
        doc = Document(); doc.add_heading('Relationships', 1)
        first = 'How is the reporting condition monitored outside self-report?'
        follow = 'In relation to the above question, what did the patient say?'
        doc.add_paragraph(first); box(doc); doc.add_paragraph(follow); box(doc)
        fields = w.inspect(data(doc))['fields']
        answer = next(f for f in fields if f['label'] == follow)
        self.assertIn(first, answer['context'])
        self.assertIn('Relationships', answer['context'])
        self.assertEqual(answer['locator']['slot'], 'b/tbl[1]/tr[0]/tc[0]')
        self.assertEqual(answer['source_questions'][0]['question'], first)
        source = data(doc)
        w.fill(source, fields, {answer['key']: 'Synthetic response.'})
        doc.paragraphs[1].text = 'A different clinical question?'
        with self.assertRaises(w.V3Failure) as failure:
            w.fill(data(doc), fields, {answer['key']: 'Synthetic response.'})
        self.assertEqual(failure.exception.code, 'mapping_mismatch')

    def test_reference_does_not_cross_boundaries_or_borrow_an_answer(self):
        for boundary in ('heading', 'intervening', 'unsigned', 'answer', 'following', 'unmapped'):
            with self.subTest(boundary=boundary):
                doc = Document(); doc.add_heading('History', 1)
                doc.add_paragraph('Please provide the signature?' if boundary == 'unsigned' else 'What changed?')
                box(doc, bordered=boundary != 'unmapped')
                if boundary == 'heading': doc.add_heading('Plan', 1)
                if boundary == 'intervening': doc.add_paragraph('Printed intervening instruction.')
                reference = {'answer': 'above answer', 'following': 'following question'}.get(boundary, 'above question')
                doc.add_paragraph('In relation to the ' + reference + ', what happened?'); box(doc)
                fields = w.inspect(data(doc))['fields']
                self.assertFalse([f for f in fields if f['locator']['slot'] == 'b/tbl[1]/tr[0]/tc[0]'])

    def test_fixed_link_introductions_are_not_answer_fields(self):
        for introduction in ('For questions please contact:', 'Please refer to the application forms at:'):
            with self.subTest(introduction=introduction):
                doc = Document(); doc.add_paragraph(introduction); doc.add_paragraph(); link(doc.add_paragraph())
                doc.add_paragraph('Patient contact: __________')
                original = data(doc); fields = w.inspect(original)['fields']
                self.assertEqual([f['label'] for f in fields], ['Patient contact'])
                exported = w.fill(original, fields, {fields[0]['key']: 'Synthetic person'})
                self.assertIn(b'https://example.test/guidance', w.Package(exported).zip.read('word/_rels/document.xml.rels'))

    def test_conditional_guidance_list_is_not_a_choice(self):
        doc = Document(); doc.add_paragraph('If you need any of the following:')
        numbered(doc, ('Change of conditions', 'Request supporting evidence'), 'lowerLetter')
        doc.add_paragraph('Then please refer to the guidance at:'); link(doc.add_paragraph())
        self.assertEqual(w.inspect(data(doc))['fields'], [])

    def test_section_heading_does_not_add_a_phantom_answer(self):
        doc = Document(); doc.add_heading('Annex: Patient comments:', 1)
        doc.add_paragraph('What would you like recorded?'); box(doc)
        self.assertEqual([f['label'] for f in w.inspect(data(doc))['fields']], ['What would you like recorded?'])

    def test_heading_with_an_explicit_blank_still_has_an_answer(self):
        doc = Document(); doc.add_heading('Patient name: __________', 1)
        self.assertEqual([f['label'] for f in w.inspect(data(doc))['fields']], ['Patient name'])

    def test_list_box_has_full_question_without_guessing_list_cardinality(self):
        doc = Document(); doc.add_heading('Accommodation', 1)
        doc.add_paragraph('What type of residence does the patient occupy:')
        numbered(doc, ('Own home', 'With family', 'Other (please specify)'))
        for _ in range(3): doc.add_paragraph()
        box(doc)
        fields = w.inspect(data(doc))['fields']
        field = next(f for f in fields if f['locator']['target']['type'] == 'cell')
        self.assertEqual(field['label'], 'What type of residence does the patient occupy:')
        self.assertIn('What type of residence does the patient occupy:', field['context'])
        self.assertIn('Own home | With family | Other (please specify)', field['context'])
        for answer in ('', 'Synthetic supported residence.', 'Synthetic long response. ' * 100):
            filled = w.fill(data(doc), fields, {field['key']: answer})
            self.assertEqual(Document(__import__('io').BytesIO(filled)).tables[0].cell(0, 0).text, answer)

    def test_other_box_does_not_cross_an_intervening_boundary(self):
        for boundary in ('heading', 'table', 'question', 'consent'):
            with self.subTest(boundary=boundary):
                doc = Document(); doc.add_paragraph('Consent choices:' if boundary == 'consent' else 'Residence types:')
                numbered(doc, ('Own home', 'Other (please specify)'))
                if boundary == 'heading': doc.add_heading('Unrelated', 1)
                elif boundary == 'table': doc.add_table(rows=1, cols=2)
                elif boundary == 'question': doc.add_paragraph('New unrelated instruction.')
                table = box(doc); result = w.inspect(data(doc))
                cells = [f for f in result['fields'] if f['locator']['target']['type'] == 'cell']
                self.assertFalse([f for f in cells if f['label'].lower().startswith('other')])

    def test_third_party_author_area_is_visible_and_cannot_be_forged_writable(self):
        doc = Document(); doc.add_heading('Manager comments', 1)
        statement = 'This section is for the line manager of the clinician to add any comments or concerns.'
        doc.add_paragraph(statement); box(doc)
        original = data(doc); fields = w.inspect(original)['fields']
        self.assertEqual(len(fields), 1)
        field = fields[0]; self.assertTrue(field['write_protected'])
        self.assertEqual(field['label'], statement)
        field.pop('write_protected'); field.pop('review_reason')
        with self.assertRaises(w.V3Failure) as failure:
            w.fill(original, fields, {field['key']: 'The manager agrees.'})
        self.assertEqual(failure.exception.code, 'protected_signing_area')

    def test_explicit_conditional_selection_keeps_its_choices_beside_help(self):
        for verb in ('select', 'choose', 'check', 'tick', 'mark', 'circle', 'indicate'):
            with self.subTest(verb=verb):
                doc = Document(); doc.add_paragraph('If pain is present, ' + verb + ' one severity:')
                numbered(doc, ('Mild', 'Severe'), 'lowerLetter')
                doc.add_paragraph('For help, please refer to the guidance at:'); link(doc.add_paragraph())
                fields = w.inspect(data(doc))['fields']
                self.assertEqual(len(fields), 1)
                self.assertEqual(fields[0]['options'], ['Mild', 'Severe'])

    def test_reference_rechecks_physical_destination_after_identical_box_insertion(self):
        doc = Document(); doc.add_heading('History', 1)
        doc.add_paragraph('What symptoms were observed?'); first = box(doc)
        follow = doc.add_paragraph('In relation to the above question, what did the patient say?'); box(doc)
        fields = w.inspect(data(doc))['fields']; field = next(f for f in fields if f.get('source_questions'))
        follow._p.addprevious(copy.deepcopy(first._tbl))
        with self.assertRaises(w.V3Failure) as failure:
            w.fill(data(doc), fields, {field['key']: 'Synthetic response.'})
        self.assertEqual(failure.exception.code, 'mapping_mismatch')

    def test_other_and_already_filled_author_boxes_remain_protected(self):
        for other in (False, True):
            for filled in (False, True):
                with self.subTest(other=other, filled=filled):
                    doc = Document(); doc.add_heading('Parent comments', 1)
                    doc.add_paragraph('This section is for the parent to provide comments:')
                    if other: numbered(doc, ('No comments', 'Other (please specify)'))
                    table = box(doc); fields = w.inspect(data(doc))['fields']
                    field = next(f for f in fields if f['locator']['target']['type'] == 'cell')
                    self.assertTrue(field['write_protected'])
                    if filled: table.cell(0, 0).text = 'Existing synthetic parent statement.'
                    original = data(doc); idx = w.SlotIndex(w.open_package(original))
                    slot = idx.by_id[field['locator']['part'] + '#' + field['locator']['slot']]
                    field.pop('write_protected'); field.pop('review_reason')
                    field['locator']['fingerprint'] = w.fingerprint(slot.el)
                    field['locator']['target'] = {'type': 'cell_replace', 'all': True}
                    with self.assertRaises(w.V3Failure) as failure:
                        w.fill(original, fields, {field['key']: 'Invented parent statement.'})
                    self.assertEqual(failure.exception.code, 'protected_signing_area')
