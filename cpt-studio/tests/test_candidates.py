"""Candidate answers to open questions (HARNESS.md 11.3, 12.5): the sources of each fact, the value in CPT Studio's own
words, the verification - located passages, exact spans, no page break, the consistency check of each fact - the merge
of identical candidates, their ids and phases, and that agreement never verifies one. Pure; synthetic data only."""
import hashlib

from django.test import SimpleTestCase

from studio import candidates as c
from studio.participants import prompt, reading
from studio.types import (EvidenceSpan, LocatedQuote, PageSpan, ParticipantReading, ParticipantService, QuestionAnswer,
                          canonical_json)

NOTE = ('SYNTHETIC TEST DOCUMENT - not a real patient.\n'
        'GI Procedure Report\n'
        'Date of service: 2026-10-21\n'
        'Indication: Screening colonoscopy; the last colonoscopy reached the cecum in 2019.\n'
        'Procedure: Colonoscopy.\n'
        'Technique: The colonoscope was advanced to the cecum. The appendiceal orifice was identified.\n'
        'Findings: A 6 mm polyp in the ascending colon was removed with a cold snare.\n'
        'History: Colonoscopy in 2019 reached the terminal ileum.\n'
        'Plan: Repeat colonoscopy in 7 years.\n')
BREAK = NOTE.index('Findings:')
PAGES = (PageSpan(page=1, start=0, end=BREAK), PageSpan(page=2, start=BREAK, end=len(NOTE)))
DATE_QUOTE = 'Date of service: 2026-10-21'
CECUM_QUOTE = 'The colonoscope was advanced to the cecum.'
SNARE_QUOTE = 'A 6 mm polyp in the ascending colon was removed with a cold snare.'
PLAN_QUOTE = 'Repeat colonoscopy in 7 years.'
HISTORY_QUOTE = 'Colonoscopy in 2019 reached the terminal ileum.'
INDICATION_QUOTE = 'Screening colonoscopy; the last colonoscopy reached the cecum in 2019.'
ERCP_NOTE = ('SYNTHETIC TEST DOCUMENT - not a real patient.\nProcedure: ERCP.\n'
             'Technique: Deep biliary cannulation was achieved with a sphincterotome. A stone was removed.\n')
EUS_NOTE = ('SYNTHETIC TEST DOCUMENT - not a real patient.\n'
            'Procedure: EUS of the pancreatic head mass with fine needle aspiration.\n'
            'Findings: Two lymph nodes were seen near the celiac axis.\n')
OFFICE_NOTE = ('SYNTHETIC TEST DOCUMENT - not a real patient.\nOffice visit for follow-up of reflux.\n'
               'Total time on the date of the encounter was 24 minutes.\n'
               'Medical decision making: moderate complexity.\nTotal procedure time 30 minutes.\n')
DATE = c.Question(id='q-date', scope='encounter', fact='service_date')
EXTENT = c.Question(id='q-extent', scope='proposal', fact='extent', family='gi.colonoscopy', proposal_key='sel:0')
STATUS = c.Question(id='q-status', scope='proposal', fact='performed_status', family='gi.colonoscopy',
                    proposal_key='sel:1')
TARGET = c.Question(id='q-target', scope='service', fact='target', family='gi.eus')
CANNULATION = c.Question(id='q-cannulation', scope='service', fact='cannulation', family='gi.ercp')
BASIS = c.Question(id='q-basis', scope='proposal', fact='em_basis', family='gi.office_em', proposal_key='sel:0')


def located(text, quote):
    return reading.Locator(text).locate(quote)


def service(text, family='colonoscopy', *, status='performed', extent='', anatomy='', quotes=(), service_id='s1'):
    return ParticipantService(id=service_id, family=family, status=status, description='', anatomy=anatomy,
                              extent=extent, technique='', evidence=tuple(located(text, q) for q in quotes))


def frozen(name, text, *, date='', date_quotes=(), services=(), refused=False, run=None):
    model = {'astra': 'gpt-6-astra', 'fable': 'claude-fable-5-1'}[name]
    item = ParticipantReading(provider=name, adapter_version=f'{name}-test@2', reading_version=prompt.READING_VERSION,
                              requested_model=model, returned_model=model, date_of_service=date,
                              date_evidence=tuple(located(text, q) for q in date_quotes), services=tuple(services),
                              refused=refused)
    return c.FrozenReading(name=name, run=run or f'run-{name}-1', reading=item)


