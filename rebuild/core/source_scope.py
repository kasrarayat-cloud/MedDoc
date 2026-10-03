"""A transition's explicit argument bounds the claim it can change.

Unknown endings and elided drug changes remain held. A complete positional
transition names a position; it supplies no evidence of changing medication.
This is one structural interpretation, not a list of verbs that release notes.
"""

def transition_scope(reading,unit,*,clause=None):
    cache=reading.setdefault('_transition_scopes',{})
    if clause is None and unit['id'] in cache:return cache[unit['id']]
    from . import v3_syntax,v3_actors as a
    docs=v3_syntax.docs([unit['quote']]) if clause is None else None
    doc=(docs[0] if docs else None) if clause is None else clause
    inside=set(doc) if doc is not None else set()
    answer=None
    if doc is not None:
        roots=[t for t in doc if t.dep_=='ROOT' or t.head not in inside]
        if len(roots)==1:
            root=roots[0]
            children=[t for t in root.children if t in inside]
            subjects=[t for t in children if t.dep_ in ('nsubj','nsubjpass')]
            targets=[g for p in children if p.dep_=='prep' and a._fold(p.text)=='to'
                     for g in p.children if g in inside and g.dep_=='pobj']
            verbs=[t for t in doc if t.pos_=='VERB']
            def test_purpose(prep):
                objects=[t for t in prep.children if t in inside and t.dep_=='pobj']
                return bool(a._lemma(prep)=='for' and len(objects)==1
                    and objects[0].text.isupper() and a._fold(objects[0].text) in a.SOLE_INITIALISMS
                    and all(t==objects[0] or t.pos_ in ('DET','PUNCT') for t in objects[0].subtree if t in inside))
            purposes={p for p in doc if p.dep_=='prep' and test_purpose(p)}
            def position_argument(token,excluded=()):
                # The explicit position noun includes its grammatical noun
                # nominalization. No orientation-word whitelist supplies it.
                word=a._lemma(token)
                named=token.pos_=='NOUN' and (word=='position' or (word.endswith('ing') and word[:-3]=='position'))
                purpose_words={t for p in purposes if p.head==token for t in p.subtree}
                members=[t for t in token.subtree if t in inside and t not in excluded and t not in purpose_words]
                return bool(named and any(t.dep_ in ('amod','compound') and t.pos_=='ADJ' for t in members)
                    and all(t==token or t.pos_ in ('ADJ','ADV','DET','PUNCT') for t in members)
                    and not any(a.SOLE_CLASSES.get(a._lemma(t),frozenset()) for t in members))
            sources=[p for p in children if p.dep_=='prep' and a._lemma(p)=='from']
            positional_targets=[(p,g) for p in doc if p.dep_=='prep' and a._lemma(p)=='to'
                for g in p.children if g.dep_=='pobj' and position_argument(g)]
            positional=bool(not sources and len(positional_targets)==1 and positional_targets[0][0].head==root)
            if len(sources)==1 and len(positional_targets)==1:
                source=sources[0];target_prep,target=positional_targets[0]
                objects=[t for t in source.children if t in inside and t.dep_=='pobj']
                adjectival=[t for t in source.subtree if t in inside and t not in set(target_prep.subtree)]
                adjective_source=bool(not objects and any(t.pos_=='ADJ' for t in adjectival)
                    and all(t==source or t.pos_ in ('ADJ','ADV','PUNCT') for t in adjectival)
                    and not any(a.SOLE_CLASSES.get(a._lemma(t),frozenset())
                        or a._fold(t.text) in a.SOLE_UNCERTAIN for t in adjectival))
                noun_source=bool(len(objects)==1 and position_argument(objects[0],set(target_prep.subtree)))
                positional=bool((adjective_source or noun_source)
                    and (target_prep.head==root or (adjective_source and target_prep.head==source)
                         or (noun_source and target_prep.head==objects[0])))
            if (positional and a._lemma(root) in ('switch','change') and len(verbs)==1
                    and all(a.this_patient(t) or a.names_person(t) or a._fold(t.text) in ('he','she') for t in subjects)
                    and not any(t.dep_ in ('dobj','obj','ccomp','xcomp','advcl','conj','neg') for t in children)
                    and not any(t.dep_=='prep' and a._fold(t.text) in ('with','by','of','for') and t not in purposes for t in doc)):
                answer='position'
            complete=bool(a._lemma(root) in ('switch','change') and len(verbs)==1 and len(targets)==1
                and all(a.this_patient(t) or a._fold(t.text) in ('he','she') for t in subjects)
                and not any(t.dep_ in ('dobj','obj','ccomp','xcomp','advcl','conj','neg') for t in children)
                and not any(t.dep_=='prep' and a._fold(t.text) in ('from','with','by','of','for') for t in doc)
                and not any(a.names_person(t) for t in targets[0].subtree)
                and not any(t.pos_ in ('PRON',) for t in targets[0].subtree))
            if complete and answer is None:
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
    if clause is None:cache[unit['id']]=answer
    return answer

def bare_affects(reading,change,claim):
    """The affected treatment and claims depending on it stay held.

    A structurally complete change to a medication holds medication claims. A
    source statement that itself mentions a medication remains a dependency even
    when it answers another question. Only a positively known, separate topic
    avoids this additional floor; unknown claims and references remain held.
    """
    scope=transition_scope(reading,change)
    if scope is None:
        clauses=clause_readings(reading,change)
        # The entire sole clause has an explicit foreign subject and no
        # unresolved pronoun/patient branch. No patient action is inherited.
        if len(clauses)==1 and clauses[0]['foreign']:return False
        bounded=bounded_mixed_endings(reading,change)
        if bounded is None:return True
        return any(ending_affects(reading,ending,claim) for ending in bounded)
    info=reading['actors'][claim['id']]
    if scope=='position':return bool(info.get('named_keys',frozenset()) & {'position','posit'})
    return medication_affects(reading,claim)


def medication_affects(reading,claim):
    """An unresolved medication event governs its claim and actual dependencies."""
    info=reading['actors'][claim['id']]
    sole=info.get('sole') or {}
    classes=sole.get('classes',frozenset())
    if not classes or sole.get('unknown') or 'global' in sole.get('reach',()):return True
    return bool(classes & {'medication','therapy','test','care'})


def nominal_carrier(token):
    """The pinned parser's nominal reporting head still owns a finite clause."""
    from . import v3_actors as a
    return bool(token.pos_=='NOUN' and token.dep_=='conj' and a._lemma(token) in a.LIGHT_VERBS
        and any(c.dep_=='acl' and c.pos_ in ('VERB','AUX')
            and any(s.dep_ in ('nsubj','nsubjpass') for s in c.children)
            and any(m.dep_=='mark' and a._fold(m.text)=='that' for m in c.children) for c in token.children))


def detached_passive_theme(predicate):
    """Bind the pinned parser's adjacent nominal/passive coordination.

    The exact named medication sits immediately before its passive auxiliary,
    although the parser attached it to the preceding nominal conjunction. This
    accounts for the same source token in both clauses; it supplies no actor.
    Unknown objects, alternatives and nonadjacent clauses cannot use this proof.
    """
    from . import v3_actors as a
    auxiliaries=[t for t in predicate.children if t.dep_=='auxpass']
    if (predicate.pos_!='VERB' or predicate.tag_!='VBN' or predicate.dep_ not in ('conj','advcl')
            or len(auxiliaries)!=1 or predicate.head.pos_ not in ('VERB','AUX')
            or any(t.dep_ in ('nsubj','nsubjpass','dobj','obj','mark') for t in predicate.children)):
        return None
    first=auxiliaries[0]
    if first.i<2:return None
    theme=predicate.doc[first.i-1]
    # Recover the entire adjacent nominal group, rather than the last drug.
    # Every member must be a named medication and every join explicit AND;
    # an alternative, unknown item or incomplete group retains the old hold.
    while theme.dep_=='conj' and theme.head.pos_ in ('NOUN','PROPN') and 'medication' in a.SOLE_CLASSES.get(a._lemma(theme.head),()):
        theme=theme.head
    if theme.i<1:return None
    join=predicate.doc[theme.i-1];members=list(theme.subtree)
    if (theme.pos_ not in ('NOUN','PROPN') or theme.dep_!='conj'
            or 'medication' not in a.SOLE_CLASSES.get(a._lemma(theme),())
            or theme.head.pos_!='NOUN' or theme.head not in set(predicate.head.subtree)
            or a._lemma(theme.head) not in ('position','positioning')
            or join.dep_!='cc' or join.head!=theme.head or a._fold(join.text)!='and'
            or a._lemma(theme) in a.DOSAGE_FORM_NOUNS
            or {t.i for t in members}!=set(range(theme.i,first.i))
            or any(t!=theme and t.dep_ not in ('det','compound','amod','poss','conj','cc') for t in members)
            or any(t.dep_=='cc' and a._fold(t.text)!='and' for t in members)
            or any(t.dep_=='conj' and a._lemma(t) in a.DOSAGE_FORM_NOUNS for t in members)
            or any(t.pos_ in ('NOUN','PROPN') and 'medication' not in a.SOLE_CLASSES.get(a._lemma(t),()) for t in members)
            or any(t.dep_=='conj' and t.pos_ not in ('NOUN','PROPN') for t in members)):
        return None
    return theme


