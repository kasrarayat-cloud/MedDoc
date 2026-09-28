"""Printed value columns and coded choices are distinct answer structures."""
import unittest

from docx import Document
from docx.oxml.ns import qn

from . import word_v3 as w, layout_source
from .test_question_boxes import data
from . import test_question_boxes as question_fixtures


def grid(headers=('Left', 'Right'), *, boxes=False, instruction='Pulses'):
    doc = Document()
    outer = doc.add_table(rows=1, cols=1)
    table = outer.cell(0, 0).add_table(rows=4, cols=3)
    table.cell(0, 0).text = instruction
    for col, text in enumerate(headers, 1): table.cell(0, col).text = text
    for row, label in enumerate(('Radial', 'Femoral', 'Tibial'), 1):
        table.cell(row, 0).text = label
        if boxes:
            for col in (1, 2): table.cell(row, col).text = '☐'
    return doc


class StructuralColumns(unittest.TestCase):
    def test_blank_side_columns_keep_independent_values_and_fixed_headers(self):
        raw = data(grid()); fields = w.inspect(raw)['fields']
        self.assertEqual(len(fields), 6)
        self.assertTrue(all(f['kind'] == 'text' for f in fields))
        self.assertEqual({f['label'] for f in fields},
                         {f'{row} — {side}' for row in ('Radial', 'Femoral', 'Tibial') for side in ('Left', 'Right')})
        answers = {f['key']: str(i + 1) for i, f in enumerate(fields)}
        result = w.fill(raw, fields, answers)
        before = w.SlotIndex(w.open_package(raw)); after = w.SlotIndex(w.open_package(result))
        for f in fields:
            ref = f['locator']['part'] + '#' + f['locator']['slot']
            self.assertEqual(w.text_of(after.by_id[ref].el), answers[f['key']])
        from lxml import etree
        for col in range(3):
            header = f'word/document.xml#b/tbl[0]/tr[0]/tc[0]/tbl[0]/tr[0]/tc[{col}]'
            self.assertEqual(etree.tostring(before.by_id[header].el), etree.tostring(after.by_id[header].el))
        self.assertEqual(w.fill(raw, fields, {}), raw)

    def test_true_option_grids_keep_choices_and_never_map_the_header(self):
        for headers, boxes, instruction in [(('Yes', 'No'), False, 'Finding'),
                                            (('Left', 'Right'), True, 'Affected side'),
                                            (('Left', 'Right'), False, 'Select one side')]:
            with self.subTest(headers=headers, boxes=boxes, instruction=instruction):
                raw = data(grid(headers, boxes=boxes, instruction=instruction))
                fields = w.inspect(raw)['fields']
                self.assertEqual(len(fields), 3)
                self.assertTrue(all(f['kind'] == 'choice' for f in fields))
                self.assertTrue(all(f['options'] == list(headers) for f in fields))
                self.assertFalse(any('/tr[0]/tc[1]' in f['locator']['slot'].split('/tbl[0]/')[-1] for f in fields))

    def test_summary_title_owns_the_single_unlabelled_coded_row(self):
        for control in ('glyph', 'sdt', 'ff'):
            with self.subTest(control=control):
                doc = question_fixtures.TabColumnOwnership().form(control=control, count=3)
                doc.tables[0].cell(0, 1).text = 'Fixed details'
                cell = doc.tables[0].cell(0, 0)
                cell.paragraphs[0].text = 'Examination summary'
                row = cell.paragraphs[-1]
                row.runs[0].text = ''
                raw = data(doc)
                proposal, _, _ = layout_source.prepare(raw)
                self.assertEqual(len(proposal['fields']), 1)
                field = proposal['fields'][0]
                self.assertEqual(field['label'], 'Examination summary')
                self.assertEqual(field['options'], ['Normal', 'Abnormal', 'Unavailable'])
                self.assertEqual(w.inspect(raw)['fields'], [])
                _, result, _ = layout_source.prepare(raw, mapping=proposal['fields'], answers={field['key']: 'Abnormal'})
                self.assertEqual(w.option_states(w.SlotIndex(w.open_package(result)), field), [False, True, False])

    def test_unresolved_coded_row_never_becomes_numeric_options(self):
        for row in ('Finding      1 ☐    2 ☐', 'Finding\t\t1 ☐\t2 ☐'):
            doc = Document(); cell = doc.add_table(rows=1, cols=1).cell(0, 0)
            cell.text = 'Examination'; cell.add_paragraph(row)
            result = w.inspect(data(doc))
            self.assertFalse(any(f.get('options') for f in result['fields']))
            self.assertTrue(any('coded' in note.lower() for note in result['notes']))


def coded_form(*cells, control='ff', marked=None, heading='Physical examination'):
    """One outer table; each cell prints `lines`. Every '☐' is a checkbox control of `control` kind
    and every '▭' a legacy text field."""
    from docx.oxml import OxmlElement
    from .test_word_v3 import checkbox_control, ff_field, ff_text_field
    doc = Document()
    if heading:
        doc.add_paragraph(heading, style='Heading 1')
    table = doc.add_table(rows=len(cells) + bool(marked), cols=2)
    if marked:
        table.cell(0, 0).text = marked; table.cell(0, 1).text = 'Comments'
        table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    for number, lines in enumerate(cells):
        cell = table.cell(number + bool(marked), 0)
        for line_number, line in enumerate(lines):
            paragraph = cell.paragraphs[0] if line_number == 0 else cell.add_paragraph()
            pieces = line.split('☐')
            for ordinal, piece in enumerate(pieces):
                for part_number, part in enumerate(piece.split('▭')):
                    if part_number:
                        ff_text_field(paragraph, name='T%d_%d' % (number, line_number))
                    if part:
                        paragraph.add_run(part)
                if ordinal < len(pieces) - 1:
                    if control == 'glyph':
                        paragraph.add_run('☐')
                    elif control == 'sdt':
                        paragraph._p.append(checkbox_control())
                    else:
                        ff_field(paragraph, 'checkbox', name='C%d_%d_%d' % (number, line_number, ordinal))
    return doc


HEART = ['11.\tHeart and large arteries', '', '\tNormal\tAbnormal', 'Heart palpation\t1 ☐\t2 ☐', '',
         'Carotid artery ', 'Auscultation/Pain\tAbsent\tPresent', '(systolic bruit)\t1 ☐\t2 ☐', '',
         'Abdominal artery  ', 'auscultation (bruit)\t1 ☐\t2 ☐', '']
LYMPH = ['16.\tLymph Nodes', '', 'Cervical\tNormal\tEnlarged\tTender', 'Posterior\t1 ☐\t2 ☐\t3 ☐', '',
         'Anterior\t1 ☐\t2 ☐\t3 ☐', '', 'Axillary\t1 ☐\t2 ☐\t3 ☐', '']
SUMMARY = ['Head summary', '', '\tNormal\tAbnormal\tExam not done', '\t1 ☐\t2 ☐\t3 ☐', '', '']


def stops(paragraph, leader=None):
    from docx.oxml import OxmlElement
    tabs = OxmlElement('w:tabs')
    for position in (3600, 5400):
        tab = OxmlElement('w:tab'); tab.set(qn('w:val'), 'center'); tab.set(qn('w:pos'), str(position))
        if leader:
            tab.set(qn('w:leader'), leader)
        tabs.append(tab)
    paragraph._p.get_or_add_pPr().append(tabs)


def detect(raw):
    detector = w.Detector(w.open_package(raw), layout_proposal=True)
    areas, notes = detector.detect()
    coded = [a for a in areas if 'column_sequence' in a.target]
    return detector, coded, notes


