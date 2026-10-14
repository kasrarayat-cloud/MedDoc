"""Independent v8 observation fidelity boundaries using synthetic provider fixtures.

The checker intentionally passes clipped source values. Deterministic source
binding must still hold them; no saved clinical cases or live providers are read.
"""
from copy import deepcopy
from itertools import product

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation, semantic_generation as semantic, semantic_source_context as context
from core.tests.test_semantic_generation import FixtureSender, assignments, checker, fact, span
from core.tests.test_semantic_source_binding import trace_digest
from core.tests.test_referral_citation import referral_case, PURPOSE, DOCTOR
from documents.semantic_preparation_roles import default_definitions


V8 = 'positioned-observation-context-v8'
V7 = 'positioned-referral-citation-v7'
REFERENCES = (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT)
SOURCE = 'On video, the patient appears alert and comfortable.'
CLIPPED = 'appears alert and comfortable'
# Captured BEFORE v8 edits: semantic_generation SHA256
# 8ca37036cbaa420e50b8ebee5608bb32e912fcdfa397b51fb9a227599a922f5a;
# semantic_source_context SHA256
# 4648d2c6a78edcdee59b6eb6392b7f7123e864cec6c7209f82b461933a8cd905.
# Each pair covers complete answers and all request payload/schema/instructions,
# in REFERENCES order. These are retained v1-v7 behavior, including the old gap.
HISTORICAL_TRACES = {'note-wide-offer-scope-v1': ('c5cc7a2b960d56465f8e1eb3fa9d1cb8381f81ae58e3de8c489c3ddc597ae609',
                              'd3104e22bf21ce58cae1d0b73a93dbb741165f1f5f7e42b7464a48f53b07e123'),
 'positioned-fact-scope-v2': ('0b4c190a858faefb0267ff92f923f8063281a51141d733c5ecc0da51aefe2563',
                              '32210e457fde9f921718547798165d4e6d30fbcb3e9846321d3b3701e4d38c7f'),
 'dimension-aware-duration-scope-v3': ('a41e60e83f4c21ccd1a32920246382ae5fab3c780ce8479c0ab62cf4f0d01adb',
                                       'e3257426c2e12df11c84a8f1d3936c9055a1fa92a04186955b3919afd70bedde'),
 'positioned-family-context-v4': ('6b49a3be8c8ca9c6edf66447073a0c2457971a04d8f9cda5f3642f74c8d2fa46',
                                  '8b6f14751032599a981a777710f237e77b2bd915889835362775c3e984f47c93'),
 'positioned-source-context-v5': ('9d9078822a0eacd2febb98094ace76c4a2ccad7d9c778b554c3b70fb9bba46fa',
                                  '8418f1f3235c9c98083c5ae0ff8020368761f0eaaff6a37ddf6c1e2f747edf0a'),
 'positioned-source-binding-v6': ('a6b24619169ca1feb245fc7dd21dbbc7a450a752f67b060f5a211a1522d9d138',
                                  '608b94c061eee95bf699817936622123fd092417b2177732871b9efe612bfb14'),
 'positioned-referral-citation-v7': ('60d54f0faecaf6bbe41910300ca07e105760b7eb79ca664bc002d6ee228f56c5',
                                     '3eaf5db064a2f2e4c381c322eb10f04d3f46276d1454e281a4f57af639f60dd4')}


def observation_case(notes=SOURCE, quote=CLIPPED, *, occurrence=0, kind='finding',
                     subject='patient', polarity='affirmed', answer_subject='patient'):
    fields = [{'key':'observation', 'kind':'text', 'label':'General observation', 'locator':{'cell':0}}]
    definitions = default_definitions(fields)
    definitions['observation'].update(version=2, answer_mode='narrative',
        meaning='The documented patient observation and its stated context.')
    definitions['observation']['scope'].update(subject=answer_subject, polarity='any', temporality='any')
    values = [fact(notes, fields, 'finding', quote, occurrence=occurrence,
                   kind=kind, subject=subject, polarity=polarity)]
    selected = assignments(fields, {'observation':['finding']})
    return notes, fields, definitions, values, selected


