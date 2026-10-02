"""Versioned catalogue de-duplication; compiler-only controls never call providers."""
import copy
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from core import generation as g, generation_batch as b
from .test_generation_batch import sample, manifest, SETTINGS


@override_settings(**SETTINGS)
class BatchPayload(SimpleTestCase):
    def test_original_v1_four_request_hashes_reconstruct_without_new_admission(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/batch_v1_plan.json').read_text())
        for case in fixture['cases']:
            with self.subTest(history=case['history']):
                plan=case['plan']
                for ordinal,wanted in enumerate(case['request_sha256'],1):
                    wire=b.request(plan,ordinal)
                    self.assertEqual(b.digest(wire),wanted)
                    self.assertEqual(b.digest(b.request(json.loads(json.dumps(plan,sort_keys=True)),ordinal)),wanted)
                    self.assertEqual(plan['parts'][ordinal-1]['request_sha256'],wanted)
                    self.assertEqual(plan['parts'][ordinal-1]['input_token_bound'],len(json.dumps(wire).encode())+12000)
                with self.assertRaisesMessage(ValidationError,'predates'):b.require_config(plan['config'])

    def test_v2_keeps_full_original_fields_options_scope_sources_and_rules_once(self):
        e=sample(102,notes='The patient reports a cough. The patient denies fever.')
        fs=e.template_version.fields
        for index,scope in ((0,'Right knee'),(1,'Left knee')):
            fs[index].update(label='Other:',context=scope,kind='choice',options=['Yes','No'])
        fs[-1]['kind']='signature';fs[-1]['context']='Donor only';fs[-1]['write_protected']=True
        e.template_version.review_requirements=[{'key':'review','label':'Original instruction','reason':'Verify original'}]
        m=manifest(fs);m['instruction_references']=[{'id':'rule','part':'word/document.xml','slot':'b/p[0]','sha256':'2'*64}]
        m['rules']=[{'kind':'unique_values','source_id':'rule','keys':['q002','q100'],'allowed_values':['1','2','3']}]
        e.template_version.generation_constraints=m
        plan=b.plan_for(e,g.configuration())
        self.assertEqual(plan['contract'],'v3-generation-batch-v2')
        for ordinal in (1,2):
            payload=json.loads(b.request(plan,ordinal)['messages'][0]['content'])
            self.assertNotIn('questions',payload)
            self.assertEqual(payload['full_catalogue'],fs)
            self.assertEqual(payload['form_constraints'],m)
            self.assertEqual(payload['source_units'],plan['units'])
            self.assertEqual(payload['notes'],e.notes)
            self.assertEqual(payload['context_labels'],plan['context_labels'])
            self.assertEqual(payload['requirements'],e.template_version.review_requirements)
            self.assertEqual(payload['requested_field_ids'],plan['parts'][ordinal-1]['field_ids'])
            self.assertNotIn('q101',payload['requested_field_ids'])
            # The sole v2 payload delta is the version and duplicate removal.
            legacy=copy.deepcopy(plan);legacy['contract']=legacy['config']['generation_batch_contract']=b.LEGACY_CONTRACT
            previous=json.loads(b.request(legacy,ordinal)['messages'][0]['content'])
            previous.pop('questions');previous['contract']=b.CONTRACT
            self.assertEqual(payload,previous)

    def test_sixteen_actual_compiler_profiles_and_costs_stay_bounded(self):
        self.assertEqual(b.MAX_REQUEST_BYTES,512000)
        with patch.dict('os.environ',QUILLMD_PROVIDER_DISCOUNT_RATE='0'):
            for count in (101,203,559,800):
                for thinking,cap in [('disabled',8000),('adaptive',16000)]:
                    for geo,factor in [('',Decimal(1)),('us',Decimal('1.1'))]:
                        with self.subTest(count=count,thinking=thinking,geo=geo),override_settings(AI_THINKING=thinking,AI_INFERENCE_GEO=geo):
                            e=sample(count,notes='The patient reports a cough. The patient denies fever.')
                            for field in e.template_version.fields:field['context']='Independent source context — β / café / clinically unchanged.'
                            e.template_version.generation_constraints=manifest(e.template_version.fields)
                            plan=b.plan_for(e,g.configuration());total=Decimal(0)
                            for ordinal,part in enumerate(plan['parts'],1):
                                wire=b.request(plan,ordinal);size=len(json.dumps(wire).encode())
                                self.assertLessEqual(size,512000)
                                self.assertEqual(wire['model'],'claude-sonnet-5');self.assertEqual(wire['max_tokens'],cap)
                                self.assertEqual(part['input_token_bound'],size+12000)
                                cost=Decimal(part['maximum_cost']);charge=Decimal(part['maximum_charge'])
                                expected=(Decimal(size+12000)*2+Decimal(cap)*10)/1000000*factor
                                self.assertGreaterEqual(cost,expected);self.assertLess(cost,expected+Decimal('.00000000001'))
                                self.assertEqual(charge,cost*Decimal('1.5'));total+=charge
                            self.assertEqual(Decimal(plan['maximum_charge']),total)

    def test_actual_oversize_and_unknown_or_mismatched_contract_refuse(self):
        e=sample(800,notes='The patient reports a cough.')
        for field in e.template_version.fields:field['context']='Full original scope '*100
        e.template_version.generation_constraints=manifest(e.template_version.fields)
        with self.assertRaisesMessage(ValidationError,'bounded payload'):b.plan_for(e,g.configuration())
        plan=b.plan_for(sample(),g.configuration())
        for name in ('unknown',b.LEGACY_CONTRACT):
            changed=copy.deepcopy(plan);changed['contract']=name
            with self.assertRaisesMessage(ValidationError,'unknown or inconsistent'):b.request(changed,1)
