"""Repair round r2b, builder records2 (DECISIONS D297 R2RX-3, R2RX-4 and records Q2). Synthetic transcripts and the
tree's own texts only; no Docker, no database, no network.

R2RX-3 - whenever the D15 judge's verdict or transcript changes, a test drives rollback_check's Check.assess on a
synthetic transcript and pins assertion 7's verdict, problems and reported evidence (d15.json's evidence and
D15-SUMMARY.txt's line) for a Fable and a non-Fable v2 candidate, and for a candidate before design v2.

R2RX-4 - whenever a guard claims every statement of a bound, it reads every form a statement takes or states the forms
it reads: ops/test_r2r_records.py's F4 guard now reads the forms its STOP_FORMS lists in every ops text, each with its
whitespace collapsed, and requires every statement of the worker's bound to lie in a listed form. Here: each listed form
read in the texts refuses a stale value planted in it (the forms the refutation's survivors used among them: INSTALL.md's
``stop timeout N s`` and install.py's ``N s outlasts``), a wrapped statement is read whole, and a statement of the
bound in a form the guard does not list fails the completeness test.

Records Q2 - whenever an ops text states what recordings the image ships, it is checked against the shipped tree: the
interpreter's replay directory (install.INTERPRETER's replay_dir, under the image's copy of cpt-studio/) holds no Fable
recording (the adapter's recording folder and suffix, read from its source), so no ops text names the Fable recording
folder as holding recordings or says replay reads "the recordings the image ships" (the two forms the texts used, the
forms this test reads), and every text describing the interpreter's replay mode states that the image ships no Fable
recording - the sentence this test fails on if the tree ever ships one.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_r2br_*.py' -v
"""
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import rollback_check as rc  # noqa: E402
import test_r2r_records as F4  # noqa: E402  (the F4 guard: STOP_FORMS, prose, stop_statements, spellings)

OPS = Path(__file__).resolve().parent
APP_ROOT = OPS.parent
ALL = rc.SCENARIO_V2 + rc.SCENARIO_V3
START = '2031-05-20T10:00:00+00:00'


def tearDownModule():
    harness2 = sys.modules.get('test_install_harness2')
    if harness2 is not None and 'connection' in harness2._DATABASE:  # test_r2r_records' database tests made it
        connection = harness2._DATABASE.pop('connection')
        connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)


def counts(kinds=ALL, **overrides) -> dict:
    """Every record kind of ``kinds`` counted once, but ``overrides``."""
    return {**{key: 1 for key, _, _ in kinds}, **overrides}


# --- R2RX-3: the D15 judge, driven on a synthetic transcript ----------------------------------------------------------

