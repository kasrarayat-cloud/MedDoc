"""Prospective source attribution with literal negatives and frozen old replays.

Every provider response is a local fixture. A passing checker deliberately
cannot discharge the source ownership, polarity or evidence guards exercised
here.
"""
from copy import deepcopy
import hashlib
import json

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation
from core import semantic_generation as semantic
from core.tests.test_semantic_generation import FixtureSender, assignments, fact
from documents.semantic_preparation_roles import default_definitions


PATIENT = 'Synthetic Rowan Vale'
DOCTOR = 'Dr. Synthetic Avery Cole'
REFERRAL = PATIENT + ' is 47 years old and was referred by ' + DOCTOR + '. '
OLD_PROFILES = (
    semantic.LEGACY_SCOPE_CONTRACT,
    semantic.POSITIONED_SCOPE_CONTRACT,
    semantic.DURATION_SCOPE_CONTRACT,
    semantic.FAMILY_SCOPE_CONTRACT,
)
REFERENCES = (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT)
# Captured with the exact semantic source at base commit 053a156f23bf568b069f75e828f6f7773f647a7f
# (source SHA256 4a21bdb2150929720e16ea0d1564cbdcd5446b1b459cc65da8e1a405760cd442).
# Each digest covers five complete retained answers AND all three provider
# request payloads/schemas/instructions, in the reference-contract order above.
HISTORICAL_REPLAY_SHA256 = {
    'note-wide-offer-scope-v1': (
        '9f5213576e39af2ef1bb44d932f76518eb20c6583c682d6366a37802bea5b4c4',
        'caf1f01ba7d61735ce703e079f7ba9137e2c3c33316ff831d9a289e7c097d6db'),
    'positioned-fact-scope-v2': (
        'bebf86d894f292fc42d689e487959e3abd86ec679c7a20418fee90f8a65ddfb8',
        '16d7e0a9440519cffdc6c257b672091e04191dc49992cb9ebbcf5131bb224e27'),
    'dimension-aware-duration-scope-v3': (
        'd9036c1e864ef99cb8e51acf2a0d8a338c7de83aa1e9f4f676e97b8b6234cca2',
        '161e69d1abd0747c415fcefb91f6ff99504c6fc8c591f176090cc7fb07cc26cd'),
    'positioned-family-context-v4': (
        'c91226c963640e1851045f39b0fa48047cd82eff747d8e5493394e688f61f7ce',
        '157a0f5627dedddf03808cd0e48ab9c13c6084905daefb79df19938c5bf05a23'),
}


