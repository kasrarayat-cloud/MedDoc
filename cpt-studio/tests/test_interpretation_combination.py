"""The combination rules (Gemini migration slice S08; design/FINAL.md 7.9, as design/ADJUDICATION.md C-3 and C-4 amend it),
SYNTHETIC: one test per row - base (beside a code of its session, beside a reportable act no code accounts for, beside a
doubted act, two E/M codes of one visit, and the examination-only EUS codes as their family's base: beside an FNA
code, beside an uncovered FNA), base-within (C-4's structural EGD inside an upper EUS, whatever the EUS device but the
digital one, C3's part_of, a lower EUS, an uncoded EUS), competing (P-ADMIT2), the same-day E/M by date of service
(C-3: a procedure done today, one done "earlier today", a separately identifiable visit stated, an undatable
procedure, a procedure of another date), the separate-lesion modifier review (distinct lesions only) and the
endoscopic rows - with every hold's wording pinned equal to the legacy builder for equivalent inputs. Nothing is
sent."""
from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.interpretation import combination, coverage, events
from studio.validation import checks, engine
from tests.test_interpretation_events import (COLONOSCOPE, EUS_LINES, FNA, L1, POLYP, asked, check, colonoscopy, eus,
                                              exam, inventory, proposal, reached, removed, run)
from tests.test_interpretation_identity import a, act, les, sc, tg

MEMBER = {'setting': 'office', 'patient_status': 'established'}
# The examination-only EUS codes (their profile covers only the EUS examination): 43231, 43237, 43259, 45341, 45391
# and 44406.
EXAM_ONLY = tuple(code for code, profile in catalogue.CODES.items()
                  if profile.family == 'gi.eus' and profile.covers == ('eus_exam',))
VISIT_LINE = 'Office visit: established patient seen this afternoon for iron-deficiency anemia.'
TIME_LINE = 'Total time on the date of the encounter: 30 minutes.'


def visit(**changes) -> dict:
    return act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen this afternoon',
               procedure=a('office_em', 'Office visit', ['V1']), **changes)


def visit_facts(separate=None) -> dict:
    return {'event': 'E0', 'basis': a('total_time', '30 minutes', ['V2']),
            'separately_identifiable': separate or a('not_stated')}


def office(*procedures, lines=None, separate=None, **options):
    base = {'V1': VISIT_LINE, 'V2': TIME_LINE}
    base.update(lines or {})
    return inventory(base, events=[visit(), *procedures], visits=[visit_facts(separate)], **options)


