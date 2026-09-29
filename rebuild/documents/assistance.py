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


#: What the engine holds, in the order a place's reason is named when several apply.
HOLDS = ('signing', 'consent', 'protected', 'authorship')


def places(data):
    """What the deterministic engine itself holds at each place of a blank original, for the model-assisted mapping
    place rule (core.mapping_assistance). Nothing is written. Every reader here is the engine's own:

      signing     every place a signature/initials area of the detection writes to, or a paragraph (each printed
                  part alone, word.label_parts) or a table row label the engine's kind rule reads as
                  signature/initials;
      consent     a question box whose printed question or section is a signing/consent context
                  (Detector.question_box_signing);
      protected   every place fill refuses to write (word.protected_places: each write-protected area's anchor, the
                  protected regions and the protected legacy text fields);
      authorship  a printed patient-role section or an attestation answer cell (source_policy).

    `held` maps a place to its first reason in HOLDS order; `anchored` lists every place inside a header/footer,
    text box, drawing, object or positioned frame (word.floating_place)."""
    package = word.open_package(data)
    source = word.Detector(package, layout_proposal=True)
    source.detect()
    index = source.index
    protected, regions, legacy = word.protected_places(package, source, index)
    found = {code: set() for code in HOLDS}
    for area in source.areas:
        if area.kind in word.SIGNING_KINDS:
            found['signing'].update(word.field_locations(word.area_to_field(0, area)))
    for slot in index.slots:
        if slot.kind == 'p' and word.signing_wording(source.ptext(slot.el)[0]):
            found['signing'].add(slot.id)
        cell = source.host_cell(slot) if slot.kind == 'tc' else None
        if cell is not None and word.signing_wording(source.row_label(cell.parent, cell.info['row'], cell.info['col'])):
            found['signing'].add(slot.id)
        if slot.kind == 'tc' and source_policy.attestation_statement(source, slot):
            found['authorship'].add(slot.id)
    found['consent'] = source.signing_boxes | protected.signing_boxes
    found['protected'] |= set(regions) | set(legacy)
    found['authorship'] |= {root for root, role in source_policy.roles(source).items() if role}
    held = {}
    for code in HOLDS:
        for identity in found[code]:
            held.setdefault(identity, code)
    anchored = sorted(slot.id for slot in index.slots if word.floating_place(slot))
    return {'contract': word.CONTRACT, 'held': sorted([identity, code] for identity, code in held.items()),
            'anchored': anchored}
