"""Destroying one document or a whole practice's data (release 1, D1; PHY-9, ORG-18 and FLOW-19 blockers; REG-27).

A management command only (dispose), never an HTTP route, run through the installer's --phase manage as a ruled act with
a committed declaration (A6):

    close(workspace_id)   Workspace.closed_at set: no new upload and no coding (studio.intake, studio.jobs), and the
                          practice leaves the console's routine lists. Reading stays on: the practice keeps its access
                          until it confirms in writing that it received its data or chose destruction (ORG-18 (4)).
                          DisposalEvent 'closed'.
    plan(scope)           a dry run: the rows per table, the file counts and the sha256 manifest of the files in scope,
                          as a DisposalEvent 'planned'. Nothing else changes.
    execute(plan)         the plan carried out by two different people, one who runs it and one who approves it
                          (FLOW-19 (3); OWNER DECISION D14). Refused (Refused) during an install or a switch-back
                          (switch_in_progress), while a job, a round or a send in scope is open or a hold its runs set
                          still stands, for a practice that was not closed first, with a stale plan (older than
                          PLAN_MAX_AGE, or rows or files that changed since), and when a row outside the scope refers to
                          the scope (ORG-18 (1)). Then, in ONE transaction: raw SQL deletes every table that holds PHI
                          (DISPOSAL_TABLES), children first - the database's foreign keys are deferred, so no schema change
                          is needed, and they are checked before the commit (SET CONSTRAINTS ALL IMMEDIATE); the Encounter
                          rows stay as tombstones (title and values blanked, pointers null, destroyed_at set), beside the
                          audit rows, which hold no PHI (OWNER DECISION D25, recommended: kept); for a whole practice the
                          memberships are turned off, every account with no membership in another practice still open
                          and no operator grant gets an unusable password, is made inactive and has its sessions ended,
                          and the names on its sign-in rows are replaced by keyed hashes (user rows stay: audit rows name
                          them). After the
                          commit the files in scope are deleted, their folder synced and checked empty; VACUUM (ANALYZE)
                          runs on the tables touched (never VACUUM FULL on this host: it locks each table); the counts
                          prove nothing in scope remains; and a DisposalEvent 'completed' (or 'failed') is written. The
                          certificate (certificate()) holds ids, counts, digests and names of people only, and says what
                          the command cannot reach.
                          'failed' is written only once the transaction's commit was attempted: its counts say
                          rows_destroyed 'yes' (committed; a file, the folder or a count afterwards failed - every error
                          after the commit ends here, never as an escape) or 'unknown' (the commit's own answer was lost),
                          and files['remaining_names'] lists what was left. An interrupt after the commit (Ctrl-C, a stop
                          signal) ends the same way - recorded 'failed' and its certificate printed, as far as that can
                          be done - and then goes on as an interrupt. A transaction that rolled back writes nothing
                          (NotDestroyed: nothing was destroyed). To finish a failed or interrupted disposal, remove what
                          stopped it and plan the same scope again: the new plan takes in the files a run of the document
                          left (leftover_names: those its failed run recorded, and those its plan named), and a destroyed
                          document may be planned again while any of its files remains or its last run did not complete.
    replay(ledger)        after a restore from a backup older than a disposal, the ledger's disposals whose rows were
                          destroyed - 'completed', and 'failed' with rows_destroyed 'yes' - carried out again and its
                          missing rows written back (needed on the new server; PHY-9). A 'failed' one whose commit's
                          answer was lost ('unknown') may have destroyed nothing, so it is never carried out again: the
                          report lists it as a person's decision, and the person who decides to destroy the scope plans
                          it again and carries the plan out - that later entry, which a replay does carry out, is what
                          marks the first decided. Every entry's refusals - its files read too - are checked before
                          anything is destroyed, so a replay either refuses having changed nothing or goes on; one that
                          stops partway reports, entry by entry, what it destroyed. The ledger is what
                          ledger_lines() prints: one signed line per DisposalEvent, so a line that was changed, or not
                          written by this installation, is refused before anything is touched.

What a disposal keeps (OWNER DECISION D25, a question for counsel, and named in every certificate): the audit trail
(AuditEvent) of each destroyed document still holds its decisions' code and line values and the sha256 of its original
and of the requests sent; the read records (AccessRecord) name its id, who read it and when; and a practice export made
before the destruction links each document's id to its title, until that copy is destroyed under the termination
runbook. Values and hashes, never the document's text - but a trace, not none.

What is deliberately not here: shred (it cannot be verified on this kind of disk; ORG-18 (2)) - the real purge is a
cryptographic erase; and the destruction of a practice's file key (F1's crypto-erase), which is release 1b with the rest
of F1's wiring (nothing in release 1 seals a file, so no practice has a key).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone

from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from . import console, jobs, models, sessions, storage
from .maintenance import hashed_signin_name

log = logging.getLogger(__name__)

DisposalEvent, Encounter = models.DisposalEvent, models.Encounter
DOCUMENT, WORKSPACE = DisposalEvent.DOCUMENT, DisposalEvent.WORKSPACE
PLAN_MAX_AGE = timedelta(hours=24)
NAME_CHARS, REASON_CHARS, AUTHORIZATION_CHARS = 120, 2000, 200
TOMBSTONE_STATE = 'destroyed'  # Encounter.state of a tombstone: a fixed word, never a list state the page draws
# What the installer's --phase manage passes when it found no cpt-studio-web-next, -previous (or worker) container, so no
# install and no switch-back is under way (A6; Lane 6). Anything else, or nothing, refuses: the installer assumes no row
# is ever deleted while it runs (INSTALL.md 222-225; PHY-9).
SWITCH_STATE_VARIABLE, SWITCH_IDLE = 'CPT_STUDIO_SWITCH_STATE', 'idle'
LEDGER_SALT = 'studio.disposal.ledger'
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')

# Every table that holds PHI (ORG-18's list), children first, each with its path to the encounter it belongs to. A row is
# in scope when that path leads to an encounter in scope. Cycles (SourceRevision and Clarification, EncounterContext and
# Assessment, Encounter's own pointers) are why the order is "children first as far as there is one" and why the deferred
# foreign keys matter: they are checked once, after the last delete and before the commit.
DISPOSAL_TABLES = (
    (models.ToolCall, 'exchange__run__encounter'),
    (models.ProviderExchange, 'run__encounter'),
    (models.InterpreterHoldRelease, 'hold__run__encounter'),
    (models.InterpreterHold, 'run__encounter'),
    (models.ProviderHoldRelease, 'hold__run__encounter'),
    (models.ProviderHold, 'run__encounter'),
    (models.DecisionInvalidation, 'decision__encounter'),
    (models.Decision, 'encounter'),
    (models.MemberAnswerRevocation, 'answer__encounter'),
    (models.FindingConfirmation, 'encounter'),
    (models.Clarification, 'encounter'),
    (models.MemberAnswer, 'encounter'),
    (models.CodeDecision, 'encounter'),
    (models.CodingAnswer, 'encounter'),
    (models.ExportArtifact, 'encounter'),
    (models.ReportArtifact, 'encounter'),
    (models.Proposal, 'assessment__encounter'),
    (models.Job, 'encounter'),
    (models.Assessment, 'encounter'),
    (models.EncounterContext, 'encounter'),
    (models.EventInventory, 'encounter'),
    (models.RoutingRun, 'revision__encounter'),
    (models.CodingRound, 'encounter'),
    (models.ProviderRun, 'encounter'),
    (models.SourceRevision, 'encounter'),
    (models.SourceFile, 'encounter'),
)
# The models with a path to Encounter, SourceRevision or ProviderRun that a disposal keeps, and why. A model in neither
# list fails tests/test_disposal.py's model-graph test, so a new table cannot be forgotten.
KEPT_MODELS = {
    models.Encounter: 'the tombstone: title and values blanked, pointers null, destroyed_at set',
    models.AuditEvent: 'OWNER DECISION D25 (recommended): the audit rows hold no PHI and stay beside the tombstone',
}
CANNOT_REACH = (
    "Anthropic's copies of what was sent for coding, until its 30-day retention ends, unless zero data retention was "
    'expressly authorized.',
    "Deleted rows and the write-ahead log on the database's disk, until that volume is cryptographically erased. This "
    "host's disk is not encrypted, which is one reason it must never hold real PHI (PHY-13).",
    'Backups: none are taken on this host today (INSTALL.md). On the new server, every backup holding this data counts '
    'until it expires.',
    'The audit trail it keeps (OWNER DECISION D25, for counsel): the destroyed documents\' audit rows still hold their '
    'decisions\' code and line values and the sha256 of each original and of every request sent, and the read records '
    'name the document ids, who read them and when. Values and hashes, not the documents\' text, but not "no trace".',
    'A practice export made before the destruction (export_workspace) links each document id to its title, until that '
    'copy is destroyed under the termination runbook.',
)
MISFILED_REMINDER = ('A single misfiled document also starts the incident procedure and the breach assessment (ORG-18 '
                     "(3)): record it in the incident log and tell the practice whose document it was.")


class Refused(Exception):
    """The command declines; ``reasons`` are the sentences the operator reads (ids, counts and fixed words only)."""

    def __init__(self, *reasons):
        super().__init__(' '.join(reasons))
        self.reasons = list(reasons)


# --- who, why and under which authority ------------------------------------------------------------------------------------

def _clean(value, label, limit, *, required=True) -> str:
    text = ' '.join(str(value or '').split())
    if required and not text:
        raise Refused(f'{label} is required.')
    if len(text) > limit:
        raise Refused(f'{label} can be at most {limit} characters.')
    if UNSTORABLE.search(text):
        raise Refused(f'{label} contains a NUL character or an invalid Unicode code point.')
    return text


def name_as_recorded(value) -> str:
    """A person's name as it is recorded and compared: Unicode NFKC (a composed and a decomposed accent, a no-break and an
    ordinary space, a full-width and an ordinary letter are one spelling), every character no one can see or type removed
    (studio.console.hidden: format characters such as zero-width spaces and direction marks, controls, the
    default-ignorable ranges, blank glyphs) - then NFKC again, since a removed character can have stood between a letter
    and its accent - and runs of white space made one space."""
    text = unicodedata.normalize('NFKC', str(value or ''))
    text = ''.join(ch for ch in text if ch.isspace() or not console.hidden(ch))
    return ' '.join(unicodedata.normalize('NFKC', text).split())


SCRIPTS = ('LATIN', 'CYRILLIC', 'GREEK')  # their look-alike letters: one name never mixes two of them
# what a reader takes for an apostrophe, made ASCII's when two names are compared (a dash: Unicode category Pd, or MINUS)
APOSTROPHES = frozenset('\u0060\u00b4\u02b9\u02bb\u02bc\u02bd\u02c8\u055a\u05f3\u2018\u2019\u201b\u2032'
                        '\ua78c\uff07')
MINUS = '\u2212'


def scripts_of(name) -> set:
    """The scripts of SCRIPTS that ``name``'s letters are written in (by each letter's Unicode name)."""
    return {word for word in (unicodedata.name(ch, '').split(' ', 1)[0] for ch in name if ch.isalpha())
            if word in SCRIPTS}


def _plain_marks(text) -> str:
    """``text`` with every apostrophe (APOSTROPHES) and dash (category Pd, MINUS) variant made ASCII's ' and -."""
    return ''.join("'" if ch in APOSTROPHES else '-' if ch == MINUS or unicodedata.category(ch) == 'Pd' else ch
                   for ch in text)


def comparison_key(value) -> str:
    """How two given names are compared (two_people): apostrophe and dash variants made ASCII's - first, since NFKC
    splits an acute accent used as an apostrophe - then as recorded (name_as_recorded), accents and every other mark
    dropped (NFKD), case folded with the dotless i read as i (Turkish capitals and small letters match), white space
    collapsed. Generous on purpose: two people refused as one write fuller names; one person accepted as two defeats the
    rule."""
    text = name_as_recorded(_plain_marks(str(value or '')))
    text = _plain_marks(unicodedata.normalize('NFKD', text))
    text = ''.join(ch for ch in text if not unicodedata.category(ch).startswith('M'))
    return ' '.join(text.casefold().replace('\u0131', 'i').split())


def person(value, label='--by') -> str:
    """A named person (a ruled act's --by or --approved-by) as recorded (name_as_recorded): refused when nothing visible
    is left of it, when it is longer than NAME_CHARS, or when its letters mix two of the Latin, Cyrillic and Greek
    scripts, whose look-alike letters let one name read as another."""
    name = name_as_recorded(value)
    if not name:
        raise Refused(f'{label} is required: a person\'s name, with at least one visible character.')
    if len(name) > NAME_CHARS:
        raise Refused(f'{label} can be at most {NAME_CHARS} characters.')
    if len(scripts_of(name)) > 1:
        raise Refused(f'{label} mixes Latin, Cyrillic or Greek letters, which can make one name read as another; write '
                      'it in one script.')
    return name


def reason_text(value) -> str:
    """The reason, as read from its file (never argv): required, at most REASON_CHARS."""
    text = str(value or '').strip()
    if not text:
        raise Refused('The reason file is empty.')
    if len(text) > REASON_CHARS or UNSTORABLE.search(text):
        raise Refused(f'The reason can be at most {REASON_CHARS} characters, with no NUL character.')
    return text


def authorization(value, *, required) -> str:
    return _clean(value, '--authorization-ref', AUTHORIZATION_CHARS, required=required)


def two_people(by, approved_by):
    """(runner, approver), as recorded: two different named people (FLOW-19 (3)), compared by comparison_key - so two
    spellings of one name that read the same are one person - and neither name mixing scripts (person)."""
    runner, approver = person(by, '--by'), person(approved_by, '--approved-by')
    if comparison_key(by) == comparison_key(approved_by):
        raise Refused('The person who runs a destruction and the person who approves it must be two different people.')
    return runner, approver


def switch_in_progress() -> str:
    """'' when the installer said no install and no switch-back is under way, else the refusal's sentence. The answer
    comes from the installer (SWITCH_STATE_VARIABLE, which its --phase manage sets to SWITCH_IDLE only after finding no
    -next or -previous container): a command started any other way refuses (fail closed). The tests patch this."""
    state = os.environ.get(SWITCH_STATE_VARIABLE, '')
    if state == SWITCH_IDLE:
        return ''
    if not state:
        return ('The installer did not say that no install or switch-back is under way; a destruction runs only through '
                "the installer's --phase manage.")
    return 'An install or a switch-back is under way; a destruction waits until it has finished.'


# --- the scope ---------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Scope:
    """What a disposal covers: one document, or a whole practice (every document of it)."""
    kind: str
    workspace_id: uuid.UUID
    encounter_ids: tuple = field(default=())

    def encounters(self):
        """The scope's encounters as a subquery: the document's, or every one of the practice."""
        if self.kind == WORKSPACE:
            return Encounter._base_manager.filter(workspace_id=self.workspace_id).values('pk')
        return Encounter._base_manager.filter(pk__in=list(self.encounter_ids)).values('pk')

    def label(self) -> str:
        return f'practice {self.workspace_id}' if self.kind == WORKSPACE else f'document {self.encounter_ids[0]}'


def _uuid(value, label):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise Refused(f'{label} is not an id.') from None


def document_scope(encounter_id) -> Scope:
    encounter = Encounter._base_manager.filter(pk=_uuid(encounter_id, 'The document')).first()
    if encounter is None:
        raise Refused(f'No document has the id {encounter_id}.')
    return Scope(DOCUMENT, encounter.workspace_id, (encounter.pk,))


def workspace_scope(workspace_id) -> Scope:
    workspace = models.Workspace.objects.filter(pk=_uuid(workspace_id, 'The practice')).first()
    if workspace is None:
        raise Refused(f'No practice has the id {workspace_id}.')
    ids = tuple(sorted(Encounter._base_manager.filter(workspace_id=workspace.pk).values_list('pk', flat=True)))
    return Scope(WORKSPACE, workspace.pk, ids)


def scope_rows(model, scope):
    """The rows of ``model`` (one of DISPOSAL_TABLES) in ``scope``."""
    path = dict(DISPOSAL_TABLES)[model]
    return model._base_manager.filter(**{f'{path}__in': scope.encounters()})


def row_counts(scope) -> dict:
    """{table: rows in scope} for every table of DISPOSAL_TABLES."""
    return {model._meta.db_table: scope_rows(model, scope).count() for model, _ in DISPOSAL_TABLES}


def named_in_scope(scope) -> set:
    """The storage names the scope's rows name: its originals and its converted PDFs."""
    names = set(scope_rows(models.SourceFile, scope).values_list('storage_name', flat=True))
    names.update(scope_rows(models.CodingRound, scope).filter(view_pdf_storage_name__isnull=False)
                 .exclude(view_pdf_storage_name='').values_list('view_pdf_storage_name', flat=True))
    return names


def leftover_names(scope) -> set:
    """The files of a document a run of it left that are still on the disk: those a failed run recorded as left
    (files['remaining_names']), and those its plans named (files['names']) - for a run interrupted, or unrecorded,
    before it could say what it left. What a new plan of the document finishes; their rows are gone, so no row names
    them any more. A whole practice's left-overs lie in its folder, which its plan reads anyway: none here."""
    if scope.kind != DOCUMENT:
        return set()
    events = DisposalEvent.objects.filter(stage__in=(DisposalEvent.FAILED, DisposalEvent.PLANNED), scope=DOCUMENT,
                                          workspace_id=scope.workspace_id,
                                          encounter_ids__contains=[str(pk) for pk in scope.encounter_ids])
    found = set()
    for files in events.values_list('files', flat=True):
        for name in [*((files or {}).get('remaining_names') or ()), *((files or {}).get('names') or ())]:
            try:
                os.lstat(storage.stored_path(name))
            except FileNotFoundError:
                continue
            except storage.StoreRefused:
                pass  # refused below with every other name outside the practice's folder
            found.add(name)
    return found


def scope_files(scope) -> list:
    """Every file in scope, by storage name, sorted: the files its rows name, those a failed run of this scope left
    (leftover_names), and for a whole practice every entry of its folder (an upload that failed before release 1 can
    have left one no row names). Refused - nothing is destroyed that the command does not understand - for an entry of
    the folder that is not a regular file, and for any name outside the practice's own folder: a row of one practice that
    names another's file is a corrupted or crafted row, and the other practice's file is never destroyed for it."""
    names = named_in_scope(scope) | leftover_names(scope)
    foreign = [name for name in names if not storage.in_practice_folder(scope.workspace_id, name)]
    if foreign:
        raise Refused(f'{len(foreign)} file name(s) in scope lie outside the practice\'s own folder, or are no stored '
                      'file\'s name; nothing was destroyed.')
    if scope.kind == WORKSPACE:
        folder = storage.workspace_folder(scope.workspace_id)
        for name, kind in storage.folder_entries(folder):
            if kind != storage.FILE:
                raise Refused(f"The practice's folder holds an entry that is not a stored file ({kind}); it was left "
                              'as it is, and nothing was destroyed.')
            names.add(f'{scope.workspace_id}/{name}')
    return sorted(names)


def manifest(names) -> list:
    """[{name, bytes, sha256}] of every file in ``names``, read from the disk ('' and None for one that is missing)."""
    entries = []
    for name in names:
        try:
            path = storage.stored_path(name)
            size, digest = storage.file_digest(path)
        except FileNotFoundError:
            size, digest = None, ''
        except storage.StoreRefused:
            raise Refused('A file in scope is named outside the original store; nothing was destroyed.') from None
        except OSError as exc:
            raise Refused(f'A file in scope cannot be read ({type(exc).__name__}); nothing was destroyed.') from None
        entries.append({'name': name, 'bytes': size, 'sha256': digest})
    return entries


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def manifest_digest(entries) -> str:
    return hashlib.sha256(canonical(entries)).hexdigest()


def file_counts(entries) -> dict:
    present = [entry for entry in entries if entry['bytes'] is not None]
    return {'files': len(present), 'bytes': sum(entry['bytes'] for entry in present),
            'missing': len(entries) - len(present)}


# --- the refusals ----------------------------------------------------------------------------------------------------------

def open_work(scope, *, holds_only=False) -> list:
    """Sentences for whatever in scope is still under way: a queued or running job or round, a send reserved or in
    flight, or a hold one of its runs set that no release ended (deleting it would lift an installation-wide hold).
    ``holds_only``: the holds alone - a replay, which runs only while the worker is stopped, so a queued or running row of
    a restored database is no work in progress and is destroyed with the rest."""
    found = []
    checks = (
        (scope_rows(models.Job, scope).filter(state__in=(models.Job.QUEUED, models.Job.RUNNING)),
         'job(s) are queued or running'),
        (scope_rows(models.CodingRound, scope).filter(state__in=(models.CodingRound.QUEUED, models.CodingRound.RUNNING)),
         'coding round(s) are queued or running'),
        (scope_rows(models.ProviderRun, scope).filter(state__in=(models.ProviderRun.RESERVED, models.ProviderRun.SENDING)),
         'send(s) are reserved or in flight'),
        (scope_rows(models.InterpreterHold, scope).filter(release__isnull=True),
         'coding hold(s) set by its runs still stand; release them first'),
        (scope_rows(models.ProviderHold, scope).filter(release__isnull=True),
         'provider hold(s) set by its runs still stand; release them first'),
    )
    for rows, words in checks[3:] if holds_only else checks:
        count = rows.count()
        if count:
            found.append(f'{count} {words}.')
    return found


def outside_references(scope) -> list:
    """Every foreign key of any model whose rows outside the scope point at a row the disposal would delete (ORG-18
    (1)), as (table, column, rows). The tombstones are in scope: their pointers are nulled in the same transaction."""
    deleted = {model: scope_rows(model, scope).values('pk') for model, _ in DISPOSAL_TABLES}
    found = []
    for model in apps.get_models():
        for fk in model._meta.concrete_fields:
            if not (fk.many_to_one or fk.one_to_one) or fk.related_model not in deleted:
                continue
            referring = model._base_manager.filter(**{f'{fk.name}__in': deleted[fk.related_model]})
            if model in deleted:
                referring = referring.exclude(pk__in=deleted[model])
            elif model is Encounter:
                referring = referring.exclude(pk__in=scope.encounters())
            count = referring.count()
            if count:
                found.append((model._meta.db_table, fk.column, count))
    return found


def files_named_outside(scope, names) -> int:
    """How many rows outside the scope name a file in scope (it would be deleted under them)."""
    names = list(names)
    sources = models.SourceFile._base_manager.filter(storage_name__in=names).exclude(
        pk__in=scope_rows(models.SourceFile, scope).values('pk')).count()
    views = models.CodingRound._base_manager.filter(view_pdf_storage_name__in=names).exclude(
        pk__in=scope_rows(models.CodingRound, scope).values('pk')).count()
    return sources + views


def refusals(scope, names=None, *, holds_only=False, closed_required=True) -> list:
    """Every reason ``scope`` cannot be destroyed now (the install check and the plan's age are the caller's).
    ``closed_required`` False: a replay's check before it starts, whose destruction closes the practice itself."""
    reasons = []
    if closed_required and scope.kind == WORKSPACE and not models.Workspace.objects.filter(
            pk=scope.workspace_id, closed_at__isnull=False).exists():
        reasons.append('The practice was not closed first (dispose --close); its whole data is destroyed only after '
                       'that.')
    reasons += open_work(scope, holds_only=holds_only)
    for table, column, count in outside_references(scope):
        reasons.append(f'{count} row(s) of {table} outside the scope refer to it through {column}.')
    if names is not None and files_named_outside(scope, names):
        reasons.append('A file in scope is also named by a row outside the scope.')
    return reasons


# --- close and plan --------------------------------------------------------------------------------------------------------

def close(workspace_id, *, by, reason, authorization_ref='') -> DisposalEvent:
    """Close the practice (module docstring): Workspace.closed_at and a DisposalEvent 'closed', in one transaction."""
    by, reason = person(by), reason_text(reason)
    authorization_ref = authorization(authorization_ref, required=False)
    with transaction.atomic():
        workspace = models.Workspace.objects.select_for_update().filter(pk=_uuid(workspace_id, 'The practice')).first()
        if workspace is None:
            raise Refused(f'No practice has the id {workspace_id}.')
        if workspace.closed_at is not None:
            raise Refused(f'The practice was already closed at {iso_time(workspace.closed_at)}; nothing was recorded.')
        now = timezone.now()
        models.Workspace.objects.filter(pk=workspace.pk).update(closed_at=now)
        return DisposalEvent.objects.create(
            stage=DisposalEvent.CLOSED, scope=WORKSPACE, workspace_id=workspace.pk, reason=reason, run_by=by,
            authorization_ref=authorization_ref,
            counts={'documents': Encounter._base_manager.filter(workspace_id=workspace.pk).count()})


def plan(scope, *, by, reason, authorization_ref='') -> DisposalEvent:
    """The dry run (module docstring): refused for whatever execute would refuse but the install and the plan's age; else
    one DisposalEvent 'planned' holding the rows, the file counts and the manifest's digest. The manifest itself is
    plan_manifest(event)."""
    by, reason = person(by), reason_text(reason)
    authorization_ref = authorization(authorization_ref, required=False)
    names = scope_files(scope)
    reasons = refusals(scope, names)
    rows = row_counts(scope)
    if scope.kind == DOCUMENT and Encounter._base_manager.filter(pk__in=scope.encounter_ids,
                                                                 destroyed_at__isnull=False).exists():
        if not names and not any(rows.values()) and not last_run_unfinished(scope):
            reasons.insert(0, 'This document was already destroyed, and nothing of it remains.')
    if reasons:
        raise Refused(*reasons)
    entries = manifest(names)
    return DisposalEvent.objects.create(
        stage=DisposalEvent.PLANNED, scope=scope.kind, workspace_id=scope.workspace_id,
        encounter_ids=[str(pk) for pk in scope.encounter_ids],
        counts={'rows': rows, 'documents': len(scope.encounter_ids)},
        files={**file_counts(entries), **({'names': names} if scope.kind == DOCUMENT else {})},
        manifest_digest=manifest_digest(entries), reason=reason, run_by=by, authorization_ref=authorization_ref)


def last_run_unfinished(scope) -> bool:
    """Whether the scope's latest plan or run event is not a completed run: a failed run, or a plan whose run left no
    event (interrupted, or its event unwritten) - so a destroyed document may be planned again, and every run can end
    in a record."""
    runs = DisposalEvent.objects.filter(stage__in=(DisposalEvent.PLANNED, DisposalEvent.COMPLETED, DisposalEvent.FAILED),
                                        workspace_id=scope.workspace_id, scope=scope.kind)
    if scope.kind == DOCUMENT:
        runs = runs.filter(encounter_ids__contains=[str(pk) for pk in scope.encounter_ids])
    return runs.order_by('-created_at', '-pk').values_list('stage', flat=True).first() in (DisposalEvent.PLANNED,
                                                                                         DisposalEvent.FAILED)


def plan_manifest(event) -> list:
    """The manifest a plan's digest is of, read again (the files as they are now)."""
    return manifest(scope_files(_scope_of(event)))


def _scope_of(event) -> Scope:
    if event.scope == WORKSPACE:
        return workspace_scope(event.workspace_id)
    return Scope(DOCUMENT, event.workspace_id, tuple(uuid.UUID(pk) for pk in event.encounter_ids))


# --- the destruction --------------------------------------------------------------------------------------------------------

YES, UNKNOWN = 'yes', 'unknown'  # counts['rows_destroyed'] of a run whose commit was attempted (see the module)
# a replay item's status besides a stage: an 'unknown' entry a person must decide, or one decided or with nothing left;
# a run stopped by an interrupt
DECIDE, DECIDED, INTERRUPTED = 'needs a person\'s decision', 'decided', 'interrupted'


@dataclass
class Outcome:
    """What one destruction did: rows deleted per table, tombstones, the practice's accounts, the files, the vacuum - and
    whether its rows were destroyed ('yes' once committed, 'unknown' when the commit's own answer was lost) and what
    failed after the commit (``problems``: fixed words, the step and the error's type)."""
    deleted: dict
    tombstones: int
    accounts: dict
    entries: list
    rows_destroyed: str = YES
    files_deleted: int = 0
    files_remaining: int = 0
    remaining_names: list = field(default_factory=list)
    vacuum: str = ''
    remaining_rows: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)
    interrupted: BaseException | None = None  # what stopped the run after the commit (Ctrl-C, a stop signal): raised again

    @property
    def complete(self) -> bool:
        return (self.rows_destroyed == YES and not self.problems and not self.files_remaining
                and not any(self.remaining_rows.values()) and self.interrupted is None)


