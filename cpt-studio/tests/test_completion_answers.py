"""Completion repair (owner directive 2026-11-06), builder Q2: truthful questions, answer controls, recompute after an
answer, and answer binding (CPT-HARNESS-CHECKLIST.md U10, U11; HARNESS.md contract C5).

- A question shows the passages it concerns and names the fact CPT Studio could not confirm - never that the document
  leaves it out - with the concise control: "Not documented", "Cannot confirm", the physician's addendum (D7 keeps
  reviewer confirmation off), and the choice and date controls for context facts.
- An answer recomputes the assessment: one AGAIN assess of the recorded runs (nothing sent), keyed by the answers, which
  reads the answers as an input (engine._MemberAnswers). The code it answers is excluded by the member's answer; it
  still holds every code its presence held (session decision (e), L7-01); the competition it was a rival in is released
  (L4-5); the other codes' CMS endoscopic-family check is read again without it. The answered question is closed with
  its answer, so the operator queue, the customer page, review and the reports agree.
- An answer binds to the question it answered - (code, family, fact) and the fingerprint of the question as its row
  showed it (studio.validation.questions). A later assessment applies it only to the same question; any other answer is
  kept and listed as an earlier answer, never applied. An answer recorded before answers carried a fingerprint was given
  to the earlier form (no passage) and is never applied.

Synthetic data only; every provider is an in-process fake (nothing is sent anywhere).
"""
import dataclasses
import json
from unittest import mock

from django.test import SimpleTestCase, TestCase

from studio import answers, customer_api, jobs, models, reports, review, serializers
from studio.types import EvidenceSpan, sha256_json
from studio.validation import engine, questions, review_view
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_cux_flow import COLON, DetailsCase, asks
from tests.test_cux_r2_details import PipelineCase
from tests.test_harness_engine import COLON as COLON_NOTE
from tests.test_harness_engine import BIOPSY, SNARE, code, corti, read, run, span
from tests.test_h3_refutation_r1 import CompetitionReleaseTests
from tests.test_pipeline_api import drain
from tests.test_reference import ArchiveMixin

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
        'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
        'The colonoscope was advanced to the cecum and the examination was completed.\n')
FORCEPS = 'A 4 mm polyp in the rectum was removed with cold forceps.'
HEDGED_SNARE = 'A 9 mm polyp in the sigmoid colon was possibly removed with a hot snare.'
HEDGED = HEAD + FORCEPS + '\n' + HEDGED_SNARE + '\n'
# the extent unstated: each colonoscopy code is asked how far the instrument was advanced
UNREACHED = COLON_NOTE.replace('The colonoscope was advanced to the cecum and the examination was completed.\n',
                               'The colonoscope was advanced.\n')


def asked(result, text):
    """The questions an engine result asks, by member key, as the engine binds them (engine._MemberAnswers)."""
    pairs = []
    acts = questions.acts_of(result.services)
    for p in result.proposals:
        for spec in p.clarifications:
            family = spec.family or p.family
            shown = questions.question_passages(result.services, family, spec.fact, p.evidence, p.support, text, acts)
            pairs.append((questions.member_key(p.code, family, spec.fact),
                          questions.instance(spec.scope, family, spec.fact, p.code, spec.question, spec.reason,
                                             shown)))
    return questions.group(pairs)


def given(result, text, value, fact, *, verdict='not_documented', ident='a1'):
    family = next(p.family for p in result.proposals if p.code == value)
    return questions.MemberAnswerInput(code=value, family=family, fact=fact, value=verdict,
                                       question=asked(result, text).get((value, family, fact), ''), answer_id=ident)


def by_code(result):
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}


def check(p, check_id):
    return next((c for c in p.checks if c.id == check_id), None)


# --- the question's identity (studio/validation/questions.py) --------------------------------------------------------

