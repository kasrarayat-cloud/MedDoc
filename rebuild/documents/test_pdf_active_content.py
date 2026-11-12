"""Finding P1: active content hidden from the PDF upload check (docs/rebuild/pypdf-6.21.4.md).

Every fixture is built here, in memory: the pre-commit hook forbids tracked PDFs, and a fixture
that is generated is one that cannot drift from the shape it claims. Payloads are harmless:
app.alert('synthetic'), a file name with no file, a URL-shaped string with no network use.

Run under each pypdf the rebuild may ship with (6.21.1, 6.21.2, 6.21.4). Measured on all three
with the base 4ebba7732 code: every HIDDEN fixture below was ACCEPTED as a supported template.
"""

import base64
from contextlib import contextmanager
from io import BytesIO
import logging
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zlib

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from . import engine, pdf_raw
from .service import DocumentError, check_original, fill_template, inspect_template

SCRIPT = b"<< /S /JavaScript /JS (app.alert\\('synthetic'\\)) >>"


# ---------------------------------------------------------------------------- builders
def form():
    """The one stock shape the engine supports: a ReportLab Helvetica text field."""
    buffer = BytesIO()
    document = canvas.Canvas(buffer, invariant=1)
    document.drawString(30, 780, "Synthetic question: Symptoms")
    document.acroForm.textfield(name="Symptoms", tooltip="Symptoms", x=30, y=700, width=300, height=30,
                                fontName="Helvetica", fontSize=10)
    document.showPage()
    document.save()
    return buffer.getvalue()


class Base:
    """The form, and what an incremental update needs to know about it."""

    def __init__(self):
        self.data = form()
        reader = PdfReader(BytesIO(self.data))
        self.root = reader.trailer.raw_get("/Root").idnum
        self.size = int(reader.trailer["/Size"])
        self.startxref = int(re.findall(rb"startxref\s+(\d+)", self.data)[-1])
        self.catalog = re.search(rb"(?:^|\n)%d 0 obj\s*(<<.*?>>)\s*endobj" % self.root, self.data, re.S).group(1)

    def catalog_with(self, extra):
        return self.catalog[:-2] + b" " + extra + b" >>"

    def scripted(self, payload=True):
        return self.catalog_with(b"/OpenAction " + SCRIPT) if payload else self.catalog


def _body(data):
    return bytearray(data if data.endswith(b"\n") else data + b"\n")


def _objects(body, objects):
    offsets = {}
    for number, content in objects:
        offsets[number] = len(body)
        body += b"%d 0 obj\n" % number + content + b"\nendobj\n"
    return offsets


def _trailer(body, size, root, prev, at, extra=b""):
    body += b"trailer\n<< /Size %d /Root %d 0 R /Prev %d %s>>\nstartxref\n%d\n%%%%EOF\n" % (size, root, prev, extra, at)
    return bytes(body)


def table_revision(data, objects, root, prev, size):
    """A classic incremental update."""
    body = _body(data)
    offsets = _objects(body, objects)
    at = len(body)
    body += b"xref\n" + b"".join(b"%d 1\n%010d 00000 n \n" % (n, offsets[n]) for n in sorted(offsets))
    return _trailer(body, size, root, prev, at)


def xref_stream_revision(data, objects, root, prev, number, *, defect=None, compressed=(), w=(1, 4, 2)):
    """An incremental update indexed by a cross-reference stream carrying one defect pypdf drops
    even with strict=True: 'type' (/Type /Xref), 'nosize', 'indexover' or 'widew' (/W [1 4 9])."""
    body = _body(data)
    offsets = _objects(body, objects)
    at = len(body)
    rows = sorted([(n, 1, offsets[n], 0) for n in offsets] + [(n, 2, c, i) for n, c, i in compressed]
                  + [(number, 1, at, 0)])
    encoded = b"".join(bytes((kind,)) + a.to_bytes(w[1], "big") + b.to_bytes(w[2], "big") for _, kind, a, b in rows)
    index = b" ".join(b"%d 1" % row[0] for row in rows)
    if defect == "indexover":
        index = index[:-1] + b"6"
    fields = b"/Type %s %s/W [%s] /Index [%s] /Root %d 0 R /Prev %d /Length %d" % (
        b"/Xref" if defect == "type" else b"/XRef", b"" if defect == "nosize" else b"/Size %d " % (number + 1),
        b"1 4 9" if defect == "widew" else b"%d %d %d" % w, index, root, prev, len(encoded))
    body += b"%d 0 obj\n<< %s >>\nstream\n" % (number, fields) + encoded + b"\nendstream\nendobj\n"
    body += b"startxref\n%d\n%%%%EOF\n" % at
    return bytes(body)


def readable_on_top(data, size):
    """A readable classic revision whose /Prev reaches the (dropped) one below it."""
    prev = int(re.findall(rb"startxref\s+(\d+)", data)[-1])
    root = int(re.findall(rb"/Root (\d+) 0 R", data)[-1])
    return table_revision(data, [(size, b"(synthetic third revision)")], root, prev, size + 1)


def object_stream(objects, encoding):
    """(dictionary entries, encoded data) of an object stream holding `objects`."""
    head, parts, offset = [], [], 0
    for number, content in objects:
        head.append(b"%d %d" % (number, offset))
        parts.append(content + b"\n")
        offset += len(content) + 1
    header = b" ".join(head) + b"\n"
    raw = header + b"".join(parts)
    entries = b"/N %d /First %d" % (len(objects), len(header))
    if encoding == "flate":
        return entries + b" /Filter /FlateDecode", zlib.compress(raw)
    if encoding == "flate-predictor":
        columns, rows, prior = 7, [], bytes(7)
        padded = raw + b" " * (-len(raw) % columns)
        for at in range(0, len(padded), columns):
            row = padded[at:at + columns]
            rows.append(b"\x02" + bytes((a - b) & 255 for a, b in zip(row, prior)))
            prior = row
        return (entries + b" /Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns %d >>" % columns,
                zlib.compress(b"".join(rows)))
    if encoding == "ascii85-flate":
        return entries + b" /Filter [/ASCII85Decode /FlateDecode]", base64.a85encode(zlib.compress(raw)) + b"~>"
    if encoding == "lzw":
        from pypdf._codecs._codecs import LzwCodec   # test-time encoder only; the scan decodes itself
        return entries + b" /Filter /LZWDecode", LzwCodec().encode(raw)
    if encoding == "none":
        return entries, raw
    raise ValueError(encoding)


def p1_trigger(defect, payload=True):
    """The finding's own shape: a catalog with an /OpenAction script in revision 2, indexed by a
    cross-reference stream with one defect, reached through /Prev from a readable revision 3."""
    base = Base()
    data = xref_stream_revision(base.data, [(base.root, base.scripted(payload))], base.root, base.startxref,
                                base.size, defect=defect, w=(1, 4, 1))
    return readable_on_top(data, base.size + 1)


