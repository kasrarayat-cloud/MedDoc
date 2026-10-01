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
import unicodedata
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
#: A content control the original locks (contentLocked / sdtContentLocked): its content cannot take an answer, so
#: its area is protected and the control is a destination role (destination_roles).
LOCKED_CONTROL = "This content control is locked in the original form. It remains unchanged; review it by hand."
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
# Detector.cardinality uses it (through one_only) ONLY to keep a question single, never to allow more selections.
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
                        r"|\bone\s*(?:/|\s+or\s+)\s*both\b|\bany\s+number\b|\bat\s+least\s+(?:one|1)\b" + _NOT_A_MEASURE, re.I)


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
                            r"tier|appendix|annex|chapter|pages?|schedule|volume|number|no\.?|questions?|items?|q|box|options?)\s+"
                            r"(?:one|\d{1,3}[a-z]?|[ivx]{1,4})\b"
                            r"|\bone-\w+|\bmultiple\s+(?:sclerosis|myeloma|births?|pregnancy)\b"
                            # a printed date ("Revised: April 9, 2025"), never a count
                            r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?"
                            r"(?:\s*,\s*\d{4})?\b", re.I)
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
                          r"(?:\bmore\s+than\s+(?:one|1)\b" + _NOT_A_MEASURE + r"|\b(?:multiple|several)\b)", re.I)
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


# ── Selection cardinality: one structural, fail-closed rule (Detector.cardinality) ─────────────────────────────────
# A question accepts MORE THAN ONE answer only with explicit POSITIVE local evidence - a complete "all / any / as many
# as / one or more that apply" command (MANY_COMMAND) printed in its own label, its own source (the text printed after
# its boxes, its answer cell, its column header) or its own adjacent instruction, or a verified independent-event
# native-checkbox history relation (Detector.native_history_source) - and only when no one-only or limited-count
# language is printed in its reachable scope: its own texts, the instructions printed next to it, and every one-only
# instruction printed anywhere else in the form that no separate question owns, unless all it counts is form-filling
# mechanics (Detector.scope_limit, limit_reaches). Everything else keeps ONE choice:
# - a count phrase in a question ("one or both sides", "one or more joints", "at least one", "1+", "any number") and
#   any other wording that only suggests several answers ("Reason(s)", "which apply") keep one choice with a review
#   note, never several (R4-F1);
# - an instruction printed between two questions belongs to neither: it never grants the question below several
#   answers, and a limit there still governs both (R4-F5);
# - a printed answer count or bound is never permission: a range or bound over answers that are themselves counts or
#   scale points ("up to 3" over One / Two / Three, "circle 1-5" over 1 Never .. 5 Always) is a scale key and keeps
#   one choice (R4-F4); any other count of two or more ("select up to 3" of 17, "at least two", "exactly 2", "pick
#   one or two") is held for manual mapping, because one choice cannot record it and several cannot enforce it
#   (R4-F14);
# - a positive command beside a limit (in its own texts, next to it or elsewhere in the form), beside a count, or
#   beside a per-item instruction ("tick one box for each symptom present") is a conflict: held, never guessed.
# A rating-grid row, a coded response row and a column of boxes over labelled rows have their own structural rules
# (Detector.rule_tables, Detector.coded_kind).
_SELECT_VERB = r"(?:check|tick|choose|select|mark|circle|pick|indicate|cross|ring|record|list|give)"
_TICK_VERB = r"(?:check|tick|choose|select|mark|circle|pick|indicate|cross|ring)"
_ANSWER_NOUNS = r"(?:boxes|options|answers|items|categories|responses|choices|squares)"
_TICKED = r"(?:checked|ticked|chosen|selected|marked|circled|picked|indicated|crossed|ringed|recorded)"
_OF_THESE = r"(?:(?:of\s+)?(?:the\s+following|these|those|them|the)\s+)?"
# The complete positive commands. A count phrase alone is never one: "one or more" needs "that apply" or a selection
# verb acting on the answers ("select one or more options", "tick one or both"), never a question's own subject
# ("Pain in one or more joints?", "on one or both sides?").
MANY_COMMAND = re.compile(
    r"\b(?:all|any|any\s*/\s*all|all\s*/\s*any|any\s+or\s+all|one\s+or\s+more)\s+" + _OF_THESE +
    r"(?:" + _ANSWER_NOUNS + r"\s+)?(?:that|which)\s+(?:appl(?:y|ies|ied)|are\s+(?:applicable|relevant|appropriate))\b"
    r"|\bas\s+many\s+(?:" + _ANSWER_NOUNS + r"\s+)?as\s+(?:appl(?:y|ies|ied)|are\s+(?:applicable|relevant|appropriate)|"
    r"applicable|relevant|appropriate|necessary|needed|required)\b"
    r"|\ball\s+(?:applicable|relevant|appropriate)\s+" + _ANSWER_NOUNS + r"\b"
    r"|\b" + _TICK_VERB + r"\s+(?:one\s+or\s+more|one\s*(?:/|\s+or\s+)\s*both)\b"
    r"|\bmore\s+than\s+(?:one|1|a\s+single)(?:\s+(?:box|option|answer|item|category|response|choice))?\s+(?:may|can)\s+be\s+"
    + _TICKED + r"\b"
    r"|\byou\s+(?:may|can)\s+" + _SELECT_VERB + r"\s+more\s+than\s+(?:one|1)\b", re.I)
_NEGATION = re.compile(r"\b(?:no|not|never|cannot|nor)\b|n[’']t\b", re.I)
_COUNT_VALUE = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10}
_NUMBER = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)"
# Counts of answers, as (kind, numbers): an upper bound ("up to 3", "no more than two", "maximum 2"), a lower bound
# ("at least two", "minimum of 2"), an exact count ("exactly two", "tick 2", "2 answers"), a range after a selection
# verb ("tick 1-3", "select one to three") and a list ("pick one, two or three"). A scale key after "tick one" ("tick
# one - 1: never, 5: always") is none of them: its number is 1 and it names a scale point.
COUNT_BOUND = re.compile(
    r"\b(?P<upper>up\s+to|at\s+most|no\s+more\s+than|not\s+more\s+than|(?:a\s+)?max(?:imum)?\.?(?:\s+of)?)\s*" + _NUMBER
    + r"\b" + _NOT_A_MEASURE +
    r"|\b(?P<lower>at\s+least|(?:a\s+)?min(?:imum)?\.?(?:\s+of)?)\s*" + _NUMBER.replace("(", "(?P<low>", 1) + r"\b"
    + _NOT_A_MEASURE +
    r"|\b(?P<exact>exactly|" + _SELECT_VERB + r")\s+" + _NUMBER.replace("(", "(?P<num>", 1) + r"\b(?!\s*(?:[-–—/+]|or\b|to\b|,))"
    + _NOT_A_MEASURE +
    r"|\b" + _SELECT_VERB + r"\s+(?:(?:between|from)\s+)?" + _NUMBER.replace("(", "(?P<first>", 1)
    + r"\s*(?:[-–—]|to|and|or)\s*" + _NUMBER.replace("(", "(?P<last>", 1)
    # the upper bound ends the phrase or names the answers, as in MORE_THAN_ONE_AFTER: "tick one - two ticks void the
    # answer" is a warning and "tick 1-5 = always" a scale key, not ranges
    + r"\b(?=\s*(?:$|[):.;,]|(?:that|which|of|boxes|options|answers|items|responses|categories|choices)\b))" +
    r"|\b(?:one|1)\s*,\s*(?:(?:two|2)\s*,?\s*)?(?:or|and)\s+" + _NUMBER.replace("(", "(?P<listed>", 1) + r"\b"
    + _NOT_A_MEASURE, re.I)
# Answer-count nouns after a number ("2 answers", "three boxes") make an exact count.
COUNTED_ANSWERS = re.compile(r"(?<![\w/.:,\-–])" + _NUMBER + r"\s+(?:" + _ANSWER_NOUNS + r"|treatments|symptoms|"
                             r"diagnoses|reasons|types)\b", re.I)
# One-only and limited-count language (limit_language, fail-closed): a selection command with a limit
# (limited_selection), a negated count, a count with a recording verb or an answer noun ("Record 1 treatment.", "Only
# one type of leave may be recorded."), a bare count ("Just 1."), a one-only count with no verb at all ("Only one
# treatment per admission.", "A maximum of one treatment is permitted.", "Patients are allowed a single treatment.",
# "One treatment per patient.", R4-F7) and exclusivity ("These are mutually exclusive.", "Treatments may not be
# combined.", "neither"). What such a sentence LIMITS is read by limit_targets: printed elsewhere in the form it
# reaches every question (fail-closed) unless all it counts is form-filling mechanics that is not that question's own
# subject ("one letter per box", "one emergency contact" and "a single patient label" limit how the form is written,
# R4-F10; limit_reaches). A
# single-answer word alone ("focus on your worst headache", "the principal treatment") scopes its own question, never
# the form: the native-checkbox history reads it in its own heading chain and instructions (SINGLE_QUANTITY, R3-F7).
# ("document" as a noun is not an act: "Use one font throughout the document.")
LIMIT_ACT = re.compile(SELECTION_ACT.pattern + r"|\b(?:record(?:s|ed|ing)?|enter(?:s|ed|ing)?|document(?:ed|ing)|"
                       r"report(?:s|ed|ing)?|list(?:s|ed|ing)?|writ(?:e|es|ten|ing)|giv(?:e|es|en|ing)|stat(?:e|es|ed|ing)|"
                       r"put(?:s|ting)?|plac(?:e|es|ed|ing)|answer(?:s|ed|ing)?|ring(?:s|ed|ing)?|underlin(?:e|es|ed|ing)|"
                       r"highlight(?:s|ed|ing)?|nominat(?:e|es|ed|ing)|specif(?:y|ies|ied))\b", re.I)
LIMIT_COUNT = re.compile(r"\b(?:one|single|sole)\b" + _NOT_A_MEASURE + r"|" + NUMERAL_QUANTITY +
                         r"|\b" + _COUNT_WORD + r"\b" + _NOT_A_MEASURE, re.I)
ONE_COUNT = re.compile(r"\b(?:only|just|exactly)\s+(?:one|1|a\s+single)\b" + _NOT_A_MEASURE +
                       r"|\b(?:may|can|must|should|shall|will)\s+(?:only\s+)?(?:have|receive|get|take|be\s+(?:given|"
                       r"ticked|checked|selected|chosen|marked|recorded|entered|reported))\s+(?:only\s+)?(?:one|1|a\s+single)\b"
                       + _NOT_A_MEASURE +
                       r"|\b(?:limited|restricted|confined)\s+to\s+(?:only\s+)?(?:one|1|a\s+single)\b|\blimit\s+(?:of\s+)?(?:one|1)\b"
                       + _NOT_A_MEASURE +
                       r"|\b(?:one|1)\b" + _NOT_A_MEASURE + r"(?:\s+[^\W\d_][\w-]*){0,3}?\s+(?:only|per|each)\b"
                       r"|\b(?:single|sole)\b"
                       r"|\b(?:(?:a\s+)?max(?:imum)?\.?|at\s+most|(?:no|not)\s+more\s+than)\s*(?:of\s+)?(?:one|1)\b"
                       + _NOT_A_MEASURE, re.I)
EXCLUSIVE = re.compile(r"\bexclusiv\w*|\bneither\b"
                       r"|(?:\b(?:not|never|cannot)\b|n[’']t\b)\s+(?:be\s+)?(?:combined|used\s+together|"
                       r"(?:ticked|selected|chosen|marked|recorded)\s+together)\b", re.I)
BARE_COUNT = re.compile(r"\W*(?:please\s+)?(?:(?:just|only|exactly)\s+(?:one|1|a\s+single|single)|one|a\s+single|single)"
                        r"(?:\s+only)?\W*", re.I)
# "Tick one box for each symptom present", "one box per symptom": one box per ITEM, where the items may be several
# of this question's answers. One per question, row, line or statement is a one-only limit instead.
PER_ITEM = re.compile(r"\b(?:one|1|a)\s+(?:box|tick|mark|cross|answer|response)\s+(?:for\s+(?:each|every)|per|against\s+each)"
                      r"\s+(?!(?:question|row|line|statement|section|part|page|patient|person|form)s?\b)\w", re.I)
# Wording that only suggests several answers: a plural "(s)", "any / which / each of the ...", "that apply" without a
# complete command, "multiple", "several", and a count phrase that is not a command ("one or more", "one or both",
# "at least one", "1+", "any number", "more than one").
UNCERTAIN_MANY = re.compile(r"\(e?s\)|\b(?:any|all|which|each)\s+of\s+(?:the|these|those|them)\b|\b(?:that|which)\s+"
                            r"appl(?:y|ies)\b|\bmultiple\b|\bseveral\b|\b(?:one|1)\s*(?:or\s+more\b|\+)"
                            r"|\bone\s*(?:/|\s+or\s+)\s*both\b|\bat\s+least\s+(?:one|1)\b|\bany\s+number\b"
                            r"|\bmore\s+than\s+(?:one|1)\b|\b" + _TICK_VERB + r"\s+(?:any|all)\b", re.I)
# A sentence printed after a question's own boxes that names a wider reach than that question ("tick one box only
# for every question", "throughout this form", "for the question above") is not that question's own.
WIDER_REACH = re.compile(r"\b(?:throughout|every\s+\w+|each\s+(?:question|section|part|page|item|row|line)s?|"
                         r"all\s+(?:the\s+)?(?:questions|sections|parts|pages|items)|(?:this|the|whole|entire)\s+"
                         r"(?:form|document|questionnaire|section|part|page)|above|below|following|preceding|previous|"
                         r"next|other\s+questions?)\b", re.I)
# Answer and box nouns: a limit that counts them is about selection wherever it is printed.
SELECTION_NOUN = re.compile(r"(?:box|boxe|tick|cross|crosse|mark|answer|option|response|choice|categor(?:y|ie)|item|"
                            r"selection|square|type|kind|sort|entry|entrie)s?", re.I)
# Words that end a counted phrase ("one per patient", "only one may be ticked") or carry no subject of their own.
_FUNCTION_WORDS = frozenset(
    "a an the of per only may can could should must will would shall is are was were be been being at in on for to "
    "and or nor from if where which that with by as than then so it its this these those they them their there here "
    "each every any all more most no not never please do does did has have had allowed permitted".split())
# Words too general to tie a limit to one question's subject.
_GENERIC_WORDS = frozenset(
    "please patient patients details detail information section part form page other date name yes no none not any "
    "all each per used use given state record recorded list tick ticked box boxes question questions answer answers "
    "below above following only one single".split())


def _count(value):
    value = (value or "").lower()
    return int(value) if value.isdigit() else _COUNT_VALUE.get(value)


def _bound_value(m):
    """The largest count a COUNT_BOUND match names."""
    return max(_count(v) or 0 for v in m.groups()[1:] if v)


def _strip_counts(text, *, bounds):
    """The text without its positive commands and open counts, and (bounds=True) without the counted bounds of two
    or more that many_evidence judges against the question's own answers."""
    # Open counts first: "one, some or all that apply" is an open count before its "all that apply" is a command.
    for rx in (OPEN_COUNT, MANY_COMMAND):
        text = rx.sub(" ", text)
    if bounds:
        text = COUNT_BOUND.sub(lambda m: " " if _bound_value(m) >= 2 else m.group(0), text)
        text = COUNTED_ANSWERS.sub(lambda m: " " if (_count(m.group(1)) or 0) >= 2 else m.group(0), text)
    return text


def _clauses(text):
    """Sentences and their bracketed or dash-separated clauses: a command in "(tick all that apply)" is its own clause."""
    return [x for x in re.split(r"(?<=[.!?;:])\s+|[()\[\]]|\s[-–—]\s", text or "") if x.strip()]


def negated_command(text):
    """A negation before a positive command in the same clause: "Do not tick all that apply."."""
    for clause in _clauses(text):
        negation = _NEGATION.search(clause)
        if negation and MANY_COMMAND.search(clause, negation.end()):
            return True
    return False


def positive_command(text):
    """A complete positive command in `text` that no negation in its clause turns into a limit."""
    return any(MANY_COMMAND.search(clause) and not negated_command(clause) for clause in _clauses(text))


def limit_language(sentence, *, local=False):
    """One-only or limited-count language in one printed sentence (fail-closed): a selection command with a limit
    (limited_selection), a negated count, a count with a recording verb or an answer noun, a bare count, a one-only
    count with no verb, or exclusivity. Positive commands and open counts are never limits. A counted bound of two or
    more ("up to 3", "tick 1-3") is a limit wherever it is printed, except in the question's own label and
    instructions (local=True): many_evidence judges it there against the question's own answers. A complete
    one-box-per-row rule for a table is about that table's rows."""
    raw = (sentence or "").strip()
    if TABLE_ROWS.fullmatch(re.sub(r"[\s.!:;]+$", "", raw)):
        return False
    text = NOT_A_QUANTITY.sub(" ", raw)
    if NEGATED_MANY.search(text) or negated_command(text):
        return True
    text = _strip_counts(text, bounds=local)
    if limited_selection(text) or EXCLUSIVE.search(text) or BARE_COUNT.fullmatch(text) or ONE_COUNT.search(text):
        return True
    acts = LIMIT_ACT.search(text) or ANSWER_NOUN.search(text)
    return bool(acts and LIMIT_COUNT.search(text))


def _words(text):
    return re.findall(r"[^\W\d_][\w'’-]*", text or "")


def _stem(word):
    """A word's first five letters after its plural ending: "copies" and "copy", "therapies" and "therapy",
    "treatments" and "treatment" share a stem."""
    word = re.sub(r"[^a-z]", "", (word or "").lower())
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 4 and re.search(r"(?:[sxz]|[cs]h)es$", word):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word[:5]


def subject_stems(*texts):
    """The content-word stems of a question's own subject (its label, its answers, its heading chain)."""
    return {_stem(x) for t in texts for x in _words(t)
            if len(x) >= 3 and x.lower() not in _FUNCTION_WORDS and x.lower() not in _GENERIC_WORDS}


_COUNT_CUE = re.compile(r"\b(?:(?:only|just|exactly)\s+)?(?:a\s+)?(?:one|1|single|sole)\b" + _NOT_A_MEASURE +
                        r"|\bmore\s+than\s+(?:one|1)\b|\b(?:multiple|several)\b|" + NUMERAL_QUANTITY +
                        r"|\b" + _COUNT_WORD + r"\b" + _NOT_A_MEASURE, re.I)


def limit_targets(sentence):
    """What a one-only or limited-count sentence counts: "*" when it names nothing of its own ("Just 1.", "Tick one.",
    "These are mutually exclusive.", "record only the main one") or selects with a verb or a mark ("Only one letter
    may be circled."), else the phrases it counts ("one letter per box" ->
    (letter,), "Only one treatment per admission" -> (treatment,), "a single patient label" -> (patient, label)); for
    exclusivity, the words it names ("Treatments may not be combined" -> (Treatments,)). limit_reaches reads them."""
    text = _strip_counts(NOT_A_QUANTITY.sub(" ", sentence or ""), bounds=False)
    if SELECTION_ACT.search(SELECTION_ATTRIBUTION.sub(" ", text)):
        return "*"                  # a count with a selection verb or mark is about ticking, whatever it names
    phrases = []
    counted = False
    for m in _COUNT_CUE.finditer(text):
        counted = True
        rest = re.sub(r"^\s*(?:of\s+)?(?:the\s+|these\s+|those\s+)?", "", text[m.end():])
        words = []
        for token in re.findall(r"[^\W\d_][\w'’-]*|\S", rest)[:4]:
            if not re.match(r"[^\W\d_]", token) or token.lower() in _FUNCTION_WORDS:
                break
            words.append(token)
        if not words:
            return "*"
        phrases.append(tuple(words))
    if EXCLUSIVE.search(text) or not counted:
        named = [x for x in _words(EXCLUSIVE.sub(" ", text))
                 if x.lower() not in _FUNCTION_WORDS and x.lower() not in {"mutually", "combined", "together"}]
        if not named:
            return "*"
        phrases.append(tuple(named))
    return phrases or "*"


# Nouns of form-filling mechanics: a count of them limits how the form is written, never which answers are chosen
# ("one letter per box", "one emergency contact", "a single patient label", "one copy", "one page", R4-F10).
_MECHANICS_NOUNS = frozenset(
    "letter letters character characters digit digits capital capitals label labels sticker stickers barcode barcodes "
    "contact contacts copy copies page pages sheet sheets form forms signature signatures initial initials witness "
    "witnesses ink pen pens pencil pencils font fonts photo photos photograph photographs picture pictures attachment "
    "attachments envelope envelopes stamp stamps email emails address addresses phone phones telephone telephones "
    "visitor visitors".split())


def limit_reaches(targets, stems):
    """A limit printed elsewhere reaches a question unless everything it counts is form-filling mechanics (the head
    noun of each counted phrase is a _MECHANICS_NOUNS word) that is not that question's own subject (`stems`,
    subject_stems). Fail-closed: a limit that names nothing, counts answers or boxes, or counts any other thing
    ("treatment", "intervention", "type") may govern it."""
    if targets == "*":
        return True
    return any(phrase[-1].lower() not in _MECHANICS_NOUNS or any(_stem(x) in stems for x in phrase) for phrase in targets)


_OPTION_VALUE = {"none": 0, "zero": 0, "nil": 0, "once": 1, "twice": 2, **_COUNT_VALUE}


def scale_values(options):
    """The value each answer prints first when every answer is a count or a scale point ("One / Two / Three" ->
    1, 2, 3; "1 Never .. 5 Always" -> 1..5; "None / Once / Twice or more" -> 0, 1, 2), else None. A non-answer
    ("Unknown", "N/A", "REFUSED") is no point of the scale and is left out; any other answer ("Other") ends it."""
    values = []
    for option in options or []:
        if YESNO.match((option or "").strip()) or RESPONSE_EXTRA.fullmatch((option or "").strip()):
            continue
        m = re.match(r"\W*(\d{1,3}|[a-z]+)\b", option or "", re.I)
        word = m.group(1).lower() if m else ""
        value = int(word) if word.isdigit() else _OPTION_VALUE.get(word)
        if value is None:
            return None
        values.append(value)
    return values or None


