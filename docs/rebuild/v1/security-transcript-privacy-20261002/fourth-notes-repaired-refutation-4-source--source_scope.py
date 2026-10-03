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
                    and ('class' in sole.get('reach',()) or any(t.dep_=='neg'
                        or (t.dep_=='det' and a._fold(t.text)=='no') for t in doc)))
                # A negated indefinite nominal predicate omits what it is
                # classifying ("No longer a daily medication"). Its clinical
                # class bounds the adjacent dependency; a direct independent
                # negative "No diabetes" has no indefinite predicate article.
                nominal_predicate=bool(not any(t.pos_ in ('VERB','AUX') for t in doc)
                    and a._negates(root)
                    and any(t.dep_=='det' and a._fold(t.text) in ('a','an') for t in root.children))
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
    def predicate_lemmas(root):
        heads=[root]+[t for t in root.children if t.dep_ in ('xcomp','ccomp','conj','compound')]
        # A nominal copular predicate can identify the actor of an action
        # ("the only one to take ..."). An incidental advcl/prepositional
        # clause ("is alone while taking ...") is not that predicate.
        for noun in (t for t in root.children if t.dep_ in ('attr','oprd') and t.pos_ in ('NOUN','PROPN','PRON','NUM')):
            heads.extend(t for t in noun.children if t.dep_ in ('acl','relcl','xcomp'))
        return {a._lemma(t) for t in heads if t.pos_ in ('VERB','AUX')}
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
        predicates=predicate_lemmas(root)
        heads=frozenset().union(frozenset(),*(p[0] for p in info.get('predicates',())))
        topic=info.get('claim_keys',frozenset())|info.get('named_keys',frozenset())
        for claim,claim_doc in zip(units,docs or [None]*len(units)):
            if claim['id']==other['id'] or claim_doc is None:continue
            mine=reading['actors'][claim['id']]
            if mine.get('other_floor'):continue
            my_roots=[t for t in claim_doc if t.dep_=='ROOT']
            my_predicates=predicate_lemmas(my_roots[0]) if len(my_roots)==1 else set()
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
            if ((predicates-{'be'}) & (my_predicates-{'be'}) or heads & my_heads
                    or same_assertion or nominal_reference) and topic & (
                    mine.get('claim_keys',frozenset())|mine.get('named_keys',frozenset())):
                causes.setdefault(claim['id'],[]).append(other)
    reading[key]=causes
    return causes
