"""Finite consent-purpose fidelity; all provider replies are synthetic fixtures."""
from copy import deepcopy
from itertools import product

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation, semantic_generation as semantic, semantic_source_context as context
from core.tests.test_semantic_generation import FixtureSender, assignments, checker, fact, span
from core.tests.test_semantic_source_binding import trace_digest
from core.tests.test_observation_context import observation_case
from core.tests.test_referral_citation import referral_case, PURPOSE, DOCTOR
from documents.semantic_preparation_roles import default_definitions


V9 = 'positioned-consent-context-v9'
V8 = 'positioned-observation-context-v8'
REFERENCES = (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT)
SOURCE = 'The patient gave verbal consent for this video consultation.'
COMPLETE = 'verbal consent for this video consultation'
CLIPPED = 'verbal consent'
# Frozen before v9 implementation against installed a9d64d8b. Each reference
# pair covers complete payload/schema/instructions and answers for consent and
# observation, retaining even the old consent omission. No private cases loaded.
HISTORICAL_TRACES = {'note-wide-offer-scope-v1': [('eea594ff86e22114862c9ce07bdb28678d68a35be5bee739b20621c5596e6883',
                               'c5cc7a2b960d56465f8e1eb3fa9d1cb8381f81ae58e3de8c489c3ddc597ae609'),
                              ('de6103fbd471c8f7402a2afaf57098d4a66ec112a9d30145650822e6c7fbe0b8',
                               'd3104e22bf21ce58cae1d0b73a93dbb741165f1f5f7e42b7464a48f53b07e123')],
 'positioned-fact-scope-v2': [('badd9b78d6df046afed19aaf2729b4565a91a087da000f944497e4bc13f27199',
                               '0b4c190a858faefb0267ff92f923f8063281a51141d733c5ecc0da51aefe2563'),
                              ('f16e981b2d7641c7772af7953495a0e6e2c128f651ceccb41d2f61fe8586d58f',
                               '32210e457fde9f921718547798165d4e6d30fbcb3e9846321d3b3701e4d38c7f')],
 'dimension-aware-duration-scope-v3': [('b7b8a2e9169e44e14665690a8eea1177e8fdddbc1e6b2b11cbf72f0b6c362d44',
                                        'a41e60e83f4c21ccd1a32920246382ae5fab3c780ce8479c0ab62cf4f0d01adb'),
                                       ('c9958e853f61ba54863a8500baac297c39476defb9cac9588627ddd932ed1968',
                                        'e3257426c2e12df11c84a8f1d3936c9055a1fa92a04186955b3919afd70bedde')],
 'positioned-family-context-v4': [('0ed0955f9939353a6fd80216e2ca2bf88bcc19d359e3712b0bffe7e1be6c8728',
                                   '6b49a3be8c8ca9c6edf66447073a0c2457971a04d8f9cda5f3642f74c8d2fa46'),
                                  ('5b09a71544a4d91a5eab95ec675c69efb75cee49166b6029df630d9fd7eb2e07',
                                   '8b6f14751032599a981a777710f237e77b2bd915889835362775c3e984f47c93')],
 'positioned-source-context-v5': [('4db5076a5e2e54c194b0e47760e57095f4df047cbcc1efd04365a4c73d7903d1',
                                   '9d9078822a0eacd2febb98094ace76c4a2ccad7d9c778b554c3b70fb9bba46fa'),
                                  ('37d956737babc80ae5d257d0e6ddbe4e11cf001eec4adda45e3f2f98ba217d63',
                                   '8418f1f3235c9c98083c5ae0ff8020368761f0eaaff6a37ddf6c1e2f747edf0a')],
 'positioned-source-binding-v6': [('058607cd16e168df722d7f9f1c9b120ba864091999f87bfcefb501dbb2e0e01f',
                                   'a6b24619169ca1feb245fc7dd21dbbc7a450a752f67b060f5a211a1522d9d138'),
                                  ('c5d0ff09ea421884c3bf0c8aa1eb37cf345b8651be8e47e108c8ff7f4942deac',
                                   '608b94c061eee95bf699817936622123fd092417b2177732871b9efe612bfb14')],
 'positioned-referral-citation-v7': [('8384bdda13a1490d48e6afeea72207cb5e8a47d530e0be0f1b3b5faccccc253f',
                                      '60d54f0faecaf6bbe41910300ca07e105760b7eb79ca664bc002d6ee228f56c5'),
                                     ('81a89a4e0270c8b54099d6103a4ec7612a231a2f159cb6234972af5d7e7fed95',
                                      '3eaf5db064a2f2e4c381c322eb10f04d3f46276d1454e281a4f57af639f60dd4')],
 'positioned-observation-context-v8': [('280da5d365a6ff45a894a887428d0e9c80615d457e86bebf22d0466ae848109a',
                                        '7826fdc24a531a0caebbdd3a5b6fefe0be274e8674a70f000cdf5afafd503418'),
                                       ('c6b8e92154356a48f81a025fffe535ed64a621e4c047c4626a225b0878de4cf3',
                                        '0887c4ce123f84136bf14a11bc3ce0a156de3fae7391bfe7354bdff6852cab81')]}


