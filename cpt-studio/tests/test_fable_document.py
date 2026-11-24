"""studio.fable.document (BUILD-SPEC 4.3) and studio.fable.docx_package (release 1 E1 and E2): the document block for a
PDF, a Word file (through a converter) and text, its stored form, and every way a document cannot be sent; the Word
package LibreOffice is given (SEC-S6: no link of the document reaches outside it - proven with a link-following
stand-in for soffice and a loopback listener, and, where a LibreOffice is named by CPT_STUDIO_TEST_SOFFICE or on the
PATH, with LibreOffice itself); E1's limits on that package and the clean-up of every conversion; E2's removal of field
instructions and embedded content by byte ranges, where a Word file that needs no change gives exactly the package the
code before release 1 gave (that code is kept below as the reference: legacy_safe_package). Synthetic bytes only; every
package is built here, never read from a file."""
import base64
import hashlib
import http.server
import io
import os
import posixpath
import random
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
import zlib
from pathlib import Path
from unittest import mock, skipUnless
from xml.etree import ElementTree
from xml.parsers import expat
from xml.sax.saxutils import escape, quoteattr

from django.test import SimpleTestCase, TestCase, override_settings

from studio import bounded
from studio.fable import CONVERT, DOCUMENT, STORAGE
from studio.fable import document, docx_package
from studio.storage import ALLOWED_SUFFIXES, OriginalCorrupted
from tests.support import coding as f
from tests.test_bounded import GRANDCHILD, kill_marked, marked

DOCX = ALLOWED_SUFFIXES['.docx']
CONVERTED = b'%PDF-1.4\n% synthetic conversion\n%%EOF\n'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
WORD_MAIN = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
# the Open Packaging Conventions' namespaces, stated here as the standard gives them (ECMA-376 Part 2)
RELATIONSHIPS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
STRICT_WORD_NS = 'http://purl.oclc.org/ooxml/wordprocessingml/main'
CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
NAMESPACES = (f'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="{REL}" '
              'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
              'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
              'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
# and the legacy picture and markup-compatibility ones a Word file also declares on its root
FULL_NAMESPACES = (NAMESPACES + ' xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"'
                   ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
                   ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
                   ' xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'
                   ' xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"'
                   ' mc:Ignorable="w14 wp14"')
TEXT = '<w:p><w:r><w:t>SYNTHETIC NOTE - FICTIONAL - NO PATIENT DATA</w:t></w:r></w:p>'
# a picture LINKED, not embedded: the relationship rIdImg names where it is (r:link)
LINKED_PICTURE = (
    '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="609600" cy="609600"/><wp:docPr id="1" name="p"/><a:graphic>'
    '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr>'
    '<pic:cNvPr id="1" name="p"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:link="rIdImg"/><a:stretch>'
    '<a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="609600" cy="609600"/>'
    '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
    '</wp:inline></w:drawing></w:r></w:p>')
EMBEDDED_DRAWING = LINKED_PICTURE.replace('r:link="rIdImg"', 'r:embed="rIdPic"')[len('<w:p><w:r>'):-len('</w:r></w:p>')]
PNG = b'\x89PNG\r\n\x1a\n synthetic picture bytes'
STORY = 'application/vnd.openxmlformats-officedocument.wordprocessingml.{}+xml'


def relationship(rid, kind, target, mode=None):
    return (f'<Relationship Id="{rid}" Type="{REL}/{kind}" Target="{target}"'
            + (f' TargetMode="{mode}"' if mode is not None else '') + '/>')


def relationships(*rows):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships '
            f'xmlns="{RELATIONSHIPS_NS}">{"".join(rows)}</Relationships>')


def content_types(*overrides, defaults=''):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types '
            f'xmlns="{CONTENT_TYPES_NS}"><Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
            f'{defaults}{"".join(overrides)}</Types>')


def override(part, content_type):
    return f'<Override PartName="/{part}" ContentType="{content_type}"/>'


def word_package(body=TEXT, document_rels=None, *, main_type=WORD_MAIN, overrides='', parts=(), root_rels=None,
                 namespaces=NAMESPACES):
    """A synthetic .docx: its content types, the package relationships, the main document part with ``body`` and, when
    given, the main part's relationships (``document_rels``, a list of <Relationship/> rows) and more ``parts``."""
    entries = [
        ('[Content_Types].xml', content_types(override('word/document.xml', main_type), overrides)),
        ('_rels/.rels', root_rels if root_rels is not None
         else relationships(relationship('rId1', 'officeDocument', 'word/document.xml'))),
        ('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
         f'<w:document {namespaces}><w:body>{body}</w:body></w:document>')]
    if document_rels is not None:
        entries.append(('word/_rels/document.xml.rels', relationships(*document_rels)))
    return zipped(entries + list(parts))


def prefixed_package(body, prefix):
    """A synthetic .docx whose main part writes the WordprocessingML namespace with ``prefix`` instead of 'w'."""
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<w:document xmlns:w="{WORD_NS}"><w:body>{body}</w:body></w:document>').replace('w:', f'{prefix}:')
    return zipped([('[Content_Types].xml', content_types(override('word/document.xml', WORD_MAIN))),
                   ('_rels/.rels', relationships(relationship('rId1', 'officeDocument', 'word/document.xml'))),
                   ('word/document.xml', xml.replace('xmlns:w=', f'xmlns:{prefix}='))])


def full_package(body=TEXT, *, header=TEXT, footer=TEXT, footnote=TEXT, endnote=TEXT, comment=TEXT, glossary=TEXT,
                 namespaces=FULL_NAMESPACES, document_rels=(), defaults='', parts=(), stored=()):
    """A synthetic .docx with every story E2 covers: the main document (``body`` and a section naming the header and
    the footer), a header, a footer, footnotes, endnotes, comments and a glossary document, each holding the given
    paragraphs; ``document_rels`` and ``parts`` add to it; ``stored`` names parts kept uncompressed."""
    def story(root, inner):
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:{root} {namespaces}>{inner}</w:{root}>'
    section = ('<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/>'
               '<w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>')
    entries = [
        ('[Content_Types].xml', content_types(
            override('word/document.xml', WORD_MAIN), override('word/header1.xml', STORY.format('header')),
            override('word/footer1.xml', STORY.format('footer')),
            override('word/footnotes.xml', STORY.format('footnotes')),
            override('word/endnotes.xml', STORY.format('endnotes')),
            override('word/comments.xml', STORY.format('comments')),
            override('word/glossary/document.xml', STORY.format('document.glossary')), defaults=defaults)),
        ('_rels/.rels', relationships(relationship('rId1', 'officeDocument', 'word/document.xml'))),
        ('word/document.xml', story('document', f'<w:body>{body}{section}</w:body>')),
        ('word/_rels/document.xml.rels', relationships(
            relationship('rIdHeader', 'header', 'header1.xml'), relationship('rIdFooter', 'footer', 'footer1.xml'),
            relationship('rIdFootnotes', 'footnotes', 'footnotes.xml'),
            relationship('rIdEndnotes', 'endnotes', 'endnotes.xml'),
            relationship('rIdComments', 'comments', 'comments.xml'),
            relationship('rIdGlossary', 'glossaryDocument', 'glossary/document.xml'), *document_rels)),
        ('word/header1.xml', story('hdr', header)),
        ('word/footer1.xml', story('ftr', footer)),
        ('word/footnotes.xml', story('footnotes', f'<w:footnote w:id="1">{footnote}</w:footnote>')),
        ('word/endnotes.xml', story('endnotes', f'<w:endnote w:id="1">{endnote}</w:endnote>')),
        ('word/comments.xml', story('comments', f'<w:comment w:id="0" w:author="Synthetic">{comment}</w:comment>')),
        ('word/glossary/document.xml', story(
            'glossaryDocument', f'<w:docParts><w:docPart><w:docPartBody>{glossary}</w:docPartBody></w:docPart>'
                                '</w:docParts>')),
    ]
    return zipped(entries + list(parts), stored=stored)


def zipped(entries, *, stored=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content, compress_type=zipfile.ZIP_STORED if name in stored else None)
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


# Runners: run in the bounded child (Django-free) on the package safe_package made and the work folder its parent made.
def fake_runner(data, work):
    return CONVERTED + data[:4]


def failing_runner(data, work):
    raise RuntimeError('synthetic conversion failure')


def no_pdf_runner(data, work):
    return b'not a pdf'


def _sleeps(data, work):
    time.sleep(30)


def _echo_package(data, work):  # a PDF carrying what it was given, for the test to compare
    return CONVERTED + data


# --- fields, as Word writes them ----------------------------------------------------------------------------------

