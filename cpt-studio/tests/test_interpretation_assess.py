"""The events engine's entry (Gemini migration slice S08; design/FINAL.md 7.1, 7.10, 7.11 and 10.4; design/ADJUDICATION.md
R-4, R-5), SYNTHETIC:
- the AssessmentResult shape matches studio.types (a JSON round trip; the services stub and the inventory_problems
  sentence the rollback image reads fail-closed, checked against the legacy readers themselves, test-only);
- the sentinel in strict mode (sentinel.strict: PY_START on every denied code object and CALL-level regex and cache
  reads) shows zero denied executions over every path of the engine: proposals, exclusions, holds, participants, the
  second review, member answers, the E/M, the EUS and the context derivation - and a planted legacy call trips it;
- an AST scan of the six S08 modules: nothing of studio.gi but the reference tables, no denied validation module, and
  studio.validation.checks only by a FINAL 7.1 name (R-5); no regex compiled (a twin of a denied pattern is impossible);
- P-ADMIT: a participant's first-reading code admitted and evaluated by the per-code rule; agreement adds proposers and
  nothing else (I3); peer-only and unlocated codes stay alternatives; two codes for one event compete (P-ADMIT2); a
  participant's disagreement is a warn that never changes a status;
- the second review's merge by E* intersection with the marked items;
- member answers bound by fingerprint: the answered code excluded, cross-code effects, the overlay's answers recorded;
- fingerprint stability across an AGAIN recompute over the same inventory, and its change with the events;
- every legacy wording the engine copies pinned equal to its original. Nothing is sent."""
from __future__ import annotations

import ast
import dataclasses
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio import customer_api
from studio.gi import catalogue
from studio.gi.profiles import PROFILES
from studio.interpretation import assess, coverage, events, facts, read, sentinel, store, wording
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (AssessmentResult, CodePosition, EvidenceSpan, LocatedQuote, NormalizedResponse,
                          ParticipantCode, ParticipantInput, ParticipantNotCoded, ParticipantReading, PeerReview,
                          ProviderCode, ReferenceSourceInfo, Span, from_jsonable, to_jsonable)
from studio.validation import checks, engine, questions, rationale, reconcile, review_view
from tests.test_interpretation_events import (COLONOSCOPE, DUODENAL_REACH, EUS_LINES, FNA, LOOKUP, NO_FNA, POLYP, asked,
                                              check, colonoscopy, eus, exam, inventory, proposal, reached, removed,
                                              response, run)
from tests.test_interpretation_identity import a, act, les, sc, tg
from tests.test_interpretation_no_gi import scan, violations

APP = Path(__file__).resolve().parents[1]
MODULES = ('facts', 'events', 'coverage', 'combination', 'assess', 'wording')
EGD_LINES = {'G1': 'EGD: the gastroscope was advanced to the second portion of the duodenum.',
             'G2': 'EGD: cold forceps biopsies were taken from the gastric antrum.',
             'P1': 'Colonoscopy: ' + COLONOSCOPE, 'P2': POLYP}


def quote(text: str, phrase: str) -> LocatedQuote:
    start = text.index(phrase)
    return LocatedQuote(phrase, (EvidenceSpan(0, start, start + len(phrase), phrase, True),))


def reading_of(provider: str, codes=(), not_coded=()) -> ParticipantReading:
    return ParticipantReading(provider=provider, adapter_version=f'{provider}@test', reading_version='harness-reading@2',
                              requested_model='model', returned_model='model', codes=tuple(codes),
                              not_coded=tuple(not_coded))


def participant(provider: str, text: str, codes=(), not_coded=(), peer_codes=(), positions=()) -> ParticipantInput:
    first = reading_of(provider, [ParticipantCode(code=code, evidence=(quote(text, phrase),) if phrase else ())
                                  for code, phrase in codes], not_coded)
    if not peer_codes and not positions:
        return ParticipantInput(provider, 'read', first)
    peer = PeerReview(provider=provider, adapter_version=f'{provider}@test', review_version='peer@1',
                      requested_model='model', returned_model='model',
                      additional_codes=tuple(ParticipantCode(code=code, evidence=(quote(text, phrase),))
                                             for code, phrase in peer_codes), positions=tuple(positions))
    return ParticipantInput(provider, 'read', first, peer_state='read', peer=peer)


def two_procedures():
    """An EGD with antral biopsies and a colonoscopy with the sigmoid polyp's cold snare removal."""
    l1 = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='6 mm')
    return inventory(EGD_LINES, lesions=[l1], events=[
        exam('E0', 'G1', words='gastroscope', procedure=a('egd', 'EGD', ['G1'])),
        act('E5', 'G2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd', 'EGD', ['G2']),
            technique=a('cold_forceps', 'cold forceps', ['G2']), target=tg('', 'gastric_antrum', 'gastric antrum',
                                                                           ['G2'])),
        exam(procedure=a('colonoscopy', 'Colonoscopy', ['P1'])),
        removed(procedure=a('colonoscopy', 'polyp', ['P2']))],
        reach=[reached('E0', 'second_portion_duodenum', 'second portion of the duodenum', 'G1'), reached()])


# --- the shape and the rollback record -------------------------------------------------------------------------------

