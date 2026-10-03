"""Contract v3 Word mappings on the clinical side: mapping review, the text form of every answer kind, and the
answers handed to the engine at export.

ANSWERS STAY TEXT. `Encounter.answers[key]['text']` holds one unambiguous text form per kind, so every existing
review rule (evidence, held candidates, "Leave blank — reviewed", attribution, audit) keeps working unchanged:

    text, long_text, date, time   the answer as typed (dates and times are not reformatted)
    choice                        exactly one printed option label
    multi_choice                  one printed option label per line
    checkbox                      'checked' for a ticked box; empty for a box left unticked
    table_rows                    one table row per line, cells separated by ' | ' (a cell cannot contain '|')
    signature, initials           always empty: signed by hand on the printed form, never filled

`normalize` is the ONE reader of these forms: saving, finalizing and export all go through it, so a value the
review page accepts is exactly a value the export can write.
"""
from django.core.exceptions import ValidationError

CONTRACT = 'v3'
TEXT_KINDS = ('text', 'long_text', 'date', 'time')
OPTION_KINDS = ('choice', 'multi_choice', 'checkbox')
SIGNING_KINDS = ('signature', 'initials')
#: Never generated from notes: the clinician enters table rows; signature and initials are signed by hand.
NEVER_GENERATED = ('table_rows',) + SIGNING_KINDS
#: What a clinician may add by hand (the engine's manual kinds).
MANUAL_KINDS = ('text', 'long_text', 'date', 'time', 'choice', 'multi_choice', 'checkbox', 'signature', 'initials')
KIND_NAMES = {'text': 'Text', 'long_text': 'Long text', 'date': 'Date', 'time': 'Time', 'choice': 'One printed option',
              'multi_choice': 'Printed options (several)', 'checkbox': 'Checkbox', 'table_rows': 'Table rows',
              'signature': 'Signature', 'initials': 'Initials'}
#: Generation refuses more than 100 fields, so a v3 form above 100 answerable areas is refused at upload rather
#: than accepted and later unusable. Signature and initials areas are never generated and do not count.
GENERATION_FIELD_LIMIT = 100

def field_limit():
    from .generation_batch import enabled, MAX_PARTS, relations_parts, require_config
    if enabled():return GENERATION_FIELD_LIMIT * MAX_PARTS
    # The qualified ordinary contract already has bounded complete-form parts;
    # import must not require a separate generic-batch grant to reach that route.
    from .generation import configuration
    try:
        config=configuration()
        if relations_parts(config):
            require_config(config)
            return GENERATION_FIELD_LIMIT * MAX_PARTS
    except ValidationError:
        pass
    return GENERATION_FIELD_LIMIT
CHECKED = 'checked'
#: The only source values that tick a checkbox automatically.
CHECKBOX_YES = frozenset(('yes', 'checked', 'present'))
MAX_TABLE_ROWS = 200


def is_v3_version(version):
    return getattr(version, 'contract', '') == CONTRACT


def is_v3_fields(fields):
    return bool(fields) and all(isinstance(f, dict) and (f.get('locator') or {}).get('contract') == CONTRACT
                                for f in fields)


def answerable(fields):
    """Fields that can hold an answer, excluding signatures, initials and protected signing details."""
    return [f for f in fields or [] if f.get('kind') not in SIGNING_KINDS and not f.get('write_protected')]


def export_refusal(template):
    """The encounter page's explanation, from the STORED inspection notes only (no sandbox run on a page view): the
    floating initials refusal, as on the base.

    ⚠️ IT DOES NOT EXPLAIN THE LAYOUT VERIFIER, DELIBERATELY. A stored layout note says the inspection counted a
    tab-column candidate, not that fill will refuse: fill's reader (word_v3.Detector in proposal mode) withdraws a
    candidate whose complete question or section passes the mapping limit, and that form exports with no verifier
    (refutation FV:F1: a 989-character row label under a side heading; two identical tables with 850-character titles).
    Read from the note, the page told those forms that no answer could be exported, on a page whose export had just
    succeeded. Only fill's own question separates the two, and it is asked at admission (admission_refusals), whose
    refusal says why."""
    from documents.word_v3 import FLOATING_INITIALS_REFUSAL
    return FLOATING_INITIALS_REFUSAL if FLOATING_INITIALS_REFUSAL in template.warnings else ''



GENERATION_EXPORT_REFUSAL = ("Generation is unavailable for this form's floating initials layout. "
                             "Nothing was sent or charged; the unchanged form and mapping remain available.")