def in_object_stream(encoding, *, with_type=True, payload=True):
    """The scripted catalog inside an object stream of a dropped revision."""
    base = Base()
    entries, encoded = object_stream([(base.root, base.scripted(payload))], encoding)
    stm = base.size
    head = (b"<< /Type /ObjStm " if with_type else b"<< ") + entries + b" /Length %d >>" % len(encoded)
    data = xref_stream_revision(base.data, [(stm, head + b"\nstream\n" + encoded + b"\nendstream")], base.root,
                                base.startxref, stm + 1, defect="type", compressed=[(base.root, stm, 0)])
    return readable_on_top(data, stm + 2)


def hybrid_xrefstm(payload=True):
    """A classic section whose /XRefStm, unreadable to pypdf, alone indexes the new catalog."""
    base = Base()
    body = _body(base.data)
    offsets = _objects(body, [(base.root, base.scripted(payload))])
    stm, stm_at = base.size, len(body)
    rows = bytes((1,)) + offsets[base.root].to_bytes(4, "big") + bytes((0,))
    body += (b"%d 0 obj\n<< /Type /Xref /Size %d /W [1 4 1] /Index [%d 1] /Length %d >>\nstream\n"
             % (stm, stm + 1, base.root, len(rows)) + rows + b"\nendstream\nendobj\n")
    at = len(body)
    body += b"xref\n0 1\n0000000000 65535 f \n%d 1\n%010d 00000 n \n" % (stm, stm_at)
    return _trailer(body, stm + 1, base.root, base.startxref, at, b"/XRefStm %d " % stm_at)


def first_match(payload=True):
    """Revision 2's table points the catalog at another object, so pypdf re-locates it by regex
    and takes the FIRST match in the file: the old, clean catalog. A reader that rebuilds the
    table takes the last one."""
    base = Base()
    filler = base.size
    body = _body(base.data)
    offsets = _objects(body, [(base.root, base.scripted(payload)), (filler, b"(synthetic filler)")])
    at = len(body)
    body += b"xref\n%d 1\n%010d 00000 n \n%d 1\n%010d 00000 n \n" % (base.root, offsets[filler], filler, offsets[filler])
    return _trailer(body, filler + 1, base.root, base.startxref, at)


def not_in_xref(payload=True):
    """The catalog names an object no table lists; pypdf finds its first spelling, in a comment."""
    base = Base()
    q = base.size
    names = b"<< /JavaScript << /Names [(synthetic) " + SCRIPT + b"] >> >>" if payload else b"<< >>"
    body = _body(base.data)
    body += b"%% %d 0 obj << >> endobj\n" % q
    offsets = _objects(body, [(base.root, base.catalog_with(b"/Names %d 0 R" % q)), (q, names)])
    at = len(body)
    body += b"xref\n%d 1\n%010d 00000 n \n" % (base.root, offsets[base.root])
    return _trailer(body, q + 1, base.root, base.startxref, at)


def invalid_entry(found=True, payload=True):
    """A malformed table entry: pypdf re-locates the object by its first match, or marks it free."""
    base = Base()
    body = _body(base.data)
    _objects(body, [(base.root, base.scripted(payload))])
    at = len(body)
    body += b"xref\n%d 1\n00000000xx 00000 n \n" % (base.root if found else 99)
    return _trailer(body, 100, base.root, base.startxref, at)


def rebuilt_table():
    """A subsection count that is not an integer: pypdf rebuilds the whole table."""
    base = Base()
    body = _body(base.data)
    offsets = _objects(body, [(base.root, base.catalog)])
    at = len(body)
    body += b"xref\n%d /x\n%010d 00000 n \n" % (base.root, offsets[base.root])
    return _trailer(body, base.size, base.root, base.startxref, at)


def root_recovery(payload=True):
    """The trailer's /Root lost /Type /Catalog; pypdf's root_object adopts another catalog."""
    base = Base()
    bogus = base.catalog.replace(b"/Type /Catalog", b"")
    return table_revision(base.data, [(base.root, bogus), (base.size, base.scripted(payload))], base.root,
                          base.startxref, base.size + 1)


def root_without_catalog_type():
    """No /Type /Catalog anywhere: pypdf takes the trailer's root anyway, after searching."""
    data = Base().data
    assert data.count(b"/Type /Catalog") == 1
    return data.replace(b"/Type /Catalog", b"/Type /Xatalog")          # same length: offsets stay right


def trailer_without_root():
    base = Base()
    assert base.data.count(b"/Root %d 0 R" % base.root) == 1
    return base.data.replace(b"/Root %d 0 R" % base.root, b"/Xoot %d 0 R" % base.root)


def no_eof(payload=True):
    """A last revision without %%EOF: pypdf goes back to the previous %%EOF, a viewer reads the
    last startxref."""
    base = Base()
    data = table_revision(base.data, [(base.root, base.scripted(payload))], base.root, base.startxref, base.size)
    return data[:data.rindex(b"%%EOF")]


def escaped_names(hidden=True):
    base = Base()
    catalog = base.catalog_with(b"/Open#41ction << /S /Java#53cript /#4AS (app.alert\\('synthetic'\\)) >>")
    if not hidden:
        return table_revision(base.data, [(base.root, catalog)], base.root, base.startxref, base.size)
    data = xref_stream_revision(base.data, [(base.root, catalog)], base.root, base.startxref, base.size,
                                defect="type", w=(1, 4, 1))
    return readable_on_top(data, base.size + 1)


def after_eof():
    base = Base()
    return base.data + b"%d 0 obj\n" % base.root + base.scripted() + b"\nendobj\n"


def inside_stream_data():
    """A stream whose /Length runs over the next object up to a second "endstream": the object,
    the scripted catalog of a dropped revision, is syntax only from its own "obj" keyword."""
    base = Base()
    s, xref = base.size, base.size + 1
    body = _body(base.data)
    inner = b"synthetic\nendstream\nendobj\n%d 0 obj\n" % base.root + base.scripted() + b"\nendobj\n"
    s_at = len(body)
    body += b"%d 0 obj\n<< /Length %d >>\nstream\n" % (s, len(inner)) + inner + b"\nendstream\nendobj\n"
    root_at = s_at + body[s_at:].index(b"\n%d 0 obj" % base.root) + 1
    at = len(body)
    rows = b"".join(bytes((1,)) + offset.to_bytes(4, "big") + bytes((0,)) for offset in (root_at, s_at, at))
    body += (b"%d 0 obj\n<< /Type /Xref /Size %d /W [1 4 1] /Index [%d 1 %d 1 %d 1] /Root %d 0 R /Prev %d "
             b"/Length %d >>\nstream\n" % (xref, xref + 1, base.root, s, xref, base.root, base.startxref, len(rows))
             + rows + b"\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n" % at)
    return readable_on_top(bytes(body), xref + 1)


def old_revision_script():
    """Revision 2 adds a script; revision 3 takes it out again. pypdf reads revision 3 only."""
    base = Base()
    scripted = table_revision(base.data, [(base.root, base.scripted())], base.root, base.startxref, base.size)
    prev = int(re.findall(rb"startxref\s+(\d+)", scripted)[-1])
    return table_revision(scripted, [(base.root, base.catalog)], base.root, prev, base.size)