def owned_clause(predicate):
    """A grammatical clause excludes separately owned coordinated assertions."""
    excluded=set()
    for token in predicate.subtree:
        if token==predicate:continue
        active=detached_active_theme(token)
        if active is not None:
            excluded.update(active.subtree)
            excluded.add(token.doc[token.i-1])
            continue
        if (nominal_carrier(token) or (token.pos_ in ('VERB','AUX') and token.dep_ in ('conj','ccomp','advcl','relcl','acl','parataxis'))
                or (token.dep_ in ('xcomp','pcomp') and any(c.dep_ in ('nsubj','nsubjpass') for c in token.children))):
            excluded.update(token.subtree)
            theme=detached_passive_theme(token)
            if theme is not None:
                excluded.update(theme.subtree)
                excluded.update(c for c in theme.head.children if c.dep_=='cc' and c.i==theme.i-1)
            if token.dep_=='conj':
                excluded.update(c for c in token.head.children if c.dep_=='cc')
    own=set(predicate.subtree)-excluded
    theme=detached_passive_theme(predicate)
    if theme is not None:own.update(theme.subtree)
    active=detached_active_theme(predicate)
    if active is not None:own.update(active.subtree)
    return sorted(own,key=lambda t:t.i)


def detached_active_theme(predicate):
    """Recover one adjacent active ending misattached as a nominal modifier.

    In explicit AND coordination after a position noun, a past ending directly
    precedes its sole named medication. No passive, alternative, possession,
    list member or unknown argument is recovered by this proof.
    """
    from . import v3_actors as a
    if (predicate.pos_!='VERB' or predicate.tag_ not in ('VBD','VBN') or predicate.dep_!='amod'
            or a._lemma(predicate) not in a.CESSATION_VERBS | a.SUPERSESSION_VERBS or predicate.i<1):return None
    theme=predicate.head;join=predicate.doc[predicate.i-1]
    if (theme.pos_ not in ('NOUN','PROPN') or theme.dep_!='conj' or theme.i!=predicate.i+1
            or 'medication' not in a.SOLE_CLASSES.get(a._lemma(theme),()) or a._lemma(theme) in a.DOSAGE_FORM_NOUNS
            or theme.head.pos_!='NOUN' or a._lemma(theme.head) not in ('position','positioning')
            or join.dep_!='cc' or join.head!=theme.head or a._fold(join.text)!='and'
            or any(t!=predicate and t.dep_ not in ('det','compound','amod') for t in theme.children)
            or any(t.dep_ in ('nsubj','nsubjpass','auxpass','dobj','obj','mark','neg','conj') for t in predicate.children)):
        return None
    return theme


def denied_ending(predicate, words):
    """A canonical denial owns one subjectless completed ending.

    Denying stopping does not deny taking. Extra negation, a modal, another
    argument or an unknown ended value cannot establish this narrow scope.
    This grants no current medication status or replacement answer.
    """
    from . import v3_actors as a
    inside=set(words)
    children=[t for t in predicate.children if t in inside]
    endings=[t for t in children if t.dep_=='xcomp' and t.pos_=='VERB'
        and a._lemma(t) in a.CESSATION_VERBS | a.SUPERSESSION_VERBS]
    subjects=[t for t in children if t.dep_ in ('nsubj','nsubjpass')]
    if (a._lemma(predicate)!='deny' or a._negates(predicate) or len(endings)!=1
            or len(subjects)!=1 or not a.this_patient(subjects[0])):return False
    ending=endings[0]
    arguments=[t for t in ending.children if t in inside and (t.dep_ in ('dobj','obj')
        or (t.dep_=='xcomp' and t.pos_ in ('NOUN','PROPN')))]
    if (len(arguments)!=1 or not a.keys({a._lemma(arguments[0])})
            or 'medication' not in a.SOLE_CLASSES.get(a._lemma(arguments[0]),())
            or a._lemma(arguments[0]) in a.DOSAGE_FORM_NOUNS):return False
    if any(a._negates(t) or t.tag_=='MD' for t in words):return False
    if any(t.pos_=='VERB' and t not in (predicate,ending) for t in words):return False
    permitted=set(subjects[0].subtree)|set(ending.subtree)|{predicate}
    return bool(all(t in permitted or t.is_punct for t in words)
        and not any(t.dep_ in ('nsubj','nsubjpass','csubj','csubjpass','ccomp','conj','relcl','acl')
            for t in ending.subtree if t in inside)
        and all({a._lemma(t),a._fold(t.text)} & a._SOLE_KNOWN
            for t in arguments[0].subtree if t in inside and t.pos_ in a.CONTENT))


def replacement_relation(predicate, words):
    """Read the old argument of an explicit grammatical replacement relation.

    IN PLACE OF attaches the former value to its OF argument, irrespective of
    which verb describes introducing the replacement. The passive medication
    theme and an explicit FOR recipient belong to this event; a requester or
    another clause cannot supply that recipient. This only adds review holds.
    It never establishes that the replacement is a current medication.
    """
    from . import v3_actors as a
    inside=set(words)
    if predicate.pos_ not in ('VERB','AUX'):return None
    themes=[t for t in predicate.children if t in inside and t.dep_ in ('nsubjpass','dobj','obj')]
    prepositions=[p for p in words if p.dep_=='prep' and a._lemma(p)=='in'
        and (p.head==predicate or p.head in themes)]
    arguments=[]
    for prep in prepositions:
        places=[t for t in prep.children if t in inside and t.dep_=='pobj'
            and t.pos_=='NOUN' and a._lemma(t)=='place']
        for place in places:
            if any(t.dep_ not in ('prep','det') for t in place.children if t in inside):continue
            for former in place.children:
                if former in inside and former.dep_=='prep' and a._lemma(former)=='of':
                    arguments.extend(t for t in former.children if t in inside and t.dep_=='pobj'
                        and 'medication' in a.SOLE_CLASSES.get(a._lemma(t),()))
    if not arguments:return None
    topics=a.keys({a._lemma(t) for argument in arguments for t in argument.subtree
        if t in inside and t.pos_ in a.CONTENT})-a.keys({'patient'})
    generic=any(a._lemma(argument) in a.DOSAGE_FORM_NOUNS for argument in arguments)
    owned=any(c.dep_=='poss' and a.this_patient(c) for argument in arguments+themes for c in argument.children)
    subjects=[t for t in predicate.children if t in inside and t.dep_=='nsubj']
    direct=bool(len(subjects)==1 and a.this_patient(subjects[0]))
    recipients=[t for prep in predicate.children if prep in inside and prep.dep_=='prep' and a._lemma(prep)=='for'
        for t in prep.children if t in inside and t.dep_=='pobj']
    recipient=recipients[0] if len(recipients)==1 else None
    patient=bool(direct or owned or (recipient is not None and a.this_patient(recipient)))
    foreign=bool(recipient is not None and a.names_person(recipient) and not patient
        and not any(t.dep_=='conj' or a.this_patient(t)
            or (t.pos_=='PRON' and (t.dep_!='poss' or not a.names_person(t.head)))
            for t in recipient.subtree))
    # Canonical event negation precedes its predicate. A trailing "not merely
    # proposed" or focus modifier cannot negate a completed introduction.
    negative=[t for t in predicate.children if t in inside and t.dep_=='neg']
    auxiliaries=[t for t in predicate.children if t in inside and t.dep_ in ('aux','auxpass')]
    negated=bool(len(negative)==1 and negative[0].i<predicate.i
        and all(t==negative[0] or t.pos_ in ('AUX','PART') for t in words
            if min([negative[0].i]+[t.i for t in auxiliaries])<=t.i<predicate.i))
    modal=bool(any(t.tag_=='MD' for t in auxiliaries)
        and not any(a._lemma(t)=='have' for t in auxiliaries))
    return {'topics':topics,'generic':generic,'patient':patient,'foreign':foreign,'cancelled':negated or modal}


