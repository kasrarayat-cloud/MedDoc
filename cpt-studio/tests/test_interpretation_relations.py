"""Relations (Gemini migration slice S03; design/contract.md 6.4-6.6, design/FINAL.md 7.3-7.7, as design/ADJUDICATION.md
C-2, C-5, C-7, C-8, C-11 and C-16 amend them), TEXT-ONLY: the pairing table row by row - procedure (C-8), time,
performer, technique (C-16), target by scope (C-7's exceptive scope, all_of_kind within its session) - each SAME,
DIFFERENT and UNKNOWN cell; CONTRADICTION, DOUBT and the unverified kind or status; what a statement concerns (the
umbrellas, a tattoo and an injection as one act); the model's claims (C-11: dismissed only by a hard literal), between a
statement and an act and between two acts; the steps; the bundling identities (6.6, C-2, C-5); and every relation stored
and read back by the store. Synthetic answers built in code, normalized with slice S03's linked steps; nothing is sent."""
from __future__ import annotations

import json
import sys

from django.test import SimpleTestCase

from studio.interpretation import normalize, relations, store
from tests.test_interpretation_identity import (a, accepted, act, answer, les, normalized, relations_of, sc, snare,
                                              tg)

ENCOUNTER = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0101'
REVISION = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0102'
RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0103'
ENDOSCOPIST = {'P9': 'Endoscopist: Ana Ruiz, MD (fictional).'}
NAMED = {'documenting_endoscopist': {'words': 'Ana Ruiz, MD (fictional)', 'passages': ['P9']}}

POLYP = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
L1 = les('L1', '6 mm sessile polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='6 mm')


def removed(**changes) -> dict:
    """E1: the cold snare removal of L1 (P1), verified."""
    return snare('E1', 'P1', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', ['P1']),
                 **changes)


def denial(kind_words: str = 'removed', status_words: str = 'No polyp was removed', scope=None, kind: str = 'removal',
           eid: str = 'E2', passage: str = 'P2', **changes) -> dict:
    """E2: a statement that ``kind`` was not done (P2), broad by its quantifier unless ``scope`` says otherwise."""
    return act(eid, passage, kind, kind_words, status='not_performed', status_words=status_words,
               scope=scope if scope is not None else sc('all_of_kind', 'No', [passage]), **changes)


def verdict(inventory, statement: str = 'E2', event: str = 'E1') -> tuple:
    found = relations_of(inventory, statement, event)
    assert len(found) == 1, found
    return found[0]['type'], found[0]['attribute'], found[0]['reason']


def pairing(denial_line: str, *events, lesions=(L1,), extra=None, **options):
    lines = {'P1': POLYP, 'P2': denial_line, **(extra or {})}
    return normalized(lines, events=list(events), lesions=list(lesions), **options)


CONTRADICTION = ('contradiction', 'status', 'same_act')


class Contradiction(SimpleTestCase):
    def test_a_broad_current_denial_against_the_act(self):
        inventory = pairing('No polyp was removed.', removed(), denial())
        self.assertEqual(verdict(inventory), CONTRADICTION)
        relation = relations_of(inventory, 'E2', 'E1')[0]
        self.assertEqual(relation['passages'], ['P2', 'P1'])  # both sides' own passages
        self.assertFalse(relation['claimed_by_model'])

    def test_an_uncertain_statement_is_a_doubt(self):
        inventory = pairing('It is unclear whether any polyp was removed.', removed(),
                            act('E2', 'P2', 'removal', 'removed', status='uncertain',
                                status_words='It is unclear whether any polyp was removed',
                                scope=sc('all_of_kind', 'any', ['P2'])))
        self.assertEqual(verdict(inventory), ('doubt', 'status', 'in_doubt'))

    def test_an_unverified_negative_status(self):
        inventory = pairing('No polyp was removed.', removed(), denial(status_words='polyp was removed'))
        self.assertEqual(verdict(inventory), ('unresolved', 'status', 'status_unresolved'))

    def test_an_unverified_kind_leaves_open_whether_the_statement_concerns_the_act(self):
        inventory = pairing('No polyp was removed.', removed(), denial(kind_words='excised'))
        self.assertEqual(verdict(inventory), ('unresolved', 'scope', 'kind_unresolved'))


class Procedure(SimpleTestCase):
    """C-8: verified different families are independent; an unverified family in a multi-family encounter is
    UNRESOLVED(procedure); all_of_kind is every act of its kind in the statement's own examination or session."""
    LINES = {'P1': 'EGD: the gastroscope was advanced to the second portion of the duodenum.',
             'P2': 'EGD: cold forceps biopsies were taken from the duodenum.',
             'P3': 'Colonoscopy: the colonoscope was advanced to the cecum.',
             'P4': 'Colonoscopy: no biopsies were taken.'}

    def events(self, statement_procedure) -> list:
        return [act('E0', 'P1', 'examination', 'gastroscope', status_words='was advanced',
                    procedure=a('egd', 'EGD', ['P1'])),
                act('E1', 'P3', 'examination', 'colonoscope', status_words='was advanced to the cecum',
                    procedure=a('colonoscopy', 'Colonoscopy', ['P3'])),
                act('E2', 'P2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd', 'EGD', ['P2']),
                    technique=a('cold_forceps', 'cold forceps', ['P2']), target=tg('', 'duodenum', 'duodenum', ['P2'])),
                act('E3', 'P4', 'biopsy', 'biopsies', status='not_performed', status_words='no biopsies were taken',
                    procedure=statement_procedure, scope=sc('all_of_kind', 'no', ['P4']))]

    def test_verified_different_families_are_independent(self):
        inventory = normalized(self.LINES, events=self.events(a('colonoscopy', 'Colonoscopy', ['P4'])))
        self.assertEqual(verdict(inventory, 'E3', 'E2'), ('independent', 'procedure', 'another_procedure'))

    def test_an_unverified_family_in_a_multi_family_encounter(self):
        inventory = normalized(self.LINES, events=self.events(a('unknown')))
        self.assertEqual(verdict(inventory, 'E3', 'E2'), ('unresolved', 'procedure', 'procedure_unresolved'))

    def test_one_family_settles_an_unstated_procedure(self):
        lines = {'P1': 'Cold forceps biopsies were taken from the cecum.', 'P2': 'No biopsies were taken.'}
        inventory = normalized(lines, events=[
            act('E1', 'P1', 'biopsy', 'biopsies', status_words='were taken'),
            act('E2', 'P2', 'biopsy', 'biopsies', status='not_performed', status_words='No biopsies were taken',
                procedure=a('unknown'), scope=sc('all_of_kind', 'No', ['P2']))])
        self.assertEqual(verdict(inventory), CONTRADICTION)

    def test_two_examinations_of_one_family_leave_the_session_unresolved(self):
        lines = {'P1': POLYP, 'P2': 'No polyp was removed.', 'P3': 'The colonoscope was advanced to the cecum.',
                 'P4': 'The colonoscope was reinserted to the splenic flexure.'}
        inventory = normalized(lines, lesions=[L1], events=[
            removed(), denial(),
            act('E3', 'P3', 'examination', 'colonoscope', status_words='was advanced to the cecum'),
            act('E4', 'P4', 'examination', 'colonoscope', status_words='was reinserted')])
        self.assertEqual(verdict(inventory), ('unresolved', 'procedure', 'session_unresolved'))


class Time(SimpleTestCase):
    def test_another_time_by_a_date_literal(self):
        inventory = pairing('No polyp was removed in 2024.', removed(),
                            denial(time=a('earlier_encounter', 'in 2024', ['P2'])))
        self.assertEqual(verdict(inventory), ('independent', 'time', 'another_time'))

    def test_an_unknown_time_is_never_a_match_or_a_non_match(self):
        inventory = pairing('No polyp was removed.', removed(), denial(time=a('unknown')))
        self.assertEqual(verdict(inventory), ('unresolved', 'time', 'time_unresolved'))

    def test_an_unverified_time(self):
        inventory = pairing('No polyp was removed previously.', removed(),
                            denial(time=a('earlier_encounter', 'removed', ['P2'])))  # no date and no marker
        self.assertEqual(verdict(inventory), ('unresolved', 'time', 'time_unresolved'))


