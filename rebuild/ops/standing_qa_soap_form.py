"""Prospectively frozen voice probe of the application's actual blank SOAP original.

Historical r1-11 forms and outcomes retain their own denominator. This module
reads no credentials and grants no provider or patient-data authority.
"""
import hashlib
import json
from pathlib import Path

try:
    from . import provider_campaign as pc
    from . import standing_qa_voice_forms as references
except ImportError:
    import provider_campaign as pc
    import standing_qa_voice_forms as references

FORM_ID = 'builtin-soap-voice-v1'
FORM_SHA256 = 'd92f300248ced2b07f6da5f0e7c12beaf43b01c0264253fd1b40ef2cb78f03aa'
MANIFEST_SHA256 = 'fa7692791c91bed18261e0301e636e12c9d606853c8612a48a244438e34860ad'
MANIFEST = Path(__file__).with_name('fixtures') / 'builtin-soap-voice-v1.json'
AUDIO_ID = 'soap-ankle-speech'


def build():
    from core.soap_document import original_bytes
    return original_bytes()


def frozen():
    root = Path(__file__).resolve().parents[2]
    data, _, _, _ = pc.committed_file(MANIFEST, root, 'built-in SOAP voice manifest')
    pc.committed_file(Path(__file__).resolve(), root, 'built-in SOAP voice freeze')
    pc.committed_file(root / 'rebuild/core/soap_document.py', root, 'application SOAP original constructor')
    pc.require(hashlib.sha256(data).hexdigest() == MANIFEST_SHA256,
               'The built-in SOAP manifest differs from its prospectively frozen hash.')
    manifest = json.loads(data)
    pc.require(manifest['id'] == FORM_ID and manifest['sha256'] == FORM_SHA256
               and manifest['audio_id'] == AUDIO_ID and manifest['provider_upload_allowed'] is True
               and manifest['corpus_qualification'] is False,
               'The built-in SOAP input identity or rights changed.')
    raw = build()
    pc.require(hashlib.sha256(raw).hexdigest() == FORM_SHA256,
               'The application SOAP original differs from the prospectively frozen bytes.')
    return manifest, raw


def score(manifest, notes, answers, source_support):
    result = references.score(manifest, notes, answers, source_support)
    return {**result, 'form_id': FORM_ID,
            'scope': 'Application built-in SOAP original with retained synthetic machine speech; supplemental only.'}
