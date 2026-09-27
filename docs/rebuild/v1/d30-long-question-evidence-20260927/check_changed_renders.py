"""Read only retained original PDF and six changed PDFs; no corpus harness execution."""
import hashlib,json,re,sys
from pathlib import Path
import pypdfium2 as pdfium
root=Path(__file__).parent.resolve()
sys.path.insert(0,str(root.parents[2]/'docs/rebuild/v1/word-eval'))
from render_eval import page_chars,overlaps
old=Path('/opt/meddoc-pro/.worktrees/v1-word-d30/rebuild/.runtime/d30-repair-20260927/render-output/original.pdf')
norm=lambda s:re.sub(r'\s+',' ',s).strip()
phrases={'A23':'If accommodation is being changed','A35':'What structured activities','A44':'Please set out any clinical changes'}
repeat='SYNTHETIC long clinician review of supervised contact.'
results=[]
for area in ('A23','A35','A44'):
    for mode in ('original','ordinary','long'):
        path=old if mode=='original' else root/'render-output'/(area+'-'+mode+'.pdf')
        chars=page_chars(path);texts=[norm(text) for text,_ in chars];whole=' '.join(texts)
        folder='capture-A35-review' if area=='A35' else 'capture-'+area
        answer=''
        if mode!='original':
            record=json.loads((root/folder/(mode+'-workflow.json')).read_text())
            field=next(f for f in record['fields'] if f['locator']['slot']==record['target_slot'])
            answer=record['answers'][field['key']]['text']
        pages=[i for i,t in enumerate(texts) if phrases[area] in t or mode=='long' and repeat in t or answer and mode=='ordinary' and norm(answer) in t]
        pdf=pdfium.PdfDocument(str(path));images=[]
        for page in pages:
            png=root/'render-output'/f'{area}-{mode}-{page+1:02d}.png'
            if png.exists():raise RuntimeError('Refusing to overwrite render image')
            pdf[page].render(scale=1.2).to_pil().save(png)
            images.append({'page':page+1,'path':str(png),'sha256':hashlib.sha256(png.read_bytes()).hexdigest()})
        pdf.close()
        result={'area':area,'mode':mode,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'pages':len(chars),'overlap_pairs':overlaps(chars),'full_answer_contiguous':not answer or norm(answer) in whole,
                'long_statement_count':whole.count(repeat) if mode=='long' else None,
                'long_statement_expected':answer.count(repeat) if mode=='long' else None,'images':images}
        results.append(result)
(root/'16-render-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps([{k:v for k,v in r.items() if k!='images'} for r in results],indent=2))
