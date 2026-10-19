"""CPT selection from owner-supplied licensed criteria; no CPT catalogue here."""
from datetime import date
import re

from django.core.exceptions import ValidationError

from .coding_licensing import canonical, cpt_status

CODE = re.compile(r'(?:[0-9]{5}|[0-9]{4}[A-Z])\Z')
LEVELS = {'straightforward', 'low', 'moderate', 'high'}


def _strings(value, maximum=100):
    return (type(value) is list and 0 < len(value) <= maximum
            and all(type(item) is str and 0 < len(item.strip()) <= 2000 for item in value)
            and len(set(value)) == len(value))


def validate_rules(rules, release):
    """Validate the finite, data-supplied rules language before any import."""
    def require(condition):
        if not condition:
            raise ValidationError('Licensed CPT criteria are incomplete or use an unsupported rule shape.')
    require(type(rules) is dict and set(rules) == {'format', 'release', 'index', 'tabular'})
    require(rules['format'] == 'quillmd-cpt-rules-v1' and canonical(rules['release']) == canonical(release))
    require(type(rules['tabular']) is dict and set(rules['tabular']) == {'codes'})
    codes = rules['tabular']['codes']
    require(type(codes) is dict and bool(codes) and len(codes) <= release['code_count'])
    for code, row in codes.items():
        require(type(code) is str and bool(CODE.fullmatch(code)))
        require(type(row) is dict and set(row) == {'description', 'kind', 'reference', 'instructions', 'requirements'})
        require(type(row['description']) is str and 0 < len(row['description']) <= 500)
        require(type(row['reference']) is str and 0 < len(row['reference']) <= 2000)
        require(type(row['instructions']) is list and (not row['instructions'] or _strings(row['instructions'])))
        requirement = row['requirements']
        require(type(requirement) is dict)
        if row['kind'] == 'procedure':
            require(set(requirement) == {'performed_terms', 'required_details'})
            require(_strings(requirement['performed_terms']))
            require(type(requirement['required_details']) is list and len(requirement['required_details']) <= 30)
            names = []
            for detail in requirement['required_details']:
                require(type(detail) is dict and set(detail) == {'name', 'terms', 'reference'})
                require(type(detail['name']) is str and bool(re.fullmatch('[a-z][a-z0-9_]{0,59}', detail['name'])))
                require(_strings(detail['terms']) and type(detail['reference']) is str and bool(detail['reference']))
                names.append(detail['name'])
            require(len(names) == len(set(names)))
        elif row['kind'] == 'office_em':
            require(set(requirement) == {'setting', 'patient_status', 'mdm', 'time'})
            require(requirement['setting'] == 'outpatient_office' and requirement['patient_status'] in ('new', 'established'))
            mdm, timing = requirement['mdm'], requirement['time']
            require(mdm is not None or timing is not None)
            if mdm is not None:
                require(type(mdm) is dict and set(mdm) == {'required_elements', 'problems', 'data', 'risk', 'evidence_terms'})
                require(type(mdm['required_elements']) is int and mdm['required_elements'] == 2)
                require(type(mdm['evidence_terms']) is dict and set(mdm['evidence_terms']) == {'problems', 'data', 'risk'})
                for key in ('problems', 'data', 'risk'):
                    require(_strings(mdm[key], 4) and set(mdm[key]) <= LEVELS)
                    require(_strings(mdm['evidence_terms'][key]))
            if timing is not None:
                require(type(timing) is dict and set(timing) == {'minimum', 'maximum', 'basis', 'total_time_terms', 'excluded_activities'})
                require(type(timing['minimum']) is int and type(timing['maximum']) is int
                        and 0 < timing['minimum'] <= timing['maximum'] <= 1440)
                require(timing['basis'] == 'total_practitioner_same_day' and _strings(timing['total_time_terms'])
                        and _strings(timing['excluded_activities']))
        else:
            require(False)
    require(type(rules['index']) is list and 0 < len(rules['index']) <= 100000)
    indexed = set()
    for item in rules['index']:
        require(type(item) is dict and set(item) == {'terms', 'code', 'reference'})
        require(item['code'] in codes and _strings(item['terms']) and type(item['reference']) is str and bool(item['reference']))
        indexed.add(item['code'])
    require(indexed == set(codes))


def _sources(run):
    return [run.inputs.get('notes', '')] + [value.get('text', '') for value in run.inputs.get('answers', {}).values()
                                          if type(value) is dict and type(value.get('text')) is str]


def _quote(run, quote):
    return type(quote) is str and bool(quote.strip()) and any(quote in source for source in _sources(run))