def future_event_at(reading,unit,start,end):
    """A future modal governs this event, not a completed neighbouring claim.

    Only one explicit patient event with a named medication and a positively
    future temporal argument is proved. Perfect modals, reporting clauses,
    conditions and additional actors retain the inherited uncertainty floor.
    """
    from . import v3_syntax,v3_actors as a
    docs=v3_syntax.docs([unit['quote']]);doc=docs[0] if docs else None
    if doc is None:return False
    roots=[t for t in doc if t.dep_=='ROOT'];verbs=[t for t in doc if t.pos_=='VERB']
    if len(roots)!=1 or verbs!=roots:return False
    root=roots[0];children=list(root.children)
    subjects=[t for t in children if t.dep_=='nsubj']
    modals=[t for t in children if t.dep_=='aux' and t.tag_=='MD']
    arguments=[t for t in children if t.dep_ in ('dobj','obj')]
    if (a._lemma(root) not in a.CESSATION_VERBS or len(subjects)!=1 or not a.this_patient(subjects[0])
            or len(modals)!=1 or unit['start']+modals[0].idx!=start
            or start+len(modals[0].text)!=end or len(arguments)!=1
            or 'medication' not in a.SOLE_CLASSES.get(a._lemma(arguments[0]),())
            or a._lemma(arguments[0]) in a.DOSAGE_FORM_NOUNS
            or any(t.dep_ in ('neg','mark','ccomp','xcomp','advcl','conj') for t in children)
            or any(a._lemma(t)=='have' for t in children if t.pos_=='AUX')):return False
    temporals=[t for t in children if t.dep_=='prep' and a._lemma(t)=='after']
    if len(temporals)!=1:return False
    objects=[t for t in temporals[0].children if t.dep_=='pobj']
    if len(objects)!=1 or not a.SOLE_CLASSES.get(a._lemma(objects[0]),()):return False
    future=[t for t in objects[0].subtree if t.dep_=='poss' and a._lemma(t) in a.SOLE_TIME_WORDS
        and any(c.dep_=='amod' and a._lemma(c)=='next' for c in t.children)]
    if len(future)!=1:return False
    allowed=set(subjects[0].subtree)|set(arguments[0].subtree)|set(temporals[0].subtree)|{root,modals[0]}
    return bool(all(t in allowed or t.is_punct for t in doc)
        and not any(t.pos_=='PRON' or a.names_person(t) for t in temporals[0].subtree)
        and all({a._lemma(t),a._fold(t.text)} & a._SOLE_KNOWN or t in future
            for t in arguments[0].subtree if t.pos_ in a.CONTENT))


def continued_medication(predicate,words):
    """Bound a complete present continuation's dependency to medication.

    This does not resolve its pronoun or adopt an answer. It only prevents a
    separate positional clause from changing an unrelated examination.
    """
    from . import v3_actors as a
    children=[t for t in predicate.children if t in words]
    subjects=[t for t in children if t.dep_=='nsubj']
    objects=[t for t in children if t.dep_ in ('dobj','obj')]
    if (a._lemma(predicate)!='continue' or predicate.tag_ not in ('VBP','VBZ')
            or len(subjects)!=1 or not (a.this_patient(subjects[0]) or a._fold(subjects[0].text) in ('he','she'))
            or len(objects)!=1 or 'medication' not in a.SOLE_CLASSES.get(a._lemma(objects[0]),())
            or a._lemma(objects[0]) in a.DOSAGE_FORM_NOUNS
            or any(t.dep_ in ('neg','aux','auxpass','mark','prep','advcl','conj','xcomp') for t in children)):return False
    allowed=set(subjects[0].subtree)|set(objects[0].subtree)|{predicate}
    return bool(all(t in allowed or t.is_punct for t in words)
        and all({a._lemma(t),a._fold(t.text)} & a._SOLE_KNOWN for t in objects[0].subtree if t.pos_ in a.CONTENT))


def resumed_current(reading,claim,ended):
    """A completed restart plus explicit present use supersedes a dated stop.

    Source order alone is insufficient. The exact same named medication must
    be the sole argument of an explicit patient's completed restart and current
    taking clause. Nothing here releases a later stop or an intended restart.
    """
    from . import v3_syntax,v3_actors as a
    old=reading['actors'][ended['id']]
    if (ended['end']>=claim['start'] or not old['past_time'] or not old['finite_past']
            or old['present_tense'] or old['other_floor']):return False
    docs=v3_syntax.docs([claim['quote']]);doc=docs[0] if docs else None
    if doc is None:return False
    roots=[t for t in doc if t.dep_=='ROOT']
    if len(roots)!=1:return False
    root=roots[0];children=list(root.children)
    subjects=[t for t in children if t.dep_=='nsubj']
    objects=[t for t in children if t.dep_ in ('dobj','obj')]
    auxiliaries=[t for t in children if t.dep_=='aux']
    current=[t for t in children if t.dep_=='conj' and t.pos_=='VERB']
    if (a._lemma(root)!='restart' or root.tag_!='VBN' or len(subjects)!=1 or not a.this_patient(subjects[0])
            or len(auxiliaries)!=1 or a._lemma(auxiliaries[0])!='have' or auxiliaries[0].tag_ not in ('VBP','VBZ')
            or len(objects)!=1 or 'medication' not in a.SOLE_CLASSES.get(a._lemma(objects[0]),())
            or a._lemma(objects[0]) in a.DOSAGE_FORM_NOUNS or len(current)!=1
            or len([t for t in doc if t.pos_=='VERB'])!=2 or any(a._negates(t) or t.tag_=='MD' for t in doc)):return False
    take=current[0];arguments=[t for t in take.children if t.dep_ in ('dobj','obj')]
    if (a._lemma(take)!='take' or take.tag_ not in ('VBP','VBZ') or len(arguments)!=1
            or not (a._fold(arguments[0].text)=='it' or a._lemma(arguments[0])==a._lemma(objects[0]))
            or not any(t.dep_=='advmod' and a._lemma(t)=='now' for t in take.children)
            or any(t.dep_ in ('nsubj','nsubjpass','prep','aux','neg','conj','advcl','ccomp','xcomp') for t in take.children)
            or not any(t.dep_=='cc' and a._fold(t.text)=='and' for t in children)):return False
    allowed=set(subjects[0].subtree)|set(objects[0].subtree)|set(take.subtree)|{root,auxiliaries[0]}
    if any(t not in allowed and not t.is_punct and t.dep_!='cc' for t in doc):return False
    key=a.keys({a._lemma(objects[0])})
    # The pronoun has exactly one medication antecedent. An added medication,
    # recipient or embedded event cannot borrow this present-taking proof.
    if any(t!=objects[0] and (t.dep_ in ('prep','poss','conj','acl','relcl')
            or ('medication' in a.SOLE_CLASSES.get(a._lemma(t),())
                and not (t.dep_=='npadvmod' and any(c.dep_=='nummod' and c.pos_=='NUM' for c in t.children))))
            for t in objects[0].subtree):return False
    endings=clause_readings(reading,ended)
    if len(endings)!=1:return False
    earlier=endings[0];predicate=earlier['predicate'];children=list(predicate.children)
    themes=[t for t in children if t.dep_=='nsubjpass']
    dates=[t for t in children if t.dep_=='npadvmod' and a._lemma(t) in a.SOLE_FREQUENCY_NOUNS
        and any(c.dep_=='amod' and a._lemma(c)=='last' for c in t.children)]
    if (a._lemma(predicate) not in a.CESSATION_VERBS or earlier['cancelled'] or len(themes)!=1
            or a._lemma(themes[0])!=a._lemma(objects[0]) or len(dates)!=1
            or any(t.pos_=='VERB' and t!=predicate for t in earlier['words'])):return False
    dated_words=set(themes[0].subtree)|set(dates[0].subtree)|{predicate}
    if any(t not in dated_words and not t.is_punct and t.dep_!='auxpass' for t in earlier['words']):return False
    return bool(old['ceased_keys'] and old['ceased_keys']<=key
        and all({a._lemma(t),a._fold(t.text)} & a._SOLE_KNOWN for t in objects[0].subtree if t.pos_ in a.CONTENT))


