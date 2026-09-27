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


# ─── slots ─────────────────────────────────────────────────────────────────────────────────────────────────────────

GLYPH_BOX = "☐□❏❑❒▢○"         # empty boxes (○ = radio option)
GLYPH_CHECKED = "☑☒✓✔■▣"     # ticked/filled boxes
# Wingdings/Symbol private-use checkbox glyphs written with w:sym (char codes, upper-case hex)
SYM_BOX = {"F06F", "F0A8", "F071", "F072", "F0FE", "F0FD", "006F", "00A8", "F0A3", "F070"}
SYM_CHECKED = {"F0FE", "F0FD", "F078", "F0FC", "F0FB", "F052", "F053", "F054", "F0D6"}


def text_of(el, *, skip_fallback=True, own=False) -> str:
    """Visible text; `own` leaves out text boxes anchored inside `el` (they are separate slots)."""
    out = []
    skip = {id(x) for fb in el.iter(q("mc:Fallback")) for x in fb.iter()} if skip_fallback else set()
    if own:
        skip.update(id(x) for t in el.iter(q("w:txbxContent")) for x in t.iter())
    for node in el.iter():
        if id(node) in skip:
            continue
        tag = node.tag
        if tag == q("w:t") and node.text:
            out.append(node.text)
        elif tag == q("w:tab") or tag == q("w:ptab"):
            out.append("\t")
        elif tag in (q("w:br"), q("w:cr")):
            out.append("\n")
        elif tag == q("w:sym"):
            code = (node.get(q("w:char")) or "").upper()
            out.append("☐" if code in SYM_BOX else "☒" if code in SYM_CHECKED else "")
        elif tag == q("w:noBreakHyphen"):
            out.append("-")
    return "".join(out)


def fingerprint(el) -> str:
    return hashlib.sha256(etree.tostring(el, method="c14n")).hexdigest()


@dataclass
class Slot:
    part: str
    path: str
    kind: str                     # p | tbl | tc | sdt | ff | txbx | glyphs
    el: object
    parent: "Slot | None" = None
    info: dict = dfield(default_factory=dict)

    @property
    def id(self):
        return "%s#%s" % (self.part, self.path)


class SlotIndex:
    """Every slot of the content parts, in document order, with a path -> element map."""

    def __init__(self, package: Package):
        self.package = package
        self.slots: list[Slot] = []
        self.by_id: dict[str, Slot] = {}
        for part in package.content_parts():
            root = package.tree(part)
            if part == "word/document.xml":
                body = root.find(q("w:body"))
                self._container(part, body, "b", None)
            else:
                self._container(part, root, "hf", None)

    def _add(self, slot):
        self.slots.append(slot)
        self.by_id[slot.id] = slot
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
            # inline content (runs) inside a block-less sdt is covered by the sdt slot itself

    def _table(self, part, el, path, parent):
        tslot = self._add(Slot(part, path, "tbl", el, parent))
        for ri, tr in enumerate(el.findall(q("w:tr"))):
            col = 0
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
        # hyperlink/smartTag wrappers can hold sdt too; they keep their own index space in the neutral grammar
        ff = 0
        skip = {id(x) for fb in el.iter(q("mc:Fallback")) for x in fb.iter()}
        for r in el.iter(q("w:r")):
            if id(r) in skip:
                continue
            fc = r.find(q("w:fldChar"))
            if fc is not None and fc.get(q("w:fldCharType")) == "begin":
                data = fc.find(q("w:ffData"))
                if data is not None:
                    self._add(Slot(part, "%s/ff[%d]" % (path, ff), "ff", r, pslot, ff_info(data)))
                    ff += 1
        txt = text_of(el, own=True)
        if any(ch in GLYPH_BOX or ch in GLYPH_CHECKED for ch in txt):
            self._add(Slot(part, "%s/glyphs" % path, "glyphs", el, pslot))
        tb = 0
        for t in el.iter(q("w:txbxContent")):
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
    name = data.find(q("w:name"))
    info["name"] = name.get(q("w:val")) if name is not None else None
    info["field"] = kind
    return info


