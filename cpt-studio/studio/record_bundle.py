"""Returning a document's or a whole practice's data (release 1, D2; ORG-14 and REG-27 high, FLOW-19 (5), ORG-18).

    record_json(encounter, membership)   record.json: the document as the app shows it (customer.encounter_json, the very
                                         payload of GET /api/encounters/<id>), then every coding round - its codes with
                                         their quotes (the citations), questions and notes as the app shows them
                                         (customer.round_rows, questions_json, notes_json), the answers given to it, and
                                         every decision on it with who and when (customer.decision_json). The activity
                                         is the document's own (in the document block).
    bundle(encounter, membership)        one document's zip, built in memory: the original (or the pasted text), the
                                         converted PDF of a Word document, the latest report PDF, record.json and
                                         manifest.json (the sha256 of every file). TooLarge when it would pass
                                         settings.BUNDLE_MAX_BYTES, which keeps every answer inside the edge's in-memory
                                         buffers (A3). Served by studio.bundle_api.
    export_practice(workspace, folder)   a whole practice, for the end of its contract (export_workspace, a ruled act):
                                         one folder per document holding what its bundle holds - with every stored report
                                         - and a practice manifest in JSON and CSV listing documents, codes, decisions
                                         with who and when, answers and the practice's audit trail, with the sha256 of
                                         every file, and SHA256SUMS. Folders 0700, files 0600, written once. A
                                         failed export removes its folder (discard_export), as export_workspace does
                                         when the export's DisposalEvent cannot be written.

Every query is scoped to the one document it reads (encounter_id), or to the one practice: nothing of another document
or practice can enter a bundle or an export. Delivery of a practice's export - encrypted, through a time-limited link,
logged - is the termination runbook's step, not code (OWNER DECISION D14).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.utils import timezone

from . import customer, models, state
from .storage import read_own_original

FORMAT = 'cpt-studio-record-bundle@1'
PRACTICE_FORMAT = 'cpt-studio-practice-export@1'
TOO_LARGE = 'This document is too large for one bundle; download the original and the report separately.'
PDF_MEDIA = customer.PDF
STORED_SUFFIXES = ('.pdf', '.docx', '.zip')  # already compressed: stored as they are, never deflated again
Round, Decision, Answer, Export = models.CodingRound, models.CodeDecision, models.CodingAnswer, models.ExportArtifact


class TooLarge(Exception):
    """The bundle would pass settings.BUNDLE_MAX_BYTES (the API answers 413 with TOO_LARGE)."""


# --- record.json -------------------------------------------------------------------------------------------------------

def _answers(round_) -> list:
    """The answers given to ``round_``'s questions, in customer.answers_json's own shape."""
    rows = Answer.objects.filter(encounter_id=round_.encounter_id, round_id=round_.pk).select_related(
        'answered_by').order_by('answered_at', 'pk')
    return [{'question': customer.shown(row.question), 'answer': row.answer, 'by': row.answered_by.label(),
             'at': customer.iso(row.answered_at)} for row in rows]


def _decisions(round_) -> list:
    """Every decision on ``round_``, revoked ones included, in recording order: its line and code, then
    customer.decision_json (id, action, who, when, note)."""
    rows = Decision.objects.filter(encounter_id=round_.encounter_id, round_id=round_.pk).select_related(
        'reviewer').order_by('sequence')
    return [{'line': row.line, 'code': row.code, **customer.decision_json(row)} for row in rows]


def round_record(round_, can_review: bool) -> dict:
    context = round_.context if isinstance(round_.context, dict) else {}
    current = state.current_decisions(round_) if round_.state == Round.DONE else {}
    return {'number': round_.number, 'trigger': round_.trigger, 'state': round_.state,
            'created_at': customer.iso(round_.created_at), 'started_at': customer.iso(round_.started_at),
            'finished_at': customer.iso(round_.finished_at),
            'context': {'service_date': context.get('service_date'), 'insurance': context.get('insurance')},
            'error': round_.error or None,
            'codes': customer.round_rows(round_, current, can_review), 'questions': customer.questions_json(round_),
            'notes': customer.notes_json(round_), 'answers': _answers(round_), 'decisions': _decisions(round_)}


def record_json(encounter, membership, *, now=None) -> dict:
    """record.json of ``encounter`` for ``membership`` (anything with ``can_review``) - see the module."""
    now = now or timezone.now()
    can_review = bool(membership.can_review)
    rounds = Round.objects.filter(encounter_id=encounter.pk).order_by('number')
    return {'format': FORMAT, 'generated_at': customer.iso(now),
            'document': customer.encounter_json(encounter, membership, now=now),
            'rounds': [round_record(round_, can_review) for round_ in rounds]}


# --- the files of a document --------------------------------------------------------------------------------------------

def document_files(encounter, *, every_report=False) -> list:
    """[(path in the bundle, bytes)] of ``encounter``'s files: its original (the pasted text for a paste), the converted
    PDF of a Word document, and the latest report PDF (with ``every_report``, every stored export as stored). Every stored
    file is read through storage.read_own_original for the document's practice: storage.OriginalCorrupted - before any
    byte is read - for a name that is not one of that practice's own stored files (another practice's, a '..' path, a
    symbolic link), or when the bytes no longer match; OSError when it cannot be read."""
    files = []
    source = customer.original_file(encounter)
    if source is not None:
        files.append((f'original/{customer.safe_name(source.original_name)}',
                      read_own_original(encounter.workspace_id, source)))
        view = customer.converted_view(encounter) if source.media_type == customer.DOCX else None
        if view is not None:
            stem = (source.original_name or 'document').rsplit('.', 1)[0]
            data = read_own_original(encounter.workspace_id, SimpleNamespace(storage_name=view.view_pdf_storage_name,
                                                                             sha256=view.view_pdf_sha256))
            files.append((f'converted/{customer.safe_name(f"{stem}.pdf", "document.pdf")}', data))
    else:
        pasted = customer.view_content(encounter)  # a paste is viewed as its text: the document itself
        if pasted is not None:
            files.append(('original/pasted-text.txt', pasted[0]))
    exports = Export.objects.filter(encounter_id=encounter.pk).order_by('-created_at', '-pk')
    if not every_report:
        exports = exports.filter(fmt='pdf')[:1]
    for export in exports:
        name = customer.safe_name(export.filename, 'report')
        # every stored report in a practice export: two can share a name made in the same second, so each is named by
        # its id too
        files.append((f'reports/{export.pk}-{name}' if every_report else f'reports/{name}', bytes(export.content)))
    return files


def _json_bytes(value) -> bytes:
    return (json.dumps(value, indent=1, ensure_ascii=False) + '\n').encode('utf-8')


def _entry(path, data) -> dict:
    return {'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def _manifest(encounter, files, now) -> dict:
    return {'format': FORMAT, 'document': str(encounter.pk), 'generated_at': customer.iso(now),
            'files': [_entry(path, data) for path, data in files]}


def _zip_info(path, now) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=now.astimezone(timezone.get_default_timezone()).timetuple()[:6])
    info.compress_type = zipfile.ZIP_STORED if path.lower().endswith(STORED_SUFFIXES) else zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


def bundle(encounter, membership, *, now=None, max_bytes=None) -> bytes:
    """One document's zip (module docstring), at most ``max_bytes`` (settings.BUNDLE_MAX_BYTES), else TooLarge."""
    now = now or timezone.now()
    limit = settings.BUNDLE_MAX_BYTES if max_bytes is None else max_bytes
    files = document_files(encounter)
    files.append(('record.json', _json_bytes(record_json(encounter, membership, now=now))))
    if sum(len(data) for _, data in files) > 4 * limit:  # an outer bound: so large it is never even built
        raise TooLarge(TOO_LARGE)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for path, data in files:
            archive.writestr(_zip_info(path, now), data)
        archive.writestr(_zip_info('manifest.json', now), _json_bytes(_manifest(encounter, files, now)))
    data = buffer.getvalue()
    if len(data) > limit:
        raise TooLarge(TOO_LARGE)
    return data


