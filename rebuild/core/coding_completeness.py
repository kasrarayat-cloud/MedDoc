"""Source-owned ICD coverage, separate from immutable provider predictions.

This module makes no requests, queries, decisions or exports.  Its inventory is
deliberately bounded: an unparsed current assessment/report remains an explicit
obligation, not evidence that the source contains no other condition.  Candidate
codes come only from the supplied authoritative reference, never from provider
alternatives, generated clinical answer text, or a condition-to-code table.
"""
from copy import deepcopy
from datetime import date
import hashlib
import re
from types import SimpleNamespace
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

from . import coding_engine as engine, coding_nec, corti_coding
from .clinical_source_context import (SOURCE_GOVERNANCE_PROFILE, source_context,
                                      source_date, owned_current)
from .generation import source_units
from .coding_terminology import normalize_code

CONTRACT = 'source-icd-completeness-v1'
REFERENCE_CONTRACT = 'source-reference-closure-v1'
MAX_ITEMS = 64
MAX_SOURCE = 128000
MAX_REFERENCE_ENTRIES = 2048
MAX_CANDIDATES = 48
_ASSESSMENT = {'assessment', 'impression'}
_NOMINAL = re.compile(r'[A-Za-z][A-Za-z -]{0,178}[A-Za-z]|[A-Za-z]')
_NON_NOMINAL = re.compile(r'\b(?:he|she|they|patient|reports?|retracts?|withdraws?|'
    r'believes?|claims?|denies?|has|have|had|is|are|was|were|will|would|could|may|'
    r'statement|account|documentation|information|whether|if|because|although|but|'
    r'which|whose|occurs?|feels?|improves?|resolves?)\b', re.I)
_PRESENT = r'(?:today|now|currently|at this visit|at this encounter|during this encounter|during the current encounter)'
_EVALUATION = re.compile(r'(?P<objects>.+?)\s+(?:is|are|was|were)\s+(?:both\s+)?'
    r'(?:evaluated|assessed|addressed|managed)(?:\s+and\s+discussed)?'
    r'(?P<tail>\s+.+)?', re.I)
_NEGATIVE = re.compile(r'(?:no|denies?|without)\s+.+|.+?\s+(?:is|are|was|were)\s+'
    r'(?:absent|denied|not present|not established|not diagnosed)(?:\s+today)?', re.I)
_UNCERTAIN_PREFIX = re.compile(r'(?:possible|possibly|probable|suspected|unconfirmed|'
    r'uncertain|questionable|potential|conjectured|unlikely|unsubstantiated|rule out)\b', re.I)
_UNCERTAIN_PREDICATE = re.compile(r'(?P<objects>.+?)\s+(?:is|are|remains?|remain)\s+'
    r'(?:a\s+)?(?:possibility|possibilities|consideration|considerations|uncertain|'
    r'unconfirmed|suspected)(?:,?\s+not established diagnos(?:is|es))?', re.I)
_META = re.compile(r'(?:the\s+)?(?:underlying\s+)?(?:etiology|cause)\s+'
    r'(?:is|remains)\s+(?:unknown|uncertain|undetermined)|'
    r'no\s+(?:definitive\s+)?(?:underlying\s+)?(?:disease|diagnosis)\s+'
    r'is\s+(?:diagnosed|established)(?:\s+at this (?:visit|encounter))?', re.I)
_LIST = re.compile(r'\s*,\s*(?:and\s+)?|\s+and\s+', re.I)
_ASSESSMENT_LABEL = (r'(?:(?:clinical\s+)?assessment(?:\s*(?:and|&|/)\s*plan)?|a\s*[/&]\s*p|'
    r'impression|diagnosis|diagnoses|current problems?|current conditions?|'
    r'(?:(?:other|current|active)\s+)?(?:problems?|conditions?|symptoms?|complaints?)\s+'
    r'(?:addressed|evaluated|assessed|managed|reviewed)(?:\s+today)?)')
_EVALUATION_CUE = re.compile(r'\b(?:evaluated|assessed|addressed|diagnosed|managed|'
    r'assessment|diagnoses)\b', re.I)


def _span(unit, start=0, end=None):
    end = len(unit['quote']) if end is None else end
    return {'start': unit['start'] + start, 'end': unit['start'] + end,
            'quote': unit['quote'][start:end]}


def _identity(kind, text):
    return kind + ':' + engine.digest({'contract': CONTRACT, 'text': text})[:24]


