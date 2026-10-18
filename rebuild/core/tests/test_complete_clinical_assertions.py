"""Prospective assertion boundaries; no retained clinical documents or providers."""
from copy import deepcopy

from django.test import SimpleTestCase

from core import generation, semantic_generation as semantic
from core.clinical_assertions import calendar_mask
from core.tests.test_semantic_generation import fact


class CompleteClinicalAssertionTests(SimpleTestCase):
    profile = semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT
    patient = 'Synthetic Ada Tern'
    header = 'Patient: Synthetic Ada Tern\nDate of service: 21 October 2027\nTreating clinician: Dr. Mira Cole\n'

    def validate(self, body, selected, *, section='History', profile=None):
        notes = self.header + section + '\n' + body
        fields = []
        units, _ = generation.source_units(notes, fields)
        values = []
        for index, (quote, kind, polarity, timing) in enumerate(selected):
            value = fact(notes, fields, str(index), quote, kind=kind,
                polarity=polarity, timing=timing, name_quote=self.patient)
            named = value['subject']['name_span']
            value['source_unit_ids'].append(next(u['id'] for u in units
                if u['start'] <= named['start'] < named['end'] <= u['end']))
            value['source_unit_ids'] = sorted(set(value['source_unit_ids']))
            values.append(value)
        original = deepcopy(values)
        validated = semantic.validate_facts(notes, units, {'facts': values},
            scope_contract=profile or self.profile,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
        self.assertEqual(values, original)
        for value in validated.values():
            for span in value['evidence']:
                self.assertEqual(notes[span['start']:span['end']], span['quote'])
        return list(validated.values())

    def assert_supported(self, values):
        self.assertTrue(values)
        self.assertTrue(all(not value['issues'] for value in values), [v['issues'] for v in values])

    def assert_held(self, values):
        self.assertTrue(values)
        self.assertTrue(all(value['issues'] for value in values))

    def test_scheduled_safety_net_does_not_reframe_unrelated_facts(self):
        finding = 'He reports mild wrist pain'
        follow = 'Follow-up is planned in two months to review results and symptoms, with earlier contact if symptoms persist'
        selected = [(finding, 'finding', 'affirmed', 'current'),
            (follow, 'follow_up', 'affirmed', 'future'), ('in two months', 'follow_up', 'affirmed', 'future')]
        self.assert_supported(self.validate(finding + '.\nPlan\n' + follow + '.', selected))
        self.assert_held(self.validate(finding + '.\nPlan\n' + follow + '.', selected,
            profile=semantic.SCOPED_DENIAL_SCOPE_CONTRACT))

    def test_unknown_safety_net_tail_and_foreign_or_past_scope_remain_held(self):
        follow = 'Follow-up is planned in two months to review results and symptoms, with earlier contact if symptoms persist'
        for suffix in (' unless otherwise advised', ' for another patient', ' but this is unverified',
                ' and a diagnosis is confirmed'):
            with self.subTest(suffix=suffix):
                self.assert_held(self.validate(follow + suffix + '.',
                    [(follow, 'follow_up', 'affirmed', 'future')], section='Plan'))
        for heading in ('Mother\nPlan', 'Previous visit\nPlan'):
            self.assert_held(self.validate(follow + '.', [(follow, 'follow_up', 'affirmed', 'future')], section=heading))

    def test_real_retraction_after_complete_followup_still_governs(self):
        finding = 'He reports mild wrist pain'
        follow = 'Follow-up is planned in two months to review symptoms, with earlier contact if symptoms persist'
        self.assert_held(self.validate(finding + '.\nPlan\n' + follow + '.\nThe above note is not this patient\'s record.',
            [(finding, 'finding', 'affirmed', 'current')]))

    def test_dates_mask_only_valid_complete_calendar_expressions(self):
        for date in ('8 May 2027', 'May 8, 2027', '2027-05-08'):
            self.assertNotEqual(calendar_mask(date), date)
        for text in ('May', '8 May', '32 May 2027', '29 February 2027', '8 Maybe 2027', '8 May 2027/2028'):
            self.assertEqual(calendar_mask(text), text)
        self.assertIn('may persist', calendar_mask('On 8 May 2027 symptoms may persist'))

    def test_calendar_month_is_not_modal_but_actual_modal_is(self):
        prior = 'He previously saw this same clinician, Dr. Mira Cole, in this same office on 8 May 2027 for follow-up of an earlier cough'
        self.assert_supported(self.validate(prior + '.', [(prior, 'history', 'affirmed', 'past')]))
        self.assert_held(self.validate(prior + '.', [(prior, 'history', 'affirmed', 'past')],
            profile=semantic.SCOPED_DENIAL_SCOPE_CONTRACT))
        changed = prior + ' and may have another episode'
        self.assert_held(self.validate(changed + '.', [(changed, 'history', 'affirmed', 'past')]))
        self.assert_held(self.validate(prior + '.', [(prior, 'history', 'affirmed', 'past')], section='Mother\nHistory'))

    def test_each_historical_negative_keeps_its_own_entire_predicate(self):
        report = 'She reports no previous diagnosis of inflammatory bowel disease and no prior pelvic surgery'
        selected = [('no previous diagnosis of inflammatory bowel disease', 'history', 'negated', 'past'),
            ('no prior pelvic surgery', 'history', 'negated', 'past')]
        self.assert_supported(self.validate(report + '.', selected))
        for quote in ('bowel disease', 'pelvic surgery', 'no prior pelvic'):
            self.assert_held(self.validate(report + '.', [(quote, 'history', 'negated', 'past')]))

    def test_unknown_or_nested_history_is_not_a_complete_repeated_negative(self):
        for report, quote in (
            ('She reports no previous diagnosis of inflammatory bowel disease and has fever', 'no previous diagnosis of inflammatory bowel disease'),
            ('She reports no prior pelvic surgery except a recent operation', 'no prior pelvic surgery'),
            ('She does not report no prior pelvic surgery', 'no prior pelvic surgery'),
            ('She never reports no prior pelvic surgery', 'no prior pelvic surgery'),
            ('She reports no prior pelvic surgery and no current cough', 'no prior pelvic surgery')):
            with self.subTest(report=report):
                self.assert_held(self.validate(report + '.', [(quote, 'history', 'negated', 'past')]))

    def test_current_medication_nonuse_keeps_same_subject_and_named_trial(self):
        prior = 'She previously tried magnesium citrate 150 mg, one tablet daily from 2 October through 7 October 2027.'
        stopped = 'She stopped it on 7 October because it was not helping and is no longer taking magnesium citrate'
        value = 'is no longer taking magnesium citrate'
        selected = [(value, 'history', 'negated', 'current')]
        self.assert_supported(self.validate(prior + ' It provided little benefit. ' + stopped + '.', selected))
        for changed in (prior.replace('magnesium citrate', 'sodium bicarbonate'),
                prior + ' An unfamiliar event occurred.', prior + '\nMother\n'):
            self.assert_held(self.validate(changed + ' ' + stopped + '.', selected))
        for tail in (' occasionally', ' unless symptoms recur', ' tomorrow'):
            self.assert_held(self.validate(prior + ' ' + stopped + tail + '.', selected))

    def test_current_nonuse_assignment_covers_its_current_predicate_and_keeps_bad_antecedents_held(self):
        from documents.semantic_preparation_roles import default_definitions
        from core.tests.test_semantic_generation import assignments
        prior = 'She previously tried magnesium citrate 150 mg, one tablet daily from 2 October through 7 October 2027'
        stopped = 'She stopped it on 7 October because it was not helping and is no longer taking magnesium citrate'
        value = 'is no longer taking magnesium citrate'
        fields = [{'key':'m','kind':'text','label':'Current medications and documented current medication non-use.',
                   'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        definitions['m'].update(version=2, answer_mode='narrative')
        definitions['m']['scope'].update(temporality='current', polarity='any')
        for suffix in ('', ', but this report was withdrawn', ', but the medication name is uncertain',
                       ', although this was actually sodium bicarbonate', ', for another patient'):
            body = prior + suffix + '. ' + stopped + '.'
            notes = self.header + 'History\n' + body
            facts = self.validate(body, [(value,'history','negated','current')])
            answers = semantic._assign(notes,fields,definitions,{f['id']:f for f in facts},
                assignments(fields,{'m':['0']}), scope_contract=self.profile,
                timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
            with self.subTest(suffix=suffix):
                if not suffix:
                    self.assertEqual(answers['m']['status'],'supported',answers['m']['review_reasons'])
                    self.assertEqual(answers['m']['text'],'Is no longer taking magnesium citrate')
                else:
                    self.assertNotEqual(answers['m']['status'],'supported')
                    self.assertTrue(facts[0]['issues'])

    def test_diagnostic_limit_needs_current_assessed_antecedent(self):
        assessed = 'Chest discomfort and mild wrist pain were both assessed today.'
        limit = 'Their cause has not been established'
        self.assert_supported(self.validate(assessed + ' ' + limit + '.',
            [(limit, 'assessment', 'negated', 'current')], section='Assessment'))
        for prior in ('A different assertion was recorded.', 'Mother and father were both assessed today.',
                'Chest discomfort and mild wrist pain were both assessed yesterday.'):
            self.assert_held(self.validate(prior + ' ' + limit + '.',
                [(limit, 'assessment', 'negated', 'current')], section='Assessment'))

    def test_possible_explanations_cannot_be_affirmed_or_clipped(self):
        statement = 'Muscular irritation and activity-related causes are possible explanations; neither is a confirmed diagnosis'
        self.assert_supported(self.validate(statement + '.', [(statement, 'assessment', 'uncertain', 'current')], section='Assessment'))
        self.assert_held(self.validate(statement + '.', [(statement, 'assessment', 'affirmed', 'current')], section='Assessment'))
        self.assert_held(self.validate(statement + '.', [('Muscular irritation', 'assessment', 'uncertain', 'current')], section='Assessment'))
        self.assert_held(self.validate(statement + ' unless a later test confirms one.',
            [(statement, 'assessment', 'uncertain', 'current')], section='Assessment'))

    def test_time_qualification_preserves_one_adjacent_same_day_clinician_total(self):
        total = ('Dr. Cole personally spent 23 minutes on 21 October 2027: three minutes reviewing records, '
            '15 minutes obtaining the history and examining the patient, and five minutes documenting the visit.')
        exclusion = 'The 23 minutes exclude four minutes of staff intake work and six minutes of physician record review performed on the preceding day'
        qualifier = 'These activities were all performed by the physician on the encounter date.'
        basis = 'Office E/M selection is based on total physician time on the date of service.'
        body = ' '.join((basis,total,qualifier,exclusion+'.','The total also excludes any time for separately reported services.'))
        selected = [(exclusion, 'other', 'affirmed', 'unspecified')]
        self.assert_supported(self.validate(body, selected, section='Plan'))
        for changed in (body.replace('Dr. Cole personally', 'Dr. Vale personally'),
                body.replace('23 minutes on 21 October 2027', '23 minutes on 20 October 2027'),
                body.replace(qualifier, 'An unrelated clinical event was recorded.'),
                body.replace(qualifier, 'The time activities may belong to another clinician.'),
                body.replace('The 23 minutes exclude', 'The 24 minutes exclude')):
            with self.subTest(changed=changed):
                quote = exclusion.replace('23 minutes', '24 minutes') if 'The 24 minutes' in changed else exclusion
                self.assert_held(self.validate(changed, [(quote,'other','affirmed','unspecified')], section='Plan'))

    def test_preservation_instruction_never_grants_restricted_topic_permission(self):
        definition = {'answer_mode':'narrative','value_type':'text','scope':
            {'subject':'patient','temporality':'any','polarity':'negative'},
            'meaning':'All documented symptom negatives (symptoms documented as absent), preserving the exact scope of recurrent cough rather than broadening it.'}
        objects = 'recurrent cough and fever'
        self.assertTrue(semantic._denial_destination(definition, objects, scope_contract=self.profile))
        self.assertFalse(semantic._denial_destination(definition, objects, scope_contract=semantic.SCOPED_DENIAL_SCOPE_CONTRACT))
        for suffix in (' Omit fever.', ' Except fever.', ' Only include cough.'):
            changed = {**definition,'meaning':definition['meaning']+suffix}
            self.assertFalse(semantic._denial_destination(changed,objects,scope_contract=self.profile))

