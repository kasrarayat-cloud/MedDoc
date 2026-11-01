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

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect
from studio.participants.prompt import READING_VERSION
from studio.reference.store import InMemoryReferenceLookup, PrefetchedReferenceLookup
from studio.types import (EvidenceSpan, LocatedQuote, NormalizedResponse, ParticipantCode, ParticipantInput,
                          ParticipantNotCoded, ParticipantQuestion, ParticipantReading, ParticipantService,
                          ProviderCode, ReferenceSourceInfo, canonical_json, sha256_json)
from studio.validation import engine
from studio.validation.engine import UNLOCATED, assess, participant_codes

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


def corti(*codes):
    """The proposal provider's selected codes: (code, quote) pairs, each quote exact in COLON-like texts."""
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


def without_record(item):
    """A proposal with the participants' record taken out of its support: what it was before them."""
    support = {k: v for k, v in item.support.items() if k not in ('proposed_by', 'participants')}
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

    def test_a_code_no_proposal_carries_becomes_a_proposal_of_its_own(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE))))
        self.assertEqual([(i['family'], i['act']) for i in alone.completeness['unresolved_items']],
                         [('gi.colonoscopy', 'biopsy')])
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45380', BIOPSY)])])
        added = proposal(result, '45380')
        self.assertEqual((added.key, added.bucket, added.status), ('sel:1', 'selected', 'ready'))
        self.assertEqual(added.support['origin'], 'participant')
        self.assertEqual(added.support['proposed_by'], ['astra'])
        self.assertEqual([e.text for e in added.evidence], [BIOPSY])
        self.assertTrue(added.rationale.startswith('Selected by Astra (independent participant).'), added.rationale)
        # it is a proposal like any other: the reconciliation counts it, so the biopsy is no longer unresolved
        self.assertEqual(result.completeness['unresolved_items'], [])
        self.assertEqual(result.completeness['state'], 'complete_pending_review')
        self.assertEqual(proposal(result, '45385').support['proposed_by'], ['corti'])
        self.assertEqual(proposal(result, '45385').support['participants']['astra']['position'], 'not_proposed')

    def test_a_provider_code_with_no_exact_passage_carries_nothing(self):
        """Decidable as _second_review reads it: a provider selection excluded for scope or evidence (never
        reinstatable) does not hide a participant's code; that code is judged as a proposal of its own beside it."""
        off = EvidenceSpan(0, 0, len(BIOPSY), BIOPSY, True)  # not the text at those offsets
        alone = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', off)))
        self.assertEqual([(p.key, p.bucket, p.reinstatable) for p in alone.proposals if p.code == '45380'],
                         [('exc:0', 'excluded', False)])
        result = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', off)),
                     [read('astra', [code(COLON, '45380', BIOPSY)])])
        self.assertEqual([(p.key, p.bucket, p.status, p.support['proposed_by']) for p in result.proposals
                          if p.code == '45380'],
                         [('sel:1', 'selected', 'ready', ['astra']), ('exc:0', 'excluded', 'excluded', ['corti'])])
        self.assertEqual(without_record(proposal(result, '45380', 'excluded')), proposal(alone, '45380'))

    def test_a_participant_code_is_judged_by_the_providers_own_path(self):
        """I2: the same code and the same passage give the same proposal whoever proposed it - bucket, status, checks,
        evidence, clarifications and fingerprint."""
        for quote, text in ((BIOPSY, COLON), (PLAN, COLON_PLAN), (CECUM, COLON)):
            by_provider = proposal(run(text, corti(('45385', span(text, SNARE)), ('45380', span(text, quote)))),
                                   '45380')
            by_participant = proposal(run(text, corti(('45385', span(text, SNARE))),
                                          [read('fable', [code(text, '45380', quote)])]), '45380')
            self.assertEqual(decision(by_participant), decision(by_provider), quote)
            self.assertEqual(by_participant.provider_display, '')  # a participant's own words are never shown

    def test_a_held_or_excluded_reading_is_never_overridden_by_a_participant(self):
        """I2: a participant's code is ready only where the readers make it so. "Repeat colonoscopy" quoted from a plan
        section, for a family the document does not show done, is never ready."""
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nOffice visit (fictional)\n'
                'Date of service: 2026-10-14\nPlace of service: Office\nAssessment: Iron deficiency anemia.\n'
                'Plan: Colonoscopy with biopsies next month.\n')
        result = run(text, (), [read('astra', [code(text, '45380', 'Colonoscopy with biopsies next month.')]),
                                read('fable', [code(text, '45380', 'Colonoscopy with biopsies next month.')])])
        item = proposal(result, '45380')
        self.assertNotEqual(item.status, 'ready')
        self.assertEqual(item.bucket, 'excluded')
        self.assertTrue(item.reinstatable)  # a documentation judgement: a reviewer may reinstate it, as the provider's

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
        self.assertEqual(item.support['proposed_by'], ['astra', 'fable'])  # who listed it; it is no proposal
        positions = item.support['participants']
        self.assertEqual(positions['astra']['position'], 'proposed')
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
        one = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45380', BIOPSY)])])
        two = run(COLON, corti(('45385', span(COLON, SNARE))), [read('astra', [code(COLON, '45380', BIOPSY)]),
                                                                 read('fable', [code(COLON, '45380', BIOPSY, units=2,
                                                                                     confidence='low')])])
        alone, agreed = proposal(one, '45380'), proposal(two, '45380')
        self.assertEqual(decision(agreed), decision(alone))
        self.assertEqual((alone.support['proposed_by'], agreed.support['proposed_by']), (['astra'], ['astra', 'fable']))
        self.assertEqual(agreed.rationale.split('. ', 1)[1], alone.rationale.split('. ', 1)[1])
        self.assertEqual(agreed.units, 1)  # one selection: a stated unit count is recorded, never used
        self.assertIn('stated units 2', agreed.support['participants']['fable']['detail'])
        self.assertEqual({k: v for k, v in agreed.support.items() if k not in ('proposed_by', 'participants')},
                         {k: v for k, v in alone.support.items() if k not in ('proposed_by', 'participants')})

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
        result = run(COLON, corti(('45385', span(COLON, SNARE))), [
            read('astra', [code(COLON, '45380', BIOPSY)]),
            read('fable', advised=[not_coded(COLON, '45380', 'A separate 12 mm flat lesion')])])
        item = proposal(result, '45380')
        self.assertEqual((item.status, check(item, 'participants.disagree').status), ('ready', 'warn'))