class ObservationContextTests(SimpleTestCase):
    def generate(self, prepared, reference=semantic.REFERENCE_INVENTORY_CONTRACT, profile=V8):
        original = deepcopy(prepared)
        notes, fields, definitions, values, selected = deepcopy(prepared)
        sender = FixtureSender(values, selected)
        answers = semantic.run(notes, fields, definitions, sender,
            scope_contract=profile, reference_contract=reference)
        self.assertEqual(prepared, original)
        self.assertEqual([c[:2] for c in sender.calls], [('extractor',1),('assigner',1),('checker',1)])
        for call in sender.calls:
            self.assertEqual(call[2]['notes'], notes)
        for field in fields:
            semantic.validate_stored_answer(notes, field, definitions[field['key']], answers[field['key']])
        return answers['observation'], sender

    def assert_held(self, answer):
        self.assertIn(answer['status'], ('ambiguous','conflict'))
        self.assertEqual(answer['text'], '')
        self.assertIsNone(answer['value'])
        self.assertTrue(answer['review_reasons'])
        self.assertFalse(answer['reviewed'])

    def test_all_seven_historical_profiles_preserve_complete_trace_bytes(self):
        for profile, goldens in HISTORICAL_TRACES.items():
            for reference, golden in zip(REFERENCES, goldens):
                with self.subTest(profile=profile, reference=reference):
                    answer, sender = self.generate(observation_case(), reference, profile)
                    self.assertEqual(answer['status'], 'supported')
                    self.assertEqual(trace_digest({'observation':answer}, sender), golden)
                    for call in sender.calls:
                        self.assertNotIn('observation_qualifier_inventory', call[2])

    def test_v8_inherits_titled_referral_without_changing_identity_modality_or_purpose(self):
        for title, reference in product(('Dr.','Dr','Doctor'), REFERENCES):
            with self.subTest(title=title, reference=reference):
                case = referral_case(title=title)
                original = deepcopy(case)
                notes, fields, definitions, values, selected = case
                sender = FixtureSender(values, selected)
                answers = semantic.run(notes,fields,definitions,sender,
                    scope_contract=V8,reference_contract=reference)
                self.assertEqual(case, original)
                self.assertEqual([c[:2] for c in sender.calls],
                    [('extractor',1),('assigner',1),('checker',1)])
                self.assertEqual(answers['referrer']['text'], DOCTOR)
                self.assertEqual(answers['modality']['text'], 'In-person')
                self.assertEqual(answers['purpose']['text'], PURPOSE[0].upper()+PURPOSE[1:])
                for field in fields:
                    answer = answers[field['key']]
                    self.assertEqual(answer['status'], 'supported')
                    self.assertEqual(answer['fact_scope_contract'], V8)
                    semantic.validate_stored_answer(notes,field,definitions[field['key']],answer)

    def test_clipped_observation_is_held_even_when_checker_explicitly_passes(self):
        self.assertEqual(semantic.OBSERVATION_CONTEXT_SCOPE_CONTRACT, V8)
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, sender = self.generate(observation_case(), reference)
                self.assert_held(answer)
                self.assertEqual(answer['independent_check']['verdict'], 'pass')
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'], CLIPPED)
                self.assertEqual(answer['facts'][0]['evidence'][0]['quote'], SOURCE)
                self.assertEqual(answer['fact_scope_contract'], V8)
                self.assertEqual(sum(c[0]=='extractor' for c in sender.calls), 1)

    def test_complete_source_observation_is_retained_without_renderer_insertion(self):
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                quote = SOURCE[:-1]
                answer, _ = self.generate(observation_case(quote=quote), reference)
                self.assertEqual(answer['status'], 'supported')
                self.assertEqual(answer['text'], quote)
                self.assertEqual(answer['value'], quote)
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'], quote)

    def test_three_roles_receive_identical_source_owned_exact_inventory(self):
        answer, sender = self.generate(observation_case(quote=SOURCE[:-1]))
        inventories = [call[2]['observation_qualifier_inventory'] for call in sender.calls]
        self.assertEqual(inventories[0], inventories[1])
        self.assertEqual(inventories[1], inventories[2])
        self.assertEqual(len(inventories[0]), 1)
        row = inventories[0][0]
        self.assertEqual(row['source_unit_id'], 1)
        self.assertEqual(row['subject']['quote'], 'the patient')
        self.assertIn(CLIPPED, row['observation']['quote'])
        self.assertEqual(len(row['qualifiers']), 1)
        self.assertEqual(row['qualifiers'][0]['kind'], 'observation_modality')
        self.assertEqual(row['qualifiers'][0]['quote'], 'On video')
        for bound in (row['source'], row['subject'], row['observation'], *row['qualifiers']):
            self.assertEqual(SOURCE[bound['start']:bound['end']], bound['quote'])
        self.assertEqual(answer['status'], 'supported')

    def test_fact_kind_or_subject_relabel_does_not_evade_raw_source_qualifier(self):
        for kind, subject, reference in product(('finding','history','other'),
                                                ('patient','clinician','other'), REFERENCES):
            with self.subTest(kind=kind, subject=subject, reference=reference):
                case = observation_case(kind=kind, subject=subject, answer_subject=subject)
                if subject == 'other':
                    # Explicit citation keeps this an otherwise valid provider
                    # shape, so the observation guard cannot hide behind a
                    # missing-name schema error.
                    case[3][0]['subject']['name_span'] = span(case[0], 'the patient')
                answer, _ = self.generate(case, reference)
                self.assert_held(answer)

    def test_complete_patient_observation_cannot_be_relabelled_as_clinician_or_other(self):
        for subject,kind,reference in product(('clinician','other'),
                                             ('finding','history','other'),REFERENCES):
            with self.subTest(subject=subject,kind=kind,reference=reference):
                case = observation_case(quote=SOURCE[:-1],subject=subject,
                    answer_subject=subject,kind=kind)
                if subject == 'other':
                    case[3][0]['subject']['name_span'] = span(case[0],'the patient')
                answer, _ = self.generate(case,reference)
                self.assert_held(answer)

    def test_comma_spacing_cannot_erase_explicit_source_modality(self):
        sources = (
            'On video,the patient appears alert and comfortable.',
            'On video ,the patient appears alert and comfortable.',
            'On video\t,the patient appears alert and comfortable.',
        )
        for notes,reference in product(sources,REFERENCES):
            with self.subTest(notes=notes,reference=reference):
                answer, sender = self.generate(observation_case(notes),reference)
                self.assert_held(answer)
                rows = sender.calls[0][2]['observation_qualifier_inventory']
                self.assertTrue(rows)
                qualifier = rows[0]['qualifiers'][0]
                self.assertEqual(notes[qualifier['start']:qualifier['end']],qualifier['quote'])
                self.assertEqual(qualifier['quote'],'On video')

    def test_colon_or_absent_separator_cannot_erase_explicit_source_modality(self):
        sources = (
            'On video,the patient appears alert and comfortable.',
            'On video: the patient appears alert and comfortable.',
            'On video:the patient appears alert and comfortable.',
            'On video the patient appears alert and comfortable.',
        )
        for notes,reference in product(sources,REFERENCES):
            with self.subTest(notes=notes,reference=reference):
                answer, sender = self.generate(observation_case(notes),reference)
                self.assert_held(answer)
                self.assertEqual(answer['independent_check']['verdict'],'pass')
                rows = sender.calls[0][2]['observation_qualifier_inventory']
                self.assertTrue(rows)
                qualifier = rows[0]['qualifiers'][0]
                self.assertEqual(notes[qualifier['start']:qualifier['end']],'On video')
                complete, _ = self.generate(observation_case(notes,notes[:-1]),reference)
                self.assertEqual(complete['status'],'supported')
                self.assertEqual(complete['text'],notes[:-1])

    def test_unfamiliar_separator_keeps_observation_held_instead_of_erasing_qualifier(self):
        for separator,reference in product(('—',';','–','／','。'),REFERENCES):
            with self.subTest(separator=separator,reference=reference):
                notes = 'On video'+separator+'the patient appears alert and comfortable.'
                for quote in (CLIPPED,notes[:-1]):
                    with self.subTest(quote=quote):
                        answer, sender = self.generate(observation_case(notes,quote),reference)
                        self.assert_held(answer)
                        rows = sender.calls[0][2]['observation_qualifier_inventory']
                        self.assertTrue(rows)
                        qualifier = rows[0]['qualifiers'][0]
                        self.assertEqual(notes[qualifier['start']:qualifier['end']],'On video')

    def test_full_generic_observation_requires_unambiguous_preceding_source_context(self):
        target = 'Synthetic Nia Park'
        prefixes = (
            target+' is 36 years old. Another patient entered the room. ',
            target+' is 36 years old. Synthetic Hugo Reed is anxious. ',
            'Another patient entered the room. ',
            'Synthetic Hugo Reed is anxious. ',
            'The note now discusses a different person. ',
        )
        for prefix,reference,cite_name in product(prefixes,REFERENCES,(False,True)):
            with self.subTest(prefix=prefix,reference=reference,cite_name=cite_name):
                notes = prefix+SOURCE
                case = observation_case(notes,SOURCE[:-1])
                finding = case[3][0]
                if target in prefix:
                    case[3].insert(0,fact(notes,case[1],'identity',target,
                        kind='identity',name_quote=target,timing='unspecified'))
                if cite_name:
                    finding['subject']['name_span'] = span(notes,
                        target if target in prefix else 'the patient')
                finding['source_unit_ids'] = [u['id'] for u in generation.source_units(notes,case[1])[0]]
                answer, _ = self.generate(case,reference)
                self.assert_held(answer)
                self.assertEqual(answer['independent_check']['verdict'],'pass')

    def test_full_generic_observation_cannot_cite_a_different_named_person(self):
        target,other = 'Synthetic Nia Park','Synthetic Hugo Reed'
        notes = target+' is 36 years old. '+SOURCE+' '+other+' is anxious.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = observation_case(notes,SOURCE[:-1])
                case[3].insert(0,fact(notes,case[1],'identity',target,
                    kind='identity',name_quote=target,timing='unspecified'))
                finding = case[3][-1]
                finding['subject']['name_span'] = span(notes,other)
                finding['source_unit_ids'] = [u['id'] for u in generation.source_units(notes,case[1])[0]]
                answer, _ = self.generate(case,reference)
                self.assert_held(answer)
                saved_finding = next(value for value in answer['facts'] if value['id']=='finding')
                self.assertEqual(saved_finding['subject']['name_evidence']['quote'],other)

    def test_complete_generic_standalone_or_repeated_source_keeps_exact_ownership(self):
        for repeats,reference,cite_name in product((1,2),REFERENCES,(False,True)):
            with self.subTest(repeats=repeats,reference=reference,cite_name=cite_name):
                notes = ' '.join([SOURCE]*repeats)
                case = observation_case(notes,SOURCE[:-1],occurrence=repeats-1)
                if cite_name:
                    case[3][0]['subject']['name_span'] = span(notes,'the patient',repeats-1)
                answer, _ = self.generate(case,reference)
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],SOURCE[:-1])
                self.assertEqual(answer['facts'][0]['value_span'],span(notes,SOURCE[:-1],repeats-1))

    def test_complete_observation_does_not_override_an_independent_checker_hold(self):
        case = observation_case(quote=SOURCE[:-1])
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                notes,fields,definitions,values,selected = deepcopy(case)
                sender = FixtureSender(values,selected,checker(selected,fact_findings=[{
                    'fact_id':'finding','verdict':'ambiguous',
                    'reason':'Independent fixture leaves source unresolved.'}]))
                answers = semantic.run(notes,fields,definitions,sender,
                    scope_contract=V8,reference_contract=reference)
                self.assert_held(answers['observation'])
                semantic.validate_stored_answer(notes,fields[0],definitions['observation'],answers['observation'])

    def test_separate_selected_modality_fact_cannot_launder_clipped_observation(self):
        case = observation_case()
        case[3].append(fact(case[0], case[1], 'modality', 'On video', kind='other'))
        case[4]['fields'][0]['fact_ids'] = ['modality','finding']
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, _ = self.generate(case, reference)
                self.assert_held(answer)
                self.assertEqual(answer['fact_ids'], ['modality','finding'])

    def test_unrelated_video_visit_or_future_plan_does_not_qualify_this_observation(self):
        notes_cases = (
            'The patient appears alert and comfortable. The plan is a video follow-up.',
            'The patient had a video visit. The patient appears alert and comfortable.',
        )
        for notes, reference in product(notes_cases, REFERENCES):
            with self.subTest(notes=notes, reference=reference):
                old, _ = self.generate(observation_case(notes), reference, V7)
                answer, sender = self.generate(observation_case(notes), reference)
                self.assertEqual(old['status'], 'supported')
                self.assertEqual(answer['status'], 'supported')
                self.assertEqual(answer['text'], old['text'])
                self.assertEqual(sender.calls[0][2]['observation_qualifier_inventory'], [])

    def test_video_prefixed_history_does_not_acquire_observation_modality_requirement(self):
        cases = (
            ('On video, the patient denies nausea.', 'denies nausea', 'negated'),
            ('On video, the patient takes acetaminophen.', 'takes acetaminophen', 'affirmed'),
        )
        for (notes, quote, polarity), reference in product(cases,REFERENCES):
            with self.subTest(notes=notes,reference=reference):
                case = observation_case(notes,quote,kind='history',polarity=polarity)
                case[1][0]['label'] = 'History'
                case[2]['observation']['meaning'] = 'The documented patient history, without examination findings.'
                old, _ = self.generate(case,reference,V7)
                current, sender = self.generate(case,reference)
                self.assertEqual(old['status'],'supported')
                self.assertEqual(current['status'],'supported')
                self.assertEqual(current['text'],old['text'])
                self.assertEqual(sender.calls[0][2]['observation_qualifier_inventory'],[])

    def test_duplicate_words_are_bound_to_each_exact_occurrence(self):
        notes = SOURCE+' '+SOURCE
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, sender = self.generate(observation_case(notes, occurrence=1), reference)
                self.assert_held(answer)
                rows = sender.calls[0][2]['observation_qualifier_inventory']
                self.assertEqual(len(rows), 2)
                self.assertEqual([r['qualifiers'][0]['start'] for r in rows], [0,len(SOURCE)+1])
                self.assertEqual(answer['facts'][0]['value_span'], span(notes, CLIPPED, 1))
                self.assertNotEqual(rows[0]['qualifiers'][0]['start'], rows[1]['qualifiers'][0]['start'])
                complete, _ = self.generate(observation_case(notes, SOURCE[:-1], occurrence=1), reference)
                self.assertEqual(complete['status'], 'supported')
                self.assertEqual(complete['facts'][0]['value_span'], span(notes, SOURCE[:-1], 1))

    def test_compound_clause_cannot_hide_an_explicit_governing_video_qualifier(self):
        notes_cases = (
            'On video, the patient appears alert and comfortable and the nurse is anxious.',
            'On video, the patient appears alert and comfortable but the examiner is uncertain.',
        )
        for notes, reference in product(notes_cases, REFERENCES):
            with self.subTest(notes=notes, reference=reference):
                answer, _ = self.generate(observation_case(notes), reference)
                self.assert_held(answer)

    def test_complete_qualifier_does_not_grant_foreign_or_hypothetical_ownership(self):
        cases = (
            ("On video, the patient's sister appears alert and comfortable.",
             "On video, the patient's sister appears alert and comfortable"),
            ('On video, the nurse appears alert and comfortable.',
             'On video, the nurse appears alert and comfortable'),
            ("On video, the patient's partner appears alert and comfortable.",
             "On video, the patient's partner appears alert and comfortable"),
            ('On video, another patient appears alert and comfortable.',
             'On video, another patient appears alert and comfortable'),
            ('If on video, the patient appears alert and comfortable.',
             'If on video, the patient appears alert and comfortable'),
            ('Possibly on video, the patient appears alert and comfortable.',
             'Possibly on video, the patient appears alert and comfortable'),
            ('On video, the patient may appear alert and comfortable.',
             'On video, the patient may appear alert and comfortable'),
        )
        for (notes, quote), reference in product(cases, REFERENCES):
            with self.subTest(notes=notes, reference=reference):
                answer, _ = self.generate(observation_case(notes, quote), reference)
                self.assert_held(answer)

    def test_foreign_observation_qualifier_does_not_spread_to_later_patient(self):
        notes_cases = (
            'On video, the nurse appears alert. The patient appears alert and comfortable.',
            "On video, the patient's sister appears alert. The patient appears alert and comfortable.",
        )
        for notes, reference in product(notes_cases, REFERENCES):
            with self.subTest(notes=notes, reference=reference):
                answer, _ = self.generate(observation_case(notes), reference)
                self.assertEqual(answer['status'], 'supported')
                self.assertEqual(answer['text'], 'Appears alert and comfortable')

    def test_identical_words_in_unqualified_second_occurrence_do_not_borrow_first_context(self):
        notes = SOURCE+' The patient appears alert and comfortable.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                first, _ = self.generate(observation_case(notes, occurrence=0), reference)
                self.assert_held(first)
                second, _ = self.generate(observation_case(notes, occurrence=1), reference)
                self.assertEqual(second['status'], 'supported')
                self.assertEqual(second['text'], 'Appears alert and comfortable')
                self.assertEqual(second['facts'][0]['value_span'], span(notes,CLIPPED,1))

    def test_full_foreign_name_does_not_override_independently_evidenced_target(self):
        target, other = 'Synthetic Nia Park', 'Synthetic Hugo Reed'
        notes = target+' is 36 years old. On video, '+other+' appears alert and comfortable.'
        quote = 'On video, '+other+' appears alert and comfortable'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = observation_case(notes, quote)
                case[3].insert(0, fact(notes,case[1],'patient_identity',target,
                    kind='identity',name_quote=target,timing='unspecified'))
                finding = case[3][1]
                finding['subject']['name_span'] = span(notes,target)
                finding['source_unit_ids'] = [u['id'] for u in generation.source_units(notes,case[1])[0]]
                answer, _ = self.generate(case, reference)
                self.assert_held(answer)

    def test_complete_negative_keeps_existing_negation_guard_and_clipped_negative_is_held(self):
        notes = 'On video, the patient is in no acute distress.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                complete = observation_case(notes, notes[:-1], polarity='negated')
                old_full, _ = self.generate(complete, reference, V7)
                new_full, _ = self.generate(complete, reference)
                self.assert_held(old_full)
                self.assert_held(new_full)
                self.assertEqual(new_full['review_reasons'], old_full['review_reasons'])
                # Bounded limitation: the existing negative-head rule does not
                # admit a whole prefixed negative observation. V8 must not waive
                # that rule to make the new qualifier requirement pass.
                for quote in ('in no acute distress','no acute distress'):
                    clipped = observation_case(notes, quote, polarity='negated')
                    old_clip, _ = self.generate(clipped, reference, V7)
                    self.assertEqual(old_clip['status'], 'supported')
                    new_clip, _ = self.generate(clipped, reference)
                    self.assert_held(new_clip)

    def test_unicode_and_literal_whitespace_keep_exact_codepoint_offsets(self):
        notes = 'Record 🩺 café. On video,	 the patient appears alert and comfortable.'
        fields = observation_case()[1]
        units = generation.source_units(notes, fields)[0]
        original = deepcopy(units)
        rows = context.observation_qualifier_inventory(units)
        self.assertEqual(units, original)
        self.assertEqual(len(rows), 1)
        qualifier = rows[0]['qualifiers'][0]
        self.assertEqual(qualifier['quote'], 'On video')
        self.assertEqual(qualifier['start'], notes.index('On video'))
        self.assertNotEqual(qualifier['start'], len(notes[:qualifier['start']].encode('utf-8')))
        for bound in (rows[0]['source'], rows[0]['subject'], rows[0]['observation'], qualifier):
            self.assertEqual(notes[bound['start']:bound['end']], bound['quote'])
        literal = 'On video,	the patient appears alert and comfortable.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                clipped, _ = self.generate(observation_case(literal), reference)
                self.assert_held(clipped)
                complete, _ = self.generate(observation_case(literal, literal[:-1]), reference)
                self.assertEqual(complete['status'], 'supported')
                # Rendering may apply its established whitespace normalization,
                # but source evidence must retain the exact original span bytes.
                self.assertEqual(complete['facts'][0]['value_evidence']['quote'], literal[:-1])
                self.assertIn('video', complete['text'])

    def test_stored_held_answer_cannot_be_forged_supported_by_checker_pass(self):
        case = observation_case()
        answer, _ = self.generate(case)
        self.assert_held(answer)
        forged = deepcopy(answer)
        forged.update(status='supported', text='Appears alert and comfortable',
                      value='Appears alert and comfortable', review_reasons=[])
        # Fact inventory, source spans and proof stay untouched; a passing checker
        # and altered display/status still cannot authorize the source omission.
        self.assertEqual(forged['semantic_proof_sha256'], answer['semantic_proof_sha256'])
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(case[0],case[1][0],case[2]['observation'],forged)

    def test_stored_complete_answer_rejects_removed_qualifier_and_changed_source(self):
        case = observation_case(quote=SOURCE[:-1])
        answer, _ = self.generate(case)
        self.assertEqual(answer['status'], 'supported')
        forged = deepcopy(answer)
        forged.update(text='Appears alert and comfortable',value='Appears alert and comfortable')
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(case[0],case[1][0],case[2]['observation'],forged)
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(case[0].replace('video','telephone'),
                case[1][0],case[2]['observation'],answer)
