"""One exact cached paid original/export with only its Plan runs hidden."""
import hashlib,io,json,socket,sys,subprocess
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
S=Path('/opt/meddoc-pro/.worktrees/v1-word-refute-saved-export-2c11e951')
sys.path.insert(0,str(S/'rebuild'))
socket.socket.connect=lambda *a,**k:(_ for _ in ()).throw(AssertionError('offline'))
from documents import word_v3 as w
from ops import sonnet5_stages as st
P=Path('/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-2/evidence/016')
B=Path(__file__).parent/'exact-paid16-hidden';B.mkdir(mode=0o700)
original=(P/'case/form.docx').read_bytes();export=(P/'export.docx').read_bytes()
assert hashlib.sha256(export).hexdigest()=='0e28f73fd6259153ab6419f89b6c5c74d217a184617123b208b696da2836f9a7'
fields=json.loads((P/'case/mapping.json').read_text());reviewed=json.loads((P/'answers-reviewed.json').read_text())['answers']
saved={k:{**v,'status':'supported' if v.get('status') in ('supported','edited') and v.get('text') else v.get('status')} for k,v in reviewed.items()}
field=next(f for f in fields if f['key']=='v3_9');assert '\n' in saved['v3_9']['text']
baseline,baseline_read=st.saved_export_verification(original,export,fields,saved,reviewed_answers=reviewed)
assert baseline['workflow_success'] and not baseline['frozen_export_verification']['workflow_success']
stream=io.BytesIO();runs_hidden=0
with ZipFile(io.BytesIO(export)) as source,ZipFile(stream,'w') as output:
 output.comment=source.comment
 for item in source.infolist():
  raw=source.read(item.filename)
  if item.filename=='word/document.xml':
   root=E.fromstring(raw);index=w.SlotIndex(w.open_package(export))
   for ref in [field['locator'],*field['locator'].get('extra',[])]:
    slot=index.by_id[ref['part']+'#'+ref['slot']]
    element=root.xpath(slot.el.getroottree().getpath(slot.el),namespaces=root.nsmap)[0]
    for run in element.iter(w.q('w:r')):
     if not list(run.iter(w.q('w:t'))):continue
     props=run.find(w.q('w:rPr'))
     if props is None:props=E.Element(w.q('w:rPr'));run.insert(0,props)
     vanish=E.SubElement(props,w.q('w:vanish'));vanish.set(w.q('w:val'),'1');runs_hidden+=1
   raw=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
  output.writestr(item,raw)
wrong=stream.getvalue();assert runs_hidden
(B/'original.docx').write_bytes(original);(B/'baseline-paid-export.docx').write_bytes(export);(B/'wrong-hidden-export.docx').write_bytes(wrong)
(B/'fields.json').write_text(json.dumps(fields,indent=2)+'\n')
# Do not duplicate signed provenance tokens: input record remains in the paid archive.
(B/'answers-reference.json').write_text(json.dumps({'path':str(P/'answers-reviewed.json'),'sha256':hashlib.sha256((P/'answers-reviewed.json').read_bytes()).hexdigest()},indent=2)+'\n')
result,read=st.saved_export_verification(original,wrong,fields,saved,reviewed_answers=reviewed)
record={'commit':'2c11e951cc2e864fc387d77ff784ea33b21f2d14','attempt':16,
 'baseline_paid_export_sha256':hashlib.sha256(export).hexdigest(),'wrong_export_sha256':hashlib.sha256(wrong).hexdigest(),
 'original_sha256':hashlib.sha256(original).hexdigest(),'runs_hidden':runs_hidden,'target':field['locator'],
 'frozen_false':not result['frozen_export_verification']['workflow_success'],'new_checker_accepted_wrong_hidden_export':result['workflow_success'],
 'all_read_back_pass':read['passed'],'exact_saved_Plan_XML_read':read['fields']['v3_9']['read']==saved['v3_9']['text'],
 'corrections':list(result['visible_break_readback_corrections']),
 'verification':result,'read_back':read,'source_clean':not subprocess.check_output(['git','status','--porcelain'],cwd=S).strip(),
 'network_DB_render_provider_calls':0,'native_Word':'not run; valid explicit hidden text property'}
(B/'result.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k in ('runs_hidden','frozen_false','new_checker_accepted_wrong_hidden_export','all_read_back_pass','wrong_export_sha256')}))
raise SystemExit(1 if result['workflow_success'] else 0)
