"""Actual service-table/Node assertion controls; no browser, DB or provider."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
import unittest

from django.template import Context, Engine

ROOT = Path(__file__).resolve().parents[3]


class Cells(HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.cells = []

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.active = True; self.cells.append('')

    def handle_endtag(self, tag):
        if tag == 'td':
            self.active = False

    def handle_data(self, value):
        if self.active:
            self.cells[-1] += value


class BrowserServedProfileRender(unittest.TestCase):
    def rendered(self, rows):
        template = (ROOT / 'rebuild/templates/admin_services.html').read_text()
        fragment = re.search(r'<div[^>]*id="language-model".*?</div>', template, re.S)
        self.assertIsNotNone(fragment)
        rendered = Engine().from_string(fragment.group()).render(
            Context({'configuration': SimpleNamespace(language_model=rows)}, use_l10n=False))
        parser = Cells(); parser.feed(rendered)
        return {' '.join(parser.cells[i].split()): ' '.join(parser.cells[i + 1].split())
                for i in range(0, len(parser.cells), 2)}

    def accepted(self, rows):
        source = (ROOT / 'rebuild/browser-tests.mjs').read_text()
        assertions = [line.strip() for line in source.splitlines()
                      if "assert.match(rows['provider requests']" in line]
        self.assertEqual(len(assertions), 1)
        code = ("const assert=require('node:assert/strict');const vm=require('node:vm');"
                "const rows=JSON.parse(process.argv[1]);try{vm.runInNewContext(process.argv[2],{assert,rows});"
                "process.stdout.write(JSON.stringify({accepted:true}));}catch{"
                "process.stdout.write(JSON.stringify({accepted:false}));}")
        result = subprocess.run(['node', '-e', code, json.dumps(rows), assertions[0]],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)['accepted']

    def row(self, value, severity='warning'):
        return {'name': 'provider requests', 'severity': severity, 'value': value}

    def test_actual_fixture_warning_badge_is_retained_and_accepted(self):
        value = 'NONE — QUILLMD_AI_MODE is fixture, not live: generation answers from the synthetic fixture.'
        rows = self.rendered([self.row(value)])
        self.assertEqual(rows['provider requests'], 'warning ' + value)
        self.assertTrue(self.accepted(rows))

    def test_optional_plain_fixture_value_and_inline_badge_spacing_are_accepted(self):
        value = 'NONE — QUILLMD_AI_MODE is fixture, not live: no provider request is sent.'
        self.assertTrue(self.accepted(self.rendered([self.row(value, '')])))
        self.assertTrue(self.accepted({'provider requests': 'warning\n' + value}))

    def test_live_missing_wrong_label_and_foreign_badge_refuse(self):
        negatives = [[], [self.row('Requests are enabled for live provider generation.')],
                     [self.row('NONE — QUILLMD_AI_MODE is live, requests may be sent.')],
                     [self.row('NONE — QUILLMD_AI_MODE is fixture-other, not the fixture profile.')],
                     [self.row('NONE — QUILLMD_AI_MODE is fixture, unavailable.', 'error')]]
        for rows in negatives:
            with self.subTest(rows=rows):
                self.assertFalse(self.accepted(self.rendered(rows)))


if __name__ == '__main__':
    unittest.main()
