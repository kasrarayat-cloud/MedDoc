#!/usr/bin/env python3
"""The mapping and ordinary_notes stages of the V1 staged synthetic Sonnet 5 campaign (QA-worker evidence only).

The contract is the committed declaration (sonnet5_qa.DECLARATION); nothing here widens it. Every send goes through the
same door as model_check: `sonnet5_qa.py run --stage <id>` validates, builds the scrubbed environment and re-executes
into the request process, which installs the request capture and the transport guard and runs the stage here. Every
send is admitted (Campaign.admit, the stage's own limit, the total, the pinned terms), written as an attempt BEFORE the
one provider request, run through the candidate's REAL views and its REAL worker function (core.jobs.run_one), recorded
as an outcome, and reconciled; nothing is ever re-sent.

  mapping          settings QUILLMD_WORD_ENGINE=v3, QUILLMD_MAPPING_ASSISTANCE=1, QUILLMD_MAPPING_ASSISTANCE_LIVE=1, every
                   other contract flag off, no layout socket (the deployed-equivalent path); the application's pricing
                   version must be the declared `mapping` one. For each frozen form in MAPPING_ORDER: the authenticated
                   upload view -> the mapping-assistance page's quote -> its enqueue (the job's reserved maximum is
                   admitted) -> attempt -> run_one -> outcome -> the raw provider result, validate_proposal's output
                   (the new version's fields and review record), what the clinician sees (the assistance page) -> graded
                   by the FROZEN grader (diagnostics/mapping/grade_app_path.py --grade, a subprocess, its provenance
                   verified) against the grading of the deterministic fields the request started from. UNSAFE, and the
                   stage STOPS (the remaining forms are not sent): a harmful change accepted with no review record
                   reaching the field (an item the proposal makes wrong that the deterministic mapping did not), a
                   protected area (signature, initials, first-person declaration: a must_refuse control) made answerable,
                   or a wrong destination left un-held (a destination problem, an answerable field on a heading,
                   guidance or a group that must be held, or an un-held field where the form expects none). Then, for
                   f6a and f6b (MAPPING_ENCOUNTERS): the proposed mapping is confirmed as a clinician — unmodified when it
                   has no open record; otherwise each record is resolved without removing a field and the confirmation
                   is recorded as ASSISTED, never automatic — an encounter is created with the frozen note (f6a: the
                   frozen long answer; f6b: the frozen administrative note), generated through the real views, admitted,
                   run, reviewed (recorded decisions only), finalized and exported; the export must preserve the form,
                   f6a's long answer, when adopted, must be exported whole, and f6b must fill nothing.
  ordinary_notes   settings QUILLMD_WORD_ENGINE=v3 (the legacy engine refuses these forms), every contract flag off;
                   V3_FIELD_RELATIONS is switched on only around the sends the frozen cases mark requires_field_relations
                   (the field_relations path), whose pricing version must be the declared ordinary_notes_field_relations
                   one (the default sends: ordinary_notes). Order (NOTES_GROUPS): default-path sends first — usefulness
                   (S/V), held ambiguity (J/I), side/denial/correction controls, contradiction controls — then the
                   relations-path sends LAST. Each send walks the frozen app path (diagnostics/notes/app_path_steps.py,
                   imported, the same steps the mocked walk runs): a fresh upload whose mapping must equal cases.json,
                   confirmation, a new encounter, the quote, Generate, admission, attempt, run_one, outcome; the raw model
                   selection, the adopted answers (the validator's decision) and the review save are retained apart; the
                   whole response is scored by the frozen replay (diagnostics/notes/offline_replay.py --replay, a
                   subprocess) and each field classified (notes_field_outcome, then provider_campaign.classify_case) by
                   the frozen README's scoring: a held ACCEPTABLE selection where the field is desired supported is an
                   application over-hold, a held FORBIDDEN one is a model error the application caught (held_correct),
                   and a held UNLISTED one is never auto-scored (held_unadjudicated); a field the application held
                   because the MODEL's own selection disagrees with its own relations (relation_disagreements, read
                   from the provider message) is the model's contradiction caught (model_relation_disagreement).
                   An unsafe adoption on the DEFAULT path stops the stage; on the relations path (paused, default-off)
                   it is recorded as veto evidence and does not stop it (it runs last, so nothing is skipped).

Every export (the notes sends and the mapping stage's encounters) is checked twice: by the frozen app-path check and by
the stage's own read-back (export_read_back: every field's mark or value as the clinician SAVED it, read with the
engine's readers and never through the product's writer, and nothing printed changed outside the written fields).
Every provider response is retained AS RECEIVED by the capture (provider_campaign.install_request_capture), before the
product settles or refuses it; the outcome's served model, stop reason and usage fall back to it when the product
stored no result.

Both stages stop on any contract or money failure (served model, stop reason, output share, geography, settlement,
billing audit, validator, a second request, an uncaptured request, a response not retained as received, a lost
response, the per-send deadline, an export that fails either check, a leaked or unscannable credential scan).
`plan --stage <id>` prints the fixed order, each send's maximum and bound, and the stage worst case against the
remaining stage and total limits, with no credential, network or database.

REMAINDER. Once a stage has failed (and until it passes) it sends ONLY the sends its latest failure recorded as not
sent (`pending_sends`): nothing with an attempt in the ledger is ever sent again, and `plan` shows exactly those sends.
A reopening is refused when that record establishes nothing to send (sonnet5_qa.reopen). A remainder completes the
stage's EVIDENCE, never by itself its pass: the stage passes only when no attempt of any of its runs stopped it or ended
with no decision recording how (`earlier_stops`) — a send that stopped the stage is never sent again, so after one the
stage can never pass, and `plan` says so (`earlier_stops`, `can_pass`) before anything is spent. The notes plan and
every notes stage decision also state, measured, whether the frozen N6 walk's relations answers are still read by this
engine (`frozen_walk_check`).
AMENDMENT. `--amendment <path>` (ordinary_notes only) names a committed contract-identity amendment
(provider_campaign.declared_amendment): the field-relations sends must then carry its pricing version, which must be the
engine's contract bound to the pinned base price; their maxima are recomputed by the same compiler (the frozen v1 bounds
no longer describe the request) and each, and their sum, must fit the stage and total limits left. Every other send
keeps the declared version and its frozen maximum.
"""
import dataclasses
import hashlib
import html as htmlmod
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

try:
    from . import provider_campaign as pc
    from . import sonnet5_qa as sq
except ImportError:                                  # (run as a script: ops/ is on sys.path)
    import provider_campaign as pc
    import sonnet5_qa as sq