def file_attachment():
    """A /FileAttachment annotation with no /EF, unreferenced: only the subtype rule refuses it."""
    base = Base()
    annotation = (b"<< /Type /Annot /Subtype /FileAttachment /Rect [30 30 60 60] /Contents (synthetic) "
                  b"/FS << /Type /Filespec /F (synthetic.txt) >> >>")
    return table_revision(base.data, [(base.size, annotation)], base.root, base.startxref, base.size + 1)


def container_without_object_stream_keys():
    """A stream with neither /Type /ObjStm nor /N and /First, named as a container by an xref
    stream's type-2 row. pdf.js resolves type-2 rows without looking at /Type."""
    base = Base()
    _, encoded = object_stream([(base.root, base.scripted())], "flate")
    stm = base.size
    head = b"<< /Filter /FlateDecode /Length %d >>" % len(encoded)
    data = xref_stream_revision(base.data, [(stm, head + b"\nstream\n" + encoded + b"\nendstream")], base.root,
                                base.startxref, stm + 1, defect="type", compressed=[(base.root, stm, 0)])
    return readable_on_top(data, stm + 2)


#: Shapes whose script or attachment the base code (4ebba7732) ACCEPTED, on 6.21.1, 6.21.2 and
#: 6.21.4, with the raw kind the scan must report.
HIDDEN = {
    "P1 /Type /Xref in a /Prev revision": (lambda: p1_trigger("type"), "active"),
    "P1 missing /Size in a /Prev revision": (lambda: p1_trigger("nosize"), "active"),
    "P1 /Index count above /Size in a /Prev revision": (lambda: p1_trigger("indexover"), "active"),
    "P1 /W [1 4 9] in a /Prev revision": (lambda: p1_trigger("widew"), "active"),
    "hybrid /XRefStm pypdf cannot read": (hybrid_xrefstm, "active"),
    "regex first-match recovery": (first_match, "active"),
    "object outside the xref, found by its first spelling": (not_in_xref, "active"),
    "invalid xref entry, recovered by first match": (invalid_entry, "active"),
    "root recovery to another catalog": (root_recovery, "active"),
    "last revision without %%EOF": (no_eof, "active"),
    "catalog in an object stream (Flate)": (lambda: in_object_stream("flate"), "active"),
    "catalog in an object stream (Flate + PNG predictor)": (lambda: in_object_stream("flate-predictor"), "active"),
    "catalog in an object stream (ASCII85 then Flate)": (lambda: in_object_stream("ascii85-flate"), "active"),
    "catalog in an object stream (LZW)": (lambda: in_object_stream("lzw"), "active"),
    "catalog in an object stream without /Type": (lambda: in_object_stream("flate", with_type=False), "active"),
    "object stream named only by an xref stream": (container_without_object_stream_keys, "active"),
    "#-escaped names in a dropped revision": (escaped_names, "active"),
    "objects after %%EOF": (after_eof, "active"),
    "object inside another stream's data (/Length runs over it)": (inside_stream_data, "active"),
    "script in an unreferenced old revision": (old_revision_script, "active"),
    "unreferenced /FileAttachment annotation": (file_attachment, "annotation"),
}

#: No active content, but pypdf recovers structure while reading: refused as unreadable_pdf by
#: the second layer. Each names the pypdf template it must produce (strict=True, every version).
RECOVERED = {
    "Previous trailer cannot be read: %(args)s": lambda: p1_trigger("type", payload=False),
    "XRef object at %(xref_stm)d can not be read, some object may be missing": lambda: hybrid_xrefstm(False),
    "Object ID %(idnum)d,%(generation)d ref repaired": lambda: first_match(False),
    "Object %(idnum)d %(generation)d found": lambda: not_in_xref(False),
    "entry %(num)d in Xref table invalid but object found": lambda: invalid_entry(True, False),
    "entry %(num)d in Xref table invalid; object not found": lambda: invalid_entry(False, False),
    "Invalid/Truncated xref table. Rebuilding it.": rebuilt_table,
    "Invalid Root object in trailer": lambda: root_recovery(False),
    "Possible root found at %(root_ref)r, but missing /Catalog key": root_without_catalog_type,
    'Cannot find "/Root" key in trailer': trailer_without_root,
    "CAUTION: startxref found while searching for %%EOF. The file might be truncated and some data might not be read.":
        lambda: no_eof(False),
}


def raw_kind(data):
    try:
        pdf_raw.scan(data)
    except pdf_raw.Refusal as refusal:
        return refusal.kind
    return None


@contextmanager
def pypdf_templates():
    """The templates of every pypdf warning logged inside the block."""
    records = []

    class Handler(logging.Handler):
        def emit(self, record):
            records.append(record.msg)

    handler = Handler(logging.WARNING)
    logger = logging.getLogger("pypdf")
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)


def pypdf_reports(data):
    """What this pypdf logs while reading the file the way inspection reads it: the reader, the
    catalog, every object reachable from the trailer, the pages and the fields."""
    with pypdf_templates() as seen:
        try:
            reader = PdfReader(BytesIO(data), strict=True)
            reader.root_object
            stack, visited = [reader.trailer], set()
            while stack:
                item = stack.pop()
                if hasattr(item, "idnum"):
                    if (item.idnum, item.generation) in visited:
                        continue
                    visited.add((item.idnum, item.generation))
                    item = item.get_object()
                if isinstance(item, dict):
                    stack.extend(item.values())
                elif isinstance(item, list):
                    stack.extend(item)
            len(reader.pages)
            reader.get_fields()
        except Exception:
            pass
    return seen


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, data, name="input.pdf"):
        path = self.directory / name
        path.write_bytes(data)
        return path

    def engine_code(self, data, operation="inspect"):
        """The engine in-process, exactly as the worker calls it, without the sandbox."""
        workspace = self.directory / ("engine-" + operation)
        workspace.mkdir(exist_ok=True)
        (workspace / "input.pdf").write_bytes(data)
        try:
            engine.process(workspace, {"operation": operation, "format": "pdf"})
        except engine.DocumentFailure as failure:
            return failure.code
        except Exception:
            return "invalid_document"
        return "accepted"


# ---------------------------------------------------------------------------- the raw scan alone
class RawScanAlone(Workspace):
    """pdf_raw.scan is the guarantee: every hidden shape must be refused by it with no other layer."""

    def test_every_hidden_fixture_is_refused_by_the_raw_scan_alone(self):
        for name, (build, kind) in HIDDEN.items():
            with self.subTest(name=name):
                self.assertEqual(raw_kind(build()), kind)

    def test_controls_without_active_content_pass_the_raw_scan(self):
        for name, build in {"form": form, **RECOVERED}.items():
            with self.subTest(name=name):
                self.assertIsNone(raw_kind(build()))

    def test_every_hidden_fixture_is_refused_with_the_warning_layer_switched_off(self):
        with mock.patch.object(engine, "PYPDF_RECOVERY_GUARD", False):
            for name, (build, _kind) in HIDDEN.items():
                with self.subTest(name=name):
                    self.assertEqual(self.engine_code(build()), "unsafe_upload")
                    self.assertEqual(self.engine_code(build(), "check"), "unsafe_upload")


