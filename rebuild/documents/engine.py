"""Adapters around python-docx and pypdf, run only inside the isolated worker."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
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

if __package__:
    from .tab_form import inspect_tabs, fill_tabs, _answer_tab, WARNINGS as TAB_WARNINGS
else:  # Isolated worker imports this module directly.
    from tab_form import inspect_tabs, fill_tabs, _answer_tab, WARNINGS as TAB_WARNINGS

MAX_FIELDS = 200
MAX_ANSWER = 100_000
TOKEN = re.compile(r"\{\{\s*([\w][\w .?:/()\-]{0,119}?)\s*\}\}")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


PRINTED_UNITS = {'°C', '°F', 'mm', 'cm', 'm', 'ms', 's', 'mL', 'ml', 'L',
                 'kg', 'g', 'mg', '%', 'bpm', 'mmHg', 'mm Hg', 'µm', 'μm', 'm/s'}
PRINTED_DATE_FORMATS = {'YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY',
                        'DD-MM-YYYY', 'MM-DD-YYYY'}


def constraint_from_context(prefix, suffix):
    """Only literal local form declarations establish an answer constraint.

    A clinical label, an underscore length and nearby prose do not establish a
    date format, range or unit. Ambiguous/combined declarations remain text.
    This same reader runs before preparation and against the prepared token at
    export, so neither a model nor mutable mapping metadata supplies authority.
    """
    base = {'version': 1, 'data_type': 'text'}
    before, after = prefix.strip().rstrip(':').strip(), suffix.strip()
    declarations = []
    parenthetical = re.search(r'\(([^()]*)\)\s*$', before)
    unit = after.strip('()[] ').rstrip('.')
    if unit in PRINTED_UNITS and not (unit == 's' and after.startswith(('(', '['))):
        declarations.append({**base, 'data_type': 'number', 'unit': unit})
    if parenthetical:
        declaration = parenthetical.group(1).strip()
        explicit = re.fullmatch(r'units?\s*:\s*(.+)', declaration, re.I)
        printed_unit = explicit.group(1).strip() if explicit else declaration
        # (s) also denotes a grammatical plural, even when separated by a
        # space. A label is not authority to reinterpret it as seconds. Keep
        # that ambiguity unless the original explicitly calls it a unit.
        if printed_unit in PRINTED_UNITS and (printed_unit != 's' or explicit):
            declarations.append({**base, 'data_type': 'number', 'unit': printed_unit})
    formats = [fmt for fmt in PRINTED_DATE_FORMATS
               if after.strip('()[] ') == fmt or re.search(r'\(' + re.escape(fmt) + r'\)\s*:?$', before)]
    if len(formats) == 1:
        declarations.append({**base, 'data_type': 'date', 'format': formats[0]})
    if after.lower() in {'(integer)', '[integer]'}:
        declarations.append({**base, 'data_type': 'integer'})
    elif after.lower() in {'(number)', '[number]'}:
        declarations.append({**base, 'data_type': 'number'})
    marked_prefix = re.search(r'\b(?:choose|select)\s+one\s*:?\s*([^:]+)$', before, re.I)
    option_texts = [after.strip('()[] '), marked_prefix.group() if marked_prefix else before.rsplit(':', 1)[-1].strip()]
    if parenthetical:
        option_texts.append(parenthetical.group(1).strip())
    for text in option_texts:
        # Yes/No is an explicit binary list. Other slash-separated text is a
        # list only when the local form explicitly says to choose/select ONE.
        marked = re.fullmatch(r'(?:choose|select)\s+one\s*:?\s*(.+)', text, re.I)
        source = marked.group(1) if marked else text
        options = [part.strip() for part in source.split('/')]
        binary = [part.casefold() for part in options] in [['yes', 'no'], ['no', 'yes']]
        if ((binary or marked) and 2 <= len(options) <= 12
                and len(set(options)) == len(options)
                and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9 -]{0,60}', part) for part in options)):
            declarations.append({**base, 'data_type': 'choice', 'options': options})
    unique = {json.dumps(item, sort_keys=True): item for item in declarations}
    return next(iter(unique.values())) if len(unique) == 1 else base



class DocumentFailure(ValueError):
    def __init__(self, message, code="invalid_document"):
        super().__init__(message)
        self.code = code


def fail(message, code="invalid_document"):
    raise DocumentFailure(message, code)


def validate_docx(path, *, inventory_only=False):
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
                        if local in {"object", "altChunk"}:
                            fail("Active and embedded document content is not supported.", "unsafe_upload")
                        if local in {"fldSimple", "fldChar", "instrText", "del", "ins"} or (not inventory_only and local in {"sdt", "txbxContent"}):
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


def answerable_row(row_cells):
    """A row that LOOKS like question/answer but is not a shape this adapter maps.

    Deliberately conservative: at least one short, label-like cell with text, and at least
    one other cell entirely empty. A fully populated data table and a one-column layout
    table both score false, so an ordinary document does not collect advisory noise.
    """
    texts = [cell_text(cell) for cell in row_cells]
    return (any(text and len(text) <= 80 for text in texts)
            and any(not cell_occupied(cell) for cell in row_cells))


def answer_tabs_present(paragraphs):
    """Underlined answer tabs exist somewhere, WITHOUT mapping them.

    Detection only. The tab adapter owns its own contract and runs solely when no
    placeholder/table mapping applies; this exists so that precedence can be REPORTED
    instead of silently discarding a whole section of the doctor's form.
    """
    for paragraph in paragraphs:
        if any(_answer_tab(run) for run in paragraph._p.findall(qn("w:r"))):
            return True
    return False


MAX_LABEL_CELL = 80
CONTRACT_V1 = "v1"          # two-column tables only; tabs only when nothing else matched
CONTRACT_V2 = "v2"          # + unambiguous multi-column rows, + tabs alongside other structures
CONTRACT = CONTRACT_V2


def cell_text(cell):
    return "".join(cell.xpath(".//w:t/text()")).strip()


#: ⚠️ ELEMENTS THAT RENDER SOMETHING WITHOUT PRODUCING A `w:t`. `cell_text` reads only
#: `.//w:t`, so a cell holding a TICKED WINGDINGS CHECKBOX (`w:sym w:char="F0FE"`) reads as
#: empty — and the write path assigns `Run.text`, which clears the run and DELETES the symbol.
#: Measured: a consent box a clinician had ticked was erased from the document being finalized.
#: The old screen named three tags out of this set while the docstring promised never to
#: overwrite anything, which is a promise enumerated instead of stated.
OCCUPYING = (".//w:drawing | .//w:pict | .//w:br | .//w:sym | .//w:object"
             " | .//w:fldChar | .//w:fldSimple | .//w:sdt")


def cell_occupied(cell):
    """Anything already in this cell — text OR rendered content `cell_text` cannot see.

    ONE predicate, because the two readers disagreeing is the failure: the answer-target screen
    and the unmapped-area notice must mean the same thing by "empty", or a cell is silently
    overwritten by one and not reported by the other.
    """
    return bool(cell_text(cell)) or bool(cell.xpath(OCCUPYING))


def usable_answer_cell(cell):
    """An empty cell that can safely receive an answer."""
    return not cell_occupied(cell)


def multi_column_answers(row_cells):
    """Answer cells in a row of MORE than two columns, only where placement is unambiguous.

    Returns a list of (label, answer_cell), or [] when the row must not be mapped.

    Two shapes qualify, and nothing else does:

      PAIRS      Label | blank | Label | blank | …   — strict alternation, even width >= 4.
                 Every blank has exactly one label immediately before it, so no boundary is
                 inferred. Six columns work the same way as four.

      ONE BLANK  exactly one empty cell anywhere in the row, and the FIRST cell carries text.
                 Covers Label | blank | Unit and Label | Unit | blank alike: there is only one
                 place an answer can go, and only one cell that can be its question.

    Deliberately NOT qualifying: two or more blanks that are not a strict alternation (is the
    second blank another answer to the same question, or a separate unlabelled one?), and any
    row whose first cell is empty (its blank has no question, and borrowing one from elsewhere
    is the heading-theft this product already refuses).
    """
    if len(row_cells) <= 2:
        return []
    texts = [cell_text(cell) for cell in row_cells]
    blanks = [i for i, text in enumerate(texts) if not text]
    if not blanks:
        return []                                   # a fully populated row is data, not questions

    if len(row_cells) % 2 == 0:
        # ⚠️ EVERY VALUE CELL MUST BE BLANK. The earlier rule allowed a part-filled row, and
        # measurement REFUTED it: `Procedure | Diagnostic colonoscopy | Consent | ____` reads as a
        # pairs grid, but `Aspirin | 81 mg | Daily | ____` is THE SAME SHAPE — and there the only
        # question offered was `Daily`, a frequency, whose answer was written into the Route
        # column. A header row with one empty trailing cell, `Date | Finding | Action | ____`,
        # mapped `Action` and wrote a clinical finding INTO THE HEADER ROW.
        #
        # Nothing in a row distinguishes a part-completed question from ordinary data, so the
        # part-completed form is now REPORTED as unmapped instead of guessed at. That is the
        # promise this adapter makes about an ambiguous layout, applied to itself.
        labels, values = texts[0::2], row_cells[1::2]
        if (all(label and len(label) <= MAX_LABEL_CELL for label in labels)
                and all(index % 2 == 1 for index in blanks)):
            offered = [(label, cell) for label, cell in zip(labels, values)
                       if not cell_text(cell) and usable_answer_cell(cell)]
            if len(offered) == len(values) == len(blanks):
                return offered
        return []

    # ⚠️ ODD WIDTH HAS NO UNAMBIGUOUS SHAPE, and the branch that claimed one is REMOVED.
    # It accepted "exactly one blank, first cell carries the question", which cannot tell
    # `Estimated blood loss | ____ | mL` apart from `Sodium | 140 | ____`, where the answer lands
    # in the REFERENCE RANGE column of a result table beside a result that already reads 140, or
    # from `Diabetes | ____ | X`, where free text goes into the Yes column of a history grid whose
    # No column is already ticked. All three are one blank after a non-empty first cell.
    return []


def docx_inspect(path, contract=CONTRACT):
    validate_docx(path)
    document = Document(path)
    paragraphs = []
    cells = []
    fields = []
    # Answer-shaped areas this adapter deliberately does NOT map. Every one of these was a
    # silent `continue`: the import succeeded, the doctor saw a plausible field list, and the
    # rest of the form was gone with nothing said. Refusing them is right; saying nothing is not.
    skipped = Counter()
    for part in docx_parts(document):
        for element in part.element.iter(qn("w:p")):
            paragraphs.append(Paragraph(element, part))
        for row in part.element.iter(qn("w:tr")):
            row_cells = row.findall(qn("w:tc"))
            # Merged cells can conceal a different question/answer boundary. Checked before the
            # width rules so a merged wide row is reported as merged, not as multi-column.
            if any(cell.xpath(".//w:vMerge | .//w:gridSpan | .//w:tbl") for cell in row_cells):
                if answerable_row(row_cells):
                    skipped["merged"] += 1
                continue
            if len(row_cells) != 2:
                pairs = multi_column_answers(row_cells) if contract == CONTRACT_V2 else []
                if not pairs:
                    if answerable_row(row_cells):
                        skipped["multi_column"] += 1
                    continue
                if row.xpath('./w:trPr/w:trHeight[@w:hRule="exact"]'):
                    fail("A blank answer cell has fixed height and could hide text; use an expanding row.", "overflow_risk")
                for label, answer_cell in pairs:
                    cells.append((answer_cell, part))
                    fields.append({"key": f"cell_{len(cells)-1}", "label": label, "kind": "text",
                                   "locator": {"cell": len(cells) - 1}})
                continue
            left, right = row_cells
            label = "".join(left.xpath(".//w:t/text()")).strip()
            contents = "".join(right.xpath(".//w:t/text()")).strip()
            if label and not contents:
                # ⚠️ THE THIRD READER, AND IT WAS LEFT BEHIND. `cell_occupied`'s docstring says
                # "ONE predicate, because the two readers disagreeing is the failure" — and this
                # one, the SHIPPED MAJORITY PATH, still enumerated three tags. Measured on
                # `Consent obtained | ☑`: the ticked Wingdings box has no `w:t`, so `contents` is
                # empty, the row mapped, and `Run.text` DELETED the symbol from the exported
                # document. Pre-existing, and the one line that makes the docstring true.
                if not usable_answer_cell(right):
                    skipped["answer_cell_contents"] += 1
                    continue
                if row.xpath('./w:trPr/w:trHeight[@w:hRule="exact"]'):
                    fail("A blank answer cell has fixed height and could hide text; use an expanding row.", "overflow_risk")
                cells.append((right, part))
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
        fields = inspect_tabs(path, paragraphs, fail)
    elif answer_tabs_present(paragraphs):
        # PRECEDENCE, NOW RESOLVED RATHER THAN REPORTED. A form holding both a question/answer
        # table and a labelled underlined section used to map the table and discard the section
        # without a word — while the same section ALONE imported perfectly. The two contracts are
        # disjoint by construction (inspect_tabs refuses any tab inside a table cell), so they
        # compose. Placeholders and tables already coexisted; this brings tabs into the same set.
        #
        # ⚠️ NEVER WORSE THAN BEFORE. inspect_tabs REFUSES an ambiguous tab layout, and it is
        # entitled to: adjacent blanks without separate labels, an unlabelled area with no
        # heading. Letting that refusal escape would turn a form that imports today into one
        # that does not. So a refusal falls back to the note this replaced, and the rest of the
        # form still maps.
        if contract == CONTRACT_V2:
            try:
                tab_fields = inspect_tabs(path, paragraphs, fail)
            except DocumentFailure:
                tab_fields = []
                skipped["underlined_tabs_ambiguous"] += 1
            fields.extend(tab_fields)
        else:
            skipped["underlined_tabs"] += 1
    if not fields:
        # The skipped areas ARE the explanation. Without them this refusal tells a doctor whose
        # form is full of visible blanks that the form contains nothing at all.
        fail(" ".join(["No supported fields found."] + unmapped_notes(skipped)
                      + ["Use labelled underlined answer tabs, {{Question}} placeholders, or two-column "
                         "question/blank-answer tables. Unlabelled decorative lines are not fields."]), "no_fields")
    if len(fields) > MAX_FIELDS or any(len(field["label"]) > 2000 for field in fields):
        fail("The template exceeds 200 fields or has an oversized question.", "field_limit")
    return document, paragraphs, cells, fields, unmapped_notes(skipped) + duplicate_label_note(fields)


UNMAPPED_NOTES = {
    "multi_column": ("{count} table row(s) have a question and a blank answer but are not two columns, so they were NOT "
                     "mapped. Only two-column question/answer rows are placed automatically. Split those rows into two "
                     "columns, or add a {{{{Question name}}}} placeholder in each answer cell."),
    "merged": ("{count} table row(s) with merged cells were NOT mapped, because a merge can hide where the answer really "
               "belongs. Unmerge those answer cells, or add a {{{{Question name}}}} placeholder inside each one."),
    "answer_cell_contents": ("{count} blank answer cell(s) contain a line break, image or drawing and were NOT mapped, so "
                             "nothing there is overwritten. Clear the cell, or add a {{{{Question name}}}} placeholder in it."),
    "underlined_tabs": ("This form also contains labelled underlined answer blanks. They were NOT mapped, because a form "
                        "uses ONE method: placeholders and question/answer tables take precedence. Keep one style "
                        "throughout, or add a {{{{Question name}}}} placeholder on each underlined line."),
    "underlined_tabs_ambiguous": ("This form also contains underlined answer blanks that could NOT be placed unambiguously, "
                                  "so they were not mapped; everything else in the form was. Adjacent blanks need their own "
                                  "label and a separating tab, and a blank with no label needs a section heading above it. "
                                  "Fix the layout, or add a {{{{Question name}}}} placeholder on each of those lines."),
}


def duplicate_label_note(fields):
    """Two answer areas that read as the same question cannot be told apart.

    It happens for ordinary reasons: the same {{placeholder}} name used twice, two sections
    with the same title, or — the case that matters clinically — a section title that Word
    does not consider a heading, so the numbered slots beneath it inherit the PREVIOUS
    section's name and a recommendation ends up labelled as a finding.

    This is reported, not repaired, and deliberately so. Inferring a heading from bold or
    capitalised text would be guessing at formatting, and the label is editable on the
    mapping-review screen, which is where a person can settle it in seconds.

    ⚠️ A WARNING AND NOT A FIELD KEY. `validate_mapping` compares the stored mapping against
    a fresh inspection with `fields != mapping (⚠️ SUPERSEDED: `validate_mapping` now compares STRUCTURE — key, kind, locator and the rest — and excludes only `label`, which the mapping-review rename gate owns instead.)`, so adding anything to the field dict would
    refuse every mapping version already saved — measured, not assumed.
    """
    counts = Counter((field.get("label") or "").strip() for field in fields)
    repeated = sorted(label for label, count in counts.items() if label and count > 1)
    if not repeated:
        return []
    shown = ", ".join(f'"{label}" ({counts[label]}x)' for label in repeated[:5])
    if len(repeated) > 5:
        shown += f", and {len(repeated) - 5} more"
    return [f"{len(repeated)} question label(s) appear more than once: {shown}. Answers cannot be told apart "
            f"while two questions read the same. If these are genuinely different questions — a section title "
            f"that is bold text rather than a Word heading makes the items beneath it inherit the previous "
            f"section's name — rename them under Edit field mapping before using this form."]


def unmapped_notes(skipped):
    """Name every answer-shaped area that was skipped, with a supported alternative.

    Ordered by UNMAPPED_NOTES so the same document always reports the same way. These are
    review notes, not errors: the mapping that WAS produced remains valid and usable.
    """
    return [UNMAPPED_NOTES[reason].format(count=skipped[reason]) for reason in UNMAPPED_NOTES if skipped.get(reason)]


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
    unsupported = next(((index, character) for index, character in enumerate(answer)
                        if ord(character) < 32 and character != "\n" or ord(character) > 126), None)
    if unsupported:
        index, character = unsupported
        # Name the character: a no-break space or a stray carriage return looks like plain text.
        shown = f"\u201c{character}\u201d, " if character.isprintable() and not character.isspace() else ""
        fail(f"The answer for {field['label']} has a character a PDF form cannot hold ({shown}U+{ord(character):04X} at "
             f"character {index + 1}): use plain ASCII letters, digits and punctuation (no curly quotes, long dashes, "
             f"symbols, accented letters or invisible characters such as no-break spaces), or use DOCX for Unicode. "
             f"No export was created.", "unsupported_characters")
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


def structure(fields):
    """A mapping's binding, without the question text.

    ⚠️ THE LABEL IS DELIBERATELY EXCLUDED, and this file's own contract says why: "Editable
    clinical labels should be separate application metadata." Mapping review lets a doctor
    rename a question, which produces a new mapping version whose labels differ from a fresh
    inspection of the unchanged original. Comparing labels would refuse every renamed mapping
    at fill time — which is exactly why the caller used to hand us a fresh inspection instead
    of the stored mapping, discarding the doctor's labels and, once two contracts existed,
    filling answers into renumbered cells.

    Everything that decides WHERE an answer goes — key, kind and locator — is still compared
    exactly, so a stale or altered binding is still refused.
    """
    return [{k: v for k, v in field.items() if k != "label"} for field in fields]


def validate_mapping(fields, mapping, answers):
    if not isinstance(mapping, list) or not isinstance(answers, dict):
        fail("Invalid mapping or answers.", "invalid_mapping")
    if structure(fields) != structure(mapping):
        fail("The field mapping does not match this original. Reinspect and create a new mapping version.", "mapping_mismatch")
    keys = {field["key"] for field in fields}
    if set(answers) - keys:
        fail("An answer refers to a field outside the template.", "invalid_mapping")
    for value in answers.values():
        if not isinstance(value, str) or len(value) > MAX_ANSWER:
            fail("Each answer must be text of at most 100,000 characters. Split the document instead of truncating.", "answer_limit")
        if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
            fail("An answer contains unsupported control characters.", "invalid_answer")
    validate_answer_constraints(mapping, answers)


def answer_constraint_error(field, value):
    """Validate newly reviewed source constraints; legacy fields stay unchanged."""
    constraint = field.get('answer_constraints')
    if constraint is None:
        return None
    label = field.get('label', 'This answer')
    if not isinstance(constraint, dict) or type(constraint.get('version')) is not int or constraint['version'] != 1:
        return f'{label}: the approved answer constraint is invalid.'
    kind = constraint.get('data_type')
    allowed = {'text': {'version', 'data_type'}, 'number': {'version', 'data_type', 'unit'},
               'integer': {'version', 'data_type'}, 'date': {'version', 'data_type', 'format'},
               'choice': {'version', 'data_type', 'options'}}
    if (not isinstance(kind, str) or kind not in allowed or set(constraint) - allowed[kind]
            or not {'version', 'data_type'} <= set(constraint)):
        return f'{label}: the approved answer constraint is invalid.'
    if kind == 'choice':
        options = constraint.get('options')
        if (not isinstance(options, list) or not 2 <= len(options) <= 12
                or any(not isinstance(option, str) or not option for option in options)
                or len(set(options)) != len(options)):
            return f'{label}: the approved original options are invalid.'
    if kind == 'date' and (not isinstance(constraint.get('format'), str)
                           or constraint['format'] not in PRINTED_DATE_FORMATS):
        return f'{label}: the approved date format is invalid.'
    if 'unit' in constraint and (not isinstance(constraint['unit'], str) or constraint['unit'] not in PRINTED_UNITS):
        return f'{label}: the approved measurement unit is invalid.'
    if not isinstance(value, str):
        return f'{label}: enter a text answer.'
    if not value.strip():
        return None  # Held/missing answers still require their explicit review decision.
    text = value.strip()
    if kind == 'choice':
        if text not in options:
            return f'{label}: choose exactly one original option; unsupported answers cannot be finalized.'
    elif kind in {'number', 'integer'}:
        unit = constraint.get('unit')
        if unit is not None:
            if not isinstance(unit, str) or not unit:
                return f'{label}: the approved measurement unit is invalid.'
            if text.endswith(unit):
                text = text[:-len(unit)].rstrip()
        number = r'[+-]?\d+' if kind == 'integer' else r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
        if not re.fullmatch(number, text):
            return f'{label}: enter {"an integer" if kind == "integer" else "a number"}' + (f' in {unit}.' if unit else '.')
    elif kind == 'date':
        patterns = {'YYYY-MM-DD': (r'\d{4}-\d{2}-\d{2}', '%Y-%m-%d'),
                    'DD/MM/YYYY': (r'\d{2}/\d{2}/\d{4}', '%d/%m/%Y'),
                    'MM/DD/YYYY': (r'\d{2}/\d{2}/\d{4}', '%m/%d/%Y'),
                    'DD-MM-YYYY': (r'\d{2}-\d{2}-\d{4}', '%d-%m-%Y'),
                    'MM-DD-YYYY': (r'\d{2}-\d{2}-\d{4}', '%m-%d-%Y')}
        fmt = constraint.get('format')
        if fmt not in patterns:
            return f'{label}: the approved date format is invalid.'
        pattern, parser = patterns[fmt]
        try:
            if not re.fullmatch(pattern, text):
                raise ValueError()
            datetime.strptime(text, parser)
        except ValueError:
            return f'{label}: enter a valid date in the original {fmt} format.'
    return None


def validate_answer_constraints(mapping, answers):
    for field in mapping:
        error = answer_constraint_error(field, answers.get(field['key'], ''))
        if error:
            fail(error, 'invalid_answer_constraint')


def constrained_answer_text(field, value):
    error = answer_constraint_error(field, value)
    if error:
        fail(error, 'invalid_answer_constraint')
    constraint = field.get('answer_constraints', {})
    unit = constraint.get('unit')
    # The original still prints the unit beside the blank. Retain the complete
    # reviewed answer in records; insert its numeric portion exactly once.
    if constraint.get('data_type') == 'number' and unit and value.strip().endswith(unit):
        return value.strip()[:-len(unit)].rstrip()
    return value


def bind_answer_constraints(paragraphs, fields, mapping):
    """Re-derive present new constraints; do not reinterpret approved old maps."""
    stored = {field['key']: field for field in mapping}
    for field in fields:
        entry = stored.get(field['key'], {})
        if 'answer_constraints' not in entry:
            continue
        location = field['locator']
        if 'paragraph' not in location or 'token' not in location:
            fail('This answer constraint is not bound to a prepared literal blank.', 'mapping_mismatch')
        text = paragraphs[location['paragraph']].text
        actual = constraint_from_context(text[:location['start']], text[location['end']:])
        if entry['answer_constraints'] != actual:
            fail('The answer constraint differs from the original printed form.', 'mapping_mismatch')
        field['answer_constraints'] = actual
    return fields


def apply_cell_and_placeholder(document, paragraphs, cells, fields, answers):
    """Write every non-tab answer into the tree, returning the package parts touched.

    Reverse order matters for placeholders: two tokens in one paragraph share an offset
    space, so replacing the later span first keeps the earlier one's offsets valid.
    """
    changed = set()
    for field in reversed(fields):
        answer = constrained_answer_text(field, answers.get(field["key"], ""))
        locator = field["locator"]
        if "cell" in locator:
            cell, part = cells[locator["cell"]]
            paragraph = Paragraph(cell.findall(qn("w:p"))[0], part)
            if paragraph.runs:
                paragraph.runs[0].text = answer
            else:
                paragraph.add_run(answer)
            if answer:
                changed.add(str(part.partname).lstrip("/"))
        else:
            paragraph = paragraphs[locator["paragraph"]]
            replace_span(paragraph, locator["start"], locator["end"], answer)
            changed.add(str(paragraph.part.partname).lstrip("/"))
    return changed


def fill_docx(path, output, document, paragraphs, cells, fields, answers):
    """Fill a DOCX whatever mix of answer shapes its mapping holds.

    The dispatch used to be all-or-nothing on `fields[0]`: one tab field sent the WHOLE
    mapping to fill_tabs, and otherwise the whole mapping went through python-docx. A mapping
    holding both — now possible, and the point of this change — could not be filled by either.

    ⚠️ THE TWO WRITERS ALSO SAVE DIFFERENTLY, AND THAT IS NOT INCIDENTAL. fill_tabs copies the
    ORIGINAL package and substitutes only the parts it touched, so untouched bytes survive
    exactly; python-docx's save() re-serializes every part. They mutate the same element tree,
    so a mixed document can use both writers and then the byte-preserving save — but a
    tab-free document keeps python-docx's save, because changing how EXISTING supported forms
    are written is not this change's business.
    """
    tab_fields = [f for f in fields if "tab_form" in f["locator"]]
    other_fields = [f for f in fields if "tab_form" not in f["locator"]]
    if tab_fields and other_fields:
        changed = apply_cell_and_placeholder(document, paragraphs, cells, other_fields, answers)
        fill_tabs(path, output, docx_parts(document), tab_fields, answers, also_changed=changed)
    elif tab_fields:
        fill_tabs(path, output, docx_parts(document), tab_fields, answers)
    else:
        apply_cell_and_placeholder(document, paragraphs, cells, other_fields, answers)
        document.save(output)


def process(workspace, request):
    fmt = request["format"]
    path = workspace / ("input." + fmt)
    warnings = []
    if fmt == "docx":
        stored = request.get("mapping") if request.get("operation") == "fill" else None
        try:
            document, paragraphs, cells, fields, notes = docx_inspect(path)
        except DocumentFailure as refusal:
            # ⚠️ A REFUSAL THE CURRENT CONTRACT INVENTED MUST NOT STRAND AN OLDER MAPPING.
            # The structural fallback further down only runs if the inspection RETURNS. A v2-only
            # `fail()` — a fixed-height answer cell, or a field count the wider contract pushes past
            # the limit — escapes first, and a reviewed encounter then cannot be exported AT ALL,
            # refused by name over a table row the doctor never mapped. Retry under the contract
            # the stored mapping was made with, and accept it only if it matches field for field.
            if stored is None:
                raise
            try:
                legacy = docx_inspect(path, contract=CONTRACT_V1)
            except DocumentFailure:
                raise refusal from None
            if structure(legacy[3]) != structure(stored):
                raise refusal from None
            document, paragraphs, cells, fields, notes = legacy
        warnings = ["DOCX answers expand and can change pagination. Review the exported document's layout."]
        if fields and "tab_form" in fields[0]["locator"]:
            warnings.extend(TAB_WARNINGS)
        # Answer-shaped areas that were NOT mapped, named first: they are what the doctor
        # would otherwise discover only by reading the exported form and finding it blank.
        warnings = notes + warnings
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
    if fmt == "docx":
        bind_answer_constraints(paragraphs, fields, request['mapping'])
    if fmt == "docx" and structure(fields) != structure(request["mapping"]):
        # ⚠️ A STORED MAPPING IS BOUND TO THE CONTRACT THAT PRODUCED IT. Mappings saved before
        # multi-column and mixed support existed hold FEWER fields for the same document, and
        # validate_mapping compares exactly — so re-inspecting such a template under the current
        # contract would refuse to export it. Re-read it under the legacy contract instead.
        # Exact equality is the proof: if the legacy inspection matches the stored mapping
        # field for field, it IS that mapping's contract, and filling it behaves as it always did.
        legacy = docx_inspect(path, contract=CONTRACT_V1)
        bind_answer_constraints(legacy[1], legacy[3], request['mapping'])
        if structure(legacy[3]) == structure(request["mapping"]):
            document, paragraphs, cells, fields, _ = legacy
            result["fields"] = fields
    validate_mapping(fields, request["mapping"], answers)
    if fmt == "docx":
        fill_docx(path, workspace / "output.docx", document, paragraphs, cells, fields, answers)
    else:
        values = {field["key"]: answers.get(field["key"], "") for field in fields}
        # Refusals name the question as the doctor sees it: the stored mapping's label, which a rename
        # changes, not the PDF's own tooltip or internal field name. The structure was proved equal above.
        labels = {entry["key"]: entry.get("label") for entry in request["mapping"]}
        for field in fields:
            check_pdf_capacity({**field, "label": labels.get(field["key"]) or field["label"]}, values[field["key"]])
        writer = PdfWriter()
        writer.append(reader)
        for page in writer.pages:
            if page.get("/Annots"):
                writer.update_page_form_field_values(page, values, auto_regenerate=False)
        writer.write(workspace / "output.pdf")
    return {**result, "filled": sum(bool(answers.get(field["key"])) for field in fields), "missing": [field["key"] for field in fields if not answers.get(field["key"])]}
