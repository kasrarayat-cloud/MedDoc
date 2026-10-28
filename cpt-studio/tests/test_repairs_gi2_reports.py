"""CPT Studio GI round 2 (session 7c8d38da, 2026-10-28), repair "reports": what the bounded second review's merge and
check say (engine._second_review, engine._second_review_check), and where the Suggestions screen and the reports say
that a code came from it (app.js candidateSection, reports._rejected_section). Found by this round's EUS investigation
(eus2: F1, F2, F4, F5) and by the provider.second_review sentence seen live on 2026-10-28. Synthetic data only; the
provider is an in-process fake (no network).

- F1 (engine._second_review): a code the second review SELECTED with no exact passage, of a family whose whole
  documented service the primary proposals left unresolved, was kept as an alternative "not added as a proposal: the
  act it accounts for is not documented as done in the service left unresolved" - a statement about the document,
  though nothing of it was read (an EUS documented as performed with its fine-needle sampling; a 43242 whose only
  passage was three characters off). It states its own reason: no exact source evidence. The same branch said so of
  an act the document states both as done and as not done (a conflict the assessment records): it says that.
- F2 (engine._second_review_check): the second review's own normaliser problems and the codes it returned that cannot
  be listed were reported nowhere unless its response was refused whole; the primary's are provider.problems and
  provider.unlisted warnings. They are worded in provider.second_review, a warning, in the same words.
- WORDING (engine._second_review_check): "A second review limited to the passages of endoscopic ultrasound (documented
  as performed) has no supported proposal added no proposal for them." worded an unresolved item's label - a clause, or
  a phrase - into the sentence as a noun phrase, as "which accounts for <label> and is added" did. Every list of items
  is quoted as items: after a colon, ending its sentence; past four asked items the rest are counted.
- F4 (app.js candidateSection): an alternative the second review listed was drawn on the Suggestions screen like the
  primary's, while the TXT ("second-review alternative") and the CSV (proposal_origin) say where it came from.
- F5 (reports._rejected_section): a second-review code the reviewer rejected lost the Origin line the approved and
  undecided lists print.
"""
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from studio import models
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode, RawExchange
from studio.validation import checks
from studio.validation.engine import MAX_LISTED_CODE, NO_EVIDENCE
from tests.test_pipeline_api import drain
from tests.test_repairs_7c8_p1reports import (BIOPSY, COLONOSCOPY, COLONOSCOPY_THREE, DILATION, SNARE, Harness, page,
                                              section)
from tests.test_repairs_7c8_p2reports import EUS_WITH_EGD, FNA, unresolved_items
from tests.test_services_reconcile import run, sel, span
from tests.test_services_second_review import TwoPassProvider, ask

SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
EUS_ITEM = 'endoscopic ultrasound (documented as performed) has no supported proposal'
NOT_DONE = 'the act it accounts for is not documented as done in the service left unresolved'
NOT_ADDED = 'it accounts for no documented service or act the primary proposals left unresolved'
SELECTED_NOT_ADDED = 'Selected by the provider in the bounded second review, but not added as a proposal: '
CANNOT_APPROVE = ' Candidates and alternatives cannot be approved.'
ORIGIN = 'Origin: selected by the provider in the bounded second review of an unresolved service'
BOTH_WAYS = 'the document states the act it accounts for both as done and as not done (both are kept; neither is chosen)'

COLONOSCOPY_BASE = (SYNTHETIC + 'Colonoscopy report (fictional)\nDate of service: 2026-10-16\nProcedure: Colonoscopy\n'
                    'The colonoscope was advanced to the cecum and the examination was completed.\n')
CECUM = 'The colonoscope was advanced to the cecum'
NO_BIOPSY_DOCUMENTED = COLONOSCOPY_BASE + 'The colon was normal.\n'
BIOPSY_BOTH_WAYS = COLONOSCOPY_BASE + 'Cold forceps biopsies were taken from the sigmoid colon.\nNo biopsies were taken.\n'
COLONOSCOPY_ITEM = 'colonoscopy (documented as performed) has no supported proposal'

