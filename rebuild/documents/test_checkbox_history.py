"""Bounded native-checkbox event lists; synthetic examples are not corpus qualification."""
import copy
import io
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from lxml import etree

from . import word_v3 as w
from .test_question_boxes import data
from .test_word_v3 import checkbox_control, ff_field, _sdt


def form(question='Treatments received', options=('Physiotherapy', 'Occupational therapy', 'Hydrotherapy'),
         *, control='ff', instruction='', heading='Clinical history', separate=False):
    doc = Document(); doc.add_heading(heading, 1)
    if instruction: doc.add_paragraph(instruction)
    if separate: doc.add_paragraph(question + ':')
    for i, option in enumerate(options):
        p = doc.add_paragraph(question + ': ' if i == 0 and not separate else '')
        if control == 'ff': ff_field(p, 'checkbox', name='Answer' + str(i))
        elif control == 'sdt': p._p.append(checkbox_control())
        else: p.add_run('☐')
        p.add_run(' ' + option)
    return doc


def rewrite(raw, old, new):
    out = io.BytesIO()
    with ZipFile(io.BytesIO(raw)) as a, ZipFile(out, 'w', ZIP_DEFLATED) as b:
        for name in a.namelist():
            value = a.read(name)
            b.writestr(name, value.replace(old.encode(), new.encode()) if name == 'word/document.xml' else value)
    return out.getvalue()