class CodedColumnSequences(unittest.TestCase):
    """Coded response columns: the literal header names each option by position; codes never do."""

    def proposal(self, raw):
        proposal, _, _ = layout_source.prepare(raw)
        return [f for f in proposal['fields'] if f['locator']['target'].get('column_sequence')], proposal

    def test_a_lead_names_only_the_first_row_of_its_header(self):
        for control in ('ff', 'glyph', 'sdt'):
            with self.subTest(control=control):
                fields, _ = self.proposal(data(coded_form(HEART, LYMPH, control=control)))
                self.assertEqual([(f['label'], f['options']) for f in fields], [
                    ('Heart palpation', ['Normal', 'Abnormal']),
                    ('Carotid artery Auscultation/Pain (systolic bruit)', ['Absent', 'Present']),
                    ('Abdominal artery auscultation (bruit)', ['Absent', 'Present']),
                    ('Posterior', ['Normal', 'Enlarged', 'Tender']),
                    ('Anterior', ['Normal', 'Enlarged', 'Tender']),
                    ('Axillary', ['Normal', 'Enlarged', 'Tender'])])
                self.assertTrue(all('Cervical' in f['context'] for f in fields[3:]))
                carotid = fields[1]['locator']['target']['column_sequence']
                self.assertEqual(carotid['header_index'], 1)
                self.assertEqual([s['slot'].rsplit('/', 1)[1] for s in carotid['source']], ['p[5]', 'p[6]', 'p[7]'])

    def test_response_codes_never_become_options_and_boxes_follow_their_header(self):
        cell = ['3.\tNeck', '\tYes\tNo', 'Supple\t1 ☐\t2 ☐', '', '\tNo\tYes', 'Masses\t2 ☐\t1 ☐', '',
                'Jugular venous\tAbsent\tPresent', 'Distension\t1 ☐\t2 ☐', '']
        raw = data(coded_form(cell))
        fields, proposal = self.proposal(raw)
        self.assertEqual([(f['label'], f['options']) for f in fields], [
            ('Supple', ['Yes', 'No']), ('Masses', ['No', 'Yes']),
            ('Jugular venous Distension', ['Absent', 'Present'])])
        answers = {fields[0]['key']: 'Yes', fields[1]['key']: 'Yes'}
        prepared, actual, _ = layout_source.prepare(raw, mapping=proposal['fields'], answers=answers)
        index = w.SlotIndex(w.open_package(actual))
        self.assertEqual(w.option_states(index, fields[0]), [True, False])
        self.assertEqual(w.option_states(index, fields[1]), [False, True])
        self.assertEqual(w.option_states(index, fields[2]), [False, False])
        described = {c['source']['label']: c for c in prepared['manifest']['candidates']}
        self.assertEqual({k: (c['optional'], c['untouched']) for k, c in described.items()},
                         {'Supple': (True, False), 'Masses': (True, False), 'Jugular venous Distension': (True, True)})

    def test_answering_one_row_leaves_a_later_row_of_the_same_printed_sequence_holdable(self):
        raw = data(coded_form(['10.\tLungs', '\tNormal\tAbnormal', 'Percussion\t1 ☐\t2 ☐', '',
                               'Auscultation\t1 ☐\t2 ☐', '', 'Palpation\t1 ☐\t2 ☐']))
        fields, proposal = self.proposal(raw)
        later = fields[1]['locator']['target']['column_sequence']['source']
        self.assertEqual([s['slot'].rsplit('/', 1)[1] for s in later], ['p[1]', 'p[2]', 'p[4]'])
        for answered, expected in (({fields[0]['key']: 'Abnormal'}, (False, True, True)),
                                   ({fields[1]['key']: 'Normal'}, (True, False, True)),
                                   ({fields[1]['key']: ''}, (True, True, True))):
            with self.subTest(answered=answered):
                prepared, _, _ = layout_source.prepare(raw, mapping=proposal['fields'], answers=answered)
                self.assertEqual(tuple(c['untouched'] for c in prepared['manifest']['candidates']), expected)
        # An answer that repeats a printed tick changes no byte of its row and is still an answer to it.
        from docx.oxml import OxmlElement
        doc = coded_form(['10.\tLungs', '\tNormal\tAbnormal', 'Percussion\t1 ☐\t2 ☐', '',
                          'Auscultation\t1 ☐\t2 ☐', '', 'Palpation\t1 ☐\t2 ☐'])
        for box, value in zip(doc.tables[0].cell(0, 0).paragraphs[6]._p.iter(qn('w:checkBox')), ('1', '0')):
            checked = OxmlElement('w:checked'); checked.set(qn('w:val'), value); box.append(checked)
        raw = data(doc)
        fields, proposal = self.proposal(raw)
        self.assertEqual(fields[2]['options'], ['Normal', 'Abnormal'])
        prepared, actual, _ = layout_source.prepare(raw, mapping=proposal['fields'], answers={fields[2]['key']: 'Normal'})
        row = w.SlotIndex(w.open_package(raw)).by_id['word/document.xml#' + fields[2]['locator']['slot']].el
        self.assertEqual(w.fingerprint(row),
                         w.fingerprint(w.SlotIndex(w.open_package(actual)).by_id['word/document.xml#' + fields[2]['locator']['slot']].el))
        self.assertEqual(tuple(c['untouched'] for c in prepared['manifest']['candidates']), (True, True, False))

    def test_wide_whitespace_columns_titles_and_blank_spacers_are_read(self):
        joints = ['14.\tJoints Muscles ( review swelling, heat or redness, ', '       nodularity, ROM, tender points)',
                  '\t\tNormal\tAbnormal', 'Spine\t1 ☐\t2 ☐', ' ', 'Hands\t1 ☐\t2 ☐', '']
        extremities = ['13.\tExtremities', '\t  No\tYes', 'Edematous\t1 ☐\t2 ☐', '',
                       'Dependent rubor                     1 ☐                   2 ☐', '']
        pharynx = [' 8.  Pharynx', '', '                         Normal           Abnormal',
                   '    Mucosa          \t                     1 ☐                 2 ☐', '',
                   ' Volume adequate                   1 ☐                  2 ☐', '    ']
        eyes = ['5.\tEyes', '', 'Pupils', '\tYes\tNo', 'Equal\t1 ☐\t2 ☐', '', 'Round\t1 ☐\t2 ☐', '']
        doc = coded_form(joints, extremities, pharynx, eyes)
        for row, number in ((0, 4), (2, 6)):
            stops(doc.tables[0].cell(row, 0).paragraphs[number])  # printed spaces, no tab character
        fields, _ = self.proposal(data(doc))
        self.assertEqual([(f['label'], f['options']) for f in fields], [
            ('Spine', ['Normal', 'Abnormal']), ('Hands', ['Normal', 'Abnormal']),
            ('Edematous', ['No', 'Yes']), ('Dependent rubor', ['No', 'Yes']),
            ('Mucosa', ['Normal', 'Abnormal']), ('Volume adequate', ['Normal', 'Abnormal']),
            ('Equal', ['Yes', 'No']), ('Round', ['Yes', 'No'])])
        self.assertIn('Pupils', fields[-1]['context'])

    def test_an_indented_header_label_is_read_only_when_it_leaves_one_option_per_box(self):
        muscles = ['17d.\tMuscles ', '\tNormal\tAbnormal', 'Tone\t1 ☐\t2 ☐', '',
                   '      Proximal muscle strength     Normal          Abnormal', '\t                    1 ☐\t  2 ☐',
                   '     Distal muscle strength     Normal          Abnormal', '\t                    1 ☐\t  2 ☐', '']
        fields, _ = self.proposal(data(coded_form(muscles)))
        self.assertEqual([(f['label'], f['options']) for f in fields], [
            ('Tone', ['Normal', 'Abnormal']), ('Proximal muscle strength', ['Normal', 'Abnormal']),
            ('Distal muscle strength', ['Normal', 'Abnormal'])])
        proximal = fields[1]['locator']['target']['column_sequence']['source'][0]
        self.assertEqual(proximal['starts'][0], 0); self.assertEqual(len(proximal['starts']), 3)
        # Leading printed spaces are never dropped to force a fit: three words over three boxes stay three options.
        wide = ['17d.\tMuscles ', '      Strength     Normal          Abnormal', '\t     1 ☐\t  2 ☐\t 3 ☐']
        fields, _ = self.proposal(data(coded_form(wide)))
        self.assertEqual([(f['label'], f['options']) for f in fields], [('17d. Muscles', ['Strength', 'Normal', 'Abnormal'])])
        for cell in (['17d.\tMuscles ', '      Strength     Normal          Abnormal', '\t     1 ☐'],
                     ['17d.\tMuscles ', '\t  Strength     Normal          Abnormal', '\t     1 ☐\t  2 ☐']):
            with self.subTest(cell=cell):
                _, coded, notes = detect(data(coded_form(cell)))
                self.assertEqual(coded, [])

    def test_a_summary_title_is_verified_with_its_single_unlabelled_row(self):
        raw = data(coded_form(SUMMARY, ['Neck summary', '', '\tNormal\tAbnormal\tExam not done', '\t1 ☐\t2 ☐\t3 ☐']))
        fields, proposal = self.proposal(raw)
        self.assertEqual([f['label'] for f in fields], ['Head summary', 'Neck summary'])
        for field in fields:
            relation = field['locator']['target']['column_sequence']
            self.assertEqual(relation['header_index'], 1)
            self.assertEqual([s['slot'].rsplit('/', 1)[1] for s in relation['source']], ['p[0]', 'p[2]', 'p[3]'])
        self.assertFalse([n for n in proposal['warnings'] if 'Tab-column options' in n])
        model = proposal['manifest']['candidates'][0]['rendered_source']
        self.assertEqual(''.join(i['text'] for s in model['sequence'][0]['segments'] for i in s), 'Head summary')
        self.assertEqual(model['header_index'], 1)
        inspected = w.inspect(raw)
        self.assertFalse([f for f in inspected['fields'] if f['locator']['target']['type'] == 'checkboxes'])
        self.assertEqual(inspected['layout_pending'], 2)
        self.assertFalse([n for n in inspected['notes'] if 'Tab-column options' in n])

    def test_unlabelled_rows_never_borrow_an_uncertain_title(self):
        for cell in (['5.\tEyes', 'Pupils', '\tNormal\tAbnormal', '\t1 ☐\t2 ☐'],
                     ['4.\tThyroid', '\tNo\tYes', 'Visible\t1 ☐\t2 ☐', '', '\t1 ☐\t2 ☐']):
            with self.subTest(cell=cell):
                _, coded, notes = detect(data(coded_form(cell)))
                self.assertEqual(coded, [])
                self.assertTrue(any(n.startswith('Coded column sequence at ') for n in notes))

    def test_incomplete_or_ambiguous_sources_are_noted_and_never_guessed(self):
        cases = {
            'trailing header': ['7.\tNose', '\tNormal\tAbnormal', 'Mucosa\t1 ☐\t2 ☐', 'Septum\t1 ☐\t2 ☐', '',
                                '\tAbsent\tPresent', ''],
            'text below a row': ['10.\tLungs', '\tNormal\tAbnormal', 'Chest percussion\t1 ☐\t2 ☐',
                                 'Lung auscultation', '(sound, rales)\t1 ☐\t2 ☐'],
            'text above a spacer': ['10.\tLungs', '\tNormal\tAbnormal', 'Chest percussion\t1 ☐\t2 ☐', '',
                                    'Lung auscultation', '', '(sound, rales)\t1 ☐\t2 ☐'],
            'title asks for an answer': ['19. Other (specify)', '', 'Mental status    Normal\t   Abnormal',
                                         '\t     1 ☐          2 ☐', 'Speech\t1 ☐\t2 ☐'],
            'repeated row label': ['6.\tEars', '\tNormal\tAbnormal', 'Canal\t1 ☐\t2 ☐', '', 'Canal\t1 ☐\t2 ☐'],
            'row before header': ['6.\tEars', 'Canal\t1 ☐\t2 ☐', '\tNormal\tAbnormal', 'Drum\t1 ☐\t2 ☐'],
            'no title': ['\tNormal\tAbnormal', 'Canal\t1 ☐\t2 ☐', '', 'Drum\t1 ☐\t2 ☐'],
            'numbers only': ['2.\tScale', '\t1\t2\t3', 'Pain\t1 ☐\t2 ☐\t3 ☐', '', 'Fatigue\t1 ☐\t2 ☐\t3 ☐'],
        }
        cases['tab-led blank'] = ['9.\tChest', '\tNormal\tAbnormal', 'Shape\t1 ☐\t2 ☐', '\t', 'Symmetry\t1 ☐\t2 ☐']
        cases['underlined blank'] = ['9.\tChest', '\tNormal\tAbnormal', 'Shape\t1 ☐\t2 ☐', '    ', 'Symmetry\t1 ☐\t2 ☐']
        for name, cell in cases.items():
            with self.subTest(name):
                doc = coded_form(cell)
                if name == 'tab-led blank':
                    stops(doc.tables[0].cell(0, 0).paragraphs[3], leader='dot')
                if name == 'underlined blank':
                    doc.tables[0].cell(0, 0).paragraphs[3].runs[0].font.underline = True
                raw = data(doc)
                detector, coded, notes = detect(raw)
                self.assertEqual(coded, [])
                self.assertTrue(any(n.startswith('Coded column sequence at ') for n in notes))
                # Nothing in the unresolved coded source becomes an option or a numeric label.
                self.assertFalse([a for a in detector.areas if a.options and any(o.strip().isdigit() for o in a.options)])

    def test_embedded_objects_breaks_and_unknown_states_are_noted_before_rendering(self):
        from docx.oxml import OxmlElement
        from .test_word_v3 import checkbox_control, ff_field
        good = ['9.\tChest', '\tNormal\tAbnormal', 'Shape\t1 ☐\t2 ☐', '', 'Symmetry\t1 ☐\t2 ☐']
        for problem in ('text field', 'field in label text', 'carriage return', 'unknown state'):
            with self.subTest(problem):
                doc = coded_form(good, ['12a.\tAbdomen', '\tNormal\tAbnormal', 'Bowel\t1 ☐\t2 ☐', '', 'Masses\t1 ☐\t2 ☐'])
                row = doc.tables[0].cell(1, 0).paragraphs[4]
                if problem == 'text field':
                    doc = coded_form(good, ['12a.\tAbdomen', '\tNormal\tAbnormal', 'Bowel\t1 ☐\t2 ☐', '',
                                            'Masses ▭\t1 ☐\t2 ☐'])
                    self.assertIn('\x00', w.paragraph_text(doc.tables[0].cell(1, 0).paragraphs[4]._p)[0])
                elif problem == 'field in label text':
                    doc = coded_form(good, ['12a.\tAbdomen', '\tNormal\tAbnormal', 'Bowel\t1 ☐\t2 ☐', '',
                                            'Masses ▭ and', 'organs\t1 ☐\t2 ☐'])
                elif problem == 'carriage return':
                    row.runs[0]._r.append(OxmlElement('w:cr'))
                else:
                    sdt_doc = coded_form(['12a.\tAbdomen', '\tNormal\tAbnormal', 'Bowel\t1 ☐\t2 ☐', '',
                                          'Masses\t1 ☐\t2 ☐'], control='sdt')
                    control = sdt_doc.tables[0].cell(0, 0).paragraphs[4]._p.findall(qn('w:sdt'))[0]
                    control.find(qn('w:sdtContent')).find(qn('w:r')).find(qn('w:t')).text = '☒'
                    doc = coded_form(good); doc.tables[0].add_row()
                    target = doc.tables[0].cell(1, 0)._tc
                    target.remove(target.find(qn('w:p')))
                    for paragraph in sdt_doc.tables[0].cell(0, 0)._tc.findall(qn('w:p')):
                        target.append(paragraph)
                raw = data(doc)
                _, coded, notes = detect(raw)
                self.assertEqual([a.label for a in coded], ['Shape', 'Symmetry'])
                self.assertTrue(any(n.startswith('Coded column sequence at ') and 'tr[1]/tc[0]' in n for n in notes))
                fields, _ = self.proposal(raw)
                self.assertEqual([f['label'] for f in fields], ['Shape', 'Symmetry'])

    def test_a_proposal_later_withdrawn_for_its_metadata_bound_is_no_longer_a_layout_candidate(self):
        long_title = '20.\tRepeated section ' + 'with a long printed explanation ' * 26
        repeated = [long_title, '\tNormal\tAbnormal', 'Finding\t1 ☐\t2 ☐', '', 'Second finding\t1 ☐\t2 ☐']
        raw = data(coded_form(repeated, repeated, HEART))
        detector, coded, notes = detect(raw)
        self.assertLessEqual(len(detector.layout_candidates), len(coded))
        self.assertEqual({id(area) for _, _, area in detector.layout_candidates}, {id(area) for area in coded})
        self.assertTrue(any('exceeds the mapping limit' in n for n in notes))
        fields, _ = self.proposal(raw)
        self.assertEqual([f['label'] for f in fields], ['Heart palpation', 'Carotid artery Auscultation/Pain (systolic bruit)',
                                                        'Abdominal artery auscultation (bruit)'])

    def test_marked_column_headers_are_the_only_table_context_and_must_be_visible(self):
        from docx.oxml import OxmlElement
        raw = data(coded_form(['12b.\tLiver', '', '\tNo\tYes', 'Palpable\t1 ☐\t2 ☐', '', 'Tender\t1 ☐\t2 ☐'],
                              SUMMARY, marked='Physical examination'))
        fields, _ = self.proposal(raw)
        self.assertEqual(fields[-1]['label'], 'Head summary')
        self.assertNotIn('Palpable', fields[-1]['context'])
        self.assertIn('Physical examination', fields[-1]['context'])
        doc = coded_form(SUMMARY, marked='Physical examination')
        doc.tables[0].cell(0, 0).paragraphs[0].runs[0]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
        _, coded, notes = detect(data(doc))
        self.assertEqual(coded, [])
        self.assertTrue(any(n.startswith('Coded column sequence at ') for n in notes))


def stopped_form(rows, widths, *, control='ff', heading='Physical examination'):
    """rows: [[cell lines, ...], ...]; a line is text or (text, [(position, kind), ...], leader)."""
    from docx.oxml import OxmlElement
    from .test_word_v3 import ff_field
    doc = Document()
    if heading:
        doc.add_paragraph(heading, style='Heading 1')
    table = doc.add_table(rows=len(rows), cols=len(widths))
    for col, width in zip(table._tbl.tblGrid.findall(qn('w:gridCol')), widths):
        col.set(qn('w:w'), str(width))
    for r, cells in enumerate(rows):
        for c, lines in enumerate(cells):
            cell = table.cell(r, c)
            for n, line in enumerate(lines):
                paragraph = cell.paragraphs[0] if n == 0 else cell.add_paragraph()
                text, positions, leader = (line + (None,))[:3] if isinstance(line, tuple) else (line, None, None)
                pieces = text.split('☐')
                for ordinal, piece in enumerate(pieces):
                    if piece:
                        paragraph.add_run(piece)
                    if ordinal < len(pieces) - 1:
                        if control == 'glyph':
                            paragraph.add_run('☐')
                        else:
                            ff_field(paragraph, 'checkbox', name='S%d_%d_%d_%d' % (r, c, n, ordinal))
                if positions:
                    tabs = OxmlElement('w:tabs')
                    for position in positions:
                        tab = OxmlElement('w:tab'); tab.set(qn('w:val'), 'center'); tab.set(qn('w:pos'), str(position))
                        if leader:
                            tab.set(qn('w:leader'), leader)
                        tabs.append(tab)
                    paragraph._p.get_or_add_pPr().append(tabs)
    return doc


class WitnessOwnsItsRendering(unittest.TestCase):
    """A proposal is verified only on its own printed paragraphs (refutation 2026-09-28 A1, C1, C4)."""

    @classmethod
    def setUpClass(cls):
        from .test_layout_containment import SequenceContainment
        cls.pdf = SequenceContainment('test_fixture_font_keeps_literal_character_codes')
        SequenceContainment.setUpClass()

    def liver_and_spleen(self):
        # The refuter's form: two cells print the same header and rows; Liver's rows are one column right.
        liver = ['12b.\tLiver', ('\tNormal\tAbnormal', (2880, 4320)), ('Palpation\t1 ☐\t2 ☐', (4320, 5760)),
                 ('Tenderness\t1 ☐\t2 ☐', (4320, 5760))]
        spleen = ['12c.\tSpleen', ('\tNormal\tAbnormal', (2880, 4320)), ('Palpation\t1 ☐\t2 ☐', (2880, 4320)),
                  ('Tenderness\t1 ☐\t2 ☐', (2880, 4320))]
        return data(stopped_form([[liver, ['If abnormal,', 'describe below']], [spleen, ['']]], (6480, 2880)))

    def rendered(self, shift_liver=100):
        """Liver's header shares its baseline with 'describe below'; Spleen prints alone and aligned."""
        def cell(y, title, extra, shift):
            return [(y, [(20, title)] + extra[:1]), (y - 20, [(200, 'Normal'), (300, 'Abnormal')] + extra[1:]),
                    (y - 40, [(20, 'Palpation'), (212 + shift, '1 '), (222 + shift, None), (322 + shift, '2 '), (332 + shift, None)]),
                    (y - 60, [(20, 'Tenderness'), (212 + shift, '1 '), (222 + shift, None), (322 + shift, '2 '), (332 + shift, None)])]
        return self.pdf.page(cell(360, '12b. Liver', [(420, 'If abnormal,'), (420, 'describe below')], shift_liver)
                             + cell(260, '12c. Spleen', [], 0))

    def test_an_identical_printed_sequence_in_another_cell_never_verifies_a_proposal(self):
        from .layout_geometry import containment
        raw = self.liver_and_spleen()
        proposal, _, _ = layout_source.prepare(raw)
        candidates = proposal['manifest']['candidates']
        self.assertEqual([c['source']['label'] for c in candidates], ['Palpation', 'Tenderness'] * 2)
        result = containment(self.rendered(), candidates)
        self.assertEqual([(m['candidate'], m['header']['y']) for m in result['measurements']], [])
        self.assertEqual(len(result['held']), 4)
        self.assertEqual([c['rendered_source']['source_occurrences'] for c in candidates], [2, 2, 2, 2])
        # Both rows answered 'Normal' (the common case): the export is refused, never verified from Spleen's lines.
        fields = [f for f in proposal['fields'] if f.get('layout_candidate') and f['label'] == 'Palpation']
        prepared, _, _ = layout_source.prepare(raw, mapping=proposal['fields'],
                                                answers={f['key']: 'Normal' for f in fields})
        with self.assertRaises(ValueError):
            containment(self.rendered(), prepared['manifest']['candidates'])

    def test_prepared_sequences_verify_an_aligned_rendering_and_refuse_a_shifted_one(self):
        from .layout_geometry import containment
        lungs = ['10.\tLungs', ('\tNormal\tAbnormal', (2880, 4320)), ('Percussion\t1 ☐\t2 ☐', (2880, 4320), 'dot'), '',
                 ('Auscultation\t1 ☐\t2 ☐', (2880, 4320))]
        summary = ['Lungs summary', '', ('\tNormal\tAbnormal\tExam not done', (2880, 4320, 5760)),
                   ('\t1 ☐\t2 ☐\t3 ☐', (2880, 4320, 5760)), '']
        raw = data(stopped_form([[lungs, ['']], [summary, ['']]], (6480, 2880)))
        proposal, _, _ = layout_source.prepare(raw)
        candidates = sorted(proposal['manifest']['candidates'], key=lambda c: c['source']['row']['slot'])
        self.assertEqual([c['source']['label'] for c in candidates], ['Percussion', 'Auscultation', 'Lungs summary'])
        # The coded sequences are optional proposals; the summary's single tab pair is a required one.
        self.assertEqual([c['optional'] for c in candidates], [True, True, False])
        self.assertEqual([c['rendered_source']['sequence'][i]['dot_leaders'] for c in candidates[:1] for i in (0, 1)],
                         [False, True])
        def lines(shift=0):
            box = lambda x, y, label, dots=False: (y, [(20, label)] + ([(90, '.....'), (180, '.....')] if dots else [])
                                                    + [(x, '1 '), (x + 10, None), (x + 100, '2 '), (x + 110, None)])
            return [(360, [(20, '10. Lungs')]), (340, [(200, 'Normal'), (300, 'Abnormal')]),
                    box(212 + shift, 320, 'Percussion', dots=True), box(212, 300, 'Auscultation'),
                    (260, [(20, 'Lungs summary')]), (240, [(150, 'Normal'), (230, 'Abnormal'), (310, 'Exam not done')]),
                    (220, [(162, '1 '), (172, None), (242, '2 '), (252, None), (342, '3 '), (352, None)])]
        result = containment(self.pdf.page(lines()), candidates)
        self.assertTrue(result['passed']); self.assertEqual(result['held'], [])
        self.assertEqual(len(result['measurements']), 7)
        self.assertEqual({(m['candidate'], m['header']['y'], m['row']['y']) for m in result['measurements']},
                         {(candidates[0]['id'], 340, 320), (candidates[1]['id'], 340, 300), (candidates[2]['id'], 240, 220)})
        shifted = containment(self.pdf.page(lines(shift=100)), candidates)
        self.assertEqual([h['candidate'] for h in shifted['held']], [candidates[0]['id'], candidates[1]['id']])

    def test_a_tab_column_proposal_is_required_and_its_failure_refuses_everything(self):
        from .layout_geometry import containment
        from .test_question_boxes import TabColumnOwnership
        raw = data(TabColumnOwnership().form(control='ff'))
        proposal, _, _ = layout_source.prepare(raw)
        [candidate] = proposal['manifest']['candidates']
        self.assertIs(candidate['optional'], False)
        with self.assertRaises(ValueError):
            containment(self.pdf.page([(300, [(20, 'Unrelated text')])]), [candidate])

    def test_the_occurrence_count_is_taken_from_the_export_that_is_rendered(self):
        # A typed answer elsewhere can print the proposal's own sequence a second time in the export.
        liver = ['12b.\tLiver', ('\tNormal\tAbnormal', (2880, 4320)), ('Palpation\t1 ☐\t2 ☐', (2880, 4320))]
        notes = ['Notes', ('\tNormal\tAbnormal', (2880, 4320)), 'Palpation ________']
        raw = data(stopped_form([[liver, ['']], [notes, ['']]], (6480, 2880), control='glyph'))
        proposal, _, _ = layout_source.prepare(raw)
        [candidate] = proposal['manifest']['candidates']
        self.assertEqual(candidate['rendered_source']['source_occurrences'], 1)
        typed = next(f for f in proposal['fields'] if f['label'] == 'Palpation' and not f.get('layout_candidate'))
        prepared, _, _ = layout_source.prepare(raw, mapping=proposal['fields'], answers={typed['key']: '1 ☐ 2 ☐'})
        self.assertEqual(prepared['manifest']['candidates'][0]['rendered_source']['source_occurrences'], 2)


