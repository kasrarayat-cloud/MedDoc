"""Regression tests for refutation round 3 ingest:12: Acrobat's time formats are display formatting.

A text field's format action decides how a viewer shows its stored value; a field whose appearance shows what the
format makes of the value is not a disagreement. Times follow util.printd (pdf.js and Acrobat): HH / H 24-hour,
hh / h 12-hour, MM minutes, ss seconds, tt am / pm. A value is read as Acrobat's AFParseTime reads it: hours and
minutes (seconds optional) after the date, an am / pm marker if written, otherwise the hour as written.
"""
from __future__ import annotations

import unittest

from studio.ingest.pdfformat import displayed_texts
from tests.test_repairs_ingest_r2 import FIELDS_NOTE, formatted_form, mismatch, pdf_extract


class TimeFormatTests(unittest.TestCase):
    """ingest:12 — AFTime_Format, AFTime_FormatEx and date-time AFDate formats explain what the field shows."""

    def test_time_fields_shown_in_their_format_are_ok(self):
        cases = {'AFTime_Format(1), the claimed input': [('withdrawal', '8:30', '8:30 am', 'AFTime_Format(1);'),
                                                         ('bbps', '8:52', '8:52 am', 'AFTime_Format(1);')],
                 'AFTime_Format(0)': [('withdrawal', '8:30', '08:30', 'AFTime_Format(0);')],
                 'AFTime_Format(2), seconds': [('withdrawal', '8:30', '08:30:00', 'AFTime_Format(2);')],
                 'AFTime_Format(3)': [('withdrawal', '14:05:09', '2:05:09 pm', 'AFTime_Format(3);')],
                 'AFTime_FormatEx': [('withdrawal', '8:30', '8:30 am', 'AFTime_FormatEx("h:MM tt");')],
                 'a value written with pm': [('withdrawal', '8:30 pm', '20:30', 'AFTime_Format(0);')],
                 'AFDate_FormatEx date-time': [('withdrawal', '10/21/26 08:30', '10/21/2026 08:30',
                                                'AFDate_FormatEx("mm/dd/yyyy HH:MM");')],
                 'AFDate_Format(13)': [('withdrawal', '10/21/26 8:30', '10/21/26 08:30', 'AFDate_Format(13);')],
                 'AFDate_Format(12)': [('withdrawal', '10/21/26 14:30', '10/21/26 2:30 pm', 'AFDate_Format(12);')],
                 'the round-2 date-time case': [('withdrawal', '10/21/26 14:30', '10/21/2026 14:30',
                                                 'AFDate_FormatEx("mm/dd/yyyy HH:MM");')]}
        for label, fields in cases.items():
            with self.subTest(label):
                result = pdf_extract(formatted_form(fields), ocr=None)
                self.assertEqual((result.status, result.messages), ('ok', (FIELDS_NOTE,)))
                for name, stored, _, _ in fields:
                    self.assertIn(f'{name}: {stored}', result.text)

    def test_times_the_format_does_not_explain_stay_flagged(self):
        cases = {'pm shown for a morning value': ('8:30', '8:30 pm', 'AFTime_Format(1);'),
                 'another minute': ('8:30', '8:45 am', 'AFTime_Format(1);'),
                 'a 12-hour shape the format does not draw': ('8:30', '08:30', 'AFTime_Format(1);'),
                 'an hour that is no hour': ('25:00', '01:00', 'AFTime_Format(0);'),
                 'a minute that is no minute': ('8:75', '09:15', 'AFTime_Format(0);'),
                 'a date-time with another date': ('10/21/26 08:30', '10/22/2026 08:30',
                                                   'AFDate_FormatEx("mm/dd/yyyy HH:MM");'),
                 'a date-time with another time': ('10/21/26 08:30', '10/21/2026 09:30',
                                                   'AFDate_FormatEx("mm/dd/yyyy HH:MM");'),
                 'a date with no time under a date-time format': ('10/21/26', '10/21/2026 00:00',
                                                                  'AFDate_FormatEx("mm/dd/yyyy HH:MM");'),
                 'a word that is no marker': ('8:30 later', '08:30', 'AFTime_Format(0);'),
                 'a time format followed by more script': ('8:30', '8:30 am',
                                                           'AFTime_Format(1); event.value = "8:30 am";')}
        for label, (stored, shown, script) in cases.items():
            with self.subTest(label):
                result = pdf_extract(formatted_form([('withdrawal', stored, shown, script)]), ocr=None)
                self.assertEqual(result.status, 'partial')
                self.assertIn(mismatch('withdrawal'), result.messages)

    def test_displayed_texts_for_times(self):
        self.assertEqual(displayed_texts('AFTime_Format(1);', '8:30'), {'8:30 am', '8:30 AM'})
        self.assertEqual(displayed_texts('AFTime_Format(0);', '8:30'), {'08:30'})
        self.assertEqual(displayed_texts('AFTime_Format(0);', '12:15 am'), {'00:15'})
        self.assertEqual(displayed_texts('AFTime_Format(0);', '12:15 pm'), {'12:15'})
        self.assertEqual(displayed_texts('AFTime_Format(1);', '0:05'), {'12:05 am', '12:05 AM'})
        self.assertEqual(displayed_texts('AFTime_Format(2);', '8:30'), {'08:30:00'})
        self.assertEqual(displayed_texts('AFTime_FormatEx("H:M:s");', '08:05:07'), {'8:5:7'})
        self.assertEqual(displayed_texts('AFTime_FormatEx("hh:MM t");', '9:05 p.m.'), {'09:05 p', '09:05 P'})
        self.assertEqual(displayed_texts('AFDate_Format(13);', '10/21/26 8:30'),
                         {'10/21/26 08:30'})
        self.assertEqual(displayed_texts('AFDate_FormatEx("mm/dd/yyyy HH:MM");', '10/21/26 8:30'),
                         {'10/21/2026 08:30', '10/21/1926 08:30'})
        # a format whose time comes first reads the time first
        self.assertEqual(displayed_texts('AFDate_FormatEx("HH:MM mm/dd/yyyy");', '08:30 10/21/26'),
                         {'08:30 10/21/2026', '08:30 10/21/1926'})
        # a date-time whose date is no date shows nothing this can know
        self.assertEqual(displayed_texts('AFDate_FormatEx("mm/dd/yyyy HH:MM");', '13/45/26 08:30'), set())
        for script, value in (('AFTime_Format(1);', '13:30 pm'), ('AFTime_Format(0);', '24:00'),
                              ('AFTime_Format(0);', '8'), ('AFTime_Format(4);', '8:30'),
                              ('AFTime_Format(0);', '8:30:61'), ('AFTime_Format(0);', '8:30 am pm'),
                              # seconds the format does not show: the value says more than the field draws
                              ('AFTime_Format(0);', '8:30:15'),
                              ('AFDate_FormatEx("mm/dd/yyyy HH:MM");', '8:30')):
            with self.subTest(script=script, value=value):
                self.assertEqual(displayed_texts(script, value), set())

    def test_date_only_formats_are_unchanged(self):
        self.assertEqual(displayed_texts('AFDate_FormatEx("mm/dd/yyyy");', '10/21/26'), {'10/21/2026', '10/21/1926'})
        self.assertEqual(displayed_texts('AFDate_Format(2);', '10/21/2026'), {'10/21/26'})
        self.assertEqual(displayed_texts('AFDate_FormatEx("mm/dd/yyyy");', '10/21/26 14:30'), set())


if __name__ == '__main__':
    unittest.main()
