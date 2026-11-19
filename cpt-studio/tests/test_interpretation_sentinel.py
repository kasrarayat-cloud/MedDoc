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
  scope or a failed callback refuse too; a read records once per scope and never refuses, and a process that cannot
  count records that once on a read (FINAL 10.2); the D22 record.
- ForkTests: a forked child's counts come back with its result and join the parent's scope, even when the child raised.
- CallCheckTests (test mode, R-3): the C-level reads PY_START cannot see - each call form of a denied pattern and a
  denied cache hit - are counted from the app's own code, and the legacy chain records a hit in every class; checks.py's
  denied readers' keyword patterns are denied and SCOPE_FORMATS is not (R-5); only a pinned pattern is exempt, so a
  module that imports a legacy pattern leaves it denied, and every production regex equal to a denied one is a twin of a
  pinned pattern.
- Design v2's RETIRED kind (FINAL-V2 5.0, 5.7 measures 1-3): RetiredSetTests, RetiredCountTests, RetiredUnarmedTests,
  StrictModeTests, RetiredGateTests; and RetiredPatternTests (refutation 6a-r1 F7): the RETIRED kind's regex class in
  test mode - a retired module's pattern read by the app's own code is counted as RETIRED and refuses, the seam leaves
  it out in either order, strict measures it with retired=True only, and only the pinned twins are exempt.