class CodedSourceScope(unittest.TestCase):
    """Refutation 2026-09-28 A2-A5, B2, B4: what a coded source may and may not name."""

    def proposal(self, raw):
        proposal, _, _ = layout_source.prepare(raw)
        return [f for f in proposal['fields'] if f.get('layout_candidate')], proposal

    def test_a_code_before_each_box_is_a_coded_row_and_never_supplies_options(self):
        cases = {
            'trailing option text': ['4.\tThyroid', '\tNormal\tAbnormal\tNot done', 'Finding\t1 ☐\t2 ☐\t9 ☐ Other'],
            'space separated': ['4.\tThyroid', '\tNormal\tAbnormal\tNot done', 'Edema   1 ☐   2 ☐   3 ☐ Not examined'],
            'parenthesised codes': ['4.\tThyroid', '\tNormal\tAbnormal\tNot done', 'Finding\t(1) ☐\t(2) ☐\t(3) ☐'],
            'missing code': ['4.\tThyroid', '\tNormal\tAbnormal', 'Size\t1 ☐\t2 ☐', '', 'Shape\t☐\t2 ☐'],
            'duplicate code': ['4.\tThyroid', '\tNormal\tAbnormal', 'Size\t1 ☐\t2 ☐', '', 'Shape\t1 ☐\t1 ☐'],
            'number after the last box': ['4.\tThyroid', '\tNormal\tAbnormal\tNot done', 'Finding\t1 ☐\t2 ☐\t☐ 3'],
            'codes before worded boxes': ['4.\tThyroid', 'Result\t(1) ☐ Positive\t(2) ☐ Negative'],
        }
        for control in ('glyph', 'ff'):
            for name, cell in cases.items():
                with self.subTest(control=control, case=name):
                    raw = data(coded_form(cell, control=control))
                    result = w.inspect(raw)
                    boxes = [f for f in result['fields'] if f['locator']['target']['type'] == 'checkboxes']
                    self.assertEqual([(f['label'], f['options']) for f in boxes], [])
                    self.assertTrue(any('response codes are not option labels' in n for n in result['notes']))
        # Positive controls: numbers printed after their boxes are the options, and a question that ends in a
        # number keeps its own printed option words.
        for line, label, options in (('Pain\t☐ 0\t☐ 1\t☐ 2', 'Pain', ['0', '1', '2']),
                                     ('Over 65\t☐ Yes\t☐ No', 'Over 65', ['Yes', 'No'])):
            with self.subTest(line=line):
                doc = Document(); doc.add_table(rows=1, cols=1).cell(0, 0).text = line
                result = w.inspect(data(doc))
                self.assertEqual([(f['label'], f['options']) for f in result['fields'] if f.get('options')],
                                 [(label, options)])

    def test_a_row_question_printed_in_the_cell_to_its_left_is_never_replaced_by_the_cell_title(self):
        rows = []
        for question, options in (('Heart sounds', ['Normal', 'Abnormal']), ('Pericardial rub', ['Absent', 'Present']),
                                  ('Peripheral edema', ['None', 'Pitting', 'Non-pitting'])):
            stops = tuple(2160 + 1440 * i for i in range(len(options)))
            rows.append([[question], ['Findings', '', ('\t' + '\t'.join(options), stops),
                                      ('\t' + '\t'.join('%d ☐' % (i + 1) for i in range(len(options))), stops), '']])
        for offset in (0, 20):
            with self.subTest(offset=offset):
                if offset:  # rule_tab_columns refuses offset stops; the coded rule reads the same cells
                    for row in rows:
                        line = row[1][3]; row[1][3] = (line[0], tuple(p + offset for p in line[1]))
                detector, _, _ = detect(data(stopped_form(rows, (2880, 6480))))
                areas = [a for _, _, a in detector.layout_candidates]
                # The question printed in the row's own label cell names it; the cell title is context.
                self.assertEqual([a.label for a in areas], ['Heart sounds', 'Pericardial rub', 'Peripheral edema'])
                self.assertTrue(all('Findings' in a.context for a in areas))
        # A cell to the right (fixed details, comments) is not the row's question: the title still names it.
        raw = data(stopped_form([[['Head summary', '', ('\tNormal\tAbnormal', (2880, 4320)), ('\t1 ☐\t2 ☐', (2880, 4320))],
                                  ['Fixed details']]], (6480, 2880)))
        detector, _, _ = detect(raw)
        self.assertEqual([a.label for _, _, a in detector.layout_candidates], ['Head summary'])

    def test_the_row_question_printed_to_the_left_stays_with_labelled_rows_and_numbers_are_not_questions(self):
        stops = (2880, 4320)
        carotid = ['Findings', ('\tAbsent\tPresent', stops), ('Left\t1 ☐\t2 ☐', stops), '', ('Right\t1 ☐\t2 ☐', stops)]
        detector, _, _ = detect(data(stopped_form([[['Carotid bruit'], carotid]], (2880, 6480))))
        areas = [a for _, _, a in detector.layout_candidates]
        self.assertEqual([a.label for a in areas], ['Left', 'Right'])
        self.assertTrue(all('Carotid bruit' in a.context for a in areas))
        # The same for one labelled tab pair, which rule_tab_columns owns.
        detector, _, _ = detect(data(stopped_form([[['Carotid bruit'], carotid[:3]]], (2880, 6480))))
        self.assertEqual([(a.label, 'column_sequence' in a.target, 'Carotid bruit' in a.context)
                          for _, _, a in detector.layout_candidates], [('Left', False, True)])
        # A left cell that prints only an item number is not the row's question, and is not ignored either.
        lone = ['Findings', '', ('\tNormal\tAbnormal', stops), ('\t1 ☐\t2 ☐', stops)]
        for offset, number in ((0, '12.'), (20, '12.'), (0, '(12)'), (20, '(12)')):
            with self.subTest(offset=offset, number=number):
                cell = lone[:3] + [(lone[3][0], tuple(p + offset for p in stops))]
                detector, _, notes = detect(data(stopped_form([[[number], cell]], (1440, 7920))))
                self.assertEqual(detector.layout_candidates, [])
                self.assertTrue(any('not a usable row label' in n for n in notes))

    def test_a_sub_heading_or_group_label_over_several_rows_is_never_scoped_to_one(self):
        pulses = ['13.\tPulses', '\tPresent\tAbsent', 'Right side', 'Radial\t1 ☐\t2 ☐', 'Femoral\t1 ☐\t2 ☐', '',
                  'Left side', 'Radial\t1 ☐\t2 ☐', 'Dorsalis pedis\t1 ☐\t2 ☐']
        asymmetric = ['13.\tPulses', '\tPresent\tAbsent', 'Right side', 'Radial\t1 ☐\t2 ☐', 'Femoral\t1 ☐\t2 ☐', '',
                      'Left side', 'Dorsalis pedis\t1 ☐\t2 ☐', 'Posterior tibial\t1 ☐\t2 ☐']
        carotid = ['11.\tArteries', '\tNormal\tAbnormal', 'Heart palpation\t1 ☐\t2 ☐', '', 'Carotid artery',
                   'Auscultation\tAbsent\tPresent', '(systolic bruit)', 'Left\t1 ☐\t2 ☐', 'Right\t1 ☐\t2 ☐']
        grouped = ['13.\tPulses', 'Right\tPresent\tAbsent', 'Radial\t1 ☐\t2 ☐', 'Femoral\t1 ☐\t2 ☐', '',
                   'Left\tPresent\tAbsent', 'Dorsalis pedis\t1 ☐\t2 ☐', 'Posterior tibial\t1 ☐\t2 ☐']
        for name, cell in (('sub-headings', pulses), ('asymmetric sub-headings', asymmetric),
                           ('lead over two rows', carotid), ('group labels in one cell', grouped)):
            with self.subTest(name):
                _, coded, notes = detect(data(coded_form(cell)))
                self.assertEqual([a.label for a in coded], [])
                self.assertTrue(any(n.startswith('Coded column sequence at ') for n in notes))

    def test_a_single_row_is_named_by_its_lead_prefix_and_text_above_in_printed_order(self):
        cell = ['11.\tArteries', '\tNormal\tAbnormal', 'Heart palpation\t1 ☐\t2 ☐', '', 'Carotid artery',
                'Auscultation\tAbsent\tPresent', '(systolic bruit)', 'Left\t1 ☐\t2 ☐']
        _, coded, _ = detect(data(coded_form(cell)))
        self.assertEqual([a.label for a in coded], ['Heart palpation', 'Carotid artery Auscultation (systolic bruit) Left'])

    def test_a_single_group_label_is_context_for_all_its_rows_or_none(self):
        fields, _ = self.proposal(data(coded_form(LYMPH)))
        self.assertEqual([f['label'] for f in fields], ['Posterior', 'Anterior', 'Axillary'])
        self.assertTrue(all('Cervical' in f['context'] for f in fields))

    def test_a_coded_row_records_one_response_whatever_its_label_or_section_says(self):
        skin = ['15.\tSkin', '\tAbsent\tPresent', 'Lesion(s)\t1 ☐\t2 ☐', '', 'Rash\t1 ☐\t2 ☐']
        fields, _ = self.proposal(data(coded_form(skin)))
        self.assertEqual([(f['label'], f['kind']) for f in fields], [('Lesion(s)', 'choice'), ('Rash', 'choice')])
        single = ['15.\tSkin', ('\tAbsent\tPresent', (2880, 4320)), ('Lesion(s)\t1 ☐\t2 ☐', (2880, 4320))]
        fields, _ = self.proposal(data(stopped_form([[single, ['']]], (6480, 2880))))
        self.assertEqual([(f['label'], f['kind']) for f in fields], [('Lesion(s)', 'choice')])
        # A check-all instruction over coded single-response rows is a conflict: noted, never multi-choice.
        _, coded, notes = detect(data(coded_form(skin, heading='Findings (check all that apply)')))
        self.assertEqual([a.label for a in coded], [])
        self.assertTrue(any(n.startswith('Coded column sequence at ') for n in notes))

    def test_a_single_labelled_row_refused_by_the_tab_pair_contract_is_read_as_a_coded_sequence(self):
        for cell, label, options in ((['12b.\tLiver', '', '\tNo\tYes', 'Palpable\t1 ☐\t2 ☐', ''], 'Palpable', ['No', 'Yes']),
                                     (['9.\tChest', '', '\tNormal\tAbnormal', 'Shape\t\t1 ☐\t2 ☐', '', ''], 'Shape',
                                      ['Normal', 'Abnormal']),
                                     (['7.\tNose', '\tNormal\tAbnormal', 'Nasal mucosa\t1 ☐\t2 ☐', '', ''], 'Nasal mucosa',
                                      ['Normal', 'Abnormal'])):
            with self.subTest(label):
                raw = data(coded_form(cell))
                fields, proposal = self.proposal(raw)
                self.assertEqual([(f['label'], f['options']) for f in fields], [(label, options)])
                # Its title and spacers are claimed: nothing inside the coded cell is a free-text destination.
                self.assertFalse([f for f in proposal['fields'] if '/tc[0]' in f['locator']['slot']
                                  and f['locator']['target']['type'] != 'checkboxes'])
                self.assertFalse([n for n in proposal['warnings'] if n.startswith('Tab-column options at ')])


