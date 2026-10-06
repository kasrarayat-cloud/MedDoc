"""Source-owned predicates under a complete ordinary relation.

The positive single-patient reading and the original neutral destination are
prerequisites. This scopes an operator to its grammatical property; it supplies
neither a patient identity nor a clinical synonym.
"""


def apply(reading):
    from . import generation as g, v3_actors as a, v3_syntax as syntax
    if not reading.get('sole_patient'):
        return reading
    if '_ordinary_scoped_roles' in reading:
        return reading
    docs = syntax.docs(u['quote'] for u in reading['units'])
    if docs is None or any(doc is None for doc in docs):
        return reading
    labels = {label: matches[0] for label, matches in reading['named'].items()
        if len(matches) == 1 and matches[0].get('kind') in ('text', 'long_text')
        and not matches[0].get('write_protected') and not matches[0].get('answer_policy')
        and a.neutral_field(matches[0]['label'], matches[0].get('context', ''))}
    roles = {}
    for index, (unit, doc) in enumerate(zip(reading['units'], docs)):
        uid = unit['id']; info = reading['actors'][uid]; sole = info.get('sole') or {}
        root = next((t for t in doc if t.dep_ == 'ROOT'), None)
        if (root is None or not sole or sole['unknown'] or info.get('other_floor')
                or info.get('habitual') or info.get('past_time') or info.get('bounded')
                or info.get('bare_cessation') or info.get('ceased_keys')):
            continue
        # The retained literal declaration owns an allergy property, not the
        # act of taking a medication. Context must positively name no other
        # person or time; this does not discard the original context.
        if unit['quote'] == 'No known drug allergies.' and 'allergies' in labels:
            roles[uid] = {'owner': 'allergies', 'classes': frozenset({'allergy'}),
                          'current': True, 'negative_allergy': True}
            continue
        # A finite, affirmative, present normal result belongs to the exact
        # source question. Preserve anatomical modifiers and every source byte.
        if ('examination' in labels and root.pos_ == 'AUX' and a._lemma(root) == 'be'
                and root.tag_ in ('VBP', 'VBZ') and not a._negates(root)
                and not sole['uncertain'] and sole['negation_only']):
            subjects = [t for t in root.children if t.dep_ == 'nsubj']
            attributes = [t for t in root.children if t.dep_ == 'acomp']
            if (len(subjects) == len(attributes) == 1 and subjects[0].pos_ == 'NOUN'
                    and a._lemma(subjects[0]) == 'examination'
                    and attributes[0].pos_ == 'ADJ' and a._lemma(attributes[0]) == 'normal'
                    and all(t == subjects[0] or t.dep_ in ('amod', 'det') for t in subjects[0].subtree)
                    and not any(t.dep_ in ('conj', 'prep', 'advcl', 'ccomp', 'xcomp') for t in root.children)):
                roles[uid] = {'owner': 'examination', 'classes': frozenset({'finding'}),
                              'current': True, 'normal_result': True}
                continue
        # An explicit patient future follow-up is a care event in the adjacent
        # documented Plan. A pronoun still requires the positive whole-note
        # actor proof; a condition, unknown event or medication ending gains none.
        previous = reading['units'][index - 1]['id'] if index else None
        own = reading['parsed'].get(previous)
        if ('plan' in labels and own and own[0] == 'plan'
                and info.get('kind') in ('pronoun', 'patient') and not sole['bad_pronoun']
                and not info.get('dependent') and info.get('intention')
                and root.pos_ == 'VERB' and a._lemma(root) == 'follow'
                and not a._negates(root)
                and any(t.dep_ == 'aux' and a._fold(t.text) == 'will' for t in root.children)
                and any(t.dep_ == 'prt' and a._fold(t.text) == 'up' for t in root.children)
                and not sole['uncertain'] and sole['negation_only']
                and not any(t.dep_ in ('conj', 'advcl', 'ccomp', 'xcomp', 'dobj', 'obj') for t in root.children)):
            roles[uid] = {'owner': 'plan', 'classes': frozenset({'care'}),
                          'current': False, 'follow_up': True}
    actors = {uid: {**info, 'sole': dict(info.get('sole') or {})} for uid, info in reading['actors'].items()}
    subjects = dict(reading['subjects'])
    for uid, role in roles.items():
        actors[uid]['sole'].update(classes=role['classes'], current=role['current'],
                                  reach=actors[uid]['sole']['reach'] - {'global'})
        subjects[uid] = role['owner']
    return {**reading, 'actors': actors, 'subjects': subjects,
            '_ordinary_scoped_roles': roles,
            '_ordinary_scope_docs': {u['id']: doc for u, doc in zip(reading['units'], docs)}}


