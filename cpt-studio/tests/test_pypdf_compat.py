"""pypdf 6.21.4 read as pypdf 6.21.2 reads (studio/ingest/pypdf_compat.py): the layer is applied where CPT Studio
reads PDFs with pypdf (the extraction child, ops/verify_passages.py, this test package, ops/verification's suite), the
extraction child reads each restored shape as 6.21.2 did, a pypdf the layer was not proven against is refused before
anything is patched and the reason is kept for operators, the advisory fixes the layer keeps are checked as loaded,
the two advisory limits the reader can meet are named before anything is read past them, and the layer's address
space is given back to the PDF child. Synthetic PDFs only."""
import dataclasses
import io
import json
import resource
import subprocess
import sys
import textwrap
import unittest
import zlib
from pathlib import Path
from unittest import mock

import pypdf
from pypdf.errors import LimitReachedError, PdfReadError

from studio.ingest import _child, extract, pypdf_compat
from studio.ingest import pdf as reader
from studio.ingest.extract import Limits, extract_document
from studio.types import to_jsonable
from tests.support import pypdf_limits as shapes
from tests.support.pypdf_guards import GUARDS, holds

SERVICE = Path(__file__).resolve().parents[1]
NOTE = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING', 'Date of service: 2026-10-21',
        'Procedure: Colonoscopy to the cecum.', 'Findings: A 6 mm sigmoid polyp was seen.']
TARGETS = ('pypdf._cmap:_parse_encoding', 'pypdf._cmap:_glyph_name_to_unicode', 'pypdf._text_extraction:get_text_operands',
           'pypdf.generic._font:Font._collect_cid_character_widths', 'pypdf._encryption:Encryption.read',
           'pypdf.filters:FlateDecode.decode', 'pypdf.filters:CCITTFaxDecode._get_parameters',
           'pypdf.filters:decode_stream_data', 'pypdf._page:PageObject._extract_text',
           'pypdf.generic._data_structures:DictionaryObject.read_from_stream',
           'pypdf._reader:PdfReader._sanitize_pdf15_xref_stream_index_pairs')