class WholeFormDestinations(unittest.TestCase):
    """Refutation 2026-09-28 B1 and B3 (pre-existing on D10): a destination is named by its own printed header."""

    def vitals(self):
        doc = Document(); doc.add_paragraph('Section 1: Vital Measurements', style='Heading 1')
        table = doc.add_table(rows=2, cols=3)
        for col, text in enumerate(('Blood pressure (mmHg)', 'Heart Rate', 'Respiratory Rate')):
            table.cell(0, col).text = text
        for col, (boxes, unit) in enumerate((('▯▯▯/▯▯▯', '\tSystolic\tdiastolic'), ('▯▯▯', 'beats/min'),
                                              ('▯▯▯', 'breaths/min'))):
            table.cell(1, col).text = boxes; table.cell(1, col).add_paragraph(unit)
        return data(doc)

    def test_a_value_cell_is_named_by_its_column_header_never_by_the_answer_cell_to_its_left(self):
        raw = self.vitals()
        fields = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}
        rate, breaths = fields['b/tbl[0]/tr[1]/tc[1]/p[0]'], fields['b/tbl[0]/tr[1]/tc[2]/p[0]']
        self.assertEqual((rate['label'], breaths['label']), ('Heart Rate', 'Respiratory Rate'))
        self.assertIn('Heart Rate', rate['context']); self.assertIn('Respiratory Rate', breaths['context'])
        # A value routed by its label reaches the column that prints that label.
        out = w.fill(raw, list(fields.values()), {rate['key']: '072', breaths['key']: '16'})
        index = w.SlotIndex(w.open_package(out))
        self.assertIn('072', w.text_of(index.by_id['word/document.xml#b/tbl[0]/tr[1]/tc[1]'].el))
        self.assertIn('16', w.text_of(index.by_id['word/document.xml#b/tbl[0]/tr[1]/tc[2]'].el))
        # A column without a printed header keeps the value cell beside it as context and label source.
        doc = Document(); table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = 'Weight ▯▯▯ kg'; table.cell(0, 1).text = '▯▯▯'
        [left, right] = [f for f in w.inspect(data(doc))['fields']]
        self.assertEqual((left['label'], right['label']), ('Weight', 'Weight ▯▯▯ kg'))
        # Leader dots after a printed question are not an answer blank: that question still names the value.
        doc = Document(); table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = 'Measure'; table.cell(0, 1).text = 'Value'
        table.cell(1, 0).text = 'Heart rate ..........'; table.cell(1, 1).text = '▯▯▯'
        [value] = [f for f in w.inspect(data(doc))['fields'] if f['locator']['slot'].startswith('b/tbl[0]/tr[1]/tc[1]')]
        self.assertTrue(value['label'].startswith('Heart rate'))

    def test_only_an_instruction_in_a_data_row_is_an_append_destination(self):
        doc = Document(); table = doc.add_table(rows=3, cols=3)
        for r, cells in enumerate((('Item', 'Dose', 'Notes'), ('Section A', 'Printed dose', 'Describe any findings below'),
                                   ('Aspirin', '81 mg', ''))):
            for c, text in enumerate(cells):
                table.cell(r, c).text = text
        fields = {f['locator']['slot']: f for f in w.inspect(data(doc))['fields']}
        self.assertNotIn('b/tbl[0]/tr[1]/tc[2]', fields)  # an instruction in a label row, not an answer cell
        self.assertNotIn('b/tbl[0]/tr[2]/tc[1]', fields)  # printed content, not an instruction
        self.assertEqual(fields['b/tbl[0]/tr[2]/tc[2]']['locator']['target']['type'], 'cell')

    def test_an_instruction_in_an_answer_column_belongs_to_its_own_row_never_the_next(self):
        doc = coded_form(['12b.\tLiver', '', '\tNo\tYes', 'Palpable\t1 ☐\t2 ☐', ''], SUMMARY, marked='Physical examination')
        doc.tables[0].cell(0, 1).add_paragraph('If abnormal, explain or describe below')
        instruction = 'If palpable, describe here'
        doc.tables[0].cell(1, 1).text = instruction
        raw = data(doc)
        fields = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}
        self.assertNotIn(instruction, fields['b/tbl[0]/tr[2]/tc[1]']['label'])
        self.assertNotIn(instruction, fields['b/tbl[0]/tr[2]/tc[1]']['context'])
        own = fields['b/tbl[0]/tr[1]/tc[1]']
        self.assertEqual((own['kind'], own['locator']['target']['type']), ('long_text', 'cell_append'))
        self.assertEqual([s['text'] for s in own['source_instructions']], [instruction])
        answer = 'Liver edge palpable 2 cm below the costal margin.'
        proposal, _, _ = layout_source.prepare(raw)  # the form also carries coded proposals: export through layout
        own = next(f for f in proposal['fields'] if f['locator']['slot'] == 'b/tbl[0]/tr[1]/tc[1]')
        _, out, _ = layout_source.prepare(raw, mapping=proposal['fields'], answers={own['key']: answer})
        cell = w.SlotIndex(w.open_package(out)).by_id['word/document.xml#b/tbl[0]/tr[1]/tc[1]'].el
        self.assertEqual([w.text_of(p) for p in cell.findall(w.q('w:p'))], [instruction, answer])


# ─── Refutation 2026-09-28, third round (F1-F10) ────────────────────────────────────────────────────────────────────


def drawn(pdf, lines, before=b'', after=b''):
    """A synthetic page in the pinned profile's embedded fixture font, painted in the order given.
    lines: [(y, [(x, text) | (x, None) for a native checkbox | (x, True) for a ticked one])]."""
    import io
    from pypdf import PdfReader
    from pypdf.generic import DecodedStreamObject, NameObject
    reader = PdfReader(io.BytesIO(pdf.fixture)); page = reader.pages[0]
    font = next(name for name, ref in page['/Resources']['/Font'].items() if ref.get_object().get('/Subtype') == '/TrueType')
    stream = b'.1 w\n' + before
    for y, items in lines:
        for x, text in items:
            if text is None or text is True:
                stream += f'0 0 0 RG {x} {y - 2} 10 10 re S\n'.encode()
                if text is True:
                    stream += f'{x} {y + 8} m {x + 10} {y - 2} l S {x + 10} {y + 8} m {x} {y - 2} l S\n'.encode()
            else:
                stream += f'q 0 0 0 rg BT {x} {y} Td {font} 11 Tf <{text.encode().hex()}> Tj ET Q\n'.encode()
    content = DecodedStreamObject(); content.set_data(stream + after); page[NameObject('/Contents')] = content
    return reader.pages


class PaintedFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .test_layout_containment import SequenceContainment
        cls.pdf = SequenceContainment('test_fixture_font_keeps_literal_character_codes')
        SequenceContainment.setUpClass()


class NeverPrintedCharacters(PaintedFixture):
    """F1: two places that print the same thing count as two, whatever the source holds that never prints."""

    def form(self, spleen_header='\tNormal\tAbnormal', *, hidden=False, liver_header='\tNormal\tAbnormal', caps=False,
             styled=False):
        from docx.oxml import OxmlElement
        from docx.enum.style import WD_STYLE_TYPE
        liver = ['12b.\tLiver', (liver_header, (2880, 4320)), ('Palpation\t1 ☐\t2 ☐', (4320, 5760)),
                 ('Tenderness\t1 ☐\t2 ☐', (4320, 5760))]
        spleen = ['12c.\tSpleen', (spleen_header, (2880, 4320)), ('Palpation\t1 ☐\t2 ☐', (2880, 4320)),
                  ('Tenderness\t1 ☐\t2 ☐', (2880, 4320))]
        doc = stopped_form([[liver, ['If abnormal,', 'describe below']], [spleen, ['']]], (6480, 2880))
        header = doc.tables[0].cell(1, 0).paragraphs[1]
        if hidden:
            run = header.add_run('X'); run._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
        if styled:  # hidden by its character style, not by its own properties
            style = doc.styles.add_style('Unprinted', WD_STYLE_TYPE.CHARACTER); style.font.hidden = True
            header.add_run('X', style='Unprinted')
        if caps:
            for run in header.runs:
                run._r.get_or_add_rPr().append(OxmlElement('w:caps'))
        return data(doc)

    def test_characters_that_never_print_do_not_make_a_repeated_place_unique(self):
        for name, raw in (('soft hyphen', self.form('\tNor­mal\tAbnormal')),
                          ('zero width space', self.form('\tNor​mal\tAbnormal')),
                          ('word joiner', self.form('\tNor⁠mal\tAbnormal')),
                          ('hidden run', self.form(hidden=True)),
                          ('hidden by style', self.form(styled=True)),
                          ('capitals by formatting', self.form('\tnormal\tabnormal', liver_header='\tNORMAL\tABNORMAL', caps=True))):
            with self.subTest(name):
                proposal, _, _ = layout_source.prepare(raw)
                candidates = proposal['manifest']['candidates']
                liver = [c for c in candidates if c['source']['row']['slot'].startswith('b/tbl[0]/tr[0]/')]
                self.assertEqual(len(liver), 2)
                self.assertEqual({c['rendered_source']['source_occurrences'] for c in candidates}, {2})

    def cell(self, y, title, shift, *, wrap=False):
        """One coded cell, painted as the renderer paints a cell: title, header, rows, in order."""
        header = [(y - 20, [(200, 'Normal'), (300, 'Abnormal')])] if not wrap else \
            [(y - 20, [(200, 'Normal')]), (y - 30, [(200, 'Abnormal')])]
        rows = [(y - 45 - 20 * n, [(20, label), (212 + shift, '1 '), (222 + shift, None), (322 + shift, '2 '), (332 + shift, None)])
                for n, label in enumerate(('Palpation', 'Tenderness'))]
        return [(y, [(20, title)])] + header + rows

    def test_a_place_rendered_twice_is_never_measured_on_the_other_place(self):
        from .layout_geometry import containment
        proposal, _, _ = layout_source.prepare(self.form())
        candidates = proposal['manifest']['candidates']
        for candidate in candidates:  # what an undercounting source key reports
            candidate['rendered_source']['source_occurrences'] = 1
        liver = {c['id'] for c in candidates if c['source']['row']['slot'].startswith('b/tbl[0]/tr[0]/')}
        # Liver prints its boxes one column right. Its neighbour cell prints on Liver's title and header
        # baselines, painted after Liver's cell; or Liver's header wraps. Spleen prints the same text, aligned.
        neighbour = self.cell(400, '12b. Liver', 100) + [(400, [(420, 'If abnormal,')]), (380, [(420, 'describe below')])]
        wrapped = self.cell(400, '12b. Liver', 100, wrap=True)
        for name, liver_lines in (('neighbour on its baselines', neighbour), ('wrapped header', wrapped)):
            with self.subTest(name):
                pages = drawn(self.pdf, liver_lines + self.cell(250, '12c. Spleen', 0))
                result = containment(pages, candidates)
                self.assertFalse([m for m in result['measurements'] if m['candidate'] in liver])
                self.assertTrue(liver <= {h['candidate'] for h in result['held']})
                answered = [dict(c, untouched=False) if c['id'] in liver else c for c in candidates]
                with self.assertRaises(ValueError):
                    containment(pages, answered)


class RenderedOnAnotherPage(PaintedFixture):
    """F1: the rendered repeat is looked for on every page, not only on the matched one."""

    def test_the_same_text_painted_on_another_page_is_a_second_place(self):
        from .layout_geometry import containment
        glyph = lambda text: [{'kind': 'glyph', 'text': text}]
        header = [[], glyph('Normal'), glyph('Abnormal')]
        row = [glyph('Palpation')] + [glyph(str(i + 1) + ' ') + [{'kind': 'ff_checkbox', 'text': '\ufffc', 'checked': False}]
                                      for i in range(2)]
        candidate = {'id': 'c', 'source': {'options': ['Normal', 'Abnormal']}, 'rendered_source': {
            'header': header, 'row': row, 'row_dot_leaders': False, 'source_occurrences': 1}}
        lines = [(300, [(200, 'Normal'), (300, 'Abnormal')]),
                 (280, [(20, 'Palpation'), (212, '1 '), (222, None), (312, '2 '), (322, None)])]
        own = drawn(self.pdf, lines)
        self.assertTrue(containment([own[0]], [candidate])['passed'])
        # The second page paints the same characters in the same order (so with the same paint positions);
        # a word after them keeps its header line from matching whole.
        other = drawn(self.pdf, lines + [(300, [(380, 'Findings')])])
        with self.assertRaises(ValueError):
            containment([own[0], other[0]], [candidate])


class RowQuestionCells(unittest.TestCase):
    """F2: only a plain question cell of the same row names a coded row."""

    def test_a_merged_group_cell_is_context_and_each_row_keeps_its_own_title(self):
        for control in ('glyph', 'ff'):
            with self.subTest(control=control):
                rows = [[['Abdomen'], ['Liver summary', '', ('\tNormal\tEnlarged', (1440, 2880)), ('\t1 ☐\t2 ☐', (1440, 2880))]],
                        [[''], ['Spleen summary', '', ('\tNormal\tEnlarged\tNot felt', (1440, 2880, 4320)),
                                ('\t1 ☐\t2 ☐\t3 ☐', (1440, 2880, 4320))]]]
                doc = stopped_form(rows, (2880, 6480), control=control)
                doc.tables[0].cell(0, 0).merge(doc.tables[0].cell(1, 0))
                detector, _, _ = detect(data(doc))
                areas = [a for _, _, a in detector.layout_candidates]
                self.assertEqual([(a.label, a.options) for a in areas],
                                 [('Liver summary', ['Normal', 'Enlarged']), ('Spleen summary', ['Normal', 'Enlarged', 'Not felt'])])
                self.assertTrue(all('Abdomen' in a.context for a in areas))

    def test_a_cell_holding_its_own_answer_is_never_the_row_question(self):
        murmur = ['Murmur', '', ('\tAbsent\tPresent', (1440, 2880)), ('\t1 ☐\t2 ☐', (1440, 2880))]
        for text, control in (('Referred to cardiology ☐', 'ff'), ('Referred to cardiology ☐', 'glyph'),
                              ('Date examined: ____________', 'glyph'), ('Temperature ▯▯.▯ °C', 'glyph')):
            with self.subTest(text=text, control=control):
                detector, _, notes = detect(data(stopped_form([[[text], murmur]], (2880, 6480), control=control)))
                self.assertEqual([a.label for _, _, a in detector.layout_candidates], [])
                self.assertTrue(any('holds its own answer' in n for n in notes))
        # A plain question to the left still names the row.
        detector, _, _ = detect(data(stopped_form([[['Heart'], murmur]], (2880, 6480), control='glyph')))
        self.assertEqual([a.label for _, _, a in detector.layout_candidates], ['Heart'])


class WordsAndCodesBeforeBoxes(unittest.TestCase):
    """F3: a code or word printed before each box never becomes the next box's option."""

    def test_a_code_printed_before_every_box_in_any_form_is_noted(self):
        rows = ['Finding\t1 - ☐\t2 - ☐\t3 - ☐ Other', 'Finding\t#1 ☐\t#2 ☐\t#3 ☐ Other', 'Finding\ta) ☐\tb) ☐\tc) ☐ Other',
                'Finding\ta ☐\tb ☐\tc ☐ Other', 'Finding\tI ☐\tII ☐\tIII ☐ Other', 'Finding\t1a ☐\t1b ☐\t1c ☐ Other',
                'Finding\t1= ☐\t2= ☐\t3= ☐ Other', 'Finding\t1: ☐\t2: ☐\t3: ☐ Other']
        for control in ('glyph', 'ff'):
            for row in rows:
                with self.subTest(control=control, row=row):
                    result = w.inspect(data(coded_form(['4.\tThyroid', '\tNormal\tAbnormal\tNot done', row], control=control)))
                    self.assertEqual([f['label'] for f in result['fields'] if f['locator']['target']['type'] == 'checkboxes'], [])
                    self.assertTrue(any('response codes are not option labels' in n for n in result['notes']))

    def test_words_printed_before_their_boxes_are_noted_and_never_shifted_onto_the_next_box(self):
        for control in ('glyph', 'ff'):
            for line in ('Smoker: Yes ☐ No ☐', 'Enlarged: Y ☐ N ☐ Unknown ☐', 'Smoker ☐   Diabetic ☐'):
                with self.subTest(control=control, line=line):
                    result = w.inspect(data(coded_form([line], control=control, heading=None)))
                    self.assertEqual([f['label'] for f in result['fields'] if f['locator']['target']['type'] == 'checkboxes'], [])
                    self.assertTrue(any('printed before' in n or 'response codes are not option labels' in n
                                        for n in result['notes']))
        # Positive controls: words and numbers printed after their boxes stay those boxes' options.
        for line, label, options in (('Grade: ☐ A ☐ B ☐ C', 'Grade', ['A', 'B', 'C']),
                                     ('Smoker? ☐ Yes ☐ No', 'Smoker?', ['Yes', 'No']),
                                     ('Stage ☐ I ☐ II ☐ III', 'Stage', ['I', 'II', 'III']),
                                     ('Is this a ☐ new ☐ follow-up visit', 'Is this a', ['new', 'follow-up visit']),
                                     ('Pain\t☐ 0\t☐ 1\t☐ 2', 'Pain', ['0', '1', '2']),
                                     ('☐ a ☐ b ☐ c', 'Choose', ['a', 'b', 'c'])):
            for control in ('glyph', 'ff'):
                with self.subTest(control=control, line=line):
                    result = w.inspect(data(coded_form([line], control=control, heading=None)))
                    self.assertEqual([(f['label'], f['options']) for f in result['fields']
                                      if f['locator']['target']['type'] == 'checkboxes'], [(label, options)])