def effective(reading, unit, chosen, label):
    """A per-answer operator reading; the full source remains in every guard."""
    if '_ordinary_scoped_roles' not in reading:
        return reading
    from . import v3_actors as a
    actors = {uid: {**info, 'sole': dict(info.get('sole') or {})} for uid, info in reading['actors'].items()}
    roles = reading['_ordinary_scoped_roles']; uid = unit['id']; mine = actors[uid]['sole']
    def negative_allergy(oid):
        return bool(roles.get(oid, {}).get('negative_allergy') and actors[oid]['sole']['classes'] == {'allergy'})
    def apart(oid, other_id):
        own = actors[oid]['sole']; other = actors[other_id]['sole']
        return bool(not other['unknown'] and 'global' not in other['reach']
            and 'allergy' not in other['classes']
            and not ('medication' in other['classes'] and other['classes'] & a.SOLE_CLINICAL)
            and not actors[other_id].get('bare_cessation') and not own['keys'] & other['keys'])
    if negative_allergy(uid) and all(other['id'] in chosen or apart(uid, other['id']) for other in reading['units']):
        mine['reach'] = frozenset()
    for oid, info in actors.items():
        if oid in chosen:
            continue
        theirs = info['sole']; doc = reading['_ordinary_scope_docs'][oid]
        root = next((t for t in doc if t.dep_ == 'ROOT'), None)
        # A noun such as the direct argument "visual changes" is not a
        # medication-change predicate. Read operators by their actual roles.
        def nominal_argument(t):
            return bool(t.pos_ == 'NOUN' and t.dep_ in ('dobj', 'conj')
                or t.pos_ == 'VERB' and t.tag_ == 'VBG' and t.head == root
                and t.dep_ in ('dobj', 'xcomp')
                and not any(c.dep_ not in ('det', 'amod', 'punct') for c in t.children))
        direct_denial = bool(root is not None and theirs['classes'] and theirs['classes'] <= a.SOLE_CLINICAL
            and not theirs['unknown'] and not theirs['uncertain'] and 'global' not in theirs['reach']
            and root.pos_ == 'VERB' and a._lemma(root) == 'deny'
            and any(t.dep_ == 'dobj' or nominal_argument(t) for t in root.children)
            and not any(t.dep_ in ('ccomp', 'advcl', 'relcl')
                or t.dep_ == 'xcomp' and not nominal_argument(t)
                or t.dep_ == 'conj' and t.pos_ in ('VERB', 'AUX') or t.tag_ == 'MD' for t in doc)
            and all(a._lemma(t) in a.SOLE_NEGATION | {'or'}
                or nominal_argument(t)
                for t in doc if a._lemma(t) in a.SOLE_OPERATORS['class'])
            and not any(a.SOLE_CLASSES.get(a._lemma(t), frozenset()) - a.SOLE_CLINICAL
                for t in doc if t.pos_ == 'NOUN'))
        # A complete denial of a separately named symptom does not oppose
        # the literal absence of drug allergies. It still cannot establish
        # an affirmative symptom, allergy reaction or medication change.
        if (negative_allergy(oid) and (not mine['reach'] or nominal_denial_atoms(reading, unit))
                and apart(oid, uid)):
            theirs['reach'] -= {'class'}
        specific = (mine['classes'] == {'medication'} and not mine['reach']
            or negative_allergy(uid) or roles.get(uid, {}).get('normal_result')
            or label == 'plan' and roles.get(uid, {}).get('follow_up'))
        if direct_denial and specific and not mine['keys'] & theirs['keys']:
            theirs['reach'] -= {'class'}
        if (label == 'plan' and roles.get(uid, {}).get('follow_up')
                and theirs['negation_only'] and not theirs['unknown'] and not theirs['uncertain']
                and 'global' not in theirs['reach'] and theirs['classes']
                and not theirs['classes'] & {'care', 'therapy', 'test', 'medication', 'allergy'}
                and not mine['keys'] & theirs['keys']):
            theirs['reach'] -= {'class'}
    return {**reading, 'actors': actors}


def clinical_atoms(reading, unit):
    """Closed symptom meanings, not different words presumed independent.

    Only the existing headache noun and separately named nausea, weakness or
    visual change are qualified here. Generic pain and every unclassified
    clinical noun retain the broad clinical floor, including possible aliases.
    Modifiers and embedded topics remain in the complete source comparison.
    """
    from . import v3_actors as a
    doc = reading.get('_ordinary_scope_docs', {}).get(unit['id'])
    if doc is None or doc.text != unit['quote']:
        return frozenset()
    found = set()
    for token in doc:
        word = a._lemma(token)
        classes = a.SOLE_CLASSES.get(word, frozenset()) | a.SOLE_WORD_CLASSES.get(word, frozenset())
        if not classes & a.SOLE_CLINICAL:
            continue
        if token.pos_ != 'NOUN':
            return frozenset()
        if word in ('headache', 'nausea', 'weakness'):
            if (any(child.dep_ in ('poss', 'appos') for child in token.children)
                    or any(child.dep_ == 'compound'
                           and any(a._lemma(part) not in ('tension', 'type')
                                   for part in child.subtree if not part.is_punct)
                           for child in token.children)
                    or any(child.dep_ == 'amod' and a._lemma(child) == 'visual' for child in token.children)):
                return frozenset()
            found.add(word)
        elif word == 'change':
            modifiers = [child for child in token.children if child.dep_ == 'amod']
            if (len(modifiers) != 1 or a._lemma(modifiers[0]) != 'visual'
                    or any(child.dep_ in ('compound', 'poss', 'appos') for child in token.children)):
                return frozenset()
            found.add('visual change')
        else:
            return frozenset()
    return frozenset(found)


