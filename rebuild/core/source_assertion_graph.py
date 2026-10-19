"""Prospective checked source assertions; no legacy clinical grammar dispatch.

Exact quotations are structural evidence, not semantic approval. The independently
retained checker must adjudicate the complete graph and source-unit population.
"""
from copy import deepcopy
import hashlib
import json
import re

from django.core.exceptions import ValidationError

CONTRACT = 'source-assertion-graph-v25'
SCOPE_CONTRACT = CONTRACT
DIAGNOSTICS = 'source-route-diagnostics-v1'
ASSERTION_KINDS = ('clinical', 'identity', 'context', 'condition', 'instruction',
                   'time_total', 'time_work', 'time_exclusion', 'time_qualification', 'nonclinical')
SUBJECTS = ('patient', 'clinician', 'other', 'uncertain')
ENCOUNTERS = ('current', 'past', 'future', 'unknown')
TIMES = ('current', 'past', 'future', 'unspecified')
POLARITIES = ('affirmed', 'negated', 'uncertain', 'mixed')
CERTAINTIES = ('established', 'possible', 'conditional', 'hypothetical', 'unknown')
IDENTITY_ROLES = ('none', 'patient_name', 'patient_reference', 'clinician_name', 'other_name')
CONSUMER_ROLES = ('none','symptom','disease','family_history','personal_history','condition_modifier','normal_finding',
    'encounter_evaluation','service_setting','patient_status','em_basis','clinician_role','service_date',
    'order_placed','collection','procedure_performed','result','time_total','time_work','time_exclusion','time_qualification')
CONDITION_ROLES = ('symptom','disease','family_history','personal_history','condition_modifier')
CONSUMER_VALUES = {'service_setting':('outpatient_office','inpatient','emergency','other','unknown'),
    'patient_status':('new','established','unknown'),'em_basis':('time','mdm','unknown'),
    'clinician_role':('physician','qualified_health_professional','staff','other','unknown')}
PERFORMERS = ('clinician','staff','patient','other','unknown')
EXCLUSIONS = ('none','staff','prior_date','separately_reported','nonqualifying','overlap','unknown')
RELATIONS = ('validity_dependency', 'qualifies', 'condition_of', 'retracts', 'corrects', 'causes', 'independent_of',
             'ownership', 'event_scope', 'account_includes', 'account_excludes', 'overlaps')
DISPOSITIONS = ('assertions', 'context', 'nonclinical', 'unknown')
VERDICTS = ('confirmed', 'unknown', 'contradiction', 'incorrect')
CAUSES = ('none','assignment','extraction','interpretation','definition')
FIELD_VERDICTS = ('supported', 'missing', 'unknown', 'conflict', 'omission', 'incorrect')
IDENTITY_KEYS = ('patient_id', 'encounter_id', 'department_id', 'service_date',
                 'template_version_id', 'generation_job_id', 'patient_display_name', 'patient_reference')