class CheckboxHistory(unittest.TestCase):
    def field(self, raw):
        fields = [f for f in w.inspect(raw)['fields'] if f['locator']['target']['type'] == 'checkboxes']
        self.assertEqual(len(fields), 1)
        return fields[0]

    def test_distinct_treatment_and_course_histories_select_multiple_native_controls(self):
        for question, options in (
                ('Treatments received', ('Physiotherapy', 'Occupational therapy', 'Hydrotherapy')),
                ('Courses attended', ('First aid', 'Food hygiene', 'Literacy'))):
            for control in ('ff', 'sdt'):
                with self.subTest(question=question, control=control):
                    raw = data(form(question, options, control=control)); field = self.field(raw)
                    self.assertEqual(field['kind'], 'multi_choice')
                    self.assertEqual(field['options'], list(options))
                    original = copy.deepcopy(field)
                    for chosen in ([], [options[1]], [options[0], options[2]]):
                        output = w.fill(raw, [field], {field['key']: chosen})
                        index = w.SlotIndex(w.open_package(output))
                        self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']],
                                         [o in chosen for o in options])
                        before = w.SlotIndex(w.open_package(raw))
                        for box in field['locator']['target']['boxes']:
                            ident = box['part'] + '#' + box['slot']
                            node = index.by_id[ident].el
                            node.getparent().replace(node, copy.deepcopy(before.by_id[ident].el))
                        self.assertEqual(etree.tostring(before.package.tree('word/document.xml')),
                                         etree.tostring(index.package.tree('word/document.xml')))
                    self.assertEqual(field, original)

    def test_separate_complete_owner_and_local_instruction_are_bound(self):
        raw = data(form(separate=True, instruction='Record events during the reporting period.'))
        field = self.field(raw)
        self.assertEqual(field['kind'], 'multi_choice')
        self.assertIn('Record events during the reporting period.', field['context'])
        self.assertEqual(field['source_questions'][0]['question'], 'Treatments received')
        self.assertGreaterEqual(len(field['source_questions'][0]['sources']), 5)

    def test_explicit_exclusive_binary_and_single_event_scopes_keep_one_choice(self):
        for args in (
                {'instruction': 'Tick one.'}, {'heading': 'Select one'},
                {'question': 'Most recent treatment received'}, {'question': 'Current treatment received'},
                {'question': 'Single treatment received'}, {'question': 'Latest treatment received'},
                {'options': ('Yes', 'No')}, {'options': ('Mild', 'Moderate', 'Severe')},
                {'options': ('Physiotherapy', 'Yes', 'No')},
                {'options': ('Physiotherapy', 'None')}):
            with self.subTest(args=args):
                raw = data(form(**args)); field = self.field(raw)
                self.assertEqual(field['kind'], 'choice')
                with self.assertRaises(w.V3Failure):
                    w.fill(raw, [field], {field['key']: field['options'][:2]})

    def test_conflicting_or_unrepresented_limits_do_not_authorize_history_selections(self):
        for instruction in ('Select up to two.', 'Choose one. Tick all that apply.', 'At least two are required.'):
            with self.subTest(instruction=instruction):
                result = w.inspect(data(form(instruction=instruction)))
                self.assertFalse([f for f in result['fields'] if f['locator']['target']['type'] == 'checkboxes'])
                self.assertTrue(any('selection limits' in n for n in result['notes']))

    def test_prior_unrelated_tick_one_table_does_not_own_history(self):
        doc = form(); table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).text = 'Type of application (please tick one):'
        doc.paragraphs[1]._p.addprevious(table._tbl)
        raw = data(doc); field = self.field(raw)
        self.assertEqual(field['kind'], 'multi_choice')
        out = w.fill(raw, [field], {field['key']: field['options'][:2]})
        index = w.SlotIndex(w.open_package(out))
        self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [True, True, False])
        self.assertEqual(Document(io.BytesIO(out)).tables[0].cell(0, 0).text,
                         'Type of application (please tick one):')

    def test_full_source_and_mapping_identity_are_revalidated_at_export(self):
        raw = data(form(instruction='Record events during the reporting period.')); field = self.field(raw)
        self.assertEqual(field['kind'], 'multi_choice')
        for old, new in (('Treatments received', 'Most recent treatment received'),
                         ('Physiotherapy', 'Changed option'), ('Clinical history', 'Select one'),
                         ('Record events during the reporting period.', 'Tick one.')):
            with self.subTest(source=old):
                with self.assertRaises(w.V3Failure) as failure:
                    w.fill(rewrite(raw, old, new), [field], {field['key']: field['options'][:2]})
                self.assertEqual(failure.exception.code, 'mapping_mismatch')
        for alter in (lambda f: f.update(label='Invented question'), lambda f: f.update(context='Invented context'),
                      lambda f: f['options'].reverse(), lambda f: f.update(kind='choice'),
                      lambda f: f['source_questions'][0]['sources'].pop()):
            changed = copy.deepcopy(field); alter(changed)
            with self.assertRaises(w.V3Failure) as failure:
                w.fill(raw, [changed], {changed['key']: changed['options'][0]})
            self.assertEqual(failure.exception.code, 'mapping_mismatch')

    def test_unrelated_checkbox_and_dropdown_defaults_do_not_change(self):
        for args in ({'question': 'Preferred treatment'}, {'control': 'glyph'}):
            with self.subTest(args=args):
                field = self.field(data(form(**args)))
                self.assertEqual(field['kind'], 'choice')
                self.assertNotIn('source_questions', field)
        doc = Document(); p = doc.add_paragraph('Treatments received: ')
        p._p.append(_sdt('dropdown', options=('Physiotherapy', 'Hydrotherapy')))
        field = w.inspect(data(doc))['fields'][0]
        self.assertEqual(field['kind'], 'choice')

    def test_legacy_mapping_keeps_recorded_kind_and_source_metadata(self):
        raw = data(form()); field = self.field(raw)
        field['kind'] = 'choice'; field.pop('source_questions', None)
        previous = copy.deepcopy(field)
        output = w.fill(raw, [field], {field['key']: 'Physiotherapy'})
        index = w.SlotIndex(w.open_package(output))
        self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [True, False, False])
        self.assertEqual(previous, field)
        with self.assertRaises(w.V3Failure):
            w.fill(raw, [field], {field['key']: field['options'][:2]})
