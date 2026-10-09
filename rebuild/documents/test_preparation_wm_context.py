"""Independent original-XML checks for the finite WM source-review context.

These tests do not call the Word SDK or a model. The clinical label policy is
the qualified WM mapping; destinations, choices, units, placeholder links and
original assertion/signature text are independently read from the blank file.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest
from zipfile import ZipFile

from lxml import etree

from .engine import DocumentFailure, W_NS
from .preparation import (inventory, model_inventory, wm_source_review_context,
    digest, TYPED_PROTOCOL, WM_SOURCE_REVIEW_CONTEXT, WM_SOURCE_REVIEW_SHA256)
from .sdk_service import WM_IOV_SHA256

W = '{'+W_NS+'}'
NS = {'w': W_NS}
CONTROL_LABELS = (
    'Practice address', 'Exam side', 'Referring physician', 'Ultrasound technologist',
    'Ultrasound machine', 'Exam location', 'Clinical indication: leg pain',
    'Clinical indication: swelling', 'Clinical indication: heaviness',
    'Clinical indication: history or skin changes', 'Clinical indication: sensory symptoms',
    'Clinical indication: asymptomatic or itching', 'Diagnosis', 'Technique: venous systems',
    'Right previous treatment: vein', 'Right previous treatment: start',
    'Right previous treatment: end', 'Right previous treatment: outcome',
    'Left previous treatment: vein', 'Left previous treatment: start',
    'Left previous treatment: end', 'Left previous treatment: outcome',
    'Right impression: vein', 'Right impression: reflux or absence', 'Right deep venous system',
    'Left impression: vein', 'Left impression: reflux or absence', 'Left deep venous system')
REQUIREMENT_LABELS = {
    9: 'Exam type', 11: 'Interpreting physician', 19: 'Technique',
    23: 'Right previous treatment', 27: 'Left previous treatment',
    30: 'Right impression', 31: 'Right deep venous system', 32: 'Right saphenous reflux finding',
    34: 'Left impression', 35: 'Left deep venous system', 36: 'Left saphenous reflux finding',
    39: 'Clinical correlation', 45: 'Signature timestamp', 46: 'Signer identity'}


def text(element):
    return ''.join(element.xpath('.//w:t/text()', namespaces=NS))


def original_xml_inventory():
    path = Path(__file__).resolve().parents[2] / 'WM IOV Template.docx'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == WM_IOV_SHA256
    with ZipFile(path) as package:
        body = etree.fromstring(package.read('word/document.xml'))
        glossary = etree.fromstring(package.read('word/glossary/document.xml'))
    controls = list(body.iter(W+'sdt'))
    paragraphs = body.find(W+'body').findall(W+'p')
    fields = []
    for control, label in zip(controls, CONTROL_LABELS):
        ident = control.find(W+'sdtPr/'+W+'id').get(W+'val')
        fields.append({'key': 'sdt_'+ident, 'kind': 'choice', 'label': label,
            'locator': {'part': 'word/document.xml', 'sdt_id': ident},
            'options': [node.get(W+'value') for node in control.findall('.//'+W+'listItem')
                        if node.get(W+'value') != 'Choose an item.']})
    for index, key, label in [(4, 'date_of_service', 'Date of service'), (5, 'patient_id', 'Patient ID'),
                              (6, 'patient_name', 'Patient name'), (7, 'date_of_birth', 'Date of birth')]:
        fields.append({'key': key, 'kind': 'text', 'label': label, 'options': [],
            'locator': {'body_paragraph': index,
                        'expected_text_sha256': hashlib.sha256(text(paragraphs[index]).encode()).hexdigest()}})
    rows = body.find('.//'+W+'tbl').findall(W+'tr')
    for row_index, row in enumerate(rows):
        if row_index in (0, 14):
            continue
        cells = row.findall(W+'tc')
        question = text(cells[0])
        side = 'Right' if row_index < 14 else 'Left'
        label = side+' tributary row '+str(row_index) if '<<insert location>>' in question else side+' '+question
        for column, unit, suffix in [(1, 'mm', 'diameter (mm)'), (2, 'ms', 'reflux time (ms)')]:
            assert not text(cells[column])
            fields.append({'key': f'measurement_{row_index}_{column}', 'kind': 'measurement',
                'label': label+': '+suffix, 'options': [],
                'locator': {'table': 0, 'row': row_index, 'column': column, 'unit': unit}})
        if '<<insert location>>' in question:
            fields.append({'key': 'location_'+str(row_index), 'kind': 'text',
                'label': label+': anatomical location', 'options': [],
                'locator': {'table': 0, 'row': row_index, 'column': 0, 'marker': '<<insert location>>'}})
    requirements = []
    for index, label in REQUIREMENT_LABELS.items():
        original_text = text(paragraphs[index])
        sha = hashlib.sha256(original_text.encode()).hexdigest()
        requirements.append({'key': 'claim_'+str(index), 'label': 'Prewritten statement: '+label,
            'kind': 'identity' if index in (11, 46) else 'signature' if index == 45 else 'assertion',
            'body_paragraph': index, 'text': original_text, 'text_sha256': sha,
            'control_keys': ['sdt_'+node.find(W+'sdtPr/'+W+'id').get(W+'val')
                             for node in paragraphs[index].iter(W+'sdt')],
            'original_text': original_text, 'original_text_sha256': sha})
    known = {'backend': 'wm-iov-foss-v2', 'sha256': WM_IOV_SHA256, 'source_sha256': WM_IOV_SHA256,
             'mapping_digest': '0fcc5e36dfe589a190a726f059c45b10364f3d02f312aea5fc8935d16ea05072',
             'fields': fields, 'review_requirements': requirements}
    return inventory(path, known, protocol=TYPED_PROTOCOL), body, glossary, path


class WMSourceContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value, cls.body, cls.glossary, cls.original = original_xml_inventory()

    def context(self, value=None, mode=WM_SOURCE_REVIEW_CONTEXT):
        return wm_source_review_context(value or self.value, mode)

    def reseal(self, value):
        value['inventory_sha256'] = digest({key: item for key, item in value.items() if key != 'inventory_sha256'})

    def test_all_ninety_original_destinations_and_fourteen_requirements_are_source_bound(self):
        before = deepcopy(self.value)
        context = self.context()
        self.assertEqual(context['source_context_sha256'], WM_SOURCE_REVIEW_SHA256)
        destinations = context['body']['answer_destinations']
        self.assertEqual(len(destinations), 90)
        self.assertEqual(len(self.value['parts']), 25)
        self.assertEqual([item['anchor_id'] for item in destinations], [a['id'] for a in self.value['anchors']])
        self.assertEqual([item['question_id'] for item in destinations], [a['question_id'] for a in self.value['anchors']])
        self.assertEqual([item['original_label'] for item in destinations], [f['label'] for f in self.value['fields']])
        for field, destination in zip(self.value['fields'], destinations):
            if field['kind'] == 'measurement':
                self.assertEqual(destination['source_area']['printed_unit'], field['locator']['unit'])
        by_key = {field['key']: anchor['id'] for field, anchor in zip(self.value['fields'], self.value['anchors'])}
        requirements = context['body']['preserved_review_requirements']
        self.assertEqual(len(requirements), 14)
        for source, actual in zip(self.value['review_requirements'], requirements):
            self.assertEqual(actual['original_text'], text(self.body.find(W+'body').findall(W+'p')[source['body_paragraph']]))
            self.assertEqual(actual['answer_anchor_ids'], [by_key[key] for key in source['control_keys']])
            self.assertEqual(actual['kind'], source['kind'])
        self.assertEqual([r['handling'] for r in requirements if r['kind'] == 'signature'], ['actual_finalization_time_only'])
        self.assertEqual([r['handling'] for r in requirements if r['kind'] == 'identity'], ['actual_authenticated_signer_only']*2)
        self.assertEqual(self.value, before)

    def test_all_glossary_definitions_are_placeholder_only_and_link_to_one_original_dropdown(self):
        context = self.context()
        blocks = self.glossary.findall('.//'+W+'docPart')
        names = {block.find(W+'docPartPr/'+W+'name').get(W+'val'): block for block in blocks}
        definitions = context['glossary']['definitions']
        self.assertEqual(len(definitions), 28)
        self.assertEqual(len(names), 28)
        seen = set()
        for control, definition, destination in zip(self.body.iter(W+'sdt'), definitions, context['body']['answer_destinations']):
            ref = control.find(W+'sdtPr/'+W+'placeholder/'+W+'docPart').get(W+'val')
            self.assertNotIn(ref, seen)
            seen.add(ref)
            block = names[ref]
            self.assertEqual(block.find(W+'docPartPr/'+W+'category/'+W+'gallery').get(W+'val'), 'placeholder')
            self.assertEqual([n.get(W+'val') for n in block.findall(W+'docPartPr/'+W+'types/'+W+'type')], ['bbPlcHdr'])
            self.assertEqual(text(block), definition['original_text'])
            self.assertEqual(text(block), 'Choose an item.')
            self.assertEqual(definition['body_anchor_id'], destination['anchor_id'])
            self.assertEqual(destination['source_area']['placeholder_definition'], definition['id'])
        self.assertEqual(seen, set(names))
        self.assertEqual(context['glossary']['operation'], 'retain_unchanged')

    def test_public_context_contains_no_xml_paths_locators_raw_control_ids_or_signing_destination(self):
        public = model_inventory(self.value, source_review_context=WM_SOURCE_REVIEW_CONTEXT)
        encoded = json.dumps(public, ensure_ascii=False)
        for forbidden in ['word/', 'locator', 'sdt_', 'body_paragraph', '<w:', 'XPath']:
            self.assertNotIn(forbidden, encoded)
        self.assertIsNone(re.search(r'"(?:measurement|location)_\d+(?:_\d+)?"', encoded))
        context = public['source_review_context']
        signing = [r for r in context['body']['preserved_review_requirements'] if r['kind'] in ('signature', 'identity')]
        self.assertTrue(all(not r['answer_anchor_ids'] for r in signing))
        self.assertTrue(all(context['approval_policy'].values()))

    def test_absent_mode_preserves_the_historical_payload_and_does_not_rewrite_unknown_verdicts(self):
        before = deepcopy(self.value)
        public = model_inventory(self.value)
        self.assertNotIn('source_review_context', public)
        self.assertEqual(model_inventory(self.value, source_review_context=None), public)
        self.context()
        self.assertEqual(self.value, before)

    def test_wrong_source_mapping_package_and_source_projection_are_refused_even_after_resealing(self):
        changes = [
            lambda v: v.update(protocol='blank-word-preparation-v1'),
            lambda v: v.update(source_sha256='0'*64),
            lambda v: v['document_backend'].update(mapping_digest='0'*64),
            lambda v: v['document_backend'].update(extra='unsupported'),
            lambda v: v['parts'].update({'word/glossary/document.xml': '0'*64}),
            lambda v: v['stories'][7]['texts'].__setitem__(0, 'Extra question'),
            lambda v: v['fields'][0].update(label='Wrong question'),
            lambda v: v['fields'][0]['options'].reverse(),
            lambda v: v['fields'][32]['locator'].update(unit='cm'),
            lambda v: v['fields'][32]['locator'].update(column=2),
            lambda v: v['anchors'].reverse(),
            lambda v: v['anchors'][0].update(question_id='q2'),
            lambda v: v['questions'][0].update(protected_signing=True),
            lambda v: v['review_requirements'][12].update(kind='assertion'),
            lambda v: v['review_requirements'][12].update(control_keys=[v['fields'][0]['key']]),
            lambda v: v['review_requirements'][2].update(original_text='Rewritten clinical assertion'),
            lambda v: v['review_requirements'].pop(),
            lambda v: v['issues'].append({'code': 'unsupported_structure', 'message': 'Unresolved source'}),
        ]
        for index, change in enumerate(changes):
            value = deepcopy(self.value)
            change(value)
            self.reseal(value)
            with self.subTest(index=index), self.assertRaises(DocumentFailure):
                self.context(value)
        for mode in ['', 'universal-word', False, {}, 1]:
            with self.subTest(mode=mode), self.assertRaises(DocumentFailure):
                self.context(mode=mode)
        stale = deepcopy(self.value)
        stale['anchors'][0]['question_id'] = 'q2'
        with self.assertRaises(DocumentFailure):
            self.context(stale)
