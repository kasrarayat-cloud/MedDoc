"""Conservative, extractive review gates for versioned advanced Word mappings.

No provider or document engine runs here. The caller saves a receipt built from
the locked encounter and authenticated clinician, then rechecks it inside the
finalization transaction. Source offsets use Python Unicode character offsets.
"""
from copy import deepcopy
import hashlib
import json
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

from .generation import INJECTION
from .security import membership

BACKEND = 'wm-iov-foss-v2'
ORIGINAL_SHA256 = 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'


def require(value, message):
    if not value:
        raise ValidationError(message)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def _label(value):
    return value.strip().rstrip(':?').strip().casefold()


def _space(value):
    return ' '.join(value.split())


def source_units(notes, label, known_labels=()):
    """Return complete nonempty lines and this exact label's complete values.

    A line assigned to another known field cannot support this field. Offsets
    distinguish duplicate quotations and preserve negation and side context.
    """
    require(isinstance(notes, str) and len(notes) <= 50000, 'Source exceeds the supported review limit.')
    label = _label(label)
    known = {_label(item) for item in known_labels} | {label}
    units, explicit, offset = {}, [], 0
    for line in notes.splitlines(keepends=True):
        full = line.strip()
        if full:
            start = offset + len(line) - len(line.lstrip())
            # Canonical labels can themselves contain colons. Match the entire
            # longest known label, not a prefix such as "Right impression".
            candidates = [(index, _label(full[:index])) for index, char in enumerate(full)
                          if char == ':' and _label(full[:index]) in known]
            delimiter, line_label = max(candidates, default=(None, None))
            if line_label == label:
                raw_value = full[delimiter + 1:]
                value = raw_value.strip()
                if value:
                    value_start = start + delimiter + 1 + len(raw_value) - len(raw_value.lstrip())
                    units[(value_start, value_start + len(value), value)] = {'value': value, 'labelled': True}
                    explicit.append(value)
                units[(start, start + len(full), full)] = {'value': value, 'labelled': True}
            elif line_label not in known:
                units[(start, start + len(full), full)] = {'value': full, 'labelled': False}
        offset += len(line)
    return units, explicit


def validate_evidence(notes, label, evidence, known_labels=()):
    require(isinstance(evidence, list) and len(evidence) <= 100, 'Evidence must be a bounded list of complete source quotations.')
    units, explicit = source_units(notes, label, known_labels)
    result, values, seen = [], [], set()
    for item in evidence:
        require(type(item) is dict and set(item) == {'quote', 'start', 'end'}, 'Evidence needs only the exact quote and source offsets.')
        start, end, quote = item['start'], item['end'], item['quote']
        require(type(start) is int and type(end) is int and isinstance(quote, str)
                and 0 <= start < end <= len(notes) and notes[start:end] == quote,
                'Evidence offsets no longer match the source.')
        key = (start, end, quote)
        require(key in units, 'Evidence must preserve a complete source line or the complete value for this exact label.')
        require(key not in seen, 'Duplicate source evidence was supplied.')
        seen.add(key)
        result.append({'quote': quote, 'start': start, 'end': end})
        values.append(units[key])
    return result, values, len(set(explicit)) > 1


def _mapping(encounter):
    version = encounter.template_version
    fields, requirements = version.fields, version.review_requirements
    backend = version.document_backend
    require(isinstance(backend, dict) and backend.get('backend') == BACKEND
            and backend.get('source_sha256') == version.template.sha256 == ORIGINAL_SHA256
            and isinstance(backend.get('mapping_digest'), str)
            and re.fullmatch(r'[a-f0-9]{64}', backend['mapping_digest']),
            'The qualified original and canonical SDK mapping identity are required.')
    require(isinstance(fields, list) and 0 < len(fields) <= 100
            and isinstance(requirements, list) and 0 < len(requirements) <= 100,
            'The versioned Word clinical review mapping is unavailable.')
    for rows in (fields, requirements):
        require(all(isinstance(row, dict) and isinstance(row.get('key'), str)
                    and row['key'] and isinstance(row.get('label'), str) and row['label'].strip()
                    for row in rows), 'Invalid clinical review mapping.')
        require(len({row['key'] for row in rows}) == len(rows), 'Duplicate mapping keys are not supported.')
    require(len({_label(row['label']) for row in fields}) == len(fields),
            'Answer labels must distinguish every side, anatomical row and repeated location.')
    require(not ({row['key'] for row in fields} & {row['key'] for row in requirements}),
            'Answer and assertion keys must remain distinct.')
    return fields, requirements


