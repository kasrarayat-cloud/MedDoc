import hashlib,json,re,sys
from pathlib import Path
import pypdfium2 as pdfium
R=Path(__file__).parent.resolve();sys.path.insert(0,str(R.parents[2]/'docs/rebuild/v1/word-eval'))
from render_eval import page_chars,overlaps
norm=lambda s:re.sub(r'\s+',' ',s).strip();output=[]
for identity,label in [('D30','Date of Birth'),('D31','Report on leave')]:
 for mode in ('original','ordinary','long'):
  pdfpath=next(Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev/renders').glob(identity+'-*/original.pdf')) if mode=='original' else R/'render-output'/(identity+'-'+mode+'.pdf')
  chars=page_chars(pdfpath);texts=[norm(t) for t,_ in chars];whole=' '.join(texts)
  record=json.loads((R/(identity+'-workflow-after')/(mode+'.json')).read_text()) if mode!='original' else {}
  answer=record.get('answer',{}).get('text','');pages=[i for i,t in enumerate(texts) if label in t or answer and answer[:45] in t]
  pdf=pdfium.PdfDocument(str(pdfpath));images=[]
  for page in pages:
   dest=R/'render-output'/f'{identity}-{mode}-{page+1:02d}.png';assert not dest.exists()
   pdf[page].render(scale=1.2).to_pil().save(dest);images.append(str(dest))
  pdf.close()
  output.append({'identity':identity,'mode':mode,'pdf':str(pdfpath),'pdf_sha256':hashlib.sha256(pdfpath.read_bytes()).hexdigest(),'pages':len(chars),'overlap_pairs':overlaps(chars),'answer_present_contiguous':not answer or norm(answer) in whole,'answer_prefix_count':whole.count(answer[:45]) if answer else None,'images':images,'page_texts':[texts[i] for i in pages]})
(R/'15-render-check.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
for x in output:print(json.dumps({k:v for k,v in x.items() if k!='page_texts'},ensure_ascii=False))