# --- a whole practice ---------------------------------------------------------------------------------------------------

class ExportRefused(Exception):
    """The practice export cannot be written where it was asked to be (a fixed sentence)."""


class ExportKept(Exception):
    """A practice export that failed - or whose 'exported' DisposalEvent could not be written - could not be removed:
    a copy of the practice's data may remain in its folder (a fixed sentence). Said instead of "nothing was kept"."""


EXPORT_KEPT = ("its folder could not be removed: a complete or partial copy of the practice's data may remain in the "
               'export folder (--out). Remove it by hand.')


def _write(path: Path, data: bytes) -> dict:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def _csv(rows, fields) -> bytes:
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                         for key, value in row.items()})
    return text.getvalue().encode('utf-8')


def _audit_trail(workspace) -> list:
    """The practice's audit trail as the app names people: a member of the practice by their label, anyone else (a
    platform operator) as CPT Studio (customer.OPERATOR), as the document's activity does."""
    members = set(models.Membership.objects.filter(workspace_id=workspace.pk).values_list('user_id', flat=True))
    rows = models.AuditEvent.objects.filter(workspace_id=workspace.pk).select_related('actor').order_by(
        'created_at', 'pk')
    return [{'at': customer.iso(row.created_at), 'event': row.event,
             'document': str(row.encounter_id) if row.encounter_id else None,
             'by': row.actor.label() if row.actor_id in members else customer.OPERATOR,
             'data': row.data if isinstance(row.data, dict) else {}} for row in rows]


