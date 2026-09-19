#!/usr/bin/env python3
"""Assemble the native-Word review package from artifacts that already exist. Deterministic, no AI, no SDK.

⚠️ WHAT THIS DOES NOT DO, SAID FIRST. It does not GENERATE documents. Every input is an artifact produced
earlier by the real export path or by the pinned SDK qualification, and this script only selects, applies
the shipped export-layout repair, renames the two misnamed fixtures to what they actually are, and writes
a manifest. A packaging step that generated its own evidence would be describing itself.

The 2026-09-18 package shipped `05-all-blanks-fixture-no-AI.docx` labelled "every answer reviewed as
missing" when it fills every blank, and `04-long-answer-fixture-no-AI.docx` labelled a long-answer case
when its 19,931 characters are a BODY paragraph and its longest mapped answer is 89 characters. Both names
are corrected here; the bytes are untouched, because the fixtures are fine and the labels were not.
"""
import argparse
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

# ⚠️ THE DOCUMENTS COME FROM THIS CHECKOUT, NOT FROM A HARD-CODED TREE. Building a package that quietly
# reads another checkout's checklist is how a corrected document ships with an uncorrected one beside it.
REPO = Path(__file__).resolve().parents[1]
APP = Path('/opt/meddoc-pro/rebuild')
SOURCE = APP / '.runtime/word-review-package/quillmd-word-review-20260918'
ORIGINAL_SHA256 = 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'

# (destination name, source file, apply the export-layout repair?)
CONTENTS = (
    ('01-original-blank-WM-IOV-Template.docx', '01-original-blank-WM-IOV-Template.docx', False),
    ('02-export-absent-scenario-BEFORE-layout-repair.docx', '02-fresh-export-live-absent-scenario.docx', False),
    ('03-export-absent-scenario-AFTER-layout-repair.docx', '02-fresh-export-live-absent-scenario.docx', True),
    ('04-export-positive-scenario-BEFORE-layout-repair.docx', '03-previous-export-live-positive-scenario.docx', False),
    ('05-export-positive-scenario-AFTER-layout-repair.docx', '03-previous-export-live-positive-scenario.docx', True),
    ('06-sdk-fixture-EVERY-BLANK-FILLED-not-missing.docx', '05-all-blanks-fixture-no-AI.docx', False),
    ('07-sdk-fixture-LONG-BODY-PARAGRAPH-not-a-mapped-answer.docx', '04-long-answer-fixture-no-AI.docx', False),
)


def build(destination):
    sys.path.insert(0, str(APP))
    from documents import layout
    if destination.exists():
        raise SystemExit('Refusing to overwrite %s' % destination)
    staging = destination.with_suffix('')
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(mode=0o700, parents=True)
    summaries = {}
    for name, source, repair in CONTENTS:
        target = staging / name
        shutil.copy(SOURCE / source, target)
        if repair:
            summaries[name] = layout.repair_export(target)
        target.chmod(0o600)
    original = staging / CONTENTS[0][0]
    if hashlib.sha256(original.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit('The original in this package is not the accepted blank fixture.')
    # ⚠️ THE REPAIR MUST HAVE DONE SOMETHING, OR THE PAIR IS TWO COPIES OF THE SAME FILE AND THE PACKAGE
    # SILENTLY DEMONSTRATES NOTHING.
    for name, summary in summaries.items():
        if not summary['heading_rows']:
            raise SystemExit('%s: the layout repair found no heading rows' % name)
    for before, after in (('02-export-absent-scenario-BEFORE-layout-repair.docx',
                           '03-export-absent-scenario-AFTER-layout-repair.docx'),
                          ('04-export-positive-scenario-BEFORE-layout-repair.docx',
                           '05-export-positive-scenario-AFTER-layout-repair.docx')):
        if (staging / before).read_bytes() == (staging / after).read_bytes():
            raise SystemExit('%s and %s are identical; the repair did not apply' % (before, after))
        document = zipfile.ZipFile(staging / after).read('word/document.xml').decode('utf-8')
        if '<w:cantSplit/>' not in document or '<w:keepNext' not in document:
            raise SystemExit('%s carries no layout safeguards' % after)
    for name in ('word-acceptance-checklist.md', 'README.txt'):
        source = REPO / 'docs/rebuild/word-review' / name
        if not source.is_file():
            raise SystemExit('Missing package document: %s' % source)
        shutil.copy(source, staging / name)
        (staging / name).chmod(0o600)
    digests = []
    for path in sorted(staging.iterdir()):
        if path.name == 'SHA256SUMS.txt':
            continue
        digests.append('%s  %s' % (hashlib.sha256(path.read_bytes()).hexdigest(), path.name))
    (staging / 'SHA256SUMS.txt').write_text('\n'.join(digests) + '\n')
    (staging / 'SHA256SUMS.txt').chmod(0o600)
    # Written with zipfile rather than the `zip` binary, which is not installed on this host - a builder
    # that depends on a tool the host may not have fails at the last step, after doing all the work.
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive_file:
        for path in sorted(staging.iterdir()):
            archive_file.write(path, '%s/%s' % (staging.name, path.name))
    destination.chmod(0o600)
    archive = hashlib.sha256(destination.read_bytes()).hexdigest()
    (destination.parent / (destination.name + '.sha256')).write_text(
        '%s  %s\n' % (archive, destination.name))
    print('archive : %s' % destination)
    print('bytes   : %d' % destination.stat().st_size)
    print('sha256  : %s' % archive)
    print('files   : %d' % (len(CONTENTS) + 3))
    for name, summary in summaries.items():
        print('repaired: %-56s tables=%d headingRows=%d' % (name, summary['tables'], summary['heading_rows']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True)
    build(Path(parser.parse_args().destination))
