"""A transition's explicit argument bounds the claim it can change.

Unknown endings and elided drug changes remain held. A complete positional
transition names a position; it supplies no evidence of changing medication.
This is one structural interpretation, not a list of verbs that release notes.
"""

def transition_scope(reading,unit):
    cache=reading.setdefault('_transition_scopes',{})
    if unit['id'] in cache:return cache[unit['id']]
    from . import v3_syntax,v3_actors as a
    docs=v3_syntax.docs([unit['quote']]);doc=docs[0] if docs else None
    answer=None
    if doc is not None:
        roots=[t for t in doc if t.dep_=='ROOT']
        if len(roots)==1:
            root=roots[0]
            subjects=[t for t in root.children if t.dep_ in ('nsubj','nsubjpass')]
            targets=[g for p in root.children if p.dep_=='prep' and a._fold(p.text)=='to'
                     for g in p.children if g.dep_=='pobj']
            verbs=[t for t in doc if t.pos_=='VERB']
            complete=bool(a._lemma(root) in ('switch','change') and len(verbs)==1 and len(targets)==1
                and all(a.this_patient(t) or a._fold(t.text) in ('he','she') for t in subjects)
                and not any(t.dep_ in ('dobj','obj','ccomp','xcomp','advcl','conj','neg') for t in root.children)
                and not any(t.dep_=='prep' and a._fold(t.text) in ('from','with','by','of','for') for t in doc)
                and not any(a.names_person(t) for t in targets[0].subtree)
                and not any(t.pos_ in ('PRON',) for t in targets[0].subtree))
            if complete:
                if (a._lemma(targets[0])=='position'
                        and any(t.dep_ in ('amod','compound') for t in targets[0].children)):
                    answer='position'
                else:
                    sole=reading['actors'][unit['id']].get('sole') or {}
                    # Existing positively typed nouns, rather than new drug-name
                    # matching or release keywords. Unknown topics stay global.
                    if (sole.get('classes')==frozenset({'medication'}) and not sole.get('unknown')
                            and 'global' not in sole.get('reach',())):
                        answer='medication'
    cache[unit['id']]=answer
    return answer

def bare_affects(reading,change,claim):
    """The affected treatment and claims depending on it stay held.

    A structurally complete change to a medication holds medication claims. A
    source statement that itself mentions a medication remains a dependency even
    when it answers another question. Only a positively known, separate topic
    avoids this additional floor; unknown claims and references remain held.
    """
    scope=transition_scope(reading,change)
    if scope is None:return True
    info=reading['actors'][claim['id']]
    if scope=='position':return bool(info.get('named_keys',frozenset()) & {'position','posit'})
    sole=info.get('sole') or {}
    classes=sole.get('classes',frozenset())
    if not classes or sole.get('unknown') or 'global' in sole.get('reach',()):return True
    return bool(classes & {'medication','therapy','test','care'})


