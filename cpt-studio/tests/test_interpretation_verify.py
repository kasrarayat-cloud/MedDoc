"""Evidence binding's checks (Gemini migration slice S02; design/contract.md 5.3-5.5, design/FINAL.md C1, as
design/ADJUDICATION.md EB1-EB4 amend them), TEXT-ONLY: every check row passes and fails on an attribute's own words; the
EB rules (no passage guard exists; a date in given time words that differs from the service date, and a name in given
performer words that is not the team's, leave the attribute unverified; the C1 markers read only a value that could
exclude); the structural rules of 5.4; usable and exclusion_basis (no wording-only exclusion); time_state's
re-evaluation with no text read; and the closed lists. Synthetic words written for this test; nothing is sent."""
from __future__ import annotations

import copy
from datetime import date

from django.test import SimpleTestCase

from studio.interpretation import literals, verify

SERVICE = date(2026, 11, 9)
TEAM = literals.names('Grace Okafor, MD') + literals.names('Robin Fellow-Synthetic')


def reasons(verdict) -> tuple:
    return tuple(verdict.reasons)


class ClosedLists(SimpleTestCase):
    def test_the_removed_passage_guards_are_never_a_reason(self):
        for removed in verify.REMOVED_REASONS:
            self.assertNotIn(removed, verify.REASONS)
            self.assertNotIn(removed, verify.IDENTITY_REASONS)
        self.assertEqual(verify.REMOVED_REASONS, ('foreign_date_in_passage', 'foreign_name_in_passage'))

    def test_the_lists_are_disjoint_and_unique(self):
        everything = verify.REASONS + verify.IDENTITY_REASONS
        self.assertEqual(len(everything), len(set(everything)))
        self.assertEqual(len(verify.CHECKS), len(set(verify.CHECKS)))

    def test_ordered_follows_the_closed_list_and_refuses_anything_else(self):
        self.assertEqual(verify.ordered(['date_mismatch', 'words_missing', 'date_mismatch']),
                         ['words_missing', 'date_mismatch'])
        self.assertEqual(verify.ordered(['identity_no_tie', 'lesion_unknown']), ['lesion_unknown', 'identity_no_tie'])
        with self.assertRaises(ValueError):
            verify.ordered(['foreign_date_in_passage'])
        with self.assertRaises(ValueError):
            verify.ordered(['a model reason'])

    def test_every_check_a_verdict_names_is_in_the_closed_list(self):
        verdicts = [verify.date_words('2026-11-09', '11/09/2026'), verify.time_words('future', 'next year', SERVICE),
                    verify.time_words('earlier_encounter', 'in 2024', SERVICE),
                    verify.performer_words('other_facility', 'an outside hospital', TEAM),
                    verify.size_words('7 mm'), verify.landmark_words('cecum', 'cecum'),
                    verify.reach_words('cecum', 'to the cecum'), verify.device_words('balloon', 'CRE balloon'),
                    verify.procedure_words('egd', 'EGD', True), verify.status_words('not_performed', 'no'),
                    verify.status_words('planned', 'planned'), verify.status_words('attempted_not_completed', 'failed'),
                    verify.scope_words('all_of_kind', 'no'), verify.basis_words('total_time', '20 minutes'),
                    verify.basis_words('medical_decision_making', 'MDM'), verify.separate_words('denied', 'not')]
        for verdict in verdicts:
            self.assertTrue(set(verdict.checks) <= set(verify.CHECKS), verdict.checks)
            self.assertTrue(set(verdict.reasons) <= set(verify.REASONS), verdict.reasons)


class DateOfService(SimpleTestCase):
    def test_pass_exactly_one_full_date_equal_to_the_value(self):
        for text in ('03/14/2026', 'Date of service: March 14, 2026', 'Saturday, March 14, 2026', '3/14/26'):
            with self.subTest(text):
                verdict = verify.date_words('2026-03-14', text)
                self.assertEqual(reasons(verdict), ())
                self.assertEqual(verdict.checks, ('date_literal',))
                self.assertEqual(verdict.literals, {'dates': [{'value': '2026-03-14', 'precision': 'day'}]})

    def test_fail_date_mismatch(self):
        for text in ('03/15/2026', '03/14/2026 and 03/15/2026', 'March 2026', '2026', 'yesterday',
                     'Friday, March 14, 2026'):
            with self.subTest(text):
                self.assertEqual(reasons(verify.date_words('2026-03-14', text)), ('date_mismatch',))


