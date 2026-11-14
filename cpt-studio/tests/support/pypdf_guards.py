"""One synthetic PDF per patch of studio/ingest/pypdf_compat.py that pypdf 6.21.4 reads differently without it, with
the reading pypdf 6.21.2 gives (the installed reader's): tests/test_pypdf_compat.py reads each through the real
extraction child. Raw PDF syntax only (no pypdf writer), fictional text. Importable without Django."""
from __future__ import annotations

DAMAGED = 'The PDF could not be read; the file is damaged or is not a valid PDF.'
NO_LAYER = 'Page 1 has no usable text layer and OCR is not available on this server.'
CONTENT_DAMAGED = 'Page 1 is damaged: part of its content could not be decoded, so its text may be incomplete or wrong.'
NOTE = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING', 'Date of service: 2026-10-21',
        'Procedure: Colonoscopy to the cecum.', 'Findings: A 6 mm sigmoid polyp was seen.']
HELVETICA = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'


def stream(data: bytes, extra: str = '') -> bytes:
    return f'<< {extra} /Length {len(data)} >>\nstream\n'.encode() + data + b'\nendstream'


def lines(rows) -> str:
    return '\n'.join(f'BT /F1 11 Tf 72 {740 - 20 * n} Td ({row}) Tj ET' for n, row in enumerate(rows))


def document(content: str, *, fonts: str = '/F1 4 0 R', extra: dict | None = None, contents: str = '5 0 R',
             trailer: str = '') -> bytes:
    """Objects 1-5 (catalog, pages, page, Helvetica, content) and ``extra``, with an exact cross-reference table."""
    objects = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               3: (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << {fonts} >> >> '
                   f'/Contents {contents} >>').encode(),
               4: HELVETICA, 5: stream(content.encode('latin-1')), **(extra or {})}
    out, offsets = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n'), {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b'%d 0 obj\n' % number + objects[number] + b'\nendobj\n'
    size = max(objects) + 1
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size
    out += b''.join(b'%010d 00000 n \n' % offsets[n] if n in offsets else b'0000000000 65535 f \n'
                    for n in range(1, size))
    out += b'trailer\n<< /Size %d /Root 1 0 R %s >>\nstartxref\n%d\n%%%%EOF\n' % (size, trailer.encode(), xref)
    return bytes(out)


def identity_font(widths: str = '') -> dict:
    """An Identity-H composite font (6) with an identity ToUnicode (7), its descendant (8) and descriptor (9)."""
    cmap = ('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry (Adobe) '
            '/Ordering (UCS) /Supplement 0 >> def\n/CMapName /Synthetic-UCS def\n/CMapType 2 def\n'
            '1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n1 beginbfrange\n<0000> <00FF> <0000>\n'
            'endbfrange\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n')
    return {6: b'<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+SyntheticSans /Encoding /Identity-H '
               b'/DescendantFonts [8 0 R] /ToUnicode 7 0 R >>',
            7: stream(cmap.encode()),
            8: (f'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /ABCDEF+SyntheticSans /CIDSystemInfo << /Registry '
                f'(Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 9 0 R /CIDToGIDMap /Identity /DW 500 '
                f'{widths} >>').encode(),
            9: (b'<< /Type /FontDescriptor /FontName /ABCDEF+SyntheticSans /Flags 32 /FontBBox [0 -200 1000 900] '
                b'/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>')}


def type1_font(builtin: dict) -> dict:
    """A Type 1 font (6) whose embedded program (8; descriptor 7) has the built-in encoding ``builtin``."""
    dups = '\n'.join(f'dup {code} /{glyph} put' for code, glyph in sorted(builtin.items()))
    clear = ('%!PS-AdobeFont-1.0: SyntheticSerif 001.000\n/FontName /SyntheticSerif def\n/Encoding 256 array\n'
             f'0 1 255 {{1 index exch /.notdef put}} for\n{dups}\nreadonly def\ncurrentfile eexec\n')
    program = clear.encode('latin-1') + bytes(range(256)) * 4
    widths = ' '.join(['556'] * 224)
    return {6: (f'<< /Type /Font /Subtype /Type1 /BaseFont /ABCDEF+SyntheticSerif /FirstChar 32 /LastChar 255 '
                f'/Widths [{widths}] /FontDescriptor 7 0 R >>').encode(),
            7: (b'<< /Type /FontDescriptor /FontName /ABCDEF+SyntheticSerif /Flags 32 /FontBBox [0 -200 1000 900] '
                b'/ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile 8 0 R >>'),
            8: stream(program, f'/Length1 {program.index(b"currentfile eexec") + 18} /Length2 1024 /Length3 0')}


