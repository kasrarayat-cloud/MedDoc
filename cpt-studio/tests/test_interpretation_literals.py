"""The literal parsers of evidence binding (Gemini migration slice S02; design/contract.md 5.3, design/ADJUDICATION.md
EB1), TEXT-ONLY: every date form with its precision and the weekday and %y rules, the comparison at a literal's own
precision, sizes, distances and durations, and person names - parentheticals removed whether closed or cut, titles,
credentials and role words set aside, one name per part. Each parser's misses are pinned as known limits, so a later
widening is a deliberate, versioned change. Synthetic strings written for this test; nothing is sent."""
from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase

from studio.interpretation import literals


def read(text: str) -> list:
    return [(item.iso, item.precision) for item in literals.dates(text)]


def names(text: str) -> list:
    return [(item.tokens, item.titled, item.credentialed) for item in literals.names(text)]


class FullDates(SimpleTestCase):
    def test_every_form_the_contract_names_reads_at_day_precision(self):
        for text, iso in (('2026-03-14', '2026-03-14'), ('03/14/2026', '2026-03-14'), ('3/4/2026', '2026-03-04'),
                          ('3/14/26', '2026-03-14'), ('March 14, 2026', '2026-03-14'), ('Mar. 14 2026', '2026-03-14'),
                          ('March 14th, 2026', '2026-03-14'), ('14 March 2026', '2026-03-14'),
                          ('16-Nov-2026', '2026-11-16'), ('Sept 9, 2026', '2026-09-09')):
            with self.subTest(text):
                self.assertEqual(read(text), [(iso, 'day')])
                self.assertEqual([item.value.isoformat() for item in literals.full_dates(text)], [iso])

    def test_two_digit_years_pivot_as_strptime_does(self):
        self.assertEqual(read('1/2/68'), [('2068-01-02', 'day')])
        self.assertEqual(read('1/2/69'), [('1969-01-02', 'day')])
        self.assertEqual(read('1/2/00'), [('2000-01-02', 'day')])

    def test_a_weekday_must_name_the_dates_own_day(self):
        # 2026-11-09 is a Monday (the owner decision of 2026-11-07, ported).
        self.assertEqual(read('Monday, November 9, 2026'), [('2026-11-09', 'day')])
        self.assertEqual(read('Mon 11/09/2026'), [('2026-11-09', 'day')])
        self.assertEqual(read('Mon., 11/09/2026'), [('2026-11-09', 'day')])
        for text in ('Tuesday, November 9, 2026', 'Tue 11/09/2026'):
            with self.subTest(text):
                self.assertEqual(read(text), [], 'a weekday naming another day leaves the date unread')
                self.assertEqual(literals.full_dates(text), ())

    def test_an_impossible_date_is_not_read_and_covers_its_place(self):
        self.assertEqual(read('2/30/2026'), [])
        self.assertEqual(read('2026-13-01'), [])

    def test_a_date_inside_a_longer_token_is_not_read(self):
        for text in ('x03/14/2026', '03/14/2026x', '1/03/14/2026', '03/14/20265'):
            with self.subTest(text):
                self.assertEqual(literals.full_dates(text), ())

    def test_offsets_are_the_texts_own(self):
        text = 'Seen on 03/14/2026 and again on 04/01/2026.'
        found = literals.full_dates(text)
        self.assertEqual([text[item.start:item.end] for item in found], ['03/14/2026', '04/01/2026'])


class CoarserDates(SimpleTestCase):
    def test_month_and_year(self):
        for text in ('January 2024', 'Jan 2024', 'Jan. 2024', 'January, 2024', '1/2024', '01/2024'):
            with self.subTest(text):
                self.assertEqual(read(text), [('2024-01', 'month')])

    def test_a_bare_year_standing_alone(self):
        for text in ('2024', 'in 2024', 'since 2019', '(2017)', 'colonoscopy 2019 normal'):
            with self.subTest(text):
                self.assertEqual(len(read(text)), 1)
                self.assertEqual(read(text)[0][1], 'year')
        self.assertEqual(read('1900'), [('1900', 'year')])
        self.assertEqual(read('2099'), [('2099', 'year')])

    def test_a_year_is_not_read_inside_a_number_a_range_or_before_a_unit(self):
        for text in ('12024', '20245', '2024-05', '2024.5', '1899', '2100', '2000 mg', '2000mg', '2024 units',
                     '1950 kcal', '2 years ago', '3 months'):
            with self.subTest(text):
                self.assertEqual(read(text), [])

    def test_a_finer_literal_covers_its_coarser_parts(self):
        self.assertEqual(read('March 14, 2024'), [('2024-03-14', 'day')])
        self.assertEqual(read('March 2024'), [('2024-03', 'month')])
        self.assertEqual(read('Tuesday, November 9, 2026'), [], 'an unread full date still covers its year')
        self.assertEqual(read('in 2019 and on 03/14/2026'), [('2019', 'year'), ('2026-03-14', 'day')])

    def test_known_limits(self):
        # Forms the contract does not name are not read (a later widening is a new INVENTORY_VERSION).
        for text in ('03-14-2026', '14.03.2026', '2026/03/14', '03/14', 'the 14th of March, 2026'):
            with self.subTest(text):
                self.assertEqual(literals.full_dates(text), ())
        self.assertEqual(read('2019-2024'), [], 'a year range is read as no year')


