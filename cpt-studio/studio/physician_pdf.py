"""The physician PDF report: one saved encounter's coding summary as a searchable US Letter document.

This module only draws. It takes a PhysicianReport, whose every string was chosen from saved records by
studio.physician_report, and returns PDF bytes. It reads no database, opens no network connection, calls no
provider and decides nothing about codes: what appears is exactly what the report says.

Safety properties the tests pin:
- Every dynamic string is XML-escaped before it reaches ReportLab's paragraph markup, so source text can never
  become markup (an <img> or <a> tag in a quote is printed, not followed). No image is drawn and no remote
  resource is referenced; the fonts are the files in report_fonts/, embedded as subsets.
- A character the design font lacks is drawn in the bundled fallback font instead of a blank box, so an exact
  quotation stays exact.
- The output is deterministic: the same report renders to the same bytes (invariant mode; the PDF date is the
  report's own saved timestamp, never the clock).

Layout follows the owner-approved first-page design (handoff 2026-11-21, 01-APPROVED-MAIN-DESIGN.png) and the
evidence-page treatment for continuation pages; longer cases flow onto more pages instead of shrinking text.
"""

from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import TimeStamp
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

FONT_DIR = Path(__file__).resolve().parent / 'report_fonts'

DISPLAY = 'CPTReportDisplay'
BODY = 'CPTReportBody'
BODY_SEMI = 'CPTReportBodySemiBold'
MONO = 'CPTReportMono'
MONO_REGULAR = 'CPTReportMonoRegular'
FALLBACK = 'CPTReportFallback'

_FONT_FILES = {
    DISPLAY: 'CormorantGaramond-Medium.ttf',
    BODY: 'Manrope-Regular.ttf',
    BODY_SEMI: 'Manrope-SemiBold.ttf',
    MONO: 'IBMPlexMono-Medium.ttf',
    MONO_REGULAR: 'IBMPlexMono-Regular.ttf',
    FALLBACK: 'DejaVuSans.ttf',
}

# Design tokens (DESIGN-TOKENS.json of the handoff).
FOREST = colors.HexColor('#173F35')
INK = colors.HexColor('#1B2B27')
SECONDARY = colors.HexColor('#53645E')
IVORY = colors.HexColor('#F4F5F0')
RULE = colors.HexColor('#D8DFD9')
REVIEW_INK = colors.HexColor('#745216')
REVIEW_SURFACE = colors.HexColor('#FAF6E9')

PAGE_WIDTH, PAGE_HEIGHT = letter  # 612 x 792 pt, portrait
MARGIN_X = 36
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X
HEADER_RULE_Y = PAGE_HEIGHT - 120
FOOTER_RULE_Y = 43
FRAME_TOP = HEADER_RULE_Y - 18
FRAME_BOTTOM = FOOTER_RULE_Y + 14
FRAME_HEIGHT = FRAME_TOP - FRAME_BOTTOM

APPROVED = 'approved'
DRAFT = 'draft'


@dataclass(frozen=True)
class LabelledValue:
    """A labelled value; value None means nothing is saved there and the report prints its not-recorded text."""

    label: str
    value: str | None


@dataclass(frozen=True)
class EvidenceItem:
    quote: str
    locator: str | None = None


@dataclass(frozen=True)
class CodeRow:
    code: str
    caption: str                       # 'CPT suggestion' or 'Accepted code'
    label: str | None = None           # the line's leading words (its status, or who approved it)
    details: tuple[str, ...] = ()      # further saved facts of the line, one per printed line
    units: str | None = None
    status: str = ''                   # 'Review', 'Accepted', ...
    evidence_ref: str = ''             # 'Evidence 01'
    evidence: tuple[EvidenceItem, ...] = ()
    note: str | None = None            # a saved customer-safe explanation, if any