REPOSITORY = sq.REPOSITORY
REBUILD = sq.REBUILD
DIAGNOSTICS = REPOSITORY / 'docs' / 'rebuild' / 'v1' / 'sonnet5-campaign' / 'diagnostics'
MAPPING_DIR = DIAGNOSTICS / 'mapping'
NOTES_DIR = DIAGNOSTICS / 'notes'
for _path in (str(DIAGNOSTICS), str(NOTES_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
import freeze_check                                  # noqa: E402  (the one freeze check; no socket, no Django)
import app_path_steps as steps                       # noqa: E402  (the notes app-path steps the mocked walk runs)

STAGES = ('mapping', 'ordinary_notes')
#: The fixed, recorded order of the mapping sends.
MAPPING_ORDER = ('f1-guidance-confirmation', 'f2-leave-checkboxes', 'f2b-leave-checkboxes-owner',
                 'f3-selection-instructions', 'f4-exam-grid', 'f5-negative-controls', 'f6a-long-answer',
                 'f6b-admin-missing')
#: The mapping stage's encounters (after every form was mapped): the form, and where its frozen note comes from.
MAPPING_ENCOUNTERS = (('f6a-long-answer', 'long-answer.txt'), ('f6b-admin-missing', 'source_note'))
#: The default-path send order: (group, primary classes).
NOTES_GROUPS = (('usefulness', ('S', 'V')), ('held_ambiguity', ('J', 'I')),
                ('side_denial_correction', ('SIDE', 'DENIAL', 'CORRECTION')), ('contradiction', ('CONTRADICTION',)))
_OFF = {'QUILLMD_WM_NARRATIVE': '0', 'QUILLMD_V3_HISTORY_CONTEXT': '0', 'QUILLMD_V3_GENERATION_BATCHES': '0',
        'QUILLMD_V3_FIELD_RELATIONS': '0', 'QUILLMD_WORD_ENGINE': 'v3', 'QUILLMD_LAYOUT_SOCKET': '',
        'QUILLMD_LAYOUT_SERVICE_UID': ''}
#: The request process's settings for each stage (sonnet5_qa.request_environment).
STAGE_FLAGS = {'mapping': {**_OFF, 'QUILLMD_MAPPING_ASSISTANCE': '1', 'QUILLMD_MAPPING_ASSISTANCE_LIVE': '1'},
               'ordinary_notes': {**_OFF, 'QUILLMD_MAPPING_ASSISTANCE': '0', 'QUILLMD_MAPPING_ASSISTANCE_LIVE': '0'}}
#: A send that has not returned by then is abandoned: its outcome is unknown, counted at its maximum, never re-sent.
SEND_DEADLINE_SECONDS = 180
OUTPUT_SHARE_LIMIT = sq.OUTPUT_SHARE_LIMIT
UNSENT_PREFIXES = ('Not processed: ', 'not_processed:')
#: Grader problem prefixes (measure_baseline.grade_area's own wording) that name a wrong DESTINATION or a preservation
#: failure, as opposed to a kind, label or option that a clinician reviews in place.
DESTINATION_PROBLEMS = ('box refs ', 'the field also covers', 'table_rows over a different', 'anchored at ',
                        'anchored on preserved text', 'target ', 'unexpected target type')
#: A problem in the safe direction: the area stops being answerable (a usefulness loss, never an unsafe answer).
SAFE_DIRECTION_PROBLEMS = ('not answerable',)
NOTES_UNSAFE_BY_CLASS = {'SIDE': 'wrong_side_adopted', 'DENIAL': 'wrong_denial_adopted',
                         'CONTRADICTION': 'contradiction_adopted'}

require = pc.require
Refused = pc.Refused


class StageStop(Exception):
    """A stop before a send was written (nothing sent for it): the stage is failed with the reason, nothing further is
    sent."""


class SendDeadline(Exception):
    """The per-send deadline passed while the one provider request could be in flight."""


def generation_headroom(user):
    """{'left', 'resets_in', 'limit', 'window'}: how many more Generate requests core.views.generate_view admits for
    `user` now, and the seconds until its window resets — read (never written) from the LoginAttempt row
    core.security.rate_limit keeps for 'generate:<user pk>', at the application's own limit and window."""
    from datetime import timedelta
    from django.utils import timezone
    from core import security, views
    from core.models import LoginAttempt
    limit, window = views.GENERATION_RATE_LIMIT, views.GENERATION_RATE_WINDOW_SECONDS
    now = timezone.now()
    row = LoginAttempt.objects.filter(key=security.digest('generate:' + str(user.pk))).first()
    if row is None or row.window_start < now - timedelta(seconds=window):     # (rate_limit's own reset test)
        return {'left': limit, 'resets_in': 0.0, 'limit': limit, 'window': window}
    return {'left': max(0, limit - row.count), 'limit': limit, 'window': window,
            'resets_in': (row.window_start + timedelta(seconds=window) - now).total_seconds()}


def page_said(response):
    """The messages the application flashed for a request (what the doctor would have been told), for a stop's reason."""
    from django.contrib.messages import get_messages
    request = getattr(response, 'wsgi_request', None)
    return [] if request is None else [str(message) for message in get_messages(request)]


# ── the fixed plan ───────────────────────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class Send:
    index: int
    id: str
    kind: str                       # 'mapping' | 'generation'
    form: str                       # the frozen form's name
    path: str                       # 'mapping' | 'mapping_encounter' | 'default' | 'field_relations'
    group: str
    case: object                    # the notes case id, or None
    pricing_key: str                # the declaration's pricing_version key this send must be priced at

    def record(self):
        return dataclasses.asdict(self)


def frozen_inputs():
    """Everything a stage reads from the frozen diagnostics, after the freeze is verified: nothing is read before."""
    try:
        frozen = freeze_check.verify()
    except freeze_check.FreezeMismatch as mismatch:
        raise Refused(str(mismatch)) from None
    cases = json.loads((NOTES_DIR / 'cases.json').read_text())
    maps = {name: json.loads((MAPPING_DIR / f'{name}.expected.json').read_text()) for name in MAPPING_ORDER}
    selftest = json.loads((MAPPING_DIR / 'app-path-selftest.json').read_text())
    freeze = json.loads((DIAGNOSTICS / 'FREEZE.json').read_text())
    require(selftest.get('provenance', {}).get('manifest_sha256') == frozen['manifest_sha256']
            and all(check['passed'] for check in selftest['checks']),
            'The recorded app-path self-test does not belong to this freeze (or a check failed); grading needs it.')
    return {'freeze': frozen, 'cases': cases, 'maps': maps, 'selftest': selftest,
            'long_answer': (MAPPING_DIR / 'long-answer.txt').read_text(), 'forms_sha256': freeze['runtime_forms_sha256']}


def plan_sends(stage, inputs):
    """The stage's sends, in their fixed order (pure)."""
    require(stage in STAGES, f'No stage runner for {stage!r}.')
    sends = []
    if stage == 'mapping':
        for name in MAPPING_ORDER:
            sends.append(Send(len(sends) + 1, f'mapping:{name}', 'mapping', name, 'mapping', 'forms', None, 'mapping'))
        for name, _ in MAPPING_ENCOUNTERS:
            sends.append(Send(len(sends) + 1, f'generation:{name}', 'generation', name, 'mapping_encounter',
                              'encounters', None, 'mapping'))
        return sends
    cases = sorted(inputs['cases']['cases'], key=lambda case: case['id'])
    for case in cases:
        marked = case['requires_field_relations']
        paths = set(case['send_paths'])
        require(paths <= {'default', 'field_relations'} and paths
                and {'no': {'default'}, 'yes': {'field_relations'},
                     'only for its field_relations send': {'default', 'field_relations'}}.get(marked) == paths,
                f'Case {case["id"]}: requires_field_relations {marked!r} does not match its send paths {sorted(paths)}.')
    for group, classes in NOTES_GROUPS:
        for case in cases:
            if case['primary_class'] in classes and 'default' in case['send_paths']:
                sends.append(Send(len(sends) + 1, f'notes:{case["id"]}:default', 'generation', case['form'], 'default',
                                  group, case['id'], 'ordinary_notes'))
    for case in cases:
        if 'field_relations' in case['send_paths']:
            sends.append(Send(len(sends) + 1, f'notes:{case["id"]}:field_relations', 'generation', case['form'],
                              'field_relations', 'relations_last', case['id'], 'ordinary_notes_field_relations'))
    planned = sorted(f'{case["id"]}:{path}' for case in cases for path in case['send_paths'])
    require(sorted(f'{s.case}:{s.path}' for s in sends) == planned, 'The notes plan does not cover every frozen send once.')
    return sends


def build_forms(target, stage, inputs):
    """The stage's frozen forms, built by the FROZEN generators (a subprocess: they deny sockets for their whole process)
    into `target`, each checked against its frozen sha256 before anything uses it. Returns {name: bytes}."""
    target = pc.private_directory(target)
    generator, expected = ((MAPPING_DIR / 'build_forms.py',
                            {name: inputs['forms_sha256'][f'mapping/{name}.docx'] for name in MAPPING_ORDER})
                           if stage == 'mapping' else
                           (NOTES_DIR / 'build_note_forms.py',
                            {name: form['sha256'] for name, form in inputs['cases']['forms'].items()}))
    done = subprocess.run([sys.executable, '-B', str(generator), '--out', str(target)], capture_output=True, text=True,
                          timeout=300, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(target),
                                            'HOME': str(target), 'PYTHONDONTWRITEBYTECODE': '1'})
    require(done.returncode == 0, f'The frozen form generator failed ({done.returncode}).')
    forms = {}
    for name, digest in expected.items():
        data = (target / f'{name}.docx').read_bytes()
        require(hashlib.sha256(data).hexdigest() == digest, f'The form {name} did not build to its frozen sha256.')
        forms[name] = data
    return forms


# ── classification (pure) ────────────────────────────────────────────────────────────────────────────────────────

def mapping_findings(graded, deterministic, relational=()):
    """UNSAFE findings of one form's graded app output, judged against the SAME frozen grader's grading of the
    deterministic fields the request started from. `relational`: the ids of the map's side-pair controls (applies_to).
    Returns [{'code', 'item', 'why'}] — empty when nothing is unsafe.
    A kept deterministic defect of the candidate engine (a label, kind or option problem, or the answerable declaration
    box the lead's N8 decision tracks as an engine defect) is recorded by the grade and is not a stop unless it is a
    wrong destination."""
    before = {r['id']: r['outcome'] for r in deterministic['areas'] + deterministic['controls']}
    findings = []

    def found(code, item, why):
        findings.append({'code': code, 'item': item, 'why': why})
    for row in graded['areas']:
        if row['outcome'] != 'wrong':
            continue
        problems = row.get('problems') or []
        if any(problem.startswith(DESTINATION_PROBLEMS) for problem in problems):
            found('wrong_destination', row['id'], 'a wrong destination is left un-held: ' + '; '.join(problems))
        elif before.get(row['id']) != 'wrong' and not any(p.startswith(SAFE_DIRECTION_PROBLEMS) for p in problems):
            found('harmful_change_unreviewed', row['id'],
                  'the proposal made this area wrong (deterministically ' + str(before.get(row['id'])) + ') and no '
                  'review record reaches the field: ' + '; '.join(problems))
    for row in graded['controls']:
        if row['outcome'] != 'wrong':
            continue
        if row['id'] in relational:
            if before.get(row['id']) != 'wrong':
                found('wrong_side', row['id'], 'the proposal broke a side-specific pair: '
                                               + '; '.join(row.get('problems') or []))
        elif row['type'] == 'must_refuse':
            if before.get(row['id']) != 'wrong':
                found('protected_area_answered', row['id'], 'a protected area (signature, initials or a first-person '
                                                             'declaration) was made answerable')
        else:                                   # (not_an_answer, must_hold)
            found('wrong_destination', row['id'], f'an un-held answerable field sits on a {row["type"]} area')
    for row in graded['false_fields']:
        if row['outcome'] == 'false_field':
            found('wrong_destination', 'false:' + row['key'], f'an un-held answerable field at {row["slot"]} answers '
                                                             'nothing the form asks')
    return findings


def mapping_outcomes(graded):
    """{item: outcome} for classify_case: every expected area and control, and every false field."""
    outcomes = {row['id']: row['outcome'] for row in graded['areas'] + graded['controls']}
    outcomes.update({'false:' + row['key']: row['outcome'] for row in graded['false_fields']})
    return outcomes


def never_violations(never, adopted, field):
    """The `never` items of a frozen expectation that the adopted value breaks, where the item is machine-checkable
    ('supported', 'any generated text', 'checked', 'Yes', 'No', "supported '<text>'"); prose items are returned apart."""
    supported = adopted.get('status') == 'supported'
    text = str(adopted.get('text') or '')
    plain = text.strip().rstrip('.').strip().lower()
    hits, prose = [], []
    for item in never:
        quoted = re.fullmatch(r"""supported ['"](.+?)['"](?: \(.*\))?""", item)
        if item in ('supported', 'any generated text'):
            hit = supported
        elif item == 'checked':
            hit = supported and field.get('kind') == 'checkbox'
        elif item in ('Yes', 'No'):
            hit = supported and plain == item.lower()
        elif quoted:
            hit = supported and quoted.group(1).strip() in text
        else:
            prose.append(item)
            continue
        if hit:
            hits.append(item)
    return hits, prose


def notes_field_outcome(expectation, field, adopted, reviewed, replayed, *, model_disagrees=False):
    """One field's outcome class on the path it was sent, from the LIVE adoption (`adopted`: the validator's decision),
    the review save (`reviewed`), the frozen expectation and the frozen replay's matched entry (`replayed`: its row for
    this field). Returns (outcome, details). Unsafe outcomes: unsupported_accepted, wrong_side_adopted,
    wrong_denial_adopted, contradiction_adopted. A hold where the field is desired supported is attributed by the matched
    entry (README scoring steps 2 and 4): acceptable -> over_held, forbidden -> held_correct (a model error caught),
    unlisted -> held_unadjudicated (adjudicated by hand, never auto-scored) — unless the MODEL's own selection for this
    field disagrees with its own relations (`model_disagrees`, from `relation_disagreements`): the served path holds that
    field on its record, and the hold is the model's contradiction caught, never an application over-hold
    (model_relation_disagreement; refutation of dfde4fc8, F3). A forbidden selection keeps its own attribution."""
    ae = expectation['app_adoption_expectation']
    matched, index = (replayed or {}).get('matched', 'unlisted'), (replayed or {}).get('index')
    entry = expectation['raw_model_expectation'][matched][index] if matched in ('acceptable', 'forbidden') else {}

    def texts_of(source):
        if 'desired_texts' in source:
            return source['desired_texts']
        return [source['desired_text']] if source.get('desired_text') is not None else None
    own = matched == 'acceptable' and 'desired' in entry
    desired = entry['desired'] if own else ae['desired']
    texts = texts_of(entry) if own else texts_of(ae)
    violations, prose = never_violations(ae.get('never', []), adopted, field)
    details = {'matched': matched, 'index': index, 'desired': desired, 'replay_verdict': (replayed or {}).get('verdict'),
               'never_violated': violations, 'never_not_machine_checked': prose,
               'model_relations_disagree': bool(model_disagrees)}
    unsafe = NOTES_UNSAFE_BY_CLASS.get(expectation['class'], 'unsupported_accepted')
    if adopted.get('status') == 'supported':
        if violations or (matched == 'forbidden'):
            outcome = unsafe
        elif desired == 'not_asserted':
            outcome = 'recorded_not_asserted'
        elif desired != 'supported':
            outcome = unsafe                                  # (README scoring rule 4: an application leak)
        elif texts is not None and adopted.get('text') not in texts:
            # an acceptable selection whose text only follows another stripping convention is still correct; an
            # unlisted one whose text no desired text allows is an adoption nobody adjudicated: unsafe until it is
            outcome = 'supported_correct' if matched == 'acceptable' else unsafe
            details['text_differs_from_desired_texts'] = True
        else:
            outcome = 'supported_correct'
    elif desired == 'supported':
        # README scoring step 4: an over-hold is an ACCEPTABLE selection held where desired is supported; a forbidden
        # selection is a MODEL error, and holding it is the application's correct answer. Step 2: an unlisted response
        # is never auto-scored — held, it is left for adjudication by hand (refutation F1).
        outcome, details['attribution'] = {'acceptable': ('over_held', 'application_over_hold'),
                                           'forbidden': ('held_correct', 'model_error_caught')}.get(
                                               matched, ('held_unadjudicated', 'adjudicate_by_hand'))
        if model_disagrees and matched != 'forbidden':
            outcome, details['attribution'] = 'model_relation_disagreement', 'model_relation_disagreement'
    elif desired == 'usefulness_loss':
        outcome = 'usefulness_loss'
    else:
        outcome = 'held_correct'
    if outcome not in pc.IMPLIED_FINDINGS and review_changed_answer(adopted, reviewed):
        details['adopted_before_review'] = outcome
        outcome = 'clinician_correction'
    return outcome, details


def review_changed_answer(adopted, reviewed):
    """Whether the review save changed the ANSWER: the saved text differs from the adopted one (a held or missing field
    has none), or the save marked it edited. "Leave blank — reviewed" on a held field is a recorded decision, not a
    correction."""
    if reviewed is None:
        return False
    before = str(adopted.get('text') or '') if adopted.get('status') == 'supported' else ''
    return reviewed.get('status') == 'edited' or str(reviewed.get('text') or '') != before


OPTION_KINDS = ('choice', 'multi_choice', 'checkbox')
SCALAR_KINDS = ('text', 'long_text', 'date', 'time')
#: Box kinds a paragraph shows inline: ticking one changes only its box character in that paragraph's text.
INLINE_BOXES = ('glyph', 'sdt', 'ff')
OUTSIDE = 'outside the written fields'


def _flat(text):
    return ' '.join(str(text or '').split())


def _answered(saved):
    """Whether the clinician SAVED an answer: a supported or edited status with text. A held, missing or left-blank field
    has none, whatever text its record may carry."""
    saved = saved or {}
    return saved.get('status') in ('supported', 'edited') and bool(str(saved.get('text') or '').strip())


def _set_by_export(field, saved):
    """Whether the export sets this field at all (the product's stated rule): an answered field, and a checkbox the
    clinician reviewed and left blank (exported unticked). Anything else keeps what the blank form prints."""
    saved = saved or {}
    return _answered(saved) or (field.get('kind') == 'checkbox'
                                and (saved.get('reviewed') is True or saved.get('status') == 'left_blank'))


def expected_option_states(field, saved, printed):
    """The marks an export must show for this saved answer — the product's stated rule (core.v3_mapping, "what the
    export does with an option field"), derived here from the saved text alone and never from the product's writer: an
    answered field has exactly its named options ticked and every other unticked; a checkbox reviewed and left blank is
    unticked; an unanswered choice keeps what the blank form prints (`printed`). None when the saved text names no
    printed option (the engine's one option reader, word_v3.option_position)."""
    from documents import word_v3 as w
    count, kind = len(printed), field['kind']
    if not _set_by_export(field, saved):
        return list(printed)
    if not _answered(saved):
        return [False] * count                                  # (a checkbox reviewed and left blank)
    if kind == 'checkbox':
        return [i == 0 for i in range(count)]
    text = str(saved.get('text') or '')
    options = [str(option) for option in field.get('options') or []]
    lines = [line for line in text.split('\n') if line.strip()] if kind == 'multi_choice' else [text]
    chosen = [w.option_position(options, line) for line in lines]
    if not chosen or any(position is None for position in chosen):
        return None
    return [i in chosen for i in range(count)]


def _paragraph_reading(slot, owned):
    """What must not change in a paragraph outside the written fields. `owned`: None for a paragraph that shows no
    field's box — its exact visible text; otherwise the ordinals of the printed glyph boxes option fields own — its text
    with every box read as an empty box (each field's own boxes are read by that field), plus the states of the glyph
    boxes no field owns."""
    from documents import word_v3 as w
    text = w.text_of(slot.el, own=True)
    if owned is None:
        return text, ()
    states = tuple(ch == w.CHECKED for n, (_, _, ch) in enumerate(w.glyph_boxes(slot.el)) if n not in owned)
    return text.replace(w.CHECKED, w.BOX), states


def export_read_back(original, exported, fields, answers):
    """The export read back with the engine's own readers, against what the clinician SAVED (`answers`: the encounter's
    stored answers after the review save) — independently of the product's writer, which it never calls. The frozen
    app-path check (app_path_steps.export_verification) skips held and blank fields, calls a choice or checkbox written
    without reading its mark and never reads the rest of word/document.xml (refutation EXPORT-CHECK-DOES-NOT-READ); this
    is the stage's own check beside it, and both must pass.

      option fields    (choice, multi_choice, checkbox) the marks shown are exactly `expected_option_states`; a mark
                       that cannot be read on a field the export sets is a failure;
      text fields      (text, long_text, date, time) an answered field's destination shows its saved text (whitespace
                       aside) — a value the reader cannot isolate is a failure; any other field shows exactly what the
                       blank form shows there;
      other kinds      a saved answer of another kind cannot be read back: a failure (signature and initials are never
                       answered, so they stay printed content);
      everything else  every paragraph of every displayed part outside the destinations the export writes is unchanged,
                       none is added and none removed — printed labels, headings, instructions, and every destination the
                       export must leave alone. In a paragraph showing a field's inline box only the box characters are
                       read by the fields; a printed glyph box no field owns keeps its state. A written destination
                       nested inside a paragraph of printed text (an inline content control or form field) cannot be
                       separated from that text: it fails, never passes unread.

    Returns {'passed', 'problems': [{'where': a field key | 'outside the written fields' | 'export', 'why'}],
    'fields': {key: {'answered', 'set_by_export', 'expected', 'read'}},
    'outside_written_fields': {'changed', 'added', 'removed', 'inseparable'}}."""
    from documents import word_v3 as w
    problems, readings = [], {}

    def problem(where, why):
        problems.append({'where': where, 'why': why})
    try:
        before, after = w.SlotIndex(w.open_package(original)), w.SlotIndex(w.open_package(exported))
    except Exception as error:                              # (an export that cannot be opened is a failed read-back)
        problem('export', f'the export cannot be opened for reading back ({type(error).__name__})')
        return {'passed': False, 'problems': problems, 'fields': {}, 'outside_written_fields': {}}
    written, owned = set(), {}              # (written destination slot ids; box paragraph id -> owned glyph ordinals)

    def ident(ref):
        return f'{ref.get("part")}#{ref.get("slot")}'
    for f in fields:
        key, kind = f['key'], f.get('kind')
        saved = answers.get(key) or {}
        answered, sets = _answered(saved), _set_by_export(f, saved)
        loc = f.get('locator') or {}
        target = loc.get('target') or {}
        refs = [loc] + list(loc.get('extra') or []) + list(target.get('copies') or [])
        record = readings[key] = {'answered': answered, 'set_by_export': sets}
        try:
            if kind in OPTION_KINDS:
                for box in target.get('boxes') or []:
                    paragraph = f'{box.get("part")}#{str(box.get("slot") or "").rsplit("/", 1)[0]}'
                    if box.get('kind') in INLINE_BOXES and getattr(before.by_id.get(paragraph), 'kind', None) == 'p':
                        mine = owned.setdefault(paragraph, set())
                        if box.get('kind') == 'glyph':
                            mine.add(box.get('glyph', 0))
                    elif sets:
                        written.add(ident(box))
                if sets and target.get('type') != 'checkboxes':
                    written.update(ident(ref) for ref in refs)
                    written.update(f'{loc.get("part")}#{path}' for path in target.get('paragraphs') or [])
                printed = w.constrained_option_states(before, f)
                expected = expected_option_states(f, saved, printed)
                shown = w.constrained_option_states(after, f)
                record.update(expected=expected, read=shown)
                if expected is None:
                    problem(key, 'the saved answer names no printed option')
                elif shown != expected or (sets and any(state is None for state in shown)):
                    problem(key, f"the export shows the marks {shown}, not the saved answer's {expected}")
            elif kind in SCALAR_KINDS:
                if answered:
                    written.update(ident(ref) for ref in refs)
                shown = w.constrained_scalar_value(before, after, f, answered)
                expected = (str(saved.get('text') or '') if answered
                            else w.constrained_scalar_value(before, before, f, False))
                record.update(expected=expected, read=shown)
                if answered and (shown is None or _flat(shown) != _flat(expected)):
                    problem(key, 'the export shows ' + (repr(shown[:80]) if shown is not None else 'no readable value')
                            + ' where the saved answer is ' + repr(expected[:80]))
                elif not answered and shown != expected:
                    problem(key, f'the export shows {shown!r:.80} where the blank form shows {expected!r:.80} and '
                                 'nothing was saved')
            elif answered:
                written.update(ident(ref) for ref in refs)
                problem(key, f'a saved {kind} answer cannot be read back')
        except Exception as error:                          # (what cannot be read back is a failure, never a pass)
            problem(key, f'the field cannot be read back ({type(error).__name__})')

    def covered(slot_id):
        return any(slot_id == d or slot_id.startswith(d + '/') for d in written)

    def inseparable(slot_id):
        return any(d.startswith(slot_id + '/') and not d[len(slot_id) + 1:].startswith('txbx[') for d in written)

    def paragraph_slots(index):
        return {s.id: s for s in index.slots if s.kind == 'p' and not covered(s.id)}
    old, new = paragraph_slots(before), paragraph_slots(after)
    inline = sorted(p for p in old if inseparable(p))
    changed = sorted(p for p in old if p in new and p not in inline
                     and _paragraph_reading(old[p], owned.get(p)) != _paragraph_reading(new[p], owned.get(p)))
    outside = {'changed': changed, 'added': sorted(set(new) - set(old)), 'removed': sorted(set(old) - set(new)),
               'inseparable': inline}
    if any(outside.values()):
        problem(OUTSIDE, 'printed content outside the written fields changed: '
                + '; '.join(f'{name} {", ".join(ids[:6])}' for name, ids in outside.items() if ids))
    return {'passed': not problems, 'problems': problems, 'fields': readings, 'outside_written_fields': outside}


def stop_decision(verdict, path):
    """Whether one send's verdict stops the stage. Unsafe output and contract failures stop it — EXCEPT unsafe output on
    the paused, default-off field_relations path, which is recorded as veto evidence (a contract failure there still
    stops it)."""
    if not verdict['stops_stage']:
        return False, None
    if path == 'field_relations' and verdict['verdict'] == 'unsafe' and not verdict['contract']:
        return False, 'veto_evidence'
    return True, verdict['verdict']


# ── the request process's checks, per stage ──────────────────────────────────────────────────────────────────────

def stage_preconditions(declaration, stage, root, *, database_prefix=sq.DATABASE_PREFIX, rebuild=REBUILD, environ=None,
                        ledger=None, expect=None):
    """Asserted before anything is written for a stage: model_check's own preconditions for everything they share
    (database, state directory, synthetic mode, live Sonnet 5 at the declared rates, credential, scrubbed environment,
    leak scan, reconciled ledger), then this stage's settings and its declared pricing version. `expect`: another
    runner's expectations (ops/standing_qa.py): its model, and `max_output_tokens` / `timeout_seconds`, the per-request
    bounds a profile it has no name for must fit; None: this campaign's Sonnet 5 profiles by name."""
    from django.conf import settings
    from core import generation
    require(stage in STAGES, f'No stage runner for {stage!r}.')
    checked = sq.preconditions(declaration, stage, root, database_prefix=database_prefix, rebuild=rebuild,
                               environ=environ, ledger=ledger, expect=expect)
    require(settings.QUILLMD_WORD_ENGINE == 'v3', 'The stage runs the v3 Word engine.')
    require(not (settings.WM_NARRATIVE or settings.V3_FIELD_RELATIONS or settings.V3_GENERATION_BATCHES
                 or settings.V3_HISTORY_CONTEXT), 'Every contract flag is off (field relations only around its sends).')
    require(not settings.QUILLMD_LAYOUT_SOCKET, 'The deployed-equivalent path has no layout socket.')
    mapping = stage == 'mapping'
    require(bool(settings.QUILLMD_MAPPING_ASSISTANCE) is mapping and bool(settings.QUILLMD_MAPPING_ASSISTANCE_LIVE) is mapping,
            'Mapping assistance (and its live admission) is on for the mapping stage only.')
    config = generation.configuration()
    if expect is None:
        require(config['request_profile'].get('profile') == 'claude-sonnet-5-v1'
                and 'invalid' not in config['request_profile'],
                'The request profile is not the Sonnet 5 generation profile.')
    else:
        require(within_bounds(config['request_profile'], expect),
                'The generation request profile is invalid or outside the declared per-request bounds.')
    if mapping:
        from core import mapping_assistance
        profile = mapping_assistance.request_profile(config)
        if expect is None:
            require(profile['profile'] == mapping_assistance.PROFILE and profile['max_output_tokens'] == 20000,
                    'The mapping request profile is not the declared Sonnet 5 blank-mapping profile.')
        else:
            require(within_bounds(profile, expect),
                    'The mapping request profile is invalid or outside the declared per-request bounds.')
    return {**checked, 'stage_flags': {name: os.environ.get(name, '') for name in STAGE_FLAGS[stage]},
            'word_engine': settings.QUILLMD_WORD_ENGINE, 'mapping_assistance': bool(settings.QUILLMD_MAPPING_ASSISTANCE),
            'layout_socket': settings.QUILLMD_LAYOUT_SOCKET}


def within_bounds(profile, expect):
    """Whether a request profile is valid and inside another runner's per-request bounds (`expect`
    max_output_tokens and timeout_seconds): an integer output limit and client timeout, each positive and at most the
    bound."""
    tokens, timeout = (profile or {}).get('max_output_tokens'), (profile or {}).get('timeout_seconds')
    return (isinstance(profile, dict) and 'invalid' not in profile and type(tokens) is int and type(timeout) is int
            and 0 < tokens <= expect['max_output_tokens'] and 0 < timeout <= expect['timeout_seconds'])


def amended(amendment, send):
    """Whether `send` is priced under the one key a verified amendment changes."""
    return amendment is not None and send.pricing_key == amendment.pricing_key


def require_price(declaration, config, send, amendment=None):
    """The quote's or job's configuration carries the version `send` must be priced at: the declared one, or for an
    amended send the amendment's (and the amendment's contract)."""
    if amended(amendment, send):
        require(config.get('pricing_version') == amendment.pricing_version
                and config.get('ordinary_field_contract') == amendment.contract
                and config.get('model') == declaration.model and config.get('mode') == 'live',
                f'{send.id} is priced {config.get("pricing_version")}, not the amended {send.pricing_key} version.')
        return
    require(config.get('pricing_version') == declaration.pricing_version(send.pricing_key)
            and config.get('model') == declaration.model and config.get('mode') == 'live',
            f'{send.id} is priced {config.get("pricing_version")}, not the declared {send.pricing_key} version.')


def amendment_in_force(campaign):
    """The campaign's contract-identity amendment, verified (or None): it names the contract this engine runs, and the
    version it replaces is the one the ledger's first attempt pinned (Campaign.pricing_version)."""
    amendment = campaign.amendment
    if amendment is None:
        return None
    from core import v3_field_relations
    require(amendment.contract == v3_field_relations.CONTRACT,
            f'The amendment names the contract {amendment.contract}; this engine runs {v3_field_relations.CONTRACT}.')
    require(campaign.pricing_version(amendment.pricing_key) == amendment.pricing_version,
            'The amendment is not the version in force.')
    return amendment


def remaining_limits(campaign, stage):
    """(stage, total): what is left under the limits in force, at the pinned rates."""
    rows = campaign.rows()
    limits = campaign.limits(rows)
    return (limits.stage(stage).limit - campaign.totals(stage)['exposure'],
            limits.total - campaign.totals()['exposure'])


def pending_sends(campaign, stage, plan):
    """(sends, remainder). The fixed plan — or, once the stage has failed and until it passes, ONLY the sends its latest
    failure recorded as not sent, in plan order (`remainder` then describes them; None otherwise). Refuses when that
    failure records no readable list, names a send the plan does not have, leaves nothing unsent, names a send that
    already has an attempt (nothing is ever sent twice), or drops a planned send it neither made nor lists; and a mapping
    encounter whose form's mapping send is not in the same remainder (its form would not exist in this run)."""
    state = campaign.ledger.stage_state(stage)
    if not state['failures'] or state['state'] == 'passed':
        return list(plan), None
    number = state['failures']
    summary = state['failed'][-1].get('summary')
    require(isinstance(summary, dict) and isinstance(summary.get('not_sent'), list)
            and isinstance(summary.get('plan'), list) and isinstance(summary.get('sends', []), list)
            and all(isinstance(i, str) for i in summary['not_sent'] + summary['plan']),
            f'Stage {stage} failure {number} records no readable list of the sends it did not make; the remainder '
            'cannot be established and nothing is sent again.')
    not_sent, recorded = summary['not_sent'], summary['plan']
    by_id = {send.id: send for send in plan}
    require(len(set(not_sent)) == len(not_sent) and set(not_sent) <= set(recorded) and set(recorded) <= set(by_id),
            f'Stage {stage} failure {number} names a send twice, or one the fixed plan does not have.')
    require(not_sent, f'Stage {stage} failure {number} left no send unsent; there is no remainder to send.')
    attempted = set()
    for attempt, _ in campaign.rows():
        if attempt.get('stage') != stage:
            continue
        send = attempt.get('send')
        require(isinstance(send, dict) and isinstance(send.get('id'), str),
                f'Attempt {attempt.get("number")} of stage {stage} records no send; the sends already made cannot be '
                'established.')
        attempted.add(send['id'])
    again = sorted(set(not_sent) & attempted)
    require(not again, f'Stage {stage}: {", ".join(again)} already has an attempt; a send is never made twice.')
    unexercised = {row['send']['id'] for row in summary.get('sends', []) if isinstance(row, dict)
                   and 'not_exercised' in row and isinstance(row.get('send'), dict)}
    dropped = sorted(set(recorded) - set(not_sent) - attempted - unexercised)
    require(not dropped, f'Stage {stage} failure {number} neither made nor lists {", ".join(dropped)}; the remainder '
                         'cannot be established.')
    sends = [send for send in plan if send.id in set(not_sent)]
    for send in sends:
        if send.path == 'mapping_encounter':
            require(f'mapping:{send.form}' in not_sent, f'{send.id} needs its form\'s mapping send in the same run, '
                                                        'and that send was already made; it is not sent.')
    return sends, {'failure': number, 'plan': [send.id for send in plan], 'sends': [send.id for send in sends],
                   'already_made': sorted(attempted)}


def earlier_stops(ledger, stage, current=()):
    """The attempts of `stage` outside the run deciding now (`current`: that run's attempt numbers) that did not end
    clean: the stage's failures record each attempt's per-send row, and an attempt is clean only when exactly one row
    names it, for the send the attempt records, and says it did not stop the stage. Anything else — a row that stopped
    the stage (a contract failure, unsafe output, an interruption), or no row at all (a run that ended before it could
    be decided) — is returned. A send is never made twice, so while any is left the stage can NEVER pass: a remainder
    completes the stage's evidence, not its pass (refutations F1 and F1-REMAINDER-FALSE-PASS). Read-only.
    Returns [{'send', 'attempt', 'failure', 'why'}] in attempt order."""
    state = ledger.stage_state(stage)
    rows = {}
    for failure in state['failed']:
        summary = failure.get('summary')
        recorded = summary.get('sends') if isinstance(summary, dict) else None
        for row in recorded if isinstance(recorded, list) else []:
            if isinstance(row, dict) and type(row.get('attempt')) is int:
                rows.setdefault(row['attempt'], []).append((failure.get('number'), row))
    current, found = set(current), []
    for attempt, _ in ledger.rows():
        number = attempt.get('number')
        if attempt.get('stage') != stage or number in current:
            continue
        send = attempt.get('send') if isinstance(attempt.get('send'), dict) else {}
        named = rows.get(number, [])
        failure, row = named[0] if len(named) == 1 else (None, None)
        if row is None:
            why = ('no decision of the stage records how it ended' if not named
                   else 'more than one decision of the stage records it')
        elif not (isinstance(row.get('send'), dict) and row['send'].get('id') == send.get('id')):
            why = 'its decision records it for another send'
        elif row.get('stops_stage') is not False:
            why = f'it stopped the stage ({row.get("recorded_as") or "no reason recorded"})'
        else:
            continue
        found.append({'send': send.get('id'), 'attempt': number, 'failure': failure, 'why': why})
    return found


# ── the per-send machinery ───────────────────────────────────────────────────────────────────────────────────────

class Deadline:
    """signal.SIGALRM raises SendDeadline after `seconds` (the main thread only); cleared on exit whatever happened."""

    def __init__(self, seconds):
        self.seconds, self.fired = seconds, None

    def _fire(self, signum, frame):
        # (remembered here as well: the SDK wraps what its transport raises, so the exception may arrive renamed)
        self.fired = f'the send did not return within {self.seconds} s'
        raise SendDeadline(self.fired)

    def __enter__(self):
        self.previous = signal.signal(signal.SIGALRM, self._fire)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)
        return self

    def __exit__(self, *exc):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.previous)
        return False