PROBLEMS = ('codes[1] has no code; it was dropped.', 'codes[2] is not an object; it was dropped.')
OVERLONG = '43242-PROVIDER-WORDING'  # a "code" too long to list: never quoted anywhere


def second_review(*codes, problems=(), refused=False):
    return NormalizedResponse('replay', 'test@1', tuple(codes), problems=tuple(problems), refused=refused)


def shifted(text, quote, by=3):
    """``quote``'s passage with its offsets ``by`` characters off: not exact in the text."""
    good = span(text, quote)
    return EvidenceSpan(0, good.start + by, good.end + by, quote, True)


def merged(text, primary, second, items):
    """The assessment of ``text`` with ``primary`` selections and the second review ``second`` asked about ``items``."""
    return run(text, list(primary), second=second, second_scope={'items': list(items)})


def review_check(result):
    (found,) = [c for c in result.encounter_checks if c.id == 'provider.second_review']
    return found


def alternatives(result, code):
    return [p for p in result.proposals if p.code == code and p.bucket == 'alternative']


def assert_items_quoted(test, detail, labels):
    """Every occurrence of every label in ``detail`` is an item of a list - after ': ' or '; ', and followed by '; ', a
    full stop or ' and N more' - never worded into a sentence as a noun phrase."""
    for label in labels:
        at = detail.find(label)
        test.assertNotEqual(at, -1, (label, detail))
        while at != -1:
            before, after = detail[:at], detail[at + len(label):]
            test.assertTrue(before.endswith((': ', '; ')), (label, before[-60:]))
            test.assertTrue(after == '.' or after.startswith(('. ', '; ')) or re.match(r' and \d+ more\.', after),
                            (label, after[:60]))
            at = detail.find(label, at + 1)


# --- F1: a second-review code with no exact passage states its own reason ---------------------------------------------

class ASecondReviewCodeWithoutAnExactPassageStatesItsOwnReasonTests(SimpleTestCase):
    """F1. An EUS documented as performed with its fine-needle sampling, the primary proposals leaving it unresolved; the
    second review selects 43242 - the code the source supports - but cites no passage that is exact in the text. Nothing
    of the document was read for it, so the only true reason it is not added is that: never "the act it accounts for is
    not documented as done", which the document contradicts."""

    def test_no_exact_passage_is_said_never_not_documented_as_done(self):
        text = EUS_WITH_EGD
        self.assertEqual([u[3] for u in unresolved_items(run(text, []))], [EUS_ITEM])
        for name, passages in (('offsets three characters off', (shifted(text, FNA),)),
                               ('only the date context cited', (EvidenceSpan(1, 0, 10, 'Date of se', True),)),
                               ('no passage', ())):
            with self.subTest(name):
                result = merged(text, [], second_review(sel('43242', *passages)), [EUS_ITEM])
                (listed,) = alternatives(result, '43242')
                self.assertEqual(listed.exclusion_reason, f'{SELECTED_NOT_ADDED}{NO_EVIDENCE}.{CANNOT_APPROVE}')
                self.assertNotIn('not documented as done', listed.rationale)
                self.assertIn(f'not added as a proposal: {NO_EVIDENCE}.', listed.rationale)
                self.assertEqual(listed.support, {'origin': 'second_review'})
                self.assertFalse([p for p in result.proposals if p.bucket != 'alternative'])
                self.assertEqual([u[3] for u in unresolved_items(result)], [EUS_ITEM])  # nothing promoted

    def test_an_act_the_document_states_both_ways_is_said_so(self):
        text = BIOPSY_BOTH_WAYS
        result = merged(text, [], second_review(sel('45380', span(text, CECUM))), [COLONOSCOPY_ITEM])
        # the persisted fact the reason states: the conflict the assessment records, kept with both sides
        (conflict,) = result.services['conflicts']
        self.assertEqual(([s['status'] for s in conflict['sides']], conflict['subject']), (['performed', 'negated'],
                                                                                          'biopsy'))
        (listed,) = alternatives(result, '45380')
        self.assertEqual(listed.exclusion_reason, f'{SELECTED_NOT_ADDED}{BOTH_WAYS}.{CANNOT_APPROVE}')
        self.assertNotIn('not documented as done', listed.rationale)
        self.assertEqual([u[3] for u in unresolved_items(result)], [COLONOSCOPY_ITEM])

    def test_controls_what_was_read_keeps_its_reason(self):
        # an act the document does not document as done, read through the code's exact passage: the reason stands
        text = NO_BIOPSY_DOCUMENTED
        result = merged(text, [], second_review(sel('45380', span(text, CECUM))), [COLONOSCOPY_ITEM])
        (listed,) = alternatives(result, '45380')
        self.assertEqual(listed.exclusion_reason, f'{SELECTED_NOT_ADDED}{NOT_DONE}.{CANNOT_APPROVE}')
        # a code of another family accounts for none of it, with or without a passage
        for passages in ((), (span(EUS_WITH_EGD, FNA),)):
            with self.subTest(passages=len(passages)):
                result = merged(EUS_WITH_EGD, [], second_review(sel('45380', *passages)), [EUS_ITEM])
                (listed,) = alternatives(result, '45380')
                self.assertEqual(listed.exclusion_reason, f'{SELECTED_NOT_ADDED}{NOT_ADDED}.{CANNOT_APPROVE}')
        # the exact passage the source supports: added, marked as from the second review
        result = merged(EUS_WITH_EGD, [], second_review(sel('43242', span(EUS_WITH_EGD, FNA))), [EUS_ITEM])
        (added,) = [p for p in result.proposals if p.code == '43242']
        self.assertEqual((added.bucket, added.support['origin']), ('selected', 'second_review'))
        self.assertEqual(unresolved_items(result), [])


