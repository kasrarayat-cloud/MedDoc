"""Core repair and customer interface (2026-11-03), package P3 REVIEW (CORE-UX-DESIGN.md 4; R3 section 7; R8 D14).

The review overlay (studio/validation/review_view.py) re-applies the engine's own combination rules - the diagnostic-base
rule and the CMS PFS endoscopic-family check (engine.base_included, engine.base_hold, engine.endoscopic_rows,
checks.endoscopic_check: one implementation) - over the CURRENT decisions and member answers, and every gate reads it.

DB-free:
- the positive control: with no decision and no answer the overlay reproduces every stored status, check and open
  question byte for byte, over every battery row (ops/gi4/battery.py), every regression replay state
  (tests/fixtures/gi4/regression), Mara's retained Corti answer and the synthetic shapes below, each with the retrieval
  trace jobs._retrieval records;
- the rule is the engine's: what the overlay makes after a decision equals what the engine itself makes when the codes
  of the effective set are its selection;
- D14, rejection and revocation, two therapeutic siblings with one rejected, a reinstated base beside a selected
  therapeutic code, member answers (P5's data, P3's rule), the structured modifier review, migration 0009's verdict.
DB-backed (CPT_STUDIO_TEST_DB_SUFFIX): record_decision, readiness, the encounter state, coding completeness, the
operator API, the decisions endpoint's "modifiers", the carry of a chosen modifier, the report snapshot and
review.approved_items. Synthetic data only.
"""
import hashlib
import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from studio import jobs, models, reports, review, serializers
from studio.gi import context as gi_context
from studio.gi import detect
from studio.providers.corti import ADAPTER_VERSION, build_coding_request, normalize_coding_response
from studio.reference import passages as reference_passages
from studio.reference.store import InMemoryReferenceLookup, selected_codes
from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, ReferenceSourceInfo, to_jsonable
from studio.validation import checks, engine, review_view
from tests.support import pipeline_factories as pf
from tests.test_passages import file_passages

DAY = date(2026, 11, 3)
B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
HEAD = (B + 'Colonoscopy report (fictional)\nDate of service: 2026-11-03\nPlace of service: Ambulatory surgery center\n'
        'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was completed.\n')
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
SNARE = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
BIOPSY = 'A 3 mm sessile polyp in the ascending colon was biopsied with cold forceps.'
DENIED = 'A cold snare polypectomy was not performed.'
BOX = 'Cold snare polypectomy: Completed ☒ Not performed ☐'
# (text, [(code, the exact passage the synthetic Corti answer cites)])
SHAPES = {
    # R3 2.3 / R8 D14: a genuine denial the reviewer's reinstatement overrides, and the misread checked box
    'denied': (HEAD + f'A 9 mm sessile polyp in the sigmoid colon was seen. {DENIED}\n', [('45378', CECUM),
                                                                                      ('45385', DENIED)]),
    'box_misread': (HEAD + f'Findings: A 9 mm sessile polyp in the sigmoid colon.\n{BOX}\n', [('45378', CECUM),
                                                                                         ('45385', BOX)]),
    'selected': (HEAD + SNARE + '\n', [('45378', CECUM), ('45385', SNARE)]),
    'siblings': (HEAD + BIOPSY + '\n' + SNARE + '\n', [('45378', CECUM), ('45380', BIOPSY), ('45385', SNARE)]),
    'pair': (HEAD + BIOPSY + '\n' + SNARE + '\n', [('45380', BIOPSY), ('45385', SNARE)]),
    'egd': (B + 'Upper endoscopy report (fictional)\nDate of service: 2026-11-03\nPlace of service: Ambulatory surgery '
            'center\nProcedure: EGD\nThe gastroscope was advanced to the second part of the duodenum.\nCold forceps '
            'biopsies were taken from the gastric antrum.\n',
            [('43235', 'The gastroscope was advanced to the second part of the duodenum.'),
             ('43239', 'Cold forceps biopsies were taken from the gastric antrum.')]),
    # two E/M codes hold each other through the base rule (E/M profiles are base codes that cover the visit: R3 Q7)
    'em_pair': (B + 'Office visit note (fictional)\nDate of service: 2026-11-03\nPlace of service: Office\n'
                'Established patient seen in the office today for follow-up of reflux.\n'
                'Total time spent on the date of the encounter was 25 minutes.\nMedical decision making: low '
                'complexity.\n',
                [('99213', 'Established patient seen in the office today for follow-up of reflux.'),
                 ('99214', 'Total time spent on the date of the encounter was 25 minutes.')]),
}
MARA = Path(__file__).resolve().parent / 'fixtures' / 'cux' / 'mara'


def _info(key, kind, release):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=key, release=release, url='https://x',
                               sha256=hashlib.sha256(key.encode()).hexdigest(), effective_start='2026-10-01',
                               effective_end='2026-12-31', license_note='', scope_note='')


def _pfs(mult_proc, endo_base, global_days='000'):
    return {'status': 'A', 'global_days': global_days, 'mult_proc': mult_proc, 'endo_base': endo_base, 'pctc': '0'}


# Synthetic PFS rows (the endoscopic families of tests/test_passages_retrieve.py: bases 43235 and 45378); test data only.
ROWS = {'43235': _pfs('2', None), '43239': _pfs('3', '43235'), '45378': _pfs('2', None), '45380': _pfs('3', '45378'),
        '45384': _pfs('3', '45378'), '45385': _pfs('3', '45378'), '99213': _pfs('0', None, 'XXX'),
        '99214': _pfs('0', None, 'XXX')}
MUE_ROW = {'value': 1, 'mai': {'indicator': '2', 'label': 'Date of Service Edit: Policy'}, 'rationale': 'Anatomic'}
PFS_KEY, MUE_KEY = 'cms-pfs-rvu26d', 'cms-mue-practitioner-2026q4'
LOOKUP = InMemoryReferenceLookup([_info(PFS_KEY, 'cms-pfs', 'RVU26D'), _info(MUE_KEY, 'cms-mue-practitioner', '2026-Q4')],
                                 {PFS_KEY: {(code, ''): row for code, row in ROWS.items()},
                                  MUE_KEY: {(code, ''): MUE_ROW for code in ROWS}})
PASSAGES = file_passages()
BASE_Q = 'Is 45378 reported separately from 45385 for this examination?'
D14_BLOCKER = ('45378 was approved, but 45385 was reinstated: its diagnostic examination is normally included in that '
               'intervention; revoke one of the decisions')
