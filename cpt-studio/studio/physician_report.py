"""The physician PDF report's content: which saved facts reach the doctor-facing PDF, and in what words.

Owner directive of 2026-11-21 (the approved design handoff): the PDF is the primary doctor-facing export; CSV and TXT
stay. This module only chooses words; studio.physician_pdf draws them.

It reads the same snapshot as the TXT and CSV exports (exports.snapshot: the encounter's latest done coding round, each
line with its own current decision), so the PDF can never list a code, a decision or a quotation those exports would
not:
- a draft lists every code line of the round, in stored order, with its status and its current decision if it has one,
  then what still needs a decision (the round's questions and the lines without a saved decision) and its notes;
- an approved report lists only the lines whose current decision is approve (customer.approved_lines), each with who
  approved it and when, and says how many lines of the round it leaves out. An approval made by an automated agent
  carries exports.AGENT_LINE, exactly as the other exports do.
Nothing is inferred. The record has no patient identifier and no plain-language service label, so neither is printed; a
field the record does not hold prints as not recorded or not given, never a guess. A quotation is printed as stored: a
line's citations are the document's own words (pages where the document has pages); a line without citations falls back
to the coding review's own quotation, and the PDF says so. Text the coding review wrote has been through customer.shown
already (the snapshot's), so no vendor or model name reaches the PDF; no provider, run, usage or log field is read here.
Timestamps are UTC, in the page's convention ("21 Nov 2026, 14:02 UTC").

Making a report reads saved rows only; it writes nothing (exports.create stores the result as an ExportArtifact, like
the TXT and CSV, and records export.created).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from . import customer, decisions, models
from . import physician_pdf as pdf

DRAFT, APPROVED = models.ExportArtifact.DRAFT, models.ExportArtifact.APPROVED
FORMAT_VERSION = 'cpt-studio-customer-export@3'
AGENT_LINE = 'Agent-executed synthetic review — not clinical approval'
SYNTHETIC_FOOTER = 'Synthetic data · Not for billing or claims'
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
DECISION_WORDS = {models.CodeDecision.APPROVE: 'Approved', models.CodeDecision.REJECT: 'Rejected'}
NO_DECISION = 'No saved decision'
REVIEW_QUOTE = "The coding review's quotation, not checked against the document"
TEXT_LOCATOR = 'Text document · no page numbers'
# The insurance as saved. 'unknown' is stored both for the member's "Not sure" and for no answer at all, so it reads as
# the TXT export, the coding review's prompt and the review page say it: not given. Anything else is not recorded.
INSURANCE_WORDS = {'medicare': 'Medicare', 'medicaid': 'Medicaid', 'commercial': 'Commercial or other',
                   'unknown': 'Not given'}
NO_PAGE = 'Page not given'


def _day(value: date) -> str:
    return f'{value.day} {MONTHS[value.month - 1]} {value.year}'


def when(value) -> str | None:
    """A saved timestamp in the page's convention, UTC named: '21 Nov 2026, 14:02 UTC'."""
    if value is None:
        return None
    moment = value.astimezone(timezone.utc)
    return f'{_day(moment)}, {moment:%H:%M} UTC'


def service_day(value) -> str | None:
    """The saved date of service as the page shows it; the stored text itself if it is not a date; None if absent."""
    if not isinstance(value, str) or not value.strip() or value == 'not given':
        return None
    try:
        return _day(date.fromisoformat(value))
    except ValueError:
        return value


def said(text):
    """Text the coding review wrote, as the PDF prints it: cleaned of what is never printed (pdf.clean_text: controls
    become spaces, invisible format characters go) and THEN through customer.shown(), so an invisible character inside a
    vendor or model name cannot carry it past the name filter and be joined up again by the printing."""
    if not isinstance(text, str):
        return text
    return customer.shown(pdf.clean_text(text))


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def _encounter_ref(encounter) -> str:
    return encounter.pk.hex[:8].upper()


def _text_source(encounter) -> bool:
    """True when the document has no pages: pasted text or an uploaded text file."""
    source = customer.original_file(encounter)
    return source is None or source.media_type == customer.TEXT


