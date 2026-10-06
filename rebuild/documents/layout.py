"""Output-only DOCX pagination safeguards; originals are never rewritten.

The qualified WM IOV table contains two limbs in one original table. Preserve
that table and its physical row destinations. Keep-with-next binds each original
section heading to its first numeric row. Do not invent a repeating header: a
single table cannot switch its repeated first-row header to the later limb.
The six mapped free-text location rows may span pages. Their answers can exceed
one page; forbidding a split cannot keep such a row together. Numeric rows and
headings remain indivisible. Existing header properties and unrelated tables
are untouched. Already separate 14-row limb tables retain their existing
independent repeated-header behavior.

These properties express layout intent. Native Microsoft Word appearance still
requires opening the real application exports; XML checks are not that evidence.
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
WM_CAPTIONS = ['DIAMETER (mm)', 'REFLUX TIME (ms)']
WM_LIMBS = ('** Right Leg **', '** Left Leg **')
WM_NUMERIC_ROWS = ['GSV at the SFJ', 'GSV at the Proximal Thigh', 'GSV at the Knee',
                   'GSV Below Knee', 'SSV at the SPJ', 'SSV at the Proximal Calf',
                   'AAGSV at the SFJ', 'AAGSV at the Proximal Thigh', 'PAGSV at the SFJ',
                   'PAGSV at the Proximal Thigh']
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


def _wm_sections(rows):
    """Return only the exact WM limb sections, never guess from a generic table."""
    columns = [_columns(row) for row in rows]
    if (len(rows) not in (14, 28) or not all(len(value) == 3 for value in columns)
            or any([columns[start + i][0] for i in range(1, 11)] != WM_NUMERIC_ROWS
                   for start in range(0, len(rows), 14))
            or any(not columns[start + i][0].startswith('Saphenous Tributary Vein ')
                   for start in range(0, len(rows), 14) for i in (11, 12, 13))):
        return None
    if len(rows) == 28 and all(len(value) == 3 for value in columns):
        if (columns[0] == [WM_LIMBS[0], *WM_CAPTIONS]
                and columns[14] == [WM_LIMBS[1], *WM_CAPTIONS]
                and [i for i, value in enumerate(columns)
                     if value[1:] == WM_CAPTIONS] == [0, 14]):
            return [rows[:14], rows[14:]]
    # Re-entry over an already split export must not change it again.
    if (len(rows) == 14 and all(len(value) == 3 for value in columns)
            and columns[0][0] in WM_LIMBS and columns[0][1:] == WM_CAPTIONS
            and not any(value[1:] == WM_CAPTIONS for value in columns[1:])):
        return [rows]
    return None


def _repair_table(table):
    rows = ROW.findall(table)
    if len(rows) < 2:
        return table, 0
    sections = _wm_sections(rows)
    if not sections:
        return table, 0
    first = table.index(rows[0])
    last = table.rindex(rows[-1]) + len(rows[-1])
    if table[first:last] != ''.join(rows):
        # Do not drop inter-row bookmarks/ranges in an unqualified table shape.
        return table, 0
    captions = WM_CAPTIONS
    headings = 0
    replacements = []
    for index, row in enumerate(rows):
        if index % 14 in (11, 12, 13):
            # Original free-text location answers have no one-page length bound.
            # On an over-height cantSplit row some renderers omit the header at
            # the forced break. Let these rows flow beneath their limb header.
            repaired = re.sub(r'<w:cantSplit(?:\s[^>]*)?\s*/>', '', row)
        else:
            repaired = _with_row_property(row, '<w:cantSplit/>')
        if _columns(row)[1:] == captions:
            repaired = _keep_paragraphs_together(repaired)
            headings += 1
            if len(rows) == 14:
                repaired = _with_row_property(repaired, '<w:tblHeader/>')
        replacements.append(repaired)
    # Preserve the original table boundary and native table/row coordinates.
    # Splitting a 28-row original made left-limb saved destinations unreadable
    # by their source-bound row numbers. No post-export recombination is used.
    for row, replacement in zip(rows, replacements):
        table = table.replace(row, replacement, 1)
    return table, headings


def _repair_title(document, table):
    """Bind only contiguous body paragraphs, never cells of a preceding table."""
    start = document.index(table)
    before = document[:start]
    end = len(before)
    replacements = []
    for match in reversed(list(PARAGRAPH.finditer(before))):
        if before[match.end():end].strip():
            break
        replacements.append(match)
        end = match.start()
        if len(replacements) == TITLE_PARAGRAPHS:
            break
    for match in replacements:  # reverse positions preserve earlier offsets
        paragraph = match.group(0)
        if _text(paragraph):
            before = before[:match.start()] + _with_keep_next(paragraph) + before[match.end():]
    return before + document[start:]


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
        comment = archive.comment
    repaired, summary = apply_table_continuation(original)
    if repaired == original:
        return summary
    temporary = path.with_name(path.name + '.layout')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as out:
        out.comment = comment
        for info, payload in entries:
            out.writestr(info, repaired.encode('utf-8') if info.filename == DOCUMENT else payload)
    shutil.move(str(temporary), str(path))
    return summary