CUSTOMER_DENYLIST = ('Corti', 'Astra', 'Fable', 'OpenAI', 'Anthropic', 'Claude', 'gpt-', 'claude-', 'participant',
                     'provider', 'vendor', 'token', 'credit', 'sha256', 'trace', 'rule id', 'request id')


def response(text, codes):
    selected = []
    for value, phrase in codes:
        start = text.index(phrase)
        selected.append(ProviderCode('selected', 'cpt', value, 'UNVERIFIED PROVIDER WORDING',
                                     (EvidenceSpan(0, start, start + len(phrase), phrase, True),)))
    return NormalizedResponse('corti', 'test@1', tuple(selected))


def assess(text, codes, *, reference=LOOKUP):
    facts = gi_context.extract_context(text)
    return engine.assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=facts, routing=detect.route(text, DAY),
                         normalized=response(text, codes), reference=reference, service_date=DAY,
                         provider_status='succeeded')


def retrieval_for(result, codes, *, passages=PASSAGES, reference=LOOKUP, day=DAY):
    """The retrieval trace the assess stage records (jobs._retrieval), the bundled CMS passages standing in for the
    imported ones."""
    with mock.patch.object(reference_passages, 'load_passages', return_value=list(passages)):
        return to_jsonable(jobs._retrieval(result, day, reference, tuple(codes)))


def services_of(result):
    return None if (result.completeness or {}).get('inventory_problems') else to_jsonable(result.services)


class Shape:
    """One engine result with its stored rows, as the overlay reads them."""

    def __init__(self, name, *, passages=PASSAGES, text=None, codes=None, result=None, retrieval=None):
        self.text, self.codes = (text, codes) if text is not None else SHAPES[name]
        self.result = result if result is not None else assess(self.text, self.codes)
        self.retrieval = (retrieval if retrieval is not None
                          else retrieval_for(self.result, [c for c, _ in self.codes], passages=passages))
        self.stored = [review_view.stored_from(p) for p in self.result.proposals]
        self.by_code = {s.code: s for s in self.stored if s.bucket != 'alternative'}

    def key(self, code):
        return self.by_code[code].key

    def view(self, decisions=None, answers=(), stored=None):
        decisions = {self.key(code) if code in self.by_code else code: value
                     for code, value in (decisions or {}).items()}
        views = review_view.review_view(stored or self.stored, decisions, services=services_of(self.result),
                                        retrieval=self.retrieval,
                                        reference_sources=to_jsonable(self.result.reference_sources),
                                        service_date=DAY, answers=answers)
        return {view.code: view for view in views.values() if view.bucket != 'alternative'}


def check(view_or_stored, check_id):
    return next((c for c in view_or_stored.checks if c['id'] == check_id), None)


def stand_in(stored):
    """A stored Proposal as review._actions reads it."""
    return SimpleNamespace(bucket=stored.bucket, status=stored.status, evidence=list(stored.evidence),
                           reinstatable=stored.reinstatable, checks=list(stored.checks), code=stored.code)


def actions(shape, code, views, decisions=None):
    current = (decisions or {}).get(code)
    return review._actions(stand_in(shape.by_code[code]), SimpleNamespace(action=current) if current else None,
                           shape.text, views[code].same_day_held, views[code])


def mara_result():
    """Mara's synthetic revision assessed with its retained Corti answer (tests/fixtures/cux/mara), offline."""
    text = (MARA / 'rev1.txt').read_text(encoding='utf-8')
    starts = [i for i in range(len(text)) if text.startswith('SYNTHETIC TEST CASE - ALL PEOPLE', i)]
    pages = tuple(PageSpan(n, start, (starts[n] - 2) if n < len(starts) else len(text))
                  for n, start in enumerate(starts, 1))
    request = build_coding_request('corti', ADAPTER_VERSION, text, DAY, settings.PROVIDER_MAX_REQUEST_BYTES)
    normalized = normalize_coding_response('corti', request, (MARA / 'corti-response.json').read_bytes())
    facts = gi_context.extract_context(text)
    _, result = jobs._assess_child(text, DAY, pages, facts, normalized, LOOKUP, 'succeeded', 'ok', ())
    jobs.release_routing_caches()
    return text, normalized, result