# --- F2: the second review's problems and unlisted codes are reported --------------------------------------------------

class TheSecondReviewsResponseProblemsAreReportedTests(SimpleTestCase):
    """F2. Read as a primary, a response with two malformed entries and an over-long code gives provider.problems and
    provider.unlisted warnings. Read as the second review, nothing said so: its check was 'info' and named only the
    added code. Its check says what the primary's would, of its own response, and is a warning."""

    def test_problems_and_unlisted_codes_are_worded_as_the_primarys_are(self):
        text = EUS_WITH_EGD
        overlong = ProviderCode('candidate', 'cpt', OVERLONG, '', ())
        result = merged(text, [], second_review(sel('43242', span(text, FNA)), overlong, problems=PROBLEMS),
                        [EUS_ITEM])
        self.assertEqual([(p.code, p.bucket) for p in result.proposals], [('43242', 'selected')])  # still added
        check = review_check(result)
        self.assertEqual(check.status, 'warn')
        primary = checks.provider_checks('succeeded', NormalizedResponse('replay', 'test@1', problems=PROBLEMS))[1]
        self.assertTrue(primary.detail.startswith('2 problems reading the provider response: '), primary.detail)
        self.assertIn(primary.detail.replace('the provider response', "the second review's response"), check.detail)
        unlisted = checks.unlisted_codes_check(1, MAX_LISTED_CODE).detail
        self.assertTrue(check.detail.endswith(unlisted.replace('The provider returned', 'The second review returned')),
                        check.detail)
        self.assertNotIn(OVERLONG, check.detail)  # never quoted
        self.assertNotIn(OVERLONG, json.dumps([p.code for p in result.proposals]))
        ids = [c.id for c in result.encounter_checks]
        self.assertNotIn('provider.problems', ids)  # the primary's response had none: never said of it
        self.assertNotIn('provider.unlisted', ids)

    def test_a_second_review_that_added_nothing_says_them_too(self):
        text = EUS_WITH_EGD
        overlong = ProviderCode('selected', 'cpt', OVERLONG, '', ())
        check = review_check(merged(text, [], second_review(overlong, problems=PROBLEMS[:1]), [EUS_ITEM]))
        self.assertEqual(check.status, 'warn')
        self.assertIn("1 problem reading the second review's response: codes[1] has no code; it was dropped.",
                      check.detail)
        self.assertIn('The second review returned 1 code that cannot be listed', check.detail)

    def test_control_the_primarys_own_wording_is_unchanged(self):
        # byte for byte as the installed code wrote provider.problems and provider.unlisted (ee1aa9a46 checks.py)
        problems = checks.provider_checks('succeeded', NormalizedResponse('replay', 'test@1', problems=PROBLEMS))[1]
        self.assertEqual((problems.id, problems.status, problems.detail),
                         ('provider.problems', 'warn', '2 problems reading the provider response: '
                                                       'codes[1] has no code; it was dropped.; '
                                                       'codes[2] is not an object; it was dropped.'))
        for count, said in ((1, '1 code that cannot be listed: empty, or longer than 10 characters (a CPT code has '
                                'five). It is not shown'),
                            (3, '3 codes that cannot be listed: empty, or longer than 10 characters (a CPT code has '
                                'five). They are not shown')):
            unlisted = checks.unlisted_codes_check(count, MAX_LISTED_CODE)
            self.assertEqual((unlisted.id, unlisted.status, unlisted.detail),
                             ('provider.unlisted', 'warn', f'The provider returned {said} and never truncated.'))

    def test_controls_a_clean_response_and_one_refused_whole(self):
        text = EUS_WITH_EGD
        check = review_check(merged(text, [], second_review(sel('43242', span(text, FNA))), [EUS_ITEM]))
        self.assertEqual(check.status, 'info')
        self.assertNotIn('problem', check.detail)
        self.assertNotIn('cannot be listed', check.detail)
        refusal = ('The provider response was not used: it selects 65 codes, more than the 64 this adapter accepts.',)
        check = review_check(merged(text, [], second_review(problems=refusal, refused=True), [EUS_ITEM]))
        self.assertEqual((check.status, check.detail),
                         ('fail', f'A second review was requested for: {EUS_ITEM}. Its response was not used '
                                  f'({refusal[0]}).'))