def many_evidence(texts, options):
    """(positive, unrepresented, bounded, scale) for a question's own label and instructions. positive: a complete
    command allows several answers (positive_command); a count never does. unrepresented: a printed count one choice
    cannot satisfy ("at least two", "exactly 2", "tick 2-3", "2 answers"). bounded: a printed count that allows two or
    more answers ("select up to 3", "tick 1-3", "pick one, two or three"): one choice cannot record it and several
    choices cannot enforce it. scale: a printed range or bound that is the answers' own scale - every answer prints a
    count or a scale point and every printed count spans exactly their values ("up to 3" over One / Two / Three,
    "circle 1-5" over 1 Never .. 5 Always): a scale key, never a count of answers (R4-F4). "Up to 2" over answers
    numbered 1 to 3 is still a count."""
    values = scale_values(options)
    scale = values is not None
    positive, unrepresented, bounded = False, "", ""
    for text in texts:
        for sentence in _clauses(NOT_A_QUANTITY.sub(" ", text or "")):
            if positive_command(sentence):
                positive = True
            for m in COUNT_BOUND.finditer(sentence):
                printed = m.group(0).strip()
                if m.group("upper"):
                    high = _count(m.group(2))
                    if high and high >= 2:
                        bounded = bounded or printed
                        scale = scale and high == max(values)
                elif m.group("lower"):
                    low = _count(m.group("low"))
                    if low and low >= 2:
                        unrepresented = unrepresented or printed
                        scale = False
                elif m.group("exact"):
                    exact = _count(m.group("num"))
                    if exact and exact >= 2:
                        unrepresented = unrepresented or printed
                        scale = False
                elif m.group("first"):
                    first, last = _count(m.group("first")), _count(m.group("last"))
                    if first and last and last > first and last >= 2:
                        if first >= 2:
                            unrepresented = unrepresented or printed
                        else:
                            bounded = bounded or printed
                        scale = scale and (first, last) == (min(values), max(values))
                elif m.group("listed"):
                    last = _count(m.group("listed"))
                    if last and last >= 2:
                        bounded = bounded or printed
                        scale = scale and last == max(values)
            bounds = [m.span() for m in COUNT_BOUND.finditer(sentence)]
            for m in COUNTED_ANSWERS.finditer(sentence):
                # "Select up to three diagnoses": the number is the bound's, already judged above.
                if (_count(m.group(1)) or 0) >= 2 and not any(a <= m.start() < b for a, b in bounds):
                    unrepresented = unrepresented or m.group(0).strip()
                    scale = False
    return positive, unrepresented, bounded, scale

#: ⚠️ 'countersigned' / 'cosigned' are signatures too ('co-signed' already was: the hyphen is a word boundary), and a
#: non-breaking space is still a space ('Please sign\u00a0here' was read as text).
SIGNATURE = re.compile(r"\bsignature\b|\b(?:counter|co)?signed\b|\bsign(?:ed)?\s+here\b", re.I)
INITIALS = re.compile(r"\binitials?\b|\binitial (?:the )?box", re.I)
DATE_LABEL = re.compile(r"\b(?:date|dob|d\.o\.b|born)\b|mm/dd|dd/mm|yyyy|\bD[DT]\s*\((?:dictated|transcribed)\)", re.I)
#: ⚠️ A SIGNATURE (OR INITIALS) AND A DATE PRINTED AS ONE PLACE IS STILL A SIGNING PLACE. The date word used to remove
#: the signing reading from the whole label, so 'Signature and date: ____', 'Patient signature / date' and 'Sign & date'
#: became DATE fields and the export wrote 'Dr Example 30/09/2026' in the signing place. Only the two joined by 'and',
#: '&', '+' or '/' - 'Signature date', 'Date of signature' and 'Date signed' stay date questions.
#: ⚠️ NARROWED (refutation of 258650f2, L1:R1-04 / L1:R1-05): searched anywhere, the pair also read ordinary questions as
#: signing places - 'Date signed / date received', 'Care plan signed and date of next review', 'Consent form signed and
#: dated', 'Patient initials and date of birth', 'Date of referral / initial contact', 'Date of diagnosis / initial
#: stage' - so they were never generated (43fcf214 generated them). A 'signed' pair now opens the label (a 'signed' after
#: other words is the checklist state signing_place already releases), and an initials pair closes it (only a
#: parenthetical, punctuation or a writing line may follow). No signing word is added; fewer labels are pairs.
_JOIN = r"(?:\band\b|&|\+|/)"
_PAIR_CLOSES = r"(?=\s*(?:\([^)]*\))?[\W_]*$)"
SIGNATURE_DATE_PAIR = re.compile(
    r"\bsignatures?\b[^.;:?]*?" + _JOIN + r"\s*dated?\b"
    r"|^\s*(?:please\s+)?(?:electronically\s+|digitally\s+)?(?:counter-?|co-?|e-?)?signed\b[^.;:?]*?" + _JOIN
    + r"\s*dated?\b"
    r"|^\s*(?:please\s+)?sign\s*" + _JOIN + r"\s*dated?\b"
    r"|\bdated?\b[^.;:?]*?" + _JOIN + r"\s*(?:sign(?:ed|atures?)?|(?:counter|co)signed)\b", re.I)
INITIALS_DATE_PAIR = re.compile(
    r"(?:\binitials\b[^.;:?]*?" + _JOIN + r"\s*dated?\b|\binitial\s*" + _JOIN + r"\s*dated?\b"
    r"|\bdated?\b[^.;:?]*?" + _JOIN + r"\s*initials?\b)" + _PAIR_CLOSES, re.I)
TIME_LABEL = re.compile(r"\btime\b|hh:mm|\(24.?h", re.I)
LONG_LABEL = re.compile(r"\b(?:comments?|describe|description|details?|explain|notes?|summary|history|findings|plan|narrative|reason)\b", re.I)


def kind_rule(label: str, *, signing=True) -> str:
    """The wording kind rule of 43fcf214/f5fe720f, unchanged (Detector.kind_for corrects it by the destination state).
    signing=False reads the label without its signature/initials arms: the kind its other words ask for."""
    label = re.sub(r"\s+", " ", label or "")
    if signing:
        if SIGNATURE_DATE_PAIR.search(label):
            return "signature"
        if INITIALS_DATE_PAIR.search(label):
            return "initials"
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
# the question (refutation R3-1). COMPANION words join any family ('N/A ☐ Yes ☐ No'). Vocabulary only ever ADDS a
# reason to hold a row; the one exception is a CLOSED family (below), whose members a form cannot extend.
OPTION_FAMILIES = tuple(re.compile(r"(?:%s)\.?" % f, re.I) for f in (
    r"y|n|yes|no|maybe|possibly|probably",
    r"normal|abnormal|abn|wnl|nl|high|low|borderline|elevated|raised|reduced|critical|intermediate|equivocal",
    r"present|absent|suspected|possible|probable|equivocal",
    r"positive|negative|pos|neg|equivocal|indeterminate|inconclusive|reactive|non-?reactive|detected|not detected|trace|"
    r"weak(?:ly)? positive|strong(?:ly)? positive|invalid|pending|borderline",
    r"none|mild|moderate|severe",
    r"left|right|bilateral|both|l|r|lt|rt|bil|midline|central|unilateral|neither",
    r"male|female|m|f|intersex|non-?binary|transgender",
    r"pass|fail|true|false|borderline|incomplete|partial",
    r"(?:strongly |somewhat )?(?:agree|disagree)|neutral|undecided",
    r"always|often|usually|sometimes|rarely|never|daily|weekly|monthly|yearly|as needed|as required|when needed|"
    r"when required|prn|once|twice|stat|hourly|nightly|occasional(?:ly)?|frequent(?:ly)?|constant(?:ly)?|"
    r"intermittent(?:ly)?|continuous(?:ly)?|(?:once|twice) (?:a day|daily|weekly)|every day",
    r"current(?: smoker)?|former(?: smoker)?|never(?: smoker)?|ex-?smoker|non-?smoker|occasional smoker|social smoker|"
    r"light smoker|heavy smoker|vaper",
    r"regular|irregular|irregularly irregular|regularly irregular",
    r"increased|decreased|unchanged|improved|worse|better|same",
    r"active|inactive|resolved|ongoing|acute|chronic",
    r"mm|cm|m|in|inches|ft|kg|g|lbs?|oz|\u00b0\s?[CF]|bpm|mm\s?hg|%|mg|mcg|ml|l|units?|years?|yrs?|months?|weeks?|days?|"
    r"hours?|hrs?|minutes?|mins?|seconds?|secs?|times?",
    r"single|married|divorced|widowed|separated|partnered|cohabiting|civil partnership|domestic partner|engaged|widower|"
    r"widow",
))
# Families a form rarely extends with a word of its own: after-box options all of one of them are the question's whole
# answer set, so a word before the first box that is not a member is the question's (yes/no, normal/abnormal,
# present/absent, positive/negative, sides, sexes, pass/fail, agreement, smoking status, regularity, marital status).
# Each lists its middle and extra members ('Borderline', 'Trace', 'Midline', 'Suspected'): such a word before the first
# box shares the family and holds the row. RESIDUAL: a member no list names still reads as the question when the
# row's only other mark is a companion or 'Other' after its last box.
CLOSED_FAMILIES = frozenset({0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 15})
UNIT_TAIL = re.compile(r"\(?\s*(?:mm|cm|m|in|inches|ft|kg|g|lbs?|oz|\u00b0\s?[CF]|bpm|mm\s?hg|%|mg|mcg|ml|l|units?|years?|yrs?|"
                       r"months?|weeks?|days?|hours?|hrs?|minutes?|mins?|times?)\.?\s*\)?", re.I)
COMPANION_OPTION = re.compile(r"(?:n/?a|nd|unk|unknown|not known|not applicable|not done|done|other|unsure|"
                              r"don'?t know|dk|not assessed|not examined|not tested|not recorded|not stated|nkda|nka|nil|"
                              r"none|declined|refused|unable to assess)\.?", re.I)
# A word and its printed negation ('Equal' / 'Unequal', 'Tender' / 'Non-tender', 'Palpable' / 'Not palpable').
NEGATION_PREFIX = ("un", "in", "im", "il", "ir", "non", "non-", "non ", "not ", "a", "ab", "dis")


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
    # Read only by destination_roles (never serialised into a field): the paragraph the engine read this area's label
    # from when that is another paragraph (a caption over its writing line), and whether its kind comes from printed
    # structure (a drawn initials box) rather than from its label's wording.
    label_slot: object = None
    structural: bool = False
    # roles-2: the destination state the engine's structure gave this area (Detector.assign_destinations), when it is
    # not its label's own reading (a sequence word beside a bare 'Initial', a caption under a writing line, a signing box).
    # Read only by destination roles; never serialised into a field.
    destination: object = None


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


# Answer words printed as column headers beyond OPTION_WORD: a survey's non-answers and availability.
RESPONSE_EXTRA = re.compile(r"(?:refused|declined|don[’']?t\s+know|do\s+not\s+know|not\s+sure|unsure|prefer\s+not\s+to\s+"
                            r"(?:say|answer)|not\s+available|service\s+not\s+available|n/?k)\.?", re.I)


