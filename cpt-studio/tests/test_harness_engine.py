"""HARNESS.md 5: the validation engine's merge of the independent participants (Astra and Fable).

Each test builds a synthetic document, the proposal provider's answer and the participants' readings - every quote
located as the reading normaliser locates it, at each exact occurrence - and runs the real routing, the real
documented-service inventory and the engine. The expected outcome is written here, outside the coding input. The
invariants: I1 (none configured: the result is unchanged; tests/test_harness_engine_parity.py pins it against the
round-4 engine), I2 (a participant's code is judged only by the proposal provider's own path, with exact evidence), I3
(agreement never promotes). Synthetic data only; nothing is sent.
"""
from dataclasses import replace
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect
from studio.participants.prompt import PEER_VERSION, READING_VERSION
from studio.reference.store import InMemoryReferenceLookup, PrefetchedReferenceLookup
from studio.types import (CodePosition, EvidenceSpan, LocatedQuote, NormalizedResponse, ParticipantCode,
                          ParticipantInput, ParticipantNotCoded, ParticipantQuestion, ParticipantReading,
                          ParticipantService, PeerReview, ProviderCode, QuestionAnswer, ReferenceSourceInfo,
                          canonical_json, sha256_json)
from studio.validation import engine
from studio.validation.engine import PARTICIPANT_NOT_ADDED, UNLOCATED, assess, participant_codes

DAY = date(2026, 10, 14)
MODELS = {'astra': 'gpt-6-astra', 'fable': 'claude-fable-5-1'}
# Wording a participant writes in its own words: never part of an assessment (only its codes, its enumerated reasons and
# the document's own passages are).
OWN_WORDS = 'PARTICIPANT-OWN-WORDING'

COLON = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Colonoscopy report (fictional)
Date of service: 2026-10-14
Place of service: Ambulatory surgery center
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.
A separate 12 mm flat lesion in the ascending colon was biopsied with cold forceps.
"""
SNARE = 'was removed with a hot snare'
POLYP = 'A 9 mm pedunculated polyp in the sigmoid colon'
BIOPSY = 'was biopsied with cold forceps'
CECUM = 'The colonoscope was advanced to the cecum'
PLAN = 'Plan: Surveillance colonoscopy in three years.'
COLON_PLAN = COLON + PLAN + '\n'
# A later sentence leaves further biopsies of the same lesion in doubt (refutation round 1, EV-5).
HEDGE = 'further biopsies were taken from the ascending colon lesion'
COLON_HEDGE = COLON + 'It is unclear whether ' + HEDGE + '.\n'
# The GI round 2 regression office note h2-08 (a committed synthetic fixture): its closing charge block asks the date.
H208 = (Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'regression' / 'h2-08.txt').read_text(encoding='utf-8')
CHARGED = 'a 6 mm polyp in the sigmoid colon was removed with a cold snare'


def info(key, kind, release):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=f'{release} synthetic', release=release,
                               url='https://www.cms.gov/synthetic', sha256='0' * 64, effective_start='2026-10-01',
                               effective_end='2026-12-31', license_note='licence', scope_note='scope')


PFS_INFO = info('cms-pfs-rvu26d', 'cms-pfs', 'RVU26D')
MUE_INFO = info('cms-mue-practitioner-2026q4', 'cms-mue-practitioner', '2026-Q4')
PFS_ROWS = {(code, ''): {'status': 'A', 'global_days': '000', 'mult_proc': '3' if code != '45378' else '2',
                         'endo_base': None if code == '45378' else '45378', 'pctc': '0'}
            for code in ('45378', '45380', '45385')}
MUE_ROWS = {(code, ''): {'value': 1, 'mai': {'indicator': '2', 'label': 'Date of Service Edit: Policy'},
                         'rationale': 'Anatomic Consideration'} for code in ('45378', '45380', '45385')}
FACTS = {PFS_INFO.key: PFS_ROWS, MUE_INFO.key: MUE_ROWS}
REFERENCE = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], FACTS)


def span(text, phrase, nth=0):
    start = -1
    for _ in range(nth + 1):
        start = text.index(phrase, start + 1)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def located(text, quote):
    """A quote as the reading normaliser leaves it: every exact occurrence (at most 8), or unverified."""
    spans, at = [], text.find(quote)
    while at >= 0 and len(spans) < 8:
        spans.append(EvidenceSpan(0, at, at + len(quote), quote, True))
        at = text.find(quote, at + 1)
    return LocatedQuote(quote, tuple(spans), '' if spans else 'not found')


def code(text, value, *quotes, units=1, modifiers=(), confidence='high'):
    return ParticipantCode(value, tuple(modifiers), units, ('S1',), OWN_WORDS,
                           tuple(located(text, q) for q in quotes), confidence)


def not_coded(text, value, *quotes, reason='not_performed_at_this_encounter'):
    return ParticipantNotCoded(('S1',), value, reason, tuple(located(text, q) for q in quotes))


def service(text, family, *quotes, status='performed'):
    return ParticipantService('S1', family, status, OWN_WORDS, '', '', '',
                              evidence=tuple(located(text, q) for q in quotes))


def reading(provider, codes=(), *, advised=(), services=(), questions=(), unverified=0):
    return ParticipantReading(provider=provider, adapter_version=f'{provider}-test@1', reading_version=READING_VERSION,
                              requested_model=MODELS[provider], returned_model=MODELS[provider],
                              codes=tuple(codes), not_coded=tuple(advised), services=tuple(services),
                              questions=tuple(questions), unverified_quotes=unverified)


def read(provider, codes=(), **kwargs):
    return ParticipantInput(provider, 'read', reading(provider, codes, **kwargs))


def peer(provider, *, positions=(), additional=(), answers=(), unverified=0):
    """A participant's phase-2 output (HARNESS.md 11.1), made after its first reading was frozen."""
    return PeerReview(provider=provider, adapter_version=f'{provider}-peer-test@1', review_version=PEER_VERSION,
                      requested_model=MODELS[provider], returned_model=MODELS[provider],
                      frozen_inputs=(('own', '0' * 64),), answers=tuple(answers), positions=tuple(positions),
                      additional_codes=tuple(additional), unverified_quotes=unverified)


def stance(text, value, position, *quotes):
    return CodePosition(value, position, OWN_WORDS, tuple(located(text, q) for q in quotes))


def reviewed(provider, codes=(), review=None, **kwargs):
    """A participant read in both phases: its frozen first reading and its peer review."""
    return ParticipantInput(provider, 'read', reading(provider, codes, **kwargs), peer_state='read',
                            peer=review if review is not None else peer(provider))


def corti(*codes):
    """The proposal provider's selected codes: (code, evidence span) pairs, each span exact in its text."""
    return [ProviderCode('selected', 'cpt', value, 'UNVERIFIED PROVIDER WORDING', (quote,)) for value, quote in codes]


def run(text, codes=(), participants=(), *, provider_status='succeeded', reference=REFERENCE, **kwargs):
    facts = gi_context.extract_context(text)
    response = NormalizedResponse('corti', 'test@1', tuple(codes)) if provider_status == 'succeeded' else None
    return assess(text=text, pages=(), context=facts, routing=detect.route(text, DAY), normalized=response,
                  reference=reference, service_date=DAY, provider_status=provider_status,
                  participants=tuple(participants), **kwargs)


def proposal(result, value, bucket=None):
    found = [p for p in result.proposals if p.code == value and (bucket is None or p.bucket == bucket)]
    assert len(found) == 1, f'{value}: {[(p.key, p.code, p.bucket) for p in result.proposals]}'
    return found[0]


def check(item, check_id):
    found = [c for c in item.checks if c.id == check_id]
    return found[0] if found else None


def encounter_check(result, check_id):
    return next((c for c in result.encounter_checks if c.id == check_id), None)


def decision(item):
    """What a decision on a proposal rests on: everything but who proposed it (support's record, the rationale and the
    proposer's own untrusted wording, provider_display, which a participant never has)."""
    return (item.key, item.bucket, item.code, item.code_kind, item.family, item.profile_version, item.status,
            item.exclusion_reason, item.reinstatable, item.evidence, item.checks, item.modifier_considerations,
            item.units, item.fingerprint, item.clarifications)


# What a configured participant adds to a proposal's support, outside its decision: the participants' record, and the
# identity a confirmation of its question is bound to (HARNESS.md 12.5), recorded only while one is configured.
RECORD = ('proposed_by', 'participants', 'phases', 'identity')


def without_record(item):
    """A proposal with what the participants add taken out of its support: what it was before them."""
    support = {k: v for k, v in item.support.items() if k not in RECORD}
    return replace(item, support=support)


