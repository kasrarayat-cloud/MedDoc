from pathlib import Path
import hashlib,json,shutil,unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import django
django.setup()
from django.conf import settings
from django.test import TestCase,RequestFactory,override_settings
from django.test.utils import setup_test_environment
from django.utils import timezone
from core.tests.test_generation_batch import BatchFixture,SETTINGS
from core import batch_jobs as jobs
from core.models import Job,Usage,ProviderReceipt,Reservation,PlatformCost
from core.security import private_path
R=Path(__file__).parent
assert settings.AI_MODE=='fixture' and settings.DATABASES['default']['NAME']=='quillmd_root_financial_20260928_0147' and settings.DATABASES['default']['PORT']=='55707' and settings.DATABASES['default']['HOST']=='127.0.0.1'
rows=[]
def save(row):
 rows.append(row);(R/'02-results.json').write_text(json.dumps(rows,indent=2)+'\n')

def snapshot(batch):
 batch.refresh_from_db();parts=list(batch.parts.select_related('job').order_by('ordinal'))
 return {'batch_state':batch.state,'pending':jobs.pending(batch.encounter),'children':[{'ordinal':p.ordinal,'state':p.job.state,'held':str(sum(p.job.reservations.filter(state='held').values_list('amount',flat=True),Decimal(0))),'usage':list(Usage.objects.filter(job=p.job).values('actual_cost','charged_cost')),'receipt':list(ProviderReceipt.objects.filter(job=p.job).values('actual_cost','provider_request_id')),'platform':list(PlatformCost.objects.filter(job=p.job).values('kind','amount'))} for p in parts]}
def serial(v):return json.loads(json.dumps(v,default=str))

@override_settings(**SETTINGS)
class FinancialInterruption(BatchFixture,TestCase):
 def resolve(self,part):
  self.user.is_staff=True;self.user.save(update_fields=['is_staff'])
  req=RequestFactory().post('/console/jobs/'+str(part.job_id)+'/resolve/',{'outcome':'release_no_cost','evidence_note':'SYNTHETIC explicit administrative financial closeout'})
  req.user=self.user
  with patch('django.contrib.messages.success'):
   out=jobs.resolve_view(req,part.job_id)
  self.assertEqual(out.status_code,302)
 def preserve(self,batch,label):
  for part in batch.parts.select_related('job').all():
   if part.job.result_path:
    p=private_path(part.job.result_path)
    if p.exists():shutil.copyfile(p,R/(label+'-part'+str(part.ordinal)+'-raw.json'))
 def test_01_recorded_interruption_then_financial_closeout_closes_every_child(self):
  batch=self.admit();calls,call=self.fake(batch);store=jobs.store_response
  admitted=str(sum(Reservation.objects.filter(job__generation_part__batch=batch,state='held').values_list('amount',flat=True),Decimal(0)))
  def exit_after_record(batch,part,raw,receipt):
   store(batch,part,raw,receipt)
   if part.ordinal==2:raise SystemExit('SYNTHETIC process death after final durable response')
  with patch('anthropic.Anthropic') as provider:
   provider.return_value.messages.create.side_effect=call
   jobs.run_one()
   with patch('core.batch_jobs.store_response',side_effect=exit_after_record),self.assertRaises(SystemExit):jobs.run_one()
   part=batch.parts.get(ordinal=2)
   Job.objects.filter(pk=part.job_id).update(started_at=timezone.now()-timedelta(minutes=6))
   jobs.mark_stale();before=serial(snapshot(batch))
   self.resolve(part);after=serial(snapshot(batch));self.preserve(batch,'01')
   dispatch=jobs.run_one()
  save({'case':'01_recorded_interrupt_admin_closeout','admitted_hold':admitted,'batch_authorized_limit':str(batch.maximum_charge),'sends':len(calls),'before':before,'after':after,'worker_after_closeout':dispatch,'expected':'No unadopted staged child stays charged or pending after whole-batch financial closeout.'})
  self.assertFalse(after['pending'],after)
  self.assertEqual(after['children'][0]['state'],'failed')
 def test_02_late_known_response_cannot_hide_after_admin_terminal_closeout(self):
  batch=self.admit();calls,call=self.fake(batch);store=jobs.store_response
  def late_store(batch,part,raw,receipt):
   Job.objects.filter(pk=part.job_id).update(started_at=timezone.now()-timedelta(minutes=6))
   jobs.mark_stale();self.resolve(part)
   store(batch,part,raw,receipt)
  with patch('anthropic.Anthropic') as provider:
   provider.return_value.messages.create.side_effect=call
   with patch('core.batch_jobs.store_response',side_effect=late_store):jobs.run_one()
   after=serial(snapshot(batch));self.preserve(batch,'02');dispatch=jobs.run_one()
  save({'case':'02_late_recorded_response_after_admin_closeout','sends':len(calls),'after':after,'worker_after_closeout':dispatch,'expected':'A newly durable known provider cost must reopen unresolved accounting or be settled/absorbed, not remain terminal without usage/platform cost.'})
  first=after['children'][0]
  self.assertTrue(first['state']=='reconciliation' or first['usage'] or first['platform'],after)