class Shape(SimpleTestCase):
    def test_the_result_is_the_types_assessment_result_and_round_trips(self):
        inv, text = colonoscopy()
        result = run(inv, text, [('45378', COLONOSCOPE), ('45385', POLYP), ('99999', POLYP, 'candidate')])
        self.assertIsInstance(result, AssessmentResult)
        self.assertEqual([f.name for f in dataclasses.fields(result)],
                         [f.name for f in dataclasses.fields(AssessmentResult)])
        self.assertEqual((result.engine_version, result.profiles_version), ('cpt-studio-events@1', 'gi-profiles@3'))
        self.assertEqual(from_jsonable(AssessmentResult, to_jsonable(result)), result)
        self.assertEqual([p.key for p in result.proposals], ['sel:0', 'sel:1', 'alt:0'])
        self.assertEqual(result.summary['selected'], 2)
        for p in result.proposals:
            self.assertEqual(to_jsonable(p.support), p.support)  # plain JSON data

    def test_the_services_stub_and_the_frozen_reconciliation(self):
        inv, text = colonoscopy()
        result = run(inv, text, [('45385', POLYP)])
        self.assertEqual(result.services, {'version': 'cpt-studio-events@1', 'services': [], 'conflicts': [],
                                           'attributions': [], 'problems': []})
        self.assertEqual(result.completeness['inventory_problems'], list(assess.INVENTORY_PROBLEMS))
        # what the rollback image does with them (FINAL 12, test-only legacy calls): its overlay reads no inventory, and
        # its read-time reconciliation returns the stored completeness, a reinstated code or not
        self.assertIsNone(review_view._inventory(result.services))
        stored = to_jsonable(result.completeness)
        self.assertIs(engine.reviewed_completeness(result.services, stored, [('45385', 'gi.colonoscopy')],
                                                   [('45386', 'gi.colonoscopy')], []), stored)

    def test_a_refused_inventory_is_never_read_as_empty(self):
        refusal = read.refuse('schema', 'the answer breaks the interpretation schema')
        ids = dict(encounter_id='6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0101', revision_id='6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0102',
                   provider_run_id='6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0103')
        fields = store.refused_row(refusal, text_sha256='0' * 64, request_sha256='1' * 64, response_sha256='2' * 64,
                                   **ids)
        stored = store.load(fields, text_sha256='0' * 64, response_sha256='2' * 64)
        with self.assertRaises(store.StoreError):
            assess.assess(inventory=stored, context={}, normalized=None, provider_status='not_run', reference=LOOKUP,
                          text='')

    def test_an_assessment_without_proposals_still_reconciles(self):
        inv, text = colonoscopy()
        result = run(inv, text, [], provider_status='failed')
        self.assertEqual(result.proposals, ())
        self.assertEqual(check_of(result, 'provider.status').status, 'fail')
        self.assertIn('the provider response was not available', result.completeness['reasons'])


def check_of(result, cid: str):
    return next(item for item in result.encounter_checks if item.id == cid)


# --- the call guard: zero denied executions, strict --------------------------------------------------------------------

class Sentinel(SimpleTestCase):
    def assessments(self):
        inv, text = colonoscopy()
        yield lambda: run(inv, text, [('45378', COLONOSCOPE), ('45385', POLYP), ('G0105', POLYP), ('45386', POLYP)])
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']))
        inv2, text2 = colonoscopy(denial, lines={'P3': 'No polyp was removed today.'})
        yield lambda: run(inv2, text2, [('45385', POLYP), ('45390', 'No polyp was removed')])
        inv3, text3 = two_procedures()
        astra = participant('astra', text3, codes=[('43239', EGD_LINES['G2']), ('45385', POLYP)],
                            not_coded=[ParticipantNotCoded(code='45378', reason='not_performed_at_this_encounter',
                                                           evidence=(quote(text3, EGD_LINES['P1']),))])
        fable = participant('fable', text3, peer_codes=[('45380', POLYP)],
                            positions=[CodePosition(code='45385', position='disputes', reason='r',
                                                    evidence=(quote(text3, POLYP),))])
        second = response(text3, [('43239', EGD_LINES['G2']), ('45380', POLYP)])
        yield lambda: run(inv3, text3, [('45385', POLYP), ('45378', EGD_LINES['P1'])], participants=(astra, fable),
                          second=second, second_scope={'items': ['upper endoscopy']})
        first = run(inv, text, [('45385', POLYP)])
        asked_ = assess._MemberAnswers((), text)._proposal_questions(first.proposals)
        answer = questions.MemberAnswerInput('45385', 'gi.colonoscopy', 'extent', 'not_documented',
                                             asked_.get(('45385', 'gi.colonoscopy', 'extent'), ''), 'answer-1')
        inv4, text4 = colonoscopy(reach=False)
        yield lambda: run(inv4, text4, [('45385', POLYP), ('45378', COLONOSCOPE)], member_answers=(answer,))
        from tests.test_interpretation_combination import MEMBER, VISIT_LINE, office
        inv5, text5 = office(exam(procedure=a('colonoscopy', 'colonoscope', ['P1'])),
                             lines={'P1': COLONOSCOPE})
        yield lambda: run(inv5, text5, [('99213', VISIT_LINE), ('45378', COLONOSCOPE)], user_values=MEMBER)
        from tests.test_interpretation_events import EUS_LINES, FNA, eus
        inv6, text6 = eus(FNA)
        yield lambda: run(inv6, text6, [('43242', EUS_LINES['P3']), ('43232', EUS_LINES['P1'])])
        yield lambda: (facts.derive(inv, {'service_date': '2026-11-09', 'setting': 'office'}),
                       facts.routing_stand_in(inv, '2026-11-09', inventory_id='x'))
        from tests.test_interpretation_cases import OwnerClasses  # the modifier review over two distinct lesions
        from tests.test_interpretation_combination import EGD_EUS, egd_eus
        yield lambda: OwnerClasses('test_v1_two_lesions_at_one_site').test_v1_two_lesions_at_one_site()
        inv7, text7 = egd_eus()
        yield lambda: run(inv7, text7, [('43235', EGD_EUS['P1']), ('43242', EGD_EUS['P2'])])
        line = 'The distal esophageal stricture was dilated with a through-the-scope balloon to 15 mm.'
        inv8, text8 = inventory({'G1': EGD_LINES['G1'], 'G2': line}, events=[
            exam('E0', 'G1', words='gastroscope', procedure=a('egd')),
            act('E2', 'G2', 'dilation', 'dilated', procedure=a('egd'), technique=a('balloon', 'balloon', ['G2']),
                target=tg('', 'distal_esophagus', 'distal esophageal', ['G2']))])
        yield lambda: run(inv8, text8, [('43249', line)], participants=(participant('astra', text8, [('43245', line)]),))
        undatable = act('E1', 'P1', 'examination', 'upper endoscopy', status_words='was performed',
                        procedure=a('egd', 'upper endoscopy', ['P1']), time=a('unknown'))
        inv9, text9 = office(undatable, lines={'P1': 'An upper endoscopy with duodenal biopsies was performed.'})
        yield lambda: run(inv9, text9, [('99213', VISIT_LINE), ('45999', VISIT_LINE)], user_values=MEMBER)
        # C-7 and C-10's statement_scope questions (a broad denial beside an omitted act; a code citing the act beside a
        # historical denial), and an examination-only EUS code held as its family's base beside the FNA code
        omitted = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                      scope=sc('all_of_kind', 'No', ['P3']), time=a('current_encounter', 'today', ['P3']))
        inv10, text10 = inventory({'P1': COLONOSCOPE, 'P2': POLYP, 'P3': 'No polyp was removed today.'},
                                  events=[exam(), omitted], reach=[reached()])
        yield lambda: run(inv10, text10, [('45385', POLYP), ('45390', (POLYP, 'No polyp was removed today.'))])
        yield lambda: run(inv6, text6, [('43242', EUS_LINES['P3']), ('43259', EUS_LINES['P1'])])
        # DECISIONS D27-D30: the defining act not documented, the examination class that does not fit, the dilation at
        # an anastomosis, the procedural adjunct
        from tests.test_interpretation_coverage import adjunct
        from tests.test_interpretation_events import ANASTOMOTIC, ERCP_LINES, dilated, ercp
        inv11, text11 = ercp()
        yield lambda: run(inv11, text11, [('43264', ERCP_LINES['P3']), ('43265', ERCP_LINES['P3'])])
        inv12, text12 = eus(FNA, reach=[DUODENAL_REACH])
        yield lambda: run(inv12, text12, [('43242', EUS_LINES['P3']), ('43238', EUS_LINES['P3'])])
        inv13, text13 = dilated(*ANASTOMOTIC)
        yield lambda: run(inv13, text13, [('43249', ANASTOMOTIC[0]), ('43245', ANASTOMOTIC[0])])
        inv14, text14, lines14 = adjunct()
        yield lambda: run(inv14, text14, [('45390', lines14['P2']), ('45388', lines14['P3'])])

    def test_strict_mode_shows_zero_denied_executions_on_every_path(self):
        for index, work in enumerate(self.assessments()):
            with self.subTest(path=index), sentinel.strict(f'S08 events engine {index}') as opened:
                work()
            self.assertEqual(opened.count(sentinel.NEW_PATH), 0)

    def test_the_instrument_is_live_a_planted_legacy_call_trips_it(self):
        with self.assertRaises(AssertionError) as caught, sentinel.strict('S08 positive control'):
            reconcile.mention_label('snare')  # a denied module's function, as a mutated engine would call it
        self.assertIn('reconcile.py', str(caught.exception))


