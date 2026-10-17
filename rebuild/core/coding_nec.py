"""Bounded clinical-concept evidence for an official specified-NEC route.

MeSH supplies clinical term identities and explicit narrower-concept edges.
It supplies no ICD mapping. The complete dated ICD family, source assertions
and Tabular instructions still decide whether the selected NEC route applies.
"""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from django.core.exceptions import ValidationError


RESOURCE = Path(__file__).parent / 'data/mesh2026_clinical_concepts.json'
RESOURCE_SHA256 = '5d28080fdc09736bd42e52adf8157f42dae68f5c137fe4f19a4e3814e9a7b8df'
VOCAB = 'http://id.nlm.nih.gov/mesh/vocab#'
BASE = 'http://id.nlm.nih.gov/mesh/2026/'
FORMAT = 'source-bound-mesh-nec-proof-v1'
GUIDELINES_SHA256 = '1f0065b609b678e98f85bf047b3b012c6a88ba3222e42be2f2435889e05738ab'


def _guideline_bound(reference):
    # Sparse reads expose exactly one scalar from the immutable release. Never
    # trigger a deferred ORM provenance read as a fallback for missing data.
    values = vars(reference)
    if 'guidelines_sha256' in values:
        digest = values['guidelines_sha256']
    else:
        provenance = values.get('provenance', {})
        try:
            digest = provenance['manifest']['files']['guidelines']['sha256']
        except (KeyError, TypeError):
            return False
    return reference.release.version == 'FY2027' and digest == GUIDELINES_SHA256


def _values(value):
    return value if isinstance(value, list) else [] if value is None else [value]


def _label(value):
    if type(value) is not dict or value.get('@language') != 'en' or type(value.get('@value')) is not str:
        raise ValidationError('The clinical terminology label is unresolved.')
    text = value['@value']
    if not text or len(text) > 180:
        raise ValidationError('The clinical terminology label exceeds its bound.')
    return text


def parse_resource(raw):
    """Derive the projection from every raw record, not a hand-written mapping."""
    if (type(raw) is not dict or raw.get('format') != 'nlm-mesh-concept-records-v1'
            or raw.get('version') != 'MeSH 2026' or type(raw.get('records')) is not list
            or not 1 <= len(raw['records']) <= 256):
        raise ValidationError('The clinical terminology resource is unresolved.')
    records = {}
    for item in raw['records']:
        if type(item) is not dict or type(item.get('raw')) is not str or len(item['raw']) > 100000:
            raise ValidationError('A clinical terminology record exceeds its bound.')
        if hashlib.sha256(item['raw'].encode()).hexdigest() != item.get('sha256'):
            raise ValidationError('A clinical terminology record changed.')
        obj = json.loads(item['raw']); key = obj.get('@id')
        if (not isinstance(key, str) or not re.fullmatch(re.escape(BASE) + r'[DMT]\d+', key)
                or item.get('url') != key.replace('http:', 'https:') + '.json' or key in records):
            raise ValidationError('A clinical terminology identity is invalid or repeated.')
        for predicate in ('narrowerConcept','broaderDescriptor','concept','preferredConcept','preferredTerm','term'):
            if predicate in obj and obj.get('@context', {}).get(predicate, {}).get('@id') != VOCAB + predicate:
                raise ValidationError('The clinical terminology predicate is not the asserted typed edge.')
        records[key] = obj
    descriptors = [row for row in records.values() if row.get('@type') == VOCAB + 'TopicalDescriptor']
    if not descriptors or len(descriptors) > 32:
        raise ValidationError('The clinical terminology descriptor scope is unresolved.')
    used = set(); relations = []
    for descriptor in descriptors:
        used.add(descriptor['@id'])
        parent_id = descriptor.get('preferredConcept')
        ids = [parent_id, *_values(descriptor.get('concept'))]
        if len(ids) != len(set(ids)) or len(ids) > 64:
            raise ValidationError('The clinical terminology concept scope is invalid.')
        concepts = {}
        for key in ids:
            row = records.get(key)
            if not row or row.get('@type') != VOCAB + 'Concept':
                raise ValidationError('A descriptor concept is missing.')
            used.add(key)
            term_ids = [row.get('preferredTerm'), *_values(row.get('term'))]
            if len(term_ids) != len(set(term_ids)) or len(term_ids) > 64:
                raise ValidationError('A concept term scope is invalid.')
            terms = []
            for term_id in term_ids:
                term = records.get(term_id)
                if not term or term.get('@type') != VOCAB + 'Term':
                    raise ValidationError('An authoritative concept term is missing.')
                used.add(term_id); terms.append(_label(term.get('prefLabel')))
            if _label(row.get('label')) not in terms:
                raise ValidationError('The preferred concept label is inconsistent.')
            children = _values(row.get('narrowerConcept'))
            if any(child not in ids or child == key for child in children) or len(children) != len(set(children)):
                raise ValidationError('The clinical narrower-concept relation is incomplete.')
            concepts[key] = dict(id=key, terms=terms, children=children)
        # Every edge remains explicit; a descriptor association is not IS_A.
        def walk(key, seen):
            if key in seen:
                raise ValidationError('The clinical terminology relation contains a cycle.')
            for child in concepts[key]['children']:
                walk(child, seen | {key})
        for key in concepts:
            walk(key, set())
        for parent in concepts.values():
            for child_id in parent['children']:
                relations.append(dict(descriptor_id=descriptor['@id'], parent=parent,
                    child=concepts[child_id], concepts=concepts,
                    broader_descriptors=_values(descriptor.get('broaderDescriptor')),
                    preferred_concept_id=parent_id))
    if used != set(records):
        raise ValidationError('The clinical terminology resource contains unbound records.')
    scope=raw.get('nec_relation_roots')
    if (type(scope) is not list or not scope or len(scope) != len(set(scope))
            or any(key not in {row['@id'] for row in descriptors} for key in scope)):
        raise ValidationError('The positive clinical relation scope is unresolved.')
    return relations


