"""Full blank-source outline for bounded mapping proposals, inside the isolated parser."""
if __package__:
    from . import word_v3 as word
else:
    import word_v3 as word


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