def paragraph(*content, properties=''):
    return f'<w:p>{properties}{"".join(content)}</w:p>'


def complex_field(instruction, result='VISIBLE RESULT', *, text='instrText'):
    """A complex field in runs of its own: begin, the instruction, separate, the result, end."""
    return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:{text} xml:space="preserve">{escape(instruction)}</w:{text}></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:t>{escape(result)}</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def simple_field(instruction, result='VISIBLE RESULT'):
    return f'<w:fldSimple w:instr={quoteattr(instruction)}><w:r><w:t>{escape(result)}</w:t></w:r></w:fldSimple>'


def without_complex_field(xml, instruction, *, text='instrText'):
    """``xml`` as E2 leaves it once the complex_field(instruction) in it lost its instruction: from begin to separate
    only the run boundaries remain, and the end mark goes - every other byte unchanged."""
    begin_to_separate = ('<w:fldChar w:fldCharType="begin"/></w:r>'
                         f'<w:r><w:{text} xml:space="preserve">{escape(instruction)}</w:{text}></w:r>'
                         '<w:r><w:fldChar w:fldCharType="separate"/>')
    assert xml.count(begin_to_separate) == 1 and xml.count('<w:fldChar w:fldCharType="end"/>') == 1
    return xml.replace(begin_to_separate, '</w:r><w:r>').replace('<w:fldChar w:fldCharType="end"/>', '')


def without_simple_field(xml, instruction):
    start = f'<w:fldSimple w:instr={quoteattr(instruction)}>'
    assert xml.count(start) == 1 and xml.count('</w:fldSimple>') == 1
    return xml.replace(start, '').replace('</w:fldSimple>', '')


# Each type E2 removes, with an instruction of the shape Word writes; every instruction names something synthetic
# (a local path, the TEST-NET 192.0.2.1) that must not survive in the package.
DANGEROUS = {
    'INCLUDETEXT': r'INCLUDETEXT "c:\\synthetic\\secret-text.docx" \* MERGEFORMAT',
    'INCLUDEPICTURE': r'INCLUDEPICTURE "http://192.0.2.1/secret-picture.png" \* MERGEFORMATINET \d',
    'INCLUDE': r'INCLUDE "c:\\synthetic\\secret-old.doc"',
    'LINK': r'LINK Excel.Sheet.12 "c:\\synthetic\\secret-book.xlsx" "Sheet1!R1C1:R2C2" \a \f 4 \h',
    'DDE': r'DDE Excel "c:\\synthetic\\secret-dde.xls" "R1C1"',
    'DDEAUTO': r'DDEAUTO c:\\synthetic\\secret-cmd.exe "/k synthetic"',
    'IMPORT': r'IMPORT "c:\\synthetic\\secret-import.wmf"',
    'DATABASE': r'DATABASE \d "c:\\synthetic\\secret-data.mdb" \s "SELECT * FROM t"',
}
SECRET_MARKS = ('secret', '192.0.2.1', 'synthetic\\')


def document_xml(data):
    return parts_of(data)['word/document.xml'].decode('utf-8')


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


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
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

    def test_the_moved_names_are_the_same_objects_here(self):
        # E3: the code moved to docx_package (no Django), and document re-exports it, so callers keep their names
        for name in ('safe_package', 'soffice_convert', 'PackageRefused', 'PROFILE_SETTINGS', 'SOFFICE', 'WORK_PREFIX',
                     'MAX_PDF_BYTES', 'CONVERT_SECONDS', 'CONVERT_MEMORY_BYTES', 'MAX_PACKAGE_PARTS',
                     'MAX_PACKAGE_BYTES', '_convert_package', '_relationships'):
            with self.subTest(name=name):
                self.assertIs(getattr(document, name), getattr(docx_package, name))


# --- E1: the package's limits, the conversion's clean-up ------------------------------------------------------------

MIB = 1024 * 1024