def load():
    data = RESOURCE.read_bytes()
    if len(data) > 1000000 or hashlib.sha256(data).hexdigest() != RESOURCE_SHA256:
        raise ValidationError('The pinned clinical terminology resource changed.')
    raw = json.loads(data)
    condition_families(raw)
    return raw, parse_resource(raw)


def condition_families(raw):
    """Validate the complete, counted official hold-only terminology query.

    A result page is not completeness evidence. The independent descriptor
    inventory, aggregate row count and ordered pages must all reconcile.
    None of these broader-descriptor edges permits a positive NEC inference.
    """
    families=raw.get('conditional_families')
    if type(families) is not list or not 1 <= len(families) <= 8:
        raise ValidationError('The conditional terminology scope is unresolved.')
    result={};prefix='PREFIX meshv: <'+VOCAB+'> '
    def read(item,query):
        if (type(item) is not dict or item.get('query') != query or type(item.get('raw')) is not str
                or len(item['raw']) > 600000 or item.get('url') != 'https://id.nlm.nih.gov/mesh/sparql?'+urlencode({'query':query,'format':'JSON'})
                or hashlib.sha256(item['raw'].encode()).hexdigest() != item.get('sha256')):
            raise ValidationError('The typed conditional terminology query changed.')
        try:
            rows=json.loads(item['raw'])['results']['bindings']
        except (ValueError,KeyError,TypeError) as exc:
            raise ValidationError('The conditional query response is malformed.') from exc
        if type(rows) is not list or any(type(row) is not dict for row in rows):
            raise ValidationError('The conditional query rows are malformed.')
        return rows
    def identity(row,key,kind):
        value=row.get(key,{})
        if (type(value) is not dict or value.get('type') != 'uri'
                or not re.fullmatch(re.escape(BASE)+kind+r'\d+',str(value.get('value')))):
            raise ValidationError('A conditional terminology identity has an invalid type or version.')
        return value['value']
    for family in families:
        root=family.get('root') if type(family) is dict else None
        if not isinstance(root,str) or not re.fullmatch(re.escape(BASE)+r'D\d+',root) or root in result:
            raise ValidationError('The conditional terminology root is invalid or repeated.')
        where='WHERE { ?descriptor meshv:broaderDescriptor* <'+root+'> . ?descriptor (meshv:preferredConcept|meshv:concept) ?concept . ?concept (meshv:preferredTerm|meshv:term) ?term . ?term meshv:prefLabel ?label . OPTIONAL { ?descriptor meshv:broaderDescriptor ?parent . } }'
        count_query=prefix+'SELECT (COUNT(*) AS ?count) WHERE { SELECT DISTINCT ?descriptor ?parent ?concept ?term ?label '+where+' }'
        counts=read(family.get('count'),count_query)
        value=counts[0].get('count',{}) if len(counts)==1 else {}
        if (type(value) is not dict or value.get('type') != 'literal' or value.get('datatype') != 'http://www.w3.org/2001/XMLSchema#integer'
                or not re.fullmatch(r'[1-9]\d*',str(value.get('value')))):
            raise ValidationError('The independent conditional row count is unresolved.')
        count=int(value['value'])
        inventory_query=prefix+'SELECT DISTINCT ?descriptor WHERE { ?descriptor meshv:broaderDescriptor* <'+root+'> . } ORDER BY ?descriptor LIMIT 1000'
        inventory=read(family.get('inventory'),inventory_query)
        descriptors=[identity(row,'descriptor','D') for row in inventory]
        if (not 1 <= count <= 8192 or not 1 <= len(descriptors) < 1000
                or descriptors != sorted(set(descriptors)) or root not in descriptors):
            raise ValidationError('The complete conditional descriptor inventory exceeds its bound.')
        pages=family.get('pages')
        if type(pages) is not list or len(pages) != (count+999)//1000:
            raise ValidationError('A counted conditional terminology page is missing.')
        rows=[]
        for offset,page in enumerate(pages):
            query=prefix+'SELECT DISTINCT ?descriptor ?parent ?concept ?term ?label '+where+' ORDER BY ?descriptor ?parent ?concept ?term ?label LIMIT 1000 OFFSET '+str(offset*1000)
            part=read(page,query)
            if len(part) != min(1000,count-offset*1000):
                raise ValidationError('The conditional terminology response was truncated.')
            rows.extend(part)
        tuples=[];parents={};concepts={};terms={}
        for row in rows:
            if set(row) not in ({'descriptor','concept','term','label'},{'descriptor','parent','concept','term','label'}):
                raise ValidationError('The conditional query row has an unexpected predicate.')
            descriptor=identity(row,'descriptor','D');concept=identity(row,'concept','M');term=identity(row,'term','T')
            parent=identity(row,'parent','D') if 'parent' in row else ''
            label=row.get('label',{})
            if (type(label) is not dict or label.get('type') != 'literal' or label.get('xml:lang') != 'en'
                    or type(label.get('value')) is not str or not 1 <= len(label['value']) <= 180):
                raise ValidationError('A conditional terminology term is unresolved.')
            label=label['value'];tuples.append((descriptor,parent,concept,term,label))
            parents.setdefault(descriptor,set()).add(parent)
            concepts.setdefault(concept,set()).add(label)
            if term in terms and terms[term] != label:
                raise ValidationError('A conditional terminology term has conflicting labels.')
            terms[term]=label
        if tuples != sorted(set(tuples)) or set(parents) != set(descriptors):
            raise ValidationError('The conditional pages do not match their complete ordered inventory.')
        connected={}
        def reaches(key,path):
            if key in connected:return connected[key]
            if key in path or len(path)>len(parents):
                raise ValidationError('The conditional descriptor graph is cyclic.')
            choices=parents[key].intersection(parents)
            outcomes=[reaches(parent,path|{key}) for parent in choices]
            connected[key]=(key==root or any(outcomes))
            return connected[key]
        if any(not reaches(key,set()) for key in parents):
            raise ValidationError('A conditional descriptor is disconnected from its claimed family.')
        result[root]={'descriptors':sorted(parents),'concepts':{key:sorted(values) for key,values in concepts.items()},
            'rows':count,'term_count':len(terms)}
    return result


