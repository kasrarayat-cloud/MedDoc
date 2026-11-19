"""DECISIONS D90, D92 and D94 (the integration of round 3, 732d172d2), SYNTHETIC: each pin is the input an independent
reviewer reproduced on 62d5bf0dd, built with the suite's own builders, read by read.read, normalized with the real
linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own words.
Fictional patients; nothing is sent.

- D90 (the adjuncts review of D76, 'NEW FALSE READY AGAINST a4dcbea72'): two lesions NOT established distinct stay a
  doubt for a removal's procedural adjunct. D76 sent every pair of two different verified lesions on to the part_of
  test, so a verified part_of naming another act set apart even a lesion possibly the removal's own: the epinephrine
  injection and the hemoclips of the bleeding from "the polypectomy site" (its own lesion, no landmark and no size, so
  possibly the 12 mm polyp) made 45382 READY, and so did the author's D76 control once its vessel was not distinct.
- D92 (the currency review of D67(a), its LOW problem): 'date_unchecked' never fails the deny path's default. Words
  that do not locate are not the document's and nothing of them is stored, so no effective date could re-judge them:
  an undated document's EMR whose time words "On 11/09/2026" do not locate was held on event_time for the member's
  date 2026-11-09 for good, where the document's own 11/09/2026 makes it READY.
- D94 (the families review of D81, disagreement 1): the same-day E/M rule counts gi.unsupported too - a procedure
  outside the GI profiles, which the installed routing reads as gi.other: the office excision of a sebaceous cyst,
  read as procedure not_gi, left 99213 READY with no same-day procedure, where c2e53f8e asks separate_em.

Each pin carries a control (a subtest) that holds under the decision's mutant too: what the decision must NOT move."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import combination, coverage, events, identity, relations, verify
from studio.validation import checks
from tests.test_interpretation_events import asked, check, colonoscopy, inventory, proposal, run
from tests.test_interpretation_identity import a, act, les, snare, tg
from tests.test_interpretation_r3_adjuncts import VESSEL_POLYP, assert_asked, clips
from tests.test_interpretation_r3_currency import DATE_LINE, EMR_SAME_DAY, STATED, assessed, emr_document, time_of
from tests.test_interpretation_r3_families import MEMBER, OFFICE, PLAN, TIME, VISIT, visit, visit_facts

# --- D90: two lesions not established distinct stay a doubt for a procedural adjunct ---------------------------------

SIGMOID_POLYP = 'A 12 mm sessile polyp in the sigmoid colon was removed with a hot snare.'
SITE_BLEEDING = ('Bleeding from the polypectomy site was treated with an epinephrine injection and two hemoclips for '
                 'hemostasis.')
BIOPSY_SIGMOID = 'Cold forceps biopsies were taken from the sigmoid colon.'


def sigmoid_polyp(polyp: str) -> tuple:
    """(L1, E2): the 12 mm sigmoid ``polyp`` (P2) and its hot snare removal, as both reviews' inputs state them."""
    lesion = les('L1', polyp, 'P2', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='12 mm')
    removal = snare('E2', 'P2', technique=a('hot_snare', 'hot snare', ['P2']),
                    status_words='was removed with a hot snare',
                    target=tg('L1', 'sigmoid_colon', f'{polyp} in the sigmoid colon', ['P2']))
    return lesion, removal


def polypectomy_site_bleeding(part_of: str = 'E4'):
    """The adjuncts review's input: a colonoscopy to the cecum (E1); the 12 mm sessile sigmoid polyp L1 removed with a
    hot snare (E2, P2); the bleeding from 'the polypectomy site' - Gemini's own lesion L2 (P3, no landmark, no size) -
    treated with an epinephrine injection (E4: hemostasis verified, so a bleeding control) and two hemoclips (E3,
    part_of ``part_of``), both targeting L2. Corti proposes 45385 and 45382. (inventory, text, result)."""
    l1, removal = sigmoid_polyp('12 mm sessile polyp')
    l2 = les('L2', 'polypectomy site', 'P3')
    injection = act('E4', 'P3', 'injection', 'epinephrine injection', status_words='was treated',
                    purpose=a('hemostasis', 'for hemostasis', ['P3']),
                    target=tg('L2', 'not_stated', 'polypectomy site', ['P3']))
    clip = clips(SITE_BLEEDING, 'was treated', part_of=part_of,
                 target=tg('L2', 'not_stated', 'polypectomy site', ['P3']))
    inv, text = colonoscopy(clip, injection, polyp=removal, lesions=(l1, l2),
                            lines={'P2': SIGMOID_POLYP, 'P3': SITE_BLEEDING})
    return inv, text, run(inv, text, [('45385', SIGMOID_POLYP), ('45382', SITE_BLEEDING)])


