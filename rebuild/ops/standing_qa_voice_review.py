"""Prospective, explicit edits of retained synthetic ASR; no human acceptance claim."""
import hashlib
import json
from pathlib import Path

try:
    from . import provider_campaign as pc
except ImportError:
    import provider_campaign as pc

MANIFEST = Path(__file__).with_name('fixtures') / 'reviewed-synthetic-voice-v1.json'
MANIFEST_SHA256 = '81153aa063ca4020204e5028eaabf611d549f294b949d913137da89c7621c7d6'


def validate(data):
    pc.require(data['id'] == 'reviewed-synthetic-voice-v1'
               and data['provider_upload_allowed'] is True and data['corpus_qualification'] is False,
               'The synthetic review identity or rights changed.')
    rows = {}
    for row in data['rows']:
        pc.require(row['audio_id'] not in rows, 'A recording has only one frozen review.')
        pc.require(hashlib.sha256(row['raw_text'].encode()).hexdigest() == row['prior_raw_sha256']
                   and hashlib.sha256(row['reviewed_text'].encode()).hexdigest() == row['reviewed_sha256'],
                   'The raw or reviewed transcript differs from its explicit frozen hash.')
        reconstructed = row['raw_text']
        for edit in row['edits']:
            pc.require(reconstructed.count(edit['raw']) == 1,
                       'An explicit synthetic correction must identify exactly one source span.')
            reconstructed = reconstructed.replace(edit['raw'], edit['reviewed'])
        pc.require(reconstructed == row['reviewed_text'],
                   'The reviewed transcript contains an unrecorded edit.')
        rows[row['audio_id']] = row
    return rows


def frozen(digest):
    root = Path(__file__).resolve().parents[2]
    raw, _, _, _ = pc.committed_file(MANIFEST, root, 'prospective synthetic transcript review')
    pc.committed_file(Path(__file__).resolve(), root, 'synthetic transcript review reader')
    pc.require(digest == MANIFEST_SHA256 == hashlib.sha256(raw).hexdigest(),
               'The declared synthetic review differs from the committed freeze.')
    return validate(json.loads(raw))


def reviewed(row, audio_sha256, raw):
    pc.require(row['audio_sha256'] == audio_sha256
               and hashlib.sha256(raw.encode()).hexdigest() == row['prior_raw_sha256']
               and raw == row['raw_text'],
               'The current ASR differs from the prospectively reviewed source; no correction or generation is applied.')
    return row['reviewed_text']
