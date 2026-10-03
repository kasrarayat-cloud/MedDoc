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
            def position_argument(token,excluded=()):
                # The explicit position noun includes its grammatical noun
                # nominalization. No orientation-word whitelist supplies it.
                word=a._lemma(token)
                named=token.pos_=='NOUN' and (word=='position' or (word.endswith('ing') and word[:-3]=='position'))
                members=[t for t in token.subtree if t not in excluded]
                return bool(named and any(t.dep_ in ('amod','compound') and t.pos_=='ADJ' for t in members)
                    and all(t==token or t.pos_ in ('ADJ','ADV','DET','PUNCT') for t in members)
                    and not any(a.SOLE_CLASSES.get(a._lemma(t),frozenset()) for t in members))
            sources=[p for p in root.children if p.dep_=='prep' and a._lemma(p)=='from']
            positional_targets=[(p,g) for p in doc if p.dep_=='prep' and a._lemma(p)=='to'
                for g in p.children if g.dep_=='pobj' and position_argument(g)]
            positional=bool(not sources and len(positional_targets)==1 and positional_targets[0][0].head==root)
            if len(sources)==1 and len(positional_targets)==1:
                source=sources[0];target_prep,target=positional_targets[0]
                objects=[t for t in source.children if t.dep_=='pobj']
                adjectival=[t for t in source.subtree if t not in set(target_prep.subtree)]
                adjective_source=bool(not objects and any(t.pos_=='ADJ' for t in adjectival)
                    and all(t==source or t.pos_ in ('ADJ','ADV','PUNCT') for t in adjectival)
                    and not any(a.SOLE_CLASSES.get(a._lemma(t),frozenset())
                        or a._fold(t.text) in a.SOLE_UNCERTAIN for t in adjectival))
                noun_source=bool(len(objects)==1 and position_argument(objects[0],set(target_prep.subtree)))
                positional=bool((adjective_source or noun_source)
                    and (target_prep.head==root or (noun_source and target_prep.head==objects[0])))
            if (positional and a._lemma(root) in ('switch','change') and len(verbs)==1
                    and all(a.this_patient(t) or a.names_person(t) or a._fold(t.text) in ('he','she') for t in subjects)
                    and not any(t.dep_ in ('dobj','obj','ccomp','xcomp','advcl','conj','neg') for t in root.children)
                    and not any(t.dep_=='prep' and a._fold(t.text) in ('with','by','of','for') for t in doc)):
                answer='position'
            complete=bool(a._lemma(root) in ('switch','change') and len(verbs)==1 and len(targets)==1
                and all(a.this_patient(t) or a._fold(t.text) in ('he','she') for t in subjects)
                and not any(t.dep_ in ('dobj','obj','ccomp','xcomp','advcl','conj','neg') for t in root.children)
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
    return medication_affects(reading,claim)


def medication_affects(reading,claim):
    """An unresolved medication event governs its claim and actual dependencies."""
    info=reading['actors'][claim['id']]
    sole=info.get('sole') or {}
    classes=sole.get('classes',frozenset())
    if not classes or sole.get('unknown') or 'global' in sole.get('reach',()):return True
    return bool(classes & {'medication','therapy','test','care'})


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
    found=[];targets={}
    for unit,doc in zip(reading['units'],reading['_source_scope_docs'] or [None]*len(reading['units'])):
        if doc is None or pure_foreign_clause(reading,unit):continue
        for predicate in doc:
            verb=a._lemma(predicate)
            if predicate.pos_!='VERB' or verb not in a.SUPERSEDED_PREPOSITIONS:continue
            if a._negates(predicate) or any(t.dep_=='aux' and t.tag_=='MD' for t in predicate.children):continue
            replacements=[t for prep in predicate.children if prep.dep_=='prep' and a._lemma(prep)=='to'
                for t in prep.children if t.dep_ in ('pobj','pcomp')]
            source_preps=list(predicate.children)+[p for target in replacements for p in target.children]
            for prep in source_preps:
                if prep.dep_!='prep' or a._lemma(prep) not in a.SUPERSEDED_PREPOSITIONS[verb]:continue
                for argument in prep.children:
                    if (argument.dep_ not in ('pobj','pcomp') or argument.pos_ not in ('NOUN','PROPN')
                            or a._lemma(argument) not in a.DOSAGE_FORM_NOUNS
                            or 'medication' not in a.SOLE_CLASSES.get(a._lemma(argument),())):continue
                    # A known medication name must modify this argument, not
                    # the target or another clause. Quantities and forms do
                    # not provide an identity ('5 mg medication').
                    named=any(t.dep_ in ('amod','compound','appos') and t.pos_ in ('NOUN','PROPN','ADJ')
                        and 'medication' in a.SOLE_CLASSES.get(a._lemma(t),())
                        and a._lemma(t) not in a.DOSAGE_FORM_NOUNS
                        and not any(c.pos_=='NUM' for c in t.children) for t in argument.children)
                    if not named and unit not in found:
                        found.append(unit)
                        if len(replacements)==1:
                            target=replacements[0]
                            if ('medication' in a.SOLE_CLASSES.get(a._lemma(target),())
                                    and a._lemma(target) not in a.DOSAGE_FORM_NOUNS
                                    and all(t==target or t.pos_ in ('DET','PUNCT')
                                        for t in target.subtree if t not in set(prep.subtree))):
                                targets[unit['id']]=a.keys({a._lemma(target),a._fold(target.text)})
    reading[key]=found
    reading['_unresolved_medication_targets']=targets
    return found


def unresolved_medication_affects(reading,change,claim):
    if not medication_affects(reading,claim):return False
    # Switching FROM an unidentified source does not also end its named TO
    # value. Only that exact target's separate complete current medication claim
    # can avoid this new source dependency; all other existing guards still see it.
    unresolved_medication_changes(reading)
    target=reading.get('_unresolved_medication_targets',{}).get(change['id'],frozenset())
    info=reading['actors'][claim['id']];sole=info.get('sole') or {}
    names=info.get('named_keys',frozenset())
    if (target and names and names<=target and sole.get('classes')==frozenset({'medication'})
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