def binding(encounter):
    fields, requirements = _mapping(encounter)
    version = encounter.template_version
    require(encounter.department_id == encounter.patient.department_id == version.template.department_id,
            'Patient, template and encounter must share one department.')
    require(type(encounter.revision) is int and encounter.revision >= 0,
            'Invalid source revision.')
    return {'encounter_id': str(encounter.pk), 'department_id': str(encounter.department_id),
            'template_version_id': str(version.pk), 'mapping_number': version.number,
            'original_sha256': version.template.sha256,
            'document_backend': deepcopy(version.document_backend),
            'mapping_sha256': _hash({'fields': fields, 'review_requirements': requirements}),
            'source_revision': encounter.revision, 'source_sha256': _hash(encounter.notes),
            'answers_sha256': _hash(encounter.answers)}


def _authorize(encounter, actor):
    require(getattr(actor, 'is_authenticated', False), 'A signed-in clinician must perform the review.')
    membership(actor, encounter.department, roles=['owner', 'clinician'])
    binding(encounter)


def _reviewed(answer, actor, revision):
    return (answer.get('reviewed') is True and answer.get('reviewed_by') == str(actor.pk)
            and type(answer.get('review_revision')) is int and answer['review_revision'] == revision)


def _narrative_kind(item):
    return type(item) is dict and item.get('kind') in ('unit', 'answers')


def _split_evidence(evidence):
    """(labelled entries, narrative entries). Narrative entries are refused unless the narrative contract is on."""
    require(isinstance(evidence, list) and len(evidence) <= 100, 'Evidence must be a bounded list of complete source quotations.')
    return [item for item in evidence if not _narrative_kind(item)], [item for item in evidence if _narrative_kind(item)]


#: Narrative support verdicts (`wm_narrative.support`) as review blockers.
NARRATIVE_BLOCKERS = {'unsupported': 'narrative_value_not_in_source', 'labelled': 'labelled_value_differs',
                      'correction': 'superseded_by_correction', 'side': 'side_not_supported',
                      'side_unknown': 'side_not_stated'}


def _narrative_units(notes, narrative, entries):
    from . import wm_narrative
    require(all(item.get('kind') == 'unit' for item in entries), 'Answers cite source sentences only.')
    return wm_narrative.unit_entries(notes, narrative['fields'], narrative['context_labels'], entries)


def _field_decision(notes, field, answer, actor, labels, revision, narrative=None):
    require(isinstance(answer, dict), 'Invalid answer review record.')
    text = answer.get('text', '')
    require(isinstance(text, str) and len(text) <= 20000, 'Answer exceeds the supported limit; nothing was truncated.')
    labelled, cited = _split_evidence(answer.get('evidence', []))
    evidence, values, conflict = validate_evidence(notes, field['label'], labelled, labels)
    blockers = []
    if cited:
        if narrative is None:
            blockers.append('narrative_evidence_disabled')
        else:
            evidence = evidence + _narrative_units(notes, narrative, cited)
    if not _reviewed(answer, actor, revision):
        blockers.append('clinician_review_required')
    if answer.get('status') == 'conflict' or conflict:
        blockers.append('conflicting_source')
    if INJECTION.search(notes):
        blockers.append('instruction_like_source')
    if not text:
        # A reviewed empty field is explicit missing information, never zero or
        # an assumed normal finding. Required preprinted claims are checked next.
        _, explicit = source_units(notes, field['label'], labels)
        if explicit:
            blockers.append('documented_value_marked_missing')
        return {'key': field['key'], 'text': '', 'status': 'missing', 'evidence': evidence,
                'reviewed': _reviewed(answer, actor, revision), 'blockers': blockers}
    options = field.get('options')
    if field.get('kind') == 'choice':
        require(isinstance(options, list) and options and all(isinstance(item, str) for item in options),
                'The original dropdown options are unavailable.')
        if text not in options or text == 'Choose an item.':
            blockers.append('not_an_original_option')
    if cited and narrative is not None:
        # The narrative contract: the same deterministic support generation applied (`wm_narrative.support`), over
        # every cited sentence and labelled line, and the model's qualifiers for an answer it pre-filled.
        from . import wm_narrative
        verdict = wm_narrative.support(field, text, evidence, notes, narrative['labels'], labels)
        if verdict:
            blockers.append(NARRATIVE_BLOCKERS[verdict])
        qualifiers = answer.get('narrative')
        if answer.get('status') == 'supported' and isinstance(qualifiers, dict) and not wm_narrative.qualifiers_fit(field, qualifiers):
            blockers.append('narrative_qualifiers_hold')
    elif not values or not all(value['labelled'] and value['value'] == text for value in values):
        blockers.append('exact_labelled_source_required')
    if field.get('kind') == 'measurement':
        unit = field.get('locator', {}).get('unit')
        require(unit in ('mm', 'ms'), 'Unsupported measurement unit.')
        if not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\s+' + re.escape(unit), text):
            blockers.append('documented_numeric_value_and_unit_required')
    return {'key': field['key'], 'text': text, 'status': 'conflict' if blockers else
            'edited' if answer.get('status') == 'edited' else 'supported',
            'evidence': evidence, 'reviewed': _reviewed(answer, actor, revision), 'blockers': blockers}


