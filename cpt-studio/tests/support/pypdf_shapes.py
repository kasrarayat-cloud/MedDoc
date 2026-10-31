"""The shapes pypdf 6.21.4 reads differently from 6.21.2 (ACCURACY-RESIDUALS.md, "pypdf 6.21.4"), built as bytes.

Every document is synthetic: fictional text written here in raw PDF syntax, with zlib and, for the producer route of
TXT-2, ReportLab. Nothing is read from disk and no pypdf writer is used, so a builder means the same bytes under any
pypdf version. ``SHAPES`` names each one by its residual row; the tests in test_repairs_gi4_pypdf.py read them through
the real extraction child, and the measurement scripts of the round read the same bytes under both pypdf versions.

Importable without Django.
"""
from __future__ import annotations

import hashlib
import struct
import zlib

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'
NOTE = [BANNER, 'Date of service: 2026-10-21', 'Procedure: Colonoscopy to the cecum.',
        'Findings: A 6 mm sigmoid polyp was seen.', 'Interventions:']
NOTE_TEXT = '\n'.join(NOTE)
HELVETICA = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
SNARE = 'Cold snare polypectomy of the sigmoid polyp'


# --- syntax -------------------------------------------------------------------------------------------------------

def esc(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def stream(data: bytes | str, extra: str = '') -> bytes:
    raw = data.encode('latin-1') if isinstance(data, str) else data
    return f'<< {extra} /Length {len(raw)} >>\nstream\n'.encode() + raw + b'\nendstream'


def flate(data: bytes | str, extra: str = '') -> bytes:
    raw = zlib.compress(data.encode('latin-1') if isinstance(data, str) else data)
    return stream(raw, f'/Filter /FlateDecode {extra}')


def serialise(objects: dict[int, bytes], root: int = 1, trailer: str = '') -> bytes:
    """A complete one-revision PDF from numbered object bodies, with an exact cross-reference table."""
    out = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b'%d 0 obj\n' % number + objects[number] + b'\nendobj\n'
    size = max(objects) + 1
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size
    for number in range(1, size):
        out += b'%010d 00000 n \n' % offsets[number] if number in offsets else b'0000000000 65535 f \n'
    out += b'trailer\n<< /Size %d /Root %d 0 R %s >>\nstartxref\n%d\n%%%%EOF\n' % (size, root, trailer.encode(), xref)
    return bytes(out)


def lines(rows, x: int = 72, top: int = 740, step: int = 20, font: str = '/F1', size: int = 11) -> str:
    """One BT block per row of plain text in ``font``."""
    return '\n'.join(f'BT {font} {size} Tf {x} {top - step * index} Td ({esc(row)}) Tj ET'
                     for index, row in enumerate(rows))


def page_pdf(content: str | bytes, *, fonts: str = '/F1 4 0 R', extra: dict | None = None, annots: str = '',
             catalog: str = '', xobjects: str = '') -> bytes:
    """Objects 1-5: catalog, pages, page, Helvetica /F1, content. Extra objects from 6 up."""
    resources = f'/Font << {fonts} >>' + (f' /XObject << {xobjects} >>' if xobjects else '')
    objects = {1: f'<< /Type /Catalog /Pages 2 0 R {catalog} >>'.encode(),
               2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << {resources} >> '
                   f'/Contents 5 0 R {annots} >>').encode(),
               4: HELVETICA, 5: stream(content)}
    objects.update(extra or {})
    return serialise(objects)


def to_unicode(pairs=(), ranges=(), code_bytes: int = 2) -> bytes:
    """A ToUnicode CMap: bfchar (code, text) pairs and bfrange (low, high, first) ranges."""
    width = 2 * code_bytes
    low, high = '0' * width, 'F' * width
    body = f'1 begincodespacerange\n<{low}> <{high}>\nendcodespacerange\n'
    if pairs:
        entries = '\n'.join(f'<{code:0{width}X}> <{text.encode("utf-16-be", "surrogatepass").hex().upper()}>'
                            for code, text in pairs)
        body += f'{len(pairs)} beginbfchar\n{entries}\nendbfchar\n'
    if ranges:
        entries = '\n'.join(f'<{a:0{width}X}> <{b:0{width}X}> <{c:04X}>' for a, b, c in ranges)
        body += f'{len(ranges)} beginbfrange\n{entries}\nendbfrange\n'
    return stream('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry '
                  '(Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Synthetic-UCS def\n/CMapType 2 def\n'
                  + body + 'endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n')


IDENTITY_RANGE = ((0x0000, 0x00FF, 0x0000),)  # a subset font's ToUnicode: its codes are their characters


def composite(base: str = 'ABCDEF+SyntheticSans', *, encoding: str = '/Identity-H', to_unicode_ref: str = '',
              descendant: int, descriptor: int, widths: str = '', ordering: str = 'Identity',
              cid_type: str = 'CIDFontType2', cid_to_gid: str = '/CIDToGIDMap /Identity') -> dict:
    """A Type0 font (returned as {descendant: ..., descriptor: ...} plus the font itself under key 0)."""
    return {0: (f'<< /Type /Font /Subtype /Type0 /BaseFont /{base} /Encoding {encoding} /DescendantFonts '
                f'[{descendant} 0 R] {to_unicode_ref} >>').encode(),
            descendant: (f'<< /Type /Font /Subtype /{cid_type} /BaseFont /{base} /CIDSystemInfo << /Registry (Adobe) '
                         f'/Ordering ({ordering}) /Supplement 0 >> /FontDescriptor {descriptor} 0 R {cid_to_gid} '
                         f'/DW 500 {widths} >>').encode(),
            descriptor: (f'<< /Type /FontDescriptor /FontName /{base} /Flags 32 /FontBBox [0 -200 1000 900] '
                         '/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>').encode()}


def with_font(content: str, font: dict, number: int = 6, extra: dict | None = None, **kwargs) -> bytes:
    """``page_pdf`` with ``font`` (from ``composite`` or a simple font body under key 0) as /F2 = object ``number``."""
    objects = {number: font[0], **{key: value for key, value in font.items() if key}, **(extra or {})}
    return page_pdf(content, fonts=f'/F1 4 0 R /F2 {number} 0 R', extra=objects, **kwargs)


