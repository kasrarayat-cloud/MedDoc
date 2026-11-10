"""DECISIONS D80 and D81 (the round-3 refutation of a4dcbea72, findings 19 and 20), SYNTHETIC: the family a code or a
same-day procedure belongs to.

- D80: a code on the catalogue route of a RECOGNISED-ONLY family (mapping.recognised_only: gi.sedation's 99152 and
  99153, which the catalogue recognises and lists for review but does not reconcile, and which gi.profiles marks not
  supported) is not assessed: it is held with the performed_status question (wording.performed_question) and a check
  saying the service is recognised, not assessed, by CPT Studio - never READY and never excluded, whatever the
  inventory states. Finding 19's two variants (8 minutes with no independent observer; a 3-year-old) and a control
  (25 minutes, an observer, an adult) are all held; a4dcbea72 made 99152 READY on each.
- D81: the same-day E/M rule counts an event of gi.other (an office hemorrhoid banding, an anoscopy) as a same-day
  procedure, as the legacy rule (engine._same_day_family) does: finding 20's 99213 asks separate_em with and without
  member values; its control, an in-office flexible sigmoidoscopy, asked already.

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read and normalized
with the real linked steps, then assessed through assess.assess with a synthetic Corti response citing the document's own
spans (the S08 builders). Nothing is sent."""
from __future__ import annotations

from dataclasses import replace
from unittest import mock

from django.test import SimpleTestCase

from studio.gi import catalogue, profiles
from studio.interpretation import combination, events, lexicon, mapping, wording
from studio.types import EvidenceSpan, FamilyFinding
from studio.validation import checks, engine
from tests.test_interpretation_events import COLONOSCOPE, asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, tg

# --- D80: the sedation documents (finding 19) ----------------------------------------------------------------------------

EIGHT_MINUTES = ('Sedation: Moderate sedation was given by me (midazolam 2 mg IV); no independent trained observer was '
                 'present. Intraservice time 8 minutes.')
CHILD = 'Patient: Tobias Linde (fictional), 3-year-old boy.'
THREE_YEAR_OLD = ('Sedation: Moderate sedation was given by me (midazolam 0.5 mg/kg by mouth) with Noel Fairbanks, RN, as '
                  'independent trained observer. Intraservice time 25 minutes.')
ADULT = 'Patient: Mara Holt (fictional), 54-year-old woman.'
TWENTY_FIVE_MINUTES = ('Sedation: Moderate sedation was given by me (midazolam 3 mg IV) with Noel Fairbanks, RN, as '
                       'independent trained observer. Intraservice time 25 minutes.')
NINETEEN_MINUTES = ('Sedation: Moderate sedation was given by me (midazolam 3 mg IV) with Noel Fairbanks, RN, as '
                    'independent trained observer. Intraservice time 19 minutes.')
NOT_GIVEN = 'Sedation: No sedation was given.'
RECOGNISED = 'is recognised by CPT Studio and listed for review, not assessed'


def performed_twin(line: str) -> str:
    """The same line in the wording the installed release reads as performed ('was performed by me')."""
    return line.replace('was given by me', 'was performed by me')


def sedation(passage: str = 'P2', status: str = 'performed', status_words: str = 'was given by me',
             kind_words: str = 'Moderate sedation', **changes) -> dict:
    """Finding 19's E2: kind moderate_sedation, procedure sedation (the kind's words, 'Moderate sedation'), status
    performed ('was given by me'), the current encounter and the documenting team by the frame defaults."""
    return act('E2', passage, 'moderate_sedation', kind_words, status=status, status_words=status_words,
               procedure=a('sedation', kind_words, [passage]), **changes)


def sedated_colonoscopy(line: str, patient: str = '', event=None):
    """A colonoscopy to the cecum (E1, P1) with the sedation stated in ``line`` (E2, P2; its status words as the line
    words them), and the patient line P3."""
    lines = {'P1': COLONOSCOPE, 'P2': line}
    if patient:
        lines['P3'] = patient
    stated = 'was performed by me' if 'was performed by me' in line else 'was given by me'
    return inventory(lines, events=[exam(), event if event is not None else sedation(status_words=stated)],
                     reach=[reached()])


# --- D81: the office note (finding 20) -----------------------------------------------------------------------------------