class Base(SimpleTestCase):
    def test_a_base_code_beside_a_code_of_its_session(self):
        inv, text = colonoscopy()
        p = proposal(run(inv, text, [('45378', COLONOSCOPE), ('45385', POLYP)]), '45378')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
        held, question = combination.base_hold('45378', 'gi.colonoscopy', p.key, ('45385',), 'colonoscopy')
        self.assertEqual(check(p, 'services.base_included'), held)
        self.assertEqual(p.clarifications[0], question)

    def test_a_base_code_beside_a_reportable_act_no_code_accounts_for(self):
        inv, text = colonoscopy()
        p = proposal(run(inv, text, [('45378', COLONOSCOPE)]), '45378')
        self.assertIn('The documented colonoscopy includes snare removal, which this diagnostic code does not account '
                      'for', check(p, 'services.base_included').detail)

    def test_a_base_code_beside_a_doubted_act(self):
        """Base rule (c): an act stated in doubt may have been done, and then the base code is included in it."""
        doubt = act('E3', 'P3', 'biopsy', 'biopsies', status='uncertain', status_words='It is unclear whether')
        inv, text = colonoscopy(doubt, polyp=act('E2', 'P2', 'other', 'polyp'),
                                lines={'P3': 'It is unclear whether biopsies were taken.'})
        p = proposal(run(inv, text, [('45378', COLONOSCOPE)]), '45378')
        self.assertIn('includes forceps biopsy (stated in doubt)', check(p, 'services.base_included').detail)

    def test_a_base_code_alone_is_ready(self):
        inv, text = colonoscopy(polyp=act('E2', 'P2', 'other', 'polyp'))
        self.assertEqual(proposal(run(inv, text, [('45378', COLONOSCOPE)]), '45378').status, 'ready')

    def test_an_examination_only_eus_code_beside_an_fna_code_of_its_session_is_held(self):
        """Base rule (a) over an examination-only EUS code (covers only eus_exam: FINAL 7.3 makes the EUS examination its
        act, so it is its family's base): beside the FNA code of its session it is held, so the EUS examination is
        never accounted for twice. Each origin: both Corti's, or the examination code a participant's."""
        inv, text = eus(FNA)
        result = run(inv, text, [('43242', EUS_LINES['P3']), ('43259', EUS_LINES['P1'])])
        p = proposal(result, '43259')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
        held, question = combination.base_hold('43259', 'gi.eus', p.key, ('43242',), 'endoscopic ultrasound')
        self.assertEqual((check(p, 'services.base_included'), p.clarifications[0]), (held, question))
        self.assertEqual(proposal(result, '43242').status, 'ready')
        from tests.test_interpretation_assess import participant
        admitted = run(inv, text, [('43242', EUS_LINES['P3'])],
                       participants=(participant('astra', text, [('43259', EUS_LINES['P1'])]),))
        p = proposal(admitted, '43259')
        self.assertEqual((p.support['origin'], asked(p)), ('participant', ['base_included']))

    def test_every_examination_only_eus_code_beside_an_uncovered_fna_is_held(self):
        """Base rule (b): the session's reportable FNA, which no counted code accounts for, holds every
        examination-only EUS code, as a colonoscopy's snare holds 45378; on an examination-only document each is
        ready (the control)."""
        self.assertEqual(len(EXAM_ONLY), 6)
        with_fna, fna_text = eus(FNA)
        alone, alone_text = eus()
        for code in EXAM_ONLY:
            with self.subTest(code=code):
                p = proposal(run(with_fna, fna_text, [(code, EUS_LINES['P1'])]), code)
                self.assertEqual(asked(p), ['base_included'])
                self.assertIn('The documented endoscopic ultrasound includes fine-needle aspiration or biopsy, which '
                              'this diagnostic code does not account for', check(p, 'services.base_included').detail)
                control = proposal(run(alone, alone_text, [(code, EUS_LINES['P1'])]), code)
                self.assertIsNone(check(control, 'services.base_included'))

    def test_an_em_add_on_is_no_base_code(self):
        """Only a base profile and an examination-only profile are base codes: 99417 (prolonged visit time, an add-on)
        is neither, so it holds nothing as a base would."""
        self.assertEqual([code for code in ('99213', '99417', '43259', '43242', '45378', '45385')
                          if combination._base(code)], ['99213', '43259', '45378'])

    def test_two_em_codes_of_one_visit_hold_each_other(self):
        """The legacy base rule reads E/M profiles as base codes that cover the visit (R3 Q7), and an office visit's own
        event is never an act beside itself."""
        inv, text = office()
        result = run(inv, text, [('99213', VISIT_LINE), ('99214', TIME_LINE)], user_values=MEMBER)
        self.assertEqual([asked(proposal(result, code)) for code in ('99213', '99214')],
                         [['base_included'], ['base_included']])
        alone = run(inv, text, [('99213', VISIT_LINE)], user_values=MEMBER)
        self.assertEqual(proposal(alone, '99213').status, 'ready')


EGD_EUS = {'P1': 'A standard gastroscope was advanced to the second portion of the duodenum.',
           'P2': 'A linear echoendoscope was then introduced; the pancreatic head mass was sampled with a 22-gauge '
                 'needle.'}


