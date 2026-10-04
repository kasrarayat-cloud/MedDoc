"""Bounded source ownership under an explicit, immutable transcript review.

An original destination heading names its own complete nominal value. A
complete observation names its own grammatical theme. Neither proof turns
another person, a quotation or a clinical qualifier into the encounter patient.
"""


def backward_attribution(reading, selected, docs):
    """A later pointer assigning its referenced source to another bearer.

    The pointer's grammatical role supplies the backward edge, not the mere
    presence of a family member elsewhere in the transcript. A person inside
    that finite predicate's object/possessor cannot be supplied by the earlier
    default-patient review. Uncertain or open attribution remains a dependency.
    """
    from . import generation as g, v3_actors as a
    import re
    chosen = {u['id'] for u in selected}
    first = min((u['start'] for u in selected), default=None)
    if first is None:
        return False
    for unit, doc in zip(reading['units'], docs):
        if unit['id'] in chosen or unit['start'] <= first:
            continue
        if doc is None:
            return True
        for target in doc:
            if target.pos_ not in ('NOUN', 'PRON') or target.dep_ not in ('nsubj', 'nsubjpass'):
                continue
            if a.names_person(target) or a.names_carer(target) or a.this_patient(target):
                continue
            pointer = any('Dem' in t.morph.get('PronType') or 'Def' in t.morph.get('Definite')
                or re.fullmatch(g.SCOPE_POINTERS, t.text, re.I) for t in target.subtree)
            predicate = target.head
            if not pointer or predicate.pos_ not in ('AUX', 'VERB'):
                continue
            theme = set(target.subtree)
            bearers = [t for t in predicate.subtree if t not in theme
                and t.dep_ in ('dobj', 'pobj', 'attr', 'poss')
                and (a.this_patient(t) or a.names_person(t) or a.names_carer(t) or t.pos_ in ('PROPN', 'PRON'))
                and not any(ancestor.dep_ == 'agent' for ancestor in t.ancestors)]
            # "Prepared by the clinician" names an author in the passive
            # agent, whereas a source predicate excluding its current patient
            # or appointing another visit cannot confirm this source's bearer.
            temporal = any(t.pos_ != 'ADP' and ({a._lemma(t), a._fold(t.text)} & a.SOLE_FIELD_TIME)
                for t in predicate.subtree)
            patient = any(a.this_patient(t) for t in bearers)
            if temporal or patient and a._negates(predicate):
                return True
            if not bearers:
                continue
            closed = bool(predicate.dep_ == 'ROOT'
                and any('Fin' in t.morph.get('VerbForm') for t in (predicate, *predicate.children))
                and '?' not in doc.text and not any(t.tag_ == 'MD'
                    or a._fold(t.text) in a.SOLE_UNCERTAIN
                    or t.dep_ in ('advcl', 'relcl', 'ccomp', 'xcomp', 'conj') for t in predicate.subtree))
            if (closed and a._negates(predicate) and not patient
                    and sum(t.dep_ == 'neg' for t in predicate.subtree) == 1
                    and not any(t.dep_ == 'advmod' for t in predicate.subtree)):
                continue
            if closed and patient and all(a.this_patient(t) for t in bearers):
                continue
            return True
    return False