class Imports(SimpleTestCase):
    def test_the_six_modules_import_only_what_the_new_path_may_run(self):
        for name in MODULES:
            source = (APP / 'studio' / 'interpretation' / f'{name}.py').read_text(encoding='utf-8')
            with self.subTest(module=name):
                found = scan(source)
                self.assertTrue(found['modules'])
                self.assertEqual(violations(found, 'S03'), [])  # the reference tables only, as S03's modules
                self.assertEqual(found['dynamic'], [])
                tree = ast.parse(source)
                imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
                imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
                self.assertNotIn('re', imported)  # no pattern here can be a denied pattern's twin
                for node in ast.walk(tree):  # checks.py is read only by FINAL 7.1's names (R-5; incomplete_check: R-4)
                    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'checks':
                        self.assertIn(node.attr, sentinel.CHECKS_ALLOWLIST + sentinel.CHECKS_ALLOWLIST_CONSTANTS)


# --- the independent participants (P-ADMIT) ------------------------------------------------------------------------------

class Participants(SimpleTestCase):
    def test_a_first_reading_code_no_proposal_carries_is_admitted_and_read_by_the_per_code_rule(self):
        inv, text = two_procedures()
        result = run(inv, text, [('45385', POLYP)], participants=(participant('astra', text,
                                                                              [('43239', EGD_LINES['G2'])]),))
        p = proposal(result, '43239')
        self.assertEqual((p.support['origin'], p.support['proposed_by'], p.status),
                         ('participant', ['astra'], 'ready'))
        self.assertTrue(p.rationale.startswith('Proposed by Astra (independent participant); Corti did not propose '
                                               'this code.'))
        self.assertEqual(check_of(result, 'participants.summary').status, 'info')

    def test_agreement_adds_proposers_and_nothing_else(self):
        inv, text = colonoscopy()
        alone = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        agreed = proposal(run(inv, text, [('45385', POLYP)],
                              participants=(participant('astra', text, [('45385', POLYP)]),
                                            participant('fable', text, [('45385', POLYP)]))), '45385')
        self.assertEqual(agreed.support['proposed_by'], ['corti', 'astra', 'fable'])
        for name in ('status', 'checks', 'fingerprint', 'clarifications', 'evidence', 'units', 'bucket'):
            self.assertEqual(getattr(agreed, name), getattr(alone, name), name)

    def test_peer_only_and_unlocated_codes_stay_alternatives(self):
        inv, text = colonoscopy()
        located = participant('astra', text, codes=[('45380', '')], peer_codes=[('45384', POLYP)])
        result = run(inv, text, [('45385', POLYP)], participants=(located,))
        alternatives = {p.code: p for p in result.proposals if p.bucket == 'alternative'}
        self.assertEqual(set(alternatives), {'45380', '45384'})
        self.assertIn(assess.UNLOCATED, alternatives['45380'].exclusion_reason)
        self.assertIn(assess.PARTICIPANT_PEER_ONLY, alternatives['45384'].exclusion_reason)
        self.assertTrue(all(key.startswith('altp:') for key in (p.key for p in alternatives.values())))

    def test_two_codes_for_one_event_compete_when_one_is_a_participants(self):
        """Two esophageal balloon dilation codes for one distal esophageal balloon dilation (43245, a gastric or
        duodenal dilation code, is no longer matched by it: DECISIONS D29)."""
        line = 'The distal esophageal stricture was dilated with a through-the-scope balloon to 15 mm.'
        inv, text = inventory({'G1': EGD_LINES['G1'], 'G2': line}, events=[
            exam('E0', 'G1', words='gastroscope', procedure=a('egd')),
            act('E2', 'G2', 'dilation', 'dilated', procedure=a('egd'), technique=a('balloon', 'balloon', ['G2']),
                target=tg('', 'distal_esophagus', 'distal esophageal', ['G2']))],
            reach=[reached('E0', 'second_portion_duodenum', 'second portion of the duodenum', 'G1')])
        result = run(inv, text, [('43249', line)], participants=(participant('astra', text, [('43233', line)]),))
        for code, rival in (('43249', '43233'), ('43233', '43249')):
            p = proposal(result, code)
            self.assertEqual(asked(p), ['competing_codes'])
            self.assertEqual(p.support['competes'], [rival])

    def test_a_disagreement_is_shown_and_changes_no_status(self):
        inv, text = colonoscopy()
        dissent = participant('astra', text, not_coded=[ParticipantNotCoded(
            code='45385', reason='not_performed_at_this_encounter', evidence=(quote(text, POLYP),))])
        p = proposal(run(inv, text, [('45385', POLYP)], participants=(dissent,)), '45385')
        self.assertEqual((p.status, check(p, 'participants.disagree').status), ('ready', 'warn'))

    def test_a_malformed_or_unknown_participant(self):
        inv, text = colonoscopy()
        broken = ParticipantInput('astra', 'read', None)
        result = run(inv, text, [('45385', POLYP)], participants=(broken,))
        self.assertIn('Astra: not read (refused)', check_of(result, 'participants.summary').detail)
        with self.assertRaises(ValueError):
            run(inv, text, [('45385', POLYP)], participants=(ParticipantInput('corti', 'read', None),))

    def test_the_codes_to_look_up_cover_every_proposer(self):
        inv, text = two_procedures()
        astra = participant('astra', text, codes=[('43239', EGD_LINES['G2'])], peer_codes=[('45380', POLYP)])
        self.assertEqual(assess.codes_to_look_up(response(text, [('45385', POLYP)]),
                                                 response(text, [('43235', EGD_LINES['G1'])]), (astra,)),
                         ('43235', '43239', '45380', '45385'))