class CommitUnknown(Exception):
    """The destruction's commit failed: whether its rows were destroyed is not known (``outcome`` says 'unknown'). Its
    files were not touched. It is recorded 'failed', and a replay carries it out again."""

    def __init__(self, outcome):
        super().__init__('the commit of the destruction failed')
        self.outcome = outcome


class NotDestroyed(Exception):
    """The destruction stopped before its commit, on an error that is no refusal: the transaction rolled back, and
    nothing was destroyed (the sentence says so, with the error's type)."""


class Unrecorded(Exception):
    """A destruction ran, but its DisposalEvent could not be written: ``text`` is its certificate, the only record."""

    def __init__(self, text):
        super().__init__('the DisposalEvent of a destruction could not be written')
        self.text = text


def _delete_rows(model, scope) -> int:
    """Delete the rows of ``model`` in scope with one raw SQL statement (the ORM's own guard refuses deletes of the
    immutable tables, and SourceRevision refuses them on its own): DELETE ... WHERE pk IN (the scope's rows)."""
    query = scope_rows(model, scope).values('pk').query
    subquery, params = query.sql_with_params()
    quote = connection.ops.quote_name
    sql = f'DELETE FROM {quote(model._meta.db_table)} WHERE {quote(model._meta.pk.column)} IN ({subquery})'
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


