"""The Gemini migration's new path in ops/verify_downloads.py (cpt-studio/design: FINAL.md 4.3, 8.3, 13): the mirrors of
what studio/reports.py writes for an assessment the events engine made, held to the renderer's own lines.

- CONFLICTS IN THE RECORD: the stub services record stores no conflict, so no entry of a stored conflict is listed; the
  one line is the detail of the assessment's 'services.conflicts' check where it warns (reports._event_services'
  conflict_note, printed by reports._conflicts_section), and none where it does not.
- act_index: read whatever the engine, as review.act_index is; the stub carries no act, so a quotation of a new-path code
  is only its support.source and its supporting provider passages.
- A legacy assessment is read exactly as before.

Hand-made reports built with test_verify_downloads' helpers and test_format4_verify_downloads' @4 layout.

    cd cpt-studio && .venv/bin/python -m unittest discover -s ops -p 'test_events_verify_downloads.py' -v
"""
import copy
import unittest
from pathlib import Path

import test_format4_verify_downloads as f4
import test_verify_downloads as h

vd = h.vd

# reports._conflicts_section's line of a stored (legacy) conflict, and interpretation/assess.py's warning on the new path
LEGACY_LINE = '  - performed status (S1); both sides kept, neither chosen:'
NOTE = ('Conflicting statements, kept and not chosen between: snare removal of lesion L1 in the colonoscopy: stated as '
        'done and as not done.')
EVENTS = 'cpt-studio-events@1'


def check(status, detail):
    return {'id': 'services.conflicts', 'label': 'Conflicting statements', 'status': status, 'detail': detail,
            'source': 'CPT Studio event interpretation'}


def new_path(api, note=None):
    """The encounter JSON of a new-path assessment: the engine label, the stub services record, its encounter check."""
    api = copy.deepcopy(api)
    api['assessment']['engine_version'] = EVENTS
    api['assessment']['services'] = {'version': EVENTS, 'services': [], 'conflicts': [], 'attributions': [],
                                     'problems': []}
    api['assessment']['encounter_checks'] = [check('warn', note) if note else
                                             check('pass', 'No act is stated both as done and as not done for the '
                                                           'same service and site.')]
    return api


def conflicts_of(report_lines):
    """The draft @4 report of test_format4 with CONFLICTS IN THE RECORD's body replaced by ``report_lines``."""
    api, source = f4.doc()
    text = f4.report(source)
    head, _, rest = text.partition('\nCONFLICTS IN THE RECORD\n')
    assert _, 'the @4 layout has a CONFLICTS IN THE RECORD section'
    body, _, tail = rest.partition('\n\n')
    assert body == '  - none', body
    return f'{head}\nCONFLICTS IN THE RECORD\n' + '\n'.join(report_lines) + f'\n\n{tail}', api


def conflict_status(text, api):
    return [r.status for r in vd.check_txt('d', 'r.txt', text, 'draft', api) if r.check == 'txt.conflicts']