def bomb(size, name='word/media/zeros.bin'):
    """PLAIN_PACKAGE plus one part of ``size`` zeros: a small zip that inflates hugely."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for entry, content in parts_of(PLAIN_PACKAGE).items():
            archive.writestr(entry, content)
        with archive.open(name, 'w', force_zip64=False) as handle:
            chunk, left = b'\x00' * MIB, size
            while left:
                handle.write(chunk[:min(left, MIB)])
                left -= min(left, MIB)
    return buffer.getvalue()


def lying(data, name, declared, *, crc_of=None):
    """``data`` with the part ``name``'s size header (its local header and its central directory entry) set to
    ``declared`` and, when given, its CRC to that of ``crc_of``: what a crafted zip can say about a part."""
    raw = bytearray(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        local = archive.getinfo(name).header_offset
    assert raw[local:local + 4] == b'PK\x03\x04'
    end = raw.rfind(b'PK\x05\x06')
    at, entry = int.from_bytes(raw[end + 16:end + 20], 'little'), None
    while raw[at:at + 4] == b'PK\x01\x02':
        length = int.from_bytes(raw[at + 28:at + 30], 'little')
        if raw[at + 46:at + 46 + length] == name.encode():
            entry = at
        at += 46 + sum(int.from_bytes(raw[at + k:at + k + 2], 'little') for k in (28, 30, 32))
    assert entry is not None
    struct.pack_into('<I', raw, local + 22, declared)
    struct.pack_into('<I', raw, entry + 24, declared)
    if crc_of is not None:
        struct.pack_into('<I', raw, local + 14, zlib.crc32(crc_of))
        struct.pack_into('<I', raw, entry + 16, zlib.crc32(crc_of))
    return bytes(raw)


class PackageLimitTests(SimpleTestCase):
    """E1: what a Word package may inflate to is checked from its zip directory before a part is read, and each part is
    read through a bounded reader that refuses a size header that lies."""

    def refused(self, data, said):
        with self.assertRaises(docx_package.PackageRefused) as caught:
            docx_package.safe_package(data)
        self.assertIn(said, str(caught.exception))

    def test_a_zip_bomb_is_refused_before_any_part_is_read(self):
        data = bomb(65 * MIB)
        self.assertLess(len(data), MIB)  # a small upload...
        with zipfile.ZipFile(io.BytesIO(data)) as archive:  # ...that says it inflates to 65 MiB of zeros
            self.assertEqual(archive.getinfo('word/media/zeros.bin').file_size, 65 * MIB)
        with mock.patch.object(docx_package, '_read_part', side_effect=AssertionError('a part was read')) as read:
            self.refused(data, 'too large once inflated')
        read.assert_not_called()

    def test_the_package_and_each_part_have_their_own_ceiling(self):
        self.assertEqual((docx_package.MAX_PACKAGE_BYTES, docx_package.MAX_PART_BYTES), (64 * MIB, 32 * MIB))
        with mock.patch.object(docx_package, 'MAX_PART_BYTES', 100):
            self.refused(PLAIN_PACKAGE, 'a part is too large once inflated')
        with mock.patch.object(docx_package, 'MAX_PACKAGE_BYTES', 100):
            self.refused(PLAIN_PACKAGE, 'its parts are too large once inflated')

    def test_a_part_that_inflates_more_than_a_hundred_times_its_size_is_refused(self):
        data = bomb(2 * MIB)  # 2 MiB of zeros deflates to about 2 KiB
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo('word/media/zeros.bin')
        self.assertGreater(info.file_size, 100 * info.compress_size)
        with mock.patch.object(docx_package, '_read_part', side_effect=AssertionError('a part was read')):
            self.refused(data, 'inflates more than 100 times its stored size')
        # a part too small to cost anything is not held to the ratio (printer settings, empty headers compress so)
        small = bomb(512 * 1024)
        self.assertEqual(parts_of(docx_package.safe_package(small))['word/media/zeros.bin'], b'\x00' * (512 * 1024))

    def test_a_lying_size_header_is_refused(self):
        real = parts_of(PLAIN_PACKAGE)['word/document.xml']
        short = lying(PLAIN_PACKAGE, 'word/document.xml', 100, crc_of=real[:100])  # says 100 bytes; holds more
        long = lying(PLAIN_PACKAGE, 'word/document.xml', len(real) + 50)  # says 50 bytes more than it holds
        for data in (short, long):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:  # the positive control: zipfile alone believes both
                self.assertIn(len(archive.read('word/document.xml')), (100, len(real)))
        self.refused(short, 'a part cannot be read')
        self.refused(long, 'a part is not the size its header says')

    def test_the_checks_have_a_time_budget(self):
        self.assertEqual((docx_package.PACKAGE_SECONDS, docx_package.SOFFICE_SECONDS, docx_package.CONVERT_SECONDS),
                         (10, 45, 60))
        with mock.patch.object(docx_package, 'PACKAGE_SECONDS', -1):  # checked between parts
            self.refused(PLAIN_PACKAGE, 'checking it took longer than')
        # and within one part, every few thousand elements
        many = (f'<?xml version="1.0"?><w:document {NAMESPACES}><w:body>'
                + paragraph(complex_field(' PAGE ', '1')) * 1000 + '</w:body></w:document>').encode('utf-8')
        docx_package._PartReader(many, time.monotonic() + 60).read()  # the control: in time, it is read
        with self.assertRaises(docx_package.PackageRefused) as caught:
            docx_package._PartReader(many, time.monotonic() - 1).read()
        self.assertIn('checking it took longer than', str(caught.exception))


def grandchild_runner(marker, note):
    """A runner for the bounded child that ignores SIGTERM and starts a grandchild in a session of its own (as soffice
    is started) that ignores SIGTERM too; it tells its parent the grandchild's group, as soffice_convert does, and never
    returns."""
    def run(data, work):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        process = subprocess.Popen([sys.executable, '-c', GRANDCHILD, marker, str(note)], start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        bounded.report_group(process.pid)
        while not Path(note).exists():
            time.sleep(0.01)
        time.sleep(120)
    return run


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
class ConversionCleanupTests(SimpleTestCase):
    """E1: the parent makes the work folder, passes it in and removes it after every run; LibreOffice's process group,
    reported by the child, is killed by the parent whatever happens."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        patcher = mock.patch.object(tempfile, 'tempdir', str(self.temp))
        patcher.start()
        self.addCleanup(patcher.stop)

    def leftovers(self):
        return sorted(path.name for path in self.temp.glob(f'{docx_package.WORK_PREFIX}*'))

    def test_the_work_folder_is_made_by_the_parent_and_gone_after_a_success_a_failure_and_a_timeout(self):
        record = self.temp / 'seen'

        def seeing(data, work):
            record.write_text(f'{work}\n{work.is_dir()}\n{oct(work.stat().st_mode & 0o777)}')
            return CONVERTED
        self.assertEqual(document.convert_docx(PLAIN_PACKAGE, runner=seeing), CONVERTED)
        work, existed, mode = record.read_text().split('\n')
        self.assertEqual((Path(work).parent, Path(work).name.startswith(docx_package.WORK_PREFIX), existed, mode),
                         (self.temp, True, 'True', '0o700'))
        self.assertEqual(self.leftovers(), [])
        for runner, seconds in ((failing_runner, 30), (no_pdf_runner, 30), (_sleeps, 1)):
            with self.subTest(runner=runner.__name__), self.assertRaises(document.DocumentError):
                document.convert_docx(PLAIN_PACKAGE, runner=runner, seconds=seconds)
            self.assertEqual(self.leftovers(), [])
        with self.assertRaises(document.DocumentError):  # refused before any runner runs
            document.convert_docx(b'PK\x03\x04 not a zip', runner=fake_runner)
        self.assertEqual(self.leftovers(), [])

    def test_soffice_works_in_the_folder_its_parent_made_and_tells_the_parent_its_group(self):
        folder = Path(tempfile.mkdtemp(prefix=docx_package.WORK_PREFIX))
        calls, seen = [], {}

        class Process:
            pid, returncode = 4242, 0

            def __init__(self, command, **kwargs):
                seen.update(kwargs)
                (Path(command[command.index('--outdir') + 1]) / 'document.pdf').write_bytes(CONVERTED)

            def wait(self, timeout=None):
                calls.append(('wait', timeout))
                return 0
        with mock.patch('subprocess.Popen', Process), \
                mock.patch('os.killpg', side_effect=lambda pgid, number: calls.append(('killpg', pgid, number))), \
                mock.patch.object(bounded, 'report_group', side_effect=lambda pgid: calls.append(('report', pgid))), \
                mock.patch.object(bounded, 'group_ended', side_effect=lambda pgid: calls.append(('ended', pgid))):
            self.assertEqual(docx_package.soffice_convert(PLAIN_PACKAGE, folder), CONVERTED)
        self.assertEqual(calls, [('report', 4242), ('wait', 45), ('killpg', 4242, signal.SIGKILL), ('ended', 4242),
                                 ('wait', None)])
        self.assertEqual(Path(seen['cwd']), folder)
        self.assertTrue(folder.is_dir())  # the parent removes it, not soffice_convert

    def test_a_runner_that_ignores_sigterm_and_starts_a_grandchild_in_its_own_session_leaves_nothing(self):
        marker, note = f'cpt-lane5-grandchild-{uuid.uuid4().hex}', self.temp / 'grandchild'
        try:
            with self.assertRaises(document.DocumentError) as caught:
                document.convert_docx(PLAIN_PACKAGE, runner=grandchild_runner(marker, note), seconds=8)
            self.assertIn('time', caught.exception.detail)
            pid, session = map(int, note.read_text().split())  # the grandchild ran, in a session of its own
            self.assertEqual(pid, session)
            self.assertEqual(marked(marker), [])
            self.assertEqual(self.leftovers(), [])
        finally:
            kill_marked(marker)


# --- E2: field instructions and embedded content ------------------------------------------------------------------