class Time(SimpleTestCase):
    def test_pass_each_value_against_the_service_date_at_the_literals_precision(self):
        cases = (('current_encounter', 'on 11/09/2026'), ('current_encounter', 'November 2026'),
                 ('current_encounter', 'today'), ('earlier_encounter', 'in 2024'),
                 ('earlier_encounter', 'October 2026'), ('earlier_encounter', 'on 11/08/2026'),
                 ('future', 'in 2027'), ('future', 'on 12/01/2026'))
        for value, text in cases:
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.time_words(value, text, SERVICE)), ())

    def test_fail_date_mismatch(self):
        cases = (('current_encounter', 'on 12/01/2026'), ('current_encounter', 'in 2024'),
                 ('earlier_encounter', 'in 2026'), ('earlier_encounter', 'September 21, 2027'),
                 ('future', 'in 2026'), ('future', 'on 11/09/2026'),
                 ('earlier_encounter', 'in 2019 and again on 12/01/2026'))
        for value, text in cases:
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.time_words(value, text, SERVICE)), ('date_mismatch',))

    def test_a_literal_with_no_service_date(self):
        # date_unchecked: unverified only for an earlier or a future time (contract 5.3).
        self.assertEqual(reasons(verify.time_words('earlier_encounter', 'in 2024', None)), ('date_unchecked',))
        self.assertEqual(reasons(verify.time_words('future', 'in 2027', None)), ('date_unchecked',))
        self.assertEqual(reasons(verify.time_words('current_encounter', 'on 11/09/2026', None)), ())

    def test_c1_time_marker_with_no_date_literal(self):
        for value, text in (('earlier_encounter', 'previously'), ('earlier_encounter', '2 years ago'),
                            ('earlier_encounter', 'at that time'), ('future', 'in 3 months'),
                            ('future', 'repeat colonoscopy'), ('future', 'will be')):
            with self.subTest(value=value, text=text):
                verdict = verify.time_words(value, text, SERVICE)
                self.assertEqual(reasons(verdict), ())
                self.assertIn('time_marker', verdict.checks)
                self.assertTrue(verdict.literals['markers'])
        for value, text in (('earlier_encounter', 'during the procedure'), ('future', 'afterwards'),
                            ('earlier_encounter', 'next year'), ('future', 'previously')):
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.time_words(value, text, SERVICE)), ('time_marker_missing',))

    def test_eb3_markers_never_touch_the_ready_path(self):
        # A current_encounter time is never asked for a marker, whatever its words hold.
        verdict = verify.time_words('current_encounter', 'previously', SERVICE)
        self.assertEqual(reasons(verdict), ())
        self.assertNotIn('time_marker', verdict.checks)

    def test_a_date_literal_decides_without_a_marker(self):
        verdict = verify.time_words('earlier_encounter', 'in 2024', SERVICE)
        self.assertNotIn('time_marker', verdict.checks)
        self.assertEqual(verdict.literals, {'dates': [{'value': '2024', 'precision': 'year'}]})