def require(condition, code):
    if not condition:
        raise ValidationError('Source assertion graph: '+code, code=code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_digest(notes):
    return hashlib.sha256(notes.encode()).hexdigest()


def same(a, b):
    return canonical(a) == canonical(b)


def obj(value, keys, code):
    require(type(value) is dict and set(value) == set(keys), code)
    return value


def string(value, code, maximum=2000, empty=False):
    require(type(value) is str and len(value) <= maximum and (empty or bool(value.strip()))
            and not any(ord(c) < 32 and c not in '\r\n\t' for c in value), code)
    return value


def array(value, code, maximum=1000):
    require(type(value) is list and len(value) <= maximum, code)
    return value


def ids(value, universe, code, *, nonempty=False):
    array(value, code)
    require((bool(value) or not nonempty) and all(type(i) is str and i in universe for i in value)
            and len(value) == len(set(value)), code)
    return value


def unit_ids(value, units, code, *, nonempty=False):
    array(value, code)
    require((bool(value) or not nonempty) and all(type(i) is int and i in units for i in value)
            and len(value) == len(set(value)), code)
    return value


def units_for(notes):
    # Only segmentation/coordinates are reused. Legacy correction and scope flags
    # are deliberately absent from this graph's semantic input.
    from .generation import source_units
    require(type(notes) is str and len(notes) <= 50000, 'source_limit')
    return [{k: u[k] for k in ('id', 'start', 'end', 'quote')} for u in source_units(notes, [])[0]]


def resolve_ref(notes, by_unit, ref, *, nullable=False):
    if ref is None and nullable:
        return None
    obj(ref, ('quote', 'source_unit_id', 'occurrence'), 'reference_shape')
    quote = string(ref['quote'], 'reference_quote', 50000)
    require(type(ref['source_unit_id']) is int and ref['source_unit_id'] in by_unit
            and type(ref['occurrence']) is int and 1 <= ref['occurrence'] <= 50000, 'reference_identity')
    unit = by_unit[ref['source_unit_id']]
    offset = -1
    for _ in range(ref['occurrence']):
        offset = unit['quote'].find(quote, offset+1)
        require(offset >= 0, 'reference_absent')
    start = unit['start']+offset
    require(notes[start:start+len(quote)] == quote, 'reference_source_changed')
    return {'start': start, 'end': start+len(quote), 'quote': quote,
            'source_unit_id': unit['id']}


def _refs(notes, by_unit, values, permitted, code, *, nonempty=False):
    array(values, code, 100)
    require(bool(values) or not nonempty, code)
    result = [resolve_ref(notes, by_unit, r) for r in values]
    require(all(r['source_unit_id'] in permitted for r in result)
            and len({digest(r) for r in result}) == len(result), code)
    return result


def validate_literal_facts(notes, units, raw_facts):
    """Hard literal subset of legacy validation, without its scope/governance calls."""
    from . import semantic_generation as literal
    array(raw_facts, 'fact_limit', 200)
    by_unit = {u['id']: u for u in units}
    facts = {}
    keys = ('id', 'kind', 'concept', 'subject', 'value_span', 'polarity', 'timing',
            'unit', 'unit_span', 'scale', 'supersedes')
    for raw in raw_facts:
        obj(raw, keys, 'fact_shape')
        identifier = string(raw['id'], 'fact_id', 80)
        string(raw['concept'], 'fact_concept', 120)
        require(identifier not in facts and raw['kind'] in literal.KINDS
                and raw['polarity'] in POLARITIES, 'fact_type_or_duplicate')
        cited = set()
        def ref(value, nullable=False):
            resolved = resolve_ref(notes, by_unit, value, nullable=nullable)
            if resolved:
                cited.add(resolved['source_unit_id'])
                return {k: resolved[k] for k in ('start', 'end', 'quote')}
            return None
        value = ref(raw['value_span'])
        if literal._source_number(value['quote']) is not None:
            require(not literal._number_fragment(notes, value, score_scale=raw['scale'] is not None),
                    'numeric_fragment')
        require(not (value['quote'][:1].isdigit() and notes[max(0,value['start']-1):value['start']]
                     in ('-', '+', '.', '−')), 'numeric_sign_fragment')
        if re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)', value['quote']):
            require(not (re.match(r'(?:,\d|[eE][+-]?\d)', notes[value['end']:])
                         or re.search(r'(?:\d,|\d[eE][+-]?)$', notes[:value['start']])), 'numeric_group_fragment')
        for adjacent, edge, beyond in (
            (notes[max(0,value['start']-1):value['start']], value['quote'][:1],
             notes[max(0,value['start']-2):max(0,value['start']-1)]),
            (notes[value['end']:value['end']+1], value['quote'][-1:], notes[value['end']+1:value['end']+2])):
            require(not (adjacent and edge and (adjacent.isalpha() and edge.isalpha()
                    or edge.isdigit() and (adjacent.isdigit() or adjacent == '.' and beyond.isdigit()))),
                    'literal_word_fragment')
        subject = obj(raw['subject'], ('kind', 'name_span'), 'fact_subject')
        require(subject['kind'] in SUBJECTS, 'fact_subject_kind')
        name = ref(subject['name_span'], True)
        require(subject['kind'] != 'other' or name is not None, 'foreign_subject_without_evidence')
        timing = obj(raw['timing'], ('kind', 'span'), 'fact_timing')
        require(timing['kind'] in TIMES, 'fact_timing_kind')
        time = ref(timing['span'], True)
        unit = ref(raw['unit_span'], True)
        if raw['unit'] is None:
            require(unit is None, 'unit_without_value')
        else:
            string(raw['unit'], 'fact_unit', 80)
            require(unit is not None and raw['unit'].casefold() == unit['quote'].casefold(), 'unit_not_literal')
            suffix = notes[value['end']:unit['start']] if unit['start'] >= value['end'] else None
            require(suffix is not None and (not suffix.strip() or
                unit['quote'].casefold() in ('celsius', 'fahrenheit')
                and re.fullmatch(r'\s+degrees\s+', suffix, re.I)), 'unit_not_attached')
        scale = raw['scale']
        if scale is not None:
            obj(scale, ('minimum', 'maximum', 'span'), 'scale_shape')
            evidence = ref(scale['span'])
            for bound in ('minimum', 'maximum'):
                if scale[bound] is not None:
                    require(literal._source_bound_present(notes, evidence, literal._decimal(scale[bound])),
                            'scale_bound_absent')
            contexts = [{k: by_unit[i][k] for k in ('start', 'end', 'quote')} for i in sorted(cited)]
            try:
                literal._measurement_scale(notes, value, contexts, scale, evidence)
            except ValidationError as exc:
                raise ValidationError('Source assertion graph: literal_scale_binding', code='literal_scale_binding') from exc
            scale = {**deepcopy(scale), 'span': {k: evidence[k] for k in ('start', 'end')}, 'evidence': evidence}
        array(raw['supersedes'], 'supersedes', 200)
        require(all(type(i) is str for i in raw['supersedes'])
                and len(set(raw['supersedes'])) == len(raw['supersedes']), 'supersedes')
        facts[identifier] = {**deepcopy(raw), 'value_span': {k:value[k] for k in ('start','end')},
            'value_evidence': value, 'source_unit_ids': sorted(cited),
            'evidence': [{k:by_unit[i][k] for k in ('start','end','quote')} for i in sorted(cited)],
            'subject': {'kind':subject['kind'], 'name_span': None if name is None else {k:name[k] for k in ('start','end')},
                        'name_evidence': name},
            'timing': {'kind':timing['kind'], 'span':None if time is None else {k:time[k] for k in ('start','end')},
                       'evidence':time},
            'unit_span': None if unit is None else {k:unit[k] for k in ('start','end')}, 'scale':scale}
    for fact in facts.values():
        ids(fact['supersedes'], facts, 'supersedes_unknown')
        require(fact['id'] not in fact['supersedes'], 'self_correction')
    return facts


