"""Regressions for refutation round 4, pipeline:3: context extraction was quadratic in the number of matching facts.

_fact kept the longest of overlapping readings of one value with an any() scan over every reading already kept, so a
paste of 36,000 billing statements ('837P ') held the analyze stage for 80 s, and POST /context ran the same work in
the web request. The repair keeps, per value, the kept readings sorted and bisects. These prove the output is byte
for byte the old function's, on random and on recorded inputs, and bound the cost. Synthetic data only.
"""
import json
import random
import time
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import jobs, models
from studio.gi import context
from studio.gi.context import MISSING_NOTES
from studio.types import CONTEXT_FACTS, Fact, Span, to_jsonable
from tests.support import pipeline_factories as pf
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import LIVE, NO_DATE_NOTE, ApiHarness

ROOT = Path(settings.BASE_DIR)
HEADER = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
          'Date of service: 2026-10-20\nPlace of service: Office\n\nBilling notes\n')


def old_fact(name, found):
    """studio/gi/context.py _fact at 4347acd24, verbatim: the reference the repair must reproduce exactly."""
    # Overlapping readings of one value are one statement; the longest is kept.
    kept = []
    for value, span in sorted(found, key=lambda item: item[1].start - item[1].end):
        if not any(v == value and s.start < span.end and span.start < s.end for v, s in kept):
            kept.append((value, span))
    found = sorted(kept, key=lambda item: item[1].start)
    values = list(dict.fromkeys(value for value, _ in found))
    evidence = tuple(sorted(dict.fromkeys(span for _, span in found), key=lambda s: (s.start, s.end)))
    if not values:
        if name == 'billing_context':
            return Fact(name, 'not_documented', 'missing', (), MISSING_NOTES[name])
        return Fact(name, None, 'missing', (), MISSING_NOTES[name])
    if len(values) == 1:
        return Fact(name, values[0], 'document', evidence)
    return Fact(name, None, 'conflict', evidence, 'Conflicting documented values: ' + ', '.join(values) + '.')


def as_bytes(value):
    return json.dumps(to_jsonable(value), sort_keys=True, ensure_ascii=False).encode('utf-8')


def recorded_documents():
    """Every document the batteries route, the pipeline tests' notes, and notes built to hold overlapping readings."""
    docs = {}
    manifest = json.loads((ROOT / 'ops' / 'verification' / 'manifest.json').read_text(encoding='utf-8'))
    for doc in manifest['documents']:
        docs['ver:' + doc['id']] = (ROOT / 'ops' / 'verification' / doc['source']).read_text(encoding='utf-8')
    for path in sorted((ROOT / 'tests' / 'fixtures' / 'gi').glob('*.txt')):
        docs['gi:' + path.name] = path.read_text(encoding='utf-8')
    docs.update({'office': OFFICE_NOTE, 'no-date': NO_DATE_NOTE, 'gi-note': pf.GI_NOTE})
    docs['overlaps'] = (
        'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 2026-10-20\nDOS: 2026-10-20\nService date: 10/21/2026\n'
        'Place of service: 11\nPOS 24\nSetting: office clinic, ambulatory surgery center (ASC)\n'
        'Location: hospital outpatient department; office visit; seen in the clinic\n'
        'Billing: professional; professional claim 837P CMS-1500 CMS 1500; facility billing UB-04 837I\n'
        'Patient status: established. New patient to the practice; established patient.\n'
        'Telehealth visit by video visit. Inpatient consultation.\n')
    docs['837P x2000'] = HEADER + '837P ' * 2000
    return docs


