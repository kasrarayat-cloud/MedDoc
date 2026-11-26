"""Release 2, R2-3 (measure M10; specification 2.1, D358): what the coder is sent, pinned.

Release 2 moves the coder's import (R2-4) and changes the Word package (R2-28 to R2-31). A byte diff cannot show that
the requests are unchanged, so this module holds them to release 1's, two ways.

1. The requests. The shipped job path - jobs.start_round, then jobs.run_job of the claimed job: the round's document
   prepared from its stored original, the READER built and sent, its answer read, the CHECKER built from it and sent -
   runs with a coder that records every request it is sent (tests.support.coding.FakeCoder answering
   tests.support.rounds' READER and CHECKER), over a text file, a pasted text and a PDF of fixed bytes. For each request
   it pins three things, for the reader and the checker:
   - request.sha256: the canonical stored request, which ProviderRun.request_sha256 records and replay reads;
   - the sha256 of the exact parameters the SDK would be given (studio.fable.client.canonical of request.params, the
     document's own bytes included, so a PDF sent re-encoded changes it while the stored form would not);
   - the attempts one send may bill (the requested model's and the server-side fallback's).
   The values are release 1's: measured on this tree's cpt-studio/ while it was still release 1's (tree bc0729bb9596,
   main 9ee0c85be), before release 2 changed anything. The text file and the pasted text are the measure area's own
   two text cases, and their four request hashes are the measure area's (55af66cb, 45b724da, 06d46117, 80f1d337 of the
   eight its two runs on release 1 gave). Its other four come from PDFs reportlab generates, one of them drawn with the
   C library's unseeded rand() (Pillow's effect_noise), so its bytes depend on what ran before it in the process: a
   fixed PDF stands in for them here, built byte for byte below, and the bench's requests part (ops/bench, lane M)
   compares those four between the trees it measures. Nothing here needs reportlab or the network.
2. The blob gate (specification 2.1). The seven files that are what the coder is asked and how its answer is read and
   priced keep the git blob ids they had at 9ee0c85be: each file on disk hashed as git hashes a blob (so an edit that
   was never committed fails too), and - in a git checkout - git's own HEAD naming the same blobs. The image has no
   .git: there the second check says so and is skipped, and the first still runs.

A failure here is the alarm working (R2-3's risk: a new SDK version or a changed document rebuild breaks the equality),
never a value to re-pin: what the coder is sent may change only through the coding-path gate (D358). Synthetic data
only; nothing reaches the network.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import jobs, models
from studio.fable import client as fable_client
from tests.support import coding as f
from tests.support import rounds as r

ROOT = Path(settings.BASE_DIR)

# The measure area's two text cases, verbatim: a UTF-8 text file uploaded as n.txt, and a paste of
# tests.support.coding.NOTE (copied here, so this pin does not move with that module's constant).
TEXT_FILE = b'SYNTHETIC NOTE polyp removed by cold snare.'
PASTED = ('SYNTHETIC PROCEDURE NOTE\nProcedure: colonoscopy to the cecum.\nFindings: one 6 mm polyp in the sigmoid '
          'colon, removed by cold snare.\nPlan: follow up per pathology.')
# Release 1's reader and checker answers, tests.support.rounds' READER and CHECKER at 9ee0c85be, copied here as
# literals for the same reason: the checker's request carries the reader's answer (fable.result.listing), so an
# edit to that shared fixture would move this pin with no change to what the coder is sent (refutation round 1,
# gates[5]); the checker's answer decides only the round's final state.
RELEASE_1_READER = {'document_kind': 'synthetic colonoscopy report',
                    'services_found': ['colonoscopy with polypectomy'],
                    'codes': [{'code': '45385',
                               'units': 1,
                               'modifiers': [],
                               'status': 'ready',
                               'reason': 'A 6 mm sigmoid polyp was removed by cold snare.',
                               'evidence': [{'quote': 'removed by cold snare', 'page': 1}],
                               'question': None},
                              {'code': '45380',
                               'units': 1,
                               'modifiers': [],
                               'status': 'needs_answer',
                               'reason': 'A biopsy may have been taken.',
                               'evidence': [{'quote': 'removed by cold snare', 'page': 1}],
                               'question': 'Was a biopsy taken from a separate site?'},
                              {'code': '43239',
                               'units': 1,
                               'modifiers': [],
                               'status': 'ready',
                               'reason': 'An upper endoscopy with biopsy is documented.',
                               'evidence': [{'quote': 'removed by cold snare', 'page': 1}],
                               'question': None},
                              {'code': '43251',
                               'units': 1,
                               'modifiers': [],
                               'status': 'not_supported',
                               'reason': 'No snare was used in the upper tract.',
                               'evidence': [{'quote': 'removed by cold snare', 'page': 1}],
                               'question': None}],
                    'documentation_problems': ['The note is not signed.'],
                    'questions': [{'question': 'Was a biopsy taken from a separate site?', 'affects': ['45380']}]}
RELEASE_1_CHECKER = {'reviews': [{'line': 'L1',
                                  'code': '45385',
                                  'verdict': 'agree',
                                  'correct_code': '45385',
                                  'correct_units': 1,
                                  'correct_modifiers': [],
                                  'correct_status': 'ready',
                                  'reason': 'The snare removal is documented.',
                                  'evidence': [{'quote': 'cold snare', 'page': 1}],
                                  'question': None},
                                 {'line': 'L2',
                                  'code': '45380',
                                  'verdict': 'agree',
                                  'correct_code': '45380',
                                  'correct_units': 1,
                                  'correct_modifiers': [],
                                  'correct_status': 'needs_answer',
                                  'reason': 'Supported as listed.',
                                  'evidence': [{'quote': 'cold snare', 'page': 1}],
                                  'question': None},
                                 {'line': 'L3',
                                  'code': '43239',
                                  'verdict': 'disagree',
                                  'correct_code': '43239',
                                  'correct_units': 1,
                                  'correct_modifiers': [],
                                  'correct_status': 'ready',
                                  'reason': 'The biopsy site is not stated.',
                                  'evidence': [{'quote': 'cold snare', 'page': 1}],
                                  'question': None},
                                 {'line': 'L4',
                                  'code': '43251',
                                  'verdict': 'agree',
                                  'correct_code': '43251',
                                  'correct_units': 1,
                                  'correct_modifiers': [],
                                  'correct_status': 'not_supported',
                                  'reason': 'Supported as listed.',
                                  'evidence': [{'quote': 'cold snare', 'page': 1}],
                                  'question': None}],
                     'missed_codes': [{'code': '45378',
                                       'units': 1,
                                       'modifiers': [],
                                       'status': 'ready',
                                       'reason': 'A diagnostic colonoscopy is documented.',
                                       'evidence': [{'quote': 'colonoscopy to the cecum', 'page': 1}],
                                       'question': None}],
                     'questions': [{'question': 'Which site was biopsied during the upper endoscopy?',
                                    'affects': ['43239']}]}


def synthetic_pdf() -> bytes:
    """A valid one-page PDF of three synthetic lines, built here byte for byte: the coding step never parses a PDF (it
    is sent as it was stored, studio.fable.document), so fixed bytes exercise the PDF request exactly as a generated
    file would, and stay the same wherever the suite runs."""
    lines = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE',
             'Colonoscopy to the cecum. One 6 mm sigmoid polyp was removed by cold snare.',
             'Release 2, R2-3: the request identity case.')
    stream = 'BT /F1 11 Tf 16 TL 56 740 Td ' + ' '.join(f'({line}) Tj T*' for line in lines) + ' ET'
    objects = ('<< /Type /Catalog /Pages 2 0 R >>',
               '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
               '/Contents 5 0 R >>',
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream')
    body, offsets = '%PDF-1.4\n', []
    for number, item in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f'{number} 0 obj\n{item}\nendobj\n'
    xref = len(body)
    body += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n' + ''.join(f'{at:010d} 00000 n \n' for at in offsets)
    body += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'
    return body.encode('ascii')


PDF = synthetic_pdf()
# The fixture's own identity: a change to synthetic_pdf fails here, before it can read as a changed request.
PDF_SHA256 = '094d41072aae677ca5c1c5cf2fa57a865c43fdb0350364105f063f9ddc790d23'

# Refutation round 1, item A: the normalisation the document step gives a text before the coder reads it
# (studio.fable.document, which lane D's Word changes edit beside: CRLF and CR line ends become LF, a leading
# byte-order mark is dropped, Unicode becomes NFC), reached by text files and a paste.
LINES = ('SYNTHETIC NOTE', 'Procedure: colonoscopy to the cecum.',
         'Findings: one 6 mm polyp in the sigmoid colon, removed by cold snare.')
ACCENTED = 'SYNTHETIC NOTE: a caf\u00e9-au-lait macule on the flank; one polyp removed by cold snare.'


def text_file(text: str, filename: str) -> dict:
    return {'data': text.encode('utf-8'), 'filename': filename, 'media_type': 'text/plain'}


# label -> the upload as the member made it, or {'paste': its text}. Item A's equal pins are what the normalisation
# does: the CRLF and CR files equal the LF one, the file with a BOM equals 'txt', the NFD file equals the NFC one,
# and the CRLF paste equals 'paste'.
CASES = {
    'txt': {'data': TEXT_FILE, 'filename': 'n.txt', 'media_type': 'text/plain'},
    'paste': {'paste': PASTED},
    'pdf': {'data': PDF, 'filename': 'a.pdf', 'media_type': 'application/pdf'},
    'txt-lf': text_file('\n'.join(LINES) + '\n', 'lines.txt'),
    'txt-crlf': text_file('\r\n'.join(LINES) + '\r\n', 'lines.txt'),
    'txt-cr': text_file('\r'.join(LINES) + '\r', 'lines.txt'),
    'txt-bom': {'data': b'\xef\xbb\xbf' + TEXT_FILE, 'filename': 'n.txt', 'media_type': 'text/plain'},
    'txt-nfc': text_file(unicodedata.normalize('NFC', ACCENTED), 'accent.txt'),
    'txt-nfd': text_file(unicodedata.normalize('NFD', ACCENTED), 'accent.txt'),
    'paste-crlf': {'paste': PASTED.replace('\n', '\r\n')},
}
# label -> each request the coder was sent, in order: (role, request.sha256, sha256 of the exact parameters, attempts).
# Release 1's, measured on tree bc0729bb9596 (lane F's PROOFS.md; item A's cases on 93c33dc1d's cpt-studio, exported
# read-only, in refutation round 1); a text request carries no base64, so its two hashes are equal.
RELEASE_1_REQUESTS = {
    'txt': (
        ('reader', '55af66cb9481b369be7b3cd97f6bf245bd5f87ea9612206e2bd0f7f389cf5bd9',
         '55af66cb9481b369be7b3cd97f6bf245bd5f87ea9612206e2bd0f7f389cf5bd9', 2),
        ('checker', '45b724da91b3ba74bdd594e9bf8f0b0d45cbc433f73795a6394b510690e6c906',
         '45b724da91b3ba74bdd594e9bf8f0b0d45cbc433f73795a6394b510690e6c906', 2),
    ),
    'paste': (
        ('reader', '06d461171fcb70d0798068b6b8d8244251bd5132b07c4ebdded465b4331f3d7b',
         '06d461171fcb70d0798068b6b8d8244251bd5132b07c4ebdded465b4331f3d7b', 2),
        ('checker', '80f1d3372678f154aee73962c148675ec9bb57f8cbf86b2415ffb1148e967695',
         '80f1d3372678f154aee73962c148675ec9bb57f8cbf86b2415ffb1148e967695', 2),
    ),
    'pdf': (
        ('reader', '2aacf5aa0610f077fea376d58dedf653e8000848724372c4448c030f1f041c76',
         'dcc365c8433ca018705239a1e045c88d097b41aa41248ea49a859f68078bc005', 2),
        ('checker', '10d38279f1abe56181fb27f60e5d60a25b2dac9092020f956ac5498c41854445',
         '7b9733e964e32fa4f21f534515a93123abe1655212ae46081e6b6e201f2ed43d', 2),
    ),
    'txt-lf': (
        ('reader', '495c267ea2528ef031488bcca7876a2175256847b6112551e65501a46e659969',
         '495c267ea2528ef031488bcca7876a2175256847b6112551e65501a46e659969', 2),
        ('checker', '485074c1631cd3543e5c1935f257d544d6de07bb6a4d89cc5aa4615317bc5185',
         '485074c1631cd3543e5c1935f257d544d6de07bb6a4d89cc5aa4615317bc5185', 2),
    ),
    'txt-crlf': (
        ('reader', '495c267ea2528ef031488bcca7876a2175256847b6112551e65501a46e659969',
         '495c267ea2528ef031488bcca7876a2175256847b6112551e65501a46e659969', 2),
        ('checker', '485074c1631cd3543e5c1935f257d544d6de07bb6a4d89cc5aa4615317bc5185',
         '485074c1631cd3543e5c1935f257d544d6de07bb6a4d89cc5aa4615317bc5185', 2),
    ),
    'txt-cr': (
        ('reader', '495c267ea2528ef031488bcca7876a2175256847b6112551e65501a46e659969',
         '495c267ea2528ef031488bcca7876a2175256847b6112551e65501a46e659969', 2),
        ('checker', '485074c1631cd3543e5c1935f257d544d6de07bb6a4d89cc5aa4615317bc5185',
         '485074c1631cd3543e5c1935f257d544d6de07bb6a4d89cc5aa4615317bc5185', 2),
    ),
    'txt-bom': (
        ('reader', '55af66cb9481b369be7b3cd97f6bf245bd5f87ea9612206e2bd0f7f389cf5bd9',
         '55af66cb9481b369be7b3cd97f6bf245bd5f87ea9612206e2bd0f7f389cf5bd9', 2),
        ('checker', '45b724da91b3ba74bdd594e9bf8f0b0d45cbc433f73795a6394b510690e6c906',
         '45b724da91b3ba74bdd594e9bf8f0b0d45cbc433f73795a6394b510690e6c906', 2),
    ),
    'txt-nfc': (
        ('reader', '57f8c1974ba37d5b7240ac2ac8d5fb438147b0c61ed386f492360273fdea972f',
         '57f8c1974ba37d5b7240ac2ac8d5fb438147b0c61ed386f492360273fdea972f', 2),
        ('checker', 'ba86a0e0cf404e9869b26851f09fd4a97806506537b9fa2b1709d809c641ca55',
         'ba86a0e0cf404e9869b26851f09fd4a97806506537b9fa2b1709d809c641ca55', 2),
    ),
    'txt-nfd': (
        ('reader', '57f8c1974ba37d5b7240ac2ac8d5fb438147b0c61ed386f492360273fdea972f',
         '57f8c1974ba37d5b7240ac2ac8d5fb438147b0c61ed386f492360273fdea972f', 2),
        ('checker', 'ba86a0e0cf404e9869b26851f09fd4a97806506537b9fa2b1709d809c641ca55',
         'ba86a0e0cf404e9869b26851f09fd4a97806506537b9fa2b1709d809c641ca55', 2),
    ),
    'paste-crlf': (
        ('reader', '06d461171fcb70d0798068b6b8d8244251bd5132b07c4ebdded465b4331f3d7b',
         '06d461171fcb70d0798068b6b8d8244251bd5132b07c4ebdded465b4331f3d7b', 2),
        ('checker', '80f1d3372678f154aee73962c148675ec9bb57f8cbf86b2415ffb1148e967695',
         '80f1d3372678f154aee73962c148675ec9bb57f8cbf86b2415ffb1148e967695', 2),
    ),
}

# Specification 2.1: the files of the coding path that keep the blob ids they have at 9ee0c85be (the request's prompts,
# its pricing, the reading of its answer, the credentials it is sent with, the package's kinds, the client, and the
# decision rules).
RELEASE_1_BLOBS = {
    'studio/fable/prompts.py': 'b353b913e8fdd0c2bb84e76fa70bd13238de5155',
    'studio/fable/pricing.py': 'bbb4d81e4fabec01d592d5859a403677e49b417f',
    'studio/fable/result.py': 'fc0ad228732cfb77459056836110fea4f0db88a3',
    'studio/fable/credentials.py': 'f327fb2d743b1788324a82c92211e137fc833ec4',
    'studio/fable/__init__.py': 'fefa89f55c8f6ebf4988fac56f90fd3856b720a3',
    'studio/fable/client.py': '6fdc46407c2f1da5190b5a44b82bfa7963dd4700',
    'studio/decisions.py': 'adf92a6c91a788abb7b5145fd106bb9edb606c2f',
}


def git_blob_id(data: bytes) -> str:
    """The id git gives a blob of ``data`` (no filter applies to these files: the repository sets no attributes)."""
    return hashlib.sha1(b'blob %d\x00' % len(data) + data).hexdigest()


def requests_sent(ws, user, case) -> tuple:
    """Code one document of ``case`` in practice ``ws``, uploaded by ``user``, through the shipped job path; every
    request the coder was sent, in order, as (role, request.sha256, sha256 of the exact parameters, attempts), and the
    round's final state."""
    enc = f.encounter(ws, user, service_date='2026-11-02', insurance='medicare', title='Request identity case')
    made = CASES[case]
    revision = f.paste(enc, user, text=made['paste']) if 'paste' in made else f.upload(enc, user, **made)
    jobs.start_round(enc, revision, models.CodingRound.UPLOAD, user)
    fake = f.FakeCoder(reader=f.succeeded(r.reader_message(RELEASE_1_READER)),
                       checker=f.succeeded(r.checker_message(RELEASE_1_CHECKER)))
    with mock.patch.object(fable_client, 'coder', return_value=fake):
        jobs.run_job(jobs.claim_next())
    sent = tuple((role, request.sha256, hashlib.sha256(fable_client.canonical(request.params)).hexdigest(),
                  request.attempts) for role, request in fake.calls)
    return sent, models.CodingRound.objects.get(encounter=enc).state


