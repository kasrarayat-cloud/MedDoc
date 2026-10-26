"""Round 5 regressions in the stage runner (repair round 4c, lead).

bounded:0, bounded:2, validation:0, pipeline:2 — the assess stage re-ran the whole routing analysis in the worker,
  outside the bounded child (validation's span readings), with no deadline, and kept it cached.
bounded:1, pipeline:1 — the analyze stage gave context extraction and routing the full deadline each, in two children.
pipeline:0 — after an analyze overrun (nothing sent), a member's context change sent the provider request anyway.
pipeline:4 — none of that had a test.

Each stage now reads the document in ONE bounded child under its own deadline, with the references it needs fetched
in the worker first. Probes record the process every reader ran in, through a file, because the readers run in
forked children. Synthetic data only; no network.
"""
import json
import os
import tempfile
import time
from datetime import date
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from studio import jobs, models
from studio.gi import context as gi_context
from studio.gi import detect, sections
from studio.reference.store import DbReferenceLookup, prefetched_lookup, selected_codes
from studio.types import NormalizedResponse, ProviderCode, to_jsonable
from studio.validation import checks
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.test_reference import ArchiveMixin

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
DEADLINES = {'extract': 300, 'analyze': 60, 'predict': 180, 'assess': 60}
_ROUTE, _EXTRACT, _SPAN = detect.route, gi_context.extract_context, detect.status_for_span


class Probe:
    """Wrappers that append '<label> <pid>' to a file. ``sleeps`` maps a label to (seconds, scope): the wrapper sleeps
    on its first call in each process (scope 'process') or on the first call of the whole run (scope 'run'). Routing
    calls context extraction itself, so 'run' lets a probe slow down only the stage's own first context read."""

    def __init__(self, test, sleeps=None):
        handle = tempfile.NamedTemporaryFile('w', delete=False, suffix='.probe')
        handle.close()
        self.path, self.sleeps, self.slept = handle.name, dict(sleeps or {}), set()
        test.addCleanup(os.unlink, self.path)

    def wrap(self, label, fn):
        def wrapped(*args, **kwargs):
            seen = {name for name, _ in self.calls()}
            with open(self.path, 'a', encoding='utf-8') as out:
                out.write(f'{label} {os.getpid()}\n')
            if label in self.sleeps:
                seconds, scope = self.sleeps[label]
                first = label not in seen if scope == 'run' else (label, os.getpid()) not in self.slept
                self.slept.add((label, os.getpid()))
                if first:
                    time.sleep(seconds)
            return fn(*args, **kwargs)
        return wrapped

    def calls(self):
        with open(self.path, encoding='utf-8') as handle:
            return [tuple(line.split()) for line in handle if line.strip()]

    def pids(self, label):
        return {int(pid) for name, pid in self.calls() if name == label}

    def patches(self):
        return (mock.patch.object(detect, 'route', self.wrap('route', _ROUTE)),
                mock.patch.object(gi_context, 'extract_context', self.wrap('context', _EXTRACT)),
                mock.patch.object(detect, 'status_for_span', self.wrap('span', _SPAN)))