def response_word(txt: str) -> bool:
    """A column header that is itself an answer ('Yes', 'N/A or ND', 'UNKNOWN', 'REFUSED', 'DON'T KNOW')."""
    txt = (txt or "").strip()
    return is_option_word(txt) or bool(YESNO.match(txt)) or bool(RESPONSE_EXTRA.fullmatch(txt))


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
        self.destination_places: list = []       # roles-2: governed writing lines with no engine area (assign_destinations)
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
        self._form_wide_nodes = []        # keeps the guidance paragraphs alive: their ids key the scope reading
        self._coded_problem = ""
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
        """The kind of an area read from its printed label: the wording kind rule (kind_rule), corrected by the
        destination state (roles-2, destination_state) of the same label. A label the state reads ORDINARY on positive
        evidence ('Troponin (initial)', 'Consent form signed by patient') takes the kind its other words ask for; a label
        it reads as a signing or uncertain place ('Sign below', 'Signature, date') takes a signing kind, so it is never
        generated on any path. Every other label keeps the kind rule's kind."""
        label = re.sub(r"\s+", " ", label or "")
        kind = kind_rule(label)
        if not SIGNING_TOKEN.search(label):
            return kind
        state = destination_state(label)
        if kind in SIGNING_KINDS and state["state"] == STATE_ORDINARY and state["basis"] in ORDINARY_EVIDENCE:
            return kind_rule(label, signing=False)
        if kind not in SIGNING_KINDS and kind in ("text", "long_text", "date", "time") and state["state"] != STATE_ORDINARY:
            return state["kind"] or "signature"
        return kind

    def cardinality(self, question, options, *, local=(), between=(), own=(), hint="", where="", context=""):
        """The selection rule for one checkbox question (see MANY_COMMAND): {"kind": "choice" | "multi_choice",
        "note": review note or "", "single": one answer is printed as the rule (a one-only instruction or Yes/No
        answers)} or {"problem": why it is held}.

        `question` is its printed label. `local` is the rest of its own source, where a positive command counts: the
        text printed after its boxes, the other paragraphs of its own cells, its column header, a nested grid's parent
        question and its own adjacent instructions. `between` holds the instructions printed next to it that it does
        not own (printed between it and another question, or pointing elsewhere): a limit there governs it, a command
        there never does (R4-F5). `own` is the ids of the w:p elements read here, never read again as guidance printed
        elsewhere. `context` is its heading chain: with its label and answers, its subject, which keeps a limit printed
        elsewhere on form-filling mechanics in reach when the question is about that thing (limit_reaches). `hint` is
        the printed line of its first boxes."""
        texts = [t for t in [question or "", *local] if t and t.strip()]
        near = [t for t in between or () if t and t.strip()]
        options = [o or "" for o in options or []]
        printed = (question or "")[:200]
        if options and all(YESNO.match(o.strip()) for o in options):
            return {"kind": "choice", "note": "", "single": True}
        clauses = [x for t in [*texts, *near] for x in _clauses(t)]
        one = one_only([*texts, *near, hint or ""], [*texts, *near]) or any(limit_language(x, local=True) for x in clauses)
        positive, unrepresented, bounded, scale = many_evidence(texts, options)
        count = unrepresented or bounded
        per_item = next((m.group(0) for t in [*texts, *near] for m in [PER_ITEM.search(t)] if m), "")
        if positive:
            if count:
                return {"problem": "Checkbox question%s carries a printed selection count the form's choices cannot "
                        "represent ('%s') beside its all-that-apply instruction: the printed cardinality instructions "
                        "conflict; nothing was guessed. Printed question: %s" % (where, count, printed)}
            if one or per_item:
                return {"problem": "Checkbox question%s: the printed cardinality instructions conflict (one only and "
                        "several selections); nothing was guessed. Printed question: %s" % (where, printed)}
            elsewhere = self.scope_limit(own, subject_stems(question, context, *options))
            if elsewhere:
                return {"problem": "Checkbox question%s: its all-that-apply instruction conflicts with a limited "
                        "selection instruction printed elsewhere in the form (%s: %s) whose reach is unresolved; "
                        "nothing was guessed. Printed question: %s" % (where, elsewhere[0], elsewhere[1][:120], printed)}
            return {"kind": "multi_choice", "note": "", "single": False}
        if per_item:
            return {"problem": "Checkbox question%s asks for one box per item ('%s'); whether several of its answers "
                    "may be chosen is unresolved, so nothing was guessed. Printed question: %s"
                    % (where, per_item.strip(), printed)}
        if count and not scale:
            # One choice cannot record the second answer the count allows, and several choices cannot enforce the
            # count: held, never mapped to either (R4-F14).
            return {"problem": "Checkbox question%s carries a printed selection count the form's choices cannot "
                    "represent ('%s'); nothing was guessed. Printed question: %s" % (where, count, printed)}
        if one:
            return {"kind": "choice", "note": "", "single": True}
        if count:
            # A scale key: one choice, said so, because the same print could count answers numbered like a scale.
            return {"kind": "choice", "single": True, "note": (
                "Checkbox question%s keeps one choice: its printed range ('%s') is read as the scale of its own "
                "numbered answers, not as a number of answers to choose; review it. Printed question: %s"
                % (where, count, printed))}
        pointed = next((t for t in near if positive_command(t)), "")
        # A yes/no question ("Do you have more than one type of headache? [ ] No [ ] Yes - describe") has one answer
        # whatever its subject counts.
        yes_no = bool(options) and all(re.match(r"\W*(?:yes|no)\b", o, re.I) for o in options)
        uncertain = "" if yes_no else next((m.group(0) for t in texts for m in [UNCERTAIN_MANY.search(t)] if m), "")
        note = ""
        if pointed:
            note = ("Checkbox question%s keeps one choice: an all-that-apply instruction is printed near it ('%s') but "
                    "not as its own instruction (it sits between it and another question), so which question it governs "
                    "is unresolved; review it before relying on one answer. Printed question: %s"
                    % (where, pointed[:120], printed))
        elif uncertain:
            note = ("Checkbox question%s keeps one choice: its printed wording ('%s') suggests several answers may "
                    "apply, but no complete all-that-apply instruction governs it; review it before relying on one "
                    "answer. Printed question: %s" % (where, uncertain, printed))
        return {"kind": "choice", "note": note, "single": False}

    def scope_limit(self, own, stems=frozenset()):
        """An unowned one-only or limited-count instruction printed anywhere in the form outside `own` (w:p ids) that
        may govern a question whose subject stems are `stems` (limit_reaches): (where, sentence), or None. Its reach
        cannot be read, so it may govern any question unless all it counts is form-filling mechanics."""
        for pid, owner, sentence, where, targets in self.selection_guidance():
            if pid in own or owner is not None or not limit_reaches(targets, stems):
                continue
            return where, sentence
        return None

    def adjacent_instructions(self, slot):
        """The printed instruction paragraphs directly above `slot` in its own container (body or cell): consecutive
        plain paragraphs up to a heading, a table, another question (boxes or a blank) or the container's start; the
        three nearest are read. They are the question's OWN instructions only when a heading, plain text or the
        container's start is printed above them. Printed below another question's boxes or blank, or after a table
        or a block control, they sit between two questions and belong to neither (R4-F5); so does one that points
        back ("for the question above"). Returns (own texts, between texts, paragraph slots)."""
        container = [s for s in (slot.parent.children if slot.parent is not None else self.index.roots)
                     if s.part == slot.part]
        if slot not in container:
            return [], [], []
        texts, slots, owned = [], [], True
        for prior in reversed(container[:container.index(slot)]):
            if prior.kind != "p":
                owned = False
                break
            text = self.text(prior.el).strip()
            if not text:
                continue
            if self.question_box_paragraph(prior.el)[0]:
                break
            if (BOX in self.ptext(prior.el)[0] or CHECKED in self.ptext(prior.el)[0]
                    or self.blank_spans(*self.ptext(prior.el))):
                owned = False
                break
            texts.insert(0, text)
            slots.insert(0, prior)
        texts, slots = texts[-3:], slots[-3:]
        if not owned:
            return [], texts, slots
        back = [t for t in texts if re.search(r"\b(?:above|previous|preceding)\b", t, re.I)]
        return [t for t in texts if t not in back], back, slots

    def own_source_texts(self, paras, cells=()):
        """A question's printed source read with it, never again as guidance printed elsewhere (R4-F12): (own, shared).
        Its own: the text printed after its boxes on its own lines (past a wide gap, or in brackets) and the other
        paragraphs of its own cells (its answer cell, its row label and column header cells) when they hold no other
        question (no box of another question, no nested table). A cell that also holds other questions is shared: its
        other paragraphs are near the question but not its own - a limit there governs it, a command there never
        does. Answer words are answers, never instructions ("Pain in only one joint")."""
        own, shared, seen = [], [], {id(p.el) for p in paras}
        for p in paras:
            for segment in re.split("[" + BOX + CHECKED + "]", self.ptext(p.el)[0])[1:]:
                for n, piece in enumerate(re.split(r"\t{2,}| {4,}|\n", segment)):
                    piece = piece.replace("\x00", " ").strip()
                    if n:
                        own.append(piece)
                    else:
                        # the answer itself is not read; what it prints in brackets or after its first sentence is
                        own += [a or b for a, b in re.findall(r"\(([^()]*)\)|\[([^\[\]]*)\]", piece)]
                        own += re.split(r"(?<=[.!?;])\s+", piece)[1:]
        for cell in cells:
            paragraphs = [x for x in cell.el.iter(q("w:p")) if id(x) not in seen]
            alone = cell.el.find(".//" + q("w:tbl")) is None and not any(
                BOX in paragraph_text(x)[0] or CHECKED in paragraph_text(x)[0] for x in paragraphs)
            for x in paragraphs:
                seen.add(id(x))
                if BOX not in paragraph_text(x)[0] and CHECKED not in paragraph_text(x)[0]:
                    (own if alone else shared).append(text_of(x, own=True))
        return [t.strip() for t in own if t and t.strip()], [t.strip() for t in shared if t and t.strip()]

    def question_cells(self, tbl_slot, row, col):
        """The cells that print a table question's own source for the answer at (row, col): its row label (the
        nearest label cell to the left, as row_label reads it) and its column header cells (the label row directly
        above and the header rows over that column). Every other cell of the table stays in the question's scope."""
        cells, rows = [], self.grid(tbl_slot)
        label = None
        for c in sorted(rows.get(row, []), key=lambda c: c.info["col"]):
            if c.info["col"] >= col:
                break
            if self.is_label_cell(c):
                label = c
        cells += [label] if label is not None else []
        above = [r for r in rows if r < row]
        header_rows = [max(above)] if above and self.row_kind(tbl_slot, max(above)) == "label" else []
        ht = self.header_table(tbl_slot)
        for table, rr in [(tbl_slot, r) for r in header_rows] + [(ht, r) for r in self.header_rows(ht)]:
            cells += [c for c in self.grid(table).get(rr, []) if c.info["col"] <= col < c.info["col"] + c.info["span"]]
        return cells

    def own_paragraph_ids(self, cells):
        return {id(x) for c in cells for x in c.el.iter(q("w:p"))}

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
        self.assign_destinations()
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

    # -- roles-2: destination states read from STRUCTURE ---------------------------------------------------------------
    #: A writing line: underscores (ASCII, fullwidth U+FF3F, double low U+2017, box-drawing and overline rules), a dotted
    #: leader, optionally opened by a title ('Dr ____'). Read only for destination roles.
    _LINE = r"(?:[_\uff3f\u2017\u2500\u2501\u2015\u00af\u203e]{3,}|\.{5,}|\u2026{2,})"
    _LINE_RUN = re.compile(r"(?:(?:dr|mr|mrs|ms|miss|prof)\.?[ \t]+)?" + _LINE +
                           r"(?:[ ]*(?:[_\uff3f\u2017\u2500\u2501\u2015\u00af\u203e]{2,}|\.{5,}|\u2026{2,}))*", re.I)
    _TITLE = re.compile(r"(?:dr|mr|mrs|ms|miss|prof)\.?[ \t]+", re.I)

    def _bordered_empty(self, p) -> bool:
        """An empty paragraph drawn as a writing rule by its own top or bottom border."""
        ppr = p.find(q("w:pPr"))
        border = ppr.find(q("w:pBdr")) if ppr is not None else None
        if border is None:
            return False
        return any(edge is not None and (edge.get(q("w:val")) or "single") not in ("none", "nil")
                   for edge in (border.find(q("w:bottom")), border.find(q("w:top"))))

    def _line_runs(self, pslot):
        """[(start, end)] of the writing lines a paragraph prints AS lines - every run of a paragraph that is nothing but
        lines (one per tab-separated segment), or the line that opens it (guidance or another labelled blank may follow);
        [(None, None)] for a bordered empty paragraph; [] for any other paragraph (a labelled blank is its own label's)."""
        text, _ = self.ptext(pslot.el)
        if not text.strip():
            return [(None, None)] if "\x00" not in text and self._bordered_empty(pslot.el) else []
        runs = [(m.start(), m.end()) for m in self._LINE_RUN.finditer(text)]
        if not runs:
            return []
        rest = text
        for start, end in reversed(runs):
            rest = rest[:start] + rest[end:]
        if not rest.strip():
            return runs
        lead = len(text) - len(text.lstrip())
        return [runs[0]] if runs[0][0] == lead else []

    def _caption(self, pslot) -> str:
        """The printed caption a paragraph is, or '': short printed words with no blank of their own, no line, no box and
        no field, not a Word heading style, not a sentence (a declaration above a signing block is no caption)."""
        text, pieces = self.ptext(pslot.el)
        if not text.strip() or "\x00" in text or BOX in text or CHECKED in text or self._LINE_RUN.search(text):
            return ""
        if self.blank_spans(text, pieces):
            return ""
        ppr = pslot.el.find(q("w:pPr"))
        style = ppr.find(q("w:pStyle")).get(q("w:val")) if ppr is not None and ppr.find(q("w:pStyle")) is not None else ""
        if HEADING_STYLE.match(style or ""):
            return ""
        words = clean_label(text).split()
        if not words or len(words) > 12 or (len(words) >= 4 and text.strip().endswith((".", "!"))):
            return ""
        return text

    @staticmethod
    def _segment_states(caption):
        """The destination state of each tab-separated segment of a caption ('Patient signature<tab><tab>Date')."""
        return [destination_state(x) for x in re.split(r"\t+", caption) if clean_label(x)]

    def _paragraph_sequences(self):
        """Every run of paragraphs that are siblings in the XML (a table or other block between them ends the run)."""
        containers = [[s for s in self.index.roots if s.kind == "p" and s.part == part]
                      for part in dict.fromkeys(s.part for s in self.index.roots)]
        containers += [[c for c in s.children if c.kind == "p"] for s in self.index.slots if s.kind in ("tc", "txbx")]
        for paras in containers:
            run = []
            for ps in paras:
                if run and run[-1].el.getnext() is not ps.el:
                    yield run
                    run = []
                run.append(ps)
            if run:
                yield run

    def _governed_lines(self):
        """{(paragraph slot id, start, end): (state, caption)} for every writing line a signing or uncertain caption
        governs (roles-2): a caption printed under its line or over it ('Consultant signature' under '______'; a 'Label:'
        over its line), read as a block - the block's first element says which way its captions run; a line whose own
        caption is ordinary but which sits directly against a signing caption is UNCERTAIN (residual L1:F2, 'Print name'
        under a line that also sits under 'Patient signature'). Guidance or an empty paragraph between a caption and
        its line does not end the block (L1:F8, L1:RR1-06)."""
        out = {}
        for paras in self._paragraph_sequences():
            items = []
            for ps in paras:
                runs = self._line_runs(ps)
                caption = "" if runs else self._caption(ps)
                text = self.ptext(ps.el)[0]
                kind = "line" if runs else "caption" if caption else "empty" if not text.strip() else "other"
                items.append((ps, kind, runs, caption))
            blocks, block, empties = [], [], 0
            for item in items:
                if item[1] in ("other",):
                    if block:
                        blocks.append(block)
                    block, empties = [], 0
                    continue
                if item[1] == "empty":
                    empties += 1
                    if empties > 2 and block:
                        blocks.append(block)
                        block, empties = [], 0
                    continue
                empties = 0
                block.append(item)
            if block:
                blocks.append(block)
            for block in blocks:
                if not any(k == "line" for _, k, _, _ in block) or not any(k == "caption" for _, k, _, _ in block):
                    continue
                under = block[0][1] == "line"
                for i, (ps, kind, runs, _) in enumerate(block):
                    if kind != "line":
                        continue
                    above = block[i - 1] if i > 0 and block[i - 1][1] == "caption" else None
                    below = block[i + 1] if i + 1 < len(block) and block[i + 1][1] == "caption" else None
                    # A 'Label:' caption claims the line under it whichever way the block runs.
                    if above is not None and above[3].rstrip().endswith(":"):
                        own, other = above, below
                    elif under:
                        own, other = below, above
                    else:
                        own, other = above, below
                    own_states = self._segment_states(own[3]) if own is not None else []
                    other_states = self._segment_states(other[3]) if other is not None else []
                    # A signing caption directly against the line on its other side, or within two captions on its
                    # own side ('Consultant signature' / 'Use black ink.' / '____'), leaves the line uncertain.
                    near = [block[j] for j in (range(max(0, i - 2), i) if not under else range(i + 1, min(len(block), i + 3)))
                            if block[j][1] == "caption" and block[j] is not own]
                    near_states = [x for item in near for x in self._segment_states(item[3])]
                    signing_other = any(x["state"] != STATE_ORDINARY for x in other_states + near_states)
                    if other is None and near:
                        other = next((item for item in near if any(x["state"] != STATE_ORDINARY
                                                                   for x in self._segment_states(item[3]))), None)
                    for n, (start, end) in enumerate(runs):
                        if own_states and len(own_states) == len(runs) and len(runs) > 1:
                            state = own_states[n]
                        elif own_states:
                            state = max(own_states, key=lambda x: STATE_RANK[x["state"]])
                        else:
                            state = None
                        caption = clean_label(own[3]) if own is not None else ""
                        if (state is None or state["state"] == STATE_ORDINARY) and signing_other:
                            state = _state(STATE_UNCERTAIN, "line_beside_signing_caption", "signature")
                            caption = caption or clean_label(other[3])
                        if state is not None and state["state"] != STATE_ORDINARY:
                            out[(ps.id, start, end)] = (dict(state, basis="governed_line:" + state["basis"]), caption)
        return out

    def _question_box_cells(self):
        """{cell id: (state, question)} for every one-cell box whose printed question or section reads as signing or
        consent (the engine's own reading) or whose question the destination state holds (roles-2: 'Countersignature?',
        'Signatures?' - residual L1:F6). Nested boxes are read too (residual L1:RR1-07)."""
        out = {}
        for table in [s for s in self.index.slots if s.kind == "tbl"]:
            cells = [c for c in table.children if c.kind == "tc"]
            if len(cells) != 1 or len(table_rows_of(table.el)) != 1:
                continue
            question, section = self.question_box_role_source(table)
            state = destination_state(question) if question else None
            if state is not None and state["state"] != STATE_ORDINARY:
                out[cells[0].id] = (state, question)
            elif signing_box_reading(question) or signing_box_reading(section):
                out[cells[0].id] = (_state(STATE_PROTECTED, "signing_box", "signature"), question or section)
        return out

    def _own_label(self, area):
        """The words printed before an area's blank on its own line (after the previous blank), or '' - '' means the
        engine borrowed its label from elsewhere (a caption, a heading, the text after the line)."""
        target = area.target or {}
        if target.get("type") != "span" or area.slot.kind != "p":
            return None
        text = self.ptext(area.slot.el)[0]
        start = target.get("start")
        if not isinstance(start, int):
            return None
        before = text[:start]
        before = re.split(r"(?:[_\uff3f\u2017]{2,}|\.{5,}|\u2026{2,}|\x00)", before)[-1]
        return clean_label(self._TITLE.sub("", before)) if not self._TITLE.fullmatch(before.strip() + " ") else ""

    #: A placeholder that is an author's note about the printed WORDING (which version applies, what to add or remove)
    #: rather than a question: '<for hospital-based POS>', '<if POS collects genetic data>', '<remove if not applicable>'.
    _WORDING_NOTE = re.compile(r"^\W*(?:if|for|when|where|unless|all|or|and|only|optional(?:ly)?|remove|delete|add|"
                               r"choose|select|use|e\.g|i\.e)\b", re.I)
    #: An agent heading of a signing row: who completed, reviewed, assented ('Completed by:', 'Assent of Minor:').
    _AGENT = re.compile(r"^(?:[\w/-]+\s+){0,3}(?:by|of)\s*$|^(?:assent|consent|agreement|declaration)\b", re.I)
    _CONNECTOR = re.compile(r"^(?:by|on|at|of|and|the|date|time)?$", re.I)

    def _inline_caption(self, area):
        """(the words printed just before an inline area since the previous blank, the paragraph's words before it) -
        placeholders, writing lines and objects removed - or None when the area is not inline in a paragraph."""
        target = area.target or {}
        if area.slot.kind == "p" and target.get("type") == "span" and isinstance(target.get("start"), int):
            text, start = self.ptext(area.slot.el)[0], target["start"]
        elif area.slot.kind in ("sdt", "ff") and area.slot.parent is not None and area.slot.parent.kind == "p":
            text, pieces = self.ptext(area.slot.parent.el)
            start = next((pc.start for pc in pieces if pc.kind == "obj" and pc.node is area.slot.el), None)
            if start is None:
                return None
        else:
            return None
        def words(chunk):
            chunk = re.sub(r"<<?[^<>]*>>?|\[[^\[\]]*\]|\{\{[^}]*\}\}", " ", chunk)
            chunk = re.sub(r"[_\uff3f\u2017\u2500\u2501\u2015\u00af\u203e.\u2026\u00b7\x00]{2,}|\x00", " ", chunk)
            return clean_label(chunk)
        before = text[:start]
        own = re.split(r"[_\uff3f\u2017\u2026\x00]{2,}|\x00|\.{5,}|>>|\]|(?<=[.!?])\s+", before)[-1]
        return words(own), words(before)

    def assign_destinations(self):
        """roles-2: the destination state of every engine area, from its label AND its structure, recorded on the area
        (area.destination) and on the places with no area (self.destination_places), and the kind made to agree: an
        area held on a signing or uncertain place takes a Signature or Initials kind (never generated on any path, its
        place a role), an area the structure establishes as ordinary keeps the kind its words ask for.

        Structure read, in order: (1) a writing line a signing caption governs; (2) a table cell's label cell read as
        words, its table's other rows and its row's units; (3) a signing box's own line, a person's line in it;
        (4) the caption printed just before an inline area (a content control after 'Consultant signature:', an
        attestation 'Electronically Signed On <...> By:'); (5) a placeholder's own words ('[Sign]') or an author's note
        about the wording ('<if POS collects genetic data>'); (6) an agent heading of a signing row ('Completed by:'
        beside 'Signature:', 'Investigator:' over 'Signature of Investigator'); (7) a caption line of several segments
        over a whole writing line; then (8) every area on the same writing run as a held signing area, and the inline
        signing captions with no area of their own (a manual add there is refused)."""
        self.destination_places = []
        lines = self._governed_lines()
        boxes = self._question_box_cells()
        line_hit = {}
        for (pid, start, end), value in lines.items():
            line_hit.setdefault(pid, []).append((start, end, value))
        covered = set()
        previous_note = {}
        for area in self.areas:
            if area.protection or area.structural:
                continue
            state, caption = None, ""
            target = area.target or {}
            # (1) a writing line a signing caption governs.
            for start, end, (st, cap) in line_hit.get(area.slot.id, []):
                ts, te = target.get("start"), target.get("end")
                whole = start is None or not isinstance(ts, int) or target.get("type") != "span"
                if whole or (ts < end and te > start) or ts == start:
                    state, caption = st, cap
                    covered.add((area.slot.id, start, end))
                    break
            # (2) a table cell: its label cell read with its paragraphs as words, its table and row as structure.
            cell = self.host_cell(area.slot)
            if state is None and cell is not None and target.get("type") in ("cell", "cell_replace", "cell_append") \
                    and cell.id not in boxes:
                spaced, siblings, unit = self._cell_context(cell)
                base = destination_state(area.label)
                st = destination_state(spaced, siblings=siblings, unit=unit, lines=self._cell_lines) if spaced else base
                caption_for = spaced
                if spaced and re.sub(r"\W", "", spaced).casefold() != re.sub(r"\W", "", area.label).casefold():
                    # The label joins the row label and its column header ('Nurse — Initials', 'Troponin (initial) —
                    # Result'): each is read as itself, with its own neighbours, and the stricter reading decides - the
                    # engine's joined wording is no printed label ('Troponin (initial) — Result' read as one closes no
                    # qualifier). A header the row label does not explain keeps the joined reading as well.
                    header, header_siblings = self._header_context(cell)
                    readings = [st, destination_state(header, siblings=header_siblings, unit=unit)] if header else [st, base]
                    st = max(readings, key=lambda x: STATE_RANK[x["state"]])
                    if st["state"] == STATE_ORDINARY and not any(x["basis"] in ORDINARY_EVIDENCE for x in readings):
                        st = base
                    caption_for = area.label
                if st["state"] != base["state"] or st["basis"] != base["basis"]:
                    state, caption = st, caption_for
            # (3) inside a signing box: the box's line or a person's line is the signing place.
            box_cell = next((c for c in (self.host_cell(area.slot),) if c is not None and c.id in boxes), None)
            if state is None and box_cell is not None:
                box_state, question = boxes[box_cell.id]
                own = self._own_label(area)
                if area.slot.id == box_cell.id or target.get("type") in ("cell", "cell_replace", "cell_append"):
                    state, caption = box_state, clean_label(question)
                elif own == "":
                    state, caption = dict(box_state, basis="signing_box_line"), clean_label(question)
                elif own is not None:
                    st = destination_state(own)
                    if st["state"] != STATE_ORDINARY:
                        state, caption = st, own
                    elif _person(own) or _agent_only(own) or re.fullmatch(r"(?:dr|mr|mrs|ms|miss|prof)\.?", own, re.I):
                        state, caption = _state(STATE_PROTECTED, "signing_box_person", "signature"), own
            # (4) the caption printed just before an inline area: its own words, or - where they are only a connector
            #     ('By:', '>', 'on') - the paragraph's words before it. A date keeps its date (PC02).
            inline = self._inline_caption(area) if state is None and area.kind != "date" else None
            if inline is not None:
                own_words, prefix = inline
                reading = prefix if self._CONNECTOR.match(own_words) else own_words
                st = destination_state(reading) if reading else None
                if st is not None and st["state"] != STATE_ORDINARY:
                    state, caption = dict(st, basis="caption:" + st["basis"]), clean_label(reading)
            # (5) a placeholder's own words, or an author's note about the printed wording.
            shape = target.get("shape")
            if state is None and target.get("type") == "span" and shape in ("angle", "bracket") and area.slot.kind == "p":
                text = self.ptext(area.slot.el)[0]
                content = text[target["start"]:target["end"]].strip("<>[] ")
                st = destination_state(content)
                if st["state"] != STATE_ORDINARY:
                    state, caption = dict(st, basis="placeholder:" + st["basis"]), clean_label(content)
                elif shape == "angle" and (self._WORDING_NOTE.match(content) or (
                        previous_note.get(area.slot.id) is not None
                        and not text[previous_note[area.slot.id]:target["start"]].strip())):
                    # Only an ANGLE placeholder is an author's template note ('<if POS collects genetic data>'); a square
                    # bracket inside a question is the form's own hint to the person answering ('[If yes, give details]').
                    state = _state(STATE_UNCERTAIN, "wording_note", "signature")
                    caption = clean_label(content)
                if shape == "angle" and (state is not None and state["basis"] == "wording_note"):
                    previous_note[area.slot.id] = target["end"]
            # (6) an agent heading of a signing row: 'Completed by:' beside 'Signature:', 'Investigator:' over the row
            #     whose caption reads 'Signature of Investigator'.
            if state is None and cell is not None and target.get("type") == "span" and shape == "after_label":
                own = clean_label(area.label)
                agent = bool(self._AGENT.search(own))
                if (agent and self._signing_row_near(cell, rows=(0, 1, 2))) or \
                        ((_person(own) or _agent_only(own)) and self._signing_row_near(cell, rows=(1, 2))):
                    state, caption = _state(STATE_UNCERTAIN, "signing_row_agent", "signature"), own
            # (7) a caption line of several segments over a whole writing line ('Signature of Participant<tab>Print
            #     Name<tab>Date' over one line): the line holds the signing segment.
            if state is None and area.label_slot is not None and target.get("type") in ("paragraph", "cell"):
                segments = self._segment_states(self.ptext(area.label_slot.el)[0])
                if len(segments) > 1:
                    worst = max(segments, key=lambda x: STATE_RANK[x["state"]])
                    if worst["state"] != STATE_ORDINARY:
                        state, caption = dict(worst, basis="caption_segments"), clean_label(self.text(area.label_slot.el))
            if state is None:
                continue
            self._apply_destination(area, state, caption)
        # (8) the same writing run as a held signing area ('Signature:……………........…………' read as three areas).
        for area in self.areas:
            target = area.target or {}
            if area.kind not in SIGNING_KINDS or area.slot.kind != "p" or target.get("type") != "span" \
                    or not isinstance(target.get("start"), int):
                continue
            held = area_destination(area)
            if held["state"] == STATE_ORDINARY and not area.structural:
                continue
            text = self.ptext(area.slot.el)[0]
            low, high = target["start"], target["end"]
            while low > 0 and text[low - 1] in self._RUN_CHARS:
                low -= 1
            while high < len(text) and text[high] in self._RUN_CHARS:
                high += 1
            for other in self.areas:
                ot = other.target or {}
                if other is area or other.slot is not area.slot or other.protection or ot.get("type") != "span" \
                        or not isinstance(ot.get("start"), int) or other.kind in SIGNING_KINDS:
                    continue
                if low <= ot["start"] and ot["end"] <= high:
                    self._apply_destination(other, dict(held, basis="same_writing_run"), area.label)
        for key, (state, caption) in lines.items():
            if key not in covered:
                self.destination_places.append((key[0], key[1], key[2], state, caption))
        self.destination_places.extend(self._inline_signing_captions())

    _RUN_CHARS = "_\uff3f\u2017\u2500\u2501\u2015\u00af\u203e.\u2026\u00b7"

    def _apply_destination(self, area, state, caption):
        area.destination = state
        if state["state"] == STATE_ORDINARY:
            if area.kind in SIGNING_KINDS and state["basis"] in ORDINARY_EVIDENCE:
                area.kind = kind_rule(caption or area.label, signing=False)
                if caption:
                    area.label = caption
            return
        if area.kind in ("text", "long_text", "date", "time"):
            area.kind = state["kind"] or "signature"
        if caption and (not SIGNING_TOKEN.search(area.label) or self._own_label(area) == "" or
                        re.sub(r"\s", "", caption).casefold() == re.sub(r"\s", "", area.label).casefold()):
            area.label = caption

    def _signing_row_near(self, cell, rows=(0, 1, 2)):
        """Whether the cell's own row (offset 0) or one of the rows under it prints a signing caption."""
        table, row = cell.parent, cell.info["row"]
        grid = self.grid(table)
        for r in (row + n for n in rows):
            for c in grid.get(r, []):
                if c is cell:
                    continue
                text = self.cell_text(c)
                if text and destination_state(text)["state"] == STATE_PROTECTED:
                    return True
        return False

    def _inline_signing_captions(self):
        """[(paragraph id, start, end, state, caption)] for every 'Label:' segment of a paragraph whose label holds the
        place and no engine area answers ('Circle Yes or No: Yes No Initials: ____ Date: ____' - the initials segment has
        no area): a manual text field there is refused (protected) or held (uncertain)."""
        out = []
        answered = {}
        for area in self.areas:
            t = area.target or {}
            if area.slot.kind == "p" and t.get("type") == "span" and isinstance(t.get("start"), int):
                answered.setdefault(area.slot.id, []).append((t["start"], t["end"]))
        for slot in self.index.slots:
            if slot.kind != "p":
                continue
            text = self.ptext(slot.el)[0]
            if ":" not in text or len(text) > 400:
                continue
            # A label is the words just before a colon, after the last box, object, tab or run of spaces: the
            # printed options of a question beside it ('Reviewed: ☐ Yes ☐ No    Signature:') are never part of it.
            marks = [m for m in re.finditer(r"(?:^|(?<=[\s\x00" + BOX + CHECKED + r"]))([^\s:\t\x00" + BOX + CHECKED +
                                            r"](?:[^:\t\x00" + BOX + CHECKED + r" ]| (?! ))" + r"{0,40}?):", text)]
            for i, m in enumerate(marks):
                label = clean_label(m.group(1))
                st = destination_state(label) if label else None
                if st is None or st["state"] == STATE_ORDINARY:
                    continue
                start, end = m.start(1), marks[i + 1].start(1) if i + 1 < len(marks) else len(text) + 1
                if any(start <= a < end or start < b <= end for a, b in answered.get(slot.id, [])):
                    continue
                out.append((slot.id, start, end, dict(st, basis="inline_caption:" + st["basis"]), label))
        return out

    def _header_context(self, cell):
        """(the answer cell's column header, the other column headers of its header row)."""
        table, row, col = cell.parent, cell.info["row"], cell.info["col"]
        header = clean_label(self.column_header(table, col, row))
        others = []
        for c in self.grid(table).get(0, []):
            if c.info["col"] != col and self.cell_text(c):
                others.append(clean_label(self.cell_text(c)))
        return header, others

    def _cell_context(self, cell):
        """(the row's label cell read with its paragraphs and line breaks as spaces, the other row labels of the table,
        whether the row or the answer's column prints a unit)."""
        def spaced(c):
            return re.sub(r"\s+", " ", " ".join(self.text(p.el) for p in c.children if p.kind == "p")).strip()
        table, row, col = cell.parent, cell.info["row"], cell.info["col"]
        label_cell = None
        for c in sorted(self.grid(table).get(row, []), key=lambda c: c.info["col"]):
            if c.info["col"] >= col:
                break
            if self.is_label_cell(c):
                label_cell = c
        own = spaced(label_cell) if label_cell is not None else ""
        self._cell_lines = [line for p in (label_cell.children if label_cell is not None else []) if p.kind == "p"
                            for line in re.split(r"\n", self.text(p.el)) if line.strip()]
        siblings = []
        for r, cells in self.grid(table).items():
            if r == row:
                continue
            first = sorted(cells, key=lambda c: c.info["col"])
            if first and self.is_label_cell(first[0]):
                siblings.append(spaced(first[0]))
        row_text = " ".join(self.cell_text(c) for c in self.grid(table).get(row, []) if c is not label_cell and c is not cell)
        header = self.column_header(table, col, row)
        unit = bool(UNIT_TOKEN.search(row_text) or UNIT_TOKEN.search(header or ""))
        return own, siblings, unit

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
                              context=self.context_for(slot), options=options,
                              protection=LOCKED_CONTROL if info["locked"] else ""))
            elif typ == "date":
                self.add(Area("date", clean_label(label) or "Date", slot, {"type": "sdt_text", "date": True},
                              context=self.context_for(slot), protection=LOCKED_CONTROL if info["locked"] else ""))
            elif empty_like:
                self.add(Area(self.kind_for(label), clean_label(label) or "Answer", slot, {"type": "sdt_text"},
                              context=self.context_for(slot), protection=LOCKED_CONTROL if info["locked"] else ""))
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

    def answer_cell(self, c) -> bool:
        """The cell holds an answer place of its own: a box or other control, a drawn answer blank of any kind (an
        underscore rule, leader dots or an ellipsis, digit boxes, a bracket, an underlined gap: every blank the
        engine itself maps as an answer), or a printed answer gap after a label read exactly as the engine's own
        answer-line reader reads one (inline_answer_gap: 'Temp:   °C', 'Weight:<em spaces>kg'; never a two-level
        label 'Cardiovascular:<tab>Heart sounds'). Linear in the cell's text and read once per cell: a merged cell
        beside twenty coded rows is asked twenty times (refutation F2, R3-3, R4-6, R4-10)."""
        key = ("answer_cell", id(c.el))
        if key not in self._grid:
            objects = self.cell_objects(c)
            self._grid[key] = BOX in objects or CHECKED in objects or "\x00" in objects or any(
                self.blank_spans(*self.ptext(x.el)) or self.inline_answer_gap(x) for x in c.children if x.kind == "p")
        return self._grid[key]

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

    # A number printed in a header option, in any legend form: '2 = Abnormal', '(2)', '2)', '1. Normal', '1.Normal',
    # '1)Normal', 'Normal (1.)', and a decimal '1.0 Normal' (read whole, so it never equals a code '1'). Never part of a
    # word ('12b').
    HEADER_NUMBER = re.compile(r"(?<![\w.])[(\[]?(\d{1,3}(?:\.\d+)?)(?:[.)\]:=\-\u2013]|(?![\w.]))")
    # In governing text (a title, lead, heading or row label): a number, the printed joiners between a code and its
    # meaning (spaces, brackets, '=', ':', '.', a dash, an arrow - never ',' ';' or '|', which end an entry), and a
    # run of words.
    LEGEND_NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:\.\d+)?(?!\w)")
    LEGEND_JOIN = r"[\s.:=()\[\]\-\u2013\u2014>\u2192\u21d2]*"
    LEGEND_WORDS = r"[^\W\d_]+(?:[ '\u2019/-]+[^\W\d_]+)*"
    LEGEND_ARROW = re.compile(r"=|->|=>|\u2192|\u21d2")

    @staticmethod
    def legend_words(text):
        """A printed meaning as its words: case, punctuation and 'and'/'or' at either end dropped ('Non-tender' is
        'non tender'; 'Not palpable' never equals 'palpable')."""
        words = re.findall(r"[^\W\d_]+", text.lower())
        while words and words[0] in ("and", "or"):
            words = words[1:]
        while words and words[-1] in ("and", "or"):
            words = words[:-1]
        return " ".join(words)

    def legend_entries(self, segment, meanings, codes):
        """(code, meaning) for every legend entry printed in one piece of governing text, or None when a number is
        printed next to an option's words in a form whose direction cannot be read.

        An entry is a number printed with '=' or an arrow ('1 = Normal', 'Abnormal = 1', '1 → Normal'), or a number
        printed next to words that contain an option ('1 Abnormal', '(1) Normal', '[1] Normal', 'Normal (1)',
        '1.Normal'), or one of two or more numbered items whose numbers are all the row's codes ('(1) Absent
        (2) Present'). Its meaning is the words on the side the legend prints them: the operator's side, else the
        one side naming an option, else the side the first entry of the same text used (refutation R3-2, R4-4)."""
        involves = lambda words: bool(words) and any(m and (" %s " % m) in (" %s " % words) for m in meanings)
        found = []
        for match in self.LEGEND_NUMBER.finditer(segment):
            # A legend entry is short: the words on each side are read within 120 characters, so a long printed
            # text costs linear time (refutation R4-6).
            following, preceding = segment[match.end():match.end() + 120], segment[max(0, match.start() - 120):match.start()]
            joined_after = re.match(self.LEGEND_JOIN, following).group()
            joined_before = re.search(self.LEGEND_JOIN + "$", preceding).group()
            after = re.match(self.LEGEND_WORDS, following[len(joined_after):])
            before = re.search(self.LEGEND_WORDS + "$", preceding[:len(preceding) - len(joined_before)])
            after = self.legend_words(after.group()) if after else ""
            before = self.legend_words(before.group()) if before else ""
            listed = bool(after) and bool(re.fullmatch(r"\s*[.):\]\-\u2013]\s*", joined_after))
            found.append((match.group(), after, before, bool(self.LEGEND_ARROW.search(joined_after)),
                          bool(self.LEGEND_ARROW.search(joined_before)), listed))
        numbered = [code for code, _, _, _, _, listed in found if listed]
        numbered_legend = len(numbered) >= 2 and all(code in codes for code in numbered)
        entries, direction = [], None
        for code, after, before, operator_after, operator_before, listed in found:
            if operator_after and operator_before:
                return None
            if operator_after or operator_before:
                side = "after" if operator_after else "before"
            else:
                sides = [name for name, words in (("after", after), ("before", before)) if involves(words)]
                if not sides and listed and numbered_legend:
                    sides = ["after"]
                if not sides:
                    continue
                side = sides[0] if len(sides) == 1 else direction
                if side is None:
                    return None
            direction = direction or side
            entries.append((code, after if side == "after" else before))
        return entries

    def legend_conflict(self, options, row, governing=""):
        """A printed header whose options also print numbers ('2 = Abnormal', '1.Normal') is a code legend. It agrees
        with a row only when each option prints exactly the code printed before the box under it; otherwise which
        box means which option is not certain (refutation F4, R3-2, R4-4). A legend printed in the governing text
        ('codes: 1 = Abnormal, 2 = Normal', 'Abnormal (1)', '[1] Abnormal') must name, for each code it prints,
        exactly the option printed over that code's box: its words equal the option's, so 'Not palpable' never
        agrees with 'Palpable' (R4-5). A legend whose direction cannot be read refuses the row. A header and
        governing text that print no legend never conflict."""
        codes = re.findall(r"(\d{1,3})\s*[☐☒]", self.ptext(row.el)[0])
        printed = [self.HEADER_NUMBER.findall(option) for option in options]
        if any(printed) and (len(codes) != len(options) or any(found != [code] for found, code in zip(printed, codes))):
            return True
        meanings = [self.legend_words(option) for option in options]
        # Each printed piece (heading, title, lead, row label) is read alone: a number in one never pairs with the
        # words of another.
        for segment in re.split(r" > | \| ", governing):
            entries = self.legend_entries(segment, meanings, codes)
            if entries is None:
                return True
            for code, meaning in entries:
                if code not in codes or len(codes) != len(options) or meanings[codes.index(code)] != meaning:
                    return True
        return False

    def coded_kind(self, label, options, context):
        """A coded response row records ONE code per row: one choice, whatever its label, title or heading says (R4-F3).
        A complete positive command in its label or its governing context (cell title, column headers, headings)
        asks for several codes the row cannot record: held, never widened. Returns the kind, or None with the reason
        in self._coded_problem."""
        self._coded_problem = ""
        if any(positive_command(text) for text in (label, context)):
            self._coded_problem = "A check-all instruction governs coded rows that each record one response."
            return None
        return "choice"

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
                    if kind is None:
                        complete = False;problem = self._coded_problem;break
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
                # ⚠️ A REFUSED SOURCE'S TEXT LINES ARE HELD WITH ITS ROWS (CI 36479289351): claiming only the rows left
                # the literal header to the text-option rule, which offered the header's words as options and would have
                # ticked the header line while the row's own boxes stayed empty. A line with its own box or blank is
                # still read on its own control (and a coded one is noted there), never on this source's structure.
                for slot in candidates + [p for p in paragraphs if self.text_only_line(p)]:
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

    def text_only_line(self, slot):
        """A paragraph with no box and no blank: it can become a field only by borrowing another line's structure."""
        return not self.box_units(slot) and not self.blank_spans(*self.ptext(slot.el))

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
    # A code printed against the question with no space: 'Score:0 ☐', 'Grade—0 ☐', 'Pain(0) ☐'. A bracketed code may
    # touch a word; a bare one follows a printed separator ('COVID-19' then a box is the question's own number, and
    # is harmless: no bare code follows it).
    CODE_GLUED = re.compile(r"(?:[(\[]\d{1,3}[a-z]?[)\]]|(?<=[:=/#\-\u2013\u2014])(?:\d{1,3}[a-z]?|[ivx]{1,4}|[a-z]))\s*$", re.I)

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
        # The first code may touch the question ('Pain score:0 ☐ 1 ☐ 2'): it is still printed before its box, and
        # read box-then-option every box would take the next box's code (refutation R4-3).
        before[0] = before[0] or bool(self.CODE_GLUED.search(segments[0]))
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
                kind = self.coded_kind(label, info["options"], context)
                if kind is None:
                    return [], self._coded_problem
                area = Area(kind, label, row,
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
                # Its text lines are held, as a refused tab-column source's are: no weaker rule re-reads its title or
                # header as a question of their own words. Its rows go on to the checkbox rule, which notes each one.
                for paragraph in (s for s in cell.children if s.kind == "p" and self.text_only_line(s)):
                    self.claimed.add(id(paragraph.el))
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
        """Every one-only or limited-count sentence printed in the form (limit_language: body, table cells, text
        boxes, positioned frames, page headers/footers, footnotes, endnotes), and every selection command in floating
        text, as (paragraph id, owner, sentence, where, targets). `targets` is what the sentence limits
        (limit_targets; "*" for a selection command in floating text). The owner is the question whose own source the
        sentence is, and nothing else is owned:
        - in a paragraph that prints a question's own boxes (boxed_guidance): the label printed directly before a run
          of at least two of them ("Exclusively breastfed? [ ] Yes [ ] No") and the text printed after them on the
          same line ("[ ] Y [ ] N [ ] NA (choose one)", "[ ] Neither", "[ ] Eye tearing in only ONE EYE"), unless it
          names a wider reach (WIDER_REACH: "tick one box only for every question", "for the question above") or
          starts a new label ("... [ ] No  Leave type (tick one):"). Text on an earlier line or after a line break is
          not that question's (R4-F9);
        - in a paragraph without boxes: its first sentence when it is a label carrying a complete one-only command
          (label_instruction) and at least two of that question's own boxes follow directly (label_owner); and, in a
          question of several sentences, its last sentence when it leads in to those boxes ("6. Investigator's
          opinion of the relationship ... Check applicable box:") and nothing in the paragraph names a wider reach
          ("Answer the questions below. Tick one box only:" governs more than the next boxes)."""
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
                    printed = paragraph_text(p)[0]
                    boxed = BOX in printed or CHECKED in printed
                    if boxed:
                        entries = self.boxed_guidance(p, printed)
                    else:
                        sentences = [x for x in re.split(r"(?<=[.!?;])\s+", text_of(p, own=True).strip()) if x]
                        entries = [(x, "label" if i == 0 else "lead" if i == len(sentences) - 1 and x.rstrip().endswith(":")
                                    else "") for i, x in enumerate(sentences)]
                    flagged = []
                    for sentence, role in entries:
                        limit = limit_language(sentence)
                        if limit or floating and floating_selection(sentence):
                            flagged.append((sentence, role, limit))
                    if not flagged:
                        continue
                    self._form_wide_nodes.append(p)
                    where = ("a text box in " if unit.tag == TXBX else "a positioned frame in " if framed else "") + part
                    for sentence, role, limit in flagged:
                        owner = None
                        if framed:
                            pass
                        elif role is True:
                            owner = p
                        elif role == "label":
                            owner = self.label_owner(p, sentence)
                        elif role == "lead" and not WIDER_REACH.search(text_of(p, own=True)):
                            owner = self.boxes_below(p)
                        found.append((id(p), owner, sentence, where, limit_targets(sentence) if limit else "*"))
            self._form_wide = found
        return self._form_wide

    def boxed_guidance(self, p, printed):
        """(sentence, owned by the paragraph's own question) for every sentence of a paragraph that prints boxes
        (see selection_guidance). The text after a question's box is that box's own answer or instruction ("[ ] Eye
        tearing in only ONE EYE" is an answer, never guidance for another question); a label before the boxes is owned
        only by a run of at least two of them (R3-F1: a lone box never owns "tick one")."""
        answers = self.question_boxes(p, printed)
        own = answers and self.box_run(p) >= 2
        clean = lambda text: re.sub(r"\s+", " ", re.sub("[\x00" + BOX + CHECKED + "]", " ", text)).strip()
        split = lambda text: [x for x in re.split(r"(?<=[.!?;])\s+", clean(text)) if x]
        first = min(i for i, ch in enumerate(printed) if ch in (BOX, CHECKED))
        out = []
        head = printed[:first].split("\n")
        for n, line in enumerate(head):
            sentences = split(line)
            for i, sentence in enumerate(sentences):
                label = n == len(head) - 1 and i == len(sentences) - 1
                out.append((sentence, own and label and not WIDER_REACH.search(sentence)))
        def own(sentence, answer):
            # A box's own answer text, or a trailing command that counts nothing of its own ("(choose one)"); a
            # trailing sentence that counts its own subject ("... Only one treatment may be recorded.") may govern
            # other questions too.
            if not answers or WIDER_REACH.search(sentence) or re.search(r"[:?]\s*$", sentence):
                return False
            if answer or not limit_language(sentence):
                return True
            targets = limit_targets(sentence)
            return targets == "*" or all(SELECTION_NOUN.fullmatch(x) for phrase in targets for x in phrase)
        line, *later = printed[first:].split("\n")
        for segment in re.split("[" + BOX + CHECKED + "]", line)[1:]:
            answer, *tail = re.split(r"\t{2,}| {4,}", segment, maxsplit=1)
            for i, sentence in enumerate(split(answer)):
                out.append((sentence, own(sentence, i == 0)))
            for sentence in split(tail[0] if tail else ""):
                out.append((sentence, own(sentence, False)))
        for sentence in (x for text in later for x in split(text)):
            out.append((sentence, False))
        return out

    @staticmethod
    def question_boxes(p, printed):
        """The paragraph's boxes are a question's own answers: native boxes, or printed glyphs that start the line or
        follow a label ending in ':', '?' or ')', each followed by its answer. Sample glyphs inside an instruction
        ("Mark [x] one box only, leave the others [ ]") are not a question."""
        if checkbox_nodes(p, own=True):
            return True
        parts = re.split("[" + BOX + CHECKED + "]", printed)
        label = re.sub(r"[\s\[(]+$", "", parts[0])          # a bracketed box: "Sex: (choose one) [ ] M [ ] F"
        return (not label.strip() or bool(re.search(r"\S\s*[:?)]$", label))) and all(x.strip(" \t])") for x in parts[1:])

    @staticmethod
    def box_run(p):
        """The boxes printed in `p` and in the paragraphs directly around it that start with a box (one option per
        line), counted up to two."""
        count = sum(paragraph_text(p)[0].count(ch) for ch in (BOX, CHECKED))
        for step in ("getprevious", "getnext"):
            node = getattr(p, step)()
            while count < 2 and node is not None and node.tag == q("w:p"):
                text = paragraph_text(node)[0]
                if not text.strip():
                    node = getattr(node, step)()
                    continue
                if text.lstrip(" \t[(")[:1] not in (BOX, CHECKED):
                    break
                count += sum(text.count(ch) for ch in (BOX, CHECKED))
                node = getattr(node, step)()
        return count

    def label_owner(self, p, sentence):
        """The block whose boxes the label `sentence` (the first sentence of paragraph `p`, which prints no box)
        introduces, or None: the next printed block when it starts with a box (the label above its own option lines,
        in a boxed cell, or beside the answer cell of its table row). A single box cannot satisfy "tick one" on its
        own, so an owner needs at least two boxes of its own (R3-F1): a lone box ("[ ] No community leave taken")
        never owns the command, which then may govern the next list."""
        cell = p.getparent()
        contained = cell is not None and cell.tag == q("w:tc") and bool(checkbox_nodes(cell, own=False))
        label = label_instruction(sentence, contained)
        # The label starts the paragraph as printed.
        start = re.match(r"\s*" + re.escape(label) + r"[.\s]*[:?]?", paragraph_text(p)[0]) if label else None
        if start is None or paragraph_text(p)[0][start.end():].strip():
            return None
        return self.boxes_below(p)

    def boxes_below(self, p):
        """The next printed block after `p` when it starts a run of at least two boxes of its own, else None."""
        block = self.next_printed(p)
        if block is None or not self.starts_with_box(block):
            return None
        # Its own boxes: the run of printed blocks that each start with a box, directly below the label.
        own, node = 0, block
        while node is not None and self.starts_with_box(node) and own < 2:
            own += sum(paragraph_text(para)[0].count(ch) for para in node.iter(q("w:p")) for ch in (BOX, CHECKED))
            last = node if node.tag == q("w:p") else next(reversed(list(node.iter(q("w:p")))), None)
            node = self.next_printed(last) if last is not None else None
        return block if own >= 2 else None

    @staticmethod
    def next_printed(p):
        """The next paragraph, table or block control printed after `p` in its container (text or a box); after the
        last one in a table cell, the next cell of its row, or, for a row that is that one cell (a question printed
        across the table), the first cell of the next row."""
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
            row = cell.getparent()
            if nxt is None and row is not None and row.tag == q("w:tr") and len(row.findall(q("w:tc"))) == 1:
                following = row.getnext()
                while following is not None and following.tag != q("w:tr"):
                    following = following.getnext()
                nxt = following.find(q("w:tc")) if following is not None else None
            return nxt
        return None

    @staticmethod
    def starts_with_box(el):
        """The first printed content of `el` is a box (a native control or a box glyph, bracketed or not: "[ ]")."""
        for para in el.iter(q("w:p")):
            text = paragraph_text(para)[0]
            if text.strip():
                return text.lstrip(" \t[(")[:1] in (BOX, CHECKED)
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

    def limited_selection_elsewhere(self, sources, stems=frozenset()):
        """Limited selection guidance outside this list's own source that no separate question owns and that is about
        this list (limit_reaches over its subject `stems`): (where, sentence), or None. Its reach cannot be read, so it
        may govern this list. (A body label directly above the list's own lines is part of its source and read there,
        never here.)"""
        return self.scope_limit({id(s.el) for s in sources}, stems)

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
        # The reason is kept: beside an explicit all-that-apply command an exclusive answer ("None") does not make
        # the list exclusive, while a single-answer question or count answers conflict with it (R4-F8).
        exclusive = any(YESNO.fullmatch(o) or OPTION_WORD.fullmatch(o)
                        or re.match(r"(?:yes|no|none|nil|not|n/?a|unknown)\b", o, re.I) for o in options)
        if (options and all(QUANTITY_OPTION.match(o) for o in options)) or SINGLE_QUANTITY.search(question):
            return {"kind": "choice", "single": "question"}
        if exclusive:
            return {"kind": "choice", "single": "answers"}
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
                if not history_selection(sentence) and not limit_language(sentence):
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
        # A single-answer word anywhere in the governing headings, the instructions or the owner ("Principal
        # treatment", "Highest level of care", "Record the current treatment.") keeps one answer (R3-F7): the
        # same vocabulary as a single-quantity owner question.
        single = bool(SINGLE_QUANTITY.search(scope))
        kind = "choice" if one or single else "multi_choice"
        stems = subject_stems(question, heading_context, *options)
        # Independence is never inferred past a limited selection instruction
        # printed anywhere else in the form (a parent heading, the section, the
        # preamble, a page header, a text box, below the list) that no separate
        # question owns: its reach cannot be read, so the list keeps one choice.
        # An explicit all-that-apply command beside such a limit is a conflict:
        # never narrowed to one choice, never widened; it is held (R3-F9).
        elsewhere = self.limited_selection_elsewhere(sources, stems) if kind == "multi_choice" else None
        if elsewhere and many:
            return {"problem": "The native-checkbox history's all-that-apply instruction conflicts with a limited "
                    "selection instruction printed elsewhere in the form (" + elsewhere[0] + ": " + elsewhere[1][:120]
                    + ") whose reach is unresolved; nothing was guessed."}
        if elsewhere:
            return {"kind": "choice", "note": "The native-checkbox history keeps one choice: a limited selection "
                    "instruction is printed elsewhere in the form (" + elsewhere[0] + ": " + elsewhere[1][:120]
                    + ") and which answers it governs is unresolved."}
        relation = {"relation": "native_checkbox_history", "question": question, "context": context,
                    "options": options, "cardinality": kind,
                    "sources": [{"part": s.part, "slot": s.path, "fingerprint": fingerprint(s.el)} for s in sources]}
        return {"kind": kind, "question": question, "context": context, "relation": relation,
                "single": "question" if kind == "choice" else ""}

    @staticmethod
    def option_families(text):
        """The OPTION_FAMILIES a printed option belongs to; -1 for a companion word ('N/A', 'Unknown')."""
        word = re.sub(r"^[\s(\[]+|[\s)\].:;,]+$", "", " ".join(option_text(text).lower().split()))
        found = {n for n, family in enumerate(OPTION_FAMILIES) if family.fullmatch(word)}
        return found | ({-1} if COMPANION_OPTION.fullmatch(word) else set())

    @staticmethod
    def option_shape(text):
        """A printed option's form: numbers as '9', letter runs as 'a', punctuation kept ('0.5 mg' and '1 mg' are
        '9 a'; 'A+' and 'O+' are 'a+')."""
        shape = re.sub(r"[^\W\d_]+", "a", re.sub(r"\d+(?:[.,]\d+)?", "9", option_text(text).lower().rstrip(".,;")))
        return " ".join(shape.split())

    @staticmethod
    def negation_pair(a, b):
        """One printed option is the other's negation ('Equal' / 'Unequal', 'Tender' / 'Non-tender')."""
        a, b = " ".join(option_text(a).lower().split()), " ".join(option_text(b).lower().split())
        return bool(a and b) and any(b == prefix + a or a == prefix + b for prefix in NEGATION_PREFIX)

    @staticmethod
    def option_sequence(options):
        """Two or more options counting from the start, each after the same printed word or none: '1', '2', '3';
        'I', 'II', 'III'; 'A', 'B'; 'Type 1', 'Type 2'."""
        romans = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]
        parts = [option_text(o).lower().rsplit(" ", 1) if " " in option_text(o) else ["", option_text(o).lower()]
                 for o in options]
        if len(parts) < 2 or len({lead for lead, _ in parts}) != 1:
            return False
        items = [item for _, item in parts]
        for sequence in ([str(n) for n in range(0, 21)], [str(n) for n in range(1, 21)], romans, list("abcdefghij")):
            if items == sequence[:len(items)]:
                return True
        return False

    def words_before_boxes(self, units, options):
        """Why a row of boxes may print each box's word BEFORE it ('Smoker: Yes ☐ No ☐ (tick one)'), or "".

        Read after-box, each box would take the next box's word. A row is read after-box when nothing but the question
        is printed before its first box, or when the words printed right before the first box (after the question's
        colon, or the whole text before it) have no mark of being an option. The marks are layout and printed form,
        never the absence of a word from a list (refutation F3, R3-1, R4-1, R4-2, R4-8):

        - held always: that word shares an option family, or is the negation, of an after-box word ('Allergies Yes ☐
          No'); a word is printed against the box after it (a gap); the words before the first box have the printed
          form of the words between the boxes ('Dose 0.5 mg ☐ 1 mg ☐', 'Blood type A+ ☐ O+ ☐', '... every day smoker
          ☐ Former smoker ☐'); or the text after the last box is a write-in or an instruction of its own ('Discussed
          with ____', 'If yes, list ____', 'Exact: ____'), so the last box has no word after it;
        - held unless the after-box words are provably the question's whole answer set (a closed family such as
          yes/no, a negation pair, a counted sequence): the word before the first box is itself an option word or
          starts a new capitalised phrase ('Urine protein Negative ☐', 'DNR status Full code ☐'); or the text after
          the last box is a companion ('Unknown', 'Not done') or an 'Other ____' write-in, which a form may print with
          no box of its own.

        A row with none of these marks is read after-box: read the other way, its last printed option would have no
        box at all."""
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
        # The question ends at its colon, a printed gap or its own answer blank ('Date: ____ Yes ☐ No ☐ N/A'): only
        # what follows is the word printed right before the first box.
        cuts = list(re.finditer(r"[:?]|\t| {2,}|_+|\.{2,}|…+|[\u25af\x00" + BOX + CHECKED + "]+", head))
        blank_cut = bool(cuts) and not re.fullmatch(r"[:?]|\t| {2,}", cuts[-1].group())
        # A bracketed selection instruction ('Sex: (choose one) ☐ M') is not an option word; a bracketed word ('Smoker:
        # (Yes) ☐ (No) ☐ N/A', 'Smoker [Yes] ☐') still is. A bracket drawn around a box ('Grade [☐] 1 [☐] 2') prints no
        # word at all (D35).
        tail = re.sub(r"\(([^()]*)\)", lambda m: " " if any(rx.search(m.group(1)) for rx in (CHECK_ONE, CHECK_ALL, EXPLICIT_ONE))
                      or re.search(r"\b(?:choose|select|tick|check|circle|mark|pick)\b", m.group(1), re.I) else m.group(0),
                      head[cuts[-1].end():] if cuts else head)
        tail = re.sub(r"[\[\]]", " ", tail)
        # The question's own condition or question clause ('If yes', 'If yes, how many', 'which side', 'how often') is
        # the question's; only what follows it may be the first box's option ('Smoker? If yes Yes ☐ No ☐ Unknown',
        # 'Diet: what type Normal ☐ Soft ☐'). 'When' begins an option ('When required ☐ Daily ☐'), never a clause.
        clause = re.compile(r"\s*(?:if\s+(?:not\s+)?|how\s+|what\s+|which\s+|where\s+)[^\W\d_]+[\s,:;]*", re.I)
        after_clause = False
        while clause.match(tail):
            tail, after_clause = tail[clause.match(tail).end():], True
        # The question, its clause, a rate ('how many per day'), or the unit of its own answer blank ('Weight ____ kg ☐
        # measured ☐ stated') ends right before the first box. After the question's colon a unit is an option ('Dose
        # unit: mg ☐ mcg ☐').
        unit = UNIT_TAIL.fullmatch(re.sub(r"[^\w\s\u00b0%/]", " ", re.sub(r"^\s*(?:per|a|an|each)\s+", "", tail, flags=re.I)).strip())
        if not re.search(r"[^\W\d_]", tail) or unit and (blank_cut or after_clause):
            return ""
        words = option_text(tail).split()
        grams = lambda chosen: [" ".join(chosen[:k]) for k in (1, 2, 3) if k <= len(chosen)]
        families = lambda texts: set().union(*(self.option_families(x) for x in texts)) if texts else set()
        ending = families([" ".join(words[-k:]) for k in (1, 2, 3) if k <= len(words)])
        # After the question's colon the tail starts at its first word ('Tobacco: Current every day smoker ☐').
        near = ending | (families(grams(words)) if cuts or after_clause else set())
        anywhere = families([" ".join(words[i:j]) for i in range(len(words)) for j in range(i + 1, min(len(words), i + 3) + 1)])
        own_last = re.split(r"\t{2,}| {4,}", units[-1][1])[0]
        own_last = own_last if re.search(r"\S", own_last) else units[-1][1]
        write_in = bool(re.search(r"_{2,}|\.{3,}|…|[\u25af\x00]|[^\W\d_]\s*:|\?", own_last)
                        or re.match(r"\s*(?:if|specify|please|comments?|list|describe|explain|details?)\b", own_last, re.I)
                        or any(rx.search(own_last) for rx in (CHECK_ONE, CHECK_ALL, EXPLICIT_ONE)))
        other_write_in = write_in and set(re.findall(r"[^\W\d_]+", own_last.lower())) <= {"other", "specify", "please",
                                                                                         "state", "describe", "details"} \
            and "other" in own_last.lower()
        after = [o for o in between if o] + ([last] if last and not write_in else [])
        after_families = [self.option_families(o) for o in after]
        core = [(o, f - {-1}) for o, f in zip(after, after_families) if f != {-1}]
        if (near - {-1}) & set().union(*after_families) or (-1 in ending and any(f - {-1} for f in after_families)) \
                or any(self.negation_pair(words[-1], o) or self.negation_pair(" ".join(words[-2:]), o) for o in after):
            return "(the word before the first box is one of the same printed options)"
        for raw in (u[1] for u in units[:-1]):
            if raw.strip() and gap_width(raw[:len(raw) - len(raw.lstrip())]) > gap_width(raw[len(raw.rstrip()):]):
                return "(a word is printed against the box after it)"
        shapes = {self.option_shape(o) for o in between if o}
        if len(shapes) == 1 and re.search(r"[9+%/<>=#\u00b0]", next(iter(shapes))) and \
                any(self.option_shape(" ".join(words[-k:])) in shapes for k in (1, 2, 3) if k <= len(words)):
            return "(the words before the first box have the printed form of the options between the boxes)"
        # The same last WORD ('... every day smoker ☐ Former smoker ☐'): printed brackets and numbers are not words.
        lettered = lambda text: re.findall(r"[^\W\d_][\w'\-]*", text.lower())
        ends = {lettered(o)[-1] for o in between if len(lettered(o)) > 1}
        if len(lettered(tail)) > 1 and ends == {lettered(tail)[-1]} and all(len(lettered(o)) > 1 for o in between if o):
            return "(the words before the first box have the printed form of the options between the boxes)"
        if write_in and not other_write_in:
            return "(the text after the last box is a write-in of its own, so the last box's word is printed before it)"
        titled = any(re.fullmatch(r"[a-z][\w'\-]*", a) and re.fullmatch(r"[A-Z][a-z]+(?:[-'][A-Za-z]+)*", b)
                     for a, b in zip(words, words[1:]))
        weak = bool(ending) or titled or -1 in self.option_families(last) or other_write_in
        if not weak:
            return ""
        closed = set.intersection(*(f for _, f in core)) & CLOSED_FAMILIES if core and all(f for _, f in core) else set()
        paired = bool(core) and all(any(self.negation_pair(o, x) for x, _ in core) for o, _ in core)
        counted = self.option_sequence([o for o, _ in core])
        if (closed - anywhere) or paired or counted:
            return ""
        return "(the words right before the first box may be the first box's option)"

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
            decision = {"kind": "checkbox", "note": ""}
            if len(units) > 1:
                # The question's own source: its label, the lines of its boxes and what is printed after them, the
                # other paragraphs of its own cells, the header of its column, a nested grid's parent question and its
                # own adjacent instructions (the plain paragraphs directly above it, when they are not printed between
                # it and another question).
                local, between, local_slots = self.adjacent_instructions(used_para or pslot)
                cell = self.host_cell(pslot)
                cells = []
                if cell is not None and self.owning_cell(pslot) is cell:
                    cells = [cell, *self.question_cells(cell.parent, cell.info["row"], cell.info["col"])]
                # (its column header is one of its question cells, read with the rest of its own source)
                source, shared = self.own_source_texts(g["paras"] + ([used_para] if used_para is not None else []), cells)
                local = ([nested["cardinality"]] if nested else []) + local + source
                between = between + shared
                own = {id(x.el) for x in [*g["paras"], *local_slots, *([used_para] if used_para is not None else []),
                                          *(nested["source_slots"] if nested else [])]}
                if cell is not None:
                    own.update(self.own_paragraph_ids([cell, *self.question_cells(cell.parent, cell.info["row"],
                                                                                    cell.info["col"])]))
                decision = self.cardinality(question, options, local=local, between=between, own=own,
                                            hint=self.text(g["paras"][0].el), where=" at " + pslot.id,
                                            context=self.context_for(anchor))
            if decision.get("problem"):
                # Never narrowed to one choice, never widened past a limit: the source is left for manual mapping.
                self.notes.append(decision["problem"])
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
                area = Area(decision["kind"], question or "Choose", anchor, target,
                            context=self.context_for(anchor), options=[o or "(option %d)" % (i + 1) for i, o in enumerate(options)],
                            extra_slots=extra)
                history = self.native_history_source(g, units, options, used_para)
                if (history and not history.get("problem") and decision["kind"] == "multi_choice"
                        and history["kind"] == "choice" and history.get("single") != "answers"):
                    # An explicit all-that-apply command is never narrowed to one answer: beside a single-answer
                    # question, count answers or a limit the history read, the list is held (R4-F8). An exclusive
                    # answer ("None") does not make an all-that-apply list exclusive.
                    history = {"problem": "Checkbox question at %s: its all-that-apply instruction conflicts with the "
                               "single answer its native-checkbox history reads (%s); nothing was guessed."
                               % (pslot.id, (question or "")[:120])}
                if history and not history.get("problem") and decision["kind"] == "multi_choice":
                    history = {k: v for k, v in history.items() if k != "note"}
                    history["kind"] = "multi_choice"
                    if "relation" in history:
                        history["relation"] = dict(history["relation"], cardinality="multi_choice")
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
                if area.kind == "choice" and decision.get("note") and not (history and history.get("note")):
                    self.notes.append(decision["note"])
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
                            local, between, local_slots = self.adjacent_instructions(q_slot)
                            decision = self.cardinality(qtext, words, local=local, between=between,
                                                        where=" at " + opt_slot.id, context=self.context_for(opt_slot),
                                                        own={id(x.el) for x in [q_slot, opt_slot, *local_slots]})
                            if decision.get("problem"):
                                self.notes.append(decision["problem"])
                            else:
                                if decision["note"]:
                                    self.notes.append(decision["note"])
                                self.add(Area(decision["kind"], clean_label(qtext), opt_slot,
                                              {"type": "text_options", "options": words}, context=self.context_for(opt_slot),
                                              options=words))
                            self.claimed.add(id(q_slot.el))
                            self.claimed.add(id(opt_slot.el))
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
                        local, between, local_slots = self.adjacent_instructions(q_slot)
                        decision = self.cardinality(qtext, words, local=local, between=between,
                                                    where=" at " + opts[0].id, context=self.context_for(opts[0]),
                                                    own={id(x.el) for x in [q_slot, *opts, *local_slots]})
                        if decision.get("problem"):
                            self.notes.append(decision["problem"])
                        else:
                            if decision["note"]:
                                self.notes.append(decision["note"])
                            self.add(Area(decision["kind"], clean_label(qtext), opts[0],
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

    def spanned_response_columns(self, tslot, row, run):
        """A header cell printed above the run's own column headers that spans exactly the run's columns ('RESPONSE
        OPTIONS' over 'All of the Time' .. 'DON'T KNOW'): the form prints those columns as ONE set of answers to each
        row's statement, which establishes the grid's orientation (R3-F6, R4-F6)."""
        first = run[0][0].info["col"]
        last = run[-1][0].info["col"] + run[-1][0].info["span"]
        ht = self.header_table(tslot)
        rows = [r for r in self.header_rows(ht) if ht is not tslot or r < row]
        return any(c.info["vmerge"] != "continue" and c.info["span"] >= 2 and c.info["col"] == first
                   and c.info["col"] + c.info["span"] == last and self.cell_text(c)
                   for r in rows for c in self.grid(ht).get(r, []))

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
            #     (a 'Name | Date | Signature' row is three answers, never one choice). Printed boxes under longer
            #     response headers ('All of the Time', 'Daily or Almost Daily') are one rating-grid row too (R3-F6),
            #     but only when the form prints those columns as one set of answers: a header cell above them spanning
            #     exactly those columns ('RESPONSE OPTIONS'). Without it the header shape alone does not establish the
            #     grid's orientation ('Diagnosed by a doctor | Currently taking medication for it' are two facts, not
            #     one answer): the boxes are left to the column rules, which hold a shared-row grid (R4-F6). Each
            #     statement row is ONE choice across its response columns, whatever its statement says (R4-F2). A
            #     column headed by a question ('Diagnosed?') is a question of its own.
            def question_header(text):
                return bool(re.search(r"[?:]", text) or SELECTION_ACT.search(text) or history_selection(text))
            candidates = []
            for r in ordered:
                cells = [c for c in sorted(rows[r], key=lambda c: c.info["col"]) if c.info["vmerge"] != "continue"]
                opt_cells = []
                for c in cells:
                    header = option_text(self.column_header(tslot, c.info["col"], r).strip("√✓✔*† "))
                    if id(c) in filler:
                        continue
                    boxed = self.cell_text(c) in (BOX, CHECKED)
                    short = len(header.split()) <= 3 and len(header) <= 24 and \
                        (is_option_word(header) or not FIELDISH.search(header))
                    response = boxed and len(header) <= 60 and not question_header(header)
                    if self.is_option_cell(c) and header and (short or response):
                        opt_cells.append((c, header, not short))
                cur = []
                for c, h, long in opt_cells:
                    if cur and cells.index(c) != cells.index(cur[-1][0]) + 1:
                        candidates.append((r, cur))
                        cur = []
                    cur.append((c, h, long))
                if cur:
                    candidates.append((r, cur))
            # A run under longer response headers is a rating-grid row only under a spanning response header.
            candidates = [(r, [(c, h) for c, h, _ in run]) for r, run in candidates
                          if not any(long for _, _, long in run) or self.spanned_response_columns(tslot, r, run)]
            shared = {}
            for r, run in candidates:
                shared[tuple(h for _, h in run)] = shared.get(tuple(h for _, h in run), 0) + 1
            accepted = []
            for r, run in candidates:
                if len(run) < 2:
                    continue
                headers = [h for _, h in run]
                if len(set(h.lower() for h in headers)) < len(headers):
                    continue                  # the same header over several cells: separate answers, not one choice
                # Headers that are not all answer words establish a row reading for printed boxes only when the form
                # prints them as answers: a spanning response header over them, or answer words among them ('Yes' /
                # 'No' / 'UNKNOWN' / 'SERVICE NOT AVAILABLE', 'Agree' .. 'REFUSED'). 'Diagnosed | Medicated' over
                # boxes are two facts about each row, never one answer (R4-F6): left to the column rules, which hold.
                boxed_run = all(self.cell_text(c) in (BOX, CHECKED) for c, _ in run)
                optionish = all(is_option_word(h) for h in headers) or shared[tuple(headers)] >= 3 and (
                    not boxed_run or any(response_word(h) for h in headers)
                    or self.spanned_response_columns(tslot, r, run))
                # A pair of blank side columns records independent values. The
                # printed axis alone does not instruct the author to choose a side.
                source = self.text(tslot.el)
                if ({h.lower() for h in headers} == {"left", "right"}
                        and all(self.is_empty_cell(c) for c, _ in run)
                        and not re.search(r"\b(?:select|choose|tick|check|circle|mark)\b", source, re.I)):
                    optionish = False
                if not optionish:
                    continue
                label = self.row_label(tslot, r, run[0][0].info["col"])
                if label:
                    accepted.append((r, run, headers, label))
            # A row whose printed boxes are not all one run (a second run of response columns, or a box under no
            # header) has no established row/column orientation: its runs are held, never read as two questions.
            held = set()
            for r in {r for r, _, _, _ in accepted}:
                cells = [c for c in sorted(rows[r], key=lambda c: c.info["col"]) if c.info["vmerge"] != "continue"]
                runs = [run for rr, run, _, _ in accepted if rr == r]
                segment, segments = [], []
                for c in cells:
                    if self.is_label_cell(c):
                        segments.append(segment)
                        segment = []
                    elif BOX in self.cell_text(c) or CHECKED in self.cell_text(c) or checkbox_nodes(c.el, own=False):
                        segment.append(c)
                segments.append(segment)
                for segment in segments:
                    mine = [run for run in runs if any(c is run[0][0] for c in segment)]
                    covered = {id(c) for run in mine for c, _ in run}
                    stray = [c for c in segment if id(c) not in covered and not question_header(
                        self.column_header(tslot, c.info["col"], r))]
                    if mine and (len(mine) > 1 or stray):
                        held.update(id(run[0][0]) for run in mine)
            grid_own = self.adjacent_instructions(tslot)[0] if accepted else []
            for r, run, headers, label in accepted:
                if id(run[0][0]) in held:
                    self.notes.append("Rating grid row '%s' at %s was left for manual mapping: its printed boxes are not "
                                      "one run of headed response columns, so which answers the row offers is not "
                                      "established." % (label[:60], run[0][0].id))
                elif any(positive_command(text) for text in [label, *grid_own] + [
                        self.cell_text(x) for c, _ in run for x in self.question_cells(tslot, r, c.info["col"])]):
                    # A grid row reads one answer per row; a several-answers command in the row, over its columns or
                    # in the grid's own instruction cannot be honoured.
                    self.notes.append("Rating grid row '%s' at %s was left for manual mapping: its printed all-that-apply "
                                      "instruction conflicts with the grid's one answer per row; nothing was guessed."
                                      % (label[:60], run[0][0].id))
                else:
                    boxes = [{"kind": "cell", "part": c.part, "slot": c.path} for c, _ in run]
                    self.add(Area("choice", label, run[0][0], {"type": "checkboxes", "boxes": boxes},
                                  context=self.context_for(run[0][0]), options=headers,
                                  extra_slots=[c for c, _ in run[1:]]))
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
                            decision = self.cardinality(txt, words, own={id(x) for o in [c, *opts] for x in o.el.iter(q("w:p"))},
                                                        where=" at " + opts[0].id, context=self.context_for(opts[0]))
                            if decision.get("problem"):
                                self.notes.append(decision["problem"])
                            else:
                                if decision["note"]:
                                    self.notes.append(decision["note"])
                                self.add(Area(decision["kind"], clean_label(txt), opts[0],
                                              {"type": "checkboxes", "boxes": boxes}, context=self.context_for(opts[0]),
                                              options=words, extra_slots=opts[1:]))
                            for o in opts:
                                for x in o.el.iter():
                                    self.claimed.add(id(x))
                            i = j
                            continue
                    i += 1
            # (b2) a checklist down a column: box cells in >= 3 data rows under one question header, each row
            #      labelled -> one question whose options are the row labels. Its boxes mark rows of independent
            #      items, so neither reading is printed by the layout alone: it accepts several rows only by the
            #      selection rule (Detector.cardinality: a complete all-that-apply command in its header or in its own
            #      instruction printed directly above the table, and no limit in reach), and one row only by a
            #      printed one-only rule. Anything else ('Continue', 'Mark (X) if continuing', 'Still taking') is held:
            #      one choice would assert an exclusivity the form never prints (R4-F11). Box cells left in two or
            #      more columns of the same rows are a grid whose rows the option-grid rule could not read: its
            #      row/column orientation is not established, so it is held, never read as column-wise lists (R3-F6).
            #      A table continuing a list takes that list's reading, held with it when it was held.
            unclaimed = {col: {r for r, c in items if not self.cell_has_claim(c.el)} for col, items in box_cols.items()}
            above_texts, above_between, above_slots = self.adjacent_instructions(tslot)
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
                # Other box columns share this column's rows: a grid. Only a column headed by its own question
                # ('Diagnosed?') is a column-wise question there; any other header is one of the rows' answers.
                item_rows = {r for r, _ in items}
                shares = any(other != col and item_rows & {r for r, _ in box_cols[other]} for other in box_cols)
                if (any(other != col and unclaimed[other] & unclaimed[col] for other in unclaimed)
                        or shares and not question_header(header)):
                    self.notes.append("Checkbox grid at %s was left for manual mapping: boxes in several columns share its "
                                      "rows, and which of them answer one row's question is not established. Column: %s"
                                      % (tslot.id, clean_label(header)[:80]))
                    for _, c, _ in labelled:
                        for x in c.el.iter():
                            self.claimed.add(id(x))
                    self._col_lists[(id(tslot), col)] = False
                    continue
                existing = self._col_lists.get((id(ht), col)) if ht is not tslot else None
                for _, c, _ in labelled:
                    for x in c.el.iter():
                        self.claimed.add(id(x))
                if existing is False:
                    # The list this table continues was held: its continuation is held with it.
                    self.notes.append("Checkbox list continued at %s was left for manual mapping with the list it "
                                      "continues. Column: %s" % (tslot.id, clean_label(header)[:80]))
                    continue
                if existing is not None:
                    # Its reading was taken over the whole form: every limit printed in this continuation was in its
                    # reach (scope_limit), and a printed count is never read against the number of rows.
                    existing.target["boxes"].extend(boxes)
                    existing.options.extend(lbl for _, _, lbl in labelled)
                    existing.extra_slots.extend(c for _, c, _ in labelled)
                    continue
                own = self.own_paragraph_ids([c for _, c in items]
                                             + [x for r, _ in items for x in self.question_cells(tslot, r, col)])
                own.update(id(x.el) for x in above_slots)
                options = [lbl for _, _, lbl in labelled]
                decision = self.cardinality(header, options, local=above_texts, between=above_between, own=own,
                                            where=" at " + first.id, context=self.context_for(first))
                if decision.get("problem"):
                    self.notes.append(decision["problem"])
                    self._col_lists[(id(tslot), col)] = False
                    continue
                if decision["kind"] != "multi_choice" and not decision["single"]:
                    self.notes.append("Checkbox column at %s was left for manual mapping: its boxes mark rows of "
                                      "independent items, and nothing printed says whether one row or several may be "
                                      "marked; one choice would assert an exclusivity the form does not print. Column: %s"
                                      % (first.id, clean_label(header)[:80]))
                    self._col_lists[(id(tslot), col)] = False
                    continue
                if decision["note"]:
                    self.notes.append(decision["note"])
                area = Area(decision["kind"], clean_label(header), first, {"type": "checkboxes", "boxes": boxes},
                            context=self.context_for(first), options=options, extra_slots=[c for _, c, _ in labelled[1:]])
                self.add(area)
                self._col_lists[(id(tslot), col)] = area
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
                        decision = self.cardinality(question, options, where=" at " + c0.id, context=self.context_for(c0),
                                                    own=self.own_paragraph_ids(
                                                        [cc for r, c, _ in g for cc in rows[r] if cc is c or cc.info["col"]
                                                         == c.info["col"] + c.info["span"]]
                                                        + [x for r, c, _ in g for x in self.question_cells(tslot, r, c.info["col"])]))
                        if decision.get("problem"):
                            self.notes.append(decision["problem"])
                            for _, c, _ in g:
                                for x in c.el.iter():
                                    self.claimed.add(id(x))
                            continue
                        if decision["note"]:
                            self.notes.append(decision["note"])
                        area = Area(decision["kind"], question or "Choose", c0,
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
                        label = self.instructed_item(tslot, rows, r, c) or label
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
    # Printed advice to the patient, never a request for the clinician's answer: it speaks to its reader as 'you'
    # ('... at your next appointment', '... when you phone us'), sends its reader to a clinician ('... to the nurse'), or
    # adds an instruction to act ('Note any dizziness and stop the tablets'). A clinician's request names the patient
    # or the team in the third person ('Describe discussion with the patient here') and stays a destination. A column
    # printing content ('Patient information', 'Instructions') holds printed content unless its header records what
    # was done ('Education provided') (refutation R3-5, R4-9).
    ADDRESSED = re.compile(r"\b(?:you|your|yours|yourself)\b|\b(?:phone|call|tell|ask|contact|inform|email|text|see|visit)\s+us\b|"
                           r"\b(?:to|tell|ask|call|phone|contact|inform|see)\s+(?:your|the|a|an)\s+(?:doctor|physician|nurse|"
                           r"pharmacist|gp|provider|care\s+team|clinic|surgery|midwife|dentist)\b", re.I)
    ACTION_ADVICE = re.compile(r"\b(?:and|then|or)\s+(?:stop|take|start|continue|avoid|call|phone|contact|tell|inform|seek|go|"
                               r"attend|return|reduce|increase|keep|rest|drink|eat|do\s+not|don'?t)\b", re.I)
    CONTENT_COLUMN = re.compile(r"\b(?:instructions?|information|advice|guidance|directions?|education)\b", re.I)
    RECORDED_COLUMN = re.compile(r"\b(?:provided|given|delivered|discussed|documented|completed|received|reviewed|done|"
                                 r"reinforced|explained)\b", re.I)

    def instructed_answer_cell(self, table, row, cell):
        """A plain cell of a data row whose printed text asks for the answer to be written in it ('If palpable,
        describe here', 'Describe any findings below'), under a printed column header and beside the row's own
        label; or 'Note if ... present.'. Its answer is appended below the instruction; the instruction never names
        another row's cell. Printed content ('Note: INR must be checked', 'Detail: bleeding, infection', 'Explain
        the procedure to the patient') is not a request to write there (refutation F6). Printed advice to the
        patient is withdrawn WITH A NOTE, so a clinician's request misread as advice is never lost silently (R4-9)."""
        text = self.cell_text(cell)
        header = self.column_header(table, cell.info["col"], row)
        if len(text) > 200 or not self.INSTRUCTED.match(text) \
                or not (self.INSTRUCTED_PLACE.search(text) or self.INSTRUCTED_REQUEST.match(text)) \
                or not self.cell_is_plain(cell) or self.row_kind(table, row) != "data":
            return False
        for paragraph in (x for x in cell.children if x.kind == "p"):
            printed, pieces = self.ptext(paragraph.el)
            if BOX in printed or CHECKED in printed or "\x00" in printed or self.blank_spans(printed, pieces):
                return False
        if not (header and self.row_label(table, row, cell.info["col"])):
            return False
        reason = ("it speaks to the patient" if self.ADDRESSED.search(text) else
                  "it tells the reader to act" if self.ACTION_ADVICE.search(text) else
                  "its column '%s' prints content" % clean_label(header)[:60]
                  if self.CONTENT_COLUMN.search(header) and not self.RECORDED_COLUMN.search(header) else "")
        if reason:
            self.notes.append("The cell at %s prints the instruction '%s', which reads as printed advice or content "
                              "(%s), so it was kept as printed text and is not an answer place; map it manually if "
                              "it asks for the clinician's answer." % (cell.id, clean_label(text)[:120], reason))
            return False
        return True

    # A printed value, never an item: a date, a time, a number or a dose ('01/02/2026', '08:30', '500 mg', '2 x 5 ml').
    MONTH_WORD = re.compile(r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|"
                            r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|am|pm|x", re.I)

    def value_text(self, text):
        if not re.search(r"\d", text):
            return False
        return all(OPTION_FAMILIES[14].fullmatch(word) or self.MONTH_WORD.fullmatch(word)
                   for word in re.findall(r"[^\W\d_]+", text))

    def instructed_item(self, table, rows, row, cell):
        """The item an instructed cell's row is about: the nearest printed label cell to its left that is not a value
        ('500 mg', '01/02/2026'), not a label merged over several rows, and not in a column that prints a label only
        on the first row of each group ('Abdomen' over Liver and Spleen); the nearest label otherwise, or "" (then
        the row's own label is kept) (refutation R3-5, R4-7)."""
        def grouped(col):
            return any(is_blank_text(self.cell_text(x)) for other in rows if other != row and self.row_kind(table, other) == "data"
                       for x in rows[other] if x.info["col"] == col and not x.info["vmerge"])
        items = [x for x in sorted(rows[row], key=lambda x: -x.info["col"]) if x.info["col"] < cell.info["col"]
                 and not x.info["vmerge"] and self.is_label_cell(x) and not self.value_text(self.cell_text(x))]
        own = [x for x in items if not grouped(x.info["col"])]
        return clean_label(self.cell_text((own or items)[0])) if items else ""

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

    def question_box_role_source(self, table):
        """(printed question, section) over a one-cell box, read for the box's DESTINATION ROLE only (destination_roles).

        Unlike rule_question_boxes' reading, a question paragraph holding a line break, a drawing or a field is still
        read, and so is a header or footer box: those are never mapped by the engine (so nothing here becomes a label),
        but a signing box printed that way is still a signing box. At most two empty paragraphs are skipped."""
        # roles-2 (residual L1:RR1-07): a bookmark, permission or proofing mark between the question and its box is no
        # paragraph and does not end the reading; a question wrapped in a block content control is read inside it; up
        # to four empty paragraphs are skipped.
        transparent = {q("w:bookmarkStart"), q("w:bookmarkEnd"), q("w:proofErr"), q("w:permStart"), q("w:permEnd"),
                       q("w:commentRangeStart"), q("w:commentRangeEnd")}
        node, skipped = table.el.getprevious(), 0
        while node is not None and (node.tag in (q("w:p"), q("w:sdt")) or node.tag in transparent):
            if node.tag in transparent:
                node = node.getprevious()
                continue
            if node.tag == q("w:sdt"):
                content = node.find(q("w:sdtContent"))
                inner = [x for x in content if x.tag == q("w:p")] if content is not None else []
                if not inner:
                    break
                node = inner[-1]
            raw = re.sub(r"\s+", " ", self.text(node)).strip()
            if raw:
                slot = self.index.by_el.get(id(node))
                section = self.question_box_context(slot)[0] if slot is not None and slot.parent is None else ""
                return raw, section
            skipped += 1
            if skipped > 4:
                break
            node = node.getprevious()
        return "", ""

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
                              extra_slots=blanks[1:], label_slot=ps))
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
    # A unit printed after an answer gap ('Weight:      kg', 'Temp:      °C', 'Pulse:      bpm').
    ANSWER_UNIT = re.compile(r"\(?\s*(?:mm|dd|yy|hh|units?|kg|cm|lbs?|in|minutes?|hours?|days?|years?|%|\u00b0\s?[CF]|bpm|"
                             r"mm\s?hg|mg|mcg|ml|mmol|breaths|weeks?|months?)\b", re.I)

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
                              {"type": "none", "drawing": n}, context=reason, protection=reason, structural=True))
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
                self.add(Area("initials", label or header or "Initials", c, {"type": "none"}, context=self.context_for(c),
                              structural=True))

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