@dataclass(frozen=True)
class PhysicianReport:
    kind: str                                   # APPROVED or DRAFT
    status_line: str                            # 'DRAFT · REVIEW REQUIRED' / 'APPROVED · REVIEWED'
    identity_line: str                          # repeated in the header of every page
    report_ref: str                             # footer: report identifier and revision
    footer_note: str
    eyebrow: str
    title: str
    subtitle: str
    strip: tuple[LabelledValue, ...]
    metrics: tuple[tuple[str, str], ...]        # (value, label)
    codes_heading: str
    codes_side_note: str
    rows: tuple[CodeRow, ...]
    empty_rows_text: str
    review_title: str | None = None             # drafts with open items only
    review_items: tuple[str, ...] = ()
    record: tuple[LabelledValue, ...] = ()
    evidence_eyebrow: str = ''
    evidence_title: str = ''
    evidence_identity: str = ''
    no_evidence_text: str = ''
    scope: tuple[tuple[str, str, bool], ...] = ()   # (label, value, needs attention)
    closing_title: str = ''
    closing_text: str = ''
    document_title: str = ''                    # PDF metadata title
    not_recorded: str = 'Not recorded'
    units_missing: str = 'Not given'            # a line whose units the record does not hold
    notes_title: str = ''
    notes: tuple[str, ...] = ()                 # documentation notes (drafts)
    as_of: datetime | None = None               # the saved timestamp the PDF metadata carries (UTC)


_registered = False


def register_fonts() -> None:
    global _registered
    if _registered:
        return
    for name, filename in _FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
    pdfmetrics.registerFontFamily(BODY, normal=BODY, bold=BODY_SEMI, italic=BODY, boldItalic=BODY_SEMI)
    _registered = True


# Characters that carry no visible meaning in a printed quotation; everything else is kept exactly.
_CONTROL = re.compile('[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f​-‍⁠﻿]')
_LINE_BREAKS = re.compile(r'\r\n|\r|\n|\t| | ')


def clean_text(value) -> str:
    """Printable form of a saved string: line breaks and tabs become spaces, invisible control characters go."""
    text = '' if value is None else str(value)
    return _CONTROL.sub('', _LINE_BREAKS.sub(' ', text))


def _covered(font_name: str) -> dict:
    return getattr(pdfmetrics.getFont(font_name), 'face').charToGlyph


def markup(value, font: str = BODY) -> str:
    """Escape a saved string for paragraph markup; runs the font cannot draw use the fallback font."""
    register_fonts()
    text = clean_text(value)
    if not text:
        return ''
    primary = _covered(font)
    out: list[str] = []
    run: list[str] = []
    run_fallback = False

    def flush():
        if not run:
            return
        piece = escape(''.join(run))
        out.append(f'<font face="{FALLBACK}">{piece}</font>' if run_fallback else piece)
        run.clear()

    for ch in text:
        needs_fallback = ord(ch) not in primary and ch != ' '
        if needs_fallback != run_fallback:
            flush()
            run_fallback = needs_fallback
        run.append(ch)
    flush()
    return ''.join(out)


def _style(name, font, size, leading=None, color=INK, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading or round(size * 1.35, 1),
                          textColor=color, **kw)


