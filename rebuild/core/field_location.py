"""Where an answer goes, in words a doctor can check against their own form.

DISPLAY ONLY, and deliberately so. `documents.engine.validate_mapping` compares the stored
field list against a fresh inspection with `fields != mapping (⚠️ SUPERSEDED: `validate_mapping` now compares STRUCTURE — key, kind, locator and the rest — and excludes only `label`, which the mapping-review rename gate owns instead.)`, so adding a key to the field
dict would invalidate every mapping version already saved. Nothing here is persisted or sent
to the adapter; it is derived from the locator each time a review screen is rendered.

The mapping-review table previously rendered `{% firstof field.location field.kind %}` and no
code ever set `location`, so its "Location" column showed the literal word "text" on every
row — on the one screen whose purpose is confirming where each answer belongs.
"""

PART_NAMES = {
    'word/document.xml': 'Body',
    'word/header1.xml': 'Header',
    'word/header2.xml': 'Header (continuation pages)',
    'word/header3.xml': 'Header (first page)',
    'word/footer1.xml': 'Footer',
    'word/footer2.xml': 'Footer (continuation pages)',
    'word/footer3.xml': 'Footer (first page)',
}


def part_name(part):
    """A package part named for a doctor, falling back to something still recognisable."""
    if part in PART_NAMES:
        return PART_NAMES[part]
    name = str(part).rsplit('/', 1)[-1].removesuffix('.xml')
    if name.startswith('header'):
        return 'Header ' + name.removeprefix('header')
    if name.startswith('footer'):
        return 'Footer ' + name.removeprefix('footer')
    return name or 'Body'


V3_TARGETS = {
    'cell': 'empty answer cell in a table', 'cell_replace': 'answer cell in a table', 'paragraph': 'empty line',
    'sdt_text': 'Word content control', 'sdt_choice': 'Word dropdown', 'ff_text': 'legacy Word form field',
    'ff_dropdown': 'legacy Word dropdown field', 'checkboxes': 'printed boxes', 'paragraph_options': 'printed options',
    'text_options': 'printed options', 'table_rows': 'rows of a table',
}


def describe_v3(locator, box_keys=None):
    """Contract v3: the part (body, header, footer) and the kind of place the answer is written to. A single box on a
    place of boxes says which one: 'printed box 2 of 3', counted among EVERY box the place's preview shows (its
    `box_keys` in the form's outline: printed glyph boxes and checkbox controls alike), exactly as the clinician's box
    number counts. Without the place's boxes it names no number."""
    target = locator.get('target') or {}
    kind = target.get('type', '')
    if kind == 'span':
        what = 'after the printed label' if target.get('shape') == 'after_label' else 'on the printed blank'
    else:
        what = V3_TARGETS.get(kind, 'answer area')
    boxes = target.get('boxes') or []
    if kind == 'checkboxes' and len(boxes) == 1:
        from documents.word_v3 import box_key
        what = 'printed box'
        keys = (box_keys or {}).get('%s#%s' % (locator.get('part', ''), locator.get('slot', '')))
        keys = keys if isinstance(keys, list) else []
        if box_key(boxes[0]) in keys:
            what = 'printed box %d of %d' % (keys.index(box_key(boxes[0])) + 1, len(keys))
    where = part_name(locator.get('part', 'word/document.xml'))
    copies = len(target.get('copies') or [])
    return f'{where} · {what}' + (f' (and {copies} repeated copy/copies)' if copies else '')


def describe(field, box_keys=None):
    """One short phrase locating this field's answer area in the original form."""
    locator = field.get('locator') or {}

    if locator.get('contract') == 'v3':
        return describe_v3(locator, box_keys)

    if 'cell' in locator:
        return 'Answer cell in a question/answer table'

    if 'paragraph' in locator:
        token = (locator.get('token') or '').strip()
        where = f"Paragraph {locator['paragraph'] + 1}"
        return f'{where} · {token}' if token else where

    tab = locator.get('tab_form')
    if tab:
        anchors = tab.get('anchors') or []
        if not anchors:
            return 'Underlined answer area'
        first = anchors[0]
        where = f"{part_name(first.get('part'))} paragraph {first.get('paragraph', 0) + 1}"
        if len(anchors) > 1:
            # A logical question can own several physical blanks; say so rather than
            # showing only the first and letting the count look like a mismatch.
            where += f' and {len(anchors) - 1} more line(s)'
        if tab.get('grouping') == 'heading':
            where += ' · under its section heading'
        return 'Underlined blank · ' + where

    return 'Original form field'


def rows(fields):
    """Fields paired with their described location, for a review table or editor.

    `duplicate` marks a row whose question label is shared with another row. Two answers that
    read as the same question cannot be told apart, and the top-of-page inspection note says
    so — this points at the specific rows to rename. Display only, like everything here.
    """
    fields = fields or []
    counts = {}
    for field in fields:
        label = (field.get('label') or '').strip()
        counts[label] = counts.get(label, 0) + 1
    return [{'field': field,
             'location': describe(field),
             'duplicate': counts.get((field.get('label') or '').strip(), 0) > 1}
            for field in fields]
