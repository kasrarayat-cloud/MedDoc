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
    ('R8 D2 N10 antral biopsy failed', '43235'): HELD,
    ('R8 D3 N15 no polyps removed, snare header', '45378'): HELD,
    ('R8 D3 N17 polyp was not removed, snare header', '45378'): HELD,
    ('R8 D3 N16 we did not remove it, snare header', '45378'): HELD,
    ('R8 D3 release-0 none was snared', '45378'): HELD,
    ('R8 D3 release-0 at no point', '45378'): HELD,
    ('R8 D3 release-0 without resection', '45378'): HELD,
    ('R8 D3 negtime-0 biopsies not obtained (whether)', '43235'): HELD,
    ('R8 D3 declared:1 period-ended row, No checked', '45378'): HELD,
    ('R8 D4 F7N EGD biopsy line, colonoscopy denies', '45378'): HELD,
    ('R8 D4 F1 EGD snare line, colonoscopy normal', '45378'): HELD,
    ('R8 D5 F4B pathology specimen line', '45380'): READY,
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


def acts(text, day=date(2026, 10, 14)):
    """[(family, kind, status)] of every act the documented-service reader reads."""
    from studio.gi import services as gi_services
    inventory = gi_services.build(text, service_date=day, routing=detect.route(text, day))
    return [(s.family, a.kind, a.status) for s in inventory.services for a in s.acts]


class FailedActClauseTests(SimpleTestCase):
    """D2 (R8 1.3): the clause reader reads a failure word on the act's own predicate - after the mention in its clause,
    or right before it as its attribute - as a doubt (held, as "attempted" already is), never as an act done; a failure
    of something else in the sentence leaves the act to its own predicate. HEDGE_WORDS is not widened."""

    def test_d2_rows(self):
        RegisterRowsTests.assert_rows(self, 'R8 D2 ')

    def test_a_failed_act_is_not_read_as_done(self):
        for head, kind, line in (
                (EGD_HEAD, 'biopsy', 'Cold forceps biopsy of the antrum failed.'),
                (EGD_HEAD, 'biopsy', 'An unsuccessful cold forceps biopsy of the antrum was the only attempt.'),
                (HEAD + CECUM + '\n', 'snare', 'The hot snare polypectomy of the 9 mm sigmoid polyp failed.'),
                (HEAD + CECUM + '\n', 'snare', 'Hot snare polypectomy was abandoned.'),
                (ERCP_HEAD, 'stent', 'Biliary stent placement failed.')):
            with self.subTest(line):
                read = [status for _, k, status in acts(head + line + '\n') if k == kind]
                self.assertNotIn('performed', read)  # read in doubt, or not read as an act at all

    def test_controls_a_failure_of_something_else_leaves_the_act_done(self):
        for head, kind, line in (
                (EGD_HEAD, 'biopsy', 'Two cold forceps biopsies of the antrum were taken after brushing had failed.'),
                (HEAD + CECUM + '\n', 'snare', 'The polyp was removed with a hot snare because cold forceps removal '
                                               'had failed.'),
                (EGD_HEAD, 'biopsy', 'Cold forceps biopsies of the antrum were taken for failed medical therapy.')):
            with self.subTest(line):
                read = [status for _, k, status in acts(head + line + '\n') if k == kind]
                self.assertIn('performed', read, acts(head + line + '\n'))


SNARE_HEAD = HEAD.replace('Procedure: Colonoscopy', 'Procedure: Colonoscopy with hot snare polypectomy')