def _styles() -> dict:
    return {
        'eyebrow': _style('eyebrow', BODY_SEMI, 8, 11, SECONDARY, spaceAfter=10),
        'title': _style('title', DISPLAY, 35, 41, FOREST, spaceAfter=6),
        'subtitle': _style('subtitle', BODY, 11, 16, SECONDARY, spaceAfter=18),
        'strip_label': _style('strip_label', BODY_SEMI, 7.5, 10, SECONDARY),
        'strip_value': _style('strip_value', BODY_SEMI, 11, 14.5, INK),
        'metric_value': _style('metric_value', DISPLAY, 26, 30, FOREST),
        'metric_label': _style('metric_label', BODY, 10, 13, SECONDARY),
        'section': _style('section', BODY_SEMI, 8, 11, SECONDARY),
        'section_side': _style('section_side', BODY, 8.5, 11, SECONDARY, alignment=TA_RIGHT),
        'index': _style('index', MONO_REGULAR, 9, 12, SECONDARY),
        'code': _style('code', MONO, 22, 26, FOREST),
        'caption': _style('caption', BODY, 8, 11, SECONDARY),
        'row_label': _style('row_label', BODY_SEMI, 12, 16, INK),
        'row_detail': _style('row_detail', BODY, 10.5, 14.5, SECONDARY),
        'units_label': _style('units_label', BODY_SEMI, 7, 10, SECONDARY),
        'units_value': _style('units_value', MONO, 14, 18, INK),
        'units_missing': _style('units_missing', BODY, 8.5, 11.5, SECONDARY, spaceBefore=3),
        'notes_title': _style('notes_title', BODY_SEMI, 8, 11, SECONDARY, spaceBefore=16, spaceAfter=4,
                              keepWithNext=1),
        'note_item': _style('note_item', BODY, 10.5, 15, INK, leftIndent=12, bulletIndent=0, spaceAfter=4),
        'status_review': _style('status_review', BODY_SEMI, 10, 13, REVIEW_INK),
        'status_ok': _style('status_ok', BODY_SEMI, 10, 13, FOREST),
        'evidence_ref': _style('evidence_ref', BODY, 8.5, 11.5, SECONDARY),
        'empty': _style('empty', BODY, 11, 16, SECONDARY, spaceBefore=6, spaceAfter=10),
        'review_title': _style('review_title', BODY_SEMI, 12, 16, REVIEW_INK, spaceAfter=4),
        'review_body': _style('review_body', BODY, 11, 16, INK),
        'record_label': _style('record_label', BODY_SEMI, 8, 11, SECONDARY),
        'record_value': _style('record_value', BODY_SEMI, 11, 15, INK),
        'evidence_title': _style('evidence_title', DISPLAY, 30, 34, FOREST, spaceAfter=6),
        'identity': _style('identity', BODY, 9.5, 13.5, SECONDARY, spaceAfter=14),
        'code_heading': _style('code_heading', BODY_SEMI, 15, 19, FOREST),
        'quote': _style('quote', BODY, 12, 18, INK),
        'locator': _style('locator', MONO_REGULAR, 8, 11, SECONDARY),
        'quote_long': _style('quote_long', BODY, 12, 18, INK, backColor=IVORY, borderColor=RULE, borderWidth=0.75,
                             borderPadding=(10, 14, 10, 14), spaceBefore=12, spaceAfter=12, leftIndent=14,
                             rightIndent=14),
        'note': _style('note', BODY, 10, 14, SECONDARY, spaceBefore=6, spaceAfter=8),
        'scope_label': _style('scope_label', BODY_SEMI, 10, 13.5, INK),
        'scope_value': _style('scope_value', BODY, 10, 13.5, SECONDARY, alignment=TA_RIGHT),
        'scope_attention': _style('scope_attention', BODY, 10, 13.5, REVIEW_INK, alignment=TA_RIGHT),
        'closing_title': _style('closing_title', DISPLAY, 20, 25, FOREST, spaceBefore=18, spaceAfter=6),
        'closing_text': _style('closing_text', BODY, 10, 14.5, SECONDARY),
    }


class HorizontalRule(Flowable):
    def __init__(self, width=CONTENT_WIDTH, color=RULE, thickness=0.75, space_before=0, space_after=0):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness
        self.space_before = space_before
        self.space_after = space_after

    def wrap(self, aW, aH):
        return self.width, self.space_before + self.thickness + self.space_after

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        y = self.space_after + self.thickness / 2
        self.canv.line(0, y, self.width, y)


def _p(text_markup: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text_markup, style)


def _present(value) -> bool:
    return value is not None and bool(clean_text(value).strip())


def _value_or_absent(value: str | None, report: PhysicianReport) -> str:
    return markup(value) if _present(value) else markup(report.not_recorded)