def unsent(job, receipt, captured):
    return (job.state == 'failed' and any((job.error or '').startswith(prefix) for prefix in UNSENT_PREFIXES)
            and receipt is None and not captured)


def outcome_class(job, receipt, usage_row, captured):
    if receipt is not None and usage_row is not None and job.state in ('succeeded', 'failed'):
        return 'completed'
    if unsent(job, receipt, captured):
        return 'not_sent'
    if job.state == 'reconciliation':
        return 'reconciliation'
    return 'uncertain'


class Run:
    """One stage run in the request process: the campaign, its world, and what every send recorded."""

    def __init__(self, campaign, stage, *, secret, provenance, inputs, forms, world, checked, deadline):
        self.campaign, self.stage, self.secret, self.provenance = campaign, stage, secret, provenance
        self.inputs, self.forms, self.world, self.checked, self.deadline = inputs, forms, world, checked, deadline
        self.declaration, self.ledger, self.root = campaign.declaration, campaign.ledger, campaign.root
        self.rates = campaign.pinned_terms().rates
        self.amendment = amendment_in_force(campaign)
        self.templates = {}             # form -> (template pk, deterministic fields) from its mapping send
        self.sends, self.veto_evidence, self.stopped = [], [], None

    # ── admission and the attempt ────────────────────────────────────────────────────────────────────────────────
    def admit(self, maximum):
        return self.campaign.admit(self.stage, maximum, runner_commit=self.provenance.get('runner_commit'))

    def require_not_stopped(self):
        check = getattr(self.campaign, 'require_not_stopped', None)       # (the standing campaign's Stop file)
        if check is not None:
            check()
        require(self.ledger.campaign_stop() is None, 'The campaign is stopped.')

    def pace_generation(self):
        """Waits, sending nothing, until the application's per-user generation rate limit admits one more Generate
        (generation_headroom), and returns the seconds waited. Without it a long run's next Generate is refused — on
        2026-10-02 a campaign's 31st generation inside ten minutes stopped its stage — and in the transcription stage
        the refusal strands a transcript whose generation is never made (each send is made once). The Stop file is
        honoured every second; a window that does not reset when the application says it will is a stop."""
        state = generation_headroom(self.world.user)
        waited = 0.0
        while state['left'] < 1:
            self.require_not_stopped()
            require(waited <= state['window'] + 5 and 0 <= state['resets_in'] <= state['window'],
                    'The generation rate-limit window did not reset when the application says it would; nothing was '
                    'sent.')
            step = min(1.0, state['resets_in'] + 0.05)
            time.sleep(step)
            waited += step
            state = generation_headroom(self.world.user)
        return round(waited, 3)

    def attempt(self, send, job, maximum, bound, held, shown, extra):
        declaration = self.declaration
        number = len(self.ledger.rows()) + 1
        record = {'number': number, 'campaign': declaration.campaign, 'authority_id': declaration.authority_id,
                  'stage': self.stage, 'send': send.record(), 'maximum_cost': format(maximum, 'f'),
                  'exposure_bound': format(bound, 'f'), 'rates': self.rates.as_dict(), 'hold': format(held, 'f'),
                  'shown_maximum_charge': format(shown, 'f'), 'pricing_version': job.config['pricing_version'],
                  'job': str(job.pk), 'declaration_sha256': declaration.sha256, 'declaration_commit': declaration.commit,
                  'limits': self.campaign.limits().record(), 'terms': self.campaign.pinned_terms().record(),
                  'engine_files': sq.watched_hashes(), 'freeze_manifest_sha256': self.inputs['freeze']['manifest_sha256'],
                  'runner_commit': self.provenance.get('runner_commit'), 'started_at': pc.now(), 'pid': os.getpid(),
                  **({'amendment': self.amendment.record()} if self.amendment is not None else {}), **extra}
        self.ledger.write_attempt(record)                                # BEFORE anything can be sent
        return record

    def refuse_job(self, job, reason):
        """Cancels a queued job through the product (its hold is released; it never ran) and stops the stage."""
        from core.jobs import cancel
        cancel(job, self.world.user)
        raise StageStop(reason + '; the job was cancelled unsent')

    # ── the one request ──────────────────────────────────────────────────────────────────────────────────────────
    def send(self, attempt, job, evidence, maximum, output_limit):
        """run_one ONCE under the capture and the deadline, then the outcome record and the contract checks."""
        from core.jobs import run_one
        from core.models import AuditEvent, ProviderReceipt, Reservation, Usage
        number = attempt['number']
        receipts_before = ProviderReceipt.objects.count()
        pc.CURRENT_ATTEMPT.update(number=number, evidence_dir=str(evidence), secret=self.secret)
        timer = Deadline(self.deadline)
        try:
            with timer:
                worked = run_one()
        except SendDeadline:
            worked = None
        finally:
            pc.CURRENT_ATTEMPT.clear()
        deadline = timer.fired
        job.refresh_from_db()
        captured = (evidence / 'request.json').exists()
        receipt = ProviderReceipt.objects.filter(job=job).first()
        usage_row = Usage.objects.filter(job=job).first()
        # (the response as the capture retained it on arrival, whatever the product then did: the product stores its
        # result only once settlement succeeded, so a billed response it refused is known from here alone — refutation
        # RAW-RESPONSE-LOST-200)
        received = pc.received_response(evidence)
        data, parsed = sq.raw_result(job)
        if data is not None:
            pc.write_new(evidence / 'provider-result.json', data, raw=True)
        message = (parsed or {}).get('provider_output', parsed) if isinstance(parsed, dict) else {}
        message = message if isinstance(message, dict) else {}
        source = 'product_result' if message else None
        body = (received or {}).get('body_json')
        if not message and (received or {}).get('status_code') == 200 and isinstance(body, dict):
            message, source = body, 'provider_response'
        usage = message.get('usage') if isinstance(message.get('usage'), dict) else (
            sq.usage_from_receipt(receipt.units) if receipt is not None else None)
        cls = outcome_class(job, receipt, usage_row, captured) if deadline is None else (
            'not_sent' if unsent(job, receipt, captured) else 'uncertain')
        prefix = 'mapping.' if job.kind == 'mapping' else 'job.'
        audit = AuditEvent.objects.filter(target=str(job.pk), action__in=[prefix + s for s in ('failed', 'reconciliation',
                                                                                            'succeeded')]
                                          ).order_by('-created_at').first()
        details = audit.details if audit else {}
        computed = standard = None
        if usage is not None:
            try:
                computed = pc.usage_cost(usage, self.rates)
                standard = pc.usage_cost(usage, self.rates, unknown_geography_margin=False)
            except (KeyError, ValueError, TypeError):
                computed = standard = None
        outcome = {'class': cls, 'job': str(job.pk), 'job_kind': job.kind, 'job_state': job.state,
                   'job_error': job.error, 'worker_ran': worked, 'deadline': deadline,
                   'error_class': details.get('error_class', ''), 'billing': details.get('billing', ''),
                   'request_captured': captured, 'sends_at_transport': pc.SENT.get(number, 0),
                   'served_model': message.get('model'), 'stop_reason': message.get('stop_reason'), 'usage': usage,
                   'computed_cost': format(computed, 'f') if computed is not None else None,
                   'computed_cost_metered_geography': format(standard, 'f') if standard is not None else None,
                   'provider_request_id': job.provider_request_id, 'provider_resource_id': job.provider_resource_id,
                   'raw_result_sha256': job.result_sha256 or None, 'message_source': source,
                   'provider_response': ({'status_code': received.get('status_code'),
                                          'request_id': received.get('request_id'),
                                          'message_id': body.get('id') if isinstance(body, dict) else None,
                                          'body_sha256': received.get('body_sha256'),
                                          'body_bytes': received.get('body_bytes')} if received else None),
                   'settlement': {'receipt_actual_cost': str(receipt.actual_cost) if receipt else None,
                                  'usage_actual_cost': str(usage_row.actual_cost) if usage_row else None,
                                  'charged_cost': str(usage_row.charged_cost) if usage_row else None,
                                  'reservations': sorted(r.state for r in Reservation.objects.filter(job=job))},
                   'recorded_at': pc.now()}
        outcome['exposure'] = format(pc.exposure(attempt, outcome, self.rates), 'f')
        self.ledger.write_outcome(number, outcome)                        # AFTER, whatever happened
        findings = []

        def contract(code, why):
            findings.append({'code': code, 'why': why})
        if deadline is not None:
            contract('uncertain_outcome', deadline + '; the outcome is unknown and it is never re-sent')
        if cls != 'completed' or job.state != 'succeeded':
            code = {'reconciliation': 'reconciliation', 'uncertain': 'uncertain_outcome'}.get(cls, 'validator_failure')
            contract(code, f'the attempt ended {cls} with the job {job.state} ({outcome["error_class"] or "no error class"})')
        if ProviderReceipt.objects.count() - receipts_before > 1 or pc.SENT.get(number, 0) > 1:
            contract('more_than_one_request', 'more than one provider request was made for the attempt')
        if outcome['served_model'] != self.declaration.model:
            contract('wrong_served_model', f'the provider served {outcome["served_model"]!r}, not {self.declaration.model}')
        if outcome['stop_reason'] != 'end_turn':
            contract('stop_reason_not_end_turn', f'the provider stopped with {outcome["stop_reason"]!r}, not end_turn')
        tokens = (usage or {}).get('output_tokens')
        if not (type(tokens) is int and Decimal(tokens) < OUTPUT_SHARE_LIMIT * output_limit):
            contract('output_over_70_percent', f'output tokens {tokens} are not below 70% of the {output_limit}-token limit')
        if not self.declaration.inference_geo and (usage or {}).get('inference_geo') == 'us':
            contract('metered_us_while_unset', 'the provider metered inference_geo us while the declaration leaves it unset')
        if standard is None or standard > maximum:
            contract('settlement_mismatch', 'the provider-reported cost is unknown or above the attempt\'s maximum')
        if receipt is None or usage_row is None or not (receipt.actual_cost == usage_row.actual_cost == standard):
            contract('settlement_mismatch', 'the settled cost is not the provider-reported usage at the pinned rates')
        if not captured:
            contract('request_not_captured', 'the outbound request was not captured')
        if received is None and (data is not None or receipt is not None):
            contract('response_not_captured', 'the provider answered, but its response was not retained as received')
        return outcome, message, findings

    def audit(self, job, evidence):
        from core.management.commands.audit_billing import audit_report
        report = audit_report()
        pc.write_new(evidence / 'audit-billing.json', report)
        return [{'code': 'audit_failure', 'why': problem} for problem in sq.audit_checks(report, job)]

    def reconcile(self):
        """After every send: every attempt has an outcome and the exposure stays inside the limits in force."""
        rows = self.campaign.rows()
        limits = self.campaign.limits(rows)
        problems = []
        if any(outcome is None for _, outcome in rows):
            problems.append('an attempt has no outcome after its send')
        stage, total = self.campaign.totals(self.stage)['exposure'], self.campaign.totals()['exposure']
        # (a campaign with no monetary ceiling — ops/standing_qa.py — has None for both limits: nothing to be past)
        stage_limit, total_limit = limits.stage(self.stage).limit, limits.total
        if (stage_limit is not None and stage > stage_limit) or (total_limit is not None and total > total_limit):
            problems.append(f'exposure {stage} (stage) / {total} (total) is past a limit in force')
        return [{'code': 'reconciliation', 'why': problem} for problem in problems]

    def scan(self, evidence, attempt, context):
        """The provenance manifest and the leak scan of the whole campaign root: unreadable or leaked is a campaign stop."""
        reasons = []
        try:
            sq.write_manifest(evidence, attempt, context)
        except (OSError, pc.Refused) as error:
            reasons.append(f'the evidence could not be read for its manifest: {error}')
        try:
            hits = pc.leaked(self.root, self.secret, exclude=(self.declaration.credential_file,))
        except pc.Refused as refused:
            hits = []
            reasons.append(f'the retained evidence could not be scanned for the credential: {refused}')
        if hits:
            reasons.append('the credential was found in retained evidence: ' + ', '.join(hits))
        if reasons:
            self.ledger.write_stop({'reason': 'the retained evidence could not be scanned, or carries the credential',
                                    'detail': reasons})
        return [{'code': 'credential_leak', 'why': reason} for reason in reasons]

    def context(self, send):
        import django
        import anthropic
        identity = pc.git_identity(REBUILD)
        return {'campaign': self.declaration.campaign, 'authority_id': self.declaration.authority_id, 'send': send.record(),
                'runner': {'commit': self.provenance.get('runner_commit') or identity['commit'], 'clean': identity['clean'],
                           'files': sq.watched_hashes()},
                'declaration': {'path': self.declaration.path, 'sha256': self.declaration.sha256,
                                'commit': self.declaration.commit, 'commit_time': self.declaration.commit_time},
                'freeze': {k: v for k, v in self.inputs['freeze'].items() if k != 'frozen_files'},
                'settings': self.checked, 'login': sq.LOGIN,
                'versions': {'python': sys.version.split()[0], 'django': django.get_version(),
                             'anthropic': anthropic.__version__}}

    # ── one send, whole ──────────────────────────────────────────────────────────────────────────────────────────
    def run_send(self, send):
        """One send end to end. Returns its record; raises StageStop when it stopped before an attempt was written."""
        planned = self.planned.get(send.id)
        if planned is not None:
            self.admit(planned)            # (a preview on the planned maximum: nothing is created if it cannot fit)
        do = {'mapping': self.mapping_send, 'mapping_encounter': self.encounter_send}.get(send.path, self.notes_send)
        return do(send)

    def finish(self, send, attempt, evidence, outcome, findings, verdict_fields, extra):
        """The per-send verdict (classify_case), the billing audit, the reconciliation, the manifest and the scan."""
        from core.models import Job
        job = Job.objects.get(pk=attempt['job'])
        findings = list(findings) + self.audit(job, evidence) + self.reconcile()
        codes = sorted({f['code'] for f in findings})
        verdict = pc.classify_case(verdict_fields, codes)
        stops, why = stop_decision(verdict, send.path)
        record = {'send': send.record(), 'attempt': attempt['number'], 'class': outcome['class'], 'findings': findings,
                  'verdict': verdict, 'stops_stage': stops, 'recorded_as': why, **extra}
        pc.write_new(evidence / 'classification.json', record)
        scan = self.scan(evidence, attempt, {**self.context(send), 'classification_sha256':
                                             pc.file_sha256(evidence / 'classification.json')})
        if scan:
            record = {**record, 'findings': findings + scan, 'stops_stage': True, 'recorded_as': 'unsafe'}
            stops = True
        if why == 'veto_evidence':
            self.veto_evidence.append({'send': send.id, 'attempt': attempt['number'], 'unsafe': verdict['unsafe']})
        self.sends.append(record)
        return record, stops

    # ── mapping ──────────────────────────────────────────────────────────────────────────────────────────────────
    def upload(self, data, name, filename):
        from core.models import Template
        before = set(Template.objects.values_list('pk', flat=True))
        response = steps.upload_form(self.world.client, self.world.department.pk, data, name, filename)
        created = Template.objects.exclude(pk__in=before)
        require(response.status_code == 302 and created.count() == 1 and created.get().name == name,
                f'The upload of {name} did not create exactly one form ({response.status_code}).')
        template = created.get()
        return template, template.versions.get(number=1)

    def mapping_send(self, send):
        from core import mapping_assistance
        from core.models import Job, Reservation
        name, data = send.form, self.forms[send.form]
        number = len(self.ledger.rows()) + 1
        template, version = self.upload(data, f'SYNTHETIC SONNET5 MAPPING {name} attempt {number}', f'{name}.docx')
        require(version.contract == 'v3' and template.sha256 == hashlib.sha256(data).hexdigest(),
                f'{name} was not stored as the frozen v3 form.')
        page = self.world.client.get(f'/templates/{template.pk}/assistance/')
        require(page.status_code == 200, f'The mapping-assistance page failed ({page.status_code}).')
        text = page.content.decode()
        approval = re.search(r'name="approval" value="([^"]*)"', text)
        shown = re.search(r'Maximum charge: \$([0-9.]+)\.', text)
        require(approval and shown, 'The mapping-assistance page shows no complete quote.')
        before = set(Job.objects.filter(kind='mapping').values_list('pk', flat=True))
        response = self.world.client.post(f'/templates/{template.pk}/assistance/', {
            'action': 'queue', 'approval': htmlmod.unescape(approval.group(1)), 'blank_only': 'on'})
        jobs = list(Job.objects.filter(kind='mapping').exclude(pk__in=before))
        if not (response.status_code == 302 and len(jobs) == 1 and jobs[0].state == 'queued'):
            from core.jobs import cancel
            for extra in jobs:
                if extra.state == 'queued':
                    cancel(extra, self.world.user)
            raise StageStop('The mapping request did not queue exactly one job; nothing was sent')
        job = jobs[0]
        if list(Job.objects.filter(state='queued').values_list('pk', flat=True)) != [job.pk]:
            self.refuse_job(job, 'another queued job would run first')
        try:
            require_price(self.declaration, job.config, send)
            maximum = Decimal(job.config['mapping_maximum_cost'])
            held = sum((r.amount for r in Reservation.objects.filter(job=job)), Decimal(0))
            compiled = mapping_assistance.compile_request(version, job.config)
            require(compiled['request_sha256'] == job.config['request_sha256']
                    and Decimal(compiled['maximum_cost']) == maximum and held == maximum * Decimal('1.5')
                    and Decimal(shown.group(1)) == held,
                    'The mapping job\'s hold, its maximum, its request and the page\'s quote disagree.')
            bound = self.admit(maximum)
        except Refused as refused:
            self.refuse_job(job, str(refused))
        evidence = sq.private_evidence(self.root, number)
        case = pc.private_directory(evidence / 'case')
        pc.write_new(case / f'{name}.docx', data, raw=True)
        pc.write_new(evidence / 'deterministic-fields.json', version.fields)
        attempt = self.attempt(send, job, maximum, bound, held, Decimal(shown.group(1)), {
            'form_sha256': template.sha256, 'template': str(template.pk), 'version': str(version.pk),
            'request_sha256': job.config['request_sha256'],
            'request_profile': job.config['mapping_request_profile']})
        try:
            outcome, message, findings = self.send(attempt, job, evidence, maximum,
                                                   job.config['mapping_request_profile']['max_output_tokens'])
            self.templates[name] = (template.pk, version.fields)
            fields, extra = {}, {}
            if not findings:
                fields, extra, unsafe = self.grade_mapping(send, template, version, evidence)
                findings += unsafe
            return self.finish(send, attempt, evidence, outcome, findings, fields, extra)
        except BaseException as error:
            return self.interrupted(send, attempt, evidence, error)

    def grade_mapping(self, send, template, version, evidence):
        """validate_proposal's output (the new version), what the clinician sees, and the frozen grader's verdict."""
        name = send.form
        latest = template.versions.order_by('-number').first()
        require(latest.number == version.number + 1 and latest.assistance.get('job_id'),
                'The mapping job did not create exactly one proposed version.')
        proposal = {'fields': latest.fields, 'review': latest.assistance}
        pc.write_new(evidence / 'proposal.json', proposal)
        page = self.world.client.get(f'/templates/{template.pk}/assistance/')
        seen = clinician_view(page.content.decode()) if page.status_code == 200 else {'status': page.status_code}
        pc.write_new(evidence / 'clinician-view.json', seen)
        expressible = self.inputs['selftest']['forms'][name]['expressibility']
        pc.write_new(evidence / 'expressible.json', expressible)
        graded = self.grade(name, evidence / 'proposal.json', evidence / 'deterministic-fields.json',
                            evidence / 'expressible.json', evidence / 'graded.json')
        pc.write_new(evidence / 'deterministic-output.json', {'fields': version.fields, 'review': {}})
        baseline = self.grade(name, evidence / 'deterministic-output.json', evidence / 'deterministic-fields.json',
                              evidence / 'expressible.json', evidence / 'graded-deterministic.json')
        unsafe = mapping_findings(graded, baseline, {c['id'] for c in self.inputs['maps'][name]['controls']
                                                     if c.get('applies_to')})
        extra = {'form': name, 'version': str(latest.pk), 'unresolved': len(latest.assistance.get('unresolved') or []),
                 'changes': latest.assistance.get('changes') or [], 'summary': graded['summary'],
                 'deterministic_summary': baseline['summary'],
                 'protected_areas_left_answerable': [r['id'] for r in graded['controls'] if r['type'] == 'must_refuse'
                                                     and r['outcome'] == 'wrong'],
                 'clinician_sees': {'areas_requiring_review': len(seen.get('areas', [])),
                                    'confirm_blocked': graded['clinician_view']['confirm_blocked']}}
        return mapping_outcomes(graded), extra, unsafe

    def grade(self, name, output, deterministic, expressible, target):
        """The FROZEN grader, as a subprocess (it denies sockets for its whole process); its provenance must name this
        freeze and the grader's frozen sha256."""
        done = subprocess.run([sys.executable, '-B', str(MAPPING_DIR / 'grade_app_path.py'), '--grade', str(output),
                               '--form', name, '--deterministic', str(deterministic), '--expressible', str(expressible),
                               '--out', str(target)], capture_output=True, text=True, timeout=300,
                              env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(target.parent),
                                   'HOME': str(target.parent), 'PYTHONDONTWRITEBYTECODE': '1'})
        require(done.returncode == 0, f'The frozen grader refused or failed ({done.returncode}): {done.stderr[-300:]}')
        graded = json.loads(target.read_text())
        provenance = graded.get('provenance') or {}
        require(provenance.get('manifest_sha256') == self.inputs['freeze']['manifest_sha256']
                and provenance.get('grader_sha256') == self.inputs['freeze']['frozen_files']['grade_app_path.py'],
                'The grader output does not carry this freeze\'s provenance.')
        return graded

    # ── the mapping stage's encounters (f6a, f6b) ────────────────────────────────────────────────────────────────
    def confirm_proposed(self, template):
        """The clinician's confirmation of the PROPOSED mapping: unmodified when no record is open (automatic);
        otherwise each open record is resolved without removing a field — 'mapped' where the slot is mapped, 'not an
        answer' only for a record with no field key — and the confirmation is ASSISTED. A record that could be resolved
        only by removing a field blocks the encounter (recorded; nothing is sent for it)."""
        from core import v3_mapping
        latest = template.versions.order_by('-number').first()
        unresolved = latest.assistance.get('unresolved') or []
        mode, decisions = 'automatic', []
        if unresolved:
            mapped = v3_mapping.mapped_slots(latest.fields)
            posted = {'action': 'resolve', 'mapping_version': str(latest.pk)}
            for number, row in enumerate(unresolved):
                if v3_mapping.is_mapped(row['slot'], mapped):
                    decision = 'mapped'
                elif not row.get('key'):
                    decision = 'not_answer'
                else:
                    return None, [{'slot': row['slot'], 'key': row['key'], 'blocked': 'only removing the field resolves it'}]
                posted[f'resolution_{number}'] = decision
                decisions.append({'slot': row['slot'], 'key': row.get('key', ''), 'decision': decision})
            response = self.world.client.post(f'/templates/{template.pk}/assistance/', posted)
            require(response.status_code == 302, f'The area decisions were refused ({response.status_code}).')
            latest = template.versions.order_by('-number').first()
            require(latest.assistance.get('assisted') is True and not latest.assistance.get('unresolved'),
                    'The area decisions did not produce an assisted version with no open record.')
            mode = 'assisted'
        response = steps.confirm_mapping(self.world.client, template.pk, latest.pk)
        latest.refresh_from_db()
        require(response.status_code == 302 and latest.confirmed, 'The mapping confirmation was refused.')
        return (latest, mode), decisions

    def encounter_send(self, send):
        from core.models import Template
        name = send.form
        if name not in self.templates:
            return None                                        # (its mapping send was never made)
        template = Template.objects.get(pk=self.templates[name][0])
        confirmed, decisions = self.confirm_proposed(template)
        if confirmed is None:
            self.sends.append({'send': send.record(), 'not_exercised': 'the proposed mapping could not be confirmed '
                               'without removing a field', 'blocked': decisions})
            return None
        version, mode = confirmed
        if name == 'f6a-long-answer':
            notes = self.inputs['long_answer']
        else:
            notes = self.inputs['maps'][name]['source_note']['text']
        return self.generation_send(send, template, version, notes, extra={'confirmation': mode, 'resolutions': decisions},
                                    judge=self.judge_encounter)

    def judge_encounter(self, send, version, outcomes, exported, original, **_):
        """f6a: an adopted long answer is exported WHOLE (partial = a data-loss failure); f6b: NOTHING is filled (any
        adoption is an answer the administrative note does not support: unsafe)."""
        from documents import word_v3 as w
        fields, findings, details = {}, [], {}

        def place(f):
            return f['locator']['part'] + '#' + f['locator']['slot']
        if send.form == 'f6b-admin-missing':
            for f in version.fields:
                adopted = outcomes.get(f['key'], {})
                fields[f['key']] = 'unsupported_accepted' if adopted.get('status') == 'supported' else 'held_correct'
            before, after = w.SlotIndex(w.open_package(original)), w.SlotIndex(w.open_package(exported))

            def reading(index, f):
                """What the engine's own constrained reader sees at the field (option states, or the scalar value; a
                ticked legacy checkbox changes no text, and a blank one may be rewritten as explicitly unticked)."""
                if f['kind'] in ('choice', 'multi_choice', 'checkbox'):
                    return w.constrained_option_states(index, f)
                return w.constrained_scalar_value(before, index, f, False)
            filled = [f['key'] for f in version.fields if f['kind'] not in ('signature', 'initials')
                      and reading(after, f) != reading(before, f)]
            details['destinations_changed'] = filled
            details['readings'] = {f['key']: {'original': reading(before, f), 'export': reading(after, f)}
                                   for f in version.fields if f['kind'] not in ('signature', 'initials')}
            if filled:
                findings.append({'code': 'adopted_without_source_support',
                                 'why': 'the administrative note answers nothing, and the export changed ' + ', '.join(filled)})
            return fields, findings, details
        answer = ' '.join(self.inputs['long_answer'].split())
        region = next(a for a in self.inputs['maps'][send.form]['areas'] if a['id'] == 'f6a.A2')['destination']['region']
        index = w.SlotIndex(w.open_package(exported))
        details['long_answer'] = {'adopted': False, 'whole': False, 'region': region}
        for f in version.fields:
            adopted = outcomes.get(f['key'], {})
            slot = f['locator']['slot']
            is_long = slot == region or slot.startswith(region + '/')
            if adopted.get('status') != 'supported':
                fields[f['key']] = 'over_held' if is_long else 'held_correct'
                continue
            if not is_long:
                fields[f['key']] = 'recorded_not_asserted'    # (the frozen map asserts nothing note-based for it)
                continue
            cell = ' '.join(w.text_of(index.by_id[place(f)].el).split())
            whole = answer in cell and answer in ' '.join(str(adopted.get('text', '')).split())
            details['long_answer'] = {'adopted': True, 'whole': whole, 'key': f['key'], 'region': region,
                                      'exported_characters': len(cell), 'answer_characters': len(answer)}
            fields[f['key']] = 'supported_correct' if whole else 'supported_incomplete'
            if not whole:
                findings.append({'code': 'export_verification_failed',
                                 'why': 'the long answer was adopted but is not exported whole (data loss)'})
        return fields, findings, details

    # ── ordinary notes ───────────────────────────────────────────────────────────────────────────────────────────
    def notes_send(self, send):
        from django.test.utils import override_settings
        case = next(c for c in self.inputs['cases']['cases'] if c['id'] == send.case)
        form = self.inputs['cases']['forms'][case['form']]
        with override_settings(**steps.PATH_FLAGS[send.path]):
            number = len(self.ledger.rows()) + 1
            template, version = self.upload(self.forms[case['form']],
                                            f'SYNTHETIC SONNET5 NOTES {case["id"]} {send.path} attempt {number}',
                                            'intake.docx')
            if version.fields != form['fields']:
                raise StageStop(f'{send.id}: the stored mapping differs from the frozen cases.json fields (nothing sent)')
            page = self.world.client.get(f'/templates/{template.pk}/')
            require(page.status_code == 200, f'The mapping review page failed ({page.status_code}).')
            response = steps.confirm_mapping(self.world.client, template.pk, version.pk)
            version.refresh_from_db()
            require(response.status_code == 302 and version.confirmed, 'The mapping confirmation was refused.')
            return self.generation_send(send, template, version, case['notes'], extra={'case': case['id']},
                                        judge=self.judge_notes(case))

    def judge_notes(self, case):
        def judge(send, version, outcomes, exported, original, *, raw, reviewed, evidence):
            selection = raw_selection(raw, version.fields, case['notes'], send.path)
            disagreeing = relation_disagreements(raw, version.fields, case['notes'], send.path)
            pc.write_new(evidence / 'raw-selection.json', {'path': send.path, 'selection': selection,
                                                           'relation_disagreements': sorted(disagreeing)})
            replayed = self.replay(case['id'], send.path, selection, evidence)
            rows = replayed['responses'][case['id']][send.path]
            fields, details = {}, {}
            by_key = {f['key']: f for f in version.fields}
            for key, expectation in case['fields'].items():
                outcome, detail = notes_field_outcome(expectation, by_key[key], outcomes.get(key, {}),
                                                      (reviewed or {}).get(key), rows.get(key),
                                                      model_disagrees=key in disagreeing)
                fields[key], details[key] = outcome, detail
                if rows.get(key) and (rows[key]['status'], rows[key]['text']) != (outcomes.get(key, {}).get('status'),
                                                                                   outcomes.get(key, {}).get('text')):
                    detail['served_path_diverged_from_replay'] = {'replay': [rows[key]['status'], rows[key]['text']]}
            return fields, [], {'fields': details}
        return judge

    def replay(self, case_id, path, selection, evidence):
        """The frozen replay of the WHOLE live response (a subprocess); its provenance must name this freeze."""
        responses = evidence / 'replay-input.json'
        pc.write_new(responses, {case_id: {path: selection}})
        state = pc.private_directory(evidence / 'replay-state')
        target = evidence / 'replay.json'
        done = subprocess.run([sys.executable, '-B', str(NOTES_DIR / 'offline_replay.py'), '--state-dir', str(state),
                               '--replay', str(responses), '--skip-form-check', '--out', str(target)],
                              capture_output=True, text=True, timeout=600,
                              env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(state), 'HOME': str(state),
                                   'PYTHONDONTWRITEBYTECODE': '1'})
        require(done.returncode == 0, f'The frozen replay refused or failed ({done.returncode}): {done.stderr[-300:]}')
        replayed = json.loads(target.read_text())
        provenance = replayed.get('provenance') or {}
        require(provenance.get('manifest_sha256') == self.inputs['freeze']['manifest_sha256']
                and provenance.get('grader_sha256') == self.inputs['freeze']['frozen_files']['../notes/offline_replay.py'],
                'The replay output does not carry this freeze\'s provenance.')
        return replayed

    # ── a generation send (notes, and the mapping stage's encounters) ────────────────────────────────────────────
    def generation_send(self, send, template, version, notes, *, extra, judge):
        from django.utils import timezone
        from core import generation
        from core.models import Encounter, Job, Reservation
        paced = self.pace_generation()                   # (before anything is created for this send)
        if paced:
            extra = {**extra, 'generation_paced_seconds': paced}
        before = set(Encounter.objects.values_list('pk', flat=True))
        response = steps.create_encounter(self.world.client, self.world.patient.pk, version.pk, notes,
                                          timezone.localdate().isoformat())
        created = Encounter.objects.exclude(pk__in=before)
        require(response.status_code == 302 and created.count() == 1, 'Encounter creation did not create exactly one.')
        encounter = created.get()
        require(encounter.notes == notes, 'The saved notes are not the frozen notes.')
        token, revision, shown, quoted = sq.page_quote(self.world.client, encounter)
        require_price(self.declaration, quoted, send, self.amendment)
        jobs_before = set(Job.objects.values_list('pk', flat=True))
        response = steps.request_generation(self.world.client, encounter.pk, token, revision)
        jobs = list(Job.objects.exclude(pk__in=jobs_before))
        if not (response.status_code == 302 and len(jobs) == 1 and jobs[0].kind == 'generation'
                and jobs[0].state == 'queued' and jobs[0].encounter_id == encounter.pk):
            from core.jobs import cancel
            said = page_said(response)
            for other in jobs:
                if other.state == 'queued':
                    cancel(other, self.world.user)          # (nothing was sent: whatever was queued is released)
            raise StageStop('Generate did not queue exactly one generation job (status '
                            f'{response.status_code}, {len(jobs)} job(s); the page said: '
                            f'{" | ".join(said) or "nothing"}); nothing was sent')
        job = jobs[0]
        if list(Job.objects.filter(state='queued').values_list('pk', flat=True)) != [job.pk]:
            self.refuse_job(job, 'another queued job would run first')
        try:
            require_price(self.declaration, job.config, send, self.amendment)
            requirements = version.review_requirements
            maximum = generation.maximum_cost(encounter.notes, version.fields, job.config,
                                              context_labels=[row['label'] for row in requirements],
                                              requirements=requirements)
            held = sum((r.amount for r in Reservation.objects.filter(job=job)), Decimal(0))
            require(held == maximum * Decimal('1.5') == shown,
                    'The job\'s hold, its maximum and the page\'s quote disagree.')
            if amended(self.amendment, send):
                # (the amended maximum is the one the plan recomputed and fitted to the limits left, exactly)
                require(maximum == self.planned.get(send.id),
                        f'{send.id}: the job\'s maximum {maximum} is not the amended plan\'s {self.planned.get(send.id)}.')
            bound = self.admit(maximum)
        except Refused as refused:
            self.refuse_job(job, str(refused))
        number = len(self.ledger.rows()) + 1
        evidence = sq.private_evidence(self.root, number)
        case_dir = pc.private_directory(evidence / 'case')
        original = self.forms[send.form]
        pc.write_new(case_dir / 'form.docx', original, raw=True)
        pc.write_new(case_dir / 'notes.txt', notes, raw=True)
        pc.write_new(case_dir / 'mapping.json', version.fields)
        attempt = self.attempt(send, job, maximum, bound, held, shown, {
            'form_sha256': template.sha256, 'template': str(template.pk), 'version': str(version.pk),
            'encounter': str(encounter.pk), 'notes_sha256': hashlib.sha256(notes.encode()).hexdigest(),
            'request_profile': job.config['request_profile'], **extra})
        try:
            outcome, message, findings = self.send(attempt, job, evidence, maximum,
                                                   job.config['request_profile']['max_output_tokens'])
            encounter.refresh_from_db()
            pc.write_new(evidence / 'answers-adopted.json', {'answers': encounter.answers,
                                                            'template_review': encounter.template_review,
                                                            'status': encounter.status, 'revision': encounter.revision})
            fields, extra_record = {}, {**extra}
            if not findings:
                adopted = steps.field_outcomes(encounter.answers)
                reviewed, exported, export_findings, export_record = self.review_and_export(encounter, version, adopted,
                                                                                            original, evidence)
                findings += export_findings
                extra_record['export'] = export_record
                fields, more, details = judge(send, version, adopted, exported, original, raw=message,
                                              reviewed=reviewed, evidence=evidence)
                findings += more
                extra_record.update(details)
            return self.finish(send, attempt, evidence, outcome, findings, fields, extra_record)
        except BaseException as error:
            return self.interrupted(send, attempt, evidence, error)

    def review_and_export(self, encounter, version, adopted, original, evidence):
        """The review save with no clinical edit (the frozen steps), finalization, the authenticated export and its
        preservation (the frozen steps). Returns (the saved answers, the export, findings, the export record)."""
        findings = []
        page = self.world.client.get(f'/encounters/{encounter.pk}/')
        require(page.status_code == 200, f'The review page failed ({page.status_code}).')
        payload = steps.review_payload(version.fields, encounter.answers, steps.review_controls(page.content),
                                       encounter.revision, version.review_requirements)
        response = steps.save_review(self.world.client, encounter.pk, payload)
        encounter.refresh_from_db()
        reviewed = steps.field_outcomes(encounter.answers)
        pc.write_new(evidence / 'answers-reviewed.json', {'answers': encounter.answers, 'status': encounter.status,
                                                         'revision': encounter.revision, 'posted_keys': sorted(payload)})
        if response.status_code != 302:
            findings.append({'code': 'export_verification_failed', 'why': f'the review save was refused ({response.status_code})'})
            return reviewed, b'', findings, {'saved': False}
        response = steps.finalize(self.world.client, encounter.pk, encounter.revision)
        encounter.refresh_from_db()
        if response.status_code != 302 or encounter.status != 'finalized' or not encounter.export_sha256:
            findings.append({'code': 'export_verification_failed', 'why': 'finalization did not complete'})
            return reviewed, b'', findings, {'finalized': False}
        status, exported = steps.export(self.world.client, encounter.pk)
        pc.write_new(evidence / 'export.docx', exported, raw=True)
        record = {'status': status, 'sha256': hashlib.sha256(exported).hexdigest(), 'bytes': len(exported),
                  'finalized_export_sha256': encounter.export_sha256}
        if status != 200 or not exported or record['sha256'] != encounter.export_sha256:
            findings.append({'code': 'export_verification_failed', 'why': 'the authenticated export is not the finalized record'})
        else:
            # (the frozen check, on what the clinician SAVED: an edited answer must be in its field as edited)
            saved = {k: {**v, 'status': 'supported' if v.get('status') in ('supported', 'edited') and v.get('text')
                                        else v.get('status')} for k, v in reviewed.items()}
            verified = steps.export_verification(original, exported, version.fields, saved)
            record.update(verified)
            if not verified['workflow_success']:
                findings.append({'code': 'export_verification_failed',
                                 'why': 'the export does not preserve the form or an answer is outside its field'})
            # (and the stage's own read-back, which the frozen check is not: every field's mark or value as SAVED, and
            # nothing printed changed outside the written fields — refutation EXPORT-CHECK-DOES-NOT-READ)
            read_back = export_read_back(original, exported, version.fields, encounter.answers)
            record['read_back'] = read_back
            if not read_back['passed']:
                findings.append({'code': 'export_verification_failed',
                                 'why': 'the export read back does not show what was saved: '
                                        + '; '.join(f'{p["where"]}: {p["why"]}' for p in read_back['problems'][:6])})
        pc.write_new(evidence / 'export.json', record)
        return reviewed, exported, findings, record

    def interrupted(self, send, attempt, evidence, error):
        """After an attempt is written nothing escapes as 'refused': the attempt gets an outcome (unknown unless one was
        recorded), the stage fails, and nothing is re-sent. An ordinary exception returns to run_stage, whose decision
        (decide_stage) fails the stage WITH the sends it did not make, so a reopening can establish its remainder; only
        an interruption that ends the process fails the stage here, at once (refutation F2: failing it here for every
        error left a failure that recorded nothing unsent, and a reopened stage that could never send or fail again)."""
        sq._record_interruption(self.ledger, attempt, error, fail_stage=not isinstance(error, Exception))
        record = {'send': send.record(), 'attempt': attempt['number'], 'stops_stage': True, 'recorded_as': 'interrupted',
                  'findings': [{'code': 'uncertain_outcome', 'why': f'the runner failed after the attempt was written '
                                                                   f'({type(error).__name__}: {str(error)[:300]}); '
                                                                   'nothing is re-sent'}]}
        self.sends.append(record)
        if not isinstance(error, Exception):
            raise error
        return record, True