class DenialTiedToItsActTests(SimpleTestCase):
    """D3 (R8 1.3): a denial is read as a denial and tied to its act. (a) The routing-era reader's own negated or
    cancelled reading, or its unresolved-negation doubt, is a status signal (engine._status_signal), so a denial in the
    matched service's own report holds the code with both readings - never "not about the documented colonoscopy, so it
    does not decide". (b) The clause reader's negation forms "none (of ...) was", "at no point was" and "without" over
    the act's noun phrase, and "<act> to determine whether ... were not obtained". (c) A boxed row read as performed only
    by its section, whose own line marks a denying option, is held (the box row tie), never read as done."""

    def test_d3_rows(self):
        RegisterRowsTests.assert_rows(self, 'R8 D3 ')

    def test_the_negation_forms_are_read_as_denials(self):
        for head, kind, line in (
                (HEAD + CECUM + '\n', 'snare', 'Three polyps were seen. Of the three polyps, none was snared.'),
                (HEAD + CECUM + '\n', 'snare', 'At no point was the polyp snared.'),
                (HEAD, 'snare', 'The examination was completed without endoscopic resection of the 25 mm sigmoid polyp by '
                                'hot snare.'),
                (EGD_HEAD, 'biopsy', 'Biopsies to determine whether this represents malignancy were not obtained because '
                                     'of anticoagulation.')):
            with self.subTest(line):
                read = [status for _, k, status in acts(head + line + '\n') if k == kind]
                self.assertNotIn('performed', read, acts(head + line + '\n'))

    def test_controls_an_act_outside_the_negation_stays_done(self):
        for head, kind, line in (
                (HEAD + CECUM + '\n', 'snare', 'The 9 mm polyp was removed with a hot snare; none of the other polyps was '
                                               'larger than 3 mm.'),
                (HEAD + CECUM + '\n', 'snare', 'At no point was there bleeding after the polyp was snared.'),
                (HEAD + CECUM + '\n', 'snare', 'The examination was completed without difficulty. The 9 mm polyp was '
                                               'removed with a hot snare.'),
                (EGD_HEAD, 'biopsy', 'Biopsies were taken to determine whether this represents malignancy.'),
                (EGD_HEAD, 'biopsy', 'Biopsies to determine whether H. pylori is present were obtained from the antrum.')):
            with self.subTest(line):
                read = [status for _, k, status in acts(head + line + '\n') if k == kind]
                self.assertIn('performed', read, acts(head + line + '\n'))

    def test_controls_a_denial_of_a_finding_or_of_another_act_decides_nothing(self):
        # tests/test_services_reconcile.py's fragments control and h4-04's 43251 ("so no clip was needed" cited for a
        # snare code), read through the status signal: neither denies an act the code accounts for
        done = 'A 6 mm polyp in the sigmoid colon was removed with a hot snare.'
        for denial in ('No gastric ulcer or mass was identified.', 'The stalk base was clean and dry, so no clip was '
                                                                   'needed.'):
            with self.subTest(denial):
                text = colon(done, denial)
                item = proposal(run(text, [sel('45385', span(text, done), span(text, denial))]), '45385')
                self.assertEqual(item.status, 'ready')

    def test_controls_the_procedure_line_alone_and_a_stated_snare_stay(self):
        stated = 'The polyp was removed with a hot snare.'
        text = SNARE_HEAD + CECUM + '\n' + SEEN + '\n' + stated + '\n'
        result = run(text, [sel('45378', span(text, CECUM)), sel('45385', span(text, stated))])
        self.assertEqual(proposal(result, '45385').status, 'ready')
        # the plain procedure line cited alone, under no denial: ready as on the base
        text = SNARE_HEAD + CECUM + '\n' + SEEN + '\n'
        line = 'Procedure: Colonoscopy with hot snare polypectomy'
        result = run(text, [sel('45378', span(text, CECUM)), sel('45385', span(text, line))])
        self.assertEqual(proposal(result, '45385').status, 'ready')

    def test_the_box_row_tie(self):
        text = colon('Biopsy of the sigmoid colon. | Yes ☐ | No ☒')
        item = proposal(run(text, [sel('45378', span(text, CECUM)), sel('45380', span(text, 'Biopsy of the sigmoid '
                                                                                             'colon.'))]), '45380')
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
        # control: the same row with its "Yes" checked still reads as done
        text = colon('Biopsy of the sigmoid colon. | Yes ☒ | No ☐')
        item = proposal(run(text, [sel('45378', span(text, CECUM)), sel('45380', span(text, 'Biopsy of the sigmoid '
                                                                                             'colon.'))]), '45380')
        self.assertEqual(item.status, 'ready')


