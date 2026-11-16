"""Repair round r2, lens records (DECISIONS D294 F1 and F4). Synthetic counts, the test database the way
ops/test_rollback_check fills it, and the tree's own source only; no Docker, no network.

F1 - whenever a record kind can be made on a test instance only by a paid or nondeterministic provider outcome (the
hold a decline sets: replay never records a hold, and no free live outcome is a decline), rollback_check's assertion 7
counts and reports it and never requires it; every other kind stays required. Every kind of SCENARIO_V2 and
SCENARIO_V3 is classified by how a test instance makes it (rollback_check.MADE_BY), and a kind the table does not
classify is required (fail-closed).

F4 - whenever install.py's comments and docstrings state a container's stop bound (a ``docker stop --time N``, or the
seconds a comment beside a stop_service_container call names), they state that role's STOP_SECONDS (the worker's 1,500 s
since AMENDMENT-2 1.12), so a moved bound leaves no stale statement; INSTALL.md is read the same way. The other bounds
that shared the old literal (the 600 s stale-stage sweep, the drain's 600 s) are left alone.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_r2r_*.py' -v
"""
import io
import re
import sys
import tokenize
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import rollback_check as rc  # noqa: E402
import test_install_interpreter as TI  # noqa: E402  (helpers: FableRows' D15 database)

OPS = Path(__file__).resolve().parent
ALL = rc.SCENARIO_V2 + rc.SCENARIO_V3


def tearDownModule():
    harness2 = sys.modules.get('test_install_harness2')
    if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
        connection = harness2._DATABASE.pop('connection')
        connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)


def counts(**overrides) -> dict:
    """Every record kind counted once, but ``overrides``."""
    return {**{key: 1 for key, _, _ in ALL}, **overrides}


# --- F1 --------------------------------------------------------------------------------------------------------------

class R2RAssertion7Reported(unittest.TestCase):
    def test_every_record_kind_is_classified_by_how_a_test_instance_makes_it(self):
        self.assertEqual(set(rc.MADE_BY), {key for key, _, _ in ALL})  # a new kind arrives classified or this fails
        self.assertLessEqual(set(rc.MADE_BY.values()), {rc.MADE_ON_TEST, rc.MADE_BY_PROVIDER_OUTCOME})
        self.assertEqual([key for key, _, _ in ALL if not rc.required(key)], ['declined_hold'])
        self.assertTrue(rc.required('a_kind_no_table_classifies'))  # fail-closed

    def test_a_fable_candidates_run_without_a_declined_hold_passes_assertion_7_and_reports_it(self):
        """The rule changes this: a D15 database made through replay and free live outcomes holds no declined hold."""
        self.assertEqual(rc.assertion_7(counts(declined_hold=0), True, True), ([], {'declined_hold': 0}))
        self.assertEqual(rc.scenario_problems(counts(declined_hold=0), ALL), [])
        for found in (3, 'RuntimeError: psql failed', None):  # counted and reported whatever it counts, never a problem
            with self.subTest(found=found):
                problems, reported = rc.assertion_7(counts(declined_hold=found), True, True)
                self.assertEqual(problems, [])
                self.assertEqual(reported, {'declined_hold': found if type(found) is int else
                                            f'not counted ({found!r})'})

    def test_every_kind_a_test_instance_makes_stays_required(self):
        """The boundary the rule leaves alone (scenario_problems, as before the repair): each other kind of 6.4 and 8.5
        - an interpreter hold of any reason (a refused key's free 401 makes one), the Fable inventory, assessment and
        run included - is a problem at 0 or uncounted, and 6.4's kinds alone judge a v2 candidate that is not Fable's."""
        for key, title, _ in ALL:
            if key == 'declined_hold':
                continue
            for found in (0, 'RuntimeError: psql failed'):
                with self.subTest(key=key, found=found):
                    expected = (f'{key}: the run holds no {title}' if found == 0
                                else f'{key}: not counted ({found!r})')
                    self.assertEqual(rc.scenario_problems(counts(**{key: found}), ALL), [expected])
        self.assertEqual(rc.scenario_problems(counts(declined_hold=0)), [])
        self.assertEqual(rc.scenario_problems(counts(interpreter_hold=0)),
                         ['interpreter_hold: the run holds no an interpreter hold'])

    def test_assertion_7_reports_what_it_never_requires_and_judges_each_candidate_by_its_kinds(self):
        for key, title, _ in ALL:
            if key != 'declined_hold':
                with self.subTest(key=key):
                    self.assertEqual(rc.assertion_7(counts(**{key: 0}), True, True),
                                     ([f'{key}: the run holds no {title}'], {'declined_hold': 1}))
        # a v2 candidate that is not Fable's is judged on 6.4's kinds alone; a candidate before design v2 on none
        self.assertEqual(rc.assertion_7(counts(declined_hold=0), True, False), ([], {}))
        self.assertEqual(rc.assertion_7({}, False, True), ([], {}))