class Performer(SimpleTestCase):
    def test_documenting_team_pass(self):
        for text in ('Dr. Okafor', 'Grace Okafor, MD (fictional', 'Okafor, Grace', 'the fellow, Dr. Fellow-Synthetic',
                     'the endoscopist', 'I', 'Dr. Okafor and Dr. Synthetic'):
            with self.subTest(text):
                self.assertEqual(reasons(verify.performer_words('documenting_team', text, TEAM)), ())

    def test_documenting_team_fail_name_mismatch(self):
        # EB2: a name in given performer words that is not the endoscopist's or a listed team member's.
        for text in ('Dr. Patel', 'Dr. Okafor and Dr. Patel', 'Dr. Grace Lee'):
            with self.subTest(text):
                self.assertEqual(reasons(verify.performer_words('documenting_team', text, TEAM)), ('name_mismatch',))
        self.assertEqual(reasons(verify.performer_words('documenting_team', 'Dr. Okafor', ())), ('name_mismatch',),
                         'with no verified team name, a name cannot be confirmed')

    def test_other_clinician_pass_and_fail(self):
        self.assertEqual(reasons(verify.performer_words('other_clinician', 'Dr. Patel', TEAM)), ())
        self.assertEqual(reasons(verify.performer_words('other_clinician', 'a surgeon', TEAM)), ())
        for text in ('Dr. Okafor', 'Dr. Grace Lee', 'Dr. Patel and Dr. Okafor'):
            with self.subTest(text):
                self.assertEqual(reasons(verify.performer_words('other_clinician', text, TEAM)), ('name_not_other',))
        self.assertEqual(reasons(verify.performer_words('other_clinician', 'Dr. Patel', ())), ('name_not_other',),
                         'another clinician cannot be established with no verified team name (contract 8.3)')

    def test_other_facility_pass_and_fail(self):
        verdict = verify.performer_words('other_facility', 'an outside hospital', TEAM)
        self.assertEqual(reasons(verdict), ())
        self.assertEqual(verdict.literals['markers'], ['outside', 'hospital'])
        verdict = verify.performer_words('other_facility', 'Dr. Patel', TEAM)
        self.assertEqual(reasons(verdict), (), 'a titled person name needs no facility marker')
        self.assertNotIn('facility_marker', verdict.checks)
        self.assertEqual(reasons(verify.performer_words('other_facility', 'County General', TEAM)),
                         ('facility_marker_missing',), 'an untitled capitalized name is no person name')
        self.assertEqual(reasons(verify.performer_words('other_facility', 'elsewhere', TEAM)), ())
        self.assertEqual(reasons(verify.performer_words('other_facility', 'Dr. Okafor at the outside hospital', TEAM)),
                         ('name_not_other',))

    def test_unknown_is_not_checked(self):
        self.assertEqual(verify.performer_words('unknown', 'Dr. Patel', TEAM).reasons, ())


class Measures(SimpleTestCase):
    def test_size(self):
        verdict = verify.size_words('7 mm')
        self.assertEqual(reasons(verdict), ())
        self.assertEqual(verdict.literals, {'sizes_mm': [7]})
        for text in ('small', 'at 30 cm', 'diminutive'):
            with self.subTest(text):
                self.assertEqual(reasons(verify.size_words(text)), ('size_missing',))

    def test_identity_literals_are_recorded_and_never_a_failure(self):
        self.assertEqual(verify.identity_literals('a 7 mm polyp at 30 cm'), {'sizes_mm': [7], 'distances_cm': [30]})
        self.assertEqual(verify.identity_literals('the polyp'), {})


class Landmark(SimpleTestCase):
    def test_pass(self):
        for value, text in (('cecum', 'the cecum'), ('colon', 'the transverse colon'), ('colon', 'colon'),
                            ('transverse_colon', 'mid transverse colon'), ('sigmoid_colon', 'sigmoid and rectum'),
                            ('right_colon', 'in the right colon'), ('other', 'the tattoo site')):
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.landmark_words(value, text)), ())

    def test_fail_landmark_missing(self):
        for value, text in (('cecum', 'the polyp'), ('transverse_colon', 'the colon'), ('cecum', 'the right colon')):
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.landmark_words(value, text)), ('landmark_missing',))

    def test_fail_landmark_conflict(self):
        for value, text in (('cecum', 'the rectum'), ('rectum', 'the sigmoid colon'), ('other', 'the cecum'),
                            ('right_colon', 'the sigmoid colon')):
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.landmark_words(value, text)), ('landmark_conflict',))

    def test_reach(self):
        self.assertEqual(reasons(verify.reach_words('cecum', 'The colonoscope was advanced to the cecum')), ())
        self.assertEqual(reasons(verify.reach_words('cecum', 'to the cecum')), ())
        self.assertEqual(reasons(verify.reach_words('duodenum', 'the guidewire was advanced into the duodenum')),
                         ('device_reach',))
        self.assertEqual(reasons(verify.reach_words('duodenum', 'the guidewire and the endoscope reached the duodenum')),
                         ())
        self.assertEqual(reasons(verify.reach_words('cecum', 'the guidewire reached the rectum')),
                         ('landmark_conflict', 'device_reach'))
        self.assertIn('reach_device', verify.reach_words('cecum', 'cecum').checks)