class QuestionIdentityTests(SimpleTestCase):
    TEXT = 'Procedure: Colonoscopy. A 6 mm polyp in the sigmoid colon was removed with a cold snare. Biopsies taken.'

    def spans(self, *phrases, exact=True, index=0):
        return [EvidenceSpan(index, self.TEXT.index(p), self.TEXT.index(p) + len(p), p, exact) for p in phrases]

    def test_passages_are_the_acts_then_the_codes_then_cpt_studios_located_readable_bounded_and_exact(self):
        snare = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        support = {'source': [{'start': self.TEXT.index(snare), 'end': self.TEXT.index(snare) + len(snare),
                               'text': snare}]}
        cited = self.spans('cold snare', 'Biopsies taken.', 'sigmoid colon')
        shown = questions.passages(cited, support, self.TEXT)
        # the code's own cited passages (at most PER_SOURCE), then CPT Studio's located sentence, which holds the cited
        # "cold snare" and takes its place: each passage once
        self.assertEqual([quoted for _, _, quoted in shown], [snare, 'Biopsies taken.'])
        partly = [EvidenceSpan(0, 0, 30, self.TEXT[0:30], True)]
        later = {'source': [{'start': 20, 'end': 60, 'text': self.TEXT[20:60]}]}
        self.assertEqual([q for _, _, q in questions.passages(partly, later, self.TEXT)], [self.TEXT[0:30]])
        # the passages of the act the code was matched to come first, whatever its status; one they hold adds nothing
        act = {'start': self.TEXT.index(snare), 'end': self.TEXT.index(snare) + len(snare), 'text': snare}
        matched = questions.passages(cited, {**support, 'acts': [{'id': 'S1-A2', 'kind': 'snare'}]}, self.TEXT,
                                     {'S1-A2': {'id': 'S1-A2', 'status': 'uncertain', 'evidence': [act]}})
        self.assertEqual([quoted for _, _, quoted in matched], [snare, 'Biopsies taken.'])
        one_word = [EvidenceSpan(0, 0, 8, 'Multiple', True)]
        self.assertEqual(questions.passages(one_word, {}, 'Multiple biopsies'), ())  # a single word is a fragment
        # too short to read a question by, another context's span, a span not flagged exact, a non-slice: never shown
        self.assertEqual(questions.passages(self.spans('A 6'), {}, self.TEXT), ())
        self.assertEqual(questions.passages(self.spans('Biopsies taken.', index=1), {}, self.TEXT), ())
        self.assertEqual(questions.passages(self.spans('Biopsies taken.', exact=False), {}, self.TEXT), ())
        forged = [EvidenceSpan(0, 0, 15, 'Biopsies taken.', True)]
        self.assertEqual(questions.passages(forged, {}, self.TEXT), ())
        many = {'source': [{'start': i, 'end': i + 12, 'text': self.TEXT[i:i + 12]} for i in (0, 24, 40, 60, 80)]}
        self.assertEqual(len(questions.passages((), many, self.TEXT)), questions.PER_SOURCE)  # each source bounded
        acts = {f'A{i}': {'evidence': [{'start': i, 'end': i + 12, 'text': self.TEXT[i:i + 12]}]} for i in (0, 24)}
        cited_many = [EvidenceSpan(0, i, i + 12, self.TEXT[i:i + 12], True) for i in (40, 60)]
        every = questions.passages(cited_many, {**many, 'acts': [{'id': 'A0'}, {'id': 'A24'}]}, self.TEXT, acts)
        self.assertEqual(len(every), questions.MAX_PASSAGES)  # and the whole list too
        # the stored (JSON) form reads the same as the engine's
        stored = [{'context_index': 0, 'start': s.start, 'end': s.end, 'text': s.text, 'exact': True, 'page': None}
                  for s in cited]
        self.assertEqual(questions.passages(stored, support, self.TEXT), shown)

    def test_the_fingerprint_reads_the_question_its_reason_its_passages_its_code_and_the_form(self):
        base = questions.instance('proposal', COLON, 'extent', '45385', 'Q', 'R', ((1, 9, 'passage1'),))
        same = questions.fingerprint([dict(base)])
        self.assertEqual(questions.fingerprint([base]), same)
        self.assertEqual(len(same), 64)
        for name, value in (('question', 'Q2'), ('reason', 'R2'), ('code', '45380'), ('fact', 'completion'),
                            ('family', 'gi.egd'), ('scope', 'service'), ('passages', [[1, 9, 'passage2']])):
            with self.subTest(name):
                self.assertNotEqual(questions.fingerprint([{**base, name: value}]), same)
        # the instance itself carries the passages shown: the same question shown with another passage is another one
        other = questions.instance('proposal', COLON, 'extent', '45385', 'Q', 'R', ((1, 9, 'passage2'),))
        self.assertNotEqual(questions.fingerprint([other]), same)
        self.assertEqual(base['passages'], [[1, 9, 'passage1']])
        two = [base, {**base, 'reason': 'R2'}]
        self.assertEqual(questions.fingerprint(two), questions.fingerprint(list(reversed(two))))  # order-free
        self.assertNotEqual(questions.fingerprint(two), same)  # an added instance asks differently
        self.assertEqual(questions.fingerprint([]), '')
        with mock.patch.object(questions, 'FORM', 'cpt-studio-question@2'):
            self.assertNotEqual(questions.fingerprint([base]), same)

    def test_bind_applies_an_answer_only_to_its_own_question_and_says_why_it_does_not(self):
        asked_now = {('45385', COLON, 'extent'): 'f' * 64}

        def answer(**kw):
            return {'code': '45385', 'family': COLON, 'fact': 'extent', 'value': 'not_documented',
                    'question': 'f' * 64, **kw}
        bound, earlier = questions.bind([answer(), answer(question='e' * 64), answer(question=''),
                                         answer(code='45380'), answer(value='performed')], asked_now)
        # refutation cycle 2 (answers W2, W4): an answer stored before the binding (question '') binds by its key, as the
        # installed release bound it; a fingerprinted one by its fingerprint alone
        self.assertEqual([a['question'] for a in bound], ['f' * 64, ''])
        self.assertEqual([why for _, why in earlier], [questions.ASKED_DIFFERENTLY, questions.NO_LONGER_ASKED])

    def test_every_fact_a_question_asks_is_named_in_plain_words(self):
        from studio.gi.profiles import PROFILES
        facts = {fact for profile in PROFILES.values() for fact in profile.required_facts}
        facts |= {'performed_status', 'base_included', 'separate_em', 'units', 'documentation', engine.COMPETING_FACT}
        for fact in sorted(facts):
            with self.subTest(fact):
                self.assertIn(fact, questions.MISSING)
                self.assertNotIn('not documented', questions.missing(fact))
        self.assertEqual(questions.missing('conflict:biopsy', 'forceps biopsy'),
                         'which statement about the forceps biopsy is right for this date')


