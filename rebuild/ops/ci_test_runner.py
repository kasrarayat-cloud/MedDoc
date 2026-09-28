"""Build Django's real core suite, then select one validated whole-class CI shard."""
import json
import os
from pathlib import Path
import unittest

from django.test.runner import DiscoverRunner, iter_test_cases
from .ci_test_shards import manifest, plan


class CoreShardRunner(DiscoverRunner):
    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)
        parser.add_argument('--core-shard', type=int, choices=(1, 2), required=True)
        parser.add_argument('--core-shard-manifest', required=True)

    def __init__(self, *args, core_shard=None, core_shard_manifest=None, **kwargs):
        super().__init__(*args, **kwargs)
        if type(core_shard) is not int or core_shard not in (1, 2) or not core_shard_manifest:
            raise ValueError('core_shard_configuration_missing')
        if (self.tags or self.exclude_tags or self.test_name_patterns or self.parallel > 1
                or self.pattern not in (None, 'test*.py') or self.top_level
                or self.shuffle is not False or self.reverse):
            raise ValueError('core_shards_require_unfiltered_serial_discovery')
        self.core_shard = core_shard
        self.core_shard_manifest = Path(core_shard_manifest)

    def build_suite(self, test_labels=None, **kwargs):
        if list(test_labels or []) != ['core.tests']:
            raise ValueError('core_shards_require_full_core_tests_label')
        full_suite = super().build_suite(test_labels, **kwargs)
        tests = list(iter_test_cases(full_suite))
        if self.test_loader.errors or any(isinstance(test, unittest.loader._FailedTest) for test in tests):
            raise ValueError('core_shard_discovery_failed')
        classes = {}
        for test in tests:
            name = type(test).__module__ + '.' + type(test).__qualname__
            classes.setdefault(name, []).append(test.id())
        lanes = plan(classes)
        selected_ids = set(lanes[self.core_shard - 1])
        selected = [test for test in tests if test.id() in selected_ids]
        proof = manifest(classes, self.core_shard, [test.id() for test in selected], os.getenv('GITHUB_SHA', ''))
        self.core_shard_manifest.parent.mkdir(parents=True, exist_ok=True)
        # CI starts in a fresh checkout. Never silently overwrite a prior local witness.
        with self.core_shard_manifest.open('x') as output:
            json.dump(proof, output, sort_keys=True, indent=2)
            output.write('\n')
        self.log(f"Core shard {self.core_shard}/2: {len(selected)} of {len(tests)} tests; "
                 f"universe {proof['universe_sha256']}")
        return self.test_suite(selected)