def _qualified_quote(run, quote):
    if not _quote(run, quote):
        return False
    notes = run.inputs.get('notes', '')
    sources = [notes] if quote in notes else list(dict.fromkeys(_sources(run)[1:]))
    if sum(source.count(quote) for source in sources) != 1:
        return False
    source = next(source for source in sources if quote in source)
    start = source.find(quote)
    low = source.rfind('\n', 0, start) + 1
    high = source.find('\n', start + len(quote))
    context = source[low:high if high >= 0 else len(source)]
    prior = source[:low].rstrip().split('\n')[-1]
    if prior.endswith(':'):
        context = prior + '\n' + context
    return not re.search(r'\b(?:no|not|never|denies|planned|scheduled|history\s+of|previously|yesterday|last\s+(?:year|month|week)|will|may|would|mother|father|sister|brother|family)\b', context, re.IGNORECASE)


def _span(run, span):
    if type(span) is not dict or set(span) != {'start', 'end', 'quote'}:
        return False
    source = run.inputs.get('notes', '')
    return (type(span['start']) is int and type(span['end']) is int
            and 0 <= span['start'] < span['end'] <= len(source)
            and type(span['quote']) is str and source[span['start']:span['end']] == span['quote'])


def _terms(text, terms):
    # Whole literal phrases supplied by the licensed criteria, never fuzzy codes.
    return any(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.IGNORECASE) for term in terms)


def _span_context(run, span):
    source = run.inputs['notes']
    low = source.rfind('\n', 0, span['start']) + 1
    high = source.find('\n', span['end'])
    line = source[low:high if high >= 0 else len(source)]
    prior = source[:low].rstrip().split('\n')[-1]
    return prior + '\n' + line if prior.endswith(':') else line


def _evidence(run, evidence, requirements):
    """Resolve only exact note text; selectors cannot fabricate span metadata."""
    if type(evidence) is dict and 'source' in evidence:
        return evidence
    concept = evidence if type(evidence) is dict else None
    quote = concept.get('evidence') if concept is not None else evidence
    notes = run.inputs.get('notes', '')
    if type(quote) is not str or not quote or notes.count(quote) != 1:
        return {}
    start = notes.find(quote)
    span = {'start': start, 'end': start + len(quote), 'quote': quote}
    if concept is not None and (concept.get('kind') != 'procedure' or concept.get('certainty') != 'confirmed'
            or concept.get('temporality') != 'current' or concept.get('subject') != 'patient'
            or concept.get('relevant') is not True):
        return {}
    return {'source': span, 'assertion': 'affirmed', 'subject': 'patient', 'timing': 'current',
            'procedure_status': 'performed', 'details': {detail['name']: span for detail in requirements.get('required_details', [])
                if _terms(quote, detail['terms'])}}


def _reference(run):
    try:
        when = date.fromisoformat(run.inputs['service_date'])
    except (KeyError, TypeError, ValueError):
        return None, 'A dated coding input is required.'
    status = cpt_status(when)
    if not status['available']:
        return None, status['reason']
    snapshots = [item for item in run.releases if item.get('system') == 'CPT']
    if len(snapshots) != 1 or any(snapshots[0].get(key) != status[key] for key in ('version', 'sha256', 'coding_digest', 'license_reference', 'effective_from', 'effective_until')) or snapshots[0].get('id') != status['release_id']:
        return None, 'CPT entitlement or licensed reference differs from this immutable coding run.'
    from .models import CodingRelease
    return CodingRelease.objects.select_related('release').get(release_id=status['release_id']), ''


