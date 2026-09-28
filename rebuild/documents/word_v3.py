"""Contract v3: answer-area detection and faithful filling for ordinary Word (.docx) forms.

Runs only inside the isolated worker, like engine.py. It reads the package with the standard library and lxml,
never executes or fetches anything, and writes an export by replacing ONLY the XML parts it changed; every other
part is copied byte for byte from the original.

A v3 mapping field:
    {"key": "v3_12", "label": "...", "kind": "text|long_text|date|choice|multi_choice|checkbox|signature",
     "context": "...", "options": [...],
     "locator": {"contract": "v3", "part": "word/document.xml", "slot": "b/tbl[0]/tr[2]/tc[1]",
                 "target": {...writer-specific...}, "fingerprint": "<sha256 of the anchor element's XML>"}}

Slot paths use the grammar of the neutral enumerator used for ground truth:
    b (body) | hf (header/footer root) / tbl[i] / tr[j] / tc[k] / p[n] / sdt[s] / txbx[t] / ff[f] / glyphs
indices count same-kind children in document order - except that a table's rows and a row's cells are counted through
the content controls and custom XML wrapping them (table_rows_of / row_cells_of), so a wrapped cell keeps its column.

Detection is deterministic. Areas it is unsure about are reported as notes (never silently dropped, never
guessed); a doctor's manual mapping is recorded separately as an assisted correction.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field as dfield

from lxml import etree

if __package__:
    from .mapping_limits import MAX_MAPPING_LABEL, MAX_MAPPING_CONTEXT
    from . import source_policy
else:  # isolated worker imports directly before closing its filesystem
    from mapping_limits import MAX_MAPPING_LABEL, MAX_MAPPING_CONTEXT
    import source_policy

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NS = {"w": W, "w14": W14, "mc": MC}
CONTRACT = "v3"
MAX_FIELDS = 1500
MAX_ANSWER = 100_000
FLOATING_INITIALS_REFUSAL = ("Filled export is unavailable for this form's floating initials boxes: answer reflow can "
                           "clip or move a box away from its question. The unchanged original remains available. "
                           "This layout needs qualification before any nonempty export.")


def q(tag: str) -> str:
    prefix, local = tag.split(":")
    return "{%s}%s" % (NS[prefix], local)


class V3Failure(ValueError):
    def __init__(self, message, code="invalid_document"):
        super().__init__(message)
        self.code = code


def fail(message, code="invalid_document"):
    raise V3Failure(message, code)


# ─── package ───────────────────────────────────────────────────────────────────────────────────────────────────────

PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_blank_text=False)
HEADER_FOOTER = re.compile(r"^word/(header|footer)\d*\.xml$")


class Package:
    """The original package: raw bytes of every part, and parsed trees for the parts we read or write."""

    def __init__(self, data: bytes):
        self.data = data
        self.zip = zipfile.ZipFile(io.BytesIO(data))
        self.infos = self.zip.infolist()
        self.names = [i.filename for i in self.infos]
        self.trees = {}
        self._alive = {}

    def tree(self, part):
        if part not in self.trees:
            root = etree.fromstring(self.zip.read(part), PARSER)
            self.trees[part] = root
            # lxml element proxies are created on demand and freed when unreferenced, after which id() values are
            # reused by other elements. Holding every original element keeps its proxy (and its id) unique and
            # stable for the life of the package - the detector's claims and caches are keyed by id().
            self._alive[part] = list(root.iter())
        return self.trees[part]

    def content_parts(self):
        parts = ["word/document.xml"]
        parts += sorted(n for n in self.names if HEADER_FOOTER.match(n))
        return parts

    def displayed_parts(self):
        """Header/footer parts some section actually shows: a 'first' header only where the section has a
        different first page, an 'even' one only when odd/even headers are on. Sections without their own
        reference inherit the previous section's."""
        if getattr(self, "_displayed", None) is not None:
            return self._displayed
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        targets = {}
        rels_name = "word/_rels/document.xml.rels"
        if rels_name in self.names:
            for rel in etree.fromstring(self.zip.read(rels_name), PARSER):
                target = (rel.get("Target") or "").lstrip("/")
                targets[rel.get("Id")] = target if target.startswith("word/") else "word/" + target
        even_on = False
        if "word/settings.xml" in self.names:
            settings = self.tree("word/settings.xml")
            flag = settings.find(q("w:evenAndOddHeaders"))
            even_on = flag is not None and (flag.get(q("w:val")) or "1") not in ("0", "false")
        shown = set()
        doc = self.tree("word/document.xml")
        current = {}
        for sect in doc.iter(q("w:sectPr")):
            for tag in ("w:headerReference", "w:footerReference"):
                for ref in sect.findall(q(tag)):
                    current[(tag, ref.get(q("w:type")) or "default")] = targets.get(ref.get("{%s}id" % rel_ns))
            title = sect.find(q("w:titlePg"))
            title_on = title is not None and (title.get(q("w:val")) or "1") not in ("0", "false")
            for (tag, kind), target in current.items():
                if target and (kind == "default" or (kind == "first" and title_on) or (kind == "even" and even_on)):
                    shown.add(target)
        self._displayed = ["word/document.xml"] + [p for p in self.content_parts()[1:] if p in shown]
        return self._displayed

    def write(self, changed: dict) -> bytes:
        """A new package: changed parts re-serialized, every other entry copied byte for byte (same order, same
        compression, same metadata)."""
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as target:
            for info in self.infos:
                if info.filename in changed:
                    xml = etree.tostring(changed[info.filename], xml_declaration=True, encoding="UTF-8", standalone=True)
                    clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    clone.compress_type = zipfile.ZIP_DEFLATED
                    clone.external_attr = info.external_attr
                    target.writestr(clone, xml)
                else:
                    target.writestr(info, self.zip.read(info.filename), compress_type=info.compress_type)
        return out.getvalue()


def open_package(data: bytes) -> Package:
    """Safety checks, relaxed only where v2 refused structure rather than danger: content controls, fields,
    text boxes, hidden text and hyperlinks are supported; macros, active content, embedded packages, DTDs,
    non-hyperlink external relationships and tracked changes are refused by name."""
    try:
        package = Package(data)
    except zipfile.BadZipFile:
        fail("The DOCX package is malformed.")
    infos = package.infos
    names = package.names
    if len(infos) > 2000 or len(names) != len(set(names)):
        fail("DOCX contains duplicate entries or too many parts.", "unsafe_upload")
    if sum(i.file_size for i in infos) > 80 * 1024 * 1024:
        fail("DOCX expands beyond the processing limit.", "unsafe_upload")
    if "word/document.xml" not in names or "[Content_Types].xml" not in names:
        fail("The upload is not a DOCX document.")
    for info in infos:
        name = info.filename
        lower = name.lower()
        mode = info.external_attr >> 16
        if name.startswith("/") or "\\" in name or ".." in name.split("/") or ":" in name or (mode & 0o170000) == 0o120000 \
                or info.flag_bits & 1:
            fail("DOCX contains an unsafe package entry.", "unsafe_upload")
        if any(marker in lower for marker in ("vbaproject", "activex", "embeddings/", "afchunk")) or lower.startswith("word/macros"):
            fail("Macros, active content and embedded documents are not supported. Save the form as an ordinary .docx without them.",
                 "unsafe_upload")
        if info.file_size > 30 * 1024 * 1024 or info.file_size > max(1, info.compress_size) * 400:
            fail("DOCX compression exceeds the safe processing limit.", "unsafe_upload")
        if lower.endswith((".xml", ".rels")):
            raw = package.zip.read(info)
            upper = raw[:4096].upper()
            if b"<!DOCTYPE" in upper or b"<!ENTITY" in raw.upper():
                fail("XML entities and document types are not supported.", "unsafe_upload")
            tree = etree.fromstring(raw, PARSER)
            if tree.getroottree().docinfo.doctype:
                fail("XML entities and document types are not supported.", "unsafe_upload")
            if lower.endswith(".rels"):
                for rel in tree:
                    kind = (rel.get("Type") or "").lower()
                    if any(m in kind for m in ("vbaproject", "vbasignature", "activex", "oleobject")) or kind.endswith(("/package", "/afchunk", "/control")):
                        fail("Macros, active content and embedded documents are not supported.", "unsafe_upload")
                    if (rel.get("TargetMode") or "").lower() == "external" and not kind.endswith(("/hyperlink", "/attachedtemplate")):
                        fail("The form links to an external resource (for example a linked image). Embed it or remove the link; "
                             "external resources are never fetched.", "unsafe_upload")
            if lower == "[content_types].xml":
                for decl in tree:
                    kind = (decl.get("ContentType") or "").lower()
                    if any(m in kind for m in ("macroenabled", "vbaproject", "vbasignature", "activex", "oleobject")):
                        fail("Macros, active content and embedded documents are not supported.", "unsafe_upload")
    for part in package.content_parts():
        root = package.tree(part)
        if root.find(".//" + q("w:ins")) is not None or root.find(".//" + q("w:del")) is not None \
                or root.find(".//" + q("w:moveFrom")) is not None or root.find(".//" + q("w:moveTo")) is not None:
            fail("The form contains tracked changes. Accept or reject them in Word, then upload the clean form.", "tracked_changes")
        if root.find(".//" + q("w:altChunk")) is not None:
            fail("Embedded documents are not supported.", "unsafe_upload")
    return package


# ─── text ──────────────────────────────────────────────────────────────────────────────────────────────────────────

GLYPH_BOX = "☐□❏❑❒▢○⃝"   # empty boxes (○ radio option, U+20DD enclosing circle)
GLYPH_CHECKED = "☑☒▣◉"          # ticked/filled boxes
BOX, CHECKED = "☐", "☒"
# Symbol-font characters that draw a checkbox (codes may be written as U+F0xx or as the plain byte)
SYMBOL_BOXES = {
    "wingdings": ({0x6F, 0x71, 0x72, 0xA8, 0xA1}, {0xFE, 0xFD, 0x78}),
    "wingdings 2": ({0x2A, 0xA3, 0x81, 0x99}, {0x52, 0x53, 0x54, 0x51}),
}
PUA_BOXES = ({0xF06F, 0xF071, 0xF072, 0xF0A8, 0xF0A3, 0xF02A, 0xF081}, {0xF0FE, 0xF0FD, 0xF078, 0xF052, 0xF053, 0xF054})
T, TAB, PTAB, BR, CR, SYM, NBH = (q("w:t"), q("w:tab"), q("w:ptab"), q("w:br"), q("w:cr"), q("w:sym"), q("w:noBreakHyphen"))
R, SDT, FLDCHAR, FALLBACK, TXBX = q("w:r"), q("w:sdt"), q("w:fldChar"), q("mc:Fallback"), q("w:txbxContent")
PASS_THROUGH = {q("w:hyperlink"), q("w:smartTag"), q("w:fldSimple"), q("w:customXml"), q("w:dir"), q("w:bdo"),
                q("mc:AlternateContent"), q("mc:Choice"), q("w:sdtContent")}


def run_font(r) -> str:
    rpr = r.find(q("w:rPr"))
    fonts = rpr.find(q("w:rFonts")) if rpr is not None else None
    if fonts is None:
        return ""
    return (fonts.get(q("w:ascii")) or fonts.get(q("w:hAnsi")) or fonts.get(q("w:cs")) or "").strip().lower()


def map_char(ch: str, font: str) -> str:
    """One visible character -> itself, or BOX / CHECKED when it draws a checkbox. Always one character."""
    if ch in GLYPH_BOX:
        return BOX
    if ch in GLYPH_CHECKED:
        return CHECKED
    code = ord(ch)
    table = SYMBOL_BOXES.get(font)
    if table:
        low = code - 0xF000 if code >= 0xF000 else code
        if low in table[0]:
            return BOX
        if low in table[1]:
            return CHECKED
        return ch
    if code in PUA_BOXES[0]:
        return BOX
    if code in PUA_BOXES[1]:
        return CHECKED
    return ch


DIGIT_BOX = "\u25af"          # a symbol-font digit-entry box (one character position of a number)
DIGIT_SYMBOLS = {("symbol", 0xF0)}


def sym_char(node) -> str:
    code = (node.get(q("w:char")) or "").upper()
    font = (node.get(q("w:font")) or "").lower()
    try:
        value = int(code, 16)
    except ValueError:
        return ""
    low = value - 0xF000 if value >= 0xF000 else value
    if (font, low) in DIGIT_SYMBOLS:
        return DIGIT_BOX
    return map_char(chr(value), font) if value < 0x110000 else ""


def text_of(el, *, own=False) -> str:
    """Visible text (fallback copies and field instructions excluded; checkbox glyphs normalised to BOX/CHECKED).
    `own` leaves out text boxes anchored inside `el` (they are separate slots)."""
    out = []

    def walk(node):
        for ch in node:
            tag = ch.tag
            if not isinstance(tag, str) or tag == FALLBACK or (own and tag == TXBX) or tag in (q("w:instrText"), q("w:delText")):
                continue
            if tag == T:
                font = run_font(ch.getparent()) if ch.getparent() is not None and ch.getparent().tag == R else ""
                out.append("".join(map_char(c, font) for c in (ch.text or "")))
            elif tag in (TAB, PTAB):
                out.append("\t")
            elif tag in (BR, CR):
                out.append("\n")
            elif tag == SYM:
                out.append(sym_char(ch))
            elif tag == NBH:
                out.append("-")
            else:
                walk(ch)
    walk(el)
    return "".join(out)


def fingerprint(el) -> str:
    return hashlib.sha256(etree.tostring(el, method="c14n")).hexdigest()


@dataclass
class Piece:
    start: int
    end: int
    kind: str            # t | tab | br | sym | obj
    run: object = None   # the w:r holding it (None for obj)
    node: object = None  # w:t / w:tab / w:sym element, or the object (sdt / field-begin run)
    obj: str = ""        # for obj: sdt_checkbox | sdt | ff_checkbox | ff


def paragraph_pieces(p):
    """The paragraph's own visible content, in order, as positioned pieces. Text boxes and fallback copies are left
    out (separate slots); an inline content control or a legacy form field is ONE object piece whose text is BOX for
    a checkbox and NUL otherwise (its content is its own answer area) - except a control wrapping a checkbox control,
    whose content is read as part of the line so the checkbox inside is a box like any other."""
    pieces, pos = [], [0]
    stack = []                          # open complex fields: [kind, separated]

    def add(kind, text_len, run=None, node=None, obj=""):
        pieces.append(Piece(pos[0], pos[0] + text_len, kind, run, node, obj))
        pos[0] += text_len

    def walk(el):
        for ch in el:
            tag = ch.tag
            if not isinstance(tag, str) or tag in (FALLBACK, TXBX, q("w:pPr"), q("w:rPr"), q("w:sdtPr"), q("w:sdtEndPr")):
                continue
            if tag == SDT:
                info = sdt_info(ch)
                if info["type"] != "checkbox" and checkbox_nodes(ch.find(q("w:sdtContent"))):
                    # ⚠️ A CONTROL WRAPPING A CHECKBOX CONTROL IS READ THROUGH: as one opaque object it hid the
                    # checkbox inside it from every box reader, so a printed tick there was never read, never
                    # unticked and never checked by the read-back (round 3 F1).
                    walk(ch)
                    continue
                add("obj", 1, node=ch, obj="sdt_checkbox" if info["type"] == "checkbox" else "sdt")
                continue
            if tag == R:
                fc = ch.find(FLDCHAR)
                if fc is not None:
                    kind = fc.get(q("w:fldCharType"))
                    if kind == "begin":
                        data = fc.find(q("w:ffData"))
                        if data is None:
                            stack.append(["other", False])
                        else:
                            is_cb = data.find(q("w:checkBox")) is not None
                            stack.append(["cb" if is_cb else "ff", False])
                            add("obj", 1, node=ch, obj="ff_checkbox" if is_cb else "ff")
                    elif kind == "separate" and stack:
                        stack[-1][1] = True
                    elif kind == "end" and stack:
                        stack.pop()
                    continue
                if any(k in ("cb", "ff") for k, _ in stack) or (stack and not stack[-1][1]):
                    continue                    # a form field's own result, or a field's instruction part
                font = None
                for node in ch:
                    ntag = node.tag
                    if ntag == T:
                        if font is None:
                            font = run_font(ch)
                        text = node.text or ""
                        add("t", len(text), ch, node)
                    elif ntag in (TAB, PTAB):
                        add("tab", 1, ch, node)
                    elif ntag in (BR, CR):
                        add("br", 1, ch, node)
                    elif ntag == SYM:
                        add("sym", 1, ch, node)
                    elif ntag == NBH:
                        add("t", 1, ch, node)
                continue
            if tag in PASS_THROUGH:
                walk(ch)
    walk(p)
    return pieces


def checkbox_nodes(el, own=True) -> list:
    """Every checkbox control inside `el`, found by walking the whole subtree (never through the box readers): the
    w:sdt of a checkbox content control and the begin run of a legacy checkbox field, in document order. Fallback
    copies are left out, and with `own` text boxes too (each is a place of its own)."""
    out = []
    if el is None:
        return out

    def walk(node):
        for ch in node:
            tag = ch.tag
            if not isinstance(tag, str) or tag == FALLBACK or (own and tag == TXBX):
                continue
            if tag == SDT:
                pr = ch.find(q("w:sdtPr"))
                if pr is not None and pr.find(q("w14:checkbox")) is not None:
                    out.append(ch)
            elif tag == R:
                fc = ch.find(FLDCHAR)
                if fc is not None and fc.get(q("w:fldCharType")) == "begin":
                    data = fc.find(q("w:ffData"))
                    if data is not None and data.find(q("w:checkBox")) is not None:
                        out.append(ch)
            walk(ch)
    walk(el)
    return out


def piece_text(pc: Piece) -> str:
    if pc.kind == "t":
        if pc.node.tag == NBH:
            return "-"
        font = run_font(pc.run)
        return "".join(map_char(c, font) for c in (pc.node.text or ""))
    if pc.kind == "tab":
        return "\t"
    if pc.kind == "br":
        return "\n"
    if pc.kind == "sym":
        return sym_char(pc.node) or " "
    return BOX if pc.obj in ("sdt_checkbox", "ff_checkbox") else "\x00"


def paragraph_text(p):
    pieces = paragraph_pieces(p)
    return "".join(piece_text(pc) for pc in pieces), pieces


# ─── slots ─────────────────────────────────────────────────────────────────────────────────────────────────────────

@dataclass(eq=False)
class Slot:
    part: str
    path: str
    kind: str                     # p | tbl | tc | sdt | ff | txbx | glyphs
    el: object
    parent: "Slot | None" = None
    info: dict = dfield(default_factory=dict)
    children: list = dfield(default_factory=list)
    seq: int = 0

    @property
    def id(self):
        return "%s#%s" % (self.part, self.path)


def _through(el, want) -> list:
    """`want` children of `el` in document order, looking through the content controls and custom XML that wrap them."""
    out = []
    for ch in el:
        if ch.tag == want:
            out.append(ch)
        elif ch.tag == SDT:
            content = ch.find(q("w:sdtContent"))
            if content is not None:
                out += _through(content, want)
        elif ch.tag == q("w:customXml"):
            out += _through(ch, want)
    return out


def table_rows_of(tbl) -> list:
    """⚠️ A TABLE'S ROWS, THROUGH ANY CONTROL WRAPPING A ROW (w:tbl/w:sdt/w:tr): direct rows only made a wrapped row
    invisible (round 3 P1). The one reading of rows for the index and the table_rows writer."""
    return _through(tbl, q("w:tr"))


def row_cells_of(tr) -> list:
    """⚠️ A ROW'S CELLS, THROUGH ANY CONTROL WRAPPING A CELL (w:tr/w:sdt/w:tc): direct cells only skipped a wrapped cell,
    so every later cell took the column before its own and a Yes answer was ticked under No (round 3 P1)."""
    return _through(tr, q("w:tc"))


def grid_before(tr) -> int:
    """The grid columns a row skips before its first cell (w:gridBefore)."""
    trpr = tr.find(q("w:trPr"))
    before = trpr.find(q("w:gridBefore")) if trpr is not None else None
    try:
        return int(before.get(q("w:val"), "0") or 0) if before is not None else 0
    except ValueError:
        return 0


def cell_span(tc) -> int:
    tcpr = tc.find(q("w:tcPr"))
    gs = tcpr.find(q("w:gridSpan")) if tcpr is not None else None
    try:
        return int(gs.get(q("w:val"), "1") or 1) if gs is not None else 1
    except ValueError:
        return 1


def row_of(tc):
    """The w:tr holding a cell (through any control wrapping the cell)."""
    return next(tc.iterancestors(q("w:tr")), None)


def own_paragraph_slots(cell) -> list:
    """A table cell slot's own paragraph slots in order: direct ones and those inside block-level content controls
    wrapping them (never a nested table's or a text box's)."""
    out = []

    def walk(slot):
        for c in slot.children:
            if c.kind == "p":
                out.append(c)
            elif c.kind == "sdt":
                walk(c)
    walk(cell)
    return out


class SlotIndex:
    """Every slot of the content parts in document order, with element and sibling lookups."""

    def __init__(self, package: Package):
        self.package = package
        self.slots: list[Slot] = []
        self.by_id: dict[str, Slot] = {}
        self.by_el: dict[int, Slot] = {}
        self.hidden_parts = [p for p in package.content_parts() if p not in package.displayed_parts()]
        for part in package.displayed_parts():
            root = package.tree(part)
            if part == "word/document.xml":
                self._container(part, root.find(q("w:body")), "b", None)
            else:
                self._container(part, root, "hf", None)
        self.roots = [s for s in self.slots if s.parent is None]

    def _add(self, slot):
        slot.seq = len(self.slots)
        self.slots.append(slot)
        self.by_id[slot.id] = slot
        self.by_el.setdefault(id(slot.el), slot)
        if slot.parent is not None:
            slot.parent.children.append(slot)
        return slot

    def _container(self, part, el, path, parent):
        counts = {}
        for child in el:
            local = etree.QName(child).localname if isinstance(child.tag, str) else None
            if local in ("p", "tbl", "sdt"):
                i = counts.get(local, 0)
                counts[local] = i + 1
                sub = "%s/%s[%d]" % (path, local, i)
                if local == "p":
                    self._paragraph(part, child, sub, parent)
                elif local == "tbl":
                    self._table(part, child, sub, parent)
                else:
                    self._sdt(part, child, sub, parent)

    def _sdt(self, part, el, path, parent):
        slot = self._add(Slot(part, path, "sdt", el, parent, sdt_info(el)))
        content = el.find(q("w:sdtContent"))
        if content is not None:
            self._container(part, content, path, slot)

    def _table(self, part, el, path, parent):
        tslot = self._add(Slot(part, path, "tbl", el, parent))
        for ri, tr in enumerate(table_rows_of(el)):
            col = grid_before(tr)
            for ci, tc in enumerate(row_cells_of(tr)):
                tcpr = tc.find(q("w:tcPr"))
                span, vmerge = cell_span(tc), None
                if tcpr is not None:
                    vm = tcpr.find(q("w:vMerge"))
                    vmerge = (vm.get(q("w:val")) or "continue") if vm is not None else None
                cpath = "%s/tr[%d]/tc[%d]" % (path, ri, ci)
                cslot = self._add(Slot(part, cpath, "tc", tc, tslot, {"row": ri, "col": col, "span": span, "vmerge": vmerge}))
                self._container(part, tc, cpath, cslot)
                col += span
            for si, sdt in enumerate(tr.findall(q("w:sdt"))):
                self._sdt(part, sdt, "%s/tr[%d]/sdt[%d]" % (path, ri, si), tslot)

    def _paragraph(self, part, el, path, parent):
        pslot = self._add(Slot(part, path, "p", el, parent))
        for si, sdt in enumerate(el.findall(q("w:sdt"))):
            self._sdt(part, sdt, "%s/sdt[%d]" % (path, si), pslot)
        ff = 0
        skip = {id(x) for fb in el.iter(FALLBACK) for x in fb.iter()}
        for r in el.iter(R):
            if id(r) in skip:
                continue
            fc = r.find(FLDCHAR)
            if fc is not None and fc.get(q("w:fldCharType")) == "begin":
                data = fc.find(q("w:ffData"))
                if data is not None:
                    self._add(Slot(part, "%s/ff[%d]" % (path, ff), "ff", r, pslot, ff_info(data)))
                    ff += 1
        if any(ch in (BOX, CHECKED) for ch in text_of(el, own=True)):
            glyph = Slot(part, "%s/glyphs" % path, "glyphs", el, pslot)
            self.slots.append(glyph)          # not registered by element: the paragraph slot owns `el`
            glyph.seq = len(self.slots) - 1
            self.by_id[glyph.id] = glyph
            pslot.children.append(glyph)
        tb = 0
        for t in el.iter(TXBX):
            if id(t) in skip:
                continue
            tpath = "%s/txbx[%d]" % (path, tb)
            tslot = self._add(Slot(part, tpath, "txbx", t, pslot))
            self._container(part, t, tpath, tslot)
            tb += 1


def sdt_info(el) -> dict:
    pr = el.find(q("w:sdtPr"))
    info = {"type": "richText", "options": [], "alias": None, "tag": None, "placeholder": False, "locked": False}
    if pr is None:
        return info
    for t in ("dropDownList", "comboBox", "date", "text", "picture", "docPartObj", "docPartList", "group", "citation",
              "bibliography", "equation", "richText"):
        x = pr.find(q("w:" + t))
        if x is not None:
            info["type"] = "plainText" if t == "text" else t
            if t in ("dropDownList", "comboBox"):
                info["options"] = [((li.get(q("w:displayText")) or li.get(q("w:value")) or "").strip())
                                   for li in x.findall(q("w:listItem"))]
            if t == "date":
                fmt = x.find(q("w:dateFormat"))
                info["date_format"] = fmt.get(q("w:val")) if fmt is not None else None
            break
    cb = pr.find(q("w14:checkbox"))
    if cb is not None:
        info["type"] = "checkbox"
        ch = cb.find(q("w14:checked"))
        info["checked"] = (ch.get(q("w14:val")) if ch is not None else "0") in ("1", "true")
    a = pr.find(q("w:alias"))
    info["alias"] = a.get(q("w:val")) if a is not None else None
    tg = pr.find(q("w:tag"))
    info["tag"] = tg.get(q("w:val")) if tg is not None else None
    info["placeholder"] = pr.find(q("w:showingPlcHdr")) is not None
    lock = pr.find(q("w:lock"))
    info["locked"] = lock is not None and (lock.get(q("w:val")) or "") in ("contentLocked", "sdtContentLocked")
    return info


def ff_text_limit(data):
    """Word OOXML admits 1..32767; omission alone is unlimited. -1 is unresolved.

    MS-OI29500 17.16.26 restricts this attribute to a positive XML Schema short.
    Binary .doc's cch=0 convention does not make w:maxLength=0 unlimited.
    """
    nodes = data.findall(q("w:textInput") + "/" + q("w:maxLength"))
    if not nodes:
        return None
    value = (nodes[0].get(q("w:val")) or "").strip()
    if len(nodes) != 1 or not re.fullmatch(r"\+?[0-9]{1,8}", value):
        return -1
    number = int(value)
    return number if 1 <= number <= 32767 else -1


def ff_info(data) -> dict:
    kind = "FORMTEXT"
    info = {}
    if data.find(q("w:checkBox")) is not None:
        kind = "FORMCHECKBOX"
        cb = data.find(q("w:checkBox"))
        d = cb.find(q("w:default"))
        c = cb.find(q("w:checked"))
        val = c if c is not None else d
        info["checked"] = val is not None and (val.get(q("w:val")) or "1") in ("1", "true", "on")
    elif data.find(q("w:ddList")) is not None:
        kind = "FORMDROPDOWN"
        info["options"] = [x.get(q("w:val")) for x in data.find(q("w:ddList")).findall(q("w:listEntry"))]
    elif data.find(q("w:textInput")) is not None:
        ti = data.find(q("w:textInput"))
        typ = ti.find(q("w:type"))
        info["input_type"] = typ.get(q("w:val")) if typ is not None else "regular"
        info["max_chars"] = ff_text_limit(data)
    name = data.find(q("w:name"))
    info["name"] = name.get(q("w:val")) if name is not None else None
    info["field"] = kind
    return info


# ─── detection ─────────────────────────────────────────────────────────────────────────────────────────────────────

UNDERSCORES = re.compile(r"_{3,}(?:[ \t]*_{2,})*|_{2}(?:[ \t]+_{1,2}){1,}")   # ___ , or character positions __ __ __
DIGIT_RUN = re.compile(r"\u25af+(?:\s*[/.:\-]\s*\u25af+)*")                     # digit-entry boxes (symbol font) as one blank
SEGMENTED = re.compile(r"\|(?:[ _]*_[ _]*\|)+(?:\s*[/.:\-]?\s*\|(?:[ _]*_[ _]*\|)+)*")   # digit boxes |__|__| / |__|__|
DOTS = re.compile(r"(?:\.{5,}|…{2,}|(?:\. ){4,}\.?)")    # a dotted leader: ....... or …… or . . . . .
BRACKET_ANY = re.compile(r"\[([^\[\]\n]{2,120})\]")


class _Bracket:
    """[Placeholder] fill-ins: an instruction verb (insert/enter/specify...) or a short noun phrase. Bracketed
    abbreviations ('[SDU]'), sentences and printed notes ('[This page intentionally left blank]') are text."""
    VERB = re.compile(r"^\s*(?:insert|enter|add|type|specify|list|describe|provide|state|include)\b", re.I)

    def finditer(self, text):
        for m in BRACKET_ANY.finditer(text):
            inner = m.group(1).strip()
            words = inner.split()
            if self.VERB.match(inner):
                yield m
                continue
            if re.fullmatch(r"[A-Z0-9/&.\-]{1,6}s?", inner) or re.fullmatch(r"\d+(?:[.,]\d+)?%?", inner):
                continue                        # an abbreviation or a number, printed
            if len(words) > 5 or inner.endswith((".", "!", "?")) or re.search(r"\b(?:is|are|was|were|will|must|should|may|has|have)\b", inner, re.I):
                continue                        # a sentence: printed text
            yield m

    def fullmatch(self, text):
        m = BRACKET_ANY.fullmatch(text)
        return m if m and any(True for _ in self.finditer(text)) else None


BRACKET = _Bracket()
ANGLE = re.compile(r"<(?![/!?])[^<>\n]{3,120}>")                  # <Protocol Number: Abbreviated Title> author placeholders
TOKEN = re.compile(r"\{\{\s*([\w][\w .?:/()\-]{0,119}?)\s*\}\}")
PLACEHOLDER_TEXT = re.compile(r"^(?:click (?:or tap )?here to enter (?:text|a date)\.?|choose an item\.?|click or tap to enter a date\.?|"
                              r"enter (?:text|date)(?: here)?\.?|type here\.?|data to be filled in by site\.?|mm/dd/yyyy|dd/mm/yyyy|"
                              r"dd|mm|yy|yyyy|hh|dd/mm/yy|mm/dd/yy)$", re.I)
ENTER_HINT = re.compile(r"^(?:enter|insert|type|add|specify)\s+\S.{0,60}$", re.I)
CHECK_ALL = re.compile(r"\b(?:check|tick|mark|select|circle)\s+all\s+that\s+apply\b|\ball that apply\b|\bselect up to\b|"
                       r"\b(?:check|tick|mark|select)\s+(?:any|as many)\b", re.I)
CHECK_ONE = re.compile(r"\b(?:check|tick|choose|select|mark|circle)\s+(?:only\s+)?one\b|\bone only\b", re.I)
# A number followed by a time or a measured unit ("one day", "max 1 g") is an amount, not a count of answers.
_NOT_A_MEASURE = (r"(?!\s*(?:st|nd|rd|th|am|pm|h|hr|hrs|hours?|mins?|minutes?|days?|nights?|weeks?|months?|years?|"
                  r"times?|occasions?|mg|mcg|ml|kg|g|l|cm|mm|%)\b)")
# Explicit one-only commands CHECK_ONE misses ("select just one", "pick one", "select a single option").
# choice_kind uses it (through one_only) ONLY to keep a question single, never to allow more selections.
EXPLICIT_ONE = re.compile(r"\b(?:check|tick|choose|select|mark|circle|pick|indicate)\s+(?:(?:only|just|exactly)\s+)?"
                          r"(?:one|1|a\s+single)\b"
                          r"|(?<!\bthan\sa\s)(?<!\bthan\s)(?<!\bnot\sa\s)\bsingle\s+(?:option|answer|response|choice|selection)\b",
                          re.I)
# One-only limits printed in the question itself ("only one may be ticked", "one box only", "no more than one",
# "maximum one", "tick the ONE main ...", "the single best"). Read only in the question, never in an answer label
# ("Pain in only one joint" is an answer, not a limit).
ONE_LIMIT = re.compile(r"\bonly\s+(?:one|1)\b(?!\s*-)" + _NOT_A_MEASURE +
                       r"|\b(?:one|1)\s+(?:(?:box|option|answer|response|choice|item)\s+)?only\b"
                       r"|\b(?:no|not)\s+more\s+than\s+(?:one|1)\b" + _NOT_A_MEASURE +
                       r"|\b(?:max(?:imum)?\.?|at\s+most)\s*(?:of\s+)?(?:one|1)\b" + _NOT_A_MEASURE +
                       r"|\bthe\s+(?:one|single)\b(?!\s*-)" + _NOT_A_MEASURE, re.I)
# A following quantity turns "one" into a range or an open count: "one or more", "one to three", "one/both", "1+",
# "one, some or all", "one, two or three", "1-3 that apply", "1–3:". Any other continuation ("pick one and give
# details", "pick 1 / see notes", "indicate one to be reviewed") leaves the one-only reading standing, and so does a
# scale key or a warning after a comma or a dash ("tick one - 1 = never, 5 = always", "tick one, all others blank",
# "tick one - two ticks void the answer"): a comma needs a complete "X or Y" count, and a dash range needs a numeral
# upper bound that ends the phrase ("1-3:", "1-3 that apply") or, printed unspaced, names the answers ("1-3 boxes").
_COUNT_WORD = r"(?:two|three|four|five|six|seven|eight|nine|ten)"
_MANY_WORD = r"(?:more|some|all|any|several|many|multiple|both|" + _COUNT_WORD + r")"
MORE_THAN_ONE_AFTER = re.compile(
    r"\s*\+"
    r"|\s*(?:\bor\b|\band\b|\bto\b|\bnor\b)\s*(?:" + _MANY_WORD + r"|\d)"
    r"|\s*/\s*" + _MANY_WORD + r"\b"
    r"|\s*,\s*(?:some|" + _COUNT_WORD + r")\s*,?\s*(?:or|and)\s+" + _MANY_WORD + r"\b"
    r"|\s*[-–—]\s*\d{1,2}\b(?=\s*(?:$|[):.;,]|(?:that|which|of)\b))"
    r"|[-–]\d{1,2}\b(?=\s+(?:boxes|options|answers|items|responses|categories|choices)\b)", re.I)
# An open count ("one or more", "1+", "more than one", "one, some or all") is never a limit.
OPEN_COUNT = re.compile(r"\b(?:one|1)\s*(?:or\s+more\b|\+)|\bmore\s+than\s+(?:one|1)\b|\bone\s*,\s*some\s+or\s+all\b"
                        r"|\bone\s*/\s*both\b|\bany\s+number\b", re.I)


def one_only(texts, questions=""):
    """Explicit one-only wording that is not the start of a range or an open count: the commands anywhere in the
    printed text, the limits only in the question. Each printed piece (a question, its printed cardinality, its
    paragraph) is read on its own: what follows "tick 1" is read in the same piece, never in the next piece a caller
    joined on ("Symptom(s) - tick 1-3" followed by its own paragraph is still a range)."""
    texts = [texts] if isinstance(texts, str) else list(texts)
    questions = [questions] if isinstance(questions, str) else list(questions)
    for rx, values in ((CHECK_ONE, texts), (EXPLICIT_ONE, texts), (ONE_LIMIT, questions)):
        for value in values:
            value = value or ""
            for m in rx.finditer(value):
                if not MORE_THAN_ONE_AFTER.match(value, m.end()):
                    return True
    return False


# Uses of "one", "multiple" and heading numbers that are not a quantity of answers.
NOT_A_QUANTITY = re.compile(r"^\s*\(?(?:\d{1,3}(?:\.\d{1,3})*|[a-z]|[ivxlc]{1,5})[.):]\s"
                            r"|\b(?:day|week|month|year|part|section|stage|step|phase|visit|cycle|level|grade|type|class|"
                            r"tier|appendix|annex|chapter|pages?|schedule|volume|number|no\.?|questions?|items?|q|box)\s+"
                            r"(?:one|\d{1,3}[a-z]?|[ivx]{1,4})\b"
                            r"|\bone-\w+|\bmultiple\s+(?:sclerosis|myeloma|births?|pregnancy)\b", re.I)
# A standalone small number printed as a quantity ("Put an X in 1 box.", "Record 2 treatments.", "Just 1."), never
# a code, a decimal, a date, a time or a measured amount.
NUMERAL_QUANTITY = (r"(?<![\w/.:,\-–])\d{1,2}(?![\w/:%]|[.,\-–]\d{3})(?!\s*(?:st|nd|rd|th|am|pm|h|hr|hrs|hours?|mins?|"
                    r"minutes?|days?|weeks?|wks?|months?|years?|yrs?|mg|mcg|ml|kg|g|cm|mm|jan\w*|feb\w*|mar\w*|apr\w*|"
                    r"may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)\b)")
# Native-checkbox history cardinality (Detector.native_history_source). A sentence that speaks about selecting,
# how many, or exclusivity must be ONE complete positive command (HISTORY_ONE / HISTORY_MANY); anything else,
# negated or limited commands included, leaves the history unresolved rather than independent. Only the word forms
# of a command count: "checklist", "markers", "selection criteria" and "treatment options" are not commands.
HISTORY_SELECTION = re.compile(
    r"\b(?:check(?:s|ed|ing)?|tick(?:s|ed|ing)?|choos(?:e|es|ing)|chose|chosen|select(?:s|ed|ing)?|mark(?:s|ed|ing)?|"
    r"circl(?:e|es|ed|ing)|pick(?:s|ed|ing)?|indicate|cross(?!-)|only|one|single|both|two|three|four|five|six|seven|"
    r"eight|nine|ten|multiple|several|either|neither|exclusiv\w*|max|maximum|min|minimum|limit|limits)\b"
    r"|\b(?:that|which|whichever|as)\s+appl(?:y|ies|ied)\b"
    # a mark printed into one box: "Place an X in ...", "✓ the relevant box", "the box that best describes"
    r"|[✓✔✗✘☑☒]|(?<![\w-])[Xx](?![\w-])"
    r"|\b(?:appropriate|relevant|correct|applicable|right|best|suitable|matching|corresponding)\s+"
    r"(?:box|boxes|answer|option|response|category)\b|\bbox(?:es)?\s+(?:that|which)\b"
    r"|" + NUMERAL_QUANTITY, re.I)


def history_selection(text):
    return bool(HISTORY_SELECTION.search(NOT_A_QUANTITY.sub(" ", text or "")))


