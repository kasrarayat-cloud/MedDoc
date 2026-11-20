"""studio.fable.document (BUILD-SPEC 4.3): the document block for a PDF, a Word file (through a converter) and text,
its stored form, and every way a document cannot be sent; and the Word package LibreOffice is given (SEC-S6: no link of
the document reaches outside it - proven with a link-following stand-in for soffice and a loopback listener, and, where
a LibreOffice is named by CPT_STUDIO_TEST_SOFFICE or on the PATH, with LibreOffice itself). Synthetic bytes only."""
import base64
import hashlib
import http.server
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from unittest import mock, skipUnless

from django.test import SimpleTestCase, TestCase, override_settings

from studio.fable import CONVERT, DOCUMENT, STORAGE
from studio.fable import document
from studio.storage import ALLOWED_SUFFIXES, OriginalCorrupted
from tests.support import coding as f

DOCX = ALLOWED_SUFFIXES['.docx']
CONVERTED = b'%PDF-1.4\n% synthetic conversion\n%%EOF\n'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
WORD_MAIN = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
# the Open Packaging Conventions' namespaces, stated here as the standard gives them (ECMA-376 Part 2)
RELATIONSHIPS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
NAMESPACES = (f'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="{REL}" '
              'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
              'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
              'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
TEXT = '<w:p><w:r><w:t>SYNTHETIC NOTE - FICTIONAL - NO PATIENT DATA</w:t></w:r></w:p>'
# a picture LINKED, not embedded: the relationship rIdImg names where it is (r:link)
LINKED_PICTURE = (
    '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="609600" cy="609600"/><wp:docPr id="1" name="p"/><a:graphic>'
    '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr>'
    '<pic:cNvPr id="1" name="p"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:link="rIdImg"/><a:stretch>'
    '<a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="609600" cy="609600"/>'
    '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
    '</wp:inline></w:drawing></w:r></w:p>')


def relationship(rid, kind, target, mode=None):
    return (f'<Relationship Id="{rid}" Type="{REL}/{kind}" Target="{target}"'
            + (f' TargetMode="{mode}"' if mode is not None else '') + '/>')


def relationships(*rows):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships '
            f'xmlns="{RELATIONSHIPS_NS}">{"".join(rows)}</Relationships>')


def word_package(body=TEXT, document_rels=None, *, main_type=WORD_MAIN, overrides='', parts=(), root_rels=None):
    """A synthetic .docx: its content types, the package relationships, the main document part with ``body`` and, when
    given, the main part's relationships (``document_rels``, a list of <Relationship/> rows) and more ``parts``."""
    entries = [
        ('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types '
         f'xmlns="{CONTENT_TYPES_NS}"><Default Extension="rels" '
         'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
         f'<Override PartName="/word/document.xml" ContentType="{main_type}"/>{overrides}</Types>'),
        ('_rels/.rels', root_rels if root_rels is not None
         else relationships(relationship('rId1', 'officeDocument', 'word/document.xml'))),
        ('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
         f'<w:document {NAMESPACES}><w:body>{body}</w:body></w:document>')]
    if document_rels is not None:
        entries.append(('word/_rels/document.xml.rels', relationships(*document_rels)))
    return zipped(entries + list(parts))