def _index(rows, code, maximum=1000):
    array(rows, code, maximum)
    result = {}
    for row in rows:
        require(type(row) is dict, code)
        identifier = string(row.get('id'), code+'_id', 80)
        require(identifier not in result, code+'_duplicate')
        result[identifier] = row
    return result


def _acyclic(nodes, edges):
    visiting, done = set(), set()
    def visit(node):
        require(node not in visiting, 'dependency_cycle')
        if node in done:
            return
        visiting.add(node)
        for target in edges.get(node, []):
            visit(target)
        visiting.remove(node)
        done.add(node)
    for node in nodes:
        visit(node)


def compile_graph(notes, extraction):
    obj(extraction, ('contract','facts','assertions','relationships','unit_coverage','time_accounts'), 'graph_shape')
    require(extraction['contract'] == CONTRACT, 'graph_contract')
    units = units_for(notes)
    by_unit = {u['id']:u for u in units}
    facts = validate_literal_facts(notes, units, extraction['facts'])
    assertions = _index(extraction['assertions'], 'assertions', 400)
    relationships = _index(extraction['relationships'], 'relationships', 800)
    accounts = _index(extraction['time_accounts'], 'time_accounts', 100)
    assertions = deepcopy(assertions)
    owners = {}
    for assertion in assertions.values():
        obj(assertion, ('id','fact_ids','source_unit_ids','kind','subject','encounter','temporality',
                       'polarity','certainty','identity_role','consumer_role','consumer_value','consumer_ref','clinically_relevant','time',
                       'predicate_refs','context_refs','qualifier_refs'), 'assertion_shape')
        ids(assertion['fact_ids'], facts, 'assertion_facts')
        unit_ids(assertion['source_unit_ids'], by_unit, 'assertion_units', nonempty=True)
        require(assertion['kind'] in ASSERTION_KINDS and assertion['subject'] in SUBJECTS
                and assertion['encounter'] in ENCOUNTERS and assertion['temporality'] in TIMES
                and assertion['polarity'] in POLARITIES and assertion['certainty'] in CERTAINTIES
                and assertion['identity_role'] in IDENTITY_ROLES and assertion['consumer_role'] in CONSUMER_ROLES
                and type(assertion['clinically_relevant']) is bool, 'assertion_type')
        require(assertion['identity_role']=='none' or assertion['kind']=='identity' and bool(assertion['fact_ids']), 'identity_role_without_value')
        role_subject = {'patient_name':'patient','patient_reference':'patient','clinician_name':'clinician','other_name':'other'}
        require(assertion['identity_role']=='none' or assertion['subject']==role_subject[assertion['identity_role']], 'identity_role_subject')
        require(not assertion['consumer_role'].startswith('time_') or assertion['kind']==assertion['consumer_role'], 'time_role_kind')
        require(assertion['consumer_role'] != 'condition_modifier' or assertion['kind'] == 'context', 'condition_modifier_kind')
        allowed_values = CONSUMER_VALUES.get(assertion['consumer_role'])
        require(assertion['consumer_value'] in allowed_values if allowed_values else assertion['consumer_value'] is None, 'consumer_value')
        time = assertion['time']
        if time is not None:
            obj(time, ('performer','performer_ref','date_ref','quantity_ref','unit_ref','exclusion'), 'time_claim')
            require(time['performer'] in PERFORMERS and time['exclusion'] in EXCLUSIONS, 'time_claim_type')
            for key in ('performer_ref','date_ref','quantity_ref','unit_ref'):
                time[key] = resolve_ref(notes, by_unit, time[key], nullable=True)
                require(time[key] is None or time[key]['source_unit_id'] in assertion['source_unit_ids'], 'time_claim_scope')
            require((time['quantity_ref'] is None)==(time['unit_ref'] is None), 'time_quantity_unit_pair')
            require(time['performer']=='unknown' or time['performer_ref'] is not None, 'time_performer_evidence')
        require(not assertion['consumer_role'].startswith('time_') or time is not None, 'time_role_without_claim')
        for name in ('predicate_refs','context_refs','qualifier_refs'):
            assertion[name] = _refs(notes, by_unit, assertion[name], assertion['source_unit_ids'],
                                    name, nonempty=name=='predicate_refs')
        consumer_ref = resolve_ref(notes, by_unit, assertion['consumer_ref'], nullable=True)
        require((consumer_ref is not None) == (assertion['consumer_role'] in CONDITION_ROLES), 'consumer_reference_role')
        if consumer_ref is not None:
            owned = assertion['predicate_refs'] + [facts[i]['value_evidence'] for i in assertion['fact_ids']]
            require(consumer_ref['source_unit_id'] in assertion['source_unit_ids'] and any(
                value['start'] <= consumer_ref['start'] < consumer_ref['end'] <= value['end']
                for value in owned), 'consumer_reference_ownership')
            start, end = consumer_ref['start'], consumer_ref['end']
            word = lambda char: bool(char) and (char.isalnum() or char == '_')
            require(not (word(notes[start:start+1]) and word(notes[max(0,start-1):start])
                         or word(notes[end-1:end]) and word(notes[end:end+1])), 'consumer_reference_word_fragment')
        assertion['consumer_ref'] = consumer_ref
        if assertion['polarity'] in ('negated','uncertain','mixed') or assertion['certainty'] in ('possible','conditional','hypothetical'):
            require(bool(assertion['qualifier_refs']), 'qualified_assertion_without_qualifier')
        for fact_id in assertion['fact_ids']:
            require(fact_id not in owners, 'fact_multiple_assertions')
            owners[fact_id] = assertion['id']
            fact = facts[fact_id]
            require(set(fact['source_unit_ids']) <= set(assertion['source_unit_ids']), 'fact_outside_assertion')
            require(fact['subject']['kind'] == assertion['subject'] and fact['timing']['kind'] == assertion['temporality']
                    and fact['polarity'] == assertion['polarity'], 'fact_assertion_disagreement')
    require(set(owners) == set(facts), 'unassigned_fact_assertion')
    relationships = deepcopy(relationships)
    dependencies = {}
    for relationship in relationships.values():
        obj(relationship, ('id','kind','source_assertion_id','target_assertion_ids','evidence_refs'), 'relationship_shape')
        require(relationship['kind'] in RELATIONS and relationship['source_assertion_id'] in assertions, 'relationship_source')
        ids(relationship['target_assertion_ids'], assertions, 'relationship_targets', nonempty=True)
        require(relationship['source_assertion_id'] not in relationship['target_assertion_ids'], 'relationship_self')
        allowed = set(assertions[relationship['source_assertion_id']]['source_unit_ids'])
        for target in relationship['target_assertion_ids']:
            allowed.update(assertions[target]['source_unit_ids'])
        relationship['evidence_refs'] = _refs(notes, by_unit, relationship['evidence_refs'], allowed,
                                              'relationship_evidence', nonempty=True)
        if relationship['kind'] in ('corrects','retracts','validity_dependency'):
            dependencies.setdefault(relationship['source_assertion_id'], []).extend(relationship['target_assertion_ids'])
    _acyclic(assertions, dependencies)
    for fact in facts.values():
        for prior in fact['supersedes']:
            require(any(r['kind']=='corrects' and r['source_assertion_id']==owners[fact['id']]
                        and owners[prior] in r['target_assertion_ids'] for r in relationships.values()), 'correction_edge_missing')
    coverage = {}
    for row in array(extraction['unit_coverage'], 'coverage'):
        obj(row, ('source_unit_id','disposition','assertion_ids','affected_assertion_ids'), 'coverage_shape')
        unit_id = row['source_unit_id']
        require(type(unit_id) is int and unit_id in by_unit and unit_id not in coverage
                and row['disposition'] in DISPOSITIONS, 'coverage_identity')
        ids(row['assertion_ids'], assertions, 'coverage_assertions')
        ids(row['affected_assertion_ids'], assertions, 'coverage_dependents')
        require(set(row['assertion_ids']) == {a['id'] for a in assertions.values() if unit_id in a['source_unit_ids']},
                'coverage_assertion_population')
        require(row['disposition'] != 'assertions' or bool(row['assertion_ids']), 'empty_assertion_coverage')
        require(row['disposition'] == 'unknown' or not row['affected_assertion_ids'], 'unexpected_unresolved_dependents')
        coverage[unit_id] = deepcopy(row)
    require(set(coverage) == set(by_unit), 'incomplete_source_coverage')
    accounts = deepcopy(accounts)
    for account in accounts.values():
        obj(account, ('id','owner_assertion_id','date_ref','total_ref','unit_ref','included_assertion_ids',
                      'excluded_assertion_ids','overlap_assertion_ids','closed'), 'account_shape')
        owner = account['owner_assertion_id']
        require(owner in assertions and assertions[owner]['kind']=='time_total' and type(account['closed']) is bool,
                'account_owner')
        for key in ('date_ref','total_ref','unit_ref'):
            account[key] = resolve_ref(notes, by_unit, account[key])
            require(account[key]['source_unit_id'] in assertions[owner]['source_unit_ids'], 'account_evidence_scope')
        for name, kind, relation in (('included_assertion_ids','time_work','account_includes'),
                                    ('excluded_assertion_ids','time_exclusion','account_excludes'),
                                    ('overlap_assertion_ids',None,'overlaps')):
            ids(account[name], assertions, name)
            for target in account[name]:
                require((kind is None or assertions[target]['kind']==kind)
                        and any(r['kind']==relation and r['source_assertion_id']==owner
                                and target in r['target_assertion_ids'] for r in relationships.values()), 'account_membership')
        require(not set(account['included_assertion_ids']) & set(account['excluded_assertion_ids']), 'account_included_and_excluded')
    graph = {'contract':CONTRACT, 'source_sha256':source_digest(notes), 'units':units, 'facts':facts,
             'assertions':assertions, 'relationships':relationships,
             'unit_coverage':{str(k):v for k,v in coverage.items()}, 'time_accounts':accounts,
             'fact_assertions':owners}
    return {**graph, 'graph_sha256':digest(graph)}