# --- the bounded second review (D10) ------------------------------------------------------------------------------------

class SecondReview(SimpleTestCase):
    def test_a_code_whose_events_meet_a_marked_item_is_added(self):
        inv, text = two_procedures()
        first = run(inv, text, [('45385', POLYP)])
        marked = [item for item in first.completeness['unresolved_items'] if item['second_review']]
        self.assertEqual([(item['service'], item['reason']) for item in marked], [('gi.egd', 'no_proposal')])
        second = response(text, [('43239', EGD_LINES['G2']), ('45380', POLYP), ('45385', POLYP)])
        result = run(inv, text, [('45385', POLYP)], second=second,
                     second_scope={'items': [marked[0]['label']]})
        p = proposal(result, '43239')
        self.assertEqual((p.bucket, p.support['origin'], p.status), ('selected', 'second_review', 'ready'))
        alternatives = {p.code: p for p in result.proposals if p.key.startswith('alt2:')}
        self.assertEqual(set(alternatives), {'45380', '45385'})
        self.assertIn('it accounts for no documented service or act the primary proposals left unresolved',
                      alternatives['45380'].exclusion_reason)
        self.assertIn('a primary proposal already carries it', alternatives['45385'].exclusion_reason)
        second_check = check_of(result, 'provider.second_review')
        self.assertIn('selected 43239, added as a proposal for review', second_check.detail)
        self.assertNotIn('gi.egd', [item['service'] for item in result.completeness['unresolved_items']])


# --- member answers --------------------------------------------------------------------------------------------------

class MemberAnswers(SimpleTestCase):
    def setUp(self):
        self.inv, self.text = colonoscopy(reach=False)
        self.codes = [('45378', COLONOSCOPE), ('45385', POLYP)]
        first = run(self.inv, self.text, self.codes)
        self.asked = assess._MemberAnswers((), self.text)._proposal_questions(first.proposals)
        self.first = first

    def answered(self, *answers):
        return run(self.inv, self.text, self.codes, member_answers=answers)

    def test_an_answer_to_the_question_asked_excludes_exactly_that_code(self):
        fingerprint = self.asked[('45385', 'gi.colonoscopy', 'extent')]
        result = self.answered(questions.MemberAnswerInput('45385', 'gi.colonoscopy', 'extent', 'not_documented',
                                                           fingerprint, 'answer-1'))
        p = proposal(result, '45385')
        before = proposal(self.first, '45385')
        self.assertEqual((p.bucket, p.status, p.reinstatable), ('excluded', 'excluded', False))
        self.assertEqual(p.support[questions.ANSWERED_SUPPORT],
                         {'fact': 'extent', 'value': 'not_documented', 'answers': ['answer-1']})
        self.assertEqual(check(p, 'member.answer').status, 'fail')
        self.assertEqual(p.fingerprint, wording.answered_fingerprint(before.fingerprint, p.checks, 'excluded'))
        self.assertTrue(questions.answered_away(p))
        base = proposal(result, '45378')  # its presence still holds the base code (session decision (e))
        self.assertEqual(asked(base)[:1], ['base_included'])
        self.assertEqual(base.fingerprint, proposal(self.first, '45378').fingerprint)
        record = result.completeness['member_answers']
        self.assertEqual([(item['answer'], item['proposals']) for item in record['applied']],
                         [('answer-1', ['sel:1'])])

    def test_answers_the_engine_leaves_to_the_overlay_or_that_no_longer_bind(self):
        result = self.answered(
            questions.MemberAnswerInput('45385', 'gi.colonoscopy', 'extent', 'cannot_confirm', '', 'answer-1'),
            questions.MemberAnswerInput('45378', 'gi.colonoscopy', 'base_included', 'not_documented', 'x', 'answer-2'),
            questions.MemberAnswerInput('45385', 'gi.colonoscopy', 'target', 'not_documented', 'y', 'answer-3'))
        self.assertEqual(proposal(result, '45385').bucket, 'selected')
        why = {item['answer']: item['why'] for item in result.completeness['member_answers']['earlier']}
        self.assertEqual(why, {'answer-1': wording.OVERLAY_READ, 'answer-2': wording.OVERLAY_READ,
                               'answer-3': questions.NO_LONGER_ASKED})