class FieldInstructionTests(SimpleTestCase):
    """E2: the instruction of every field of a removed type goes, in both forms and in every part that holds one; what
    the reader sees stays; nothing else of the part changes, byte for byte."""

    def test_a_complex_field_of_each_removed_type_loses_its_instruction_and_keeps_its_result(self):
        for kind, instruction in DANGEROUS.items():
            with self.subTest(kind=kind):
                visible = f'VISIBLE {kind} RESULT'
                data = word_package(TEXT + paragraph(complex_field(instruction, visible)))
                package, removed = docx_package._safe_package(data)
                self.assertEqual(document_xml(package), without_complex_field(document_xml(data), instruction))
                self.assertIn(f'<w:r><w:t>{visible}</w:t></w:r>', document_xml(package))
                for mark in SECRET_MARKS:
                    self.assertNotIn(mark, document_xml(package))
                self.assertEqual(removed, {'fields': 1, 'objects': 0, 'controls': 0, 'chunks': 0})

    def test_a_simple_field_of_each_removed_type_loses_its_instruction_and_keeps_its_runs(self):
        for kind, instruction in DANGEROUS.items():
            with self.subTest(kind=kind):
                visible = f'VISIBLE {kind} RESULT'
                data = word_package(paragraph(simple_field(instruction, visible)))
                package, removed = docx_package._safe_package(data)
                self.assertEqual(document_xml(package), without_simple_field(document_xml(data), instruction))
                self.assertIn(f'<w:p><w:r><w:t>{visible}</w:t></w:r></w:p>', document_xml(package))
                self.assertEqual(removed['fields'], 1)

    def test_fields_are_removed_in_every_part_that_holds_them(self):
        field = paragraph(complex_field(DANGEROUS['INCLUDETEXT'], 'VISIBLE C')) + paragraph(
            simple_field(DANGEROUS['INCLUDEPICTURE'], 'VISIBLE S'))
        data = full_package(field, header=field, footer=field, footnote=field, endnote=field, comment=field,
                            glossary=field)
        package, removed = docx_package._safe_package(data)
        safe, original = parts_of(package), parts_of(data)
        for part in ('word/document.xml', 'word/header1.xml', 'word/footer1.xml', 'word/footnotes.xml',
                     'word/endnotes.xml', 'word/comments.xml', 'word/glossary/document.xml'):
            with self.subTest(part=part):
                text = safe[part].decode('utf-8')
                self.assertEqual(text, without_simple_field(without_complex_field(
                    original[part].decode('utf-8'), DANGEROUS['INCLUDETEXT']), DANGEROUS['INCLUDEPICTURE']))
                self.assertIn('VISIBLE C', text)
                self.assertIn('VISIBLE S', text)
        self.assertEqual(removed['fields'], 14)
        for part in ('[Content_Types].xml', '_rels/.rels', 'word/_rels/document.xml.rels'):  # nothing else changes
            self.assertEqual(safe[part], original[part], part)

    def test_the_type_is_read_as_libreoffice_would_read_it(self):
        rpr = '<w:rPr><w:rFonts w:ascii="Arial"/></w:rPr>'
        cases = {
            'lower case': complex_field(' includetext "c:\\\\synthetic\\\\secret.docx" '),
            'mixed case, no leading space': complex_field('IncludePicture "http://192.0.2.1/secret.png"'),
            'a leading backslash': complex_field(' \\INCLUDETEXT "c:\\\\synthetic\\\\secret.docx" '),
            'a quoted type': complex_field(' "INCLUDETEXT" "c:\\\\synthetic\\\\secret.docx" '),
            'a tab and spaces first': complex_field('\t  DDEAUTO c:\\\\synthetic\\\\secret.exe '),
            'deleted instruction text': complex_field(' LINK Word.Document "c:\\\\secret.docx" ', text='delInstrText'),
            'plain text in the instruction': complex_field(' INCLUDETEXT "c:\\\\secret.docx" ', text='t'),
            'split across runs': (
                '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                f'<w:r>{rpr}<w:instrText xml:space="preserve"> INCL</w:instrText></w:r><w:proofErr w:type="spellStart"/>'
                f'<w:r w:rsidR="00A1"><w:instrText>UDE</w:instrText></w:r><w:r>{rpr}<w:instrText xml:space="preserve">'
                'TEXT "c:\\\\secret.docx" </w:instrText></w:r>'
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>VISIBLE RESULT</w:t></w:r>'
                '<w:r><w:fldChar w:fldCharType="end"/></w:r>'),
        }
        for label, field in cases.items():
            with self.subTest(label):
                package, removed = docx_package._safe_package(word_package(paragraph(field)))
                xml = document_xml(package)
                self.assertEqual(removed['fields'], 1)
                self.assertNotIn('secret', xml)
                self.assertNotIn('fldChar', xml)
                self.assertIn('VISIBLE RESULT', xml)

    def test_a_field_whose_type_its_text_does_not_spell_is_removed(self):
        nested_first = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                        f'{complex_field(" QUOTE " + chr(34) + "INCLUDETEXT" + chr(34) + " ", "INCLUDETEXT")}'
                        '<w:r><w:instrText xml:space="preserve"> "c:\\\\synthetic\\\\secret.docx" </w:instrText></w:r>'
                        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>VISIBLE RESULT</w:t></w:r>'
                        '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        symbol_first = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:sym w:font="Arial" w:char="0049"/>'
                        '<w:instrText>NCLUDETEXT "c:\\\\synthetic\\\\secret.docx" </w:instrText></w:r>'
                        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>VISIBLE RESULT</w:t></w:r>'
                        '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        for label, field in (('a nested field makes the type', nested_first), ('a symbol starts it', symbol_first)):
            with self.subTest(label):
                xml = document_xml(docx_package.safe_package(word_package(paragraph(field))))
                self.assertNotIn('secret', xml)
                self.assertEqual(xml.count('VISIBLE RESULT'), 1)
                self.assertNotIn('fldChar', xml)

    def test_nesting_removes_exactly_the_dangerous_instruction(self):
        inner = complex_field(DANGEROUS['INCLUDETEXT'], 'INNER RESULT')
        harmless_outer = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                          '<w:r><w:instrText xml:space="preserve"> IF 1 = 1 "</w:instrText></w:r>'
                          f'{inner}<w:r><w:instrText xml:space="preserve">" "" </w:instrText></w:r>'
                          '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>OUTER RESULT</w:t></w:r>'
                          '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        data = word_package(paragraph(harmless_outer))
        xml = document_xml(docx_package.safe_package(data))
        inner_marks = ('<w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve">'
                       f'{escape(DANGEROUS["INCLUDETEXT"])}</w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/>',
                       '<w:fldChar w:fldCharType="end"/></w:r><w:r><w:instrText xml:space="preserve">" ""')
        expected = document_xml(data)
        for mark, left in zip(inner_marks, ('</w:r><w:r>', '</w:r><w:r><w:instrText xml:space="preserve">" ""')):
            self.assertEqual(expected.count(mark), 1)
            expected = expected.replace(mark, left)
        self.assertEqual(xml, expected)
        self.assertIn(' IF 1 = 1 "', xml)  # the harmless field keeps its instruction
        harmful_outer = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                         '<w:r><w:instrText xml:space="preserve"> INCLUDETEXT "</w:instrText></w:r>'
                         f'{complex_field(" FILENAME ", "secret-name.docx")}'
                         '<w:r><w:instrText xml:space="preserve">" </w:instrText></w:r>'
                         '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>OUTER RESULT</w:t></w:r>'
                         '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        xml = document_xml(docx_package.safe_package(word_package(paragraph(harmful_outer))))
        self.assertNotIn('INCLUDETEXT', xml)
        self.assertNotIn('FILENAME', xml)
        self.assertNotIn('secret-name', xml)  # the nested field was part of the instruction: it goes with it
        self.assertIn('<w:t>OUTER RESULT</w:t>', xml)

    def test_an_instruction_over_two_paragraphs_goes_and_both_paragraphs_keep_their_properties(self):
        first, second = '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>', '<w:pPr><w:jc w:val="center"/></w:pPr>'
        body = (f'<w:p>{first}<w:r><w:t>BEFORE</w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r><w:instrText xml:space="preserve"> INCLUDETEXT "c:\\\\synthetic\\\\</w:instrText></w:r></w:p>'
                f'<w:p>{second}<w:r><w:rPr><w:b/></w:rPr><w:instrText>secret.docx" </w:instrText></w:r>'
                '<w:r><w:rPr><w:i/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>VISIBLE RESULT</w:t>'
                '</w:r><w:r><w:fldChar w:fldCharType="end"/></w:r><w:r><w:t>AFTER</w:t></w:r></w:p>')
        xml = document_xml(docx_package.safe_package(word_package(body)))
        self.assertIn(f'<w:p>{first}<w:r><w:t>BEFORE</w:t></w:r><w:r></w:r></w:p><w:p>{second}<w:r><w:rPr><w:i/>'
                      '</w:rPr></w:r><w:r><w:t>VISIBLE RESULT</w:t></w:r><w:r></w:r><w:r><w:t>AFTER</w:t></w:r></w:p>',
                      xml)
        self.assertNotIn('secret', xml)

    def test_a_field_with_no_result_goes_whole_and_one_never_closed_is_refused(self):
        no_result = ('<w:r><w:t>KEPT</w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText>'
                     ' DDEAUTO c:\\\\synthetic\\\\secret.exe </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/>'
                     '</w:r>')
        xml = document_xml(docx_package.safe_package(word_package(paragraph(no_result))))
        self.assertIn('<w:p><w:r><w:t>KEPT</w:t></w:r><w:r></w:r><w:r></w:r></w:p>', xml)
        unclosed = '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> INCLUDETEXT x </w:instrText></w:r>'
        with self.assertRaises(docx_package.PackageRefused) as caught:
            docx_package.safe_package(word_package(paragraph(unclosed)))
        self.assertIn('not closed', str(caught.exception))
        harmless = '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r>'
        data = word_package(paragraph(harmless))
        self.assertEqual(docx_package.safe_package(data), legacy_safe_package(data))  # not ours to change

    def test_any_prefix_and_the_strict_namespace_are_read(self):
        ns0 = prefixed_package(paragraph(complex_field(DANGEROUS['LINK'])), 'ns0')
        strict = word_package(paragraph(simple_field(DANGEROUS['DATABASE'])), namespaces=f'xmlns:w="{STRICT_WORD_NS}"')
        for label, data in (('ns0', ns0), ('strict', strict)):
            with self.subTest(label):
                xml = document_xml(docx_package.safe_package(data))
                self.assertNotIn('secret', xml)
                self.assertIn('VISIBLE RESULT', xml)

    def test_field_markup_in_a_part_of_any_name_or_type_is_removed(self):
        # LibreOffice could be pointed at a header by its relationship id whatever the part is called or typed as
        evil = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<w:hdr {NAMESPACES}>{paragraph(simple_field(DANGEROUS["INCLUDETEXT"]))}</w:hdr>')
        data = word_package(TEXT, [relationship('rIdHeader', 'image', 'media/picture.png')],
                            parts=[('word/media/picture.png', evil)])
        safe = parts_of(docx_package.safe_package(data))['word/media/picture.png'].decode('utf-8')
        self.assertNotIn('secret', safe)
        self.assertIn('VISIBLE RESULT', safe)

    def test_a_part_that_needs_a_change_and_is_not_utf8_is_refused_and_one_that_does_not_passes(self):
        def header(inner):
            return word_package(TEXT, [relationship('rIdHeader', 'header', 'header1.xml')], parts=[
                ('word/header1.xml', ('<?xml version="1.0" encoding="UTF-16"?>\n'
                                      f'<w:hdr {NAMESPACES}>{inner}</w:hdr>').encode('utf-16'))],
                overrides=override('word/header1.xml', STORY.format('header')))
        harmless = header(paragraph(complex_field(' PAGE ', '1')))
        self.assertEqual(docx_package.safe_package(harmless), legacy_safe_package(harmless))
        with self.assertRaises(docx_package.PackageRefused) as caught:
            docx_package.safe_package(header(paragraph(complex_field(DANGEROUS['INCLUDETEXT']))))
        self.assertIn('not UTF-8', str(caught.exception))

    def test_a_dtd_in_a_document_part_is_refused(self):
        dtd = '<!DOCTYPE w:document [<!ENTITY e SYSTEM "file:///synthetic/secret">]>'
        cases = {
            'the main document, with nothing else to remove': zipped([
                (name, content.replace(b'?>\n<w:document', b'?>\n' + dtd.encode() + b'<w:document'))
                for name, content in parts_of(PLAIN_PACKAGE).items()]),
            'a header with a field': word_package(TEXT, [relationship('rIdHeader', 'header', 'header1.xml')], parts=[
                ('word/header1.xml', f'<?xml version="1.0"?>{dtd}<w:hdr {NAMESPACES}>'
                                     f'{paragraph(complex_field(" PAGE "))}</w:hdr>')]),
            'styles': word_package(TEXT, parts=[('word/styles.xml', f'<?xml version="1.0"?>{dtd}<w:styles '
                                                                    f'{NAMESPACES}/>')]),
        }
        for label, data in cases.items():
            with self.subTest(label):
                with self.assertRaises(docx_package.PackageRefused) as caught:
                    docx_package.safe_package(data)
                self.assertIn('declares a DTD', str(caught.exception))
        # an SVG picture may declare one: it is a picture, not a document part
        svg = ('<?xml version="1.0"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
               '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg xmlns="http://www.w3.org/2000/svg"/>')
        data = word_package(TEXT, [relationship('rIdSvg', 'image', 'media/image1.svg')],
                            parts=[('word/media/image1.svg', svg)], overrides=override('word/media/image1.svg',
                                                                                       'image/svg+xml'))
        self.assertEqual(docx_package.safe_package(data), legacy_safe_package(data))

    def test_a_document_part_that_is_not_well_formed_is_refused_and_a_picture_is_not_read_as_xml(self):
        broken = word_package(paragraph(complex_field(DANGEROUS['INCLUDETEXT'])) + '<w:p><w:r></w:p>')
        with self.assertRaises(docx_package.PackageRefused) as caught:
            docx_package.safe_package(broken)
        self.assertIn('not well-formed XML', str(caught.exception))
        picture = PNG + b' <w:fldChar w:fldCharType="begin"/> <object> more bytes'
        data = word_package(TEXT, [relationship('rIdPic', 'image', 'media/image1.png')],
                            parts=[('word/media/image1.png', picture)])
        self.assertEqual(docx_package.safe_package(data), legacy_safe_package(data))

    def test_what_was_removed_is_logged_as_counts_only(self):
        data = full_package(paragraph(complex_field(DANGEROUS['INCLUDETEXT'], 'VISIBLE C')) + OLE_OBJECT_RUN_PARAGRAPH,
                            document_rels=OLE_RELS, parts=OLE_PARTS, defaults=OLE_DEFAULTS)
        with override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False), \
                self.assertLogs('studio.fable.docx_package', 'INFO') as logged:
            document.convert_docx(data, runner=fake_runner)
        line = '\n'.join(logged.output)
        self.assertIn('1 field instructions, 1 embedded objects, 0 controls and 0 imported documents removed', line)
        for content in ('secret', 'VISIBLE', 'word/', 'oleObject', 'synthetic'):
            self.assertNotIn(content, line)


