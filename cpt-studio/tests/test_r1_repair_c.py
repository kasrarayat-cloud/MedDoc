"""Release 1, repair round 1, builder C: the Word conversion and the converter (the integrated refutation's coding-0 to
coding-4). Each test fails on the lens's own input before its repair and passes after it; PROOFS.md in the builder's
folder records the mutation that undoes each repair and the test it fails.

- C1 (coding-0): no ratio of inflated to stored size is held against a part. Generated Word tables (no w14:paraId, a
  border on every cell) deflate more than 100 times, and the code before release 1 converts them; the absolute limits,
  the bounded reader and the bounded child's limits still hold.

Synthetic bytes only, every package built here; no LibreOffice, no network, no provider."""
import io
import random
import zipfile
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from studio.fable import document, docx_package
from studio.models import SourceRevision
from tests.test_fable_document import (CONVERTED, DANGEROUS, DOCX, FULL_NAMESPACES, NAMESPACES, PLAIN_PACKAGE, TEXT,
                                       WORD_MAIN, _echo_package, complex_field, content_types, legacy_safe_package,
                                       lying, override, paragraph, parts_of, private_tempdir, relationship,
                                       relationships, word_package)

MIB = 1024 * 1024

# --- C1: Word tables as report generators write them (the L-CODING lens's coding-0 builders, rebuilt here) ---------
GENERATED_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
GENERATED_RSID = 'w:rsidR="00A21F3C" w:rsidRDefault="00A21F3C" w:rsidP="00A21F3C"'
GENERATED_BORDERS = ('<w:tcBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" '
                     'w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" '
                     'w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tcBorders>')
FLOWSHEET_VALUES = ('WNL', '—', 'N/A', '0', 'Given', 'Held', 'WNL', 'WNL', '—', '—')


def generated_cell(text=''):
    """One table cell as a generator writes it: its width, four borders and alignment, and a paragraph with its own
    spacing, alignment and run font - no w14:paraId, so every cell's XML repeats the last."""
    run = (f'<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="16"/></w:rPr>'
           f'<w:t>{text}</w:t></w:r>') if text else ''
    return (f'<w:tc><w:tcPr><w:tcW w:w="400" w:type="dxa"/>{GENERATED_BORDERS}<w:vAlign w:val="center"/></w:tcPr>'
            f'<w:p {GENERATED_RSID}><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/>'
            f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="16"/></w:rPr></w:pPr>{run}'
            '</w:p></w:tc>')


def generated_note():
    lines = ('SYNTHETIC PROCEDURE NOTE - FICTIONAL - NO PATIENT DATA', 'Procedure: colonoscopy with biopsy.',
             'Findings: two small polyps removed by cold snare.', 'Medication administration record follows.')
    return ''.join(f'<w:p {GENERATED_RSID}><w:r><w:t>{line}</w:t></w:r></w:p>' for line in lines)


def generated_flowsheet(rows, cols, seed=9):
    """A vital-signs flowsheet: ``rows`` x ``cols`` cells of repeated short values."""
    rng = random.Random(seed)
    out = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr><w:tblGrid>' + '<w:gridCol w:w="400"/>' * cols
           + '</w:tblGrid>']
    for _ in range(rows):
        out.append('<w:tr>' + ''.join(generated_cell(rng.choice(FLOWSHEET_VALUES)) for _ in range(cols)) + '</w:tr>')
    return ''.join(out) + '</w:tbl>'


def generated_medication_grid(rows, days=31):
    """A medication administration record: ``rows`` x ``days`` bordered cells, a handful filled in."""
    filled = {(row, day) for row in range(0, 60, 7) for day in range(0, days, 5)}
    out = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>',
           '<w:gridCol w:w="400"/>' * days, '</w:tblGrid>']
    for row in range(rows):
        out.append('<w:tr><w:trPr><w:trHeight w:val="280"/></w:trPr>')
        out += [generated_cell('x' if (row, day) in filled else '') for day in range(days)]
        out.append('</w:tr>')
    return ''.join(out + ['</w:tbl>'])


def generated_package(body, level=None):
    """A Word file as a generator writes one: the three parts a .docx needs, the main part with a CRLF after its XML
    declaration, the root declaring Word's namespaces, a landscape section; deflated at ``level``."""
    xml = (f'{GENERATED_HEADER}<w:document {FULL_NAMESPACES}><w:body>{body}<w:sectPr><w:pgSz w:w="15840" w:h="12240" '
           'w:orient="landscape"/></w:sectPr></w:body></w:document>')
    entries = [('[Content_Types].xml', content_types(override('word/document.xml', WORD_MAIN))),
               ('_rels/.rels', relationships(relationship('rId1', 'officeDocument', 'word/document.xml'))),
               ('word/document.xml', xml)]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=level) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


def generated_tables():
    """(label, bytes) of the lens's generated Word files: none holds a field, an object, a control or an altChunk."""
    return [('vital-signs flowsheet 70x24', generated_package(generated_note() + generated_flowsheet(70, 24))),
            ('vital-signs flowsheet 120x24', generated_package(generated_note() + generated_flowsheet(120, 24))),
            ('medication grid 60x31', generated_package(generated_note() + generated_medication_grid(60))),
            ('medication grid 60x31, level 9', generated_package(generated_note() + generated_medication_grid(60), 9)),
            ('medication grid 90x31', generated_package(generated_note() + generated_medication_grid(90)))]


