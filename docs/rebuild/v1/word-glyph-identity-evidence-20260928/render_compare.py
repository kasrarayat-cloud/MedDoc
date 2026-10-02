from pathlib import Path
import hashlib,json,pypdfium2 as pdfium
r=Path(__file__).resolve().parents[1]/'word-nested-diagnosis-20260928';g=Path(__file__).parent
p=r/'render-output/D03-q10-glyph.pdf';doc=pdfium.PdfDocument(p);png=g/'D03-q10-glyph-page-2.png';doc[1].render(scale=1.5).to_pil().save(png)
old=r/'render-output/D03-q10-ordinary-page-2.png'
out={'pages':len(doc),'pdf':str(p),'pdf_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'png':str(png),'png_sha256':hashlib.sha256(png.read_bytes()).hexdigest(),'preceding_workflow_png_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'affected_render_identical':png.read_bytes()==old.read_bytes()}
(g/'12-render-equivalence.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
