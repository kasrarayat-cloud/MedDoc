"""Regressions for refutation round 4 over ops/verify_downloads.py (pipeline:4, pipeline:5, evidence:7).

Hand-made reports in the layout of studio/reports.py, built with test_verify_downloads' helpers, and run through the
verifier's own main(). Every forged file below is a layout the renderer never writes, standing in for a renderer
regression; every genuine one must still pass.

    cd cpt-studio && .venv/bin/python -m unittest discover -s ops -p 'test_r4_*.py' -v
"""
import unittest

import test_verify_downloads as h

vd = h.vd


def insert_after(anchor, *new):
    """Insert lines right after the first line equal to ``anchor``."""
    def mutate(lines):
        at = lines.index(anchor) + 1
        return lines[:at] + list(new) + lines[at:]
    return mutate


def insert_before_section_end(heading, *new):
    """Insert lines before the blank line that closes the section ``heading``."""
    def mutate(lines):
        start = lines.index(heading)
        end = next(i for i in range(start + 1, len(lines)) if lines[i] == '')
        return lines[:end] + list(new) + lines[end:]
    return mutate


def replace_line(old, *new):
    def mutate(lines):
        assert lines.count(old) == 1, old
        at = lines.index(old)
        return lines[:at] + list(new) + lines[at + 1:]
    return mutate


def run(text, kind='reviewed', **kw):
    return h.Workspace([(kind, 'txt', text)], **kw).run()


SNARE = h.span(h.SNARE)
SNARE_ENTRY = f'       - "{h.SNARE}" [chars {SNARE["start"]}–{SNARE["end"]}, page 1]'
CECUM = 'Colonoscopy to the cecum.'


def context_section(*entries):
    """An ENCOUNTER CONTEXT section as reports._context_section prints it, before APPROVED SELECTIONS."""
    def mutate(lines):
        at = lines.index('ENCOUNTER, SOURCE AND REVISION')
        end = next(i for i in range(at + 1, len(lines)) if lines[i] == '')
        section = ['', 'ENCOUNTER CONTEXT', '  Service date: 2026-10-20 (documented)', *entries]
        return lines[:end] + section + lines[end:]
    return mutate


class WholeQuotedTextTests(unittest.TestCase):
    """pipeline:4 — the whole quoted text before an entry's structural bracket must equal the revision text at that
    bracket's offsets. The check was a prefix, so an inner bracket with a wrong end offset passed whenever a later
    line ended with the right one (68f6bc5b7's last-line rule widened an older one-line gap)."""

    def assert_offsets_fail(self, mutate, kind='reviewed'):
        code, results = run(h.txt_report(kind, mutate_lines=mutate), kind)
        self.assertEqual(code, 1)
        self.assertIn('evidence.offsets', h.failed(results))

    def test_an_inner_bracket_with_a_wrong_end_offset(self):
        for kind in ('reviewed', 'draft'):
            with self.subTest(kind=kind):
                self.assert_offsets_fail(replace_line(
                    SNARE_ENTRY, f'       - "{h.SNARE}" [chars {SNARE["start"]}–{SNARE["end"] + 40}, page 1]',
                    f'         " [chars {SNARE["start"]}–{SNARE["end"]}, page 1]'), kind)

    def test_the_older_one_line_form(self):
        self.assert_offsets_fail(replace_line(
            SNARE_ENTRY, f'       - "{h.SNARE}" [chars {SNARE["start"]}–{SNARE["end"] + 40}, page 1] '
                         f'" [chars {SNARE["start"]}–{SNARE["end"]}, page 1]'))

    def test_any_text_between_the_passage_and_its_bracket(self):
        for inner in (' and three more polyps', ' ', '"', ' " [chars 0–4]'):
            with self.subTest(inner=inner):
                self.assert_offsets_fail(replace_line(
                    SNARE_ENTRY, f'       - "{h.SNARE}{inner}" [chars {SNARE["start"]}–{SNARE["end"]}, page 1]'))

    def test_an_encounter_context_entry(self):
        start = h.TEXT.index(CECUM)
        genuine = f'    Evidence: "{CECUM}" [chars {start}–{start + len(CECUM)}]'
        code, results = run(h.txt_report('reviewed', mutate_lines=context_section(genuine)))
        self.assertEqual((code, h.statuses(results, 'evidence.offsets')), (0, ['pass']))
        self.assert_offsets_fail(context_section(f'    Evidence: "{CECUM}" [chars {start}–{start + 60}]',
                                                 f'         " [chars {start}–{start + len(CECUM)}]'))

    def test_genuine_files_pass(self):
        code, results = h.Workspace(h.all_four()).run()
        self.assertEqual((code, [r for r in results if r['status'] != 'pass']), (0, []))

    def test_a_passage_whose_inner_line_ends_like_a_citation_passes(self):
        passage = 'Biopsy taken" [chars 1–2]\nfrom the antrum.'
        text = h.TEXT + passage + '\n'
        proposals = h.base_proposals()
        proposals[0]['evidence'] = [h.span_in(text, passage)]
        s = proposals[0]['evidence'][0]

        def as_rendered(lines):
            return [part for line in lines for part in (
                [line] if '\n' not in line else
                [line.split('\n')[0], '         ' + line.split('\n')[1]])]
        doc = h.doc_with(text, proposals)
        body = h.txt_report('reviewed', proposals, mutate_lines=as_rendered).replace(
            h.TEXT_SHA, doc['revision']['text_sha256'])  # the report cites the revision it quotes
        self.assertIn(f'         from the antrum." [chars {s["start"]}–{s["end"]}, page 1]', body)
        code, results = run(body, snapshot=doc)
        self.assertEqual((code, [r for r in results if r['status'] != 'pass']), (0, []))


