"""The closed lists of evidence binding (Gemini migration slice S02; design/contract.md 5.3 and appendix B, design/FINAL.md
5.5, design/ADJUDICATION.md EB1-EB3 and C-15), TEXT-ONLY: folding; word-bounded, longest-first matching; every
landmark's surface forms and the containment (the colon regions included); every device class; the reach guard;
procedure names; negators, quantifiers and the visit labels; the five C1 marker lists; the words a person name is not;
the family tables pinned equal to gi.profiles (imported here, by the test only); and an AST scan showing that the four
modules of this slice import nothing from studio.gi. Misses are pinned as known limits."""
from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import lexicon, schema

PACKAGE = Path(__file__).resolve().parents[1] / 'studio' / 'interpretation'
SLICE_MODULES = ('literals', 'lexicon', 'normalize', 'verify')


class Folding(SimpleTestCase):
    def test_fold_is_the_normalized_tier(self):
        self.assertEqual(lexicon.fold('  Cold\u2011Snare\n\tPOLYPECTOMY '), 'cold snare polypectomy')
        self.assertEqual(lexicon.fold('\u201cNo\u201d \u2018further\u2019'), '"no" \'further\'')
        self.assertEqual(lexicon.fold('inter\u00adval'), 'interval', 'a soft hyphen is removed, never a space')
        self.assertEqual(lexicon.fold('\ufb01ne needle'), 'fine needle', 'NFKC')
        self.assertEqual(lexicon.fold('Stra\u00dfe'), 'strasse', 'case folding')
        self.assertEqual(lexicon.fold('A\u2014B\u2013C-D\u2212E'), 'a b c d e')

    def test_matching_is_word_bounded(self):
        self.assertEqual(lexicon.found('Biopsies were taken from another site', lexicon.NEGATORS), ())
        self.assertEqual(lexicon.found('notable nodularity', lexicon.NEGATORS), ())
        self.assertEqual(lexicon.landmarks_named('colonoscopy and sigmoidoscopy'), ())
        self.assertEqual(lexicon.found('No polyp; NOT removed', lexicon.NEGATORS), ('no', 'not'))

    def test_the_longest_entry_at_a_place_wins_and_each_is_given_once_in_order(self):
        self.assertEqual(lexicon.found('no further no polyp', lexicon.QUANTIFIERS), ('no further', 'no'))
        self.assertEqual(lexicon.landmarks_named('hepatic flexure'), ('hepatic_flexure',))
        self.assertEqual(lexicon.landmarks_named('transverse colon'), ('transverse_colon',))
        self.assertEqual(lexicon.landmarks_named('terminal ileum'), ('terminal_ileum',))
        self.assertEqual(lexicon.landmarks_named('second portion of the duodenum'), ('second_portion_duodenum',))
        self.assertEqual(lexicon.landmarks_named('the rectum, then the sigmoid colon, then the rectum'),
                         ('rectum', 'sigmoid_colon'))


