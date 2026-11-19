"""The legacy call-guard matrix (Gemini migration slice S12; design/FINAL.md 10.4(2), 14.3 and 14.6; P7; DECISIONS D15,
D17 and D22). Synthetic data only; nothing is sent.

Legacy records are read by the legacy code, unchanged (P7). The legacy encounters here are made through the test-only
legacy chain (tests/legacy_chain.py, FINAL 14.6: every document uploaded through POST /api/encounters and read by the
legacy stages, one with Astra and Fable configured) in the states FINAL 10.4(1) names, each act asserted offered by the
legacy reading and made, never skipped where a reading does not offer it (tests/guard_support.LegacyWorld.check): an
approval and a rejection, a reinstatement, a member's answer that stands and one withdrawn, an approval carrying the
reviewer's modifier, and the participants' readings and peer reviews with the second review that reading offers, asked
and run. Then:
- LegacyLabelTests: the new-path matrix's reads on those encounters - the customer's detail, list and session, the
  operator's detail, trace and report list, the exports and their downloads, and the in-image scripts and commands
  (which meet the standing answer, and name it) - run legacy code ONLY as legacy_record: no denied execution under
  new_path, other or unscoped, and none of them trips a gate. And the legacy reader did serve them (the detail of each
  encounter counted legacy_record executions).
- LegacyByteIdentityTests: the same reads are BYTE-IDENTICAL to the c2e53f8e code's - the rollback image's - output on
  the same committed rows: the customer's detail, list and session as served, the review overlay's views, the reviewed
  coverage, the readiness, and both report renderers (the operator's and the customer's; FINAL 14.3's list). Each tree
  reads in a process of its own, at one instant held for both (a page states the server's time), and this tree reads
  again afterwards, so a read that is not stable cannot pass as identical. The c2e53f8e code is ``git archive`` of the
  commit when this repository's history holds it, or the tree CPT_STUDIO_BASELINE_TREE names - checked WHOLE against
  the pinned manifest of the archive either way (every file by path and sha256, none missing, none added, no link;
  BaselineTests). A clone with no history (CI's shallow checkout) has neither: the test then SKIPS and says why, and
  FINAL 14.3's parity on the restored dump (slice S17) is that comparison's evidence there.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from unittest import mock

from django.test import SimpleTestCase, TransactionTestCase, override_settings

from studio import interpretation, models
from studio.interpretation import readers, sentinel
from tests import guard_support
from tests.guard_support import (APP, LABELS, LEGACY, NEW, OTHER, PIPELINE_SETTINGS, UNSCOPED, GuardCase, LegacyWorld,
                                 Matrix, Pipeline, World, baseline_tree, reads)

ENC = 'api/encounters/<uuid:encounter_id>'
OPS_ENC = 'ops/api/encounters/<uuid:encounter_id>'
# the reads the legacy matrix makes of each encounter (the new-path matrix's reads, FINAL 10.4(2): "the same reads")
READS = {('url', ENC), ('url', 'api/encounters'), ('url', 'api/session'), ('url', OPS_ENC), ('url', f'{OPS_ENC}/trace'),
         ('url', f'{OPS_ENC}/reports'), ('url', f'{ENC}/reports'), ('url', 'api/reports/<uuid:report_id>/download'),
         ('url', 'ops/api/reports/<uuid:report_id>/download'), ('script', 'RECOMPUTE_STATES'),
         ('script', 'UNDO_HAZARDS_READ'), ('script', 'INSTALLED_STATES'), ('script', 'CLOSE_STAGES'),
         ('command', 'interpretation_report')}


class LegacyLabelTests(GuardCase):
    def test_every_denied_execution_of_the_legacy_reads_is_labelled_legacy_record(self):
        legacy = LegacyWorld(self).build()
        names = [name for name, _ in LegacyWorld.SCENARIOS]
        for name in names:
            encounter = legacy.encounter(name)
            self.assertEqual(readers.label_of(encounter), LEGACY)
            self.assertFalse(interpretation.is_new_assessment(encounter.current_assessment))
        decisions = set(models.Decision.objects.values_list('action', flat=True))
        self.assertTrue({'approve', 'reject'} <= decisions, decisions)  # the member's acts on the legacy records
        matrix = Matrix(self)
        world = World(self, matrix, operator=(legacy.operator_user, legacy.operator))
        world.ids = dict(legacy.ids)
        with sentinel.call_checks():
            for name in names:
                world.reads(name)
                world.exports(name)
            world.in_image(reassess='L1', answered=LegacyWorld.ANSWERED)
        self.assertLessEqual(READS, matrix.keys())
        self.assertEqual(matrix.red((NEW, OTHER, UNSCOPED)), [], matrix.report((NEW, OTHER, UNSCOPED)))
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())
        # the legacy reader served each encounter's page (FINAL 10.4(2): its executions are legacy_record's)
        details = [item for item in matrix.observations if item.key == ('url', ENC)]
        self.assertEqual(len(details), len(names))
        self.assertTrue(all(item.count(LEGACY) > 0 for item in details), [item.describe() for item in details])
        self.assertEqual(sum(item.count(LABELS) for item in matrix.observations),
                         sum(item.count(LEGACY) for item in matrix.observations))
        # the re-assessment from retained answers refuses a legacy final (D16, FINAL 6.10): an exit, nothing queued
        [refused] = [item for item in matrix.observations if item.key == ('command', 'reassess_retained')]
        self.assertEqual(refused.detail['exit'], 1)


@override_settings(**PIPELINE_SETTINGS)
class LegacyByteIdentityTests(Pipeline, TransactionTestCase):
    NOW = '2026-11-10T12:00:00+00:00'

    def test_the_legacy_reads_are_byte_identical_to_the_c2e53f8e_codes(self):
        legacy = LegacyWorld(self).build()
        names = [name for name, _ in LegacyWorld.SCENARIOS]
        ids = [legacy.ids[name] for name in names]
        for pk in ids:
            self.assertFalse(interpretation.is_new_assessment(models.Encounter.objects.get(pk=pk).current_assessment))
        params = {'user': str(self.user.pk), 'now': self.NOW, 'encounters': ids,
                  'paths': ['/api/session', '/api/encounters'] + [f'/api/encounters/{pk}' for pk in ids]}
        with tempfile.TemporaryDirectory(prefix='s12-baseline-') as scratch:
            tree, how = baseline_tree(Path(scratch) / 'baseline')
            if tree is None:
                self.skipTest(how)
            mine = reads(APP, params)
            theirs = reads(tree, params)
            again = reads(APP, params)
            # the control: one line planted in the operator renderer of a COPY of the c2e53f8e code is seen
            planted = Path(scratch) / 'planted'
            shutil.copytree(tree, planted)
            source = (planted / 'studio' / 'reports.py').read_text(encoding='utf-8')
            anchor = 'lines = [HEADLINES[kind], SYNTHETIC_LINE]'
            self.assertEqual(source.count(anchor), 1)
            planted_line = "lines = [HEADLINES[kind], SYNTHETIC_LINE, 'S12-PLANTED-LINE']"
            (planted / 'studio' / 'reports.py').write_text(source.replace(anchor, planted_line), encoding='utf-8')
            self.assertIn('S12-PLANTED-LINE', (planted / 'studio' / 'reports.py').read_text(encoding='utf-8'))
            control = reads(planted, params)
        print(f'\n[S12 legacy byte-identity] the c2e53f8e code from {how}: {len(mine)} reads compared')
        expected = 2 + len(ids) + len(ids) * 7  # the session, the list and each detail; per encounter seven reads
        self.assertEqual(len(mine), expected)
        self.assertEqual(sorted(mine), sorted(theirs))
        self.assertEqual({name: value for name, value in again.items() if value != mine[name]}, {})  # stable reads
        differ = sorted(name for name in mine if mine[name] != theirs[name])
        self.assertEqual(differ, [], '\n'.join(f'{name}: this tree {mine[name][:300]!r}\n'
                                               f'  c2e53f8e {theirs[name][:300]!r}' for name in differ[:5]))
        # the comparison sees a one-line change: exactly the operator reports that render differ in the planted copy
        seen = sorted(name for name in mine if control[name] != theirs[name])
        rendered = sorted(name for name in mine if name.startswith('operator report ') and b'SYNTHETIC' in mine[name])
        self.assertEqual(seen, rendered)
        self.assertTrue(rendered and all(b'S12-PLANTED-LINE' in control[name] for name in seen))
        # what was compared is substantive: every page served, each encounter's views and both renderers' text
        for pk in ids:
            self.assertTrue(mine[f'GET /api/encounters/{pk}'].startswith(b'200 {'))
            self.assertGreater(len(mine[f'views {pk}']), 1000)
            self.assertIn(b'SYNTHETIC', mine[f'operator report draft {pk}'])
            self.assertIn(b'SYNTHETIC', mine[f'customer report draft {pk}'])


class BaselineTests(SimpleTestCase):
    """What is compared is the c2e53f8e code, or nothing - and then the test says why."""

    def test_a_tree_that_is_not_the_c2e53f8e_code_is_refused(self):
        with tempfile.TemporaryDirectory() as scratch, \
                mock.patch.object(guard_support, 'BASELINE', '0' * 40), \
                mock.patch.dict('os.environ', {'CPT_STUDIO_BASELINE_TREE': str(APP)}):
            tree, why = baseline_tree(Path(scratch))
        self.assertIsNone(tree)
        self.assertIn('is not the c2e53f8e code', why)  # this tree's own files differ from the pins
        self.assertIn('studio/review.py', why)

    def test_with_no_history_and_no_tree_nothing_is_compared_and_it_says_so(self):
        environment = {key: value for key, value in __import__('os').environ.items()
                       if key != 'CPT_STUDIO_BASELINE_TREE'}
        with tempfile.TemporaryDirectory() as scratch, \
                mock.patch.object(guard_support, 'BASELINE', '0' * 40), \
                mock.patch.dict('os.environ', environment, clear=True):
            tree, why = baseline_tree(Path(scratch))
        self.assertIsNone(tree)
        self.assertIn('the reads are not compared with the c2e53f8e code here', why)

    def test_the_pins_are_the_c2e53f8e_files(self):
        with tempfile.TemporaryDirectory() as scratch:
            tree, how = baseline_tree(Path(scratch))
            if tree is None:
                self.skipTest(how)
            self.assertEqual(guard_support._pinned(tree), [])
            self.assertTrue(guard_support._pinned(APP))  # this tree is not that code
            # the whole archive is the pinned manifest: every one of its files, by path and sha256
            self.assertEqual(guard_support.manifest(tree),
                             (guard_support.BASELINE_MANIFEST, guard_support.BASELINE_FILES, []))
            self.assertNotEqual(guard_support.manifest(APP)[0], guard_support.BASELINE_MANIFEST)

    def test_a_named_tree_is_the_c2e53f8e_code_only_when_every_file_is(self):
        # the review of S12, finding 6: a tree CPT_STUDIO_BASELINE_TREE names is compared with only when it holds every
        # file of the c2e53f8e archive, unchanged, and nothing else - a later serializers.py (no pin names it), a file
        # added or removed, or a link in place of a file is refused
        with tempfile.TemporaryDirectory() as scratch:
            archive, how = baseline_tree(Path(scratch) / 'archive')
            if archive is None:
                self.skipTest(how)
            made = []

            def named(change):
                tree = Path(scratch) / f'named-{len(made)}'
                made.append(tree)
                shutil.copytree(archive, tree)
                change(tree)
                with mock.patch.object(guard_support, 'BASELINE', '0' * 40), \
                        mock.patch.dict('os.environ', {'CPT_STUDIO_BASELINE_TREE': str(tree)}):
                    return baseline_tree(Path(scratch) / 'unused')

            def later(tree):
                (tree / 'studio' / 'serializers.py').write_bytes((APP / 'studio' / 'serializers.py').read_bytes())

            def added(tree):
                (tree / 'studio' / '__pycache__').mkdir()
                (tree / 'studio' / '__pycache__' / 'serializers.cpython-312.pyc').write_bytes(b'synthetic')

            def removed(tree):
                (tree / 'studio' / 'answers.py').unlink()

            def linked(tree):
                kept = Path(scratch) / 'api-copy.py'
                kept.write_bytes((tree / 'studio' / 'api.py').read_bytes())
                (tree / 'studio' / 'api.py').unlink()
                (tree / 'studio' / 'api.py').symlink_to(kept)

            tree, why = named(lambda tree: None)
            self.assertEqual(tree, made[-1], why)  # the archive itself, named: compared with
            for what, change in (('a later serializers.py', later), ('a file added', added),
                                 ('a file removed', removed), ('a link in place of a file', linked)):
                with self.subTest(what):
                    self.assertEqual(guard_support._pinned(archive), [])
                    tree, why = named(change)
                    self.assertIsNone(tree, f'{what}: accepted as the c2e53f8e code')
                    self.assertIn('is not the c2e53f8e code', why)