GENERATION_SOURCE_REFUSAL = ("The original form could not be verified for generation. Nothing was sent or charged. "
                            "Ask an administrator to check the original before trying again.")
#: ⚠️ D10 (V1 B-W1): without the isolated layout verifier a form with a tab-column answer was generated — quoted, held,
#: sent, charged — and refused only at finalization, because word_v3.fill refuses EVERY non-empty answer on such a form
#: until the verifier has verified it. Predictable from the original, so a NEW request is refused at admission
#: (admission_refusals, core.jobs.enqueue), before all of that, and only when fill itself refuses (export_needs_verifier).
#: Never raised after admission (see admission_refusals). Worded for both ways the verifier fails it: absent or
#: unreachable, or answering that it cannot establish the form's tab-column answer places.
GENERATION_LAYOUT_REFUSAL = ("Generation is unavailable: no answer on this form can be exported until the isolated "
                             "layout verifier has verified its tab-column answers. Nothing was sent or charged.")
#: The refusals of the export path that mean "the layout verifier did not verify this export" (documents.layout_transport
#: verify_document): not configured, unreachable or incomplete ('layout_unavailable'), or answered 'not verified'
#: ('layout_unresolved'). Any other refusal of the admission probe is not a layout answer (see export_needs_verifier).
LAYOUT_REFUSAL_CODES = ('layout_unavailable', 'layout_unresolved')
#: The probe's one answer, under a key no field of the mapping has (export_needs_verifier).
LAYOUT_PROBE_KEY = 'quillmd-layout-admission-probe'


def generation_refusal(version):
    """Before quoting/holding/sending: today's source-bound export restriction also applies to old v3 jobs.

    Stored warnings can refuse early, but their absence never authorizes generation. Inspect the original again
    in the existing document sandbox and bind its digest to the selected version's template. Never rewrite old
    mappings, warnings, jobs or receipts. Voice transcription does not depend on filled-form export.

    ⚠️ SHARED BY ADMISSION AND BY EVERY LATER CHECK OF A RUNNING REQUEST: the page, enqueue, the worker before its send,
    the complete-form batch before EVERY part (after earlier parts were sent and settled) and once more at adoption
    (core.batch_jobs.current_plan / finish). A refusal here after a send discards output already paid for, so it holds
    only what the ORIGINAL says (source identity, floating initials). The layout verifier's answer is not the
    original's: it is refused at admission only (admission_refusals). Refutation L1:F1 measured the other placement — an
    outage before the second part or at adoption failed a two-part batch whose parts were settled, and absorbed them.
    """
    return _source_refusal(version)[0]


def admission_refusals(version):
    """(refusal, layout_refusal) for a NEW generation request: core.jobs.enqueue only.

    `refusal` is generation_refusal's answer, from one fresh inspection. `layout_refusal` is fill's OWN answer, asked
    whenever that inspection counted a tab-column candidate (counted_tab_column): export_needs_verifier runs the real
    export path on the original with one non-empty answer, and refuses only if fill then refuses for want of the
    verifier. The inspection's count is not that answer — fill's reader can withdraw what it counted, and those forms
    export with no verifier (refutation FV:F1) — so it only decides whether to ask. The stored upload note is never read
    here: a verifier configured since is honoured and one lost since is caught.

    ⚠️ THE CALLER RAISES `layout_refusal` ONLY FOR A REQUEST THAT WOULD TAKE A NEW HOLD — after its own replay answers
    (an admitted request re-posted from a stale page stays that request) and never after admission. Once admitted the
    request runs as before: a verifier lost later costs the true cost and keeps the draft, and export asks the verifier
    itself (word_v3.fill), so the draft can be exported when it answers again.
    """
    # Legacy also needs import coverage/processor verification before any job
    # or reservation; its source-role path otherwise returns before this gate.
    from .import_binding import verify
    verify(version)
    from . import destination_roles
    if (not is_v3_version(version) and destination_roles.applies(version)
            and version.template.format == 'docx'):
        destination_roles.report(version)
    refusal, inspection = _source_refusal(version)
    if refusal or not counted_tab_column(inspection):
        return refusal, ''
    return '', export_needs_verifier(version)