class R2BRJudgeAssertion7Tests(unittest.TestCase):
    """rollback_check.Check.assess over a synthetic d15 transcript (every other assertion's inputs are the transcript's
    own and fail or pass as they may: only assertion 7 is pinned): its verdict, problems and reported evidence, and the
    summary line D15-SUMMARY.txt prints for it."""

    def judge(self, found, *, v2: bool, fable: bool, question: bool = False) -> tuple:
        """(assertion 7's record, its D15-SUMMARY.txt lines: its verdict, its evidence and each problem printed) of
        Check.assess on a transcript whose switch-back counted ``found`` before it ran."""
        worker = {'running': True, 'restarts': 0, 'oom_killed': False}
        check = rc.Check.__new__(rc.Check)
        check.record = {
            'started_at': START,
            'switch_back': {'scenario_v2': found, 'note': None, 'independent': {}, 'refusals': {}, 'closed_stages': [],
                            'unrunnable_after_close': {'stuck': 0}, 'update': {}},
            'http': {'health': 200, 'statuses': {'200': 1}}, 'comparison': {'encounters': 1, 'findings': []},
            'recompute': {}, 'renders': {},
            'worker': {'after_20s': worker, 'at_end': worker, 'open_at_start': {}, 'interpret_jobs_at_start': [],
                       'reading_jobs_at_start': [], 'started_at': START}}
        check.instance = SimpleNamespace(calls=[])
        check.views, check.declared, check.v2, check.fable = {}, None, v2, fable
        check.question = question  # round r3: a candidate whose installer knows the question stage (question_candidate)
        check.candidate = {'tag': 'cpt-studio:candidate', 'revision': 'c' * 40}
        check.previous = {'tag': 'cpt-studio:previous', 'revision': 'p' * 40}
        check.args = SimpleNamespace(db='test_r2br_synthetic')
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            check.out = Path(folder)
            check.assess()
            summary = (check.out / 'D15-SUMMARY.txt').read_text(encoding='utf-8').splitlines()
        seventh = [item for item in check.record['assertions'] if item['assertion'] == 7]
        self.assertEqual(len(seventh), 1)
        at = next(index for index, line in enumerate(summary) if line.startswith('  7. '))
        end = next(index for index, line in enumerate(summary) if line.startswith('  8. '))
        return seventh[0], summary[at:end]

    def assertSeventh(self, found, *, v2, fable, result, problems, reported, question=False):
        seventh, lines = self.judge(found, v2=v2, fable=fable, question=question)
        self.assertEqual((seventh['result'], seventh['problems']), (result, problems))
        self.assertEqual(seventh['evidence']['reported_not_required'], reported)
        self.assertEqual((seventh['evidence']['v2_candidate'], seventh['evidence']['fable_candidate'],
                          seventh['evidence']['question_candidate'], seventh['evidence']['scenario_v2']),
                         (v2, fable, question, found))
        self.assertTrue(lines[0].startswith(f'  7. {result}  '), lines[0])
        self.assertEqual(lines[1], f'       evidence: v2 candidate {v2}; Fable candidate {fable}; question candidate '
                                   f'{question}; record kinds {found}; reported, never required: {reported}')
        self.assertEqual(lines[2:], [f'       - {problem}' for problem in problems])
        return seventh, lines

    def test_a_fable_candidate_without_a_declined_hold_passes_and_reports_it(self):
        self.assertSeventh(counts(declined_hold=0), v2=True, fable=True, result='PASS', problems=[],
                           reported={'declined_hold': 0})

    def test_a_fable_candidate_is_judged_on_its_new_versions_kinds(self):
        """The candidate's Fable kinds are required: a run without the Fable inventory fails assertion 7, and the
        declined hold is still reported."""
        problem = f'fable_inventory: the run holds no an event inventory of {rc.PAIR_V3} and {rc.INVENTORY_V3}'
        seventh, lines = self.assertSeventh(counts(declined_hold=0, fable_inventory=0), v2=True, fable=True,
                                            result='FAIL', problems=[problem], reported={'declined_hold': 0})
        self.assertEqual(lines[2:], [f'       - {problem}'])  # each problem is printed under the evidence

    def test_a_question_candidate_is_judged_on_the_question_stages_kinds(self):
        """Round r3: a candidate with the question stage requires its records - a run without an answer-released code
        fails assertion 7 naming it - and the same counts pass a candidate without the stage (the boundary)."""
        found = counts(rc.SCENARIO_V2 + rc.SCENARIO_V3 + rc.SCENARIO_R3, declined_hold=0, question_released=0)
        problem = 'question_released: the run holds no a code an established answer released'
        self.assertSeventh(found, v2=True, fable=True, question=True, result='FAIL', problems=[problem],
                           reported={'declined_hold': 0})
        self.assertSeventh(found, v2=True, fable=True, question=False, result='PASS', problems=[],
                           reported={'declined_hold': 0})
        self.assertSeventh(counts(rc.SCENARIO_V2 + rc.SCENARIO_V3 + rc.SCENARIO_R3, declined_hold=0), v2=True,
                           fable=True, question=True, result='PASS', problems=[], reported={'declined_hold': 0})

    def test_an_uncounted_declined_hold_is_reported_as_not_counted(self):
        self.assertSeventh(counts(declined_hold='RuntimeError: psql failed'), v2=True, fable=True, result='PASS',
                           problems=[], reported={'declined_hold': "not counted ('RuntimeError: psql failed')"})

    def test_a_v2_candidate_that_is_not_fables_is_judged_on_6_4s_kinds_alone(self):
        """The boundary: no SCENARIO_V3 kind is required or reported for it - the Fable kinds at 0 change nothing - and
        a missing 6.4 kind fails it."""
        none_of_v3 = counts(**{key: 0 for key, _, _ in rc.SCENARIO_V3})
        self.assertSeventh(none_of_v3, v2=True, fable=False, result='PASS', problems=[], reported={})
        missing = counts(rc.SCENARIO_V2, held_code=0)
        title = dict((key, title) for key, title, _ in rc.SCENARIO_V2)['held_code']
        self.assertSeventh(missing, v2=True, fable=False, result='FAIL', problems=[f'held_code: the run holds no {title}'],
                           reported={})

    def test_a_candidate_before_design_v2_is_not_judged_on_record_kinds(self):
        self.assertSeventh({}, v2=False, fable=False, result='PASS', problems=[], reported={})
        self.assertSeventh(None, v2=False, fable=True, result='PASS', problems=[], reported={})


