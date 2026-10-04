"""Fixed, immutable inputs for a prospective cached-response transfer. No application imports."""
from pathlib import Path
import hashlib
import json

PAID_SOURCE = '5bf3024508c65d99d2e8573fd87e920a754a65e1'
ROOT = Path('/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-4/evidence')
GROUPS = {'typed-first': tuple(range(2, 9)), 'typed-second': tuple(range(9, 16)), 'voice': (17, 19)}
SEALS = json.loads(Path(__file__).with_name('transfer-seals.json').read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(attempt, root=ROOT):
    if attempt not in tuple(range(2, 16)) + (17, 19):
        raise ValueError('Only the sixteen declared closed generation artifacts are eligible.')
    folder = root / f'{attempt:03}'
    manifest_bytes = (folder / 'manifest.json').read_bytes()
    if sha(manifest_bytes) != SEALS[f'{attempt:03}']:
        raise ValueError('The prospectively sealed paid attempt manifest differs.')
    manifest = json.loads(manifest_bytes)
    if manifest['runner']['commit'] != PAID_SOURCE:
        raise ValueError('The retained source identity differs.')
    hashes = {}
    for name, record in manifest['evidence'].items():
        path = folder / name
        if path.resolve().parent != folder.resolve() and not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError('Evidence cannot escape its closed attempt folder.')
        expected = record['sha256'] if isinstance(record, dict) else record
        actual = sha(path.read_bytes())
        if actual != expected:
            raise ValueError(f'Changed retained evidence: {name}')
        hashes[name] = actual
    request = json.loads((folder / 'request.json').read_text())['body_json']
    payload = json.loads(request['messages'][0]['content'])
    fields = json.loads((folder / 'case/mapping.json').read_text())
    notes = (folder / 'case/notes.txt').read_text()
    provider = json.loads((folder / 'provider-result.json').read_text())['provider_output']
    if (notes != payload['notes'] or fields != payload['catalogue'] or request['model'] != 'claude-sonnet-5-5'
            or provider['model'] != request['model'] or request['max_tokens'] != 20000
            or provider['stop_reason'] != 'end_turn'):
        raise ValueError('The retained source, complete catalogue or qualified profile differs.')
    result = dict(attempt=attempt, folder=folder, manifest=manifest, hashes=hashes, request=request,
                  payload=payload, fields=fields, notes=notes, provider=provider,
                  original=(folder / 'case/form.docx').read_bytes(),
                  classification=json.loads((folder / 'classification.json').read_text()),
                  first=json.loads((folder / 'answers-adopted.json').read_text())['answers'])
    if attempt in (17, 19):
        asr = root / f'{attempt-1:03}'
        asr_bytes = (asr / 'manifest.json').read_bytes()
        if sha(asr_bytes) != SEALS[f'{attempt-1:03}']:
            raise ValueError('The prospectively sealed paired transcription manifest differs.')
        asr_manifest = json.loads(asr_bytes)
        if asr_manifest['runner']['commit'] != PAID_SOURCE:
            raise ValueError('The paired transcription source differs.')
        for name, record in asr_manifest['evidence'].items():
            if not (asr / name).resolve().is_relative_to(asr.resolve()):
                raise ValueError('Paired evidence cannot escape the closed attempt folder.')
            expected = record['sha256'] if isinstance(record, dict) else record
            if sha((asr / name).read_bytes()) != expected:
                raise ValueError(f'Changed paired transcription evidence: {name}')
        request = json.loads((asr / 'request.json').read_text())
        result['voice'] = dict(folder=asr, manifest=asr_manifest, request=request,
            response=json.loads((asr / 'provider-response.json').read_text()),
            raw=(asr / 'raw-transcript.txt').read_text(), reviewed=(asr / 'reviewed-transcript.txt').read_text(),
            edits=json.loads((asr / 'transcript-edits.json').read_text()))
        if result['voice']['reviewed'] != notes:
            raise ValueError('The reviewed transcript differs from the generation source.')
    return result


def semantic(answer):
    """Only the new server signature and review timestamp are intentionally excluded."""
    return {key: value for key, value in answer.items() if key not in ('ordinary_relation', 'reviewed_at')}
