"""Secondary page-body extraction. Raw full-page failures remain unchanged."""
import hashlib,json,re
from pathlib import Path
import pypdfium2 as pdfium
root=Path(__file__).parent
results=[]
for area,folder in [('A23','capture-A23'),('A35','capture-A35-review'),('A44','capture-A44')]:
    path=root/'render-output'/(area+'-long.pdf')
    pdf=pdfium.PdfDocument(str(path));body=[]
    for page in pdf:
        width,height=page.get_size()
        text=page.get_textpage().get_text_bounded(0,70,width,height-100)
        body.append(re.sub(r'\s+',' ',text).strip())
    record=json.loads((root/folder/'long-workflow.json').read_text())
    field=next(f for f in record['fields'] if f['locator']['slot']==record['target_slot'])
    answer=record['answers'][field['key']]['text']
    whole=' '.join(body);repeat='SYNTHETIC long clinician review of supervised contact.'
    results.append({'area':area,'pdf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'body_bounds_points':{'bottom':70,'top':'page height minus 100','left':0,'right':'page width'},
        'raw_fullpage_count_retained':89,'body_contiguous_answer':answer in whole,
        'body_full_statement_count':whole.count(repeat),'expected':90,'page_body_text':body})
    pdf.close()
(root/'20-page-break-text.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps([{k:v for k,v in r.items() if k!='page_body_text'} for r in results],indent=2))