def vessel_beside_a_biopsy(size: str = ''):
    """The review's variant of the author's D76 control (test_interpretation_r3_adjuncts): the 12 mm pedunculated
    sigmoid polyp L1 removed with a hot snare (E2, P2); hemoclips (E3, P3) on 'a visible vessel in the polypectomy base'
    (L2, no site; ``size`` its size words, none in the review's input), part_of a cold forceps biopsy of the sigmoid
    colon (E4, P4). Corti proposes 45385, 45382 and 45380. (inventory, text, result)."""
    sized = f'{size} visible vessel' if size else 'visible vessel'
    line = f'A {sized} in the polypectomy base was treated with two hemoclips for hemostasis.'
    biopsy = act('E4', 'P4', 'biopsy', 'biopsies', status_words='were taken',
                 technique=a('cold_forceps', 'Cold forceps', ['P4']),
                 target=tg('', 'sigmoid_colon', 'sigmoid colon', ['P4']))
    lesion = les('L2', sized, 'P3', size_words=size)
    clip = clips(line, 'was treated', part_of='E4', target=tg('L2', 'not_stated', sized, ['P3']))
    l1, removal = sigmoid_polyp('12 mm pedunculated polyp')
    inv, text = colonoscopy(clip, biopsy, polyp=removal, lesions=(l1, lesion),
                            lines={'P2': VESSEL_POLYP, 'P3': line, 'P4': BIOPSY_SIGMOID})
    return inv, text, run(inv, text, [('45385', VESSEL_POLYP), ('45382', line), ('45380', BIOPSY_SIGMOID)])


def bundling_relations(reading, eid: str) -> list:
    """(whole, rule) of every bundling_identity relation normalize stored on ``eid``."""
    return [(item['statement'], item['reason']) for item in reading.relations_of(eid, (relations.BUNDLING,))]


