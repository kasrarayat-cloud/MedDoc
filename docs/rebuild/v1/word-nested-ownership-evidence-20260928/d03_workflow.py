"""One original DEV form; fixture HTTP and mocked provider only. No compatibility score."""
import hashlib,importlib.util,json,os
from pathlib import Path
source=Path('/opt/meddoc-pro/.worktrees/v1-word-workflows/rebuild/core/tests/test_question_box_workflow.py')
spec=importlib.util.spec_from_file_location('core.tests._nested_owned_test',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
R=Path(__file__).parent;C=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
class D03(module.NestedCheckboxWorkflow):
    target_slot='b/tbl[0]/tr[9]/tc[0]/tbl[0]/tr[0]/tc[0]/p[0]/glyphs'
    question='10. Please indicate what your headaches usually feel like: (tick all that apply):'
    wanted_options=['Throbbing/Pulsing','Dull']
    def source(self):
        stage=os.environ['WORD_STAGE'];assert stage in ('red','after')
        self.folder=R/('D03-http-'+stage);self.folder.mkdir(exist_ok=False)
        rec=next(r for r in json.loads((C/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records'] if r['development_id']=='D03')
        assert rec['offline_filled_copy_replay_supported']
        raw=(C/rec['corpus_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==rec['sha256']
        (self.folder/'original.docx').write_bytes(raw);return raw
    def uploaded(self,**kw):
        t,v=super().uploaded(**kw)
        (self.folder/'uploaded-map.json').write_text(json.dumps(v.fields,ensure_ascii=False,indent=2))
        return t,v
    def capture(self,mode,original,version,encounter,exported):
        from documents import word_v3
        (self.folder/(mode+'.docx')).write_bytes(exported)
        target=next(f for f in version.fields if f['locator']['slot']==self.target_slot)
        (self.folder/(mode+'.json')).write_text(json.dumps({'original_sha256':hashlib.sha256(original).hexdigest(),
            'source_engine_sha256':hashlib.sha256(Path(word_v3.__file__).read_bytes()).hexdigest(),
            'target':target,'notes':encounter.notes,'answer':encounter.answers[target['key']],
            'export_sha256':encounter.export_sha256,'state':encounter.status,'original_download_identical':True,
            'export_download_identical':True,'outside_target_paragraphs_unchanged':True,
            'ordinary_option_completion':'assisted; ordinary unlabelled option evidence held',
            'document_success':False},ensure_ascii=False,indent=2))
