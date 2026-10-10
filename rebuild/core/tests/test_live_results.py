"""Authenticated observation and persisted generation replay guards, on real PostgreSQL."""
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase,override_settings
from django.utils import timezone

from core.jobs import enqueue,run_one,cancel
from core.models import AuditEvent,Encounter,Job,Usage,ProviderReceipt,PlatformCost
from core.tests.test_billing_boundary import BoundaryFixture,LIVE,adopted_live_result
from core.tests.test_billing_policy import STORAGES


@override_settings(AI_MODE='fixture',ADMIN_SITE=False,STORAGES=STORAGES)
class LiveResults(BoundaryFixture,TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.encounter.answers={};self.encounter.save(update_fields=['answers'])
        self.url=f'/encounters/{self.encounter.pk}/'

    def snapshot(self):
        response=self.client.get(self.url+'status/')
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response['Cache-Control'])
        return response.json()

    def generate(self,revision=None,quote=None):
        payload={'revision':str(self.encounter.revision if revision is None else revision)}
        if quote:payload['usage_quote']=quote
        return self.client.post(self.url+'generate/',payload,HTTP_ACCEPT='application/json')

    def test_initial_page_and_polls_use_same_version_without_job_or_audit_mutation(self):
        page=self.client.get(self.url)
        before=(Job.objects.count(),Usage.objects.count(),AuditEvent.objects.count())
        first=self.snapshot();second=self.snapshot()
        self.assertEqual(first,second)
        self.assertEqual(first['result_version'],page.context['live_result_version'])
        self.assertEqual((Job.objects.count(),Usage.objects.count(),AuditEvent.objects.count()),before)
        self.assertFalse(first['pending']);self.assertIsNone(first['latest_job'])
        self.assertEqual(first['answers_preview'],[])

    def test_queued_running_review_ready_snapshots_and_same_revision_replay(self):
        first=self.generate();self.assertEqual(first.status_code,200)
        job=Job.objects.get(encounter=self.encounter)
        self.assertFalse(first.json()['reused']);self.assertTrue(first.json()['pending'])
        queued=self.snapshot();self.assertEqual(queued['latest_job']['state'],'queued')
        Job.objects.filter(pk=job.pk).update(state='running',started_at=timezone.now())
        running=self.snapshot();self.assertEqual(running['latest_job']['state'],'running')
        self.assertNotEqual(queued['result_version'],running['result_version'])
        Job.objects.filter(pk=job.pk).update(state='queued')
        self.assertTrue(run_one())
        ready=self.snapshot()
        self.assertFalse(ready['pending']);self.assertEqual(ready['status'],'review')
        self.assertEqual(ready['latest_job']['state'],'succeeded')
        self.assertTrue(ready['answers_preview'])
        again=self.generate()
        self.assertEqual(again.status_code,200);self.assertTrue(again.json()['reused'])
        self.assertEqual(again.json()['latest_job']['id'],str(job.pk))
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),1)
        self.assertEqual(Usage.objects.filter(job=job).count(),1)
        self.assertFalse(run_one())

    def test_cancelled_revision_is_reused_until_explicit_source_save(self):
        first=self.generate();job=Job.objects.get(encounter=self.encounter)
        cancel(job,self.user)
        repeated=self.generate()
        self.assertTrue(repeated.json()['reused'])
        self.assertEqual(repeated.json()['latest_job']['id'],str(job.pk))
        self.assertEqual(repeated.json()['latest_job']['state'],'cancelled')
        self.assertIn('save the source notes again',repeated.json()['message'])
        saved=self.client.post(self.url+'notes/',{'revision':self.encounter.revision,'notes':self.encounter.notes})
        self.assertEqual(saved.status_code,302)
        self.encounter.refresh_from_db()
        fresh=self.generate();self.assertFalse(fresh.json()['reused'])
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),2)
        job.refresh_from_db();self.assertEqual(job.state,'cancelled')

    def test_status_tenant_and_authentication_boundaries_and_read_only_method(self):
        self.assertEqual(self.client.post(self.url+'status/').status_code,405)
        other=self.make_scope('other-live-results')[0]
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url+'status/').status_code,404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url+'status/').status_code,302)
        self.assertFalse(Job.objects.exists())

    def test_stale_revision_refuses_json_without_new_job(self):
        response=self.generate(revision=self.encounter.revision+1)
        self.assertEqual(response.status_code,409)
        self.assertIn('Source notes changed',response.json()['error'])
        self.assertIn('no-store',response['Cache-Control'])
        self.assertFalse(Job.objects.exists())

    def test_poll_does_not_expose_private_provider_or_accounting_payload(self):
        self.generate();job=Job.objects.get(encounter=self.encounter)
        result=self.snapshot()
        self.assertEqual(set(result['latest_job']),{'id','kind','state','display_error','revision'})
        for forbidden in ('notes','config','request_key','result_path','provider_output','provider_request_id'):
            self.assertNotIn(forbidden,result)
            self.assertNotIn(forbidden,result['latest_job'])

    @override_settings(**LIVE)
    def test_failed_paid_attempt_replay_never_duplicates_provider_usage_or_charge(self):
        quote=self.client.get(self.url).context['usage_quote']
        first=self.generate(quote=quote);self.assertEqual(first.status_code,200)
        job=Job.objects.get(encounter=self.encounter)
        returned=adopted_live_result(self.encounter.notes,self.encounter.template_version.fields,
            'req_live_failed_replay',Decimal('0.001'))
        with (patch('core.jobs.generation.generate',return_value=returned) as provider,
              patch('core.jobs.generation.validated',side_effect=ValidationError('Controlled invalid evidence'))):
            self.assertTrue(run_one())
            job.refresh_from_db();self.assertEqual(job.state,'failed')
            before=(list(Usage.objects.values()),list(ProviderReceipt.objects.values()),list(PlatformCost.objects.values()))
            for _ in range(3):
                replay=self.generate(quote=quote)
                self.assertEqual(replay.status_code,200)
                self.assertTrue(replay.json()['reused'])
                self.assertEqual(replay.json()['latest_job']['id'],str(job.pk))
                self.assertFalse(run_one())
            self.assertEqual(provider.call_count,1)
        self.assertEqual(Job.objects.count(),1)
        self.assertEqual((list(Usage.objects.values()),list(ProviderReceipt.objects.values()),list(PlatformCost.objects.values())),before)
        state=self.snapshot();self.assertFalse(state['pending'])
        self.assertIn('not charged',state['latest_job']['display_error'])
        self.assertEqual(Usage.objects.get(job=job).actual_cost,Decimal('0.001'))