# Selection wording inside an answer label ("Weekend (tick one only)"); answer labels are not instructions, so marks,
# numbers and clinical names ("Fragile X", "Physiotherapy x2") are left to the label.
OPTION_SELECTION = re.compile(
    r"\b(?:check\w*|tick\w*|choos\w*|chose\w*|select\w*|mark\w*|circl\w*|pick\w*|indicate|cross(?!-)|option\w*|only|"
    r"one|multiple|several|either|neither|exclusiv\w*|max|maximum|min|minimum|limit|limits)\b"
    r"|\b(?:that|which|whichever|as)\s+appl(?:y|ies|ied)\b", re.I)


_HISTORY_VERB = r"(?:check|tick|choose|select|mark|circle|pick|indicate|cross)"
_HISTORY_NOUNS = r"(?:boxes|options|answers|items|categories|responses)"
HISTORY_ONE = re.compile(r"(?:please\s+)?(?:" + _HISTORY_VERB + r"\s+(?:(?:only|just|exactly)\s+)?(?:one|1|a\s+single)"
                         r"(?:\s+(?:option|answer|response|item|box|category|choice))?(?:\s+only)?(?:\s+of\s+the\s+following)?"
                         r"|only\s+one|one\s+only)", re.I)
# The complete positive multiple commands: "Tick all that apply", "Tick all boxes that apply", "Tick all applicable
# boxes", "Tick as many boxes as apply", "Tick all that are applicable", "Please tick all relevant boxes", "Tick
# any/all that apply", "You may tick more than one box".
HISTORY_MANY = re.compile(
    r"(?:please\s+)?(?:you\s+(?:may|can)\s+)?(?:" + _HISTORY_VERB + r"\s+)?(?:"
    r"(?:all|any|any\s*/\s*all|all\s*/\s*any|any\s+or\s+all)\s+(?:of\s+the\s+)?(?:" + _HISTORY_NOUNS + r"\s+)?"
    r"(?:that|which)\s+(?:appl(?:y|ied)|are\s+(?:applicable|relevant|appropriate))"
    r"|as\s+many\s+(?:" + _HISTORY_NOUNS + r"\s+)?as\s+(?:appl(?:y|ied)|are\s+(?:applicable|relevant|appropriate)|"
    r"applicable|relevant|appropriate|necessary|needed|required)"
    r"|all\s+(?:applicable|relevant|appropriate)\s+" + _HISTORY_NOUNS + r")"
    r"|(?:please\s+)?you\s+(?:may|can)\s+" + _HISTORY_VERB + r"\s+more\s+than\s+one(?:\s+(?:box|option|answer|item|category|response))?"
    r"|more\s+than\s+one\s+(?:box|option|answer|item|category|response)\s+(?:may|can)\s+be\s+"
    r"(?:checked|ticked|chosen|selected|marked|circled|picked|indicated|crossed)", re.I)
# A printed reference mark sends the reader to guidance this rule never reads.
HISTORY_REFERENCE = re.compile(r"[*†‡§¶]")
# Answers that are counts or ranges ("One", "0-2", "6 or more", "Under 7 days", "Over 14 days") exclude each other.
QUANTITY_OPTION = re.compile(r"^\W*(?:\d|(?:none|zero|nil|one|two|three|four|five|six|seven|eight|nine|ten|once|twice|"
                             r"never|under|over|less\s+than|more\s+than|fewer\s+than|greater\s+than|at\s+least|"
                             r"at\s+most|up\s+to|between|within|above|below)\b)", re.I)
# A question that asks for one level, count or total has one answer.
SINGLE_QUANTITY = re.compile(r"\b(?:highest|lowest|greatest|best|worst|principal|number\s+of|total|how\s+many|how\s+long|"
                             r"how\s+often|duration|length\s+of|frequency|amount\s+of|level\s+of|single|sole|current|"
                             r"currently|latest|last|most\s+recent|primary|main)\b", re.I)
# Limited selection guidance printed anywhere in the form (Detector.limited_selection_elsewhere): a selection verb or
# a printed mark together with a limit (one, a number, only, either, exclusive), a one-answer noun phrase ("one box
# only", "a single answer") or a singular-box phrase ("the relevant box", "the box that best describes"). "More than
# one", "one or more", "1+", times, dates, codes and measured amounts ("at least 14 days") are not limits.
SELECTION_ACT = re.compile(r"\b(?:tick(?:s|ed|ing)?|check(?:s|ed|ing)?|mark(?:s|ed|ing)?|select(?:s|ed|ing)?|"
                           r"choos(?:e|es|ing)|chose|chosen|pick(?:s|ed|ing)?|circl(?:e|es|ed|ing)|cross(?:es|ed|ing)?|"
                           r"indicat(?:e|es|ed|ing))\b|[✓✔✗✘☑☒]|(?<![\w-])[Xx](?![\w-])", re.I)
SELECTION_LIMIT = re.compile(r"\b(?:one|single|sole|two|three|four|five|six|seven|eight|nine|ten|only|either|neither|"
                             r"exclusive(?:ly)?)\b|" + NUMERAL_QUANTITY, re.I)
# Wording that allows several boxes ("the appropriate box(es)", "box or boxes", "box/boxes") is not one answer.
_NOT_PLURAL = r"(?!\s*\(e?s\)|(?:\s*/\s*|\s+or\s+)(?:boxes|answers|options|responses|categories|squares)\b)"
ONE_ANSWER = re.compile(r"\b(?:(?:only\s+)?(?:one|1)|a\s+single|single)\s+(?:box|answer|option|response|choice|category|"
                        r"square)s?\b(?:\s+only\b)?"
                        r"|\b(?:appropriate|relevant|correct|applicable|right|best|suitable|matching|corresponding)\s+"
                        r"(?:box|answer|option|response|category|square)\b" + _NOT_PLURAL +
                        r"|\b(?:box|answer|option|response|category|square)\s+(?:that|which)\s+(?:best\s+)?"
                        r"(?:appl|describ|match|fit|correspond)", re.I)
# A negated count is a limit, never an open count: "do not tick more than one box", "no more than one answer",
# "never select multiple options".
NEGATED_MANY = re.compile(r"(?:\b(?:no|not|never|cannot)\b|n[’']t\b)[^.;!?]*?"
                          r"(?:\bmore\s+than\s+(?:one|1)\b|\b(?:multiple|several)\b)", re.I)
ANSWER_NOUN = re.compile(r"\b(?:box|answer|option|response|choice|categor)", re.I)
# Only a complete one-box-per-row rule for a table or grid is about a table ("Tick one box per row in the table
# below."); any other sentence that mentions a column or a table ("tick one box in the column provided", "see table of
# codes") is still a limit.
TABLE_ROWS = re.compile(r"(?:in\s+the\s+(?:table|grid)\s+below\s*,\s*)?(?:tick|mark|select)\s+(?:only\s+)?one\s+box"
                        r"(?:\s+only)?\s+(?:per|in\s+each)\s+row(?:\s+(?:of|in)\s+the\s+(?:table|grid)(?:\s+below)?)?", re.I)
# Selection wording in floating text (a text box or a positioned frame), whose printed place beside a list is
# unknown: any selection command there may govern it. "Checked by:" names who checked; it is not a command.
SELECTION_ATTRIBUTION = re.compile(r"\b(?:checked|marked)\s+by\b", re.I)


def limited_selection(sentence):
    text = NOT_A_QUANTITY.sub(" ", sentence or "")
    if NEGATED_MANY.search(text):
        return bool(SELECTION_ACT.search(text) or ANSWER_NOUN.search(text))
    text = OPEN_COUNT.sub(" ", text)
    return bool((SELECTION_ACT.search(text) and SELECTION_LIMIT.search(text) or ONE_ANSWER.search(text))
                and not TABLE_ROWS.fullmatch(re.sub(r"[\s.!:;]+$", "", (sentence or "").strip())))


def floating_selection(sentence):
    return bool(SELECTION_ACT.search(SELECTION_ATTRIBUTION.sub(" ", NOT_A_QUANTITY.sub(" ", sentence or ""))))


# A complete one-only command printed inside a question's own label ("(please tick one)", "- tick one box only",
# "(tick one of the following)"), optionally pointing at notes ("- see page 3").
LABEL_ONE = re.compile(r"(?:please\s+)?(?:(?:check|tick|choose|select|mark|circle|pick|indicate|cross)\s+"
                       r"(?:(?:only|just|exactly)\s+)?(?:one|1|a\s+single)"
                       r"(?:\s+(?:option|answer|response|item|box|category|choice))?(?:\s+only)?(?:\s+of\s+the\s+following)?"
                       r"|one(?:\s+(?:option|answer|response|item|box|category|choice))?\s+only"
                       r"|only\s+one(?:\s+(?:option|answer|response|item|box|category|choice))?)"
                       r"(?:\s*[-–—,]\s*see\s+(?:page\s+\d{1,3}|notes|overleaf))?", re.I)


def label_instruction(sentence, contained=False):
    """The printed label of a separate question whose only selection wording is a complete one-only command printed
    inside it ("Type of discharge applied for (please tick one):", "Sex [tick one]:", "Smoking status (tick one)",
    "Type - please tick one"), or None. The command may also stand alone after the label's colon when it is
    bracketed ("Type of discharge applied for: (please tick one)") or, `contained` in the table cell that holds the
    question's own native boxes, unbracketed ("Type of discharge applied for: please tick one"). The name before the
    command is not itself a limit, and nothing after the label is. A standalone command ("Tick one box only."), a body
    notice ("Please note: only one box may be ticked.", "NB: tick one box only.") and a command that says more ("tick
    one box for leave and one for treatment", "tick one box only throughout this form") are not part of any one
    question's label; neither is a label with any other selection wording in it."""
    m = re.fullmatch(r"\s*([^:?]*[^:?\s])\s*(?:[:?](.*))?", sentence or "", re.S)
    if not m:
        return None
    label, rest, printed, commands = m.group(1), m.group(2) or "", m.group(1), []
    after = re.sub(r"[.!:;\s]+$", "", rest.strip())
    wrapped = re.fullmatch(r"\((.*)\)|\[(.*)\]", after)
    alone = (wrapped.group(1) if wrapped.group(1) is not None else wrapped.group(2)) if wrapped else after
    if after and (wrapped or contained) and LABEL_ONE.fullmatch(alone.strip()):
        commands, rest, printed = [alone], "", re.sub(r"[.!:;\s]+$", "", (sentence or "").strip())
    if limited_selection(rest):
        return None
    commands += [a or b for a, b in re.findall(r"\(([^()]*)\)|\[([^\[\]]*)\]", label)]
    name = re.sub(r"\([^()]*\)|\[[^\[\]]*\]", " ", label)
    dash = re.search(r"\s[-–—]\s", name)
    if dash:
        commands.append(name[dash.end():])
        name = name[:dash.start()]
    commands = [c.strip() for c in commands if history_selection(c)]
    if (commands and all(LABEL_ONE.fullmatch(re.sub(r"[.!:;]+$", "", c).strip()) for c in commands)
            and re.search(r"[^\W\d_]{2,}", name) and not limited_selection(name)):
        return printed
    return None


SIGNATURE = re.compile(r"\bsignature\b|\bsigned\b|\bsign(?:ed)? here\b", re.I)
INITIALS = re.compile(r"\binitials?\b|\binitial (?:the )?box", re.I)
DATE_LABEL = re.compile(r"\b(?:date|dob|d\.o\.b|born)\b|mm/dd|dd/mm|yyyy|\bD[DT]\s*\((?:dictated|transcribed)\)", re.I)
TIME_LABEL = re.compile(r"\btime\b|hh:mm|\(24.?h", re.I)
LONG_LABEL = re.compile(r"\b(?:comments?|describe|description|details?|explain|notes?|summary|history|findings|plan|narrative|reason)\b", re.I)
HEADING_STYLE = re.compile(r"^(?:heading|title|subtitle|toc)", re.I)
LABEL_END = re.compile(r"[:?]\s*$|[–—-]\s*$")
OPTION_WORD = re.compile(r"^(?:y|n|yes|no|m|f|male|female|n/?a|nd|unk|unknown|not known|true|false|done|not done|normal|abnormal|"
                         r"present|absent|positive|negative|pos|neg|[0-9]{1,2}|[+\-]|none|mild|moderate|severe|left|right|l|r|"
                         r"bilateral|pass|fail|ok|agree|disagree|always|often|sometimes|rarely|never)\.?$", re.I)
SIDE_WORD = re.compile(r"\b(?:left(?!\s+(?:blank|empty|unchanged)\b)|right(?!\s+for\b)|bilateral|lt|rt|bil)\b", re.I)


def side_phrase(text):
    """A printed side phrase; a unit 'per L' or a questionnaire list marker 'l.' is not a side."""
    return bool(SIDE_WORD.search(text) or re.fullmatch(r"\(?[LR]\)?[.:]?", text.strip(), re.I) or
                re.match(r"^(?:[LR][.)]?|\([LR]\))\s+(?:side|knee|leg|hip|arm|ankle|foot|hand|wrist|elbow|shoulder|eye|ear)\b",
                         text, re.I))
FIELDISH = re.compile(r"\b(?:date|time|name|signature|signed|initials?|comments?|notes?|number|no\.|#|dose|amount|result|"
                      r"value|score|site|code|address|phone|reason|description|details?|id)\b", re.I)
YESNO = re.compile(r"^(?:y|n|yes|no|n/?a|nd|unk|unknown|not known|not applicable|n/a or nd|na or nd|not done|done)\.?$", re.I)
MAX_LABEL_WORDS = 18
# Printed options that answer one question together. A word printed right before a row's first box that shares a
# family with the words between its boxes ('Allergies: Yes ☐ No ☐ NKDA') is that box's option, never part of
# the question (refutation R3-1). COMPANION words join any family ('N/A ☐ Yes ☐ No').
OPTION_FAMILIES = tuple(re.compile(r"(?:%s)\.?" % f, re.I) for f in (
    r"y|n|yes|no",
    r"normal|abnormal|abn|wnl|nl|high|low",
    r"present|absent",
    r"positive|negative|pos|neg|equivocal|indeterminate|inconclusive|reactive|non-?reactive|detected|not detected",
    r"none|mild|moderate|severe",
    r"left|right|bilateral|both|l|r|lt|rt|bil",
    r"male|female|m|f",
    r"pass|fail|true|false",
    r"(?:strongly )?(?:agree|disagree)|neutral",
    r"always|often|usually|sometimes|rarely|never|daily|weekly|monthly|yearly",
    r"current(?: smoker)?|former(?: smoker)?|never(?: smoker)?|ex-?smoker|non-?smoker",
    r"regular|irregular",
    r"increased|decreased|unchanged|improved|worse|better|same",
    r"active|inactive|resolved|ongoing|acute|chronic",
))
COMPANION_OPTION = re.compile(r"(?:n/?a|nd|unk|unknown|not known|not applicable|not done|done|other|unsure|"
                              r"don'?t know|dk|not assessed|not examined)\.?", re.I)


@dataclass
class Area:
    kind: str
    label: str
    slot: Slot                      # the anchor slot (its fingerprint binds the mapping)
    target: dict
    context: str = ""
    options: list = dfield(default_factory=list)
    extra_slots: list = dfield(default_factory=list)   # parallel header/footer copies, option slots
    order: int = 0
    note: str = ""
    capacity: int | None = None
    protection: str = ""
    complete_source: bool = False   # question-box source cannot be shortened by later metadata passes
    source_questions: list = dfield(default_factory=list)


#: A list marker is 1-3 digits, ONE letter or a roman numeral (i..xxx), as 'M.' 'M)' or '(M)' before a space.
#: ⚠️ Never a multi-letter word: 'Rt.', 'Lt.', 'Bil.', 'Dr.', 'No.' are text, and stripping them turned 'Rt. knee' and
#: 'Lt. knee' into the same label - and, through the option reader, the left knee into the right one.
#: ⚠️ AND NEVER A SIDE: 'L.' 'R.' 'L)' 'R)' (either case) and ANY single letter in parentheses - '(L)' '(R)' '(a)' '(i)'
#: - are kept (fail closed): '(L) Effusion' and '(R) Effusion' both became 'Effusion', and a notes line
#: 'Effusion: Yes' that names no side filled the left-only question.
LIST_MARK = r"(?:\d{1,3}|[A-Za-z]|(?i:x{0,2}(?:i{1,3}|iv|vi{0,3}|ix)|x{1,3}))"
LIST_MARKER = re.compile(r"^(?:(?![LRlr][.)])" + LIST_MARK + r"[.)]|\((?![A-Za-z]\))" + LIST_MARK + r"\))\s+")


def clean_label(text: str, *, limit=300) -> str:
    text = (text or "").replace("\x00", " ").replace(BOX, " ").replace(CHECKED, " ")
    text = re.sub(r"\s+", " ", text.replace("\t", " ")).strip()
    text = LIST_MARKER.sub("", text)
    return text.strip(" :–—-_*").strip()[:limit]


def option_text(text: str) -> str:
    """An option as printed, trimmed: box glyphs and NULs removed, each whitespace run read as one space, and the
    ends trimmed of the spaces, colons, dashes, underscores and asterisks around a printed option (the write-in blank
    after 'Other: ____', the separator in 'Temple -') - exactly clean_label's trimming.
    ⚠️ NEVER the list-marker strip, which is for question labels only: '(L) knee' and '(R) knee' are two options, and
    stripping them made both 'knee' - the clinician chose a side the export could not tell apart."""
    text = (text or "").replace("\x00", " ").replace(BOX, " ").replace(CHECKED, " ")
    return re.sub(r"\s+", " ", text.replace("\t", " ")).strip().strip(" :–—-_*").strip()[:300]


def gap_width(space: str) -> int:
    """How wide a run of printed whitespace is, a tab counted as eight spaces: which box a word is printed against."""
    return 8 * space.count("\t") + len(space) - space.count("\t")


def is_hint_run(r) -> bool:
    """Author guidance ink: a light, grey or blue colour (not black/auto), the convention for text to overwrite."""
    rpr = r.find(q("w:rPr")) if r is not None else None
    col = rpr.find(q("w:color")) if rpr is not None else None
    if col is None:
        return False
    theme = (col.get(q("w:themeColor")) or "").lower()
    if theme.startswith("accent") or theme in ("text2", "background2", "hyperlink"):
        return True
    val = (col.get(q("w:val")) or "").lower()
    if not re.fullmatch(r"[0-9a-f]{6}", val):
        return False
    rr, gg, bb = int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16)
    lum = (0.299 * rr + 0.587 * gg + 0.114 * bb) / 255
    bluish = bb > rr + 40 and bb > gg + 10
    return (lum >= 0.35 and not (rr > 150 and gg < 90 and bb < 90)) or bluish


def hyperlink_run(run) -> bool:
    return run is not None and any(node.tag == q("w:hyperlink") for node in run.iterancestors())


def hyperlink_control(control) -> bool:
    return hyperlink_run(control) or control.find(".//" + q("w:hyperlink")) is not None


def hyperlink_write(pieces, start, end) -> bool:
    """Whether replace_range would replace link text or insert inside its run parent.

    Link text and its relationship are fixed source content. Inserting after the
    last run of a hyperlink still inserts *inside* that hyperlink with addnext.
    An ordinary run after it gives a separate safe insertion anchor.
    """
    if start < end:
        return any(pc.start < end and pc.end > start and hyperlink_run(pc.run) for pc in pieces)
    if any(pc.start < start < pc.end and hyperlink_run(pc.run) for pc in pieces):
        return True
    before = [pc for pc in pieces if pc.end <= start and pc.run is not None]
    return bool(before and hyperlink_run(before[-1].run))


def is_blank_text(txt: str) -> bool:
    t = txt.strip()
    return not t or set(t) <= set("_ \t.   ") or bool(PLACEHOLDER_TEXT.match(t))


def is_option_word(txt: str) -> bool:
    return bool(OPTION_WORD.match(txt.strip()))


