"""Prepare synthetic browser inputs using the actual pinned Word resolver."""
import hashlib
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from documents import inspect_template, resolve_template
from documents.sdk_word.synthetic_fixture import build_fixture

base = Path(__file__).resolve().parent
load_dotenv(base / '.env')
assert os.getenv('QUILLMD_AI_MODE') == 'fixture', 'Use an isolated fixture application.'
os.umask(0o077)
original = base.parent / 'WM IOV Template.docx'
info = inspect_template(original)
metadata = {key: info[key] for key in ('backend', 'source_sha256', 'mapping_digest')}
def resolve(request):
    return resolve_template(original, metadata, request['answers'],
                            claim_variants=request['claim_variants'], trusted_context=request['trusted_context'])
result = {'synthetic_only': True, 'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
          'fields': info['fields'], 'backend': metadata, 'scenarios': {}}
for scenario in ('positive', 'absent', 'no_prior', 'asymptomatic', 'long'):
    request, resolved = build_fixture(info, resolve, scenario=scenario, signer_name='Synthetic Doctor')
    result['scenarios'][scenario] = {'notes': request['trusted_context']['notes'],
                                   'answers': request['answers'], 'claim_variants': request['claim_variants'],
                                   'requirements': resolved['review_requirements']}
path = base / '.runtime/wm-browser-input.json'
with path.open('x') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print('Prepared five synthetic browser scenarios through the actual isolated Word resolver.')
