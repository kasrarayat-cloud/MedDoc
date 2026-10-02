from pathlib import Path
import hashlib,json
import pypdfium2 as pdfium
R=Path(__file__).parent
paths={'original':Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev/renders/D03-29dfcdd8a5da/original.pdf'),'ordinary':R/'render-output/D03-q10-ordinary.pdf'}
out={}
for key,path in paths.items():
 doc=pdfium.PdfDocument(path);pages=[]
 for i in range(len(doc)):
  page=doc[i];text=page.get_textpage().get_text_range()
  if 'headaches usually feel like' in text:
   image=R/'render-output'/f'D03-q10-{key}-page-{i+1}.png'
   assert not image.exists();page.render(scale=1.5).to_pil().save(image)
   pages.append({'page':i+1,'text':text,'png':str(image),'png_sha256':hashlib.sha256(image.read_bytes()).hexdigest()})
 out[key]={'pdf':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(doc),'affected':pages}
p=R/'15-render-comparison.json';assert not p.exists();p.write_text(json.dumps(out,indent=2));print(json.dumps({k:{'pages':v['pages'],'affected_pages':[p['page'] for p in v['affected']]} for k,v in out.items()}))
