"""Repair round r2f, lane f-tools (DECISIONS D309: the r2e refutation's F2). The tree's own ops texts and in-memory
plants only; no Docker, no database, no network.

F2 - whenever a guard claims completeness over every statement of a bound, its spelling set reads the bound's number in
every numeral form (digits with or without any grouping separator, trailing decimal zeros, number words, a fraction of a
larger unit) and every unit form in any letter case, with any joiner (space, none, any hyphen or dash character); and a
test plants each form in a text and requires the completeness check to fail on it. ops/test_r2r_records.py's F4 guard
claims every statement of each role's stop bound (STOP_SECONDS): its completeness check (``unaccounted`` over
``spellings``) read, after D303 RDRX-2, the setter's flags and the number in each unit spaced, with an ASCII hyphen or
joined, in lower case, with the thousands comma or none - so a statement of a role's CURRENT bound in any other form was
invisible to it (the r2e refutation: 17 of its 21 plants green; with the bound moved as a mover moves it, the guard's
failures were the same multiset with the plant as without it). Here, through the guard's own tests run with a statement
planted in INSTALL.md (ops/test_r2dr_records3.py's harness): the refutation's plants and every form of each category,
for each role, fail the completeness check naming the plant's role; the texts as they stand pass; the same forms stating
a number that is no role's bound are left alone; and ``spellings`` reads a bound wherever a mover moves it (90 s, 45 s,
1,620 s, 1,800 s, an hour) in the same forms, and nothing else; and a decimal's digits after its point are never read as
a count (the earlier set read '0.25 min' as the worker's 25 minutes).

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_r2ft_*.py' -v
"""
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_r2dr_records3 as H  # noqa: E402  (the guard harness: guard, failing, planted, reading)
import test_r2r_records as F4  # noqa: E402  (the F4 guard)