"""
from __future__ import annotations

import gc
import importlib
import json
import os
import pkgutil
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.test import SimpleTestCase, TestCase

import cptstudio
import studio
from studio import bounded, context_facts, jobs, progress
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
         'studio/gi/services.py': 456, 'studio/gi/structure.py': 152, 'studio/validation/engine.py': 452,
         'studio/validation/reconcile.py': 107, 'studio/validation/review_view.py': 45,
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
# FINAL-V2 5.7 measure 1: each retired file's code-object count, named again here (RETIRED_SIZE is their sum)
RETIRED_SIZES = {'studio/interpretation/prompt.py': 4, 'studio/interpretation/schema.py': 10,
                 'studio/interpretation/read.py': 13, 'studio/interpretation/normalize.py': 79,
                 'studio/interpretation/verify.py': 45, 'studio/interpretation/literals.py': 29,
                 'studio/interpretation/identity.py': 36, 'studio/interpretation/lexicon.py': 32,
                 'studio/interpretation/relations.py': 60, 'studio/interpretation/mapping.py': 47,
                 'studio/interpretation/classes.py': 36, 'studio/interpretation/ercp.py': 85,
                 'studio/interpretation/facts.py': 22, 'studio/interpretation/events.py': 171,
                 'studio/interpretation/coverage.py': 72, 'studio/interpretation/combination.py': 27,
                 'studio/interpretation/assess.py': 139}
# The only exempt patterns, named again here: a new exemption takes a deliberate edit of both. Since the RETIRED kind has
# a regex class (refutation 6a-r1 F7) the retired modules' twins are pinned too (RETIRED_EXEMPT)
RETIRED_EXEMPT = ('studio.interpretation.literals.BARE_YEAR', 'studio.interpretation.literals.FULL_DATE',
                  'studio.interpretation.literals.MONTH_YEAR', "studio.interpretation.literals._STORED['day']",
                  "studio.interpretation.literals._STORED['month']", "studio.interpretation.literals._STORED['year']",
                  'studio.interpretation.read._DATE')
EXEMPT = ('studio.candidates._ISO_DATE', 'studio.gi.context.MONTH_YEAR', 'studio.gi.context._CHARGE_NOTE_OWN',
          *RETIRED_EXEMPT)


def patterns_in(value, depth=0) -> list:
    """The compiled patterns a module global holds, directly or in a container (the test's own reading)."""
    if isinstance(value, re.Pattern):
        return [value]
    if depth < 6 and isinstance(value, (tuple, list, set, frozenset)):
        return [found for item in value for found in patterns_in(item, depth + 1)]
    if depth < 6 and isinstance(value, dict):
        return [found for item in value.values() for found in patterns_in(item, depth + 1)]
    return []


def import_production():
    """Every module of the application's own packages, as a long-running process may load them (migrations and the
    WSGI and ASGI entry points aside): a twin in a module nothing imported yet must still be seen."""
    for package in (studio, cptstudio):
        for info in pkgutil.walk_packages(package.__path__, f'{package.__name__}.'):
            if '.migrations' not in info.name and info.name not in ('cptstudio.wsgi', 'cptstudio.asgi'):
                importlib.import_module(info.name)


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
        self.assertEqual(sentinel.LEGACY_SIZES, SIZES)
        self.assertEqual(sentinel.PINNED_SIZES, {**SIZES, **RETIRED_SIZES})  # FINAL-V2 5.7 measure 1: both kinds
        self.assertEqual(status['sizes'], {**SIZES, **RETIRED_SIZES})
        self.assertEqual((status['deny_size'], sentinel.DENY_SIZE), (2539, 2539))
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
        self.assertEqual(events, list(sentinel.DENY_MODULES) + [sentinel.CHECKS_MODULE, sentinel.JOBS_MODULE]
                         + list(sentinel.RETIRED_MODULES) + ['compute'])  # FINAL-V2 5.7 measure 1: the retired too

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
        self.assertEqual((found['state'], found['reason'], found['size'], found['control']), ('ok', '', 2539, 'ok'))
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

    def test_the_checks_patterns_are_split_as_its_functions_are(self):
        # R-5 applied to checks.py's compiled patterns: only what the allowed closure names is allowed
        split = sentinel.checks_split()
        self.assertEqual((split['patterns_allowed'], len(split['patterns_denied'])), (['SCOPE_FORMATS'], 45))
        self.assertEqual(split['patterns_denied'], sorted(sentinel.CHECKS_DENIED_PATTERNS))
        self.assertEqual(sentinel.checks_patterns(), {key: split[key] for key in ('patterns_allowed',
                                                                                   'patterns_denied')})
        held = {name for name, value in vars(checks).items() if patterns_in(value)}  # measured independently
        self.assertEqual(held, set(split['patterns_allowed']) | set(split['patterns_denied']))
        for name in ('_V2_DENIAL_WORDS', '_V2_DOUBT_WORDS', '_V2_HEDGE', '_V2_MODAL', '_V2_TIME_WORD',
                     '_VAL_TEMPORAL_LEAD', '_VAL_INTRO_ELSEWHEN', '_V2_CLASS_WORD'):
            self.assertIn(name, split['patterns_denied'])
        top = {name: sentinel._unwrap(getattr(checks, name)) for name in split['allowed']}
        named = set().union(*(sentinel._global_refs(sentinel._tree(fn.__code__, {})) for fn in top.values()))
        self.assertEqual(set(split['patterns_allowed']), held & named)  # code_scope reads SCOPE_FORMATS

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
                   reconcile.mention_label, review_view.review_view, rationale.alternative_note, checks.evidence_readings,
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
                                 'importers'),
                                (mock.patch.object(sentinel, 'CHECKS_DENIED_PATTERNS',
                                                   sentinel.CHECKS_DENIED_PATTERNS[1:]), 'patterns_denied')):
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
                          'label': NEW, 'counts': {NEW: 1}, 'install': 'ok', 'deny_size': 2539})
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

    def test_a_process_that_cannot_count_records_it_once_on_a_read(self):
        # FINAL 10.2: "If tool id 4 cannot be acquired ... The web records it. The D22 report shows it." A read in such a
        # process runs legacy code unseen (nothing is armed, so nothing is counted): the read must say so itself, once
        # for the process, before any write of it trips a gate
        sentinel.uninstall()
        self.addCleanup(lambda: (sentinel.uninstall(), ensure_installed(self)))
        sys.monitoring.use_tool_id(4, 'synthetic-debugger')
        try:
            with self.assertLogs(sentinel.log, 'ERROR'):
                self.assertEqual(sentinel.install()['state'], 'failed')
            with self.assertLogs(sentinel.log, 'ERROR') as logged:
                with sentinel.scope(NEW, entry='GET /api/session'):
                    legacy_call()
                    self.assertEqual(sentinel.observe('session view'), {})  # no encounter: logged only
            self.assertEqual(len(logged.output), 1)
            self.assertEqual(self.trips(), [])
            with self.assertLogs(sentinel.log, 'ERROR'):
                with sentinel.scope(NEW, entry='GET /api/encounters/x'):
                    legacy_call()
                    self.assertEqual(sentinel.observe('review view', encounter=self.encounter, actor=self.user), {})
            with self.assertNoLogs(sentinel.log, 'ERROR'):  # once per process: later reads record nothing more
                for entry in ('GET /api/encounters/y', 'GET /api/encounters/z'):
                    with sentinel.scope(NEW, entry=entry):
                        legacy_call()
                        sentinel.observe('review view', encounter=self.encounter)
                sentinel.observe('outside any scope', encounter=self.encounter)
        finally:
            sys.monitoring.free_tool_id(4)
        (event,) = self.trips()
        self.assertEqual((event.encounter, event.actor), (self.encounter, self.user))
        self.assertEqual({key: event.data[key] for key in ('entry', 'reason', 'refused', 'scope', 'label', 'counts')},
                         {'entry': 'review view', 'reason': 'unavailable', 'refused': False,
                          'scope': 'GET /api/encounters/x', 'label': NEW, 'counts': {}})
        self.assertIn("sys.monitoring tool 4 is held by 'synthetic-debugger'", event.data['install'])

    def test_a_read_records_its_scopes_own_reason_once(self):
        # a read records what a write in its place would be refused for, not only a counted execution
        sentinel.uninstall()
        self.addCleanup(lambda: (sentinel.uninstall(), ensure_installed(self)))
        with sentinel.scope(OTHER, entry='opened before the install'):
            ensure_installed(self)
            with self.assertLogs(sentinel.log, 'ERROR'):
                sentinel.observe('list view', encounter=self.encounter)
            sentinel.observe('list view', encounter=self.encounter)
        with sentinel.scope(NEW, entry='GET /api/encounters/x'):
            sentinel._FRAME.get().hits = None  # the next callback fails
            legacy_call()
            with self.assertLogs(sentinel.log, 'ERROR'):
                sentinel.observe('review view', encounter=self.encounter)
            sentinel.observe('review view', encounter=self.encounter)
        self.assertEqual([(event.data['reason'], event.data['refused']) for event in self.trips()],
                         [('unavailable', False), ('instrument', False)])

    def test_the_d22_record(self):
        with sentinel.scope(NEW, entry='assess') as opened:
            self.assertEqual(sentinel.record(), {'legacy_calls': 0, 'scope': 'assess', 'tool': 'sys.monitoring',
                                                 'deny_size': 2539, 'positive_control': 'ok', 'retired_calls': 0,
                                                 'retired_size': 907, 'retired_control': 'ok'})
            with sentinel.scope(NEW, entry='child'):
                legacy_call()
            legacy_call()
            self.assertEqual(sentinel.record(opened, name='assess')['legacy_calls'], 2)
        with self.assertRaises(ValueError):
            sentinel.record()

    def test_the_trip_test_is_the_positive_control_tripping(self):
        before = sentinel.totals()
        found = sentinel.trip_test()
        self.assertGreater(found.pop('retired_counted'), 0)  # FINAL-V2 5.7 measures 2-3: the retired probe trips too
        self.assertEqual(found, {'tripped': True, 'clean': True, 'counted': 1, 'retired_tripped': True, 'ok': True})
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
        patterns, exempt = sentinel.denied_patterns()
        self.pattern = cues.PAGE_NUMBER_LINE
        self.assertIn(id(self.pattern), patterns)
        self.exempt = exempt

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

    def test_only_a_pinned_pattern_is_exempt_and_holding_a_legacy_pattern_exempts_nothing(self):
        self.assertEqual(sorted(sentinel.EXEMPT_PATTERNS), sorted(EXEMPT))
        self.assertTrue(all(why.strip() for why in sentinel.EXEMPT_PATTERNS.values()))
        # each exempt pattern is named by (the first of) its pinned locations; a twin held by two pinned locations (the
        # month-and-year literal gi.context and the retired literals both hold) is named once, by either
        named = {where for where, _ in self.exempt.values()}
        self.assertLessEqual(named, set(EXEMPT))
        self.assertEqual({where for where in EXEMPT if not any(other in named for other in EXEMPT
                                                                if self.same_pattern(where, other))}, set())
        patterns, _ = sentinel.denied_patterns()
        self.assertNotIn(id(context_facts._CHARGE_NOTE_OWN), patterns)  # the re-homed predicates' own pattern
        # the reviewer's case: a consumer that imports a legacy pattern (simulated on studio.progress) must not exempt
        # it, so a new-path read of it through the consumer is still counted
        with mock.patch.object(progress, 'PAGE_NUMBER_LINE', cues.PAGE_NUMBER_LINE, create=True):
            patterns, exempt = sentinel.denied_patterns()
            self.assertIn(id(cues.PAGE_NUMBER_LINE), patterns)
            self.assertNotIn(id(cues.PAGE_NUMBER_LINE), exempt)
            self.assertIn('studio.progress.PAGE_NUMBER_LINE', sentinel.twins())  # a twin of an unpinned pattern, which
            # the twin test below fails on
            with self.assertRaises(AssertionError) as caught, sentinel.strict('a consumer\'s imported pattern'):
                progress.PAGE_NUMBER_LINE.search('page 3')
        self.assertIn('studio.gi.cues.PAGE_NUMBER_LINE', str(caught.exception))

    @staticmethod
    def same_pattern(one: str, other: str) -> bool:
        """Whether two pinned locations hold one compiled pattern (by identity, or by source and flags)."""
        held = {}
        for name in sentinel.DENY_MODULES + sentinel.RETIRED_MODULES:
            for located in sentinel._pattern_globals(sys.modules[name]).values():
                held.update(located)
        first, second = held.get(one), held.get(other)
        return first is not None and second is not None and (
            first is second or (first.pattern, first.flags) == (second.pattern, second.flags))

    def test_every_production_twin_of_a_denied_pattern_is_a_twin_of_a_pinned_one(self):
        # re's cache returns one object for one source in some import orders, so a production regex equal to a denied
        # one is either new code's own (its original pinned in EXEMPT_PATTERNS) or a legacy pattern imported: every
        # module is loaded first, so the answer does not depend on what this process happened to import
        import_production()
        found = sentinel.twins()
        self.assertIn('studio.context_facts._CHARGE_NOTE_OWN', found)  # S04's re-homing, by identity
        unpinned = {where: originals for where, originals in found.items() if not set(originals) <= set(EXEMPT)}
        self.assertEqual(unpinned, {})
        self.assertEqual({original for originals in found.values() for original in originals}, set(EXEMPT))

    def test_the_checks_readers_keyword_patterns_are_denied_and_scope_formats_is_not(self):
        # R-5: checks.py is an allowlist, and its denied readers' keyword vocabularies are as legacy as a gi pattern
        patterns, _ = sentinel.denied_patterns()
        denied = [pattern for name in sentinel.CHECKS_DENIED_PATTERNS for pattern in patterns_in(getattr(checks, name))]
        self.assertGreaterEqual(len(denied), 45)
        self.assertEqual([pattern.pattern for pattern in denied if id(pattern) not in patterns], [])
        self.assertIn(id(detect._MOTION_PREDICATE_WORD), patterns)  # whether re's cache made it checks' or not
        for _, pattern, _ in checks.SCOPE_FORMATS:
            self.assertNotIn(id(pattern), patterns)
        # re's cache could hand a denied module code_scope's own object: the allowlist still wins
        with mock.patch.object(cues, 'PLANTED_SCOPE_FORMAT', checks.SCOPE_FORMATS[0][1], create=True):
            self.assertNotIn(id(checks.SCOPE_FORMATS[0][1]), sentinel.denied_patterns()[0])
        with self.assertRaises(AssertionError) as caught, sentinel.strict('a checks keyword read'):
            checks._V2_DENIAL_WORDS.search('the snare was not used')
        self.assertIn('studio.validation.checks._V2_DENIAL_WORDS', str(caught.exception))
        with sentinel.strict('the allowlisted code_scope') as opened:
            self.assertEqual(checks.code_scope('45385'), ('cpt1', ''))
            self.assertEqual(checks.code_scope('G0121')[0], 'hcpcs')
        self.assertEqual(opened.counts(), {})

    def test_the_legacy_chain_records_a_hit_in_every_class(self):
        # FINAL 10.4(3): a gi function, an engine/reconcile/review_view function, a legacy regex and a cache wrapper
        with sentinel.call_checks(), sentinel.scope(NEW, entry='the legacy chain') as opened:
            services.build(TEXT, service_date=None)
            detect.route(TEXT, None)
            reconcile.mention_label('cold_snare')
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


