"""Current transport adoption after two retained rejections; provider I/O is mocked."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from anthropic import BadRequestError
from django.db import transaction
from django.test import TestCase, override_settings

from core import ai_stages, generation, generation_recovery as recovery
from core import clinical_schema_transport as transport
from core import clinical_node_transport as codec
from core import source_assertion_graph as graph
from core.jobs import enqueue, run_one
from core.models import AuditEvent, Job, Reservation, SourceInterpretation, Usage
from core.security import private_path
from core.tests.test_billing_policy import STORAGES
from core.tests.test_generation_recovery import RecoveryFixture, NEW_RELEASE
from core.tests.test_source_assertion_graph import checker

CURRENT_RELEASE='e'*40


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',
    STORAGES=STORAGES,RELEASE_SHA=NEW_RELEASE)
class ClinicalEvidenceRecoveryTests(RecoveryFixture,TestCase):
    def test_current_three_stage_adoption_shares_five_calls_with_two_immutable_rejections(self):
        self.assertNotIn(transport.CONFIG_KEY,self.old.config)
        self.assertIsNotNone(recovery.rejection(self.old))
        # Reconstruct the already-supported historical v1 request only for the
        # second rejection. The third request below uses the active pipeline.
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            second=self.retry()
        self.assertEqual(second.config[transport.CONFIG_KEY],transport.TRANSPORT)
        response=httpx.Response(400,request=httpx.Request('POST','https://synthetic.invalid/messages'),
            headers={'request-id':'req_offlineV1Rejected'+second.pk.hex},
            json={'error':{'type':'invalid_request_error','message':'Synthetic retained schema rejection'}})
        rejected=BadRequestError('Synthetic schema rejection',response=response,body=response.json())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),\
             patch.object(ai_stages,'_response',side_effect=rejected)as provider:
            self.assertTrue(run_one());self.assertEqual(provider.call_count,1)
        second.refresh_from_db();self.assertEqual(second.state,'reconciliation')
        proof=recovery.rejection(second);self.assertIsNotNone(proof);self.assertEqual(proof['prior_calls'],2)

        previous=[self.old,second];previous_ids=[j.pk for j in previous]
        jobs_before=deepcopy(list(Job.objects.filter(pk__in=previous_ids).order_by('pk').values()))
        stages_before=deepcopy([list(j.ai_stage_receipts.order_by('pk').values())for j in previous])
        reservations_before=deepcopy(list(Reservation.objects.filter(job__in=previous).order_by('pk').values()))
        audit_before=deepcopy(list(AuditEvent.objects.order_by('pk').values()))
        retained={}
        for job in previous:
            stage=job.ai_stage_receipts.get()
            self.assertEqual(stage.state,'unknown');self.assertIsNone(stage.actual_cost)
            event=AuditEvent.objects.get(action='ai.stage_error_retained',target=str(stage.pk))
            for name,digest in [(stage.request_path,stage.request_sha256),
                                (event.details['evidence_path'],event.details['evidence_sha256'])]:
                retained[name]=private_path(name).read_bytes()
                self.assertEqual(hashlib.sha256(retained[name]).hexdigest(),digest)

        with override_settings(RELEASE_SHA=CURRENT_RELEASE):
            active=ai_stages.pipeline_config(self.config())
            self.assertEqual(active[transport.CONFIG_KEY],transport.CURRENT_TRANSPORT)
            self.assertEqual(active[transport.CONFIG_KEY],codec.TRANSPORT)
            token=recovery.offer(self.encounter,self.user,active);self.assertIsNotNone(token)
            new=enqueue(self.encounter,self.user,config=self.config(),
                expected_revision=self.encounter.revision,recovery_token=token)
            self.assertEqual(new.config[transport.CONFIG_KEY],transport.CURRENT_TRANSPORT)
            self.assertEqual(new.config['queued_release_sha'],CURRENT_RELEASE)
            self.assertEqual(new.config[recovery.RECOVERY_KEY]['job'],str(second.pk))
            self.assertEqual(new.config[recovery.RECOVERY_KEY]['prior_calls'],2)
            calls=[];transmitted=[];assigned=None
            def provider(payload,schema,instructions,config,maximum,timeout,on_response):
                nonlocal assigned
                role=('extractor','assigner','checker')[len(calls)];calls.append(role)
                self.assertEqual(config[transport.CONFIG_KEY],transport.CURRENT_TRANSPORT)
                # Retain the original schema's ordering here, just as the
                # sending code does before canonical envelope serialization.
                transmitted.append(transport.transmitted_schema(schema,transport.CURRENT_TRANSPORT))
                if role=='extractor':
                    parsed={'contract':graph.CONTRACT,'facts':[],'assertions':[],'relationships':[],
                        'time_accounts':[],'unit_coverage':[{'source_unit_id':u['id'],
                        'disposition':'nonclinical','assertion_ids':[],'affected_assertion_ids':[]}
                        for u in payload['source_units']]}
                elif role=='assigner':
                    parsed={'fields':[{'key':f['key'],'separator':'; ','components':[
                        {'id':c['id'],'disposition':'missing','fact_ids':[],
                         'predicate_assertion_ids':[],'relationship_ids':[]}
                        for c in payload['approved_definitions'][f['key']]['component_contract']['components']]}
                        for f in payload['fields']]};assigned=parsed
                else:parsed=checker(payload['graph'],payload['fields'],payload['approved_definitions'],assigned)
                wire=codec.encode(schema,parsed)
                self.assertEqual(wire['transport'],transport.CURRENT_TRANSPORT)
                self.assertEqual(codec.decode(schema,wire),parsed)
                text=json.dumps(wire)
                usage={'input_tokens':10,'cached_input_tokens':0,'cache_creation_tokens':0,'output_tokens':0}
                value=SimpleNamespace(id='msg_offlineV2'+new.pk.hex+role,
                    _request_id='req_offlineV2'+new.pk.hex+role,model=config['model'],
                    model_dump=lambda **kw:{'id':'msg_offlineV2'+new.pk.hex+role,
                        'content':[{'type':'text','text':text}],'usage':usage,'stop_reason':'end_turn'})
                on_response(value);cost=Decimal('0.00002')
                rates=generation.cost_rates(generation.rates(config),cost,Decimal('0'))
                return value,cost,usage,rates,text,True
            with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),\
                 patch.object(ai_stages,'_response',side_effect=provider)as send,\
                 patch('core.coding_hooks.after_saved_document'):
                self.assertTrue(run_one());self.assertEqual(send.call_count,3)

        new.refresh_from_db();self.encounter.refresh_from_db()
        self.assertEqual(new.state,'succeeded',new.error)
        self.assertEqual(calls,['extractor','assigner','checker'])
        rows=list(new.ai_stage_receipts.order_by('created_at','pk'))
        self.assertEqual([r.stage for r in rows],calls)
        self.assertTrue(all(r.state=='succeeded'and r.actual_cost==Decimal('0.00002')for r in rows))
        for row,expected_transmitted in zip(rows,transmitted):
            request=json.loads(private_path(row.request_path).read_bytes())
            self.assertEqual(request['schema_transport'],transport.CURRENT_TRANSPORT)
            self.assertEqual(json.loads(request['transmitted_schema']),expected_transmitted)
        self.assertTrue(SourceInterpretation.objects.filter(job=new,encounter=self.encounter).exists())
        self.assertTrue(self.encounter.answers)
        self.assertTrue(all(a['status']=='missing'and not a['text']for a in self.encounter.answers.values()))
        self.assertEqual(self.encounter.status,'review');self.assertFalse(self.encounter.export_path)
        all_jobs=list(Job.objects.filter(encounter=self.encounter))
        self.assertEqual(len(all_jobs),3)
        self.assertEqual(sum(j.ai_stage_receipts.count()for j in all_jobs),5)
        self.assertFalse(recovery.pending_jobs(all_jobs))
        self.assertTrue(recovery.linked(self.old,second));self.assertTrue(recovery.linked(second,new))
        self.assertEqual(Decimal(new.config['semantic_maximum_cost']),Decimal('8.15'))
        with transaction.atomic(),self.assertRaises(ai_stages.StageNotSent):
            recovery.enforce_stage_budget(new,rows,Decimal('0.000000000001'))
        self.assertEqual(Job.objects.filter(pk__in=previous_ids).order_by('pk').values().count(),2)
        self.assertEqual(list(Job.objects.filter(pk__in=previous_ids).order_by('pk').values()),jobs_before)
        self.assertEqual([list(j.ai_stage_receipts.order_by('pk').values())for j in previous],stages_before)
        self.assertEqual(list(Reservation.objects.filter(job__in=previous).order_by('pk').values()),reservations_before)
        self.assertEqual(list(AuditEvent.objects.filter(pk__in=[a['id']for a in audit_before]).order_by('pk').values()),audit_before)
        self.assertFalse(Usage.objects.filter(job__in=previous).exists())
        for name,raw in retained.items():self.assertEqual(private_path(name).read_bytes(),raw)
        self.unchanged()
