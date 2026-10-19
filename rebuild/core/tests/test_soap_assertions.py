"""Offline prospective syntax checks and preservation of genuine holds."""
from core import generation, semantic_generation as semantic
from core.clinical_source_context import source_context, time_blocks, SOAP_ASSERTION_PROFILE
from core.clinical_assertions_v4 import follow_up_frame, soap_heading
from core.tests import test_complete_clinical_assertions as legacy


class SoapAssertionTests(legacy.CompleteClinicalAssertionTests):
    profile = semantic.SOAP_ASSERTION_SCOPE_CONTRACT
    follow = ('Follow-up is planned in four weeks to review symptoms and the laboratory result, '
              'with earlier contact if symptoms worsen or visible blood appears in the stool')

    def test_compound_followup_does_not_hold_unrelated_fact(self):
        finding = 'He reports mild wrist pain'
        values = [(finding, 'finding', 'affirmed', 'current'),
                  (self.follow, 'follow_up', 'affirmed', 'future')]
        self.assert_supported(self.validate(finding + '.\nP\n' + self.follow + '.', values))
        self.assert_held(self.validate(finding + '.\nP\n' + self.follow + '.', values,
            profile=semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT))

    def test_followup_conditions_are_not_diagnoses_or_truncated(self):
        for tail in (' unless otherwise advised', ' but is not confirmed',
                     ' or the patient is diagnosed', ' for another patient',
                     ' or fever appears and the note is invalid'):
            with self.subTest(tail=tail):
                self.assertIsNone(follow_up_frame(self.follow + tail))
                self.assert_held(self.validate(self.follow + tail + '.',
                    [(self.follow, 'follow_up', 'affirmed', 'future')], section='P'))
        self.assert_held(self.validate(self.follow + '.',
            [('visible blood', 'finding', 'affirmed', 'current')], section='P'))

    def test_section_and_date_aliases_are_exact(self):
        for letter, expected in [('S','subjective'),('O','objective'),('A','assessment'),('P','plan')]:
            self.assertEqual(soap_heading(letter + ':'), expected)
        for text in ('s', 'P for another patient', 'A: possible disease', 'patient', 'S O A P'):
            self.assertIsNone(soap_heading(text))
        notes = self.header.replace('Date of service:', 'Service date:') + 'O\nHe appears comfortable.'
        units, _ = generation.source_units(notes, [])
        current = source_context(notes, units, profile=SOAP_ASSERTION_PROFILE)
        self.assertEqual(current['service_date'], '2027-10-21')
        self.assertEqual(current['units'][units[-1]['start']]['section'], 'objective')
        legacy = source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT))
        self.assertIsNone(legacy['service_date'])
        self.assertIsNone(legacy['units'][units[-1]['start']]['section'])

    def test_excluded_time_does_not_retract_symptom_duration(self):
        finding = 'He reports wrist pain lasting 12 minutes'
        tail = 'Time for any separately reported service is also excluded from the total.'
        self.assert_supported(self.validate(finding + '.\n' + tail,
            [(finding, 'finding', 'affirmed', 'current')]))

    def test_shared_subject_retraction_after_exclusion_still_holds(self):
        from core.clinical_source_context import _retracted_clause_domains
        for text in ('The total excludes staff time but is invalid.',
                     'The 33 minutes exclude staff time and are incorrect.',
                     'The documented time belongs to another patient.',
                     'The documented time is incorrect.'):
            with self.subTest(text=text):
                self.assertIn('time', _retracted_clause_domains(text, {'time'}, profile=SOAP_ASSERTION_PROFILE))

    def test_stopping_date_bounds_apply_to_the_whole_continuation(self):
        prior='She previously took cetirizine 10 mg by mouth each evening for itching from 2 October through 7 October 2027.'
        response='It gave no meaningful relief.'
        for date,valid in [('8 October',True),('7 October',True),('21 October',True),('6 October',False),('22 October',False)]:
            stopped='She stopped it on '+date+' because it was not helping and is no longer taking cetirizine'
            selected=[(stopped.split(' and ')[0],'history','affirmed','past'),
                ('is no longer taking cetirizine','history','negated','current')]
            values=self.validate(prior+' '+response+' '+stopped+'.',selected,section='S')
            if valid:self.assert_supported(values)
            else:self.assert_held(values)

    def test_complete_time_facts_cannot_escape_shared_subject_qualification(self):
        from core.tests.test_semantic_generation import fact
        basis = "Office E/M selection is based on the treating physician's total time on the service date"
        total = 'Dr. Cole personally spent 34 minutes on 21 October 2027: 30 minutes examining the patient and four minutes documenting'
        prefix = self.header + 'P\n' + basis + '. ' + total + '.\n'
        tails = ('but belongs to another patient', 'but refers to yesterday',
            'but is for a previous visit', 'but is not valid',
            'but its validity is unknown', 'and are incorrect',
            'and cannot be used', '; it is for another patient', ', is not valid')
        for suffix in tails:
            with self.subTest(suffix=suffix):
                notes = prefix + 'The total excludes staff time ' + suffix + '.'
                units, _ = generation.source_units(notes, [])
                raw = [fact(notes, [], str(i), quote, kind='other', subject='clinician')
                    for i, quote in enumerate((basis, total))]
                validated = semantic.validate_facts(notes, units, {'facts': raw},
                    scope_contract=self.profile)
                self.assert_held(list(validated.values()))
                context = source_context(notes, units, profile=SOAP_ASSERTION_PROFILE)
                self.assertTrue(all(not row['binding_valid'] for row in time_blocks(notes, units, context)))

    def test_historical_account_exemption_does_not_gain_new_profile_permissions(self):
        from core.clinical_source_context import _retracted_clause_domains, COMPLETE_ASSERTION_PROFILE
        text = 'Dr. Cole spent 33 minutes on 18 October 2026: reviewing the documented time.'
        self.assertEqual(_retracted_clause_domains(text, {'time'}, profile=COMPLETE_ASSERTION_PROFILE), {'time'})

    def test_assessment_clauses_keep_separate_polarities_and_full_qualifications(self):
        negative = 'The cause of the tingling is not established'
        uncertain = 'nerve compression is a possibility but is not diagnosed'
        body = negative + '; ' + uncertain
        choices = [(negative,'assessment','negated','current'),
                   (uncertain,'assessment','uncertain','current')]
        self.assert_supported(self.validate(body + '.',choices,section='A'))
        for quote,kind,polarity,timing in choices:
            self.assert_held(self.validate(body + '.',[(quote,kind,'affirmed',timing)],section='A'))
            for suffix in ('; an unfamiliar qualification applies',' but this is unverified',' for another patient'):
                self.assert_held(self.validate(body + suffix + '.',[(quote,kind,polarity,timing)],section='A'))
            for section in ('Mother\nA','Previous visit\nA','P'):
                self.assert_held(self.validate(body + '.',[(quote,kind,polarity,timing)],section=section))
        for quote in ('tingling','nerve compression',body):
            self.assert_held(self.validate(body + '.',[(quote,'assessment','negated','current')],section='A'))

    def test_diagnostic_attributes_do_not_negate_the_documented_condition(self):
        body = 'Tingling is documented without an established subtype or cause'
        self.assert_supported(self.validate(body+'.',[(body,'assessment','negated','current')],section='A'))
        self.assert_held(self.validate(body+'.',[('Tingling','assessment','negated','current')],section='A'))
        absent = 'Condition alpha, condition beta and condition gamma are not diagnosed today'
        self.assert_supported(self.validate(absent+'.',[(absent,'assessment','negated','current')],section='A'))
        self.assert_held(self.validate(absent+'.',[('Condition alpha','assessment','affirmed','current')],section='A'))

    def test_medication_response_and_cessation_require_same_immediate_trial(self):
        prior = 'She previously tried zelunor citrate 2.5 mg orally once daily for discomfort from 4 October through 9 October 2027.'
        response = 'It gave no meaningful relief'
        stopped = 'She stopped it on 9 October because it was not helping and is no longer taking zelunor citrate'
        current = 'is no longer taking zelunor citrate'
        body = prior + ' ' + response + '. ' + stopped + '.'
        self.assert_supported(self.validate(body,[(response,'history','negated','past'),
            (current,'history','negated','current')],section='S'))
        for prefix in ('', prior+' An unfamiliar event occurred.', prior+'\nMother\nS\n'):
            self.assert_held(self.validate(prefix+' '+response+'.',[(response,'history','negated','past')],section='S'))
        self.assert_held(self.validate(body,[(response,'history','negated','current')],section='S'))
        self.assert_held(self.validate(body,[(response,'history','affirmed','past')],section='S'))
        changed = body.replace('previously tried zelunor citrate','previously tried narulin citrate')
        self.assert_held(self.validate(changed,[(current,'history','negated','current')],section='S'))
        for dates in ('22 October 2027 through 29 October 2027',
                      '22 October through 9 October 2027',
                      '4 October through 9 October',
                      '4 October 2028 through 9 October 2028'):
            with self.subTest(dates=dates):
                changed = body.replace('4 October through 9 October 2027',dates)
                self.assert_held(self.validate(changed,[(response,'history','negated','past'),
                    (current,'history','negated','current')],section='S'))

    def test_time_block_keeps_date_and_actor_binding(self):
        basis = "Office E/M selection is based on the treating physician's total time on the service date."
        total = 'Dr. Cole personally spent 34 minutes on 21 October 2027: 30 minutes examining the patient and four minutes documenting.'
        exclusion = 'Time for any separately reported service is also excluded from the total.'
        notes = self.header.replace('Date of service:', 'Service date:') + 'P\n' + ' '.join((basis,total,exclusion))
        def blocks(source):
            units, _ = generation.source_units(source, [])
            context = source_context(source, units, profile=SOAP_ASSERTION_PROFILE)
            return time_blocks(source, units, context)
        self.assertTrue(all(row['binding_valid'] for row in blocks(notes)))
        self.assertEqual([row['kind'] for row in blocks(notes)], ['basis','total','exclusion'])
        for old,new in [('Dr. Cole personally', 'Dr. Quinn personally'),
                        ('34 minutes on 21 October', '34 minutes on 20 October')]:
            with self.subTest(new=new):
                changed = blocks(notes.replace(old,new))
                self.assertTrue(changed)
                self.assertTrue(all(not row['binding_valid'] for row in changed))