class R2RAssertion7OnAReplayFilledDatabase(TI.FableRows):
    """F1 on real rows: a database the Fable candidate filled with every record kind, its interpreter hold the one a
    free live outcome makes (a refused key: reason auth, HTTP 401) and no declined hold - the database a D15 run in
    replay mode can make. Assertion 7 passes on it and reports the declined hold's 0."""

    def counts(self) -> dict:
        from django.db import connection
        found = {}
        with connection.cursor() as cursor:
            for key, _, statement in ALL:
                cursor.execute(statement)
                found[key] = cursor.fetchone()[0]
        return found

    def test_assertion_7_passes_without_a_declined_hold_and_reports_it(self):
        from studio import models
        real = models.InterpreterHold.objects.create

        def refused_key(**fields):  # the free live outcome's hold, never a decline
            return real(**{**fields, 'reason': models.InterpreterHold.AUTH, 'http_status': 401,
                           'vendor_status': 'authentication_error'})
        with mock.patch.object(models.InterpreterHold.objects, 'create', side_effect=refused_key):
            self.fill_d15()
        self.assertEqual(list(models.InterpreterHold.objects.values_list('reason', flat=True)), ['auth'])
        found = self.counts()
        self.assertEqual((found['interpreter_hold'], found['declined_hold']), (1, 0))
        self.assertEqual(rc.assertion_7(found, True, True), ([], {'declined_hold': 0}))

    def test_a_kind_a_test_instance_makes_still_fails_on_real_rows(self):
        """The boundary: the same database with no Fable run of the adapter's version counts fable_run 0 - a failure."""
        from studio import interpretation, models
        self.fill_d15()
        models.ProviderRun.objects.filter(adapter_version=interpretation.ADAPTER_VERSION_V3).update(
            adapter_version='anthropic-messages@other')
        found = self.counts()
        self.assertEqual(found['fable_run'], 0)
        self.assertEqual(rc.scenario_problems(found, ALL),
                         [f'fable_run: the run holds no an interpreter run of {rc.ADAPTER_V3}'])


# --- F4 --------------------------------------------------------------------------------------------------------------

TIME = re.compile(r'--time\s+(\d[\d,]*)')
SECONDS = re.compile(r'(\d[\d,]*)\s*s\b')
STOP_CALL = re.compile(r"stop_service_container\([^)]*'(web|worker)'\)")


def seconds(text: str) -> int:
    return int(text.replace(',', ''))


def stated_stop_bounds(source: str) -> list:
    """(line, role or None, seconds) of every statement of a container's stop bound in a Python source's comments and
    string tokens: each ``--time N`` (the role the same line names, 'worker' before 'web'), and each ``N s`` a comment
    beside a stop_service_container(..., '<role>') call states."""
    found = []
    lines = source.splitlines()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        for offset, line in enumerate(token.string.splitlines()):
            number = token.start[0] + offset
            for match in TIME.finditer(line):
                role = 'worker' if 'worker' in line else 'web' if 'web' in line else None
                found.append((number, role, seconds(match.group(1))))
            if token.type == tokenize.COMMENT:
                call = STOP_CALL.search(lines[number - 1])
                if call:
                    found += [(number, call.group(1), seconds(match.group(1))) for match in SECONDS.finditer(line)]
    return found


class R2RStopBoundStated(unittest.TestCase):
    def test_every_stated_stop_bound_in_the_installer_is_its_roles(self):
        found = stated_stop_bounds((OPS / 'install.py').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len([item for item in found if item[1] == 'worker']), 3)  # the scan reads something
        for number, role, value in found:
            with self.subTest(line=number):
                self.assertIn(role, install.STOP_SECONDS, f'install.py:{number} states a stop bound of no role')
                self.assertEqual(value, install.STOP_SECONDS[role], f'install.py:{number}')

    def test_every_stated_docker_stop_in_the_ops_texts_is_a_stop_bound(self):
        for path in sorted(OPS.glob('*.py')) + [OPS / 'INSTALL.md']:
            text = path.read_text(encoding='utf-8')
            for number, line in enumerate(text.splitlines(), 1):
                for match in TIME.finditer(line):
                    with self.subTest(path=path.name, line=number):
                        self.assertIn(seconds(match.group(1)), set(install.STOP_SECONDS.values()))

    def test_the_scan_refuses_a_planted_stale_statement(self):
        stale = '--' + 'time 600'  # built, so this file states no stale bound itself (the scan above reads it)
        planted = ("def park():\n"
                   f"    '''park the old worker (docker stop {stale}: its current stage finishes)'''\n"
                   "    stop_service_container(worker, 'worker')  # its current stage finishes (600 s)\n")
        self.assertEqual(stated_stop_bounds(planted), [(2, 'worker', 600), (3, 'worker', 600)])

    def test_the_other_bounds_of_600_s_are_left_alone(self):
        """The boundary: the stale-stage sweep's and the drain's 600 s are other bounds, stated as before."""
        source = (OPS / 'install.py').read_text(encoding='utf-8')
        self.assertIn('STALE_RUNNING_SECONDS, 600 s', source)
        self.assertEqual(install.DRAIN_MAX_SECONDS, 600)
        said = ' '.join((OPS / 'INSTALL.md').read_text(encoding='utf-8').split())
        self.assertTrue('never longer than 600 s' in said, 'INSTALL.md no longer states the drain bound')
        self.assertEqual(install.STOP_SECONDS, {'web': 30, 'worker': 1500})


if __name__ == '__main__':
    unittest.main()
