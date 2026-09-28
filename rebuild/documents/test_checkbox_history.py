"""Bounded native-checkbox event lists; synthetic examples are not corpus qualification."""
import copy
import io
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from lxml import etree

from . import word_v3 as w
from .test_question_boxes import data
from .test_word_v3 import checkbox_control, ff_field, _sdt


def form(question='Treatments received', options=('Physiotherapy', 'Occupational therapy', 'Hydrotherapy'),
         *, control='ff', instruction='', heading='Clinical history', separate=False, after='', bold_after=False,
         table_before='', table_after=''):
    doc = Document(); doc.add_heading(heading, 1)
    if table_before: doc.add_table(rows=1, cols=1).cell(0, 0).text = table_before
    if instruction: doc.add_paragraph(instruction)
    if separate: doc.add_paragraph(question + ':')
    for i, option in enumerate(options):
        p = doc.add_paragraph(question + ': ' if i == 0 and not separate else '')
        if control == 'ff': ff_field(p, 'checkbox', name='Answer' + str(i))
        elif control == 'sdt': p._p.append(checkbox_control())
        else: p.add_run('☐')
        p.add_run(' ' + option)
    if after:
        doc.add_paragraph('')
        doc.add_paragraph().add_run(after).bold = bold_after
    if table_after: doc.add_table(rows=1, cols=1).cell(0, 0).text = table_after
    return doc