# --- R2RX-4: every form a statement of the stop bound takes --------------------------------------------------------

def planted(path: Path, old: str, new: str) -> str:
    """``path``'s text with ``old`` (which must occur once) replaced by ``new`` - a stale statement, in memory."""
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise AssertionError(f'{path.name}: the planted statement\'s anchor occurs {text.count(old)} times')
    return text.replace(old, new)


def stale(path: Path, text: str) -> list:
    """The statements of a stop bound in ``text`` (read as ``path``'s, F4.prose) that do not state their role's bound
    (any role's, for a statement that names none)."""
    out = []
    for name, span, role, value in F4.stop_statements(F4.prose(path, text)):
        right = (value in install.STOP_SECONDS.values()) if role is None else value == install.STOP_SECONDS[role]
        if not right:
            out.append((name, role, value))
    return out


def unlisted(path: Path, text: str) -> list:
    """Every statement of the worker's bound ``text`` holds outside a listed form."""
    flat = F4.prose(path, text)
    spans = [span for _, span, _, _ in F4.stop_statements(flat)]
    return [match.group(0) for match in F4.spellings(install.STOP_SECONDS['worker']).finditer(flat)
            if not any(start <= match.start() < end for start, end in spans)]


class R2BRStopBoundFormsTests(unittest.TestCase):
    """The F4 guard reads every form it lists, in every ops text, whole when wrapped; a stale value planted in any of
    them is refused, and a statement of the bound in a form it does not list fails its completeness test."""
    INSTALL_MD, INSTALL_PY = OPS / 'INSTALL.md', OPS / 'install.py'
    OLD = 1500  # the worker's bound before round r3 (600 before AMENDMENT-2 1.12): the stale value a missed one keeps

    def test_the_guard_reads_the_texts_as_they_stand(self):
        for path in F4.ops_texts():
            with self.subTest(path=path.name):
                text = path.read_text(encoding='utf-8')
                self.assertEqual(stale(path, text), [])
                self.assertEqual(unlisted(path, text), [])
        read = {name for path in F4.ops_texts() for name, _, _, _ in F4.stop_statements(F4.prose(path))}
        self.assertEqual(read, {name for name, _, _, _ in F4.STOP_FORMS})  # every listed form reads a statement

    def test_a_stale_value_in_every_listed_form_is_refused(self):
        old = self.OLD
        plants = (
            # (the text, its statement as it stands, the same statement stale)
            (self.INSTALL_MD, 'read-only root, stop timeout 1,800 s', f'read-only root, stop timeout {old} s'),
            (self.INSTALL_PY, 'So 1,800 s outlasts', f'So {old} s outlasts'),
            (self.INSTALL_PY, 'may so wait up to 30 minutes', f'may so wait up to {old // 60} minutes'),
            (self.INSTALL_MD, "The worker's stop timeout (1,800 s", f"The worker's stop timeout ({old} s"),
            (self.INSTALL_MD, 'can take\n  up to 30 minutes', f'can take\n  up to {old // 60} minutes'),
            (self.INSTALL_MD, 'about a second when idle, up to 1,800 s', f'about a second when idle, up to {old} s'),
            (self.INSTALL_MD, 'when the 1,800 s pass', f'when the {old} s pass'),
            (self.INSTALL_MD, '`docker\n  stop --time 1800`', f'`docker\n  stop --time {old}`'),
            (self.INSTALL_PY, "(STOP_SECONDS['worker'], 1,800 s)", f"(STOP_SECONDS['worker'], {old} s)"),
        )
        for path, now, then in plants:
            with self.subTest(path=path.name, statement=then):
                self.assertEqual(stale(path, path.read_text(encoding='utf-8')), [])
                self.assertTrue(stale(path, planted(path, now, then)), 'the guard did not read the stale statement')

    def test_a_wrapped_statement_is_read_whole(self):
        """INSTALL.md's '(up to' and '1,800 s; ...' stand on two lines: the guard reads them as one statement."""
        text = self.INSTALL_MD.read_text(encoding='utf-8')
        self.assertTrue(re.search(r'\(up to\n\s+1,800 s;', text), 'the wrapped statement this test reads moved')
        self.assertTrue(stale(self.INSTALL_MD, re.sub(r'\(up to\n(\s+)1,800 s;', rf'(up to\n\g<1>{self.OLD} s;', text,
                                                      count=1)))

    def test_a_statement_of_the_bound_in_a_form_the_guard_does_not_list_fails_its_completeness_test(self):
        text = planted(self.INSTALL_MD, 'stop timeout 1,800 s', 'stop timeout 1,800 s (the worker is given 1,800 '
                                                                'seconds to finish its stage)')
        self.assertEqual(unlisted(self.INSTALL_MD, text), ['1,800 seconds'])
        self.assertEqual(stale(self.INSTALL_MD, text), [])  # its value is right: only the completeness test reads it

    def test_the_other_bounds_are_never_read_as_a_stop_bound(self):
        """The boundary: the drain's 'up to 600 s', the 600 s stale-stage sweep, the reading stages' 1,440 s, 1,560 s
        and 1,380 s and the question stage's 1,588 s and 1,768 s are no statements of a stop bound - every value a listed form reads is a role's bound (the web's 30 s
        too, since D301 RBRX-2 listed its form)."""
        for path in (self.INSTALL_MD, self.INSTALL_PY):
            with self.subTest(path=path.name):
                values = {value for _, _, _, value in F4.stop_statements(F4.prose(path))}
                self.assertEqual(values, {install.STOP_SECONDS['worker'], install.STOP_SECONDS['web']})