def elliptical_dependencies(reading):
    """Hold the adjacent claim an incomplete predicate/modifier can change.

    A do/have/modal operator without its own predicate is verbal ellipsis:
    "Only her father does" cannot be independent of the omitted action. A
    topicless, positively read fragment such as "Not today"/"Except today",
    or an adpositional fragment such as "Not since Monday", likewise supplies
    no standalone predicate. An unknown date/object does not make its preceding
    claim independent. No inferred replacement value is
    adopted. Complete other-person clauses remain separate. These dependencies
    attach to the preceding nonfragment (or the following one at source start),
    rather than every field or the whole note.
    """
    key='_elliptical_dependencies'
    if key in reading:return reading[key]
    from . import v3_syntax,v3_actors as a
    units=reading['units'];docs=v3_syntax.docs(u['quote'] for u in units)
    reading['_source_scope_docs']=docs
    causes={};previous=[];leading=[];typed={}
    def affected(claim,modifier):
        classes=typed.get(modifier['id'],frozenset())
        mine=(reading['actors'][claim['id']].get('sole') or {}).get('classes',frozenset())
        return not classes or not mine or bool(classes & mine)
    for unit,doc in zip(units,docs or [None]*len(units)):
        uid=unit['id'];info=reading['actors'][uid];sole=info.get('sole') or {}
        fragment=False
        if doc is not None and not reading['parsed'].get(uid):
            roots=[t for t in doc if t.dep_=='ROOT']
            if len(roots)==1:
                root=roots[0];lemma=a._lemma(root)
                complements={'dobj','obj','ccomp','xcomp','attr','oprd'}
                if lemma=='be':complements=complements|{'prep','acomp'}
                operator=bool((lemma in ('do','have') or root.pos_=='AUX')
                    and not any(t.dep_ in complements for t in root.children))
                topicless=bool(not any(t.pos_ in ('VERB','AUX') for t in doc)
                    and not info.get('named_keys') and not sole.get('unknown'))
                adpositional=bool(root.pos_ in ('ADP','SCONJ')
                    and not any(t.pos_ in ('VERB','AUX') for t in doc))
                # A restriction without an established clinical noun may
                # qualify the preceding predicate even when an unknown word
                # was tagged as a noun ("No longer routine"). It does not
                # establish stopped/current/PRN status. Known clinical negatives
                # such as "No diabetes" remain their own claims.
                restriction=bool(not any(t.pos_ in ('VERB','AUX') for t in doc)
                    and not sole.get('classes') and not info.get('other_floor')
                    and (a._negates(root) or a._lemma(root) in a.SOLE_NEGATION))
                # A negated nominal predicate omits what it is
                # classifying ("No longer the daily medication"). Its clinical
                # class bounds the adjacent dependency; a direct independent
                # negative "No diabetes" has no separate predicate determiner.
                nominal_predicate=bool(not any(t.pos_ in ('VERB','AUX') for t in doc)
                    and a._negates(root)
                    and any(t.dep_=='neg' or (t.dep_=='advmod' and a._negates(t)) for t in root.children))
                if nominal_predicate:typed[uid]=sole.get('classes',frozenset())
                fragment=operator or topicless or adpositional or restriction or nominal_predicate
        if fragment:
            prior=next((u for u in reversed(previous) if affected(u,unit)),None)
            if prior is not None:causes.setdefault(prior['id'],[]).append(unit)
            else:leading.append(unit)
        else:
            if leading:
                causes.setdefault(uid,[]).extend(u for u in leading if affected(unit,u))
                leading=[u for u in leading if not affected(unit,u)]
            previous.append(unit)
    reading[key]=causes
    return causes


