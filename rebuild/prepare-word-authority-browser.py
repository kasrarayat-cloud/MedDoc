"""Build the SYNTHETIC blank legacy form and the expected values for word-authority-browser.mjs.

Run with the candidate venv python (python-docx), no Django and no network:
    <venv>/bin/python -B prepare-word-authority-browser.py
Writes (new files only, mode 0600, directory 0700):
    .runtime/word-authority-form.docx   a BLANK two-column legacy form: a heading, an instruction paragraph and
                                        eight question rows with empty answer cells (no patient data)
    .runtime/word-authority-input.json  labels, the synthetic notes, the expected ordinary values, the signing
                                        rows that must stay untouched, and the original's sha256
Known failure L01 (legacy default path): 'Patient signature' and 'Initials' are ordinary text fields for the
legacy inspector, so the labelled note lines fill them. The browser script asserts they are NOT filled.
"""
import hashlib
import json
import os
from pathlib import Path

from docx import Document

HERE = Path(__file__).resolve().parent
OUT = HERE / '.runtime'
HEADING = 'Synthetic Legacy Intake Form'
INSTRUCTION = 'Use black ink.'
ROWS = ['Patient name', 'Chief complaint', 'Smoking status', 'Patient signature', 'Initials',
        'Consent form signed', 'Initial assessment', 'Date of visit']
NOTES = {'Patient name': 'Synthetic Example', 'Chief complaint': 'Cough for three days.',
         'Smoking status': 'Never smoker', 'Patient signature': 'SYNTHETIC-SIGNATURE-LEAK', 'Initials': 'SX',
         'Consent form signed': 'Yes', 'Initial assessment': 'Stable.', 'Date of visit': '2026-09-30'}
SIGNING = ['Patient signature', 'Initials']

os.umask(0o077)
OUT.mkdir(mode=0o700, exist_ok=True)
form = OUT / 'word-authority-form.docx'
document = Document()
document.core_properties.author = 'QuillMD synthetic fixture'
document.core_properties.title = 'Synthetic legacy signing-row form'
document.add_heading(HEADING, level=1)
document.add_paragraph(INSTRUCTION)
table = document.add_table(rows=0, cols=2)
table.style = 'Table Grid'
for label in ROWS:
    cells = table.add_row().cells
    cells[0].text = label
    cells[1].text = ''
with open(form, 'xb') as stream:      # never replace an existing fixture
    document.save(stream)
digest = hashlib.sha256(form.read_bytes()).hexdigest()
data = {
    'synthetic_only': True,
    'form': form.name,
    'original_sha256': digest,
    'heading': HEADING,
    'instruction': INSTRUCTION,
    'rows': ROWS,
    'notes': '\n'.join(f'{label}: {NOTES[label]}' for label in ROWS),
    'ordinary': {label: NOTES[label] for label in ROWS if label not in SIGNING},
    'signing': {label: NOTES[label] for label in SIGNING},
}
with open(OUT / 'word-authority-input.json', 'x') as stream:
    json.dump(data, stream, indent=2)
print(f'Prepared a blank synthetic legacy form with {len(ROWS)} rows ({len(SIGNING)} signing rows).')
