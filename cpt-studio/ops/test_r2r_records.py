"""Repair round r2, lens records (DECISIONS D294 F1 and F4). Synthetic counts, the test database the way
ops/test_rollback_check fills it, and the tree's own source only; no Docker, no network.

F1 - whenever a record kind can be made on a test instance only by a paid or nondeterministic provider outcome (the
hold a decline sets: replay never records a hold, and no free live outcome is a decline), rollback_check's assertion 7
counts and reports it and never requires it; every other kind stays required. Every kind of SCENARIO_V2 and
SCENARIO_V3 is classified by how a test instance makes it (rollback_check.MADE_BY), and a kind the table does not
classify is required (fail-closed).

F4 - whenever an ops text states a container's stop bound, it states that role's STOP_SECONDS (the worker's 1,500 s
since AMENDMENT-2 1.12, the web's 30 s), so a moved bound leaves no stale statement. The guard reads the forms
STOP_FORMS lists (DECISIONS D297 R2RX-4: it states the forms it reads) - ``--time N``, ``stop timeout N s``, ``N s
outlasts``, ``up to N minutes``, the remaining stage time's ``up to N s``, ``the N s pass``, ``STOP_SECONDS['<role>'],
N s``, the web's graceful stop ``(graceful, N s)``, and the seconds a comment beside a stop_service_container(...,
'<role>') call names - in every ops text: install.py's and every other ops/*.py's comments, docstrings and strings, and
INSTALL.md's prose, each with its whitespace collapsed so a wrapped statement is read whole. Its completeness check
covers every bound it claims (DECISIONS D301 RBRX-2): every statement of EACH role's bound in any spelling (N s, N
seconds, --time N, N/60 minutes) must lie in a listed form, so a statement in a new form fails until its form is
listed; a stale value in a form not listed is the one statement it cannot read. A spelling of a role's bound that
states another bound sharing its literal lies in a form OTHER_BOUNDS lists (systemctl reload's 30 s client timeout and
the database's 30 s lock timeout share the web's), each of which must read a statement. The other bounds that shared
the worker's old literal (the 600 s stale-stage sweep, the drain's 600 s) are left alone.

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
NUMBER = r'(\d[\d,]*)'
# Every form a statement of a container's stop bound takes in the ops texts (the module docstring, F4): (its name, its
# pattern - the number its last group -, the seconds one unit of the number is, and how it names its role: the group
# naming it (an int), the role the form itself states (a str: a graceful stop is the web's, stopped once its requests
# are drained; the worker's stop lets its stage finish), or None). A form naming no role takes the role named nearest
# before it within ROLE_WINDOW characters, else any role's bound.
STOP_FORMS = (
    ('--time N', re.compile(rf'--time\s+{NUMBER}'), 1, None),
    ('stop timeout N s', re.compile(rf'stop timeout\W{{0,3}}{NUMBER}\s*s\b'), 1, None),
    ('N s outlasts', re.compile(rf'{NUMBER}\s*s outlasts\b'), 1, None),
    ('up to N minutes', re.compile(rf'\bup to {NUMBER} minutes\b'), 60, None),
    ('the remaining stage time, up to N s', re.compile(rf'remaining stage time\W[^.;]*?\bup to {NUMBER}\s*s\b'), 1,
     None),
    ('the N s pass', re.compile(rf'\bthe {NUMBER}\s*s pass\b'), 1, None),
    ("STOP_SECONDS['<role>'], N s", re.compile(rf"STOP_SECONDS\['(web|worker)'\],\s*{NUMBER}\s*s\b"), 1, 1),
    ('(graceful, N s)', re.compile(rf'\(graceful,\s*{NUMBER}\s*s\)'), 1, 'web'),
)
ROLE = re.compile(r'\b(worker|web)\b')
ROLE_WINDOW = 160
# The other bounds a role's bound shares its literal with in the ops texts (DECISIONS D301 RBRX-2): (its name, its
# pattern). A spelling of a role's bound inside one states that other bound, never a stop bound: the completeness check
# leaves it alone, and each must read a statement (an entry that reads nothing is stale).
OTHER_BOUNDS = (
    ("systemctl reload's client timeout, 'gives up at the N s timeout'",
     re.compile(rf'\bgives up at the {NUMBER}\s*s timeout\b')),
    ("the database's lock timeout, \"lock_timeout = 'Ns'\"", re.compile(rf"\block_timeout = '{NUMBER}s'")),
)


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


def prose(path: Path, text: str | None = None) -> str:
    """What the forms are read over: a Python file's comments (without their '#') and string tokens, in order, or a
    Markdown file's text - its whitespace collapsed, so a statement wrapped across lines or comment lines is one."""
    text = path.read_text(encoding='utf-8') if text is None else text
    if path.suffix == '.py':
        kinds = {tokenize.COMMENT, tokenize.STRING}
        if hasattr(tokenize, 'FSTRING_MIDDLE'):  # an f-string's text, tokenized apart since Python 3.12
            kinds.add(tokenize.FSTRING_MIDDLE)
        text = ' '.join(token.string.lstrip('#') for token in tokenize.generate_tokens(io.StringIO(text).readline)
                        if token.type in kinds)
    return ' '.join(text.split())


def stop_statements(text: str) -> list:
    """(form, (start, end), role or None, seconds) of every statement of a stop bound ``text`` (``prose``) holds in a
    form of STOP_FORMS."""
    found = []
    for name, pattern, unit, names in STOP_FORMS:
        for match in pattern.finditer(text):
            if isinstance(names, int):
                role = match.group(names)
            elif isinstance(names, str):
                role = names
            else:
                before = list(ROLE.finditer(text, max(0, match.start() - ROLE_WINDOW), match.start()))
                role = before[-1].group(1) if before else None
            found.append((name, match.span(), role, seconds(match.group(match.re.groups)) * unit))
    return found