def _plain_table(rows, widths, extra=()) -> Table:
    table = Table(rows, colWidths=list(widths))
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        *extra,
    ]))
    return table


class _Pages:
    """Draws the running header and footer; the total page count comes from a first counting pass."""

    def __init__(self, report: PhysicianReport, total: int | None):
        self.report = report
        self.total = total

    def __call__(self, canv, doc):
        register_fonts()
        report = self.report
        right = PAGE_WIDTH - MARGIN_X
        canv.saveState()
        canv.setFillColor(FOREST)
        canv.rect(MARGIN_X, PAGE_HEIGHT - 3.5, CONTENT_WIDTH, 3.5, stroke=0, fill=1)
        _draw_text(canv, MARGIN_X, PAGE_HEIGHT - 66, 'QuillMD', DISPLAY, 19, FOREST)
        _draw_text(canv, MARGIN_X, PAGE_HEIGHT - 79, 'CPT STUDIO', BODY_SEMI, 6.8, SECONDARY, char_space=1.5)
        # Status and identity, repeated on every page.
        _draw_text(canv, right, PAGE_HEIGHT - 59, report.status_line, BODY_SEMI, 8,
                   REVIEW_INK if report.kind == DRAFT else FOREST, align='right')
        _draw_text(canv, right, PAGE_HEIGHT - 72, report.identity_line, BODY, 7.5, SECONDARY, align='right',
                   max_width=CONTENT_WIDTH * 0.62)
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.75)
        canv.line(MARGIN_X, HEADER_RULE_Y, right, HEADER_RULE_Y)
        canv.line(MARGIN_X, FOOTER_RULE_Y, right, FOOTER_RULE_Y)
        _draw_text(canv, MARGIN_X, FOOTER_RULE_Y - 15, report.footer_note, BODY, 7.5, SECONDARY)
        page = canv.getPageNumber()
        number = f'{page:02d}' if self.total is None else f'{page:02d} of {self.total:02d}'
        _draw_text(canv, right, FOOTER_RULE_Y - 15, f'{clean_text(report.report_ref)}   /   {number}', MONO_REGULAR, 7.5,
                   SECONDARY, align='right')
        canv.restoreState()


def _runs(text: str, font: str) -> list:
    """(font, text) runs of a canvas string: what ``font`` cannot draw goes to the fallback font, as markup() does."""
    primary = _covered(font)
    runs: list = []
    for ch in text:
        face = font if ch == ' ' or ord(ch) in primary else FALLBACK
        if runs and runs[-1][0] == face:
            runs[-1][1].append(ch)
        else:
            runs.append((face, [ch]))
    return [(face, ''.join(chars)) for face, chars in runs]


def _runs_width(runs, size) -> float:
    return sum(pdfmetrics.stringWidth(text, face, size) for face, text in runs)


def _draw_text(canv, x, y, text, font, size, color, align='left', max_width=None, char_space=0):
    """One canvas line with the fallback font for what ``font`` lacks; shortened with an ellipsis only when it cannot fit
    ``max_width`` (the header's identity line, which carries the document title the member typed)."""
    register_fonts()
    text = clean_text(text)
    runs = _runs(text, font)
    if max_width is not None and _runs_width(runs, size) > max_width:
        while text and _runs_width(_runs(text + '…', font), size) > max_width:
            text = text[:-1]
        runs = _runs(text.rstrip() + '…', font)
    width = _runs_width(runs, size) + char_space * max(len(text) - 1, 0)
    start = x - width if align == 'right' else x
    canv.setFillColor(color)
    for face, piece in runs:
        canv.setFont(face, size)
        canv.drawString(start, y, piece, charSpace=char_space)
        start += pdfmetrics.stringWidth(piece, face, size) + char_space * len(piece)


