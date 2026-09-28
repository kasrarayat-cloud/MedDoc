from pathlib import Path
import json,re
R=Path(__file__).parent
raw=json.loads((R/'10-render-first-reading.json').read_text());out={}
def normalized(text):
 for header in ('Version 1 - 31.01.2018','Version 1 – 31.01.2018','MREC06/Q0104/133'):
  text=text.replace(header,' ')
 return ' '.join(re.sub('[☐☒□]','',text).split())
for mode,reading in raw.items():
 text=reading['full_pdf_text'];answer=reading['answer']
 out[mode]={'literal_pdf_text_match':reading['literal_match'],
  'word_sequence_after_excluding_repeated_page_headers_and_box_symbols':normalized(answer) in normalized(text),
  'expected_repetitions':answer.count('SYNTHETIC retained pressure description'),
  'visible_repetitions':text.count('SYNTHETIC retained pressure description'),
  'visual_pages_inspected':[2] if mode=='ordinary' else [2,3],
  'visual_observation':'Selected Other state and answer visible in its original column; ordinary wraps; long continues on next page. Following questions remain ordered and legible on inspected pages; no clipping or overlap observed. Inserted square glyphs visibly remain literal. PDF text extraction reorders some glyphs; exact answer text verified independently in DOCX XML. Native Word not performed.'}
(R/'10-render-visual-completeness.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
assert all(v['word_sequence_after_excluding_repeated_page_headers_and_box_symbols'] for v in out.values())