MEMBER = {'setting': 'office', 'patient_status': 'established'}
VISIT = 'Office visit: established patient seen today for rectal bleeding.'
TIME = 'Total time on the date of the encounter: 25 minutes.'
ANOSCOPY = 'Anoscopy showed grade 2 internal hemorrhoids.'
BANDING = 'Rubber band ligation of one internal hemorrhoid was performed in the office today.'
PLAN = 'Plan: fiber; recheck in 6 weeks.'
FLEX_SIG = 'A flexible sigmoidoscopy was performed in the office today.'
OFFICE = {'V1': VISIT, 'V2': TIME, 'P1': ANOSCOPY, 'P2': BANDING, 'P3': PLAN}


def visit() -> dict:
    """Finding 20's E0: an office E/M visit (office_em)."""
    return act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
               procedure=a('office_em', 'Office visit', ['V1']))


def visit_facts() -> dict:
    """The visit's basis total time, separately_identifiable not stated."""
    return {'event': 'E0', 'basis': a('total_time', '25 minutes', ['V2']), 'separately_identifiable': a('not_stated')}


def banding(procedure=None, **changes) -> dict:
    """Finding 20's E1: a band ligation of procedure other_gi (gi.other), performed, current, by the documenting team."""
    return act('E1', 'P2', 'band_ligation', 'Rubber band ligation', status_words='was performed',
               procedure=procedure if procedure is not None else a('other_gi'), **changes)


def office(*procedures, lines=None):
    return inventory({**OFFICE, **(lines or {})}, events=[visit(), *procedures], visits=[visit_facts()])


def em(inv, text, user_values=MEMBER, codes=None):
    return proposal(run(inv, text, codes or [('99213', VISIT)], user_values=user_values), '99213')