def identity_font(to_unicode_body: bytes | None = None, **kwargs) -> dict:
    """An Identity-H subset font (objects 6, 7 ToUnicode, 8 descendant, 9 descriptor)."""
    font = composite(descendant=8, descriptor=9, to_unicode_ref='/ToUnicode 7 0 R', **kwargs)
    font[7] = to_unicode_body if to_unicode_body is not None else to_unicode(ranges=IDENTITY_RANGE)
    return font


# --- annotations whose appearance pypdf reads -------------------------------------------------------------------

def annotated(appearance_ops: str, *, annotation: str = '/Subtype /Stamp', font: dict | None = None,
              acroform: bool = False, form_ops: str = '', pages: int = 1, layer_ops: str = '') -> bytes:
    """A page of ordinary text with one displayed annotation whose normal appearance (object 20) draws
    ``appearance_ops`` with /F9 (``font``, default an Identity-H subset font at 21-24). ``form_ops``: the appearance
    draws a nested form (object 25) holding them. ``pages`` > 1 adds plain pages before it; ``layer_ops`` adds a
    last page whose own content draws them in the same font."""
    font = font if font is not None else composite(descendant=23, descriptor=24, to_unicode_ref='/ToUnicode 22 0 R')
    if 22 not in font and b'/ToUnicode 22 0 R' in font[0]:
        font[22] = to_unicode(ranges=IDENTITY_RANGE)
    nested = '/XObject << /Fm1 25 0 R >>' if form_ops else ''
    objects = {20: stream(appearance_ops + ('\n/Fm1 Do' if form_ops else ''),
                          f'/Type /XObject /Subtype /Form /BBox [0 0 228 20] /Resources << /Font << /F9 21 0 R >> '
                          f'{nested} >>'),
               21: font[0], **{key: value for key, value in font.items() if key}}
    if form_ops:
        objects[25] = stream(form_ops, '/Type /XObject /Subtype /Form /BBox [0 0 228 20] /Resources << /Font '
                                       '<< /F9 21 0 R >> >>')
    widget = '/T (result) /FT /Tx' if acroform else ''
    objects[26] = (f'<< /Type /Annot {annotation} {widget} /Rect [72 480 300 500] /F 4 /AP << /N 20 0 R >> '
                   '>>').encode()
    kids, number = [], 30
    plain = stream(lines(NOTE))
    for index in range(pages - 1):
        objects[number] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R '
                           b'>> >> /Contents %d 0 R >>' % (number + 1))
        objects[number + 1] = plain
        kids.append(number)
        number += 2
    objects[3] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  b'/Contents 5 0 R /Annots [26 0 R] >>')
    kids.append(3)
    if layer_ops:
        objects[number] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R '
                           b'/F9 21 0 R >> >> /Contents %d 0 R >>' % (number + 1))
        objects[number + 1] = stream(lines(NOTE) + '\n' + layer_ops)
        kids.append(number)
    catalog = '/AcroForm << /Fields [26 0 R] >>' if acroform else ''
    objects[1] = f'<< /Type /Catalog /Pages 2 0 R {catalog} >>'.encode()
    objects[2] = f'<< /Type /Pages /Kids [{" ".join(f"{kid} 0 R" for kid in kids)}] /Count {len(kids)} >>'.encode()
    objects[4] = HELVETICA
    objects[5] = stream(lines(NOTE))
    return serialise(objects)


def shown(hex_codes: str) -> str:
    return f'BT /F9 10 Tf 2 5 Td <{hex_codes}> Tj ET'


# --- TXT-2: a predefined CMap pypdf does not implement -------------------------------------------------------------

CJK_TEXT = ['Colonoscopy with cold snare polypectomy.', 'Sessile polyp in the sigmoid colon removed.',
            'No complications. Synthetic note only.']
UNIMPLEMENTED_CMAPS = ('KSCms-UHC-H', '90msp-RKSJ-H', '90pv-RKSJ-H', '83pv-RKSJ-H', 'Add-RKSJ-H', 'Ext-RKSJ-H',
                       'EUC-H', 'KSC-EUC-H', 'KSCpc-EUC-H', 'KSCms-UHC-HW-H', 'B5pc-H', 'HKscs-B5-H', 'CNS-EUC-H',
                       'GBKp-EUC-H', 'UniJIS-UTF8-H')
IMPLEMENTED_CMAPS = ('90ms-RKSJ-H', 'GBK-EUC-H')


def cjk_page(cmap: str, *, odd: bool = True) -> bytes:
    """A page of ASCII text in a non-embedded CID font under the predefined CMap ``cmap``, as ReportLab's CIDFont
    writes it: each ASCII character one byte. ``odd``: every line has an odd byte count."""
    rows = [row if (len(row) % 2 == 1) == odd else row + ' ' for row in CJK_TEXT]
    font = composite('HYSMyeongJo-Medium', encoding=f'/{cmap}', descendant=8, descriptor=9, ordering='Korea1',
                     cid_type='CIDFontType0', cid_to_gid='')
    return with_font(lines(rows, font='/F2', size=12), font)


def beside_plain_page(content: str, font: dict) -> bytes:
    """Page 1 the plain note; page 2 the note and ``content`` drawn with /F2 (``font`` from ``composite``)."""
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R 10 0 R] /Count 2 >>',
               3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                   b'/Contents 5 0 R >>'),
               4: HELVETICA, 5: stream(lines(NOTE)),
               10: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 6 0 R '
                    b'>> >> /Contents 11 0 R >>'),
               11: stream(lines(NOTE) + '\n' + content), 6: font[0],
               **{key: value for key, value in font.items() if key}}
    return serialise(objects)


def reportlab_cjk(face: str, cmap: str, text: str) -> bytes:
    """The producer route: ReportLab's own CIDFont (a valid PDF it writes for these CMaps)."""
    import io  # noqa: PLC0415

    from reportlab.pdfbase import pdfmetrics  # noqa: PLC0415
    from reportlab.pdfbase.cidfonts import CIDFont  # noqa: PLC0415
    from reportlab.pdfgen import canvas  # noqa: PLC0415

    font = CIDFont(face, cmap)
    pdfmetrics.registerFont(font)
    out = io.BytesIO()
    page = canvas.Canvas(out, invariant=1)
    page.setFont(font.fontName, 12)
    for index, row in enumerate([text, 'Second synthetic line of the same note, no patient content.']):
        page.drawString(72, 720 - 20 * index, row)
    page.showPage()
    page.save()
    return out.getvalue()


