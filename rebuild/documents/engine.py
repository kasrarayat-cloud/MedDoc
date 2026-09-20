"""Adapters around python-docx and pypdf, run only inside the isolated worker."""

from __future__ import annotations

from pathlib import PurePosixPath
import re
import stat
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject
from reportlab.pdfbase.pdfmetrics import stringWidth

MAX_FIELDS = 200
MAX_ANSWER = 100_000
TOKEN = re.compile(r"\{\{\s*([\w][\w .?:/()\-]{0,119}?)\s*\}\}")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class DocumentFailure(ValueError):
    def __init__(self, message, code="invalid_document"):
        super().__init__(message)
        self.code = code


def fail(message, code="invalid_document"):
    raise DocumentFailure(message, code)


def validate_docx(path):
    try:
        with ZipFile(path) as package:
            infos = package.infolist()
            names = [x.filename for x in infos]
            if len(infos) > 1000 or len(names) != len(set(names)):
                fail("DOCX contains duplicate entries or too many parts.", "unsafe_upload")
            if sum(x.file_size for x in infos) > 50 * 1024 * 1024:
                fail("DOCX expands beyond the 50 MiB processing limit.", "unsafe_upload")
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                fail("The upload is not a DOCX document.")
            for item in infos:
                name = unquote(item.filename)
                mode = item.external_attr >> 16
                if (name.startswith("/") or "\\" in name or ".." in PurePosixPath(name).parts
                        or ":" in name or stat.S_ISLNK(mode) or item.flag_bits & 1):
                    fail("DOCX contains an unsafe package entry.", "unsafe_upload")
                lower = name.lower()
                if any(part in lower for part in ("vbaproject", "macros", "activex", "embeddings/", "afchunk")):
                    fail("Macros, active content, and embedded documents are not supported.", "unsafe_upload")
                if item.file_size > 20 * 1024 * 1024 or item.file_size > max(1, item.compress_size) * 250:
                    fail("DOCX compression exceeds the safe processing limit.", "unsafe_upload")
                if lower.endswith((".xml", ".rels")):
                    data = package.read(item)
                    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                        fail("XML entities and document types are not supported.", "unsafe_upload")
                    tree = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
                    # XML can be UTF-16/32. Judge the parsed declaration too;
                    # ASCII byte matching alone does not identify every DTD.
                    if tree.getroottree().docinfo.doctype:
                        fail("XML entities and document types are not supported.", "unsafe_upload")
                    if lower.endswith(".rels"):
                        for relation in tree:
                            target = unquote(relation.get("Target", ""))
                            if relation.get("TargetMode", "").lower() == "external" or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                                fail("External links and linked resources are not accepted in templates.", "unsafe_upload")
                            kind = relation.get("Type", "").lower()
                            if any(marker in kind for marker in ("vbaproject", "vbasignature", "activex", "oleobject")) or kind.endswith(("/package", "/afchunk", "/control")):
                                fail("Macros, active content, and embedded documents are not supported.", "unsafe_upload")
                    if lower == "[content_types].xml":
                        for declaration in tree:
                            kind = declaration.get("ContentType", "").lower()
                            if any(marker in kind for marker in ("macroenabled", "vbaproject", "vbasignature", "activex", "oleobject")):
                                fail("Macros, active content, and embedded documents are not supported.", "unsafe_upload")
                    for node in tree.iter():
                        local = etree.QName(node).localname
                        if local in {"vanish", "webHidden", "specVanish", "noWrap", "fitText"} and node.get(qn("w:val"), "1") not in {"0", "false", "off"}:
                            fail("Hidden text and compressed or non-wrapping text need the advanced document adapter.", "overflow_risk")
                        if local in {"object", "altChunk", "fldSimple", "fldChar", "instrText", "sdt", "txbxContent", "del", "ins"}:
                            fail("Word fields, content controls, text boxes, and tracked changes need the advanced document adapter.", "unsupported_structure")
    except BadZipFile:
        fail("The DOCX package is malformed.")


def docx_parts(document):
    # Keep order deterministic. Headers/footers can share parts across sections.
    yield document.part
    seen = {str(document.part.partname)}
    for relation in document.part.rels.values():
        if relation.reltype.endswith(("/header", "/footer")):
            part = relation.target_part
            if str(part.partname) not in seen:
                seen.add(str(part.partname))
                yield part