class HeaderLegendCodes(unittest.TestCase):
    """F4: a printed header whose codes disagree with the row's codes is ambiguous."""

    def test_a_legend_whose_codes_contradict_the_row_codes_is_noted(self):
        legend = ('\t2 = Abnormal\t1 = Normal', (2880, 4320))
        for name, cell in (('two rows', ['12b.\tLiver', legend, ('Palpable\t1 ☐\t2 ☐', (2880, 4320)), '',
                                         ('Tender\t1 ☐\t2 ☐', (2880, 4320))]),
                           ('one tab pair', ['12b.\tLiver', legend, ('Palpable\t1 ☐\t2 ☐', (2880, 4320))])):
            with self.subTest(name):
                detector, _, notes = detect(data(stopped_form([[cell, ['']]], (6480, 2880))))
                self.assertEqual(detector.layout_candidates, [])
                self.assertTrue(any('codes' in n and ('Coded column sequence at ' in n or 'Tab-column options at ' in n)
                                    for n in notes))
        # A legend whose codes agree with the rows keeps its printed words as the options.
        agreeing = ['12b.\tLiver', ('\t1 = Normal\t2 = Abnormal', (2880, 4320)), ('Palpable\t1 ☐\t2 ☐', (2880, 4320)), '',
                    ('Tender\t1 ☐\t2 ☐', (2880, 4320))]
        detector, _, _ = detect(data(stopped_form([[agreeing, ['']]], (6480, 2880))))
        self.assertEqual([(a.label, a.options) for _, _, a in detector.layout_candidates],
                         [('Palpable', ['1 = Normal', '2 = Abnormal']), ('Tender', ['1 = Normal', '2 = Abnormal'])])


def table_doc(*tables):
    doc = Document()
    for rows in tables:
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        for r, cells in enumerate(rows):
            for c, text in enumerate(cells):
                table.cell(r, c).text = text
        doc.add_paragraph('')
    return data(doc)


class ValueRowsAreNotHeaders(unittest.TestCase):
    """F5 and F8: a row that prints answer places is never a column header for the rows below it."""

    def test_a_row_of_value_cells_never_names_the_values_below_it(self):
        raw = table_doc([('Medication', 'Dose (mg)'), ('Aspirin', '▯▯▯'), ('Other: ______________', '▯▯▯'),
                         ('Other: ______________', '▯▯▯')],
                        [('Level', 'Left (cm)', 'Right (cm)'), ('Calf at ____ cm below patella', '▯▯▯', '▯▯▯'),
                         ('Thigh at ____ cm above patella', '▯▯▯', '▯▯▯')])
        fields = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}
        for slot in ('b/tbl[0]/tr[2]/tc[1]/p[0]', 'b/tbl[0]/tr[3]/tc[1]/p[0]'):
            self.assertNotIn('▯', fields[slot]['label'])
            self.assertIn('Dose (mg)', fields[slot]['label'] + ' ' + fields[slot]['context'])
        for row in (1, 2):
            left, right = fields['b/tbl[1]/tr[%d]/tc[1]/p[0]' % row], fields['b/tbl[1]/tr[%d]/tc[2]/p[0]' % row]
            self.assertNotIn('▯', left['label'] + right['label'])
            self.assertIn('Left (cm)', left['label'] + ' ' + left['context'])
            self.assertIn('Right (cm)', right['label'] + ' ' + right['context'])
            self.assertNotIn('Right (cm)', left['label'] + ' ' + left['context'])
            self.assertNotIn('Left (cm)', right['label'] + ' ' + right['context'])

    def test_a_header_that_prints_a_blank_beside_its_words_is_still_a_header(self):
        raw = table_doc([('Criteria', 'Participant #_______', 'Participant #_______'), ('Met all inclusion criteria', '', '')])
        fields = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}
        for col in (1, 2):
            self.assertIn('Participant #', fields['b/tbl[0]/tr[1]/tc[%d]' % col]['label'])

    def test_a_row_of_inline_answer_gaps_is_not_the_header_of_the_items_below(self):
        from .test_word_v3 import ff_field
        doc = Document(); cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.paragraphs[0].add_run('Optional items').bold = True  # a printed sub-heading, as on the development form
        inner = cell.add_table(rows=3, cols=1)
        inner.cell(0, 0).text = '5. Number of completed sessions:        6. Average duration of sessions:    minutes'
        for r, (question, options) in enumerate((('7. Provider type:', ('Speech therapist', 'Physical therapist')),
                                                 ('8. Format:', ('Individual', 'Group'))), 1):
            paragraph = inner.cell(r, 0).paragraphs[0]; paragraph.add_run(question + '  ')
            for n, option in enumerate(options):
                ff_field(paragraph, 'checkbox', name='I%d_%d' % (r, n)); paragraph.add_run(' ' + option + '    ')
        fields = [f for f in w.inspect(data(doc))['fields'] if f['kind'] in ('choice', 'multi_choice')]
        self.assertEqual([f['label'] for f in fields], ['Provider type', 'Format'])
        for field in fields:
            self.assertIn('Optional items', field['context'])
            self.assertNotIn('completed sessions', field['context'])


class PrintedContentIsNotAnInstruction(unittest.TestCase):
    """F6 (and the guards F9 found untested): only an explicit request to write in a cell makes it a destination."""

    def test_printed_notes_doses_and_explanations_are_not_answer_destinations(self):
        raw = table_doc([('Medication', 'Dose', 'Instructions', 'Given (initials)'),
                         ('Warfarin', '5 mg', 'Note: INR must be checked before each dose', '')],
                        [('Topic', 'Printed explanation', 'Patient initials'), ('Risks', 'Detail: bleeding, infection, nerve injury', '')])
        fields = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}
        self.assertNotIn('b/tbl[0]/tr[1]/tc[2]', fields)
        self.assertNotIn('b/tbl[1]/tr[1]/tc[1]', fields)
        self.assertFalse([f for f in fields.values() if f.get('source_instructions')])

    def test_an_instruction_is_a_destination_only_in_a_plain_cell_under_a_printed_column_header(self):
        instruction = 'If palpable, describe here'
        # No printed column header over the instruction: it is printed text, not a place to answer.
        raw = table_doc([('Liver', instruction, '')])
        self.assertNotIn('b/tbl[0]/tr[0]/tc[1]', {f['locator']['slot'] for f in w.inspect(raw)['fields']})
        # A cell holding more than the instruction (three printed paragraphs) is not plain.
        doc = Document(); table = doc.add_table(rows=2, cols=3)
        for c, text in enumerate(('Organ', 'Findings', 'Initials')):
            table.cell(0, c).text = text
        table.cell(1, 0).text = 'Liver'
        table.cell(1, 1).text = instruction
        table.cell(1, 1).add_paragraph('(size, edge, consistency)'); table.cell(1, 1).add_paragraph('and tenderness')
        self.assertNotIn('b/tbl[0]/tr[1]/tc[1]', {f['locator']['slot'] for f in w.inspect(data(doc))['fields']})
        # Positive control: the same instruction alone, under a header, beside the row's label.
        doc = Document(); table = doc.add_table(rows=2, cols=3)
        for c, text in enumerate(('Organ', 'Findings', 'Initials')):
            table.cell(0, c).text = text
        table.cell(1, 0).text = 'Liver'; table.cell(1, 1).text = instruction
        own = {f['locator']['slot']: f for f in w.inspect(data(doc))['fields']}['b/tbl[0]/tr[1]/tc[1]']
        self.assertEqual(own['locator']['target']['type'], 'cell_append')
        # A request for what to write (the development form's 'Note if ... present.') is one too; printed
        # content that merely starts with the same verb is not.
        for text, destination in (('Note if supraclavicular fullness present.', True), ('Describe any findings', True),
                                  ('Note INR must be checked before each dose', False),
                                  ('Detail: bleeding below the knee', False),
                                  ('Explain the procedure to the patient', False)):
            with self.subTest(text=text):
                table.cell(1, 1).text = text
                fields = {f['locator']['slot']: f for f in w.inspect(data(doc))['fields']}
                self.assertEqual('b/tbl[0]/tr[1]/tc[1]' in fields, destination)


class NeighbourTextOnTheSameBaseline(PaintedFixture):
    """F7: a comment written beside an answered coded row shares its baselines; the row is measured on its own ink."""

    def prepared(self, stops=True):
        summary = ['Head summary', '', ('\tNormal\tAbnormal\tExam not done', (2880, 4320, 5760)),
                   ('\t1 ☐\t2 ☐\t3 ☐', (2880, 4320, 5760)), '']
        if not stops:
            summary = [line if isinstance(line, str) else line[0] for line in summary]
        raw = data(stopped_form([[summary, ['']]], (6480, 2880)))
        proposal, _, _ = layout_source.prepare(raw)
        head = next(f for f in proposal['fields'] if f.get('layout_candidate'))
        comment = next(f for f in proposal['fields'] if f['locator']['slot'].startswith('b/tbl[0]/tr[0]/tc[1]'))
        answers = {head['key']: 'Abnormal', comment['key']: 'Scalp laceration 2 cm, sutured.'}
        prepared, _, _ = layout_source.prepare(raw, mapping=proposal['fields'], answers=answers)
        [candidate] = prepared['manifest']['candidates']
        self.assertIs(candidate['untouched'], False)
        return candidate

    cell = [(300, [(20, 'Head summary')]), (280, [(150, 'Normal'), (230, 'Abnormal'), (310, 'Exam not done')]),
            (260, [(162, '1 '), (172, None), (242, '2 '), (252, True), (342, '3 '), (352, None)])]

    def test_an_answered_row_is_measured_on_its_own_ink_beside_its_comment(self):
        from .layout_geometry import containment
        candidate = self.prepared()
        comment = [(300, [(420, 'Scalp laceration 2')]), (280, [(420, 'cm, sutured.')])]
        result = containment(drawn(self.pdf, self.cell + comment), [candidate])
        self.assertTrue(result['passed']); self.assertEqual(result['held'], [])
        self.assertEqual({(m['header']['y'], m['row']['y']) for m in result['measurements']}, {(280, 260)})
        self.assertEqual(len(result['measurements']), 3)

    def test_a_wrapped_comment_line_between_the_rows_lines_is_the_neighbours_own(self):
        from .layout_geometry import containment
        candidate = self.prepared(stops=False)  # a coded sequence: title, header and row
        self.assertEqual(candidate['rendered_source']['header_index'], 1)
        title, header, row = self.cell
        # The comment's second line falls on the baseline of the cell's blank spacer paragraph. The renderer
        # paints the comment cell after the coded cell.
        lines = [title, (270, header[1]), (250, row[1]), (300, [(420, 'Scalp laceration 2')]), (290, [(420, 'cm, sutured.')])]
        result = containment(drawn(self.pdf, lines), [candidate])
        self.assertTrue(result['passed']); self.assertEqual(len(result['measurements']), 3)
        # Not the row's text, left of the row's ink, or over it: refused.
        for stray in ((290, [(420, 'Unrelated words')]), (290, [(5, 'sutured.')]), (290, [(170, 'sutured.')])):
            with self.subTest(stray=stray), self.assertRaises(ValueError):
                containment(drawn(self.pdf, [title, (270, header[1]), (250, row[1]), stray]), [candidate])

    def test_a_comment_line_of_its_own_above_the_first_line_is_not_a_second_reading(self):
        from .layout_geometry import containment
        candidate = self.prepared()
        title, header, row = self.cell
        lines = [title, header, row, (290, [(420, 'Scalp laceration 2 cm, sutured.')])]
        result = containment(drawn(self.pdf, lines), [candidate])
        self.assertTrue(result['passed']); self.assertEqual(len(result['measurements']), 3)

    def test_a_box_whose_height_spans_a_comment_baseline_belongs_to_the_line_printed_beside_it(self):
        from .layout_geometry import containment
        candidate = self.prepared()
        title, header, row = self.cell
        # The comment's line sits 1.1 pt above (or 1 pt below) the answer row's baseline, inside the boxes' height.
        for y in (261.1, 259):
            with self.subTest(y=y):
                result = containment(drawn(self.pdf, [title, header, row, (y, [(420, 'Scalp laceration 2')])]), [candidate])
                self.assertTrue(result['passed']); self.assertEqual(len(result['measurements']), 3)
        # With the comment's ink beside a box too, that box belongs to no line: refused.
        with self.assertRaises(ValueError):
            containment(drawn(self.pdf, [title, header, row, (261.1, [(364, 'Scalp laceration 2')])]), [candidate])

    def test_text_that_is_not_printed_beside_the_row_still_refuses(self):
        from .layout_geometry import containment
        candidate = self.prepared()
        from .layout_geometry import geometry
        header = next(l for l in geometry(drawn(self.pdf, self.cell)[0]) if l['y'] == 280)
        end = header['records'][-1]['ink'][2]
        for stray in ([(280, [(420, 'Unrelated words')])],       # not the row's other cells
                      [(280, [(60, 'Scalp')])],                  # the comment cell is to the right, never the left
                      [(280, [(360, 'cm, sutured.')])],          # inside the row's own printed extent
                      [(280, [(end - 1.5, 'cm, sutured.')])]):   # its ink touches the row's own ink
            with self.subTest(stray=stray), self.assertRaises(ValueError):
                containment(drawn(self.pdf, self.cell + stray), [candidate])

    def test_a_line_that_reads_as_the_paragraph_in_two_places_is_ambiguous(self):
        from .layout_geometry import containment
        candidate = self.prepared()
        header = candidate['rendered_source']['header']
        text = ''.join(i['text'] for segment in header for i in segment).replace(' ', '')
        for neighbours in ({'left': text, 'right': text},):
            doubled = dict(candidate, rendered_source=dict(candidate['rendered_source'], neighbours=neighbours))
            line = [(10, 'Normal'), (52, 'Abnormal'), (104, 'Exam not done'), (200, 'Normal'), (242, 'Abnormal'), (294, 'Exam not done')]
            lines = [self.cell[0], self.cell[2], (280, line)]  # the row painted first: only the line itself is ambiguous
            with self.assertRaises(ValueError):
                containment(drawn(self.pdf, lines), [doubled])
        # Without text beside the row a line is the paragraph alone, not even a space more on either side.
        for extra in ((280, [(5, ' ')]), (280, [(420, ' ')])):
            with self.subTest(extra=extra):
                alone = dict(candidate, rendered_source=dict(candidate['rendered_source'], neighbours={'left': '', 'right': ''}))
                self.assertTrue(containment(drawn(self.pdf, self.cell), [alone])['passed'])
                with self.assertRaises(ValueError):
                    containment(drawn(self.pdf, self.cell + [extra]), [alone])
        for neighbours in ({'left': 1, 'right': ''}, {'right': ''}, ['', ''], {'left': '', 'right': '', 'other': ''}):
            malformed = dict(candidate, rendered_source=dict(candidate['rendered_source'], neighbours=neighbours))
            with self.subTest(neighbours=neighbours), self.assertRaises(ValueError):
                containment(drawn(self.pdf, self.cell), [malformed])