def _strip(report: PhysicianReport, s: dict) -> Flowable:
    if not report.strip:
        return Spacer(1, 1)
    labels = [_p(markup(item.label.upper(), BODY_SEMI), s['strip_label']) for item in report.strip]
    values = [_p(_value_or_absent(item.value, report), s['strip_value']) for item in report.strip]
    columns = len(report.strip)
    table = Table([labels, values], colWidths=[CONTENT_WIDTH / columns] * columns)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), IVORY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 13),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
        ('TOPPADDING', (0, 1), (-1, 1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 13),
    ]))
    return table


def _metrics(report: PhysicianReport, s: dict) -> Flowable:
    if not report.metrics:
        return Spacer(1, 1)
    values = [_p(markup(value, DISPLAY), s['metric_value']) for value, _ in report.metrics]
    labels = [_p(markup(label), s['metric_label']) for _, label in report.metrics]
    columns = len(report.metrics)
    return _plain_table([values, labels], [CONTENT_WIDTH / columns] * columns,
                        [('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                         ('BOTTOMPADDING', (0, 0), (-1, 0), 2)])


def _section_heading(left: str, right: str, s: dict) -> Table:
    return _plain_table([[_p(markup(left.upper(), BODY_SEMI), s['section']), _p(markup(right), s['section_side'])]],
                        [CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4],
                        [('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)])


_ROW_COLUMNS = (36, 104, 244, 54, 102)  # index, code, label, units, status: 540 pt


def _code_row(index: int, row: CodeRow, report: PhysicianReport, s: dict) -> Table:
    code_cell = [_p(markup(row.code, MONO), s['code']), _p(markup(row.caption), s['caption'])]
    label_cell = [_p(_value_or_absent(row.label, report), s['row_label'])]
    label_cell += [_p(markup(detail), s['row_detail']) for detail in row.details if _present(detail)]
    if _present(row.units):
        units_cell = [_p('UNITS', s['units_label']), _p(markup(row.units, MONO), s['units_value'])]
    else:
        units_cell = [_p('UNITS', s['units_label']), _p(markup(report.units_missing), s['units_missing'])]
    status_style = s['status_ok'] if report.kind == APPROVED else s['status_review']
    status_cell = [_p(markup(row.status, BODY_SEMI), status_style)]
    if row.evidence_ref:
        status_cell.append(_p(markup(row.evidence_ref), s['evidence_ref']))
    table = Table([[_p(markup(f'{index:02d}', MONO_REGULAR), s['index']), code_cell, label_cell, units_cell,
                    status_cell]], colWidths=list(_ROW_COLUMNS))
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (0, 0), 24),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('LINEBELOW', (0, 0), (-1, -1), 0.75, RULE),
    ]))
    return table


def _review_flow(report: PhysicianReport, s: dict) -> list:
    """Open items as one box when short; as flowing shaded paragraphs (which may continue overleaf) when long."""
    if not report.review_title:
        return []
    content = [_p(markup(report.review_title, BODY_SEMI), s['review_title'])]
    content += [_p(markup(item), s['review_body']) for item in report.review_items]
    box = Table([[content]], colWidths=[CONTENT_WIDTH])
    box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), REVIEW_SURFACE),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
    ]))
    _, height = box.wrap(CONTENT_WIDTH, PAGE_HEIGHT)
    if height <= FRAME_HEIGHT * 0.5:
        return [Spacer(1, 32), box]
    title = ParagraphStyle('review_long_title', parent=s['review_title'], backColor=REVIEW_SURFACE,
                           borderPadding=(10, 16, 4, 16), leftIndent=16, rightIndent=16, keepWithNext=1)
    body = ParagraphStyle('review_long_body', parent=s['review_body'], backColor=REVIEW_SURFACE,
                          borderPadding=(4, 16, 4, 16), leftIndent=16, rightIndent=16, spaceAfter=6)
    return ([Spacer(1, 32), _p(markup(report.review_title, BODY_SEMI), title)]
            + [_p(markup(item), body) for item in report.review_items])


