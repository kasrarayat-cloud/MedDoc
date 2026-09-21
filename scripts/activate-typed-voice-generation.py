#!/usr/bin/env python3
"""Code-only preserving activation for the demonstrated operative-summary omission.

Default is read-only. The qualified driver retains current rows, financial
history and files; this adapter authenticates the newer completed static receipt
instead of reinstalling assets. No migration or provider work occurs here.
"""
import hashlib
import json
from pathlib import Path
import sys
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
SELF = 'scripts/activate-typed-voice-generation.py'
DECL = 'docs/foundation/mutations/20260921-quillmd-typed-voice-generation.md'
BASELINE = 'b6b40b02c3dea69f88f4b2b0438535865f4dc32e'
EVIDENCE = ROOT / 'rebuild/.runtime/typed-voice-20260921'
DRIVER = 'scripts/activate-colonoscopy-compatibility.py'
DRIVER_SHA256 = '1010d4a58ada0d34a32738a7ed9e00bf6b100212034bdb3db8c02f0848b4742c'
ASSET_READER = 'scripts/activate-typed-voice.py'
ASSET_READER_SHA256 = 'ef4c050862b52d29b2dc62a0d60bc183354f50d8e41c261f9137f1f79bded4bd'
STATIC_RECEIPT = EVIDENCE / 'typed-voice-resume-b6b40b02.json'
STATIC_RECEIPT_SHA256 = '757d43c7da60db56ea8f5030757e7bf95db4f37e5677cae7648a114c4b04d13e'
ALLOWED = {SELF, DECL, 'rebuild/ops/test_typed_voice_generation_activation.py',
           'rebuild/core/generation.py', 'rebuild/core/tests/test_tab_independent_sections.py'}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pinned_module(relative, expected, name):
    data = (SOURCE / relative).read_bytes()
    require(sha(data) == expected, 'Qualified generation-activation helper changed.')
    module = types.ModuleType(name)
    module.__file__ = str(SOURCE / relative)
    sys.modules[name] = module
    exec(compile(data, module.__file__, 'exec'), module.__dict__)
    return module


assets = pinned_module(ASSET_READER, ASSET_READER_SHA256, '_generation_static_reader')
driver = pinned_module(DRIVER, DRIVER_SHA256, '_generation_preserving_driver')
for module in (driver, driver.a, driver.b):
    for name, value in {'BASELINE': BASELINE, 'RUNNING_RELEASE': BASELINE,
                        'SOURCE': SOURCE, 'SELF': SELF, 'DECL': DECL, 'EVIDENCE': EVIDENCE}.items():
        setattr(module, name, value)
driver.__file__ = __file__
driver.RUNTIME_ALLOWED = ALLOWED
driver.REQUIRED = ALLOWED
_qualified_load = driver.a.load


def validate_static_receipt(data):
    require(sha(data) == STATIC_RECEIPT_SHA256, 'Completed static receipt bytes changed.')
    receipt = json.loads(data)
    require(receipt.get('complete') is True and receipt.get('target') == BASELINE
            and receipt.get('stage') == 'complete' and receipt.get('provider_calls') == 0
            and receipt.get('existing_hashed_assets_retained') is True
            and receipt.get('static_delta_source_bound') is True
            and receipt.get('static_transition', {}).get('old_immutable_assets_retained') is True,
            'Completed source-bound static transition is required.')
    return receipt['static_transition']['after']


def current_static(identity, word):
    expected = validate_static_receipt(word.checked_file(STATIC_RECEIPT, private=True))
    current = assets.static_inventory(ROOT / 'rebuild/staticfiles')
    require(current == expected, 'Current static assets differ from completed activation evidence.')
    # Current aliases must still be the unchanged reviewed application/OTP bytes.
    for name, source in identity.static_sources().items():
        require(current.get(name, {}).get('sha256') == sha(source.read_bytes()),
                'Current static alias differs from unchanged source.')
    return current


def load(name, relative, target):
    module = _qualified_load(name, relative, target)
    if name == 'old':
        module.static_inventory = current_static
    return module


driver.a.load = load


if __name__ == '__main__':
    driver.main()