def consent_case(notes=SOURCE, quote=CLIPPED, *, occurrence=0, kind='other',
                 subject='patient', polarity='affirmed', answer_subject='encounter',
                 name_quote=None):
    fields = [{'key':'consent', 'kind':'text', 'label':'Documented consent', 'locator':{'cell':0}}]
    definitions = default_definitions(fields)
    definitions['consent'].update(version=2, answer_mode='atomic',
        meaning='The documented consent and its stated purpose.')
    definitions['consent']['scope'].update(subject=answer_subject, polarity='any', temporality='any')
    values = [fact(notes, fields, 'consent', quote, occurrence=occurrence,
        kind=kind, subject=subject, polarity=polarity, name_quote=name_quote)]
    units = generation.source_units(notes, fields)[0]
    for value in values:
        name = value['subject']['name_span']
        if name is not None:
            value['source_unit_ids'] = sorted(set(value['source_unit_ids'] + [
                unit['id'] for unit in units if unit['start'] <= name['start'] < name['end'] <= unit['end']]))
    return notes, fields, definitions, values, assignments(fields, {'consent':['consent']})


def named_consent_case(quote=CLIPPED, *, name='Synthetic Wren Bell',
                       referrer='Avery Lane', statement=None, named=True, separator=' '):
    given = name.split()[1]
    statement = statement or given+' gave verbal consent for this video consultation.'
    notes = name+' is 39 years old and was referred by Dr. '+referrer+'.'+separator+statement
    case = consent_case(notes, quote, name_quote=name if named else None)
    values = case[3]
    values[:0] = [fact(notes,case[1],'patient',name,kind='identity',name_quote=name,timing='unspecified'),
        fact(notes,case[1],'referrer',referrer,kind='identity',subject='other',
             name_quote='Dr. '+referrer,timing='unspecified')]
    return case