class ParityTests(SimpleTestCase):
    """I1 inside one tree. Against the round-4 engine it is pinned by tests/test_harness_engine_parity.py and proved by
    the H1 replay and the H4 battery (ops/gi4)."""

    def test_no_participant_is_the_engine_as_before(self):
        for text, codes in ((COLON, corti(('45385', span(COLON, SNARE)))),
                            (COLON_PLAN, corti(('45385', span(COLON_PLAN, SNARE)),
                                               ('45380', span(COLON_PLAN, BIOPSY))))):
            facts = gi_context.extract_context(text)
            kwargs = dict(text=text, pages=(), context=facts, routing=detect.route(text, DAY), reference=REFERENCE,
                          normalized=NormalizedResponse('corti', 'test@1', tuple(codes)), service_date=DAY,
                          provider_status='succeeded')
            before, after = assess(**kwargs), assess(**kwargs, participants=())
            self.assertEqual(before, after)
            self.assertEqual(sha256_json(before), sha256_json(after))
            self.assertFalse(any(c.id.startswith('participants.') for c in after.encounter_checks))
            self.assertFalse(any('proposed_by' in p.support or 'participants' in p.support for p in after.proposals))
            self.assertNotIn('participant_services', after.completeness)

    def test_participants_that_read_nothing_add_only_their_record(self):
        """A configured participant that did not read the document changes nothing but the record of its state: the
        summary check, and each proposal's proposed_by and positions."""
        for status in ('succeeded', 'failed', 'unknown', 'not_run'):
            codes = corti(('45385', span(COLON, SNARE))) if status == 'succeeded' else ()
            before = run(COLON, codes, provider_status=status)
            after = run(COLON, codes, [ParticipantInput('astra', 'failed', reason='HTTP 529'),
                                       ParticipantInput('fable', 'blocked')], provider_status=status)
            self.assertEqual(tuple(without_record(p) for p in after.proposals), before.proposals, status)
            self.assertEqual([c for c in after.encounter_checks if c.id != 'participants.summary'],
                             list(before.encounter_checks), status)
            self.assertEqual((after.clarifications, after.completeness, after.services, after.summary,
                              after.unsupported, after.reference_sources),
                             (before.clarifications, before.completeness, before.services, before.summary,
                              before.unsupported, before.reference_sources), status)
            for item in after.proposals:
                self.assertEqual(item.support['proposed_by'], ['corti'])
                self.assertEqual({k: v['position'] for k, v in item.support['participants'].items()},
                                 {'astra': 'not_run', 'fable': 'not_run'})


class MergeTests(SimpleTestCase):
    def test_a_code_the_provider_selected_stays_its_proposal_with_the_participant_recorded(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE))))
        both = run(COLON, corti(('45385', span(COLON, SNARE))),
                   [read('astra', [code(COLON, '45385', POLYP)])])  # another quote: never merged into it
        mine, before = proposal(both, '45385'), proposal(alone, '45385')
        self.assertEqual(without_record(mine), before)  # nothing else about it changes: evidence, checks, fingerprint
        self.assertEqual(mine.support['proposed_by'], ['corti', 'astra'])
        astra = mine.support['participants']['astra']
        self.assertEqual(astra['position'], 'proposed')
        self.assertEqual(astra['quote'], POLYP)
        self.assertEqual(len([p for p in both.proposals if p.code == '45385']), 1)

    def test_a_code_no_proposal_carries_is_admitted_through_the_providers_own_path(self):
        """HARNESS.md P-ADMIT (owner directive 2026-11-05). Moved by refutation round 6 (R6-MEANING, the session's D14)
        to an alternative that left the biopsy unresolved; the owner's controlled replacement restores what it was
        before D14 wherever the readers support it: the biopsy is documented as done and the participant's own passage
        shows it, so its 45380 is read by the provider's path and is a proposal of its own (sel:1, ready) that the
        reconciliation counts, and only a member's decision approves it."""
        alone = run(COLON, corti(('45385', span(COLON, SNARE))))
        self.assertEqual([(i['family'], i['act']) for i in alone.completeness['unresolved_items']],
                         [('gi.colonoscopy', 'biopsy')])
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45380', BIOPSY)])])
        added = proposal(result, '45380')
        self.assertEqual((added.key, added.bucket, added.status, added.reinstatable), ('sel:1', 'selected', 'ready', False))
        self.assertEqual(added.support['origin'], 'participant')
        self.assertEqual(added.support['proposed_by'], ['astra'])
        self.assertEqual(added.support['phases'], {'astra': 'independent'})
        self.assertEqual([e.text for e in added.evidence], [BIOPSY])
        # HARNESS.md 11.4: its origin, never "Selected by"
        self.assertTrue(added.rationale.startswith('Proposed by Astra (independent participant); Corti did not '
                                                   'propose this code. 1 exact evidence passage.'), added.rationale)
        self.assertNotIn('Selected by', added.rationale)
        self.assertEqual(added.exclusion_reason, '')
        # a proposal like any other: the reconciliation counts it, so the biopsy is no longer unresolved
        self.assertEqual(result.completeness['unresolved_items'], [])
        self.assertEqual(result.completeness['state'], 'complete_pending_review')
        self.assertEqual(proposal(result, '45385').support['proposed_by'], ['corti'])

    def test_a_provider_code_with_no_exact_passage_carries_nothing(self):
        """Decidable as _second_review reads it: a provider selection excluded for scope or evidence (never
        reinstatable) does not hide a participant's code. HARNESS.md P-ADMIT (2026-11-05): that code is judged as a
        proposal of its own beside it, as it was before D14 (which listed it): sel:1, selected and ready."""
        off = EvidenceSpan(0, 0, len(BIOPSY), BIOPSY, True)  # not the text at those offsets
        alone = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', off)))
        self.assertEqual([(p.key, p.bucket, p.reinstatable) for p in alone.proposals if p.code == '45380'],
                         [('exc:0', 'excluded', False)])
        result = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', off)),
                     [read('astra', [code(COLON, '45380', BIOPSY)])])
        self.assertEqual([(p.key, p.bucket, p.status, p.support['proposed_by']) for p in result.proposals
                          if p.code == '45380'],
                         [('sel:1', 'selected', 'ready', ['astra']), ('exc:0', 'excluded', 'excluded', ['corti'])])
        self.assertTrue(proposal(result, '45380', 'selected').rationale.startswith(
            'Proposed by Astra (independent participant); Corti also selected this code, with no exact passage; it is '
            'listed apart, excluded.'))
        self.assertEqual(without_record(proposal(result, '45380', 'excluded')), proposal(alone, '45380'))

    def test_a_provider_candidate_is_no_proposal(self):
        """A code the provider only listed (a candidate, never selected) carries nothing: a participant's code of the
        same number is listed as its own alternative (it was judged as a proposal of its own until refutation round 6's
        D14, R6-MEANING), and the provider's listing stays an alternative."""
        candidate = ProviderCode('candidate', 'cpt', '45378', 'UNVERIFIED PROVIDER WORDING', (span(COLON, CECUM),))
        result = run(COLON, [*corti(('45385', span(COLON, SNARE))), candidate],
                     [read('astra', [code(COLON, '45378', CECUM)])])
        # moved by refutation round 6 (R6-MEANING, the session's D14): the participant's code is its alternative beside
        # the provider's, never a proposal (it was sel:1, selected)
        self.assertEqual([(p.key, p.bucket, p.support['proposed_by']) for p in result.proposals if p.code == '45378'],
                         [('alt:0', 'alternative', []), ('altp:0', 'alternative', ['astra'])])
        self.assertEqual(next(p for p in result.proposals if p.key == 'alt:0').support['participants']['astra']
                         ['position'], 'proposed')

    def test_stated_values_outside_the_schema_are_counted_never_shown(self):
        odd = replace(code(COLON, '45380', BIOPSY, modifiers=('59', 'XS', f'{OWN_WORDS} modifier')),
                      units=f'{OWN_WORDS} units', confidence=f'{OWN_WORDS} confidence')
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [odd])])
        detail = proposal(result, '45380').support['participants']['astra']['detail']
        self.assertIn('stated units none; modifiers 59, XS; confidence none (3 other values not shown)', detail)
        self.assertNotIn(OWN_WORDS, canonical_json(result).decode('utf-8'))

    def test_a_participant_code_is_judged_by_the_providers_own_path_and_admitted_only_where_its_passage_shows_the_act(self):
        """I2 (HARNESS.md P-ADMIT, 2026-11-05): a participant's code is judged by the proposal provider's own path, the
        same passage giving the same proposal whoever proposed it where it is admitted. Admission adds one condition
        the provider's own selection does not meet: the participant's own passage must show the act it accounts for.
        So the plan sentence and the cecal-intubation sentence quoted for 45380 are not admitted (the provider's own
        selection of them is held, or ready on the documented biopsy with its support warned), and Corti's proposals
        are then exactly what the engine makes with no participant. (D14 had listed all three; before D14 all three
        were proposals.)"""
        for quote, text in ((BIOPSY, COLON), (PLAN, COLON_PLAN), (CECUM, COLON)):
            alone = run(text, corti(('45385', span(text, SNARE))))
            by_provider = proposal(run(text, corti(('45385', span(text, SNARE)), ('45380', span(text, quote)))),
                                   '45380')
            result = run(text, corti(('45385', span(text, SNARE))), [read('fable', [code(text, '45380', quote)])])
            by_participant = proposal(result, '45380')
            self.assertEqual(by_participant.provider_display, '')  # a participant's own words are never shown
            if quote == BIOPSY:
                self.assertEqual(decision(by_participant), decision(by_provider), quote)
                self.assertEqual(by_participant.support['origin'], 'participant')
            else:
                self.assertEqual((by_participant.bucket, by_participant.status), ('alternative', 'informational'), quote)
                self.assertIn(engine.PARTICIPANT_NOT_SHOWN, by_participant.exclusion_reason)
                self.assertEqual([without_record(p) for p in result.proposals if p.code != '45380'],
                                 list(alone.proposals))

    def test_a_held_or_excluded_reading_is_never_overridden_by_a_participant(self):
        """I2: a participant's code is ready only where the readers make it so. "Repeat colonoscopy" quoted from a plan
        section, for a family the document does not show done, is never ready. Moved by D14 to an alternative with no
        reading made; under HARNESS.md P-ADMIT (2026-11-05) it is read and admitted by none of its rules - no
        colonoscopy is documented as done - so it stays an alternative a member can do nothing with."""
        from tests.test_harness2_r6_meaning import not_added_reason
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nOffice visit (fictional)\n'
                'Date of service: 2026-10-14\nPlace of service: Office\nAssessment: Iron deficiency anemia.\n'
                'Plan: Colonoscopy with biopsies next month.\n')
        result = run(text, (), [read('astra', [code(text, '45380', 'Colonoscopy with biopsies next month.')]),
                                read('fable', [code(text, '45380', 'Colonoscopy with biopsies next month.')])])
        item = proposal(result, '45380')
        self.assertNotEqual(item.status, 'ready')
        self.assertEqual((item.bucket, item.status, item.reinstatable), ('alternative', 'informational', False))
        self.assertTrue(not_added_reason(item.exclusion_reason), item.exclusion_reason)

    def test_unverified_quotes_never_make_a_proposal(self):
        """I2 and I7: a code whose quotes were all not found verbatim, or whose spans are not exact slices of the
        revision text, is listed with why and never proposed."""
        forged = LocatedQuote(BIOPSY, (EvidenceSpan(0, 3, 3 + len(BIOPSY), BIOPSY, True),))  # not the text there
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', [code(COLON, '45380', 'a biopsy was taken from the cecum')], unverified=1),
            read('fable', [ParticipantCode('45380', evidence=(forged,))])])
        self.assertEqual([p.key for p in result.proposals if p.code == '45380'], ['altp:0'])
        item = proposal(result, '45380')
        self.assertEqual((item.bucket, item.status, item.evidence), ('alternative', 'informational', ()))
        self.assertIn(UNLOCATED, item.exclusion_reason)
        # moved by refutation round 5 (R5-ACCOUNT, the session's D12): an alternative names as its proposers only the
        # participants that located the code - none here - and the ones that only listed it apart (support['listed_by']);
        # both were its proposed_by, so "Proposed by Astra and Fable" was said of readings that proposed nothing
        self.assertEqual((item.support['proposed_by'], item.support['listed_by']), ([], ['astra', 'fable']))
        self.assertNotIn('phases', item.support)
        positions = item.support['participants']
        # no proposal, so no 'proposed' position either (refutation round 4, truth-2; this pin moved from 'proposed')
        self.assertEqual(positions['astra']['position'], 'not_proposed')
        self.assertIn('not counted as a proposer', positions['astra']['detail'])
        self.assertEqual(participant_codes([read('astra', [code(COLON, '45380', 'not in the text')])]), ())

    def test_out_of_scope_and_unquoted_codes_are_alternatives_saying_why(self):
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', [code(COLON, 'G0105', CECUM), code(COLON, '45378', 'not in the document')]),
            read('fable', [code(COLON, '0001U', CECUM), code(COLON, 'G0105', CECUM)])])
        alternatives = [(p.key, p.code) for p in result.proposals if p.bucket == 'alternative']
        self.assertEqual(alternatives, [('altp:0', 'G0105'), ('altp:1', '45378'), ('altp:2', '0001U')])
        hcpcs = proposal(result, 'G0105')
        self.assertIn('HCPCS Level II code', hcpcs.exclusion_reason)
        self.assertEqual(hcpcs.support['proposed_by'], ['astra', 'fable'])
        self.assertEqual([e.text for e in hcpcs.evidence], [CECUM])
        self.assertEqual(check(hcpcs, 'scope.cpt').status, 'fail')
        self.assertIn(UNLOCATED, proposal(result, '45378').exclusion_reason)
        self.assertIn('Proprietary Laboratory Analyses', proposal(result, '0001U').exclusion_reason)
        for item in result.proposals:
            if item.bucket == 'alternative':
                self.assertEqual((item.status, item.reinstatable), ('informational', False))
                self.assertTrue(item.fingerprint)


