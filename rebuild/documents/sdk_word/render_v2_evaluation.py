"""Private, watermarked layout evidence only; never a clinical export backend."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re

import aspose.words as aw
import pymupdf


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verification',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    cases=[]
    requests={name:json.loads((args.verification/(name+'-fill-request.json')).read_text()) for name in ('positive','absent','no_prior','asymptomatic','long')}
    inspect=json.loads((args.verification/'inspect.json').read_text())
    for name,request in requests.items():
        matches=[p.parent for p in args.verification.glob('case-*/request.json') if json.loads(p.read_text())==request and (p.parent/'output.docx').is_file()]
        if len(matches)!=1: raise ValueError('Require exactly one successful qualified export per scenario.')
        source=matches[0]/'output.docx'
        document=aw.Document(str(source))
        target=args.output/(name+'.evaluation.pdf')
        document.save(str(target))
        pdf=pymupdf.open(target)
        pages=[page.get_text() for page in pdf]
        text='\n'.join(pages)
        normal=''.join(text.split())
        # Only exact known evaluation lines are excluded when checking a value
        # spanning pages. Repeated footer text is not part of the DOCX answer.
        prefixes=('Evaluation Only. Created with Aspose.Words.', 'Created with an evaluation copy of Aspose.Words.', 'Temporary License https://products.aspose.com/words/temporary-license/')
        watermark_lines=[line for line in text.splitlines() if line.strip().startswith(prefixes)]
        content_normal=''.join('\n'.join(line for line in text.splitlines() if line not in watermark_lines).split())
        resolved=json.loads((args.verification/(name+'-resolved.json')).read_text())
        amounts=Counter(a['text'].removesuffix(' '+f['locator']['unit']) for f in inspect['fields'] if f['kind']=='measurement' and (a:=request['answers'][f['key']])['text'])
        expected_measurements={value: {'expected':count,'observed':len(re.findall(r'(?<![\d.])'+re.escape(value)+r'(?![\d.])',text))} for value,count in amounts.items()}
        overflows=[]
        for page_index,page in enumerate(pdf):
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    for span in line.get('spans',[]):
                        x0,y0,x1,y1=span['bbox']
                        if x0 < -2 or y0 < -2 or x1 > page.rect.width+2 or y1 > page.rect.height+2:
                            overflows.append({'page':page_index+1,'bbox':[x0,y0,x1,y1],'text_length':len(span['text'])})
            page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25)).save(args.output/(name+'.evaluation-'+str(page_index+1)+'.png'))
        signature_pages=[i+1 for i,page in enumerate(pages) if 'ElectronicallySignedOn' in ''.join(page.split())]
        result={'case':name,'source':str(source),'pages':len(pdf),'watermark_present':'aspose' in normal.lower(),
                'truncation_warning':'truncated' in normal.lower(),
                'all_resolved_statements_visible':all(''.join(r['text'].split()) in normal for r in resolved['review_requirements'] if r['kind']!='signature'),
                'evaluation_lines_excluded_from_cross_page_comparison':len(watermark_lines),
                'all_supported_text_answers_visible':all(''.join(a['text'].split()) in content_normal for f in inspect['fields'] if f['kind']!='measurement' and (a:=request['answers'][f['key']])['text']),
                'measurement_counts':expected_measurements,
                'all_measurement_counts_present':all(v['observed']>=v['expected'] for v in expected_measurements.values()),
                'signature_label_and_actual_signer_same_page':bool(signature_pages) and all(''.join(request['trusted_context']['signer_name'].split()) in ''.join(pages[i-1].split()) for i in signature_pages),
                'signature_pages':signature_pages,'text_spans_outside_page':overflows,
                'no_duplicated_is': 'isisabsent.' not in normal,
                'long_answer_complete':request['answers']['patient_name']['text'].replace(' ','') in content_normal if name=='long' else None,
                'long_payload_x_characters':content_normal.count('x') if name=='long' else None}
        cases.append(result)
        print(json.dumps(result),flush=True)
    report={'scope':'Private synthetic evaluation evidence; not application exports',
            'renderer':'Aspose.Words Python.NET 26.9.0 unlicensed evaluation',
            'font_limit':'System substitutes Liberation Serif for Times New Roman and DejaVu Sans for Aptos/Aptos Display; native Word parity is not established.',
            'results':cases}
    (args.output/'render-evidence.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