# --- design v2: the RETIRED kind (docs/gemini-migration/FINAL-V2.md 5.0 and 5.7 measures 1-3; step 6a) ------------------

RETIRED_NAMES = ('prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations',
                 'mapping', 'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess')  # FINAL-V2 5.0
KEPT = ('__init__', 'adapter', 'holds', 'sentinel', 'readers', 'overlay', 'store', 'wording', 'report', 'replay', 'dates',
        'fable_adapter')  # AMENDMENT-2 section 9: sentinel.KEPT gains fable_adapter


def retired_call():
    """One execution of the RETIRED kind's positive-control function (its callees run too)."""
    from studio.interpretation import lexicon

    return lexicon.negation('no')


def interpretation_layout(root: Path, extra=()):
    """A studio/interpretation of empty files: the kept and retired modules, contract/ and engine/, and ``extra``."""
    folder = root / 'interpretation'
    for name in KEPT + RETIRED_NAMES + tuple(extra):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / f'{name}.py').write_text('', encoding='utf-8')
    for package in ('contract', 'engine'):
        (folder / package).mkdir(exist_ok=True)
        (folder / package / '__init__.py').write_text('', encoding='utf-8')
        (folder / package / 'module.py').write_text('', encoding='utf-8')


class RetiredSetTests(SentinelCase):
    """5.7 measure 1: the 17 retired modules denied whole, as code objects, armed by the existing machinery, of the
    RETIRED kind, their list the files and their sizes pinned."""

    def test_the_retired_set_is_computed_from_code_objects_and_equals_its_pins(self):
        status = sentinel.status()
        self.assertEqual(sentinel.RETIRED_MODULES, tuple(f'studio.interpretation.{name}' for name in RETIRED_NAMES))
        self.assertEqual(sentinel.RETIRED_SIZES, RETIRED_SIZES)
        self.assertEqual((status['retired_size'], status['pinned_retired_size'], sentinel.RETIRED_SIZE), (907,) * 3)
        self.assertEqual((status['retired_control'], status['retired_armed'], status['retired_modules']),
                         ('ok', True, 17))
        by_file = {}
        for code in sentinel.retired_set().values():
            by_file[code.co_filename] = by_file.get(code.co_filename, 0) + 1
        files = {sys.modules[name].__file__: sentinel._module_key(sys.modules[name]) for name in sentinel.RETIRED_MODULES}
        self.assertEqual({files[path]: n for path, n in by_file.items()}, RETIRED_SIZES)
        events = sys.monitoring.events
        self.assertTrue(all(sys.monitoring.get_local_events(4, code) == events.PY_START
                            for code in sentinel.retired_set().values()))
        # the two kinds are disjoint, and each code object is counted as its own kind
        self.assertFalse(set(sentinel.retired_set()) & set(sentinel.deny_set()))
        from studio.interpretation import lexicon
        self.assertEqual(sentinel.kind_of(id(lexicon.negation.__code__)), sentinel.RETIRED)
        self.assertEqual(sentinel.kind_of(id(cues.page_number_line.__code__)), sentinel.LEGACY)
        # nested code objects and the cache wrapper are the RETIRED kind's too
        from studio.interpretation import events as v1_events
        nested = [const for const in v1_events.another_role_hold.__code__.co_consts
                  if isinstance(const, type(v1_events.another_role_hold.__code__))]
        self.assertTrue(nested)
        self.assertTrue(all(id(code) in sentinel.retired_set() for code in nested))
        self.assertEqual(sentinel.kind_of(id(lexicon._compiled)), sentinel.RETIRED)
        # the new path's own code is in neither set
        from studio.interpretation import dates, store
        from studio.interpretation.engine import assess as engine_assess, combination as engine_combination
        for code in (engine_assess.assess.__code__, engine_combination.procedure_day.__code__,
                     dates.member_date_state.__code__, store.load_v2.__code__):
            self.assertNotIn(id(code), sentinel.retired_set())
            self.assertNotIn(id(code), sentinel.deny_set())
            self.assertEqual(sys.monitoring.get_local_events(4, code), 0)

    def test_the_retired_list_is_the_files_but_the_kept_ones(self):
        on_disk = {path.stem for path in (APP / 'studio' / 'interpretation').glob('*.py')}
        self.assertEqual({f'studio.interpretation.{stem}' for stem in on_disk - set(KEPT)},
                         set(sentinel.RETIRED_MODULES))
        self.assertEqual(sentinel.expected_retired(), set(sentinel.RETIRED_MODULES))
        sentinel.check_retired_list()

    def test_a_new_top_level_module_a_missing_one_and_code_outside_contract_and_engine_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            interpretation_layout(root)
            sentinel.check_retired_list(root)  # the tree's layout: accepted
            interpretation_layout(root, extra=('newreader',))
            with self.assertRaisesRegex(sentinel._Refused, r"neither kept nor retired \['studio\.interpretation\."
                                                           r"newreader'\]"):
                sentinel.check_retired_list(root)
            (root / 'interpretation' / 'newreader.py').unlink()
            (root / 'interpretation' / 'lexicon.py').unlink()
            with self.assertRaisesRegex(sentinel._Refused, r"not a file \['studio\.interpretation\.lexicon'\]"):
                sentinel.check_retired_list(root)
            interpretation_layout(root)
            (root / 'interpretation' / 'replay.py').unlink()
            with self.assertRaisesRegex(sentinel._Refused, r"no kept module \['replay'\]"):
                sentinel.check_retired_list(root)
            interpretation_layout(root)
            (root / 'interpretation' / 'v3').mkdir()
            (root / 'interpretation' / 'v3' / 'reader.py').write_text('', encoding='utf-8')
            with self.assertRaisesRegex(sentinel._Refused, r'outside contract/ and engine/'):
                sentinel.check_retired_list(root)
            (root / 'interpretation' / 'v3' / 'reader.py').unlink()
            (root / 'interpretation' / 'contract' / 'deeper').mkdir()
            (root / 'interpretation' / 'contract' / 'deeper' / 'x.py').write_text('', encoding='utf-8')
            sentinel.check_retired_list(root)  # under contract/: new code's place
        with self.assertRaisesRegex(sentinel._Refused, 'differ from the files'):
            sentinel.check_retired_list(modules=sentinel.RETIRED_MODULES + ('studio.interpretation.lexicon',))
        with self.assertRaisesRegex(sentinel._Refused, 'differ from the files'):
            sentinel.check_retired_list(modules=sentinel.RETIRED_MODULES[1:])

    def test_a_retired_pin_or_probe_that_does_not_hold_fails_the_install_and_the_failure_stands(self):
        self.reinstall_after()
        cases = {
            'a retired file\'s pin': (mock.patch.dict(sentinel.PINNED_SIZES,
                                                      {'studio/interpretation/lexicon.py': 31}),
                                      'differs from its pins'),
            'a retired list that is not the files': (mock.patch.object(sentinel, 'RETIRED_MODULES',
                                                                       sentinel.RETIRED_MODULES[:-1]),
                                                     'retired modules differ from the files'),
            'a probe of another kind': (mock.patch.object(sentinel, 'PROBE_CALL_RETIRED',
                                                          ('studio.gi.cues', 'page_number_line', ('3',))),
                                        'is not of the RETIRED kind'),
            'a probe counted twice': (mock.patch.object(sentinel, '_retired_probe_count', return_value=2),
                                      'counted 2 times, not exactly once'),
            'a probe never counted': (mock.patch.object(sentinel, '_retired_probe_count', return_value=0),
                                      'counted 0 times, not exactly once'),
        }
        for what, (patch, reason) in cases.items():
            with self.subTest(case=what):
                sentinel.uninstall()
                with patch, self.assertLogs(sentinel.log, 'ERROR'):
                    status = sentinel.install()
                self.assertEqual(status['state'], 'failed')
                self.assertIn(reason, status['reason'])
                self.assertEqual((status['retired_control'], status['positive_control'], status['retired_armed']),
                                 ('failed', 'failed', False))
                self.assertEqual((sentinel.retired_set(), sentinel.deny_set()), ({}, {}))
                self.assertEqual(sentinel.install()['state'], 'failed')  # the failure stands
                self.assertEqual(sentinel.refusal(sentinel.Scope(NEW, 'x', armed=True)), 'unavailable')

    def test_the_retired_probe_is_counted_exactly_once_under_the_probe_label(self):
        from studio.interpretation import lexicon

        self.assertEqual(sentinel.PROBE_CALL_RETIRED, ('studio.interpretation.lexicon', 'negation', ('no',)))
        self.assertEqual(sentinel._retired_probe_count(lexicon.negation), 1)
        before = sentinel.totals()
        with sentinel._private() as probe:
            lexicon.negation('no')
            lexicon.negation('no')
        self.assertEqual(probe.hits[sentinel.PROBE][id(lexicon.negation.__code__)], 2)  # the control: it counts calls
        self.assertEqual(sentinel.totals(), before)  # the probe label joins no total


