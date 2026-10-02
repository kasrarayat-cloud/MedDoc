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
    topicless, positively read fragment such as "Not today"/"Except today"
    likewise supplies no standalone claim. No inferred replacement value is
    adopted. Complete other-person clauses remain separate. These dependencies
    attach to the preceding nonfragment (or the following one at source start),
    rather than every field or the whole note.
    """
    key='_elliptical_dependencies'
    if key in reading:return reading[key]
    from . import v3_syntax,v3_actors as a
    units=reading['units'];docs=v3_syntax.docs(u['quote'] for u in units)
    causes={};previous=None;leading=[]
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
                fragment=operator or topicless
        if fragment:
            if previous is not None:causes.setdefault(previous,[]).append(unit)
            else:leading.append(unit)
        else:
            if leading:causes.setdefault(uid,[]).extend(leading);leading=[]
            previous=uid
    reading[key]=causes
    return causes