def counted_tab_column(inspection):
    """Whether a fresh inspection counted a tab-column candidate: when it did, admission asks fill (export_needs_verifier).

    documents.service says so in one of two ways. Not verified now (no verifier, unreachable, or 'not verified'): the
    inspection keeps `layout_pending`. VERIFIED now: the response is replaced by the verifier's own, `layout_pending` is
    dropped and its `layout_receipt` is the only sign left.

    ⚠️ A VERIFIED INSPECTION IS NOT A VERIFIED EXPORT (refutation L1:RF1:F1). The verifier verifies an export against the
    STORED mapping and its field receipts, and refuses every export of a mapping whose tab-column question was renamed
    ('A tab-column mapping changed; verify its complete source again.') or whose receipts name an earlier renderer
    profile ('Missing, changed or stale source/profile receipt') — while it still verifies the inspection of the same
    original. Read from `layout_pending` alone, both were admitted, held, sent and charged, then refused at
    finalization. So a verified inspection asks fill too; a verifier that verifies the export admits the request."""
    return bool(inspection.get('layout_pending')) or 'layout_receipt' in inspection


def export_needs_verifier(version):
    """GENERATION_LAYOUT_REFUSAL when the export of this version refuses a non-empty answer set for want of the layout
    verifier; '' when it does not.

    ⚠️ THE SAME PREDICATE AS EXPORT, BECAUSE IT IS EXPORT: documents.fill_template — the finalization path — on the
    stored mapping, in the sandbox, with ONE non-empty answer under a key no field has, and no output written.
    word_v3.fill's gate reads only the original (its proposal-mode tab-column candidates) and whether ANY answer is
    non-empty, so this answer stands for every non-empty answer set; the unknown key writes nothing. When the gate fires,
    documents.service asks the verifier exactly as finalization would, and only its refusal (LAYOUT_REFUSAL_CODES)
    refuses here: a verifier that verifies the export admits the request.

    Fails closed: any other refusal of the probe, or a mapping the probe cannot be run on (not a contract v3 mapping),
    means fill's answer is unknown, and the request is refused as an unverifiable original (GENERATION_SOURCE_REFUSAL),
    never admitted on a guess."""
    from documents import DocumentError, fill_template
    from .security import private_path
    fields = version.fields
    if not is_v3_fields(fields):
        return GENERATION_SOURCE_REFUSAL
    key = LAYOUT_PROBE_KEY
    while key in {f.get('key') for f in fields}:
        key += '-'
    try:
        fill_template(private_path(version.template.original_path), fields, {key: 'x'}, None)
    except DocumentError as exc:
        return GENERATION_LAYOUT_REFUSAL if exc.code in LAYOUT_REFUSAL_CODES else GENERATION_SOURCE_REFUSAL
    except (OSError, ValueError, ValidationError):
        return GENERATION_SOURCE_REFUSAL
    return ''


def _source_refusal(version):
    """(refusal, fresh inspection) — what the ORIGINAL says, from one inspection in the sandbox."""
    from documents import DocumentError, inspect_template
    from . import destination_roles
    if not is_v3_version(version):
        return '', {}
    if export_refusal(version.template):
        return GENERATION_EXPORT_REFUSAL, {}
    from documents.word_v3 import FLOATING_INITIALS_REFUSAL
    from .security import private_path
    try:
        result = inspect_template(private_path(version.template.original_path), engine=CONTRACT)
        destination_roles.report(version)
    except (DocumentError, OSError, ValueError, ValidationError):
        return GENERATION_SOURCE_REFUSAL, {}
    if result.get('sha256') != version.template.sha256 or result.get('contract') != CONTRACT:
        return GENERATION_SOURCE_REFUSAL, {}
    if FLOATING_INITIALS_REFUSAL in result.get('warnings', []):
        return GENERATION_EXPORT_REFUSAL, {}
    return '', result


def too_many_fields(count):
    if field_limit()!=GENERATION_FIELD_LIMIT:
        return (f'This form has {count} answer areas and exceeds the bounded {field_limit()}-area limit. '
                'The form was not added; no answer area was dropped.')
    return (f'This form has {count} answer areas (signature and initials areas are not counted). QuillMD can generate '
            f'answers for at most {GENERATION_FIELD_LIMIT} per form today, so the form was not added and nothing was '
            f'dropped. Split it into parts of at most {GENERATION_FIELD_LIMIT} answer areas and upload each part.')


def label_of(field):
    return str(field.get('label') or field.get('key') or 'this question')