# --- TXT-3, TXT-8, TXT-9, TXT-10: glyph names ----------------------------------------------------------------------

def differences_font(names: str, *, base: str = 'Helvetica', to_unicode_ref: str = '', font_file: str = '',
                     encoding: str | None = None, subtype: str = 'Type1') -> bytes:
    enc = encoding if encoding is not None else f'<< /Type /Encoding /Differences [{names}] >>'
    descriptor = f'/FontDescriptor {font_file}' if font_file else ''
    widths = '/FirstChar 32 /LastChar 255 /Widths [' + ' '.join(['556'] * 224) + ']' if font_file else ''
    return (f'<< /Type /Font /Subtype /{subtype} /BaseFont /{base} /Encoding {enc} {widths} {descriptor} '
            f'{to_unicode_ref} >>').encode()


def boxed(mark_codes: str, label: str = SNARE, brackets: bool = True) -> bytes:
    """Interventions, then '[' (Helvetica) + ``mark_codes`` (/F2) + ']' and ``label`` (Helvetica) on one line."""
    opening, closing = ('([) Tj ', f'(] {esc(label)}) Tj') if brackets else ('', f'( {esc(label)}) Tj')
    return f'{lines(NOTE)}\nBT /F1 11 Tf 72 620 Td {opening}/F2 11 Tf <{mark_codes}> Tj /F1 11 Tf {closing} ET'


def named_mark(name: str, *, brackets: bool = True, label: str = SNARE, to_unicode_body: bytes | None = None) -> bytes:
    """A mark drawn with code 0x41 of a text font whose /Differences names it ``name`` (no ToUnicode unless
    given), in printed brackets before ``label``."""
    names = f'65 /{name}' if name else ''
    ref = '/ToUnicode 7 0 R' if to_unicode_body is not None else ''
    extra = {7: to_unicode_body} if to_unicode_body is not None else {}
    return with_font(boxed('41', label, brackets), {0: differences_font(names, to_unicode_ref=ref)}, extra=extra)


def type1_program(entries: dict[int, str], name: str = 'SyntheticSerif') -> bytes:
    """A Type 1 font program's clear-text part with a built-in encoding (pypdf reads only the part before eexec)."""
    dups = '\n'.join(f'dup {code} /{glyph} put' for code, glyph in sorted(entries.items()))
    clear = (f'%!PS-AdobeFont-1.0: {name} 001.000\n/FontName /{name} def\n/Encoding 256 array\n'
             f'0 1 255 {{1 index exch /.notdef put}} for\n{dups}\nreadonly def\ncurrentfile eexec\n')
    return clear.encode('latin-1') + bytes(range(256)) * 4


def builtin_font(entries: dict[int, str], *, encoding: str = '', to_unicode_ref: str = '') -> dict:
    """A Type 1 font (object 6) with an embedded program (7: descriptor, 8: FontFile) whose built-in encoding is
    ``entries``; ``encoding``: the font dictionary's own /Encoding entry."""
    program = type1_program(entries)
    widths = '/FirstChar 32 /LastChar 255 /Widths [' + ' '.join(['556'] * 224) + ']'
    enc = f'/Encoding {encoding}' if encoding else ''
    return {0: (f'<< /Type /Font /Subtype /Type1 /BaseFont /ABCDEF+SyntheticSerif {enc} {widths} /FontDescriptor '
                f'7 0 R {to_unicode_ref} >>').encode(),
            7: (b'<< /Type /FontDescriptor /FontName /ABCDEF+SyntheticSerif /Flags 32 /FontBBox [0 -200 1000 900] '
                b'/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile 8 0 R >>'),
            8: stream(program, f'/Length1 {program.index(b"currentfile eexec") + 18} /Length2 1024 /Length3 0')}


# --- TXT-4, parser-03, parser-04: fonts pypdf 6.21.4 no longer builds -----------------------------------------------

def base_encoding_font(base: str, *, differences: str = '', subtype: str = 'Type1', font_base: str = 'Helvetica',
                       indirect: bool = False) -> dict:
    value = '9 0 R' if indirect else base
    enc = f'<< /Type /Encoding /BaseEncoding {value} {f"/Differences [{differences}]" if differences else ""} >>'
    font = {0: f'<< /Type /Font /Subtype /{subtype} /BaseFont /{font_base} /Encoding {enc} >>'.encode()}
    if indirect:
        font[9] = base.encode()
    return font


def w_font(w_entry: str) -> dict:
    """An Identity-H subset font whose /W holds ``w_entry`` (covering codes the text never uses)."""
    return identity_font(widths=f'/W [{w_entry}]')


# --- TXT-6: a built-in encoding name too long for a character --------------------------------------------------------

def overflow_font_page(*, used: bool) -> bytes:
    font = builtin_font({65: 'A', 66: 'u' + 'F' * 20})
    content = lines(NOTE + ['Polypectomy of a sessile polyp'])
    if used:
        content += '\nBT /F2 11 Tf 72 600 Td (AB) Tj ET'
    return with_font(content, font)


# --- TXT-5: two pages, the second in a composite font whose /Encoding is a stream or a dictionary ----------------