def exclusive_reattributions(reading):
    """An exclusive other actor can retract the same action/object claim.

    A restriction on the other actor or its predicate ("Only her father takes
    warfarin") differs from a restriction on its object ("Her father takes
    only warfarin"). Compare the predicate and named clinical claim, rather
    than holding every medication or every family statement. This only adds
    holds; it establishes no replacement subject, answer or positive value.
    """
    key='_exclusive_reattributions'
    if key in reading:return reading[key]
    from . import v3_syntax,v3_actors as a
    units=reading['units']
    docs=reading.get('_source_scope_docs')
    if docs is None:docs=v3_syntax.docs(u['quote'] for u in units)
    def predicate_nodes(root):
        heads=[root]+[t for t in root.children if t.dep_ in ('xcomp','ccomp','conj','compound')]
        # A nominal copular predicate can identify the actor of an action
        # ("the only one to take ..."). An incidental advcl/prepositional
        # clause ("is alone while taking ...") is not that predicate.
        for noun in (t for t in root.children if t.dep_ in ('attr','oprd') and t.pos_ in ('NOUN','PROPN','PRON','NUM')):
            heads.extend(t for t in noun.children if t.dep_ in ('acl','relcl','xcomp'))
        return [t for t in heads if t.pos_ in ('VERB','AUX')]
    def predicate_lemmas(root):
        return {a._lemma(t) for t in predicate_nodes(root)}
    def predicate_negations(root):
        # Negation on an actual action differs from negation of exclusive focus.
        # Prefer the lexical predicate to copular/auxiliary framing.
        nodes=[t for t in predicate_nodes(root) if a._lemma(t)!='be']
        if not nodes and a._lemma(root)=='be':
            # A negative relational preposition ('the only person without
            # warfarin') denies possession, rather than medication use by the
            # patient. This is the existing polarity vocabulary, not an actor
            # or medication whitelist.
            relations=[p for attr in root.children if attr.dep_ in ('attr','oprd')
                for p in attr.subtree if p.dep_=='prep' and a._fold(p.text) in a.SOLE_NEGATION]
            if relations:return {not a._negates(p) for p in relations}
        return {a._negates(t) for t in nodes or [root]}
    causes={}
    for other,doc in zip(units,docs or [None]*len(units)):
        info=reading['actors'][other['id']]
        if doc is None or not info.get('other_floor'):continue
        roots=[t for t in doc if t.dep_=='ROOT']
        if len(roots)!=1:continue
        root=roots[0]
        # Focus on an actor or predicate, excluding clinical object modifiers.
        # A restriction on a different action/object cannot retract this claim.
        focused=any((a._fold(t.text) in ('only','alone','solely','just')
                     or (a._fold(t.text)=='sole' and t.pos_=='ADJ' and t.dep_=='amod'))
            and (t.head.dep_ in ('nsubj','nsubjpass') or (t.head==root and a._fold(t.text)!='alone')
                 or (t.head.dep_=='attr' and a._lemma(root)=='be'))
            for t in doc)
        if not focused:continue
        # 'Not the only user' denies exclusivity; it does not exclude the
        # patient. An exclusive NEGATIVE action instead applies to negative
        # claims of that same action, never a positive patient assertion.
        nominal_focus=any(t.head.dep_=='attr' and (a._fold(t.text) in ('only','sole','solely','just')) for t in doc)
        if nominal_focus and a._negates(root):continue
        negations=predicate_negations(root)
        predicates=predicate_lemmas(root)
        heads=frozenset().union(frozenset(),*(p[0] for p in info.get('predicates',())))
        topic=info.get('claim_keys',frozenset())|info.get('named_keys',frozenset())
        for claim,claim_doc in zip(units,docs or [None]*len(units)):
            if claim['id']==other['id'] or claim_doc is None:continue
            mine=reading['actors'][claim['id']]
            if mine.get('other_floor'):continue
            if (mine.get('present_tense') and not mine.get('habitual') and not mine.get('past_time')
                    and (info.get('habitual') or (info.get('past_time') and not info.get('present_tense')))):
                continue
            my_roots=[t for t in claim_doc if t.dep_=='ROOT']
            my_predicates=predicate_lemmas(my_roots[0]) if len(my_roots)==1 else set()
            if len(my_roots)!=1 or not negations & predicate_negations(my_roots[0]):continue
            my_heads=frozenset().union(frozenset(),*(p[0] for p in mine.get('predicates',())))
            mine_sole=mine.get('sole') or {};other_sole=info.get('sole') or {}
            my_sides=mine_sole.get('sides',frozenset());other_sides=other_sole.get('sides',frozenset())
            if my_sides and other_sides and not my_sides & other_sides:continue
            # Existing light predicates can describe the same positively typed
            # clinical claim (reports/has cough). A distinct action such as
            # knows warfarin supplies no exclusive patient medication assertion.
            core_clauses=predicates-{'be'}
            nominal_action=bool(core_clauses and core_clauses<=a.LIGHT_VERBS)
            same_assertion=bool(a._lemma(root) in a.LIGHT_VERBS and my_predicates
                and my_predicates <= a.LIGHT_VERBS
                and (nominal_action or not (a._lemma(root)=='be'
                    and any(t.dep_ in ('acomp','attr') for t in root.children)))
                and mine_sole.get('classes',frozenset()) & other_sole.get('classes',frozenset()))
            # A copular nominal role/reference has no separate positive action
            # proving it independent (sole warfarin user / only patient on
            # warfarin). A same-named clinical claim remains reviewable rather
            # than inferring a relation. Distinct complete knowledge actions
            # and adjectival solitude/status retain their separate predicates.
            nominal_reference=bool(a._lemma(root)=='be' and not core_clauses
                and any(t.dep_=='attr' and t.pos_ in ('NOUN','PROPN','PRON','NUM') for t in root.children))
            # An anatomical modifier misread as a perfect lexical predicate
            # ('Only her father has left knee pain') cannot prove independence
            # of the same named clinical claim. Hold that unresolved relation;
            # do not silently reinterpret leave as a positive clinical verb.
            anatomical_parse=bool(root.pos_=='VERB' and a._fold(root.text) in a.SOLE_SIDES
                and any(t.dep_=='aux' and a._lemma(t) in a.LIGHT_VERBS for t in root.children)
                and mine_sole.get('classes',frozenset()) & other_sole.get('classes',frozenset()))
            if ((predicates-{'be'}) & (my_predicates-{'be'}) or heads & my_heads
                    or same_assertion or nominal_reference or anatomical_parse) and topic & (
                    mine.get('claim_keys',frozenset())|mine.get('named_keys',frozenset())):
                causes.setdefault(claim['id'],[]).append(other)
    reading[key]=causes
    return causes