def _tombstone(scope, now) -> int:
    """The scope's encounters kept as tombstones: no title, no values, no pointers, destroyed_at set (once)."""
    rows = Encounter._base_manager.filter(pk__in=scope.encounters())
    first = rows.filter(destroyed_at__isnull=True).update(destroyed_at=now)
    rows.update(title='', user_values={}, current_revision=None, current_context=None, current_assessment=None,
                state=TOMBSTONE_STATE, updated_at=now)
    return first


def _close_accounts(workspace_id) -> dict:
    """A whole practice's people (module docstring): memberships off; every account that holds no membership in another
    practice that is still open (Workspace.closed_at unset) - active or turned off: a practice turns a person's access
    off by its membership alone (C4), and turning it on again must still work - and no operator grant is made unusable
    and inactive, its sessions ended and the names on its sign-in rows hashed. A closed practice keeps no account: once
    every practice of a person is closed, the disposal of any of them ends the account."""
    memberships = models.Membership.objects.filter(workspace_id=workspace_id)
    users = list(models.User.objects.filter(memberships__workspace_id=workspace_id).distinct().order_by('pk'))
    off = memberships.filter(active=True).update(active=False)
    closed, kept, ended = [], 0, 0
    for user in users:
        elsewhere = models.Membership.objects.filter(user_id=user.pk, workspace__closed_at__isnull=True).exclude(
            workspace_id=workspace_id).exists()
        operator = models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True).exists()
        if elsewhere or operator:
            kept += 1
            continue
        user.set_unusable_password()
        user.is_active = False
        user.save(update_fields=['password', 'is_active'])
        try:
            ended += sessions.end_sessions(user)
        except sessions.Refused as exc:  # a session store the console cannot end: nothing is destroyed
            raise Refused(str(exc)) from None
        closed.append(user)
    closed_ids = [user.pk for user in closed]
    hashed = 0
    for user in closed:
        shared = models.User.objects.filter(username__iexact=user.username).exclude(pk__in=closed_ids).exists()
        rows = models.LoginAttempt.objects.filter(
            **({'username': user.username} if shared else {'username__iexact': user.username}))
        hashed += rows.update(username=hashed_signin_name(user.username))
    return {'memberships_off': off, 'accounts_off': len(closed), 'accounts_kept': kept, 'sessions_ended': ended,
            'signin_names_hashed': hashed}


