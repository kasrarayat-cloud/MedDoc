"""DECISIONS D86 (the Gemini migration's round-3 repair "questions"; the owner's head-to-head of 2026-11-10): a
same-event contradiction asks the contradiction.

On three FRESH-2 rows the new path held the code and asked act_target ("Which lesion or site was the snare removal ...
done on?") where the document contradicts itself, and the installed release asks the contradiction (performed_status,
conflict:<kind>): C1CL3-001 45385 ("No polypectomy was performed in the prior segment." beside the sigmoid snare),
W1-u30a-rel-f1-ownpassage-004 and -005 45381 ("Lift: submucosal injection x2." / "Submucosal injection: Yes" beside a
removal "without submucosal injection"). Each code rested on an UNRESOLVED(target) relation whose STATEMENT is the
denial, and FINAL 7.4 h3 asked the fact of the attribute (events.RELATION_FACTS). Now, for a code, an UNRESOLVED
relation whose statement is a denial - status not_performed in any state, or a negator recorded in its own status words
- asks whether that statement applies to the act (statement_scope, naming both), whatever attribute the relation rests
on. Only the question changes: the code stays held, never READY, never excluded.

The boundaries, each pinned: a doubt (status uncertain), a positive event (Gemini's claim that two acts are one) and the
service-scope question about an event no code depends on (events.focus_question, FINAL 7.8) keep the question of the
attribute. The last because coverage.in_doubt_questions asks one question per (family, fact): moved to statement_scope,
the in_doubt act's question was dropped where the family's codes ask statement_scope (FRESH-2 C2MEM-031 r1, the balloon
dilation's "done at this encounter?").

RECORDED: the committed FRESH-2 run 1 of each row (tests/fixtures/interpretation), read and assessed exactly as
score_fresh.py does - the paste's text and pages with the recorded request checked, the stored answer read and
normalized, the gemini-context facts with no member values, one replayed proposer response citing the registry's own
quotes, and an empty reference lookup. SYNTHETIC: the shared S08 builders (tests.test_interpretation_events). Nothing is
sent."""
from __future__ import annotations

import copy
import hashlib

from django.test import SimpleTestCase

from studio.interpretation import adapter, events, facts, normalize
from studio.interpretation import assess as events_engine
from studio.interpretation import read as interpretation_read
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from tests.test_interpretation_events import (COLONOSCOPE, POLYP, asked, colonoscopy, exam, inventory, proposal,
                                              reached, removed, run)
from tests.test_interpretation_identity import a, act, les, sc, snare, tg
from tests.test_interpretation_replay import FIXTURES, MANIFEST, text_and_pages

ENTRIES = {entry['id']: entry for entry in MANIFEST['documents']}


def recorded(item_id: str, citations) -> tuple:
    """(the normalized inventory, the assessment) of the committed FRESH-2 run 1 of ``item_id``, as score_fresh.py makes
    them; ``citations``: (code, quote, the registry's start, or None for a FRESH-A quote) each, located as
    score_fresh.locate locates them."""
    entry = ENTRIES[item_id]
    text, pages = text_and_pages(entry)
    request = adapter.Interpreter().build_request(text, pages, 'paste')
    assert request.canonical_sha256 == entry['request_sha256'], item_id
    run_1 = entry['runs']['r1']
    body = (FIXTURES / run_1['body']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == run_1['body_sha256'], item_id
    parsed = interpretation_read.read(adapter.answer_text(request, body))
    assert not isinstance(parsed, interpretation_read.Refusal), parsed
    inventory = normalize.normalize(parsed, text)
    derived = facts.derive(inventory, {})
    codes = []
    for code, quote, start in citations:
        at = start if start is not None and text[start:start + len(quote)] == quote else text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, at, at + len(quote), quote, True),)))
    result = events_engine.assess(
        inventory=inventory, context=dict(derived.facts),
        normalized=NormalizedResponse('replay', 'test@1', tuple(sorted(codes, key=lambda item: item.code))),
        provider_status='succeeded', reference=InMemoryReferenceLookup((), {}), text=text, pages=pages,
        extraction_status='ok', extraction_messages=())
    return inventory, result