def egd_eus(eus_target=('pancreas', 'pancreatic head'), part_of='', eus_technique=None):
    """An EGD (E1) and an upper EUS (E2) with its FNA (E3); ``eus_technique`` the EUS examination's device
    (the echoendoscope as an endoscope by default)."""
    target = tg('', eus_target[0], eus_target[1], ['P2'])
    technique = eus_technique or a('endoscope', 'echoendoscope', ['P2'])
    return inventory(EGD_EUS, events=[
        exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1']), part_of=part_of),
        act('E2', 'P2', 'examination', 'echoendoscope', status_words='was then introduced',
            procedure=a('eus', 'echoendoscope', ['P2']), target=target, technique=technique),
        act('E3', 'P2', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'echoendoscope', ['P2']),
            technique=a('needle', '22-gauge needle', ['P2']), target=target)],
        reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])


class BaseWithin(SimpleTestCase):
    def test_c4_an_egd_beside_an_upper_eus_is_held_beside_its_code(self):
        inv, text = egd_eus()
        result = run(inv, text, [('43235', EGD_EUS['P1']), ('43242', EGD_EUS['P2'])])
        p = proposal(result, '43235')
        self.assertEqual(asked(p), ['base_included'])
        held, question = combination.base_within_hold('43235', 'gi.egd', p.key, ('43242',), 'upper endoscopy')
        self.assertEqual((check(p, 'services.base_included'), p.clarifications[0]), (held, question))

    def test_c4_an_egd_beside_an_uncoded_eus_is_held_beside_none(self):
        inv, text = egd_eus()
        p = proposal(run(inv, text, [('43235', EGD_EUS['P1'])]), '43235')
        self.assertIn('Is 43235 reported separately from the endoscopic ultrasound', p.clarifications[0].question)

    def test_c4_an_eus_examination_whose_device_is_not_the_endoscope_is_still_the_session(self):
        """FINAL 5.6 E13 sets apart only a digital examination (technique manual): an EUS examination whose device
        is verified as another class (the echoendoscope read as ``other``) is still the EUS session, so C-4's
        structural inclusion holds the EGD base code beside the EUS code, as with the endoscope."""
        inv, text = egd_eus(eus_technique=a('other', 'linear echoendoscope', ['P2']))
        self.assertEqual(inv.events['events'][1]['technique']['state'], 'verified')
        sessions = coverage.sessions(events.Reading.of(inv))
        self.assertEqual((sessions['gi.eus'].event, sessions['gi.egd'].part_of), ('E2', 'gi.eus'))
        result = run(inv, text, [('43235', EGD_EUS['P1']), ('43242', EGD_EUS['P2'])])
        self.assertEqual(asked(proposal(result, '43235')), ['base_included'])
        p = proposal(run(inv, text, [('43259', EGD_EUS['P2'])]), '43259')
        self.assertEqual(([item['id'] for item in p.support['acts']], asked(p)), (['E2'], ['base_included']))

    def test_c3_part_of_names_the_endoscopic_portion_too(self):
        inv, text = egd_eus(part_of='E2')
        p = proposal(run(inv, text, [('43235', EGD_EUS['P1']), ('43242', EGD_EUS['P2'])]), '43235')
        self.assertEqual(asked(p), ['base_included'])

    def test_a_lower_eus_includes_no_egd(self):
        lines = dict(EGD_EUS)
        lines['P2'] = 'A radial echoendoscope was then introduced; the rectal mass was sampled with a 22-gauge needle.'
        target = tg('', 'rectum', 'rectal', ['P2'])
        inv, text = inventory(lines, events=[
            exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
            exam('E2', 'P2', words='echoendoscope', status_words='was then introduced',
                 procedure=a('eus', 'echoendoscope', ['P2']), target=target),
            act('E3', 'P2', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'echoendoscope', ['P2']),
                technique=a('needle', '22-gauge needle', ['P2']), target=target)],
            reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])
        p = proposal(run(inv, text, [('43235', lines['P1']), ('45392', lines['P2'])]), '43235')
        self.assertEqual(p.status, 'ready')