# --- fingerprints (FINAL 7.11, D7) ------------------------------------------------------------------------------------

class Fingerprints(SimpleTestCase):
    def test_stable_across_an_again_recompute_over_the_same_inventory(self):
        inv, text = colonoscopy()
        codes = [('45378', COLONOSCOPE), ('45385', POLYP)]
        once = run(inv, text, codes)
        stored = to_jsonable({'events': inv.events, 'encounter_facts': inv.encounter_facts,
                              'open_questions': inv.open_questions})
        again = run(stored, text, codes)
        self.assertEqual([p.fingerprint for p in once.proposals], [p.fingerprint for p in again.proposals])
        self.assertEqual(to_jsonable(once), to_jsonable(again))

    def test_changed_by_the_events_the_decision_read(self):
        inv, text = colonoscopy()
        hot, hot_text = colonoscopy(polyp=removed(technique=a('hot_snare', 'cold snare', ['P2'])))
        self.assertNotEqual(proposal(run(inv, text, [('45385', POLYP)]), '45385').fingerprint,
                            proposal(run(hot, hot_text, [('45385', POLYP)]), '45385').fingerprint)

    def test_it_names_the_engine(self):
        inv, text = colonoscopy()
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        context = {'service_date': '2026-11-09'}
        self.assertNotEqual(p.fingerprint, engine._fingerprint(p.code, p.family, p.profile_version, p.evidence,
                                                               p.checks, context, p.units, p.status))


# --- customer words ----------------------------------------------------------------------------------------------------

class CustomerWords(SimpleTestCase):
    def test_no_question_reason_summary_or_exclusion_names_a_provider_reader_or_rule_id(self):
        inv, text = colonoscopy(act('E3', 'P3', 'removal', 'removed', status='not_performed',
                                    status_words='No polyp was removed', scope=sc('all_of_kind', 'No', ['P3'])),
                                lines={'P3': 'No polyp was removed today.'})
        result = run(inv, text, [('45378', COLONOSCOPE), ('45385', POLYP), ('45390', 'No polyp was removed'),
                                 ('45305', COLONOSCOPE), ('45386', POLYP)])
        texts = [spec.question for spec in result.clarifications] + [spec.reason for spec in result.clarifications]
        for p in result.proposals:
            texts += [spec.question for spec in p.clarifications] + [spec.reason for spec in p.clarifications]
            texts += [p.exclusion_reason, p.support.get('summary', '')]
            texts += [item['label'] for item in p.support.get('acts', ())]
        for text_ in texts:
            if text_:
                self.assertIsNone(customer_api.FORBIDDEN.search(text_), text_)
                self.assertNotIn('gemini', text_.lower())

    def test_the_s16_repairs_holds_name_no_provider_reader_or_rule_id(self):
        """The sentences DECISIONS D27-D30 added: the defining act not documented, the examination class (its reach not
        stated, or not fitting), the dilation site (unsettled, or another site) and the procedural adjunct."""
        from tests.test_interpretation_coverage import adjunct
        from tests.test_interpretation_events import ANASTOMOTIC, ERCP_LINES, ESOPHAGEAL, dilated, ercp
        results = []
        inv, text = ercp()
        results.append(run(inv, text, [('43265', ERCP_LINES['P3'])]))
        for reach in ((), (reached('E1', 'duodenum', 'duodenum', 'P1'),)):
            inv, text = eus(FNA, reach=reach)
            results.append(run(inv, text, [('43238', EUS_LINES['P3']), ('43242', EUS_LINES['P3'])]))
        for line, target in (ANASTOMOTIC, ESOPHAGEAL):
            inv, text = dilated(line, target)
            results.append(run(inv, text, [('43245', line), ('43249', line)]))
        inv, text, lines = adjunct()
        results.append(run(inv, text, [('45390', lines['P2']), ('45388', lines['P3'])]))
        texts, reasons = [], set()
        for result in results:
            for p in result.proposals:
                reasons.add(p.support.get('reason'))
                texts += [spec.question for spec in p.clarifications] + [spec.reason for spec in p.clarifications]
                texts += [item.detail for item in p.checks if item.id in ('service.status', 'facts.examination_class',
                                                                          'facts.required', 'events.match')]
                texts += [p.support.get('summary', '')] + [item['label'] for item in p.support.get('acts', ())]
        self.assertLessEqual({events.NOT_DOCUMENTED, events.SITE, events.ANOTHER_SITE, events.BUNDLED}, reasons)
        self.assertTrue(any('limited endoscopic ultrasound examination' in t for t in texts))
        for text_ in texts:
            if text_:
                self.assertIsNone(customer_api.FORBIDDEN.search(text_), text_)
                self.assertNotIn('gemini', text_.lower())


# --- DECISIONS D28: the EUS examination class (R6) ---------------------------------------------------------------------

def eus_reaching(landmark: str, words: str, *more):
    """An upper EUS whose echoendoscope was advanced to ``words`` (its verified reach, ``landmark``), the pancreatic head
    examined, with ``more`` events (each in its EUS_LINES passage)."""
    lines = {'P1': f'A linear echoendoscope was advanced to the {words}.', 'P2': EUS_LINES['P2']}
    lines.update({event['status']['passages'][0]: EUS_LINES[event['status']['passages'][0]] for event in more})
    examination = exam(words='echoendoscope', procedure=a('eus'), target=tg('', 'pancreas', 'pancreatic head', ['P2']))
    examination['target']['passages'] = ['P2']
    return inventory(lines, events=[examination, *more], reach=[reached('E1', landmark, words, 'P1')])