class D90NotDistinctLesionsStayADoubt(SimpleTestCase):
    """D90: an adjunct whose verified lesion is only POSSIBLY the removal's is asked, whatever its part_of names."""

    def assert_possibly_the_same(self, reading):
        """The two verified lesions are not established distinct: the polyp is possibly the adjunct's own lesion."""
        self.assertEqual((identity.verified_lesion(reading.events['E2']),
                          identity.verified_lesion(reading.events['E3'])), ('L1', 'L2'))
        self.assertEqual(reading.context.distinct('L1', 'L2'), '')
        self.assertEqual(reading.lesions['L1']['possibly_same_as'], ['L2'])

    def test_d90_the_polypectomy_site_bleeding_treated_with_an_injection_and_clips_is_asked(self):
        """The review's exact input: the clips part_of the verified injection, which IS an act (so a part_of test would
        set the clips apart), beside the removal of a lesion possibly their own. 62d5bf0dd: 45382 READY (supported);
        a4dcbea72 and D90: asked act_target (bundling), never READY."""
        with self.subTest("the review's input"):
            inv, text, result = polypectomy_site_bleeding()
            self.assertEqual(proposal(result, '45385').status, 'ready')
            assert_asked(self, result, '45382')
            reading = events.Reading.of(inv)
            removal, clip, injection = reading.events['E2'], reading.events['E3'], reading.events['E4']
            self.assert_possibly_the_same(reading)
            self.assertEqual((clip['catalogue_kind'], clip['part_of']['value'], clip['part_of']['state'],
                              injection['catalogue_kind']), ('bleeding_control', 'E4', 'verified', 'bleeding_control'))
            self.assertTrue(relations.names_an_act(reading.context, 'E4'))  # the part_of reaches D58's act arm
            self.assertEqual(relations.bundling_rule(reading.context, removal, clip), 'procedural_adjunct')
            # the rule itself (relations.identity_in_doubt), on the stored reading's context
            self.assertIs(relations.identity_in_doubt(reading.context, 'procedural_adjunct', removal, clip), True)
            self.assertIn(('E2', 'procedural_adjunct'), bundling_relations(reading, 'E3'))  # normalize stored the doubt
            self.assertEqual(coverage.bundled_reason(reading, clip), '')
            self.assertEqual((coverage.bundling_doubt(reading, clip) or {}).get('reason'), 'procedural_adjunct')
        with self.subTest('control: the same clips naming no part_of are asked as before (D41)'):
            inv, text, result = polypectomy_site_bleeding(part_of='')
            reading = events.Reading.of(inv)
            self.assert_possibly_the_same(reading)
            self.assertEqual(reading.events['E3']['part_of']['value'], '')
            self.assertIn(('E2', 'procedural_adjunct'), bundling_relations(reading, 'E3'))
            self.assertEqual(proposal(result, '45385').status, 'ready')
            assert_asked(self, result, '45382')

    def test_d90_the_visible_vessel_possibly_the_polyp_part_of_a_biopsy_is_asked(self):
        """The review's variant: the author's D76 control with the vessel made non-distinct ('visible vessel': no
        size, no site). Its part_of names the biopsy, an act. 62d5bf0dd: 45382 READY; D90: asked act_target. The biopsy
        and the removal are their own codes, READY."""
        with self.subTest("the review's variant"):
            inv, text, result = vessel_beside_a_biopsy()
            self.assertEqual([proposal(result, code).status for code in ('45385', '45380')], ['ready', 'ready'])
            assert_asked(self, result, '45382')
            reading = events.Reading.of(inv)
            removal, clip = reading.events['E2'], reading.events['E3']
            self.assert_possibly_the_same(reading)
            self.assertEqual((clip['catalogue_kind'], clip['part_of']['value'], clip['part_of']['state'],
                              reading.events['E4']['catalogue_kind']), ('bleeding_control', 'E4', 'verified', 'biopsy'))
            self.assertTrue(relations.names_an_act(reading.context, 'E4'))
            self.assertIs(relations.identity_in_doubt(reading.context, 'procedural_adjunct', removal, clip), True)
            self.assertEqual((coverage.bundling_doubt(reading, clip) or {}).get('reason'), 'procedural_adjunct')
        with self.subTest('control: a 2 mm vessel, distinct by sizes, is set apart by the part_of naming the biopsy'):
            inv, text, result = vessel_beside_a_biopsy('2 mm')  # D76's own control: D90 reaches no DISTINCT pair
            reading = events.Reading.of(inv)
            self.assertEqual((reading.context.distinct('L1', 'L2'), reading.lesions['L1']['possibly_same_as']),
                             ('sizes', []))
            self.assertIs(relations.identity_in_doubt(reading.context, 'procedural_adjunct', reading.events['E2'],
                                                      reading.events['E3']), False)
            self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
            self.assertEqual([proposal(result, code).status for code in ('45385', '45382', '45380')],
                             ['ready', 'ready', 'ready'])


# --- D92: date_unchecked never fails the deny path's default ------------------------------------------------------

EMR_LINE = 'A 25 mm flat polyp in the cecum was resected by EMR.'
SAME_DAY_WORDS = 'On 11/09/2026'
UNLOCATED = 'events[2].time: its words were not found in its own passages, so the frame default was accepted.'