class Performer(SimpleTestCase):
    def run_with(self, act_line: str, denial_line: str, act_performer, denial_performer) -> tuple:
        lines = {'P1': act_line, 'P2': denial_line, **ENDOSCOPIST}
        inventory = normalized(lines, lesions=[], events=[
            snare('E1', 'P1', performer=act_performer), denial(performer=denial_performer)], **NAMED)
        return verdict(inventory)

    def test_another_category(self):
        self.assertEqual(self.run_with('A polyp was removed with a cold snare.', 'No polyp was removed by Dr. Lena Ortiz.',
                                       a('documenting_team'), a('other_clinician', 'Dr. Lena Ortiz', ['P2'])),
                         ('independent', 'performer', 'another_performer'))

    def test_two_other_clinicians_by_their_names(self):
        line = 'A polyp was removed with a cold snare by Dr. Lena Ortiz.'
        ortiz = a('other_clinician', 'Dr. Lena Ortiz', ['P1'])
        self.assertEqual(self.run_with(line, 'No polyp was removed by Dr. Lena Ortiz.', ortiz,
                                       a('other_clinician', 'Dr. Lena Ortiz', ['P2'])), CONTRADICTION)
        self.assertEqual(self.run_with(line, 'No polyp was removed by Dr. Paul Kim.', ortiz,
                                       a('other_clinician', 'Dr. Paul Kim', ['P2'])),
                         ('independent', 'performer', 'another_performer'))
        self.assertEqual(self.run_with(line, 'No polyp was removed by another physician.', ortiz,
                                       a('other_clinician', 'another physician', ['P2'])),
                         ('unresolved', 'performer', 'performer_unresolved'))

    def test_an_unknown_performer(self):
        self.assertEqual(self.run_with('A polyp was removed with a cold snare.', 'No polyp was removed.',
                                       a('documenting_team'), a('unknown')),
                         ('unresolved', 'performer', 'performer_unresolved'))


class Technique(SimpleTestCase):
    def test_a_device_outside_the_statements(self):
        inventory = pairing('No hot snare was used.', removed(),
                            denial('hot snare', 'No hot snare was used', kind='snare',
                                   technique=a('hot_snare', 'hot snare', ['P2'])))
        self.assertEqual(verdict(inventory), ('independent', 'technique', 'another_technique'))

    def test_a_device_that_contains_the_acts(self):
        inventory = pairing('No snare was used.', removed(),
                            denial('snare', 'No snare was used', kind='snare', technique=a('snare', 'snare', ['P2'])))
        self.assertEqual(verdict(inventory), CONTRADICTION)

    def test_c16_the_acts_device_absent(self):
        inventory = pairing('No hot snare was used.', removed(technique=a('not_stated')),
                            denial('hot snare', 'No hot snare was used', kind='snare',
                                   technique=a('hot_snare', 'hot snare', ['P2'])))
        self.assertEqual(verdict(inventory), ('unresolved', 'technique', 'technique_unresolved'))

    def test_the_acts_device_wider_than_the_statements(self):
        lines_act = removed(technique=a('snare', 'snare', ['P1']))
        inventory = pairing('No cold snare was used.', lines_act,
                            denial('cold snare', 'No cold snare was used', kind='snare',
                                   technique=a('cold_snare', 'cold snare', ['P2'])))
        self.assertEqual(verdict(inventory), ('unresolved', 'technique', 'technique_unresolved'))

    def test_the_statements_device_unverified(self):
        inventory = pairing('No hot snare was used.', removed(),
                            denial('hot snare', 'No hot snare was used', kind='snare',
                                   technique=a('hot_snare', 'used', ['P2'])))
        self.assertEqual(verdict(inventory), ('unresolved', 'technique', 'technique_unresolved'))