def peer(name, text, value, *quotes, settled=True, question='q', run=None):
    answer = QuestionAnswer(question_id=question, settled=settled, value=value,
                            evidence=tuple(located(text, q) for q in quotes))
    return c.PeerAnswer(name=name, run=run or f'run-{name}-peer', answer=answer)


class DateTests(SimpleTestCase):
    def test_a_located_passage_stating_the_date_is_verified(self):
        (candidate,) = c.candidates(DATE, NOTE, PAGES, [frozen('astra', NOTE, date='2026-10-21',
                                                               date_quotes=[DATE_QUOTE])])
        start = NOTE.index(DATE_QUOTE)
        self.assertEqual(candidate, {
            'id': candidate['id'], 'clarification_id': 'q-date', 'fact': 'service_date', 'value': '2026-10-21',
            'located_by': ['astra'], 'phase': 'independent', 'phases': {'astra': 'independent'},
            'runs': ['run-astra-1'],
            'spans': [{'start': start, 'end': start + len(DATE_QUOTE), 'text': DATE_QUOTE, 'page': 1}],
            'verified': True, 'why': '', 'attestation': c.attestation('2026-10-21')})

    def test_a_passage_that_states_no_such_calendar_date_is_unverified(self):
        (candidate,) = c.candidates(DATE, NOTE, PAGES, [frozen('astra', NOTE, date='2026-10-21',
                                                               date_quotes=['Procedure: Colonoscopy.'])])
        self.assertEqual((candidate['verified'], candidate['why'], candidate['attestation']),
                         (False, 'The passage does not state 2026-10-21 as a calendar date.', ''))
        # a year names no calendar date at day precision
        (candidate,) = c.candidates(DATE, NOTE, PAGES, [frozen('fable', NOTE, date='2019-01-01',
                                                               date_quotes=[HISTORY_QUOTE])])
        self.assertFalse(candidate['verified'])
        self.assertIn('does not state 2019-01-01', candidate['why'])

    def test_a_peer_answer_is_restated_as_a_calendar_date_or_left_unverified(self):
        out = c.candidates(DATE, NOTE, PAGES, answers=[peer('fable', NOTE, 'October 21, 2026', DATE_QUOTE)])
        self.assertEqual([(x['value'], x['verified'], x['phase']) for x in out], [('2026-10-21', True, 'peer_review')])
        (unverified,) = c.candidates(DATE, NOTE, PAGES,
                                     answers=[peer('fable', NOTE, '2026-10-21 or 2026-10-22', DATE_QUOTE)])
        self.assertEqual((unverified['value'], unverified['verified']), ('', False))
        self.assertEqual(unverified['why'], 'The value qualifies its date (a negation, a doubt or an alternative).')


class ExtentTests(SimpleTestCase):
    def reading(self, extent, *quotes):
        return frozen('astra', NOTE, services=[service(NOTE, extent=extent, quotes=quotes)])

    def test_the_passage_must_name_the_landmark_the_value_names(self):
        (verified,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading('to the cecum', CECUM_QUOTE)])
        self.assertEqual((verified['value'], verified['verified'], verified['why']), ('cecum', True, ''))
        (unverified,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading('cecum', PLAN_QUOTE)])
        self.assertEqual((unverified['value'], unverified['verified'], unverified['why']),
                         ('cecum', False, 'The passage does not name the cecum.'))

    def test_a_value_naming_two_landmarks_or_qualifying_itself_has_no_value(self):
        (two,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading('cecum and terminal ileum', CECUM_QUOTE)])
        self.assertEqual((two['value'], two['verified'], two['why']),
                         ('', False, 'The value names more than one landmark (cecum, terminal ileum).'))
        # never restated as the landmark it denies: "cecum not reached" is no candidate for "cecum"
        (denied,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading('cecum not reached', CECUM_QUOTE)])
        self.assertEqual((denied['value'], denied['verified']), ('', False))
        self.assertIn('says more than a landmark reached', denied['why'])
        (none,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading('the whole colon', CECUM_QUOTE)])
        self.assertEqual(none['why'], 'The value names no landmark CPT Studio reads.')

    def test_the_value_is_cpt_studio_s_label_never_the_participant_s_wording(self):
        (candidate,) = c.candidates(EXTENT, NOTE, PAGES,
                                    [self.reading('Cecum (appendiceal orifice seen) - 45378 colonoscopy', CECUM_QUOTE)])
        self.assertEqual(candidate['value'], 'cecum')
        self.assertEqual(c.attestation(candidate['value']),
                         'I read this passage in the source document; it documents cecum for this encounter.')

    def test_upper_tract_labels_take_the_most_specific_landmark(self):
        self.assertEqual(c.canonical_value('extent', 'gi.egd', 'the second part of the duodenum'),
                         ('second part of duodenum', ''))
        self.assertEqual(c.canonical_value('extent', 'gi.eus', 'cecum'),
                         ('', 'the value is an extent of a service whose landmarks CPT Studio does not read'))