def _vacuum(tables) -> str:
    """VACUUM (ANALYZE) of the tables touched: 'done', 'failed' (logged by type), or 'skipped' inside a transaction
    (VACUUM cannot run in one; the command never runs in one, a test case does)."""
    if connection.in_atomic_block:
        return 'skipped'
    quote = connection.ops.quote_name
    try:
        with connection.cursor() as cursor:
            cursor.execute('VACUUM (ANALYZE) ' + ', '.join(quote(table) for table in sorted(set(tables))))
    except Exception as exc:  # noqa: BLE001 - the rows are gone; the dead tuples wait for autovacuum
        log.error('VACUUM (ANALYZE) after a disposal failed (%s)', type(exc).__name__)
        return 'failed'
    return 'done'


def touched_tables(scope) -> list:
    tables = [model._meta.db_table for model, _ in DISPOSAL_TABLES] + [Encounter._meta.db_table]
    if scope.kind == WORKSPACE:
        tables += [models.Membership._meta.db_table, models.User._meta.db_table, models.LoginAttempt._meta.db_table,
                   'django_session']
    return tables


def _problem(outcome, step, exc):
    """Record what failed after the commit - the step and the error's type, fixed words - and log it the same way."""
    word = f'{step}: {type(exc).__name__}'
    if word not in outcome.problems:
        outcome.problems.append(word)
        log.error('a disposal step after the commit failed (%s)', word)


