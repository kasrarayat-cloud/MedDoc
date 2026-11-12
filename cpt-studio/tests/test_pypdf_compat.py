"""pypdf 6.21.4 read as pypdf 6.21.2 reads (studio/ingest/pypdf_compat.py): the layer is in place wherever PDFs are
read, the extraction child reads each restored shape as 6.21.2 did, a pypdf the layer was not proven against is
refused before anything is patched, and the two advisory limits the reader can meet are named. Synthetic PDFs only."""
import dataclasses
import subprocess
import sys
import textwrap
import unittest
import zlib
from pathlib import Path
from unittest import mock

from pypdf.errors import LimitReachedError, PdfReadError

from studio.ingest import _child, pypdf_compat
from studio.ingest.extract import Limits, extract_document
from studio.ingest.pdf import LIMIT_REACHED, _advisory_limit
from tests.support.pypdf_guards import GUARDS, holds

SERVICE = Path(__file__).resolve().parents[1]
NOTE = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING', 'Date of service: 2026-10-21',
        'Procedure: Colonoscopy to the cecum.', 'Findings: A 6 mm sigmoid polyp was seen.']
TARGETS = ('pypdf._cmap:_parse_encoding', 'pypdf._cmap:_glyph_name_to_unicode', 'pypdf._text_extraction:get_text_operands',
           'pypdf.generic._font:Font._collect_cid_character_widths', 'pypdf._encryption:Encryption.read',
           'pypdf.filters:FlateDecode.decode', 'pypdf.filters:CCITTFaxDecode._get_parameters',
           'pypdf.filters:decode_stream_data', 'pypdf._page:PageObject._extract_text',
           'pypdf.generic._data_structures:DictionaryObject.read_from_stream')


def _stream(data: bytes, extra: str = '') -> bytes:
    return f'<< {extra} /Length {len(data)} >>\nstream\n'.encode() + data + b'\nendstream'


