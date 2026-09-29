"""Full blank-source outline for bounded mapping proposals, inside the isolated parser."""
if __package__:
    from . import word_v3 as word
    from . import source_policy
else:
    import word_v3 as word
    import source_policy


def outline(data):
    rows = word.outline(data)['slots']
    detector = word.Detector(word.open_package(data))
    for row in rows:
        slot = detector.index.by_id[row['slot']]
        if slot.kind in ('p', 'glyphs'):
            text = detector.ptext(slot.el)[0]
        elif slot.kind == 'tc':
            text = detector.cell_text(slot)
        elif slot.kind == 'sdt':
            content = slot.el.find(word.q('w:sdtContent'))
            text = detector.text(content, own=False) if content is not None else ''
        else:
            text = slot.info.get('name') or slot.info.get('field') or ''
        row['text'] = text.replace('\x00', '[control]')
        row['options'] = list(slot.info.get('options') or [])
        row['heading'] = detector.heading_before(slot)
        cell = detector.host_cell(slot)
        row['row_label'] = detector.row_label(cell.parent, cell.info['row'], cell.info['col']) if cell is not None else ''
        row['parent'] = slot.parent.id if slot.parent is not None else ''
        if cell is not None:
            row['row'] = cell.info['row']
            row['column'] = cell.info['col']
    return {'contract': word.CONTRACT, 'slots': rows}


#: What the engine holds, in the order a place's reason is named when several apply (word_v3.HELD_CODES).
HOLDS = word.HELD_CODES


def places(data):
    """What the ONE authority holds at each place of a blank original (word_v3.held_places), for the model-assisted
    mapping place rule, in this module's historical shape: `held` lists [place, first reason in HOLDS order] and
    `anchored` every place inside a header/footer, text box, drawing, object or positioned frame (word.floating_place).
    The signing, consent and authorship readers that used to live here are the authority's own now; nothing here reads
    whether a cell is empty or whether the engine made an area. Nothing is written."""
    report = word.held_report(data)
    return {'contract': report['contract'], 'held': sorted([row['slot'], row['code']] for row in report['held']),
            'anchored': report['anchored']}