class ExaminationClass(SimpleTestCase):
    """DECISIONS D28 (fb12: 43238 READY beside 43242, on an echoendoscope advanced to the second portion of the
    duodenum): a code the catalogue gives an EUS examination class reads its session's verified reach - the extent R6
    reads - and is held, never excluded and never READY, when that reach is not verified or does not fit the class.
    Every other code is unaffected."""

    def test_a_reach_into_the_duodenum_fits_the_full_code_and_holds_the_limited_one(self):
        inv, text = eus_reaching('second_portion_duodenum', 'second portion of the duodenum', FNA)
        result = run(inv, text, [('43242', EUS_LINES['P3']), ('43238', EUS_LINES['P3'])])
        full, limited = proposal(result, '43242'), proposal(result, '43238')
        self.assertEqual((full.status, check(full, 'facts.examination_class')), ('ready', None))
        self.assertIn('extent reached = second portion duodenum', check(full, 'facts.required').detail)
        self.assertEqual((limited.bucket, limited.status, asked(limited), limited.support['reason']),
                         ('selected', 'needs_clarification', ['extent'], events.SUPPORTED))
        reason, question = wording.examination_class_hold('43238', 'limited', 'second portion duodenum',
                                                          'second portion of the duodenum')
        self.assertEqual((check(limited, 'facts.examination_class').status, check(limited, 'facts.examination_class')
                          .detail, limited.clarifications[0].question, limited.clarifications[0].reason),
                         ('warn', reason, question, reason))
        self.assertEqual(question, 'The documented endoscopic ultrasound examination (“second portion of the duodenum”) '
                                   'reached the second portion duodenum. Was a limited endoscopic ultrasound examination '
                                   '(short of the duodenum) performed on the date of service?')

    def test_a_reach_short_of_the_duodenum_fits_the_limited_code_and_holds_the_full_one(self):
        inv, text = eus_reaching('gastric_antrum', 'gastric antrum', FNA)
        result = run(inv, text, [('43242', EUS_LINES['P3']), ('43238', EUS_LINES['P3'])])
        self.assertEqual(proposal(result, '43238').status, 'ready')
        full = proposal(result, '43242')
        self.assertEqual((full.status, asked(full)), ('needs_clarification', ['extent']))
        self.assertIn('accounts for a full endoscopic ultrasound examination (to the duodenum or beyond)',
                      full.clarifications[0].reason)

    def test_a_reach_in_neither_class_holds_both(self):
        """A limited examination is one verified SHORT of the duodenum (D28), not any reach outside the full list: a
        reach named only as the small bowel, or at an anastomosis, fits neither class."""
        for landmark, words in (('small_bowel', 'small bowel'), ('anastomosis', 'anastomosis')):
            inv, text = eus_reaching(landmark, words, FNA)
            self.assertEqual(inv.encounter_facts['reach'][0]['state'], 'verified')
            result = run(inv, text, [('43242', EUS_LINES['P3']), ('43238', EUS_LINES['P3'])])
            for code in ('43242', '43238'):
                p = proposal(result, code)
                with self.subTest(reach=landmark, code=code):
                    self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['extent']))
                    self.assertEqual(check(p, 'facts.examination_class').status, 'warn')

    def test_an_unverified_reach_asks_the_extent_and_never_excludes(self):
        inv, text = eus(FNA)
        result = run(inv, text, [('43242', EUS_LINES['P3']), ('43238', EUS_LINES['P3']), ('45342', EUS_LINES['P3'])])
        for code in ('43242', '43238'):
            p = proposal(result, code)
            with self.subTest(code=code):
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['extent']))
                self.assertEqual(p.clarifications[0].question, 'Endoscopic ultrasound: confirm the furthest extent '
                                                               'reached.')
                self.assertEqual(check(p, 'facts.required').status, 'warn')
                self.assertIsNone(check(p, 'facts.examination_class'))
        self.assertEqual(proposal(result, '45342').status, 'ready')  # a code with no class is unaffected

    def test_the_examination_only_codes(self):
        inv, text = eus(reach=[DUODENAL_REACH])
        statuses = {code: proposal(run(inv, text, [(code, EUS_LINES['P1'])]), code) for code in ('43259', '43237',
                                                                                                 '43231', '45341')}
        self.assertEqual({code: (p.status, asked(p)) for code, p in statuses.items()},
                         {'43259': ('ready', []), '43237': ('needs_clarification', ['extent']),
                          '43231': ('needs_clarification', ['extent']), '45341': ('ready', [])})

    def test_an_excluded_class_code_waits_on_its_class_when_reinstated(self):
        inv, text = eus(NO_FNA, reach=[DUODENAL_REACH])
        p = proposal(run(inv, text, [('43238', 'No fine-needle aspiration was performed')]), '43238')
        self.assertEqual((p.bucket, p.reinstatable), ('excluded', True))
        _, question = wording.examination_class_hold('43238', 'limited', 'duodenum', 'duodenum')
        self.assertEqual(p.support['reinstatement_waits'], [{'fact': 'extent', 'question': question}])
        self.assertEqual(check(p, 'review.reinstatement').status, 'warn')


# --- the copied legacy words, pinned ------------------------------------------------------------------------------------