class OverlayPositiveControlTests(SimpleTestCase):
    """With no decision and no member answer the overlay reproduces every stored status, check and open question byte
    for byte (CORE-UX-DESIGN.md 4's positive control), on every assessment the battery and the regression replay make,
    Mara's, and the shapes here - each with the retrieval trace the assess stage records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from ops.gi4 import battery, regression, replay
        cls.calls = []
        real = jobs._assess_child

        def spy(text, day, pages, context, normalized, reference, provider_status, *rest, **kwargs):
            data, result = real(text, day, pages, context, normalized, reference, provider_status, *rest, **kwargs)
            second = rest[3] if len(rest) > 3 else None
            codes = tuple(sorted(set(selected_codes(normalized)) | set(selected_codes(second))))
            cls.calls.append((result, retrieval_for(result, codes, reference=reference, day=day), day))
            return data, result

        with mock.patch.object(jobs, '_assess_child', spy):
            battery.run()
            cls.battery_calls = len(cls.calls)
            replay.replay(regression.load_fixtures())
        cls.battery_rows = len(battery.CASES)
        cls.register_rows = sum(n.startswith('R8 ') for n in battery.CASES)
        cls.replay_calls = len(cls.calls) - cls.battery_calls
        text, normalized, result = mara_result()
        cls.calls.append((result, retrieval_for(result, selected_codes(normalized)), DAY))
        for name in SHAPES:
            shape = Shape(name)
            cls.calls.append((shape.result, shape.retrieval, DAY))

    def test_every_view_equals_its_stored_proposal_with_no_decision_and_no_answer(self):
        compared = recomputable = 0
        for index, (result, retrieval, day) in enumerate(self.calls):
            stored = [review_view.stored_from(p) for p in result.proposals]
            views = review_view.review_view(stored, {}, services=services_of(result), retrieval=retrieval,
                                            reference_sources=to_jsonable(result.reference_sources), service_date=day)
            self.assertEqual(sorted(views), sorted(s.key for s in stored))
            for s in stored:
                v = views[s.key]
                where = (index, s.key, s.code)
                compared += 1
                recomputable += any(c['id'] == 'pfs.endoscopic_base' and c['status'] != 'not_verified'
                                    for c in s.checks)
                self.assertEqual(v.status, s.status, where)
                self.assertEqual(list(v.checks), list(s.checks), where)
                self.assertEqual(list(v.questions), list(s.questions), where)
                self.assertEqual((v.added, v.released, v.recomputed, v.stale, v.withheld_by, v.blocker, v.reason),
                                 ((), (), (), (), '', '', ''), where)
                self.assertEqual(v.reinstatement_clear, any(c['id'] == 'review.reinstatement' and c['status'] == 'pass'
                                                            for c in s.checks), where)
                self.assertEqual(v.active, s.bucket == 'selected', where)
        # every battery row: the 50 round-4 rows and package P2 READ-HOLD's register rows ('R8 '), D15 among them
        self.assertEqual(self.battery_calls, self.battery_rows)
        self.assertGreater(self.register_rows, 0)
        self.assertGreater(self.replay_calls, 50)
        self.assertGreater(compared, 300)
        self.assertGreater(recomputable, 25)  # the endoscopic-family check is recomputed (and equal), not skipped

    def test_mara_is_part_of_the_control_and_carries_a_retrieved_endoscopy_trace(self):
        result, retrieval, _ = self.calls[self.battery_calls + self.replay_calls]
        self.assertEqual(sorted(p.code for p in result.proposals if p.bucket == 'selected'),
                         ['43239', '45380', '45385'])
        self.assertTrue(any(p.get('passage_key') == 'item-13-example' for entry in retrieval
                            for p in entry.get('passages', [])))


class OverlayIsTheEngineRuleTests(SimpleTestCase):
    """What the overlay makes after a decision is what the engine itself makes when the effective set is its
    selection: one rule (engine.base_included / base_hold / endoscopic_rows, checks.endoscopic_check), never a copy."""

    def test_rejecting_one_sibling_gives_the_engines_reading_of_the_other_two(self):
        three, two = Shape('siblings'), Shape('siblings', codes=[('45378', CECUM), ('45380', BIOPSY)],
                                              text=SHAPES['siblings'][0])
        after = three.view({'45385': 'reject'})
        for code in ('45378', '45380'):
            engine_row = two.by_code[code]
            self.assertEqual(after[code].status, engine_row.status, code)
            for check_id in ('services.base_included', 'pfs.endoscopic_base'):
                self.assertEqual(check(after[code], check_id), check(engine_row, check_id), (code, check_id))
            self.assertEqual(list(after[code].checks), list(engine_row.checks), code)  # every check, in order
        self.assertEqual([q['question'] for q in after['45378'].questions],
                         ['Is 45378 reported separately from 45380 for this examination?'])
        self.assertEqual(after['45378'].recomputed, ('services.base_included', 'pfs.endoscopic_base'))

    def test_a_reinstated_therapeutic_code_gives_the_engines_counterfactual(self):
        shape = Shape('denied')
        after = shape.view({'45385': 'reinstate'})
        # R3 2.3's counterfactual: engine._encounter with the reinstated 45385 counted active, then engine._proposal
        text = shape.text
        context = gi_context.extract_context(text)
        routing = detect.route(text, DAY)
        inventory = engine.gi_services.build(text, service_date=DAY, routing=routing, context_facts=context,
                                             pages=(PageSpan(1, 0, len(text)),))
        selections = [engine._select(group, text, (PageSpan(1, 0, len(text)),), routing, LOOKUP, DAY, inventory)
                      for group in engine._merge_selected(list(response(text, shape.codes).codes))]
        revived = []
        for s in selections:
            if s.code == '45385':
                found = replace(s.evaluation.match, state='performed')
                s = replace(s, evaluation=replace(s.evaluation, outcome=checks.StatusOutcome(
                    'performed', s.evaluation.outcome.decisive), match=found))
            revived.append(s)
        date_state = checks.service_date_state(context, DAY)
        encounter = engine._encounter('corti', context, routing, tuple(LOOKUP.sources()), date_state, revived)
        base = engine._proposal(revived[0], 'sel:0', encounter)
        self.assertEqual(base.code, '45378')
        for check_id in ('services.base_included', 'pfs.endoscopic_base'):
            self.assertEqual(check(after['45378'], check_id),
                             to_jsonable(next(c for c in base.checks if c.id == check_id)), check_id)
        self.assertEqual(after['45378'].status, base.status)
        self.assertEqual([q['question'] for q in after['45378'].questions], [c.question for c in base.clarifications])
        # every check, in the engine's order: the added base check stands where engine._proposal puts it
        self.assertEqual(list(after['45378'].checks), to_jsonable(list(base.checks)))


class D14Tests(SimpleTestCase):
    """R8 D14 / HARNESS.md 12.18: reinstating 45385 beside a selected 45378 holds 45378 again."""

    def setUp(self):
        self.shape = Shape('denied')

    def test_the_shape_is_d14s(self):
        before = self.shape.view()
        self.assertEqual((self.shape.by_code['45378'].bucket, before['45378'].status), ('selected', 'ready'))
        self.assertEqual((self.shape.by_code['45385'].bucket, self.shape.by_code['45385'].reinstatable),
                         ('excluded', True))
        self.assertEqual(actions(self.shape, '45378', before), ['approve', 'reject'])
        self.assertEqual(actions(self.shape, '45385', before), ['reinstate', 'confirm'])

    def test_reinstating_the_therapeutic_code_holds_the_base_and_withholds_its_approval(self):
        after = self.shape.view({'45385': 'reinstate'})
        base = after['45378']
        self.assertEqual(base.status, 'needs_clarification')
        self.assertEqual(base.withheld_by, 'services.base_included')
        self.assertEqual(base.added, ('base_included',))
        self.assertEqual([q['question'] for q in base.questions], [BASE_Q])
        self.assertEqual(check(base, 'services.base_included')['status'], 'warn')
        self.assertIn('45378 is the endoscopic base of 45385 in RVU26D, also selected',
                      check(base, 'pfs.endoscopic_base')['detail'])
        self.assertEqual(actions(self.shape, '45378', after), ['reject'])
        # the reinstated therapeutic code itself stays approvable: its own gates pass and the base rule holds bases only
        self.assertTrue(after['45385'].reinstatement_clear)
        self.assertEqual(actions(self.shape, '45385', after, {'45385': 'reinstate'}), ['approve', 'reject', 'revoke'])

    def test_an_approval_already_on_the_base_becomes_a_blocker_until_revoked(self):
        after = self.shape.view({'45378': 'approve', '45385': 'reinstate'})
        self.assertEqual(after['45378'].blocker, D14_BLOCKER)
        self.assertEqual(actions(self.shape, '45378', after, {'45378': 'approve'}), ['revoke'])
        revoked = self.shape.view({'45385': 'reinstate'})  # a revoke is no current decision
        self.assertEqual(revoked['45378'].blocker, '')
        self.assertEqual(actions(self.shape, '45378', revoked), ['reject'])

    def test_revoking_or_confirming_the_exclusion_releases_the_base(self):
        for decisions in ({}, {'45385': 'confirm'}, {'45385': 'reject'}):
            with self.subTest(decisions):
                views = self.shape.view(decisions)
                self.assertEqual((views['45378'].status, views['45378'].withheld_by, views['45378'].checks),
                                 ('ready', '', self.shape.by_code['45378'].checks))

    def test_the_misread_box_takes_the_same_path(self):
        shape = Shape('box_misread')
        if shape.by_code['45385'].bucket != 'excluded':
            self.skipTest('the reader now reads the checked box (P1/P2): D14 has no misread input here')
        after = shape.view({'45385': 'reinstate'})
        self.assertEqual((after['45378'].status, after['45378'].withheld_by), ('needs_clarification',
                                                                                'services.base_included'))


class RejectAndRevokeTests(SimpleTestCase):
    """Selection: rejecting the therapeutic code releases the base only by the engine's own rule."""

    def test_a_documented_intervention_keeps_the_base_held_after_its_code_is_rejected(self):
        shape = Shape('selected')
        stored = shape.by_code['45378']
        self.assertEqual((stored.status, stored.holds), ('needs_clarification', ('base_included',)))
        after = shape.view({'45385': 'reject'})
        base = after['45378']
        self.assertEqual(base.status, 'needs_clarification')
        self.assertEqual([q['question'] for q in base.questions],
                         ['Is 45378 reported separately from snare removal for this examination?'])
        self.assertIn('includes snare removal, which this diagnostic code does not account for',
                      check(base, 'services.base_included')['detail'])
        self.assertEqual(check(base, 'pfs.endoscopic_base')['status'], 'pass')
        self.assertEqual(base.withheld_by, '')  # the stored reading held it already
        self.assertEqual(shape.view({})['45378'].checks, stored.checks)  # revoked: the stored reading again

    def test_two_siblings_with_one_rejected(self):
        shape = Shape('siblings')
        before, after = shape.view(), shape.view({'45385': 'reject'})
        self.assertIn('45380, 45385 account for', check(before['45378'], 'services.base_included')['detail'])
        self.assertIn('45380 account for', check(after['45378'], 'services.base_included')['detail'])
        self.assertNotIn('45385', check(after['45378'], 'services.base_included')['detail'])
        self.assertEqual(after['45378'].status, 'needs_clarification')
        self.assertIsNotNone(before['45380'].modifier_review)
        self.assertIsNone(after['45380'].modifier_review)  # dropped: the other code left the effective set
        self.assertNotIn('share the endoscopic base', check(after['45380'], 'pfs.endoscopic_base')['detail'])
        self.assertFalse(after['45385'].active)
        self.assertEqual(after['45385'].checks, shape.by_code['45385'].checks)  # a rejected code's own reading stands

    def test_rejecting_both_therapeutic_codes_keeps_the_base_held_by_the_documented_acts(self):
        shape = Shape('siblings')
        after = shape.view({'45380': 'reject', '45385': 'reject'})
        self.assertEqual(after['45378'].status, 'needs_clarification')
        self.assertIn('includes forceps biopsy, snare removal', check(after['45378'], 'services.base_included')
                      ['detail'])


