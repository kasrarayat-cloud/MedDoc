"""Small synthetic controls for the D19 development finding; no corpus qualification."""
import io
import unittest
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from lxml import etree

from . import word_v3 as word


def signing_form(*, mismatch=False, table=True):
    doc = Document()
    doc.add_paragraph('Participant ID: __________')
    if table:
        doc.add_paragraph('Please initial box')
        t = doc.add_table(rows=3, cols=2)
        for number in range(2):
            t.cell(number, 0).text = 'Consent statement %s' % (number + 1)
            p = t.cell(number, 1).paragraphs[0]._p
            r = OxmlElement('w:r'); p.append(r)
            drawing = OxmlElement('w:drawing'); r.append(drawing)
            ns = {'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
                  'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                  'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape'}
            anchor = etree.SubElement(drawing, '{%s}anchor' % ns['wp'], nsmap=ns)
            shape = etree.SubElement(anchor, '{%s}wsp' % ns['wps'])
            prop = etree.SubElement(shape, '{%s}spPr' % ns['wps'])
            etree.SubElement(prop, '{%s}prstGeom' % ns['a'], prst='rect')
    p = doc.add_paragraph()
    for n in range(3):
        if n: p.add_run('\t')
        p.add_run('\t\t\t').underline = True
    doc.add_paragraph('Name of Participant\t\tDate\t\tSignature' if not mismatch else
                      'Name of Participant\t\tSignature')
    doc.add_paragraph()
    out = io.BytesIO(); doc.save(out)
    return out.getvalue()


class SigningAreas(unittest.TestCase):
    def test_captioned_signing_bands_preserve_types_and_actual_spans(self):
        result = word.inspect(signing_form())
        fields = result['fields']
        protected = [f for f in fields if f.get('write_protected')]
        self.assertEqual(len(protected), 5)
        bands = [f for f in protected if f['locator']['target']['type'] == 'span']
        self.assertEqual([(f['label'], f['kind']) for f in bands],
                         [('Name of Participant', 'text'), ('Date', 'date'), ('Signature', 'signature')])
        self.assertEqual([(f['locator']['target']['start'], f['locator']['target']['end']) for f in bands],
                         [(0, 3), (4, 7), (8, 11)])
        self.assertTrue(all('signing block' in f['review_reason'] for f in bands))
        self.assertEqual([f['label'] for f in fields if not f.get('write_protected')], ['Participant ID'])
        self.assertTrue(all(f['locator']['slot'] != 'b/p[4]' for f in fields))

    def test_floating_initials_have_no_guessed_consent_label(self):
        result = word.inspect(signing_form())
        boxes = [f for f in result['fields'] if f['kind'] == 'initials']
        self.assertEqual(len(boxes), 2)
        self.assertTrue(all('unresolved' in f['label'] for f in boxes))
        self.assertTrue(all('Consent statement' not in f['context'] for f in boxes))
        self.assertTrue(all(f['write_protected'] for f in boxes))
        self.assertTrue(any('floating' in note.lower() for note in result['notes']))

    def test_caption_count_mismatch_is_visible_and_not_guessed(self):
        result = word.inspect(signing_form(mismatch=True, table=False))
        held = [f for f in result['fields'] if f.get('write_protected')]
        self.assertEqual(len(held), 3)
        self.assertTrue(all('unresolved' in f['label'] for f in held))
        self.assertTrue(any('captions' in n for n in result['notes']))

    def test_protected_short_long_and_forged_flags_refuse_without_writing(self):
        data = signing_form()
        fields = word.inspect(data)['fields']
        self.assertEqual(sum(bool(f.get('write_protected')) for f in fields), 5)
        for field in [f for f in fields if f.get('write_protected')]:
            for answer in ('AB', 'Synthetic answer ' * 100):
                with self.subTest(label=field['label'], length=len(answer)):
                    with self.assertRaisesRegex(word.V3Failure, 'protected'):
                        word.fill(data, fields, {field['key']: answer})
                    forged = [{**f, 'kind': 'text', 'write_protected': False} for f in fields]
                    with self.assertRaisesRegex(word.V3Failure, 'protected'):
                        word.fill(data, forged, {field['key']: answer})

    def test_supported_answer_and_missing_preserve_all_signing_xml(self):
        data = signing_form(table=False)
        fields = word.inspect(data)['fields']
        key = next(f['key'] for f in fields if f['label'] == 'Participant ID')
        for answers in ({}, {key: 'SYNTHETIC-123'}, {key: 'SYNTHETIC ' * 100}):
            output = word.fill(data, fields, answers)
            with ZipFile(io.BytesIO(data)) as before, ZipFile(io.BytesIO(output)) as after:
                old = etree.fromstring(before.read('word/document.xml'))
                new = etree.fromstring(after.read('word/document.xml'))
                self.assertEqual([etree.tostring(x) for x in old.find(word.q('w:body'))][1:],
                                 [etree.tostring(x) for x in new.find(word.q('w:body'))][1:])

    def test_floating_layout_all_nonempty_exports_refuse_but_missing_is_unchanged(self):
        data = signing_form(); fields = word.inspect(data)['fields']
        self.assertIn(word.FLOATING_INITIALS_REFUSAL, word.inspect(data)['notes'])
        safe = next(f for f in fields if not f.get('write_protected'))
        for answer in ('A', 'SYNTHETIC ' * 100):
            with self.assertRaises(word.V3Failure) as caught:
                word.fill(data, fields, {safe['key']: answer})
            self.assertEqual(caught.exception.code, 'unqualified_floating_initials')
        with ZipFile(io.BytesIO(data)) as before, ZipFile(io.BytesIO(word.fill(data, fields, {}))) as after:
            self.assertTrue(all(before.read(n) == after.read(n) for n in before.namelist()))

    def test_every_primary_writer_and_paragraph_option_secondary_target_is_protected(self):
        from copy import deepcopy
        # No floating boxes: global export containment must not mask this bypass.
        data = signing_form(table=False); fields = word.inspect(data)['fields']
        safe = next(f for f in fields if not f.get('write_protected'))
        name = next(f for f in fields if f['label'] == 'Name of Participant')
        target_kinds = ('span', 'cell', 'cell_replace', 'paragraph', 'sdt_text', 'sdt_choice',
                        'ff_text', 'ff_dropdown', 'checkboxes', 'paragraph_options', 'text_options', 'table_rows')
        for kind in target_kinds:
            forged = deepcopy(safe); forged['locator'] = deepcopy(name['locator'])
            forged['locator']['target']['type'] = kind
            with self.subTest(kind=kind), self.assertRaisesRegex(word.V3Failure, 'protected'):
                word.fill(data, [forged], {forged['key']: 'AB'})
        forged = deepcopy(safe); forged.update(kind='choice', options=['Yes'])
        forged['locator']['target'] = {'type': 'paragraph_options', 'paragraphs': [name['locator']['slot']], 'printed': ['Yes']}
        with self.assertRaisesRegex(word.V3Failure, 'protected'):
            word.fill(data, [forged], {forged['key']: 'Yes'})

    def test_copies_and_descendant_slots_cannot_bypass_protected_source(self):
        from copy import deepcopy
        data = signing_form(); fields = word.inspect(data)['fields']
        safe = next(f for f in fields if not f.get('write_protected'))
        name = next(f for f in fields if f['label'] == 'Name of Participant')
        forged = deepcopy(safe)
        forged['locator']['target']['copies'] = [{k: name['locator'][k] for k in ('part', 'slot', 'fingerprint')}]
        with self.assertRaisesRegex(word.V3Failure, 'protected'):
            word.fill(data, [forged], {forged['key']: 'AB'})
        # An old mapping might target a blank cell below an overlapping shape.
        forged = deepcopy(safe)
        forged['locator'].update(slot='b/tbl[0]/tr[2]/tc[1]', fingerprint=None, target={'type': 'cell'})
        with self.assertRaisesRegex(word.V3Failure, 'protected'):
            word.fill(data, [forged], {forged['key']: 'AB'})
        box = next(f for f in fields if f['kind'] == 'initials')
        forged = deepcopy(safe)
        forged['locator'].update(slot=box['locator']['slot'] + '/p[0]', fingerprint=None)
        with self.assertRaisesRegex(word.V3Failure, 'protected'):
            word.fill(data, [forged], {forged['key']: 'AB'})

    def test_initials_instruction_does_not_cross_a_table_to_an_empty_paragraph(self):
        doc = Document(); doc.add_paragraph('Please initial box')
        doc.add_table(rows=1, cols=1).cell(0, 0).text = 'Printed instructions'
        doc.add_paragraph()
        out = io.BytesIO(); doc.save(out)
        self.assertEqual(word.inspect(out.getvalue())['fields'], [])

    def test_dated_inline_blank_is_a_date(self):
        doc = Document(); doc.add_paragraph('Information sheet dated.................... (version............)')
        out = io.BytesIO(); doc.save(out)
        self.assertEqual([f['kind'] for f in word.inspect(out.getvalue())['fields']], ['date', 'text'])
        doc = Document(); doc.add_paragraph('Dated and signed: __________')
        out = io.BytesIO(); doc.save(out)
        self.assertEqual(word.inspect(out.getvalue())['fields'][0]['kind'], 'signature')