class Detector:
    def __init__(self, package: Package, *, layout_proposal=False):
        self.package = package
        self.index = SlotIndex(package)
        self.areas: list[Area] = []
        self.layout_proposal = layout_proposal
        self.layout_candidates = []
        self.notes: list[str] = []
        self.claimed: set = set()          # element ids already turned into an area (or used as its label)
        self.protected_regions: set[str] = set()
        self.floating_initials = False
        self._order = 0
        self._grid = {}
        self._text = {}
        self._ptext = {}
        self._heading = {}
        self._is_heading = {}
        self._numbering = None
        self._col_lists = {}
        self._pure = {}
        self._form_wide = None
        self._compute_headings()

    # -- cached reads ----------------------------------------------------------------------------------------------
    def text(self, el, own=True) -> str:
        key = (id(el), own)
        if key not in self._text:
            self._text[key] = text_of(el, own=own)
        return self._text[key]

    def ptext(self, p):
        if id(p) not in self._ptext:
            self._ptext[id(p)] = paragraph_text(p)
        return self._ptext[id(p)]

    def is_heading(self, p) -> bool:
        if id(p) in self._is_heading:
            return self._is_heading[id(p)]
        ppr = p.find(q("w:pPr"))
        style = ppr.find(q("w:pStyle")).get(q("w:val")) if ppr is not None and ppr.find(q("w:pStyle")) is not None else ""
        txt = self.text(p).strip()
        result = False
        if txt and len(txt) <= 120 and BOX not in txt and not UNDERSCORES.search(txt):
            if HEADING_STYLE.match(style or ""):
                result = True
            else:
                runs = [r for r in p.iter(R) if (r.findtext(T) or "").strip()]
                bold = runs and all(r.find(q("w:rPr")) is not None and r.find(q("w:rPr")).find(q("w:b")) is not None
                                    and (r.find(q("w:rPr")).find(q("w:b")).get(q("w:val")) or "1") not in ("0", "false") for r in runs)
                result = bool(bold) and not LABEL_END.search(txt) and len(txt.split()) <= 12
            # A plain printed side heading is still part of the question's identity.
            # It need not use a Word heading style: e.g. 'Left knee:' over a grid.
            if side_phrase(txt) and txt.endswith(":") and len(txt.split()) <= 6 and "\x00" not in self.ptext(p)[0]:
                result = True
        self._is_heading[id(p)] = result
        return result

    def _compute_headings(self):
        last = {}
        for s in self.index.slots:
            if s.kind != "p":
                continue
            self._heading[id(s.el)] = last.get(s.part, "")
            if self.is_heading(s.el):
                last[s.part] = clean_label(self.text(s.el))

    def heading_before(self, slot: Slot) -> str:
        s = slot
        while s is not None and s.kind != "p":
            if s.kind == "tc":
                first = next((c for c in s.children if c.kind == "p"), None)
                if first is not None:
                    s = first
                    break
            s = s.parent
        return self._heading.get(id(s.el), "") if s is not None else ""

    def grid(self, tbl_slot: Slot):
        if id(tbl_slot) not in self._grid:
            rows = {}
            for c in tbl_slot.children:
                if c.kind == "tc":
                    rows.setdefault(c.info["row"], []).append(c)
            self._grid[id(tbl_slot)] = rows
        return self._grid[id(tbl_slot)]

    def cell_text(self, tc_slot) -> str:
        return re.sub(r"\s+", " ", self.text(tc_slot.el, own=False)).strip()

    def is_empty_cell(self, tc_slot) -> bool:
        tc = tc_slot.el
        if not is_blank_text(self.text(tc, own=False)):
            return False
        for occ in (q("w:tbl"), q("w:sdt"), FLDCHAR, q("w:drawing"), q("w:pict"), q("w:object")):
            if tc.find(".//" + occ) is not None:
                return False
        return True

    def row_kind(self, tbl_slot, r) -> str:
        """data (has an empty/box/object cell) | divider (one text cell spanning the table) | label (text only)."""
        key = ("rowkind", id(tbl_slot), r)
        if key in self._grid:
            return self._grid[key]
        cells = [c for c in self.grid(tbl_slot).get(r, []) if c.info["vmerge"] != "continue"]
        width = max((c.info["col"] + c.info["span"] for rr in self.grid(tbl_slot).values() for c in rr), default=1)
        texts = [c for c in cells if self.cell_text(c) and not is_blank_text(self.cell_text(c))]
        kind = "label"
        cells = sorted(cells, key=lambda c: c.info["col"])
        # A native checkbox (BOX in the cell's objects, though its printed text omits it) is an answer too, and
        # so is a value cell (a drawn blank and no printed words: '▯▯▯') or an answer gap inside a printed line
        # ('Number of sessions:      Average duration:   minutes'): such a row is never a column header
        # (refutation F5, F8). A header that prints a blank beside its words ('Participant #____') still is one.
        if any(self.is_empty_cell(c) or BOX in self.cell_text(c) or "\x00" in self.cell_objects(c)
               or BOX in self.cell_objects(c) or CHECKED in self.cell_objects(c) or self.value_cell(c)
               or any(self.inline_answer_gap(x) for x in c.children if x.kind == "p") for c in cells):
            # a data row starts with its label (or an answer); a row that starts empty and carries text only in
            # cells spanning the answer columns is a sub-header ('| | | Yes/No/NA | |')
            first = cells[0] if cells else None
            starts_empty = first is not None and self.is_empty_cell(first) and first.info["col"] == 0
            if not (starts_empty and texts and all(c.info["span"] >= 2 for c in texts)):
                kind = "data"
        if len(texts) == 1 and texts[0].info["span"] >= max(2, width - 1) and all(
                c is texts[0] or self.is_empty_cell(c) for c in cells):
            kind = "divider"
        self._grid[key] = kind
        return kind

    def header_rows(self, tbl_slot):
        key = ("headers", id(tbl_slot))
        if key not in self._grid:
            out = []
            for r in sorted(self.grid(tbl_slot)):
                k = self.row_kind(tbl_slot, r)
                if k == "data":
                    break
                if k == "label":
                    out.append(r)
            self._grid[key] = out
        return self._grid[key]

    def text_at(self, tbl_slot, r, col, *, complete=False):
        for c in self.grid(tbl_slot).get(r, []):
            if c.info["col"] <= col < c.info["col"] + c.info["span"]:
                if c.info["vmerge"] == "continue":
                    return ""
                txt = self.cell_text(c)
                if txt and not is_blank_text(txt) and BOX not in txt and "\x00" not in self.cell_objects(c):
                    if len(txt) > 80 and not complete:
                        first = next((self.text(x.el).strip() for x in c.children if x.kind == "p" and self.text(x.el).strip()), "")
                        txt = first[:80]
                    return txt
                return ""
        return ""

    def grid_cols(self, tbl_slot) -> int:
        grid = tbl_slot.el.find(q("w:tblGrid"))
        return len(grid.findall(q("w:gridCol"))) if grid is not None else 0

    def header_table(self, tbl_slot):
        """A table continued from the previous one (split across pages, headers not repeated) reads its column
        headers from that table: same container, only empty paragraphs between, same grid width."""
        key = ("htable", id(tbl_slot))
        if key in self._grid:
            return self._grid[key]
        result = tbl_slot
        if not self.header_rows(tbl_slot):
            parent = tbl_slot.parent
            sibs = [x for x in (parent.children if parent is not None else self.index.roots)
                    if x.part == tbl_slot.part and x.kind in ("p", "tbl") and x.seq < tbl_slot.seq]
            for prev in reversed(sibs):
                if prev.kind == "p" and not self.text(prev.el).strip():
                    continue
                if prev.kind == "tbl" and self.grid_cols(prev) == self.grid_cols(tbl_slot) and self.grid_cols(prev):
                    result = self.header_table(prev)
                break
        self._grid[key] = result
        return result

    def column_header(self, tbl_slot, col, row, *, complete=False) -> str:
        """The label printed directly above (a label row over a blank row), else the table's header rows (a
        continued table's come from the table it continues)."""
        above = [r for r in self.grid(tbl_slot) if r < row]
        if above:
            r = max(above)
            if self.row_kind(tbl_slot, r) == "label":
                txt = self.text_at(tbl_slot, r, col, complete=complete)
                if txt:
                    return txt
        ht = self.header_table(tbl_slot)
        for r in reversed([h for h in self.header_rows(ht) if ht is not tbl_slot or h < row]):
            txt = self.text_at(ht, r, col, complete=complete)
            if txt:
                return txt
        return ""

    def column_headers_all(self, tbl_slot, col, row) -> list:
        ht = self.header_table(tbl_slot)
        out = [self.text_at(ht, r, col) for r in self.header_rows(ht) if ht is not tbl_slot or r < row]
        return [t for t in out if t]

    def cell_objects(self, c) -> str:
        return "".join(self.ptext(x.el)[0] for x in c.children if x.kind == "p")

    def is_label_cell(self, c, *, complete=False) -> bool:
        txt = self.cell_text(c)
        if not txt or is_blank_text(txt) or is_option_word(txt) or (len(txt) > 300 and not complete):
            return False
        objs = self.cell_objects(c)
        return BOX not in txt and CHECKED not in txt and "\x00" not in objs

    def prints_answer_blank(self, c) -> bool:
        """The cell is a value cell: it prints a drawn answer blank (digit-entry boxes, an underscore rule, an
        underlined gap). Leader dots after a printed label are not a blank here."""
        key = ("drawn", id(c.el))
        if key not in self._grid:
            self._grid[key] = any(kind in ("segmented", "utab") or kind == "blank" and "_" in printed[start:end]
                                  for x in c.children if x.kind == "p" for printed, pieces in [self.ptext(x.el)]
                                  for start, end, kind in self.blank_spans(printed, pieces))
        return self._grid[key]

    def value_cell(self, c) -> bool:
        """The cell prints a drawn answer blank and no printed words outside its blanks ('▯▯▯', '▯▯▯/▯▯▯')."""
        if not self.prints_answer_blank(c):
            return False
        for x in c.children:
            if x.kind != "p":
                continue
            printed, pieces = self.ptext(x.el)
            spans = self.blank_spans(printed, pieces)
            outside = "".join(ch for i, ch in enumerate(printed) if not any(a <= i < b for a, b, _ in spans))
            if re.search(r"[^\W\d_]", outside):
                return False
        return True

    def row_identity(self, tbl_slot, row, col, *, complete=False) -> str:
        """The leftmost label of the row (the item the row is about)."""
        for c in sorted(self.grid(tbl_slot).get(row, []), key=lambda c: c.info["col"]):
            if c.info["col"] >= col:
                break
            if self.is_label_cell(c, complete=complete):
                return clean_label(self.cell_text(c), limit=None if complete else 300)
        return ""

    def row_label(self, tbl_slot, row, col, printed=False, *, complete=False, values=True) -> str:
        """The row's label; `printed` reads it as an option (option_text: no list-marker strip). With
        values=False a value cell (one printing its own answer blank) is never the label."""
        read = option_text if printed else lambda text: clean_label(text, limit=None if complete else 300)
        rows = self.grid(tbl_slot)
        best = ""
        for c in sorted(rows.get(row, []), key=lambda c: c.info["col"]):
            if c.info["col"] >= col:
                break
            if self.is_label_cell(c, complete=complete) and (values or not self.prints_answer_blank(c)):
                best = read(self.cell_text(c))
        if not best:
            # a vertically merged label cell continues from the row above
            for c in rows.get(row, []):
                if c.info["col"] < col and c.info["vmerge"] == "continue":
                    for r in sorted((r for r in rows if r < row), reverse=True):
                        head = next((x for x in rows[r] if x.info["col"] == c.info["col"]), None)
                        if head is not None and head.info["vmerge"] != "continue":
                            best = read(self.cell_text(head))
                            break
        return best

    def context_for(self, slot: Slot, *, complete=False) -> str:
        parts = []
        cell = self.host_cell(slot)
        read = lambda text: clean_label(text, limit=None if complete else 300)
        if cell is not None:
            tbl = cell.parent
            header = read(self.column_header(tbl, cell.info["col"], cell.info["row"], complete=complete))
            ident = self.row_identity(tbl, cell.info["row"], cell.info["col"], complete=complete)
            rowlab = self.row_label(tbl, cell.info["row"], cell.info["col"], complete=complete)
            if ident and ident != rowlab:
                parts.append(ident if complete else ident[:120])
            if rowlab:
                parts.append(rowlab if complete else rowlab[:120])
            if header:
                parts.append(header if complete else header[:80])
        if complete:
            root = slot
            while root.parent is not None:
                root = root.parent
            head, problem = self.question_box_context(root)
            if problem:
                fail("The complete source section is unresolved: " + problem, "invalid_mapping")
            # Preserve headings inside real ancestor containers too. A sibling
            # from another cell is never the local heading of this destination.
            local, place = [], slot
            while place.parent is not None:
                headings = []
                for sibling in place.parent.children:
                    if sibling is place:
                        break
                    if sibling.kind != "p" or not self.text(sibling.el).strip():
                        continue
                    heading, _, issue = self.question_box_paragraph(sibling.el)
                    if issue and not issue.startswith("A page break "):
                        fail("The complete source section is unresolved: " + issue, "invalid_mapping")
                    if heading:
                        headings.append(re.sub(r"\s+", " ", self.text(sibling.el)).strip())
                if headings:
                    local.insert(0, headings[-1])
                place = place.parent
            head = " > ".join(dict.fromkeys(x for x in [head] + local if x))
        else:
            head = self.heading_before(slot)
        if head:
            parts.insert(0, head if complete else head[:120])
        context = " > ".join(dict.fromkeys(p for p in parts if p))
        return context if complete else context[:300]

    def host_paragraph(self, slot):
        s = slot
        while s is not None and s.kind != "p":
            s = s.parent
        return s

    def host_cell(self, slot):
        s = slot
        while s is not None and s.kind != "tc":
            s = s.parent
        return s

    def siblings(self, pslot):
        parent = pslot.parent
        if parent is None:
            return [s for s in self.index.roots if s.part == pslot.part and s.kind == "p"]
        return [s for s in parent.children if s.kind == "p"]

    def para_neighbours(self, pslot):
        sibs = self.siblings(pslot)
        idx = next((i for i, s in enumerate(sibs) if s is pslot), None)
        return sibs, idx

    def previous_paragraph_text(self, pslot, limit=3) -> str:
        sibs, idx = self.para_neighbours(pslot)
        if idx is None:
            return ""
        for s in reversed(sibs[max(0, idx - limit):idx]):
            t = self.text(s.el).strip()
            if t:
                return t
        return ""

    def previous_paragraph(self, pslot, limit=3):
        sibs, idx = self.para_neighbours(pslot)
        if idx is None:
            return None
        for s in reversed(sibs[max(0, idx - limit):idx]):
            if self.text(s.el).strip():
                return s
        return None

    def cell_has_claim(self, tc) -> bool:
        return any(id(x) in self.claimed for x in tc.iter())

    def region_hidden(self, region) -> bool:
        """hidden_boxes, once per region (a paragraph or a table cell)."""
        return region_hidden(self.index, region)

    def owning_cell(self, pslot):
        """The table cell whose OWN paragraph `pslot` is - directly, or inside block-level content controls wrapping it
        (w:tc/w:sdt/w:p) - else None. A nested table's or a text box's paragraph is not its outer cell's own."""
        s = pslot.parent
        while s is not None and s.kind == "sdt":
            s = s.parent
        return s if s is not None and s.kind == "tc" else None

    def own_paragraphs(self, cell) -> list:
        """A cell's own paragraphs in order: direct ones and those inside block-level content controls wrapping them.
        ⚠️ Direct children only made a box in a wrapped paragraph a stranger to its cell: detected alone as 'Checkbox'
        while the row's No box took the row's question (round 3 P2)."""
        return own_paragraph_slots(cell)

    def unattributed_row_boxes(self, cells) -> bool:
        """Whether the row of `cells` prints a box (or holds a checkbox control) in another cell answering the same row
        label - between the label cells around them - than `cells`, the cells a group of boxes was read from."""
        first = cells[0]
        row = sorted((c for c in self.grid(first.parent).get(first.info["row"], []) if c.info["vmerge"] != "continue"),
                     key=lambda c: c.info["col"])
        if first not in row:
            return False
        at = row.index(first)
        stretch = []
        for side in (reversed(row[:at]), row[at + 1:]):
            for c in side:
                if self.is_label_cell(c):
                    break
                stretch.append(c)
        return any(c not in cells and (BOX in self.cell_text(c) or CHECKED in self.cell_text(c) or checkbox_nodes(c.el, own=False))
                   for c in stretch)

    # -- adding ----------------------------------------------------------------------------------------------------
    def add(self, area: Area):
        self._order += 1
        area.order = self._order
        if area.slot.kind == "tc":
            area.order = self._order
        self.areas.append(area)
        self.claimed.add(id(area.slot.el))

    def kind_for(self, label: str) -> str:
        label = label or ""
        if SIGNATURE.search(label) and not DATE_LABEL.search(label):
            return "signature"
        if INITIALS.search(label) and not DATE_LABEL.search(label):
            return "initials"
        # A free-text destination asking for description keeps the whole
        # answer even when its printed question also mentions a date or time.
        # Dedicated native date controls are typed by their own OOXML rule.
        if LONG_LABEL.search(label):
            return "long_text"
        if TIME_LABEL.search(label) and not DATE_LABEL.search(label):
            return "time"
        if DATE_LABEL.search(label) or re.search(r"\bdated\s*$", label, re.I):
            return "date"
        return "text"

    def choice_kind(self, question: str, options: list, hint="") -> str:
        pieces = [question or ""] + (list(hint) if isinstance(hint, (list, tuple)) else [hint or ""])
        text = " ".join(pieces)
        # Explicit one-only wording keeps the question single; "one or more", "1-3", "one/both" and "1+" are not
        # one-only (a conflict with "all that apply" is refused by the checkbox-group reader, never narrowed here).
        if one_only(pieces, question):
            return "choice"
        if options and all(YESNO.match((o or "").strip()) for o in options):
            return "choice"
        if CHECK_ALL.search(text) or re.search(r"\(s\)|\bapply\b", question or "", re.I):
            return "multi_choice"
        return "choice"

    # -- the rules -------------------------------------------------------------------------------------------------
    def detect(self):
        self.rule_protected_signing_areas()
        self.rule_content_controls()
        self.rule_form_fields()
        self.rule_tab_columns()
        self.rule_coded_column_sequences()
        self.rule_checkboxes()
        self.rule_question_boxes(list_only=True)
        self.rule_text_option_choices()
        self.rule_tables()
        self.rule_question_boxes()
        self.rule_checkboxes(leftovers=True)
        self.rule_lines_below_label()
        self.rule_paragraph_fields()
        self.rule_inline_initial_boxes()
        self.merge_header_copies()
        self.areas.sort(key=lambda a: (self.index.by_id[a.slot.id].seq if a.slot.id in self.index.by_id else 0, a.order))
        self.qualify_sides()
        self.surface_duplicates()
        for a in list(self.areas):
            if a.complete_source and (len(a.label) > MAX_MAPPING_LABEL or len(a.context) > MAX_MAPPING_CONTEXT):
                self.notes.append("Unassigned answer box at " + a.slot.id +
                                  ". The complete question or section exceeds the mapping limit; nothing was shortened. "
                                  "Printed text: " + a.label + " Section: " + a.context)
                self.areas.remove(a)
                # A withdrawn area is no longer a layout proposal either; its source stays claimed.
                self.layout_candidates[:] = [c for c in self.layout_candidates if c[2] is not a]
                continue
            a.capacity = self.capacity_for(a)
        self.areas.sort(key=lambda a: (self.index.by_id[a.slot.id].seq if a.slot.id in self.index.by_id else 0, a.order))
        return self.areas, self.notes

    def qualify_sides(self):
        """A side printed in another row cell or its heading belongs to the question used for source matching.
        Checkbox/option cells are excluded: their 'Left'/'Right' words are possible answers, not a governing side.
        Stored mappings are never rewritten; this qualifies only newly detected areas."""
        area_cells = {}
        cell_owners = {}
        for number, area in enumerate(self.areas):
            slots = [area.slot] + area.extra_slots
            for box in area.target.get("boxes", []):
                slot = self.index.by_id.get("%s#%s" % (box.get("part"), box.get("slot")))
                if slot is not None:
                    slots.append(slot)
            cells = {cell.id for slot in slots if (cell := self.host_cell(slot)) is not None}
            area_cells[number] = cells
            for identity in cells:
                cell_owners.setdefault(identity, set()).add(number)
        for number, area in enumerate(self.areas):
            if side_phrase(area.label):
                continue
            scope = []
            cell = self.host_cell(area.slot)
            if cell is not None:
                row = sorted(self.grid(cell.parent).get(cell.info["row"], []), key=lambda c: c.info["col"])
                positions = [i for i, c in enumerate(row) if c.id in area_cells[number]]
                if positions:
                    # A row can contain independent Right/Left sections. Use its
                    # nearest preceding side, including for several detail answers
                    # under that side. A trailing side cannot cross another answer.
                    before = list(reversed(row[:min(positions)]))
                    after = row[max(positions) + 1:]
                    for candidates, preceding in ((before, True), (after, False)):
                        for candidate in candidates:
                            if cell_owners.get(candidate.id, set()) - {number}:
                                if preceding:
                                    continue
                                break
                            text = clean_label(self.cell_text(candidate))
                            objects = self.cell_objects(candidate)
                            if any(c in objects for c in (BOX, CHECKED, "\x00")) or \
                                    checkbox_nodes(candidate.el, own=False) or is_blank_text(text):
                                if preceding:
                                    continue
                                break
                            if side_phrase(text) and text not in (clean_label(o) for o in area.options):
                                scope.append(text)
                                break
                        if scope:
                            break
                if not scope:
                    # Side sections can repeat within one table. The nearest label row owns
                    # this section; the table's first column heading may name the opposite leg.
                    for row in sorted((r for r in self.grid(cell.parent) if r < cell.info["row"]), reverse=True):
                        if self.row_kind(cell.parent, row) != "label":
                            continue
                        header = clean_label(self.text_at(cell.parent, row, cell.info["col"]))
                        phrases = [header] if side_phrase(header) else [clean_label(self.cell_text(c))
                                   for c in self.grid(cell.parent)[row] if side_phrase(clean_label(self.cell_text(c)))]
                        scope.extend(s for s in phrases if s not in (clean_label(o) for o in area.options))
                        break
            if not scope:
                # A heading in another cell or a previous answer must not govern this field.
                # Walk actual containers, considering only preceding sibling headings.
                place = area.slot
                while place is not None:
                    siblings = place.parent.children if place.parent is not None else self.index.roots
                    previous = [p for p in siblings if p.part == place.part and p.kind == "p" and p.seq < place.seq
                                and id(p.el) not in self.claimed and self.is_heading(p.el)]
                    if previous:
                        head = clean_label(self.text(previous[-1].el))
                        if side_phrase(head):
                            scope.append(head)
                        break
                    place = place.parent
            # Keep each complete source phrase; truncating it could remove its side.
            scope = list(dict.fromkeys(s for s in scope if s and
                                      not re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", area.label, re.I)))
            if scope:
                area.label = " — ".join(scope + [area.label])
                context = " > ".join(dict.fromkeys(s for s in scope + [area.context] if s))
                area.context = context if area.complete_source else context[:300]

    def label_before_object(self, slot, obj_el) -> str:
        """Text before an inline object in its paragraph (after any previous object); else row label / column header /
        previous paragraph."""
        p = self.host_paragraph(slot)
        if p is not None:
            text, pieces = self.ptext(p.el)
            pos = next((pc.start for pc in pieces if pc.node is obj_el), None)
            if pos is not None:
                before = text[:pos]
                before = re.split(r"[\x00" + BOX + CHECKED + r"]", before)[-1]
                before = re.split(r"\t{2,}| {4,}", before)[-1] if re.search(r"\S", re.split(r"\t{2,}| {4,}", before)[-1]) else before
                label = clean_label(before)
                if label and not UNDERSCORES.fullmatch(label):
                    return label
        cell = self.host_cell(slot)
        if cell is not None:
            left = self.row_label(cell.parent, cell.info["row"], cell.info["col"])
            if left:
                return left
            head = self.column_header(cell.parent, cell.info["col"], cell.info["row"])
            if head:
                return clean_label(head)
        if p is not None:
            return clean_label(self.previous_paragraph_text(p))
        return ""

    # 1. content controls ------------------------------------------------------------------------------------------
    def rule_content_controls(self):
        for slot in self.index.slots:
            if slot.kind != "sdt" or id(slot.el) in self.claimed:
                continue
            info = slot.info
            typ = info["type"]
            if typ in ("docPartObj", "docPartList", "citation", "bibliography", "equation", "picture", "group", "checkbox"):
                continue
            content = slot.el.find(q("w:sdtContent"))
            if content is not None and content.find(".//" + q("w:hyperlink")) is not None:
                self.notes.append("A content control containing a fixed hyperlink was read by its parts. Location: "
                                  + slot.id)
                continue
            if content is not None and wraps_structure(content):
                # A control that wraps other controls, fields, tables or drawings is a container, not an
                # answer: writing into it would replace what it holds. Its contents are read by the other rules.
                self.notes.append("A content control that contains other form parts was read by its parts.")
                continue
            shown = self.text(content, own=False).strip() if content is not None else ""
            empty_like = info["placeholder"] or is_blank_text(shown) or bool(ENTER_HINT.match(shown))
            label = info["alias"] or info["tag"] or self.label_before_object(slot, slot.el)
            if typ in ("dropDownList", "comboBox"):
                options = [o for o in info["options"] if o and not PLACEHOLDER_TEXT.match(o)]
                self.add(Area("choice", clean_label(label) or "Choice", slot, {"type": "sdt_choice"},
                              context=self.context_for(slot), options=options))
            elif typ == "date":
                self.add(Area("date", clean_label(label) or "Date", slot, {"type": "sdt_text", "date": True},
                              context=self.context_for(slot)))
            elif empty_like:
                self.add(Area(self.kind_for(label), clean_label(label) or "Answer", slot, {"type": "sdt_text"},
                              context=self.context_for(slot)))
            else:
                self.notes.append("A content control holding fixed text was kept as printed: %s" % shown[:60])
            for x in slot.el.iter():
                self.claimed.add(id(x))

    # 2. legacy text fields and dropdowns --------------------------------------------------------------------------
    def rule_form_fields(self):
        for slot in self.index.slots:
            if slot.kind != "ff" or slot.info["field"] == "FORMCHECKBOX" or id(slot.el) in self.claimed:
                continue
            label = self.label_before_object(slot, slot.el) or slot.info.get("name") or "Answer"
            if slot.info["field"] == "FORMDROPDOWN":
                self.add(Area("choice", clean_label(label), slot, {"type": "ff_dropdown"}, context=self.context_for(slot),
                              options=[o for o in slot.info.get("options", []) if o]))
            else:
                kind = "date" if slot.info.get("input_type") == "date" else self.kind_for(label)
                self.add(Area(kind, clean_label(label), slot, {"type": "ff_text"}, context=self.context_for(slot),
                              protection=ff_text_protection(slot.el)))

    # 3. checkboxes: content-control, legacy and glyph boxes, grouped into questions -------------------------------
    def box_units(self, pslot):
        """[(box_ref, option_text, before_text)] for every box in one paragraph, in order."""
        text, pieces = self.ptext(pslot.el)
        positions = [i for i, ch in enumerate(text) if ch in (BOX, CHECKED)]
        units = []
        glyph_n = 0
        for n, pos in enumerate(positions):
            piece = next(pc for pc in pieces if pc.start <= pos < pc.end)
            if piece.kind == "obj":
                slot = self.index.by_el.get(id(piece.node))
                ref = {"kind": "sdt" if piece.obj == "sdt_checkbox" else "ff", "part": pslot.part,
                       "slot": slot.path if slot is not None else pslot.path}
            else:
                ref = {"kind": "glyph", "part": pslot.part, "slot": pslot.path + "/glyphs", "glyph": glyph_n}
                glyph_n += 1
            end = positions[n + 1] if n + 1 < len(positions) else len(text)
            option = text[pos + 1:end]
            # the option ends at a wide gap followed by more text only when it is the last box on the line
            units.append([ref, option, text[:pos] if n == 0 else ""])
        return units

    def tab_column_properties(self, slot, *, scope_only=False):
        """Resolve additive stops and per-attribute indentation; unknown layout refuses."""
        styles = self.package.tree("word/styles.xml") if "word/styles.xml" in self.package.names else None
        props = []
        if styles is not None:
            props.append(styles.find("./" + q("w:docDefaults") + "/" + q("w:pPrDefault") + "/" + q("w:pPr")))
        cell = self.host_cell(slot)
        for kind, ref in (("table", cell.parent.el.find("./" + q("w:tblPr") + "/" + q("w:tblStyle"))
                           if cell is not None else None),
                          ("paragraph", slot.el.find("./" + q("w:pPr") + "/" + q("w:pStyle")))):
            if ref is not None:
                name = ref.get(q("w:val"))
            else:
                defaults = [s for s in styles.findall(q("w:style")) if s.get(q("w:type")) == kind
                            and s.get(q("w:default")) in ("1", "true", "on")] if styles is not None else []
                if len(defaults) > 1:
                    return None
                name = defaults[0].get(q("w:styleId")) if defaults else None
            if name:
                chain, problem = self.question_box_style_chain(name, kind)
                if problem or any(s.find(q("w:tblStylePr")) is not None for s in chain):
                    return None
                props.extend(s.find(q("w:pPr")) for s in reversed(chain))
            elif ref is not None:
                return None
        props.append(slot.el.find(q("w:pPr")))
        stops, indent = {}, {}
        forbidden = {q("w:bidi"), q("w:mirrorIndents"), q("w:numPr"), q("w:framePr"), q("w:sectPr"),
                     q("w:pBdr"), q("w:shd"), q("w:pageBreakBefore")}
        for ppr in (p for p in props if p is not None):
            if any(c.tag in forbidden for c in ppr):
                return None
            alignment = ppr.find(q("w:jc"))
            if alignment is not None and alignment.get(q("w:val")) not in ("left", "start", "both"):
                return None
            ind = ppr.find(q("w:ind"))
            if ind is not None:
                if any(etree.QName(k).localname not in ("left", "right", "firstLine", "hanging") for k in ind.attrib):
                    return None
                try:
                    indent.update({etree.QName(k).localname: int(v) for k, v in ind.attrib.items()})
                except ValueError:
                    return None
            local = set()
            for tab in ppr.findall("./" + q("w:tabs") + "/" + q("w:tab")):
                try:
                    position = int(tab.get(q("w:pos"), ""))
                except ValueError:
                    return None
                if position in local:
                    return None
                local.add(position)
                value = tab.get(q("w:val"))
                if value == "clear":
                    stops.pop(position, None)
                elif value in ("left", "center", "right", "decimal", "bar"):
                    stops[position] = value
                else:
                    return None
        if scope_only:
            return (), ()  # Scope text/spacers need boundary validation, not option coordinates.
        # A hanging indent creates another implicit stop; do not erase it by
        # pretending that the explicit center list is the entire layout.
        if indent.get("hanging", 0) or indent.get("firstLine", 0):
            return None
        return sorted((pos, kind) for pos, kind in stops.items() if pos > 0), \
            (indent.get("left", 0), indent.get("right", 0))

    def tab_source_visible(self, slot):
        """Prove this relation's source has no hidden/unknown formatting.

        Style toggle/conditional overrides are deliberately not guessed: an
        enabled hide marker anywhere in the applicable ancestry remains unresolved.
        This is separate from region_hidden, which checks checkbox containment.
        """
        hide = {q("w:vanish"), q("w:webHidden"), q("w:specVanish")}
        def unhidden(node):
            return node is None or not any(n.tag in hide and n.get(q("w:val"), "1")
                                           not in ("0", "false", "off") for n in node.iter())
        if not unhidden(slot.el):
            return False
        styles = self.package.tree("word/styles.xml") if "word/styles.xml" in self.package.names else None
        if styles is not None and not unhidden(styles.find(q("w:docDefaults"))):
            return False
        def visible_style(refs, kind):
            if len(refs) > 1:
                return False
            if refs:
                name = refs[0].get(q("w:val"))
            else:
                defaults = [s for s in styles.findall(q("w:style")) if s.get(q("w:type")) == kind
                            and s.get(q("w:default")) in ("1", "true", "on")] if styles is not None else []
                if len(defaults) > 1:
                    return False
                if not defaults:
                    return True
                name = defaults[0].get(q("w:styleId"))
            chain, problem = self.question_box_style_chain(name, kind)
            return not problem and all(unhidden(style) for style in chain)
        if not visible_style(slot.el.findall("./" + q("w:pPr") + "/" + q("w:pStyle")), "paragraph"):
            return False
        for run in slot.el.iter(R):
            if not visible_style(run.findall("./" + q("w:rPr") + "/" + q("w:rStyle")), "character"):
                return False
        parent = slot.parent
        while parent is not None:
            if parent.kind == "tbl" and not visible_style(
                    parent.el.findall("./" + q("w:tblPr") + "/" + q("w:tblStyle")), "table"):
                return False
            parent = parent.parent
        return True

    def marked_column_headers(self, cell):
        """Visible text of the repeating (marked) header rows spanning this cell, or the issue that
        makes them unusable: hidden/unresolved visibility, or an answer area inside the header."""
        headers, issue = [], ""
        for number, row in enumerate(cell.parent.el.findall(q("w:tr"))[:cell.info["row"]]):
            marked = row.find("./" + q("w:trPr") + "/" + q("w:tblHeader"))
            if marked is None or marked.get(q("w:val"), "1") in ("0", "false", "off"):
                continue
            for owner in self.grid(cell.parent).get(number, []):
                if owner.info["col"] <= cell.info["col"] and owner.info["col"] + owner.info["span"] >= cell.info["col"] + cell.info["span"]:
                    header_paras = self.own_paragraphs(owner)
                    if any(not self.tab_source_visible(p) for p in header_paras):
                        issue = "The column header has hidden or unresolved visibility."
                    headers.extend(self.ptext(p.el)[0].strip() for p in header_paras if self.ptext(p.el)[0].strip())
                    if any(self.box_units(p) or self.blank_spans(*self.ptext(p.el))
                           or "\x00" in self.ptext(p.el)[0] for p in self.own_paragraphs(owner)) \
                            or any(node.tag in (q("w:drawing"), q("w:pict"), q("w:tbl")) for node in owner.el.iter()):
                        issue = "The column header contains an answer area."
        return headers, issue

    # 'Label:' then a printed gap (a tab, or three or more spaces) and more of the line ('Temp:          °C'): the
    # answer is written in the gap.
    ANSWER_LINE = re.compile(r"[^\t\x00:;?!]*[^\W\d_][^\t\x00:;?!]*:(?:[ \u00a0]*\t[ \t\u00a0]*|[ \u00a0]{3,})\S")

    def answer_cell(self, c) -> bool:
        """The cell holds an answer place of its own: a box or other control, a drawn answer blank of any kind (an
        underscore rule, leader dots or an ellipsis, digit boxes, a bracket, an underlined gap: every blank the
        engine itself maps as an answer), or a printed answer gap after a label (refutation F2, R3-3)."""
        objects = self.cell_objects(c)
        return BOX in objects or CHECKED in objects or "\x00" in objects or any(
            self.blank_spans(printed, pieces) or self.ANSWER_LINE.search(printed)
            for x in c.children if x.kind == "p" for printed, pieces in [self.ptext(x.el)])

    def printed_row_label(self, cell):
        """(question, issue, group) for the row of `cell`: the row's question printed in its own plain label cell
        to the left; or the issue when a cell to the left prints something that is not one; and the text of any
        vertically merged cell to the left, which spans several rows, so it is context and no one row's question.
        A cell that holds its own answer (a box, a control, a drawn blank) is another question: never this row's.
        A cell to the right (comments, fixed details) never names the row (refutation F2)."""
        table, row, col = cell.parent, cell.info["row"], cell.info["col"]
        rows = self.grid(table)
        groups, plain = [], []
        for c in sorted((c for c in rows.get(row, []) if c.info["col"] < col), key=lambda c: c.info["col"]):
            if c.info["vmerge"]:
                head = c
                if c.info["vmerge"] == "continue":
                    head = next((x for r in sorted((r for r in rows if r < row), reverse=True) for x in rows[r]
                                 if x.info["col"] == c.info["col"] and x.info["vmerge"] != "continue"), None)
                if head is None or self.answer_cell(head):
                    return "", "A merged cell to the left of the source is not a printed group label.", ""
                if not is_blank_text(self.cell_text(head)):
                    groups.append(clean_label(self.cell_text(head)))
                continue
            if self.answer_cell(c):
                return "", "A cell to the left of the source holds its own answer; it is not this row's question.", ""
            if not is_blank_text(self.cell_text(c)):
                plain.append(c)
        group = " > ".join(g for g in groups if g)
        label = ""
        for c in plain:
            if self.is_label_cell(c):
                label = clean_label(self.cell_text(c))
        if label and re.search(r"[^\W\d_]", label):
            return label, "", group
        if plain:
            return "", "A cell to the left of the source prints text that is not a usable row label.", group
        return "", "", group

    # A number printed in a header option, in any legend form: '2 = Abnormal', '(2)', '2)', '1. Normal', 'Normal (1.)',
    # and a decimal '1.0 Normal' (read whole, so it never equals a code '1'). Never part of a word ('12b').
    HEADER_NUMBER = re.compile(r"(?<![\w.])[(\[]?(\d{1,3}(?:\.\d+)?)\.?[)\]]?(?![\w.])")
    # A legend printed in the governing text (a title, lead or heading): '(codes: 1 = Abnormal, 2 = Normal)'.
    LEGEND_PAIR = re.compile(r"(?<![\w.])(\d{1,3})\s*=\s*([^\W\d_]+(?:[ '\u2019/-]+[^\W\d_]+)*)")
    # ... or as a numbered list of two or more of the row's codes: '(1) Abnormal (2) Normal', '1. Abnormal 2. Normal'.
    LEGEND_LIST = re.compile(r"(?<![\w.])(?:\((\d{1,3})\)|(\d{1,3})\s*[.:)\-\u2013])\s*([^\W\d_]+(?:[ '\u2019/-]+[^\W\d_]+)*)")

    def legend_conflict(self, options, row, governing=""):
        """A printed header whose options also print numbers ('2 = Abnormal', '1. Normal') is a code legend. It
        agrees with a row only when each option prints exactly the code printed before the box under it; otherwise
        which box means which option is not certain (refutation F4, R3-2). A legend printed in the governing text
        ('codes: 1 = Abnormal, 2 = Normal') must name, for each code it prints, the option printed over that code's
        box. A header and governing text that print no number never conflict."""
        codes = re.findall(r"(\d{1,3})\s*[☐☒]", self.ptext(row.el)[0])
        printed = [self.HEADER_NUMBER.findall(option) for option in options]
        if any(printed) and (len(codes) != len(options) or any(found != [code] for found, code in zip(printed, codes))):
            return True
        words = lambda text: " %s " % " ".join(re.findall(r"[^\W\d_]+", text.lower()))
        pairs = self.LEGEND_PAIR.findall(governing)
        for segment in re.split(r" > | \| ", governing):
            listed = [(a or b, meaning) for a, b, meaning in self.LEGEND_LIST.findall(segment)]
            if len(listed) >= 2 and all(code in codes for code, _ in listed):
                pairs.extend(listed)
        for code, meaning in pairs:
            if code not in codes or len(codes) != len(options):
                return True
            option, meaning = words(options[codes.index(code)]), words(meaning)
            if meaning not in option and option not in meaning:
                return True
        return False

    def coded_kind(self, label, options, context):
        """A coded response row records one code per row. Only a literal instruction widens it; a plural label
        ('Lesion(s)') or 'apply' is not one."""
        text = label + " " + context
        if CHECK_ONE.search(text) or all(YESNO.match((o or "").strip()) for o in options):
            return "choice"
        return "multi_choice" if CHECK_ALL.search(text) else "choice"

    def rule_tab_columns(self):
        """Complete same-cell title + repeated header/response pairs, never numeric-code guessing."""
        def coded(slot):
            if slot.kind != "p" or id(slot.el) in self.claimed:
                return None
            text = self.ptext(slot.el)[0]
            segments = text.rstrip(" \t").split("\t")
            if len(segments) < 2 or not all(re.fullmatch(r"\s*\d{1,3}\s*[☐☒]\s*", s)
                                           for s in segments[1:]):
                return None
            codes = [re.sub(r"\D", "", s) for s in segments[1:]]
            if len(set(codes)) != len(codes):
                return None
            return segments[0].strip(), len(codes)
        for cell in (s for s in self.index.slots if s.kind == "tc"):
            candidates = [s for s in cell.children if coded(s)]
            if not candidates:
                continue
            source = " | ".join(self.ptext(s.el)[0] for s in cell.children if s.kind == "p")
            problem = "The cell is not one complete title followed by header/response pairs."
            paragraphs = [s for s in cell.children if s.kind == "p" and self.ptext(s.el)[0].strip()]
            complete = cell.parent.parent is None and all(s.kind in ("p", "glyphs") for s in cell.children)
            complete = complete and len(paragraphs) >= 3 and len(paragraphs) % 2 == 1
            pending = []
            if complete:
                title = self.ptext(paragraphs[0].el)[0].strip()
                complete = not (self.box_units(paragraphs[0]) or self.blank_spans(*self.ptext(paragraphs[0].el))
                                or "\x00" in title)
                if self.tab_column_properties(paragraphs[0], scope_only=True) is None or any(
                        node.tag in (q("w:drawing"), q("w:pict"), q("w:object"), q("w:br"), q("w:sectPr"))
                        for node in cell.el.iter()):
                    complete = False
                context, issue = self.question_box_context(cell.parent, require_visible=True)
                if any(not self.tab_source_visible(p) for p in paragraphs):
                    complete = False
                    problem = "A source title, header or response has hidden or unresolved visibility."
                headers, header_issue = self.marked_column_headers(cell)
                row_question, row_issue, group = self.printed_row_label(cell)
                issue = header_issue or row_issue or issue
                context = " > ".join(x for x in (context, *headers, group, row_question, title) if x)
                if issue or len(context) > MAX_MAPPING_CONTEXT or self.question_box_signing(context):
                    complete = False
                    problem = row_issue or "The complete governing context is unresolved, oversized or protected."
                for header, row in zip(paragraphs[1::2], paragraphs[2::2]):
                    item = coded(row)
                    printed = self.ptext(header.el)[0].rstrip(" \t").split("\t")
                    options = [s.strip() for s in printed[1:]]
                    header_layout, row_layout = self.tab_column_properties(header), self.tab_column_properties(row)
                    summary = bool(item and not item[0] and len(paragraphs) == 3)
                    # A lone unlabelled row: the question printed in its own label cell, else the cell title.
                    unlabelled = row_question or title
                    if (not item or not (item[0] or summary) or len(item[0] or unlabelled) > MAX_MAPPING_LABEL or printed[0].strip()
                            or any(char in item[0] for char in (BOX, CHECKED, "\x00", "\n"))
                            or self.blank_spans(*self.ptext(row.el))
                            or len(options) != item[1] or not all(options) or len(set(options)) != len(options)
                            or any(len(o) > 300 for o in options)
                            or self.box_units(header) or self.blank_spans(*self.ptext(header.el))
                            or any("\x00" in o or "\n" in o for o in options)
                            or not header_layout or not row_layout or header_layout[1] != row_layout[1]
                            or header_layout[0][:item[1]] != row_layout[0][:item[1]]
                            or len(header_layout[0]) < item[1]
                            or any(kind != "center" for _, kind in header_layout[0][:item[1]])):
                        complete = False
                        problem = "Literal headers, complete row labels or effective tab coordinates do not agree."
                        break
                    label = item[0] or unlabelled
                    if self.legend_conflict(options, row, context):
                        complete = False
                        problem = "The printed header prints numbers that are not the row's response codes."
                        break
                    if self.question_box_signing(label) or any(self.question_box_signing(o) for o in options):
                        complete = False;problem = "The printed row or options contain signing/consent instructions.";break
                    refs = [unit[0] for unit in self.box_units(row)]
                    if len(refs) != len(options) or self.region_hidden(box_region(row.el)):
                        complete = False;problem = "A source control is not independently readable.";break
                    instructions = label + " " + context
                    if CHECK_ONE.search(instructions) and CHECK_ALL.search(instructions):
                        complete = False;problem = "The governing cardinality instructions conflict.";break
                    if re.search(r"\bselect up to\b", instructions, re.I):
                        complete = False;problem = "The governing cardinality includes an unrepresented selection limit.";break
                    kind = self.coded_kind(label, options, context)
                    pending.append((header, row, Area("checkbox" if len(options) == 1 else kind, label, row,
                        {"type": "checkboxes", "boxes": refs}, context=context,
                        options=options, complete_source=True)))
                # A blank paragraph may still be a separate drawn answer area.
                for spacer in (s for s in cell.children if s.kind == "p" and not self.ptext(s.el)[0].strip()):
                    if not self.plain_spacing_paragraph(spacer, unused_tab_stops=True) \
                            or self.tab_column_properties(spacer, scope_only=True) is None:
                        complete = False;problem = "A marked spacer or unresolved layout boundary separates the source."
            if not complete or len(pending) != len(candidates):
                self.notes.append("Tab-column options at " + cell.id + ": " + problem + " Printed source: " + source)
                for slot in candidates:
                    self.claimed.add(id(slot.el))
                continue
            self.claimed.add(id(paragraphs[0].el))
            for header, row, area in pending:
                self.claimed.add(id(header.el))
                self.layout_candidates.append((header, row, area))
                if self.layout_proposal:
                    self.add(area)
                else:
                    self.claimed.add(id(row.el))
                    self.notes.append("Layout verification required for tab-column answer at " + row.id +
                                      ". Printed question: " + area.label + ". Section: " + area.context)

    def coded_choice_paragraph(self, slot):
        """Recognise response codes only as evidence that labels live elsewhere."""
        text = self.ptext(slot.el)[0]
        marks = list(re.finditer("[☐☒]", text))
        if len(marks) < 2 or text[marks[-1].end():].strip():
            return False
        codes = []
        for i, mark in enumerate(marks):
            segment = text[marks[i - 1].end() if i else 0:mark.start()]
            match = re.fullmatch(r"(?:.*?\s)?(\d{1,3})\s*", segment, re.S) if not i else \
                re.fullmatch(r"\s*(\d{1,3})\s*", segment)
            if not match:
                return False
            codes.append(match.group(1))
        return len(set(codes)) == len(codes)

    # A response code as forms print it: '1', '(1)', '1.', '#1', '1a', '1=', '1:', '1 -', 'a)', 'a', 'I', 'iv'.
    CODE_TOKEN = r"(?:#\s?)?[(\[]?(?:\d{1,3}[a-z]?|[a-z]|[ivx]{1,4})[)\].:=]?(?:\s?[-\u2013=:])?"
    CODE_BEFORE = re.compile(r"(?:^|\s)" + CODE_TOKEN + r"\s*$", re.I)
    CODE_BARE = re.compile(r"\s*" + CODE_TOKEN + r"\s*", re.I)

    def response_code_row(self, slot):
        """A row whose boxes are printed after digit codes ('1 ☐ 2 ☐', '(1) ☐', 'Shape ☐ 2 ☐'), in any shape.
        Reading the text after each box as its option would name a box by the next box's code: such a row
        is a coded row, and its meanings live in a printed header, never in the codes.
        Numbers printed after their boxes ('☐ 0 ☐ 1 ☐ 2') are those boxes' own options and stay readable."""
        text = self.ptext(slot.el)[0]
        marks = [m.start() for m in re.finditer("[☐☒]", text)]
        if len(marks) < 2:
            return False
        segments = [text[marks[i - 1] + 1 if i else 0:mark] for i, mark in enumerate(marks)]
        before = [bool(self.CODE_BEFORE.search(segment)) for segment in segments]
        if all(before):
            return True  # a code printed before every box
        bare = [segment for segment in segments[1:] if self.CODE_BARE.fullmatch(segment)]
        if not bare:
            return False
        # A bare code between two boxes is the previous box's option or the next box's code. It is the previous
        # box's option only when the whole row reads box-then-option: nothing coded before the first box, an option
        # (a number or a word) printed after the last box, every bare code printed against the box before it, and
        # the first box's own option starting its sequence ('☐ 0', '☐ 1', '☐ I', '☐ A'). 'Stage: ☐ I ... ☐ IV ☐
        # Unknown' is read; 'Shape ☐ 2 ☐ Other' (the first box's code missing) is a coded row (refutation R3-4).
        if before[0] or not text[marks[-1] + 1:].strip():
            return True
        if any(gap_width(s[:len(s) - len(s.lstrip())]) > gap_width(s[len(s.rstrip()):]) for s in bare):
            return True
        first = segments[1]
        return bool(self.CODE_BARE.fullmatch(first)) and \
            re.sub(r"[#\s()\[\].:=\-\u2013]", "", first).lower() not in ("0", "1", "a", "i")

    def coded_column_parts(self, slot):
        if not self.coded_choice_paragraph(slot):
            return None
        text = self.ptext(slot.el)[0]
        matches = list(re.finditer(r"\d{1,3}\s*[☐☒]", text))
        if len(matches) != len(self.box_units(slot)):
            return None
        return {"label": text[:matches[0].start()].strip(),
                "starts": [0] + [m.start() for m in matches]}

    def literal_column_header(self, slot):
        """Literal option words separated by printed gaps: a tab, or two or more spaces, merged
        with all adjacent whitespace. A single space stays inside one option's words."""
        text = self.ptext(slot.el)[0]
        if any(c in text for c in (BOX, CHECKED, "\x00", "\n")) or self.blank_spans(*self.ptext(slot.el)):
            return None
        printed = text.rstrip(" \t")
        separators = [m for m in re.finditer(r"[ \t]+", printed) if "\t" in m.group() or len(m.group()) > 1]
        if not separators:
            return None
        starts = [0] + [m.end() for m in separators]
        ends = [m.start() for m in separators] + [len(printed)]
        parts = [printed[a:b].strip() for a, b in zip(starts, ends)]
        if len(parts) < 3 or not all(parts[1:]) or len(set(parts[1:])) != len(parts[1:]) \
                or any(len(p) > 300 for p in parts[1:]):
            return None
        # Leading spaces alone may be indentation or an empty label column; the group decides.
        indented = separators[0].start() == 0 and "\t" not in separators[0].group()
        return {"prefix": parts[0], "options": parts[1:], "starts": starts, "indented": indented}

    def readable_box_states(self, slot):
        """Every native control in the paragraph has one known state the renderer can be held to."""
        for piece in self.ptext(slot.el)[1]:
            if piece.kind != "obj":
                continue
            state = ff_checkbox_state(piece.node) if piece.obj == "ff_checkbox" else \
                sdt_checkbox_state(piece.node) if piece.obj == "sdt_checkbox" else None
            if type(state) is not bool:
                return False
        return True

    def coded_column_source(self, cell, rows, infos):
        """Resolve one cell's complete coded-column source, or return the reason it is unresolved.

        Titles (before the first header) are context. A header's lead - text printed directly above
        it and its own prefix - belongs to the first row below it only; text printed directly above
        a row belongs to that row. A summary title names only a cell's single unlabelled row.
        Positions, never codes, bind a box to its header option; only the PDF may confirm that."""
        children = [s for s in cell.children if s.kind == "p"]
        texts = {p.id: self.ptext(p.el)[0] for p in children}
        if cell.parent.parent is not None:
            return [], "The cell is inside a nested table."
        if any(s.kind != "p" and s.seq < rows[-1].seq for s in cell.children):
            return [], "Another object interrupts the printed source."
        for p in children:
            if not texts[p.id].strip():
                if not self.plain_spacing_paragraph(p, unused_tab_stops=True) \
                        or self.tab_column_properties(p, scope_only=True) is None:
                    return [], "A marked or unresolved spacer interrupts the source."
                continue
            if ("\x00" in texts[p.id] or "\n" in texts[p.id] or not self.tab_source_visible(p)
                    or self.tab_column_properties(p, scope_only=True) is None
                    or self.question_box_paragraph(p.el)[2]
                    or any(n.tag in (q("w:drawing"), q("w:pict"), q("w:object"), q("w:br"), q("w:cr"), q("w:sectPr"))
                           for n in p.el.iter())):
                return [], "A source paragraph has hidden, broken, embedded or unresolved content."
        context, issue = self.question_box_context(cell.parent, require_visible=True)
        headers, header_issue = self.marked_column_headers(cell)
        row_question, row_issue, group = self.printed_row_label(cell)
        if row_issue:
            return [], row_issue
        governing = " > ".join(x for x in (context, *headers, group, row_question) if x)
        context = " > ".join(x for x in (context, *headers, group, row_question,
                             " | ".join(texts[p.id].strip() for p in children if texts[p.id].strip())) if x)
        if issue or header_issue or len(context) > MAX_MAPPING_CONTEXT or self.question_box_signing(context):
            return [], "The full source context is oversized, protected or unresolved."
        if CHECK_ONE.search(context) and CHECK_ALL.search(context) or re.search(r"\bselect up to\b", context, re.I):
            return [], "The governing cardinality instructions conflict or carry an unrepresented limit."
        if CHECK_ALL.search(context):
            # One response code per row: a check-all instruction over it cannot be honoured or overruled.
            return [], "A check-all instruction governs coded rows that each record one response."
        titles, groups, current, waiting, previous = [], [], None, [], None
        for p in children:
            text = texts[p.id]
            if not text.strip():
                if waiting:
                    return [], "A spacer separates printed label text from the row it would name."
                previous = "blank"
                continue
            if p.id in infos:
                if current is None:
                    return [], "An answer row precedes its printed column header."
                current["rows"].append((p, waiting))
                waiting, previous = [], "row"
                continue
            header = self.literal_column_header(p)
            if header is not None:
                if current is not None and not current["rows"]:
                    return [], "A printed column header governs no answer row."
                current = {"para": p, "info": header, "lead": waiting, "rows": []}
                groups.append(current)
                waiting, previous = [], "header"
                continue
            if self.box_units(p) or self.blank_spans(*self.ptext(p.el)):
                return [], "Another answer area interrupts the printed source."
            asks = (text.strip().endswith((":", "?")) or self.question_box_request(text.strip())
                    or re.search(r"\b(?:specify|comments?|explain|describe)\b", text, re.I))
            if current is None:
                if asks:
                    return [], "A printed title requests its own answer."
                titles.append(p)
                previous = "title"
                continue
            if previous == "row":
                return [], "Printed text directly below an answer row may belong to it or to the next row."
            if asks or self.is_heading(p.el):
                return [], "Printed text between rows asks a question or starts a new section."
            waiting.append(p)
            previous = "text"
        if waiting or current is None or not current["rows"]:
            return [], "Printed text or a column header follows the last answer row."
        if not titles:
            return [], "The cell has no printed title of its own."
        for group in groups:
            counts = {len(infos[row.id]["starts"]) - 1 for row, _ in group["rows"]}
            info = group["info"]
            if len(counts) == 1 and info["indented"] and len(info["options"]) == min(counts) + 1:
                # Leading printed spaces are indentation here, not an empty label column: the only
                # reading with one printed option per box. The rendered witness still decides ownership.
                group["info"] = {"prefix": info["options"][0], "options": info["options"][1:],
                                 "starts": [0] + info["starts"][2:], "indented": False}
            if all(re.fullmatch(r"[\d\s.,)(-]+", option) for option in group["info"]["options"]):
                return [], "A printed column header names only numbers; a response code is never an option's meaning."
        pending, seen = [], set()
        paras = [p for p in children if texts[p.id].strip()]
        for group in groups:
            header, info = group["para"], group["info"]
            # Printed text above a row (and a header's lead and prefix, above its first row) may name that row
            # alone or every row after it until the next such text: when it is followed by several rows its
            # scope is not printed. A lone group label (one header, no lead) is left to the context for all.
            marks = [number for number, (_, before) in enumerate(group["rows"]) if before] + [len(group["rows"])]
            if any(following - mark > 1 for mark, following in zip(marks, marks[1:])):
                return [], "Printed text above a row is followed by several rows; which of them it names is not printed."
            # Rows before the first one with text of its own: the lead and prefix are printed over all of them.
            governed = marks[0] if marks[0] else 1
            if (group["lead"] or info["prefix"]) and governed > 1 and (group["lead"] or len(groups) > 1):
                return [], "A printed group label is followed by several rows; which of them it names is not printed."
            group_text = governed == 1
            for number, (row, before) in enumerate(group["rows"]):
                first = number == 0 and group_text
                sources = (group["lead"] if first else []) + before
                pieces = ([texts[p.id] for p in group["lead"]] + [info["prefix"]] if first else []) \
                    + [texts[p.id] for p in before] + [infos[row.id]["label"]]
                label = re.sub(r"[.·]{3,}$", "", " ".join(" ".join(pieces).split())).strip()
                start = sources[0] if sources and sources[0].seq < header.seq else header
                if not label:
                    if len(rows) != 1 or len(titles) != 1:
                        return [], "An answer row has no printed label of its own."
                    label = row_question or " ".join(texts[titles[0].id].split())
                    start = header if row_question else titles[0]
                if label.lower() in seen:
                    return [], "Two answer rows print the same label; their destinations are ambiguous."
                seen.add(label.lower())
                refs = [unit[0] for unit in self.box_units(row)]
                if len(refs) != len(info["options"]) or len(infos[row.id]["starts"]) != len(info["options"]) + 1:
                    return [], "A row's answer boxes do not match its printed column header."
                legend = " | ".join([governing, info["prefix"]] + [texts[p.id] for p in titles + group["lead"] + before])
                if self.legend_conflict(info["options"], row, legend):
                    return [], "The printed header prints numbers that are not the row's response codes."
                if (self.region_hidden(box_region(row.el)) or not self.readable_box_states(row)
                        or any(hyperlink_control(node) for node in checkbox_nodes(row.el))
                        or any(hyperlink_run(piece.run) for piece, _, _ in glyph_boxes(row.el))):
                    return [], "A source control is hidden, linked or not independently readable."
                if (len(label) > MAX_MAPPING_LABEL or self.question_box_signing(label)
                        or any(self.question_box_signing(o) for o in info["options"])):
                    return [], "A printed label is oversized or carries signing/consent instructions."
                chain = [p for p in paras if start.seq <= p.seq <= row.seq]
                roles = {g["para"].id: g["info"]["starts"] for g in groups}
                relation = {"header_index": chain.index(header),
                            "source": [{"part": p.part, "slot": p.path, "fingerprint": fingerprint(p.el),
                                        "starts": infos[p.id]["starts"] if p.id in infos else roles.get(p.id, [0])}
                                       for p in chain]}
                area = Area(self.coded_kind(label, info["options"], context), label, row,
                            {"type": "checkboxes", "boxes": refs, "column_sequence": relation},
                            context=context, options=list(info["options"]), complete_source=True)
                pending.append((header, row, area))
        return pending, ""

    def rule_coded_column_sequences(self):
        """Complete coded response columns in one table cell; only the PDF can establish ownership.

        A literal header (tabs or wide spaces) names the options. Each row's boxes are proposed
        under it by position, as an optional candidate that a rendered witness must confirm; no
        response code ever supplies an option's meaning. Every unresolved shape is a note."""
        already = {row.id for _, row, _ in self.layout_candidates}
        for cell in (s for s in self.index.slots if s.kind == "tc"):
            rows = [p for p in cell.children if p.kind == "p" and self.coded_choice_paragraph(p)]
            if not rows or any(p.id in already for p in rows):
                continue
            infos = {p.id: self.coded_column_parts(p) for p in rows}
            if any(info is None for info in infos.values()):
                continue  # rule_checkboxes notes every unresolved coded row
            # A cell the tab-pair contract accepted is already a candidate (above); one it refused is read here.
            pending, reason = self.coded_column_source(cell, rows, infos)
            if reason:
                self.notes.append("Coded column sequence at " + cell.id + ": " + reason + " Printed source: "
                                  + " | ".join(self.ptext(p.el)[0] for p in cell.children if p.kind == "p"))
                continue
            # This complete source supersedes the tab-stop refusal for the same cell.
            refused = "Tab-column options at " + cell.id + ": "
            self.notes[:] = [note for note in self.notes if not note.startswith(refused)]
            # Titles and spacing in a complete control-bearing source are never free-text answers.
            for paragraph in (s for s in cell.children if s.kind == "p"):
                self.claimed.add(id(paragraph.el))
            for header, row, area in pending:
                self.layout_candidates.append((header, row, area))
                if self.layout_proposal:
                    self.add(area)
                else:
                    self.notes.append("Layout verification required for coded-column answer at " + row.id +
                                      ". Printed question: " + area.label + ". Section: " + area.context)

    def rule_checkboxes(self, leftovers=False):
        # paragraph-level units, then grouping. A cell holding ONLY a box under a column header is left for the
        # option-grid rule; whatever that rule does not take comes back here (leftovers=True) - never dropped.
        para_units = []
        for s in self.index.slots:
            if s.kind != "p" or id(s.el) in self.claimed:
                continue
            txt = self.ptext(s.el)[0]
            if BOX not in txt and CHECKED not in txt:
                continue
            if self.coded_choice_paragraph(s) or self.response_code_row(s):
                self.notes.append("Coded checkbox options at " + s.id +
                                  " need their complete printed header and layout; response codes are not option labels. "
                                  "Printed source: " + txt)
                self.claimed.add(id(s.el))
                continue
            if (any(hyperlink_run(piece.run) for piece, _, _ in glyph_boxes(s.el))
                    or any(hyperlink_control(node) for node in checkbox_nodes(s.el))):
                self.notes.append("A checkbox inside a fixed hyperlink was kept unchanged. Location: " + s.id)
                self.claimed.add(id(s.el))
                continue
            if self.region_hidden(box_region(s.el)):
                # ⚠️ Its boxes cannot all be seen: no question is read from it (round 3 F1).
                self.notes.append("A line holds a checkbox QuillMD cannot read in place, so it was left for manual "
                                  "mapping: %s" % clean_label(txt)[:60])
                self.claimed.add(id(s.el))
                continue
            units = self.box_units(s)
            cell = self.host_cell(s)
            if not leftovers and cell is not None and self.owning_cell(s) is cell and \
                    not any(clean_label(u[1]) for u in units) and not clean_label(units[0][2]) and \
                    self.column_header(cell.parent, cell.info["col"], cell.info["row"]):
                continue
            if cell is not None and self.owning_cell(s) is cell and len(units) == 1 and self.pure_option_cell(cell, s, units[0]):
                opt = option_text(units[0][2]) if clean_label(units[0][2]) else option_text(units[0][1])
                units = [[units[0][0], opt, ""]]
                self._pure[id(s)] = cell
            para_units.append((s, units))
        groups = []
        current = None
        for pslot, units in para_units:
            before = clean_label(units[0][2]) if units else ""
            own_question = bool(before)
            cell = self.host_cell(pslot)
            joined = False
            if current is not None and id(pslot) in self._pure and id(current["paras"][-1]) in self._pure:
                lc = self._pure[id(current["paras"][-1])]
                if lc.parent is cell.parent and lc.info["row"] == cell.info["row"] and \
                        cell.info["col"] == lc.info["col"] + lc.info["span"]:
                    current["paras"].append(pslot)
                    current["units"].extend(units)
                    continue
            if current is not None and not own_question:
                last_p = current["paras"][-1]
                if last_p.parent is pslot.parent:
                    sibs, ia = self.para_neighbours(last_p)
                    ib = next((i for i, x in enumerate(sibs) if x is pslot), None)
                    if ia is not None and ib is not None and 0 < ib - ia <= 2 and \
                            not any(self.text(x.el).strip() for x in sibs[ia + 1:ib]):
                        joined = True
                elif cell is not None and self.owning_cell(last_p) is not None and self.owning_cell(last_p).parent is cell.parent \
                        and not current["question_from_cell"]:
                    lc = self.owning_cell(last_p)
                    first_l = next(iter(self.own_paragraphs(lc)), None)
                    first_c = next(iter(self.own_paragraphs(cell)), None)
                    same_row = lc.info["row"] == cell.info["row"] or abs(lc.info["row"] - cell.info["row"]) == 1
                    if first_l is last_p and first_c is pslot and same_row and \
                            not self.row_label(cell.parent, cell.info["row"], cell.info["col"]):
                        joined = True
            if joined:
                current["paras"].append(pslot)
                current["units"].extend(units)
                continue
            current = {"paras": [pslot], "units": list(units), "question_from_cell": False}
            groups.append(current)
        for g in groups:
            self.emit_checkbox_group(g)

    def pure_option_cell(self, cell, pslot, unit) -> bool:
        """A cell that holds one box and a short option word ('Yes ☐' / '☐ No') and nothing else."""
        if len([c for c in self.own_paragraphs(cell) if self.text(c.el).strip()]) != 1:
            return False
        before, after = clean_label(unit[2]), clean_label(unit[1])
        opt = before or after
        if before and after:
            return False
        return bool(opt) and (is_option_word(opt) or len(opt.split()) <= 3)

    def split_inline_groups(self, g):
        """A single paragraph may hold several questions: 'Q1? ☐Yes ☐No   Q2? ☐Yes ☐No'. Split where an option's
        text ends with a question/label ('?' or ':') after a wide gap; that label heads the next group."""
        units = [list(u) for u in g["units"]]
        out, cur = [], []
        for i, (ref, option, before) in enumerate(units):
            if cur and clean_label(before):
                out.append(cur)
                cur = []
            m = re.search(r"^(.*?)(?:\t+| {3,})(\S[^\t]*[?:])\s*$", option)
            if m and i + 1 < len(units) and len(m.group(2).split()) <= MAX_LABEL_WORDS:
                cur.append([ref, m.group(1), before])
                out.append(cur)
                cur = []
                units[i + 1][2] = m.group(2)
                continue
            cur.append([ref, option, before])
        if cur:
            out.append(cur)
        return out

    def nested_checkbox_source(self, group):
        """One complete nested option grid belongs to its printed source question.

        Only a full-width outer cell of a body table participates. Subsection
        labels can inherit one explicit parent question, never a neighbouring
        row's question or a guessed subordinate-control relationship.
        """
        cell = self.host_cell(group["paras"][0])
        if cell is None:
            return None
        table, outer = cell.parent, cell.parent.parent
        if outer is None or outer.kind != "tc" or outer.parent.parent is not None:
            return None
        if outer.part != "word/document.xml" or len(self.grid(outer.parent).get(outer.info["row"], [])) != 1:
            return None
        before = [slot for slot in outer.children if slot.seq < table.seq]
        paragraphs = [slot for slot in before if slot.kind == "p" and self.text(slot.el).strip()]
        if not paragraphs:
            return None
        sources = [self.text(slot.el).strip() for slot in paragraphs]
        source = " ".join(sources)
        problem = ""
        explicit = [slot for slot in paragraphs if "?" in self.text(slot.el)
                    or CHECK_ALL.search(self.text(slot.el)) or CHECK_ONE.search(self.text(slot.el))]
        if len(explicit) != 1:
            problem = "There is not one complete printed parent question."
        question = explicit[0] if len(explicit) == 1 else paragraphs[-1]
        label_slot = paragraphs[-1]
        subsection = label_slot is not question
        if not problem and not subsection and paragraphs != [question]:
            problem = "Additional source text has no proven relationship to this question."
        if not problem and subsection and (paragraphs[0] is not question or any(
                slot is not question and (not self.text(slot.el).strip().endswith(":")
                or len(self.text(slot.el).strip()) > 100 or self.blank_spans(*self.ptext(slot.el)))
                for slot in paragraphs)):
            problem = "The intervening text does not establish one subsection."
        if not problem and subsection:
            sequence = [slot.kind for slot in before if slot.kind != "p" or self.text(slot.el).strip()][1:]
            if sequence and sequence[0] == "tbl":
                sequence = sequence[1:]  # The first grid can belong to the parent question itself.
            if not sequence or sequence != ["p", "tbl"] * (len(sequence) // 2) + ["p"]:
                problem = "An intervening source label has no separate answer grid; its scope cannot be dropped."
        if not problem and any(slot.kind == "p" and not self.text(slot.el).strip()
                               and not self.plain_spacing_paragraph(slot) for slot in before):
            problem = "A marked or unresolved answer paragraph separates this source."
        for slot in (item for item in before if item.kind == "p"):
            _, _, issue = self.question_box_paragraph(slot.el)
            if issue or self.blank_spans(*self.ptext(slot.el)) or any(
                    ch in self.ptext(slot.el)[0] for ch in (BOX, CHECKED, "\x00")):
                problem = "The complete source or its layout boundary is unresolved."
        grid_source = [slot for slot in self.index.slots if slot.kind == "p"
                       and (owner := self.host_cell(slot)) is not None and owner.parent is table]
        grid_paras = [slot for slot in grid_source if self.box_units(slot)]
        if any((self.ptext(slot.el)[0].strip() or not self.plain_spacing_paragraph(slot))
               for slot in grid_source if slot not in grid_paras) or any(
                slot.kind == "tbl" and slot.parent is not None and slot.parent.parent is table
                for slot in self.index.slots):
            problem = "The grid contains separate printed headers, context or answer areas whose ownership is unresolved."
        if {slot.id for slot in grid_paras} != {slot.id for slot in group["paras"]}:
            problem = "The grid contains separate option groups whose ownership is unresolved."
        if any(len(self.box_units(slot)) != 1 for slot in grid_paras):
            problem = "Parent and subordinate boxes share a paragraph; they cannot be flattened into one choice."
        context, issue = self.question_box_context(outer.parent)
        if issue:
            problem = issue
        raw_question, label = self.text(question.el).strip(), self.text(label_slot.el).strip()
        context = " > ".join(x for x in (context, raw_question if subsection else "") if x)
        write_context = " > ".join(x for x in (context, label) if x)
        if len(group["units"]) == 1:
            # A checkbox keeps its printed option as label; its question still
            # governs that option, including a local subject or subsection.
            context = " > ".join(x for x in (context, label) if x)
        if len(label) > MAX_MAPPING_LABEL or len(context) > MAX_MAPPING_CONTEXT:
            problem = "The complete question or context exceeds limits."
        if any(self.question_box_signing(value) for value in sources + [context]):
            problem = "The complete source contains signing/consent instructions. Governing context: " + context
        if problem:
            return {"problem": "Nested option grid at " + table.id + ": " + problem
                    + " Printed source: " + source + " Options: " + self.text(table.el, own=False)}
        return {"label": label, "context": context, "cardinality": raw_question,
                "write_context": write_context,
                "source_slots": paragraphs + [slot for slot in before if slot.kind == "p"
                    and not self.text(slot.el).strip()], "option_paras": grid_paras}

    def nested_write_in(self, slot, context):
        """A separate explicit trailing blank never supplies a checkbox decision."""
        text, pieces = self.ptext(slot.el)
        spans = self.blank_spans(text, pieces)
        if not spans:
            return
        problem = "Its source does not prove one separate trailing blank."
        if len(spans) == 1:
            start, end, shape = spans[0]
            boxes = [i for i, char in enumerate(text) if char in (BOX, CHECKED)]
            if (len(boxes) == 1 and not text[:boxes[0]].strip() and boxes[0] < start
                    and not text[end:].strip() and "\x00" not in text
                    and not any(node.tag in (q("w:drawing"), q("w:pict"), q("w:object"))
                                for node in slot.el.iter())
                    and (shape == "utab" or (shape == "blank" and set(text[start:end]) == {"_"}))):
                label = text[boxes[0] + 1:start].strip()
                if label and len(label) <= MAX_MAPPING_LABEL and len(context) <= MAX_MAPPING_CONTEXT:
                    if not any(self.question_box_signing(value) for value in (label, context)):
                        self.add(Area("text", label, slot,
                            {"type": "span", "start": start, "end": end, "shape": shape},
                            context=context, complete_source=True))
                        return
                    problem = "The complete source contains signing/consent instructions."
                elif len(label) > MAX_MAPPING_LABEL or len(context) > MAX_MAPPING_CONTEXT:
                    problem = "The complete label or context exceeds limits; nothing was shortened."
        self.notes.append("Unassigned write-in beside a nested option at " + slot.id + ". " + problem
                          + " Printed text: " + text + " Governing context: " + context)

    def selection_guidance(self):
        """Every limited selection sentence printed in the form (body, table cells, text boxes, positioned frames,
        page headers/footers, footnotes, endnotes), and every selection command in floating text, as (paragraph
        id, owner, sentence, where). The owner is the block of a separate question whose label the sentence is:
        only a paragraph's first sentence, only a label carrying a complete one-only command (label_instruction),
        and only when that question's boxes follow the label directly (label_owner). Nothing else is owned."""
        if self._form_wide is None:
            found = []
            parts = self.package.content_parts() + [n for n in ("word/footnotes.xml", "word/endnotes.xml")
                                                    if n in self.package.names]
            for part in parts:
                root = self.package.tree(part)
                for p in root.iter(q("w:p")):
                    unit = next((a for a in p.iterancestors() if a.tag in (q("w:tc"), TXBX)), p)
                    framed = p.find("./" + q("w:pPr") + "/" + q("w:framePr")) is not None
                    floating = framed or unit.tag == TXBX
                    printed = [x for x in re.split(r"(?<=[.!?;])\s+", text_of(p, own=True).strip()) if x]
                    flags = [limited_selection(x) or floating and floating_selection(x) for x in printed]
                    if not any(flags):
                        continue
                    owner = None if framed else self.label_owner(p, printed[0])
                    where = ("a text box in " if unit.tag == TXBX else "a positioned frame in " if framed else "") + part
                    for i, sentence in enumerate(printed):
                        if flags[i]:
                            found.append((id(p), owner if i == 0 else None, sentence, where))
            self._form_wide = found
        return self._form_wide

    def label_owner(self, p, sentence):
        """The block whose boxes the label `sentence` (the first sentence of paragraph `p`) introduces, or None:
        `p` itself when its boxes follow the label directly ("Sex (tick one): [ ] Male [ ] Female"), or, when
        nothing follows the label in `p`, the next printed block when it starts with a box (the label above its own
        option lines, in a boxed cell, or beside the answer cell of its table row). Boxes printed after other text
        answer a separately labelled question ("Leave type (tick one):" above "Escorted: [ ] Yes [ ] No")."""
        cell = p.getparent()
        contained = cell is not None and cell.tag == q("w:tc") and bool(checkbox_nodes(cell, own=False))
        label = label_instruction(sentence, contained)
        # The label starts the paragraph as printed: after a box it is an answer's text, not a question's label.
        start = re.match(r"\s*" + re.escape(label) + r"[.\s]*[:?]?", paragraph_text(p)[0]) if label else None
        if start is None:
            return None
        after = paragraph_text(p)[0][start.end():]
        if after.strip():
            return p if after.lstrip()[0] in (BOX, CHECKED) else None
        block = self.next_printed(p)
        return block if block is not None and self.starts_with_box(block) else None

    @staticmethod
    def next_printed(p):
        """The next paragraph, table or block control printed after `p` in its container (text or a box); after the
        last one in a table cell, the next cell of its row."""
        node = p.getnext()
        while node is not None:
            if node.tag in (q("w:p"), q("w:tbl"), q("w:sdt")) and any(
                    paragraph_text(para)[0].strip() for para in node.iter(q("w:p"))):
                return node
            node = node.getnext()
        cell = p.getparent()
        if cell is not None and cell.tag == q("w:tc"):
            nxt = cell.getnext()
            while nxt is not None and nxt.tag != q("w:tc"):
                nxt = nxt.getnext()
            return nxt
        return None

    @staticmethod
    def starts_with_box(el):
        """The first printed content of `el` is a box (a native control or a box glyph)."""
        for para in el.iter(q("w:p")):
            text = paragraph_text(para)[0]
            if text.strip():
                return text.lstrip()[0] in (BOX, CHECKED)
        return False

    @staticmethod
    def owns_boxes(el):
        """Native boxes, or a printed glyph question: a label ending in ':', '?' or ')' and then at least two box
        glyphs, each followed by its answer ("Sex (tick one): [ ] Male [ ] Female"). Sample glyphs inside an
        instruction ("Mark [x] one box only, leave the others [ ]") are not a question."""
        if checkbox_nodes(el, own=False):
            return True
        parts = re.split("[" + BOX + CHECKED + "]", text_of(el))
        return len(parts) >= 3 and bool(re.search(r"\S\s*[:?)]\s*$", parts[0])) and all(x.strip() for x in parts[1:])

    def limited_selection_elsewhere(self, sources):
        """Limited selection guidance outside this list's own source that no separate question owns: (where,
        sentence), or None. Its reach cannot be read, so it may govern this list. (A body label directly above the
        list's own lines is part of its source and read there, never here.)"""
        own = {id(s.el) for s in sources}
        for pid, owner, sentence, where in self.selection_guidance():
            if pid in own or owner is not None:
                continue
            return where, sentence
        return None

    def native_history_source(self, group, units, options, used_para):
        """A bounded completed-event list has independent native checkboxes.

        This does not change the default for dropdowns, printed option lists,
        table grids or arbitrary checkbox questions. Explicit/known exclusive
        alternatives and single-event wording retain one-choice behavior.
        Selection wording counts only as one complete positive command; any
        other selection wording in the owner, its context, its options or the
        text printed immediately beside the list leaves it unresolved.
        """
        raw = units[0][2] or (self.text(used_para.el) if used_para is not None else "")
        question = clean_label(raw, limit=None)
        if not re.search(r"\b(?:taken|received|completed|attended|undergone)\s*$", question, re.I):
            return None
        # A question ("Has a test been completed", "Were any courses attended")
        # or a conditional owner ("If yes, ...") is not a declarative event
        # list: the prior one-choice default stands for it.
        if re.match(r"(?:has|have|had|was|were|is|are|did|does|do|will|would|can|could|should|shall|may|might|must|"
                    r"which|what|who|whom|whose|when|where|how|why|if|whether|unless)\b", question, re.I):
            return None
        if (len(units) < 2 or len(units) != len(group["units"])
                or any(u[0]["kind"] not in ("ff", "sdt") for u in units)
                or any(p.parent is not None or p.part != "word/document.xml" for p in group["paras"])):
            return None
        owner = used_para or group["paras"][0]
        if owner.parent is not None or owner.part != "word/document.xml":
            return None
        # Answers that exclude each other (Yes/No, "None of the above", "No
        # treatment", "Yes - other", a count or a range) and a question that
        # asks for one level, count or total ("Highest level of education
        # completed", "Number of sessions attended", "Doses received: One /
        # Two / Three") have exactly one answer whatever is printed around
        # them: one choice, as before this rule, never held and never several.
        exclusive = any(YESNO.fullmatch(o) or OPTION_WORD.fullmatch(o)
                        or re.match(r"(?:yes|no|none|nil|not|n/?a|unknown)\b", o, re.I) for o in options)
        if exclusive or (options and all(QUANTITY_OPTION.match(o) for o in options)) or SINGLE_QUANTITY.search(question):
            return {"kind": "choice"}
        problem = "The complete native-checkbox history source is unresolved."
        unresolved = "The native-checkbox history selection instruction is unresolved."
        if (len(question) > MAX_MAPPING_LABEL or any(not o for o in options)
                or len(set(o.casefold() for o in options)) != len(options)
                or options != [option_text(u[1]) for u in units]
                or any(OPTION_SELECTION.search(o) for o in options)):
            return {"problem": problem}
        if HISTORY_REFERENCE.search(raw) or any(HISTORY_REFERENCE.search(u[1] or "") for u in units):
            return {"problem": problem + " A printed reference mark points to guidance outside it."}
        roots = [s for s in self.index.roots if s.part == owner.part]
        first, last = roots.index(owner), roots.index(group["paras"][-1])
        sources = roots[first:last + 1]
        if any(s.kind != "p" for s in sources):
            return {"problem": problem}
        instructions, stopper = [], None
        for prior in reversed(roots[:first]):
            if prior.kind != "p":
                stopper = prior
                break
            heading, _, issue = self.question_box_paragraph(prior.el)
            if heading:
                break
            text = self.text(prior.el).strip()
            if issue:
                return {"problem": problem}
            if self.box_units(prior) or self.blank_spans(*self.ptext(prior.el)):
                # A paragraph with its own boxes or blank is a separate
                # question, as it is below the list: it ends the scan and is
                # judged as the neighbour above.
                stopper = prior
                break
            if text:
                if self.question_box_request(text) or self.list_info(prior.el):
                    return {"problem": problem}
                instructions.insert(0, text)
            elif not self.plain_spacing_paragraph(prior):
                return {"problem": problem}
            sources.insert(0, prior)
        if any(not self.tab_source_visible(s) or any(n.tag in (q("w:sectPr"), q("w:drawing"), q("w:pict"),
                    q("w:object"), q("w:br"), q("w:footnoteReference"), q("w:endnoteReference"), q("w:framePr"))
                    for n in s.el.iter()) for s in sources):
            return {"problem": problem}

        def beside(slot):
            """(owns its boxes, prints text, speaks about selection) for a neighbour outside the source."""
            texts = [text_of(p, own=False) for p in ([slot.el] if slot.kind == "p" else slot.el.iter(q("w:p")))]
            return (self.owns_boxes(slot.el), any(t.strip() for t in texts),
                    any(history_selection(t) for t in texts))
        # The block that ends the instruction scan above the list (a boxed
        # instruction) and the first printed block below it are never part of
        # this relation. Selection wording there is ownership nobody resolved,
        # unless that neighbour holds its own native boxes: then it is a
        # separate question that owns its instruction (D31's page-1 "please
        # tick one"). A printed box glyph is not enough: an instruction can show
        # a sample box ("Mark [x] one box only").
        outside = "A selection instruction is printed beside the native-checkbox history, outside its source; " \
                  "which answers it governs is unresolved."
        if stopper is not None:
            own_boxes, _, speaks = beside(stopper)
            if speaks and not own_boxes:
                return {"problem": outside}
        for later in roots[last + 1:]:
            own_boxes, printed, speaks = beside(later)
            if own_boxes:
                break
            if not printed and later.kind == "p":
                continue
            if speaks:
                return {"problem": outside}
            break

        def points(slot, direction):
            """A selection sentence in `slot` that points at a list further away ("the list below")."""
            if checkbox_nodes(slot.el, own=False):
                return False
            texts = [text_of(p, own=False) for p in ([slot.el] if slot.kind == "p" else slot.el.iter(q("w:p")))]
            return any(history_selection(x) and re.search(direction, x, re.I)
                       for t in texts for x in re.split(r"(?<=[.!?;])\s+", t))
        # Further away inside the same heading scope, a selection sentence that
        # points at a list may govern this one; its reach is unresolved.
        for prior in reversed(roots[:roots.index(sources[0])]):
            if prior.kind == "p" and self.question_box_paragraph(prior.el)[0]:
                break
            if points(prior, r"\b(?:below|following|beneath|underneath|next)\b"):
                return {"problem": outside}
        for later in roots[last + 1:]:
            if points(later, r"\b(?:above|preceding|previous)\b"):
                return {"problem": outside}
            if later.kind == "p" and self.question_box_paragraph(later.el)[0]:
                break
        heading_context, issue = self.question_box_context(owner, require_visible=True)
        context = " > ".join(x for x in (heading_context, *instructions) if x)
        scope = context + " > " + question
        if (issue or len(context) > MAX_MAPPING_CONTEXT or self.question_box_signing(scope)
                or any(self.question_box_signing(o) for o in options)
                or re.search(r"\b(?:above|previous|following)\s+(?:question|answer|section)\b|\bas above\b|\bsame as\b", scope, re.I)):
            return {"problem": problem}
        # Only complete positive selection instructions establish cardinality.
        # Every sentence of the governing headings and instructions that uses
        # selection wording must be one; anything else (a negated, limited or
        # partial command) is unknown, never permission to allow several.
        one, many = False, False
        headings = [re.sub(r"^(?:part|section|step|stage|annex|appendix)\s+one\b[\s.:)\-–—]*", "", h, flags=re.I)
                    for h in heading_context.split(" > ")]
        for text in (*headings, *instructions):
            for sentence in re.split(r"(?<=[.!?;])\s+", text.strip()):
                if not history_selection(sentence) and not limited_selection(sentence):
                    continue
                command = re.sub(r"[.!:;]+$", "", sentence.strip()).strip()
                wrapped = re.fullmatch(r"\((.*)\)", command)
                if wrapped:
                    command = re.sub(r"[.!:;]+$", "", wrapped.group(1).strip()).strip()
                if HISTORY_ONE.fullmatch(command):
                    one = True
                elif HISTORY_MANY.fullmatch(command):
                    many = True
                else:
                    return {"problem": unresolved}
        if history_selection(question):
            # Only "(only|just|exactly) one <event> received": never "one or
            # more", "one or two", "one to three" or a second quantity.
            owner_one = re.fullmatch(r"(?:(?:only|just|exactly)\s+)?(?:one|1)\s+(.+)", question, re.I)
            rest = owner_one.group(1) if owner_one else ""
            if (not owner_one or history_selection(rest)
                    or re.search(r"\b(?:or|and|nor|plus|more|fewer|less|to|two|three|four|five|six|seven|eight|nine|ten|"
                                 r"both|many|all|any|each|every)\b|\d|[/&+,;()]", rest, re.I)):
                return {"problem": unresolved}
            one = True
        if (one and many or re.search(r"\b(?:up to|at most|at least|no more than|between|maximum|minimum)\b", scope, re.I)
                or re.search(r"\bexactly\b", scope, re.I) and not one):
            return {"problem": "The native-checkbox history has conflicting or unrepresented selection limits."}
        single = bool(re.search(r"\b(?:single|current|currently|latest|last|most recent|primary|main|sole)\b", scope, re.I))
        kind = "choice" if one or single else "multi_choice"
        # Independence is never inferred past a limited selection instruction
        # printed anywhere else in the form (a parent heading, the section, the
        # preamble, a page header, a text box, below the list) that no separate
        # question owns: its reach cannot be read, so the list keeps one choice.
        elsewhere = self.limited_selection_elsewhere(sources) if kind == "multi_choice" else None
        if elsewhere:
            return {"kind": "choice", "note": "The native-checkbox history keeps one choice: a limited selection "
                    "instruction is printed elsewhere in the form (" + elsewhere[0] + ": " + elsewhere[1][:120]
                    + ") and which answers it governs is unresolved."}
        relation = {"relation": "native_checkbox_history", "question": question, "context": context,
                    "options": options, "cardinality": kind,
                    "sources": [{"part": s.part, "slot": s.path, "fingerprint": fingerprint(s.el)} for s in sources]}
        return {"kind": kind, "question": question, "context": context, "relation": relation}

    @staticmethod
    def option_families(text):
        """The OPTION_FAMILIES a printed option belongs to; -1 for a companion word ('N/A', 'Unknown')."""
        word = re.sub(r"^[\s(\[]+|[\s)\].:;,]+$", "", " ".join(option_text(text).lower().split()))
        found = {n for n, family in enumerate(OPTION_FAMILIES) if family.fullmatch(word)}
        return found | ({-1} if COMPANION_OPTION.fullmatch(word) else set())

    def words_before_boxes(self, units, options):
        """Why a row of boxes may print each box's word BEFORE it ('Smoker: Yes ☐ No ☐ (tick one)'), or "".

        Read after-box, each box would take the next box's word. The after-box reading is kept only when the row
        cannot be read the other way: nothing but the question before the first box, no word printed against the
        next box, and something other than a bare instruction after the last one (refutation F3, R3-1)."""
        between, last = options[:-1], options[-1]
        if clean_label(units[0][2]) and all(between) and not last:
            return "and nothing after the last one"
        instruction = re.sub(r"[()\[\].,:;!]", " ", last)
        for rx in (CHECK_ONE, CHECK_ALL, EXPLICIT_ONE):
            instruction = rx.sub(" ", instruction)
        instruction = re.sub(r"\b(?:please|only|boxe?s?|answers?|options?|responses?|here)\b", " ", instruction, flags=re.I)
        if any(rx.search(last) for rx in (CHECK_ONE, CHECK_ALL, EXPLICIT_ONE)) and not re.search(r"[^\W_]", instruction):
            return "and only a selection instruction after the last one"
        head = units[0][2].rstrip()
        cut = [m.end() for m in re.finditer(r"[:?]|\t| {2,}", head)]
        # A bracketed selection instruction or a bracket drawn around the box ('Sex: (choose one) [☐] M') is not an
        # option word; a bracketed word ('Smoker: (Yes) ☐ (No) ☐ N/A') still is.
        tail = re.sub(r"\(([^()]*)\)", lambda m: " " if any(rx.search(m.group(1)) for rx in (CHECK_ONE, CHECK_ALL, EXPLICIT_ONE))
                      or re.search(r"\b(?:choose|select|tick|check|circle|mark|pick)\b", m.group(1), re.I) else m.group(0),
                      head[cut[-1]:] if cut else head)
        tail = re.sub(r"[\[\]]", " ", tail)
        if (not re.search(r"[^\W\d_]", tail) or re.search(r"_|\.{2,}|…|[\u25af\x00" + BOX + CHECKED + "]", tail)
                or re.match(r"\s*(?:if|when|where|how|what|which|since)\b", tail, re.I)):
            return ""  # the question (or its own answer blank) ends right before the first box
        words = option_text(tail).split()
        suffixes = [" ".join(words[-k:]) for k in (1, 2, 3) if k <= len(words)]
        tail_families = set().union(*(self.option_families(x) for x in suffixes))
        between_families = [self.option_families(o) for o in between if o]
        if (tail_families - {-1}) & set().union(*between_families) or (-1 in tail_families and any(between_families)):
            return "(the word before the first box is one of the same printed options)"
        for raw in (u[1] for u in units[:-1]):
            if raw.strip() and gap_width(raw[:len(raw) - len(raw.lstrip())]) > gap_width(raw[len(raw.rstrip()):]):
                return "(a word is printed against the box after it)"
        # After the question's colon, a word right before the first box is the question's own only when every word
        # between the boxes is an option of one printed family that it is not ('PMH: Diabetes ☐ Yes ☐ No').
        shared = set.intersection(*between_families) if between_families and all(between_families) else set()
        if cut and not shared - tail_families:
            return "(a word printed after the question's colon may be the first box's option)"
        return ""

    def emit_checkbox_group(self, g):
        pslot = g["paras"][0]
        for units in self.split_inline_groups(g):
            options = [option_text(re.split(r"\t{2,}| {4,}", o)[0]) if re.search(r"\S", re.split(r"\t{2,}| {4,}", o)[0]) else option_text(o)
                       for _, o, _ in units]
            question = clean_label(units[0][2])
            before_boxes = self.words_before_boxes(units, options) if len(units) > 1 else ""
            if before_boxes:
                # ⚠️ WORDS PRINTED BEFORE THEIR BOXES ('Smoker: Yes ☐ No ☐', 'Allergies: Yes ☐ No ☐ NKDA'): read as the
                # text after each box, every box took the next box's word, and 'No' ticked the Yes box (refutation F3,
                # and R3-1 whatever is printed after the last box).
                self.notes.append("Boxes at %s have their words printed before each box %s, so which printed word "
                                  "names which box was left for manual mapping. Printed source: %s"
                                  % (pslot.id, before_boxes, " | ".join(self.ptext(p.el)[0] for p in g["paras"])))
                for p in g["paras"]:
                    self.claimed.add(id(p.el))
                continue
            host = pslot
            used_para = None
            row_question = False
            nested = self.nested_checkbox_source(g) if not question else None
            if nested and nested.get("problem"):
                self.notes.append(nested["problem"])
                for paragraph in g["paras"]:
                    self.claimed.add(id(paragraph.el))
                continue
            if nested:
                question = nested["label"]
            if not question:
                cell = self.host_cell(pslot)
                if cell is not None and next(iter(self.own_paragraphs(cell)), None) is pslot:
                    question = self.row_label(cell.parent, cell.info["row"], cell.info["col"])
                    row_question = bool(question)
                    question = question or clean_label(self.column_header(cell.parent, cell.info["col"], cell.info["row"]))
                    cells = list(dict.fromkeys(c for c in (self.owning_cell(p) for p in g["paras"]) if c is not None))
                    header = clean_label(self.column_header(cell.parent, cell.info["col"], cell.info["row"]))
                    choices = {o.lower().rstrip(".") for o in options}
                    independent_question = len(cells) == 1 and header and not is_option_word(header) and \
                        (choices >= {"yes", "no"} or choices >= {"y", "n"})
                    if row_question and not independent_question and (len(units) > 1 or not options[0]) and cells and self.unattributed_row_boxes(cells):
                        # ⚠️ THE ROW PRINTS ANOTHER BOX THESE WERE NOT GIVEN: they are some of the row's options, never
                        # its question - a lone No box labelled with the row's question was ticked by 'Chest pain: yes'
                        # (round 3 P2). Refused, with a note, rather than guessed.
                        self.notes.append("Boxes in the '%s' row were left for manual mapping: the row prints another box "
                                          "beside them, so which of the row's options they are is not known." % question[:60])
                        for p in g["paras"]:
                            self.claimed.add(id(p.el))
                        continue
                if not question:
                    prev = self.previous_paragraph(pslot)
                    if prev is not None and BOX not in self.ptext(prev.el)[0]:
                        question = clean_label(self.text(prev.el))
                        used_para = prev
                if not question and cell is not None:
                    # an option grid inside a nested table: the question precedes the table
                    tbl = cell.parent
                    outer = tbl.parent
                    if outer is not None:
                        sib_p = [s for s in outer.children if s.kind == "p" and s.seq < tbl.seq]
                        if sib_p:
                            question = clean_label(self.text(sib_p[-1].el))
            boxes = [u[0] for u in units]
            anchor = self.index.by_id.get("%s#%s" % (boxes[0]["part"], boxes[0]["slot"])) or host
            target = {"type": "checkboxes", "boxes": boxes}
            extra = []
            for b in boxes[1:]:
                s = self.index.by_id.get("%s#%s" % (b["part"], b["slot"]))
                if s is not None and s is not anchor and s not in extra:
                    extra.append(s)
            hint = ([question] + ([nested["cardinality"]] if nested else [])
                    + [self.text(p.el) for p in g["paras"][:1]])
            printed = " ".join([question or ""] + ([nested["cardinality"]] if nested else []))
            if len(units) > 1 and one_only(printed, printed) and CHECK_ALL.search(printed):
                # "Tick all that apply and indicate one as the main symptom": one
                # answer and several at once. Neither is guessed: never narrowed
                # to one choice, never widened past the one-only wording.
                self.notes.append("Checkbox question at " + pslot.id + ": the printed cardinality instructions conflict "
                                  "(one only and several); nothing was guessed. Printed question: " + (question or "")[:200])
                for p in g["paras"]:
                    self.claimed.add(id(p.el))
                if used_para is not None:
                    self.claimed.add(id(used_para.el))
                for source_slot in (nested["source_slots"] if nested else []):
                    self.claimed.add(id(source_slot.el))
                continue
            if len(units) == 1:
                label = options[0] or question or "Checkbox"
                area = Area("checkbox", label, anchor, target, context=self.context_for(anchor), options=[options[0]] if options[0] else [])
                if question and options[0]:
                    area.context = (area.context + " > " + question).strip(" >")[:300]
            else:
                area = Area(self.choice_kind(question, options, hint), question or "Choose", anchor, target,
                            context=self.context_for(anchor), options=[o or "(option %d)" % (i + 1) for i, o in enumerate(options)],
                            extra_slots=extra)
                history = self.native_history_source(g, units, options, used_para)
                if history:
                    if history.get("problem"):
                        self.notes.append(history["problem"] + " Location: " + pslot.id)
                        for paragraph in g["paras"]:
                            self.claimed.add(id(paragraph.el))
                        continue
                    if "relation" in history:
                        area.kind, area.label, area.context = history["kind"], history["question"], history["context"]
                        area.complete_source, area.source_questions = True, [history["relation"]]
                    else:
                        area.kind = history["kind"]
                        if history.get("note"):
                            self.notes.append(history["note"] + " Location: " + pslot.id)
            if nested:
                area.context, area.complete_source = nested["context"], True
                for source_slot in nested["source_slots"]:
                    self.claimed.add(id(source_slot.el))
                for option_para in nested["option_paras"]:
                    self.nested_write_in(option_para, nested["write_context"])
            self.add(area)
            for p in g["paras"]:
                self.claimed.add(id(p.el))
            if used_para is not None:
                self.claimed.add(id(used_para.el))

    # 4. options printed as text: lettered list items under a question, or 'YES<tab>NO' circle-one lines ------------
    def numbering(self):
        if self._numbering is None:
            fmt = {}
            if "word/numbering.xml" in self.package.names:
                root = self.package.tree("word/numbering.xml")
                abstract = {}
                for an in root.findall(q("w:abstractNum")):
                    levels = {}
                    for lvl in an.findall(q("w:lvl")):
                        nf = lvl.find(q("w:numFmt"))
                        levels[lvl.get(q("w:ilvl"))] = nf.get(q("w:val")) if nf is not None else "decimal"
                    abstract[an.get(q("w:abstractNumId"))] = levels
                for num in root.findall(q("w:num")):
                    a = num.find(q("w:abstractNumId"))
                    if a is not None:
                        fmt[num.get(q("w:numId"))] = abstract.get(a.get(q("w:val")), {})
            self._numbering = fmt
        return self._numbering

    def list_info(self, p):
        ppr = p.find(q("w:pPr"))
        num = ppr.find(q("w:numPr")) if ppr is not None else None
        if num is None:
            return None
        nid = num.find(q("w:numId"))
        ilvl = num.find(q("w:ilvl"))
        nid = nid.get(q("w:val")) if nid is not None else None
        lvl = ilvl.get(q("w:val")) if ilvl is not None else "0"
        if nid in (None, "0"):
            return None
        return (nid, lvl, self.numbering().get(nid, {}).get(lvl, "decimal"))

    def list_marker_is_plain(self, info):
        """Resolve the printed level marker before treating a list as descriptors.

        Checkbox glyphs can live in numbering.xml rather than paragraph text.
        An override replaces the level; ambiguous or linked definitions cannot
        establish this rule's plain-list ownership.
        """
        if "word/numbering.xml" not in self.package.names:
            return False
        root = self.package.tree("word/numbering.xml")
        nums = [n for n in root.findall(q("w:num")) if n.get(q("w:numId")) == info[0]]
        if len(nums) != 1 or len(nums[0].findall(q("w:abstractNumId"))) != 1:
            return False
        aid = nums[0].find(q("w:abstractNumId")).get(q("w:val"))
        abstracts = [a for a in root.findall(q("w:abstractNum")) if a.get(q("w:abstractNumId")) == aid]
        if len(abstracts) != 1 or any(abstracts[0].find(q("w:" + name)) is not None
                                      for name in ("numStyleLink", "styleLink")):
            return False
        levels = [level for level in abstracts[0].findall(q("w:lvl")) if level.get(q("w:ilvl")) == info[1]]
        overrides = [o for o in nums[0].findall(q("w:lvlOverride")) if o.get(q("w:ilvl")) == info[1]]
        if len(levels) != 1 or len(overrides) > 1:
            return False
        if overrides:
            replacements = overrides[0].findall(q("w:lvl"))
            if len(replacements) > 1:
                return False
            if replacements:
                levels = replacements
        level = levels[0]
        if level.get(q("w:ilvl")) != info[1] or level.find(q("w:lvlPicBulletId")) is not None:
            return False
        formats, markers = level.findall(q("w:numFmt")), level.findall(q("w:lvlText"))
        if len(formats) != 1 or formats[0].get(q("w:val")) != info[2] or len(markers) > 1:
            return False
        # A missing marker adds no printed control. An explicit malformed marker
        # or a marker rendered as a box in any declared font is unresolved here.
        if not markers:
            return True
        marker = markers[0].get(q("w:val"))
        if marker is None:
            return False
        fonts = [""] + [v.lower() for f in level.findall("./" + q("w:rPr") + "/" + q("w:rFonts"))
                         for k, v in f.attrib.items() if k in (q("w:ascii"), q("w:hAnsi"), q("w:cs"), q("w:eastAsia"))]
        return not any(map_char(ch, font) in (BOX, CHECKED) for ch in marker for font in fonts)

    def rule_text_option_choices(self):
        for parent in [None] + [s for s in self.index.slots if s.kind in ("tc", "txbx", "sdt")]:
            if parent is None:
                groups = {}
                for s in self.index.roots:
                    if s.kind == "p":
                        groups.setdefault(s.part, []).append(s)
                seqs = list(groups.values())
            else:
                seqs = [[c for c in parent.children if c.kind == "p"]]
            for paras in seqs:
                i = 0
                while i < len(paras):
                    q_slot = paras[i]
                    qtext = self.text(q_slot.el).strip()
                    if not qtext or id(q_slot.el) in self.claimed or len(qtext) > 300:
                        i += 1
                        continue
                    # (a) circle-one line below (blank lines between allowed): 'YES<tab>NO'
                    k = i + 1
                    while k < len(paras) and k <= i + 3 and not self.text(paras[k].el).strip():
                        k += 1
                    if k < len(paras) and id(paras[k].el) not in self.claimed:
                        line = self.text(paras[k].el)
                        words = [w.strip() for w in re.split(r"\t+| {3,}", line) if w.strip()]
                        if 2 <= len(words) <= 6 and all(is_option_word(w) for w in words) and \
                                (qtext.endswith(("?", ":", ".")) or re.search(r"\bcircle\b", qtext, re.I)):
                            opt_slot = paras[k]
                            self.add(Area(self.choice_kind(qtext, words), clean_label(qtext), opt_slot,
                                          {"type": "text_options", "options": words}, context=self.context_for(opt_slot),
                                          options=words))
                            self.claimed.add(id(q_slot.el))
                            i = k + 1
                            continue
                    # (b) lettered list items (or short numbered items) below a question
                    qinfo = self.list_info(q_slot.el)
                    if not qtext.endswith(("?", ":")):
                        i += 1
                        continue
                    opts = []
                    j = i + 1
                    while j < len(paras):
                        el = paras[j].el
                        t = self.text(el).strip()
                        info = self.list_info(el)
                        if not t or info is None or id(el) in self.claimed or BOX in t or UNDERSCORES.search(t) or len(t) > 120:
                            break
                        lettered = info[2] in ("lowerLetter", "upperLetter", "lowerRoman", "upperRoman")
                        deeper = qinfo is not None and info[0] == qinfo[0] and int(info[1]) > int(qinfo[1])
                        if not (lettered or deeper) or (qinfo is not None and info[:2] == qinfo[:2]):
                            break
                        opts.append(paras[j])
                        j += 1
                    if len(opts) >= 2:
                        # A conditional list followed by a printed guidance link
                        # describes routes to take; it is not an answer selection.
                        following = j
                        while following < len(paras) and following <= j + 2 and not self.text(paras[following].el).strip():
                            following += 1
                        if re.match(r"^if\b", qtext, re.I) and not re.search(
                                r"\b(?:select|choose|check|tick|mark|circle|indicate)\b", qtext, re.I) and \
                                following < len(paras) and \
                                self.fixed_link_introduction(paras[following]):
                            i = j
                            continue
                        words = [option_text(self.text(o.el)) for o in opts]
                        self.add(Area(self.choice_kind(qtext, words), clean_label(qtext), opts[0],
                                      {"type": "paragraph_options", "paragraphs": [o.path for o in opts]},
                                      context=self.context_for(opts[0]), options=words, extra_slots=opts[1:]))
                        self.claimed.add(id(q_slot.el))
                        for o in opts:
                            self.claimed.add(id(o.el))
                        i = j
                        continue
                    i += 1

    # 5. tables ----------------------------------------------------------------------------------------------------
    def is_option_cell(self, c) -> bool:
        """An empty cell, or one holding only a checkbox (to be ticked), under an option column."""
        if self.cell_has_claim(c.el):
            return False
        txt = self.cell_text(c)
        if self.region_hidden(c.el):
            return False                # a checkbox its reading does not show (round 3 F1)
        return is_blank_text(txt) and self.is_empty_cell(c) or txt in (BOX, CHECKED)

    def plain_layout_properties(self, table, cell):
        """Resolve the bounded direct/default style set, without assuming a background."""
        cell_props, table_props = cell.el.findall(q("w:tcPr")), table.el.findall(q("w:tblPr"))
        if len(cell_props) > 1 or len(table_props) > 1:
            return None
        props = cell_props + table_props
        refs = table.el.findall("./" + q("w:tblPr") + "/" + q("w:tblStyle"))
        if len(refs) > 1:
            return None
        if refs:
            name = refs[0].get(q("w:val"))
        else:
            defaults = [s for s in self.package.tree("word/styles.xml").findall(q("w:style"))
                        if s.get(q("w:type")) == "table" and s.get(q("w:default")) in ("1", "true", "on")] \
                if "word/styles.xml" in self.package.names else []
            if len(defaults) > 1:
                return None
            name = defaults[0].get(q("w:styleId")) if defaults else None
        if name:
            styles, problem = self.question_box_style_chain(name, "table")
            if problem or any(s.find(q("w:tblStylePr")) is not None for s in styles):
                return None
            for style in styles:
                props.extend([style.find(q("w:tcPr")), style.find(q("w:tblPr"))])
        elif refs:
            return None
        return props

    def plain_layout_edges(self, table, cell):
        """Known visible edges on a white background; unknown formatting proves nothing.

        This narrow layout exclusion does not resolve conditional table styles,
        theme colours, diagonal borders or non-white shading. Missing borders are
        unknown too: absence of a direct border is not proof of invisible ink.
        """
        props = self.plain_layout_properties(table, cell)
        if props is None:
            return None
        background_props = list(props)
        ancestor = table.parent
        while ancestor is not None:
            if ancestor.kind == "tc":
                inherited = self.plain_layout_properties(ancestor.parent, ancestor)
                if inherited is None:
                    return None
                background_props.extend(inherited)
            ancestor = ancestor.parent
        document = self.package.tree("word/document.xml")
        backgrounds = document.findall(q("w:background"))
        if len(backgrounds) > 1:
            return None
        if backgrounds:
            background = backgrounds[0]
            if background.get(q("w:color"), "FFFFFF") != "FFFFFF" or len(background) or \
                    any("theme" in k.lower() for k in background.attrib):
                return None
        for prop in background_props:
            if prop is None:
                continue
            for shade in prop.findall(q("w:shd")):
                if shade.get(q("w:val"), "clear") not in ("clear", "nil") or \
                        shade.get(q("w:fill"), "auto") not in ("auto", "FFFFFF") or \
                        any("theme" in k.lower() for k in shade.attrib):
                    return None
        rows = self.grid(table)
        last_col = max(c.info["col"] + c.info["span"] for row in rows.values() for c in row)
        result = {}
        for side in ("top", "left", "bottom", "right"):
            table_side = side
            if (side == "top" and cell.info["row"] != min(rows)) or (side == "bottom" and cell.info["row"] != max(rows)):
                table_side = "insideH"
            if (side == "left" and cell.info["col"] != 0) or (side == "right" and cell.info["col"] + cell.info["span"] != last_col):
                table_side = "insideV"
            edge = None
            for prop in props:
                if prop is None:
                    continue
                borders = prop.findall(q("w:tcBorders" if prop.tag == q("w:tcPr") else "w:tblBorders"))
                if len(borders) > 1:
                    return None
                if not borders:
                    continue
                if any(n.tag in (q("w:start"), q("w:end"), q("w:tl2br"), q("w:tr2bl")) for n in borders[0]):
                    return None
                candidates = borders[0].findall(q("w:" + (side if prop.tag == q("w:tcPr") else table_side)))
                if len(candidates) > 1:
                    return None
                if candidates and edge is None:
                    edge = candidates[0]
            if edge is None or any("theme" in k.lower() for k in edge.attrib):
                return None
            value, color = edge.get(q("w:val")), edge.get(q("w:color"), "auto")
            if value in ("none", "nil"):
                result[side] = False
            elif value == "single" and (color == "auto" or re.fullmatch(r"[0-9A-Fa-f]{6}", color)):
                result[side] = color.upper() != "FFFFFF"
            else:
                return None
        return result

    def presentation_heading_table(self, table):
        """A single unruled title/subtitle band has spacing, not inferred answers."""
        rows = self.grid(table)
        if len(rows) != 1 or len(next(iter(rows.values()))) < 2:
            return False
        cells = next(iter(rows.values()))
        if any(c.info["vmerge"] or any(p.kind != "p" for p in c.children) for c in cells):
            return False
        printed = [c for c in cells if self.cell_text(c)]
        if len(printed) != 1:
            return False
        headings = [p for p in printed[0].children if self.text(p.el).strip()]
        if len(headings) < 2:
            return False
        for c in cells:
            edges = self.plain_layout_edges(table, c)
            if edges is None or any(edges.values()):
                return False
            for para in c.children:
                text = self.text(para.el).strip()
                if not text:
                    if not self.plain_spacing_paragraph(para):
                        return False
                    continue
                jc = para.el.findall("./" + q("w:pPr") + "/" + q("w:jc"))
                if not self.is_heading(para.el) or len(jc) != 1 or jc[0].get(q("w:val")) != "center" or \
                        not self.tab_source_visible(para) or \
                        LABEL_END.search(text) or FIELDISH.search(text) or LONG_LABEL.search(text) or \
                        self.question_box_request(text) or self.blank_spans(*self.ptext(para.el)) or \
                        "\x00" in self.ptext(para.el)[0]:
                    return False
        return True

    def continuation_layout_tail(self, table, cell):
        """An unmarked remainder below an owned box, beside only merge continuations."""
        row = self.grid(table)[cell.info["row"]]
        others = [c for c in row if c is not cell]
        if not others or any(c.info["vmerge"] != "continue" for c in others) or not self.is_empty_cell(cell):
            return False
        if any(p.kind != "p" or not self.plain_spacing_paragraph(p) for p in cell.children):
            return False
        above = next((c for c in self.grid(table).get(cell.info["row"] - 1, [])
                      if c.info["col"] == cell.info["col"] and c.info["span"] == cell.info["span"]), None)
        if above is None or not any(a.slot is above and a.target.get("type") in
                                    ("cell", "cell_replace", "cell_append") for a in self.areas):
            return False
        edges, upper = self.plain_layout_edges(table, cell), self.plain_layout_edges(table, above)
        return edges == {"top": True, "left": False, "bottom": False, "right": False} and \
            upper is not None and all(upper.values())

    def rule_tables(self):
        for tslot in [s for s in self.index.slots if s.kind == "tbl"]:
            rows = self.grid(tslot)
            if self.presentation_heading_table(tslot):
                self.claimed.update(id(node) for node in tslot.el.iter())
                continue
            ordered = sorted(rows)
            # Read header structure before any answer rule claims the empty/box
            # cells below it. Claiming answers cannot turn a header into choices.
            original_option_cells = {id(c) for r in ordered for c in rows[r] if self.is_option_cell(c)}
            handled = set()
            box_cols = {}
            for r in ordered:
                for c in rows[r]:
                    if c.info["vmerge"] != "continue" and not self.cell_has_claim(c.el) and self.cell_text(c) in (BOX, CHECKED) \
                            and not self.region_hidden(c.el):
                        box_cols.setdefault(c.info["col"], []).append((r, c))
            # empty cells in a column whose answers are boxes are filler (a sub-heading row), not answers
            filler = set()
            for col, items in box_cols.items():
                if len(items) >= 2:
                    for r in ordered:
                        for c in rows[r]:
                            if c.info["col"] == col and self.is_empty_cell(c):
                                filler.add(id(c))
            # (a) option grids: a row with a label and >=2 empty cells under short option headers -> one choice.
            #     Headers must be option words (Yes/No/N/A/0-4/...), or short, non-field-like and shared by >= 3 rows
            #     (a 'Name | Date | Signature' row is three answers, never one choice).
            candidates = []
            for r in ordered:
                cells = [c for c in sorted(rows[r], key=lambda c: c.info["col"]) if c.info["vmerge"] != "continue"]
                opt_cells = []
                for c in cells:
                    header = option_text(self.column_header(tslot, c.info["col"], r).strip("√✓✔*† "))
                    if id(c) in filler:
                        continue
                    if self.is_option_cell(c) and header and len(header.split()) <= 3 and len(header) <= 24 and \
                            (is_option_word(header) or not FIELDISH.search(header)):
                        opt_cells.append((c, header))
                cur = []
                for c, h in opt_cells:
                    if cur and cells.index(c) != cells.index(cur[-1][0]) + 1:
                        candidates.append((r, cur))
                        cur = []
                    cur.append((c, h))
                if cur:
                    candidates.append((r, cur))
            shared = {}
            for r, run in candidates:
                shared[tuple(h for _, h in run)] = shared.get(tuple(h for _, h in run), 0) + 1
            for r, run in candidates:
                if len(run) < 2:
                    continue
                headers = [h for _, h in run]
                if len(set(h.lower() for h in headers)) < len(headers):
                    continue                  # the same header over several cells: separate answers, not one choice
                optionish = all(is_option_word(h) for h in headers) or shared[tuple(headers)] >= 3
                # A pair of blank side columns records independent values. The
                # printed axis alone does not instruct the author to choose a side.
                source = self.text(tslot.el)
                if ({h.lower() for h in headers} == {"left", "right"}
                        and all(self.is_empty_cell(c) for c, _ in run)
                        and not re.search(r"\b(?:select|choose|tick|check|circle|mark)\b", source, re.I)):
                    optionish = False
                if not optionish:
                    continue
                if True:
                    label = self.row_label(tslot, r, run[0][0].info["col"])
                    if not label:
                        continue
                    boxes = [{"kind": "cell", "part": c.part, "slot": c.path} for c, _ in run]
                    self.add(Area(self.choice_kind(label, headers), label, run[0][0], {"type": "checkboxes", "boxes": boxes},
                                  context=self.context_for(run[0][0]), options=headers, extra_slots=[c for c, _ in run[1:]]))
                    for c, _ in run:
                        self.claimed.add(id(c.el))
                        for x in c.el.iter():
                            self.claimed.add(id(x))
            # (b) printed option cells to circle: 'Label | Y | N' (not a header row over empty option columns)
            for r in ordered:
                cells = [c for c in sorted(rows[r], key=lambda c: c.info["col"]) if c.info["vmerge"] != "continue"]
                i = 0
                while i < len(cells):
                    c = cells[i]
                    txt = self.cell_text(c)
                    if txt and not is_option_word(txt) and not is_blank_text(txt) and not self.cell_has_claim(c.el):
                        j = i + 1
                        opts = []
                        while j < len(cells) and is_option_word(self.cell_text(cells[j])) and not self.cell_has_claim(cells[j].el):
                            opts.append(cells[j])
                            j += 1
                        below = rows.get(r + 1, [])
                        header_row = any(x.info["col"] == opts[0].info["col"] and id(x) in original_option_cells for x in below) \
                            if len(opts) >= 2 else False
                        if len(opts) >= 2 and not header_row:
                            words = [self.cell_text(o) for o in opts]
                            boxes = [{"kind": "cell_text", "part": o.part, "slot": o.path} for o in opts]
                            self.add(Area(self.choice_kind(txt, words), clean_label(txt), opts[0],
                                          {"type": "checkboxes", "boxes": boxes}, context=self.context_for(opts[0]),
                                          options=words, extra_slots=opts[1:]))
                            for o in opts:
                                for x in o.el.iter():
                                    self.claimed.add(id(x))
                            i = j
                            continue
                    i += 1
            # (b2) a checklist down a column: box cells in >= 3 data rows under one question header, each row
            #      labelled -> one multi-choice whose options are the row labels
            for col, items in sorted(box_cols.items()):
                items = [(r, c) for r, c in items if not self.cell_has_claim(c.el)]
                if len(items) < 3:
                    continue
                ht = self.header_table(tslot)
                header = " ".join(dict.fromkeys(self.column_headers_all(tslot, col, items[0][0])))
                labelled = [(r, c, self.row_label(tslot, r, col, printed=True)) for r, c in items]
                if not header or not all(lbl for _, _, lbl in labelled):
                    continue
                first = labelled[0][1]
                boxes = [{"kind": "cell", "part": c.part, "slot": c.path} for _, c, _ in labelled]
                existing = self._col_lists.get((id(ht), col)) if ht is not tslot else None
                if existing is not None:
                    existing.target["boxes"].extend(boxes)
                    existing.options.extend(lbl for _, _, lbl in labelled)
                    existing.extra_slots.extend(c for _, c, _ in labelled)
                    for _, c, _ in labelled:
                        for x in c.el.iter():
                            self.claimed.add(id(x))
                    continue
                self._col_lists[(id(tslot), col)] = None
                self.add(Area(self.choice_kind(header, [], header + " all that apply"), clean_label(header), first,
                              {"type": "checkboxes", "boxes": boxes}, context=self.context_for(first),
                              options=[lbl for _, _, lbl in labelled], extra_slots=[c for _, c, _ in labelled[1:]]))
                self._col_lists[(id(tslot), col)] = self.areas[-1]
                for _, c, _ in labelled:
                    for x in c.el.iter():
                        self.claimed.add(id(x))
            # (b3) narrow empty cells (no room for text): a tick box beside a printed option ('[ ] Male'), grouped
            #      down the column into one question; a narrow cell with no option beside it is a spacer
            ticks = {}
            for r in ordered:
                cells = sorted([c for c in rows[r] if c.info["vmerge"] != "continue"], key=lambda c: c.info["col"])
                for i, c in enumerate(cells):
                    if not self.is_narrow(tslot, c) or not self.is_empty_cell(c) or self.cell_has_claim(c.el) or id(c) in filler:
                        continue
                    right = cells[i + 1] if i + 1 < len(cells) else None
                    opt = self.cell_text(right) if right is not None else ""
                    if opt and len(opt.split()) <= 8 and not is_blank_text(opt) and BOX not in opt:
                        ticks.setdefault(c.info["col"], []).append((r, c, option_text(opt)))
                    else:
                        filler.add(id(c))
            for col, items in sorted(ticks.items()):
                groups, cur = [], []
                for item in items:
                    if cur and item[0] != cur[-1][0] + 1:
                        groups.append(cur)
                        cur = []
                    cur.append(item)
                if cur:
                    groups.append(cur)
                for g in groups:
                    r0, c0, _ = g[0]
                    question = self.row_label(tslot, r0, col) or clean_label(self.column_header(tslot, col, r0)) or \
                        self.heading_before(c0)
                    boxes = [{"kind": "cell", "part": c.part, "slot": c.path} for _, c, _ in g]
                    options = [o for _, _, o in g]
                    if len(g) == 1:
                        area = Area("checkbox", options[0], c0, {"type": "checkboxes", "boxes": boxes},
                                    context=(self.context_for(c0) + " > " + question).strip(" >")[:300], options=options)
                    else:
                        area = Area(self.choice_kind(question, options), question or "Choose", c0,
                                    {"type": "checkboxes", "boxes": boxes}, context=self.context_for(c0), options=options,
                                    extra_slots=[c for _, c, _ in g[1:]])
                    self.add(area)
                    for _, c, _ in g:
                        for x in c.el.iter():
                            self.claimed.add(id(x))
            # (c) log tables: >= 2 consecutive fully-empty rows under a header row -> one table_rows area
            i = 0
            while i < len(ordered):
                r = ordered[i]
                cells = [c for c in rows[r] if c.info["vmerge"] != "continue"]
                empty = [c for c in cells if self.is_empty_cell(c) and not self.cell_has_claim(c.el)]
                if len(cells) >= 2 and len(empty) == len(cells):
                    run = [r]
                    j = i + 1
                    while j < len(ordered):
                        c2 = [c for c in rows[ordered[j]] if c.info["vmerge"] != "continue"]
                        e2 = [c for c in c2 if self.is_empty_cell(c) and not self.cell_has_claim(c.el)]
                        if c2 and len(e2) == len(c2) and len(c2) == len(cells):
                            run.append(ordered[j])
                            j += 1
                        else:
                            break
                    headers = [option_text(self.column_header(tslot, c.info["col"], r)) for c in cells]
                    if len(run) >= 2 and sum(1 for h in headers if h) >= max(2, len(cells) // 2):
                        first = sorted(cells, key=lambda c: c.info["col"])[0]
                        title = self.heading_before(first) or "Table"
                        self.add(Area("table_rows", clean_label(title) or "Table", first,
                                      {"type": "table_rows", "table": tslot.path, "rows": run,
                                       "columns": [c.info["col"] for c in sorted(cells, key=lambda c: c.info["col"])]},
                                      context=self.context_for(first), options=headers))
                        handled.update(run)
                        for rr in run:
                            for c in rows[rr]:
                                for x in c.el.iter():
                                    self.claimed.add(id(x))
                        i = j
                        continue
                i += 1
            # (d) single answer cells beside/below a label
            for r in ordered:
                if r in handled:
                    continue
                for c in sorted(rows[r], key=lambda c: c.info["col"]):
                    if c.info["vmerge"] == "continue" or self.cell_has_claim(c.el) or id(c) in filler:
                        continue
                    if self.continuation_layout_tail(tslot, c):
                        self.claimed.update(id(node) for node in c.el.iter())
                        continue
                    txt = self.cell_text(c)
                    placeholder = bool(txt) and (PLACEHOLDER_TEXT.match(txt) or ENTER_HINT.match(txt) or ANGLE.fullmatch(txt)
                                                 or BRACKET.fullmatch(txt))
                    guidance = bool(txt) and not placeholder and self.is_guidance_cell(c) and \
                        bool(self.row_label(tslot, r, c.info["col"]) or self.column_header(tslot, c.info["col"], r))
                    if guidance and not self.row_label(tslot, r, c.info["col"]):
                        heading = self.column_header(tslot, c.info["col"], r)
                        if re.match(r"(?:the following (?:are|is) (?:an? )?(?:examples?|illustrations?)\b|(?:for (?:reference|information|illustration)\b)|"
                                    r"examples?\b.*\bfor (?:reference|information|illustration)\b)", heading, re.I):
                            # A stated reference list has no answer destination merely
                            # because its fixed text uses the form's guidance colour.
                            # Bracketed example values inside it are printed examples too.
                            self.claimed.update(id(node) for node in c.el.iter())
                            self.protected_regions.add(c.id)
                            continue
                    instructed = bool(txt) and not placeholder and not guidance and self.instructed_answer_cell(tslot, r, c)
                    if not (self.is_empty_cell(c) or placeholder and self.cell_is_plain(c) or guidance or instructed):
                        continue
                    label = self.row_label(tslot, r, c.info["col"])
                    if instructed:
                        # The row's own item (its leftmost label cell) names an instructed cell, never a value printed
                        # beside it ('500 mg'); a group label merged over several rows is context, never the item.
                        items = [x for x in sorted(rows[r], key=lambda x: x.info["col"]) if x.info["col"] < c.info["col"]
                                 and not x.info["vmerge"] and self.is_label_cell(x)]
                        label = clean_label(self.cell_text(items[0])) if items else label
                    header = clean_label(self.column_header(tslot, c.info["col"], r))
                    below = self.label_below(tslot, c)
                    if placeholder and not label and not header:
                        label = clean_label(txt.strip("<>[]"))
                    if not label and not header and not below:
                        continue
                    name = label if label and (not header or header == label) else \
                        ("%s — %s" % (label, header) if label and header else (header or below))
                    target = {"type": "cell_replace"} if txt else {"type": "cell"}
                    if guidance or instructed:
                        target = {"type": "cell_append"}  # the printed instruction stays; the answer goes below it
                    slash = []
                    for h in [header] + self.column_headers_all(tslot, c.info["col"], r):
                        parts = [x.strip() for x in re.split(r"\s*/\s*|\s+or\s+", option_text(h))] if h else []
                        if len(parts) >= 2 and all(is_option_word(x) for x in parts):
                            slash = parts
                            break
                    if slash and label:
                        self.add(Area("choice", label, c, dict(target, write="option_text"), context=self.context_for(c),
                                      options=slash))
                        continue
                    self.add(Area(self.kind_for(name), clean_label(name), c, target, context=self.context_for(c)))

    # An imperative to write, never a printed 'Note: ...' or 'Detail: ...' label; and a request for what to write
    # ('Note if ... present', 'Describe any findings') or where to write it ('describe here', 'explain below').
    INSTRUCTED = re.compile(r"^(?:if\b[^.;:?]{0,80},\s*)?(?:please\s+)?(?:describe|explain|specify|note|list|comment|detail)\b"
                            r"(?!\s*:)", re.I)
    INSTRUCTED_REQUEST = re.compile(r"^(?:if\b[^.;:?]{0,80},\s*)?(?:please\s+)?(?:describe|explain|specify|note|list|comment|detail)"
                                    r"\s+(?:if|whether|any|all)\b", re.I)
    INSTRUCTED_PLACE = re.compile(r"\b(?:here|below|in this (?:box|space|cell|column|section))\b", re.I)
    # Printed advice to the patient: it names someone else to tell ('... to your doctor', '... to the nurse'), or
    # the column prints instructions or information rather than answers (refutation R3-5).
    ADDRESSED = re.compile(r"\b(?:to|with|tell|ask|call|contact|inform)\s+(?:your|the|a|an)\s+(?:doctor|physician|nurse|"
                           r"pharmacist|gp|provider|care\s+team|team|clinic|carer|caregiver|patient|family)\b|"
                           r"\byour\s+(?:doctor|physician|nurse|pharmacist|gp|provider|care\s+team)\b", re.I)
    CONTENT_COLUMN = re.compile(r"\b(?:instructions?|information|advice|guidance|directions?|education)\b", re.I)

    def instructed_answer_cell(self, table, row, cell):
        """A plain cell of a data row whose printed text asks for the answer to be written in it ('If palpable,
        describe here', 'Describe any findings below'), under a printed column header and beside the row's own
        label; or 'Note if ... present.'. Its answer is appended below the instruction; the instruction never names
        another row's cell. Printed content ('Note: INR must be checked', 'Detail: bleeding, infection', 'Explain
        the procedure to the patient') is not a request to write there (refutation F6)."""
        text = self.cell_text(cell)
        if len(text) > 200 or not self.INSTRUCTED.match(text) \
                or not (self.INSTRUCTED_PLACE.search(text) or self.INSTRUCTED_REQUEST.match(text)) \
                or self.ADDRESSED.search(text) \
                or self.CONTENT_COLUMN.search(self.column_header(table, cell.info["col"], row)) \
                or not self.cell_is_plain(cell) or self.row_kind(table, row) != "data":
            return False
        for paragraph in (x for x in cell.children if x.kind == "p"):
            printed, pieces = self.ptext(paragraph.el)
            if BOX in printed or CHECKED in printed or "\x00" in printed or self.blank_spans(printed, pieces):
                return False
        return bool(self.column_header(table, cell.info["col"], row)) and bool(self.row_label(table, row, cell.info["col"]))

    def question_box_style_chain(self, name, kind):
        chain, seen = [], set()
        if not name:
            return [], "The style ancestry is not uniquely defined."
        while name:
            if name in seen or len(chain) >= 32 or "word/styles.xml" not in self.package.names:
                return [], "The style ancestry is cyclic or unavailable."
            seen.add(name)
            matches = [s for s in self.package.tree("word/styles.xml").findall(q("w:style"))
                       if s.get(q("w:styleId")) == name and s.get(q("w:type")) == kind]
            if len(matches) != 1:
                return [], "The style ancestry is not uniquely defined."
            style = matches[0]
            chain.append(style)
            base = style.find(q("w:basedOn"))
            name = base.get(q("w:val")) if base is not None else ""
            if base is not None and not name:
                return [], "The style ancestry is not uniquely defined."
        return chain, ""

    def question_box_paragraph(self, node):
        """Resolve only this rule's physical break and heading scope, including style ancestry."""
        ppr = node.find(q("w:pPr"))
        ref = ppr.find(q("w:pStyle")) if ppr is not None else None
        chain, problem = self.question_box_style_chain(ref.get(q("w:val")), "paragraph") if ref is not None else ([], "")
        props = [ppr] + [s.find(q("w:pPr")) for s in chain]
        def property(name):
            return next((p.find(q("w:" + name)) for p in props
                         if p is not None and p.find(q("w:" + name)) is not None), None)
        page = property("pageBreakBefore")
        if not problem and page is not None and page.get(q("w:val"), "1") not in ("0", "false", "off"):
            problem = "A page break separates the printed question or spacer from the preceding source."
        outline = property("outlineLvl")
        if outline is not None:
            level = outline.get(q("w:val"), "")
            if level not in tuple(str(x) for x in range(10)):
                return False, False, "The paragraph's heading level is unresolved."
            return int(level) < 9, level == "0", problem
        return self.is_heading(node), False, problem

    def question_box_context(self, question, *, require_visible=False):
        """Keep explicit outer section and local heading for this body-only relation."""
        outer, role, heading, awaiting_role = "", "", "", False
        source_slots = [None, None, None]
        for slot in self.index.roots:
            if slot is question:
                break
            if slot.part != question.part:
                continue
            if slot.kind != "p":
                awaiting_role = False
                continue
            text = re.sub(r"\s+", " ", self.text(slot.el)).strip()
            if not text:
                continue
            is_heading, major, problem = self.question_box_paragraph(slot.el)
            if problem and not problem.startswith("A page break "):
                return "", problem
            if not is_heading:
                awaiting_role = False
                continue
            major = major or re.fullmatch(r"(?:part|section)\s+(?:[A-Z]|\d+|[IVX]+)\s*[:.]?", text, re.I)
            if major:
                outer, role, heading, awaiting_role = text, "", "", True
                source_slots = [slot, None, None]
            elif awaiting_role:
                role, awaiting_role = text, False
                source_slots[1] = slot
            else:
                heading = text
                source_slots[2] = slot
        if require_visible and any(s is not None and not self.tab_source_visible(s) for s in source_slots):
            return " > ".join(dict.fromkeys(x for x in (outer, role, heading) if x)), \
                "A governing heading has hidden or unresolved visibility."
        return " > ".join(dict.fromkeys(x for x in (outer, role, heading) if x)), ""

    def question_box_bordered(self, table, cell):
        borders = [cell.el.find("./" + q("w:tcPr") + "/" + q("w:tcBorders")),
                   table.el.find("./" + q("w:tblPr") + "/" + q("w:tblBorders"))]
        style_ref = table.el.find("./" + q("w:tblPr") + "/" + q("w:tblStyle"))
        if style_ref is not None:
            styles, problem = self.question_box_style_chain(style_ref.get(q("w:val")), "table")
            if problem or any(s.find(q("w:tblStylePr")) is not None for s in styles):
                return False
            borders.extend(s.find("./" + q("w:tblPr") + "/" + q("w:tblBorders")) for s in styles)
        for side in ("top", "left", "bottom", "right"):
            edge = next((b.find(q("w:" + side)) for b in borders
                         if b is not None and b.find(q("w:" + side)) is not None), None)
            if edge is None or edge.get(q("w:val"), "none") in ("none", "nil", ""):
                return False
        return True

    @staticmethod
    def question_box_request(text):
        return bool(re.search(r"\?", text) or re.match(
            r"^(?:please\s+)?(?:set out|provide|describe|explain|detail|list)\b", text, re.I))

    @staticmethod
    def question_box_reference(text):
        return re.search(r"\b(?:above|previous|following)\s+(?:question|answer|section)\b|\bas above\b|\bsame as\b", text, re.I)

    @staticmethod
    def question_box_signing(text):
        # Only the demonstrated temporal/source-reference phrases qualify.
        # A direct request about "the initial report" remains ambiguous, as do
        # bare "Initial", "Initials", initial-here, and other signing markers.
        reading = re.sub(r"\b(since|in\s+the\s+case\s+of)\s+the\s+initial\s+report\b",
                         r"\1 the report", text, flags=re.I)
        # A signing verb still governs an adjective-bearing report (for example,
        # "Please sign the initial report here?"). The shared regex is unchanged.
        if reading != text and re.search(
                r"\b(?:(?:counter|under|co|re)[ -]?)?sign(?:s|ed|ing|off|offs)?\b", reading, re.I):
            return True
        return SIGNATURE.search(reading) or INITIALS.search(reading) or re.search(r"\bconsent\b", reading, re.I)

    def previous_question_source(self, question, raw, context):
        """Resolve only the immediately preceding, already owned question box.

        The printed *question* is carried, never its answer. An intervening block,
        section change, signing context, unresolved owner or chained reference
        makes the relation unavailable.
        """
        if not re.search(r"\b(?:above|previous) question\b", raw, re.I) or re.search(
                r"\b(?:above|previous|following) (?:answer|section)\b|\bfollowing question\b|\bas above\b|\bsame as\b", raw, re.I):
            return None
        node, blanks = question.el.getprevious(), 0
        while node is not None and node.tag == q("w:p"):
            slot = self.index.by_el.get(id(node))
            if slot is None or self.text(node).strip() or not self.plain_spacing_paragraph(slot):
                return None
            blanks += 1
            if blanks > 2:
                return None
            node = node.getprevious()
        table = self.index.by_el.get(id(node)) if node is not None else None
        if table is None or table.kind != "tbl" or table.parent is not None:
            return None
        owners = [a for a in self.areas if a.slot.parent is table]
        if len(owners) != 1:
            return None
        owner = owners[0]
        if owner.kind != "long_text" or not owner.complete_source or owner.protection or owner.source_questions or \
                not context or owner.context != context:
            return None
        previous = table.el.getprevious()
        while previous is not None and previous.tag == q("w:p") and not self.text(previous).strip():
            previous = previous.getprevious()
        source = self.index.by_el.get(id(previous)) if previous is not None else None
        if source is None or source.kind != "p" or re.sub(r"\s+", " ", self.text(previous)).strip() != owner.label:
            return None
        return {"relation": "immediate_previous_question", "question": owner.label,
                "source": {"part": source.part, "slot": source.path, "fingerprint": fingerprint(source.el)},
                "reference": {"part": question.part, "slot": question.path,
                              "fingerprint": fingerprint(question.el)}}

    def paragraph_list_box_source(self, table):
        """A whole question/list owns its sole blank box; bullets are not controls.

        With no printed selection operation, the answer is complete text and
        cardinality stays unspecified. A final Other descriptor does not acquire
        the whole box. Explicit selection controls/instructions keep their own
        rules. All source blocks and package definitions are bound at export.
        """
        node, blanks = table.el.getprevious(), 0
        while node is not None and node.tag == q("w:p") and not self.text(node).strip():
            slot = self.index.by_el.get(id(node))
            if slot is None or not self.plain_spacing_paragraph(slot) or self.question_box_paragraph(node)[2]:
                return None
            blanks += 1
            if blanks > 4:
                return None
            node = node.getprevious()
        descriptors, sources = [], []
        unsafe = {SDT, FLDCHAR, q("w:instrText"), q("w:drawing"), q("w:pict"),
                  q("w:object"), q("w:sectPr"), q("w:sym")}
        while node is not None and node.tag == q("w:p") and self.list_info(node):
            slot = self.index.by_el.get(id(node))
            _, _, problem = self.question_box_paragraph(node)
            # Bold list text is still a descriptor. Only explicit heading/outline
            # properties establish a new section inside this numbered block.
            style = node.find("./" + q("w:pPr") + "/" + q("w:pStyle"))
            chain, _ = self.question_box_style_chain(style.get(q("w:val")), "paragraph") if style is not None else ([], "")
            heading = any((outline := part.find("./" + q("w:pPr") + "/" + q("w:outlineLvl"))) is not None
                          and outline.get(q("w:val")) in tuple(str(i) for i in range(9)) for part in [node] + chain)
            heading = heading or style is not None and bool(HEADING_STYLE.match(style.get(q("w:val"), "")))
            info = self.list_info(node)
            if (slot is None or slot.parent is not None or id(node) in self.claimed or heading
                    or problem and not problem.startswith("A page break ")
                    or not self.tab_source_visible(slot)
                    or any(x.tag in unsafe or x.tag == q("w:br") and x.get(q("w:type")) != "page"
                           for x in node.iter())
                    or info[1] not in self.numbering().get(info[0], {}) or not self.list_marker_is_plain(info)):
                return None
            text = re.sub(r"\s+", " ", self.text(node)).strip()
            if (not text or len(text) > MAX_MAPPING_LABEL or self.blank_spans(*self.ptext(node))
                    or BOX in text or CHECKED in text or self.question_box_request(text)):
                return None
            if descriptors and list(info[1:]) != descriptors[0]["numbering"][1:]:
                return None
            descriptors.insert(0, {"part": slot.part, "slot": slot.path, "fingerprint": fingerprint(node),
                                   "text": text, "numbering": list(info)})
            sources.insert(0, slot)
            node = node.getprevious()
        question = self.index.by_el.get(id(node)) if node is not None else None
        if len(descriptors) < 2 or question is None or question.kind != "p" or question.parent is not None:
            return None
        prompt = re.sub(r"\s+", " ", self.text(node)).strip()
        if (id(node) in self.claimed or not prompt.endswith(("?", ":"))
                or not (self.question_box_request(prompt) or re.match(r"^(?:what|which|where|how|who|when)\b", prompt, re.I)
                        or self.question_box_authorship(prompt))
                or self.question_box_reference(prompt)
                or self.question_box_paragraph(node)[2] or not self.tab_source_visible(question)
                or any(x.tag in unsafe for x in node.iter()) or self.blank_spans(*self.ptext(node))):
            return None
        # Plain local instructions carry ownership too. Preserve their full text
        # and anchors up to the preceding heading/table, without borrowing across
        # a competing question or an unresolved source block.
        instructions = []
        prior = node.getprevious()
        while prior is not None and prior.tag == q("w:p"):
            slot = self.index.by_el.get(id(prior))
            heading, _, barrier = self.question_box_paragraph(prior)
            if heading:
                break
            text = re.sub(r"\s+", " ", self.text(prior)).strip()
            if (slot is None or barrier or not self.tab_source_visible(slot)
                    or any(x.tag in unsafe for x in prior.iter())):
                return None
            if text:
                if (self.list_info(prior) or self.question_box_request(text) or self.question_box_reference(text)
                        or self.blank_spans(*self.ptext(prior)) or BOX in text or CHECKED in text):
                    return None
                instructions.insert(0, {"part": slot.part, "slot": slot.path,
                                        "fingerprint": fingerprint(prior), "text": text})
            elif not self.plain_spacing_paragraph(slot):
                return None
            prior = prior.getprevious()
        context, problem = self.question_box_context(question, require_visible=True)
        context = " > ".join(x for x in (context, *[i["text"] for i in instructions], prompt,
                              "Printed descriptors: " + " | ".join(x["text"] for x in descriptors)) if x)
        if (problem or len(prompt) > MAX_MAPPING_LABEL or len(context) > MAX_MAPPING_CONTEXT
                or self.question_box_signing(context)
                or re.search(r"\b(?:select|choose|tick|check|mark|circle|indicate)\b|\b(?:only one|one only|all that apply)\b"
                             r"|\b(?:only|solely|exclusively)\b[^>]*\bother\b|\bother\b[^>]*\bonly\b",
                             context, re.I)):
            return None
        protection = ("This area is reserved for another author's comments. Ordinary clinician notes do not establish that author's statement."
                      if self.question_box_authorship(prompt) else "")
        relation = {"relation": "paragraph_list_answer", "question": prompt, "context": context,
                    "cardinality": "unspecified",
                    "source": {"part": question.part, "slot": question.path, "fingerprint": fingerprint(node)},
                    "descriptors": descriptors,
                    "definitions": {name: hashlib.sha256(self.package.zip.read(name)).hexdigest()
                                    for name in ("word/numbering.xml", "word/_rels/document.xml.rels")
                                    if name in self.package.names}}
        if instructions:
            relation["instructions"] = instructions
        return question, prompt, context, protection, relation, sources

    @staticmethod
    def question_box_authorship(text):
        return re.match(r"^this section is for (?:the )?(?:patient|parent|guardian|line manager|employer|witness)\b"
                        r".*\bto (?:add|provide|record)\b.*\b(?:comments|concerns|statement)\b", text, re.I)

    def rule_question_boxes(self, *, list_only=False):
        """A printed body question followed by its own empty one-cell bordered table.

        Never borrow across another block, assign a list option, shorten a question,
        or treat a signing box as ordinary narrative. Unresolved boxes stay visible.
        """
        unsafe = {q("w:sdt"), FLDCHAR, q("w:instrText"), q("w:drawing"), q("w:pict"),
                  q("w:object"), q("w:sectPr"), q("w:br"), q("w:vanish")}
        for table in self.index.roots:
            if table.kind != "tbl" or table.part != "word/document.xml":
                continue
            cells = [c for c in table.children if c.kind == "tc"]
            if len(table_rows_of(table.el)) != 1 or len(cells) != 1:
                continue
            cell = cells[0]
            if self.cell_has_claim(cell.el):
                continue
            raw, question, reason = "", None, "No unambiguous adjacent printed question."
            node, skipped = table.el.getprevious(), 0
            while node is not None and node.tag == q("w:p"):
                if any(x.tag in unsafe for x in node.iter()):
                    break
                _, _, problem = self.question_box_paragraph(node)
                if problem:
                    reason = problem
                    break
                raw = re.sub(r"\s+", " ", self.text(node)).strip()
                if raw:
                    question = self.index.by_el.get(id(node))
                    break
                skipped += 1
                if skipped > 2:
                    break
                node = node.getprevious()
            bordered = self.question_box_bordered(table, cell)
            list_source = self.paragraph_list_box_source(table) if bordered and cell.info["span"] == 1 and cell.info["vmerge"] is None else None
            if list_source:
                owner, label, list_context, protection, relation, sources = list_source
                if protection:
                    self.protected_regions.add(cell.id)
                if not self.is_empty_cell(cell):
                    continue
                paragraphs = [s for s in cell.children if s.kind == "p"]
                if not paragraphs or not all(self.tab_source_visible(p) for p in paragraphs):
                    continue
                self.add(Area("long_text", label, cell, {"type": "cell"}, context=list_context,
                              complete_source=True, protection=protection, source_questions=[relation]))
                for source in [owner] + sources:
                    self.claimed.add(id(source.el))
                continue
            if list_only:
                continue
            if question is not None and self.question_box_authorship(raw):
                # Existing author statements are just as protected as an empty
                # author box, including when a forged mapping changes its kind.
                self.protected_regions.add(cell.id)
            if not self.is_empty_cell(cell):
                continue
            context, scope_problem = self.question_box_context(question) if question is not None else ("", "")
            request = self.question_box_request(raw)
            prior_question = ""
            previous, blanks = (question.el.getprevious() if question is not None else None), 0
            while previous is not None and previous.tag == q("w:p"):
                prior = re.sub(r"\s+", " ", self.text(previous)).strip()
                heading, _, barrier = self.question_box_paragraph(previous)
                if any(x.tag in unsafe for x in previous.iter()) or barrier or heading:
                    break
                if prior:
                    if self.question_box_request(prior) and id(previous) not in self.claimed:
                        prior_question = prior
                    break
                blanks += 1
                if blanks > 2:
                    break
                previous = previous.getprevious()
            reference = self.question_box_reference(raw)
            related = self.previous_question_source(question, raw, context) if reference and question is not None else None
            if related:
                context += " > Related preceding question: " + related["question"]
            # Question and section are distinct source blocks: joining them can
            # manufacture the adjective phrase across a real signing boundary.
            signing = self.question_box_signing(raw) or self.question_box_signing(context)
            inline_answer = question is not None and (BOX in raw or CHECKED in raw or
                bool(self.blank_spans(*self.ptext(question.el))))
            if not bordered or cell.info["span"] != 1 or cell.info["vmerge"] is not None:
                reason = "The border or unmerged one-cell structure is not explicit."
            elif scope_problem:
                reason = scope_problem
            elif prior_question:
                reason = "The question spans multiple paragraphs; review the complete source block. Earlier text: " + prior_question
            elif inline_answer:
                reason = "The printed question contains another answer area; review their separate destinations."
            elif len(raw) > MAX_MAPPING_LABEL or len(context) > MAX_MAPPING_CONTEXT:
                reason = "The complete question or section exceeds the mapping label limit; it was not shortened."
                if len(context) > MAX_MAPPING_CONTEXT:
                    reason += " Section: " + context
            elif reference and related is None:
                reason = "The question refers to another area; review both source questions."
            elif signing:
                reason = "Signing or consent context needs explicit review; it is not an ordinary narrative answer."
            elif question is not None and self.question_box_authorship(raw):
                reason = "This area is reserved for another author's comments. Ordinary clinician notes do not establish that author's statement."
                self.add(Area("long_text", raw, cell, {"type": "cell"}, context=context,
                              complete_source=True, protection=reason))
                self.claimed.add(id(question.el))
                continue
            elif question is not None and question.parent is None and request and \
                    id(question.el) not in self.claimed and self.list_info(question.el) is None:
                self.add(Area("long_text", raw, cell, {"type": "cell"}, context=context, complete_source=True,
                              source_questions=[related] if related else []))
                self.claimed.add(id(question.el))
                continue
            self.notes.append("Unassigned answer box at " + cell.id + ". " + reason +
                              (" Printed text: " + raw if raw else ""))

    def cell_twips(self, tslot, c) -> float:
        tcpr = c.el.find(q("w:tcPr"))
        tcw = tcpr.find(q("w:tcW")) if tcpr is not None else None
        if tcw is None:
            return 10000.0
        try:
            val = float(tcw.get(q("w:w")) or 0)
        except ValueError:
            return 10000.0
        kind = tcw.get(q("w:type")) or "dxa"
        if kind == "dxa":
            return val
        if kind == "pct":
            tblpr = tslot.el.find(q("w:tblPr"))
            tw = tblpr.find(q("w:tblW")) if tblpr is not None else None
            total = float(tw.get(q("w:w")) or 0) if tw is not None and (tw.get(q("w:type")) or "") == "dxa" else 9360.0
            return val / 5000.0 * (total or 9360.0)
        return 10000.0

    def is_narrow(self, tslot, c) -> bool:
        return self.cell_twips(tslot, c) < 400

    def is_guidance_cell(self, c) -> bool:
        """Every visible run uses hint ink; colour does not establish that text is disposable."""
        runs = [r for r in c.el.iter(R) if (r.findtext(T) or "").strip()]
        if not runs or c.el.find(".//" + q("w:tbl")) is not None or c.el.find(".//" + SDT) is not None or \
                c.el.find(".//" + FLDCHAR) is not None \
                or BOX in self.cell_text(c):
            return False
        # Hyperlink colour alone denotes a fixed reference, not an answer area.
        # A linked guidance cell must also carry ordinary unlinked guidance.
        if not any(any(ch.isalnum() for ch in (r.findtext(T) or "")) and
                   not any(parent.tag == q("w:hyperlink") for parent in r.iterancestors())
                   for r in runs):
            return False
        return all(is_hint_run(r) for r in runs)

    def cell_is_plain(self, c) -> bool:
        return all(x.kind in ("p", "glyphs") for x in c.children) and len([x for x in c.children if x.kind == "p"]) <= 2

    def label_below(self, tslot, cell) -> str:
        """Captions printed under a blank cell ('Last Name' under the box)."""
        rows = self.grid(tslot)
        below = rows.get(cell.info["row"] + 1, [])
        for c in below:
            if c.info["col"] == cell.info["col"] and c.info["span"] == cell.info["span"]:
                txt = self.cell_text(c)
                if txt and len(txt) <= 40 and not is_blank_text(txt):
                    above = rows.get(cell.info["row"] - 1, [])
                    if not any(x.info["col"] == cell.info["col"] and self.cell_text(x) for x in above):
                        return clean_label(txt)
        return ""

    # 6. a label followed by empty paragraph(s): the answer goes on those lines ------------------------------------
    def plain_spacing_paragraph(self, slot, *, unused_tab_stops=False):
        """Only unmarked spacing can yield to a separately mapped destination."""
        text, pieces = self.ptext(slot.el)
        if text.strip() or self.blank_spans(text, pieces):
            return False
        markers = {q("w:sdt"), FLDCHAR, q("w:instrText"), TXBX, q("w:drawing"), q("w:pict"),
                   q("w:object"), q("w:pBdr"), q("w:framePr"), q("w:u"), q("w:br"), q("w:sectPr"), q("w:tabs"),
                   q("w:tab"), q("w:shd"), q("w:highlight"), q("w:numPr"), q("w:bdr"), q("w:strike"), q("w:dstrike")}
        if unused_tab_stops and "\t" not in text:
            # No rendered tab character exists (only printed spaces, if any). Its
            # configured stops cannot draw a blank, but every other direct or
            # inherited marker check still applies (an underlined space is marked).
            markers -= {q("w:tabs"), q("w:tab")}
        if any(node.tag in markers for node in slot.el.iter()):
            return False
        if "word/styles.xml" in self.package.names:
            defaults = self.package.tree("word/styles.xml").find(q("w:docDefaults"))
            if defaults is not None and any(node.tag in markers for node in defaults.iter()):
                return False
        def unmarked_style(refs, kind):
            # An explicit style replaces that type's implicit default, but all
            # ancestors still participate. Unknown or duplicate references cannot
            # prove that an empty-looking paragraph has no drawn answer area.
            if len(refs) > 1:
                return False
            if refs:
                name = refs[0].get(q("w:val"))
            else:
                defaults = [s for s in self.package.tree("word/styles.xml").findall(q("w:style"))
                            if s.get(q("w:type")) == kind and s.get(q("w:default")) in ("1", "true", "on")] \
                    if "word/styles.xml" in self.package.names else []
                if len(defaults) > 1:
                    return False
                if not defaults:
                    return True
                name = defaults[0].get(q("w:styleId"))
            styles, problem = self.question_box_style_chain(name, kind)
            return not problem and not any(node.tag in markers for style in styles for node in style.iter())

        if not unmarked_style(slot.el.findall("./" + q("w:pPr") + "/" + q("w:pStyle")), "paragraph"):
            return False
        for run in slot.el.iter(R):
            if not unmarked_style(run.findall("./" + q("w:rPr") + "/" + q("w:rStyle")), "character"):
                return False
        parent = slot.parent
        while parent is not None:
            if parent.kind == "tbl" and not unmarked_style(
                    parent.el.findall("./" + q("w:tblPr") + "/" + q("w:tblStyle")), "table"):
                return False
            parent = parent.parent
        return True

    def mapped_beside_label(self, slot):
        """A sole plain cell label already has a directly adjacent mapped answer cell.

        This does not infer ownership from an empty neighbour alone, and never
        borrows an outer table's destination for a nested control or text box.
        """
        cell = self.host_cell(slot)
        if cell is None or slot.parent is not cell or any(c.kind != "p" for c in cell.children):
            return False
        named = [p for p in cell.children if self.text(p.el).strip()]
        if named != [slot] or self.blank_spans(*self.ptext(slot.el)) or "\x00" in self.ptext(slot.el)[0]:
            return False
        right = next((c for c in self.grid(cell.parent).get(cell.info["row"], [])
                      if c.info["col"] == cell.info["col"] + cell.info["span"]
                      and c.info["vmerge"] != "continue"), None)
        if right is None or self.row_label(cell.parent, cell.info["row"], right.info["col"]) != clean_label(self.text(slot.el)):
            return False
        return any(a.slot is right and a.target.get("type") in ("cell", "cell_replace", "cell_append") for a in self.areas)

    def mapped_below_label(self, slot):
        """A sole plain column label already owns the cell immediately below it."""
        cell = self.host_cell(slot)
        if cell is None or slot.parent is not cell or any(c.kind != "p" for c in cell.children):
            return False
        if [p for p in cell.children if self.text(p.el).strip()] != [slot] or \
                self.blank_spans(*self.ptext(slot.el)) or "\x00" in self.ptext(slot.el)[0]:
            return False
        below = next((c for c in self.grid(cell.parent).get(cell.info["row"] + 1, [])
                      if c.info["col"] == cell.info["col"] and c.info["span"] == cell.info["span"]
                      and c.info["vmerge"] != "continue"), None)
        if below is None or clean_label(self.column_header(cell.parent, below.info["col"], below.info["row"],
                                                         complete=True)) != clean_label(self.text(slot.el)):
            return False
        return any(a.slot is below and a.target.get("type") in ("cell", "cell_replace", "cell_append") for a in self.areas)

    def rule_lines_below_label(self):
        containers = [s for s in self.index.slots if s.kind in ("tc", "txbx")]
        seqs = [[c for c in s.children if c.kind == "p"] for s in containers]
        by_part = {}
        for s in self.index.roots:
            if s.kind == "p":
                by_part.setdefault(s.part, []).append(s)
        body_seqs = list(by_part.values())
        for paras, in_container in [(x, True) for x in seqs] + [(x, False) for x in body_seqs]:
            for i, ps in enumerate(paras):
                if id(ps.el) in self.claimed:
                    continue
                txt = self.text(ps.el).strip()
                if not txt or len(txt) > 200 or BOX in txt or "\x00" in self.ptext(ps.el)[0]:
                    continue
                if UNDERSCORES.search(txt) or DOTS.search(txt):
                    continue
                label = clean_label(txt)
                signing = bool(SIGNATURE.search(label) or INITIALS.search(label) or re.match(r"^(?:date|printed name|name)\b", label, re.I))
                if in_container:
                    if not (txt.endswith(":") or signing or self.is_heading(ps.el) and len(paras) > i + 1):
                        continue
                elif not ((signing or LONG_LABEL.search(label) and self.text(ps.el).rstrip("\n").endswith(":"))
                          and len(label.split()) <= 12):
                    continue                      # (trailing spaces after the colon mean: answer on this line)
                blanks = []
                for nxt in paras[i + 1:]:
                    # A table or other block between paragraphs ends the relationship.
                    if nxt.el.getprevious() is not (blanks[-1].el if blanks else ps.el):
                        break
                    t2, pcs = self.ptext(nxt.el)
                    if t2.strip() or id(nxt.el) in self.claimed or nxt.el.find(".//" + TXBX) is not None:
                        break
                    blanks.append(nxt)
                    if not in_container and len(blanks) >= 1:
                        break
                if not blanks:
                    continue
                if in_container and self.mapped_beside_label(ps) and all(self.plain_spacing_paragraph(b) for b in blanks):
                    continue
                kind = "long_text" if len(blanks) >= 2 and not signing else self.kind_for(label)
                self.add(Area(kind, label, blanks[0], {"type": "paragraph"}, context=self.context_for(ps),
                              extra_slots=blanks[1:]))
                self.claimed.add(id(ps.el))
                for b in blanks:
                    self.claimed.add(id(b.el))

    # 7. blanks and 'Label:' answers inside paragraphs ---------------------------------------------------------------
    def blank_spans(self, text, pieces):
        spans = []
        for rx, kind in ((SEGMENTED, "segmented"), (DIGIT_RUN, "segmented"), (UNDERSCORES, "blank"), (DOTS, "blank"), (TOKEN, "token"), (BRACKET, "bracket"), (ANGLE, "angle")):
            for m in rx.finditer(text):
                spans.append((m.start(), m.end(), kind))
        # underlined tabs / spaces (a drawn line)
        run_start = None
        for pc in pieces:
            underlined = False
            if pc.kind in ("tab", "t") and pc.run is not None:
                rpr = pc.run.find(q("w:rPr"))
                u = rpr.find(q("w:u")) if rpr is not None else None
                underlined = u is not None and (u.get(q("w:val")) or "single") != "none"
                if pc.kind == "t" and (pc.node.text or "").strip("    "):
                    underlined = False
            if underlined:
                if run_start is None:
                    run_start = pc.start
                run_end = pc.end
            elif run_start is not None:
                spans.append((run_start, run_end, "utab"))
                run_start = None
        if run_start is not None:
            spans.append((run_start, run_end, "utab"))
        # inline guidance ink: 'Label: Enter PID No.' written in blue/grey
        hint_start = None
        for pc in pieces + [None]:
            hint = pc is not None and pc.kind == "t" and pc.run is not None and is_hint_run(pc.run)
            if hint and hint_start is None:
                hint_start, hint_end = pc.start, pc.end
            elif hint:
                hint_end = pc.end
            elif hint_start is not None:
                seg = text[hint_start:hint_end]
                lead = text[:hint_start].rstrip()
                if seg.strip() and (ENTER_HINT.match(seg.strip()) or PLACEHOLDER_TEXT.match(seg.strip()) or
                                    (lead.endswith(":") and len(seg.split()) <= 6)):
                    lstrip = len(seg) - len(seg.lstrip())
                    spans.append((hint_start + lstrip, hint_end - (len(seg) - len(seg.rstrip())), "hint"))
                hint_start = None
        kept = []
        for start, end, kind in merge_spans(spans):
            if hyperlink_write(pieces, start, end):
                owner = next((ancestor for pc in pieces if pc.run is not None
                              for ancestor in pc.run.iterancestors() if ancestor.tag == q("w:p")), None)
                slot = self.index.by_el.get(id(owner)) if owner is not None else None
                note = "Answer-like text inside a fixed hyperlink was kept unchanged; review the original."
                if slot is not None:
                    note += " Location: " + slot.id
                if note not in self.notes:
                    self.notes.append(note)
            else:
                kept.append((start, end, kind))
        return kept

    def rule_paragraph_fields(self):
        pending, pending_last = None, None     # a multi-line answer area and its last line
        for slot in [s for s in self.index.slots if s.kind == "p"]:
            p = slot.el
            if id(p) in self.claimed:
                pending = None
                continue
            cell = self.host_cell(slot)
            if cell is not None and id(cell.el) in self.claimed:
                continue
            text, pieces = self.ptext(p)
            spans = self.blank_spans(text, pieces)
            residue = "".join(ch for i, ch in enumerate(text) if not any(s <= i < e for s, e, _ in spans))
            if len(spans) == 1 and not clean_label(residue.replace("_", "")):
                # a line that is ONLY a drawn blank: continues the previous line's area, or takes the label above
                sibs, idx = self.para_neighbours(slot)
                prev_sib = sibs[idx - 1] if idx else None
                if pending is not None and prev_sib is pending_last:
                    pending.extra_slots.append(slot)
                    if pending.kind == "text":
                        pending.kind = "long_text"
                    self.claimed.add(id(p))
                    pending_last = slot
                    continue
                label_p = self.previous_paragraph(slot, limit=2)
                label = clean_label(self.text(label_p.el)) if label_p is not None and id(label_p.el) not in self.claimed else ""
                if len(label.split()) > MAX_LABEL_WORDS:
                    label = ""
                if not label and cell is not None and label_p is None:
                    label_p = None
                    # Under a printed column header, a value cell to the left ('▯▯▯/▯▯▯ Systolic diastolic') is a
                    # sibling answer, never this blank's question: the header names it (refutation 2026-09-28 B1).
                    header = clean_label(self.column_header(cell.parent, cell.info["col"], cell.info["row"]))
                    label = self.row_label(cell.parent, cell.info["row"], cell.info["col"], values=not header) or header
                if not label and spans[0][2] in ("angle", "bracket", "token"):
                    label = clean_label(text[spans[0][0]:spans[0][1]].strip("{}[]<> "))
                label = label or "Answer"
                area = Area(self.kind_for(label), label, slot, {"type": "span", "start": spans[0][0], "end": spans[0][1],
                                                               "shape": spans[0][2]}, context=self.context_for(slot))
                self.add(area)
                if label_p is not None and label != "Answer":
                    self.claimed.add(id(label_p.el))
                pending, pending_last = area, slot
                continue
            pending = None
            if not text.strip(" \t\n\x00"):
                continue
            if self.segment_paragraph(slot, text, pieces, spans):
                self.claimed.add(id(p))

    LABEL_COLON = re.compile(r"([^\t\x00:;?!]{1,160}?)\s*:(?=[\s\x00]|$)")
    ANSWER_GAP = re.compile(r"[ \t\u00a0\u2002\u2003]*")
    ANSWER_UNIT = re.compile(r"\(?\s*(?:mm|dd|yy|hh|units?|kg|cm|lbs?|in|minutes?|hours?|days?|years?|%)\b", re.I)

    def inline_answer_gap(self, slot) -> bool:
        """'Label:' followed by a printed gap (a tab or three or more spaces) and then more of an answer line:
        another 'Label:' or a unit. The answer is written inside the printed line (segment_paragraph's reading)."""
        text = self.ptext(slot.el)[0]
        for m in self.LABEL_COLON.finditer(text):
            label_text = m.group(1)
            if len(label_text.split()) > MAX_LABEL_WORDS or not re.search(r"[A-Za-z]", label_text):
                continue
            rest = text[m.end():]
            gap = self.ANSWER_GAP.match(rest).group(0)
            after = rest[len(gap):]
            if after and ("\t" in gap or len(gap) >= 3) and (self.LABEL_COLON.match(after) or self.ANSWER_UNIT.match(after)):
                return True
        return False

    def fixed_link_introduction(self, slot):
        """A printed instruction introducing a fixed link in the next paragraph."""
        text = self.text(slot.el).strip()
        if not text.endswith(":") or not re.search(r"\bplease\s+(?:contact|refer to)\b", text, re.I):
            return False
        node, blanks = slot.el.getnext(), 0
        while node is not None and node.tag == q("w:p"):
            if self.text(node).strip():
                return node.find(".//" + q("w:hyperlink")) is not None
            if any(x.tag in {q("w:sectPr"), q("w:br"), q("w:drawing"), q("w:pict"), SDT, FLDCHAR}
                   for x in node.iter()):
                return False
            blanks += 1
            if blanks > 2:
                return False
            node = node.getnext()
        return False

    def segment_paragraph(self, slot, text, pieces, spans) -> int:
        made = 0
        format_hint = False
        blanks = list(spans)
        # 'Label:' followed by a gap (>=1 tab or >=3 spaces) or the end of the paragraph, with nothing else drawn
        for m in self.LABEL_COLON.finditer(text):
            if self.fixed_link_introduction(slot):
                continue
            end = m.end()
            if any(s <= m.start() < e or s <= end - 1 < e for s, e, _ in blanks):
                continue
            rest = text[end:]
            gap = self.ANSWER_GAP.match(rest).group(0)
            after = rest[len(gap):]
            if after.startswith(("\x00", BOX, CHECKED)):
                continue                          # an object or box right after the label answers it
            if any(s == end + len(gap) for s, e, _ in blanks):
                continue                          # a drawn blank follows; handled with the blanks
            label_text = m.group(1)
            if len(label_text.split()) > MAX_LABEL_WORDS or not re.search(r"[A-Za-z]", label_text):
                continue
            hint = re.match(r"\(?[^()]{0,40}(?:mm|dd|yy|yyyy|month|day|year|hh|24)[^()]{0,40}\)?\s*$", after, re.I)
            if hint and after.strip().startswith("("):
                blanks.append((len(text), len(text), "after_label"))
                format_hint = True
                continue                          # 'Date: (month/day/year)': the answer goes after the hint
            if after and not ("\t" in gap or len(gap) >= 3):
                continue                          # a sentence continues after the colon
            if after and not self.LABEL_COLON.match(after) and not self.ANSWER_UNIT.match(after):
                continue                          # other printed text follows the gap: not an answer space
            blanks.append((end, end + len(gap), "after_label"))
        blanks = merge_spans(blanks)
        if not blanks:
            return 0
        if self.is_heading(slot.el) and all(k == "after_label" for _, _, k in blanks) \
                and not format_hint:
            return 0
        prose_words = len(re.findall(r"[A-Za-z]{2,}", "".join(ch for i, ch in enumerate(text)
                                                             if not any(s0 <= i < e0 for s0, e0, _ in blanks))))
        kept = []
        for s0, e0, kind in blanks:
            inner = text[s0:e0]
            if kind in ("bracket", "angle") and re.search(r"pre-?filled|pre-?populated|by (?:the )?sponsor", inner, re.I):
                self.notes.append("A sponsor pre-filled placeholder was kept as printed: %s" % inner[:60])
                continue
            if re.search(r"\bpage\s*_+\s*of\s*_+", text, re.I) and re.search(r"\bpage\s*$|\bof\s*$", text[:s0], re.I):
                continue                          # 'Page ___ of ___' numbering lines
            kept.append((s0, e0, kind))
        blanks = kept
        if not blanks:
            return 0
        prev_end = 0
        for n, (s, e, kind) in enumerate(blanks):
            if hyperlink_write(pieces, s, s if kind == "after_label" else e):
                self.notes.append("An answer insertion inside a fixed hyperlink was left unassigned at " + slot.id)
                continue
            seg = text[prev_end:s]
            seg = re.split(r"[\x00" + BOX + CHECKED + "]", seg)[-1]
            seg = re.split(r"(?<=[.;!?])\s+(?=[A-Z(])", seg.strip())[-1]
            label = clean_label(seg)
            if kind in ("token", "bracket", "angle", "hint") and not label:
                label = clean_label(re.sub(r"^(?:enter|insert|type|add|specify)\s+", "", text[s:e].strip("{}[]<> "), flags=re.I))
            elif kind in ("token", "bracket", "angle"):
                inner = clean_label(text[s:e].strip("{}[]<> "))
                label = inner if kind == "token" or not label else ("%s %s" % (label, inner)).strip()
            if not label:
                nxt = blanks[n + 1][0] if n + 1 < len(blanks) else len(text)
                after = clean_label(re.split(r"[\x00" + BOX + CHECKED + "]", text[e:nxt])[0])
                label = after or clean_label(self.previous_paragraph_text(slot)) or "Answer"
            if kind == "after_label" and self.is_label_of_next_lines(slot, text):
                continue
            field_kind = "date" if kind == "segmented" and text[s:e].count("/") in (1, 2) else self.kind_for(label)
            self.add(Area(field_kind, label, slot, {"type": "span", "start": s, "end": e, "shape": kind},
                          context=self.context_for(slot)))
            made += 1
            prev_end = e
        return made

    def next_block(self, slot):
        parent = slot.parent
        pool = parent.children if parent is not None else [x for x in self.index.roots if x.part == slot.part]
        later = [x for x in pool if x.kind in ("p", "tbl") and x.seq > slot.seq]
        for x in later:
            if x.kind == "p" and not self.text(x.el).strip():
                continue
            return x
        return None

    def answered_beside(self, slot) -> bool:
        """A label that is a whole table cell is answered by the cell beside it (empty) or describes printed
        content beside it; either way nothing goes after its colon. A neighbour that is itself a label keeps it."""
        cell = self.host_cell(slot)
        if cell is None or slot.parent is not cell:
            return False
        paras = [x for x in cell.children if x.kind == "p" and self.text(x.el).strip()]
        if len(paras) != 1 or paras[0] is not slot:
            return False
        right = [c for c in self.grid(cell.parent).get(cell.info["row"], []) if c.info["col"] > cell.info["col"]
                 and c.info["vmerge"] != "continue"]
        if not right:
            return False
        nxt = min(right, key=lambda c: c.info["col"])
        txt = self.cell_text(nxt)
        if self.is_empty_cell(nxt):
            return True
        return not re.search(r":\s*$|\?\s*$", txt) and not re.match(r"^\d{1,3}[.)]\s", txt)

    def is_label_of_next_lines(self, slot, text) -> bool:
        """'Findings:' heading a numbered list / a table / lines below rather than taking an answer after it."""
        if self.mapped_beside_label(slot) or self.mapped_below_label(slot) or self.answered_beside(slot):
            return True
        nb = self.next_block(slot)
        if nb is not None and nb.kind == "tbl" and text.strip().endswith(":") and len(text.split()) <= 6:
            return True
        sibs, idx = self.para_neighbours(slot)
        if idx is None or idx + 1 >= len(sibs):
            return False
        nxt = sibs[idx + 1]
        nt = self.text(nxt.el).strip()
        if not nt:
            return False
        return self.list_info(nxt.el) is not None and self.list_info(slot.el) is None and text.strip().endswith(":")

    # Protected signing structures: enumerate them without claiming a visual layout engine.
    def rule_protected_signing_areas(self):
        self.rule_signing_captions()
        self.rule_initial_boxes()

    def rule_signing_captions(self):
        for slot in [s for s in self.index.slots if s.kind == "p"]:
            text, pieces = self.ptext(slot.el)
            spans = self.blank_spans(text, pieces)
            if len(spans) < 2 or any(kind != "utab" for _, _, kind in spans) or text.strip():
                continue
            below = self.index.by_el.get(id(slot.el.getnext()))
            if below is None or below.kind != "p" or below.parent is not slot.parent:
                continue
            caption, _ = self.ptext(below.el)
            labels = [clean_label(x) for x in re.split(r"\t+", caption) if x.strip()]
            if not any(SIGNATURE.search(x) or INITIALS.search(x) for x in labels):
                continue
            reason = ("Protected signing block: its name, date and signature areas remain unchanged. "
                      "Complete them by hand after checking the actual signing act; ordinary notes do not authorize them.")
            paired = len(labels) == len(spans) and all(FIELDISH.search(x) for x in labels)
            if not paired:
                reason = ("Protected signing block: the captions do not identify every writing band unambiguously. "
                          "Review the original; these areas remain unchanged.")
            for n, (start, end, shape) in enumerate(spans):
                label = labels[n] if paired else "Signing area %d (caption unresolved)" % (n + 1)
                self.add(Area(self.kind_for(label) if paired else "text", label, slot,
                              {"type": "span", "start": start, "end": end, "shape": shape},
                              context=reason, protection=reason))
            self.claimed.add(id(below.el))
            self.protected_regions.add(below.id)
            self.notes.append(reason + " Location: " + slot.id)

    def rule_initial_boxes(self):
        WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
        WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
        A = "http://schemas.openxmlformats.org/drawingml/2006/main"
        affected = set()
        for c in [s for s in self.index.slots if s.kind == "tc"]:
            if self.cell_has_claim(c.el) or self.cell_text(c):
                continue
            rects = [x for x in c.el.iter("{%s}wsp" % WPS)
                     if x.find("{%s}txbx" % WPS) is None
                     and not any(a.tag == FALLBACK for a in x.iterancestors())
                     and any(a.tag == "{%s}anchor" % WP for a in x.iterancestors())
                     and any(g.get("prst") == "rect" for g in x.iter("{%s}prstGeom" % A))]
            if not rects:
                continue
            header = clean_label(self.column_header(c.parent, c.info["col"], c.info["row"]))
            label = self.row_label(c.parent, c.info["row"], c.info["col"])
            before = c.parent.el.getprevious()
            instruction = self.text(before) if before is not None and before.tag == q("w:p") else ""
            if not INITIALS.search(" ".join((header, label, instruction, self.context_for(c)))):
                self.notes.append("An unlabelled floating rectangle needs visual review at " + c.id)
                continue
            affected.add(c.parent)
            reason = ("Protected floating initials box: its visual question is unresolved because an anchor can sit "
                      "in another row. Check each box against the original; QuillMD leaves it unchanged.")
            for n, _ in enumerate(rects, 1):
                self.add(Area("initials", "Floating initials box %d (placement unresolved)" % n, c,
                              {"type": "none", "drawing": n}, context=reason, protection=reason))
            self.notes.append(reason + " Location: " + c.id + " (%d boxes)." % len(rects))
        for table in affected:
            # Empty cells in such a table can be spacers or sit under an overlapping
            # floating shape. They are not inferred as writable text destinations.
            # Inline blanks in printed statements are still parsed independently.
            for c in table.children:
                if c.kind == "tc" and self.is_empty_cell(c):
                    self.claimed.add(id(c.el))
                    self.protected_regions.add(c.id)
            self.notes.append("Blank cells in the floating-initials table are not assigned text answers; "
                              "check the original for additional areas. Location: " + table.id)
        if affected:
            self.floating_initials = True
            self.notes.append(FLOATING_INITIALS_REFUSAL)

    def rule_inline_initial_boxes(self):
        """Keep the previous non-floating drawn-box path; floating anchors need explicit review above."""
        WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
        WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
        for c in [s for s in self.index.slots if s.kind == "tc"]:
            if self.cell_has_claim(c.el) or self.cell_text(c):
                continue
            rects = [x for x in c.el.iter("{%s}wsp" % WPS) if x.find("{%s}txbx" % WPS) is None
                     and not any(a.tag == "{%s}anchor" % WP for a in x.iterancestors())]
            if not rects:
                continue
            header = clean_label(self.column_header(c.parent, c.info["col"], c.info["row"]))
            label = self.row_label(c.parent, c.info["row"], c.info["col"])
            if INITIALS.search(header + " " + label) or INITIALS.search(self.context_for(c)):
                self.add(Area("initials", label or header or "Initials", c, {"type": "none"}, context=self.context_for(c)))

    def capacity_for(self, area):
        """Characters an area can show without breaking the page: headers/footers, text boxes and narrow or
        fixed-height cells are bounded; body paragraphs and growing table cells are not (None)."""
        if area.kind not in ("text", "long_text", "date", "time"):
            return None
        slot = area.slot
        chain, s = [], slot
        while s is not None:
            chain.append(s)
            s = s.parent
        bound = None
        cell = self.host_cell(slot)
        if cell is not None:
            width = self.cell_twips(cell.parent, cell)
            tr = row_of(cell.el)
            trpr = tr.find(q("w:trPr")) if tr is not None else None
            h = trpr.find(q("w:trHeight")) if trpr is not None else None
            exact = h is not None and h.get(q("w:hRule")) == "exact"
            per_line = max(1, int(width / 110))
            if exact:
                lines = max(1, int(float(h.get(q("w:val")) or 240) / 240))
                bound = per_line * lines
            elif width < 1440:
                bound = per_line * 3
        if slot.part != "word/document.xml":
            bound = min(bound or 120, 120)
        if any(x.kind == "txbx" for x in chain):
            bound = min(bound or 120, 120)
        for ref in [slot] + [self.index.by_id.get(r["part"] + "#" + r["slot"])
                             for r in area.target.get("copies", [])]:
            native = ref.info.get("max_chars") if ref is not None and ref.kind == "ff" else None
            if native is not None and native > 0:
                bound = min(bound, native) if bound is not None else native
        return bound

    def surface_duplicates(self):
        """Identical label + context for different areas is never guessed between: each gets its position."""
        groups = {}
        for a in self.areas:
            groups.setdefault((a.label, a.context), []).append(a)
        for (label, context), group in groups.items():
            if len(group) < 2:
                continue
            for n, a in enumerate(group, 1):
                cell = self.host_cell(a.slot)
                para = self.host_paragraph(a.slot)
                if cell is not None:
                    where = "table row %d: %s" % (cell.info["row"] + 1, self.cell_text(cell)[:100])
                elif para is not None:
                    preceding = [s for s in self.index.slots if s.part == para.part and s.kind == "p" and s.seq < para.seq]
                    where = "line %d: %s" % (len(preceding) + 1, self.text(para.el)[:100])
                else:
                    where = "printed question %d: %s" % (n, a.label[:100])
                qualified = ("%s · occurrence %d of %d (%s)" % (context, n, len(group), where)).strip(" ·")
                a.context = qualified if a.complete_source else qualified[:300]
                a.note = "duplicate label: position shown"

    # 9. the same field in several header/footer parts (first page, even, default) is one answer ------------------
    def merge_header_copies(self):
        by_key = {}
        for a in self.areas:
            if a.slot.part == "word/document.xml":
                continue
            key = (a.kind, a.label, a.context, tuple(a.options), a.slot.path, json_dumps(a.target))
            by_key.setdefault(key, []).append(a)
        for key, group in by_key.items():
            if len(group) < 2:
                continue
            keep = group[0]
            for other in group[1:]:
                keep.protection = keep.protection or other.protection
                keep.target.setdefault("copies", []).append({"part": other.slot.part, "slot": other.slot.path,
                                                             "fingerprint": fingerprint(other.slot.el)})
                self.areas.remove(other)


def json_dumps(value):
    import json
    return json.dumps(value, sort_keys=True)


def merge_spans(spans):
    """Sort, drop spans nested in or overlapping an earlier one (the first, widest reading wins)."""
    out = []
    for s, e, kind in sorted(spans, key=lambda x: (x[0], -(x[1] - x[0]))):
        if out and s < out[-1][1]:
            continue
        out.append((s, e, kind))
    return out


# ─── public: inspect ───────────────────────────────────────────────────────────────────────────────────────────────

FIELD_KINDS = {"text", "long_text", "date", "time", "choice", "multi_choice", "checkbox", "signature", "initials",
               "table_rows"}


def unique_options(options) -> list:
    """Option labels the option reader can tell apart: an option printed more than once keeps its words and gets
    ' (2)', ' (3)' in print order, so every printed option can be chosen (fill maps by position, and writes the
    printed words, never the suffix)."""
    taken = {str(o).strip().lower() for o in options}
    seen, out = set(), []
    for option in options:
        label = str(option)
        key = label.strip().lower()
        if key in seen:
            n = 2
            while ("%s (%d)" % (label.strip(), n)).lower() in taken:
                n += 1
            label = "%s (%d)" % (label.strip(), n)
            taken.add(label.lower())
        seen.add(label.strip().lower())
        out.append(label)
    return out


def printed_options(field) -> list:
    """The option words as printed on the form, by position (the labels may carry a repeat suffix)."""
    target = (field.get("locator") or {}).get("target") or {}
    return list(target.get("printed") or field.get("options") or [])


def area_to_field(n: int, area: Area) -> dict:
    target = dict(area.target)
    locator = {"contract": CONTRACT, "part": area.slot.part, "slot": area.slot.path, "target": target,
               "fingerprint": fingerprint(area.slot.el)}
    if area.extra_slots:
        locator["extra"] = [{"part": s.part, "slot": s.path, "fingerprint": fingerprint(s.el)} for s in area.extra_slots]
    field = {"key": "v3_%d" % n, "label": area.label or "Answer", "kind": area.kind, "context": area.context,
             "locator": locator}
    if area.options:
        # labels: the options as read, each whitespace run one space (a legacy dropdown keeps its entries raw)
        field["options"] = unique_options([" ".join(str(o).split()) for o in area.options])
        if field["options"] != list(area.options):
            target["printed"] = list(area.options)
    if area.capacity:
        field["max_chars"] = int(area.capacity)
    if area.protection:
        field["write_protected"] = True
        field["review_reason"] = area.protection
    if area.source_questions:
        field["source_questions"] = area.source_questions
    return field


MAX_SOURCE_INSTRUCTION_CHARS = 20000


def cell_instruction_source(index, field):
    loc = field.get("locator") or {}
    result = []
    for ref in [loc] + list((loc.get("target") or {}).get("copies", [])):
        slot = index.by_id.get(str(ref.get("part")) + "#" + str(ref.get("slot")))
        if slot is None or slot.kind != "tc":
            fail("The preserved cell instructions no longer identify an answer area.", "mapping_mismatch")
        text = "\n".join(text_of(p) for p in slot.el.findall(q("w:p"))).strip()
        if not text or len(text) > MAX_SOURCE_INSTRUCTION_CHARS:
            fail("The complete answer-cell instructions exceed the supported metadata bound.", "mapping_limit")
        result.append({"part": slot.part, "slot": slot.path, "fingerprint": fingerprint(slot.el), "text": text})
    return result


def mapped_fields(detector, areas):
    """Keep source evidence identical across ordinary and rendered inspection."""
    if len(areas) > MAX_FIELDS:
        fail("The form has more answer areas than one mapping can hold (%d)." % MAX_FIELDS, "too_many_fields")
    fields = [area_to_field(i + 1, a) for i, a in enumerate(areas)]
    for field in fields:
        annotate_printed(detector.index, field)
        if field["locator"]["target"]["type"] == "cell_append":
            field["source_instructions"] = cell_instruction_source(detector.index, field)
        elif field["locator"]["target"]["type"] == "ff_text" and field.get("write_protected"):
            refs = [field["locator"]] + field["locator"]["target"].get("copies", [])
            sources = []
            for ref in refs:
                slot = detector.index.by_id[ref["part"] + "#" + ref["slot"]]
                text = ff_literal_help(slot.el)
                if text:
                    if len(text) > MAX_SOURCE_INSTRUCTION_CHARS:
                        fail("The complete legacy field help exceeds the supported metadata bound.", "mapping_limit")
                    sources.append({"part": slot.part, "slot": slot.path,
                                    "fingerprint": fingerprint(slot.el), "text": text})
            if sources:
                field["source_instructions"] = sources
    source_policy.annotate(detector, fields)
    return fields


def inspect(data: bytes) -> dict:
    package = open_package(data)
    detector = Detector(package)
    areas, notes = detector.detect()
    fields = mapped_fields(detector, areas)
    return {"contract": CONTRACT, "fields": fields, "notes": notes,
            "layout_pending": len(detector.layout_candidates)}


# ─── fill ──────────────────────────────────────────────────────────────────────────────────────────────────────────

MARK_FONT = "Segoe UI Symbol"
SIGNING_KINDS = {"signature", "initials"}


def _el(tag, **attrs):
    el = etree.Element(q(tag))
    for k, v in attrs.items():
        el.set(q(k) if ":" in k else k, v)
    return el


def _text_nodes(text):
    """w:t / w:br / w:tab sequence for an answer (newlines -> breaks, tabs kept)."""
    out = []
    for n, line in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n")):
        if n:
            out.append(_el("w:br"))
        for k, token in enumerate(line.split("\t")):
            if k:
                out.append(_el("w:tab"))
            if token:
                t = _el("w:t")
                t.set(XML_SPACE, "preserve")
                t.text = token
                out.append(t)
    return out


def _answer_rpr(source_rpr, *, plain=True):
    """Run properties for answer text: the neighbour's font and size, black ink, no placeholder style; `plain`
    also drops bold/italic/caps a printed label carries."""
    rpr = etree.fromstring(etree.tostring(source_rpr)) if source_rpr is not None else _el("w:rPr")
    for tag in ("w:rStyle", "w:vanish", "w:webHidden", "w:highlight", "w:shd"):
        for x in rpr.findall(q(tag)):
            rpr.remove(x)
    if plain:
        for tag in ("w:b", "w:bCs", "w:i", "w:iCs", "w:caps", "w:smallCaps"):
            for x in rpr.findall(q(tag)):
                rpr.remove(x)
    for x in rpr.findall(q("w:color")):
        rpr.remove(x)
    color = _el("w:color")
    color.set(q("w:val"), "000000")
    _insert_rpr_child(rpr, color)
    return rpr


RPR_ORDER = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline", "shadow",
             "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern",
             "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs",
             "em", "lang", "eastAsianLayout", "specVanish", "oMath"]


def _insert_rpr_child(rpr, child):
    """Insert keeping the schema order of rPr children (Word rejects out-of-order properties)."""
    name = etree.QName(child).localname
    rank = RPR_ORDER.index(name) if name in RPR_ORDER else len(RPR_ORDER)
    for i, existing in enumerate(rpr):
        other = etree.QName(existing).localname if isinstance(existing.tag, str) else ""
        if other in RPR_ORDER and RPR_ORDER.index(other) > rank:
            rpr.insert(i, child)
            return
    rpr.append(child)


def _new_run(rpr, text):
    r = _el("w:r")
    if rpr is not None:
        r.append(rpr)
    for node in _text_nodes(text):
        r.append(node)
    return r


def _flowing(p):
    """Exact line spacing clips taller answer text: make it a minimum. Keeps everything else."""
    ppr = p.find(q("w:pPr"))
    if ppr is None:
        return
    sp = ppr.find(q("w:spacing"))
    if sp is not None and sp.get(q("w:lineRule")) == "exact":
        sp.set(q("w:lineRule"), "atLeast")


def _unclip_row(tc):
    tr = row_of(tc)
    if tr is None:
        return
    trpr = tr.find(q("w:trPr"))
    h = trpr.find(q("w:trHeight")) if trpr is not None else None
    if h is not None and h.get(q("w:hRule")) == "exact":
        h.set(q("w:hRule"), "atLeast")


def _split_run_before(run, node):
    """Move `node` and everything after it in `run` into a new run (same properties) right after `run`."""
    children = [c for c in run if c.tag != q("w:rPr")]
    if not children or node is children[0]:
        return
    twin = etree.Element(run.tag, dict(run.attrib))
    rpr = run.find(q("w:rPr"))
    if rpr is not None:
        twin.append(etree.fromstring(etree.tostring(rpr)))
    moving = children[children.index(node):]
    for c in moving:
        twin.append(c)
    run.addnext(twin)


def _split_at(p, pos):
    text, pieces = paragraph_text(p)
    for pc in pieces:
        if pc.run is None:
            continue
        if pc.kind == "t" and pc.node.tag == T and pc.start < pos < pc.end:
            k = pos - pc.start
            t = pc.node
            tail = etree.fromstring(etree.tostring(t))
            tail.text = (t.text or "")[k:]
            t.text = (t.text or "")[:k]
            t.set(XML_SPACE, "preserve")
            tail.set(XML_SPACE, "preserve")
            t.addnext(tail)
            _split_run_before(pc.run, tail)
            return
        if pc.start == pos and pc.kind in ("t", "tab", "sym", "br"):
            _split_run_before(pc.run, pc.node)
            return


def replace_range(p, start, end, answer, *, plain=True):
    """Replace paragraph text [start, end) (positions of paragraph_text) with `answer`. Runs are split at the
    boundaries so exactly the range is removed; the answer takes the properties of the first replaced run (or of
    the run before an insertion point). Nothing outside the range is touched."""
    text, pieces = paragraph_text(p)
    if not (0 <= start <= end <= len(text)):
        fail("A stored mapping position no longer matches the form.", "mapping_mismatch")
    if hyperlink_write(pieces, start, end):
        fail("This mapping would change a fixed hyperlink. Review the original and choose a separate answer area.",
             "protected_hyperlink")
    if any(pc.kind == "obj" and pc.start < end and pc.end > start for pc in pieces):
        fail("A stored mapping position overlaps a form control.", "mapping_mismatch")
    if start < end:
        _split_at(p, end)
    _split_at(p, start)
    text2, pieces = paragraph_text(p)
    if text2 != text:
        fail("The form's text changed while splitting runs.", "internal")
    inside = [pc for pc in pieces if start <= pc.start and pc.end <= end and pc.start < pc.end and pc.kind in ("t", "tab", "sym", "br")]
    if start < end and sum(pc.end - pc.start for pc in inside) != end - start:
        fail("A stored mapping range does not cover whole text.", "mapping_mismatch")
    if inside:
        src = inside[0].run.find(q("w:rPr"))
        new = _new_run(_answer_rpr(src, plain=plain), answer)
        inside[0].run.addprevious(new)
        nodes = {id(pc.node) for pc in inside}
        for run in dict.fromkeys(pc.run for pc in inside):
            for child in list(run):
                if id(child) in nodes:
                    run.remove(child)
            if all(c.tag == q("w:rPr") for c in run):
                run.getparent().remove(run)
    else:
        before = [pc for pc in pieces if pc.end <= start and pc.run is not None]
        if before:
            anchor = before[-1].run
            lead = "" if (not text[:start] or text[:start].endswith((" ", "\t", "\u00a0"))) else " "
            new = _new_run(_answer_rpr(anchor.find(q("w:rPr")), plain=plain), lead + answer)
            anchor.addnext(new)
        else:
            ppr = p.find(q("w:pPr"))
            mark = ppr.find(q("w:rPr")) if ppr is not None else None
            new = _new_run(_answer_rpr(_rpr_from_mark(mark), plain=plain), answer)
            if ppr is not None:
                ppr.addnext(new)
            else:
                p.insert(0, new)
    _flowing(p)
    return True


def _rpr_from_mark(mark):
    """The paragraph mark's run properties, usable on a run."""
    if mark is None:
        return None
    rpr = etree.fromstring(etree.tostring(mark))
    rpr.tag = q("w:rPr")
    for tag in ("w:ins", "w:del", "w:moveFrom", "w:moveTo"):
        for x in rpr.findall(q(tag)):
            rpr.remove(x)
    return rpr
# ─── writers ────────────────────────────────────────────────────────────────────────────────────────────────────

def _set_run_mark(run, mark):
    """Replace a run's visible content with a mark character in a font that has it."""
    for child in list(run):
        if child.tag != q("w:rPr"):
            run.remove(child)
    rpr = run.find(q("w:rPr"))
    if rpr is None:
        rpr = _el("w:rPr")
        run.insert(0, rpr)
    for x in rpr.findall(q("w:rFonts")):
        rpr.remove(x)
    fonts = _el("w:rFonts")
    for a in ("ascii", "hAnsi", "cs", "eastAsia"):
        fonts.set(q("w:" + a), MARK_FONT)
    _insert_rpr_child(rpr, fonts)
    t = _el("w:t")
    t.text = mark
    run.append(t)


def glyph_boxes(p):
    """[(piece, k, char)] for every printed glyph box (not a control) of paragraph p, in order: the numbering
    box_units gives glyph boxes, and the one every writer and reader of a glyph box uses."""
    text, pieces = paragraph_text(p)
    out = []
    for pc in pieces:
        if pc.kind == "obj":
            continue
        for k, ch in enumerate(piece_text(pc)):
            if ch in (BOX, CHECKED):
                out.append((pc, k, ch))
    return out


def box_pieces(p):
    """[(kind, node, n)] for EVERY box paragraph p shows, in the order its text shows them (paragraph_text: a checkbox
    control is one box): ('glyph', None, n) for its n-th printed glyph box (glyph_boxes' numbering), ('sdt', the
    control, None) for a checkbox content control, ('ff', the field's begin run, None) for a legacy checkbox."""
    _, pieces = paragraph_text(p)
    out, n = [], 0
    for pc in pieces:
        for ch in piece_text(pc):
            if ch not in (BOX, CHECKED):
                continue
            if pc.kind == "obj":
                out.append(("sdt" if pc.obj == "sdt_checkbox" else "ff", pc.node, None))
            else:
                out.append(("glyph", None, n))
                n += 1
    return out


def cell_boxes(tc):
    """[(kind, node)] for every box a table cell's paragraphs show, in order (box_pieces' kinds)."""
    return [(kind, node) for p in tc.iter(q("w:p")) for kind, node, _ in box_pieces(p)]


def box_region(el):
    """Where a box is read and checked: the table cell holding it (through content controls, never out of a text box),
    else its paragraph. `el` is a paragraph, a table cell or a checkbox control."""
    if el.tag == q("w:tc"):
        return el
    host = el if el.tag == q("w:p") else next(el.iterancestors(q("w:p")), None)
    if host is None:
        return el
    for anc in host.iterancestors():
        if anc.tag == TXBX:
            return host
        if anc.tag == q("w:tc"):
            return anc
    return host


def hidden_boxes(region) -> list:
    """⚠️ THE CHECKBOX CONTROLS A REGION HOLDS THAT ITS BOX READING DOES NOT SHOW: every checkbox control found by
    walking the region's whole subtree (checkbox_nodes) that box_pieces does not show. Not empty means the region's
    boxes cannot be accounted for - it is refused where it would be read, written or numbered, and read back as
    unread - so a ticked box nobody can see can never pass as the chosen one's neighbour (round 3 F1)."""
    if region.tag == q("w:tc"):
        nodes = checkbox_nodes(region, own=False)
        seen_nodes = [node for p in region.iter(q("w:p")) for _, node, _ in box_pieces(p) if node is not None]
    elif region.tag == q("w:p"):
        nodes = checkbox_nodes(region)
        seen_nodes = [node for _, node, _ in box_pieces(region) if node is not None]
    else:
        return checkbox_nodes(region)          # a control outside any paragraph: whatever it holds is not shown
    seen = {id(node) for node in seen_nodes}   # (seen_nodes keeps every proxy alive while its id is compared)
    return [node for node in nodes if id(node) not in seen]


def region_hidden(index, el) -> bool:
    """Whether the box region of `el` holds a checkbox its reading does not show (hidden_boxes), once per region for
    one package read: the index keeps the answer, and every region is an element the package keeps alive."""
    region = box_region(el)
    cache = index.__dict__.setdefault("_hidden", {})
    if id(region) not in cache:
        cache[id(region)] = bool(hidden_boxes(region))
    return cache[id(region)]


HIDDEN_BOX = ("This place holds a checkbox QuillMD cannot read in place (for example a checkbox inside another checkbox), "
              "so which box an answer means is not known and nothing there is filled.")


RADIO_CODES = (0x81, 0xF081, 0xA1, 0xF0A1)


def set_glyph(p, n, ticked):
    """Tick or untick the n-th glyph box of paragraph p. A radio circle becomes ◉ / ○ (both still read as a box, so
    the numbering of the other boxes never moves); any other box becomes ☒ / ☐, in a font that has it."""
    boxes = glyph_boxes(p)
    if n >= len(boxes):
        fail("A stored checkbox position no longer matches the form.", "mapping_mismatch")
    pc, k, ch = boxes[n]
    if hyperlink_run(pc.run):
        fail("This mapping would change a checkbox inside a fixed hyperlink.", "protected_hyperlink")
    if (ch == CHECKED) == bool(ticked):
        return False
    original = (pc.node.text or "")[k] if pc.kind == "t" else ""
    radio = original in ("○", "⃝", "◉") or (pc.kind == "t" and ord(original) in RADIO_CODES)
    mark = ("◉" if radio else "☒") if ticked else ("○" if radio else "☐")
    pos = pc.start + k
    # isolate this one character into its own run, then mark it
    if pc.kind == "sym":
        run = pc.run
        _split_run_before(run, pc.node)
        sym_run = pc.node.getparent()
        after = [c for c in sym_run if c.tag != q("w:rPr")]
        if len(after) > 1:
            _split_run_before(sym_run, after[1])
        _set_run_mark(sym_run, mark)
        return True
    _split_at(p, pos + 1)
    _split_at(p, pos)
    _, pieces2 = paragraph_text(p)
    target = next(x for x in pieces2 if x.start == pos and x.kind == "t")
    _set_run_mark(target.run, mark)
    return True


def tick_glyph(p, n):
    """Tick the n-th glyph box (not a control) of paragraph p."""
    return set_glyph(p, n, True)


def pin_glyph(p, n):
    """Isolate an original glyph leaf so later disjoint run splits cannot rename it."""
    boxes = glyph_boxes(p)
    if not 0 <= n < len(boxes):
        fail("A stored checkbox position no longer matches the form.", "mapping_mismatch")
    piece, offset, _ = boxes[n]
    if hyperlink_run(piece.run):
        fail("This mapping would change a checkbox inside a fixed hyperlink.", "protected_hyperlink")
    if piece.kind == "t":
        position = piece.start + offset
        _split_at(p, position + 1)
        _split_at(p, position)
        piece, _, _ = glyph_boxes(p)[n]
    return piece.node


def pinned_glyph_state(node):
    """Read a retained physical leaf, never its ordinal among newly inserted text."""
    p = next(node.iterancestors(q("w:p")), None)
    if p is None:
        return None
    found = [ch == CHECKED for piece, _, ch in glyph_boxes(p) if piece.node is node]
    return found[0] if len(found) == 1 else None


def element_identity_path(root, node):
    """Namespace-independent path to a retained leaf after all structural edits."""
    path = []
    while node is not root:
        parent = node.getparent()
        if parent is None:
            fail("An original checkbox is no longer in its document part.", "mapping_mismatch")
        path.append((node.tag, list(parent.findall(node.tag)).index(node)))
        node = parent
    return list(reversed(path))


def set_sdt_checkbox(sdt, ticked):
    """A checkbox content control: its checked state and the glyph its state names (checkedState/uncheckedState)."""
    if hyperlink_control(sdt):
        fail("This mapping would change a fixed hyperlink in a checkbox control.", "protected_hyperlink")
    pr = sdt.find(q("w:sdtPr"))
    cb = pr.find(q("w14:checkbox")) if pr is not None else None
    if cb is None:
        fail("A stored checkbox is no longer a checkbox control.", "mapping_mismatch")
    ch = cb.find(q("w14:checked"))
    if ch is None:
        ch = etree.Element(q("w14:checked"))
        cb.insert(0, ch)                         # schema order: checked, checkedState, uncheckedState
    ch.set(q("w14:val"), "1" if ticked else "0")
    state = cb.find(q("w14:checkedState" if ticked else "w14:uncheckedState"))
    code = (state.get(q("w14:val")) if state is not None else None) or ("2612" if ticked else "2610")
    font = (state.get(q("w14:font")) if state is not None else None) or "MS Gothic"
    content = sdt.find(q("w:sdtContent"))
    ts = list(content.iter(T)) if content is not None else []
    if ts:
        ts[0].text = chr(int(code, 16))
        run = ts[0].getparent()
        rpr = run.find(q("w:rPr"))
        if rpr is None:
            rpr = _el("w:rPr")
            run.insert(0, rpr)
        for x in rpr.findall(q("w:rFonts")):
            rpr.remove(x)
        fonts = _el("w:rFonts")
        for a in ("ascii", "hAnsi", "cs", "eastAsia"):
            fonts.set(q("w:" + a), font)
        _insert_rpr_child(rpr, fonts)
        for extra in ts[1:]:
            extra.text = ""
    return True


def tick_sdt_checkbox(sdt):
    return set_sdt_checkbox(sdt, True)


def set_ff_checkbox(begin_run, ticked):
    """A legacy checkbox: an explicit checked state, which overrides the field's default."""
    data = begin_run.find(FLDCHAR).find(q("w:ffData"))
    cb = data.find(q("w:checkBox")) if data is not None else None
    if cb is None:
        fail("A stored checkbox is no longer a legacy checkbox.", "mapping_mismatch")
    for x in cb.findall(q("w:checked")):
        cb.remove(x)
    checked = _el("w:checked")
    checked.set(q("w:val"), "1" if ticked else "0")
    cb.append(checked)
    return True


def tick_ff_checkbox(begin_run):
    return set_ff_checkbox(begin_run, True)


#: A hand-written or typed tick in a box cell.
CELL_MARKS = ("X", "x", "✓", "✔", "√", "✗", "✘")


def set_cell_box(tc, ticked):
    """A box cell: the checkbox control it holds, set as that control; else its first printed glyph box when it has
    one; otherwise an X written in (or removed from) it.
    ⚠️ A CONTROL IS NEVER WRITTEN OVER: an X over a checkbox control refused every answer, and an untick left a
    printed tick the reader could not see. A cell holding a control beside another box is refused: which box its
    answer means is not known."""
    if hidden_boxes(tc):
        fail(HIDDEN_BOX, "unsupported_layout")
    boxes = cell_boxes(tc)
    if any(kind != "glyph" for kind, _ in boxes):
        if len(boxes) != 1:
            fail("A table cell holds a checkbox control beside another box, so which box its answer means is not known.",
                 "unsupported_layout")
        kind, node = boxes[0]
        return set_sdt_checkbox(node, ticked) if kind == "sdt" else set_ff_checkbox(node, ticked)
    for p in tc.iter(q("w:p")):
        if glyph_boxes(p):
            return set_glyph(p, 0, ticked)
    shown = text_of(tc).strip()
    if ticked:
        return False if shown in CELL_MARKS else write_cell(tc, "X")
    if shown in CELL_MARKS:
        for t in tc.iter(T):
            if (t.text or "").strip() in CELL_MARKS:
                t.text = ""
        return True
    return False


def _field_result_runs(begin_run):
    """Runs between a field's 'separate' and 'end' at the same nesting level (the visible result)."""
    runs, depth, state = [], 0, "instr"
    node = begin_run
    while True:
        node = node.getnext()
        if node is None:
            break
        if node.tag != R:
            continue
        fc = node.find(FLDCHAR)
        if fc is not None:
            kind = fc.get(q("w:fldCharType"))
            if kind == "begin":
                depth += 1
            elif kind == "end":
                if depth == 0:
                    return runs, node
                depth -= 1
            elif kind == "separate" and depth == 0:
                state = "result"
            continue
        if state == "result" and depth == 0:
            runs.append(node)
    fail("A form field is not closed in its paragraph.", "unsupported_layout")


def ff_literal_help(begin_run):
    data = begin_run.find(FLDCHAR).find(q("w:ffData"))
    return "\n".join(node.get(q("w:val")) or "" for tag in ("w:statusText", "w:helpText")
                     for node in data.findall(q(tag)) if node.get(q("w:type")) == "text")


def ff_text_protection(begin_run):
    data = begin_run.find(FLDCHAR).find(q("w:ffData"))
    if data.find(q("w:textInput")) is None:
        return ""
    info = ff_info(data)
    if info["max_chars"] == -1:
        return "This legacy input has an unsupported native maximum length. Its original value remains unchanged."
    default = data.find(q("w:textInput") + "/" + q("w:default"))
    paragraph = next(begin_run.iterancestors(q("w:p")), None)
    if (info["max_chars"] != 1 or info.get("name") or info.get("input_type") != "regular" or
            default is None or (default.get(q("w:val")) or "").strip() or not ff_literal_help(begin_run).strip() or
            paragraph is None or text_of(paragraph).strip() or next(paragraph.iterancestors(q("w:tc")), None) is not None):
        return ""
    runs, end = _field_result_runs(begin_run)
    if not runs or any(text_of(r).strip() for r in runs):
        return ""
    for run in [begin_run] + _siblings_between(begin_run, end) + [end]:
        if run.tag != R:
            return ""
        for tag in ("w:sz", "w:szCs"):
            size = run.find(q("w:rPr") + "/" + q(tag))
            if size is None or size.get(q("w:val")) not in ("1", "2"):
                return ""
    return ("This tiny blank legacy control carries source guidance in its help text. "
            "It remains protected, with its original value, help and navigation intact.")


def write_ff_text(begin_run, answer):
    reason = ff_text_protection(begin_run)
    if reason:
        fail(reason, "protected_source_guidance")
    data = begin_run.find(FLDCHAR).find(q("w:ffData"))
    limit = ff_text_limit(data)
    if limit is not None and len(answer) > limit:
        fail("This legacy input permits at most %d characters. Nothing was cut or written." % limit, "answer_too_long")
    runs, end = _field_result_runs(begin_run)
    src = runs[0].find(q("w:rPr")) if runs else begin_run.find(q("w:rPr"))
    for r in runs:
        r.getparent().remove(r)
    if not any(n.find(FLDCHAR) is not None and n.find(FLDCHAR).get(q("w:fldCharType")) == "separate"
               for n in _siblings_between(begin_run, end)):
        sep = _el("w:r")
        fc = _el("w:fldChar")
        fc.set(q("w:fldCharType"), "separate")
        sep.append(fc)
        end.addprevious(sep)
    end.addprevious(_new_run(_answer_rpr(src, plain=False), answer))
    return True


def _siblings_between(a, b):
    out, node = [], a.getnext()
    while node is not None and node is not b:
        out.append(node)
        node = node.getnext()
    return out


def write_ff_dropdown(begin_run, answer, occurrence=0):
    """Select the `occurrence`-th list entry printed as `answer` (0 = its first printing)."""
    data = begin_run.find(FLDCHAR).find(q("w:ffData"))
    dd = data.find(q("w:ddList"))
    entries = [x.get(q("w:val")) for x in dd.findall(q("w:listEntry"))]
    at = [i for i, entry in enumerate(entries) if entry == answer]
    if len(at) <= occurrence:
        fail("The answer is not one of the dropdown's options.", "invalid_answer")
    for x in dd.findall(q("w:result")):
        dd.remove(x)
    res = _el("w:result")
    res.set(q("w:val"), str(at[occurrence]))
    dd.insert(0, res)
    return True


def wraps_structure(content) -> bool:
    """True when a content control's content holds other controls, fields, tables or drawings."""
    for tag in ("w:sdt", "w:fldChar", "w:fldSimple", "w:tbl", "w:tr", "w:tc", "w:drawing", "w:pict", "w:object", "w:txbxContent"):
        if content.find(".//" + q(tag)) is not None:
            return True
    return False


def write_sdt_text(sdt, answer):
    content_now = sdt.find(q("w:sdtContent"))
    if hyperlink_control(sdt):
        fail("This mapping would change a fixed hyperlink in a content control. Review the original answer area.",
             "protected_hyperlink")
    if content_now is not None and wraps_structure(content_now):
        fail("This content control contains other form parts and cannot take a text answer.", "unsupported_layout")
    pr = sdt.find(q("w:sdtPr"))
    if pr is not None:
        for x in pr.findall(q("w:showingPlcHdr")):
            pr.remove(x)
        lock = pr.find(q("w:lock"))
        if lock is not None and (lock.get(q("w:val")) or "") in ("contentLocked", "sdtContentLocked"):
            fail("A locked content control cannot take an answer.", "unsupported_layout")
    content = sdt.find(q("w:sdtContent"))
    if content is None:
        content = etree.SubElement(sdt, q("w:sdtContent"))
    first_run = next(content.iter(R), None)
    src = first_run.find(q("w:rPr")) if first_run is not None else (pr.find(q("w:rPr")) if pr is not None else None)
    paras = content.findall(q("w:p"))
    rows_or_cells = content.findall(q("w:tr")) + content.findall(q("w:tc"))
    if rows_or_cells:
        fail("A content control around table rows cannot take a text answer.", "unsupported_layout")
    if paras:                                  # block-level control: first paragraph takes the answer
        p0 = paras[0]
        for r in [c for c in p0 if c.tag in (R, q("w:hyperlink"), q("w:fldSimple"))]:
            p0.remove(r)
        p0.append(_new_run(_answer_rpr(src, plain=False), answer))
        for extra in paras[1:]:
            content.remove(extra)
        _flowing(p0)
    else:
        for c in list(content):
            content.remove(c)
        content.append(_new_run(_answer_rpr(src, plain=False), answer))
    return True


def write_cell(tc, answer, replace=False, whole=False, append=False):
    if whole and tc.find(".//" + q("w:hyperlink")) is not None:
        fail("This mapping would remove a fixed hyperlink from its cell. Review the original answer area.",
             "protected_hyperlink")
    paras = tc.findall(q("w:p"))
    if not paras:
        paras = [etree.SubElement(tc, q("w:p"))]
    p0 = paras[0]
    if whole or append:
        # Colour identifies a possible prompt, never authority to delete it.
        # Old all=True mappings retain their identity but preserve source too.
        if wraps_structure(tc):
            fail("The instruction cell contains another form structure.", "unsupported_layout")
        paragraph = etree.SubElement(tc, q("w:p"))
        source_run = next(p0.iter(R), None)
        props = source_run.find(q("w:rPr")) if source_run is not None else None
        paragraph.append(_new_run(_answer_rpr(props), answer))
        _unclip_row(tc)
        return True
    text, pieces = paragraph_text(p0)
    if replace or text.strip():
        for p in paras[1:]:
            if not text_of(p).strip():
                continue
            fail("A stored answer cell holds more than one line of printed text.", "mapping_mismatch")
        replace_range(p0, 0, len(text), answer) if text else replace_range(p0, 0, 0, answer)
    else:
        replace_range(p0, 0, 0, answer)
    _unclip_row(tc)
    return True


def option_word_match(text, option, occurrence=0):
    """The `occurrence`-th printing of an option word in a paragraph's text (0 = the first), or None."""
    found = list(re.finditer(r"(?<![A-Za-z0-9])" + re.escape(option.strip()) + r"(?![A-Za-z0-9])", text))
    if len(found) > occurrence:
        return found[occurrence]
    return re.search(re.escape(clean_label(option)), text) if occurrence == 0 else None


def mark_option_text(p, option, occurrence=0):
    """Tick a printed option word ('YES<tab>NO', a lettered list item, a printed option cell): a ☒ goes right
    before it. `occurrence` picks a word printed more than once (0 = its first printing)."""
    text, pieces = paragraph_text(p)
    m = option_word_match(text, option, occurrence)
    if not m:
        fail("A stored option no longer matches the printed text.", "mapping_mismatch")
    at = m.start()
    if at < len(text) and not text[:at].strip():
        at = len(text[:at])
    replace_range(p, at, at, "☒ ", plain=False)
    return True


def option_position(options, value):
    """THE option reader (core/v3_mapping.option_for calls this one): the index of the one stored option label equal
    to `value` after trimming, ignoring case (str.lower) - nothing else. None when no label or more than one matches.
    ⚠️ Never clean_label: it made 'Lt. knee' name 'Rt. knee' (the first hit), so the left knee reviewed was the right
    knee exported."""
    wanted = str(value if value is not None else "").strip().lower()
    if not wanted:
        return None
    hits = [i for i, option in enumerate(options or []) if str(option).strip().lower() == wanted]
    return hits[0] if len(hits) == 1 else None


def _options_chosen(field, answer):
    """The option positions an answer selects, validated against the field's stored option labels."""
    options = field.get("options") or []
    kind = field["kind"]
    if kind == "checkbox":
        if answer in (True, "true", "True", "checked", "yes", "Yes") or (options and answer == options[0]):
            return [0]
        if answer in (False, "false", "False", "unchecked", "no", "No", ""):
            return []
        fail("A checkbox answer must be checked or unchecked.", "invalid_answer")
    chosen = answer if isinstance(answer, list) else [answer]
    if kind == "choice" and len(chosen) > 1:
        fail("Only one option can be chosen for this question.", "invalid_answer")
    out = []
    for value in chosen:
        position = option_position(options, value)
        if position is None:
            fail("The answer is not one of the printed options.", "invalid_answer")
        if position not in out:
            out.append(position)
    return out


def fill(data: bytes, fields: list, answers: dict, *, retained_layout=None) -> bytes:
    """Write answers into the original package. Every field's anchor is checked against its fingerprint before
    anything changes; signature and initials areas never take an automatic answer."""
    package = open_package(data)
    index = SlotIndex(package)
    source_detector = Detector(package, layout_proposal=True)
    source_detector.detect()
    layout_nodes = [(header, row) for header, row, _ in source_detector.layout_candidates]
    if layout_nodes and retained_layout is None and any(value not in (None, "", []) for value in answers.values()):
        fail("This form's tab-column answers require layout verification before export.",
             "layout_verification_required")
    protected = Detector(package)
    protected.rule_protected_signing_areas()
    protected.rule_question_boxes()
    protected_slots = ({area.slot.id for area in protected.areas if area.protection}
                       | protected.protected_regions | source_detector.protected_regions)
    legacy_protected = {slot.id: ff_text_protection(slot.el) for slot in index.slots if slot.kind == "ff"}
    legacy_protected = {identity: reason for identity, reason in legacy_protected.items() if reason}
    ops = []                                   # (paragraph_or_element, sort_position, callable)
    glyph_writes = {}                          # original source identity -> (paragraph, ordinal, state, part)
    relation_areas = None

    def resolve(part, path, fp):
        slot = index.by_id.get("%s#%s" % (part, path))
        if slot is None or (fp is not None and fingerprint(slot.el) != fp):
            fail("The stored mapping no longer matches this form. Review the mapping again.", "mapping_mismatch")
        return slot

    for field in fields:
        loc = field.get("locator") or {}
        if loc.get("contract") != CONTRACT:
            fail("The mapping is not a contract v3 mapping.", "mapping_mismatch")
        answer = answers.get(field["key"])
        if answer is None or answer == "" or answer == []:
            continue
        target = loc.get("target") or {}
        if target.get("type") == "cell_append":
            if field.get("source_instructions") != cell_instruction_source(index, field):
                fail("The complete printed answer-cell instructions changed. Review the mapping again.", "mapping_mismatch")
        if "answer_policy" in field:
            current_policy = {k: v for k, v in field.items() if k != "answer_policy"}
            source_policy.annotate(protected, [current_policy])
            if current_policy.get("answer_policy") != field["answer_policy"]:
                fail("The printed authorship or review requirement has changed. Review the mapping again.",
                     "mapping_mismatch")
        destinations = [loc] + list(loc.get("extra", [])) + list(target.get("copies", [])) + list(target.get("boxes", []))
        if target.get("type") == "paragraph_options":
            destinations.extend({"part": anchor.get("part"), "slot": path}
                                for anchor in [loc] + list(target.get("copies", []))
                                for path in target.get("paragraphs", []))
        if target.get("type") == "table_rows":
            destinations.append({"part": loc.get("part"), "slot": target.get("table")})
        locations = ["%s#%s" % (x.get("part"), x.get("slot")) for x in destinations]
        for identity, reason in legacy_protected.items():
            if any(location == identity or location.startswith(identity + "/") or identity.startswith(location + "/")
                   for location in locations):
                fail(reason, "protected_source_guidance")
        if field.get("write_protected") or any(location == s or location.startswith(s + "/") or s.startswith(location + "/")
                                               for location in locations for s in protected_slots):
            fail("This signing area is protected and remains unchanged. Review the original and complete it by hand.",
                 "protected_signing_area")
        if isinstance(answer, str) and len(answer) > MAX_ANSWER:
            fail("An answer is longer than the form can take.", "invalid_answer")
        if isinstance(answer, str) and field.get("max_chars") and len(answer) > int(field["max_chars"]):
            fail("The answer for \"%s\" is longer than that space on the form can show (%d characters). Shorten it "
                 "in review." % (field.get("label", "")[:60], int(field["max_chars"])), "answer_too_long")
        if field["kind"] in SIGNING_KINDS:
            fail("Signature and initials areas are signed by the clinician; they are never filled automatically.",
                 "invalid_answer")
        target = loc["target"]
        anchors = [resolve(loc["part"], loc["slot"], loc["fingerprint"])]
        relations = field.get("source_questions", [])
        if not isinstance(relations, list):
            fail("The related question mapping is invalid.", "invalid_mapping")
        for relation in relations:
            if not isinstance(relation, dict):
                fail("The related question mapping is invalid.", "invalid_mapping")
            if relation.get("relation") == "immediate_previous_question":
                refs = [relation.get("source"), relation.get("reference")]
            elif relation.get("relation") == "paragraph_list_answer" and isinstance(relation.get("descriptors"), list):
                instructions = relation.get("instructions", [])
                if not isinstance(instructions, list):
                    fail("The related question instructions are invalid.", "invalid_mapping")
                refs = [relation.get("source")] + relation["descriptors"] + instructions
            elif relation.get("relation") == "native_checkbox_history" and isinstance(relation.get("sources"), list):
                refs = relation["sources"]
            else:
                fail("The related question mapping is invalid.", "invalid_mapping")
            for ref in refs:
                if not isinstance(ref, dict) or not ref.get("fingerprint"):
                    fail("The related question source is missing.", "invalid_mapping")
                resolve(ref.get("part"), ref.get("slot"), ref["fingerprint"])
        if relations:
            if relation_areas is None:
                relation_areas = Detector(package).detect()[0]
            if not any(area.slot.id == anchors[0].id and area.target == target and area.source_questions == relations
                       and (not any(r.get("relation") == "native_checkbox_history" for r in relations)
                            or area.kind == field.get("kind") and area.options == field.get("options")
                            and area.label == field.get("label") and area.context == field.get("context"))
                       for area in relation_areas):
                fail("The related question no longer owns this answer destination. Review the mapping again.",
                     "mapping_mismatch")
        for extra in loc.get("extra", []):
            resolve(extra["part"], extra["slot"], extra["fingerprint"])
        for copy in target.get("copies", []):
            anchors.append(resolve(copy["part"], copy["slot"], copy["fingerprint"]))
        kind = target["type"]
        for anchor in anchors:
            part = anchor.part
            if kind == "span":
                s0, e0 = target["start"], target["end"]
                if target.get("shape") == "after_label":
                    e0 = s0
                ops.append((anchor.el, s0, lambda el=anchor.el, s0=s0, e0=e0, a=str(answer): replace_range(el, s0, e0, a), part))
            elif kind in ("cell", "cell_replace", "cell_append"):
                value = str(answer)
                if field["kind"] == "choice" and target.get("write") == "option_text":
                    value = printed_options(field)[_options_chosen(field, answer)[0]]
                ops.append((anchor.el, 0, lambda el=anchor.el, v=value, rep=(kind == "cell_replace"), whole=bool(target.get("all")), append=(kind == "cell_append"):
                            write_cell(el, v, rep, whole, append), part))
            elif kind == "paragraph":
                paras = [anchor] + [resolve(x["part"], x["slot"], x["fingerprint"]) for x in loc.get("extra", [])]
                lines = str(answer).replace("\r\n", "\n").split("\n")
                chunks = lines[:len(paras) - 1] + ["\n".join(lines[len(paras) - 1:])] if len(paras) > 1 else [str(answer)]
                for para, chunk in zip(paras, chunks):
                    if chunk:
                        ops.append((para.el, 0, lambda el=para.el, c=chunk: replace_range(el, 0, 0, c), part))
            elif kind in ("sdt_text", "sdt_choice"):
                value = str(answer)
                if kind == "sdt_choice" and anchor.info.get("type") == "dropDownList":
                    value = printed_options(field)[_options_chosen(field, answer)[0]]
                ops.append((anchor.el, 0, lambda el=anchor.el, v=value: write_sdt_text(el, v), part))
            elif kind == "ff_text":
                ops.append((anchor.el, 0, lambda el=anchor.el, v=str(answer): write_ff_text(el, v), part))
            elif kind == "ff_dropdown":
                i = _options_chosen(field, answer)[0]
                printed = printed_options(field)
                value, nth = printed[i], printed[:i].count(printed[i])
                ops.append((anchor.el, 0, lambda el=anchor.el, v=value, k=nth: write_ff_dropdown(el, v, k), part))
            elif kind == "checkboxes":
                # ⚠️ EVERY BOX OF THE GROUP IS SET TO THE ANSWER: the chosen ones ticked, every other one unticked
                # (a box the blank form printed ticked included). An unanswered field never gets here: it stays as
                # printed. A checkbox answered False is unticked.
                boxes = target["boxes"]
                chosen = _options_chosen(field, answer)
                for i, box in enumerate(boxes):
                    want = i in chosen
                    slot = index.by_id.get("%s#%s" % (box["part"], box["slot"]))
                    if slot is None:
                        fail("The stored mapping no longer matches this form. Review the mapping again.", "mapping_mismatch")
                    if box["kind"] in ("sdt", "ff", "glyph", "cell") and region_hidden(index, slot.el):
                        fail(HIDDEN_BOX, "unsupported_layout")
                    if box["kind"] == "sdt":
                        ops.append((slot.el, -1, lambda el=slot.el, w=want: set_sdt_checkbox(el, w), box["part"]))
                    elif box["kind"] == "ff":
                        ops.append((slot.el, -1, lambda el=slot.el, w=want: set_ff_checkbox(el, w), box["part"]))
                    elif box["kind"] == "glyph":
                        key = box_key(box)
                        if key in glyph_writes and glyph_writes[key][2] != want:
                            fail("Two answers request different states for one printed checkbox.", "mapping_mismatch")
                        glyph_writes[key] = (slot.el, box["glyph"], want, box["part"])
                    elif box["kind"] == "cell":
                        ops.append((slot.el, -1, lambda tc=slot.el, w=want: set_cell_box(tc, w), box["part"]))
                    elif box["kind"] == "cell_text" and want:
                        p0 = slot.el.find(q("w:p"))
                        printed = printed_options(field)
                        nth = sum(1 for j in range(i) if printed[j].strip() == printed[i].strip() and boxes[j]["slot"] == box["slot"])
                        ops.append((p0, 0, lambda el=p0, o=printed[i], k=nth: mark_option_text(el, o, k), box["part"]))
            elif kind == "paragraph_options":
                paths = target["paragraphs"]
                for i in _options_chosen(field, answer):
                    slot = index.by_id.get("%s#%s" % (anchor.part, paths[i]))
                    ops.append((slot.el, 0, lambda el=slot.el: replace_range(el, 0, 0, "☒ ", plain=False), part))
            elif kind == "text_options":
                printed = printed_options(field)
                for i in _options_chosen(field, answer):
                    nth = sum(1 for j in range(i) if printed[j].strip() == printed[i].strip())
                    ops.append((anchor.el, 0, lambda el=anchor.el, o=printed[i], k=nth: mark_option_text(el, o, k), part))
            elif kind == "table_rows":
                ops.append((anchor.el, 0, lambda f=field, a=answer: write_table_rows(index, f, a), part))
            else:
                fail("This answer area cannot be filled automatically.", "unsupported_layout")
    if protected.floating_initials and (ops or glyph_writes):
        fail(FLOATING_INITIALS_REFUSAL, "unqualified_floating_initials")
    # Checkbox state edits preserve source offsets. Resolve them before text can
    # insert new checkbox-looking characters, then retain the actual leaf nodes.
    changed = set()
    for p, n, want, part in glyph_writes.values():
        set_glyph(p, n, want)
        changed.add(part)
    pins = {key: (p, pin_glyph(p, n), want, part)
            for key, (p, n, want, part) in glyph_writes.items()}
    # position edits inside one element run from the end backwards; ticks (position -1) last
    ops.sort(key=lambda op: (id(op[0]), -op[1] if op[1] >= 0 else float("inf")))
    for _, _, apply, part in ops:
        apply()
        changed.add(part)
    glyph_readback = {}
    for key, (p, node, want, part) in pins.items():
        if (p.getroottree().getroot() is not package.tree(part)
                or next(node.iterancestors(q("w:p")), None) is not p):
            fail("An answer changed or removed an original printed checkbox.", "mapping_mismatch")
        glyph_readback[key] = {"part": part, "path": element_identity_path(package.tree(part), node)}
    out = package.write({part: package.tree(part) for part in changed}) if changed else data
    verify_options(out, fields, answers, glyph_readback=glyph_readback)
    if retained_layout is not None:
        for header, row, area in source_detector.layout_candidates:
            if any(slot.el.getroottree().getroot() is not package.tree(slot.part) for slot in (header, row)):
                fail("An answer removed a tab-column source paragraph.", "mapping_mismatch")
            retained_layout.append({"header": {"part": header.part,
                "path": element_identity_path(package.tree(header.part), header.el)},
                "row": {"part": row.part,
                "path": element_identity_path(package.tree(row.part), row.el)},
                "sequence": [{"part": ref["part"], "path": element_identity_path(package.tree(ref["part"]),
                              index.by_id[ref["part"] + "#" + ref["slot"]].el)}
                             for ref in area.target.get("column_sequence", {}).get("source", [])]})
    return out


# ─── option state: the blank form's printed state, and the read-back after filling ────────────────────────────────

DISPLAYED = ("sdt_choice", "ff_dropdown")


def _symbol_code(code):
    """A glyph's code point, a symbol font's private-use form (U+F0xx) read as the plain byte it stands for."""
    return code - 0xF000 if 0xF000 <= code <= 0xF0FF else code


def _state_code(cb, checked):
    """The glyph a checkbox control's own checkedState / uncheckedState names (☒ / ☐ when it names none)."""
    state = cb.find(q("w14:checkedState" if checked else "w14:uncheckedState"))
    try:
        return _symbol_code(int((state.get(q("w14:val")) if state is not None else None) or ("2612" if checked else "2610"), 16))
    except ValueError:
        return None


def _shown_code(sdt):
    """The one glyph a control's content displays, or None when it displays none or more than one."""
    content = sdt.find(q("w:sdtContent"))
    codes = []
    for node in content.iter(T, SYM) if content is not None else ():
        if any(a.tag == FALLBACK for a in node.iterancestors()):
            continue
        if node.tag == T:
            codes += [ord(c) for c in (node.text or "") if not c.isspace()]
        else:
            try:
                codes.append(int(node.get(q("w:char")) or "", 16))
            except ValueError:
                return None
    return _symbol_code(codes[0]) if len(codes) == 1 else None


def sdt_checkbox_state(sdt):
    """⚠️ A CHECKBOX CONTROL IS TICKED OR UNTICKED ONLY WHEN ITS w14:checked FLAG AND THE GLYPH IT DISPLAYS AGREE:
    True / False, or None (cannot be read) when the glyph is not the one the flag's own checkedState / uncheckedState
    names. The read-back trusted the flag alone, so a writer that cleared the flag but left ☒ passed as unticked."""
    pr = sdt.find(q("w:sdtPr"))
    cb = pr.find(q("w14:checkbox")) if pr is not None else None
    if cb is None:
        return None
    flag = cb.find(q("w14:checked"))
    checked = (flag.get(q("w14:val")) if flag is not None else "0") in ("1", "true")
    shown = _shown_code(sdt)
    return checked if shown is not None and shown == _state_code(cb, checked) else None


def ff_checkbox_state(begin_run):
    """A legacy checkbox's state (its explicit checked state, else its default), or None when it is not one."""
    fc = begin_run.find(FLDCHAR)
    data = fc.find(q("w:ffData")) if fc is not None else None
    info = ff_info(data) if data is not None else {}
    return info.get("checked") if info.get("field") == "FORMCHECKBOX" else None


def box_state(index, box):
    """Whether one box is ticked, read from the package: True, False, or None when it cannot be read."""
    slot = index.by_id.get("%s#%s" % (box["part"], box["slot"]))
    if slot is None:
        return None
    if box["kind"] in ("sdt", "ff", "glyph", "cell") and region_hidden(index, slot.el):
        return None                     # a checkbox the region's reading does not show: nothing there is read
    if box["kind"] == "sdt":
        return sdt_checkbox_state(slot.el)
    if box["kind"] == "ff":
        return ff_checkbox_state(slot.el)
    if box["kind"] == "glyph":
        boxes = glyph_boxes(slot.el)
        n = box.get("glyph", 0)
        return boxes[n][2] == CHECKED if n < len(boxes) else None
    if box["kind"] == "cell":
        # the control a box cell holds is read as that control (set_cell_box writes it so); beside another box: unread
        boxes = cell_boxes(slot.el)
        if any(kind != "glyph" for kind, _ in boxes):
            if len(boxes) != 1:
                return None
            kind, node = boxes[0]
            return sdt_checkbox_state(node) if kind == "sdt" else ff_checkbox_state(node)
        for p in slot.el.iter(q("w:p")):
            boxes = glyph_boxes(p)
            if boxes:
                return boxes[0][2] == CHECKED
        return text_of(slot.el).strip() in CELL_MARKS
    return None


def option_word_marked(p, word, occurrence):
    """Whether a printed option word carries a ☒ right before it; None when the word is not printed there."""
    text = paragraph_text(p)[0]
    m = option_word_match(text, word, occurrence)
    return None if m is None else text[:m.start()].rstrip().endswith(CHECKED)


def displayed_option(index, field):
    """The option position a dropdown (or an option-text cell) shows, or None: for a legacy dropdown the selected
    entry at its printing; otherwise the first option whose printed words equal the shown text."""
    loc = field["locator"]
    target = loc["target"]
    slot = index.by_id.get("%s#%s" % (loc["part"], loc["slot"]))
    if slot is None:
        return None
    printed = printed_options(field)
    if target["type"] == "ff_dropdown":
        data = slot.el.find(FLDCHAR).find(q("w:ffData"))
        dd = data.find(q("w:ddList")) if data is not None else None
        if dd is None:
            return None
        entries = [x.get(q("w:val")) for x in dd.findall(q("w:listEntry"))]
        # the entry Word shows: w:result, else w:default, else the first
        res = dd.find(q("w:result"))
        res = res if res is not None else dd.find(q("w:default"))
        at = int(res.get(q("w:val")) or 0) if res is not None else 0
        if not 0 <= at < len(entries):
            return None
        nth = entries[:at].count(entries[at])
        hits = [i for i, word in enumerate(printed) if word == entries[at]]
        return hits[nth] if nth < len(hits) else None
    shown = displayed_words(slot, target, field["locator"].get("fingerprint"))
    return next((i for i, word in enumerate(printed) if str(word).strip() == shown), None) if shown else None


def appended_cell_value(cell, source_fingerprint):
    """Read only an appended paragraph whose complete preceding cell is unchanged."""
    if not source_fingerprint or wraps_structure(cell):
        return None
    paragraphs = cell.findall(q("w:p"))
    if len(paragraphs) < 2:
        return None
    # Retain all in-scope namespaces: deepcopy drops unused ancestor bindings,
    # whereas the stored fingerprint covers their canonical representation.
    original = etree.fromstring(etree.tostring(cell))
    original.remove(original.findall(q("w:p"))[-1])
    return text_of(paragraphs[-1]).strip() if fingerprint(original) == source_fingerprint else None


def displayed_words(slot, target, source_fingerprint=None):
    """The words a dropdown content control (placeholder excluded) or an option-text cell shows."""
    if target["type"] == "sdt_choice":
        if sdt_info(slot.el)["placeholder"]:
            return ""
        content = slot.el.find(q("w:sdtContent"))
        return text_of(content).strip() if content is not None else ""
    if target.get("type") == "cell_append" or target.get("type") == "cell_replace" and target.get("all"):
        value = appended_cell_value(slot.el, source_fingerprint)
        return value if value is not None else text_of(slot.el).strip()
    return text_of(slot.el).strip()


def option_states(index, field):
    """Per option of a choice, multi_choice or checkbox field: True when the form shows it chosen (ticked, marked or
    displayed), False when not, None when it cannot be read. Glyph ordinals name the original source layout;
    export verification uses retained physical leaves after text insertions can add new box characters."""
    target = field["locator"]["target"]
    kind = target["type"]
    printed = printed_options(field)
    if kind == "checkboxes":
        states = []
        for i, box in enumerate(target["boxes"]):
            if box["kind"] == "cell_text":
                slot = index.by_id.get("%s#%s" % (box["part"], box["slot"]))
                p0 = slot.el.find(q("w:p")) if slot is not None else None
                nth = sum(1 for j in range(i) if printed[j].strip() == printed[i].strip()
                          and target["boxes"][j]["slot"] == box["slot"])
                states.append(option_word_marked(p0, printed[i], nth) if p0 is not None and i < len(printed) else None)
            else:
                states.append(box_state(index, box))
        return states
    if kind == "paragraph_options":
        part = field["locator"]["part"]
        states = []
        for path in target["paragraphs"]:
            slot = index.by_id.get("%s#%s" % (part, path))
            states.append(None if slot is None else paragraph_text(slot.el)[0].lstrip().startswith(CHECKED))
        return states
    if kind == "text_options":
        loc = field["locator"]
        slot = index.by_id.get("%s#%s" % (loc["part"], loc["slot"]))
        if slot is None:
            return [None] * len(printed)
        return [option_word_marked(slot.el, word, sum(1 for j in range(i) if printed[j].strip() == word.strip()))
                for i, word in enumerate(printed)]
    if kind in DISPLAYED or target.get("write") == "option_text":
        shown = displayed_option(index, field)
        return [i == shown for i in range(len(printed))]
    return []


def printed_ticked(index, field):
    """Positions the blank form itself shows chosen (a box printed ticked, a dropdown showing an option)."""
    if field.get("kind") not in ("choice", "multi_choice", "checkbox"):
        return []
    try:
        return [i for i, state in enumerate(option_states(index, field)) if state]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return []                       # an annotation for the review page; never a reason to refuse the upload


def constrained_placeholder(sdt):
    """A present AND true w:showingPlcHdr is a placeholder; malformed is unknown.

    ISO/IEC 29500 common boolean property, documented by Microsoft's
    Wordprocessing.ShowingPlaceholder / OnOffType reference. Presence alone
    must not erase a control whose explicit on/off value is false.
    """
    properties = sdt.findall(q("w:sdtPr"))
    if len(properties) > 1:
        return None
    pr = properties[0] if properties else None
    flags = pr.findall(q("w:showingPlcHdr")) if pr is not None else []
    if not flags:
        return False
    if len(flags) != 1:
        return None
    value = flags[0].get(q("w:val"))
    if value is None or value in ("1", "true", "on"):
        return True
    if value in ("0", "false", "off"):
        return False
    return None


def constrained_option_states(index, field):
    """Unlike an empty placeholder, an unrecognised displayed value is unknown."""
    target = field["locator"]["target"]
    if target.get("type") == "cell_append" or target.get("type") == "cell_replace" and target.get("all"):
        # Preserved ink can contain a real existing option. A newly appended
        # word does not make the old visible value cease to count.
        return [None] * len(printed_options(field))
    if target["type"] in DISPLAYED or target.get("write") == "option_text":
        loc = field["locator"]
        slot = index.by_id.get("%s#%s" % (loc["part"], loc["slot"]))
        if slot is None:
            return [None] * len(printed_options(field))
        if target["type"] == "sdt_choice":
            printed = printed_options(field)
            contents = slot.el.findall(q("w:sdtContent"))
            content = contents[0] if len(contents) == 1 else None
            placeholder = constrained_placeholder(slot.el)
            if content is None or wraps_structure(content) or placeholder is None:
                return [None] * len(printed)
            shown = "" if placeholder else text_of(content).strip()
            if not shown:
                return [False] * len(printed)
            matches = [i for i, word in enumerate(printed) if str(word).strip() == shown]
            return [i == matches[0] for i in range(len(printed))] if len(matches) == 1 else [None] * len(printed)
        try:
            position = displayed_option(index, field)
            if position is None and (target["type"] == "ff_dropdown" or displayed_words(slot, target, loc.get("fingerprint"))):
                return [None] * len(printed_options(field))
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return [None] * len(printed_options(field))
    return option_states(index, field)


def constrained_scalar_value(original, final, field, written):
    """Visible value in a bounded scalar destination, or None when it is ambiguous.

    Read native controls and whole plain cells/paragraphs directly. A span is
    readable only while its original surrounding text still identifies it;
    simultaneous neighbouring edits must never move the read into another value.
    """
    loc = field["locator"]; target = loc["target"]
    identity = "%s#%s" % (loc["part"], loc["slot"])
    before, after = original.by_id.get(identity), final.by_id.get(identity)
    if before is None or after is None:
        return None
    kind = target["type"]
    if kind == "ff_text":
        try:
            runs, end = _field_result_runs(after.el)
        except V3Failure:
            return None
        between = _siblings_between(after.el, end)
        if any(text_of(node).strip() for node in [after.el, end] + [
                node for node in between if node.find(FLDCHAR) is not None]):
            return None
        if any(node.tag != R and text_of(node).strip() or
               any(fc.get(q("w:fldCharType")) == "begin" for fc in node.iter(FLDCHAR)) or
               wraps_structure(node) and node.find(FLDCHAR) is None for node in between):
            return None
        separators = [i for i, node in enumerate(between) for fc in node.iter(FLDCHAR)
                      if fc.get(q("w:fldCharType")) == "separate"]
        # No/duplicate separator is an unresolved result boundary, not an
        # empty value. Visible XML text before the separator is ambiguous too,
        # including text a writer could retain while adding a missing marker.
        if len(separators) != 1 or any(text_of(node).strip() for node in between[:separators[0]]):
            return None
        value = "".join(text_of(run) for run in runs)
        # A nonempty default without a visible result is not evidence of an
        # empty field. Word may materialize that default; require explicit text.
        default = after.el.find("%s/%s/%s/%s" % (FLDCHAR, q("w:ffData"), q("w:textInput"), q("w:default")))
        if not value.strip() and default is not None and (default.get(q("w:val")) or "").strip():
            return None
    elif kind == "sdt_text":
        contents = after.el.findall(q("w:sdtContent"))
        content = contents[0] if len(contents) == 1 else None
        placeholder = constrained_placeholder(after.el)
        if content is None or wraps_structure(content) or placeholder is None:
            return None
        value = "" if placeholder else text_of(content)
    elif kind == "cell_append" or kind == "cell_replace" and target.get("all"):
        # The old cell remains visible and may contain an existing answer.
        # Colour and a successful append cannot prove a unique scalar value.
        return None
    elif kind in ("cell", "cell_replace", "paragraph"):
        anchors = [after]
        if kind == "paragraph":
            anchors += [final.by_id.get("%s#%s" % (ref["part"], ref["slot"])) for ref in loc.get("extra", [])]
        if any(anchor is None or wraps_structure(anchor.el) for anchor in anchors):
            return None
        paragraphs = [p for anchor in anchors for p in
                      (anchor.el.findall(q("w:p")) if kind in ("cell", "cell_replace") else [anchor.el])]
        value = "\n".join(text_of(p) for p in paragraphs)
    elif kind == "span":
        source, current = paragraph_text(before.el)[0], paragraph_text(after.el)[0]
        start, end = target.get("start"), target.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(source):
            return None
        if target.get("shape") == "after_label":
            end = start
        prefix, suffix = source[:start], source[end:]
        if ("\x00" in source or "\x00" in current or not current.startswith(prefix) or
                not current.endswith(suffix) or len(current) < len(prefix) + len(suffix)):
            return None
        value = current[len(prefix):len(current) - len(suffix) if suffix else len(current)]
    else:
        return None
    return "" if not written and is_blank_text(value) else value.strip()


def effective_values(data, fields, answers, *, _written=None):
    """The existing writer's actual resulting constrained values, without an export.

    Unanswered controls retain their original state. Validate their source
    anchors too: fill validates only fields it writes. Unknown states remain
    None; the clinical constraint reader must refuse to count them as false.
    """
    if (not isinstance(fields, list) or not 0 < len(fields) <= MAX_FIELDS
            or not isinstance(answers, dict) or any(not isinstance(f, dict) for f in fields)):
        fail("Constrained option mapping is invalid.", "invalid_mapping")
    keys = [f.get("key") for f in fields]
    if any(not isinstance(k, str) or not k for k in keys) or len(keys) != len(set(keys)) or not set(answers) <= set(keys):
        fail("Constrained option identities are invalid.", "invalid_mapping")
    index = SlotIndex(open_package(data))
    if _written is None:
        detector = Detector(index.package, layout_proposal=True)
        detector.detect()
        if detector.layout_candidates:
            fail("Constrained tab-column values require layout verification.", "layout_verification_required")
    for field in fields:
        loc = field.get("locator") or {}
        if field.get("kind") not in ("choice", "multi_choice", "checkbox", "text", "long_text", "date", "time") or loc.get("contract") != CONTRACT:
            fail("Constrained answer mapping is invalid.", "invalid_mapping")
        for ref in [loc] + list(loc.get("extra", [])) + list((loc.get("target") or {}).get("copies", [])):
            slot = index.by_id.get("%s#%s" % (ref.get("part"), ref.get("slot")))
            if slot is None or not ref.get("fingerprint") or fingerprint(slot.el) != ref["fingerprint"]:
                fail("The stored option mapping no longer matches the original.", "mapping_mismatch")
    # The isolated layout preparer may read its own just-written bytes. This is
    # never a request parameter; callers still reach fill's renderer guard.
    output = fill(data, fields, answers) if _written is None else _written
    final = SlotIndex(open_package(output))
    result = {}
    for field in fields:
        loc = field["locator"]; target = loc["target"]
        option = field["kind"] in ("choice", "multi_choice", "checkbox")
        state = constrained_option_states(final, field) if option else constrained_scalar_value(index, final, field, field["key"] in answers)
        for copy in target.get("copies", []):
            # These readers resolve their own copied anchor. Absolute checkbox
            # destinations do not establish an independent copy relationship.
            if option and target["type"] not in DISPLAYED + ("text_options", "paragraph_options") and target.get("write") != "option_text":
                state = [None] * max(1, len(field.get("options") or []))
                break
            variant = {**field, "locator": {**loc, **copy}}
            copied = constrained_option_states(final, variant) if option else constrained_scalar_value(index, final, variant, field["key"] in answers)
            if copied != state:
                state = [None] * max(1, len(field.get("options") or [])) if option else None
                break
        result[field["key"]] = state
    return result


def effective_options(data, fields, answers):
    """Compatibility entry point for the original constrained-state reader."""
    return effective_values(data, fields, answers)


def printed_unread(index, field):
    """Positions whose printed state cannot be read (a control whose flag and glyph disagree, a cell holding a control
    beside another box): the pages never call them unticked. An unreadable field is unread throughout."""
    if field.get("kind") not in ("choice", "multi_choice", "checkbox"):
        return []
    try:
        return [i for i, state in enumerate(option_states(index, field)) if state is None]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return list(range(len(field.get("options") or [])))


def annotate_printed(index, field):
    """The blank form's printed state on a field: `printed_ticked` and `printed_unread`, each only when not empty."""
    for name, read in (("printed_ticked", printed_ticked), ("printed_unread", printed_unread)):
        positions = read(index, field)
        if positions:
            field[name] = positions


def verify_options(data, fields, answers, *, glyph_readback):
    """⚠️ READ BACK EVERY ANSWERED OPTION FIELD FROM THE WRITTEN PACKAGE: the ticked (or shown) options must be
    exactly the chosen ones, or the export is refused. Belt and braces against any future disagreement between the
    reviewed answer and what a writer did."""
    index = SlotIndex(open_package(data))
    for field in fields:
        if field.get("kind") not in ("choice", "multi_choice", "checkbox"):
            continue
        answer = answers.get(field["key"])
        if answer is None or answer == "" or answer == []:
            continue
        chosen = set(_options_chosen(field, answer))
        target = field["locator"]["target"]
        try:
            if target["type"] == "ff_dropdown":
                ok = displayed_option(index, field) in chosen
            elif target["type"] in DISPLAYED or target.get("write") == "option_text":
                # A control shows words, not a position: an option printed twice reads the same at both printings.
                loc = field["locator"]
                slot = index.by_id.get("%s#%s" % (loc["part"], loc["slot"]))
                ok = slot is not None and len(chosen) == 1 and \
                    displayed_words(slot, target, loc.get("fingerprint")) == str(printed_options(field)[min(chosen)]).strip()
            else:
                states = option_states(index, field)
                if target["type"] == "checkboxes":
                    for i, box in enumerate(target["boxes"]):
                        if box["kind"] != "glyph":
                            continue
                        ref = glyph_readback[box_key(box)]
                        node = index.package.tree(ref["part"])
                        for tag, position in ref["path"]:
                            children = node.findall(tag)
                            if not 0 <= position < len(children):
                                node = None
                                break
                            node = children[position]
                        states[i] = pinned_glyph_state(node) if node is not None else None
                ok = bool(states) and all(state is (i in chosen) for i, state in enumerate(states))
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            ok = False                  # what cannot be read back is not exported
        if not ok:
            fail("After filling, the options shown for \"%s\" differ from the reviewed answer, so no export was made. "
                 "Report this form to QuillMD." % field.get("label", "")[:60], "fill_mismatch")


def write_table_rows(index, field, answer):
    """answer: a list of rows, each a list of cell texts in column order (as many as the mapped columns)."""
    if not isinstance(answer, list) or not all(isinstance(r, list) for r in answer):
        fail("A table answer must be a list of rows.", "invalid_answer")
    target = field["locator"]["target"]
    tbl = index.by_id.get("%s#%s" % (field["locator"]["part"], target["table"]))
    if tbl is None:
        fail("The stored mapping no longer matches this form.", "mapping_mismatch")
    trs = table_rows_of(tbl.el)
    rows = [trs[r] for r in target["rows"]]
    if len(answer) > 200:
        fail("Too many table rows.", "invalid_answer")
    while len(rows) < len(answer):
        clone = etree.fromstring(etree.tostring(rows[-1]))
        for t in clone.iter(T):
            t.text = ""
        rows[-1].addnext(clone)
        rows.append(clone)
    for tr, values in zip(rows, answer):
        # ⚠️ columns counted exactly as the index counts them (grid_before, row_cells_of, cell_span): counting from 0
        # over direct cells wrote a dose under Route in a row that skips a grid column
        col_of, col = {}, grid_before(tr)
        for tc in row_cells_of(tr):
            col_of[col] = tc
            col += cell_span(tc)
        for c, value in zip(target["columns"], values):
            if value and c in col_of:
                write_cell(col_of[c], str(value))
    return True


# ─── manual mapping: outline and locate ────────────────────────────────────────────────────────────────────────────

MANUAL_KINDS = {"text", "long_text", "date", "time", "checkbox", "choice", "signature", "initials"}


def box_key(box) -> str:
    """One box ref as text (kind, part, slot, and a glyph box's number): how the outline lists the boxes of a place,
    and how the pages find a field's box among them."""
    kind = box.get("kind", "")
    return "%s:%s#%s:%s" % (kind, box.get("part", ""), box.get("slot", ""), box.get("glyph") if kind == "glyph" else "")


def _paragraph_refs(index, pslot):
    """Box refs for every box paragraph slot `pslot` shows, in order (box_pieces); None for a control the index
    cannot address (one nested where no slot reaches it)."""
    refs = []
    for kind, node, n in box_pieces(pslot.el):
        if kind == "glyph":
            refs.append({"kind": "glyph", "part": pslot.part, "slot": pslot.path + "/glyphs", "glyph": n})
            continue
        control = index.by_el.get(id(node))
        refs.append({"kind": kind, "part": control.part, "slot": control.path}
                    if control is not None and control.kind == kind else None)
    return refs


def _boxes_shown(el) -> int:
    return sum(1 for ch in text_of(el) if ch in (BOX, CHECKED))


def place_box_refs(index, slot):
    """⚠️ THE BOXES A PLACE'S PREVIEW SHOWS, IN ITS ORDER - the numbering a clinician's box number counts in - as box
    refs the writers and the read-back understand: a printed glyph box, a checkbox content control and a legacy
    checkbox alike (None for a control no slot addresses). Counting glyph boxes only mapped box 2 'Left' of
    'Side: ☐ Right [control] Left ☐ Bilateral' to Bilateral, and D03's 'Red' to 'Other'.

    A paragraph's preview is its paragraph_text, which shows every checkbox control as one box, so its boxes are
    numbered as shown. A cell's preview is its text, which does not show a legacy checkbox and does show boxes nested
    inside the cell: a cell is numbered only when its preview shows exactly its own paragraphs' boxes, each control
    once; otherwise None, and the cell refuses a box number (its line, or the checkbox itself, is the place)."""
    boxy = slot.kind in ("p", "glyphs", "tc") or slot.info.get("type") == "checkbox" or slot.info.get("field") == "FORMCHECKBOX"
    if boxy and region_hidden(index, slot.el):
        return None                     # a checkbox its preview does not show: no number can name a box there
    if slot.kind in ("p", "glyphs"):
        return _paragraph_refs(index, slot if slot.kind == "p" else slot.parent)
    if slot.kind == "tc":
        refs = [ref for c in own_paragraph_slots(slot) for ref in _paragraph_refs(index, c)]
        for ref in refs:
            if ref is None or ref["kind"] == "ff":
                return None
            if ref["kind"] == "sdt":
                content = index.by_id["%s#%s" % (ref["part"], ref["slot"])].el.find(q("w:sdtContent"))
                if content is None or _boxes_shown(content) != 1:
                    return None
        return refs if _boxes_shown(slot.el) == len(refs) else None
    if slot.kind == "sdt":
        return [{"kind": "sdt", "part": slot.part, "slot": slot.path}] if slot.info.get("type") == "checkbox" else []
    if slot.kind == "ff":
        return [{"kind": "ff", "part": slot.part, "slot": slot.path}] if slot.info.get("field") == "FORMCHECKBOX" else []
    return []


#: ⚠️ A checkbox on a text answer area was accepted, confirmed, and then refused at every export (fill_mismatch).
NOT_A_BOX = ("That place is a %s, which is not a checkbox: choose a printed box or a checkbox control as the place, or "
             "add this answer as text.")
UNNUMBERED_CELL = ("This cell's preview does not show exactly its boxes (a legacy checkbox field, or boxes nested inside "
                   "the cell), so a box number cannot name one of them: choose the line inside the cell, or the checkbox "
                   "itself, as the place.")


def box_number(t, count):
    """The chosen box (0-based) of a place holding `count` printed boxes, or a refusal naming the count."""
    try:
        n = int(t.get("glyph") or 0)
    except (TypeError, ValueError):
        n = -1
    if count == 0:
        fail("A checkbox must be mapped to a printed box.", "invalid_mapping")
    if not 0 <= n < count:
        fail("That place has %d printed box%s; choose a box number from 1 to %d."
             % (count, "" if count == 1 else "es", count), "invalid_mapping")
    return n


def outline(data: bytes) -> dict:
    """Every place a clinician can map by hand: paragraphs, cells, content controls, legacy fields and glyph
    boxes, with a short preview and where they sit. Nothing is written."""
    package = open_package(data)
    detector = Detector(package)
    rows = []
    for s in detector.index.slots:
        if s.kind not in ("p", "tc", "sdt", "ff", "glyphs"):
            continue
        if s.kind == "p":
            preview = detector.ptext(s.el)[0]
        elif s.kind == "tc":
            preview = detector.cell_text(s)
        elif s.kind == "sdt":
            if s.info["type"] in ("docPartObj", "docPartList", "group", "picture"):
                continue
            content = s.el.find(q("w:sdtContent"))
            preview = detector.text(content, own=False) if content is not None else ""
        elif s.kind == "ff":
            preview = s.info.get("name") or s.info["field"]
        else:
            preview = detector.ptext(s.el)[0]
        refs = place_box_refs(detector.index, s)
        row = {"slot": s.id, "kind": s.kind, "part": "body" if s.part == "word/document.xml" else
               ("header" if "header" in s.part else "footer"),
               "preview": re.sub(r"\s+", " ", preview.replace("\x00", "[text field]")).strip()[:120],
               "context": detector.heading_before(s)[:120],
               "control": s.info.get("type") or s.info.get("field") or "", "boxes": len(refs or [])}
        if refs:
            row["box_keys"] = [box_key(ref) if ref is not None else None for ref in refs]
        if refs is None:
            row["unnumbered_boxes"] = True
        rows.append(row)
    return {"contract": CONTRACT, "slots": rows}


def locate(data: bytes, targets: list) -> list:
    """Clinician-chosen places -> v3 fields (origin 'manual'). A paragraph with printed text takes the answer
    after its text; an empty paragraph or cell takes it as its content; printed text is never replaced."""
    package = open_package(data)
    detector = Detector(package)
    out = []
    for n, t in enumerate(targets, 1):
        kind = t.get("kind")
        supplied_label, supplied_context = t.get("label") or "", t.get("context") or ""
        if not isinstance(supplied_label, str) or len(supplied_label) > MAX_MAPPING_LABEL:
            fail("An added question label must be at most %d characters; nothing was shortened." % MAX_MAPPING_LABEL, "invalid_mapping")
        if not isinstance(supplied_context, str) or len(supplied_context) > MAX_MAPPING_CONTEXT:
            fail("An added question section must be at most %d characters; nothing was shortened." % MAX_MAPPING_CONTEXT, "invalid_mapping")
        label = clean_label(supplied_label, limit=MAX_MAPPING_LABEL)
        if kind not in MANUAL_KINDS or not label:
            fail("Each added field needs a label and a supported kind.", "invalid_mapping")
        slot = detector.index.by_id.get(t.get("slot") or "")
        if slot is None:
            fail("The chosen place is not in this form.", "invalid_mapping")
        options = [option_text(str(o))[:200] for o in (t.get("options") or []) if option_text(str(o))]
        target = None
        if slot.kind == "glyphs" or slot.kind == "p" and kind == "checkbox":
            # ⚠️ THE CLINICIAN'S BOX, NOT THE FIRST ONE ('Smoker? ☐ Yes ☐ No' mapped as box 2 ticked Yes), counted among
            # EVERY box the preview shows - a checkbox control included - and written as whatever kind of box it is.
            refs = place_box_refs(detector.index, slot)
            if refs is None:
                fail(HIDDEN_BOX, "invalid_mapping")
            box = box_number(t, len(refs))
            if refs[box] is None:
                fail("Box %d of that place is a checkbox control QuillMD cannot address there, so it cannot be filled."
                     % (box + 1), "invalid_mapping")
            target, kind = {"type": "checkboxes", "boxes": [refs[box]]}, "checkbox"
            if slot.kind == "glyphs":
                slot = slot.parent
        elif slot.kind == "p":
            text = detector.ptext(slot.el)[0]
            if not text.strip(" \t\x00"):
                target = {"type": "paragraph"}
            else:
                end = len(text.rstrip())
                target = {"type": "span", "start": end, "end": end, "shape": "after_label"}
        elif slot.kind == "tc":
            refs = place_box_refs(detector.index, slot) if kind == "checkbox" else []
            if refs is None:
                fail(HIDDEN_BOX if region_hidden(detector.index, slot.el) else UNNUMBERED_CELL, "invalid_mapping")
            if refs:
                target = {"type": "checkboxes", "boxes": [refs[box_number(t, len(refs))]]}
            else:
                if kind == "checkbox":
                    box_number(t, 1)
                if not detector.is_empty_cell(slot):
                    fail("The chosen cell holds printed text. Choose the empty answer cell, or a paragraph to write after.",
                         "invalid_mapping")
                target = {"type": "checkboxes", "boxes": [{"kind": "cell", "part": slot.part, "slot": slot.path}]} \
                    if kind == "checkbox" else {"type": "cell"}
        elif slot.kind == "sdt":
            typ = slot.info["type"]
            content = slot.el.find(q("w:sdtContent"))
            if typ == "checkbox":
                box_number(t, 1)
                if place_box_refs(detector.index, slot) is None:
                    fail(HIDDEN_BOX, "invalid_mapping")
                target = {"type": "checkboxes", "boxes": [{"kind": "sdt", "part": slot.part, "slot": slot.path}]}
                kind = "checkbox"
            elif content is not None and wraps_structure(content):
                fail("That content control contains other form parts; choose one of them instead.", "invalid_mapping")
            elif typ in ("dropDownList", "comboBox"):
                target, kind = {"type": "sdt_choice"}, "choice"
                options = [o for o in slot.info["options"] if o and not PLACEHOLDER_TEXT.match(o)]
            elif kind == "checkbox":
                fail(NOT_A_BOX % "Word text control", "invalid_mapping")
            else:
                target = {"type": "sdt_text", "date": typ == "date"} if typ == "date" else {"type": "sdt_text"}
        elif slot.kind == "ff":
            field_kind = slot.info["field"]
            if field_kind == "FORMCHECKBOX":
                box_number(t, 1)
                if place_box_refs(detector.index, slot) is None:
                    fail(HIDDEN_BOX, "invalid_mapping")
                target, kind = {"type": "checkboxes", "boxes": [{"kind": "ff", "part": slot.part, "slot": slot.path}]}, "checkbox"
            elif field_kind == "FORMDROPDOWN":
                target, kind, options = {"type": "ff_dropdown"}, "choice", [o for o in slot.info.get("options", []) if o]
            elif kind == "checkbox":
                fail(NOT_A_BOX % "legacy text field", "invalid_mapping")
            else:
                target = {"type": "ff_text"}
        if target is None:
            fail("That place cannot take an answer.", "invalid_mapping")
        context = supplied_context or detector.context_for(slot, complete=True)
        if len(context) > MAX_MAPPING_CONTEXT:
            fail("The complete source section exceeds %d characters; nothing was shortened." % MAX_MAPPING_CONTEXT, "invalid_mapping")
        area = Area(kind, label, slot, target, context=clean_label(context, limit=MAX_MAPPING_CONTEXT),
                    options=options if kind in ("choice", "multi_choice") else ([label] if kind == "checkbox" else []))
        if slot.kind == "ff" and target["type"] == "ff_text":
            area.protection = ff_text_protection(slot.el)
        area.capacity = detector.capacity_for(area)
        field = area_to_field(n, area)
        field["key"] = "m3_%s" % hashlib.sha256(("%s|%s|%s" % (slot.id, json_dumps(target), label)).encode()).hexdigest()[:12]
        field["origin"] = "manual"
        annotate_printed(detector.index, field)
        out.append(field)
    return out