def deflation(data, name='word/document.xml'):
    """(inflated size, stored size) of the part ``name``."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo(name)
    return info.file_size, info.compress_size


def zero_parts(*sizes):
    """PLAIN_PACKAGE plus one part of zeros per size, named customXml/itemN.xml: small uploads that inflate hugely."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for entry, content in parts_of(PLAIN_PACKAGE).items():
            archive.writestr(entry, content)
        for number, size in enumerate(sizes, 1):
            with archive.open(f'customXml/item{number}.xml', 'w', force_zip64=False) as handle:
                left = size
                while left:
                    handle.write(b'\x00' * min(left, MIB))
                    left -= min(left, MIB)
    return buffer.getvalue()


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
class GeneratedTableTests(SimpleTestCase):
    """C1 (coding-0): the lens's generated tables were refused for good ('a part inflates more than 100 times its
    stored size') where the code before release 1 converts them."""

    def setUp(self):
        private_tempdir(self)

    def test_generated_tables_the_ratio_refused_give_the_base_package_and_are_sent(self):
        for label, data in generated_tables():
            with self.subTest(label):
                inflated, stored = deflation(data)
                # the positive control: the rule this repair removed refused exactly these (past 1 MiB, over 100-fold)
                self.assertGreater(inflated, MIB)
                self.assertGreater(inflated, 100 * stored)
                package, removed = docx_package._safe_package(data)
                self.assertEqual(package, legacy_safe_package(data))  # the package the base revision makes
                self.assertEqual(removed, {'fields': 0, 'objects': 0, 'controls': 0, 'chunks': 0})
                # through the conversion as the worker runs it: LibreOffice's stand-in is given the base's package
                self.assertEqual(document.convert_docx(data, runner=_echo_package),
                                 CONVERTED + legacy_safe_package(data))
                revision = SimpleNamespace(kind=SourceRevision.UPLOAD, pasted_text='', source_file=SimpleNamespace(
                    media_type=DOCX, sha256='0' * 64, original_name='synthetic-flowsheet.docx'))
                prepared = document.prepare(revision, converter=lambda word: document.convert_docx(
                    word, runner=_echo_package), reader=lambda source: data)
                self.assertEqual((prepared.kind, prepared.data), ('docx', CONVERTED + legacy_safe_package(data)))

    def test_the_absolute_limits_still_refuse_before_any_part_is_read(self):
        too_large = zero_parts(docx_package.MAX_PART_BYTES + 1)
        too_much = zero_parts(22 * MIB, 22 * MIB, 22 * MIB)  # each part within its limit, 66 MiB in all
        for data, said in ((too_large, 'a part is too large once inflated'),
                           (too_much, 'its parts are too large once inflated')):
            with self.subTest(said), \
                    mock.patch.object(docx_package, '_read_part', side_effect=AssertionError('a part was read')) as read:
                self.assertLess(len(data), MIB)  # a small upload that says it inflates past the limits
                with self.assertRaises(docx_package.PackageRefused) as caught:
                    docx_package.safe_package(data)
                self.assertIn(said, str(caught.exception))
                read.assert_not_called()
        # the control: a part of exactly MAX_PART_BYTES, 1,000-fold, is taken as the base takes it - the limit
        # refuses, not the ratio
        at_limit = zero_parts(docx_package.MAX_PART_BYTES)
        inflated, stored = deflation(at_limit, 'customXml/item1.xml')
        self.assertGreater(inflated, 100 * stored)
        self.assertEqual(docx_package.safe_package(at_limit), legacy_safe_package(at_limit))

    def test_a_size_header_that_lies_is_still_refused_for_a_generated_table(self):
        data = generated_tables()[0][1]
        real = parts_of(data)['word/document.xml']
        short = lying(data, 'word/document.xml', 1000, crc_of=real[:1000])  # says 1,000 bytes; holds 1.2 MB
        long = lying(data, 'word/document.xml', len(real) + 50)  # says 50 bytes more than it holds
        for lie, said in ((short, 'a part cannot be read'), (long, 'a part is not the size its header says')):
            with self.subTest(said), self.assertRaises(docx_package.PackageRefused) as caught:
                docx_package.safe_package(lie)
            self.assertIn(said, str(caught.exception))

    def test_a_part_read_as_xml_is_held_to_the_size_limits_only_whatever_its_name(self):
        def header_named_as_a_picture(inner):
            header = f'<?xml version="1.0" encoding="UTF-8"?>\n<w:hdr {NAMESPACES}>{inner}</w:hdr>'
            return word_package(TEXT, [relationship('rIdHeader', 'image', 'media/picture.png')],
                                parts=[('word/media/picture.png', header)])
        kept = header_named_as_a_picture(paragraph(complex_field(' PAGE ', '1')) * 9000)
        inflated, stored = deflation(kept, 'word/media/picture.png')
        self.assertGreater(inflated, max(MIB, 100 * stored))  # the positive control: refused before this repair
        self.assertEqual(docx_package.safe_package(kept), legacy_safe_package(kept))  # read, nothing to remove
        removed = header_named_as_a_picture(paragraph(complex_field(' PAGE ', '1')) * 9000
                                            + paragraph(complex_field(DANGEROUS['INCLUDETEXT'])))
        package, counts = docx_package._safe_package(removed)
        self.assertEqual(counts['fields'], 1)
        self.assertNotIn(b'secret', parts_of(package)['word/media/picture.png'])