def _source_words(encounter, round_) -> str:
    source = customer.original_file(encounter)
    name = source.original_name if source is not None and source.original_name else 'Pasted text'
    revision = getattr(round_, 'revision', None)
    number = getattr(revision, 'number', None)
    return f'{name} · revision {number}' if number else name


def _decision_words(decision) -> str:
    if decision is None:
        return NO_DECISION
    word = DECISION_WORDS.get(decision.action, decision.action)
    return f'{word} by {decision.reviewer.label()} · {when(decision.created_at)}'


def _modifier_words(modifiers) -> str:
    if modifiers is None:
        return 'Modifiers: not given'
    return 'Modifiers: ' + (', '.join(said(str(item)) for item in modifiers) if modifiers else 'none')  # model-written


def _row_state(item) -> str:
    decision = item['decided']
    if decision is not None:
        return DECISION_WORDS.get(decision.action, decision.action)
    if item['status'] == 'needs_answer':
        return 'Answer needed'
    if item['status'] in decisions.DECIDABLE:
        return 'Decision needed'
    return 'Not supported'


def _evidence(item, verified: bool, text_source: bool) -> tuple:
    out = []
    for quote in item['quotes']:
        page = quote.get('page')
        if page:
            locator = f'Page {page}'
        else:
            locator = TEXT_LOCATOR if text_source else NO_PAGE
        if not verified:
            locator = f'{REVIEW_QUOTE} · {locator}'
        # a citation is the document's own words, printed as cleaned; the fallback quotation is the coding review's
        out.append(pdf.EvidenceItem(quote=quote['text'] if verified else said(quote['text']), locator=locator))
    return tuple(out)


def _note(item, kind) -> str | None:
    parts = []
    if item['reason']:
        parts.append(f'Reason: {said(item["reason"])}')
    if kind == DRAFT:
        check = item['second_check']
        verdict = {True: 'agrees', False: 'disagrees'}.get(check['agrees'], 'no verdict')
        parts.append(f'Second check: {verdict}.' + (f' {said(check["reason"])}' if check['reason'] else ''))
        if item['question']:
            parts.append(f'Question: {said(item["question"])}')
    return ' '.join(parts) or None


def _reviewers(decided) -> str | None:
    labels = list(dict.fromkeys(decision.reviewer.label() for decision in decided))
    return ', '.join(labels) if labels else None