def two_page_composite(encoding: str, *, td: bool, indirect_w: bool) -> bytes:
    """Page 1 plain; page 2 in a Type0 font with ``encoding`` ('stream' or 'dict'), no ToUnicode, and a non-numeric
    TD (``td``) or an indirect /W width (``indirect_w``)."""
    enc = '12 0 R' if encoding == 'stream' else '<< /Type /Encoding >>'
    width = '/W [65 [13 0 R 500 500]]' if indirect_w else ''
    move = '0 /A TD' if td else '0 -14 Td'
    content2 = (f'BT /F2 11 Tf 72 700 Td (Colonoscopy with cold snare polypectomy.) Tj {move} '
                '(The sessile sigmoid polyp was removed.) Tj ET')
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>',
               3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                   b'/Contents 5 0 R >>'),
               4: HELVETICA, 5: stream(lines(NOTE)),
               6: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F2 8 0 R >> >> '
                   b'/Contents 7 0 R >>'),
               7: stream(content2),
               8: (f'<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+SyntheticSans /Encoding {enc} /DescendantFonts '
                   '[10 0 R] >>').encode(),
               10: (f'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /ABCDEF+SyntheticSans /CIDSystemInfo '
                    f'<< /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 11 0 R /DW 500 '
                    f'{width} >>').encode(),
               11: (b'<< /Type /FontDescriptor /FontName /ABCDEF+SyntheticSans /Flags 32 /FontBBox [0 -200 1000 900] '
                    b'/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>'),
               12: stream('/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Synthetic-H def '
                          '1 begincodespacerange <00> <FF> endcodespacerange 1 begincidrange <00> <FF> 0 endcidrange '
                          'endcmap CMapName currentdict /CMap defineresource pop end end',
                          '/Type /CMap /CMapName /Synthetic-H /CIDSystemInfo << /Registry (Adobe) /Ordering '
                          '(Identity) /Supplement 0 >>'),
               13: b'500'}
    return serialise(objects)


# --- n-5: U+FFFD reaching the labelled block by other routes ---------------------------------------------------------

def utf16(text: str) -> str:
    return '<FEFF' + text.encode('utf-16-be').hex().upper() + '>'


def field_page(field: str, *, extra: dict | None = None) -> bytes:
    """A page of ordinary text with one displayed text field ``field`` (object 26) and no appearance."""
    objects = {26: (f'<< /Type /Annot /Subtype /Widget /FT /Tx {field} /Rect [72 480 300 500] /F 4 >>').encode(),
               **(extra or {})}
    return page_pdf(lines(NOTE), extra=objects, annots='/Annots [26 0 R]',
                    catalog='/AcroForm << /Fields [26 0 R] >>')


def free_text_page(entries: str, *, extra: dict | None = None) -> bytes:
    objects = {26: (f'<< /Type /Annot /Subtype /FreeText /Rect [72 480 300 500] /F 4 /DA (/Helv 10 Tf 0 g) '
                    f'{entries} >>').encode(), **(extra or {})}
    return page_pdf(lines(NOTE), extra=objects, annots='/Annots [26 0 R]')


# --- parser rows --------------------------------------------------------------------------------------------------

def _xref_stream(entries: list[tuple[int, int, int]], *, size: int, index: str, extra: str = '',
                 padding: int = 0) -> bytes:
    """A cross-reference stream: ``entries``, then ``padding`` free entries."""
    data = b''.join(struct.pack('>BIH', kind, a, b) for kind, a, b in entries) + b'\x00' * (7 * padding)
    return flate(data, f'/Type /XRef /W [1 4 2] /Size {size} /Index [{index}] {extra}')


XREF_LIMIT = 2_000_000  # pypdf 6.21.4's xref_stream_maximum_entries and page_tree_maximum_page_entries


