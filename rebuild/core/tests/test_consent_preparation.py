"""Retrospective consent facts are not signatures; historical inventories stay sealed."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from docx import Document

from core.template_review import review_items
from core import preparation
from documents.engine import DocumentFailure
from documents.preparation import (inventory, candidate, digest, signing_protected,
    validate_inventory, TYPED_PROTOCOL, PROTOCOL, SIGNING_CONTEXT)
from documents.preparation_service import inspect_preparation, prepare_candidate
from documents.semantic_preparation_roles import protected_field


class ConsentPreparationTests(SimpleTestCase):
    question = ('What telehealth consent was documented?For telephone or video visits only. '
                'Leave blank for in-person visits.')

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root/'blank.docx'
        document = Document()
        table = document.add_table(rows=4, cols=2)
        for row, label in zip(table.rows, [self.question, 'Patient signature', 'I consent to treatment', 'Age in years']):
            row.cells[0].text = label
        document.save(self.path)

    def test_documented_fact_questions_and_real_authorizations_remain_distinct(self):
        facts = [self.question, 'What informed consent was documented?',
            'Which verbal consent has been recorded?',
            'Describe the consent discussion documented for this visit.',
            'Describe the consent discussion recorded for this visit',
            '  WHAT TELEHEALTH CONSENT WAS DOCUMENTED?  ',
            'What telehealth con\u200bsent was documented?']
        protected = ['Patient signature', 'Consent signature / date', 'I consent to treatment',
            'I attest that consent was obtained', 'Please sign below', 'Consent',
            'What consent was documented? Patient signature',
            'What consent was documented? I agree to treatment.',
            'What consent was documented? I consent.',
            'Describe the consent discussion documented for this visit. I certify it.',
            'What consent was documented?For video visits only. Sign below.',
            'What consent was documented?Leave blank for in-person visits. I attest this is true.',
            'What consent is granted?', 'Do you consent to treatment?',
            'ｐａｔｉｅｎｔ ｓｉｇｎａｔｕｒｅ', 'Patient sig\u200bnature']
        for label in facts:
            with self.subTest(label=label):
                self.assertFalse(signing_protected(label, SIGNING_CONTEXT))
                self.assertFalse(protected_field({'label':label}))
        for label in protected:
            with self.subTest(label=label):
                self.assertTrue(signing_protected(label, SIGNING_CONTEXT))
        self.assertTrue(signing_protected(self.question))
        self.assertTrue(signing_protected('I consent to treatment'))
        self.assertFalse(signing_protected('Consentless support'))

    def test_context_is_new_inventory_only_and_binds_complete_source(self):
        old = inventory(self.path, protocol=TYPED_PROTOCOL)
        new = inventory(self.path, protocol=TYPED_PROTOCOL, signing_context=SIGNING_CONTEXT)
        self.assertNotIn('signing_context', old)
        self.assertEqual(new['signing_context'], SIGNING_CONTEXT)
        self.assertNotEqual(old['inventory_sha256'], new['inventory_sha256'])
        self.assertTrue(old['anchors'][0]['protected_signing'])
        self.assertFalse(new['anchors'][0]['protected_signing'])
        self.assertEqual(new['anchors'][0]['protected_signing'], new['questions'][0]['protected_signing'])
        self.assertTrue(new['anchors'][1]['protected_signing'])
        self.assertTrue(new['anchors'][2]['protected_signing'])
        for key in ('source_sha256','parts','stories','fields','review_requirements','document_backend'):
            self.assertEqual(new[key], old[key])
        restored = deepcopy(new)
        restored.pop('signing_context')
        restored['anchors'][0]['protected_signing'] = True
        restored['questions'][0] = deepcopy(old['questions'][0])
        restored['inventory_sha256'] = digest({k:v for k,v in restored.items() if k!='inventory_sha256'})
        self.assertEqual(restored, old)

    def test_both_historical_and_new_candidates_rederive_their_own_policy(self):
        original = self.path.read_bytes()
        for name, context in [('historical', None), ('new', SIGNING_CONTEXT)]:
            inv = inventory(self.path, protocol=TYPED_PROTOCOL, signing_context=context)
            out = self.root/(name+'.docx')
            result = candidate(self.path, out, inv, [a['id'] for a in inv['anchors']])
            self.assertEqual(out.read_bytes(), original)
            self.assertEqual(result['inventory_sha256'], inv['inventory_sha256'])
        wrong = inventory(self.path, protocol=TYPED_PROTOCOL)
        wrong['signing_context'] = SIGNING_CONTEXT
        wrong['inventory_sha256'] = digest({k:v for k,v in wrong.items() if k!='inventory_sha256'})
        with self.assertRaises(DocumentFailure):
            candidate(self.path, self.root/'wrong.docx', wrong, [a['id'] for a in wrong['anchors']])

    def test_unknown_or_downgraded_explicit_policy_refuses(self):
        for context in ('', False, 'unknown'):
            with self.subTest(context=context), self.assertRaises(DocumentFailure):
                inventory(self.path, protocol=TYPED_PROTOCOL, signing_context=context)
        with self.assertRaises(DocumentFailure):
            inventory(self.path, protocol=PROTOCOL, signing_context=SIGNING_CONTEXT)
        for value in (None, False, 'unknown'):
            inv = inventory(self.path, protocol=TYPED_PROTOCOL)
            inv['signing_context'] = value
            inv['inventory_sha256'] = digest({k:v for k,v in inv.items() if k!='inventory_sha256'})
            with self.assertRaises(DocumentFailure):
                validate_inventory(inv)

    def test_only_new_ordinary_preparations_freeze_the_policy(self):
        config = {'mode':'fixture'}
        for source, expected in [('a'*64, SIGNING_CONTEXT), (preparation.WM_IOV_SHA256, None)]:
            with patch.object(preparation,'feature_enabled',return_value=True), \
                    patch.object(preparation,'configuration',return_value=config), \
                    patch('core.preparation_campaign.active_campaign_config',side_effect=lambda value,_:value), \
                    patch('core.testing_authority.identity',return_value=True), \
                    patch('core.testing_authority.create_preparation') as create:
                preparation.create_preparation(SimpleNamespace(sha256=source),'synthetic-clinician')
            frozen=create.call_args.args[2]
            self.assertEqual(frozen.get('word_signing_context'),expected)
            if expected is None:self.assertNotIn('word_signing_context',frozen)
        self.assertEqual(config,{'mode':'fixture'})

    def test_actual_networkless_worker_keeps_policy_and_original_cells(self):
        inv = inspect_preparation(self.path, protocol=TYPED_PROTOCOL, signing_context=SIGNING_CONTEXT)
        self.assertEqual(inv, inventory(self.path, protocol=TYPED_PROTOCOL, signing_context=SIGNING_CONTEXT))
        self.assertEqual(len(inv['fields']),4)
        out = self.root/'sandbox-candidate.docx'
        result = prepare_candidate(self.path, inv, [a['id'] for a in inv['anchors']], out)
        self.assertEqual(out.read_bytes(), self.path.read_bytes())
        self.assertTrue(result['parts_preserved'])


class QualifiedNameQuestionsTests(SimpleTestCase):
    def row(self, label):
        return {'field':{'key':'name','label':label},'state':'pass',
                'definition':{'value_type':'person_name'},'reason':''}

    def test_explicit_role_questions_need_summary_review_without_repeated_identity_choice(self):
        prep = SimpleNamespace(state='review', corrections={}, candidate_sha256='present')
        for label in ["What is the patient's full name?", 'Who is the referring physician?',
                      'What is the full name of the patient?', 'Patient full name']:
            with self.subTest(label=label):
                self.assertEqual(review_items(prep,[self.row(label)])[0]['state'],'pass')
        for label in ['Person full name', 'Full name (clinician to complete)',
                      'What is the full name?', 'Who is the patient to contact about a name?',
                      'What is the full name of the patient (or guardian)?',
                      'Who is the patient (or clinician)?',
                      "What is the patient's full name (or legal guardian's name)?",
                      'The full name of the patient (or guardian)',
                      'The name of the clinician (or patient)']:
            with self.subTest(label=label):
                self.assertEqual(review_items(prep,[self.row(label)])[0]['state'],'unresolved')
        unresolved=self.row("What is the patient's full name?")
        unresolved.update(state='unresolved',reason='Provider definitions disagree.')
        self.assertEqual(review_items(prep,[unresolved])[0],unresolved)
