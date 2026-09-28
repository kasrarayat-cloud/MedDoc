from pathlib import Path
import json,re
import pypdfium2 as p
R=Path(__file__).parent
out={}
for mode in ('ordinary','long'):
 doc=p.PdfDocument(R/'render-output'/f'{mode}.pdf')
 text=' '.join(' '.join(page.get_textpage().get_text_range().split()) for page in doc)
 metadata=json.loads((R/f'D03-http-after/{mode}.json').read_text())
 answer=' '.join(metadata['final_answer']['text'].split())
 expected_repeat=metadata['final_answer']['text'].count('SYNTHETIC retained pressure description')
 observed_repeat=text.count('SYNTHETIC retained pressure description')
 out[mode]={'full_answer_visible':answer in text,'expected_repetitions':expected_repeat,'visible_repetitions':observed_repeat,
 'following_numbered_questions':{str(n):bool(re.search(r'\b'+str(n)+r'\.',text)) for n in range(11,31)},
 'visual_pages_inspected':[2] if mode=='ordinary' else [2,3],
 'visual_observation':'Selected Other state and complete answer visible in its original column; ordinary wraps; long continues on next page. Following questions remain ordered and legible on inspected pages; no clipping or overlap observed. XML/preserved parts checked separately; native Word not performed.'}
 assert out[mode]['full_answer_visible']
 assert observed_repeat==expected_repeat
(R/'10-render-visual-completeness.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