def nominal_denial_atoms(reading, unit):
    """A whole current patient denial with only explicit nominal arguments.

    No subordinate event, double negation, temporal qualifier, foreign actor,
    generic object or missing argument can supply the bounded clinical proof.
    """
    from . import v3_actors as a
    uid = unit['id']; info = reading['actors'].get(uid, {}); sole = info.get('sole') or {}
    doc = reading.get('_ordinary_scope_docs', {}).get(uid)
    if (doc is None or doc.text != unit['quote'] or uid not in reading.get('sole_patient', ()) or not sole.get('current')
            or sole.get('unknown') or sole.get('uncertain') or not sole.get('negation_only')
            or sole.get('reach') != {'class'} or info.get('other_floor') or info.get('bounded')
            or info.get('past_time') or info.get('habitual') or info.get('intention')):
        return frozenset()
    root = next((t for t in doc if t.dep_ == 'ROOT'), None)
    if (root is None or root.pos_ != 'VERB' or a._lemma(root) != 'deny'
            or root.tag_ not in ('VBP', 'VBZ') or a._negates(root)):
        return frozenset()
    subjects = [t for t in root.children if t.dep_ == 'nsubj']
    objects = [t for t in root.children if t.dep_ in ('dobj', 'obj')]
    if len(subjects) != 1 or len(objects) != 1:
        return frozenset()
    subject = subjects[0]
    if (not (a.this_patient(subject) or a._fold(subject.text) in ('he', 'she'))
            or any(t.dep_ != 'det' for t in subject.children)):
        return frozenset()
    arguments = [objects[0], *objects[0].conjuncts]
    allowed = {root, subject} | set(subject.subtree)
    for argument in arguments:
        if argument.pos_ != 'NOUN':
            return frozenset()
        allowed.add(argument)
        for child in argument.children:
            if child in arguments:
                continue
            if child.dep_ == 'cc' and a._fold(child.text) in ('and', 'or'):
                allowed.add(child)
            elif child.dep_ == 'det' and a._fold(child.text) in ('any', 'the'):
                allowed.add(child)
            elif child.dep_ == 'amod' and a._lemma(argument) == 'change' and a._lemma(child) == 'visual':
                allowed.add(child)
            elif not child.is_punct:
                return frozenset()
    if any(t not in allowed and not t.is_punct for t in doc):
        return frozenset()
    return clinical_atoms(reading, unit)


def clinical_denial_apart(reading, denial, other, chosen=frozenset()):
    """The named denial and another clinical statement are provably distinct.

    The only qualified disjoint pairs are headache versus visual change,
    nausea or weakness. Association with a headache is not their equivalence;
    a source naming both topics, a general pain denial or a possible synonym
    gets no exception. Both sides of a clinical pair must be represented in
    the selected source: the complete denial and a statement with the exact
    other named topic. Otherwise a model's erroneous 'independent' relation
    could discard one half of the clinical history. Full relation, source
    ownership and every other floor remain necessary.
    """
    denied = nominal_denial_atoms(reading, denial)
    if not denied:
        return False
    info = reading['actors'].get(other['id'], {}); sole = info.get('sole') or {}
    role = reading.get('_ordinary_scoped_roles', {}).get(other['id'], {})
    # These source-owned properties already exclude a symptom-denial operator
    # when they are the answer. The same relationship applies when the complete
    # nominal denial is the answer: neither an intake nor a future care act
    # asserts that the named symptom exists, and two negative facts do not
    # contradict each other. Clinical themes/ending operators still refuse.
    if (sole and not sole.get('unknown') and not sole.get('reach')
            and not info.get('bare_cessation') and not info.get('ceased_keys')
            and (sole.get('classes') == {'medication'}
                 or role.get('normal_result') or role.get('follow_up')
                 or ((reading['parsed'].get(other['id']) or (None,))[0] == 'plan'
                     and sole.get('classes') <= {'medication', 'therapy', 'test', 'care'}))):
        return True
    if role.get('negative_allergy') and sole.get('classes') == {'allergy'}:
        return True
    stated = clinical_atoms(reading, other)
    if (not stated or denial['id'] not in chosen
            or not any(unit['id'] in chosen and clinical_atoms(reading, unit) == stated
                       for unit in reading['units'])):
        return False
    separate = frozenset({'visual change', 'nausea', 'weakness'})
    return all((left == 'headache' and right in separate)
               or (right == 'headache' and left in separate) for left in denied for right in stated)