# ─── destination roles: whether a place may receive an answer at all ───────────────────────────────────────────────
#: ⚠️ WHETHER A DESTINATION MAY RECEIVE AN ANSWER IS A DIFFERENT QUESTION FROM WHETHER THE ANSWER IS SUPPORTED. A model
#: (mapping or generation) never creates permission to write a signature, perform an attestation or change a protected
#: area. The permission comes ONLY from structure this engine already reads in the ORIGINAL:
#:   signing   - its signature and initials areas. A span area owns its line segment up to the next engine area,
#:               measured by each neighbour's FULL printed extent ('Printed name:    Signature: ____' keeps Name
#:               answerable; 'Signature: ____ (use black ink)' holds the whole segment). An inline control or legacy
#:               field area owns its line segment the same way. A caption over a writing line owns the line under it,
#:               and a writing line owns the caption the engine read its label from. A one-cell box whose question or
#:               section reads as signing or consent (the engine's question_box_signing, whatever the box prints),
#:               unless the engine maps answer areas INSIDE it (then it is a frame holding questions, and those areas
#:               carry their own roles).
#:               ⚠️ A LOG TABLE'S COLUMN IS NO ROLE (as on 43fcf214; refutation of 258650f2, L1:R1-03). Its rows are
#:               typed by the clinician only (table_rows is never generated), and a column read as signing by its
#:               printed header refused ordinary clinical columns - 'Visit type (initial/follow-up)', 'Dose (initial)',
#:               'Initial' under 'Troponin (ng/L)' - at save and at fill. Declared residual (L1:F7, pre-existing on
#:               43fcf214): a clinician's typed text in a 'Nurse initials' column exports, as a typed legacy value does.
#:   protected - protected areas and regions, legacy form-field protection, locked content controls (a control nested
#:               inside one keeps its own lock) and picture content controls.
#:   policy    - the printed patient-author role of a section and a printed review attestation cell (source_policy):
#:               a field there must carry that same requirement.
#: ⚠️ ONE WORDING READER DECIDES WHETHER A LABEL NAMES A SIGNING PLACE: signing_place (below), shared with the legacy
#: default path. The engine's kind rule reads more labels as signature/initials than that (every 'Initial ...' reading,
#: every '... signed' checklist state); such an area is still never generated, but it is not a role, so the clinician can
#: remove it and add the answer the form asks for. Every gate re-inspects the original (never the stored mapping), so a
#: removed engine field, a re-added manual field or a stored mapping cannot move a role.
ROLE_SIGNING, ROLE_PROTECTED, ROLE_POLICY = "signing", "protected", "policy"
#: roles-2: a place whose role the original's label and structure cannot establish (destination_state UNCERTAIN). It
#: refuses nothing (it is not in ROLE_ORDER): a field there is HELD - never generated, its generated or accepted text
#: refused at save and finalization, a clinician's own typed value allowed (role_holds).
ROLE_UNCERTAIN = "uncertain"
ROLE_ORDER = (ROLE_SIGNING, ROLE_PROTECTED, ROLE_POLICY)
ROLE_REFUSALS = {
    ROLE_SIGNING: ("This place is a signing, initials or consent area of the original form. It never takes a typed or "
                   "generated answer: only a Signature or Initials field may sit there, and it is completed by hand."),
    ROLE_PROTECTED: "This place is protected on the original form and remains unchanged; no answer can be written there.",
    ROLE_POLICY: ("This place carries a printed authorship or review requirement on the original form, and the field "
                  "there does not carry that same requirement. Review the mapping again."),
}
ROLE_CODES = {ROLE_SIGNING: "protected_signing_area", ROLE_PROTECTED: "protected_signing_area",
              ROLE_POLICY: "mapping_mismatch"}
