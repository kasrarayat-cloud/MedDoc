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
                    ('Cervical Posterior', ['Normal', 'Enlarged', 'Tender']),
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