@override_settings(**LIVE)
class OneChildPerStageTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def run_with(self, probe, deadlines=DEADLINES):
        a, b, c = probe.patches()
        with override_settings(JOB_DEADLINE_SECONDS=deadlines), a, b, c:
            encounter_id = self.create()
            drain()
        return encounter_id

    def job(self, encounter_id, kind):
        return models.Job.objects.get(encounter_id=encounter_id, kind=kind)

    def test_no_stage_reads_the_document_in_the_worker_and_each_stage_uses_one_child(self):
        probe = Probe(self)
        encounter_id = self.run_with(probe)
        self.assertEqual(self.job(encounter_id, models.Job.ASSESS).state, models.Job.SUCCEEDED)
        everyone = probe.pids('route') | probe.pids('context') | probe.pids('span')
        self.assertNotIn(os.getpid(), everyone, 'a reader ran in the worker process')
        self.assertTrue(probe.pids('span'), 'validation read no span: the probe proves nothing')
        self.assertLessEqual(probe.pids('span'), probe.pids('route'), 'validation read spans outside the routing child')
        self.assertEqual(len(everyone), 2, f'expected one analyze child and one assess child, saw {sorted(everyone)}')

    def test_the_analyze_deadline_is_one_budget_for_context_and_routing(self):
        # Two children of 2 s each would let both reads finish; one budget for the stage cannot.
        probe = Probe(self, sleeps={'context': (1.2, 'run'), 'route': (1.2, 'process')})
        encounter_id = self.run_with(probe, dict(DEADLINES, analyze=2))
        job = self.job(encounter_id, models.Job.ANALYZE)
        self.assertEqual(job.state, models.Job.FAILED)
        self.assertIn('took longer than 2 seconds and was stopped', job.error)
        self.assertEqual(self.provider.sent, [])
        self.assertFalse(models.EncounterContext.objects.filter(encounter_id=encounter_id).exists())

    def test_the_assess_deadline_covers_routing_and_validation_together(self):
        # Routing alone fits the deadline, and validation's span reading in the worker had none at all.
        probe = Probe(self, sleeps={'route': (1.2, 'process'), 'span': (1.2, 'run')})
        encounter_id = self.run_with(probe, dict(DEADLINES, assess=2))
        job = self.job(encounter_id, models.Job.ASSESS)
        self.assertEqual(job.state, models.Job.FAILED)
        self.assertIn('took longer than 2 seconds and was stopped', job.error)
        self.assertFalse(models.Assessment.objects.filter(encounter_id=encounter_id).exists())

    def test_a_stage_leaves_no_routing_analysis_cached_in_the_worker(self):
        detect.route(OFFICE_NOTE, date(2026, 10, 21))  # something resident before the stages run
        self.assertGreater(detect._analysis.cache_info().currsize, 0)
        encounter_id = self.create()
        drain()
        self.assertEqual(self.job(encounter_id, models.Job.ASSESS).state, models.Job.SUCCEEDED)
        for name, cached in caches():
            self.assertEqual(cached.cache_info().currsize, 0, name)

    def test_a_context_change_after_an_analyze_overrun_is_refused_and_sends_nothing(self):
        def slow_route(text, service_date=None):
            time.sleep(30)
            return _ROUTE(text, service_date)

        with override_settings(JOB_DEADLINE_SECONDS=dict(DEADLINES, analyze=1)), \
                mock.patch.object(detect, 'route', slow_route):
            encounter_id = self.create()
            drain()
        self.assertEqual(self.job(encounter_id, models.Job.ANALYZE).state, models.Job.FAILED)
        for values in ({'setting': 'office'}, {'service_date': '2026-10-22'}):
            with self.subTest(values=values), self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps(values),
                                            content_type='application/json')
            self.assertEqual(response.status_code, 409, response.content)
            self.assertIn('could not be read to the end', response.json()['error'])
        drain()
        self.assertEqual(self.provider.sent, [])
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.PREDICT).exists())
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id).exists())


def caches():
    """Every functools cache of the modules the stages read documents with (the names may change; the set must not
    be fixed here, or a new cache would escape the check)."""
    import sys
    found = []
    for module_name in jobs.ROUTING_CACHE_MODULES:
        for name, value in sorted(vars(sys.modules[module_name]).items()):
            if callable(getattr(value, 'cache_clear', None)) and hasattr(value, 'cache_info'):
                found.append((f'{module_name}.{name}', value))
    return found


class ReleaseCachesTests(SimpleTestCase):
    def test_every_routing_and_validation_cache_is_emptied(self):
        detect.route(OFFICE_NOTE, date(2026, 10, 21))
        detect.status_for_span(OFFICE_NOTE, 0, 20, date(2026, 10, 21))
        checks.span_status(OFFICE_NOTE, 0, 20, date(2026, 10, 21))
        names = [name for name, _ in caches()]
        for expected in ('studio.gi.detect._analysis', 'studio.gi.sections.layout', 'studio.gi.context._context',
                         'studio.gi.context.find_dates'):
            self.assertIn(expected, names)
        self.assertGreater(detect._analysis.cache_info().currsize, 0)
        jobs.release_routing_caches()
        for name, cached in caches():
            self.assertEqual(cached.cache_info().currsize, 0, name)


class PrefetchedReferenceTests(ArchiveMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()

    def test_it_answers_exactly_as_the_database_lookup_does(self):
        codes = ('45378', '43239', '45999', '86153')
        prefetched, db = prefetched_lookup(codes), DbReferenceLookup()
        self.assertEqual(prefetched.sources(), db.sources())
        for code in codes:
            for day in (date(2026, 10, 21), None, date(2027, 1, 1), date(2026, 9, 30)):
                with self.subTest(code=code, day=day):
                    self.assertEqual(to_jsonable(prefetched.lookup(code, day)), to_jsonable(db.lookup(code, day)))

    def test_a_code_it_was_not_given_is_an_error_never_an_empty_answer(self):
        with self.assertRaisesRegex(LookupError, '45380 was not prefetched'):
            prefetched_lookup(('45378',)).lookup('45380', date(2026, 10, 21))

    def test_only_selected_codes_are_fetched(self):
        normalized = NormalizedResponse(provider='corti', adapter_version='x', codes=(
            ProviderCode(role='selected', system='cpt', code='45378', display=''),
            ProviderCode(role='candidate', system='cpt', code='45380', display=''),
            ProviderCode(role='selected', system='cpt', code='45378', display=''),
            ProviderCode(role='alternative', system='cpt', code='45385', display='')))
        self.assertEqual(selected_codes(normalized), ('45378',))
        self.assertEqual(selected_codes(None), ())