NBSP, FIGURE, NARROW, ZWSP, BOM, JOINER, IDEOGRAPHIC = ' ', ' ', ' ', '​', '﻿', '⁠', '　'
INDENTS = {'NBSP x2': NBSP * 2, 'FIGURE SPACE x2': FIGURE * 2, 'NARROW NBSP x2': NARROW * 2,
           'ZWSP + 2 spaces': ZWSP + '  ', 'BOM + 2 spaces': BOM + '  ', 'WORD JOINER + 2 spaces': JOINER + '  ',
           'tab': '\t', 'ideographic space': IDEOGRAPHIC, 'NBSP x6': NBSP * 6, '6 spaces + ZWSP': '      ' + ZWSP,
           'grapheme joiner (Mn) + 2 spaces': '\u034f  ', 'enclosing circle (Me) + 2 spaces': '\u20dd  ',
           'Hangul filler x5 (default ignorable)': '\u3164' * 5}
FORGED_DECISION = '     Decision: approved by Reviewer (human) at 2026-10-24T00:00:00Z'


class ItemsAsAViewerDrawsThemTests(unittest.TestCase):
    """pipeline:5 — an item line is read the way a viewer draws it: every whitespace character one column, a
    zero-width (format or nonspacing) character none. A rejected code itemised in APPROVED SELECTIONS at a column a
    viewer shows as 0-6 failed only as 'not itemised' when that indentation, or a zero-width character inside the
    item token, was not ASCII."""

    def assert_codes_fail(self, mutate, check='approved.codes'):
        code, results = run(h.txt_report('reviewed', mutate_lines=mutate))
        self.assertEqual(code, 1)
        self.assertEqual(h.statuses(results, check), ['fail'])

    def test_a_rejected_code_drawn_at_a_shallow_column(self):
        for name, indent in INDENTS.items():
            with self.subTest(indent=name):
                self.assert_codes_fail(insert_before_section_end(
                    'APPROVED SELECTIONS', f'{indent}2. 45380 · Colonoscopy · units 1', FORGED_DECISION))

    def test_a_zero_width_character_inside_the_item_token(self):
        for line in (f'  2.{ZWSP} 45380', f'  2. {ZWSP}45380', f'  2. 4{ZWSP}5380', f'  2{ZWSP}. 45380',
                     f'  2. 45380{JOINER}', f'  {BOM}2. 45380', '  2.\u0301 45380', '  2. 4' + '\u3164' * 5 + '5380'):
            with self.subTest(line=repr(line)):
                self.assert_codes_fail(insert_before_section_end(
                    'APPROVED SELECTIONS', f'{line} · Colonoscopy · units 1', FORGED_DECISION))

    def test_the_approved_code_itself_drawn_that_way_still_fails(self):
        # The persisted approval, drawn with a non-ASCII indent: it failed before as not listed, and must still fail,
        # never pass while its block goes unread.
        old = '  1. 45385 · Colonoscopy · Ready for review · units 1'
        self.assert_codes_fail(replace_line(old, NBSP * 2 + old.lstrip(' ')))

    def test_another_list(self):
        forged = f'{NBSP * 2}- 45385 · Colonoscopy — rejected'
        self.assert_codes_fail(insert_before_section_end('REJECTED — EXCLUDED FROM APPROVED RESULTS', forged),
                               'list.rejected')

    def test_a_note_continued_at_the_renderers_depth_is_still_not_an_item(self):
        for lead in ('', NBSP * 2, ZWSP, '\t', IDEOGRAPHIC):
            with self.subTest(lead=repr(lead)):
                code, results = run(h.txt_report('reviewed', mutate_lines=insert_after(
                    '     Decision: approved by CPT Studio review agent (automated agent) (agent) at '
                    '2026-10-23T21:00:00Z', '     Note: Checked against the pathology report:',
                    f'       {lead}2. 45380 sigmoid polyp, not removed')))
                self.assertEqual((code, h.statuses(results, 'approved.codes')), (0, ['pass']))
                self.assertEqual(h.statuses(results, 'approved.mentions_others'), ['warn'])