class AgreementNeverPromotesTests(SimpleTestCase):
    """I3."""

    def test_a_second_proposer_with_the_same_quotes_changes_nothing_but_the_record(self):
        """I3 (HARNESS.md P-ADMIT, 2026-11-05: the code is admitted by one proposer or by two, as before D14, which
        listed it): a second proposer with the same quotes, its own stated units and its own confidence change nothing
        but the record and the rationale's first sentence, which names the proposers."""
        one = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45380', BIOPSY)])])
        two = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45380', BIOPSY)]),
                                                                 read('fable', [code(COLON, '45380', BIOPSY, units=2,
                                                                                     confidence='low')])])
        alone, agreed = proposal(one, '45380'), proposal(two, '45380')
        self.assertEqual(decision(agreed), decision(alone))
        self.assertEqual((alone.bucket, agreed.bucket), ('selected', 'selected'))
        self.assertEqual((alone.support['proposed_by'], agreed.support['proposed_by']), (['astra'], ['astra', 'fable']))
        self.assertEqual(agreed.rationale.split('; ', 1)[1], alone.rationale.split('; ', 1)[1])
        self.assertTrue(agreed.rationale.startswith('Proposed by Astra and Fable (independent participants); Corti did '
                                                    'not propose this code.'), agreed.rationale)
        self.assertEqual(agreed.units, 1)  # a stated unit count is recorded, never used
        self.assertIn('stated units 2', agreed.support['participants']['fable']['detail'])
        self.assertEqual({k: v for k, v in agreed.support.items() if k not in RECORD},
                         {k: v for k, v in alone.support.items() if k not in RECORD})
        # the identity a confirmation of its question would be bound to is the same whoever proposed it
        self.assertEqual(agreed.support.get('identity'), alone.support.get('identity'))

    def test_agreement_on_a_code_the_provider_selected_changes_nothing_but_the_record(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE))))
        agreed = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45385', SNARE)]),
                                                                    read('fable', [code(COLON, '45385', SNARE)])])
        self.assertEqual(without_record(proposal(agreed, '45385')), proposal(alone, '45385'))
        self.assertEqual(proposal(agreed, '45385').support['proposed_by'], ['corti', 'astra', 'fable'])

    def test_the_union_of_quotes_is_read_once_in_document_order(self):
        """Several proposers: one selection, read once from every exact quote, in the order of the document - whoever
        quoted which, and in whatever order."""
        a = run(COLON, (), [read('astra', [code(COLON, '45380', BIOPSY, CECUM)]),
                            read('fable', [code(COLON, '45380', CECUM)])], provider_status='failed')
        b = run(COLON, (), [read('astra', [code(COLON, '45380', CECUM)]),
                            read('fable', [code(COLON, '45380', CECUM, BIOPSY)])], provider_status='failed')
        self.assertEqual(decision(proposal(a, '45380')), decision(proposal(b, '45380')))
        self.assertEqual([e.text for e in proposal(a, '45380').evidence], [CECUM, BIOPSY])
        self.assertEqual(len([p for p in a.proposals if p.code == '45380']), 1)


    def test_agreement_never_releases_a_held_code(self):
        """I3 on a HELD code (refutation round 1, FG-1: every agreement test above uses a code that is ready already, so
        a regression releasing a held code once a second proposer agrees passed them all). 45378 beside 45385 is held on
        the base-inclusion question - exactly where a ready result would offer a wrong code - and stays held, its
        decision unchanged, whoever else proposes it with the same passage."""
        codes = corti(('45385', span(COLON, SNARE)), ('45378', span(COLON, CECUM)))
        alone = proposal(run(COLON, codes), '45378')
        self.assertEqual((alone.status, [q.fact for q in alone.clarifications]),
                         ('needs_clarification', ['base_included']))
        astra, fable = read('astra', [code(COLON, '45378', CECUM)]), read('fable', [code(COLON, '45378', CECUM)])
        for participants in ([astra], [astra, fable]):
            agreed = proposal(run(COLON, codes, participants), '45378')
            self.assertEqual(decision(agreed), decision(alone), [p.provider for p in participants])
            self.assertEqual(agreed.support['proposed_by'], ['corti', *[p.provider for p in participants]])
        # the proposal provider's answer failed: the participants' own proposals (HARNESS.md P-ADMIT, 2026-11-05; D14 had
        # listed them, and before D14 they were these proposals): 45378 is admitted beside the admitted 45385 and held
        # on the base-inclusion question, by one proposer and by two, its decision unchanged
        own = read('astra', [code(COLON, '45385', SNARE), code(COLON, '45378', CECUM)])
        one = proposal(run(COLON, (), [own], provider_status='failed'), '45378')
        self.assertEqual((one.bucket, one.status, [q.fact for q in one.clarifications]),
                         ('selected', 'needs_clarification', ['base_included']))
        two = proposal(run(COLON, (), [own, fable], provider_status='failed'), '45378')
        self.assertEqual(decision(two), decision(one))
        self.assertEqual(two.support['proposed_by'], ['astra', 'fable'])

    def test_another_proposer_s_own_passage_can_hold_a_code_and_agreement_never_releases_it(self):
        """I3 as the engine guarantees it (refutation round 1, EV-5; HARNESS.md 5 and 9), under HARNESS.md P-ADMIT
        (2026-11-05). Fable's passage alone shows the biopsy, so its 45380 is admitted and ready. Astra's hedging passage
        alone leaves the act in doubt; and beside Fable's, read with it, it leaves the act not established as done, so the code is
        not admitted at all (never ready, never a held code that could cover the biopsy) - whichever proposer comes
        first: agreement never releases, and a doubt another proposer raises never makes the code more ready. (D14
        listed it in all three; before D14 the pair held it.)"""
        codes = corti(('45385', span(COLON_HEDGE, SNARE)))
        fable, astra = (read('fable', [code(COLON_HEDGE, '45380', BIOPSY)]),
                        read('astra', [code(COLON_HEDGE, '45380', HEDGE)]))
        alone = proposal(run(COLON_HEDGE, codes, [fable]), '45380')
        self.assertEqual((alone.bucket, alone.status), ('selected', 'ready'))
        hedged = proposal(run(COLON_HEDGE, codes, [astra]), '45380')
        self.assertEqual((hedged.bucket, hedged.status), ('alternative', 'informational'))
        self.assertIn(engine.PARTICIPANT_NOT_ESTABLISHED, hedged.exclusion_reason)  # its own passage puts the act in doubt
        both = proposal(run(COLON_HEDGE, codes, [astra, fable]), '45380')
        self.assertEqual((both.bucket, both.status, both.clarifications), ('alternative', 'informational', ()))
        self.assertIn(engine.PARTICIPANT_NOT_ESTABLISHED, both.exclusion_reason)
        self.assertEqual([e.text for e in both.evidence], [BIOPSY, HEDGE])
        self.assertEqual(decision(proposal(run(COLON_HEDGE, codes, [fable, astra]), '45380')), decision(both))