def question_parts(field):
    """Printed question segments for review, never inferred coverage or new destinations."""
    if field.get('kind') not in ('text', 'long_text'):
        return []
    label = str(field.get('label') or '')
    parts, start = [], 0
    for index, char in enumerate(label):
        if char not in '?？':
            continue
        end = index + 1
        while end < len(label) and label[end] in ')）]\"\'”’':
            end += 1
        part = label[start:end]
        if any(character.isalnum() for character in part):
            parts.append(part)
            start = end
    if len(parts) < 2:
        return []
    # Preserve trailing instructions, punctuation and all original wording.
    parts[-1] += label[start:]
    return parts


def option_for(options, text):
    """The one printed option `text` names: equal after trimming, ignoring case. None when it names no option, or
    when two printed options would both match (then the text does not identify one).

    Case only: `lower()`, not Unicode case folding, so 'MASS' does not name 'Maß' and a long s does not name an s.
    Generation fills an option only through this comparison, so the narrower reading is the conservative one.

    ⚠️ ONE READER: this is the engine's own `option_position`, so the option the review accepts is the option the
    export ticks (they disagreed: the engine compared list-marker-stripped labels and took the first hit)."""
    from documents.word_v3 import option_position
    position = option_position(options, text)
    return None if position is None else list(options)[position]


def columns(field):
    """The table's column headers, in the order the cells of a row are written."""
    target = (field.get('locator') or {}).get('target') or {}
    count = len(target.get('columns') or []) or len(field.get('options') or [])
    headers = [str(h or '').strip() for h in (field.get('options') or [])][:count]
    return headers + [f'Column {n}' for n in range(len(headers) + 1, count + 1)]


def _shown(text, limit=60):
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def table_rows(field, text):
    """One row per line, cells separated by '|'; each row padded to the table's columns."""
    heads = columns(field)
    lines = str(text or '').split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    if len(lines) > MAX_TABLE_ROWS:
        raise ValidationError(f'"{label_of(field)}" takes at most {MAX_TABLE_ROWS} table rows; this answer has {len(lines)}.')
    rows = []
    for number, line in enumerate(lines, 1):
        cells = [cell.strip() for cell in line.split('|')]
        if len(cells) > len(heads):
            raise ValidationError(
                f'"{label_of(field)}", row {number}: {len(cells)} cells, but the table has {len(heads)} columns '
                f'({" | ".join(heads)}). Separate cells with " | "; a cell cannot contain "|".')
        rows.append(cells + [''] * (len(heads) - len(cells)))
    return rows


def normalize(field, text):
    """The stored text form of an answer for this field, or ValidationError naming the question.

    Canonical: a choice becomes its printed option label, multi_choice becomes option labels in printed order."""
    kind = field.get('kind')
    label = label_of(field)
    text = str(text or '')
    if not text.strip():
        return ''
    if field.get('write_protected'):
        raise ValidationError(f'"{label}" is a protected signing area. It remains unchanged; review the original and complete it by hand.')
    if kind in SIGNING_KINDS:
        raise ValidationError(f'"{label}" is signed by hand on the printed form; QuillMD never fills it.')
    options = [str(option) for option in field.get('options') or []]
    if kind == 'choice':
        option = option_for(options, text) if '\n' not in text.strip() else None
        if option is None:
            raise ValidationError(f'"{label}": "{_shown(text)}" is not one of the printed options '
                                  f'({", ".join(options) or "none recorded"}). Choose one of them or leave it unanswered.')
        text = option
    elif kind == 'multi_choice':
        chosen = []
        for line in text.split('\n'):
            if not line.strip():
                continue
            option = option_for(options, line)
            if option is None:
                raise ValidationError(f'"{label}": "{_shown(line)}" is not one of the printed options '
                                      f'({", ".join(options) or "none recorded"}).')
            chosen.append(option)
        text = '\n'.join(option for option in options if option in chosen)
    elif kind == 'checkbox':
        if text.strip() != CHECKED:
            raise ValidationError(f'"{label}" is a checkbox: its answer is "{CHECKED}" or empty.')
        text = CHECKED
    elif kind == 'table_rows':
        table_rows(field, text)
    elif kind not in TEXT_KINDS:
        raise ValidationError(f'"{label}" has a kind QuillMD cannot fill ({kind}).')
    limit = field.get('max_chars')
    # The engine bounds every text answer it writes as a string (text kinds and a choice's label).
    if limit and kind in TEXT_KINDS + ('choice',) and len(text) > int(limit):
        raise ValidationError(f'"{label}": that space on the form shows at most {int(limit)} characters; this answer '
                              f'has {len(text)}. Shorten it; nothing was cut.')
    return text