class StaleCheckTests(SimpleTestCase):
    def test_a_check_whose_inputs_were_not_recorded_is_kept_and_named_stale_once_the_set_moves(self):
        failed = [jobs.retrieval_failure(DAY, 'Synthetic', applied=True)]
        shape = Shape('siblings', retrieval=failed)
        self.assertEqual(shape.view()['45380'].stale, ())  # nothing moved: the stored check is current
        after = shape.view({'45385': 'reject'})
        self.assertEqual(after['45380'].stale, ('pfs.endoscopic_base',))
        self.assertEqual(check(after['45380'], 'pfs.endoscopic_base'), check(shape.by_code['45380'],
                                                                             'pfs.endoscopic_base'))
        self.assertIn('services.base_included', after['45378'].recomputed)  # the base rule needs no retrieval


class ReinstatedBaseTests(SimpleTestCase):
    """A reinstated base beside a selected therapeutic code (R3 2.3, last bullet): the base rule reads it too."""

    @staticmethod
    def excluded_base_shape(*, keep_service=True):
        text, codes = SHAPES['selected']
        real = engine._select

        def select(group, *args, **kwargs):
            s = real(group, *args, **kwargs)
            if s.code != '45378':
                return s
            # the engine's own excluded reading of the base (both readers agreeing it was not done today)
            match = replace(s.evaluation.match, state='not_performed', reason='act_denied') if keep_service else None
            return replace(s, evaluation=replace(s.evaluation, match=match, outcome=checks.StatusOutcome(
                'not_performed', s.evaluation.outcome.decisive)))

        with mock.patch.object(engine, '_select', select):
            result = assess(text, codes)
        return Shape('selected', result=result)

    def test_the_constructed_shape_is_an_excluded_reinstatable_base(self):
        shape = self.excluded_base_shape()
        self.assertEqual((shape.by_code['45378'].bucket, shape.by_code['45378'].reinstatable), ('excluded', True))
        self.assertEqual(check(shape.by_code['45378'], 'review.reinstatement')['status'], 'pass')
        self.assertEqual(check(shape.by_code['45385'], 'pfs.endoscopic_base')['status'], 'pass')

    def test_reinstating_the_base_holds_it_beside_the_selected_therapeutic_code(self):
        for keep_service in (True, False):
            with self.subTest(service_recorded=keep_service):
                shape = self.excluded_base_shape(keep_service=keep_service)
                after = shape.view({'45378': 'reinstate'})
                base = after['45378']
                self.assertTrue(base.active)
                self.assertEqual(base.withheld_by, 'services.base_included')
                self.assertFalse(base.reinstatement_clear)
                self.assertEqual([q['question'] for q in base.questions], [BASE_Q])
                self.assertEqual(check(base, 'review.reinstatement')['status'], 'warn')
                self.assertIn(BASE_Q, check(base, 'review.reinstatement')['detail'])
                self.assertEqual(actions(shape, '45378', after, {'45378': 'reinstate'}), ['reject', 'revoke'])
                # the therapeutic code's endoscopic-family check now names the reinstated base, as the engine's does
                self.assertEqual(check(after['45385'], 'pfs.endoscopic_base'),
                                 check(Shape('selected').by_code['45385'], 'pfs.endoscopic_base'))
                self.assertEqual(check(base, 'services.base_included'),
                                 check(Shape('selected').by_code['45378'], 'services.base_included'))

    def test_an_approval_of_the_reinstated_base_blocks_once_the_therapeutic_code_returns(self):
        shape = self.excluded_base_shape()
        rejected = shape.view({'45378': 'reinstate', '45385': 'reject'})
        self.assertEqual(rejected['45378'].withheld_by, 'services.base_included')  # the snare act is documented
        self.assertEqual(shape.view({'45378': 'approve', '45385': 'reject'})['45378'].blocker,
                         '45378 was approved, but the documented colonoscopy includes snare removal, which this '
                         'diagnostic code does not account for; revoke the approval')


