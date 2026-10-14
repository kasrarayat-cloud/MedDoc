"""Regressions from independent refutation of the original finished v5 diff.

The protected report is pinned by SHA256
068271737697459e1214b76df39d75bda84f4d649bcad4c82091b71b751857ad.
Its inputs are reproduced here without reading private artifacts in the suite.
Every reply is a local fixture; a passing checker must not clear these holds.
Both reference schemas and stored-answer validation run for every case.
"""
from copy import deepcopy
from itertools import product

from django.test import SimpleTestCase

from core import generation
from core import semantic_generation as semantic
from core.tests import test_source_context_attribution as attribution
from core.tests import test_source_context_mixed_assessment as mixed
from core.tests.test_semantic_generation import fact, span


PATIENT = attribution.PATIENT
DOCTOR = attribution.DOCTOR
REFERRAL = attribution.REFERRAL
REFERENCES = attribution.REFERENCES


class SourceContextRefutationTests(SimpleTestCase):
    # Compose helpers rather than inheriting their independently discovered tests.
    prepare = attribution.SourceContextAttributionTests.prepare
    generate = attribution.SourceContextAttributionTests.generate
    run_inventory = attribution.SourceContextAttributionTests.run_inventory
    assert_held = attribution.SourceContextAttributionTests.assert_held

    def bound(self, notes, quote, reference, **kwargs):
        return self.generate(notes, quote, name=PATIENT, other_name=DOCTOR,
                             other_kind='identity', reference=reference, **kwargs)[0]

    def test_shared_comma_denials_cannot_become_positive_symptoms(self):
        cases = (
            ('The patient denies fever, cough and wheezing.', ('cough', 'wheezing')),
            ('The patient denies fever, nausea, vomiting and cough.',
             ('nausea', 'vomiting', 'cough')),
            ('The patient reports fever and denies cough, nausea and vomiting.',
             ('nausea', 'vomiting')),
        )
        for (statement, quotes), reference in product(cases, REFERENCES):
            for quote in quotes:
                with self.subTest(statement=statement, quote=quote, reference=reference):
                    answer = self.bound(REFERRAL + statement, quote, reference)
                    self.assert_held(answer)
                    clinical = next(f for f in answer['facts'] if f['id'] == 'clinical')
                    self.assertEqual(clinical['value_evidence']['quote'], quote)

    def test_other_person_mentions_preserve_previously_supported_explicit_patient_statements(self):
        patient_statement = 'The patient reports wheezing.'
        cases = (
            (patient_statement + ' ' + DOCTOR + ' reviewed the chart.', DOCTOR),
            (DOCTOR + ' reviewed the chart. ' + patient_statement, DOCTOR),
            (patient_statement + ' Synthetic Nolan Reed entered the room.', 'Synthetic Nolan Reed'),
        )
        for (notes, other), reference in product(cases, REFERENCES):
            with self.subTest(notes=notes, reference=reference):
                observed = []
                for scope in (semantic.FAMILY_SCOPE_CONTRACT, semantic.SOURCE_CONTEXT_SCOPE_CONTRACT):
                    answer, _, _, _ = self.generate(notes, 'wheezing', other_name=other,
                        other_kind='identity', profile=scope, reference=reference)
                    observed.append((answer['status'], answer['text']))
                    clinical = next(f for f in answer['facts'] if f['id'] == 'clinical')
                    self.assertIsNone(clinical['subject']['name_evidence'])
                    self.assertEqual(clinical['value_evidence']['quote'], 'wheezing')
                    self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'other_person')
                                     ['value_evidence']['quote'], other)
                self.assertEqual(observed, [('supported', 'Wheezing'), ('supported', 'Wheezing')])

    def test_complete_standalone_oral_coordination_preserves_both_polarities(self):
        notes = 'There was no scleral icterus and the oropharynx was clear.'
        for (quote, polarity), reference in product(
                (('no scleral icterus', 'negated'), ('oropharynx was clear', 'affirmed')), REFERENCES):
            with self.subTest(quote=quote, reference=reference):
                answer, _, _, _ = self.generate(notes, quote, polarity=polarity,
                    answer_mode='narrative', reference=reference)
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', quote[0].upper() + quote[1:]))
                self.assertEqual(answer['facts'][0]['polarity'], polarity)
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'], quote)

    def test_unextracted_unknown_person_blocks_new_oral_coordination_release(self):
        clinical_statement = 'There was no scleral icterus and the oropharynx was clear.'
        foreign_statement = 'Synthetic Nolan Reed entered the room.'
        for unknown_first, reference in product((True, False), REFERENCES):
            with self.subTest(unknown_first=unknown_first, reference=reference):
                first, second = ((foreign_statement, clinical_statement) if unknown_first
                                 else (clinical_statement, foreign_statement))
                answer, _, _, _ = self.generate(first + ' ' + second,
                    'oropharynx was clear', answer_mode='narrative', reference=reference)
                self.assert_held(answer)
                self.assertEqual([f['id'] for f in answer['facts']], ['clinical'])
                self.assertIsNone(answer['facts'][0]['subject']['name_evidence'])

    def test_later_unbound_referral_preserves_previously_supported_patient_statement(self):
        notes = ('The patient reports wheezing. Synthetic Nolan Reed was referred by '
                 + DOCTOR + '.')
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                observed = []
                for scope in (semantic.FAMILY_SCOPE_CONTRACT, semantic.SOURCE_CONTEXT_SCOPE_CONTRACT):
                    answer, _, _, _ = self.generate(notes, 'wheezing', other_name=DOCTOR,
                        other_kind='identity', profile=scope, reference=reference)
                    observed.append((answer['status'], answer['text']))
                    self.assertIsNone(next(f for f in answer['facts'] if f['id'] == 'clinical')
                                      ['subject']['name_evidence'])
                self.assertEqual(observed, [('supported', 'Wheezing'), ('supported', 'Wheezing')])

    def test_unbound_referral_cannot_release_new_source_scopes_before_or_after_it(self):
        referral = 'Synthetic Nolan Reed was referred by ' + DOCTOR + '.'
        clinical_cases = (
            ('The patient was in no acute distress.', 'in no acute distress', 'negated', 'finding'),
            ('The patient has never used tobacco.', 'never used tobacco', 'negated', 'history'),
            ('There was no scleral icterus and the oropharynx was clear.',
             'oropharynx was clear', 'affirmed', 'finding'),
            (mixed.PREFIX + mixed.MIXED + '.', mixed.MIXED, 'mixed', 'assessment'),
        )
        for case, referral_first, reference in product(clinical_cases, (True, False), REFERENCES):
            statement, quote, polarity, kind = case
            with self.subTest(quote=quote, referral_first=referral_first, reference=reference):
                first, second = (referral, statement) if referral_first else (statement, referral)
                answer, _, _, _ = self.generate(first + ' ' + second, quote,
                    polarity=polarity, kind=kind, answer_mode='narrative',
                    other_name=DOCTOR, other_kind='identity', reference=reference)
                self.assert_held(answer)
                self.assertEqual({f['id'] for f in answer['facts']}, {'clinical', 'other_person'})
                self.assertIsNone(next(f for f in answer['facts'] if f['id'] == 'clinical')
                                  ['subject']['name_evidence'])

    def test_complete_coordinated_denial_is_retained_literally(self):
        quote = 'denies fever, cough and wheezing'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer = self.bound(REFERRAL + 'The patient ' + quote + '.', quote,
                                    reference, polarity='negated', answer_mode='narrative')
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', 'Denies fever, cough and wheezing'))

    def test_non_prefix_cannot_be_clipped_to_an_affirmed_finding(self):
        for term, reference in product(('tender', 'distended'), REFERENCES):
            with self.subTest(term=term, reference=reference):
                answer = self.bound(REFERRAL + 'The abdomen was non-' + term + '.',
                                    term, reference)
                self.assert_held(answer)
                self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'clinical')
                                 ['value_evidence']['quote'], term)

    def test_referrer_identity_cannot_swallow_a_second_owner_clause(self):
        suffixes = (
            ', who attended as the patient himself',
            '; NOLAN REED entered the room',
            ', and another patient entered the room',
            ', who is the person being examined',
            ', WHO IS THE PERSON BEING EXAMINED',
            ', AND ANOTHER PATIENT ENTERED THE ROOM',
        )
        for suffix, swallow, reference in product(suffixes, (False, True), REFERENCES):
            with self.subTest(suffix=suffix, swallow=swallow, reference=reference):
                notes = (PATIENT + ' was referred by ' + DOCTOR + suffix
                         + '. Bowel sounds were normal.')
                other = DOCTOR + suffix if swallow else DOCTOR
                answer, _, _, _ = self.generate(notes, 'normal', name=PATIENT,
                    other_name=other, other_kind='identity', reference=reference)
                self.assert_held(answer)
                # The rejected identity remains visible, never silently shortened.
                retained = next(f for f in answer['facts'] if f['id'] == 'other_person')
                self.assertEqual(retained['value_evidence']['quote'], other)

    def test_mixed_peer_annotations_cannot_hide_a_conflicting_component(self):
        helper = mixed.SourceContextMixedAssessmentTests()
        phrase = 'current gastrointestinal symptoms'
        notes = mixed.PREFIX + mixed.MIXED + '. ' + mixed.PREFIX + phrase + '.'
        timings = ('current', 'unspecified', 'past', 'future')
        concepts = ('clinical impression', 'gastrointestinal symptoms',
                    'positive gastrointestinal symptom status')
        kinds = ('assessment', 'finding', 'history')
        for timing, concept, kind, selected, reference in product(
                timings, concepts, kinds, ('assessment', 'peer'), REFERENCES):
            with self.subTest(timing=timing, concept=concept, kind=kind,
                              selected=selected, reference=reference):
                prepared = helper.prepare(notes)
                prepared[3].append(fact(notes, prepared[1], 'peer', phrase, kind=kind,
                    concept=concept, timing=timing, occurrence=1))
                original = deepcopy(prepared[3])
                answer, _ = helper.generate(prepared, selected=(selected,), reference=reference)
                self.assert_held(answer)
                self.assertEqual(prepared[3], original)
                self.assertEqual({f['id'] for f in answer['facts']}, {'assessment', 'peer'})
                self.assertEqual(answer['fact_ids'], [selected])
                self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'assessment')
                                 ['value_evidence']['quote'], mixed.MIXED)

    def mixed_with_symptom_source(self, mixed_value, statement, *, mixed_first, referral):
        helper = mixed.SourceContextMixedAssessmentTests()
        assessment = mixed.PREFIX + mixed_value + '.'
        first, second = (assessment, statement) if mixed_first else (statement, assessment)
        notes = (REFERRAL if referral else '') + first + ' ' + second
        prepared = helper.prepare(notes, mixed_value)
        # This permits either patient or clinician peer metadata, so source
        # conflict controls cannot pass merely because of a destination mismatch.
        prepared[2]['impression']['scope']['subject'] = 'encounter'
        if referral:
            prepared[3].extend((
                fact(notes, prepared[1], 'identity', PATIENT, kind='identity',
                     name_quote=PATIENT, timing='unspecified'),
                fact(notes, prepared[1], 'other_person', DOCTOR, kind='identity',
                     subject='other', name_quote=DOCTOR, timing='unspecified'),
            ))
        return helper, prepared

    def test_positive_gi_source_conflicts_with_mixed_even_when_symptom_fact_is_omitted(self):
        for symptom, mixed_first, referral, reference in product(
                ('persistent vomiting', 'persistent abdominal pain'), (True, False), (True, False), REFERENCES):
            statement = 'The patient reports ' + symptom + '.'
            for inventory, selected in (('mixed_only', 'assessment'), ('both', 'assessment'),
                                        ('both', 'symptom'), ('symptom_only', 'symptom')):
                with self.subTest(symptom=symptom, mixed_first=mixed_first, referral=referral,
                                  reference=reference, inventory=inventory, selected=selected):
                    helper, prepared = self.mixed_with_symptom_source(mixed.MIXED, statement,
                        mixed_first=mixed_first, referral=referral)
                    if inventory != 'mixed_only':
                        prepared[3].append(fact(prepared[0], prepared[1], 'symptom', symptom,
                            kind='finding', concept='current gastrointestinal symptom'))
                    if inventory == 'symptom_only':
                        prepared[3][:] = [f for f in prepared[3] if f['id'] != 'assessment']
                    answer, _ = helper.generate(prepared, selected=(selected,), reference=reference)
                    self.assert_held(answer)
                    self.assertEqual(answer['fact_ids'], [selected])
                    self.assertEqual({f['id'] for f in answer['facts']}, {f['id'] for f in prepared[3]})

    def test_symptom_metadata_cannot_resolve_a_source_level_mixed_conflict(self):
        metadata = (
            {}, {'kind': 'history'}, {'kind': 'assessment'}, {'subject': 'clinician'},
            {'concept': 'unrelated model label'}, {'timing': 'unspecified'},
            {'timing': 'past'}, {'timing': 'future'},
            {'kind': 'other', 'subject': 'clinician', 'concept': 'unrelated model label', 'timing': 'future'},
        )
        for change, mixed_first, referral, selected, reference in product(
                metadata, (True, False), (True, False), ('assessment', 'symptom'), REFERENCES):
            with self.subTest(change=change, mixed_first=mixed_first, referral=referral,
                              selected=selected, reference=reference):
                helper, prepared = self.mixed_with_symptom_source(mixed.MIXED,
                    'The patient reports persistent vomiting.', mixed_first=mixed_first, referral=referral)
                attributes = {'kind': 'finding', 'subject': 'patient',
                              'concept': 'current gastrointestinal symptom', 'timing': 'current', **change}
                prepared[3].append(fact(prepared[0], prepared[1], 'symptom',
                    'persistent vomiting', **attributes))
                answer, _ = helper.generate(prepared, selected=(selected,), reference=reference)
                self.assert_held(answer)
                self.assertNotIn('The fact subject does not match the approved field scope.',
                                 answer['review_reasons'])

    def test_literal_whitespace_does_not_hide_source_level_gi_conflicts(self):
        for separator, words, mixed_first, referral, reference in product(
                (' ', '  ', '\t', '\u00a0'), (('abdominal', 'pain'), ('rectal', 'bleeding')),
                (True, False), (True, False), REFERENCES):
            symptom = separator.join(words)
            for inventory, selected in (('mixed_only', 'assessment'), ('both', 'assessment'),
                                        ('both', 'symptom'), ('symptom_only', 'symptom')):
                with self.subTest(separator=separator, symptom=symptom, mixed_first=mixed_first,
                                  referral=referral, reference=reference,
                                  inventory=inventory, selected=selected):
                    helper, prepared = self.mixed_with_symptom_source(mixed.MIXED,
                        'The patient reports ' + symptom + '.',
                        mixed_first=mixed_first, referral=referral)
                    if inventory != 'mixed_only':
                        prepared[3].append(fact(prepared[0], prepared[1], 'symptom', symptom,
                            kind='finding', concept='current gastrointestinal symptom'))
                    if inventory == 'symptom_only':
                        prepared[3][:] = [f for f in prepared[3] if f['id'] != 'assessment']
                    answer, _ = helper.generate(prepared, selected=(selected,), reference=reference)
                    self.assert_held(answer)
                    self.assertEqual(answer['fact_ids'], [selected])
                    if inventory != 'mixed_only':
                        self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'symptom')
                                         ['value_evidence']['quote'], symptom)

    def test_literal_whitespace_does_not_release_clipped_shared_denials(self):
        for separator, referral, reference in product((' ', '  ', '\t', '\u00a0'),
                                                       (True, False), REFERENCES):
            cases = (
                ('The patient denies fever, abdominal' + separator + 'pain and cough.',
                 ('abdominal' + separator + 'pain', 'cough')),
                ('The patient reports fever and' + separator + 'denies cough, nausea and vomiting.',
                 ('nausea', 'vomiting')),
            )
            for statement, quotes in cases:
                for quote in quotes:
                    with self.subTest(separator=separator, referral=referral, reference=reference,
                                      statement=statement, quote=quote):
                        answer, _, _, _ = self.generate((REFERRAL if referral else '') + statement,
                            quote, reference=reference, name=PATIENT if referral else None,
                            other_name=DOCTOR if referral else None, other_kind='identity')
                        self.assert_held(answer)
                        self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'clinical')
                                         ['value_evidence']['quote'], quote)

    def test_literal_whitespace_preserves_complete_denial_evidence(self):
        for separator, referral, reference in product((' ', '  ', '\t', '\u00a0'),
                                                       (True, False), REFERENCES):
            quote = 'denies cough, abdominal' + separator + 'pain and vomiting'
            notes = ((REFERRAL if referral else '') + 'The patient reports fever and'
                     + separator + quote + '.')
            with self.subTest(separator=separator, referral=referral, reference=reference):
                answer, _, _, _ = self.generate(notes, quote, reference=reference,
                    name=PATIENT if referral else None, other_name=DOCTOR if referral else None,
                    other_kind='identity', polarity='negated', answer_mode='narrative')
                self.assertEqual(answer['status'], 'supported')
                self.assertEqual(' '.join(answer['text'].split()),
                                 'Denies cough, abdominal pain and vomiting')
                self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'clinical')
                                 ['value_evidence']['quote'], quote)

    def test_mixed_symptom_domain_conflicts_do_not_absorb_unrelated_or_negative_findings(self):
        cases = (
            ('gastrointestinal', 'The patient reports cough.', 'cough', 'affirmed', False),
            ('gastrointestinal', 'The patient denies abdominal pain.', 'denies abdominal pain', 'negated', False),
            ('gastrointestinal', 'The patient reports normal bowel movements.', 'normal bowel movements', 'affirmed', False),
            ('', 'The patient reports cough.', 'cough', 'affirmed', True),
            ('respiratory', 'The patient reports cough.', 'cough', 'affirmed', True),
            ('respiratory', 'The patient reports wheezing.', 'wheezing', 'affirmed', True),
            ('respiratory', 'The patient reports abdominal pain.', 'abdominal pain', 'affirmed', False),
            ('cardiac', 'The patient reports chest pain.', 'chest pain', 'affirmed', True),
        )
        for case, mixed_first, referral, peer_present, reference in product(
                cases, (True, False), (True, False), (True, False), REFERENCES):
            domain, statement, quote, polarity, conflict = case
            value = ('no current ' + (domain + ' ' if domain else '')
                     + 'symptoms and a family history of colon polyps')
            with self.subTest(domain=domain, statement=statement, mixed_first=mixed_first,
                              referral=referral, peer_present=peer_present, reference=reference):
                helper, prepared = self.mixed_with_symptom_source(value, statement,
                    mixed_first=mixed_first, referral=referral)
                if peer_present:
                    prepared[3].append(fact(prepared[0], prepared[1], 'symptom', quote,
                        concept='separate reported symptom', polarity=polarity))
                answer, _ = helper.generate(prepared, reference=reference)
                if conflict:
                    self.assert_held(answer)
                else:
                    self.assertEqual((answer['status'], answer['text']),
                                     ('supported', value[0].upper() + value[1:]))
                self.assertEqual(answer['fact_ids'], ['assessment'])

    def test_omitted_competing_impression_still_holds_the_mixed_value(self):
        helper = mixed.SourceContextMixedAssessmentTests()
        competitors = (
            mixed.PREFIX + 'current gastrointestinal symptoms.',
            'My documented assessment is current gastrointestinal symptoms.',
            '\nAssessment: current gastrointestinal symptoms.',
        )
        complete = mixed.PREFIX + mixed.MIXED + '.'
        for competitor, mixed_first, reference in product(competitors, (True, False), REFERENCES):
            with self.subTest(competitor=competitor, mixed_first=mixed_first, reference=reference):
                first, second = (complete, competitor) if mixed_first else (competitor, complete)
                notes = first + ' ' + second
                prepared = helper.prepare(notes)
                self.assertEqual([f['id'] for f in prepared[3]], ['assessment'])
                answer, _ = helper.generate(prepared, reference=reference)
                self.assert_held(answer)
                self.assertEqual([f['id'] for f in answer['facts']], ['assessment'])
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'], mixed.MIXED)

    def test_clinician_peer_annotation_cannot_hide_the_source_competition(self):
        helper = mixed.SourceContextMixedAssessmentTests()
        phrase = 'current gastrointestinal symptoms'
        notes = mixed.PREFIX + mixed.MIXED + '. ' + mixed.PREFIX + phrase + '.'
        for selected, reference in product(('assessment', 'peer'), REFERENCES):
            with self.subTest(selected=selected, reference=reference):
                prepared = helper.prepare(notes)
                # Encounter scope admits either subject annotation, so a subject
                # mismatch cannot accidentally satisfy this source-competition test.
                prepared[2]['impression']['scope']['subject'] = 'encounter'
                prepared[3].append(fact(notes, prepared[1], 'peer', phrase, kind='assessment',
                    concept='clinical impression', subject='clinician', occurrence=1))
                answer, _ = helper.generate(prepared, selected=(selected,), reference=reference)
                self.assert_held(answer)
                self.assertEqual(answer['fact_ids'], [selected])
                self.assertEqual({f['id'] for f in answer['facts']}, {'assessment', 'peer'})
                self.assertNotIn('The fact subject does not match the approved field scope.',
                                 answer['review_reasons'])

    def test_recognized_modality_does_not_release_its_explicit_contradiction(self):
        for mode, reference in product(('telephone', 'telehealth'), REFERENCES):
            with self.subTest(mode=mode, reference=reference):
                notes = (REFERRAL + 'This was a ' + mode
                         + ' visit; no telephone or telehealth encounter occurred.')
                answer = self.bound(notes, mode, reference, kind='other')
                self.assert_held(answer)

    def test_standalone_remote_modality_cannot_contradict_its_own_denial(self):
        for mode, reference in product(('telephone', 'telehealth'), REFERENCES):
            with self.subTest(mode=mode, reference=reference):
                notes = ('This was a ' + mode
                         + ' visit; no telephone or telehealth encounter occurred.')
                answer, _, _, _ = self.generate(notes, mode, reference=reference, kind='other')
                self.assert_held(answer)

    def test_unfamiliar_omitted_competing_assessment_holds_mixed_in_either_order(self):
        competitors = (
            "However, the clinician's impression was current gastrointestinal symptoms.",
            "In addition, the clinician's impression was current gastrointestinal symptoms.",
            "The clinician's impression has changed to current gastrointestinal symptoms.",
        )
        complete = mixed.PREFIX + mixed.MIXED + '.'
        for competitor, mixed_first, referral, reference in product(
                competitors, (True, False), (True, False), REFERENCES):
            with self.subTest(competitor=competitor, mixed_first=mixed_first,
                              referral=referral, reference=reference):
                first, second = (complete, competitor) if mixed_first else (competitor, complete)
                notes = (REFERRAL if referral else '') + first + ' ' + second
                answer, _, _, _ = self.generate(notes, mixed.MIXED, reference=reference,
                    label='Impression', polarity='mixed', kind='assessment',
                    name=PATIENT if referral else None, other_name=DOCTOR if referral else None,
                    other_kind='identity')
                self.assert_held(answer)
                # No peer extraction or changed annotation supplies this hold.
                self.assertEqual({f['id'] for f in answer['facts']},
                                 {'identity', 'other_person', 'clinical'} if referral else {'clinical'})

    def test_in_person_modality_and_denied_remote_encounter_are_consistent(self):
        notes = REFERRAL + 'This was an in-person visit; no telephone or telehealth encounter occurred.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer = self.bound(notes, 'in-person', reference, kind='other')
                self.assertEqual((answer['status'], answer['text']), ('supported', 'In-person'))

    def test_complete_distress_negative_accepts_bound_named_and_null_name_facts(self):
        for speaker, null_name, reference in product((PATIENT, 'Rowan', 'The patient'), (False, True), REFERENCES):
            with self.subTest(speaker=speaker, null_name=null_name, reference=reference):
                notes = REFERRAL + speaker + ' was alert, oriented and in no acute distress.'
                fields, definitions, values, selected = self.prepare(notes, 'in no acute distress',
                    name=PATIENT, other_name=DOCTOR, other_kind='identity', polarity='negated')
                if null_name:
                    clinical = next(f for f in values if f['id'] == 'clinical')
                    clinical['subject']['name_span'] = None
                    clinical['source_unit_ids'] = [u['id'] for u in generation.source_units(notes, fields)[0]
                        if u['start'] <= clinical['value_span']['start']
                        < clinical['value_span']['end'] <= u['end']]
                answer = self.run_inventory(notes, fields, definitions, values, selected, reference)
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', 'In no acute distress'))
                clinical = next(f for f in answer['facts'] if f['id'] == 'clinical')
                self.assertEqual(clinical['subject']['name_evidence'] is None, null_name)
                self.assertEqual(clinical['polarity'], 'negated')

    def test_complete_social_negatives_accept_full_or_given_name_with_null_annotation(self):
        for speaker, reference in product((PATIENT, 'Rowan'), REFERENCES):
            notes = (REFERRAL + speaker + ' has never used tobacco, does not drink alcohol '
                     'and does not use recreational drugs.')
            for quote in ('never used tobacco', 'does not drink alcohol', 'does not use recreational drugs'):
                with self.subTest(speaker=speaker, quote=quote, reference=reference):
                    fields, definitions, values, selected = self.prepare(notes, quote,
                        name=PATIENT, other_name=DOCTOR, other_kind='identity', polarity='negated')
                    clinical = next(f for f in values if f['id'] == 'clinical')
                    clinical['subject']['name_span'] = None
                    clinical['source_unit_ids'] = [u['id'] for u in generation.source_units(notes, fields)[0]
                        if u['start'] <= clinical['value_span']['start']
                        < clinical['value_span']['end'] <= u['end']]
                    answer = self.run_inventory(notes, fields, definitions, values, selected, reference)
                    self.assertEqual((answer['status'], answer['text']),
                                     ('supported', quote[0].upper() + quote[1:]))
                    retained = next(f for f in answer['facts'] if f['id'] == 'clinical')
                    self.assertIsNone(retained['subject']['name_evidence'])
                    self.assertEqual(retained['polarity'], 'negated')

    def test_recognized_generic_multiunit_source_preserves_complete_negatives(self):
        notes = ('The patient currently feels well. '
                 'The patient was alert, oriented and in no acute distress. '
                 'The patient has never used tobacco and does not drink alcohol.')
        for quote, reference in product(
                ('in no acute distress', 'never used tobacco', 'does not drink alcohol'), REFERENCES):
            with self.subTest(quote=quote, reference=reference):
                answer, _, _, _ = self.generate(notes, quote, polarity='negated', reference=reference)
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', quote[0].upper() + quote[1:]))
                self.assertIsNone(answer['facts'][0]['subject']['name_evidence'])

    def test_complete_video_distress_negative_is_supported_generic_or_referral(self):
        for referral, reference in product((False, True), REFERENCES):
            with self.subTest(referral=referral, reference=reference):
                notes = ((REFERRAL if referral else '')
                         + 'On video, the patient was alert, oriented and in no acute distress.')
                answer, _, _, _ = self.generate(notes, 'in no acute distress',
                    polarity='negated', reference=reference, name=PATIENT if referral else None,
                    other_name=DOCTOR if referral else None, other_kind='identity')
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', 'In no acute distress'))
                self.assertEqual(next(f for f in answer['facts'] if f['id'] == 'clinical')
                                 ['value_evidence']['quote'], 'in no acute distress')

    def test_other_named_video_subject_does_not_supply_patient_distress_negative(self):
        for referral, null_name, reference in product((False, True), (False, True), REFERENCES):
            with self.subTest(referral=referral, null_name=null_name, reference=reference):
                notes = ((REFERRAL if referral else PATIENT + ' attended the clinic. ')
                         + 'On video, Synthetic Nolan Reed was alert, oriented and in no acute distress.')
                fields, definitions, values, selected = self.prepare(notes, 'in no acute distress',
                    polarity='negated', name=PATIENT, other_name=DOCTOR if referral else None,
                    other_kind='identity')
                if null_name:
                    clinical = next(f for f in values if f['id'] == 'clinical')
                    clinical['subject']['name_span'] = None
                    clinical['source_unit_ids'] = [u['id'] for u in generation.source_units(notes, fields)[0]
                        if u['start'] <= clinical['value_span']['start']
                        < clinical['value_span']['end'] <= u['end']]
                answer = self.run_inventory(notes, fields, definitions, values, selected, reference)
                self.assert_held(answer)

    def test_complete_chest_and_neck_nontender_findings_keep_the_literal_negative(self):
        for body, referral, reference in product(('chest', 'neck'), (False, True), REFERENCES):
            with self.subTest(body=body, referral=referral, reference=reference):
                notes = (REFERRAL if referral else '') + 'The ' + body + ' was non-tender.'
                answer, _, _, _ = self.generate(notes, 'non-tender', polarity='negated',
                    reference=reference, name=PATIENT if referral else None,
                    other_name=DOCTOR if referral else None, other_kind='identity')
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Non-tender'))
                clinical = next(f for f in answer['facts'] if f['id'] == 'clinical')
                self.assertEqual(clinical['value_evidence']['quote'], 'non-tender')
                self.assertEqual(clinical['polarity'], 'negated')

    def test_another_person_exam_cannot_supply_patient_chest_or_neck_negatives(self):
        for body, referral, null_name, reference in product(
                ('chest', 'neck'), (False, True), (False, True), REFERENCES):
            with self.subTest(body=body, referral=referral, null_name=null_name, reference=reference):
                notes = ((REFERRAL if referral else PATIENT + ' attended the clinic. ')
                         + 'Synthetic Nolan Reed was being examined. The ' + body + ' was non-tender.')
                fields, definitions, values, selected = self.prepare(notes, 'non-tender',
                    polarity='negated', name=PATIENT, other_name=DOCTOR if referral else None,
                    other_kind='identity')
                if null_name:
                    clinical = next(f for f in values if f['id'] == 'clinical')
                    clinical['subject']['name_span'] = None
                    clinical['source_unit_ids'] = [u['id'] for u in generation.source_units(notes, fields)[0]
                        if u['start'] <= clinical['value_span']['start']
                        < clinical['value_span']['end'] <= u['end']]
                answer = self.run_inventory(notes, fields, definitions, values, selected, reference)
                self.assert_held(answer)

    def test_recognized_unrelated_wellbeing_or_family_record_preserves_mixed(self):
        helper = mixed.SourceContextMixedAssessmentTests()
        companions = (
            ('The patient currently feels well.', 'currently feels well', 'history', 'current'),
            ("The patient's mother had colon polyps diagnosed at age 68.",
             'mother had colon polyps diagnosed at age 68', 'history', 'past'),
        )
        complete = mixed.PREFIX + mixed.MIXED + '.'
        for companion, mixed_first, reference in product(companions, (True, False), REFERENCES):
            statement, quote, kind, timing = companion
            with self.subTest(companion=statement, mixed_first=mixed_first, reference=reference):
                first, second = (complete, statement) if mixed_first else (statement, complete)
                notes = first + ' ' + second
                prepared = helper.prepare(notes)
                prepared[3].append(fact(notes, prepared[1], 'unrelated', quote,
                    kind=kind, concept='separate documented history', timing=timing))
                answer, _ = helper.generate(prepared, reference=reference)
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', mixed.MIXED.capitalize()))
                self.assertEqual(answer['fact_ids'], ['assessment'])
                self.assertEqual({f['id'] for f in answer['facts']}, {'assessment', 'unrelated'})

    def test_nonreferral_foreign_distress_finding_cannot_become_target_patient_fact(self):
        foreign = 'Synthetic Nolan Reed'
        notes = (PATIENT + ' attended the clinic. ' + foreign
                 + ' was alert, oriented and in no acute distress.')
        for annotation, reference in product((PATIENT, None, foreign), REFERENCES):
            with self.subTest(annotation=annotation, reference=reference):
                fields, definitions, values, selected = self.prepare(notes, 'in no acute distress',
                    name=PATIENT, polarity='negated')
                clinical = next(f for f in values if f['id'] == 'clinical')
                clinical['subject']['name_span'] = span(notes, annotation) if annotation else None
                if annotation != PATIENT:
                    clinical['source_unit_ids'] = [u['id'] for u in generation.source_units(notes, fields)[0]
                        if u['start'] <= clinical['value_span']['start']
                        < clinical['value_span']['end'] <= u['end']]
                # Keep the original target identity even when the model calls
                # the foreign source speaker a patient or omits its name.
                self.assertEqual(next(f for f in values if f['id'] == 'identity')
                                 ['value_span'], span(notes, PATIENT))
                answer = self.run_inventory(notes, fields, definitions, values, selected, reference)
                self.assert_held(answer)

    def test_omitted_other_patient_leaves_generic_negative_owner_unresolved(self):
        statements = (
            ('The patient was alert, oriented and in no acute distress.', 'in no acute distress'),
            ('The patient has never used tobacco and does not drink alcohol.', 'never used tobacco'),
            ('The patient has never used tobacco and does not drink alcohol.', 'does not drink alcohol'),
        )
        for (statement, quote), null_name, reference in product(statements, (False, True), REFERENCES):
            with self.subTest(quote=quote, null_name=null_name, reference=reference):
                notes = (PATIENT + ' attended the clinic. Another patient, Synthetic Nolan Reed, '
                         'entered the room. ' + statement)
                fields, definitions, values, selected = self.prepare(notes, quote,
                    name=PATIENT, polarity='negated')
                if null_name:
                    clinical = next(f for f in values if f['id'] == 'clinical')
                    clinical['subject']['name_span'] = None
                    clinical['source_unit_ids'] = [u['id'] for u in generation.source_units(notes, fields)[0]
                        if u['start'] <= clinical['value_span']['start']
                        < clinical['value_span']['end'] <= u['end']]
                self.assertEqual({f['id'] for f in values}, {'identity', 'clinical'})
                answer = self.run_inventory(notes, fields, definitions, values, selected, reference)
                self.assert_held(answer)

    def test_same_unit_video_referral_supports_visit_consultation_and_follow_up(self):
        for visit, reference in product(('visit', 'consultation', 'follow-up'), REFERENCES):
            whole = 'video gastroenterology ' + visit + ' to review prior GI records'
            notes = REFERRAL.rstrip('. ') + ' for a ' + whole + '.'
            for quote in ('video', 'to review prior GI records', whole):
                with self.subTest(visit=visit, quote=quote, reference=reference):
                    answer = self.bound(notes, quote, reference, kind='reason',
                        answer_mode='atomic' if quote == 'video' else 'narrative')
                    self.assertEqual((answer['status'], answer['text']),
                                     ('supported', quote[0].upper() + quote[1:]))

    def test_spelled_referral_age_binds_the_same_target_as_numeric_age(self):
        for age, reference in product(('47', 'forty'), REFERENCES):
            with self.subTest(age=age, reference=reference):
                notes = REFERRAL.replace('47', age) + 'Bowel sounds were normal.'
                answer = self.bound(notes, 'normal', reference)
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Normal'))

    def test_complete_mixed_history_diagnoses_keep_ownership_after_referral(self):
        histories = ('colon polyps', 'colorectal polyps', 'colon cancer', 'colorectal cancer',
                     'irritable bowel syndrome', 'inflammatory bowel disease')
        for history, reference in product(histories, REFERENCES):
            with self.subTest(history=history, reference=reference):
                quote = 'no current gastrointestinal symptoms and a family history of ' + history
                notes = REFERRAL + mixed.PREFIX + quote + '.'
                answer = self.bound(notes, quote, reference, polarity='mixed', kind='assessment')
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', quote[0].upper() + quote[1:]))
                self.assertEqual(answer['fact_ids'], ['clinical'])
                clinical = next(f for f in answer['facts'] if f['id'] == 'clinical')
                self.assertEqual(clinical['value_evidence']['quote'], quote)
                self.assertEqual(clinical['polarity'], 'mixed')