# --- embedded objects, controls and imported documents ----------------------------------------------------------

OLE_SHAPE = ('<v:shapetype id="_x0000_t75" coordsize="21600,21600" o:spt="75" path="m@4@5l@4@11@9@11@9@5xe">'
             '<v:stroke joinstyle="miter"/></v:shapetype>'
             '<v:shape id="_x0000_i1025" type="#_x0000_t75" style="width:72pt;height:36pt" o:ole="">'
             '<v:imagedata r:id="rIdPreview" o:title=""/></v:shape>')
OLE_OBJECT = ('<w:object w:dxaOrig="1440" w:dyaOrig="720">' + OLE_SHAPE +
              '<o:OLEObject Type="Embed" ProgID="Excel.Sheet.12" ShapeID="_x0000_i1025" DrawAspect="Content" '
              'ObjectID="_1700000001" r:id="rIdOle"/></w:object>')
OLE_OBJECT_RUN_PARAGRAPH = paragraph(f'<w:r>{OLE_OBJECT}</w:r>')
OLE_RELS = (relationship('rIdPreview', 'image', 'media/image1.emf'),
            relationship('rIdOle', 'package', 'embeddings/Microsoft_Excel_Worksheet.xlsx'))
OLE_PARTS = (('word/media/image1.emf', b'\x01\x00\x00\x00 synthetic preview'),
             ('word/embeddings/Microsoft_Excel_Worksheet.xlsx', b'PK\x03\x04 synthetic embedded workbook secret'))
OLE_DEFAULTS = ('<Default Extension="emf" ContentType="image/x-emf"/><Default Extension="xlsx" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>'
                '<Default Extension="bin" ContentType="application/vnd.ms-office.activeX"/>'
                '<Default Extension="mht" ContentType="message/rfc822"/>')


