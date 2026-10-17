"""A context save reuses an immutable successful prediction, with zero sends."""
from copy import deepcopy
from decimal import Decimal
import json
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core import coding_recovery as recovery, coding_service as service, corti_coding, corti_prediction
from core.models import CodingRun
from core.tests import test_corti_workflow as workflow
from core.tests.test_coding_output_live import bind_request


@override_settings(CODING_PROVIDER='corti', SYNTHETIC_ONLY=True, ADMIN_SITE=False,
    STORAGES=workflow.STORAGES, CPT_ENTITLEMENT_MANIFEST='/missing-context-reuse-entitlement.json')
class RetainedContextReviewTests(TestCase):
    def setUp(self):
        workflow.CortiWorkflowTests.setUp(self)
        inputs, context, releases, key = service.input_snapshot(self.encounter)
        self.source = CodingRun(encounter=self.encounter, user=self.actor, input_digest=key,
            inputs=inputs, context=context, releases=releases,
            config={'provider':'corti', 'mode':'live', 'context_review_contract':recovery.CONTEXT_CONTRACT},
            requests=[{'state':'succeeded','sent':True,'simulated':False,
                'raw_response':{'body':workflow.RAW,'redacted':False},
                'response_sha256':workflow.FIXTURE['response_sha256']}],
            state='needs_detail', actual_cost=None)
        bind_request(self.source)
        self.source.result=corti_coding.retained_result(self.source,corti_prediction.payload(self.source),
            json.loads(workflow.RAW),workflow.FIXTURE['response_sha256'])
        self.source.selection={'selected_ids':['selected:0'],'overrides':{}}
        self.source.save(force_insert=True)
        self.before=CodingRun.objects.values().get(pk=self.source.pk)

    def save_context(self):
        return service.update_context(self.encounter,self.actor,
            {**self.source.context,'patient_status':'established','em_basis':'time','time_minutes':'25',
             'time_same_day':True,'time_qualified_clinician':True,'time_excludes_separately_reported':True})

    def test_changed_context_derives_new_review_without_charging_or_rewriting_original(self):
        with patch.object(corti_prediction,'execute',side_effect=AssertionError('No provider send')):
            derived=self.save_context()
            self.assertEqual(derived.config['mode'],'retained_live')
            self.assertEqual(derived.config['max_calls'],0)
            self.assertEqual(derived.requests,[])
            self.assertEqual(derived.actual_cost,Decimal('0'))
            self.assertEqual(service.assert_current(derived,self.encounter).pk,self.source.pk)
            self.assertEqual(service.ensure_run(self.encounter,self.actor).pk,derived.pk)
            self.assertEqual(CodingRun.objects.values().get(pk=self.source.pk),self.before)
            self.assertEqual(CodingRun.objects.count(),2)
        self.send.assert_not_called()

    def test_same_quote_cannot_move_retained_context_to_different_patient_answers_or_reference(self):
        derived=self.save_context()
        for field in ('patient_id','notes','answers','service_date','revision','template_version_id'):
            changed=deepcopy(derived);changed.inputs[field]='changed'
            changed.input_digest=service.digest({'inputs':changed.inputs,'context':changed.context,'releases':changed.releases})
            with self.subTest(field=field),self.assertRaises(ValidationError): recovery.source_for(changed)
        for kind in ('context','request','cost','config','result','source_hash','response_hash','encounter'):
            changed=deepcopy(derived)
            if kind=='context':changed.context['time_minutes']='36'
            elif kind=='request':changed.requests=[deepcopy(self.source.requests[0])]
            elif kind=='cost':changed.actual_cost=Decimal('1')
            elif kind=='config':changed.config['automatic_retries']=1
            elif kind=='source_hash':changed.config['retained_prediction']['source_input_digest']='0'*64
            elif kind=='response_hash':changed.config['retained_prediction']['source_requests_digest']='0'*64
            elif kind=='encounter':changed.encounter_id=uuid4()
            else:changed.result['retained_prediction']['review_context_digest']='0'*64
            with self.subTest(kind=kind),self.assertRaises(ValidationError): recovery.source_for(changed)
        self.send.assert_not_called()

    def test_source_change_requires_its_own_request_and_cannot_borrow_a_retained_result(self):
        for key,value in [('notes',self.encounter.notes+' Correction: time was 12 minutes.'),
                          ('service_date','2026-10-17'),('encounter_id',str(uuid4()))]:
            changed=deepcopy(self.source.inputs);changed[key]=value
            with self.subTest(key=key):
                self.assertIsNone(recovery.reuse_for_context(self.encounter,self.actor,changed,
                    {**self.source.context,'time_minutes':'25'},self.source.releases,'x'*64))
        self.assertEqual(CodingRun.objects.count(),1)
        self.send.assert_not_called()

    def test_context_reuse_never_treats_unknown_transport_as_successful_or_resends_it(self):
        # This is an in-memory control; native immutable receipts are untouched.
        altered=deepcopy(self.source);altered.requests[0]['state']='uncertain'
        with patch.object(CodingRun.objects,'filter') as query:
            query.return_value.order_by.return_value=[altered]
            with self.assertRaises(ValidationError):
                recovery.reuse_for_context(self.encounter,self.actor,self.source.inputs,
                    {**self.source.context,'time_minutes':'25'},self.source.releases,'x'*64)
        self.send.assert_not_called()