def complete_ids(reading, field, ordered):
    from . import generation as g, v3_syntax, v3_actors as a
    if not reading.get('_transcript_review_proof') or field.get('kind') not in ('text', 'long_text'):
        return set()
    if field.get('write_protected') or len(reading['named'].get(g.question_key(field['label']), ())) != 1:
        return set()
    proof = reading['_transcript_review_proof']
    units = reading['units']
    docs = v3_syntax.docs(u['quote'] for u in units)
    labels = v3_syntax.docs([field['label']])
    if docs is None or labels is None:
        return set()
    if backward_attribution(reading, ordered, docs):
        return set()
    # An abstract clinical annotation entered in error retracts its source.
    # A bounded numeric correction (for example the earlier pain score) is not
    # an invalidation of the entire examination or assessment.
    for doc in docs:
        roots = [t for t in doc if t.dep_ == 'ROOT']
        if len(roots) != 1:
            continue
        root = roots[0]
        targets = [t for t in root.children if t.dep_ in ('nsubjpass', 'dobj')]
        if (a._lemma(root) == 'enter' and 'Fin' in {value for t in (root, *root.children)
                for value in t.morph.get('VerbForm')} and not a._negates(root)
                and len(targets) == 1 and targets[0].pos_ in ('NOUN', 'PROPN')
                and any(t.dep_ == 'prep' and a._lemma(t) == 'in'
                    and any(g.V3_IDENTITY_WORDS.fullmatch(c.text) for c in t.children if c.dep_ == 'pobj')
                    for t in root.children)):
            return set()
    label = g.question_key(field['label'])
    by_id = {u['id']: (u, doc) for u, doc in zip(units, docs)}
    label_words = {a._lemma(t) for t in labels[0] if t.pos_ in ('NOUN', 'ADJ')}
    heading = field['label'].strip().rstrip(':').casefold() + '.'
    headings = [u for u in units if u['quote'].casefold() == heading]
    heading_position = reading['position'][headings[0]['id']] if len(headings) == 1 else None
    # A human subject of a completed source clause establishes somebody's
    # scope even when its action is absent from the old bearer-verb lexicon.
    # Printed headings and metadata name no new patient. Only an explicit
    # patient clause/object can reanchor that scope.
    foreign_before = {}
    foreign = False
    from .reviewed_speaker import frames
    speakers = frames(reading, docs, proof)
    qualified_speakers = set()
    for unit, doc in zip(units, docs):
        foreign_before[unit['id']] = foreign
        info = reading['actors'][unit['id']]
        state = reading['resolved'][unit['id']]
        if unit['id'] in speakers and not foreign:
            # This is a documented speaker, not a new clinical bearer. It
            # preserves the current review scope and never resets a foreign one.
            qualified_speakers.add(unit['id'])
            continue
        if info.get('other_floor') or state.get('self_other'):
            foreign = True
            continue
        subjects = [t for t in doc if t.dep_ in ('nsubj', 'nsubjpass')]
        if any(a.this_patient(t) for t in subjects):
            foreign = False
        elif any(a.names_person(t) or a.names_carer(t)
                 or t.pos_ == 'PROPN' or t.pos_ == 'PRON' for t in subjects):
            from .v3_literal_facts import _patient_object
            foreign = not any(_patient_object(t.head) for t in subjects)

    def initialism(t):
        return bool(t.pos_ == 'PROPN' and t.text.isalpha() and t.text.isupper()
            and 2 <= len(t.text) <= 6 and any(c.dep_ == 'nummod' and c.like_num for c in t.children))

    def owned(unit, doc, *, caption=False):
        info = reading['actors'][unit['id']]
        if (not proof['start'] <= unit['start'] < unit['end'] <= proof['end']
                or foreign_before[unit['id']] or not info.get('readable') or info.get('other_floor')
                or reading['resolved'][unit['id']].get('self_other')
                or unit['id'] in reading['unresolved_subjects']
                or info.get('habitual') or info.get('past_time')
                or info.get('dependent') or info.get('bounded')
                or info.get('bare_cessation') or info.get('ceased_keys')):
            return False
        return bool(doc is not None and len(list(doc.sents)) == 1
            and not any((t.pos_ == 'PRON' and not (t.dep_ == 'expl' and a._fold(t.text) == 'there'))
                or (t.pos_ == 'PROPN' and not initialism(t))
                or (not caption and (a.names_person(t) or a.names_carer(t)))
                or t.text in ('"', '“', '”', '‘', '’') for t in doc)
            and not any(t.tag_ == 'MD' for t in doc)
            and not any(g.SELF_CORRECTION.search(s) or g.INHERITED_SCOPE.search(s)
                        for s in g.safety_readings(unit['quote'])))

    def nominal(doc):
        words = [t for t in doc if not t.is_punct and not t.is_space]
        roots = [t for t in words if t.dep_ == 'ROOT']
        return bool(words and len(roots) == 1 and (roots[0].pos_ == 'NOUN' or initialism(roots[0]))
            and all(t.pos_ in ('NOUN', 'ADJ', 'DET', 'NUM', 'CCONJ') or initialism(t) for t in words)
            and all(t.dep_ in ('ROOT', 'amod', 'compound', 'det', 'nummod', 'conj', 'cc', 'nsubj') for t in words)
            and all(a._fold(t.text) == 'and' for t in words if t.dep_ == 'cc')
            and not any(g.UNSETTLED.search(s) or g.DENIAL.search(s) for s in g.safety_readings(doc.text)))

    result = set()
    selected = {u['id'] for u in ordered}
    from .source_scope import _date_scope_backward_dependency
    source_dependency = _date_scope_backward_dependency(reading, ordered)
    for unit in ordered:
        _, doc = by_id[unit['id']]
        if unit['id'] in qualified_speakers and speakers[unit['id']] == label:
            result.add(unit['id'])
            continue
        from .reviewed_procedure_source import caption, complete
        care_caption = bool(doc is not None and caption(doc, field))
        if not owned(unit, doc, caption=care_caption):
            continue
        if not source_dependency and (care_caption or complete(doc, field, nominal=nominal)):
            result.add(unit['id'])
            continue
        position = reading['position'][unit['id']]
        previous = units[position - 1]['id'] if position else None
        if previous in qualified_speakers and previous in selected and speakers[previous] == label:
            # A complete adjacent entity statement belongs to the same selected
            # report, retaining both source units. An agent, another speaker,
            # future/hypothetical clause or a medication change gains no proof.
            from .v3_literal_facts import _simple_fact
            if (_simple_fact(doc, field['label']) == 'entity'
                    and not any(t.dep_ == 'agent' for t in doc)):
                result.add(unit['id'])
                continue
        # One adjacent complete phrase, under the exact unique source heading.
        # A later heading, two values or a named actor cannot gain this proof.
        if heading_position is not None and position == heading_position + 1 and nominal(doc):
            result.add(unit['id'])
            continue
        roots = [t for t in doc if t.dep_ == 'ROOT']
        if len(roots) != 1:
            continue
        root = roots[0]
        subjects = [t for t in root.children if t.dep_ in ('nsubj', 'nsubjpass')]
        # A completed passive observation with a theme naming this original
        # question, or an expletive copula whose nominal attribute names it.
        passive = bool(root.pos_ == 'VERB' and root.tag_ == 'VBN'
            and any(t.dep_ == 'auxpass' and 'Fin' in t.morph.get('VerbForm') for t in root.children)
            and len(subjects) == 1 and subjects[0].dep_ == 'nsubjpass'
            and not any(t.dep_ in ('agent', 'prep', 'ccomp', 'xcomp', 'advcl', 'relcl', 'conj') for t in doc))
        attributes = [t for t in root.children if t.dep_ == 'attr' and t.pos_ == 'NOUN']
        expletive = bool(root.pos_ in ('AUX', 'VERB') and 'Fin' in root.morph.get('VerbForm')
            and a._lemma(root) == 'be' and len(attributes) == 1
            and any(t.dep_ == 'expl' and a._fold(t.text) == 'there' for t in root.children)
            and not subjects and not any(t.dep_ in ('prep', 'ccomp', 'xcomp', 'advcl', 'relcl', 'conj') for t in doc))
        theme = subjects[0] if passive else attributes[0] if expletive else None
        if theme is None:
            continue
        theme_words = {a._lemma(t) for t in theme.subtree if t.pos_ in ('NOUN', 'ADJ')}
        if label_words and theme_words == label_words:
            result.add(unit['id'])
    if (heading_position is not None and heading_position + 1 < len(units)
            and units[heading_position + 1]['id'] in result
            and units[heading_position]['id'] in selected):
        result.add(units[heading_position]['id'])
    return result


