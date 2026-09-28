"""Explicit printed authorship/attestation boundaries for new Word mappings.

The source is identified, never evidence that the required statement occurred.
This module does not choose answers or change an existing stored mapping.
"""
import re


def annotate(detector, fields):
    if __package__:
        from .word_v3 import fingerprint, q
        from .mapping_limits import MAX_MAPPING_CONTEXT
    else:
        from word_v3 import fingerprint, q
        from mapping_limits import MAX_MAPPING_CONTEXT

    def source(slot, text):
        return {'part': slot.part, 'slot': slot.path, 'fingerprint': fingerprint(slot.el), 'text': text}

    roles = {}
    current = None
    for root in detector.index.roots:
        if root.part != 'word/document.xml':
            continue
        if root.kind == 'p':
            text = re.sub(r'\s+', ' ', detector.text(root.el)).strip()
            role = re.fullmatch(r'(?:for|(?:to be )?completed by)\s+(?:the\s+)?(.{1,100}?)\s*:', text, re.I)
            if root.el.find('.//' + q('w:sectPr')) is not None:
                current = None
            elif role and role[1].lower() == 'patient':
                current = source(root, text)
            elif (role and re.search(r'\b(?:clinicians?|doctors?|physicians?|nurses?|supervisors?|parents?|guardians?|'
                                      r'carers?|caregivers?|witnesses?|employers?|managers?|representatives?)\b', role[1], re.I)) or \
                    detector.is_heading(root.el):
                current = None
        roles[root.id] = current

    for field in fields:
        loc = field.get('locator') or {}
        slot = detector.index.by_id.get(str(loc.get('part')) + '#' + str(loc.get('slot')))
        if slot is None:
            continue
        root = slot
        while root.parent is not None:
            root = root.parent
        policy = {}
        if roles.get(root.id):
            policy = {'source_author': 'patient', 'source': roles[root.id]}
        # A simple paired table's left-hand source is explicit. Do not infer
        # attestation authority from a model-edited label or a remote header.
        if slot.kind == 'tc' and loc.get('target', {}).get('type') == 'cell':
            row = sorted(detector.grid(slot.parent).get(slot.info['row'], []), key=lambda c: c.info['col'])
            position = next((i for i, c in enumerate(row) if c is slot), None)
            if position and position > 0:
                previous = row[position - 1]
                text = detector.cell_text(previous)
                label = field.get('label', '')
                if text.strip(' :') == label.strip(' :') and len(text) <= MAX_MAPPING_CONTEXT and \
                        re.search(r'\b(?:report|form|document)\b', text, re.I) and re.search(
                            r'\bconfirm\s+(?:that\s+)?(?:the\s+)?patient\s+(?:(?:has|had)\s+)?'
                            r'(?:read\b|reviewed\b|seen\b|had\s+sight\s+of\b|'
                            r'(?:had|was\s+given)\s+(?:an?\s+)?opportunity\s+to\b)', text, re.I):
                    policy.update(attestation='document_review', attestation_source=source(previous, text))
        if policy:
            field['answer_policy'] = policy