class RetiredCountTests(SentinelCase):
    """A retired execution is counted under its label and as the RETIRED kind, apart from a legacy one; it joins the
    scope from a forked child; in test mode its cache wrapper is counted; the D22 record reports it apart."""

    LIMITS = {'seconds': 60, 'memory_bytes': 512 * 1024 * 1024}

    def test_counted_under_its_label_and_kind_apart_from_the_legacy_set(self):
        with sentinel.scope(NEW, entry='assess') as opened:
            retired_call()
            legacy_call()
            with sentinel.relabel(LEGACY):
                retired_call()
            record = sentinel.record()
        kinds = opened.by_set(NEW)
        self.assertGreater(kinds[sentinel.RETIRED], 0)
        self.assertEqual(kinds[sentinel.LEGACY], 1)
        self.assertEqual(record['legacy_calls'], 1)
        self.assertEqual(record['retired_calls'], kinds[sentinel.RETIRED])
        self.assertEqual((record['retired_size'], record['retired_control']), (907, 'ok'))
        self.assertGreater(opened.by_set(LEGACY)[sentinel.RETIRED], 0)  # the relabelled row's, under legacy_record
        self.assertEqual(opened.by_set(LEGACY)[sentinel.LEGACY], 0)
        self.assertEqual(sentinel.refusal(opened), 'executed')
        self.assertRegex('\n'.join(opened.describe(NEW)), r'studio/interpretation/lexicon\.py:\d+ negation x1')
        self.assertRegex(opened.entries[0], r'retired_call -> studio/interpretation/lexicon\.py:\d+ negation$')

    def test_a_retired_execution_alone_refuses_and_a_clean_scope_does_not(self):
        with sentinel.scope(NEW, entry='assess') as dirty:
            retired_call()
        with sentinel.scope(NEW, entry='assess') as clean:
            from studio.interpretation.engine import catalogue
            catalogue.EM_FAMILIES  # new-path code and data: nothing counted
        self.assertEqual(dirty.by_set(NEW)[sentinel.LEGACY], 0)
        self.assertEqual(sentinel.refusal(dirty), 'executed')
        self.assertIsNone(sentinel.refusal(clean))
        with sentinel.scope(LEGACY, entry='a legacy row') as legacy_row:
            retired_call()
        self.assertIsNone(sentinel.refusal(legacy_row))  # a legacy_record scope's own reads refuse nothing

    def test_a_forked_childs_retired_executions_join_the_parents_scope_as_retired(self):
        with sentinel.scope(NEW, entry='assess') as opened:
            result = sentinel.run_counted(retired_call, **self.LIMITS)
        self.assertEqual(result, ('no',))
        self.assertGreater(opened.by_set(NEW)[sentinel.RETIRED], 0)
        self.assertEqual(opened.by_set(NEW)[sentinel.LEGACY], 0)
        self.assertEqual(sentinel.refusal(opened), 'executed')

    def test_in_test_mode_a_retired_cache_hit_is_counted_as_retired(self):
        from studio.interpretation import lexicon

        with sentinel.call_checks(), sentinel.scope(NEW, entry='stage') as opened:
            lexicon._compiled.cache_clear()
            lexicon._compiled(('no',))
            first = (opened.by_kind(), opened.by_set())
            lexicon._compiled(('no',))  # a hit: only the CALL check sees it
            second = (opened.by_kind(), opened.by_set())
        self.assertEqual(second[0][sentinel.CACHE] - first[0][sentinel.CACHE], 1)
        self.assertEqual(second[0][sentinel.CODE] - first[0][sentinel.CODE], 0)
        self.assertEqual(second[1][sentinel.RETIRED] - first[1][sentinel.RETIRED], 1)
        self.assertEqual(second[1][sentinel.LEGACY], 0)