def _remove_files(scope, outcome) -> None:
    """After the commit: delete every file of the manifest - each on its own, so one that cannot be removed never keeps
    the others - sync each folder, check that none remains, and for a whole practice that its folder is empty, then
    remove it. What is left is counted and named in ``outcome``. An error of any step but a file's own deletion goes on
    to the one guard in _after_commit."""
    names = [entry['name'] for entry in outcome.entries]
    folders = set()
    for name in names:
        folders.add(storage.stored_path(name).parent)
        try:
            if storage.delete_stored(name):
                outcome.files_deleted += 1
        except (OSError, storage.StoreRefused) as exc:
            _problem(outcome, 'delete', exc)  # counted below as left
    for folder in folders:
        storage.sync_folder(folder)
    left = []
    for name in names:
        try:
            os.lstat(storage.stored_path(name))
        except FileNotFoundError:
            continue
        left.append(name)
    if scope.kind == WORKSPACE:
        folder = storage.workspace_folder(scope.workspace_id)
        entries = storage.folder_entries(folder)
        left += [f'{scope.workspace_id}/{name}' for name, _ in entries if f'{scope.workspace_id}/{name}' not in names]
        if not entries:
            storage.remove_empty_folder(folder)
    outcome.remaining_names = sorted(set(left))
    outcome.files_remaining = len(outcome.remaining_names)


def _left_on_disk(scope, outcome) -> list:
    """What is left of the manifest when the file steps stopped on an error, as far as it can be told: a file that cannot
    be checked counts as left. Never raises."""
    left = set(outcome.remaining_names)
    for entry in outcome.entries:
        try:
            os.lstat(storage.stored_path(entry['name']))
        except FileNotFoundError:
            continue
        except Exception:  # noqa: BLE001 - what cannot be checked counts as left
            pass
        left.add(entry['name'])
    if scope.kind == WORKSPACE:
        try:
            left.update(f'{scope.workspace_id}/{name}'
                        for name, _ in storage.folder_entries(storage.workspace_folder(scope.workspace_id)))
        except Exception:  # noqa: BLE001 - the folder cannot be read: its problem is recorded already
            pass
    return sorted(left)


def _count_left(scope, outcome) -> None:
    outcome.remaining_names = _left_on_disk(scope, outcome)
    outcome.files_remaining = len(outcome.remaining_names)


def _after_commit(scope, outcome) -> None:
    """Everything after the commit - the files, the vacuum, the counts that prove nothing remains. The rows are gone, so
    nothing here escapes the record: an error is recorded in ``outcome`` and the next step goes on; an interrupt (Ctrl-C,
    a stop signal: any BaseException) is recorded too, the steps left are skipped, and it is kept in
    ``outcome.interrupted`` for _run to raise again once the run is recorded. Either way the run ends 'failed', with
    what is known."""
    def files():
        _remove_files(scope, outcome)

    def vacuum():
        outcome.vacuum = _vacuum(touched_tables(scope))

    def counts():
        outcome.remaining_rows = {table: count for table, count in row_counts(scope).items() if count}

    for step, action in (('files', files), ('vacuum', vacuum), ('counts', counts)):
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - the one guard: an error after the commit never escapes the record
            _problem(outcome, step, exc)
            if step == 'files':
                _count_left(scope, outcome)
        except BaseException as exc:  # noqa: BLE001 - an interrupt: recorded, the steps left skipped, raised again by _run
            outcome.interrupted = exc
            _problem(outcome, step, exc)
            _count_left(scope, outcome)
            return


