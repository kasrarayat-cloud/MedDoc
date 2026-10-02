"""Readiness (/health/ready/, core.readiness) is separate from liveness, reads its checks from ops/alarms.json, answers
on the host only, and carries counts, ages and fixed labels. Synthetic rows only; no provider or network is involved.
"""
import json
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from core import readiness
from core.admin_console import STALENESS_BOUND
from core.models import Job, ServiceHealth
from core.tests.test_security import SyntheticFixture

HOSTING = Path(__file__).resolve().parents[3] / 'docs/rebuild/v1/production-hosting.md'
ISOLATED = dict(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})


def doc_alert_rows():
    """The signals the section-15 alert table of the hosting document states, in order."""
    text = HOSTING.read_text()
    section = text[text.index('## 15. Alerts'):]
    section = section[:section.index('\n## ', 1)]
    return [line.split('|')[1].strip() for line in section.splitlines()
            if line.startswith('| ') and not line.startswith('| Signal') and not line.startswith('| ---')]


class AlarmTableIsData(TestCase):
    def test_the_document_table_and_the_alarm_data_name_the_same_signals(self):
        data = json.loads(readiness.ALARMS.read_text())
        self.assertEqual(data['contract'], 'quillmd-alarms-v1')
        self.assertEqual(doc_alert_rows(), [row['signal'] for row in data['alarms']])
        for row in data['alarms']:
            with self.subTest(row=row['id']):
                self.assertTrue(row['condition'])
                self.assertIn(row['source'], ('readiness', 'cloudwatch', 'eventbridge', 'healthchecks'))
        # Every readiness row is a check the endpoint evaluates, with the threshold its row states.
        report = readiness.report()
        self.assertEqual([check['id'] for check in report['checks']],
                         [row['id'] for row in data['alarms'] if row['source'] == 'readiness'])
        defaults = {row['id']: row['default'] for row in data['alarms'] if row['source'] == 'readiness'}
        self.assertEqual({check['id']: check['threshold'] for check in report['checks']}, defaults)
        self.assertEqual(defaults['worker_heartbeat'], 2 * int(STALENESS_BOUND.total_seconds()))
        self.assertEqual(defaults['oldest_queued_job'], int(STALENESS_BOUND.total_seconds()))

    def test_the_heartbeat_row_states_the_readiness_gate(self):
        text = ' '.join(HOSTING.read_text().split())
        self.assertIn('/health/ready/', text[text.index('## 15. Alerts'):])

    def test_a_missing_or_malformed_table_is_never_ready(self):
        for label, content in (('missing', None), ('not json', 'x'), ('no readiness rows', json.dumps(
                {'contract': 'quillmd-alarms-v1', 'alarms': []}))):
            with self.subTest(label), patch.object(readiness, 'ALARMS', Path('/nonexistent/alarms.json') if content is None
                                                    else self.temporary(content)):
                value = readiness.report()
                self.assertFalse(value['ready']); self.assertTrue(value['reason'].startswith('alarm_table'))

    def temporary(self, content):
        import tempfile
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'alarms.json'; path.write_text(content)
        return path


