"""The operator's interpretation evidence of design v2 (docs/gemini-migration/FINAL-V2.md 5.7 measure 9, 6.2 and 7.4;
AMENDMENT-1 9.2; step 5c of its 8.1): interpretation/report.py and ``manage.py interpretation_report`` over v2 rows -
both Gemini runs (pass 1, purpose interpretation, and the appraisal, purpose appraisal), their usage and estimated cost
and the sums, the appraisal's health and coherence, the retired calls, and the v1 rows counted apart. Synthetic rows
only (tests/v2/test_readers.V2World); nothing is sent.

The step's done-when "the report shows both runs and the usage sums": the record names both runs; the operator's section
shows both runs with their usage and cost and the sums of the two, and every Gemini run of the encounter by purpose with
the sums; the window report counts and sums the runs by purpose; ``--encounter`` prints them.

AMENDMENT-2 section 9 and 8.1 (DECISIONS D275, D279, D289; step F5): the interpreter's runs of both providers
(interpretation.READ_PROVIDERS: Fable's 'anthropic' and Gemini's stored ones) are counted, summed and priced by the
model their request named, with no fallback (a run that recorded no model is unpriced); Anthropic's usage counts - the
cache read and write and the thinking tokens among them - are summed and shown; the human labels read "interpreter"; an
AMENDMENT-2 assessment (cpt-studio-events@3) is read as design v2's, and its record names the engine that made it
(FableRunTests, EngineFamilyTests).
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from studio import interpretation, models
from studio.interpretation import report, sentinel, store
from studio.interpretation.engine import assess as AS
from studio.participants import pricing
from studio.types import sha256_json
from tests.test_interpretation_pricing import RECORDED
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
                         {'engine_version': AS.ENGINE_VERSION,  # the engine's own label (AMENDMENT-2 8.1)
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
        wrong = models.Assessment.objects.create(  # at the engine the copied record names (AMENDMENT-2 8.1)
            encounter=world.enc, revision=world.rev, context=world.context, routing=world.assessment.routing,
            profiles_version='p', engine_version=record['engine_version'], sha256='0' * 64,
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
        self.assertEqual(found, {'runs': 4, 'usage': {**{key: 0 for key in report.SUMMED_KEYS}, 'promptTokenCount': 15,
                                                      'candidatesTokenCount': 2, 'totalTokenCount': 17},
                                 'estimated_usd': '0.25', 'priced_runs': 1, 'unpriced_runs': 1})

    def test_anthropics_counts_are_summed_beside_geminis_nested_ones_by_their_dotted_keys(self):
        """AMENDMENT-2 section 9: the cache read and write tokens and the thinking tokens are summed and shown."""
        self.assertEqual(report.SUMMED_KEYS, report.ANTHROPIC_USAGE_KEYS + report.USAGE_KEYS)
        first = RECORDED['F3all, a short note, pass 1 reading the cached instruction'][0]
        second = RECORDED['F3all, the first pass 1: a 1-hour cache write'][0]
        runs = [{'sent': True, 'reused_from': None, 'estimated_cost': '0.445629', 'usage': first},
                {'sent': True, 'reused_from': None, 'estimated_cost': None, 'usage': second},
                {'sent': True, 'reused_from': None, 'estimated_cost': None,  # a count that is not one is not summed
                 'usage': {'input_tokens': '9', 'output_tokens_details': {'thinking_tokens': True},
                           'cache_creation': 'not an object'}}]
        found = report.usage_sums(runs)
        self.assertEqual({key: value for key, value in found['usage'].items() if value},
                         {'input_tokens': 472 + 411, 'cache_creation_input_tokens': 44466,
                          'cache_creation.ephemeral_1h_input_tokens': 44466, 'cache_read_input_tokens': 44466,
                          'output_tokens': 10824 + 9716, 'output_tokens_details.thinking_tokens': 6120 + 5023})
        self.assertEqual((found['estimated_usd'], found['priced_runs'], found['unpriced_runs']), ('0.445629', 1, 2))
        self.assertEqual((report.usage_count(first, 'output_tokens_details.thinking_tokens'),
                          report.usage_count(first, 'cache_creation.missing'), report.usage_count(first, 'speed'),
                          report.usage_count(None, 'input_tokens')), (6120, None, None, None))


class LaterEventsVersionTests(TestCase):
    """The refutation's problem 09: an assessment of an events version this release neither reads nor reads as stored
    (a later release's row, after a switch-back) is never counted or judged as a v1 row. AMENDMENT-2 8.1: @3 is read by
    this release (EngineFamilyTests), so the later version is @4."""

    def setUp(self):
        installed(self)
        self.since = timezone.now()

    def test_a_later_events_version_is_counted_apart_and_its_record_is_a_problem(self):
        world = V2World(sentinel_record=CLEAN_V2)
        later = models.Assessment.objects.create(
            encounter=world.enc, revision=world.rev, context=world.context, routing=world.assessment.routing,
            profiles_version='p', engine_version='cpt-studio-events@4', sha256='0' * 64,
            event_inventory=world.inventory,
            interpretation={**world.assessment.interpretation, 'engine_version': 'cpt-studio-events@4'})
        problem = 'The assessment was made at cpt-studio-events@4, an events version this release does not read.'
        self.assertEqual(report.record_problems(later), [problem])
        section = report.interpretation_section(later)
        self.assertEqual((section['engine_version'], section['problems'], section['inventory'], section['run']),
                         ('cpt-studio-events@4', [problem], None, None))
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
        self.assertTrue(lines['interpreter runs by purpose'].startswith('interpretation 1 (1 sent, 0 reused); '
                                                                        'appraisal 3'))
        self.assertIn('promptTokenCount 15000', lines['interpreter usage by purpose'].split('appraisal: ')[1])
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
        self.assertTrue(lines['encounter interpreter runs'].startswith('2;'))  # AMENDMENT-2 section 9's label
        found = json.loads(self.command('--encounter', str(world.enc.pk), '--json'))
        self.assertEqual(found['encounter']['section']['appraisal_run']['id'], str(world.second.pk))
        self.assertEqual(found['encounter']['usage']['total']['usage']['totalTokenCount'],
                         2 * USAGE['totalTokenCount'])

    def test_an_id_that_names_no_encounter_is_refused(self):
        for value in ('00000000-0000-0000-0000-000000000000', 'not-an-id'):
            with self.subTest(value=value), self.assertRaises(CommandError):
                self.command('--encounter', value)


# --- AMENDMENT-2 section 9 (DECISIONS D275, D289): the interpreter's runs of both providers ---------------------------

NOVEMBER_16 = datetime(2026, 11, 16, 12, 0, tzinfo=dt_timezone.utc)
# AMENDMENT-2 E.1's real usage objects (the Fable probes' frozen bodies; tests/test_interpretation_pricing.RECORDED)
FABLE_PASS_1 = RECORDED['F3all, a short note, pass 1 reading the cached instruction'][0]  # $0.445629
FABLE_PASS_2 = RECORDED['F2high-p2, a short note, pass 2 under structured outputs'][0]  # $0.562784
FABLE_1H = RECORDED['F3all, the first pass 1: a 1-hour cache write'][0]  # no estimate (1.7)
SSE = b'event: message_stop\ndata: {"type":"message_stop"}\n\n'  # synthetic bytes: the report never reads a body


def fable_run(world, purpose, usage, *, requested_model=interpretation.MODEL_V3, state='succeeded', sent=True,
              provider=interpretation.PROVIDER_V3, scope=None, adapter_version=interpretation.ADAPTER_VERSION_V3,
              returned_model=None):
    """A run of the Fable interpreter (or, with ``provider``, of another one) on ``world``'s revision, as jobs records
    one: its provider and adapter version, the model its request named, the model its answer named (``returned_model``;
    by default the requested one, '' for a run never sent), the usage as reported, its start."""
    request = {'model': requested_model, 'purpose': purpose, 'n': models.ProviderRun.objects.count()}
    body = SSE if sent else b''
    returned = '' if not sent else requested_model if returned_model is None else returned_model
    return models.ProviderRun.objects.create(
        encounter=world.enc, revision=world.rev, provider=provider, adapter_version=adapter_version, purpose=purpose,
        request_sha256=sha256_json(request), request_body=request, contexts=[], state=state, sent=sent,
        http_status=200 if sent else None, response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest(),
        usage=dict(usage), requested_model=requested_model, returned_model=returned,
        started_at=NOVEMBER_16 if sent else None, scope=scope or {})


class FableRunTests(TestCase):
    def setUp(self):
        installed(self)
        self.since = timezone.now()
        self.world = V2World(sentinel_record=CLEAN_V2)  # two Gemini runs with no start: their dated rates price none

    def test_a_fable_run_is_priced_by_the_model_its_request_named_and_its_counts_summed(self):
        first = fable_run(self.world, interpretation.PURPOSE, FABLE_PASS_1)
        second = fable_run(self.world, interpretation.APPRAISAL_PURPOSE, FABLE_PASS_2)
        found = [report.run_json(run) for run in (first, second)]
        self.assertEqual([(run['provider'], run['requested_model'], run['estimated_cost']) for run in found],
                         [('anthropic', 'claude-fable-5-2', '0.445629'), ('anthropic', 'claude-fable-5-2', '0.562784')])
        self.assertEqual(found[0]['estimated_cost'],
                         pricing.estimate(interpretation.MODEL_V3, FABLE_PASS_1)['estimated_usd'])
        sums = report.usage_sums(found)
        self.assertEqual((sums['estimated_usd'], sums['priced_runs'], sums['unpriced_runs']), ('1.008413', 2, 0))
        self.assertEqual({key: sums['usage'][key] for key in report.ANTHROPIC_USAGE_KEYS},
                         {'input_tokens': 472 + 7538, 'cache_creation_input_tokens': 0,
                          'cache_creation.ephemeral_5m_input_tokens': 0, 'cache_creation.ephemeral_1h_input_tokens': 0,
                          'cache_read_input_tokens': 44466, 'output_tokens': 10824 + 12562,
                          'output_tokens_details.thinking_tokens': 6120 + 8832})
        self.assertEqual(sum(sums['usage'][key] for key in report.USAGE_KEYS), 0)  # Gemini's counts: none reported
        line = report._run_line('pass 1', found[0])
        self.assertIn('provider anthropic', line)
        self.assertIn('cache_read_input_tokens 44466', line)
        self.assertIn('output_tokens_details.thinking_tokens 6120', line)
        self.assertTrue(line.endswith('estimated cost USD 0.445629'))

    def test_the_window_counts_and_prices_every_interpreter_provider(self):
        world = self.world
        fable_run(world, interpretation.PURPOSE, FABLE_PASS_1)  # priced $0.445629
        fable_run(world, interpretation.APPRAISAL_PURPOSE, FABLE_PASS_2)  # priced $0.562784
        fable_run(world, interpretation.PURPOSE, FABLE_1H)  # a 1-hour write: sent, not priced
        fable_run(world, interpretation.PURPOSE, {}, state='unknown')  # a stream without message_delta: no usage
        fable_run(world, interpretation.APPRAISAL_PURPOSE, FABLE_PASS_2, requested_model='')  # names no model
        fable_run(world, 'primary', FABLE_PASS_1, provider='fable')  # the Fable participant's: not the interpreter's
        # a stored Gemini run with its start: priced at its dated rate, by the model its request named
        fable_run(world, interpretation.PURPOSE, USAGE, provider=interpretation.PROVIDER,
                  requested_model=interpretation.MODEL, adapter_version=interpretation.ADAPTER_VERSION_V2)
        gemini = pricing.estimate(interpretation.MODEL, USAGE, on=NOVEMBER_16)['estimated_usd']
        self.assertEqual(gemini, '0.019000')  # 5,000 x $2 + 900 x $10
        found = report.window(self.since)
        runs = found['gemini_runs']
        self.assertEqual((runs['total'], runs['sent'], runs['by_provider']), (8, 8, {'anthropic': 5, 'gemini': 3}))
        self.assertEqual(runs['requested_models'], {'(none)': 1, 'claude-fable-5-2': 4, 'gemini-4-carbon': 3})
        self.assertEqual(runs['cost']['estimated_usd'], '1.027413')  # 0.445629 + 0.562784 + 0.019000
        self.assertEqual((runs['cost']['priced_runs'], runs['cost']['unpriced_runs']), (3, 5))
        self.assertTrue(runs['cost']['basis'].startswith('each run priced by the model its request named, a run that '
                                                         'named none not priced; claude-fable-5-2: estimated from '
                                                         'published rates as of 2026-11-03'))
        usage = runs['usage']
        self.assertEqual((usage['cache_read_input_tokens'], usage['cache_creation.ephemeral_1h_input_tokens'],
                          usage['output_tokens_details.thinking_tokens'], usage['promptTokenCount']),
                         (44466, 44466, 6120 + 8832 + 5023 + 8832, 3 * USAGE['promptTokenCount']))
        self.assertEqual({purpose: (item['total'], item['priced_runs'], item['unpriced_runs'], item['estimated_usd'])
                          for purpose, item in runs['by_purpose'].items()},
                         {'interpretation': (5, 2, 3, '0.464629'), 'appraisal': (3, 1, 2, '0.562784')})
        lines = dict(line.split(': ', 1) for line in report.render(found))
        self.assertEqual(lines['interpreter runs'], '8 (8 sent, 0 reused; by provider anthropic 5, gemini 3)')
        self.assertTrue(lines['interpreter estimated cost'].startswith(
            'USD 1.027413 over 3 priced runs (5 sent runs not priced); each run priced by the model its request named'))
        self.assertIn('cache_read_input_tokens 44466', lines['interpreter usage'])
        self.assertIn('output_tokens_details.thinking_tokens 28807', lines['interpreter usage'])
        self.assertIn('cache_creation_input_tokens 44466', lines['interpreter usage'])
        self.assertEqual([line for line in report.render(found) if line.lower().startswith('gemini')], [])

    def test_a_run_that_recorded_no_model_is_never_priced_at_another_models_rates(self):
        # DECISIONS D289, G2-05: no fallback - a run whose request named no model is reported unpriced
        self.assertIsNotNone(pricing.estimate(interpretation.MODEL, USAGE, on=NOVEMBER_16))  # the control: priceable
        for missing in ('', None):
            with self.subTest(requested_model=missing):
                self.assertIsNone(report.estimated_cost(missing, USAGE, NOVEMBER_16))
                self.assertIsNone(report.estimated_cost(missing, FABLE_PASS_2, NOVEMBER_16))
        self.assertEqual(report.estimated_cost(interpretation.MODEL, USAGE, NOVEMBER_16), '0.019000')
        self.assertEqual(report.estimated_cost(interpretation.MODEL_V3, FABLE_PASS_2, NOVEMBER_16), '0.562784')
        # a Fable usage is never priced at Gemini's rates, nor a Gemini usage at Fable's
        self.assertIsNone(report.estimated_cost(interpretation.MODEL, FABLE_PASS_2, NOVEMBER_16))
        self.assertIsNone(report.estimated_cost(interpretation.MODEL_V3, USAGE, NOVEMBER_16))
        # its answer named a model pricing prices: still unpriced (the answering model is no fallback either)
        unnamed = report.run_json(fable_run(self.world, interpretation.PURPOSE, FABLE_PASS_2, requested_model='',
                                            returned_model=interpretation.MODEL_V3))
        self.assertEqual((unnamed['requested_model'], unnamed['returned_model'], unnamed['estimated_cost']),
                         ('', 'claude-fable-5-2', None))
        self.assertEqual(report.usage_sums([unnamed])['unpriced_runs'], 1)

    def test_a_run_is_priced_by_the_model_its_request_named_never_by_the_one_that_answered(self):
        """Refutation VF51-2 (DECISIONS D289, G2-05; AMENDMENT-2 section 9): a run whose answer named another model than
        its request did (1.6's HOLD model: the stream completes, so describe records its usage and the run is billed)
        is priced at the rates of the model its REQUEST named - in run_json, the window's sums, its purpose sums and the
        encounter's - and a run whose request named none is never priced at the answering model's rates."""
        world = self.world  # two Gemini runs, sent with no start: their dated rates price neither
        older, other = 'claude-fable-5-1', 'claude-opus-5-5'  # one priced at other rates, one pricing does not price
        self.assertEqual(pricing.estimate(older, FABLE_PASS_1)['estimated_usd'], '0.557037')  # the controls
        self.assertIsNone(pricing.estimate(other, FABLE_PASS_1))
        fable_run(world, interpretation.PURPOSE, FABLE_PASS_1, returned_model=older)
        fable_run(world, interpretation.APPRAISAL_PURPOSE, FABLE_PASS_1, returned_model=other)
        fable_run(world, interpretation.APPRAISAL_PURPOSE, FABLE_PASS_1, requested_model='',
                  returned_model=interpretation.MODEL_V3)
        found = {(run['requested_model'], run['returned_model']): run['estimated_cost'] for run in (
            report.run_json(run) for run in models.ProviderRun.objects.filter(provider=interpretation.PROVIDER_V3))}
        self.assertEqual(found, {('claude-fable-5-2', older): '0.445629', ('claude-fable-5-2', other): '0.445629',
                                 ('', 'claude-fable-5-2'): None})
        runs = report.window(self.since)['gemini_runs']
        self.assertEqual(runs['returned_models'], {'claude-fable-5-1': 1, 'claude-fable-5-2': 1, 'claude-opus-5-5': 1,
                                                   'gemini-4-carbon': 2})
        self.assertEqual((runs['cost']['estimated_usd'], runs['cost']['priced_runs'], runs['cost']['unpriced_runs']),
                         ('0.891258', 2, 3))  # 2 x $0.445629
        self.assertEqual({purpose: (item['estimated_usd'], item['priced_runs'], item['unpriced_runs'])
                          for purpose, item in runs['by_purpose'].items()},
                         {'interpretation': ('0.445629', 1, 1), 'appraisal': ('0.445629', 1, 2)})
        total = report.encounter_usage(world.enc.pk)['total']
        self.assertEqual((total['runs'], total['estimated_usd'], total['priced_runs'], total['unpriced_runs']),
                         (5, '0.891258', 2, 3))

    def test_the_encounters_sums_count_the_interpreter_runs_of_both_providers(self):
        fable_run(self.world, interpretation.PURPOSE, FABLE_PASS_1)
        fable_run(self.world, interpretation.APPRAISAL_PURPOSE, FABLE_PASS_2)
        fable_run(self.world, 'primary', FABLE_PASS_1, provider='fable')  # a participant's run: not counted
        found = report.encounter_usage(self.world.enc.pk)
        self.assertEqual((found['total']['runs'], found['by_purpose']['interpretation']['runs'],
                          found['by_purpose']['appraisal']['runs']), (4, 2, 2))
        self.assertEqual((found['total']['estimated_usd'], found['total']['priced_runs'],
                          found['total']['unpriced_runs']), ('1.008413', 2, 2))
        self.assertEqual(found['total']['usage']['output_tokens_details.thinking_tokens'], 6120 + 8832)
        lines = report.render_encounter(report.encounter_section(self.world.enc.pk))
        total = next(line for line in lines if line.startswith('encounter interpreter runs: '))
        self.assertTrue(total.startswith('encounter interpreter runs: 4; usage input_tokens 8010,'), total)

    def test_a_fable_appraisal_refused_as_unhealthy_is_counted(self):
        fable_run(self.world, interpretation.APPRAISAL_PURPOSE, FABLE_PASS_2, state='failed',
                  scope={'health': {'refused': ['no_sayer']}})
        found = report.window(self.since)
        self.assertEqual((found['appraisal']['unhealthy'], found['appraisal']['refused']), (1, {'no_sayer': 1}))


class EngineFamilyTests(TestCase):
    """AMENDMENT-2 8.1 (report.py, F5): every reader of a stored row accepts both families of design v2's engine
    (cpt-studio-events@3, and @2 read as stored), and the record builder - a writer - names the engine that made the
    assessment: the engine's own label (engine/assess.ENGINE_VERSION), or the one its caller names."""

    def setUp(self):
        installed(self)
        self.since = timezone.now()
        self.world = V2World(sentinel_record=CLEAN_V2)

    def assessment_at(self, engine_version, *, record_engine=None):
        world = self.world
        record = report.interpretation_record(inventory=world.inventory, context=world.context,
                                              member_date_state={'state': 'agrees'}, sentinel_record=dict(CLEAN_V2),
                                              engine_version=record_engine or engine_version)
        return models.Assessment.objects.create(
            encounter=world.enc, revision=world.rev, context=world.context, routing=world.assessment.routing,
            profiles_version='p', engine_version=engine_version, sha256='0' * 64, event_inventory=world.inventory,
            interpretation=record)

    def test_an_amendment_2_assessment_is_read_as_design_v2s(self):
        self.assertEqual(report.V2_ENGINES, ('cpt-studio-events@3', 'cpt-studio-events@2'))
        later = self.assessment_at(interpretation.ENGINE_VERSION_V3)
        self.assertEqual(later.interpretation['engine_version'], 'cpt-studio-events@3')
        self.assertEqual(report.record_problems(later), [])
        section = report.interpretation_section(later)
        self.assertEqual((section['engine_version'], section['problems'], section['appraisal_run']['id']),
                         ('cpt-studio-events@3', [], str(self.world.second.pk)))
        found = report.window(self.since)
        self.assertEqual({key: found['assessments'][key] for key in ('v2', 'v1_events', 'unread_events',
                                                                      'with_record_problems')},
                         {'v2': 2, 'v1_events': 0, 'unread_events': 0, 'with_record_problems': 0})
        test = report.self_test(found)
        self.assertTrue(test['passed'], test)

    def test_a_record_naming_another_engine_than_its_assessment_is_a_problem(self):
        problem = 'The interpretation record names another engine than the assessment was made by.'
        for row, record in ((interpretation.ENGINE_VERSION_V3, interpretation.ENGINE_VERSION_V2),
                            (interpretation.ENGINE_VERSION_V2, interpretation.ENGINE_VERSION_V3)):
            with self.subTest(row=row, record=record):
                wrong = self.assessment_at(row, record_engine=record)
                self.assertEqual(report.record_problems(wrong), [problem])
        found = report.window(self.since)
        self.assertEqual(found['assessments']['record_problems'], {problem: 2})
        self.assertIn('every new-path assessment carries its record',
                      {item['name'] for item in report.self_test(found)['checks'] if not item['ok']})

    def test_the_builder_names_the_engine_that_made_the_assessment(self):
        world = self.world
        made = dict(inventory=world.inventory, context=world.context, member_date_state='supplies',
                    sentinel_record=dict(CLEAN_V2))
        self.assertEqual(report.interpretation_record(**made)['engine_version'], AS.ENGINE_VERSION)
        with mock.patch.object(AS, 'ENGINE_VERSION', interpretation.ENGINE_VERSION_V3):  # read at call time
            self.assertEqual(report.interpretation_record(**made)['engine_version'], 'cpt-studio-events@3')
        for named in V2_NAMED:
            with self.subTest(named=named):
                self.assertEqual(report.interpretation_record(**made, engine_version=named)['engine_version'], named)
        for refused in ('cpt-studio-events@1', 'cpt-studio-events@4', 'cpt-studio-validation@10', ''):
            with self.subTest(refused=refused), self.assertRaises(ValueError):
                report.interpretation_record(**made, engine_version=refused)
        with mock.patch.object(AS, 'ENGINE_VERSION', 'cpt-studio-events@4'), self.assertRaises(ValueError):
            report.interpretation_record(**made)  # an engine this release does not read writes no record


V2_NAMED = (interpretation.ENGINE_VERSION_V3, interpretation.ENGINE_VERSION_V2)
