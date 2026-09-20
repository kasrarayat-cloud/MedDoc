"""Offline prepaid audit and import failures. Never contacts B2."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ops import offsite_renewal as r, test_offsite_account_audit as fixture


class RenewalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state, self.secret, self.evidence = [self.root / n for n in ('state', 'secret', 'evidence')]
        for path in (self.state, self.secret, self.evidence): path.mkdir(mode=0o700)
        self.old = self.evidence / 'original'; self.old.mkdir(mode=0o700)
        self.at = datetime(2026, 9, 20, 22, tzinfo=timezone.utc)
        self.start = self.at.replace(day=21, hour=0); self.end = self.start + timedelta(hours=18)
        self.policy = dict(observed_at='2026-09-20T20:16:35+00:00', valid_until='2026-09-21T20:16:35+00:00',
            bucket_id='bucket', prefix='quillmd-fresh/synthetic/', daily_request_budget=500,
            daily_download_budget_bytes=100_000_000)
        self.journal = dict(version=2, day='2026-09-20', requests=422, download_bytes=98_474_544,
            days={'2026-09-20': dict(requests=422, download_bytes=98_474_544)}, legacy_import=None, external_reservations=[])
        self.write(self.state/'budget.json', self.journal); self.write(self.secret/'policy.json', self.policy)
        for obj, name, value in ((r, 'STATE', self.state/'renewal'), (r, 'ACCOUNT_ID', 'account'),
            (r.engine, 'STATE', self.state), (r.engine, 'POLICY', self.secret/'policy.json'),
            (r.allocation, 'EVIDENCE_ROOT', self.evidence), (r.allocation, 'CONTRACT', self.secret/'contract.json')):
            p = patch.object(obj,name,value); p.start(); self.addCleanup(p.stop)
        p = patch.object(r.engine, 'policy', side_effect=lambda *a, **k: dict(self.policy)); p.start(); self.addCleanup(p.stop)
        self.write(self.old/'operating-evidence.json', {'provider_caps_observation': {'observed_at': 'historical-fixture'}})
        self.write(self.secret/'contract.json', {'evidence_directory': str(self.old), 'operating_evidence': {
            'name':'operating-evidence.json','local_sha256':r.installer.digest((self.old/'operating-evidence.json').read_bytes())}})

    def write(self,path,value): r.engine.atomic(path,value)

    def issue(self):
        value = r.issue_ticket(self.start.isoformat(),self.end.isoformat(),'a'*40,at=self.at)
        self.ticket_path=Path(value['ticket_path']); self.ticket=json.loads(self.ticket_path.read_bytes())
        return value

    def returned(self,status='verified_over_observed_interval'):
        ticks=iter(self.start+timedelta(seconds=n) for n in range(1,50))
        value=r.collector.collect({},self.ticket_path.read_bytes(),transport_factory=fixture.FixtureTransport,clock=lambda:next(ticks))
        self.assertEqual(value['status'],'verified_over_observed_interval')
        value['status']=status; self.result_path=self.root/'result.json'; self.write(self.result_path,value)
        return value

    def accept(self):
        return r.import_result(self.result_path,self.ticket['ticket_id'],'a'*40,at=self.start+timedelta(minutes=1))

    def test_future_reservation_preserves_today_and_rollover(self):
        self.assertEqual(self.issue()['provider_calls'],0)
        value=r.engine.budget_ledger(self.state/'budget.json',self.start)
        self.assertEqual(value['days']['2026-09-20'],self.journal['days']['2026-09-20'])
        self.assertEqual((value['requests'],value['download_bytes']),(20,8388608))
        self.assertEqual(json.loads((self.state/'budget.json').read_bytes())['requests'],422)
        with self.assertRaises(r.Refusal): self.issue()

    def test_today_and_competing_future_consumption_refuse_before_ticket(self):
        with self.assertRaisesRegex(r.Refusal,'budget_exhausted'):
            r.issue_ticket((self.at+timedelta(seconds=1)).isoformat(),self.at.replace(hour=23).isoformat(),'a'*40,at=self.at)
        self.assertFalse(r.STATE.exists())
        value=copy.deepcopy(self.journal); value['days']['2026-09-21']=dict(requests=490,download_bytes=99_000_000)
        self.write(self.state/'budget.json',value)
        with self.assertRaisesRegex(r.Refusal,'budget_exhausted'): self.issue()

    def test_competing_execution_refuses(self):
        with r.engine.exclusion(self.state):
            with self.assertRaises(r.engine.Refusal): self.issue()
        self.assertEqual(json.loads((self.state/'budget.json').read_bytes()),self.journal)

    def test_ticket_publication_failure_preserves_charge(self):
        original=r.engine.backup.write_private
        def fail(path,data):
            if str(path).endswith('.ticket.json'): raise OSError('fixture disk')
            return original(path,data)
        with patch.object(r.engine.backup,'write_private',side_effect=fail):
            with self.assertRaises(OSError): self.issue()
        self.assertEqual(json.loads((self.state/'budget.json').read_bytes())['days']['2026-09-21']['requests'],20)
        self.assertEqual(list(r.STATE.glob('*.ticket.json')),[])

    def test_failed_audit_preserves_policy_and_all_reservations(self):
        self.issue(); self.returned('failed')
        before=[p.read_bytes() for p in (self.state/'budget.json',self.secret/'policy.json')]
        with self.assertRaisesRegex(r.Refusal,'audit_failed'): self.accept()
        self.assertEqual(before,[p.read_bytes() for p in (self.state/'budget.json',self.secret/'policy.json')])
        status=r.renewal_status(self.start+timedelta(minutes=1))
        self.assertEqual(status['state'],'failed'); self.assertEqual(status['valid_until'],self.policy['valid_until'])
        self.assertFalse(status['unattended_available'])

    def test_concurrent_policy_change_is_preserved(self):
        self.issue(); self.returned(); self.write(self.secret/'policy.json',dict(self.policy,concurrent_change=True))
        with self.assertRaisesRegex(r.Refusal,'policy_conflict'): self.accept()
        self.assertTrue(json.loads((self.secret/'policy.json').read_bytes())['concurrent_change'])

    def test_invalid_json_result_is_visible_without_changing_policy(self):
        self.issue(); self.returned()
        self.result_path.write_bytes(b'{incomplete fixture')
        before=(self.secret/'policy.json').read_bytes()
        with self.assertRaisesRegex(r.Refusal,'evidence_invalid'): self.accept()
        self.assertEqual(r.read_state()['state'],'failed')
        self.assertEqual((self.secret/'policy.json').read_bytes(),before)

    def test_valid_import_preserves_original_bytes_caps_and_no_refunds(self):
        self.issue(); audit=self.returned(); before=(self.state/'budget.json').read_bytes()
        def install(directory,commit,**options):
            self.assertEqual((directory/'account-audit.json').read_bytes(),self.result_path.read_bytes())
            self.assertEqual((directory/'ticket.json').read_bytes(),self.ticket_path.read_bytes())
            updated=json.loads((directory/'operating-evidence.json').read_bytes())
            self.assertTrue(updated['caps_are_historical'])
            self.assertEqual(updated['policy_candidate']['observed_at'],audit['scans'][-1]['completed_at'])
            self.assertEqual(options['expected_previous_sha256'],self.ticket['expected_policy_sha256'])
            return {'success':True,'provider_calls':0}
        with patch.object(r.installer,'install_pair',side_effect=install): self.assertTrue(self.accept()['success'])
        self.assertEqual((self.state/'budget.json').read_bytes(),before)
        self.assertEqual(r.read_state()['state'],'installed')
        with self.assertRaises(r.Refusal): self.accept()
        self.assertEqual(r.read_state()['state'],'installed')

    def test_ticket_expiry_display_keeps_original_policy_deadline(self):
        self.issue(); status=r.renewal_status(self.end)
        self.assertEqual((status['state'],status['reason_code']),('failed','ticket_expired'))
        self.assertEqual(status['valid_until'],self.policy['valid_until'])

if __name__=='__main__': unittest.main()