class D92DateUncheckedNeverFailsTheDefault(SimpleTestCase):
    """D92: Gemini's time words that do not locate are not the document's; a date in them that no service date can check
    yet (date_unchecked) never denies the frame default - nothing of them is stored, so no date could lift the hold."""

    def test_d92_the_undated_emrs_unlocated_same_day_words_take_the_default_and_45390_is_ready(self):
        """The currency review's input: an undated document; the EMR line 'A 25 mm flat polyp in the cecum was resected
        by EMR.' (E3), its time current_encounter worded 'On 11/09/2026', words that do not locate; the member's date
        2026-11-09; Corti proposes 45380 and 45390. 62d5bf0dd: the time unverified ['words_unlocated',
        'date_unchecked'] with nothing stored, 45390 held on event_time for good; a4dcbea72 and D92: the frame default,
        45390 READY - as the document's own 11/09/2026 makes it."""
        with self.subTest("the review's input"):
            inv, text, line = emr_document(EMR_LINE, SAME_DAY_WORDS)
            member = assessed(inv, text, line, '2026-11-09')
            p = proposal(member, '45390')
            self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                             ('selected', 'ready', [], 'supported'))
            self.assertEqual(proposal(member, '45380').status, 'ready')
            self.assertIsNone(inv.encounter_facts['date_of_service']['value'])  # undated: no service date at normalize
            self.assertNotIn('11/09/2026', text)  # the words locate nowhere
            # the deny path's verdict is date_unchecked alone: exactly the reason D92 keeps from failing the default
            self.assertEqual(tuple(verify.time_words('current_encounter', SAME_DAY_WORDS, None).reasons),
                             ('date_unchecked',))
            stored = time_of(inv)
            self.assertEqual((stored['value'], stored['basis'], stored['state'], stored['reasons'], stored['words'],
                              stored['literals']), ('current_encounter', 'default', 'verified', [], None, {}))
            self.assertEqual(stored['checks'][:2], ['default', 'default_after_unlocated_words'])
            self.assertIn(UNLOCATED, inv.verification['problems'])
            self.assertEqual(next(item for item in inv.events['events'] if item['id'] == 'E3')['current'], 'yes')
            # the member-date path and the document-date path agree (the review: they diverged on 62d5bf0dd)
            dated, dated_text, _ = emr_document(EMR_LINE, SAME_DAY_WORDS, date_lines={'P0': DATE_LINE},
                                                date_of_service=STATED)
            document = assessed(dated, dated_text, line)
            self.assertEqual([proposal(member, code).status for code in ('45380', '45390')],
                             [proposal(document, code).status for code in ('45380', '45390')])
        with self.subTest('control: a date the document CAN check still denies the default (date_mismatch, EB2)'):
            dated, dated_text, _ = emr_document(EMR_LINE, 'On 03/14/2024', date_lines={'P0': DATE_LINE},
                                                date_of_service=STATED)
            stored = time_of(dated)
            self.assertEqual((stored['basis'], stored['state'], stored['reasons']),
                             ('absent', 'unverified', ['words_unlocated', 'date_mismatch']))
            p = proposal(assessed(dated, dated_text, line, '2026-11-09'), '45390')
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['event_time']))
        with self.subTest("control: D35's marker in unlocated words still denies the default on the undated document"):
            undated, undated_text, _ = emr_document(EMR_LINE, 'At the original procedure')
            stored = time_of(undated)
            self.assertEqual((stored['basis'], stored['state'], stored['reasons']),
                             ('absent', 'unverified', ['words_unlocated', 'other_occasion']))
            p = proposal(assessed(undated, undated_text, line, '2026-11-09'), '45390')
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['event_time']))
        with self.subTest('control: located day words stay date_unchecked until a date decides them (D67)'):
            located, located_text, located_line = emr_document(EMR_SAME_DAY, SAME_DAY_WORDS)
            self.assertEqual((time_of(located)['basis'], time_of(located)['reasons']), ('stated', ['date_unchecked']))
            self.assertEqual(proposal(assessed(located, located_text, located_line, '2026-11-09'), '45390').status,
                             'ready')


# --- D94: the same-day E/M rule counts gi.unsupported -----------------------------------------------------------------