ROLE_REGION = "This area is protected on the original form and remains unchanged."
ROLE_FORM_FIELD = "This legacy form field is protected on the original form and remains unchanged."
ROLE_SIGNING_BOX = "Signing or consent box: it is completed by hand after the actual signing act."
ROLE_PICTURE = ("This place holds a picture content control of the original form (a signature image or a photograph); "
                "it takes no typed or generated answer.")
UNCERTAIN_REASON = ("Needs your review: the printed form does not show whether this is a signing or initials place or an "
                    "ordinary answer. It is never filled from the notes. If it is an answer, enter it yourself.")


def _place_id(part, path):
    return "%s#%s" % (part, path)


def _root_of(place):
    part, _, path = str(place).partition("#")
    return part + "#" + "/".join(path.split("/")[:2])


class _PlaceReader:
    """Where a field writes, as slot ids of the ORIGINAL, with code-point offsets inside a paragraph when the write is a
    part of it (a span, an insertion, a printed glyph box, an option word) - the same reading for the engine's own
    areas (a role's extent) and for any field of any mapping (what it would write)."""

    def __init__(self, index):
        self.index = index
        self._text = {}

    def text(self, pslot):
        if pslot.id not in self._text:
            self._text[pslot.id] = paragraph_text(pslot.el)
        return self._text[pslot.id]

    def inline(self, parent_id, child_id):
        """The offsets of an inline content control or legacy form field inside its own paragraph, or None."""
        parent, child = self.index.by_id.get(parent_id), self.index.by_id.get(child_id)
        if parent is None or child is None or parent.kind != "p" or child.parent is not parent \
                or child.kind not in ("sdt", "ff"):
            return None
        for pc in self.text(parent)[1]:
            if pc.kind == "obj" and pc.node is child.el:
                return pc.start, pc.end
        return None

    def of(self, field):
        """[(slot id, start, end)]; start/end None means the whole slot. Never empty: a field that writes nowhere
        readable is read as writing its whole anchor (fail closed)."""
        loc = field.get("locator") or {}
        target = loc.get("target") or {}
        part, typ = loc.get("part"), target.get("type")
        anchors = [(loc.get("part"), loc.get("slot"))] + [(c.get("part"), c.get("slot"))
                                                          for c in target.get("copies", []) or [] if isinstance(c, dict)]
        out = []
        if typ == "span":
            try:
                start, end = int(target["start"]), int(target["end"])
            except (KeyError, TypeError, ValueError):
                start = end = None
            if start is not None and target.get("shape") == "after_label":
                end = start
            if start is not None and end < start:
                start = end = None
            out.extend((_place_id(p, path), start, end) for p, path in anchors)
        elif typ == "checkboxes":
            for box in target.get("boxes", []) or []:
                if not isinstance(box, dict):
                    continue
                path = str(box.get("slot") or "")
                if box.get("kind") == "glyph" and path.endswith("/glyphs"):
                    pid = _place_id(box.get("part"), path[:-len("/glyphs")])
                    pslot, at = self.index.by_id.get(pid), None
                    if pslot is not None and pslot.kind == "p":
                        boxes, n = glyph_boxes(pslot.el), box.get("glyph")
                        if isinstance(n, int) and 0 <= n < len(boxes):
                            pc, k, _ = boxes[n]
                            at = pc.start + k
                    out.append((pid, at, at + 1) if at is not None else (pid, None, None))
                else:
                    out.append((_place_id(box.get("part"), path), None, None))
        elif typ == "paragraph_options":
            for p, _ in anchors:
                out.extend((_place_id(p, path), 0, 0) for path in target.get("paragraphs", []) or [])
        elif typ == "text_options":
            printed = [str(o) for o in printed_options(field)]
            for p, path in anchors:
                pslot = self.index.by_id.get(_place_id(p, path))
                if pslot is None or pslot.kind != "p":
                    out.append((_place_id(p, path), None, None))
                    continue
                text = self.text(pslot)[0]
                for i, option in enumerate(printed):
                    nth = sum(1 for j in range(i) if printed[j].strip() == option.strip())
                    m = option_word_match(text, option, nth)
                    out.append((pslot.id, m.start(), m.start()) if m else (pslot.id, None, None))
        elif typ == "table_rows":
            table = self.index.by_id.get(_place_id(part, target.get("table")))
            rows, columns = set(target.get("rows") or []), set(target.get("columns") or [])
            cells = [c.id for c in (table.children if table is not None else [])
                     if c.kind == "tc" and c.info["row"] in rows and c.info["col"] in columns]
            out.extend((c, None, None) for c in cells)
            if not cells:
                out.append((_place_id(part, target.get("table")), None, None))
        elif typ != "none":
            out.extend((_place_id(p, path), None, None) for p, path in anchors)
        if typ == "paragraph":
            out.extend((_place_id(x.get("part"), x.get("slot")), None, None)
                       for x in loc.get("extra", []) or [] if isinstance(x, dict))
        if not out:
            out.append((_place_id(loc.get("part"), loc.get("slot")), None, None))
        return out

    def touches(self, place, role):
        pid, s, e = place
        rid, rs, re_ = role["place"], role["start"], role["end"]
        if any(pid == x or pid.startswith(x + "/") for x in role.get("except") or ()):
            return False
        if pid == rid:
            if rs is None or s is None:
                return True
            return rs <= s < re_ if s == e else (s < re_ and e > rs)
        if pid.startswith(rid + "/"):
            if rs is None:
                return True
            inner = self.inline(rid, pid)
            return inner is None or (inner[0] < re_ and inner[1] > rs)
        if rid.startswith(pid + "/"):
            if s is None:
                return True
            inner = self.inline(pid, rid)
            if inner is None:
                return True
            return inner[0] <= s < inner[1] if s == e else (s < inner[1] and e > inner[0])
        return False