# --- the engine reads the answers as an input (engine._MemberAnswers) -------------------------------------------------

class EngineAnswerTests(SimpleTestCase):
    def test_no_answer_leaves_the_result_byte_for_byte(self):
        codes = corti(('45385', span(UNREACHED, SNARE)), ('45380', span(UNREACHED, BIOPSY)))
        self.assertEqual(sha256_json(run(UNREACHED, codes, member_answers=())), sha256_json(run(UNREACHED, codes)))
        self.assertNotIn('member_answers', run(UNREACHED, codes, member_answers=()).completeness)

    def test_an_answer_excludes_the_code_it_answers_by_the_members_answer_and_the_base_stays_held(self):
        """L7-01 in the engine (session decision (e)): "Cannot confirm" on 45385's extent excludes 45385 only. The
        diagnostic base 45378 beside it keeps its base_included question and its own extent question, and its
        fingerprint, so a decision on it carries."""
        base = 'The colonoscope was advanced.'
        codes = corti(('45378', span(UNREACHED, base)), ('45385', span(UNREACHED, SNARE)))
        before = run(UNREACHED, codes)
        self.assertEqual({c: (p.bucket, p.status) for c, p in by_code(before).items()},
                         {'45378': ('selected', 'needs_clarification'), '45385': ('selected', 'needs_clarification')})
        answer = given(before, UNREACHED, '45385', 'extent', verdict='cannot_confirm')
        after = run(UNREACHED, codes, member_answers=(answer,))
        snare, diagnostic = by_code(after)['45385'], by_code(after)['45378']
        self.assertEqual((snare.bucket, snare.status, snare.reinstatable), ('excluded', 'excluded', False))
        self.assertEqual(snare.exclusion_reason, 'The member answered "Cannot confirm" to how far the instrument was '
                                                 'advanced; this code is excluded by that answer until it is withdrawn.')
        self.assertEqual(check(snare, engine.MEMBER_ANSWER_CHECK).status, 'fail')
        self.assertEqual(snare.support['answered'], {'fact': 'extent', 'value': 'cannot_confirm', 'answers': ['a1']})
        self.assertEqual([c.fact for c in snare.clarifications], ['extent'])  # the answered question, kept
        self.assertEqual((diagnostic.status, sorted(c.fact for c in diagnostic.clarifications)),
                         ('needs_clarification', ['base_included', 'extent']))
        self.assertEqual(check(diagnostic, 'services.base_included').status, 'warn')
        # its CMS endoscopic-family check reads the codes still in review: 45385, whose endoscopic base 45378 is, is not
        self.assertEqual((check(by_code(before)['45378'], 'pfs.endoscopic_base').status,
                          check(diagnostic, 'pfs.endoscopic_base').status), ('warn', 'pass'))
        # refutation cycle 4 (answers 1): a check another code's answer moves keeps the fingerprint - the review overlay
        # shows it so already - so a decision on the diagnostic carries; the answered code's own moves
        self.assertEqual(diagnostic.fingerprint, by_code(before)['45378'].fingerprint)
        self.assertNotEqual(snare.fingerprint, by_code(before)['45385'].fingerprint)
        record = after.completeness['member_answers']
        self.assertEqual([(e['answer'], e['code'], e['fact'], e['proposals']) for e in record['applied']],
                         [('a1', '45385', 'extent', [snare.key])])
        self.assertEqual(record['earlier'], [])
        self.assertIn('2 open questions', after.completeness['reasons'])  # the answered one is closed

    def test_an_answer_to_another_question_is_kept_as_earlier_and_changes_nothing(self):
        codes = corti(('45385', span(UNREACHED, SNARE)), ('45380', span(UNREACHED, BIOPSY)))
        before = run(UNREACHED, codes)
        real = given(before, UNREACHED, '45385', 'extent')
        cases = [questions.MemberAnswerInput('45385', COLON, 'extent', 'not_documented', 'e' * 64, 'x1'),
                 questions.MemberAnswerInput('45390', COLON, 'extent', 'not_documented', real.question, 'x3')]
        after = run(UNREACHED, codes, member_answers=cases)
        self.assertEqual([p.fingerprint for p in after.proposals], [p.fingerprint for p in before.proposals])
        self.assertEqual(after.clarifications, before.clarifications)
        self.assertEqual([(e['answer'], e['why']) for e in after.completeness['member_answers']['earlier']],
                         [('x1', questions.ASKED_DIFFERENTLY), ('x3', questions.NO_LONGER_ASKED)])
        # refutation cycle 2 (answers W2, W4): an answer stored before the binding (no fingerprint) binds by its key, as
        # the installed release bound it. Refutation cycle 4 (answers 1-3): the review overlay reads it, at read time over
        # the current decisions, as the installed release read it - this reader leaves every code as it was and records
        # the answer as the overlay's
        legacy = questions.MemberAnswerInput('45385', COLON, 'extent', 'not_documented', '', 'x2')
        applied = run(UNREACHED, codes, member_answers=[legacy])
        self.assertEqual([p.fingerprint for p in applied.proposals], [p.fingerprint for p in before.proposals])
        self.assertEqual(next(p for p in applied.proposals if p.code == '45385').bucket, 'selected')
        self.assertEqual([(e['answer'], e['why']) for e in applied.completeness['member_answers']['earlier']],
                         [('x2', engine.OVERLAY_READ)])
        # a reason reworded by the engine is a question asked differently: the answer to the old wording is not read
        reworded = dataclasses.replace(before, proposals=tuple(replace_reason(p) for p in before.proposals))
        self.assertNotEqual(asked(reworded, UNREACHED)[('45385', COLON, 'extent')], real.question)

    def test_an_answer_to_a_question_shown_with_another_passage_is_not_read(self):
        """The question is the one its row showed, passages included: 45385 now cites only part of the hedged sentence,
        so the question it is asked shows another passage (and its reason quotes it), and the answer is an earlier one.
        Citing the whole sentence again, it is read."""
        text = HEAD + HEDGED_SNARE + '\n'
        part = 'possibly removed with a hot snare'
        first = run(text, corti(('45385', span(text, HEDGED_SNARE))))
        answer = given(first, text, '45385', 'performed_status')
        moved = run(text, corti(('45385', span(text, part))), member_answers=(answer,))
        self.assertEqual(by_code(moved)['45385'].bucket, 'selected')
        self.assertEqual([(e['answer'], e['why']) for e in moved.completeness['member_answers']['earlier']],
                         [('a1', questions.ASKED_DIFFERENTLY)])
        (spec,), (before,) = by_code(moved)['45385'].clarifications, by_code(first)['45385'].clarifications
        self.assertEqual((spec.fact, spec.question), (before.fact, before.question))  # the same words are asked
        same = run(text, corti(('45385', span(text, HEDGED_SNARE))), member_answers=(answer,))
        self.assertEqual(by_code(same)['45385'].bucket, 'excluded')

    def test_the_other_codes_endoscopic_family_check_is_read_again_without_the_answered_code(self):
        """The base code's effect recomputed: 45380 and 45385 share the endoscopic base 45378 (the multiple endoscopy
        rule, info); 45380 answered away, 45385's check reads no other code of the family."""
        codes = corti(('45385', span(UNREACHED, SNARE)), ('45380', span(UNREACHED, BIOPSY)))
        before = run(UNREACHED, codes)
        self.assertEqual(check(by_code(before)['45385'], 'pfs.endoscopic_base').status, 'info')
        after = run(UNREACHED, codes, member_answers=(given(before, UNREACHED, '45380', 'extent'),))
        snare = by_code(after)['45385']
        self.assertEqual(by_code(after)['45380'].bucket, 'excluded')
        self.assertEqual((snare.status, check(snare, 'pfs.endoscopic_base').status), ('needs_clarification', 'pass'))
        self.assertIn('No other selected code shares an endoscopic base relationship with 45385',
                      check(snare, 'pfs.endoscopic_base').detail)
        # refutation cycle 4 (answers 1): its checks moved through another code's answer - its fingerprint does not
        self.assertEqual(snare.fingerprint, by_code(before)['45385'].fingerprint)

    def test_a_rival_answered_away_releases_the_competition_and_an_answer_to_the_hold_itself_never_does(self):
        text = CompetitionReleaseTests.EGD + CompetitionReleaseTests.DILATION + '\n'
        # Completion repair (integration, 2026-11-06): a guide-wire code (43248) no longer accounts for a balloon
        # dilation (reconcile.technique_fits); the rival is the other balloon code (43233), whose technique the
        # document does not tell apart from 43249's, so what this pins is unchanged
        codes = corti(('43233', span(text, CompetitionReleaseTests.DILATION)))
        participants = [read('astra', [code(text, '43249', CompetitionReleaseTests.DILATION)])]
        before = run(text, codes, participants)
        self.assertEqual(sorted(c.fact for c in by_code(before)['43249'].clarifications),
                         [engine.COMPETING_FACT, 'extent'])
        after = run(text, codes, participants, member_answers=(given(before, text, '43233', 'extent'),))
        kept = by_code(after)['43249']
        self.assertEqual((by_code(after)['43233'].bucket, kept.status, [c.fact for c in kept.clarifications]),
                         ('excluded', 'needs_clarification', ['extent']))
        self.assertIsNone(check(kept, engine.COMPETING_CHECK))
        on_hold = run(text, codes, participants,
                      member_answers=(given(before, text, '43233', engine.COMPETING_FACT),))
        self.assertEqual(sorted(c.fact for c in by_code(on_hold)['43249'].clarifications),
                         [engine.COMPETING_FACT, 'extent'])

    def test_the_same_answer_reads_the_same_on_a_labelled_line_and_in_a_paragraph(self):
        for layout in ('Procedure: Colonoscopy. The colonoscope was advanced. {biopsy} {snare}\n',
                       'Procedure: Colonoscopy\nThe colonoscope was advanced.\n{biopsy}\n{snare}\n'):
            text = (HEAD.split('Procedure:')[0]
                    + layout.format(biopsy='A separate 12 mm flat lesion in the ascending colon was biopsied with '
                                           'cold forceps.', snare='A 9 mm pedunculated polyp in the sigmoid colon '
                                                                  'was removed with a hot snare.'))
            with self.subTest(layout=layout[:30]):
                codes = corti(('45385', span(text, SNARE)), ('45380', span(text, BIOPSY)))
                before = run(text, codes)
                self.assertEqual(by_code(before)['45380'].status, 'needs_clarification')
                after = run(text, codes, member_answers=(given(before, text, '45380', 'extent'),))
                self.assertEqual((by_code(after)['45380'].bucket, by_code(after)['45385'].bucket),
                                 ('excluded', 'selected'))

    def test_the_overlay_over_the_answered_result_is_the_overlay_over_the_unanswered_one_with_the_answer(self):
        """Positive control at read time: the stored, answered assessment reads through review_view exactly as the
        unanswered one does with the live answer - status, reason, answer, questions, the base hold - and its
        endoscopic-family check is current, never marked stale."""
        base = 'The colonoscope was advanced.'
        codes = corti(('45378', span(UNREACHED, base)), ('45385', span(UNREACHED, SNARE)),
                      ('45380', span(UNREACHED, BIOPSY)))
        before = run(UNREACHED, codes)
        answer = given(before, UNREACHED, '45380', 'extent')
        after = run(UNREACHED, codes, member_answers=(answer,))

        def views(result, live=()):
            return review_view.review_view([review_view.stored_from(p) for p in result.proposals], {},
                                           services=result.services, reference_sources=result.reference_sources,
                                           answers=live)
        live = views(before, [{'code': answer.code, 'family': answer.family, 'fact': answer.fact,
                               'value': answer.value}])
        read = views(after)
        for key in live:
            with self.subTest(key):
                self.assertEqual((read[key].status, read[key].reason, read[key].answer, read[key].active,
                                  [q['fact'] for q in read[key].questions]),
                                 (live[key].status, live[key].reason, live[key].answer, live[key].active,
                                  [q['fact'] for q in live[key].questions]))
                self.assertEqual(read[key].stale, ())
        diagnostic = next(k for k, p in zip(read, after.proposals) if p.code == '45378')
        self.assertIn('base_included', [q['fact'] for q in read[diagnostic].questions])  # never released