class TargetTests(SimpleTestCase):
    def test_the_passage_must_name_the_structure_the_value_names(self):
        question = TARGET
        good = frozen('fable', EUS_NOTE, services=[service(
            EUS_NOTE, 'eus', anatomy='Pancreatic head mass',
            quotes=['EUS of the pancreatic head mass with fine needle aspiration.'])])
        (verified,) = c.candidates(question, EUS_NOTE, (), [good])
        self.assertEqual((verified['value'], verified['verified']), ('pancreatic head mass', True))
        other = frozen('fable', EUS_NOTE, services=[service(
            EUS_NOTE, 'eus', anatomy='pancreatic head mass',
            quotes=['Two lymph nodes were seen near the celiac axis.'])])
        (unverified,) = c.candidates(question, EUS_NOTE, (), [other])
        self.assertEqual(unverified['why'], 'The passage does not name the pancreatic head mass.')
        unknown = frozen('fable', EUS_NOTE, services=[service(EUS_NOTE, 'eus', anatomy='liver',
                                                              quotes=['Two lymph nodes were seen'])])
        self.assertEqual(c.candidates(question, EUS_NOTE, (), [unknown])[0]['why'],
                         'The value names no structure CPT Studio reads.')


class CannulationTests(SimpleTestCase):
    QUOTE = 'Deep biliary cannulation was achieved with a sphincterotome.'

    def test_only_a_peer_answer_offers_one(self):
        reading_only = frozen('astra', ERCP_NOTE, services=[service(ERCP_NOTE, 'ercp', extent='bile duct',
                                                                    quotes=[self.QUOTE])])
        self.assertEqual(c.candidates(CANNULATION, ERCP_NOTE, (), [reading_only]), [])
        (verified,) = c.candidates(CANNULATION, ERCP_NOTE, (), answers=[peer('astra', ERCP_NOTE, 'Successful.',
                                                                            self.QUOTE)])
        self.assertEqual((verified['value'], verified['verified'], verified['phase']),
                         ('successful', True, 'peer_review'))

    def test_the_passage_must_state_the_value_s_outcome(self):
        (other,) = c.candidates(CANNULATION, ERCP_NOTE, (), answers=[peer('astra', ERCP_NOTE, 'failed', self.QUOTE)])
        self.assertEqual(other['why'], 'The passage states a successful cannulation, not a failed one.')
        (none,) = c.candidates(CANNULATION, ERCP_NOTE, (), answers=[peer('astra', ERCP_NOTE, 'successful',
                                                                         'A stone was removed.')])
        self.assertEqual(none['why'], 'The passage states no cannulation outcome.')
        (doubt,) = c.candidates(CANNULATION, ERCP_NOTE, (), answers=[peer('astra', ERCP_NOTE, 'probably successful',
                                                                          self.QUOTE)])
        self.assertEqual((doubt['value'], doubt['verified']), ('', False))