def other_statements(text: str) -> list:
    """(name, (start, end)) of every statement of another bound OTHER_BOUNDS lists that ``text`` (``prose``) holds."""
    return [(name, match.span()) for name, pattern in OTHER_BOUNDS for match in pattern.finditer(text)]


def unaccounted(text: str, bound: int) -> list:
    """Every spelling of ``bound`` (``spellings``) in ``text`` (``prose``) that lies in no listed form - neither a
    statement of a stop bound (STOP_FORMS) nor one of another bound sharing the literal (OTHER_BOUNDS) - with the words
    around it."""
    spans = [span for _, span, _, _ in stop_statements(text)] + [span for _, span in other_statements(text)]
    return [text[max(0, match.start() - 40):match.end() + 10] for match in spellings(bound).finditer(text)
            if not any(start <= match.start() < end for start, end in spans)]


def spellings(bound: int) -> re.Pattern:
    """Every spelling of ``bound`` seconds a statement may take: N s or N seconds (with or without the thousands
    comma), --time N, and N/60 minutes when it is whole minutes."""
    numbers = sorted({str(bound), f'{bound:,}'}, key=len, reverse=True)
    alternatives = [rf'(?<![\d,]){re.escape(n)}\s*(?:s|seconds)\b' for n in numbers] + [rf'--time\s+{bound}\b']
    if bound % 60 == 0:
        alternatives.append(rf'(?<![\d,]){bound // 60} minutes\b')
    return re.compile('|'.join(alternatives))


def ops_texts() -> list:
    """Every ops text the guard reads: INSTALL.md and every ops/*.py that is not a test module."""
    return sorted(path for path in OPS.glob('*.py') if not path.name.startswith('test_')) + [OPS / 'INSTALL.md']


class R2RStopBoundStated(unittest.TestCase):
    """F4 (module docstring): the forms STOP_FORMS lists, in every ops text, state their role's bound, and every
    statement of each role's bound is in a listed form (DECISIONS D301 RBRX-2)."""

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

    def test_every_statement_in_a_listed_form_states_its_roles_bound(self):
        read = 0
        for path in ops_texts():
            for name, span, role, value in stop_statements(prose(path)):
                read += 1
                with self.subTest(path=path.name, form=name, at=span):
                    if role is None:
                        self.assertIn(value, set(install.STOP_SECONDS.values()))
                    else:
                        self.assertEqual(value, install.STOP_SECONDS[role])
        self.assertGreaterEqual(read, 15)  # the forms read the texts' statements (16 when the web's form was listed)

    def test_every_statement_of_each_roles_bound_is_in_a_listed_form(self):
        """DECISIONS D301 RBRX-2: the completeness check covers every bound the guard claims - each role's spellings,
        not one role's (a spelling stating another bound that shares the literal lies in a form OTHER_BOUNDS lists)."""
        for role, bound in install.STOP_SECONDS.items():
            for path in ops_texts():
                with self.subTest(role=role, path=path.name):
                    self.assertEqual(unaccounted(prose(path), bound), [],
                                     'a statement of the bound in a form STOP_FORMS does not list')

    def test_each_other_bound_reads_a_statement_and_never_a_stop_statement(self):
        """OTHER_BOUNDS states what the completeness check leaves alone: each form reads a statement in the texts, and
        none lies inside a statement of a stop bound."""
        for name, _ in OTHER_BOUNDS:
            read = 0
            for path in ops_texts():
                text = prose(path)
                stops = [span for _, span, _, _ in stop_statements(text)]
                for other, (start, end) in other_statements(text):
                    if other == name:
                        read += 1
                        with self.subTest(form=name, path=path.name, at=(start, end)):
                            self.assertFalse(any(begin < end and start < finish for begin, finish in stops))
            with self.subTest(form=name):
                self.assertGreaterEqual(read, 1, 'an OTHER_BOUNDS form that reads no statement is stale')

    def test_the_scan_refuses_a_planted_stale_statement(self):
        stale = '--' + 'time 600'  # built, so this file states no stale bound itself (the scan above reads it)
        planted = ("def park():\n"
                   f"    '''park the old worker (docker stop {stale}: its current stage finishes)'''\n"
                   "    stop_service_container(worker, 'worker')  # its current stage finishes (600 s)\n")
        self.assertEqual(stated_stop_bounds(planted), [(2, 'worker', 600), (3, 'worker', 600)])

    def test_the_other_bounds_of_600_s_are_left_alone(self):
        """The boundary: the stale-stage sweep's and the drain's 600 s are other bounds, stated as before, and no
        listed form reads them."""
        source = (OPS / 'install.py').read_text(encoding='utf-8')
        self.assertIn('STALE_RUNNING_SECONDS, 600 s', source)
        self.assertEqual(install.DRAIN_MAX_SECONDS, 600)
        said = ' '.join((OPS / 'INSTALL.md').read_text(encoding='utf-8').split())
        self.assertTrue('never longer than 600 s' in said, 'INSTALL.md no longer states the drain bound')
        self.assertEqual(install.STOP_SECONDS, {'web': 30, 'worker': 1500})
        for path in ops_texts():
            with self.subTest(path=path.name):
                self.assertNotIn(600, {value for _, _, _, value in stop_statements(prose(path))})


if __name__ == '__main__':
    unittest.main()