class EngineAnsweredHoldsTests(SimpleTestCase):
    """L7-01's own shape (refutation round 2; session decision (e)) through the engine and at read time: the diagnostic
    base 45378 is held only because 45385 is proposed beside it (the hedged snare is no performed act of its own; with
    45385 never proposed, 45378 is ready). "Cannot confirm" on 45385 excludes 45385 and never releases 45378 - in the
    engine's result, and in the overlay over the stored result. Only a reviewer's rejection releases it."""
    TEXT = HEAD + HEDGED_SNARE + '\n'
    CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'

    def codes(self, *values):
        quotes = {'45378': self.CECUM, '45385': HEDGED_SNARE}
        return corti(*((value, span(self.TEXT, quotes[value])) for value in values))

    def test_cannot_confirm_on_the_hedged_snare_never_releases_the_base(self):
        alone = run(self.TEXT, self.codes('45378'))
        self.assertEqual(by_code(alone)['45378'].status, 'ready')  # held by nothing but 45385's presence
        both = run(self.TEXT, self.codes('45378', '45385'))
        self.assertEqual([c.fact for c in by_code(both)['45378'].clarifications], ['base_included'])
        after = run(self.TEXT, self.codes('45378', '45385'),
                    member_answers=(given(both, self.TEXT, '45385', 'performed_status', verdict='cannot_confirm'),))
        self.assertEqual((by_code(after)['45385'].bucket, by_code(after)['45378'].status), ('excluded',
                                                                                               'needs_clarification'))
        self.assertEqual([c.fact for c in by_code(after)['45378'].clarifications], ['base_included'])
        keys = {p.code: p.key for p in after.proposals}
        read = review_view.review_view([review_view.stored_from(p) for p in after.proposals], {},
                                       services=after.services, reference_sources=after.reference_sources)
        self.assertEqual((read[keys['45378']].status, [q['fact'] for q in read[keys['45378']].questions]),
                         ('needs_clarification', ['base_included']))
        self.assertEqual((read[keys['45385']].active, read[keys['45385']].reason),
                         (True, review_view.DETAIL_UNAVAILABLE))  # counted wherever its presence holds another
        # the reviewer's path, for contrast: 45385 rejected (its answer withdrawn first), the base is released
        keys = {p.code: p.key for p in both.proposals}
        rejected = review_view.review_view([review_view.stored_from(p) for p in both.proposals],
                                           {keys['45385']: review_view.Decided('reject')}, services=both.services,
                                           reference_sources=both.reference_sources)
        self.assertEqual((rejected[keys['45378']].status, rejected[keys['45378']].questions), ('ready', ()))