class Target(SimpleTestCase):
    def test_single_target_the_same_verified_lesion(self):
        inventory = pairing('The sessile polyp was not removed.', removed(),
                            denial(status_words='was not removed', scope=sc('single_target', 'The sessile polyp', ['P2']),
                                   target=tg('L1', 'not_stated', 'The sessile polyp', ['P2'])))
        self.assertEqual(verdict(inventory), CONTRADICTION)

    def test_single_target_a_distinct_lesion(self):
        lines = {'P3': 'A 4 mm flat polyp was seen in the rectum.'}
        inventory = pairing('The flat polyp was not removed.', removed(),
                            denial(status_words='was not removed', scope=sc('single_target', 'The flat polyp', ['P2']),
                                   target=tg('L2', 'not_stated', 'The flat polyp', ['P2'])),
                            lesions=(L1, les('L2', '4 mm flat polyp', 'P3', landmark='rectum', site_words='rectum')),
                            extra=lines)
        self.assertEqual(verdict(inventory), ('independent', 'target', 'another_lesion'))

    def test_single_target_lesions_possibly_the_same(self):
        lines = {'P3': 'A flat polyp was also seen.'}
        inventory = pairing('The flat polyp was not removed.', removed(),
                            denial(status_words='was not removed', scope=sc('single_target', 'The flat polyp', ['P2']),
                                   target=tg('L2', 'not_stated', 'The flat polyp', ['P2'])),
                            lesions=(L1, les('L2', 'flat polyp', 'P3')), extra=lines)
        self.assertEqual(verdict(inventory), ('unresolved', 'target', 'possibly_same_lesion'))

    def test_a_site_statement_containing_the_acts_place(self):
        inventory = pairing('No polyp was removed from the colon.', removed(),
                            denial(scope=sc('single_target', 'from the colon', ['P2']),
                                   target=tg('', 'colon', 'the colon', ['P2'])))
        self.assertEqual(verdict(inventory), CONTRADICTION)

    def test_a_site_statement_at_a_disjoint_place(self):
        inventory = pairing('No polyp was removed from the rectum.', removed(),
                            denial(scope=sc('single_target', 'from the rectum', ['P2']),
                                   target=tg('', 'rectum', 'the rectum', ['P2'])))
        self.assertEqual(verdict(inventory), ('independent', 'target', 'another_site'))

    def test_a_site_statement_inside_the_acts_place(self):
        lines = {'P1': 'A polyp in the colon was removed with a cold snare.',
                 'P2': 'No polyp was removed from the sigmoid colon.'}
        inventory = normalized(lines, events=[
            snare('E1', 'P1', target=tg('', 'colon', 'colon', ['P1'])),
            denial(scope=sc('single_target', 'from the sigmoid colon', ['P2']),
                   target=tg('', 'sigmoid_colon', 'sigmoid colon', ['P2']))])
        self.assertEqual(verdict(inventory), ('unresolved', 'target', 'site_overlap'))

    def test_a_named_lesion_and_an_act_whose_identity_is_unresolved(self):
        lines = {'P1': 'A 6 mm sessile polyp was seen in the sigmoid colon.', 'P3': 'A polyp was removed with a cold snare.'}
        inventory = normalized({**lines, 'P2': 'The sessile polyp was not removed.'}, lesions=[L1], events=[
            snare('E1', 'P3', target=tg('L1', 'not_stated', '6 mm sessile polyp', ['P1'])),  # not in its statement
            denial(status_words='was not removed', scope=sc('single_target', 'The sessile polyp', ['P2']),
                   target=tg('L1', 'not_stated', 'The sessile polyp', ['P2']))])
        self.assertEqual(verdict(inventory), ('unresolved', 'target', 'identity_unresolved'))

    def test_listed_targets(self):
        lines = {'P3': 'A 4 mm flat polyp was seen in the cecum.', 'P4': 'A 3 mm pale polyp was seen in the rectum.'}
        lesions = (L1, les('L2', '4 mm flat polyp', 'P3', landmark='cecum', site_words='cecum'),
                   les('L3', '3 mm pale polyp', 'P4', landmark='rectum', site_words='rectum'))
        unlisted = pairing('Neither the flat nor the pale polyp was removed.', removed(),
                           denial(status_words='Neither the flat nor the pale polyp was removed',
                                  scope=sc('listed_targets', 'Neither the flat nor the pale polyp', ['P2'], ['L2', 'L3'])),
                           lesions=lesions, extra=lines)
        self.assertEqual(verdict(unlisted), ('independent', 'target', 'another_lesion'))
        listed = pairing('Neither the sessile nor the pale polyp was removed.', removed(),
                         denial(status_words='Neither the sessile nor the pale polyp was removed',
                                scope=sc('listed_targets', 'Neither the sessile nor the pale polyp', ['P2'], ['L1', 'L3'])),
                         lesions=lesions, extra=lines)
        self.assertEqual(verdict(listed), CONTRADICTION)

    def test_listed_targets_one_distinct_and_one_possibly_the_same(self):
        # review finding 5, mutant (d): a lesion distinct from SOME listed lesions is not distinct from the list
        lines = {'P3': 'A 4 mm flat polyp was seen in the cecum.', 'P4': 'A pale polyp was also seen.'}
        lesions = (L1, les('L2', '4 mm flat polyp', 'P3', landmark='cecum', site_words='cecum'),
                   les('L3', 'pale polyp', 'P4'))
        inventory = pairing('Neither the flat nor the pale polyp was removed.', removed(),
                            denial(status_words='Neither the flat nor the pale polyp was removed',
                                   scope=sc('listed_targets', 'Neither the flat nor the pale polyp', ['P2'], ['L2', 'L3'])),
                            lesions=lesions, extra=lines)
        self.assertEqual(verdict(inventory), ('unresolved', 'target', 'possibly_same_lesion'))

    def test_listed_targets_at_places_disjoint_from_an_acts_own(self):
        # review finding 5, the listed another_site arm: an act verified to no lesion, at a verified place disjoint
        # from every listed lesion's verified site
        lines = {'P3': 'A 4 mm flat polyp was seen in the cecum.', 'P4': 'A 3 mm pale polyp was seen in the rectum.'}
        lesions = (les('L2', '4 mm flat polyp', 'P3', landmark='cecum', site_words='cecum'),
                   les('L3', '3 mm pale polyp', 'P4', landmark='rectum', site_words='rectum'))
        statement = denial(status_words='Neither the flat nor the pale polyp was removed',
                           scope=sc('listed_targets', 'Neither the flat nor the pale polyp', ['P2'], ['L2', 'L3']))
        line = 'Neither the flat nor the pale polyp was removed.'
        inventory = pairing(line, snare('E1', 'P1', target=tg('', 'sigmoid_colon', 'sigmoid colon', ['P1'])), statement,
                            lesions=lesions, extra=lines)
        self.assertEqual(verdict(inventory), ('independent', 'target', 'another_site'))
        inventory = pairing(line, snare('E1', 'P1'), statement, lesions=lesions, extra=lines)  # no place: unknown
        self.assertEqual(verdict(inventory), ('unresolved', 'target', 'identity_unresolved'))

    def test_a_named_lesion_whose_identity_is_unresolved_at_a_disjoint_site(self):
        # contract 6.5 (review finding 5): an unresolved identity at a site disjoint from the act's is still INDEPENDENT
        lines = {'P3': 'A 4 mm flat polyp was seen in the rectum.'}
        lesions = (L1, les('L2', '4 mm flat polyp', 'P3', landmark='rectum', site_words='rectum'))
        inventory = pairing('No polyp was removed from the rectum.', removed(),
                            denial(scope=sc('single_target', 'from the rectum', ['P2']),
                                   target=tg('L2', 'rectum', 'rectum', ['P3'])),  # its words are not in its statement
                            lesions=lesions, extra=lines)
        self.assertEqual(inventory.events['events'][1]['target']['identity_by']['reasons'],
                         ['identity_not_in_statement'])
        self.assertEqual(verdict(inventory), ('independent', 'target', 'another_site'))
        inventory = pairing('No polyp was removed from the colon.', removed(),  # the twin: a place holding the act's
                            denial(scope=sc('single_target', 'from the colon', ['P2']),
                                   target=tg('L2', 'colon', 'colon', ['P3'])),
                            lesions=(L1, les('L2', '4 mm flat polyp', 'P3', landmark='colon', site_words='colon')),
                            extra={'P3': 'A 4 mm flat polyp was seen in the colon.'})
        self.assertEqual(inventory.events['events'][1]['target']['identity_by']['reasons'],
                         ['identity_not_in_statement'])
        self.assertEqual(verdict(inventory), ('unresolved', 'target', 'identity_unresolved'))

    def test_c11_review_b2_sizes_beside_one_site_named_in_both_descriptions(self):
        # review finding 3, probe B2: the descriptions both name the sigmoid colon - a site literal saying "same" - so
        # a 6 mm and a 1 cm polyp are possibly one lesion and the denial of one is a question on the other's removal
        lines = {'P1': POLYP, 'P2': 'Impression: 1 cm sessile polyp in the sigmoid colon, not removed.'}
        first = les('L1', '6 mm sessile polyp in the sigmoid colon', 'P1', size_words='6 mm')
        second = les('L2', '1 cm sessile polyp in the sigmoid colon', 'P2', size_words='1 cm')
        inventory = normalized(lines, lesions=[first, second], events=[
            snare('E1', 'P1', target=tg('L1', 'not_stated', '6 mm sessile polyp in the sigmoid colon', ['P1'])),
            denial(status_words='not removed', scope=sc('single_target', '1 cm sessile polyp in the sigmoid colon', ['P2']),
                   target=tg('L2', 'not_stated', '1 cm sessile polyp in the sigmoid colon', ['P2']))])
        self.assertEqual([item['target']['identity'] for item in inventory.events['events']], ['verified', 'verified'])
        self.assertEqual(verdict(inventory), ('unresolved', 'target', 'possibly_same_lesion'))


# --- DECISIONS D34: the place an anastomosis takes ------------------------------------------------------------------------

DILATED = 'The anastomotic narrowing was dilated with a through-the-scope balloon to 15 mm.'
DESCENDING_POLYP = 'A 7 mm sessile polyp was seen in the descending colon.'
NOT_DILATED = 'No dilation was performed on this polyp.'
SURGERY = 'History: right hemicolectomy with a stapled side-to-side ileocolonic anastomosis.'
L_DESCENDING = les('L1', '7 mm sessile polyp', 'P2', landmark='descending_colon', site_words='descending colon',
                   size_words='7 mm')


def anatomy_entry(words: str, passage: str = 'P4', state: str = 'altered', landmark: str = 'anastomosis') -> dict:
    """An encounter.anatomy entry as Gemini gives it."""
    return {'state': state, 'landmark': landmark, 'words': words, 'passages': [passage]}


IN_SURGERY = anatomy_entry('stapled side-to-side ileocolonic anastomosis')