class EmbeddedContentTests(SimpleTestCase):
    """E2: w:object (its preview picture kept), w:control and w:altChunk are removed, with the parts only they named and
    those parts' own relationships."""

    def safe(self, body, rels=(), parts=()):
        data = full_package(body, document_rels=rels, parts=parts, defaults=OLE_DEFAULTS)
        package, removed = docx_package._safe_package(data)
        return data, parts_of(package), removed

    def test_an_object_becomes_its_preview_picture_and_its_embedding_goes(self):
        data, safe, removed = self.safe(TEXT + OLE_OBJECT_RUN_PARAGRAPH, OLE_RELS, OLE_PARTS)
        original = parts_of(data)['word/document.xml'].decode('utf-8')
        ole = ('<o:OLEObject Type="Embed" ProgID="Excel.Sheet.12" ShapeID="_x0000_i1025" DrawAspect="Content" '
               'ObjectID="_1700000001" r:id="rIdOle"/>')
        expected = original.replace('<w:object w:dxaOrig="1440" w:dyaOrig="720">', '<w:pict>').replace(
            ole + '</w:object>', '</w:pict>')
        self.assertEqual(safe['word/document.xml'].decode('utf-8'), expected)
        self.assertNotIn('word/embeddings/Microsoft_Excel_Worksheet.xlsx', safe)
        rels = safe['word/_rels/document.xml.rels'].decode('utf-8')
        self.assertNotIn('rIdOle', rels)
        self.assertIn(relationship('rIdPreview', 'image', 'media/image1.emf'), rels)
        self.assertEqual(safe['word/media/image1.emf'], OLE_PARTS[0][1])  # the preview picture stays
        self.assertEqual(removed['objects'], 1)
        for b in safe.values():
            self.assertNotIn(b'secret', b)

    def test_an_object_with_a_drawing_keeps_the_drawing_in_its_place_and_one_with_no_preview_goes(self):
        drawing_object = (f'<w:object>{EMBEDDED_DRAWING}<w:objectEmbed w:drawAspect="content" r:id="rIdOle" '
                          'w:progId="Excel.Sheet.12" w:shapeId="1" w:fieldCodes=""/></w:object>')
        data, safe, removed = self.safe(paragraph(f'<w:r>{drawing_object}</w:r>'),
                                        (relationship('rIdPic', 'image', 'media/image1.png'), OLE_RELS[1]),
                                        (('word/media/image1.png', PNG), OLE_PARTS[1]))
        self.assertIn(f'<w:r>{EMBEDDED_DRAWING}</w:r>', safe['word/document.xml'].decode('utf-8'))
        self.assertNotIn('objectEmbed', safe['word/document.xml'].decode('utf-8'))
        self.assertNotIn('word/embeddings/Microsoft_Excel_Worksheet.xlsx', safe)
        self.assertEqual(safe['word/media/image1.png'], PNG)
        bare = '<w:object><o:OLEObject Type="Embed" ProgID="Package" r:id="rIdOle"/></w:object>'
        data, safe, removed = self.safe(paragraph(f'<w:r><w:t>KEPT</w:t>{bare}</w:r>'), OLE_RELS[1:], OLE_PARTS[1:])
        self.assertIn('<w:p><w:r><w:t>KEPT</w:t></w:r></w:p>', safe['word/document.xml'].decode('utf-8'))
        self.assertNotIn('word/embeddings/Microsoft_Excel_Worksheet.xlsx', safe)

    def test_a_control_goes_with_its_part_and_what_only_that_part_named(self):
        control = ('<w:pict>' + OLE_SHAPE + '<w:control r:id="rIdAx" w:name="CheckBox1" w:shapeid="_x0000_i1025"/>'
                   '</w:pict>')
        axml = ('<?xml version="1.0" encoding="UTF-8"?><ax:ocx xmlns:ax="http://schemas.microsoft.com/office/2006/'
                f'activeX" xmlns:r="{REL}" ax:classid="{{8BD21D40-EC42-11CE-9E0D-00AA006002F3}}" ax:persistence='
                '"persistStorage" r:id="rIdBin"/>')
        data, safe, removed = self.safe(
            paragraph(f'<w:r>{control}</w:r>'),
            (relationship('rIdPreview', 'image', 'media/image1.emf'), relationship('rIdAx', 'control',
                                                                                    'activeX/activeX1.xml')),
            (OLE_PARTS[0], ('word/activeX/activeX1.xml', axml),
             ('word/activeX/_rels/activeX1.xml.rels', relationships(relationship(
                 'rIdBin', 'activeXControlBinary', 'activeX1.bin'))),
             ('word/activeX/activeX1.bin', b'\xd0\xcf\x11\xe0 synthetic control secret')))
        xml = safe['word/document.xml'].decode('utf-8')
        self.assertIn('<w:pict>' + OLE_SHAPE + '</w:pict>', xml)
        for gone in ('word/activeX/activeX1.xml', 'word/activeX/_rels/activeX1.xml.rels', 'word/activeX/activeX1.bin'):
            self.assertNotIn(gone, safe)
        self.assertNotIn('rIdAx', safe['word/_rels/document.xml.rels'].decode('utf-8'))
        self.assertEqual(removed['controls'], 1)

    def test_an_imported_document_goes_with_its_part(self):
        chunk = (b'MIME-Version: 1.0\r\nContent-Type: text/html\r\n\r\n<html><body><img src="http://192.0.2.1/'
                 b'secret.png"><object data="file:///synthetic/secret"></object></body></html>')
        data, safe, removed = self.safe(TEXT + '<w:altChunk r:id="rIdChunk"/>' + TEXT,
                                        (relationship('rIdChunk', 'aFChunk', 'afchunk.mht'),),
                                        (('word/afchunk.mht', chunk),))
        self.assertNotIn('altChunk', safe['word/document.xml'].decode('utf-8'))
        self.assertEqual(safe['word/document.xml'].decode('utf-8').count('SYNTHETIC NOTE'), 2)
        self.assertNotIn('word/afchunk.mht', safe)
        self.assertNotIn('rIdChunk', safe['word/_rels/document.xml.rels'].decode('utf-8'))
        self.assertEqual(removed['chunks'], 1)

    def test_a_relationship_kept_content_still_names_is_kept(self):
        shared = paragraph(f'<w:r>{OLE_OBJECT}</w:r>') + paragraph('<w:hyperlink r:id="rIdOle"><w:r><w:t>KEPT LINK'
                                                                   '</w:t></w:r></w:hyperlink>')
        data, safe, removed = self.safe(shared, OLE_RELS, OLE_PARTS)
        self.assertIn('rIdOle', safe['word/_rels/document.xml.rels'].decode('utf-8'))
        self.assertIn('word/embeddings/Microsoft_Excel_Worksheet.xlsx', safe)

    def test_an_object_that_declares_namespaces_of_its_own_keeps_them_or_is_refused(self):
        own = (f'<w:object xmlns:v="urn:schemas-microsoft-com:vml" xmlns:q="{REL}"><v:shape id="s" style="width:1pt">'
               '<v:imagedata q:id="rIdPreview"/></v:shape><o:OLEObject Type="Embed" ProgID="Package" q:id="rIdOle"/>'
               '</w:object>')
        data, safe, removed = self.safe(paragraph(f'<w:r>{own}</w:r>'), OLE_RELS, OLE_PARTS)
        self.assertIn(f'<w:pict xmlns:v="urn:schemas-microsoft-com:vml" xmlns:q="{REL}"><v:shape',
                      safe['word/document.xml'].decode('utf-8'))
        self.assertNotIn('word/embeddings/Microsoft_Excel_Worksheet.xlsx', safe)
        unwrap = f'<w:object xmlns:q="{REL}">{EMBEDDED_DRAWING}<w:objectEmbed q:id="rIdOle"/></w:object>'
        with self.assertRaises(docx_package.PackageRefused):
            self.safe(paragraph(f'<w:r>{unwrap}</w:r>'), OLE_RELS, OLE_PARTS)


# --- E2: a Word file with nothing to remove gives exactly today's package -----------------------------------------

