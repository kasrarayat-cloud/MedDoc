"""Synthetic PDFs at pypdf 6.21.4's #4269 cross-reference stream limit (2,000,000 entries, counted at every read of a
stream) and its negative /Index count, for tests/test_pypdf_compat.py and tests/test_passages_verify.py: each is a
shape round 6's refutation measured (pypdf-r6 L1-L7, F1, F2, C1, C2, V3). Raw PDF syntax only (no pypdf writer),
fictional text. Importable without Django."""
from __future__ import annotations

import zlib

LIMIT = 2_000_000  # pypdf 6.21.4's xref_stream_maximum_entries (PdfReader's default)
HELVETICA = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
PAGE_TEXT = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR BILLING'
ANNOTATION = 'Cold snare polypectomy noted in a synthetic annotation.'
OLDER = 'SUPERSEDED DRAFT: biopsy deferred (fictional).'
CURRENT = 'CURRENT: antral biopsy taken with cold forceps (fictional).'


def obj(number: int, body: bytes) -> bytes:
    return b'%d 0 obj\n' % number + body + b'\nendobj\n'


def stream(entries: bytes, data: bytes, flate: bool = True) -> bytes:
    if flate:
        data = zlib.compress(data, 9)
        entries = b'/Filter /FlateDecode ' + entries
    return b'<< ' + entries + b' /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


def table(offsets: dict) -> bytes:
    """A classic cross-reference section listing ``offsets`` ({number: offset}) and object 0, one subsection per run."""
    numbers = sorted(set(offsets) | {0})
    runs, run = [], [numbers[0]]
    for number in numbers[1:]:
        if number == run[-1] + 1:
            run.append(number)
        else:
            runs.append(run)
            run = [number]
    runs.append(run)
    out = b'xref\n'
    for run in runs:
        out += b'%d %d\n' % (run[0], len(run))
        out += b''.join(b'0000000000 65535 f \n' if n == 0 else b'%010d 00000 n \n' % offsets[n] for n in run)
    return out


def xref_stream(entries: int, listed: dict) -> bytes:
    """A cross-reference stream of ``entries`` entries from 0 (W [1 4 2]): free, except ``listed`` {number: (type,
    field 2, field 3)}."""
    rows = bytearray(7 * entries)
    for number, (kind, second, third) in listed.items():
        rows[number * 7:(number + 1) * 7] = kind.to_bytes(1, 'big') + second.to_bytes(4, 'big') + third.to_bytes(2, 'big')
    return stream(b'/Type /XRef /W [1 4 2] /Index [0 %d] /Size %d' % (entries, entries), bytes(rows))


def object_stream(members: list) -> bytes:
    head, body = [], b''
    for number, member in members:
        head.append(b'%d %d' % (number, len(body)))
        body += member + b'\n'
    header = b' '.join(head) + b'\n'
    return stream(b'/Type /ObjStm /N %d /First %d' % (len(members), len(header)), header + body)


class _Writer:
    def __init__(self):
        self.out = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
        self.offsets = {}

    def add(self, number: int, body: bytes) -> int:
        self.offsets[number] = len(self.out)
        self.out += obj(number, body)
        return self.offsets[number]

    def section(self, numbers, trailer: bytes) -> int:
        at = len(self.out)
        self.out += table({n: self.offsets[n] for n in numbers}) + b'trailer\n<< ' + trailer + b' >>\n'
        self.out += b'startxref\n%d\n%%%%EOF\n' % at
        return at