def fill_answers(fields, answers):
    """Reviewed text forms -> the engine's fill answers. Every value is re-read by `normalize` first.

    ⚠️ A checkbox the clinician reviewed and left unticked is sent as False, so the export unticks it even when the
    blank form printed it ticked (the engine sets every box of an answered field). An unanswered choice is not sent:
    the form keeps what it prints, and the page says what that is."""
    out = {}
    for field in fields:
        record = answers.get(field['key']) or {}
        text = normalize(field, record.get('text', ''))
        if field.get('write_protected'):
            # Empty review preserves a human-owned control's printed state.
            # normalize above still refuses any proposed text or tick.
            continue
        kind = field.get('kind')
        if kind == 'checkbox':
            if text:
                out[field['key']] = True
            elif record.get('reviewed') is True or record.get('status') == 'left_blank':
                out[field['key']] = False
            continue
        if not text:
            continue
        if kind == 'multi_choice':
            out[field['key']] = text.split('\n')
        elif kind == 'table_rows':
            out[field['key']] = table_rows(field, text)
        else:
            out[field['key']] = text
    return out


# ─── what the export does with an option field, in the words the pages show ───────────────────────────────────────
#: ⚠️ THE PAGES STATE EXACTLY WHAT THE EXPORT DOES (refutation F3): an answered option field has every box set - the
#: chosen ticked, every other unticked; a reviewed checkbox left unticked is exported unticked; an unanswered choice
#: keeps what the blank form prints, and the blank form's printed ticks (`printed_ticked`) are named.

def shows_words(field):
    """A dropdown or an option-text cell: the chosen option is written, not ticked."""
    target = (field.get('locator') or {}).get('target') or {}
    return target.get('type') in ('sdt_choice', 'ff_dropdown') or target.get('write') == 'option_text'


def printed_words(field, key='printed_ticked'):
    """The options the blank form itself shows chosen (or, with key='printed_unread', whose printed state QuillMD
    cannot read), as printed."""
    from documents.word_v3 import printed_options
    printed = printed_options(field)
    words = []
    for i in field.get(key) or []:
        if isinstance(i, int) and 0 <= i < len(printed) and str(printed[i]) not in words:
            words.append(str(printed[i]))
    return words


def as_printed(field):
    verb = 'shown' if shows_words(field) else 'ticked'
    words = printed_words(field)
    unread = printed_words(field, 'printed_unread')
    if unread:
        # ⚠️ Never "with no option ticked" about a box the reader could not read.
        return ('the form keeps what it prints' + (': ' + ', '.join(words) + ' ' + verb if words else '')
                + '; QuillMD cannot read whether ' + ', '.join(unread) + (' is ' if len(unread) == 1 else ' are ')
                + verb + ' on the blank form')
    if words:
        return 'the form keeps what it prints: ' + ', '.join(words) + ' ' + verb
    return 'the form keeps what it prints, with no option ' + verb


def review_note(field):
    """Under the input on the review page."""
    if field.get('write_protected'):
        return field.get('review_reason') or 'Protected signing area; left unchanged.'
    kind = field.get('kind')
    if kind == 'checkbox':
        return ('Ticked here, the box is exported ticked; left unticked, it is exported unticked'
                + (', although the blank form prints it ticked' if field.get('printed_ticked') else '')
                + ('. QuillMD cannot read whether the blank form prints this box ticked' if field.get('printed_unread') else '')
                + '.')
    if kind in ('choice', 'multi_choice'):
        if shows_words(field):
            first = 'The chosen option is written in its place on the form'
        elif kind == 'choice':
            first = 'The chosen option is ticked and every other printed option is left unticked'
        else:
            first = 'Each chosen option is ticked and every other printed option is left unticked'
        return first + '. With no option chosen, ' + as_printed(field) + '.'
    return ''


def blank_note(field):
    """What "Leave blank - reviewed" exports, when that is not an empty answer area."""
    if field.get('kind') in ('choice', 'multi_choice') and (field.get('printed_ticked') or field.get('printed_unread')):
        return 'the exported ' + as_printed(field)[len('the '):]
    return ''


def finalized_note(field, answer):
    """What the finalized page states the export holds, when the answer text alone does not say it."""
    if field.get('write_protected'):
        return field.get('review_reason') or 'Protected signing area; left unchanged.'
    kind = field.get('kind')
    if kind == 'checkbox':
        return 'Box exported ticked.' if (answer.get('text') or '').strip() else 'Box exported unticked.'
    if kind in ('choice', 'multi_choice') and not (answer.get('text') or '').strip():
        return 'No option chosen; ' + as_printed(field) + '.'
    return ''