# ---------------------------------------------------------------------------- the second layer
class SecondLayer(Workspace):
    """pypdf's own reports, and the single-catalog rule, refuse what pypdf reads differently."""

    def test_each_structure_recovery_is_reported_by_this_pypdf_and_refused_as_unreadable(self):
        for template, build in RECOVERED.items():
            with self.subTest(template=template):
                self.assertIn(template, engine.PYPDF_STRUCTURE_RECOVERIES)
                data = build()
                self.assertIn(template, pypdf_reports(data))
                self.assertEqual(self.engine_code(data), "unreadable_pdf")
                self.assertEqual(self.engine_code(data, "check"), "unreadable_pdf")

    def test_the_second_layer_alone_refuses_the_hidden_shapes_pypdf_recovers_from(self):
        # With the raw scan disabled, every hidden shape that makes pypdf recover is still refused.
        # The others (after %%EOF, an old revision, an unreferenced annotation) involve no recovery:
        # only the raw scan sees them, which is why it, not this layer, is the guarantee.
        silent = {"objects after %%EOF", "script in an unreferenced old revision",
                  "unreferenced /FileAttachment annotation"}
        with mock.patch.object(pdf_raw, "scan", lambda data: None):
            for name, (build, _kind) in HIDDEN.items():
                with self.subTest(name=name):
                    if name in silent:
                        self.assertEqual(self.engine_code(build()), "accepted")
                    else:
                        self.assertIn(self.engine_code(build()), {"unreadable_pdf", "unsafe_upload"})

    def test_root_recovery_is_refused_without_the_warning_layer(self):
        with mock.patch.object(pdf_raw, "scan", lambda data: None), \
                mock.patch.object(engine, "PYPDF_RECOVERY_GUARD", False):
            self.assertEqual(self.engine_code(root_recovery(False)), "unreadable_pdf")
            self.assertEqual(self.engine_code(trailer_without_root()), "unreadable_pdf")

    def test_ordinary_incremental_update_logs_no_recovery(self):
        base = Base()
        data = table_revision(base.data, [(base.size, b"(synthetic)")], base.root, base.startxref, base.size + 1)
        with pypdf_templates() as seen:
            self.assertEqual(self.engine_code(data), "accepted")
        self.assertFalse(set(seen) & engine.PYPDF_STRUCTURE_RECOVERIES)


# ---------------------------------------------------------------------------- the real worker
class RealWorker(Workspace):
    """Upload inspection, fill and the download check, through the sandboxed worker."""

    def test_every_hidden_fixture_is_refused_by_inspection_and_by_the_download_check(self):
        for name, (build, _kind) in HIDDEN.items():
            with self.subTest(name=name):
                path = self.write(build())
                for operation in (inspect_template, check_original):
                    with self.assertRaises(DocumentError) as caught:
                        operation(path)
                    self.assertEqual(caught.exception.code, "unsafe_upload", operation.__name__)

    def test_recovered_structure_is_unreadable_with_the_user_message(self):
        path = self.write(p1_trigger("type", payload=False))
        with self.assertRaises(DocumentError) as caught:
            inspect_template(path)
        self.assertEqual(caught.exception.code, "unreadable_pdf")
        self.assertEqual(str(caught.exception), "This PDF could not be read completely, so it cannot be checked "
                                                "for active content. Save it as a new PDF and upload it again.")
        with self.assertRaises(DocumentError) as caught:
            check_original(path)
        self.assertEqual(caught.exception.code, "unreadable_pdf")

    def test_ordinary_forms_keep_their_verdict_and_are_served(self):
        base = Base()
        incremental = table_revision(base.data, [(base.size, b"(synthetic)")], base.root, base.startxref,
                                     base.size + 1)
        for data in (base.data, incremental):
            path = self.write(data)
            self.assertEqual([field["key"] for field in inspect_template(path)["fields"]], ["Symptoms"])
            result = check_original(path)
            self.assertTrue(result["checked"])
            self.assertEqual(result["sandbox"], "landlock+seccomp")

    def test_check_serves_safe_flat_pdfs_and_refuses_what_inspection_refuses_for_safety(self):
        flat = BytesIO()
        document = canvas.Canvas(flat, invariant=1)
        document.drawString(30, 780, "Synthetic flat page")
        document.showPage()
        document.save()
        path = self.write(flat.getvalue())
        with self.assertRaises(DocumentError) as caught:
            inspect_template(path)
        self.assertEqual(caught.exception.code, "flat_pdf")                   # field rules: not the check's
        self.assertTrue(check_original(path)["checked"])
        encrypted = self.write(Base().data.replace(b"trailer\n<<", b"trailer\n<< /Encrypt 99 0 R", 1), "e.pdf")
        with self.assertRaises(DocumentError) as caught:
            check_original(encrypted)
        self.assertEqual(caught.exception.code, "unsafe_upload")

    def test_check_refuses_docx_and_changed_bytes(self):
        path = self.write(b"PK\x03\x04synthetic", "input.docx")
        with self.assertRaises(DocumentError) as caught:
            check_original(path)
        self.assertEqual(caught.exception.code, "unsupported_format")
        path = self.write(form())
        with self.assertRaises(DocumentError) as caught:
            check_original(path, expected_sha256="0" * 64)
        self.assertEqual(caught.exception.code, "source_changed")

    def test_fill_writes_exactly_what_was_scanned_and_the_export_is_clean(self):
        original = self.write(form())
        before = original.read_bytes()
        fields = inspect_template(original)["fields"]
        output = self.directory / "filled.pdf"
        fill_template(original, fields, {"Symptoms": "Synthetic symptom only"}, output)
        self.assertEqual(original.read_bytes(), before)
        exported = output.read_bytes()
        pdf_raw.scan(exported)                                    # no active content reaches an export
        self.assertEqual(PdfReader(BytesIO(exported)).get_form_text_fields()["Symptoms"], "Synthetic symptom only")
        with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=Path.read_bytes) as reads:
            engine._open_pdf(original)
        self.assertEqual(reads.call_count, 1)                     # one read: the scanned bytes are parsed

    def test_fill_of_a_hidden_fixture_writes_no_export(self):
        output = self.directory / "filled.pdf"
        with self.assertRaises(DocumentError) as caught:
            fill_template(self.write(p1_trigger("type")), [{"key": "Symptoms", "label": "Symptoms", "kind": "text",
                          "locator": {"pdf_field": "Symptoms"}}], {"Symptoms": "x"}, output)
        self.assertEqual(caught.exception.code, "unsafe_upload")
        self.assertFalse(output.exists())

    def test_too_complex_to_check_is_unreadable(self):
        path = self.write(b"%PDF-1.7\n1 0 obj\n" + b"[" * 300 + b"\nendobj\n")
        with self.assertRaises(DocumentError) as caught:
            check_original(path)
        self.assertEqual(caught.exception.code, "unreadable_pdf")

    def test_an_unreferenced_rendition_action_in_a_form_is_refused(self):
        # COV-RENDITION, as the audit built it: the supported form plus an object listed in the xref
        # that nothing points at. Accepted (and served) before; MuPDF reports the action.
        base = Base()
        for kind in (b"/Rendition", b"/Movie", b"/Sound"):
            with self.subTest(kind=kind):
                path = self.write(table_revision(base.data, [(base.size, b"<< /S " + kind + b" >>")], base.root,
                                                 base.startxref, base.size + 1))
                for operation in (inspect_template, check_original):
                    with self.assertRaises(DocumentError) as caught:
                        operation(path)
                    self.assertEqual(caught.exception.code, "unsafe_upload", operation.__name__)

    def test_a_commented_stream_keyword_before_a_stream_keeps_the_form_supported(self):
        # DELTA-1 through the real worker: a revision whose stream has "% >> stream" on the line before
        # its own keyword. Round 2 refused it as unreadable_pdf at inspection and download.
        base = Base()
        data = table_revision(base.data, [(base.size, b"<< /Length 9 >>\n% >> stream\nstream\nsynthetic\nendstream")],
                              base.root, base.startxref, base.size + 1)
        path = self.write(data)
        self.assertEqual([field["key"] for field in inspect_template(path)["fields"]], ["Symptoms"])
        self.assertTrue(check_original(path)["checked"])