class RetiredUnarmedTests(SentinelCase):
    """retired_unarmed, the test-only v1 chain's seam: nothing retired is counted while it is open, the record is v1's
    five keys, nested blocks nest, and the retired codes are armed again when it closes."""

    def test_nothing_retired_is_counted_inside_and_everything_again_after(self):
        events = sys.monitoring.events
        from studio.interpretation import lexicon

        code = lexicon.negation.__code__
        with sentinel.retired_unarmed():
            self.assertFalse(sentinel.retired_armed())
            self.assertFalse(sentinel.status()['retired_armed'])
            self.assertEqual(sys.monitoring.get_local_events(4, code), 0)
            with sentinel.retired_unarmed():
                pass
            self.assertEqual(sys.monitoring.get_local_events(4, code), 0)  # the inner block left it unarmed
            with sentinel.scope(NEW, entry='assess') as opened:
                retired_call()
                legacy_call()  # the legacy set is still counted
                record = sentinel.record()
            self.assertEqual(opened.by_set(NEW), {sentinel.LEGACY: 1, sentinel.RETIRED: 0})
            self.assertEqual(sorted(record), ['deny_size', 'legacy_calls', 'positive_control', 'scope', 'tool'])
            self.assertEqual(record['legacy_calls'], 1)
            self.assertFalse(sentinel.trip_test()['retired_tripped'])
        self.assertTrue(sentinel.retired_armed())
        self.assertEqual(sys.monitoring.get_local_events(4, code), events.PY_START)
        with sentinel.scope(NEW, entry='assess') as again:
            retired_call()
        self.assertGreater(again.by_set(NEW)[sentinel.RETIRED], 0)

    def test_an_install_inside_it_leaves_the_retired_codes_unarmed_until_it_closes(self):
        self.reinstall_after()
        from studio.interpretation import lexicon

        code = lexicon.negation.__code__
        with sentinel.retired_unarmed():
            sentinel.uninstall()
            status = sentinel.install()
            self.assertEqual((status['state'], status['retired_control'], status['retired_armed']), ('ok', 'ok', False))
            self.assertEqual(sys.monitoring.get_local_events(4, code), 0)
        self.assertEqual(sys.monitoring.get_local_events(4, code), sys.monitoring.events.PY_START)

    def test_in_test_mode_a_retired_cache_hit_is_not_counted_inside_it(self):
        from studio.interpretation import lexicon

        with sentinel.call_checks(), sentinel.retired_unarmed(), sentinel.scope(NEW, entry='stage') as opened:
            lexicon._compiled(('no',))
            lexicon._compiled(('no',))
        self.assertEqual(opened.by_set(NEW)[sentinel.RETIRED], 0)
        with sentinel.retired_unarmed(), sentinel.call_checks(), sentinel.scope(NEW, entry='stage') as inner:
            lexicon._compiled(('no',))
        self.assertEqual(inner.by_set(NEW)[sentinel.RETIRED], 0)  # entered in either order