class WordingPinned(SimpleTestCase):
    def test_labels(self):
        self.assertEqual(wording.ACT_LABELS, reconcile.ACT_LABELS)
        self.assertEqual(wording.SERVICE_LABELS, reconcile.SERVICE_LABELS)
        for kind in list(reconcile.ACT_LABELS) + list(reconcile.SERVICE_LABELS) + ['unheard_of_kind']:
            self.assertEqual(wording.act_label(kind), reconcile.act_label(kind))
            self.assertEqual(wording.kind_label(kind), reconcile.kind_label(kind))
        self.assertEqual(wording.TECHNIQUE_WORDS, reconcile.TECHNIQUE_WORDS)
        self.assertEqual(wording.quote('  A  long\nquote ' * 20, 50), reconcile.quote(Span(0, 1, '  A  long\nquote ' * 20),
                                                                                       50))
        self.assertEqual(wording.SOURCE, reconcile.SOURCE)

    def test_helpers_and_constants(self):
        for text_ in ('short', 'x ' * 200):
            self.assertEqual(wording.excerpt(text_), checks.excerpt(text_))
        for items in ([], ['a'], ['a', 'b'], ['a', 'b', 'c']):
            self.assertEqual(wording.join(items), checks._join(items))
        self.assertEqual((wording.plural(1, 'code'), wording.plural(2, 'code')),
                         (checks.plural(1, 'code'), checks.plural(2, 'code')))
        for family in PROFILES:
            self.assertEqual(wording.service_name('99999', family), checks.service_name(PROFILES[family], '99999'))
        self.assertEqual(wording.PROPOSAL_DATE_CHECK, checks.PROPOSAL_DATE_CHECK)
        self.assertEqual(wording.SEPARATE_EM_CONSIDERATION, checks.SEPARATE_EM_CONSIDERATION)
        self.assertEqual(wording.EM_FAMILIES, checks.EM_FAMILIES)
        self.assertEqual((wording.STATUS_SOURCE, wording.CONTEXT_SOURCE, wording.EM_SOURCE, wording.COVERAGE_SOURCE,
                          wording.PROVIDER_SOURCE),
                         (checks.STATUS_SOURCE, checks.CONTEXT_SOURCE, checks.EM_SOURCE, checks.COVERAGE_SOURCE,
                          checks.PROVIDER_SOURCE))
        self.assertEqual((wording.MAX_LISTED_CODE, wording.NO_EVIDENCE), (engine.MAX_LISTED_CODE, engine.NO_EVIDENCE))
        self.assertEqual(wording.MEMBER_ENTERED, checks.MEMBER_ENTERED)

    def test_the_dated_and_consideration_sentences(self):
        for pfs in (None, {'modifier_rows': ['53']}, {'modifier_rows': []}):
            self.assertEqual(wording.incomplete_consideration('45378', pfs, 'RVU26D'),
                             checks.incomplete_consideration('45378', pfs, 'RVU26D'))
        for entries in ((), (('45385', '000'), ('45378', '000'))):
            self.assertEqual(wording.global_days_note(entries, 'RVU26D', 'none.'),
                             checks.global_days_note(entries, 'RVU26D', 'none.'))
        for count in (1, 3):
            self.assertEqual(wording.unlisted_codes(count, 10), checks.unlisted_codes(count, 10))
            self.assertEqual(wording.unlisted_codes(count, 10, 'The second review'),
                             checks.unlisted_codes(count, 10, 'The second review'))
            self.assertEqual(wording.unlisted_codes_check(count, 10), checks.unlisted_codes_check(count, 10))
        self.assertEqual(wording.response_problems(['a', 'b'], 'x'), checks.response_problems(['a', 'b'], 'x'))
        source = ReferenceSourceInfo(key='k', kind='cms-pfs', publisher='CMS', title='t', release='RVU26D', url='u',
                                     sha256='0' * 64, effective_start='2026-10-01', effective_end='2026-12-31',
                                     license_note='', scope_note='')
        for sources, day in (((), None), ((), date(2026, 11, 9)), ((source,), date(2026, 11, 9)),
                             ((source, source), date(2026, 11, 9)), ((source,), date(2027, 1, 9))):
            self.assertEqual(wording.unavailable_reason('CMS Physician Fee Schedule', sources, 'cms-pfs', day),
                             checks.unavailable_reason('cms-pfs', sources, day))

    def test_the_reconcile_holds_are_the_legacy_sentences(self):
        """The reconcile.match sentences the engine copies (FINAL 7.2 R5, 7.4 h6 and h1), each built by the legacy
        reconcile.match itself over a minimal documented-service reading (a test-only import) and compared with the
        copy for the same inputs: the "part of another documented act" detail and question (reconcile.py:268-289), the
        dilation of another technique (reconcile.py:307-316) and the conflict question (reconcile.py:252-258). The
        conflict's detail is CPT Studio's own sentence over two events (wording.conflict_reason), not a copy."""
        from studio.gi import services as gi_services
        text = ('A 25 mm flat lesion in the cecum was lifted with a submucosal injection and resected by EMR. '
                'The rectal stricture was dilated with Savary dilators over a guide wire to 15 mm. '
                'A 6 mm polyp was removed with a cold snare. No polyp was removed.')

        def span(phrase):
            start = text.index(phrase)
            return Span(start, start + len(phrase), phrase)

        def legacy(code, acts, conflicts=()):
            service = gi_services.DocumentedService(id='S1', family='gi.colonoscopy', kind='colonoscopy',
                                                    status='performed', acts=tuple(acts))
            reading = gi_services.ServiceInventory(version='test', services=(service,), conflicts=tuple(conflicts))
            return service, reconcile.match(code, reading, 'gi.colonoscopy')

        def done(aid, kind, phrase, anatomy=()):
            return gi_services.Act(id=aid, service='S1', kind=kind, status='performed', role='physician',
                                   anatomy=tuple(anatomy), evidence=(span(phrase),))

        lift = 'lifted with a submucosal injection'
        service, match = legacy('45381', [done('A1', 'injection', lift, ['cecum']),
                                          done('A2', 'emr', 'resected by EMR', ['cecum'])])
        self.assertEqual(match.reason, 'act_included')
        listed = '; '.join(reconcile.describe_act(service, item) for item in match.acts[:4])
        what = ' or '.join(reconcile.act_label(kind) for kind in ('injection', 'tattoo'))
        self.assertEqual(wording.act_included('colonoscopy', 'performed', listed,
                                              reconcile._bundled(service, match.acts[0]), what, lift),
                         (match.detail, match.question))
        savary = 'dilated with Savary dilators over a guide wire to 15 mm'
        _, match = legacy('45386', [done('A1', 'dilation', savary, ['rectum'])])
        self.assertTrue(match.detail.startswith('The colonoscopy is documented as performed with a dilation with'))
        self.assertEqual(wording.another_technique('colonoscopy', wording.TECHNIQUE_WORDS['wire_bougie'],
                                                   wording.TECHNIQUE_WORDS['balloon'], savary),
                         (match.detail, match.question))
        removed = 'A 6 mm polyp was removed with a cold snare'
        sides = (gi_services.ConflictSide('performed', 'physician', (span(removed),)),
                 gi_services.ConflictSide('negated', 'physician', (span('No polyp was removed'),)))
        _, match = legacy('45385', [done('A1', 'snare', removed)],
                          [gi_services.Conflict(id='C1', service='S1', subject='snare', lesion='', sides=sides)])
        self.assertEqual(match.reason, 'conflict')
        self.assertEqual(wording.conflict_question(reconcile.act_label('snare')), match.question)

    def test_the_performed_question_is_the_engines_inline_sentence(self):
        """wording.performed_question copies an f-string the legacy engine writes inline (engine._proposal's fallback
        question, engine.py:3327), so it is pinned against that function's own source."""
        import inspect
        self.assertIn("f'" + wording.performed_question('{s.code}') + "'", inspect.getsource(engine._proposal))

    def test_the_member_answers_exclusion_is_the_engines(self):
        """The member answer's exclusion (its reason sentence, the member.answer check, support['answered'] and the
        answered fingerprint) built by the legacy engine's own _MemberAnswers._excluded (a test-only import) over the
        same proposal and answer: a required fact and a conflict."""
        inv, text = colonoscopy(reach=False)
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']))
        conflicted, conflict_text = colonoscopy(denial, lines={'P3': 'No polyp was removed today.'})
        for fact, (inventory_, text_) in (('extent', (inv, text)), ('conflict:snare', (conflicted, conflict_text))):
            with self.subTest(fact=fact):
                p = proposal(run(inventory_, text_, [('45385', POLYP)]), '45385')
                self.assertIn(fact, asked(p))
                answer = questions.MemberAnswerInput('45385', 'gi.colonoscopy', fact, 'cannot_confirm', 'f', 'a-1')
                answer_of = {questions.member_key('45385', 'gi.colonoscopy', fact): answer}
                ours = assess._MemberAnswers((), text_)._excluded(p, fact, answer_of)
                theirs = engine._MemberAnswers((), text_)._excluded(p, SimpleNamespace(answered=fact), answer_of)
                self.assertEqual(ours, theirs)
                self.assertTrue(ours.exclusion_reason.startswith('The member answered "Cannot confirm" to '))

    def test_the_incomplete_check_is_worded_from_its_own_words(self):
        """R-4: checks.incomplete_check reads a legacy status outcome and is not allowed; the copy keeps its id, label,
        status, source and closing sentence."""
        found = wording.incomplete_check('could not be advanced')
        self.assertEqual((found.id, found.label, found.status, found.source),
                         ('service.incomplete', 'Incomplete procedure documented', 'warn', checks.STATUS_SOURCE))
        self.assertTrue(found.detail.endswith('Kept for review: not treated as completed and not excluded.'))
        self.assertNotIn('incomplete_check', sentinel.CHECKS_ALLOWLIST)

    def test_member_answer_and_alternative_words(self):
        self.assertEqual((wording.MEMBER_ANSWER_CHECK, wording.MEMBER_ANSWER_SOURCE, wording.MEMBER_ANSWER_LABELS,
                          wording.NOT_APPLIED, wording.OVERLAY_READ),
                         (engine.MEMBER_ANSWER_CHECK, engine.MEMBER_ANSWER_SOURCE, engine.MEMBER_ANSWER_LABELS,
                          engine.NOT_APPLIED, engine.OVERLAY_READ))
        found = (checks.PROPOSAL_DATE_CHECK,)
        self.assertEqual(wording.answered_fingerprint('f', found, 'excluded'),
                         engine.answered_fingerprint('f', found, 'excluded'))
        for role, parent, unlisted, not_added in (('alternative', '45385', False, ''), ('alternative', None, True, ''),
                                                  ('candidate', None, False, ''), ('selected', None, False, 'why'),
                                                  ('odd', None, False, '')):
            self.assertEqual(wording.alternative_note(role, parent, unlisted_parent=unlisted, not_added=not_added),
                             rationale.alternative_note(role, parent, unlisted_parent=unlisted, not_added=not_added))
            self.assertEqual(wording.alternative_rationale(provider='corti', role=role, parent_code=parent,
                                                           evidence_count=2, unlisted_parent=unlisted,
                                                           not_added=not_added),
                             rationale.alternative_rationale(provider='corti', role=role, parent_code=parent,
                                                             evidence_count=2, unlisted_parent=unlisted,
                                                             not_added=not_added))

    def test_the_assess_copies(self):
        self.assertEqual((assess.UNLOCATED, assess.PARTICIPANT_PEER_ONLY, assess.SECOND_REVIEW_NAMED),
                         (engine.UNLOCATED, engine.PARTICIPANT_PEER_ONLY, engine.SECOND_REVIEW_NAMED))
        for labels in ([], ['a'], [str(index) for index in range(7)]):
            self.assertEqual(assess._asked_items(labels), engine._asked_items(labels))
        for names in (['astra'], ['astra', 'fable']):
            self.assertEqual(assess._participant_names(names), engine._participant_names(names))
        codes = [ProviderCode('selected', 'cpt', '45385', 'x'), ProviderCode('candidate', 'cpt', '45380', 'x'),
                 ProviderCode('selected', 'cpt', '45385', 'y'), ProviderCode('selected', 'cpt', '45378', 'z')]
        self.assertEqual(assess._merge_selected(codes), engine._merge_selected(codes))
        rows = [SimpleNamespace(excluded=value) for value in (False, True, False, True, False)]
        self.assertEqual(assess._keys(rows), engine._keys(rows))
        merge = dict(what='a; b', asked=('a', 'b'), refused=False, problems=('p',), added=('43239',),
                     listed=('45380',), accounts_for=('a',), unlisted=1)
        for unresolved in ([], [{'label': 'b'}]):
            self.assertEqual(assess._second_review_check(assess._SecondMerge(**merge), unresolved),
                             engine._second_review_check(engine._SecondMerge(**merge),
                                                         [SimpleNamespace(label=item['label']) for item in unresolved]))
        for changes in ({'added': (), 'accounts_for': ()}, {'refused': True}):
            self.assertEqual(assess._second_review_check(assess._SecondMerge(**{**merge, **changes}), []),
                             engine._second_review_check(engine._SecondMerge(**{**merge, **changes}), []))
        proposals = [SimpleNamespace(bucket='selected', status='ready'), SimpleNamespace(bucket='alternative',
                                                                                         status='informational')]
        state = checks.DateState(date(2026, 11, 9), 'document')
        self.assertEqual(assess._summary(proposals, 'succeeded', 'ok', date(2026, 11, 9)),
                         engine._summary(proposals, 'succeeded', 'ok', state))

    def test_the_rows_of_the_catalogue_this_engine_reads_are_named(self):
        self.assertEqual(coverage.RESECTIONS, frozenset({'emr', 'esd'}))
        self.assertEqual(set(catalogue.NOT_REPORTED), {'clip', 'cannulation'})