def docx_inspect(path):
    validate_docx(path)
    document = Document(path)
    paragraphs = []
    cells = []
    fields = []
    for part in docx_parts(document):
        for element in part.element.iter(qn("w:p")):
            paragraphs.append(Paragraph(element, part))
        for row in part.element.iter(qn("w:tr")):
            row_cells = row.findall(qn("w:tc"))
            if len(row_cells) != 2:
                continue
            # Merged cells can conceal a different question/answer boundary.
            if any(cell.xpath(".//w:vMerge | .//w:gridSpan | .//w:tbl") for cell in row_cells):
                continue
            left, right = row_cells
            label = "".join(left.xpath(".//w:t/text()")).strip()
            contents = "".join(right.xpath(".//w:t/text()")).strip()
            if label and not contents and not right.xpath(".//w:drawing | .//w:pict | .//w:br"):
                if row.xpath('./w:trPr/w:trHeight[@w:hRule="exact"]'):
                    fail("A blank answer cell has fixed height and could hide text; use an expanding row.", "overflow_risk")
                cells.append(right)
                fields.append({"key": f"cell_{len(cells)-1}", "label": label, "kind": "text", "locator": {"cell": len(cells)-1}})
    for index, paragraph in enumerate(paragraphs):
        remaining = TOKEN.sub("", paragraph.text)
        if "{{" in remaining or "}}" in remaining:
            fail("A placeholder has invalid syntax. Use {{Question name}}.", "invalid_placeholder")
        if TOKEN.search(paragraph.text) and paragraph.text != "".join(run.text for run in paragraph.runs):
            fail("A placeholder contains a hyperlink or another unsupported inline structure.", "unsupported_structure")
        for match in TOKEN.finditer(paragraph.text):
            if paragraph._p.xpath('ancestor::w:tr/w:trPr/w:trHeight[@w:hRule="exact"]'):
                fail("A placeholder is in a fixed height row and could hide text.", "overflow_risk")
            fields.append({"key": f"text_{index}_{match.start()}", "label": match.group(1).strip(), "kind": "text",
                           "locator": {"paragraph": index, "start": match.start(), "end": match.end(), "token": match.group()}})
    if not fields:
        fail("No supported fields found. Use {{Question}} placeholders or two-column question/blank-answer tables.", "no_fields")
    if len(fields) > MAX_FIELDS or any(len(field["label"]) > 2000 for field in fields):
        fail("The template exceeds 200 fields or has an oversized question.", "field_limit")
    return document, paragraphs, cells, fields


def replace_span(paragraph, start, end, answer):
    """Edit only affected runs, retaining question text and every run's style."""
    offset = 0
    inserted = False
    for run in paragraph.runs:
        value = run.text
        run_start, run_end = offset, offset + len(value)
        offset = run_end
        if run_end <= start or run_start >= end:
            continue
        prefix = value[:max(0, start - run_start)]
        suffix = value[max(0, end - run_start):] if end < run_end else ""
        run.text = prefix + (answer if not inserted else "") + suffix
        inserted = True
    if not inserted:
        fail("The placeholder spans unsupported Word content.", "unsupported_structure")


def _scan_pdf(reader):
    if reader.is_encrypted:
        fail("Encrypted PDFs are not accepted.", "unsafe_upload")
    if len(reader.pages) > 100:
        fail("PDF templates are limited to 100 pages.", "upload_limit")
    forbidden = {"/JavaScript", "/JS", "/OpenAction", "/AA", "/A", "/EmbeddedFiles", "/EmbeddedFile", "/EF", "/Launch", "/RichMediaContent", "/XFA", "/URI", "/SubmitForm", "/ImportData"}
    seen = set()
    stack = [reader.trailer]
    count = 0
    while stack:
        obj = stack.pop()
        if isinstance(obj, IndirectObject):
            identity = (obj.idnum, obj.generation)
            if identity in seen:
                continue
            seen.add(identity)
            obj = obj.get_object()
        count += 1
        if count > 100_000:
            fail("The PDF object graph is too large.", "upload_limit")
        if isinstance(obj, DictionaryObject):
            if forbidden.intersection(obj.keys()) or str(obj.get("/Type", "")) == "/EmbeddedFile":
                fail("PDF actions, attachments, XFA, and external resources are not accepted.", "unsafe_upload")
            stack.extend(obj.values())
        elif isinstance(obj, (ArrayObject, list)):
            stack.extend(obj)


