from pathlib import Path
import hashlib,json
import pypdfium2 as pdfium
R=Path(__file__).parent
paths={'original':Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev/renders/D03-29dfcdd8a5da/original.pdf'),**{k:R/'render-output'/f'{k}.pdf' for k in ('ordinary','long')}}
out={}
for key,path in paths.items():
 doc=pdfium.PdfDocument(path);pages=[]
 for i in range(len(doc)):
  page=doc[i];text=page.get_textpage().get_text_range()
  if 'headaches usually feel like' in text or 'SYNTHETIC retained' in text:
   image=R/'render-output'/f'{key}-page-{i+1}.png';assert not image.exists()
   page.render(scale=1.3).to_pil().save(image)
   pages.append({'page':i+1,'text':text,'png':str(image),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()})
 out[key]={'pdf':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(doc),'affected':pages}
(R/'08-render-comparison.json').write_text(json.dumps(out,indent=2))
print(json.dumps({k:{'pages':v['pages'],'affected_pages':[p['page'] for p in v['affected']]} for k,v in out.items()}))
