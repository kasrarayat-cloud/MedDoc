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
from datetime import date

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

# Exact original blanks with retained rendered failures, not width guesses or
# qualification of changed/proxy documents. Each remains unsupported until its
# growth contract is independently qualified. Original stored exports are never
# rewritten. New import manifests carry this evidence to the admission guard.
KNOWN_LAYOUT_FAILURES = {
    "bc002ff4594eb374f1748c8e80a66dfa432bc1432d98cd4e218a06d3515d0c66": {
        "case": "D27",
        "failed_anchors": [
            {
                "part": "word/document.xml",
                "slot": "b/tbl[5]/tr[6]/tc[1]",
                "fingerprint": "f43b264a2a4e0d1a370968fa5f63910d8731f33825abffeb138a5e52389f12fb"
            },
            {
                "part": "word/document.xml",
                "slot": "b/tbl[8]/tr[1]/tc[5]/p[0]",
                "fingerprint": "0e258b98e64b64bc9716c7de1a01d30ca3fbddc88f3162203cdcc48a66d4784c"
            },
            {
                "part": "word/document.xml",
                "slot": "b/tbl[9]/tr[1]/tc[5]/p[0]",
                "fingerprint": "171d6aa4caade933fc6dfea8ece21f8b6407568ad01898d1327b4a5bdb1b07a3"
            },
            {
                "part": "word/footer2.xml",
                "slot": "hf/p[1]",
                "fingerprint": "96beb00f4b0e94110ddf741159d52937818ab5031c51bac325620fb01d78767d",
                "copies": [
                    {
                        "part": "word/footer3.xml",
                        "slot": "hf/p[1]",
                        "fingerprint": "04133e66bad8d8b0b6c6465ede81375c550085b692e94db332461f936a57fd7a"
                    }
                ]
            },
            {
                "part": "word/header2.xml",
                "slot": "hf/p[0]",
                "fingerprint": "beb6a4109bd8d8d5f2274d2913507372a4e72378111505029f32ebcf41c48c07",
                "copies": [
                    {
                        "part": "word/header3.xml",
                        "slot": "hf/p[0]",
                        "fingerprint": "f9d88e2f21fb7099ed0350ce25e35c239e4e2670fe653e888d95b4e63f1cff28"
                    }
                ]
            }
        ],
        "evidence": [
            "development-coverage-5a06295a6bcf-20261003T005255569947Z",
            "retained-export-render-20261003T014550746568Z",
            "fixed096-render-20261003T021326015945Z"
        ],
        "measurements": [
            {
                "artifact": "retained-export-render-20261003T014550746568Z/D27/pdfium-geometry-supplement.json",
                "sha256": "698e72a9691a928ecf0df5e5ad4cf8ef653ab8b22a9b239a7511fd76cb46e32e",
                "long_new_overlap_pairs": 96,
                "long_missing_probes": [
                    "v3_38"
                ],
                "original_pdf_sha256": "978aafae128d0f332bced93651ffd36778d4ea53bae3864d2bb18511f28c003f",
                "export_pdf_sha256": "36a3122233ba93add830926554dccac5b80b8505843bd2432e7f08f0ea936eeb"
            },
            {
                "artifact": "fixed096-render-20261003T021326015945Z/D27/pdfium-geometry-supplement.json",
                "sha256": "353c6e5dab634dbc42a5e2cfd20bef63e105badbd32637cc66e0c071cfa3ee67",
                "long_new_overlap_pairs": 0,
                "long_missing_probes": [
                    "v3_25",
                    "v3_40"
                ],
                "original_pdf_sha256": "8620c0a9aee972042bbad25549253ca961ec3570392d019cead870c778f98656",
                "export_pdf_sha256": "a8f09f15b57f4dfe9cb060506a313e7501470ca3e12c3364369c17d3760619d4"
            }
        ]
    },
    "cf9b240f3893f97bf168c7cd3ac808bb720b3bf0f65b168c9671c6827ca1a4b7": {
        "case": "D35",
        "failed_anchors": [
            {
                "part": "word/document.xml",
                "slot": "b/tbl[9]/tr[18]/tc[2]",
                "fingerprint": "8efb5bf6bca7de20a1417c7dd8ffad09a7fe5b92130ff7e90b82d947e6b837ca"
            },
            {
                "part": "word/header1.xml",
                "slot": "hf/p[0]/txbx[0]/p[0]",
                "fingerprint": "2c4c5b60ecdb4e8144f1a37359bf132b2c4c6e81c7b20a06ecf30185913023ff",
                "copies": [
                    {
                        "part": "word/header2.xml",
                        "slot": "hf/p[0]/txbx[0]/p[0]",
                        "fingerprint": "fbb2ee921630eb011e4a13957b286dd9a2a90e614e1f9c1f4c189ddee6b93bf7"
                    },
                    {
                        "part": "word/header3.xml",
                        "slot": "hf/p[0]/txbx[0]/p[0]",
                        "fingerprint": "50150ee99595390e15fb340501ad3b64bc71817f7cfc1d05bae7069d24e7a5b8"
                    }
                ]
            }
        ],
        "evidence": [
            "development-coverage-5a06295a6bcf-20261003T005255569947Z",
            "retained-export-render-20261003T014550746568Z",
            "fixed096-render-20261003T021326015945Z"
        ],
        "measurements": [
            {
                "artifact": "retained-export-render-20261003T014550746568Z/D35/pdfium-geometry-supplement.json",
                "sha256": "d208407ebd773ede29a1f46836d9dcf760bb0e0745ae187a39caa167c5905f55",
                "long_new_overlap_pairs": 0,
                "long_missing_probes": [
                    "v3_257",
                    "v3_299"
                ],
                "original_pdf_sha256": "094d4bd75cdd77f9e40e422765668bb9e0128d375e1e9e48a1eeb29ded000d06",
                "export_pdf_sha256": "b99932f05c7ed36e4be51fb169a032bfad84617b666fed89366105f66f894896"
            },
            {
                "artifact": "fixed096-render-20261003T021326015945Z/D35/pdfium-geometry-supplement.json",
                "sha256": "eaafaa807b24ce3db7330b3d6ddd560befbda1d67522714ed866fee8a8dfaf06",
                "long_new_overlap_pairs": 0,
                "long_missing_probes": [
                    "v3_257"
                ],
                "original_pdf_sha256": "53396a5797d748098e16f28454ca1baedff9254390f0f93b9982184f48931018",
                "export_pdf_sha256": "13c16246fc72fa9a1e94bf146dc3b5f8a5fe8a0672e1be3c6be4fb20d47d520b"
            }
        ]
    }
}
MAX_ANSWER = 100_000
#: A content control the original locks (contentLocked / sdtContentLocked): its content cannot take an answer, so
#: its area is protected and the control is a destination role (destination_roles).
# Shared finite auxiliary grammar: prospective source actions and appointed
# response authors read the same tense/aspect/obligation relationship.
SOURCE_ACTION_AUXILIARY = (r'(?:will|would|shall|should|can|could|may|might|must|cannot|'
                           r'am|is|are|was|were|has|have|had|do|does|did|been|being|not|yet|hereby|personally)')

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


def known_layout_failure(data):
    """The exact-source declaration is independent of parser or engine success."""
    source_hash=hashlib.sha256(data).hexdigest()
    declaration=KNOWN_LAYOUT_FAILURES.get(source_hash)
    return {'source_sha256':source_hash,**declaration} if declaration else None


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
            target.comment = self.zip.comment
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
        if lower.startswith('_xmlsignatures/'):
            fail('Digitally signed Word files are not editable templates. Upload an unsigned blank original.', 'signed_document')
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
            if any(node.tag == q('w:documentProtection') and node.get(q('w:enforcement'), '0') not in ('0', 'false', 'off')
                   for node in tree.iter()):
                fail('Protected Word files are not editable templates. Upload an unprotected blank original.', 'protected_document')
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
NUMERIC_PARTS = re.compile(r"[ \t]*\u25af+(?:[ \t]*[/.:\-][ \t]*\u25af+)+[ \t]*")


def numeric_part_ranges(text):
    """A complete empty numeric band; separators identify parts, never their clinical labels."""
    if not NUMERIC_PARTS.fullmatch(text):
        return []
    parts = [(match.start(), match.end()) for match in re.finditer(r'\u25af+', text)]
    return parts if len(parts) <= 100 else []


