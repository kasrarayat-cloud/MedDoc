"""Authorized original D03 A28, synthetic notes and mocked provider only."""
import hashlib,json,os
from pathlib import Path
from core.tests.test_question_box_workflow import NestedWriteInWorkflow
from documents import word_v3 as w
R=Path(__file__).parents[1]/'word-writein-workflow-20260928'
C=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
class D03(NestedWriteInWorkflow):
    target_slot='b/tbl[0]/tr[9]/tc[0]/tbl[0]/tr[2]/tc[2]/p[0]'
    def source(self):
        stage=os.environ['WORD_STAGE'];assert stage in ('red','after')
        self.folder=R/('D03-http-'+stage);self.folder.mkdir(exist_ok=False)
        rec=next(r for r in json.loads((C/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records'] if r['development_id']=='D03')
        assert rec['offline_filled_copy_replay_supported']
        raw=(C/rec['corpus_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==rec['sha256']
        (self.folder/'original.docx').write_bytes(raw)
        return raw
    def uploaded(self,**kw):
        template,version=super().uploaded(**kw)
        (self.folder/'uploaded-map.json').write_text(json.dumps(version.fields,ensure_ascii=False,indent=2))
        return template,version
    def capture(self,mode,original,version,encounter,exported,generated):
        (self.folder/(mode+'.docx')).write_bytes(exported)
        field=next(f for f in version.fields if f['locator']['slot']==self.target_slot and f['locator']['target']['type']=='span')
        (self.folder/(mode+'.json')).write_text(json.dumps({'original_sha256':hashlib.sha256(original).hexdigest(),
          'source_engine_sha256':hashlib.sha256(Path(w.__file__).read_bytes()).hexdigest(),
          'field':field,'notes':encounter.notes,'generated_answer':generated,'final_answer':encounter.answers[field['key']],
          'export_sha256':encounter.export_sha256,'state':encounter.status,'original_download_identical':True,
          'mapping_review_roundtrip_identical':True,'outside_targets_unchanged':True,
          'all_missing_package_members_unchanged':mode=='missing',
          'checkbox_selection':'independent explicit clinician selection; never inferred from write-in',
          'document_success':False},ensure_ascii=False,indent=2))