def completed_receipt_question(field):
    """A grammatical past receipt asks about that event, not a current signer.

    This only bounds the dated-past floor. Role protection, selected-source
    identity, attribution, contradictions and model relation guards still apply.
    """
    from . import v3_syntax,v3_actors as a,generation as g
    if g.V3_NOW_QUESTION.search(str(field.get('label')or'')+' '+str(field.get('context')or'')):return False
    docs=v3_syntax.docs([str(field.get('label')or'')]);doc=docs[0] if docs else None
    if doc is None:return False
    roots=[t for t in doc if t.dep_=='ROOT']
    if len(roots)!=1:return False
    root=roots[0];children=list(root.children)
    subjects=[t for t in children if t.dep_ in ('nsubj','nsubjpass')]
    past=bool(root.tag_=='VBD' or any(t.dep_=='auxpass' and t.tag_=='VBD' for t in children))
    # A form caption can omit BE from its passive: "Signed consent
    # received on". The pinned parser then gives RECEIVE VBN and CONSENT
    # nsubj. A single nonhuman nominal theme and no auxiliary establish this
    # reduced passive; an infinitive, intention, actor or qualified/embedded
    # clause cannot borrow it. Source identity and context still govern below.
    elliptical=bool(root.tag_=='VBN' and len(subjects)==1 and subjects[0].dep_=='nsubj'
        and not any(t.pos_=='AUX' or a.names_carer(t) or t.pos_=='PROPN'
            or a._fold(t.text) in a.SOLE_UNCERTAIN or a._lemma(t) in a.INTENTION_WORDS for t in doc)
        and all(t==subjects[0] or t.dep_ in ('det','compound','amod')
            for t in subjects[0].subtree)
        and all(t.pos_ in ('NOUN','DET') or (t.dep_=='amod' and t.tag_=='VBN')
            for t in subjects[0].subtree))
    return bool(a._lemma(root)=='receive' and (past or elliptical) and len(subjects)==1
        and subjects[0].pos_=='NOUN' and subjects[0].i<root.i
        and not any(a.names_person(t) or a.this_patient(t) or t.pos_=='PRON' or t.tag_=='MD' or a._negates(t) for t in doc)
        and all(t==root or t.pos_!='VERB' or (t.dep_=='amod' and t.head in set(subjects[0].subtree)) for t in doc)
        and all(t.dep_ in ('nsubj','nsubjpass','auxpass','punct')
            or (t.dep_=='prep' and a._lemma(t)=='on' and not list(t.children)) for t in children))


def receipt_date_warnings(reading, field, selected):
    """A completed receipt's own labelled ON value must actually name a date.

    The printed reduced/passive clause supplies the event; a literal calendar
    date supplies only its time. A future, uncertain, negative or arbitrary
    labelled value cannot manufacture that completed event. Preserve the
    exact original answer bytes; this parser never rewrites ambiguous US/UK
    numeric dates. Non-date receipt questions and planned receipt questions
    keep their existing source guards.
    """
    from datetime import datetime
    from . import v3_syntax, generation as g
    if not completed_receipt_question(field):return []
    docs=v3_syntax.docs([str(field.get('label')or'')]);doc=docs[0] if docs else None
    if doc is None:return list(selected)
    roots=[t for t in doc if t.dep_=='ROOT']
    if len(roots)!=1 or not any(t.dep_=='prep' and t.text.casefold()=='on'
            for t in roots[0].children):return []
    def calendar_date(value):
        value=value.strip().rstrip('.')
        # These source-relative day names require no invented encounter date.
        # Future relative dates do not describe a completed receipt.
        if value.casefold() in ('today','yesterday'):return True
        # A successful parse must consume the whole value. Parsing proves
        # calendar validity, never whose receipt it is or a clinical event.
        for fmt in ('%Y-%m-%d','%m/%d/%Y','%d/%m/%Y','%d %B %Y','%d %b %Y',
                    '%B %d, %Y','%b %d, %Y','%B %d %Y','%b %d %Y'):
            try:datetime.strptime(value,fmt);return True
            except ValueError:pass
        return False
    key=g.question_key(field.get('label'))
    return [unit for unit in selected if (own:=reading['parsed'].get(unit['id']))
        and own[0]==key and not calendar_date(own[1])]


def reserved_identity_source(reading, source, claim, field):
    """A protected area's exact labelled human name is metadata for that area.

    It supplies no actor to a separately labelled clinical answer. A clinical
    statement, pronoun, correction, unknown label or unprotected source cannot
    use this boundary. The caller still requires a valid complete-source
    relation and keeps every other actor, contradiction and context floor.
    """
    from . import v3_syntax, v3_actors as a, generation as g
    own=reading['parsed'].get(source['id']);answer=reading['parsed'].get(claim['id'])
    if not own or not own[1] or not answer or field is None or answer[0]!=g.question_key(field['label']):return False
    if not reading['colon'].get(source['id']) or not reading['colon'].get(claim['id']):return False
    matches=[f for f in reading.get('catalogue',()) if g.question_key(f.get('label'))==own[0]]
    if len(matches)!=1:return False
    protected=matches[0]
    if (protected['key']==field['key'] or (not protected.get('write_protected')
            and protected.get('kind') not in ('signature','initials'))
            or (protected.get('locator')or{}).get('contract')!='v3'):return False
    if any(pattern.search(own[1]) for pattern in (g.SELF_CORRECTION,g.INHERITED_SCOPE,g.UNSETTLED,g.SCOPE_POINTER,g.DENIAL)):
        return False
    docs=v3_syntax.docs([own[1]]);doc=docs[0] if docs else None
    if doc is None:return False
    roots=[t for t in doc if t.dep_=='ROOT']
    if len(roots)!=1 or roots[0].pos_ not in ('NOUN','PROPN'):return False
    if any(t.pos_ not in ('NOUN','PROPN') and not (t.is_punct and t.text=='.') for t in doc):return False
    if any(a.SOLE_CLASSES.get(a._lemma(t),()) or a._negates(t) for t in doc):return False
    return bool(a.names_person(roots[0]) or a.names_carer(roots[0])
        or any(a._fold(t.text).rstrip('.') in a.TITLES | a.CARE_TITLES for t in doc))