# --- WORDING: the items are quoted as items ----------------------------------------------------------------------------

class TheSecondReviewCheckQuotesItsItemsAsItemsTests(SimpleTestCase):
    """The provider.second_review sentence seen live on 2026-10-28 (ho-06's EUS, nothing added): "A second review
    limited to the passages of endoscopic ultrasound (documented as performed) has no supported proposal added no
    proposal for them." The item's label is a clause; worded in as a noun phrase it reads as nonsense, and "which accounts
    for <label> and is added" did the same. Each sentence states one persisted fact: the items the run's scope records
    as asked (a list after a colon), the codes added and the items they account for in this assessment's
    reconciliation, the codes listed as alternatives, and the asked items that reconciliation still lists."""

    def test_the_live_shape_nothing_added(self):
        check = review_check(merged(EUS_WITH_EGD, [], second_review(), [EUS_ITEM]))
        self.assertEqual((check.status, check.detail),
                         ('warn', f'A second review was requested for: {EUS_ITEM}. It was limited to the text that '
                                  'documents this item and added no proposal. The item stays unresolved.'))
        self.assertNotIn('passages of', check.detail)
        assert_items_quoted(self, check.detail, [EUS_ITEM])

    def test_one_item_accounted_for(self):
        check = review_check(merged(EUS_WITH_EGD, [], second_review(sel('43242', span(EUS_WITH_EGD, FNA))), [EUS_ITEM]))
        self.assertEqual((check.status, check.detail),
                         ('info', f'A second review was requested for: {EUS_ITEM}. It was limited to the text that '
                                  'documents this item and selected 43242, added as a proposal for review (marked as '
                                  f'from the second review). 43242 accounts for: {EUS_ITEM}.'))
        assert_items_quoted(self, check.detail, [EUS_ITEM])

    def test_a_code_not_added_is_listed_with_its_item_left_unresolved(self):
        text = EUS_WITH_EGD
        check = review_check(merged(text, [], second_review(sel('43242', shifted(text, FNA))), [EUS_ITEM]))
        self.assertEqual(check.detail, f'A second review was requested for: {EUS_ITEM}. It was limited to the text that '
                                       'documents this item and added no proposal (it listed 43242, shown as an '
                                       'alternative only, with why it is not added). The item stays unresolved.')

    def test_two_items_one_accounted_for_one_still_unresolved(self):
        text = COLONOSCOPY_THREE
        primary = [sel(SNARE[0], span(text, SNARE[1]))]
        biopsy, dilation = [u[3] for u in unresolved_items(run(text, primary))]
        self.assertTrue(biopsy.startswith('forceps biopsy') and dilation.startswith('dilation'), (biopsy, dilation))
        asked = f'A second review was requested for: {biopsy}; {dilation}. It was limited to the text that documents ' \
                'these items and '
        for later, status, said in (
                ((BIOPSY, SNARE), 'warn', 'selected 45380, added as a proposal for review (marked as from the second '
                                          f'review). 45380 accounts for: {biopsy}. It also listed 45385, shown as an '
                                          f'alternative only. Still unresolved: {dilation}.'),
                ((BIOPSY, DILATION), 'info', 'selected 45380, 45386, added as proposals for review (marked as from the '
                                             f'second review). 45380, 45386 account for: {biopsy}; {dilation}.'),
                ((), 'warn', 'added no proposal. The items stay unresolved.')):
            with self.subTest(later=[code for code, _ in later]):
                second = second_review(*(sel(code, span(text, quote)) for code, quote in later))
                check = review_check(merged(text, primary, second, [biopsy, dilation]))
                self.assertEqual((check.status, check.detail), (status, asked + said))
                assert_items_quoted(self, check.detail, [biopsy, dilation])

    def test_past_four_asked_items_the_rest_are_counted(self):
        others = [f'synthetic item {n} (documented as performed) has no supported proposal' for n in range(1, 5)]
        for second in (second_review(), second_review(problems=('it is not a JSON object',), refused=True)):
            with self.subTest(refused=second.refused):
                check = review_check(merged(EUS_WITH_EGD, [], second, [EUS_ITEM, *others]))
                self.assertTrue(check.detail.startswith(f'A second review was requested for: {EUS_ITEM}; '
                                                        f'{"; ".join(others[:3])} and 1 more. '), check.detail)
                self.assertNotIn(others[3], check.detail)
                assert_items_quoted(self, check.detail, [EUS_ITEM, *others[:3]])


