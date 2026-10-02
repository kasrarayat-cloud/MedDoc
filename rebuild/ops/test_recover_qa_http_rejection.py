"""Counterexamples for the exact financial declaration's comparison."""
import copy
import unittest
from decimal import Decimal
try:
    from .recover_qa_http_rejection import validate_resolution
except ImportError:
    from recover_qa_http_rejection import validate_resolution


class ExactResolution(unittest.TestCase):
    def setUp(self):
        self.before = {
            'job': {'id': 'j', 'state': 'reconciliation', 'finished_at': None,
                    'request_key': 'live:key', 'config': {'mode': 'live'},
                    'encounter_id': 'e', 'provider_request_id': 'req'},
            'reservations': [{'id': 'r', 'wallet_id': 'w', 'amount': Decimal('.3'), 'state': 'held'}],
            'wallets': [{'id': 'w', 'balance': Decimal('10'), 'reserved': Decimal('.8')}],
            'unrelated_reservations': [{'id': 'u', 'job_id': 'other', 'wallet_id': 'w',
                                        'amount': Decimal('.5'), 'state': 'held'}],
            'ledger': [{'id': 'old', 'amount': Decimal('10')}], 'platform_cost_count': 0,
            'cost_reconciliation_count': 0, 'usage_count': 0, 'receipt_count': 0,
            'immutable_financial_rows': {},
            'resolution_audits': [],
        }
        self.after = copy.deepcopy(self.before)
        self.after['job'].update(state='failed', finished_at='now', request_key='ended:key')
        self.after['reservations'][0]['state'] = 'released'
        self.after['wallets'][0]['reserved'] = Decimal('.5')
        self.after['resolution_audits'] = [{'id': 'resolution'}]

    def test_exact_release_preserves_other_job(self):
        validate_resolution(self.before, self.after)

    def test_wiping_all_reserved_money_is_rejected(self):
        self.after['wallets'][0]['reserved'] = Decimal('0')
        with self.assertRaises(RuntimeError): validate_resolution(self.before, self.after)

    def test_moved_or_resized_reservation_is_rejected(self):
        for key, value in [('wallet_id', 'another'), ('amount', Decimal('.4')), ('id', 'substitute')]:
            after = copy.deepcopy(self.after); after['reservations'][0][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): validate_resolution(self.before, after)

    def test_unrelated_released_or_deleted_hold_is_rejected(self):
        for rows in ([], [{**self.after['unrelated_reservations'][0], 'state': 'released'}]):
            after = copy.deepcopy(self.after); after['unrelated_reservations'] = rows
            with self.subTest(rows=rows), self.assertRaises(RuntimeError): validate_resolution(self.before, after)

    def test_credit_or_new_financial_evidence_is_rejected(self):
        for key, value in [('platform_cost_count', 1), ('cost_reconciliation_count', 1),
                           ('usage_count', 1), ('receipt_count', 1), ('ledger', [])]:
            after = copy.deepcopy(self.after); after[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): validate_resolution(self.before, after)
        self.after['wallets'][0]['balance'] += 1
        with self.assertRaises(RuntimeError): validate_resolution(self.before, self.after)

    def test_unrelated_wallet_change_is_rejected(self):
        row = {'id': 'other-wallet', 'balance': Decimal('10'), 'reserved': Decimal('2')}
        self.before['wallets'].append(row)
        self.after['wallets'].append(copy.deepcopy(row))
        validate_resolution(self.before, self.after)
        self.after['wallets'][-1]['balance'] = Decimal('0')
        with self.assertRaises(RuntimeError): validate_resolution(self.before, self.after)

    def test_unrelated_existing_financial_row_change_is_rejected(self):
        self.before['immutable_financial_rows']['Usage'] = [{'id': 'u', 'actual_cost': Decimal('.1')}]
        self.after['immutable_financial_rows']['Usage'] = [{'id': 'u', 'actual_cost': Decimal('1')}]
        with self.assertRaises(RuntimeError): validate_resolution(self.before, self.after)

    def test_provider_or_job_evidence_substitution_is_rejected(self):
        for key, value in [('provider_request_id', 'other'), ('config', {'mode': 'fixture'}),
                           ('encounter_id', 'other'), ('request_key', 'live:key')]:
            after = copy.deepcopy(self.after); after['job'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): validate_resolution(self.before, after)


if __name__ == '__main__': unittest.main()