def _parts(objects, *, report=False):
    """Return complete literal nominal objects, without erasing modifiers."""
    result = []
    for raw in _LIST.split(objects):
        value = raw.strip()
        if report:
            # Only a complete, already reviewed ordinary timing adjunct can
            # be separated from the condition. The full statement stays in
            # evidence and in all downstream source checks.
            adjunct = re.search(r'\s+(?:for|lasting|persisting for|today|currently|now|'
                r'at present|daily|nightly|intermittently|since|after|with|according to|as reported by)\b', value, re.I)
            if adjunct:
                if not engine._complete_presence_tail(engine.norm(value[adjunct.start():])):
                    return None
                value = value[:adjunct.start()].rstrip()
        if not _NOMINAL.fullmatch(value) or _NON_NOMINAL.search(value):
            return None
        result.append(value)
    return result if result and len(result) <= MAX_ITEMS else None


def reference_terms(condition_text):
    """Exact source phrase plus explicit typed authority parent vocabulary.

    A typed narrower concept is useful for finding its Index main term.  This
    is not itself an ICD mapping or permission to discard a source qualifier.
    """
    words = condition_text.split()
    # Retrieval only: all words remain in the condition and its source proof.
    # A compact authoritative main-term scan can thus find Pain for a literal
    # qualified pain phrase without treating the main term as a diagnosis.
    values = [' '.join(words[a:b]) for a in range(len(words)) for b in range(a + 1, len(words) + 1)]
    raw, relations = coding_nec.load()
    for relation in relations:
        if relation['descriptor_id'] not in raw['nec_relation_roots']:
            continue
        if engine.norm(condition_text) in {engine.norm(t) for t in relation['child']['terms']}:
            values.extend(relation['child']['terms'])
            values.extend(relation['parent']['terms'])
    return sorted(set(values), key=lambda value: (engine.norm(value), value))


def _review_context(notes, units):
    """Add review-local provenance scope without changing historical contracts.

    An unparsed account header governs the following prose; an ordinary SOAP
    heading cannot silently make that account verified. Explicit foreign and
    historical account headers keep their existing scope. This identifies a
    review obligation, not a new source fact or a universal language parser.
    """
    context = source_context(notes, units, profile=SOURCE_GOVERNANCE_PROFILE)
    qualified = False
    account = r'(?:accounts?|records?|reports?|notes?|statements?|documentation|clinical information|clinical history|source)'
    neutral = re.compile(r'(?:(?:current|present)\s+)?(?:(?:clinical|encounter|source)\s+)?'
        r'(?:account|record|notes?|documentation|clinical history)', re.I)
    for unit in units:
        row = context['units'][unit['start']]
        text = unit['quote'].strip()
        body = text.rstrip(':.').strip()
        # Account framing is semantic scope, not a colon convention. Preserve
        # the whole nominal/frame (including unknown qualifications); never
        # turn its embedded assertion into an independently verified source.
        framed = re.match(r'(?:according to|based on|from|per|as reported by|as described by)\b',body,re.I)
        nominal_match = re.fullmatch(r'(?P<qualifier>[A-Za-z][A-Za-z -]{0,178}\b)'+account,body,re.I)
        nominal = (nominal_match and not re.search(r'\b(?:he|she|they|patient|has|have|had|is|are|was|were|'
                r'reports|describes|reviewed|reviewing|ordered|orders|documented|records|recorded)\b',
                nominal_match['qualifier'],re.I))
        if ((text.endswith(':') or framed or nominal) and re.search(r'\b'+account+r'\b',body,re.I)
                and not neutral.fullmatch(body)
                and row['section_timing'] == 'current' and row['subject'] != 'foreign'):
            qualified = True
        if qualified and row['section_timing'] == 'current' and row['subject'] != 'foreign':
            row['issues'].append('An unresolved source-account header governs this assertion; structural headings do not establish its provenance.')
    return context