def zipped(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


def parts_of(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def opendocument(href):
    """An OpenDocument text whose picture is linked from ``href``: LibreOffice reads it as such whatever its name."""
    content = ('<?xml version="1.0" encoding="UTF-8"?><office:document-content '
               'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
               'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
               'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
               'xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.2"><office:body><office:text>'
               '<text:p>SYNTHETIC NOTE</text:p><text:p><draw:frame svg:width="2cm" svg:height="2cm">'
               f'<draw:image xlink:href="{href}" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>'
               '</draw:frame></text:p></office:text></office:body></office:document-content>')
    manifest = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest '
                'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                '<manifest:file-entry manifest:full-path="/" '
                'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '</manifest:manifest>')
    return zipped([('mimetype', 'application/vnd.oasis.opendocument.text'), ('META-INF/manifest.xml', manifest),
                   ('content.xml', content)])


PLAIN_PACKAGE = word_package()


def fake_runner(data):  # runs in the bounded child (Django-free), on the package safe_package made
    return CONVERTED + data[:4]


def failing_runner(data):
    raise RuntimeError('synthetic conversion failure')


def no_pdf_runner(data):
    return b'not a pdf'


class PrepareTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.originals = tempfile.TemporaryDirectory()
        cls.override = override_settings(ORIGINALS_DIR=Path(cls.originals.name))
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.originals.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.user)

    def test_a_pdf_is_sent_as_base64_with_citations_and_stored_without_it(self):
        rev = f.upload(self.enc, self.user, f.PDF_BYTES, 'synthetic-note.pdf')
        doc = document.prepare(rev)
        self.assertEqual(doc.kind, 'pdf')
        self.assertEqual(doc.block, {'type': 'document', 'title': 'synthetic-note.pdf', 'citations': {'enabled': True},
                                     'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                'data': base64.standard_b64encode(f.PDF_BYTES).decode('ascii')}})
        digest = hashlib.sha256(f.PDF_BYTES).hexdigest()
        self.assertEqual(doc.stored_block['source']['data'], {'$original_sha256': digest,
                                                              '$original_bytes': len(f.PDF_BYTES)})
        self.assertEqual((doc.sha256, doc.source_sha256, doc.size), (digest, digest, len(f.PDF_BYTES)))
        self.assertNotIn(base64.standard_b64encode(f.PDF_BYTES).decode('ascii'), str(doc.stored_block))

    def test_a_word_file_is_converted_and_sent_as_a_pdf_naming_its_source(self):
        docx = PLAIN_PACKAGE
        rev = f.upload(self.enc, self.user, docx, 'synthetic-note.docx', DOCX)
        doc = document.prepare(rev, converter=lambda data: CONVERTED)
        self.assertEqual((doc.kind, doc.title, doc.data), ('docx', 'synthetic-note.docx', CONVERTED))
        self.assertEqual(doc.block['source']['media_type'], 'application/pdf')
        self.assertEqual(doc.stored_block['source']['data'], {
            '$original_sha256': hashlib.sha256(CONVERTED).hexdigest(), '$original_bytes': len(CONVERTED),
            '$converted_from': {'media_type': DOCX, 'sha256': hashlib.sha256(docx).hexdigest(), 'bytes': len(docx)}})

    def test_a_failed_conversion_is_convert(self):
        rev = f.upload(self.enc, self.user, b'PK\x03\x04synthetic docx', 'synthetic-note.docx', DOCX)
        for converter in (lambda data: b'no pdf here', lambda data: (_ for _ in ()).throw(ValueError('x')),
                          lambda data: (_ for _ in ()).throw(document.DocumentError(CONVERT, 'x'))):
            with self.subTest(converter=converter), self.assertRaises(document.DocumentError) as caught:
                document.prepare(rev, converter=converter)
            self.assertEqual(caught.exception.failure_kind, CONVERT)

    def test_a_text_file_and_a_paste_are_text_blocks(self):
        rev = f.upload(self.enc, self.user, b'\xef\xbb\xbfLine one\r\nLine two\x00', 'note.txt', 'text/plain')
        doc = document.prepare(rev)
        self.assertEqual(doc.block['source'], {'type': 'text', 'media_type': 'text/plain',
                                               'data': 'Line one\nLine two'})
        self.assertEqual(doc.stored_block, doc.block)
        self.assertEqual(doc.block['citations'], {'enabled': True})
        pasted = document.prepare(f.paste(self.enc, self.user, 'Pasted synthetic note.'))
        self.assertEqual((pasted.kind, pasted.title, pasted.block['source']['data']),
                         ('paste', 'Pasted text', 'Pasted synthetic note.'))

    def test_text_that_cannot_be_sent_is_document(self):
        for rev in (f.upload(self.enc, self.user, b'\xff\xfe not utf-8', 'bad.txt', 'text/plain'),
                    f.paste(self.enc, self.user, ' \n\t ')):
            with self.subTest(kind=rev.kind), self.assertRaises(document.DocumentError) as caught:
                document.prepare(rev)
            self.assertEqual(caught.exception.failure_kind, DOCUMENT)

    def test_a_stored_original_that_does_not_read_back_is_storage(self):
        rev = f.upload(self.enc, self.user)
        for error in (OriginalCorrupted('synthetic'), FileNotFoundError('synthetic')):
            with self.subTest(error=error), self.assertRaises(document.DocumentError) as caught:
                document.prepare(rev, reader=mock.Mock(side_effect=error))
            self.assertEqual(caught.exception.failure_kind, STORAGE)
            self.assertEqual(caught.exception.text, document.STORAGE_TEXT)


class ConvertTests(SimpleTestCase):
    def test_the_conversion_runs_in_the_bounded_child(self):
        self.assertEqual(document.convert_docx(PLAIN_PACKAGE, runner=fake_runner), CONVERTED + b'PK\x03\x04')

    def test_a_child_that_fails_or_returns_no_pdf_is_convert(self):
        for runner in (failing_runner, no_pdf_runner):
            with self.subTest(runner=runner.__name__), self.assertRaises(document.DocumentError) as caught:
                document.convert_docx(PLAIN_PACKAGE, runner=runner)
            self.assertEqual((caught.exception.failure_kind, caught.exception.text), (CONVERT, document.CONVERT_TEXT))

    def test_a_child_past_its_time_is_convert(self):
        with self.assertRaises(document.DocumentError) as caught:
            document.convert_docx(PLAIN_PACKAGE, runner=_sleeps, seconds=0.5)
        self.assertIn('time', caught.exception.detail)

    def test_every_converter_is_given_the_safe_package_and_a_refused_one_is_convert_before_it_runs(self):
        crafted = word_package(TEXT + LINKED_PICTURE, [relationship('rIdImg', 'image', 'http://192.0.2.1/x.png',
                                                                    'External')])
        self.assertEqual(document.convert_docx(crafted, runner=_echo_package),
                         CONVERTED + document.safe_package(crafted))
        self.assertNotIn(b'192.0.2.1', parts_of(document.safe_package(crafted))['word/_rels/document.xml.rels'])
        for refused in (b'PK\x03\x04 not a zip', opendocument('http://192.0.2.1/x.png')):
            with self.subTest(refused=refused[:12]), self.assertRaises(document.DocumentError) as caught:
                document.convert_docx(refused, runner=failing_runner)  # never reached: the package is refused first
            self.assertEqual((caught.exception.failure_kind, caught.exception.text), (CONVERT, document.CONVERT_TEXT))
            self.assertIn('the Word package was refused', caught.exception.detail)

    def test_soffice_runs_with_a_throwaway_home_and_profile_and_no_inherited_environment(self):
        seen = {}

        class Process:
            pid, returncode = 999_999_999, 0

            def __init__(self, command, **kwargs):
                seen.update(command=command, **kwargs)
                profile = Path(command[1].split('=', 1)[1].removeprefix('file://'))
                seen['profile_settings'] = (profile / 'user' / 'registrymodifications.xcu').read_text(encoding='utf-8')
                out = Path(command[command.index('--outdir') + 1])
                (out / 'document.pdf').write_bytes(CONVERTED)

            def wait(self, timeout=None):
                return 0
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'must-not-leak'}), \
                mock.patch('subprocess.Popen', Process), mock.patch('os.killpg') as killpg:
            self.assertEqual(document.soffice_convert(PLAIN_PACKAGE), CONVERTED)
        command, env = seen['command'], seen['env']
        # the throwaway profile follows no untrusted link (a second guard behind safe_package)
        self.assertEqual(seen['profile_settings'], document.PROFILE_SETTINGS)
        self.assertIn('<prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop>',
                      document.PROFILE_SETTINGS)
        self.assertEqual(command[0], 'soffice')
        self.assertIn('--headless', command)
        self.assertEqual(command[command.index('--convert-to') + 1], 'pdf')
        self.assertEqual(sorted(env), ['HOME', 'LANG', 'PATH', 'TMPDIR'])
        work = Path(seen['cwd'])
        self.assertTrue(env['HOME'].startswith(str(work)) and env['TMPDIR'].startswith(str(work)))
        self.assertIn(f'-env:UserInstallation={(work / "profile").as_uri()}', command)
        self.assertTrue(seen['start_new_session'])
        killpg.assert_called_once()
        self.assertFalse(work.exists())  # the throwaway directory is gone


def _sleeps(data):
    import time

    time.sleep(30)


def _echo_package(data):  # runs in the bounded child: a PDF carrying what it was given, for the test to compare
    return CONVERTED + data


class SafePackageTests(SimpleTestCase):
    """SEC-S6: the Word package LibreOffice is given has no relationship that reaches outside it, and only a Word
    package is converted."""

    def test_a_package_with_nothing_external_keeps_every_part_byte_for_byte(self):
        embedded = word_package(TEXT, [relationship('rIdImg', 'image', 'media/image1.png')],
                                parts=[('word/media/image1.png', b'\x89PNG synthetic')])
        for data in (PLAIN_PACKAGE, embedded, _installer_docx()):
            with self.subTest(parts=sorted(parts_of(data))):
                self.assertEqual(parts_of(document.safe_package(data)), parts_of(data))
                with zipfile.ZipFile(io.BytesIO(document.safe_package(data))) as archive:
                    self.assertEqual(archive.namelist(), zipfile.ZipFile(io.BytesIO(data)).namelist())

    def test_every_relationship_that_reaches_outside_is_dropped_and_the_rest_kept(self):
        crafted = word_package(
            TEXT + LINKED_PICTURE,
            [relationship('rIdStyles', 'styles', 'styles.xml'),
             relationship('rIdImg', 'image', 'http://192.0.2.1/x.png', 'External'),
             relationship('rIdFile', 'image', 'file:///synthetic/secret.png', 'External'),
             relationship('rIdUp', 'image', '../secret.png', 'External'),
             relationship('rIdLower', 'image', 'http://192.0.2.1/y.png', 'external'),
             relationship('rIdLink', 'hyperlink', 'https://example.test/', 'External'),
             relationship('rIdKept', 'image', 'media/image1.png', 'Internal')],
            parts=[('word/styles.xml', f'<w:styles xmlns:w="{WORD_NS}"/>'),
                   ('word/media/image1.png', b'\x89PNG synthetic'),
                   ('word/settings.xml', f'<w:settings xmlns:w="{WORD_NS}"/>'),
                   ('word/_rels/settings.xml.rels', relationships(
                       relationship('rIdT', 'attachedTemplate', 'http://192.0.2.1/t.dotx', 'External')))],
            root_rels=relationships(
                relationship('rId1', 'officeDocument', 'word/document.xml'),
                relationship('rIdThumb', 'metadata/thumbnail', 'http://192.0.2.1/t.png', 'External')))
        safe = parts_of(document.safe_package(crafted))
        for name in ('_rels/.rels', 'word/_rels/document.xml.rels', 'word/_rels/settings.xml.rels'):
            with self.subTest(part=name):
                self.assertNotIn(b'TargetMode="External"', safe[name])
                self.assertNotIn(b'192.0.2.1', safe[name])
                self.assertNotIn(b'secret', safe[name])
        kept = safe['word/_rels/document.xml.rels'].decode()
        self.assertIn(relationship('rIdStyles', 'styles', 'styles.xml'), kept)
        self.assertIn(relationship('rIdKept', 'image', 'media/image1.png', 'Internal'), kept)
        self.assertNotIn('rIdLink', kept)  # a hyperlink's text stays in the document; only the link target goes
        self.assertIn(relationship('rId1', 'officeDocument', 'word/document.xml'), safe['_rels/.rels'].decode())
        # nothing else of any part changes: the document, its pictures and its styles as uploaded
        original = parts_of(crafted)
        for name in ('[Content_Types].xml', 'word/document.xml', 'word/styles.xml', 'word/media/image1.png'):
            self.assertEqual(safe[name], original[name], name)

    def test_a_part_only_dropped_relationships_named_is_dropped_with_its_relationships(self):
        crafted = word_package(TEXT, [relationship('rIdOdd', 'image', 'media/only-external.png', 'External'),
                                      relationship('rIdBoth', 'image', 'media/shared.png', 'External'),
                                      relationship('rIdShared', 'image', 'media/shared.png')],
                               parts=[('word/media/only-external.png', b'\x89PNG one'),
                                      ('word/media/_rels/only-external.png.rels', relationships()),
                                      ('word/media/shared.png', b'\x89PNG two')])
        safe = parts_of(document.safe_package(crafted))
        self.assertNotIn('word/media/only-external.png', safe)
        self.assertNotIn('word/media/_rels/only-external.png.rels', safe)
        self.assertEqual(safe['word/media/shared.png'], b'\x89PNG two')  # an internal relationship names it too

    def test_what_is_not_a_word_package_is_refused(self):
        def refused(data, said):
            with self.assertRaises(document.PackageRefused) as caught:
                document.safe_package(data)
            self.assertIn(said, str(caught.exception))

        def renamed(name, new):
            return zipped([(new if entry == name else entry, content)
                           for entry, content in parts_of(PLAIN_PACKAGE).items()])

        twice = io.BytesIO()
        with zipfile.ZipFile(twice, 'w') as archive:
            for name, content in parts_of(PLAIN_PACKAGE).items():
                archive.writestr(name, content)
            archive.writestr('WORD/document.xml', b'<w:document/>')
        locked = _encrypted_flag(PLAIN_PACKAGE, 'word/document.xml')
        cases = [
            (b'PK\x03\x04 synthetic, not a zip', 'not a zip'),
            (opendocument('http://192.0.2.1/x.png'), 'OpenDocument'),
            (zipped(list(parts_of(PLAIN_PACKAGE).items()) + [('mimetype', 'application/vnd.oasis.opendocument.text')]),
             'OpenDocument'),
            (renamed('[Content_Types].xml', 'content-types.xml'), 'not a Word package'),
            (renamed('_rels/.rels', '_rels/other.rels'), 'not a Word package'),
            (word_package(root_rels=relationships()), 'no single main document part'),
            (word_package(root_rels=relationships(relationship('rId1', 'officeDocument', 'http://192.0.2.1/d.xml',
                                                               'External'))), 'no single main document part'),
            (word_package(root_rels=relationships(relationship('rId1', 'officeDocument', 'word/gone.xml'))),
             'main document part is missing'),
            (word_package(main_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'),
             'not a Word document'),
            (word_package(main_type='application/vnd.ms-word.document.macroEnabled.main+xml'), 'not a Word document'),
            (twice.getvalue(), 'named twice'),
            (locked, 'encrypted'),
            (word_package(TEXT, ['<!DOCTYPE r [<!ENTITY e "x">]>']), 'not well-formed XML'),
            (zipped(list(parts_of(PLAIN_PACKAGE).items()) + [(
                'word/_rels/document.xml.rels', '<?xml version="1.0"?><!DOCTYPE Relationships [<!ENTITY e "x">]>'
                f'<Relationships xmlns="{RELATIONSHIPS_NS}"/>')]), 'declares a DTD'),
            (zipped(list(parts_of(PLAIN_PACKAGE).items()) + [('word/_rels/document.xml.rels', '<Other/>')]),
             'not a package relationships part'),
        ]
        for data, said in cases:
            with self.subTest(said=said):
                refused(data, said)
        with mock.patch.object(document, 'MAX_PACKAGE_PARTS', 2):
            refused(PLAIN_PACKAGE, 'more than 2 parts')
        with mock.patch.object(document, 'MAX_PACKAGE_BYTES', 100):
            refused(PLAIN_PACKAGE, 'too large once inflated')


def _encrypted_flag(data, name):
    """``data`` with the part ``name`` marked encrypted (general purpose flag bit 0) in its local header and its central
    directory entry, as an encrypting zip tool writes it (zipfile itself never writes the bit)."""
    raw = bytearray(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        local = archive.getinfo(name).header_offset
    assert raw[local:local + 4] == b'PK\x03\x04'
    raw[local + 6] |= 0x1
    end = raw.rfind(b'PK\x05\x06')
    at = int.from_bytes(raw[end + 16:end + 20], 'little')
    while raw[at:at + 4] == b'PK\x01\x02':
        size = 46 + sum(int.from_bytes(raw[at + k:at + k + 2], 'little') for k in (28, 30, 32))
        if raw[at + 46:at + 46 + int.from_bytes(raw[at + 28:at + 30], 'little')] == name.encode():
            raw[at + 8] |= 0x1
        at += size
    return bytes(raw)


def _installer_docx():
    """ops/install.py's synthetic Word file, which its conversion gate converts in the built image: it must stay a
    package safe_package passes unchanged."""
    from ops import install
    return install.synthetic_docx()


# --- SEC-S6 end to end: a crafted Word file pointing at a loopback listener -----------------------------------------

# A stand-in for soffice that follows every link a converter could: each http(s) target of a relationship marked
# External in any relationships part, and each xlink:href of an OpenDocument content part, is fetched; then it writes a
# PDF where soffice would. Run as soffice_convert runs soffice (its own argv and empty environment).
LINK_FOLLOWER = """#!{python}
import re, sys, urllib.request, zipfile
args = sys.argv[1:]
out, source = args[args.index('--outdir') + 1], args[-1]
targets = []
with zipfile.ZipFile(source) as archive:
    for name in archive.namelist():
        text = archive.read(name).decode('utf-8', 'replace')
        if name.endswith('.rels'):
            for row in re.findall(r'<Relationship\\b[^>]*>', text):
                mode = re.search(r'TargetMode="([^"]*)"', row)
                target = re.search(r'Target="([^"]*)"', row)
                if mode and mode.group(1) != 'Internal' and target:
                    targets.append(target.group(1))
        elif name == 'content.xml':
            targets += re.findall(r'xlink:href="([^"]*)"', text)
for target in targets:
    if target.startswith(('http://', 'https://')):
        try:
            urllib.request.urlopen(target, timeout=5).read()
        except Exception:
            pass
open(out + '/document.pdf', 'wb').write(b'%PDF-1.4 synthetic stand-in\\n%%EOF\\n')
"""


class _Listener:
    """A loopback HTTP listener that records every request made to it."""

    def __init__(self):
        self.requests = []
        listener = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                listener.requests.append(f'{self.command} {self.path}')
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', '8')
                self.end_headers()
                self.wfile.write(b'\x89PNG\r\n\x1a\n')

            def do_HEAD(self):  # noqa: N802
                listener.requests.append(f'{self.command} {self.path}')
                self.send_response(200)
                self.end_headers()

            do_OPTIONS = do_PROPFIND = do_HEAD

            def log_message(self, *args):
                pass
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class ListenerTests(SimpleTestCase):
    def crafted(self, url):
        return word_package(TEXT + LINKED_PICTURE, [relationship('rIdImg', 'image', f'{url}/linked.png', 'External')])

    def test_the_stand_in_follows_links_so_the_listener_would_hear_one(self):
        # the positive control: the stand-in, given the crafted package as uploaded, does reach the listener
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        follower = _follower(folder)
        with _Listener() as listener:
            (folder / 'out').mkdir()
            source = folder / 'in.docx'
            source.write_bytes(self.crafted(listener.url))
            subprocess.run([str(follower), '--outdir', str(folder / 'out'), str(source)], env={}, check=True,
                           timeout=30)
        self.assertEqual(listener.requests, ['GET /linked.png'])

    def test_a_crafted_word_file_pointing_at_a_local_listener_converts_without_any_request_reaching_it(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with _Listener() as listener, mock.patch.object(document, 'SOFFICE', str(_follower(folder))):
            pdf = document.convert_docx(self.crafted(listener.url))  # the real bounded child and soffice_convert
            heard = list(listener.requests)
            odt = _outcome(opendocument(f'{listener.url}/odt.png'))  # an OpenDocument file named .docx
        self.assertEqual(heard, [])
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual((odt, listener.requests), (CONVERT, []))

    @skipUnless(os.environ.get('CPT_STUDIO_TEST_SOFFICE') or shutil.which('soffice'),
                'no LibreOffice here (CPT_STUDIO_TEST_SOFFICE names one; the image has one)')
    def test_with_libreoffice_itself_no_request_reaches_the_listener(self):
        with _Listener() as listener, mock.patch.object(document, 'SOFFICE', os.environ.get('CPT_STUDIO_TEST_SOFFICE')
                                                        or shutil.which('soffice')):
            pdf = document.convert_docx(self.crafted(listener.url))
            heard = list(listener.requests)
            odt = _outcome(opendocument(f'{listener.url}/odt.png'))
            plain = document.convert_docx(PLAIN_PACKAGE)
        self.assertEqual(heard, [])
        self.assertTrue(pdf.startswith(b'%PDF-') and plain.startswith(b'%PDF-'))
        self.assertEqual((odt, listener.requests), (CONVERT, []))


def _outcome(data):
    """'converted', or the failure kind of the DocumentError converting ``data`` raised."""
    try:
        document.convert_docx(data)
    except document.DocumentError as exc:
        return exc.failure_kind
    return 'converted'


def _follower(folder):
    path = Path(folder) / 'soffice-stand-in'
    path.write_text(LINK_FOLLOWER.replace('{python}', sys.executable), encoding='utf-8')
    path.chmod(0o700)
    return path