class RecognisedOnly(SimpleTestCase):
    """D80: a recognised-only family's code is held - never READY, never excluded."""

    def assert_recognised_hold(self, p, code):
        self.assertEqual((p.bucket, p.status, p.reinstatable), ('selected', 'needs_clarification', False))
        self.assertEqual(asked(p), ['performed_status'])
        self.assertEqual(p.clarifications[0].question, wording.performed_question(code))
        self.assertIn(RECOGNISED, p.clarifications[0].reason)
        status = check(p, 'service.status')
        self.assertEqual(status.status, 'warn')
        self.assertIn(f'Moderate sedation by the performing physician {RECOGNISED}', status.detail)
        self.assertIn('intraservice time when the endoscopist provided moderate sedation', status.detail)
        self.assertIn('Held for the reviewer, not excluded.', status.detail)
        self.assertEqual(check(p, 'events.match').status, 'warn')
        self.assertEqual((p.support['reason'], p.support['state'], p.support['acts']),
                         (mapping.RECOGNISED_ONLY, 'uncertain', []))
        self.assertEqual(p.exclusion_reason, '')

    def held_beside_its_colonoscopy(self, line, patient=''):
        for wording_ in (line, performed_twin(line)):
            with self.subTest(line=wording_):
                inv, text = sedated_colonoscopy(wording_, patient)
                result = run(inv, text, [('99152', wording_), ('45378', COLONOSCOPE)])
                self.assert_recognised_hold(proposal(result, '99152'), '99152')
                self.assertEqual(proposal(result, '45378').status, 'ready')  # the rest of the encounter proceeds

    def test_d80_only_the_sedation_codes_are_recognised_only(self):
        """mapping.recognised_only reads CodeLink.supported and CodeLink.support: of the catalogue's codes exactly
        gi.sedation's 99152 and 99153; never route (b) (46221) or route (d) (99151, 45305, 99223). Fail-closed: a family
        the catalogue marks recognised or unsupported, or has no entry for, or that gi.profiles marks not supported, is
        recognised-only."""
        self.assertEqual({code for code in catalogue.CODES if mapping.recognised_only(mapping.code_link(code))},
                         {'99152', '99153'})
        for code in ('46221', '99151', '45305', '99223', '45378', '99213'):
            with self.subTest(code=code):
                self.assertFalse(mapping.recognised_only(mapping.code_link(code)))
        capsule = catalogue.CATALOGUE['gi.capsule']
        for patch in ({'gi.capsule': replace(capsule, support=catalogue.RECOGNISED)},
                      {'gi.capsule': replace(capsule, support=catalogue.UNSUPPORTED)}):
            with self.subTest(support=patch['gi.capsule'].support), mock.patch.dict(catalogue.CATALOGUE, patch):
                self.assertTrue(mapping.recognised_only(mapping.code_link('91110')))
        with self.subTest('no catalogue entry'), mock.patch.dict(catalogue.CATALOGUE, {}, clear=False):
            del catalogue.CATALOGUE['gi.capsule']
            self.assertTrue(mapping.recognised_only(mapping.code_link('91110')))
        with self.subTest('profile not supported'), mock.patch.dict(profiles.PROFILES, {
                'gi.capsule': replace(profiles.PROFILES['gi.capsule'], supported=False)}):
            self.assertTrue(mapping.recognised_only(mapping.code_link('91110')))
        self.assertFalse(mapping.recognised_only(mapping.code_link('91110')))
        self.assertEqual(mapping.documentation('gi.sedation'), catalogue.CATALOGUE['gi.sedation'].documentation)
        self.assertEqual(mapping.documentation('gi.em_other'), ())

    def test_d80_finding_19_eight_minutes_with_no_observer_is_held(self):
        """Finding 19's exact input (a4dcbea72: 99152 READY with no question; c2e53f8e: held, performed_status), and
        the same input with the performer's words 'by me' and with the installed release's performed wording."""
        self.held_beside_its_colonoscopy(EIGHT_MINUTES)
        inv, text = sedated_colonoscopy(EIGHT_MINUTES, event=sedation(performer=a('documenting_team', 'by me', ['P2'])))
        result = run(inv, text, [('99152', EIGHT_MINUTES), ('45378', COLONOSCOPE)])
        self.assert_recognised_hold(proposal(result, '99152'), '99152')

    def test_d80_finding_19_a_three_year_old_is_held(self):
        """Finding 19's variant: a 3-year-old (a patient under 5 takes 99151), 25 minutes, an observer."""
        self.held_beside_its_colonoscopy(THREE_YEAR_OLD, CHILD)

    def test_d80_the_control_twenty_five_minutes_an_observer_an_adult_is_held(self):
        """The control a document supports - 25 minutes, an independent observer, an adult - is held too: CPT Studio
        does not assess the family, so it never reads one as ready."""
        self.held_beside_its_colonoscopy(TWENTY_FIVE_MINUTES, ADULT)

    def test_d80_a_sedation_stated_not_done_is_held_never_excluded(self):
        """A sedation stated not done, cited by its own words, excluded 99152 at a4dcbea72 (7.5); D80 holds it - a
        recognised-only code is never excluded by CPT Studio."""
        denied = sedation(status='not_performed', status_words='No sedation was given', kind_words='sedation')
        inv, text = sedated_colonoscopy(NOT_GIVEN, event=denied)
        result = run(inv, text, [('99152', 'No sedation was given'), ('45378', COLONOSCOPE)])
        self.assert_recognised_hold(proposal(result, '99152'), '99152')
        self.assertFalse(any(p.code == '99152' and p.bucket == 'excluded' for p in result.proposals))

    def test_d80_the_add_on_alone_and_with_its_primary_are_held(self):
        """99153 alone on a 19-minute sedation (a4dcbea72: READY) is held; 99152 and 99153 together are each held with
        their own performed_status question (they account for no event, so they no longer compete for one)."""
        inv, text = sedated_colonoscopy(NINETEEN_MINUTES, ADULT)
        result = run(inv, text, [('99153', NINETEEN_MINUTES), ('45378', COLONOSCOPE)])
        self.assert_recognised_hold(proposal(result, '99153'), '99153')
        inv, text = sedated_colonoscopy(TWENTY_FIVE_MINUTES, ADULT)
        result = run(inv, text, [('99152', TWENTY_FIVE_MINUTES), ('99153', TWENTY_FIVE_MINUTES),
                                 ('45378', COLONOSCOPE)])
        for code in ('99152', '99153'):
            with self.subTest(code=code):
                self.assert_recognised_hold(proposal(result, code), code)
        held = next(c for c in result.encounter_checks if c.id == 'services.unsupported')
        self.assertIn('Moderate sedation by the performing physician (99152 and 99153)', held.detail)

    def test_d80_the_hold_reads_the_family_not_the_document(self):
        """events.evaluate itself: the hold accounts for no event, reads none and quotes the code's own passage."""
        inv, text = sedated_colonoscopy(EIGHT_MINUTES)
        start = text.index(EIGHT_MINUTES)
        kept = (EvidenceSpan(0, start, start + len(EIGHT_MINUTES), EIGHT_MINUTES, True),)
        evaluation = events.evaluate('99152', kept, events.Reading.of(inv))
        self.assertEqual((evaluation.state, evaluation.reason, evaluation.supporting, evaluation.read),
                         ('uncertain', mapping.RECOGNISED_ONLY, (), ()))
        self.assertEqual(evaluation.question.passages, ({'start': start, 'end': start + len(EIGHT_MINUTES),
                                                         'text': EIGHT_MINUTES},))
        self.assertEqual(evaluation.question.events, ())


