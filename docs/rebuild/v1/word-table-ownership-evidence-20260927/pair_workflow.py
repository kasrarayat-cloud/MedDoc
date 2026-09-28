"""Two known authorized DEV originals; real authenticated application, synthetic data and mocked provider only."""
import hashlib,json,os
from pathlib import Path
from core.tests.test_question_box_workflow import QuestionBoxWorkflow
R=Path(__file__).parent;C=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
class PairCapture(QuestionBoxWorkflow):
    identity='abstract'
    def source(self):
        stage=os.environ['WORD_STAGE'];assert stage in ('red','after')
        self.capture_dir=R/(self.identity+'-workflow-'+stage);self.capture_dir.mkdir(exist_ok=False)
        ledger=json.loads((C/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records']
        rec=next(r for r in ledger if r['development_id']==self.identity);assert rec['offline_filled_copy_replay_supported']
        raw=(C/rec['corpus_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==rec['sha256']
        (self.capture_dir/'original.docx').write_bytes(raw);return raw
    def uploaded(self,**kw):
        template,version=super().uploaded(**kw)
        (self.capture_dir/'uploaded-map.json').write_text(json.dumps(version.fields,ensure_ascii=False,indent=2))
        wrong=[f for f in version.fields if f['locator']['slot']==self.label_spacer]
        self.assertEqual(wrong,[], 'A plain label spacer became a second answer destination')
        return template,version
    def capture(self,mode,template,version,encounter,original,exported):
        (self.capture_dir/(mode+'.docx')).write_bytes(exported)
        field=next(f for f in version.fields if f['locator']['slot']==self.target_slot)
        record={'identity':self.identity,'original_sha256':hashlib.sha256(original).hexdigest(),
                'export_sha256':encounter.export_sha256,'target':field,'notes':encounter.notes,
                'answer':encounter.answers[field['key']],'state':encounter.status,
                'original_download_identical':True,'export_download_identical':True,
                'all_outside_target_slots_unchanged':True,'automatic_document_success':False,
                'provider':'mocked-selection; full source-unit validation; no API call'}
        (self.capture_dir/(mode+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
class D30(PairCapture):
    identity='D30';target_slot='b/tbl[0]/tr[5]/tc[1]';label_spacer='b/tbl[0]/tr[5]/tc[0]/p[2]'
    ordinary_notes='The patient was born on January 1, 1980.'
    ordinary_correction='January 1, 1980, confirmed with the patient.'
    long_correction=('SYNTHETIC birth-record verification details retained for export stress testing. '*75).strip()
class D31(PairCapture):
    identity='D31';target_slot='b/tbl[19]/tr[0]/tc[1]';label_spacer='b/tbl[19]/tr[0]/tc[0]/p[1]'
    ordinary_notes='The patient reports supervised leave every Monday.'
    ordinary_correction='The patient reports supervised leave every Monday and Wednesday.'
    long_correction=('SYNTHETIC supervised leave progress and monitoring details. '*90).strip()
