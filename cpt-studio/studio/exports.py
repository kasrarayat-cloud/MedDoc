"""Customer exports (BUILD-SPEC 8): the physician PDF report, cpt-studio-customer-export@3, made from the encounter's
latest coding round.

- draft: every code line of the round with its status, units, modifiers, reason, the second check's verdict, its
  question and its quotes with their pages, and any current decision; then the round's questions and documentation
  notes.
- approved: only the lines whose current decision is approve and whose status is ready or needs_review (FIX-SPEC 1;
  customer.approved_lines), each with who approved it, their kind (human or agent) and when.
Units or modifiers the coding review did not give read "not given" - never a number or "none" it did not write.

The report is a PDF (owner directions of 2026-11-21: the doctor-facing report, and then the only one): drawn from the
snapshot below by studio.physician_report and studio.physician_pdf (searchable text, embedded fonts, US Letter), stored
once as an immutable ExportArtifact (fmt 'pdf') with its sha256 and one export.created audit row, and served as the
stored bytes. A request for any other format is refused (FORMATS). TXT and CSV exports made before that direction are
records: they stay stored, listed and downloadable exactly as made (CONTENT_TYPES still names their types); none is made
again. ExportArtifact.fmt's declared choices name only txt and csv; they are not a database constraint, and widening them
would be a field migration the installer refuses. A PDF that cannot be made is refused (NotMade) before anything is
stored: no empty or partial file is ever saved or served.

Release 1, C5: a request for a report that is still current by the page's own rule (customer.export_current: made from
the latest round, no decision on that round after it) returns the stored copy instead of rendering another - one
export.reused audit row records it - so clicks stop piling up copies of PHI; a new decision makes the next request render
a fresh one. The lock is the document's row alone (select_for_update(of=('self',))), so a report being made blocks no
other work in its practice. How many reports a member and a practice may ask for is studio.api's limit.

Release 1b, not built here (D402): F1's reports half - sealing ExportArtifact.content with studio.file_crypto.

Readiness: a draft needs the latest round done; the approved report needs a code of it approved (customer.readiness, the
rule the page shows). A request names the round the page shows (FIX-SPEC-2 section 5): one that is not the latest is
refused as changed, so a page left open never downloads a round its member did not see. An export made from an earlier
round stays listed and downloadable, marked earlier (customer.report_json). The text the coding review wrote passes
through the same display hygiene as the page (customer.shown).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from . import audit, customer, decisions, models, physician_report, state

Round, Export = models.CodingRound, models.ExportArtifact
DRAFT, APPROVED = Export.DRAFT, Export.APPROVED
KINDS = (DRAFT, APPROVED)
PDF = 'pdf'
FORMATS = (PDF,)  # what a new export may be made as (owner direction 2026-11-21: the PDF is the only report)
FORMAT_VERSION = 'cpt-studio-customer-export@3'
AGENT_LINE = 'Agent-executed synthetic review — not clinical approval'
# the stored formats served: the PDF, and the TXT and CSV exports made before 2026-11-21's direction, kept as records
CONTENT_TYPES = {PDF: 'application/pdf', Export.TXT: 'text/plain; charset=utf-8', Export.CSV: 'text/csv; charset=utf-8'}
INSURANCE_WORDS = {'medicare': 'Medicare', 'medicaid': 'Medicaid', 'commercial': 'Commercial or other',
                   'unknown': 'Not given'}
TRIGGER_WORDS = {Round.ANSWERS: ', after the practice answered questions', Round.RETRY: ', after a retry'}
NOTHING_YET = 'There is nothing to export yet.'
APPROVED_NOT_YET = 'The approved export is not available yet.'
ROUND_REQUIRED = 'Name the coding review the export is made from.'
FORMAT_REQUIRED = 'Choose a draft or an approved PDF report.'
PDF_NOT_MADE = 'The PDF could not be made. Nothing was saved. Try again.'


logger = logging.getLogger(__name__)


class NotMade(Exception):
    """The PDF could not be made; nothing was stored. ``message`` is the member's sentence."""

    def __init__(self, message=PDF_NOT_MADE):
        super().__init__(message)
        self.message = message


class NotReady(Exception):
    """The export asked for is not available now: ``message`` and the readiness ``blockers``."""

    def __init__(self, message, blockers):
        super().__init__(message)
        self.message, self.blockers = message, list(blockers)


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