def _record(report: PhysicianReport, s: dict) -> list:
    if not report.record:
        return []
    labels = [_p(markup(item.label.upper(), BODY_SEMI), s['record_label']) for item in report.record]
    values = [_p(_value_or_absent(item.value, report), s['record_value']) for item in report.record]
    columns = len(report.record)
    table = _plain_table([labels, values], [CONTENT_WIDTH / columns] * columns,
                         [('RIGHTPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, 0), 4)])
    return [KeepTogether([Spacer(1, 22), table])]


def _quote_block(item: EvidenceItem, s: dict) -> list:
    """An exact quotation in an ivory box with its locator; a quotation too long for one box flows across pages."""
    quote = '“' + markup(item.quote) + '”'
    has_locator = _present(item.locator)
    rows = [[_p(quote, s['quote'])]]
    if has_locator:
        rows.append([_p(markup(item.locator, MONO_REGULAR), s['locator'])])
    box = Table(rows, colWidths=[CONTENT_WIDTH])
    box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), IVORY),
        ('BOX', (0, 0), (-1, -1), 0.75, RULE),
        ('LEFTPADDING', (0, 0), (-1, -1), 19),
        ('RIGHTPADDING', (0, 0), (-1, -1), 19),
        ('TOPPADDING', (0, 0), (-1, 0), 17),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 17),
        ('TOPPADDING', (0, 1), (-1, 1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 0 if has_locator else 17),
    ]))
    _, height = box.wrap(CONTENT_WIDTH, PAGE_HEIGHT)
    if height <= FRAME_HEIGHT * 0.45:
        return [Spacer(1, 10), box]
    text = quote
    if has_locator:
        text += f'<br/><font face="{MONO_REGULAR}" size="8" color="#53645E">{markup(item.locator, MONO_REGULAR)}</font>'
    return [_p(text, s['quote_long'])]