class SourceContextAttributionTests(SimpleTestCase):
    def prepare(self, notes, quote, *, label='Findings', name=None,
                other_name=None, other_kind='other', polarity='affirmed', kind='finding',
                answer_mode='atomic'):
        fields = [{'key': 'answer', 'label': label, 'kind': 'text', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        definitions['answer'].update(version=2, answer_mode=answer_mode)
        definitions['answer']['scope'].update(subject='patient', temporality='any', polarity='any')
        values = []
        if name:
            values.append(fact(notes, fields, 'identity', name, kind='identity',
                               name_quote=name, timing='unspecified'))
        if other_name:
            values.append(fact(notes, fields, 'other_person', other_name, kind=other_kind,
                               subject='other', name_quote=other_name, timing='unspecified'))
        if quote is not None:
            clinical = fact(notes, fields, 'clinical', quote, kind=kind,
                            name_quote=name, polarity=polarity)
            # A separately cited patient identity supplies the name, not a
            # blanket interpretation of every clinical statement that follows.
            if name:
                units = generation.source_units(notes, fields)[0]
                named = clinical['subject']['name_span']
                name_unit = next(unit['id'] for unit in units
                                 if unit['start'] <= named['start'] < named['end'] <= unit['end'])
                clinical['source_unit_ids'] = sorted(set(clinical['source_unit_ids'] + [name_unit]))
            values.append(clinical)
        selected = assignments(fields, {'answer': ['clinical']} if quote is not None else {})
        return fields, definitions, values, selected

    def generate(self, notes, quote, *, profile=None, reference=None, **kwargs):
        profile = semantic.SOURCE_CONTEXT_SCOPE_CONTRACT if profile is None else profile
        reference = semantic.REFERENCE_INVENTORY_CONTRACT if reference is None else reference
        fields, definitions, values, selected = self.prepare(notes, quote, **kwargs)
        original = deepcopy(values)
        sender = FixtureSender(values, selected)
        answers = semantic.run(notes, fields, definitions, sender,
                               scope_contract=profile, reference_contract=reference)
        answer = answers['answer']
        self.assertEqual(values, original)
        self.assertEqual([call[:2] for call in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1)])
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
        return answer, sender, fields, definitions

    def assert_held(self, answer):
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['text'], '')
        self.assertFalse(answer['reviewed'])
        self.assertTrue(answer['review_reasons'])

    def run_inventory(self, notes, fields, definitions, values, selected, reference):
        original = deepcopy(values)
        sender = FixtureSender(values, selected)
        answer = semantic.run(notes, fields, definitions, sender,
            scope_contract=semantic.SOURCE_CONTEXT_SCOPE_CONTRACT,
            reference_contract=reference)['answer']
        self.assertEqual(values, original)
        self.assertEqual([call[:2] for call in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1)])
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
        return answer

    def test_referring_doctor_in_identity_citation_does_not_own_later_patient_statement(self):
        notes = REFERRAL + 'The patient reports normal bowel movements.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, sender, _, _ = self.generate(notes, 'normal bowel movements',
                    name=PATIENT, other_name=DOCTOR, other_kind='identity', reference=reference)
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', 'Normal bowel movements'))
                self.assertEqual(answer['fact_scope_contract'], 'positioned-source-context-v5')
                for call in sender.calls:
                    self.assertEqual(call[2]['fact_scope_contract'], semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)
                retained = next(value for value in answer['facts'] if value['id'] == 'clinical')
                self.assertEqual(retained['subject']['name_evidence']['quote'], PATIENT)
                self.assertTrue(any(DOCTOR in value['quote'] for value in retained['evidence']))

    def test_source_bound_referring_role_allows_a_distinct_implicit_exam_statement(self):
        notes = REFERRAL + 'Bowel sounds were normal.'
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, _, _, _ = self.generate(notes, 'normal', label='Bowel sounds',
                    name=PATIENT, other_name=DOCTOR, other_kind='identity', reference=reference)
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Normal'))

    def test_referrer_identity_may_exclude_the_title_retained_in_source(self):
        name = 'Synthetic Avery Cole'
        for title in ('Dr.', 'Doctor'):
            notes = PATIENT + ' was referred by ' + title + ' ' + name + '. Bowel sounds were normal.'
            for reference in REFERENCES:
                with self.subTest(title=title, reference=reference):
                    answer, _, _, _ = self.generate(notes, 'normal', label='Bowel sounds',
                        name=PATIENT, other_name=name, other_kind='identity', reference=reference)
                    self.assertEqual((answer['status'], answer['text']), ('supported', 'Normal'))
                    retained = next(value for value in answer['facts'] if value['id'] == 'other_person')
                    self.assertEqual(retained['value_evidence']['quote'], name)
                    self.assertTrue(any(title + ' ' + name in value['quote'] for value in retained['evidence']))

    def test_recorded_relative_past_diagnosis_does_not_own_later_patient_exam(self):
        notes = (REFERRAL + "The patient's mother had colon polyps diagnosed at age 68. "
                 'Bowel sounds were normal.')
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, _, _, _ = self.generate(notes, 'normal', label='Bowel sounds',
                    name=PATIENT, other_name=DOCTOR, other_kind='identity', reference=reference)
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Normal'))
                self.assertNotIn('colon polyps', answer['text'])

    def test_relative_past_diagnosis_does_not_clear_companion_or_pronoun_ownership(self):
        for history, statement, quote in (
                ("The patient's mother had colon polyps diagnosed at age 68. ",
                 'She reports wheezing.', 'wheezing'),
                ("The patient's mother had colon polyps diagnosed at age 68. "
                 "The patient's mother sat beside him. ", 'Breathing was clear.', 'clear'),
                ("The patient's mother had accompanied him and had colon polyps diagnosed at age 68. ",
                 'Breathing was clear.', 'clear'),
                ("The doctor's mother had colon polyps diagnosed at age 68. ",
                 'Breathing was clear.', 'clear')):
            for reference in REFERENCES:
                with self.subTest(history=history, statement=statement, reference=reference):
                    answer, _, _, _ = self.generate(REFERRAL + history + statement, quote,
                        name=PATIENT, other_name=DOCTOR, other_kind='identity', reference=reference)
                    self.assert_held(answer)

    def test_nonidentity_other_fact_does_not_authorize_implicit_patient_attribution(self):
        answer, _, _, _ = self.generate(REFERRAL + 'Bowel sounds were normal.', 'normal',
            label='Bowel sounds', name=PATIENT, other_name=DOCTOR, other_kind='other')
        self.assert_held(answer)

    def test_referral_requires_independently_extracted_patient_and_referrer_identities(self):
        notes = REFERRAL + 'The patient reports normal bowel movements.'
        fields, definitions, values, selected = self.prepare(notes, 'normal bowel movements',
            name=PATIENT, other_name=DOCTOR, other_kind='identity')
        # A name attached to a clinical claim is not a separately evidenced
        # identity. Likewise, source wording alone cannot replace the missing
        # referrer fact when choosing which person owns later statements.
        for omitted in ({'identity'}, {'other_person'}, {'identity', 'other_person'}):
            inventory = [value for value in values if value['id'] not in omitted]
            for reference in REFERENCES:
                with self.subTest(omitted=sorted(omitted), reference=reference):
                    answer = self.run_inventory(notes, fields, definitions, inventory, selected, reference)
                    self.assert_held(answer)

    def test_unnamed_patient_fact_still_needs_bound_identities_and_continuous_ownership(self):
        for interruption in ('', 'A visitor entered the room. '):
            notes = REFERRAL + interruption + 'Bowel sounds were normal.'
            fields, definitions, values, selected = self.prepare(notes, 'normal',
                label='Bowel sounds', name=PATIENT, other_name=DOCTOR, other_kind='identity')
            clinical = next(value for value in values if value['id'] == 'clinical')
            clinical['subject']['name_span'] = None
            units = generation.source_units(notes, fields)[0]
            clinical['source_unit_ids'] = [unit['id'] for unit in units
                if unit['start'] <= clinical['value_span']['start']
                < clinical['value_span']['end'] <= unit['end']]
            for omitted in (set(), {'identity'}, {'other_person'}, {'identity', 'other_person'}):
                inventory = [value for value in values if value['id'] not in omitted]
                for reference in REFERENCES:
                    with self.subTest(interruption=interruption, omitted=sorted(omitted), reference=reference):
                        answer = self.run_inventory(notes, fields, definitions, inventory, selected, reference)
                        if not interruption and not omitted:
                            self.assertEqual((answer['status'], answer['text']), ('supported', 'Normal'))
                        else:
                            self.assert_held(answer)
                        retained = next(value for value in answer['facts'] if value['id'] == 'clinical')
                        self.assertIsNone(retained['subject']['name_evidence'])

    def test_omitted_initial_foreign_subject_cannot_be_replaced_by_later_patient_identity(self):
        for introduction in ('Synthetic Nolan Reed attended the clinic. ',
                             'NOLAN REED entered the room. ',
                             'Another patient attended first. '):
            notes = introduction + REFERRAL + 'Bowel sounds were normal.'
            fields, definitions, values, selected = self.prepare(notes, 'normal',
                label='Bowel sounds', name=PATIENT, other_name=DOCTOR, other_kind='identity')
            for unnamed in (False, True):
                inventory = deepcopy(values)
                if unnamed:
                    next(value for value in inventory if value['id'] == 'clinical')['subject']['name_span'] = None
                for reference in REFERENCES:
                    with self.subTest(introduction=introduction, unnamed=unnamed, reference=reference):
                        # No fact represents the first person. The source order
                        # still prevents the later identity from claiming the encounter.
                        answer = self.run_inventory(notes, fields, definitions, inventory, selected, reference)
                        self.assert_held(answer)

    def test_unrelated_clinician_or_companion_does_not_resolve_an_implicit_subject(self):
        for introduction in (
                PATIENT + ' attended with his brother, ' + DOCTOR + '. ',
                PATIENT + ' spoke with ' + DOCTOR + '. ',
                PATIENT + ' referred ' + DOCTOR + ' to the clinic. ',
                PATIENT + ' was not referred by ' + DOCTOR + '. ',
                DOCTOR + ' was referred by ' + PATIENT + '. '):
            for statement, quote in (('He reports wheezing.', 'wheezing'),
                                     ('Breathing was clear.', 'clear')):
                with self.subTest(introduction=introduction, statement=statement):
                    answer, _, _, _ = self.generate(introduction + statement, quote,
                        name=PATIENT, other_name=DOCTOR, other_kind='identity')
                    self.assert_held(answer)

    def test_patient_name_inside_a_referred_relatives_identity_does_not_establish_patient(self):
        notes = 'The brother of ' + PATIENT + ' was referred by ' + DOCTOR + '. Bowel sounds were normal.'
        answer, _, _, _ = self.generate(notes, 'normal', label='Bowel sounds',
            name=PATIENT, other_name=DOCTOR, other_kind='identity')
        self.assert_held(answer)

    def test_intervening_named_companion_leaves_later_pronoun_unresolved(self):
        notes = (REFERRAL + "The patient's brother, Synthetic Nolan Reed, joined him. "
                 'He reports wheezing.')
        fields, definitions, values, selected = self.prepare(notes, 'wheezing',
            name=PATIENT, other_name=DOCTOR, other_kind='identity')
        companion = fact(notes, fields, 'companion', 'Synthetic Nolan Reed', kind='identity',
                         subject='other', name_quote='Synthetic Nolan Reed', timing='unspecified')
        for extracted_companion in (False, True):
            for reference in REFERENCES:
                with self.subTest(reference=reference, extracted_companion=extracted_companion):
                    inventory = values + ([companion] if extracted_companion else [])
                    sender = FixtureSender(inventory, selected)
                    answer = semantic.run(notes, fields, definitions, sender,
                        scope_contract=semantic.SOURCE_CONTEXT_SCOPE_CONTRACT,
                        reference_contract=reference)['answer']
                    semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
                    self.assert_held(answer)

    def test_generic_patient_reference_does_not_resolve_intervening_companion_context(self):
        notes = (REFERRAL + "The patient's brother, Synthetic Nolan Reed, joined him. "
                 'The patient reports wheezing.')
        answer, _, _, _ = self.generate(notes, 'wheezing', name=PATIENT, other_name=DOCTOR,
                                       other_kind='identity')
        self.assert_held(answer)

    def test_full_patient_name_does_not_resolve_intervening_companion_context(self):
        notes = (REFERRAL + "The patient's brother, Synthetic Nolan Reed, joined him. "
                 + PATIENT + ' reports wheezing.')
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, _, _, _ = self.generate(notes, 'wheezing', name=PATIENT,
                    other_name=DOCTOR, other_kind='identity', reference=reference)
                self.assert_held(answer)

    def test_explicit_same_statement_referral_purpose_retains_patient_ownership(self):
        purpose = 'gastroenterology visit to review previous GI records'
        notes = REFERRAL.rstrip('. ') + ' for an in-person ' + purpose + '.'
        for quote, label, mode, kind in (('in-person', 'Visit format', 'atomic', 'other'),
                                         ('in-person ' + purpose, 'Visit purpose', 'narrative', 'reason'),
                                         ('to review previous GI records', 'HPI', 'narrative', 'reason')):
            with self.subTest(label=label):
                answer, _, _, _ = self.generate(notes, quote, label=label, kind=kind,
                    name=PATIENT, other_name=DOCTOR, other_kind='identity', answer_mode=mode)
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', quote[:1].upper() + quote[1:]))
        answer, _, _, _ = self.generate(notes, purpose, label='Visit purpose', kind='reason',
            name=PATIENT, other_name=DOCTOR, other_kind='identity', answer_mode='narrative')
        self.assert_held(answer)

    def test_same_statement_referral_purpose_cannot_transfer_other_ownership(self):
        purpose = 'gastroenterology visit to review previous GI records'
        for prefix in (
                PATIENT + ' was not referred by ' + DOCTOR + ' for an ',
                DOCTOR + ' was referred by ' + PATIENT + ' for an ',
                PATIENT + ' was referred by ' + DOCTOR + ', who arranged his own ',
                PATIENT + ' was referred by ' + DOCTOR + " for his brother's ",
                PATIENT + ' was referred by ' + DOCTOR + " for the doctor's own ",
                PATIENT + ' was possibly referred by ' + DOCTOR + ' for an ',
                'If ' + PATIENT + ' was referred by ' + DOCTOR + ' for an ',
                '"' + PATIENT + ' was referred by ' + DOCTOR + ' for an '):
            notes = prefix + 'in-person ' + purpose + '.'
            if prefix.startswith('"'):
                notes += '"'
            for quote, mode in (('in-person', 'atomic'), (purpose, 'narrative'),
                                ('to review previous GI records', 'narrative')):
                with self.subTest(prefix=prefix, quote=quote):
                    answer, _, _, _ = self.generate(notes, quote, label='Visit purpose', kind='other',
                        name=PATIENT, other_name=DOCTOR, other_kind='identity', answer_mode=mode)
                    self.assert_held(answer)

    def test_same_statement_named_other_person_stays_held(self):
        notes = PATIENT + ' listened as ' + DOCTOR + ' described wheezing.'
        answer, _, _, _ = self.generate(notes, 'wheezing', name=PATIENT, other_name=DOCTOR,
                                       other_kind='identity')
        self.assert_held(answer)
        self.assertIn('Another named subject occurs before this value; attribution needs review.',
                      answer['review_reasons'])

    def test_referring_role_does_not_clear_a_later_physician_owned_finding(self):
        notes = REFERRAL + DOCTOR + ' reports wheezing.'
        answer, _, _, _ = self.generate(notes, 'wheezing', name=PATIENT, other_name=DOCTOR,
                                       other_kind='identity')
        self.assert_held(answer)

    def test_explicit_companion_ownership_still_refuses_before_assignment(self):
        notes = ("The patient's brother, Synthetic Avery Cole, discussed the patient "
                 'and attended a review visit himself.')
        fields, definitions, values, selected = self.prepare(notes, 'review', label='Visit category')
        sender = FixtureSender(values, selected)
        with self.assertRaisesMessage(ValidationError, 'Person attribution needs review:'):
            semantic.run(notes, fields, definitions, sender,
                         scope_contract=semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)
        self.assertEqual([call[:2] for call in sender.calls], [('extractor', 1)])

    def test_hypothesis_and_denial_govern_their_own_patient_statement(self):
        for statement in ('If the patient had wheezing, further review would be needed.',
                          'The patient denies wheezing.',
                          'The following findings are denied:\nThe patient reports wheezing.'):
            with self.subTest(statement=statement):
                answer, _, _, _ = self.generate(REFERRAL + statement, 'wheezing',
                    name=PATIENT, other_name=DOCTOR)
                self.assert_held(answer)

    def test_complete_literal_negative_phrases_are_supported_without_rewriting(self):
        for phrase in ('never used tobacco', 'does not drink alcohol',
                       'does not use recreational drugs', 'in no acute distress'):
            notes = 'The patient is ' + phrase + '.' if phrase.startswith('in ') else 'The patient ' + phrase + '.'
            for reference in REFERENCES:
                with self.subTest(phrase=phrase, reference=reference):
                    answer, _, _, _ = self.generate(notes, phrase, polarity='negated', reference=reference)
                    self.assertEqual((answer['status'], answer['text']),
                                     ('supported', phrase[:1].upper() + phrase[1:]))
                    clinical = next(value for value in answer['facts'] if value['id'] == 'clinical')
                    self.assertEqual(clinical['value_evidence']['quote'], phrase)
                    self.assertEqual(clinical['polarity'], 'negated')

    def test_negative_annotations_cannot_supply_missing_negative_words(self):
        for statement, quote in (
                ('The patient never used tobacco.', 'tobacco'),
                ('The patient does not drink alcohol.', 'alcohol'),
                ('The patient does not use recreational drugs.', 'recreational drugs'),
                ('The patient is in no acute distress.', 'acute distress'),
                ('The patient denies fever and cough.', 'cough')):
            with self.subTest(statement=statement):
                answer, _, _, _ = self.generate(statement, quote, polarity='negated')
                self.assert_held(answer)
                self.assertIn('The negative answer must retain its documented negative phrase; an annotation cannot synthesize absence.',
                              answer['review_reasons'])

    def test_literal_negative_phrases_cannot_be_mislabelled_affirmed(self):
        for phrase in ('never used tobacco', 'does not drink alcohol',
                       'does not use recreational drugs', 'in no acute distress'):
            notes = 'The patient is ' + phrase + '.' if phrase.startswith('in ') else 'The patient ' + phrase + '.'
            with self.subTest(phrase=phrase):
                answer, _, _, _ = self.generate(notes, phrase, polarity='affirmed')
                self.assert_held(answer)

    def test_finite_non_prefix_findings_preserve_literal_negative_values(self):
        for phrase in ('non-tender', 'non-distended', 'non tender', 'non distended'):
            notes = 'The abdomen was ' + phrase + '.'
            with self.subTest(phrase=phrase):
                answer, _, _, _ = self.generate(notes, phrase, polarity='negated')
                self.assertEqual((answer['status'], answer['text']),
                                 ('supported', phrase[:1].upper() + phrase[1:]))
                clinical = next(value for value in answer['facts'] if value['id'] == 'clinical')
                self.assertEqual(clinical['value_evidence']['quote'], phrase)
                self.assertEqual(clinical['polarity'], 'negated')
                wrong, _, _, _ = self.generate(notes, phrase, polarity='affirmed')
                self.assert_held(wrong)

    def test_non_prefix_annotations_cannot_supply_generic_or_clipped_absence(self):
        for notes, quote in (('The abdomen was non-tender.', 'tender'),
                             ('The abdomen was non-distended.', 'distended'),
                             ('The patient is a non-smoker.', 'non-smoker'),
                             ('The patient is nonverbal.', 'nonverbal')):
            with self.subTest(notes=notes, quote=quote):
                answer, _, _, _ = self.generate(notes, quote, polarity='negated')
                self.assert_held(answer)

    def test_new_subject_and_predicate_end_negation_but_a_shared_list_does_not(self):
        notes = 'There was no scleral icterus and the oropharynx was clear.'
        answer, _, _, _ = self.generate(notes, 'clear', label='Oropharynx')
        self.assertEqual((answer['status'], answer['text']), ('supported', 'Clear'))
        answer, _, _, _ = self.generate(notes, 'oropharynx was clear', answer_mode='narrative')
        self.assertEqual((answer['status'], answer['text']), ('supported', 'Oropharynx was clear'))
        for polarity in ('affirmed', 'negated'):
            with self.subTest(shared_predicate_polarity=polarity):
                answer, _, _, _ = self.generate('The patient denies fever and cough.', 'cough', polarity=polarity)
                self.assert_held(answer)
        answer, _, _, _ = self.generate('The patient denies fever and cough.',
                                      'denies fever and cough', polarity='negated')
        self.assertEqual((answer['status'], answer['text']), ('supported', 'Denies fever and cough'))

    def test_negated_denial_and_hypothetical_complete_phrase_do_not_assert_absence(self):
        for statement, quote in (
                ('The patient does not deny fever.', 'does not deny fever'),
                ('The patient says they never deny fever.', 'never deny fever'),
                ('The patient never denies fever.', 'never denies fever'),
                ('The patient is never without pain.', 'never without pain'),
                ('The patient is not without pain.', 'not without pain'),
                ('If the patient never used tobacco, this risk would be lower.', 'never used tobacco')):
            with self.subTest(statement=statement):
                answer, _, _, _ = self.generate(statement, quote, polarity='negated')
                self.assert_held(answer)

    def test_missing_social_history_stays_missing_and_cannot_synthesize_a_negative(self):
        answer, _, _, _ = self.generate('The patient attended today.', None, label='Tobacco use')
        self.assertEqual((answer['status'], answer['text']), ('missing', ''))
        self.assertEqual(answer['fact_ids'], [])

    def test_supported_v5_proof_cannot_be_downgraded_or_have_negative_words_removed(self):
        notes = 'The patient never used tobacco.'
        answer, _, fields, definitions = self.generate(notes, 'never used tobacco', polarity='negated')
        for profile in (*OLD_PROFILES, None, 'unrecognized-source-scope'):
            changed = deepcopy(answer)
            if profile is None:
                changed.pop('fact_scope_contract')
            else:
                changed['fact_scope_contract'] = profile
            with self.subTest(profile=profile), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], changed)
        changed = deepcopy(answer)
        changed.update(text='Tobacco', value='Tobacco')
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(notes, fields[0], definitions['answer'], changed)

    def test_mixed_family_assessment_with_wrong_polarity_remains_held(self):
        phrase = 'no current gastrointestinal symptoms and a family history of colon polyps'
        notes = PATIENT + " attended today. The clinician's impression was " + phrase + '.'
        answer, _, _, _ = self.generate(notes, phrase, label='Impression', kind='assessment', polarity='affirmed')
        self.assert_held(answer)

    def split_impression(self, notes, *, family_quote='family history of colon polyps'):
        fields, definitions, _, _ = self.prepare(notes, None, label='Impression')
        definitions['answer']['answer_mode'] = 'narrative'
        values = [fact(notes, fields, 'symptoms', 'no current gastrointestinal symptoms',
                       kind='assessment', polarity='negated'),
                  fact(notes, fields, 'family', family_quote, kind='assessment')]
        selected = assignments(fields, {'answer': ['symptoms', 'family']})
        sender = FixtureSender(values, selected)
        answer = semantic.run(notes, fields, definitions, sender,
                              scope_contract=semantic.SOURCE_CONTEXT_SCOPE_CONTRACT)['answer']
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
        self.assertEqual(len(sender.calls), 3)
        return answer

    def test_split_reported_impression_remains_held_with_both_original_facts_retained(self):
        notes = ("The clinician's impression was no current gastrointestinal symptoms "
                 'and a family history of colon polyps.')
        answer = self.split_impression(notes)
        self.assert_held(answer)
        retained = {value['id']: value for value in answer['facts']}
        self.assertEqual(retained['symptoms']['polarity'], 'negated')
        self.assertEqual(retained['symptoms']['value_evidence']['quote'], 'no current gastrointestinal symptoms')
        self.assertEqual(retained['family']['polarity'], 'affirmed')
        self.assertEqual(retained['family']['value_evidence']['quote'], 'family history of colon polyps')

    def test_split_impression_cannot_erase_governance_ownership_or_family_qualifications(self):
        phrase = 'no current gastrointestinal symptoms and a family history of colon polyps'
        for notes in (
                '"The clinician\'s impression was ' + phrase + '."',
                "If the clinician's impression was " + phrase + ', review would be needed.',
                "The clinician's impression was not " + phrase + '.',
                "The clinician's impression was no current gastrointestinal symptoms "
                "and the clinician's own family history of colon polyps.",
                "The clinician's impression was " + phrase + ' that remains unconfirmed.'):
            with self.subTest(notes=notes):
                self.assert_held(self.split_impression(notes))
        with self.subTest(clipped_relationship=True):
            self.assert_held(self.split_impression("The clinician's impression was " + phrase + '.',
                                                  family_quote='colon polyps'))

    def test_unknown_profile_refuses_before_any_provider_fixture(self):
        fields, definitions, values, selected = self.prepare('The patient reports wheezing.', 'wheezing')
        sender = FixtureSender(values, selected)
        with self.assertRaises(ValidationError):
            semantic.run('The patient reports wheezing.', fields, definitions, sender,
                         scope_contract='positioned-source-context-v500')
        self.assertEqual(sender.calls, [])

    def test_shared_evidence_knowledge_or_confirmation_scope_does_not_affirm_family_history(self):
        for qualification in ('no evidence of', 'no knowledge of', 'no confirmation of',
                              'without evidence of', 'no evidence of both'):
            notes = ("The clinician's impression was " + qualification
                     + ' gastrointestinal symptoms and a family history of colon polyps.')
            for reference in REFERENCES:
                with self.subTest(qualification=qualification, reference=reference):
                    answer, _, _, _ = self.generate(notes, 'family history of colon polyps',
                        label='Family history', kind='assessment', reference=reference)
                    self.assert_held(answer)

    def test_unextracted_companion_does_not_assign_later_pronoun_or_exam_to_patient(self):
        for intervening in ("The patient's brother, Synthetic Nolan Reed, sat beside him. ",
                            'His colleague, Synthetic Nolan Reed, joined him. ',
                            'Synthetic Nolan Reed accompanied him. '):
            for statement, quote in (('He reports wheezing.', 'wheezing'),
                                     ('Breathing was clear.', 'clear')):
                for reference in REFERENCES:
                    with self.subTest(intervening=intervening, statement=statement, reference=reference):
                        # The source names the companion, but no companion
                        # fact is supplied. Extraction is not an exhaustive
                        # inventory of every possible owner in the notes.
                        answer, _, _, _ = self.generate(REFERRAL + intervening + statement, quote,
                            name=PATIENT, other_name=DOCTOR, other_kind='identity', reference=reference)
                        self.assert_held(answer)

    def test_patient_reporter_does_not_own_embedded_doctor_nurse_or_named_person_findings(self):
        for statement in ("The patient reports his doctor's wheezing.",
                          "The patient reports the nurse's wheezing.",
                          'The patient reports that his doctor has wheezing.',
                          'The patient reports that Synthetic Nolan Reed has wheezing.'):
            for reference in REFERENCES:
                with self.subTest(statement=statement, reference=reference):
                    answer, _, _, _ = self.generate(REFERRAL + statement, 'wheezing',
                        name=PATIENT, other_name=DOCTOR, other_kind='identity', reference=reference)
                    self.assert_held(answer)

    def test_referrer_short_name_or_reported_foreign_owner_cannot_become_the_patient(self):
        for statement in ('Avery reports wheezing.',
                          'AVERY reports wheezing.',
                          'The patient reports that Avery has wheezing.',
                          'The patient reports that AVERY has wheezing.',
                          'The patient reports that a visitor has wheezing.'):
            for reference in REFERENCES:
                with self.subTest(statement=statement, reference=reference):
                    answer, _, _, _ = self.generate(REFERRAL + statement, 'wheezing',
                        name=PATIENT, other_name=DOCTOR, other_kind='identity', reference=reference)
                    self.assert_held(answer)

    def test_unrecognized_person_or_unit_closes_ownership_even_when_no_person_fact_is_extracted(self):
        for interruption in ('NOLAN REED entered the room. ',
                             'nolan reed entered the room. ',
                             'N. Reed entered the room. ',
                             'A visitor entered the room. ',
                             'Another patient entered the room. ',
                             'The note continued with an unfamiliar observation. '):
            for reference in REFERENCES:
                with self.subTest(interruption=interruption, reference=reference):
                    answer, _, _, _ = self.generate(REFERRAL + interruption + 'Breathing was clear.',
                        'clear', label='Breathing', name=PATIENT, other_name=DOCTOR,
                        other_kind='identity', reference=reference)
                    self.assert_held(answer)

    def test_short_name_preserves_known_patient_but_does_not_reset_unknown_scope(self):
        for interruption in ('', 'Another patient entered the room. '):
            for subject in ('Rowan', 'The patient'):
                notes = REFERRAL + interruption + subject + ' reports wheezing. Breathing was clear.'
                for quote, label in (('wheezing', 'Symptoms'), ('clear', 'Breathing')):
                    for reference in REFERENCES:
                        with self.subTest(interruption=interruption, subject=subject, quote=quote, reference=reference):
                            answer, _, _, _ = self.generate(notes, quote, label=label, name=PATIENT,
                                other_name=DOCTOR, other_kind='identity', reference=reference)
                            if interruption:
                                self.assert_held(answer)
                            else:
                                self.assertEqual((answer['status'], answer['text']),
                                                 ('supported', quote.capitalize()))

    def test_full_name_repetition_does_not_restore_scope_after_an_unknown_person(self):
        notes = (REFERRAL + 'Another patient entered the room. ' + PATIENT
                 + ' currently feels well. Breathing was clear.')
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                answer, _, _, _ = self.generate(notes, 'clear', label='Breathing', name=PATIENT,
                    other_name=DOCTOR, other_kind='identity', reference=reference)
                self.assert_held(answer)

    def test_duplicate_full_name_cannot_resolve_which_patient_owns_a_later_finding(self):
        notes = (REFERRAL + 'Another patient has the same full name, ' + PATIENT
                 + '. ' + PATIENT + ' reports wheezing.')
        for reference in REFERENCES:
            with self.subTest(reference=reference):
                # The other patient is deliberately absent from the inventory.
                # Repeating the target's full name cannot disambiguate the source.
                answer, _, _, _ = self.generate(notes, 'wheezing', name=PATIENT,
                    other_name=DOCTOR, other_kind='identity', reference=reference)
                self.assert_held(answer)

    def test_recognized_clinical_words_cannot_hide_an_unparsed_owner_clause(self):
        for statement in ('The patient currently feels well and Avery entered the room. ',
                          'Past medical history includes asthma and Avery entered the room. ',
                          'The neck was supple for Avery. ',
                          'The plan is follow-up in six weeks and Avery entered the room. ',
                          'The total encounter time was 25 minutes, including Avery examining another patient. '):
            for reference in REFERENCES:
                with self.subTest(statement=statement, reference=reference):
                    answer, _, _, _ = self.generate(REFERRAL + statement + 'Breathing was clear.',
                        'clear', label='Breathing', name=PATIENT, other_name=DOCTOR,
                        other_kind='identity', reference=reference)
                    self.assert_held(answer)

    def test_sentential_uncertainty_and_denied_complement_survive_a_new_local_subject(self):
        for notes in ('It is possible that the abdomen is tender and the chest is clear.',
                      'The patient denies that the abdomen is tender and the chest is clear.'):
            for reference in REFERENCES:
                with self.subTest(notes=notes, reference=reference):
                    answer, _, _, _ = self.generate(notes, 'clear', label='Chest', reference=reference)
                    self.assert_held(answer)

    def test_uncertain_or_not_only_negative_phrase_does_not_assert_absence(self):
        for notes, quote in (('The patient perhaps never used tobacco.', 'never used tobacco'),
                             ('The patient has not only fever but also cough.', 'not only fever')):
            for reference in REFERENCES:
                with self.subTest(notes=notes, reference=reference):
                    answer, _, _, _ = self.generate(notes, quote, polarity='negated', reference=reference)
                    self.assert_held(answer)

    def test_v1_through_v4_requests_answers_and_stored_replays_remain_exact(self):
        cases = (
            (REFERRAL + 'The patient reports normal bowel movements.', 'normal bowel movements',
             {'name': PATIENT, 'other_name': DOCTOR}),
            ('The patient never used tobacco.', 'never used tobacco', {'polarity': 'negated'}),
            ('There was no scleral icterus and the oropharynx was clear.', 'clear', {'label': 'Oropharynx'}),
            ('The patient reports normal bowel movements.', 'normal bowel movements', {}),
            ('The patient denies fever and cough.', 'denies fever and cough', {'polarity': 'negated'}),
        )
        for profile in OLD_PROFILES:
            for reference, expected in zip(REFERENCES, HISTORICAL_REPLAY_SHA256[profile]):
                with self.subTest(profile=profile, reference=reference):
                    records = []
                    for notes, quote, kwargs in cases:
                        answer, sender, _, _ = self.generate(notes, quote, profile=profile,
                                                            reference=reference, **kwargs)
                        records.append({'answer': answer, 'requests': sender.calls})
                    self.assertEqual([record['answer']['status'] for record in records],
                                     ['conflict', 'conflict', 'conflict', 'supported', 'supported'])
                    digest = hashlib.sha256(json.dumps(records, sort_keys=True,
                                                       separators=(',', ':')).encode()).hexdigest()
                    self.assertEqual(digest, expected)
