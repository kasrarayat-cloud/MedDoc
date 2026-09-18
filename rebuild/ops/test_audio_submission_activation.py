"""The audio-submission activator's static guards, proved against the real repository.

This activation carries NO migration, so its declared delta is EMPTY. That makes the interesting guards the ones that
assert absence — no migration in the range, no schema difference across the act, no comparable= escape hatch on the
fingerprints — and absence is exactly what a check can claim while never being able to detect it. Each one below is
therefore exercised against a planted counterexample, not merely called.
"""
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

from exercised import requires_input

ROOT = Path(__file__).resolve().parents[2]


def load_activator():
    spec = importlib.util.spec_from_file_location('activate_audio_submission',
                                                  ROOT / 'scripts/activate-audio-submission.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source():
    return (ROOT / 'scripts/activate-audio-submission.py').read_text()


class ThreeRevisionsAreThreeFacts(unittest.TestCase):
    """The tree's HEAD, the release the services answer, and the target are separate and must stay separate."""

    def test_the_baseline_and_the_running_release_are_different_commits(self):
        activator = load_activator()
        self.assertNotEqual(activator.BASELINE, activator.RUNNING_RELEASE,
                            'if these were equal this activator would not need to distinguish them, and the '
                            'distinction is the reason it exists')
        for name in ('BASELINE', 'RUNNING_RELEASE'):
            self.assertRegex(getattr(activator, name), r'^[a-f0-9]{40}$', name)

    def test_the_declared_change_set_is_measured_from_the_running_release_not_the_tree(self):
        """Measuring from the tree's HEAD would silently exempt everything already merged and never deployed — which
        here is a whole milestone, including the file this change builds on."""
        body = source()
        self.assertIn("output(['git', 'diff', '--name-only', RUNNING_RELEASE, args.target]", body)
        self.assertNotIn("output(['git', 'diff', '--name-only', BASELINE, args.target]).splitlines()", body)

    def test_the_undeployed_milestone_is_inside_the_declared_set(self):
        activator = load_activator()
        for path in ('rebuild/exercised.py', 'scripts/activate-service-date.py', '.github/workflows/test.yml'):
            self.assertIn(path, activator.ALLOWED,
                          'a path already merged but never deployed is part of what this activation ships')


class TheDeclarationMustBeVISIBLEToItsOwnGate(unittest.TestCase):
    """The ruled-mutation gate refused this activation, and it was right to.

    It checks that the declaration is TRACKED and COMMITTED in the tree the act runs in. This activation's declaration
    ships in the very commit it activates, so while the activator advanced `main` ITSELF the declaration existed only
    in a worktree the gate cannot see, and it reported `tracked: no`. **An activation whose declaration is invisible
    to its own gate is a gate that cannot fire** — and nothing would have said so except the refusal.

    The tree is fast-forwarded first now. Advancing it is reversible bookkeeping, not part of the act; the act is the
    release line and the restart.
    """

    def test_the_act_does_not_advance_the_tree_itself(self):
        self.assertNotIn("run(['git', 'merge', '--ff-only'", source(),
            'advancing the tree inside the act puts the declaration out of the gate\'s sight again')

    def test_it_requires_the_tree_to_be_at_the_target_already(self):
        body = source()
        self.assertIn("output(['git', 'rev-parse', 'HEAD']) == args.target", body)
        self.assertNotIn("output(['git', 'rev-parse', 'HEAD']) == BASELINE", body)

    def test_it_asserts_the_declaration_is_tracked_in_this_tree(self):
        self.assertIn("run(['git', 'ls-files', '--error-unmatch', DECL]", source(),
            'the preflight must fail on the same condition the gate would, rather than leaving it to the gate after '
            'the services are already stopped')

    def test_the_previous_tree_head_is_still_recorded(self):
        """BASELINE stops being the required HEAD and does not stop being a fact: the range judged runs from the
        RUNNING RELEASE and must contain the commit the tree came from."""
        activator = load_activator()
        self.assertRegex(activator.BASELINE, r'^[a-f0-9]{40}$')
        self.assertIn('BASELINE, args.target', source())
        self.assertIn('RUNNING_RELEASE, BASELINE', source())


class TheDeclaredDeltaIsEmpty(unittest.TestCase):
    def test_no_migration_may_appear_in_the_range(self):
        self.assertIn("'rebuild/core/migrations']) == ''", source())

    def test_the_fingerprints_offer_no_subtraction(self):
        """The migration-carrying activators take comparable= to drop what their migration adds. Here nothing may be
        dropped, and an unused escape hatch is the one a later edit reaches for."""
        activator = load_activator()
        import inspect
        self.assertNotIn('comparable', inspect.signature(activator.fingerprints).parameters)
        self.assertNotIn('comparable', inspect.getsource(activator.fingerprints).split('"""')[-1])

    def test_every_before_snapshot_is_compared_after(self):
        """A snapshot taken and never compared is evidence nobody reads."""
        body = source()
        for name in ('schema', 'constraints', 'indexes', 'database', 'clinical', 'storage'):
            self.assertIn("result['%s_before']" % name, body, name)
        for comparison in ('schema() == result[\'schema_before\']', 'constraints() == result[\'constraints_before\']',
                           'indexes() == result[\'indexes_before\']',
                           'fingerprints(old_tables) == result[\'database_before\']',
                           'clinical_counts() == result[\'clinical_before\']'):
            self.assertIn(comparison, body, comparison)


class TheWorkerIsIdentifiedByMoreThanItsPid(unittest.TestCase):
    """PID alone is insufficient: a PID is reused, so one read in one place and checked in another describes whatever
    holds it now. Start time, command and cgroup membership together cannot be satisfied by a stale process."""

    def test_the_worker_check_reads_start_time_command_and_cgroup(self):
        body = ast.dump(ast.parse(source()))
        for evidence in ('cmdline', 'cgroup', 'btime', 'ExecMainStartTimestamp'):
            self.assertIn(evidence, body, evidence)

    def test_a_restart_is_proved_by_the_start_time_moving(self):
        self.assertIn("worker_after['systemd_start'] != worker_before['systemd_start']", source())

    def test_it_describes_this_host_correctly(self):
        activator = load_activator()
        # ⚠️ THE SKIP IS NARROWED TO THE SERVICE BEING ABSENT, because the wide form hid a real defect. Catching every
        # exception turned 'the activator asserts the wrong command' into 'NOT EXERCISED', and the activator would
        # have refused a correctly running worker at the worst possible moment. A host gap is a skip; a live service
        # that does not match what the activator claims is a FAILURE.
        try:
            state = activator.output(['systemctl', 'show', 'quillmd-fresh-worker.service', '--property=ActiveState', '--value'])
        except Exception as error:                                   # noqa: BLE001 - the reason is the message
            raise unittest.SkipTest('Worker identification NOT EXERCISED: systemctl is unavailable here (%s)' % error)
        if state != 'active':
            raise unittest.SkipTest('Worker identification NOT EXERCISED: the worker is %s on this host' % state)
        described = activator.worker_process()
        self.assertIn('manage.py', described['command'])
        self.assertEqual(described['command'].split()[-1], 'worker')
        self.assertIn('.venv/bin/python', described['command'])
        self.assertIn(described['unit'], described['cgroup'])
        self.assertGreater(described['pid'], 0)
        requires_input(bool(described['systemd_start']), "systemd's own record of when it started the main process")


class TheNewRuntimeDependencyIsVerified(unittest.TestCase):
    def test_both_media_tools_must_resolve_before_the_act(self):
        activator = load_activator()
        self.assertEqual(activator.MEDIA_TOOLS, ('ffmpeg', 'ffprobe'))
        # ⚠️ THIS SKIPPED ITSELF ON EXACTLY THE CONDITION IT EXISTS TO REPORT. `except Exception: raise SkipTest`
        # swallowed the missing-tool refusal, so the one test written to assert the dependency reported NOT EXERCISED
        # instead of failing. In CI, where the workflow installs both tools, absence is a broken promise and fails.
        try:
            found = activator.media_tools()
        except Exception as error:                                   # noqa: BLE001
            requires_input(not os.getenv('CI'),
                           'the media tools the workflow installs, which CI guaranteed and did not supply (%s)' % error)
            raise unittest.SkipTest('Media tools NOT EXERCISED on this host: %s' % error)
        for name in activator.MEDIA_TOOLS:
            self.assertTrue(found[name]['path'].startswith('/'), name)
            self.assertIn('version', found[name]['version'].lower(), name)

    def test_a_missing_tool_refuses_rather_than_degrading(self):
        """Without ffmpeg the application still works — every recording is submitted exactly as uploaded — which is
        why the activation has to check, and why the check has to be proved to fail."""
        activator = load_activator()
        original = activator.output
        activator.output = lambda command, **kwargs: '' if 'command -v' in ' '.join(command) else original(command, **kwargs)
        try:
            with self.assertRaises(RuntimeError) as refusal:
                activator.media_tools()
        finally:
            activator.output = original
        self.assertIn('not installed', str(refusal.exception))


class AllowedPaths(unittest.TestCase):
    def test_the_activation_declares_its_own_parts(self):
        activator = load_activator()
        for path in (activator.DECL, activator.SELF, 'rebuild/ops/test_audio_submission_activation.py',
                     'rebuild/core/media.py', 'rebuild/core/jobs.py'):
            self.assertIn(path, activator.ALLOWED, path)

    def test_every_path_this_branch_changes_was_declared(self):
        activator = load_activator()
        for commit in (activator.RUNNING_RELEASE,):
            if subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', commit + '^{commit}'],
                              capture_output=True).returncode:
                self.skipTest('The activation range is not available in this checkout (shallow clone).')
        changed = set(subprocess.check_output(
            ['git', '-C', str(ROOT), 'diff', '--name-only', activator.RUNNING_RELEASE, 'HEAD'], text=True).split())
        requires_input(changed != set(),
                       'a non-empty diff between the running release and this tree — an empty range would make this '
                       'comparison pass while proving nothing about what ships')
        self.assertEqual(sorted(changed - activator.ALLOWED), [])

    def test_the_declaration_it_names_exists(self):
        activator = load_activator()
        self.assertTrue((ROOT / activator.DECL).is_file(), activator.DECL)


if __name__ == '__main__':
    unittest.main()