def dependent_closure(graph, identifiers):
    affected = set(identifiers)
    while True:
        prior = set(affected)
        for r in graph['relationships'].values():
            if r['kind'] == 'validity_dependency' and r['source_assertion_id'] in affected:
                affected.update(r['target_assertion_ids'])
        if affected == prior:
            return sorted(affected)


def hold(graph, code, affected, evidence, *, field_key=None, component_id=None):
    affected = dependent_closure(graph, affected)
    return {'code':code, 'rule':CONTRACT+'.'+code, 'assertion_ids':affected,
            'fact_ids':sorted(f for f,a in graph['fact_assertions'].items() if a in affected),
            'field_key':field_key, 'component_id':component_id, 'relationship_ids':[],
            'checker_reason':'', 'evidence':deepcopy(evidence)}


def validate_checker(notes, graph, fields, definitions, assignments, response):
    obj(response, ('contract','graph_sha256','assertions','relationships','unit_coverage','time_accounts',
                   'components','fields'), 'checker_shape')
    require(response['contract']==CONTRACT and response['graph_sha256']==graph['graph_sha256'], 'checker_graph_binding')
    by_unit = {u['id']:u for u in graph['units']}
    checked, holds = {}, []
    for population in ('assertions','relationships','unit_coverage','time_accounts'):
        rows = _index(response[population], 'checked_'+population)
        require(set(rows)==set(graph[population]), 'checker_population_'+population)
        checked[population] = {}
        for identifier, row in rows.items():
            obj(row, ('id','verdict','reason','evidence_refs'), 'checker_item')
            require(row['verdict'] in VERDICTS, 'checker_verdict')
            string(row['reason'], 'checker_reason', empty=row['verdict']=='confirmed')
            evidence = _refs(notes,by_unit,row['evidence_refs'],by_unit,'checker_evidence')
            checked[population][identifier] = {**deepcopy(row), 'evidence':evidence}
            source = graph[population][identifier]
            if population=='assertions':
                affected = [identifier]
                unknown = source['subject']=='uncertain' or source['encounter']=='unknown' or source['certainty']=='unknown'
                default = source['predicate_refs']+source['context_refs']
            elif population=='relationships':
                affected = source['target_assertion_ids'] if source['kind']=='validity_dependency' else []
                unknown, default = False, source['evidence_refs']
                if row['verdict']=='confirmed' and source['kind'] in ('retracts','corrects'):
                    holds.append(hold(graph, 'source_'+source['kind'], source['target_assertion_ids'], default))
            elif population=='unit_coverage':
                unknown = source['disposition']=='unknown'
                # A rejected coverage claim supplies no independently confirmed
                # scope. Only an explicitly unknown, bounded source claim can
                # restrict its possible dependents; otherwise this is an
                # explicit unresolved-source hold, including missing fields.
                unbounded = row['verdict']!='confirmed' or not source['affected_assertion_ids']
                affected = source['affected_assertion_ids'] if not unbounded else list(graph['assertions'])
                default = [by_unit[int(identifier)]]
            else:
                affected = [source['owner_assertion_id'], *source['included_assertion_ids'],
                            *source['excluded_assertion_ids'], *source['overlap_assertion_ids']]
                unknown, default = not source['closed'], [source['total_ref'],source['date_ref']]
            if unknown or row['verdict']!='confirmed':
                holds.append(hold(graph, ('unresolved_' if unknown else 'checker_'+row['verdict']+'_')+population,
                                  affected, evidence or default))
                holds[-1]['checker_reason'] = row['reason']
                if population=='relationships':
                    holds[-1]['relationship_ids'] = [identifier]
                if population=='time_accounts':
                    # Account qualification governs the E/M consumer. It does
                    # not retract independently checked source assertions such
                    # as a documented clinical total or symptom duration.
                    holds[-1]['consumer_scope'] = 'office_em'
                    holds[-1]['time_account_ids'] = [identifier]
                if population=='unit_coverage' and unbounded:
                    holds[-1]['global'] = True
    component_rows = {}
    expected = {(f['key'],c['id']) for f in fields for c in definitions[f['key']]['component_contract']['components']}
    for row in array(response['components'], 'checker_components', 3000):
        obj(row, ('field_key','component_id','verdict','cause','fact_ids','reason','evidence_refs'), 'checker_component')
        pair = (row['field_key'], row['component_id'])
        require(pair in expected and pair not in component_rows and row['verdict'] in FIELD_VERDICTS and row['cause'] in CAUSES,
                'checker_component_identity')
        ids(row['fact_ids'],graph['facts'],'checker_component_facts')
        string(row['reason'],'checker_component_reason',empty=row['verdict'] in ('supported','missing'))
        evidence = _refs(notes,by_unit,row['evidence_refs'],by_unit,'checker_component_evidence')
        assignment = next(c for c in assignments[row['field_key']]['components'] if c['id']==row['component_id'])
        if row['verdict'] in ('supported','missing'):
            require(row['cause']=='none', 'checker_success_cause')
            require(row['verdict']==assignment['disposition'] and row['fact_ids']==assignment['fact_ids'],
                    'checker_component_selection_disagreement')
        component_rows[pair] = {**deepcopy(row),'evidence':evidence}
        if row['verdict'] not in ('supported','missing'):
            holds.append(hold(graph,'component_'+row['verdict'],
                [graph['fact_assertions'][i] for i in set(row['fact_ids']+assignment['fact_ids'])],evidence,
                field_key=pair[0],component_id=pair[1]))
            holds[-1]['checker_reason'] = row['reason']
    require(set(component_rows)==expected, 'checker_component_population')
    checked['components'] = list(component_rows.values())
    field_rows = {}
    for row in array(response['fields'],'checker_fields',100):
        obj(row,('key','verdict','cause','reason','evidence_refs'),'checker_field')
        key = row['key']
        require(key in definitions and key not in field_rows and row['verdict'] in FIELD_VERDICTS and row['cause'] in CAUSES,'checker_field_identity')
        string(row['reason'],'checker_field_reason',empty=row['verdict'] in ('supported','missing'))
        evidence = _refs(notes,by_unit,row['evidence_refs'],by_unit,'checker_field_evidence')
        verdicts = [r['verdict'] for (k,_),r in component_rows.items() if k==key]
        if row['verdict'] in ('supported','missing'):
            require(row['cause']=='none','checker_success_cause')
        if row['verdict']=='supported':
            require(bool(verdicts) and all(v=='supported' for v in verdicts),'checker_partial_field_supported')
        if row['verdict']=='missing':
            require(all(v=='missing' for v in verdicts),'checker_partial_field_missing')
        field_rows[key] = {**deepcopy(row),'evidence':evidence}
        if row['verdict'] not in ('supported','missing'):
            holds.append(hold(graph,'field_'+row['verdict'],[],evidence,field_key=key))
            holds[-1]['checker_reason'] = row['reason']
    require(set(field_rows)==set(definitions),'checker_field_population')
    checked['fields'] = field_rows
    return {'checked':checked,'holds':holds}