def destroy(scope, *, expected=None, holds_only=False, close=False) -> Outcome:
    """Destroy ``scope`` (module docstring). ``expected``: the plan's {'rows', 'documents', 'digest'}, checked again
    under the locks; Refused (nothing changed) when it differs, or for any refusal (``holds_only``: open_work's).
    ``close``: close the practice in the same transaction first (a replay). The caller checks the install. Once the
    commit is attempted: an Outcome (whatever failed afterwards is in it), or CommitUnknown when the commit's own answer
    was lost; an error before it rolls the transaction back and goes on as it is."""
    marks = {'committing': False}
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:  # whatever this session set before: the deletes rely on deferral
                cursor.execute('SET CONSTRAINTS ALL DEFERRED')
            if scope.kind == WORKSPACE:
                models.Workspace.objects.select_for_update().filter(pk=scope.workspace_id).first()
                if close:
                    models.Workspace.objects.filter(pk=scope.workspace_id, closed_at__isnull=True).update(
                        closed_at=timezone.now())
            locked = list(Encounter._base_manager.select_for_update().filter(pk__in=scope.encounters())
                          .order_by('pk').values_list('pk', flat=True))
            if scope.kind == WORKSPACE:
                scope = Scope(WORKSPACE, scope.workspace_id, tuple(sorted(locked)))
            names = scope_files(scope)
            reasons = refusals(scope, names, holds_only=holds_only)
            if reasons:
                raise Refused(*reasons)
            rows, entries = row_counts(scope), manifest(names)
            if expected is not None and (rows != expected['rows'] or len(locked) != expected['documents']
                                         or manifest_digest(entries) != expected['digest']):
                raise Refused('The plan is stale: rows or files in scope changed since it was made. Make a new plan.')
            now = timezone.now()
            tombstones = _tombstone(scope, now)  # first: the encounter rows stop pointing at what is deleted next
            deleted = {model._meta.db_table: _delete_rows(model, scope) for model, _ in DISPOSAL_TABLES}
            accounts = _close_accounts(scope.workspace_id) if scope.kind == WORKSPACE else {}
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')  # every deferred check now, before the commit
                cursor.execute('SET CONSTRAINTS ALL DEFERRED')  # and the default again for the rest of the transaction
            left = {table: count for table, count in row_counts(scope).items() if count}
            current = set(Encounter._base_manager.filter(pk__in=scope.encounters()).values_list('pk', flat=True))
            if left or current != set(locked):
                raise Refused('Rows in scope remained after the deletes; nothing was destroyed.')
            marks['committing'] = True  # the block's last statement: whatever raises from here on is the commit
    except (Refused, IntegrityError):
        raise  # refused, or refused by the database inside the block or at its commit: rolled back, nothing destroyed
    except BaseException as exc:  # noqa: BLE001 - an error or an interrupt at the commit: its answer was lost
        if not marks['committing']:
            raise  # before the commit: rolled back, nothing destroyed - an error or an interrupt goes on as it is
        log.error('the commit of a disposal failed (%s): whether its rows were destroyed is not known',
                  type(exc).__name__)
        left = sorted(entry['name'] for entry in entries if entry['bytes'] is not None)  # no file was touched
        raise CommitUnknown(Outcome(deleted=deleted, tombstones=tombstones, accounts=accounts, entries=entries,
                                    rows_destroyed=UNKNOWN, problems=[f'commit: {type(exc).__name__}'],
                                    remaining_names=left, files_remaining=len(left),
                                    interrupted=None if isinstance(exc, Exception) else exc)) from exc
    outcome = Outcome(deleted=deleted, tombstones=tombstones, accounts=accounts, entries=entries)
    _after_commit(scope, outcome)
    return outcome


def _attempt(scope, **options) -> Outcome:
    """destroy(), with the two ways it can end besides an Outcome made plain: CommitUnknown gives its Outcome ('unknown',
    recorded 'failed'); any other error but a refusal rolled the transaction back, and becomes NotDestroyed."""
    try:
        return destroy(scope, **options)
    except CommitUnknown as exc:
        return exc.outcome
    except Refused:
        raise
    except Exception as exc:
        raise NotDestroyed(f'The destruction stopped before its commit ({type(exc).__name__}); the transaction was '
                           'rolled back, and nothing was destroyed.') from exc


def _run(scope, record, **options):
    """One destruction and its DisposalEvent: _attempt(scope, **options), then _record - 'completed' when the Outcome is
    complete, else 'failed' - with ``record``'s fields: (event, outcome). Unrecorded when the event cannot be written.
    An interrupt after the commit (outcome.interrupted) is raised again once the run is recorded, carrying the run's
    certificate as ``disposal_certificate`` - the event's, or Unrecorded's text - for the command to print first."""
    outcome = _attempt(scope, **options)
    stage = DisposalEvent.COMPLETED if outcome.complete else DisposalEvent.FAILED
    try:
        event = _record(stage, scope, outcome, **record)
    except Unrecorded as exc:
        if outcome.interrupted is not None:
            outcome.interrupted.disposal_certificate = exc.text
            raise outcome.interrupted
        raise
    if outcome.interrupted is not None:
        outcome.interrupted.disposal_certificate = certificate(event)
        raise outcome.interrupted
    return event, outcome


def _event_fields(stage, scope, outcome, *, reason, by, approved_by, authorization_ref, notes) -> dict:
    try:
        audit = (models.AuditEvent.objects.filter(workspace_id=scope.workspace_id) if scope.kind == WORKSPACE
                 else models.AuditEvent.objects.filter(encounter_id__in=scope.encounter_ids))
        kept = audit.count()
    except Exception as exc:  # noqa: BLE001 - after the commit nothing may stop the record
        _problem(outcome, 'counts', exc)
        kept = None
    counts = {'rows_destroyed': outcome.rows_destroyed, 'deleted': outcome.deleted, 'tombstones': outcome.tombstones,
              'documents': len(scope.encounter_ids), 'audit_rows_kept': kept, **outcome.accounts}
    if outcome.remaining_rows:
        counts['remaining'] = outcome.remaining_rows
    if outcome.problems:
        counts['problems'] = list(outcome.problems)
    files = {**file_counts(outcome.entries), 'deleted': outcome.files_deleted, 'remaining': outcome.files_remaining}
    if outcome.remaining_names:
        files['remaining_names'] = list(outcome.remaining_names)
    return dict(stage=stage, scope=scope.kind, workspace_id=scope.workspace_id,
                encounter_ids=[str(pk) for pk in scope.encounter_ids], counts=counts, files=files,
                manifest_digest=manifest_digest(outcome.entries), reason=reason, run_by=by, approved_by=approved_by,
                authorization_ref=authorization_ref, notes=f'{notes}; vacuum={outcome.vacuum or "not run"}')


def _record(stage, scope, outcome, **fields) -> DisposalEvent:
    """Write the run's DisposalEvent; when it cannot be written, Unrecorded carries the certificate it would have had."""
    values = _event_fields(stage, scope, outcome, **fields)
    try:
        return DisposalEvent.objects.create(**values)
    except Exception as exc:  # noqa: BLE001 - the destruction ran: its certificate is printed instead of lost
        log.error('the DisposalEvent of a disposal could not be written (%s)', type(exc).__name__)
        raise Unrecorded(certificate_text({**values, 'id': None, 'created_at': timezone.now()})) from exc


def execute(plan_id, *, by, approved_by, authorization_ref):
    """Carry out a plan (module docstring): (the DisposalEvent 'completed' or 'failed', the Outcome). Refused or
    NotDestroyed when nothing was destroyed; Unrecorded when the destruction ran and its event could not be written."""
    runner, approver = two_people(by, approved_by)
    authorization_ref = authorization(authorization_ref, required=True)
    switching = switch_in_progress()
    if switching:
        raise Refused(switching)
    event = DisposalEvent.objects.filter(pk=_uuid(plan_id, 'The plan'), stage=DisposalEvent.PLANNED).first()
    if event is None:
        raise Refused(f'No plan has the id {plan_id}.')
    if event.created_at < timezone.now() - PLAN_MAX_AGE:
        raise Refused(f'The plan is stale: it is older than {int(PLAN_MAX_AGE.total_seconds() // 3600)} hours. Make a '
                      'new plan.')
    if DisposalEvent.objects.filter(stage=DisposalEvent.COMPLETED, notes__startswith=f'plan={event.pk};').exists():
        raise Refused('This plan was already carried out.')
    scope = _scope_of(event)
    expected = {'rows': event.counts.get('rows'), 'documents': event.counts.get('documents'),
                'digest': event.manifest_digest}
    if scope.kind == WORKSPACE and sorted(str(pk) for pk in scope.encounter_ids) != sorted(event.encounter_ids):
        raise Refused('The plan is stale: the practice\'s documents changed since it was made. Make a new plan.')
    return _run(scope, dict(reason=event.reason, by=runner, approved_by=approver, authorization_ref=authorization_ref,
                            notes=f'plan={event.pk}'), expected=expected)


# --- the certificate ----------------------------------------------------------------------------------------------------