def separate_sides(reading, first, second, shared):
    """Prove shared topic words belong to explicitly disjoint anatomical sides.

    Read each matching noun phrase locally, excluding coordinated clauses and
    sibling topics. A side elsewhere in a sentence cannot qualify another
    denial. Unknown, unqualified and mixed scope retains the existing hold.
    This affects only the lexical overlap floor; other dependencies still hold.
    """
    if not shared:return False
    from . import v3_syntax,v3_actors as a
    if '_source_scope_docs' not in reading:
        reading['_source_scope_docs']=v3_syntax.docs(u['quote'] for u in reading['units'])
    docs=reading['_source_scope_docs']
    if docs is None:return False
    def local_sides(token):
        phrase=negative_phrase_anchor(token, a)
        while phrase.dep_ in ('compound','amod') and phrase.head.pos_ in ('NOUN','PROPN'):
            phrase=phrase.head
        sides=set()
        for member in phrase.subtree:
            path=member
            while path!=phrase and path.head!=path:
                if path.dep_ in ('conj','advcl','ccomp','xcomp','relcl','acl'):break
                path=path.head
            if path!=phrase:continue
            side=a.SOLE_SIDES.get(a._fold(member.text))
            if side=='both':sides.update(('left','right'))
            elif side:sides.add(side)
        return sides
    def occurrences(unit):
        info=reading['actors'][unit['id']]
        if not info.get('readable') or info.get('other_floor'):return None
        doc=docs[reading['position'][unit['id']]]
        if doc is None:return None
        matched={key:[] for key in shared}
        for token in doc:
            if token.pos_ not in ('NOUN','PROPN') and not negative_clinical_modifiers(token,a):continue
            keys=a.keys({a._lemma(token),a._fold(token.text)}) & shared
            if keys:
                sides=local_sides(token)
                if len(sides)!=1:return None
                for key in keys:matched[key].append(sides)
        return matched if all(matched.values()) else None
    mine=occurrences(first);theirs=occurrences(second)
    return bool(mine and theirs and all(not l & r for key in shared for l in mine[key] for r in theirs[key]))