class Competition(SimpleTestCase):
    def test_two_codes_one_a_participants_whose_events_meet_compete(self):
        entries = [('sel:0', '43249', 'primary', ('E2',)), ('sel:1', '43248', 'participant', ('E2',)),
                   ('sel:2', '43239', 'primary', ('E3',))]
        self.assertEqual(combination.competition(entries), {'sel:0': ('43248',), 'sel:1': ('43249',)})

    def test_two_primary_codes_never_compete(self):
        self.assertEqual(combination.competition([('sel:0', '45380', 'primary', ('E2',)),
                                                  ('sel:1', '45385', 'primary', ('E2',))]), {})

    def test_the_hold_is_worded_as_the_engines(self):
        service = SimpleNamespace(kind='egd')
        self.assertEqual(combination.competing_hold('43249', 'gi.egd', 'sel:0', ('43248',), 'upper endoscopy'),
                         engine.competing_hold('43249', 'gi.egd', 'sel:0', ('43248',), service))
        self.assertEqual((combination.COMPETING_CHECK, combination.COMPETING_FACT),
                         (engine.COMPETING_CHECK, engine.COMPETING_FACT))


class SameDayEM(SimpleTestCase):
    """D21 by date of service (ADJUDICATION C-3)."""
    LINES = {'P1': COLONOSCOPE, 'P2': POLYP}

    def em(self, *procedures, lines=None, separate=None):
        inv, text = office(*procedures, lines={**self.LINES, **(lines or {})}, separate=separate, lesions=[L1],
                           reach=[reached()] if procedures else ())
        return proposal(run(inv, text, [('99213', VISIT_LINE)], user_values=MEMBER), '99213')

    def colonoscopy_today(self, **changes):
        return (exam(procedure=a('colonoscopy', 'colonoscope', ['P1']), **changes),
                removed(procedure=a('colonoscopy', 'polyp', ['P2'])))

    def test_a_procedure_today_holds_the_visit(self):
        p = self.em(*self.colonoscopy_today())
        self.assertEqual(asked(p), ['separate_em'])
        self.assertEqual(check(p, 'em.same_day_procedure').status, 'warn')
        self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)

    def test_a_separately_identifiable_visit_stated_is_not_asked(self):
        lines = {'V3': 'A significant, separately identifiable evaluation was performed.'}
        p = self.em(*self.colonoscopy_today(), lines=lines,
                    separate=a('stated', 'significant, separately identifiable evaluation', ['V3']))
        self.assertEqual(asked(p), [])
        self.assertIn('significant, separately identifiable evaluation', check(p, 'em.same_day_procedure').detail)

    def test_c3_a_procedure_earlier_today_is_the_same_date_of_service(self):
        """The refuter's C-3 scenario: the EGD is another encounter's ('earlier today'), so it is not current - but it is
        on the date of service, and the visit is held."""
        lines = {'P1': 'I performed an upper endoscopy with duodenal biopsies on her earlier today.'}
        egd = act('E1', 'P1', 'examination', 'upper endoscopy', status_words='I performed',
                  procedure=a('egd', 'upper endoscopy', ['P1']), time=a('earlier_encounter', 'earlier today', ['P1']))
        inv, text = office(egd, lines=lines)
        p = proposal(run(inv, text, [('99213', VISIT_LINE)], user_values=MEMBER), '99213')
        self.assertEqual(asked(p), ['separate_em'])

    def test_c3_an_undatable_procedure_asks_its_time(self):
        lines = {'P1': 'An upper endoscopy with duodenal biopsies was performed.'}
        egd = act('E1', 'P1', 'examination', 'upper endoscopy', status_words='was performed',
                  procedure=a('egd', 'upper endoscopy', ['P1']), time=a('unknown'))
        inv, text = office(egd, lines=lines)
        p = proposal(run(inv, text, [('99213', VISIT_LINE)], user_values=MEMBER), '99213')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['event_time']))
        self.assertIn('done at this encounter?', p.clarifications[0].question)

    def test_a_procedure_of_another_date_is_no_procedure_day(self):
        lines = {'P1': 'An upper endoscopy with duodenal biopsies was performed in 2024.'}
        egd = act('E1', 'P1', 'examination', 'upper endoscopy', status_words='was performed',
                  procedure=a('egd', 'upper endoscopy', ['P1']), time=a('earlier_encounter', 'in 2024', ['P1']))
        inv, text = office(egd, lines=lines)
        p = proposal(run(inv, text, [('99213', VISIT_LINE)], user_values=MEMBER), '99213')
        self.assertEqual(p.status, 'ready')
        self.assertEqual(check(p, 'em.same_day_coverage').status, 'not_verified')

    def test_the_visit_basis_and_member_values_are_the_required_facts(self):
        inv, text = office()
        p = proposal(run(inv, text, [('99213', VISIT_LINE)]), '99213')
        self.assertEqual(asked(p), ['setting', 'patient_status'])  # D3: member values only
        self.assertIn('basis for the visit level (total time or medical decision making) = total time',
                      check(p, 'facts.required').detail)