# --- through the pipeline: the stored check, the reports and the screens ----------------------------------------------

class ListingProvider(TwoPassProvider):
    """As TwoPassProvider - each request's selected codes quoted exactly - and each response also lists ``first_listed``
    (the primary's) or ``later_listed`` (the second review's) as candidates, so both list informational codes."""

    def __init__(self, first, later, first_listed=(), later_listed=()):
        super().__init__(first, later)
        self.first_listed, self.later_listed = list(first_listed), list(later_listed)

    def send(self, request, *, deadline_s):
        quotes, listed = (self.first, self.first_listed) if not self.requests else (self.later, self.later_listed)
        self.requests.append(request)
        context = request.contexts[0]
        codes = []
        for code, quote in quotes:
            start = context.index(quote)
            codes.append({'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING', 'alternatives': [],
                          'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}]})
        candidates = [{'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING'} for code in listed]
        data = json.dumps({'codes': codes, 'candidates': candidates, 'usageInfo': {'creditsConsumed': 0.02}}).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


def verify_downloads():
    """ops/verify_downloads.py, the reviewed-download verifier, imported from this tree."""
    ops = str(Path(settings.BASE_DIR) / 'ops')
    if ops not in sys.path:
        sys.path.insert(0, ops)
    import verify_downloads as module
    return module


def unescape(html):
    return html.replace('&#x27;', "'").replace('&quot;', '"').replace('&amp;', '&')


class TheSecondReviewThroughThePipelineTests(Harness):
    """The live shape end to end: the primary answer proposes nothing for the EUS, a reviewer asks for the one second
    review, and it adds nothing. The stored check, the draft TXT and the Checks tab carry the reworded sentence."""

    def test_the_live_shape_on_every_surface(self):
        self.use(TwoPassProvider([], []))
        encounter_id = self.create(EUS_WITH_EGD)
        drain()
        offered = self.detail(encounter_id)['second_review']
        self.assertEqual((offered['available'], offered['items']), (True, [EUS_ITEM]), offered)
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        second = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review')
        self.assertEqual((second.state, second.scope['items']), ('succeeded', [EUS_ITEM]))
        check = self.encounter_check(encounter_id, 'provider.second_review')
        said = (f'A second review was requested for: {EUS_ITEM}. It was limited to the text that documents this item '
                'and added no proposal. The item stays unresolved.')
        self.assertEqual((check['status'], check['detail']), ('warn', said))
        self.assertIn(f'[WARN] provider.second_review — Second review: {said}', self.txt(encounter_id))
        self.assertIn(said, unescape(page(self.detail(encounter_id))['checks']))


class MalformedSecondReview(ListingProvider):
    """The primary request gets ``first``; the second review's response selects ``later`` exactly beside two malformed
    entries (one with an empty code, one not an object) and a code too long to list - read by the real adapter's
    normaliser, as stored."""

    def send(self, request, *, deadline_s):
        if not self.requests:
            return super().send(request, deadline_s=deadline_s)
        self.requests.append(request)
        context = request.contexts[0]
        codes = []
        for code, quote in self.later:
            start = context.index(quote)
            codes.append({'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING', 'alternatives': [],
                          'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}]})
        codes += [{'system': 'cpt', 'code': ''}, 'not-an-object', {'system': 'cpt', 'code': OVERLONG}]
        data = json.dumps({'codes': codes, 'candidates': [], 'usageInfo': {'creditsConsumed': 0.02}}).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


class TheSecondReviewsProblemsThroughThePipelineTests(Harness):
    """F2 as stored: the second review's response is normalised by the adapter and its passages moved to the revision
    (jobs._second_inputs) before the merge; its problems and the code it returned that cannot be listed reach the stored
    provider.second_review check, the draft TXT and the Checks tab - never the primary's provider.problems."""

    def test_the_stored_check_and_reports_say_them(self):
        self.use(MalformedSecondReview([SNARE], [BIOPSY]))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        assessment = self.assessment(encounter_id)
        added = assessment.proposals.get(code='45380')
        self.assertEqual((added.bucket, added.support['origin']), ('selected', 'second_review'))
        check = self.encounter_check(encounter_id, 'provider.second_review')
        self.assertEqual(check['status'], 'warn')
        problems = ("2 problems reading the second review's response: codes[1] has no code; it was dropped.; "
                    'codes[2] is not an object; it was dropped.')
        unlisted = ('The second review returned 1 code that cannot be listed: empty, or longer than 10 characters (a '
                    'CPT code has five). It is not shown and never truncated.')
        self.assertTrue(check['detail'].endswith(f'{problems} {unlisted}'), check['detail'])
        ids = [c['id'] for c in assessment.encounter_checks]
        self.assertNotIn('provider.problems', ids)
        self.assertNotIn('provider.unlisted', ids)
        draft = self.txt(encounter_id)
        self.assertIn(f'[WARN] provider.second_review — Second review: {check["detail"]}', draft)
        self.assertNotIn(OVERLONG, draft)
        self.assertIn(check['detail'], unescape(page(self.detail(encounter_id))['checks']))


class TheOriginOfASecondReviewCodeIsSaidTests(Harness):
    """F4 and F5. The primary selects the snare polypectomy and lists 45378; a reviewer asks for the second review, which
    selects the biopsy (added, marked as from it) and lists 45381. On the Suggestions screen the alternative it listed
    says where it came from, as the TXT and the CSV do; a code of its the reviewer rejects keeps the Origin line in
    REJECTED, as in the approved and undecided lists, and the verifier still reads that list as exactly its codes."""

    def reviewed(self, rejected):
        self.use(ListingProvider([SNARE], [BIOPSY], first_listed=['45378'], later_listed=['45381']))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        for code in ('45385', '45380'):
            self.decide_with_note(encounter_id, code, 'reject' if code == rejected else 'approve')
        reply = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertEqual(reply.status_code, 201, reply.content)
        return encounter_id

    def decide_with_note(self, encounter_id, code, action):
        (proposal,) = [p for p in self.detail(encounter_id)['assessment']['proposals']
                       if p['code'] == code and p['bucket'] == 'selected']
        body = {'proposal_id': proposal['id'], 'action': action,
                'note': 'Agent-executed synthetic verification review; not a clinical judgement.'}
        if action == 'approve':
            body['acknowledgement'] = self.client.get('/api/session').json()['acknowledgement']
        reply = self.post(f'/api/encounters/{encounter_id}/decisions', body)
        self.assertEqual(reply.status_code, 201, reply.content)

    def test_the_screen_marks_the_alternatives_the_second_review_listed(self):
        encounter_id = self.reviewed(rejected='45380')
        detail = self.detail(encounter_id)
        listed = {p['code']: p for p in detail['assessment']['proposals'] if p['bucket'] == 'alternative'}
        self.assertEqual({code: (p['support'] or {}).get('origin') for code, p in listed.items()},
                         {'45378': None, '45381': 'second_review'})
        codes = unescape(page(detail)['codes'])
        titles = re.findall(r'<strong>(\d{5} · [^<]*)</strong>', codes)
        label = listed['45381']['family_label']
        self.assertIn(f'45381 · {label} · from the second review', titles)
        self.assertIn(f'45378 · {listed["45378"]["family_label"]}', titles)  # the primary's, as before
        self.assertNotIn(f'45378 · {listed["45378"]["family_label"]} · from the second review', titles)
        draft = self.txt(encounter_id)  # the TXT and the CSV said so already
        self.assertIn(f'  - 45381 · {label} — second-review alternative, never selectable', draft)
        rows = {row['code']: row for row in csv.DictReader(self.csv_text(encounter_id).splitlines())
                if row['item_list'] == 'alternative'}
        self.assertEqual((rows['45381']['proposal_origin'], rows['45378']['proposal_origin']), ('second_review', ''))

    def test_a_rejected_second_review_code_keeps_its_origin_line(self):
        encounter_id = self.reviewed(rejected='45380')
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind):
                rejected = section(self.txt(encounter_id, kind), 'REJECTED').split('\n')
                self.assertEqual(len(rejected), 3, rejected)
                self.assertTrue(rejected[0].startswith('  - 45380 · ') and ' — rejected by ' in rejected[0], rejected)
                self.assertEqual(rejected[1], f'     {ORIGIN}')
                self.assertTrue(rejected[2].startswith('     Note: Agent-executed synthetic verification review'))
                listed = verify_downloads()._listed(rejected, False)
                self.assertEqual(listed, Counter({('45380', ''): 1}))  # still read as exactly its one item
        reviewed = self.txt(encounter_id, 'reviewed')
        approved = section(reviewed, 'APPROVED SELECTIONS')
        self.assertNotIn(ORIGIN, approved)  # the primary's 45385
        self.assertEqual(reviewed.count(ORIGIN), 1)

    def test_control_a_rejected_primary_code_has_none_and_the_approved_one_keeps_its_own(self):
        encounter_id = self.reviewed(rejected='45385')
        reviewed = self.txt(encounter_id, 'reviewed')
        rejected = section(reviewed, 'REJECTED').split('\n')
        self.assertEqual(len(rejected), 2, rejected)
        self.assertTrue(rejected[0].startswith('  - 45385 · '), rejected)
        self.assertNotIn(ORIGIN, '\n'.join(rejected))
        approved = section(reviewed, 'APPROVED SELECTIONS')
        self.assertIn(f'     {ORIGIN}', approved)  # 45380, from the second review
        self.assertEqual(reviewed.count(ORIGIN), 1)