def inherited(widget, key, default=None):
    current = widget
    for _ in range(20):
        if key in current:
            return current[key]
        parent = current.get("/Parent")
        if parent is None:
            return default
        current = parent.get_object()
    fail("The PDF field hierarchy is too deep.")


def qualified_name(widget):
    parts = []
    current = widget
    for _ in range(20):
        if current.get("/T"):
            parts.insert(0, str(current["/T"]))
        if "/Parent" not in current:
            return ".".join(parts)
        current = current["/Parent"].get_object()
    fail("The PDF field hierarchy is too deep.")


def pdf_inspect(path):
    reader = PdfReader(path, strict=True)
    _scan_pdf(reader)
    acro = reader.trailer["/Root"].get("/AcroForm")
    if acro is None:
        fail("Flat or scanned PDFs need licensed field detection/OCR and manual mapping; upload a fillable PDF or DOCX.", "flat_pdf")
    acro = acro.get_object()
    raw_fields = reader.get_fields() or {}
    if not raw_fields or len(raw_fields) > MAX_FIELDS:
        fail("The PDF must contain between 1 and 200 interactive fields.", "field_limit")
    widgets = {}
    for page_index, page in enumerate(reader.pages):
        for ref in page.get("/Annots", []):
            widget = ref.get_object()
            if widget.get("/Subtype") == "/Widget":
                widgets.setdefault(qualified_name(widget), []).append((page_index, widget))
            elif widget.get("/Subtype") in {"/FileAttachment", "/RichMedia", "/Movie", "/Sound", "/Screen", "/3D"}:
                fail("Active PDF annotations are not accepted.", "unsafe_upload")
    fields = []
    for key, value in raw_fields.items():
        if value.get("/FT") is None and value.get("/Kids"):
            continue  # non-terminal grouping node
        if value.get("/FT") != "/Tx":
            fail("This adapter supports PDF text fields only; other controls need the advanced adapter.", "unsupported_field")
        appearances = widgets.get(key, [])
        if not appearances:
            fail("A PDF field has no visible widget.", "unsupported_field")
        capacities = []
        for page_index, widget in appearances:
            flags = int(inherited(widget, "/Ff", 0))
            if flags & (1 | 8192 | 1048576 | 16777216 | 33554432):
                fail("Read-only, password, file-select, comb, and rich-text fields need the advanced adapter.", "unsupported_field")
            if int(widget.get("/F", 0)) & (1 | 2 | 32):
                fail("Invisible or hidden PDF fields are not supported.", "unsupported_field")
            rect = [float(x) for x in widget.get("/Rect", [])]
            if len(rect) != 4 or rect[2] <= rect[0] or rect[3] <= rect[1]:
                fail("The PDF field rectangle is invalid.", "unsupported_field")
            appearance = str(inherited(widget, "/DA", acro.get("/DA", "")))
            font = re.search(r"/([^\s]+)\s+([\d.]+)\s+Tf", appearance)
            if not font or float(font.group(2)) <= 0:
                fail("PDF fields need an explicit font size for reliable overflow checks.", "unsupported_font")
            resources = acro.get("/DR", {}).get_object() if hasattr(acro.get("/DR", {}), "get_object") else acro.get("/DR", {})
            font_resource = resources.get("/Font", {}).get_object().get("/" + font.group(1)) if hasattr(resources.get("/Font", {}), "get_object") else resources.get("/Font", {}).get("/" + font.group(1))
            if font_resource is None or str(font_resource.get_object().get("/BaseFont", "")) != "/Helvetica":
                fail("PDF appearance metrics currently support the standard Helvetica font only.", "unsupported_font")
            if widget.get("/MK", {}).get("/R", 0):
                fail("Rotated PDF fields need the advanced document adapter.", "unsupported_field")
            capacities.append({"page": page_index, "width": rect[2]-rect[0]-4, "height": rect[3]-rect[1]-4,
                               "font_size": float(font.group(2)), "multiline": bool(flags & 4096)})
        fields.append({"key": key, "label": str(value.get("/TU", key)), "kind": "text",
                       "locator": {"pdf_field": key}, "max_length": int(value.get("/MaxLen", 0)), "capacity": capacities})
    if not fields:
        fail("The PDF has no supported visible fields.", "no_fields")
    return reader, fields