def _role(cls, source, place, start, end, reason, requires=None):
    role = {"class": cls, "source": source, "place": place, "start": start, "end": end, "reason": reason}
    if requires:
        role["requires"] = requires
    return role


def destination_roles_of(package) -> list:
    """Every destination role of the ORIGINAL package (see the section comment). Read-only."""
    return _role_reading(package)[0]


def _extent(reader, field):
    """Where a field's printed area lies, as reader.of reads it, except that an 'after_label' span keeps its whole printed
    extent (the spaces or tab after its label), not only its insertion point: a neighbour's segment ends there."""
    places = reader.of(field)
    target = (field.get("locator") or {}).get("target") or {}
    if target.get("type") == "span" and target.get("shape") == "after_label":
        try:
            start, end = int(target["start"]), int(target["end"])
        except (KeyError, TypeError, ValueError):
            return places
        if end >= start:
            return [(pid, start, end) if s is not None else (pid, s, e) for pid, s, e in places]
    return places


def _writing_line(text) -> bool:
    """A paragraph printed only as a writing line: underscores, dots or dashes (at least three), nothing else."""
    visible = re.sub(r"\s", "", text or "")
    return len(visible) >= 3 and re.fullmatch(r"[_.\u2026\u2025\u00b7\-\u2013\u2014]+", visible) is not None