# ─── detection ─────────────────────────────────────────────────────────────────────────────────────────────────────

UNDERSCORES = re.compile(r"_{3,}(?:[ \t]*_{2,})*")            # a blank line: ___ (runs may be split by spaces)
DOTS = re.compile(r"(?:\.{5,}|…{2,}|(?:\. ){4,}\.?)")    # a dotted leader: ....... or …… or . . . . .
BRACKET = re.compile(r"\[(?=[^\]\n]{2,120}\])(?:insert|enter|add|type|your|name|date|address|specify|[A-Z<])[^\]\n]*\]", re.I)
ANGLE = re.compile(r"<(?![/!?])[^<>\n]{3,120}>")                  # <Protocol Number: Title> author placeholders
TOKEN = re.compile(r"\{\{\s*([\w][\w .?:/()\-]{0,119}?)\s*\}\}")
PLACEHOLDER_TEXT = re.compile(r"^(?:click (?:or tap )?here to enter (?:text|a date)\.?|choose an item\.?|click or tap to enter a date\.?|"
                              r"enter (?:text|date)(?: here)?\.?|type here\.?|data to be filled in by site\.?|mm/dd/yyyy|dd/mm/yyyy)$", re.I)
CHECK_ALL = re.compile(r"\b(?:check|tick|mark|select|circle)\s+all\s+that\s+apply\b|\ball that apply\b", re.I)
CHECK_ONE = re.compile(r"\b(?:check|tick|choose|select|mark|circle)\s+(?:only\s+)?one\b", re.I)
SIGNATURE = re.compile(r"\bsignature\b|\bsigned\b|\bsign(?:ed)? here\b", re.I)
INITIALS = re.compile(r"\binitials?\b|\binitial (?:the )?box", re.I)
DATE_LABEL = re.compile(r"\b(?:date|dob|d\.o\.b|born)\b|mm/dd|dd/mm|yyyy", re.I)
TIME_LABEL = re.compile(r"\btime\b|hh:mm|\(24.?h", re.I)
LONG_LABEL = re.compile(r"\b(?:comments?|describe|description|details?|explain|notes?|summary|history|findings|plan|narrative|reason)\b", re.I)
HEADING_STYLE = re.compile(r"^(?:heading|title|subtitle|toc)", re.I)
LABEL_END = re.compile(r"[:?]\s*$|[–—-]\s*$")
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


def run_text_map(p):
    """(text, [(run_element, start, end, text_node_or_None)]) for a paragraph's own runs (not inside fields' instr,
    not inside text boxes or fallback copies, not inside nested content controls)."""
    pieces, pos = [], 0
    skip = set()
    for sub in p.iter(q("w:txbxContent"), q("mc:Fallback")):
        skip.update(id(x) for x in sub.iter())
    for r in p.iter(q("w:r")):
        if id(r) in skip:
            continue
        for node in r:
            tag = node.tag
            if tag == q("w:t"):
                t = node.text or ""
                pieces.append((r, pos, pos + len(t), node))
                pos += len(t)
            elif tag in (q("w:tab"), q("w:ptab")):
                pieces.append((r, pos, pos + 1, None))
                pos += 1
    text = "".join((n.text or "") if n is not None else "\t" for _, _, _, n in pieces)
    return text, pieces


def is_empty_cell(tc) -> bool:
    txt = text_of(tc).strip()
    if txt and not (set(txt) <= set("_ \t. ") or PLACEHOLDER_TEXT.match(txt)):
        return False
    if tc.find(".//" + q("w:tbl")) is not None or tc.find(".//" + q("w:sdt")) is not None:
        return False
    if tc.find(".//" + q("w:fldChar")) is not None:
        return False
    for occ in (q("w:drawing"), q("w:pict"), q("w:object")):
        if tc.find(".//" + occ) is not None:
            return False
    return True