class StrictModeTests(SentinelCase):
    """strict(): v1's instrument by default (v1's own tests, S08 among them, run v1's events engine - retired modules -
    inside it and read its count: FINAL-V2 5.0, 8.0), the retired kind unarmed while it is open and armed again after;
    strict(retired=True) measures both kinds and refuses to open where the retired kind is not armed."""

    def test_by_default_a_retired_execution_is_not_counted_and_a_legacy_one_still_fails_it(self):
        from studio.interpretation import lexicon

        code = lexicon.negation.__code__
        with sentinel.strict('v1 record: the events engine') as opened:
            self.assertFalse(sentinel.retired_armed())
            self.assertEqual(sys.monitoring.get_local_events(4, code), 0)
            retired_call()
        self.assertEqual(opened.count(NEW), 0)  # what S08 reads after its block
        self.assertEqual(opened.by_set(NEW), {sentinel.LEGACY: 0, sentinel.RETIRED: 0})
        self.assertTrue(sentinel.retired_armed())  # armed again once it closed
        self.assertEqual(sys.monitoring.get_local_events(4, code), sys.monitoring.events.PY_START)
        with self.assertRaises(AssertionError) as caught, sentinel.strict('v1 record: a legacy call'):
            retired_call()
            legacy_call()
        self.assertIn('cues.py', str(caught.exception))  # the legacy set is still measured, and named
        self.assertNotIn('lexicon.py', str(caught.exception))

    def test_with_retired_a_retired_execution_fails_it_named_by_file_and_function(self):
        with self.assertRaises(AssertionError) as caught, sentinel.strict('v2: both kinds', retired=True) as opened:
            self.assertTrue(sentinel.retired_armed())
            retired_call()
        self.assertIn('lexicon.py', str(caught.exception))
        self.assertIn('negation', str(caught.exception))
        self.assertGreater(opened.by_set(NEW)[sentinel.RETIRED], 0)
        with sentinel.strict('v2: clean', retired=True) as clean:
            pass
        self.assertEqual(clean.count(NEW), 0)

    def test_with_retired_it_refuses_to_open_inside_the_seam(self):
        with sentinel.retired_unarmed(), self.assertRaises(AssertionError) as caught:
            with sentinel.strict('v2 inside the seam', retired=True):
                retired_call()  # never reached: it would be measured as nothing
        self.assertIn('needs the RETIRED kind armed', str(caught.exception))
        self.assertTrue(sentinel.retired_armed())

    def test_the_default_nests_inside_the_seam_and_leaves_it_open(self):
        with sentinel.retired_unarmed():
            with sentinel.strict('v1 record inside the v1 chain'):
                retired_call()
            self.assertFalse(sentinel.retired_armed())  # the outer seam is still open
        self.assertTrue(sentinel.retired_armed())


