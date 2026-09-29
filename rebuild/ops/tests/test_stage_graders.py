"""The frozen diagnostic graders the stage runner uses (docs/rebuild/v1/sonnet5-campaign/diagnostics), offline.

Every grader is run in a SUBPROCESS: measure_baseline.py and offline_replay.py deny sockets for their whole process at
import, so importing them here would change this test process's network behaviour.

  · R1 — grade_app_path.grade_output never grades `held_safe` an area whose covering field is a KEPT WRONG field held
    only by a slot-level record (the clinician's 'not an answer' on such a record removes nothing): it is `wrong`, with
    hold_reaches_field false recorded; a field verdict or a keyed record over the covering field still holds it, and a
    slot record over an UNCOVERED area still holds it.
  · R2 — grade_app_path --grade / --self-test and offline_replay --replay REFUSE (exit 2, nothing written) unless every
    file EXPECTED-SHA256SUMS lists matches (and every expected map is listed), and record the manifest, grader and
    candidate sha256 in what they write.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
DIAGNOSTICS = REPOSITORY / 'docs' / 'rebuild' / 'v1' / 'sonnet5-campaign' / 'diagnostics'
PYTHON = sys.executable


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, cwd=None, timeout=600):
    env = {'PATH': '/usr/bin:/bin', 'TMPDIR': '/tmp', 'HOME': '/tmp', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run([PYTHON, '-B', *map(str, args)], capture_output=True, text=True, timeout=timeout, cwd=cwd,
                          env=env)


def copy_diagnostics(test):
    """A private copy of the diagnostics tree at the same depth (docs/rebuild/v1/sonnet5-campaign/diagnostics) beside a
    link to this checkout's rebuild/, so the copied graders resolve their candidate exactly as the originals do."""
    root = Path(tempfile.mkdtemp(prefix='stage-graders-'))
    test.addCleanup(shutil.rmtree, root, True)
    target = root / 'docs' / 'rebuild' / 'v1' / 'sonnet5-campaign' / 'diagnostics'
    shutil.copytree(DIAGNOSTICS, target)
    os.symlink(REPOSITORY / 'rebuild', root / 'rebuild')
    return root, target