def raw_selection(message, fields, notes, path):
    """The model's own selection, from the provider's message, in the frozen replay's response shape: per field
    `unit_ids` and `conflict`; on the relations path also the printed option TEXTS and each non-answer, non-independent
    unit's relation (by quote). Nothing here is the adopted answer."""
    from django.core.exceptions import ValidationError
    from core import v3_field_relations as rel
    texts = [block.get('text') for block in (message or {}).get('content') or [] if block.get('type') == 'text']
    require(len(texts) == 1, 'The provider message does not carry exactly one text block.')
    asked, units = steps.source_units(notes, fields)
    selection = {}
    if path == 'field_relations':
        # The keyed answer, read by the engine's own strict parser (context back in the offered unit order): the same
        # per-field shape the frozen replay reads.
        try:
            parsed = rel.parse(texts[0], asked, units)
        except ValidationError as error:
            raise Refused('The relations answer cannot be read: ' + '; '.join(error.messages)) from None
        by_key = {f['key']: f for f in asked}
        for row in parsed.fields:
            chosen = {'unit_ids': list(row.unit_ids), 'conflict': bool(row.conflict)}
            options = {o['id']: o['text'] for o in rel.options(by_key[row.key])}
            chosen['options'] = [options[i] for i in row.option_ids if i in options]
            # Every UNSELECTED unit's relation but the replay's default ('independent'), 'answer' included: the frozen
            # replay rebuilds a selected unit as 'answer' and any other from `relations`, so an unselected answer it is
            # not given reads as an agreeing field the served path held (refutation of dfde4fc8, F3). A SELECTED unit's
            # own relation cannot reach the replay at all; `relation_disagreements` names those fields for the judge.
            chosen['relations'] = {u['quote']: c for u, c in zip(units, row.context)
                                   if u['id'] not in chosen['unit_ids'] and c != 'independent'}
            selection[row.key] = chosen
        return selection
    body = json.loads(texts[0])
    for row in body.get('fields') or []:
        selection[row.get('key')] = {'unit_ids': list(row.get('unit_ids') or []), 'conflict': bool(row.get('conflict'))}
    return selection


