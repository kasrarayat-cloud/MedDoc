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
MANUAL_KINDS = ('text', 'long_text', 'date', 'time', 'choice', 'checkbox', 'signature', 'initials')
KIND_NAMES = {'text': 'Text', 'long_text': 'Long text', 'date': 'Date', 'time': 'Time', 'choice': 'One printed option',
              'multi_choice': 'Printed options (several)', 'checkbox': 'Checkbox', 'table_rows': 'Table rows',
              'signature': 'Signature', 'initials': 'Initials'}
#: Generation refuses more than 100 fields, so a v3 form above 100 answerable areas is refused at upload rather
#: than accepted and later unusable. Signature and initials areas are never generated and do not count.
GENERATION_FIELD_LIMIT = 100
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
    """Every field that can hold an answer: all but signature and initials areas."""
    return [f for f in fields or [] if f.get('kind') not in SIGNING_KINDS]


def too_many_fields(count):
    return (f'This form has {count} answer areas (signature and initials areas are not counted). QuillMD can generate '
            f'answers for at most {GENERATION_FIELD_LIMIT} per form today, so the form was not added and nothing was '
            f'dropped. Split it into parts of at most {GENERATION_FIELD_LIMIT} answer areas and upload each part.')


def label_of(field):
    return str(field.get('label') or field.get('key') or 'this question')


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


def printed_words(field):
    """The options the blank form itself shows chosen, as printed."""
    from documents.word_v3 import printed_options
    printed = printed_options(field)
    words = []
    for i in field.get('printed_ticked') or []:
        if isinstance(i, int) and 0 <= i < len(printed) and str(printed[i]) not in words:
            words.append(str(printed[i]))
    return words


def as_printed(field):
    verb = 'shown' if shows_words(field) else 'ticked'
    words = printed_words(field)
    if words:
        return 'the form keeps what it prints: ' + ', '.join(words) + ' ' + verb
    return 'the form keeps what it prints, with no option ' + verb


def review_note(field):
    """Under the input on the review page."""
    kind = field.get('kind')
    if kind == 'checkbox':
        return ('Ticked here, the box is exported ticked; left unticked, it is exported unticked'
                + (', although the blank form prints it ticked' if field.get('printed_ticked') else '') + '.')
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
    if field.get('kind') in ('choice', 'multi_choice') and field.get('printed_ticked'):
        return 'the exported ' + as_printed(field)[len('the '):]
    return ''


def finalized_note(field, answer):
    """What the finalized page states the export holds, when the answer text alone does not say it."""
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