def validate_interpretation(notes, interpretation):
    # Lazy import avoids a graph/generation cycle and recomputes every answer,
    # checker and graph binding; a re-signed outer digest is insufficient.
    from .source_assertion_generation import restore
    restore(notes, interpretation)
    return interpretation


def projection(interpretation):
    validate_interpretation(interpretation['notes'], interpretation)
    return {'contract':CONTRACT, 'identity':deepcopy(interpretation['identity']),
            'graph':deepcopy(interpretation['graph']),
            'adjudication':deepcopy(interpretation['adjudication']),
            'interpretation_sha256':interpretation['sha256']}


# Closed provider schemas. Structural validators above remain authoritative.
def object_schema(properties):
    return {'type':'object','additionalProperties':False,'required':list(properties),'properties':properties}


def enum(values):
    return {'type':'string','enum':list(values)}


def list_schema(item, maximum=1000):
    return {'type':'array','maxItems':maximum,'items':item}


TEXT = {'type':'string','maxLength':2000}
ID = {'type':'string','minLength':1,'maxLength':80}
REF = object_schema({'quote':{'type':'string','minLength':1,'maxLength':50000},
                     'source_unit_id':{'type':'integer','minimum':1},
                     'occurrence':{'type':'integer','minimum':1,'maximum':50000}})