class StatusTests(SimpleTestCase):
    def candidate(self, status, quote):
        return c.candidates(STATUS, NOTE, PAGES, [frozen('astra', NOTE, services=[service(NOTE, status=status,
                                                                                         quotes=[quote])])])

    def test_a_passage_outside_history_plan_and_indication_is_verified(self):
        (verified,) = self.candidate('performed', SNARE_QUOTE)
        self.assertEqual((verified['value'], verified['verified'], verified['spans'][0]['page']),
                         ('performed', True, 2))

    def test_history_plan_and_indication_never_verify_a_status(self):
        for quote, kind in ((PLAN_QUOTE, 'plan'), (HISTORY_QUOTE, 'history'), (INDICATION_QUOTE, 'indication')):
            for status in ('performed', 'planned', 'historical'):
                (candidate,) = self.candidate(status, quote)
                self.assertFalse(candidate['verified'], (quote, status))
                self.assertEqual(candidate['why'], f'The passage is in a {kind} section, which never documents a '
                                                   'service at this encounter.')

    def test_attempted_and_unclear(self):
        (attempted,) = self.candidate('attempted_incomplete', SNARE_QUOTE)
        self.assertEqual((attempted['value'], attempted['verified']), ('', False))
        self.assertIn('attempted, incomplete service', attempted['why'])
        self.assertEqual(self.candidate('unclear', SNARE_QUOTE), [])  # the participant does not settle it
        (answer,) = c.candidates(STATUS, NOTE, PAGES, answers=[peer('fable', NOTE, 'not performed', SNARE_QUOTE)])
        self.assertEqual((answer['value'], answer['verified']), ('not performed', True))
        (odd,) = c.candidates(STATUS, NOTE, PAGES, answers=[peer('fable', NOTE, 'done', SNARE_QUOTE)])
        self.assertEqual((odd['value'], odd['verified']), ('', False))

    def test_a_quote_located_twice_needs_every_occurrence_to_pass(self):
        text = NOTE + 'History: The colonoscope was advanced to the cecum.\n'
        (candidate,) = c.candidates(STATUS, text, (), [frozen('astra', text, services=[service(
            text, quotes=[CECUM_QUOTE])])])
        self.assertEqual(len(candidate['spans']), 2)
        self.assertEqual((candidate['verified'], candidate['why']),
                         (False, 'The passage is in a history section, which never documents a service at this '
                                 'encounter.'))
        (extent,) = c.candidates(EXTENT, text, (), [frozen('astra', text, services=[service(
            text, extent='cecum', quotes=[CECUM_QUOTE])])])
        self.assertEqual((len(extent['spans']), extent['verified']), (2, True))


class BasisTests(SimpleTestCase):
    TIME = 'Total time on the date of the encounter was 24 minutes.'
    MDM = 'Medical decision making: moderate complexity.'

    def test_each_reading_quote_stating_time_or_a_level_is_a_candidate(self):
        visit = service(OFFICE_NOTE, 'office_em', quotes=[self.TIME, self.MDM, 'Office visit for follow-up of reflux.',
                                                          'Total procedure time 30 minutes.'])
        out = c.candidates(BASIS, OFFICE_NOTE, (), [frozen('astra', OFFICE_NOTE, services=[visit])])
        self.assertEqual([(x['value'], x['verified'], x['spans'][0]['text']) for x in out],
                         [('time', True, self.TIME), ('mdm', True, self.MDM)])

    def test_a_peer_answer_must_state_what_its_passage_states(self):
        (wrong,) = c.candidates(BASIS, OFFICE_NOTE, (), answers=[peer('fable', OFFICE_NOTE, 'total time', self.MDM)])
        self.assertEqual(wrong['why'], 'The passage states no total time in minutes.')
        (right,) = c.candidates(BASIS, OFFICE_NOTE, (), answers=[peer('fable', OFFICE_NOTE, 'MDM moderate', self.MDM)])
        self.assertEqual((right['value'], right['verified']), ('mdm', True))
        (procedure,) = c.candidates(BASIS, OFFICE_NOTE, (), answers=[peer('fable', OFFICE_NOTE, 'time',
                                                                          'Total procedure time 30 minutes.')])
        self.assertFalse(procedure['verified'])


