"""Repair round r2d, builder records3 (DECISIONS D301 RBRX-2). The tree's own ops texts and in-memory plants only; no
Docker, no database, no network.

RBRX-2 - whenever a guard claims every statement of a set of bounds, its completeness check covers every bound it
claims: ops/test_r2r_records.py's F4 guard claims each role's stop bound (STOP_SECONDS: the web's and the worker's), so
it reads the web's statements - ``(graceful, N s)``, the form install.py and INSTALL.md state the web's stop in, which
STOP_FORMS now lists as the web's - and every spelling of EACH role's bound must lie in a listed form (one stating
another bound that shares a role's literal lies in a form OTHER_BOUNDS lists), not the worker's alone. Here, through the
guard's own tests run with the bound moved in memory (as a mover moves it, the texts left as they stand) or with a
statement planted in a text: the web's statements are read as the web's; a moved web bound - the r2b refutation's input
- fails the guard on each stale statement; a stale value in the web's form is refused; a statement of the web's bound in
a form the guard does not list fails its completeness test; and the other bounds sharing the web's literal, and the
worker's reading, are left alone.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_r2dr_*.py' -v
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_r2r_records as F4  # noqa: E402  (the F4 guard)

OPS = Path(__file__).resolve().parent
INSTALL_MD, INSTALL_PY = OPS / 'INSTALL.md', OPS / 'install.py'
WEB_FORM = '(graceful, N s)'
GRACEFUL = '(graceful, 30 s)'  # the web's stop as the texts state it: install.py twice, INSTALL.md once
# the other bounds that share the web's literal in the texts (systemctl reload's client timeout; the lock timeout)
OTHERS = ('gives up at the 30 s timeout', "lock_timeout = '30s'")
STATEMENT_TEST = 'test_every_statement_in_a_listed_form_states_its_roles_bound'


def guard(method: str, **moved) -> unittest.TestResult:
    """The result of the F4 guard's test ``method`` with STOP_SECONDS moved in memory (``moved``: role -> seconds) - as a
    mover moves the bound, the texts left as they stand."""
    result = unittest.TestResult()
    with mock.patch.dict(install.STOP_SECONDS, moved):
        F4.R2RStopBoundStated(method).run(result)
    return result


def failing(result: unittest.TestResult) -> list:
    """The parameters of each failing (sub)test of ``result``, in order."""
    return [dict(getattr(test, 'params', {})) for test, _ in result.failures + result.errors]


def completeness_methods() -> list:
    """The F4 guard's completeness tests: its methods requiring every statement of a bound to lie in a listed form."""
    return [name for name in dir(F4.R2RStopBoundStated)
            if name.startswith('test_every_statement_of_') and name.endswith('_is_in_a_listed_form')]


def planted(path: Path, old: str, new: str) -> str:
    """``path``'s text with ``old`` (which must occur once) replaced by ``new``, in memory."""
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise AssertionError(f'{path.name}: the planted statement\'s anchor occurs {text.count(old)} times')
    return text.replace(old, new)


def reading(texts: dict):
    """F4.prose reading ``texts`` (path -> text) for those paths, and the files for every other path."""
    real = F4.prose

    def prose(path, text=None):
        return real(path, texts[path] if text is None and path in texts else text)
    return mock.patch.object(F4, 'prose', prose)


def stale(text: str) -> list:
    """(form, role, seconds) of every statement in a listed form ``text`` (F4.prose) holds that does not state its role's
    bound (any role's, for a statement naming none)."""
    return [(name, role, value) for name, _, role, value in F4.stop_statements(text)
            if (value not in install.STOP_SECONDS.values() if role is None else value != install.STOP_SECONDS[role])]