def _variants(requirement):
    variants = requirement.get('variants')
    require(isinstance(variants, list) and variants and all(isinstance(row, dict)
            and isinstance(row.get('id'), str) and row['id'] for row in variants),
            'The immutable statement alternatives are unavailable.')
    result = {row['id']: row for row in variants}
    require(len(result) == len(variants) and requirement.get('default_variant') in result,
            'Invalid versioned statement alternatives.')
    return result


def _normalize_decisions(requirements, decisions):
    require(type(decisions) is dict and set(decisions) <= {row['key'] for row in requirements},
            'Unknown preprinted assertion decisions were supplied.')
    result = {}
    for requirement in requirements:
        item = decisions.get(requirement['key'], {})
        require(type(item) is dict and set(item) <= {'reviewed', 'evidence', 'variant'},
                'Assertion decisions accept only the approved alternative, explicit review and source evidence.')
        require(type(item.get('reviewed', False)) is bool, 'Review confirmation must be explicit.')
        variant = item.get('variant', requirement.get('default_variant'))
        require(variant in _variants(requirement), 'Choose an original approved statement alternative.')
        result[requirement['key']] = {'reviewed': item.get('reviewed', False),
                                      'evidence': deepcopy(item.get('evidence', [])), 'variant': variant}
    return result


def _variant_text(variant, answers, actor):
    template = variant.get('text_template')
    require(isinstance(template, str) and len(template) <= 20000,
            'The approved statement text template is unavailable.')
    def substitute(match):
        token = match.group(1)
        if token == 'signer_name':
            return _space(actor.get_full_name()) or actor.email
        if token in ('right_reflux_connector', 'left_reflux_connector'):
            key = 'sdt_-213273323' if token.startswith('right') else 'sdt_605543147'
            require(key in answers, 'The statement connector has no mapped answer.')
            return ' ' if answers[key]['text'] == 'is absent.' else ' is '
        if token in ('right_treatment_connector', 'left_treatment_connector'):
            key = 'sdt_1706206184' if token.startswith('right') else 'sdt_-1268837810'
            require(key in answers, 'The treatment connector has no mapped answer.')
            return '' if answers[key]['text'].startswith(',') else ' '
        require(token.startswith('sdt_') and token in answers,
                'The statement uses an unknown replacement token.')
        return answers[token]['text'] or 'Choose an item.'
    result = re.sub(r'\{([^{}]+)\}', substitute, template)
    # Unmatched braces are not a supported template language.
    require(not re.search(r'[{}]', re.sub(r'\{[^{}]+\}', '', template)),
            'Malformed approved statement replacement token.')
    return result


