"""Coding consumers of the same checked source graph used for clinical text.

No source-scope parser is called on this contract. Dated classification and
licensed output authority remain separate gates; a graph never supplies codes.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import re

from django.core.exceptions import ValidationError

from . import source_assertion_graph as graph

CONTRACT = 'graph-source-coding-v1'
INPUT_KEY = 'source_interpretation'
CLINICAL_ROLES = ('symptom', 'disease', 'family_history', 'personal_history')
HISTORY_ROLES = ('family_history','personal_history')


def enabled(run):
    return getattr(run, 'config', {}).get('clinical_source_contract') == CONTRACT


def need(value, code):
    if not value:
        raise ValidationError('Checked source coding: ' + code, code=code)


def snapshot(encounter):
    """One explicit generation supplies all graph destinations; never latest()."""
    from .source_interpretation_store import load_for_answer
    from .semantic_review import definitions_for, validate_answer
    from . import word_contract
    fields = encounter.template_version.fields
    answers = encounter.answers
    # A newly created encounter has no generated document to interpret yet.
    # The coding service independently marks it documentation_pending and
    # refuses requests/approvals until answers exist. Reading that empty panel
    # must not require a generation lineage that has not been created.
    if not answers:
        return None
    version = encounter.template_version
    graph_answers = any(type(a) is dict and a.get('fact_scope_contract') == graph.CONTRACT for a in answers.values())
    inline_graph = (word_contract.has_inline(version)
        and version.preparation.config.get(word_contract.CONFIG_KEY) == word_contract.GRAPH_PROFILE)
    if not (graph_answers or inline_graph or any(type(d) is dict and d.get('version') == 4
               for d in version.semantic_definitions.values())):
        return None
    # Inline Word definitions are sealed in preparation metadata, not copied
    # into semantic_definitions. Markers trigger validation; only this approved
    # reader can establish the actual component definitions and destinations.
    definitions = definitions_for(version)
    need(bool(definitions) and all(type(d) is dict and d.get('version') == 4 for d in definitions.values()),
         'graph_requires_approved_components')
    need(set(answers) == {f['key'] for f in fields} and bool(fields), 'complete_graph_answers')
    lineage = None
    for field in fields:
        answer = answers[field['key']]
        need(answer.get('fact_scope_contract') == graph.CONTRACT, 'mixed_generation_contracts')
        current = answer.get('source_interpretation')
        if lineage is None:
            lineage = current
        need(graph.same(current, lineage), 'mixed_generation_lineage')
        validate_answer(encounter, field, answer, definitions)
    return load_for_answer(encounter, fields[0], definitions[fields[0]['key']], answers[fields[0]['key']])


def source(run):
    """Validate frozen source/revision identity without a provider or database."""
    need(enabled(run), 'wrong_contract')
    interpretation = run.inputs.get(INPUT_KEY)
    need(type(interpretation) is dict, 'missing_source_interpretation')
    fingerprint = graph.digest({'contract':run.config.get('clinical_source_contract'),'inputs':run.inputs})
    cached = getattr(run,'_checked_graph_projection',None)
    if cached is not None and cached[0] == fingerprint:
        need(graph.digest(cached[2]) == cached[1], 'request_cache_changed')
        return deepcopy(cached[2])
    projected = graph.projection(interpretation)
    identity = projected['identity']
    need(interpretation['notes'] == run.inputs['notes'], 'source_bytes_changed')
    for key in ('patient_id', 'encounter_id', 'department_id', 'service_date', 'template_version_id'):
        need(identity[key] == run.inputs.get(key), 'input_' + key)
    patient = run.inputs.get('patient_identity', {})
    need(identity['patient_display_name'] == patient.get('display_name')
        and identity['patient_reference'] == patient.get('reference'), 'registry_binding')
    template = run.inputs.get('template', {})
    need(template.get('fields_sha256') == graph.digest(interpretation['fields'])
        and template.get('definitions_sha256') == graph.digest(interpretation['definitions']), 'template_binding')
    lineage = {'generation_job_id':identity['generation_job_id'], 'interpretation_sha256':projected['interpretation_sha256']}
    answers = run.inputs.get('answers', {})
    need(set(answers) == {f['key'] for f in interpretation['fields']}
        and all(type(a) is dict and graph.same(a.get('source_interpretation'), lineage) for a in answers.values()),
        'answer_lineage')
    run._checked_graph_projection = (fingerprint,graph.digest(projected),deepcopy(projected))
    return projected


def _holds(projected, identifier, *, office_em=False):
    return [h for h in projected['adjudication']['holds'] if identifier in h['assertion_ids']
            and (office_em or h.get('consumer_scope') != 'office_em')]


def _checked(projected, category, identifier):
    return projected['adjudication']['checked'][category][identifier]['verdict'] == 'confirmed'


def assertion_errors(projected, assertion, *, subject='patient', relevant=True):
    errors = []
    if not _checked(projected, 'assertions', assertion['id']): errors.append('assertion_not_confirmed')
    if _holds(projected, assertion['id']): errors.append('source_dependency_unresolved')
    if assertion['subject'] != subject: errors.append('subject_not_' + subject)
    if assertion['encounter'] != 'current': errors.append('encounter_not_current')
    if assertion['temporality'] != 'current' and not (assertion['consumer_role'] in ('personal_history','family_history')
            and assertion['temporality'] == 'past'): errors.append('predicate_not_current')
    if assertion['polarity'] != 'affirmed': errors.append('assertion_not_affirmed')
    if assertion['certainty'] != 'established': errors.append('assertion_not_established')
    if relevant and assertion['clinically_relevant'] is not True: errors.append('encounter_relevance_not_established')
    return errors


def _own_classification_refs(projected, assertion):
    # Units and context refs locate the assertion; they do not transfer another
    # person's or event's qualifiers into this checked clinical predicate.
    refs = assertion['predicate_refs'] + assertion['qualifier_refs']
    refs += [projected['graph']['facts'][key]['value_evidence'] for key in assertion['fact_ids']]
    return [deepcopy(row) for _,row in sorted({(r['start'],r['end'],r['quote']):r for r in refs}.items())]


def _classification_context(projected, assertion):
    """Only checked incoming qualification edges extend this classification."""
    g = projected['graph']; refs = []; atoms = []; dependencies = []; errors = []; visited = set(); active = set()
    incoming = {}
    for relation in g['relationships'].values():
        if relation['kind'] == 'qualifies':
            for target in relation['target_assertion_ids']:
                incoming.setdefault(target, []).append(relation)
    def visit(current):
        key = current['id']
        if key in active:
            errors.append('qualification_cycle:' + key)
            return
        if key in visited: return
        active.add(key)
        refs.extend(_own_classification_refs(projected, current))
        atom=current['consumer_ref']
        if current['consumer_role'] in (*CLINICAL_ROLES,'condition_modifier'):
            if atom is None:
                errors.append('classification_atom_missing:'+key)
            else:
                atoms.append({'assertion_id':key,'polarity':current['polarity'],'reference':deepcopy(atom),
                    'consumer_role':current['consumer_role'],
                    'assertion_check':deepcopy(projected['adjudication']['checked']['assertions'][key])})
        for relation in incoming.get(key, []):
            qualifier = g['assertions'][relation['source_assertion_id']]
            problems = []
            if not _checked(projected, 'relationships', relation['id']): problems.append('relationship_not_confirmed')
            if not _checked(projected, 'assertions', qualifier['id']): problems.append('qualifier_not_confirmed')
            if _holds(projected, qualifier['id']): problems.append('qualifier_dependency_unresolved')
            if qualifier['subject'] != assertion['subject']: problems.append('qualifier_owner_not_current_subject')
            if qualifier['encounter'] != 'current' or qualifier['temporality'] != 'current':
                problems.append('qualifier_event_not_current')
            if qualifier['certainty'] != 'established': problems.append('qualifier_not_established')
            if qualifier['polarity'] not in ('affirmed', 'negated'): problems.append('qualifier_polarity_unresolved')
            if qualifier['consumer_role'] != 'condition_modifier': problems.append('qualifier_role_unresolved')
            dependencies.append({'relationship':deepcopy(relation), 'assertion':deepcopy(qualifier),
                'relationship_check':deepcopy(projected['adjudication']['checked']['relationships'][relation['id']]),
                'assertion_check':deepcopy(projected['adjudication']['checked']['assertions'][qualifier['id']]),
                'errors':problems})
            errors.extend(relation['id'] + ':' + problem for problem in problems)
            if not problems: visit(qualifier)
        active.remove(key); visited.add(key)
    visit(assertion)
    unique = {(r['start'],r['end'],r['quote']):r for r in refs}
    # Do not repeat an inner value as a new affirmative phrase after its full
    # negative predicate. All literal facts remain in the graph/dependency proof.
    maximal = [r for key,r in sorted(unique.items()) if not any(
        outer['start'] <= r['start'] and r['end'] <= outer['end'] and other != key
        for other,outer in unique.items())]
    # Contrary checked claims remain a classification question. Neither a more
    # specific code nor its default parent may choose which claim is true.
    authority=CheckedClassification(atoms)
    for positive in authority.positive_quotes:
        for negative in authority.negative_quotes:
            if authority.contains(positive,negative):
                errors.append('opposite_classification_atoms')
    return {'references':maximal, 'atoms':atoms, 'dependencies':dependencies,
            'errors':list(dict.fromkeys(errors))}


class CheckedClassification:
    """Reference vocabulary over checked nominal spans; never prose polarity.

    Constructed only after source() has replayed the immutable interpretation
    and the dependency walk has checked each owner/event/edge. Full clinical
    predicates remain separate evidence and cannot grant a lexical qualifier.
    """
    def __init__(self, atoms):
        self.atoms=atoms
        self.positive_quotes=[a['reference']['quote'] for a in atoms if a['polarity']=='affirmed']
        self.negative_quotes=[a['reference']['quote'] for a in atoms if a['polarity']=='negated']
        self.positive_text='\n'.join(self.positive_quotes)

    @staticmethod
    def contains(quote, term):
        from .coding_engine import norm
        phrase=norm(term)
        return bool(phrase and re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',norm(quote)))

    def affirmed(self, term):
        return any(self.contains(quote,term) for quote in self.positive_quotes)

    def supported(self, words, *, polarity='affirmed'):
        quotes=self.positive_quotes if polarity=='affirmed' else self.negative_quotes
        # A multiword branch must occur in one checked nominal atom. Distinct
        # anatomical findings cannot donate individual words to a new phrase.
        return bool(words) and any(all(self.contains(quote,word)
            or word=='colonic' and self.contains(quote,'colon')
            or word=='gastroesophageal' and self.contains(quote,'gastro oesophageal')
            for word in words) for quote in quotes)

    def laterality(self, side, site):
        from .coding_engine import norm
        for atom in self.atoms:
            if atom['polarity']!='affirmed':continue
            quote=atom['reference']['quote']
            if self.contains(quote,side) and re.search(r'\b'+re.escape(site)+r's?\b',norm(quote)):
                return True
            # An explicit side modifier belongs to this root via checked
            # qualification; a side attached to a different site does not.
            if atom['consumer_role']=='condition_modifier' and norm(quote)==side and any(
                    a['polarity']=='affirmed' and a['consumer_role'] in CLINICAL_ROLES
                    and re.search(r'\b'+re.escape(site)+r's?\b',norm(a['reference']['quote']))
                    for a in self.atoms):
                return True
        return False


def _evidence(projected, assertion):
    selected = set(assertion['source_unit_ids'])
    return [deepcopy(u) for u in projected['graph']['units'] if u['id'] in selected]


def identity_blockers(run):
    projected = source(run)
    names = [a for a in projected['graph']['assertions'].values() if a['identity_role'] == 'patient_name']
    good = []
    for assertion in names:
        if assertion_errors(projected, assertion, relevant=False):
            return ['The independently checked source patient identity remains unresolved.']
        values = [projected['graph']['facts'][key]['value_evidence']['quote'] for key in assertion['fact_ids']]
        if values != [projected['identity']['patient_display_name']]:
            return ['The exact documented source patient identity differs from this encounter.']
        good.append(assertion['id'])
    return [] if good else ['The complete checked source does not establish this patient’s identity.']


def _literal(text, term):
    return bool(term and re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I))


def _literal_span_in_reference(evidence, term, span):
    """Bind the cited occurrence, not the size of the clinical rendering fact."""
    return bool(term and any(span['start'] <= evidence['start'] + match.start()
        and evidence['start'] + match.end() <= span['end']
        for match in re.finditer(r'(?<!\w)' + re.escape(term) + r'(?!\w)', evidence['quote'], re.I)))


def _concept(projected, assertion, term, identifier, classification):
    role = assertion['consumer_role']
    refs = classification['references']
    return {'id':identifier, 'term':term, 'index_terms':[term],
        'evidence':'\n'.join(r['quote'] for r in refs), 'classification_evidence':refs,
        'classification_dependencies':classification['dependencies'],
        'classification_atoms':classification['atoms'], 'consumer_ref':deepcopy(assertion['consumer_ref']),
        'source_units':_evidence(projected,assertion),
        'kind':{'symptom':'symptom','disease':'diagnosis','family_history':'family_history',
                'personal_history':'personal_history'}[role],
        'certainty':'confirmed', 'temporality':'current', 'subject':'patient', 'relevant':True,
        'missing_detail':'', 'integral_to':'', 'source_assertion_id':assertion['id'],
        'source_fact_ids':list(assertion['fact_ids']),
        'source_fact_id':next((key for key in assertion['fact_ids']
            if projected['graph']['facts'][key]['value_evidence']['start']<=assertion['consumer_ref']['start']
            and assertion['consumer_ref']['end']<=projected['graph']['facts'][key]['value_evidence']['end']),None),
        'interpretation_sha256':projected['interpretation_sha256']}


def history_role(entry, lookup):
    """Only the dated History -> family/personal taxonomy has this adapter."""
    from .coding_engine import norm
    chain=[];visited=set();node=entry
    while node:
        need(node['id'] not in visited and len(visited)<33,'history_reference_ancestry')
        visited.add(node['id']);chain.append(node)
        node=lookup.get(node.get('parent_id'))
    if len(chain)<2 or norm(chain[-1].get('term',''))!='history':return None
    return {'family':'family_history','personal':'personal_history'}.get(norm(chain[-2].get('term','')))


def _history_terms(entry, lookup):
    from .coding_engine import norm, index_head_terms, TAXONOMY_HEADS
    # Branch vocabulary comes from this dated reference. The typed role supplies
    # History/family/personal, while the nominal source must supply the condition.
    result=[];node=entry
    while node.get('parent_id') in lookup:
        for term in index_head_terms(node):
            if norm(term) not in TAXONOMY_HEADS|{'family','personal'}:result.append(term)
        node=lookup[node['parent_id']]
    return list(dict.fromkeys(result))


def icd_source(run, reference, proposal, selected_codes, *, diagnostics=None, required_assertion_id=None):
    """Truth/ownership from the graph; classification from the dated reference."""
    from . import coding_engine as engine, coding_terminology
    from .corti_coding import _diagnostic_attempt, _diagnostic_gate, _diagnostic_finish
    projected = source(run); notes = run.inputs['notes']; g = projected['graph']
    lookup = engine.index_lookup(reference)
    matches = [e for e in reference.index if e.get('code') == proposal['code'] and not e.get('requires_review')]
    if not matches:
        attempt = _diagnostic_attempt(diagnostics, notes)
        _diagnostic_gate(attempt, 'index_candidate', 'failed', {'reason':'No admissible dated Index entry for the selected code.'})
        for gate in ('provider_span','graph_fact_binding','checked_source_assertion','checked_classification_dependencies','tabular_instructions','index_route','specificity'):
            _diagnostic_gate(attempt,gate,'not_evaluated',{'blocked_by':'index_candidate'})
    for entry in matches:
        head = entry
        while head.get('parent_id') in lookup: head = lookup[head['parent_id']]
        description = proposal['terminology']['description']
        history=history_role(entry,lookup)
        terms=_history_terms(entry,lookup) if history else engine.index_head_terms(head, description)
        for term in terms:
            if engine.norm(term) in engine.TAXONOMY_HEADS: continue
            for span in proposal['evidence']:
                attempt = _diagnostic_attempt(diagnostics, notes, entry=entry, term=term, span=span)
                valid = (span.get('status') == 'valid' and span.get('context_index') == 0
                    and type(span.get('start')) is int and type(span.get('end')) is int
                    and notes[span['start']:span['end']] == span.get('text'))
                _diagnostic_gate(attempt, 'provider_span', 'passed' if valid else 'failed', {'span':deepcopy(span)})
                if not valid:
                    for gate in ('graph_fact_binding','checked_source_assertion','checked_classification_dependencies','tabular_instructions','index_route','specificity'):
                        _diagnostic_gate(attempt,gate,'not_evaluated',{'blocked_by':'provider_span'})
                    continue
                assertions = [a for a in g['assertions'].values() if a['consumer_ref'] is not None
                    and _literal_span_in_reference(a['consumer_ref'],term,span)
                    and (required_assertion_id is None or a['id']==required_assertion_id)]
                _diagnostic_gate(attempt, 'graph_fact_binding', 'passed' if assertions else 'not_applicable',
                    {'assertion_ids':[a['id'] for a in assertions],
                     'consumer_refs':[deepcopy(a['consumer_ref']) for a in assertions],
                     'reason':'The cited occurrence must contain the independently checked nominal condition.'})
                for assertion in assertions:
                    proof = _diagnostic_attempt(diagnostics, notes, entry=entry, term=term, span=span)
                    errors = assertion_errors(projected, assertion)
                    if assertion['consumer_role'] not in CLINICAL_ROLES: errors.append('not_a_clinical_coding_assertion')
                    if history and assertion['consumer_role']!=history:errors.append('history_taxonomy_role_mismatch')
                    _diagnostic_gate(proof, 'checked_source_assertion', 'failed' if errors else 'passed',
                        {'errors':errors, 'assertion':deepcopy(assertion), 'fact_ids':list(assertion['fact_ids']),
                         'source_units':_evidence(projected,assertion),
                         'interpretation_sha256':projected['interpretation_sha256']})
                    if errors:
                        for gate in ('checked_classification_dependencies','tabular_instructions','index_route','specificity'):
                            _diagnostic_gate(proof,gate,'not_evaluated',{'blocked_by':'checked_source_assertion'})
                        continue
                    classification = _classification_context(projected, assertion)
                    _diagnostic_gate(proof, 'checked_classification_dependencies',
                        'failed' if classification['errors'] else 'passed', classification)
                    if classification['errors']:
                        for gate in ('tabular_instructions','index_route','specificity'):
                            _diagnostic_gate(proof,gate,'not_evaluated',{'blocked_by':'checked_classification_dependencies'})
                        continue
                    concept = _concept(projected, assertion, term, proposal['id'], classification)
                    authority = CheckedClassification(classification['atoms'])
                    # Unresolved conditional classification instructions remain holds. No source regex can discharge them.
                    checked = coding_terminology.validate_code(reference, proposal['code'], selected_codes=selected_codes)
                    errors = list(checked.get('errors', []))
                    if checked.get('description') != description: errors.append('dated_description_mismatch')
                    if not checked['valid'] or checked.get('requires_review'): errors.append('dated_tabular_instructions_unresolved')
                    _diagnostic_gate(proof,'tabular_instructions','failed' if errors else 'passed',checked)
                    route_errors = engine.index_route_errors(entry, concept, lookup, code_description=description,
                        classification=authority)
                    _diagnostic_gate(proof,'index_route','failed' if route_errors else 'passed',{'errors':route_errors})
                    specific = engine.specificity_errors(concept,proposal['code'],description,classification=authority)
                    # A verified, more-specific source fact in this same assertion may not be discarded.
                    for child in reference.index:
                        if child.get('code') == proposal['code'] or not child.get('code') or child.get('requires_review'): continue
                        ancestor = child
                        while ancestor.get('parent_id') in lookup and ancestor['parent_id'] != entry['id']:
                            ancestor = lookup[ancestor['parent_id']]
                        if ancestor.get('parent_id') != entry['id']: continue
                        if not engine.index_route_errors(child,concept,lookup,
                            code_description=reference.tabular['codes'].get(child['code'],''),classification=authority):
                            specific.append('A source-supported narrower dated Index route requires review: '+child['id'])
                    _diagnostic_gate(proof,'specificity','failed' if specific else 'passed',{'errors':specific})
                    if errors or route_errors or specific: continue
                    candidate = {'code':proposal['code'],'system':'ICD-10-CM','entry_id':entry['id'],
                        'description':description,'path':entry.get('path',[]),'release_id':str(reference.release_id),
                        'release_version':reference.release.version,'instructions':checked.get('instructions',[])}
                    return _diagnostic_finish(diagnostics,(concept,candidate,{'disposition':'eligible',
                        'reason':'Independently checked source assertion and dated Index/Tabular route.',
                        'interpretation_sha256':projected['interpretation_sha256'],'assertion_id':assertion['id'],
                        'consumer_ref':deepcopy(assertion['consumer_ref']),'fact_ids':list(assertion['fact_ids'])}))
    if diagnostics is not None and not any(a['failures'] for a in diagnostics['attempts']):
        attempt=_diagnostic_attempt(diagnostics,notes)
        _diagnostic_gate(attempt,'graph_fact_binding','failed',
            {'reason':'No independently checked condition is bound to this selected literal source span.'})
        for gate in ('checked_classification_dependencies','tabular_instructions','index_route','specificity'):
            _diagnostic_gate(attempt,gate,'not_evaluated',{'blocked_by':'graph_fact_binding'})
    return _diagnostic_finish(diagnostics,(None,None,None))


def integral_holds(run, rows):
    projected = source(run); g = projected['graph']; held = {}
    selected = {r.get('concept',{}).get('source_assertion_id'):r for r in rows if r.get('eligible')}
    for rel in g['relationships'].values():
        if rel['kind'] != 'causes' or not _checked(projected,'relationships',rel['id']): continue
        parent = selected.get(rel['source_assertion_id'])
        if parent is None or parent['concept']['kind'] != 'diagnosis': continue
        for target in rel['target_assertion_ids']:
            child = selected.get(target)
            if child and child['concept']['kind'] == 'symptom': held[child['id']] = parent['id']
    return held


def inventory(run):
    from .coding_completeness import CONTRACT as INVENTORY_CONTRACT, reference_terms
    projected = source(run); g = projected['graph']; items, unresolved, excluded = [], [], []
    for assertion in g['assertions'].values():
        role = assertion['consumer_role']
        confirmed = _checked(projected,'assertions',assertion['id']) and not _holds(projected,assertion['id'])
        clinical = role in CLINICAL_ROLES or assertion['kind'] in ('clinical','condition')
        if not clinical and confirmed: continue
        if not clinical and assertion['kind'] not in ('clinical','condition'):
            # A rejected nonclinical/role classification is not permission to drop the unit.
            clinical = not confirmed
        if not clinical: continue
        evidence = [{'start':u['start'],'end':u['end'],'quote':u['quote']} for u in _evidence(projected,assertion)]
        values = [deepcopy(g['facts'][key]['value_evidence']) for key in assertion['fact_ids']]
        # The checked predicate is the clinical obligation. Its duration and
        # other literal parts remain evidence, not separate invented diagnoses.
        atom=assertion['consumer_ref']
        text = atom['quote'] if atom is not None else '\n'.join(value['quote'] for value in values) if values else ' '.join(e['quote'] for e in evidence)
        errors = assertion_errors(projected,assertion)
        if role not in CLINICAL_ROLES: errors.append('clinical_role_unresolved')
        row = {'id':'graph:'+assertion['id'],'condition_text':text,'evidence':deepcopy(evidence),
            'current_evaluation_evidence':deepcopy(evidence) if not errors else [],
            'state':'unresolved','reason':'; '.join(errors),'approved_codes':[],'candidates':[],
            'assertion_id':assertion['id'],'consumer_role':role,'consumer_ref':deepcopy(atom),
            'fact_ids':list(assertion['fact_ids']),'fact_evidence':values,
            'reference_terms':reference_terms(text) if not errors else []}
        # Only confirmed, explicitly inapplicable source can be excluded.
        noncurrent = assertion['subject'] == 'other' or assertion['encounter'] in ('past','future')
        negative = assertion['polarity'] == 'negated' and assertion['certainty'] == 'established'
        if confirmed and (noncurrent or negative or assertion['clinically_relevant'] is False):
            excluded.append(row)
        elif errors:
            unresolved.append(row)
        else:
            items.append(row)
    for key,row in g['unit_coverage'].items():
        if row['disposition'] != 'unknown' and _checked(projected,'unit_coverage',key): continue
        unit = next(u for u in g['units'] if u['id'] == row['source_unit_id'])
        unresolved.append({'id':'graph-unit:'+key,'condition_text':unit['quote'],
            'evidence':[{'start':unit['start'],'end':unit['end'],'quote':unit['quote']}],
            'current_evaluation_evidence':[],'state':'unresolved','reason':'Original source-unit interpretation remains unresolved.',
            'approved_codes':[],'candidates':[],'reference_terms':[],'assertion_id':None,'fact_ids':[], 'fact_evidence':[]})
    need(len(items)+len(unresolved) <= 200, 'source_inventory_bound')
    result = {'contract':INVENTORY_CONTRACT,'source_contract':CONTRACT,
        'source_sha256':g['source_sha256'],'service_date':projected['identity']['service_date'],
        'interpretation_sha256':projected['interpretation_sha256'], 'items':items,'unresolved':unresolved,
        'excluded':excluded,'blockers':identity_blockers(run),
        'reference_terms':sorted({term for row in items for term in row['reference_terms']}),
        'reference_taxonomy_roles':sorted({row['consumer_role'] for row in items if row['consumer_role'] in HISTORY_ROLES}),
        'coverage_limit':'Complete checked source-unit graph. Unknown assertions remain explicit review outcomes; no universal interpretation claim.'}
    need(len(result['reference_terms']) <= 64,'reference_vocabulary_bound')
    result['inventory_sha256'] = graph.digest(result)
    return result


def evaluate(run, reference, *, approved_codes=(), inventory_result=None):
    from . import coding_completeness as completeness, coding_engine as engine, coding_terminology
    inv = inventory(run)
    need(inventory_result is None or graph.same(inv,inventory_result),'inventory_changed')
    need(graph.same(getattr(reference,'completeness_scope',{}).get('taxonomy_roles',[]),inv['reference_taxonomy_roles']),
         'reference_taxonomy_scope_changed')
    lookup, release = completeness._reference(reference,inv,run)
    need(type(approved_codes) in (list,tuple,set,frozenset) and len(approved_codes)<=200,'approved_population')
    approved = set(approved_codes)
    need(all(type(code) is str and code in reference.tabular['codes'] for code in approved),'approved_reference_membership')
    rows = deepcopy(inv['items']+inv['unresolved']); suggestions = []
    for row in rows:
        if not row['current_evaluation_evidence'] or inv['blockers']: continue
        terms = {engine.norm(t) for t in row['reference_terms']}
        roots = {e['id'] for e in reference.index if e.get('parent_id') is None and any(
            engine.norm(t) in terms for t in engine.index_head_terms(e,reference.tabular['codes'].get(e.get('code'),'')))}
        if row.get('consumer_role') in HISTORY_ROLES:
            roots.update(e['id'] for e in reference.index if e.get('parent_id') is None
                and engine.norm(e.get('term',''))=='history')
        codes = sorted({e['code'] for e in reference.index if e.get('code') in reference.tabular['codes']
            and completeness._root(e,lookup)['id'] in roots
            and (engine.norm(completeness._root(e,lookup).get('term',''))!='history'
                 or history_role(e,lookup)==row.get('consumer_role'))})
        if len(codes)>completeness.MAX_CANDIDATES:
            row['reason']='The complete authoritative family exceeds the finite candidate bound.'; continue
        row['authoritative_candidate_count']=len(codes)
        for code in codes:
            proposal = {'id':row['id'],'code':code,'terminology':{'description':reference.tabular['codes'][code]},
                'evidence':[{'context_index':0,'status':'valid','text':e['quote'],'start':e['start'],'end':e['end']}
                            for e in row['evidence']]}
            concept,candidate,checked = icd_source(run,reference,proposal,sorted(approved|{code}),
                required_assertion_id=row['assertion_id'])
            if not candidate or concept['source_assertion_id']!=row['assertion_id'] \
                    or not graph.same(concept['consumer_ref'],row['consumer_ref']) \
                    or not graph.same(concept['source_fact_ids'],row['fact_ids']): continue
            proof = {'contract':completeness.CONTRACT,'source_contract':CONTRACT,'source_sha256':inv['source_sha256'],
                'inventory_sha256':inv['inventory_sha256'],'condition_id':row['id'],'reference':release,
                'candidate':candidate,'source_check':checked,'concept':concept}
            value = {'id':'source:'+graph.digest(proof)[:24],'origin':'saved_source','condition_id':row['id'],
                'system':'ICD-10-CM','code':code,'description':candidate['description'],'eligible':True,'hold_reasons':[],
                'route':' > '.join(candidate['path']),'index_route':candidate,'instructions':candidate['instructions'],
                'evidence':[{'text':e['quote'],'start':e['start'],'end':e['end']} for e in row['evidence']],
                'release':deepcopy(release),'support_digest':graph.digest(proof),'proof':proof}
            row['candidates'].append(value); suggestions.append(value)
        if len(row['candidates']) != 1:
            row['reason']='No unique authoritative source-supported code is established.'
            for value in row['candidates']: value['eligible']=False;value['hold_reasons'].append(row['reason'])
    proposed = approved | {v['code'] for v in suggestions if v['eligible']}
    pseudo = [{'id':v['id'],'eligible':v['eligible'],'concept':v['proof']['concept']} for v in suggestions]
    integral = integral_holds(run,pseudo)
    for row in rows:
        for value in row['candidates']:
            if not value['eligible']: continue
            checked = coding_terminology.validate_code(reference,value['code'],selected_codes=sorted(proposed))
            if value['id'] in integral or not checked['valid'] or checked.get('requires_review'):
                value['eligible']=False;value['hold_reasons'].append('Checked causal relationship or combined dated Tabular instructions require review.')
                row['reason']=value['hold_reasons'][-1]
            else:
                row['state']='covered' if value['code'] in approved else 'review_required'
                row['approved_codes']=[value['code']] if value['code'] in approved else []
    covered = sum(r['state']=='covered' for r in rows); reviewable=sum(r['state']=='review_required' for r in rows)
    result={'contract':completeness.CONTRACT,'bindings':{'source_sha256':inv['source_sha256'],
        'inventory_sha256':inv['inventory_sha256'],'run_id':str(getattr(run,'pk','')),'run_input_digest':getattr(run,'input_digest',''),
        'provider_result_digest':graph.digest(getattr(run,'result',{})),'source_contract':CONTRACT,'reference':release},
        'inventory':rows,'suggestions':suggestions,'excluded':inv['excluded'],'blockers':inv['blockers'],
        'coverage':{'total':len(rows),'covered':covered,'review_required':reviewable,'unresolved':len(rows)-covered-reviewable,
            'complete':bool(rows) and covered==len(rows) and not inv['blockers'],'limit':inv['coverage_limit']}}
    result['support_digest']=graph.digest(result)
    return result


def _date_ref(ref):
    from .corti_semantics import _calendar_day
    if not ref: return None
    parsed=_calendar_day(ref['quote'])
    return parsed.isoformat() if parsed else None


def _minutes(quantity,unit):
    from .semantic_generation import _source_number
    if not quantity or not unit or unit['quote'].strip().casefold() not in ('minute','minutes','min','mins'): return None
    try:
        value=_source_number(quantity['quote'])
        return int(value) if value is not None and value.is_finite() and value==value.to_integral_value() and 0<=value<=1440 else None
    except (ValueError,ArithmeticError): return None


def context_suggestions(run):
    """Independent checked metadata never supplies a time attestation."""
    p=source(run); result={}
    for role,key in (('service_setting','setting'),('patient_status','patient_status'),('em_basis','em_basis')):
        rows=[a for a in p['graph']['assertions'].values() if a['consumer_role']==role]
        values={a['consumer_value'] for a in rows}
        if (rows and len(values)==1 and 'unknown' not in values
            and all(not assertion_errors(p,a,relevant=False) for a in rows)):
            result[key]=next(iter(values))
    return result


def _outside_current_time(projected, assertion):
    """Exclude only independently confirmed, explicitly separate time domains."""
    t = assertion['time']
    if (not _checked(projected,'assertions',assertion['id']) or _holds(projected,assertion['id'])
        or assertion['subject']=='uncertain' or assertion['certainty']!='established'
        or assertion['polarity']!='affirmed' or not t or t['performer']=='unknown'
        or t['performer_ref'] is None): return False
    day = _date_ref(t['date_ref']); service = projected['identity']['service_date']
    if day is None: return False
    event, timing = assertion['encounter'], assertion['temporality']
    if event=='past' and timing=='past' and day<service: return True
    if event=='future' and timing=='future' and day>service: return True
    return event=='current' and timing=='current' and day==service and t['performer'] in ('staff','patient','other')


def office_time_facts(run):
    from .corti_semantics import REQUIRED_TIME_FACTS
    p=source(run);g=p['graph'];facts={};blockers=[]
    potential_time = {a['id'] for a in g['assertions'].values()
        if a['consumer_role'] in ('time_total','time_work','time_exclusion') and not _outside_current_time(p,a)}
    accounts = [account for account in g['time_accounts'].values()
        if not _outside_current_time(p,g['assertions'][account['owner_assertion_id']])]
    account_ids = {account['id'] for account in accounts}
    if any(h.get('consumer_scope')=='office_em' and (potential_time.intersection(h['assertion_ids'])
        or account_ids.intersection(h.get('time_account_ids',[]))) for h in p['adjudication']['holds']):
        blockers.append('Checked office E/M time accounting remains unresolved.')
    def add(key,value,ref):
        row={'key':key,'value':value,'source':'checked source graph','start':ref['start'],'end':ref['end'],'quote':ref['quote']}
        if key in facts and facts[key]['value']!=value: blockers.append('Conflicting checked '+key+'.')
        else: facts[key]=row
    for role,key in (('service_setting','setting'),('patient_status','patient_status'),('em_basis','em_basis')):
        assertions=[a for a in g['assertions'].values() if a['consumer_role']==role]
        for a in assertions:
            if assertion_errors(p,a,relevant=False) or a['consumer_value']=='unknown':
                blockers.append('Unresolved checked '+role+'.');continue
            add(key,a['consumer_value'],a['predicate_refs'][0])
    clinicians=[a for a in g['assertions'].values() if a['consumer_role']=='clinician_role']
    qualified=[a for a in clinicians if not assertion_errors(p,a,subject='clinician',relevant=False)
        and a['consumer_value'] in ('physician','qualified_health_professional')]
    if len(qualified)!=1 or any(assertion_errors(p,a,subject='clinician',relevant=False) for a in clinicians):
        blockers.append('One independently checked qualified practitioner is required.')
    else: add('time_qualified_clinician',True,qualified[0]['predicate_refs'][0])
    if len(accounts)!=1:
        blockers.append('One closed checked practitioner time account is required.')
    else:
        account=accounts[0];owner=g['assertions'][account['owner_assertion_id']]
        errors=assertion_errors(p,owner,subject='clinician',relevant=False)
        if not _checked(p,'time_accounts',account['id']) or not account['closed']:errors.append('account_not_closed_and_confirmed')
        if owner['time']['performer']!='clinician' or owner['time']['performer_ref'] is None:errors.append('account_performer')
        total=_minutes(account['total_ref'],account['unit_ref'])
        if total is None or total<=0:errors.append('invalid_exact_total_minutes')
        if _date_ref(account['date_ref'])!=p['identity']['service_date']:errors.append('account_date_mismatch')
        included=[]
        for identifier in account['included_assertion_ids']:
            a=g['assertions'][identifier];t=a['time']
            if (assertion_errors(p,a,subject='clinician',relevant=False) or t['performer']!='clinician'
                or t['performer_ref'] is None or t['exclusion']!='none'
                or _date_ref(t['date_ref'])!=p['identity']['service_date']):errors.append('included_work_scope')
            minutes=_minutes(t['quantity_ref'],t['unit_ref'])
            if minutes is None:errors.append('included_work_quantity')
            else:included.append(minutes)
        if not included or total!=sum(included):errors.append('work_total_mismatch')
        if account['overlap_assertion_ids']:errors.append('overlapping_time_requires_resolution')
        exclusions={}
        for identifier in account['excluded_assertion_ids']:
            a=g['assertions'][identifier];t=a['time']
            if not _checked(p,'assertions',identifier) or _holds(p,identifier) or a['certainty']!='established':errors.append('excluded_work_unresolved')
            exclusions.setdefault(t['exclusion'],[]).append(a)
        membership=[r for r in g['relationships'].values() if r['source_assertion_id']==owner['id']
            and r['kind'] in ('account_includes','account_excludes','overlaps')]
        if any(not _checked(p,'relationships',r['id']) for r in membership):errors.append('account_membership_unresolved')
        # Unknown or potentially current work cannot disappear from a closed
        # account. Explicit separate dates/performers do not redefine its scope.
        accounted={owner['id'],*account['included_assertion_ids'],*account['excluded_assertion_ids'],*account['overlap_assertion_ids']}
        if potential_time-accounted:errors.append('unaccounted_source_time')
        if 'staff' not in exclusions or 'separately_reported' not in exclusions:errors.append('required_time_exclusions_missing')
        if errors:blockers.extend(errors)
        else:
            total_unit=next(u for u in g['units'] if u['id']==account['total_ref']['source_unit_id'])
            add('time_minutes',total,total_unit);add('time_same_day',True,account['date_ref'])
            add('time_excludes_staff',True,exclusions['staff'][0]['predicate_refs'][0])
            add('time_excludes_separately_reported',True,exclusions['separately_reported'][0]['predicate_refs'][0])
    missing=[key for key in REQUIRED_TIME_FACTS if key not in facts]
    if missing:blockers.append('Missing checked time facts: '+', '.join(missing)+'.')
    if facts.get('setting',{}).get('value')!='outpatient_office':blockers.append('The checked service is not an outpatient office visit.')
    if facts.get('em_basis',{}).get('value')!='time':blockers.append('The checked E/M basis is not time.')
    return {'status':'documented' if not blockers else 'needs_detail','facts':[facts[k] for k in REQUIRED_TIME_FACTS if k in facts],
        'missing':missing,'blockers':list(dict.fromkeys(blockers)),'interpretation_sha256':p['interpretation_sha256']}


def office_service_eligibility(run):
    p=source(run)
    evaluations=[a for a in p['graph']['assertions'].values() if a['consumer_role']=='encounter_evaluation']
    if not evaluations or any(assertion_errors(p,a) for a in evaluations):
        return ['The checked graph does not establish the current evaluated office service.']
    return office_time_facts(run)['blockers']


def licensed_cpt_rule(run, code, evidence, rule, *, evidence_spans=None):
    """Apply the supplied dated rule to graph evidence, never to a source regex."""
    from .corti_semantics import confirmed_time_context
    requirements=rule['requirements']; errors=[]; instructions=list(rule['instructions'])
    if rule['kind']=='procedure':
        p=source(run); matching=[]
        for assertion in p['graph']['assertions'].values():
            if assertion['consumer_role']!='procedure_performed' or assertion_errors(p,assertion):continue
            classification=_classification_context(p,assertion)
            if classification['errors']:continue
            refs=classification['references']
            if any(type(span) is dict and span.get('status')=='valid' and span.get('context_index')==0
                and type(span.get('start')) is int and type(span.get('end')) is int
                and span.get('text')==evidence==run.inputs['notes'][span['start']:span['end']]
                and any(r['start']<=span['start']<span['end']<=r['end'] for r in refs)
                for span in (evidence_spans or [])):
                matching.append(assertion)
        if len(matching)!=1:errors.append('One checked current performed procedure for this patient is required.')
        if requirements['required_details']:
            errors.append('This graph contract has no independently checked licensed procedure-detail mapping.')
        if not any(_literal(evidence,term) for term in requirements['performed_terms']):
            errors.append('The exact evidence does not establish the dated licensed procedure criterion.')
    elif run.context.get('em_basis')=='time' and requirements['time'] is not None:
        support=office_time_facts(run)
        errors.extend(support['blockers']);errors.extend(office_service_eligibility(run))
        errors.extend(confirmed_time_context(run.context,run.inputs['notes'],support['facts']))
        values={f['key']:f['value'] for f in support['facts']}
        if values.get('setting')!=requirements['setting'] or values.get('patient_status')!=requirements['patient_status']:
            errors.append('Checked setting/status differ from the dated licensed criterion.')
        minutes=values.get('time_minutes')
        if type(minutes) is not int or not requirements['time']['minimum']<=minutes<=requirements['time']['maximum']:
            errors.append('Checked total time is outside the dated licensed criterion.')
        if not any(_literal(run.context.get('time_evidence',''),term) for term in requirements['time']['total_time_terms']):
            errors.append('The checked total does not match the supplied licensed total-time criterion.')
        instructions.extend('Exclude from time: '+value for value in requirements['time']['excluded_activities'])
    else:
        errors.append('This graph contract does not establish the supplied licensed MDM criteria.')
    return {'valid':not errors,'errors':list(dict.fromkeys(errors)),
        'instructions':[{'kind':'licensed_instruction','text':item,'reference':rule['reference']} for item in instructions],
        'rule_reference':rule['reference'],'requires_review':bool(rule['instructions']),'description':rule['description']}
