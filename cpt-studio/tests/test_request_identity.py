"""Release 2, R2-3 (measure M10; specification 2.1, D358): what the coder is sent, pinned.

Release 2 moves the coder's import (R2-4) and changes the Word package (R2-28 to R2-31). A byte diff cannot show that
the requests are unchanged, so this module holds them to release 1's - at the coder's effort R2-33 sets - three ways.

1. The requests. The shipped job path - jobs.start_round, then jobs.run_job of the claimed job: the round's document
   prepared from its stored original, the READER built and sent, its answer read, the CHECKER built from it and sent -
   runs with a coder that records every request it is sent (tests.support.coding.FakeCoder answering release 1's
   READER and CHECKER, kept below as literals), over a text file, a pasted text, a PDF of fixed bytes and the text cases
   the document step normalises (line ends, a byte-order mark, NFD). For each request it pins three things, for the
   reader and the checker:
   - request.sha256: the canonical stored request, which ProviderRun.request_sha256 records and replay reads;
   - the sha256 of the exact parameters the SDK would be given (studio.fable.client.canonical of request.params, the
     document's own bytes included, so a PDF sent re-encoded changes it while the stored form would not);
   - the attempts one send may bill (the requested model's and the server-side fallback's).
   The values are release 1's code at the coder's effort "high", release 2's setting (R2-33, owner D433 and D434;
   release 1's setting was "max"). They were first measured at "max" on this tree's cpt-studio/ while it was still
   release 1's (tree bc0729bb9596, main 9ee0c85be), before release 2 changed anything; R2-33 re-measured them on
   purpose, twice and independently (the lead's measurements m1 and m2, cpt-r2-20261125/lead/r2-33/), on release 1's
   commit 816045c7 (the same cpt-studio tree, bc0729bb9596) with CPT_STUDIO_CODING_EFFORT=high: this module's own
   helpers - the shipped job path, then the shipped LiveCoder - run on release 1's checkout in fresh processes. The two
   agree value for value, and each one's control run without the variable gives release 1's "max" values exactly. Only
   the effort moved: every request.sha256, parameters sha256 and body sha256 changed, and with output_config.effort
   taken out each digest equals release 1's at "max" (m1 checked it digest by digest); the attempts, the wire's method,
   path and headers and the PDF's bytes are as they were. The text file and the pasted text are the measure area's own
   two text cases; at "max" their four request hashes were the measure area's (55af66cb, 45b724da, 06d46117, 80f1d337
   of the eight its two runs on release 1 gave), and at "high" they are 36229e88, 56fa9c97, e97949fb and 99642f7a.
   Its other four come from PDFs reportlab generates, one of them drawn with the C library's unseeded rand() (Pillow's
   effect_noise), so its bytes depend on what ran before it in the process: a fixed PDF stands in for them here, built
   byte for byte below, and the bench's requests part (ops/bench, lane M) compares those four between the trees it
   measures. Nothing here needs reportlab or the network.
2. The wire (refutation round 1, gates[2]). The request is what the SDK is GIVEN; an anthropic, httpx2 or pydantic
   release could change what it SENDS from the same arguments (an effort clamped, a fallback dropped) and leave the
   request pin as it was. So each request also goes through the shipped LiveCoder - its own client construction, the
   SDK's token count, then its stream - over an in-memory httpx2.MockTransport that answers 400, and each HTTP request
   the SDK built is pinned: its method and path, its anthropic-beta and anthropic-version headers, the sha256 of its
   body, and the credentials' workspace as anthropic-workspace-id, run without one and with one (release 1's at "high",
   measured as above with requirements.txt's anthropic 2.11.0, httpx2 2.16.2 and pydantic 2.14.4: the count's body and
   the send's carry the effort; the method, path and headers do not). A retryable answer (529) and a read that times
   out leave the same one count and one send on the wire: release 1 sends nothing again automatically (refutation
   round 2, pins[0] to pins[2]). The SDK's x-stainless-* telemetry is not pinned. Nothing leaves the process: the base
   URL is a closed local port as a second guard, the key is synthetic, and the credentials loader is replaced, so no
   credentials file is read.
3. The blob gate (specification 2.1). The seven files that are what the coder is asked and how its answer is read and
   priced keep the git blob ids they had at 9ee0c85be: each file on disk hashed as git hashes a blob (so an edit that
   was never committed fails too), and - in a git checkout - git's own HEAD naming the same blobs. The image has no
   .git: there the second check says so and is skipped, and the first still runs.

A failure here is the alarm working (R2-3's risk: a new SDK version - seen on the wire - or a changed document rebuild
breaks the equality), never a value to re-pin: what the coder is sent may change only through the coding-path gate
(D358), and a bump of the SDK, its transport or pydantic is re-measured on release 1's tree before it is pinned. R2-33
is such a change, made on purpose by the owner's decision: he moved the coder's effort from "max" to "high" (D433: a
paid test of five synthetic documents at both; D434: at "high" every code, unit and modifier matched "max", at 84% less
cost), and these pins were re-measured on release 1's tree at "high" rather than taken from release 2's. Synthetic data
only; nothing reaches the network.
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic
import httpx2
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
# byte-order mark is dropped, Unicode becomes NFC), reached by text files and a paste. The accented text also holds
# what NFC keeps and NFKC rewrites (cm², 10³ and the micro sign), so its pair tells NFC from NFKC too (refutation
# round 2, pins[3]).
LINES = ('SYNTHETIC NOTE', 'Procedure: colonoscopy to the cecum.',
         'Findings: one 6 mm polyp in the sigmoid colon, removed by cold snare.')
ACCENTED = ('SYNTHETIC NOTE: a caf\u00e9-au-lait macule on the flank, 2 cm\u00b2; WBC 6.4 x 10\u00b3/\u00b5L; '
            'one polyp removed by cold snare.')
# The other line boundaries str.splitlines knows - VT, FF, FS, GS, RS, NEL, U+2028, U+2029 - which canonical_text
# keeps as they are ('nothing else'): pdftotext ends each page with a form feed, Word's manual line break is VT
# (refutation round 2, pins[4]).
KEPT_BREAKS = '\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029'


def text_file(text: str, filename: str) -> dict:
    return {'data': text.encode('utf-8'), 'filename': filename, 'media_type': 'text/plain'}


# label -> the upload as the member made it, or {'paste': its text}. Item A's equal pins are what the normalisation
# does: the CRLF and CR files equal the LF one, the file with a BOM equals 'txt', the NFD file equals the NFC one (and
# neither equals what NFKC would give), and the CRLF paste equals 'paste'. 'txt-kept' keeps every other line boundary,
# so it equals no other case.
CASES = {
    'txt': {'data': TEXT_FILE, 'filename': 'n.txt', 'media_type': 'text/plain'},
    'paste': {'paste': PASTED},
    'pdf': {'data': PDF, 'filename': 'a.pdf', 'media_type': 'application/pdf'},
    'txt-lf': text_file('\n'.join(LINES) + '\n', 'lines.txt'),
    'txt-crlf': text_file('\r\n'.join(LINES) + '\r\n', 'lines.txt'),
    'txt-cr': text_file('\r'.join(LINES) + '\r', 'lines.txt'),
    'txt-kept': text_file(LINES[0] + '\x0c' + LINES[1] + KEPT_BREAKS + LINES[2] + '\x0c', 'lines.txt'),
    'txt-bom': {'data': b'\xef\xbb\xbf' + TEXT_FILE, 'filename': 'n.txt', 'media_type': 'text/plain'},
    'txt-nfc': text_file(unicodedata.normalize('NFC', ACCENTED), 'accent.txt'),
    'txt-nfd': text_file(unicodedata.normalize('NFD', ACCENTED), 'accent.txt'),
    'paste-crlf': {'paste': PASTED.replace('\n', '\r\n')},
}
# label -> each request the coder was sent, in order: (role, request.sha256, sha256 of the exact parameters, attempts).
# Release 1's at the coder's effort "high" (R2-33, D434): measured on release 1's commit 816045c7 (tree bc0729bb9596)
# with CPT_STUDIO_CODING_EFFORT=high, twice and independently (the lead's m1 and m2). At release 1's own "max" they
# were measured on the same tree by lane F (its PROOFS.md; item A's cases on 93c33dc1d's cpt-studio, exported
# read-only, in refutation round 1). A text request carries no base64, so its two hashes are equal.
RELEASE_1_REQUESTS = {
    'txt': (
        ('reader', '36229e881b0b7f5e7384ce73ab51fa90486a457a280b8de3206d852d539efb96',
         '36229e881b0b7f5e7384ce73ab51fa90486a457a280b8de3206d852d539efb96', 2),
        ('checker', '56fa9c972574f54683a5b2bf8dabd76598fc11d1d9855dc9a563f9d9422fb2a6',
         '56fa9c972574f54683a5b2bf8dabd76598fc11d1d9855dc9a563f9d9422fb2a6', 2),
    ),
    'paste': (
        ('reader', 'e97949fb43b854a1395f8b0b36b4e39fa8fa01ffa7053f6516161fcb0113c9ad',
         'e97949fb43b854a1395f8b0b36b4e39fa8fa01ffa7053f6516161fcb0113c9ad', 2),
        ('checker', '99642f7a9aa7cfb6172e656a2ab00707d36169d2b706f24b33b6bf5088380a77',
         '99642f7a9aa7cfb6172e656a2ab00707d36169d2b706f24b33b6bf5088380a77', 2),
    ),
    'pdf': (
        ('reader', '687b0ce0bf802f814ff6a0410e73fe02539918d9889665ca4289d9c5cd553316',
         '55f7a8b9fe9bad0e9420ce70f87903f1e51dae645d053c1be1ca283f5efee6ee', 2),
        ('checker', 'cfa16b98776a04b97fdc1ff5aff60c75d641f9d53754b79e5572df2aa35ced86',
         'e79755e33ef881cd402ab96c62d8d4726b422a9772517271cba402edd2938501', 2),
    ),
    'txt-lf': (
        ('reader', '88dfe4f6994754fd035bd2c3f3b95eb989d85ce7ae2d3846d1cd395d41b6afc0',
         '88dfe4f6994754fd035bd2c3f3b95eb989d85ce7ae2d3846d1cd395d41b6afc0', 2),
        ('checker', '1d2df021e52922b047a8a3ae7366c98015f227939be3c7b9574740c0974153f2',
         '1d2df021e52922b047a8a3ae7366c98015f227939be3c7b9574740c0974153f2', 2),
    ),
    'txt-crlf': (
        ('reader', '88dfe4f6994754fd035bd2c3f3b95eb989d85ce7ae2d3846d1cd395d41b6afc0',
         '88dfe4f6994754fd035bd2c3f3b95eb989d85ce7ae2d3846d1cd395d41b6afc0', 2),
        ('checker', '1d2df021e52922b047a8a3ae7366c98015f227939be3c7b9574740c0974153f2',
         '1d2df021e52922b047a8a3ae7366c98015f227939be3c7b9574740c0974153f2', 2),
    ),
    'txt-cr': (
        ('reader', '88dfe4f6994754fd035bd2c3f3b95eb989d85ce7ae2d3846d1cd395d41b6afc0',
         '88dfe4f6994754fd035bd2c3f3b95eb989d85ce7ae2d3846d1cd395d41b6afc0', 2),
        ('checker', '1d2df021e52922b047a8a3ae7366c98015f227939be3c7b9574740c0974153f2',
         '1d2df021e52922b047a8a3ae7366c98015f227939be3c7b9574740c0974153f2', 2),
    ),
    'txt-kept': (
        ('reader', '87c454dc9da59375dac11728007c68a7a2851872b64a5c92ad18f9a94d93dd9e',
         '87c454dc9da59375dac11728007c68a7a2851872b64a5c92ad18f9a94d93dd9e', 2),
        ('checker', '1d67ff9d3c2fd988c63cb67c6f92174d6cd27cc3a4514b80c6cfd0c64ce85406',
         '1d67ff9d3c2fd988c63cb67c6f92174d6cd27cc3a4514b80c6cfd0c64ce85406', 2),
    ),
    'txt-bom': (
        ('reader', '36229e881b0b7f5e7384ce73ab51fa90486a457a280b8de3206d852d539efb96',
         '36229e881b0b7f5e7384ce73ab51fa90486a457a280b8de3206d852d539efb96', 2),
        ('checker', '56fa9c972574f54683a5b2bf8dabd76598fc11d1d9855dc9a563f9d9422fb2a6',
         '56fa9c972574f54683a5b2bf8dabd76598fc11d1d9855dc9a563f9d9422fb2a6', 2),
    ),
    'txt-nfc': (
        ('reader', '4838c488b22fbdabf33baa37ad3fac243606ae70f1fd4eae5eee2e36235177fb',
         '4838c488b22fbdabf33baa37ad3fac243606ae70f1fd4eae5eee2e36235177fb', 2),
        ('checker', '1147b7d3b8f7f698aed3f2e9c84f67de2017a376ef7eb38651412a54e6c1ae84',
         '1147b7d3b8f7f698aed3f2e9c84f67de2017a376ef7eb38651412a54e6c1ae84', 2),
    ),
    'txt-nfd': (
        ('reader', '4838c488b22fbdabf33baa37ad3fac243606ae70f1fd4eae5eee2e36235177fb',
         '4838c488b22fbdabf33baa37ad3fac243606ae70f1fd4eae5eee2e36235177fb', 2),
        ('checker', '1147b7d3b8f7f698aed3f2e9c84f67de2017a376ef7eb38651412a54e6c1ae84',
         '1147b7d3b8f7f698aed3f2e9c84f67de2017a376ef7eb38651412a54e6c1ae84', 2),
    ),
    'paste-crlf': (
        ('reader', 'e97949fb43b854a1395f8b0b36b4e39fa8fa01ffa7053f6516161fcb0113c9ad',
         'e97949fb43b854a1395f8b0b36b4e39fa8fa01ffa7053f6516161fcb0113c9ad', 2),
        ('checker', '99642f7a9aa7cfb6172e656a2ab00707d36169d2b706f24b33b6bf5088380a77',
         '99642f7a9aa7cfb6172e656a2ab00707d36169d2b706f24b33b6bf5088380a77', 2),
    ),
}

# Refutation round 1, gates[2]: the HTTP requests the SDK builds for each request above, as the shipped LiveCoder
# makes them - the token count, then the send: each one's method and path, its anthropic-beta and anthropic-version
# headers (round 2, pins[0]), the same for every request, and per request (role, sha256 of the count's body, sha256 of
# the send's body). Release 1's at "high" (R2-33, D434), measured with the requests above (m1 and m2, on 816045c7's
# cpt-studio, the tree lane F measured them on at "max" as 93c33dc1d's, exported read-only), with requirements.txt's
# anthropic 2.11.0, httpx2 2.16.2 and pydantic 2.14.4. Both bodies carry the effort (the count's through
# client.COUNT_KEYS); the method, path and headers do not, and are release 1's at either effort.
COUNT_ON_THE_WIRE = ('POST /v1/messages/count_tokens', 'server-side-fallback-2026-07-01,token-counting-2024-11-01',
                     '2026-10-21')
SEND_ON_THE_WIRE = ('POST /v1/messages', 'server-side-fallback-2026-07-01', '2026-10-21')
RELEASE_1_WIRE = {
    'txt': (
        ('reader', 'f5f420c1ef1074146edb3f1a0e093319ded762e0dbf9804b2899314434ebd9b0',
         'a04d90cc3a0d51ed1ad6020f0b59640f2c09df0e1d0736c954acc2e9fac838c5'),
        ('checker', '04c2e21d5bd399476e94b52e8121ae5fed5bf2afc6905cb66ad792bb306e4564',
         '76c9a83e2eaf63bb90fb3f9f7a57de66c068c1653c4ba39539ad3cdf6c041170'),
    ),
    'paste': (
        ('reader', '507f1fbfa201bbdbf8713cf150bb6238db4aa6b63eecaecb40cc701b907ab307',
         'c33d7b2a862c7653e1fb6f26b86d3e06fae9cd51baf0c08fa3f5e6ed3ce0fdf6'),
        ('checker', 'f709a59e4d39eb9e0d1e3ddfe76a98b5375fe4a56c8326d794ab4ee4eeb91762',
         '3215c7339c71eb4c04a25ea809647db4eb95987411d062a821ba8db74d9225ab'),
    ),
    'pdf': (
        ('reader', '9aecfbedbc99f9aa5723bec51faba8a1446be7e98d842ab8e5686ea472e6113b',
         '67a7ca19049f2a660ff778bd87da52c55c384d825df8247eae843ac89e7b4ff0'),
        ('checker', 'd44a6e5732c84ffd10226beef04ad9e1f8f019da151efac7978f92e850fe04e8',
         'bc8dc935b166c17643192d8f11fbbd5ca794a720eeba0d61b97c9f38496b8f34'),
    ),
    'txt-lf': (
        ('reader', 'e895ae3a487228c651b75634ec9e37973acd1fce51d91681d97a007b8b13faba',
         'a85996dd7437209775831af937f52f7a643e29ca9551b698a4778f257a1a84fc'),
        ('checker', 'acd7e3a3e6eba97bdcb9dadace27f10fd0f076b756c83160ab54c86f69a8f953',
         '0f97c7f1cba4cbe17f9663f46007f394ba351a3702a2150466e342bd0fa9e1f2'),
    ),
    'txt-crlf': (
        ('reader', 'e895ae3a487228c651b75634ec9e37973acd1fce51d91681d97a007b8b13faba',
         'a85996dd7437209775831af937f52f7a643e29ca9551b698a4778f257a1a84fc'),
        ('checker', 'acd7e3a3e6eba97bdcb9dadace27f10fd0f076b756c83160ab54c86f69a8f953',
         '0f97c7f1cba4cbe17f9663f46007f394ba351a3702a2150466e342bd0fa9e1f2'),
    ),
    'txt-cr': (
        ('reader', 'e895ae3a487228c651b75634ec9e37973acd1fce51d91681d97a007b8b13faba',
         'a85996dd7437209775831af937f52f7a643e29ca9551b698a4778f257a1a84fc'),
        ('checker', 'acd7e3a3e6eba97bdcb9dadace27f10fd0f076b756c83160ab54c86f69a8f953',
         '0f97c7f1cba4cbe17f9663f46007f394ba351a3702a2150466e342bd0fa9e1f2'),
    ),
    'txt-kept': (
        ('reader', '2a789fda18a5945b36bfe09588dc0a1316826a4718f9662e1610bb091eb45020',
         '02b0ca155a0155d330791541d6a16416b6d99c5468e93a95a4e3c9165e1a7ead'),
        ('checker', '246129e9cf2cd98c52e052078a756c7963a154ac52b50494c50d61209b7dad3d',
         'f25d853c8da7fd318211a72ba7bb584361c6fd155711b79611adb6f668ab87d8'),
    ),
    'txt-bom': (
        ('reader', 'f5f420c1ef1074146edb3f1a0e093319ded762e0dbf9804b2899314434ebd9b0',
         'a04d90cc3a0d51ed1ad6020f0b59640f2c09df0e1d0736c954acc2e9fac838c5'),
        ('checker', '04c2e21d5bd399476e94b52e8121ae5fed5bf2afc6905cb66ad792bb306e4564',
         '76c9a83e2eaf63bb90fb3f9f7a57de66c068c1653c4ba39539ad3cdf6c041170'),
    ),
    'txt-nfc': (
        ('reader', '925a9decedfef735b6110e7b064ac227438f04b585b1f5b76839b4ecd4a51135',
         'caec197773abd36a839e8c313c577439cbad67ec8b5a53b78e3c6bf0659ef072'),
        ('checker', 'a7ef1895095a91dae938b276bbcef1588814a76d3fb32d5b204284032b6c5eb6',
         '1851068d818b4c20cc13f8ae777a9851736295b09a808b7dd10d0e1ef5f0a7fb'),
    ),
    'txt-nfd': (
        ('reader', '925a9decedfef735b6110e7b064ac227438f04b585b1f5b76839b4ecd4a51135',
         'caec197773abd36a839e8c313c577439cbad67ec8b5a53b78e3c6bf0659ef072'),
        ('checker', 'a7ef1895095a91dae938b276bbcef1588814a76d3fb32d5b204284032b6c5eb6',
         '1851068d818b4c20cc13f8ae777a9851736295b09a808b7dd10d0e1ef5f0a7fb'),
    ),
    'paste-crlf': (
        ('reader', '507f1fbfa201bbdbf8713cf150bb6238db4aa6b63eecaecb40cc701b907ab307',
         'c33d7b2a862c7653e1fb6f26b86d3e06fae9cd51baf0c08fa3f5e6ed3ce0fdf6'),
        ('checker', 'f709a59e4d39eb9e0d1e3ddfe76a98b5375fe4a56c8326d794ab4ee4eeb91762',
         '3215c7339c71eb4c04a25ea809647db4eb95987411d062a821ba8db74d9225ab'),
    ),
}
# A key no vendor would take, for the credentials loader this module replaces: no credentials file is read.
SYNTHETIC_CREDENTIALS = SimpleNamespace(api_key='synthetic-key-for-the-wire-pin-not-a-credential', workspace_id='')
# Release 1 sends the credentials' optional workspace as anthropic-workspace-id on the count and on the send
# (studio.fable.client: LiveCoder.client's default_headers, which anthropic 2.11.0 keeps on every request), so the wire
# pin runs each request without one and with this one (refutation round 2, pins[1]).
SYNTHETIC_WORKSPACE = 'wrkspc_synthetic_wire_pin'
WORKSPACE_CREDENTIALS = SimpleNamespace(api_key=SYNTHETIC_CREDENTIALS.api_key, workspace_id=SYNTHETIC_WORKSPACE)

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


def coded(ws, user, case) -> tuple:
    """Code one document of ``case`` in practice ``ws``, uploaded by ``user``, through the shipped job path: the
    (role, Request) pairs the coder was sent, in order, and the round's final state."""
    enc = f.encounter(ws, user, service_date='2026-11-02', insurance='medicare', title='Request identity case')
    made = CASES[case]
    revision = f.paste(enc, user, text=made['paste']) if 'paste' in made else f.upload(enc, user, **made)
    jobs.start_round(enc, revision, models.CodingRound.UPLOAD, user)
    fake = f.FakeCoder(reader=f.succeeded(r.reader_message(RELEASE_1_READER)),
                       checker=f.succeeded(r.checker_message(RELEASE_1_CHECKER)))
    with mock.patch.object(fable_client, 'coder', return_value=fake):
        jobs.run_job(jobs.claim_next())
    return list(fake.calls), models.CodingRound.objects.get(encounter=enc).state


