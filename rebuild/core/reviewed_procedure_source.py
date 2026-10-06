"""Complete procedural observations inside an explicit immutable source review.

The caller supplies its existing ownership, invalidation and source guards.
This grants no actor, date, quantity, option or clinical interpretation.
"""


def destination(field):
    """Original question context cannot name another bearer or encounter time."""
    from . import v3_actors as a, v3_syntax as syntax
    from .v3_literal_facts import FOREIGN
    label = str(field.get('label') or '')
    context = str(field.get('context') or '')
    # The inspector's final breadcrumb is this exact original question. Parse
    # it once as a label; repeating it inside a longer title makes the pinned
    # tagger call "Recommendation" a proper name. Earlier context stays intact.
    parts = context.split(' > ')
    if len(parts) > 1 and parts[-1] == label:
        context = ' > '.join(parts[:-1])
    text = ' '.join((label, context))
    docs = syntax.docs([part for part in (label, context) if part])
    return bool(docs and all(doc is not None for doc in docs) and not FOREIGN.search(text)
        and not any(t.pos_ in ('PRON', 'PROPN') or a.names_carer(t)
            or a.names_person(t) and a._lemma(t) != 'patient'
            or {a._fold(t.text), a._lemma(t)} & (a.SOLE_FIELD_FRAMES | a.SOLE_FIELD_TIME)
            for doc in docs for t in doc))


def complete(doc, field, *, nominal):
    from . import generation as g, v3_actors as a
    words = [t for t in doc if not t.is_punct and not t.is_space]
    roots = [t for t in words if t.dep_ == 'ROOT']
    if len(roots) != 1:
        return False
    root = roots[0]
    label = g.question_key(field['label'])
    if not destination(field):
        return False
    # A complete coordinated nominal observation has no grammatical actor.
    # Its attribution is the clinician's explicit transcript review; field
    # relevance is the qualified model contract, not a new clinical lexicon.
    if label == 'findings' and nominal(doc):
        return True
    # Keep an aggregate's complete passive observation, including its negation.
    # Agents, possessors, conditions and multiple clauses gain no proof.
    if (label == 'findings' and root.pos_ == 'VERB' and root.tag_ == 'VBN'
            and any(t.dep_ == 'auxpass' and 'Fin' in t.morph.get('VerbForm') for t in root.children)
            and len([t for t in root.children if t.dep_ in ('nsubj', 'nsubjpass')]) == 1
            and any(t.dep_ == 'nsubjpass' and t.pos_ == 'NOUN' for t in root.children)
            and all(t.pos_ in ('NOUN', 'VERB', 'AUX', 'ADJ', 'DET', 'PART') for t in words)
            and not any(t.dep_ in ('agent', 'prep', 'ccomp', 'xcomp', 'advcl', 'relcl', 'conj', 'poss') for t in doc)):
        return True
    # The pinned parser reads the procedural instrument event as a past copula
    # with an adjectival complement. Bind "to" to this actual complete extent;
    # it cannot mean an intention, an unknown actor or an unfinished complement.
    if label == 'extent reached':
        subjects = [t for t in root.children if t.dep_ == 'nsubj']
        attributes = [t for t in root.children if t.dep_ == 'acomp']
        if (root.pos_ != 'AUX' or a._lemma(root) != 'be' or root.tag_ != 'VBD'
                or len(subjects) != 1 or len(attributes) != 1
                or subjects[0].pos_ != 'NOUN' or a._lemma(subjects[0]) != 'scope'
                or any(t.dep_ != 'det' or a._fold(t.text) != 'the' for t in subjects[0].children)
                or attributes[0].pos_ != 'ADJ' or a._lemma(attributes[0]) != 'advanced'
                or a._negates(root) or a._negates(attributes[0])):
            return False
        adjective = attributes[0]
        preps = [t for t in adjective.children if t.dep_ == 'prep']
        if (len(preps) != 1 or a._fold(preps[0].text) != 'to'
                or any(t.dep_ != 'prep' for t in adjective.children)):
            return False
        objects = [t for t in preps[0].children if t.dep_ == 'pobj']
        if (len(objects) != 1 or objects[0].pos_ != 'NOUN'
                or any(t.dep_ not in ('det', 'amod', 'compound')
                    or t.pos_ not in ('DET', 'ADJ', 'NOUN') for t in objects[0].children)
                or any(t.dep_ not in ('nsubj', 'acomp', 'punct') for t in root.children)):
            return False
        allowed = {(preps[0].idx, preps[0].idx + len(preps[0].text))}
        return bool(not any('Dem' in t.morph.get('PronType') for t in words)
            and all(t.pos_ in ('NOUN', 'AUX', 'ADJ', 'DET', 'ADP') for t in words)
            and all((m.start(), m.end()) in allowed for m in g.UNSETTLED.finditer(doc.text)))
    return False


def caption(doc, field):
    """An exact original care heading owns its full comma-delimited phrase.

    A clinician after "with" is a recipient, never a new patient bearer. The
    existing source reader still rejects every other person and every possessor.
    """
    from . import generation as g, v3_actors as a
    from .v3_literal_facts import CLINICIANS
    words = [t for t in doc if not t.is_punct and not t.is_space]
    roots = [t for t in words if t.dep_ == 'ROOT']
    if len(roots) != 1 or not destination(field):
        return False
    root = roots[0]
    if not (words[0] == root and root.pos_ == 'NOUN' and a._lemma(root) == g.question_key(field['label'])
            and g.v3_plan_question(field, g.question_key(field['label']))
            and any(t.text == ',' for t in root.children)):
        return False
    def recipient(t):
        return (a._lemma(t) in CLINICIANS and t.dep_ == 'pobj' and a._lemma(t.head) == 'with'
            and t.head.dep_ == 'prep' and not any(c.dep_ == 'poss' for c in t.children))
    return bool(all(t.pos_ in ('NOUN', 'ADJ', 'DET', 'NUM', 'ADP') or t.pos_ == 'VERB' and t.dep_ == 'amod' for t in words)
        and all(t.dep_ in ('ROOT', 'amod', 'compound', 'det', 'nummod', 'conj', 'prep', 'pobj') for t in words)
        and not any((a.names_person(t) or a.names_carer(t)) and not recipient(t) for t in words)
        and not any(g.UNSETTLED.search(s) or g.DENIAL.search(s) for s in g.safety_readings(doc.text)))