def inventory(notes, *, retained_facts=()):
    """Inventory complete source assertions independently of model omissions.

    Retained facts are intentionally not authority for discovery.  Their IDs
    may corroborate an exact literal source term, but deleting every extracted
    fact cannot remove an inventory obligation or manufacture completeness.
    """
    if type(notes) is not str or not notes.strip() or len(notes.encode()) > MAX_SOURCE:
        raise ValidationError('Source completeness requires a bounded nonempty original note.')
    units, _ = source_units(notes, [])
    context = _review_context(notes, units)
    items, unresolved, excluded = {}, [], []
    assessment_section = None
    assessment_context_section = None
    patient = re.escape(context.get('patient_name') or '\0')
    report = re.compile(r'(?:(?:the\s+)?patient|he|she|they|' + patient + r')\s+'
        r'(?:(?:also|currently|still)\s+)?(?:reports?|experiences?|endorses?|describes?|'
        r'complains? of|presents? with|has|have)\s+(?P<objects>.+)', re.I)
    complaint = re.compile(r'(?:(?:the|his|her|their)\s+)?(?:current |present |chief )?'
        r'(?:complaint|concern|symptom)\s+is\s+(?P<objects>.+)', re.I)
    presence = re.compile(r'(?P<objects>.+?)\s+(?:is|are)\s+present(?P<tail>\s+.+)?', re.I)
    report_cue = re.compile(r'\b(?:(?:the\s+)?patient|he|she|they|' + patient + r')\s+'
        r'(?:(?:also|currently|still|previously)\s+)*(?:(?:is|are|was|were)\s+)?'
        r'(?:reports?|reported|experiences?|experiencing|endorses?|complains?|complaining)\b',re.I)

    def gap(unit, reason):
        unresolved.append({'id': _identity('source-gap', str(unit['start']) + ':' + unit['quote']),
            'condition_text': unit['quote'], 'evidence': [_span(unit)],
            'current_evaluation_evidence': [], 'state': 'unresolved',
            'reason': reason, 'approved_codes': [], 'candidates': [], 'saved_outcome': None})

    def add(term, unit, *, evaluated):
        key = engine.norm(term)
        value = items.setdefault(key, {'id': _identity('source-condition', key),
            'condition_text': term, 'evidence': [], 'current_evaluation_evidence': [],
            'state': 'unresolved', 'approved_codes': [], 'candidates': [], 'saved_outcome': None})
        evidence = _span(unit)
        if evidence not in value['evidence']:
            value['evidence'].append(evidence)
        if evaluated and evidence not in value['current_evaluation_evidence']:
            value['current_evaluation_evidence'].append(evidence)

    for unit in units:
        text = unit['quote'].strip().rstrip('.')
        heading = re.fullmatch(r'(?:[AS]\s*[-–:]\s*)?('+_ASSESSMENT_LABEL+r')\s*:?', text, re.I)
        inline = re.fullmatch(r'(?:[AS]\s*[-–:]\s*)?('+_ASSESSMENT_LABEL+r')\s*:\s*(.+)', text, re.I)
        row = context['units'][unit['start']]
        section = row['section']
        if heading:
            assessment_section = heading[1].casefold()
            assessment_context_section = section
            continue
        if assessment_section and section != assessment_context_section:
            assessment_section = None
        if re.fullmatch(r'(?:[SOP]\s*[-–:]\s*)?(?:subjective|objective|plan|history of present illness|review of systems|physical examination|examination|exam|history)\s*:?', text, re.I):
            assessment_section = None
        in_assessment = section in _ASSESSMENT or assessment_section is not None or inline is not None
        if inline:
            text = inline[2].strip()
        evaluated = _EVALUATION.fullmatch(text)
        reported = report.fullmatch(text) or complaint.fullmatch(text)
        present = presence.fullmatch(text)
        opaque_assertion = re.match(r'(?:(?:the\s+)?patient|he|she|they|' + patient + r')\s+'
            r'(?:(?:also|currently|still)\s+)?(?:suffers? from|notes?|developed|is experiencing|'
            r'is diagnosed with|was diagnosed with)\b', text, re.I)
        # Discovery is deliberately broader than permission. An unfamiliar
        # actor, adverb or ordering around a clinical evaluation/report cannot
        # disappear merely because the complete assertion parser rejects it.
        # It becomes a visible unresolved source clause, never an eligible code.
        evaluation_cue = _EVALUATION_CUE.search(text) or report_cue.search(text)
        if not (in_assessment or evaluated or reported or present or opaque_assertion or evaluation_cue):
            continue
        if row['subject'] == 'foreign' or row['section_timing'] != 'current' or row['timing'] == 'past':
            excluded.append({'evidence': _span(unit), 'reason': 'Explicit other-person or historical/future encounter scope.'})
            continue
        if not owned_current(context, unit):
            gap(unit, 'Current condition-bearing source has unresolved ownership, timing, quotation or governance.')
            continue
        if _META.fullmatch(text):
            excluded.append({'evidence': _span(unit), 'reason': 'Complete statement of diagnostic uncertainty or no established underlying diagnosis.'})
            continue
        uncertain = _UNCERTAIN_PREDICATE.fullmatch(text)
        if uncertain and _parts(uncertain['objects']):
            excluded.append({'evidence': _span(unit), 'reason': 'Complete explicitly uncertain condition statement, not a confirmed outpatient diagnosis.'})
            continue
        if reported:
            negative_objects = _parts(reported['objects'])
            if negative_objects and all(re.match(r'no\b', value, re.I) for value in negative_objects):
                excluded.append({'evidence': _span(unit), 'reason': 'Complete reported negative condition/history list.'})
                continue
            negative_past = re.fullmatch(r'not had\s+(.+)', reported['objects'], re.I)
            if negative_past and _parts(negative_past[1]):
                excluded.append({'evidence': _span(unit), 'reason': 'Complete reported absence of a prior event.'})
                continue
        # Negation applies only to a complete nominal list/predicate. A trailing
        # second assertion must not disappear with a negative first clause.
        if _NEGATIVE.fullmatch(text) and not re.search(r'\b(?:but|although|however)\b|;', text, re.I):
            body = re.sub(r'^(?:no|denies?|without)\s+', '', text, flags=re.I)
            body = re.sub(r'\s+(?:is|are|was|were)\s+(?:absent|denied|not present|not established|not diagnosed)(?:\s+today)?$', '', body, flags=re.I)
            if _parts(body):
                excluded.append({'evidence': _span(unit), 'reason': 'Complete explicit negative condition statement.'})
                continue
        if evaluated:
            tail = (evaluated['tail'] or '').strip()
            if _parts(evaluated['objects']) and re.fullmatch(
                    r'(?:yesterday|last (?:week|month|year)|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) '
                    r'(?:days?|weeks?|months?|years?) ago|in (?:19|20)\d\d)',tail,re.I):
                excluded.append({'evidence':_span(unit),'reason':'Complete explicitly historical evaluation, not a current encounter condition.'})
                continue
            current = not tail or re.fullmatch(_PRESENT, tail, re.I)
            if tail.lower().startswith('on '):
                current = source_date(tail[3:]) == context.get('service_date') and context.get('service_date') is not None
            parts = _parts(evaluated['objects']) if current else None
        elif reported:
            parts = _parts(reported['objects'], report=True)
        elif present:
            parts = (_parts(present['objects']) if engine._complete_presence_tail(
                engine.norm(present['tail'] or '')) else None)
        elif in_assessment:
            bare = re.sub(r'^\d+[.)]\s*', '', text)
            parts = _parts(bare)
        else:
            parts = None
        if not parts:
            gap(unit, 'The complete current assessment/report cannot be separated into verified condition objects without interpreting or dropping text.')
            continue
        for term in parts:
            if _UNCERTAIN_PREFIX.match(term):
                excluded.append({'condition_text': term, 'evidence': _span(unit),
                    'reason': 'Explicit uncertain condition; no affirmative diagnosis inferred.'})
            else:
                add(term, unit, evaluated=bool(evaluated or in_assessment))
    for item in items.values():
        item['reference_terms'] = reference_terms(item['condition_text'])
        item['retained_fact_ids'] = sorted({f.get('id') for f in retained_facts
            if type(f) is dict and type(f.get('id')) is str
            and type(f.get('value_evidence')) is dict
            and f['value_evidence'].get('quote') == item['condition_text']
            and notes[f['value_evidence'].get('start', 0):f['value_evidence'].get('end', 0)] == item['condition_text']})
        if not item['current_evaluation_evidence']:
            item['reason'] = 'Current report found, but its relevance/evaluation at this encounter is not independently established.'
    if len(items) + len(unresolved) > MAX_ITEMS:
        raise ValidationError('Source completeness exceeds the finite condition inventory bound.')
    date_headers = [unit for unit in units if owned_current(context, unit)
        and re.match(r'\s*Date\s+of\s+service\s*:',unit['quote'],re.I)]
    blockers = list(context['issues'])
    if date_headers and not context.get('service_date'):
        blockers.append('The original source service-date header is ambiguous or unparsed.')
    result = {'contract': CONTRACT, 'source_sha256': hashlib.sha256(notes.encode()).hexdigest(),
        'service_date': context.get('service_date'),
        'items': list(items.values()), 'unresolved': unresolved, 'excluded': excluded,
        'blockers': blockers,
        'reference_terms': sorted({t for item in items.values() for t in item['reference_terms']}),
        'coverage_limit': 'Bounded current assessment and explicit evaluation/report grammar. Unparsed or unevaluated current assertions remain unresolved; this is not universal natural-language comprehension.'}
    if len(result['reference_terms']) > 64:
        raise ValidationError('Source completeness exceeds the finite authoritative retrieval vocabulary bound.')
    # Fact annotations are supplementary and cannot change source identity or
    # the reference search watched set.
    result['inventory_sha256'] = engine.digest({k:v for k,v in result.items() if k != 'items'} | {
        'items': [{k:v for k,v in item.items() if k != 'retained_fact_ids'} for item in result['items']]})
    return result