def clause_readings(reading,unit):
    """Keep each finite clause's actor and ended argument together.

    The main actor cannot erase a second explicit patient's cessation. Equally,
    a different named ended medication must not turn an independent positional
    clause into a note-wide unidentified cessation. This reads existing ending
    operators; it supplies no actor to an elided or ambiguous clause.
    """
    cache=reading.setdefault('_clause_readings',{})
    if unit['id'] in cache:return cache[unit['id']]
    from . import v3_syntax,v3_actors as a
    if '_source_scope_docs' not in reading:
        reading['_source_scope_docs']=v3_syntax.docs(u['quote']for u in reading['units'])
    docs=reading['_source_scope_docs'];doc=docs[reading['position'][unit['id']]] if docs else None
    result=[]
    if doc is not None:
        lem={t.i:a._lemma(t) for t in doc};txt={t.i:a._fold(t.text) for t in doc}
        predicates=[t for t in doc if nominal_carrier(t) or detached_active_theme(t) is not None or (t.pos_ in ('VERB','AUX') and (t.dep_=='ROOT'
            or t.dep_ in ('conj','ccomp','advcl','parataxis','acl','relcl')
            or (t.dep_ in ('xcomp','pcomp') and any(c.dep_ in ('nsubj','nsubjpass') for c in t.children))))]
        for predicate in predicates:
            words=owned_clause(predicate);inside=set(words)
            subjects=[t for t in predicate.children if t in inside and t.dep_ in ('nsubj','nsubjpass')]
            direct_patient=bool(len(subjects)==1 and a.this_patient(subjects[0]))
            malformed_denials=[t for t in subjects if t.pos_=='VERB' and a._lemma(t) in a.SOLE_NEGATION
                and not a._negates(t) and any(c.dep_ in ('nsubj','nsubjpass') and a.this_patient(c)
                    for c in t.children)]
            themes=[t for t in predicate.children if t in inside and t.dep_ in ('dobj','obj','nsubjpass')]
            passive_theme=detached_passive_theme(predicate)
            if passive_theme is not None:themes.append(passive_theme)
            possessed=bool(any(c.dep_=='poss' and a.this_patient(c) for t in themes for c in t.children))
            foreign=bool(len(subjects)==1 and a.names_person(subjects[0])
                and not any(a.this_patient(t) or (t.pos_=='PRON' and (t.dep_!='poss' or not a.names_person(t.head))) for t in words))
            # A known family member's complete positional action can own its
            # direct coordinated action. This does not inherit a clinician or
            # service's agent role, an unresolved subject, or an embedded actor.
            parent=predicate.head
            active_theme=detached_active_theme(predicate)
            if active_theme is not None:
                parent=next((t for t in active_theme.head.ancestors if t.pos_ in ('VERB','AUX')),parent)
            parent_subjects=[t for t in parent.children if t.dep_ in ('nsubj','nsubjpass')]
            if (not subjects and (predicate.dep_=='conj' or active_theme is not None) and parent.pos_ in ('VERB','AUX')
                    and not any(t.dep_=='auxpass' for t in predicate.children)
                    and len(parent_subjects)==1 and a._family(parent_subjects[0])
                    and transition_scope(reading,unit,clause=owned_clause(parent))=='position'
                    and not any(a.this_patient(t) or (t.pos_=='PRON' and (t.dep_!='poss' or not a.names_person(t.head))) for t in words)):
                foreign=True
            floor=a._floor_reading(words,predicate,lem=lem,txt=txt)
            # A medication nominal still attached to the position argument
            # after owned-clause recovery is an unresolved clinical theme.
            # The outer family's subject cannot make that omitted theme
            # foreign (for example, "warfarin but not apixaban was withheld").
            unresolved_theme=bool(floor['bare_cessation'] and any(t.dep_=='conj'
                    and t.head in inside
                    and 'medication' in a.SOLE_CLASSES.get(a._lemma(t),())
                    and a._lemma(t.head) in ('position','positioning') for t in words))
            if unresolved_theme:
                foreign=False
            own_keys=a.keys({a._lemma(t) for t in words if t.pos_ in a.CONTENT})-a.keys({'patient'})
            topics=floor['ceased_keys'] & own_keys
            # The pinned parser can use an object-predicate slot for a named
            # medication ('stopped apixaban'). Its positively typed argument
            # remains named; arbitrary adjectival complements do not qualify.
            nominal=[t for t in predicate.children if t in inside and t.dep_ in ('oprd','attr','acomp')
                and 'medication' in a.SOLE_CLASSES.get(a._lemma(t),())]
            repaired_argument=bool(a._lemma(predicate) in a.CESSATION_VERBS and nominal)
            if passive_theme is not None and a._lemma(predicate) in a.CESSATION_VERBS | a.SUPERSESSION_VERBS:
                nominal.append(passive_theme);repaired_argument=True
            if active_theme is not None:
                nominal.append(active_theme);repaired_argument=True
            if repaired_argument:
                topics |= a.keys({a._lemma(t) for argument in nominal for t in argument.subtree
                    if t in inside and t.pos_ in a.CONTENT})
            replacement=replacement_relation(predicate,words)
            if replacement:
                topics |= replacement['topics']
                foreign |= replacement['foreign']
            foreign_themes=[t for t in themes if any(c.dep_=='poss' and a.names_person(c) for c in t.children)
                and not any(a.this_patient(c) for c in t.subtree if c in inside)]
            foreign_keys=a.keys({a._lemma(t) for theme in foreign_themes for t in theme.subtree
                if t in inside and t.pos_ in a.CONTENT})
            if topics and topics<=foreign_keys:foreign=True
            # Withholding's explicit FROM recipient owns that affected action.
            # A passive theme or its preceding speaker never supplies a person.
            recipients=[t for prep in predicate.children if prep in inside and prep.dep_=='prep'
                and a._lemma(prep)=='from' for t in prep.children if t in inside and t.dep_=='pobj']
            recipient_patient=bool(a._lemma(predicate)=='withhold' and topics and len(recipients)==1
                and a.this_patient(recipients[0]))
            if (a._lemma(predicate)=='withhold' and topics and len(recipients)==1
                    and a.names_person(recipients[0])
                    and not direct_patient and not possessed
                    and not any(a.this_patient(t) or (t.pos_=='PRON' and (t.dep_!='poss' or not a.names_person(t.head)))
                        for t in recipients[0].subtree)):
                foreign=True
            generic=bool(any(a._lemma(t) in a.DOSAGE_FORM_NOUNS
                and 'medication' in a.SOLE_CLASSES.get(a._lemma(t),()) and a.keys({a._lemma(t)}) & topics for t in words)
                and not any('medication' in a.SOLE_CLASSES.get(a._lemma(t),())
                    and a._lemma(t) not in a.DOSAGE_FORM_NOUNS and a.keys({a._lemma(t)}) & topics for t in words))
            if replacement:generic |= replacement['generic']
            denied_end=denied_ending(predicate,words)
            cancelled=bool(a._negates(predicate) or denied_end or any(t.dep_=='aux' and t.tag_=='MD' for t in predicate.children))
            if replacement:cancelled=replacement['cancelled']
            span=doc[min(t.i for t in words):max(t.i for t in words)+1]
            sole=(a._sole_reading(span,predicate,value_start=0,colon=False,age=False,opener=False,explicit=direct_patient)
                if all(t in inside or t.is_punct for t in span) else {})
            separate=bool(sole.get('nouns_ok') and not sole.get('unknown') and not sole.get('reach')
                and sole.get('classes') and not sole.get('classes') & {'medication','therapy','test','care','allergy'}
                and a._lemma(predicate) in a.SOLE_CURRENT_VERBS and not floor['bare_cessation'] and not topics)
            negative_predicate=malformed_denials[0] if len(malformed_denials)==1 else predicate
            separate |= bool((direct_patient or len(malformed_denials)==1) and negative_operator(negative_predicate,a) is not None
                and (sole.get('nouns_ok') or len(malformed_denials)==1) and not sole.get('unknown') and sole.get('negation_only')
                and not sole.get('reach',frozenset()) & {'global','key'}
                and sole.get('classes') and not sole.get('classes') & {'medication','therapy','test','care','allergy'}
                and not floor['bare_cessation'] and not topics)
            # A complete named medication denial has its own argument. This
            # bounds only the positional floor; its matching denial still
            # holds that same value through the ordinary opposition checks.
            claim_topics=frozenset()
            if (direct_patient and negative_operator(predicate,a) is not None and sole.get('nouns_ok')
                    and not sole.get('unknown') and sole.get('negation_only')
                    and not sole.get('reach',frozenset()) & {'global','key'}
                    and sole.get('classes')==frozenset({'medication'}) and not floor['bare_cessation'] and not topics):
                medications=[t for t in words if 'medication' in a.SOLE_CLASSES.get(a._lemma(t),())]
                if medications and all(a._lemma(t) not in a.DOSAGE_FORM_NOUNS for t in medications):
                    claim_topics=a.keys({a._lemma(t) for t in medications})
            # A finite content clause owns its explicit subject, not its outer
            # speaker. Its carrier has no independent clinical argument here.
            # Its canonical denial retains scope on that owned content; an
            # extra negation, modifier, intention or ending cannot establish
            # this bounded carrier. No reporting-verb release list.
            complements=[c for c in predicate.children if c.dep_=='ccomp'
                or (nominal_carrier(predicate) and c.dep_=='acl')]
            subject_words={t for subject in subjects for t in subject.subtree if t in inside}
            carrier=bool(len(complements)==1 and complements[0] in predicates
                and any(c.dep_ in ('nsubj','nsubjpass') for c in complements[0].children)
                and (nominal_carrier(predicate) or (len(subjects)==1 and (direct_patient or foreign)))
                and all(t==predicate or t in subject_words or t.is_punct or t.dep_=='aux' for t in words)
                and not cancelled and not floor['intention'] and not floor['quantified_denial']
                and not floor['bare_cessation'] and not topics)
            result.append({'unit':unit,'predicate':predicate,'words':words,'patient':direct_patient or possessed or recipient_patient
                or bool(replacement and replacement['patient']),
                'foreign':foreign,'topics':topics,'generic':generic,'cancelled':cancelled,
                'denied_end':denied_end,
                'cancelled_replacement':bool(replacement and replacement['cancelled']),
                'medication_continuation':continued_medication(predicate,words),
                'unresolved_theme':unresolved_theme,
                'bare':floor['bare_cessation'] and not repaired_argument,'position':transition_scope(reading,unit,clause=words)=='position',
                'separate':separate,'carrier':carrier,'claim_topics':claim_topics,'bounded_end':bool(topics and (generic or all(
                    {a._lemma(t),a._fold(t.text)} & a._SOLE_KNOWN for t in words
                    if a.keys({a._lemma(t)}) & topics and t.pos_ in a.CONTENT)))})
    cache[unit['id']]=result
    return result


def denied_ending_keys(reading, unit):
    """Only keys of the proved denied event avoid the lexical value-denial floor."""
    clauses=clause_readings(reading,unit)
    if not all(c['denied_end'] or c['cancelled_replacement'] or c['foreign'] or c['position'] or c['carrier'] for c in clauses):
        return frozenset()
    return frozenset().union(*(c['topics'] for c in clauses if (c['denied_end'] or c['cancelled_replacement']) and c['bounded_end']))


def ending_affects(reading,ending,claim):
    if ending['foreign'] or ending['cancelled'] or ending['position'] or ending['separate'] or ending['carrier']:return False
    info=reading['actors'][claim['id']]
    if ending['medication_continuation']:return medication_affects(reading,claim)
    if ending['claim_topics']:
        return bool(ending['claim_topics'] & (reading['claim_keys'][claim['id']] | info.get('named_keys',frozenset())))
    if not ending['patient']:
        if not ending['bounded_end'] or ending['generic']:return True
        return bool(ending['topics'] & (reading['claim_keys'][claim['id']] | info.get('named_keys',frozenset())))
    if ending['generic']:
        from . import v3_actors as a
        if a._lemma(ending['predicate']) in a.SUPERSEDED_PREPOSITIONS:
            return unresolved_medication_affects(reading,ending['unit'],claim,predicate=ending['predicate'])
    return bool(ending['topics'] & (reading['claim_keys'][claim['id']] | info.get('named_keys',frozenset()))
        or (ending['generic'] and medication_affects(reading,claim)))


