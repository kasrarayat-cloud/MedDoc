"""The export's output-layout safeguards, against the real customer template and real exports.

These are STRUCTURAL tests. They prove what the file says; they do not prove what Microsoft Word draws.
Native Word verification is a separate, still-open step and nothing here substitutes for it.
"""
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from . import layout

# ⚠️ THE ORIGINAL IS THE TRACKED FIXTURE AT THE REPOSITORY ROOT, NOT A COPY UNDER `.runtime`. `.runtime`
# is private to one host, so tests keyed to it SKIP in CI — and a whole suite that skips is a gate that
# passes without measuring anything. Its sha256 is pinned to the same value `wm_qualification` accepts, so
# a swapped fixture fails loudly instead of being quietly measured.
ORIGINAL = Path(__file__).resolve().parents[2] / 'WM IOV Template.docx'
ORIGINAL_SHA256 = 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
# A real EXPORT, when this host happens to hold one. Optional by design: it adds parity coverage against a
# filled document, and its absence must not silence the checks above.
FRESH = Path('/opt/meddoc-pro/rebuild/.runtime/word-review-package/quillmd-word-review-20260918'
             '/02-fresh-export-live-absent-scenario.docx')
TEXT = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', re.S)
ROW = re.compile(r'<w:tr(?:\s[^>]*)?>.*?</w:tr>', re.S)


def document(path):
    return zipfile.ZipFile(path).read('word/document.xml').decode('utf-8')


def visible(xml):
    return ''.join(TEXT.findall(xml))


