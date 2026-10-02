"""Pure shard coverage/refusal checks; never runs the core suite or opens a DB."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from django.test.runner import DiscoverRunner
from ops.ci_test_runner import CoreShardRunner
from ops.ci_test_shards import manifest, plan, verify_manifests

SHA = 'a' * 40


def synthetic_tests():
    tests = []
    for name, count in [('A', 6), ('B', 4), ('C', 3), ('D', 2), ('E', 1)]:
        cls = type(name, (unittest.TestCase,), {'__module__': 'synthetic',
                   **{f'test_{i}': lambda self: None for i in range(count)}})
        tests.extend(cls(f'test_{i}') for i in range(count))
    return tests


def classes_for(tests):
    classes = {}
    for test in tests:
        name = type(test).__module__ + '.' + type(test).__qualname__
        classes.setdefault(name, []).append(test.id())
    return classes


class CoreShardContracts(unittest.TestCase):
    def test_plan_is_deterministic_complete_disjoint_balanced_and_whole_class(self):
        classes = classes_for(synthetic_tests())
        lanes = plan(classes)
        self.assertEqual(list(map(len, lanes)), [8, 8])
        self.assertEqual(lanes, plan({name: list(reversed(ids)) for name, ids in reversed(list(classes.items()))}))
        self.assertFalse(set(lanes[0]) & set(lanes[1]))
        self.assertEqual(sorted(lanes[0] + lanes[1]), sorted(t.id() for t in synthetic_tests()))
        for ids in classes.values():
            self.assertEqual(sum(set(ids) <= set(lane) for lane in lanes), 1)

    def test_invalid_empty_or_duplicate_discovery_refuses(self):
        cases = [{}, {'one.Case': ['one.Case.test']},
                 {'one.Case': [], 'two.Case': ['two.Case.test']},
                 {'one.Case': ['one.Case.test', 'one.Case.test'], 'two.Case': ['two.Case.test']},
                 {'one.Case': ['foreign.Case.test'], 'two.Case': ['two.Case.test']}]
        for classes in cases:
            with self.subTest(classes=classes), self.assertRaises(ValueError):
                plan(classes)

    def test_runner_uses_full_real_discovery_then_preserves_order_and_once_only_ids(self):
        tests = synthetic_tests()
        selected = []
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for shard in (1, 2):
                path = Path(directory) / f'{shard}.json'
                runner = CoreShardRunner(core_shard=shard, core_shard_manifest=path, verbosity=0)
                runner.test_loader = unittest.TestLoader()
                with patch.object(DiscoverRunner, 'build_suite', return_value=unittest.TestSuite(tests)) as build, patch.dict('os.environ', GITHUB_SHA=SHA):
                    result = list(runner.build_suite(['core.tests']))
                build.assert_called_once_with(['core.tests'])
                self.assertEqual(result, [test for test in tests if test in result])
                selected.extend(test.id() for test in result)
                paths.append(path)
            summary = verify_manifests(paths, SHA)
            self.assertEqual((summary['tests'], summary['classes'], summary['shard_counts']), (16, 5, [8, 8]))
            self.assertEqual(sorted(selected), sorted(test.id() for test in tests))

    def test_runner_discovery_errors_and_duplicate_tests_refuse_before_manifest(self):
        tests = synthetic_tests()
        cases = [('loader', tests), ('failed', [unittest.loader._FailedTest('broken_module', ImportError('synthetic'))] + tests),
                 ('duplicate', tests + tests[:1]), ('empty', [])]
        for kind, caseset in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'manifest.json'
                runner = CoreShardRunner(core_shard=1, core_shard_manifest=path, verbosity=0)
                runner.test_loader = unittest.TestLoader()
                if kind == 'loader':
                    runner.test_loader.errors.append('synthetic discovery error')
                with patch.object(DiscoverRunner, 'build_suite', return_value=unittest.TestSuite(caseset)), patch.dict('os.environ', GITHUB_SHA=SHA), self.assertRaises(ValueError):
                    runner.build_suite(['core.tests'])
                self.assertFalse(path.exists())

    def test_runner_rejects_filters_parallelism_labels_and_missing_identity(self):
        for kwargs in [{'tags': ['x']}, {'exclude_tags': ['x']}, {'test_name_patterns': ['x']},
                       {'parallel': 2}, {'pattern': 'test_small.py'}, {'top_level': '/tmp'},
                       {'shuffle': 1}, {'reverse': True}, {'core_shard': 0}, {'core_shard': True}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                CoreShardRunner(**({'core_shard': 1, 'core_shard_manifest': '/unused'} | kwargs))
        runner = CoreShardRunner(core_shard=1, core_shard_manifest='/unused', verbosity=0)
        with patch.object(DiscoverRunner, 'build_suite') as build:
            for labels in (None, [], ['core'], ['core.tests.one'], ['core.tests', 'core.tests']):
                with self.subTest(labels=labels), self.assertRaises(ValueError):
                    runner.build_suite(labels)
            build.assert_not_called()
        with patch.object(DiscoverRunner, 'build_suite', return_value=unittest.TestSuite(synthetic_tests())), patch.dict('os.environ', GITHUB_SHA=''), self.assertRaises(ValueError):
            runner.build_suite(['core.tests'])

    def test_manifest_mutations_missing_duplicate_foreign_source_and_universe_refuse(self):
        classes = classes_for(synthetic_tests())
        lanes = plan(classes)
        original = [manifest(classes, i + 1, lanes[i], SHA) for i in range(2)]
        for kind in ('missing', 'duplicate_shard', 'source', 'universe', 'selection_missing', 'selection_extra',
                     'selection_duplicate', 'discovery_differs', 'extra_key', 'hash', 'format_bool',
                     'classes_null', 'row_null'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                rows = copy.deepcopy(original)
                if kind == 'missing': rows.pop()
                elif kind == 'duplicate_shard': rows[1] = rows[0]
                elif kind == 'source': rows[1]['source_sha'] = 'b' * 40
                elif kind == 'universe': rows[1]['classes'].pop(next(iter(classes)))
                elif kind == 'selection_missing': rows[1]['selected'].pop()
                elif kind == 'selection_extra': rows[1]['selected'].append(rows[0]['selected'][0])
                elif kind == 'selection_duplicate': rows[1]['selected'].append(rows[1]['selected'][0])
                elif kind == 'discovery_differs':
                    changed = copy.deepcopy(classes); changed['synthetic.New'] = ['synthetic.New.test']
                    rows[1] = manifest(changed, 2, plan(changed)[1], SHA)
                elif kind == 'extra_key': rows[1]['allow_missing'] = True
                elif kind == 'hash': rows[1]['universe_sha256'] = 'f' * 64
                elif kind == 'format_bool': rows[1]['format'] = True
                elif kind == 'classes_null': rows[1]['classes'] = None
                elif kind == 'row_null': rows[1] = None
                paths = []
                for i, row in enumerate(rows):
                    p = Path(directory) / f'{i}.json'; p.write_text(json.dumps(row)); paths.append(p)
                with self.assertRaises(ValueError):
                    verify_manifests(paths, SHA)

    def test_manifest_file_must_be_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing.json'; path.write_text('preserved')
            runner = CoreShardRunner(core_shard=1, core_shard_manifest=path, verbosity=0)
            runner.test_loader = unittest.TestLoader()
            with patch.object(DiscoverRunner, 'build_suite', return_value=unittest.TestSuite(synthetic_tests())), patch.dict('os.environ', GITHUB_SHA=SHA), self.assertRaises(FileExistsError):
                runner.build_suite(['core.tests'])
            self.assertEqual(path.read_text(), 'preserved')
