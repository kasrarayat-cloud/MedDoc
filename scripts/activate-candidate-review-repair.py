#!/usr/bin/env python3
"""Forward repair of the stopped candidate-review activation.

The source and static halves already landed; the environment replace and the receipt did not,
because the operations publisher wrote to core_servicehealth inside the act and the unchanged()
invariant refused. Nothing is wrong with the release. This completes it.

✅ RESOLVED 2026-09-22 — the hold below was cleared by a new independent-key drill against an
offsite-origin 36-table capture. Kept for the record: The pinned independent-key
restore proof covers a 35-table capture taken before migration `0018_servicehealth`, while the
live population is 36, and the bounded exception that bridged the two expired when
`core_servicehealth` stopped being empty. A local restore is not a substitute: the guard demands
the proof whose positive control is that the LIVE KEY WAS DENIED. The three ways out are all owner
decisions and are written out at the top of the declaration. Read that before touching anything
here.

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
import time
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
SELF = 'scripts/activate-candidate-review-repair.py'
DECL = 'docs/foundation/mutations/20260922-quillmd-candidate-review-repair.md'
DECL_SHA256 = 'f216e91feae23184ef86be51c81597a05361080e4a0aa5adf597d44171c2cb38'
#: ⚠️ THE TREE AND THE CONFIGURED RELEASE HAVE DIVERGED, AND THAT IS PRECISELY THE PARTIAL STATE.
#: The stopped act installed the source (so the shared tree is at 5b2576c5) but never replaced the
#: environment (so the app is still CONFIGURED as, and serves, eb37c784). These are two different
#: facts and the driver reads them for two different purposes: BASELINE is the tree's commit, used
#: for the shared-tree assertion and the diff range; RUNNING_RELEASE is what `.env` says and what
#: `/health/` reports, used by `updated_environment` and by the live-health checks.
#:
#: Collapsing them — as a normal activation may, because normally they agree — is what made the
#: first read-only pass refuse with "Unexpected configured release". The refusal was correct: it
#: noticed the divergence this repair exists to close.
#:
#: The configured value is taken from the application's OWN /health/ output, never by reading
#: `.env`, which is not read by any route.
BASELINE = '5b2576c5081ad7e86376197d828b1b7ac5336ad4'
RUNNING_RELEASE = 'eb37c7846f3ef634c16b4da46456663b88217a60'
EVIDENCE = ROOT / 'rebuild/.runtime/candidate-review-repair-20260922'
DRIVER = 'scripts/activate-typed-voice.py'
DRIVER_SHA256 = '4e2efda2357fa2c33262eb2f747ac7201eadbc94875528cde2b7fe9040ebba18'
MIGRATION = '0018_servicehealth'
#: ⚠️ THE INHERITED BOUNDED EXCEPTION IS GONE, AND A NEW INDEPENDENT-KEY DRILL IS WHY.
#:
#: The previous activation accepted a 35-table safety capture that did not cover
#: `core_servicehealth`, bounded to ONLY while that table was EMPTY. The operations publisher
#: wrote a row, the exception expired exactly as designed, and the read-only pass refused. The
#: 2026-09-20 drill could not rescue it either: its proof is byte-frozen by sha256 and covers a
#: capture taken BEFORE migration `0018_servicehealth`.
#:
#: So a new drill was performed on 2026-09-22 against an OFFSITE-ORIGIN 36-table capture:
#:
#:   capture   20260922T043002Z-7d766ca1 — scheduled 04:30Z run, 36 tables, 226,080 rows,
#:             64 files, source_commit eb37c784 = the running release
#:   offsite   scheduled 05:00Z upload, 66 objects, 18,509,364 ciphertext bytes, readback
#:             verified; live_transport / transport_verified / restore_verified all true
#:   drill     downloaded back under a BOUNDED reservation (80 requests / 22,000,000 bytes,
#:             sized from today's measured manifest, not from 2026-09-20 observation bytes) and
#:             restored in isolation with the desktop's vault-returned key as the SOLE
#:             decryption source
#:
#: ⚠️ WHAT THE DRILL PROVES, AND WHAT IT DOES NOT. The Fernet key was independently recovered and
#: the operating key was never opened — observed by an inotify watch that fires for ANY process
#: on this host, with its own positive control, because a Python audit hook is language-level and
#: cannot see a docker child. The B2 RETRIEVAL credential was the live one; its independent
#: recovery is NOT demonstrated, exactly as in 2026-09-20.
#:
#: Because this capture's population equals the live population, the DRIVER'S OWN
#: `assert_retained_capture` passes unmodified and this adapter overrides it with nothing.
#:
#: Every pin below is set on the modules for THIS RUN ONLY. The historical activators keep their
#: own constants and their proof stays byte-identical at 774171311054f0df…, so no past receipt
#: and no consumed activation eligibility is disturbed.
RESTORE_RESULT = APP / '.runtime/recovery-custody-handoff-20260922/return-evidence/independent-key-restore/result.json'
RESTORE_RESULT_SHA256 = 'f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f'
RESTORED_MANIFEST_SHA256 = 'c3c4994fa4b50c51e75197e2ba57f8e2427daaf5929539c01498548da2083011'
CAPTURE_RUN = '20260922T043002Z-7d766ca1'
CAPTURE_SOURCE = 'eb37c7846f3ef634c16b4da46456663b88217a60'
CAPTURE_MANIFEST_SHA256 = 'c3c4994fa4b50c51e75197e2ba57f8e2427daaf5929539c01498548da2083011'
#: The completed static transition of the release now serving. This act reinstalls nothing.
STATIC_RECEIPT = APP / '.runtime/word-multicolumn-activation-20260921/word-multicolumn-activation-eb37c7846f3e.json'
STATIC_RECEIPT_SHA256 = '626d7eff5f318b618ff020af813e1265253eadedd0bf26828f05e844529d16f1'
#: ⚠️ THE INHERITED DRIVER HARD-CODES ITS OWN RECEIPT NAME, and a receipt called
#: `typed-voice-activation-*` for this release would mislead whoever reads the evidence later.
#: Exactly ONE pattern is renamed; every other regex the driver uses stays the module's own.
#: The same targeted rename the admin-console adapter made, for the same reason.
RESULT_PATTERN = r'typed-voice-activation-[a-zA-Z0-9_-]+\.json'
RENAMED_PATTERN = r'candidate-review-repair-[a-zA-Z0-9_-]+\.json'
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
#: The repair changes only itself and its declaration; the code it completes already landed.
REQUIRED = {SELF, DECL, 'rebuild/ops/activation_exclusion.py',
            'rebuild/core/management/commands/publish_operations_status.py',
            'rebuild/ops/backup_alerts.py'}
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


driver = pinned_module(DRIVER, DRIVER_SHA256, '_candidate_review_repair_driver')
for module in (driver, driver.a, driver.b):
    for name, value in {'BASELINE': BASELINE, 'RUNNING_RELEASE': RUNNING_RELEASE, 'SOURCE': SOURCE,
                        'SELF': SELF, 'DECL': DECL, 'EVIDENCE': EVIDENCE,
                        'MIGRATION': MIGRATION, 'CAPTURE_RUN': CAPTURE_RUN,
                        'CAPTURE_SOURCE': CAPTURE_SOURCE,
                        'CAPTURE_MANIFEST_SHA256': CAPTURE_MANIFEST_SHA256,
                        'RESTORED_RUN': CAPTURE_RUN, 'RESTORED_RELEASE': CAPTURE_SOURCE,
                        'RESTORED_MANIFEST_SHA256': RESTORED_MANIFEST_SHA256,
                        'RESTORE_RESULT': RESTORE_RESULT,
                        'RESTORE_RESULT_SHA256': RESTORE_RESULT_SHA256}.items():
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
    # ⚠️ THE SAME DIVERGENCE, IN A SECOND PLACE. The installed static assets belong to the
    # release that is SERVING, not to the tree commit — the stopped act left them
    # byte-identical (before == after == 37, matching this receipt). So the completed
    # transition to authenticate is RUNNING_RELEASE's, not BASELINE's.
    require(receipt.get('complete') is True and receipt.get('target') == RUNNING_RELEASE
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


#: ⚠️ THE PUBLISHER TIMER IS COORDINATED WITH, NOT SILENCED. The installed publisher is not yet
#: lock-aware — this repair is what installs the lock-aware one — so for THIS act the code-level
#: exclusion is one-sided. The timer is therefore stopped for the act and RESTORED in a finally,
#: on success or failure alike, with both transitions recorded. It is never disabled, and the
#: deferral is visible rather than silent: the ServiceHealth row keeps its own freshness check, so
#: a longer-than-expected gap still reads as stale instead of as a manufactured green.
PUBLISHER_TIMER = 'quillmd-fresh-operations-publisher.timer'
PUBLISHER_COMMAND = 'publish_operations_status'


def publisher_timer(action):
    """Exactly one unit, exactly two verbs, through the same pinned helper the driver uses."""
    require(action in ('start', 'stop'), 'Only start/stop of the publisher timer is permitted.')
    helper = json.loads((APP / '.runtime/word-beta-recovery-20260917-final.json').read_text())['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper), 'Helper image must be locally pinned.')
    code = "import os,subprocess\nos.chroot('/host');os.chdir('/')\n"
    code += 'subprocess.run(' + repr(['systemctl', action, PUBLISHER_TIMER]) + ',check=True)\n'
    import subprocess as sp
    done = sp.run(['docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--pid=host',
                   '--mount', 'type=bind,src=/,dst=/host,readonly', helper, 'python', '-B', '-'],
                  input=code, text=True, capture_output=True, timeout=200)
    require(done.returncode == 0, 'Publisher timer %s failed; helper stderr withheld.' % action)




if __name__ == '__main__':
    if '--execute' not in sys.argv:
        driver.main()
    else:
        EVIDENCE.mkdir(mode=0o700, exist_ok=True)
        # ⚠️ FROM THE SOURCE BEING INSTALLED, NOT THE TREE IT IS INSTALLED INTO. `APP` is the
        # INSTALLED application, which does not carry `activation_exclusion` yet — this repair is
        # what puts it there. Importing from APP failed at the import, six seconds in, before any
        # mutation: the chicken-and-egg of a coordination mechanism that ships in the very act it
        # coordinates. SOURCE is the reviewed target worktree, so these are the exact bytes the
        # act is about to install.
        sys.path.insert(0, str(SOURCE / 'rebuild'))
        from ops import activation_exclusion as exclusion
        target = sys.argv[sys.argv.index('--target') + 1]
        owner = 'activation:' + target[:12]
        # ⚠️ THE DEBT IS RECORDED DURABLY BEFORE IT IS INCURRED, not after. If this process dies
        # between the pause and the finally, the marker is what lets the independent alerts timer
        # restore publication; writing it afterwards would leave exactly the window it exists for.
        exclusion.note_timer_paused(owner, prior_active=True)
        publisher_timer('stop')
        try:
            # ⚠️ PAUSING THE TIMER DOES NOT STOP A RUN ALREADY IN FLIGHT, and the installed
            # publisher does not take the new lock, so acquiring the lock cannot drain it either.
            # The drain therefore waits for the actual process to exit, BEFORE the baseline
            # snapshot that driver.main() takes.
            exclusion.drain_publisher()
            exclusion.record('publication_drained', owner=owner)
            # Held across the baseline snapshot, every preservation check and the receipt —
            # released only after the act has written its outcome, success or failure.
            with exclusion.hold(owner):
                driver.main()
        finally:
            publisher_timer('start')
            exclusion.clear_timer_pause(owner)