def _role_reading(package):
    """(roles, the engine's own option groups as box keys - the boxes one engine choice area answers together)."""
    detector = Detector(package)
    areas, _ = detector.detect()
    index = detector.index
    reader = _PlaceReader(index)
    engine = [area_to_field(n + 1, a) for n, a in enumerate(areas)]
    source_policy.annotate(detector, engine)
    roles = []
    # Every paragraph offset an engine area occupies (by its full printed extent): the boundaries of a line segment.
    occupied, engine_places = {}, set()
    for field in engine:
        for pid, start, end in _extent(reader, field):
            engine_places.add(pid)
            slot = index.by_id.get(pid)
            if start is None and slot is not None and slot.parent is not None and slot.kind in ("sdt", "ff"):
                inner = reader.inline(slot.parent.id, pid)
                if inner is not None:
                    occupied.setdefault(slot.parent.id, []).append((inner, field["key"]))
            elif start is not None:
                occupied.setdefault(pid, []).append(((start, end), field["key"]))

    def segment(pid, start, end, key):
        # The line segment an area at [start, end) owns: from the end of the engine area before it to the start of the
        # one after it (the paragraph's end included, where an insertion after the printed text would go).
        others = [rng for rng, other in occupied.get(pid, []) if other != key]
        low = max([b for a, b in others if b <= start], default=0)
        pslot = index.by_id.get(pid)
        length = len(reader.text(pslot)[0]) if pslot is not None and pslot.kind == "p" else end
        high = min([a for a, b in others if a >= max(start, end)], default=length + 1)
        return low, max(high, end, low + 1)

    def line_role(cls, source, slot, reason, key):
        # An inline content control or legacy field owns its line segment in the paragraph that holds it.
        if slot is None or slot.parent is None or slot.kind not in ("sdt", "ff"):
            return
        inner = reader.inline(slot.parent.id, slot.id)
        if inner is not None:
            low, high = segment(slot.parent.id, inner[0], inner[1], key)
            roles.append(_role(cls, source, slot.parent.id, low, high, reason))

    signing = ROLE_REFUSALS[ROLE_SIGNING]
    for area, field in zip(areas, engine):
        places = reader.of(field)
        anchor = _place_id(field["locator"]["part"], field["locator"]["slot"])
        if area.protection:
            for pid in dict.fromkeys([anchor] + [pid for pid, _, _ in places]):
                roles.append(_role(ROLE_PROTECTED, "protected_area", pid, None, None, area.protection))
        elif area.kind in SIGNING_KINDS:
            state = area_destination(area)
            if not area.structural and state["state"] == STATE_ORDINARY:
                # The kind rule's reading of a label the destination state does not hold (no evidence either way):
                # never generated, but not a role - the clinician may replace it with the answer it asks.
                continue
            # roles-2: a place the state establishes as signing is a SIGNING role (refused to every other field); a place
            # whose role it cannot establish is an UNCERTAIN role (a field there is held, never refused).
            cls = ROLE_SIGNING if area.structural or state["state"] == STATE_PROTECTED else ROLE_UNCERTAIN
            why = signing if cls == ROLE_SIGNING else UNCERTAIN_REASON
            for pid, start, end in places:
                if start is None:
                    roles.append(_role(cls, "signing_area", pid, None, None, why))
                    line_role(cls, "signing_area", index.by_id.get(pid), why, field["key"])
                    continue
                low, high = segment(pid, start, end, field["key"])
                roles.append(_role(cls, "signing_area", pid, low, high, why))
                # A caption with no blank of its own ('Consultant signature:') is signed on the writing line under it.
                pslot = index.by_id.get(pid)
                if pslot is not None and pslot.kind == "p" and not reader.text(pslot)[0][start:].strip():
                    after = pslot.el.getnext()
                    below = index.by_el.get(id(after)) if after is not None else None
                    if below is not None and below.kind == "p" and below.parent is pslot.parent \
                            and _writing_line(reader.text(below)[0]):
                        roles.append(_role(cls, "signing_line", below.id, None, None, why))
            if area.label_slot is not None:
                # The caption paragraph the engine read this writing line's label from belongs to the same place.
                roles.append(_role(cls, "signing_caption", area.label_slot.id, None, None, why))
    for region in sorted(detector.protected_regions):
        roles.append(_role(ROLE_PROTECTED, "protected_region", region, None, None, ROLE_REGION))
    # A one-cell box whose printed question or section reads as signing or consent (or whose question the destination
    # state holds, roles-2) is a signing box, whatever it prints. The answer areas the engine maps INSIDE it whose own
    # destination is ordinary ('Patient name: ____', 'Date: ____') are excepted; a held one (the box's line, a person's
    # line, 'Signature, date') carries its own role, and the rest of the box stays the box's. A box the engine mapped AS
    # an answer is held by its own area's role (assign_destinations).
    ordinary_places = {pid for area, field in zip(areas, engine)
                       if area_destination(area)["state"] == STATE_ORDINARY and area.kind not in SIGNING_KINDS
                       for pid, _, _ in _extent(reader, field)}
    for cell_id, (state, _) in detector._question_box_cells().items():
        if cell_id in engine_places:
            continue
        cls = ROLE_SIGNING if state["state"] == STATE_PROTECTED else ROLE_UNCERTAIN
        role = _role(cls, "question_box_signing", cell_id, None, None,
                     ROLE_SIGNING_BOX if cls == ROLE_SIGNING else UNCERTAIN_REASON)
        inside = sorted(pid for pid in ordinary_places if pid.startswith(cell_id + "/"))
        if inside:
            role["except"] = inside
        roles.append(role)
    # A writing line a signing or uncertain caption governs, where the engine found no area (a bordered paragraph rule,
    # a fullwidth line - residual L1:F9): the role refuses a manual text field there, or holds it.
    for pid, start, end, state, _ in detector.destination_places:
        cls = ROLE_SIGNING if state["state"] == STATE_PROTECTED else ROLE_UNCERTAIN
        if start is not None:
            # The line owns its segment of the paragraph, up to the next engine area (an insertion after it included).
            start, end = segment(pid, start, end, None)
        roles.append(_role(cls, "governed_line", pid, start, end, signing if cls == ROLE_SIGNING else UNCERTAIN_REASON))
    for slot in index.slots:
        if slot.kind == "ff" and ff_text_protection(slot.el):
            roles.append(_role(ROLE_PROTECTED, "form_field_protection", slot.id, None, None, ROLE_FORM_FIELD))
        elif slot.kind == "sdt" and slot.info.get("locked") and slot.info.get("type") != "checkbox":
            role = _role(ROLE_PROTECTED, "locked_control", slot.id, None, None, LOCKED_CONTROL)
            # ⚠️ A control nested inside a locked one keeps its OWN lock: the form's author left it unlocked to be
            # answered (a locked frame around unlocked answer controls), so only the frame's own content is protected.
            nested = [x.id for x in index.slots if x.kind == "sdt" and x.id.startswith(slot.id + "/")
                      and not x.info.get("locked")]
            if nested:
                role["except"] = nested
            roles.append(role)
        if slot.kind == "sdt" and slot.info.get("type") == "picture":
            roles.append(_role(ROLE_PROTECTED, "picture_control", slot.id, None, None, ROLE_PICTURE))
            line_role(ROLE_PROTECTED, "picture_control", slot, ROLE_PICTURE, None)
    for root, source in source_policy.section_sources(detector).items():
        if source:
            roles.append(_role(ROLE_POLICY, "source_policy", root, None, None, ROLE_REFUSALS[ROLE_POLICY],
                               {"source_author": "patient", "source": source}))
    for field in engine:
        policy = field.get("answer_policy")
        if isinstance(policy, dict) and "attestation" in policy:
            for pid, _, _ in reader.of(field):
                roles.append(_role(ROLE_POLICY, "attestation", pid, None, None, ROLE_REFUSALS[ROLE_POLICY],
                                   {"attestation": policy["attestation"],
                                    "attestation_source": policy["attestation_source"]}))
    choices = [sorted(box_key(box) for box in field["locator"]["target"].get("boxes", []))
               for field in engine if field["kind"] in ("choice", "multi_choice", "checkbox")
               and field["locator"]["target"].get("type") == "checkboxes"]
    return roles, [group for group in choices if group]


def area_destination(area) -> dict:
    """The destination state of an engine area: the structural reading Detector.assign_destinations recorded, else its
    printed label's own reading."""
    return area.destination if isinstance(area.destination, dict) else destination_state(area.label)


def role_allows(field, role) -> bool:
    """A signature/initials field and a write-protected field never take an answer, so they may sit on any role place;
    a policy place also takes a field carrying exactly its printed requirement. Nothing else may touch a role."""
    if field.get("kind") in SIGNING_KINDS or field.get("write_protected"):
        return True
    if role["class"] == ROLE_POLICY:
        policy = field.get("answer_policy")
        policy = policy if isinstance(policy, dict) else {}
        return all(policy.get(name) == value for name, value in role["requires"].items())
    return False


def role_violations(reader, fields, roles) -> dict:
    """{field key: {class, source, place, reason}} for every field whose writes touch a role place it may not take."""
    by_root = {}
    for role in roles:
        by_root.setdefault(_root_of(role["place"]), []).append(role)
    out = {}
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        places = reader.of(field)
        near = [r for pid in dict.fromkeys(_root_of(p[0]) for p in places) for r in by_root.get(pid, [])]
        for cls in ROLE_ORDER:
            hit = next((r for r in near if r["class"] == cls and not role_allows(field, r)
                        and any(reader.touches(place, r) for place in places)), None)
            if hit is not None:
                out[str(field.get("key"))] = {"class": cls, "source": hit["source"], "place": hit["place"],
                                              "reason": ROLE_REFUSALS[cls]}
                break
    return out


def role_holds(reader, fields, roles, violations=None, *, every=False) -> dict:
    """{field key: {class, source, place, reason}} for every field (not a Signature/Initials field, not write-protected,
    not already a violation) whose writes touch an UNCERTAIN place: never generated, its generated or accepted text
    refused at save and finalization; a clinician's own typed value is allowed. every=True reads every field, whatever
    its kind (what the review page says needs review)."""
    violations = {} if every else (violations or {})
    uncertain = [r for r in roles if r["class"] == ROLE_UNCERTAIN]
    if not uncertain:
        return {}
    by_root = {}
    for role in uncertain:
        by_root.setdefault(_root_of(role["place"]), []).append(role)
    out = {}
    for field in fields or []:
        if not isinstance(field, dict) or str(field.get("key")) in violations:
            continue
        if not every and (field.get("kind") in SIGNING_KINDS or field.get("write_protected")):
            continue
        places = reader.of(field)
        near = [r for pid in dict.fromkeys(_root_of(p[0]) for p in places) for r in by_root.get(pid, [])]
        hit = next((r for r in near if any(reader.touches(place, r) for place in places)), None)
        if hit is not None:
            out[str(field.get("key"))] = {"class": ROLE_UNCERTAIN, "source": hit["source"], "place": hit["place"],
                                          "reason": UNCERTAIN_REASON}
    return out


def destination_roles(data: bytes, fields=None) -> dict:
    """The role report of an original: its roles (class, source, place, span), for `fields` (any mapping) every field
    whose writes touch a role place it may not take ('violations') and every field held on an uncertain place
    ('held'), and the role reading that judged them. Read-only; the isolated parser's 'roles' operation."""
    package = open_package(data)
    roles, choices = _role_reading(package)
    reader = _PlaceReader(SlotIndex(package))
    violations = role_violations(reader, fields or [], roles)
    return {"contract": CONTRACT, "reading": ROLE_READING,
            "roles": [{k: v for k, v in r.items() if k != "requires"} for r in roles],
            "violations": violations, "held": role_holds(reader, fields or [], roles, violations),
            "uncertain_places": sorted(role_holds(reader, fields or [], roles, every=True)), "choices": choices}


#: ⚠️ THE ONE READER OF WHETHER A PRINTED LABEL NAMES A SIGNING PLACE (a signature or initials area): the legacy default
#: path's role (never generated; generated or accepted text refused) and, on contract v3, whether an area the kind rule
#: typed signature/initials is a destination role. It FAILS CLOSED: every label naming a signature, 'signed by',
#: initials or a signature/initials-and-date place is a signing place, and only two POSITIONAL readings are released,
#: each measured as a clinical reading rather than a place:
#:   - 'signed' closing a label after other words, with no agent: a checklist state ('Consent form signed', 'Time
#:     signed', 'Signed consent in notes' - a leading 'signed' followed by an ordinary word);
#:   - 'initial' followed by an ordinary word or a number: the adjective ('Initial assessment', 'Initial 12-lead ECG');
#:   - 'initial' closing a label after a dash separator: a qualifier ('Troponin — Initial', DASH_QUALIFIER_INITIAL).
#: An ordinary word is anything outside a CLOSED class of function words (_ACT_WORDS: where or what an imperative 'sign'
#: or 'initial' acts on) - so 'Signed (Consultant)', 'Initial here', 'Initial each page', 'Sign here' stay places.
#: ⚠️ The earlier restriction ('signed' only with a later 'by'; 'initial' before ANY word) released 'Signed (GP)', 'Signed
#: (patient)', 'Initial here' and 'Initial each page', and generation filled them. Declared residuals, held (never
#: generated; the clinician types the value, and it exports): 'Consent form signed by patient', 'Patient signature
#: obtained', 'Troponin (initial)', 'Initial / repeat', a bare 'Initial' - the same wording prints a real signing place
#: ('Note signed by attending physician', 'Patient signature', 'Nurse (initial)', 'Initial:').
_ACT_WORDS = ("here|there|below|above|beside|overleaf|opposite|each|every|all|both|the|this|these|those|if|to|where"
              "|when")
_INVISIBLE = re.compile("[\u00ad\u180e\u200b-\u200f\u2060-\u2064\ufeff]")
SIGNATURE_PLACE = re.compile(r"\bsignatures?\b", re.I)
SIGNED_PLACE = re.compile(
    r"^(?:please\s+)?(?:electronically\s+|digitally\s+)?(?:counter-?|co-?|e-?)?signed"
    r"(?=\s*$|\s*[^\w\s]|\s+(?:" + _ACT_WORDS + r"|and|or|by|for|on|off)\b)"
    r"|\b(?:counter-?|co-?)?signed\b.*\bby\b"
    r"|\bsign(?:ed)?\s+(?:" + _ACT_WORDS + r")\b"
    r"|^(?:please\s+)?sign\s*(?:\band\b|\bor\b|&|\+|/)", re.I)
INITIALS_PLACE = re.compile(r"\binitials\b|\binitial(?=\s*$|\s*[^\w\s]|\s+(?:box|" + _ACT_WORDS + r"|and|or)\b)", re.I)
#: The measured over-read of the engine's question_box_signing: the adjective 'initial' ('Describe the initial
#: presentation?', a section 'Initial assessment'). A signing verb still governs once it is removed.
ADJECTIVE_INITIAL = re.compile(r"\binitial(?=\s+(?!(?:box|" + _ACT_WORDS + r"|and|or)\b)[^\W_])", re.I)
#: A closing 'initial' after a DASH separator is a qualifier of the printed question ('Troponin — Initial' beside
#: 'Troponin — Repeat'): a NARROWING of INITIALS_PLACE's closing arm, never a new signing word (refutation of
#: a32243eb, usefulness: 43fcf214 generated this reading and a32243eb held it). Released like 'signed' closing a label
#: after other words - and with the same declared cost: '<person> — Initial' is released too, exactly as 43fcf214
#: released it. 'Initial' alone, 'Initial:', '(initial)' and 'Nurse initial' stay places.
DASH_QUALIFIER_INITIAL = re.compile(r"(?<=\w)\s*[\u2013\u2014]\s*initial\s*$|(?<=\w)\s+-\s+initial\s*$", re.I)
BOX_SIGNING_VERB = re.compile(r"\b(?:counter|under|co|re)[ -]?sign|\bsign(?:ed|ing|off|offs)\b|\bsign\s+(?:"
                              + _ACT_WORDS + r")\b", re.I)


def _plain(label) -> str:
    text = unicodedata.normalize("NFKC", str(label or ""))
    return clean_label(_INVISIBLE.sub("", text), limit=1000).casefold()


def signing_place(label) -> str:
    """'signature', 'initials' or '' for a PRINTED label (see the section comment above)."""
    text = _plain(label)
    if not text:
        return ""
    if SIGNATURE_DATE_PAIR.search(text):
        return "signature"
    if INITIALS_DATE_PAIR.search(text):
        return "initials"
    if DATE_LABEL.search(text):
        return ""
    if SIGNATURE_PLACE.search(text) or SIGNED_PLACE.search(text):
        return "signature"
    if INITIALS_PLACE.search(DASH_QUALIFIER_INITIAL.sub("", text)):
        return "initials"
    return ""


def base_role(label) -> str:
    """The f5fe720f role of a PRINTED label (the kind rule types it signature/initials AND signing_place names a signing
    place): what destination_state falls back to wherever its own grammar does not decide."""
    text = _plain(label)
    kind = kind_rule(text)
    return kind if kind in SIGNING_KINDS and signing_place(text) else ""


# ─── destination state (roles-2): ONE decision for every gate, both engines ─────────────────────────────────────────
#: ⚠️ THREE STATES, NOT A BINARY READER. Five rounds refuted a binary wording reader in both directions: every release
#: arm leaked a signing place ('Nurse — Initial', 'Witness sign'), every fail-closed arm over-held a clinical label
#: ('Troponin (initial)', 'Consent form signed by patient'). The difference here is where a vocabulary miss lands:
#:   ordinary  - generated. ONLY on positive evidence of a clinical or checklist reading (ORDINARY_EVIDENCE): an
#:               attributive or sequence-option 'initial', a measured head or a printed unit before a qualifier
#:               'initial', a state participle closing a signature ('... signature obtained'), a document subject of
#:               'signed' with a person agent ('Consent form signed by patient'), a scientific 'signature'. A label the
#:               grammar does not decide keeps f5fe720f's reading (base_role) - never a new release.
#:   protected - a signing, initials, attestation or consent ACTION place: a person's signature/initials/sign ('Nurse
#:               (initial)', 'Witness sign'), an imperative ('Sign below', 'Initial on each page'), a signature or
#:               initials joined to a date as one place ('Signature, date'), a numbered initials place ('Initial 1').
#:               Never generated; on contract v3 only a Signature or Initials field may sit there.
#:   uncertain - signing wording whose role the label's grammar cannot establish ('Signed off by consultant' - a sign-off
#:               status or the consultant's signing place; 'Sign' alone; '<unknown head> (initial)'; 'Reviewed and
#:               signed'): never generated, shown on the review page with what needs review, never silently dropped; the
#:               clinician may type it (legacy) or replace the area with a text field and type it (v3).
#: The vocabularies below only ever ADD evidence: a PERSON miss lands in uncertain or in f5fe720f's reading, a MEASURE or
#: DOCUMENT miss lands in uncertain or in f5fe720f's reading - never in ordinary. A model's proposal never moves a place
#: out of protected or uncertain: every gate reads the state from the ORIGINAL's printed label and structure.
#: Structure decides as well (Detector.assign_destinations): a sequence word beside a bare 'Initial' in the same table,
#: a unit in the row, a caption printed under or over a writing line, a signing box, a two-paragraph label cell.
ROLE_READING = "roles-2"
STATE_ORDINARY, STATE_PROTECTED, STATE_UNCERTAIN = "ordinary", "protected", "uncertain"
STATE_RANK = {STATE_ORDINARY: 0, STATE_UNCERTAIN: 1, STATE_PROTECTED: 2}
#: The bases that establish an ordinary reading on evidence; every other ordinary basis is f5fe720f's reading (and on
#: contract v3 leaves the kind rule's kind unchanged: a fallback never turns a signing kind into an answer).
ORDINARY_EVIDENCE = frozenset({"sequence_option", "attributive", "sequence_sibling", "measure_unit", "measure_head",
                               "signature_state", "scientific_signature", "signed_document", "document_signed_by",
                               "document_signed", "count_question", "time_question", "initialled_state"})
SIGNING_TOKEN = re.compile(r"sign|initial|consent|agree|assent|authori[sz]", re.I)
#: A first-person consent declaration ('I have been asked to give consent for my child to participate in this study:',
#: 'I agree to take part'): the consent WORDING the signer signs, never an answer place - unlike a factual consent
#: question ('Consent obtained?', 'Consent form signed: Yes/No'), which is ordinary.
CONSENT_DECLARATION = re.compile(r"^(?:i|we)\s+(?:(?:hereby|do|also|fully|freely|voluntarily|have\s+been\s+asked\s+to|"
                                 r"am\s+asked\s+to|would\s+like\s+to|wish\s+to|want\s+to)\s+)*(?:(?:give|provide|grant)\s+"
                                 r"(?:my\s+|our\s+)?(?:informed\s+)?consent|consent|agree|assent|authori[sz]e)\b", re.I)
_DW = r"[^\W\d_]"
_PERSON = (r"(?:patient|pt|witness|nurse|staff\s+nurse|charge\s+nurse|nurse\s+in\s+charge|rn|rgn|rmn|en|hca|hcsw|"
           r"nursing|staff|doctor|dr|consultant|registrar|spr|sho|fy1|fy2|f1|f2|ct1|ct2|st\d|resident|intern|attending|"
           r"fellow|physician|surgeon|anaesthetist|anesthetist|anaesthesiologist|anesthesiologist|midwife|sister|"
           r"matron|clinician|practitioner|gp|pharmacist|technician|radiographer|sonographer|physiotherapist|physio|"
           r"therapist|ot|slt|dietitian|dietician|psychologist|psychiatrist|paramedic|odp|scrub|runner|porter|"
           r"assistant|student|trainee|supervisor|manager|lead|co-?ordinator|officer|worker|assessor|examiner|reviewer|"
           r"checker|verifier|prescriber|administrator|operator|author|parent|mother|father|guardian|carer|caregiver|"
           r"relative|partner|spouse|next\s+of\s+kin|kin|interpreter|translator|advocate|representative|participant|"
           r"subject|donor|recipient|person|individual|employee|member|delegate|nominee|investigator|chaperone|"
           r"provider|md|np|pa|hcp|clerk|receptionist|secretary|client|signatory|signer|signee|professional|colleague|"
           r"team|healthcare\s+professional|phlebotomist|leader|volunteer|proxy|attorney|deputy|lpa|associate|"
           r"\w*ologist|\w*iatrist|\w+ician|\w+grapher|\w*therapist|\w*nurse|\w*wife)"
           r"(?:'s|s'|’s|s’|s|es)?")
_DOCUMENT = (r"(?:form|forms|chart|charts|kardex|consent|prescription|prescriptions|script|plan|summary|letter|"
             r"letters|checklist|check-?list|list|note|notes|record|records|request|referral|order|card|sheet|"
             r"declaration|document|documents|documentation|report|agreement|certificate|dnacpr|dnar|respect|policy|"
             r"protocol|copy|contract|waiver|disclaimer|application|statement|proforma|pro-?forma|pathway|mar|tta|tto|"
             r"log|entry|page|pages|audit|questionnaire|leaflet|booklet|time\s+out|sign\s+in|sign\s+out)")
_TEMPORAL = r"(?:time|date|day|when)"
_STATE = (r"(?:obtained|received|present|absent|checked|verified|confirmed|completed|documented|recorded|seen|"
          r"attached|scanned|provided|given|available|missing|done|collected|filed|on\s+file|in\s+(?:the\s+)?notes|"
          r"in\s+place|on\s+record)")
_SEQUENCE = (r"(?:repeat(?:ed)?|follow[- ]?up|f/u|subsequent|ongoing|final|peak|current|latest|last|previous|prior|"
             r"baseline|second|2nd|third|3rd|later|continuing|maintenance|interim|review|new|end|discharge|"
             r"\d+\s*(?:h|hr|hrs|hours?|mins?|minutes?|days?|weeks?)|day\s*\d+|week\s*\d+)")
#: A sibling row or column that makes a bare 'Initial' a measurement's first reading: a repeat or a timed reading only.
#: 'Second', 'Final', 'Review', 'New' are deliberately absent - an approvals or checking table prints 'Initial' and
#: 'Second' (or 'Final') as two people's initials.
_SEQUENCE_SIBLING = (r"(?:repeat(?:ed)?|follow[- ]?up|peak|subsequent|baseline|\d+\s*(?:h|hr|hrs|hours?|mins?|minutes?|days?|"
                     r"weeks?)|day\s*\d+|week\s*\d+)")
_SEQUENCE_ADJ = (r"(?:ongoing|subsequent|continuing|follow[- ]?up|final|later|maintenance|repeat(?:ed)?|current|"
                 r"long[- ]term)")
#: The heads of a measured or recorded clinical value ('Troponin (initial)'): evidence only. Ambiguous one- and two-
#: letter abbreviations (K, Na, Ca, Mg, HR, RR, CT, PT - 'Pt' is a patient) are deliberately absent.
_MEASURE = (r"(?:troponin|trop|hs-?trop|hs-?troponin|lactate|lac|dose|doses|dosage|rate|weight|wt|height|bmi|bp|"
            r"blood\s+pressure|pulse|heart\s+rate|resp(?:iratory)?\s+rate|temperature|temp|spo2|sats|saturations?|o2|"
            r"oxygen|fio2|gcs|news2?|pews|score|pain|glucose|cbg|ketones|hb|haemoglobin|hemoglobin|wcc|wbc|neutrophils|"
            r"crp|pct|procalcitonin|esr|creatinine|egfr|urea|sodium|potassium|chloride|bicarbonate|hco3|pco2|po2|"
            r"base\s+excess|inr|aptt|aptr|fibrinogen|d-?dimer|platelets|plt|ck|cpk|ast|alt|alp|ggt|bilirubin|bili|"
            r"albumin|protein|amylase|lipase|magnesium|calcium|phosphate|ferritin|tsh|t4|bnp|nt-?pro-?bnp|hba1c|"
            r"cholesterol|ldl|hdl|triglycerides|urate|ecg|qtc|qrs|lvef|peak\s+flow|pefr|fev1|fvc|volume|output|intake|"
            r"fluids?|bolus|infusion|insulin|heparin|antibiotics?|drug|medication|regimen|treatment|therapy|management|"
            r"assessment|presentation|diagnosis|impression|observations|obs|examination|exam|history|complaint|"
            r"symptoms?|findings?|imaging|x-?ray|mri|scan|ultrasound|echo|visit|appointment|consultation|attendance|"
            r"encounter|episode|stage|grade|size|diameter|length|measurement|reading|value|result|level|count|"
            r"concentration|titre|culture|sample|specimen|test|investigations?|results?|bloods|lfts?|u\s*&\s*es?|fbc|"
            r"abg|vbg|cxr|plans?|care|triage|response|rhythm|work-?up|contact|referral|resuscitation|analgesia)")