class FactIsTheOldFunctionTests(SimpleTestCase):
    """The repaired _fact returns exactly the old _fact's Fact for every input."""

    VALUE_SETS = (('professional',), ('professional', 'facility'), ('office', 'asc', 'telehealth'),
                  ('2026-10-20', '2026-10-21'), ('new', 'established'))

    def random_found(self, rng, size, width):
        text = ''.join(rng.choice('abcdef \n') for _ in range(width + 50))
        values = rng.choice(self.VALUE_SETS)
        found = []
        for _ in range(size):
            start = rng.randint(0, width)
            end = min(width, start + rng.choice((0, 0, 1, 2, 3, 4, 5, 8, 13, 21, 40)))  # empty readings too
            found.append((rng.choice(values), Span(start, end, text[start:end])))
        for _ in range(rng.randint(0, 3)):
            if found:  # the same reading twice, and one span read as two values
                found.append(rng.choice(found))
                found.append((rng.choice(values), rng.choice(found)[1]))
        rng.shuffle(found)
        return found

    def assert_same(self, name, found):
        self.assertEqual(as_bytes(context._fact(name, list(found))), as_bytes(old_fact(name, list(found))),
                         (name, found))

    def test_random_inputs(self):
        rng = random.Random(20261024)
        for trial in range(20000):
            name = CONTEXT_FACTS[trial % len(CONTEXT_FACTS)]
            self.assert_same(name, self.random_found(rng, rng.randint(0, 30), rng.choice((10, 40, 200))))

    def test_random_crowded_inputs(self):
        rng = random.Random(4347)
        for trial in range(150):
            self.assert_same('billing_context', self.random_found(rng, rng.randint(100, 400), rng.choice((60, 600))))

    def test_recorded_inputs(self):
        documents = recorded_documents()
        calls = 0
        for label, text in documents.items():
            captured = []
            real = context._fact

            def capture(name, found, real=real, captured=captured):
                captured.append((name, list(found)))
                return real(name, found)
            context._context.cache_clear()
            with mock.patch.object(context, '_fact', capture):
                repaired = context.extract_context(text)
            context._context.cache_clear()
            with mock.patch.object(context, '_fact', old_fact):
                reference = context.extract_context(text)
            context._context.cache_clear()
            with self.subTest(document=label):
                self.assertEqual(len(captured), len(CONTEXT_FACTS))
                for name, found in captured:
                    self.assert_same(name, found)
                self.assertEqual(as_bytes(repaired), as_bytes(reference))
            calls += len(captured)
        self.assertEqual(calls, len(documents) * len(CONTEXT_FACTS))
        self.assertGreaterEqual(len(documents), 26 + 5)


class ContextCostIsBoundedTests(SimpleTestCase):
    """The claimant's paste and shapes that make the sorted lists work hardest stay far inside the 60 s budget."""

    LIMIT_S = 15.0  # the old function took about 80 s for the first case; the repair takes well under a second

    def timed(self, text):
        context._context.cache_clear()
        context.find_dates.cache_clear()
        started = time.perf_counter()
        facts = context.extract_context(text)
        elapsed = time.perf_counter() - started
        context._context.cache_clear()
        return facts, elapsed

    def test_36000_billing_statements(self):
        facts, elapsed = self.timed(HEADER + '837P ' * 36000)
        self.assertLess(elapsed, self.LIMIT_S)
        billing = facts['billing_context']
        self.assertEqual((billing.value, billing.origin, len(billing.evidence)), ('professional', 'document', 36000))

    def test_every_insert_lands_before_every_kept_reading(self):
        # Longer readings are taken first and appended; every shorter one then lands in front of all of them.
        text = HEADER + '837P ' * 40000 + 'CMS-1500 ' * 22000
        self.assertLessEqual(len(text), settings.MAX_PASTE_CHARS)
        facts, elapsed = self.timed(text)
        self.assertLess(elapsed, self.LIMIT_S)
        self.assertEqual(len(facts['billing_context'].evidence), 62000)

    def test_two_values_in_conflict(self):
        text = HEADER + '837P UB-04 ' * 36000
        self.assertLessEqual(len(text), settings.MAX_PASTE_CHARS)
        facts, elapsed = self.timed(text)
        self.assertLess(elapsed, self.LIMIT_S)
        self.assertEqual((facts['billing_context'].origin, len(facts['billing_context'].evidence)), ('conflict', 72000))


@override_settings(**LIVE)
class ContextCostThroughTheServiceTests(ApiHarness, TestCase):
    """The finding's own routes: the analyze stage in the worker, and POST /context in a cold web process."""

    LIMIT_S = 30.0

    def test_the_analyze_stage_and_a_context_change_on_the_claimants_paste(self):
        text = HEADER + '837P ' * 36000
        encounter_id = self.create(text)
        jobs.run_job(jobs.claim_next())  # extract
        context._context.cache_clear()
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.ANALYZE)
        started = time.perf_counter()
        jobs.run_job(job)
        self.assertLess(time.perf_counter() - started, self.LIMIT_S)
        self.assertEqual(models.Job.objects.get(pk=job.pk).state, models.Job.SUCCEEDED)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop', {}).status_code, 200)
        drain()
        context._context.cache_clear()  # the web process is another process: its cache is cold
        context.find_dates.cache_clear()
        started = time.perf_counter()
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertLess(time.perf_counter() - started, self.LIMIT_S)
        self.assertEqual(response.status_code, 201, response.content)
        facts = models.EncounterContext.objects.get(pk=response.json()['context_id']).facts
        self.assertEqual(len(facts['billing_context']['evidence']), 36000)
