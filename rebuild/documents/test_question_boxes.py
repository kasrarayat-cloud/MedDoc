"""Synthetic structural controls for a printed question followed by a separate answer box."""
import io
import unittest
from zipfile import ZipFile

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
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
    def test_complete_long_question_and_section_are_retained(self):
        doc = Document()
        context = 'Clinical section ' + 'complete context ' * 25
        question = 'What changed? ' + 'Keep every qualifier. ' * 25
        doc.add_paragraph(context.strip(), style='Heading 1')
        doc.add_paragraph(question.strip())
        box(doc)
        result = w.inspect(data(doc))
        self.assertEqual(len(result['fields']), 1)
        self.assertEqual(result['fields'][0]['label'], question.strip())
        self.assertEqual(result['fields'][0]['context'], context.strip())

    def test_full_source_limits_keep_boundary_and_refuse_after_scope_expansion(self):
        for length in (1000, 1001):
            for what in ('label', 'context'):
                with self.subTest(length=length, what=what):
                    doc = Document()
                    context = 'C' * length if what == 'context' else 'Clinical history'
                    question = 'What ' + 'q' * (length - 6) + '?' if what == 'label' else 'What changed?'
                    doc.add_paragraph(context, style='Heading 1')
                    doc.add_paragraph(question)
                    box(doc)
                    result = w.inspect(data(doc))
                    if length == 1000:
                        self.assertEqual(len(result['fields']), 1)
                        self.assertEqual(result['fields'][0]['label'], question)
                        self.assertEqual(result['fields'][0]['context'], context)
                    else:
                        self.assertEqual(result['fields'], [])
                        self.assertTrue(any(question in n and 'limit' in n for n in result['notes']))
        doc = Document()
        long_context = 'Clinical ' + 'x' * 981
        doc.add_paragraph(long_context, style='Heading 1')
        for _ in range(2):
            doc.add_paragraph('What changed?')
            box(doc)
        result = w.inspect(data(doc))
        self.assertEqual(result['fields'], [])
        self.assertEqual(sum('nothing was shortened' in n for n in result['notes']), 2)

    def test_manual_derived_context_is_complete_or_visibly_refused(self):
        for length in (600, 1001):
            doc = Document()
            context = 'Clinical ' + 'c' * (length - 9)
            doc.add_paragraph(context, style='Heading 1')
            box(doc)
            target = {'slot': 'word/document.xml#b/tbl[0]/tr[0]/tc[0]', 'kind': 'long_text', 'label': 'Comments'}
            with self.subTest(length=length):
                if length == 600:
                    self.assertEqual(w.locate(data(doc), [target])[0]['context'], context)
                else:
                    with self.assertRaises(w.V3Failure): w.locate(data(doc), [target])

    def test_manual_root_verified_long_donor_scope_is_not_lost(self):
        doc = Document()
        context = 'Clinical section ' + 'continued ' * 16 + 'DONOR ONLY'
        doc.add_paragraph(context, style='Heading 1')
        doc.add_paragraph('What medications are currently taken?')
        box(doc)
        target = {'slot': 'word/document.xml#b/tbl[0]/tr[0]/tc[0]', 'kind': 'long_text', 'label': 'Medications'}
        self.assertEqual(w.locate(data(doc), [target])[0]['context'], context)

    def test_manual_long_metadata_never_slices_and_oversize_refuses(self):
        doc = Document()
        box(doc)
        source = data(doc)
        target = {'slot': 'word/document.xml#b/tbl[0]/tr[0]/tc[0]',
                  'kind': 'long_text', 'label': 'Question ' + 'q' * 491,
                  'context': 'Section ' + 'c' * 592}
        field = w.locate(source, [target])[0]
        self.assertEqual(field['label'], target['label'])
        self.assertEqual(field['context'], target['context'])
        for name in ('label', 'context'):
            with self.subTest(name=name), self.assertRaises(w.V3Failure):
                w.locate(source, [{**target, name: 'x' * 1001}])

    def test_initial_report_adjective_is_not_a_signing_instruction(self):
        for phrase, accepted in (
            ('Please describe the changes since the initial report?', True),
            ('Please describe changes in the case of the initial report?', True),
            ('Please notarize the initial report?', False),
            ('Please describe the changes since the initial report, then initial here?', False),
            ('Please describe the initial report and provide initials?', False),
            ('Please describe the initial report and provide signature?', False),
            ('Please provide Initial?', False), ('Please provide Initials?', False),
            ('Please sign the initial report here?', False),
            ('Please countersign the initial report?', False),
            ('Please counter-sign the initial report?', False),
            ('Has the initial report been countersigned?', False),
            ('Please undersign the initial report?', False),
            ('Please co-sign the initial report?', False),
            ('Please re-sign the initial report?', False),
            ('Please provide signoff on the initial report?', False),
            ('Please describe signing the initial report?', False),
            ('Please countersign since the initial report?', False),
            ('Please initial the report here?', False), ('Please initial here?', False)):
            with self.subTest(phrase=phrase):
                doc = Document()
                doc.add_paragraph(phrase)
                box(doc)
                result = w.inspect(data(doc))
                fields = [f for f in result['fields'] if f['locator']['target']['type'] == 'cell']
                self.assertEqual(len(fields), int(accepted))
                if accepted:
                    self.assertEqual(fields[0]['label'], phrase)
                    exported = w.fill(data(doc), fields, {fields[0]['key']: 'SYNTHETIC'})
                    self.assertEqual(w.text_of(w.SlotIndex(w.open_package(exported)).by_id['word/document.xml#b/tbl[0]/tr[0]/tc[0]'].el), 'SYNTHETIC')

    def test_initial_adjective_cannot_cross_question_section_boundary(self):
        for heading, question in (('Report', 'Please provide the initial'),
                                  ('Initial', 'Please describe the initial report?'),
                                  ('Please countersign the initial report', 'What changed?')):
            with self.subTest(heading=heading, question=question):
                doc = Document()
                doc.add_paragraph(heading, style='Heading 1')
                doc.add_paragraph(question)
                box(doc)
                result = w.inspect(data(doc))
                self.assertEqual(result['fields'], [])
                self.assertTrue(any('Signing or consent' in note for note in result['notes']))

    def test_inherited_heading_scope_and_unknown_or_cyclic_ancestry(self):
        for ancestor in ('Heading 1', 'Unknown', 'cycle'):
            with self.subTest(ancestor=ancestor):
                doc = Document()
                style = doc.styles.add_style('Donor Section', WD_STYLE_TYPE.PARAGRAPH)
                style.base_style = doc.styles['Heading 1']
                if ancestor != 'Heading 1':
                    style.element.find(qn('w:basedOn')).set(qn('w:val'), 'DonorSection' if ancestor == 'cycle' else ancestor)
                doc.add_paragraph('Donor', style)
                doc.add_paragraph('What medications are currently taken?')
                box(doc)
                result = w.inspect(data(doc))
                if ancestor == 'Heading 1':
                    self.assertEqual(result['fields'][0]['context'], 'Donor')
                else:
                    self.assertEqual(result['fields'], [])
                    self.assertTrue(any('style ancestry' in note for note in result['notes']))

    def test_multi_paragraph_question_keeps_both_sources_in_review(self):
        for blanks in (0, 1, 2):
            with self.subTest(blanks=blanks):
                doc = Document()
                first = 'Which medications are currently taken?'
                last = 'Please provide their doses and frequencies.'
                doc.add_paragraph(first)
                for _ in range(blanks):
                    doc.add_paragraph()
                doc.add_paragraph(last)
                box(doc)
                result = w.inspect(data(doc))
                self.assertEqual(result['fields'], [])
                self.assertTrue(any(first in note and last in note for note in result['notes']))

    def test_page_break_before_spacer_is_not_plain_empty_space(self):
        for inherited in (False, True):
            with self.subTest(inherited=inherited):
                doc = Document()
                doc.add_paragraph('What symptoms changed?')
                p = doc.add_paragraph()
                if inherited:
                    style = doc.styles.add_style('New page', WD_STYLE_TYPE.PARAGRAPH)
                    style.paragraph_format.page_break_before = True
                    p.style = style
                else:
                    p.paragraph_format.page_break_before = True
                box(doc)
                result = w.inspect(data(doc))
                self.assertEqual(result['fields'], [])
                self.assertTrue(any('page break' in note for note in result['notes']))

    def test_conditional_border_in_ancestor_style_is_not_claimed_as_explicit(self):
        doc = Document()
        doc.add_paragraph('What symptoms changed?')
        table = box(doc, bordered=False)
        parent = doc.styles.add_style('Base Box', WD_STYLE_TYPE.TABLE)
        conditional = OxmlElement('w:tblStylePr')
        conditional.set(qn('w:type'), 'firstRow')
        parent.element.append(conditional)
        child = doc.styles.add_style('Child Box', WD_STYLE_TYPE.TABLE)
        child.base_style = parent
        props = OxmlElement('w:tblPr')
        borders = OxmlElement('w:tblBorders')
        for side in ('top', 'left', 'bottom', 'right'):
            edge = OxmlElement('w:' + side)
            edge.set(qn('w:val'), 'single')
            borders.append(edge)
        props.append(borders)
        child.element.append(props)
        table.style = child
        result = w.inspect(data(doc))
        self.assertEqual(result['fields'], [])
        self.assertTrue(any('border' in note for note in result['notes']))

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
                            'long': 'What happened? ' + 'Keep every qualifier. ' * 50}.get(case, 'What changed?')
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