def numeric_part_value(source, current, number):
    """Read one reviewed part independently of simultaneous edits to the other parts."""
    parts = numeric_part_ranges(source)
    if type(number) is not int or not 1 <= number <= len(parts):
        return None
    pattern, end = [], 0
    for start, stop in parts:
        pattern.extend((re.escape(source[end:start]), '([0-9]{1,%d}|%s)' % (stop - start, re.escape(source[start:stop]))))
        end = stop
    pattern.append(re.escape(source[end:]))
    match = re.fullmatch(''.join(pattern), current)
    if not match:
        return None
    value = match.group(number)
    return '' if value == source[slice(*parts[number - 1])] else value
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
    source_action: bool = False     # source-owned action; role bounded to this destination, not its whole paragraph
    ordinary_reading: bool = False  # fresh physical argument, never a reviewed label or persisted permission


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
        self.withdrawn_areas: list[Area] = []   # EC3: answer areas withdrawn from shared merged cells
        self.coverage_issues: list[dict] = []   # source-bound exclusions, never inferred from field counts
        self.shared_kept: set = set()            # id() of signing/protected areas kept inside a shared merged cell
        self.notes: list[str] = []
        self.claimed: set = set()          # element ids already turned into an area (or used as its label)
        self.protected_regions: set[str] = set()
        self.response_header_corners: set[str] = set()
        self.fixed_subheading_slots: set[str] = set()
        self.box_action_reasons: dict[str, str] = {}
        self.geometry_regions: dict[str, str] = {}
        self.layout_quarantine = None
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
        # Only this detector's immutable source package owns these style readings.
        # Physical paragraph/run visibility still reads its actual XML each time.
        self._style_index = None
        self._style_defaults = None
        self._style_chains = {}
        self._form_wide = None
        self._form_wide_nodes = []        # keeps the guidance paragraphs alive: their ids key the scope reading
        self._named_guidance = None       # immutable original's captions, physical owners and named instructions
        self._coded_problem = ""
        self._compute_headings()

    def coverage_issue(self, slot, code, detail, *, start=None, end=None):
        issue = {'part': slot.part, 'slot': slot.path, 'code': code, 'detail': detail}
        if start is not None:issue.update(start=start,end=end)
        issue['id'] = hashlib.sha256(repr((slot.part, slot.id, code, detail, start, end)).encode()).hexdigest()
        if not any(prior['id'] == issue['id'] for prior in self.coverage_issues):
            self.coverage_issues.append(issue)

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
            slot = self.index.by_el.get(id(p))
            if not result and slot is not None and self.fixed_underlined_subheading(slot):
                result = True
                self.fixed_subheading_slots.add(slot.id)
        self._is_heading[id(p)] = result
        return result

    def fixed_underlined_subheading(self, slot) -> bool:
        """A completely underlined caption owns two separate literal-list answer lines.

        The caption itself has no answer gap. Underlining alone, a following
        blank line or one question cannot establish this hierarchy. Actual XML
        siblings, rather than a paragraph-only view across tables, own the scope.
        """
        if slot.kind != 'p':
            return False
        text, pieces = self.ptext(slot.el)
        if (not text or text != text.strip() or not text.endswith(':')
                or text.count(':') != 1 or len(text.split()) > MAX_LABEL_WORDS
                or re.match(r'^[-\u2022]\s', text)
                or '\x00' in text or BOX in text or CHECKED in text):
            return False
        runs = [r for r in slot.el.iter(R) if any((n.text or '').strip() for n in r.iter(T))]
        if not runs or any((u := r.find('./' + q('w:rPr') + '/' + q('w:u'))) is None
                           or u.get(q('w:val'), 'single') not in ('single', 'double') for r in runs):
            return False
        if (not self.tab_source_visible(slot) or self.list_info(slot.el) is not None
                or self.blank_spans(text, pieces) or self.checkbox_source_action(text, governing=True)):
            return False
        children = []
        node = slot.el.getnext()
        while node is not None and node.tag == q('w:p'):
            child = self.index.by_el.get(id(node))
            if child is None or child.parent is not slot.parent or not self.tab_source_visible(child):
                break
            printed, _ = self.ptext(node)
            match = re.fullmatch(r'\s*-\s+([^:?!\t\n\x00]+):([ \u00a0\u2002\u2003]+)', printed)
            if (match is None or len(match.group(1).split()) > MAX_LABEL_WORDS
                    or not re.search(r'[A-Za-z]', match.group(1))
                    or BOX in printed or CHECKED in printed or self.list_info(node) is not None):
                break
            children.append(clean_label(match.group(1)))
            node = node.getnext()
        return len(children) >= 2 and len(set(children)) == len(children)

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

    def response_matrix_header_corner(self, tbl_slot, r):
        """Fixed header spacing even when response controls cannot be qualified.

        This proves where the header is, not whether any response may be written.
        A physical response axis over captioned checkbox bands keeps its empty
        corner fixed when merges, visibility or extra controls require review.
        A drawn blank or another genuine answer in the corner is never excluded.
        """
        key = ("response-header-corner", id(tbl_slot), r)
        if key in self._grid:
            return self._grid[key]
        self._grid[key] = None
        rows = self.grid(tbl_slot)
        if not rows or r != min(rows):
            return None
        cells = sorted(rows[r], key=lambda cell: cell.info["col"])
        width = self.grid_cols(tbl_slot)
        if len(cells) < 2 or width < 3:
            return None
        corner = cells[0]
        if (corner.info["col"] != 0 or corner.info["span"] != 1 or corner.info["vmerge"]
                or not self.is_empty_cell(corner) or not self.cell_is_plain(corner) or not corner.children
                or any(p.kind != "p" or not self.plain_spacing_paragraph(p)
                       or not self.tab_source_visible(p) for p in corner.children)):
            return None
        column, labels = 1, []
        for cell in cells[1:]:
            if cell.info["col"] != column or not cell.children:
                return None
            for para in cell.children:
                if para.kind != "p" or self.box_units(para) or self.blank_spans(*self.ptext(para.el)):
                    return None
                text = self.ptext(para.el)[0].strip()
                if not response_word(text):
                    return None
                labels.append(text)
            column += cell.info["span"]
        if column != width or len(labels) < 2:
            return None
        complete = 0
        for row in sorted(rr for rr in rows if rr > r):
            body = sorted(rows[row], key=lambda cell: cell.info["col"])
            if row != r + complete + 1 or not body:
                break
            label = body[0]
            if (label.info["col"] != 0 or label.info["span"] != 1 or label.info["vmerge"]
                    or not self.is_label_cell(label, complete=True) or not label.children
                    or any(p.kind != "p" or self.box_units(p) or self.blank_spans(*self.ptext(p.el))
                           for p in label.children)):
                break
            column, boxed = 1, True
            for cell in body[1:]:
                source = self.merge_head(tbl_slot, cell)
                paras = list(self.own_paragraphs(source))
                text = "".join(self.ptext(p.el)[0] for p in paras)
                if (cell.info["col"] != column or not paras or re.sub(r"[\s☐☒]", "", text)
                        or not (BOX in text or CHECKED in text)):
                    boxed = False
                    break
                column += cell.info["span"]
            if not boxed or column != width:
                break
            complete += 1
        if complete >= 2:
            self._grid[key] = corner
        return self._grid[key]

    def response_matrix_corner(self, tbl_slot, r):
        """A fixed empty corner above one complete, aligned response axis.

        The empty first cell alone proves nothing. The original must print distinct
        response headers over at least two consecutive captioned rows, each with
        exactly one visible checkbox in every response column. A merge, gap,
        additional caption/control or marked corner cannot establish this axis.
        """
        key = ("response-matrix-corner", id(tbl_slot), r)
        if key in self._grid:
            return self._grid[key]
        self._grid[key] = None
        rows = self.grid(tbl_slot)
        if not rows or r != min(rows):
            return None
        cells = sorted(rows[r], key=lambda cell: cell.info["col"])
        width = self.grid_cols(tbl_slot)
        if (len(cells) < 3 or width != len(cells)
                or any(c.info["col"] != i or c.info["span"] != 1 or c.info["vmerge"]
                       for i, c in enumerate(cells))):
            return None
        corner = cells[0]
        if (not self.is_empty_cell(corner) or not self.cell_is_plain(corner)
                or not corner.children or any(p.kind != "p" or not self.plain_spacing_paragraph(p)
                                              or not self.tab_source_visible(p) for p in corner.children)):
            return None
        headers = [self.cell_text(c) for c in cells[1:]]
        if (len(set(h.casefold() for h in headers)) != len(headers)
                or not all(response_word(h) for h in headers)):
            return None
        for cell in cells[1:]:
            if (not cell.children or any(p.kind != "p" or not self.tab_source_visible(p)
                                        or self.box_units(p) or self.blank_spans(*self.ptext(p.el))
                                        for p in cell.children)):
                return None
        complete = 0
        for row in sorted(rr for rr in rows if rr > r):
            body = sorted(rows[row], key=lambda cell: cell.info["col"])
            if (row != r + complete + 1 or len(body) != width
                    or any(c.info["col"] != i or c.info["span"] != 1 or c.info["vmerge"]
                           for i, c in enumerate(body))):
                break
            label = body[0]
            if (not self.is_label_cell(label, complete=True) or not label.children
                    or any(p.kind != "p" or not self.tab_source_visible(p)
                           or self.box_units(p) or self.blank_spans(*self.ptext(p.el))
                           for p in label.children)):
                break
            def one_response_box(cell):
                paras = list(self.own_paragraphs(cell))
                return (bool(paras) and all(self.tab_source_visible(p)
                                           and not self.blank_spans(*self.ptext(p.el)) for p in paras)
                        and "".join(self.ptext(p.el)[0] for p in paras).strip() in (BOX, CHECKED)
                        and sum(len(self.box_units(p)) for p in paras) == 1)
            if any(not one_response_box(c) for c in body[1:]):
                break
            complete += 1
        if complete >= 2:
            self._grid[key] = corner
        return self._grid[key]

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
        if self.response_matrix_corner(tbl_slot, r) is not None:
            kind = "label"
        self._grid[key] = kind
        return kind

    def merge_index(self, tbl_slot):
        """(any vertical merge in the table, its row numbers in order, each row's position, the cell at (row, col)) -
        read once per table, so the EC3 pass reads a merge in steps proportional to its own rows (WE3-m-3: re-sorting
        every later row for each cell made a 2,400-row log exceed the sandbox's CPU limit)."""
        key = ("merge-index", id(tbl_slot))
        if key not in self._grid:
            rows = self.grid(tbl_slot)
            order = sorted(rows)
            at = {(c.info["row"], c.info["col"]): c for r in order for c in rows[r]}
            merged = any(c.info["vmerge"] for c in at.values())
            self._grid[key] = (merged, order, {r: i for i, r in enumerate(order)}, at)
        return self._grid[key]

    def merge_head(self, tbl_slot, cell):
        """The first cell of the vertical merge `cell` belongs to: `cell` itself unless it is a continuation; else the
        nearest cell above it in its column that is no continuation (a restart, or a plain cell the continuation
        continues), else the TOPMOST continuation of the run.

        ⚠️ FAIL CLOSED (refutation of be743e94, WEC3-m-2/m-4): a merge with no explicit restart - a continuation under a
        plain cell, or a run of continuations from the first row - is still ONE merge; Word and the export's readers
        show it as one cell beside every row it spans."""
        if cell.info["vmerge"] != "continue":
            return cell
        _, order, position, at = self.merge_index(tbl_slot)
        head = cell
        for i in range(position[cell.info["row"]] - 1, -1, -1):
            above = at.get((order[i], cell.info["col"]))
            if above is None:
                break
            head = above
            if above.info["vmerge"] != "continue":
                break
        return head

    def merge_rows(self, tbl_slot, head) -> list:
        """The rows the vertical merge starting at `head` spans: its own and each following row continuing it."""
        _, order, position, at = self.merge_index(tbl_slot)
        spanned = [head.info["row"]]
        for i in range(position[head.info["row"]] + 1, len(order)):
            below = at.get((order[i], head.info["col"]))
            if below is None or below.info["vmerge"] != "continue":
                break
            spanned.append(order[i])
        return spanned

    @staticmethod
    def answers_only(text) -> bool:
        """No printed question: empty, a drawn blank, box glyphs, or a control's placeholder or a format hint
        ('Click here to enter text.', 'dd/mm/yyyy') - what a row of answer places prints (WE3-m-2)."""
        text = re.sub("[%s]" % re.escape(GLYPH_BOX + GLYPH_CHECKED), " ", text).strip()
        return not text or is_blank_text(text)

    def shared_rows(self, tbl_slot, head, answer_rows) -> list:
        """For the vertical merge starting at `head`, a description of each DISTINCT row it spans that is a question's
        or an answer's own row, when there are two or more; else []. A row is
          - what its printed cells LEFT of the merge say (where rule (d) reads a row's question), a continued cell read
            as its merge's first cell (merge_head); two rows that read through the same cells are one row; or
          - when it prints no question outside the merge (answers_only: nothing, a drawn blank, a box, a control's
            placeholder or a format hint), an ANSWER row: a row where an engine area (a field, or a log's table_rows)
            has a place (`answer_rows`) - two entries of a log, two rows of blank answer cells, two rows of controls
            or of 'dd/mm/yyyy' date cells beside one merged cell (WEC3-m-1, WE3-m-2); or a row whose only answer
            place is the merge's own continuation, which Word does not show (WEC3-m-3).
        A tall answer cell beside ONE question (the continued rows print nothing and answer nothing, or a label merged
        the same way) is that question's own place.

        ⚠️ FAIL CLOSED (refutations of 8e00df9e, c1cae13d and be743e94): distinct LAST-label strings counted 'Right eye |
        Visual acuity' over 'Left eye | Visual acuity' as one question (M2) and option words as none (M3); skipping a
        continued label gave the cell to the question rule (d) labels it with while counting only the other (WEC2-m-2);
        log rows, which print nothing, counted as no rows (WEC3-m-1). Any printed cell left of the merge counts - an
        option word, a hint, a unit - so a single question beside a hint row is withdrawn too: declared cost (WEC2-m-4,
        m-7). Recorded, not changed: a side printed to the RIGHT of a merged cell (WEC2-m-6, pre-existing) - counting the
        right as well withdrew question cells on two dev forms."""
        spanned = self.merge_rows(tbl_slot, head)
        if len(spanned) < 2:
            return []
        rows = self.grid(tbl_slot)
        low = head.info["col"]
        seen, described = [], []
        for r in spanned:
            sources = []
            for c in sorted(rows[r], key=lambda c: c.info["col"]):
                if c.info["col"] + c.info["span"] > low:
                    continue
                source = self.merge_head(tbl_slot, c)
                text = clean_label(self.cell_text(source))
                if text and not is_blank_text(self.cell_text(source)):
                    sources.append((id(source.el), text))
            identity = frozenset(i for i, _ in sources)
            if identity:
                description = "'%s'" % " — ".join(text for _, text in sources)[:80]
            elif r in answer_rows and all(self.answers_only(self.cell_text(c)) for c in rows[r]
                                          if c.info["vmerge"] != "continue" and c.info["col"] != low):
                identity, description = ("answers", r), "table row %d (answer places, no printed question)" % (r + 1)
            else:
                continue
            if identity not in seen:
                seen.append(identity)
                described.append(description)
        return described if len(described) >= 2 else []

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
        label = re.sub(r"\s+", " ", label or "")
        qualified = qualified_signing_role(label)
        if qualified:
            return qualified
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
        self.rule_temporal_bands()
        self.rule_ruled_paragraphs()
        self.rule_parenthetical_write_cells()
        self.rule_lines_below_label(write_requests_only=True)
        self.rule_tab_columns()
        self.rule_coded_column_sequences()
        self.rule_merged_checkbox_hierarchy()
        self.rule_bracketed_checkbox_hierarchy()
        self.rule_guided_other_response_rows()
        self.rule_checkboxes()
        self.rule_adjacent_write_ins()
        self.rule_question_boxes(list_only=True)
        self.rule_text_option_choices()
        self.rule_tables()
        self.rule_question_boxes()
        self.rule_checkboxes(leftovers=True)
        self.rule_unclassified_response_lists()
        self.rule_lines_below_label()
        self.rule_temporal_format_pairs()
        self.rule_paragraph_fields()
        self.rule_inline_initial_boxes()
        self.guard_source_actions()
        self.guard_action_participants()
        self.rule_scalar_alternatives()
        self.guard_numeric_bands()
        self.guard_fixed_containers()
        self.merge_header_copies()
        self.areas.sort(key=lambda a: (self.index.by_id[a.slot.id].seq if a.slot.id in self.index.by_id else 0, a.order))
        shared = self.shared_merged_answers()
        self.qualify_sides()
        self.surface_duplicates()
        for a in list(self.areas):
            if a.complete_source and (len(a.label) > MAX_MAPPING_LABEL or len(a.context) > MAX_MAPPING_CONTEXT):
                self.notes.append("Unassigned answer box at " + a.slot.id +
                                  ". The complete question or section exceeds the mapping limit; nothing was shortened. "
                                  "Printed text: " + a.label + " Section: " + a.context)
                self.coverage_issue(a.slot, 'source_limit', self.notes[-1])
                self.areas.remove(a)
                # A withdrawn area is no longer a layout proposal either; its source stays claimed.
                self.layout_candidates[:] = [c for c in self.layout_candidates if c[2] is not a]
                continue
            a.capacity = self.capacity_for(a)
        self.withdraw_shared_merged_answers(shared)
        self.areas.sort(key=lambda a: (self.index.by_id[a.slot.id].seq if a.slot.id in self.index.by_id else 0, a.order))
        return self.areas, self.notes

    def guard_source_actions(self):
        """Human acts read from the physical source of each actual destination.

        A checkbox is one representation of an act. Its ordinary paragraph
        writing line or empty table answer cell grants no signing authority
        either. Read only that destination's existing source relation: its own
        line prefix/caption, or its row/column labels. No neighboring question,
        unrelated cell, page heading or user-supplied field label supplies one.
        """
        for area in self.areas:
            if area.protection:
                continue
            sources = []
            if area.label_slot is not None:
                sources.append(self.text(area.label_slot.el))
            if area.slot.kind == 'p' and area.target.get('type') == 'span':
                printed, pieces = self.ptext(area.slot.el)
                start = area.target['start']
                boundaries=list(re.finditer(r'[;?]|\.(?=\s+[^\W\d_])|\t{2,}| {4,}',printed))
                clause_start=max((b.end() for b in boundaries if b.end()<=start),default=0)
                clause_end=min((b.start() for b in boundaries if b.start()>=area.target['end']),
                               default=len(printed))
                before = max((end for _, end, _ in self.blank_spans(printed, pieces)
                              if end <= start), default=0)
                # A separately printed caption followed by its own blank is
                # a different question even within one Word paragraph. Keep
                # actor/predicate continuations in the original act clause:
                # whitespace alone, or a modal verb after an actor blank,
                # cannot establish an independent clinical destination.
                prefix = printed[before:start]
                caption = re.fullmatch(r'(?:[ \t]{2,}|\s*[\r\n]+\s*)([^:;?!\r\n]+):\s*', prefix) if before else None
                if (caption and not self.checkbox_source_action(caption[1], governing=True)
                        and clean_label(caption[1], limit=None) == area.label):
                    clause_start = max(clause_start, before)
                sources.append(printed[max(before,clause_start):start])
                # A named author's abbreviation can contain a period. Read a
                # complete ownership caption up to THIS blank, independently
                # of sentence splitting, only when nothing but punctuation
                # follows the caption. This cannot borrow a reservation across
                # a subsequent clinical question or a previous answer blank.
                ownership_prefix = printed[before:start]
                ownership = self.question_box_authorship(ownership_prefix)
                if ownership and not ownership_prefix[ownership.end():].strip(' \t\r\n:_.'):
                    sources.append(ownership_prefix)
                # Identity and response blanks belong to their original
                # printed clause even when the acting predicate follows them.
                # Bind every destination in that clause; never invent a signer
                # or cross a sentence, question, or printed independent gap.
                # A period before another blank (Dr. ____) is not a new clause.
                sources.append(printed[clause_start:clause_end])
            elif area.slot.kind == 'tc':
                cell = area.slot
                for source in self.question_cells(cell.parent, cell.info['row'], cell.info['col']):
                    if source is not cell:
                        sources.append(self.cell_text(source))
            # Native controls retain their own printed alias/tag source; the
            # engine label is derived from that original control, not a review.
            elif area.slot.kind in ('sdt', 'ff'):
                sources.append(area.label)
            if any(relation.get('relation') == 'nested_cell_options' for relation in area.source_questions):
                # A proved own caption can carry a printed list marker. Read
                # its action/clinical grammar after that marker, while keeping
                # the full original caption and fingerprints in the mapping.
                sources = [LIST_MARKER.sub('', str(source or '').strip()) for source in sources]
            # A printed reservation of an author's comments belongs to that
            # author regardless of the destination's representation. Reading
            # this relationship only for one-cell boxes released identical
            # manager-owned statements in ordinary table answer cells.
            if any(self.question_box_authorship(source) for source in sources):
                area.source_action = True
                area.protection = ('This answer area is reserved for another author\'s comments. '
                                   'Ordinary clinician notes do not establish that author\'s statement; '
                                   'complete it through the explicit human workflow.')
                extent = ({'start': area.target['start'], 'end': area.target['end']}
                          if area.target.get('type') == 'span' else {})
                self.coverage_issue(area.slot, 'human_authored_destination',
                                    area.protection + ' Location: ' + area.slot.id, **extent)
                continue
            roles = [self.checkbox_source_action(source, governing=True) for source in sources]
            if not any(roles):
                # A lexical kind is not a physical signing role. Only the
                # printed argument of this destination can show an initial
                # clinical reading or the receipt/status of a signed document.
                # Native signature controls retain their structural kind.
                if (not area.structural and area.kind in SIGNING_KINDS
                        and self.ordinary_source_kind(sources, area.kind)):
                    area.kind = 'text'
                    area.ordinary_reading = True
                continue
            code = 'human_signing_action' if 'human_signing_action' in roles else 'ambiguous_source_action'
            area.source_action = True
            area.protection = ('This printed document action is human-owned. Complete it through the established signing workflow.'
                               if code == 'human_signing_action' else
                               'This printed action does not establish who performs it. Keep this precise destination unchanged; '
                               'a review click does not authorize the act.')
            extent = ({'start': area.target['start'], 'end': area.target['end']}
                      if area.target.get('type') == 'span' else {})
            self.coverage_issue(area.slot, code, area.protection + ' Location: ' + area.slot.id, **extent)

    def previous_continuous_paragraph(self, host):
        """Nearest substantive source across plain spacers or adjacent one-column rows only."""
        node = host.el.getprevious()
        while node is not None and node.tag == q('w:p'):
            candidate = self.index.by_el.get(id(node))
            if candidate is None or candidate.parent is not host.parent or candidate.part != host.part:
                return None
            if self.ptext(node)[0].strip():
                return candidate
            if (not self.plain_spacing_paragraph(candidate) or not self.tab_source_visible(candidate)
                    or any(self.question_box_paragraph(node)[::2])):
                return None
            node = node.getprevious()
        # One-column, unmerged adjacent rows are a continuous printed
        # document-act block. A different column, nested table, heading,
        # intervening row or unresolved merge cannot appoint a witness.
        cell = self.host_cell(host)
        if (cell is None or host.parent is not cell or self.grid_cols(cell.parent) != 1
                or node is not None and node is not cell.el.find(q('w:tcPr'))):
            return None
        rows = self.grid(cell.parent); number = cell.info['row']
        current, previous = rows.get(number, []), rows.get(number - 1, [])
        if (number < 1 or len(current) != 1 or current[0] is not cell or len(previous) != 1
                or any(c.info['col'] != 0 or c.info['span'] != 1
                       or c.el.find('./' + q('w:tcPr') + '/' + q('w:vMerge')) is not None
                       or any(child.kind != 'p' for child in c.children)
                       for c in current + previous)):
            return None
        paragraphs = [child for child in previous[0].children if child.kind == 'p']
        for candidate in reversed(paragraphs):
            if self.ptext(candidate.el)[0].strip():
                return candidate
            if (not self.plain_spacing_paragraph(candidate) or not self.tab_source_visible(candidate)
                    or any(self.question_box_paragraph(candidate.el)[::2])):
                return None
        return None

    def guard_numeric_bands(self):
        """A separate empty band inherits its continuous source act, never a reviewed label.

        Claiming an after-label caption cannot release the writing band below
        it. A substantive clinical caption, marked spacer or container boundary
        ends that physical relationship. No caption-to-number label is guessed.
        """
        for slot in self.index.slots:
            if not self.manual_numeric_parts(slot):
                continue
            before = self.previous_continuous_paragraph(slot)
            if before is None:
                continue
            caption = self.ptext(before.el)[0].strip()
            action = self.checkbox_source_action(caption, governing=True)
            inherited = any(a.protection and a.source_action and self.host_paragraph(a.slot) is before
                            for a in self.areas)
            if not (signing_place(caption) or action or inherited or self.question_box_authorship(caption)):
                continue
            reason = ('This empty numeric band belongs to the preceding signing or document act. '
                      'It remains unchanged and is completed through the explicit human workflow.')
            self.protected_regions.add(slot.id)
            for area in self.areas:
                if self.host_paragraph(area.slot) is slot:
                    area.protection = reason; area.source_action = True
            self.coverage_issue(slot, 'human_signing_action', reason + ' Location: ' + slot.id)

    def guard_action_participants(self):
        """A witness identity belongs to its physically continuous source act.

        The complete source caption appoints a witness, and the immediately
        preceding paragraph owns a protected document act. Plain spacers and
        adjacent single-column table rows preserve that continuity. Both physical
        relations are required; a witness recorded in clinical history or a
        receipt has no such signing authority. Reviewed labels supply neither.
        """
        acts = [a for a in self.areas if a.source_action]
        for area in self.areas:
            if area.slot.kind not in ('sdt', 'ff', 'p') or area.source_action:
                continue
            if not re.fullmatch(r'(?:name of (?:the )?witness|(?:the )?witness(?: name)?)',
                                clean_label(area.label), re.I):
                continue
            host = self.host_paragraph(area.slot)
            before = self.previous_continuous_paragraph(host) if host is not None else None
            ambiguous = False
            if before is None and host is not None:
                cell = self.host_cell(host)
                # A nearby act in a complex table is evidence of an unresolved
                # witness area, not permission to guess which column owns it.
                if cell is not None:
                    ambiguous = any((prior := self.host_cell(a.slot)) is not None
                                    and prior.parent is cell.parent and prior.info['row'] == cell.info['row'] - 1
                                    for a in acts)
            # An explicit printed act is source even when it has no mapped
            # answer of its own. A plain identity caption has the same human
            # ownership as its native-control representation.
            direct_act = bool(before is not None and self.checkbox_source_action(
                self.ptext(before.el)[0], governing=True))
            if not ambiguous and (before is None or not direct_act
                                  and not any(self.host_paragraph(a.slot) is before for a in acts)):
                continue
            area.source_action = True
            area.protection = (('This witness area is beside a human document act in a table whose ownership cannot be resolved. '
                                if ambiguous else 'This witness identity belongs to the preceding human document act. ')
                               + "Ordinary notes and the finalizer cannot supply this person's identity or act; "
                               'complete it through the explicit human workflow.')
            self.coverage_issue(area.slot, 'human_document_participant',
                                area.protection + ' Location: ' + area.slot.id)

    def guard_fixed_containers(self):
        """Unqualified fixed geometry remains visible, source-held and unwritable.

        Positioned tables and header/footer parts containing fixed text boxes
        cannot safely grow with generated answers. Their placement has not been
        qualified; a character-count estimate cannot authorize overprinting.
        Plain flowing header/footer fields and ordinary inline images keep their
        existing behavior. This never moves a container or shortens an answer.
        """
        fixed_parts={part for part in self.package.content_parts()
                     if part!='word/document.xml' and
                     self.package.tree(part).find('.//'+q('w:txbxContent')) is not None}
        positioned_parts={part for part in self.package.content_parts()
                          if self.package.tree(part).find('.//'+q('w:tblpPr')) is not None}
        failed=known_layout_failure(self.package.data)
        if failed:
            self.layout_quarantine=failed
        for part in fixed_parts|positioned_parts|(
                set(self.package.content_parts()) if failed else set()):
            region=part+('#b' if part=='word/document.xml' else '#hf')
            if failed:
                reason=('This exact original has retained rendered answer truncation or overlap failures. '
                        'Its whole-document answer growth remains unsupported; no generation or charge is allowed. '
                        'Review cannot qualify it by leaving an area unchanged.')
            elif part in positioned_parts:
                reason=('This source part contains positioned tables. Growth in neighboring flowing areas can '
                        'overlap those fixed placements; answer growth in this whole part remains unqualified.')
            else:
                reason=('This header/footer contains fixed text boxes. Answer growth has not been qualified '
                        'and can overwrite nearby printed content; these source areas remain unchanged.')
            self.protected_regions.add(region)
            self.geometry_regions[region]=reason
        for area in self.areas:
            sources=[area.slot,*area.extra_slots]
            for ref in area.target.get('copies',[]):
                slot=self.index.by_id.get(ref.get('part','')+'#'+ref.get('slot',''))
                if slot is not None:sources.append(slot)
            for slot in sources:
                fixed=None;reason=''
                root=slot.part+('#b' if slot.part=='word/document.xml' else '#hf')
                if root in self.geometry_regions:
                    fixed=root;reason=self.geometry_regions[root]
                else:
                    parent=slot
                    while parent is not None:
                        if (parent.kind=='tbl' and parent.el.find('./'+q('w:tblPr')+'/'+q('w:tblpPr')) is not None):
                            fixed=parent.id
                            reason=('This positioned table has fixed placement. Answer growth has not been qualified '
                                    'and can overlap another area; these source areas remain unchanged.')
                            break
                        parent=parent.parent
                if fixed is None:continue
                if not area.protection:area.protection=reason
                self.protected_regions.add(fixed)
                self.geometry_regions[fixed]=reason
                detail=reason+' Location: '+slot.id
                self.coverage_issue(slot,'unqualified_fixed_container',detail)
                if detail not in self.notes:self.notes.append(detail)

    def shared_merged_answers(self) -> list:
        """EC3's decision, as ONE pass over every rule's areas, with NO exemption: every answer area with a place anywhere
        inside a vertically merged cell beside two or more rows (shared_rows) is to be withdrawn - mapped for none of
        them. Signing, initials and protected areas are kept (they never take an answer, and their destination roles
        depend on them; declared cost: such a role also refuses a field added there by hand) and are never
        side-qualified from one row (self.shared_kept, read by qualify_sides). Returns [(area, the merge's first cell,
        its row descriptions, kept)]; withdraw_shared_merged_answers acts on it once every labelling pass has run.

        An area's places are its anchor, its extra slots, its boxes, its header/footer COPIES, and - for a log
        (table_rows) - every cell of its rows and columns. A place inside the merge's continuation is inside the merged
        cell (WEC3-m-3); a merge with no explicit restart is one merge (merge_head, WEC3-m-2/m-4); a copy in another
        header part withdraws its area whichever part comes first (R3P-2); a log that writes into a merged cell shared
        with another answer row is withdrawn whole (WEC3-m-1; declared cost: its rows clear of the merge too). A table
        with no vertical merge at all is never read for merges (WE3-m-3).

        ⚠️ ROUND 3 (refutation of c1cae13d, WEC2-m-1/R2F-01 HIGH): the 'question printed inside the merged cell'
        exemption was a substring test that kept the first question for any guidance mentioning it ('List current
        medications and allergies.', 'Record separately.'), silently dropping the second. Removed. Declared cost: a
        question printed inside a shared merged cell ('Primary Event (diagnosis): ____', a dev form) is withdrawn too."""
        places, held = {}, {}
        for area in self.areas:
            slots = [area.slot] + list(area.extra_slots)
            for ref in list(area.target.get("boxes", [])) + list(area.target.get("copies", [])):
                slot = self.index.by_id.get("%s#%s" % (ref.get("part"), ref.get("slot")))
                if slot is not None:
                    slots.append(slot)
            if area.target.get("type") == "table_rows" and area.slot.kind == "tc":
                columns = set(area.target.get("columns", []))
                for r in area.target.get("rows", []):
                    slots.extend(c for c in self.grid(area.slot.parent).get(r, []) if c.info["col"] in columns)
            places[id(area)] = slots
            for slot in slots:
                node = slot
                while node is not None:
                    if node.kind == "tc":
                        held.setdefault(id(node.parent), {}).setdefault(node.info["row"], set()).add(node.id)
                    node = node.parent
        verdicts, answer_rows = {}, {}

        def shared_cell(slots):
            for slot in slots:
                node = slot
                while node is not None:
                    if node.kind == "tc" and self.merge_index(node.parent)[0]:
                        head = self.merge_head(node.parent, node)
                        if head.id not in verdicts:
                            verdicts[head.id] = []
                            if len(self.merge_rows(node.parent, head)) >= 2:
                                if id(node.parent) not in answer_rows:
                                    answer_rows[id(node.parent)] = set(held.get(id(node.parent), {}))
                                verdicts[head.id] = self.shared_rows(node.parent, head, answer_rows[id(node.parent)])
                        if verdicts[head.id]:
                            return head
                    node = node.parent
            return None
        decided = []
        for area in self.areas:
            cell = shared_cell(places[id(area)])
            if cell is None:
                continue
            kept = bool(area.protection or area.kind in SIGNING_KINDS)
            if kept:
                self.shared_kept.add(id(area))
            decided.append((area, cell, verdicts[cell.id], kept))
        return decided

    def withdraw_shared_merged_answers(self, decided):
        """EC3's withdrawal, run LAST in detect(): the areas shared_merged_answers decided to withdraw leave the mapping
        (each still owned its cell and counted as a duplicate while every labelling pass ran), and the inspection says
        so once per cell. A withdrawn area keeps its extent in the role reading (Detector.withdrawn_areas,
        _role_reading), so no neighbouring signing or protected role grows over it.

        ⚠️ WEC3P-1 / WE3-m-1 (refutation of d9afcf2f, HIGH): withdrawing BEFORE qualify_sides freed the cell, and its
        printed 'Left knee: ____' became the side of the right knee's answer beside it ('Left knee — Effusion'); and a
        surviving duplicate lost its occurrence. A withdrawal changes no other area's label, context, kind or locator."""
        present = {id(area) for area in self.areas}
        decided = [entry for entry in decided if id(entry[0]) in present]  # an area a later check removed has its note
        gone = {id(area) for area, _, _, kept in decided if not kept}
        self.withdrawn_areas.extend(area for area, _, _, kept in decided if not kept)
        self.areas[:] = [area for area in self.areas if id(area) not in gone]
        self.layout_candidates[:] = [c for c in self.layout_candidates if id(c[2]) not in gone]
        noted = []
        for _, cell, shared, _ in decided:
            if cell.id in noted:
                continue
            noted.append(cell.id)
            rows = "; ".join(shared[:6])
            here = [(area, kept) for area, c, _, kept in decided if c.id == cell.id]
            withdrawn = [area for area, kept in here if not kept]
            if withdrawn:
                note = ("The answer cell at %s is one vertically merged cell beside %d rows (%s), so it was NOT mapped: "
                        "the merge hides which answer belongs to which row. Unmerge the answer cell, or add a field for "
                        "it by hand on this page." % (cell.id, len(shared), rows))
                logs = ["%d-%d" % (min(a.target["rows"]) + 1, max(a.target["rows"]) + 1) for a in withdrawn
                        if a.target.get("type") == "table_rows" and a.target.get("rows")]
                if logs:
                    note += " The log rows that write into it (table rows %s) were not mapped either." % ", ".join(logs)
                if any(kept for _, kept in here):
                    note += " Its signing or protected area is kept as printed and completed by hand."
            else:
                note = ("The cell at %s is one vertically merged cell beside %d rows (%s). Its signing or protected area "
                        "is kept as printed and completed by hand; no answer is mapped there." % (cell.id, len(shared), rows))
            self.notes.append(note)
            if withdrawn:
                self.coverage_issue(cell, 'shared_merged_answer', note)

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
            if side_phrase(area.label) or id(area) in self.shared_kept:
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

    def adjacent_blank_plan(self, slot):
        """One physically separate answer span beside qualified box controls.

        Two blanks, hidden/linked ink, drawings and ambiguous option text stay
        with the existing coverage hold. A printed condition never selects its
        controlling box; a separate labelled unit never inherits that box.
        """
        text, pieces = self.ptext(slot.el)
        positions = [i for i, ch in enumerate(text) if ch in (BOX, CHECKED)]
        if not positions:
            return None
        # A checkbox can perform a first-person document act. Its physical
        # option text is read before the supported write-in shape: extra/no
        # blanks do not grant authority to acknowledge, approve or attest.
        options = [text[pos + 1:(positions[n + 1] if n + 1 < len(positions) else len(text))]
                   for n, pos in enumerate(positions)]
        roles = [self.checkbox_source_action(option) for option in options]
        roles.extend(branch['protection'] for unit in self.box_units(slot)
                     for branch in [self.option_branch_source(unit)] if branch and branch['protection'])
        head = text[:positions[0]].strip()
        if head:
            roles.append(self.checkbox_source_action(head, governing=True))
        elif not any(re.search(r'\?', option) or self.first_person_source(option)
                     and not self.checkbox_source_action(option) for option in options):
            # Only a physically adjacent statement governs a leading response.
            # Never cross a table/cell, another answer, an independent question,
            # or a substantive first-person clinical statement printed by a box.
            previous = slot.el.getprevious()
            before = self.index.by_el.get(id(previous)) if previous is not None else None
            if (before is not None and before.kind == 'p' and before.parent is slot.parent
                    and before.part == slot.part):
                prior, prior_pieces = self.ptext(before.el)
                if (prior.strip() and BOX not in prior and CHECKED not in prior
                        and not self.blank_spans(prior, prior_pieces)
                        and not any(area.slot is before or before in area.extra_slots for area in self.areas)
                        and not any(n.tag in (q('w:drawing'), q('w:pict'), q('w:object'), TXBX)
                                    for n in before.el.iter())):
                    roles.append(self.checkbox_source_action(LIST_MARKER.sub('', prior.strip()), governing=True))
        if any(roles):
            definite = 'human_signing_action' in roles
            code = 'human_signing_action' if definite else 'ambiguous_source_action'
            reason = ('This printed document action is human-owned. Complete it through the established signing workflow.'
                      if definite else 'This printed action does not establish who performs it. '
                      'Keep it unchanged and review its precise source role; a review click does not authorize that act.')
            self.protected_regions.add(slot.id);self.box_action_reasons[slot.id] = reason
            self.coverage_issue(slot, code, reason + ' Location: ' + slot.id)
            return None
        spans = self.blank_spans(text, pieces)
        if not spans and slot.part == 'word/document.xml' and self.tab_source_visible(slot):
            # A terminal colon appoints an answer after this option's complete
            # printed label. Keep this finite Other frame separate from a
            # sentence, another question or an arbitrary qualifier/predicate.
            tail = text[positions[-1] + 1:]
            terminal = re.fullmatch(r"\s*(Other(?:\s+[\w'-]+|,\s*(?:please\s+)?specify|"
                                   r'\s+\((?:please\s+)?specify\))?)\s*:\s*', tail, re.I)
            if (terminal and len(tail.strip()) <= MAX_MAPPING_LABEL
                    and not hyperlink_write(pieces, len(text), len(text))
                    and not any(n.tag in (q('w:drawing'), q('w:pict'), q('w:object'), TXBX)
                                for n in slot.el.iter())):
                return {'start': len(text), 'end': len(text), 'shape': 'after_label',
                        'label': tail.strip(), 'option': option_text(terminal[1]),
                        'condition': 'printed_option', 'box': len(positions) - 1, 'terminal_label': True}
        if (slot.part != 'word/document.xml' or len(spans) != 1 or not self.tab_source_visible(slot)
                or any(n.tag in (q('w:drawing'), q('w:pict'), q('w:object'), TXBX) for n in slot.el.iter())):
            return None
        if self.question_box_signing(head):
            self.protected_regions.add(slot.id)
            self.coverage_issue(slot, 'human_signing_action',
                'The printed signing or attestation action remains human-owned at ' + slot.id)
            return None
        start, end, shape = spans[0]
        if (shape not in ('blank', 'utab') or start <= positions[-1]
                or hyperlink_write(pieces, start, end)):
            return None
        if shape == 'blank':
            # A recognised ellipsis/underscore rule can end with one or two
            # contiguous dots that are too short to be a second blank. They
            # belong to this drawn rule, not to the option or a neighbour.
            while end < len(text) and text[end] in '_.…': end += 1
            while start > positions[-1] + 1 and text[start - 1] in '_.…': start -= 1
            if hyperlink_write(pieces, start, end): return None
        prefix, suffix = text[positions[-1] + 1:start], text[end:]
        # Explicit Yes/No condition printed after its own labelled option.
        condition = re.fullmatch(r'\s*(Yes|No)\s*(?:[→⇒]\s*)?(if\s+(yes|no)\s*,\s*\S.+[?:])\s*', prefix, re.I)
        if condition and not suffix.strip() and condition[1].casefold() == condition[3].casefold():
            return {'start': start, 'end': end, 'shape': shape, 'label': condition[2].strip(),
                    'option': condition[1], 'condition': 'printed_option', 'box': len(positions) - 1}
        # A wide printed gap separates a different labelled/unit answer from
        # the last option (Gender ... Female<TAB><TAB>Age ____ years).
        gap = re.search(r'\t{2,}| {4,}', prefix)
        if gap and suffix.strip() and self.ANSWER_UNIT.fullmatch(suffix.strip()):
            option, label = prefix[:gap.start()].strip(), clean_label(prefix[gap.end():], limit=None)
            if option and label and not re.search(r'[:?!\x00' + BOX + CHECKED + r']', label):
                return {'start': start, 'end': end, 'shape': shape, 'label': label,
                        'option': option, 'condition': 'independent_unit', 'box': len(positions) - 1}
        # One box and one trailing write-in are distinct destinations. Do not
        # generalise multiple-box descriptions or a sentence after the blank.
        if len(positions) == 1 and not text[:positions[0]].strip() and not suffix.strip():
            label = clean_label(prefix, limit=None)
            if label and not re.search(r'\bif\b|[?!\x00]', label, re.I):
                return {'start': start, 'end': end, 'shape': shape, 'label': label,
                        'option': label, 'condition': 'printed_option', 'box': 0}
        return None

    @staticmethod
    def first_person_source(text):
        source = _INVISIBLE.sub('', unicodedata.normalize('NFKC', str(text or ''))).strip()
        contractions = {'m':'am','re':'are','ve':'have','d':'would','ll':'will'}
        source = re.sub(r"\b(I|we)[’'](m|re|ve|d|ll)\b",
                        lambda m:m[1]+' '+contractions[m[2].casefold()],source,flags=re.I)
        # An explicit subject remains explicit after a bounded introductory
        # capacity phrase. The printed capacity supplies no signer identity.
        introductory = re.match(r'^(?:as|acting\s+as|in\s+(?:my|our|the)\s+(?:capacity|role)\s+as)\s+'
                                r'[^,;:?!\r\n]{1,120}?(?:,\s*|\s+)(?=(?:I|we)(?=\W|$))',source,re.I)
        if introductory:source=source[introductory.end():]
        person = re.match(r'^(?:I|we)(?=\W|$)',source,re.I)
        if not person:return ''
        predicate=source[person.end():].strip()
        # A printed apposition qualifies the speaker; it never proves their
        # identity or signing authority. Keep malformed qualifiers as unknown
        # predicates, so a consent/signing argument still requires exact review.
        qualifier = re.match(r'^(?:,\s*[^,;:?!\r\n]{1,120}\s*,|'
                             r'\([^()\r\n]{1,120}\)|\[[^\[\]\r\n]{1,120}\]|'
                             r'([—–-])\s*[^—–\r\n]{1,120}?\s*\1)\s*',predicate)
        if qualifier:predicate=predicate[qualifier.end():]
        # A capacity phrase without a comma is grammatically ambiguous. Only
        # isolate a finite permission predicate with its explicit determined
        # object; a noun such as "permit holder" is not that predicate. Other
        # unknown predicates retain their original arguments for role review.
        capacity = re.match(r'^as\s+[^,;:?!\r\n]{1,120}?\s+'
                            r'(?=(?:allow|permit)(?:s|ted|ting|ed|ing)?\s+'
                            r'(?:this|that|these|the|a|an|my|our|their|his|her)\b)',predicate,re.I)
        if capacity:predicate=predicate[capacity.end():]
        aspect=re.match(r'^(?:(?:hereby|am|are|was|were|have|had|been|being|personally|do|did|not|yet|cannot|will|would)\s+)*',
                        predicate,re.I)
        return predicate[aspect.end():]

    @staticmethod
    def complete_signing_action(text):
        """A complete actor/auxiliary/signing predicate, without an identity guess.

        A temporal caption still qualifies that act. Clinical signs, initial
        observations and received signed documents have no such predicate.
        Dotted names and negation do not turn another person's act into data.
        """
        return re.fullmatch(r'\s*[^:;?!\r\n]+?\s+'
            r'(?:' + SOURCE_ACTION_AUXILIARY + r'\s+)+'
            r'(?:(?:required\s+)?to\s+)?(?:sign|initial)'
            r'(?:\s+(?!of\b)[^:;?!\r\n]+)?\s*[:.]?', text, re.I)

    @classmethod
    def checkbox_source_action(cls,text,*,governing=False):
        """Printed performative ownership, not a signer-name guess.

        Ordinary clinical states and recorded-status labels are not this frame.
        First-person, documentary nominal, imperative, third-person and explicit
        checkbox-action conditions share one reading. A third-person subject
        supplies no signer identity. Documentary objects distinguish those
        requests from ordinary clinical questions and nonhuman observations.
        """
        source = _INVISIBLE.sub('', unicodedata.normalize('NFKC', str(text or ''))).strip()
        if cls.complete_signing_action(source) or cls.question_box_authorship(source):
            return 'human_signing_action'
        # Quoting or qualifying a printed human act supplies no authority to
        # perform it. Read only a complete paired quotation / explicit clause;
        # ordinary quoted clinical statements retain their own arguments.
        quote_pairs={'"':'"',"'":"'",'“':'”','‘':'’'}
        if source[:1] in quote_pairs:
            closer=source.rfind(quote_pairs[source[0]],1)
            if closer>0 and re.fullmatch(r'[\s:._…]*',source[closer+1:]):
                return cls.checkbox_source_action(source[1:closer],governing=governing)
        conditional=re.match(r'^if\s+[^,;:?!\r\n]{1,200},\s*(.+)$',source,re.I)
        if conditional:return cls.checkbox_source_action(conditional[1],governing=governing)
        condition = re.match(r'^by\s+(?:checking|ticking|selecting|signing|initiall?ing)\b'
                             r'[^,;:\r\n]{0,200}?(?:[,;:]\s*|\s+(?=(?:I|we|you|he|she|they)\b))(.+)$',source,re.I)
        if condition:
            return cls.checkbox_source_action(condition[1],governing=governing)
        predicate = cls.first_person_source(source)
        first_person = bool(predicate)
        # A documentary action noun is a governing label, not a recorded-status
        # label. This reads the action, irrespective of a named signer/role.
        if governing:
            # A question cell is a caption without requiring a literal colon.
            # Read the complete noun phrase: a status/date/receipt suffix is
            # not an action caption, and no signer name is inferred.
            heading = re.fullmatch(r'(?:[^:?!\r\n]+?\s+)?'
                                  r'(?P<action>approval|verification|confirmation|acknowledg(?:e)?ment|acceptance|review|'
                                  r'certification|attestation|declaration|authori[sz]ation|consent|sign[ -]?off)s?'
                                  r'(?:\s+(?:of|for|to|by|from)\s+[^:?!]+)?\s*[:.]?',source,re.I)
            if heading:
                explicit = (re.search(r'\b(?:record|document|form|report|information)\b',source,re.I)
                            or re.match(r'certification|attestation|declaration|authori[sz]ation|consent|sign',
                                        heading['action'],re.I))
                # A complete nominal "review/confirmation/... of <clinical
                # object>" names an observation category. It has neither an
                # appointed author nor a document/formal act argument. Keep
                # bare/assigned reviews ambiguous and formal objects held;
                # a clinician's reviewed label cannot establish this reading.
                descriptive = re.fullmatch(re.escape(heading['action']) + r's?\s+of\s+[^:?!]+\s*[:.]?', source, re.I)
                formal_object = re.search(r'\b(?:consent|permission|authori[sz]ation|attestation|certification|declaration)s?\b', source, re.I)
                # The nominal act's complete agentive complement appoints its
                # author, regardless of that person's name or job title. It is
                # not an ordinary observation category even for clinical objects.
                if descriptive and re.search(r'\s+by\s+\S[^:?!]*\s*[:.]?$', source, re.I):
                    return 'human_signing_action'
                if descriptive and not explicit and not formal_object:
                    return ''
                return 'human_signing_action' if explicit else 'ambiguous_source_action'
            if ':' in source:
                caption, statement = source.split(':',1)
                tail = cls.checkbox_source_action(statement)
                if tail:
                    return tail
                # A printed declaration/statement of witnessing a signing act
                # governs its response. It supplies no identity or authority.
                if (re.search(r'\b(?:statement|declaration|attestation)\s*$',caption,re.I)
                        and cls.first_person_source(statement)
                        and re.search(r'\bsign(?:ed|ing)?\b',statement,re.I)):
                    return 'human_signing_action'
        document_pattern = (r'\b(?:this|the|these|above|foregoing)\s+'
                            r'(?:(?:clinical|medical|written|recorded|provided|above)\s+)*'
                            r'(?:records?|documents?|forms?|reports?|information|statements?|details?)(?=\W|_|$)')
        # A finite auxiliary belongs to the subject/predicate relation, not
        # the actor's name. Read its complement with the same action reader;
        # neither tense, negation nor an unfamiliar actor creates authority.
        # This also protects an actor blank before the predicate. Clinical
        # complements keep their ordinary meaning ("will review the dose").
        auxiliary = SOURCE_ACTION_AUXILIARY
        finite = re.match(r'^(?:(?P<subject>[^.;:?!\r\n]+?)\s+)?'
                          r'(?P<aspect>(?:'+auxiliary+r'\s+)+)(?P<complement>\S.+)$', source, re.I)
        if finite and not first_person:
            complement = finite['complement']
            action = cls.checkbox_source_action(complement, governing=governing)
            if action:
                return 'ambiguous_source_action'
        # Permission and witnessing are acts even when their object is a
        # procedure/person rather than the document. Their subject/predicate
        # relationship supplies the role; merely mentioning consent, signing
        # or a past document receipt does not.
        permission = (r'(?:permit(?:s|ted|ting)?|allow(?:s|ed|ing)?)(?=\W|_|$)|'
                      r'(?:grant(?:s|ed|ing)?|giv(?:e|es|en|ing)|gave)\s+'
                      r'(?:(?:my|our|their|the|explicit|informed)\s+)*(?:permission|consent|authori[sz]ation)\b')
        witness = (r'\b(?:observ(?:e|es|ed|ing)|see|sees|seen|saw|witness(?:es|ed|ing)?)\b'
                   r'[^.;:?!\r\n]*\b(?:signing|signed|signatures?|sign(?=\s*(?:[.:;_]|$)))\b')
        witnessed_presence = (r'\b(?:sign(?:ed|ing)|signatures?)\b[^.;:?!\r\n]*'
                              r'\bin\s+(?:my|our)\s+presence\b')
        # A signing event does not require a particular document noun: its
        # verb may take a pronoun, a printed place, or an unfamiliar object.
        # "Signs" and "sign of ..." are clinical noun readings. An otherwise
        # ambiguous singular sign remains a precise source-role decision.
        signing_event = (r'\b(?:signed|signing|signatures?)\b|'
                         r'\bsign(?=\W|_|$)(?!\s+of\b)')
        if (governing and re.search(r'\b(?:observation|witnessing)\s+of\b',source,re.I)
                and re.search(signing_event,source,re.I)):
            return 'ambiguous_source_action'
        # Witnessing is a subject + perception predicate + signing event. Its
        # subject need not name a known role, and cannot authorize generation
        # to perform that person's observation. Clinical observations without
        # a signing event and recorded noun/status labels remain independent.
        observed = re.match(r'^([^.;:?!\r\n]+?)\s+'
                            r'(?:observ(?:es|ed)|sees|saw|witness(?:es|ed)|watch(?:es|ed))\b'
                            r'(?P<argument>[^.;:?!\r\n]+)',source,re.I)
        if (observed and re.search(signing_event,observed['argument'],re.I)):
            return 'human_signing_action' if first_person else 'ambiguous_source_action'
        if (first_person and (re.match(permission,predicate,re.I) or re.search(witness,predicate,re.I))
                or re.search(witnessed_presence,source,re.I)):
            return 'human_signing_action'
        if first_person:
            # The argument supplies a legal/signing role even when its verb
            # is unfamiliar, negated, withdrawing consent, or describes a
            # witness's presence. Do not grow a verb/signer-name whitelist.
            # Clinical signs/observations have no such signing-event argument.
            signing_argument = re.search(signing_event,predicate,re.I)
            formal_argument = re.search(r'\b(?:consent|permission|authori[sz]ation|attestation|certification|declaration)s?\b',
                                        predicate,re.I)
            if signing_argument or formal_argument:
                return 'ambiguous_source_action'
        if not predicate:
            # A documentary nominal printed as an option is still the act,
            # even without a named signer or a colon-bearing parent label.
            nominal = re.match(r'^(approval|verification|confirmation|acknowledg(?:e)?ment|acceptance|review|'
                               r'certification|attestation|declaration|authori[sz]ation|consent)s?'
                               r'\s+(?:that|of|for|to)\b',source,re.I)
            if (nominal and (re.search(document_pattern,source,re.I)
                             or re.match(r'certification|attestation|declaration|authori[sz]ation|consent',nominal[1],re.I))):
                return 'human_signing_action'
            action = (r'certif(?:y|ies|ied|ying)|attest(?:s|ed|ing)?|declar(?:e|es|ed|ing)|'
                      r'affirm(?:s|ed|ing)?|consent(?:s|ed|ing)?|authori[sz](?:e|es|ed|ing)|'
                      r'confirm(?:s|ed|ing)?|verif(?:y|ies|ied|ying)|acknowledg(?:e|es|ed|ing)|'
                      r'agree(?:s|d|ing)?|accept(?:s|ed|ing)?|approv(?:e|es|ed|ing)|review(?:s|ed|ing)?|read(?:s)?|'
                      r'permit(?:s|ted|ting)?|allow(?:s|ed|ing)?|grant(?:s|ed|ing)?|giv(?:e|es|en|ing)|gave')
            base_action = (r'certify|attest|declare|affirm|consent|authori[sz]e|confirm|verify|acknowledge|'
                           r'agree|accept|approve|review|read|permit|allow|grant|give')
            imperative = re.match(r'^(?:please\s+)?('+base_action+r')(?=\W|_|$)',source,re.I)
            if imperative and re.match(r'\s+(?:is|are|was|were|has|have|had)\b',source[imperative.end():],re.I):
                imperative = None  # "Consent was obtained" reports a noun's status; it is not an order.
            third_person = re.match(r'^([^.;:?!\r\n]+?)\s+('+action+r')(?=\W|_|$)',source,re.I)
            if third_person:
                subject,verb = third_person[1].strip(),third_person[2]
                # A terminal passive restriction counts printed answers, not
                # a human actor granting permission. Reuse the selection
                # grammar and require that its counted noun is the subject's
                # complete tail; an actor + permission complement stays held.
                counted = ONE_ANSWER.search(subject) or COUNTED_ANSWERS.search(subject)
                if (governing and counted and not subject[counted.end():].strip()
                        and limit_language(subject, local=True) and verb.lower().endswith('ed')
                        and re.match(permission, verb, re.I)
                        and not source[third_person.end():].strip(' \t\r\n:.;')):
                    third_person = None
                if (third_person and re.fullmatch(base_action,verb,re.I)
                        and not re.fullmatch(r'you|they|he|she|it',subject,re.I)
                        and not re.search(r's\s*$',subject,re.I)):
                    third_person = None  # "Signed consent" is a noun phrase, not subject + finite verb.
            frame = imperative or third_person
            if not frame:
                return ''
            predicate = source[frame.start(1 if imperative else 2):]
            if re.match(permission,predicate,re.I):
                return 'human_signing_action' if imperative else 'ambiguous_source_action'
            # A request about a clinical observation is not a documentary
            # attestation merely because it says confirm/verify/review.
            if not re.search(document_pattern,predicate,re.I):
                formal = re.match(r'(?:certif(?:y|ies|ied|ying)|attest(?:s|ed|ing)?|declar(?:e|es|ed|ing)|'
                                  r'affirm(?:s|ed|ing)?|consent(?:s|ed|ing)?|authori[sz](?:e|es|ed|ing))'
                                  r'(?=\W|_|$)',predicate,re.I)
                # Authorizing treatment or giving consent performs an act
                # without saying "document". An unqualified third-person
                # subject supplies no identity/authority to perform it either.
                if formal:
                    return 'human_signing_action' if imperative else 'ambiguous_source_action'
                return ''
        if re.match(r'(?:so|this|that)(?=\W|_|$)',predicate,re.I):
            return 'ambiguous_source_action'
        document = re.search(document_pattern,predicate,re.I)
        if re.match(r'(?:certif(?:y|ies|ied|ying)|attest(?:s|ed|ing)?|declar(?:e|es|ed|ing)|affirm(?:s|ed|ing)?|'
                    r'consent(?:s|ed|ing)?|authori[sz](?:e|es|ed|ing)|(?:give|given|gave)\s+(?:(?:my|our)\s+)?consent)'
                    r'(?=\W|_|$)', predicate, re.I):
            return 'human_signing_action'
        if not re.match(r'(?:confirm(?:s|ed|ing)?|verif(?:y|ies|ied|ying)|acknowledg(?:e|es|ed|ing)|agree(?:s|d|ing)?|'
                        r'accept(?:s|ed|ing)?|approv(?:e|es|ed|ing)|review(?:s|ed|ing)?|read(?:s)?)(?=\W|_|$)',
                        predicate, re.I):
            # An unfamiliar predicate about the document cannot silently become
            # authority to make the printed first-person assertion either.
            return 'ambiguous_source_action' if document else ''
        return 'human_signing_action' if document else 'ambiguous_source_action' if first_person else ''

    @staticmethod
    def ordinary_source_kind(sources, kind):
        """An incidental signing word with an ordinary physical argument.

        This does not release a signature/initials instruction or an attestation.
        The caller has already excluded action captions and native controls.
        It uses the original caption/span prefix, never a reviewed field label.
        """
        printed = [_plain(source) for source in sources if _plain(source)]
        if not printed or any(signing_place(source) for source in printed):
            return False
        if kind == 'initials':
            return any(ADJECTIVE_INITIAL.search(source) for source in printed)
        # A signed noun being received/recorded is a document's history, not
        # the act of signing it. Terminal explicit status asks for that history
        # too; a bare "consent form signed" remains a review decision.
        receipt = (r'\bsigned\s+[^:?!\r\n]+?\s+'
                   r'(?:(?:was|were|is|are|has\s+been|had\s+been)\s+)?'
                   r'(?:received|recorded|filed|stored)\b')
        received_signed_object = (r'\b(?:received|recorded|filed|stored)\s+'
                                  r'(?:the|a|an|this|that|these|those)\s+signed\s+[^:?!\r\n]+')
        # A terminal receipt object records delivery of a signed document;
        # the action-caption guard already excluded any act of certification.
        nominal_receipt = r'\bsigned\s+[^:?!\r\n]+?\s+receipt\s*[:.]?$'
        return any(re.search(receipt,source,re.I) or re.search(received_signed_object,source,re.I) or
                   re.search(nominal_receipt,source,re.I) or
                   re.search(r'\b(?:recorded|documented)\b[^:?!]*\bsigned\b[^:?!]*\bstatus$',source,re.I)
                   for source in printed)

    def option_branch_source(self, unit):
        """A repeated Yes/No condition or exact numbered skip separates guidance.

        The complete source remains part of the mapping. Only this physically
        adjacent, matching frame has a shorter option value; there is no
        global alias for Yes or any arbitrary option prefix.
        """
        frame = re.fullmatch(r'\s*(Yes|No)\s*→\s*(if\s+(yes|no),)\s*(.+?)\s*', unit[1], re.I | re.S)
        skip = re.fullmatch(r'\s*(Yes|No|Refused)\s+(\[GO\s+TO\s+[1-9][0-9]{0,3}\.?\])\s*',
                            unit[1], re.I)
        if not frame and not skip:
            return None
        ref = unit[0]
        slot = self.index.by_id.get(ref['part'] + '#' + ref['slot'])
        paragraph = self.host_paragraph(slot) if slot is not None else None
        if paragraph is None:
            return None
        caption = frame[1] if frame else skip[1]
        condition = frame[2] if frame else skip[2]
        instruction = frame[4] if frame else skip[2]
        acts = [self.checkbox_source_action(clause, governing=True)
                for clause in [instruction, *re.split(r'(?<=[.;!?])\s*|[\r\n]+', instruction)]]
        protection = next((act for act in acts if act), '')
        text, pieces = self.ptext(paragraph.el)
        spans = self.blank_spans(text, pieces)
        # A single option's literal numbered skip is source guidance. Keep its
        # exact text and control in the existing branch relation; only the local
        # Yes/No/Refused answer value is shorter. Other bracketed words, multiple
        # boxes, write-ins and arbitrary prefixes cannot establish this frame.
        source_blank_safe = (not spans if frame else
                             len(self.box_units(paragraph)) == 1
                             and all(kind == 'bracket' and text[start:end] == instruction
                                     for start, end, kind in spans))
        qualified = ((frame is None or frame[1].casefold() == frame[3].casefold()) and '→' not in instruction
                     and not re.search(r'[?\r\n\x00]', instruction) and ':' not in instruction.rstrip(':')
                     and source_blank_safe
                     and self.tab_source_visible(paragraph)
                     and not any(n.tag in (q('w:drawing'), q('w:pict'), q('w:object'), TXBX)
                                 for n in paragraph.el.iter()) and not protection)
        return {'caption': caption, 'condition': condition, 'instruction': instruction,
                'printed': option_text(unit[1]), 'control': dict(ref), 'qualified': qualified,
                'protection': protection,
                'source': {'part': paragraph.part, 'slot': paragraph.path,
                           'fingerprint': fingerprint(paragraph.el)}, 'source_text': text}

    def adjacent_option_text(self, unit):
        """Separate only a proven explicit trailing condition from its option."""
        branch = self.option_branch_source(unit)
        if branch and branch['qualified']:
            return branch['caption']
        ref = unit[0]
        slot = self.index.by_id.get(ref['part'] + '#' + ref['slot'])
        paragraph = self.host_paragraph(slot) if slot is not None else None
        if paragraph is None:
            return unit[1]
        plan = self.adjacent_blank_plan(paragraph)
        refs = [u[0] for u in self.box_units(paragraph)]
        if (plan and plan['condition'] == 'printed_option' and refs[plan['box']] == ref
                and (len(refs) == 1 or re.match(r'if\s+(?:yes|no)\s*,', plan['label'], re.I))):
            return plan['option']
        return unit[1]

    def rule_adjacent_write_ins(self):
        """An existing qualified checkbox owner permits a separate exact span.

        The complete owner and condition travel with the mapping and are read
        again by fill. Coverage holds are removed only by a genuine writer at
        this exact span; no ambiguous option/cardinality group is promoted.
        """
        for slot in [s for s in self.index.slots if s.kind == 'p']:
            plan = self.adjacent_blank_plan(slot)
            if slot.id in self.protected_regions:
                for area in self.areas:
                    if any(ref.get('part') == slot.part and ref.get('slot', '').startswith(slot.path + '/')
                           for ref in area.target.get('boxes', [])):
                        area.protection = self.box_action_reasons.get(slot.id,
                            'This printed signing or attestation action is human-owned. Complete it through the established signing workflow.')
                continue
            if not plan:
                continue
            target = {'type': 'span', 'start': plan['start'], 'end': plan['end'], 'shape': plan['shape']}
            if any(a.slot is slot and a.target == target for a in self.areas):
                continue
            control = self.box_units(slot)[plan['box']][0]
            owners = [a for a in self.areas if a.target.get('type') == 'checkboxes'
                      and control in a.target.get('boxes', [])]
            if len(owners) != 1:
                continue
            owner = owners[0]; position = owner.target['boxes'].index(control)
            if (owner.protection or owner.kind not in ('choice', 'multi_choice', 'checkbox')
                    or owner.label in ('Choose', 'Checkbox', '') or not owner.options
                    or position >= len(owner.options)
                    or option_text(owner.options[position]).casefold() != option_text(plan['option']).casefold()):
                continue
            label = plan['label']
            context = ' > '.join(x for x in (owner.context, owner.label,
                ('Only when the printed option ' + owner.options[position] + ' is selected')
                    if plan['condition'] == 'printed_option' else 'Separate labelled answer: ' + label) if x)
            if plan.get('terminal_label'):
                printed = [label, owner.label, *owner.context.split(' > ')]
                human_source = any(self.checkbox_source_action(LIST_MARKER.sub('', value.strip()), governing=True)
                                   or signing_place(value) for value in printed)
            else:
                human_source = (self.question_box_signing(label) or self.question_box_signing(context)
                                or self.question_box_signing(owner.label + ':'))
            if len(label) > MAX_MAPPING_LABEL or len(context) > MAX_MAPPING_CONTEXT or human_source:
                continue
            source = {'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el)}
            owner_ref = {'part': owner.slot.part, 'slot': owner.slot.path, 'fingerprint': fingerprint(owner.slot.el)}
            relation = {'relation': 'adjacent_checkbox_answer', 'question': label, 'context': context,
                        'source': source, 'owner': owner_ref, 'owner_label': owner.label,
                        'owner_context': owner.context, 'owner_kind': owner.kind,
                        'owner_options': list(owner.options), 'owner_target': dict(owner.target),
                        'condition': plan['condition'], 'control': dict(control), 'option_index': position,
                        'printed_option': owner.options[position], 'source_text': self.ptext(slot.el)[0]}
            self.add(Area(self.kind_for(label), label, slot, target, context=context,
                          complete_source=True, source_questions=[relation]))

    def tab_column_properties(self, slot, *, scope_only=False, checkbox_indent=False):
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
                defaults = self.default_source_styles(kind)
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
        if checkbox_indent:
            # A box at the exact start has one first-line coordinate. No tab
            # precedes it, so stored stops cannot move it. Competing firstLine
            # and hanging remain unresolved.
            if self.ptext(slot.el)[0][:1] not in (BOX, CHECKED) or (
                    indent.get('hanging', 0) and indent.get('firstLine', 0)):
                return None
            return indent.get('left', 0) + indent.get('firstLine', 0) - indent.get('hanging', 0)
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
                defaults = self.default_source_styles(kind)
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
                self.coverage_issue(cell, 'tab_column_withdrawal', self.notes[-1])
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
                # A separately proved request before the header owns only its
                # caption/plain blanks. The refused coded controls still need
                # exclusions of their own; excluding the whole cell would also
                # exclude that independent supported answer.
                requests = [area for area in self.areas if self.host_cell(area.slot) is cell and any(
                    ref.get('relation') == 'parenthetical_write_request' for ref in area.source_questions)]
                header = next((p for p in cell.children if p.kind == 'p' and self.literal_column_header(p)), None)
                owned = {id(p.el) for area in requests for p in [area.slot, *area.extra_slots, area.label_slot] if p is not None}
                prefix = [p for p in cell.children if header is not None and p.seq < header.seq]
                separate = (reason == 'A printed title requests its own answer.' and requests and header is not None
                            and all(p.kind == 'p' and (id(p.el) in owned or self.plain_spacing_paragraph(p, unused_tab_stops=True))
                                    for p in prefix))
                if separate:
                    earlier = [issue for issue in self.coverage_issues if issue['part'] == cell.part
                               and issue['slot'] == cell.path and issue['code'] == 'tab_column_withdrawal']
                    self.coverage_issues[:] = [issue for issue in self.coverage_issues if issue not in earlier]
                    for prior in earlier:
                        for row in rows:
                            self.coverage_issue(row, prior['code'], prior['detail'] +
                                ' The independent prefix request is mapped separately; this exact coded row remains unsupported.')
                for unresolved in rows if separate else [cell]:
                    self.coverage_issue(unresolved, 'unmapped_answer', self.notes[-1])
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

    def rule_merged_checkbox_hierarchy(self):
        """One column question and a two-row merged item own parent alternatives.

        A colon parent's uniformly indented children are separate from the
        unindented peer in the next row of that same printed item. Unknown
        merge, header, indentation or scope remains held rather than flattened.
        """
        ref = lambda slot: {'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el)}
        for table in [s for s in self.index.slots if s.kind == 'tbl' and s.part == 'word/document.xml']:
            rows = self.grid(table)
            for row, cells in rows.items():
                for cell in cells:
                    paragraphs = self.own_paragraphs(cell)
                    units = [self.box_units(p) for p in paragraphs]
                    if (len(paragraphs) < 3 or any(len(u) != 1 for u in units)
                            or any(u[0][2].strip() for u in units) or not units[0][0][1].strip().endswith(':')):
                        continue
                    # Ordinary unindented option lists keep their established
                    # flat behavior; indentation is essential to this shape.
                    positions = [self.tab_column_properties(p, checkbox_indent=True) for p in paragraphs]
                    if all(position == positions[0] for position in positions) and positions[0] is not None:
                        continue
                    column = cell.info['col']
                    heads = [c for c in cells if c.info['col'] + c.info['span'] == column
                             and c.info['vmerge'] == 'restart']
                    if len(heads) != 1:
                        for p in paragraphs:
                            self.coverage_issue(p, 'unmapped_answer',
                                'These indented controls follow a colon parent, but their complete printed item scope is unresolved. Review the parent and child questions separately.')
                            self.claimed.add(id(p.el))
                        continue
                    head = heads[0]
                    spanned = self.merge_rows(table, head)
                    peer = next((c for c in rows.get(row + 1, []) if c.info['col'] == column), None)
                    tail = next((c for c in rows.get(row + 1, []) if c.info['col'] == head.info['col']), None)
                    if peer is None or tail is None:
                        for p in paragraphs:
                            self.coverage_issue(p, 'unmapped_answer',
                                'This indented parent/subtype question lacks its complete peer row; review the exact original scope.')
                            self.claimed.add(id(p.el))
                        continue
                    peer_paragraphs = self.own_paragraphs(peer)
                    peer_units = [self.box_units(p) for p in peer_paragraphs]
                    headers = [c for r in self.header_rows(table) if r < row for c in rows[r]
                               if c.info['col'] == column and c.info['span'] == cell.info['span']]
                    header = headers[-1] if headers else None
                    source_cells = [c for c in (header, head, tail, cell, peer) if c is not None]
                    source_paragraphs = [p for c in source_cells for p in self.own_paragraphs(c)]
                    eligible = (header is not None and spanned == [row, row + 1]
                        and all(c.info['span'] == 1 for c in source_cells)
                        and cell.info['vmerge'] is None and peer.info['vmerge'] is None
                        and header.info['vmerge'] is None and tail.info['vmerge'] == 'continue'
                        and len(self.own_paragraphs(header)) == 1 and len(self.own_paragraphs(head)) == 1
                        and all(self.plain_spacing_paragraph(p, unused_tab_stops=True) for p in self.own_paragraphs(tail))
                        and not self.cell_text(tail).strip()
                        and len(peer_paragraphs) == 1 and len(peer_units[0]) == 1 and not peer_units[0][0][2].strip()
                        and all(c.kind == 'p' for source_cell in source_cells for c in source_cell.children)
                        and all(self.tab_source_visible(p) and not self.region_hidden(p.el) for p in source_paragraphs)
                        and not any(node.tag in (q('w:drawing'), q('w:pict'), q('w:object'), TXBX, q('w:hyperlink'))
                                    for p in source_paragraphs for node in p.el.iter()))
                    label = self.cell_text(header).strip() if header is not None else ''
                    item = self.cell_text(head).strip()
                    parent_label = clean_label(units[0][0][1])
                    peer_option = option_text(peer_units[0][0][1]) if len(peer_paragraphs) == 1 and peer_units[0] else ''
                    child_options = [option_text(u[0][1]) for u in units[1:]]
                    options = [parent_label, peer_option]
                    peer_position = self.tab_column_properties(peer_paragraphs[0], checkbox_indent=True) if peer_paragraphs else None
                    eligible = (eligible and positions[0] is not None and positions[0] == peer_position
                        and positions[1] is not None and positions[1] > positions[0]
                        and all(position == positions[1] for position in positions[1:])
                        and item.endswith(':') and label and (':' in label or '?' in label)
                        and len(label) <= MAX_MAPPING_LABEL and len(parent_label) <= MAX_MAPPING_LABEL
                        and len(set(options)) == 2 and all(options) and len(set(child_options)) == len(child_options)
                        and all(child_options) and not any(':' in option or '?' in option for option in [peer_option, *child_options])
                        and not self.box_units(self.own_paragraphs(head)[0])
                        and header is not None and not self.box_units(self.own_paragraphs(header)[0]))
                    texts = [self.text(p.el).strip() for p in source_paragraphs]
                    eligible = eligible and not any(self.blank_spans(*self.ptext(p.el)) for p in source_paragraphs
                                                   if p not in self.own_paragraphs(tail))
                    context = self.context_for(paragraphs[0], complete=True)
                    preceding = self.previous_continuous_paragraph(table)
                    context_sources = [preceding] if preceding is not None else []
                    human = any(self.checkbox_source_action(LIST_MARKER.sub('', clause.strip()), governing=True)
                        or signing_place(clause) for text in [*texts, *[u[0][1] for u in [*units, *peer_units] if u],
                            *context.split(' > '),
                            *(self.text(p.el).strip() for p in context_sources)]
                        for clause in [text, *re.split(r'(?<=[.;!?])\s*|[\r\n]+', text)] if clause.strip())
                    problem = 'The merged item, parent alternatives and indented child question need exact source review.'
                    if human:
                        self.protected_regions.update([cell.id, peer.id])
                        eligible = False
                        problem = 'This parent/subtype source contains a human-owned response or signing act; keep it unchanged.'
                    if eligible:
                        own = {id(p.el) for p in source_paragraphs}
                        # An existing tick is a state, not an imperative such
                        # as 'check one'. Read the complete printed label after
                        # each proved control; retain all other source clauses.
                        commands = [self.box_units(p)[0][1] if len(self.box_units(p)) == 1 else self.text(p.el)
                                    for p in source_paragraphs]
                        decisions = [self.cardinality(question, choices, local=commands, own=own, context=context)
                                     for question, choices in ((label, options), (parent_label, child_options))]
                        eligible = (len(context) <= MAX_MAPPING_CONTEXT
                            and all(not decision.get('problem') and decision.get('kind') == 'choice'
                                    for decision in decisions)
                            and not self.scope_limit(own, subject_stems(label, context, *options)))
                    if not eligible:
                        for p in [*paragraphs, *peer_paragraphs]:
                            self.coverage_issue(p, 'unmapped_answer', problem)
                            self.claimed.add(id(p.el))
                        continue
                    root_boxes = [units[0][0][0], peer_units[0][0][0]]
                    groups = [(label, options, root_boxes, None),
                              (parent_label, child_options, [u[0][0] for u in units[1:]], root_boxes[0])]
                    for question, choices, boxes, parent in groups:
                        anchors = [self.index.by_id.get(box['part'] + '#' + box['slot'])
                                   or next(p for p in [*paragraphs, *peer_paragraphs] if box in [u[0] for u in self.box_units(p)])
                                   for box in boxes]
                        relation = {'relation': 'merged_checkbox_hierarchy', 'sources': [ref(table), *[ref(c) for c in source_cells]],
                            'bands': [ref(cell), ref(peer)], 'parent': parent, 'question': question,
                            'context': context, 'options': choices, 'cardinality': 'choice'}
                        self.add(Area('choice', question, anchors[0], {'type': 'checkboxes', 'boxes': boxes}, context=context,
                            options=choices, complete_source=True, source_questions=[relation],
                            extra_slots=list(dict.fromkeys(s for s in anchors[1:] if s is not anchors[0]))))
                    self.claimed.update(id(p.el) for p in [*paragraphs, *peer_paragraphs])

    def checkbox_label_size(self, paragraph, position):
        """Explicit printed label size, never the checkbox glyph's font.

        Inherited/mixed sizes cannot establish a parent/child relationship.
        Delimiter and blank-rule glyphs are not words in the option label.
        """
        text, pieces = self.ptext(paragraph.el)
        boxes = [i for i, char in enumerate(text) if char in (BOX, CHECKED)]
        start = boxes[position] + 1
        stop = boxes[position + 1] if position + 1 < len(boxes) else len(text)
        sizes = set()
        for piece in pieces:
            ink = text[max(start, piece.start):min(stop, piece.end)]
            if not any(char.isalpha() for char in ink):
                continue
            if piece.run is None or hyperlink_run(piece.run):
                return None
            node = piece.run.find('./' + q('w:rPr') + '/' + q('w:sz'))
            if node is None or not str(node.get(q('w:val'), '')).isdigit():
                return None
            sizes.add(int(node.get(q('w:val'))))
        return next(iter(sizes)) if len(sizes) == 1 else None

    def rule_bracketed_checkbox_hierarchy(self):
        """A complete membership panel owns a finite two-line option tree.

        One colon parent continues the root-size options; its smaller child
        labels contain one explicitly bracketed sub-list. Every control and
        delimiter is accounted for. Other shapes remain source-held, rather
        than flattening parents and children into mutually exclusive peers.
        """
        for cell in [s for s in self.index.slots if s.kind == 'tc' and s.part == 'word/document.xml']:
            paragraphs = self.own_paragraphs(cell)
            for n, first in enumerate(paragraphs[:-1]):
                first_units = self.box_units(first)
                second = paragraphs[n + 1]
                units = self.box_units(second)
                if (len(first_units) < 2 or len(units) != 5 or not first_units[0][2].strip().endswith(':')
                        or units[0][2].strip() or not units[0][1].strip().endswith(':')
                        or '[' not in units[1][1] or ']' not in units[3][1]):
                    continue
                source = [p for p in paragraphs[:n] if self.text(p.el).strip()]
                problem = 'The printed parent, child options and selection permission need exact source review.'
                eligible = (len(source) == 2 and all(not self.box_units(p)
                    and not self.blank_spans(*self.ptext(p.el)) for p in source)
                    and all(p.kind == 'p' for p in cell.children)
                    and all(self.tab_source_visible(p) and not self.region_hidden(p.el) for p in [*source, first, second])
                    and not any(node.tag in (q('w:drawing'), q('w:pict'), q('w:object'), TXBX, q('w:hyperlink'))
                                for p in [*source, first, second] for node in p.el.iter()))
                title = self.text(source[0].el).strip() if source else ''
                instruction = self.text(source[-1].el).strip() if source else ''
                membership = re.fullmatch(r'(?:[^;?!\r\n]+\.\s+)?(?:Please\s+)?indicate\s+if\s+any\s+of\s+the\s+'
                    r'[^.;:?!\r\n]+\s+below\s+are\s+[^.;:?!\r\n]+\.?', instruction, re.I)
                explicit_many = many_evidence([instruction], [option_text(u[1]) for u in first_units])[0]
                eligible = eligible and bool(membership or explicit_many)
                texts = [self.text(p.el).strip() for p in [*source, first, second]]
                human_texts = [*texts, first_units[0][2], *[unit[1] for unit in [*first_units, *units]]]
                human = any(self.checkbox_source_action(LIST_MARKER.sub('', clause.strip()), governing=True)
                    or signing_place(clause) for text in human_texts
                    for clause in [text, *re.split(r'(?<=[.;!?])\s*|[\r\n]+', text)] if clause.strip())
                if human:
                    self.protected_regions.update([first.id, second.id])
                    eligible = False
                    problem = 'The printed hierarchy contains a human-owned signing or response act; keep it unchanged.'
                parent = re.fullmatch(r'\s*([^:;?!\[\]\r\n]+):\s*', units[0][1])
                branch = re.fullmatch(r'\s*([^:;?!\[\]\r\n]+)\s*\[\s*', units[1][1])
                inside = re.fullmatch(r'\s*([^:;?!\[\]\r\n]+?)\s*', units[2][1])
                close = re.fullmatch(r'\s*([^:;?!\[\]\r\n]+?)\s*\]\s*,?\s*', units[3][1])
                tail = re.fullmatch(r'\s*([^:;?!\[\]\r\n]+?)\s*:\s*_+\s*', units[4][1])
                eligible = eligible and all((parent, branch, inside, close, tail))
                second_text = self.ptext(second.el)[0]
                eligible = eligible and second_text.count('[') == 1 and second_text.count(']') == 1
                # The proven bracket contains its two child controls, not a
                # separate scalar blank. Other bracket/blank extents stay held.
                bracket = (second_text.find('['), second_text.find(']') + 1)
                spans = [span for span in self.blank_spans(*self.ptext(second.el))
                         if not (span[:2] == bracket and span[2] == 'bracket')]
                eligible = (eligible and len(spans) == 1 and spans[0][2] == 'blank'
                            and set(self.ptext(second.el)[0][spans[0][0]:spans[0][1]]) == {'_'})
                root_sizes = [self.checkbox_label_size(first, i) for i in range(len(first_units))]
                sizes = [self.checkbox_label_size(second, i) for i in range(5)]
                eligible = (eligible and root_sizes[0] is not None and all(s == root_sizes[0] for s in root_sizes)
                            and sizes[0] == root_sizes[0] and sizes[1] is not None and sizes[1] < sizes[0]
                            and all(s == sizes[1] for s in sizes[1:]))
                root_label = clean_label(first_units[0][2])
                context = ' > '.join(x for x in (title, instruction) if x)
                own = {id(p.el) for p in [*source, first, second]}
                group_options = [[option_text(u[1]) for u in first_units] + ([parent[1].strip()] if parent else []),
                                 [branch[1].strip(), tail[1].strip()] if branch and tail else [],
                                 [inside[1].strip(), close[1].strip()] if inside and close else []]
                if eligible:
                    # A binary question and every complete one/count command
                    # retain the established cardinality guard. Membership is
                    # local to this exact panel, never a global option alias.
                    eligible = not any(all(YESNO.match(o) for o in opts) for opts in group_options)
                    eligible = eligible and not one_only(texts, texts) and not any(
                        limit_language(clause, local=True) for text in texts for clause in _clauses(text))
                    eligible = eligible and not self.scope_limit(own, subject_stems(root_label, context, *group_options[0]))
                    eligible = eligible and len(context) <= MAX_MAPPING_CONTEXT
                if not eligible:
                    for p in (first, second):
                        self.coverage_issue(p, 'unmapped_answer', problem)
                        self.claimed.add(id(p.el))
                    continue
                ref = lambda p: {'part': p.part, 'slot': p.path, 'fingerprint': fingerprint(p.el)}
                grouping = [(root_label, [*first_units, units[0]], None),
                            (parent[1].strip(), [units[1], units[4]], units[0][0]),
                            (branch[1].strip(), [units[2], units[3]], units[1][0])]
                child_owner = None
                for position, (label, controls, required_parent) in enumerate(grouping):
                    boxes = [unit[0] for unit in controls]
                    anchors = [self.index.by_id.get(box['part'] + '#' + box['slot'])
                               or (first if box in [u[0] for u in first_units] else second) for box in boxes]
                    anchor = anchors[0]
                    relation = {'relation': 'bracketed_checkbox_hierarchy', 'sources': [ref(p) for p in [cell, *source, first, second]],
                        'bands': [ref(first), ref(second)], 'parent': required_parent,
                        'question': label, 'context': context, 'options': group_options[position], 'cardinality': 'multi_choice'}
                    area = Area('multi_choice', label, anchor, {'type': 'checkboxes', 'boxes': boxes},
                        context=context, options=group_options[position], complete_source=True,
                        source_questions=[relation], extra_slots=list(dict.fromkeys(s for s in anchors[1:] if s is not anchor)))
                    self.add(area)
                    if position == 1:
                        child_owner = area
                label = tail[1].strip()
                write_context = ' > '.join((context, child_owner.label,
                    'Only when the printed option ' + label + ' is selected'))
                start, end, shape = spans[0]
                relation = {'relation': 'adjacent_checkbox_answer', 'question': label, 'context': write_context,
                    'source': ref(second), 'owner': ref(child_owner.slot), 'owner_label': child_owner.label,
                    'owner_context': child_owner.context, 'owner_kind': child_owner.kind,
                    'owner_options': list(child_owner.options), 'owner_target': dict(child_owner.target),
                    'condition': 'printed_option', 'control': dict(units[4][0]), 'option_index': 1,
                    'printed_option': label, 'source_text': self.ptext(second.el)[0]}
                self.add(Area('text', label, second, {'type': 'span', 'start': start, 'end': end, 'shape': shape},
                    context=write_context, complete_source=True, source_questions=[relation]))
                self.claimed.update(id(p.el) for p in [*source, first, second])

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
                self.coverage_issue(s, 'coded_checkbox_withdrawal', self.notes[-1])
                self.claimed.add(id(s.el))
                continue
            if (any(hyperlink_run(piece.run) for piece, _, _ in glyph_boxes(s.el))
                    or any(hyperlink_control(node) for node in checkbox_nodes(s.el))):
                self.notes.append("A checkbox inside a fixed hyperlink was kept unchanged. Location: " + s.id)
                self.coverage_issue(s, 'unmapped_answer', self.notes[-1])
                self.claimed.add(id(s.el))
                continue
            if self.region_hidden(box_region(s.el)):
                # ⚠️ Its boxes cannot all be seen: no question is read from it (round 3 F1).
                self.notes.append("A line holds a checkbox QuillMD cannot read in place, so it was left for manual "
                                  "mapping: %s" % clean_label(txt)[:60])
                self.coverage_issue(s, 'unmapped_answer', self.notes[-1])
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

    def nested_cell_partition(self, table):
        """Prove independent question cells, never a shared row/column option grid.

        Each physical cell must begin with its own complete printed caption.
        A header-only cell, a nested grid, hidden source or competing first
        paragraph prevents this proof; no neighbouring caption is borrowed.
        """
        questions = {}
        cells = [slot for slot in self.index.slots if slot.kind == 'tc' and slot.parent is table]
        if not cells:
            return None
        for cell in cells:
            if any(slot.kind == 'tbl' for slot in cell.children) or self.region_hidden(cell.el):
                return None
            paragraphs = self.own_paragraphs(cell)
            first = next((slot for slot in paragraphs if self.text(slot.el).strip()), None)
            if first is None:
                return None
            caption = self.text(first.el).strip()
            _, _, source_problem = self.question_box_paragraph(first.el)
            if (source_problem or not self.tab_source_visible(first)
                    or not caption.endswith((':', '?')) or self.box_units(first)
                    or self.blank_spans(*self.ptext(first.el))
                    or len(caption) > MAX_MAPPING_LABEL
                    or any(not self.plain_spacing_paragraph(slot) for slot in paragraphs[:paragraphs.index(first)])):
                return None
            questions[cell.id] = first
        return questions

    def nested_cell_checkbox_source(self, group, table, cell, questions, outer):
        """One independently captioned cell owns exactly its complete option group."""
        if len(group['units']) < 2:
            # A lone alternative beside a scalar question may accompany an
            # independent date/text destination. Do not claim that caption as
            # the checkbox's whole question; leave its box explicitly held.
            return None
        question = questions[cell.id]
        paragraphs = self.own_paragraphs(cell)
        boxes = [slot for slot in paragraphs if self.box_units(slot)]
        if ({slot.id for slot in boxes} != {slot.id for slot in group['paras']}
                or any(self.owning_cell(slot) is not cell for slot in group['paras'])
                or any(len(self.box_units(slot)) != 1 for slot in boxes)):
            return None
        if any(slot is not question and slot not in boxes and (
                self.text(slot.el).strip() or not self.plain_spacing_paragraph(slot)) for slot in paragraphs):
            return None
        if any(self.blank_spans(*self.ptext(slot.el)) or not self.tab_source_visible(slot) for slot in boxes):
            return None
        before = [slot for slot in outer.children if slot.seq < table.seq]
        if any(slot.kind != 'p' for slot in before):
            return None
        sources = [slot for slot in before if self.text(slot.el).strip()]
        if any(not self.plain_spacing_paragraph(slot) for slot in before if slot not in sources):
            return None
        inherited, problem = self.question_box_context(outer.parent, require_visible=True)
        label = self.text(question.el).strip()
        context = ' > '.join(x for x in (inherited, *(self.text(slot.el).strip() for slot in sources)) if x)
        if (problem or len(context) > MAX_MAPPING_CONTEXT
                or any(not self.tab_source_visible(slot) for slot in sources)):
            return None
        # The exact caption and inherited source appoint an author or an act;
        # incidental words in an ordinary clinical caption do not do so.
        def action(value):
            caption = LIST_MARKER.sub('', str(value or '').strip())
            return bool(self.checkbox_source_action(caption, governing=True) or signing_place(caption))
        if action(label) or any(action(value) for value in [context, *(self.text(slot.el).strip() for slot in sources)]):
            self.protected_regions.add(cell.id if action(label) else table.id)
            return None
        relation = {'relation': 'nested_cell_options', 'sources': [
            {'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el)}
            for slot in [outer, table, question, *sources]]}
        return {'label': label, 'context': context, 'cardinality': label,
                'question_slot': question, 'relation': relation,
                'write_context': ' > '.join(x for x in (context, label) if x),
                'source_slots': sources + [question] + [slot for slot in paragraphs if not self.text(slot.el).strip()],
                'option_paras': boxes, 'local_cell_owner': True}

    def rule_scalar_alternatives(self):
        """A printed Or control is an alternative to one proven empty scalar.

        This deferred proof uses the immutable original's already detected
        scalar, never a reviewed label. Independent nested captions and one
        complete control must occupy the same cell. Other questions, blanks,
        hidden source and unknown native states retain the original hold.
        """
        for cell in [slot for slot in self.index.slots if slot.kind == 'tc']:
            paragraphs = self.own_paragraphs(cell)
            options = [(p, units[0]) for p in paragraphs for units in [self.box_units(p)]
                       if len(units) == 1 and not units[0][2].strip()
                       and re.fullmatch(r'Or\s+[^:;?!\n\t]{1,80}', option_text(units[0][1]), re.I)]
            if not options:
                continue
            table, outer = cell.parent, cell.parent.parent
            if (outer is None or outer.kind != 'tc' or outer.parent.parent is not None
                    or outer.part != 'word/document.xml'
                    or len(self.grid(outer.parent).get(outer.info['row'], [])) != 1):
                continue
            partition = self.nested_cell_partition(table)
            question = partition.get(cell.id) if partition else None
            scalars = [area for area in self.areas if self.host_cell(area.slot) is cell]
            option_p, unit = options[0]
            problem = 'The printed Or control does not have one proven empty scalar in its own captioned cell.'
            scalar = scalars[0] if len(scalars) == 1 else None
            eligible = (question is not None and scalar is not None and len(options) == 1
                        and scalar.slot is question and scalar.kind in ('text', 'date', 'time')
                        and not scalar.protection and not scalar.extra_slots
                        and scalar.target == {'type': 'span', 'start': len(self.ptext(question.el)[0]),
                            'end': len(self.ptext(question.el)[0]), 'shape': 'after_label'}
                        and sum(len(self.box_units(p)) for p in paragraphs) == 1
                        and not any(area.slot is option_p or option_p in area.extra_slots for area in self.areas))
            guidance = [p for p in paragraphs if p not in (question, option_p) and self.text(p.el).strip()]
            if eligible:
                eligible = all(re.match(r'^Instructions?\s*:', self.text(p.el).strip(), re.I)
                               and len(self.LABEL_COLON.findall(self.text(p.el))) == 1
                               for p in guidance)
                eligible = (eligible and all(self.tab_source_visible(p) and not self.blank_spans(*self.ptext(p.el))
                            and not any(node.tag in (q('w:drawing'), q('w:pict'), q('w:hyperlink'), q('w:sectPr'))
                                        for node in p.el.iter())
                            for p in paragraphs)
                            and all(self.plain_spacing_paragraph(p) for p in paragraphs
                                    if not self.text(p.el).strip() and not self.box_units(p)))
            before = [p for p in outer.children if p.seq < table.seq]
            sources = [p for p in before if p.kind == 'p' and self.text(p.el).strip()]
            inherited, inherited_problem = self.question_box_context(outer.parent, require_visible=True)
            context = ' > '.join(x for x in (inherited, *(self.text(p.el).strip() for p in sources),
                                 self.text(question.el).strip() if question else '',
                                 *(self.text(p.el).strip() for p in guidance)) if x)
            eligible = (eligible and not inherited_problem and len(context) <= MAX_MAPPING_CONTEXT
                        and all(p.kind == 'p' and self.tab_source_visible(p) and (
                            self.text(p.el).strip() or self.plain_spacing_paragraph(p)) for p in before))
            # Structural context separators are not part of a caption's noun
            # phrase. Read each complete original component and every clause;
            # appending a section title must not turn Review of systems into
            # an assigned review. A temporal caption still qualifies its own
            # governing act (Manager review date), rather than erasing it.
            source_texts = [*inherited.split(' > '), *(self.text(p.el).strip() for p in sources),
                            *(self.text(p.el).strip() for p in paragraphs)]
            clauses = [LIST_MARKER.sub('', clause.strip()) for text in source_texts
                       for clause in [text, *re.split(r'(?<=[.;!?])\s*|[\r\n]+', text)] if clause.strip()]
            human = any(self.checkbox_source_action(text, governing=True) or signing_place(text)
                        for text in clauses)
            if scalar is not None and scalar.kind == 'date' and question is not None:
                temporal = DATE_LABEL.sub(' ', LIST_MARKER.sub('', self.text(question.el).strip()))
                human = human or bool(self.checkbox_source_action(temporal, governing=True)
                    or signing_place(temporal) or BOX_SIGNING_VERB.search(temporal)
                    and not self.ordinary_source_kind([temporal], 'signature'))
            if human:
                self.protected_regions.add(cell.id)
                eligible = False
            if eligible:
                decision = self.cardinality(self.text(question.el), ['Scalar answer', option_text(unit[1])],
                    local=[self.text(p.el) for p in guidance], own={id(p.el) for p in paragraphs},
                    context=context)
                eligible = not decision.get('problem') and decision.get('kind') == 'choice'
            if eligible:
                box = unit[0]
                state = box_state(self.index, box)
                if box['kind'] == 'ff':
                    native = self.index.by_id.get(box['part'] + '#' + box['slot'])
                    fc = native.el.find(FLDCHAR) if native else None
                    data = fc.find(q('w:ffData')) if fc is not None else None
                    controls = data.findall(q('w:checkBox')) if data is not None else []
                    valid = len(controls) == 1 and all(len(controls[0].findall(q(tag))) <= 1
                        and all(n.get(q('w:val')) in (None, '1', 'true', 'on', '0', 'false', 'off')
                                for n in controls[0].findall(q(tag))) for tag in ('w:checked', 'w:default'))
                    eligible = valid and (state is True or state is False)
                elif box['kind'] == 'sdt':
                    native = self.index.by_id.get(box['part'] + '#' + box['slot'])
                    controls = native.el.findall('./' + q('w:sdtPr') + '/' + q('w14:checkbox')) if native else []
                    eligible = (len(controls) == 1 and len(controls[0].findall(q('w14:checked'))) <= 1
                        and all(n.get(q('w14:val')) in (None, '1', 'true', '0', 'false')
                                for n in controls[0].findall(q('w14:checked')))
                        and (state is True or state is False))
                else:
                    eligible = state is True or state is False
            if not eligible:
                for p in dict.fromkeys([*( [question] if question else []), *[p for p, _ in options]]):
                    self.coverage_issue(p, 'scalar_alternative_source', problem)
                continue
            ref = lambda p: {'part': p.part, 'slot': p.path, 'fingerprint': fingerprint(p.el)}
            anchor = self.index.by_id[unit[0]['part'] + '#' + unit[0]['slot']]
            relation = {'relation': 'scalar_checkbox_alternative', 'scalar': ref(scalar.slot),
                'scalar_target': dict(scalar.target), 'scalar_kind': scalar.kind, 'scalar_label': scalar.label,
                'scalar_context': scalar.context, 'cell': ref(cell), 'sources': [ref(p) for p in dict.fromkeys(
                    [outer, table, cell, question, option_p, *sources, *guidance])], 'original_checked': state}
            self.add(Area('checkbox', option_text(unit[1]), anchor,
                {'type': 'checkboxes', 'boxes': [unit[0]]}, context=context, options=[option_text(unit[1])],
                complete_source=True, source_questions=[relation], label_slot=question))
            removed = {issue['detail'] for issue in self.coverage_issues
                       if issue['part'] == option_p.part and issue['slot'] == option_p.path
                       and issue['code'] == 'nested_options'}
            self.coverage_issues[:] = [issue for issue in self.coverage_issues
                if not (issue['part'] == option_p.part and issue['slot'] == option_p.path
                        and issue['code'] == 'nested_options')]
            self.notes[:] = [note for note in self.notes if note not in removed
                            or any(issue['detail'] == note for issue in self.coverage_issues)]

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
        partition = self.nested_cell_partition(table)
        if partition:
            local = self.nested_cell_checkbox_source(group, table, cell, partition, outer)
            if local:
                return local
        before = [slot for slot in outer.children if slot.seq < table.seq]
        paragraphs = [slot for slot in before if slot.kind == "p" and self.text(slot.el).strip()]
        if not paragraphs:
            return None
        sources = [self.text(slot.el).strip() for slot in paragraphs]
        source = " ".join(sources)
        problem = ""
        explicit = [slot for slot in paragraphs if "?" in self.text(slot.el)
                    or CHECK_ALL.search(self.text(slot.el)) or CHECK_ONE.search(self.text(slot.el))]
        if not explicit and len(paragraphs) == 1 and sources[0].endswith(':'):
            explicit = paragraphs  # one complete printed label; all structural/source guards below still apply
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
            self.protected_regions.add(table.id)
        if problem:
            return {"problem": "Nested option grid at " + table.id + ": " + problem
                    + " Printed source: " + source + " Options: " + self.text(table.el, own=False),
                    "coverage_slot": table.id,
                    # Only a proven independent-cell partition permits a
                    # precise option-paragraph exclusion. The unsupported
                    # group's own physical boxes remain untouched; ordinary
                    # answers in other paragraphs/cells are not excluded.
                    "coverage_slots": [slot.id for slot in group['paras']] if partition else [table.id]}
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
        for start, end, _ in spans:
            self.coverage_issue(slot, 'unmapped_answer', self.notes[-1], start=start, end=end)

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
                        counted_sentence = self.count_guidance_sentence(sentence)
                        limit = limit_language(counted_sentence)
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
                        document = self.document_count_owner(p, sentence)
                        if document is not None:
                            owner = document
                        bounded = self.cell_instruction_owner(p)
                        if bounded is not None:
                            owner = bounded.el
                        named = self.named_guidance_owner(p)
                        if named is not None:
                            owner = named.el
                        found.append((id(p), owner, sentence, where, limit_targets(sentence) if limit else "*"))
            self._form_wide = found
        return self._form_wide

    @staticmethod
    def count_guidance_sentence(sentence):
        """Distinguish printed predicate numbers and coordinated amounts.

        Only the analysis text changes. The complete original sentence remains
        in the mapping and source evidence; a real selection/count command
        still reaches the established cardinality guard.
        """
        markers = list(re.finditer(r'\(([1-9][0-9]?)\)', sentence))
        if (len(markers) >= 2 and [int(m[1]) for m in markers] == list(range(1, len(markers) + 1))
                and re.search(r'\bwhen\s*$', sentence[:markers[0].start()], re.I)):
            pieces = [sentence[m.end():markers[n + 1].start() if n + 1 < len(markers) else len(sentence)]
                      for n, m in enumerate(markers)]
            if all(re.match(r'\s*(?:it\s+)?(?:is|are|was|were)\b', piece, re.I) for piece in pieces):
                sentence = re.sub(r'\(([1-9][0-9]?)\)', '', sentence)
        # An amount inherits the unit after its last coordinate: "6 and 12
        # months". Reuse exactly the existing measured-unit grammar.
        for match in reversed(list(re.finditer(r'\b([0-9]{1,2})\s+(?:and|or)\s+([0-9]{1,2})(?=\s+\S)', sentence))):
            if re.match(_NOT_A_MEASURE, sentence[match.end(2):], re.I) is None:
                sentence = sentence[:match.start(1)] + ' ' + sentence[match.end(1):]
        return sentence

    def document_count_owner(self, paragraph, sentence):
        """A declared current template's count concerns whole copies.

        Require its complete declared name to occur in a visible original
        header title and the entire copies-per-item command. An answer/box
        count or an extra command never gains this source relationship.
        """
        text = paragraph_text(paragraph)[0].strip()
        declared = re.match(r'^Instructions:\s*(?:The\s+)?([^.;:!?\r\n]+?)\s+is\s+a\s+template\.', text, re.I)
        if not declared:
            return None
        slot = next((s for s in self.index.slots if s.el is paragraph and s.kind == 'p'), None)
        if (slot is None or slot.part != 'word/document.xml' or slot.parent is not None
                or not self.tab_source_visible(slot) or self.blank_spans(*self.ptext(paragraph))
                or any(n.tag in (FLDCHAR, q('w:sdt'), q('w:drawing'), q('w:pict'), q('w:object'), TXBX) for n in paragraph.iter())):
            return None
        name = re.sub(r'\s+', ' ', declared[1]).strip()
        headers = [s for s in self.index.slots if s.kind == 'p' and s.part.startswith('word/header')
                   and self.is_heading(s.el) and self.tab_source_visible(s)]
        if not any(re.match(re.escape(name) + r'(?:\s|$)', self.ptext(s.el)[0].strip(), re.I) for s in headers):
            return None
        frame = re.fullmatch(r'After\s+[^,;.!?\r\n]+,\s*fill\s+out\s+all\s+' + re.escape(name)
                             + r's\s+for\s+[^;.!?\r\n]+?\s+[–—-]\s+one\s+for\s+each\s+[^;.!?\r\n]+\.?', sentence, re.I)
        if frame and not re.search(r'\b' + _TICK_VERB + r'\b|\b(?:only|max|minimum|maximum|limit)\b', sentence, re.I):
            return self.package.tree('word/document.xml')
        return None

    def cell_instruction_owner(self, paragraph):
        """An explicit instruction in one visible captioned cell stays local.

        A second caption, nested table, hidden source or stated wider reach
        leaves its scope unresolved. The actual question still reads this
        instruction through its own cell; no count wording is discarded.
        """
        slot = next((s for s in self.index.slots if s.el is paragraph and s.kind == 'p'), None)
        if slot is None or not re.match(r'^instruction\s*:', self.ptext(paragraph)[0].strip(), re.I):
            return None
        cell = self.host_cell(slot)
        if (cell is None or cell.part != 'word/document.xml'
                or cell.el.find('.//' + q('w:tbl')) is not None
                or any(n.tag in (q('w:drawing'), q('w:pict'), q('w:object'), TXBX, q('w:framePr')) for n in cell.el.iter())):
            return None
        paragraphs = [s for s in cell.children if s.kind == 'p']
        if len(paragraphs) != len(cell.children) or any(not self.tab_source_visible(s) for s in paragraphs):
            return None
        texts = [self.ptext(s.el)[0].strip() for s in paragraphs]
        captions = [s for s, text in zip(paragraphs, texts) if text.endswith((':', '?'))
                    and not re.match(r'^instruction\s*:', text, re.I) and BOX not in text and CHECKED not in text
                    and not self.blank_spans(*self.ptext(s.el))]
        if (len(captions) != 1 or paragraphs.index(captions[0]) >= paragraphs.index(slot)
                or any(WIDER_REACH.search(text) for text in texts)):
            return None
        return cell

    @staticmethod
    def named_caption(text):
        # The whole printed caption, with only numbering, terminal colon,
        # case and whitespace normalized. No subject/noun-stem association.
        text = unicodedata.normalize('NFKC', text)
        return re.sub(r'\s+', ' ', LIST_MARKER.sub('', text.strip())).rstrip(':').strip().casefold()

    def named_guidance_index(self):
        if self._named_guidance is None:
            owners, instructions = {}, {}
            for slot in [s for s in self.index.slots if s.kind == 'p']:
                text = self.ptext(slot.el)[0]
                frame = re.fullmatch(r'([^\r\n]+?)\s+[–—-]\s+(.+)', text.strip(), re.S)
                if frame and BOX not in text and CHECKED not in text:
                    instructions.setdefault(self.named_caption(frame[1]), []).append((slot, frame[2]))
                    continue
                prefix = re.split('[' + BOX + CHECKED + ']', text, maxsplit=1)[0].strip()
                boxed = ((BOX in text or CHECKED in text) and self.question_boxes(slot.el, text)
                         and self.box_run(slot.el) >= 2)
                below = (not boxed and prefix.endswith((':', '?')) and
                         (self.boxes_below(slot.el) is not None or
                          (following := self.next_printed(slot.el)) is not None and self.starts_with_box(following)))
                if prefix and (boxed or below):
                    owners.setdefault(self.named_caption(prefix), []).append(slot)
            self._named_guidance = owners, instructions
        return self._named_guidance

    def named_instruction_visible(self, slot):
        return (slot.part == 'word/document.xml' and slot.parent is None and self.tab_source_visible(slot)
                and not self.blank_spans(*self.ptext(slot.el))
                and not any(n.tag in (FLDCHAR, q('w:sdt'), q('w:drawing'), q('w:pict'),
                                     q('w:object'), TXBX, q('w:framePr')) for n in slot.el.iter()))

    def named_guidance_owner(self, paragraph):
        owners, instructions = self.named_guidance_index()
        for caption, entries in instructions.items():
            if not any(slot.el is paragraph for slot, _ in entries):
                continue
            candidates = owners.get(caption, [])
            if (len(candidates) == 1 and all(self.named_instruction_visible(slot) and not WIDER_REACH.search(text)
                    for slot, text in entries)
                    and self.tab_source_visible(candidates[0])):
                return candidates[0]
        return None

    @staticmethod
    def named_instruction_clauses(text, *, qualified=False):
        """Complete balanced source clauses and, when requested, qualifiers.

        A sentence's terminal period can be inside its closing quote. Apostrophes
        within a word are not quotation boundaries. Parentheses, brackets and
        quotation marks bind complete qualifier clauses, not a source-act escape.
        Malformed framing remains unproved; original text is never changed.
        """
        clauses, qualifiers, start, stack, quote = [], [], 0, [], None
        pairs = {'‘': '’', '“': '”', "'": "'", '"': '"'}
        delimiters = {'(': ')', '[': ']', '{': '}'}
        for at, char in enumerate(text):
            boundary = False
            if quote:
                if char == quote[0]:
                    qualifiers.append(text[quote[1] + 1:at])
                    quote = None
                    boundary = not stack and at > 0 and text[at - 1] in '.!?'
            elif char in pairs and (char in '‘“' or at == 0 or not text[at - 1].isalnum()):
                quote = (pairs[char], at)
            elif char in delimiters:
                stack.append((delimiters[char], at))
            elif char in delimiters.values():
                if not stack or char != stack[-1][0]:
                    return None
                qualifiers.append(text[stack.pop()[1] + 1:at])
            elif not stack and char in '.;!?\r\n':
                boundary = True
            if boundary:
                value = text[start:at + 1].strip(' .;!?\r\n')
                if value:
                    clauses.append(value)
                start = at + 1
        if quote or stack:
            return None
        rest = text[start:].strip(' .;!?\r\n')
        if rest:
            clauses.append(rest)
        return clauses + qualifiers if qualified else clauses

    @classmethod
    def named_instruction_source_action(cls, text):
        """Read complete nested clauses before proving local selection scope.

        Parenthetical appointments and coordinated response clauses remain part
        of the physical named instruction. A complete prospective determined
        response with an unresolved verb is held rather than appointed to the
        ordinary clinical writer. The original text and its binding stay intact.
        """
        # Quoted qualifiers can themselves contain balanced subordinate
        # clauses. Every proper qualifier is shorter than its enclosing source;
        # this finite invocation-local reading never derives authority from output.
        readings, pending, seen = [], [text], set()
        while pending:
            reading = pending.pop()
            if reading in seen:
                continue
            seen.add(reading); readings.append(reading)
            frames = cls.named_instruction_clauses(reading, qualified=True)
            if frames is not None:
                pending.extend(frame for frame in frames if frame not in seen)
        readings.extend(re.split(r'(?<=[.;!?])\s*|[\r\n]+', text))
        for reading in tuple(readings):
            readings.extend(re.split(r'(?:\s+|,\s*)(?:and|or|but)\s+|,\s*', reading, flags=re.I))
            readings.extend(re.split(r'\b(?:if|when)\s+', reading, flags=re.I)[1:])
        for reading in readings:
            source = re.sub(r'^(?:if|when|and|or|but)\s+', '', reading.strip(), flags=re.I)
            action = cls.checkbox_source_action(source, governing=True)
            # A possessive has/have/had takes an ordinary adjectival "initial"
            # noun phrase. A modal "must initial this response" still appoints
            # the signing act. Other complete source clauses keep their own
            # role readings; no clinical noun list supplies this distinction.
            initial_state = (cls.complete_signing_action(source)
                and cls.ordinary_source_kind([source], 'initials')
                and re.search(r'\b(?:has|have|had)\s+(?:(?:an?|the|my|our|your|his|her|their)\s+)?initial\b', source, re.I))
            if (action and not initial_state or cls.prospective_response(source, located=True)):
                return True
            # A present-tense signing predicate has an explicit subject and
            # determined object. "Clinical signs" / "initial observations"
            # lack this actor + finite predicate + object relationship.
            if re.fullmatch(r'[^.;:?!\r\n]+?\s+(?:sign|initial)s\s+'
                            r'(?:this|the|these|those)\s+[^.;:?!\r\n]+[.:]?', source, re.I):
                return True
        return False

    def named_local_object_scope(self, entries, options):
        """Prove selection objects stay on this uniquely captioned local group.

        Every selection command must name one unique printed option. A condition
        may refer to a datum defined above/below, but that direction must belong
        to its complete definition-reference frame, not the selected object.
        This proves scope only; it never supplies multiple or single cardinality
        and never changes the accepted answer names.
        """
        names = []
        for option in options:
            printed = option_text(option)
            names.append((printed, printed))
            # The instruction can cite the option before its printed skip
            # qualifier. Its answer value still includes that exact qualifier.
            skip = re.fullmatch(r'(.+?)\s+\(skip\s+to\s+[^()]+\)', printed, re.I)
            if skip:
                names.append((skip[1], printed))
        def condition_scope(condition):
            refs = list(re.finditer(r'as\s+defined\s+in\s+(?:[‘“\'"][^‘’“”\'"\r\n]+[’”\'"]|'
                                   r'[\w -]+?)\s+(?P<direction>above|below)\b', condition, re.I))
            return all(any(match.span() == ref.span('direction') for ref in refs)
                       for match in WIDER_REACH.finditer(condition))
        selected = []
        for _, text in entries:
            clauses = self.named_instruction_clauses(text)
            if clauses is None:
                return None
            for clause in clauses:
                verbs = list(re.finditer(r'\b' + _TICK_VERB + r'\b', clause, re.I))
                if not verbs:
                    if WIDER_REACH.search(clause) or limit_language(clause):
                        return None
                    continue
                if len(verbs) != 1:
                    return None
                verb = verbs[0]; prefix = clause[:verb.start()].strip()
                if prefix.casefold() not in ('', 'please'):
                    leading = re.fullmatch(r'(?:if|when)\s+(.+),\s*(?:please\s*)?', prefix, re.I)
                    if not leading or not condition_scope(leading[1]):
                        return None
                argument = clause[verb.end():].strip()
                quoted = re.match(r'([‘“\'\"])(.+?)([’”\'\"])(?=\s|$)', argument)
                if quoted:
                    matching_quote = {'‘': '’', '“': '”', "'": "'", '"': '"'}[quoted[1]]
                    if quoted[3] != matching_quote:
                        return None
                    cited = quoted[2].removesuffix('.')
                    matches = [(name, printed) for name, printed in names if name.casefold() == cited.casefold()]
                    tail = argument[quoted.end():].strip()
                else:
                    matches = [(name, printed) for name, printed in names
                               if re.match(re.escape(name) + r'(?=\s|$)', argument, re.I)]
                    longest = max((len(name) for name, _ in matches), default=0)
                    matches = [(name, printed) for name, printed in matches if len(name) == longest]
                    tail = argument[longest:].strip()
                if len(matches) != 1:
                    return None
                if tail:
                    trailing = re.fullmatch(r'(?:if|when)\s+(.+)', tail, re.I)
                    if not trailing or not condition_scope(trailing[1]):
                        return None
                selected.append(matches[0][1])
        return selected if selected and set(selected) == set(options) else None

    def named_selection_source(self, question, own, options):
        owners, instructions = self.named_guidance_index()
        caption = self.named_caption(question);entries = instructions.get(caption, [])
        if not entries:
            return None
        candidates = owners.get(caption, [])
        problem = 'The named selection instruction does not have one complete visible original question owner; review its exact caption and instructions.'
        if (len(candidates) != 1 or id(candidates[0].el) not in own
                or not self.tab_source_visible(candidates[0])
                or any(not self.named_instruction_visible(slot) for slot, _ in entries)):
            return {'problem': problem, 'source_slots': candidates + [slot for slot, _ in entries]}
        if any(self.named_instruction_clauses(text) is None for _, text in entries):
            return {'problem': problem, 'source_slots': candidates + [slot for slot, _ in entries]}
        if any(self.named_instruction_source_action(text) for _, text in entries):
            return {'problem': 'This exact named instruction appoints a human signing or author action; ordinary clinical answers cannot perform it.', 'human': True, 'source_slots': candidates + [slot for slot, _ in entries]}
        if any(WIDER_REACH.search(text) for _, text in entries):
            local_objects = self.named_local_object_scope(entries, options)
            if local_objects:
                return {'commands': [], 'owner': candidates[0], 'entries': entries,
                        'selected_objects': local_objects}
            return {'problem': 'The named instruction states a wider or referenced scope; its reach remains unresolved.',
                    'source_slots': candidates + [slot for slot, _ in entries]}
        many, unresolved, commands = False, False, []
        for _, text in entries:
            for sentence in [x.strip(' .;!?:\r\n') for x in re.split(r'(?<=[.;!?])\s*|[\r\n]+', text) if x.strip()]:
                conditional = re.fullmatch(r'(?:if|when)\s+[^;!?\r\n]+,\s*(.+)', sentence, re.I)
                command = conditional[1] if conditional else sentence
                command = re.sub(r'^please\s+', '', command, flags=re.I)
                select = re.fullmatch(r'(?:' + _TICK_VERB + r')\s+(.+)', command, re.I)
                permission = bool(HISTORY_MANY.fullmatch(command))
                if select:
                    argument = select[1]
                    permission |= bool(re.fullmatch(r'all\s+(?:relevant|applicable|appropriate)\s+[\w-]+', argument, re.I)
                                       or re.fullmatch(r'more\s+than\s+one\s+[\w-]+\s+if\s+relevant', argument, re.I)
                                       or conditional and re.fullmatch(r'both(?:\s+[\w-]+)?', argument, re.I))
                    alternative = re.fullmatch(r'a\s+([\w-]+)\s+or\s+([\w-]+)(?:\s+[^;:!?\r\n]+)?', argument, re.I)
                    permission |= bool(alternative and alternative[2].casefold() == alternative[1].casefold() + 's')
                    if permission and (COUNT_BOUND.search(command) or limit_language(command, local=True)
                                       or re.search(r'\b' + _TICK_VERB + r'\b', argument, re.I)):
                        unresolved = True
                    conditional_single = bool(conditional and (re.fullmatch(r'that\s+one\s+[^;:!?\r\n]+', argument, re.I)
                                               or option_text(argument).strip('‘’"').casefold() in [o.casefold() for o in options]))
                    if not permission and not conditional_single and not HISTORY_ONE.fullmatch(command):
                        unresolved = True
                elif limit_language(sentence):
                    unresolved = True
                if permission:
                    many = True;commands.append('Select all that apply')
                elif HISTORY_ONE.fullmatch(command):
                    commands.append('Select one')
        if not many:
            return None
        if unresolved:
            return {'problem': 'The complete named selection instruction includes an unsupported or competing selection command; review every original clause.', 'source_slots': candidates + [slot for slot, _ in entries]}
        return {'commands': commands, 'owner': candidates[0], 'entries': entries}

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
                       for o in (self.adjacent_option_text(unit) for unit in units)]
            question = clean_label(units[0][2])
            before_boxes = self.words_before_boxes(units, options) if len(units) > 1 else ""
            if before_boxes:
                # ⚠️ WORDS PRINTED BEFORE THEIR BOXES ('Smoker: Yes ☐ No ☐', 'Allergies: Yes ☐ No ☐ NKDA'): read as the
                # text after each box, every box took the next box's word, and 'No' ticked the Yes box (refutation F3,
                # and R3-1 whatever is printed after the last box).
                self.notes.append("Boxes at %s have their words printed before each box %s, so which printed word "
                                  "names which box was left for manual mapping. Printed source: %s"
                                  % (pslot.id, before_boxes, " | ".join(self.ptext(p.el)[0] for p in g["paras"])))
                for affected in g['paras']:
                    self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
                for p in g["paras"]:
                    self.claimed.add(id(p.el))
                continue
            host = pslot
            used_para = None
            row_question = False
            nested = self.nested_checkbox_source(g) if not question else None
            if nested and nested.get("problem"):
                self.notes.append(nested["problem"])
                for identity in nested.get('coverage_slots', [nested['coverage_slot']]):
                    self.coverage_issue(self.index.by_id[identity], 'nested_options', nested['problem'])
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
                        for affected in g['paras']:
                            self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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
            named = None
            if len(units) > 1:
                # The question's own source: its label, the lines of its boxes and what is printed after them, the
                # other paragraphs of its own cells, the header of its column, a nested grid's parent question and its
                # own adjacent instructions (the plain paragraphs directly above it, when they are not printed between
                # it and another question).
                local, between, local_slots = self.adjacent_instructions(used_para or pslot)
                cell = self.host_cell(pslot)
                cells = []
                if cell is not None and self.owning_cell(pslot) is cell:
                    cells = ([cell] if nested and nested.get('local_cell_owner') else
                             [cell, *self.question_cells(cell.parent, cell.info["row"], cell.info["col"])])
                # (its column header is one of its question cells, read with the rest of its own source)
                source, shared = self.own_source_texts(g["paras"] + ([used_para] if used_para is not None else []), cells)
                local = ([nested["cardinality"]] if nested else []) + local + source
                between = between + shared
                own = {id(x.el) for x in [*g["paras"], *local_slots, *([used_para] if used_para is not None else []),
                                          *(nested["source_slots"] if nested else [])]}
                if cell is not None:
                    own.update(self.own_paragraph_ids(cells))
                named = self.named_selection_source(question, own, options)
                if named and not named.get('problem'):
                    local += named['commands']
                    own.update(id(slot.el) for slot, _ in named['entries'])
                decision = named if named and named.get('problem') else self.cardinality(question, options, local=local, between=between, own=own,
                                            hint=self.text(g["paras"][0].el), where=" at " + pslot.id,
                                            context=self.context_for(anchor))
            if decision.get("problem"):
                # Never narrowed to one choice, never widened past a limit: the source is left for manual mapping.
                self.notes.append(decision["problem"])
                scoped_sources = []
                if named:
                    scoped_sources = (named['source_slots'] if 'source_slots' in named else
                                      [named['owner'], *[slot for slot, _ in named['entries']]])
                for affected in dict.fromkeys([*g['paras'], *scoped_sources]):
                    self.coverage_issue(affected, 'named_selection_source' if named else 'unmapped_answer', self.notes[-1])
                    if named and named.get('human'):
                        self.protected_regions.add(affected.id)
                        self.box_action_reasons[affected.id] = self.notes[-1]
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
                        for affected in g['paras']:
                            self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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
                if nested.get('local_cell_owner'):
                    area.label_slot = nested['question_slot']
                    area.source_questions = [nested['relation']]
                for source_slot in nested["source_slots"]:
                    self.claimed.add(id(source_slot.el))
                for option_para in nested["option_paras"]:
                    self.nested_write_in(option_para, nested["write_context"])
            if named:
                area.context = ' > '.join([area.context, *[text for _, text in named['entries']]]).strip(' >')
                if len(area.context) > MAX_MAPPING_CONTEXT:
                    for affected in g['paras']:
                        self.coverage_issue(affected, 'named_selection_source', 'The complete named instruction context exceeds mapping limits; nothing was shortened.')
                    continue
                area.complete_source = True
                area.source_questions.append({'relation': 'named_selection_instruction', 'question': area.label,
                    'context': area.context, 'options': list(area.options), 'cardinality': area.kind,
                    'instructions': [text for _, text in named['entries']],
                    'sources': [{'part': p.part, 'slot': p.path, 'fingerprint': fingerprint(p.el)}
                                for p in dict.fromkeys([named['owner'], *g['paras'], *[slot for slot, _ in named['entries']]])]})
                if named.get('selected_objects'):
                    area.source_questions[-1]['selected_objects'] = named['selected_objects']
            branches = [branch for unit in units for branch in [self.option_branch_source(unit)]
                        if branch and branch['qualified']]
            if branches:
                printed = [option_text(unit[1]) for unit in units]
                original_target, original_context = dict(area.target), area.context
                original_relations = list(area.source_questions)
                area.target['printed'] = printed
                area.context = ' > '.join(x for x in [area.context, *[
                    'Printed instruction for ' + branch['caption'] + ': ' + branch['instruction']
                    for branch in branches]] if x)
                area.complete_source = True
                area.source_questions.append({'relation': 'option_branch_instruction',
                    'question': area.label, 'context': area.context, 'options': list(area.options),
                    'printed': printed, 'branches': branches, 'original_target': original_target,
                    'original_context': original_context, 'original_relations': original_relations,
                    'sources': [{'part': p.part, 'slot': p.path, 'fingerprint': fingerprint(p.el)}
                                for p in g['paras']]})
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

    def rule_unclassified_response_lists(self):
        """Unclaimed printed list structure is reviewable, never a guessed question.

        A decimal parent followed by a separate lettered list can be an answer
        menu or an instruction list. Likewise literal a)/b) items under a colon
        heading have no physical write control. Neither structure proves role,
        cardinality or where an answer should be inserted. Preserve every item
        and require an exact source-area review before generation.
        """
        for question in [s for s in self.index.slots if s.kind == 'p']:
            if id(question.el) in self.claimed:
                continue
            label=self.text(question.el).strip()
            info=self.list_info(question.el)
            numbered=bool(info and info[2]=='decimal' and self.list_marker_is_plain(info)
                          and label and not label.endswith(('?',':')))
            literal=bool(label and len(label)<=MAX_MAPPING_LABEL and not BOX in label
                         and not CHECKED in label and not UNDERSCORES.search(label))
            if not (numbered or literal):
                continue
            items=[];node=question.el.getnext();identity=None
            while node is not None and node.tag==q('w:p'):
                slot=self.index.by_el.get(id(node))
                if slot is None or slot.parent is not question.parent or id(node) in self.claimed:
                    break
                text=self.text(node).strip();option=self.list_info(node)
                if not text or len(text)>120 or BOX in text or CHECKED in text or UNDERSCORES.search(text):
                    break
                if numbered:
                    if (not option or option[2] not in ('lowerLetter','upperLetter','lowerRoman','upperRoman')
                            or option[:2]==info[:2] or not self.list_marker_is_plain(option)):
                        break
                    if identity is not None and option!=identity:
                        break
                    identity=option
                elif not re.fullmatch(r'(?:[a-z]|[ivxlcdm]+)[).]\s+\S.{0,117}',text,re.I):
                    break
                items.append(slot);node=node.getnext()
            if len(items)<2:
                continue
            detail=('This printed list has no qualified answer ownership or cardinality. It may be an answer '
                    'menu or fixed instructions; no answer place was invented. Review these exact original '
                    'areas before generation. Parent: '+label+'. Items: '+' | '.join(self.text(s.el).strip() for s in items))
            self.notes.append(detail)
            for affected in [question,*items]:
                self.coverage_issue(affected,'unclassified_response_list',detail)
                self.claimed.add(id(affected.el))

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
                                self.coverage_issue(opt_slot, 'unmapped_answer', self.notes[-1])
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
                            for affected in opts:
                                self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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
    def is_box_cell(self, c) -> bool:
        """The existing printed-box reading, plus one unprinted native field."""
        return (self.cell_text(c) in (BOX, CHECKED) and not self.region_hidden(c.el)) or (
                len(c.children) == 1 and c.children[0].kind == "p"
                and self.tab_source_visible(c.children[0])
                and self.ptext(c.children[0].el)[0].strip() in (BOX, CHECKED)
                and len(self.box_units(c.children[0])) == 1)

    def is_option_cell(self, c) -> bool:
        """An empty cell, or one holding only a checkbox (to be ticked), under an option column."""
        if self.cell_has_claim(c.el):
            return False
        txt = self.cell_text(c)
        if self.region_hidden(c.el):
            return False                # a checkbox its reading does not show (round 3 F1)
        return is_blank_text(txt) and self.is_empty_cell(c) or self.is_box_cell(c)

    def guided_other_response_row(self, table, row):
        """One OTHER row on a proved YES/NO/REFUSED axis, with fixed trailing guidance.

        The guidance is not an option or a writable span. This narrow source
        contract keeps three distinct visible glyphs and binds the complete
        headers, row caption and appended instruction before grouping them.
        """
        rows = self.grid(table)
        first = min(rows)
        if row <= first or self.response_matrix_corner(table, first) is None:
            return None
        header = sorted(rows[first], key=lambda c: c.info['col'])
        cells = sorted(rows[row], key=lambda c: c.info['col'])
        if (len(header) != 4 or len(cells) != 4
                or [self.cell_text(c) for c in header[1:]] != ['YES', 'NO', 'REFUSED']
                or self.cell_text(cells[0]) != 'OTHER'
                or any(c.info['col'] != n or c.info['span'] != 1 or c.info['vmerge']
                       for n, c in enumerate(cells))):
            return None
        unsafe = {q('w:sdt'), FLDCHAR, q('w:instrText'), q('w:drawing'), q('w:pict'),
                  q('w:object'), q('w:hyperlink'), q('w:tbl'), q('w:br')}
        if any(node.tag in unsafe for cell in header for node in cell.el.iter()):
            return None
        # The original axis must continue without an intervening header,
        # divider, merge, hidden control or independent answer band.
        for previous in range(first + 1, row):
            band = sorted(rows.get(previous, []), key=lambda c: c.info['col'])
            if (len(band) != 4 or any(c.info['col'] != n or c.info['span'] != 1 or c.info['vmerge']
                                     for n, c in enumerate(band))
                    or not self.is_label_cell(band[0], complete=True)
                    or any(node.tag in unsafe for cell in band for node in cell.el.iter())
                    or any(p.kind != 'p' or not self.tab_source_visible(p) or self.box_units(p)
                           or self.blank_spans(*self.ptext(p.el)) for p in band[0].children)):
                return None
            for cell in band[1:]:
                if (len(cell.children) != 1 or cell.children[0].kind != 'p'
                        or not self.tab_source_visible(cell.children[0])
                        or self.ptext(cell.children[0].el)[0].strip() not in (BOX, CHECKED)
                        or len(self.box_units(cell.children[0])) != 1
                        or self.box_units(cell.children[0])[0][0]['kind'] != 'glyph'):
                    return None
        boxes = []
        for n, cell in enumerate(cells):
            if (len(cell.children) != 1 or cell.children[0].kind != 'p'
                    or not self.tab_source_visible(cell.children[0])
                    or any(node.tag in unsafe for node in cell.el.iter())
                    or self.cell_has_claim(cell.el)):
                return None
            para = cell.children[0]
            text = self.ptext(para.el)[0].strip()
            units = self.box_units(para)
            if n == 0:
                if units or self.blank_spans(*self.ptext(para.el)):
                    return None
                continue
            if len(units) != 1 or units[0][0]['kind'] != 'glyph':
                return None
            if n < 3 and text not in (BOX, CHECKED):
                return None
            if n == 3 and not re.fullmatch(r'[☐☒][\s\uf020]*\[IF YES, SPECIFY BELOW\.\]', text):
                return None
            boxes.append(units[0][0])
        sources = [{'part': c.part, 'slot': c.path, 'fingerprint': fingerprint(c.el)}
                   for c in [*header, *cells]]
        return {'boxes': boxes, 'relation': {'relation': 'guided_response_row', 'sources': sources,
                                           'guidance': self.ptext(cells[3].children[0].el)[0]}}

    def rule_guided_other_response_rows(self):
        # Bind the complete row before its appended guidance can look like the
        # caption of a standalone checkbox. Other table readings are unchanged.
        for table in (s for s in self.index.slots if s.kind == 'tbl'):
            for row in self.grid(table):
                guided = self.guided_other_response_row(table, row)
                if guided is None:
                    continue
                cells = sorted(self.grid(table)[row], key=lambda c: c.info['col'])
                self.add(Area('choice', 'OTHER', cells[1], {'type': 'checkboxes', 'boxes': guided['boxes']},
                              context=self.context_for(cells[1]), options=['YES', 'NO', 'REFUSED'],
                              extra_slots=cells[2:], source_questions=[guided['relation']]))
                for cell in cells[1:]:
                    self.claimed.update(id(node) for node in cell.el.iter())

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
            defaults = self.default_source_styles("table")
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
            for r in rows:
                corner = self.response_matrix_header_corner(tslot, r)
                if corner is not None:
                    self.claimed.update(id(node) for node in corner.el.iter())
                    self.protected_regions.add(corner.id)
                    self.response_header_corners.add(corner.id)
                    self.notes.append("The empty corner at " + corner.id +
                                      " is fixed spacing above this table's response columns, not an answer. "
                                      "Use each row's checkbox choices; reinspect an older mapping that writes here.")
                    if self.response_matrix_corner(tslot, r) is None:
                        detail = ("The response matrix at " + tslot.id +
                                  " has a fixed header but its complete one-box-per-response layout is unresolved. "
                                  "Review the original controls, visibility and merges; no answer belongs in the empty header corner.")
                        self.notes.append(detail)
                        self.coverage_issue(tslot, 'unmapped_response_matrix', detail)
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
                    if c.info["vmerge"] != "continue" and not self.cell_has_claim(c.el) and self.is_box_cell(c) \
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
                    boxed = self.is_box_cell(c)
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
                boxed_run = all(self.is_box_cell(c) for c, _ in run)
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
                    for affected, _ in run:
                        self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
                elif any(positive_command(text) for text in [label, *grid_own] + [
                        self.cell_text(x) for c, _ in run for x in self.question_cells(tslot, r, c.info["col"])]):
                    # A grid row reads one answer per row; a several-answers command in the row, over its columns or
                    # in the grid's own instruction cannot be honoured.
                    self.notes.append("Rating grid row '%s' at %s was left for manual mapping: its printed all-that-apply "
                                      "instruction conflicts with the grid's one answer per row; nothing was guessed."
                                      % (label[:60], run[0][0].id))
                    for affected, _ in run:
                        self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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
                                for affected in opts:
                                    self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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
                    for _, affected, _ in labelled:
                        self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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
                    for _, affected, _ in labelled:
                        self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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
                    for _, affected, _ in labelled:
                        self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
                    self._col_lists[(id(tslot), col)] = False
                    continue
                if decision["kind"] != "multi_choice" and not decision["single"]:
                    self.notes.append("Checkbox column at %s was left for manual mapping: its boxes mark rows of "
                                      "independent items, and nothing printed says whether one row or several may be "
                                      "marked; one choice would assert an exclusivity the form does not print. Column: %s"
                                      % (first.id, clean_label(header)[:80]))
                    self.coverage_issue(first, 'unmapped_answer', self.notes[-1])
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
                            for _, affected, _ in g:
                                self.coverage_issue(affected, 'unmapped_answer', self.notes[-1])
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

    @classmethod
    def parenthetical_write_request(cls, text):
        """A complete named caption with a terminal imperative, not a status qualifier."""
        frame = re.fullmatch(r'([^()\r\n?!]{1,160}?)\s*\(([^()\r\n]{1,80})\)\s*[:.]?', text.strip())
        return bool(frame and clean_label(frame[1]) and cls.INSTRUCTED.fullmatch(frame[2].strip()))

    def write_request_source(self, caption):
        return {'relation': 'parenthetical_write_request', 'question': self.ptext(caption.el)[0].strip(),
                'source': {'part': caption.part, 'slot': caption.path, 'fingerprint': fingerprint(caption.el)}}

    def rule_parenthetical_write_cells(self):
        """A sole printed request owns its flowing cell; append below and preserve its ink."""
        for cell in (slot for slot in self.index.slots if slot.kind == 'tc'):
            if self.cell_has_claim(cell.el) or not self.cell_is_plain(cell) or wraps_structure(cell.el):
                continue
            named = [p for p in cell.children if p.kind == 'p' and self.ptext(p.el)[0].strip()]
            if len(named) != 1:
                continue
            caption = named[0]; printed, pieces = self.ptext(caption.el)
            head = clean_label(printed.partition('(')[0])
            role = signing_place(head); action = self.checkbox_source_action(head, governing=True)
            if (not self.parenthetical_write_request(printed) or self.blank_spans(printed, pieces)
                    or not self.tab_source_visible(caption) or self.question_box_paragraph(caption.el)[2]
                    or not role and self.row_label(cell.parent, cell.info['row'], cell.info['col'])
                    or any(p.kind != 'p' or p is not caption and not self.plain_spacing_paragraph(p, unused_tab_stops=True)
                           for p in cell.children)):
                continue
            area = Area(role or 'long_text', clean_label(printed), cell, {'type': 'cell_append'},
                        context=self.context_for(caption, complete=True), complete_source=True,
                        source_questions=[self.write_request_source(caption)], label_slot=caption)
            if role or action:
                area.source_action = True
                area.protection = ('This printed signing or document action is human-owned. Complete it through the explicit human signing workflow.'
                                   if role or action == 'human_signing_action' else
                                   'This printed action does not establish who performs it. Keep it unchanged and review its precise source role.')
            self.add(area)
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

    def source_style_index(self):
        """Read this immutable source's catalogue once, retaining every duplicate."""
        if self._style_index is None:
            index, defaults = {}, {}
            if "word/styles.xml" in self.package.names:
                styles = self.package.tree("word/styles.xml").findall(q("w:style"))
                identity, category, implicit = q("w:styleId"), q("w:type"), q("w:default")
                for style in styles:
                    kind = style.get(category)
                    index.setdefault((style.get(identity), kind), []).append(style)
                    if style.get(implicit) in ("1", "true", "on"):
                        defaults.setdefault(kind, []).append(style)
            self._style_index = {key: tuple(nodes) for key, nodes in index.items()}
            self._style_defaults = {key: tuple(nodes) for key, nodes in defaults.items()}
        return self._style_index

    def default_source_styles(self, kind):
        self.source_style_index()
        return self._style_defaults.get(kind, ())

    def question_box_style_chain(self, name, kind):
        key = (name, kind)
        if key in self._style_chains:
            chain, problem = self._style_chains[key]
            return list(chain), problem

        def finish(chain, problem):
            self._style_chains[key] = (tuple(chain), problem)
            # A caller cannot change another reading's cached ancestry list.
            return list(chain), problem

        chain, seen = [], set()
        if not name:
            return finish([], "The style ancestry is not uniquely defined.")
        while name:
            if name in seen or len(chain) >= 32 or "word/styles.xml" not in self.package.names:
                return finish([], "The style ancestry is cyclic or unavailable.")
            seen.add(name)
            matches = self.source_style_index().get((name, kind), ())
            if len(matches) != 1:
                return finish([], "The style ancestry is not uniquely defined.")
            style = matches[0]
            chain.append(style)
            base = style.find(q("w:basedOn"))
            name = base.get(q("w:val")) if base is not None else ""
            if base is not None and not name:
                return finish([], "The style ancestry is not uniquely defined.")
        return finish(chain, "")

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
        return (SIGNATURE.search(reading) or INITIALS.search(reading) or re.search(r"\bconsent\b", reading, re.I)
                # A complete printed place label ending in the action noun is
                # human-owned regardless of who is named before it. Enumerating
                # signer roles would release every role omitted from that list.
                # A question about recorded status is a different structure and
                # does not end in this action label.
                or re.fullmatch(r'(?:[^:?!\r\n]+\s+)?(?:attestation|declaration|sign[ -]?off)\s*:',
                                reading.strip(), re.I))

    def question_box_role_source(self, table):
        """(printed question, section) over a one-cell box, read for the box's DESTINATION ROLE only (destination_roles).

        Unlike rule_question_boxes' reading, a question paragraph holding a line break, a drawing or a field is still
        read, and so is a header or footer box: those are never mapped by the engine (so nothing here becomes a label),
        but a signing box printed that way is still a signing box. At most two empty paragraphs are skipped."""
        node, skipped = table.el.getprevious(), 0
        while node is not None and node.tag == q("w:p"):
            raw = re.sub(r"\s+", " ", self.text(node)).strip()
            if raw:
                slot = self.index.by_el.get(id(node))
                section = self.question_box_context(slot)[0] if slot is not None and slot.parent is None else ""
                return raw, section
            skipped += 1
            if skipped > 2:
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
    def prospective_response(text, *, located=False):
        """Existing finite subject/auxiliary/determined-response relationship.

        Its verb can be unresolved. The ordinary authorship reader still requires
        the existing writing predicate; a named instruction can hold that exact
        ambiguous current response without granting another person's authority.
        """
        response = r"(?:comments?|concerns?|statements?|answers?|responses?)"
        location = (r"(?:\s+(?:here|in\s+this\s+(?:(?:answer|response)\s+)?"
                    r"(?:section|area|space|box|field)))?" if located else '')
        return re.fullmatch(
            r"\s*[^;:?!\r\n]+?\s+(?:" + SOURCE_ACTION_AUXILIARY + r"\s+)+"
            r"(?:(?:required\s+)?to\s+)?(?P<predicate>[^.;:?!\r\n]+?)\s+"
            r"(?P<object>the\s+following|(?:this|the|these|my|our|your|his|her|their)\s+" + response + r")"
            + location + r"\s*[:.]?\s*", text, re.I)

    @classmethod
    def question_box_authorship(cls, text):
        # Complete prospective authorship frames appoint the author, without
        # inferring a job title or enumerating ways they might write comments.
        # An active section assignment has an author + infinitive predicate;
        # its passive equivalent has a comment object + "to be" + "by" author.
        # A receipt/status label lacks that relation. Read the whole caption:
        # neither a later clinical question nor a neighboring answer belongs
        # to this reservation. A period in an author's name stays permissible.
        response = r"(?:comments?|concerns?|statements?|answers?|responses?)"
        # A physical area assigned to an author + infinitive appoints that
        # author whatever the particular writing verb or answer subject is.
        # Medication/status captions have neither this area subject nor that
        # complete agentive relationship.
        active = re.fullmatch(r"\s*this (?:section|area|space|box|field) is (?P<reserved>reserved\s+)?for\s+"
                  r"(?P<author>[^:;?!\r\n]+?)\s+to\s+(?P<predicate>[^.;:?!\r\n]+?)\s*[:.]?\s*", text, re.I)
        # An explicit generic clinician recording an ordinary observation or
        # a document's receipt is the form's data-entry operator, not another
        # person's authored statement. Require the complete record argument
        # to have the established ordinary initial/receipt reading and no act
        # clause. Named/reserved authors and response/approval objects stay
        # held; a reviewed label cannot supply this source relationship.
        if active and not active['reserved'] and re.fullmatch(r'the\s+clinician', active['author'], re.I):
            recorded = re.fullmatch(r'record\s+(.+)', active['predicate'], re.I)
            if (recorded and (cls.ordinary_source_kind([recorded[1]], 'initials')
                              or cls.ordinary_source_kind([recorded[1]], 'signature'))
                    and not cls.temporal_source_action(recorded[1])):
                active = None
        passive = (r"^\s*" + response + r"\s+to\s+be\s+[^.;:?!\r\n]+?\s+by\s+"
                   r"[^:;?!\r\n]+?\s*[:.]?\s*$")
        # An explicit subject obligated to write this response is its author;
        # clinical obligations about medication/signs are different arguments.
        prospective = cls.prospective_response(text)
        # Reuse the existing data-entry instruction grammar. A prospective
        # clinical obligation to include/avoid something is not a writer.
        writing = prospective and (re.match(r'write\b', prospective['predicate'], re.I)
                                    or ENTER_HINT.match(prospective['predicate'] + ' ' + prospective['object']))
        return active or re.fullmatch(passive, text, re.I) or writing

    def manual_numeric_parts(self, chosen):
        """Visible, empty, plain numeric parts available for explicit human mapping only."""
        if chosen.kind != 'p' or not self.tab_source_visible(chosen):
            return []
        unsafe = {q('w:sdt'), FLDCHAR, q('w:instrText'), q('w:drawing'), q('w:pict'), q('w:object'),
                  q('w:hyperlink'), q('w:sectPr'), q('w:br'), q('w:vanish'), q('w:numPr')}
        if any(node.tag in unsafe for node in chosen.el.iter()):
            return []
        return numeric_part_ranges(self.ptext(chosen.el)[0])

    def manual_numeric_part(self, chosen, number, kind):
        parts = self.manual_numeric_parts(chosen)
        if kind != 'text' or type(number) is not int or not 1 <= number <= len(parts):
            return None
        start, end = parts[number - 1]
        relation = {'relation': 'manual_numeric_part', 'number': number, 'parts': len(parts),
                    'source': {'part': chosen.part, 'slot': chosen.path, 'fingerprint': fingerprint(chosen.el)}}
        return Area('text', 'Numeric part %d' % number, chosen,
                    {'type': 'span', 'start': start, 'end': end, 'shape': 'numeric_part', 'number': number},
                    context=self.context_for(chosen, complete=True), complete_source=True,
                    source_questions=[relation], capacity=end - start)

    def manual_paragraph_options(self, chosen, kind):
        """A clinician explicitly appoints a complete printed list as options.

        Plain bullets alone do not establish selection or cardinality. This
        recovery is available only for an adjacent complete printed question
        and a finite homogeneous list, with every physical paragraph bound.
        Existing boxes, fields, selections and uncertain list boundaries stay
        outside this contract. No automatic detection score changes here.
        """
        if chosen.kind != 'p' or kind not in ('choice', 'multi_choice'):
            return None
        question = chosen
        if self.list_info(chosen.el):
            previous = chosen.el.getprevious()
            question = self.index.by_el.get(id(previous)) if previous is not None else None
        if question is None or question.kind != 'p' or question.parent is not chosen.parent:
            return None
        prompt = self.text(question.el).strip()
        unsafe = {q('w:sdt'), FLDCHAR, q('w:instrText'), q('w:drawing'), q('w:pict'),
                  q('w:object'), q('w:sectPr'), q('w:br'), q('w:vanish')}
        if (self.list_info(question.el) or not prompt.endswith(('?', ':'))
                or not (self.question_box_request(prompt) or re.match(r'^(?:what|which|where|how|who|when)\b', prompt, re.I))
                or self.question_box_reference(prompt) or self.question_box_authorship(prompt)
                or self.checkbox_source_action(prompt, governing=True) or self.question_box_signing(prompt)
                or len(prompt) > MAX_MAPPING_LABEL or not self.tab_source_visible(question)
                or any(node.tag in unsafe for node in question.el.iter())
                or self.blank_spans(*self.ptext(question.el))):
            return None
        options, descriptors, slots = [], [], []
        node = question.el.getnext()
        while node is not None and node.tag == q('w:p'):
            slot = self.index.by_el.get(id(node)); info = self.list_info(node)
            if info is None:
                break
            text = self.text(node).strip()
            # A malformed/hidden/different-level list item is an incomplete
            # group, never a reason to silently keep only its easy prefix.
            if (slot is None or slot.parent is not question.parent or slot.part != question.part
                    or not text or len(text) > 200 or BOX in text or CHECKED in text
                    or self.blank_spans(*self.ptext(node)) or self.question_box_request(text)
                    or not self.tab_source_visible(slot) or any(child.tag in unsafe for child in node.iter())
                    or len(node.findall('./' + q('w:pPr') + '/' + q('w:numPr'))) != 1
                    or not self.list_marker_is_plain(info)
                    or info[2] not in ('bullet', 'lowerLetter', 'upperLetter', 'lowerRoman', 'upperRoman', 'decimal')
                    or descriptors and list(info[1:]) != descriptors[0]['numbering'][1:]
                    or len(options) >= 100):
                return None
            options.append(option_text(text)); slots.append(slot)
            descriptors.append({'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(node),
                                'text': text, 'numbering': list(info)})
            node = node.getnext()
        if len(options) < 2 or chosen is not question and chosen is not slots[0]:
            return None
        if len({option.lower() for option in options}) != len(options):
            return None
        context = self.context_for(question, complete=True)
        context = ' > '.join(value for value in (context, prompt) if value)
        if len(context) > MAX_MAPPING_CONTEXT:
            return None
        relation = {'relation': 'manual_paragraph_options', 'question': prompt,
                    'cardinality': 'one' if kind == 'choice' else 'many',
                    'source': {'part': question.part, 'slot': question.path, 'fingerprint': fingerprint(question.el)},
                    'descriptors': descriptors,
                    'definitions': {name: hashlib.sha256(self.package.zip.read(name)).hexdigest()
                                    for name in ('word/numbering.xml', 'word/_rels/document.xml.rels')
                                    if name in self.package.names}}
        return Area(kind, prompt, slots[0], {'type': 'paragraph_options', 'paragraphs': [slot.path for slot in slots]},
                    options=options, extra_slots=slots[1:], context=context,
                    complete_source=True, source_questions=[relation])

    def ruled_paragraph_stop(self, slot):
        """An explicit single flowing underscore leader, not a column or guessed line."""
        if slot.kind != 'p' or slot.part != 'word/document.xml' or slot.parent is not None:
            return None
        tabs = slot.el.findall('./' + q('w:pPr') + '/' + q('w:tabs') + '/' + q('w:tab'))
        if len(tabs) != 1 or tabs[0].get(q('w:leader')) != 'underscore' or tabs[0].get(q('w:val')) != 'right':
            return None
        geometry = self.tab_column_properties(slot)
        if geometry is None or len(geometry[0]) != 1 or geometry[0][0][1] != 'right':
            return None
        return geometry

    def rule_ruled_paragraphs(self):
        """One complete printed narrative owns every matching line and spacer.

        Reuse the historical source-bound recovery compiler. The relation's
        legacy name stays stable; automatic fields have no manual origin.
        Partial or unresolved ruled destinations remain visible exclusions.
        """
        for slot in self.index.slots:
            if (id(slot.el) in self.claimed or self.ruled_paragraph_stop(slot) is None
                    or self.ptext(slot.el)[0] != '\t'):
                continue
            area = self.manual_ruled_paragraphs(slot, 'long_text')
            if area is None:
                self.claimed.add(id(slot.el))
                reason = ('The complete ruled answer group and its printed question could not be bound. '
                          'Review the original and recover the complete group; no partial group was appointed.')
                self.coverage_issue(slot, 'unmapped_answer', reason)
                self.notes.append(reason + ' Location: ' + slot.id)
                continue
            relation = area.source_questions[0]
            refs = [relation['source'], *relation['descriptors'], *relation['instructions']]
            if any(id(self.index.by_id[_place_id(ref['part'], ref['slot'])].el) in self.claimed for ref in refs):
                continue
            self.add(area)
            for ref in refs:
                self.claimed.add(id(self.index.by_id[_place_id(ref['part'], ref['slot'])].el))

    def manual_ruled_paragraphs(self, chosen, kind):
        """Explicitly recover a complete body narrative made of printed ruled lines.

        All answer lines, intervening ruled spacers, the adjacent caption and
        optional fixed bracket guidance belong to one source-bound relation.
        The line group must start here; a middle line never creates a suffix.
        Tables, hidden/unknown formatting, filled lines and column tabs refuse.
        """
        geometry = self.ruled_paragraph_stop(chosen)
        if kind != 'long_text' or geometry is None or self.ptext(chosen.el)[0] != '\t':
            return None
        unsafe = {q('w:sdt'), FLDCHAR, q('w:instrText'), q('w:drawing'), q('w:pict'),
                  q('w:object'), q('w:sectPr'), q('w:br')}
        def safe(slot):
            return (slot is not None and slot.kind == 'p' and slot.part == chosen.part
                    and slot.parent is chosen.parent and self.tab_source_visible(slot)
                    and not self.question_box_paragraph(slot.el)[2]
                    and not any(node.tag in unsafe for node in slot.el.iter()))
        def ref(slot):
            return {'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el),
                    'text': self.ptext(slot.el)[0]}
        def human(text):
            lexical = self.question_box_signing(text)
            if lexical and (self.ordinary_source_kind([text], 'initials')
                            or self.ordinary_source_kind([text], 'signature')):
                lexical = False
            return (self.checkbox_source_action(text, governing=True) or self.question_box_authorship(text)
                    or signing_place(text) or lexical)
        node, preceding = chosen.el.getprevious(), []
        while node is not None and node.tag == q('w:p') and len(preceding) < 3:
            slot = self.index.by_el.get(id(node))
            if not safe(slot) or self.ruled_paragraph_stop(slot) is not None:
                return None
            text = self.ptext(node)[0].strip()
            if text:
                break
            preceding.append(slot); node = node.getprevious()
        guidance = []
        if node is not None and node.tag == q('w:p'):
            slot = self.index.by_el.get(id(node)); text = self.ptext(node)[0].strip()
            if text.startswith('[') and text.endswith(']') and text.count('[') == text.count(']') == 1:
                if not safe(slot): return None
                guidance = [slot]; node = node.getprevious()
        question = self.index.by_el.get(id(node)) if node is not None else None
        if not safe(question): return None
        prompt = self.ptext(question.el)[0].strip()
        if (not prompt or ':' not in prompt and not self.question_box_request(prompt)
                or len(prompt) > MAX_MAPPING_LABEL or self.blank_spans(*self.ptext(question.el))
                or self.question_box_reference(prompt) or human(prompt)):
            return None
        lines, descriptors = [], []
        node = chosen.el
        while node is not None and node.tag == q('w:p'):
            slot = self.index.by_el.get(id(node)); stop = self.ruled_paragraph_stop(slot) if slot else None
            if stop is None:
                if slot is not None and (self.ptext(node)[0] == '\t'
                        or not self.ptext(node)[0].strip() and node.find('./' + q('w:pPr') + '/' + q('w:tabs')) is not None):
                    return None  # an inconsistent empty line cannot shorten the complete group
                break
            text = self.ptext(node)[0]
            if (not safe(slot) or stop != geometry or text not in ('', '\t') or len(descriptors) >= 100):
                return None
            if text == '\t': lines.append(slot)
            descriptors.append(ref(slot)); node = node.getnext()
        if len(lines) < 2:
            return None
        context = ' > '.join(value for value in (self.context_for(question, complete=True), prompt,
                            *[self.ptext(slot.el)[0].strip() for slot in guidance]) if value)
        governing_context, context_problem = self.question_box_context(question, require_visible=True)
        previous = self.previous_continuous_paragraph(question)
        source_readings = [prompt, governing_context, *[self.ptext(slot.el)[0].strip('[] \t\r\n') for slot in guidance]]
        if previous is not None:
            source_readings.append(self.ptext(previous.el)[0])
        source_readings = [clause.strip() for text in source_readings for clause in
                           [text, *re.split(r'(?<=[.;!?])\s*|[\r\n]+', text)] if clause.strip()]
        if (context_problem or len(context) > MAX_MAPPING_CONTEXT
                or any(human(value) for value in source_readings)):
            return None
        relation = {'relation': 'manual_ruled_paragraph_answer', 'question': prompt, 'source': ref(question),
                    'descriptors': descriptors, 'instructions': [ref(slot) for slot in guidance + preceding],
                    'definitions': {name: hashlib.sha256(self.package.zip.read(name)).hexdigest()
                                    for name in ('word/styles.xml',) if name in self.package.names}}
        return Area('long_text', prompt, lines[0], {'type': 'ruled_paragraphs'}, extra_slots=lines[1:],
                    context=context, complete_source=True, source_questions=[relation])

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
            self.coverage_issue(cell, 'unmapped_answer', self.notes[-1])

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
                defaults = self.default_source_styles(kind)
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

    def rule_lines_below_label(self, *, write_requests_only=False):
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
                if write_requests_only and not self.parenthetical_write_request(txt):
                    continue
                # A printed heading can contain its own digit, underline or
                # placeholder answer. That precise source blank owns the
                # response; following empty paragraphs are not its answer.
                if self.blank_spans(*self.ptext(ps.el)):
                    continue
                label = clean_label(txt)
                requested = self.parenthetical_write_request(txt)
                # A printed bullet ending in a colon can own a flowing answer
                # band. Its complete caption, rather than a word-count cutoff,
                # is the source; two plain empty paragraphs prove the band.
                narrative = (not in_container and txt.rstrip().endswith(":")
                             and (re.match(r"^[•●▪‣]\s+", txt) is not None
                                  or self.list_info(ps.el) is not None))
                props = ps.el.find(q('w:pPr'))
                band_style = fingerprint(props) if props is not None else ''
                if not requested and self.ptext(ps.el)[0].rstrip("\n").endswith("\t"):
                    continue  # the actual inline tab is already its answer gap
                cell = self.host_cell(ps)
                if (requested and cell is not None and not signing_place(clean_label(txt.partition('(')[0]))
                        and self.row_label(cell.parent, cell.info['row'], cell.info['col'])):
                    continue  # A row's option/write-in cannot become a separate unconditional request.
                signing = bool(SIGNATURE.search(label) or INITIALS.search(label) or re.match(r"^(?:date|printed name|name)\b", label, re.I))
                if in_container:
                    if not (requested or txt.endswith(":") or signing or self.is_heading(ps.el) and len(paras) > i + 1):
                        continue
                elif not (narrative or (signing or LONG_LABEL.search(label) and self.text(ps.el).rstrip("\n").endswith(":"))
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
                    props = nxt.el.find(q('w:pPr'))
                    if narrative and (fingerprint(props) if props is not None else '') != band_style:
                        break  # a style/spacing transition is a different layout band
                    blanks.append(nxt)
                    if not in_container and not narrative and len(blanks) >= 1:
                        break
                if not blanks:
                    continue
                if narrative and (len(blanks) < 2 or len(blanks) > 20
                                  or not self.insertion_source_plain(ps)
                                  or any(not self.plain_spacing_paragraph(b, unused_tab_stops=True)
                                         or not self.tab_source_visible(b) for b in blanks)):
                    if len(blanks) >= 2:
                        for source in [ps, *blanks]:
                            self.coverage_issue(source, 'unresolved_narrative_band',
                                'This printed caption and blank band have unresolved structure or visibility; '
                                'preserve them and review the exact source relationship.')
                    continue
                if requested and (not self.tab_source_visible(ps) or self.question_box_paragraph(ps.el)[2]
                                  or any(not self.plain_spacing_paragraph(b, unused_tab_stops=True) or not self.tab_source_visible(b)
                                         for b in blanks)):
                    continue
                if in_container and not requested and self.mapped_beside_label(ps) and all(self.plain_spacing_paragraph(b) for b in blanks):
                    continue
                head = clean_label(txt.partition('(')[0]) if requested else ''
                role = signing_place(head) if requested else ''
                action = self.checkbox_source_action(head, governing=True) if requested else ''
                kind = (role or ('long_text' if len(blanks) >= 2 else 'text')) if requested else \
                    ("long_text" if len(blanks) >= 2 and not signing else self.kind_for(label))
                relation = ({'relation': 'narrative_empty_band', 'question': self.ptext(ps.el)[0],
                             'source': {'part': ps.part, 'slot': ps.path, 'fingerprint': fingerprint(ps.el)}}
                            if narrative else self.write_request_source(ps) if requested else None)
                area = Area(kind, label, blanks[0], {"type": "paragraph"}, context=self.context_for(ps),
                            extra_slots=blanks[1:], label_slot=ps, complete_source=requested or narrative,
                            source_questions=[relation] if relation else [])
                if role or action:
                    area.source_action = True
                    area.protection = ('This printed signing or document action is human-owned. Complete it through the explicit human signing workflow.'
                                       if role or action == 'human_signing_action' else
                                       'This printed action does not establish who performs it. Keep it unchanged and review its precise source role.')
                self.add(area)
                self.claimed.add(id(ps.el))
                for b in blanks:
                    self.claimed.add(id(b.el))

    # 7. blanks and 'Label:' answers inside paragraphs ---------------------------------------------------------------
    def literal_reference_link(self, text, pieces, start, end):
        """A printed address equal to its hyperlink target is fixed reference ink."""
        links = {ancestor for piece in pieces if piece.run is not None
                 and piece.start < end and piece.end > start
                 for ancestor in piece.run.iterancestors() if ancestor.tag == q('w:hyperlink')}
        if len(links) != 1:return False
        link = next(iter(links)); shown = ''.join(link.itertext()).strip()
        if shown != text[start:end].strip():return False
        paragraph = next((a for a in link.iterancestors() if a.tag == q('w:p')), None)
        slot = self.index.by_el.get(id(paragraph)) if paragraph is not None else None
        if slot is None:return False
        parent, name = slot.part.rsplit('/', 1)
        rels = parent + '/_rels/' + name + '.rels'
        if rels not in self.package.names:return False
        target = next((r.get('Target') for r in self.package.tree(rels)
                       if r.get('Id') == link.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                       and r.get('TargetMode') == 'External'
                       and (r.get('Type') or '').endswith('/hyperlink')), None)
        return ((target == 'mailto:' + shown and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', shown) is not None)
                or (target == shown and shown.startswith(('https://', 'http://'))))

    def blank_spans(self, text, pieces):
        spans = []
        unresolved=[]
        # Printed slash-separated parts are alternatives, irrespective of their
        # punctuation, script, digits, empty parts or line breaks. A leading
        # verb does not prove an authoring role: [type A/type B] is a menu.
        # Only the existing explicit date-format hint is a slash placeholder.
        for match in re.finditer(r'\[([^\[\]]+)\]',text):
            inner=match.group(1).strip()
            parts=inner.split('/')
            if (len(parts)>1 and
                    not re.fullmatch(r'(?:dd|mm|yy|yyyy)(?:[^\S\r\n]*/[^\S\r\n]*(?:dd|mm|yy|yyyy))+',inner,re.I)):
                unresolved.append((match.start(),match.end(),'printed_bracket_alternatives',
                    'Bracketed printed alternatives cannot take arbitrary generated text. Their role and exact '
                    'choice interpretation need review; this source range remains unchanged: '+match.group(0)))
        # An unmatched opening ends at the next opening or paragraph end. A
        # later closed placeholder cannot close or hide this earlier range.
        for match in re.finditer(r'\[[^\[\]]*/[^\[\]]*(?=\[|$)',text):
            unresolved.append((match.start(),match.end(),'unbalanced_bracketed_source',
                'This slash-bearing source range has no closing bracket. Its answer or authoring role is unresolved; '
                'preserve the exact text and review it before generation: '+match.group(0)))
        # A long marked range is outside the qualified placeholder grammar. Its
        # physical presence cannot be silently omitted because of the 120 limit.
        for match in re.finditer(r'\[[^\[\]]+\]',text):
            if len(match.group(0))<=122 and '\n' not in match.group(0):continue
            if any(start==match.start() and end==match.end() for start,end,_,_ in unresolved):continue
            unresolved.append((match.start(),match.end(),'unmapped_bracketed_source',
                'This long bracketed source range exceeds the qualified placeholder grammar. Its authoring or '
                'answer role is unresolved; preserve the exact text and review it before generation: '+match.group(0)))
        slot=next((self.index.by_el.get(id(ancestor)) for pc in pieces if pc.run is not None
                   for ancestor in pc.run.iterancestors() if ancestor.tag==q('w:p')),None)
        for start,end,code,detail in unresolved:
            if slot is not None:
                self.coverage_issue(slot,code,detail,start=start,end=end)
                if detail not in self.notes:self.notes.append(detail)
        for rx, kind in ((SEGMENTED, "segmented"), (DIGIT_RUN, "segmented"), (UNDERSCORES, "blank"), (DOTS, "blank"), (TOKEN, "token"), (BRACKET, "bracket"), (ANGLE, "angle")):
            for m in rx.finditer(text):
                if kind=='bracket' and any(start<=m.start() and m.end()<=end for start,end,_,_ in unresolved):
                    continue
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
            if any(start < stop and end > begin for begin, stop, _, _ in unresolved):
                continue
            if hyperlink_write(pieces, start, end):
                owner = next((ancestor for pc in pieces if pc.run is not None
                              for ancestor in pc.run.iterancestors() if ancestor.tag == q("w:p")), None)
                slot = self.index.by_el.get(id(owner)) if owner is not None else None
                note = "Answer-like text inside a fixed hyperlink was kept unchanged; review the original."
                if slot is not None:
                    note += " Location: " + slot.id
                if note not in self.notes:
                    self.notes.append(note)
                if slot is not None and not (kind == 'hint' and self.literal_reference_link(text, pieces, start, end)):
                    self.coverage_issue(slot, 'fixed_link_answer', note, start=start, end=end)
            else:
                kept.append((start, end, kind))
        return kept

    @classmethod
    def temporal_source_action(cls, argument):
        # A temporal modifier can qualify coordinated events. Each complete
        # clause keeps its own actor/predicate/argument reading: recording an
        # observation does not release a subsequent approval or appointed
        # response. Ordinary coordinated recorded states are still ordinary.
        clauses = [argument, *re.split(r'(?:\s+|,\s*)(?:and|or|but)\s+', argument, flags=re.I)]
        return any(cls.checkbox_source_action(clause, governing=True)
                   or cls.question_box_authorship(clause) or signing_place(clause)
                   for clause in clauses if clause.strip())

    def temporal_band(self, slot):
        """One caption, one divided blank and its own printed date-format guide.

        The format's character positions appoint the blank runs, rather than
        turning every run and separator into a separate question. All three
        paragraphs must be immediate siblings in the same physical container.
        """
        siblings, at = self.para_neighbours(slot)
        if at is None or at == 0 or at + 1 >= len(siblings):
            return None
        caption, guide = siblings[at - 1], siblings[at + 1]
        if caption.el.getnext() is not slot.el or slot.el.getnext() is not guide.el:
            return None
        sources = (caption, slot, guide)
        if (any(s.part != slot.part or s.parent is not slot.parent for s in sources)
                or any(not self.tab_source_visible(s) or self.region_hidden(s.el) or wraps_structure(s.el)
                       for s in sources)
                or any(n.tag in (q('w:hyperlink'), q('w:drawing'), q('w:pict'), q('w:object'), TXBX)
                       for s in sources for n in s.el.iter())):
            return None
        label = self.ptext(caption.el)[0].strip()
        pattern = re.sub(r'\s+', '', self.ptext(guide.el)[0]).lower()
        if (pattern not in ('ddmmmyyyy', 'ddmmyyyy', 'mmddyyyy', 'yyyymmdd')
                or not re.fullmatch(r'[^:;.!?\r\n]+:', label)
                or not DATE_LABEL.search(label) or self.blank_spans(*self.ptext(caption.el))):
            return None
        text, pieces = self.ptext(slot.el)
        spans = self.blank_spans(text, pieces)
        if (len(spans) != len(pattern) or any(kind != 'utab' for _, _, kind in spans)
                or any(text[start:end].strip() for start, end, _ in spans)):
            return None
        outside = ''.join(ch for n, ch in enumerate(text)
                          if not any(start <= n < end for start, end, _ in spans))
        # Only the date's two printed separators and optional fixed terminal
        # punctuation surround these runs. Existing values are never blanks.
        if re.sub(r'\s+', '', outside).rstrip('.') != '//':
            return None
        groups = re.findall(r'd+|m+|y+', pattern)
        boundaries = {len(groups[0]), len(groups[0]) + len(groups[1])}
        if any(text[spans[n - 1][1]:spans[n][0]].strip() != ('/' if n in boundaries else '')
               for n in range(1, len(spans))):
            return None
        if self.box_units(slot) or len(label) > MAX_MAPPING_LABEL:
            return None
        context = self.context_for(caption, complete=True)
        if len(context) > MAX_MAPPING_CONTEXT:
            return None
        refs = [{'part': s.part, 'slot': s.path, 'fingerprint': fingerprint(s.el)} for s in sources]
        target = {'type': 'span', 'shape': 'temporal_band', 'start': spans[0][0], 'end': spans[-1][1],
                  'parts': [[start, end] for start, end, _ in spans], 'format': pattern,
                  'caption': refs[0], 'guide': refs[2]}
        area = Area('date', clean_label(label), slot, target, context=context,
                    complete_source=True, label_slot=caption)
        if self.temporal_source_action(label) or self.kind_for(label) in SIGNING_KINDS:
            area.source_action = True
            area.protection = 'This date belongs to a printed human signing or authored act; keep it unchanged.'
        return area

    def rule_temporal_bands(self):
        for slot in (s for s in self.index.slots if s.kind == 'p'):
            area = self.temporal_band(slot)
            if area is None:
                continue
            siblings, at = self.para_neighbours(slot)
            sources = siblings[at - 1:at + 2]
            if any(id(s.el) in self.claimed for s in sources):
                continue
            self.add(area)
            self.claimed.update(id(s.el) for s in sources)
            if area.protection:
                self.coverage_issue(slot, 'human_signing_action', area.protection)

    def rule_temporal_format_pairs(self):
        """Two complete format paragraphs under their own aligned temporal caption.

        Native clock controls can already own the surrounding cell, and their
        preceding time hint can already be claimed as a label. Neither owns the
        distinct date/time paragraph's ink. Do not change the existing clock
        mapping or infer a field from a partial hint or neighboring caption.
        """
        date_format = re.compile(r'(?:MM/DD/YYYY|DD/MM/YYYY)', re.I)
        time_format = re.compile(r':?\(HH:MM\)', re.I)
        for cell in (s for s in self.index.slots if s.kind == 'tc' and s.part == 'word/document.xml'):
            if cell.info['span'] != 1 or cell.info['vmerge']:
                continue
            paragraphs = self.own_paragraphs(cell)
            if (len(paragraphs) not in (2, 3) or len(paragraphs) != len(cell.children)
                    or not date_format.fullmatch(self.ptext(paragraphs[0].el)[0].strip())
                    or not time_format.fullmatch(self.ptext(paragraphs[1].el)[0].strip())):
                continue
            if len(paragraphs) == 3:
                units = self.box_units(paragraphs[2])
                if (len(units) != 3 or units[0][2].strip()
                        or [option_text(u[1]).casefold() for u in units] != ['am', 'pm', '24-hr clock']):
                    continue
            row, col = cell.info['row'], cell.info['col']
            above = [c for c in self.grid(cell.parent).get(row - 1, [])
                     if c.info['col'] <= col < c.info['col'] + c.info['span']]
            if len(above) != 1:
                continue
            header = above[0]
            captions = self.own_paragraphs(header)
            if (header.info['col'] != col or header.info['span'] != 1 or header.info['vmerge']
                    or len(captions) != 1 or len(header.children) != 1):
                continue
            caption = captions[0]; printed, pieces = self.ptext(caption.el)
            if (not printed.strip().endswith(':') or not DATE_LABEL.search(printed)
                    or not TIME_LABEL.search(printed) or self.blank_spans(printed, pieces)
                    or self.box_units(caption) or wraps_structure(caption.el) or len(printed.strip()) > MAX_MAPPING_LABEL
                    or self.column_header(cell.parent, col, row, complete=True) != self.cell_text(header)):
                continue
            if not re.fullmatch(r'[^:;.!?\r\n]+:', printed.strip()):
                # Several clauses/captions in this one cell do not appoint one
                # unambiguous temporal question. Keep the complete source and
                # expose the omission rather than borrowing the first caption.
                clauses = [printed, *re.split(r'(?<=[.;!?])\s*|[:\r\n]+', printed)]
                human = any(self.checkbox_source_action(clause.strip(), governing=True)
                            or signing_place(clause) for clause in clauses if clause.strip())
                for paragraph in paragraphs[:2]:
                    self.coverage_issue(paragraph, 'unmapped_answer',
                        'The date/time format has competing printed captions or clauses. Review the complete '
                        'source question and its exact answer area; no temporal ownership was inferred.')
                    if human:
                        self.protected_regions.add(paragraph.id)
                continue
            sources = [caption, *paragraphs]
            if (not all(self.tab_source_visible(p) and not self.region_hidden(p.el) for p in sources)
                    or any(n.tag in (q('w:hyperlink'), q('w:drawing'), q('w:pict'), q('w:object'), TXBX)
                           for p in sources for n in p.el.iter())
                    or any(wraps_structure(p.el) for p in paragraphs[:2])
                    or any(area.slot is p or p in area.extra_slots for area in self.areas for p in paragraphs[:2])):
                continue
            context = self.context_for(caption, complete=True)
            if len(context) > MAX_MAPPING_CONTEXT:
                continue
            nominal = re.fullmatch(r'date\s+and\s+time(?:\s+(.+))?', printed.strip()[:-1].strip(), re.I)
            trailing = re.fullmatch(r'(.+?)\s+date\s+and\s+time', printed.strip()[:-1].strip(), re.I)
            if nominal is None and trailing is None:
                continue
            argument = (nominal[1] or '') if nominal is not None else trailing[1]
            # The temporal noun modifies a complete event/author argument; it
            # does not convert that person's signing, approval or statement
            # into an ordinary clinical field. Use the established source
            # predicates on that argument and retain the complete original.
            human = self.temporal_source_action(argument)
            refs = [{'part': p.part, 'slot': p.path, 'fingerprint': fingerprint(p.el)} for p in sources]
            for kind, paragraph in zip(('date', 'time'), paragraphs[:2]):
                text, _ = self.ptext(paragraph.el)
                relation = {'relation': 'temporal_format_hint', 'question': printed.strip(),
                            'format': text, 'component': kind, 'argument': argument, 'sources': refs}
                area = Area(kind, clean_label(printed) + ' — ' + kind.capitalize(), paragraph,
                    {'type': 'span', 'start': 0, 'end': len(text), 'shape': 'format_hint'},
                    context=context, complete_source=True, label_slot=caption, source_questions=[relation])
                if human:
                    area.source_action = True
                    area.protection = ('The printed temporal question belongs to a human signing or authored act. '
                                       'Keep it unchanged and use the explicit human workflow.')
                    self.coverage_issue(paragraph, 'human_signing_action', area.protection)
                self.add(area)

    def insertion_source_plain(self, slot):
        """An insertion's printed source has no control, wrapper or foreign ink."""
        unsafe = {SDT, FLDCHAR, q('w:instrText'), q('w:hyperlink'), TXBX, q('w:drawing'),
                  q('w:pict'), q('w:object'), q('w:customXml'), q('w:ins'), q('w:del'),
                  q('w:moveFrom'), q('w:moveTo'), q('w:sectPr'), q('w:br')}
        return (slot.parent is None and slot.el.getparent() is not None
                and slot.el.getparent().tag == q('w:body')
                and not any(not isinstance(node.tag, str) or node.tag in unsafe
                            or not node.tag.startswith('{' + W + '}') for node in slot.el.iter())
                and self.tab_source_visible(slot))

    def explicit_insertion_spans(self, slot, text, pieces):
        """Read explicit authoring slots, retaining their complete printed request.

        Single braces require an insertion verb. They do not turn arbitrary
        brace prose or printed choice menus into scalar answers. A whole-line
        insertion also needs the explicit destination word 'here'.
        """
        candidates = [(m.start(), m.end(), m.group(1).strip(), False)
                      for m in re.finditer(r'(?<!\{)\{([^{}\r\n]+)\}(?!\})', text)]
        whole = re.fullmatch(r'\s*(?:insert|enter|type|add|specify)\s+(.{1,160}?)\s+here\s*[.]?\s*', text, re.I)
        if whole:
            candidates.append((len(text) - len(text.lstrip()), len(text.rstrip()),
                               text.strip().rstrip('.'), True))
        spans = []
        for opening in re.finditer(r'(?<!\{)\{(?:insert|enter|type|add|specify)\b', text, re.I):
            if not any(start == opening.start() for start, _, _, _ in candidates):
                self.coverage_issue(slot, 'unresolved_insertion_source',
                    'This explicit insertion has unmatched or nested delimiters; preserve its original source.',
                    start=opening.start(), end=len(text))
        for start, end, printed, full in candidates:
            request = re.fullmatch(r'(?:insert|enter|type|add|specify)\s+([^{}\[\]<>;?!\r\n]{1,160})', printed, re.I)
            if not request:
                if re.match(r'^(?:insert|enter|type|add|specify)\b', printed, re.I):
                    self.coverage_issue(slot, 'unresolved_insertion_source',
                        'This explicit insertion exceeds the supported request grammar; preserve its exact source.',
                        start=start, end=end)
                continue
            argument = request[1].strip()
            if full:
                argument = re.sub(r'\s+here$', '', argument, flags=re.I)
            # A slash between author descriptors can qualify one scalar
            # identifier ('provider/plan telephone number'). A slash-only
            # menu, a selection instruction or competing alternatives cannot.
            slash_scalar = re.fullmatch(r'[\w-]+/[\w-]+\s+(?:[\w-]+\s+){0,8}(?:number|address|identifier)', argument, re.I)
            enclosed = any(m.start() < start and end < m.end()
                           for m in re.finditer(r'\[[^\[\]\r\n]*\]', text))
            alternatives = any(start in (m.start('left'), m.start('right'))
                               for m in re.finditer(r'(?=(?P<left>\{[^{}\r\n]+\})\s+or\s+'
                                                    r'(?P<right>\{[^{}\r\n]+\}))', text, re.I))
            ambiguous = (OPTION_SELECTION.search(argument) or re.search(r'\b(?:or|either|neither)\b', argument, re.I)
                         or '/' in argument and not slash_scalar or ':' in argument or ',' in argument
                         or enclosed or alternatives)
            if (ambiguous or not self.insertion_source_plain(slot)
                    or hyperlink_write(pieces, start, end)):
                self.coverage_issue(slot, 'unresolved_insertion_source',
                    'This explicit insertion needs review of its exact source role or alternatives; preserve it unchanged: '
                    + text[start:end], start=start, end=end)
                continue
            spans.append((start, end, 'insertion'))
        return spans

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
            spans = merge_spans(self.explicit_insertion_spans(slot, text, pieces)
                                + self.blank_spans(text, pieces))
            residue = "".join(ch for i, ch in enumerate(text) if not any(s <= i < e for s, e, _ in spans))
            named_placeholder = (len(spans) == 1 and (spans[0][2] in ('insertion', 'token', 'bracket', 'angle')
                                 or spans[0][2] == 'hint' and not PLACEHOLDER_TEXT.fullmatch(text[spans[0][0]:spans[0][1]].strip())))
            if len(spans) == 1 and spans[0][2] != 'insertion' and not clean_label(residue.replace("_", "")):
                # a line that is ONLY a drawn blank: continues the previous line's area, or takes the label above
                sibs, idx = self.para_neighbours(slot)
                prev_sib = sibs[idx - 1] if idx else None
                prior_human = (pending is not None and (pending.kind in SIGNING_KINDS or pending.protection
                               or self.question_box_authorship(pending.label)
                               or self.checkbox_source_action(pending.label, governing=True)))
                if pending is not None and prev_sib is pending_last and (not named_placeholder or prior_human):
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
                if not label and spans[0][2] in ("angle", "bracket", "token", "insertion"):
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
            label_ink = m.start(1) + len(m.group(1)) - len(m.group(1).lstrip())
            # The next caption's regex can include the preceding answer's
            # plain-space gap. Only printed caption ink overlaps that answer;
            # its leading whitespace is not part of the question. A unit
            # after the previous gap still belongs to that previous answer,
            # so do not newly reinterpret a unit-prefixed run as a caption.
            if (any(s <= label_ink < e or s <= end - 1 < e for s, e, _ in blanks)
                    or any(s <= m.start() < e for s, e, _ in blanks)
                    and self.ANSWER_UNIT.match(text[label_ink:end - 1])):
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
                self.coverage_issue(slot, 'unmapped_answer', self.notes[-1])
                continue
            seg = text[prev_end:s]
            seg = re.split(r"[\x00" + BOX + CHECKED + "]", seg)[-1]
            seg = re.split(r"(?<=[.;!?])\s+(?=[A-Z(])", seg.strip())[-1]
            label = clean_label(seg)
            if kind == 'insertion':
                argument = re.sub(r'^(?:insert|enter|type|add|specify)\s+', '',
                                  text[s:e].strip('{} ').rstrip('.'), flags=re.I)
                argument = re.sub(r'\s+here$', '', argument, flags=re.I)
                label = clean_label(argument)
                whole = not text[:s].strip() and not text[e:].strip()
                relation = {'relation': 'explicit_insertion', 'question': text,
                            'request': text[s:e], 'source': {'part': slot.part, 'slot': slot.path,
                                                           'fingerprint': fingerprint(slot.el)}}
                physical_kind = self.kind_for(clean_label(seg)) if SIGNATURE.search(seg) or INITIALS.search(seg) else ''
                self.add(Area(physical_kind or ('long_text' if whole else self.kind_for(label)), label, slot,
                              {'type': 'span', 'start': s, 'end': e, 'shape': kind},
                              context=self.context_for(slot), complete_source=True,
                              source_questions=[relation]))
                made += 1
                prev_end = e
                continue
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
                self.coverage_issue(c, 'unmapped_answer', self.notes[-1])
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
            self.coverage_issue(table, 'unmapped_answer', self.notes[-1])
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
    # A checkbox group's claim must not hide separate writable blanks on its
    # paragraph (for example two distinct write-ins after the last option).
    # These are excluded extents, never two inferred fields or option decisions.
    reader = _PlaceReader(detector.index)
    writes = [place for field in fields for place in reader.of(field)]
    for slot in detector.index.slots:
        if slot.kind != 'p' or not detector.box_units(slot):
            continue
        for start, end, _ in detector.blank_spans(*detector.ptext(slot.el)):
            region = {'place': slot.id, 'start': start, 'end': end}
            if not any(reader.touches(place, region) for place in writes):
                detail = 'A separate checkbox write-in has no mapped writer at ' + slot.id + ' offsets ' + str(start) + '-' + str(end) + '. It remains unchanged; review this exact exclusion.'
                detector.coverage_issue(slot, 'unmapped_checkbox_write_in', detail, start=start, end=end)
                if detail not in notes:notes.append(detail)
    return {"contract": CONTRACT, "fields": fields, "notes": notes,
            "coverage_issues": detector.coverage_issues,
            "layout_quarantine": detector.layout_quarantine,
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
        if typ in ("paragraph", "ruled_paragraphs"):
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


def _role_reading(package, *, retained_areas=None):
    """(roles, the engine's own option groups as box keys - the boxes one engine choice area answers together)."""
    detector = Detector(package)
    detected, _ = detector.detect()
    # ⚠️ The areas EC3 withdrew from shared merged cells take part as before (refutation of c1cae13d, P-1): a signing
    # segment is bounded by every engine area of its paragraph, and an attestation role comes from an engine field, so
    # without them a withdrawal moved a neighbouring signing role over the withdrawn place.
    areas = list(detected) + list(detector.withdrawn_areas)
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
        if area.protection and area.source_action:
            for pid, start, end in _extent(reader, field):
                if start is not None:
                    start, end = segment(pid, start, end, field['key'])
                roles.append(_role(ROLE_PROTECTED, 'human_document_action', pid, start, end, area.protection))
        elif area.protection:
            for pid in dict.fromkeys([anchor] + [pid for pid, _, _ in places]):
                roles.append(_role(ROLE_PROTECTED, "protected_area", pid, None, None, area.protection))
        elif area.kind in SIGNING_KINDS:
            if not area.structural and detector.kind_for(area.label) == area.kind and not signing_place(area.label):
                # The kind rule's reading of a clinical reading or a checklist state ('Initial GCS', 'Consent form
                # signed'): never generated, but not a role - the clinician may replace it with the answer it asks.
                continue
            for pid, start, end in places:
                if start is None:
                    roles.append(_role(ROLE_SIGNING, "signing_area", pid, None, None, signing))
                    line_role(ROLE_SIGNING, "signing_area", index.by_id.get(pid), signing, field["key"])
                    continue
                low, high = segment(pid, start, end, field["key"])
                roles.append(_role(ROLE_SIGNING, "signing_area", pid, low, high, signing))
                # A caption with no blank of its own ('Consultant signature:') is signed on the writing line under it.
                pslot = index.by_id.get(pid)
                if pslot is not None and pslot.kind == "p" and not reader.text(pslot)[0][start:].strip():
                    after = pslot.el.getnext()
                    below = index.by_el.get(id(after)) if after is not None else None
                    if below is not None and below.kind == "p" and below.parent is pslot.parent \
                            and _writing_line(reader.text(below)[0]):
                        roles.append(_role(ROLE_SIGNING, "signing_line", below.id, None, None, signing))
            if area.label_slot is not None:
                # The caption paragraph the engine read this writing line's label from belongs to the same place.
                roles.append(_role(ROLE_SIGNING, "signing_caption", area.label_slot.id, None, None, signing))
    for region in sorted(detector.protected_regions):
        roles.append(_role(ROLE_PROTECTED, "protected_region", region, None, None, ROLE_REGION))
    for table in index.roots:
        # A one-cell box whose printed question or section reads as signing or consent is a signing box, whatever it
        # prints. The answer areas the engine maps INSIDE it (a frame holding 'Presenting complaint: ____') are excepted:
        # each carries its own role, and the rest of the box stays the box's. A box the engine maps AS an answer is one
        # its own (broader) signing reading let through, so it is no signing box.
        cells = [c for c in table.children if c.kind == "tc"] if table.kind == "tbl" else []
        if len(cells) != 1 or len(table_rows_of(table.el)) != 1:
            continue
        cell = cells[0]
        if cell.id in engine_places:
            continue
        question, section = detector.question_box_role_source(table)
        if signing_box_reading(question) or signing_box_reading(section):
            role = _role(ROLE_SIGNING, "question_box_signing", cell.id, None, None, ROLE_SIGNING_BOX)
            inside = sorted(pid for pid in engine_places if pid.startswith(cell.id + "/"))
            if inside:
                role["except"] = inside
            roles.append(role)
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
    if retained_areas is not None:
        # Only this fresh ordinary detector's retained areas, before any write.
        # The shared-merged withdrawals above remain role boundaries, but were
        # never eligible relation owners in the separate ordinary detection.
        retained_areas.extend(detected)
    return roles, [group for group in choices if group]


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


def destination_roles(data: bytes, fields=None) -> dict:
    """The role report of an original: its roles (class, source, place, span) and, for `fields` (any mapping), every
    field whose writes touch a role place it may not take. Read-only; the isolated parser's 'roles' operation."""
    package = open_package(data)
    roles, choices = _role_reading(package)
    reader = _PlaceReader(SlotIndex(package))
    return {"contract": CONTRACT,
            "roles": [{k: v for k, v in r.items() if k != "requires"} for r in roles],
            "violations": role_violations(reader, fields or [], roles), "choices": choices}


def writing_places(data, fields):
    """The stored v3 writer's exact destinations, read only from this original.

    Consumers compare these sandbox-derived coordinates without parsing the
    original themselves. An inline native control therefore carries its exact
    containing-paragraph extent, as a glyph does. Unknown, block and empty
    extents retain the conservative whole-slot representation.
    """
    reader = _PlaceReader(SlotIndex(open_package(data)))
    places = {}
    for field in fields:
        resolved = []
        for pid, start, end in reader.of(field):
            slot = reader.index.by_id.get(pid)
            if start is None and end is None and slot is not None and slot.kind in ('sdt', 'ff') \
                    and slot.parent is not None:
                extent = reader.inline(slot.parent.id, pid)
                if extent is not None and extent[0] < extent[1]:
                    resolved.append((slot.parent.id, *extent))
                    continue
            resolved.append((pid, start, end))
        places[field['key']] = resolved
    return places


def reconcile_layout_coverage(data, fields, issues, qualified):
    """Resolve only first-route tab withdrawals through measured coded sources.

    The renderer supplies the exact receipt for each proof-backed candidate.
    Other withdrawal causes never clear merely because a writer overlaps them.
    Uncovered visible boxes/blanks retain exact extents and the full source note.
    """
    detector = Detector(open_package(data))
    reader = _PlaceReader(detector.index)
    proven = [field for field in fields
              if field.get('layout_candidate') in qualified
              and field.get('layout_verified') == qualified[field['layout_candidate']]
              and field.get('locator', {}).get('target', {}).get('column_sequence')]
    box_writes = {place for field in proven for place in reader.of(field)}
    blank_writes = {place for field in fields
                    if field.get('locator', {}).get('target', {}).get('type') == 'span'
                    and not field.get('write_protected') and field.get('kind') not in SIGNING_KINDS
                    for place in reader.of(field)}
    remaining, resolved = [], []
    for issue in issues:
        root = _place_id(issue['part'], issue['slot'])
        if issue['code'] not in ('tab_column_withdrawal', 'coded_checkbox_withdrawal') or not any(
                field['locator']['part'] == issue['part']
                and (field['locator']['slot'] == issue['slot']
                     or field['locator']['slot'].startswith(issue['slot'] + '/')) for field in proven):
            remaining.append(issue);continue
        expected = []
        for slot in detector.index.slots:
            if slot.kind != 'p' or not (slot.id == root or slot.id.startswith(root + '/')):
                continue
            for ref, _, _ in detector.box_units(slot):
                location = {'part': slot.part, 'slot': slot.path, 'target': {'type': 'checkboxes', 'boxes': [ref]}}
                for place in reader.of({'locator': location}):
                    expected.append((place, box_writes))
            text, pieces = detector.ptext(slot.el)
            for start, end, _ in detector.blank_spans(text, pieces):
                own = [field['locator']['target']['column_sequence']['source'][-1] for field in proven
                       if _place_id(field['locator']['part'],field['locator']['slot']) == slot.id]
                if text[start:end] and not text[start:end].strip('.') and any(
                        len(ref['starts']) > 1 and end <= ref['starts'][1] for ref in own):
                    continue  # fixed dot leader in the measured complete question column
                expected.append(((slot.id, start, end), blank_writes))
        if not expected:
            remaining.append(issue);continue
        missing = [place for place, actual in expected if place not in actual]
        if not missing:
            resolved.append(issue);continue
        for place, start, end in missing:
            part, path = place.split('#', 1)
            detail = 'An answer extent remains unresolved after measured coded-column mapping. ' + issue['detail']
            item = {'part': part, 'slot': path, 'code': 'unmapped_tab_extent', 'detail': detail,
                    'parent_issue': issue['id']}
            if start is not None:item.update(start=start,end=end)
            item['id'] = hashlib.sha256(repr((part,path,start,end,issue['id'])).encode()).hexdigest()
            remaining.append(item)
    return {'coverage_issues': remaining, 'resolved_tab_routes': resolved}


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


def qualified_signing_role(label) -> str:
    """A temporal qualifier cannot erase the person qualified by a signing caption.

    A complete date-only parenthetical still asks for a date. A signature or
    initials caption whose parenthetical also qualifies a signer remains that
    person's human destination, without enumerating relationships or titles.
    """
    text = _plain(label)
    head, separator, qualifier = text.partition('(')
    if not separator or not DATE_LABEL.search(qualifier):
        return ''
    role = signing_place(head)
    if not role:
        return ''
    match = re.fullmatch(r'([^()]*)\)\s*[:.]?', qualifier)
    if match is None:
        return role  # unresolved/nested qualification cannot become an ordinary date
    remainder = DATE_LABEL.sub(' ', match[1])
    remainder = re.sub(r'\b(?:of\s+birth|time|day|and|or)\b', ' ', remainder)
    return role if re.sub(r'[\s.,;:/&+\-]+', '', remainder) else ''


def signing_place(label) -> str:
    """'signature', 'initials' or '' for a PRINTED label (see the section comment above)."""
    text = _plain(label)
    if not text:
        return ""
    qualified = qualified_signing_role(text)
    if qualified:
        return qualified
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


def legacy_role_kind(label) -> str:
    """The legacy default path's role for a field's PRINTED label: the v3 rule for a labelled area - the engine's kind
    rule types it signature or initials AND signing_place names a signing place - so the legacy path never holds a
    label the v3 path generates. Returns the kind rule's kind, or ''.

    ⚠️ signing_place ALONE (refutation of 258650f2, L1:R1-04 and PC05) held labels the kind rule reads as text - 'Tinel
    sign both wrists', 'Sign and symptom review' - which 43fcf214 generated on legacy and every tree generates on v3.
    The design (matrix L02: 'Sign below', 'Sign and print name', 'Nurse sign' are text to the kind rule, LEAVE) never
    gave the legacy path a reader wider than the engine's own; declared residual, as on v3 (L1:RR1-11)."""
    text = _plain(label)
    kind = Detector.kind_for(None, text)
    return kind if kind in SIGNING_KINDS and signing_place(text) else ""


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
    # Inline spans inherit their table row's clipping just as whole-cell
    # answers do. Expanding the paragraph alone leaves an exact-height row
    # clipping long text and overprinting the following fixed content.
    cell=next((a for a in p.iterancestors() if a.tag==q('w:tc')),None)
    if cell is not None:
        _unclip_row(cell)
    return True


def temporal_band_characters(answer, pattern):
    """An explicit date, rendered in the original's printed format positions."""
    months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
    value = str(answer).strip()
    iso = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', value)
    try:
        if iso:
            year, month, day = (int(part) for part in iso.groups())
        else:
            orders = {'ddmmmyyyy': ('dd', 'mmm', 'yyyy'), 'ddmmyyyy': ('dd', 'mm', 'yyyy'),
                      'mmddyyyy': ('mm', 'dd', 'yyyy'), 'yyyymmdd': ('yyyy', 'mm', 'dd')}
            order = orders[pattern]
            widths = {'dd': r'\d{2}', 'mm': r'\d{2}', 'mmm': r'[A-Za-z]{3}', 'yyyy': r'\d{4}'}
            match = re.fullmatch(r'\s*/\s*'.join('(' + widths[part] + ')' for part in order), value)
            if match is None:
                raise ValueError
            parts = dict(zip(order, match.groups()))
            year, day = int(parts['yyyy']), int(parts['dd'])
            month = (next(n for n, word in enumerate(months, 1) if word.lower() == parts['mmm'].lower())
                     if 'mmm' in parts else int(parts['mm']))
        date(year, month, day)
    except (ValueError, KeyError, StopIteration):
        fail('This divided date needs a real YYYY-MM-DD value or its exact printed slash-separated format.',
             'invalid_answer')
    parts = {'dd': '%02d' % day, 'mm': '%02d' % month, 'mmm': months[month - 1], 'yyyy': '%04d' % year}
    order = {'ddmmmyyyy': ('dd', 'mmm', 'yyyy'), 'ddmmyyyy': ('dd', 'mm', 'yyyy'),
             'mmddyyyy': ('mm', 'dd', 'yyyy'), 'yyyymmdd': ('yyyy', 'mm', 'dd')}
    return ''.join(parts[part] for part in order[pattern])


def temporal_band_printed_value(answer, pattern):
    """The one calendar-valid date's literal source-appointed component order."""
    characters = temporal_band_characters(answer, pattern)
    values, start = [], 0
    for part in re.findall(r'd+|m+|y+', pattern):
        values.append(characters[start:start + len(part)]); start += len(part)
    return '/'.join(values)


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
    fc = begin_run.find(FLDCHAR)
    data = fc.find(q("w:ffData")) if fc is not None else None
    boxes = data.findall(q("w:checkBox")) if data is not None else []
    if len(boxes) != 1:
        fail("A stored checkbox is no longer one legacy checkbox.", "mapping_mismatch")
    cb = boxes[0]
    checked_nodes, defaults = cb.findall(q("w:checked")), cb.findall(q("w:default"))
    if (len(checked_nodes) > 1 or len(defaults) > 1
            or any(node.get(q("w:val")) not in (None, "1", "true", "on", "0", "false", "off")
                   for node in [*checked_nodes, *defaults])):
        fail("The original legacy checkbox has an unreadable checked/default state. Keep it unchanged and review the form.",
             "unsupported_layout")
    # Word reads the explicit state before the default. Preserve the exact
    # original representation when that effective state already agrees; a
    # reviewed blank must not materialize a new zero in an unticked field.
    if ff_checkbox_state(begin_run) is bool(ticked):
        return False
    for x in checked_nodes:
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


def paired_colon_areas(detector, identity):
    """Complete ordinary insertion spans sharing one original plain paragraph.

    This is the existing paragraph compiler's exact result, not a second caption
    grammar or authority derived from a stored field. Mixed controls, drawn
    blanks and protected acts remain outside this finite reading.
    """
    slot = detector.index.by_id.get(identity)
    if slot is None or slot.kind != 'p':
        return []
    areas = [area for area in detector.areas if area.slot.id == identity]
    if len(areas) < 2 or any(area.target.get('type') != 'span'
            or area.target.get('shape') != 'after_label' or area.protection
            or area.extra_slots or area.source_questions or area.options for area in areas):
        return []
    source, pieces = paragraph_text(slot.el)
    if ('\x00' in source or any(piece.kind not in ('t', 'tab', 'br') for piece in pieces)
            or not detector.tab_source_visible(slot) or detector.region_hidden(slot.el)):
        return []
    areas = sorted(areas, key=lambda area: area.target['start'])
    previous = -1
    for area in areas:
        start, end = area.target.get('start'), area.target.get('end')
        if (type(start) is not int or type(end) is not int
                or not 0 < start <= end <= len(source) or start <= previous
                or source[start - 1] != ':' or source[start:end].strip()
                or hyperlink_write(pieces, start, start)):
            return []
        previous = end
    return areas


def exact_paired_colon_field(field, area):
    """Original physical and semantic binding; keys and manual origin grant nothing."""
    loc = field.get('locator') or {}
    return (loc.get('part') == area.slot.part and loc.get('slot') == area.slot.path
            and loc.get('fingerprint') == fingerprint(area.slot.el)
            and not loc.get('extra') and not loc.get('target', {}).get('copies')
            and loc.get('target') == area.target and field.get('kind') == area.kind
            and field.get('label') == area.label and field.get('context') == area.context
            and field.get('options', []) == area.options
            and field.get('source_questions', []) == area.source_questions)


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
    relation_areas = []
    original_roles = _role_reading(package, retained_areas=relation_areas)[0]
    reader = _PlaceReader(index)
    role_refusals = role_violations(reader, fields, original_roles)
    fixed_response_headers = [{'place': place, 'start': None, 'end': None}
                              for place in source_detector.response_header_corners]
    fixed_subheadings = [{'place': place, 'start': None, 'end': None}
                         for place in source_detector.fixed_subheading_slots]
    unresolved_brackets = [{'place': _place_id(issue['part'], issue['slot']),
                            'start': issue.get('start'), 'end': issue.get('end')}
                           for issue in source_detector.coverage_issues
                           if issue['code'] in ('printed_bracket_alternatives', 'unbalanced_bracketed_source',
                                                'unmapped_bracketed_source', 'named_selection_source',
                                                'scalar_alternative_source', 'unresolved_insertion_source',
                                                'unresolved_narrative_band')]
    adjacent_answers = [area for area in source_detector.areas if any(
        relation.get('relation') == 'adjacent_checkbox_answer' for relation in area.source_questions)]
    temporal_answers = [area for area in source_detector.areas if any(
        relation.get('relation') == 'temporal_format_hint' for relation in area.source_questions)]
    requested_answers = [area for area in source_detector.areas if any(
        relation.get('relation') == 'parenthetical_write_request' for relation in area.source_questions)]
    nested_choices = [area for area in source_detector.areas if any(
        relation.get('relation') == 'nested_cell_options' for relation in area.source_questions)]
    branch_choices = [area for area in source_detector.areas if any(
        relation.get('relation') == 'option_branch_instruction' for relation in area.source_questions)]
    named_choices = [area for area in source_detector.areas if any(
        relation.get('relation') == 'named_selection_instruction' for relation in area.source_questions)]
    scalar_alternatives = [area for area in source_detector.areas if any(
        relation.get('relation') == 'scalar_checkbox_alternative' for relation in area.source_questions)]
    hierarchy_choices = [area for area in source_detector.areas if any(
        relation.get('relation') in ('bracketed_checkbox_hierarchy', 'merged_checkbox_hierarchy') for relation in area.source_questions)]
    ops = []                                   # (paragraph_or_element, sort_position, callable)
    glyph_writes = {}                          # original source identity -> (paragraph, ordinal, state, part)

    def resolve(part, path, fp):
        slot = index.by_id.get("%s#%s" % (part, path))
        if slot is None or (fp is not None and fingerprint(slot.el) != fp):
            fail("The stored mapping no longer matches this form. Review the mapping again.", "mapping_mismatch")
        return slot

    def original_branch_mapping(field, area):
        """Match the complete former representation compiled from this original.

        A nested question's existing source relationship is retained, never
        dropped to obtain a shorter option. The former full option still has
        only its former full answer value.
        """
        relation = next((r for r in area.source_questions
                         if r.get('relation') == 'option_branch_instruction'), None)
        if relation is None:
            return False
        loc = field.get('locator') or {}
        extras = [{'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el)}
                  for slot in area.extra_slots]
        return (loc.get('part') == area.slot.part and loc.get('slot') == area.slot.path
                and loc.get('fingerprint') == fingerprint(area.slot.el) and loc.get('extra', []) == extras
                and loc.get('target') == relation['original_target']
                and field.get('kind') == area.kind and field.get('label') == area.label
                and field.get('options') == relation['printed']
                and field.get('context') == relation['original_context']
                and field.get('source_questions', []) == relation['original_relations'])

    def exact_original_area(field, area):
        loc = field.get('locator') or {}
        extras = [{'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el)}
                  for slot in area.extra_slots]
        return (loc.get('part') == area.slot.part and loc.get('slot') == area.slot.path
                and loc.get('fingerprint') == fingerprint(area.slot.el) and loc.get('extra', []) == extras
                and loc.get('target') == area.target and field.get('kind') == area.kind
                and field.get('label') == area.label and field.get('context') == area.context
                and field.get('options', []) == area.options
                and field.get('source_questions', []) == area.source_questions)

    for area in source_detector.areas:
        if not any(r.get('relation') in ('explicit_insertion', 'narrative_empty_band')
                   for r in area.source_questions):
            continue
        regions = [{'place': place[0], 'start': place[1], 'end': place[2]}
                   for place in reader.of(area_to_field(1, area))]
        if area.label_slot is not None:
            regions.append({'place': area.label_slot.id, 'start': None, 'end': None})
        active = [f for f in fields if answers.get(f['key']) not in (None, '', [])
                  and any(reader.touches(place, region) for place in reader.of(f) for region in regions)]
        if active and (len(active) != 1 or not exact_original_area(active[0], area)):
            fail('This insertion requires its complete original request and exact answer band. '
                 'Review the mapping again; its source and neighbors remain unchanged.', 'mapping_mismatch')

    for area in source_detector.areas:
        if not any(r.get('relation') == 'guided_response_row' for r in area.source_questions):
            continue
        regions = [{'place': ref['part'] + '#' + ref['slot'], 'start': None, 'end': None}
                   for ref in area.target['boxes']]
        active = [f for f in fields if answers.get(f['key']) not in (None, '', [])
                  and any(reader.touches(place, region) for place in reader.of(f) for region in regions)]
        if active and (len(active) != 1 or not exact_original_area(active[0], area)):
            fail('This guided response row needs its complete original question, options and controls. '
                 'Review the mapping again; its printed guidance remains unchanged.', 'mapping_mismatch')

    for identity in {area.slot.id for area in source_detector.areas
                     if area.target.get('shape') == 'after_label'}:
        paired = paired_colon_areas(source_detector, identity)
        if not paired:
            continue
        region = {'place': identity, 'start': None, 'end': None}
        writers = [field for field in fields
                   if (field.get('locator') or {}).get('target', {}).get('type') != 'none'
                   and any(reader.touches(place, region) for place in reader.of(field))]
        if not any(answers.get(field['key']) not in (None, '', []) for field in writers):
            continue
        if (any(not any(exact_paired_colon_field(field, area) for area in paired) for field in writers)
                or any(sum(exact_paired_colon_field(field, area) for field in writers) > 1 for area in paired)):
            fail('These printed captions require their distinct original answer spans. Remove the repeated '
                 'or overlapping writer and review each physical destination once.', 'mapping_mismatch')

    for area in hierarchy_choices:
        relation = area.source_questions[0]
        regions = [{'place': ref['part'] + '#' + ref['slot'], 'start': None, 'end': None}
                   for ref in relation['sources'][1:]]
        active = [f for f in fields if answers.get(f['key']) not in (None, '', [])
                  and any(reader.touches(place, region) for place in reader.of(f) for region in regions)]
        if not active:
            continue
        if any(not any(exact_original_area(f, candidate) for candidate in [*hierarchy_choices, *adjacent_answers])
               for f in active):
            fail('This printed parent/subgroup hierarchy requires its exact original question and controls. '
                 'Review the separate groups; a former flat mapping cannot authorize these destinations.', 'mapping_mismatch')
        matches = [f for f in fields if exact_original_area(f, area)]
        if len(matches) > 1:
            fail('This printed subgroup has more than one mapped writer. Review each destination once.', 'mapping_mismatch')
        parent = relation['parent']
        if parent is None:
            continue
        parent_areas = [a for a in hierarchy_choices if parent in a.target['boxes']]
        if len(parent_areas) != 1:
            fail('The printed subgroup no longer has one controlling parent.', 'mapping_mismatch')
        parent_area = parent_areas[0]
        parent_fields = [f for f in fields if exact_original_area(f, parent_area)]
        if len(parent_fields) > 1:
            fail('The controlling parent has more than one mapped writer.', 'mapping_mismatch')
        parent_value = answers.get(parent_fields[0]['key']) if parent_fields else None
        parent_position = parent_area.target['boxes'].index(parent)
        parent_selected = (parent_position in _options_chosen(parent_fields[0], parent_value)
                           if parent_value not in (None, '', []) else box_state(index, parent) is True)
        value = answers.get(matches[0]['key']) if matches else None
        selected = (bool(_options_chosen(matches[0], value)) if value not in (None, '', [])
                    else any(box_state(index, box) is True for box in area.target['boxes']))
        if selected and not parent_selected:
            fail('This subgroup has a selected answer while its own printed parent is unselected. '
                 'Review the parent and child answers; no selection was inferred.', 'conditional_answer_unselected')

    # The printed Or is an exclusive alternative, not an invitation to silently
    # clear an existing selection. Read the exact original pair before queuing
    # any edits, including when a stored mapping omitted the alternative.
    for alternative in scalar_alternatives:
        relation = alternative.source_questions[0]
        region = {'place': relation['cell']['part'] + '#' + relation['cell']['slot'],
                  'start': None, 'end': None}
        writers = [field for field in fields if any(reader.touches(place, region) for place in reader.of(field))]
        active = [field for field in writers if answers.get(field['key']) not in (None, '', [])]
        if not active:
            continue
        scalar = next(area for area in source_detector.areas
                      if area.slot.id == relation['scalar']['part'] + '#' + relation['scalar']['slot']
                      and area.target == relation['scalar_target'])
        scalar_fields = [field for field in writers if exact_original_area(field, scalar)]
        alternative_fields = [field for field in writers if exact_original_area(field, alternative)]
        if (len(scalar_fields) > 1 or len(alternative_fields) > 1
                or any(not exact_original_area(field, scalar) and not exact_original_area(field, alternative)
                       for field in active)):
            fail('This printed Or alternative requires its exact original scalar and checkbox mappings. '
                 'Review the complete caption and control again.', 'mapping_mismatch')
        scalar_value = answers.get(scalar_fields[0]['key']) if scalar_fields else None
        checked_value = answers.get(alternative_fields[0]['key']) if alternative_fields else None
        checked = (bool(_options_chosen(alternative_fields[0], checked_value))
                   if checked_value not in (None, '', []) else relation['original_checked'])
        if checked and scalar_value not in (None, '', []):
            fail('The printed Or control and its scalar answer cannot both be filled. '
                 'Review the answer and explicitly untick the alternative before entering a value.',
                 'conflicting_alternative_answers')

    for field in fields:
        loc = field.get("locator") or {}
        if loc.get("contract") != CONTRACT:
            fail("The mapping is not a contract v3 mapping.", "mapping_mismatch")
        answer = answers.get(field["key"])
        if answer is None or answer == "" or answer == []:
            continue
        if any(reader.touches(place, region) for place in reader.of(field) for region in fixed_response_headers):
            fail("This mapping writes into fixed response-column header spacing, not an answer. "
                 "Reinspect the original and review the row's checkbox choices before exporting.", "mapping_mismatch")
        if any(reader.touches(place, region) for place in reader.of(field) for region in fixed_subheadings):
            fail("This mapping writes into a fixed underlined group heading, not an answer. "
                 "Reinspect the original and review its separate answer lines before exporting.", "mapping_mismatch")
        if any(reader.touches(place, region) for place in reader.of(field) for region in unresolved_brackets):
            fail("This answer touches an unresolved printed source range. Keep that exact range unchanged and "
                 "review its mapping before generation or export.", "unresolved_source_range")
        target = loc.get("target") or {}
        if target.get('shape') == 'insertion' and not any(
                exact_original_area(field, area) for area in source_detector.areas
                if any(r.get('relation') == 'explicit_insertion' for r in area.source_questions)):
            fail('This insertion no longer matches its complete original request and span. '
                 'Review the mapping again.', 'mapping_mismatch')
        for area in named_choices:
            relation = next(r for r in area.source_questions if r.get('relation') == 'named_selection_instruction')
            regions = [{'place': ref['part'] + '#' + ref['slot'], 'start': None, 'end': None} for ref in relation['sources']]
            if not any(reader.touches(place, region) for place in reader.of(field) for region in regions):
                continue
            if any(loc.get('part') == adjacent.slot.part and loc.get('slot') == adjacent.slot.path
                   and target == adjacent.target and field.get('kind') == adjacent.kind
                   and field.get('label') == adjacent.label and field.get('context') == adjacent.context
                   and field.get('source_questions') == adjacent.source_questions for adjacent in adjacent_answers):
                continue
            if (loc.get('part') != area.slot.part or loc.get('slot') != area.slot.path or target != area.target
                    or field.get('kind') != area.kind or field.get('label') != area.label
                    or field.get('context') != area.context or field.get('options') != area.options
                    or field.get('source_questions') != area.source_questions):
                fail('This named instruction no longer owns the complete original question and options. Review its exact mapping again.', 'mapping_mismatch')
        for area in branch_choices:
            branch_relation = next(r for r in area.source_questions if r.get('relation') == 'option_branch_instruction')
            regions = [{'place': ref['part'] + '#' + ref['slot'], 'start': None, 'end': None}
                       for ref in branch_relation['sources']]
            if not any(reader.touches(place, region) for place in reader.of(field) for region in regions):
                continue
            legacy = original_branch_mapping(field, area)
            if (loc.get('part') != area.slot.part or loc.get('slot') != area.slot.path
                    or field.get('kind') != area.kind or field.get('label') != area.label
                    or not legacy and (target != area.target or field.get('context') != area.context
                                       or field.get('options') != area.options
                                       or field.get('source_questions') != area.source_questions)):
                fail('This option and its conditional instruction no longer match the original question. '
                     'Review the exact caption and instruction again.', 'mapping_mismatch')
        for area in nested_choices:
            # This proven cell contains one caption, its complete options and
            # plain spacers. Its caption is source, never a second scalar answer.
            region = {'place': area.label_slot.parent.id, 'start': None, 'end': None}
            if not any(reader.touches(place, region) for place in reader.of(field)):
                continue
            # The same original-source compiler can qualify one separate
            # conditional write-in beside these options. Its exact relationship
            # is checked below; it never grants a generic writer inside the cell.
            if any(loc.get('part') == adjacent.slot.part and loc.get('slot') == adjacent.slot.path
                   and target == adjacent.target and field.get('kind') == adjacent.kind
                   and field.get('label') == adjacent.label and field.get('context') == adjacent.context
                   and field.get('source_questions') == adjacent.source_questions for adjacent in adjacent_answers):
                continue
            if original_branch_mapping(field, area):
                continue
            if (loc.get('part') != area.slot.part or loc.get('slot') != area.slot.path
                    or target != area.target or field.get('kind') != area.kind
                    or field.get('label') != area.label or field.get('context') != area.context
                    or field.get('options') != area.options
                    or field.get('source_questions') != area.source_questions):
                fail('This nested choice no longer matches its complete original question cell. '
                     'Review the exact question and options again.', 'mapping_mismatch')
        for area in requested_answers:
            regions = [{'place': slot.id, 'start': None, 'end': None} for slot in [area.slot, *area.extra_slots]]
            if not any(reader.touches(place, region) for place in reader.of(field) for region in regions):
                continue
            extras = [{'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el)}
                      for slot in area.extra_slots]
            if (loc.get('part') != area.slot.part or loc.get('slot') != area.slot.path
                    or target != area.target or loc.get('extra', []) != extras
                    or field.get('source_questions') != area.source_questions):
                fail('The complete printed write request and answer area changed. Review its exact mapping again.',
                     'mapping_mismatch')
        for area in temporal_answers:
            # Each paragraph contains one complete format, so an insertion at
            # either boundary is also this destination, not another question.
            region = {'place': area.slot.id, 'start': None, 'end': None}
            if not any(reader.touches(place, region) for place in reader.of(field)):
                continue
            if (loc.get('part') != area.slot.part or loc.get('slot') != area.slot.path
                    or target != area.target or field.get('kind') != area.kind
                    or field.get('label') != area.label or field.get('context') != area.context
                    or field.get('source_questions') != area.source_questions):
                fail('The date/time answer does not match its complete original format and aligned caption. '
                     'Review this exact mapping again.', 'mapping_mismatch')
            writers = [other for other in fields
                       if (other.get('locator') or {}).get('target', {}).get('type') != 'none'
                       and any(reader.touches(place, region) for place in reader.of(other))]
            if len(writers) != 1:
                fail('This complete date/time paragraph has more than one mapped writer. Remove the repeated '
                     'or overlapping field and review each physical destination once.', 'mapping_mismatch')
        for area in adjacent_answers:
            region = {'place': area.slot.id, 'start': area.target['start'],
                      'end': area.target['start'] + 1 if area.target.get('shape') == 'after_label' else area.target['end']}
            if not any(reader.touches(place, region) for place in reader.of(field)):
                continue
            if (loc.get('part') != area.slot.part or loc.get('slot') != area.slot.path
                    or target != area.target or field.get('kind') != area.kind
                    or field.get('label') != area.label or field.get('context') != area.context
                    or field.get('source_questions') != area.source_questions):
                fail('This answer changes a source-bound checkbox write-in or its complete ownership. '
                     'Review its exact mapping again.', 'mapping_mismatch')
            relation = area.source_questions[0]
            if relation['condition'] != 'printed_option':
                continue
            owner = relation['owner']
            controls = [f for f in fields if f.get('kind') == relation['owner_kind']
                        and f.get('label') == relation['owner_label']
                        and f.get('context') == relation['owner_context']
                        and f.get('options') == relation['owner_options']
                        and (f.get('locator') or {}).get('part') == owner['part']
                        and (f.get('locator') or {}).get('slot') == owner['slot']
                        and (f.get('locator') or {}).get('fingerprint') == owner['fingerprint']
                        and (f.get('locator') or {}).get('target') == relation['owner_target']]
            if len(controls) != 1:
                fail('The conditional write-in has no unique original controlling choice. Review the mapping.',
                     'mapping_mismatch')
            control = controls[0]; value = answers.get(control['key'])
            position = relation['option_index']
            if value not in (None, '', []):
                selected = position in _options_chosen(control, value)
            else:
                states = constrained_option_states(index, control)
                selected = position < len(states) and states[position] is True
                if control['kind'] == 'choice':
                    # The original's tick is usable only when this single-choice
                    # control has one unambiguous, readable selection. A pair of
                    # printed ticks is not the clinician resolving that conflict.
                    selected = (selected and len(states) == len(control['options'])
                                and all(state is True or state is False for state in states)
                                and sum(state is True for state in states) == 1)
            if not selected:
                fail('This write-in is conditional on its own printed option being selected. '
                     'Review the controlling choice; no tick was inferred.', 'conditional_answer_unselected')
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
        for region,reason in source_detector.geometry_regions.items():
            if any(location==region or location.startswith(region+'/') or region.startswith(location+'/')
                   for location in locations):
                fail(reason,'unqualified_layout')
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
        numeric = [relation for relation in relations if isinstance(relation, dict)
                   and relation.get('relation') == 'manual_numeric_part']
        parts = source_detector.manual_numeric_parts(anchors[0])
        if parts and any(reader.touches(place, {'place': anchors[0].id, 'start': start, 'end': stop})
                         for place in reader.of(field) for start, stop in parts):
            automatic = any(area.slot.id == anchors[0].id and area.target == target
                            for area in source_detector.areas)
            if not automatic and not numeric:
                fail('A divided numeric band needs its exact source-bound part review. Review its numbered part '
                     'again; the separator and other parts remain unchanged.', 'mapping_mismatch')
        if numeric or target.get('shape') == 'numeric_part':
            current = (source_detector.manual_numeric_part(anchors[0], numeric[0].get('number'), field.get('kind'))
                       if len(numeric) == 1 and len(relations) == 1 else None)
            if (current is None or current.target != target or current.source_questions != relations
                    or loc.get('extra') or field.get('max_chars') != current.capacity):
                fail('This numeric part no longer matches its complete original band. Remove the field and review '
                     'the exact part again.', 'mapping_mismatch')
            if not isinstance(answer, str) or not re.fullmatch(r'[0-9]{1,%d}' % current.capacity, answer):
                fail('Numeric part %d takes at most %d digits, with no separator or other text. Nothing was shortened.'
                     % (numeric[0]['number'], current.capacity), 'invalid_answer')
            region = {'place': anchors[0].id, 'start': target['start'], 'end': target['end']}
            if any(reader.touches(place, region) or place[0] == anchors[0].id
                   and (other.get('locator', {}).get('target', {}).get('shape') != 'numeric_part'
                        or other.get('source_questions') == relations)
                   for other in fields if other is not field for place in reader.of(other)):
                fail('This numeric part overlaps another mapped writer. Remove the whole-band or repeated field '
                     'and review each part once.', 'mapping_mismatch')
        for relation in relations:
            if not isinstance(relation, dict):
                fail("The related question mapping is invalid.", "invalid_mapping")
            if relation.get("relation") == "immediate_previous_question":
                refs = [relation.get("source"), relation.get("reference")]
            elif relation.get("relation") in ('paragraph_list_answer', 'manual_paragraph_options', 'manual_ruled_paragraph_answer') and isinstance(relation.get("descriptors"), list):
                instructions = relation.get("instructions", [])
                if not isinstance(instructions, list):
                    fail("The related question instructions are invalid.", "invalid_mapping")
                refs = [relation.get("source")] + relation["descriptors"] + instructions
            elif relation.get("relation") in ("native_checkbox_history", "nested_cell_options", "option_branch_instruction", "named_selection_instruction", "scalar_checkbox_alternative", "bracketed_checkbox_hierarchy", "merged_checkbox_hierarchy", "temporal_format_hint", "guided_response_row") and isinstance(relation.get("sources"), list):
                refs = relation["sources"]
            elif relation.get('relation') == 'adjacent_checkbox_answer':
                refs = [relation.get('source'), relation.get('owner')]
            elif relation.get('relation') in ('parenthetical_write_request', 'explicit_insertion', 'narrative_empty_band'):
                refs = [relation.get('source')]
            elif relation.get('relation') == 'manual_numeric_part':
                refs = [relation.get('source')]
            else:
                fail("The related question mapping is invalid.", "invalid_mapping")
            for ref in refs:
                if not isinstance(ref, dict) or not ref.get("fingerprint"):
                    fail("The related question source is missing.", "invalid_mapping")
                resolve(ref.get("part"), ref.get("slot"), ref["fingerprint"])
        if relations:
            manual_ruled = any(relation.get('relation') == 'manual_ruled_paragraph_answer' for relation in relations)
            manual_list = any(relation.get('relation') == 'manual_paragraph_options' for relation in relations)
            if numeric:
                owns = True  # the complete band, exact part and capacity were recompiled above
            elif manual_ruled:
                current = source_detector.manual_ruled_paragraphs(source_detector.index.by_id[anchors[0].id], field.get('kind'))
                expected_extra = ([{'part': s.part, 'slot': s.path, 'fingerprint': fingerprint(s.el)}
                                   for s in current.extra_slots] if current else [])
                owns = bool(current and current.target == target and current.source_questions == relations
                            and loc.get('extra', []) == expected_extra)
            elif manual_list:
                current = source_detector.manual_paragraph_options(source_detector.index.by_id[anchors[0].id],
                                                                   field.get('kind'))
                owns = bool(current and current.target == target and current.source_questions == relations
                            and current.options == field.get('options'))
            else:
                owns = (any(original_branch_mapping(field, area) for area in relation_areas)
                        or any(area.slot.id == anchors[0].id and area.target == target and area.source_questions == relations
                           and (not any(r.get("relation") in ('native_checkbox_history', 'adjacent_checkbox_answer', 'nested_cell_options', 'option_branch_instruction', 'named_selection_instruction', 'scalar_checkbox_alternative', 'bracketed_checkbox_hierarchy', 'merged_checkbox_hierarchy', 'temporal_format_hint', 'guided_response_row') for r in relations)
                                or area.kind == field.get("kind") and area.options == (field.get("options") or [])
                                and area.label == field.get("label") and area.context == field.get("context"))
                           for area in relation_areas))
            if not owns:
                fail("The related question no longer owns this answer destination. Review the mapping again.",
                     "mapping_mismatch")
        elif target.get('type') == 'paragraph_options':
            # Removing the manual origin/ownership metadata cannot appoint
            # arbitrary paragraphs as options. Existing automatically detected
            # groups retain their original exact target and printed options.
            if not any(area.slot.id == anchors[0].id and area.target == target
                       and area.options == field.get('options') for area in source_detector.areas):
                fail('The printed option group has no source-bound review. Review the complete list mapping again.',
                     'mapping_mismatch')
        elif target.get('type') == 'ruled_paragraphs':
            fail('The ruled answer area has no complete source-bound review. Choose its first line and review the mapping.',
                 'mapping_mismatch')
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
                if target.get('shape') == 'temporal_band':
                    current = next((area for area in source_detector.areas
                                    if area.slot.id == anchor.id and area.target == target), None)
                    if current is None or current.kind != field.get('kind') or loc.get('extra'):
                        fail('This divided date no longer owns its original caption, blank runs and format guide.',
                             'mapping_mismatch')
                    for ref in (target['caption'], target['guide']):
                        resolve(ref['part'], ref['slot'], ref['fingerprint'])
                    characters = temporal_band_characters(answer, target['format'])
                    for (start, end), character in zip(target['parts'], characters):
                        ops.append((anchor.el, start, lambda el=anchor.el, s=start, e=end, a=character:
                                    replace_range(el, s, e, a), part))
                    continue
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
            elif kind in ("paragraph", "ruled_paragraphs"):
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
    # Read this invocation's immutable original trees before any checkbox,
    # pinning or text edit. An already-correct box may schedule a write that
    # changes no XML; serializing that part would still change its original
    # declaration/BOM/empty-element syntax. Compare the complete tree, rather
    # than inferring a no-op from a Boolean flag or from the field's metadata.
    original_part_hashes = {part: fingerprint(package.tree(part))
                            for part in {op[3] for op in ops} | {row[3] for row in glyph_writes.values()}}
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
    updates = {part: package.tree(part) for part in changed
               if fingerprint(package.tree(part)) != original_part_hashes[part]}
    out = package.write(updates) if updates else data
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


def _adjacent_glyph_prefix(original, before, field, source, current, start):
    """Read only source-owned checkbox state changes before a conditional value.

    A freshly compiled relationship from this immutable original must match the
    complete scalar mapping. Other printed characters and unrelated boxes still
    identify the span exactly. This is invocation-local readback, never authority
    for a writer or a cache shared between documents.
    """
    loc = field.get('locator') or {}
    relations = field.get('source_questions') or []
    shape = loc.get('target', {}).get('shape')
    if (shape not in ('after_label', 'blank') or len(relations) != 1
            or relations[0].get('relation') != 'adjacent_checkbox_answer'
            or fingerprint(before.el) != loc.get('fingerprint') or len(current) < start):
        return False
    detector = Detector(original.package, layout_proposal=True)
    detector.detect()
    matches = [area for area in detector.areas
               if area.slot.id == before.id and not area.protection
               and area.target == loc.get('target') and area.kind == field.get('kind')
               and area.label == field.get('label') and area.context == field.get('context')
               and area.source_questions == relations]
    if len(matches) != 1:
        return False
    relation = matches[0].source_questions[0]
    owners = [area for area in detector.areas if area.slot.id == relation['owner']['part'] + '#' + relation['owner']['slot']
              and not area.protection and area.target == relation['owner_target']
              and area.kind == relation['owner_kind'] and area.label == relation['owner_label']
              and area.context == relation['owner_context'] and area.options == relation['owner_options']]
    hierarchies = [r for owner in owners for r in owner.source_questions
                   if r.get('relation') == 'bracketed_checkbox_hierarchy']
    if shape == 'blank' and (len(owners) != 1 or len(hierarchies) != 1):
        return False
    refs = relation['owner_target'].get('boxes', [])
    if len(hierarchies) == 1:
        # A fresh hierarchy proves all parents/children on this same original
        # band. Its other owned glyphs can change while the conditional scalar
        # remains in place; unrelated controls and every other character cannot.
        refs = [ref for area in detector.areas for r in area.source_questions
                if r.get('relation') == 'bracketed_checkbox_hierarchy'
                and r['sources'] == hierarchies[0]['sources'] and r['bands'] == hierarchies[0]['bands']
                for ref in area.target.get('boxes', [])]
    glyphs = glyph_boxes(before.el)
    normalized = list(current[:start]); owned = False
    for ref in refs:
        if ref.get('part') != before.part or ref.get('slot') != before.path + '/glyphs':
            continue
        ordinal = ref.get('glyph')
        if type(ordinal) is not int or not 0 <= ordinal < len(glyphs):
            return False
        piece, offset, char = glyphs[ordinal]
        position = piece.start + offset
        if not 0 <= position < start or current[position] not in (BOX, CHECKED):
            return False
        normalized[position] = char
        owned = True
    return owned and ''.join(normalized) == source[:start]


def _paired_colon_value(original, final, before, after, field, source_detector):
    """Read simultaneous insertions only between uniquely retained original ink.

    Each complete caption, gap and unit remains literal. A repeated boundary
    inside an answer is ambiguous and is held, rather than selecting the first
    occurrence. The detector is compiled from this exact immutable input and is
    reused only by the current effective_values invocation.
    """
    detector = source_detector() if callable(source_detector) else source_detector
    if detector is None:
        detector = Detector(original.package, layout_proposal=True)
        detector.detect()
    if detector.package is not original.package:
        return None
    paired = paired_colon_areas(detector, before.id)
    matches = [i for i, area in enumerate(paired) if exact_paired_colon_field(field, area)]
    if len(matches) != 1:
        return None
    visibility = Detector(final.package)
    current, pieces = paragraph_text(after.el)
    if ('\x00' in current or any(piece.kind not in ('t', 'tab', 'br') for piece in pieces)
            or not visibility.tab_source_visible(after) or visibility.region_hidden(after.el)):
        return None
    source = paragraph_text(before.el)[0]
    points = [area.target['start'] for area in paired]
    fixed = [source[:points[0]], *[source[a:b] for a, b in zip(points, points[1:])], source[points[-1]:]]
    if not current.startswith(fixed[0]) or not current.endswith(fixed[-1]):
        return None
    cursor = len(fixed[0]); values = []
    for ink in fixed[1:-1]:
        # The entire original inter-answer ink identifies this boundary. Do
        # not accept a removed caption, duplicate caption inside an answer or
        # an earlier occurrence outside its physical order.
        position = current.find(ink)
        if not ink or position < cursor or current.find(ink, position + 1) != -1:
            return None
        values.append(current[cursor:position]); cursor = position + len(ink)
    last = len(current) - len(fixed[-1])
    if last < cursor:
        return None
    values.append(current[cursor:last])
    return values[matches[0]]


def constrained_scalar_value(original, final, field, written, *, _source_detector=None):
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
    elif kind == 'ruled_paragraphs':
        refs = [loc] + list(loc.get('extra', []))
        chunks = []
        for ref in refs:
            old = original.by_id.get('%s#%s' % (ref.get('part'), ref.get('slot')))
            new = final.by_id.get('%s#%s' % (ref.get('part'), ref.get('slot')))
            if old is None or new is None:
                return None
            source, current = paragraph_text(old.el)[0], paragraph_text(new.el)[0]
            if source != '\t' or not current.endswith(source):
                return None
            chunks.append(current[:-len(source)])
        while chunks and not chunks[-1]: chunks.pop()
        value = '\n'.join(chunks)
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
        if target.get('shape') == 'numeric_part':
            return numeric_part_value(source, current, target.get('number'))
        if target.get('shape') == 'temporal_band':
            detector = _source_detector() if callable(_source_detector) else _source_detector
            if detector is None:
                detector = Detector(original.package)
            if detector.package is not original.package:
                return None
            own = detector.index.by_id.get(identity)
            area = detector.temporal_band(own) if own is not None else None
            if area is None or area.target != target or field.get('kind') != 'date':
                return None
            for ref in (target['caption'], target['guide']):
                neighbour = final.by_id.get('%s#%s' % (ref['part'], ref['slot']))
                if neighbour is None or fingerprint(neighbour.el) != ref['fingerprint']:
                    return None
            visibility = Detector(final.package)
            if (not visibility.tab_source_visible(after) or visibility.region_hidden(after.el)
                    or wraps_structure(after.el)):
                return None
            expression, end = '', 0
            for start, stop in target['parts']:
                expression += re.escape(source[end:start]) + r'([A-Za-z0-9])'
                end = stop
            match = re.fullmatch(expression + re.escape(source[end:]), current)
            if match is None:
                return '' if not written and current == source else None
            characters = ''.join(match.groups())
            lengths = [len(part) for part in re.findall(r'd+|m+|y+', target['format'])]
            pieces, at = [], 0
            for length in lengths:
                pieces.append(characters[at:at + length]); at += length
            try:
                if temporal_band_characters('/'.join(pieces), target['format']) != characters:
                    return None
            except V3Failure:
                return None
            return '/'.join(pieces)
        start, end = target.get("start"), target.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(source):
            return None
        if target.get("shape") == "after_label":
            end = start
        prefix, suffix = source[:start], source[end:]
        prefix_matches = current.startswith(prefix) or _adjacent_glyph_prefix(
            original, before, field, source, current, start)
        if ("\x00" in source or "\x00" in current or not prefix_matches or
                not current.endswith(suffix) or len(current) < len(prefix) + len(suffix)):
            value = (_paired_colon_value(original, final, before, after, field, _source_detector)
                     if target.get('shape') == 'after_label' else None)
            if value is None:
                return None
        else:
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
    detector = None
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
    def source_detector():
        # Lazy and invocation-local. Recompile only if simultaneous insertion
        # readback requires it; never derive authority from the mutable output.
        nonlocal detector
        if detector is None:
            detector = Detector(index.package, layout_proposal=True)
            detector.detect()
        return detector
    result = {}
    for field in fields:
        loc = field["locator"]; target = loc["target"]
        option = field["kind"] in ("choice", "multi_choice", "checkbox")
        state = constrained_option_states(final, field) if option else constrained_scalar_value(
            index, final, field, field["key"] in answers, _source_detector=source_detector)
        for copy in target.get("copies", []):
            # These readers resolve their own copied anchor. Absolute checkbox
            # destinations do not establish an independent copy relationship.
            if option and target["type"] not in DISPLAYED + ("text_options", "paragraph_options") and target.get("write") != "option_text":
                state = [None] * max(1, len(field.get("options") or []))
                break
            variant = {**field, "locator": {**loc, **copy}}
            copied = constrained_option_states(final, variant) if option else constrained_scalar_value(
                index, final, variant, field["key"] in answers, _source_detector=source_detector)
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

MANUAL_KINDS = {"text", "long_text", "date", "time", "checkbox", "choice", "multi_choice", "signature", "initials"}


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
        parts = detector.manual_numeric_parts(s)
        if parts:
            row['numeric_parts'] = [{'number': n, 'digits': stop - start}
                                    for n, (start, stop) in enumerate(parts, 1)]
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
        numeric_part = t.get('numeric_part')
        if numeric_part is not None:
            group = detector.manual_numeric_part(slot, numeric_part, kind)
            if group is None:
                fail('Choose Text and a numbered part of a complete empty numeric band. Filled, hidden, linked or '
                     'mixed content cannot be divided this way.', 'invalid_mapping')
            target = group.target
        elif slot.kind == "glyphs" or slot.kind == "p" and kind == "checkbox":
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
            group = detector.manual_paragraph_options(slot, kind) or detector.manual_ruled_paragraphs(slot, kind)
            if group is not None:
                slot, target, options = group.slot, group.target, group.options
            elif kind == 'long_text' and (detector.ruled_paragraph_stop(slot) is not None
                                         or detector.ptext(slot.el)[0] == '\t'):
                fail('Choose the first line of the complete empty ruled answer area, immediately after its printed '
                     'question and optional guidance. Filled, hidden or inconsistent lines need another mapping.',
                     'invalid_mapping')
            elif kind == 'multi_choice':
                fail('For several printed options, choose the question or first item of its complete adjacent '
                     'plain list. Existing selections, hidden fields and incomplete lists need another mapping.',
                     'invalid_mapping')
            else:
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
        if target['type'] in ('paragraph_options', 'ruled_paragraphs') or target.get('shape') == 'numeric_part':
            area = group
            area.label = label
            if supplied_context:
                area.context = clean_label(supplied_context, limit=MAX_MAPPING_CONTEXT)
        else:
            area = Area(kind, label, slot, target, context=clean_label(context, limit=MAX_MAPPING_CONTEXT),
                        options=options if kind in ("choice", "multi_choice") else ([label] if kind == "checkbox" else []))
        if slot.kind == "ff" and target["type"] == "ff_text":
            area.protection = ff_text_protection(slot.el)
        if target.get('shape') != 'numeric_part':
            area.capacity = detector.capacity_for(area)
        field = area_to_field(n, area)
        field["key"] = "m3_%s" % hashlib.sha256(("%s|%s|%s" % (slot.id, json_dumps(target), label)).encode()).hexdigest()[:12]
        field["origin"] = "manual"
        annotate_printed(detector.index, field)
        # The place's printed authorship/review requirement, read exactly as for the engine's own fields.
        source_policy.annotate(detector, [field])
        fixed_subheadings = [{'place': place, 'start': None, 'end': None}
                             for place in detector.fixed_subheading_slots]
        reader = _PlaceReader(detector.index)
        if any(reader.touches(place, region) for place in reader.of(field) for region in fixed_subheadings):
            fail("This place is a fixed underlined group heading, not an answer. "
                 "Reinspect the original and choose one of its separate answer lines. Nothing was added.",
                 "invalid_mapping")
        # ⚠️ A ROLE PLACE TAKES ONLY WHAT IT ALLOWS, whoever chooses it: a clinician's add or a model's proposal on a
        # signing, initials, consent or protected place is refused unless it is a Signature or Initials field.
        roles = destination_roles_of(package) if roles is None else roles
        refusal = role_violations(_PlaceReader(detector.index), [field], roles).get(field["key"])
        if refusal:
            fail(refusal["reason"] + " Nothing was added.", "destination_role")
        out.append(field)
    return out