def build(snap: dict, *, encounter, round_, all_lines: int) -> pdf.PhysicianReport:
    """The report for ``snap`` (exports.snapshot of ``round_``); ``all_lines`` is how many code lines the round has."""
    kind = snap['kind']
    ref = _encounter_ref(encounter)
    number = snap['round']
    title = snap['title'] if pdf.clean_text(snap['title']).strip() else 'Untitled document'  # nothing printable: none
    index = customer.citation_index(round_)
    text_source = _text_source(encounter)
    items = snap['items']
    rows = []
    for position, item in enumerate(items, start=1):
        decision = item['decided']
        evidence = _evidence(item, bool(index.get(item['line'])), text_source)
        if kind == APPROVED:
            details = [when(decision.created_at), f'Line {item["line"]} · {_modifier_words(item["modifiers"])}']
            if decision.reviewer_kind == models.User.AGENT:
                details.append(AGENT_LINE)
            row = pdf.CodeRow(code=item['code'], caption='Approved code', label=f'Approved by {decision.reviewer.label()}',
                              details=tuple(details), status='Approved')
        else:
            details = [f'Line {item["line"]} · {_modifier_words(item["modifiers"])}']
            if decision is not None:
                details.append(_decision_words(decision))
            if decision is not None and decision.action == models.CodeDecision.APPROVE \
                    and decision.reviewer_kind == models.User.AGENT:
                details.append(AGENT_LINE)
            row = pdf.CodeRow(code=item['code'], caption='CPT suggestion', label=item['status_label'],
                              details=tuple(details), status=_row_state(item))
        rows.append(pdf.CodeRow(
            code=row.code, caption=row.caption, label=row.label, details=row.details,
            units=str(item['units']) if item['units'] is not None else None, status=row.status,
            evidence_ref=f'Evidence {position:02d}' if evidence else 'No excerpt', evidence=evidence,
            note=_note(item, kind)))

    decided = [item['decided'] for item in items if item['decided'] is not None]
    context = round_.context if isinstance(round_.context, dict) else {}
    approvals = [d for d in decided if d.action == models.CodeDecision.APPROVE]
    agent_approvals = [d for d in approvals if d.reviewer_kind == models.User.AGENT]
    strip = (pdf.LabelledValue('Document', title),
             pdf.LabelledValue('Date of service', service_day(snap['service_date'])),
             pdf.LabelledValue('Insurance', INSURANCE_WORDS.get(context.get('insurance'))),
             pdf.LabelledValue('Specialty', getattr(encounter.workspace.category, 'name', None) or None),
             pdf.LabelledValue('Encounter', ref))
    review_title, review_items, notes = None, (), ()
    if kind == APPROVED:
        latest = max((decision.created_at for decision in decided), default=None)
        left_out = max(all_lines - len(items), 0)
        metrics = ((f'{len(items):02d}', _plural(len(items), 'Approved code', 'Approved codes')),
                   (f'{left_out:02d}', 'Not approved, not listed'),
                   (_day(latest.astimezone(timezone.utc)) if latest else '—', 'Latest approval'))
        record = [pdf.LabelledValue('Approved by', _reviewers(decided)),
                  pdf.LabelledValue('Approval record', f'{len(items)} {_plural(len(items), "code", "codes")} approved'
                                                       f' · latest {when(latest)}' if latest else None)]
        subtitle = f'The codes approved in coding review {number}: only codes with a current approval are listed.'
        codes_heading, side = 'Approved codes', 'Only codes with a current saved approval'
        closing_title = 'A record of saved approvals.'
        closing_text = ('Only codes with a current approval in CPT Studio are listed, each with who approved it and when. '
                        'It is not a submitted claim. Synthetic data, not for billing or claims.')
        empty = 'No code of this coding review has a current approval.'
    else:
        undecided = [item for item in items if item['status'] in decisions.DECIDABLE and item['decided'] is None]
        questions = customer.questions_json(round_)
        # What still needs the practice, one entry per open item, as the page offers it: every question of the round
        # (answering one makes a new coding review, whatever the decisions on its lines) and every decidable line
        # without a saved decision. A line awaiting an answer is finished by answering the round's questions (the page
        # says so on the line), so it is an entry of its own only when the round has no question to answer. The count
        # and the status are read from this list.
        unasked = [] if questions else [item for item in items if item['status'] == 'needs_answer']
        open_entries = [f'Question: {said(question["text"])}' for question in questions]
        open_entries += [f'{item["code"]} ({item["line"]}) needs your answer'
                         + (f': {said(item["question"])}' if item['question'] else '.') for item in unasked]
        open_count = len(open_entries) + len(undecided)
        approved_count = sum(1 for d in decided if d.action == models.CodeDecision.APPROVE)
        rejected_count = sum(1 for d in decided if d.action == models.CodeDecision.REJECT)
        metrics = ((f'{len(items):02d}', _plural(len(items), 'Suggested code', 'Suggested codes')),
                   (f'{open_count:02d}', _plural(open_count, 'Open review item', 'Open review items')),
                   ('Pending' if open_count else 'Complete', 'Review status'))
        lines = list(open_entries)
        if undecided:
            codes = ', '.join(f'{item["code"]} ({item["line"]})' for item in undecided)
            lines.append(f'{len(undecided)} code {_plural(len(undecided), "line has", "lines have")} no saved decision: '
                         f'{codes}.')
        if lines:
            review_title, review_items = 'What still needs your decision', tuple(lines)
        notes = tuple(said(note) for note in snap['notes'])
        record = [pdf.LabelledValue('Reviewer', _reviewers(decided) or 'Not yet reviewed'),
                  pdf.LabelledValue('Approval record',
                                    f'{approved_count} approved · {rejected_count} rejected' if decided
                                    else 'No saved approval')]
        subtitle = f'The codes from coding review {number}, their evidence and what still needs your decision.'
        codes_heading, side = 'CPT suggestions', 'Status and saved decision of each line'
        closing_title = 'Prepared for a professional decision.'
        closing_text = ('This draft lists the coding review\'s suggestions and the decisions saved so far. It is not a '
                        'coding determination and not a claim: a qualified reviewer must assess each code before use. '
                        'Synthetic data, not for billing or claims.')
        empty = 'The coding review found no CPT code to report for this document.'
    if agent_approvals:
        # qualified unless the agent made every current decision: a human's approval or rejection beside its own
        # approvals makes the review a mixed one, whose agent approvals are marked on each code
        mixed = any(d.reviewer_kind != models.User.AGENT for d in decided)
        record.append(pdf.LabelledValue(
            'Review type', f'{AGENT_LINE} — {len(agent_approvals)} of {len(approvals)} approvals, marked on each code'
            if mixed else AGENT_LINE))
    quoted = [item for item in items if item['quotes']]
    every_cited = all(item['quotes'] and index.get(item['line']) for item in items)
    if every_cited and items:
        evidence_title = 'Every suggestion has a source.' if kind == DRAFT else 'Every approved code has a source.'
    else:
        evidence_title = 'The evidence for each code.'
    generated = snap.get('generated_at') or ''
    as_of = datetime.strptime(generated, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc) if generated else None
    scope = (('Source document', _source_words(encounter, round_), False),
             ('Coding review', f'Review {number}{snap["trigger"]}, finished {when_text(snap["finished_at"])}', False),
             _excerpt_scope(items, quoted, index),
             ('Prepared', f'{when(as_of) or "Not recorded"} by {snap["generated_by"]}', False),
             ('Report format', f'PDF · {FORMAT_VERSION}', False))
    identity = f'{title} · {ref} · Coding review {number}'
    agent_closing = ''
    if kind == APPROVED and agent_approvals:
        agent_closing = (f' {AGENT_LINE}.' if len(agent_approvals) == len(approvals) else
                         ' Approvals marked as agent-executed are synthetic reviews, not clinical approval.')
    return pdf.PhysicianReport(
        kind=pdf.APPROVED if kind == APPROVED else pdf.DRAFT,
        status_line='APPROVED CODES' if kind == APPROVED else 'DRAFT · REVIEW REQUIRED',
        identity_line=identity, header_title=title, header_suffix=f'{ref} · Coding review {number}',
        report_ref=f'CPT-{ref} · r{number}', footer_note=SYNTHETIC_FOOTER,
        eyebrow='The encounter, at a glance', title='Approved CPT codes' if kind == APPROVED else 'CPT coding summary',
        subtitle=subtitle, strip=strip, metrics=metrics, codes_heading=codes_heading, codes_side_note=side,
        rows=tuple(rows), empty_rows_text=empty, review_title=review_title, review_items=review_items,
        record=tuple(record), evidence_eyebrow='The reasons, in the record', evidence_title=evidence_title,
        evidence_identity=identity, no_evidence_text='No excerpt from the document was saved for this code.',
        scope=scope, closing_title=closing_title,
        closing_text=closing_text + agent_closing,
        document_title=f'CPT Studio {"approved codes" if kind == APPROVED else "draft codes"} {ref} r{number}',
        notes_title='Documentation notes', notes=notes, as_of=as_of)