def relation_disagreements(message, fields, notes, path):
    """The fields whose OWN selection disagrees with their own relations in the model's keyed answer (the engine's one
    predicate, v3_field_relations.disagrees: a selected unit that is not answer/qualifier, or an answer unit left
    unselected), read from the provider's message with the engine's strict parser — never from the adopted answers.
    The served path holds such a field on its record; that hold is the MODEL's contradiction, which the frozen replay
    cannot always see (it rebuilds every selected unit as 'answer'). Nothing on the default path carries relations."""
    if path != 'field_relations':
        return set()
    from django.core.exceptions import ValidationError
    from core import v3_field_relations as rel
    texts = [block.get('text') for block in (message or {}).get('content') or [] if block.get('type') == 'text']
    require(len(texts) == 1, 'The provider message does not carry exactly one text block.')
    asked, units = steps.source_units(notes, fields)
    try:
        parsed = rel.parse(texts[0], asked, units)
    except ValidationError as error:
        raise Refused('The relations answer cannot be read: ' + '; '.join(error.messages)) from None
    return {row.key for row in parsed.fields if rel.disagrees(row, units)}


def clinician_view(page):
    """The mapping-assistance page's 'Areas requiring review', as the clinician sees them (location, text, reason)."""
    areas = []
    for match in re.finditer(r'<h3>Area (\d+) · ([^<]*)</h3><p>([^<]*)</p><p class="helptext">([^<]*)</p>', page):
        areas.append({'area': int(match.group(1)), 'location': htmlmod.unescape(match.group(2)),
                      'text': htmlmod.unescape(match.group(3)), 'reason': htmlmod.unescape(match.group(4))})
    return {'areas': areas, 'confirm_blocked_until_decided': bool(areas),
            'verdict_table': 'All source-area verdicts' in page}