class AnastomosisPlace(SimpleTestCase):
    """DECISIONS D34 (Note #8's 45386): a target verified at an anastomosis takes the place of the encounter's ONE
    anastomosis, read from its anatomy entry's own type words (ileocolonic: the right colon), so the dilation of the
    anastomotic narrowing is set apart from a dilation denial on a descending-colon polyp. Nothing else moves: no
    anatomy entry, several anastomoses (an unverified second one too), no type word in the entry's own words (one in its
    passage only), an unknown type, or a type of another place in the act's own words keep the anastomosis unplaced and
    the pair unresolved, as before. A statement at the anastomosis still meets the act there; a D34 difference never
    dismisses Gemini's own claim (C-11); and the bundling identities read the same place."""

    def inventory(self, anatomy=(IN_SURGERY,), act_line=DILATED, act_words='anastomotic narrowing',
                  act_landmark='anastomosis', statement=None, extra=None):
        lines = {'P1': act_line, 'P2': DESCENDING_POLYP, 'P3': NOT_DILATED, 'P4': SURGERY, **(extra or {})}
        dilation = act('E1', 'P1', 'dilation', 'dilated', technique=a('balloon', 'through-the-scope balloon', ['P1']),
                       target=tg('', act_landmark, act_words, ['P1']))
        statement = statement or act('E2', 'P3', 'dilation', 'dilation', status='not_performed',
                                     status_words='No dilation was performed',
                                     scope=sc('single_target', 'on this polyp', ['P3']),
                                     target=tg('L1', 'not_stated', 'this polyp', ['P3']))
        return normalized(lines, lesions=[L_DESCENDING], events=[dilation, statement], anatomy=list(anatomy))

    def test_an_ileocolonic_anastomosis_is_set_apart_from_a_descending_colon_polyp(self):
        inventory = self.inventory()
        self.assertEqual(inventory.encounter_facts['anatomy'][0]['state'], 'verified')
        self.assertEqual(verdict(inventory), ('independent', 'target', 'another_site'))
        self.assertEqual(verdict(self.inventory(anatomy=())), ('unresolved', 'target', 'identity_unresolved'))

    def test_what_keeps_the_ambiguity(self):
        second = anatomy_entry('colorectal anastomosis', 'P5')
        unverified_second = anatomy_entry('end colostomy', 'P5')  # its words name no anastomosis: unverified, counted
        cases = {
            'a type word in the passage only': dict(anatomy=(anatomy_entry('anastomosis'),)),
            'two anastomoses': dict(anatomy=(IN_SURGERY, second),
                                    extra={'P5': 'A colorectal anastomosis was also described.'}),
            'an unverified second one': dict(anatomy=(IN_SURGERY, unverified_second),
                                             extra={'P5': 'An end colostomy was also noted.'}),
            'an unknown type': dict(anatomy=(anatomy_entry('colocolonic anastomosis'),),
                                    extra={'P4': 'History: subtotal colectomy with a colocolonic anastomosis.'}),
            'two types in the entry': dict(anatomy=(anatomy_entry('right hemicolectomy for colorectal cancer, with an '
                                                                  'ileocolonic anastomosis'),),
                                           extra={'P4': 'History: right hemicolectomy for colorectal cancer, with an '
                                                        'ileocolonic anastomosis.'}),
            'another type in the act\'s own words': dict(
                act_line='The colorectal anastomotic narrowing was dilated with a through-the-scope balloon to 15 mm.',
                act_words='colorectal anastomotic narrowing'),
            'an absent anastomosis': dict(anatomy=(anatomy_entry('stapled side-to-side ileocolonic anastomosis',
                                                                 state='absent'),)),
        }
        for name, options in cases.items():
            with self.subTest(name):
                inventory = self.inventory(**options)
                if name == 'an unverified second one':
                    self.assertEqual([item['state'] for item in inventory.encounter_facts['anatomy']],
                                     ['verified', 'unverified'])
                self.assertEqual(verdict(inventory), ('unresolved', 'target', 'identity_unresolved'))

    def test_a_statement_at_the_anastomosis_still_meets_the_act_there(self):
        statement = act('E2', 'P3', 'dilation', 'dilation', status='not_performed',
                        status_words='No dilation of the anastomosis was performed',
                        scope=sc('single_target', 'of the anastomosis', ['P3']),
                        target=tg('', 'anastomosis', 'the anastomosis', ['P3']))
        extra = {'P3': 'No dilation of the anastomosis was performed.'}
        for anatomy in ((IN_SURGERY,), ()):
            with self.subTest(anatomy=bool(anatomy)):
                self.assertEqual(verdict(self.inventory(anatomy=anatomy, statement=statement, extra=extra)),
                                 CONTRADICTION)

    def test_a_d34_difference_never_dismisses_geminis_own_claim(self):
        claimed = act('E2', 'P3', 'dilation', 'dilation', status='not_performed', status_words='No dilation was performed',
                      scope=sc('single_target', 'on this polyp', ['P3']), target=tg('L1', 'not_stated', 'this polyp', ['P3']),
                      contradicts=[{'event': 'E1', 'passages': ['P1', 'P3']}])
        found = relations_of(self.inventory(statement=claimed), 'E2', 'E1')
        self.assertEqual([(item['type'], item['attribute'], item['reason'], item['claimed_by_model']) for item in found],
                         [('unresolved', 'target', 'claim_soft_difference', True)])
        # the twin: the act's own words place it in the transverse colon, a hard literal
        found = relations_of(self.inventory(statement=claimed, act_landmark='transverse_colon',
                                            act_line='The transverse colon narrowing was dilated with a through-the-scope '
                                                     'balloon to 15 mm.', act_words='transverse colon narrowing'),
                             'E2', 'E1')
        self.assertEqual([(item['type'], item['attribute'], item['reason'], item['claimed_by_model']) for item in found],
                         [('dismissed_claim', 'target', 'another_site', True)])

    def test_the_bundling_identities_read_the_same_place(self):
        line = 'Biopsies were taken from the anastomosis and a polyp in the {} was removed with a cold snare.'

        def bundling(segment: str, anatomy) -> list:
            lines = {'P1': line.format(segment.replace('_', ' ')), 'P4': SURGERY}
            inventory = normalized(lines, anatomy=list(anatomy), events=[
                act('E1', 'P1', 'biopsy', 'Biopsies', status_words='were taken',
                    target=tg('', 'anastomosis', 'the anastomosis', ['P1'])),
                snare('E2', 'P1', target=tg('', segment, segment.replace('_', ' '), ['P1']))])
            return [(item['type'], item['statement'], item['event'], item['reason'])
                    for item in inventory.events['relations'] if item['type'] == relations.BUNDLING]

        # placed on the right colon side: compatible with the ascending colon, so the identity in doubt is asked (never
        # READY); disjoint from the descending colon, so nothing is asked. Unplaced, an anastomosis is compared with
        # nothing, as before.
        self.assertEqual(bundling('ascending_colon', (IN_SURGERY,)),
                         [('bundling_identity', 'E2', 'E1', 'biopsy_of_removed_lesion')])
        self.assertEqual(bundling('descending_colon', (IN_SURGERY,)), [])
        self.assertEqual(bundling('ascending_colon', ()), [])


class Scope(SimpleTestCase):
    def test_c7_an_exceptive_statement_never_pairs(self):
        inventory = pairing('No other polyp was removed.', removed(),
                            denial(status_words='No other polyp was removed', scope=sc('exceptive', 'No other', ['P2'])))
        self.assertEqual(verdict(inventory), ('independent', 'scope', 'exceptive'))

    def test_c7_no_further_intervention(self):
        lines = {'P1': POLYP, 'P2': 'No further intervention was required.'}
        inventory = normalized(lines, lesions=[L1], events=[
            removed(), denial('intervention', 'No further intervention was required', kind='intervention',
                              scope=sc('exceptive', 'No further', ['P2']))])
        self.assertEqual(verdict(inventory), ('independent', 'scope', 'exceptive'))

    def test_an_exceptive_scope_whose_words_do_not_bind(self):
        inventory = pairing('No other polyp was removed.', removed(),
                            denial(status_words='No other polyp was removed', scope=sc('exceptive', 'No further', ['P2'])))
        self.assertEqual(verdict(inventory), ('unresolved', 'scope', 'scope_unresolved'))

    def test_a_statement_with_no_scope(self):
        inventory = pairing('No polyp was removed.', removed(), denial(scope=sc()))
        self.assertEqual(verdict(inventory), ('unresolved', 'scope', 'scope_unresolved'))


class Concerns(SimpleTestCase):
    def test_the_intervention_umbrella_concerns_every_act_but_the_examination(self):
        lines = {'P1': POLYP, 'P2': 'No interventions were performed.', 'P3': 'The colonoscope was advanced to the cecum.'}
        inventory = normalized(lines, lesions=[L1], events=[
            removed(), denial('interventions', 'No interventions were performed', kind='intervention'),
            act('E3', 'P3', 'examination', 'colonoscope', status_words='was advanced to the cecum')])
        self.assertEqual(verdict(inventory), CONTRADICTION)
        self.assertEqual(relations_of(inventory, 'E2', 'E3'), [])

    def test_another_kind_is_not_concerned(self):
        inventory = pairing('No biopsies were taken.', removed(),
                            denial('biopsies', 'No biopsies were taken', kind='biopsy'))
        self.assertEqual(relations_of(inventory, 'E2'), [])

    def test_a_tattoo_and_an_injection_are_one_act(self):
        lines = {'P1': 'Saline was injected into the submucosa.', 'P2': 'No tattoo was placed.'}
        inventory = normalized(lines, events=[act('E1', 'P1', 'injection', 'injected', status_words='was injected'),
                                              denial('tattoo', 'No tattoo was placed', kind='tattoo')])
        self.assertEqual(verdict(inventory), CONTRADICTION)

    def test_a_clip_denial_meets_a_clip_placed_for_hemostasis(self):
        lines = {'P1': 'A clip was placed to treat bleeding.', 'P2': 'No clip was placed.'}
        inventory = normalized(lines, events=[
            act('E1', 'P1', 'clip', 'clip', status_words='was placed', purpose=a('hemostasis', 'to treat bleeding',
                                                                                 ['P1'])),
            denial('clip', 'No clip was placed', kind='clip')])
        self.assertEqual(verdict(inventory), CONTRADICTION)