def malformed_denial_dependencies(reading):
    """A misattached explicit patient denial cannot erase its named object.

    The pinned parser sometimes reads 'patient denies left knee pain' as a
    past left/leave root, with the finite deny predicate as its subject. That
    unresolved finite predicate still denies a named clinical topic. Only its
    positively named topic holds; no parse or clinical value is repaired.
    """
    key='_malformed_denials'
    if key in reading:return reading[key]
    from . import v3_syntax,v3_actors as a
    docs=reading.get('_source_scope_docs')
    if docs is None:
        docs=v3_syntax.docs(u['quote'] for u in reading['units'])
        reading['_source_scope_docs']=docs
    found=[]
    for unit,doc in zip(reading['units'],docs or [None]*len(reading['units'])):
        info=reading['actors'][unit['id']]
        if doc is None or info.get('other_floor'):continue
        for token in doc:
            if (token.pos_=='VERB' and a._lemma(token) in a.SOLE_NEGATION
                    and token.dep_ in ('nsubj','nsubjpass') and token.head.pos_ in ('VERB','AUX')
                    and not a._negates(token)
                    and any(c.dep_ in ('nsubj','nsubjpass') and a.this_patient(c) for c in token.children)):
                topics=a.keys({a._lemma(t) for t in token.head.subtree
                    if t.pos_ in ('NOUN','PROPN') and a.SOLE_CLASSES.get(a._lemma(t),frozenset()) & a.SOLE_CLINICAL})
                if topics:found.append((unit,topics))
    reading[key]=found
    return found


def prefixed_modifier_dependencies(reading):
    """Unresolved reversing modifiers govern their own named noun phrase.

    Use the literal reader's existing written-prefix comparison, without deciding
    what that prefix means or equating swollen with swelling. A prefixed
    adjective on the same named anatomical/clinical object remains reviewable;
    an explicitly different source side can still prove a different object.
    """
    key='_prefixed_modifiers'
    if key in reading:return reading[key]
    from . import v3_syntax,v3_actors as a,v3_literal_facts as literal
    if '_source_scope_docs' not in reading:
        reading['_source_scope_docs']=v3_syntax.docs(u['quote']for u in reading['units'])
    found=[]
    for unit,doc in zip(reading['units'],reading['_source_scope_docs'] or [None]*len(reading['units'])):
        if doc is None or reading['actors'][unit['id']].get('other_floor'):continue
        for token in doc:
            if (token.pos_=='ADJ' and token.dep_=='amod' and token.head.pos_ in ('NOUN','PROPN')
                    and a._lemma(token.head) in a.SOLE_NOUNS
                    and literal._related(literal._surface(token),literal._singular(token.text.casefold()))=='prefixed'):
                found.append((unit,a.keys({a._lemma(token.head),a._fold(token.head.text)})))
    reading[key]=found
    return found


def pure_foreign_clause(reading,unit):
    """A complete single foreign actor, with no patient or embedded speaker.

    This proves only whose own claim this is. Mixed subjects, references to the
    patient and unresolved grammatical actors keep the previous conservative
    hold. Exclusive attribution is judged separately, including its polarity.
    """
    from . import v3_actors as a,v3_syntax
    info=reading['actors'][unit['id']]
    if not info.get('other_floor') or info.get('main_patient'):return False
    if '_source_scope_docs' not in reading:
        reading['_source_scope_docs']=v3_syntax.docs(u['quote']for u in reading['units'])
    docs=reading['_source_scope_docs']
    if docs is None:return False
    doc=docs[reading['position'][unit['id']]]
    roots=[t for t in doc if t.dep_=='ROOT']
    if len(roots)!=1:return False
    root=roots[0];subjects=[t for t in doc if t.dep_ in ('nsubj','nsubjpass','csubj','csubjpass','expl')]
    return bool(len(subjects)==1 and subjects[0].head==root and a.names_person(subjects[0])
        and root.pos_ in ('VERB','AUX') and not any(t.tag_=='MD' for t in doc)
        and not any(a.this_patient(t) or (t.pos_=='PRON' and t.dep_!='poss') for t in doc)
        and not any(t.dep_ in ('ccomp','xcomp','advcl','conj','relcl','acl') for t in doc))