# ── the stage ────────────────────────────────────────────────────────────────────────────────────────────────────

def seed_account(root):
    """The synthetic QA doctor, organization, patient and welcome credit (sonnet5_qa.seed_world's account, without the
    model_check form)."""
    return sq.seed_account(root)


def run_stage(campaign, stage, *, secret, provenance, database_prefix=sq.DATABASE_PREFIX, environ=None, rebuild=REBUILD,
              deadline=SEND_DEADLINE_SECONDS):
    """Every send of `stage`, in its fixed order, until the plan is done or a send stops it. Returns the stage result
    ({'verdict': 'PASS'|'FAIL', ...}); raises Refused when it stops before any attempt was written."""
    declaration, ledger, root = campaign.declaration, campaign.ledger, campaign.root
    ledger.acquire()
    settled = sq.settle_open_stages(campaign)
    checked = stage_preconditions(declaration, stage, root, database_prefix=database_prefix, rebuild=rebuild,
                                  environ=environ, ledger=ledger)
    inputs = frozen_inputs()
    planned = plan_sends(stage, inputs)
    campaign.admit(stage, Decimal('0.000001'), runner_commit=provenance.get('runner_commit'))   # (stage open at all)
    sends, remainder = pending_sends(campaign, stage, planned)
    amendment = amendment_in_force(campaign)
    forms = build_forms(root / 'forms' / stage, stage, inputs)
    world = seed_account(root)
    stale = sq.cancel_stale_jobs(world)
    run = Run(campaign, stage, secret=secret, provenance=provenance, inputs=inputs, forms=forms, world=world,
              checked=checked, deadline=deadline)
    # (the plan's own prices, before anything is created: a pricing version other than the declared one refuses here,
    # and each send is previewed against the limits on its planned maximum before its world is built)
    scratch = pc.private_directory(root / 'tmp' / f'plan-{stage}-{os.getpid()}-{len(ledger.rows())}')
    run.planned = {key: value['maximum_cost'] for key, value in price_sends(
        stage, sends, inputs, scratch, declaration, amendment=amendment,
        remaining=remaining_limits(campaign, stage)).items()}
    walk = frozen_walk_check(inputs) if stage == 'ordinary_notes' else None       # (refutation F2-FROZEN-WALK)
    reasons, not_sent = [], []
    for send in sends:
        if run.stopped:
            not_sent.append(send.id)
            continue
        try:
            done = run.run_send(send)
        except (StageStop, Refused) as stop:
            run.stopped = {'send': send.id, 'before_attempt': True, 'reason': str(stop)}
            reasons.append(f'{send.id}: stopped before its attempt was written (nothing sent): {stop}')
            not_sent.append(send.id)
            continue
        if done is None:
            continue
        record, stops = done
        if stops:
            run.stopped = {'send': send.id, 'attempt': record.get('attempt'), 'findings': record.get('findings')}
            reasons.append(f'{send.id}: ' + '; '.join(f['why'] for f in record.get('findings') or []))
    base = {'recovered_before_start': settled, 'stale_jobs_cancelled': stale}
    if remainder is not None:
        base['remainder'] = remainder
    if amendment is not None:
        base['amendment'] = amendment.record()
    if walk is not None:
        base['frozen_walk'] = walk
    return decide_stage(run, sends, reasons, not_sent, base)


