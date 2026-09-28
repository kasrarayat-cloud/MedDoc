"""Printed instructions remain evidence when an answer is entered beside a question."""
import copy
import json
import tempfile
from pathlib import Path
import unittest

from docx import Document
from docx.shared import RGBColor
from lxml import etree

from . import word_v3 as w
from .test_question_boxes import data


def form():
    doc = Document(); table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = 'What information has the patient reviewed?'
    for index, text in enumerate(('Do not share third-party information with the patient.',
                                   'The patient must have an opportunity to add comments.')):
        p = table.cell(0, 1).paragraphs[0] if index == 0 else table.cell(0, 1).add_paragraph()
        p.add_run(text).font.color.rgb = RGBColor.from_string('808080')
    return data(doc)


class GuidancePreservation(unittest.TestCase):
    def test_repeated_header_instructions_all_reach_the_mapping(self):
        from docx.shared import Inches
        doc = Document(); doc.settings.odd_and_even_pages_header_footer = True
        instructions = ['Do not disclose information about the mother.',
                        'Do not disclose information about the father.']
        for header, text in zip((doc.sections[0].header, doc.sections[0].even_page_header), instructions):
            table = header.add_table(rows=1, cols=2, width=Inches(6))
            table.cell(0, 0).text = 'What progress have you made?'
            table.cell(0, 1).paragraphs[0].add_run(text).font.color.rgb = RGBColor.from_string('808080')
        original = data(doc); fields = w.inspect(original)['fields']
        self.assertEqual(len(fields), 1)
        self.assertEqual([item['text'] for item in fields[0]['source_instructions']], instructions)
        changed = copy.deepcopy(fields); changed[0]['source_instructions'].pop()
        with self.assertRaises(w.V3Failure): w.fill(original, changed, {changed[0]['key']: 'A complete observation.'})

    def test_equal_header_labels_with_different_subjects_are_separate_answers(self):
        from docx.shared import Inches
        doc = Document(); doc.settings.odd_and_even_pages_header_footer = True
        for header, role in zip((doc.sections[0].header, doc.sections[0].even_page_header), ('Donor', 'Recipient')):
            header.paragraphs[0].text = role; header.paragraphs[0].style = 'Heading 1'
            table = header.add_table(rows=1, cols=2, width=Inches(6))
            table.cell(0, 0).text = 'Name'
            table.cell(0, 1).paragraphs[0].add_run('Enter the full name.').font.color.rgb = RGBColor.from_string('808080')
        original = data(doc); fields = w.inspect(original)['fields']
        self.assertEqual(len(fields), 2)
        self.assertEqual(len({field['context'] for field in fields}), 2)
        target = next(f for f in fields if 'Donor' in f['context'])
        final = w.fill(original, fields, {target['key']: 'SYNTHETIC DONOR'})
        before = w.open_package(original); after = w.open_package(final)
        self.assertEqual(before.zip.read('word/header2.xml'), after.zip.read('word/header2.xml'))

    def test_new_mapping_preserves_all_instruction_paragraphs_and_appends_full_answer(self):
        original = form(); fields = w.inspect(original)['fields']; field = fields[0]
        self.assertEqual(field['locator']['target']['type'], 'cell_append')
        self.assertEqual(len(field['source_instructions']), 1)
        self.assertIn('Do not share third-party information', field['source_instructions'][0]['text'])
        for answer in ('The patient reviewed the report.', ('A complete reviewed sentence. ' * 150).strip()):
            with self.subTest(long=len(answer) > 100):
                result = w.fill(original, fields, {field['key']: answer})
                before = w.SlotIndex(w.open_package(original)).by_id['word/document.xml#b/tbl[0]/tr[0]/tc[1]'].el
                after = w.SlotIndex(w.open_package(result)).by_id['word/document.xml#b/tbl[0]/tr[0]/tc[1]'].el
                self.assertEqual([etree.tostring(p) for p in before.findall(w.q('w:p'))],
                                 [etree.tostring(p) for p in after.findall(w.q('w:p'))][:-1])
                self.assertEqual(w.text_of(after.findall(w.q('w:p'))[-1]), answer)
                self.assertIsNone(w.effective_values(original, fields, {field['key']: answer})[field['key']])

    def test_old_whole_cell_mapping_is_not_rewritten_and_cannot_delete_printed_guidance(self):
        original = form(); fields = w.inspect(original)['fields']
        fields[0]['locator']['target'] = {'type': 'cell_replace', 'all': True}
        fields[0].pop('source_instructions', None)
        old = copy.deepcopy(fields); answer = 'The patient reviewed the report.'
        result = w.fill(original, fields, {fields[0]['key']: answer})
        text = w.text_of(w.SlotIndex(w.open_package(result)).by_id['word/document.xml#b/tbl[0]/tr[0]/tc[1]'].el)
        self.assertIn('Do not share third-party information with the patient.', text)
        self.assertIn(answer, text)
        self.assertEqual(fields, old)
        self.assertIsNone(w.effective_values(original, fields, {fields[0]['key']: answer})[fields[0]['key']])

    def test_instruction_identity_is_checked_and_unwritten_constrained_state_is_unknown(self):
        original = form(); fields = w.inspect(original)['fields']; key = fields[0]['key']
        self.assertIsNone(w.effective_values(original, fields, {})[key])
        fields[0]['source_instructions'][0]['text'] = 'The patient has already consented.'
        with self.assertRaises(w.V3Failure) as failure:
            w.fill(original, fields, {key: 'The patient reviewed the report.'})
        self.assertEqual(failure.exception.code, 'mapping_mismatch')

    def test_preserved_coloured_values_are_not_erased_from_constrained_state(self):
        for color in ('808080', '0000FF'):
            for option in (False, True):
                doc = Document(); table = doc.add_table(rows=2 if option else 1, cols=2)
                if option:
                    table.cell(0, 0).text = 'Question'; table.cell(0, 1).text = 'Yes / No'
                row = 1 if option else 0
                table.cell(row, 0).text = 'Do you smoke?' if option else 'Priority'
                table.cell(row, 1).paragraphs[0].add_run('Yes' if option else '1').font.color.rgb = RGBColor.from_string(color)
                original = data(doc); inspected = w.inspect(original)['fields']
                self.assertEqual(len(inspected), 1)
                for legacy in (False, True):
                    with self.subTest(color=color, option=option, legacy=legacy):
                        fields = copy.deepcopy(inspected); field = fields[0]
                        if legacy:
                            field['locator']['target'].update(type='cell_replace', all=True)
                            field.pop('source_instructions')
                        expected = [None, None] if option else None
                        for answers in ({}, {field['key']: 'No' if option else '2'}):
                            self.assertEqual(w.effective_values(original, fields, answers)[field['key']], expected)
                        output = w.fill(original, fields, {field['key']: 'No' if option else '2'})
                        cell = w.SlotIndex(w.open_package(output)).by_id['word/document.xml#b/tbl[0]/tr[%d]/tc[1]' % row].el
                        self.assertEqual([w.text_of(p) for p in cell.findall(w.q('w:p'))], ['Yes', 'No'] if option else ['1', '2'])

    def test_complete_instruction_bound_survives_sandbox_json_and_export(self):
        from documents import inspect_template, fill_template, DocumentError
        text = 'Preserved guidance: ' + 'x' * (w.MAX_SOURCE_INSTRUCTION_CHARS - len('Preserved guidance: ') - 1) + 'Ω'
        doc = Document(); table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = 'What observations were made?'
        table.cell(0, 1).paragraphs[0].add_run(text).font.color.rgb = RGBColor.from_string('808080')
        original = data(doc)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'original.docx'; path.write_bytes(original)
            mapped = inspect_template(path, engine='v3')
            fields = json.loads(json.dumps(mapped['fields']))
            self.assertEqual(fields[0]['source_instructions'][0]['text'], text)
            self.assertEqual(len(text), 20000)
            export = Path(directory) / 'export.docx'; answer = 'The observed finding is recorded in full.'
            fill_template(path, fields, {fields[0]['key']: answer}, export)
            cell = w.SlotIndex(w.open_package(export.read_bytes())).by_id['word/document.xml#b/tbl[0]/tr[0]/tc[1]'].el
            self.assertEqual([w.text_of(p) for p in cell.findall(w.q('w:p'))], [text, answer])
            color = cell.findall(w.q('w:p'))[-1].find('.//' + w.q('w:color'))
            self.assertEqual(color.get(w.q('w:val')), '000000')
            self.assertEqual(path.read_bytes(), original)
            table.cell(0, 1).paragraphs[0].runs[0].text += 'x'
            path.write_bytes(data(doc))
            with self.assertRaises(DocumentError) as failure:
                inspect_template(path, engine='v3')
            self.assertEqual(failure.exception.code, 'mapping_limit')

    def test_missing_or_changed_instruction_anchor_refuses_export(self):
        original = form(); first = w.inspect(original)['fields']
        for mutate in (lambda f: f.pop('source_instructions'),
                       lambda f: f['source_instructions'][0].update(slot='b/p[0]'),
                       lambda f: f['source_instructions'][0].update(fingerprint='f' * 64)):
            fields = copy.deepcopy(first); mutate(fields[0])
            with self.assertRaises(w.V3Failure) as failure:
                w.fill(original, fields, {fields[0]['key']: 'A complete observation.'})
            self.assertEqual(failure.exception.code, 'mapping_mismatch')