def _resolved_requirements(requirements, answers, resolved, decisions, actor):
    require(isinstance(resolved, list) and len(resolved) == len(requirements)
            and all(isinstance(row, dict) and isinstance(row.get('key'), str) for row in resolved),
            'Resolve the current answers through the isolated Word adapter before reviewing assertions.')
    by_key = {row['key']: row for row in resolved}
    require(len(by_key) == len(resolved) and set(by_key) == {row['key'] for row in requirements},
            'Resolved assertion population differs from the immutable mapping.')
    result = []
    for original in requirements:
        row = by_key[original['key']]
        require(all(row.get(key) == original.get(key) for key in
                    ('kind', 'label', 'body_paragraph', 'control_keys', 'variants', 'default_variant')),
                'Resolved assertion anchors differ from the immutable mapping.')
        require(isinstance(row.get('text'), str)
                and row.get('text_sha256') == hashlib.sha256(row['text'].encode()).hexdigest(),
                'Resolved assertion text does not match its hash.')
        require(row.get('original_text') == original['text']
                and row.get('original_text_sha256') == original['text_sha256'],
                'Resolved statement does not identify its immutable original.')
        variant = row.get('selected_variant')
        require(variant == decisions[original['key']]['variant'] and variant in _variants(original),
                'The resolved statement differs from the explicitly selected alternative.')
        selected = _variants(original)[variant]
        for key in ('required_control_keys', 'empty_control_keys'):
            require(isinstance(selected.get(key), list) and all(name in answers for name in selected[key]),
                    'Invalid statement alternative control requirements.')
        require(row['text'] == _variant_text(selected, answers, actor),
                'Resolved assertion differs from the approved statement and trusted current answers.')
        result.append({**original, 'resolved_text': row['text'], 'resolved_text_sha256': row['text_sha256'],
                       'selected_variant': variant, 'selected_rule': selected})
    return result


def narrative_reading(encounter, fields, requirements):
    """What the narrative review reads, or None when the contract is off (narrative evidence is then refused)."""
    from . import wm_narrative
    if not wm_narrative.enabled(fields):
        return None
    from .generation import recognized_labels
    context_labels = [row['label'] for row in requirements]
    return {'fields': fields, 'context_labels': context_labels, 'labels': recognized_labels(fields, context_labels)}


def _answer_assessment(encounter, actor, fields, requirements):
    labels = [row['label'] for row in fields + requirements]
    require(isinstance(encounter.answers, dict) and set(encounter.answers) <= {row['key'] for row in fields},
            'Answers contain unknown mapping keys.')
    narrative = narrative_reading(encounter, fields, requirements)
    return {field['key']: _field_decision(encounter.notes, field,
            encounter.answers.get(field['key'], {}), actor, labels, encounter.revision, narrative) for field in fields}


def sdk_answers(encounter, actor):
    """Parent-authored answer DTO for resolve; this does not authorize export."""
    require(getattr(actor, 'is_authenticated', False), 'Sign in to inspect the current document.')
    membership(actor, encounter.department)
    binding(encounter)
    fields, requirements = _mapping(encounter)
    assessed = _answer_assessment(encounter, actor, fields, requirements)
    return {key: {'text': row['text'], 'status': 'supported' if row['text'] else 'missing',
                  'reviewed_by': str(actor.pk) if row['reviewed'] else '',
                  'revision': encounter.revision, 'evidence': deepcopy(row['evidence'])}
            for key, row in assessed.items()}