class Landmarks(SimpleTestCase):
    def test_every_landmark_but_the_unplaced_has_forms_and_every_form_is_one_landmark(self):
        placed = set(schema.LANDMARKS) - lexicon.UNPLACED_LANDMARKS
        self.assertEqual(set(lexicon.LANDMARK_FORMS), placed)
        forms = [lexicon.fold(form) for values in lexicon.LANDMARK_FORMS.values() for form in values]
        self.assertEqual(len(forms), len(set(forms)), 'one form names one landmark')
        for landmark, values in lexicon.LANDMARK_FORMS.items():
            for form in values:
                with self.subTest(landmark=landmark, form=form):
                    self.assertEqual(lexicon.landmarks_named(f'seen in the {form} today'), (landmark,))

    def test_appendix_b_examples(self):
        cases = (('caecal', 'cecum'), ('the TI', 'terminal_ileum'), ('neo-terminal ileum', 'neo_terminal_ileum'),
                 ('neo TI', 'neo_terminal_ileum'), ('anastomotic', 'anastomosis'), ('anastomoses', 'anastomosis'),
                 ('D2', 'second_portion_duodenum'), ('post-bulbar duodenum', 'second_portion_duodenum'),
                 ('Z-line', 'gastroesophageal_junction'), ('GEJ', 'gastroesophageal_junction'),
                 ('right-sided colon', 'right_colon'), ('the left colon', 'left_colon'))
        for text, landmark in cases:
            with self.subTest(text):
                self.assertEqual(lexicon.landmarks_named(text), (landmark,))

    def test_containment_appendix_b_and_the_colon_regions(self):
        contains = lexicon.contains
        for inner in ('cecum', 'appendiceal_orifice', 'ileocecal_valve', 'ascending_colon', 'hepatic_flexure',
                      'transverse_colon', 'splenic_flexure', 'descending_colon', 'sigmoid_colon', 'rectosigmoid',
                      'right_colon', 'left_colon', 'proximal_colon', 'distal_colon'):
            with self.subTest(inner=inner):
                self.assertTrue(contains('colon', inner))
        self.assertFalse(contains('colon', 'rectum'), 'appendix B: the colon is cecum to rectosigmoid')
        for outer, inner in (('right_colon', 'cecum'), ('right_colon', 'ascending_colon'),
                             ('right_colon', 'hepatic_flexure'), ('left_colon', 'descending_colon'),
                             ('left_colon', 'sigmoid_colon'), ('proximal_colon', 'transverse_colon'),
                             ('proximal_colon', 'right_colon'), ('proximal_colon', 'cecum'),
                             ('distal_colon', 'left_colon'), ('distal_colon', 'sigmoid_colon'),
                             ('small_bowel', 'duodenum'), ('small_bowel', 'terminal_ileum'), ('ileum', 'terminal_ileum'),
                             ('ileum', 'neo_terminal_ileum'), ('stomach', 'gastric_antrum'),
                             ('esophagus', 'distal_esophagus'), ('esophagus', 'gastroesophageal_junction'),
                             ('duodenum', 'ampulla'), ('duodenum', 'duodenal_bulb'),
                             ('second_portion_duodenum', 'ampulla'), ('bile_duct', 'common_bile_duct'),
                             ('pancreas', 'pancreatic_duct')):
            with self.subTest(outer=outer, inner=inner):
                self.assertTrue(contains(outer, inner))
                self.assertFalse(contains(inner, outer), 'containment is one way')
        self.assertFalse(contains('right_colon', 'transverse_colon'))
        self.assertFalse(contains('cecum', 'cecum'), 'strict')

    def test_containment_is_transitive_and_acyclic(self):
        for outer, inners in lexicon.CONTAINS.items():
            self.assertNotIn(outer, inners)
            for inner in inners:
                self.assertTrue(lexicon.CONTAINS[inner] <= inners, f'{outer} contains what {inner} contains')

    def test_disjoint_needs_two_placed_landmarks_with_nothing_in_common(self):
        self.assertTrue(lexicon.disjoint('right_colon', 'sigmoid_colon'))  # ADJUDICATION C-15's case
        self.assertTrue(lexicon.disjoint('rectum', 'transverse_colon'))
        self.assertTrue(lexicon.disjoint('proximal_colon', 'distal_colon'))
        self.assertFalse(lexicon.disjoint('colon', 'sigmoid_colon'))
        self.assertFalse(lexicon.disjoint('proximal_colon', 'right_colon'))
        self.assertFalse(lexicon.disjoint('cecum', 'cecum'))
        for unplaced in ('anastomosis', 'stoma', 'pouch', 'other', 'not_stated'):
            with self.subTest(unplaced):
                self.assertFalse(lexicon.disjoint(unplaced, 'rectum'))
                self.assertFalse(lexicon.disjoint('rectum', unplaced))
        self.assertTrue(lexicon.compatible('colon', 'cecum') and lexicon.compatible('cecum', 'colon'))
        self.assertFalse(lexicon.compatible('cecum', 'rectum'))