def boxed_question(doc, question, options, *, before=None):
    """A separate printed question that owns its own native boxes inside a one-cell table (the D31 page-1 shape)."""
    table = doc.add_table(rows=1, cols=1); cell = table.cell(0, 0)
    cell.paragraphs[0].text = question
    for i, option in enumerate(options):
        p = cell.add_paragraph(); ff_field(p, 'checkbox', name='Own' + str(i)); p.add_run(' ' + option)
    if before is not None:
        before._p.addprevious(table._tbl)
    return table


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
                self.assertTrue(any('selection' in n for n in result['notes']))

    def test_only_one_owner_and_just_one_command_retain_exclusive_selection(self):
        for args in ({'question': 'Only one treatment received'}, {'instruction': 'Select just one.'}):
            with self.subTest(args=args):
                raw = data(form(**args)); field = self.field(raw)
                self.assertEqual(field['kind'], 'choice')
                output = w.fill(raw, [field], {field['key']: field['options'][0]})
                index = w.SlotIndex(w.open_package(output))
                self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [True, False, False])
                with self.assertRaises(w.V3Failure):
                    w.fill(raw, [field], {field['key']: field['options'][:2]})

    def test_unknown_or_negative_selection_instructions_never_grant_multiple(self):
        for instruction in ('Do not select multiple options.', 'Do not tick all that apply.',
                            'Select one or more.', 'Never choose several options.'):
            with self.subTest(instruction=instruction):
                result = w.inspect(data(form(instruction=instruction)))
                self.assertFalse([f for f in result['fields'] if f['locator']['target']['type'] == 'checkboxes'])
                self.assertTrue(any('selection' in n for n in result['notes']))

    def test_complete_positive_all_that_apply_command_remains_useful(self):
        raw = data(form(instruction='Please select all that apply.')); field = self.field(raw)
        self.assertEqual(field['kind'], 'multi_choice')
        output = w.fill(raw, [field], {field['key']: field['options'][:2]})
        index = w.SlotIndex(w.open_package(output))
        self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [True, True, False])

    def test_prior_unrelated_tick_one_table_does_not_own_history(self):
        # D31's shape: the tick-one instruction belongs to a separate question
        # that prints and owns its own boxes, so it does not govern the list.
        doc = form()
        boxed_question(doc, 'Type of application (please tick one):', ('Conditional', 'Absolute'),
                       before=doc.paragraphs[1])
        raw = data(doc)
        fields = [f for f in w.inspect(raw)['fields'] if f['locator']['target']['type'] == 'checkboxes']
        own = next(f for f in fields if f['label'].startswith('Type of application'))
        field = next(f for f in fields if f['label'] == 'Treatments received')
        self.assertEqual((own['kind'], field['kind']), ('choice', 'multi_choice'))
        out = w.fill(raw, [field], {field['key']: field['options'][:2]})
        index = w.SlotIndex(w.open_package(out))
        self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [True, True, False])
        self.assertEqual(Document(io.BytesIO(out)).tables[0].cell(0, 0).paragraphs[0].text,
                         'Type of application (please tick one):')
        with self.assertRaises(w.V3Failure):
            w.fill(raw, [own], {own['key']: own['options']})

    def assertUnresolved(self, raw, note='selection'):
        result = w.inspect(raw)
        self.assertFalse([f for f in result['fields'] if f['locator']['target']['type'] == 'checkboxes'
                          and f['kind'] == 'multi_choice'])
        self.assertFalse([f for f in result['fields'] if f.get('source_questions')])
        self.assertTrue(any(note in n for n in result['notes']))

    def test_adjacent_selection_instruction_outside_the_owner_is_never_skipped(self):
        # A printed "tick one" beside the list, but outside the paragraphs the
        # rule reads, must never let the list accept several selections.
        for args in ({'after': 'Tick one only.'}, {'after': 'Please tick one box.'},
                     {'after': 'Select one', 'bold_after': True}, {'after': 'Tick all that apply.'},
                     {'table_after': 'Tick one only.'}, {'table_before': 'Please tick one box only.'},
                     {'table_before': 'Type of application (please tick one):'},
                     # A sample glyph printed inside an instruction is not a separate question's own box.
                     {'table_before': 'Mark ☒ one box only.'}, {'after': 'Tick ☐ one only.'}):
            with self.subTest(args=args):
                self.assertUnresolved(data(form(**args)))

    def test_form_wide_or_floating_selection_instruction_is_never_skipped(self):
        # Printed guidance whose reach is the whole form (a preamble, a page
        # header) or whose position is unknown (a floating text box) is never
        # read as part of the local relation, so it cannot be ignored either.
        textbox = ('<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                   'xmlns:v="urn:schemas-microsoft-com:vml"><w:pict><v:shape style="position:absolute;'
                   'margin-left:300pt;width:120pt;height:30pt"><v:textbox><w:txbxContent><w:p><w:r><w:t>%s</w:t>'
                   '</w:r></w:p></w:txbxContent></v:textbox></v:shape></w:pict></w:r>')
        preamble = form(); preamble.paragraphs[0]._p.addprevious(
            copy.deepcopy(preamble.add_paragraph('Please tick only one box for each question.')._p))
        preamble.paragraphs[-1]._p.getparent().remove(preamble.paragraphs[-1]._p)
        header = form(); header.sections[0].header.paragraphs[0].text = 'Tick one box per question.'
        in_heading = form(); in_heading.paragraphs[0]._p.append(parse_xml(textbox % 'Tick one only'))
        elsewhere = form(heading='Clinical history')
        early = elsewhere.paragraphs[0]._p
        intro = copy.deepcopy(early); early.addprevious(intro)
        note = elsewhere.add_paragraph('Details below.'); note._p.append(parse_xml(textbox % 'Tick one only'))
        early.addprevious(note._p)
        framed = form(); frame = framed.add_paragraph('Tick one only')
        frame._p.get_or_add_pPr().append(parse_xml(
            '<w:framePr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'w:w="2400" w:hAnchor="page" w:vAnchor="page" w:x="8000" w:y="3000"/>'))
        framed.paragraphs[0]._p.addprevious(frame._p)
        for name, doc in (('preamble', preamble), ('page header', header), ('text box in heading', in_heading),
                          ('text box elsewhere', elsewhere), ('positioned frame elsewhere', framed)):
            with self.subTest(case=name):
                self.assertUnresolved(data(doc))

    def test_form_wide_text_without_a_selection_command_keeps_the_history_useful(self):
        textbox = ('<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                   'xmlns:v="urn:schemas-microsoft-com:vml"><w:pict><v:shape style="position:absolute;'
                   'margin-left:300pt;width:120pt;height:30pt"><v:textbox><w:txbxContent><w:p><w:r><w:t>%s</w:t>'
                   '</w:r></w:p></w:txbxContent></v:textbox></v:shape></w:pict></w:r>')
        doc = form(); doc.sections[0].header.paragraphs[0].text = 'Please answer all questions on this form.'
        grid = doc.add_paragraph('Tick one box per row in the table below.')
        doc.paragraphs[0]._p.addprevious(copy.deepcopy(grid._p)); grid._p.getparent().remove(grid._p)
        doc.paragraphs[0]._p.append(parse_xml(textbox % 'Office use'))
        raw = data(doc); field = self.field(raw)
        self.assertEqual(field['kind'], 'multi_choice')
        output = w.fill(raw, [field], {field['key']: field['options'][:2]})
        index = w.SlotIndex(w.open_package(output))
        self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [True, True, False])

    def test_a_selection_instruction_pointing_at_the_list_from_further_away_is_not_skipped(self):
        above = form()
        pointer = above.add_table(rows=1, cols=1); pointer.cell(0, 0).text = 'Please tick one box in the list below.'
        name = above.add_table(rows=1, cols=2); name.cell(0, 0).text = 'Name:'
        above.paragraphs[1]._p.addprevious(pointer._tbl); above.paragraphs[1]._p.addprevious(name._tbl)
        below = form(table_after='Other: give details.'); below.add_paragraph('For the list above, tick one only.')
        for name, doc in (('pointer two blocks above', above), ('pointer two blocks below', below)):
            with self.subTest(case=name):
                self.assertUnresolved(data(doc))

    def test_neighbouring_content_without_selection_wording_keeps_the_history_useful(self):
        plain = form(after='Record further details in the box below.')
        tables = form(table_before='Other: give the dates and destination.',
                      table_after='Other leave: give the dates and destination.')
        following = form(); boxed_question(following, 'Type of application (please tick one):', ('Conditional', 'Absolute'))
        for name, doc in (('plain paragraph after', plain), ('text tables around', tables),
                          ('next question owns its tick-one boxes', following)):
            with self.subTest(case=name):
                raw = data(doc)
                fields = [f for f in w.inspect(raw)['fields'] if f['locator']['target']['type'] == 'checkboxes']
                field = next(f for f in fields if f['label'] == 'Treatments received')
                self.assertEqual(field['kind'], 'multi_choice')
                self.assertTrue(all(f['kind'] == 'choice' for f in fields if f is not field))
                out = w.fill(raw, [field], {field['key']: field['options'][1:]})
                index = w.SlotIndex(w.open_package(out))
                self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [False, True, True])

    def test_ordinary_complete_single_commands_remain_useful_single_choices(self):
        for instruction in ('Tick one box.', 'Tick one only.', 'Choose one of the following:', '(Tick one)',
                            'Select a single answer.', 'Pick one.', 'Tick 1 box.', 'Please select ONE option only.',
                            'Record the treatment. Tick one.', 'Pick 1.', 'Indicate 1 answer.'):
            with self.subTest(instruction=instruction):
                raw = data(form(instruction=instruction)); field = self.field(raw)
                self.assertEqual(field['kind'], 'choice')
                self.assertIn(instruction, field['context'])
                output = w.fill(raw, [field], {field['key']: field['options'][2]})
                index = w.SlotIndex(w.open_package(output))
                self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [False, False, True])
                with self.assertRaises(w.V3Failure):
                    w.fill(raw, [field], {field['key']: field['options'][:2]})

    def test_a_numbered_part_heading_is_not_a_quantity(self):
        for heading in ('Part One: Leave history', 'Section One'):
            with self.subTest(heading=heading):
                raw = data(form(heading=heading)); field = self.field(raw)
                self.assertEqual(field['kind'], 'multi_choice')
                self.assertIn(heading, field['context'])
        self.assertUnresolved(data(form(heading='Part One: select one or more')))

    def test_ordinary_complete_multiple_commands_remain_useful(self):
        for instruction in ('Tick as many as apply.', 'Record the treatments. Tick all that apply.',
                            '(Tick all that apply)', 'All that apply.', 'Select any that apply.'):
            with self.subTest(instruction=instruction):
                raw = data(form(instruction=instruction)); field = self.field(raw)
                self.assertEqual(field['kind'], 'multi_choice')
                output = w.fill(raw, [field], {field['key']: [field['options'][0], field['options'][2]]})
                index = w.SlotIndex(w.open_package(output))
                self.assertEqual([w.box_state(index, b) for b in field['locator']['target']['boxes']], [True, False, True])

    def test_single_or_limited_wording_outside_the_command_grammar_never_grants_multiple(self):
        for instruction in ('Put an X in the box that applies.', 'Put a cross in one box.',
                            'Record either physiotherapy or hydrotherapy.', 'These are mutually exclusive.',
                            'Pick two.', 'Tick one. Do not tick more than one.', 'Max 2.', 'Choose the best option.'):
            with self.subTest(instruction=instruction):
                self.assertUnresolved(data(form(instruction=instruction)))

    def test_owner_quantity_other_than_exactly_one_is_unresolved(self):
        for question in ('One or more treatments received', 'One or two treatments received',
                         'One to three treatments received', 'One and only one treatment received'):
            with self.subTest(question=question):
                self.assertUnresolved(data(form(question=question)))

    def test_interrogative_or_conditional_owner_is_not_an_event_history(self):
        for question, options in (('Has a pregnancy test been completed', ('Yes - urine', 'Yes - serum', 'Declined')),
                                  ('Were any courses attended', ('First aid', 'Literacy', 'Food hygiene')),
                                  ('If yes, treatments received', ('Physiotherapy', 'Hydrotherapy'))):
            with self.subTest(question=question):
                raw = data(form(question, options)); field = self.field(raw)
                self.assertEqual(field['kind'], 'choice')
                self.assertNotIn('source_questions', field)
                with self.assertRaises(w.V3Failure):
                    w.fill(raw, [field], {field['key']: field['options'][:2]})

    def test_negative_or_exclusive_answer_options_keep_one_choice(self):
        for options in (('Physiotherapy', 'Hydrotherapy', 'None of the above'), ('Physiotherapy', 'No treatment'),
                        ('Physiotherapy', 'Yes - other'), ('Physiotherapy', 'Not taken')):
            with self.subTest(options=options):
                raw = data(form(options=options)); field = self.field(raw)
                self.assertEqual(field['kind'], 'choice')
                with self.assertRaises(w.V3Failure):
                    w.fill(raw, [field], {field['key']: field['options'][:2]})

    def test_referenced_owner_or_option_is_unresolved(self):
        doc = form(); note = OxmlElement('w:r'); ref = OxmlElement('w:footnoteReference')
        ref.set(qn('w:id'), '1'); note.append(ref); doc.paragraphs[1].runs[0]._r.addnext(note)
        cases = [('footnote', data(doc)), ('owner asterisk', data(form(question='Treatments received*'))),
                 ('option dagger', data(form(options=('Physiotherapy', 'Hydrotherapy†'))))]
        for name, raw in cases:
            with self.subTest(case=name):
                self.assertUnresolved(raw, note='native-checkbox history source is unresolved')

    def test_positioned_source_paragraph_is_unresolved(self):
        # A frame prints the paragraph somewhere else on the page: it is not
        # proven to be this list's adjacent instruction.
        doc = form(instruction='Record events during the reporting period.')
        doc.paragraphs[1]._p.get_or_add_pPr().append(parse_xml(
            '<w:framePr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'w:w="2400" w:hAnchor="page" w:vAnchor="page" w:x="8000" w:y="3000"/>'))
        self.assertUnresolved(data(doc), note='native-checkbox history source is unresolved')

    def test_d31_shaped_leave_history_accepts_two_leave_selections(self):
        # Synthetic mirror of D31's A15 layout (no corpus content): a long
        # section instruction box, question/answer tables, then the leave list
        # as two tab-separated native boxes per paragraph with spacer lines.
        doc = Document(); doc.add_heading('Conditional Discharge Proposal', 1)
        boxed_question(doc, 'Type of discharge applied for (please tick one):', ('Conditional', 'Absolute'))
        doc.add_table(rows=1, cols=2).rows[0].cells[1].text = 'Please see the list at annex B and select accordingly'
        doc.add_table(rows=1, cols=2).rows[0].cells[1].text = 'Responsible Clinician (including employing organisation)'
        doc.add_paragraph(''); doc.add_paragraph('')
        rows = (('Compassionate (day)', 'Compassionate (overnight)'), ('Medical (day)', 'Medical (overnight)'),
                ('Long Term Escorted Leave of Absence',))
        for n, row in enumerate(rows):
            p = doc.add_paragraph('Community leave taken:\t' if n == 0 else '')
            for k, option in enumerate(row):
                ff_field(p, 'checkbox', name='Leave%d%d' % (n, k)); p.add_run(' ' + option + ('    \t        \t' if k == 0 and len(row) > 1 else ''))
            doc.add_paragraph('')
        doc.add_table(rows=1, cols=2).rows[0].cells[1].text = 'Leave taken within the hospital grounds; leave to attend Court;'
        raw = data(doc)
        fields = [f for f in w.inspect(raw)['fields'] if f['locator']['target']['type'] == 'checkboxes']
        leave = next(f for f in fields if f['label'] == 'Community leave taken')
        discharge = next(f for f in fields if f['label'].startswith('Type of discharge'))
        self.assertEqual((leave['kind'], discharge['kind']), ('multi_choice', 'choice'))
        self.assertEqual(len(leave['options']), 5)
        chosen = ['Compassionate (day)', 'Compassionate (overnight)']
        output = w.fill(raw, [leave], {leave['key']: chosen})
        index = w.SlotIndex(w.open_package(output))
        self.assertEqual([w.box_state(index, b) for b in leave['locator']['target']['boxes']],
                         [o in chosen for o in leave['options']])
        with self.assertRaises(w.V3Failure):
            w.fill(raw, [discharge], {discharge['key']: discharge['options']})

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
