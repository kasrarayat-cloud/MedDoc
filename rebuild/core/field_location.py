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


def describe(field):
    """One short phrase locating this field's answer area in the original form."""
    locator = field.get('locator') or {}

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