def _term_forms(terms, *, inflections=False):
    """Literal terms, ordinary disease plural, and explicit synonym abbreviations."""
    from .coding_engine import norm
    result = {norm(term) for term in terms}
    for term in terms:
        value = norm(term)
        if value.endswith((' diseases', ' disorders')):
            result.add(value[:-1])
        abbreviation = re.fullmatch(r'([A-Z]{2,10})\s*\(([^()]+)\)', term)
        if abbreviation and norm(abbreviation[2]) in result:
            result.add(abbreviation[1].casefold())
    if inflections:
        # Recognition can only retain a hold. These finite ordinary number
        # inflections never create a positive clinical subtype or code route.
        for term in tuple(result):
            words=term.split();last=words[-1];variants=set()
            if last.endswith('sis'):variants.add(last[:-2]+'es')
            elif last.endswith('ies'):variants.add(last[:-3]+'y')
            elif last.endswith('s') and not last.endswith(('ss','us')):variants.add(last[:-1])
            elif last.endswith(('ch','sh','x','z')):variants.add(last+'es')
            elif len(last)>1 and last.endswith('y') and last[-2] not in 'aeiou':variants.add(last[:-1]+'ies')
            else:variants.add(last+'s')
            result.update(' '.join([*words[:-1],value]) for value in variants)
    return result