def replace_reason(p):
    return dataclasses.replace(p, clarifications=tuple(dataclasses.replace(c, reason=c.reason + ' (reworded)')
                                                       for c in p.clarifications))


# --- the chain through the website: an answer recomputes, every surface agrees ----------------------------------------

class AnswerRecomputeChainTests(ArchiveMixin, PipelineCase):
    """The target of builder Q2: save an answer and follow the chain - the recompute job, the new assessment (the code
    excluded by the member's answer, the other code's endoscopic-family check recomputed, the question closed), the
    operator queue without "question", the customer page, and the draft and reviewed reports agreeing."""

    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()
        self.provider.selections = [('45380', FORCEPS), ('45385', HEDGED_SNARE)]

    def code_rows(self, doc):
        return {row['code']: row for row in doc['codes']}

    def assessment(self, encounter_id):
        return self.encounter(encounter_id).current_assessment

    def approve(self, encounter_id, value):
        proposal = self.assessment(encounter_id).proposals.get(code=value)
        response = self.client.post(f'/api/encounters/{encounter_id}/decisions', content_type='application/json',
                                    data=json.dumps({'proposal_id': str(proposal.pk), 'action': 'approve',
                                                     'acknowledgement': review.ACKNOWLEDGEMENTS['human']}))
        self.assertEqual(response.status_code, 201, response.content)

    def test_saving_an_answer_recomputes_the_assessment_and_every_surface_agrees(self):
        encounter_id = self.upload(HEDGED)
        first = self.assessment(encounter_id)
        doc = self.doc(encounter_id)
        self.assertEqual({c: r['status'] for c, r in self.code_rows(doc).items()},
                         {'45380': 'ready', '45385': 'needs_detail'})
        (row,) = [r for r in doc['details_needed'] if r['fact'] == 'performed_status']
        # the question names the fact, says what CPT Studio could not confirm, and shows the passages it concerns
        self.assertEqual((row['affects'], row['allow'], row['addendum_allowed'], row['control']),
                         (['45385'], ['not_documented', 'cannot_confirm'], True, 'confirm'))
        self.assertEqual(row['missing'], 'that this procedure was performed on the date of service')
        self.assertEqual(row['statement'], 'From the document, CPT Studio could not confirm that this procedure was '
                                           'performed on the date of service.')
        self.assertIn(HEDGED_SNARE, [p['text'] for p in row['passages']])
        for passage in row['passages']:
            self.assertEqual(doc['document']['text'][passage['start']:passage['end']], passage['text'])
        self.assertIn('CPT Studio could not confirm from the document that this was done on the date of service.',
                      self.code_rows(doc)['45385']['why']['qualifications'])
        self.assertNotIn('is not documented', json.dumps(doc['details_needed']))
        self.assertIn('question', serializers.queue_reasons(self.encounter(encounter_id)))
        self.assertEqual(check_status(first, '45380', 'pfs.endoscopic_base'), 'info')
        sent = len(self.provider.sent)

        response = self.client.post(f'/api/encounters/{encounter_id}/details', content_type='application/json',
                                    data=json.dumps({'answers': [{'id': row['id'], 'fact': row['fact'],
                                                                  'value': 'not_documented'}]}))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['reassessing'])
        (answer,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id)
        self.assertEqual(answer.question, review.asked_fingerprints(first)[('45385', COLON, 'performed_status')])
        # the recompute job: one AGAIN assess, keyed by the answers, queued under the save
        (job,) = models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED)
        self.assertEqual(job.kind, models.Job.ASSESS)
        self.assertIn(jobs.AGAIN_MARK + jobs.ANSWERS_MARK + jobs.answers_digest(answer.revision), job.idempotency_key)
        self.assertEqual(self.doc(encounter_id)['progress']['busy'], True)  # the page shows progress while it runs
        drain()
        self.assertEqual(len(self.provider.sent), sent)  # nothing sent

        # the new assessment
        second = self.assessment(encounter_id)
        self.assertNotEqual(second.pk, first.pk)
        snare = second.proposals.get(code='45385')
        self.assertEqual((snare.bucket, snare.status), ('excluded', 'excluded'))
        self.assertTrue(snare.exclusion_reason.startswith('The member answered "Not documented" to that this procedure '
                                                          'was performed'))
        self.assertEqual(check_status(second, '45380', 'pfs.endoscopic_base'), 'pass')  # the base code's effect
        self.assertEqual(second.proposals.get(code='45380').status, 'ready')
        # the question closed with its answer: on the new assessment, and on the one the member answered
        for assessment in (second, first):
            closed = assessment.clarifications.get(fact='performed_status', proposal__code='45385')
            self.assertEqual((closed.state, closed.answer_id), (models.Clarification.ANSWERED, answer.pk))
        self.assertEqual([e['answer'] for e in second.completeness['member_answers']['applied']], [str(answer.pk)])
        # the operator queue, the customer page and the operator view agree
        encounter = self.encounter(encounter_id)
        self.assertNotIn('question', serializers.queue_reasons(encounter))
        self.assertEqual(serializers.encounter_summary(encounter)['open_clarifications'], 0)
        doc = self.doc(encounter_id)
        rows = self.code_rows(doc)
        self.assertEqual((rows['45385']['status'], rows['45385']['sub_label'], rows['45385']['allowed_actions']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABEL, []))
        self.assertEqual(rows['45380']['status'], 'ready')
        (row,) = [r for r in doc['details_needed'] if r['fact'] == 'performed_status']
        self.assertEqual((row['saved']['value'], row['saved']['answer_id']), ('not_documented', str(answer.pk)))
        self.assertEqual(doc['earlier_answers'], [])
        self.assertEqual(doc['state'], 'ready')
        # the draft and reviewed reports agree with the page
        self.approve(encounter_id, '45380')
        doc = self.doc(encounter_id)
        self.assertTrue(doc['readiness']['approved'])
        draft = {item['code']: item['list'] for item in reports.snapshot(self.encounter(encounter_id),
                                                                          reports.DRAFT)['proposals']}
        reviewed = {item['code']: item['list'] for item in reports.snapshot(self.encounter(encounter_id),
                                                                             reports.REVIEWED)['proposals']}
        self.assertEqual((draft['45385'], reviewed['45385'], reviewed['45380']), ('excluded', 'excluded', 'approved'))
        approved = reports.customer_snapshot(self.encounter(encounter_id), reports.APPROVED)
        self.assertEqual([item['code'] for item in approved['items']], ['45380'])
        customer_draft = {item['code']: item['status'] for item in
                          reports.customer_snapshot(self.encounter(encounter_id), reports.DRAFT)['items']}
        self.assertEqual(customer_draft, {'45380': 'approved', '45385': 'excluded'})

        # withdrawn: recomputed again, the code back in review. Refutation cycle 4 (answers 1): 45380's checks moved only
        # through another code's answer, so its fingerprint did not, and its approval carries - as the installed release
        # carried every decision across an answer (the overlay showing 45385 back in review beside it)
        revoked = self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke')
        self.assertEqual(revoked.status_code, 201, revoked.content)
        drain()
        third = self.assessment(encounter_id)
        self.assertEqual(third.proposals.get(code='45385').status, 'needs_clarification')
        self.assertEqual(check_status(third, '45380', 'pfs.endoscopic_base'), 'info')
        self.assertIn('question', serializers.queue_reasons(self.encounter(encounter_id)))
        self.assertEqual([third.proposals.get(pk=pk).code for pk in review.current_decisions(third)], ['45380'])
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision__encounter_id=encounter_id).exists())
        self.assertEqual(len(self.provider.sent), sent)

    def test_an_approval_carries_where_the_answer_moves_none_of_its_checks(self):
        """Persisted decisions carry by their existing fingerprint rule: with no CMS fee-schedule file applied, no
        check of 45380 reads 45385, so its approval carries onto the recomputed assessment."""
        encounter_id = self.upload(HEDGED.replace('2026-10-14', '2025-03-14'))  # no PFS release covers the date
        self.assertEqual(check_status(self.assessment(encounter_id), '45380', 'pfs.endoscopic_base'), 'not_verified')
        self.approve(encounter_id, '45380')
        first = self.assessment(encounter_id)
        (row,) = [r for r in self.doc(encounter_id)['details_needed'] if r['fact'] == 'performed_status']
        self.save(encounter_id, row, 'cannot_confirm')
        second = self.assessment(encounter_id)
        self.assertNotEqual(second.pk, first.pk)
        carried = review.current_decisions(second)
        self.assertEqual([second.proposals.get(pk=pk).code for pk in carried], ['45380'])
        self.assertEqual(second.proposals.get(code='45385').bucket, 'excluded')

    def test_a_context_value_and_an_answer_in_one_save_queue_one_reassessment(self):
        """A save that changes a context value re-assesses through the context change (a new context, its own
        assessment), which reads the answers saved with it: no answer recompute of the replaced context is queued."""
        visit = 'Patient seen for reflux.'
        self.provider.selections = [('99213', visit)]
        encounter_id = self.upload('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nOffice visit\n'
                                   'Date of service: 2026-10-21\n' + visit + '\n')
        doc = self.doc(encounter_id)
        facts = {r['fact']: r for r in doc['details_needed']}
        self.assertEqual((facts['patient_status']['control'], facts['em_basis']['control']), ('choice', 'confirm'))
        response = self.client.post(f'/api/encounters/{encounter_id}/details', content_type='application/json',
                                    data=json.dumps({'answers': [
                                        {'id': facts['em_basis']['id'], 'fact': 'em_basis', 'value': 'not_documented'},
                                        {'id': facts['patient_status']['id'], 'fact': 'patient_status',
                                         'value': 'established'}]}))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['reassessing'])
        self.assertFalse(models.Job.objects.filter(
            encounter_id=encounter_id, idempotency_key__contains=jobs.AGAIN_MARK + jobs.ANSWERS_MARK).exists())
        drain()
        assessment = self.assessment(encounter_id)
        self.assertEqual(assessment.context.user_values, {'patient_status': 'established'})
        # the visit's basis is asked the same way under the new context: the answer saved beside the value is read
        self.assertEqual([entry['fact'] for entry in assessment.completeness['member_answers']['applied']],
                         ['em_basis'])
        self.assertEqual(assessment.proposals.get(code='99213').bucket, 'excluded')

    def test_the_recompute_key_names_the_answer_history_so_the_old_assessment_is_never_returned(self):
        encounter_id = self.upload(HEDGED)
        (row,) = [r for r in self.doc(encounter_id)['details_needed'] if r['fact'] == 'performed_status']
        self.save(encounter_id, row, 'not_documented')
        answered = self.assessment(encounter_id)
        (saved,) = [r for r in self.doc(encounter_id)['details_needed'] if r['fact'] == 'performed_status']
        self.save(encounter_id, saved, 'cannot_confirm')  # supersedes: a new history, a new recompute
        superseded = self.assessment(encounter_id)
        self.assertNotEqual(superseded.pk, answered.pk)
        self.assertEqual(superseded.proposals.get(code='45385').support['answered']['value'], 'cannot_confirm')
        keys = list(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.ASSESS,
                                              idempotency_key__contains=jobs.AGAIN_MARK + jobs.ANSWERS_MARK)
                    .values_list('idempotency_key', flat=True))
        self.assertEqual(len(keys), len(set(keys)), keys)
        self.assertEqual(len(keys), 2)


