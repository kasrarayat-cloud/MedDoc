"""Generate synthetic WM fixtures from immutable SDK metadata; no provider calls.

No clinical values or completed documents are committed. The caller supplies an
actual isolated SDK resolver and may select a known test scenario.
"""
from copy import deepcopy


def build_fixture(inspected, resolve, *, scenario='positive', reviewer_id='synthetic-clinician',
                  signer_name='Synthetic Doctor', revision=7):
    fields = inspected['fields']
    answers = {}
    for field in fields:
        if field['kind'] == 'choice':
            value = field['options'][0]
            if field['label'] == 'Clinical indication: asymptomatic or itching':
                value = 'Itching'
            if scenario == 'positive' and field['label'].endswith('previous treatment: outcome'):
                value = ', however, there has been a recurrence.'
            if scenario == 'no_prior' and field['label'] == 'Clinical indication: history or skin changes':
                value = 'Skin changes or dermatitis'
            if field['label'].endswith('impression: reflux or absence'):
                value = 'reflux positive.' if scenario == 'positive' else 'is absent.'
        elif field['kind'] == 'measurement':
            value = ('700' if scenario == 'positive' and field['locator']['unit'] == 'ms' else '3.25') + ' ' + field['locator']['unit']
        else:
            value = {'date_of_service': '2026-09-17', 'date_of_birth': '1980-01-01',
                     'patient_name': 'Synthetic WM Test Patient', 'patient_id': 'SYNTHETIC-WM-001'}.get(field['key'], 'synthetic anatomical site '+field['key'])
        answers[field['key']] = {'text': value, 'status': 'supported', 'reviewed_by': reviewer_id,
                                  'revision': revision, 'evidence': []}
    variants = {r['key']: r['default_variant'] for r in inspected['review_requirements']}
    variants.update(claim_32='positive' if scenario == 'positive' else 'negative',
                    claim_36='positive' if scenario == 'positive' else 'negative')
    if scenario in ('no_prior', 'asymptomatic'):
        variants.update(claim_23='none', claim_27='none')
        for field in fields:
            if ' previous treatment: ' in field['label']:
                answers[field['key']].update(text='', status='missing')
    if scenario == 'asymptomatic':
        for field in fields:
            if field['label'].startswith('Clinical indication: '):
                if field['label'].endswith('asymptomatic or itching'):
                    answers[field['key']]['text'] = 'Asymptomatic'
                else:
                    answers[field['key']].update(text='', status='missing')
    if scenario == 'long':
        answers['patient_name']['text'] = 'Synthetic long answer ' + 'x' * 19800 + ' END'
    lines = [field['label'] + ': ' + answers[field['key']]['text'] for field in fields if answers[field['key']]['text']]
    context = {'reviewer_id': reviewer_id, 'revision': revision, 'notes': '\n'.join(lines),
               'signer_name': signer_name, 'finalized_at': '2026-09-17T12:34:56Z'}
    request = {'operation': 'resolve', 'mapping_digest': inspected['mapping_digest'], 'answers': answers,
               'claim_variants': variants, 'trusted_context': context}
    resolved = resolve(deepcopy(request))
    if resolved.get('conflicts'):
        raise ValueError('Synthetic scenario has unresolved SDK conflicts: '+repr(resolved['conflicts']))
    for requirement in resolved['review_requirements']:
        if requirement['kind'] == 'assertion':
            lines.append(requirement['label'] + ': ' + requirement['text'].strip())
    notes = '\n'.join(lines)
    context['notes'] = notes

    def evidence(line):
        start = notes.index(line)
        return [{'quote': line, 'start': start, 'end': start + len(line)}]

    for field in fields:
        answer = answers[field['key']]
        answer['evidence'] = evidence(field['label'] + ': ' + answer['text']) if answer['text'] else []
    request.update(operation='fill', reviewed_requirements={r['key']: {
        'text_sha256': r['text_sha256'], 'reviewed_by': reviewer_id, 'revision': revision,
        'evidence': evidence(r['label'] + ': ' + r['text'].strip()) if r['kind'] == 'assertion' else []}
        for r in resolved['review_requirements']})
    return request, resolved
