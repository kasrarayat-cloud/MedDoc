"""The operator's interpretation evidence of design v2 (docs/gemini-migration/FINAL-V2.md 5.7 measure 9, 6.2 and 7.4;
AMENDMENT-1 9.2; step 5c of its 8.1): interpretation/report.py and ``manage.py interpretation_report`` over v2 rows -
both Gemini runs (pass 1, purpose interpretation, and the appraisal, purpose appraisal), their usage and estimated cost
and the sums, the appraisal's health and coherence, the retired calls, and the v1 rows counted apart. Synthetic rows
only (tests/v2/test_readers.V2World); nothing is sent.

The step's done-when "the report shows both runs and the usage sums": the record names both runs; the operator's section
shows both runs with their usage and cost and the sums of the two, and every Gemini run of the encounter by purpose with
the sums; the window report counts and sums the runs by purpose; ``--encounter`` prints them.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from studio import interpretation, models
from studio.interpretation import report, sentinel, store
from studio.participants import pricing
from tests.test_interpretation_report import CLEAN, NOVEMBER, installed
from tests.v2 import test_facts as TF
from tests.v2.test_readers import USAGE, V2World

CLEAN_V2 = {**CLEAN, report.RETIRED_CALLS: 0}
HEALTH = {'pairs': 10, 'not_rejected': 1, 'claims': 12, 'established': 9, 'verdicts': 22, 'missing': 0, 'refused': []}
COHERENCE = {'established': 9, 'incoherent': 1, 'uninformative': 0, 'contradicted': 1, 'qualified': 0, 'unclear': 1,
             'detached': 0, 'missing': 0, 'control_missing': 0}


def with_health(fields):
    """A v2 row's fields with settle's health and coherence recorded (TF.report records empty ones), resealed."""
    fields = dict(fields)
    fields['verification'] = dict(fields['verification'], health=HEALTH, coherence=COHERENCE)
    fields['sha256'] = store.content_sha256_v2(fields)
    return fields


def v2_assessment(sentinel_record=None, transform=None):
    """A v2 world (tests/v2/test_readers.V2World) whose assessment carries the record interpretation_record builds for
    its inventory (the dispatch: the v2 record), written at creation (Assessment rows are immutable)."""
    world = V2World(transform=transform, sentinel_record=sentinel_record or CLEAN_V2)
    return world, models.Assessment.objects.get(pk=world.assessment.pk)


class RecordTests(TestCase):
    def test_the_v2_record_names_both_runs_and_the_retired_calls(self):
        world, assessment = v2_assessment()
        record = assessment.interpretation
        self.assertEqual(set(record), set(report.RECORD_KEYS_V2))  # jsonb keeps no key order
        self.assertEqual({key: record[key] for key in ('engine_version', 'interpretation_version', 'inventory_version',
                                                       'gemini_run', 'appraisal_run', 'context')},
                         {'engine_version': 'cpt-studio-events@2',
                          'interpretation_version': 'gemini-events@2/appraisal@1',
                          'inventory_version': 'gemini-inventory@2', 'gemini_run': str(world.first.pk),
                          'appraisal_run': str(world.second.pk), 'context': str(world.context.pk)})
        self.assertEqual(record['sentinel'], CLEAN_V2)
        self.assertEqual(report.record_problems(assessment), [])

    def test_a_sentinel_that_counts_no_retired_calls_is_a_problem_until_it_does(self):
        world, assessment = v2_assessment(sentinel_record=CLEAN)  # this image's sentinel: no RETIRED kind yet
        self.assertIsNone(assessment.interpretation['sentinel'][report.RETIRED_CALLS])
        self.assertEqual(report.record_problems(assessment), [
            'The sentinel record counts no retired executions: the sentinel that made it does not count the retired '
            'modules.'])
        _, counted = v2_assessment(sentinel_record={**CLEAN_V2, report.RETIRED_CALLS: 2, 'retired_size': 9})
        self.assertEqual(counted.interpretation['sentinel']['retired_size'], 9)  # a later sentinel's key, kept
        self.assertEqual(report.record_problems(counted),
                         ['The sentinel counted 2 retired executions while the assessment was made.'])
        self.assertEqual(report.record_problems(counted, calls=False), [])

    def test_a_record_that_would_not_say_what_made_a_v2_assessment_is_refused(self):
        world = V2World(sentinel_record=CLEAN_V2)
        good = {'inventory': world.inventory, 'context': world.context, 'member_date_state': 'supplies',
                'sentinel_record': dict(CLEAN_V2)}
        report.interpretation_record(**good)
        legacy_context = models.EncounterContext.objects.create(
            encounter=world.enc, revision=world.rev, facts={}, version=interpretation.CONTEXT_VERSION,
            sha256='3' * 64, event_inventory=world.inventory)
        for name, change in (('a v1 context', {'context': legacy_context}),
                             ('a sentinel record missing a key', {'sentinel_record': {
                                 key: value for key, value in CLEAN_V2.items() if key != 'tool'}}),
                             ('a date state that is not JSON', {'member_date_state': object()})):
            with self.subTest(name), self.assertRaises(ValueError):
                report.interpretation_record(**{**good, **change})

    def test_a_stored_record_naming_another_appraisal_run_is_named(self):
        world, assessment = v2_assessment()
        record = {**assessment.interpretation, 'appraisal_run': str(world.first.pk)}
        wrong = models.Assessment.objects.create(
            encounter=world.enc, revision=world.rev, context=world.context, routing=world.assessment.routing,
            profiles_version='p', engine_version=interpretation.ENGINE_VERSION_V2, sha256='0' * 64,
            event_inventory=world.inventory, interpretation=record)
        self.assertEqual(report.record_problems(wrong),
                         ['The record names another appraisal run than the inventory was settled from.'])


class SectionTests(TestCase):
    def test_the_section_shows_both_runs_and_the_usage_sums(self):
        world, assessment = v2_assessment()
        section = report.interpretation_section(assessment)
        first, second = section['run'], section['appraisal_run']
        self.assertEqual((first['purpose'], second['purpose']), ('interpretation', 'appraisal'))
        self.assertEqual((first['usage'], second['usage']), (USAGE, USAGE))
        self.assertEqual(section['usage']['runs'], 2)
        self.assertEqual(section['usage']['usage']['totalTokenCount'], 2 * USAGE['totalTokenCount'])
        self.assertEqual(section['usage']['usage']['promptTokenCount'], 2 * USAGE['promptTokenCount'])
        each = [Decimal(run['estimated_cost']) for run in (first, second) if run['estimated_cost'] is not None]
        self.assertEqual(Decimal(section['usage']['estimated_usd']), sum(each, Decimal('0')))
        # the encounter's runs by purpose: an update's further pass-1 run adds to the interpretation's sums
        world.run(interpretation.PURPOSE, b'{"synthetic": "an update"}')
        again = report.interpretation_section(assessment)['encounter_usage']
        self.assertEqual((again['by_purpose']['interpretation']['runs'], again['by_purpose']['appraisal']['runs'],
                          again['total']['runs']), (2, 1, 3))
        self.assertEqual(again['total']['usage']['totalTokenCount'], 3 * USAGE['totalTokenCount'])
        self.assertEqual(section['inventory']['counts']['events'], 5)
        self.assertEqual(section['problems'], [])


class UsageSumsTests(SimpleTestCase):
    def test_only_runs_sent_and_not_reused_are_summed_and_priced(self):
        """The refutation's problem 07 (mutant M4 survived): a run never sent and a reuse report no new usage, so the
        sums and the pricing skip them; every run is counted in ``runs``."""
        sent = {'sent': True, 'reused_from': None, 'estimated_cost': '0.25',
                'usage': {'promptTokenCount': 10, 'candidatesTokenCount': 2, 'totalTokenCount': 12}}
        unpriced = {'sent': True, 'reused_from': None, 'estimated_cost': None,
                    'usage': {'promptTokenCount': 5, 'totalTokenCount': 5}}
        unsent = {'sent': False, 'reused_from': None, 'estimated_cost': '9.00',
                  'usage': {'promptTokenCount': 1000, 'totalTokenCount': 1000}}
        reused = {'sent': True, 'reused_from': 'run-1', 'estimated_cost': '7.00',
                  'usage': {'promptTokenCount': 100, 'totalTokenCount': 100}}
        found = report.usage_sums([sent, unsent, reused, unpriced])
        self.assertEqual(found, {'runs': 4, 'usage': {**{key: 0 for key in report.USAGE_KEYS}, 'promptTokenCount': 15,
                                                      'candidatesTokenCount': 2, 'totalTokenCount': 17},
                                 'estimated_usd': '0.25', 'priced_runs': 1, 'unpriced_runs': 1})


class LaterEventsVersionTests(TestCase):
    """The refutation's problem 09: an assessment of an events version this release neither reads nor reads as stored
    (a later release's row, after a switch-back) is never counted or judged as a v1 row."""

    def setUp(self):
        installed(self)
        self.since = timezone.now()

    def test_a_later_events_version_is_counted_apart_and_its_record_is_a_problem(self):
        world = V2World(sentinel_record=CLEAN_V2)
        later = models.Assessment.objects.create(
            encounter=world.enc, revision=world.rev, context=world.context, routing=world.assessment.routing,
            profiles_version='p', engine_version='cpt-studio-events@3', sha256='0' * 64,
            event_inventory=world.inventory,
            interpretation={**world.assessment.interpretation, 'engine_version': 'cpt-studio-events@3'})
        problem = 'The assessment was made at cpt-studio-events@3, an events version this release does not read.'
        self.assertEqual(report.record_problems(later), [problem])
        section = report.interpretation_section(later)
        self.assertEqual((section['engine_version'], section['problems'], section['inventory'], section['run']),
                         ('cpt-studio-events@3', [problem], None, None))
        found = report.window(self.since)
        self.assertEqual({key: found['assessments'][key] for key in ('v2', 'v1_events', 'unread_events')},
                         {'v2': 1, 'v1_events': 0, 'unread_events': 1})
        self.assertEqual(found['assessments']['record_problems'], {problem: 1})
        lines = dict(line.split(': ', 1) for line in report.render(found))
        self.assertEqual(lines['v1 assessments'], '0 (cpt-studio-events@1: read as stored and blocked; 1 design v2 '
                                                  'assessments; 1 of an events version this release does not read)')
        failed = {item['name'] for item in report.self_test(found)['checks'] if not item['ok']}
        self.assertIn('every new-path assessment carries its record', failed)
        self.assertNotIn('no legacy-engine assessment', failed)


class WindowTests(TestCase):
    def setUp(self):
        installed(self)
        self.since = timezone.now()

    def test_the_window_sums_both_runs_by_purpose_and_the_appraisals_health(self):
        world, _ = v2_assessment(transform=with_health)
        world.run(interpretation.APPRAISAL_PURPOSE, b'{"synthetic": "refused"}')
        unhealthy = models.ProviderRun.objects.create(
            encounter=world.enc, revision=world.rev, provider=interpretation.PROVIDER,
            adapter_version=interpretation.ADAPTER_VERSION_V2, purpose=interpretation.APPRAISAL_PURPOSE,
            request_sha256='6' * 64, request_body={}, contexts=[], state='failed', sent=True, http_status=200,
            scope={'health': {'refused': ['yes_sayer']}}, usage=dict(USAGE))
        found = report.window(self.since)
        by_purpose = found['gemini_runs']['by_purpose']
        self.assertEqual((by_purpose['interpretation']['total'], by_purpose['appraisal']['total']), (1, 3))
        self.assertEqual(by_purpose['interpretation']['usage']['totalTokenCount'], USAGE['totalTokenCount'])
        self.assertEqual(by_purpose['appraisal']['usage']['totalTokenCount'], 3 * USAGE['totalTokenCount'])
        self.assertEqual(found['inventories_by_version'], {'gemini-events@2/appraisal@1 / gemini-inventory@2': 1})
        self.assertEqual(found['appraisal'], {'inventories': 1, 'without_health': 0,
                                              'health': {key: HEALTH[key] for key in report.HEALTH_MEASURES},
                                              'coherence': COHERENCE, 'unhealthy': 1, 'refused': {'yes_sayer': 1}})
        self.assertEqual((found['assessments']['v2'], found['assessments']['v1_events']), (1, 0))
        test = report.self_test(found)
        self.assertTrue(test['passed'], test)
        lines = dict(line.split(': ', 1) for line in report.render(found, test))
        self.assertTrue(lines['gemini runs by purpose'].startswith('interpretation 1 (1 sent, 0 reused); appraisal 3'))
        self.assertIn('appraisal: promptTokenCount 15000', lines['gemini usage by purpose'])
        self.assertEqual(lines['appraisals refused as unhealthy'], '1 (yes_sayer 1)')
        self.assertIn('pairs 10', lines['appraisal health'])
        self.assertTrue(unhealthy.pk)

    def test_retired_calls_and_v1_rows_fail_the_self_test(self):
        v2_assessment(sentinel_record={**CLEAN_V2, report.RETIRED_CALLS: 1})
        world = V2World(sentinel_record=CLEAN_V2)
        models.Assessment.objects.create(
            encounter=world.enc, revision=world.rev, context=world.context, routing=world.assessment.routing,
            profiles_version='p', engine_version=interpretation.ENGINE_VERSION, sha256='0' * 64)
        found = report.window(self.since)
        self.assertEqual((found['assessments']['retired_calls'], found['assessments']['v1_events']), (1, 1))
        test = report.self_test(found)
        failed = {item['name']: item['detail'] for item in test['checks'] if not item['ok']}
        self.assertIn('1 retired executions', failed['no new-path legacy execution recorded'])
        self.assertIn('1 v1 assessments', failed['no legacy-engine assessment'])
        self.assertEqual(tuple(item['name'] for item in test['checks']), report.SELF_TEST)  # names unchanged (ops)

    def test_every_d22_field_is_printed_once_in_order(self):
        v2_assessment()
        out = io.StringIO()
        call_command('interpretation_report', '--since', self.since.isoformat(), stdout=out)
        fields = [line.split(': ', 1)[0] for line in out.getvalue().splitlines()]
        self.assertEqual(fields, list(report.D22_FIELDS))


class CommandTests(TestCase):
    def setUp(self):
        installed(self)

    def command(self, *args):
        out = io.StringIO()
        call_command('interpretation_report', '--since', '2026-01-01T00:00:00Z', *args, stdout=out)
        return out.getvalue()

    def test_an_encounter_prints_both_runs_and_the_usage_sums(self):
        world, _assessment = v2_assessment()
        text = self.command('--encounter', str(world.enc.pk))
        lines = dict(line.split(': ', 1) for line in text.splitlines())
        self.assertIn(str(world.first.pk), lines['encounter pass 1 run'])
        self.assertIn('purpose interpretation', lines['encounter pass 1 run'])
        self.assertIn(str(world.second.pk), lines['encounter appraisal run'])
        self.assertIn('purpose appraisal', lines['encounter appraisal run'])
        self.assertIn(f'totalTokenCount {2 * USAGE["totalTokenCount"]}', lines['encounter assessment usage'])
        self.assertTrue(lines['encounter gemini runs'].startswith('2;'))
        found = json.loads(self.command('--encounter', str(world.enc.pk), '--json'))
        self.assertEqual(found['encounter']['section']['appraisal_run']['id'], str(world.second.pk))
        self.assertEqual(found['encounter']['usage']['total']['usage']['totalTokenCount'],
                         2 * USAGE['totalTokenCount'])

    def test_an_id_that_names_no_encounter_is_refused(self):
        for value in ('00000000-0000-0000-0000-000000000000', 'not-an-id'):
            with self.subTest(value=value), self.assertRaises(CommandError):
                self.command('--encounter', value)
