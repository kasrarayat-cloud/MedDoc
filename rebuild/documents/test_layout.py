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

    def test_no_row_may_split_across_a_page(self):
        target, _ = self.repaired(ORIGINAL)
        xml = document(target)
        self.assertEqual(len(ROW.findall(xml)), xml.count('<w:cantSplit/>'),
                         'some rows can still break across a page boundary')

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

    def test_no_repeating_header_row_is_added(self):
        """⚠️ THE OBVIOUS FIX IS THE WRONG ONE HERE, AND THIS PINS THAT DECISION. Word repeats a
        `<w:tblHeader/>` row verbatim, and this table holds TWO sections. Repeating row 0 would print
        `** Right Leg **` above the LEFT leg's measurements — a caption that is wrong about which limb the
        numbers describe."""
        target, _ = self.repaired(ORIGINAL)
        self.assertNotIn('<w:tblHeader', document(target))

    def test_not_one_visible_character_changes(self):
        for source in self.documents_under_test():
            target, _ = self.repaired(source)
            self.assertEqual(visible(document(source)), visible(document(target)), source.name)

    def test_paragraph_and_control_counts_are_preserved(self):
        """The independent verifier compares these; a layout pass that moved them would fail parity."""
        for source in self.documents_under_test():
            target, _ = self.repaired(source)
            before, after = document(source), document(target)
            for pattern in (r'<w:p(?:\s[^>]*)?>', r'<w:sdt>', r'<w:tr(?:\s[^>]*)?>', r'<w:tc>'):
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