@override_settings(**ISOLATED)
class Readiness(SyntheticFixture, TestCase):
    def setUp(self):
        self.scope = self.make_scope('ready')
        readiness._last_beat[0] = 0.0

    def check(self, value, name):
        return next(check for check in value['checks'] if check['id'] == name)

    def job(self, state='queued', age=timedelta(0), started=None):
        row = Job.objects.create(encounter=self.scope[5], user=self.scope[0], request_key=f'ready:{Job.objects.count()}',
                                 state=state, started_at=started)
        Job.objects.filter(pk=row.pk).update(created_at=timezone.now() - age)
        return row

    def test_no_recorded_heartbeat_is_not_ready_and_a_recorded_one_is(self):
        value = readiness.report()
        self.assertFalse(value['ready'])
        self.assertEqual((self.check(value, 'worker_heartbeat')['value'], self.check(value, 'worker_heartbeat')['passed']),
                         (None, False))
        self.assertTrue(readiness.beat())
        self.assertFalse(readiness.beat())  # throttled: one write per HEARTBEAT_EVERY seconds per process
        value = readiness.report()
        self.assertTrue(value['ready'], value)

    def test_a_stale_heartbeat_is_not_ready(self):
        readiness.beat()
        ServiceHealth.objects.filter(key=readiness.HEARTBEAT_KEY).update(computed_at=timezone.now() - timedelta(seconds=601))
        value = readiness.report()
        self.assertFalse(value['ready']); self.assertFalse(self.check(value, 'worker_heartbeat')['passed'])
        self.assertGreaterEqual(self.check(value, 'worker_heartbeat')['value'], 601)
        ServiceHealth.objects.filter(key=readiness.HEARTBEAT_KEY).update(computed_at=timezone.now() - timedelta(seconds=599))
        self.assertTrue(readiness.report()['ready'])  # positive control: inside the default threshold

    def test_queue_depth_oldest_wait_and_processing_health_each_fail_readiness(self):
        readiness.beat()
        self.job(); self.job()
        with override_settings(READINESS_QUEUE_DEPTH='1'):
            value = readiness.report()
            self.assertFalse(value['ready']); self.assertEqual(self.check(value, 'queue_depth')['value'], 2)
        self.assertTrue(readiness.report()['ready'])  # the default depth admits two
        Job.objects.update(state='failed')
        self.job(age=timedelta(seconds=120))
        with override_settings(READINESS_OLDEST_QUEUED_SECONDS='60'):
            value = readiness.report()
            self.assertFalse(self.check(value, 'oldest_queued_job')['passed'])
            self.assertTrue(self.check(value, 'processing_health')['passed'])  # isolated: the console sees no stall yet
        Job.objects.update(state='failed')
        self.job(state='running', started=timezone.now() - STALENESS_BOUND - timedelta(minutes=1))
        value = readiness.report()
        self.assertEqual((self.check(value, 'processing_health')['value'], value['ready']), ('error', False))

    def test_an_invalid_threshold_setting_is_never_ready(self):
        readiness.beat()
        for raw in ('abc', '0', '-5', '1.5'):
            with self.subTest(raw=raw), override_settings(READINESS_QUEUE_DEPTH=raw):
                value = readiness.report()
                self.assertEqual((value['ready'], value['reason']), (False, 'threshold_invalid'))

    def test_the_endpoint_answers_on_the_host_only_and_carries_no_identifier(self):
        readiness.beat(); job = self.job()
        client = Client(REMOTE_ADDR='127.0.0.1')
        response = client.get('/health/ready/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for private in (str(job.pk), self.scope[0].email, self.scope[3].display_name, str(self.scope[5].pk)):
            self.assertNotIn(private, body)
        self.assertEqual(set(json.loads(body)), {'ready', 'checks', 'release'})
        for headers in ({'HTTP_X_REAL_IP': '203.0.113.9'}, {'HTTP_X_FORWARDED_FOR': '203.0.113.9'}):
            with self.subTest(headers=headers):
                self.assertEqual(client.get('/health/ready/', **headers).status_code, 404)  # came through the proxy
        self.assertEqual(Client(REMOTE_ADDR='10.40.1.5').get('/health/ready/').status_code, 404)
        Job.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(hours=1))
        not_ready = client.get('/health/ready/')
        self.assertEqual(not_ready.status_code, 503); self.assertFalse(json.loads(not_ready.content)['ready'])
        self.assertEqual(client.get('/health/').status_code, 200)  # liveness is unchanged and separate

    def test_the_worker_loop_records_its_heartbeat(self):
        self.assertFalse(ServiceHealth.objects.filter(key=readiness.HEARTBEAT_KEY).exists())
        with patch('core.management.commands.worker.run_one', return_value=False), \
                patch('core.management.commands.worker.mark_stale'), \
                patch('core.management.commands.worker.reap_abandoned_voice_uploads'):
            call_command('worker', once=True)
        row = ServiceHealth.objects.get(key=readiness.HEARTBEAT_KEY)
        self.assertTrue(row.healthy); self.assertEqual(row.payload, {})
        self.assertLess((timezone.now() - row.computed_at).total_seconds(), 60)
        self.assertTrue(re.fullmatch(r'[a-z ]+', row.condition))