class MemberAnswerTests(SimpleTestCase):
    """P5's data, P3's rule: a code's open question answered not documented / cannot confirm makes it
    detail_unavailable until the answer is revoked; a service's answer closes that question only."""

    def test_an_answered_base_question_excludes_the_base_and_the_others_read_without_it(self):
        shape = Shape('selected')
        answers = [{'code': '45378', 'family': 'gi.colonoscopy', 'fact': 'base_included', 'value': 'cannot_confirm'}]
        views = shape.view(answers=answers)
        base = views['45378']
        self.assertEqual((base.status, base.reason, base.active, base.questions, base.answer),
                         ('excluded', 'detail_unavailable', False, (), 'cannot_confirm'))
        self.assertEqual(actions(shape, '45378', views), [])
        self.assertEqual(views['45385'].status, 'ready')
        self.assertEqual(check(views['45385'], 'pfs.endoscopic_base')['status'], 'pass')  # 45378 left the set
        approved = shape.view({'45378': 'approve'}, answers=answers)['45378']
        self.assertEqual(approved.blocker, '45378 was approved, but a detail it needs was answered as cannot be '
                                           'confirmed: revoke the approval')

    def test_an_answer_binds_to_its_code_family_and_fact_only(self):
        shape = Shape('selected')
        for answer in ({'code': '45385', 'family': 'gi.colonoscopy', 'fact': 'base_included', 'value': 'cannot_confirm'},
                       {'code': '45378', 'family': 'gi.colonoscopy', 'fact': 'extent', 'value': 'not_documented'},
                       {'code': '45378', 'family': 'gi.egd', 'fact': 'base_included', 'value': 'not_documented'},
                       {'code': '45378', 'family': 'gi.colonoscopy', 'fact': 'base_included', 'value': 'other'},
                       {'code': '', 'family': 'gi.colonoscopy', 'fact': 'base_included', 'value': 'not_documented'}):
            with self.subTest(answer):
                views = shape.view(answers=[answer])
                self.assertEqual((views['45378'].status, views['45378'].reason), ('needs_clarification', ''))

    def test_an_answer_to_a_question_that_is_not_asked_changes_nothing(self):
        shape = Shape('denied')  # 45378 is not held: no base question is asked
        views = shape.view(answers=[{'code': '45378', 'family': 'gi.colonoscopy', 'fact': 'base_included',
                                     'value': 'not_documented'}])
        self.assertEqual((views['45378'].status, views['45378'].reason), ('ready', ''))

    def test_removal_is_monotone_where_two_codes_hold_each_other(self):
        shape = Shape('em_pair')
        self.assertEqual([shape.by_code[c].holds for c in ('99213', '99214')], [('base_included',)] * 2)
        one = [{'code': '99213', 'family': 'gi.office_em', 'fact': 'base_included', 'value': 'not_documented'}]
        views = shape.view(answers=one)
        self.assertEqual(views['99213'].reason, 'detail_unavailable')
        self.assertEqual((views['99214'].status, views['99214'].released), ('ready', ('base_included',)))
        both = one + [{'code': '99214', 'family': 'gi.office_em', 'fact': 'base_included', 'value': 'cannot_confirm'}]
        views = shape.view(answers=both)
        self.assertEqual([views[c].reason for c in ('99213', '99214')], ['detail_unavailable'] * 2)


class ModifierReviewTests(SimpleTestCase):
    """The structured separate-lesion modifier review, recomputed over the effective set (CORE-UX-DESIGN.md 4)."""

    def test_two_codes_on_separate_lesions_offer_59_or_xs_with_the_dated_claims_manual_example(self):
        shape = Shape('pair')
        views = shape.view()
        for code, other in (('45380', '45385'), ('45385', '45380')):
            review_ = views[code].modifier_review
            self.assertEqual(review_['kind'], 'distinct_lesion')
            self.assertEqual(review_['codes'], [code, other])
            self.assertEqual(review_['options'], ['59', 'XS'])
            self.assertEqual(sorted(review_['lesions']), sorted([code, other]))
            source = review_['sources'][0]
            self.assertEqual((source['key'], source['release'], source['passage_key']),
                             ('cms-claims-manual-100-04-ch12', 'Rev. 13753; Issued: 05-07-26', 'item-13-example'))
            self.assertTrue(source['title'].startswith('Medicare Claims Processing Manual (Pub. 100-04), Chapter 12'))
            self.assertIn('item 13, example', source['section'])
            text = review_['text']
            self.assertIn('Pub. 100-04, chapter 12, section 40.6.C, item 13', text)
            self.assertIn('Whether an NCCI procedure-to-procedure edit pairs these codes', text)
            self.assertIn('No modifier is added unless the reviewer chooses one.', text)
            self.assertIn('ascending colon', text)
            self.assertIn('sigmoid colon', text)
            for word in CUSTOMER_DENYLIST:
                self.assertNotIn(word.lower(), text.lower(), word)
            self.assertEqual(views[code].modifiers, ())  # never prefilled

    def test_the_review_is_dropped_when_the_other_code_leaves_the_effective_set(self):
        shape = Shape('pair')
        for decisions in ({'45385': 'reject'},):
            views = shape.view(decisions)
            self.assertIsNone(views['45380'].modifier_review)
            self.assertIsNone(views['45385'].modifier_review)
        answered = shape.view(answers=[{'code': '45385', 'family': 'gi.colonoscopy', 'fact': 'x', 'value':
                                        'not_documented'}])
        self.assertIsNotNone(answered['45380'].modifier_review)  # no such question: nothing left the set

    def test_no_citation_without_the_retrieved_passage_or_for_another_pair(self):
        bare = Shape('pair', passages=[])
        review_ = bare.view()['45380'].modifier_review
        self.assertEqual(review_['sources'], [])
        self.assertNotIn('Pub. 100-04', review_['text'])
        shape = Shape('pair')
        renamed = [replace(s, code='45384') if s.code == '45380' else s for s in shape.stored]
        views = review_view.review_view(renamed, {}, services=services_of(shape.result), retrieval=shape.retrieval,
                                        reference_sources=to_jsonable(shape.result.reference_sources),
                                        service_date=DAY)
        hot = next(v for v in views.values() if v.code == '45384')
        self.assertEqual(hot.modifier_review['sources'], [])  # the example bills 45380 with 45385, nothing else

    def test_an_approval_whose_modifier_the_view_no_longer_offers_is_a_blocker(self):
        shape = Shape('pair')
        chosen = review_view.Decided('approve', ('XS',))
        self.assertEqual(shape.view({'45380': chosen})['45380'].blocker, '')
        self.assertEqual(shape.view({'45380': chosen})['45380'].modifiers, ('XS',))
        self.assertEqual(shape.view({'45380': chosen, '45385': 'reject'})['45380'].blocker,
                         '45380 was approved with modifier XS, but the separate-lesion modifier review no longer '
                         'applies to it; revoke the approval and decide it again')