# --- PDF ----------------------------------------------------------------------------------------------------------------

def render_pdf(snap, encounter, round_) -> bytes:
    """The physician PDF of ``snap``; NotMade when it cannot be made (only the error's type is logged: never its
    text, which could carry document words). physician_report and ReportLab are imported with this module, and the
    report fonts load at that import, so a broken library or a missing font fails the image phase's system check
    (manage.py check, whose URL check imports the API and so this module) and every request of an app started anyway,
    instead of only a doctor's download."""
    try:
        content = physician_report.render(snap, encounter=encounter, round_=round_)
    except Exception as exc:  # noqa: BLE001 - any failure refuses the export; nothing is stored
        logger.error('physician PDF not made for encounter %s round %s: %s', encounter.pk, round_.number,
                     type(exc).__name__)
        raise NotMade() from None
    if not isinstance(content, bytes) or not content.startswith(b'%PDF-') or b'%%EOF' not in content[-64:]:
        logger.error('physician PDF not made for encounter %s round %s: not a complete PDF', encounter.pk,
                     round_.number)
        raise NotMade()
    return content


# --- making and serving an export ------------------------------------------------------------------------------------------

def current_export(encounter, round_, kind, fmt):
    """The latest stored export of ``round_`` of this kind and format when it is still current
    (customer.export_current), or None. Its bytes are not read: the caller lists it."""
    latest = (Export.objects.filter(encounter_id=encounter.pk, round_id=round_.pk, kind=kind, fmt=fmt)
              .defer('content').order_by('-created_at', '-pk').first())
    if latest is None or not customer.export_current(latest, round_.pk, customer.last_decision_at(round_.pk)):
        return None
    return latest


def create(encounter, user, kind, fmt, *, round_number) -> models.ExportArtifact:
    """Make and store one export of the latest round, which must be round ``round_number`` - the one the page shows
    (any active member of the workspace may; the caller has scoped the encounter to the member), as a PDF - or, when
    one of that round, kind and format is still current, return it (``reused`` true on the answer, export.reused
    recorded). ValueError for an unknown kind or any format but the PDF; decisions.Refused (409, changed) for another
    round; NotReady when it is not available now; NotMade when the PDF cannot be made (nothing stored)."""
    if kind not in KINDS or fmt not in FORMATS:
        raise ValueError(FORMAT_REQUIRED)
    with transaction.atomic():
        # the document's row alone: never its practice's, so a report being made blocks no other work there (UP-4)
        locked = models.Encounter.objects.select_for_update(of=('self',)).select_related('workspace').get(
            pk=encounter.pk)
        round_ = state.latest_round(locked)
        if round_ is None or round_.number != round_number:
            raise decisions.Refused(409, decisions.ROUND_CHANGED)
        current = state.current_decisions(round_) if round_ is not None and round_.state == Round.DONE else {}
        ready = customer.readiness(round_, current)
        if not ready['draft']:
            raise NotReady(NOTHING_YET, ready['blockers'])
        if kind == APPROVED and not ready['approved']:
            raise NotReady(APPROVED_NOT_YET, ready['blockers'])
        stored = current_export(locked, round_, kind, fmt)
        if stored is not None:
            audit.record(locked.workspace, 'export.reused', encounter=locked, actor=user, export=str(stored.pk),
                         round=str(round_.pk), number=round_.number, kind=kind, fmt=fmt)
            stored.reused = True
            return stored
        now = timezone.now()
        snap = snapshot(locked, round_, current, kind, user, now)
        content = render_pdf(snap, locked, round_)
        stamp = now.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%S')
        export = Export.objects.create(
            encounter=locked, round=round_, kind=kind, fmt=fmt, filename=f'CPT-Studio-{kind}-r{round_.number}-{stamp}.{fmt}',
            content=content, sha256=hashlib.sha256(content).hexdigest(), created_by=user)
        audit.record(locked.workspace, 'export.created', encounter=locked, actor=user, export=str(export.pk),
                     round=str(round_.pk), number=round_.number, kind=kind, fmt=fmt)
    export.reused = False
    return export


def download(export) -> tuple:
    """(bytes, content type, file name) of a stored export, exactly as stored."""
    return bytes(export.content), CONTENT_TYPES.get(export.fmt, 'application/octet-stream'), export.filename