def _identity_corpus():
    """Packages with none of the features E2 removes - but with every neighbour of them a Word file holds: fields of
    harmless types in both forms, split, nested and over paragraphs; pictures (VML, DrawingML, markup-compatibility
    choices); headers, footers, notes, comments and a glossary; External relationships (removed before release 1 too);
    the strict namespace, a default namespace and unusual prefixes; mc:Ignorable; a byte order mark, CRLF, stored parts,
    CDATA and comments that spell field markup, an SVG with a DOCTYPE. (label, bytes)."""
    page = complex_field(' PAGE ', '1')
    rsid_page = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r w:rsidR="00B2"><w:instrText>PA</w:instrText>'
                 '</w:r><w:r><w:rPr><w:b/></w:rPr><w:instrText xml:space="preserve">GE \\* MERGEFORMAT </w:instrText>'
                 '</w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>2</w:t></w:r>'
                 '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    nested_if = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> IF '
                 '</w:instrText></w:r>' + complex_field(' MERGEFIELD Kind ', 'A') +
                 '<w:r><w:instrText xml:space="preserve"> = "A" "yes" "no" </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>yes</w:t></w:r>'
                 '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    form_text = ('<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Text1"/><w:enabled/>'
                 '<w:calcOnExit w:val="0"/><w:textInput/></w:ffData></w:fldChar></w:r>'
                 '<w:r><w:instrText xml:space="preserve"> FORMTEXT </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>typed</w:t></w:r>'
                 '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    deleted_page = ('<w:del w:id="9" w:author="Synthetic" w:date="2026-11-24T00:00:00Z"><w:r><w:fldChar '
                    'w:fldCharType="begin"/></w:r><w:r><w:delInstrText xml:space="preserve"> PAGE </w:delInstrText>'
                    '</w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:delText>4</w:delText></w:r><w:r>'
                    '<w:fldChar w:fldCharType="end"/></w:r></w:del>')
    toc = ('<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r>'
           '<w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r><w:r><w:fldChar '
           'w:fldCharType="separate"/></w:r><w:r><w:t>Heading one</w:t></w:r></w:p><w:p><w:pPr><w:pStyle '
           'w:val="TOC1"/></w:pPr><w:r><w:t>Heading two</w:t></w:r></w:p><w:p><w:r><w:fldChar w:fldCharType="end"/>'
           '</w:r></w:p>')
    look_alikes = [complex_field(' HYPERLINK "http://example.test/" ', 'a link'), complex_field(' QUOTE "INCLUDETEXT" ',
                   'INCLUDETEXT'), complex_field(' MERGEFIELD Include ', 'Include'), complex_field(' REF LINK_1 \\h ',
                   'Table 1'), complex_field(' LISTNUM LegalDefault ', '1.'), complex_field(' AUTOTEXT Database ', 'x'),
                   simple_field(' DATE \\@ "yyyy-MM-dd" ', '2026-11-24'), simple_field(' AUTHOR ', 'Synthetic'),
                   simple_field(' NUMPAGES ', '3'), simple_field(' SEQ Table \\* ARABIC ', '1')]
    vml_picture = ('<w:r><w:pict><v:shapetype id="_x0000_t75" coordsize="21600,21600" o:spt="75" '
                   'path="m@4@5l@4@11@9@11@9@5xe"/><v:shape id="Picture1" type="#_x0000_t75" style="width:40pt;'
                   'height:40pt"><v:imagedata r:id="rIdPic" o:title=""/></v:shape></w:pict></w:r>')
    alternate = (f'<w:r><mc:AlternateContent><mc:Choice Requires="wps">{EMBEDDED_DRAWING}</mc:Choice><mc:Fallback>'
                 '<w:pict><v:rect style="width:10pt;height:10pt"/></w:pict></mc:Fallback></mc:AlternateContent></w:r>')
    words = paragraph('<w:r><w:t>the object of control is &lt;w:object&gt; and &lt;w:fldChar&gt;</w:t></w:r>')
    picture_rels = (relationship('rIdPic', 'image', 'media/image1.png'),)
    picture_parts = (('word/media/image1.png', PNG),)
    external = (relationship('rIdLink', 'hyperlink', 'https://example.test/', 'External'),
                relationship('rIdImg', 'image', 'http://192.0.2.1/x.png', 'External'))
    settings = ('word/settings.xml', f'<w:settings {NAMESPACES}><w:attachedTemplate r:id="rIdT"/></w:settings>')
    settings_rels = ('word/_rels/settings.xml.rels', relationships(
        relationship('rIdT', 'attachedTemplate', 'file:///synthetic/template.dotx', 'External')))
    custom = ('customXml/item1.xml', '<?xml version="1.0"?><data><![CDATA[<w:fldChar w:fldCharType="begin"/>'
              '<w:object>]]><!-- <w:fldSimple w:instr="INCLUDETEXT x"/> --><control/></data>')
    svg = ('word/media/image2.svg', '<?xml version="1.0"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
           '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg xmlns="http://www.w3.org/2000/svg"/>')
    svg_type = '<Default Extension="svg" ContentType="image/svg+xml"/>'
    corpus = [('plain', PLAIN_PACKAGE), ('installer', _installer_docx()), ('self-test', _self_test_docx())]
    for number, field in enumerate([page, rsid_page, nested_if, form_text, deleted_page, *look_alikes]):
        corpus.append((f'field {number}', word_package(TEXT + paragraph(field))))
    corpus.append(('toc', word_package(toc + TEXT)))
    corpus.append(('every story', full_package(
        paragraph(page, '<w:r><w:t> of </w:t></w:r>', simple_field(' NUMPAGES ', '3')) + toc,
        header=paragraph(rsid_page), footer=paragraph(page), footnote=paragraph(nested_if), endnote=paragraph(
            form_text), comment=paragraph(deleted_page), glossary=paragraph(look_alikes[0]))))
    corpus.append(('pictures', full_package(TEXT + paragraph(vml_picture) + paragraph(alternate) + words,
                                            document_rels=picture_rels, parts=picture_parts)))
    corpus.append(('external links', full_package(TEXT + LINKED_PICTURE + paragraph(page), document_rels=external,
                                                  parts=(settings, settings_rels))))
    corpus.append(('strict', word_package(paragraph(page) + paragraph(simple_field(' DATE ', 'today')),
                                          namespaces=f'xmlns:w="{STRICT_WORD_NS}"')))
    corpus.append(('ns0', prefixed_package(paragraph(page, simple_field(' PAGE ')), 'ns0')))
    corpus.append(('default namespace', zipped([
        ('[Content_Types].xml', content_types(override('word/document.xml', WORD_MAIN))),
        ('_rels/.rels', relationships(relationship('rId1', 'officeDocument', 'word/document.xml'))),
        ('word/document.xml', f'<document xmlns="{WORD_NS}" xmlns:w="{WORD_NS}"><body>'
                              + paragraph(page).replace('w:', '').replace('fldCharType', 'w:fldCharType')
                              + '</body></document>')])))
    corpus.append(('bom, crlf, stored', full_package(
        TEXT + paragraph(page), header=paragraph(page).replace('</w:r>', '</w:r>\r\n'), stored=(
            'word/header1.xml', 'word/document.xml', '[Content_Types].xml'))))
    corpus.append(('cdata, comments, svg', full_package(TEXT + paragraph(page), parts=(custom, svg),
                                                        defaults=svg_type)))
    features = [page, rsid_page, nested_if, form_text, deleted_page, vml_picture, alternate, *look_alikes]
    rng = random.Random(20261124)
    for number in range(24):
        chosen = rng.sample(features, rng.randint(1, 5))
        stories = {story: paragraph(*rng.sample(features, rng.randint(0, 2))) if rng.random() < 0.6 else TEXT
                   for story in ('header', 'footer', 'footnote', 'endnote', 'comment', 'glossary')}
        corpus.append((f'mixed {number}', full_package(
            TEXT + ''.join(paragraph(feature) for feature in chosen) + (toc if rng.random() < 0.3 else ''),
            document_rels=picture_rels + (external if rng.random() < 0.4 else ()), parts=picture_parts,
            stored=('word/document.xml',) if rng.random() < 0.3 else (), **stories)))
    with_bom = full_package(TEXT + paragraph(page))
    corpus.append(('utf-8 bom', zipped([(name, (b'\xef\xbb\xbf' + body) if name == 'word/document.xml' else body)
                                        for name, body in parts_of(with_bom).items()])))
    return corpus


def _self_test_docx():
    from studio import converter_server
    return converter_server.self_test_docx()


class ByteIdentityTests(SimpleTestCase):
    """E2 and the coding path (spec 2.4): for a Word file with none of the removed features, the package is
    byte-identical to the one the code before release 1 made (legacy_safe_package, below)."""

    def test_a_package_with_nothing_to_remove_is_byte_identical_to_the_one_made_before(self):
        reads = []
        real = docx_package._PartReader.read

        def counted(reader):
            reads.append(reader)
            return real(reader)
        corpus = _identity_corpus()
        self.assertGreaterEqual(len(corpus), 50)
        with mock.patch.object(docx_package._PartReader, 'read', counted):
            for label, data in corpus:
                with self.subTest(label):
                    package, removed = docx_package._safe_package(data)
                    self.assertEqual(package, legacy_safe_package(data))
                    self.assertEqual(removed, {'fields': 0, 'objects': 0, 'controls': 0, 'chunks': 0})
        # not vacuous: the parts holding field markup were read and found to need nothing
        self.assertGreaterEqual(len(reads), 80)

    def test_a_part_with_nothing_to_remove_passes_through_beside_one_that_changes(self):
        data = full_package(paragraph(complex_field(DANGEROUS['INCLUDETEXT'])),
                            header=paragraph(complex_field(' PAGE ', '1')))
        safe, original = parts_of(docx_package.safe_package(data)), parts_of(data)
        self.assertNotEqual(safe['word/document.xml'], original['word/document.xml'])
        for name in original:
            if name != 'word/document.xml':
                self.assertEqual(safe[name], original[name], name)


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
        with mock.patch.object(docx_package, 'MAX_PACKAGE_PARTS', 2):
            refused(PLAIN_PACKAGE, 'more than 2 parts')
        with mock.patch.object(docx_package, 'MAX_PACKAGE_BYTES', 100):
            refused(PLAIN_PACKAGE, 'too large once inflated')

    def test_a_refusal_names_no_part(self):
        # ids, not content (spec 2.3): the reason reaches the worker's log, so it names no part of the upload
        named = zipped(list(parts_of(PLAIN_PACKAGE).items()) + [(
            'word/_rels/Synthetic-Patient-Name.xml.rels', '<?xml version="1.0"?><!DOCTYPE r><Relationships/>')])
        with self.assertRaises(document.PackageRefused) as caught:
            document.safe_package(named)
        self.assertNotIn('Synthetic-Patient-Name', str(caught.exception))


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


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
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
        with _Listener() as listener, mock.patch.object(docx_package, 'SOFFICE', str(_follower(folder))):
            pdf = document.convert_docx(self.crafted(listener.url))  # the real bounded child and soffice_convert
            heard = list(listener.requests)
            odt = _outcome(opendocument(f'{listener.url}/odt.png'))  # an OpenDocument file named .docx
        self.assertEqual(heard, [])
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual((odt, listener.requests), (CONVERT, []))

    @skipUnless(os.environ.get('CPT_STUDIO_TEST_SOFFICE') or shutil.which('soffice'),
                'no LibreOffice here (CPT_STUDIO_TEST_SOFFICE names one; the image has one)')
    def test_with_libreoffice_itself_no_request_reaches_the_listener(self):
        with _Listener() as listener, mock.patch.object(docx_package, 'SOFFICE', os.environ.get(
                'CPT_STUDIO_TEST_SOFFICE') or shutil.which('soffice')):
            pdf = document.convert_docx(self.crafted(listener.url))
            heard = list(listener.requests)
            odt = _outcome(opendocument(f'{listener.url}/odt.png'))
            plain = document.convert_docx(PLAIN_PACKAGE)
            fields = document.convert_docx(word_package(paragraph(complex_field(
                f' INCLUDEPICTURE "{listener.url}/field.png" \\d '))))
            heard_fields = list(listener.requests)
        self.assertEqual(heard, [])
        self.assertTrue(pdf.startswith(b'%PDF-') and plain.startswith(b'%PDF-') and fields.startswith(b'%PDF-'))
        self.assertEqual((odt, heard_fields), (CONVERT, []))


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


# --- the reference: safe_package as it was before release 1 (studio/fable/document.py at bd7587cc3, lines 57-70 and
# 210-379), every top-level name prefixed and the docstrings shortened; its statements are those of that revision,
# unchanged (PROOFS.md records the check). The byte-identity test holds the new code to it. -------------------------