def negative_clinical_modifiers(token,a):
    """Existing clinical word and a direct grammatical absence relation.

    The pinned parser can tag a nominal -ing argument as a verb. Its actual
    direct argument/modifier edge still supplies a hold; it supplies no positive
    assertion or repaired predicate. An embedded action (without treating pain)
    has no such direct edge to the clinical word.
    """
    classes=a.SOLE_CLASSES.get(a._lemma(token),frozenset()) | a.SOLE_CLASSES.get(a._fold(token.text),frozenset())
    if not classes & a.SOLE_CLINICAL:return []
    modifiers=[t for t in token.children if t.dep_ in ('amod','det') and a._lemma(t) in a.SOLE_NEGATION]
    if (token.dep_ in ('compound','npadvmod','acl') and token.head.pos_ in ('ADJ','NOUN')
            and a._lemma(token.head) in a.SOLE_NEGATION):modifiers.append(token.head)
    if token.dep_ in ('pobj','pcomp') and token.head.pos_=='ADP':
        prep=token.head
        if a._lemma(prep) in a.SOLE_NEGATION:modifiers.append(prep)
        elif prep.dep_=='prep' and prep.head.pos_=='ADJ' and a._lemma(prep.head) in a.SOLE_NEGATION:
            modifiers.append(prep.head)
    return modifiers


def negative_phrase_anchor(token,a):
    """The explicit anatomy in the SAME direct absence phrase, when unique.

    The parser attaches 'without pain' to 'has', beside its sole anatomical
    object. Only that positively typed single object can supply the side; a
    side in another topic, coordinate or clause cannot. Unknown attachment
    retains the existing hold.
    """
    if not negative_clinical_modifiers(token,a):return token
    body=frozenset(a.SOLE_LEXICON['body'].split())
    def anatomical(t):return t.pos_ in ('NOUN','PROPN') and bool({a._lemma(t),a._fold(t.text)} & body)
    head=token.head
    if head.pos_=='ADJ' and head.dep_=='amod' and anatomical(head.head):return head.head
    if token.dep_ in ('pobj','pcomp') and head.pos_=='ADP':
        parent=head.head
        if anatomical(parent):return parent
        if parent.pos_=='ADJ' and parent.dep_=='amod' and anatomical(parent.head):return parent.head
        if parent.pos_ in ('VERB','AUX') and a._lemma(parent) in a.LIGHT_VERBS:
            objects=[t for t in parent.children if t.dep_ in ('dobj','obj','attr') and anatomical(t)]
            if len(objects)==1 and not any(t.dep_ in ('conj','ccomp','xcomp','advcl','relcl','acl') for t in parent.subtree
                    if t!=token):return objects[0]
    return token


def clinical_modifier_negations(reading):
    """Polarity on a named clinical word, by its own modifier/relation scope.

    Existing negative words must directly modify that clinical argument: absent
    swelling, ankle without swelling, ankle free of swelling, swelling-free
    ankle. An intervening predicate (without treating pain) does not deny pain.
    Negation of that modifier remains unresolved rather than declaring a
    positive value. No source text or clinical claim is added.
    """
    key='_clinical_modifier_negations'
    if key in reading:return reading[key]
    from . import v3_syntax,v3_actors as a
    if '_source_scope_docs' not in reading:
        reading['_source_scope_docs']=v3_syntax.docs(u['quote']for u in reading['units'])
    result={}
    for unit,doc in zip(reading['units'],reading['_source_scope_docs'] or [None]*len(reading['units'])):
        if doc is None:continue
        targets=set();ambiguous=set()
        for noun in doc:
            modifiers=negative_clinical_modifiers(noun,a)
            if modifiers:
                keys=a.keys({a._lemma(noun),a._fold(noun.text)})
                spine=[noun,*noun.ancestors]
                cancelled=any(a._negates(t) for t in modifiers) or any(
                    c.dep_=='neg' for t in spine for c in t.children)
                if cancelled:ambiguous |= keys
                else:targets |= keys
        if targets or ambiguous:result[unit['id']]={'negative':frozenset(targets),'ambiguous':frozenset(ambiguous)}
    reading[key]=result
    return result