class CentredControlsUnderNarrowWords(PaintedFixture):
    """F10: a code and box centred under a narrower option word belong to it; nothing wider is loosened."""

    def candidate(self, options=('No', 'Yes'), label='Supple'):
        glyph = lambda text: [{'kind': 'glyph', 'text': text}]
        header = [[]] + [glyph(o) for o in options]
        row = [glyph(label)] + [glyph(str(i + 1) + ' ') + [{'kind': 'ff_checkbox', 'text': '￼', 'checked': False}]
                                for i in range(len(options))]
        return {'id': 'c', 'source': {'options': list(options)}, 'optional': True, 'untouched': True,
                'rendered_source': {'header': header, 'row': row, 'row_dot_leaders': False, 'header_index': 0,
                                    'source_occurrences': 1, 'sequence': [{'segments': header, 'dot_leaders': False},
                                                                          {'segments': row, 'dot_leaders': False}]}}

    def lines(self, first=197, second=297, headers=((200, 'No'), (300, 'Yes'))):
        return [(300, list(headers)),
                (280, [(20, 'Supple'), (first, '1 '), (first + 10, None), (second, '2 '), (second + 10, None)])]

    def test_a_centred_code_and_box_under_a_narrower_word_is_owned_by_it(self):
        from .layout_geometry import containment
        result = containment(drawn(self.pdf, self.lines()), [self.candidate()])
        self.assertEqual(result['held'], [])
        self.assertTrue(result['passed']); self.assertEqual(len(result['measurements']), 2)

    def test_the_centre_must_lie_under_the_word_and_the_segment_inside_its_column(self):
        from .layout_geometry import containment, geometry
        header = next(l for l in geometry(drawn(self.pdf, self.lines())[0]) if l['y'] == 300)
        no_right = max(r['ink'][2] for r in header['records'][:2])
        # The segment '1 ' + box spans x+1.21 .. x+20.05 in this font; its centre is x+10.63.
        for first in (no_right - 10.63 + .01,):   # centre just right of 'No'
            with self.subTest(first=first):
                result = containment(drawn(self.pdf, self.lines(first=first)), [self.candidate()])
                self.assertEqual([h['candidate'] for h in result['held']], ['c'])
        # Words close together: the centre is under 'Normal' but the segment reaches past the midpoint.
        close = ((100, 'Normal'), (142, 'Abnormal'))
        result = containment(drawn(self.pdf, self.lines(first=124.4, second=150, headers=close)),
                             [self.candidate(('Normal', 'Abnormal'))])
        self.assertEqual([h['candidate'] for h in result['held']], ['c'])


class WitnessGuards(PaintedFixture):
    """F9: every repaired guard of the witness has a test that fails when the guard is removed."""

    header = [[], [{'kind': 'glyph', 'text': 'Normal'}], [{'kind': 'glyph', 'text': 'Abnormal'}]]

    def titled(self, **flags):
        row = [[]] + [[{'kind': 'glyph', 'text': str(i + 1) + ' '}, {'kind': 'ff_checkbox', 'text': '￼', 'checked': False}]
                      for i in range(2)]
        paragraphs = [[[{'kind': 'glyph', 'text': 'Head summary'}]], self.header, row]
        return dict({'id': 'head', 'source': {'options': ['Normal', 'Abnormal']}, 'rendered_source': {
            'header': self.header, 'row': row, 'row_dot_leaders': False, 'header_index': 1, 'source_occurrences': 1,
            'sequence': [{'segments': p, 'dot_leaders': False} for p in paragraphs]}}, **flags)

    lines = [(300, [(20, 'Head summary')]), (280, [(100, 'Normal'), (200, 'Abnormal')]),
             (260, [(110, '1 '), (120, None), (210, '2 '), (220, None)])]

    def test_a_fill_painted_just_after_a_glyph_covers_it(self):
        from .layout_geometry import containment, geometry
        order = self.lines[1:] + self.lines[:1]   # the title is painted last
        title = next(l for l in geometry(drawn(self.pdf, order)[0]) if l['text'] == 'Head summary')
        ink = title['records'][-1]['ink']
        width = ink[2] - ink[0]
        cover = f'q 1 1 1 rg {ink[0] + width / 4} {ink[1]} {width / 2} {ink[3] - ink[1]} re f Q\n'.encode()
        self.assertTrue(containment(drawn(self.pdf, order), [self.titled()])['passed'])
        with self.assertRaises(ValueError):
            containment(drawn(self.pdf, order, after=cover), [self.titled()])

    def test_a_fill_beneath_the_text_must_contrast_with_it(self):
        from .layout_geometry import containment
        for grey, visible in ((.4, False), (.5, True)):
            with self.subTest(grey=grey):
                shade = f'q {grey} {grey} {grey} rg 5 245 390 70 re f Q\n'.encode()
                if visible:
                    self.assertTrue(containment(drawn(self.pdf, self.lines, before=shade), [self.titled()])['passed'])
                else:
                    with self.assertRaises(ValueError):
                        containment(drawn(self.pdf, self.lines, before=shade), [self.titled()])

    def test_the_title_line_is_part_of_the_one_contiguous_rendering(self):
        from .layout_geometry import containment
        interrupted = self.lines[:1] + [(100, [(20, 'Other')])] + self.lines[1:]
        with self.assertRaises(ValueError):
            containment(drawn(self.pdf, interrupted), [self.titled()])
        self.assertTrue(containment(drawn(self.pdf, self.lines + [(100, [(20, 'Other')])]), [self.titled()])['passed'])

    def test_a_copy_printed_in_a_page_header_part_is_counted(self):
        doc = coded_form(['10.\tLungs', '\tNormal\tAbnormal', 'Percussion\t1 ☐\t2 ☐', '', 'Auscultation\t1 ☐\t2 ☐'],
                         control='glyph')
        header = doc.sections[0].header
        header.paragraphs[0].text = '\tNormal\tAbnormal'; header.add_paragraph('Percussion\t1 ☐\t2 ☐')
        proposal, _, _ = layout_source.prepare(data(doc))
        counts = {c['source']['label']: c['rendered_source']['source_occurrences'] for c in proposal['manifest']['candidates']}
        self.assertEqual(counts, {'Percussion': 2, 'Auscultation': 1})


# ─── Refutation 2026-09-28, round R3 (R3-1..R3-6) ──────────────────────────────────────────────────────────────────


def box_fields(result):
    return [(f['label'], f['options']) for f in result['fields'] if f['locator']['target']['type'] == 'checkboxes']


class WordsBeforeBoxesWithTextAfter(unittest.TestCase):
    """R3-1: words printed before their boxes are never shifted onto the next box, whatever is printed after the last."""

    def test_printed_text_after_the_last_box_never_lets_a_box_take_the_next_boxs_word(self):
        lines = ('Allergies: Yes ☐ No ☐ NKDA', 'Smoker: Yes ☐ No ☐ (check one)', 'Smoker Yes ☐ No ☐ If yes, packs/day',
                 'Smoker: Yes ☐   No ☐   Pack-years: ____', 'Smoker: Yes ☐\tNo ☐\tFormer ☐\t(tick one)',
                 'Result: positive ☐ negative ☐ equivocal', 'Right ☐ Left ☐ Bilateral',
                 'Smoker Current ☐\tFormer ☐\tNever ☐\t(tick one)', 'Smoker: Yes ☐ No ☐   Drinker: Yes ☐ No ☐ (tick one)',
                 'Smoker: (Yes) ☐ (No) ☐ N/A', 'Smoker [Yes] ☐ [No] ☐ N/A', 'Date: ____ Yes ☐ No ☐ N/A',
                 'Pregnancy test ____ Positive ☐ Negative ☐ Not done',
                 # one reading each: an instruction after the last box, a companion word before the first, a word
                 # printed against the box after it, a short word after the question's colon
                 'Mobility Independent ☐ Assisted ☐ (tick one)', 'Pregnant N/A ☐ Yes ☐ No',
                 'Mobility Independent ☐\tAssisted ☐\tBedbound', 'Allergies: NKDA ☐ Penicillin ☐ Sulfa ☐ Other')
        for control in ('glyph', 'ff'):
            for line in lines:
                with self.subTest(control=control, line=line):
                    result = w.inspect(data(coded_form([line], control=control, heading=None)))
                    self.assertEqual(box_fields(result), [])
                    self.assertTrue(any('printed before' in n for n in result['notes']))

    def test_a_no_answer_never_ticks_the_box_printed_after_yes(self):
        raw = data(coded_form(['Allergies: Yes ☐ No ☐ NKDA'], control='ff', heading=None))
        fields = [f for f in w.inspect(raw)['fields'] if f['locator']['target']['type'] == 'checkboxes']
        for field in fields:
            if 'No' in field['options']:
                states = w.option_states(w.SlotIndex(w.open_package(w.fill(raw, fields, {field['key']: 'No'}))), field)
                self.assertFalse(states[0], 'the box printed after "Yes" was ticked by "No"')

    def test_words_printed_after_their_boxes_keep_being_read(self):
        for line, label, options in (('Allergies: ☐ Yes ☐ No ☐ NKDA', 'Allergies', ['Yes', 'No', 'NKDA']),
                                     ('PMH: Diabetes ☐ Yes ☐ No ☐ Unknown', 'PMH: Diabetes', ['Yes', 'No', 'Unknown']),
                                     ('Diabetes ☐ Yes ☐ No', 'Diabetes', ['Yes', 'No']),
                                     ('Over 65\t☐ Yes\t☐ No', 'Over 65', ['Yes', 'No']),
                                     ('Pain present ☐ Yes ☐ No', 'Pain present', ['Yes', 'No']),
                                     ('Left ☐ Normal ☐ Abnormal', 'Left', ['Normal', 'Abnormal']),
                                     ('Social history: Smoking ☐ Current ☐ Former ☐ Never', 'Social history: Smoking',
                                      ['Current', 'Former', 'Never']),
                                     ('Q1? ☐ Yes ☐ No   Q2? ☐ Yes ☐ No', 'Q1?', ['Yes', 'No']),
                                     ('Allergies: (tick one) ☐ Yes ☐ No ☐ NKDA', 'Allergies: (tick one)', ['Yes', 'No', 'NKDA']),
                                     ('Do you smoke? If yes ☐ Cigarettes ☐ Cigars ☐ Pipe', 'Do you smoke? If yes',
                                      ['Cigarettes', 'Cigars', 'Pipe']),
                                     # a question's own answer blank, its unit, or a sentence continuing after it (D03, D28)
                                     ('Weight ____ kg ☐ measured ☐ stated', 'Weight ____ kg', ['measured', 'stated']),
                                     ('Referral: Dr ______ ☐ urgent ☐ routine', 'Referral: Dr', ['urgent', 'routine']),
                                     ('|____|____| TIMES ☐ REFUSED ☐ DON’T KNOW', '|____|____| TIMES', ['REFUSED', 'DON’T KNOW']),
                                     ('They usually last: _____ minutes and end _____ minutes before the pain starts OR occur '
                                      '☐ during the headache, ☐ after the headache, OR ☐ without the headache',
                                      'They usually last: _____ minutes and end _____ minutes before the pain starts OR occur',
                                      ['during the headache,', 'after the headache, OR', 'without the headache'])):
            for control in ('glyph', 'ff'):
                with self.subTest(control=control, line=line):
                    result = w.inspect(data(coded_form([line], control=control, heading=None)))
                    self.assertEqual(box_fields(result)[:1], [(label, options)])
        raw = data(coded_form(['Allergies: ☐ Yes ☐ No ☐ NKDA'], control='ff', heading=None))
        [field] = [f for f in w.inspect(raw)['fields'] if f['locator']['target']['type'] == 'checkboxes']
        out = w.fill(raw, [field], {field['key']: 'No'})
        self.assertEqual(w.option_states(w.SlotIndex(w.open_package(out)), field), [False, True, False])


class LegendNumbersInEveryPrintedForm(unittest.TestCase):
    """R3-2: a legend printed as '1. Normal', 'Normal (1.)', '1.0 Normal' or in the title is a legend too."""

    def test_a_legend_that_contradicts_the_row_codes_is_noted_in_any_printed_form(self):
        stops = (2880, 4320)
        for header in ('\t1. Normal\t2. Abnormal', '\tNormal (1.)\tAbnormal (2.)', '\t1.0 Normal\t2.0 Abnormal'):
            for name, rows in (('two rows', [('Palpable\t2 ☐\t1 ☐', stops), '', ('Tender\t2 ☐\t1 ☐', stops)]),
                               ('one tab pair', [('Palpable\t2 ☐\t1 ☐', stops)])):
                with self.subTest(header=header, rows=name):
                    cell = ['12b.\tLiver', (header, stops)] + rows
                    detector, _, notes = detect(data(stopped_form([[cell, ['']]], (6480, 2880))))
                    self.assertEqual([(a.label, a.options) for _, _, a in detector.layout_candidates], [])
                    self.assertTrue(any('codes' in n and ('Coded column sequence at ' in n or 'Tab-column options at ' in n)
                                        for n in notes))
        for title in ('12b. Liver (codes: 1 = Abnormal, 2 = Normal)', '12b. Liver (1) Abnormal (2) Normal',
                      '12b. Liver: 1. Abnormal 2. Normal', '12b. Liver (0 = not examined)'):
            titled = [title, ('\tNormal\tAbnormal', stops), ('Palpable\t1 ☐\t2 ☐', stops), '', ('Tender\t1 ☐\t2 ☐', stops)]
            for name, cell in (('two rows', titled), ('one tab pair', titled[:3])):
                with self.subTest(title=title, rows=name):
                    detector, _, notes = detect(data(stopped_form([[cell, ['']]], (6480, 2880))))
                    self.assertEqual([(a.label, a.options) for _, _, a in detector.layout_candidates], [])
                    self.assertTrue(any('codes' in n for n in notes))

    def test_a_legend_that_agrees_with_the_row_codes_keeps_its_options(self):
        stops = (2880, 4320)
        agreeing = ['12b.\tLiver', ('\t1. Normal\t2. Abnormal', stops), ('Palpable\t1 ☐\t2 ☐', stops), '', ('Tender\t1 ☐\t2 ☐', stops)]
        detector, _, _ = detect(data(stopped_form([[agreeing, ['']]], (6480, 2880))))
        self.assertEqual([(a.label, a.options) for _, _, a in detector.layout_candidates],
                         [('Palpable', ['1. Normal', '2. Abnormal']), ('Tender', ['1. Normal', '2. Abnormal'])])
        for title in ('12b. Liver (codes: 1 = Normal, 2 = Abnormal)', '12b. Liver (1) Normal (2) Abnormal', '1. Liver',
                      '2. Liver', 'Examine: 1. Inspect 2. Palpate 3. Percuss'):
            titled = [title, ('\tNormal\tAbnormal', stops), ('Palpable\t1 ☐\t2 ☐', stops), '', ('Tender\t1 ☐\t2 ☐', stops)]
            for name, cell in (('two rows', titled), ('one tab pair', titled[:3])):
                with self.subTest(title=title, rows=name):
                    detector, _, _ = detect(data(stopped_form([[cell, ['']]], (6480, 2880))))
                    self.assertEqual([(a.label, a.options) for _, _, a in detector.layout_candidates][:1],
                                     [('Palpable', ['Normal', 'Abnormal'])])


