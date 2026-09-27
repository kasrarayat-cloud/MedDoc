"""Ordinary (unlabelled) typed or dictated notes on a contract v3 Word form: synthetic notes, no provider requests.

The provider's choice is simulated by unit selections, exactly the shape the live complete-sentence contract returns.
What is asserted is what the application does with it: complete source sentences are adopted, options are filled
only from their own labelled statement, and governance, fragments and corrections are held, never discarded.
"""
from django.test import SimpleTestCase, override_settings

from core import generation as g


def field(key, label, kind='text', options=None):
    f = {'key': key, 'label': label, 'kind': kind, 'context': '',
         'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[%d]' % len(key),
                     'target': {'type': 'span', 'start': 0, 'end': 0, 'shape': 'after_label'}, 'fingerprint': '0' * 64}}
    if options is not None:
        f['options'] = options
    return f


FIELDS = [field('v3_1', 'Chief complaint'), field('v3_2', 'Allergies'), field('v3_3', 'Plan', 'long_text'),
          field('v3_4', 'Smoker', 'choice', ['Yes', 'No']), field('v3_5', 'Consent obtained', 'checkbox', ['Consent obtained']),
          field('v3_6', 'Clinician signature', 'signature')]


def run(notes, picks, conflicts=()):
    """Simulate the provider selecting unit ids per label, then validate and adopt as the application does."""
    asked, context, v3_fields = g.v3_generation_fields(FIELDS)
    units, _ = g.source_units(notes, asked, context_labels=context)
    by_quote = {u['quote']: u['id'] for u in units}
    selections = g.UnitSelections(fields=[
        g.UnitSelection(key=f['key'], unit_ids=[by_quote[q] for q in picks.get(f['label'], [])],
                        conflict=f['label'] in conflicts) for f in asked])
    selections = g.unit_selections(notes, asked, selections, context_labels=context)
    answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
    adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
    return {f['label']: adopted[f['key']] for f in FIELDS}


class OrdinaryNotesOnV3Forms(SimpleTestCase):
    def test_prose_notes_are_adopted_as_complete_sentences_not_returned_as_conflicts(self):
        notes = ('Patient presents with right knee pain for three weeks. Allergies: penicillin. '
                 'Plan is physiotherapy twice weekly and review in six weeks.')
        out = run(notes, {'Chief complaint': ['Patient presents with right knee pain for three weeks.'],
                          'Allergies': ['Allergies: penicillin.'],
                          'Plan': ['Plan is physiotherapy twice weekly and review in six weeks.']})
        self.assertEqual(out['Chief complaint']['status'], 'supported')
        self.assertEqual(out['Chief complaint']['text'], 'Patient presents with right knee pain for three weeks.')
        self.assertEqual(out['Allergies']['text'], 'penicillin.')
        self.assertEqual(out['Plan']['status'], 'supported')

    def test_an_option_is_filled_only_from_its_own_labelled_sentence(self):
        notes = 'Smoker: No. The patient drinks socially.'
        out = run(notes, {'Smoker': ['Smoker: No.']})
        self.assertEqual(out['Smoker']['text'], 'No')
        self.assertEqual(out['Smoker']['status'], 'supported')

    def test_an_unlabelled_sentence_never_becomes_an_option(self):
        notes = 'The patient does not smoke. Allergies: none known.'
        out = run(notes, {'Smoker': ['The patient does not smoke.']})
        self.assertNotEqual(out['Smoker']['status'], 'supported')
        self.assertEqual(out['Smoker']['text'], '')

    def test_a_negated_or_qualified_value_is_not_an_option(self):
        for notes in ('Smoker: no longer.', 'Smoker: not yes.', 'Smoker: No, former smoker.'):
            out = run(notes, {'Smoker': [notes]})
            self.assertEqual(out['Smoker']['text'], '', notes)

    def test_a_labelled_option_under_a_governing_line_is_held_not_filled(self):
        for notes in ('If symptoms recur:\nSmoker: yes.', 'Family history:\nSmoker: yes.',
                      'Denies the following:\nSmoker: yes.'):
            out = run(notes, {'Smoker': ['Smoker: yes.']})
            self.assertNotEqual(out['Smoker']['status'], 'supported', notes)
            self.assertEqual(out['Smoker']['text'], '', notes)

    def test_a_checkbox_is_ticked_only_by_an_explicit_yes(self):
        self.assertEqual(run('Consent obtained: yes.', {'Consent obtained': ['Consent obtained: yes.']})
                         ['Consent obtained']['text'], 'checked')
        self.assertEqual(run('Consent obtained: verbal.', {'Consent obtained': ['Consent obtained: verbal.']})
                         ['Consent obtained']['text'], '')

    def test_a_verbless_fragment_is_held_not_adopted(self):
        out = run('Right knee. Allergies: none.', {'Chief complaint': ['Right knee.']})
        self.assertNotEqual(out['Chief complaint']['status'], 'supported')

    def test_a_denial_heading_governs_what_follows_and_is_held(self):
        notes = 'Denies the following:\nChest pain.\nShortness of breath.'
        out = run(notes, {'Chief complaint': ['Chest pain.']})
        self.assertNotEqual(out['Chief complaint']['status'], 'supported')

    def test_a_statement_repeated_into_numbered_looking_labels_is_held_not_a_failed_job(self):
        fields = [field('v3_a', 'Visit — 1'), field('v3_b', 'Visit — 2')]
        notes = 'The wound is healing well.'
        units, _ = g.source_units(notes, fields)
        selections = g.UnitSelections(fields=[g.UnitSelection(key='v3_a', unit_ids=[units[0]['id']], conflict=False),
                                              g.UnitSelection(key='v3_b', unit_ids=[units[0]['id']], conflict=False)])
        answers = g.validate_selections(notes, fields, selections, evidence_contract=g.TAB_CONTRACT)
        self.assertEqual({a['status'] for a in answers.values()} - {'supported'}, {'conflict'})

    def test_signature_is_never_generated(self):
        out = run('Clinician signature: Dr Example.', {})
        self.assertEqual(out['Clinician signature']['text'], '')

    @override_settings(QUILLMD_AI_MODE='fixture')
    def test_non_v3_forms_keep_the_labelled_contract(self):
        legacy = [{'key': 'q1', 'label': 'Allergies', 'locator': {'table': 0, 'row': 0, 'col': 1}}]
        self.assertFalse(g.natural_v3(legacy))
        self.assertFalse(g.tab_evidence_contract(legacy))
        self.assertTrue(g.natural_v3(FIELDS))