# ── R1: a slot-level record over a kept wrong field is not a hold ─────────────────────────────────────────────────
GRADE_SNIPPET = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import grade_app_path as g
case = json.loads(sys.stdin.read())
print(json.dumps(g.grade_output(case["expected"], case["output"], case.get("deterministic"))))
'''

EXPECTED = {'areas': [
    {'id': 'T.A1', 'label': 'Date the lead agency was last informed', 'kind': 'date', 'options': [],
     'destination': {'region': 'b/tbl[0]/tr[1]/tc[1]', 'answer_at': 'b/tbl[0]/tr[1]/tc[1]/p[0]'},
     'must_name': ['lead agency'], 'must_not_name': ['State yes or no']},
    {'id': 'T.A2', 'label': 'Uncovered answer', 'kind': 'text', 'options': [],
     'destination': {'region': 'b/p[7]', 'answer_at': 'b/p[7]'}}], 'controls': []}


def field(key, label, slot, kind='date'):
    return {'key': key, 'label': label, 'kind': kind, 'context': '',
            'locator': {'part': 'word/document.xml', 'slot': slot, 'target': {'type': 'cell'}}}


LEAKED = field('v3_2', 'Date the lead agency was last informed — State yes or no.', 'b/tbl[0]/tr[1]/tc[1]')
CLEAN = field('v3_2', 'Date the lead agency was last informed', 'b/tbl[0]/tr[1]/tc[1]')


def output(fields, records=(), field_verdicts=()):
    return {'fields': fields,
            'review': {'verdicts': {'fields': [{'key': k, 'verdict': v} for k, v in field_verdicts], 'slots': []},
                       'areas': [], 'unresolved': [{'slot': 'word/document.xml#' + slot, 'key': key, 'reason': 'r',
                                                    'text': ''} for slot, key in records]}}


class SlotRecordOverAKeptFieldTests(unittest.TestCase):
    """R1: grade_app_path.grade_output (the frozen grader), in a subprocess."""

    def graded(self, out):
        done = subprocess.run([PYTHON, '-B', '-c', GRADE_SNIPPET, str(DIAGNOSTICS / 'mapping')],
                              input=json.dumps({'expected': EXPECTED, 'output': out}), capture_output=True, text=True,
                              timeout=120, env={'PATH': '/usr/bin:/bin', 'TMPDIR': '/tmp', 'HOME': '/tmp',
                                                'LANG': 'C.UTF-8'})
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        graded = json.loads(done.stdout)
        return {r['id']: r for r in graded['areas']}, graded['summary']

    def test_a_slot_record_over_a_kept_wrong_field_is_wrong_not_held(self):
        for slot in ('b/tbl[0]/tr[1]/tc[1]/p[0]', 'b/tbl[0]/tr[1]/tc[1]', 'b/tbl[0]'):
            with self.subTest(slot=slot):
                areas, summary = self.graded(output([LEAKED], records=[(slot, '')]))
                self.assertEqual(areas['T.A1']['outcome'], 'wrong')
                self.assertIs(areas['T.A1']['hold']['hold_reaches_field'], False)
                self.assertTrue(any('State yes or no' in p for p in areas['T.A1']['problems']), areas['T.A1'])
                self.assertEqual(summary.get('areas_held_safe', 0), 0)
                self.assertEqual(summary['areas_slot_record_over_kept_field'], 1)

    def test_a_field_verdict_or_a_keyed_record_still_holds_the_kept_field(self):
        for held in (output([LEAKED], field_verdicts=[('v3_2', 'uncertain')]),
                     output([LEAKED], field_verdicts=[('v3_2', 'not_answer')]),
                     output([LEAKED], records=[('b/tbl[0]/tr[1]/tc[1]', 'v3_2')])):
            with self.subTest(held=held['review']):
                areas, _ = self.graded(held)
                self.assertEqual(areas['T.A1']['outcome'], 'held_safe')
                self.assertIs(areas['T.A1']['hold']['hold_reaches_field'], True)
                self.assertEqual(areas['T.A1']['field_grade_under_hold'], 'wrong')

    def test_a_slot_record_over_a_right_field_leaves_it_right_and_one_over_an_uncovered_area_holds_it(self):
        areas, summary = self.graded(output([CLEAN], records=[('b/tbl[0]/tr[1]/tc[1]/p[0]', ''), ('b/p[7]', '')]))
        self.assertEqual(areas['T.A1']['outcome'], 'right')
        self.assertIs(areas['T.A1']['hold']['hold_reaches_field'], False)
        self.assertEqual(areas['T.A2']['outcome'], 'held_safe')
        self.assertIs(areas['T.A2']['hold']['hold_reaches_field'], True)
        areas, _ = self.graded(output([CLEAN]))
        self.assertEqual((areas['T.A1']['outcome'], areas['T.A2']['outcome']), ('right', 'missed'))


# ── R2: the live graders enforce and record the freeze ─────────────────────────────────────────────────────────────
class FreezeEnforcedTests(unittest.TestCase):
    """R2: a copy of the diagnostics tree; the graders there refuse on any mismatch with EXPECTED-SHA256SUMS."""

    def setUp(self):
        self.root, self.copy = copy_diagnostics(self)
        self.scratch = Path(tempfile.mkdtemp(prefix='stage-graders-out-'))
        self.addCleanup(shutil.rmtree, self.scratch, True)
        self.graded_input = self.scratch / 'output.json'
        self.graded_input.write_text(json.dumps({'fields': [], 'review': {}}))

    def grade(self, form='f5-negative-controls'):
        out = self.scratch / f'graded-{form}.json'
        if out.exists():
            out.unlink()
        done = run([self.copy / 'mapping' / 'grade_app_path.py', '--grade', self.graded_input, '--form', form,
                    '--out', out])
        return done, out

    def replay(self, cases=None):
        responses = self.scratch / 'responses.json'
        responses.write_text('{}')
        out = self.scratch / 'replayed.json'
        if out.exists():
            out.unlink()
        args = [self.copy / 'notes' / 'offline_replay.py', '--state-dir', self.scratch / 'state', '--replay', responses,
                '--skip-form-check', '--out', out]
        if cases:
            args += ['--cases', cases]
        return run(args, timeout=900), out

    def test_grade_records_the_manifest_grader_map_and_candidate(self):
        done, out = self.grade()
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        provenance = json.loads(out.read_text())['provenance']
        self.assertEqual(provenance['manifest_sha256'], sha256(self.copy / 'mapping' / 'EXPECTED-SHA256SUMS'))
        self.assertEqual(provenance['grader_sha256'], sha256(self.copy / 'mapping' / 'grade_app_path.py'))
        self.assertEqual(provenance['inputs']['map'], sha256(self.copy / 'mapping' / 'f5-negative-controls.expected.json'))
        self.assertEqual(provenance['inputs']['graded'], sha256(self.graded_input))
        self.assertEqual(provenance['candidate']['commit'], '8e3dcfd07a5946430e7291b520faf35c8055127b')
        self.assertIn('engine_sha256', provenance['candidate'])
        self.assertTrue(provenance['frozen_files_match'])

    def test_grade_refuses_an_altered_map_and_writes_nothing(self):
        # (the recheck's positive control: f5.C2 changed from must_refuse to not_an_answer graded do-nothing RIGHT)
        path = self.copy / 'mapping' / 'f5-negative-controls.expected.json'
        text = path.read_text()
        anchor = '"id": "f5.C2",\n      "type": "must_refuse"'
        self.assertEqual(text.count(anchor), 1)
        path.write_text(text.replace(anchor, anchor.replace('must_refuse', 'not_an_answer')))
        done, out = self.grade()
        self.assertEqual(done.returncode, 2, done.stdout[-2000:])
        self.assertIn('f5-negative-controls.expected.json', done.stderr)
        self.assertFalse(out.exists())

    def test_grade_refuses_any_altered_frozen_file_or_an_unlisted_map(self):
        for name in ('check_expected.py', '../notes/cases.json', 'measure_baseline.py'):
            with self.subTest(name=name):
                path = self.copy / 'mapping' / name
                original = path.read_bytes()
                path.write_bytes(original + b'\n')
                done, out = self.grade()
                self.assertEqual(done.returncode, 2, done.stdout[-2000:])
                self.assertFalse(out.exists())
                path.write_bytes(original)
        stray = self.copy / 'mapping' / 'f9-unlisted.expected.json'
        shutil.copy(self.copy / 'mapping' / 'f6b-admin-missing.expected.json', stray)
        done, out = self.grade()
        self.assertEqual(done.returncode, 2)
        self.assertIn('f9-unlisted.expected.json', done.stderr)
        stray.unlink()
        done, _ = self.grade()
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])

    def test_self_test_refuses_before_anything_runs(self):
        (self.copy / 'mapping' / 'grade_app_path.py').write_text(
            (self.copy / 'mapping' / 'grade_app_path.py').read_text() + '\n# altered\n')
        out = self.scratch / 'selftest.json'
        done = run([self.copy / 'mapping' / 'grade_app_path.py', '--self-test', '--state-dir', self.scratch / 'st',
                    '--out', out])
        self.assertEqual(done.returncode, 2, done.stdout[-2000:])
        self.assertIn('grade_app_path.py', done.stderr)
        self.assertFalse(out.exists())
        self.assertFalse((self.scratch / 'st').exists())

    def test_replay_records_the_manifest_grader_cases_and_candidate(self):
        done, out = self.replay()
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        provenance = json.loads(out.read_text())['provenance']
        self.assertEqual(provenance['manifest_sha256'], sha256(self.copy / 'mapping' / 'EXPECTED-SHA256SUMS'))
        self.assertEqual(provenance['grader_sha256'], sha256(self.copy / 'notes' / 'offline_replay.py'))
        self.assertEqual(provenance['inputs']['cases'], sha256(self.copy / 'notes' / 'cases.json'))
        self.assertEqual(provenance['candidate']['commit'], '8e3dcfd07a5946430e7291b520faf35c8055127b')

    def test_replay_refuses_altered_cases_or_another_cases_file(self):
        cases = self.copy / 'notes' / 'cases.json'
        other = self.scratch / 'cases.json'
        shutil.copy(cases, other)
        done, out = self.replay(cases=other)
        self.assertEqual(done.returncode, 2, done.stdout[-2000:])
        self.assertFalse(out.exists())
        cases.write_text(cases.read_text().replace('"desired": "supported"', '"desired": "held"', 1))
        done, out = self.replay()
        self.assertEqual(done.returncode, 2, done.stdout[-2000:])
        self.assertIn('cases.json', done.stderr)
        self.assertFalse(out.exists())
        self.assertFalse((self.scratch / 'state').exists())


if __name__ == '__main__':
    unittest.main()
