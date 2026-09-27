"""Secondary explicit body-bound comparison; preserve raw full-page extraction failures."""
import json,re
from pathlib import Path
import pypdfium2 as pdfium
R=Path(__file__).parent;records=[]
for identity,bottom,top_margin in [('D30',70,100),('D31',40,50)]:
 d=pdfium.PdfDocument(str(R/'render-output'/(identity+'-long.pdf')));body=[]
 for p in d:
  width,height=p.get_size();body.append(re.sub(r'\s+',' ',p.get_textpage().get_text_bounded(0,bottom,width,height-top_margin)).strip())
 answer=json.loads((R/(identity+'-workflow-after')/'long.json').read_text())['answer']['text'];whole=' '.join(body)
 records.append({'id':identity,'bound_reason':'Measured header/footer glyph positions and visibly inspected page continuations; no answer region excluded','bottom':bottom,'top_margin':top_margin,'full_answer_present':answer in whole,'expected_sentences':len(re.findall(r'\.',answer)),'complete_sentence_count':whole.count(answer.split('. ')[0]+'.'),'body_text':body})
 d.close()
(R/'17-body-continuation.json').write_text(json.dumps(records,indent=2))
print(json.dumps([{k:v for k,v in r.items() if k!='body_text'} for r in records],indent=2))