def xref_limit(where: str, count: int = XREF_LIMIT + 1) -> bytes:
    """parser-01/02: a valid document whose annotation lives in an object stream that only a cross-reference stream
    of ``count`` entries reaches: ``where`` 'hybrid' (a /XRefStm beside a table) or 'one' (the only section)."""
    body = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
    offsets = {}

    def put(number: int, data: bytes) -> None:
        offsets[number] = len(body)
        body.extend(b'%d 0 obj\n' % number + data + b'\nendobj\n')

    annotation = (b'<< /Type /Annot /Subtype /FreeText /Rect [72 480 300 500] /F 4 /DA (/Helv 10 Tf 0 g) '
                  b'/Contents (Follow up colonoscopy in three years per synthetic plan.) >>')
    header = b'8 0 '
    objstm = header + annotation
    put(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    put(2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    put(3, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
           b'/Contents 5 0 R /Annots [8 0 R] >>')
    put(4, HELVETICA)
    put(5, stream(lines(NOTE)))
    put(7, flate(objstm, f'/Type /ObjStm /N 1 /First {len(header)}'))
    entries = [(0, 0, 65535)] + [(1, offsets[n], 0) if n in offsets else (0, 0, 0) for n in range(1, 8)]
    entries += [(2, 7, 0)]  # object 8 in object stream 7
    if where == 'one':
        xref_at = len(body)
        entries += [(1, xref_at, 0)]
        put(9, _xref_stream(entries, size=count, index=f'0 {count}', extra='/Root 1 0 R',
                            padding=count - len(entries)))
        body.extend(b'startxref\n%d\n%%%%EOF\n' % xref_at)
        return bytes(body)
    xrefstm_at = len(body)
    put(9, _xref_stream(entries, size=count, index=f'0 {count}', padding=count - len(entries)))
    table_at = len(body)
    body.extend(b'xref\n0 8\n0000000000 65535 f \n')
    for number in range(1, 8):
        body.extend(b'%010d 00000 n \n' % offsets[number] if number in offsets else b'0000000000 65535 f \n')
    body.extend(b'trailer\n<< /Size %d /Root 1 0 R /XRefStm %d >>\nstartxref\n%d\n%%%%EOF\n'
                % (count, xrefstm_at, table_at))
    return bytes(body)


def page_entries(pages: int, keys: int) -> bytes:
    """parser-05/06: ``pages`` distinct page dictionaries of ``keys`` entries each, in object streams."""
    content = stream(lines(['Synthetic page of a long record; filler text, no patient content, page text.']))
    filler = ' '.join(f'/K{index} 0' for index in range(keys))
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 4: HELVETICA, 5: content}
    first = 10
    kids = ' '.join(f'{first + index} 0 R' for index in range(pages))
    objects[2] = f'<< /Type /Pages /Kids [{kids}] /Count {pages} >>'.encode()
    page = (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
            f'/Contents 5 0 R {filler} >>').encode()
    # pages in object streams of up to 500 pages each (stream objects numbered after the pages)
    body = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
    offsets, compressed = {}, {}
    for number in sorted(objects):
        offsets[number] = len(body)
        body.extend(b'%d 0 obj\n' % number + objects[number] + b'\nendobj\n')
    stream_number = first + pages
    for start in range(0, pages, 500):
        members = list(range(first + start, first + min(pages, start + 500)))
        heads, datas, at = [], [], 0
        for member in members:
            heads.append(f'{member} {at}')
            datas.append(page)
            at += len(page) + 1
        head = ' '.join(heads).encode() + b' '
        data = head + b'\n'.join(datas)
        offsets[stream_number] = len(body)
        body.extend(b'%d 0 obj\n' % stream_number
                    + flate(data, f'/Type /ObjStm /N {len(members)} /First {len(head)}') + b'\nendobj\n')
        for index, member in enumerate(members):
            compressed[member] = (stream_number, index)
        stream_number += 1
    xref_number = stream_number
    size = xref_number + 1
    entries = []
    for number in range(size):
        if number in offsets:
            entries.append((1, offsets[number], 0))
        elif number in compressed:
            entries.append((2, compressed[number][0], compressed[number][1]))
        else:
            entries.append((0, 0, 65535 if number == 0 else 0))
    xref_at = len(body)
    entries[xref_number] = (1, xref_at, 0)
    body.extend(b'%d 0 obj\n' % xref_number
                + _xref_stream(entries, size=size, index=f'0 {size}', extra='/Root 1 0 R') + b'\nendobj\n')
    body.extend(b'startxref\n%d\n%%%%EOF\n' % xref_at)
    return bytes(body)


def decode_parms(filter_name: str, parms: str, *, form: bool = False) -> bytes:
    """parser-08: the page's content (or a form it draws) under ``filter_name`` with a /DecodeParms ``parms`` that is
    not a dictionary; the bytes decode completely."""
    import base64  # noqa: PLC0415

    text = lines(NOTE + ['Cold snare polypectomy of a 6 mm sigmoid polyp, retrieved.'])
    raw = text.encode('latin-1')
    if filter_name == '/ASCII85Decode':
        data = base64.a85encode(raw) + b'~>'
    elif filter_name == '/ASCIIHexDecode':
        data = raw.hex().encode() + b'>'
    elif filter_name == '/RunLengthDecode':
        data = b''.join(bytes([len(raw[i:i + 128]) - 1]) + raw[i:i + 128] for i in range(0, len(raw), 128)) + b'\x80'
    elif filter_name == '/LZWDecode':
        data = _lzw(raw)
    else:
        raise ValueError(filter_name)
    encoded = stream(data, f'/Filter {filter_name} /DecodeParms {parms}')
    if not form:
        return page_pdf(b'', extra={5: encoded, 9: b'5'})
    form_stream = stream(data, f'/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F1 4 0 R '
                               f'>> >> /Filter {filter_name} /DecodeParms {parms}')
    return page_pdf('/Fm1 Do', extra={6: form_stream, 9: b'5'}, xobjects='/Fm1 6 0 R')


def _lzw(data: bytes) -> bytes:
    """LZW (EarlyChange 1), as PDF 32000-1 7.4.4 describes it."""
    table = {bytes([i]): i for i in range(256)}
    width, next_code, out, bits, count = 9, 258, bytearray(), 0, 0

    def emit(code: int) -> None:
        nonlocal bits, count
        bits = (bits << width) | code
        count += width
        while count >= 8:
            count -= 8
            out.append((bits >> count) & 0xFF)

    emit(256)
    word = b''
    for byte in data:
        candidate = word + bytes([byte])
        if candidate in table:
            word = candidate
            continue
        emit(table[word])
        table[candidate] = next_code
        next_code += 1
        if next_code >= (1 << width) and width < 12:  # the decoder widens one code after it, early by one
            width += 1
        word = bytes([byte])
    if word:
        emit(table[word])
    emit(257)
    if count:
        out.append((bits << (8 - count)) & 0xFF)
    return bytes(out)


def _rc4(key: bytes, data: bytes) -> bytes:
    s, j = list(range(256)), 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    out, i, j = bytearray(), 0, 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


_PAD = bytes.fromhex('28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A')


def rc4_encrypted(length_entry: int, *, version: int = 2, revision: int = 3, key_bits: int | None = None) -> bytes:
    """parser-09/10: the page's text under the standard security handler with an empty user password, RC4, written
    with /Length ``length_entry`` and a key of ``key_bits`` (default: what /Length says, as the file's producer
    used it). Algorithms 2, 3 and 5 of ISO 32000-1 7.6.3."""
    key_bits = length_entry if key_bits is None else key_bits
    file_id = hashlib.md5(b'synthetic-cpt-studio-encryption').digest()
    owner = _rc4(hashlib.md5(_PAD).digest()[:5], _PAD) if revision == 2 else _PAD  # any 32 bytes: not checked here
    permissions = -4
    key_length = max(1, key_bits // 8) if revision >= 3 else 5
    digest = hashlib.md5(_PAD + owner + struct.pack('<i', permissions) + file_id).digest()
    if revision >= 3:
        for _ in range(50):
            digest = hashlib.md5(digest[:key_length]).digest()
    key = digest[:key_length]
    if revision >= 3:
        user = hashlib.md5(_PAD + file_id).digest()
        user = _rc4(key, user)
        for index in range(1, 20):
            user = _rc4(bytes(b ^ index for b in key), user)
        user += b'\x00' * 16
    else:
        user = _rc4(key, _PAD)

    def object_key(number: int) -> bytes:
        digest = hashlib.md5(key + number.to_bytes(3, 'little') + (0).to_bytes(2, 'little')).digest()
        return digest[:min(16, len(key) + 5)]

    text = lines(NOTE + ['Cold snare polypectomy of a 6 mm sigmoid polyp, retrieved.']).encode('latin-1')
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                   b'/Contents 5 0 R >>'),
               4: HELVETICA, 5: stream(_rc4(object_key(5), text)),
               6: (f'<< /Filter /Standard /V {version} /R {revision} /Length {length_entry} /P {permissions} '
                   f'/O <{owner.hex()}> /U <{user.hex()}> >>').encode()}
    return serialise(objects, trailer=f'/Encrypt 6 0 R /ID [<{file_id.hex()}> <{file_id.hex()}>]')


def ccitt_content(*, form: bool) -> bytes:
    """parser-11: a content stream (or a form) stored CCITT-encoded with no /Height, beside the page's real text."""
    fax = b'\x00\x10\x01'  # Group 4 data that is only its end-of-block pattern (EOFB): no rows
    if form:
        objects = {6: stream(fax, '/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Filter /CCITTFaxDecode '
                                  '/DecodeParms << /K -1 /Columns 8 >>')}
        return page_pdf(lines(NOTE) + '\n/Fm1 Do', extra=objects, xobjects='/Fm1 6 0 R')
    objects = {3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                   b'/Contents [5 0 R 6 0 R] >>'),
               6: stream(fax, '/Filter /CCITTFaxDecode /DecodeParms << /K -1 /Columns 8 >>')}
    return page_pdf(lines(NOTE), extra=objects)


