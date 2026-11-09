"""The production legacy-call sentinel (Gemini migration slice S07; design/FINAL.md 10, 16.7 and 16.13; design/
ADJUDICATION.md R-1, R-3, R-4 and R-5; DECISIONS D17 and D22). Synthetic text only; nothing is sent.

What each class proves:
- DenySetTests: the deny set is computed from code objects and equals its per-file pins; the pinned module list is the
  files (R-1) and install() imports it itself; the checks.py split is the FINAL 7.1 allowlist (R-5, without
  incomplete_check, R-4) and denies FINAL 10.1(3)'s list; what must not be denied is not.
- InstallFailureTests: every way the install can fail leaves the process failed, with the reason, refusing new-path
  writes - a planted function (the pin is not vacuous), a pin that no longer matches, tool 4 held by another, a positive
  control that does not fire - and the failure stands; an install before the models are ready changes nothing.
- LabelTests: executions count under the open scope's label (new_path, legacy_record, other) or as unscoped; a reader's
  relabel; nesting; the entry point names the first new-path frame past the denied ones; the denied caches are cleared
  when a new_path scope opens and when a row is relabelled new_path.
- GateTests: the positive control trips the write gate (Tripped, an AuditEvent 'sentinel.tripped'); no scope, an unarmed
  scope or a failed callback refuse too; a read records once and never refuses; the D22 record.
- ForkTests: a forked child's counts come back with its result and join the parent's scope, even when the child raised.
- CallCheckTests (test mode, R-3): the C-level reads PY_START cannot see - each call form of a denied pattern and a
  denied cache hit - are counted from the app's own code, and the legacy chain records a hit in every class.
"""
from __future__ import annotations

import gc
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from studio import bounded, context_facts, jobs
from studio.gi import catalogue, context as gi_context, cues, detect, profiles, services, structure
from studio.interpretation import sentinel
from studio.validation import checks, engine, questions, rationale, reconcile, review_view
from tests.support import factories as f

APP = Path(__file__).resolve().parents[1]
TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Procedure: Colonoscopy. Date of service: 2026-10-21.\n'
        'Findings: The colonoscope was advanced to the cecum. A 6 mm sessile polyp in the sigmoid colon was removed '
        'with a cold snare.\n'
        'Impression: One sigmoid colon polyp, removed by cold snare.\n')
NEW, LEGACY, OTHER = sentinel.NEW_PATH, sentinel.LEGACY_RECORD, sentinel.OTHER
# The pins, named again here (FINAL 10.1: "the generated list is pinned by a test that names it"): shrinking the deny set
# takes a deliberate edit of both
SIZES = {'studio/gi/__init__.py': 0, 'studio/gi/clauses.py': 31, 'studio/gi/context.py': 219, 'studio/gi/cues.py': 14,
         'studio/gi/detect.py': 766, 'studio/gi/purpose.py': 5, 'studio/gi/sections.py': 71,
         'studio/gi/services.py': 456, 'studio/gi/structure.py': 152, 'studio/validation/engine.py': 457,
         'studio/validation/reconcile.py': 109, 'studio/validation/review_view.py': 47,
         'studio/validation/rationale.py': 7, 'studio/candidates.py': 45, 'studio/validation/checks.py': 164,
         'studio/jobs.py': 5}
# FINAL 7.1's pure, text-free checks, written out (R-4: incomplete_check is not among them)
FINAL_7_1 = ('code_scope', 'scope_check', 'exact_evidence', 'evidence_checks', 'pfs_check', 'mue_check',
             'endoscopic_check', 'pctc_consideration', 'duplicate_check', 'reference_source_entries',
             'service_date_state', 'service_date_check', 'service_date_clarification', 'required_facts_check',
             'fact_clarifications', 'separate_em_clarification', 'em_procedure_check', 'same_day_if_reinstated_check',
             'same_day_em_check', 'reinstatement_check', 'provider_checks', 'extraction_check',
             'distinct_lesion_review_text')
FINAL_10_1_READERS = ('evidence_readings', 'routing_readings', 'resolve_status', 'required_fact_states',
                      'separate_em_statement', 'routing_check', 'status_check', 'exclusion_reason', 'uncertain_reason',
                      'performed_clarification', 'unproposed_check', 'unsupported_check', 'restated', 'cite', 'silent')


def legacy_call():
    """One execution of one denied function."""
    return cues.page_number_line('3')


def ensure_installed(case):
    status = sentinel.install()
    if status['state'] != 'ok':
        sentinel.uninstall()
        status = sentinel.install()
    case.assertEqual(status['state'], 'ok', status['reason'])
    return status