def _date(value):
    if type(value) is date:
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError('Source review requires an exact dated ICD release.') from exc


def _reference(reference, inv, run):
    """Validate the bounded loader's watched set and complete family structure."""
    expected = {'contract': REFERENCE_CONTRACT, 'source_sha256': inv['source_sha256'],
        'inventory_sha256': inv['inventory_sha256'], 'terms': sorted(set(inv['reference_terms'])), 'complete': True}
    if getattr(reference, 'completeness_scope', None) != expected:
        raise ValidationError('Source review requires the complete source-bound authoritative retrieval projection.')
    release = reference.release
    when = _date(run.inputs['service_date'])
    if inv.get('service_date') and _date(inv['service_date']) != when:
        raise ValidationError('The original source date and saved coding service date differ.')
    start, end = _date(release.effective_from), _date(release.effective_until)
    url = urlsplit(release.source_url)
    if (release.system != 'ICD-10-CM' or not start <= when <= end
            or url.scheme != 'https' or url.hostname not in ('www.cms.gov', 'www.cdc.gov', 'ftp.cdc.gov')
            or not re.fullmatch(r'[0-9a-f]{64}', release.sha256)
            or not re.fullmatch(r'[0-9a-f]{64}', reference.digest)):
        raise ValidationError('Source review reference authority, release date or digest is invalid.')
    bound = next((r for r in run.releases if str(r.get('id')) == str(reference.release_id)), None)
    if (not bound or bound.get('sha256') != release.sha256 or bound.get('version') != release.version
            or _date(bound.get('effective_from')) != start or _date(bound.get('effective_until')) != end):
        raise ValidationError('Source review reference does not match the saved run release binding.')
    entries = reference.index
    if type(entries) is not list or len(entries) > MAX_REFERENCE_ENTRIES:
        raise ValidationError('Invalid or oversized source review Index projection.')
    lookup = {}
    for entry in entries:
        if (type(entry) is not dict or type(entry.get('id')) is not str
                or entry['id'] in lookup or type(entry.get('children')) is not list
                or len(entry['children']) != len(set(entry['children']))):
            raise ValidationError('Invalid or duplicate source review Index entry.')
        lookup[entry['id']] = entry
    for entry in entries:
        parent = entry.get('parent_id')
        if parent is not None and (parent not in lookup or entry['id'] not in lookup[parent]['children']):
            raise ValidationError('Source review Index ancestry is incomplete.')
        if any(child not in lookup or lookup[child].get('parent_id') != entry['id'] for child in entry['children']):
            raise ValidationError('Source review requires every authoritative sibling and child.')
        visited, current = set(), entry
        while current.get('parent_id') is not None:
            if current['id'] in visited or len(visited) > 32:
                raise ValidationError('Source review Index ancestry is cyclic or too deep.')
            visited.add(current['id']); current = lookup[current['parent_id']]
    return lookup, {'id': str(reference.release_id), 'version': release.version,
        'source': release.source_url, 'source_sha256': release.sha256,
        'reference_digest': reference.digest,
        'effective_from': start.isoformat(), 'effective_until': end.isoformat()}


