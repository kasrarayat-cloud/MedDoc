"""Authenticated recovery families; all provider calls use explicit test doubles."""
from copy import deepcopy
from decimal import Decimal
import os
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
from anthropic import BadRequestError
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core import ai_stages, generation_recovery as recovery
from core.jobs import enqueue, run_one
from core.live_results import result_snapshot
from core.models import AuditEvent, Job, Reservation, Usage
from core.tests.test_billing_policy import STORAGES
from core.tests.test_generation_recovery import RecoveryFixture, NEW_RELEASE, NEW_TRANSPORT

NEXT_RELEASE='d'*40
# This marker exercises recovery admission only. It does not claim that a new
# provider codec exists or that its schema has been admitted by a provider.
NEXT_TRANSPORT='TESTONLY-next-distinct-schema-transport'


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',
    STORAGES=STORAGES,RELEASE_SHA=NEW_RELEASE)
class GenerationRecoveryChainTests(RecoveryFixture,TestCase):
    def setUp(self):
        super().setUp()
        with patch.object(ai_stages,'pipeline_config',side_effect=self.prospective):
            self.second=self.retry()
        response=httpx.Response(400,request=httpx.Request('POST','https://synthetic.invalid/messages'),
            headers={'request-id':'req_offlineSecond'+self.second.pk.hex},
            json={'error':{'type':'invalid_request_error','message':'TESTONLY schema rejection'}})
        error=BadRequestError('TESTONLY rejection',response=response,body=response.json())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-offline-placeholder'}),\
             patch.object(ai_stages,'_response',side_effect=error)as provider:
            self.assertTrue(run_one());self.assertEqual(provider.call_count,1)
        self.second.refresh_from_db();self.assertEqual(self.second.state,'reconciliation')
        self.second_job=deepcopy(Job.objects.filter(pk=self.second.pk).values().get())
        self.second_stage=deepcopy(self.second.ai_stage_receipts.values().get())
        self.second_reservations=list(Reservation.objects.filter(job=self.second).values())
        self.old_audits=list(AuditEvent.objects.filter(target__in=[str(self.old.pk),str(self.second.pk),
            str(self.old.ai_stage_receipts.get().pk),str(self.second.ai_stage_receipts.get().pk)]).values())
        # Only recovery admission/budgeting is under test for the next marker.
        # Preserve real quote arithmetic via an explicit limits test double; no
        # third-stage provider execution or unsupported codec admission occurs.
        limits=ai_stages.generation_limits
        def next_limits(config):
            if config.get(recovery.TRANSPORT_KEY)==NEXT_TRANSPORT:
                config={**config,recovery.TRANSPORT_KEY:NEW_TRANSPORT}
            return limits(config)
        replacement=patch.object(ai_stages,'generation_limits',side_effect=next_limits)
        replacement.start();self.addCleanup(replacement.stop)

    def next_config(self,config):
        return {**self.original_pipeline(config),recovery.TRANSPORT_KEY:NEXT_TRANSPORT}

    def next_offer(self,config=None):
        with override_settings(RELEASE_SHA=NEXT_RELEASE):
            return recovery.offer(self.encounter,self.user,config or self.next_config(self.config()))

    def next_job(self,token=None):
        with override_settings(RELEASE_SHA=NEXT_RELEASE),\
             patch.object(ai_stages,'pipeline_config',side_effect=self.next_config):
            return enqueue(self.encounter,self.user,config=self.config(),
                expected_revision=self.encounter.revision,
                recovery_token=self.next_offer()if token is None else token)

    def histories_unchanged(self):
        self.unchanged()
        self.assertEqual(Job.objects.filter(pk=self.second.pk).values().get(),self.second_job)
        self.assertEqual(self.second.ai_stage_receipts.values().get(),self.second_stage)
        self.assertEqual(list(Reservation.objects.filter(job=self.second).values()),self.second_reservations)
        self.assertFalse(Usage.objects.filter(job=self.second).exists())
        self.assertEqual(list(AuditEvent.objects.filter(target__in=[str(self.old.pk),str(self.second.pk),
            str(self.old.ai_stage_receipts.get().pk),str(self.second.ai_stage_receipts.get().pk)]).values()),self.old_audits)

    def test_two_authenticated_rejections_offer_one_new_tip_without_rewriting_history(self):
        proof=recovery.rejection(self.second)
        self.assertEqual(proof['prior_calls'],2)
        quotes=self.old.ai_stage_receipts.get().quote_maximum+self.second.ai_stage_receipts.get().quote_maximum
        self.assertEqual(Decimal(proof['prior_quote']),quotes)
        token=self.next_offer();self.assertIsNotNone(token)
        self.assertEqual(signing.loads(token,salt=recovery.SALT)['job'],str(self.second.pk))
        third=self.next_job(token);again=self.next_job(token)
        self.assertEqual(third.pk,again.pk);self.assertTrue(again.reused)
        self.assertTrue(recovery.linked(self.old,self.second));self.assertTrue(recovery.linked(self.second,third))
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),3)
        self.assertEqual(recovery.family_ids(third),{self.old.pk,self.second.pk,third.pk})
        self.assertEqual(enqueue(self.encounter,self.user,config=self.config()).pk,third.pk)
        self.assertTrue(result_snapshot(self.encounter,[third,self.second,self.old])['pending'])
        self.histories_unchanged()

    def test_two_old_calls_leave_three_calls_and_all_old_unknown_quotes_in_shared_budget(self):
        third=self.next_job()
        rows=[SimpleNamespace(quote_maximum=Decimal('1.63'),actual_cost=Decimal('0.01'))for _ in range(3)]
        ceiling=ai_stages.maximum_cost(third.config)
        self.assertEqual(ceiling,Decimal('8.15'))
        prior=Decimal(recovery.rejection(self.second)['prior_quote'])
        remaining=ceiling-prior-Decimal('3.26')
        with transaction.atomic():
            for used in range(3):recovery.enforce_stage_budget(third,rows[:used],Decimal('1.63'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(third,rows,Decimal('0.01'))
            recovery.enforce_stage_budget(third,rows[:2],remaining)
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(third,rows[:2],remaining+Decimal('0.000000000001'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(third,[SimpleNamespace(quote_maximum=Decimal('1'),actual_cost=ceiling)],Decimal('0.01'))
        self.histories_unchanged()

    def test_no_unchanged_transport_reuse_ancestor_transport_or_same_release(self):
        self.assertIsNone(self.token())
        config=self.next_config(self.config())
        config[recovery.TRANSPORT_KEY]='anthropic-shared-local-definitions-v1'
        self.assertIsNone(self.next_offer(config))
        with override_settings(RELEASE_SHA=NEW_RELEASE):
            self.assertIsNone(recovery.offer(self.encounter,self.user,self.next_config(self.config())))
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),2)
        self.histories_unchanged()

    def test_changing_source_revision_actor_rates_or_definitions_cannot_extend_family(self):
        token=self.next_offer();self.assertIsNotNone(token)
        for changes in [{'input_rate':'3'},{'model':'other-model'},{'semantic_max_calls':True}]:
            config={**self.next_config(self.config()),**changes}
            self.assertIsNone(self.next_offer(config))
        self.encounter.notes+=' TESTONLY changed source';self.assertIsNone(self.next_offer())
        self.encounter.notes=self.encounter.notes[:-24]
        value=signing.loads(token,salt=recovery.SALT);value['actor']=str(uuid4())
        with self.assertRaises(ValidationError):self.next_job(signing.dumps(value,salt=recovery.SALT))
        self.histories_unchanged()

    def test_fork_even_with_a_forged_unapproved_branch_stays_busy_and_unrecoverable(self):
        Job.objects.create(encounter=self.encounter,user=self.user,revision=self.encounter.revision,
            request_key='TESTONLY-fork-'+uuid4().hex,config={recovery.RECOVERY_KEY:{'job':str(self.old.pk)}})
        self.assertFalse(recovery.linked(self.old,self.second))
        self.assertIsNone(recovery.rejection(self.second));self.assertIsNone(self.next_offer())
        self.assertTrue(recovery.pending_jobs(Job.objects.filter(encounter=self.encounter)))
        self.histories_unchanged()

    def test_cycle_and_missing_or_wrong_parent_never_authenticate(self):
        second=deepcopy(self.second)
        for parent in [str(second.pk),str(uuid4()),'not-a-job-uuid',None]:
            second.config=deepcopy(self.second.config);second.config[recovery.RECOVERY_KEY]['job']=parent
            with self.subTest(parent=parent):
                self.assertFalse(recovery.linked(self.old,second));self.assertIsNone(recovery.rejection(second))
                self.assertEqual(recovery.family_ids(second),set())
        first_id,second_id=uuid4(),uuid4()
        first=Job.objects.create(pk=first_id,encounter=self.encounter,user=self.user,request_key='TESTONLY-cycle-'+first_id.hex,
            config={recovery.RECOVERY_KEY:{'job':str(second_id)}})
        second=Job.objects.create(pk=second_id,encounter=self.encounter,user=self.user,request_key='TESTONLY-cycle-'+second_id.hex,
            config={recovery.RECOVERY_KEY:{'job':str(first_id)}})
        self.assertIsNone(recovery.rejection(first));self.assertFalse(recovery.linked(first,second))

    def test_ancestor_audit_loss_duplicate_or_numeric_equivalence_does_not_authenticate(self):
        event=AuditEvent.objects.get(action='generation.recovery_queued',target=str(self.second.pk))
        second=deepcopy(self.second)
        for key,value in [('prior_calls',True),('revision',False),('prior_quote',1.63),('extra','TESTONLY')]:
            second.config=deepcopy(self.second.config);second.config[recovery.RECOVERY_KEY][key]=value
            with self.subTest(key=key):self.assertFalse(recovery.linked(self.old,second))
        AuditEvent.objects.create(actor=self.user,department=self.department,organization=self.department.organization,
            action=event.action,target=event.target,details=event.details)
        self.assertFalse(recovery.linked(self.old,self.second));self.assertIsNone(self.next_offer())

    def test_invalid_cost_inputs_refuse_before_a_new_stage(self):
        third=self.next_job()
        for value in [True,1,1.0,'1',Decimal('-1'),Decimal('NaN'),Decimal('Infinity')]:
            with self.subTest(value=value),transaction.atomic(),self.assertRaises(ai_stages.StageNotSent):
                recovery.enforce_stage_budget(third,[],value)
        self.histories_unchanged()

    def test_verified_final_tip_ends_busy_state_without_resolving_two_financial_holds(self):
        third=self.next_job()
        # A state-only reader check, not clinical acceptance or provider success.
        Job.objects.filter(pk=third.pk).update(state='succeeded',finished_at=timezone.now())
        third.refresh_from_db()
        self.assertFalse(recovery.pending_jobs([self.old,self.second,third]))
        self.assertEqual(recovery.latest(self.old).pk,third.pk)
        self.assertEqual(self.encounter.answers,{})
        self.histories_unchanged()