class ContradictionTests(SimpleTestCase):
    def test_not_performed_with_a_quote_is_a_warning_never_a_status(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE))))
        disputed = run(COLON, corti(('45385', span(COLON, SNARE))),
                       [read('fable', advised=[not_coded(COLON, '45385', POLYP)])])
        before, item = proposal(alone, '45385'), proposal(disputed, '45385')
        warn = check(item, 'participants.disagree')
        self.assertEqual(warn.status, 'warn')
        self.assertIn('Fable advises not to code 45385', warn.detail)
        self.assertIn(f'“{POLYP}”', warn.detail)
        self.assertEqual((item.status, item.bucket, item.evidence), (before.status, before.bucket, before.evidence))
        self.assertEqual(item.checks[:-1], before.checks)  # added after every rule's own check, which are unchanged
        self.assertNotEqual(item.fingerprint, before.fingerprint)  # a check is part of what a decision rests on
        self.assertEqual(item.support['proposed_by'], ['corti'])
        self.assertEqual(item.support['participants']['fable']['position'], 'advised_not_to_code')
        self.assertEqual(item.support['participants']['fable']['quote'], POLYP)

    def test_no_warning_without_a_quote_or_for_another_reason(self):
        for advised in (not_coded(COLON, '45385', 'the polyp was left in place'),
                        not_coded(COLON, '45385', POLYP, reason='included_in_another_code'),
                        not_coded(COLON, '', POLYP)):
            result = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', advised=[advised])])
            item = proposal(result, '45385')
            self.assertIsNone(check(item, 'participants.disagree'), advised)
            self.assertEqual(without_record(item), proposal(run(COLON, corti(('45385', span(COLON, SNARE)))),
                                                            '45385'))
        position = proposal(run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', advised=[not_coded(COLON, '45385', POLYP, reason='included_in_another_code')])]),
            '45385').support['participants']['astra']
        self.assertEqual(position['position'], 'advised_not_to_code')
        self.assertIn('included in another code', position['detail'])

    def test_both_participants_disputing_are_quoted_each(self):
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', advised=[not_coded(COLON, '45385', SNARE)]),
            read('fable', advised=[not_coded(COLON, '45385', 'the polyp was left in place'),
                                   not_coded(COLON, '45385', POLYP)])])
        warn = check(proposal(result, '45385'), 'participants.disagree')
        self.assertIn(f'Astra and Fable advise not to code 45385: they read its service as not performed at this '
                      f'encounter (Astra: “{SNARE}”; Fable: “{POLYP}”).', warn.detail)
        self.assertEqual(proposal(result, '45385').status,
                         proposal(run(COLON, corti(('45385', span(COLON, SNARE)))), '45385').status)

    def test_a_participant_proposal_can_be_disputed_by_the_other(self):
        """HARNESS.md P-ADMIT (2026-11-05): the code Astra proposed is admitted (the biopsy is documented and shown), and
        Fable's advice not to code it is kept as a participants.disagree warning beside it, which decides nothing: the
        status stays the readers' own (as before D14, which listed the code and so had nothing to warn about)."""
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', [code(COLON, '45380', BIOPSY)]),
            read('fable', advised=[not_coded(COLON, '45380', 'A separate 12 mm flat lesion')])])
        item = proposal(result, '45380')
        disagree = check(item, 'participants.disagree')
        self.assertEqual((item.bucket, item.status, disagree.status), ('selected', 'ready', 'warn'))
        self.assertIn('A separate 12 mm flat lesion', disagree.detail)
        fable = item.support['participants']['fable']
        self.assertEqual((fable['position'], fable['quote']), ('advised_not_to_code', 'A separate 12 mm flat lesion'))