class SentinelCase(SimpleTestCase):
    """Installs the sentinel for the class and restores the process's state afterwards: a sentinel this process had
    installed stays installed, one it had not is removed again."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._was_installed = sentinel.installed()
        cls.addClassCleanup(cls._restore)

    @classmethod
    def _restore(cls):
        if not cls._was_installed:
            sentinel.uninstall()
        elif not sentinel.installed():
            sentinel.uninstall()
            sentinel.install()

    def setUp(self):
        ensure_installed(self)

    def reinstall_after(self):
        """Leave the sentinel freshly installed after this test, whatever it did to it."""
        self.addCleanup(lambda: (sentinel.uninstall(), ensure_installed(self)))


class DenySetTests(SentinelCase):
    def test_the_deny_set_is_computed_from_code_objects_and_equals_its_pins(self):
        status = sentinel.status()
        self.assertEqual(sentinel.PINNED_SIZES, SIZES)
        self.assertEqual(status['sizes'], SIZES)
        self.assertEqual((status['deny_size'], sentinel.DENY_SIZE), (2548, 2548))
        self.assertEqual((status['positive_control'], status['tool'], status['tool_id']),
                         ('ok', 'sys.monitoring', 4))
        self.assertEqual(sys.monitoring.get_tool(4), 'cpt-studio-sentinel')
        by_file = {}
        jobs_file = jobs.__file__
        for code in sentinel.deny_set().values():
            by_file[code.co_filename] = by_file.get(code.co_filename, 0) + 1
        files = {sys.modules[name].__file__: sentinel._module_key(sys.modules[name])
                 for name in sentinel.DENY_MODULES + (sentinel.CHECKS_MODULE, sentinel.JOBS_MODULE)}
        self.assertEqual({files[path]: n for path, n in by_file.items()}, {key: n for key, n in SIZES.items() if n})
        self.assertEqual(by_file[jobs_file], 5)
        # every armed code object has PY_START set for tool 4, locally, and nothing else in the process is armed for it
        events = sys.monitoring.events
        self.assertTrue(all(sys.monitoring.get_local_events(4, code) == events.PY_START
                            for code in sentinel.deny_set().values()))
        for code in (profiles.family_for_code.__code__, context_facts.is_member_conflict.__code__,
                     self.test_the_module_list_is_the_files.__code__):
            self.assertEqual(sys.monitoring.get_local_events(4, code), 0)

    def test_the_module_list_is_the_files(self):
        # R-1, measured here independently of the sentinel's own reading
        gi = sorted(path.stem for path in (APP / 'studio' / 'gi').glob('*.py'))
        expected = {('studio.gi' if stem == '__init__' else f'studio.gi.{stem}') for stem in gi
                    if stem not in ('profiles', 'catalogue')}
        expected |= {'studio.validation.engine', 'studio.validation.reconcile', 'studio.validation.review_view',
                     'studio.validation.rationale', 'studio.candidates'}
        self.assertEqual(set(sentinel.DENY_MODULES), expected)
        self.assertEqual(len(sentinel.DENY_MODULES), len(expected))
        self.assertEqual(sentinel.expected_modules(), expected)
        sentinel.check_module_list()

    def test_the_list_refuses_a_file_outside_it_a_missing_one_and_a_subpackage(self):
        def layout(root: Path):
            for name in ('__init__', 'clauses', 'context', 'cues', 'detect', 'purpose', 'sections', 'services',
                         'structure', 'profiles', 'catalogue'):
                (root / 'gi').mkdir(exist_ok=True)
                (root / 'gi' / f'{name}.py').write_text('', encoding='utf-8')
            (root / 'validation').mkdir(exist_ok=True)
            for name in ('engine', 'reconcile', 'review_view', 'rationale', 'checks', 'questions'):
                (root / 'validation' / f'{name}.py').write_text('', encoding='utf-8')
            (root / 'candidates.py').write_text('', encoding='utf-8')

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout(root)
            sentinel.check_module_list(root)  # the same layout as the tree: accepted
            (root / 'gi' / 'newreader.py').write_text('', encoding='utf-8')
            with self.assertRaisesRegex(sentinel._Refused, r"missing \['studio\.gi\.newreader'\]"):
                sentinel.check_module_list(root)
            (root / 'gi' / 'newreader.py').unlink()
            with self.assertRaisesRegex(sentinel._Refused, r"not a file \['studio\.gi\.cues'\]"):
                (root / 'gi' / 'cues.py').unlink()
                sentinel.check_module_list(root)
            layout(root)
            (root / 'validation' / 'rationale.py').unlink()
            with self.assertRaisesRegex(sentinel._Refused, 'rationale.py, a denied file, does not exist'):
                sentinel.check_module_list(root)
            layout(root)
            (root / 'gi' / 'nested').mkdir()
            (root / 'gi' / 'nested' / 'reader.py').write_text('', encoding='utf-8')
            with self.assertRaisesRegex(sentinel._Refused, 'subpackage'):
                sentinel.check_module_list(root)
        with self.assertRaisesRegex(sentinel._Refused, 'differ from the files'):
            sentinel.check_module_list(modules=sentinel.DENY_MODULES + ('studio.gi.cues',))

    def test_install_imports_the_pinned_modules_itself_before_it_walks_anything(self):
        self.reinstall_after()
        sentinel.uninstall()
        events = []
        real_import, real_compute = importlib.import_module, sentinel._compute

        def recorded_import(name, *args, **kwargs):
            events.append(name)
            return real_import(name, *args, **kwargs)

        def recorded_compute():
            events.append('compute')
            return real_compute()

        with mock.patch.object(sentinel.importlib, 'import_module', recorded_import), \
                mock.patch.object(sentinel, '_compute', recorded_compute):
            self.assertEqual(sentinel.install()['state'], 'ok')
        self.assertEqual(events, list(sentinel.DENY_MODULES) + [sentinel.CHECKS_MODULE, sentinel.JOBS_MODULE,
                                                                'compute'])

    def test_a_fresh_process_installs_it_from_nothing(self):
        # R-1: every process installs it - here a new interpreter that set Django up and imported nothing else
        code = ('import json, sys\nimport django\ndjango.setup()\n'
                'from studio.interpretation import sentinel\n'
                'names = sentinel.DENY_MODULES + (sentinel.CHECKS_MODULE, sentinel.JOBS_MODULE)\n'
                'before = [name for name in names if name in sys.modules]\n'
                'status = sentinel.install()\n'
                'after = [name for name in names if name in sys.modules]\n'
                'print(json.dumps({"before": before, "after": after, "state": status["state"], '
                '"reason": status["reason"], "size": status["deny_size"], "control": status["positive_control"]}))\n')
        environment = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'cptstudio.settings', 'PYTHONPATH': str(APP)}
        completed = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=180,
                                   cwd=APP, env=environment)
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        found = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual((found['state'], found['reason'], found['size'], found['control']), ('ok', '', 2548, 'ok'))
        self.assertEqual(found['after'], list(sentinel.DENY_MODULES) + [sentinel.CHECKS_MODULE, sentinel.JOBS_MODULE])

    def test_the_checks_split_is_the_final_allowlist_and_denies_final_10_1s_list(self):
        split = sentinel.checks_split()
        self.assertEqual(sentinel.CHECKS_ALLOWLIST, FINAL_7_1)
        self.assertNotIn('incomplete_check', split['allowed'])  # R-4
        self.assertIn('incomplete_check', split['denied'])
        self.assertEqual(split['denied'], sorted(sentinel.CHECKS_DENIED))
        self.assertEqual(split['helpers'], sorted(sentinel.CHECKS_ALLOWED_HELPERS))
        self.assertEqual(split['importers'], sorted(sentinel.CHECKS_GI_IMPORTERS))
        self.assertEqual((len(split['denied']), len(split['helpers']), len(split['importers'])), (91, 17, 22))
        self.assertTrue({name for name in split['importers'] if not name.startswith(('_V2_', '_VAL_'))}
                        == {'names_intervention', 'span_status'})
        self.assertEqual(sentinel.CHECKS_NAMED_READERS, FINAL_10_1_READERS)
        denied = set(split['denied'])
        self.assertLessEqual(set(FINAL_10_1_READERS) | set(split['importers']) | set(split['reaching']), denied)
        self.assertFalse(set(split['allowed']) & denied)
        top = {name for name, value in vars(checks).items()
               if callable(value) and getattr(sentinel._unwrap(value), '__code__', None) is not None
               and sentinel._unwrap(value).__code__.co_filename == checks.__file__}
        self.assertEqual(set(split['allowed']) | denied, top)  # every function of checks.py is one or the other
        armed = sentinel.deny_set()
        for name in split['allowed']:
            self.assertNotIn(id(sentinel._unwrap(getattr(checks, name)).__code__), armed, name)
        for name in split['denied']:
            self.assertIn(id(sentinel._unwrap(getattr(checks, name)).__code__), armed, name)

    def test_an_allowlist_that_reaches_a_reader_final_denies_is_refused(self):
        with mock.patch.object(sentinel, 'CHECKS_ALLOWLIST', sentinel.CHECKS_ALLOWLIST + ('status_check',)):
            with self.assertRaisesRegex(sentinel._Refused, 'reaches functions FINAL 10.1\\(3\\) denies'):
                sentinel.checks_split()
        with mock.patch.object(sentinel, 'CHECKS_ALLOWLIST', sentinel.CHECKS_ALLOWLIST + ('no_such_check',)):
            with self.assertRaisesRegex(sentinel._Refused, 'has no function'):
                sentinel.checks_split()

    def test_what_must_run_on_the_new_path_is_not_denied(self):
        armed = sentinel.deny_set()

        def denied(fn):
            return id(sentinel._unwrap(fn).__code__) in armed

        # the re-homed stored-fact predicates are the same objects, and their code is context_facts'
        for name in ('is_member_conflict', 'charge_date_problem', 'charge_date_own', 'documented_values'):
            with self.subTest(name):
                self.assertIs(getattr(gi_context, name), getattr(context_facts, name))
                self.assertFalse(denied(getattr(context_facts, name)))
        for module in (profiles, catalogue, questions):
            for name, value in vars(module).items():
                fn = sentinel._unwrap(value)
                if callable(fn) and getattr(fn, '__code__', None) is not None:
                    self.assertFalse(denied(fn), f'{module.__name__}.{name}')
        self.assertFalse(denied(jobs.release_routing_caches))
        self.assertEqual(review_view.View.__init__.__code__.co_filename, '<string>')
        self.assertFalse(denied(review_view.View.__init__))  # building a View is allowed (dataclass-generated)
        # and what is denied, is: whole legacy modules, a nested code object, the checks readers, the archived stages
        for fn in (detect.route, services.build, gi_context.extract_context, engine.reviewed_completeness,
                   reconcile.act_label, review_view.review_view, rationale.alternative_note, checks.evidence_readings,
                   jobs._assess_child, jobs._analyze_child, jobs._route_child, jobs.make_context, jobs._merged_facts):
            with self.subTest(fn.__qualname__):
                self.assertTrue(denied(fn))
        nested = [const for const in cues.heading_shaped_line.__code__.co_consts if hasattr(const, 'co_code')]
        self.assertTrue(nested)
        self.assertTrue(all(id(code) in armed for code in nested))


class InstallFailureTests(SentinelCase):
    def install_failing(self):
        """install(), which must fail and say so in the log."""
        with self.assertLogs(sentinel.log, 'ERROR') as logged:
            status = sentinel.install()
        self.assertEqual(status['state'], 'failed')
        self.assertIn(status['reason'], logged.output[0])
        self.assertIn('this process refuses new-path writes', logged.output[0])
        return status

    def assertRefusesWrites(self):
        with sentinel.scope(NEW, entry='after a failed install') as opened:
            self.assertEqual(sentinel.refusal(opened), 'unavailable')
            with self.assertLogs(sentinel.log, 'ERROR'), self.assertRaises(sentinel.Tripped) as tripped:
                sentinel.gate('a new-path write')
        self.assertEqual(tripped.exception.reason, 'unavailable')
        self.assertEqual(str(tripped.exception), sentinel.MESSAGES['unavailable'])

    def test_a_function_planted_in_a_denied_file_fails_the_install(self):
        # the pin is not vacuous: one more live code object in detect.py than pinned, and the process refuses
        self.reinstall_after()
        planted = {}
        exec(compile('def planted():\n    return 1\n', detect.__file__, 'exec'), planted)
        self.addCleanup(lambda: (planted.clear(), gc.collect()))
        sentinel.uninstall()
        status = self.install_failing()
        self.assertIn("'studio/gi/detect.py': (767, 766)", status['reason'])
        self.assertEqual((status['deny_size'], status['positive_control']), (0, 'failed'))
        self.assertRefusesWrites()

    def test_a_pin_that_no_longer_matches_fails_the_install(self):
        self.reinstall_after()
        for patch, expected in ((mock.patch.dict(sentinel.PINNED_SIZES, {'studio/gi/detect.py': 767}),
                                 'differs from its pins'),
                                (mock.patch.object(sentinel, 'CHECKS_ALLOWED_HELPERS',
                                                   sentinel.CHECKS_ALLOWED_HELPERS[1:]), 'helpers'),
                                (mock.patch.object(sentinel, 'CHECKS_GI_IMPORTERS', sentinel.CHECKS_GI_IMPORTERS[1:]),
                                 'importers')):
            with self.subTest(expected), patch:
                sentinel.uninstall()
                status = self.install_failing()
                self.assertIn(expected, status['reason'])
                self.assertRefusesWrites()

    def test_tool_4_held_by_another_fails_closed(self):
        self.reinstall_after()
        sentinel.uninstall()
        sys.monitoring.use_tool_id(4, 'synthetic-debugger')
        try:
            status = self.install_failing()
            self.assertIn("tool 4 is held by 'synthetic-debugger'", status['reason'])
            self.assertRefusesWrites()
            self.assertEqual(sys.monitoring.get_tool(4), 'synthetic-debugger')  # the other tool is left as it was
        finally:
            sys.monitoring.free_tool_id(4)

    def test_a_positive_control_that_does_not_fire_fails_the_install(self):
        self.reinstall_after()
        sentinel.uninstall()
        with mock.patch.object(sentinel, '_on_start', lambda code, offset: None):  # an instrument that never counts
            status = self.install_failing()
        self.assertIn('the positive control was not counted', status['reason'])
        self.assertIsNone(sys.monitoring.get_tool(4))  # nothing is left armed
        self.assertRefusesWrites()

    def test_a_failure_stands_and_the_deny_set_is_not_walked_again(self):
        self.reinstall_after()
        sentinel.uninstall()
        with mock.patch.dict(sentinel.PINNED_SIZES, {'studio/gi/cues.py': 15}):
            first = self.install_failing()
        with mock.patch.object(sentinel, '_compute', side_effect=AssertionError('walked again')):
            self.assertEqual(sentinel.install(), first)
            with sentinel.scope(NEW, entry='a later stage'):  # the backstop install returns the standing failure
                pass
        self.assertEqual(sentinel.status()['state'], 'failed')

    def test_a_tool_freed_or_a_callback_replaced_after_the_install_fails_the_process_for_good(self):
        # a replaced callback stops the counting at once; a freed id (3.12) keeps delivering to the old callback
        # until another tool takes the id, which any tool now may - either way the process can vouch for nothing
        for label, tamper, counted, expected in (
                ('the callback replaced', lambda: sys.monitoring.register_callback(4, sys.monitoring.events.PY_START,
                                                                                    None),
                 {}, 'the PY_START callback of tool 4 was replaced after the install'),
                ('the tool freed', lambda: sys.monitoring.free_tool_id(4), {NEW: 1},
                 'sys.monitoring tool 4 was freed after the install')):
            with self.subTest(label):
                self.reinstall_after()
                ensure_installed(self)
                with sentinel.scope(NEW, entry='stage') as opened:
                    tamper()
                    legacy_call()
                    self.assertEqual(opened.counts(), counted)
                    with self.assertLogs(sentinel.log, 'ERROR') as logged:
                        self.assertEqual(sentinel.refusal(opened), 'unavailable')
                    self.assertIn(expected, logged.output[0])
                status = sentinel.status()
                self.assertEqual((status['state'], status['reason'], status['positive_control']),
                                 ('failed', expected, 'failed'))
                with sentinel.scope(NEW, entry='a later stage') as later:  # the failure stands
                    self.assertEqual(sentinel.refusal(later), 'unavailable')
                sentinel.uninstall()  # and a freed id is left as it is, with no error

    def test_an_install_before_the_models_are_ready_changes_nothing(self):
        self.reinstall_after()
        sentinel.uninstall()
        with mock.patch.object(apps, 'models_ready', False):
            status = sentinel.install()
        self.assertEqual((status['state'], status['reason']), ('not installed', ''))
        self.assertIsNone(sys.monitoring.get_tool(4))
        self.assertEqual(sentinel.install()['state'], 'ok')  # not a failure: the next call installs


class LabelTests(SentinelCase):
    def test_executions_count_under_the_open_scopes_label_or_as_unscoped(self):
        before = sentinel.totals()
        for label in (NEW, LEGACY, OTHER):
            with self.subTest(label), sentinel.scope(label, entry=f'a {label} scope') as opened:
                self.assertEqual(sentinel.label(), label)
                legacy_call()
                self.assertEqual(opened.counts(), {label: 1})
        legacy_call()
        after = sentinel.totals()
        self.assertEqual({label: after[label] - before[label] for label in sentinel.LABELS},
                         {NEW: 1, LEGACY: 1, OTHER: 1, sentinel.UNSCOPED: 1})
        self.assertEqual(sentinel.label(), sentinel.UNSCOPED)
        self.assertIsNone(sentinel.current())

    def test_a_reader_relabels_one_row_within_the_scope(self):
        with sentinel.scope(OTHER, entry='GET /api/session') as opened:
            with sentinel.relabel(LEGACY) as row:
                self.assertIs(row, opened)
                legacy_call()
            with sentinel.relabel(NEW):
                self.assertEqual(sentinel.label(), NEW)
                legacy_call()
                legacy_call()
            self.assertEqual(sentinel.label(), OTHER)
        self.assertEqual(opened.counts(), {LEGACY: 1, NEW: 2})
        self.assertEqual(sentinel.refusal(opened), 'executed')
        with sentinel.relabel(LEGACY) as alone:  # with no scope open, the relabel opens one
            legacy_call()
        self.assertEqual((alone.label, alone.entry, alone.counts()), (LEGACY, 'relabel', {LEGACY: 1}))

    def test_nested_scopes_join_their_parent_and_a_gate_reads_the_enclosing_ones(self):
        with sentinel.scope(NEW, entry='stage') as outer:
            with sentinel.scope(NEW, entry='child work') as inner:
                self.assertIsNone(sentinel.refusal(inner))
                legacy_call()
                self.assertEqual(sentinel.refusal(inner), 'executed')
            self.assertEqual(outer.counts(), {NEW: 1})  # joined at close
            self.assertEqual(sentinel.refusal(outer), 'executed')
        with sentinel.scope(NEW, entry='stage') as outer:
            legacy_call()
            with sentinel.scope(LEGACY, entry='a legacy row') as inner:
                self.assertEqual(sentinel.refusal(inner), 'executed')  # the enclosing scope's count decides
                self.assertEqual(inner.total(NEW), 1)

    def test_the_labels_are_closed(self):
        for label in ('unscoped', 'probe', 'legacy', ''):
            with self.subTest(label):
                with self.assertRaises(ValueError), sentinel.scope(label, entry='x'):
                    pass
                with self.assertRaises(ValueError), sentinel.relabel(label):
                    pass

    def test_the_entry_point_names_the_first_new_path_frame_past_the_denied_ones(self):
        def caller():
            return rationale.alternative_note('candidate', None)  # alternative_note calls _listing: denied to denied

        with sentinel.scope(NEW, entry='stage') as opened:
            caller()
        self.assertEqual(opened.count(NEW), 2)
        self.assertEqual(len(opened.entries), 2)
        here = 'tests/test_interpretation_sentinel.py'
        for entry, target in zip(opened.entries, ('alternative_note', '_listing')):
            self.assertRegex(entry, rf'^{re.escape(here)}:\d+ LabelTests\.test_the_entry_point_names_the_first_new_path_'
                                    rf'frame_past_the_denied_ones\.<locals>\.caller -> studio/validation/rationale\.py:'
                                    rf'\d+ {target}$')
        described = opened.describe(NEW)
        self.assertTrue(described[0].startswith('studio/validation/rationale.py:'))
        self.assertTrue(described[-1].startswith('entered: '))
        # a scope keeps at most MAX_ENTRIES entry points; its counts stay complete
        with sentinel.scope(NEW, entry='many') as many:
            detect.route(TEXT, None)
        self.assertEqual(len(many.entries), sentinel.MAX_ENTRIES)
        self.assertGreater(len(many.hits[NEW]), sentinel.MAX_ENTRIES)  # distinct denied code objects that ran
        self.assertGreater(many.count(NEW), len(many.hits[NEW]))

    def test_the_denied_caches_are_cleared_when_new_path_work_starts(self):
        cached = structure._course_start
        self.assertIn(id(cached), {id(wrapper) for wrapper in sentinel._STATE.wrappers.values()})
        cached()  # outside any scope: the cache now holds the answer
        with sentinel.scope(NEW, entry='stage') as opened:
            cached()
        self.assertGreaterEqual(opened.count(NEW), 1)  # the cleared cache made the function run, so it was counted
        cached()
        with sentinel.scope(OTHER, entry='GET /api/session') as listing:
            cached()  # a legacy row's read finds the cache warm ...
            with sentinel.relabel(NEW):
                cached()  # ... and a new row's read must still execute it
        self.assertEqual(set(listing.counts()), {NEW})
        self.assertGreaterEqual(listing.count(NEW), 1)
        cached()
        with mock.patch.object(sentinel, 'clear_caches', lambda: 0):  # the control: without the clearing, a hit hides it
            with sentinel.scope(NEW, entry='stage') as hidden:
                cached()
        self.assertEqual(hidden.counts(), {})


class GateTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._was_installed = sentinel.installed()
        cls.addClassCleanup(SentinelCase._restore.__func__, cls)

    def setUp(self):
        ensure_installed(self)
        ws = f.workspace()
        self.user = f.member(ws)
        self.encounter = f.encounter(ws, self.user)

    def trips(self):
        from studio.models import AuditEvent

        return list(AuditEvent.objects.filter(event=sentinel.TRIPPED).order_by('created_at'))

    def test_a_clean_new_path_scope_passes_the_gate_and_records_nothing(self):
        with sentinel.scope(NEW, entry='assess'):
            self.assertIsNone(sentinel.gate('persist_assessment', encounter=self.encounter))
            self.assertEqual(sentinel.observe('review view', encounter=self.encounter), {})
        self.assertEqual(self.trips(), [])

    def test_the_positive_control_trips_the_gate(self):
        with sentinel.scope(NEW, entry='assess'):
            legacy_call()
            with self.assertLogs(sentinel.log, 'ERROR') as logged, self.assertRaises(sentinel.Tripped) as tripped:
                sentinel.gate('persist_assessment', encounter=self.encounter, actor=self.user)
        self.assertIn('legacy-call sentinel tripped', logged.output[0])  # the log line stays whatever the caller does
        self.assertEqual(tripped.exception.reason, 'executed')
        self.assertEqual(str(tripped.exception), sentinel.MESSAGES['executed'])
        for named in ('studio', '.py', 'gi', 'gemini', 'google', 'legacy'):
            self.assertNotIn(named, str(tripped.exception).lower())
        (event,) = self.trips()
        self.assertEqual((event.encounter, event.workspace, event.actor), (self.encounter, self.encounter.workspace,
                                                                           self.user))
        data = event.data
        self.assertEqual({key: data[key] for key in ('entry', 'reason', 'refused', 'scope', 'label', 'counts',
                                                     'install', 'deny_size')},
                         {'entry': 'persist_assessment', 'reason': 'executed', 'refused': True, 'scope': 'assess',
                          'label': NEW, 'counts': {NEW: 1}, 'install': 'ok', 'deny_size': 2548})
        self.assertEqual(len(data['entry_points']), 1)
        self.assertRegex(data['entry_points'][0], r'^tests/test_interpretation_sentinel\.py:\d+ legacy_call -> '
                                                  r'studio/gi/cues\.py:\d+ page_number_line$')
        self.assertEqual(data['executed'], [data['executed'][0]])
        self.assertRegex(data['executed'][0], r'^studio/gi/cues\.py:\d+ page_number_line x1$')
        self.assertEqual(data, tripped.exception.data)

    def test_no_scope_an_unarmed_scope_or_a_failed_callback_refuse(self):
        with self.assertLogs(sentinel.log, 'ERROR'), self.assertRaises(sentinel.Tripped) as unscoped:
            sentinel.gate('an EventInventory insert', encounter=self.encounter)
        self.assertEqual(unscoped.exception.reason, 'unscoped')
        sentinel.uninstall()
        self.addCleanup(lambda: (sentinel.uninstall(), ensure_installed(self)))
        with sentinel.scope(OTHER, entry='opened before the install') as early:
            ensure_installed(self)
            with sentinel.scope(NEW, entry='stage'):
                with self.assertLogs(sentinel.log, 'ERROR'), self.assertRaises(sentinel.Tripped) as unarmed:
                    sentinel.gate('record_decision', encounter=self.encounter)
        self.assertFalse(early.armed)
        self.assertEqual(unarmed.exception.reason, 'unavailable')
        with sentinel.scope(NEW, entry='stage') as opened:
            sentinel._FRAME.get().hits = None  # the next callback fails
            legacy_call()
            self.assertEqual(opened.errors, 1)
            with self.assertLogs(sentinel.log, 'ERROR'), self.assertRaises(sentinel.Tripped) as failed:
                sentinel.gate('a member answer save', encounter=self.encounter)
        self.assertEqual(failed.exception.reason, 'instrument')
        self.assertEqual([event.data['reason'] for event in self.trips()], ['unscoped', 'unavailable', 'instrument'])

    def test_a_read_records_once_and_never_refuses(self):
        with sentinel.scope(NEW, entry='GET /api/encounters/x') as opened:
            legacy_call()
            with self.assertLogs(sentinel.log, 'ERROR'):
                self.assertEqual(sentinel.observe('review view', encounter=self.encounter), {NEW: 1})
            legacy_call()
            self.assertEqual(sentinel.observe('review view', encounter=self.encounter), {NEW: 2})
        (event,) = self.trips()
        self.assertEqual((event.data['refused'], event.data['reason'], event.data['counts']), (False, 'executed',
                                                                                               {NEW: 1}))
        self.assertTrue(opened.reported)
        self.assertEqual(sentinel.observe('outside'), {})

    def test_the_d22_record(self):
        with sentinel.scope(NEW, entry='assess') as opened:
            self.assertEqual(sentinel.record(), {'legacy_calls': 0, 'scope': 'assess', 'tool': 'sys.monitoring',
                                                 'deny_size': 2548, 'positive_control': 'ok'})
            with sentinel.scope(NEW, entry='child'):
                legacy_call()
            legacy_call()
            self.assertEqual(sentinel.record(opened, name='assess')['legacy_calls'], 2)
        with self.assertRaises(ValueError):
            sentinel.record()

    def test_the_trip_test_is_the_positive_control_tripping(self):
        before = sentinel.totals()
        self.assertEqual(sentinel.trip_test(), {'tripped': True, 'clean': True, 'counted': 1, 'ok': True})
        self.assertEqual(sentinel.totals(), before)  # private scopes: nothing joins a total
        self.assertEqual(self.trips(), [])  # and nothing is recorded
        sentinel.uninstall()
        self.addCleanup(lambda: (sentinel.uninstall(), ensure_installed(self)))
        self.assertEqual(sentinel.trip_test()['ok'], False)


class ForkTests(SentinelCase):
    LIMITS = {'seconds': 60, 'memory_bytes': 512 * 1024 * 1024}

    def test_a_forked_childs_counts_join_the_parents_scope(self):
        def child_work():
            return cues.page_number_line('7')

        with sentinel.scope(NEW, entry='interpret') as opened:
            result = sentinel.run_counted(child_work, **self.LIMITS)
            self.assertIs(result, True)
            self.assertEqual(opened.counts(), {NEW: 1})
            self.assertRegex(opened.entries[0], r'child_work -> studio/gi/cues\.py:\d+ page_number_line$')
            self.assertEqual(sentinel.refusal(opened), 'executed')

    def test_without_counted_a_childs_executions_stay_in_the_child(self):
        # why run_counted exists: monitoring survives fork, but the child's counters are the child's memory
        with sentinel.scope(NEW, entry='interpret') as opened:
            self.assertIs(bounded.run_bounded(legacy_call, **self.LIMITS), True)
        self.assertEqual(opened.counts(), {})

    def test_a_child_that_raised_still_returns_its_counts(self):
        def failing_work():
            legacy_call()
            raise ValueError('synthetic failure after a legacy execution')

        with sentinel.scope(NEW, entry='interpret') as opened:
            with self.assertLogs('studio.interpretation.sentinel', 'ERROR'):
                with self.assertRaisesRegex(RuntimeError, 'The bounded child failed; the error was logged.'):
                    sentinel.run_counted(failing_work, **self.LIMITS)
            self.assertEqual(opened.counts(), {NEW: 1})

    def test_the_child_counts_under_the_label_it_inherited_and_an_unarmed_child_refuses(self):
        with sentinel.scope(LEGACY, entry='a legacy record') as opened:
            sentinel.run_counted(legacy_call, **self.LIMITS)
        self.assertEqual(opened.counts(), {LEGACY: 1})
        with sentinel.scope(NEW, entry='interpret') as opened:
            sentinel.merge({'hits': {}, 'entries': [], 'errors': 0, 'armed': False})
            self.assertEqual(sentinel.refusal(opened), 'instrument')


class CallCheckTests(SentinelCase):
    """R-3's three forms, the cache wrapper and a pattern's bound method passed on: what PY_START cannot see."""

    def setUp(self):
        super().setUp()
        patterns, shared = sentinel.denied_patterns()
        self.pattern = cues.PAGE_NUMBER_LINE
        self.assertIn(id(self.pattern), patterns)
        self.shared = shared

    def forms(self):
        """Each form isolates one branch of the check: a method call and re.Pattern's own descriptor (the pattern as
        arg0 of a method descriptor), a bound method loaded and then called (a bound builtin whose __self__ is the
        pattern), the re module's functions (the pattern as their arg0), and a bound method handed to another callable
        (the bound method as arg0)."""
        pattern = self.pattern

        def kept():
            bound = pattern.search  # an attribute load, not a call: only the bound method's own call is seen
            return bound('page 3')

        return {'pattern.search(text)': lambda: pattern.search('page 3'),
                're.Pattern.search(pattern, text)': lambda: re.Pattern.search(pattern, 'page 3'),
                'a bound method kept and called': kept,
                're.search(pattern, text)': lambda: re.search(pattern, 'page 3'),
                're.findall(pattern, text)': lambda: re.findall(pattern, 'page 3'),
                'a bound method passed on': lambda: list(map(pattern.fullmatch, ['3', 'x']))}

    def test_each_form_of_a_denied_pattern_read_is_counted(self):
        with sentinel.call_checks():
            for label, read in self.forms().items():
                with self.subTest(label), sentinel.scope(NEW, entry=label) as opened:
                    read()
                    self.assertGreaterEqual(opened.by_kind()[sentinel.REGEX], 1)
                    self.assertEqual(sentinel.refusal(opened), 'executed')
                    self.assertIn('studio.gi.cues.PAGE_NUMBER_LINE', ' '.join(opened.describe()))
        for label, read in self.forms().items():  # the control: PY_START alone sees none of them
            with self.subTest(f'{label}, PY_START only'), sentinel.scope(NEW, entry=label) as opened:
                read()
                self.assertEqual(opened.counts(), {})

    def test_a_denied_cache_hit_is_counted(self):
        cached = structure._course_start
        with sentinel.call_checks(), sentinel.scope(NEW, entry='stage') as opened:
            cached()  # a miss (the scope cleared the cache): the function runs
            first = opened.by_kind()
            cached()  # a hit: nothing runs, and only the CALL check sees it
            second = opened.by_kind()
        self.assertEqual(first[sentinel.CACHE], 1)
        self.assertGreaterEqual(first[sentinel.CODE], 1)
        self.assertEqual((second[sentinel.CACHE] - first[sentinel.CACHE], second[sentinel.CODE] - first[sentinel.CODE]),
                         (1, 0))
        with sentinel.scope(NEW, entry='stage') as unseen:  # the control: PY_START alone misses a hit
            cached()
            cached()
        self.assertEqual(unseen.count(NEW), first[sentinel.CODE])

    def test_calls_from_outside_the_app_are_not_checked_and_the_checks_end_with_the_block(self):
        outside = {}
        exec(compile('def read(pattern):\n    return pattern.search("page 3")\n', '/nonexistent-outside/caller.py',
                     'exec'), outside)
        with sentinel.call_checks(), sentinel.scope(NEW, entry='outside') as opened:
            outside['read'](self.pattern)
        self.assertEqual(opened.counts(), {})
        self.assertEqual(sys.monitoring.get_events(4), 0)
        with sentinel.scope(NEW, entry='after') as later:
            self.pattern.search('page 3')
        self.assertEqual(later.counts(), {})

    def test_a_pattern_another_production_module_holds_is_not_denied_but_checks_exempts_none(self):
        held_by = {where for _, where in self.shared.values()}
        self.assertIn('studio.context_facts._CHARGE_NOTE_OWN', held_by)  # re-homed: context_facts holds it
        self.assertFalse([where for where in held_by if where.startswith('studio.validation.checks.')])
        patterns, _ = sentinel.denied_patterns()
        self.assertIn(id(detect._MOTION_PREDICATE_WORD), patterns)  # checks.py holds the same object: still denied
        self.assertIs(detect._MOTION_PREDICATE_WORD, checks._V2_CLASS_WORD)

    def test_the_legacy_chain_records_a_hit_in_every_class(self):
        # FINAL 10.4(3): a gi function, an engine/reconcile/review_view function, a legacy regex and a cache wrapper
        with sentinel.call_checks(), sentinel.scope(NEW, entry='the legacy chain') as opened:
            services.build(TEXT, service_date=None)
            detect.route(TEXT, None)
            reconcile.act_label('cold_snare')
            structure._course_start()
            structure._course_start()
        kinds = opened.by_kind()
        self.assertTrue(all(kinds[kind] > 0 for kind in (sentinel.CODE, sentinel.REGEX, sentinel.CACHE)), kinds)
        names = ' '.join(opened.describe())
        self.assertIn('studio/gi/services.py', names)
        self.assertIn('studio/validation/reconcile.py', names)
        self.assertEqual(sentinel.refusal(opened), 'executed')

    def test_strict_mode_passes_clean_work_and_names_any_denied_execution(self):
        with sentinel.strict('clean') as opened:
            self.assertEqual(profiles.family_for_code('45385'), profiles.family_for_code('45385'))
        self.assertEqual(opened.counts(), {})
        with self.assertRaises(AssertionError) as caught:
            with sentinel.strict('dirty'):
                self.pattern.search('page 3')
        self.assertIn('studio.gi.cues.PAGE_NUMBER_LINE', str(caught.exception))