def _excerpt_scope(items, quoted, index) -> tuple:
    """The review-scope row about the excerpts, true of the excerpts actually printed (none, unchecked or unpaged)."""
    if not items:
        return ('Source excerpts', 'No code was found, so none is shown', False)
    if not quoted:
        return ('Source excerpts', 'None was saved for these codes', True)
    cited = [item for item in quoted if index.get(item['line'])]
    if not cited:
        return ('Source excerpts', "The coding review's own quotations, not checked against the document", True)
    if len(cited) < len(quoted):
        return ('Source excerpts', "Exact words from the document; marked ones are the coding review's own quotation", True)
    paged = all(quote.get('page') for item in quoted for quote in item['quotes'])
    return ('Source excerpts', 'Exact words from the document' + (', with their pages' if paged else ''), False)


def when_text(stamp: str) -> str:
    """A snapshot timestamp ('2026-11-21T14:02:09Z') in the page's convention; 'not recorded' when empty."""
    if not stamp:
        return 'not recorded'
    return when(datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)) or 'not recorded'


def render(snap: dict, *, encounter, round_) -> bytes:
    """The PDF bytes of ``snap``. Reads saved rows only; calls no provider; writes nothing."""
    report = build(snap, encounter=encounter, round_=round_, all_lines=len(customer.line_rows(round_)))
    return pdf.render_report(report)