class ModifierReview(SimpleTestCase):
    def two_lesions(self, rectal_landmark='rectum', site_words='rectum'):
        line = f'A 4 mm polyp in the {site_words} was biopsied with cold forceps.'
        rectal = les('L2', '4 mm polyp', 'P3', landmark=rectal_landmark, site_words=site_words, size_words='4 mm')
        biopsy = act('E3', 'P3', 'biopsy', 'biopsied', status_words='was biopsied',
                     technique=a('cold_forceps', 'cold forceps', ['P3']),
                     target=tg('L2', rectal_landmark, f'4 mm polyp in the {site_words}', ['P3']))
        inv, text = colonoscopy(biopsy, lesions=(L1, rectal), lines={'P3': line})
        return run(inv, text, [('45380', line), ('45385', POLYP)])

    def test_distinct_lesions_offer_the_separate_lesion_review(self):
        result = self.two_lesions()
        p = proposal(result, '45380')
        text = [item for item in p.modifier_considerations if item.startswith('Separate lesions are documented')]
        self.assertEqual(text, [checks.distinct_lesion_review_text(
            '45380', ['forceps biopsy (cold forceps) of the 4 mm polyp in the rectum'],
            [('45385', ['snare removal (cold snare) of the 6 mm sessile polyp in the sigmoid colon'])], '')])

    def test_lesions_not_verified_distinct_never_pair(self):
        result = self.two_lesions('sigmoid_colon', 'sigmoid colon')  # one site: possibly the same lesion
        p = proposal(result, '45380')
        self.assertFalse([item for item in p.modifier_considerations if item.startswith('Separate lesions')])


class CopiesPinned(SimpleTestCase):
    def test_the_holds_are_the_engine_builders(self):
        service = SimpleNamespace(kind='colonoscopy')
        for included in (('45385',), ('snare removal', 'forceps biopsy (stated in doubt)')):
            self.assertEqual(combination.base_hold('45378', 'gi.colonoscopy', 'sel:0', included, 'colonoscopy'),
                             engine.base_hold('45378', 'gi.colonoscopy', 'sel:0', included, service))
        egd = SimpleNamespace(kind='egd')
        for within in ((), ('43242',), ('43242', '43237')):
            self.assertEqual(combination.base_within_hold('43235', 'gi.egd', 'sel:0', within, 'upper endoscopy'),
                             engine.base_within_hold('43235', 'gi.egd', 'sel:0', within, egd))
        self.assertEqual(combination.base_hold('45378', 'gi.colonoscopy', 'k', ('45385',), None),
                         engine.base_hold('45378', 'gi.colonoscopy', 'k', ('45385',), None))

    def test_the_constants_and_rows(self):
        self.assertEqual(combination.DISTINCT_LESION_KINDS, engine.DISTINCT_LESION_KINDS)
        self.assertEqual((combination.DISTINCT_LESION_OPTIONS, combination.DISTINCT_LESION_NOT_CHECKED),
                         (checks.DISTINCT_LESION_OPTIONS, checks.DISTINCT_LESION_NOT_CHECKED))
        pairs = [('45378', None), ('45385', {'endo_base': '45378'}), ('45380', {})]
        self.assertEqual(combination.endoscopic_rows(pairs), engine.endoscopic_rows(pairs))