def decide_stage(run, sends, reasons, not_sent, base):
    """passed ONLY when every planned send was made (or recorded as not exercised) and none stopped — in THIS run and in
    every earlier run of the stage (earlier_stops: a send that stopped the stage is never sent again, so a remainder
    that runs clean after one completes the evidence and is decided failed, naming it); failed otherwise, with the
    reasons and the sends not made. A final leak scan covers the decision's own inputs."""
    ledger, stage = run.ledger, run.stage
    attempts = [record.get('attempt') for record in run.sends if record.get('attempt')]
    earlier = earlier_stops(ledger, stage, attempts)
    summary = {'plan': [send.id for send in sends], 'sends': run.sends, 'not_sent': not_sent,
               'veto_evidence': run.veto_evidence, 'attempts': attempts, 'earlier_stops': earlier,
               'freeze_manifest_sha256': run.inputs['freeze']['manifest_sha256'], **base}
    if earlier:
        reasons = list(reasons) + ['the stage cannot pass: an earlier run of it did not end clean — ' + '; '.join(
            f'{e["send"]} (attempt {e["attempt"]}): {e["why"]}' for e in earlier) + '. A send is never made twice.']
    try:
        late = pc.leaked(run.root, run.secret, exclude=(run.declaration.credential_file,))
    except pc.Refused as refused:
        late = [str(refused)]
    if late:
        ledger.write_stop({'reason': 'the evidence could not be scanned, or carries the credential, at the decision',
                           'detail': late})
        reasons = list(reasons) + ['the final leak scan did not come back clean']
    if not attempts and not reasons:
        reasons = ['no send was made']
    if ledger.stage_state(stage)['state'] == 'open':
        if reasons:
            ledger.write_stage(stage, 'failed', {'reasons': reasons, 'summary': summary})
        else:
            ledger.write_stage(stage, 'passed', {'summary': summary})
    return {'stage': stage, 'verdict': 'FAIL' if reasons else 'PASS', 'reasons': reasons, 'summary': summary}