def evaluate_review(encounter, actor, decisions, *, resolved_requirements=None):
    """Compute every decision from immutable metadata and actual source data.

    Callers may save incomplete reviews. Only validate_for_finalize permits
    export, and it recomputes this result from the stored bounded decisions.
    """
    _authorize(encounter, actor)
    fields, requirements = _mapping(encounter)
    decisions = _normalize_decisions(requirements, decisions)
    labels = [row['label'] for row in fields + requirements]
    answers = _answer_assessment(encounter, actor, fields, requirements)
    narrative = narrative_reading(encounter, fields, requirements)
    requirements = _resolved_requirements(requirements, answers, resolved_requirements, decisions, actor)
    assertions = {}
    signer_name = _space(actor.get_full_name()) or actor.email
    require(isinstance(signer_name, str) and 0 < len(signer_name) <= 500,
            'The actual clinician account needs a display name.')
    for requirement in requirements:
        key, decision = requirement['key'], decisions[requirement['key']]
        kind = requirement.get('kind', 'assertion')
        require(kind in ('assertion', 'identity', 'signature'), 'Unsupported fixed requirement kind.')
        require(isinstance(requirement.get('text'), str)
                and requirement.get('text_sha256') == hashlib.sha256(requirement['text'].encode()).hexdigest(),
                'The fixed requirement text differs from its versioned hash.')
        labelled, cited = _split_evidence(decision['evidence'])
        evidence, values, conflict = validate_evidence(encounter.notes, requirement['label'], labelled, labels)
        blockers = []
        if cited:
            if narrative is None:
                blockers.append('narrative_evidence_disabled')
            else:
                evidence = evidence + _statement_evidence(encounter, narrative, requirement, cited, answers, blockers)
        if not decision['reviewed']:
            blockers.append('clinician_review_required')
        if conflict or INJECTION.search(encounter.notes):
            blockers.append('conflicting_source' if conflict else 'instruction_like_source')
        statement = requirement['resolved_text']
        if any(not answers[key]['text'] for key in requirement['selected_rule']['required_control_keys']):
            blockers.append('missing_dependent_choice')
        if any(answers[key]['text'] for key in requirement['selected_rule']['empty_control_keys']):
            blockers.append('statement_alternative_requires_empty_choices')
        if kind == 'assertion':
            if 'Choose an item.' in statement:
                blockers.append('missing_dependent_choice')
            elif cited and narrative is not None:
                if values and not all(value['labelled'] and _space(value['value']) == _space(statement) for value in values):
                    blockers.append('complete_assertion_source_required')
            elif not values or not all(value['labelled'] and _space(value['value']) == _space(statement)
                                       for value in values):
                blockers.append('complete_assertion_source_required')
        elif kind == 'identity':
            paragraph = requirement.get('body_paragraph')
            require(paragraph in (11, 46), 'The original fixed identity mapping is unavailable.')
            identity = statement.removeprefix('INTERPRETING PHYSICIAN: ') if paragraph == 11 else statement
            if identity != signer_name:
                blockers.append('preprinted_identity_differs_from_actual_clinician')
            if evidence:
                blockers.append('identity_must_come_from_authenticated_clinician')
        elif evidence:
            blockers.append('signature_time_must_come_from_finalization')
        for rule in requirement.get('conflicts_with', []):
            require(type(rule) is dict and set(rule) == {'field_key', 'values'}
                    and rule['field_key'] in answers and isinstance(rule['values'], list),
                    'Invalid deterministic contradiction rule.')
            if answers[rule['field_key']]['text'] in rule['values']:
                blockers.append('selected_answer_conflicts_with_fixed_assertion')
        # These are exact known WM controls, not NLP or clinical inference.
        reflux_key = {'claim_32': 'sdt_-213273323', 'claim_36': 'sdt_605543147'}.get(key)
        if reflux_key and requirement['selected_variant'] == 'negative' and answers.get(reflux_key, {}).get('text') == 'reflux positive.':
            blockers.append('selected_answer_conflicts_with_fixed_assertion')
        assertions[key] = {'key': key, 'kind': kind, 'statement': statement,
                           'status': 'conflict' if blockers else 'supported', 'evidence': evidence,
                           'reviewed': decision['reviewed'], 'variant': requirement['selected_variant'],
                           'blockers': blockers}
    asymptomatic = answers.get('sdt_2005853103', {}).get('text') == 'Asymptomatic'
    if asymptomatic:
        symptom_keys = ('sdt_-1124008635', 'sdt_269290727', 'sdt_722175654', 'sdt_-49312682')
        for key in symptom_keys:
            if answers.get(key, {}).get('text'):
                answers[key]['blockers'].append('symptom_conflicts_with_asymptomatic')
                answers[key]['status'] = 'conflict'
                answers['sdt_2005853103']['blockers'].append('asymptomatic_conflicts_with_documented_symptom')
                answers['sdt_2005853103']['status'] = 'conflict'
    blockers = [{'kind': kind, 'key': key, 'reason': reason}
                for kind, rows in [('answer', answers), ('assertion', assertions)]
                for key, row in rows.items() for reason in row['blockers']]
    return {'answers': answers, 'assertions': assertions, 'blockers': blockers,
            'complete': not blockers, 'decisions': decisions}