class Claims(SimpleTestCase):
    """C-11: a model's contradicts[] claim is dismissed only by a hard literal; otherwise UNRESOLVED."""

    def claimed(self, lesion_two: dict, line_three: str) -> list:
        denial_ = denial(status_words='was not removed', scope=sc('single_target', 'The 12 mm polyp', ['P2']),
                         target=tg('L2', 'not_stated', 'The 12 mm polyp', ['P2']),
                         contradicts=[{'event': 'E1', 'passages': ['P1', 'P2']}])
        first = les('L1', '4 mm sessile polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                    size_words='4 mm')
        lines = {'P1': 'A 4 mm sessile polyp in the sigmoid colon was removed with a cold snare.',
                 'P2': 'The 12 mm polyp was not removed.', 'P3': line_three}
        inventory = normalized(lines, lesions=[first, lesion_two], events=[
            snare('E1', 'P1', target=tg('L1', 'sigmoid_colon', '4 mm sessile polyp in the sigmoid colon', ['P1'])),
            denial_])
        return relations_of(inventory, 'E2', 'E1')

    def test_a_size_only_difference_never_dismisses_the_claim(self):
        found = self.claimed(les('L2', '12 mm polyp', 'P3', size_words='12 mm'), 'A 12 mm polyp was also seen.')
        self.assertEqual([(item['type'], item['attribute'], item['reason'], item['claimed_by_model'])
                          for item in found], [('unresolved', 'target', 'claim_soft_difference', True)])

    def test_a_disjoint_place_dismisses_it(self):
        found = self.claimed(les('L2', '12 mm polyp', 'P3', landmark='rectum', site_words='rectum', size_words='12 mm'),
                             'A 12 mm polyp was also seen in the rectum.')
        self.assertEqual([(item['type'], item['attribute'], item['reason'], item['claimed_by_model'])
                          for item in found], [('dismissed_claim', 'target', 'another_lesion', True)])

    def test_a_computed_contradiction_stands_and_is_marked_claimed(self):
        inventory = pairing('No polyp was removed.', removed(),
                            denial(contradicts=[{'event': 'E1', 'passages': ['P1', 'P2']}]))
        found = relations_of(inventory, 'E2', 'E1')
        self.assertEqual([(item['type'], item['claimed_by_model']) for item in found], [('contradiction', True)])

    def test_a_claim_about_another_kind_stands_unless_a_hard_literal_sets_the_acts_apart(self):
        # C-11 (review finding 2): a kind is verified by its binding alone (contract 5.6) - no literal - so two kinds
        # never dismiss Gemini's own claim; it asks whether the statement concerns the act
        inventory = pairing('No biopsies were taken.', removed(),
                            denial('biopsies', 'No biopsies were taken', kind='biopsy',
                                   contradicts=[{'event': 'E1', 'passages': ['P2']}]))
        self.assertEqual([(item['type'], item['attribute'], item['reason'], item['claimed_by_model'])
                          for item in relations_of(inventory, 'E2')], [('unresolved', 'kind', 'claim_kind', True)])
        # the twin: another kind at a disjoint place is set apart by the places, a hard literal
        inventory = pairing('No biopsies were taken from the rectum.', removed(),
                            denial('biopsies', 'No biopsies were taken from the rectum', kind='biopsy',
                                   scope=sc('single_target', 'from the rectum', ['P2']),
                                   target=tg('', 'rectum', 'the rectum', ['P2']),
                                   contradicts=[{'event': 'E1', 'passages': ['P2']}]))
        self.assertEqual([(item['type'], item['attribute'], item['reason'], item['claimed_by_model'])
                          for item in relations_of(inventory, 'E2')],
                         [('dismissed_claim', 'target', 'another_site', True)])

    def test_review_a_an_emr_denial_of_the_lesion_the_snare_removed(self):
        # review finding 2, probe A: both sides name the same verified lesion at the same landmark; only the kinds
        # differ, so the claim is a question on the snare's code, never dismissed
        lines = {'P1': 'A 15 mm polyp in the ascending colon was removed with a hot snare.',
                 'P2': 'Impression: the 15 mm ascending colon polyp could not be removed; EMR was not performed.'}
        lesion = les('L1', '15 mm polyp', 'P1', landmark='ascending_colon', site_words='ascending colon',
                     size_words='15 mm')
        inventory = normalized(lines, lesions=[lesion], events=[
            act('E1', 'P1', 'snare', 'removed', status_words='was removed with a hot snare',
                technique=a('hot_snare', 'hot snare', ['P1']),
                target=tg('L1', 'ascending_colon', '15 mm polyp in the ascending colon', ['P1'])),
            act('E2', 'P2', 'emr', 'EMR', status='not_performed', status_words='EMR was not performed',
                scope=sc('single_target', 'the 15 mm ascending colon polyp', ['P2']),
                target=tg('L1', 'ascending_colon', 'the 15 mm ascending colon polyp', ['P2']),
                contradicts=[{'event': 'E1', 'passages': ['P1', 'P2']}])])
        self.assertEqual([item['target']['identity'] for item in inventory.events['events']], ['verified', 'verified'])
        self.assertEqual([(item['type'], item['statement'], item['event'], item['attribute'], item['reason'],
                           item['claimed_by_model']) for item in relations_of(inventory)],
                         [('unresolved', 'E2', 'E1', 'kind', 'claim_kind', True)])

    def test_review_a2_a_family_verified_by_its_binding_alone_never_dismisses_a_claim(self):
        # review finding 2, probe A2: in a single-family encounter a stated procedure is verified by its located words,
        # with no name check, so "another procedure" there is no literal
        lines = {'P1': POLYP, 'P2': 'No polyp was removed.'}
        inventory = normalized(lines, lesions=[L1], events=[
            removed(), denial(procedure=a('egd', 'No polyp', ['P2']), contradicts=[{'event': 'E1', 'passages': ['P2']}])])
        self.assertEqual(inventory.events['events'][1]['procedure']['checks'], ['passages_located', 'words_in_own_passage'])
        self.assertEqual([(item['type'], item['attribute'], item['reason']) for item in relations_of(inventory)],
                         [('unresolved', 'procedure', 'claim_soft_difference')])

    def test_named_families_in_a_multi_family_encounter_dismiss_a_claim(self):
        # the twin: each family named by the procedure-name check (several current families) is a literal
        inventory = normalized(Procedure.LINES, events=[
            act('E0', 'P1', 'examination', 'gastroscope', status_words='was advanced', procedure=a('egd', 'EGD', ['P1'])),
            act('E1', 'P3', 'examination', 'colonoscope', status_words='was advanced to the cecum',
                procedure=a('colonoscopy', 'Colonoscopy', ['P3'])),
            act('E2', 'P2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd', 'EGD', ['P2']),
                technique=a('cold_forceps', 'cold forceps', ['P2']), target=tg('', 'duodenum', 'duodenum', ['P2'])),
            act('E3', 'P4', 'biopsy', 'biopsies', status='not_performed', status_words='no biopsies were taken',
                procedure=a('colonoscopy', 'Colonoscopy', ['P4']), scope=sc('all_of_kind', 'no', ['P4']),
                contradicts=[{'event': 'E2', 'passages': ['P2', 'P4']}])])
        self.assertIn('procedure_name', inventory.events['events'][3]['procedure']['checks'])
        self.assertEqual([(item['type'], item['attribute'], item['reason'], item['claimed_by_model'])
                          for item in relations_of(inventory, 'E3', 'E2')],
                         [('dismissed_claim', 'procedure', 'another_procedure', True)])

    def soft_or_hard(self, line: str, **changes) -> list:
        inventory = normalized({'P1': POLYP, 'P2': line, **ENDOSCOPIST}, lesions=[L1], events=[
            removed(), denial(contradicts=[{'event': 'E1', 'passages': ['P1', 'P2']}], **changes)], **NAMED)
        return [(item['type'], item['attribute'], item['reason']) for item in relations_of(inventory, 'E2', 'E1')]

    def test_review_a_soft_time_performer_or_device_never_dismisses_a_claim(self):
        # review finding 5, mutant (a): a time read by its marker alone, another clinician named by no name, and a
        # device with no surface form ("other") are each a difference the table records, never a hard literal
        soft = 'claim_soft_difference'
        self.assertEqual(self.soft_or_hard('No polyp was previously removed.',
                                           status_words='No polyp was previously removed',
                                           time=a('earlier_encounter', 'previously', ['P2'])),
                         [('unresolved', 'time', soft)])
        self.assertEqual(self.soft_or_hard('No polyp was removed by another physician.',
                                           performer=a('other_clinician', 'another physician', ['P2'])),
                         [('unresolved', 'performer', soft)])
        self.assertEqual(self.soft_or_hard('No Captivator snare was used.', kind_words='snare', kind='snare',
                                           status_words='No Captivator snare was used',
                                           technique=a('other', 'Captivator', ['P2'])),
                         [('unresolved', 'technique', soft)])

    def test_a_dated_time_a_titled_name_or_two_named_devices_dismiss_a_claim(self):
        # the twins: each difference rests on a literal - a date, a titled name, two devices' surface forms
        self.assertEqual(self.soft_or_hard('No polyp was removed in 2024.',
                                           time=a('earlier_encounter', 'in 2024', ['P2'])),
                         [('dismissed_claim', 'time', 'another_time')])
        self.assertEqual(self.soft_or_hard('No polyp was removed by Dr. Lena Ortiz.',
                                           performer=a('other_clinician', 'Dr. Lena Ortiz', ['P2'])),
                         [('dismissed_claim', 'performer', 'another_performer')])
        self.assertEqual(self.soft_or_hard('No hot snare was used.', kind_words='hot snare', kind='snare',
                                           status_words='No hot snare was used',
                                           technique=a('hot_snare', 'hot snare', ['P2'])),
                         [('dismissed_claim', 'technique', 'another_technique')])

    def test_a_claim_between_two_statements(self):
        lines = {'P1': 'No polyp was removed.', 'P2': 'No biopsies were taken.'}
        inventory = normalized(lines, events=[
            denial(eid='E1', passage='P1', contradicts=[{'event': 'E2', 'passages': ['P1', 'P2']}]),
            denial('biopsies', 'No biopsies were taken', kind='biopsy')])
        self.assertEqual([(item['type'], item['reason']) for item in relations_of(inventory, 'E1', 'E2')],
                         [('dismissed_claim', 'no_act')])