LEGACY_CONTENT_TYPES_PART = '[Content_Types].xml'
LEGACY_ROOT_RELATIONSHIPS_PART = '_rels/.rels'
LEGACY_RELATIONSHIPS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
LEGACY_CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
LEGACY_OFFICE_DOCUMENT_TYPES = ('http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
                                'http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument')
LEGACY_WORD_MAIN_TYPES = ('application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml')
LEGACY_OPENDOCUMENT_PARTS = ('mimetype', 'meta-inf/manifest.xml')
LEGACY_MAX_PACKAGE_PARTS = 10_000
LEGACY_MAX_PACKAGE_BYTES = 512 * 1024 * 1024
LEGACY_URI_SCHEME = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*:')


class LegacyPackageRefused(Exception):
    """Refused by legacy_safe_package."""


def legacy_safe_package(data: bytes) -> bytes:
    """safe_package as it was before release 1."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError):
        raise LegacyPackageRefused('it is not a zip archive') from None
    with archive:
        infos = archive.infolist()
        if len(infos) > LEGACY_MAX_PACKAGE_PARTS:
            raise LegacyPackageRefused(f'it has more than {LEGACY_MAX_PACKAGE_PARTS:,} parts')
        if any(info.flag_bits & 0x1 for info in infos):
            raise LegacyPackageRefused('a part is encrypted')
        if len({info.filename.casefold() for info in infos}) != len(infos):
            raise LegacyPackageRefused('a part is named twice')
        if sum(info.file_size for info in infos) > LEGACY_MAX_PACKAGE_BYTES:
            raise LegacyPackageRefused('its parts are too large once inflated')
        names = {info.filename for info in infos}
        if any(name.casefold() in LEGACY_OPENDOCUMENT_PARTS for name in names):
            raise LegacyPackageRefused('it is an OpenDocument package, not a Word file')
        if LEGACY_CONTENT_TYPES_PART not in names or LEGACY_ROOT_RELATIONSHIPS_PART not in names:
            raise LegacyPackageRefused('it is not a Word package (no content types or package relationships)')
        try:
            parts = {info.filename: archive.read(info) for info in infos}
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, ValueError, OSError, EOFError) as exc:
            raise LegacyPackageRefused(f'a part cannot be read ({type(exc).__name__})') from None
    by_folded = {name.casefold(): name for name in parts}
    legacy_require_word_main_part(parts, by_folded)
    rewritten, dropped_targets, kept_targets = {}, set(), set()
    for name in parts:
        if not name.casefold().endswith('.rels'):
            continue
        kept, dropped = legacy_relationships(name, parts[name])
        folder = legacy_source_folder(name)
        for relationship in kept:
            target = legacy_part_name(folder, relationship.get('Target', ''))
            if target is not None:
                kept_targets.add(target.casefold())
        for relationship in dropped:
            target = legacy_part_name(folder, relationship.get('Target', ''))
            if target is not None:
                dropped_targets.add(target.casefold())
        if dropped:
            rewritten[name] = legacy_relationships_xml(kept)
    special = {LEGACY_CONTENT_TYPES_PART.casefold()} | {name.casefold() for name in parts
                                                        if name.casefold().endswith('.rels')}
    orphans = {by_folded[target] for target in dropped_targets - kept_targets - special if target in by_folded}
    for orphan in sorted(orphans):
        folder, _, leaf = orphan.rpartition('/')
        own = f'{folder}/_rels/{leaf}.rels' if folder else f'_rels/{leaf}.rels'
        orphans = orphans | ({by_folded[own.casefold()]} if own.casefold() in by_folded else set())
    out = io.BytesIO()
    try:
        with zipfile.ZipFile(out, 'w') as rebuilt:
            for info in infos:
                if info.filename in orphans:
                    continue
                fresh = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                stored = info.compress_type == zipfile.ZIP_STORED
                fresh.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
                rebuilt.writestr(fresh, rewritten.get(info.filename, parts[info.filename]))
    except (ValueError, OverflowError, struct.error, zipfile.LargeZipFile) as exc:
        raise LegacyPackageRefused(f'it cannot be rebuilt ({type(exc).__name__})') from None
    return out.getvalue()


def legacy_xml(name, raw):
    """_xml as it was."""
    probe = expat.ParserCreate()

    def no_dtd(*args):
        raise LegacyPackageRefused(f'{name} declares a DTD')
    probe.StartDoctypeDeclHandler = no_dtd
    probe.EntityDeclHandler = no_dtd
    try:
        probe.Parse(raw, True)
        return ElementTree.fromstring(raw)
    except (expat.ExpatError, ElementTree.ParseError, ValueError):
        raise LegacyPackageRefused(f'{name} is not well-formed XML') from None


def legacy_local(tag) -> str:
    return tag.rpartition('}')[2] if isinstance(tag, str) else ''


def legacy_relationships(name, raw):
    """_relationships as it was."""
    root = legacy_xml(name, raw)
    if root.tag != f'{{{LEGACY_RELATIONSHIPS_NS}}}Relationships':
        raise LegacyPackageRefused(f'{name} is not a package relationships part')
    kept, dropped = [], []
    for child in root:
        modes = [value for key, value in child.attrib.items() if legacy_local(key) == 'TargetMode']
        if legacy_local(child.tag) == 'Relationship' and any(mode != 'Internal' for mode in modes):
            dropped.append(child)
        elif child.tag == f'{{{LEGACY_RELATIONSHIPS_NS}}}Relationship':
            kept.append(child)
    return kept, dropped


def legacy_relationships_xml(kept) -> bytes:
    """_relationships_xml as it was."""
    rows = []
    for relationship in kept:
        attributes = ''.join(f' {key}={quoteattr(relationship.get(key))}'
                             for key in ('Id', 'Type', 'Target', 'TargetMode') if relationship.get(key) is not None)
        rows.append(f'<Relationship{attributes}/>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships '
            f'xmlns="{LEGACY_RELATIONSHIPS_NS}">{"".join(rows)}</Relationships>').encode('utf-8')


def legacy_source_folder(relationships_name) -> str:
    """_source_folder as it was."""
    folder = relationships_name.rpartition('/')[0]
    return folder.rpartition('/')[0] if '/' in folder else ''


def legacy_part_name(folder, target):
    """_part_name as it was."""
    target = (target or '').split('#', 1)[0]
    if not target or LEGACY_URI_SCHEME.match(target) or target.startswith('//'):
        return None
    path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(folder, target))
    return None if path in ('', '.', '..') or path.startswith('../') else path


def legacy_require_word_main_part(parts, by_folded):
    """_require_word_main_part as it was."""
    root = legacy_xml(LEGACY_ROOT_RELATIONSHIPS_PART, parts[LEGACY_ROOT_RELATIONSHIPS_PART])
    if root.tag != f'{{{LEGACY_RELATIONSHIPS_NS}}}Relationships':
        raise LegacyPackageRefused(f'{LEGACY_ROOT_RELATIONSHIPS_PART} is not a package relationships part')
    main = [child for child in root if child.tag == f'{{{LEGACY_RELATIONSHIPS_NS}}}Relationship'
            and child.get('Type') in LEGACY_OFFICE_DOCUMENT_TYPES]
    if len(main) != 1 or main[0].get('TargetMode', 'Internal') != 'Internal':
        raise LegacyPackageRefused('it names no single main document part inside the package')
    target = legacy_part_name('', main[0].get('Target', ''))
    if target is None or target.casefold() not in by_folded:
        raise LegacyPackageRefused('its main document part is missing')
    types = legacy_xml(LEGACY_CONTENT_TYPES_PART, parts[LEGACY_CONTENT_TYPES_PART])
    if types.tag != f'{{{LEGACY_CONTENT_TYPES_NS}}}Types':
        raise LegacyPackageRefused(f'{LEGACY_CONTENT_TYPES_PART} is not a content types part')
    found = None
    for child in types:
        if child.tag == f'{{{LEGACY_CONTENT_TYPES_NS}}}Override' and \
                (child.get('PartName') or '').lstrip('/').casefold() == target.casefold():
            found = child.get('ContentType')
    if found is None:
        extension = target.rpartition('.')[2].casefold() if '.' in target.rpartition('/')[2] else ''
        for child in types:
            if child.tag == f'{{{LEGACY_CONTENT_TYPES_NS}}}Default' and \
                    (child.get('Extension') or '').casefold() == extension:
                found = child.get('ContentType')
    if found not in LEGACY_WORD_MAIN_TYPES:  # compared exactly, as LibreOffice's own detection compares it
        raise LegacyPackageRefused('its main document part is not a Word document')