OPS = Path(__file__).resolve().parent
INSTALL_MD = OPS / 'INSTALL.md'
MD_ANCHOR = 'then stopped (graceful, 30 s), parked as'
# the r2e refutation's plants that its guard could not see (its probes/g1_guard_forms.py), each stating the role's
# current bound (the worker's 1,800 s = 30 minutes since round r3 - 1,500 s = 25 minutes before it, the plants then
# stated - the web's 30 s): its surviving mutants, each one text
REFUTATION = {
    'worker': ('the worker is given a stop of 30 Minutes', '| worker | 1,800 Seconds |',
               'WORKER STOP TIMEOUT: 1800 SECONDS', 'the worker is given a 30-Minute stop',
               'the worker stops within 1800 Sec', 'the worker service sets stop_grace_period: 30m',
               'the worker is given a 30m stop', 'the worker unit sets TimeoutStopSec=1800',
               'the worker is given thirty minutes to stop', 'the worker is given a 1,800\u2011second stop',
               'the worker is given a 1,800\u2013second stop', 'the worker is given a 1 800 s stop',
               'the worker is given 1800.0 s to stop'),
    'web': ('the web is given a 30 Second graceful stop', 'the web is given 30 Seconds to drain',
            'the web is given half a minute to drain', 'the web is given thirty seconds to drain'),
}
# every form of each category the rule names, for each role's current bound
FORMS = {
    'a grouping separator': {
        'worker': ('a 1.800 s stop', 'a 1\u00a0800 s stop', 'a 1\u202f800 s stop', "a 1'800 s stop",
                   'a 1\u2019800 s stop', 'a 1_800 s stop', 'a stop of 1,800,000 ms', 'a stop of 1.800.000 ms',
                   'a stop of 18,00,000 ms', 'a stop of 1 800 000 000 \u00b5s',
                   'a \uff11\uff18\uff10\uff10 s stop', 'a \u0661\u0668\u0660\u0660 s stop'),
        'web': ('a stop of 30,000 ms', 'a stop of 30 000 ms', 'a stop of 30.000 ms', 'a stop of 30000 msecs'),
    },
    'leading and trailing decimal zeros': {
        'worker': ('a stop of 1800.00 s', 'a stop of 1,800.0 seconds', 'a stop of 1800,0 s', 'a stop of 01800 s',
                   'a 30.0-minute stop'),
        'web': ('a stop of 30.0 s', 'a stop of 30,00 seconds', 'a stop of 030 s', 'a 30.000-second stop'),
    },
    'number words': {
        'worker': ('eighteen hundred seconds', 'one thousand eight hundred seconds',
                   'one thousand, eight hundred seconds', 'a thousand and eight hundred seconds',
                   'thirty minutes', 'Thirty Minutes', 'THIRTY MINUTES', 'a thirty-minute stop',
                   'a thirty\u2011minute stop', 'one million eight hundred thousand milliseconds',
                   'eighteen-hundred seconds', 'one-thousand eight-hundred seconds'),
        'web': ('Thirty Seconds', 'THIRTY SECONDS', 'a thirty-second stop', 'thirty thousand milliseconds'),
    },
    'a fraction of a larger unit': {
        'worker': ('a 1/2 hour stop', 'a 1\u20442-hour stop', '1 / 2 h', 'half an hour', 'a half-hour stop',
                   '0.5 h', '\u00bd hour'),
        'web': ('half a minute', 'Half A Minute', 'half-minute', 'a half minute', 'half of a minute',
                'a half\u2013minute', '0.5 min', '.5 minutes', '0,5 Min', '0.50 minutes', '\u00bd minute', '1/2 minute',
                '1\u20442 minute', '1\u22152 minute',
                'one-half minute', '\u00bd a minute'),
    },
    'a unit form in any letter case': {
        'worker': ('1800 S', '1800 Secs', '1800 SEC', '30 MINS', '30 Min', '30 m', '30 M', '30\u2032',
                   'a 30 MINUTE stop', '1800000 MS', '1,800,000 Milliseconds',
                   '1800000000000 ns', '1,800,000,000,000 NSEC', '1800000000 usec', '1800000000 \u03bcs'),
        'web': ('30 S', '30 SECONDS', '30 Sec', '30\u2033', '30000 MSEC'),
    },
    'any joiner': {
        'worker': ('1800s', '1800sec', '30min', '30minutes', 'a 1,800\u2010second stop', 'a 1,800\u2012second stop',
                   'a 1,800\u2014second stop', 'a 1,800\u2015second stop', 'a 1,800\u2212second stop',
                   'a 1,800\ufe63second stop', 'a 1,800\uff0dsecond stop', 'a 1,800 - second stop',
                   'a 1,800 \u2013 second stop', 'a 30\u2011minute stop', 'a 30 - minute stop',
                   '1800\u200bs', 'a 1,800\u2060second stop'),
        'web': ('30sec', '30seconds', 'a 30\u2010second stop', 'a 30\u2014second stop', 'a 30 \u2013 second stop',
                'a 30\u2212second stop'),
    },
    'a sum of hours, minutes and seconds, and a key naming its unit': {
        'worker': ('stop_grace_period: 30m0s', '0h30m0s', '0h30m', '30 minutes 0 seconds', '30 min, 0 s',
                   '30 minutes and 0 seconds', 'TimeoutStopSec=1800', 'TimeoutStopUSec=1800000000',
                   "STOP_SECONDS['worker'] = 1800", 'stop_timeout_minutes: 30', 'stop-timeout-ms=1800000'),
        'web': ('0m30s', '0h0m30s', 'stop_timeout_s: 30', 'seconds: 30', 'timeout_ms=30000', 'graceSeconds=30'),
    },
}
# the same categories stating numbers that are no role's bound: never read as one - beside the bound (1,801 s, 31
# minutes), the worker's number in another unit, and the worker's bound before round r3 (1,500 s = 25 minutes)
NOT_A_BOUND = ('a 1.8 s stop', '1,801 seconds', '1800.5 s', 'a stop of 1801.0 s', 'thirty-one minutes',
               'thirty hours', 'eighteen hundred minutes', 'thirty-one seconds', 'twenty-five minutes',
               '1,500 seconds', 'a quarter of a minute', '\u00bc minute', '1/3 minute', '31 Seconds', '30 Hours',
               '300 s', '18000 ms', '30m31s', '0h31m', 'TimeoutStopSec=1801', 'TimeoutStopSec=1500', 'workers: 30',
               'timeout_s=6', 'a 25-minute stop', 'a quarter of an hour', 'a 1,800-page manual', 'version 1.800',
               'stage 2, 30 items')


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


