"""Round 4: the download verifier mirrors a confirmed exclusion (decision action 'confirm').

A confirmed exclusion stays in the excluded list and was never reinstated, even when the history holds an earlier,
revoked reinstatement of the same proposal (the verifier's re-derivation would otherwise find that one).

    cd cpt-studio && .venv/bin/python -m unittest discover -s ops -p 'test_r4_lead_confirm.py' -v
"""
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_verify_downloads_r4', HERE / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_verify_downloads_r4'] = vd
_spec.loader.exec_module(vd)


def api_with_confirmed_exclusion():
    proposal = {'id': 'p-exc', 'code': '45378', 'bucket': 'excluded', 'status': 'excluded', 'reinstatable': True,
                'family_label': 'Colonoscopy', 'decision_state': 'exclusion_confirmed', 'reinstated_by': None,
                'decision': {'id': 'd-confirm', 'proposal_id': 'p-exc', 'code': '45378', 'action': 'confirm',
                             'reviewer': 'Reviewer One', 'reviewer_kind': 'human', 'carried_from': None}}
    history = [
        {'id': 'd-reinstate', 'proposal_id': 'p-exc', 'code': '45378', 'action': 'reinstate', 'reviewer': 'Reviewbot',
         'reviewer_kind': 'agent', 'carried_from': None, 'invalidated': None},
        {'id': 'd-revoke', 'proposal_id': 'p-exc', 'code': '45378', 'action': 'revoke', 'reviewer': 'Reviewbot',
         'reviewer_kind': 'agent', 'carried_from': None, 'invalidated': None},
        {**proposal['decision'], 'invalidated': None},
    ]
    return {'assessment': {'proposals': [proposal]}, 'decisions': {'history': history}}


class ConfirmedExclusionTests(unittest.TestCase):
    def test_a_confirmed_exclusion_is_listed_as_excluded_in_both_kinds(self):
        proposal = api_with_confirmed_exclusion()['assessment']['proposals'][0]
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind=kind):
                self.assertEqual(vd.expected_list(proposal, kind), 'excluded')

    def test_a_confirmed_exclusion_was_never_reinstated(self):
        item = vd.items_from_api(api_with_confirmed_exclusion(), 'reviewed')['p-exc']
        self.assertEqual((item.item_list, item.action), ('excluded', 'confirm'))
        self.assertEqual((item.derived_by, item.derived_kind), ('', ''))  # the revoked agent reinstatement is not it
        self.assertEqual((item.reinstated_by, item.reinstated_by_kind), ('', ''))

    def test_a_recorded_confirmation_matches_the_persisted_state(self):
        doc = {'decisions': [{'http_status': 201, 'proposal_id': 'p-exc', 'code': '45378', 'action': 'confirm'}]}
        result = vd._decisions_match('doc', doc, api_with_confirmed_exclusion())
        self.assertEqual(result.status, 'pass', result.detail)


if __name__ == '__main__':
    unittest.main()