def _causal_account_reference(prefix, names, finding):
    """Bind unresolved causal predicates to a clinical account, not a token.

    A pronoun or generic account noun cannot prove that the cause belongs to
    another finding. A release requires a complete, positively separate named
    account; unknown/negated modifiers keep the link unresolved. This function
    can only retain a hold, never establish a condition or anatomical subtype.
    """
    head = r'(?:symptoms?|conditions?|disorders?|problems?|difficult(?:y|ies)|complaints?|findings?|illness(?:es)?|etiolog(?:y|ies)|aetiolog(?:y|ies)|causes?)'
    determiner = r'(?:a|an|the|this|that|these|those|her|his|their|its)'
    topics=set()
    for name in names:
        for ending in (finding,'disorders','disorder','conditions','condition','symptoms','symptom'):
            if name.endswith(' '+ending):topics.add(name[:-len(ending)].strip())
    accounts=list(re.finditer(r'\b'+determiner+r'\s+(?P<modifier>(?:[a-z]+\s+){0,8}?)(?P<head>'+head+r')\b',prefix))
    if any(any(' '+topic+' ' in ' '+account['modifier']+' ' for topic in topics) for account in accounts):
        return True
    # The entire subject must make the exclusion. Searching for "unrelated"
    # inside a modifier would wrongly release "possibly/not unrelated".
    # The separately named topic is a single nominal; qualifications or extra
    # predicates are deliberately outside this bounded positive grammar.
    subject = r'(?:(?:the patient|she|he|they)\s+(?:has|have)\s+(?:a|an|the)\s+|'+determiner+r'\s+)'
    separate = re.fullmatch(subject+r'(?:unrelated|separate|different)\s+(?P<topic>[a-z]+)\s+'+head+
        r'(?:\s+(?:is|are|was|were|has|have|had|may|might|could|be|been))*\s*',prefix)
    if separate and not separate['topic'].endswith('ly') and not re.fullmatch(
            r'no|not|never|possible|probable|potential|suspected|uncertain|unconfirmed|questionable|'
            r'conjectured|unsubstantiated|hypothetical|reported|quoted|unverified|fabricated|alleged',separate['topic']):
        return False
    for account in accounts:
        # An explicit complement owns an independently named topic: "the
        # etiology of her wrist condition" does not refer to this finding.
        if re.match(r'\s+of\b',prefix[account.end():]):
            continue
        if re.search(r'\bof\s+$',prefix[:account.start()]) and account['modifier'].strip():
            continue
        return True
    if not accounts and re.search(r'\b'+head+r'\b',prefix):
        return True
    # Bare/deictic anaphors have no independently named alternative referent.
    return bool(re.match(r'^(?:it|this|that|these|those|they|them)\b',prefix.strip()))