class ConsentContextTests(SimpleTestCase):
    def generate(self, case, reference=semantic.REFERENCE_INVENTORY_CONTRACT,
                 profile=V9, checked=None):
        original = deepcopy(case)
        notes, fields, definitions, values, selected = deepcopy(case)
        sender = FixtureSender(values, selected, checked)
        answers = semantic.run(notes,fields,definitions,sender,
            scope_contract=profile,reference_contract=reference)
        self.assertEqual(case,original)
        self.assertEqual([call[:2] for call in sender.calls],
            [('extractor',1),('assigner',1),('checker',1)])
        for field in fields:
            semantic.validate_stored_answer(notes,field,definitions[field['key']],answers[field['key']])
        return answers,sender

    def assert_held(self, answer):
        self.assertIn(answer['status'],('conflict','ambiguous'))
        self.assertEqual(answer['text'],'')
        self.assertIsNone(answer['value'])
        self.assertTrue(answer['review_reasons'])
        self.assertFalse(answer['reviewed'])

    def test_all_eight_historical_profiles_keep_complete_consent_and_observation_traces(self):
        for profile, goldens in HISTORICAL_TRACES.items():
            for reference, (consent_golden, observation_golden) in zip(REFERENCES,goldens):
                with self.subTest(profile=profile,reference=reference):
                    answers,sender = self.generate(consent_case(),reference,profile)
                    self.assertEqual(answers['consent']['status'],'supported')
                    self.assertEqual(trace_digest(answers,sender),consent_golden)
                    for call in sender.calls:
                        self.assertNotIn('consent_qualifier_inventory',call[2])
                    answers,sender = self.generate(observation_case(),reference,profile)
                    self.assertEqual(trace_digest(answers,sender),observation_golden)

    def test_clipped_consent_type_head_and_incomplete_purpose_stay_held(self):
        self.assertEqual(semantic.CONSENT_CONTEXT_SCOPE_CONTRACT,V9)
        for quote,reference in product(('verbal','consent',CLIPPED,
                'verbal consent for this video','consent for this video consultation'),REFERENCES):
            with self.subTest(quote=quote,reference=reference):
                answer = self.generate(consent_case(quote=quote),reference)[0]['consent']
                self.assert_held(answer)
                self.assertEqual(answer['independent_check']['verdict'],'pass')
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'],quote)

    def test_complete_phrase_or_whole_assertion_needs_no_renderer_insertion(self):
        for quote,reference in product((COMPLETE,SOURCE[:-1],SOURCE),REFERENCES):
            with self.subTest(quote=quote,reference=reference):
                case = consent_case(quote=quote)
                if quote != COMPLETE:
                    case[2]['consent']['answer_mode'] = 'narrative'
                answer = self.generate(case,reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],quote[:1].upper()+quote[1:])
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'],quote)
                self.assertEqual(answer['fact_scope_contract'],V9)

    def test_atomic_destination_keeps_existing_whole_clause_hold(self):
        for reference in REFERENCES:
            case = consent_case(quote=SOURCE[:-1])
            old = self.generate(case,reference,V8)[0]['consent']
            new = self.generate(case,reference)[0]['consent']
            self.assert_held(old)
            self.assert_held(new)
            self.assertEqual(new['review_reasons'],old['review_reasons'])

    def test_named_referral_and_short_reference_bind_complete_consent_generically(self):
        for name,referrer,reference,named in product(
                ('Synthetic Wren Bell','Synthetic Ellis Brooks'),('Avery Lane','Dana Hill'),REFERENCES,(False,True)):
            with self.subTest(name=name,referrer=referrer,reference=reference,named=named):
                clipped = named_consent_case(name=name,referrer=referrer,named=named)
                self.assert_held(self.generate(clipped,reference)[0]['consent'])
                complete = named_consent_case(COMPLETE,name=name,referrer=referrer,named=named)
                answer = self.generate(complete,reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],'Verbal consent for this video consultation')

    def test_checker_reason_with_omitted_purpose_cannot_repair_the_selected_value(self):
        for reference in REFERENCES:
            case = named_consent_case()
            checked = checker(case[4])
            checked['fields'][0]['reason'] = 'Verbal consent for the video consultation is documented.'
            answer = self.generate(case,reference,checked=checked)[0]['consent']
            self.assert_held(answer)
            self.assertEqual(answer['independent_check']['verdict'],'pass')
            self.assertEqual(answer['candidate_text'],'Verbal consent')
            self.assertIn('video consultation',answer['independent_check']['reason'])

    def test_existing_literal_modality_vocabulary_preserves_the_own_consent_purpose(self):
        for modality,reference in product(('video','telephone','telehealth','video telehealth','in-person'),REFERENCES):
            with self.subTest(modality=modality,reference=reference):
                notes = 'The patient gave verbal consent for this '+modality+' consultation.'
                quote = 'verbal consent for this '+modality+' consultation'
                answer = self.generate(consent_case(notes,quote),reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],quote[:1].upper()+quote[1:])
                self.assert_held(self.generate(consent_case(notes),reference)[0]['consent'])

    def test_all_roles_receive_same_exact_source_owned_consent_inventory(self):
        answers,sender = self.generate(consent_case(quote=COMPLETE))
        inventories = [call[2]['consent_qualifier_inventory'] for call in sender.calls]
        self.assertEqual(inventories[0],inventories[1])
        self.assertEqual(inventories[1],inventories[2])
        self.assertEqual(len(inventories[0]),1)
        row = inventories[0][0]
        self.assertTrue(row['recognized_complete_assertion'])
        self.assertEqual(row['source_unit_id'],1)
        self.assertEqual(row['consent']['quote'],CLIPPED)
        self.assertEqual(row['purpose']['quote'],'for this video consultation')
        for selected in (row['source'],row['subject'],row['consent'],row['purpose'],*row['consent_heads']):
            self.assertEqual(SOURCE[selected['start']:selected['end']],selected['quote'])
        for call,suffix in zip(sender.calls,(semantic.CONSENT_CONTEXT_EXTRACT_INSTRUCTIONS,
                semantic.CONSENT_CONTEXT_ASSIGN_INSTRUCTIONS,semantic.CONSENT_CONTEXT_CHECK_INSTRUCTIONS)):
            self.assertTrue(call[4].endswith(suffix))
            self.assertIn('observation_qualifier_inventory',call[2])

    def test_purpose_only_modality_fact_does_not_acquire_consent_head_obligation(self):
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = consent_case(quote='video')
                case[1][0]['label'] = 'Visit modality'
                case[2]['consent'].update(meaning='The documented visit modality.',
                    value_type='choice',choices=['Video','Telephone','In-person'])
                answer = self.generate(case,reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],'Video')
                self.assertEqual(answer['facts'][0]['issues'],[])

    def test_separate_purpose_fact_cannot_repair_a_clipped_consent_head(self):
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                case = consent_case()
                case[2]['consent']['answer_mode'] = 'narrative'
                case[3].append(fact(case[0],case[1],'purpose','for this video consultation',kind='other'))
                case[4]['fields'][0]['fact_ids'] = ['consent','purpose']
                answer = self.generate(case,reference)[0]['consent']
                self.assert_held(answer)
                self.assertTrue(next(f for f in answer['facts'] if f['id']=='consent')['issues'])

    def test_kind_subject_or_concept_metadata_cannot_bypass_source_obligation(self):
        for kind,subject,reference in product(('other','history','finding','reason'),
                                             ('patient','clinician','other'),REFERENCES):
            with self.subTest(kind=kind,subject=subject,reference=reference):
                case = consent_case(kind=kind,subject=subject,answer_subject=subject,
                    name_quote='The patient' if subject=='other' else None)
                case[3][0]['concept'] = 'unrelated provider label'
                self.assert_held(self.generate(case,reference)[0]['consent'])

    def test_complete_patient_consent_cannot_be_relabelled_as_a_different_subject(self):
        for subject,reference in product(('clinician','other','uncertain'),REFERENCES):
            with self.subTest(subject=subject,reference=reference):
                case = consent_case(quote=COMPLETE,subject=subject,
                    name_quote='The patient' if subject=='other' else None)
                self.assert_held(self.generate(case,reference)[0]['consent'])

    def test_complete_foreign_relative_or_hypothetical_assertion_is_not_patient_owned(self):
        sources = (
            "The patient's sister gave verbal consent for this video consultation.",
            'The nurse gave verbal consent for this video consultation.',
            'Another patient gave verbal consent for this video consultation.',
            'Synthetic Hugo Reed gave verbal consent for this video consultation.',
            'If the patient gave verbal consent for this video consultation.',
            'Possibly the patient gave verbal consent for this video consultation.',
        )
        for notes,reference in product(sources,REFERENCES):
            with self.subTest(notes=notes,reference=reference):
                for quote in (COMPLETE,notes[:-1]):
                    case = consent_case(notes,quote)
                    case[2]['consent']['answer_mode'] = 'narrative'
                    self.assert_held(self.generate(case,reference)[0]['consent'])

    def test_named_foreign_source_or_missing_identity_does_not_borrow_target(self):
        for statement,reference in product((
                'Synthetic Hugo Reed gave verbal consent for this video consultation.',
                'Another patient entered the room. The patient gave verbal consent for this video consultation.',
                'Synthetic Hugo Reed is anxious. The patient gave verbal consent for this video consultation.'),REFERENCES):
            with self.subTest(statement=statement,reference=reference):
                case = named_consent_case(COMPLETE,statement=statement,separator='\n')
                self.assert_held(self.generate(case,reference)[0]['consent'])
        for reference in REFERENCES:
            case = named_consent_case(COMPLETE)
            case[3][:] = [f for f in case[3] if f['id']!='patient']
            self.assert_held(self.generate(case,reference)[0]['consent'])

    def test_generic_patient_requires_complete_unambiguous_source_context_and_name(self):
        prefixes = ('Another patient entered the room. ', 'Synthetic Hugo Reed is anxious. ',
                    'The note now discusses someone else. ')
        for prefix,reference in product(prefixes,REFERENCES):
            with self.subTest(prefix=prefix,reference=reference):
                notes = prefix+SOURCE
                for name in (None,'The patient'):
                    self.assert_held(self.generate(consent_case(notes,COMPLETE,name_quote=name),reference)[0]['consent'])
        for reference in REFERENCES:
            notes = SOURCE+' Synthetic Hugo Reed is anxious.'
            case = consent_case(notes,COMPLETE,name_quote='Synthetic Hugo Reed')
            self.assert_held(self.generate(case,reference)[0]['consent'])
            good = consent_case(quote=COMPLETE,name_quote='The patient')
            self.assertEqual(self.generate(good,reference)[0]['consent']['status'],'supported')

    def test_each_occurrence_retains_its_own_purpose(self):
        notes = SOURCE+' The patient gave verbal consent for this telephone consultation.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer,sender = self.generate(consent_case(notes,CLIPPED,occurrence=1),reference)
                self.assert_held(answer['consent'])
                rows = sender.calls[0][2]['consent_qualifier_inventory']
                self.assertEqual(len(rows),2)
                self.assertNotEqual(rows[0]['purpose'],rows[1]['purpose'])
                complete = consent_case(notes,'verbal consent for this telephone consultation')
                answer = self.generate(complete,reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['facts'][0]['value_span'],span(notes,'verbal consent for this telephone consultation'))

    def test_unfamiliar_type_purpose_separator_and_compound_syntax_stay_held(self):
        sources = (
            'The patient gave written consent for this video consultation.',
            'The patient gave oral consent for this video consultation.',
            'The patient gave informed verbal consent for this video consultation.',
            'The patient gave verbal—consent for this video consultation.',
            'The patient gave verbal consent: for this video consultation.',
            'The patient gave verbal consent only for this video consultation.',
            'The patient gave verbal consent for this video consultation but not telephone consultations.',
            'The patient gave verbal consent for this video consultation and the nurse signed.',
            'The patient gave verbal consent for this video consultation, and verbal consent for recording.',
            'The patient did not give verbal consent for this video consultation.',
            'The patient may give verbal consent for this video consultation.',
            'The patient previously gave verbal consent for this video consultation.',
            'The patient gave verbal consent.',
        )
        for notes,reference in product(sources,REFERENCES):
            with self.subTest(notes=notes,reference=reference):
                for quote in ('consent',notes[:-1]):
                    case = consent_case(notes,quote)
                    case[2]['consent']['answer_mode'] = 'narrative'
                    answers,sender = self.generate(case,reference)
                    self.assert_held(answers['consent'])
                    self.assertTrue(sender.calls[0][2]['consent_qualifier_inventory'])

    def test_unfamiliar_punctuation_cannot_hide_a_selected_consent_type(self):
        for separator,reference in product(('—','–','-','／','。',';',':'),REFERENCES):
            with self.subTest(separator=separator,reference=reference):
                notes = 'The patient gave verbal'+separator+'consent for this video consultation.'
                self.assert_held(self.generate(consent_case(notes,'verbal'),reference)[0]['consent'])

    def test_other_histories_and_later_purpose_do_not_inherit_consent_scope(self):
        notes = SOURCE+' The patient reports bloating for two weeks.'
        for reference in REFERENCES:
            case = consent_case(notes,'bloating',kind='history')
            answer = self.generate(case,reference)[0]['consent']
            self.assertEqual(answer['status'],'supported')
            self.assertEqual(answer['text'],'Bloating')
            bare = 'The patient gave verbal consent. This was a video consultation.'
            answer = self.generate(consent_case(bare),reference)[0]['consent']
            self.assert_held(answer)
            self.assertNotIn('video',answer['candidate_text'])

    def test_unicode_whitespace_and_case_keep_exact_raw_spans(self):
        notes = 'The patient gave VERBAL\u00a0consent for\tthis video\u00a0consultation.'
        quote = 'VERBAL\u00a0consent for\tthis video\u00a0consultation'
        for reference in REFERENCES:
            answer,sender = self.generate(consent_case(notes,quote),reference)
            self.assertEqual(answer['consent']['status'],'supported')
            row = sender.calls[0][2]['consent_qualifier_inventory'][0]
            for selected in (row['source'],row['subject'],row['consent'],row['purpose'],*row['consent_heads']):
                self.assertEqual(notes[selected['start']:selected['end']],selected['quote'])
            self.assertEqual(answer['consent']['facts'][0]['value_evidence']['quote'],quote)
        prefixed = 'Record 🩺 café. '+SOURCE
        units = generation.source_units(prefixed,[])[0]
        original = deepcopy(units)
        row = context.consent_qualifier_inventory(units)[0]
        self.assertEqual(units,original)
        self.assertEqual(row['consent']['start'],prefixed.index(CLIPPED))
        self.assertNotEqual(row['consent']['start'],len(prefixed[:row['consent']['start']].encode()))

    def test_complete_value_does_not_override_independent_checker_hold(self):
        for reference in REFERENCES:
            case = consent_case(quote=COMPLETE)
            checked = checker(case[4],fact_findings=[{'fact_id':'consent','verdict':'ambiguous',
                'reason':'Synthetic unresolved evidence.'}])
            self.assert_held(self.generate(case,reference,checked=checked)[0]['consent'])

    def test_stored_hold_or_complete_value_cannot_be_forged_supported(self):
        for reference in REFERENCES:
            case = consent_case()
            answer = self.generate(case,reference)[0]['consent']
            forged = deepcopy(answer)
            forged.update(text='Verbal consent',value='Verbal consent',status='supported',review_reasons=[])
            with self.assertRaises(ValidationError):
                semantic.validate_stored_answer(case[0],case[1][0],case[2]['consent'],forged)
            forged['facts'][0]['issues'] = []
            forged['semantic_proof_sha256'] = semantic._fact_proof(forged)
            with self.assertRaises(ValidationError):
                semantic.validate_stored_answer(case[0],case[1][0],case[2]['consent'],forged)
            complete = consent_case(quote=COMPLETE)
            answer = self.generate(complete,reference)[0]['consent']
            answer.update(text='Verbal consent',value='Verbal consent')
            with self.assertRaises(ValidationError):
                semantic.validate_stored_answer(complete[0],complete[1][0],complete[2]['consent'],answer)

    def test_v9_inherits_v8_observation_holds_and_complete_values(self):
        for reference in REFERENCES:
            case = observation_case()
            self.assert_held(self.generate(case,reference)[0]['observation'])
            case = observation_case(quote='On video, the patient appears alert and comfortable')
            self.assertEqual(self.generate(case,reference)[0]['observation']['status'],'supported')
            for sep in ('—',';','／'):
                notes = 'On video'+sep+'the patient appears alert and comfortable.'
                self.assert_held(self.generate(observation_case(notes),reference)[0]['observation'])
            foreign = 'On video, the nurse appears alert and comfortable.'
            self.assert_held(self.generate(observation_case(foreign,foreign[:-1]),reference)[0]['observation'])

    def test_v9_inherits_all_titled_referral_variants(self):
        for title,reference in product(('Dr.','Dr','Doctor'),REFERENCES):
            with self.subTest(title=title,reference=reference):
                answers,_ = self.generate(referral_case(title=title),reference)
                self.assertTrue(all(a['status']=='supported' for a in answers.values()))
                self.assertEqual(answers['referrer']['text'],DOCTOR)
                self.assertEqual(answers['purpose']['text'],PURPOSE[:1].upper()+PURPOSE[1:])

    def test_many_heads_share_one_source_unit_without_quadratic_source_duplication(self):
        notes = 'The record mentions '+', '.join(['verbal consent']*100)+'.'
        rows = context.consent_qualifier_inventory(generation.source_units(notes,[])[0])
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['consent_heads']),100)
        self.assertFalse(rows[0]['recognized_complete_assertion'])

    def test_conjunctive_and_restricted_types_cannot_escape_their_consent_head(self):
        for prefix,reference in product(('verbal and informed','verbal or written',
                'verbal but limited','verbal, then written','verbal (informed)',
                'verbal and explicitly restricted'),REFERENCES):
            with self.subTest(prefix=prefix,reference=reference):
                notes = 'The patient gave '+prefix+' consent for this video consultation.'
                answer,sender = self.generate(consent_case(notes,'verbal'),reference)
                self.assert_held(answer['consent'])
                self.assertEqual(answer['consent']['independent_check']['verdict'],'pass')
                heads = sender.calls[0][2]['consent_qualifier_inventory'][0]['consent_heads']
                selected = span(notes,'verbal')
                self.assertTrue(any(head['start'] <= selected['start'] < selected['end'] <= head['end'] for head in heads))

    def test_linebreak_cannot_detach_a_type_from_its_unfinished_consent_assertion(self):
        for middle,reference in product(('verbal\n','VERBAL\r\n','Verbal\n\n',
                'verbal\nand informed\n','verbal\nand\ninformed\n'),REFERENCES):
            with self.subTest(middle=middle,reference=reference):
                notes = 'The patient gave '+middle+'consent for this video consultation.'
                quote = middle.split()[0]
                answer,sender = self.generate(consent_case(notes,quote),reference)
                self.assert_held(answer['consent'])
                rows = sender.calls[0][2]['consent_qualifier_inventory']
                self.assertTrue(rows[0]['continuation_sources'])
                for selected in (*rows[0]['consent_heads'],*rows[0]['continuation_sources']):
                    self.assertEqual(notes[selected['start']:selected['end']],selected['quote'])

    def test_completed_earlier_statement_does_not_share_a_later_consent_type(self):
        for reference in REFERENCES:
            notes = 'The patient is verbal.\n'+SOURCE
            case = consent_case(notes,'verbal',kind='finding')
            answer = self.generate(case,reference)[0]['consent']
            self.assertEqual(answer['status'],'supported')
            self.assertEqual(answer['text'],'Verbal')

    def test_postposed_consent_types_cannot_escape_their_unresolved_assertion(self):
        for phrase,reference in product(('consent (verbal)', 'consent, verbal,',
                'consent; verbal', 'consent that was verbal', 'consent (written)',
                'consent, oral,', 'consent that was informed'),REFERENCES):
            with self.subTest(phrase=phrase,reference=reference):
                notes = 'The patient gave '+phrase+' for this video consultation.'
                quote = next(word for word in ('verbal','written','oral','informed') if word in phrase)
                answer,sender = self.generate(consent_case(notes,quote),reference)
                self.assert_held(answer['consent'])
                self.assertEqual(answer['consent']['independent_check']['verdict'],'pass')
                row = sender.calls[0][2]['consent_qualifier_inventory'][0]
                self.assertFalse(row['recognized_complete_assertion'])
                self.assertIn({**span(notes,quote),'quote':quote},row['consent_heads'])

    def test_postposed_type_continuations_keep_their_exact_source_positions(self):
        for boundary,phrase,reference in product(('\n','\r\n','\n\n'),
                ('(verbal)', 'that was verbal', 'that was\nverbal', '(written)'),REFERENCES):
            with self.subTest(boundary=boundary,phrase=phrase,reference=reference):
                notes = 'The patient gave consent'+boundary+phrase+' for this video consultation.'
                quote = 'written' if 'written' in phrase else 'verbal'
                answer,sender = self.generate(consent_case(notes,quote),reference)
                self.assert_held(answer['consent'])
                row = sender.calls[0][2]['consent_qualifier_inventory'][0]
                self.assertTrue(row['continuation_sources'])
                for selected in (*row['consent_heads'],*row['continuation_sources']):
                    self.assertEqual(notes[selected['start']:selected['end']],selected['quote'])

    def test_completed_consent_does_not_claim_a_separate_later_verbal_finding(self):
        for source,reference in product((SOURCE+'\nThe patient is verbal.',
                SOURCE[:-1]+'\nThe patient feels well\nThe patient is verbal.'),REFERENCES):
            with self.subTest(source=source,reference=reference):
                case = consent_case(source,'verbal',occurrence=1,kind='finding')
                old = self.generate(case,reference,V8)[0]['consent']
                answer,sender = self.generate(case,reference)
                self.assertEqual(old['status'],'supported')
                self.assertEqual(answer['consent']['status'],'supported')
                self.assertEqual(answer['consent']['text'],'Verbal')
                self.assertEqual(sender.calls[0][2]['consent_qualifier_inventory'][0]['continuation_sources'],[])

    def test_abbreviation_periods_cannot_detach_consent_types(self):
        for phrase,reference in product(('consent (i.e. verbal)',
                'verbal (i.e. spoken) consent', 'consent, e.g. verbal,',
                'consent: type no. 1 verbal,', 'consent i.e.\nverbal',
                'verbal i.e.\nconsent', 'consent e.g.\nwritten'),REFERENCES):
            with self.subTest(phrase=phrase,reference=reference):
                notes = 'The patient gave '+phrase+' for this video consultation.'
                quote = 'written' if 'written' in phrase else 'verbal'
                self.assert_held(self.generate(consent_case(notes,quote),reference)[0]['consent'])

    def test_independently_bound_name_positions_are_not_consent_types_or_heads(self):
        for given,ending,reverse,space,reference in product(
                ('Consent','Verbal','Oral','Informed','Explicit'),('', '.'),(False,True),
                (' ','  ','\t','\u00a0'),REFERENCES):
            with self.subTest(given=given,ending=ending,reverse=reverse,space=space,reference=reference):
                name = 'Synthetic '+given+' Hale'
                observation = 'On'+space+'video, '+given+' appears alert and comfortable'
                consent = given+' gave '+COMPLETE
                statement = '\n'.join(value+ending for value in
                    ((observation,consent) if reverse else (consent,observation)))
                case = named_consent_case(observation,name=name,statement=statement,separator='\n')
                case[1][0]['label'] = 'Direct observation'
                case[2]['consent'].update(answer_mode='narrative',
                    meaning='The documented direct observation with its exact source modality.')
                old = self.generate(case,reference,V8)[0]['consent']
                answer = self.generate(case,reference)[0]['consent']
                self.assertEqual(old['status'],'supported')
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],old['text'])
                selected = next(value for value in answer['facts'] if value['id']=='consent')
                self.assertEqual(selected['value_evidence']['quote'],observation)
                clipped = named_consent_case(name=name,statement=statement,separator='\n')
                self.assert_held(self.generate(clipped,reference)[0]['consent'])

    def test_numbered_groups_and_abbreviated_type_labels_do_not_end_type_attachment(self):
        for (phrase,quote),reference in product((
                ('consent (1. Verbal)','Verbal'),
                ('verbal (1. Spoken) consent','verbal'),
                ('consent [1. Verbal]','Verbal'),
                ('consent {1. Verbal}','Verbal'),
                ('consent ((1. Spoken) 2. Verbal)','Verbal'),
                ('consent: no. 1 verbal','verbal'),
                ('consent, viz. Verbal,','Verbal'),
                ('consent:\n1. Verbal','Verbal')),REFERENCES):
            with self.subTest(phrase=phrase,reference=reference):
                notes = 'The patient gave '+phrase+' for this video consultation.'
                self.assert_held(self.generate(consent_case(notes,quote),reference)[0]['consent'])

    def test_subject_position_exemption_needs_independent_binding_and_does_not_follow_labels(self):
        for reference in REFERENCES:
            statement = 'On video, Consent appears alert and comfortable.'
            case = named_consent_case(statement[:-1],name='Synthetic Consent Hale',
                statement=statement,separator='\n')
            case[2]['consent']['answer_mode'] = 'narrative'
            case[3][:] = [value for value in case[3] if value['id']!='patient']
            self.assert_held(self.generate(case,reference)[0]['consent'])
            clipped = named_consent_case(name='Synthetic Consent Hale')
            value = next(value for value in clipped[3] if value['id']=='consent')
            value['kind'] = 'identity'
            value['subject']['name_span'] = deepcopy(value['value_span'])
            self.assert_held(self.generate(clipped,reference)[0]['consent'])

    def test_independently_bound_alias_is_case_insensitive_without_granting_new_ownership(self):
        for alias,reference in product(('Wren','wren','WREN'),REFERENCES):
            with self.subTest(alias=alias,reference=reference):
                statement = alias+' gave '+COMPLETE+'.'
                case = named_consent_case(COMPLETE,statement=statement,separator='\n')
                answer = self.generate(case,reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],COMPLETE[:1].upper()+COMPLETE[1:])
                clipped = named_consent_case(statement=statement,separator='\n')
                self.assert_held(self.generate(clipped,reference)[0]['consent'])
                foreign = named_consent_case(COMPLETE,statement='ellis gave '+COMPLETE+'.',separator='\n')
                self.assert_held(self.generate(foreign,reference)[0]['consent'])

    def test_source_bound_identity_tokens_are_names_at_their_exact_referral_positions(self):
        for name,referrer,reference in product(('Synthetic Consent Hale','Synthetic Verbal Consent'),
                                               ('Avery Lane','Consent Reed'),REFERENCES):
            with self.subTest(name=name,referrer=referrer,reference=reference):
                notes = name+' was referred by Dr. '+referrer+'.'
                case = consent_case(notes,name,kind='identity',name_quote=name)
                case[1][0]['label'] = 'Patient name'
                case[2]['consent'].update(value_type='person_name',meaning='The documented patient identity.')
                case[3][0]['timing']['kind'] = 'unspecified'
                case[3].append(fact(notes,case[1],'referrer',referrer,kind='identity',subject='other',
                    name_quote='Dr. '+referrer,timing='unspecified'))
                answer = self.generate(case,reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],name)
                case[4]['fields'][0]['fact_ids'] = ['referrer']
                case[2]['consent']['scope']['subject'] = 'other'
                answer = self.generate(case,reference)[0]['consent']
                self.assertEqual(answer['status'],'supported')
                self.assertEqual(answer['text'],referrer)

    def test_name_tokens_do_not_exempt_a_separately_positioned_consent_or_forged_identity(self):
        for reference in REFERENCES:
            case = named_consent_case(COMPLETE,name='Synthetic Consent Hale')
            answer = self.generate(case,reference)[0]['consent']
            self.assertEqual(answer['status'],'supported')
            for kind in ('other','identity'):
                clipped = named_consent_case(name='Synthetic Consent Hale')
                value = next(f for f in clipped[3] if f['id']=='consent')
                value['kind'] = kind
                self.assert_held(self.generate(clipped,reference)[0]['consent'])
                value['subject']['name_span'] = deepcopy(value['value_span'])
                self.assert_held(self.generate(clipped,reference)[0]['consent'])
            spoof = consent_case(kind='identity',name_quote=CLIPPED)
            self.assert_held(self.generate(spoof,reference)[0]['consent'])

    def test_unfinished_type_evidence_is_not_duplicated_across_every_later_consent_unit(self):
        notes = 'The patient gave verbal\n'+'\n'.join(['consent']*100)
        rows = context.consent_qualifier_inventory(generation.source_units(notes,[])[0])
        self.assertEqual(len(rows),100)
        self.assertEqual(sum(len(row['continuation_sources']) for row in rows),1)

    def test_complete_unpunctuated_prior_frames_do_not_become_type_continuations(self):
        for reference in REFERENCES:
            generic = consent_case('The patient reports intermittent nausea\n'+SOURCE,COMPLETE)
            named = named_consent_case(COMPLETE,separator='\n')
            n,f,d,values,selected = named
            n = n.replace('.\n','\n',1)
            named = consent_case(n,COMPLETE,name_quote='Synthetic Wren Bell')
            named[3][:0] = [fact(n,named[1],'patient','Synthetic Wren Bell',kind='identity',
                name_quote='Synthetic Wren Bell',timing='unspecified'),
                fact(n,named[1],'referrer','Avery Lane',kind='identity',subject='other',
                name_quote='Dr. Avery Lane',timing='unspecified')]
            for case in (generic,named):
                old = self.generate(case,reference,V8)[0]['consent']
                answer,sender = self.generate(case,reference)
                self.assertEqual(old['status'],'supported')
                self.assertEqual(answer['consent']['status'],'supported')
                self.assertEqual(answer['consent']['text'],old['text'])
                self.assertEqual(sender.calls[0][2]['consent_qualifier_inventory'][-1]['continuation_sources'],[])
