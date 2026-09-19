"""Bounded real-provider synthetic smoke; creates normal auditable job/usage rows."""
import hashlib,json,time,wave
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from core.models import User,Encounter,TemplateVersion,Patient,Job,Usage
from core.jobs import enqueue
from core.security import private_path
from django.utils import timezone
class Command(BaseCommand):
    def handle(self,*args,**options):
        if not settings.SYNTHETIC_ONLY or settings.AI_MODE!='live':raise CommandError('Live synthetic-only mode required.')
        user=User.objects.get(email='doctor@synthetic.quillmd.invalid')
        version=TemplateVersion.objects.filter(created_by=user,template__name='Clinical assessment').first()
        patient=Patient.objects.filter(department=version.template.department).first()
        e=Encounter.objects.create(department=patient.department,patient=patient,template_version=version,created_by=user,service_date=timezone.localdate(),notes='History: Synthetic patient reports left wrist discomfort.\nFindings: No deformity documented.\nPlan: Follow-up assessment documented.')
        generation=enqueue(e,user)
        self.wait(generation)
        e.refresh_from_db()
        assert all(a['status']=='supported' for a in e.answers.values())
        audio_path='audio/live-synthetic-silence.wav';p=private_path(audio_path);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*32000)
        p.chmod(0o600)
        transcription=enqueue(e,user,'transcription',audio_path)
        self.wait(transcription)
        first=Usage.objects.get(job=generation);second=Usage.objects.get(job=transcription)
        assert first.charged_cost==first.actual_cost*__import__('decimal').Decimal('1.5')
        assert second.charged_cost==second.actual_cost*__import__('decimal').Decimal('1.5')
        result={'verified_at':__import__('django.utils.timezone',fromlist=['now']).now().isoformat(),'generation':{'state':generation.state,'provider':first.provider,'actual_cost':str(first.actual_cost),'charge':str(first.charged_cost),'units':first.units},'transcription':{'state':transcription.state,'provider':second.provider,'actual_cost':str(second.actual_cost),'charge':str(second.charged_cost),'units':second.units},'cost_basis':'actual_cost is the configured-rate cost: provider-reported units priced at the configured rates; not reconciled to a provider invoice.','limits':'Transcription smoke uses 1-second generated silence; speech accuracy is not assessed.'}
        (settings.BASE_DIR/'.runtime/live-provider-verification.json').write_text(json.dumps(result,indent=2)+'\n')
        self.stdout.write(json.dumps(result))
    def wait(self,job):
        for _ in range(60):
            job.refresh_from_db()
            if job.state not in ['queued','running']:break
            time.sleep(2)
        if job.state!='succeeded':raise CommandError(f'Synthetic job {job.kind} ended in {job.state}: {job.error}')
