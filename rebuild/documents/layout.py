"""Output-layout safeguards applied to an exported DOCX, and nothing else.

⚠️ THE ORIGINAL TEMPLATE IS NEVER TOUCHED. These properties are added to the EXPORT on its way out. The
customer's uploaded original keeps its own bytes and its own sha256; that is what makes it the original.

⚠️ WHY THIS IS NOT A REPEATING HEADER ROW, WHICH IS THE OBVIOUS FIX AND IS WRONG HERE. Word repeats a row
marked `<w:tblHeader/>` at the top of every page a table continues onto — but only rows at the TOP of the
table, and it repeats them VERBATIM. The WM IOV measurement table carries TWO section headings in one
table: `** Right Leg **` at row 0 and `** Left Leg **` at row 14, each followed by its own measurements.
Marking row 0 as a repeating header would therefore print `** Right Leg **` above the LEFT leg's
measurements on any page the table reaches that far — a caption that is not merely unhelpful but actively
wrong about which limb the numbers describe. On a vascular report that is the one mistake worth avoiding
above all others, so the repeating header is deliberately NOT used.

What is used instead keeps every heading on the same page as the values it labels:

  · `<w:cantSplit/>` on every row, so a row never breaks across a page boundary mid-height;
  · `<w:keepNext/>` on every paragraph of a SECTION HEADING row, which binds that row to the row after it,
    so a heading can never be the last thing on a page with its measurements overleaf;
  · `<w:keepNext/>` on the non-empty paragraphs immediately preceding the table, so the table's title
    travels with the table.

⚠️ AND THE HONEST LIMIT, STATED RATHER THAN IMPLIED: OOXML has no way to make a repeated heading read
"(continued)" on later pages only — a repeated row is the same row. So continuation pages are labelled the
only way that is both possible and correct: each section heading is guaranteed to appear on the page where
its own measurements begin. A page never shows measurements whose heading is on a different page.

A heading row is identified by CONTENT, not by index: the columns beyond the first repeat the table's own
first-row column captions. In the WM IOV table that matches row 0 and row 14 and no measurement row,
because a filled measurement cell holds a number. A document with no such table is returned unchanged.
"""
import re
import shutil
import zipfile

DOCUMENT = 'word/document.xml'
ROW = re.compile(r'<w:tr(?:\s[^>]*)?>.*?</w:tr>', re.S)
CELL = re.compile(r'<w:tc>.*?</w:tc>', re.S)
TEXT = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', re.S)
PARAGRAPH = re.compile(r'<w:p(?:\s[^>]*)?>.*?</w:p>', re.S)
TABLE = re.compile(r'<w:tbl>.*?</w:tbl>', re.S)
# How many paragraphs before a table are treated as its title. The WM IOV title sits directly above it;
# a larger window would start binding unrelated body text to the table.
TITLE_PARAGRAPHS = 2


def _text(fragment):
    """The visible text of a fragment. `<w:t>` EXACTLY — `<w:t[^>]*>` also matches `<w:tcW>`."""
    return ' '.join(''.join(TEXT.findall(fragment)).split())


def _columns(row):
    return [_text(cell) for cell in CELL.findall(row)]


def _with_row_property(row, element):
    """Add one `<w:trPr>` child, creating the properties block if the row has none."""
    if element in row:
        return row
    if '<w:trPr>' in row:
        return row.replace('<w:trPr>', '<w:trPr>' + element, 1)
    opening = re.match(r'<w:tr(?:\s[^>]*)?>', row).group(0)
    return row.replace(opening, opening + '<w:trPr>' + element + '</w:trPr>', 1)


def _with_keep_next(paragraph):
    """Add `<w:keepNext/>` to one paragraph, creating `<w:pPr>` if absent."""
    if '<w:keepNext' in paragraph:
        return paragraph
    if '<w:pPr>' in paragraph:
        return paragraph.replace('<w:pPr>', '<w:pPr><w:keepNext/>', 1)
    opening = re.match(r'<w:p(?:\s[^>]*)?>', paragraph).group(0)
    return paragraph.replace(opening, opening + '<w:pPr><w:keepNext/></w:pPr>', 1)


def _keep_paragraphs_together(fragment):
    return PARAGRAPH.sub(lambda m: _with_keep_next(m.group(0)), fragment)


def _repair_table(table):
    rows = ROW.findall(table)
    if len(rows) < 2:
        return table, 0
    captions = _columns(rows[0])[1:]
    # A table whose first row has no column captions has no heading shape to preserve.
    if not captions or not any(captions):
        return table, 0
    headings = 0
    for row in rows:
        repaired = _with_row_property(row, '<w:cantSplit/>')
        if _columns(row)[1:] == captions:
            repaired = _keep_paragraphs_together(repaired)
            headings += 1
        if repaired != row:
            table = table.replace(row, repaired, 1)
    return table, headings


def _repair_title(document, table):
    """Bind the paragraphs immediately above a table to it, so the title cannot orphan."""
    start = document.index(table)
    before = document[:start]
    paragraphs = PARAGRAPH.findall(before)[-TITLE_PARAGRAPHS:]
    for paragraph in paragraphs:
        if not _text(paragraph):
            continue                                  # a spacer paragraph is not a title
        document = document.replace(paragraph, _with_keep_next(paragraph), 1)
    return document


def apply_table_continuation(document_xml):
    """Return the repaired `word/document.xml` and a summary of what changed."""
    repaired, headings, tables = document_xml, 0, 0
    for table in TABLE.findall(document_xml):
        fixed, found = _repair_table(table)
        if found:
            repaired = _repair_title(repaired, table)
        if fixed != table:
            repaired = repaired.replace(table, fixed, 1)
            tables += 1
        headings += found
    return repaired, {'tables': tables, 'heading_rows': headings}


def repair_export(path):
    """Rewrite one exported DOCX in place with the layout safeguards. Returns the summary.

    Every other part is copied byte for byte: only `word/document.xml` is rewritten, so headers, footers,
    styles, numbering and embedded media are the same bytes that came out of the processor.
    """
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if DOCUMENT not in names:
            return {'tables': 0, 'heading_rows': 0}
        original = archive.read(DOCUMENT).decode('utf-8')
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    repaired, summary = apply_table_continuation(original)
    if repaired == original:
        return summary
    temporary = path.with_name(path.name + '.layout')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as out:
        for info, payload in entries:
            out.writestr(info, repaired.encode('utf-8') if info.filename == DOCUMENT else payload)
    shutil.move(str(temporary), str(path))
    return summary