def _code_heading(index: int, row: CodeRow, s: dict) -> Table:
    text = markup(row.code, BODY_SEMI)
    if _present(row.label):
        text += '&nbsp;&nbsp;/&nbsp;&nbsp;' + markup(row.label, BODY_SEMI)
    heading = _plain_table([[_p(markup(f'{index:02d}', MONO_REGULAR), s['index']), _p(text, s['code_heading'])]],
                           [36, CONTENT_WIDTH - 36], [('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                                                      ('TOPPADDING', (0, 0), (-1, -1), 8)])
    return heading


def _evidence_flow(report: PhysicianReport, s: dict) -> list:
    # The evidence continues on a new page (the design's appendix page) unless more than half a page is left, so a
    # short case does not leave a page nearly empty.
    flow: list = [CondPageBreak(FRAME_HEIGHT * 0.5), Spacer(1, 22),
                  _p(markup(report.evidence_eyebrow.upper(), BODY_SEMI), s['eyebrow']),
                  _p(markup(report.evidence_title, DISPLAY), s['evidence_title']),
                  _p(markup(report.evidence_identity), s['identity'])]
    for index, row in enumerate(report.rows, start=1):
        # A heading is never left alone at the foot of a page. An unsplittable evidence box travels with it whole;
        # a long quotation (a paragraph, which can split) starts under it, and the page break before the heading
        # guarantees room for the heading and the first lines of that quotation.
        heading = _code_heading(index, row, s)
        _, heading_height = heading.wrap(CONTENT_WIDTH, FRAME_HEIGHT)
        blocks = [_quote_block(item, s) for item in row.evidence] or [[_p(markup(report.no_evidence_text), s['empty'])]]
        first = blocks[0]
        if any(isinstance(f, Paragraph) for f in first):
            flow += [CondPageBreak(heading_height + 90), heading, *first]
        else:
            flow += [CondPageBreak(130), KeepTogether([heading, *first])]
        for block in blocks[1:]:
            flow += block
        if _present(row.note):
            flow.append(_p(markup(row.note), s['note']))
        else:
            flow.append(Spacer(1, 12))
    return flow


def _notes_flow(report: PhysicianReport, s: dict) -> list:
    if not report.notes:
        return []
    flow: list = [_p(markup((report.notes_title or 'Notes').upper(), BODY_SEMI), s['notes_title']),
                  HorizontalRule(space_before=0, space_after=6)]
    flow += [Paragraph(markup(note), s['note_item'], bulletText='–') for note in report.notes]
    return flow


def _scope_and_closing(report: PhysicianReport, s: dict) -> list:
    flow: list = []
    if report.scope:
        rows = [[_p(markup(label, BODY_SEMI), s['scope_label']),
                 _p(markup(value), s['scope_attention'] if attention else s['scope_value'])]
                for label, value, attention in report.scope]
        table = _plain_table(rows, [CONTENT_WIDTH * 0.45, CONTENT_WIDTH * 0.55],
                             [('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)])
        flow += [Spacer(1, 14), _p('REVIEW SCOPE', s['section']), HorizontalRule(space_before=5, space_after=6),
                 table]
    if report.closing_title:
        flow += [_p(markup(report.closing_title, DISPLAY), s['closing_title']),
                 _p(markup(report.closing_text), s['closing_text'])]
    return [KeepTogether(flow)] if flow else []


def _story(report: PhysicianReport) -> list:
    s = _styles()
    story: list = [
        _p(markup(report.eyebrow.upper(), BODY_SEMI), s['eyebrow']),
        _p(markup(report.title, DISPLAY), s['title']),
        _p(markup(report.subtitle), s['subtitle']),
        _strip(report, s),
        Spacer(1, 22),
        _metrics(report, s),
        Spacer(1, 22),
        _section_heading(report.codes_heading, report.codes_side_note, s),
    ]
    if report.rows:
        story += [_code_row(i, row, report, s) for i, row in enumerate(report.rows, start=1)]
    else:
        story += [HorizontalRule(space_before=6, space_after=6), _p(markup(report.empty_rows_text), s['empty'])]
    story += _review_flow(report, s)
    story += _record(report, s)
    if report.rows:
        story += _evidence_flow(report, s)
    story += _notes_flow(report, s)
    story += _scope_and_closing(report, s)
    return story


def _canvas_maker(as_of: datetime | None):
    """A canvas whose PDF dates are the report's saved timestamp (or ReportLab's fixed invariant date)."""

    class ReportCanvas(Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if as_of is not None:
                moment = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
                stamp = TimeStamp(invariant=True)
                seconds = int(moment.timestamp())
                stamp.t = seconds
                stamp.lt = time.gmtime(seconds)
                stamp.YMDhms = tuple(stamp.lt)[:6]
                stamp.dhh = stamp.dmm = 0
                stamp.tzname = 'UTC'
                self._doc._timeStamp = stamp

    return ReportCanvas


def _build(report: PhysicianReport, total: int | None) -> tuple[bytes, int]:
    register_fonts()
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer, pagesize=letter, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=PAGE_HEIGHT - FRAME_TOP, bottomMargin=FRAME_BOTTOM,
        title=clean_text(report.document_title), author='QuillMD CPT Studio', subject='CPT coding summary',
        creator='QuillMD CPT Studio', producer='QuillMD CPT Studio', keywords='', invariant=1, pageCompression=1,
    )
    frame = Frame(MARGIN_X, FRAME_BOTTOM, CONTENT_WIDTH, FRAME_HEIGHT, id='body',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='report', frames=[frame], onPage=_Pages(report, total))])
    doc.build(_story(report), canvasmaker=_canvas_maker(report.as_of))
    return buffer.getvalue(), doc.page


def render_report(report: PhysicianReport) -> bytes:
    """The report as PDF bytes. Two passes: the first counts pages so every footer can say 'n of total'."""
    _, total = _build(report, None)
    data, pages = _build(report, total)
    if pages != total:  # footers are drawn outside the frame, so the flow cannot move between passes
        raise RuntimeError('page count changed between passes')
    return data