def export_practice(workspace, folder, *, now=None) -> dict:
    """Write ``workspace``'s export into ``folder`` (module docstring), which must not exist yet (its parent must):
    {'documents', 'files', 'bytes', 'manifest_sha256', 'encounter_ids', 'destroyed', 'reports', 'decisions', 'answers',
    'audit_rows'}. ExportRefused when the folder cannot be made."""
    now = now or timezone.now()
    root = Path(folder)
    if not root.is_absolute():
        raise ExportRefused('The export folder must be an absolute path.')
    try:
        root.mkdir(mode=0o700)
    except FileExistsError:
        raise ExportRefused('The export folder already exists; an export is written once, into a new folder.') from None
    except OSError as exc:
        raise ExportRefused(f'The export folder cannot be made ({type(exc).__name__}).') from None
    os.chmod(root, 0o700)
    try:
        return _export_into(workspace, root, now)
    except BaseException:
        # a half-written export is a stray copy of PHI: the folder this run made goes with it - or ExportKept says it
        # could not (raised from the failure)
        discard_export(root)
        raise


def discard_export(root) -> None:
    """Remove a practice export's folder - export_practice's own, which nothing else writes into (it did not exist
    before) - and everything in it: on a failure inside export_practice, and when the export's 'exported'
    DisposalEvent cannot be written (export_workspace; refutation failclosed-6). Every entry is tried, a symbolic link
    removed and never followed; ExportKept when the folder is still there afterwards, so "nothing was kept" is said
    only when it is true."""
    root = Path(root)
    try:
        entries = sorted(root.rglob('*'), key=lambda item: len(item.parts), reverse=True)
    except OSError:
        entries = []  # what cannot be listed is found below: the folder stays
    for path in entries:
        try:
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        except OSError:
            continue  # the others are removed all the same; the folder stays, and that is said
    try:
        root.rmdir()
    except OSError:
        pass  # gone already, or still there: said below
    if os.path.lexists(root):
        raise ExportKept(EXPORT_KEPT)