class RetiredGateTests(GateTests):
    """5.7 measure 2: the write gate refuses a new-path write when the scope counted any RETIRED execution - Tripped, and
    the AuditEvent sentinel.tripped naming the RETIRED kind apart."""

    def test_a_retired_execution_trips_the_gate(self):
        with sentinel.scope(NEW, entry='assess'):
            retired_call()
            with self.assertLogs(sentinel.log, 'ERROR'), self.assertRaises(sentinel.Tripped) as tripped:
                sentinel.gate('persist_assessment', encounter=self.encounter, actor=self.user)
        self.assertEqual(tripped.exception.reason, 'executed')
        self.assertEqual(str(tripped.exception), sentinel.MESSAGES['executed'])
        (event,) = self.trips()
        data = event.data
        self.assertEqual((data['reason'], data['refused'], data['label']), ('executed', True, NEW))
        self.assertEqual(data['new_path_by_kind'][sentinel.LEGACY], 0)
        self.assertGreater(data['new_path_by_kind'][sentinel.RETIRED], 0)
        self.assertTrue(any(line.startswith('studio/interpretation/lexicon.py:') for line in data['executed']))
        self.assertRegex(data['entry_points'][0], r'retired_call -> studio/interpretation/lexicon\.py:\d+ negation$')

    def test_a_legacy_execution_trips_it_and_the_record_names_the_legacy_kind(self):
        with sentinel.scope(NEW, entry='assess'):
            legacy_call()
            with self.assertLogs(sentinel.log, 'ERROR'), self.assertRaises(sentinel.Tripped):
                sentinel.gate('record_decision', encounter=self.encounter, actor=self.user)
        (event,) = self.trips()
        self.assertEqual(event.data['new_path_by_kind'], {sentinel.LEGACY: 1, sentinel.RETIRED: 0})

    def test_a_clean_scope_passes_and_writes_nothing(self):
        with sentinel.scope(NEW, entry='assess'):
            self.assertIsNone(sentinel.gate('persist_assessment', encounter=self.encounter, actor=self.user))
        self.assertEqual(self.trips(), [])