class SummaryTests(SimpleTestCase):
    def test_one_sentence_of_cpt_studios_own_reading(self):
        views = Shape('pair').view()
        self.assertTrue(views['45385'].summary.startswith('The colonoscopy documents snare removal'))
        self.assertIn('sigmoid colon', views['45385'].summary)
        self.assertTrue(views['45385'].summary.endswith('.'))
        self.assertTrue(views['45380'].summary.startswith('The colonoscopy documents forceps biopsy'))
        denied = Shape('denied').view()
        self.assertEqual(denied['45378'].summary, 'The colonoscopy is documented on the date of service.')
        self.assertEqual(denied['45385'].summary, 'The document states the snare removal was not done.')
        for view in list(views.values()) + list(denied.values()):
            for word in CUSTOMER_DENYLIST:
                self.assertNotIn(word.lower(), view.summary.lower(), (view.code, word))


class MigrationTests(SimpleTestCase):
    def test_0009_cux_review_is_additive_for_the_installer(self):
        from ops import install
        source = (Path(__file__).resolve().parents[1] / 'studio' / 'migrations' / '0009_cux_review.py').read_text()
        verdict = install.migration_verdict(source)
        self.assertTrue(verdict['safe'], verdict)
        self.assertIn("decision.modifiers: NOT NULL, given a database default by this migration's SQL", verdict['why'])
        self.assertEqual(models.Decision._meta.get_field('modifiers').get_default(), [])


# --- DB-backed: the hooks -------------------------------------------------------------------------------------------

def persist(name, *, passages=PASSAGES):
    """An encounter whose current, final assessment is the engine's own result for SHAPES[name], persisted through
    review.persist_assessment with the retrieval trace the assess stage records."""
    text, codes = SHAPES[name]
    s = pf.scenario(text=text)
    facts = {fact_name: to_jsonable(fact) for fact_name, fact in gi_context.extract_context(text).items()}
    ctx = pf.context(s.encounter, s.revision, fact_values=facts)
    result = assess(text, codes)
    assessment = review.persist_assessment(
        encounter=s.encounter, revision=s.revision, context=ctx, routing_run=pf.routing(s.revision),
        provider_run=pf.provider_run(s.encounter, s.revision), result=result,
        retrieval=retrieval_for(result, [c for c, _ in codes], passages=passages))
    s.encounter.refresh_from_db()
    s.assessment = assessment
    s.result = result
    return s


def key_of(s, code):
    return s.encounter.current_assessment.proposals.get(code=code).key


def decide(s, code, action, user=None, modifiers=(), note=''):
    user = user or s.reviewer
    s.encounter.refresh_from_db()
    proposal = s.encounter.current_assessment.proposals.get(code=code)
    return review.record_decision(encounter=s.encounter, proposal=proposal, action=action, user=user,
                                  membership=s.membership(user), note=note,
                                  acknowledgement=review.ACKNOWLEDGEMENTS[user.actor_kind] if action == 'approve' else '',
                                  modifiers=modifiers)


def allowed(s, code):
    s.encounter.refresh_from_db()
    assessment = s.encounter.current_assessment
    return review.allowed_actions(assessment.proposals.get(code=code), assessment, s.membership(s.reviewer))


