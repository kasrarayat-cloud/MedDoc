"""Format @4 checks of ops/verify_downloads.py against the layout studio/reports.py writes ('cpt-studio-report@4').

Hand-made reports built with test_verify_downloads' helpers. A source passage CPT Studio selected is printed as
'       + source passage selected by CPT Studio: "<passage>" [chars s–e]' and, like every passage in the TXT, a line
break inside it continues at nine spaces (reports._item_block / _indent); the closing bracket is on its last line.

    cd cpt-studio && .venv/bin/python -m unittest discover -s ops -p 'test_format4_*.py' -v
"""
import unittest

import test_verify_downloads as h

vd = h.vd

WRAPPED = 'a separate rectal lesion was biopsied with cold forceps\nand left in place for a later resection.'
TEXT = h.TEXT + 'Findings: ' + WRAPPED + '\n'
OPENER = '       + source passage selected by CPT Studio: '


def doc():
    item = h.proposal('p-biopsy', '45380', 'selected', 'ready', h.BIOPSY)
    item['evidence'] = [h.span_in(TEXT, h.BIOPSY)]
    source = h.span_in(TEXT, WRAPPED)
    source.pop('page')
    item['support'] = {'origin': 'primary', 'service': 'S1', 'status': 'warn', 'source': [source]}
    data = h.doc_with(TEXT, [item])
    data['coding'] = {'state': 'pending_review'}
    data['assessment']['services'] = {'conflicts': []}
    data['assessment']['completeness'] = {'unresolved_items': []}
    return data, source


def report(source, closing=None, first=None):
    """The draft TXT with the @4 sections and the item's source passage, as the renderer lays them out."""
    head, tail = WRAPPED.split('\n')
    opener = OPENER + (first if first is not None else f'"{head}')
    close = closing if closing is not None else f'         {tail}" [chars {source["start"]}–{source["end"]}]'

    def mutate(lines):
        lines = [line.replace('format cpt-studio-report@1', 'format cpt-studio-report@4') for line in lines]
        at = lines.index('ENCOUNTER, SOURCE AND REVISION') - 1
        lines = lines[:at] + ['', 'CODING COMPLETENESS', '  State: pending_review',
                              '  Every documented service has a proposal; each still needs a reviewer\'s decision.',
                              '', 'UNRESOLVED DOCUMENTED SERVICES — NO SUPPORTED PROPOSAL',
                              '  - none: every documented act the catalogue reconciles has a selected proposal or is '
                              'not separately reported', '', 'CONFLICTS IN THE RECORD', '  - none'] + lines[at:]
        at = next(i for i, line in enumerate(lines) if line.startswith('       - "' + h.BIOPSY)) + 1
        return lines[:at] + ['     Evidence support: warn — The provider passage does not show forceps biopsy.',
                             opener, close] + lines[at:]
    return h.txt_report('draft', doc()[0]['assessment']['proposals'], mutate_lines=mutate)


def status(text, api):
    return [r.status for r in vd.check_txt('d', 'r.txt', text, 'draft', api) if r.check == 'txt.source_passages']


class SourcePassageOverSeveralLinesTests(unittest.TestCase):
    def test_a_genuine_wrapped_source_passage_passes(self):
        api, source = doc()
        self.assertEqual(status(report(source), api), ['pass'])

    def test_a_wrapped_source_passage_with_altered_text_fails(self):
        api, source = doc()
        altered = f'         and removed with a hot snare." [chars {source["start"]}–{source["end"]}]'
        self.assertEqual(status(report(source, closing=altered), api), ['fail'])

    def test_a_wrapped_source_passage_with_wrong_offsets_fails(self):
        api, source = doc()
        shifted = f'         and left in place for a later resection." [chars {source["start"]}–{source["end"] + 7}]'
        self.assertEqual(status(report(source, closing=shifted), api), ['fail'])

    def test_a_source_line_without_its_closing_citation_fails(self):
        api, source = doc()
        self.assertEqual(status(report(source, closing='         and left in place for a later resection."'), api),
                         ['fail'])

    def test_control_a_single_line_source_passage_with_altered_text_fails(self):
        api, source = doc()
        line = f'"{h.SNARE}" [chars {source["start"]}–{source["end"]}]'
        self.assertEqual(status(report(source, first=line, closing='     Rationale: synthetic'), api), ['fail'])


if __name__ == '__main__':
    unittest.main()
