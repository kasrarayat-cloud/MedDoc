"""Synthetic, source-only descriptor controls; no database or provider calls."""
from copy import deepcopy
from unittest.mock import patch

from django.test import SimpleTestCase

from core import coding_completeness as completeness, coding_source_descriptors as descriptors


class SourceCompoundDescriptorTests(SimpleTestCase):
    def notes(self, report, evaluation='Diarrhea and left lower quadrant abdominal pain were evaluated today.', *, name='Synthetic Neri Moss'):
        return f'Patient: {name}\nHistory of present illness\n{report}\nAssessment\n{evaluation}'

    def report(self, quantity='4–7', *, location='left lower quadrant', tail='that is relieved after each bowel movement'):
        return (f'The patient describes {quantity} watery stools each day, with recurrent moderate '
                f'{location} cramping {tail}.')

    def assert_gap(self, report, evaluation='Diarrhea and left lower quadrant abdominal pain were evaluated today.'):
        notes = self.notes(report, evaluation)
        result = completeness.inventory(notes)
        self.assertFalse(any(item.get('descriptive_reports') for item in result['items']))
        # The original nominal parser sometimes represents a report as
        # unevaluated items rather than one opaque gap. Both remain obligations
        # and must retain the full report; the descriptor pass must not hide it.
        self.assertTrue(any(not row['current_evaluation_evidence']
            and any(span['quote'] == report for span in row['evidence'])
            for row in [*result['unresolved'], *result['items']]), report)
        return result

    def test_complete_report_retains_whole_source_and_exact_typed_spans(self):
        notes = self.notes(self.report())
        result = completeness.inventory(notes)
        self.assertFalse(result['unresolved'])
        self.assertEqual(len(result['items']), 2)
        proof = result['items'][0]['descriptive_reports'][0]
        self.assertEqual(proof, result['items'][1]['descriptive_reports'][0])
        self.assertTrue(proof['exhaustive'])
        self.assertFalse(proof['establishes_diagnosis_or_code'])
        self.assertEqual(proof['contract'], descriptors.CONTRACT)
        self.assertEqual([atom['relation']['kind'] for atom in proof['atoms']],
            ['daily_loose_stool_description', 'same_location_abdominal_cramping'])
        self.assertEqual([atom['relation']['authority'] for atom in proof['atoms']],
            [descriptors.DIARRHEA_AUTHORITY, descriptors.PAIN_AUTHORITY])
        spans = [proof['report'], proof['objects'], *proof['separators']]
        for atom in proof['atoms']:
            spans.extend([atom['span'], *[attribute['span'] for attribute in atom['attributes']]])
            self.assertTrue(atom['relation']['independent_evaluation'])
            self.assertNotIn(proof['report'], atom['relation']['independent_evaluation'])
        for span in spans:
            self.assertEqual(notes[span['start']:span['end']], span['quote'])
        coverage = sorted([atom['span'] for atom in proof['atoms']] + proof['separators'], key=lambda span: span['start'])
        self.assertEqual(''.join(span['quote'] for span in coverage), proof['objects']['quote'])
        self.assertTrue(all(left['end'] == right['start'] for left, right in zip(coverage, coverage[1:])))
        quantity = next(value for value in proof['atoms'][0]['attributes'] if value['kind'] == 'quantity')
        self.assertEqual((quantity['minimum'], quantity['maximum'], quantity['unit']), (4, 7, 'stools_per_day'))
        modification = next(value for value in proof['atoms'][1]['attributes'] if value['kind'] == 'symptom_modification')
        self.assertFalse(modification['infers_etiology'])
        for item in result['items']:
            self.assertIn(proof['report'], item['evidence'])
            self.assertNotIn(proof['report'], item['current_evaluation_evidence'])

    def test_complete_integer_grammar_and_whole_range_threshold(self):
        for quantity in ('3', '3 to 5', '3–5', '3-5', '6—8', 'three to seven',
                         'between four and nine', 'four to 7', 'twenty-one',
                         'twenty-one to twenty-three', 'thirty two', '99'):
            with self.subTest(quantity=quantity):
                result = completeness.inventory(self.notes(self.report(quantity)))
                self.assertFalse(result['unresolved'])
                self.assertEqual(len(result['items']), 2)
        for quantity in ('2', '2 to 5', 'five to three', '3.5', '-3', '03', '3/5',
                         '3 or 5', 'approximately 3', 'at most 3', '3-', '3,5',
                         'three point five', 'three-to-five', '1000', 'twenty–one'):
            with self.subTest(quantity=quantity):
                self.assert_gap(self.report(quantity))

    def test_stool_quality_and_daily_unit_must_both_be_complete(self):
        for quality in ('loose', 'watery', 'loose or watery', 'watery and loose'):
            for frequency in ('daily', 'per day', 'a day', 'every day'):
                report = f'They report 6 {quality} stools {frequency}, with mild epigastric cramping.'
                result = completeness.inventory(self.notes(report, 'Diarrhea and epigastric abdominal pain are evaluated today.'))
                self.assertFalse(result['unresolved'])
        for description in ('6 formed stools daily', '6 loose or formed stools daily',
                            '6 loose stools weekly', 'loose stools daily',
                            '6 loose stools twice daily', '6 loose stools daily or weekly'):
            self.assert_gap(f'The patient reports {description}, with mild left lower quadrant cramping.')

    def test_different_names_locations_order_and_connectors(self):
        for name, location in (('Synthetic Ivo Dalen', 'epigastric'),
                               ('Synthetic Suri Keene', 'right iliac fossa'),
                               ('Synthetic Ada Tern', 'suprapubic')):
            for connector in (', with ', ', and ', ' and ', ' with '):
                report = f'{name} reports mild {location} cramping{connector}five loose stools a day.'
                result = completeness.inventory(self.notes(report,
                    f'{location} abdominal pain and diarrhea were evaluated today.', name=name))
                self.assertFalse(result['unresolved'])
                self.assertEqual(len(result['items']), 2)
        first = ('Patient: Synthetic Ivo Dalen\nAssessment\nDiarrhea and epigastric abdominal pain are evaluated today.\n'
                 'History of present illness\nHe reports five loose stools daily, with epigastric cramping.')
        self.assertFalse(completeness.inventory(first)['unresolved'])

    def test_generic_exact_nominal_linkage_needs_no_familiar_condition_name(self):
        report = ('She describes moderate Caldor plaque that improves after a bowel movement, '
                  'with intermittent dorsal wrist ache daily.')
        result = completeness.inventory(self.notes(report, 'Caldor plaque and dorsal wrist ache were evaluated today.'))
        self.assertFalse(result['unresolved'])
        proof = result['items'][0]['descriptive_reports'][0]
        self.assertEqual([atom['relation']['kind'] for atom in proof['atoms']], ['exact_nominal', 'exact_nominal'])
        self.assertEqual({item['condition_text'] for item in result['items']}, {'Caldor plaque', 'dorsal wrist ache'})

    def test_single_descriptors_and_simple_compounds_are_not_incidental_conditions(self):
        for report, evaluation, expected in (
            ('He reports five watery stools daily.', 'Diarrhea was evaluated today.', {'Diarrhea'}),
            ('She reports mild right iliac fossa cramping.', 'Right iliac fossa abdominal pain was evaluated today.', {'Right iliac fossa abdominal pain'}),
            ('They report five watery stools daily and mild left lower quadrant cramping.',
             'Diarrhea and left lower quadrant abdominal pain were evaluated today.', {'Diarrhea','left lower quadrant abdominal pain'})):
            result = completeness.inventory(self.notes(report, evaluation))
            self.assertFalse(result['unresolved'])
            self.assertEqual({item['condition_text'] for item in result['items']}, expected)
            self.assertTrue(all(item['descriptive_reports'] for item in result['items']))

    def test_repair_preserves_independent_incidental_evidence_and_assessments(self):
        report = 'He reports five watery stools daily.'
        other_report = 'He reports five watery stools.'
        result = completeness.inventory(self.notes(report + '\n' + other_report, 'Diarrhea was evaluated today.'))
        incidental = next(item for item in result['items'] if item['condition_text'] == 'five watery stools')
        self.assertEqual([span['quote'] for span in incidental['evidence']], [other_report])
        self.assertFalse(incidental['current_evaluation_evidence'])
        extra = 'Five watery stools are present according to an unverified account.'
        result = completeness.inventory(self.notes(report + '\n' + extra, 'Diarrhea was evaluated today.'))
        self.assertTrue(result['unresolved'])
        self.assertTrue(any(row['condition_text'] == extra for row in result['unresolved']))
        result = completeness.inventory(self.notes(report, 'Diarrhea and five watery stools were evaluated today.'))
        self.assertTrue(any(item['condition_text'] == 'five watery stools' and item['current_evaluation_evidence']
            for item in result['items']))

    def test_ordinary_nominal_inventory_has_no_new_empty_or_descriptor_keys(self):
        result = completeness.inventory(self.notes('She reports mild heartburn daily.', 'Heartburn was evaluated today.'))
        self.assertFalse(result['unresolved'])
        self.assertTrue(all('descriptive_reports' not in item for item in result['items']))

    def test_existing_qualified_row_coalescing_preserves_descriptor_proof(self):
        report = {'report':{'start':0,'end':12,'quote':'source words'}, 'atoms':[{'target_id':'bare'}]}
        evidence = {'start':20,'end':24,'quote':'Pain'}
        bare = {'id':'bare','condition_text':'Pain','reference_terms':['Pain'],
            'current_evaluation_evidence':[evidence], 'evidence':[evidence],
            'candidates':[], 'descriptive_reports':[report]}
        candidate = {'code':'synthetic-route','eligible':True,'proof':{},
            'index_route':{'qualified_phrase_proof':{'direct_head':'Pain'}}}
        target = {'id':'qualified','condition_text':'Epigastric pain','reference_terms':['Pain'],
            'current_evaluation_evidence':[evidence], 'evidence':[evidence], 'candidates':[candidate]}
        rows, _ = completeness._coalesce_reference_mentions([bare,target], [])
        self.assertEqual(rows, [target])
        self.assertEqual(target['descriptive_reports'], [report])
        self.assertEqual(candidate['proof']['descriptive_reports'], [report])
        self.assertEqual(candidate['support_digest'], completeness.engine.digest(candidate['proof']))
        self.assertIsNot(candidate['proof']['descriptive_reports'], target['descriptive_reports'])

    def test_unmatched_atom_does_not_partially_discharge_or_attach_evidence(self):
        for suffix in ('with new chest pain', 'and fever', 'with left wrist cramping',
                       'with possible left lower quadrant cramping', 'and diarrhea is not current'):
            self.assert_gap(f'The patient reports six loose stools daily, {suffix}.')
        for tail in ('that he no longer has', 'that might improve after a bowel movement',
                     'that improves after a bowel movement and vomiting',
                     'that improves after a bowel movement because of infection',
                     'that improves after a bowel movement except when bleeding',
                     'that improves after a bowel movement according to his mother',
                     'that improves after a bowel movement on an uncertain date'):
            self.assert_gap(self.report(tail=tail))
        self.assert_gap(self.report()[:-1] + ',')
        self.assert_gap(self.report()[:-1] + '; no other details.')

    def test_no_unknown_location_modifier_or_anatomical_equivalence(self):
        for location in ('right lower quadrant', 'left upper quadrant', 'lower left quadrant',
                         'left lower abdominal', 'left wrist', 'acute', 'postoperative', 'unexplained'):
            self.assert_gap(self.report(location=location))
        self.assert_gap(self.report(location='postoperative'), 'Diarrhea and postoperative abdominal pain were evaluated today.')
        self.assert_gap(self.report(location='left wrist'), 'Diarrhea and left wrist abdominal pain were evaluated today.')

    def test_conflicting_modifiers_and_multiple_targets_are_not_unique(self):
        self.assert_gap(self.report().replace('recurrent moderate', 'mild severe'))
        self.assert_gap(self.report().replace('recurrent moderate', 'recurrent constant'))
        report = 'They report moderate dorsal wrist ache that improves after a bowel movement, with loose stools.'
        self.assert_gap(report, 'Dorsal wrist ache and moderate dorsal wrist ache and loose stools were evaluated today.')

    def test_assessed_target_prefix_participates_in_modifier_conflicts(self):
        for target, extra in (
            ('Severe epigastric abdominal pain', 'mild '),
            ('Severe epigastric abdominal pain', 'severe '),
            ('Intermittent dorsal wrist ache', 'constant '),
            ('Intermittent dorsal wrist ache', 'intermittent '),
            ('Mild severe epigastric abdominal pain', ''),
            ('Recurrent constant dorsal wrist ache', ''),
            ('Mild intermittent severe dorsal wrist ache', '')):
            report = f'They report {extra}{target.lower()} that improves after a bowel movement.'
            with self.subTest(target=target, extra=extra):
                self.assert_gap(report, f'{target} was evaluated today.')

    def test_distinct_modifier_kinds_across_target_and_report_keep_exact_spans(self):
        for target, extra in (
            ('Severe epigastric abdominal pain', 'Intermittent  '),
            ('Intermittent dorsal wrist ache', 'Mild  '),
            ('Mild intermittent dorsal wrist ache', ''),
            ('Moderate dorsal wrist ache', '')):
            report = f'They report {extra}{target} that improves after a bowel movement.'
            notes = self.notes(report, f'{target} was evaluated today.')
            result = completeness.inventory(notes)
            self.assertFalse(result['unresolved'])
            proof = result['items'][0]['descriptive_reports'][0]
            attributes = [value for value in proof['atoms'][0]['attributes']
                          if value['kind'] in ('severity','frequency')]
            expected = 1 if target.startswith('Moderate') else 2
            self.assertEqual(len(attributes), expected)
            self.assertEqual(len({value['kind'] for value in attributes}), expected)
            for value in attributes:
                span = value['span']
                self.assertEqual(notes[span['start']:span['end']], span['quote'])
                self.assertEqual(span['quote'].casefold(), value['value'])

    def test_all_literal_target_positions_participate_in_modifier_conflicts(self):
        for target, extra in (
            ('Localized severe abdominal pain', 'mild '),
            ('Epigastric severe abdominal pain', 'mild '),
            ('Abdominal pain of severe degree', 'mild '),
            ('Dorsal wrist ache intermittent', 'constant '),
            ('Localized mild abdominal pain of severe degree', ''),
            ('Dorsal recurrent wrist ache constant', ''),
            ('Localized-severe abdominal pain', 'mild '),
            ('Dorsal wrist ache-intermittent', 'constant '),
            ('Localized-mild abdominal pain-severe', '')):
            report = f'They report {extra}{target.lower()} that improves after a bowel movement.'
            with self.subTest(target=target, extra=extra):
                self.assert_gap(report, f'{target} was evaluated today.')

    def test_interior_distinct_modifier_kinds_retain_literal_spans(self):
        for target, extra in (
            ('Localized  SeVeRe abdominal pain', 'Intermittent  '),
            ('Dorsal wrist ache InTeRmItTeNt', 'Mild  '),
            ('Localized-severe abdominal pain', 'Recurrent  '),
            ('Dorsal recurrent wrist ache of moderate degree', '')):
            report = f'They report {extra}{target} that improves after a bowel movement.'
            notes = self.notes(report, f'{target} was evaluated today.')
            with self.subTest(target=target, extra=extra):
                result = completeness.inventory(notes)
                self.assertFalse(result['unresolved'])
                proof = result['items'][0]['descriptive_reports'][0]
                atom = proof['atoms'][0]
                attributes = [value for value in atom['attributes']
                              if value['kind'] in ('severity', 'frequency')]
                self.assertEqual({value['kind'] for value in attributes}, {'severity', 'frequency'})
                self.assertEqual(len(attributes), 2)
                literal = next(value for value in atom['attributes'] if value['kind'] == 'literal_finding')
                self.assertEqual(literal['span']['quote'], target)
                for value in [literal, *attributes]:
                    span = value['span']
                    self.assertEqual(notes[span['start']:span['end']], span['quote'])
                for value in attributes:
                    self.assertEqual(value['span']['quote'].casefold(), value['value'])

    def test_recognized_modifier_words_do_not_match_substrings_or_erase_suffixes(self):
        for target in ('Severed dorsal ligament', 'Mildred dorsal ache',
                       'Recurrently reported ache', 'Currentness sensation'):
            report = f'They report mild {target} that improves after a bowel movement.'
            with self.subTest(target=target):
                result = completeness.inventory(self.notes(report, f'{target} was evaluated today.'))
                self.assertFalse(result['unresolved'])
                proof = result['items'][0]['descriptive_reports'][0]
                attributes = [value for value in proof['atoms'][0]['attributes']
                              if value['kind'] in ('severity', 'frequency')]
                self.assertEqual([(value['kind'], value['value']) for value in attributes], [('severity', 'mild')])
        for suffix in ('with unexplained nausea', 'that improves for an unknown reason',
                       'that improves after a bowel movement sometimes', ', severe'):
            self.assert_gap(f'They report intermittent localized severe abdominal pain {suffix}.',
                'Localized severe abdominal pain was evaluated today.')

    def test_separate_current_evaluation_is_mandatory(self):
        self.assert_gap(self.report(), 'Diarrhea was evaluated today.')
        self.assert_gap(self.report(), 'Left lower quadrant abdominal pain was evaluated today.')
        result = completeness.inventory(self.notes(self.report(), 'Diarrhea and left lower quadrant abdominal pain were evaluated yesterday.'))
        self.assertTrue(result['unresolved'])
        self.assertFalse(any(item.get('descriptive_reports') for item in result['items']))
        report = self.report()
        targets = [{'id':'synthetic', 'condition_text':'diarrhea',
                    'current_evaluation_evidence':[{'start':0,'end':len(report),'quote':report}]}]
        self.assertIsNone(descriptors.resolve_report('five loose stools daily', objects_start=10,
            report={'start':0,'end':len(report),'quote':report}, targets=targets))

    def test_ownership_past_negation_and_unknown_date_are_never_repaired(self):
        variants = (self.report().replace('describes', 'previously described'),
                    self.report().replace('watery', 'possibly watery'),
                    self.report().replace('watery', 'not watery'),
                    self.report()[:-1] + ' in 2020.',
                    self.report()[:-1] + ' on an unknown date.',
                    self.report().replace('The patient', 'The patient\'s mother'))
        for report in variants:
            result = completeness.inventory(self.notes(report))
            self.assertFalse(any(item.get('descriptive_reports') for item in result['items']), report)

    def test_retained_facts_and_order_do_not_supply_descriptor_authority(self):
        notes = self.notes(self.report())
        result = completeness.inventory(notes)
        self.assertEqual(result, completeness.inventory(notes, retained_facts=[{'id':'made-up', 'value':'additional condition'}]))
        changed = completeness.inventory(notes.replace('4–7', '5–7'))
        self.assertNotEqual(result['inventory_sha256'], changed['inventory_sha256'])
        self.assertEqual(result['reference_terms'], changed['reference_terms'])

    def test_code_coverage_still_uses_independent_index_and_tabular_gates(self):
        from core.tests.test_coordinated_coding import reference, run
        ref = reference()
        ref.digest = completeness.engine.digest({'index':ref.index, 'tabular':ref.tabular})
        notes = self.notes('They report four to eight loose stools per day, with mild periumbilical cramping that improves after a bowel movement.',
            'Diarrhea and periumbilical abdominal pain were evaluated during this encounter.')
        current = run(notes=notes)
        current.releases = [vars(ref.release)]
        current.result = {'irrelevant_provider_fact':'unknown diagnosis'}
        before = deepcopy(vars(current))
        inv = completeness.inventory(notes)
        ref.completeness_scope = {'contract':completeness.REFERENCE_CONTRACT,
            'source_sha256':inv['source_sha256'], 'inventory_sha256':inv['inventory_sha256'],
            'terms':sorted(set(inv['reference_terms'])), 'complete':True}
        result = completeness.evaluate(current, ref, approved_codes=['R19.7', 'R10.33'])
        self.assertEqual(vars(current), before)
        self.assertTrue(result['coverage']['complete'])
        self.assertEqual({candidate['code'] for candidate in result['suggestions']}, {'R19.7', 'R10.33'})
        for candidate in result['suggestions']:
            self.assertTrue(candidate['proof']['descriptive_reports'])
            self.assertTrue(candidate['eligible'])
        with patch.object(completeness.corti_coding, '_icd_source', return_value=(None,None,{})), \
                patch.object(completeness, '_qualified_route', return_value=(None,None,{})):
            rejected = completeness.evaluate(current, ref, approved_codes=['R19.7', 'R10.33'])
        self.assertFalse(rejected['coverage']['complete'])
        self.assertFalse(rejected['suggestions'])