def _causal_account_segments(text):
    """Read the finding side of passive, onset and active causal predicates.

    A clinical account can be either the subject or the direct object. In
    particular, the object of "attributes <account> to" cannot disappear
    behind the reporting subject. These are hold-only relationship cues.
    """
    segments=[]
    relationship = re.search(r'\b(?:following|follows|followed|due to|secondary to|caused by|'
        r'causal|causative|sequelae?|post[- ]event|consequence|result(?:s|ed|ing)? from|'
        r'effect of|complication of|attribut\w*|relat\w* to|link\w* to|associat\w* with|'
        r'induced by|precipitated by|triggered by|brought on by|in the (?:setting|context) of)\b',text)
    onset = re.search(r'\b(?:began|started|developed|arose|emerged|appeared|commenced|'
        r'originated|occurred|came|onset)\b[^.;]*\b(?:after|since|following|with)\b',text)
    if relationship or onset:
        segments.append(text[:min(m.start() for m in (relationship,onset) if m)])
    associations = r'(?:attribut(?:e|es|ed|ing)|relat(?:e|es|ed|ing)|links?|linked|linking|'
    associations += r'associat(?:e|es|ed|ing)|ascrib(?:e|es|ed|ing)|connects?|connected|connecting)'
    for active in re.finditer(r'\b'+associations+r'\s+(?P<account>.+?)\s+(?:to|with)\b',text):
        segments.append(active['account'])
    causes = r'(?:caus(?:e|es|ed|ing)|triggers?|triggered|triggering|precipitat(?:e|es|ed|ing)|'
    causes += r'induc(?:e|es|ed|ing)|brought on|brings? on|bringing on|results? in|resulted in|'
    causes += r'resulting in|leads? to|led to|leading to|gives? rise to|gave rise to|giving rise to)'
    for active in re.finditer(r'\b'+causes+r'\s+(?P<account>.+)',text):
        segments.append(active['account'])
    return segments


def conditional_following_resolution(instruction, notes, concept, reference, selected_codes):
    """Resolve a complete optional sequencing condition, never generic codeFirst.

    No causative disease is inferred from the symptom. Recognized possible,
    historical or current causes remain held, as does a source relationship
    whose wording is outside the bounded condition vocabulary.
    """
    from . import coding_engine as engine
    if instruction.get('kind') != 'codeFirst' or not _guideline_bound(reference):
        return None
    match = re.fullmatch(r'\s*,?\s*if applicable,\s*(?P<finding>[A-Za-z -]+) following '
        r'(?P<cause>[A-Za-z -]+)\s*\((?P<category>[A-Z]\d{2})\. with final characters -(?P<suffix>\d{2})\)\s*',
        instruction.get('text',''), re.I)
    if not match:
        return None
    finding, cause = engine.norm(match['finding']), engine.norm(match['cause'])
    if finding not in engine.anchors(concept):
        return None
    raw, relations = load()
    descriptors = {}
    for row in relations:
        descriptors[row['descriptor_id']] = row
    roots = [row for row in descriptors.values()
             if cause in _term_forms(row['concepts'][row['preferred_concept_id']]['terms'])]
    if len(roots) != 1:
        return None
    vocabulary=condition_families(raw).get(roots[0]['descriptor_id'])
    if vocabulary is None:
        return None
    related = set(vocabulary['descriptors'])
    cause_terms = set()
    for terms in vocabulary['concepts'].values():
        cause_terms.update(_term_forms(terms,inflections=True))
    # The Index's complete causal branch adds its official cause vocabulary.
    # Missing siblings fail closed, as for NEC classification itself.
    lookup = engine.index_lookup(reference)
    heads = [row for row in reference.index if not row.get('parent_id') and engine.norm(row.get('term','')) == finding]
    if len(heads) != 1:
        return None
    _, family = _family(reference, heads[0])
    causal = set()
    for row in family:
        parent = lookup.get(row.get('parent_id'))
        if parent and (engine.norm(parent.get('term','')) == 'following' or parent['id'] in causal):
            causal.add(row['id'])
            words = set(engine.norm(row.get('term','')).split()) - engine.ROUTE_WORDS - {'specified','nec','disease'}
            cause_terms.update(words)
    if not causal:
        return None
    category = match['category'].upper()
    if (not any(ref.get('start') == category and ref.get('kind') == 'code_or_category'
                for ref in instruction.get('references', []))
            or not any((lookup[key].get('code') or '').replace('.','').startswith(category)
                and (lookup[key].get('code') or '').endswith(match['suffix']) for key in causal)):
        return None
    if any(code.replace('.','').startswith(category) for code in selected_codes):
        return None
    from .clinical_source_context import source_context, SOURCE_GOVERNANCE_PROFILE
    from .generation import source_units
    units,_ = source_units(notes,[]); scope = source_context(notes,units,profile=SOURCE_GOVERNANCE_PROFILE)
    inspected = []
    for unit in units:
        row = scope['units'][unit['start']]
        # Historical patient disease may cause a current sequela. It must not
        # be discarded merely because the causative event preceded this visit.
        foreign = re.fullmatch(r'(?:(?:her|his|their|the patient s)\s+)?'
            r'(?:mother|father|sister|brother|relative)\s+[^;]+', engine.norm(unit['quote']))
        if row['subject'] == 'foreign' or foreign and not re.search(r'\b(?:and|but|patient|she|he|they)\b', foreign[0]):
            continue
        text = engine.norm(unit['quote'])
        hits = [term for term in cause_terms if ' '+term+' ' in ' '+text+' ']
        if hits:
            if row['subject'] != 'patient' or row['timing'] != 'current' or row['issues']:
                return None
            # Complete simple absence is allowed; unknown qualifications,
            # historical events and uncertain cause statements stay held.
            absent = any(re.fullmatch(r'(?:(?:the patient|she|he|they)\s+)?'
                r'(?:has no|have no|denies|no)\s+(?:history of\s+)?'+re.escape(term),text) for term in hits)
            if not absent:
                return None
            inspected.append(engine.evidence_span(notes,unit['quote']))
        # An unresolved relationship cannot disappear just because its cause
        # is outside the terminology projection. Causal nouns/adjectives and
        # onset linked to an event are obligations, not disease assertions.
        segments=_causal_account_segments(text)
        if segments:
            names=engine.anchors(concept)
            named = any(' '+name+' ' in ' '+text+' ' for name in names)
            if named or any(_causal_account_reference(segment,names,finding) for segment in segments):
                return None
        if re.search(r'\b(?:history of|had|has|with)\s+[A-Z]{2,10}\b',unit['quote']):
            return None
    return dict(outcome='not_applicable', basis='No supported or unresolved source condition for this optional sequencing instruction within the cited complete Index branch and bounded clinical terminology vocabulary.',
        source_sha256=hashlib.sha256(notes.encode()).hexdigest(), authority_sha256=RESOURCE_SHA256,
        guidelines_sha256=GUIDELINES_SHA256,
        authority_version=raw['version'], attribution=raw['attribution'], coverage=raw['coverage'],
        instruction_id=instruction['id'], condition_finding=finding, condition_cause=cause,
        condition_descriptor_id=roots[0]['descriptor_id'], related_descriptor_ids=sorted(related),
        conditional_vocabulary={'descriptors':len(related),'concepts':len(vocabulary['concepts']),
            'terms':vocabulary['term_count'],'counted_rows':vocabulary['rows'],'purpose':'hold-only',
            'matching':'Authoritative terms and explicit synonym abbreviations, with bounded ordinary number inflections for hold-only recognition.'},
        index_condition_entry_ids=sorted(causal), inspected_negative_source=inspected,
        limitation='Bounded source applicability analysis, not a claim that all possible causes or every clinical synonym are absent.')