class Devices(SimpleTestCase):
    NAMED = {
        'endoscope': ('the colonoscope', 'pediatric colonoscope', 'the scope', 'EGD'),
        'cold_snare': ('cold snare', 'snared cold'),
        'hot_snare': ('hot snare',),
        'snare': ('snare', 'snared'),
        'cold_forceps': ('cold forceps', 'cold biopsy'),
        'hot_forceps': ('hot forceps', 'hot biopsy'),
        'forceps': ('forceps', 'jumbo forceps'),
        'needle': ('22-gauge needle', 'FNB', 'fine needle'),
        'injection': ('injected', 'epinephrine', 'tattoo', 'carbon-particle tattoo', 'tattooed with India ink',
                      'lifted with saline', 'saline lift'),  # injected agents (S16 census)
        'balloon': ('balloon', 'CRE', 'TTS', 'through-the-scope', 'pneumatic', 'hydrostatic',
                    'controlled radial expansion'),
        'wire_bougie': ('Savary', 'Savary-Gilliard dilators', 'American dilators', 'wire-guided', 'over-the-wire',
                        'bougie over a guidewire'),
        'bougie': ('bougie', 'Maloney', 'Hurst', 'dilator'),
        'clip': ('two hemoclips', 'clipped'),
        'band': ('bands', 'banded'),
        'argon_plasma': ('argon plasma', 'APC'),
        'radiofrequency': ('radiofrequency', 'RFA'),
        'cryotherapy': ('cryotherapy', 'cryospray'),
        'thermal_probe': ('heater probe', 'bipolar', 'BICAP'),
        'electrocautery': ('electrocautery', 'cauterized', 'contact coagulation using the snare tip',
                           'low-power snare-tip soft coagulation', 'snare-tip soft coagulation', 'blended current',
                           'coagulation using the tip of the snare'),  # S16 census
        'stent': ('stent',),
        'basket': ('basket',),
        'extraction_balloon': ('balloon sweep', 'extraction balloon'),
        'sphincterotome': ('sphincterotome', 'needle-knife'),
        'lithotripter': ('lithotripsy', 'EHL'),
        'cholangioscope': ('SpyGlass', 'cholangioscope'),
        'capsule': ('PillCam', 'capsule'),
        'catheter': ('catheter',),
        'manual': ('digital', 'finger'),
    }
    NOT_NAMED = {
        'cold_snare': ('hot snare', 'snare', 'cold forceps'),
        'hot_snare': ('cold snare',),
        'snare': ('forceps', 'polypectomy'),
        'cold_forceps': ('forceps', 'hot forceps'),
        'balloon': ('Savary dilators', 'bougie'),
        'wire_bougie': ('bougie', 'dilator', 'balloon'),
        'bougie': ('balloon dilator', 'CRE balloon dilator', 'dilator over a guidewire', 'Savary'),
        'extraction_balloon': ('balloon', 'basket'),
        'endoscope': ('the polyp', 'forceps'),
        'clip': ('band',),
        # coagulation alone is no electrocautery (a heater probe coagulates; argon plasma coagulation is its own
        # class), nor is a snare's tip that does not coagulate
        'electrocautery': ('coagulation', 'contact coagulation with a heater probe', 'argon plasma coagulation',
                           'the snare tip was opened'),
        'injection': ('saline', 'washed with saline', 'a good lift'),  # saline or a lift alone is no injection
    }

    def test_every_device_has_a_rule_or_is_unchecked(self):
        for device in schema.DEVICES:
            with self.subTest(device):
                if device in lexicon.UNCHECKED_DEVICES:
                    self.assertFalse(lexicon.device_named(device, 'anything at all'))
                else:
                    self.assertIn(device, self.NAMED, 'every checked device is tested by name')
        self.assertEqual(lexicon.UNCHECKED_DEVICES, frozenset({'not_stated', 'other'}))

    def test_each_device_class_by_its_surface_forms(self):
        for device, texts in self.NAMED.items():
            for text in texts:
                with self.subTest(device=device, text=text):
                    self.assertTrue(lexicon.device_named(device, text))

    def test_and_not_by_another_classs(self):
        for device, texts in self.NOT_NAMED.items():
            for text in texts:
                with self.subTest(device=device, text=text):
                    self.assertFalse(lexicon.device_named(device, text))

    def test_the_reach_guard_reads_a_non_scope_device_with_no_scope(self):
        for text in ('the guidewire was advanced into the duodenum', 'a catheter reached the common duct',
                     'the TTS balloon was advanced', 'the capsule reached the cecum', 'the wire passed the stricture',
                     'through-the-scope balloon dilation'):
            with self.subTest(text):
                self.assertTrue(lexicon.device_reach(text))
        for text in ('the colonoscope was advanced to the cecum', 'to the cecum',
                     'a balloon was passed through the endoscope to the duodenum', 'cecum'):
            with self.subTest(text):
                self.assertFalse(lexicon.device_reach(text))
        self.assertFalse(lexicon.scope_named('through the scope'), 'through-the-scope names no scope')
        self.assertTrue(lexicon.scope_named('the instrument reached the cecum'))