def _root(entry, lookup):
    while entry.get('parent_id') is not None:
        entry = lookup[entry['parent_id']]
    return entry


def _condition_spans(notes, item):
    """Literal condition spans; downstream checks still examine whole source."""
    result = []
    for evidence in item['evidence']:
        for match in re.finditer(r'(?<!\w)' + re.escape(item['condition_text']) + r'(?!\w)', evidence['quote'], re.I):
            start, end = evidence['start'] + match.start(), evidence['start'] + match.end()
            span = {'text': notes[start:end], 'start': start, 'end': end, 'status': 'valid', 'context_index': 0}
            if span not in result:
                result.append(span)
    return result


def _condition_reference_errors(notes, concept, condition, reference, unresolved=()):
    """Keep later references attached to the current condition being reviewed.

    A literal qualified route cannot erase a later qualification of its parent
    finding. This is a veto only: neither a reference nor a negative predicate
    establishes a finding, a subtype or an alternative diagnosis. Unparsed
    predicates on a definite current condition reference stay unresolved.
    """
    units, _ = source_units(notes, [])
    context = _review_context(notes, units)
    aliases = set(engine.anchors(concept))
    # Retain the literal source's nominal suffixes around an existing official
    # head, e.g. "abdominal pain" inside "periumbilical abdominal pain". This
    # widens only contradiction detection, never candidate discovery/permission.
    words = engine.norm(condition).split()
    for start in range(len(words)):
        suffix = ' '.join(words[start:])
        if any(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)', suffix) for term in aliases):
            aliases.add(suffix)
    guarded = {**concept, 'index_terms': sorted(aliases)}
    qualifiers = [s['qualifier'] for s in engine.index_subtypes(reference, concept,
        source_contract=engine.CURRENT_SOURCE_CONTRACT)]
    reference_words = r'(?:reported|documented|described|noted|mentioned|stated|recorded)'
    reference_before = re.compile(r'(?:(?:the|this|that|his|her|their)(?:\s+'+reference_words+r')?|'+reference_words+r')?')
    reference_after = re.compile(r'^'+reference_words+r'\s+(?:above|earlier)(?:\s+in (?:this|the) (?:note|account|record))?\s*')
    patient = re.escape(engine.norm(context.get('patient_name') or '\0'))
    patient_subject = r'(?:the patient|patient|he|she|they|'+patient+r')'
    unresolved_starts = {span['start'] for item in unresolved for span in item['evidence']}
    governing_owner = None
    for unit in units:
        row = context['units'][unit['start']]
        if row['subject'] in ('patient', 'foreign'):
            governing_owner = row['subject']
        # A separately scoped past or foreign account is not a correction of
        # the current patient's account. Within a current section, however,
        # "the reported pain is attributed to her mother" is a reassignment.
        if row['section_timing'] != 'current' or governing_owner == 'foreign':
            continue
        for clause, before, after in engine.condition_mentions(unit['quote'], guarded, qualifiers):
            before, after = before.strip(), after.strip()
            if engine.explicit_other_subject(before) or re.search(
                    r'\b(?:mother|father|sister|brother|grandmother|grandfather|relative|friend|spouse)'
                    r'(?:\s+s\s*|\s+(?:has|had|reports|reported|denies|denied|experiences|experienced)\b)', before):
                continue
            if re.search(r'\b(?:during|at|in|for)\s+(?:(?:the|his|her)\s+)?'
                    r'(?:previous|prior|earlier|past)\s+(?:visit|encounter|appointment)\b', before):
                continue
            if engine._condition_integrity_mention(clause, guarded, context, units):
                continue
            if unit['start'] in unresolved_starts:
                # Completeness and eligibility share the same full assertion.
                # An unresolved current clause referring to this condition
                # cannot leave its candidate selectable merely because another
                # sentence supplied a shorter positive assertion. The scoped
                # mention filter above retains distinct official subtypes.
                return ['An unresolved current source assertion refers to this condition; its separate inventory gap cannot be ignored for code eligibility.']
            negative_current = re.fullmatch(patient_subject+r'\s+'
                r'(?:(?:is|are|does|do)\s+(?:not|no longer)\s+|(?:no longer|never)\s+)'
                r'(?:experiencing|experience|experiences|having|have|has|feeling|feel|feels)\s*'
                r'(?:(?:any|the|this|that|current)\s*)*', before)
            if negative_current:
                return ['The complete source denies current experience of this condition.']
            qualified_reference = bool(re.search(r'\b'+reference_words+r'\b', before)
                or (re.search(r'\b(?:the|this|that|his|her|their|whether|if)$', before)
                    and re.match(r'(?:is|are|was|were|has|have|had|remains?|'+reference_words+r')\b', after)))
            if not reference_before.fullmatch(before) and not qualified_reference:
                continue
            stripped = reference_after.sub('', after, count=1)
            explicit_reference = (stripped != after or bool(re.search(reference_words, before))
                or bool(re.search(r'\b'+reference_words+r'\s+(?:above|earlier)\b', after)))
            if qualified_reference and not reference_before.fullmatch(before):
                # A complete patient report may contain a definite object.
                # Its parsed whole predicate is different from an embedded
                # positive proposition under an unknown/negative preamble.
                if (owned_current(context, unit) and engine._current_condition_assertion(
                        clause, before, after, context, row) is True):
                    continue
                return ['A current condition reference has an unresolved qualifier before the reported finding.']
            # Bare assessment terms and coordinated clinical lists are handled
            # by the ordinary assertion validator. Only a complete predicate or
            # explicit account reference invokes this additional review guard.
            if not explicit_reference and not re.match(r'(?:is|are|was|were|has|have|had|belongs?|refers?|concerns?|remains?)\b', stripped):
                continue
            assertion = engine._current_condition_assertion(clause, '', stripped, context, row)
            if assertion is True and owned_current(context, unit):
                continue
            # A complete current evaluation may accompany an independently
            # affirmed condition; it cannot itself prove current presence.
            if (owned_current(context, unit) and re.fullmatch(r'(?:is|are|was|were)\s+'
                    r'(?:evaluated|assessed|addressed|managed)(?:\s+and discussed)?\s+'
                    +_PRESENT, stripped, re.I)):
                continue
            return ['A current source reference to this condition is corrected, qualified, retimed, reassigned or unresolved.']
    return []