class TheCoderIsSentWhatRelease1SentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._originals = tempfile.TemporaryDirectory()
        cls._override = override_settings(ORIGINALS_DIR=Path(cls._originals.name))
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._originals.cleanup()
        super().tearDownClass()

    def test_the_settings_are_release_1_s(self):
        # the owner's effort (class d, D358): a run under another one is sent another request, so say it first
        self.assertEqual(settings.CODING_EFFORT, 'max')
        self.assertEqual(hashlib.sha256(PDF).hexdigest(), PDF_SHA256)

    def test_each_request_is_release_1_s(self):
        ws = f.workspace('Requests')
        user = f.member(ws)
        for case in CASES:
            with self.subTest(case=case):
                sent, final = requests_sent(ws, user, case)
                self.assertEqual(final, models.CodingRound.DONE)  # the whole path ran: read, checked, combined
                self.assertEqual([role for role, *_ in sent], ['reader', 'checker'])  # each sent once, in this order
                self.assertEqual(sent, RELEASE_1_REQUESTS[case])


class TheCodingFilesKeepTheirBlobsTests(SimpleTestCase):
    def test_each_file_on_disk_is_release_1_s_blob(self):
        for path, blob in RELEASE_1_BLOBS.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob_id((ROOT / path).read_bytes()), blob)

    def test_git_s_head_names_the_same_blobs(self):
        try:
            prefix = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-prefix'], capture_output=True,
                                    check=False)
        except FileNotFoundError:
            self.skipTest('no git here (the image has no .git); the files on disk are checked above')
        if prefix.returncode != 0 or prefix.stdout.decode().strip() != 'cpt-studio/':
            self.skipTest('not a git checkout of the repository (the image has no .git); the files on disk are checked '
                          'above')
        listed = subprocess.run(['git', '-C', str(ROOT), 'ls-tree', '--full-name', 'HEAD', '--', *RELEASE_1_BLOBS],
                                capture_output=True, check=True).stdout.decode()
        found = {}
        for line in listed.splitlines():
            meta, path = line.split('\t', 1)
            found[path.removeprefix('cpt-studio/')] = meta.split()[2]
        self.assertEqual(found, RELEASE_1_BLOBS)