def _validate(run, code, evidence, reference, *, evidence_spans=None):
    row = reference.tabular['codes'].get(code)
    if row is None:
        return {'valid': False, 'errors': ['No licensed criteria are supplied for this code.'], 'instructions': []}
    from . import source_assertion_coding as shared
    if shared.enabled(run):
        return shared.licensed_cpt_rule(run,code,evidence,row,evidence_spans=evidence_spans)
    errors = []
    instructions = list(row['instructions'])
    requirements = row['requirements']
    if row['kind'] == 'procedure':
        evidence = _evidence(run, evidence, requirements)
        if (type(evidence) is not dict or evidence.get('assertion') != 'affirmed'
                or evidence.get('subject') != 'patient' or evidence.get('timing') != 'current'
                or evidence.get('procedure_status') != 'performed' or not _span(run, evidence.get('source'))):
            errors.append('Current performed procedure evidence for this patient is required; plans and history do not qualify.')
        else:
            quote = evidence['source']['quote']
            if not _terms(quote, requirements['performed_terms']):
                errors.append('The exact documentation does not establish the licensed performed-procedure criterion.')
            # A structured label cannot turn explicit planning/negation into performance.
            if re.search(r'\b(?:no|not|never|denies|declined|planned|planning|scheduled|recommend(?:ed)?|consider|history\s+of|previously|will|may|would|mother|father|sister|brother|family)\b', _span_context(run, evidence['source']), re.IGNORECASE):
                errors.append('The quoted procedure is negated, planned or historical.')
            details = evidence.get('details', {})
            if type(details) is not dict:
                details = {}
            for detail in requirements['required_details']:
                span = details.get(detail['name'])
                if not _span(run, span) or not _terms(span['quote'], detail['terms']):
                    errors.append('Document the licensed required detail: ' + detail['name'] + '.')
    else:
        context = run.context
        if context.get('setting') != requirements['setting']:
            errors.append('Document the office/outpatient setting.')
        if context.get('patient_status') != requirements['patient_status']:
            errors.append('Document the licensed new/established patient status.')
        basis = context.get('em_basis')
        if basis == 'mdm' and requirements['mdm'] is not None:
            count = 0
            for element in ('problems', 'data', 'risk'):
                level = context.get('mdm_' + element)
                quote = context.get('mdm_' + element + '_evidence')
                if (level in requirements['mdm'][element] and _qualified_quote(run, quote)
                        and _terms(quote, requirements['mdm']['evidence_terms'][element])):
                    count += 1
            if count < requirements['mdm']['required_elements']:
                errors.append('At least two licensed MDM elements need their documented qualifying level and exact source evidence.')
        elif basis == 'time' and requirements['time'] is not None:
            timing = requirements['time']
            minutes, quote = context.get('time_minutes'), context.get('time_evidence')
            if (type(minutes) is not str or not re.fullmatch('[0-9]{1,4}', minutes)
                    or not timing['minimum'] <= int(minutes) <= timing['maximum']):
                errors.append('Document total practitioner time within this dated licensed criterion.')
            if (not _qualified_quote(run, quote) or not _terms(quote, timing['total_time_terms'])
                    or re.findall(r'\b[0-9]+\b', quote or '') != [minutes]):
                errors.append('Time evidence must state one total practitioner-day value; direct time and total time are never added.')
            if any(context.get(key) is not True for key in ('time_qualified_clinician', 'time_same_day', 'time_excludes_separately_reported')):
                errors.append('Confirm qualified practitioner, same service day and exclusion of separately reported activities.')
            instructions = instructions + ['Exclude from time: ' + value for value in timing['excluded_activities']]
        else:
            errors.append('Choose a documented MDM or time basis supplied by this licensed criterion.')
    return {'valid': not errors, 'errors': errors,
            'instructions': [{'kind': 'licensed_instruction', 'text': item, 'reference': row['reference']} for item in instructions],
            'rule_reference': row['reference'], 'requires_review': bool(row['instructions']), 'description': row['description']}


def validate_cpt_selection(run, code, evidence, *, evidence_spans=None):
    if type(evidence) is not str:
        return {'valid': False, 'errors': ['CPT selection requires exact source evidence text.'], 'instructions': []}
    reference, reason = _reference(run)
    if reference is None:
        return {'valid': False, 'errors': [reason], 'instructions': []}
    from .models import Code as CodeRow
    official = CodeRow.objects.filter(release=reference.release, code=code).first()
    rule = reference.tabular['codes'].get(code)
    if official is None or rule is None or official.description != rule['description']:
        return {'valid': False, 'errors': ['The licensed description and dated code catalogue do not match.'], 'instructions': []}
    return _validate(run, code, evidence, reference,evidence_spans=evidence_spans)


def procedure_candidates(run, concepts):
    reference, _reason = _reference(run)
    if reference is None:
        return []
    if type(concepts) is dict:
        concepts = concepts.get('concepts', [])
    if type(concepts) is not list:
        return []
    from .models import Code as CodeRow
    results = []
    for index, item in enumerate(reference.index):
        row = reference.tabular['codes'][item['code']]
        if row['kind'] == 'office_em':
            matches = [{}] if not concepts else []
        else:
            matches = []
            for concept in concepts:
                if type(concept) is not dict or concept.get('kind') != 'procedure':
                    continue
                evidence = _evidence(run, concept, row['requirements'])
                if _span(run, evidence.get('source')) and _terms(evidence['source']['quote'], item['terms']):
                    matches.append(evidence)
        for evidence in matches:
            judgment = _validate(run, item['code'], evidence, reference)
            if not judgment['valid']:
                continue
            official = CodeRow.objects.filter(release=reference.release, code=item['code']).first()
            if official is None or official.description != row['description']:
                continue
            results.append({'entry_id': 'cpt:' + str(reference.release_id) + ':' + str(index),
                            'system': 'CPT', 'code': official.code, 'description': official.description,
                            'path': [item['reference'], row['reference']], 'instructions': judgment['instructions'],
                            'requires_review': judgment['requires_review'], 'release_id': str(reference.release_id),
                            'release_version': reference.release.version})
            break
    return results