def bounded_mixed_endings(reading,unit):
    clauses=clause_readings(reading,unit)
    if len(clauses)<2 or not any(c['position'] or c['foreign'] for c in clauses):return None
    if not all(c['foreign'] or c['position'] or c['separate'] or c['carrier'] or c['medication_continuation'] or (not c['bare']
        and (c['bounded_end'] or c['claim_topics'] or ((c['patient'] or c['foreign']) and c['cancelled']))) for c in clauses):return None
    return clauses


def ceased_affects(reading,change,claim):
    """A proved ended argument retains its own polarity and recipient.

    The original unit-wide ended keys remain the fallback. Only complete owned
    endings covering every matching key can narrow that old floor. Unparsed
    endings, unknown arguments and incomplete medication groups remain held.
    """
    from . import v3_actors as a
    if resumed_current(reading,claim,change):return False
    shared=reading['actors'][change['id']]['ceased_keys'] & (
        reading['claim_keys'][claim['id']] | reading['actors'][claim['id']].get('named_keys',frozenset()))
    if not shared:return False
    clauses=[c for c in clause_readings(reading,change) if c['topics'] & shared]
    covered=frozenset().union(*(c['topics'] for c in clauses))
    if not shared<=covered or any(c['bare'] or not c['bounded_end']
        or any(t.dep_=='aux' and t.tag_=='MD' for t in c['predicate'].children) for c in clauses):return True
    return any(ending_affects(reading,c,claim) for c in clauses)


def explicit_patient_endings(reading,claim):
    result=[]
    keys=reading['claim_keys'][claim['id']] | reading['actors'][claim['id']].get('named_keys',frozenset())
    for unit in reading['units']:
        if unit['id']==claim['id']:continue
        if resumed_current(reading,claim,unit):continue
        for ending in clause_readings(reading,unit):
            if ending['unresolved_theme'] and medication_affects(reading,claim):
                if unit not in result:result.append(unit)
            # An unresolved subject cannot make this same named ending
            # independent. Retain it for review; do not assign a patient actor.
            uncertain=bool(not ending['foreign'] and not ending['patient'] and ending['bounded_end']
                and (ending['topics'] & keys or (ending['generic'] and medication_affects(reading,claim))))
            if not ending['cancelled'] and ((ending['patient'] and ending_affects(reading,ending,claim)) or uncertain):
                if unit not in result:result.append(unit)
    return result


def owned_oppositions(reading,claim):
    """Compare an owned patient assertion without adopting its outer speaker.

    This retains the established predicate's head, object, polarity and tense.
    A denial of taking is not a denial of possessing. It only adds a review
    dependency; it supplies no answer or inferred actor.
    """
    from . import v3_actors as a,generation as g
    mine=[g.v3_without_time(record) for record in reading['predicates'][claim['id']]]
    result=[]
    for unit in reading['units']:
        if unit['id']==claim['id']:continue
        for clause in clause_readings(reading,unit):
            if clause['foreign'] or clause['carrier'] or not clause['patient']:continue
            predicate=clause['predicate'];words=clause['words']
            records=a._predicates(predicate)
            if not records:continue
            # The first record is this predicate, before separately owned
            # conjoined verbs. Restrict its argument to this exact clause.
            head,negated,tense,complement,coordinated=records[0]
            own_keys=a.keys({a._lemma(t) for t in words if t.pos_ in a.CONTENT})-a.keys({'patient'})
            bounded=complement & own_keys
            if complement and not bounded:continue
            # A canonical denial owns its direct content clause; a foreign
            # outer speaker cannot erase the explicit patient's argument.
            child=predicate
            while child.dep_=='ccomp':
                parent=child.head
                if negative_operator(parent,a) is not None:
                    negated ^= not a._negates(parent)
                child=parent
            record=g.v3_without_time((head,negated,tense,bounded,coordinated))
            if any(g.v3_opposed_predicates(own,record) for own in mine):
                result.append(unit);break
    return result


def unresolved_medication_changes(reading):
    """A generic old medication argument does not identify what changed.

    A named source already has its own cessation keys. A generic dosage-form
    noun without a bound medication name needs review of affected medication
    claims; a positional target cannot establish that this old argument was a
    position. This only adds dependencies. A proved foreign actor, an explicitly
    negated event or a future modal supplies no completed patient change here.
    Existing named-source, bare-event and temporal floors remain unchanged.
    """
    key='_unresolved_medication_changes'
    if key in reading:return reading[key]
    from . import v3_syntax,v3_actors as a
    if '_source_scope_docs' not in reading:
        reading['_source_scope_docs']=v3_syntax.docs(u['quote']for u in reading['units'])
    found=[];events={}
    for unit,doc in zip(reading['units'],reading['_source_scope_docs'] or [None]*len(reading['units'])):
        if doc is None or pure_foreign_clause(reading,unit):continue
        clauses={c['predicate'].i:c for c in clause_readings(reading,unit)}
        for predicate in doc:
            verb=a._lemma(predicate)
            if predicate.pos_!='VERB' or verb not in a.SUPERSEDED_PREPOSITIONS:continue
            if a._negates(predicate) or any(t.dep_=='aux' and t.tag_=='MD' for t in predicate.children):continue
            if clauses.get(predicate.i,{}).get('foreign'):continue
            replacements=[t for prep in predicate.children if prep.dep_=='prep' and a._lemma(prep)=='to'
                for t in prep.children if t.dep_ in ('pobj','pcomp')]
            source_preps=list(predicate.children)+[p for target in replacements for p in target.children]
            for prep in source_preps:
                if prep.dep_!='prep' or a._lemma(prep) not in a.SUPERSEDED_PREPOSITIONS[verb]:continue
                for argument in prep.children:
                    if (argument.dep_ not in ('pobj','pcomp') or argument.pos_ not in ('NOUN','PROPN')
                            or a._lemma(argument) not in a.DOSAGE_FORM_NOUNS
                            or 'medication' not in a.SOLE_CLASSES.get(a._lemma(argument),())):continue
                    if (any(t.dep_=='poss' and a.names_person(t) for t in argument.children)
                            and not any(a.this_patient(t) for t in argument.subtree)):continue
                    # A known medication name must modify this argument, not
                    # the target or another clause. Quantities and forms do
                    # not provide an identity ('5 mg medication').
                    named=any(t.dep_ in ('amod','compound','appos') and t.pos_ in ('NOUN','PROPN','ADJ')
                        and 'medication' in a.SOLE_CLASSES.get(a._lemma(t),())
                        and a._lemma(t) not in a.DOSAGE_FORM_NOUNS
                        and not any(c.pos_=='NUM' for c in t.children) for t in argument.children)
                    if not named:
                        if unit not in found:found.append(unit)
                        target_keys=frozenset()
                        if len(replacements)==1:
                            target=replacements[0]
                            if ('medication' in a.SOLE_CLASSES.get(a._lemma(target),())
                                    and a._lemma(target) not in a.DOSAGE_FORM_NOUNS
                                    and all(t==target or t.pos_ in ('DET','PUNCT')
                                        for t in target.subtree if t not in set(prep.subtree))):
                                target_keys=a.keys({a._lemma(target),a._fold(target.text)})
                        events.setdefault(unit['id'],[]).append({'predicate':predicate.i,'target':target_keys})
    reading[key]=found
    reading['_unresolved_medication_events']=events
    return found


def unresolved_medication_affects(reading,change,claim,*,predicate=None):
    if not medication_affects(reading,claim):return False
    # Switching FROM an unidentified source does not also end its named TO
    # value. Only that exact target's separate complete current medication claim
    # can avoid this new source dependency; all other existing guards still see it.
    unresolved_medication_changes(reading)
    events=reading.get('_unresolved_medication_events',{}).get(change['id'],())
    if predicate is not None:
        events=[event for event in events if event['predicate']==predicate.i]
        if not events:return False
    targets=[event['target'] for event in events]
    info=reading['actors'][claim['id']];sole=info.get('sole') or {}
    names=info.get('named_keys',frozenset())
    if (targets and names and all(target and names<=target for target in targets) and sole.get('classes')==frozenset({'medication'})
            and not sole.get('unknown') and info.get('present_tense')
            and not info.get('past_time') and not info.get('habitual') and not info.get('intention')):return False
    return True