class R2DRStopBoundEveryRoleTests(unittest.TestCase):
    """DECISIONS D301 RBRX-2 (module docstring): the F4 guard reads and completes every role's stop bound."""

    def test_the_guard_reads_the_webs_statements_as_the_webs(self):
        read = {path.name: [(name, role, value) for name, _, role, value in F4.stop_statements(F4.prose(path))
                            if role == 'web'] for path in F4.ops_texts()}
        self.assertEqual({name: found for name, found in read.items() if found},
                         {'install.py': [(WEB_FORM, 'web', 30)] * 2, 'INSTALL.md': [(WEB_FORM, 'web', 30)]})
        for path in (INSTALL_PY, INSTALL_MD):  # every graceful stop the texts state is one the guard reads
            with self.subTest(path=path.name):
                self.assertEqual(F4.prose(path).count(GRACEFUL), len(read[path.name]))

    def test_a_moved_web_bound_fails_the_guard_on_each_stale_statement(self):
        """The r2b refutation's input: STOP_SECONDS['web'] moved (30 -> 45), the three statements left - the guard's
        statement test fails on exactly those three (before RBRX-2 it read none of them and passed)."""
        result = guard(STATEMENT_TEST, web=45)
        self.assertFalse(result.wasSuccessful(), 'the guard passed with three stale statements of the web\'s bound')
        self.assertEqual(sorted((item.get('path'), item.get('form')) for item in failing(result)),
                         sorted([('INSTALL.md', WEB_FORM)] + [('install.py', WEB_FORM)] * 2))
        with mock.patch.dict(install.STOP_SECONDS, {'web': 45}):
            for path, count in ((INSTALL_PY, 2), (INSTALL_MD, 1)):
                with self.subTest(path=path.name):
                    self.assertEqual(stale(F4.prose(path)), [(WEB_FORM, 'web', 30)] * count)
        self.assertTrue(guard(STATEMENT_TEST).wasSuccessful())  # the control: the bound where the texts state it

    def test_a_stale_value_in_the_webs_form_is_refused(self):
        for path, old in ((INSTALL_PY, 'stop it (graceful, 30 s)'), (INSTALL_PY, 'Stop INCOMING_WEB (graceful, 30 s)'),
                          (INSTALL_MD, 'then stopped (graceful, 30 s)')):
            with self.subTest(path=path.name, statement=old):
                self.assertEqual(stale(F4.prose(path)), [])
                self.assertEqual(stale(F4.prose(path, planted(path, old, old.replace('30 s', '60 s')))),
                                 [(WEB_FORM, 'web', 60)])

    def test_a_statement_of_the_webs_bound_in_an_unlisted_form_fails_the_completeness_check(self):
        """A statement of the web's 30 s in a form STOP_FORMS does not list: the guard's completeness test fails on it -
        before RBRX-2 its completeness test read the worker's bound alone and passed."""
        text = planted(INSTALL_MD, 'then stopped (graceful, 30 s), parked as',
                       'then stopped (graceful, 30 s) - the web is given 30 seconds to finish its requests -, parked as')
        methods = completeness_methods()
        self.assertTrue(methods)
        with reading({INSTALL_MD: text}):
            results = {name: guard(name) for name in methods}
        self.assertFalse(all(result.wasSuccessful() for result in results.values()),
                         'no completeness test of the guard reads the web\'s bound')
        found = [item for result in results.values() for item in failing(result)]
        self.assertEqual([(item.get('role'), item.get('path')) for item in found], [('web', 'INSTALL.md')])
        self.assertEqual(stale(F4.prose(INSTALL_MD, text)), [])  # its value is right: only completeness reads it
        self.assertTrue(all(guard(name).wasSuccessful() for name in methods))  # the texts as they stand pass

    def test_the_other_bounds_sharing_the_webs_literal_are_left_alone(self):
        """The boundary: systemctl reload's '30 s timeout' and the database's lock_timeout '30s' state other bounds - no
        listed form reads them, a moved web bound never makes them stale, and every completeness test passes on the
        texts that state them."""
        for path in (INSTALL_PY, INSTALL_MD):
            text = F4.prose(path)
            for other in OTHERS:
                at = text.find(other)
                if at < 0:
                    continue
                with self.subTest(path=path.name, other=other):
                    self.assertFalse(any(start < at + len(other) and at < end
                                         for _, (start, end), _, _ in F4.stop_statements(text)))
        # 4 since refutation round 1 (rollback-0): END_EVERY_SESSION's lock_timeout '30s' beside LICENSE_NOTE_FIX's
        self.assertEqual(sum(F4.prose(path).count(other) for path in (INSTALL_PY, INSTALL_MD) for other in OTHERS), 4)
        result = guard(STATEMENT_TEST, web=45)
        self.assertTrue(all(item.get('form') == WEB_FORM for item in failing(result)))
        for name in completeness_methods():
            with self.subTest(method=name):
                self.assertTrue(guard(name).wasSuccessful())

    def test_the_workers_reading_is_left_alone(self):
        """The boundary (the r2b refutation's control): moving the worker's bound still fails the guard on the worker's
        statements, and no statement of the web's form is read as the worker's."""
        result = guard(STATEMENT_TEST, worker=3900)  # the Fable coding build: the bound is 3,600 s, so the move is to 3,900 s
        self.assertFalse(result.wasSuccessful())
        self.assertGreaterEqual(len(failing(result)), 12)
        self.assertNotIn(WEB_FORM, {item.get('form') for item in failing(result)})
        with mock.patch.dict(install.STOP_SECONDS, {'worker': 3900}):
            self.assertNotIn('web', {role for path in F4.ops_texts() for _, role, _ in stale(F4.prose(path))})


if __name__ == '__main__':
    unittest.main()