def iso_time(moment) -> str:
    return moment.astimezone(dt_timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def certificate(event) -> str:
    """The certificate of a completed or failed DisposalEvent, for the receipt (certificate_text)."""
    values = {name: getattr(event, name) for name in LEDGER_FIELDS if name != 'id'}
    return certificate_text({**values, 'id': event.pk}, ledger=ledger_line(event))


def certificate_text(values, *, ledger='') -> str:
    """A destruction certificate (FLOW-19 (f)) from a DisposalEvent's fields - ``id`` None for one that could not be
    written: ids, counts, digests, who ran and approved it, the authorization, whether its rows were destroyed, what is
    left and how to finish, and what the command cannot reach. It holds no PHI: no title, no file's own name, no
    document text, no answer (a storage name is a random id)."""
    counts, files = values.get('counts') or {}, values.get('files') or {}
    stage, destroyed = values['stage'], counts.get('rows_destroyed', YES)
    if stage == DisposalEvent.COMPLETED:
        title = 'CPT Studio destruction certificate'
    elif destroyed == UNKNOWN:
        title = ('CPT Studio destruction: NOT COMPLETE - the commit failed, so whether the rows were destroyed is not '
                 'known; no file was touched')
    else:
        title = 'CPT Studio destruction: NOT COMPLETE - the rows were destroyed; see what remains'
    if values.get('id') is None:
        title = 'NOT RECORDED (its DisposalEvent could not be written; keep this with the receipt) - ' + title
    scope_word = 'a whole practice' if values['scope'] == WORKSPACE else 'one document'
    ids = values.get('encounter_ids') or []
    lines = [title, f'Disposal {values.get("id") or "(not recorded)"} ({stage}) at {iso_time(values["created_at"])}; '
                    f'{values.get("notes", "")}',
             f'Scope: {scope_word}, practice {values["workspace_id"]}',
             f'Documents ({len(ids)}): ' + (', '.join(ids) or 'none'),
             f'Rows destroyed: {destroyed}',
             'Rows deleted: ' + (', '.join(f'{table} {count}' for table, count in
                                           sorted((counts.get('deleted') or {}).items())) or 'none'),
             f'Tombstones kept: {len(ids)} document row(s), title and values blanked; audit rows kept: '
             f'{counts.get("audit_rows_kept", 0)} (OWNER DECISION D25)',
             f'Files deleted: {files.get("deleted", 0)} of {files.get("files", 0)} ({files.get("bytes", 0)} bytes; '
             f'{files.get("missing", 0)} already missing); remaining: {files.get("remaining", 0)}; manifest sha256 '
             f'{values.get("manifest_digest", "")}']
    if values['scope'] == WORKSPACE:
        lines.append(f'People: {counts.get("memberships_off", 0)} membership(s) turned off, {counts.get("accounts_off", 0)} '
                     f'account(s) made unusable and inactive ({counts.get("sessions_ended", 0)} session(s) ended, '
                     f'{counts.get("signin_names_hashed", 0)} sign-in name(s) hashed), {counts.get("accounts_kept", 0)} '
                     'kept for their other access')
    if files.get('remaining_names'):
        lines.append('Files remaining, by storage name: ' + ', '.join(files['remaining_names']))
    if counts.get('remaining'):
        lines.append('Rows remaining: ' + ', '.join(f'{table} {count}' for table, count in
                                                     sorted(counts['remaining'].items())))
    if counts.get('problems'):
        lines.append('What failed after the commit: ' + '; '.join(counts['problems']))
    if stage != DisposalEvent.COMPLETED:
        target = f'--workspace {values["workspace_id"]}' if values['scope'] == WORKSPACE else f'--encounter {ids[0]}'
        lines.append(f'To finish it: remove what stopped it, then plan the same scope again (dispose --plan {target}) and '
                     'carry that plan out; the new plan takes in what this run left.')
    lines += [f'Run by: {values.get("run_by", "")}; approved by: {values.get("approved_by", "")}; authorization: '
              f'{values.get("authorization_ref", "")}', 'What this command cannot reach:']
    lines += [f'- {text}' for text in CANNOT_REACH]
    if values['scope'] == DOCUMENT:
        lines.append(MISFILED_REMINDER)
    lines.append('Ledger line (dispose --replay-ledger): ' + (ledger or 'none: the event could not be written'))
    return '\n'.join(lines)


# --- the ledger ----------------------------------------------------------------------------------------------------------

LEDGER_FIELDS = ('id', 'created_at', 'stage', 'scope', 'workspace_id', 'encounter_ids', 'counts', 'files',
                 'manifest_digest', 'reason', 'run_by', 'approved_by', 'authorization_ref', 'notes')


def _entry(event) -> dict:
    return {'id': str(event.pk), 'created_at': event.created_at.astimezone(dt_timezone.utc).isoformat(),
            'stage': event.stage, 'scope': event.scope, 'workspace_id': str(event.workspace_id),
            'encounter_ids': list(event.encounter_ids), 'counts': event.counts, 'files': event.files,
            'manifest_digest': event.manifest_digest, 'reason': event.reason, 'run_by': event.run_by,
            'approved_by': event.approved_by, 'authorization_ref': event.authorization_ref, 'notes': event.notes}


def _mac(entry) -> str:
    return salted_hmac(LEDGER_SALT, canonical(entry).decode('utf-8'), algorithm='sha256').hexdigest()


def ledger_line(event) -> str:
    """One DisposalEvent as a ledger line: the row's fields and a keyed MAC over them (SECRET_KEY, which lives in the
    installation's environment, never in the database), so a changed or foreign line is refused on replay."""
    entry = _entry(event)
    return json.dumps({'entry': entry, 'mac': _mac(entry)}, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def ledger_lines() -> list:
    """The whole ledger, oldest first (dispose --ledger): to keep beside the backups, and to replay after a restore."""
    return [ledger_line(event) for event in DisposalEvent.objects.order_by('created_at', 'pk')]


def read_ledger(lines) -> list:
    """The entries of a ledger, each checked: a line that is not exactly {'entry', 'mac'}, has another field set or a
    MAC that does not verify refuses the whole ledger (Refused), before anything is touched."""
    entries = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            raise Refused(f'Ledger line {number} is not a ledger line; nothing was replayed.') from None
        if not isinstance(item, dict) or set(item) != {'entry', 'mac'} or not isinstance(item['entry'], dict) \
                or set(item['entry']) != set(LEDGER_FIELDS) or not isinstance(item['mac'], str):
            raise Refused(f'Ledger line {number} is not a ledger line; nothing was replayed.')
        if not hmac.compare_digest(_mac(item['entry']), item['mac']):
            raise Refused(f'Ledger line {number} was changed or written by another installation; nothing was '
                          'replayed.')
        entry = item['entry']
        if entry['stage'] not in DisposalEvent.STAGES or entry['scope'] not in (DOCUMENT, WORKSPACE):
            raise Refused(f'Ledger line {number} names an unknown stage or scope; nothing was replayed.')
        entries.append(entry)
    return entries


def _insert_entry(entry) -> bool:
    """Write a ledger row the database lacks back exactly as it was (its own id and time) - an insert, never an update:
    the ledger stays append-only. True when it was missing."""
    if DisposalEvent.objects.filter(pk=entry['id']).exists():
        return False
    quote = connection.ops.quote_name
    columns = [DisposalEvent._meta.get_field(name).column for name in LEDGER_FIELDS]
    values = [uuid.UUID(entry['id']), datetime.fromisoformat(entry['created_at']), entry['stage'], entry['scope'],
              uuid.UUID(entry['workspace_id']), json.dumps(entry['encounter_ids']), json.dumps(entry['counts']),
              json.dumps(entry['files']), entry['manifest_digest'], entry['reason'], entry['run_by'],
              entry['approved_by'], entry['authorization_ref'], entry['notes']]
    placeholders = ['%s::jsonb' if name in ('encounter_ids', 'counts', 'files') else '%s' for name in LEDGER_FIELDS]
    sql = (f'INSERT INTO {quote(DisposalEvent._meta.db_table)} ({", ".join(quote(column) for column in columns)}) '
           f'VALUES ({", ".join(placeholders)})')
    with connection.cursor() as cursor:
        cursor.execute(sql, values)
    return True


def replayable(entry) -> bool:
    """Whether a ledger entry's rows were destroyed, so a replay carries it out again: every 'completed' one, and a
    'failed' one whose commit was answered (rows_destroyed 'yes')."""
    if entry['stage'] == DisposalEvent.COMPLETED:
        return True
    return entry['stage'] == DisposalEvent.FAILED and (entry['counts'] or {}).get('rows_destroyed', YES) == YES


def undecided(entry) -> bool:
    """Whether a ledger entry is a 'failed' run whose commit's answer was lost (rows_destroyed 'unknown'): its rows may
    never have been destroyed, so no replay carries it out. A person decides; to destroy the scope they plan it again
    and carry the plan out, and that run's entry is the one a replay carries out (decided_by)."""
    return entry['stage'] == DisposalEvent.FAILED and (entry['counts'] or {}).get('rows_destroyed') == UNKNOWN


def decided_by(entry, entries) -> str:
    """The id of a later entry of ``entries`` that destroyed the same scope (replayable): the decision a person made
    about an undecided ``entry`` by planning it again - for a document, a run that covered it; for a practice, a run of
    the whole practice. '' when there is none."""
    made = datetime.fromisoformat(entry['created_at'])
    for other in entries:
        if (not replayable(other) or other['workspace_id'] != entry['workspace_id']
                or datetime.fromisoformat(other['created_at']) <= made):
            continue
        if other['scope'] == WORKSPACE or (entry['scope'] == DOCUMENT
                                           and set(entry['encounter_ids']) <= set(other['encounter_ids'])):
            return other['id']
    return ''


def _replay_scope(entry):
    """The scope a ledger entry covers in this database, or None when none of it exists here."""
    workspace = uuid.UUID(entry['workspace_id'])
    if entry['scope'] == WORKSPACE:
        if not models.Workspace.objects.filter(pk=workspace).exists():
            return None
        return workspace_scope(workspace)
    present = tuple(sorted(Encounter._base_manager.filter(pk__in=entry['encounter_ids']).values_list('pk', flat=True)))
    return Scope(DOCUMENT, workspace, present) if present else None


def _what_remains(scope) -> dict:
    rows = {table: count for table, count in row_counts(scope).items() if count}
    alive = Encounter._base_manager.filter(pk__in=scope.encounters(), destroyed_at__isnull=True).count()
    try:
        files = len(scope_files(scope))
    except Refused:
        files = None  # its files cannot be listed (a refusal): counted as something left, and refused before a replay
    access = 0
    if scope.kind == WORKSPACE:
        access = models.Membership.objects.filter(workspace_id=scope.workspace_id, active=True).count()
    return {'rows': rows, 'documents_alive': alive, 'files': files, 'memberships_on': access}


def _needed(remains) -> bool:
    return remains is not None and bool(remains['rows'] or remains['documents_alive'] or remains['files'] is None
                                        or remains['files'] or remains['memberships_on'])


def replay(lines, *, execute_it=False, by='', approved_by='', authorization_ref=''):
    """Carry out again the ledger's disposals whose rows were destroyed (replayable; module docstring). Without
    ``execute_it``, a dry run: what each would destroy, nothing written. With it: refused during an install or a
    switch-back, and while the worker beats (a restored database's queued coding would send what was destroyed); two
    different people; then every entry's refusals are checked BEFORE anything is written, so a refused replay changed
    nothing; then every ledger row the database lacks is written back, and each entry whose scope holds anything again
    is destroyed again (a practice closed in the same transaction), with a DisposalEvent naming the entry it replays.
    An error on one entry stops the replay there - the entries before it stay done, each with its event - and the
    report says so entry by entry: {'ledger_rows_restored' or 'ledger_rows_missing', 'items', 'stopped'}, each item
    {entry, scope, remains, status, event, outcome, error, certificate, decided_by}. An undecided entry ('unknown') is
    listed and never carried out: status DECIDE, or DECIDED once a later entry carried out its scope or nothing of it
    remains. An interrupt stops the replay too, and goes on carrying the report as ``disposal_report``."""
    entries = read_ledger(lines)
    if execute_it:
        runner, approver = two_people(by, approved_by)
        authorization_ref = authorization(authorization_ref, required=True)
        switching = switch_in_progress()
        if switching:
            raise Refused(switching)
        if jobs.worker_responding():
            raise Refused('The worker is running, or stopped less than two minutes ago. Stop it and wait before '
                          'replaying: after a restore, its queued coding would send documents that were destroyed.')
    items = []
    for entry in entries:
        if not (replayable(entry) or undecided(entry)):
            continue
        scope = _replay_scope(entry)
        remains = _what_remains(scope) if scope is not None else None
        item = {'entry': entry['id'], 'reason': entry['reason'], 'scope': scope, 'remains': remains,
                'needed': _needed(remains), 'status': 'nothing to do', 'event': None, 'outcome': None, 'error': '',
                'certificate': '', 'decided_by': ''}
        if undecided(entry):  # never carried out by a replay: a person decides (undecided)
            item['decided_by'] = decided_by(entry, entries)
            item['status'] = DECIDED if item['decided_by'] or not item['needed'] else DECIDE
            item['needed'] = False
        items.append(item)
    missing = sum(not DisposalEvent.objects.filter(pk=entry['id']).exists() for entry in entries)
    if not execute_it:
        return {'ledger_rows_missing': missing, 'items': items, 'stopped': None}
    reasons = []  # every entry's refusals first: a replay refuses having changed nothing, or it goes on
    for item in items:
        if not item['needed']:
            continue
        try:
            names = scope_files(item['scope'])
            manifest(names)  # a file that cannot be read refuses here, before any entry is destroyed
            found = refusals(item['scope'], names, holds_only=True, closed_required=False)
        except Refused as exc:
            found = exc.reasons
        reasons += [f'Ledger entry {item["entry"]}: {reason}' for reason in found]
    if reasons:
        raise Refused(*reasons)
    with transaction.atomic():
        restored = sum(_insert_entry(entry) for entry in entries)
    report = {'ledger_rows_restored': restored, 'items': items, 'stopped': None}
    for index, item in enumerate(items):
        if not item['needed']:
            continue
        try:
            item['event'], item['outcome'] = _run(item['scope'], dict(
                reason=item['reason'], by=runner, approved_by=approver, authorization_ref=authorization_ref,
                notes=f'replay={item["entry"]}'), holds_only=True, close=True)
            item['status'] = item['event'].stage
        except Unrecorded as exc:  # it ran: its certificate is the record
            item['status'], item['certificate'] = 'unrecorded', exc.text
            report['stopped'] = item['entry']
        except (Refused, NotDestroyed) as exc:  # rolled back: nothing of this entry was destroyed
            item['status'] = 'refused' if isinstance(exc, Refused) else 'not destroyed'
            item['error'] = ' '.join(exc.reasons) if isinstance(exc, Refused) else str(exc)
            report['stopped'] = item['entry']
        except Exception as exc:  # noqa: BLE001 - reported, never mistaken for nothing having been destroyed
            item['status'], item['error'] = 'error', f'{type(exc).__name__} (logged)'
            log.exception('a ledger replay stopped on an error')
            report['stopped'] = item['entry']
        except BaseException as exc:  # noqa: BLE001 - an interrupt: the replay stops, its report goes with it
            item['status'], item['certificate'] = INTERRUPTED, getattr(exc, 'disposal_certificate', '')
            report['stopped'] = item['entry']
            for later in items[index + 1:]:
                if later['needed']:
                    later['status'] = 'not attempted'
            exc.disposal_report = report
            raise
        if report['stopped']:
            for later in items[index + 1:]:
                if later['needed']:
                    later['status'] = 'not attempted'
            break
    return report