def _export_into(workspace, root: Path, now) -> dict:
    reader = SimpleNamespace(can_review=False)  # the practice's records, read as a viewer reads them
    every_file, codes, decisions, answers, documents = {}, [], [], [], []
    encounters = models.Encounter.objects.filter(workspace_id=workspace.pk).select_related(
        'current_revision').order_by('created_at', 'pk')
    (root / 'documents').mkdir(mode=0o700)
    exported, destroyed = [], []
    for encounter in encounters:
        if encounter.destroyed_at is not None:
            destroyed.append({'id': str(encounter.pk), 'destroyed_at': customer.iso(encounter.destroyed_at)})
            continue
        exported.append(str(encounter.pk))
        home = root / 'documents' / str(encounter.pk)
        home.mkdir(mode=0o700)
        files = document_files(encounter, every_report=True)
        record = record_json(encounter, reader, now=now)
        files.append(('record.json', _json_bytes(record)))
        written = []
        for path, data in files:
            target = home / path
            target.parent.mkdir(mode=0o700, exist_ok=True)
            written.append({'path': path, **_write(target, data)})
        manifest = {'format': FORMAT, 'document': str(encounter.pk), 'generated_at': customer.iso(now),
                    'files': written}
        written.append({'path': 'manifest.json', **_write(home / 'manifest.json', _json_bytes(manifest))})
        for item in written:
            every_file[f'documents/{encounter.pk}/{item["path"]}'] = item
        document = record['document']
        documents.append({'id': str(encounter.pk), 'folder': f'documents/{encounter.pk}', 'title': encounter.title,
                          'created_at': customer.iso(encounter.created_at), 'state': document['state'],
                          'service_date': document['context']['service_date'],
                          'insurance': document['context']['insurance'],
                          'files': [{'path': f'documents/{encounter.pk}/{item["path"]}', 'bytes': item['bytes'],
                                     'sha256': item['sha256']} for item in written]})
        for round_ in record['rounds']:
            for row in round_['codes']:
                codes.append({'document': str(encounter.pk), 'round': round_['number'], 'line': row['line'],
                              'code': row['code'], 'units': row['units'], 'modifiers': row['modifiers'],
                              'status': row['status'], 'decision': (row['decision'] or {}).get('action'),
                              'decided_by': (row['decision'] or {}).get('by'),
                              'decided_at': (row['decision'] or {}).get('at')})
            for row in round_['decisions']:
                decisions.append({'document': str(encounter.pk), 'round': round_['number'], **row})
            for row in round_['answers']:
                answers.append({'document': str(encounter.pk), 'round': round_['number'], **row})
    trail = _audit_trail(workspace)
    tables = {
        'documents.csv': (documents, ['id', 'folder', 'title', 'created_at', 'state', 'service_date', 'insurance']),
        'codes.csv': (codes, ['document', 'round', 'line', 'code', 'units', 'modifiers', 'status', 'decision',
                              'decided_by', 'decided_at']),
        'decisions.csv': (decisions, ['document', 'round', 'line', 'code', 'id', 'action', 'by', 'at', 'note']),
        'answers.csv': (answers, ['document', 'round', 'question', 'answer', 'by', 'at']),
        'audit.csv': (trail, ['at', 'event', 'document', 'by', 'data']),
    }
    for name, (rows, fields) in tables.items():
        every_file[name] = {'path': name, **_write(root / name, _csv(rows, fields))}
    manifest = {'format': PRACTICE_FORMAT, 'generated_at': customer.iso(now),
                'workspace': {'id': str(workspace.pk), 'name': workspace.name},
                'documents': documents, 'destroyed_documents': destroyed, 'codes': codes, 'decisions': decisions,
                'answers': answers, 'audit_trail': trail,
                'files': [{'path': path, 'bytes': item['bytes'], 'sha256': item['sha256']}
                          for path, item in sorted(every_file.items())]}
    manifest_bytes = _json_bytes(manifest)
    every_file['manifest.json'] = {'path': 'manifest.json', **_write(root / 'manifest.json', manifest_bytes)}
    sums = ''.join(f'{item["sha256"]}  {path}\n' for path, item in sorted(every_file.items()))
    _write(root / 'SHA256SUMS', sums.encode('utf-8'))
    return {'documents': len(exported), 'encounter_ids': exported, 'destroyed': len(destroyed),
            'files': len(every_file) + 1, 'bytes': sum(item['bytes'] for item in every_file.values()) + len(sums),
            'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'reports': sum(1 for path in every_file if '/reports/' in path), 'decisions': len(decisions),
            'answers': len(answers), 'audit_rows': len(trail)}