def extraction_schema():
    from .semantic_generation import API_FACT_INVENTORY_SCHEMA
    fact_schema = deepcopy(API_FACT_INVENTORY_SCHEMA['properties']['facts'])
    fact_schema['items']['properties']['polarity'] = enum(POLARITIES)
    nullable = lambda item: {'anyOf':[item,{'type':'null'}]}
    return object_schema({'contract':enum((CONTRACT,)),
        'facts':fact_schema,
        'assertions':list_schema(object_schema({'id':ID,'fact_ids':list_schema(ID,200),
            'source_unit_ids':list_schema({'type':'integer','minimum':1}), 'kind':enum(ASSERTION_KINDS),
            'subject':enum(SUBJECTS),'encounter':enum(ENCOUNTERS),'temporality':enum(TIMES),
            'polarity':enum(POLARITIES),'certainty':enum(CERTAINTIES),'identity_role':enum(IDENTITY_ROLES),
            'clinically_relevant':{'type':'boolean'},'consumer_role':enum(CONSUMER_ROLES),'consumer_value':nullable(enum(sorted(set(v for vs in CONSUMER_VALUES.values() for v in vs)))),
            'consumer_ref':nullable(REF),
            'time':nullable(object_schema({'performer':enum(PERFORMERS),'exclusion':enum(EXCLUSIONS),
                **{k:nullable(REF) for k in ('performer_ref','date_ref','quantity_ref','unit_ref')}})),
            **{k:list_schema(REF,100) for k in ('predicate_refs','context_refs','qualifier_refs')}}),400),
        'relationships':list_schema(object_schema({'id':ID,'kind':enum(RELATIONS),'source_assertion_id':ID,
            'target_assertion_ids':list_schema(ID,400),'evidence_refs':list_schema(REF,100)}),800),
        'unit_coverage':list_schema(object_schema({'source_unit_id':{'type':'integer','minimum':1},
            'disposition':enum(DISPOSITIONS),'assertion_ids':list_schema(ID,400),'affected_assertion_ids':list_schema(ID,400)})),
        'time_accounts':list_schema(object_schema({'id':ID,'owner_assertion_id':ID,
            **{k:REF for k in ('date_ref','total_ref','unit_ref')},
            **{k:list_schema(ID,400) for k in ('included_assertion_ids','excluded_assertion_ids','overlap_assertion_ids')},
            'closed':{'type':'boolean'}}),100)})


def checker_schema():
    item = object_schema({'id':ID,'verdict':enum(VERDICTS),'reason':TEXT,'evidence_refs':list_schema(REF,100)})
    return object_schema({'contract':enum((CONTRACT,)),'graph_sha256':{'type':'string'},
        **{k:list_schema(item) for k in ('assertions','relationships','unit_coverage','time_accounts')},
        'components':list_schema(object_schema({'field_key':ID,'component_id':ID,'verdict':enum(FIELD_VERDICTS),'cause':enum(CAUSES),
            'fact_ids':list_schema(ID,200),'reason':TEXT,'evidence_refs':list_schema(REF,100)}),3000),
        'fields':list_schema(object_schema({'key':ID,'verdict':enum(FIELD_VERDICTS),'cause':enum(CAUSES),
            'reason':TEXT,'evidence_refs':list_schema(REF,100)}),100)})