class MissingServiceTests(SimpleTestCase):
    def test_a_performed_service_only_a_participant_reads_makes_coding_incomplete(self):
        alone = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', span(COLON, BIOPSY))))
        self.assertEqual(alone.completeness['state'], 'complete_pending_review')
        result = run(COLON, corti(('45385', span(COLON, SNARE)), ('45380', span(COLON, BIOPSY))), [
            read('astra', services=[service(COLON, 'eus', CECUM)])])
        complete = result.completeness
        self.assertEqual(complete['state'], 'incomplete')
        reason = ('Astra reads a performed endoscopic ultrasound that the documented-service reading does not read as '
                  f'performed (“{CECUM}”)')
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
                         [service(COLON, 'not_gi', CECUM)],  # outside the GI scope this release codes
                         [service(COLON, 'eus', 'an echoendoscope was passed')],  # not found verbatim
                         [service(COLON, 'eus', CECUM, status='planned')],
                         [service(COLON, 'egd', CECUM, status='attempted_incomplete')]):
            result = run(COLON, codes, [read('fable', services=services)])
            self.assertEqual(result.completeness['state'], 'complete_pending_review', services)
            self.assertIsNone(encounter_check(result, 'participants.services'), services)
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
        self.assertIn('Astra (OpenAI, gpt-6-astra) read the document. It proposed 2 codes (45385, 45380), 1 quoting '
                      'the document verbatim.', summary.detail)
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
        """I10: with no usable answer from the proposal provider the participants' codes are still judged, and the
        provider's own check never says there are no proposals beside them."""
        result = run(COLON, (), [read('astra', [code(COLON, '45385', SNARE), code(COLON, '45380', BIOPSY)])],
                     provider_status='failed')
        self.assertEqual([(p.key, p.code, p.status) for p in result.proposals],
                         [('sel:0', '45385', 'ready'), ('sel:1', '45380', 'ready')])
        status = encounter_check(result, 'provider.status')
        self.assertEqual(status.status, 'fail')
        self.assertNotIn('there are no CPT proposals', status.detail)
        self.assertIn('so it proposed no codes. The proposals listed come only from the independent participants '
                      '(Astra)', status.detail)
        self.assertEqual(encounter_check(result, 'services.unresolved').status, 'pass')
        self.assertIsNotNone(encounter_check(result, 'services.unproposed'))
        self.assertIn('the provider response was not available', result.completeness['reasons'])
        # with nothing a participant proposed, the provider's own words stand
        nothing = run(COLON, (), [read('astra')], provider_status='failed')
        self.assertIn('there are no CPT proposals', encounter_check(nothing, 'provider.status').detail)

    def test_reference_lookups_go_through_the_one_prefetched_lookup(self):
        """The assess child has no database: a participant's code is looked up in the stage's prefetched lookup, so the
        stage must prefetch participant_codes() beside the provider's codes."""
        participants = [read('astra', [code(COLON, '45380', BIOPSY), code(COLON, '45378', 'not in the text')])]
        self.assertEqual(participant_codes(participants), ('45380',))
        narrow = PrefetchedReferenceLookup([PFS_INFO, MUE_INFO], FACTS, ['45385'])
        with self.assertRaises(LookupError):
            run(COLON, corti(('45385', span(COLON, SNARE))), participants, reference=narrow)
        union = PrefetchedReferenceLookup([PFS_INFO, MUE_INFO], FACTS, ['45385', *participant_codes(participants)])
        item = proposal(run(COLON, corti(('45385', span(COLON, SNARE))), participants, reference=union), '45380')
        self.assertEqual(check(item, 'pfs.presence').status, 'pass')
        self.assertEqual(check(item, 'mue.units').status, 'pass')

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
        self.assertEqual([(p.key, p.code) for p in first.proposals],
                         [('sel:0', '45385'), ('sel:1', '45380'), ('sel:2', '45378'), ('altp:0', 'G0105')])
        self.assertEqual(len({p.key for p in first.proposals}), len(first.proposals))


class InputTests(SimpleTestCase):
    def test_inputs_that_break_the_contract_are_refused(self):
        astra = reading('astra')
        for given in ([ParticipantInput('corti', 'failed')],
                      [ParticipantInput('astra', 'failed'), ParticipantInput('astra', 'failed')],
                      [ParticipantInput('astra', 'read')],
                      [ParticipantInput('astra', 'failed', astra)],
                      [ParticipantInput('astra', 'sideways')],
                      [ParticipantInput('fable', 'read', astra)],
                      [ParticipantInput('astra', 'read', replace(astra, refused=True))]):
            with self.assertRaises(ValueError, msg=str(given)):
                run(COLON, corti(('45385', span(COLON, SNARE))), given)