def _statement_evidence(encounter, narrative, requirement, cited, answers, blockers):
    """A statement's narrative evidence: source sentences (a fixed wording needs one that names its side), and at most
    one `answers` entry naming exactly the answers the selected wording rests on (`wm_narrative.basis_keys`): its own
    answers, each complete without a blocker, or for a `not_documented` wording the answers whose absence it states,
    each reviewed and empty."""
    from . import wm_narrative
    units = [item for item in cited if item.get('kind') == 'unit']
    basis = [item for item in cited if item.get('kind') == 'answers']
    rule = requirement['selected_rule']
    required = list(rule['required_control_keys'])
    result = wm_narrative.unit_entries(encounter.notes, narrative['fields'], narrative['context_labels'], units)
    require(len(basis) <= 1 and all(set(item) == {'kind', 'answer_keys'} and isinstance(item['answer_keys'], list)
                                    for item in basis), 'Statement evidence names its answers once.')
    rests = wm_narrative.basis_keys(rule)
    absent = wm_narrative.rests_on_absence(rule)
    if basis:
        if not rests or basis[0]['answer_keys'] != rests:
            blockers.append('statement_answers_differ_from_wording')
        elif absent and any(answers[key]['blockers'] or answers[key]['text'] for key in rests):
            blockers.append('statement_absence_not_reviewed')
        elif not absent and any(answers[key]['blockers'] or not answers[key]['text'] for key in rests):
            blockers.append('statement_answers_incomplete')
        result.append({'kind': 'answers', 'answer_keys': list(basis[0]['answer_keys'])})
    if not units and not (basis and rests):
        blockers.append('complete_assertion_source_required')
    elif required and not wm_narrative.built_from_answers(rule) and not units:
        blockers.append('complete_assertion_source_required')
    if not required and units and not wm_narrative.names_side(requirement, result, encounter.notes):
        blockers.append('side_not_supported')
    sentences = [item for item in result if item.get('kind') == 'unit']
    if not basis and wm_narrative.rests_on_titles(requirement, sentences):
        blockers.append('statement_source_is_heading')
    if sentences:
        # The clinician chose these sentences: only the installed denial and reframing vocabulary refuses them here.
        read = wm_narrative.stored_reading(encounter.notes, narrative['fields'], narrative['context_labels'], encounter.answers)
        if wm_narrative.statement_blocked(requirement, sentences, read) is not None:
            blockers.append('governed_source')
    return result


def build_review(encounter, actor, decisions, *, resolved_requirements=None):
    assessment = evaluate_review(encounter, actor, decisions, resolved_requirements=resolved_requirements)
    return {'schema': 1, 'binding': binding(encounter), 'reviewer_id': str(actor.pk),
            'reviewed_at': timezone.now().isoformat(), 'decisions': assessment['decisions'],
            'assessment': assessment}


def invalidate_review(encounter):
    """Call on source/voice/answer edits; stale receipts also fail on recheck."""
    encounter.template_review = {}


def validate_for_finalize(encounter, actor, *, resolved_requirements=None):
    _authorize(encounter, actor)
    receipt = encounter.template_review
    require(type(receipt) is dict and set(receipt) ==
            {'schema', 'binding', 'reviewer_id', 'reviewed_at', 'decisions', 'assessment'}
            and receipt['schema'] == 1, 'Complete the versioned clinical review before finalizing.')
    require(receipt['binding'] == binding(encounter),
            'Source, answers, original or mapping changed. Repeat the clinical review.')
    require(receipt['reviewer_id'] == str(actor.pk), 'The finalizing clinician must personally review this version.')
    assessment = evaluate_review(encounter, actor, receipt['decisions'], resolved_requirements=resolved_requirements)
    require(assessment == receipt['assessment'], 'The saved clinical review no longer matches its evidence.')
    require(assessment['complete'], 'Resolve every blocked answer and preprinted assertion before finalizing.')
    name = _space(actor.get_full_name()) or actor.email
    answers = {}
    for key, row in assessment['answers'].items():
        text = row['text']
        answers[key] = {'text': text, 'status': 'supported' if text else 'missing',
                        'reviewed_by': str(actor.pk), 'revision': encounter.revision,
                        'evidence': deepcopy(row['evidence'])}
    return {'answers': answers,
            'reviewed_requirements': {key: {'text_sha256': hashlib.sha256(row['statement'].encode()).hexdigest(),
                                            'reviewed_by': str(actor.pk), 'revision': encounter.revision,
                                            'evidence': deepcopy(row['evidence'])}
                                      for key, row in assessment['assertions'].items()},
            'review_binding': binding(encounter),
            'claim_variants': {key: row['variant'] for key, row in assessment['assertions'].items()},
            'trusted_context': {'reviewer_id': str(actor.pk), 'revision': encounter.revision,
                                'notes': encounter.notes, 'signer_name': name,
                                'finalized_at': timezone.now().isoformat()}}