# ---------------------------------------------------------------------------- scanner details
def minimal(objects, trailer=b"<< /Root 1 0 R >>"):
    """A small PDF; the scan needs no valid xref, so neither do these."""
    body = b"%PDF-1.7\n" + b"".join(b"%d 0 obj\n%s\nendobj\n" % (n, c) for n, c in objects)
    return body + b"trailer\n" + trailer + b"\n%%EOF\n"


def objstm(objects, extra=b"", encoding="flate"):
    entries, encoded = object_stream(objects, encoding)
    return b"<< /Type /ObjStm " + entries + extra + b" /Length %d >>\nstream\n" % len(encoded) + encoded + b"\nendstream"


class ScannerDetails(unittest.TestCase):
    def kind(self, data):
        return raw_kind(data)

    def test_names_are_compared_decoded(self):
        self.assertEqual(self.kind(minimal([(1, b"<< /Open#41ction 2 0 R >>")])), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< /#4Aava#53cript 2 0 R >>")])), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< /#4AS (synthetic) >>")])), "active")
        # An invalid escape keeps its '#' in every reader, so it never spells a forbidden name.
        self.assertIsNone(self.kind(minimal([(1, b"<< /OpenActio#6 1 >>")])))

    def test_strings_and_comments_cannot_hide_a_forbidden_name(self):
        # A reader that does not balance nested parentheses would end this string early.
        self.assertEqual(self.kind(minimal([(1, b"<< /T (a(b) /A 2 0 R ) >>")])), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< /T (a(b) /JS (app.alert\\('synthetic'\\)) ) >>")])), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< >>")]) + b"% /OpenAction\n"), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< >>")]) + b"% 9 0 obj << /AA 2 0 R >> endobj\n"), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< /T <2F4A53> >>")]) + b"% /XFA [(x) 2 0 R]\n"), "active")

    def test_a_header_glued_to_its_number_is_still_an_object(self):
        # pdf.js reads "9 0obj" as the header "9 0 obj"; here it sits inside another stream's data,
        # where only a one-object parse at the keyword can see the key.
        data = b"synthetic\n9 0obj << /A 5 0 R >> endobj\n"
        stream = b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"
        self.assertEqual(self.kind(minimal([(3, stream)])), "active")
        self.assertEqual(self.kind(minimal([(3, stream.replace(b"0obj", b"0 xobj"))])), None)

    def test_ordinary_names_in_values_and_arrays_are_not_keys(self):
        for content in (b"<< /Type /Encoding /Differences [65 /A /B /C /JS /AA] >>",
                        b"<< /S /A /P 2 0 R >>", b"<< /Title (/A /B) /Subject (/JS) >>",
                        b"<< /O /Layout /Placement /Block >>"):
            with self.subTest(content=content):
                self.assertIsNone(self.kind(minimal([(1, content)])))

    def test_a_malformed_dictionary_is_judged_on_every_name(self):
        # pdf.js skips the stray 7 and reads /A as a key; a strict pairing would call /A a value.
        self.assertEqual(self.kind(minimal([(1, b"<< 7 /A << /S /GoTo /D [0 /Fit] >> >>")])), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< /K 1 2 /A 3 0 R >>")])), "active")

    def test_a_malformed_object_is_judged_on_every_name_inside_it(self):
        # Found by differential fuzzing against lenient pypdf: after junk inside an array, a lenient
        # reader drops the array and its dictionary and reads the rest as entries of the enclosing one.
        glyphs = b"<< /Type /Font /Encoding << /Differences [0 /space /two r /five /A /B] >> >>"
        self.assertEqual(self.kind(minimal([(1, glyphs)])), "active")
        widths = b"<< /Type /Font /W [83 [333\xe7389 278] 172 /Subtype /FileAttachment 174 611] >>"
        self.assertEqual(self.kind(minimal([(1, widths)])), "annotation")
        hidden = b"<< /Type /Font /Encoding << /Differences [0 /space /<two /A /B /C> /D] >> >>"
        self.assertEqual(self.kind(minimal([(1, hidden)])), "active")   # names swallowed by a bad hex string
        # The same objects, well formed, are ordinary fonts.
        self.assertIsNone(self.kind(minimal([(1, glyphs.replace(b" r ", b" "))])))
        self.assertIsNone(self.kind(minimal([(1, b"<< /Type /Font /W [83 [333 278] 172 [500] 174 611] >>")])))

    def test_an_r_that_ends_no_reference_makes_the_object_malformed(self):
        # Found by differential fuzzing: PDFium ends an array at an R that follows no "N G", and
        # lenient pypdf gives up there; both then read the rest of the array into the enclosing
        # dictionary, here as a font's /Subtype /FileAttachment.
        kept = b"<< /Type /Font /W [ 1 [ 722 R 556 ] 2 /Subtype /FileAttachment [ 3 ] ] >>"
        skipped = b"<< /Type /Font /Widths [ 722 R 556 /Subtype /FileAttachment ] >>"
        past_kept_items = b"<< /Type /Font /W [ " + b"(x) " * 64 + b"1 R 556 /Subtype /FileAttachment ] >>"
        for content in (kept, skipped, past_kept_items):
            with self.subTest(content=content[:30]):
                self.assertEqual(self.kind(minimal([(1, content)])), "annotation")
                # With a real reference the same names stay array items, as every reader reads them.
                reference = content.replace(b"722 R", b"722 0 R").replace(b"1 R", b"1 0 R")
                self.assertIsNone(self.kind(minimal([(1, reference)])))

    def test_a_policy_name_outside_every_container_is_refused(self):
        # Found by differential fuzzing: lenient pypdf skips an unreadable token up to the next
        # whitespace, so "junk>>" carries the trailer past its end, and the names after startxref
        # became its entries.
        overrun = (b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Size 2 /Root 1 0 R junk>>\n"
                   b"startxref\n9/Subtype /FileAttachment\n%%EOF\n")
        self.assertEqual(self.kind(overrun), "annotation")
        self.assertEqual(self.kind(minimal([(1, b"<< >>"), (9, b"/AA")])), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< >>"), (9, b"/Encrypt")])), "encrypted")
        # A name that is an ordinary object's whole value stays ordinary.
        self.assertIsNone(self.kind(minimal([(1, b"<< >>"), (9, b"/FlateDecode")])))

    def test_a_malformed_stream_object_is_unreadable(self):
        # Found by differential fuzzing: "/Helv 4 stream 0 R>>>>>>" made lenient pypdf skip every
        # ">>" and read the form's data, up to "endobj", as entries of its font dictionary.
        script = b"/OpenAction << /S /JavaScript /JS (app.alert\\('synthetic'\\)) >>"
        attachment = b"/Subtype /FileAttachment"

        def xobject(font, payload):
            data = b"x" * 20 + b"\n" + payload
            return (b"<< /Type /XObject /Subtype /Form /Resources << /Font << " + font
                    + b" >> >> /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")

        def hidden(font):
            inner = b"9 0 obj " + xobject(font, attachment) + b" endobj"
            return b"<< /Length %d >>\nstream\n" % len(inner) + inner + b"\nendstream"

        broken, ordinary = b"/Helv 4 stream 0 R", b"/Helv 4 0 R"
        self.assertEqual(self.kind(minimal([(3, xobject(broken, script))])), "unreadable")
        self.assertEqual(self.kind(minimal([(3, xobject(broken, attachment))])), "unreadable")
        self.assertEqual(self.kind(minimal([(5, hidden(broken))])), "unreadable")   # a one-object parse
        # A key without its value is malformed too.
        self.assertEqual(self.kind(minimal([(3, xobject(b"/Helv", attachment))])), "unreadable")
        # After a well-formed dictionary the same data is ordinary stream content.
        self.assertIsNone(self.kind(minimal([(3, xobject(ordinary, script))])))
        self.assertIsNone(self.kind(minimal([(5, hidden(ordinary))])))

    def test_decoding_parameters_from_a_malformed_dictionary_are_not_trusted(self):
        # Found by differential fuzzing: after the junk "o" the scan kept no more entries, lost
        # /Filter and read the compressed bytes as they were, while pdf.js and pypdf re-pair the
        # entries, inflate the data and find a link with a URI action.
        def stream_object(head, encoded):
            return head + b" /Length %d >>\nstream\n" % len(encoded) + encoded + b"\nendstream"

        link = b"<< /Type /Annot /Subtype /Link /A << /S /URI /URI (synthetic) >> >>"
        entries, encoded = object_stream([(5, link)], "flate")
        self.assertEqual(self.kind(minimal([(3, stream_object(b"<< /Type /ObjStm " + entries, encoded))])), "active")
        broken = b"<< /Type /ObjStm /Length 29 0 o " + entries
        self.assertEqual(self.kind(minimal([(3, stream_object(broken, encoded))])), "unreadable")
        # A predictor defined twice, or read from a malformed dictionary, is not trusted either.
        entries, encoded = object_stream([(5, b"<< /Type /Catalog >>")], "flate-predictor")
        parms = b"<< /Predictor 12 /Columns 7 >>"
        self.assertIn(parms, entries)
        twice = entries.replace(parms, b"<< /Predictor 12 /Predictor 1 /Columns 7 >>")
        indirect = entries.replace(parms, b"9 0 R")
        for objects in ([(3, stream_object(b"<< /Type /ObjStm " + twice, encoded))],
                        [(3, stream_object(b"<< /Type /ObjStm " + indirect, encoded)),
                         (9, b"<< /Predictor 12 junk /Columns 7 >>")]):
            with self.subTest(parms=objects[-1][1][-48:]):
                self.assertEqual(self.kind(minimal(objects)), "unreadable")
        # Well formed, the same parameters decode as before.
        self.assertIsNone(self.kind(minimal([(3, stream_object(b"<< /Type /ObjStm " + entries, encoded))])))

    def test_a_stream_start_this_scan_did_not_read_is_unreadable(self):
        # Found by fuzzing, and pdf.js reported the link both times: a "[" before /Length, or in
        # "29 0[ R", opened an array here that never closed, so the object stream was never
        # decoded. pdf.js and PDFium skip any token that is not a name where a key belongs; PDFium
        # also reads a string's contents there as entries.
        link = b"<< /Type /Annot /Subtype /Link /A << /S /URI /URI (synthetic) >> >>"
        entries, encoded = object_stream([(5, link)], "flate")
        tail = b" /Length %d >>\nstream\n" % len(encoded) + encoded + b"\nendstream"
        for head in (b"<< /Type /ObjStm [ " + entries, b"<< /Type /ObjStm ( " + entries,
                     b"<< /Type /ObjStm << " + entries, b"<< /Type /ObjStm " + entries + b" /K 9 0[ R"):
            with self.subTest(head=head[-12:]):
                self.assertEqual(self.kind(minimal([(3, head + tail)])), "unreadable")
        # Read as a stream, the same object stream is decoded and its link refused.
        self.assertEqual(self.kind(minimal([(3, b"<< /Type /ObjStm " + entries + tail)])), "active")

    def test_actions_are_refused_by_their_type_even_without_the_key_that_reaches_them(self):
        for kind in (b"/URI", b"/Launch", b"/GoToR", b"/GoToE", b"/SubmitForm", b"/RichMediaExecute"):
            with self.subTest(kind=kind):
                self.assertEqual(self.kind(minimal([(1, b"<< /S " + kind + b" /F (synthetic) >>")])), "active")

    def test_rendition_movie_and_sound_actions_are_refused_wherever_they_are(self):
        # COV-RENDITION (2026-11-01): an unreferenced << /S /Rendition >> was accepted while MuPDF
        # reports it as an action (its forbidden /S set names /Rendition). Nothing reached it, so
        # nothing could run it; an action dictionary is refused wherever it is all the same.
        for kind in (b"/Rendition", b"/Movie", b"/Sound"):
            with self.subTest(kind=kind):
                self.assertEqual(self.kind(minimal([(1, b"<< /Type /Catalog >>"), (13, b"<< /S " + kind + b" >>")])),
                                 "active")
        # A navigation action and the other inert /S values no reader reports stay accepted.
        for kind in (b"/GoTo /D [3 0 R /Fit]", b"/SetOCGState /State [/ON]", b"/Trans", b"/Transparency"):
            with self.subTest(kind=kind):
                self.assertIsNone(self.kind(minimal([(1, b"<< /Type /Catalog >>"), (13, b"<< /S " + kind + b" >>")])))

    def test_a_commented_stream_keyword_before_a_stream_the_scan_read_is_comment_text(self):
        # DELTA-1 (2026-11-01): round 2's one-pass search tested the ">>" inside a comment between a
        # dictionary and its own "stream" keyword, and refused "% >> stream" there as a stream it had
        # not read. Every lexer skips that comment; round 1's search accepted these exactly.
        for gap in (b"\n% >> stream\n", b"%>>stream\n\n", b" % >> stream\n", b"\n%\n% >>  stream x\n\n"):
            with self.subTest(gap=gap):
                data = minimal([(1, b"<< /Type /Catalog >>"),
                                (3, b"<< /Length 9 >>" + gap + b"stream\nsynthetic\nendstream")])
                self.assertIsNone(self.kind(data))
        # The audit's own input (a fuzzed object stream, 169 bytes): round 1 accepted it, round 2 did not.
        self.assertIsNone(self.kind(b"%PDF-1.7\n3 0 obj\n<< /Type /Obj\x87tm /N 2 /First 9 /Length 38 >>\n% >> "
                                    b"stream\nstream\n5 0 6 21\n<< /Type /Catalog >>\n[1 2 3]\n\nendstream\nendobj\n"
                                    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"))
        # The comment does not stop the stream being read: an object stream behind it is decoded.
        link = b"<< /Type /Annot /Subtype /Link /A << /S /URI /URI (synthetic) >> >>"
        entries, encoded = object_stream([(5, link)], "flate")
        self.assertEqual(self.kind(minimal([(3, b"<< /Type /ObjStm " + entries + b" /Length %d >>\n%% >> stream\n"
                                                 b"stream\n" % len(encoded) + encoded + b"\nendstream")])), "active")
        # Not reopened: a commented ">> stream" after a dictionary that starts NO stream the scan read
        # is still refused, exactly as both earlier rounds refused it.
        self.assertEqual(self.kind(minimal([(1, b"<< /Type /Catalog >>"), (3, b"<< /K 1 >>\n% >> stream\nx")])),
                         "unreadable")
        self.assertEqual(self.kind(minimal([(3, b"[ << /Length 9 >>\n% >> stream\nstream\nsynthetic\nendstream")])),
                         "unreadable")

    def test_every_definition_of_a_duplicated_key_is_judged(self):
        # pypdf refuses duplicate keys; pdf.js keeps the LAST definition, so judging only the
        # first would let "/S /GoTo /S /GoToR" through.
        self.assertEqual(self.kind(minimal([(1, b"<< /S /GoTo /S /GoToR /F (synthetic.pdf) >>")])), "active")
        self.assertEqual(self.kind(minimal([(1, b"<< /Subtype /Text /Subtype /FileAttachment >>")])), "annotation")
        self.assertEqual(self.kind(minimal([(1, b"<< /Type /XObject /Type /EmbeddedFile >>")])), "active")
        # An object stream whose filter is defined twice cannot be decoded without guessing which.
        twice = objstm([(5, b"<< /Type /Catalog >>")], b" /Filter /ASCIIHexDecode")
        self.assertEqual(self.kind(minimal([(3, twice)])), "unreadable")

    def test_encryption_anywhere_is_refused(self):
        self.assertEqual(self.kind(minimal([(1, b"<< >>")], b"<< /Root 1 0 R /Encrypt 2 0 R >>")), "encrypted")
        self.assertEqual(self.kind(minimal([(1, b"<< >>")]) + b"% trailer << /Encrypt 2 0 R >>\n"), "encrypted")

    def test_object_stream_parameters_are_resolved_from_every_definition(self):
        catalog = b"<< /Type /Catalog /OpenAction " + SCRIPT + b" >>"
        _, encoded = object_stream([(5, catalog)], "flate")
        indirect = (b"<< /Type /ObjStm /N 1 /First 4 /Filter 9 0 R /Length 8 0 R >>\nstream\n" + encoded
                    + b"\nendstream")
        self.assertEqual(self.kind(minimal([(3, indirect), (8, b"%d" % len(encoded)), (9, b"/FlateDecode")])), "active")
        # pdf.js reads /F as /Filter when it is present.
        alias = b"<< /Type /ObjStm /N 1 /First 4 /F /FlateDecode /Length %d >>\nstream\n" % len(encoded) + encoded + b"\nendstream"
        self.assertEqual(self.kind(minimal([(3, alias)])), "active")
        # Two definitions of the filter: both are decoded and checked.
        both = minimal([(9, b"/ASCIIHexDecode"), (3, indirect), (8, b"%d" % len(encoded)), (9, b"/FlateDecode")])
        self.assertEqual(self.kind(both), "unreadable")          # the ASCIIHex reading is not decodable

    def test_an_object_stream_that_cannot_be_read_completely_is_unreadable(self):
        catalog = b"<< /Type /Catalog >>"
        cases = {
            "corrupt Flate": objstm([(5, catalog)]).replace(b"stream\nx", b"stream\nX", 1),
            "unknown filter": objstm([(5, catalog)], b" /Filter /JBIG2Decode", "none"),
            "crypt filter": objstm([(5, catalog)], b" /Filter /Crypt", "none"),
            "unresolved indirect length": b"<< /Type /ObjStm /N 1 /First 4 /Length 77 0 R >>\nstream\n5 0 <<>>\nendstream",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.kind(minimal([(3, content)])), "unreadable")

    def test_object_streams_inside_object_streams_are_read(self):
        inner = objstm([(6, b"<< /Type /Catalog /OpenAction " + SCRIPT + b" >>")])
        self.assertEqual(self.kind(minimal([(3, objstm([(5, inner)]))])), "active")

    def test_clean_object_streams_pass(self):
        for encoding in ("flate", "flate-predictor", "ascii85-flate", "lzw", "none"):
            with self.subTest(encoding=encoding):
                self.assertIsNone(self.kind(minimal([(3, objstm([(5, b"<< /Type /Catalog >>"), (6, b"[1 2 3]")],
                                                                encoding=encoding))])))

    def test_bounds_refuse_as_unreadable(self):
        self.assertEqual(self.kind(b"%PDF-1.7\n" + b"[" * (pdf_raw.MAX_DEPTH + 1)), "unreadable")
        self.assertEqual(self.kind(b"%PDF-1.7\n" + b"%1 0 obj\n" * (pdf_raw.MAX_HIDDEN_ANCHORS + 1)), "unreadable")
        # The budget grows with the file (budget()), so a tiny MAX_WORK needs the growth switched off.
        with mock.patch.object(pdf_raw, "MAX_WORK", 50), mock.patch.object(pdf_raw, "BYTES_PER_WORK", 1 << 40):
            self.assertEqual(self.kind(form()), "unreadable")
        with mock.patch.object(pdf_raw, "MAX_DECODED", 100):
            self.assertEqual(self.kind(minimal([(3, objstm([(5, b"[" + b"0 " * 200 + b"]")]))])), "unreadable")

    def test_the_budget_grows_with_the_file_so_an_ordinary_large_graph_passes(self):
        # COST-2: a fixed 1,000,000-unit budget refused a benign large structured file before the
        # policy ran. The budget is MAX_WORK + size/BYTES_PER_WORK, so a 10 MiB file has room while a
        # crafted one is still bounded. A 6 MiB graph of 90,000 small dicts spends MORE than the old
        # fixed budget and now passes, because the budget grew with the file.
        graph = b"%PDF-1.7\n" + b"".join(b"%d 0 obj\n<< /K %d /P (%s) >>\nendobj\n" % (i, i, b"x" * 32)
                                          for i in range(1, 90_000))
        graph += b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
        self.assertGreater(len(graph), 6 << 20)
        stats = {}
        pdf_raw.scan(graph, stats)                       # no refusal
        self.assertGreater(stats["work"], pdf_raw.MAX_WORK)      # would have exhausted the old fixed budget
        self.assertLess(stats["work"], stats["budget"])
        self.assertGreater(stats["budget"], 2 * pdf_raw.MAX_WORK)

    @staticmethod
    def reason(data):
        try:
            pdf_raw.scan(data)
        except pdf_raw.Refusal as refusal:
            return refusal.reason
        return None

    def test_work_that_used_to_escape_the_budget_is_charged(self):
        # These shapes ran 15 s to over 30 s for a handful of charged units, because a regex
        # look-ahead or a decoder loop crossed bytes nobody counted (findings COST-1). Each is now
        # LINEAR and charged: it either finishes small and fast, or is refused by the budget it now
        # spends. test_cost_shapes_finish_far_inside_the_worker measures the wall cost; here the
        # concern is that the work is counted.
        # 5,000 "obj" anchors on their own comment lines: the per-anchor gap look-ahead used to
        # cross every later line (quadratic, ~15 s). Memoized, it is linear and cheap now, and the
        # units scale with the count rather than its square.
        small = {}
        pdf_raw.scan(b"%PDF-1.7\n" + b"%1 0 obj 5\n" * 5000, small)
        large = {}
        pdf_raw.scan(b"%PDF-1.7\n" + b"%1 0 obj 5\n" * 10000, large)
        self.assertLess(large["work"], 3 * small["work"])            # linear, not quadratic
        self.assertLess(small["work"], pdf_raw.MAX_WORK)
        # One comment line of 400,000 "/A" used to cross the rest of the line per name (~19 s); the
        # line end is found once now, so it passes quickly with work proportional to the line, not
        # its square. (A genuinely oversized charged loop still hits the budget: the two below.)
        wide = {}
        pdf_raw.scan(b"%PDF-1.7\n1 0 obj\n<< >>\n%" + b"/A%" * 400_000 + b"\nendobj\n%%EOF\n", wide)
        self.assertLess(wide["work"], wide["budget"])
        defined = b"".join(b"9 0 obj /F%d endobj\n" % i for i in range(pdf_raw.MAX_VARIANTS + 1))
        stream = b"<< /Type /ObjStm /N 1 /First 4 /Filter 9 0 R /Length 5 >>\nstream\n0 0 1\nendstream"
        self.assertEqual(self.reason(minimal([(3, stream)]) + defined), "a stream parameter is defined in too many ways")
        rows = zlib.compress(b"\x02" * 2_100_000)
        xref = b"<< /Type /XRef /W [1 0 0] /Size 2 /Filter /FlateDecode /Length %d >>\nstream\n" % len(rows) + rows + b"\nendstream"
        self.assertEqual(self.reason(minimal([(3, xref)])), "work limit")
        content = b"5 0\n[" + b"0 " * 600_000 + b"]"
        rows = bytearray(2 * len(content))
        rows[1::2] = content                                    # PNG rows of type 0, one byte each
        encoded = zlib.compress(bytes(rows))
        predicted = (b"<< /Type /ObjStm /N 1 /First 4 /Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 1 >> "
                     b"/Length %d >>\nstream\n" % len(encoded) + encoded + b"\nendstream")
        self.assertEqual(self.reason(minimal([(3, predicted)])), "work limit")
        with mock.patch.object(pdf_raw, "MAX_WORK", 10_000_000):     # the same rows decode when affordable
            self.assertIsNone(self.reason(minimal([(3, predicted)])))

    def test_work_on_the_ordinary_form_is_small(self):
        stats = {}
        pdf_raw.scan(form(), stats)
        self.assertLess(stats["work"], pdf_raw.MAX_WORK // 100)


def _cost_shapes():
    """The COST-1 lens shapes (refute-p1/robustness-cost), each at a size that ran 12-30 s on the
    code before the fix. Harmless: no shape names an action or a script. Built raw; the scan needs
    no valid xref. Each is paired with the verdict the policy gives it."""
    n = b"1" * 64_000
    yield "num_token", minimal([(1, b"<< /Note " + n + b"x >>")]), None
    yield "num_token_after_eof", minimal([(1, b"<< >>")]) + n + b"x\n", None
    yield "array_junk", minimal([(1, b"<< /Length 0 /BBox [ " + b"1" * 32_000 + b"x ] >>\nstream\n\nendstream")]), "unreadable"
    yield "stream_start", minimal([(1, b"<< /Length %d >>\nstream\n" % (4 * 24_000) + b"%>>\n" * 24_000 + b"endstream")]), None
    yield "gap_comment", minimal([(1, b"<< >>")]) + b"%" + b"/A%" * 40_000 + b"\n", None
    yield "gap_anchors", minimal([(1, b"<< /Length %d >>\nstream\n" % (38 * 10_000)
                                  + (b"0obj 5 %" + b"x" * 30) * 10_000 + b"\nendstream")]), None
    objstm = (b"<< /Type /ObjStm /N 500 /First 2000 /Length %d /Filter /FlateDecode >>\nstream\n"
              % len(zlib.compress(b"1 0 " * 500 + b" " * (2 << 20) + b"<<>>"))
              + zlib.compress(b"1 0 " * 500 + b" " * (2 << 20) + b"<<>>") + b"\nendstream")
    yield "objstm_index", minimal([(1, objstm)]), None
    wide = (b"<< /Type /ObjStm /N 0 /First 0 /Length %d /Filter /FlateDecode /DecodeParms << /Predictor 12 "
            b"/Columns 1048576 /Colors 32 /BitsPerComponent 16 >> >>\nstream\n" % len(zlib.compress(b"\x00"))
            + zlib.compress(b"\x00") + b"\nendstream")
    yield "predict_wide", minimal([(2 + i, wide) for i in range(30)]), None


class ScanCost(unittest.TestCase):
    """Finding COST-1: shapes that escaped the work budget. Each is scanned in a child capped at
    CAP seconds of CPU (below the worker's 12 s): a regression that makes one super-linear again is
    killed by the cap and fails here, rather than hanging. On the fixed scanner each is well under."""

    CAP = 10

    def _scan_capped(self, data):
        import os
        import resource
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (self.CAP, self.CAP))
                import time
                t = time.process_time()
                try:
                    pdf_raw.scan(data)
                    verdict = "pass"
                except pdf_raw.Refusal as exc:
                    verdict = exc.kind
                os.write(w, ("%s\t%.3f" % (verdict, time.process_time() - t)).encode())
            finally:
                os._exit(0)
        os.close(w)
        _, status, usage = os.wait4(pid, 0)
        msg = os.read(r, 4096).decode()
        os.close(r)
        killed = os.WIFSIGNALED(status)
        verdict = None if not msg else (None if msg.split("\t")[0] == "pass" else msg.split("\t")[0])
        return killed, verdict, usage.ru_utime + usage.ru_stime

    def test_cost_shapes_finish_far_inside_the_worker(self):
        for name, data, expect in _cost_shapes():
            with self.subTest(name=name):
                killed, verdict, cpu = self._scan_capped(data)
                self.assertFalse(killed, "%s was SIGKILLed at the %d s CPU cap (%.2f s)" % (name, self.CAP, cpu))
                self.assertLess(cpu, self.CAP - 2, "%s used %.2f s of CPU" % (name, cpu))
                self.assertEqual(verdict, expect, "%s verdict %r (CPU %.2f s)" % (name, verdict, cpu))


if __name__ == "__main__":
    unittest.main()