class TheMeasurementTableKeepsItsHeadingsWithItsValues(unittest.TestCase):
    """The reported defect: the table title and the right-leg column headings sat on page 1 while the
    measurements began on page 2."""

    @classmethod
    def setUpClass(cls):
        import hashlib
        if not ORIGINAL.is_file():
            raise AssertionError('The tracked WM IOV original is missing: %s' % ORIGINAL)
        digest = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
        if digest != ORIGINAL_SHA256:
            raise AssertionError('The tracked original is not the accepted fixture (%s)' % digest)
        cls.filled = [FRESH] if FRESH.is_file() else []

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='layout-'))
        self.addCleanup(shutil.rmtree, self.work, True)

    def documents_under_test(self):
        """The tracked original always; a real export as well when this host holds one."""
        return [ORIGINAL] + self.filled

    def repaired(self, source):
        target = self.work / source.name
        shutil.copy(source, target)
        return target, layout.repair_export(target)

    def test_the_original_template_has_no_safeguards_which_is_why_the_export_adds_them(self):
        """⚠️ THE STARTING CONDITION, ASSERTED SO THE REPAIR IS NOT MEASURED AGAINST ITSELF. If the
        template ever gains its own safeguards this test fails, and the export-side repair should then be
        reconsidered rather than silently doubled up."""
        xml = document(ORIGINAL)
        self.assertNotIn('<w:tblHeader', xml, 'the template already repeats a header row')
        self.assertNotIn('<w:cantSplit', xml, 'the template already prevents row splitting')
        table = re.search(r'<w:tbl>.*?</w:tbl>', xml, re.S).group(0)
        self.assertNotIn('<w:keepNext', table, 'the template already binds its heading rows')

    def test_both_section_headings_are_bound_to_the_rows_they_label(self):
        target, summary = self.repaired(ORIGINAL)
        self.assertEqual(summary, {'tables': 1, 'heading_rows': 2},
                         'the two section headings were not both found')
        rows = ROW.findall(document(target))
        bound = [i for i, row in enumerate(rows) if '<w:keepNext' in row]
        self.assertEqual(bound, [0, 14], 'keepNext landed on rows other than the two section headings')

    def test_the_headings_are_found_by_content_not_by_row_number(self):
        """Row 0 and row 14 are where they happen to be today. The rule is that a heading row repeats the
        table's own column captions, which a filled measurement row never does."""
        rows = ROW.findall(document(ORIGINAL))
        captions = [layout._text(c) for c in layout.CELL.findall(rows[0])][1:]
        self.assertEqual(captions, ['DIAMETER (mm)', 'REFLUX TIME (ms)'])
        matching = [i for i, row in enumerate(rows)
                    if [layout._text(c) for c in layout.CELL.findall(row)][1:] == captions]
        self.assertEqual(matching, [0, 14])

    def test_numeric_rows_and_headers_stay_together_while_long_location_rows_can_flow(self):
        target, _ = self.repaired(ORIGINAL)
        xml = document(target)
        rows = ROW.findall(xml)
        self.assertEqual(len(rows), 28)
        for index, row in enumerate(rows):
            self.assertEqual('<w:cantSplit' in row, index % 14 not in (11, 12, 13))

    def test_the_table_title_travels_with_the_table(self):
        target, _ = self.repaired(ORIGINAL)
        xml = document(target)
        table_at = xml.index('<w:tbl>')
        preceding = re.findall(r'<w:p(?:\s[^>]*)?>.*?</w:p>', xml[:table_at], re.S)
        titled = [p for p in preceding[-layout.TITLE_PARAGRAPHS:] if layout._text(p)]
        self.assertTrue(titled, 'there is no title paragraph above the table to bind')
        for paragraph in titled:
            self.assertIn('<w:keepNext', paragraph, 'the table title can still orphan above a page break')

    def test_a_spacer_paragraph_above_the_table_is_not_treated_as_a_title(self):
        target, _ = self.repaired(ORIGINAL)
        xml = document(target)
        preceding = re.findall(r'<w:p(?:\s[^>]*)?>.*?</w:p>', xml[:xml.index('<w:tbl>')], re.S)
        for paragraph in preceding[-layout.TITLE_PARAGRAPHS:]:
            if not layout._text(paragraph):
                self.assertNotIn('<w:keepNext', paragraph, 'an empty spacer was bound to the table')

    # ---- what the repair must NOT do ------------------------------------------------------------

    def test_the_original_single_table_and_both_physical_section_headings_survive(self):
        """The uploaded source appoints table/row destinations. A layout repair
        cannot split that table just to synthesize per-limb repetition."""
        target, _ = self.repaired(ORIGINAL)
        tables = layout.TABLE.findall(document(target))
        self.assertEqual(len(tables), 1)
        rows = ROW.findall(tables[0])
        self.assertEqual(len(rows), 28)
        for index, limb in ((0, layout.WM_LIMBS[0]), (14, layout.WM_LIMBS[1])):
            self.assertEqual(layout._columns(rows[index]), [limb, *layout.WM_CAPTIONS])
            self.assertIn('<w:keepNext', rows[index])
        self.assertNotIn('<w:tblHeader', tables[0], 'the original appoints no repeating first-row header')

    def test_existing_header_properties_on_the_single_table_are_retained(self):
        original = document(ORIGINAL)
        rows = ROW.findall(original)
        marked = layout._with_row_property(rows[0], '<w:tblHeader w:val="0"/>')
        source = original.replace(rows[0], marked, 1)
        exported, _ = layout.apply_table_continuation(source)
        self.assertEqual(len(layout.TABLE.findall(exported)), 1)
        self.assertIn('<w:tblHeader w:val="0"/>', ROW.findall(exported)[0])
        self.assertEqual(exported.count('<w:tblHeader'), 1)

    def test_an_original_fourteen_row_table_retains_its_existing_header_behavior(self):
        original = document(ORIGINAL)
        table = layout.TABLE.findall(original)[0]
        rows = ROW.findall(table)
        for start in (0, 14):
            with self.subTest(limb=start):
                standalone = table[:table.index(rows[0])] + ''.join(rows[start:start + 14]) + table[table.rindex(rows[-1]) + len(rows[-1]):]
                source = original.replace(table, standalone, 1)
                exported, _ = layout.apply_table_continuation(source)
                fixed = layout.TABLE.findall(exported)
                self.assertEqual(len(fixed), 1)
                self.assertEqual(len(ROW.findall(fixed[0])), 14)
                self.assertEqual([i for i, row in enumerate(ROW.findall(fixed[0])) if '<w:tblHeader' in row], [0])

    def test_not_one_visible_character_changes(self):
        for source in self.documents_under_test():
            target, _ = self.repaired(source)
            self.assertEqual(visible(document(source)), visible(document(target)), source.name)

    def test_paragraph_and_control_counts_are_preserved(self):
        """The independent verifier compares these; a layout pass that moved them would fail parity."""
        for source in self.documents_under_test():
            target, _ = self.repaired(source)
            before, after = document(source), document(target)
            self.assertEqual(len(re.findall(r'<w:p(?:\s[^>]*)?>', after)),
                             len(re.findall(r'<w:p(?:\s[^>]*)?>', before)),
                             'no synthetic separator paragraph may change the original structure')
            for pattern in (r'<w:sdt>', r'<w:tr(?:\s[^>]*)?>', r'<w:tc>'):
                self.assertEqual(len(re.findall(pattern, before)), len(re.findall(pattern, after)),
                                 '%s changed %s' % (source.name, pattern))

    def test_every_other_part_of_the_package_is_byte_identical(self):
        """Headers, footers, styles, numbering and embedded media must be the same bytes."""
        for source in self.documents_under_test():
            target, _ = self.repaired(source)
            a, b = zipfile.ZipFile(source), zipfile.ZipFile(target)
            self.assertEqual(sorted(a.namelist()), sorted(b.namelist()), source.name)
            changed = [n for n in a.namelist() if n != 'word/document.xml' and a.read(n) != b.read(n)]
            self.assertEqual(changed, [], '%s: %s' % (source.name, changed))

    def test_original_archive_comment_is_retained_on_changed_exports(self):
        for number, comment in enumerate((b'', b'Original customer archive comment', b'\x00\xff\x80')):
            with self.subTest(comment=comment):
                target = self.work / ('archive-comment-%d.docx' % number)
                with zipfile.ZipFile(ORIGINAL) as original, zipfile.ZipFile(target, 'w') as output:
                    output.comment = comment
                    for item in original.infolist():
                        output.writestr(item, original.read(item.filename))
                before = target.read_bytes()
                self.assertEqual(layout.repair_export(target), {'tables': 1, 'heading_rows': 2})
                with zipfile.ZipFile(target) as exported:
                    self.assertEqual(exported.comment, comment)
                # Re-entering the corrected export is a byte-identical no-op.
                corrected = target.read_bytes()
                layout.repair_export(target)
                self.assertEqual(target.read_bytes(), corrected)
                self.assertNotEqual(before, corrected)

    def test_the_uploaded_original_on_disk_is_never_modified(self):
        """The repair runs on the EXPORT. The customer's original keeps its own bytes and its own hash."""
        import hashlib
        before = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
        self.repaired(ORIGINAL)
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(), before)

    def test_applying_it_twice_changes_nothing_further(self):
        """The export seam must be safe to re-enter; a second pass must not stack duplicate properties."""
        target, first = self.repaired(ORIGINAL)
        once = document(target)
        second = layout.repair_export(target)
        self.assertEqual(document(target), once, 'a second pass altered the document')
        self.assertEqual(second['heading_rows'], first['heading_rows'])

    def test_a_document_with_no_qualifying_table_is_returned_unchanged(self):
        """A no-op by construction, so the pass cannot damage an unrelated export."""
        plain = self.work / 'plain.docx'
        with zipfile.ZipFile(ORIGINAL) as source, zipfile.ZipFile(plain, 'w') as out:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename == 'word/document.xml':
                    payload = re.sub(r'<w:tbl>.*?</w:tbl>', b''.decode(), payload.decode('utf-8'),
                                     flags=re.S).encode('utf-8')
                out.writestr(info, payload)
        before = plain.read_bytes()
        summary = layout.repair_export(plain)
        self.assertEqual(summary, {'tables': 0, 'heading_rows': 0})
        self.assertEqual(plain.read_bytes(), before, 'a table-free document was rewritten')

    def test_an_unrelated_table_with_similar_captions_is_not_modified(self):
        xml = document(ORIGINAL)
        for old, new in [('** Right Leg **', '** Right Arm **'),
                         ('REFLUX TIME (ms)', 'REFLUX TIME (seconds)'),
                         ('GSV at the SFJ', 'A different numeric question')]:
            other = xml.replace(old, new)
            repaired, summary = layout.apply_table_continuation(other)
            self.assertEqual(repaired, other)
            self.assertEqual(summary, {'tables': 0, 'heading_rows': 0})

    def test_inter_row_markup_is_preserved_by_refusing_to_restructure_it(self):
        original = document(ORIGINAL)
        rows = ROW.findall(original)
        other = original.replace(rows[0], rows[0] + '<w:bookmarkStart w:id="900" w:name="x"/>', 1)
        repaired, summary = layout.apply_table_continuation(other)
        self.assertEqual(repaired, other)
        self.assertEqual(summary, {'tables': 0, 'heading_rows': 0})

    def test_the_original_last_cells_are_not_bound_to_unrelated_following_text_on_reentry(self):
        target, _ = self.repaired(ORIGINAL)
        xml = document(target)
        first = layout.TABLE.findall(xml)[0]
        self.assertNotIn('<w:keepNext', ROW.findall(first)[-1])
        fixed, _ = layout.apply_table_continuation(xml)
        self.assertEqual(fixed, xml)

    def test_all_native_answer_cells_keep_original_table_and_row_destinations(self):
        from lxml import etree
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        original = etree.fromstring(document(ORIGINAL).encode())
        table = original.find('w:body/w:tbl', ns)
        rows = table.findall('w:tr', ns)
        answers = {}
        for section in (0, 14):
            for offset in range(1, 14):
                for column in (range(3) if offset >= 11 else (1, 2)):
                    # A source-shaped synthetic processor output, before the
                    # layout seam. Location captions remain in their own cell.
                    cell = rows[section + offset].findall('w:tc', ns)[column]
                    paragraph = cell.find('w:p', ns)
                    run = etree.SubElement(paragraph, '{%s}r' % ns['w'])
                    value = ('location %d/%d ' % (section + offset, column) + 'long answer; ' * 500
                             if offset >= 11 else '%d.%d' % (section + offset, column))
                    etree.SubElement(run, '{%s}t' % ns['w']).text = value
                    answers[(section + offset, column)] = value
        self.assertEqual(len(answers), 58)
        source = etree.tostring(original).decode()
        exported, summary = layout.apply_table_continuation(source)
        self.assertEqual(summary, {'tables': 1, 'heading_rows': 2})
        result = etree.fromstring(exported.encode())
        tables = result.findall('w:body/w:tbl', ns)
        self.assertEqual(len(tables), 1)
        final_rows = tables[0].findall('w:tr', ns)
        self.assertEqual(len(final_rows), 28)
        for index, row in enumerate(rows):
            for column, cell in enumerate(row.findall('w:tc', ns)):
                current = final_rows[index].findall('w:tc', ns)[column]
                self.assertEqual(cell.xpath('.//w:t/text()', namespaces=ns),
                                 current.xpath('.//w:t/text()', namespaces=ns), (index, column))
                if (index, column) in answers:
                    self.assertIn(answers[(index, column)], ''.join(current.xpath('.//w:t/text()', namespaces=ns)))
        # The retained native reader uses these source row indices directly.
        self.assertEqual(layout._columns(ROW.findall(exported)[14]), [layout.WM_LIMBS[1], *layout.WM_CAPTIONS])
        self.assertIn(answers[(15, 1)], ''.join(final_rows[15].findall('w:tc', ns)[1].xpath('.//w:t/text()', namespaces=ns)))
        self.assertEqual(len(original.findall('.//w:sdt', ns)), len(result.findall('.//w:sdt', ns)))

    def test_long_location_text_and_numeric_cells_are_unchanged(self):
        original = document(ORIGINAL)
        rows = ROW.findall(original)
        long_row = rows[11].replace('Saphenous Tributary Vein',
                                  'Saphenous Tributary Vein ' + 'mapped location; ' * 1200)
        stressed = original.replace(rows[11], long_row, 1)
        result, _ = layout.apply_table_continuation(stressed)
        self.assertEqual(visible(stressed), visible(result))
        self.assertNotIn('<w:cantSplit', ROW.findall(result)[11])
        self.assertEqual(len(ROW.findall(result)), 28)



class TheExportSeamAppliesIt(unittest.TestCase):
    def test_the_docx_export_path_calls_the_repair_before_the_file_is_hashed(self):
        """⚠️ A LAYOUT PASS THE EXPORT DOES NOT CALL IS A MODULE, NOT A REPAIR. And it must run before the
        caller hashes the output, or `export_sha256` would describe bytes that were never stored."""
        import inspect
        from . import service
        source = inspect.getsource(service._run)
        self.assertIn('repair_export', source)
        self.assertLess(source.index('repair_export'), source.index('os.open(target'),
                        'the layout pass runs after the export file is opened for writing')


if __name__ == '__main__':
    unittest.main()
