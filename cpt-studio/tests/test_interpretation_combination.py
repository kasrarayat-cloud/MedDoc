"""The combination rules (Gemini migration slice S08; design/FINAL.md 7.9, as design/ADJUDICATION.md C-3 and C-4 amend it),
SYNTHETIC: one test per row - base (beside a code of its session, beside a reportable act no code accounts for, beside a
doubted act, and two E/M codes of one visit), base-within (C-4's structural EGD inside an upper EUS, C3's part_of, a
lower EUS, an uncoded EUS), competing (P-ADMIT2), the same-day E/M by date of service (C-3: a procedure done today, one
done "earlier today", a separately identifiable visit stated, an undatable procedure, a procedure of another date), the
separate-lesion modifier review (distinct lesions only) and the endoscopic rows - with every hold's wording pinned equal
to the legacy builder for equivalent inputs. Nothing is sent."""
from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.interpretation import combination, events
from studio.validation import checks, engine
from tests.test_interpretation_events import (COLONOSCOPE, L1, POLYP, asked, check, colonoscopy, exam, inventory,
                                              proposal, reached, removed, run)
from tests.test_interpretation_identity import a, act, les, sc, tg

MEMBER = {'setting': 'office', 'patient_status': 'established'}
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


def egd_eus(eus_target=('pancreas', 'pancreatic head'), part_of=''):
    target = tg('', eus_target[0], eus_target[1], ['P2'])
    return inventory(EGD_EUS, events=[
        exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1']), part_of=part_of),
        exam('E2', 'P2', words='echoendoscope', status_words='was then introduced',
             procedure=a('eus', 'echoendoscope', ['P2']), target=target),
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