class SameDayOtherGI(SimpleTestCase):
    """D81: a gi.other procedure on the date of service makes a procedure day, as the legacy rule reads it."""

    def test_d81_the_same_day_families_are_the_legacy_rules(self):
        """SAME_DAY_FAMILIES equals engine._same_day_family over every gi.profiles family: a procedure profile, or
        gi.other."""
        legacy = {slug for slug in profiles.PROFILES if engine._same_day_family(FamilyFinding(slug, 'performed', ()))}
        # D94 (integration): plus gi.unsupported - the installed routing reads a procedure outside the GI profiles
        # ("Excision of a 1 cm sebaceous cyst ... in the office today") as gi.other, where Gemini says not_gi
        self.assertEqual(set(combination.SAME_DAY_FAMILIES), legacy | {'gi.unsupported'})
        self.assertIn('gi.other', combination.SAME_DAY_FAMILIES)
        self.assertTrue(set(lexicon.PROCEDURAL_FAMILIES) < set(combination.SAME_DAY_FAMILIES))
        for family in ('gi.office_em', 'gi.em_other', 'gi.sedation'):
            self.assertNotIn(family, combination.SAME_DAY_FAMILIES)

    def test_d81_finding_20_an_office_banding_asks_separate_em(self):
        """Finding 20's office note: Corti proposes only 99213. With the member's setting and patient status it asks
        separate_em (a4dcbea72: READY); with none it asks separate_em beside them (a4dcbea72: setting and
        patient_status only). The same-day check names the other GI service, never 'no same-day procedure'."""
        inv, text = office(banding())
        p = em(inv, text)
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['separate_em']))
        self.assertEqual(check(p, 'em.same_day_procedure').status, 'warn')
        self.assertIn('Other GI service is', check(p, 'em.same_day_procedure').detail)
        self.assertIn('a significant, separately identifiable E/M service is not established',
                      p.clarifications[0].reason)
        self.assertIsNone(check(p, 'em.same_day_coverage'))
        self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
        p = em(inv, text, user_values=None)
        self.assertEqual(p.status, 'needs_clarification')
        self.assertEqual(sorted(asked(p)), ['patient_status', 'separate_em', 'setting'])

    def test_d81_finding_20_with_the_banding_words_or_an_anoscopy_examination(self):
        """The banding stated with its procedure words and time words, and the anoscopy as a gi.other examination
        alone: each makes the date a procedure day."""
        variants = (
            ('procedure and time words', [banding(procedure=a('other_gi', 'Rubber band ligation', ['P2']),
                                                  time=a('current_encounter', 'today', ['P2']))]),
            ('placed at the anal canal', [banding(target=tg('', 'anal_canal', 'one internal hemorrhoid', ['P2']))]),
            ('an anoscopy examination', [act('E1', 'P1', 'examination', 'Anoscopy', status_words='showed',
                                             procedure=a('other_gi', 'Anoscopy', ['P1']))]),
        )
        for label, procedures in variants:
            with self.subTest(label):
                inv, text = office(*procedures)
                p = em(inv, text)
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['separate_em']))

    def test_d81_the_control_an_office_flexible_sigmoidoscopy_already_asks(self):
        """Finding 20's control: an in-office flexible sigmoidoscopy (a procedural family) asked separate_em before D81
        and still does."""
        flex = act('E1', 'P4', 'examination', 'flexible sigmoidoscopy', status_words='was performed',
                   procedure=a('flex_sig', 'flexible sigmoidoscopy', ['P4']))
        inv, text = office(flex, lines={'P4': FLEX_SIG})
        p = em(inv, text)
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['separate_em']))
        self.assertIn('Flexible sigmoidoscopy is documented as performed on the same date',
                      check(p, 'em.same_day_procedure').detail)

    def test_d81_a_banding_of_another_date_makes_no_procedure_day(self):
        """By date of service (C-3): a banding verified at an earlier encounter makes no procedure day, and the visit
        alone is READY with its member values, as before."""
        earlier = {'P2': 'Rubber band ligation of one internal hemorrhoid was performed in 2024.'}
        inv, text = office(banding(time=a('earlier_encounter', 'in 2024', ['P2'])), lines=earlier)
        p = em(inv, text)
        self.assertEqual((p.status, asked(p)), ('ready', []))
        self.assertEqual(check(p, 'em.same_day_coverage').status, 'not_verified')
        inv, text = office()
        self.assertEqual(em(inv, text).status, 'ready')
