"""studio.fable.document (BUILD-SPEC 4.3): the document block for a PDF, a Word file (through a converter) and text,
its stored form, and every way a document cannot be sent. Synthetic bytes only; no LibreOffice is run."""
import base64
import hashlib
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from studio.fable import CONVERT, DOCUMENT, STORAGE
from studio.fable import document
from studio.storage import ALLOWED_SUFFIXES, OriginalCorrupted
from tests.support import coding as f

DOCX = ALLOWED_SUFFIXES['.docx']
CONVERTED = b'%PDF-1.4\n% synthetic conversion\n%%EOF\n'


def fake_runner(data):  # runs in the bounded child (Django-free)
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
        docx = b'PK\x03\x04synthetic docx'
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
        self.assertEqual(document.convert_docx(b'PK\x03\x04data', runner=fake_runner), CONVERTED + b'PK\x03\x04')

    def test_a_child_that_fails_or_returns_no_pdf_is_convert(self):
        for runner in (failing_runner, no_pdf_runner):
            with self.subTest(runner=runner.__name__), self.assertRaises(document.DocumentError) as caught:
                document.convert_docx(b'PK\x03\x04data', runner=runner)
            self.assertEqual((caught.exception.failure_kind, caught.exception.text), (CONVERT, document.CONVERT_TEXT))

    def test_a_child_past_its_time_is_convert(self):
        with self.assertRaises(document.DocumentError) as caught:
            document.convert_docx(b'PK\x03\x04data', runner=_sleeps, seconds=0.5)
        self.assertIn('time', caught.exception.detail)

    def test_soffice_runs_with_a_throwaway_home_and_profile_and_no_inherited_environment(self):
        seen = {}

        class Process:
            pid, returncode = 999_999_999, 0

            def __init__(self, command, **kwargs):
                seen.update(command=command, **kwargs)
                out = Path(command[command.index('--outdir') + 1])
                (out / 'document.pdf').write_bytes(CONVERTED)

            def wait(self, timeout=None):
                return 0
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'must-not-leak'}), \
                mock.patch('subprocess.Popen', Process), mock.patch('os.killpg') as killpg:
            self.assertEqual(document.soffice_convert(b'PK\x03\x04data'), CONVERTED)
        command, env = seen['command'], seen['env']
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