class VerificationTests(SimpleTestCase):
    def reading_with(self, *quotes, text=NOTE):
        visit = ParticipantService(id='s1', family='colonoscopy', status='performed', description='', anatomy='',
                                   extent='cecum', technique='', evidence=tuple(quotes))
        return frozen('astra', text, services=[visit])

    def test_a_span_that_is_not_an_exact_slice_is_never_verified(self):
        start = NOTE.index(CECUM_QUOTE)
        forged = LocatedQuote(quote=CECUM_QUOTE, spans=(EvidenceSpan(0, start, start + len(CECUM_QUOTE),
                                                                     'The colonoscope was advanced to the cecum!',
                                                                     True),))
        (candidate,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading_with(forged)])
        self.assertEqual(candidate['why'], 'A passage is not an exact slice of the document text.')

    def test_a_span_across_a_page_break_is_never_verified(self):
        quote = NOTE[BREAK - 30:BREAK + 20]
        spans = (EvidenceSpan(0, BREAK - 30, BREAK + 20, quote, True),)
        visit = ParticipantService(id='s1', family='colonoscopy', status='performed', description='', anatomy='',
                                   extent='cecum', technique='', evidence=(LocatedQuote(quote=quote, spans=spans),))
        (candidate,) = c.candidates(EXTENT, NOTE, PAGES, [frozen('astra', NOTE, services=[visit])])
        self.assertEqual(candidate['why'], 'A passage runs across a page break (a [Page N] line).')
        (no_pages,) = c.candidates(EXTENT, NOTE, (), [frozen('astra', NOTE, services=[visit])])
        self.assertNotIn('page break', no_pages['why'])

    def test_more_than_eight_spans_is_never_verified(self):
        text = 'SYNTHETIC.\n' + 'The colonoscope was advanced to the cecum.\n' * 9
        spans = tuple(EvidenceSpan(0, at, at + len(CECUM_QUOTE), CECUM_QUOTE, True)
                      for at in [i for i in range(len(text)) if text.startswith(CECUM_QUOTE, i)])
        self.assertEqual(len(spans), 9)
        (candidate,) = c.candidates(EXTENT, text, (), [self.reading_with(LocatedQuote(CECUM_QUOTE, spans), text=text)])
        self.assertEqual(candidate['why'], 'It cites more than 8 passages.')

    def test_a_quote_not_found_or_too_short_and_no_quote_at_all(self):
        missing_quote = located(NOTE, 'The scope reached the cecum.')
        (missing,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading_with(missing_quote)])
        self.assertEqual((missing['spans'], missing['verified']), ([], False))
        self.assertTrue(missing['why'].startswith('Its quote was not found verbatim'))
        (short,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading_with(located(NOTE, 'cecum'))])
        self.assertTrue(short['why'].startswith('Its quote is too short'))
        (bare,) = c.candidates(EXTENT, NOTE, PAGES, [self.reading_with()])
        self.assertEqual(bare['why'], 'No passage is cited for this value.')