class R2FTStopBoundSpellingsTests(unittest.TestCase):
    """DECISIONS D309 F2 (module docstring): the F4 guard's completeness check reads every numeral form and every unit
    form, in any letter case and with any joiner, of each role's bound."""

    def assertCaught(self, role: str, plants) -> None:
        for plant in plants:
            with self.subTest(role=role, plant=plant):
                self.assertEqual(completeness(in_md(plant)), [(role, 'INSTALL.md')])

    def test_the_refutations_plants_fail_the_completeness_check(self):
        """The r2e refutation's surviving mutants: each plant, at the current bound, fails the completeness check
        naming its role (each passed it before)."""
        self.assertEqual(install.STOP_SECONDS, {'web': 30, 'worker': 1800})
        for role, plants in REFUTATION.items():
            self.assertCaught(role, plants)

    def test_every_numeral_form_fails_it(self):
        for category in ('a grouping separator', 'leading and trailing decimal zeros', 'number words',
                         'a fraction of a larger unit'):
            for role, plants in FORMS[category].items():
                with self.subTest(category):
                    self.assertCaught(role, plants)

    def test_every_unit_form_in_any_case_and_any_joiner_fails_it(self):
        for category in ('a unit form in any letter case', 'any joiner'):
            for role, plants in FORMS[category].items():
                with self.subTest(category):
                    self.assertCaught(role, plants)

    def test_a_sum_of_units_and_a_key_naming_its_unit_fail_it(self):
        for role, plants in FORMS['a sum of hours, minutes and seconds, and a key naming its unit'].items():
            self.assertCaught(role, plants)

    def test_the_texts_as_they_stand_and_numbers_that_are_no_bound_pass(self):
        """The boundaries: the ops texts as they stand pass every completeness test, and the same forms stating a number
        that is no role's bound - another duration, a fraction of the wrong unit, another count with a unit, a key
        naming no unit - are not read as a bound."""
        self.assertEqual(completeness({}), [])
        for plant in NOT_A_BOUND:
            with self.subTest(plant=plant):
                self.assertEqual(completeness(in_md(plant)), [])

    def test_a_decimal_is_never_read_by_its_digits_after_the_point(self):
        """A decimal's digits after its point state a fraction, never a count: '0.25 min' is 15 s and '2.30 s' 2.3 s -
        the earlier set read them as the worker's 25 minutes and the web's 30 s (a failure naming no statement of a
        bound)."""
        for plant in ('a stop of 0.25 min', 'a stop of 0.30 min', 'a stop of 2.30 s', 'a stop of 0,30 min',
                      'a stop of 1.1800 s'):
            with self.subTest(plant=plant):
                self.assertEqual(completeness(in_md(plant)), [])

    def test_the_guard_names_the_plant_where_it_was_invisible(self):
        """The refutation's measure (its p6c): every test of the F4 guard run with and without a plant at the current
        bound, the failures compared as a multiset - the plant adds exactly the failure naming it, one per role whose
        completeness check reads its bound."""
        def failures(texts: dict) -> Counter:
            names = [name for name in dir(F4.R2RStopBoundStated) if name.startswith('test_')]
            with H.reading(texts):
                results = [H.guard(name) for name in names]
            return Counter((item.get('role'), item.get('path'), item.get('form'))
                           for result in results for item in H.failing(result))

        without = failures({})
        self.assertEqual(without, Counter())
        for role, plant in (('worker', 'WORKER STOP TIMEOUT: 1800 SECONDS'), ('worker', 'thirty minutes'),
                            ('worker', 'a 1,800\u2013second stop'), ('worker', 'TimeoutStopSec=1800'),
                            ('web', 'half a minute'), ('web', 'Thirty Seconds')):
            with self.subTest(role=role, plant=plant):
                self.assertEqual(failures(in_md(plant)) - without, Counter({(role, 'INSTALL.md', None): 1}))


class R2FTSpellingsWhereverTheBoundMovesTests(unittest.TestCase):
    """DECISIONS D309 F2, the class: ``spellings`` is derived from the bound, so it reads every form of a bound a mover
    moves it to - its whole and its fractional units, its words, its sums - and no other number."""
    READ = {
        90: ('90 s', 'ninety seconds', 'a minute and a half', 'one and a half minutes', '1 and a half minutes',
             '1.5 minutes', '1,5 min', '1\u00bd minutes', '1 1/2 minutes', '1-1/2 minutes', '1m30s',
             '1 minute 30 seconds', '1 min, 30 s', 'a minute and thirty seconds', '90,000 ms', 'TimeoutStopSec=90',
             '3/2 minutes', '1/40 hour'),
        45: ('45 s', 'forty-five seconds', 'three quarters of a minute', 'three-quarters of a minute', '0.75 min',
             '\u00be minute', '3/4 minute', '0m45s'),
        1620: ('1,620 s', 'sixteen hundred and twenty seconds', 'one thousand six hundred twenty seconds',
               '27 minutes', 'twenty-seven minutes', '0.45 hours', '27m0s'),
        1800: ('1,800 s', '30 minutes', 'thirty minutes', 'half an hour', 'a half-hour', 'half-hour', '0.5 h',
               '\u00bd hour', '30m', '0h30m0s'),
        3600: ('3,600 s', 'an hour', 'one hour', 'a 60-minute stop', '1h', '1h0m0s', '1 hour 0 minutes', '60 Minutes',
               'sixty minutes'),
    }
    NOT_READ = {
        90: ('90 minutes', '9 s', '1 minute', 'a minute', 'half a minute', '1.5 hours', 'ninety-one seconds',
             '1m31s', '190 s'),
        45: ('45 minutes', 'a quarter of a minute', 'forty seconds', '0.45 min', '4/5 minute'),
        1620: ('1,600 s', '26 minutes', 'twenty-six minutes', '0.5 hours', 'sixteen hundred seconds'),
        1800: ('3 minutes', 'half a minute', 'thirty seconds', '0.5 min', '30 s', 'half a day'),
        3600: ('a minute', '6 minutes', '1h30m', '60 s', 'ninety minutes'),
    }

    def test_every_form_of_a_moved_bound_is_read(self):
        for bound, texts in self.READ.items():
            for text in texts:
                with self.subTest(bound=bound, text=text):
                    found = F4.spellings(bound).search(f'the stop is {text}, then')
                    self.assertIsNotNone(found)

    def test_no_other_number_is_read(self):
        for bound, texts in self.NOT_READ.items():
            for text in texts:
                with self.subTest(bound=bound, text=text):
                    self.assertIsNone(F4.spellings(bound).search(f'the stop is {text}, then'))


if __name__ == '__main__':
    unittest.main()