def retired_pattern_read():
    """One read of a retired module's compiled pattern (literals.SIZE, a 5.2 literal reader's) from the app's own code
    (tests/ lives in the app: the CALL check reads call sites under it)."""
    from studio.interpretation import literals

    return literals.SIZE.search('A 6 mm polyp')


class RetiredPatternTests(SentinelCase):
    """Refutation 6a-r1 F7: the RETIRED kind's regex class (test mode; 5.7 measures 1 and 8). A retired module's compiled
    pattern read by the app's own code is counted, of the RETIRED kind, and refuses a new-path write; the test-only seam
    leaves the retired patterns out (entered before or after the checks) and puts them back when it closes; strict counts
    them with retired=True and not by default (v1's instrument); and of the retired modules' patterns only the pinned
    twins are exempt (RETIRED_EXEMPT: the date literals contract/date_literals copies for L1, and the bare ISO date
    shape), so the L1 copy reads clean under strict(retired=True)."""

    def test_a_retired_pattern_read_is_counted_as_retired_and_refuses(self):
        from studio.interpretation import literals

        patterns, exempt = sentinel.denied_patterns()
        self.assertIn(id(literals.SIZE), patterns)
        self.assertNotIn(id(literals.SIZE), exempt)
        self.assertIn(id(literals.SIZE), sentinel.retired_patterns())
        with sentinel.call_checks(), sentinel.scope(NEW, entry='a retired pattern') as opened:
            self.assertIsNotNone(retired_pattern_read())
        self.assertEqual(opened.by_kind()[sentinel.REGEX], 1)
        self.assertEqual(opened.by_set(NEW), {sentinel.LEGACY: 0, sentinel.RETIRED: 1})
        self.assertEqual(sentinel.kind_of(id(literals.SIZE)), sentinel.RETIRED)
        self.assertEqual(sentinel.refusal(opened), 'executed')
        self.assertIn('studio.interpretation.literals.SIZE', ' '.join(opened.describe()))
        with sentinel.scope(NEW, entry='PY_START only') as unseen:  # the control: a C-level read PY_START never sees
            retired_pattern_read()
        self.assertEqual(unseen.counts(), {})
        with sentinel.call_checks(), sentinel.scope(NEW, entry='a legacy pattern') as legacy:
            cues.PAGE_NUMBER_LINE.search('3')
        self.assertEqual(legacy.by_set(NEW), {sentinel.LEGACY: 1, sentinel.RETIRED: 0})  # the kinds stay apart

    def test_the_seam_leaves_the_retired_patterns_out_in_either_order_and_puts_them_back(self):
        with sentinel.call_checks(), sentinel.retired_unarmed(), sentinel.scope(NEW, entry='v1 chain') as inside:
            retired_pattern_read()
            cues.PAGE_NUMBER_LINE.search('3')  # the legacy set is still counted
        self.assertEqual(inside.by_set(NEW), {sentinel.LEGACY: 1, sentinel.RETIRED: 0})
        with sentinel.retired_unarmed(), sentinel.call_checks(), sentinel.scope(NEW, entry='v1 chain') as entered:
            retired_pattern_read()
        self.assertEqual(entered.by_set(NEW), {sentinel.LEGACY: 0, sentinel.RETIRED: 0})
        with sentinel.call_checks():
            with sentinel.retired_unarmed():
                pass
            with sentinel.scope(NEW, entry='after the seam closed inside the checks') as after:
                retired_pattern_read()
        self.assertEqual(after.by_set(NEW), {sentinel.LEGACY: 0, sentinel.RETIRED: 1})

    def test_strict_measures_them_with_retired_and_not_by_default(self):
        with self.assertRaises(AssertionError) as caught, sentinel.strict('v2: a retired pattern', retired=True):
            retired_pattern_read()
        self.assertIn('studio.interpretation.literals.SIZE', str(caught.exception))
        with sentinel.strict('v1 record: a retired pattern') as opened:
            retired_pattern_read()
        self.assertEqual(opened.count(NEW), 0)

    def test_only_the_pinned_twins_of_the_retired_modules_are_exempt(self):
        from studio.interpretation.contract import date_literals

        patterns, _ = sentinel.denied_patterns()
        retired, exempted, denied = sentinel.retired_patterns(), set(), 0
        for name in sentinel.RETIRED_MODULES:
            for located in sentinel._pattern_globals(sys.modules[name]).values():
                for where, pattern in located.items():
                    with self.subTest(pattern=where):
                        if where in sentinel.EXEMPT_PATTERNS:
                            exempted.add(where)
                            self.assertNotIn(id(pattern), patterns)
                        else:
                            denied += 1
                            self.assertIn(id(pattern), patterns)
                            self.assertIn(id(pattern), retired)
        self.assertEqual(exempted, set(RETIRED_EXEMPT))
        self.assertGreaterEqual(denied, 15)  # lexicon's, literals' size and duration, normalize's, verify's ...
        with sentinel.strict('L1: the date literals contract/date_literals copies', retired=True) as clean:
            found = date_literals.dates('on 9 November 2026; in 2025; 2026-11-09')
            stored = date_literals.stored_date('2026-11-09', 'day')
        self.assertTrue(found)
        self.assertIsNotNone(stored)
        self.assertEqual(clean.count(NEW), 0)