class MissingServiceTests(SimpleTestCase):
    def test_a_performed_service_only_a_participant_reads_makes_coding_incomplete(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', span(COLON, BIOPSY))))
        self.assertEqual(alone.completeness['state'], 'complete_pending_review')
        result = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', span(COLON, BIOPSY))), [
            read('astra', services=[service(COLON, 'eus', CECUM)])])
        complete = result.completeness
        self.assertEqual(complete['state'], 'incomplete')
        # moved by refutation round 10 (wording-2): only what makes the service missing (it was "... that the
        # documented-service reading does not read as performed ..."); and by round 11 (wording-1): with what the
        # reading reads as performed in the quoted words, under another family - never the quote left looking denied
        reason = ('Astra reads a performed endoscopic ultrasound where the documented-service reading reads no performed '
                  'service of that kind, and reads in the quoted words a performed service under Colonoscopy '
                  f'(“{CECUM}”)')
        self.assertEqual(complete['reasons'], [reason])
        self.assertEqual(complete['statement'], f'Coding for this encounter is incomplete: {reason}.')
        self.assertEqual([(m['participant'], m['family'], m['quote']) for m in complete['participant_services']],
                         [('astra', 'eus', CECUM)])
        warn = encounter_check(result, 'participants.services')
        self.assertEqual(warn.status, 'warn')
        self.assertIn(f'Astra reads a performed endoscopic ultrasound (“{CECUM}”)', warn.detail)
        # nothing about the proposals changes
        self.assertEqual(tuple(without_record(p) for p in result.proposals), alone.proposals)

    def test_only_a_performed_service_quoted_verbatim_of_a_kind_the_inventory_does_not_read_counts(self):
        codes = corti(('45385', span(COLON, SNARE)), ('45380', span(COLON, BIOPSY)))
        for services in ([service(COLON, 'colonoscopy', CECUM)],  # the inventory reads a performed colonoscopy
                         [service(COLON, 'colonoscopy', CECUM, status='attempted_incomplete')],  # and this one too
                         [service(COLON, 'not_gi', CECUM)],  # outside the GI scope this release codes
                         [service(COLON, 'eus', 'an echoendoscope was passed')],  # not found verbatim
                         [service(COLON, 'eus', CECUM, status='planned')],
                         [service(COLON, 'egd', CECUM, status='not_performed')],
                         [service(COLON, 'egd', CECUM, status='unclear')]):
            result = run(COLON, codes, [read('fable', services=services)])
            self.assertEqual(result.completeness['state'], 'complete_pending_review', services)
            self.assertIsNone(encounter_check(result, 'participants.services'), services)

    def test_an_attempted_incomplete_service_counts_as_missing_too(self):
        """The harness@1 integration owner's decision (2026-11-01): a service started at this encounter and not
        completed as intended must be accounted for as one performed must, so it makes coding incomplete as well."""
        codes = corti(('45385', span(COLON, SNARE)), ('45380', span(COLON, BIOPSY)))
        result = run(COLON, codes, [read('fable', services=[service(COLON, 'egd', CECUM,
                                                                    status='attempted_incomplete')])])
        # moved by refutation rounds 10 (wording-2) and 11 (wording-1), as above
        reason = ('Fable reads an attempted, incomplete upper endoscopy where the documented-service reading reads no '
                  'performed service of that kind, and reads in the quoted words a performed service under Colonoscopy '
                  f'(“{CECUM}”)')
        self.assertEqual(result.completeness['state'], 'incomplete')
        self.assertEqual(result.completeness['reasons'], [reason])
        entry = result.completeness['participant_services'][0]
        self.assertEqual((entry['participant'], entry['family'], entry['status']), ('fable', 'egd', 'attempted_incomplete'))
        warn = encounter_check(result, 'participants.services')
        self.assertEqual(warn.status, 'warn')
        self.assertIn(f'Fable reads an attempted, incomplete upper endoscopy (“{CECUM}”)', warn.detail)
        self.assertEqual(tuple(without_record(p) for p in result.proposals), run(COLON, codes).proposals)
        result = run(COLON, codes, [read('fable', services=[service(COLON, 'other_gi', POLYP)])])
        self.assertEqual(result.completeness['participant_services'][0]['families'],
                         ['gi.enteroscopy', 'gi.capsule', 'gi.motility', 'gi.reflux', 'gi.anorectal',
                          'gi.feeding_tube', 'gi.other'])

    def test_a_quote_never_lets_the_open_question_recount_drop_the_reason(self):
        """review.coding_completeness drops every completeness reason holding "open question" (it recounts them): a
        participant's quote holding those words stays in the entry and the check, never in the reason."""
        text = COLON + 'Comment: the anoscopy left an open question about the internal hemorrhoids.\n'
        quote = 'the anoscopy left an open question about the internal hemorrhoids.'
        result = run(text, corti(('45385', span(text, SNARE)), ('45380', span(text, BIOPSY))),
                     [read('astra', services=[service(text, 'other_gi', quote)])])
        entry = result.completeness['participant_services'][0]
        self.assertEqual(entry['quote'], quote)
        self.assertNotIn('open question', entry['reason'])
        self.assertIn(entry['reason'], [r for r in result.completeness['reasons'] if 'open question' not in r])
        self.assertIn(quote, encounter_check(result, 'participants.services').detail)

    def test_a_reinstatement_never_drops_the_reason(self):
        result = run(COLON_PLAN, corti(('45385', span(COLON_PLAN, SNARE)), ('45378', span(COLON_PLAN, PLAN))),
                     [read('astra', services=[service(COLON_PLAN, 'eus', CECUM)])])
        noted = result.completeness['participant_services'][0]['reason']
        reviewed = engine.reviewed_completeness(result.services, result.completeness, [('45385', 'gi.colonoscopy')],
                                                [('45380', 'gi.colonoscopy')], [])
        self.assertEqual(reviewed['state'], 'incomplete')
        self.assertIn(noted, reviewed['reasons'])
        self.assertTrue(reviewed['statement'].endswith(f'{noted}.'), reviewed['statement'])
        self.assertEqual(reviewed['reinstated'], ['45380'])


class EncounterTests(SimpleTestCase):
    def test_the_summary_names_each_participants_state(self):
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', [code(COLON, '45385', SNARE), code(COLON, '45380', 'not in the text')], unverified=1,
                 questions=[ParticipantQuestion(OWN_WORDS, OWN_WORDS)]),
            ParticipantInput('fable', 'refused', reason='the response was cut off at the output limit.')])
        summary = encounter_check(result, 'participants.summary')
        self.assertEqual(summary.status, 'info')
        # a code listed with no quote found verbatim is not counted as proposed (refutation round 4, truth-2; this pin
        # moved from "It proposed 2 codes (45385, 45380), 1 quoting the document verbatim.")
        self.assertIn('Astra (OpenAI, gpt-6-astra) read the document. It proposed 1 code (45385), 1 quoting the '
                      'document verbatim. It listed 1 code (45380) with no quote found verbatim in the document, so it '
                      'did not propose it.', summary.detail)
        self.assertIn('1 quote it gave was not found verbatim in the document and is never evidence.', summary.detail)
        self.assertIn('1 question it asked is a note, never a clarification.', summary.detail)
        self.assertIn('Fable (Anthropic) did not read the document: it answered, and its answer was not used (the '
                      'response was cut off at the output limit).', summary.detail)
        self.assertEqual(result.encounter_checks[-1], summary)
        fable = proposal(result, '45385').support['participants']['fable']
        self.assertEqual((fable['position'], fable['quote']), ('not_run', ''))

    def test_questions_never_become_clarifications_and_own_words_never_reach_the_result(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE))))
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', [code(COLON, '45380', BIOPSY)], services=[service(COLON, 'eus', CECUM)],
                 questions=[ParticipantQuestion(f'{OWN_WORDS} question', OWN_WORDS, ('S1',), (located(COLON, CECUM),))],
                 advised=[not_coded(COLON, '45385', POLYP)])])
        self.assertEqual(result.clarifications, alone.clarifications)
        self.assertEqual(sum(len(p.clarifications) for p in result.proposals),
                         sum(len(p.clarifications) for p in alone.proposals))
        self.assertNotIn(OWN_WORDS, canonical_json(result).decode('utf-8'))

    def test_the_providers_failure_blocks_only_itself(self):
        """I10: with no usable answer from the proposal provider the participants still read and are recorded, and the
        provider's own check says what is true beside them. HARNESS.md P-ADMIT (2026-11-05) restores what D14 moved:
        their first-reading codes are judged as proposals of their own (sel:0, sel:1, ready), so the provider's check
        says "so it proposed no codes" and that the proposals listed come only from the independent participants,
        never "there are no CPT proposals" beside them; with nothing a participant proposed, those words stand."""
        result = run(COLON, (), [read('astra', [code(COLON, '45385', SNARE), code(COLON, '45380', BIOPSY)])],
                     provider_status='failed')
        self.assertEqual([(p.key, p.code, p.status, (p.support or {}).get('origin')) for p in result.proposals],
                         [('sel:0', '45385', 'ready', 'participant'), ('sel:1', '45380', 'ready', 'participant')])
        status = encounter_check(result, 'provider.status')
        self.assertEqual(status.status, 'fail')
        self.assertNotIn('there are no CPT proposals', status.detail)
        self.assertIn('so it proposed no codes. The proposals listed come only from the independent participants (Astra)',
                      status.detail)
        self.assertEqual(result.completeness['unresolved_items'], [])
        self.assertIn('the provider response was not available', result.completeness['reasons'])
        # with nothing a participant proposed, the provider's own words stand as well
        nothing = run(COLON, (), [read('astra')], provider_status='failed')
        self.assertIn('there are no CPT proposals', encounter_check(nothing, 'provider.status').detail)

    def test_a_participant_code_is_read_on_the_date_a_provider_answer_is_read(self):
        """I2 with I10: under the provider's failure, with a member's date in conflict with the document, a
        participant's code is read on the date a provider's answer is read (the closing charge block's own date, GI
        round 3), so its decision is the one the provider's own path gives. Read with no date, the report's dated
        colonoscopy line would read as not established on the date of service. HARNESS.md P-ADMIT (2026-11-05)
        restores this pin as it stood before D14 (which listed the code and read it on no date)."""
        text = H208.replace('Assessment and plan\n', f'Colonoscopy on 2026-10-05: {CHARGED}.\nAssessment and plan\n', 1)
        self.assertIn(CHARGED, text)
        facts = gi_context.merge_user_values(gi_context.extract_context(text), {'service_date': '2026-10-06'})
        self.assertEqual(facts['service_date'].origin, 'conflict')
        kwargs = dict(text=text, pages=(), context=facts, routing=detect.route(text, None), reference=REFERENCE,
                      service_date=None)
        by_provider = proposal(assess(**kwargs, normalized=NormalizedResponse('corti', 'test@1', tuple(
            corti(('45385', span(text, CHARGED))))), provider_status='succeeded'), '45385')
        by_participant = proposal(assess(**kwargs, normalized=None, provider_status='failed',
                                         participants=(read('astra', [code(text, '45385', CHARGED)]),)), '45385')
        self.assertEqual(decision(by_participant), decision(by_provider))
        self.assertEqual(check(by_participant, 'service.status').status, 'pass')

    def test_reference_lookups_go_through_the_one_prefetched_lookup(self):
        """The assess child has no database: every code it looks up is in the stage's prefetched lookup, so the stage
        prefetches participant_codes() beside the provider's codes (jobs: the participants' first-reading and
        peer-review codes). HARNESS.md P-ADMIT (2026-11-05) restores this pin as it stood before D14: an admitted
        participant code is looked up, so a lookup without it raises (a lookup the prefetch missed is an error, never a
        quiet "not found"), and with it the code's pfs.presence and mue.units checks are made."""
        participants = [read('astra', [code(COLON, '45380', BIOPSY), code(COLON, '45378', 'not in the text')])]
        self.assertEqual(participant_codes(participants), ('45380',))
        narrow = PrefetchedReferenceLookup([PFS_INFO, MUE_INFO], FACTS, ['45385'])
        with self.assertRaises(LookupError):
            run(COLON, corti(('45385', span(COLON, SNARE))), participants, reference=narrow)
        union = PrefetchedReferenceLookup([PFS_INFO, MUE_INFO], FACTS, ['45385', *participant_codes(participants)])
        item = proposal(run(COLON, corti(('45385', span(COLON, SNARE))), participants, reference=union), '45380')
        self.assertEqual(item.bucket, 'selected')
        self.assertTrue({'pfs.presence', 'mue.units'} <= {c.id for c in item.checks}, [c.id for c in item.checks])
        self.assertEqual(run(COLON, corti(('45385', span(COLON, SNARE))), participants, reference=union),
                         run(COLON, corti(('45385', span(COLON, SNARE))), participants))

    def test_a_code_the_second_review_added_is_decidable(self):
        start, end = COLON.index('Procedure: Colonoscopy'), len(COLON)
        second = NormalizedResponse('corti', 'test@1', (ProviderCode('selected', 'cpt', '45380', '',
                                                                     (span(COLON, BIOPSY),)),))
        scope = {'start': start, 'end': end, 'items': ['the ascending colon biopsy']}
        alone = run(COLON, corti(('45385', span(COLON, SNARE))), second=second, second_scope=scope)
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45380', CECUM)])],
                     second=second, second_scope=scope)
        item = proposal(result, '45380')
        self.assertEqual(item.support['origin'], 'second_review')
        self.assertEqual(item.support['proposed_by'], ['corti', 'astra'])
        self.assertEqual(without_record(item), proposal(alone, '45380'))


