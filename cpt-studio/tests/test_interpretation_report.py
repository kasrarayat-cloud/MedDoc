"""The operator's interpretation evidence (Gemini migration slice S07; design/FINAL.md 4.2, 10.3, 13 and 14.7; DECISIONS
D22; design/ADJUDICATION.md P-7): the D22 record a new-path assessment carries, the operator's interpretation section,
the window report and its self-test, and ``manage.py interpretation_report``, which prints every D22 field. Synthetic
rows only; nothing is sent.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import time
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from studio import audit, interpretation, models, operator
from studio.interpretation import holds, report, sentinel
from studio.participants import pricing
from studio.types import sha256_json
from tests.support import factories as f
from tests.test_interpretation_adapter import TRIAL_429, encoded, envelope

TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 2026-10-21\n'
        'Colonoscopy: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold snare.\n')
LEGACY_ENGINE = 'cpt-studio-validation@10'  # the installed legacy engine's label
USAGE = {'promptTokenCount': 5355, 'candidatesTokenCount': 9183, 'thoughtsTokenCount': 120, 'totalTokenCount': 14658}
NOVEMBER = datetime(2026, 11, 9, 12, 0, tzinfo=dt_timezone.utc)
DECEMBER = datetime(2026, 12, 2, 12, 0, tzinfo=dt_timezone.utc)  # the later, higher rate
CLEAN = {'legacy_calls': 0, 'scope': 'assess', 'tool': 'sys.monitoring', 'deny_size': sentinel.DENY_SIZE,
         'positive_control': 'ok'}


def installed(case):
    """The sentinel installed in this process for the test, and the process left as it was found afterwards: installed
    if it was, not installed (and no failure standing) if it was not, whatever the test did to it."""
    was = sentinel.installed()

    def restore():
        if sentinel.installed() != was or sentinel.status()['state'] == 'failed':
            sentinel.uninstall()
            if was:
                sentinel.install()

    case.addCleanup(restore)
    status = sentinel.install()
    if status['state'] != 'ok':
        sentinel.uninstall()
        status = sentinel.install()
    case.assertEqual(status['state'], 'ok', status['reason'])


class Rows:
    """Synthetic rows of every kind the report reads."""

    def __init__(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.user)
        self.rev = f.pasted_revision(self.enc, self.user, TEXT)
        self.routing = models.RoutingRun.objects.create(revision=self.rev, version=interpretation.ROUTING_VERSION,
                                                        result={'version': interpretation.ROUTING_VERSION},
                                                        sha256='1' * 64)

    def run(self, *, provider=interpretation.PROVIDER, state='succeeded', sent=True, http_status=200, body=None,
            usage=None, started_at=NOVEMBER, returned_model=interpretation.MODEL, scope=None, reused_from=None):
        body = encoded(envelope()) if body is None else body
        request = {'contents': [{'parts': [{'text': self.rev.text}]}], 'n': models.ProviderRun.objects.count()}
        return models.ProviderRun.objects.create(
            encounter=self.enc, revision=self.rev, provider=provider, adapter_version=interpretation.ADAPTER_VERSION,
            purpose=interpretation.PURPOSE if provider == interpretation.PROVIDER else 'primary',
            request_sha256=sha256_json(request), request_body=request, contexts=[], state=state, sent=sent,
            http_status=http_status, response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest(),
            usage=dict(usage or {}), requested_model=interpretation.MODEL if provider == interpretation.PROVIDER else '',
            returned_model=returned_model if sent and state == 'succeeded' else '', scope=scope or {},
            started_at=started_at if sent else None, reused_from=reused_from)

    def inventory(self, run, *, state=models.EventInventory.READ, events=None):
        parts = {'events': events or {'passages': [{'id': 'P1'}], 'lesions': [], 'events': [{'id': 'E1'}],
                                      'relations': []},
                 'encounter_facts': {}, 'open_questions': [],
                 'verification': {'problems': [] if state == models.EventInventory.READ else ['Refused.']}}
        return models.EventInventory.objects.create(
            encounter=self.enc, revision=self.rev, provider_run=run,
            interpretation_version=interpretation.INTERPRETATION_VERSION,
            inventory_version=interpretation.INVENTORY_VERSION, text_sha256=self.rev.text_sha256,
            request_sha256=run.request_sha256, response_sha256=run.response_sha256, state=state,
            sha256=sha256_json(parts), **parts)

    def context(self, inventory=None, *, version=interpretation.CONTEXT_VERSION):
        facts = {'service_date': {'value': '2026-10-21', 'origin': 'document', 'evidence': [], 'note': ''}}
        return models.EncounterContext.objects.create(encounter=self.enc, revision=self.rev, facts=facts,
                                                      version=version, sha256=sha256_json(facts),
                                                      event_inventory=inventory)

    def assessment(self, *, engine_version=interpretation.ENGINE_VERSION, context=None, inventory=None,
                   record=None):
        return models.Assessment.objects.create(
            encounter=self.enc, revision=self.rev, context=context or self.context(), routing=self.routing,
            profiles_version='gi-profiles@test', engine_version=engine_version, sha256='0' * 64,
            event_inventory=inventory, interpretation=record)

    def new_path(self, *, sentinel_record=None, run=None):
        """A new-path assessment with its inventory, context and a D22 record built by the builder."""
        run = run or self.run(usage=USAGE)
        inventory = self.inventory(run)
        context = self.context(inventory)
        record = report.interpretation_record(inventory=inventory, context=context, member_date_state='supplies',
                                              sentinel_record=dict(sentinel_record or CLEAN))
        return self.assessment(context=context, inventory=inventory, record=record), inventory, context


def an_operator(username='synthetic-operator'):
    user = f.user(username)
    operator.grant(user, 'Synthetic grant for an interpretation report test.', 'tests')
    return user


class RecordTests(TestCase):
    def setUp(self):
        self.rows = Rows()

    def test_the_record_names_what_made_the_assessment(self):
        assessment, inventory, context = self.rows.new_path()
        record = assessment.interpretation
        self.assertEqual(tuple(record), report.RECORD_KEYS)
        self.assertEqual(record, {
            'engine_version': 'cpt-studio-events@1', 'interpretation_version': 'gemini-events@1',
            'inventory_version': 'gemini-inventory@1',
            'inventory': {'id': str(inventory.pk), 'sha256': inventory.sha256},
            'gemini_run': str(inventory.provider_run_id), 'context': str(context.pk), 'member_date_state': 'supplies',
            'sentinel': CLEAN})
        self.assertEqual(tuple(record['sentinel']), report.SENTINEL_KEYS)
        self.assertEqual(report.record_problems(assessment), [])

    def test_a_record_that_would_not_say_what_made_the_assessment_is_refused(self):
        run = self.rows.run(usage=USAGE)
        inventory = self.rows.inventory(run)
        context = self.rows.context(inventory)
        refused = self.rows.inventory(self.rows.run(), state=models.EventInventory.REFUSED)
        good = {'inventory': inventory, 'context': context, 'member_date_state': {'state': 'agrees'},
                'sentinel_record': dict(CLEAN)}
        report.interpretation_record(**good)
        for label, change in (('a refused inventory', {'inventory': refused, 'context': self.rows.context(refused)}),
                              ('a legacy context', {'context': self.rows.context(inventory, version='gi-context@5')}),
                              ('a context of another inventory', {'context': self.rows.context(refused)}),
                              ('a context with no inventory', {'context': self.rows.context()}),
                              ('a date state that is not JSON', {'member_date_state': object()}),
                              ('a date state that is not finite', {'member_date_state': float('nan')}),
                              ('a sentinel record missing a key', {'sentinel_record': {
                                  key: value for key, value in CLEAN.items() if key != 'tool'}}),
                              ('a sentinel record with another key', {'sentinel_record': {**CLEAN, 'note': 'x'}}),
                              ('no sentinel record', {'sentinel_record': None})):
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    report.interpretation_record(**{**good, **change})

    def test_what_is_wrong_with_a_stored_record_is_named(self):
        assessment, inventory, context = self.rows.new_path()
        record = assessment.interpretation
        other_run = self.rows.run(usage=USAGE)
        cases = {
            'no record': (None, 'carries no interpretation record'),
            'a record lacking a part': ({k: v for k, v in record.items() if k != 'member_date_state'},
                                        'lacks member_date_state'),
            'another inventory': ({**record, 'inventory': {'id': str(other_run.pk), 'sha256': inventory.sha256}},
                                  'another inventory'),
            'another sha256': ({**record, 'inventory': {'id': str(inventory.pk), 'sha256': 'f' * 64}}, 'sha256'),
            'another run': ({**record, 'gemini_run': str(other_run.pk)}, 'another run'),
            'another context': ({**record, 'context': str(other_run.pk)}, 'another context'),
            'a counted legacy call': ({**record, 'sentinel': {**CLEAN, 'legacy_calls': 1}}, 'counted 1 legacy'),
            'another deny set': ({**record, 'sentinel': {**CLEAN, 'deny_size': 100}}, 'deny set of 100'),
            'a failed positive control': ({**record, 'sentinel': {**CLEAN, 'positive_control': 'failed'}},
                                          'positive control'),
            'another tool': ({**record, 'sentinel': {**CLEAN, 'tool': 'settrace'}}, 'another tool'),
            'no sentinel record': ({k: v for k, v in record.items() if k != 'sentinel'}, 'no sentinel record'),
        }
        for label, (stored, expected) in cases.items():
            with self.subTest(label):
                row = self.rows.assessment(context=context, inventory=inventory, record=stored)
                problems = report.record_problems(row)
                self.assertTrue(any(expected in problem for problem in problems), problems)
        bare = self.rows.assessment(record=dict(record))  # names no inventory at all
        self.assertIn('The assessment names no event inventory.', report.record_problems(bare))


class SectionTests(TestCase):
    def setUp(self):
        self.rows = Rows()

    def test_a_legacy_assessment_is_only_said_to_be_one(self):
        legacy = self.rows.assessment(engine_version=LEGACY_ENGINE, context=self.rows.context(version='gi-context@5'))
        self.assertEqual(report.interpretation_section(legacy),
                         {'engine': 'legacy', 'engine_version': LEGACY_ENGINE, 'record': None})

    def test_a_new_path_assessments_section_reads_its_stored_rows(self):
        assessment, inventory, _ = self.rows.new_path()
        section = report.interpretation_section(assessment)
        self.assertEqual((section['engine'], section['engine_version'], section['problems'], section['hold']),
                         ('events', 'cpt-studio-events@1', [], None))
        self.assertEqual(section['record'], assessment.interpretation)
        self.assertEqual({key: section['inventory'][key] for key in ('id', 'state', 'sha256', 'counts')},
                         {'id': str(inventory.pk), 'state': 'read', 'sha256': inventory.sha256,
                          'counts': {'passages': 1, 'lesions': 0, 'events': 1, 'relations': 0}})
        run = section['run']
        expected = pricing.estimate(interpretation.MODEL, USAGE, on=NOVEMBER)['estimated_usd']
        self.assertEqual({key: run[key] for key in ('id', 'state', 'requested_model', 'returned_model', 'usage',
                                                     'estimated_cost')},
                         {'id': str(inventory.provider_run_id), 'state': 'succeeded', 'requested_model': 'gemini-4-argon',
                          'returned_model': 'gemini-4-argon', 'usage': USAGE, 'estimated_cost': expected})
        self.assertNotIn('response_bytes', run)
        self.assertNotIn('request_body', run)
        json.dumps(section)  # JSON as stored

    def test_the_hold_its_run_set_is_shown(self):
        run = self.rows.run(body=encoded(envelope(modelVersion='gemini-4-argon-preview')))
        _, hold = holds.settle(run)
        assessment, _, _ = self.rows.new_path(run=run)
        section = report.interpretation_section(assessment)
        self.assertEqual((section['hold']['id'], section['hold']['reason']), (str(hold.pk), 'model'))


class WindowTests(TestCase):
    def setUp(self):
        installed(self)
        self.rows = rows = Rows()
        rows.run(usage=USAGE)  # before the window
        rows.assessment(engine_version=LEGACY_ENGINE, context=rows.context(version='gi-context@5'))
        time.sleep(0.002)
        self.since = timezone.now()
        time.sleep(0.002)
        self.answered = rows.run(usage=USAGE)
        self.december = rows.run(usage={'promptTokenCount': 1000, 'candidatesTokenCount': 2000,
                                         'totalTokenCount': 3000}, started_at=DECEMBER)
        self.quota = rows.run(state='failed', http_status=429, body=TRIAL_429.read_bytes(), usage={})
        self.paused = rows.run(state='not_sent', sent=False, http_status=None, body=b'',
                               scope={'held': holds.HELD_HOLD})
        rows.run(state='unknown', http_status=None, body=b'', usage={})
        rows.run(state='succeeded', sent=False, reused_from=self.answered, usage={})
        rows.run(provider='corti', usage={'credits': 3})  # another provider: not a Gemini run
        self.clean, _, _ = rows.new_path(run=self.answered)
        rows.inventory(rows.run(usage={}), state=models.EventInventory.REFUSED)
        rows.new_path(run=self.december, sentinel_record={**CLEAN, 'legacy_calls': 2})
        rows.assessment()  # new-path, with no inventory and no record
        rows.assessment(engine_version=LEGACY_ENGINE, context=rows.context(version='gi-context@5'))
        audit.record(rows.ws, sentinel.TRIPPED, encounter=rows.enc, entry='persist_assessment', reason='executed',
                     refused=True)
        audit.record(rows.ws, sentinel.TRIPPED, encounter=rows.enc, entry='review view', reason='executed',
                     refused=False)
        self.hold = holds.settle(self.quota)[1]
        released = holds.settle(rows.run(state='failed', http_status=401, body=b''))[1]
        self.release = models.InterpreterHoldRelease.objects.create(hold=released, released_by=an_operator(),
                                                                   note='Synthetic release.')

    def test_the_window_reports_every_d22_quantity(self):
        found = report.window(self.since)
        runs = found['gemini_runs']
        self.assertEqual(runs['total'], 8)  # the earlier run and the Corti run are outside it
        self.assertEqual(runs['by_state'], {'failed': 2, 'not_sent': 1, 'succeeded': 4, 'unknown': 1})
        self.assertEqual((runs['sent'], runs['reused']), (6, 1))
        self.assertEqual(runs['requested_models'], {'gemini-4-argon': 8})
        self.assertEqual(runs['returned_models'], {'(none)': 5, 'gemini-4-argon': 3})
        self.assertEqual(runs['paused'], {holds.HELD_HOLD: 1})
        self.assertEqual(runs['usage'], {'promptTokenCount': 6355, 'candidatesTokenCount': 11183,
                                         'thoughtsTokenCount': 120, 'totalTokenCount': 17658,
                                         'cachedContentTokenCount': 0, 'toolUsePromptTokenCount': 0})
        expected = (Decimal(pricing.estimate(interpretation.MODEL, USAGE, on=NOVEMBER)['estimated_usd'])
                    + Decimal(pricing.estimate(interpretation.MODEL, self.december.usage, on=DECEMBER)['estimated_usd']))
        self.assertEqual(Decimal(runs['cost']['estimated_usd']), expected)
        # sent and not priced: the 429, the 401, the unknown outcome and the refused answer, none reporting a usage
        self.assertEqual((runs['cost']['priced_runs'], runs['cost']['unpriced_runs']), (2, 4))
        self.assertEqual(found['inventories'], {'read': 2, 'refused': 1})
        assessments = found['assessments']
        self.assertEqual(assessments['by_engine_version'], {'cpt-studio-events@1': 3, LEGACY_ENGINE: 1})
        self.assertEqual({key: assessments[key] for key in ('total', 'new_path', 'legacy_engine', 'without_inventory',
                                                            'without_sentinel_record', 'legacy_calls',
                                                            'with_legacy_calls')},
                         {'total': 4, 'new_path': 3, 'legacy_engine': 1, 'without_inventory': 1,
                          'without_sentinel_record': 1, 'legacy_calls': 2, 'with_legacy_calls': 1})
        self.assertEqual(assessments['off_pins'], 0)
        # the record problems, read as record_problems reads them, without the legacy-call count (checked apart): only
        # the bare new-path assessment has one
        self.assertEqual((assessments['with_record_problems'], assessments['record_problems']),
                         (1, {'The assessment carries no interpretation record.': 1}))
        self.assertEqual((assessments['deny_sizes'], assessments['positive_controls'], assessments['tools']),
                         ({'2548': 2}, {'ok': 2}, {'sys.monitoring': 2}))
        self.assertEqual(found['trips'], {'total': 2, 'refused': 1, 'recorded': 1, 'by_reason': {'executed': 2},
                                          'by_entry': {'persist_assessment': 1, 'review view': 1},
                                          'unavailable': {'total': 0, 'refused': 0, 'recorded': 0, 'install': {}}})
        self.assertEqual({key: found['sentinel'][key] for key in ('state', 'deny_size', 'positive_control', 'tool')},
                         {'state': 'ok', 'deny_size': 2548, 'positive_control': 'ok', 'tool': 'sys.monitoring'})
        self.assertEqual(set(found['sentinel']['totals']), set(sentinel.LABELS))
        hold = found['hold']
        self.assertEqual([item['id'] for item in hold['standing']], [str(self.hold.pk)])
        self.assertEqual(hold['set'], {'auth': 1, 'quota': 1})
        self.assertEqual(hold['released'], [{'id': str(self.release.pk), 'hold': str(self.release.hold_id),
                                             'by': 'synthetic-operator', 'at': self.release.created_at.isoformat()}])
        self.assertEqual((hold['held'], hold['process_mode'], hold['process_paused']),
                         (True, 'disabled', holds.HELD_DISABLED))
        self.assertEqual(found['interpreter'], {
            'process_mode': 'disabled', 'model': 'gemini-4-argon', 'provider': 'gemini',
            'adapter_version': 'gemini-generate@cptstudio-1', 'interpretation_version': 'gemini-events@1',
            'inventory_version': 'gemini-inventory@1', 'engine_version': 'cpt-studio-events@1'})
        json.dumps(found)

    def test_the_window_is_half_open_and_aware(self):
        later = report.window(timezone.now())
        self.assertEqual((later['gemini_runs']['total'], later['assessments']['total'], later['trips']['total']),
                         (0, 0, 0))
        earlier = report.window(self.since - (timezone.now() - self.since) * 10, self.since)
        self.assertEqual((earlier['gemini_runs']['total'], earlier['assessments']['by_engine_version']),
                         (1, {LEGACY_ENGINE: 1}))
        for since, until in ((datetime(2026, 11, 9), None), (self.since, self.since), (self.since, datetime(2026, 1, 1))):
            with self.subTest(since=since, until=until), self.assertRaises(ValueError):
                report.window(since, until)

    def test_the_self_test_fails_on_what_the_window_holds(self):
        test = report.self_test(report.window(self.since))
        self.assertFalse(test['passed'])
        failed = [item['name'] for item in test['checks'] if not item['ok']]
        self.assertEqual(failed, ['no new-path legacy execution recorded',
                                  'every new-path assessment carries its record', 'no sentinel trip',
                                  'no legacy-engine assessment'])
        clean = report.self_test(report.window(timezone.now()))
        self.assertTrue(clean['passed'], clean)
        self.assertEqual(tuple(item['name'] for item in clean['checks']), report.SELF_TEST)
        self.assertNotIn('interpreter mode', report.SELF_TEST)  # a one-shot's mode is its own, never checked as the worker's

    def test_the_model_constant_is_checked_against_d13s_literal(self):
        # interpretation.MODEL, adapter.MODEL and adapter.ENDPOINT are one value: comparing them with each other passes
        # whatever the model is
        from studio.interpretation import adapter

        clean = {item['name']: item for item in report.self_test(report.window(timezone.now()))['checks']}
        self.assertTrue(clean['model constant']['ok'], clean['model constant'])
        self.assertEqual((report.D13_MODEL, report.FINAL_ENDPOINT),
                         ('gemini-4-argon',
                          'https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent'))
        changed = 'gemini-4-argon-preview'  # the reviewer's case: the constant edited in interpretation/__init__.py
        with mock.patch.object(interpretation, 'MODEL', changed), mock.patch.object(adapter, 'MODEL', changed), \
                mock.patch.object(adapter, 'ENDPOINT', adapter.ENDPOINT.replace('gemini-4-argon', changed)):
            test = report.self_test(report.window(timezone.now()))
        check = {item['name']: item for item in test['checks']}['model constant']
        self.assertFalse(check['ok'])
        self.assertFalse(test['passed'])
        self.assertIn('D13 says gemini-4-argon', check['detail'])
        with mock.patch.object(adapter, 'ENDPOINT', adapter.ENDPOINT.replace('v1beta', 'v1')):  # the endpoint alone
            self.assertFalse({item['name']: item for item in report.self_test(report.window(timezone.now()))['checks']}
                             ['model constant']['ok'])

    def test_a_record_that_names_another_inventory_fails_the_self_test(self):
        # the reviewer's case: a complete, on-pin sentinel record and an inventory on the assessment, but the record
        # names another inventory and run than the one the assessment was made from
        since = timezone.now()
        _, inventory, _ = self.rows.new_path()
        other = self.rows.inventory(self.rows.run(usage=USAGE))
        context = self.rows.context(other)
        record = report.interpretation_record(inventory=other, context=context, member_date_state='supplies',
                                              sentinel_record=dict(CLEAN))
        wrong = self.rows.assessment(context=context, inventory=inventory, record=record)
        self.assertEqual(report.record_problems(wrong), ['The record names another inventory than the assessment does.'])
        found = report.window(since)
        self.assertEqual({key: found['assessments'][key] for key in ('new_path', 'without_inventory',
                                                                      'without_sentinel_record', 'off_pins',
                                                                      'with_record_problems')},
                         {'new_path': 2, 'without_inventory': 0, 'without_sentinel_record': 0, 'off_pins': 0,
                          'with_record_problems': 1})
        test = report.self_test(found)
        self.assertEqual([item['name'] for item in test['checks'] if not item['ok']],
                         ['every new-path assessment carries its record'])
        self.assertIn('The record names another inventory than the assessment does. x1',
                      dict(line.split(': ', 1) for line in report.render(found))['new-path records with problems'])

    def test_a_process_that_could_not_count_is_shown_and_fails_the_self_test(self):
        # FINAL 10.2: a web process whose sentinel failed records it on its first read naming an encounter; the
        # installer's one-shot, whose own sentinel installs cleanly, must then not pass
        since = timezone.now()
        sentinel.uninstall()
        sys.monitoring.use_tool_id(4, 'synthetic-debugger')
        try:
            with self.assertLogs(sentinel.log, 'ERROR'):
                self.assertEqual(sentinel.install()['state'], 'failed')
                with sentinel.scope(sentinel.NEW_PATH, entry='GET /api/encounters/x'):
                    sentinel.observe('review view', encounter=self.rows.enc)
        finally:
            sys.monitoring.free_tool_id(4)
        sentinel.uninstall()  # the one-shot is another process: its own sentinel installs
        self.assertEqual(sentinel.install()['state'], 'ok')
        found = report.window(since)
        self.assertEqual(found['trips']['unavailable'],
                         {'total': 1, 'refused': 0, 'recorded': 1,
                          'install': {"sys.monitoring tool 4 is held by 'synthetic-debugger'": 1}})
        test = report.self_test(found)
        self.assertEqual([item['name'] for item in test['checks'] if not item['ok']], ['no sentinel trip'])
        lines = dict(line.split(': ', 1) for line in report.render(found, test))
        self.assertTrue(lines['sentinel unavailable in a process'].startswith(
            '1 recorded by a process whose sentinel could not count (0 refused writes, 1 reads); sys.monitoring tool 4 '
            'is held by \'synthetic-debugger\' x1'), lines['sentinel unavailable in a process'])
        self.assertTrue(lines['sentinel install'].startswith('ok;'))  # the one-shot's own sentinel


class CommandTests(TestCase):
    def setUp(self):
        installed(self)
        self.rows = Rows()

    def run_command(self, *args):
        out = io.StringIO()
        try:
            call_command('interpretation_report', *args, stdout=out)
        except CommandError as exc:
            exc.output = out.getvalue()
            raise
        return out.getvalue()

    def fields(self, text):
        return [line.split(': ', 1)[0] for line in text.splitlines() if not line.startswith('self-test')]

    def test_every_d22_field_is_printed_once_in_order(self):
        self.rows.new_path()
        text = self.run_command('--since', '2026-01-01T00:00:00Z')
        self.assertEqual(self.fields(text), list(report.D22_FIELDS))
        lines = dict(line.split(': ', 1) for line in text.splitlines())
        self.assertTrue(all(lines[field].strip() for field in report.D22_FIELDS))  # each with its value
        self.assertEqual(lines['model'].split(' ')[0], 'gemini-4-argon')
        self.assertIn('2548 code objects (pinned 2548', lines['sentinel deny-set size'])
        self.assertEqual(lines['sentinel positive control'], 'ok')
        self.assertTrue(lines['sentinel install'].startswith('ok; sys.monitoring tool 4 (cpt-studio-sentinel)'))
        self.assertEqual(lines['new-path assessments'], '1')
        self.assertEqual(lines['new-path records with problems'], '0')
        self.assertIn('0 over 1 new-path assessments', lines['sentinel legacy calls recorded'])
        self.assertTrue(lines['sentinel unavailable in a process'].startswith('0 recorded'))
        self.assertEqual(lines['interpreter hold'], 'none standing; installation-wide')
        self.assertTrue(lines['interpreter mode (this process)'].startswith('disabled; this process\'s own setting'))
        self.assertNotIn('self-test', text)

    def test_json_carries_the_same_report(self):
        found = json.loads(self.run_command('--since', '2026-01-01T00:00:00Z', '--json'))
        self.assertEqual(set(found), {'report', 'self_test'})
        self.assertIsNone(found['self_test'])
        self.assertEqual(set(found['report']), {'window', 'interpreter', 'gemini_runs', 'inventories', 'assessments',
                                                'trips', 'sentinel', 'hold'})
        self.assertEqual(found['report']['window']['since'], '2026-01-01T00:00:00+00:00')

    def test_the_self_test_passes_on_a_clean_window(self):
        self.rows.new_path()
        text = self.run_command('--since', '2026-01-01T00:00:00Z', '--self-test')
        for name in report.SELF_TEST:
            self.assertIn(f'self-test {name}: PASS (', text)
        self.assertTrue(text.rstrip().endswith('self-test: PASSED'))

    def test_the_self_test_fails_and_says_why(self):
        self.rows.assessment(engine_version=LEGACY_ENGINE, context=self.rows.context(version='gi-context@5'))
        self.rows.new_path(sentinel_record={**CLEAN, 'legacy_calls': 3})
        with self.assertRaises(CommandError) as failed:
            self.run_command('--since', '2026-01-01T00:00:00Z', '--self-test')
        self.assertEqual(str(failed.exception), 'The interpretation self-test failed: no new-path legacy execution '
                                                'recorded, no legacy-engine assessment.')
        self.assertIn('self-test no legacy-engine assessment: FAIL (1 in the window)', failed.exception.output)
        self.assertTrue(failed.exception.output.rstrip().endswith('self-test: FAILED'))

    def test_a_record_off_its_pins_fails_the_self_test(self):
        for change in ({'deny_size': 100}, {'tool': 'settrace'}, {'positive_control': 'failed'}):
            with self.subTest(change=change):
                self.rows.new_path(sentinel_record={**CLEAN, **change})
                with self.assertRaises(CommandError) as failed:
                    self.run_command('--since', '2026-01-01T00:00:00Z', '--self-test')
                self.assertEqual(str(failed.exception), 'The interpretation self-test failed: every new-path assessment '
                                                        'carries its record.')
                self.assertIn('new-path records off their pins: ', failed.exception.output)
                models.Assessment.objects.filter(pk__isnull=False)  # rows stay; the next case adds one more
        found = report.window(datetime(2026, 1, 1, tzinfo=dt_timezone.utc))
        self.assertEqual(found['assessments']['off_pins'], 3)

    def test_the_mode_printed_is_this_processs_own_and_never_checked_as_the_installations(self):
        # FINAL 13: a one-shot runs with the interpreter disabled unless it is given a mode, so checking its own mode
        # either fails every correct install or passes whatever mode the worker runs with
        self.rows.new_path()
        for mode in ('disabled', 'live'):
            with self.subTest(mode=mode), override_settings(GEMINI_MODE=mode):
                text = self.run_command('--since', '2026-01-01T00:00:00Z', '--self-test')
                self.assertIn(f'interpreter mode (this process): {mode}; this process\'s own setting - a one-shot runs '
                              'with the interpreter disabled unless it is given a mode', text)
                self.assertNotIn('self-test interpreter mode', text)
                self.assertTrue(text.rstrip().endswith('self-test: PASSED'))
        with self.assertRaises(CommandError) as refused:  # the option that checked the one-shot's own setting is gone
            self.run_command('--since', '2026-01-01T00:00:00Z', '--self-test', '--expect-mode', 'live')
        self.assertIn('unrecognized arguments: --expect-mode live', str(refused.exception))

    def test_a_failed_sentinel_fails_the_self_test(self):
        sentinel.uninstall()  # installed()'s cleanup restores the process
        with mock.patch.dict(sentinel.PINNED_SIZES, {'studio/gi/cues.py': 15}), self.assertLogs(sentinel.log, 'ERROR'):
            with self.assertRaises(CommandError) as failed:
                self.run_command('--since', '2026-01-01T00:00:00Z', '--self-test')
        self.assertEqual(str(failed.exception), 'The interpretation self-test failed: sentinel installed, deny set as '
                                                'pinned, positive control, positive control trips.')
        self.assertIn('sentinel install: failed (the deny set differs from its pins', failed.exception.output)

    def test_the_report_installs_its_own_processs_sentinel(self):
        # ADJUDICATION R-1: every process, one-shots included
        sentinel.uninstall()  # installed()'s cleanup restores the process
        self.assertFalse(sentinel.installed())
        self.run_command('--since', '2026-01-01T00:00:00Z')
        self.assertTrue(sentinel.installed())

    def test_refusals(self):
        for args, expected in ((('--since', '2026-11-09T09:00:00'), 'with its offset'),
                               (('--since', 'yesterday'), 'with its offset'),
                               (('--since', '2026-11-09T09:00:00Z', '--until', '2026-11-09T08:00:00Z'),
                                'ends after it starts')):
            with self.subTest(args=args):
                with self.assertRaises(CommandError) as refused:
                    self.run_command(*args)
                self.assertIn(expected, str(refused.exception))
        with self.assertRaises(CommandError):
            call_command('interpretation_report', stdout=io.StringIO())  # --since is required
