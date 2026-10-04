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
        if negative_allergy(oid) and not mine['reach'] and apart(oid, uid):
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