def _page(writer: _Writer, annotated: bool, extra: bytes = b'', depth: int = 0) -> tuple:
    """The catalog, the page tree and its one page (objects 1-5); with ``depth``, the page hangs below that many
    nested /Pages nodes (objects 200 on), whose numbers are returned."""
    nodes = tuple(range(200, 200 + depth))
    writer.add(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    writer.add(2, b'<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % (nodes[0] if nodes else 3))
    for index, number in enumerate(nodes):
        writer.add(number, b'<< /Type /Pages /Parent %d 0 R /Kids [%d 0 R] /Count 1 >>'
                   % (nodes[index - 1] if index else 2, nodes[index + 1] if index + 1 < depth else 3))
    writer.add(3, b'<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                  b'/Contents 5 0 R' % (nodes[-1] if nodes else 2) + (b' /Annots [9 0 R]' if annotated else b'')
                  + extra + b' >>')
    writer.add(4, HELVETICA)
    writer.add(5, stream(b'', f'BT /F1 11 Tf 72 720 Td ({PAGE_TEXT}) Tj ET\n'
                              'BT /F1 11 Tf 72 700 Td (Procedure: Colonoscopy to the cecum.) Tj ET\n'.encode(),
                         flate=False))
    return nodes


def _annotation() -> bytes:
    return (b'<< /Type /Annot /Subtype /FreeText /Rect [72 500 400 540] /Contents (%s) /DA (/F1 12 Tf 0 g) >>'
            % ANNOTATION.encode())


def repeated(entries: int, trailers: int, alias: bool = False, depth: int = 0) -> bytes:
    """One /XRefStm X of ``entries`` entries, the only listing of the page's FreeText annotation (object 9, in object
    stream 6), named by the first revision's trailer and repeated by ``trailers`` - 1 later ones, as a writer that
    copies the trailer forward does (pypdf-r6 L4: C1 is 1,000,001 x 2; the judge's V1 200,001 x 10). pypdf 6.21.4
    reads and counts X at each naming, so #4269 counts ``entries`` x ``trailers``. ``alias``: the later trailers name
    X one byte early, at the line break before its object header (the same stream). ``depth``: the page hangs below
    that many nested /Pages nodes (pypdf-r6 C2: 101, one past pypdf's page-tree depth limit of 100)."""
    writer = _Writer()
    nodes = _page(writer, annotated=True, depth=depth)
    writer.add(6, object_stream([(9, _annotation())]))
    x = writer.add(8, xref_stream(entries, {9: (2, 6, 0)}))
    assert writer.out[x - 1:x] == b'\n'
    trailer = b'/Size %d /Root 1 0 R /XRefStm %d' % (entries, x)
    later = b'/Size %d /Root 1 0 R /XRefStm %d' % (entries, x - 1 if alias else x)
    previous = writer.section((1, 2, 3, 4, 5, 6) + nodes, trailer)
    for revision in range(2, trailers + 1):
        writer.add(10, b'<< /Producer (synthetic writer that copies the trailer) /ModDate (D:20261112%06d) >>'
                   % revision)
        previous = writer.section((10,), later + b' /Info 10 0 R /Prev %d' % previous)
    return bytes(writer.out)


def repeated_then_distinct(first: int, second: int, repeat: bool = True) -> bytes:
    """Newest first: an update's /XRefStm X (``second`` entries), named again by the next update's trailer when
    ``repeat``, then the first revision's own /XRefStm Y (``first`` entries), the only listing of the annotation
    (pypdf-r6 L4, the judge's V3: X X Y, where pypdf 6.21.4 counted X twice and left Y out)."""
    writer = _Writer()
    _page(writer, annotated=True)
    writer.add(6, object_stream([(9, _annotation())]))
    y = writer.add(7, xref_stream(first, {9: (2, 6, 0)}))
    one = writer.section((1, 2, 3, 4, 5, 6), b'/Size %d /Root 1 0 R /XRefStm %d' % (max(first, second), y))
    writer.add(12, object_stream([(11, b'<< /Unused true >>')]))
    x = writer.add(13, xref_stream(second, {11: (2, 12, 0)}))
    two = writer.section((12,), b'/Size %d /Root 1 0 R /XRefStm %d /Prev %d' % (max(first, second), x, one))
    writer.add(10, b'<< /Producer (synthetic writer that copies the trailer) >>')
    again = b' /XRefStm %d' % x if repeat else b''
    writer.section((10,), b'/Size %d /Root 1 0 R /Info 10 0 R%s /Prev %d' % (max(first, second), again, two))
    return bytes(writer.out)


def past_the_limit(hidden: str, entries: int = LIMIT + 1) -> bytes:
    """A classic table beside one /XRefStm of ``entries`` entries; past the limit pypdf 6.21.4 leaves that stream out,
    and what it alone lists is missing. ``hidden``:
      'annotation'  the page's annotation (object 9, in object stream 6): read from the stream at the limit;
      'encrypt'     the trailer's /Encrypt 7 0 R (object 7, in object stream 6): the constructor raises 'not a
                    dictionary' after the stream was left out (pypdf-r6 L2);
      'password'    nothing: the document is encrypted (RC4 40-bit, its /U for no password is wrong), so pypdf's
                    password test fails; it must not run before the limit is seen (pypdf-r6 L3);
      'kids'        three further page-tree kids (objects 11-13, in object stream 6): each would be searched for
                    through the whole file before the limit is seen (pypdf-r6 L1)."""
    writer = _Writer()
    members, listed, trailer = [], {}, b''
    if hidden == 'kids':
        writer.add(1, b'<< /Type /Catalog /Pages 2 0 R >>')
        writer.add(2, b'<< /Type /Pages /Kids [3 0 R 11 0 R 12 0 R 13 0 R] /Count 4 >>')
        writer.add(3, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> '
                      b'/Contents 5 0 R >>')
        writer.add(4, HELVETICA)
        writer.add(5, stream(b'', f'BT /F1 11 Tf 72 720 Td ({PAGE_TEXT}) Tj ET\n'.encode(), flate=False))
        for index, number in enumerate((11, 12, 13)):
            members.append((number, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>'))
            listed[number] = (2, 6, index)
    else:
        _page(writer, annotated=hidden == 'annotation')
        if hidden == 'annotation':
            members.append((9, _annotation()))
            listed[9] = (2, 6, 0)
        elif hidden == 'encrypt':
            members.append((7, b'<< /Filter /Standard /V 1 /R 2 /Length 40 /P -4 /O <%s> /U <%s> >>'
                            % (b'41' * 32, b'42' * 32)))
            listed[7] = (2, 6, 0)
            trailer = b' /Encrypt 7 0 R'
        elif hidden == 'password':
            members.append((9, b'<< /Unused true >>'))
            listed[9] = (2, 6, 0)
            trailer = (b' /Encrypt << /Filter /Standard /V 1 /R 2 /Length 40 /P -4 /O <%s> /U <%s> >>'
                       b' /ID [<00112233445566778899aabbccddeeff> <00112233445566778899aabbccddeeff>]'
                       % (b'41' * 32, b'42' * 32))
        else:
            raise ValueError(hidden)
    writer.add(6, object_stream(members))
    x = writer.add(8, xref_stream(entries, listed))
    writer.section((1, 2, 3, 4, 5, 6), b'/Size %d /Root 1 0 R /XRefStm %d' % (entries, x) + trailer)
    return bytes(writer.out)


def negative_count(index: bytes = b'0 -20 6 1 0 7') -> bytes:
    """A classic revision whose object 4 is written twice (the table points at the second, CURRENT), and an update
    whose cross-reference stream /Index holds a negative count. pypdf 6.21.2 lowers its running total by it, so the
    last subsection escapes the clamp to the stream's data: entries past the data shadow the table and are then
    dropped as pointing nowhere, and object 4 is found by its FIRST definition, OLDER. pypdf 6.21.4 counted the
    negative count as 0, clamped the last subsection, and read CURRENT (pypdf-r6 F1)."""
    writer = _Writer()
    writer.add(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    writer.add(2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    writer.add(3, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> '
                  b'/Contents 4 0 R >>')
    for line in (OLDER, CURRENT):
        writer.add(4, stream(b'', f'BT /F1 11 Tf 72 720 Td ({PAGE_TEXT}) Tj ET\n'
                                  f'BT /F1 11 Tf 72 600 Td ({line}) Tj ET'.encode(), flate=False))
    writer.add(5, HELVETICA)
    previous = writer.section((1, 2, 3, 4, 5), b'/Size 6 /Root 1 0 R')
    at = len(writer.out)
    data = at.to_bytes(2, 'big') + b'\x00'  # one entry (W [0 2 1]): this stream itself
    writer.out += obj(6, stream(b'/Type /XRef /Size 7 /Root 1 0 R /Prev %d /W [0 2 1] /Index [%s]' % (previous, index),
                                data, flate=False))
    writer.out += b'startxref\n%d\n%%%%EOF\n' % at
    return bytes(writer.out)