class Comparison(SimpleTestCase):
    SERVICE = date(2026, 11, 9)

    def test_each_precision_compares_at_its_own_grain(self):
        cases = (((2026, 1, 1), 'year', 0), ((2025, 1, 1), 'year', -1), ((2027, 1, 1), 'year', 1),
                 ((2026, 11, 1), 'month', 0), ((2026, 10, 1), 'month', -1), ((2026, 12, 1), 'month', 1),
                 ((2026, 11, 9), 'day', 0), ((2026, 11, 8), 'day', -1), ((2026, 11, 10), 'day', 1))
        for parts, precision, want in cases:
            with self.subTest(parts=parts, precision=precision):
                self.assertEqual(literals.compare(date(*parts), precision, self.SERVICE), want)

    def test_an_unknown_precision_raises(self):
        with self.assertRaises(ValueError):
            literals.compare(date(2026, 1, 1), 'week', self.SERVICE)

    def test_stored_literals_read_back_only_when_well_formed(self):
        self.assertEqual(literals.stored_date('2024', 'year'), date(2024, 1, 1))
        self.assertEqual(literals.stored_date('2024-03', 'month'), date(2024, 3, 1))
        self.assertEqual(literals.stored_date('2024-03-14', 'day'), date(2024, 3, 14))
        for value, precision in (('2024-13', 'month'), ('2024-02-30', 'day'), ('24', 'year'), ('2024', 'day'),
                                 (2024, 'year'), ('2024', 'decade')):
            with self.subTest(value=value, precision=precision):
                self.assertIsNone(literals.stored_date(value, precision))
        self.assertEqual(literals.iso_date('2026-11-09'), date(2026, 11, 9))
        self.assertIsNone(literals.iso_date('11/09/2026'))

    def test_iso_names_the_literal_at_its_precision(self):
        self.assertEqual([item.iso for item in literals.dates('in 2024, March 2025, 03/14/2026')],
                         ['2024', '2025-03', '2026-03-14'])


class Measures(SimpleTestCase):
    def test_sizes_in_millimetres(self):
        cases = (('7 mm', (7,)), ('a 7-mm polyp', (7,)), ('5-7 mm', (5, 7)), ('5\u20137 mm', (5, 7)),
                 ('5 to 7 mm', (5, 7)), ('1.5 cm', (15,)), ('approximately 1 cm', (10,)), ('10 x 8 mm', (10, 8)),
                 ('10 x 8 x 5 mm', (10, 8, 5)), ('2 centimeters', (20,)), ('6 millimetres', (6,)))
        for text, sizes in cases:
            with self.subTest(text):
                self.assertEqual(literals.sizes_mm(text), sizes)

    def test_a_distance_is_never_a_size(self):
        self.assertEqual(literals.sizes_mm('a 7 mm polyp at 30 cm'), (7,))
        self.assertEqual(literals.sizes_mm('at 30 cm'), ())
        self.assertEqual(literals.sizes_mm('25 cm from the incisors'), ())
        self.assertEqual(literals.distances_cm('a 7 mm polyp at 30 cm'), (30,))
        self.assertEqual(literals.distances_cm('25 cm from the incisors'), (25,))
        self.assertEqual(literals.distances_cm('advanced to 60 cm'), (60,))
        self.assertEqual(literals.distances_cm('a 1 cm polyp'), ())

    def test_no_measure(self):
        for text in ('a small polyp', '7', 'mm', '2000 mg', '7 mmol', 'x7 mm'):
            with self.subTest(text):
                self.assertEqual(literals.sizes_mm(text), ())

    def test_durations_in_minutes(self):
        cases = (('45 minutes', (45,)), ('45 min', (45,)), ('45 mins', (45,)), ('1 hour', (60,)), ('2 hrs', (120,)),
                 ('1.5 hours', (90,)), ('thirty minutes', (30,)), ('twenty-five min', (25,)), ('30-40 minutes', (30, 40)),
                 ('Total time spent: 45 minutes.', (45,)))
        for text, minutes in cases:
            with self.subTest(text):
                self.assertEqual(literals.durations_min(text), minutes)

    def test_no_duration(self):
        for text in ('45', 'minutes', 'a long visit', 'several minutes', '45 mm'):
            with self.subTest(text):
                self.assertEqual(literals.durations_min(text), ())


