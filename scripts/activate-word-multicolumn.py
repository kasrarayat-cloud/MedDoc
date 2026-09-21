#!/usr/bin/env python3
"""Code-only preserving activation for the multi-column/mixed Word release.

Default is read-only. The qualified driver retains current rows, financial history and files.
This release carries NO migration and NO public-asset change, so the adapter authenticates the
completed static receipt of the release already installed instead of reinstalling assets.

⚠️ THE SCHEMA EXPECTATION COMES FROM THE DECLARATION, NOT FROM THE DATABASE. The driver ships
with the 35-table set of its own era; this baseline has 36. The replacement set is read from the
reviewed declaration and the declaration is pinned by content, because an expectation taken from
the thing under test cannot fail. It is NOT a count: two different 36-table sets compare equal
by length, and that is exactly the drift a preservation check exists to catch.

The operations-status publisher is installed by its own ruled act afterwards. This one installs
no unit and enables no timer.
"""
import hashlib
import json
from pathlib import Path
import sys
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
APP = ROOT / 'rebuild'
SELF = 'scripts/activate-word-multicolumn.py'
DECL = 'docs/foundation/mutations/20260921-quillmd-word-multicolumn-activation.md'
DECL_SHA256 = '595585a6f27d8abe238aaca17d79ca45d587158ef907f73844665aa1ab912c7f'
BASELINE = '21809ef408a5f7b6691beb338a7640da82fcfb97'
EVIDENCE = ROOT / 'rebuild/.runtime/word-multicolumn-activation-20260921'
DRIVER = 'scripts/activate-typed-voice.py'
DRIVER_SHA256 = '4e2efda2357fa2c33262eb2f747ac7201eadbc94875528cde2b7fe9040ebba18'
MIGRATION = '0018_servicehealth'
#: The completed static transition of the release now serving. This act reinstalls nothing.
STATIC_RECEIPT = APP / '.runtime/admin-console-20260921/admin-console-resume-21809ef408a5.json'
STATIC_RECEIPT_SHA256 = 'a83479597ac649a31f3d02e0d73e3412a4d79e7ab6c2bec2027c4c95126922bc'
SCHEMA_MARKER = '<!-- declared-schema -->'
SCOPE_MARKER = '<!-- declared-source-scope -->'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def declared(marker, text):
    """The fenced list directly under a marker. A parse that drifts raises rather than reading empty."""
    require(marker in text, 'The declaration carries no ' + marker + ' marker.')
    after = text.split(marker, 1)[1].splitlines()
    index = 0
    while index < len(after) and not after[index].strip():
        index += 1
    require(index < len(after) and after[index].startswith('```'),
            'The ' + marker + ' block must open, unindented, directly after the marker.')
    index += 1
    body = []
    while index < len(after) and not after[index].startswith('```'):
        body.append(after[index])
        index += 1
    require(index < len(after), 'The ' + marker + ' block is not closed.')
    values = {line.strip() for line in body if line.strip()}
    require(values, 'The ' + marker + ' block is empty.')
    require(all(' ' not in value for value in values), 'The ' + marker + ' block holds prose.')
    return values


DECLARATION = (SOURCE / DECL).read_bytes()
require(sha(DECLARATION) == DECL_SHA256, 'Reviewed activation declaration changed.')
BASELINE_TABLES = frozenset(declared(SCHEMA_MARKER, DECLARATION.decode()))
ALLOWED = declared(SCOPE_MARKER, DECLARATION.decode()) | {SELF, DECL,
                                                          'rebuild/ops/test_word_multicolumn_activation.py'}
REQUIRED = {SELF, DECL, 'rebuild/documents/engine.py', 'rebuild/core/tab_review.py',
            'rebuild/core/views.py'}
require('core_servicehealth' in BASELINE_TABLES, 'The declared schema omits the reviewed new table.')
require(len(BASELINE_TABLES) == 36, 'The declared schema is not this baseline.')


def pinned_module(relative, expected, name):
    data = (SOURCE / relative).read_bytes()
    require(sha(data) == expected, 'Qualified activation driver changed.')
    module = types.ModuleType(name)
    module.__file__ = str(SOURCE / relative)
    sys.modules[name] = module
    exec(compile(data, module.__file__, 'exec'), module.__dict__)
    return module


driver = pinned_module(DRIVER, DRIVER_SHA256, '_word_multicolumn_driver')
for module in (driver, driver.a, driver.b):
    for name, value in {'BASELINE': BASELINE, 'RUNNING_RELEASE': BASELINE, 'SOURCE': SOURCE,
                        'SELF': SELF, 'DECL': DECL, 'EVIDENCE': EVIDENCE,
                        'MIGRATION': MIGRATION}.items():
        setattr(module, name, value)
driver.__file__ = __file__
driver.RUNTIME_ALLOWED = ALLOWED
driver.REQUIRED = REQUIRED
#: The one reviewed expectation, replacing the driver's own era set. Same object, both paths.
driver.BASELINE_TABLES = BASELINE_TABLES
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
    current = driver.static_inventory(APP / 'staticfiles')
    require(current == expected, 'Current static assets differ from completed activation evidence.')
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
    if '--execute' in sys.argv:
        EVIDENCE.mkdir(mode=0o700, exist_ok=True)
    driver.main()
