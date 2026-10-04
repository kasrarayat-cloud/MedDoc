"""Version 1 adapter for explicit underlined-tab answer regions.

Only used when the earlier placeholder/table contract recognizes no fields, so
existing immutable mappings keep their original interpretation. All coordinates
refer to the unmodified package, never to the growing export.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
from pathlib import Path
import re
from zipfile import ZipFile

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


VERSION = 1
WARNINGS = [
    "Underlined answer areas were detected. Review each label and section before approving the mapping.",
    "Consecutive blank lines under a heading share one answer. Confirm that grouping during mapping review.",
    "Answers expand in their original regions and may change pagination. Long paired answers continue on separate lines. Review every exported page.",
    "Preprinted page labels are preserved; they may not reflect the page count after answers expand.",
]


def _answer_tab(run):
    underline = run.find('./' + qn('w:rPr') + '/' + qn('w:u'))
    children = [child for child in run if child.tag != qn('w:rPr')]
    return (underline is not None and underline.get(qn('w:val'), 'single') == 'single'
            and len(children) == 1 and children[0].tag == qn('w:tab'))


def _text(runs):
    return ''.join(text.text or '' for run in runs for text in run.iter(qn('w:t'))).strip()


def _heading(paragraph):
    """Require an actual heading style/outline level, not capitalization."""
    if not paragraph.text.strip():
        return False
    level = paragraph._p.find('./' + qn('w:pPr') + '/' + qn('w:outlineLvl'))
    if level is not None and level.get(qn('w:val')) in {str(i) for i in range(9)}:
        return True
    style = paragraph.style
    seen = set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        if re.fullmatch(r'Heading[1-9]', style.style_id or '', flags=re.I):
            return True
        level = style.element.find('./' + qn('w:pPr') + '/' + qn('w:outlineLvl'))
        if level is not None and level.get(qn('w:val')) in {str(i) for i in range(9)}:
            return True
        style = style.base_style
    return False


def inspect_tabs(path, paragraphs, fail):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    fields = []
    part_indexes = {}
    part_paragraphs = defaultdict(int)
    heading = None
    heading_paragraph = None
    previous_part = None
    continuation = None
    for global_index, paragraph in enumerate(paragraphs):
        part = str(paragraph.part.partname).lstrip('/')
        part_index = part_indexes.setdefault(part, len(part_indexes))
        local_index = part_paragraphs[part]
        part_paragraphs[part] += 1
        if previous_part != part:
            heading = heading_paragraph = continuation = None
            previous_part = part
        runs = paragraph._p.findall(qn('w:r'))
        candidates = [i for i, run in enumerate(runs) if _answer_tab(run)]
        if not candidates:
            continuation = None
            if _heading(paragraph):
                heading = paragraph.text.strip()
                heading_paragraph = local_index
            continue
        # Do not infer a logical region through other inline structures or table
        # boundaries. Existing table support owns its own field contract.
        if (paragraph._p.xpath('ancestor::w:tc')
                or any(child.tag not in {qn('w:pPr'), qn('w:r')} for child in paragraph._p)
                or any(child.tag not in {qn('w:rPr'), qn('w:t'), qn('w:tab')}
                       for run in runs for child in run)):
            fail('An underlined answer area crosses an unsupported structure. Use a labelled paragraph or a supported question/answer table.', 'unsupported_structure')
        if paragraph._p.xpath('./w:pPr/w:framePr'):
            fail('Positioned answer paragraphs could hide expanding text. Use a flowing paragraph.', 'overflow_risk')
        prior = -1
        for run_index in candidates:
            label_runs = runs[prior + 1:run_index]
            label = _text(label_runs)
            separator_tabs = [child for run in label_runs for child in run if child.tag == qn('w:tab')]
            # A second answer needs its own label and a single explicit ordinary
            # separator. Otherwise the boundary is not strong enough to fill.
            if prior >= 0 and (len(separator_tabs) != 1 or not label):
                fail('Adjacent underlined areas need separate labels and a separating tab. Review the form layout before uploading.', 'ambiguous_fields')
            anchor = {'part': part, 'paragraph': local_index, 'run': run_index,
                      'child': list(runs[run_index]).index(runs[run_index].find(qn('w:tab')))}
            grouping = 'label'
            notes = []
            if not label:
                if len(candidates) != 1 or separator_tabs:
                    fail('An underlined answer area has no clear label. Add a label or section heading.', 'ambiguous_fields')
                if continuation is not None and continuation['last_paragraph'] == local_index - 1:
                    continuation['field']['locator']['tab_form']['anchors'].append(anchor)
                    continuation['field']['review_notes'] = ['Confirm that these consecutive answer lines belong to one question.']
                    continuation['last_paragraph'] = local_index
                    prior = run_index
                    continue
                if heading is None or heading_paragraph != local_index - 1:
                    fail('An underlined answer area has no nearby labelled heading. Add a clear label or use a supported placeholder.', 'ambiguous_fields')
                label, grouping = heading, 'heading_continuation'
                notes = ['Confirm the section label and whether its consecutive answer lines belong together.']
            elif re.fullmatch(r'\d+[.)]', label):
                if not heading or len(candidates) != 1:
                    fail('A numbered answer line needs a section heading so its meaning can be reviewed.', 'ambiguous_fields')
                label, grouping = f'{heading} — {label.rstrip(".)")}', 'numbered'
                notes = ['Confirm the numbered item belongs to this section.']
            else:
                if not any(character.isalpha() for character in label):
                    fail('An underlined answer area has no meaningful label. Review its label before uploading.', 'ambiguous_fields')
                label = label.rstrip(':').strip()
                if not _text(label_runs).endswith(':'):
                    notes = ['Confirm this label inferred from the text immediately before the answer area.']
            field = {'key': f'tab_v1_{digest[:16]}_{part_index}_{local_index}_{run_index}',
                     'label': label, 'kind': 'text',
                     'locator': {'tab_form': {'version': VERSION, 'source_sha256': digest,
                                             'grouping': grouping, 'anchors': [anchor]}},
                     'review_notes': notes}
            # ⚠️ STRIP TRAILING PUNCTUATION, NOT ONLY THE INLINE COLON. A heading-continuation
            # label is taken from `paragraph.text` verbatim, so `Electronically signed by:` never
            # reached this set and the field got NO clinician-identity policy — measured, and it
            # finalized another clinician's name. A full-width colon does the same thing.
            normalized = re.sub(r'\s+', ' ', label).strip().rstrip(':：.,;· \t').strip().casefold()
            if normalized in {'electronically signed by', 'signed by'}:
                field['answer_policy'] = 'clinician_identity'
                field['review_notes'].append('Optional clinician identity: review explicitly; this does not create a digital signature.')
            if normalized in {'dd (dictated)', 'dt (transcribed)'}:
                field['review_notes'].append('Use only a date explicitly supplied in the notes; no date is filled automatically.')
            fields.append(field)
            if grouping == 'heading_continuation':
                continuation = {'field': field, 'last_paragraph': local_index}
            else:
                continuation = None
            prior = run_index
        if _text(runs[candidates[-1] + 1:]):
            # This is not an ordinary label/blank form: trailing text might be an
            # attestation or separate unanchored question. Refuse partial mapping.
            fail('Text after an underlined answer area needs an explicit supported field boundary.', 'ambiguous_fields')
    return fields


def _flowing(paragraph):
    props = paragraph.get_or_add_pPr()
    spacing = props.get_or_add_spacing()
    # Override exact spacing inherited from a style too: auto line spacing avoids
    # clipping tall glyphs. Direct exact values become minimum physical spacing.
    if spacing.get(qn('w:lineRule')) == 'exact':
        spacing.set(qn('w:lineRule'), 'atLeast')
    elif spacing.get(qn('w:lineRule')) is None:
        spacing.set(qn('w:lineRule'), 'auto')
        spacing.set(qn('w:line'), '240')
    for tag in ('keepLines', 'keepNext'):
        setting = getattr(props, 'get_or_add_' + tag)()
        setting.set(qn('w:val'), '0')


def _replace_tab(run, answer):
    tab = run.find(qn('w:tab'))
    if not answer:
        return
    index = list(run).index(tab)
    run.remove(tab)
    # Original blank lines may be light grey. Explicit answer text uses black,
    # retaining the run's font, size and underline instead of inheriting faint ink.
    props = run.find(qn('w:rPr'))
    props = props if props is not None else OxmlElement('w:rPr')
    if props.getparent() is None:
        run.insert(0, props)
        index += 1
    color = props.get_or_add_color()
    color.attrib.clear()
    color.set(qn('w:val'), '000000')
    for number, line in enumerate(answer.replace('\r\n', '\n').replace('\r', '\n').split('\n')):
        if number:
            element = OxmlElement('w:br')
            run.insert(index, element)
            index += 1
        for token_index, token in enumerate(line.split('\t')):
            if token_index:
                run.insert(index, OxmlElement('w:tab'))
                index += 1
            text = OxmlElement('w:t')
            text.set(qn('xml:space'), 'preserve')
            text.text = token
            run.insert(index, text)
            index += 1


def fill_tabs(path, output, parts, fields, answers, also_changed=()):
    """Write tab answers and emit the package.

    `also_changed` names parts another writer has already mutated in this same element tree —
    a mixed mapping fills its table cells and placeholders first. They must be listed here or
    the package copy below would write their ORIGINAL bytes back and silently discard those
    answers, which is the one failure this function's copy-the-original design makes easy.
    """
    parts = {str(part.partname).lstrip('/'): part for part in parts}
    paragraphs = {name: list(part.element.iter(qn('w:p'))) for name, part in parts.items()}
    changed = {name for name in also_changed if name in parts}
    paired = defaultdict(list)
    for field in fields:
        locator = field['locator']['tab_form']
        anchors = locator['anchors']
        answer = answers.get(field['key'], '')
        # The logical answer is inserted exactly once in its first physical
        # region. Explicit lines use existing continuation regions first; surplus
        # lines expand the final region. Unused blank lines remain in the form.
        lines = answer.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        chunks = lines[:len(anchors) - 1] + ['\n'.join(lines[len(anchors) - 1:])] if len(anchors) > 1 else [answer]
        chunks += [''] * (len(anchors) - len(chunks))
        for anchor, chunk in zip(anchors, chunks):
            paragraph = paragraphs[anchor['part']][anchor['paragraph']]
            run = paragraph.findall(qn('w:r'))[anchor['run']]
            if chunk:
                _replace_tab(run, chunk)
                _flowing(paragraph)
                changed.add(anchor['part'])
            paired[(anchor['part'], anchor['paragraph'])].append((anchor['run'], answer))
    # Word flows short paired answers in the original inline arrangement. Long
    # or multiline pairs continue within an answered run. The original ordinary
    # separator tab and its run belong to the printed questions and stay intact.
    # A missing first answer keeps its blank run; the second answer can start
    # below its own label without changing that neighboring blank destination.
    for (part, paragraph_index), group in paired.items():
        if len(group) < 2 or not any(len(value) > 40 or '\n' in value or '\r' in value or '\t' in value for _, value in group):
            continue
        paragraph = paragraphs[part][paragraph_index]
        runs = paragraph.findall(qn('w:r'))
        for (first, first_answer), (second, second_answer) in zip(group, group[1:]):
            if first_answer:
                runs[first].append(OxmlElement('w:br'))
            elif second_answer:
                run = runs[second]
                index = 1 if len(run) and run[0].tag == qn('w:rPr') else 0
                run.insert(index, OxmlElement('w:br'))
        _flowing(paragraph)
        changed.add(part)
    # python-docx saving normalizes unrelated package parts. Copy the retained
    # original package instead; only touched story XML has newly serialized bytes.
    with ZipFile(path) as original, ZipFile(output, 'x') as exported:
        exported.comment = original.comment
        for item in original.infolist():
            data = parts[item.filename].blob if item.filename in changed else original.read(item)
            exported.writestr(deepcopy(item), data)