EXCISION = 'Excision of a 1 cm sebaceous cyst on the upper back was performed in the office today.'
CYST_TEXT = {'V1': VISIT, 'V2': TIME, 'P2': EXCISION, 'P3': PLAN}  # the families review's exact document
OFFICE_CYST = {**OFFICE, 'P2': EXCISION}  # disagreement 1: finding 20's office lines, the banding line replaced
REVIEW_WORDS = {'procedure': a('not_gi', 'Excision of a 1 cm sebaceous cyst', ['P2']),
                'time': a('current_encounter', 'today', ['P2'])}  # the review's probe: procedure and time words


def excision(**changes) -> dict:
    """The office excision as Gemini reads it (E1, P2): kind other, procedure not_gi (gi.unsupported), performed, the
    current encounter and the documenting team by the frame defaults unless ``changes`` say otherwise."""
    changes.setdefault('procedure', a('not_gi'))
    return act('E1', 'P2', 'other', 'Excision of a 1 cm sebaceous cyst', status_words='was performed', **changes)


def office_visit(procedure: dict, lines=None):
    """(inventory, text) of the office note: the visit (E0, office_em) and its total time, beside ``procedure``."""
    return inventory(lines or CYST_TEXT, events=[visit(), procedure], visits=[visit_facts()])


def em(inv, text, user_values=MEMBER):
    return proposal(run(inv, text, [('99213', VISIT)], user_values=user_values), '99213')


class D94SameDayCountsGiUnsupported(SimpleTestCase):
    """D94: a procedure outside the GI profiles done on the date of service makes a procedure day."""

    VARIANTS = (
        ('the review: its document, procedure and time words', CYST_TEXT, REVIEW_WORDS),
        ("the review: finding 20's office lines, procedure and time words", OFFICE_CYST, REVIEW_WORDS),
        ('the D81 author: no procedure words', CYST_TEXT, {}),
        ("the D81 author: procedure words 'Excision'", CYST_TEXT, {'procedure': a('not_gi', 'Excision', ['P2'])}),
        ("disagreement 1: finding 20's office lines, no procedure words", OFFICE_CYST, {}),
    )

    def test_d94_the_office_excision_of_a_sebaceous_cyst_asks_separate_em(self):
        """The families review's input (disagreement 1): 99213 alone, the member's setting office and patient status
        established. 62d5bf0dd and a4dcbea72: READY, 'No same-day procedure is documented'; c2e53f8e and D94: held,
        separate_em. With no member values it asks separate_em beside setting and patient_status."""
        for label, lines, changes in self.VARIANTS:
            with self.subTest(label):
                inv, text = office_visit(excision(**changes), lines)
                self.assertEqual(events.Reading.of(inv).events['E1']['family'], 'gi.unsupported')
                p = em(inv, text)
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['separate_em']))
                same_day = check(p, 'em.same_day_procedure')
                self.assertEqual(same_day.status, 'warn')
                self.assertIn('Service outside the GI profiles is', same_day.detail)
                self.assertIn('a significant, separately identifiable E/M service is not established',
                              p.clarifications[0].reason)
                self.assertIsNone(check(p, 'em.same_day_coverage'))
                self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
                p = em(inv, text, user_values=None)
                self.assertEqual((p.status, sorted(asked(p))),
                                 ('needs_clarification', ['patient_status', 'separate_em', 'setting']))
        with self.subTest("D94: the excision's procedure left 'unknown' (family '') is a possible same-day procedure"):
            inv, text = office_visit(excision(procedure=a('unknown')), CYST_TEXT)
            self.assertEqual(events.Reading.of(inv).events['E1']['family'], '')
            p = em(inv, text)
            self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['separate_em']))
            self.assertIn(combination.UNIDENTIFIED_PROCEDURE, check(p, 'em.same_day_procedure').detail)
        with self.subTest('control: the excision done at an earlier encounter makes no procedure day (C-3)'):
            earlier = {**CYST_TEXT, 'P2': EXCISION.replace('in the office today', 'in 2024')}
            inv, text = office_visit(excision(time=a('earlier_encounter', 'in 2024', ['P2'])), earlier)
            p = em(inv, text)
            self.assertEqual((p.status, asked(p)), ('ready', []))
            self.assertEqual(check(p, 'em.same_day_coverage').status, 'not_verified')
