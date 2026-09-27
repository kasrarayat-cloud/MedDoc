from pathlib import Path
import json,re,sys
import pypdfium2 as pdfium
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'docs/rebuild/v1/word-eval'))
import render_eval
root=Path(__file__).parent/'render-output'
normal=lambda text:re.sub(r'\s+','',text)
original=render_eval.page_chars(root/'workflow-original.pdf')
original_text=normal(''.join(text for text,_ in original))
results=[]
for name in ['original','export','missing','long']:
 p=root/f'workflow-{name}.pdf';pages=render_eval.page_chars(p)
 text=''.join(t for t,_ in pages);compact=normal(text)
 expected='Rest and return if symptoms worsen.' if name=='export' else 'Synthetic detailed plan. '*80 if name=='long' else ''
 # Preserve all original wording in source order even when the answer splits it.
 it=iter(compact);preserved=all(any(ch==candidate for candidate in it) for ch in original_text)
 result={'document':p.name,'pages':len(pages),'overlap_pairs':render_eval.overlaps(pages),'original_wording_subsequence':preserved,
         'entire_answer_present':normal(expected) in compact,'long_answer_repetitions':compact.count(normal('Synthetic detailed plan.')) if name=='long' else None}
 assert result['overlap_pairs']<=render_eval.overlaps(original),result
 assert preserved and result['entire_answer_present'],result
 pdf=pdfium.PdfDocument(str(p))
 for i in range(len(pdf)):
  pdf[i].render(scale=1.5).to_pil().save(root/f'workflow-{name}-page-{i+1}.png')
 (root/f'workflow-{name}.txt').write_text(text)
 results.append(result)
(root/'render-comparison.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