_SCIENCE = (r"(?:gene|genes|genetic|genomic|expression|molecular|mutational|mutation|transcriptional|transcriptomic|"
            r"proteomic|metabolomic|metabolic|immune|inflammatory|epigenetic|methylation|radiomic|spectral|isotopic|"
            r"viral|bacterial|microbial|tumou?r|prognostic|predictive|rna|dna|mrna|mirna|cytokine|interferon)")
_UNIT = (r"(?:ng/l|ng/ml|mg/l|mmol/l|µmol/l|umol/l|g/l|g/dl|mg/dl|iu/l|u/l|kpa|mmhg|mg|mcg|µg|ug|ml|kg|cm|mm|"
         r"%|bpm|units?|/min|°c|x\s*10\^?9/l|10\^?9/l|meq/l|breaths/min)")
UNIT_TOKEN = re.compile(r"(?<![\w/])" + _UNIT + r"(?![\w/])", re.I)
_OPTIONS = r"\(\s*(?:y|n|yes|no|n/a|na)(?:\s*[/,]\s*(?:y|n|yes|no|n/a|na))*\s*\)"
_CLOSE = r"(?:\s*" + _OPTIONS + r")?[\s?:.\-–—]*$"
_ACT = r"(?:here|there|below|above|beside|overleaf|opposite|each|every|all|both|the|this|these|those|if|to|where|when)"
#: What one initials on a form ('Initial changes', 'Initial each page').
_EDIT_OBJECT = (r"(?:changes?|corrections?|alterations?|amendments?|deletions?|additions?|entries|entry|pages?|sheets?|"
                r"forms?|boxes|lines?|sections?)")
_PREPOSITION = r"(?:on|in|at|from|after|before|by|for|of|with|during|within|upon|per|via|until|since|into|onto|against)"
_EMPTY = re.compile(r"[\W_]*")


def _state(state, basis, kind=""):
    return {"state": state, "basis": basis, "kind": kind if state != STATE_ORDINARY else "", "reading": ROLE_READING}


def _person(text) -> bool:
    """Whether the words name a person: an optional article, an optional qualifier word, a person noun (possessive or
    plural), an optional number ('Nurse 2', 'Checker 1'). A temporal first word ('Time patient ...') is no person."""
    text = _plain(text).strip(" ,;:/-–—()")
    if re.match(_TEMPORAL + r"\b", text):
        return False
    return re.fullmatch(r"(?:(?:the|a|an|each|every|both|all)\s+)?(?:" + _DW + r"[\w'-]*\s+)?" + _PERSON +
                        r"(?:\s*\(?\d+\)?|\s+x\s*\d)?", text) is not None


def _has_person(text) -> bool:
    return re.search(r"\b" + _PERSON + r"\b", _plain(text)) is not None


def _agent_only(text) -> bool:
    """'patient', 'the prescriber', 'patient or representative', 'both parents': person nouns only, closing."""
    text = re.sub(_CLOSE, "", _plain(text)).strip()
    parts = [p for p in re.split(r"\s*(?:\bor\b|\band\b|/|&|,)\s*", text)]
    return bool(text) and all(p and _person(re.sub(r"^(?:both|either)\s+", "", p)) for p in parts)


def _initial_state(t, siblings, unit):
    """The strictest state a singular 'initial' gives the label (None when there is none)."""
    found = None
    for m in re.finditer(r"\binitial\b", t):
        before, after = t[:m.start()], t[m.end():]
        word = re.match(r"\s*(?:\([^)]*\)\s*)?(" + _DW + r"[\w'’-]*)", after)
        if re.match(r"\s*(?:\(\s*[^)]*\)\s*)?(?:box|in\s+(?:the\s+)?box|on\s+(?:each|every|all|the)\b|"
                    r"against\s+(?:each|every)\b|" + _ACT + r"\b)", after):
            st = _state(STATE_PROTECTED, "initial_action", "initials")
        elif re.match(r"\s*(?:\d+|x\s*\d+|#\s*\d+|no\.?\s*\d+)\s*[\W_]*$", after):
            st = _state(STATE_PROTECTED, "numbered_initial", "initials")
        elif re.match(r"\s*(?:/|\bor\b|\bvs\.?|\bversus\b|\bthen\b)\s*" + _SEQUENCE + r"\b", after) or \
                re.search(_SEQUENCE + r"\s*(?:/|\bor\b|\bvs\.?)\s*$", before):
            st = _state(STATE_ORDINARY, "sequence_option")
        elif re.match(r"\s+(?:and|&|/|or)\s+" + _SEQUENCE_ADJ + r"\s+" + _DW, after):
            st = _state(STATE_ORDINARY, "attributive")
        elif word and not re.fullmatch(r"box|and|or|" + _ACT, word.group(1)):
            # 'initial' before a word: an attributive adjective ('Initial assessment') only on evidence - a measured or
            # recorded clinical head within the next three words. The imperative 'initial' + what one initials
            # ('Initial changes', 'Initial page') is the place; 'initial' + a person ('Initial nurse') is uncertain; a
            # preposition ('Initial on admission') or an unknown word keeps f5fe720f's reading.
            phrase = re.split(r"[),;:/]", re.sub(r"\([^)]*\)", " ", after))[0].split()[:3]
            first = word.group(1)
            if re.fullmatch(_EDIT_OBJECT, first):
                st = _state(STATE_PROTECTED, "initial_action", "initials")
            elif any(_person(x) for x in phrase[:2]):
                st = _state(STATE_UNCERTAIN, "initial_person", "initials")
            elif re.fullmatch(_PREPOSITION, first):
                base = base_role(t)
                st = _state(STATE_PROTECTED, "base", base) if base else _state(STATE_ORDINARY, "base")
            elif any(re.fullmatch(_MEASURE, x.strip(".-")) for x in phrase) or \
                    re.search(r"\binitial\s+" + _MEASURE + r"\b", t):
                st = _state(STATE_ORDINARY, "attributive")
            else:
                base = base_role(t)
                st = _state(STATE_PROTECTED, "base", base) if base else _state(STATE_ORDINARY, "attributive_unverified")
        elif re.fullmatch(r"\s*(?:\(\s*[^)]*\)\s*)?[\W_]*", after):
            head = re.sub(r"[\s(\[–—\-:,]+$", "", before).strip()
            last = re.split(r"[\s(]+", head)[-1] if head else ""
            unit_here = unit or UNIT_TOKEN.search(after) is not None or \
                re.search(r"\([^)]*" + _UNIT + r"[^)]*\)", before) is not None
            if not head:
                if any(re.fullmatch(_SEQUENCE_SIBLING + r"[\W_]*", _plain(s)) for s in siblings or ()):
                    st = _state(STATE_ORDINARY, "sequence_sibling")
                else:
                    st = _state(STATE_PROTECTED, "bare_initial", "initials")
            elif _has_person(head):
                st = _state(STATE_PROTECTED, "person_initial", "initials")
            elif unit_here:
                st = _state(STATE_ORDINARY, "measure_unit")
            elif re.fullmatch(_MEASURE, last) or re.fullmatch(_MEASURE, head):
                st = _state(STATE_ORDINARY, "measure_head")
            elif DASH_QUALIFIER_INITIAL.search(t):
                st = _state(STATE_ORDINARY, "dash_qualifier")          # f5fe720f released it; kept, not widened
            else:
                st = _state(STATE_UNCERTAIN, "unknown_head_initial", "initials")
        else:
            base = base_role(t)
            st = _state(STATE_PROTECTED, "base", base) if base else _state(STATE_ORDINARY, "base")
        if found is None or STATE_RANK[st["state"]] > STATE_RANK[found["state"]]:
            found = st
    return found


def destination_state(label, *, siblings=(), unit=False, lines=()) -> dict:
    """{'state': ordinary|protected|uncertain, 'basis', 'kind' (signature|initials for a held place), 'reading'} for a
    PRINTED label (see the section comment). `siblings`: the printed labels beside it in the same table or block
    (structure); `unit`: whether its row or column prints a unit; `lines`: the label cell's own paragraphs and line
    breaks, when it has several - two captions stacked in one label cell ('Signature' over 'Date') and one caption
    wrapped onto two lines ('Date of' over 'signature') print the same words, so a line that alone holds the place
    while the whole reads ordinary leaves it UNCERTAIN (residual L1:F1, legacy half)."""
    whole = _destination_state(label, siblings=siblings, unit=unit)
    if whole["state"] == STATE_ORDINARY and len([x for x in lines if _plain(x)]) > 1:
        held = [st for x in lines if _plain(x) and (st := _destination_state(x))["state"] != STATE_ORDINARY]
        if held:
            return _state(STATE_UNCERTAIN, "stacked_caption", held[0]["kind"] or "signature")
    return whole


def _destination_state(label, *, siblings=(), unit=False) -> dict:
    t = _plain(label)
    if not t or not SIGNING_TOKEN.search(t):
        return _state(STATE_ORDINARY, "no_signing_word")
    if CONSENT_DECLARATION.search(t):
        return _state(STATE_UNCERTAIN, "consent_declaration", "signature")
    if not re.search(r"sign|initial", t):
        return _state(STATE_ORDINARY, "no_signing_word")
    # 1. A signature (or initials) and a date printed as ONE place - f5fe720f's pairs, and the comma, dash, 'with' and
    #    'to sign and date' joins it read as a date (L1:RR1-02, L2:RR3-01).
    if SIGNATURE_DATE_PAIR.search(t):
        return _state(STATE_PROTECTED, "signing_and_date", "signature")
    if INITIALS_DATE_PAIR.search(t):
        return _state(STATE_PROTECTED, "signing_and_date", "initials")
    if re.search(r"^(?:(?:the\s+)?" + _PERSON + r"\s+)?(?:(?:counter-?|co-?|e-?|electronically\s+|digitally\s+)?signed|"
                 r"signatures?)\s*(?:,|[–—]|\s-\s|\s+with\s+)\s*(?:and\s+)?dated?\b", t) or \
            re.search(r"(?:,\s*|\bto\s+)sign\s*(?:,\s*|\band\b|&|\+|/)\s*dated?\b", re.sub(r"\([^)]*\)", " ", t)) or \
            re.search(r"^(?:the\s+)?" + _PERSON + r"\s+(?:counter-?|co-?)?signed\s*(?:and|&|/|\+|,)\s*dated?\b", t) or \
            re.search(r"\bsigned\s+by\s*\([^)]*\b(?:name|print)", t):
        return _state(STATE_PROTECTED, "signing_and_date", "signature")
    if re.search(r"^(?:(?:the\s+)?" + _PERSON + r"\s+)?(?:date\s+and\s+)?initials\s+(?:and|&|/|\+|,)\s*dated?\b"
                 r"(?!\s+of\s+birth)", t) or re.search(r"\bdated?\s+(?:and|&|/|\+|,)\s*initials\s+of\b", t):
        return _state(STATE_PROTECTED, "signing_and_date", "initials")
    # 2. A date question that mentions signing ('Date signed', 'Date of signature'): f5fe720f's reading.
    if DATE_LABEL.search(t):
        return _state(STATE_ORDINARY, "date_question")
    states = []
    # 3. Initials (plural): the place, always. Initialling: an agent or an action is the place, a closing option list a
    #    checklist state ('Initialled (Y/N)'), anything else uncertain.
    if re.search(r"\binitials\b", t):
        states.append(_state(STATE_PROTECTED, "initials_noun", "initials"))
    for m in re.finditer(r"\binitiall?(?:ed|ing)\b", t):
        pre, post = t[:m.start()].strip(), t[m.end():].strip()
        if re.match(r"by\b|and\s+dated?\b|" + _ACT + r"\b", post) or \
                re.search(r"(?:\bto\s+be|\bto|\bplease|\bmust\s+be)$", pre):
            states.append(_state(STATE_PROTECTED, "initialled_place", "initials"))
        elif re.fullmatch(r"(?:" + _OPTIONS + r"|\?)[\s?:.]*", post):
            states.append(_state(STATE_ORDINARY, "initialled_state"))
        else:
            states.append(_state(STATE_UNCERTAIN, "initialled", "initials"))
    # 4. Countersigning and its kin.
    if re.search(r"\bcounter-?sign|\bco-?sign|\bcosign|\be-?sign\b|\besign\b|\bundersigned\b", t):
        states.append(_state(STATE_PROTECTED, "countersign", "signature"))
    # 5. 'signature(s)': the place, unless a state closes it, it is a count, or it is a scientific term.
    if re.search(r"\bsignatures?\b", t):
        if re.search(r"^(?:number|no\.?|count|total)\s+of\s+signatures?" + _CLOSE, t):
            states.append(_state(STATE_ORDINARY, "count_question"))
        elif re.search(r"\bsignatures?\s+" + _STATE + _CLOSE, t):
            states.append(_state(STATE_ORDINARY, "signature_state"))
        elif re.fullmatch(r"(?:" + _SCIENCE + r"[\s-]+)+signatures?", t):
            states.append(_state(STATE_ORDINARY, "scientific_signature"))
        else:
            states.append(_state(STATE_PROTECTED, "signature_noun", "signature"))
    # 6. 'signed'.
    for m in re.finditer(r"\b(?:e-?|electronically\s+|digitally\s+)?signed\b", t):
        pre, post = t[:m.start()].strip(), t[m.end():].strip()
        closing = not post or _EMPTY.fullmatch(post) is not None or re.fullmatch(_CLOSE, " " + post) is not None
        st = None
        if re.match(_TEMPORAL + r"\b", pre) and not re.search(r"\bby\s*$", post):
            st = _state(STATE_ORDINARY, "time_question")
        elif not pre or pre == "please":
            if closing:
                st = _state(STATE_PROTECTED, "signed_bare", "signature")
            elif re.match(r"off\s+by\s*[\W_]*$", post):
                st = _state(STATE_PROTECTED, "signed_by", "signature")
            elif re.match(r"off\b", post):
                st = _state(STATE_UNCERTAIN, "sign_off", "signature")
            elif re.match(r"(?:on|at)\s+(?:admission|arrival|discharge|transfer|the\s+day|the\s+ward)\b|(?:pre|post)-?op",
                          post):
                st = _state(STATE_UNCERTAIN, "signed_when", "signature")
            elif not re.match(r"by\b", post) and _person(re.sub(_CLOSE, "", post)):
                st = _state(STATE_PROTECTED, "signed_person", "signature")
            elif re.match(_DOCUMENT + r"\b", post) and not re.search(r"\bby\s*$", post):
                st = _state(STATE_ORDINARY, "signed_document")
        elif re.search(r"(?:\bto\s+be|\bto|\bplease|\bmust\s+be|\bshould\s+be|\bneeds?\s+to\s+be)$", pre):
            st = _state(STATE_PROTECTED, "signed_action", "signature")
        elif re.search(r"\b(?:reviewed|read|checked|witnessed|verified|approved|agreed|completed|seen)\s*(?:and|&|/)$",
                       pre):
            st = _state(STATE_UNCERTAIN, "verb_and_signed", "signature")
        elif _person(pre) and closing:
            st = _state(STATE_PROTECTED, "person_signed", "signature")
        elif re.match(r"by\b", post):
            agent = post[2:].strip()
            if agent and _agent_only(agent) and re.search(r"\b" + _DOCUMENT + r"\b", pre) and not _has_person(pre):
                st = _state(STATE_ORDINARY, "document_signed_by")
        elif closing and re.search(r"\b(?:" + _DOCUMENT + r"|" + _TEMPORAL + r")$", pre) and not _person(pre):
            st = _state(STATE_ORDINARY, "document_signed")
        if st is None:
            base = base_role(t)
            st = _state(STATE_PROTECTED, "base", base) if base else _state(STATE_ORDINARY, "base")
        states.append(st)
    # 7. 'sign': the imperative or a person's place; the clinical noun ('Babinski sign', 'Sign of infection') is not.
    for m in re.finditer(r"\bsigns?\b(?!-)|\bsign[- ]off\b|\bsigning\b", t):
        word = m.group(0)
        pre, post = t[:m.start()].strip(), t[m.end():].strip()
        st = None
        if re.fullmatch(r"sign[- ]off", word):
            if _person(pre) or re.match(r"by\s+" + _PERSON, post):
                st = _state(STATE_PROTECTED, "person_sign_off", "signature")
            elif pre and re.fullmatch(r"[\w'-]+(?:\s+[\w'-]+)?", pre) and _EMPTY.fullmatch(post):
                # '<someone> sign-off' with a head the vocabulary does not know: the role cannot be established.
                st = _state(STATE_UNCERTAIN, "sign_off", "signature")
        elif word == "signing":
            if re.match(_ACT + r"\b", post):
                st = _state(STATE_PROTECTED, "sign_action", "signature")
        elif word == "signs":
            if _person(pre) and (not post or _EMPTY.fullmatch(post) or re.match(_ACT + r"\b", post)):
                st = _state(STATE_PROTECTED, "person_signs", "signature")
        else:
            person_to = re.search(r"\b(?:to|should|must|shall|will|may|can|is\s+to|are\s+to)$", pre) is not None and \
                (_person(re.sub(r"\s*\b(?:to|should|must|shall|will|may|can|is\s+to|are\s+to)$", "", pre)) or
                 re.fullmatch(r"(?:should|must|shall|will|may|can)", pre) is not None)
            imperative = not pre or pre in ("please", "to", "then") or person_to
            if imperative and (not post or _EMPTY.fullmatch(post)):
                # 'Sign' alone may be a clinical sign's label as easily as a signing place: uncertain. 'Please sign',
                # 'Witness to sign' are the place.
                st = _state(STATE_PROTECTED if pre else STATE_UNCERTAIN, "sign_action" if pre else "sign_bare",
                            "signature")
            elif imperative and re.match(r"(?:" + _ACT + r"|in\s+(?:the\s+)?box|name|off\s+by)\b", post):
                st = _state(STATE_PROTECTED, "sign_action", "signature")
            elif imperative and re.match(r"(?:and|&|\+|/|,)\s*(?:print|name|stamp|return|initial|send|keep|retain|"
                                         r"date|dated|confirm|agree)\b", post):
                st = _state(STATE_PROTECTED, "sign_action", "signature")
            elif imperative and re.match(r"to\s+(?:confirm|agree|acknowledge|consent|say|indicate|show|accept|"
                                         r"declare)\b", post):
                st = _state(STATE_PROTECTED, "sign_action", "signature")
            elif _person(pre) and (not post or _EMPTY.fullmatch(post) or re.match(_ACT + r"\b", post)):
                st = _state(STATE_PROTECTED, "person_sign", "signature")
            elif re.search(r"\bto$", pre) and (not post or _EMPTY.fullmatch(post)):
                # '<someone> to sign' closing the label: an instruction to sign, whoever the vocabulary knows.
                st = _state(STATE_UNCERTAIN, "to_sign", "signature")
            elif re.search(r"\b(?:print(?:\s+name)?|name|read|stamp|date|initial|check|review|complete)\s*"
                           r"(?:and|&|\+|/|,)$", pre):
                st = _state(STATE_PROTECTED, "and_sign", "signature")
            elif re.search(r"\bby$", pre) or (re.search(r"\(\s*$", pre) and re.match(r"\)", post)):
                st = _state(STATE_PROTECTED, "by_sign", "signature")
        if st is None:
            base = base_role(t)
            st = _state(STATE_PROTECTED, "base", base) if base else _state(STATE_ORDINARY, "base")
        states.append(st)
    # 8. 'initial' (singular).
    if not re.search(r"\binitials\b", t):
        st = _initial_state(t, siblings, unit)
        if st is not None:
            states.append(st)
    if not states:
        base = base_role(t)
        return _state(STATE_PROTECTED, "base", base) if base else _state(STATE_ORDINARY, "base")
    return max(states, key=lambda s: STATE_RANK[s["state"]])


def legacy_role_kind(label, *, siblings=()) -> str:
    """The legacy default path's role kind for a field's PRINTED label: 'signature' or 'initials' when the destination
    state holds it (protected or uncertain), else ''. Both engines read the same decision (destination_state); a label
    the state reads ordinary on evidence is generated on both, a held label is generated on neither."""
    state = destination_state(label, siblings=siblings)
    return state["kind"] if state["state"] != STATE_ORDINARY else ""


def legacy_destination(label, *, siblings=(), lines=()) -> dict:
    """{'role', 'state', 'basis', 'reading'} for a legacy field's PRINTED label (the 'roles' operation)."""
    state = destination_state(label, siblings=siblings, lines=lines)
    return {"role": state["kind"] if state["state"] != STATE_ORDINARY else "", "state": state["state"],
            "basis": state["basis"], "reading": ROLE_READING}


def signing_box_reading(text) -> bool:
    """Whether a box's printed question or section makes it a signing box: the engine's own question_box_signing (the
    reading that declines to map it), less the adjective 'initial' - never wider than the engine's own reading."""
    if not text or not Detector.question_box_signing(text):
        return False
    reading = ADJECTIVE_INITIAL.sub(" ", text)
    return reading == text or bool(Detector.question_box_signing(reading) or BOX_SIGNING_VERB.search(reading))


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
    # ⚠️ THE ORIGINAL'S DESTINATION ROLES, read before anything is written and never from the mapping: a stored or
    # forged field on a signing, protected or policy place is refused by its span, not by its paragraph.
    original_roles = destination_roles_of(package)
    role_refusals = role_violations(_PlaceReader(index), fields, original_roles)
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
        # After the anchors are proved to be this form's (a changed source is a stale mapping first): a place the
        # ORIGINAL gives a role takes only what that role allows, by span and line segment, never by paragraph.
        if str(field.get("key")) in role_refusals:
            refusal = role_refusals[str(field.get("key"))]
            fail(refusal["reason"], ROLE_CODES[refusal["class"]])
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
    roles = None
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
        # The place's printed authorship/review requirement, read exactly as for the engine's own fields.
        source_policy.annotate(detector, [field])
        # ⚠️ A ROLE PLACE TAKES ONLY WHAT IT ALLOWS, whoever chooses it: a clinician's add or a model's proposal on a
        # signing, initials, consent or protected place is refused unless it is a Signature or Initials field.
        roles = destination_roles_of(package) if roles is None else roles
        refusal = role_violations(_PlaceReader(detector.index), [field], roles).get(field["key"])
        if refusal:
            fail(refusal["reason"] + " Nothing was added.", "destination_role")
        out.append(field)
    return out