def medication_argument_references(value,pattern):
    """All literal matches are old medication arguments, not question names.

    The same generic noun can name a printed question or the old argument of a
    supersession. Only the exact source token in the latter grammatical role
    qualifies. This removes no clinical dependency: source identity, actor,
    event polarity, time and current-answer evidence are judged separately.
    A question heading, named section, target, mixed reference or unparsed token
    retains the original structural coupling.
    """
    from . import v3_syntax,v3_actors as a
    matches=list(pattern.finditer(value))
    if not matches:return False
    docs=v3_syntax.docs([value]);doc=docs[0] if docs else None
    if doc is None:return False
    tokens={(t.idx,t.idx+len(t.text)):t for t in doc}
    for match in matches:
        token=tokens.get(match.span())
        if (token is None or token.pos_ not in ('NOUN','PROPN')
                or a._lemma(token) not in a.DOSAGE_FORM_NOUNS
                or 'medication' not in a.SOLE_CLASSES.get(a._lemma(token),())
                or token.dep_ not in ('pobj','pcomp')):return False
        prep=token.head;predicate=prep.head
        if (predicate.dep_ in ('pobj','pcomp') and predicate.head.dep_=='prep'
                and a._lemma(predicate.head)=='to'
                and 'medication' in a.SOLE_CLASSES.get(a._lemma(predicate),())
                and a._lemma(predicate) not in a.DOSAGE_FORM_NOUNS):
            predicate=predicate.head.head
        if (prep.dep_!='prep' or predicate.pos_!='VERB'
                or a._lemma(prep) not in a.SUPERSEDED_PREPOSITIONS.get(a._lemma(predicate),())):return False
    return True


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
        # The predicate's own object determiner also supplies polarity ('has
        # no swelling'). A lexical absence predicate supplies the same negative
        # relation ('lacks swelling'), unless that predicate itself is negated.
        # Merely reading syntactic neg children loses both of those relations.
        return {bool(record[1]) ^ (negative_operator(t,a) is not None)
            for t in nodes or [root] for record in a._predicates(t)}
    causes={}
    clinical_polarities=clinical_modifier_negations(reading)
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
            if len(my_roots)!=1:continue
            my_topics=mine.get('claim_keys',frozenset())|mine.get('named_keys',frozenset())
            own_property=clinical_polarities.get(claim['id'],{})
            other_property=clinical_polarities.get(other['id'],{})
            own_negative=own_property.get('negative',frozenset()) & topic
            other_negative=other_property.get('negative',frozenset()) & my_topics
            own_ambiguous=own_property.get('ambiguous',frozenset()) & topic
            other_ambiguous=other_property.get('ambiguous',frozenset()) & my_topics
            # Polarity belongs to the affected clinical PROPERTY. Its enclosing
            # light verb can stay affirmative ('has an absence of swelling').
            # Unresolved negative relations establish no polarity and cannot
            # prove an exclusive same-topic statement independent.
            my_polarity={False,True} if own_ambiguous else ({True} if own_negative else predicate_negations(my_roots[0]))
            other_polarity={False,True} if other_ambiguous else ({True} if other_negative else negations)
            if not my_polarity & other_polarity:continue
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
            # A nominal clinical property ('No swelling') and a directly
            # governed absence of that SAME property ('lacks swelling' / 'has
            # no swelling') need not share a light-verb spelling. Exclusivity
            # reattributes only their already-established negative relation.
            same_negative_property=bool(
                clinical_polarities.get(claim['id'],{}).get('negative',frozenset())
                & clinical_polarities.get(other['id'],{}).get('negative',frozenset())
                and (a._lemma(root) in a.LIGHT_VERBS or negative_operator(root,a) is not None))
            unresolved_property=bool((own_ambiguous or other_ambiguous)
                and (a._lemma(root) in a.LIGHT_VERBS or negative_operator(root,a) is not None))
            if ((predicates-{'be'}) & (my_predicates-{'be'}) or heads & my_heads
                    or same_assertion or nominal_reference or anatomical_parse or same_negative_property or unresolved_property) and topic & (
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
        # A clinical nominal gerund can own an open copular complement whose
        # negative adjective carries its anatomy ('swelling to be absent over
        # the right ankle'). That bound copula has no actor/object of its own;
        # arbitrary embedded actions and clauses remain excluded.
        complements={t for t in phrase.subtree if t.dep_=='xcomp' and a._lemma(t)=='be'
            and not any(c.dep_ in ('nsubj','nsubjpass','csubj','csubjpass','dobj','obj','iobj') for c in t.children)
            and any(c.dep_=='acomp' and c.pos_=='ADJ' and negative_operator(c,a) is not None for c in t.children)}
        for member in phrase.subtree:
            path=member
            while path!=phrase and path.head!=path:
                if path.dep_ in ('conj','advcl','ccomp','relcl','acl') or (path.dep_=='xcomp' and path not in complements):break
                path=path.head
            if path!=phrase:continue
            side=a.SOLE_SIDES.get(a._fold(member.text))
            if side=='both':sides.update(('left','right'))
            elif side:sides.add(side)
        return sides
    def occurrences(unit):
        info=reading['actors'][unit['id']]
        if not info.get('readable'):return None
        doc=docs[reading['position'][unit['id']]]
        if doc is None:return None
        matched={key:[] for key in shared}
        for token in doc:
            nominal_gerund=bool(token.tag_=='VBG' and a.SOLE_CLASSES.get(a._fold(token.text),frozenset()) & a.SOLE_CLINICAL)
            if token.pos_ not in ('NOUN','PROPN') and not nominal_gerund and not negative_clinical_modifiers(token,a):continue
            keys=a.keys({a._lemma(token),a._fold(token.text)}) & shared
            if keys:
                # An outer foreign speaker can deny an explicitly patient-owned
                # content clause. Only that matching argument's nearest direct
                # grammatical subject can prove whose side this is; a subject
                # elsewhere in the sentence cannot qualify it.
                if info.get('other_floor'):
                    current=token;patient_argument=False
                    for _ in range(6):
                        subjects=[t for t in current.children if t.dep_ in ('nsubj','nsubjpass','csubj','csubjpass')]
                        if subjects:
                            patient_argument=bool(len(subjects)==1 and a.this_patient(subjects[0]));break
                        if current.head==current:break
                        current=current.head
                    if not patient_argument:return None
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
        if doc is None:continue
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
    direct=bool(len(subjects)==1 and subjects[0].head==root and a.names_person(subjects[0]))
    # A positively bound possessor remains the actor of its own clinical
    # property. The pinned parser can misread father's swelling as a gerund
    # clause, with father its nested grammatical subject. Its explicit possessive
    # marker and sole copular clinical subject must establish that binding.
    possessed=False
    clinical_subjects=[t for t in root.children if t.dep_ in ('nsubj','nsubjpass','csubj','csubjpass')
        and a.SOLE_CLASSES.get(a._fold(t.text),frozenset()) & a.SOLE_CLINICAL]
    if len(clinical_subjects)==1 and a._lemma(root)=='be':
        subject=clinical_subjects[0]
        owners=[t for t in subject.children if t.pos_ in ('NOUN','PROPN') and a.names_person(t)
            and (t.dep_=='poss' or (t.dep_ in ('nsubj','nsubjpass')
                and any(c.dep_=='case' and a._fold(c.text) in ("'s",'’s') for c in t.children)))]
        possessed=bool(len(owners)==1 and set(subjects)==({subject,owners[0]} if owners[0] in subjects else {subject}))
    if len(clinical_subjects)==1 and not possessed:
        subject=clinical_subjects[0]
        body=frozenset(a.SOLE_LEXICON['body'].split())
        # Explicit possession of the anatomical object establishes the actor
        # of this clinical subject even through a passive open complement:
        # swelling over her father's ankle was found to be absent. A body
        # pronoun, another actor or a patient reference supplies no such proof.
        owners=[t for t in subject.subtree if t.dep_=='poss' and a.names_person(t)
            and t.head.pos_ in ('NOUN','PROPN') and {a._lemma(t.head),a._fold(t.head.text)} & body
            and any(c.dep_=='case' and a._fold(c.text) in ("'s",'’s') for c in t.children)]
        possessed=bool(len(owners)==1 and set(subjects)=={subject}
            and not any(t.dep_ in ('conj','ccomp','xcomp','advcl','relcl','acl') for t in subject.subtree))
    # A clinical gerund parsed as an open complement has the same sole
    # explicit actor when it contains no subject or another person of its own.
    inline={t for t in root.children if t.dep_=='xcomp' and t.tag_=='VBG'
        and a.SOLE_CLASSES.get(a._fold(t.text),frozenset()) & a.SOLE_CLINICAL
        and not any(c.dep_ in ('nsubj','nsubjpass','csubj','csubjpass') or a.names_person(c) for c in t.subtree)}
    inline |= {t for t in root.children if t.dep_=='xcomp' and a._lemma(t)=='be'
        and not any(c.dep_ in ('nsubj','nsubjpass','csubj','csubjpass','dobj','obj','iobj') for c in t.children)
        and any(c.dep_=='acomp' and c.pos_=='ADJ' and negative_operator(c,a) is not None for c in t.children)}
    return bool((direct or possessed) and root.pos_ in ('VERB','AUX') and not any(t.tag_=='MD' for t in doc)
        and not any(a.this_patient(t) or (t.pos_=='PRON' and (t.dep_!='poss' or not a.names_person(t.head))) for t in doc)
        and not any(t.dep_ in ('ccomp','advcl','conj','relcl','acl') or (t.dep_=='xcomp' and t not in inline) for t in doc))


def negative_operator(token,a):
    """Canonical existing absence operator, including its explicit noun form.

    The nominalization keeps the same grammatical relation; it establishes no
    clinical state and is used only to retain the affected claim for review.
    """
    word=a._lemma(token)
    if word in a.SOLE_NEGATION:return word
    if token.pos_=='NOUN' and word=='absence':return 'absent'
    return None


def negative_clinical_modifiers(token,a):
    """Existing clinical word and a direct grammatical absence relation.

    The pinned parser can tag a nominal -ing argument as a verb. Its actual
    direct argument/modifier edge still supplies a hold; it supplies no positive
    assertion or repaired predicate. An embedded action (without treating pain)
    has no such direct edge to the clinical word.
    """
    classes=a.SOLE_CLASSES.get(a._lemma(token),frozenset()) | a.SOLE_CLASSES.get(a._fold(token.text),frozenset())
    if not classes & a.SOLE_CLINICAL:return []
    modifiers=[t for t in token.children if t.dep_ in ('amod','det','acomp','oprd') and negative_operator(t,a) is not None]
    if (token.dep_ in ('compound','npadvmod','acl','xcomp','nsubj','nsubjpass','csubj','csubjpass','dobj','obj')
            and token.head.pos_ in ('ADJ','NOUN','VERB','AUX') and negative_operator(token.head,a) is not None):modifiers.append(token.head)
    if token.dep_ in ('nsubj','nsubjpass','csubj','csubjpass') and a._lemma(token.head)=='be':
        modifiers.extend(t for t in token.head.children if t.dep_=='acomp'
            and t.pos_=='ADJ' and negative_operator(t,a) is not None)
    if token.dep_ in ('pobj','pcomp') and token.head.pos_=='ADP':
        prep=token.head
        if negative_operator(prep,a) is not None:modifiers.append(prep)
        elif prep.dep_=='prep' and prep.head.pos_ in ('ADJ','NOUN') and negative_operator(prep.head,a) is not None:
            modifiers.append(prep.head)
    return modifiers


def ambiguous_negative_complements(token,a):
    """An unresolved negative complement still depends on its named topic.

    Follow only the grammatical predicate/complement chain of a positively
    typed clinical argument. A new explicit subject/object, sibling clause,
    adverbial or arbitrary nearby negative word is no such binding. This is a
    review dependency, never evidence of an inferred clinical value.
    """
    classes=a.SOLE_CLASSES.get(a._lemma(token),frozenset()) | a.SOLE_CLASSES.get(a._fold(token.text),frozenset())
    if not classes & a.SOLE_CLINICAL:return []
    # A nominal clinical gerund can itself govern an open complement even when
    # the parser attaches it as acl/xcomp to a report noun or another verb.
    nominal_gerund=bool(token.tag_=='VBG' and a.SOLE_CLASSES.get(a._fold(token.text),frozenset()) & a.SOLE_CLINICAL)
    predicates=[token] if nominal_gerund else []
    if token.dep_ in ('nsubj','nsubjpass','csubj','csubjpass','dobj','obj') and token.head.pos_ in ('VERB','AUX') and a._lemma(token.head)!='be':
        predicates.append(token.head)
    pending=[(predicate,0) for predicate in predicates];seen=set();negative=[]
    while pending:
        current,depth=pending.pop()
        if current.i in seen or depth>4:continue
        seen.add(current.i)
        for child in current.children:
            if child.dep_ not in ('xcomp','acomp','oprd'):continue
            if child.pos_=='ADJ' and negative_operator(child,a) is not None:negative.append(child)
            elif child.pos_ in ('VERB','AUX') and not any(t.dep_ in (
                    'nsubj','nsubjpass','csubj','csubjpass','dobj','obj','iobj') for t in child.children):
                pending.append((child,depth+1))
    return negative


def uncertain_negative_arguments(token,a):
    """Negative operator bound to a named topic through an unresolved relation.

    A negative unknown nominal container's OF argument ('no evidence of
    swelling') and a negative predicate's explicit patient content clause cannot
    prove that same clinical topic independent. They establish review dependencies,
    never absence, diagnosis or current treatment. A known separate treatment
    predicate or an explicitly foreign content-clause subject is not this edge.
    """
    classes=a.SOLE_CLASSES.get(a._lemma(token),frozenset()) | a.SOLE_CLASSES.get(a._fold(token.text),frozenset())
    if not classes & a.SOLE_CLINICAL:return []
    result=[]
    current=token;seen=set();intermediate=0
    # Walk the entire same grammatical OF chain, bounded by this source doc.
    # An unknown intermediate nominal relation cannot prove a named topic
    # independent of its explicit negative container. A known separate clinical
    # or treatment object, another person or a non-OF relation stops the path.
    while current.i not in seen and len(seen)<len(token.doc):
        seen.add(current.i)
        if current.dep_ not in ('pobj','pcomp') or current.head.pos_!='ADP' or a._lemma(current.head)!='of':break
        container=current.head.head
        container_classes=a.SOLE_CLASSES.get(a._lemma(container),frozenset()) | a.SOLE_CLASSES.get(a._fold(container.text),frozenset())
        if container.pos_!='NOUN' or container_classes or a.names_person(container):break
        operator=negative_operator(container,a)
        negative=bool(a._negates(container) or any(t.dep_ in ('amod','det')
            and negative_operator(t,a) is not None for t in container.children))
        if (operator is not None and intermediate) or (operator is None and negative):result.append(container)
        current=container;intermediate+=1
    clause=token if token.dep_=='ccomp' else token.head if token.dep_ in (
        'dobj','obj','nsubj','nsubjpass','csubj','csubjpass') else None
    if clause is not None and clause.dep_=='ccomp' and negative_operator(clause.head,a) is not None:
        subjects=[t for t in clause.children if t.dep_ in ('nsubj','nsubjpass','csubj','csubjpass')]
        foreign=bool(subjects and all(a.names_person(t) and not a.this_patient(t) for t in subjects))
        if not foreign:result.append(clause.head)
    return result


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
    if token.dep_ in ('nsubj','nsubjpass','csubj','csubjpass') and (
            (head.pos_=='ADJ' and a._lemma(head) in a.SOLE_NEGATION) or a._lemma(head)=='be'):
        return head
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
            # An actual noncopular predicate may change whether its negative
            # complement is an observation, report or intention. Never infer
            # which; the same named clinical claim remains reviewable.
            nominal_operator=bool(noun.tag_=='VBG'
                and a.SOLE_CLASSES.get(a._fold(noun.text),frozenset()) & a.SOLE_CLINICAL
                and any(t.dep_ in ('dobj','obj','attr') and negative_operator(t,a) is not None for t in noun.children))
            if ambiguous_negative_complements(noun,a) or uncertain_negative_arguments(noun,a) or nominal_operator:
                ambiguous |= a.keys({a._lemma(noun),a._fold(noun.text)})
            modifiers=negative_clinical_modifiers(noun,a)
            if modifiers:
                keys=a.keys({a._lemma(noun),a._fold(noun.text)})
                spine=[noun,*noun.ancestors]
                cancelled=any(a._negates(t) for t in modifiers) or any(
                    c.dep_=='neg' for t in spine for c in t.children)
                copula=noun.head
                negators=[t for t in copula.children if t.dep_=='neg']
                # The explicit 'is not absent' predicate denies absence; it
                # supplies no new value and cannot contradict an affirmation.
                # Other nested/double negation stays unresolved.
                non_opposed=bool(cancelled and noun.dep_ in ('nsubj','nsubjpass','csubj','csubjpass')
                    and a._lemma(copula)=='be' and len(modifiers)==1
                    and modifiers[0].head==copula and modifiers[0].dep_=='acomp'
                    and len(negators)==1 and a._fold(negators[0].text) in ('not',"n't")
                    and not any(a._negates(t) for t in modifiers)
                    and not any(t.tag_=='MD' or a._fold(t.text) in a.SOLE_UNCERTAIN for t in doc)
                    and sum(t.dep_=='neg' for t in doc)==1)
                if non_opposed:continue
                if cancelled:ambiguous |= keys
                else:targets |= keys
        if targets or ambiguous:result[unit['id']]={'negative':frozenset(targets),'ambiguous':frozenset(ambiguous)}
    reading[key]=result
    return result