def _pdf(content: bytes, extra: dict | None = None) -> bytes:
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  b'/Contents 5 0 R >>',
               4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
               5: _stream(content)}
    objects.update(extra or {})
    out, offsets = bytearray(b'%PDF-1.7\n'), {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b'%d 0 obj\n' % number + objects[number] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (max(objects) + 1)
    out += b''.join(b'%010d 00000 n \n' % offsets[n] if n in offsets else b'0000000000 65535 f \n'
                    for n in range(1, max(objects) + 1))
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (max(objects) + 1, xref)
    return bytes(out)


def _lines(rows) -> bytes:
    return '\n'.join(f'BT /F1 11 Tf 72 {740 - 20 * n} Td ({row}) Tj ET' for n, row in enumerate(rows)).encode()


class LayerTests(unittest.TestCase):
    def test_applied_in_this_process(self):
        report = pypdf_compat.applied()  # tests/__init__.py applies it, as the child does before reading a PDF
        self.assertIsNotNone(report)
        self.assertEqual(tuple(row[0] for row in report), TARGETS)
        self.assertIs(pypdf_compat.apply(), report)

    def test_every_binding_holds_its_replacement(self):
        import pypdf._cmap as cmap
        import pypdf._text_extraction as extraction
        import pypdf._text_extraction._text_extractor as extractor
        import pypdf.filters as filters
        from pypdf._page import PageObject
        from pypdf.generic import DictionaryObject
        from pypdf.generic._font import Font

        for function in (cmap._parse_encoding, cmap._glyph_name_to_unicode, extraction.get_text_operands,
                         extractor.get_text_operands, filters.decode_stream_data, filters.FlateDecode.decode,
                         filters.CCITTFaxDecode._get_parameters, Font._collect_cid_character_widths,
                         PageObject._extract_text, DictionaryObject.read_from_stream):
            with self.subTest(function=function.__qualname__):
                self.assertTrue(function.__code__.co_filename.startswith('<pypdf_compat '))
        self.assertIs(extractor.get_text_operands, extraction.get_text_operands)
        self.assertIsNone(cmap._glyph_name_to_unicode('/uF00C'))  # pypdf 6.21.2: only /uni names
        self.assertEqual(cmap._glyph_name_to_unicode('/uni2612'), '☒')


    def test_a_memory_failure_inside_a_dictionary_is_raised_as_itself(self):  # #4265 kept; its outcome named
        import io

        import pypdf.generic._data_structures as structures
        from pypdf.generic import DictionaryObject

        with mock.patch.object(structures, 'read_object', side_effect=MemoryError):
            with self.assertRaises(MemoryError) as raised:  # pypdf 6.21.4 itself raises PdfReadError here
                DictionaryObject.read_from_stream(io.BytesIO(b'<< /A 1 >>'), None)
            self.assertIsNone(raised.exception.__cause__)
        with mock.patch.object(structures, 'read_object', side_effect=RecursionError):
            with self.assertRaises(PdfReadError) as raised:  # #4265 kept: the fixed message, the cause chained
                DictionaryObject.read_from_stream(io.BytesIO(b'<< /A 1 >>'), None)
            self.assertEqual(raised.exception.args, ('Error reading PDF file.',))
            self.assertIsInstance(raised.exception.__cause__, RecursionError)


class ChildReadsAs6212Tests(unittest.TestCase):
    """Through the real extraction child (a fresh process that applies the layer), OCR unavailable."""

    def read(self, data: bytes):
        return extract_document(data, 'synthetic.pdf', 'application/pdf', ocr=None)

    def test_a_non_numeric_td_leaves_the_page_unread(self):  # _page.py @@ -1956,7 +1960,9 @@
        result = self.read(_pdf(_lines(NOTE) + b'\nBT /F1 11 Tf 72 600 Td (Cold snare polypectomy) Tj 0 /A TD '
                                                b'(of the sigmoid polyp.) Tj ET'))
        self.assertEqual(result.status, 'failed')
        self.assertIn('Page 1 has no usable text layer and OCR is not available on this server.', result.messages)

    def test_a_decode_parms_number_on_ascii85_is_not_damage(self):  # filters.py @@ -967,10 +982,17 @@
        import base64
        data = base64.a85encode(_lines(NOTE)) + b'~>'
        result = self.read(_pdf(b'', {5: _stream(data, '/Filter /ASCII85Decode /DecodeParms 5')}))
        self.assertEqual((result.status, result.messages), ('ok', ()))

    def test_a_flate_predictor_through_an_indirect_dictionary_still_decodes(self):  # filters.py @@ -198,13 +198,10 @@
        rows, previous, raw = [], bytes(4), _lines(NOTE)
        raw += b' ' * (-len(raw) % 4)
        for start in range(0, len(raw), 4):
            row = raw[start:start + 4]
            rows.append(b'\x02' + bytes((a - b) % 256 for a, b in zip(row, previous)))
            previous = row
        content = _stream(zlib.compress(b''.join(rows)), '/Filter /FlateDecode /DecodeParms 9 0 R')
        result = self.read(_pdf(b'', {5: content, 9: b'<< /Predictor 12 /Columns 4 >>'}))
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertIn('Colonoscopy to the cecum.', result.text)


    def test_a_deeply_nested_dictionary_reads_as_pypdf_reads_it(self):  # no patch adds a frame per nesting level
        # pypdf 6.21.2 and 6.21.4 both read a dictionary nested 400 levels deep; a wrapper around
        # DictionaryObject.read_from_stream (one more frame per level) met the recursion limit near 330 levels and
        # cut the page dictionary before its /Contents (pypdf-r6 reconcile, rec-nested-dict-340..480).
        nested = b'/PieceInfo ' + b'<< /A ' * 400 + b'/Z 1 ' + b'>> ' * 400
        data = _pdf(_lines(NOTE), {3: b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << '
                                      b'/F1 4 0 R >> >> ' + nested + b'/Contents 5 0 R >>'})
        result = self.read(data)
        self.assertEqual((result.status, result.messages), ('ok', ()))
        self.assertIn('Colonoscopy to the cecum.', result.text)


class EachPatchIsGuardedTests(unittest.TestCase):
    """One PDF per patch, through the real child: each reads as pypdf 6.21.2 reads it only with the layer (without it,
    pypdf 6.21.4 reads every one of them otherwise)."""

    def test_each_patch_reads_as_6212(self):
        for name, (patch, data, expected) in GUARDS.items():
            with self.subTest(patch=patch, shape=name):
                result = extract_document(data, 'synthetic.pdf', 'application/pdf', ocr=None)
                self.assertTrue(holds(result, expected), (result.status, result.messages, result.text[-60:]))


class RefusalTests(unittest.TestCase):
    def run_layer(self, change: str) -> str:
        """Apply the layer with ``change`` made to it, in a fresh interpreter; what it prints."""
        code = textwrap.dedent(f'''
            import dataclasses
            from studio.ingest import pypdf_compat as layer
            {change}
            try:
                layer.apply()
                print('applied')
            except layer.PypdfCompatError:
                import pypdf._cmap, pypdf.filters
                patched = pypdf._cmap._parse_encoding.__code__.co_filename.startswith('<pypdf_compat')
                print('refused', 'patched' if patched or hasattr(pypdf.filters, 'NullObject') else 'unpatched')
                try:
                    layer.apply()
                except layer.PypdfCompatError:
                    print('still refused')
        ''')
        done = subprocess.run([sys.executable, '-E', '-s', '-B', '-c', code], cwd=SERVICE, capture_output=True, text=True,
                              timeout=60, check=True)
        return done.stdout.split()

    def test_the_layer_applies_in_a_fresh_interpreter(self):
        self.assertEqual(self.run_layer('pass'), ['applied'])

    def test_a_function_whose_source_differs_is_refused_before_anything_is_patched(self):
        change = ("layer._PATCHES = layer._PATCHES[:-1] + (dataclasses.replace(layer._PATCHES[-1], "
                  "original_sha256='0' * 64),)")
        self.assertEqual(self.run_layer(change), ['refused', 'unpatched', 'still', 'refused'])

    def test_a_pypdf_file_that_differs_is_refused(self):
        change = "layer._MANIFEST = dict(layer._MANIFEST, **{'_reader.py': '0' * 64})"
        self.assertEqual(self.run_layer(change), ['refused', 'unpatched', 'still', 'refused'])

    def test_another_pypdf_version_is_refused(self):
        self.assertEqual(self.run_layer("layer.PYPDF_VERSION = '6.21.2'"), ['refused', 'unpatched', 'still', 'refused'])

    def test_an_unlisted_binding_is_refused(self):
        change = ("import pypdf._cmap, types; sys_mod = types.ModuleType('elsewhere'); "
                  "sys_mod.alias = pypdf._cmap._glyph_name_to_unicode; import sys; sys.modules['elsewhere'] = sys_mod")
        self.assertEqual(self.run_layer(change), ['refused', 'unpatched', 'still', 'refused'])

    def test_the_child_names_a_refusal_and_reads_nothing(self):
        with mock.patch.object(pypdf_compat, 'apply', side_effect=pypdf_compat.PypdfCompatError('not proven')), \
                mock.patch('studio.ingest.pdf.extract_pdf') as reader:
            result = _child.parse(_pdf(_lines(NOTE)), 'pdf', Limits(), None, 0.0, '/nonexistent')
        self.assertEqual((result.status, result.text, result.messages), ('failed', '', (_child.PDF_UNAVAILABLE,)))
        reader.assert_not_called()


class AdvisoryLimitTests(unittest.TestCase):
    def test_a_limit_an_advisory_fix_added_is_named(self):
        for message in ('Maximum XRef stream entry limit reached: 2000001 > 2000000.',
                        'Maximum page tree page entry limit exceeded!'):
            with self.subTest(message=message):
                try:
                    try:
                        raise LimitReachedError(message)
                    except LimitReachedError as exc:
                        raise PdfReadError(f'Trailer cannot be read: {exc}') from exc
                except PdfReadError as wrapped:
                    self.assertTrue(_advisory_limit(wrapped, None))

    def test_a_limit_pypdf_6_21_2_had_stays_damage(self):
        self.assertFalse(_advisory_limit(LimitReachedError('Reached maximum array element count.'), None))
        self.assertFalse(_advisory_limit(PdfReadError('Could not find xref table at specified location'), None))

    def test_a_cross_reference_stream_left_out_at_the_limit_is_named(self):
        reader = mock.Mock(_xref_stream_entry_count=2_000_008, _xref_stream_maximum_entries=2_000_000)
        self.assertTrue(_advisory_limit(None, reader))
        reader = mock.Mock(_xref_stream_entry_count=2_000_000, _xref_stream_maximum_entries=2_000_000)
        self.assertFalse(_advisory_limit(None, reader))
        self.assertTrue(LIMIT_REACHED.startswith('The PDF could not be read'))
