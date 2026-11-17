"""Repair round r2e, builder e-tools-records (DECISIONS D303: records3's RDRX-2). The tree's own ops texts and in-memory
plants only; no Docker, no database, no network.

RDRX-2 - whenever a guard claims completeness over every statement of a bound, its spelling set is derived from every
syntax that states that bound: ops/test_r2r_records.py's F4 guard claims every statement of each role's stop bound
(STOP_SECONDS), so its completeness check (``unaccounted`` over ``spellings``) reads the flags its own setter and stopper
pass the bound with - read from install.py's source (``setter_flags``: docker run's --stop-timeout, docker stop's
--time) - with docker's other spellings of them (-t, --timeout; '--flag N', '--flag=N'), and the number in every unit
(seconds, the minutes and hours it is whole in, milliseconds), spaced, hyphenated (a compound adjective) or joined.
Where D301's set read N s, N seconds, --time N and N/60 minutes alone, a statement of a role's CURRENT bound in any other
form was invisible to the guard (the r2d refutation: 15 plants, 15 green; with the bound moved as a mover moves it, the
guard's failures were the same multiset with the plant as without it). Here, through the guard's own tests run with a
statement planted in a text (ops/test_r2dr_records3.py's harness): each syntax, for each role, fails the completeness
check naming the plant's role and text; the texts as they stand pass; a number that is not a bound, and the other bounds
OTHER_BOUNDS lists, are left alone; and a flag the installer starts passing the bound with is read without being listed
by hand.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_r2et_*.py' -v
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_r2dr_records3 as H  # noqa: E402  (the guard harness: guard, failing, planted, reading)
import test_r2r_records as F4  # noqa: E402  (the F4 guard)

OPS = Path(__file__).resolve().parent
INSTALL_MD, INSTALL_PY = OPS / 'INSTALL.md', OPS / 'install.py'
MD_ANCHOR = 'then stopped (graceful, 30 s), parked as'
PY_ANCHOR = 'anyway, so waiting longer buys nothing.'
# every syntax a statement of each role's current bound may take that D301's spelling set did not read (the r2d
# refutation's plants first): the setter's and stopper's flags and their docker spellings, and the unit forms
PLANTS = {
    'worker': ('the worker container is created with docker run --stop-timeout 1500',
               'docker run --stop-timeout=1500', 'the worker is stopped with docker stop -t 1500', 'docker stop -t1500',
               'docker stop --time=1500', 'docker compose stop --timeout 1500', 'the worker is given a 25-minute stop',
               'a stop of 25 min', 'a stop of 25 mins', 'a 1,500-second stop', 'a stop of 1500 secs',
               'a stop of 1500 sec', 'a stop of 1,500,000 ms', 'a 1500-seconds stop'),
    'web': ('the web container is created with docker run --stop-timeout 30', 'the web is stopped with docker stop -t 30',
            'the web is stopped with docker stop --time=30', 'the web is given a 30-second graceful stop',
            'a stop of 30 secs', 'a stop of 30 sec', 'a stop of 30,000 ms', 'docker compose stop --timeout=30'),
}
# the same syntaxes stating numbers that are no role's bound (another container's 60 s stop among them): never read
NOT_A_BOUND = ('docker run --stop-timeout 60', 'docker stop -t 45', 'a 45-second stop', 'a stop of 26 min',
               'a stop of 1501 secs', 'docker stop --time=301')


def completeness(texts: dict) -> list:
    """The failures of every completeness test of the F4 guard with ``texts`` (path -> text) read in place of the
    files: (role, path) of each failing subtest."""
    methods = H.completeness_methods()
    assert methods, 'the F4 guard has no completeness test'
    with H.reading(texts):
        results = [H.guard(name) for name in methods]
    return [(item.get('role'), item.get('path')) for result in results for item in H.failing(result)]


def in_md(plant: str) -> dict:
    return {INSTALL_MD: H.planted(INSTALL_MD, MD_ANCHOR, f'then stopped (graceful, 30 s) - {plant} -, parked as')}


class R2ETStopBoundSpellingsTests(unittest.TestCase):
    """DECISIONS D303 RDRX-2 (module docstring): the F4 guard's completeness check reads every syntax of each role's
    bound."""

    def test_every_syntax_of_a_roles_bound_fails_the_completeness_check(self):
        for role, plants in PLANTS.items():
            for plant in plants:
                with self.subTest(role=role, plant=plant):
                    self.assertEqual(completeness(in_md(plant)), [(role, 'INSTALL.md')])

    def test_a_statement_in_the_installers_prose_fails_it_too(self):
        """install.py's comments are read as INSTALL.md's prose is: the setter's own flag in a comment beside the
        bound's definition fails the completeness check on install.py."""
        for role, plant in (('worker', 'docker run --stop-timeout 1500 sets it.'), ('web', 'the web stops in 30 secs.')):
            text = H.planted(INSTALL_PY, PY_ANCHOR, f'{PY_ANCHOR} {plant}')
            with self.subTest(role=role, plant=plant):
                self.assertEqual(completeness({INSTALL_PY: text}), [(role, 'install.py')])

    def test_the_texts_as_they_stand_and_numbers_that_are_no_bound_pass(self):
        """The boundaries: the ops texts as they stand pass every completeness test (each statement of a bound lies in a
        listed form or states another bound OTHER_BOUNDS lists), and the widened syntaxes stating a number that is no
        role's bound - another container's 60 s stop, 45 s, 26 minutes, 1,501 s, 301 s - are not read as a bound."""
        self.assertEqual(completeness({}), [])
        for plant in NOT_A_BOUND:
            with self.subTest(plant=plant):
                self.assertEqual(completeness(in_md(plant)), [])
        # the other bounds sharing the web's literal stay in the forms OTHER_BOUNDS lists, as stated
        for path in (INSTALL_PY, INSTALL_MD):
            with self.subTest(path=path.name):
                self.assertEqual(F4.unaccounted(F4.prose(path), install.STOP_SECONDS['web']), [])

    def test_the_spelling_set_reads_the_flags_the_installer_passes_the_bound_with(self):
        """The set is derived from the setter and the stopper themselves: install.py passes the bound with docker run's
        --stop-timeout and docker stop's --time (setter_flags reads them from its source), and a flag it starts passing
        the bound with is spelled without being listed by hand."""
        self.assertEqual(F4.setter_flags(), ('--stop-timeout', '--time'))
        source = "docker('stop', '--grace-period', str(STOP_SECONDS[role]), name)\n"
        self.assertEqual(F4.setter_flags(source), ('--grace-period',))
        self.assertEqual(F4.setter_flags("docker('stop', '--time', '30', name)\n"), ())  # no STOP_SECONDS: not its flag
        with mock.patch.object(F4, 'setter_flags', lambda source=None: ('--grace-period',)):
            self.assertTrue(F4.spellings(1500).search('docker stop --grace-period 1500'))
            self.assertTrue(F4.spellings(1500).search('docker stop --grace-period=1500'))
            self.assertIsNone(F4.spellings(1500).search('docker stop --time 1500'))  # the flags read, not a list
        for flag in ('--stop-timeout', '--time', '-t', '--timeout'):
            with self.subTest(flag=flag):
                self.assertTrue(F4.spellings(30).search(f'{flag} 30'))
                self.assertIsNone(F4.spellings(30).search(f'{flag} 300'))

    def test_the_guard_names_the_plant_where_it_was_invisible(self):
        """The refutation's measure (its p6c): every test of the F4 guard run with and without a plant - at the current
        bound, where the module docstring claims completeness - and the failures compared as a multiset. Before RDRX-2
        the two were equal (the plant named by no failure, so a mover could start from a text holding a statement the
        guard never reads, and leave it stale); now the plant adds exactly the failures naming it, one per role's
        completeness check that reads its bound."""
        from collections import Counter

        def failures(texts: dict) -> Counter:
            names = [name for name in dir(F4.R2RStopBoundStated) if name.startswith('test_')]
            with H.reading(texts):
                results = [H.guard(name) for name in names]
            return Counter((item.get('role'), item.get('path'), item.get('form'))
                           for result in results for item in H.failing(result))

        without = failures({})
        self.assertEqual(without, Counter())
        for role, plant in (('worker', 'the worker is stopped with docker stop -t 1500'),
                            ('worker', 'the worker is given a 25-minute stop'),
                            ('web', 'the web is given a 30-second graceful stop')):
            with self.subTest(role=role, plant=plant):
                self.assertEqual(failures(in_md(plant)) - without, Counter({(role, 'INSTALL.md', None): 1}))

if __name__ == '__main__':
    unittest.main()