class Names(SimpleTestCase):
    def test_every_procedure_with_names(self):
        unnamed = {'other_gi', 'not_gi', 'unknown'}
        self.assertEqual(set(lexicon.PROCEDURE_NAMES), set(schema.PROCEDURES) - unnamed)
        for procedure in unnamed:
            self.assertFalse(lexicon.procedure_named(procedure, 'colonoscopy egd visit'))
        for procedure, text in (('egd', 'Upper endoscopy'), ('egd', 'EGD'), ('colonoscopy', 'the colonoscope'),
                                ('flex_sig', 'flexible sigmoidoscopy'), ('eus', 'endoscopic ultrasound'),
                                ('ercp', 'ERCP'), ('enteroscopy', 'push enteroscopy'), ('office_em', 'office visit'),
                                ('capsule', 'PillCam'), ('motility', 'esophageal manometry'), ('reflux', 'Bravo'),
                                ('anorectal', 'anorectal manometry'), ('feeding_tube', 'PEG'),
                                ('sedation', 'moderate sedation'), ('em_other', 'inpatient consultation')):
            with self.subTest(procedure=procedure, text=text):
                self.assertTrue(lexicon.procedure_named(procedure, text))
        self.assertFalse(lexicon.procedure_named('colonoscopy', 'EGD'))
        self.assertFalse(lexicon.procedure_named('egd', 'colonoscopy'))

    def test_negators_and_non_performance_words(self):
        for entry in lexicon.NEGATORS:
            text = 'could' + entry if entry == "n't" else f'there was {entry} biopsy'
            with self.subTest(entry):
                self.assertTrue(lexicon.negation(text))
        for entry in lexicon.NON_PERFORMANCE:
            with self.subTest(entry):
                self.assertTrue(lexicon.negation(f'the polyp was {entry}'))
        self.assertEqual(lexicon.negation('wasn\u2019t removed'), ("n't",), 'a curly apostrophe folds straight')
        self.assertEqual(lexicon.negation('removed with a cold snare'), ())
        self.assertEqual(lexicon.negation('taken from another site'), ())

    def test_negation_known_limits(self):
        # Not in the contract's closed list (5.3): a statement worded only so gives a question, never an exclusion.
        for text in ('cannot be removed', 'unable to remove', 'the polyp remains'):
            with self.subTest(text):
                self.assertEqual(lexicon.negation(text), ())

    def test_quantifiers_durations_and_labels(self):
        for entry in lexicon.QUANTIFIERS:
            with self.subTest(entry):
                self.assertTrue(lexicon.found(f'{entry} biopsies', lexicon.QUANTIFIERS))
        self.assertEqual(lexicon.found('the biopsy', lexicon.QUANTIFIERS), ())
        self.assertEqual(lexicon.found('medical decision-making', lexicon.DECISION_LABELS), ('decision making',))
        self.assertEqual(lexicon.found('MDM: moderate', lexicon.DECISION_LABELS), ('mdm',))
        self.assertEqual(lexicon.found('decisions were made', lexicon.DECISION_LABELS), ())


