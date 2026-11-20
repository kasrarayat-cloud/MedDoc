"""Customer exports (BUILD-SPEC 8): cpt-studio-customer-export@3, made from the encounter's latest coding round.

- draft: every code line of the round with its status, units, modifiers, reason, the second check's verdict, its
  question and its quotes with their pages, and any current decision; then the round's questions and documentation
  notes.
- approved: only the lines whose current decision is approve and whose status is ready or needs_review (FIX-SPEC 1;
  customer.approved_lines), each with who approved it, their kind (human or agent) and when.
Units or modifiers the coding review did not give read "not given" - never a number or "none" it did not write.
TXT opens and closes with the SYNTHETIC banner and states the encounter, the round, the date of service, the insurance
and when and by whom it was made. CSV (RFC 4180: every field quoted, quotes doubled, CRLF records, UTF-8) has the
columns kind, code, units, modifiers, status, reason, quotes, decision, decided_by, decided_at, a banner row after the
header (the SYNTHETIC line, and what the export was made from) and one closing the file; every cell a spreadsheet could
read as a formula is neutralised with a leading apostrophe. In both, control characters and the characters that
reorder or break a displayed line (C0 controls but TAB and LF, DEL, C1 controls, the bidirectional formatting controls,
the line and paragraph separators) are shown escaped: in the TXT a line break inside a value continues indented, so no
stored text can forge a line of the export; in the CSV a line break stays a line break inside its quoted cell (a CRLF
read as LF) and every other such character is escaped.

Readiness: a draft needs the latest round done; the approved export needs a code of it approved (customer.readiness, the
rule the page shows). Each export is stored once as an ExportArtifact (immutable) with its sha256; a download serves the
stored bytes. An export made from an earlier round stays listed and downloadable, marked earlier (customer.report_json).
The text the coding review wrote passes through the same display hygiene as the page (customer.shown).
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from . import audit, customer, models, state

Round, Export = models.CodingRound, models.ExportArtifact
DRAFT, APPROVED = Export.DRAFT, Export.APPROVED
KINDS = (DRAFT, APPROVED)
FORMATS = (Export.TXT, Export.CSV)
FORMAT_VERSION = 'cpt-studio-customer-export@3'
SYNTHETIC_LINE = 'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS'
HEADLINES = {DRAFT: 'CPT STUDIO — CODES — DRAFT, NOT APPROVED', APPROVED: 'CPT STUDIO — APPROVED CODES'}
TITLES = {DRAFT: 'Codes — not approved', APPROVED: 'Approved codes'}
AGENT_LINE = 'Agent-executed synthetic review — not clinical approval'
CSV_COLUMNS = ('kind', 'code', 'units', 'modifiers', 'status', 'reason', 'quotes', 'decision', 'decided_by',
               'decided_at')
CONTENT_TYPES = {Export.TXT: 'text/plain; charset=utf-8', Export.CSV: 'text/csv; charset=utf-8'}
INSURANCE_WORDS = {'medicare': 'Medicare', 'medicaid': 'Medicaid', 'commercial': 'Commercial or other',
                   'unknown': 'Not given'}
TRIGGER_WORDS = {Round.ANSWERS: ', after the practice answered questions', Round.RETRY: ', after a retry'}
DECISION_WORDS = {models.CodeDecision.APPROVE: 'approved', models.CodeDecision.REJECT: 'rejected'}
NOTHING_YET = 'There is nothing to export yet.'
APPROVED_NOT_YET = 'The approved export is not available yet.'
# Leading characters a spreadsheet may read as a formula (fullwidth forms and line starts included, beyond the minimum).
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r', '\n', '＝', '＋', '－', '＠')
# Shown escaped (\xNN, \uNNNN): what a terminal, printer or spreadsheet acts on (C0 controls but TAB and LF, DEL, C1
# controls) and what reorders or breaks how the rest of a line is displayed (the bidirectional formatting controls, the
# line and paragraph separators). The TXT turns the line breaks among them into continuation lines first (_join).
CONTROL = re.compile('[\x00-\x08\x0b-\x1f\x7f-\x9f\u061c\u200e\u200f\u2028\u2029\u202a-\u202e\u2066-\u2069]')
# A line break inside a stored value continues at least this deep: deeper than any structural line of the TXT.
CONTINUATION = '       '


class NotReady(Exception):
    """The export asked for is not available now: ``message`` and the readiness ``blockers``."""

    def __init__(self, message, blockers):
        super().__init__(message)
        self.message, self.blockers = message, list(blockers)


def _escaped(match) -> str:
    point = ord(match.group())
    return f'\\x{point:02x}' if point < 0x100 else f'\\u{point:04x}'


def visible(text: str) -> str:
    return CONTROL.sub(_escaped, text)


def visible_cell(text: str) -> str:
    """A CSV cell's text: a CRLF read as LF (a line break inside the quoted cell), every other character CONTROL names
    escaped."""
    return visible(text.replace('\r\n', '\n'))


def neutralise(value) -> str:
    """A cell a spreadsheet shows as text: a formula-leading character gets an apostrophe before it."""
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def _join(lines) -> str:
    out = []
    for line in lines:
        first, *rest = (visible(part) for part in (str(line).splitlines() or ['']))
        out.append(first)
        out += [part if part.startswith(CONTINUATION) else CONTINUATION + part for part in rest]
    return '\n'.join(out)


def _ts(value) -> str:
    return value.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if value else ''


# --- the snapshot ---------------------------------------------------------------------------------------------------------

def snapshot(encounter, round_, current, kind, user, now) -> dict:
    """Everything an export of ``round_`` shows, read from its stored rows (each line with its own decision)."""
    index = customer.citation_index(round_)
    approved = set(customer.approved_lines(round_, current))
    items = []
    for row in customer.line_rows(round_):
        if kind == APPROVED and row['line'] not in approved:
            continue
        decision = current.get(row['line'])
        shown = customer.code_json(row, index, decision, can_review=False)
        items.append({**shown, 'decided': decision})
    context = round_.context if isinstance(round_.context, dict) else {}
    service_date = context.get('service_date')
    return {'kind': kind, 'title': encounter.title, 'round': round_.number,
            'trigger': TRIGGER_WORDS.get(round_.trigger, ''), 'finished_at': _ts(round_.finished_at),
            'service_date': service_date if isinstance(service_date, str) and service_date else 'not given',
            'insurance': INSURANCE_WORDS.get(context.get('insurance'), 'Not given'),
            'generated_at': _ts(now), 'generated_by': user.label(), 'items': items,
            'questions': [item['text'] for item in customer.questions_json(round_)] if kind == DRAFT else [],
            'notes': customer.notes_json(round_) if kind == DRAFT else []}


NOT_GIVEN = 'not given'


def _modifiers(item) -> str:
    if item['modifiers'] is None:
        return NOT_GIVEN
    return ', '.join(item['modifiers']) if item['modifiers'] else 'none'


def _units(item) -> str:
    return str(item['units']) if item['units'] is not None else NOT_GIVEN


def _quote_words(quote) -> str:
    page = f'page {quote["page"]}' if quote['page'] else 'page not given'
    return f'"{quote["text"]}" ({page})'


def _check_words(item) -> str:
    check = item['second_check']
    verdict = {True: 'agrees', False: 'disagrees'}.get(check['agrees'], 'no verdict')
    return f'Second check: {verdict}.' + (f' {check["reason"]}' if check['reason'] else '')


def _decider(decision) -> str:
    return f'{decision.reviewer.label()} ({decision.reviewer_kind}) at {_ts(decision.created_at)}'


# --- TXT ----------------------------------------------------------------------------------------------------------------

def render_txt(snap) -> bytes:
    kind = snap['kind']
    lines = [SYNTHETIC_LINE, HEADLINES[kind], f'Export format: {FORMAT_VERSION}', f'Encounter: {snap["title"]}',
             f'Coding review: {snap["round"]}{snap["trigger"]}, finished {snap["finished_at"]}',
             f'Date of service: {snap["service_date"]}', f'Insurance: {snap["insurance"]}',
             f'Generated: {snap["generated_at"]} by {snap["generated_by"]}', '', TITLES[kind]]
    if not snap['items']:
        lines.append('   The coding review found no CPT code to report for this document.')
    for number, item in enumerate(snap['items'], start=1):
        decision = item['decided']
        if kind == APPROVED:
            lines.append(f'{number}. {item["code"]} — units {_units(item)} — modifiers: {_modifiers(item)}')
            lines.append(f'   Approved by {_decider(decision)}')
            if decision.reviewer_kind == models.User.AGENT:
                lines.append(f'   {AGENT_LINE}')
        else:
            lines.append(f'{number}. {item["code"]} — {item["status_label"]} — units {_units(item)} — modifiers: '
                         f'{_modifiers(item)}')
            if decision is not None:
                lines.append(f'   Decision: {DECISION_WORDS.get(decision.action, decision.action)} by '
                             f'{_decider(decision)}')
                if decision.reviewer_kind == models.User.AGENT and decision.action == models.CodeDecision.APPROVE:
                    lines.append(f'   {AGENT_LINE}')
        if item['reason']:
            lines.append(f'   Reason: {item["reason"]}')
        if kind == DRAFT:
            lines.append(f'   {_check_words(item)}')
            if item['question']:
                lines.append(f'   Question: {item["question"]}')
        for quote in item['quotes']:
            lines.append(f'   Quote: {_quote_words(quote)}')
    if snap['questions']:
        lines += ['', 'Questions for the practice', *[f'- {text}' for text in snap['questions']]]
    if snap['notes']:
        lines += ['', 'Documentation notes', *[f'- {text}' for text in snap['notes']]]
    return (_join(lines) + f'\n\n{SYNTHETIC_LINE}\n').encode('utf-8')


# --- CSV ----------------------------------------------------------------------------------------------------------------

def render_csv(snap) -> bytes:
    made = (f'Export format {FORMAT_VERSION}; encounter: {snap["title"]}; coding review {snap["round"]}'
            f'{snap["trigger"]}, finished {snap["finished_at"]}; date of service: {snap["service_date"]}; '
            f'insurance: {snap["insurance"]}; generated {snap["generated_at"]} by {snap["generated_by"]}')
    banner = {**dict.fromkeys(CSV_COLUMNS, ''), 'kind': SYNTHETIC_LINE, 'reason': made}
    rows = [banner]
    for item in snap['items']:
        decision = item['decided']
        reason = item['reason'] + (f' {_check_words(item)}' if snap['kind'] == DRAFT else '')
        rows.append({'kind': snap['kind'], 'code': item['code'], 'units': _units(item),
                     'modifiers': NOT_GIVEN if item['modifiers'] is None else ';'.join(item['modifiers']),
                     'status': item['status'], 'reason': reason.strip(),
                     'quotes': '\n'.join(_quote_words(quote) for quote in item['quotes']),
                     'decision': DECISION_WORDS.get(decision.action, '') if decision is not None else '',
                     'decided_by': decision.reviewer.label() if decision is not None else '',
                     'decided_at': _ts(decision.created_at) if decision is not None else ''})
    rows.append({**dict.fromkeys(CSV_COLUMNS, ''), 'kind': SYNTHETIC_LINE})
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow([neutralise(column) for column in CSV_COLUMNS])
    for row in rows:
        writer.writerow([neutralise(visible_cell(cell) if isinstance(cell, str) else cell)
                         for cell in (row[column] for column in CSV_COLUMNS)])
    return buffer.getvalue().encode('utf-8')


RENDERERS = {Export.TXT: render_txt, Export.CSV: render_csv}


# --- making and serving an export ------------------------------------------------------------------------------------------

def create(encounter, user, kind, fmt) -> models.ExportArtifact:
    """Make and store one export of the latest round (any active member of the workspace may; the caller has scoped
    the encounter to the member). ValueError for an unknown kind or format; NotReady when it is not available now."""
    if kind not in KINDS or fmt not in FORMATS:
        raise ValueError('Choose a draft or an approved export as TXT or CSV.')
    with transaction.atomic():
        locked = models.Encounter.objects.select_for_update().select_related('workspace').get(pk=encounter.pk)
        round_ = state.latest_round(locked)
        current = state.current_decisions(round_) if round_ is not None and round_.state == Round.DONE else {}
        ready = customer.readiness(round_, current)
        if not ready['draft']:
            raise NotReady(NOTHING_YET, ready['blockers'])
        if kind == APPROVED and not ready['approved']:
            raise NotReady(APPROVED_NOT_YET, ready['blockers'])
        now = timezone.now()
        content = RENDERERS[fmt](snapshot(locked, round_, current, kind, user, now))
        stamp = now.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%S')
        export = Export.objects.create(
            encounter=locked, round=round_, kind=kind, fmt=fmt, filename=f'CPT-Studio-{kind}-r{round_.number}-{stamp}.{fmt}',
            content=content, sha256=hashlib.sha256(content).hexdigest(), created_by=user)
        audit.record(locked.workspace, 'export.created', encounter=locked, actor=user, export=str(export.pk),
                     round=str(round_.pk), number=round_.number, kind=kind, fmt=fmt)
    return export


def download(export) -> tuple:
    """(bytes, content type, file name) of a stored export, exactly as stored."""
    return bytes(export.content), CONTENT_TYPES.get(export.fmt, 'application/octet-stream'), export.filename