# --- records Q2: the recordings the image ships ------------------------------------------------------------------------

def module_literal(path: str, name: str):
    """A module-level literal of a tree file, read from its source (no import)."""
    import ast
    tree = ast.parse((APP_ROOT / path).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(target, 'id', None) == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise LookupError(name)


def shipped_fable_recordings() -> list:
    """The Fable recordings the image ships: each file of the interpreter's recording folder (fable_adapter's
    recording_folder - its provider's name, PROVIDER_V3 - with its recording_suffix) under the replay directory
    install.INTERPRETER names, read in the tree the image copies to /app (deploy/.dockerignore keeps tests/)."""
    adapter = (APP_ROOT / 'studio' / 'interpretation' / 'fable_adapter.py').read_text(encoding='utf-8')
    if "    recording_folder = NAME\n    recording_suffix = '.sse'\n" not in adapter or \
            'NAME = interpretation.PROVIDER_V3' not in adapter:
        raise AssertionError('the Fable adapter reads its recordings elsewhere: read its folder and suffix again')
    replay_dir = APP_ROOT / PurePosixPath(install.INTERPRETER['replay_dir']).relative_to('/app')
    folder = replay_dir / module_literal('studio/interpretation/__init__.py', 'PROVIDER_V3')
    return sorted(str(path.relative_to(APP_ROOT)) for path in folder.rglob('*.sse')) if folder.is_dir() else []


def texts() -> dict:
    """The ops texts that state what replay reads (install.py's comments, docstrings and strings; INSTALL.md), each
    with its whitespace collapsed (F4.prose)."""
    return {path.name: F4.prose(path) for path in (OPS / 'install.py', OPS / 'INSTALL.md')}


# The forms a statement that the image ships the interpreter's recordings takes in these texts (the two the texts used;
# the forms this test reads), and the sentence every text describing replay mode states while the image ships none.
SHIPS_FORMS = (re.compile(r'\brecordings the image ships\b'), re.compile(r'\banthropic/ holds\b'))
SHIPS_NONE = 'ships no Fable recording'


class R2BRShippedRecordingsTests(unittest.TestCase):
    """Records Q2: what install.py and INSTALL.md say the image ships for replay is what the shipped tree holds."""

    def test_the_image_ships_no_fable_recording(self):
        self.assertEqual(shipped_fable_recordings(), [])
        # the replay directory itself ships (tests/ stays in the image), holding the v1 FRESH recordings (gemini/)
        replay_dir = APP_ROOT / PurePosixPath(install.INTERPRETER['replay_dir']).relative_to('/app')
        self.assertTrue((replay_dir / 'gemini').is_dir())

    def test_no_ops_text_names_a_fable_recording_the_image_does_not_ship(self):
        shipped = shipped_fable_recordings()
        for name, text in texts().items():
            for form in SHIPS_FORMS:
                with self.subTest(text=name, form=form.pattern):
                    if not shipped:
                        self.assertEqual(form.findall(text), [], f'{name} says the image ships Fable recordings')

    def test_every_text_describing_replay_mode_states_what_the_image_ships(self):
        """install.py's INTERPRETER comment, its --interpreter-mode help and runtime_env's docstring, and INSTALL.md's
        app row each state it - and none may once the tree ships a Fable recording."""
        shipped = shipped_fable_recordings()
        found = {name: text.count(SHIPS_NONE) for name, text in texts().items()}
        self.assertEqual(found, {'install.py': 0, 'INSTALL.md': 0} if shipped else {'install.py': 3, 'INSTALL.md': 1})
        help_text = next(action.help for action in install_parser()._actions if '--interpreter-mode' in
                         action.option_strings)
        self.assertIn(SHIPS_NONE, help_text)
        self.assertIn(SHIPS_NONE, ' '.join(install.runtime_env.__doc__.split()))

    def test_the_forms_this_test_reads_find_the_statements_it_was_written_for(self):
        """The control: each form finds the statement the earlier texts made (so a zero above is a reading)."""
        before = {'install.py': 'Replay reads the recordings the image ships (tests/fixtures/interpretation/: '
                                'anthropic/ holds Fable\'s, gemini/ Gemini\'s; kept in the image by deploy/.dockerignore)',
                  'INSTALL.md': '`replay` - the recordings the image ships, nothing sent - or `disabled`'}
        self.assertTrue(SHIPS_FORMS[0].search(before['install.py']) and SHIPS_FORMS[1].search(before['install.py']))
        self.assertTrue(SHIPS_FORMS[0].search(before['INSTALL.md']))


def install_parser():
    """install.py's argument parser, as its parse_args builds it, captured before it parses anything."""
    import argparse
    captured = {}

    def capture(self, *args, **kwargs):
        captured['parser'] = self
        raise SystemExit(0)
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', capture), contextlib.suppress(SystemExit):
        install.parse_args([])
    return captured['parser']


if __name__ == '__main__':
    unittest.main()