def self_reference(reading, field, chosen, proven):
    """Only proved source assertions and their exact own headings name this field.

    The old reference index couples whole paragraphs. Read its actual literal
    references here; the signed relation and all other clinical floors still see
    every source unit. A contradictory/reference clause is never discharged.
    """
    import re
    from . import generation as g, v3_syntax, v3_actors as a
    if not chosen or not chosen <= proven:
        return False
    label = g.question_key(field['label'])
    variants = {label}
    if label.endswith('ies'):
        variants.add(label[:-3] + 'y')
    elif label.endswith('s') and not label.endswith(('ss', 'us', 'is')):
        variants.add(label[:-1])
    elif label.endswith('y'):
        variants.add(label[:-1] + 'ies')
    else:
        variants.add(label + 's')
    pattern = re.compile(g.LETTER_BEFORE + '(?:' + '|'.join(re.escape(v) for v in variants) + ')' + g.LETTER_AFTER, re.I)
    heading = field['label'].strip().rstrip(':').casefold() + '.'
    seen = False
    for unit in reading['units']:
        if not any(pattern.search(s) for s in g.safety_readings(unit['quote'])):
            continue
        seen = True
        if unit['id'] in chosen:
            continue
        next_position = reading['position'][unit['id']] + 1
        if (unit['quote'].casefold() == heading and next_position < len(reading['units'])
                and reading['units'][next_position]['id'] in chosen):
            continue
        # A complete numeric metadata phrase can use the field's name as a
        # modifier of a different nominal head ("Procedure date, 09/21/2026").
        # A condition, cancellation, person or uncertain time cannot enter it.
        docs = v3_syntax.docs([unit['quote']])
        doc = docs[0] if docs else None
        words = [t for t in doc if not t.is_punct and not t.is_space] if doc is not None else []
        roots = [t for t in words if t.dep_ == 'ROOT']
        reference = pattern.fullmatch(words[0].text) if words else None
        numeric = bool(words and len(roots) == 1 and roots[0].pos_ == 'NOUN' and reference
            and words[0].dep_ == 'compound' and words[0].head == roots[0]
            and any(t.pos_ == 'NUM' for t in words)
            and all(t in (words[0], roots[0]) or t.pos_ == 'NUM' for t in words)
            and not any(g.UNSETTLED.search(s) or g.DENIAL.search(s) or g.INHERITED_SCOPE.search(s)
                or g.SELF_CORRECTION.search(s) for s in g.safety_readings(unit['quote'])))
        if not numeric:
            return False
    return seen
