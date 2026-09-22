#!/usr/bin/env python3
"""Code-only preserving activation for the candidate-review release.

Default is read-only. The qualified driver retains current rows, financial history and files.
This release carries NO migration and NO public-asset change, so the adapter authenticates the
completed static receipt of the release already installed instead of reinstalling assets.

⚠️ THE SCHEMA EXPECTATION COMES FROM THE DECLARATION, NOT FROM THE DATABASE. The driver ships
with the 35-table set of its own era; this baseline has 36. The replacement set is read from the
reviewed declaration and the declaration is pinned by content, because an expectation taken from
the thing under test cannot fail. It is NOT a count: two different 36-table sets compare equal
by length, and that is exactly the drift a preservation check exists to catch.

The operations-status publisher is installed by its own ruled act. This one installs no unit,
enables no timer, and makes no provider call — the §1e allowance is spent and is not re-spent here.

⚠️ THE STATIC RECEIPT PINNED BELOW IS THE PREVIOUS ACTIVATION'S OWN OUTPUT, for the release now
serving. That is the point: this adapter reinstalls nothing, so it must authenticate the assets
that are already there against evidence produced when they were put there.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
APP = ROOT / 'rebuild'
SELF = 'scripts/activate-candidate-review.py'
DECL = 'docs/foundation/mutations/20260921-quillmd-candidate-review-activation.md'
DECL_SHA256 = '7943ca482f47354a39c9321df3bc9fd358141d0fb994a7fd8cceb5bdc180887a'
BASELINE = 'eb37c7846f3ef634c16b4da46456663b88217a60'
EVIDENCE = ROOT / 'rebuild/.runtime/candidate-review-activation-20260921'
DRIVER = 'scripts/activate-typed-voice.py'
DRIVER_SHA256 = '4e2efda2357fa2c33262eb2f747ac7201eadbc94875528cde2b7fe9040ebba18'
MIGRATION = '0018_servicehealth'
#: ⚠️ THE INHERITED BOUNDED EXCEPTION IS GONE, AND THAT IS THE POINT OF THIS PIN.
#:
#: The previous activation accepted a 35-table safety capture that did not cover
#: `core_servicehealth`, bounded to ONLY while that table was EMPTY — because a restore from it
#: would then lose no row. The operations publisher has since written a row, so the exception
#: expired exactly as designed and the read-only pass refused: *"The table the retained capture
#: does not cover is no longer empty."* That refusal was correct and is not worked around here.
#:
#: The resolution is a capture that covers everything, obtained through the existing authorized
#: LOCAL procedure — no offsite restore, no B2 allowance, no provider call:
#:
#:   backup       -> 20260922T024158Z-8d231f14   36 tables, 226,080 rows, 64 files,
#:                                               source_commit eb37c784 = the running release
#:   restore-check-> restore-88da076936d4dc98    isolated and networkless; all table hashes and
#:                                               all file hashes match; provider_actions 0,
#:                                               network none, published_ports 0, container not
#:                                               retained; financial invariants all zero
#:   compose      -> backup-restore-20260922T024158Z-8d231f14.json, validator passed
#:
#: Because that capture's population equals the live population exactly, the DRIVER'S OWN
#: `assert_retained_capture` now passes unmodified. This adapter therefore overrides it with
#: NOTHING. The guard is strictly stronger than the one it replaces, not weaker.
#:
#: The restore evidence is re-pinned to the same capture, so the drill and the safety capture are
#: one run and `set(latest['tables']) == set(manifest['tables'])` holds by identity rather than by
#: coincidence. Both are set on the modules for THIS run only; the historical activators' own
#: constants are untouched, as their receipts depend on them.
CAPTURE_RUN = '20260922T024158Z-8d231f14'
CAPTURE_SOURCE = 'eb37c7846f3ef634c16b4da46456663b88217a60'
CAPTURE_MANIFEST_SHA256 = '36d905a82be06ef7c69332b744d4e711fa82857013890d825fd44665ee451c7a'
#: The completed static transition of the release now serving. This act reinstalls nothing.
STATIC_RECEIPT = APP / '.runtime/word-multicolumn-activation-20260921/word-multicolumn-activation-eb37c7846f3e.json'
STATIC_RECEIPT_SHA256 = '626d7eff5f318b618ff020af813e1265253eadedd0bf26828f05e844529d16f1'
#: ⚠️ THE INHERITED DRIVER HARD-CODES ITS OWN RECEIPT NAME, and a receipt called
#: `typed-voice-activation-*` for this release would mislead whoever reads the evidence later.
#: Exactly ONE pattern is renamed; every other regex the driver uses stays the module's own.
#: The same targeted rename the admin-console adapter made, for the same reason.
RESULT_PATTERN = r'typed-voice-activation-[a-zA-Z0-9_-]+\.json'
RENAMED_PATTERN = r'candidate-review-activation-[a-zA-Z0-9_-]+\.json'
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
ALLOWED = declared(SCOPE_MARKER, DECLARATION.decode()) | {SELF, DECL}
#: The files this release is ABOUT. A tree missing any of them is not this release.
REQUIRED = {SELF, DECL, 'rebuild/core/generation.py', 'rebuild/core/views.py',
            'rebuild/templates/encounter_detail.html'}
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


driver = pinned_module(DRIVER, DRIVER_SHA256, '_candidate_review_driver')
for module in (driver, driver.a, driver.b):
    for name, value in {'BASELINE': BASELINE, 'RUNNING_RELEASE': BASELINE, 'SOURCE': SOURCE,
                        'SELF': SELF, 'DECL': DECL, 'EVIDENCE': EVIDENCE,
                        'MIGRATION': MIGRATION, 'CAPTURE_RUN': CAPTURE_RUN,
                        'CAPTURE_SOURCE': CAPTURE_SOURCE,
                        'CAPTURE_MANIFEST_SHA256': CAPTURE_MANIFEST_SHA256,
                        'RESTORED_RUN': CAPTURE_RUN, 'RESTORED_RELEASE': CAPTURE_SOURCE}.items():
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


#: ⚠️ NO `assert_retained_capture` OVERRIDE. The previous adapter needed one to widen a single
#: clause by exactly one empty table; this one needs none, because the pinned capture covers
#: the live population exactly. An adapter that overrides nothing here is the goal state.


class _RenamedReceiptRe:
    """Rename only the inherited receipt-name pattern; everything else is the real `re`."""

    def __getattr__(self, name):
        return getattr(re, name)

    def fullmatch(self, pattern, string, *args, **kwargs):
        if pattern == RESULT_PATTERN:
            pattern = RENAMED_PATTERN
        return re.fullmatch(pattern, string, *args, **kwargs)


driver.re = _RenamedReceiptRe()


if __name__ == '__main__':
    if '--execute' in sys.argv:
        EVIDENCE.mkdir(mode=0o700, exist_ok=True)
    driver.main()