def _qualified_route(run, reference, row, proposal, roots, lookup, selected):
    """Bind a complete qualified phrase to its own official specific route.

    This does not license arbitrary adjectives. The complete literal object
    must be the Tabular phrase or its already supported connected Index-parent
    expansion; every token must belong to that same authoritative route. The
    main-term aliases remain present, so a later denial/correction of the
    unqualified finding still vetoes this specific suggestion.
    """
    text = row['condition_text']
    words = set(engine.norm(text).split())
    for entry in reference.index:
        if entry.get('code') != proposal['code'] or entry.get('requires_review'):
            continue
        head = _root(entry, lookup)
        if head['id'] not in roots:
            continue
        chain, node = [], entry
        while node:
            chain.append(node); node = lookup.get(node.get('parent_id'))
        description = proposal['terminology']['description']
        authority_words = set(engine.norm(' '.join([description, *(n.get('term', '') for n in chain)])).split())
        if (not words or not words <= authority_words or words & (engine.ROUTE_WORDS | engine.TAXONOMY_HEADS)
                or not (engine.norm(text) == engine.norm(description)
                    or engine.tabular_specific_route(chain, text, description))):
            continue
        head_terms = engine.index_head_terms(head, description)
        for span in proposal['evidence']:
            for clause in engine.enclosing_clauses(run.inputs['notes'], span['text']):
                concept = dict(id=row['id'], term=text, index_terms=[text, *head_terms], evidence=clause,
                    kind='symptom' if proposal['code'].startswith('R') else 'diagnosis',
                    certainty='confirmed', temporality='current', subject='patient', relevant=True,
                    missing_detail='', integral_to='')
                if engine.current_source_scope_errors(run.inputs['notes'], concept, source_contract=engine.CURRENT_SOURCE_CONTRACT):
                    continue
                subtypes = engine.index_subtypes(reference, concept, source_contract=engine.CURRENT_SOURCE_CONTRACT)
                disposition, reason = engine.source_disposition(concept, run.inputs['notes'],
                    qualifiers=[s['qualifier'] for s in subtypes], source_contract=engine.CURRENT_SOURCE_CONTRACT)
                validation = engine.contextual_validation(run, reference, proposal['code'], concept, selected)
                if (disposition != 'eligible' or not validation['valid'] or validation.get('requires_review')
                        or engine.index_route_errors(entry, concept, lookup, code_description=description,
                            source_contract=engine.CURRENT_SOURCE_CONTRACT)
                        or engine.specificity_errors(concept, proposal['code'], description)
                        or engine.more_specific_source_routes(entry, concept, run.inputs['notes'], reference, subtypes)):
                    continue
                candidate = dict(code=proposal['code'], system='ICD-10-CM', entry_id=entry['id'],
                    description=description, path=entry.get('path', []), release_id=str(reference.release_id),
                    release_version=reference.release.version, instructions=validation.get('instructions', []),
                    qualified_phrase_proof={'literal':text,'entry_ids':[n['id'] for n in reversed(chain)],
                        'source_sha256':hashlib.sha256(run.inputs['notes'].encode()).hexdigest(),
                        'reference_digest':reference.digest,
                        'basis':'Complete literal phrase and all tokens bound to one connected official Index/Tabular route.'})
                return concept, candidate, {'disposition':disposition,'reason':reason,
                    'index_scope_entry_ids':[s['entry']['id'] for s in subtypes]}
    return None, None, None