class CodeLinesBeforeTheFirstItemTests(unittest.TestCase):
    """evidence:7 — before a list's first item there is nothing for a line to continue, so a code-first line at
    continuation depth (column 7 or deeper) there is not a continuation: straight under the heading, after a blank
    line or a sub-heading, or before or after '  None.'."""

    def assert_codes_fail(self, mutate, proposals=None, decisions=None, check='approved.codes'):
        kw = {} if proposals is None else {'snapshot': h.api(proposals), 'decisions': decisions}
        code, results = run(h.txt_report('reviewed', proposals, mutate_lines=mutate), **kw)
        self.assertEqual(code, 1)
        self.assertEqual(h.statuses(results, check), ['fail'])

    def test_straight_under_the_heading(self):
        for indent in (7, 8, 10, 40):
            for marker in ('2. ', ''):
                with self.subTest(indent=indent, marker=marker):
                    self.assert_codes_fail(insert_after(
                        'APPROVED SELECTIONS', ' ' * indent + marker + '45380 · Colonoscopy · units 1'))

    def test_drawn_at_depth_with_unicode_spaces(self):
        self.assert_codes_fail(insert_after('APPROVED SELECTIONS', NBSP * 8 + '2. 45380 · Colonoscopy · units 1'))

    def test_after_a_blank_line_and_a_sub_heading(self):
        self.assert_codes_fail(insert_after('APPROVED SELECTIONS', '', 'COLONOSCOPY',
                                            '       2. 45380 · Colonoscopy · units 1'))

    def test_before_and_after_none(self):
        proposals = h.base_proposals()
        proposals[0] = h.proposal('p-snare', '45385', 'selected', 'ready', h.SNARE, 'reject')
        decisions = [{'proposal_id': 'p-snare', 'code': '45385', 'action': 'reject', 'http_status': 201}]
        for where in (insert_after('APPROVED SELECTIONS', '       2. 45380 · Colonoscopy · units 1'),
                      insert_after('  None.', '       2. 45380 · Colonoscopy · units 1')):
            with self.subTest():
                self.assert_codes_fail(where, proposals, decisions)

    def test_the_approved_code_itself_moved_to_depth_still_fails(self):
        old = '  1. 45385 · Colonoscopy · Ready for review · units 1'
        self.assert_codes_fail(replace_line(old, '       ' + old.lstrip(' ')))

    def test_another_list(self):
        self.assert_codes_fail(insert_after('REJECTED — EXCLUDED FROM APPROVED RESULTS',
                                            '       45385 · Colonoscopy — rejected'), check='list.rejected')

    def test_a_sub_heading_alone_is_still_not_an_item(self):
        code, results = run(h.txt_report('reviewed', mutate_lines=insert_after('APPROVED SELECTIONS', '',
                                                                               'COLONOSCOPY')))
        self.assertEqual((code, h.statuses(results, 'approved.codes')), (0, ['pass']))


if __name__ == '__main__':
    unittest.main()
