"""Synthetic structural controls for a printed question followed by a separate answer box."""
import io
import unittest
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from . import word_v3 as w


def box(doc, *, bordered=True):
    table = doc.add_table(rows=1, cols=1)
    if bordered:
        borders = OxmlElement('w:tcBorders')
        for side in ('top', 'left', 'bottom', 'right'):
            edge = OxmlElement('w:' + side)
            edge.set(qn('w:val'), 'single')
            borders.append(edge)
        table.cell(0, 0)._tc.get_or_add_tcPr().append(borders)
    return table


def data(doc):
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


class QuestionBoxes(unittest.TestCase):
    def test_question_with_its_own_inline_answer_does_not_lose_that_field(self):
        doc = Document()
        doc.add_paragraph('Patient name: __________. What symptoms changed?')
        box(doc)
        result = w.inspect(data(doc))
        self.assertEqual([(f['label'], f['locator']['target']['type']) for f in result['fields']],
                         [('Patient name', 'span')])
        self.assertTrue(any('another answer area' in note for note in result['notes']))

    def test_explicit_style_borders_and_cell_nil_override(self):
        for nil in (False, True):
            with self.subTest(nil=nil):
                doc = Document()
                doc.add_paragraph('What changed?')
                table = box(doc, bordered=False)
                table.style = 'Table Grid'
                if nil:
                    borders = OxmlElement('w:tcBorders')
                    edge = OxmlElement('w:left')
                    edge.set(qn('w:val'), 'nil')
                    borders.append(edge)
                    table.cell(0, 0)._tc.get_or_add_tcPr().append(borders)
                result = w.inspect(data(doc))
                self.assertEqual(len(result['fields']), 0 if nil else 1)
                self.assertEqual(bool(result['notes']), nil)

    def test_adjacent_and_spaced_questions_use_the_box_with_complete_scope(self):
        for spaces in (0, 1, 2):
            with self.subTest(spaces=spaces):
                doc = Document()
                for text in ('Part B', 'Social Supervisor Report', 'Supervision'):
                    doc.add_paragraph().add_run(text).bold = True
                question = 'When did you last see the patient? Give the date and location.'
                doc.add_paragraph(question)
                for _ in range(spaces):
                    doc.add_paragraph()
                box(doc)
                fields = w.inspect(data(doc))['fields']
                self.assertEqual(len(fields), 1)
                field = fields[0]
                self.assertEqual(field['label'], question)
                self.assertEqual(field['context'], 'Part B > Social Supervisor Report > Supervision')
                self.assertEqual(field['kind'], 'long_text')
                self.assertEqual(field['locator']['slot'], 'b/tbl[0]/tr[0]/tc[0]')

    def test_ambiguous_boxes_have_a_visible_source_location(self):
        cases = ('heading', 'option', 'signature', 'reference', 'long', 'intervening', 'three-spaces',
                 'section-break', 'unbordered')
        for case in cases:
            with self.subTest(case=case):
                doc = Document()
                question = {'heading': 'Clinical history', 'option': 'Other (please specify)',
                            'signature': 'Please provide the clinician signature.',
                            'reference': 'In relation to the above question, what changed?',
                            'long': 'What happened? ' + 'Keep every qualifier. ' * 20}.get(case, 'What changed?')
                p = doc.add_paragraph(question)
                if case == 'option':
                    p.style = 'List Bullet'
                if case == 'intervening':
                    doc.add_table(rows=1, cols=2)
                if case == 'three-spaces':
                    for _ in range(3):
                        doc.add_paragraph()
                if case == 'section-break':
                    p._p.get_or_add_pPr().append(OxmlElement('w:sectPr'))
                target = box(doc, bordered=case != 'unbordered')
                result = w.inspect(data(doc))
                self.assertFalse([f for f in result['fields'] if f['locator']['slot'].endswith('/tc[0]')])
                self.assertTrue(any('Unassigned answer box' in x and 'word/document.xml#b/tbl[' in x
                                    for x in result['notes']), result)
                if case == 'long':
                    self.assertTrue(any(question.strip() in x for x in result['notes']))

    def test_empty_ordinary_long_preserve_other_document_parts_and_neighbours(self):
        doc = Document()
        doc.sections[0].header.paragraphs[0].text = 'Synthetic clinical branding'
        doc.add_paragraph('What symptoms changed?')
        box(doc)
        doc.add_paragraph('Printed consent and signature area — leave unchanged')
        original = data(doc)
        fields = w.inspect(original)['fields']
        field = next(f for f in fields if f['label'] == 'What symptoms changed?')
        for answer in ('', 'SYNTHETIC symptoms improved.', 'SYNTHETIC long answer. ' * 150):
            with self.subTest(length=len(answer)):
                output = w.fill(original, fields, {field['key']: answer})
                with ZipFile(io.BytesIO(original)) as before, ZipFile(io.BytesIO(output)) as after:
                    self.assertEqual(before.namelist(), after.namelist())
                    for part in before.namelist():
                        if part != 'word/document.xml':
                            self.assertEqual(before.read(part), after.read(part))
                    old = etree.fromstring(before.read('word/document.xml')).find(w.q('w:body'))
                    new = etree.fromstring(after.read('word/document.xml')).find(w.q('w:body'))
                    self.assertEqual(etree.tostring(old[0]), etree.tostring(new[0]))
                    self.assertEqual(etree.tostring(old[2]), etree.tostring(new[2]))
                    self.assertEqual(w.text_of(new[1]).strip(), answer.strip())

    def test_part_change_keeps_distinct_supervisors_and_does_not_reuse_a_question(self):
        doc = Document()
        for part, role in (('Part B', 'Social Supervisor'), ('Part C', 'Clinical Supervisor')):
            for text in (part, role, 'Supervision'):
                doc.add_paragraph().add_run(text).bold = True
            doc.add_paragraph('When did you last see the patient?')
            box(doc)
            box(doc)
        result = w.inspect(data(doc))
        fields = [f for f in result['fields'] if f['locator']['target']['type'] == 'cell']
        self.assertEqual(len(fields), 2)
        self.assertIn('Part B > Social Supervisor > Supervision', fields[0]['context'])
        self.assertIn('Part C > Clinical Supervisor > Supervision', fields[1]['context'])
        self.assertEqual(len([n for n in result['notes'] if 'Unassigned answer box' in n]), 2)