def evaluate(run, reference, *, approved_codes=(), inventory_result=None):
    """Recompute source-derived review candidates without altering a prediction.

    The run can have any historical provider contract.  This separate review
    explicitly uses the current source safety contract on a small copied input.
    No stored eligible flag, provider candidate or generated answer is trusted.
    """
    notes = run.inputs['notes']
    inv = inventory(notes)
    if inventory_result is not None and (inventory_result.get('inventory_sha256') != inv['inventory_sha256']
            or inventory_result.get('source_sha256') != inv['source_sha256']):
        raise ValidationError('The source review inventory is stale or belongs to different notes.')
    lookup, release = _reference(reference, inv, run)
    if (type(approved_codes) not in (list, tuple, set, frozenset) or len(approved_codes) > MAX_ITEMS
            or any(type(code) is not str for code in approved_codes)):
        raise ValidationError('Invalid approved ICD coverage inputs.')
    approved = set()
    for code in approved_codes:
        # An independently accepted CPT service can never cover an ICD row.
        if re.fullmatch(r'\d{4}[0-9A-Z]', code):
            continue
        try:
            valid = normalize_code(code) == code and code in reference.tabular['codes']
        except ValueError:
            valid = False
        if not valid:
            raise ValidationError('Approved ICD coverage must be present in the dated authoritative projection.')
        approved.add(code)
    copied = SimpleNamespace(inputs=deepcopy(run.inputs), releases=deepcopy(run.releases),
        config={**deepcopy(getattr(run, 'config', {})), 'clinical_source_contract': engine.CURRENT_SOURCE_CONTRACT})
    rows = deepcopy(inv['items']) + deepcopy(inv['unresolved'])
    checked = []
    for row in rows:
        if 'reference_terms' not in row or not row['current_evaluation_evidence'] or inv['blockers']:
            row['reason'] = row.get('reason') or 'Source ownership or current evaluation is not established.'
            continue
        terms = {engine.norm(t) for t in row['reference_terms']}
        roots = {entry['id'] for entry in reference.index if entry.get('parent_id') is None
            and any(engine.norm(term) in terms and engine.norm(term) not in engine.TAXONOMY_HEADS
                for term in engine.index_head_terms(entry, reference.tabular['codes'].get(entry.get('code'), '')))}
        codes = []
        for entry in reference.index:
            code = entry.get('code')
            if code not in reference.tabular['codes'] or _root(entry, lookup)['id'] not in roots:
                continue
            # Narrow retrieval using the complete literal object only. This
            # check cannot approve anything: current ownership/assertion and
            # the entire source are still independently tested below. An NEC
            # branch stays available for the separate typed-authority proof.
            lexical = {'evidence': row['condition_text'], 'kind': 'symptom'}
            if (engine.norm(entry.get('term', '')) != 'specified nec'
                    and engine.index_route_errors(entry, lexical, lookup,
                        code_description=reference.tabular['codes'][code], source_contract=engine.CURRENT_SOURCE_CONTRACT)):
                continue
            if code not in codes:
                codes.append(code)
        if len(codes) > MAX_CANDIDATES:
            row['reason'] = 'The complete authoritative family exceeds the finite candidate-review bound.'
            continue
        row['authoritative_candidate_count'] = len(codes)
        for code in codes:
            proposal = {'id': row['id'], 'code': code,
                'terminology': {'description': reference.tabular['codes'][code]},
                'evidence': _condition_spans(notes, row)}
            concept, candidate, source_check = corti_coding._icd_source(copied, reference, proposal, sorted(approved | {code}))
            if not candidate:
                concept, candidate, source_check = _qualified_route(copied, reference, row, proposal, roots, lookup, sorted(approved | {code}))
            if not candidate or _root(lookup[candidate['entry_id']], lookup)['id'] not in roots:
                continue
            reference_errors = _condition_reference_errors(notes, concept, row['condition_text'], reference, inv['unresolved'])
            source_check = {**source_check, 'condition_reference_errors': reference_errors}
            proof = {'contract': CONTRACT, 'source_sha256': inv['source_sha256'],
                'inventory_sha256': inv['inventory_sha256'], 'condition_id': row['id'],
                'source_contract': engine.CURRENT_SOURCE_CONTRACT, 'reference': release,
                'candidate': candidate, 'source_check': source_check, 'concept': concept}
            value = {'id': _identity('source', engine.digest(proof)), 'origin': 'saved_source',
                'condition_id': row['id'], 'system': 'ICD-10-CM', 'code': code,
                'description': candidate['description'], 'eligible': not reference_errors, 'hold_reasons': reference_errors,
                'route': ' > '.join(candidate['path']), 'index_route': deepcopy(candidate),
                'instructions': deepcopy(candidate['instructions']),
                'evidence': [{'text': e['quote'], 'start': e['start'], 'end': e['end']} for e in row['evidence']],
                'release': deepcopy(release), 'support_digest': engine.digest(proof), 'proof': proof}
            row['candidates'].append(value)
            if reference_errors:
                row['reason'] = reference_errors[0]
            checked.append({'concept': concept, 'eligible': not reference_errors, 'row': row, 'candidate': value})
        if len(row['candidates']) != 1:
            row['reason'] = ('No unique authoritative source-supported code is established.' if not row['candidates']
                             else 'More than one authoritative code remains possible; clinician detail is required.')
            for value in row['candidates']:
                value['eligible'] = False; value['hold_reasons'].append(row['reason'])
    integral = corti_coding.integral_holds(checked, notes)
    proposed_codes = {v['candidate']['code'] for v in checked if v['candidate']['eligible']}
    for value in checked:
        candidate, row = value['candidate'], value['row']
        if not candidate['eligible']:
            continue
        validation = engine.contextual_validation(copied, reference, candidate['code'], value['concept'], sorted(approved | proposed_codes))
        if row['id'] in integral or not validation['valid'] or validation.get('requires_review'):
            candidate['eligible'] = False
            candidate['hold_reasons'].append('Complete-source integral-condition or combined Tabular instructions require review.')
            row['reason'] = candidate['hold_reasons'][-1]
        else:
            row['state'] = 'covered' if candidate['code'] in approved else 'review_required'
            row['approved_codes'] = [candidate['code']] if row['state'] == 'covered' else []
    suggestions = [value['candidate'] for value in checked]
    covered = sum(row['state'] == 'covered' for row in rows)
    reviewable = sum(row['state'] == 'review_required' for row in rows)
    result = {'contract': CONTRACT, 'bindings': {'source_sha256': inv['source_sha256'],
        'inventory_sha256': inv['inventory_sha256'], 'run_id': str(getattr(run, 'pk', getattr(run, 'id', ''))),
        'run_input_digest': getattr(run, 'input_digest', ''),
        'provider_result_digest': engine.digest(getattr(run, 'result', {})),
        'source_contract': engine.CURRENT_SOURCE_CONTRACT, 'reference': release},
        'inventory': rows, 'suggestions': suggestions, 'excluded': inv['excluded'],
        'blockers': list(inv['blockers']), 'coverage': {'total': len(rows), 'covered': covered,
            'review_required': reviewable, 'unresolved': len(rows) - covered - reviewable,
            'complete': bool(rows) and covered == len(rows) and not inv['blockers'],
            'limit': inv['coverage_limit']}}
    result['support_digest'] = engine.digest(result)
    return result