class MergeAndIdentityTests(SimpleTestCase):
    def both(self, value_astra='cecum', value_fable='cecum', quote_fable=CECUM_QUOTE):
        return [frozen('astra', NOTE, services=[service(NOTE, extent=value_astra, quotes=[CECUM_QUOTE])]),
                frozen('fable', NOTE, services=[service(NOTE, extent=value_fable, quotes=[quote_fable])])]

    def test_identical_candidates_merge_naming_every_participant(self):
        (candidate,) = c.candidates(EXTENT, NOTE, PAGES, self.both(value_fable='Cecum'))
        self.assertEqual((candidate['located_by'], candidate['runs'], candidate['phases']),
                         (['astra', 'fable'], ['run-astra-1', 'run-fable-1'],
                          {'astra': 'independent', 'fable': 'independent'}))
        spans = [(candidate['spans'][0]['start'], candidate['spans'][0]['end'])]
        identity = canonical_json(['q-extent', 'extent', 'cecum', [list(spans[0])], ['astra', 'fable']])
        self.assertEqual(candidate['id'], hashlib.sha256(identity).hexdigest()[:16])
        # another passage is another candidate
        self.assertEqual(len(c.candidates(EXTENT, NOTE, PAGES, self.both(quote_fable='advanced to the cecum'))), 2)

    def test_agreement_never_verifies(self):
        out = c.candidates(EXTENT, NOTE, PAGES, [
            frozen('astra', NOTE, services=[service(NOTE, extent='cecum', quotes=[PLAN_QUOTE])]),
            frozen('fable', NOTE, services=[service(NOTE, extent='cecum', quotes=[PLAN_QUOTE])])],
            answers=[peer('astra', NOTE, 'cecum', PLAN_QUOTE), peer('fable', NOTE, 'cecum', PLAN_QUOTE)])
        (candidate,) = out
        self.assertEqual((candidate['located_by'], candidate['verified']), (['astra', 'fable'], False))

    def test_phases_a_candidate_located_first_in_peer_review_is_never_independent(self):
        out = c.candidates(EXTENT, NOTE, PAGES, [frozen('astra', NOTE, services=[service(
            NOTE, extent='cecum', quotes=[CECUM_QUOTE])])], answers=[peer('fable', NOTE, 'cecum', CECUM_QUOTE)])
        (candidate,) = out
        self.assertEqual((candidate['phase'], candidate['phases'], candidate['runs']),
                         ('independent', {'astra': 'independent', 'fable': 'peer_review'},
                          ['run-astra-1', 'run-fable-peer']))
        (later,) = c.candidates(EXTENT, NOTE, PAGES, answers=[peer('fable', NOTE, 'cecum', CECUM_QUOTE)])
        self.assertEqual((later['phase'], later['phases']), ('peer_review', {'fable': 'peer_review'}))

    def test_deterministic_whatever_the_order_given(self):
        readings = self.both(quote_fable='advanced to the cecum')
        answers = [peer('fable', NOTE, 'cecum', PLAN_QUOTE), peer('astra', NOTE, 'cecum', CECUM_QUOTE)]
        first = c.candidates(EXTENT, NOTE, PAGES, readings, answers)
        self.assertEqual(first, c.candidates(EXTENT, NOTE, PAGES, list(reversed(readings)), list(reversed(answers))))
        self.assertEqual([x['verified'] for x in first], [True, True, False])
        self.assertEqual(len({x['id'] for x in first}), 3)


class NothingToOfferTests(SimpleTestCase):
    def test_a_corti_only_encounter_has_no_candidates(self):
        for question in (DATE, EXTENT, STATUS, TARGET, CANNULATION, BASIS):
            self.assertEqual(c.candidates(question, NOTE, PAGES), [])

    def test_a_question_no_candidate_answers(self):
        reading_ = [frozen('astra', NOTE, date='2026-10-21', date_quotes=[DATE_QUOTE],
                           services=[service(NOTE, extent='cecum', quotes=[CECUM_QUOTE])])]
        for question in (c.Question(id='q', scope='proposal', fact='separate_em', family='gi.office_em',
                                    proposal_key='sel:0'),
                         c.Question(id='q', scope='proposal', fact='service_date', family='gi.colonoscopy',
                                    proposal_key='sel:0'),
                         c.Question(id='q', scope='service', fact='performed_status', family='gi.colonoscopy'),
                         c.Question(id='q', scope='service', fact='extent', family='gi.eus'),
                         c.Question(id='q', scope='encounter', fact='extent', family='gi.colonoscopy')):
            self.assertEqual(c.candidates(question, NOTE, PAGES, reading_), [], question)

    def test_a_refused_reading_and_an_unsettled_answer_offer_nothing(self):
        refused = frozen('astra', NOTE, date='2026-10-21', date_quotes=[DATE_QUOTE], refused=True)
        self.assertEqual(c.candidates(DATE, NOTE, PAGES, [refused]), [])
        unsettled = peer('fable', NOTE, '', DATE_QUOTE, settled=False)
        self.assertEqual(c.candidates(DATE, NOTE, PAGES, answers=[unsettled]), [])
        # a reading named for another participant than the entry it came from is no source either
        wrong = c.FrozenReading(name='fable', run='r', reading=frozen('astra', NOTE, date='2026-10-21',
                                                                       date_quotes=[DATE_QUOTE]).reading)
        self.assertEqual(c.candidates(DATE, NOTE, PAGES, [wrong]), [])