F2 = '/F1 4 0 R /F2 6 0 R'
SNARE = 'Cold snare polypectomy of the sigmoid polyp'
FAX = b'\x00\x10\x01'  # Group 4 data that is only its end-of-block pattern

# name -> (the patch it guards, PDF bytes, (status, text ends with, a message it holds))
GUARDS = {
    'a /BaseEncoding array': (
        '_parse_encoding (H2)',
        document(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td (Polypectomy of a sessile polyp) Tj ET', fonts=F2,
                 extra={6: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type /Encoding '
                           b'/BaseEncoding [/WinAnsiEncoding] >> >>'}),
        ('ok', 'Polypectomy of a sessile polyp', None)),
    'a /Differences name uniF00C': (
        '_parse_encoding (H3)',
        document(lines(NOTE) + f'\nBT /F1 11 Tf 72 620 Td ([) Tj /F2 11 Tf <41> Tj /F1 11 Tf (] {SNARE}) Tj ET',
                 fonts=F2, extra={6: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type '
                                     b'/Encoding /Differences [65 /uniF00C] >> >>'}),
        ('ok', f'[/uniF00C] {SNARE}', None)),
    'a built-in /u name too long for a character': (
        '_glyph_name_to_unicode (H5)',
        document(lines(NOTE + ['Polypectomy of a sessile polyp']) + '\nBT /F2 11 Tf 72 600 Td (AB) Tj ET', fonts=F2,
                 extra=type1_font({65: 'A', 66: 'u' + 'F' * 20})),
        ('ok', 'Polypectomy of a sessile polyp\nAB', None)),
    'a cut two-byte string in the page': (
        'get_text_operands (H79)',
        document(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td <0041004241> Tj ET', fonts=F2, extra=identity_font()),
        ('failed', '', NO_LAYER)),
    'a string in a /W array': (
        'Font._collect_cid_character_widths (H46)',
        document(lines(NOTE) + '\nBT /F2 11 Tf 72 600 Td <004100420043> Tj ET', fonts=F2,
                 extra=identity_font('/W [900 (ab)]')),
        ('ok', 'ABC', None)),
    'an encryption key length of 136 bits': (
        'Encryption.read (H18)',
        document(lines(NOTE), extra={10: b'<< /Filter /Standard /V 2 /R 3 /Length 136 /P -4 /O <' + b'41' * 32
                                         + b'> /U <' + b'42' * 32 + b'> >>'},
                 trailer='/Encrypt 10 0 R /ID [<00112233445566778899aabbccddeeff> <00112233445566778899aabbccddeeff>]'),
        ('failed', '', DAMAGED)),
    'CCITT content with /Height null': (
        'CCITTFaxDecode._get_parameters (H21)',
        document(lines(NOTE), contents='[5 0 R 6 0 R]',
                 extra={6: stream(FAX, '/Filter /CCITTFaxDecode /DecodeParms << /K -1 /Columns 8 >> /Height null')}),
        ('failed', '', CONTENT_DAMAGED)),
    'CCITT content without /Height': (
        'decode_stream_data (H23)',
        document(lines(NOTE), contents='[5 0 R 6 0 R]',
                 extra={6: stream(FAX, '/Filter /CCITTFaxDecode /DecodeParms << /K -1 /Columns 8 >>')}),
        ('failed', '', CONTENT_DAMAGED)),
}


def holds(result, expected) -> bool:
    status, ending, message = expected
    return (result.status == status and result.text.endswith(ending)
            and (message is None or message in result.messages))
