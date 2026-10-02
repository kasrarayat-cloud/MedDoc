import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","quillmd.settings")
import django
django.setup()
from pathlib import Path
import hashlib,json
from django.test import TestCase,override_settings
from core.tests.test_v3_sentence_syntax import SentenceWorkflow,A35,ACTIVITY
from core.tests.test_word_v3_workflow import V3,V3Fixture
from core.models import Usage
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-notes-workflows/rebuild/.runtime/notes-workflows-20260927')
@override_settings(**V3)
class D30SyntaxWorkflow(V3Fixture,TestCase):
 exercise=SentenceWorkflow.exercise
 def test_original_authorized_D30_A35(self):
  source=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev/originals/D30-fdeafbee872f.docx').read_bytes()
  self.assertEqual(hashlib.sha256(source).hexdigest(),'fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f')
  correction=ACTIVITY+' Support with disclosure of offending history is not documented in the source notes.'
  encounter,original,exported=self.exercise(A35,ACTIVITY,correction=correction,source=source,target_slot='b/tbl[18]/tr[0]/tc[0]')
  capture=ROOT/'capture-D30-A35-subject-final';capture.mkdir(exist_ok=False)
  (capture/'original.docx').write_bytes(original);(capture/'exported.docx').write_bytes(exported)
  field=next(f for f in encounter.template_version.fields if f['locator']['slot']=='b/tbl[18]/tr[0]/tc[0]')
  usage=Usage.objects.get(job__encounter=encounter)
  (capture/'result.json').write_text(json.dumps({'notes':encounter.notes,'field':field,'final_answer':encounter.answers[field['key']], 'field_count':len(encounter.template_version.fields),'warnings':encounter.template_version.template.warnings,'simulated':usage.simulated,'charged_cost':str(usage.charged_cost),'original_sha256':hashlib.sha256(original).hexdigest(),'export_sha256':encounter.export_sha256,'source_activities_supported':True,'whole_compound_question_automatic':False,'disclosure_not_documented':True},indent=2))
  page=self.client.get(f'/encounters/{encounter.pk}/')
  (capture/'final-page.html').write_bytes(page.content)

if __name__ == "__main__":
 from django.test.runner import DiscoverRunner
 raise SystemExit(DiscoverRunner(verbosity=2,keepdb=True,interactive=False).run_tests([__name__+".D30SyntaxWorkflow"]))