class Device(SimpleTestCase):
    def test_pass_and_fail(self):
        self.assertEqual(reasons(verify.device_words('balloon', 'a 15 mm CRE balloon')), ())
        self.assertEqual(reasons(verify.device_words('wire_bougie', 'Savary dilators over a guidewire')), ())
        self.assertEqual(reasons(verify.device_words('cold_snare', 'cold snare')), ())
        for value, text in (('balloon', 'Savary dilators'), ('wire_bougie', 'a balloon'), ('cold_snare', 'hot snare'),
                            ('cold_snare', 'snare'), ('clip', 'removed')):
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.device_words(value, text)), ('device_missing',))

    def test_unchecked_devices(self):
        self.assertEqual(verify.device_words('other', 'a new device'), verify.Verdict())
        self.assertEqual(verify.device_words('not_stated', ''), verify.Verdict())


class Procedure(SimpleTestCase):
    def test_one_family_needs_no_name(self):
        self.assertEqual(verify.procedure_words('colonoscopy', 'the procedure', several=False), verify.Verdict())

    def test_several_families_need_the_claimed_name(self):
        self.assertEqual(reasons(verify.procedure_words('colonoscopy', 'Colonoscopy findings', several=True)), ())
        self.assertEqual(reasons(verify.procedure_words('egd', 'Upper endoscopy', several=True)), ())
        for value, text in (('colonoscopy', 'Upper endoscopy'), ('egd', 'the procedure'), ('other_gi', 'anoscopy')):
            with self.subTest(value=value, text=text):
                self.assertEqual(reasons(verify.procedure_words(value, text, several=True)), ('procedure_name_missing',))


class Status(SimpleTestCase):
    def test_not_performed_negation(self):
        for text in ('No polyp was removed', 'not removed', "wasn't removed", 'biopsies were deferred',
                     'the lesion was left in situ', 'declined'):
            with self.subTest(text):
                verdict = verify.status_words('not_performed', text)
                self.assertEqual(reasons(verdict), ())
                self.assertTrue(verdict.literals['negators'])
        for text in ('removed', 'taken from another site', 'cannot be removed'):
            with self.subTest(text):
                self.assertEqual(reasons(verify.status_words('not_performed', text)), ('negation_missing',))

    def test_c1_planned_and_attempted(self):
        self.assertEqual(reasons(verify.status_words('planned', 'will be scheduled')), ())
        self.assertEqual(reasons(verify.status_words('planned', 'referred for EMR')), ('planning_missing',),
                         '"referred" is not in the closed list ("refer", "referral" are): a known limit')
        self.assertEqual(reasons(verify.status_words('planned', 'referral for EMR')), ())
        self.assertEqual(reasons(verify.status_words('attempted_not_completed', 'could not be completed')), ())
        self.assertEqual(reasons(verify.status_words('attempted_not_completed', 'removed')), ('failure_missing',))

    def test_performed_and_uncertain_are_bound_by_their_words_alone(self):
        self.assertEqual(verify.status_words('performed', 'no'), verify.Verdict())
        self.assertEqual(verify.status_words('uncertain', 'possibly'), verify.Verdict())


