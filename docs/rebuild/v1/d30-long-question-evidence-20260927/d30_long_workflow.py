"""Known authorized D30 only; three changed areas; synthetic mocked selections."""
import copy
import hashlib
import json
import os
from pathlib import Path
from django.test import TestCase, override_settings
from core import generation, mapping_assistance as mapping, mapping_wire as wire
from core.models import TemplateVersion
from core.tests.test_question_box_workflow import QuestionBoxWorkflow
from core.tests.test_word_v3_workflow import V3Fixture
from core.tests.test_mapping_assistance import SETTINGS
from core.security import private_path

HERE=Path(__file__).parent
ORIGINAL=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev/originals/D30-fdeafbee872f.docx')
EXPECTED=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev/groundtruth/D30-fdeafbee872f.json')
SHA='fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f'

def original():
    content=ORIGINAL.read_bytes()
    assert hashlib.sha256(content).hexdigest()==SHA
    return content

class D30Capture(QuestionBoxWorkflow):
    area='abstract'
    def source(self):
        self.capture_dir=HERE/('capture-'+self.area+os.getenv('D30_CAPTURE_SUFFIX',''))
        self.capture_dir.mkdir(exist_ok=False)
        raw=original()
        (self.capture_dir/'original.docx').write_bytes(raw)
        return raw
    def capture(self,mode,template,version,encounter,source,exported):
        with (self.capture_dir/(mode+'.docx')).open('xb') as out: out.write(exported)
        with (self.capture_dir/(mode+'-workflow.json')).open('x') as out:
            json.dump({'area':self.area,'scope':'Known D30 development repair; mocked unit selection, no provider/corpus score.',
                'original_sha256':SHA,'export_sha256':encounter.export_sha256,'status':encounter.status,
                'notes':encounter.notes,'fields':version.fields,'answers':encounter.answers,'target_slot':self.target_slot,
                'other_parts_byte_identical':True,'other_body_blocks_xml_unchanged':True,
                'automatic_document_success':False},out,ensure_ascii=False,indent=2)

class D30A23(D30Capture):
    area='A23';target_slot='b/tbl[6]/tr[0]/tc[0]'
    ordinary_notes='The accommodation changed to supported housing because daily assistance is needed.'
    ordinary_correction='The accommodation changed to supported housing for daily assistance and weekly supervision.'

class D30A35(D30Capture):
    area='A35';target_slot='b/tbl[18]/tr[0]/tc[0]'
    ordinary_status='conflict'  # Retained original ordinary source is held; clinician correction is assisted.
    ordinary_notes='The patient attends an art class every Monday.'
    ordinary_correction='The patient attends supervised art classes every Monday and Wednesday.'

class D30A44(D30Capture):
    area='A44';target_slot='b/tbl[23]/tr[0]/tc[0]'
    ordinary_notes='The patient reports improved mood since discharge.'
    ordinary_correction='The patient reports sustained mood improvement since discharge.'

@override_settings(**SETTINGS)
class D30Boundaries(V3Fixture,TestCase):
    def test_exact_long_labels_review_save_add_assistance_and_oversize(self):
        areas={a['id']:a for a in json.loads(EXPECTED.read_text())['answer_areas']}
        template,version=self.uploaded(data=original(),name='SYNTHETIC D30 long-question boundaries')
        pristine=copy.deepcopy(version.fields)
        latest=version
        records=[]
        for identity in ('A23','A35'):
            area=areas[identity];slot=area['slots'][0]
            field=next(f for f in latest.fields if f['locator']['part']+'#'+f['locator']['slot']==slot)
            self.assertEqual(field['label'],area['label'])
            self.assertContains(self.client.get(f'/templates/{template.pk}/'),area['label'])
            # Force a new mapping version while keeping the entire original question.
            response=self.client.post(f'/templates/{template.pk}/',{'action':'v3_save','mapping_version':latest.pk,
                'kind_'+field['key']:'text'})
            self.assertEqual(response.status_code,302)
            latest=self.latest(template)
            self.assertEqual(next(f for f in latest.fields if f['key']==field['key'])['label'],area['label'])
            # Full existing label crosses the compact assistance reference and
            # exact original/locator/fingerprint gate without literal output text.
            config=generation.configuration();compiled=mapping.compile_request(latest,config)
            payload=json.loads(compiled['request']['messages'][0]['content'])
            fid=next(i for i,f in enumerate(payload['fields']) if f['key']==field['key'])
            sid=next(i for i,row in enumerate(payload['slots']) if row['slot']==slot)
            body=wire.fixture(payload);body['f']['k'].remove(fid);body['f']['r']=[fid]
            body['x']=[[fid,sid,0,payload['text_refs'].index([fid,4,0]),0,len(area['label']),-1]]
            result=mapping.validate_proposal(latest,compiled,body)
            replaced=next(f for f in result['fields'] if f['locator']['part']+'#'+f['locator']['slot']==slot)
            prior=next(f for f in latest.fields if f['key']==field['key'])
            self.assertEqual(replaced['label'],area['label'])
            self.assertEqual(replaced['context'],prior['context'])
            self.assertEqual(replaced['locator'],prior['locator'])
            self.assertEqual(compiled['input_token_bound'],len(mapping.canonical(compiled['request']).encode())+12000)
            # Manual correction removes and restores only the same physical area.
            response=self.client.post(f'/templates/{template.pk}/',{'action':'v3_save','mapping_version':latest.pk,
                'remove_'+field['key']:'on'})
            self.assertEqual(response.status_code,302);latest=self.latest(template)
            payload_add={'action':'v3_add','mapping_version':latest.pk,'slot':slot,'kind':'long_text','label':'x'*1001}
            response=self.client.post(f'/templates/{template.pk}/',payload_add)
            self.assertEqual(response.status_code,400);self.assertContains(response,'1000',status_code=400)
            self.assertEqual(self.latest(template).pk,latest.pk)
            payload_add['label']=area['label']
            self.assertEqual(self.client.post(f'/templates/{template.pk}/',payload_add).status_code,302)
            latest=self.latest(template)
            restored=next(f for f in latest.fields if f['locator']['part']+'#'+f['locator']['slot']==slot)
            self.assertEqual(restored['label'],area['label']);self.assertEqual(restored['origin'],'manual')
            records.append({'area':identity,'label':area['label'],'length':len(area['label']),'slot':slot,
                'assistance_context_exact':True,'assistance_locator_exact':True,'manual_origin':restored['origin'],
                'request_bytes':len(mapping.canonical(compiled['request']).encode()),'input_token_bound':compiled['input_token_bound'],
                'maximum_cost':compiled['maximum_cost'],'request_sha256':compiled['request_sha256'],'profile':compiled['profile']})
        version.refresh_from_db();self.assertEqual(version.fields,pristine)
        self.assertEqual(private_path(template.original_path).read_bytes(),original())
        with (HERE/os.getenv('D30_BOUNDARY_RECORD','exact-label-boundaries.json')).open('x') as out:json.dump(records,out,indent=2,ensure_ascii=False)