class Markers(SimpleTestCase):
    LISTS = {'planning': lexicon.PLANNING_MARKERS, 'failure': lexicon.FAILURE_MARKERS,
             'earlier': lexicon.EARLIER_MARKERS, 'future': lexicon.FUTURE_MARKERS,
             'facility': lexicon.FACILITY_MARKERS}

    def test_every_entry_of_every_list_is_read(self):
        for kind, entries in self.LISTS.items():
            for entry in entries:
                with self.subTest(kind=kind, entry=entry):
                    self.assertTrue(lexicon.markers(kind, f'the act {entry} today'))

    def test_the_future_period(self):
        for text in ('in 3 years', 'in two weeks', 'in 6 months', 'in one year', 'in twenty four months',
                     'in 4 to 6 weeks', 'in two or three months'):  # a range of two (S16 census: "in 4 to 6 weeks")
            with self.subTest(text):
                self.assertIn(text, lexicon.markers('future', text))
        for text in ('in years', 'in the 3 weeks before', '3 years ago', '4 to 6 weeks ago', 'in 4 to weeks'):
            with self.subTest(text):
                self.assertFalse(any(marker.startswith('in ') for marker in lexicon.markers('future', text)))

    def test_markers_are_word_bounded_and_specific(self):
        self.assertEqual(lexicon.markers('earlier', 'the lasting effect'), ())
        self.assertEqual(lexicon.markers('earlier', 'status post EMR'), ('status post',))
        self.assertEqual(lexicon.markers('earlier', 's/p EMR'), ('s/p',))
        self.assertEqual(lexicon.markers('facility', 'performed today'), ())
        self.assertEqual(lexicon.markers('planning', 'removed with a cold snare'), ())
        self.assertEqual(lexicon.markers('failure', 'completed without difficulty'), ())
        self.assertEqual(lexicon.markers('future', 'A future intervention is planned'), ('future', 'planned'))
        self.assertEqual(lexicon.markers('future', 'the futures'), ())

    def test_an_unknown_marker_kind_is_an_error(self):
        with self.assertRaises(KeyError):
            lexicon.markers('negation', 'no')


class PersonWords(SimpleTestCase):
    def test_titles_credentials_role_facility_and_function_words_are_never_names(self):
        for word in lexicon.TITLES + lexicon.CREDENTIALS + lexicon.ROLE_WORDS + lexicon.FUNCTION_WORDS:
            with self.subTest(word):
                self.assertIn(lexicon.fold(word), lexicon.NOT_NAMES)
        for word in lexicon.FACILITY_MARKERS:
            self.assertIn(word, lexicon.NOT_NAMES)

    def test_the_identity_words_are_closed_lists(self):
        self.assertIn('polyp', lexicon.REFERENCE_WORDS)
        self.assertIn('the lesion', lexicon.REFERENCE_WORDS)
        self.assertIn('the', lexicon.TIE_FUNCTION_WORDS)


class Families(SimpleTestCase):
    def test_the_family_tables_equal_gi_profiles(self):
        from studio.gi import profiles  # the reference table; imported by this test only (FINAL 3.1)
        self.assertEqual(set(lexicon.FAMILY_OF.values()) - {''}, set(profiles.PROFILES))
        self.assertEqual(lexicon.PROCEDURAL_FAMILIES,
                         frozenset(slug for slug, profile in profiles.PROFILES.items() if profile.procedure))
        self.assertEqual(lexicon.FAMILY_ORDER, profiles.FAMILY_ORDER)
        for procedure in schema.PROCEDURES:
            with self.subTest(procedure):
                family = lexicon.family_of(procedure)
                if procedure == 'unknown':
                    self.assertEqual(family, '')
                else:
                    self.assertIn(family, profiles.PROFILES)
        self.assertEqual(lexicon.family_of('other_gi'), 'gi.other')
        self.assertEqual(lexicon.family_of('not_gi'), 'gi.unsupported')
        self.assertEqual(lexicon.family_of('nonsense'), '')


class NoLegacyImport(SimpleTestCase):
    def test_the_slices_modules_import_nothing_from_studio_gi(self):
        for name in SLICE_MODULES:
            tree = ast.parse((PACKAGE / f'{name}.py').read_text(encoding='utf-8'))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add(node.module or '')
                    imported.update(f'{node.module}.{alias.name}' for alias in node.names)
            with self.subTest(name):
                self.assertFalse([module for module in imported if module.startswith('studio.gi')], sorted(imported))
                self.assertFalse([module for module in imported if module.startswith('studio.validation')])