def input_for(field):
    """How the review page asks for this answer."""
    kind = field.get('kind')
    return {'choice': 'select', 'multi_choice': 'options', 'checkbox': 'checkbox', 'table_rows': 'table',
            'signature': 'signed', 'initials': 'signed'}.get(kind, 'text')


# ─── mapping review: places ─────────────────────────────────────────────────────────────────────────────────────

def _slot(part, path):
    return f'{part}#{path}'


def mapped_slots(fields):
    """Every place a field of this mapping already writes to or reads its anchor from."""
    found = set()
    for field in fields or []:
        locator = field.get('locator') or {}
        part = locator.get('part', '')
        target = locator.get('target') or {}
        if locator.get('slot'):
            found.add(_slot(part, locator['slot']))
        for extra in list(locator.get('extra') or []) + list(target.get('copies') or []) + list(target.get('boxes') or []):
            if extra.get('slot'):
                found.add(_slot(extra.get('part', part), extra['slot']))
        for path in target.get('paragraphs') or []:
            found.add(_slot(part, path))
        if target.get('type') == 'table_rows' and target.get('table'):
            for row in target.get('rows') or []:
                found.add(_slot(part, f"{target['table']}/tr[{row}]"))
    return found


def is_mapped(slot, mapped):
    """A place is taken when it is mapped, lies inside a mapped place, or holds one."""
    return slot in mapped or any(slot.startswith(m + '/') or m.startswith(slot + '/') for m in mapped)


PLACE_KINDS = {'p': 'Paragraph', 'tc': 'Table cell', 'sdt': 'Content control', 'ff': 'Legacy form field',
               'glyphs': 'Printed box'}


def open_places(outline_rows, fields, query=''):
    """Outline places not yet mapped, in document order, filtered by preview or context."""
    mapped = mapped_slots(fields)
    wanted = ' '.join(str(query or '').split()).casefold()
    rows = []
    for row in outline_rows or []:
        if is_mapped(row['slot'], mapped):
            continue
        if wanted and wanted not in ' '.join((row.get('preview') or '', row.get('context') or '')).casefold():
            continue
        rows.append({**row, 'kind_name': PLACE_KINDS.get(row.get('kind'), row.get('kind', ''))})
    return rows


def missing_boxes(fields, outline_rows):
    """Reject every unaddressable box reference before confirmation, including controls and legacy fields.
    Cell writers address a whole cell (possibly blank), so they require an addressable cell rather than a glyph."""
    from documents.word_v3 import box_key
    shown = {key for row in outline_rows or [] for key in row.get('box_keys') or [] if key}
    cells = {row['slot'] for row in outline_rows or []
             if row.get('kind') == 'tc' and not row.get('unnumbered_boxes')}
    found = []
    for field in fields or []:
        target = (field.get('locator') or {}).get('target') or {}
        for box in target.get('boxes') or []:
            kind = box.get('kind')
            valid = (box_key(box) in shown if kind in ('glyph', 'sdt', 'ff') else
                     _slot(box.get('part', ''), box.get('slot', '')) in cells if kind in ('cell', 'cell_text') else False)
            if not valid:
                found.append(label_of(field))
                break
    return found


def checkboxes_off_box(fields):
    """Labels of checkbox fields whose place is not a box (a checkbox on a text answer area, as manual mapping once
    stored): every export of them is refused, so the mapping is never confirmed."""
    return [label_of(field) for field in fields or [] if field.get('kind') == 'checkbox'
            and ((field.get('locator') or {}).get('target') or {}).get('type') != 'checkboxes']


def insert_in_document_order(fields, added, outline_rows):
    """`fields` with `added` placed before the first field that comes later in the document. Existing fields keep
    their order; a field whose place the outline does not list keeps its position."""
    position = {row['slot']: n for n, row in enumerate(outline_rows or [])}

    def where(field):
        locator = field.get('locator') or {}
        slot = _slot(locator.get('part', ''), locator.get('slot', ''))
        if slot in position:
            return position[slot]
        parent = slot.rsplit('/', 1)[0]
        return position.get(parent)

    result = list(fields)
    for field in added:
        at = where(field)
        index = len(result)
        if at is not None:
            index = next((n for n, existing in enumerate(result) if (w := where(existing)) is not None and w > at),
                         len(result))
        result.insert(index, field)
    return result