class Names(SimpleTestCase):
    def test_a_cut_parenthetical_gives_the_same_name_as_the_whole_one(self):
        # The trial's v5 slip: six strings cut by one character before a closing parenthesis.
        whole = names('Grace Okafor, MD (fictional)')
        self.assertEqual(whole, [(('grace', 'okafor'), False, True)])
        self.assertEqual(names('Grace Okafor, MD (fictional'), whole)
        self.assertEqual(names('Grace Okafor (synthetic, MD) [fellow'), [(('grace', 'okafor'), False, False)])

    def test_titles_and_credentials_mark_a_person_and_are_never_tokens(self):
        self.assertEqual(names('Dr. Okafor'), [(('okafor',), True, False)])
        self.assertEqual(names('Doctor Robin Lee'), [(('robin', 'lee'), True, False)])
        self.assertEqual(names('Okafor MD'), [(('okafor',), False, True)])
        self.assertEqual(names('dr. okafor'), [(('okafor',), True, False)], 'the word after a title, in any case')
        self.assertEqual(names('Prof. Lee, PhD, FACG'), [(('lee',), True, True)])

    def test_one_name_per_part(self):
        self.assertEqual(names('Dr. Okafor and Dr. Patel'), [(('okafor',), True, False), (('patel',), True, False)])
        self.assertEqual(names('Okafor; Patel / Lee & Kim'), [(('okafor',), False, False), (('patel',), False, False),
                                                              (('lee',), False, False), (('kim',), False, False)])
        self.assertEqual(names('Okafor, Grace'), [(('okafor',), False, False), (('grace',), False, False)])
        self.assertEqual(names('Dr. Okafor with fellow Dr. Lee'), [(('okafor',), True, False),
                                                                   (('lee',), True, False)])

    def test_role_facility_and_function_words_are_not_names(self):
        for text in ('the fellow', 'the GI fellow', 'Attending Endoscopist', 'Outside Hospital', 'the referring clinic',
                     'Anesthesia staff', 'I', 'We', 'the same physician', 'Performed by the team'):
            with self.subTest(text):
                self.assertEqual(names(text), [])
        self.assertEqual(names('Attending: Grace Okafor'), [(('grace', 'okafor'), False, False)])
        self.assertEqual(names('Under MAC by Dr. Lee'), [(('lee',), True, False)])

    def test_any_other_word_ends_a_name(self):
        self.assertEqual(names('Dr. Lee removed it'), [(('lee',), True, False)])
        self.assertEqual(names('Okafor today'), [(('okafor',), False, False)])

    def test_initials_possessives_and_hyphens(self):
        self.assertEqual(names('G. Okafor'), [(('okafor',), False, False)])
        self.assertEqual(names("Dr. Patel's team"), [(('patel',), True, False)])
        self.assertEqual(names('Dr. Okafor-Lee'), [(('okafor', 'lee'), True, False)])
        self.assertEqual(names("O'Brien"), [(("o'brien",), False, False)])

    def test_the_surname_is_the_last_token_and_tokens_are_pooled(self):
        found = literals.names('Grace Okafor, MD and Robin Lee')
        self.assertEqual([item.surname for item in found], ['okafor', 'lee'])
        self.assertEqual(literals.name_tokens(found), frozenset({'grace', 'okafor', 'robin', 'lee'}))
        self.assertEqual(found[0].as_record(), {'tokens': ['grace', 'okafor'], 'titled': False, 'credentialed': True})

    def test_no_name(self):
        for text in ('', '   ', '(Dr. Okafor)', '7 mm', 'performed'):
            with self.subTest(text):
                self.assertEqual(names(text), [])

    def test_known_limits(self):
        # A lowercase surname after a lowercase given name is not read (only capitalized words, or the one word after a
        # title, are tokens); an untitled capitalized place reads as a name, which is why only a titled or credentialed
        # name is ever an exclusion's literal (verify.exclusion_basis).
        self.assertEqual(names('dr. grace okafor'), [(('grace',), True, False)])
        self.assertEqual(names('County General'), [(('county', 'general'), False, False)])
