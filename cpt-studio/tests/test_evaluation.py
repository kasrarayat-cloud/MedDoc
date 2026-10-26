import json
import tempfile
import unittest
from pathlib import Path

from studio.evaluation import ManifestRefused, ReferenceCode, EvaluationCase, aggregate, load_manifest, score_case


def manifest(**overrides):
    data = {'adjudicated': True, 'withheld_from_development': True,
            'adjudication': {'adjudicators': ['two certified coders (synthetic test)'], 'method': 'independent double coding',
                             'adjudicated_on': '2026-10-23'},
            'cases': [{'case_id': 'c1', 'document': 'c1.txt', 'delivery': 'txt',
                       'reference_codes': [{'code': '45385'}, {'code': '45380', 'modifiers': ['59']}]}]}
    data.update(overrides)
    return data


class ManifestTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps(data))
            return load_manifest(path)

    def test_refuses_unadjudicated_or_development_cases(self):
        with self.assertRaises(ManifestRefused):
            self.load(manifest(adjudicated=False))
        with self.assertRaises(ManifestRefused):
            self.load(manifest(withheld_from_development=False))
        with self.assertRaises(ManifestRefused):
            self.load(manifest(adjudication={'adjudicators': ['x']}))

    def test_loads_valid_manifest(self):
        cases = self.load(manifest())
        self.assertEqual(cases[0].references[1].modifiers, ('59',))


class ScoringTests(unittest.TestCase):
    def test_per_family_missed_extra_and_modifiers_never_count_as_agreement(self):
        case = EvaluationCase('c1', 'c1.txt', 'txt', (ReferenceCode('45385'), ReferenceCode('45380', ('59',)),
                                                      ReferenceCode('99213')))
        proposals = [{'bucket': 'selected', 'code': '45385', 'family': 'gi.colonoscopy', 'status': 'ready', 'units': 1},
                     {'bucket': 'selected', 'code': '45378', 'family': 'gi.colonoscopy', 'status': 'ready', 'units': 1},
                     {'bucket': 'alternative', 'code': '45380', 'family': 'gi.colonoscopy', 'status': 'informational'}]
        scored = score_case(case, proposals)
        colon = scored['gi.colonoscopy']
        self.assertEqual(colon['missed'], ['45380'])
        self.assertEqual(colon['extra'], ['45378'])
        self.assertFalse(colon['complete_correct'])
        self.assertEqual(colon['modifiers_produced'], 0)
        self.assertEqual(scored['gi.office_em']['missed'], ['99213'])
        totals = aggregate([{'case_id': 'c1', 'families': scored}])
        self.assertEqual(totals['gi.colonoscopy']['complete_case_rate'], 0.0)
        self.assertNotIn('overall', totals)

    def test_complete_case_requires_exact_codes_and_units(self):
        case = EvaluationCase('c2', 'c2.txt', 'txt', (ReferenceCode('43239'),))
        ok = score_case(case, [{'bucket': 'selected', 'code': '43239', 'family': 'gi.egd', 'status': 'ready', 'units': 1}])
        self.assertTrue(ok['gi.egd']['complete_correct'])
        wrong_units = score_case(case, [{'bucket': 'selected', 'code': '43239', 'family': 'gi.egd',
                                         'status': 'ready', 'units': 2}])
        self.assertFalse(wrong_units['gi.egd']['complete_correct'])