def check_pdf_capacity(field, answer):
    if any(ord(character) < 32 and character != "\n" or ord(character) > 126 for character in answer):
        fail("PDF answers currently require printable ASCII text; use DOCX for Unicode.", "unsupported_characters")
    if field["max_length"] and len(answer) > field["max_length"]:
        fail(f"The answer for {field['label']} exceeds the PDF field's character limit. No export was created.", "answer_overflow")
    for capacity in field["capacity"]:
        size = capacity["font_size"]
        lines = answer.split("\n")
        if not capacity["multiline"] and len(lines) > 1:
            fail(f"The answer for {field['label']} needs multiple lines. No export was created.", "answer_overflow")
        # Deliberately accept only explicit lines that fit. Automatic wrap differs
        # between PDF viewers; never rely on scrolling or smaller auto-fit text.
        if any(stringWidth(line, "Helvetica", size) > capacity["width"] for line in lines) or len(lines) * size * 1.3 > capacity["height"]:
            fail(f"The complete answer for {field['label']} will not fit visibly. Edit the form or use DOCX. No text was truncated.", "answer_overflow")


def validate_mapping(fields, mapping, answers):
    if not isinstance(mapping, list) or not isinstance(answers, dict):
        fail("Invalid mapping or answers.", "invalid_mapping")
    if fields != mapping:
        fail("The field mapping does not match this original. Reinspect and create a new mapping version.", "mapping_mismatch")
    keys = {field["key"] for field in fields}
    if set(answers) - keys:
        fail("An answer refers to a field outside the template.", "invalid_mapping")
    for value in answers.values():
        if not isinstance(value, str) or len(value) > MAX_ANSWER:
            fail("Each answer must be text of at most 100,000 characters. Split the document instead of truncating.", "answer_limit")
        if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
            fail("An answer contains unsupported control characters.", "invalid_answer")


def process(workspace, request):
    fmt = request["format"]
    path = workspace / ("input." + fmt)
    warnings = []
    if fmt == "docx":
        document, paragraphs, cells, fields = docx_inspect(path)
        warnings = ["DOCX answers expand and can change pagination. Review the exported document's layout."]
    elif fmt == "pdf":
        reader, fields = pdf_inspect(path)
        warnings = ["PDF text fields only. Answers must fit visibly; overflow is rejected."]
    else:
        fail("Unsupported document format.")
    result = {"format": fmt, "fields": fields, "warnings": warnings, "adapter": "python-docx" if fmt == "docx" else "pypdf", "sandbox": "landlock+seccomp"}
    if request["operation"] == "inspect":
        return result
    if request["operation"] != "fill":
        fail("Unsupported operation.")
    answers = request["answers"]
    validate_mapping(fields, request["mapping"], answers)
    if fmt == "docx":
        for field in reversed(fields):
            answer = answers.get(field["key"], "")
            locator = field["locator"]
            if "cell" in locator:
                cell = cells[locator["cell"]]
                elements = cell.findall(qn("w:p"))
                paragraph = Paragraph(elements[0], document.part)
                if paragraph.runs:
                    paragraph.runs[0].text = answer
                else:
                    paragraph.add_run(answer)
            else:
                replace_span(paragraphs[locator["paragraph"]], locator["start"], locator["end"], answer)
        document.save(workspace / "output.docx")
    else:
        values = {field["key"]: answers.get(field["key"], "") for field in fields}
        for field in fields:
            check_pdf_capacity(field, values[field["key"]])
        writer = PdfWriter()
        writer.append(reader)
        for page in writer.pages:
            if page.get("/Annots"):
                writer.update_page_form_field_values(page, values, auto_regenerate=False)
        writer.write(workspace / "output.pdf")
    return {**result, "filled": sum(bool(answers.get(field["key"])) for field in fields), "missing": [field["key"] for field in fields if not answers.get(field["key"])]}