def cell_label(tc) -> str:
    return re.sub(r"\s+", " ", text_of(tc)).strip()


def clean_label(text: str) -> str:
    text = re.sub(r"\s+", " ", text.replace("\t", " ")).strip()
    text = re.sub(r"^[\d]{1,3}[.)]\s+", "", text)
    return text.strip(" :–—-_")[:300]


class Detector:
    def __init__(self, package: Package):
        self.package = package
        self.index = SlotIndex(package)
        self.areas: list[Area] = []
        self.notes: list[str] = []
        self.claimed: set = set()          # element ids already turned into an area
        self._order = 0

    # -- helpers ---------------------------------------------------------------------------------------------------
    def add(self, area: Area):
        self._order += 1
        area.order = self._order
        self.areas.append(area)
        self.claimed.add(id(area.slot.el))

    def context_for(self, slot: Slot) -> str:
        """Nearest heading-like paragraph before the slot in its container, plus table row/column headers."""
        parts = []
        s = slot
        while s is not None and s.kind not in ("tc",):
            s = s.parent
        if s is not None and s.kind == "tc":
            tbl = s.parent
            row, col = s.info["row"], s.info["col"]
            header = self.column_header(tbl, col, row)
            rowlab = self.row_label(tbl, row, col)
            if rowlab:
                parts.append(rowlab)
            if header:
                parts.append(header)
        head = self.heading_before(slot)
        if head:
            parts.insert(0, head)
        return " > ".join(dict.fromkeys(p for p in parts if p))[:300]

    def heading_before(self, slot: Slot) -> str:
        part_slots = [s for s in self.index.slots if s.part == slot.part and s.kind == "p"]
        best = ""
        for s in part_slots:
            if s.el is slot.el or s.path >= slot.path and s.path.startswith(slot.path):
                break
            if self.is_heading(s.el):
                best = clean_label(text_of(s.el))
            if s.el is slot.el:
                break
        return best

    def is_heading(self, p) -> bool:
        ppr = p.find(q("w:pPr"))
        style = ppr.find(q("w:pStyle")).get(q("w:val")) if ppr is not None and ppr.find(q("w:pStyle")) is not None else ""
        txt = text_of(p).strip()
        if not txt or len(txt) > 120:
            return False
        if HEADING_STYLE.match(style or ""):
            return True
        runs = [r for r in p.iter(q("w:r")) if (r.findtext(q("w:t")) or "").strip()]
        bold = runs and all(r.find(q("w:rPr")) is not None and r.find(q("w:rPr")).find(q("w:b")) is not None for r in runs)
        return bool(bold) and not LABEL_END.search(txt) and len(txt.split()) <= 12

    def grid(self, tbl_slot: Slot):
        cells = [s for s in self.index.slots if s.parent is tbl_slot and s.kind == "tc"]
        rows = {}
        for c in cells:
            rows.setdefault(c.info["row"], []).append(c)
        return rows

    def column_header(self, tbl_slot, col, row) -> str:
        rows = self.grid(tbl_slot)
        for r in sorted(rows):
            if r >= row:
                break
            for c in rows[r]:
                if c.info["col"] <= col < c.info["col"] + c.info["span"] and not is_empty_cell(c.el):
                    txt = cell_label(c.el)
                    if txt and len(txt) <= 80:
                        header = txt
                        break
            else:
                continue
            return header
        return ""

    def row_label(self, tbl_slot, row, col) -> str:
        rows = self.grid(tbl_slot)
        for c in sorted(rows.get(row, []), key=lambda c: c.info["col"]):
            if c.info["col"] >= col:
                break
            if not is_empty_cell(c.el):
                txt = cell_label(c.el)
                if txt and len(txt) <= 200:
                    return clean_label(txt)
        return ""

    def text_before_in_paragraph(self, p, stop_el) -> str:
        out = []
        for node in p.iter():
            if node is stop_el:
                break
            if node.tag == q("w:t") and node.text:
                out.append(node.text)
            elif node.tag in (q("w:tab"), q("w:ptab")):
                out.append(" ")
        return "".join(out)

    def text_after_in_paragraph(self, p, start_el) -> str:
        out, seen = [], False
        for node in p.iter():
            if node is start_el:
                seen = True
                continue
            if seen and node.tag == q("w:t") and node.text:
                out.append(node.text)
        return "".join(out)

    # -- the rules -------------------------------------------------------------------------------------------------
    def detect(self):
        self.rule_content_controls()
        self.rule_checkboxes()
        self.rule_form_text_and_dropdowns()
        self.rule_tables()
        self.rule_paragraph_blanks()
        self.rule_inline_labels()
        self.rule_lines_below_label()
        self.rule_initial_boxes()
        self.merge_header_copies()
        self.areas.sort(key=lambda a: a.order)
        return self.areas, self.notes

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

    def label_for_inline(self, slot, el) -> str:
        """Text before `el` in its paragraph; else the left cell / row label; else the previous paragraph."""
        p = self.host_paragraph(slot)
        if p is not None:
            before = clean_label(self.text_before_in_paragraph(p.el, el))
            if before and not UNDERSCORES.fullmatch(before):
                return before
        cell = self.host_cell(slot)
        if cell is not None:
            left = self.row_label(cell.parent, cell.info["row"], cell.info["col"])
            if left:
                return left
            head = self.column_header(cell.parent, cell.info["col"], cell.info["row"])
            if head:
                return clean_label(head)
        prev = self.previous_paragraph_text(p) if p is not None else ""
        return clean_label(prev)

    def previous_paragraph_text(self, pslot, limit=3) -> str:
        siblings = [s for s in self.index.slots if s.kind == "p" and s.part == pslot.part and s.parent is pslot.parent]
        idx = next((i for i, s in enumerate(siblings) if s.el is pslot.el), None)
        if idx is None:
            return ""
        for s in reversed(siblings[max(0, idx - limit):idx]):
            t = text_of(s.el).strip()
            if t:
                return t
        return ""

    # 1. content controls ------------------------------------------------------------------------------------------
    def rule_content_controls(self):
        for slot in self.index.slots:
            if slot.kind != "sdt":
                continue
            info = slot.info
            typ = info["type"]
            if typ in ("docPartObj", "docPartList", "citation", "bibliography", "equation", "picture", "group"):
                continue
            if typ == "checkbox":
                continue                      # grouped by rule_checkboxes
            content = slot.el.find(q("w:sdtContent"))
            shown = text_of(content).strip() if content is not None else ""
            empty_like = info["placeholder"] or not shown or PLACEHOLDER_TEXT.match(shown) or set(shown) <= set("_ . ")
            if typ in ("dropDownList", "comboBox"):
                options = [o for o in info["options"] if o and not PLACEHOLDER_TEXT.match(o)]
                label = info["alias"] or info["tag"] or self.label_for_inline(slot, slot.el)
                self.add(Area("choice", clean_label(label) or "Choice", slot, {"type": "sdt_choice"},
                              context=self.context_for(slot), options=options))
            elif typ == "date":
                label = info["alias"] or info["tag"] or self.label_for_inline(slot, slot.el)
                self.add(Area("date", clean_label(label) or "Date", slot, {"type": "sdt_text", "date": True},
                              context=self.context_for(slot)))
            elif empty_like:
                label = info["alias"] or info["tag"] or self.label_for_inline(slot, slot.el)
                kind = self.kind_for(label)
                self.add(Area(kind, clean_label(label) or "Answer", slot, {"type": "sdt_text"}, context=self.context_for(slot)))
            else:
                self.notes.append("A content control holding fixed text was kept as printed: %s" % shown[:60])
            # nothing inside a content control is re-read by the other rules
            for x in slot.el.iter():
                self.claimed.add(id(x))

    # 2. checkboxes: content-control, legacy and glyph boxes, grouped into questions -------------------------------
    def checkbox_units(self):
        units = []
        for slot in self.index.slots:
            if slot.kind == "sdt" and slot.info["type"] == "checkbox":
                units.append(("sdt", slot, slot.el, None))
            elif slot.kind == "ff" and slot.info["field"] == "FORMCHECKBOX":
                units.append(("ff", slot, slot.el, None))
            elif slot.kind == "glyphs":
                p = slot.el
                if id(p) in self.claimed:
                    continue
                count = sum(1 for ch in text_of(p, own=True) if ch in GLYPH_BOX or ch in GLYPH_CHECKED)
                for i in range(count):
                    units.append(("glyph", slot, p, i))
        return units

    def option_text(self, kind, slot, el, glyph_index):
        p = self.host_paragraph(slot) if kind != "glyph" else slot.parent
        pel = p.el if p is not None else el
        full = text_of(pel, own=True)
        if kind == "glyph":
            marks = [i for i, ch in enumerate(full) if ch in GLYPH_BOX or ch in GLYPH_CHECKED]
            if glyph_index >= len(marks):
                return "", ""
            start = marks[glyph_index] + 1
            end = marks[glyph_index + 1] if glyph_index + 1 < len(marks) else len(full)
            before = full[:marks[glyph_index]]
            return clean_label(full[start:end]), before
        after = self.text_after_in_paragraph(pel, el)
        before = self.text_before_in_paragraph(pel, el)
        # up to the next box in the same paragraph
        nxt = re.split(r"[☐☑☒]", after, maxsplit=1)[0]
        return clean_label(nxt), before

    def rule_checkboxes(self):
        units = self.checkbox_units()
        groups, current, last_container, last_para = [], [], None, None
        for kind, slot, el, gi in units:
            p = self.host_paragraph(slot) if kind != "glyph" else slot.parent
            container = p.parent if p is not None else None
            same_para = last_para is not None and p is not None and p.el is last_para.el
            adjacent = False
            if not same_para and current and p is not None and last_para is not None and container is last_container:
                sibs = [s for s in self.index.slots if s.kind == "p" and s.part == p.part and s.parent is container]
                ia = next((i for i, s in enumerate(sibs) if s.el is last_para.el), None)
                ib = next((i for i, s in enumerate(sibs) if s.el is p.el), None)
                if ia is not None and ib is not None and 0 < ib - ia <= 1:
                    between = [text_of(s.el).strip() for s in sibs[ia + 1:ib]]
                    adjacent = not any(between)
            if current and (same_para or adjacent):
                current.append((kind, slot, el, gi))
            else:
                if current:
                    groups.append(current)
                current = [(kind, slot, el, gi)]
            last_container, last_para = container, p
        if current:
            groups.append(current)
        for group in groups:
            options, befores = [], []
            for kind, slot, el, gi in group:
                opt, before = self.option_text(kind, slot, el, gi)
                options.append(opt)
                befores.append(before)
            first_kind, first_slot, first_el, _ = group[0]
            p = self.host_paragraph(first_slot) if first_kind != "glyph" else first_slot.parent
            question = clean_label(befores[0]) if befores and clean_label(befores[0]) else ""
            if not question and p is not None:
                cell = self.host_cell(p)
                if cell is not None and p.parent is cell:
                    first_in_cell = next((s for s in self.index.slots if s.parent is cell and s.kind == "p"), None)
                    if first_in_cell is not None and first_in_cell.el is p.el:
                        question = self.row_label(cell.parent, cell.info["row"], cell.info["col"]) or \
                            clean_label(self.column_header(cell.parent, cell.info["col"], cell.info["row"]))
                if not question:
                    question = clean_label(self.previous_paragraph_text(p))
            hint = " ".join([question] + options)
            boxes = [{"kind": k, "slot": s.path, "part": s.part, "glyph": gi} for k, s, e, gi in group]
            target = {"type": "checkboxes", "boxes": boxes}
            extra = [s for _, s, _, _ in group[1:]]
            if len(group) == 1:
                label = options[0] or question or "Checkbox"
                area = Area("checkbox", label, first_slot, target, context=self.context_for(first_slot),
                            options=[options[0]] if options[0] else [])
            else:
                kind = "multi_choice" if CHECK_ALL.search(hint) else "choice"
                area = Area(kind, question or "Choose", first_slot, target, context=self.context_for(first_slot),
                            options=[o or "(option %d)" % (i + 1) for i, o in enumerate(options)], extra_slots=extra)
            self.add(area)
            for _, s, e, _ in group:
                self.claimed.add(id(e))

    # 3. legacy text fields and dropdowns --------------------------------------------------------------------------
    def rule_form_text_and_dropdowns(self):
        for slot in self.index.slots:
            if slot.kind != "ff" or slot.info["field"] == "FORMCHECKBOX":
                continue
            label = self.label_for_inline(slot, slot.el) or slot.info.get("name") or "Answer"
            if slot.info["field"] == "FORMDROPDOWN":
                self.add(Area("choice", clean_label(label), slot, {"type": "ff_dropdown"}, context=self.context_for(slot),
                              options=[o for o in slot.info.get("options", []) if o]))
            else:
                self.add(Area(self.kind_for(label), clean_label(label), slot, {"type": "ff_text"}, context=self.context_for(slot)))

    def kind_for(self, label: str) -> str:
        if SIGNATURE.search(label or "") and not DATE_LABEL.search(label or ""):
            return "signature"
        if INITIALS.search(label or "") and not DATE_LABEL.search(label or ""):
            return "initials"
        if TIME_LABEL.search(label or "") and not DATE_LABEL.search(label or ""):
            return "time"
        if DATE_LABEL.search(label or ""):
            return "date"
        if LONG_LABEL.search(label or ""):
            return "long_text"
        return "text"

    # 4. tables ----------------------------------------------------------------------------------------------------
    def cell_has_claim(self, tc) -> bool:
        return any(id(x) in self.claimed for x in tc.iter())

    def rule_tables(self):
        for tslot in [s for s in self.index.slots if s.kind == "tbl"]:
            rows = self.grid(tslot)
            empty_rows = {}
            for r, cells in rows.items():
                cells = [c for c in cells if c.info["vmerge"] != "continue"]
                empties = [c for c in cells if is_empty_cell(c.el) and not self.cell_has_claim(c.el)]
                empty_rows[r] = (cells, empties)
            # log tables: >= 2 consecutive fully-empty rows under a header row -> one table_rows area
            handled_rows = set()
            ordered = sorted(rows)
            i = 0
            while i < len(ordered):
                r = ordered[i]
                cells, empties = empty_rows[r]
                if cells and len(empties) == len(cells) and len(cells) >= 2:
                    run = [r]
                    j = i + 1
                    while j < len(ordered):
                        c2, e2 = empty_rows[ordered[j]]
                        if c2 and len(e2) == len(c2) and len(c2) == len(cells):
                            run.append(ordered[j]); j += 1
                        else:
                            break
                    header_cols = [self.column_header(tslot, c.info["col"], r) for c in cells]
                    if len(run) >= 2 and any(header_cols):
                        first = cells[0]
                        self.add(Area("table_rows", clean_label(self.heading_before(first) or "Table") or "Table", first,
                                      {"type": "table_rows", "table": tslot.path, "rows": run,
                                       "columns": [c.info["col"] for c in cells]},
                                      context=self.context_for(first), options=[clean_label(h) for h in header_cols]))
                        handled_rows.update(run)
                        for rr in run:
                            for c in empty_rows[rr][1]:
                                self.claimed.add(id(c.el))
                        i = j
                        continue
                i += 1
            for r in ordered:
                if r in handled_rows:
                    continue
                cells, empties = empty_rows[r]
                for c in empties:
                    label = self.row_label(tslot, r, c.info["col"])
                    header = clean_label(self.column_header(tslot, c.info["col"], r))
                    if not label and not header:
                        continue                      # a blank cell with nothing naming it: not a question
                    if label and header and header != label:
                        name = "%s — %s" % (label, header)
                    else:
                        name = label or header
                    txt = text_of(c.el).strip()
                    target = {"type": "cell"} if not txt else {"type": "cell_replace"}
                    self.add(Area(self.kind_for(name), clean_label(name), c, target, context=self.context_for(c)))
                # a label cell whose answer goes after the label inside the same cell ("Investigator Name:")
                for c in cells:
                    if c in empties or self.cell_has_claim(c.el):
                        continue
                    paras = [s for s in self.index.slots if s.parent is c and s.kind == "p"]
                    txt = text_of(c.el).strip()
                    right = [x for x in cells if x.info["col"] > c.info["col"]]
                    right_empty = right and right[0] in empties
                    if right_empty or not txt or len(txt) > 120 or len(paras) != 1:
                        continue
                    if re.search(r":\s*(?:\([^)]{0,40}\))?\s*$", txt) and len(txt.split()) <= MAX_LABEL_WORDS:
                        self.add(Area(self.kind_for(txt), clean_label(txt), paras[0], {"type": "after_label"},
                                      context=self.context_for(paras[0])))
                        self.claimed.add(id(paras[0].el))

    # 5. blanks inside paragraphs: underscores, dotted leaders, underlined tabs, placeholders ----------------------
    def rule_paragraph_blanks(self):
        for slot in [s for s in self.index.slots if s.kind == "p"]:
            p = slot.el
            if id(p) in self.claimed:
                continue
            cell = self.host_cell(slot)
            if cell is not None and id(cell.el) in self.claimed:
                continue
            text, pieces = run_text_map(p)
            if not text.strip():
                continue
            spans = []
            for m in UNDERSCORES.finditer(text):
                spans.append((m.start(), m.end(), "blank"))
            for m in DOTS.finditer(text):
                spans.append((m.start(), m.end(), "blank"))
            for m in TOKEN.finditer(text):
                spans.append((m.start(), m.end(), "token"))
            for m in BRACKET.finditer(text):
                spans.append((m.start(), m.end(), "bracket"))
            for m in ANGLE.finditer(text):
                spans.append((m.start(), m.end(), "angle"))
            # underlined tab runs (the existing tab-form contract's blank)
            for r, s, e, node in pieces:
                if node is None:
                    rpr = r.find(q("w:rPr"))
                    u = rpr.find(q("w:u")) if rpr is not None else None
                    if u is not None and (u.get(q("w:val")) or "single") != "none":
                        spans.append((s, e, "utab"))
            spans = merge_spans(spans)
            if not spans:
                continue
            prev_end = 0
            for n, (s, e, kind) in enumerate(spans):
                seg = text[prev_end:s]
                label = clean_label(seg)
                if kind in ("token", "bracket", "angle"):
                    inner = clean_label(text[s:e].strip("{}[]<> "))
                    label = inner if kind == "token" or not label else ("%s %s" % (label, inner)).strip()
                if not label:
                    nxt = spans[n + 1][0] if n + 1 < len(spans) else len(text)
                    label = clean_label(text[e:nxt]) or clean_label(self.previous_paragraph_text(slot)) or "Answer"
                self.add(Area(self.kind_for(label), label, slot, {"type": "span", "start": s, "end": e, "shape": kind},
                              context=self.context_for(slot)))
                prev_end = e
            self.claimed.add(id(p))

    # 6. "Label:" lines whose answer goes after the label (no blank drawn) -----------------------------------------
    def rule_inline_labels(self):
        for slot in [s for s in self.index.slots if s.kind == "p"]:
            p = slot.el
            if id(p) in self.claimed or any(id(x) in self.claimed for x in p.iter(q("w:r"))):
                continue
            cell = self.host_cell(slot)
            if cell is not None and self.cell_has_claim(cell.el):
                continue
            txt = text_of(p).strip()
            if not txt or len(txt) > 160 or self.is_heading(p) and not txt.endswith(":"):
                continue
            m = re.search(r"^(.*?[^\s:])\s*(?::|–|—| -)\s*(\([^)]{0,60}\))?\s*$", txt)
            if not m or len(m.group(1).split()) > MAX_LABEL_WORDS or not txt.rstrip().endswith((":", "–", "—", "-", ")")):
                continue
            if txt.rstrip().endswith(")") and not m.group(2):
                continue
            # a question whose options follow on the next paragraph(s) belongs to that choice, not to a text answer
            nxt = self.next_paragraph(slot)
            if nxt is not None and any(id(x) in self.claimed for x in nxt.el.iter()) and self.is_option_line(nxt):
                continue
            if self.is_section_heading_line(slot, txt):
                continue
            label = clean_label(m.group(1))
            self.add(Area(self.kind_for(label + " " + (m.group(2) or "")), label, slot, {"type": "after_label"},
                          context=self.context_for(slot)))

    def next_paragraph(self, slot):
        sibs = [s for s in self.index.slots if s.kind == "p" and s.part == slot.part and s.parent is slot.parent]
        idx = next((i for i, s in enumerate(sibs) if s.el is slot.el), None)
        return sibs[idx + 1] if idx is not None and idx + 1 < len(sibs) else None

    def is_option_line(self, pslot) -> bool:
        return any(s.kind in ("ff", "glyphs") or (s.kind == "sdt" and s.info["type"] == "checkbox")
                   for s in self.index.slots if s.parent is pslot or s is pslot)

    def is_section_heading_line(self, slot, txt) -> bool:
        """A 'Findings:' line that heads the lines below it rather than taking an answer after it."""
        nxt = self.next_paragraph(slot)
        if nxt is None:
            return False
        nt = text_of(nxt.el).strip()
        if not nt:
            return False
        numbered = nxt.el.find(".//" + q("w:numPr")) is not None
        return bool(numbered and not self.is_option_line(nxt) and self.is_heading(slot.el))

    # 7. a label followed by empty paragraph(s) in the same cell or text box: the answer goes on those lines -------
    def rule_lines_below_label(self):
        containers = [s for s in self.index.slots if s.kind in ("tc", "txbx")]
        for c in containers:
            if id(c.el) in self.claimed:
                continue
            paras = [s for s in self.index.slots if s.parent is c and s.kind == "p"]
            for i, ps in enumerate(paras):
                txt = text_of(ps.el).strip()
                if not txt or not txt.endswith(":") or id(ps.el) in self.claimed:
                    continue
                blanks = []
                for nxt in paras[i + 1:]:
                    if text_of(nxt.el).strip() or id(nxt.el) in self.claimed:
                        break
                    blanks.append(nxt)
                if not blanks:
                    continue
                label = clean_label(txt)
                kind = "long_text" if len(blanks) >= 2 else self.kind_for(label)
                self.add(Area(kind, label, blanks[0], {"type": "paragraph"}, context=self.context_for(ps),
                              extra_slots=blanks[1:]))
                self.claimed.add(id(ps.el))
                for b in blanks:
                    self.claimed.add(id(b.el))

    # 8. empty drawn boxes for initials (consent statement tables) -------------------------------------------------
    def rule_initial_boxes(self):
        WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
        for c in [s for s in self.index.slots if s.kind == "tc"]:
            if self.cell_has_claim(c.el) or text_of(c.el).strip():
                continue
            shapes = [x for x in c.el.iter("{%s}wsp" % WPS)]
            rects = [x for x in shapes if x.find("{%s}txbx" % WPS) is None]
            if not rects:
                continue
            header = clean_label(self.column_header(c.parent, c.info["col"], c.info["row"]))
            label = self.row_label(c.parent, c.info["row"], c.info["col"])
            if INITIALS.search(header + " " + label) or "initial" in (self.context_for(c) or "").lower():
                self.add(Area("initials", label or header or "Initials", c, {"type": "none"}, context=self.context_for(c)))

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
                keep.extra_slots.append(other.slot)
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