class ScopeAndVisit(SimpleTestCase):
    def test_all_of_kind_quantifier(self):
        verdict = verify.scope_words('all_of_kind', 'No biopsies')
        self.assertEqual(reasons(verdict), ())
        self.assertEqual(verdict.literals, {'quantifiers': ['no']})
        self.assertEqual(reasons(verify.scope_words('all_of_kind', 'biopsies')), ('quantifier_missing',))

    def test_other_scopes_are_bound_by_their_words_alone(self):
        # ADJUDICATION C-7: an exceptive scope is verified as words, never through a list.
        for value in ('single_target', 'listed_targets', 'exceptive', 'unknown', 'not_applicable'):
            with self.subTest(value):
                self.assertEqual(verify.scope_words(value, 'anything'), verify.Verdict())

    def test_visit_basis(self):
        self.assertEqual(reasons(verify.basis_words('total_time', 'Total time spent: 45 minutes')), ())
        self.assertEqual(reasons(verify.basis_words('total_time', 'a long visit')), ('duration_missing',))
        self.assertEqual(reasons(verify.basis_words('medical_decision_making', 'medical decision-making: moderate')), ())
        self.assertEqual(reasons(verify.basis_words('medical_decision_making', 'MDM moderate')), ())
        self.assertEqual(reasons(verify.basis_words('medical_decision_making', 'moderate complexity')),
                         ('label_missing',))
        self.assertEqual(verify.basis_words('not_stated', ''), verify.Verdict())

    def test_separately_identifiable_denied(self):
        self.assertEqual(reasons(verify.separate_words('denied', 'not separately identifiable')), ())
        self.assertEqual(reasons(verify.separate_words('denied', 'part of the procedure')), ('negation_missing',))
        self.assertEqual(verify.separate_words('stated', 'significant and separately identifiable'), verify.Verdict())


class Structural(SimpleTestCase):
    def test_scope_permitted(self):
        self.assertTrue(verify.scope_permitted('not_performed') and verify.scope_permitted('uncertain'))
        for status in ('performed', 'attempted_not_completed', 'planned'):
            self.assertFalse(verify.scope_permitted(status))

    def test_scope_fits_its_target(self):
        self.assertTrue(verify.scope_fits('single_target', True, 'not_stated', 0))
        self.assertTrue(verify.scope_fits('single_target', False, 'rectum', 0))
        self.assertFalse(verify.scope_fits('single_target', False, 'not_stated', 0))
        self.assertTrue(verify.scope_fits('listed_targets', False, 'not_stated', 2))
        self.assertFalse(verify.scope_fits('listed_targets', False, 'not_stated', 1))
        self.assertTrue(verify.scope_fits('all_of_kind', False, 'not_stated', 0))
        self.assertFalse(verify.scope_fits('all_of_kind', False, 'rectum', 0))
        self.assertFalse(verify.scope_fits('all_of_kind', True, 'not_stated', 0))
        self.assertTrue(verify.scope_fits('exceptive', True, 'rectum', 0))

    def test_umbrella_and_status_time(self):
        self.assertFalse(verify.umbrella_fits('intervention', 'performed'))
        self.assertFalse(verify.umbrella_fits('intervention', 'attempted_not_completed'))
        self.assertTrue(verify.umbrella_fits('intervention', 'not_performed'))
        self.assertTrue(verify.umbrella_fits('removal', 'performed'))
        self.assertFalse(verify.status_time_consistent('performed', 'future'))
        self.assertFalse(verify.status_time_consistent('attempted_not_completed', 'future'))
        self.assertFalse(verify.status_time_consistent('planned', 'earlier_encounter'))
        self.assertTrue(verify.status_time_consistent('planned', 'future'))
        self.assertTrue(verify.status_time_consistent('performed', 'earlier_encounter'))

    def test_single_family(self):
        one, two = frozenset({'gi.colonoscopy'}), frozenset({'gi.colonoscopy', 'gi.egd'})
        self.assertTrue(verify.single_family('snare', 'colonoscopy', one))
        self.assertFalse(verify.single_family('snare', 'egd', one))
        self.assertFalse(verify.single_family('snare', 'colonoscopy', two))
        self.assertFalse(verify.single_family('snare', 'colonoscopy', frozenset()))
        self.assertTrue(verify.single_family('em_visit', 'office_em', two), 'an E/M visit takes its family from its kind')
        self.assertTrue(verify.single_family('em_prolonged', 'em_other', frozenset()))
        self.assertFalse(verify.single_family('em_visit', 'colonoscopy', one))

    def test_reach_permitted(self):
        def event(**changes):
            good = {'kind': {'value': 'examination', 'state': 'verified', 'open': False},
                    'time': {'value': 'current_encounter', 'state': 'verified', 'open': False},
                    'status': {'value': 'performed', 'state': 'verified', 'open': False},
                    'technique': {'value': 'endoscope', 'state': 'verified', 'open': False}}
            for name, change in changes.items():
                good[name] = dict(good[name], **change)
            return good

        self.assertTrue(verify.reach_permitted(event(), 'to the cecum'))
        self.assertTrue(verify.reach_permitted(event(status={'value': 'attempted_not_completed'}), ''))
        self.assertTrue(verify.reach_permitted(event(technique={'value': 'not_stated', 'state': 'absent'}),
                                               'the colonoscope reached the cecum'))
        refused = (event(kind={'value': 'biopsy'}), event(time={'value': 'earlier_encounter'}),
                   event(time={'state': 'unverified'}), event(time={'open': True}), event(status={'value': 'planned'}),
                   event(status={'state': 'unverified'}), event(technique={'value': 'manual'}),
                   event(technique={'state': 'unverified'}),
                   event(technique={'value': 'not_stated', 'state': 'absent'}))
        for index, item in enumerate(refused):
            with self.subTest(index):
                self.assertFalse(verify.reach_permitted(item, 'to the cecum'))
        self.assertFalse(verify.reach_permitted(event(technique={'value': 'not_stated', 'state': 'absent'}),
                                                'through-the-scope balloon to the duodenum'))