class NewPathConflictTests(unittest.TestCase):
    def test_the_engine_label_and_the_warning_are_read_from_the_encounter_json(self):
        api, _ = f4.doc()
        self.assertFalse(vd.events_engine(api))
        self.assertEqual(vd.conflict_note(api), '')
        self.assertTrue(vd.events_engine(new_path(api, NOTE)))
        self.assertEqual(vd.conflict_note(new_path(api, NOTE)), NOTE)
        self.assertEqual(vd.conflict_note(new_path(api)), '')
        # the engine label decides: a legacy assessment carrying the same check reads no note
        legacy = new_path(api, NOTE)
        legacy['assessment']['engine_version'] = 'cpt-studio-validation@10'
        self.assertEqual(vd.conflict_note(legacy), '')

    def test_the_warning_is_the_one_line_on_the_new_path(self):
        text, api = conflicts_of([f'  - {NOTE}'])
        self.assertEqual(conflict_status(text, new_path(api, NOTE)), ['pass'])

    def test_no_warning_lists_none(self):
        text, api = conflicts_of(['  - none'])
        self.assertEqual(conflict_status(text, new_path(api)), ['pass'])

    def test_a_warning_left_out_fails(self):
        text, api = conflicts_of(['  - none'])
        self.assertEqual(conflict_status(text, new_path(api, NOTE)), ['fail'])

    def test_a_warning_the_check_does_not_make_fails(self):
        text, api = conflicts_of([f'  - {NOTE}'])
        self.assertEqual(conflict_status(text, new_path(api)), ['fail'])
        text, api = conflicts_of([f'  - {NOTE.replace("snare removal", "biopsy")}'])
        self.assertEqual(conflict_status(text, new_path(api, NOTE)), ['fail'])

    def test_a_stored_conflict_entry_fails_on_the_new_path(self):
        # the stub stores no conflict: an entry of a stored one is a conflict nothing recorded
        text, api = conflicts_of([f'  - {NOTE}', LEGACY_LINE, '      document entry, performed: "x"'])
        self.assertEqual(conflict_status(text, new_path(api, NOTE)), ['fail'])

    def test_the_new_path_persists_no_conflict_entry_whatever_its_services_record_holds(self):
        # reports._event_services lists no stored conflict on the new path (its 'conflicts' is [] whatever the stub
        # holds), so neither the TXT nor the CSV mirror expects one; a legacy assessment's are read as stored
        api, _ = f4.doc()
        stored = [{'service': 'S1', 'subject': 'performed_status'}]
        events = new_path(api, NOTE)
        events['assessment']['services']['conflicts'] = stored
        self.assertEqual(vd._documented_expected(events)[2], set())
        legacy = copy.deepcopy(api)
        legacy['assessment']['services'] = {'conflicts': stored}
        self.assertEqual(vd._documented_expected(legacy)[2], {('S1', 'performed_status')})

    def test_a_legacy_report_is_read_as_before(self):
        # the legacy reading: a stored conflict listed where the services record stores it, and the new-path note means
        # nothing there
        text, api = conflicts_of([LEGACY_LINE, '      document entry, performed: "x"'])
        api['assessment']['services'] = {'conflicts': [{'service': 'S1', 'subject': 'performed_status'}]}
        self.assertEqual(conflict_status(text, api), ['pass'])
        text, api = conflicts_of(['  - none'])
        self.assertEqual(conflict_status(text, api), ['pass'])
        text, api = conflicts_of([f'  - {NOTE}'])
        self.assertEqual(conflict_status(text, api), ['pass'], 'a legacy assessment reads no note: no "(" names no conflict')

    def test_the_mirror_is_the_renderer_s_own_wording(self):
        # the stored-conflict line and the warning's opening are written where the renderer and the engine write them
        app = Path(__file__).resolve().parents[1]
        reports = (app / 'studio' / 'reports.py').read_text(encoding='utf-8')
        self.assertIn("'chosen:')", reports)
        self.assertIn("lines.append(f'  - {conflict[\"subject\"].replace(\"_\", \" \")} ({conflict[\"service\"]}); both sides "
                      "kept, neither '", reports)
        self.assertIn("lines.append(f'  - {_indent(documented[\"conflict_note\"], \"    \")}')", reports)
        self.assertTrue(vd.LEGACY_CONFLICT_END.endswith('neither chosen:'))
        assess = (app / 'studio' / 'interpretation' / 'assess.py').read_text(encoding='utf-8')
        self.assertIn("'Conflicting statements, kept and not chosen between: '", assess)
        self.assertIn(f"Check('services.conflicts', '{vd.EVENT_CONFLICTS_HEAD}', 'warn',", assess)


class NewPathActsTests(unittest.TestCase):
    def test_the_stub_carries_no_act_so_a_new_path_code_quotes_its_source(self):
        api = h.doc_with(h.TEXT, [h.proposal('p1', '45380', 'selected', 'ready', h.BIOPSY)])
        api['assessment']['services'] = {'services': [{'id': 'S1', 'acts': [{'id': 'S1-A1', 'status': 'performed',
                                                                             'evidence': [h.span_in(h.TEXT, h.BIOPSY)]}]}]}
        self.assertEqual(set(vd.act_index(api)), {'S1-A1'})
        self.assertEqual(vd.act_index(new_path(api)), {})
        # a code's quotation on the new path: its support.source and its supporting provider passages, never an act's
        proposal = api['assessment']['proposals'][0]
        proposal['support'] = {'status': 'pass', 'source': [h.span_in(h.TEXT, h.SNARE)], 'acts': [{'id': 'S1-A1'}],
                               'supporting': [], 'unrelated': []}
        legacy, _ = vd.allowed_passages(proposal, h.TEXT, vd.act_index(api))
        events, _ = vd.allowed_passages(proposal, h.TEXT, vd.act_index(new_path(api)))
        self.assertEqual([s['text'] for s in legacy], [h.SNARE, h.BIOPSY])
        self.assertEqual([s['text'] for s in events], [h.SNARE])


if __name__ == '__main__':
    unittest.main()
