"""Offline live-receipt boundary tests; constructed responses are not provider results.

The note and dated-source assessment are retained evidence. Provider code rows
here are explicit controls for the cited-service defect, never a new inference.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import coding_output as output, coding_service as service, corti_prediction
from core.coding_export import append_codes
from core.corti_semantics import checked_spans
from core.models import CodingDecision, CodingOutputDecision, CodingRun
from core.tests.test_coding_export import document_bytes, texts
from core.tests import test_corti_workflow as workflow

BUNDLE = Path(__file__).parents[2] / 'ops/fixtures/corti_rowan_output_reference.json'
NOTE = json.loads((Path(__file__).with_name('fixtures') / 'rowan_semantic_retained.json').read_text())['notes']
ACTOR = UUID('5f4d1a3d-eeb6-4207-b1df-4597dc696e82')


def controlled_receipt(notes, code='99213'):
    quote='Blood pressure 118/74 mmHg'
    start=notes.index(quote)
    raw={'codes':[{'system':'cpt','code':code,'display':'UNVERIFIED 15 MINUTES',
        'evidences':[{'contextIndex':0,'start':start,'end':start+len(quote),'text':quote}]}],
        'candidates':[{'system':'cpt','code':'99999'}]}
    body=json.dumps(raw)
    spans,status=checked_spans(raw['codes'][0]['evidences'],notes)
    receipt={'state':'succeeded','sent':True,'simulated':False,
        'raw_response':{'body':body,'redacted':False},'response_sha256':hashlib.sha256(body.encode()).hexdigest()}
    row={'id':'selected:0','system':'CPT','code':code,'description':'','provider_display':raw['codes'][0]['display'],
        'eligible':False,'evidence_status':status,'evidence_spans':spans}
    return receipt,row


def bind_request(run):
    request=corti_prediction.payload(run)
    run.requests[0].update(stage=corti_prediction.STAGE,attempt=1,provider='corti',
        envelope={'protocol':corti_prediction.PROTOCOL,'identity':corti_prediction.receipts._identity(run),
                  'config':deepcopy(run.config),'payload':request},
        request_sha256=hashlib.sha256(corti_prediction.receipts.encode(request)).hexdigest())


class ReferenceMixin:
    def install(self, bundle=None):
        raw=json.dumps(bundle or self.bundle).encode()
        path=Path(self.temporary.name)/'reference.json';path.write_bytes(raw)
        setting=override_settings(SYNTHETIC_ONLY=True,CORTI_OUTPUT_REFERENCE_FILE=str(path),
            CORTI_OUTPUT_REFERENCE_SHA256=hashlib.sha256(raw).hexdigest())
        setting.enable();self.addCleanup(setting.disable)


class LiveOutputReferenceTests(ReferenceMixin,SimpleTestCase):
    def setUp(self):
        self.temporary=TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.bundle=json.loads(BUNDLE.read_text());self.install()
        self.encounter=SimpleNamespace(pk=uuid4(),patient_id=uuid4(),created_by_id=ACTOR,
            service_date=date(2026,10,16),notes=NOTE,status='finalized')
        receipt,row=controlled_receipt(NOTE)
        self.run=SimpleNamespace(pk=uuid4(),encounter_id=self.encounter.pk,user_id=ACTOR,
            config={'provider':'corti','mode':'live'},state='needs_detail',
            inputs={'notes':NOTE,'service_date':'2026-10-16'},context={},releases=[],
            result={'replay':False,'global_blockers':[],'suggestions':[row]},requests=[receipt],
            selection={'selected_ids':[],'overrides':{}},selection_revision=0)
        self.run.input_digest=corti_prediction.receipts.digest({'inputs':self.run.inputs,
            'context':self.run.context,'releases':self.run.releases})
        bind_request(self.run)
        self.base=SimpleNamespace(pk=uuid4(),input_digest=self.run.input_digest,selections=deepcopy(self.run.selection),
            selection_digest=service.selection_digest(self.run))

    def reviewed(self):
        with patch.object(service,'assert_current'),patch.object(CodingDecision.objects,'filter',return_value=[self.base]):
            return output.reviewed(self.encounter,self.run)

    def test_inadequate_provider_citations_remain_diagnostic_and_full_note_support_is_separate(self):
        assessment,review,_=self.reviewed()
        self.assertEqual(assessment['selection']['code'],'99213')
        self.assertEqual(review['provider_citation_adequacy']['status'],'insufficient_for_time_review')
        self.assertIn('time_minutes',review['provider_citation_adequacy']['missing_facts'])
        self.assertEqual(review['provider_evidence_spans'],self.run.result['suggestions'][0]['evidence_spans'])
        self.assertEqual(review['evidence_origin'],'independently_checked_saved_note_time_facts')
        self.assertEqual({f['key'] for f in review['facts']},set(output.FACT_LABELS))
        self.assertEqual(next(f['value'] for f in review['facts'] if f['key']=='time_minutes'),24)
        self.assertTrue(any('24 minutes' in span['text'] for span in review['evidence_spans']))
        self.assertTrue(any('excludes clinical staff time' in span['text'] for span in review['evidence_spans']))
        self.assertFalse(any('Blood pressure' in span['text'] for span in review['evidence_spans']))
        self.assertEqual(review['description_status'],output.DESCRIPTION_STATUS)
        self.assertEqual(review['review_execution'],'agent_executed_synthetic')
        self.assertIn('15 MINUTES',self.run.requests[0]['raw_response']['body'])

    def test_selected_unknown_hcpcs_and_unselected_alternative_cannot_enter(self):
        for code,identifier in [('99999','selected:0'),('G8752','selected:0'),('99213','candidate:0'),
                                ('99213','selected:0:alternative:0')]:
            with self.subTest(code=code,identifier=identifier):
                receipt,row=controlled_receipt(NOTE,code);row['id']=identifier
                run=deepcopy(self.run);run.requests=[receipt];run.result['suggestions']=[row]
                bind_request(run)
                with self.assertRaises(ValidationError):output.live_assessment(self.encounter,run)

    def test_retained_response_cannot_move_to_missing_wrong_or_reordered_request_context(self):
        for change in ('missing','wrong_note','wrong_date','reordered','systems','request_hash','identity','config'):
            with self.subTest(change=change):
                run=deepcopy(self.run);receipt=run.requests[0];envelope=receipt['envelope'];request=envelope['payload']
                if change=='missing':request.pop('context')
                elif change=='wrong_note':request['context'][0]['text']='A different patient note.'
                elif change=='wrong_date':request['context'][1]['text']='Date of service: 2026-10-17'
                elif change=='reordered':request['context'].reverse()
                elif change=='systems':request['system']=['cpt']
                elif change=='identity':envelope['identity']['encounter_id']=str(uuid4())
                elif change=='config':envelope['config']['mode']='replay'
                receipt['request_sha256']=hashlib.sha256(corti_prediction.receipts.encode(request)).hexdigest()
                if change=='request_hash':receipt['request_sha256']='0'*64
                # Keep the original selected response intact, and even rehash
                # altered requests: canonical source binding still rejects it.
                with self.assertRaises(ValidationError):output.live_assessment(self.encounter,run)

    def test_date_context_quote_is_valid_diagnostic_but_cannot_supply_time_evidence(self):
        request=self.run.requests[0]['envelope']['payload'];quote=request['context'][1]['text']
        receipt=self.run.requests[0];response=json.loads(receipt['raw_response']['body'])
        response['codes'][0]['evidences']=[{'contextIndex':1,'start':0,'end':len(quote),'text':quote}]
        receipt['raw_response']['body']=json.dumps(response)
        receipt['response_sha256']=hashlib.sha256(receipt['raw_response']['body'].encode()).hexdigest()
        self.run.result['suggestions'][0]['evidence_spans']=[{'context_index':1,'start':0,
            'end':len(quote),'text':quote,'status':'valid'}]
        self.base.selection_digest=service.selection_digest(self.run)
        _,review,_=self.reviewed()
        self.assertEqual(review['provider_citation_adequacy']['status'],'insufficient_for_time_review')
        self.assertEqual(review['provider_evidence_spans'][0]['context_index'],1)
        self.assertTrue(all(s['context_index']==0 for s in review['evidence_spans']))
        self.assertTrue(any('24 minutes' in s['text'] for s in review['evidence_spans']))

    def test_date_actor_source_and_provider_receipt_are_independently_bound(self):
        for change in ('actor','date','source','unsent','simulated','hash','wrongprovider','replay','blocker'):
            with self.subTest(change=change):
                encounter,run=deepcopy(self.encounter),deepcopy(self.run)
                if change=='actor':run.user_id=uuid4()
                elif change=='date':encounter.service_date=date(2026,10,17)
                elif change=='source':encounter.notes+=' Extra unsupported statement.'
                elif change=='unsent':run.requests[0]['sent']=False
                elif change=='simulated':run.requests[0]['simulated']=True
                elif change=='hash':run.requests[0]['response_sha256']='0'*64
                elif change=='wrongprovider':run.config['provider']='other'
                elif change=='replay':run.result['replay']=True
                else:run.result['global_blockers']=['Conflicting source identity']
                with self.assertRaises(ValidationError):output.live_assessment(encounter,run)

    def test_unsupported_time_and_missing_dated_sources_or_permission_stay_held(self):
        changes=[lambda b:b['entries'][0]['criteria'].update(minimum_minutes=30),
                 lambda b:b['entries'][0]['coverage'].pop('cms_release'),
                 lambda b:b['entries'][0]['sources'][0].update(evidence_sha256=''),
                 lambda b:b['permission'].update(contradictory_restriction='Actual test restriction'),
                 lambda b:b['entries'][0].update(service_dates=['2026-10-17'])]
        for change in changes:
            with self.subTest(change=change):
                bundle=deepcopy(self.bundle);change(bundle);self.install(bundle)
                with self.assertRaises(ValidationError):self.reviewed()

    def test_missing_corrupt_or_mismatched_provider_spans_cannot_be_replaced_silently(self):
        for spans in ([],[{'context_index':0,'start':0,'end':1,'text':'F','status':'valid'}]):
            run=deepcopy(self.run);run.result['suggestions'][0]['evidence_spans']=spans
            with self.subTest(spans=spans),self.assertRaises(ValidationError):
                output.live_assessment(self.encounter,run)

    def test_original_note_survives_automated_synthetic_appendix_without_false_human_claim(self):
        _,review,_=self.reviewed()
        original=document_bytes()
        row={'system':'CPT','code':review['code'],'description':'15 MINUTES',
            'export_route':'bounded_api_output','review_execution':'agent_executed_synthetic',
            'evidence_spans':[{'quote':s['text']} for s in review['evidence_spans']]}
        downloaded=append_codes(original,[row]);content='\n'.join(texts(downloaded))
        self.assertIn('authorized automated test agent',content)
        self.assertIn('not human clinical review',content)
        self.assertIn('99213 — accepted synthetic code number',content)
        self.assertNotIn('15 MINUTES',content)
        self.assertNotIn('clinician-accepted',content)
        self.assertNotIn('Synthetic retained-response review',content)
        self.assertIn('24 minutes',content)
        self.assertNotIn('G8752',content)
        self.assertEqual(texts(original),texts(document_bytes()))


@override_settings(CODING_PROVIDER='corti',SYNTHETIC_ONLY=True,ADMIN_SITE=False)
class LiveOutputDecisionTests(ReferenceMixin,TestCase):
    def setUp(self):
        workflow.CortiWorkflowTests.setUp(self)
        self.temporary=TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.encounter.notes=NOTE;self.encounter.answers={'note':{'text':NOTE}}
        self.encounter.status='finalized';self.encounter.finalized_at=timezone.now()
        self.encounter.finalized_by=self.actor
        self.encounter.save(update_fields=['notes','answers','status','finalized_at','finalized_by'])
        self.encounter.patient.display_name='Synthetic Rowan Blake'
        self.encounter.patient.save(update_fields=['display_name'])
        self.bundle=json.loads(BUNDLE.read_text())
        self.bundle['scope']['actor_ids']=[str(self.actor.pk)] # isolated test identity only
        self.install()
        receipt,row=controlled_receipt(NOTE)
        inputs,context,releases,key=service.input_snapshot(self.encounter)
        self.run=CodingRun(encounter=self.encounter,user=self.actor,input_digest=key,
            inputs=inputs,context=context,releases=releases,config={'provider':'corti','mode':'live'},
            state='needs_detail',requests=[receipt],result={'replay':False,'global_blockers':[],'suggestions':[row]},
            selection={'selected_ids':[],'overrides':{}},selection_revision=0)
        bind_request(self.run);self.run.save(force_insert=True)
        self.base=CodingDecision.objects.create(run=self.run,user=self.actor,input_digest=key,
            selections=deepcopy(self.run.selection),selection_digest=service.selection_digest(self.run))

    def test_explicit_decision_persists_reload_and_never_creates_human_approval_claim(self):
        view=output.view(self.encounter,self.run,self.actor)
        self.assertEqual(view['state'],'pending')
        self.assertEqual(output.accepted_output_rows(self.encounter,self.run,self.base),[])
        with self.assertRaises(ValidationError):
            output.decide(self.encounter,self.run,self.actor,view['display_token'],'accepted',False)
        decision=output.decide(self.encounter,self.run,self.actor,view['display_token'],'accepted',True)
        self.run.refresh_from_db();self.encounter.refresh_from_db();decision.refresh_from_db()
        self.assertEqual(output.view(self.encounter,self.run,self.actor)['state'],'accepted')
        rows=output.accepted_output_rows(self.encounter,self.run,self.base)
        self.assertEqual([r['code'] for r in rows],['99213'])
        self.assertEqual(rows[0]['description'],'')
        self.assertEqual(rows[0]['review_execution'],'agent_executed_synthetic')
        self.assertEqual(decision.review['provider_citation_adequacy']['status'],'insufficient_for_time_review')
        self.assertTrue(any('24 minutes' in s['text'] for s in rows[0]['evidence_spans']))
        self.assertEqual(output.decide(self.encounter,self.run,self.actor,view['display_token'],'accepted',True).pk,decision.pk)
        self.assertEqual(CodingOutputDecision.objects.count(),1)
        self.send.assert_not_called()

    def test_rejected_or_stale_review_cannot_enter_accepted_export_rows(self):
        view=output.view(self.encounter,self.run,self.actor)
        output.decide(self.encounter,self.run,self.actor,view['display_token'],'rejected',False)
        self.assertEqual(output.accepted_output_rows(self.encounter,self.run,self.base),[])
        changed=deepcopy(self.encounter);changed.revision+=1
        self.assertFalse(output.view(changed,self.run,self.actor)['available'])
        with patch.object(service,'locked_encounter',return_value=changed),self.assertRaises(ValidationError):
            output.decide(self.encounter,self.run,self.actor,view['display_token'],'accepted',True)
        self.send.assert_not_called()