class Reading(SimpleTestCase):
    @staticmethod
    def attribute(value, state='verified', open=False, found=None, basis='stated', reasons=()):
        return {'value': value, 'basis': basis, 'state': state, 'open': open, 'words': None, 'passages': [],
                'checks': [], 'literals': found or {}, 'reasons': list(reasons)}

    def test_usable(self):
        self.assertTrue(verify.usable(self.attribute('performed')))
        self.assertFalse(verify.usable(self.attribute('performed', open=True)))
        self.assertFalse(verify.usable(self.attribute('performed', state='unverified')))
        self.assertFalse(verify.usable(self.attribute('performed', state='absent')))
        self.assertFalse(verify.usable(None))

    def test_exclusion_basis_literal_marker_or_none(self):
        a = self.attribute
        cases = (
            ('status', a('not_performed', found={'negators': ['no']}), 'literal'),
            ('status', a('not_performed'), ''),
            ('status', a('planned'), ''),
            ('time', a('earlier_encounter'), ''),
            ('performer', a('other_facility'), ''),
            ('status', a('planned', found={'markers': ['planned']}), 'marker'),
            ('status', a('attempted_not_completed', found={'markers': ['failed']}), 'marker'),
            ('status', a('performed'), ''),
            ('time', a('earlier_encounter', found={'dates': [{'value': '2024', 'precision': 'year'}]}), 'literal'),
            ('time', a('future', found={'markers': ['next']}), 'marker'),
            ('time', a('current_encounter', basis='default'), ''),
            ('performer', a('other_clinician', found={'names': [{'tokens': ['patel'], 'titled': True,
                                                                   'credentialed': False}]}), 'literal'),
            ('performer', a('other_clinician', found={'names': [{'tokens': ['patel'], 'titled': False,
                                                                   'credentialed': False}]}), ''),
            ('performer', a('other_clinician'), ''),
            ('performer', a('other_facility', found={'markers': ['outside']}), 'marker'),
            ('performer', a('documenting_team', basis='default'), ''),
            ('status', a('not_performed', state='unverified', found={'negators': ['no']}), ''),
            ('status', a('not_performed', open=True, found={'negators': ['no']}), ''),
        )
        for index, (name, attribute, want) in enumerate(cases):
            with self.subTest(index):
                self.assertEqual(verify.exclusion_basis(name, attribute), want)


