"""P2 READ-HOLD (2026-11-03): the hold-only repairs of the previously reported false READYs on the Corti-only path (the
register of R8 section 1.2: D1-D10, D12, D13, D15) and R3 7.5.1's narrow evidence hold. DB-free (SimpleTestCase);
every document is synthetic and fictional, and nothing is sent.

Each register input is a permanent H4 battery row ('R8 ...', ops/gi4/battery.py), read the way the stages read it
(the analyze child, the member's answer merged, the assess child). Its movement from the base c9f20a148 is declared in
tests/fixtures/gi4/declarations/cux-hold.json ("battery", written before the code), which these tests read: a
declared row ends where the declaration says and has no violation; every other register code stays as it was, its
controls among them. The rules themselves are tested on the engine's own inputs beside each row, with the must-stay
twins the verifiers' traps name (R8 section 1.3).
"""
import json
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import context as gi_context
from studio.gi import detect
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations' / 'cux-hold.json')
                         .read_text(encoding='utf-8'))
DECLARED = {(name, code): (before, after) for name, code, before, after in DECLARATION['battery']}
HELD = 'selected/needs_clarification'
READY = 'selected/ready'
_MODULES = []


def row(name):
    """The battery row ``name`` read as ops.gi4.battery reads it."""
    if not _MODULES:
        _MODULES.append(battery.modules())
    text, codes = battery.CASES[name]
    return battery.run_row(_MODULES[0], name, text, codes, battery.R8_USER.get(name))


def state(result, code):
    p = result['proposals'][code]
    return f"{p['bucket']}/{p['status']}"


# --- the engine on a synthetic Corti answer (tests/test_services_reconcile.py's form) -------------------------------

def span(text, phrase, nth=0):
    start = -1
    for _ in range(nth + 1):
        start = text.index(phrase, start + 1)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def sel(code, *spans):
    return ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING', tuple(spans))


def run(text, codes, *, user_values=None):
    facts = gi_context.merge_user_values(gi_context.extract_context(text), user_values or {})
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    response = NormalizedResponse('replay', 'test@1', tuple(codes))
    return assess(text=text, pages=(), context=facts, routing=detect.route(text, day), normalized=response,
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def proposal(result, code):
    found = [p for p in result.proposals if p.code == code and p.bucket != 'alternative']
    assert found, f'{code} not in {[p.code for p in result.proposals]}'
    return found[0]


def check(item, check_id):
    return next(c for c in item.checks if c.id == check_id)


HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
        'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\nProcedure: Colonoscopy\n')
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
SEEN = 'A 9 mm pedunculated polyp in the sigmoid colon was seen.'
EGD_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nUpper endoscopy report (fictional)\n'
            'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\nProcedure: EGD\n'
            'The endoscope was advanced to the second portion of the duodenum.\n')
EGD_BASE = 'The endoscope was advanced to the second portion of the duodenum.'
ERCP_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nERCP report (fictional)\n'
             'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\nProcedure: ERCP\n'
             'The duodenoscope was advanced to the major papilla.\nDeep biliary cannulation was achieved.\n')
ERCP_BASE = 'Deep biliary cannulation was achieved.'


def colon(*lines):
    return HEAD + CECUM + '\n' + SEEN + '\n' + ''.join(line + '\n' for line in lines)


class RegisterRowsTests(SimpleTestCase):
    """Every register row the declaration names ends where it says, with no violation; every other register code (the
    controls, the base codes, the codes the rows were measured beside) keeps its base state, recorded beside it."""

    def assert_rows(self, prefix):
        names = [n for n in battery.CASES if n.startswith(prefix)]
        self.assertTrue(names, prefix)
        for name in names:
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    if (name, code) in DECLARED:
                        self.assertEqual(state(result, code), DECLARED[(name, code)][1])
                    else:
                        self.assertEqual(state(result, code), UNMOVED[(name, code)])
                    self.assertEqual(result['proposals'][code]['violations'], [])

    def test_d1(self):
        self.assert_rows('R8 D1 ')