TOP = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nProcedure report (fictional)\n'
       'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\nProcedures: EGD and colonoscopy\n')


class AnotherProceduresSentenceTests(SimpleTestCase):
    """D4 (R8 1.3): the own-passage release stands only where the documented-service reader's own act-placement rule
    (services._family_for_act: the act's kind, the passage's anatomy, no report part, the services documented as done or
    in doubt today) places the act in the matched service's family alone. Fail-closed: an act no one service owns
    (F7N's "Biopsies were taken with cold forceps." in a combined EGD and colonoscopy report) is held for every family's
    code, the correct one too (its recorded cost)."""

    def test_d4_rows(self):
        RegisterRowsTests.assert_rows(self, 'R8 D4 ')

    def test_an_act_placed_by_its_anatomy_still_stands_for_its_own_service(self):
        text = (TOP + 'EGD: The gastroscope was advanced to the second portion of the duodenum.\nAntral biopsies x2.\n'
                'Colonoscopy: The colonoscope was advanced to the cecum and the examination was completed. The colon was '
                'normal.\n')
        result = run(text, [sel('43239', span(text, 'Antral biopsies x2.')),
                            sel('45380', span(text, 'Antral biopsies x2.'))])
        self.assertEqual(proposal(result, '43239').status, 'ready')
        self.assertEqual(proposal(result, '45380').status, 'needs_clarification')

    def test_control_a_single_service_report_still_releases(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-14\n'
                'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Biopsies x2.\n'
                'Plan: EGD next month.\n')
        item = proposal(run(text, [sel('45380', span(text, 'Biopsies x2.'))]), '45380')
        self.assertEqual(item.status, 'ready')  # a planned EGD owns no act of today's report


TODAY_BX = 'A 4 mm polyp in the transverse colon was biopsied with cold forceps.'


class AnotherRolesEntryTests(SimpleTestCase):
    """D5 (R8 1.3): the own-passage release never stands inside a non-physician role part (services.parts: a pathology,
    nursing, anesthesia, radiology or facility entry, cut by ROLE_HEADINGS) - reconcile already counts only physician
    and unknown acts. Not the narrower-looking repairs the trap names: limiting the release to the service's scope or
    refusing a section-default-only cue both break the pinned "Cecal biopsies x2." control (outside the scope, read by
    its section), which FailedActIsNeverReleasedTests keeps."""

    def test_d5_rows(self):
        RegisterRowsTests.assert_rows(self, 'R8 D5 ')

    def test_a_pathology_entry_never_stands_for_todays_act(self):
        for heading, line in (('PATHOLOGY ADDENDUM (specimens from the colonoscopy of 2026-09-02)',
                               'Sigmoid colon polyp, hot snare polypectomy: tubular adenoma.'),
                              ('Surgical pathology report', 'Sigmoid colon polyp, hot snare polypectomy: tubular '
                                                            'adenoma.')):
            with self.subTest(heading):
                text = HEAD + CECUM + '\n' + TODAY_BX + '\n\n' + heading + '\n' + line + '\n'
                item = proposal(run(text, [sel('45380', span(text, TODAY_BX)), sel('45385', span(text, line))]),
                                '45385')
                self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))

    def test_control_the_physicians_own_unread_phrasing_still_stands(self):
        text = HEAD + CECUM + '\n' + TODAY_BX + '\nSigmoid colon polyp, hot snare polypectomy x1.\n'
        line = 'Sigmoid colon polyp, hot snare polypectomy x1.'
        item = proposal(run(text, [sel('45380', span(text, TODAY_BX)), sel('45385', span(text, line))]), '45385')
        self.assertEqual(item.status, 'ready')