class TimeState(SimpleTestCase):
    @staticmethod
    def stated(value, text, service):
        verdict = verify.time_words(value, text, service)
        return {'value': value, 'basis': 'stated', 'state': 'unverified' if verdict.reasons else 'verified',
                'open': False, 'words': None, 'passages': ['P1'], 'checks': ['passages_located', *verdict.checks],
                'literals': dict(verdict.literals), 'reasons': list(verdict.reasons)}

    def test_a_new_effective_date_rejudges_the_stored_literals(self):
        earlier = self.stated('earlier_encounter', 'on 05/01/2024', SERVICE)
        self.assertEqual(earlier['state'], 'verified')
        moved = verify.time_state(earlier, date(2024, 4, 1))
        self.assertEqual((moved['state'], moved['reasons']), ('unverified', ['date_mismatch']))
        back = verify.time_state(moved, '2026-11-09')
        self.assertEqual((back['state'], back['reasons']), ('verified', []))

    def test_an_unchecked_literal_is_decided_once_a_date_exists(self):
        future = self.stated('future', 'on 12/01/2026', None)
        self.assertEqual((future['state'], future['reasons']), ('unverified', ['date_unchecked']))
        self.assertEqual(verify.time_state(future, SERVICE)['state'], 'verified')
        self.assertEqual(verify.time_state(future, date(2026, 12, 2))['reasons'], ['date_mismatch'])
        self.assertEqual(verify.time_state(future, None)['reasons'], ['date_unchecked'])

    def test_a_current_encounter_date_follows_the_members_date(self):
        current = self.stated('current_encounter', 'on 11/09/2026', None)
        self.assertEqual(current['state'], 'verified')
        self.assertEqual(verify.time_state(current, date(2026, 11, 10))['reasons'], ['date_mismatch'])
        self.assertEqual(verify.time_state(current, SERVICE)['state'], 'verified')

    def test_other_reasons_defaults_and_discarded_records_are_kept(self):
        marked = self.stated('earlier_encounter', 'during the procedure', SERVICE)
        self.assertEqual(verify.time_state(marked, date(2000, 1, 1))['reasons'], ['time_marker_missing'])
        inconsistent = dict(self.stated('future', 'in 2027', SERVICE), reasons=['inconsistent_status_time'],
                            state='unverified')
        self.assertEqual(verify.time_state(inconsistent, SERVICE)['reasons'], ['inconsistent_status_time'])
        self.assertEqual(verify.time_state(inconsistent, date(2028, 1, 1))['reasons'],
                         ['date_mismatch', 'inconsistent_status_time'])
        default = {'value': 'current_encounter', 'basis': 'default', 'state': 'verified', 'open': False,
                   'literals': {}, 'reasons': []}
        self.assertEqual(verify.time_state(default, date(1990, 1, 1)), default)
        discarded = dict(self.stated('future', 'in 2027', SERVICE), state='discarded')
        self.assertEqual(verify.time_state(discarded, date(2030, 1, 1))['state'], 'discarded')
        opened = dict(self.stated('future', 'in 2027', SERVICE), open=True)
        self.assertTrue(verify.time_state(opened, SERVICE)['open'])

    def test_the_stored_record_is_never_changed_and_no_text_is_read(self):
        earlier = self.stated('earlier_encounter', 'on 05/01/2024', SERVICE)
        frozen = copy.deepcopy(earlier)
        verify.time_state(earlier, date(2020, 1, 1))
        self.assertEqual(earlier, frozen)
        self.assertIsNone(earlier['words'], 'the record carries no text: the stored literals decide')

    def test_an_unreadable_stored_literal_never_verifies(self):
        broken = dict(self.stated('earlier_encounter', 'in 2024', SERVICE),
                      literals={'dates': [{'value': '20x4', 'precision': 'year'}]})
        self.assertEqual(verify.time_state(broken, SERVICE)['reasons'], ['date_mismatch'])

    def test_an_effective_date_that_is_no_date_raises(self):
        earlier = self.stated('earlier_encounter', 'in 2024', SERVICE)
        for bad in ('11/09/2026', '2026-02-30', 20261109):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    verify.time_state(earlier, bad)