class DeterminismTests(SimpleTestCase):
    def test_keys_and_fingerprints_are_the_same_whatever_the_order_given(self):
        participants = [read('astra', [code(COLON, 'G0105', CECUM), code(COLON, '45380', BIOPSY)]),
                        read('fable', [code(COLON, '45378', CECUM), code(COLON, '45380', BIOPSY)],
                             advised=[not_coded(COLON, '45385', POLYP)])]
        first = run(COLON, corti(('45385', span(COLON, SNARE))), participants)
        again = run(COLON, corti(('45385', span(COLON, SNARE))), list(reversed(participants)))
        self.assertEqual(first, again)
        self.assertEqual(sha256_json(first), sha256_json(again))
        # HARNESS.md P-ADMIT (2026-11-05): 45380 is admitted (sel:1); G0105 is out of scope and 45378 accounts for
        # nothing the proposals leave open, so both stay alternatives in the order they first appear (D14 had listed
        # all three; before it 45380 and 45378 were sel:1 and sel:2)
        self.assertEqual([(p.key, p.code) for p in first.proposals],
                         [('sel:0', '45385'), ('sel:1', '45380'), ('altp:0', 'G0105'), ('altp:1', '45378')])
        self.assertEqual(len({p.key for p in first.proposals}), len(first.proposals))


class InputTests(SimpleTestCase):
    def test_an_input_that_belongs_to_no_participant_is_refused(self):
        """An input that is no ParticipantInput, or that names no harness participant, cannot be blocked alone: it is
        the caller's contract violation, and raises (participant_codes reads inputs the same way)."""
        for given in ([ParticipantInput('corti', 'failed')], [ParticipantInput('gpt', 'failed')], [None],
                      [{'provider': 'astra', 'state': 'failed'}]):
            with self.assertRaises(ValueError, msg=str(given)):
                run(COLON, corti(('45385', span(COLON, SNARE))), given)
            with self.assertRaises(ValueError, msg=str(given)):
                participant_codes(given)

    def test_a_malformed_input_degrades_to_refused_and_blocks_only_itself(self):
        """The harness@1 integration owner's decision (I10): a malformed input of a participant is read as 'refused',
        with CPT Studio's own reason, instead of raising; Corti and the other participant are assessed as before."""
        astra = reading('astra', [code(COLON, '45380', BIOPSY)])
        fable = read('fable', [code(COLON, '45378', CECUM)])
        bad_code = replace(astra, codes=({'code': '45380'},))
        bad_quote = replace(astra, codes=(ParticipantCode('45380', evidence=('not a located quote',)),))
        bad_service = replace(astra, services=(ParticipantService('S1', ['egd'], 'performed', '', '', '', ''),))
        cases = {
            'given twice': ([ParticipantInput('astra', 'failed'), ParticipantInput('astra', 'read', astra)],
                            'its input was given more than once'),
            'read with no reading': ([ParticipantInput('astra', 'read')], 'its state is read but no reading was given'),
            'a reading beside another state': ([ParticipantInput('astra', 'failed', astra)],
                                               'a reading was given with a state other than read'),
            'an unknown state': ([ParticipantInput('astra', 'sideways')], 'its state is not one CPT Studio knows'),
            "another's reading": ([ParticipantInput('astra', 'read', reading('fable'))],
                                  "its reading is another participant's"),
            'a refused reading': ([ParticipantInput('astra', 'read', replace(astra, refused=True))],
                                  'its reading was refused'),
            'not a reading': ([ParticipantInput('astra', 'read', {'codes': []})], 'its reading is malformed'),
            'a malformed code': ([ParticipantInput('astra', 'read', bad_code)], 'its reading is malformed (its codes)'),
            'a malformed quote': ([ParticipantInput('astra', 'read', bad_quote)], 'its reading is malformed (its codes)'),
            'a malformed service': ([ParticipantInput('astra', 'read', bad_service)],
                                    'its reading is malformed (its services)'),
        }
        alone = run(COLON, corti(('45385', span(COLON, SNARE))), [fable])
        for name, (given, why) in cases.items():
            result = run(COLON, corti(('45385', span(COLON, SNARE))), [*given, fable])
            summary = encounter_check(result, 'participants.summary')
            self.assertIn(f'Astra (OpenAI) did not read the document: it answered, and its answer was not used (CPT '
                          f'Studio could not use its input: {why}).', summary.detail, name)
            # Fable is read as without the broken input: its own code is a proposal of its own, as before
            self.assertEqual(without_record(proposal(result, '45378')), without_record(proposal(alone, '45378')), name)
            self.assertEqual(proposal(result, '45385').support['participants']['astra']['position'], 'not_run', name)
            self.assertNotIn('45380', [p.code for p in result.proposals], name)
            self.assertIn('45378', participant_codes([*given, fable]), name)
            self.assertNotIn('45380', participant_codes([*given, fable]), name)

    def test_a_malformed_peer_review_degrades_only_the_peer_review(self):
        """A broken phase blocks only itself: the frozen first reading is still read, and its codes still proposed."""
        astra = reading('astra', [code(COLON, '45380', BIOPSY)])
        added = peer('astra', additional=[code(COLON, '45378', CECUM)])
        for given, why in ((ParticipantInput('astra', 'read', astra, peer_state='read'),
                            'its peer review state is read but no peer review was given'),
                           (ParticipantInput('astra', 'read', astra, peer_state='failed', peer=added),
                            'a peer review was given with a peer state other than read'),
                           (ParticipantInput('astra', 'read', astra, peer_state='read',
                                             peer=replace(added, provider='fable')),
                            "its peer review is another participant's"),
                           (ParticipantInput('astra', 'read', astra, peer_state='read', peer=replace(added, refused=True)),
                            'its peer review was refused'),
                           (ParticipantInput('astra', 'read', astra, peer_state='read',
                                             peer=replace(added, positions=('disputes',))),
                            'its peer review is malformed (its positions)'),
                           (ParticipantInput('astra', 'read', astra, peer_state='sideways'),
                            'its peer review state is not one CPT Studio knows')):
            result = run(COLON, corti(('45385', span(COLON, SNARE))), [given])
            self.assertEqual(proposal(result, '45380').support['origin'], 'participant', why)
            self.assertNotIn('45378', [p.code for p in result.proposals], why)
            summary = encounter_check(result, 'participants.summary').detail
            self.assertIn('Astra (OpenAI, gpt-6-astra) read the document.', summary, why)
            self.assertIn(f'Its peer review was not read: it answered, and its answer was not used (CPT Studio could not '
                          f'use its peer review: {why}).', summary, why)
            self.assertEqual(proposal(result, '45385').support['participants']['astra']['peer']['position'], 'not_run')
            self.assertEqual(participant_codes([given]), ('45380',), why)
        # a peer review beside a first reading that was not read is never read (HARNESS.md 11.1)
        result = run(COLON, corti(('45385', span(COLON, SNARE))),
                     [ParticipantInput('astra', 'failed', reason='HTTP 529', peer_state='read', peer=added)])
        summary = encounter_check(result, 'participants.summary').detail
        self.assertIn('did not read the document: its request failed (HTTP 529). It takes no part in peer review: its '
                      'first reading was not read.', summary)
        self.assertNotIn('45378', [p.code for p in result.proposals])


