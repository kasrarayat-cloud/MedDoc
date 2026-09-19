#!/usr/bin/env python3
"""Package genuine downloaded application exports without generating or repairing them."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

ORIGINAL = 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def digest(data): return hashlib.sha256(data).hexdigest()
def text(node): return ''.join(n.text or '' for n in node.iter(W+'t'))
def require(value, message):
    if not value: raise ValueError(message)

def verify_document(payload, evidence, mapping, original_payload):
    with zipfile.ZipFile(__import__('io').BytesIO(payload)) as archive:
        document = ET.fromstring(archive.read('word/document.xml'))
    controls = {n.find(W+'sdtPr/'+W+'id').get(W+'val'): n for n in document.iter(W+'sdt')}
    with zipfile.ZipFile(__import__('io').BytesIO(original_payload)) as original_archive:
        original_document = ET.fromstring(original_archive.read('word/document.xml'))
    original_controls = {n.find(W+'sdtPr/'+W+'id').get(W+'val'): n for n in original_document.iter(W+'sdt')}
    original_paragraphs = original_document.find(W+'body').findall(W+'p')
    original_rows = original_document.findall('.//'+W+'tr')
    require(len(controls) == 28, 'Expected 28 original content controls.')
    body = document.find(W+'body')
    paragraphs = body.findall(W+'p')
    tables = body.findall(W+'tbl')
    require(len(tables) == 2, 'Expected separate qualified limb tables.')
    rows = [r for t in tables for r in t.findall(W+'tr')]
    require(len(rows) == 28, 'Expected all 28 original measurement rows.')
    for table, side in zip(tables, ('Right', 'Left')):
        section = table.findall(W+'tr')
        require(len(section) == 14, 'A limb lost measurement rows.')
        heading = text(section[0])
        require('** '+side+' Leg **' in heading and 'DIAMETER (mm)' in heading and 'REFLUX TIME (ms)' in heading,
                'Limb heading or original units missing.')
        require([i for i,r in enumerate(section) if r.find(W+'trPr/'+W+'tblHeader') is not None] == [0],
                'Only the correct own limb header may repeat.')
    answers = evidence['answers']
    location_fields = {f['locator']['row']: f for f in mapping['fields'] if 'marker' in f['locator']}
    for index, row in enumerate(rows):
        expected_label = text(original_rows[index].findall(W+'tc')[0])
        if index in location_fields:
            field = location_fields[index]
            value = answers[field['key']]['text']
            if value:
                expected_label = expected_label.replace(field['locator']['marker'], value)
        require(text(row.findall(W+'tc')[0]) == expected_label,
                'Original anatomical question or exact mapped location changed: row '+str(index))
    for field in mapping['fields']:
        value = answers[field['key']]['text']; locator = field['locator']
        if field['kind'] == 'choice':
            control = controls[locator['sdt_id']]
            items = control.findall('.//'+W+'listItem')
            original_items = original_controls[locator['sdt_id']].findall('.//'+W+'listItem')
            require([dict(n.attrib) for n in items] == [dict(n.attrib) for n in original_items],
                    'Original dropdown option attributes changed: '+field['key'])
            options = [n.get(W+'displayText', n.get(W+'val', n.get(W+'value'))) for n in items]
            options = [value for value in options if value != 'Choose an item.']
            require(options == field['options'], 'Original dropdown options changed: '+field['key'])
            actual = text(control.find(W+'sdtContent'))
            require(actual == value, 'Dropdown answer differs: '+field['key'])
        elif 'row' in locator:
            cell = rows[locator['row']].findall(W+'tc')[locator['column']]
            actual = text(cell)
            if field['kind'] == 'measurement':
                require(actual.strip() == value.removesuffix(' '+locator['unit']).strip(),
                        'Numeric answer differs or an unanswered measurement was filled: '+field['key'])
            else:
                original_label = text(original_rows[locator['row']].findall(W+'tc')[0])
                require(actual == original_label.replace(locator['marker'], value) if value else actual == original_label,
                        'Mapped location missing, truncated or silently filled: '+field['key'])
        else:
            actual = text(paragraphs[locator['body_paragraph']])
            original_text = text(original_paragraphs[locator['body_paragraph']])
            require(actual.startswith(original_text) and actual[len(original_text):].strip() == value,
                    'Mapped demographic answer is filled, missing or truncated: '+field['key'])
    missing = sum(not a['text'] for a in answers.values())
    require(missing == evidence['detail']['missingAnswers'], 'Missing count differs from reviewed answers.')
    require(evidence['review']['assessment']['complete'], 'Export lacks completed clinical review.')
    return {'mappedAnswersVerified':90,'contentControls':28,'measurementRows':28,
            'limbTables':2,'missingAnswers':missing,'nativeWordAppearance':'pending'}


def build(candidate, served, destination):
    os.umask(0o077)
    require(not destination.exists() and not destination.with_suffix('').exists(), 'Archive or staging already exists; preserve prior attempts.')
    staging = destination.with_suffix(''); staging.mkdir(mode=0o700,parents=True)
    manifest = {'syntheticOnly':True,'nativeWordAcceptance':'pending','packagingMutatesDocuments':False,'sources':{},'files':[]}
    for label, folder in [('candidate',candidate),('served',served)]:
        raw = (folder/'report.json').read_bytes(); report=json.loads(raw)
        require(report['complete'] and report['providerRequests']==0 and report['directDatabaseWrites']==0,
                'Require complete genuine browser evidence with zero provider/database writes.')
        require(report['scope'] == ('isolated candidate' if label=='candidate' else 'served private application'),
                'Candidate and served evidence are mislabelled.')
        require(report['allMissing']['finalizationRefused'] and report['allMissing']['missingAnswers']==90,
                'Require actual completely unsupported case refusal.')
        mapping=json.loads((folder/'prior-draft-state.json').read_text())['mapping']
        manifest['sources'][label]={'release':report['servedRelease'],'browserReportSha256':digest(raw),
                                   'allMissingRefused':True,'browserChecks':len(report['checks'])}
        original=(folder/report['original']['filename']).read_bytes()
        require(digest(original)==ORIGINAL, 'The accepted original changed.')
        if label=='candidate':
            name='01-original-blank-WM-IOV-Template.docx';(staging/name).write_bytes(original)
            manifest['files'].append({'file':name,'bytes':len(original),'sha256':digest(original),'kind':'accepted blank original'})
        for mode in ('partial','long'):
            detail=report[mode]; name=detail['filename']
            require(Path(name).name==name and name.endswith('.docx'),'Unsafe export filename.')
            data=(folder/name).read_bytes()
            require(digest(data)==detail['downloadedSha256']==detail['recordedSha256'] and len(data)==detail['bytes'],
                    'Downloaded export no longer matches its recorded hash/size.')
            evidence=json.loads((folder/(mode+'-review-evidence.json')).read_text())
            require(evidence['detail']==detail, 'Detailed evidence belongs to another export.')
            checks=verify_document(data,evidence,mapping,original)
            target=f'{label}-{mode}-genuine-application-export.docx';(staging/target).write_bytes(data)
            manifest['files'].append({'file':target,'bytes':len(data),'sha256':digest(data),'encounter':detail['encounter'],
                'release':detail['servedRelease'],'kind':f'{label} authenticated application download',
                'longestMappedAnswer':detail['longestMappedAnswer'],**checks})
    (staging/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (staging/'README.txt').write_text('''QuillMD Word review — SYNTHETIC DATA ONLY

These are genuine application downloads, not post-processed review copies.
The candidate pair came from an isolated private application/database. The served
pair came from the private doctor application after its recorded activation.
MANIFEST.json records each actual revision, encounter, hash and file size.
The packager neither fills nor repairs documents.

PARTIAL: 88 mapped answers are genuinely missing; patient name and exam side are
documented. All 52 numeric measurements and six anatomical locations remain
unanswered. Approved not-documented statements are supported by explicit
synthetic source lines and all 90 answers/14 statements were reviewed.

LONG: 90 supported answers, including a 14,444-character mapped patient name and
six anatomical location answers over 4,400 characters EACH. These are actual
mapped fields, not added body paragraphs. Complete end markers must remain.

ALL-MISSING REFUSAL: the application refused finalization when all 90 answers
and supporting statement evidence were absent. There is deliberately no export
of that unsupported case. The source was then explicitly edited and reviewed
through the interface to create the valid partially missing case.

Layout now separates the original Right/Left sections into two tables, adding
one empty separator paragraph. Each repeats its own limb and mm/ms header.
Long free-text location rows may flow across pages; numeric rows stay together.
All original row text, questions, options and mapped answers remain in order.

Native Microsoft Word acceptance is PENDING. Linux evaluation rendering is
separate evidence and cannot certify Word pagination. Earlier review archives
and failed attempts remain preserved; their misleading fixture labels are not
repeated here. No provider calls were needed for these clinician-entered cases.
''')
    (staging/'NATIVE-WORD-CHECKLIST.txt').write_text('''Native Microsoft Word acceptance checklist — PENDING
Record reviewer, UTC date, Word version/build, operating system and ACCEPT/REJECT.
Open the ORIGINAL beside both candidate and served pairs; do not resave evidence.

[ ] Each file opens without a repair/recovery warning; original questions,
    letterhead, headers/footers and 28 dropdown controls/options are retained.
[ ] Fonts match the original's SELECTED dropdown result. The original may use
    Aptos12 for a selected answer; that alone is not a font defect.
[ ] PARTIAL: only patient name and exam side are answered. All52 measurements,
    all6 locations and the other27 controls remain genuinely unanswered.
    No blank has silently become zero, normal, negative or a clinical finding.
[ ] LONG: patient name ends END-PATIENT-NAME. Each location contains its entire
    text and ends END-LOCATION_11/12/13/25/26/27. No clipping or hidden overflow.
[ ] Every measurement continuation page retains correct limb context AND
    DIAMETER(mm)/REFLUX TIME(ms). Right headings never label Left measurements.
    A page may end Right then start Left if BOTH section headings are visible.
[ ] Long location rows flow without losing their continuation or values;
    ordinary numeric rows and their values stay together.
[ ] All52 numeric answers remain attached to their original anatomical row.
[ ] Signature, authenticated synthetic clinician name and server timestamp
    remain legible. The preserved trailing original section may add a blank page.
[ ] Print preview and exported PDF from NATIVE WORD match the on-screen pages.
Record any failure with filename, page, expected/actual appearance and screenshot.
Do not treat OOXML flags or Linux evaluation PDFs as acceptance of these rows.
''')
    checksums=[]
    for p in sorted(staging.iterdir()):
        p.chmod(0o600);checksums.append(f'{digest(p.read_bytes())}  {p.name}')
    (staging/'SHA256SUMS.txt').write_text('\n'.join(checksums)+'\n')
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(staging.iterdir()): z.write(p,staging.name+'/'+p.name)
    destination.chmod(0o600)
    sidecar=destination.with_name(destination.name+'.sha256')
    with sidecar.open('x') as f:f.write(digest(destination.read_bytes())+'  '+destination.name+'\n')
    print(json.dumps({'archive':str(destination),'bytes':destination.stat().st_size,'sha256':digest(destination.read_bytes()),
                      'genuineExports':4,'nativeWordAcceptance':'pending'}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',required=True,type=Path);p.add_argument('--served',required=True,type=Path)
    p.add_argument('--destination',required=True,type=Path);a=p.parse_args()
    build(a.candidate,a.served,a.destination)