def unresolved(inventory) -> list:
    """(statement, event, attribute, reason, the statement's status) of every UNRESOLVED relation."""
    found = {item['id']: item for item in inventory.events['events']}
    return [(item['statement'], item['event'], item['attribute'], item['reason'],
             found[item['statement']]['status']['value'])
            for item in inventory.events['relations'] if item['type'] == 'unresolved']


def sources(p) -> list:
    return [span['text'] for span in p.support['source']]


class RecordedRows(SimpleTestCase):
    """The three rows of the head-to-head, and the recorded rows D86 also reaches, on their FRESH-2 answers."""

    def assert_scope_question(self, p, statement: str, act: str, act_words: str):
        """Held, asking whether the denial applies to the act: the question names the statement's own words and the act
        (its label, then its own words quoted)."""
        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                         ('selected', 'needs_clarification', ['statement_scope'], events.UNRESOLVED))
        question = p.clarifications[0]
        self.assertTrue(question.question.startswith(f'Does “{statement}” apply to the {act}'), question.question)
        self.assertTrue(question.question.endswith(f'(“{act_words}”)?'), question.question)
        self.assertTrue(question.reason.startswith(f'The document states “{statement}”; CPT Studio could not confirm '
                                                   f'from the document whether that statement applies to the {act}'),
                        question.reason)

    def test_d86_c1cl3_001_asks_whether_the_prior_segment_denial_applies_to_the_snare(self):
        inventory, result = recorded('C1CL3-001', [('45380', 'biopsies were taken from the rectum', 354),
                                                   ('45385', 'was removed with a cold snare', 290)])
        # the rule that asked act_target: an UNRESOLVED(target) relation whose statement is the denial
        self.assertEqual(unresolved(inventory), [('E4', 'E2', 'target', 'site_unresolved', 'not_performed')])
        p = proposal(result, '45385')
        self.assert_scope_question(p, 'No polypectomy was performed', 'snare removal', 'was removed')
        self.assertIn('No polypectomy was performed in the prior segment.', sources(p))  # both sides are shown
        self.assertIn('On withdrawal, a 6 mm polyp in the sigmoid colon was removed with a cold snare.', sources(p))
        self.assertEqual(p.support['question_events'], ['E2', 'E4'])
        self.assertEqual(proposal(result, '45380').status, 'ready')  # the rectal biopsies: nothing denies them

    def test_d86_ownpassage_004_asks_whether_without_injection_applies_to_the_lift_row(self):
        inventory, result = recorded('W1-u30a-rel-f1-ownpassage-004',
                                     [('45381', 'Lift: submucosal injection x2.', 349)])
        self.assertEqual(unresolved(inventory), [('E3', 'E4', 'target', 'identity_unresolved', 'not_performed')])
        p = proposal(result, '45381')
        self.assert_scope_question(p, 'without submucosal injection', 'submucosal injection',
                                   'Lift: submucosal injection x2')
        self.assertEqual(p.support['question_events'], ['E4', 'E3'])

    def test_d86_ownpassage_005_asks_whether_without_injection_applies_to_the_yes_row(self):
        inventory, result = recorded('W1-u30a-rel-f1-ownpassage-005', [('45381', 'Submucosal injection: Yes', 226)])
        self.assertEqual(unresolved(inventory), [('E4', 'E2', 'target', 'identity_unresolved', 'not_performed')])
        p = proposal(result, '45381')
        self.assert_scope_question(p, 'without submucosal injection', 'submucosal injection', 'Yes')
        self.assertEqual(p.support['question_events'], ['E2', 'E4'])

    def test_d86_c1cl2_002_a_claimed_contradiction_whose_statuses_gemini_opened_asks_the_denial(self):
        # UNRESOLVED(status): Gemini claims the contradiction and opens both statuses with its own question, so the
        # pairing cannot read them. The code asked performed_status; D86 asks the denial, whatever attribute the
        # relation rests on (the head-to-head reads statement_scope as asking what performed_status names).
        inventory, result = recorded('C1CL2-002', [('45380', 'Biopsies were taken from the rectum', 306),
                                                   ('45385', 'was removed with a cold snare', 275)])
        self.assertEqual(unresolved(inventory), [('E4', 'E2', 'status', 'status_unresolved', 'not_performed')])
        p = proposal(result, '45385')
        # D91: a status relation keeps the question the expectation names (performed_status), as at a4dcbea72
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['performed_status'], events.UNRESOLVED))

    def test_d86_v4_r1_a_denial_whose_own_words_hold_no_negator_asks_the_contradiction(self):
        # FRESH-A v4 (an earlier denial extended to today, "This time as well."): the statement is not_performed with
        # words that hold no negator (negation_missing, unverified), so D86's first arm alone makes it a denial; the
        # code asked performed_status
        snared = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare and retrieved.'
        inventory, result = recorded('v4_this_time_as_well', [('45378', snared, None), ('45385', snared, None)])
        self.assertEqual(unresolved(inventory), [('E3', 'E5', 'status', 'status_unresolved', 'not_performed')])
        statement = next(item for item in inventory.events['events'] if item['id'] == 'E3')['status']
        self.assertEqual((statement['state'], statement['reasons'], statement['literals']),
                         ('unverified', ['negation_missing'], {}))
        p = proposal(result, '45385')
        # D91: a status relation keeps performed_status, as at a4dcbea72
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['performed_status'], events.UNRESOLVED))

    def test_d86_c2cl_013_keeps_its_scope_question(self):
        # the control the spec names: an UNRESOLVED(scope) relation already asked statement_scope, and still does
        inventory, result = recorded('C2CL-013', [('45380', 'Biopsies were taken from the rectum', 306),
                                                  ('45385', 'was removed with a cold snare', 275)])
        self.assertEqual(unresolved(inventory), [('E5', 'E2', 'scope', 'scope_unresolved', 'not_performed')])
        p = proposal(result, '45385')
        self.assert_scope_question(p, 'was not repeated', 'snare removal', 'was removed')
        self.assertEqual(proposal(result, '45380').status, 'ready')