class PositiveClaims(SimpleTestCase):
    def test_two_devices_for_one_dilation(self):
        lines = {'P1': 'The stricture was dilated with a balloon.',
                 'P2': 'The stricture was dilated with a Savary dilator over a guidewire.'}
        inventory = normalized(lines, events=[
            act('E1', 'P1', 'dilation', 'dilated', status_words='was dilated', technique=a('balloon', 'balloon', ['P1']),
                contradicts=[{'event': 'E2', 'passages': ['P1', 'P2']}]),
            act('E2', 'P2', 'dilation', 'dilated', status_words='was dilated',
                technique=a('wire_bougie', 'Savary dilator over a guidewire', ['P2']))])
        found = [(item['type'], item['statement'], item['event'], item['attribute'], item['reason'])
                 for item in relations_of(inventory)]
        self.assertEqual(found, [('unresolved', 'E1', 'E2', 'technique', 'claim_technique'),
                                 ('unresolved', 'E2', 'E1', 'technique', 'claim_technique')])

    def test_two_kinds_for_one_act(self):
        lines = {'P1': 'The polyp was removed with a cold snare.', 'P2': 'The polyp was resected by EMR.'}
        inventory = normalized(lines, events=[
            snare('E1', 'P1', contradicts=[{'event': 'E2', 'passages': ['P1', 'P2']}]),
            act('E2', 'P2', 'emr', 'EMR', status_words='was resected')])
        self.assertEqual({(item['statement'], item['event'], item['attribute'], item['reason'])
                          for item in relations_of(inventory)},
                         {('E1', 'E2', 'kind', 'claim_kind'), ('E2', 'E1', 'kind', 'claim_kind')})

    def test_two_acts_at_disjoint_places(self):
        lines = {'P1': 'A polyp in the cecum was removed with a cold snare.',
                 'P2': 'A polyp in the rectum was removed with a cold snare.'}
        inventory = normalized(lines, events=[
            snare('E1', 'P1', target=tg('', 'cecum', 'cecum', ['P1']),
                  contradicts=[{'event': 'E2', 'passages': ['P1', 'P2']}]),
            snare('E2', 'P2', target=tg('', 'rectum', 'rectum', ['P2']))])
        self.assertEqual([(item['type'], item['attribute'], item['reason']) for item in relations_of(inventory)],
                         [('dismissed_claim', 'target', 'another_site')])


class Steps(SimpleTestCase):
    def test_each_verified_part_of_is_a_step_named_by_its_rule(self):
        lines = {'P1': 'A 20 mm flat polyp in the cecum was lifted with a saline injection and resected by EMR.',
                 'P2': 'The snare used for the EMR was a hot snare.'}
        inventory = normalized(lines, events=[
            act('E1', 'P1', 'emr', 'EMR', status_words='resected by EMR'),
            act('E2', 'P1', 'injection', 'saline injection', status_words='was lifted', part_of='E1'),
            act('E3', 'P2', 'snare', 'snare', status_words='was a hot snare', part_of='E1')])
        self.assertEqual([(item['statement'], item['event'], item['reason']) for item in relations_of(inventory)
                          if item['type'] == 'step'], [('E1', 'E2', 'lift_injection'), ('E1', 'E3', 'resection_technique')])
        self.assertEqual([item for item in relations_of(inventory) if item['type'] == 'bundling_identity'], [])

    def test_an_examination_within_another(self):
        lines = {'P1': 'EUS: the echoendoscope was advanced to the duodenum.',
                 'P2': 'EGD: the gastroscope was advanced to the duodenum as part of the EUS.'}
        inventory = normalized(lines, events=[
            act('E1', 'P1', 'examination', 'echoendoscope', status_words='was advanced', procedure=a('eus', 'EUS', ['P1'])),
            act('E2', 'P2', 'examination', 'gastroscope', status_words='was advanced', procedure=a('egd', 'EGD', ['P2']),
                part_of='E1')])
        self.assertEqual([(item['type'], item['reason']) for item in relations_of(inventory, 'E1', 'E2')],
                         [('step', 'endoscopic_portion')])