def _family(reference, entry):
    from . import coding_engine as engine
    lookup = engine.index_lookup(reference)
    head = entry; seen = set()
    while head.get('parent_id'):
        if head['id'] in seen or head['parent_id'] not in lookup:
            raise ValidationError('The NEC Index ancestry is incomplete.')
        seen.add(head['id']); head = lookup[head['parent_id']]
    result = []; pending = [head['id']]; seen = set()
    while pending:
        key = pending.pop(0)
        if key in seen or key not in lookup or len(seen) >= 2048:
            raise ValidationError('The complete NEC Index family is unresolved.')
        row = lookup[key]; seen.add(key); result.append(row)
        for child in row.get('children', []):
            if child not in lookup or lookup[child].get('parent_id') != key:
                raise ValidationError('An NEC sibling route is absent from the projection.')
            pending.append(child)
    return head, result


def prove(reference, entry, concept, notes, *, source_contract):
    """Return a recomputable clinical/Index proof, or no NEC permission.

    A complete authoritative child term must itself be affirmed. Source-visible
    sibling qualifiers (including a fragment of a multiword branch) veto NEC
    when their relationship is unresolved. Different strings alone never prove
    that two source qualifiers are clinically disjoint.
    """
    from . import coding_engine as engine
    if (source_contract != engine.CURRENT_SOURCE_CONTRACT
            or engine.norm(entry.get('term', '')) != 'specified nec' or not _guideline_bound(reference)):
        return None
    head, family = _family(reference, entry)
    # Only a direct NEC branch is handled; causal/manifestation chains retain
    # all existing obligations rather than being reduced to an adjective.
    if entry.get('parent_id') != head['id'] or entry.get('requires_review'):
        return None
    raw, relations = load()
    head_terms = {engine.norm(t) for t in engine.index_head_terms(head,
        reference.tabular['codes'].get(head.get('code'), ''))}
    for relation in relations:
        if relation['descriptor_id'] not in raw['nec_relation_roots']:
            continue
        parent_terms = relation['parent']['terms']
        if not head_terms.intersection(engine.norm(t) for t in parent_terms):
            continue
        modifiers = []
        for other in relation['concepts'].values():
            for term in other['terms']:
                for parent in parent_terms:
                    if engine.norm(term).endswith(' ' + engine.norm(parent)):
                        modifiers.append(engine.norm(term)[:-len(engine.norm(parent))].strip())
        for term in relation['child']['terms']:
            if not engine.affirmative_word(concept['evidence'], term):
                continue
            checked = {**concept, 'term':term,
                'index_terms':list(dict.fromkeys([*relation['child']['terms'], *parent_terms]))}
            subtypes = engine.index_subtypes(reference, {**concept, 'term':head['term'], 'index_terms':[head['term']]},
                source_contract=source_contract)
            qualifiers = [row['qualifier'] for row in subtypes] + modifiers
            if (engine.current_source_scope_errors(notes, checked, source_contract=source_contract)
                    or engine.source_disposition(checked, notes, qualifiers=qualifiers,
                        source_contract=source_contract)[0] != 'eligible'):
                continue
            # A second sibling or unparsed compound cannot be hidden by the
            # recognized child phrase. Bind the words to an actual mention of
            # the parent condition, never an unrelated examination sentence.
            ambiguous = False
            parent_concept = {**concept, 'term':head['term'], 'index_terms':parent_terms}
            from .clinical_source_context import source_context, owned_current, SOURCE_GOVERNANCE_PROFILE
            from .generation import source_units
            units, _ = source_units(notes, [])
            scope = source_context(notes, units, profile=SOURCE_GOVERNANCE_PROFILE)
            inspected = []
            for sibling in family:
                if sibling['id'] in (head['id'], entry['id']):
                    continue
                inspected.append(sibling['id'])
                words = set(engine.norm(sibling.get('term', '')).split()) - engine.ROUTE_WORDS - {'specified','nec','phase'}
                if not words:
                    continue
                for unit in units:
                    if not owned_current(scope, unit):
                        continue
                    for clause, before, after in engine.mention_clauses(unit['quote'], parent_concept):
                        text = engine.norm(clause)
                        for word in words:
                            for match in re.finditer(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text):
                                prefix = text[:match.start()]
                                # An explicit adjacent absence can exclude a
                                # sibling; unknown/uncertain relationships hold.
                                if re.search(r'\b(?:no|not|without|denies|denied)\s+(?:(?:any|the|a|an)\s+)*$', prefix):
                                    continue
                                ambiguous = True
            if ambiguous:
                continue
            # The ordinary source/Index checks still govern the main term.
            if engine.index_route_errors(head, checked, engine.index_lookup(reference),
                    source_contract=source_contract):
                continue
            proof = dict(format=FORMAT, authority_version=raw['version'], authority_sha256=RESOURCE_SHA256,
                guidelines_sha256=GUIDELINES_SHA256,
                attribution=raw['attribution'], coverage=raw['coverage'], descriptor_id=relation['descriptor_id'],
                parent_concept_id=relation['parent']['id'], child_concept_id=relation['child']['id'],
                source_term=term, source=engine.evidence_span(notes, concept['evidence']),
                source_sha256=hashlib.sha256(notes.encode()).hexdigest(),
                index_entry_id=entry['id'], index_family_ids=[row['id'] for row in family],
                inspected_sibling_ids=inspected, classification_basis='ICD-10-CM FY2027 I.A.6 and I.A.9',
                inference='Explicit narrower clinical concept plus the complete source and official Index family; MeSH is not an ICD mapping.')
            return checked, proof
    return None