# The advisory fixes the reader depends on that the layer keeps unpatched, and checks as loaded (pypdf-r6 FC-2).
CHECKED = ('pypdf._reader:PdfReader.__init__', 'pypdf._reader:PdfReader._read_xref_tables_and_trailers',
           'pypdf._reader:PdfReader._read_xref', 'pypdf._reader:PdfReader._read_pdf15_xref_stream',
           'pypdf._doc_common:PdfDocCommon._flatten', 'pypdf._doc_common:PdfDocCommon._flatten_leaf_page')


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
    def run_layer(self, change: str, why: bool = False) -> list:
        """Apply the layer with ``change`` made to it, in a fresh interpreter; what it prints (and why it refused)."""
        code = textwrap.dedent(f'''
            import dataclasses
            from studio.ingest import pypdf_compat as layer
            {change}
            try:
                layer.apply()
                print('applied')
            except layer.PypdfCompatError as exc:
                import pypdf._cmap, pypdf.filters
                patched = pypdf._cmap._parse_encoding.__code__.co_filename.startswith('<pypdf_compat')
                print('refused', 'patched' if patched or hasattr(pypdf.filters, 'NullObject') else 'unpatched')
                if {why!r}:
                    print(exc)
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
                mock.patch('studio.ingest.pdf.extract_pdf') as reader_called:
            result = _child.parse(_pdf(_lines(NOTE)), 'pdf', Limits(), None, 0.0, '/nonexistent')
        self.assertEqual((result.status, result.text, result.messages), ('failed', '', (_child.PDF_UNAVAILABLE,)))
        reader_called.assert_not_called()

    def test_a_refusal_keeps_its_reason_for_operators_and_names_no_version(self):  # pypdf-r6 FC-3
        reason = 'pypdf.filters:FlateDecode.decode: its loaded code is not its source.'
        with mock.patch.object(pypdf_compat, 'apply', side_effect=pypdf_compat.PypdfCompatError(reason + ' ' * 300)):
            result = _child.parse(_pdf(_lines(NOTE)), 'pdf', Limits(), None, 0.0, '/nonexistent')
        self.assertEqual(result.engine, {'ingest': 'cpt-studio-ingest@3', 'pypdf_compat': (reason + ' ' * 300)[:200]})
        self.assertEqual(_child.PDF_UNAVAILABLE, 'The PDF could not be read on this server: its PDF library is not the '
                                                 'one the PDF reader was checked with.')
        self.assertNotIn('version', _child.PDF_UNAVAILABLE)  # the cause may be a file, a binding or loaded code
        # the parent keeps the reason: the child's answer passes its checks with the reason in it
        answer = json.dumps(to_jsonable(result)).encode()
        kept = extract._result(extract._ChildRun('exited', 0, answer), 'pdf', 'pdf-text', Limits(), {})
        self.assertEqual((kept.status, kept.messages, kept.engine['pypdf_compat']),
                         ('failed', (_child.PDF_UNAVAILABLE,), (reason + ' ' * 300)[:200]))
        # a successful read records no reason (the identity of every read row is unchanged)
        read = extract_document(_pdf(_lines(NOTE)), 'synthetic.pdf', 'application/pdf', ocr=None)
        self.assertEqual((read.status, sorted(read.engine)), ('ok', ['ingest', 'pypdf']))

    def test_the_unpatched_advisory_fixes_are_checked_as_loaded(self):  # pypdf-r6 FC-2
        for target in CHECKED:
            with self.subTest(target=target):
                module, qualname = target.split(':')
                owner, name = qualname.split('.')
                # the function's loaded code replaced, as a stale or foreign .pyc would replace it
                change = (f"import importlib; owner = getattr(importlib.import_module({module!r}), {owner!r}); "
                          f"owner.{name}.__code__ = (lambda self, *a, **k: None).__code__.replace("
                          f"co_name={name!r}, co_qualname={qualname!r})")
                done = self.run_layer(change, why=True)
                self.assertEqual(done[:2], ['refused', 'unpatched'], done)
                self.assertIn(f'{target}: its loaded code is not its source.', ' '.join(done))
        self.assertEqual(tuple(row.target for row in pypdf_compat._CHECKED), CHECKED)
        self.assertFalse(set(CHECKED) & set(TARGETS))  # checked, never patched


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
                    self.assertTrue(reader.advisory_limit(wrapped, None))

    def test_a_limit_pypdf_6_21_2_had_stays_damage(self):
        self.assertFalse(reader.advisory_limit(LimitReachedError('Reached maximum array element count.'), None))
        self.assertFalse(reader.advisory_limit(PdfReadError('Could not find xref table at specified location'), None))

    def test_a_cross_reference_stream_left_out_at_the_limit_is_named(self):
        counted = mock.Mock(_xref_stream_entry_count=2_000_008, _xref_stream_maximum_entries=2_000_000)
        self.assertTrue(reader.advisory_limit(None, counted))
        counted = mock.Mock(_xref_stream_entry_count=2_000_000, _xref_stream_maximum_entries=2_000_000)
        self.assertFalse(reader.advisory_limit(None, counted))
        self.assertTrue(reader.LIMIT_REACHED.startswith('The PDF could not be read'))


def _read(data: bytes):
    return extract_document(data, 'synthetic.pdf', 'application/pdf', ocr=None)


class CountedAtEveryReadTests(unittest.TestCase):
    """#4269 counts a cross-reference stream's entries at every read of it, as pypdf 6.21.4 counts them: a stream that
    an older trailer names again is read and counted again. A document whose reads add up past 2,000,000 entries is
    refused (LIMIT_REACHED) whatever its distinct entries: the named class S-limit (pypdf-r6 C1, C2, V3, L4, F2, L5;
    pypdf-r7 RG-1, FC7-1, RG-2; pypdf-r8 RG8-K). pypdf 6.21.2 read these files (a re-read added no entry); plain 6.21.4
    leaves out the section whose read passed the limit and reads on (V3), so the refusal is what keeps a reading from
    ever being partial."""

    def test_a_stream_named_again_is_read_and_counted_again(self):
        for alias in (False, True):  # named again at its offset, or one byte early (the line break before its header)
            with self.subTest(alias=alias), self.assertLogs('pypdf', 'WARNING') as logged:
                found = pypdf.PdfReader(io.BytesIO(shapes.repeated(6_000, 3, alias=alias)),
                                        xref_stream_maximum_entries=20_000)
                self.assertEqual(found._xref_stream_entry_count, 18_000)  # 6,000 x 3 namings, as plain 6.21.4
                # each re-read caches X again, as pypdf 6.21.2's re-reads did
                self.assertEqual(' '.join(logged.output).count('Overwriting cache for 0 8'), 2)
                self.assertFalse(reader.advisory_limit(None, found))
                self.assertEqual(found.get_object(9)['/Contents'], shapes.ANNOTATION)

    def test_two_namings_past_the_limit_are_refused(self):  # pypdf-r6 C1: 1,000,001 distinct entries, named twice
        result = _read(shapes.repeated(1_000_001, 2))
        self.assertEqual((result.status, result.messages), ('failed', (reader.LIMIT_REACHED,)))
        at = _read(shapes.repeated(1_000_000, 2))  # control: 1,000,000 x 2 is the limit itself, read as 6.21.2 reads it
        self.assertEqual(at.status, 'ok', at.messages)
        self.assertIn(shapes.ANNOTATION, at.text)

    def test_a_distinct_section_is_never_left_out(self):  # pypdf-r6 V3: X, X again, then Y
        data = shapes.repeated_then_distinct(600_000, 700_001)  # 1,300,001 distinct entries, counted 2,000,002
        result = _read(data)
        self.assertEqual((result.status, result.messages), ('failed', (reader.LIMIT_REACHED,)))
        # what the refusal prevents: pypdf 6.21.4 reads on with Y, the annotation's only listing, left out
        with self.assertLogs('pypdf', 'WARNING') as logged:
            found = pypdf.PdfReader(io.BytesIO(data))
        self.assertNotIn(9, found.xref_objStm)
        self.assertIn('can not be read, some object may be missing', ' '.join(logged.output))
        once = _read(shapes.repeated_then_distinct(600_000, 700_001, repeat=False))  # control: X is not named again
        self.assertEqual(once.status, 'ok', once.messages)
        self.assertIn(shapes.ANNOTATION, once.text)

    def test_a_page_tree_too_deep_is_named_at_the_limit_first(self):  # pypdf-r6 C2: C1 with a page-tree depth of 101
        result = _read(shapes.repeated(1_000_001, 2, depth=101))
        self.assertEqual((result.status, result.messages), ('failed', (reader.LIMIT_REACHED,)))
        once = _read(shapes.repeated(1_000_001, 1, depth=101))  # control: named once, pypdf's page-tree depth limit
        self.assertEqual((once.status, once.messages), ('failed', (reader.DAMAGED,)))


class PastTheLimitTests(unittest.TestCase):
    """A file past #4269's limit is named as soon as pypdf's constructor returns, before the password test and the
    first page (pypdf-r6 L1-L3); at the limit it reads."""

    def test_named_before_the_password_test_and_when_the_constructor_raises(self):
        for hidden in ('password', 'encrypt', 'annotation', 'kids'):
            with self.subTest(hidden=hidden):
                result = _read(shapes.past_the_limit(hidden))
                self.assertEqual((result.status, result.messages), ('failed', (reader.LIMIT_REACHED,)))
        at = _read(shapes.past_the_limit('annotation', entries=shapes.LIMIT))  # control: exactly the limit
        self.assertEqual(at.status, 'ok', at.messages)
        self.assertIn(shapes.ANNOTATION, at.text)

    def test_nothing_reads_an_object_once_the_limit_is_seen(self):
        data = shapes.past_the_limit('kids')
        with mock.patch.object(pypdf.PdfReader, 'get_page', autospec=True) as get_page, \
                mock.patch.object(pypdf.PdfReader, 'decrypt', autospec=True) as decrypt, \
                self.assertLogs('pypdf', 'WARNING'):
            self.assertEqual(reader._open(data), (None, reader.LIMIT_REACHED))
        get_page.assert_not_called()  # each missing kid would cost a search of the whole file (pypdf-r6 L1)
        decrypt.assert_not_called()


class NegativeIndexCountTests(unittest.TestCase):
    """A negative /Index count takes part in the clamp's arithmetic as in pypdf 6.21.2 and reads and counts no entry
    (pypdf-r6 F1; #4269 kept)."""

    def test_the_arithmetic_is_6_21_2s_and_no_entry_is_counted(self):
        with self.assertLogs('pypdf', 'WARNING') as logged:
            found = pypdf.PdfReader(io.BytesIO(shapes.negative_count()))
            stream = found.get_object(6)
            pairs = found._sanitize_pdf15_xref_stream_index_pairs([0, -20, 6, 1, 0, 7], [0, 2, 1], stream)
        self.assertEqual(pairs, [0, 0, 6, 1, 0, 7])  # 6.21.2: [0, -20, 6, 1, 0, 7]; 6.21.4: [0, 0, 6, 1, 0, 1]
        self.assertEqual(found._xref_stream_entry_count, 8)  # 1 + 7: the negative count counts nothing
        self.assertIn('Negative XRef count -20, using 0.', ' '.join(logged.output))  # #4269's warning kept
        with self.assertRaises(PdfReadError) as raised:  # and its refusal in strict mode
            pypdf.PdfReader(io.BytesIO(shapes.negative_count()), strict=True)
        self.assertEqual(str(raised.exception.__cause__), 'Negative XRef count -20.')

    def test_through_the_child_the_update_shadows_the_table_as_6_21_2(self):
        result = _read(shapes.negative_count())
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertTrue(result.text.rstrip().endswith(shapes.OLDER), result.text[-80:])
        control = _read(shapes.negative_count(b'6 1 0 7'))  # no negative count: both versions read the table
        self.assertTrue(control.text.rstrip().endswith(shapes.CURRENT), control.text[-80:])


class AddressSpaceTests(unittest.TestCase):
    """The layer's address space is given back to the PDF child (pypdf-r6 F3): the limit pypdf 6.21.2's reader had
    for a document is unchanged."""

    def test_only_the_pdf_child_is_given_the_layers_allowance(self):
        limits = {kind: dict((which, soft) for which, soft, _ in extract._rlimits(Limits(), kind))
                  for kind in ('pdf', 'docx', 'txt')}
        self.assertEqual(limits['pdf'][resource.RLIMIT_AS], extract.AS_LIMIT_BYTES + extract.PDF_LAYER_AS_BYTES)
        self.assertEqual(limits['docx'][resource.RLIMIT_AS], extract.AS_LIMIT_BYTES)
        self.assertEqual(limits['txt'][resource.RLIMIT_AS], extract.AS_LIMIT_BYTES)
        self.assertEqual(extract.PDF_LAYER_AS_BYTES % 4096, 0)

    def test_the_layers_footprint_in_the_real_child_is_within_its_allowance(self):
        """The smallest address-space limit at which the real child reads a guard PDF, with the layer and with the
        layer replaced by a stub that applies nothing: the difference is the layer's footprint."""
        data = GUARDS['a /BaseEncoding array'][1]
        stub = ("import sys, types; stub = types.ModuleType('studio.ingest.pypdf_compat'); "
                "stub.PypdfCompatError = type('PypdfCompatError', (Exception,), {}); stub.apply = lambda: (); "
                "sys.modules['studio.ingest.pypdf_compat'] = stub; ")
        run = "import runpy; runpy.run_module('studio.ingest._child', run_name='__main__', alter_sys=True)"

        def smallest(prelude: str) -> int:
            lo, hi = 16 * 1024 // 4, 512 * 1024 // 4  # pages (KiB / 4): fails at lo, reads at hi
            with mock.patch.object(extract, 'CHILD_ARGV', (sys.executable, '-c', prelude + run)), \
                    mock.patch.object(extract, '_child_env', lambda: dict(extract.tool_env(), PYTHONHASHSEED='0',
                                                                          PYTHONDONTWRITEBYTECODE='1',
                                                                          PYTHONNOUSERSITE='1', PYTHONUTF8='1')), \
                    mock.patch.object(extract, 'PDF_LAYER_AS_BYTES', 0):
                def reads(pages):
                    with mock.patch.object(extract, 'AS_LIMIT_BYTES', pages * 4096):
                        return _read(data).status == 'ok'
                self.assertTrue(reads(hi))
                self.assertFalse(reads(lo))
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    lo, hi = (lo, mid) if reads(mid) else (mid, hi)
            return hi * 4096

        footprint = smallest('') - smallest(stub)
        self.assertLessEqual(footprint, extract.PDF_LAYER_AS_BYTES, f'the layer now costs {footprint} bytes')