PRIOR = 'No polypectomy was performed in the prior segment.'


def prior_segment_denial(eid: str = 'E3', passage: str = 'P3', **changes) -> dict:
    """C1CL3-001's denial, synthetic: its target is a sigmoid colon its own words ("the prior segment") never name, so
    the target is unverified (landmark_missing) and the pairing leaves it UNRESOLVED(target, site_unresolved)."""
    options = dict(status='not_performed', status_words='No polypectomy was performed',
                   scope=sc('single_target', 'No polypectomy was performed in the prior segment', [passage]),
                   target=tg('', 'sigmoid_colon', 'the prior segment', [passage]))
    options.update(changes)
    return act(eid, passage, 'removal', 'polypectomy', **options)


class SyntheticPairs(SimpleTestCase):
    """A synthetic denial/act pair (the spec's), the lift-row pair, and every attribute an UNRESOLVED relation from a
    denial can rest on."""

    def held_by(self, p, relation_attribute: str, inventory, statement: str, event: str = 'E2'):
        found = [(item['statement'], item['event'], item['attribute']) for item in inventory.events['relations']
                 if item['type'] == 'unresolved']
        self.assertIn((statement, event, relation_attribute), found)
        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                         ('selected', 'needs_clarification', ['statement_scope'], events.UNRESOLVED))

    def test_d86_a_denial_of_a_segment_its_words_do_not_name_asks_whether_it_applies_to_the_snare(self):
        inv, text = colonoscopy(prior_segment_denial(), lines={'P3': PRIOR})
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.held_by(p, 'target', inv, 'E3')
        question = p.clarifications[0].question
        self.assertTrue(question.startswith('Does “No polypectomy was performed” apply to the snare removal'), question)
        self.assertTrue(question.endswith('(“was removed with a cold snare”)?'), question)
        self.assertIn(PRIOR, sources(p))
        self.assertIn(POLYP, sources(p))

    def test_d86_an_injection_denial_beside_a_lift_row_asks_the_contradiction(self):
        lines = {'P1': COLONOSCOPE,
                 'P2': 'A 22 mm polyp in the ascending colon was removed piecemeal with a cold snare in four pieces, '
                       'without submucosal injection.',
                 'P3': 'Lift: submucosal injection x2.'}
        polyp = les('L1', '22 mm polyp', 'P2', landmark='ascending_colon', site_words='ascending colon',
                    size_words='22 mm')
        target = tg('L1', 'ascending_colon', '22 mm polyp in the ascending colon', ['P2'])
        events_ = [snare('E2', 'P2', status_words='was removed piecemeal with a cold snare', target=target),
                   act('E3', 'P2', 'injection', 'submucosal injection', status='not_performed',
                       status_words='without submucosal injection', target=target,
                       scope=sc('single_target', '22 mm polyp in the ascending colon', ['P2'], targets=['L1'])),
                   act('E4', 'P3', 'injection', 'submucosal injection', status_words='Lift: submucosal injection x2')]
        inv, text = colonoscopy(*events_[1:], lines=lines, lesions=[polyp], polyp=events_[0])
        p = proposal(run(inv, text, [('45381', 'Lift: submucosal injection x2.')]), '45381')
        self.held_by(p, 'target', inv, 'E3', 'E4')
        question = p.clarifications[0].question
        self.assertTrue(question.startswith('Does “without submucosal injection” apply to the submucosal injection'),
                        question)
        self.assertTrue(question.endswith('(“Lift: submucosal injection x2”)?'), question)

    def test_d86_a_not_performed_statement_whose_words_hold_no_negator_is_a_denial(self):
        # v4's shape: "This time as well." extends the History's denial to today; its own words hold no negator, so
        # its status is unverified (negation_missing) and the pairing gives UNRESOLVED(status)
        lines = {'P3': 'History: No polypectomy was performed at the 2024 colonoscopy.', 'P4': 'This time as well.'}
        extended = act('E3', 'P4', 'removal', 'polypectomy', status='not_performed', status_words='This time as well',
                       scope=sc('all_of_kind', 'No polypectomy', ['P3', 'P4']),
                       time=a('current_encounter', 'This time', ['P4']))
        extended['kind'] = a('removal', 'polypectomy', ['P3', 'P4'])  # its kind is named in the History's line
        inv, text = colonoscopy(extended, lines=lines)
        status = next(item for item in inv.events['events'] if item['id'] == 'E3')['status']
        self.assertEqual((status['value'], status['reasons'], status['literals']),
                         ('not_performed', ['negation_missing'], {}))
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        found = [(item['statement'], item['event'], item['attribute']) for item in inv.events['relations']
                 if item['type'] == 'unresolved']
        self.assertIn(('E3', 'E2', 'status'), found)
        # D91: a status relation keeps performed_status, the question the expectations name for a contradiction
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['performed_status'], events.UNRESOLVED))

    def test_d91_only_a_target_relation_asks_the_denial_every_other_attribute_keeps_its_question(self):
        # DECISIONS D91 (integration of D86): 'whatever attribute' moved questions the expectations name (C1CL2-002 and
        # C2CL-008's performed_status; a time question the act really lacks), so D86 reaches the target attribute alone
        denied = 'No polyp was removed.'
        base = dict(status='not_performed', status_words='No polyp was removed', scope=sc('all_of_kind', 'No', ['P3']))
        contradiction = {'about': 'contradiction', 'events': ['E2', 'E3'], 'lesions': [], 'passages': ['P2', 'P3']}
        claim = [{'event': 'E2', 'passages': ['P2', 'P3']}]
        cases = {  # attribute: (the denial, its line, Gemini's open questions, the question asked at a4dcbea72)
            'time': (act('E3', 'P3', 'removal', 'removed', time=a('unknown'), **base), denied, (), 'event_time'),
            'performer': (act('E3', 'P3', 'removal', 'removed', performer=a('unknown'), **base), denied, (),
                          'event_performer'),
            'technique': (act('E3', 'P3', 'snare', 'cold snare', status='not_performed',
                              status_words='No cold snare was used', technique=a('cold_snare', 'cold snare', ['P3']),
                              scope=sc('single_target', 'the 6 mm sessile polyp', ['P3'], targets=['L1']),
                              target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', ['P3'])),
                          'No cold snare was used for the 6 mm sessile polyp.', (), 'technique'),
            'status': (act('E3', 'P3', 'removal', 'removed', contradicts=claim, **base), denied, (contradiction,),
                       'performed_status'),
            'kind': (act('E3', 'P3', 'emr', 'EMR', status='not_performed', status_words='No EMR was performed',
                         scope=sc('all_of_kind', 'No', ['P3']), contradicts=claim),
                     'No EMR was performed.', (), 'performed_status'),
        }
        for attribute, (denial, line, questions, before) in cases.items():
            with self.subTest(attribute=attribute, before=before):
                polyp = removed(technique=a('not_stated')) if attribute == 'technique' else None
                inv, text = colonoscopy(denial, lines={'P3': line}, polyp=polyp, open_questions=list(questions))
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
                found = [(item['statement'], item['event'], item['attribute']) for item in inv.events['relations']
                         if item['type'] == 'unresolved']
                self.assertIn(('E3', 'E2', attribute), found)
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', [before], events.UNRESOLVED))


class Boundaries(SimpleTestCase):
    """What D86 does not reach, each with the question it keeps."""

    CLIP = 'Oozing at the biopsy site was controlled with a clip.'

    def clip_beside(self, statement: dict, line: str):
        """A clip placed for hemostasis (bleeding control, 45382) beside ``statement``, a clip statement of no stated
        purpose: it meets the act by their one Gemini kind (relations.concerns) and is no candidate of 45382, so FINAL
        7.4 h2 never reads it and h3 decides the code's question."""
        clip = act('E2', 'P2', 'clip', 'clip', status_words='was controlled with a clip',
                   purpose=a('hemostasis', 'Oozing at the biopsy site was controlled', ['P2']))
        inv, text = inventory({'P1': COLONOSCOPE, 'P2': self.CLIP, 'P3': line}, events=[exam(), clip, statement],
                              reach=[reached()])
        return inv, proposal(run(inv, text, [('45382', self.CLIP)]), '45382')

    def test_d86_a_doubt_keeps_the_question_of_its_attribute(self):
        for attribute, changes, fact in (
                ('target', dict(scope=sc('single_target', 'in the prior segment', ['P3']),
                                target=tg('', 'sigmoid_colon', 'the prior segment', ['P3'])), 'act_target'),
                ('time', dict(scope=sc('all_of_kind', 'clip', ['P3']), time=a('unknown')), 'event_time')):
            for status, words, asked_now in (('uncertain', 'It is unclear whether a clip was placed', fact),
                                             ('not_performed', 'No clip was placed',
                                              'statement_scope' if attribute == 'target' else fact)):  # D91
                with self.subTest(attribute=attribute, status=status):
                    statement = act('E3', 'P3', 'clip', 'clip', status=status, status_words=words, **changes)
                    inv, p = self.clip_beside(statement, f'{words} in the prior segment.')
                    self.assertIn(('E3', 'E2', attribute, status), [item[:3] + (item[4],) for item in unresolved(inv)])
                    self.assertEqual((p.status, asked(p), p.support['reason']),
                                     ('needs_clarification', [asked_now], events.UNRESOLVED))

    def test_d86_a_claim_that_two_performed_acts_are_one_keeps_the_question_of_its_attribute(self):
        lines = {'P1': COLONOSCOPE, 'P2': POLYP, 'P3': 'The polyp was removed with a cold snare.'}
        first = removed(contradicts=[{'event': 'E3', 'passages': ['P2', 'P3']}])
        second = snare('E3', 'P3', target=tg('', 'not_stated', '', []))
        inv, text = colonoscopy(second, lines=lines, polyp=first)
        self.assertEqual({(item[2], item[4]) for item in unresolved(inv)}, {('target', 'performed')})
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['act_target'], events.UNRESOLVED))

    def test_d86_a_negator_recorded_in_the_statements_status_words_is_a_denial(self):
        # The second arm of D86's denial: the statement's own status words hold a negator (verify's negation_marker
        # literal), whatever its status value. normalize records that literal only on a not_performed status, so the
        # arm is read here on a stored record whose status value was replaced by 'planned' (never a positive candidate,
        # so h2 never reads it); its relation is the one recorded. Without the literal, a planned statement keeps the
        # question of its attribute.
        inv, text = colonoscopy(prior_segment_denial(), lines={'P3': PRIOR})
        content = inv.content()
        statement = next(item for item in content['events']['events'] if item['id'] == 'E3')
        self.assertEqual(statement['status']['literals'], {'negators': ['no']})
        derived = facts.derive(inv, {})
        for literals, fact in (({'negators': ['no']}, 'statement_scope'), ({}, 'act_target')):
            with self.subTest(literals=literals):
                stored = copy.deepcopy(content)
                record = next(item for item in stored['events']['events'] if item['id'] == 'E3')
                record['status'].update(value='planned', literals=literals)
                start = text.index(POLYP)
                response = NormalizedResponse('corti', 'test@1', (ProviderCode(
                    'selected', 'cpt', '45385', 'UNVERIFIED PROVIDER WORDING',
                    (EvidenceSpan(0, start, start + len(POLYP), POLYP, True),)),))
                result = events_engine.assess(inventory=stored, context=dict(derived.facts), normalized=response,
                                              provider_status='succeeded', reference=InMemoryReferenceLookup((), {}),
                                              text=text, extraction_status='ok')
                self.assertEqual(asked(proposal(result, '45385')), [fact])

    DILATION = 'The balloon was inflated sequentially to 12 mm.'
    ASIDE = 'Those were the findings at her index colonoscopy.'
    HISTORY = 'No dilation was carried out in 2024.'

    def in_doubt_dilation(self):
        """C2MEM-031 r1's shape, synthetic: a balloon dilation no code depends on, whose own time is worded as the index
        colonoscopy's (current_unanchored, D54), beside a 2024 denial of dilation - an UNRESOLVED(time) relation whose
        statement is a denial - and the prior-segment denial that makes 45385 ask statement_scope."""
        lines = {'P3': PRIOR, 'P4': self.DILATION, 'P5': self.ASIDE, 'P6': self.HISTORY}
        dilation = act('E4', 'P4', 'dilation', 'balloon', status_words='was inflated sequentially',
                       technique=a('balloon', 'balloon', ['P4']), time=a('current_encounter', self.ASIDE, ['P5']))
        history = act('E5', 'P6', 'dilation', 'dilation', status='not_performed',
                      status_words='No dilation was carried out', scope=sc('all_of_kind', 'No dilation', ['P6']),
                      time=a('earlier_encounter', 'in 2024', ['P6']), performer=a('unknown'))
        return colonoscopy(prior_segment_denial(), dilation, history, lines=lines)

    def test_d86_the_service_question_about_an_event_no_code_depends_on_keeps_its_attribute(self):
        inv, text = self.in_doubt_dilation()
        self.assertIn(('E5', 'E4', 'time', 'time_unresolved', 'not_performed'), unresolved(inv))
        reading = events.Reading.of(inv)
        self.assertEqual(events.focus_question(reading, reading.events['E4']).fact, 'event_time')
        result = run(inv, text, [('45385', POLYP)])
        self.assertEqual(asked(proposal(result, '45385')), ['statement_scope'])
        # the dilation's own question stays asked: moved to statement_scope, it would share (family, fact) with
        # 45385's question, and coverage.in_doubt_questions asks one question per (family, fact)
        service = [(item.scope, item.fact) for item in result.clarifications
                   if item.question.endswith('(“was inflated sequentially”) done at this encounter?')]
        self.assertEqual(service, [('service', 'event_time')])