class LeftCellAnswerLines(unittest.TestCase):
    """R3-3: a left cell printing its own answer line (leader dots, an ellipsis, a gap before a unit) is another
    question's, never the coded row's."""

    MURMUR = ['Murmur', '', ('\tAbsent\tPresent', (1440, 2880)), ('\t1 ☐\t2 ☐', (1440, 2880))]

    def test_a_left_cell_with_its_own_answer_line_never_names_the_coded_row(self):
        for text in ('Weight: .................. kg', 'Heart rate: …………… bpm', 'Temp:          °C', 'Weight:\tkg'):
            for control in ('ff', 'glyph'):
                with self.subTest(text=text, control=control):
                    raw = data(stopped_form([[[text], self.MURMUR]], (2880, 6480), control=control))
                    detector, _, notes = detect(raw)
                    self.assertEqual([a.label for _, _, a in detector.layout_candidates], [])
                    self.assertTrue(any('holds its own answer' in n for n in notes))

    def test_a_plain_question_to_the_left_still_names_the_row(self):
        for text, label in (('Heart', 'Heart'), ('Heart:', 'Heart'), ('Heart sounds (auscultation)', 'Heart sounds (auscultation)')):
            with self.subTest(text=text):
                detector, _, _ = detect(data(stopped_form([[[text], self.MURMUR]], (2880, 6480), control='glyph')))
                self.assertEqual([a.label for _, _, a in detector.layout_candidates], [label])


class ScalesWhoseLastOptionIsAWord(unittest.TestCase):
    """R3-4: numbers, letters and numerals printed after their own boxes are those boxes' options, whatever the last
    option says; a code printed before a box still is not."""

    def test_a_scale_ending_in_a_word_is_read(self):
        for line, label, options in (('Stage: ☐ I ☐ II ☐ III ☐ IV ☐ Unknown', 'Stage', ['I', 'II', 'III', 'IV', 'Unknown']),
                                     ('Blood group: ☐ A ☐ B ☐ AB ☐ O ☐ Unknown', 'Blood group', ['A', 'B', 'AB', 'O', 'Unknown']),
                                     ('Pain score: ☐ 0 ☐ 1 ☐ 2 ☐ 3 ☐ Not assessed', 'Pain score',
                                      ['0', '1', '2', '3', 'Not assessed'])):
            with self.subTest(line=line):
                doc = Document(); doc.add_table(rows=1, cols=1).cell(0, 0).text = line
                self.assertEqual([(f['label'], f['options']) for f in w.inspect(data(doc))['fields'] if f.get('options')],
                                 [(label, options)])

    def test_a_code_printed_before_its_box_is_still_noted(self):
        for line in ('Shape\t☐\t2 ☐ Other', 'Shape ☐ 2 ☐ Other', 'Shape\t☐\t2 ☐', 'Finding ☐ II ☐ III ☐ Other',
                     'Finding\t☐\t1 ☐\t2 ☐ Other', 'Finding ☐ 1 ☐ 2 ☐', 'Finding 1 ☐ 2 ☐ ☐ 3',
                     'Finding 0 ☐ 1 ☐ ☐ 2'):
            for control in ('glyph', 'ff'):
                with self.subTest(line=line, control=control):
                    result = w.inspect(data(coded_form(['4.\tThyroid', '\tNormal\tAbnormal', line], control=control)))
                    self.assertEqual(box_fields(result), [])
                    self.assertTrue(any('response codes are not option labels' in n for n in result['notes']))


class PatientInstructionsAreNotDestinations(unittest.TestCase):
    """R3-5: a printed instruction addressed to the patient is content, and an instructed cell is never named by a
    printed value of its row."""

    def test_an_instruction_to_the_patient_is_never_an_answer_destination(self):
        raw = table_doc([('Medication', 'Dose', 'Patient instructions', 'Given (initials)'),
                         ('Metformin', '500 mg', 'Describe any stomach upset to your doctor', '')])
        fields = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}
        self.assertNotIn('b/tbl[0]/tr[1]/tc[2]', fields)
        self.assertFalse([f for f in fields.values() if f.get('source_instructions')])

    def test_advice_to_the_patient_or_a_column_of_printed_information_is_content(self):
        for header, text, destination in (('Comments', 'Describe any stomach upset to your doctor', False),
                                          ('Patient information', 'Describe any side effects', False),
                                          ('Findings', 'Describe any side effects', True)):
            with self.subTest(header=header, text=text):
                raw = table_doc([('Medication', 'Dose', header, 'Given (initials)'), ('Metformin', '500 mg', text, '')])
                self.assertEqual('b/tbl[0]/tr[1]/tc[2]' in {f['locator']['slot'] for f in w.inspect(raw)['fields']}, destination)

    def test_an_instructed_cell_is_named_by_its_row_never_by_a_value_printed_beside_it(self):
        raw = table_doc([('Medication', 'Dose', 'Findings', 'Given (initials)'),
                         ('Metformin', '500 mg', 'Describe any side effects here', '')])
        own = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}['b/tbl[0]/tr[1]/tc[2]']
        self.assertEqual(own['locator']['target']['type'], 'cell_append')
        self.assertNotIn('500 mg', own['label'])
        self.assertIn('Metformin', own['label'])

    def test_a_group_label_merged_over_several_rows_never_names_an_instructed_cell(self):
        doc = Document(); table = doc.add_table(rows=3, cols=4)
        for r, cells in enumerate((('System', 'Organ', 'Findings', 'Initials'),
                                   ('Abdomen', 'Liver', 'Describe any findings here', ''),
                                   ('', 'Spleen', 'Describe any findings here', ''))):
            for c, text in enumerate(cells):
                table.cell(r, c).text = text
        table.cell(1, 0).merge(table.cell(2, 0))
        fields = {f['locator']['slot']: f for f in w.inspect(data(doc))['fields']}
        self.assertEqual([(fields[s]['label'], fields[s]['locator']['target']['type'])
                          for s in ('b/tbl[0]/tr[1]/tc[2]', 'b/tbl[0]/tr[2]/tc[2]')],
                         [('Liver — Findings', 'cell_append'), ('Spleen — Findings', 'cell_append')])


class RoundTwoGuardsArePinned(unittest.TestCase):
    """R3-6: each round-two guard has a test that fails when the guard is removed."""

    MURMUR = ['Murmur', '', ('\tAbsent\tPresent', (1440, 2880)), ('\t1 ☐\t2 ☐', (1440, 2880))]

    def detector(self, doc):
        return w.Detector(w.open_package(data(doc)))

    def test_a_merged_left_cell_holding_its_own_box_is_never_group_context(self):
        for control in ('ff', 'glyph'):
            with self.subTest(control=control):
                rows = [[['Referred ☐'], ['Liver summary', '', ('\tNormal\tEnlarged', (1440, 2880)), ('\t1 ☐\t2 ☐', (1440, 2880))]],
                        [[''], ['Spleen summary', '', ('\tNormal\tEnlarged', (1440, 2880)), ('\t1 ☐\t2 ☐', (1440, 2880))]]]
                doc = stopped_form(rows, (2880, 6480), control=control)
                doc.tables[0].cell(0, 0).merge(doc.tables[0].cell(1, 0))
                detector, _, notes = detect(data(doc))
                self.assertEqual([a.label for _, _, a in detector.layout_candidates], [])
                self.assertTrue(any('merged cell to the left' in n for n in notes))

    def test_a_left_cell_with_a_bracketed_or_underlined_answer_place_never_names_the_coded_row(self):
        for text in ('Pulse: [    ]', 'Name: <name>', 'Rate {{rate}}'):
            with self.subTest(text=text):
                detector, _, notes = detect(data(stopped_form([[[text], self.MURMUR]], (2880, 6480), control='glyph')))
                self.assertEqual([a.label for _, _, a in detector.layout_candidates], [])
                self.assertTrue(any('holds its own answer' in n for n in notes))
        doc = stopped_form([[['Pulse'], self.MURMUR]], (2880, 6480), control='glyph')
        doc.tables[0].cell(0, 0).paragraphs[0].add_run('\t\t').underline = True
        detector, _, notes = detect(data(doc))
        self.assertEqual([a.label for _, _, a in detector.layout_candidates], [])
        self.assertTrue(any('holds its own answer' in n for n in notes))

    def test_an_instruction_beside_its_own_drawn_blank_keeps_the_blank_as_the_answer_place(self):
        raw = table_doc([('Organ', 'Findings', 'Initials'), ('Liver', 'If abnormal, describe here: ________', '')])
        fields = [f for f in w.inspect(raw)['fields'] if f['locator']['slot'].startswith('b/tbl[0]/tr[1]/tc[1]')]
        self.assertEqual([f['locator']['target']['type'] for f in fields], ['span'])

    def test_an_instruction_in_a_row_without_its_own_label_is_not_a_destination(self):
        raw = table_doc([('Organ', 'Findings'), ('', 'Describe any findings here')])
        self.assertNotIn('b/tbl[0]/tr[1]/tc[1]', {f['locator']['slot'] for f in w.inspect(raw)['fields']})
        raw = table_doc([('Organ', 'Findings', 'Initials'), ('', 'Describe any findings here', '')])
        self.assertNotIn('b/tbl[0]/tr[1]/tc[1]', {f['locator']['slot'] for f in w.inspect(raw)['fields']})
        raw = table_doc([('Organ', 'Findings', 'Initials'), ('Liver', 'Describe any findings here', '')])
        self.assertIn('b/tbl[0]/tr[1]/tc[1]', {f['locator']['slot'] for f in w.inspect(raw)['fields']})

    def test_an_oversized_instruction_is_printed_content(self):
        long = 'Describe any findings here, ' + ' '.join(['including size, edge, consistency and tenderness'] * 5)
        self.assertGreater(len(long), 200)
        raw = table_doc([('Organ', 'Findings', 'Initials'), ('Liver', long, '')])
        self.assertNotIn('b/tbl[0]/tr[1]/tc[1]', {f['locator']['slot'] for f in w.inspect(raw)['fields']})
        raw = table_doc([('Organ', 'Findings', 'Initials'), ('Liver', long[:190], '')])
        self.assertIn('b/tbl[0]/tr[1]/tc[1]', {f['locator']['slot'] for f in w.inspect(raw)['fields']})

    def test_a_row_whose_answer_is_a_ticked_box_is_a_data_row(self):
        for control in ('glyph', 'ff'):
            with self.subTest(control=control):
                from .test_word_v3 import ff_field
                doc = Document(); table = doc.add_table(rows=2, cols=2)
                table.cell(0, 0).text = 'Item'; table.cell(0, 1).text = 'Done'
                table.cell(1, 0).text = 'Consent obtained'
                if control == 'glyph':
                    table.cell(1, 1).text = '☒'
                else:
                    ff_field(table.cell(1, 1).paragraphs[0], 'checkbox', checked=True, name='Done')
                detector = self.detector(doc)
                self.assertEqual(detector.row_kind(detector.index.by_id['word/document.xml#b/tbl[0]'], 1), 'data')

    def test_an_inline_answer_gap_is_a_label_and_a_gap_before_a_unit_or_another_label(self):
        cases = (('Weight:      kg', True), ('Sessions:      Duration:    minutes', True), ('Weight:\tkg', True),
                 ('Status:      see attached', False), ('Weight: kg', False), ('12:      kg', False),
                 (' '.join(['word'] * 19) + ':      kg', False))
        for text, gap in cases:
            with self.subTest(text=text):
                doc = Document(); doc.add_paragraph(text)
                detector = self.detector(doc)
                self.assertEqual(detector.inline_answer_gap(detector.index.by_id['word/document.xml#b/p[0]']), gap)

    def test_an_underlined_gap_makes_a_value_cell(self):
        doc = Document(); table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = 'Weight'
        table.cell(0, 1).paragraphs[0].add_run('\t\t').underline = True
        detector = self.detector(doc)
        self.assertTrue(detector.prints_answer_blank(detector.index.by_id['word/document.xml#b/tbl[0]/tr[0]/tc[1]']))
        self.assertFalse(detector.prints_answer_blank(detector.index.by_id['word/document.xml#b/tbl[0]/tr[0]/tc[0]']))


class LayoutKeysArePinned(unittest.TestCase):
    """R3-6: the round-two guards of the printed-source key (layout_source.Printed) and of the rendered key
    (layout_geometry), each exercised alone."""

    def key(self, doc):
        package = w.open_package(data(doc))
        paragraph = [p for p in package.tree('word/document.xml').iter(w.q('w:p'))][-1]
        return layout_source.Printed(package).key(paragraph)

    def styled(self, kind, name, *, hidden=True, based=None):
        from docx.enum.style import WD_STYLE_TYPE
        doc = Document()
        styles = [doc.styles.add_style(n, getattr(WD_STYLE_TYPE, kind)) for n in ([based] if based else []) + [name]]
        for style in styles:
            style.font.hidden = hidden and style is styles[0]
        if based:
            styles[1].base_style = styles[0]
        return doc

    def test_a_run_a_style_may_hide_is_never_counted(self):
        from docx.oxml import OxmlElement
        doc = self.styled('CHARACTER', 'Child', based='Hidden')  # hidden by the style it is based on
        paragraph = doc.add_paragraph('Normal'); paragraph.add_run('X', style='Child')
        self.assertEqual(self.key(doc), 'normal')
        doc = self.styled('CHARACTER', 'A', hidden=False, based='B')  # a cycle resolves as hiding
        doc.styles['B'].base_style = doc.styles['A']
        paragraph = doc.add_paragraph('Normal'); paragraph.add_run('X', style='A')
        self.assertEqual(self.key(doc), 'normal')
        doc = Document(); paragraph = doc.add_paragraph('Normal'); run = paragraph.add_run('X')  # an unknown style
        style = OxmlElement('w:rStyle'); style.set(qn('w:val'), 'Missing'); run._r.get_or_add_rPr().append(style)
        self.assertEqual(self.key(doc), 'normal')
        doc = Document(); paragraph = doc.add_paragraph('Normal'); paragraph.add_run('X').font.hidden = False
        self.assertEqual(self.key(doc), 'normalx')  # <w:vanish w:val="0"/> prints
        doc = Document(); paragraph = doc.add_paragraph('Normal'); paragraph.add_run('X')
        self.assertEqual(self.key(doc), 'normalx')

    def test_a_paragraph_a_style_or_the_defaults_may_hide_is_never_counted(self):
        from docx.oxml import OxmlElement
        doc = self.styled('PARAGRAPH', 'HiddenParagraph'); doc.add_paragraph('Normal', style='HiddenParagraph')
        self.assertEqual(self.key(doc), '')
        doc = Document(); doc.styles['Normal'].font.hidden = True; doc.add_paragraph('Normal')  # the default paragraph style
        self.assertEqual(self.key(doc), '')
        doc = Document(); doc.styles['Default Paragraph Font'].element.get_or_add_rPr().append(OxmlElement('w:vanish'))
        doc.add_paragraph('Normal')  # the default character style
        self.assertEqual(self.key(doc), '')
        doc = Document(); doc.add_paragraph('Normal')  # the document defaults
        defaults = doc.styles.element.find(qn('w:docDefaults')).find(qn('w:rPrDefault')).find(qn('w:rPr'))
        defaults.append(OxmlElement('w:vanish'))
        self.assertEqual(self.key(doc), '')

    def test_characters_that_never_print_are_removed_and_box_states_merged(self):
        for char in ('­', '​', '͏', 'ᅟ', '᠋', '️', '\U000e0100', '\U000e0001'):
            with self.subTest(char='U+%04X' % ord(char)):
                doc = Document(); doc.add_paragraph('Nor' + char + 'mal')
                self.assertEqual(self.key(doc), 'normal')
        doc = Document(); doc.add_paragraph('1 ☒ 2 ☐')
        self.assertEqual(self.key(doc), '1☐2☐')

    def test_the_rendered_key_drops_leaders_and_controls_and_merges_box_states(self):
        from .layout_geometry import printed_key
        self.assertEqual(printed_key('1 ☒ 2 · … __ - – . ￼'), '1☐2')
        self.assertEqual(printed_key('Palpable ☐'), 'Palpable☐')

    def test_a_line_between_the_rows_is_beside_them_only_when_it_prints_ink(self):
        from .layout_geometry import beside
        neighbours = {'left': '', 'right': 'If abnormal, describe below'}
        self.assertEqual(beside({'records': [{'text': 'describe', 'ink': (0, 0, 1, 1)}]}, neighbours), ('right',))
        self.assertEqual(beside({'records': [{'text': 'describe', 'ink': None}]}, neighbours), ())