class PeerReviewTests(SimpleTestCase):
    """HARNESS.md 11.1: what a participant says in peer review, after its first reading was frozen."""

    def test_a_dispute_with_a_located_quote_warns_naming_the_phase(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('fable')])
        disputed = run(COLON, corti(('45385', span(COLON, SNARE))),
                       [reviewed('fable', review=peer('fable', positions=[stance(COLON, '45385', 'disputes', POLYP)]))])
        before, item = proposal(alone, '45385'), proposal(disputed, '45385')
        warn = check(item, 'participants.disagree')
        self.assertEqual(warn.status, 'warn')
        self.assertIn(f"Fable disputes 45385 in peer review, after seeing the other reviewers' frozen conclusions "
                      f'(“{POLYP}”). Kept for the reviewer, never voted on', warn.detail)
        self.assertEqual((item.status, item.bucket, item.evidence), (before.status, before.bucket, before.evidence))
        self.assertEqual(item.checks[:-1], before.checks)
        self.assertNotEqual(item.fingerprint, before.fingerprint)  # a disagreement is part of what a decision rests on
        peer_position = item.support['participants']['fable']['peer']
        self.assertEqual((peer_position['position'], peer_position['quote']), ('disputes', POLYP))
        self.assertNotIn(OWN_WORDS, canonical_json(disputed).decode('utf-8'))

    def test_both_phases_in_one_warning_each_named(self):
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', advised=[not_coded(COLON, '45385', SNARE)]),
            reviewed('fable', review=peer('fable', positions=[stance(COLON, '45385', 'disputes', POLYP)]))])
        detail = check(proposal(result, '45385'), 'participants.disagree').detail
        self.assertIn(f'Astra advises not to code 45385 in its independent reading: it reads its service as not '
                      f'performed at this encounter (“{SNARE}”). Fable disputes 45385 in peer review', detail)

    def test_supports_cannot_tell_and_an_unquoted_dispute_change_nothing(self):
        """I3: a peer review's agreement never promotes; a position with no located quote is no evidence either."""
        alone = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('fable')])
        for position, quotes in (('supports', (SNARE,)), ('cannot_tell', (POLYP,)), ('disputes', ('not in the text',)),
                                 ('disputes', ())):
            result = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('fable', review=peer(
                'fable', positions=[stance(COLON, '45385', position, *quotes)]))])
            item, before = proposal(result, '45385'), proposal(alone, '45385')
            self.assertEqual(decision(item), decision(before), position)
            self.assertEqual(without_record(item), without_record(before), position)
            self.assertEqual((result.clarifications, result.completeness), (alone.clarifications, alone.completeness))
            self.assertEqual(item.support['participants']['fable']['peer']['position'], position)
        self.assertEqual(proposal(alone, '45385').support['participants']['fable']['peer']['position'], 'no_position')
        # and on a HELD code (FG-1): 45378 beside 45385 stays held on the base-inclusion question
        codes = corti(('45385', span(COLON, SNARE)), ('45378', span(COLON, CECUM)))
        held = proposal(run(COLON, codes, [reviewed('fable')]), '45378')
        self.assertEqual((held.status, [q.fact for q in held.clarifications]),
                         ('needs_clarification', ['base_included']))
        for position in ('supports', 'cannot_tell'):
            item = proposal(run(COLON, codes, [reviewed('fable', review=peer(
                'fable', positions=[stance(COLON, '45378', position, CECUM)]))]), '45378')
            self.assertEqual(decision(item), decision(held), position)

    def test_an_additional_code_is_read_as_a_participant_code_and_recorded_as_after_peer_review(self):
        """HARNESS.md P-ADMIT (2026-11-05): a code a first reading proposes is admitted (here, and it was so before
        D14); the same code given only in a peer review's additional codes is never admitted - it was proposed after
        its participant saw its peers' conclusions - and is recorded as proposed after peer review, never as
        independent (before D14 both were proposals with one decision; D14 listed both)."""
        first = run(COLON, corti(('45385', span(COLON, SNARE))), [read('fable', [code(COLON, '45380', BIOPSY)])])
        later = run(COLON, corti(('45385', span(COLON, SNARE))),
                    [reviewed('fable', review=peer('fable', additional=[code(COLON, '45380', BIOPSY)]))])
        independent, added = proposal(first, '45380'), proposal(later, '45380')
        self.assertEqual((independent.bucket, independent.status), ('selected', 'ready'))
        self.assertEqual(independent.support['phases'], {'fable': 'independent'})
        self.assertEqual(added.bucket, 'alternative')
        self.assertEqual((added.support['origin'], added.support['proposed_by'], added.support['phases']),
                         ('participant', ['fable'], {'fable': 'peer_review'}))
        self.assertEqual(added.exclusion_reason, f'Proposed by Fable after peer review, but not added as a proposal: '
                                                 f'{engine.PARTICIPANT_PEER_ONLY}. Alternatives cannot be approved.')
        self.assertTrue(added.rationale.startswith('Proposed by Fable after peer review; not added as a proposal: '),
                        added.rationale)
        self.assertNotIn('independent', added.rationale)  # never described as independent
        detail = added.support['participants']['fable']['detail']
        self.assertIn('Fable proposed 45380 after peer review, not in its independent reading (stated units 1', detail)
        summary = encounter_check(later, 'participants.summary').detail
        self.assertIn('Fable (Anthropic, claude-fable-5-1) read the document. It proposed no code. In peer review, after '
                      'its first reading was frozen, it took 0 positions on codes (0 supports, 0 disputes, 0 cannot '
                      'tell). It listed 1 additional code (45380), 1 quoting the document verbatim; a code first '
                      'proposed in peer review is never counted as independent.', summary)
        self.assertEqual(participant_codes([reviewed('fable', review=peer('fable', additional=[
            code(COLON, '45380', BIOPSY), code(COLON, '45378', 'not in the text')]))]), ('45380',))

    def test_a_code_proposed_in_both_phases_names_each_proposers_phase(self):
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', [code(COLON, '45380', BIOPSY)]),
            reviewed('fable', review=peer('fable', additional=[code(COLON, '45380', BIOPSY)]))])
        item = proposal(result, '45380')
        self.assertEqual(item.support['phases'], {'astra': 'independent', 'fable': 'peer_review'})
        # HARNESS.md P-ADMIT (2026-11-05): admitted on Astra's first reading; its first sentence names each proposer's
        # phase and goes on "Corti did not propose this code." (as before D14, which listed it)
        self.assertEqual((item.bucket, item.status), ('selected', 'ready'))
        self.assertTrue(item.rationale.startswith('Proposed by Astra (independent participant) and Fable after peer '
                                                  'review; Corti did not propose this code.'), item.rationale)
        # its own first reading's code, listed again in peer review, stays independent
        again = run(COLON, corti(('45385', span(COLON, SNARE))), [
            reviewed('astra', [code(COLON, '45380', BIOPSY)], peer('astra', additional=[code(COLON, '45380', BIOPSY)]))])
        self.assertEqual(proposal(again, '45380').support['phases'], {'astra': 'independent'})
        self.assertIn('in its independent reading and again in peer review',
                      proposal(again, '45380').support['participants']['astra']['detail'])

    def test_a_first_reading_quote_that_was_not_found_never_makes_a_peer_review_code_independent(self):
        """11.1 and 11.4 (refutation round 1, EV-2 = IND-3): a participant's phase is the phase of its LOCATED evidence.
        A code its first reading listed with a quote not found in the text - no proposal in phase 1 - that its peer
        review then quotes verbatim was proposed after peer review, exactly as if the first reading had not listed it."""
        unlocated = code(COLON, '45380', 'a 12 mm flat lesion was sampled with forceps')  # not in the text
        added = peer('astra', additional=[code(COLON, '45380', BIOPSY)])
        first = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [unlocated])])
        # moved by refutation round 5 (R5-ACCOUNT, the session's D12): what it did in its first reading is list the
        # code, which proposes it in no phase - it was its alternative's proposer, with the phase 'independent'
        support = proposal(first, '45380').support
        self.assertEqual((proposal(first, '45380').bucket, support.get('phases'), support['proposed_by'],
                          support['listed_by']), ('alternative', None, [], ['astra']))
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('astra', [unlocated], added)])
        control = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('astra', review=added)])
        item = proposal(result, '45380')
        self.assertEqual(decision(item), decision(proposal(control, '45380')))
        self.assertEqual(item.support['phases'], {'astra': 'peer_review'})
        # and the detail the API serves in support never calls that first listing a proposal (refutation round 3)
        detail = item.support['participants']['astra']['detail']
        self.assertIn(', listed in its independent reading with no quote found verbatim there, and proposed after peer '
                      'review', detail)
        self.assertNotIn('in its independent reading and again in peer review', detail)
        # HARNESS.md P-ADMIT (2026-11-05): proposed only after peer review, so it is never admitted (D14 listed it too)
        self.assertEqual(item.bucket, 'alternative')
        self.assertTrue(item.rationale.startswith('Proposed by Astra after peer review; not added as a proposal: '
                                                  f'{engine.PARTICIPANT_PEER_ONLY}'), item.rationale)
        self.assertEqual(item.rationale, proposal(control, '45380').rationale)
        # Corti's own code, listed by Astra with a quote not found and then quoted in peer review: the same rule
        snare = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed(
            'astra', [code(COLON, '45385', 'hot snare polypectomy of the sigmoid polyp')],
            peer('astra', additional=[code(COLON, '45385', SNARE)]))])
        self.assertEqual(proposal(snare, '45385').support['phases'], {'astra': 'peer_review'})
        # beside a participant whose first reading located it: each named in its own phase
        both = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('astra', [unlocated], added),
                                                                  read('fable', [code(COLON, '45380', BIOPSY)])])
        self.assertEqual(proposal(both, '45380').support['phases'], {'astra': 'peer_review', 'fable': 'independent'})
        # beside Fable's first reading the code is admitted on Fable's passage (HARNESS.md P-ADMIT, 2026-11-05)
        self.assertEqual(proposal(both, '45380').bucket, 'selected')
        self.assertTrue(proposal(both, '45380').rationale.startswith(
            'Proposed by Fable (independent participant) and Astra after peer review; Corti did not propose this code.'),
            proposal(both, '45380').rationale)

    def test_an_additional_code_a_decidable_proposal_carries_only_adds_to_its_record(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE))))
        result = run(COLON, corti(('45385', span(COLON, SNARE))),
                     [reviewed('fable', review=peer('fable', additional=[code(COLON, '45385', SNARE)]))])
        item = proposal(result, '45385')
        self.assertEqual(without_record(item), proposal(alone, '45385'))
        self.assertEqual((item.support['proposed_by'], item.support['phases']),
                         (['corti', 'fable'], {'fable': 'peer_review'}))

    def test_an_additional_code_that_is_no_proposal_is_an_alternative_saying_so(self):
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('fable', review=peer('fable', additional=[
            code(COLON, 'G0105', CECUM), code(COLON, '45378', 'not in the document')]))])
        self.assertEqual([(p.key, p.code) for p in result.proposals if p.bucket == 'alternative'],
                         [('altp:0', 'G0105'), ('altp:1', '45378')])
        self.assertTrue(proposal(result, 'G0105').exclusion_reason.startswith(
            'Proposed by Fable after peer review, but not added as a proposal: HCPCS Level II code'))
        # moved by refutation round 5 (R5-ACCOUNT, the session's D12): 45378's only quote is not in the document, so
        # Fable's peer review listed it and proposed it in no phase - it was its proposer, 'after peer review'
        unlocated = proposal(result, '45378')
        self.assertEqual((unlocated.support.get('phases'), unlocated.support['proposed_by'],
                          unlocated.support['listed_by']), (None, [], ['fable']))
        self.assertTrue(unlocated.exclusion_reason.startswith('Listed by Fable with no quote found verbatim in the '
                                                              'document, so not proposed, and not added as a proposal'))

    def test_peer_review_keeps_the_keys_of_every_first_reading_code(self):
        """assess #1 and assess #2: a code no first reading listed, added in peer review, comes after every first
        reading's code, so it never takes the key of one a first reading gave. That is all it guarantees: a new answer
        of the proposal provider selects other codes, so keys still move between assessments - which is why a
        confirmation is bound to its proposal's code and identity, never its key (refutation round 1, EV-1;
        tests/test_harness_engine_confirmations.py BindingTests). HARNESS.md P-ADMIT (2026-11-05): the first readings'
        codes are admitted (sel:0, sel:1, as before D14), and the peer review's code is an alternative after them."""
        first = run(COLON, (), [read('astra', [code(COLON, '45385', SNARE)]), read('fable', [code(COLON, '45378', CECUM)])],
                    provider_status='failed')
        second = run(COLON, (), [reviewed('astra', [code(COLON, '45385', SNARE)], peer('astra', additional=[
            code(COLON, '45380', BIOPSY)])), reviewed('fable', [code(COLON, '45378', CECUM)])], provider_status='failed')
        self.assertEqual([(p.key, p.code) for p in first.proposals], [('sel:0', '45385'), ('sel:1', '45378')])
        self.assertEqual([(p.key, p.code) for p in second.proposals],
                         [('sel:0', '45385'), ('sel:1', '45378'), ('altp:0', '45380')])

    def test_a_peer_review_that_did_not_run_is_said_and_blocks_only_itself(self):
        before = run(COLON, corti(('45385', span(COLON, SNARE))), [read('fable', [code(COLON, '45380', BIOPSY)])])
        after = run(COLON, corti(('45385', span(COLON, SNARE))), [ParticipantInput(
            'fable', 'read', reading('fable', [code(COLON, '45380', BIOPSY)]), reason='HTTP 529', peer_state='failed')])
        self.assertEqual(tuple(without_record(p) for p in after.proposals),
                         tuple(without_record(p) for p in before.proposals))
        self.assertIn('Its peer review was not read: its request failed (HTTP 529).',
                      encounter_check(after, 'participants.summary').detail)
        self.assertEqual(proposal(after, '45380').support['participants']['fable']['peer']['position'], 'not_run')
        self.assertNotIn('peer', proposal(before, '45380').support['participants']['fable'])  # assess #1: no stage yet

    def test_answers_are_counted_never_read_as_answers_and_own_words_never_reach_the_result(self):
        answer = QuestionAnswer('q1', True, f'{OWN_WORDS} value', (located(COLON, CECUM),))
        alone = run(COLON, corti(('45385', span(COLON, SNARE))), [reviewed('astra')])
        result = run(COLON, corti(('45385', span(COLON, SNARE))),
                     [reviewed('astra', review=peer('astra', answers=[answer], unverified=1))])
        self.assertEqual((result.clarifications, result.proposals[0].clarifications),
                         (alone.clarifications, alone.proposals[0].clarifications))
        summary = encounter_check(result, 'participants.summary').detail
        # moved by refutation round 4 (d7-5, HARNESS.md 12.10 as amended): the sentence is true whether or not
        # confirmations are offered, where it said "an answer is read only as the passage a reviewer confirms"
        self.assertIn('It answered 1 open question; an answer is recorded and decides nothing by itself. 1 quote it '
                      'gave in peer review was not found verbatim in the document and is never evidence.', summary)
        self.assertNotIn('confirm', summary)
        self.assertNotIn(OWN_WORDS, canonical_json(result).decode('utf-8'))

    def test_keys_and_fingerprints_are_the_same_whatever_the_order_given(self):
        participants = [reviewed('astra', [code(COLON, '45380', BIOPSY)], peer('astra', positions=[
                            stance(COLON, '45385', 'disputes', POLYP)], additional=[code(COLON, 'G0105', CECUM)])),
                        reviewed('fable', [code(COLON, '45378', CECUM)], peer('fable', additional=[
                            code(COLON, '45380', BIOPSY)]))]
        first = run(COLON, corti(('45385', span(COLON, SNARE))), participants)
        again = run(COLON, corti(('45385', span(COLON, SNARE))), list(reversed(participants)))
        self.assertEqual(first, again)
        self.assertEqual(sha256_json(first), sha256_json(again))
        # HARNESS.md P-ADMIT (2026-11-05): Astra's first-reading 45380 is admitted (sel:1); Fable's 45378 accounts for
        # nothing left open and G0105, given only in peer review, is out of scope: alternatives, first readings' first
        # (D14 had listed all three; before it 45380 and 45378 were sel:1 and sel:2)
        self.assertEqual([(p.key, p.code) for p in first.proposals],
                         [('sel:0', '45385'), ('sel:1', '45380'), ('altp:0', '45378'), ('altp:1', 'G0105')])