# The base states of the register codes the declaration does not move (measured on c9f20a148; none may move).
UNMOVED = {
    ('R8 D1 N1 hot snare polypectomy failed', '45378'): HELD,
    ('R8 D1 N2 attempted, could not be removed', '45378'): HELD,
    ('R8 D1 N3 biopsy attempted, no tissue', '45378'): HELD,
    ('R8 D1 N4 ERCP stent placement failed', '43260'): HELD,
}


class FailedActIsNeverReleasedTests(SimpleTestCase):
    """D1 (R8 1.3, candidate_rb): the own-passage release lets the routing-era reading of the code's own passage stand
    for an act the inventory does not read only when that reading is 'performed' - never 'incomplete' - and the passage
    names no failure and no yield of nothing. Never candidate_ra (a worded reading only): the pinned control
    ("Cecal biopsies x2.", read by its section alone) must still stand."""

    PHRASINGS = (  # the verifier's 19 (meaning-r6, vm6-negation-negation-1)
        ('colon', '45385', 'Hot snare polypectomy failed.'),
        ('colon', '45385', 'Hot snare polypectomy was attempted but the polyp could not be removed.'),
        ('colon', '45385', 'Hot snare polypectomy was unsuccessful.'),
        ('colon', '45385', 'The snare polypectomy was abandoned.'),
        ('colon', '45385', 'Hot snare polypectomy was attempted without success.'),
        ('colon', '45385', 'An attempt at hot snare polypectomy failed.'),
        ('colon', '45385', 'Hot snare polypectomy: unsuccessful.'),
        ('colon', '45380', 'Cold forceps biopsy was attempted but no tissue was obtained.'),
        ('colon', '45380', 'Cold forceps biopsy failed.'),
        ('colon', '45380', 'Cold forceps biopsy was unsuccessful.'),
        ('colon', '45380', 'An attempted cold forceps biopsy yielded no tissue.'),
        ('colon', '45380', 'Biopsy was attempted without success.'),
        ('egd', '43239', 'Gastric biopsy was attempted but no tissue was obtained.'),
        ('egd', '43244', 'Variceal band ligation failed.'),
        ('ercp', '43262', 'Biliary sphincterotomy failed.'),
        ('ercp', '43274', 'Biliary stent placement failed.'),
        ('ercp', '43274', 'Stent placement was unsuccessful.'),
        ('ercp', '43264', 'Stone extraction was unsuccessful.'),
        ('ercp', '43264', 'Balloon sweep failed to clear the stone.'),
    )
    HEADS = {'colon': (HEAD + CECUM + '\n' + SEEN + '\n', '45378', CECUM), 'egd': (EGD_HEAD, '43235', EGD_BASE),
             'ercp': (ERCP_HEAD, '43260', ERCP_BASE)}

    def test_a_failed_attempted_or_unyielding_act_is_never_ready(self):
        for head, code, line in self.PHRASINGS:
            with self.subTest(line):
                text, base, base_line = self.HEADS[head]
                text += line + '\n'
                item = proposal(run(text, [sel(base, span(text, base_line)), sel(code, span(text, line))]), code)
                self.assertEqual(item.bucket, 'selected')
                self.assertNotEqual(item.status, 'ready', check(item, 'service.status').detail)
                self.assertNotIn('read from its own passage by the routing-era reader',
                                 check(item, 'service.status').detail)

    def test_controls_a_stated_act_stays_ready(self):
        for code, line in (('45385', 'The polyp was removed with a hot snare.'),
                           ('45380', 'Cold forceps biopsies were taken.')):
            with self.subTest(line):
                text = colon(line)
                item = proposal(run(text, [sel('45378', span(text, CECUM)), sel(code, span(text, line))]), code)
                self.assertEqual(item.status, 'ready')

    def test_control_the_release_still_stands_for_an_unread_phrasing(self):
        # tests/test_services_reconcile.py's pinned control, read through this rule: a passage naming the act in a
        # phrasing the documented-service reader does not parse, read 'performed' (by its section) with no failure word
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-14\n'
                'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Cecal biopsies x2.\n')
        item = proposal(run(text, [sel('45380', span(text, 'Cecal biopsies x2.'))]), '45380')
        self.assertEqual(item.status, 'ready')
        self.assertIn('read from its own passage by the routing-era reader', check(item, 'service.status').detail)