# --- the registry ---------------------------------------------------------------------------------------------------

def _shapes() -> dict:
    cut_high, cut_low = '00410042FF', '0041004241'
    shapes = {
        # TXT-1 / n-1 / n-2: a cut string in an appearance the reader reads
        'TXT-1 stamp odd high': annotated(shown(cut_high)),
        'TXT-1 stamp odd low': annotated(shown(cut_low)),
        'TXT-1 push button odd high': annotated(shown(cut_high), annotation='/Subtype /Widget /FT /Btn /Ff 65536 '
                                                                            '/T (stamp)'),
        'TXT-1 push button odd low': annotated(shown(cut_low), annotation='/Subtype /Widget /FT /Btn /Ff 65536 '
                                                                          '/T (stamp)'),
        'TXT-1 text field without value, one-byte text': annotated('BT /F9 10 Tf 2 5 Td (Polyp) Tj ET',
                                                                   annotation='/Subtype /Widget', acroform=True),
        'TXT-1 stamp one-byte text': annotated('BT /F9 10 Tf 2 5 Td (Polyp biopsy.) Tj ET'),
        'pre-existing: stamp one-byte text, even count': annotated('BT /F9 10 Tf 2 5 Td (Polyp biopsy) Tj ET'),
        'TXT-1 stamp nested form odd low': annotated('', form_ops=shown(cut_low)),
        'TXT-1 stamp ToUnicode gives FFFD': annotated(shown('004100420043'), font=composite(
            descendant=23, descriptor=24, to_unicode_ref='/ToUnicode 22 0 R') | {
            22: to_unicode(pairs=[(0x41, 'A'), (0x42, 'B'), (0x43, '\ufffd')])}),
        'n-1 FreeText without Contents odd high': annotated(shown(cut_high), annotation='/Subtype /FreeText '
                                                                                       '/DA (/Helv 10 Tf 0 g)'),
        'n-1 text field without value odd high': annotated(shown(cut_high), annotation='/Subtype /Widget',
                                                           acroform=True),
        'n-1 stamp 90ms-RKSJ-H cut': annotated(shown('82A082'), font=composite(
            'HeiseiMin-W3', encoding='/90ms-RKSJ-H', descendant=23, descriptor=24, ordering='Japan1',
            cid_type='CIDFontType0', cid_to_gid='')),
        'n-1 stamp GBK-EUC-H cut': annotated(shown('B0A1FF'), font=composite(
            'STSong-Light', encoding='/GBK-EUC-H', descendant=23, descriptor=24, ordering='GB1',
            cid_type='CIDFontType0', cid_to_gid='')),
        'n-1 page 2 stamp cut, page 3 layer cut': annotated(shown(cut_high), pages=2,
                                                            layer_ops=f'BT /F9 11 Tf 72 560 Td <{cut_high}> Tj ET'),
        'n-2 stamp one-byte text odd': annotated('BT /F9 10 Tf 2 5 Td (Reviewed by Dr. Example) Tj ET'),
        'n-2 signature field one-byte text odd': annotated('BT /F9 10 Tf 2 5 Td (Reviewed by Dr. Example) Tj ET',
                                                           annotation='/Subtype /Widget /FT /Sig /T (Signature1)'),
        'n-2 stamp two-byte cut low': annotated(shown('005200650076006900650077006500640020006F006E0020003100300'
                                                      '02F0033003041')),
        'n-2 FreeText without Contents odd low': annotated(shown(cut_low), annotation='/Subtype /FreeText '
                                                                                     '/DA (/Helv 10 Tf 0 g)'),
        'n-2 text field without value odd low': annotated(shown(cut_low), annotation='/Subtype /Widget',
                                                          acroform=True),
        # TXT-7 / n-3: the replacement character looked up in a ToUnicode with an entry for code FFFD
        'TXT-7 FFFD maps to a checked box, odd high': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_high}> Tj ET',
            identity_font(to_unicode(pairs=[(0xFFFD, '\u2612')], ranges=IDENTITY_RANGE))),
        'TXT-7 FFFD maps to a checked box, odd low': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_low}> Tj ET',
            identity_font(to_unicode(pairs=[(0xFFFD, '\u2612')], ranges=IDENTITY_RANGE))),
        'TXT-7 FFFD maps to a space, odd high': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_high}> Tj ET',
            identity_font(to_unicode(pairs=[(0xFFFD, ' ')], ranges=IDENTITY_RANGE))),
        'n-3 FFFD maps to X, odd high': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_high}> Tj ET',
            identity_font(to_unicode(pairs=[(0xFFFD, 'X')], ranges=IDENTITY_RANGE))),
        'n-3 FFFD maps to X, odd low': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_low}> Tj ET',
            identity_font(to_unicode(pairs=[(0xFFFD, 'X')], ranges=IDENTITY_RANGE))),
        'n-3 range covers FFFD, odd high': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_high}> Tj ET',
            identity_font(to_unicode(ranges=IDENTITY_RANGE + ((0xFFF0, 0xFFFF, 0x01F0),)))),
        'page layer cut, odd high': with_font(lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_high}> Tj ET',
                                              identity_font()),
        'page layer cut, odd low': with_font(lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td <{cut_low}> Tj ET',
                                             identity_font()),
        'page layer one-byte text in a two-byte font': with_font(
            lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Polyp removed) Tj ET', identity_font()),
        # n-4: a page under 20 readable characters holding U+FFFD, no OCR
        'n-4 only glyph, ToUnicode gives FFFD': page_pdf('BT /F2 11 Tf 72 700 Td <0043> Tj ET',
                                                         fonts='/F1 4 0 R /F2 6 0 R', extra={
            6: identity_font(to_unicode(pairs=[(0x43, '\ufffd')]))[0],
            **{k: v for k, v in identity_font(to_unicode(pairs=[(0x43, '\ufffd')])).items() if k}}),
        'n-4 only cut high': with_font('BT /F2 11 Tf 72 700 Td <FF> Tj ET', identity_font()),
        'n-4 only cut low': with_font('BT /F2 11 Tf 72 700 Td <41> Tj ET', identity_font()),
        # n-5: U+FFFD reaching the block by other routes
        'n-5 stamp ToUnicode gives FFFD': annotated(shown('004100420043'), font=composite(
            descendant=23, descriptor=24, to_unicode_ref='/ToUnicode 22 0 R') | {
            22: to_unicode(pairs=[(0x41, 'A'), (0x42, 'B'), (0x43, '\ufffd')])}),
        'n-5 field value stream not UTF-8': field_page('/T (finding) /V 27 0 R', extra={
            27: stream(b'Finding: Caf\xe9 diet advised')}),
        'n-5 rich text stream not UTF-8': free_text_page('/RC 27 0 R', extra={
            27: stream(b'<?xml version="1.0"?><body><p>Finding: Caf\xe9 diet advised</p></body>')}),
        'n-5 field value literal FFFD': field_page(f'/T (finding) /V {utf16("Finding: Caf" + chr(0xFFFD))}'),
        'n-5 FreeText Contents literal FFFD': free_text_page(f'/Contents {utf16("Caf" + chr(0xFFFD) + " diet")}'),
        'n-5 field label literal FFFD': field_page(f'/T {utf16("find" + chr(0xFFFD))} /V (Cafe diet advised)'),
        # a glyph that names no character alone in typed brackets, in annotation text
        'box guard: FreeText Contents with a private-use mark': free_text_page(
            f'/Contents {utf16("[" + chr(0xF00C) + "] " + SNARE)}'),
        # TXT-3: a check mark named by a private-use or control glyph name
        'TXT-3 /uniF00C': named_mark('uniF00C'),
        'TXT-3 /uF00C': named_mark('uF00C'),
        'TXT-3 /uni0001': named_mark('uni0001'),
        'TXT-3 /uni0000': named_mark('uni0000'),
        'TXT-3 control: ToUnicode gives U+F00C': with_font(boxed('41'), {0: differences_font(
            '', to_unicode_ref='/ToUnicode 7 0 R', encoding='/WinAnsiEncoding')},
            extra={7: to_unicode(pairs=[(0x41, '\uf00c')], code_bytes=1)}),
        'TXT-3 control: a real check mark /uni2713': named_mark('uni2713'),
        # TXT-8: newly decoded names reaching pypdf's existing mis-lookups
        'TXT-8 built-in /u2610 under WinAnsi': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td (A {esc(SNARE)}) Tj ET',
            builtin_font({65: 'u2610'}, encoding='/WinAnsiEncoding')),
        'TXT-8 built-in /u2612, Differences /uni2610': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td (A) Tj /F1 11 Tf ( {esc(SNARE)}) Tj ET',
            builtin_font({65: 'u2612'}, encoding='<< /Differences [65 /uni2610] >>')),
        'TXT-8 double lookup /uni0041': with_font(boxed('80', brackets=False), {0: differences_font(
            '128 /uni0041', to_unicode_ref='/ToUnicode 7 0 R')}, extra={7: to_unicode(pairs=[(0x41, '\u2610')],
                                                                                      code_bytes=1)}),
        'TXT-8 double lookup /uni0058': with_font(boxed('80', brackets=False), {0: differences_font(
            '128 /uni0058', to_unicode_ref='/ToUnicode 7 0 R')}, extra={7: to_unicode(pairs=[(0x58, '\u2610')],
                                                                                      code_bytes=1)}),
        'TXT-8 pre-existing: built-in /uni2610 under WinAnsi': with_font(
            lines(NOTE) + f'\nBT /F2 11 Tf 72 600 Td (A {esc(SNARE)}) Tj ET',
            builtin_font({65: 'uni2610'}, encoding='/WinAnsiEncoding')),
        'TXT-8 pre-existing: double lookup /A': with_font(boxed('80', brackets=False), {0: differences_font(
            '128 /A', to_unicode_ref='/ToUnicode 7 0 R')}, extra={7: to_unicode(pairs=[(0x41, '\u2610')],
                                                                                code_bytes=1)}),
        # TXT-9: names outside the AGL form
        'TXT-9 /u20 in brackets': named_mark('u20'),
        'TXT-9 /u78 in brackets': named_mark('u78'),
        'TXT-9 /u261': named_mark('u261', brackets=False, label='Biopsy of a sessile polyp'),
        'TXT-9 /u0x41': named_mark('u0x41', brackets=False, label='Biopsy of a sessile polyp'),
        'TXT-9 /u+41': named_mark('u+41', brackets=False, label='Biopsy of a sessile polyp'),
        'TXT-9 /u4_1': named_mark('u4_1', brackets=False, label='Biopsy of a sessile polyp'),
        # TXT-10: NUL and U+FFFF decoded from glyph names
        'TXT-10 /uni0000': named_mark('uni0000', brackets=False, label='Biopsy of a sessile polyp'),
        'TXT-10 /u0000': named_mark('u0000', brackets=False, label='Biopsy of a sessile polyp'),
        'TXT-10 /u0': named_mark('u0', brackets=False, label='Biopsy of a sessile polyp'),
        'TXT-10 /uFFFF': named_mark('uFFFF', brackets=False, label='Biopsy of a sessile polyp'),
        'AGL control: /uni2610 in Differences': named_mark('uni2610', brackets=False),
        # TXT-6: a built-in encoding name too long for a character
        'TXT-6 font used': overflow_font_page(used=True),
        'TXT-6 font unused': overflow_font_page(used=False),
        # TXT-4 / parser-03 / parser-04: fonts 6.21.4 no longer builds
        'TXT-4 /BaseEncoding array': with_font(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Polypectomy of a sessile '
                                                             'polyp) Tj ET',
                                               base_encoding_font('[/WinAnsiEncoding]')),
        'TXT-4 /BaseEncoding dictionary': with_font(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Polypectomy of a '
                                                                  'sessile polyp) Tj ET',
                                                    base_encoding_font('<< /A 1 >>')),
        'TXT-4 /BaseEncoding array with Differences': with_font(
            lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Assessment: benign mucosa) Tj ET',
            base_encoding_font('[/WinAnsiEncoding]', differences='65 /B')),
        'TXT-4 /BaseEncoding indirect array': with_font(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Polypectomy of a '
                                                                      'sessile polyp) Tj ET',
                                                        base_encoding_font('[/WinAnsiEncoding]', indirect=True)),
        'TXT-4 symbol font /BaseEncoding array': with_font(
            lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (abcdefg) Tj ET',
            base_encoding_font('[]', font_base='ZapfDingbats')),
        'TXT-4 /W literal string': with_font(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td <004100420043> Tj ET',
                                             w_font('900 (ab)')),
        'TXT-4 /W hex string': with_font(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td <004100420043> Tj ET',
                                         w_font('900 <80ff>')),
        'TXT-4 /W name': with_font(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td <004100420043> Tj ET', w_font('900 /ab')),
        # the parked documentation's other difference: an indirect width in a CID font's /W, for codes the text uses
        'indirect /W width': with_font(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td <004100420043> Tj ET',
                                       w_font('65 [13 0 R 600 600]'), extra={13: b'600'}),
        'parser-03 /BaseEncoding font in a field appearance': _base_encoding_widget(),
        # fonts pypdf cannot build under either version (it draws their text in a stand-in font: U+FFFD per byte)
        'unbuildable: a composite font whose descendant is no dictionary': with_font(
            lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td <004100420043> Tj ET',
            {0: b'<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+SyntheticSans /Encoding /Identity-H '
                b'/DescendantFonts [99] /ToUnicode 7 0 R >>', 7: to_unicode(ranges=IDENTITY_RANGE)}),
        'unbuildable: a simple font whose descriptor is no dictionary': with_font(
            lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Polypectomy of a sessile polyp) Tj ET',
            {0: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /FontDescriptor 5 >>'}),
        # TXT-5: two pages, the second in a composite font with a stream or dictionary /Encoding
        'TXT-5 TD, encoding stream': two_page_composite('stream', td=True, indirect_w=False),
        'TXT-5 TD, encoding dictionary': two_page_composite('dict', td=True, indirect_w=False),
        'TXT-5 indirect /W, encoding stream': two_page_composite('stream', td=False, indirect_w=True),
        'TXT-5 indirect /W, encoding dictionary': two_page_composite('dict', td=False, indirect_w=True),
        'TXT-5 pre-existing crash control': two_page_composite('stream', td=False, indirect_w=False),
        # pypdf-1 (the parked documentation's limit): a non-numeric TD
        'pypdf-1 non-numeric TD': page_pdf(lines(NOTE) + '\nBT /F1 11 Tf 72 600 Td (Cold snare polypectomy) Tj '
                                                         '0 /A TD (of the sigmoid polyp.) Tj ET'),
        # parser-08: a /DecodeParms that is not a dictionary
        'parser-08 ASCII85 with a number': decode_parms('/ASCII85Decode', '5'),
        'parser-08 ASCIIHex with a name': decode_parms('/ASCIIHexDecode', '/None'),
        'parser-08 RunLength with 0': decode_parms('/RunLengthDecode', '0'),
        'parser-08 LZW with false': decode_parms('/LZWDecode', 'false'),
        'parser-08 indirect number': decode_parms('/ASCII85Decode', '9 0 R'),
        'parser-08 in a form': decode_parms('/ASCII85Decode', '5', form=True),
        'parser-08 control: Flate with a number': page_pdf(b'', extra={5: flate(lines(NOTE), '/DecodeParms 5')}),
        # parser-09 / parser-10: encryption key lengths
        'parser-09 V1 R2 /Length 129': rc4_encrypted(129, version=1, revision=2, key_bits=40),
        'parser-09 V1 R2 /Length 1024': rc4_encrypted(1024, version=1, revision=2, key_bits=40),
        'parser-10 RC4 /Length 129': rc4_encrypted(129),
        'parser-10 RC4 /Length 41': rc4_encrypted(41),
        'parser-10 control: RC4 /Length 128': rc4_encrypted(128),
        # parser-11: CCITT-encoded content with no /Height
        'parser-11 form': ccitt_content(form=True),
        'parser-11 content stream': ccitt_content(form=False),
    }
    for cmap in UNIMPLEMENTED_CMAPS + IMPLEMENTED_CMAPS:
        shapes[f'TXT-2 {cmap} odd'] = cjk_page(cmap)
        shapes[f'TXT-2 {cmap} even'] = cjk_page(cmap, odd=False)
    return shapes


def _base_encoding_widget() -> bytes:
    """parser-03 z01: a font with a /BaseEncoding array draws the page text and a text field's appearance, which shows
    exactly the field's value."""
    font = base_encoding_font('[/WinAnsiEncoding]')
    objects = {6: font[0],
               20: stream('BT /F2 10 Tf 2 5 Td (Value) Tj ET', '/Type /XObject /Subtype /Form /BBox [0 0 228 20] '
                                                              '/Resources << /Font << /F2 6 0 R >> >>'),
               26: (b'<< /Type /Annot /Subtype /Widget /FT /Tx /T (Field) /V (Value) /Rect [72 480 300 500] /F 4 '
                    b'/AP << /N 20 0 R >> >>')}
    return page_pdf(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Polypectomy of a sessile polyp) Tj ET',
                    fonts='/F1 4 0 R /F2 6 0 R', extra=objects, annots='/Annots [26 0 R]',
                    catalog='/AcroForm << /Fields [26 0 R] >>')


def shapes() -> dict[str, bytes]:
    """{name: PDF bytes}, each name starting with its residual row."""
    return _shapes()


def heavy_shapes() -> dict[str, bytes]:
    """The parser rows past pypdf 6.21.4's 2,000,000-entry limits (a few seconds each to build and read)."""
    return {'parser-01 hybrid /XRefStm over the limit': xref_limit('hybrid'),
            'parser-01 control: hybrid /XRefStm at the limit': xref_limit('hybrid', XREF_LIMIT),
            'parser-02 the only cross-reference stream over the limit': xref_limit('one'),
            'parser-05 40 pages of 52,000 entries': page_entries(40, 52_000),
            'parser-05 control: 40 pages of 49,000 entries': page_entries(40, 49_000),
            'parser-06 92,000 pages of 22 entries': page_entries(92_000, 22)}