def requests_sent(ws, user, case) -> tuple:
    """Every request the coder was sent for ``case``, in order, as (role, request.sha256, sha256 of the exact
    parameters, attempts), and the round's final state."""
    calls, final = coded(ws, user, case)
    sent = tuple((role, request.sha256, hashlib.sha256(fable_client.canonical(request.params)).hexdigest(),
                  request.attempts) for role, request in calls)
    return sent, final


def overloaded_answer(http_request):
    """A retryable answer, 529 (the API overloaded): the SDK would send again unless told not to (max_retries=0)."""
    return httpx2.Response(529, json={'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'in memory'}})


def timed_out_answer(http_request):
    """A read that times out, which the SDK's exception branch would retry unless told not to."""
    raise httpx2.ReadTimeout('in memory', request=http_request)


def on_the_wire(request, credentials=SYNTHETIC_CREDENTIALS, answer=None) -> tuple:
    """What the SDK puts on the wire for ``request`` through the shipped LiveCoder - its own client construction, the
    token count, then the send - over an in-memory httpx2.MockTransport that answers 400, or as ``answer`` does.
    Nothing leaves the process: the base URL is a closed local port as a second guard, the key is synthetic and the
    credentials loader is replaced (it hands over ``credentials``). ((method and path, sha256 of the body,
    anthropic-beta, anthropic-version, anthropic-workspace-id) of each HTTP request, the send's status, the count)."""
    captured = []

    def refuse(http_request):
        captured.append(http_request)
        if answer is not None:
            return answer(http_request)
        return httpx2.Response(400, json={'type': 'error', 'error': {
            'type': 'invalid_request_error', 'message': 'in memory: nothing was sent'}})

    def sdk(**kwargs):
        kwargs['base_url'] = 'http://127.0.0.1:9'
        return anthropic.Anthropic(http_client=httpx2.Client(transport=httpx2.MockTransport(refuse)), **kwargs)

    coder = fable_client.LiveCoder(credentials_file='(synthetic: the loader is replaced)', read_timeout=5, sdk=sdk)
    quiet = logging.root.manager.disable
    logging.disable(logging.CRITICAL)  # the transport's request lines and the coder's warnings about the 400s
    try:
        with mock.patch.object(fable_client.fable_credentials, 'load', return_value=credentials):
            counted = coder.count_input_tokens(request)
            outcome = coder.send(request)
    finally:
        logging.disable(quiet)
    wire = tuple((f'{sent.method} {sent.url.raw_path.decode()}', hashlib.sha256(sent.content).hexdigest(),
                  sent.headers.get('anthropic-beta', ''), sent.headers.get('anthropic-version', ''),
                  sent.headers.get('anthropic-workspace-id')) for sent in captured)
    return wire, outcome.http_status, counted


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

    def test_the_settings_are_those_the_pins_were_measured_at(self):
        # the owner's effort (class d, D358): 'high' since R2-33 (D433, D434; release 1's setting was 'max'), the effort
        # every pin here was measured at; a run under another one is sent another request, so say it first
        self.assertEqual(settings.CODING_EFFORT, 'high')
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

    def test_each_request_goes_on_the_wire_as_release_1_s(self):
        ws = f.workspace('Requests')
        user = f.member(ws)
        for case in CASES:
            with self.subTest(case=case):
                calls, final = coded(ws, user, case)
                self.assertEqual(final, models.CodingRound.DONE)
                sent = []
                for role, request in calls:
                    plain = on_the_wire(request)
                    named = on_the_wire(request, WORKSPACE_CREDENTIALS)
                    for (wire, status, counted), workspace in ((plain, None), (named, SYNTHETIC_WORKSPACE)):
                        # the in-memory transport answered both (a 400: no count, a failed send): it saw all there was
                        self.assertEqual((status, counted), (400, None))
                        self.assertEqual([(where, beta, version) for where, _, beta, version, _ in wire],
                                         [COUNT_ON_THE_WIRE, SEND_ON_THE_WIRE])
                        self.assertEqual([named_as for *_, named_as in wire], [workspace, workspace])
                    # the workspace is a header only: the bodies are the same either way
                    self.assertEqual([body for _, body, *_ in named[0]], [body for _, body, *_ in plain[0]])
                    sent.append((role, plain[0][0][1], plain[0][1][1]))
                    # nothing is sent again automatically: a 529 and a timeout leave the same one count and one send
                    for answer, expected in ((overloaded_answer, (529, None)), (timed_out_answer, (None, None))):
                        again, status, counted = on_the_wire(request, answer=answer)
                        self.assertEqual((status, counted), expected)
                        self.assertEqual(again, plain[0])
                self.assertEqual(tuple(sent), RELEASE_1_WIRE[case])


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
