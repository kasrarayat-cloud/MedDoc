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
indices count same-kind children in document order.

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

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NS = {"w": W, "w14": W14, "mc": MC}
CONTRACT = "v3"
MAX_FIELDS = 1500
MAX_ANSWER = 100_000


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

    def tree(self, part):
        if part not in self.trees:
            self.trees[part] = etree.fromstring(self.zip.read(part), PARSER)
        return self.trees[part]

    def content_parts(self):
        parts = ["word/document.xml"]
        parts += sorted(n for n in self.names if HEADER_FOOTER.match(n))
        return parts

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
    a checkbox and NUL otherwise (its content is its own answer area)."""
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


class SlotIndex:
    """Every slot of the content parts in document order, with element and sibling lookups."""

    def __init__(self, package: Package):
        self.package = package
        self.slots: list[Slot] = []
        self.by_id: dict[str, Slot] = {}
        self.by_el: dict[int, Slot] = {}
        for part in package.content_parts():
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
        for ri, tr in enumerate(el.findall(q("w:tr"))):
            col = 0
            trpr = tr.find(q("w:trPr"))
            before = trpr.find(q("w:gridBefore")) if trpr is not None else None
            if before is not None:
                col = int(before.get(q("w:val"), "0") or 0)
            for ci, tc in enumerate(tr.findall(q("w:tc"))):
                tcpr = tc.find(q("w:tcPr"))
                span, vmerge = 1, None
                if tcpr is not None:
                    gs = tcpr.find(q("w:gridSpan"))
                    span = int(gs.get(q("w:val"), "1") or 1) if gs is not None else 1
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
    name = data.find(q("w:name"))
    info["name"] = name.get(q("w:val")) if name is not None else None
    info["field"] = kind
    return info


# ─── detection ─────────────────────────────────────────────────────────────────────────────────────────────────────

UNDERSCORES = re.compile(r"_{3,}(?:[ \t]*_{2,})*|_{2}(?:[ \t]+_{1,2}){1,}")   # ___ , or character positions __ __ __
DIGIT_RUN = re.compile(r"\u25af+(?:\s*[/.:\-]\s*\u25af+)*")                     # digit-entry boxes (symbol font) as one blank
SEGMENTED = re.compile(r"\|(?:[ _]*_[ _]*\|)+(?:\s*[/.:\-]?\s*\|(?:[ _]*_[ _]*\|)+)*")   # digit boxes |__|__| / |__|__|
DOTS = re.compile(r"(?:\.{5,}|…{2,}|(?:\. ){4,}\.?)")    # a dotted leader: ....... or …… or . . . . .
BRACKET = re.compile(r"\[(?=[^\]\n]{2,120}\])(?:insert|enter|add|type|your|name|date|address|specify|[A-Z<])[^\]\n]*\]", re.I)
ANGLE = re.compile(r"<(?![/!?])[^<>\n]{3,120}>")                  # <Protocol Number: Abbreviated Title> author placeholders
TOKEN = re.compile(r"\{\{\s*([\w][\w .?:/()\-]{0,119}?)\s*\}\}")
PLACEHOLDER_TEXT = re.compile(r"^(?:click (?:or tap )?here to enter (?:text|a date)\.?|choose an item\.?|click or tap to enter a date\.?|"
                              r"enter (?:text|date)(?: here)?\.?|type here\.?|data to be filled in by site\.?|mm/dd/yyyy|dd/mm/yyyy|"
                              r"dd|mm|yy|yyyy|hh|dd/mm/yy|mm/dd/yy)$", re.I)
ENTER_HINT = re.compile(r"^(?:enter|insert|type|add|specify)\s+\S.{0,60}$", re.I)
CHECK_ALL = re.compile(r"\b(?:check|tick|mark|select|circle)\s+all\s+that\s+apply\b|\ball that apply\b|\bselect up to\b|"
                       r"\b(?:check|tick|mark|select)\s+(?:any|as many)\b", re.I)
CHECK_ONE = re.compile(r"\b(?:check|tick|choose|select|mark|circle)\s+(?:only\s+)?one\b|\bone only\b", re.I)
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
FIELDISH = re.compile(r"\b(?:date|time|name|signature|signed|initials?|comments?|notes?|number|no\.|#|dose|amount|result|"
                      r"value|score|site|code|address|phone|reason|description|details?|id)\b", re.I)
YESNO = re.compile(r"^(?:y|n|yes|no|n/?a|nd|unk|unknown|not known|not applicable|n/a or nd|na or nd|not done|done)\.?$", re.I)
MAX_LABEL_WORDS = 18


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


def clean_label(text: str) -> str:
    text = (text or "").replace("\x00", " ").replace(BOX, " ").replace(CHECKED, " ")
    text = re.sub(r"\s+", " ", text.replace("\t", " ")).strip()
    text = re.sub(r"^(?:[\dA-Za-z]{1,3}[.)]|\(\w{1,3}\))\s+", "", text)
    return text.strip(" :–—-_*").strip()[:300]


def is_blank_text(txt: str) -> bool:
    t = txt.strip()
    return not t or set(t) <= set("_ \t.   ") or bool(PLACEHOLDER_TEXT.match(t))


def is_option_word(txt: str) -> bool:
    return bool(OPTION_WORD.match(txt.strip()))


class Detector:
    def __init__(self, package: Package):
        self.package = package
        self.index = SlotIndex(package)
        self.areas: list[Area] = []
        self.notes: list[str] = []
        self.claimed: set = set()          # element ids already turned into an area (or used as its label)
        self._order = 0
        self._grid = {}
        self._text = {}
        self._ptext = {}
        self._heading = {}
        self._is_heading = {}
        self._numbering = None
        self._col_lists = {}
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
        if any(self.is_empty_cell(c) or BOX in self.cell_text(c) or "\x00" in self.cell_objects(c) for c in cells):
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

    def text_at(self, tbl_slot, r, col):
        for c in self.grid(tbl_slot).get(r, []):
            if c.info["col"] <= col < c.info["col"] + c.info["span"]:
                if c.info["vmerge"] == "continue":
                    return ""
                txt = self.cell_text(c)
                if txt and not is_blank_text(txt) and BOX not in txt and "\x00" not in self.cell_objects(c):
                    if len(txt) > 80:
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

    def column_header(self, tbl_slot, col, row) -> str:
        """The label printed directly above (a label row over a blank row), else the table's header rows (a
        continued table's come from the table it continues)."""
        above = [r for r in self.grid(tbl_slot) if r < row]
        if above:
            r = max(above)
            if self.row_kind(tbl_slot, r) == "label":
                txt = self.text_at(tbl_slot, r, col)
                if txt:
                    return txt
        ht = self.header_table(tbl_slot)
        for r in reversed([h for h in self.header_rows(ht) if ht is not tbl_slot or h < row]):
            txt = self.text_at(ht, r, col)
            if txt:
                return txt
        return ""

    def column_headers_all(self, tbl_slot, col, row) -> list:
        ht = self.header_table(tbl_slot)
        out = [self.text_at(ht, r, col) for r in self.header_rows(ht) if ht is not tbl_slot or r < row]
        return [t for t in out if t]

    def cell_objects(self, c) -> str:
        return "".join(self.ptext(x.el)[0] for x in c.children if x.kind == "p")

    def is_label_cell(self, c) -> bool:
        txt = self.cell_text(c)
        if not txt or is_blank_text(txt) or is_option_word(txt) or len(txt) > 300:
            return False
        objs = self.cell_objects(c)
        return BOX not in txt and CHECKED not in txt and "\x00" not in objs

    def row_identity(self, tbl_slot, row, col) -> str:
        """The leftmost label of the row (the item the row is about)."""
        for c in sorted(self.grid(tbl_slot).get(row, []), key=lambda c: c.info["col"]):
            if c.info["col"] >= col:
                break
            if self.is_label_cell(c):
                return clean_label(self.cell_text(c))
        return ""

    def row_label(self, tbl_slot, row, col) -> str:
        rows = self.grid(tbl_slot)
        best = ""
        for c in sorted(rows.get(row, []), key=lambda c: c.info["col"]):
            if c.info["col"] >= col:
                break
            if self.is_label_cell(c):
                best = clean_label(self.cell_text(c))
        if not best:
            # a vertically merged label cell continues from the row above
            for c in rows.get(row, []):
                if c.info["col"] < col and c.info["vmerge"] == "continue":
                    for r in sorted((r for r in rows if r < row), reverse=True):
                        head = next((x for x in rows[r] if x.info["col"] == c.info["col"]), None)
                        if head is not None and head.info["vmerge"] != "continue":
                            best = clean_label(self.cell_text(head))
                            break
        return best

    def context_for(self, slot: Slot) -> str:
        parts = []
        cell = self.host_cell(slot)
        if cell is not None:
            tbl = cell.parent
            header = clean_label(self.column_header(tbl, cell.info["col"], cell.info["row"]))
            ident = self.row_identity(tbl, cell.info["row"], cell.info["col"])
            rowlab = self.row_label(tbl, cell.info["row"], cell.info["col"])
            if ident and ident != rowlab:
                parts.append(ident[:120])
            if rowlab:
                parts.append(rowlab[:120])
            if header:
                parts.append(header[:80])
        head = self.heading_before(slot)
        if head:
            parts.insert(0, head[:120])
        return " > ".join(dict.fromkeys(p for p in parts if p))[:300]

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
        if TIME_LABEL.search(label) and not DATE_LABEL.search(label):
            return "time"
        if DATE_LABEL.search(label):
            return "date"
        if LONG_LABEL.search(label):
            return "long_text"
        return "text"

    def choice_kind(self, question: str, options: list, hint: str = "") -> str:
        text = " ".join([question or "", hint or ""])
        if CHECK_ONE.search(text):
            return "choice"
        if options and all(YESNO.match((o or "").strip()) for o in options):
            return "choice"
        if CHECK_ALL.search(text) or re.search(r"\(s\)|\bapply\b", question or "", re.I):
            return "multi_choice"
        return "choice"

    # -- the rules -------------------------------------------------------------------------------------------------
    def detect(self):
        self.rule_content_controls()
        self.rule_form_fields()
        self.rule_checkboxes()
        self.rule_text_option_choices()
        self.rule_tables()
        self.rule_checkboxes(leftovers=True)
        self.rule_lines_below_label()
        self.rule_paragraph_fields()
        self.rule_initial_boxes()
        self.merge_header_copies()
        self.areas.sort(key=lambda a: (self.index.by_id[a.slot.id].seq if a.slot.id in self.index.by_id else 0, a.order))
        self.surface_duplicates()
        self.areas.sort(key=lambda a: (self.index.by_id[a.slot.id].seq if a.slot.id in self.index.by_id else 0, a.order))
        return self.areas, self.notes

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
                self.add(Area(kind, clean_label(label), slot, {"type": "ff_text"}, context=self.context_for(slot)))

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
            units = self.box_units(s)
            cell = self.host_cell(s)
            if not leftovers and cell is not None and s.parent is cell and \
                    not any(clean_label(u[1]) for u in units) and not clean_label(units[0][2]) and \
                    self.column_header(cell.parent, cell.info["col"], cell.info["row"]):
                continue
            para_units.append((s, units))
        groups = []
        current = None
        for pslot, units in para_units:
            before = clean_label(units[0][2]) if units else ""
            own_question = bool(before)
            cell = self.host_cell(pslot)
            joined = False
            if current is not None and not own_question:
                last_p = current["paras"][-1]
                if last_p.parent is pslot.parent:
                    sibs, ia = self.para_neighbours(last_p)
                    ib = next((i for i, x in enumerate(sibs) if x is pslot), None)
                    if ia is not None and ib is not None and 0 < ib - ia <= 2 and \
                            not any(self.text(x.el).strip() for x in sibs[ia + 1:ib]):
                        joined = True
                elif cell is not None and self.host_cell(last_p) is not None and last_p.parent.parent is cell.parent \
                        and not current["question_from_cell"]:
                    lc = self.host_cell(last_p)
                    first_l = next((c for c in lc.children if c.kind == "p"), None)
                    first_c = next((c for c in cell.children if c.kind == "p"), None)
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

    def emit_checkbox_group(self, g):
        pslot = g["paras"][0]
        for units in self.split_inline_groups(g):
            options = [clean_label(re.split(r"\t{2,}| {4,}", o)[0]) if re.search(r"\S", re.split(r"\t{2,}| {4,}", o)[0]) else clean_label(o)
                       for _, o, _ in units]
            question = clean_label(units[0][2])
            host = pslot
            used_para = None
            if not question:
                cell = self.host_cell(pslot)
                if cell is not None and next((c for c in cell.children if c.kind == "p"), None) is pslot:
                    question = self.row_label(cell.parent, cell.info["row"], cell.info["col"]) or \
                        clean_label(self.column_header(cell.parent, cell.info["col"], cell.info["row"]))
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
            hint = " ".join([question] + [self.text(p.el) for p in g["paras"][:1]])
            if len(units) == 1:
                label = options[0] or question or "Checkbox"
                area = Area("checkbox", label, anchor, target, context=self.context_for(anchor), options=[options[0]] if options[0] else [])
                if question and options[0]:
                    area.context = (area.context + " > " + question).strip(" >")[:300]
            else:
                area = Area(self.choice_kind(question, options, hint), question or "Choose", anchor, target,
                            context=self.context_for(anchor), options=[o or "(option %d)" % (i + 1) for i, o in enumerate(options)],
                            extra_slots=extra)
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
                    # (a) circle-one line directly below: 'YES<tab>NO'
                    if i + 1 < len(paras) and id(paras[i + 1].el) not in self.claimed:
                        line = self.text(paras[i + 1].el)
                        words = [w.strip() for w in re.split(r"\t+| {3,}", line) if w.strip()]
                        if 2 <= len(words) <= 6 and all(is_option_word(w) for w in words) and \
                                (qtext.endswith(("?", ":", ".")) or re.search(r"\bcircle\b", qtext, re.I)):
                            opt_slot = paras[i + 1]
                            self.add(Area(self.choice_kind(qtext, words), clean_label(qtext), opt_slot,
                                          {"type": "text_options", "options": words}, context=self.context_for(opt_slot),
                                          options=words))
                            self.claimed.add(id(q_slot.el))
                            i += 2
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
                        words = [clean_label(self.text(o.el)) for o in opts]
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
        return is_blank_text(txt) and self.is_empty_cell(c) or txt in (BOX, CHECKED)

    def rule_tables(self):
        for tslot in [s for s in self.index.slots if s.kind == "tbl"]:
            rows = self.grid(tslot)
            ordered = sorted(rows)
            handled = set()
            box_cols = {}
            for r in ordered:
                for c in rows[r]:
                    if c.info["vmerge"] != "continue" and not self.cell_has_claim(c.el) and self.cell_text(c) in (BOX, CHECKED):
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
                    header = clean_label(self.column_header(tslot, c.info["col"], r).strip("√✓✔*† "))
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
                        header_row = any(x.info["col"] == opts[0].info["col"] and self.is_option_cell(x) for x in below) \
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
                if len(items) < 3:
                    continue
                ht = self.header_table(tslot)
                header = " ".join(dict.fromkeys(self.column_headers_all(tslot, col, items[0][0])))
                labelled = [(r, c, self.row_label(tslot, r, col)) for r, c in items]
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
                    headers = [clean_label(self.column_header(tslot, c.info["col"], r)) for c in cells]
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
                    txt = self.cell_text(c)
                    placeholder = bool(txt) and (PLACEHOLDER_TEXT.match(txt) or ENTER_HINT.match(txt) or ANGLE.fullmatch(txt)
                                                 or BRACKET.fullmatch(txt))
                    if not (self.is_empty_cell(c) or placeholder and self.cell_is_plain(c)):
                        continue
                    label = self.row_label(tslot, r, c.info["col"])
                    header = clean_label(self.column_header(tslot, c.info["col"], r))
                    below = self.label_below(tslot, c)
                    if placeholder and not label and not header:
                        label = clean_label(txt.strip("<>[]"))
                    if not label and not header and not below:
                        continue
                    name = label if label and (not header or header == label) else \
                        ("%s — %s" % (label, header) if label and header else (header or below))
                    target = {"type": "cell_replace"} if txt else {"type": "cell"}
                    slash = []
                    for h in [header] + self.column_headers_all(tslot, c.info["col"], r):
                        parts = [x.strip() for x in re.split(r"\s*/\s*|\s+or\s+", clean_label(h))] if h else []
                        if len(parts) >= 2 and all(is_option_word(x) for x in parts):
                            slash = parts
                            break
                    if slash and label:
                        self.add(Area("choice", label, c, dict(target, write="option_text"), context=self.context_for(c),
                                      options=slash))
                        continue
                    self.add(Area(self.kind_for(name), clean_label(name), c, target, context=self.context_for(c)))

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
                    t2, pcs = self.ptext(nxt.el)
                    if t2.strip() or id(nxt.el) in self.claimed or nxt.el.find(".//" + TXBX) is not None:
                        break
                    blanks.append(nxt)
                    if not in_container and len(blanks) >= 1:
                        break
                if not blanks:
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
        return merge_spans(spans)

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
                    label = self.row_label(cell.parent, cell.info["row"], cell.info["col"]) or \
                        clean_label(self.column_header(cell.parent, cell.info["col"], cell.info["row"]))
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

    def segment_paragraph(self, slot, text, pieces, spans) -> int:
        made = 0
        blanks = list(spans)
        # 'Label:' followed by a gap (>=1 tab or >=3 spaces) or the end of the paragraph, with nothing else drawn
        for m in self.LABEL_COLON.finditer(text):
            end = m.end()
            if any(s <= m.start() < e or s <= end - 1 < e for s, e, _ in blanks):
                continue
            rest = text[end:]
            gap = re.match(r"[ \t   ]*", rest).group(0)
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
                continue                          # 'Date: (month/day/year)': the answer goes after the hint
            if after and not ("\t" in gap or len(gap) >= 3):
                continue                          # a sentence continues after the colon
            if after and not self.LABEL_COLON.match(after) and not re.match(r"\(?\s*(?:mm|dd|yy|hh|units?|kg|cm|lbs?|in|minutes?|hours?|days?|years?|%)\b", after, re.I):
                continue                          # other printed text follows the gap: not an answer space
            blanks.append((end, end + len(gap), "after_label"))
        blanks = merge_spans(blanks)
        if not blanks:
            return 0
        if self.is_heading(slot.el) and all(k == "after_label" for _, _, k in blanks) and not text.strip().endswith(":"):
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
            seg = text[prev_end:s]
            seg = re.split(r"[\x00" + BOX + CHECKED + "]", seg)[-1]
            seg = re.split(r"(?<=[.;!?])\s+(?=[A-Z(])", seg.strip())[-1]
            label = clean_label(seg)
            if kind in ("token", "bracket", "angle"):
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
        if self.answered_beside(slot):
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

    # 8. empty drawn boxes for initials (consent statement tables) -------------------------------------------------
    def rule_initial_boxes(self):
        WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
        for c in [s for s in self.index.slots if s.kind == "tc"]:
            if self.cell_has_claim(c.el) or self.cell_text(c):
                continue
            rects = [x for x in c.el.iter("{%s}wsp" % WPS) if x.find("{%s}txbx" % WPS) is None]
            if not rects:
                continue
            header = clean_label(self.column_header(c.parent, c.info["col"], c.info["row"]))
            label = self.row_label(c.parent, c.info["row"], c.info["col"])
            if INITIALS.search(header + " " + label) or re.search(r"\binitial", self.context_for(c), re.I):
                self.add(Area("initials", label or header or "Initials", c, {"type": "none"}, context=self.context_for(c)))

    def surface_duplicates(self):
        """Identical label + context for different areas is never guessed between: each gets its position."""
        groups = {}
        for a in self.areas:
            groups.setdefault((a.label, a.context), []).append(a)
        for (label, context), group in groups.items():
            if len(group) < 2:
                continue
            for n, a in enumerate(group, 1):
                where = "table row %d" % (a.slot.info["row"] + 1) if a.slot.kind == "tc" else a.slot.path
                a.context = ("%s · occurrence %d of %d (%s)" % (context, n, len(group), where)).strip(" ·")[:300]
                a.note = "duplicate label: position shown"

    # 9. the same field in several header/footer parts (first page, even, default) is one answer ------------------
    def merge_header_copies(self):
        by_key = {}
        for a in self.areas:
            if a.slot.part == "word/document.xml":
                continue
            key = (a.kind, a.label, a.slot.path, json_dumps(a.target))
            by_key.setdefault(key, []).append(a)
        for key, group in by_key.items():
            if len(group) < 2:
                continue
            keep = group[0]
            for other in group[1:]:
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


def area_to_field(n: int, area: Area) -> dict:
    target = dict(area.target)
    locator = {"contract": CONTRACT, "part": area.slot.part, "slot": area.slot.path, "target": target,
               "fingerprint": fingerprint(area.slot.el)}
    if area.extra_slots:
        locator["extra"] = [{"part": s.part, "slot": s.path, "fingerprint": fingerprint(s.el)} for s in area.extra_slots]
    field = {"key": "v3_%d" % n, "label": area.label or "Answer", "kind": area.kind, "context": area.context,
             "locator": locator}
    if area.options:
        field["options"] = list(area.options)
    return field


def inspect(data: bytes) -> dict:
    package = open_package(data)
    detector = Detector(package)
    areas, notes = detector.detect()
    if len(areas) > MAX_FIELDS:
        fail("The form has more answer areas than one mapping can hold (%d)." % MAX_FIELDS, "too_many_fields")
    fields = [area_to_field(i + 1, a) for i, a in enumerate(areas)]
    return {"contract": CONTRACT, "fields": fields, "notes": notes}