class OverlayHooksTests(TestCase):
    def test_d14_through_record_decision_readiness_state_api_and_reports(self):
        s = persist('denied')
        self.assertEqual(allowed(s, '45378'), ['approve', 'reject'])
        decide(s, '45378', 'approve')
        self.assertEqual(review.readiness(s.encounter)['blockers'],
                         ['45385 was excluded by a documentation check: confirm the exclusion or reinstate it'])
        decide(s, '45385', 'reinstate', note='Synthetic: the snare was done.')
        ready = review.readiness(s.encounter)
        self.assertIn(D14_BLOCKER, ready['blockers'])
        self.assertFalse(ready['reviewed'])
        self.assertEqual(allowed(s, '45378'), ['revoke'])
        with self.assertRaises(reports.ReportNotReady):
            reports.snapshot(s.encounter, reports.REVIEWED)
        decide(s, '45378', 'revoke')
        self.assertEqual(allowed(s, '45378'), ['reject'])
        with self.assertRaisesRegex(ValidationError, 'not available'):
            decide(s, '45378', 'approve')
        s.encounter.refresh_from_db()
        self.assertEqual(s.encounter.state, 'needs_clarification')
        assessment = s.encounter.current_assessment
        current = review.current_decisions(assessment)
        item = serializers._proposal_json(assessment.proposals.get(code='45378'), current, assessment,
                                          s.membership(s.reviewer), {})
        self.assertEqual((item['status'], item['allowed_actions'], item['approve_withheld_by']),
                         ('needs_clarification', ['reject'], 'services.base_included'))
        self.assertIn('services.base_included', [c['id'] for c in item['checks']])
        view = review.effective_view(assessment)[key_of(s, '45378')]
        self.assertEqual((view.added, [q['question'] for q in view.questions]), (('base_included',), [BASE_Q]))
        coding = review.coding_completeness(s.encounter)
        self.assertIn('1 open question', coding['reasons'])
        draft = reports.snapshot(s.encounter, reports.DRAFT)
        listed = {i['code']: i for i in draft['proposals']}
        self.assertEqual(listed['45378']['status'], 'needs_clarification')
        self.assertEqual(listed['45378']['recomputed'], ['services.base_included', 'pfs.endoscopic_base'])
        self.assertIn(BASE_Q, [q['question'] for q in draft['clarifications']])
        self.assertIn('Recomputed over the current review decisions: services.base_included, pfs.endoscopic_base',
                      reports.render_txt(draft).decode())
        decide(s, '45378', 'reject', note='Synthetic: included in the snare removal.')
        decide(s, '45385', 'approve', user=s.agent)
        ready = review.readiness(s.encounter)
        self.assertTrue(ready['reviewed'], ready)
        snap = reports.snapshot(s.encounter, reports.REVIEWED)
        self.assertEqual([i['code'] for i in snap['proposals'] if i['list'] == 'approved'], ['45385'])
        items = review.approved_items(s.encounter.current_assessment)
        self.assertEqual([i['code'] for i in items], ['45385'])
        item = items[0]
        self.assertEqual((item['units'], item['modifiers'], item['approver_kind'], item['reinstated']),
                         (1, [], 'agent', True))
        self.assertIn('(automated agent)', item['approved_by'])
        self.assertEqual(item['summary'], 'The document states the snare removal was not done.')
        # the reviewer's reinstatement overrides CPT Studio's reading; the denial it cites shows no snare, so it is never
        # given as the approved item's evidence (CORE-UX-DESIGN.md 7: never a passage that does not support)
        self.assertEqual(item['evidence'], [])
        self.assertTrue(item['decided_at'])

    def test_no_decision_reads_every_stored_row_through_the_api_and_the_snapshot(self):
        s = persist('siblings')
        assessment = s.encounter.current_assessment
        current = review.current_decisions(assessment)
        rows = {c.pk: c for c in assessment.clarifications.filter(state=models.Clarification.OPEN)}
        snap = reports.snapshot(s.encounter, reports.DRAFT)
        listed = {i['code']: i for i in snap['proposals']}
        for proposal in assessment.proposals.all():
            item = serializers._proposal_json(proposal, current, assessment, s.membership(s.reviewer), {})
            self.assertEqual((item['status'], item['checks']), (proposal.status, proposal.checks), proposal.code)
            self.assertEqual([c['id'] for c in listed[proposal.code]['checks']],
                             [c['id'] for c in proposal.checks])
            self.assertNotIn('recomputed', listed[proposal.code])
        self.assertEqual(sorted(q['id'] for q in snap['clarifications']), sorted(str(pk) for pk in rows))
        self.assertEqual(review.open_questions_of(assessment), [
            {'id': str(r.pk), 'scope': r.scope, 'family': r.family, 'fact': r.fact, 'question': r.question,
             'reason': r.reason, 'code': r.proposal.code if r.proposal_id else None}
            for r in assessment.clarifications.filter(state=models.Clarification.OPEN).order_by('created_at', 'pk')])

    def test_with_no_decision_every_reader_equals_the_stored_rows_reading(self):
        # The positive control of every DB-backed reader: with no decision and no answer, reading through the overlay
        # gives exactly what reading the stored rows alone gives (review.effective_view answering {} makes every hook
        # fall back to the stored proposal - the base release's reading): both report renders and the snapshot digest,
        # readiness, coding completeness, the encounter state and the operator proposal JSON (its new keys aside).
        new_keys = ('modifier_review', 'modifiers', 'review_view')
        for name in ('siblings', 'selected', 'pair', 'egd', 'denied', 'em_pair'):
            with self.subTest(name):
                s = persist(name)
                assessment = s.encounter.current_assessment
                membership = s.membership(s.reviewer)

                def read():
                    current = review.current_decisions(assessment)
                    snap = reports.snapshot(s.encounter, reports.DRAFT)
                    return {'digest': reports.snapshot_digest(snap), 'txt': reports.render_txt(snap),
                            'csv': reports.render_csv(snap), 'readiness': review.readiness(s.encounter),
                            'coding': review.coding_completeness(s.encounter),
                            'state': review._derive_state(s.encounter),
                            'proposals': [{k: v for k, v in serializers._proposal_json(p, current, assessment,
                                                                                         membership, {}).items()
                                           if k not in new_keys} for p in assessment.proposals.all()]}

                with mock.patch('django.utils.timezone.now', return_value=assessment.created_at):
                    through = read()
                    with mock.patch.object(review, 'effective_view', return_value={}):
                        stored = read()
                self.assertEqual(through, stored)

    def test_the_modifier_choice_is_one_of_59_or_xs_on_an_approval_the_view_offers_it_for(self):
        s = persist('pair')
        for bad in (['59', 'XS'], ['XX'], ['xs'], 'XS', [59], ['XS', 'XS']):
            with self.subTest(bad):
                with self.assertRaises(review.ModifierRefused):
                    decide(s, '45380', 'approve', modifiers=bad)
        with self.assertRaises(review.ModifierRefused):
            decide(s, '45380', 'reject', modifiers=['XS'])
        self.assertFalse(models.Decision.objects.filter(encounter=s.encounter).exists())
        decision = decide(s, '45380', 'approve', modifiers=['XS'], note='Synthetic: separate lesion.')
        decision.refresh_from_db()
        self.assertEqual(decision.modifiers, ['XS'])
        audit = models.AuditEvent.objects.filter(encounter=s.encounter, event='decision.recorded').last()
        self.assertEqual(audit.data.get('modifiers'), ['XS'])
        items = review.approved_items(s.encounter.current_assessment)
        self.assertEqual([(i['code'], i['modifiers'], i['note']) for i in items],
                         [('45380', ['XS'], 'Synthetic: separate lesion.')])
        self.assertEqual([(span['text'], span['origin']) for span in items[0]['evidence']], [(BIOPSY, 'cited')])
        for span in items[0]['evidence']:
            self.assertEqual(s.revision.text[span['start']:span['end']], span['text'])
            self.assertEqual((span['start'], span['page']), (s.revision.text.index(BIOPSY), 1))
        self.assertEqual((items[0]['units'], items[0]['approver_kind'], items[0]['reinstated']), (1, 'human', False))
        self.assertEqual(items[0]['approved_by'], s.reviewer.label())
        self.assertTrue(items[0]['summary'].startswith('The colonoscopy documents forceps biopsy'))
        self.assertEqual(items[0]['decided_at'], decision.created_at.isoformat())
        snap = reports.snapshot(s.encounter, reports.DRAFT)
        self.assertIn('Modifier chosen by the reviewer: XS (not validated against NCCI procedure-to-procedure edits '
                      'or payer modifier policy)', reports.render_txt(snap).decode())
        decide(s, '45385', 'reject')
        self.assertIn('45380 was approved with modifier XS, but the separate-lesion modifier review no longer applies '
                      'to it; revoke the approval and decide it again', review.readiness(s.encounter)['blockers'])
        self.assertEqual(review.approved_items(s.encounter.current_assessment), [])

    def test_no_modifier_where_no_review_is_offered(self):
        s = persist('denied')
        with self.assertRaisesRegex(ValidationError, 'No modifier review is offered for 45378'):
            decide(s, '45378', 'approve', modifiers=['XS'])
        decision = decide(s, '45378', 'approve')  # approving with no modifier is always allowed
        self.assertEqual(decision.modifiers, [])

    def test_a_carried_approval_keeps_its_chosen_modifier(self):
        s = persist('pair')
        decide(s, '45380', 'approve', modifiers=['59'])
        facts = {name: to_jsonable(fact) for name, fact in gi_context.extract_context(s.revision.text).items()}
        ctx = pf.context(s.encounter, s.revision, fact_values=facts, user_values={'setting': 'asc'})
        review.persist_assessment(encounter=s.encounter, revision=s.revision, context=ctx,
                                  routing_run=pf.routing(s.revision), provider_run=pf.provider_run(s.encounter,
                                                                                                   s.revision),
                                  result=s.result, retrieval=s.assessment.retrieval)
        s.encounter.refresh_from_db()
        carried = review.current_decisions(s.encounter.current_assessment)
        decision = next(iter(carried.values()))
        self.assertTrue(decision.carried_from_id)
        self.assertEqual((decision.proposal.code, decision.modifiers), ('45380', ['59']))

    def test_the_decisions_endpoint_accepts_modifiers(self):
        s = persist('pair')
        self.client.force_login(s.reviewer)
        url = f'/api/encounters/{s.encounter.pk}/decisions'
        proposal = str(s.encounter.current_assessment.proposals.get(code='45380').pk)
        body = {'proposal_id': proposal, 'action': 'approve', 'acknowledgement': review.ACKNOWLEDGEMENTS['human']}
        for bad, status in ((['59', 'XS'], 400), ('XS', 400), (['ZZ'], 400)):
            with self.subTest(bad):
                reply = self.client.post(url, data=json.dumps({**body, 'modifiers': bad}),
                                         content_type='application/json')
                self.assertEqual(reply.status_code, status, reply.content)
        reply = self.client.post(url, data=json.dumps({**body, 'modifiers': ['XS']}), content_type='application/json')
        self.assertEqual(reply.status_code, 201, reply.content)
        # the customer decision shape (customer_api.decision_response, CORE-UX-DESIGN.md 7): the chosen modifier is on
        # the decision the code row shows
        self.assertEqual(reply.json()['decision']['modifiers'], ['XS'])
        other = persist('denied')
        self.client.force_login(other.reviewer)
        reply = self.client.post(f'/api/encounters/{other.encounter.pk}/decisions', data=json.dumps({
            'proposal_id': str(other.encounter.current_assessment.proposals.get(code='45378').pk), 'action': 'approve',
            'acknowledgement': review.ACKNOWLEDGEMENTS['human'], 'modifiers': ['XS']}), content_type='application/json')
        self.assertEqual(reply.status_code, 409, reply.content)

    def test_an_approval_the_same_day_gate_holds_is_no_approved_item(self):
        em_gate = pf.check('em.same_day_if_reinstated', 'warn', 'Separately identifiable E/M if a procedure is reinstated')
        marker = pf.check('review.same_day_em', 'warn', 'Same-day E/M after reinstatement')
        reinstatement = pf.check('review.reinstatement', 'pass', 'Approval after reinstatement')
        s = pf.scenario()
        pf.assess(s.encounter, pf.result(
            pf.proposal('sel:0', '99213', [pf.DATE_PASSAGE], checks=pf.standard_checks() + (em_gate,)),
            pf.proposal('exc:0', '46221', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                        checks=pf.standard_checks() + (reinstatement, marker))))
        s.decide('sel:0', 'approve')
        self.assertEqual([i['code'] for i in review.approved_items(s.encounter.current_assessment)], ['99213'])
        s.decide('exc:0', 'reinstate')
        s.decide('exc:0', 'approve')
        self.assertIn('99213 needs a separately identifiable E/M: 46221 was reinstated as a same-day procedure',
                      review.readiness(s.encounter)['blockers'])
        self.assertEqual([i['code'] for i in review.approved_items(s.encounter.current_assessment)], ['46221'])

    def test_member_answers_reach_every_gate(self):
        s = persist('selected')
        answers = [{'code': '45378', 'family': 'gi.colonoscopy', 'fact': 'base_included', 'value': 'not_documented'}]
        with mock.patch.object(review, '_member_answers', return_value=answers):
            self.assertEqual(allowed(s, '45378'), [])
            ready = review.readiness(s.encounter)
            self.assertEqual(ready['blockers'], ['45385 has no decision'])
            decide(s, '45385', 'approve')
            self.assertTrue(review.readiness(s.encounter)['reviewed'])
            snap = reports.snapshot(s.encounter, reports.REVIEWED)
            listed = {i['code']: i['list'] for i in snap['proposals']}
            self.assertEqual(listed, {'45378': 'excluded', '45385': 'approved'})
            self.assertEqual([i['code'] for i in review.approved_items(s.encounter.current_assessment)], ['45385'])
            coding = review.coding_completeness(s.encounter)
            self.assertIn('45378 excluded: a needed detail was answered as not documented or not confirmable',
                          coding['reasons'])
            self.assertNotIn('1 open question', coding['reasons'])
        self.assertFalse(review.readiness(s.encounter)['reviewed'])  # revoked (no answer): 45378 waits again