def check_status(assessment, value, check_id):
    proposal = assessment.proposals.get(code=value)
    return next((c['status'] for c in proposal.checks if c.get('id') == check_id), None)


# --- binding: an answer to question A is never applied to question B ----------------------------------------------------

class AnswerBindingTests(DetailsCase):
    def performed(self, reason):
        return pf.proposal('sel:0', '45385', [pf.SNARE_PASSAGE], status='needs_clarification', clarifications=(
            pf.clarification('performed_status', scope='proposal', family=COLON, proposal_key='sel:0',
                             reason=reason),))

    def test_an_answer_to_question_a_is_never_applied_to_question_b_and_is_listed_as_earlier(self):
        first = self.assess(self.performed('The snare act is hedged: "possibly removed".'))
        (row,) = self.rows()
        self.assertEqual(self.post([self.answer(row, 'not_documented')]).status_code, 201)
        self.assertEqual(review.effective_view(first)['sel:0'].reason, review.DETAIL_UNAVAILABLE)
        # question B: the same code and fact, asked for another reason
        second = self.assess(self.performed('The section heading reads the act as an indication.'))
        views = review.effective_view(second)
        self.assertEqual((views['sel:0'].reason, views['sel:0'].status), ('', 'needs_clarification'))  # never applied
        (row,) = self.rows(second)
        self.assertIsNone(row['saved'])  # asked again
        (earlier,) = answers.earlier_answers(self.s.encounter, second)
        self.assertEqual((earlier['why'], earlier['affects'], earlier['label']),
                         (questions.ASKED_DIFFERENTLY, ['45385'], 'Not documented'))
        self.assertIn('asked differently', earlier['why_text'])
        # answering B binds to B, and A's answer is kept as it was
        self.assertEqual(self.post([self.answer(row, 'cannot_confirm')]).status_code, 201)
        self.assertEqual(review.effective_view(second)['sel:0'].answer, 'cannot_confirm')
        self.assertEqual(models.MemberAnswer.objects.filter(revocation__isnull=True).count(), 2)
        # no longer asked at all: both kept, both earlier, the code as the reading leaves it
        third = self.assess(pf.proposal('sel:0', '45385', [pf.SNARE_PASSAGE]))
        self.assertEqual(review.effective_view(third)['sel:0'].status, 'ready')
        self.assertEqual(sorted(item['why'] for item in answers.earlier_answers(self.s.encounter, third)),
                         [questions.NO_LONGER_ASKED, questions.NO_LONGER_ASKED])
        self.assertEqual([r for r in self.rows(third) if r['fact'] == 'performed_status'], [])

    def test_an_earlier_answer_is_withdrawn_alone(self):
        first = self.assess(self.performed('Reason A.'), asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        (a,) = [r for r in self.rows() if r['fact'] == 'performed_status']
        self.post([self.answer(a, 'not_documented')])
        self.assess(self.performed('Reason B.'), asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        (b,) = [r for r in self.rows() if r['fact'] == 'performed_status']
        self.post([self.answer(b, 'not_documented')])
        (earlier,) = answers.earlier_answers(self.s.encounter, self.s.encounter.current_assessment)
        response = self.client.post(f'/api/encounters/{self.s.encounter.pk}/details/{earlier["answer_id"]}/revoke')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(models.MemberAnswerRevocation.objects.count(), 1)  # B's answer still stands
        (b,) = [r for r in self.rows() if r['fact'] == 'performed_status']
        self.assertIsNotNone(b['saved'])
        self.assertIsNotNone(first)


# --- D7: reviewer confirmation stays off; no answer confirms a clinical fact --------------------------------------------

class ConfirmationStaysOffTests(DetailsCase):
    def test_the_confirmation_endpoint_and_the_reassessment_after_one_still_refuse(self):
        self.assess(pf.proposal('sel:0', '45385', [pf.SNARE_PASSAGE], status='needs_clarification',
                                clarifications=(pf.clarification('performed_status', scope='proposal', family=COLON,
                                                                 proposal_key='sel:0'),)))
        clarification = models.Clarification.objects.get(fact='performed_status')
        before = models.Job.objects.count()
        response = self.client.post(
            f'/api/encounters/{self.s.encounter.pk}/clarifications/{clarification.pk}/confirm',
            data=json.dumps({'candidate_id': 'x', 'attestation': 'yes'}), content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(review.confirmations_offered())
        with self.assertRaisesMessage(jobs.Refused, review.CONFIRMATIONS_NOT_OFFERED):
            jobs.reassess_after_confirmation(self.s.encounter, self.s.reviewer)
        self.assertEqual(models.Job.objects.count(), before)
        self.assertFalse(models.FindingConfirmation.objects.exists())
        # a clinical detail takes no confirming value: only "Not documented", "Cannot confirm" or the addendum
        (row,) = self.rows()
        for value in ('performed', 'documented', 'yes', 'confirm', 'done'):
            with self.subTest(value):
                response = self.post([self.answer(row, value)])
                self.assertEqual((response.status_code, response.json()['error']), (400, answers.CLINICAL))
        self.assertEqual(row['allow'], ['not_documented', 'cannot_confirm'])
        self.assertTrue(row['addendum_allowed'])
        self.assertFalse(models.MemberAnswer.objects.exists())