class BundlingIdentity(SimpleTestCase):
    """6.6 with C-2 and C-5: a bundling whose identity is not established is asked, never READY."""
    LINES = {'P1': 'A 6 mm sessile polyp was seen in the sigmoid colon.', 'P2': 'It was removed with a cold snare.'}

    def biopsy(self, line: str, target: dict, **changes) -> list:
        lines = {**self.LINES, 'P3': line}
        inventory = normalized(lines, lesions=[changes.pop('lesion', L1)], events=[
            snare('E1', 'P2', target=tg('L1', 'not_stated', 'It', ['P2'])),
            act('E2', 'P3', 'biopsy', 'biopsied', status_words='biopsied', target=target)])
        return [(item['statement'], item['event'], item['reason']) for item in relations_of(inventory)
                if item['type'] == 'bundling_identity']

    def test_a_biopsy_whose_lesion_is_not_established_at_a_compatible_place(self):
        found = self.biopsy('The sigmoid colon was biopsied as well.',
                            tg('L1', 'sigmoid_colon', 'sigmoid colon', ['P1']))  # its words are not in its statement
        self.assertEqual(found, [('E1', 'E2', 'biopsy_of_removed_lesion')])

    def test_nothing_is_asked_at_a_disjoint_place(self):
        found = self.biopsy('The rectum was biopsied as well.', tg('L1', 'rectum', 'rectum', ['P3']))
        self.assertEqual(found, [])

    def test_places_that_cannot_be_compared_ask_nothing(self):
        # the E15 shape: a biopsy naming erosions at the anastomosis it is not verified to be, beside a sigmoid polypectomy
        lines = {'P1': 'There were two erosions at the anastomosis.', 'P2': 'A 5 mm polyp in the sigmoid colon was removed.',
                 'P3': 'Biopsies were taken from an inflamed portion of the anastomotic rim.'}
        inventory = normalized(lines, lesions=[
            les('L1', 'two erosions', 'P1', landmark='anastomosis', site_words='anastomosis', multiplicity='group'),
            les('L2', '5 mm polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='5 mm')],
            events=[snare('E1', 'P2', status_words='was removed', technique=a('not_stated'),
                          target=tg('L2', 'sigmoid_colon', '5 mm polyp in the sigmoid colon', ['P2'])),
                    act('E2', 'P3', 'biopsy', 'Biopsies', status_words='were taken',
                        target=tg('L1', 'anastomosis', 'an inflamed portion of the anastomotic rim', ['P3']))])
        self.assertEqual(inventory.events['events'][1]['target']['identity_by']['reasons'], ['identity_no_tie'])
        self.assertEqual([item for item in relations_of(inventory) if item['type'] == 'bundling_identity'], [])

    def test_a_place_unknown_and_one_lesion_named_by_both(self):
        lines = {'P1': 'A sessile polyp was seen.', 'P2': 'It was removed with a cold snare.',
                 'P3': 'Biopsies were also taken.'}
        inventory = normalized(lines, lesions=[les('L1', 'sessile polyp', 'P1')], events=[
            snare('E1', 'P2', target=tg('L1', 'not_stated', 'It', ['P2'])),
            act('E2', 'P3', 'biopsy', 'Biopsies', status_words='were also taken',
                target=tg('L1', 'not_stated', 'sessile polyp', ['P1']))])  # its words are not in its statement
        self.assertEqual([(item['statement'], item['event'], item['reason']) for item in relations_of(inventory)
                          if item['type'] == 'bundling_identity'], [('E1', 'E2', 'biopsy_of_removed_lesion')])

    def test_nothing_is_asked_on_one_verified_single_lesion(self):
        self.assertEqual(self.biopsy('It was biopsied before the removal.', tg('L1', 'not_stated', 'It', ['P3'])), [])

    def test_c2_a_group_lesion_whose_acts_cite_no_common_passage(self):
        group = les('L1', 'three 3 mm sessile polyps', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                    multiplicity='group')
        lines = {'P1': 'There were three 3 mm sessile polyps in the sigmoid colon.',
                 'P2': 'These polyps were removed with a cold snare.', 'P3': 'These polyps were biopsied before.'}
        inventory = normalized(lines, lesions=[group], events=[
            snare('E1', 'P2', status_words='were removed with a cold snare',
                  target=tg('L1', 'not_stated', 'These polyps', ['P2'])),
            act('E2', 'P3', 'biopsy', 'biopsied', status_words='biopsied',
                target=tg('L1', 'not_stated', 'These polyps', ['P3']))])
        self.assertEqual([(item['statement'], item['event'], item['reason']) for item in relations_of(inventory)
                          if item['type'] == 'bundling_identity'], [('E1', 'E2', 'biopsy_of_removed_lesion')])
        lines = {'P1': 'There were three 3 mm sessile polyps in the sigmoid colon.',
                 'P2': 'These polyps were biopsied and then removed with a cold snare.'}
        common = normalized(lines, lesions=[group], events=[
            snare('E1', 'P2', status_words='removed with a cold snare',
                  target=tg('L1', 'not_stated', 'These polyps', ['P2'])),
            act('E2', 'P2', 'biopsy', 'biopsied', status_words='biopsied',
                target=tg('L1', 'not_stated', 'These polyps', ['P2']))])
        self.assertEqual([item for item in relations_of(common) if item['type'] == 'bundling_identity'], [])

    def test_c5_an_injection_beside_an_emr(self):
        def inventory(line: str, **changes):
            lines = {'P1': 'A 20 mm flat polyp in the cecum was resected by EMR.', 'P2': line}
            return normalized(lines, events=[
                act('E1', 'P1', 'emr', 'EMR', status_words='was resected', target=tg('', 'cecum', 'cecum', ['P1'])),
                act('E2', 'P2', changes.pop('kind', 'injection'), changes.pop('words', 'injection'),
                    status_words='was given', **changes)])

        def asked(found):
            return [(item['statement'], item['event'], item['reason']) for item in relations_of(found)
                    if item['type'] == 'bundling_identity']

        self.assertEqual(asked(inventory('A submucosal injection was given.')), [('E1', 'E2', 'lift_injection')])
        self.assertEqual(asked(inventory('A submucosal injection was given in the cecum.',
                                         target=tg('', 'cecum', 'cecum', ['P2']))), [])  # bundled: no question
        self.assertEqual(asked(inventory('A submucosal injection was given in the rectum.',
                                         target=tg('', 'rectum', 'rectum', ['P2']))), [])  # another place
        self.assertEqual(asked(inventory('A tattoo was given.', kind='tattoo', words='tattoo')), [])
        self.assertEqual(asked(inventory('An injection was given for hemostasis.',
                                         purpose=a('hemostasis', 'for hemostasis', ['P2']))), [])

    def test_a_snare_beside_an_emr_of_a_lesion_it_is_not_verified_to_be(self):
        lines = {'P1': 'A 20 mm flat polyp was seen in the cecum.', 'P2': 'It was resected by EMR.',
                 'P3': 'A snare was used in the cecum.'}
        inventory = normalized(lines, lesions=[les('L1', '20 mm flat polyp', 'P1', landmark='cecum', site_words='cecum')],
                               events=[act('E1', 'P2', 'emr', 'EMR', status_words='was resected',
                                           target=tg('L1', 'not_stated', 'It', ['P2'])),
                                       act('E2', 'P3', 'snare', 'snare', status_words='was used',
                                           target=tg('L1', 'cecum', 'cecum', ['P1']))])
        self.assertEqual([(item['statement'], item['event'], item['reason']) for item in relations_of(inventory)
                          if item['type'] == 'bundling_identity'], [('E1', 'E2', 'resection_technique')])

    @staticmethod
    def asked(inventory) -> list:
        return [(item['statement'], item['event'], item['reason']) for item in relations_of(inventory)
                if item['type'] == 'bundling_identity']

    def test_review_no_lesion_named_one_statement_asks(self):
        # review finding 4 (P3): neither act names a lesion, both are stated in one passage at one place (or none): the
        # identity is a missing identifier, so the bundling is asked - legacy _one_resection's one-clause rule, asked
        # instead of decided - never left as two acts each READY
        lines = {'P1': 'A 20 mm flat polyp in the cecum was resected by EMR using a hot snare.'}
        for place in (tg('', 'cecum', 'cecum', ['P1']), tg()):
            inventory = normalized(lines, events=[
                act('E1', 'P1', 'emr', 'EMR', status_words='was resected by EMR', target=place),
                act('E2', 'P1', 'snare', 'hot snare', status_words='was resected',
                    technique=a('hot_snare', 'hot snare', ['P1']), target=place)])
            with self.subTest(place=place['landmark']):
                self.assertEqual(self.asked(inventory), [('E1', 'E2', 'resection_technique')])
        lines = {'P1': 'A 6 mm polyp in the cecum was biopsied and then removed with a cold snare.'}
        inventory = normalized(lines, events=[
            snare('E1', 'P1', status_words='removed with a cold snare', target=tg('', 'cecum', 'cecum', ['P1'])),
            act('E2', 'P1', 'biopsy', 'biopsied', status_words='was biopsied', target=tg('', 'cecum', 'cecum', ['P1']))])
        self.assertEqual(self.asked(inventory), [('E1', 'E2', 'biopsy_of_removed_lesion')])

    def test_no_lesion_named_in_separate_statements_or_at_disjoint_places_asks_nothing(self):
        # the twins: random biopsies told in their own statement are their own act; so are acts of one statement at
        # places set apart by their verified landmarks
        lines = {'P1': 'A 6 mm polyp in the cecum was removed with a cold snare.',
                 'P2': 'Random biopsies were taken from the colon.'}
        inventory = normalized(lines, events=[
            snare('E1', 'P1', status_words='was removed with a cold snare', target=tg('', 'cecum', 'cecum', ['P1'])),
            act('E2', 'P2', 'biopsy', 'biopsies', status_words='were taken', target=tg('', 'colon', 'colon', ['P2']))])
        self.assertEqual(self.asked(inventory), [])
        lines = {'P1': 'A polyp in the cecum was removed with a cold snare and biopsies were taken from the rectum.'}
        inventory = normalized(lines, events=[
            snare('E1', 'P1', status_words='was removed with a cold snare', target=tg('', 'cecum', 'cecum', ['P1'])),
            act('E2', 'P1', 'biopsy', 'biopsies', status_words='were taken', target=tg('', 'rectum', 'rectum', ['P1']))])
        self.assertEqual(self.asked(inventory), [])

    def test_one_act_verified_to_a_lesion_and_one_naming_none_are_each_their_own(self):
        # Gemini tied the removal to the polyp and left the biopsy's lesion "" - its reading that the document does not
        # tie the biopsy to that listed lesion (the prompt's target rule) - so even in one statement nothing is asked
        lines = {'P1': 'A 6 mm polyp in the cecum was removed with a cold snare and biopsies were taken from the colon.'}
        inventory = normalized(lines, lesions=[les('L1', '6 mm polyp', 'P1', landmark='cecum', site_words='cecum')],
                               events=[snare('E1', 'P1', status_words='was removed with a cold snare',
                                             target=tg('L1', 'cecum', '6 mm polyp in the cecum', ['P1'])),
                                       act('E2', 'P1', 'biopsy', 'biopsies', status_words='were taken',
                                           target=tg('', 'colon', 'colon', ['P1']))])
        self.assertEqual([item['target']['identity'] for item in inventory.events['events']], ['verified', 'none'])
        self.assertEqual(self.asked(inventory), [])

    def test_review_an_unverified_link_never_sets_two_acts_apart(self):
        # review finding 6: the biopsy's own verified place is the removed polyp's; Gemini links it to the rectal polyp,
        # a link the literal check fails. That link's site is no place of the biopsy's, so it cannot set the acts apart
        lines = {'P1': 'A 6 mm polyp in the sigmoid colon was seen.', 'P2': 'It was removed with a cold snare.',
                 'P3': 'A 4 mm polyp was seen in the rectum.', 'P4': 'Biopsies were taken in the sigmoid colon.'}
        lesions = [les('L1', '6 mm polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='6 mm'),
                   les('L2', '4 mm polyp', 'P3', landmark='rectum', site_words='rectum', size_words='4 mm')]

        def biopsy(line: str, target: dict):
            inventory = normalized({**lines, 'P4': line}, lesions=lesions, events=[
                snare('E1', 'P2', target=tg('L1', 'not_stated', 'It', ['P2'])),
                act('E2', 'P4', 'biopsy', 'Biopsies', status_words='were taken', target=target)])
            return inventory.events['events'][1]['target'], self.asked(inventory)

        target, asked = biopsy('Biopsies were taken in the sigmoid colon.',
                               tg('L2', 'sigmoid_colon', 'sigmoid colon', ['P4']))
        self.assertEqual((target['identity'], target['identity_by']['reasons']),
                         ('unresolved', ['identity_literal_conflict']))
        self.assertEqual(asked, [('E1', 'E2', 'biopsy_of_removed_lesion')])
        # nor through the lesion it names: with no place of its own, its unverified link to a lesion distinct from the
        # removed one establishes no difference either (P3)
        target, asked = biopsy('Biopsies were taken.', tg('L2', 'not_stated', '4 mm polyp', ['P3']))
        self.assertEqual((target['identity'], target['identity_by']['reasons']),
                         ('unresolved', ['identity_not_in_statement']))
        self.assertEqual(asked, [('E1', 'E2', 'biopsy_of_removed_lesion')])
        # the twin: the biopsy's OWN verified place is disjoint from the removal's - nothing is asked, even though it
        # names (unverified) the removed lesion
        target, asked = biopsy('Biopsies were taken in the rectum.', tg('L1', 'rectum', 'rectum', ['P4']))
        self.assertEqual((target['identity'], target['identity_by']['reasons']),
                         ('unresolved', ['identity_literal_conflict']))
        self.assertEqual(asked, [])


def stored_scenarios() -> list:
    """(lines, events, lesions) whose relations, together, are every relation type."""
    emr = {'P1': 'A 20 mm flat polyp in the cecum was resected by EMR.', 'P2': 'A submucosal injection was given.',
           'P3': 'The snare was part of the EMR.'}
    return [
        ({'P1': POLYP, 'P2': 'No polyp was removed.'},
         [removed(), denial(contradicts=[{'event': 'E1', 'passages': []}])], [L1]),
        ({'P1': POLYP, 'P2': 'It is unclear whether any polyp was removed.'},
         [removed(), act('E2', 'P2', 'removal', 'removed', status='uncertain',
                         status_words='It is unclear whether any polyp was removed',
                         scope=sc('all_of_kind', 'any', ['P2']))], [L1]),
        ({'P1': POLYP, 'P2': 'No other polyp was removed.'},
         [removed(), denial(status_words='No other polyp was removed', scope=sc('exceptive', 'No other', ['P2']))],
         [L1]),
        ({'P1': POLYP, 'P2': 'No polyp was removed.'},
         [removed(), denial(time=a('unknown'), contradicts=[{'event': 'E9', 'passages': []}])], [L1]),
        (emr, [act('E1', 'P1', 'emr', 'EMR', status_words='was resected', target=tg('', 'cecum', 'cecum', ['P1'])),
               act('E2', 'P2', 'injection', 'injection', status_words='was given'),
               act('E3', 'P3', 'snare', 'snare', status_words='was part of the EMR', part_of='E1')], []),
        ({'P1': POLYP, 'P2': 'No biopsies were taken.'},
         [removed(), denial('biopsies', 'No biopsies were taken', kind='biopsy',
                            contradicts=[{'event': 'E1', 'passages': []}])], [L1]),
    ]


class Stored(SimpleTestCase):
    def test_every_relation_type_is_stored_and_read_back(self):
        types, reasons = set(), set()
        for index, (lines, events, lesions) in enumerate(stored_scenarios()):
            value, text = answer(lines, events=events, lesions=lesions)
            inventory = normalize.normalize(accepted(value), text)
            fields = store.row(encounter_id=ENCOUNTER, revision_id=REVISION, provider_run_id=RUN, revision_text=text,
                               text_sha256=inventory.text_sha256, request_sha256='2' * 64, response_sha256='3' * 64,
                               **inventory.content())
            loaded = store.load(json.loads(json.dumps(fields)), text_sha256=inventory.text_sha256,
                                response_sha256='3' * 64)
            with self.subTest(index=index):
                self.assertEqual(loaded.events, inventory.events)
            types.update(item['type'] for item in inventory.events['relations'])
            reasons.update(item['reason'] for item in inventory.events['relations'])
        self.assertEqual(types, set(store.RELATION_TYPES))
        self.assertEqual(relations.TYPES, store.RELATION_TYPES)
        self.assertLessEqual(reasons, set(relations.REASONS) | {'claim_unknown_event'})


class ClosedLists(SimpleTestCase):
    def test_the_attributes_and_rows(self):
        self.assertEqual(relations.ROWS, ('procedure', 'time', 'performer', 'technique', 'target'))
        self.assertEqual(len(set(relations.REASONS)), len(relations.REASONS))
        self.assertLessEqual(set(relations.ROWS), set(relations.ATTRIBUTES))


if __name__ == '__main__':  # pragma: no cover
    sys.exit('Run with manage.py test.')