# ── plan (offline: no credential, no network, no database) ───────────────────────────────────────────────────────

def price_sends(stage, sends, inputs, state_dir, declaration, *, amendment=None, remaining=None):
    """Each send's maximum at the declared settings, computed with the application's own functions on the frozen forms
    (Django configured with the stage's settings; nothing is sent, no database is touched). Refuses a pricing version
    other than the declared one — or, for a send an amendment (verified: amendment_in_force) changes, other than the
    amended one. A notes send's maximum must equal its frozen bound, except an amended send's, which is recomputed by the
    same compiler: each amended bound, and their sum, must fit `remaining` ((stage, total) left: remaining_limits)."""
    from types import SimpleNamespace
    from django.test.utils import override_settings
    from core import generation, mapping_assistance
    from documents import service
    forms = build_forms(Path(state_dir) / 'forms', stage, inputs)
    originals = Path(state_dir) / 'files' / 'originals'
    originals.mkdir(parents=True, exist_ok=True)
    priced, fields_of = {}, {}
    for send in sends:
        with override_settings(MEDIA_ROOT=Path(state_dir) / 'files',
                               **(steps.PATH_FLAGS[send.path] if send.path in steps.PATH_FLAGS else {})):
            if send.kind == 'mapping' or send.path == 'mapping_encounter':
                path = originals / f'{send.form}.docx'
                path.write_bytes(forms[send.form])
                fields = fields_of.get(send.form) or service.inspect_template(str(path), engine='v3')['fields']
                fields_of[send.form] = fields
            else:
                fields = inputs['cases']['forms'][send.form]['fields']
            config = generation.configuration(fields if send.kind == 'generation' else None)
            expected = amendment.pricing_version if amended(amendment, send) else declaration.pricing_version(send.pricing_key)
            require(config['pricing_version'] == expected,
                    f'{send.id}: the application prices {config["pricing_version"]}, not the '
                    f'{"amended" if amended(amendment, send) else "declared"} {send.pricing_key}.')
            if send.kind == 'mapping':
                version = SimpleNamespace(template=SimpleNamespace(format='docx', sha256=hashlib.sha256(forms[send.form])
                                                                   .hexdigest(),
                                                                   original_path=f'originals/{send.form}.docx'),
                                          contract='v3', document_backend={}, fields=fields)
                maximum = Decimal(mapping_assistance.compile_request(version, config)['maximum_cost'])
                basis = 'compile_request on the deterministic fields'
            elif send.path == 'mapping_encounter':
                notes = (inputs['long_answer'] if send.form == 'f6a-long-answer'
                         else inputs['maps'][send.form]['source_note']['text'])
                maximum = generation.maximum_cost(notes, fields, config, context_labels=[], requirements=[])
                basis = ('maximum_cost with the deterministic fields (the confirmed proposal may differ; admission uses '
                         'the job\'s own maximum)')
            else:
                case = next(c for c in inputs['cases']['cases'] if c['id'] == send.case)
                maximum = generation.maximum_cost(case['notes'], fields, config, context_labels=[], requirements=[])
                if amended(amendment, send):
                    basis = ('maximum_cost with the frozen inspected fields under the contract-identity amendment '
                             '(recomputed; the frozen cost_bound_usd describes the replaced contract)')
                else:
                    frozen = case['cost_bound_usd'][send.path]['provider_cost_max']
                    require(Decimal(frozen) == maximum, f'{send.id}: the maximum {maximum} is not the frozen {frozen}.')
                    basis = 'maximum_cost with the frozen inspected fields (equals cases.json cost_bound_usd)'
        priced[send.id] = {'maximum_cost': maximum, 'bound': pc.attempt_bound(maximum),
                           'pricing_version': config['pricing_version'], 'basis': basis,
                           'amended': amended(amendment, send)}
    changed = [(send_id, row['bound']) for send_id, row in priced.items() if row['amended']]
    if changed:
        require(remaining is not None, 'Amended maxima are fitted to the limits left; none were given.')
        stage_left, total_left = remaining
        for send_id, bound in changed:
            require(bound <= stage_left and bound <= total_left,
                    f'{send_id}: the amended bound {bound} does not fit the {stage_left} left under the stage limit and '
                    f'the {total_left} left under the total.')
        worst = sum((bound for _, bound in changed), Decimal(0))
        require(worst <= stage_left and worst <= total_left,
                f'The amended sends\' bounds ({worst} together) do not fit the {stage_left} left under the stage limit and '
                f'the {total_left} left under the total.')
    return priced


def frozen_walk_check(inputs):
    """Refutation F2-FROZEN-WALK. The frozen N6 mocked walk (diagnostics/notes/app_path_walk.py, whose provider answers
    through app_path_steps.reference_answer) builds the relations answer in contract v1's shape; the freeze still
    verifies (the file is unchanged), so nothing said that this engine refuses that answer. Measured here on every
    relations case — the request compiled by this engine, the frozen builder's answer to it, this engine's parser — and
    stated in the notes plan and in every notes stage decision. Nothing is sent; no database. Needs Django configured."""
    from django.core.exceptions import ValidationError
    from django.test.utils import override_settings
    from core import generation, v3_field_relations as rel
    cases = {}
    try:
        for case in sorted(inputs['cases']['cases'], key=lambda c: c['id']):
            if 'field_relations' not in case['send_paths']:
                continue
            fields = inputs['cases']['forms'][case['form']]['fields']
            with override_settings(**steps.PATH_FLAGS['field_relations']):
                compiled = rel.compile_request(case['notes'], fields, generation.configuration(fields))
                payload = json.loads(compiled['wire']['messages'][0]['content'])
                body, _ = steps.reference_answer(case['notes'], fields, payload,
                                                 steps.reference_selection(case, 'field_relations'))
                try:
                    rel.parse(json.dumps(body), compiled['asked'], compiled['units'])
                    cases[case['id']] = 'accepted'
                except ValidationError as error:
                    cases[case['id']] = 'refused: ' + '; '.join(error.messages)
    except Exception as error:                              # (a statement that cannot be measured says so; never green)
        return {'walk': 'notes/app_path_walk.py (app_path_steps.reference_answer)', 'path': 'field_relations',
                'engine_contract': None, 'valid': None, 'cases': cases,
                'statement': f'not established ({type(error).__name__}: {str(error)[:200]})'}
    valid = bool(cases) and all(verdict == 'accepted' for verdict in cases.values())
    return {'walk': 'notes/app_path_walk.py (app_path_steps.reference_answer)', 'path': 'field_relations',
            'engine_contract': rel.CONTRACT, 'valid': valid, 'cases': cases,
            'statement': ('the frozen walk\'s field_relations answers are read by this engine' if valid else
                          f'the frozen walk\'s field_relations answers are refused by this engine ({rel.CONTRACT}): its '
                          'recorded field_relations results are not evidence for this contract, and a re-run of it '
                          'fails at the worker (only the field_relations path is measured here)')}


def plan_report(stage, declaration, root, state_dir, amendment=None):
    inputs = frozen_inputs()
    campaign = pc.Campaign(declaration, root, amendment=amendment)
    sends, remainder = pending_sends(campaign, stage, plan_sends(stage, inputs))     # (read-only: no lock, no write)
    amendment = amendment_in_force(campaign)
    priced = price_sends(stage, sends, inputs, state_dir, declaration, amendment=amendment,
                         remaining=remaining_limits(campaign, stage))
    rows = campaign.rows()                                  # (read-only: no lock is taken, nothing is written)
    limits = campaign.limits(rows)
    in_force = limits.stage(stage)
    spent, total = campaign.totals(stage)['exposure'], campaign.totals()['exposure']
    worst = sum((priced[s.id]['bound'] for s in sends), Decimal(0))
    earlier = earlier_stops(campaign.ledger, stage)
    return {'campaign': declaration.campaign, 'stage': stage,
            'declaration': {'commit': declaration.commit, 'sha256': declaration.sha256},
            'freeze_manifest_sha256': inputs['freeze']['manifest_sha256'],
            'frozen_walk': frozen_walk_check(inputs) if stage == 'ordinary_notes' else None,
            'settings': STAGE_FLAGS[stage], 'order': [
                # (is_declared: the DECLARATION's own version, never the amendment's — refutation F3-IS-DECLARED;
                # is_amended: the verified amendment's)
                {**s.record(), 'maximum_cost': format(priced[s.id]['maximum_cost'], 'f'),
                 'bound_x1_1': format(priced[s.id]['bound'], 'f'), 'pricing_version': priced[s.id]['pricing_version'],
                 'pricing_version_is_declared': priced[s.id]['pricing_version']
                 == declaration.pricing_version(s.pricing_key),
                 'pricing_version_is_amended': amended(amendment, s)
                 and priced[s.id]['pricing_version'] == amendment.pricing_version,
                 'amended': priced[s.id]['amended'], 'basis': priced[s.id]['basis']} for s in sends],
            'sends': len(sends), 'remainder': remainder,
            # (whatever the sends above do, the stage cannot pass while an earlier run's attempt stopped it or ended
            # unrecorded — refutation F1; the plan says so before anything is spent)
            'earlier_stops': earlier, 'can_pass': not earlier,
            'amendment': amendment.record() if amendment is not None else None,
            'stage_worst_case': format(worst, 'f'),
            'stage_limit': format(in_force.limit, 'f'), 'stage_exposure': format(spent, 'f'),
            'stage_remaining': format(in_force.limit - spent, 'f'),
            'total_limit': format(limits.total, 'f'), 'total_exposure': format(total, 'f'),
            'total_remaining': format(limits.total - total, 'f'),
            'worst_case_fits': worst <= in_force.limit - spent and worst <= limits.total - total,
            'stage_state': campaign.ledger.stage_state(stage)['state'],
            'requires': list(in_force.requires),
            'requires_met': all(campaign.ledger.stage_state(p)['state'] == 'passed' for p in in_force.requires),
            'credential_read': False, 'network': 'none', 'database': 'none'}


def plan(stage, root=None, declaration_path=None, amendment_path=None):
    """`plan --stage <id> [--amendment <path>]`: the sends the stage would make (its fixed order, or the remainder of
    its latest failure), each send's maximum and bound, and the stage worst case against the remaining stage and total
    limits in force (the live ledger, read-only). No credential, network or database."""
    require(stage in STAGES, f'No stage runner for {stage!r}.')
    require(not sq.env_file_present(), 'plan runs only in a checkout with no rebuild/.env.')
    declaration = pc.declared(sq.DECLARATION if declaration_path is None else declaration_path)
    require(amendment_path is None or stage == 'ordinary_notes', 'An amendment applies to the ordinary_notes stage only.')
    amendment = None if amendment_path is None else pc.declared_amendment(amendment_path, declaration)
    with tempfile.TemporaryDirectory(prefix='sonnet5-stage-plan-') as scratch:
        environ = {'QUILLMD_SECRET_KEY': 'plan-only-' + hashlib.sha256(os.urandom(16)).hexdigest(),
                   'QUILLMD_DB_PASSWORD': 'unused-by-plan', 'QUILLMD_DB_NAME': sq.DATABASE['name'],
                   'QUILLMD_DB_USER': sq.DATABASE['user'], 'QUILLMD_DB_HOST': '/nonexistent-plan-socket-dir',
                   'QUILLMD_DB_PORT': '1', 'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_STATE_DIR': scratch,
                   'QUILLMD_ADMIN_SITE': '0', **pc.declared_settings(declaration), **sq.PRICE_SETTINGS,
                   **STAGE_FLAGS[stage]}
        os.environ.update(environ)
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
        sys.path.insert(0, str(REBUILD))
        import django
        django.setup()
        from django.db.backends.base import base as dbbase

        def no_database(self, *args, **kwargs):
            raise AssertionError('plan never touches a database')
        dbbase.BaseDatabaseWrapper.ensure_connection = no_database
        report = plan_report(stage, declaration, sq.LIVE_ROOT if root is None else root, scratch, amendment)
    print(json.dumps(report, indent=1, default=str))
    return 0