# ─── Refutation 2026-09-28, round R4 (R4-1..R4-11) ─────────────────────────────────────────────────────────────────


def held_before_boxes(test, lines, controls=('glyph', 'ff')):
    for control in controls:
        for line in lines:
            with test.subTest(control=control, line=line):
                result = w.inspect(data(coded_form([line], control=control, heading=None)))
                test.assertEqual(box_fields(result), [])
                test.assertTrue(any('printed before' in n for n in result['notes']))


class WordsBeforeBoxesWhateverTheVocabulary(unittest.TestCase):
    """R4-1, R4-2, R4-8: a row that may print each box's word before it is held whatever its words, and a row that
    can only be read one way is read."""

    def test_a_label_ending_in_an_option_word_is_never_the_question_of_the_boxes_after_it(self):
        held_before_boxes(self, ('Allergies Yes ☐ NKDA ☐ If yes, list ____',
                                 'DNR status Full code ☐ DNR ☐ Comfort care ☐ Discussed with ____',
                                 'Dose 0.5 mg ☐ 1 mg ☐ 2 mg ☐ Other ____', 'Urine protein Negative ☐ Trace ☐ 1+ ☐ 2+ ☐ Not done',
                                 'Tobacco: Current every day smoker ☐ Former smoker ☐ Never smoker ☐ Unknown',
                                 'Blood type A+ ☐ O+ ☐ B+ ☐ Other ____', 'Consent signed Yes ☐ Refused ☐ Comment ____',
                                 'Frequency: Every 4 hours ☐ Daily ☐ Weekly ☐ Other ____'))

    def test_the_answer_never_ticks_the_box_printed_after_its_word(self):
        for line, answer in (('Allergies Yes ☐ NKDA ☐ If yes, list ____', 'NKDA'), ('Dose 0.5 mg ☐ 1 mg ☐ 2 mg ☐ Other ____', '1 mg'),
                             ('Urine protein Negative ☐ Trace ☐ 1+ ☐ 2+ ☐ Not done', 'Trace'),
                             ('DNR status Full code ☐ DNR ☐ Comfort care ☐ Discussed with ____', 'DNR')):
            with self.subTest(line=line):
                raw = data(coded_form([line], control='ff', heading=None))
                fields = [f for f in w.inspect(raw)['fields'] if f['locator']['target']['type'] == 'checkboxes']
                for field in (f for f in fields if answer in f['options']):
                    states = w.option_states(w.SlotIndex(w.open_package(w.fill(raw, fields, {field['key']: answer}))), field)
                    self.assertFalse(states[0], 'the box printed after %r was ticked by %r' % (line.split('☐')[0], answer))

    def test_a_unit_or_when_word_after_the_questions_colon_is_an_option(self):
        held_before_boxes(self, ('Dose unit: mg ☐ mcg ☐ units ☐ Other ____', 'Symptom duration: Hours ☐ Days ☐ Weeks ☐ Exact: ____',
                                 'Frequency: When required ☐ Daily ☐ Weekly ☐ Other ____'))

    def test_a_row_readable_only_after_its_boxes_is_read_whatever_its_vocabulary(self):
        for line, label, options in (
                ('Exam: Pupils ☐ Equal ☐ Unequal ☐ Not assessed', 'Exam: Pupils', ['Equal', 'Unequal', 'Not assessed']),
                ('Airway: Mallampati ☐ I ☐ II ☐ III ☐ IV', 'Airway: Mallampati', ['I', 'II', 'III', 'IV']),
                ('Social history: Alcohol ☐ Never ☐ Occasional ☐ Heavy', 'Social history: Alcohol', ['Never', 'Occasional', 'Heavy']),
                ('Neuro: Gait ☐ Steady ☐ Unsteady ☐ Unable', 'Neuro: Gait', ['Steady', 'Unsteady', 'Unable']),
                ('Skin: Rash ☐ Macular ☐ Papular ☐ Vesicular', 'Skin: Rash', ['Macular', 'Papular', 'Vesicular']),
                ('Chest pain: Character ☐ Sharp ☐ Dull ☐ Pressure', 'Chest pain: Character', ['Sharp', 'Dull', 'Pressure'])):
            for control in ('glyph', 'ff'):
                with self.subTest(control=control, line=line):
                    result = w.inspect(data(coded_form([line], control=control, heading=None)))
                    self.assertEqual(box_fields(result)[:1], [(label, options)])


class CodesGluedToTheQuestion(unittest.TestCase):
    """R4-3: a code printed against the question with no space ('Score:0 ☐') is still a code before its box."""

    def test_a_first_code_touching_the_question_is_noted(self):
        for line in ('Pain score:0 ☐ 1 ☐ 2 ☐ 3 ☐ Not assessed', 'Pain(0) ☐ (1) ☐ (2) ☐ N/A', 'Grade—0 ☐ 1 ☐ 2 ☐ Unknown'):
            for control in ('glyph', 'ff'):
                with self.subTest(line=line, control=control):
                    result = w.inspect(data(coded_form([line], control=control, heading=None)))
                    self.assertEqual(box_fields(result), [])
                    self.assertTrue(any('response codes are not option labels' in n for n in result['notes']))

    def test_a_number_that_is_the_questions_own_is_not_a_code(self):
        # Positive controls: a range or a name ending in a number before the first box, then options after each box.
        for line, label, options in (('Pain score (0-10): ☐ 0 ☐ 1 ☐ 2 ☐ Not assessed', 'Pain score (0-10)',
                                      ['0', '1', '2', 'Not assessed']),
                                     ('Pain (0–10) ☐ 0 ☐ 1 ☐ 2', 'Pain (0–10)', ['0', '1', '2']),
                                     ('COVID-19 ☐ Positive ☐ Negative ☐ Not tested', 'COVID-19',
                                      ['Positive', 'Negative', 'Not tested'])):
            for control in ('glyph', 'ff'):
                with self.subTest(line=line, control=control):
                    result = w.inspect(data(coded_form([line], control=control, heading=None)))
                    self.assertEqual(box_fields(result), [(label, options)])


class LegendsInEveryPrintedForm(unittest.TestCase):
    """R4-4, R4-5: a legend number glued to its word, or printed in a form the parser does not know, is never read as
    no legend; and a code's meaning must be exactly the option over its box."""

    STOPS = (2880, 4320)

    def candidates(self, cell):
        detector, _, notes = detect(data(stopped_form([[cell, ['']]], (6480, 2880))))
        return [(a.label, a.options) for _, _, a in detector.layout_candidates], notes

    def test_a_glued_header_legend_over_reversed_codes_is_refused(self):
        for header in ('\t1.Normal\t2.Abnormal', '\t1)Normal\t2)Abnormal'):
            with self.subTest(header=header):
                found, notes = self.candidates(['12b. Liver', (header, self.STOPS), ('Edge\t2 ☐\t1 ☐', self.STOPS)])
                self.assertEqual(found, [])
                self.assertTrue(any('codes' in n for n in notes))
                raw = data(stopped_form([[['12b. Liver', (header, self.STOPS), ('Edge\t2 ☐\t1 ☐', self.STOPS)], ['']]], (6480, 2880)))
                with self.assertRaises(w.V3Failure):
                    layout_source.prepare(raw)  # no proposal survives to be filled

    def test_a_title_legend_in_an_unparsed_form_over_reversed_codes_is_refused(self):
        for title in ('12b. Liver (Abnormal = 1, Normal = 2)', '12b. Liver (codes: 1 Abnormal, 2 Normal)',
                      '12b. Liver [1] Abnormal [2] Normal', '12b. Liver (Abnormal (1), Normal (2))',
                      '12b. Liver (1 → Abnormal, 2 → Normal)'):
            titled = [title, ('\tNormal\tAbnormal', self.STOPS), ('Palpable\t1 ☐\t2 ☐', self.STOPS), '',
                      ('Tender\t1 ☐\t2 ☐', self.STOPS)]
            for name, cell in (('two rows', titled), ('one tab pair', titled[:3])):
                with self.subTest(title=title, rows=name):
                    found, notes = self.candidates(cell)
                    self.assertEqual(found, [])
                    self.assertTrue(any('codes' in n for n in notes))

    def test_a_negated_meaning_never_agrees_with_the_option_it_contains(self):
        for title, header in (('12b. Liver (codes: 1 = Not palpable, 2 = Palpable)', '\tPalpable\tNot palpable'),
                              ('12b. Liver (codes: 1 = Non-tender, 2 = Tender)', '\tTender\tNon-tender'),
                              ('12b. Liver (1. Not examined 2. Examined)', '\tExamined\tNot examined')):
            with self.subTest(title=title):
                found, _ = self.candidates([title, (header, self.STOPS), ('Edge\t1 ☐\t2 ☐', self.STOPS)])
                self.assertEqual(found, [])


class AnswerLinesBesideCodedRows(unittest.TestCase):
    """R4-6, R4-10: a left cell's answer line is read as the engine reads one, in linear time."""

    MURMUR = ['Murmur', '', ('\tAbsent\tPresent', (1440, 2880)), ('\t1 ☐\t2 ☐', (1440, 2880))]
    PROSE = ('Please read the following instructions carefully before completing this section and ensure that each '
             'finding is recorded in the appropriate column with the date and the initials of the examiner ')

    def test_a_long_left_cell_is_read_in_bounded_time(self):
        import time
        raw = data(stopped_form([[[(self.PROSE * 20)[:3000]], self.MURMUR]], (2880, 6480), control='glyph'))
        started = time.monotonic(); w.inspect(raw)
        self.assertLess(time.monotonic() - started, 5)
        doc = stopped_form([[[(self.PROSE * 10)[:1200]], self.MURMUR]] + [[[''], self.MURMUR] for _ in range(19)],
                           (2880, 6480), control='glyph')
        doc.tables[0].cell(0, 0).merge(doc.tables[0].cell(19, 0))
        raw = data(doc)
        started = time.monotonic(); w.inspect(raw)
        self.assertLess(time.monotonic() - started, 5)

    def test_a_left_cell_is_an_answer_line_exactly_when_the_engine_reads_one(self):
        for text in ('Weight:   kg', 'Weight:    kg', 'Temp:   °C'):
            with self.subTest(text=text):
                detector, _, notes = detect(data(stopped_form([[[text], self.MURMUR]], (2880, 6480), control='glyph')))
                self.assertEqual([a.label for _, _, a in detector.layout_candidates], [])
                self.assertTrue(any('holds its own answer' in n for n in notes))
        for text in ('Cardiovascular:\tHeart sounds', 'Cardiovascular:    Heart sounds'):
            with self.subTest(text=text):
                detector, _, _ = detect(data(stopped_form([[[text], self.MURMUR]], (2880, 6480), control='glyph')))
                self.assertEqual([a.label for _, _, a in detector.layout_candidates], ['Cardiovascular: Heart sounds'])


class InstructedCellItems(unittest.TestCase):
    """R4-7, R4-9: an instructed cell is named by its row's own item; a withdrawn one is noted, and only printed
    advice to the patient is withdrawn."""

    def labels(self, raw, row_slots):
        fields = {f['locator']['slot']: f for f in w.inspect(raw)['fields']}
        return [(fields[s]['label'], fields[s]['locator']['target']['type']) if s in fields else None for s in row_slots]

    def test_the_item_is_the_rows_own_label_never_a_group_label_or_a_date(self):
        raw = table_doc([('System', 'Organ', 'Findings', 'Initials'), ('Abdomen', 'Liver', 'Describe any findings here', ''),
                         ('', 'Spleen', 'Describe any findings here', ''), ('Chest', 'Lungs', 'Describe any findings here', ''),
                         ('', 'Heart', 'Describe any findings here', '')])
        self.assertEqual(self.labels(raw, ['b/tbl[0]/tr[%d]/tc[2]' % r for r in (1, 2, 3, 4)]),
                         [('Liver — Findings', 'cell_append'), ('Spleen — Findings', 'cell_append'),
                          ('Lungs — Findings', 'cell_append'), ('Heart — Findings', 'cell_append')])
        raw = table_doc([('Date', 'Medication', 'Response', 'Initials'),
                         ('01/02/2026', 'Metformin', 'Describe any side effects here', ''),
                         ('01/02/2026', 'Warfarin', 'Describe any bleeding here', '')])
        self.assertEqual(self.labels(raw, ['b/tbl[0]/tr[1]/tc[2]', 'b/tbl[0]/tr[2]/tc[2]']),
                         [('Metformin — Response', 'cell_append'), ('Warfarin — Response', 'cell_append')])

    def test_a_clinicians_documentation_request_stays_a_destination(self):
        for header, item, text in (('Findings', 'Counselling', 'Describe discussion with the patient here'),
                                   ('Details', 'Escalation', 'Describe any concerns raised with the team here'),
                                   ('Education provided', 'Diet', 'Describe the education given here')):
            with self.subTest(text=text):
                raw = table_doc([('Item', header, 'Initials'), (item, text, '')])
                self.assertEqual(self.labels(raw, ['b/tbl[0]/tr[1]/tc[1]']), [('%s — %s' % (item, header), 'cell_append')])

    def test_printed_advice_to_the_patient_is_withdrawn_with_a_note(self):
        for header, text in (('Comments', 'Describe any stomach upset at your next appointment'),
                             ('Comments', 'Describe any bleeding when you phone us'),
                             ('Comments', 'Note any dizziness and stop the tablets'),
                             ('Comments', 'Describe any stomach upset to your doctor'),
                             ('Patient information', 'Describe any side effects')):
            with self.subTest(text=text):
                raw = table_doc([('Medication', 'Dose', header, 'Given (initials)'), ('Metformin', '500 mg', text, '')])
                result = w.inspect(raw)
                self.assertNotIn('b/tbl[0]/tr[1]/tc[2]', {f['locator']['slot'] for f in result['fields']})
                self.assertTrue(any(text in n and 'printed' in n for n in result['notes']), result['notes'])
