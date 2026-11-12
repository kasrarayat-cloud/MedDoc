"""The peer review (HARNESS.md 11.1, 12.8; I5 for phase 1, I6, I7): build_peer_request's exact body for Astra and
Fable - the participant's own frozen reading, the frozen peer conclusions and CPT Studio's labelled rule-based reading
with the question ids and the frozen inputs' sha256, no original file and nothing else of CPT Studio's - the shapes it
refuses; and read_peer: a good review, the refused, truncated, other-model and fallback answers, schema breaches,
bounds, question ids the request did not list, and the references checked against the run's own tool results. Fable's
harness-3 peer review carries no output format and its answer is read only when it is exactly one JSON object (alone or
alone in one json code fence); its stored harness@2 peer reviews are read exactly as before. Offline and synthetic
(test_participants_support)."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json

from studio.participants import anthropic_fable, openai_astra, peer, peer_reader_for, prompt, reading, registry
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.participants.replay import ReplayParticipant
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256
from studio.types import PageSpan, ParticipantReading, ProviderRequest, from_jsonable, sha256_json, to_jsonable

from tests.test_participants_support import (NOTE, ORIGINAL, PAGE_BREAK, PAGES, OfflineTestCase, astra_envelope,
                                             astra_with, changed, fable_envelope, fable_harness_2, fable_harness_3,
                                             fable_with, fixture_bytes, fixture_reading)

CORTI = {'selected': [{'code': '45385', 'evidence': ['was removed with a cold snare']}]}
CORTI_SHA256 = hashlib.sha256(b'synthetic corti response bytes').hexdigest()
CPT_STUDIO = {
    'open_questions': [
        {'question_id': 'clar-extent-0001', 'scope': 'service', 'fact': 'extent', 'family': 'colonoscopy',
         'proposal_key': '', 'question': 'How far was the colonoscope advanced?',
         'reason': 'No landmark was read for the extent.'},
        {'question_id': 'clar-date-0002', 'scope': 'encounter', 'fact': 'service_date', 'family': '',
         'proposal_key': '', 'question': 'What is the date of service?', 'reason': 'No date was read.'}],
    'held': [{'code': '45385', 'reason': 'Held until the extent is settled.'}],
    'excluded': [{'code': '45380', 'reason': 'Bundled into the snare removal.'}],
}
GOOD = {
    'question_answers': [
        {'question_id': 'clar-extent-0001', 'settled': True, 'value': 'cecum',
         'evidence': ['The colonoscope was advanced to the cecum.']},
        {'question_id': 'clar-date-0002', 'settled': False, 'value': '', 'evidence': []}],
    'code_positions': [{'code': '45380', 'position': 'supports', 'reason': 'A separate polyp was biopsied.',
                        'evidence': ['A 3 mm polyp in the rectum was biopsied with cold forceps.']}],
    'additional_codes': [],
    'references_used': [{'ref': 'ncci-2026-ch6-c-1', 'use': 'Surgical endoscopy includes diagnostic endoscopy.'},
                        {'ref': 'fact:cms-pfs-rvu26d:45385:mult_proc', 'use': 'The endoscopic base.'}],
}
# The protected constants of prompt.py, pinned at the harness@2 contract commit (7c79270cd): this package adds to
# prompt.py and changes none of them - but PEER_INSTRUCTIONS, reworded by refutation round 1's IND-4 repair (the own
# reading is shown as CPT Studio recorded it, not "unchanged"). Every peer request carries it, so a stored peer request
# of the earlier wording is refused by its reader as one this adapter does not build, never misread (part B is not
# installed: no such request was stored by an installation); PEER_VERSION names the output schema, which is unchanged.
PROTECTED = {
    'INSTRUCTIONS': '9b0d4edd857842565df4f3a5526139d04067de299d6c6b9872e6e873505f4ce9',
    'SCHEMA': '41ca6eeed2e58bcb1455f9c4a178af8c08098ed286abb0bffc01beed0feb129a',
    'TOOLS': '14e5b23965544a2eef07c7017ccba0dc21e988a74a07ce9afa386e86b94b1904',
    'PEER_INSTRUCTIONS': 'ec283b2eac90d9e2538b2df2008314e7e9d58a4949e819c7bf89823444d8887a',
    'PEER_SCHEMA': 'fe7c3b2ff866e3d35e8014df47a0fe6cbdca6b2cf2b7d79ef7f91c96049473ec',
    'KINDS': '934c56c6134aedf377765687cf2d002ea386d0dc040396011f8040ef7d280b2c',
    'READING_VERSION': '8286b50746226dd0b0a0f8f4f836a59a5cce209ca2233adf0d5a9d18e6542443',
    'PEER_VERSION': 'faec9eefdfb3531039110b0289b1a0c825243d7d65f68c24b359ee189b62d167',
    'PEER_SCHEMA_NAME': '705cd272b78a150e74163c6fbd7f5a9c93547a1431597dd8fced82485916ecd1',
}


def peer_answer(**fields) -> dict:
    answer = copy.deepcopy(GOOD)
    answer.update(fields)
    return answer


def framed_peer() -> str:
    return '\n'.join([
        'Document: a PDF; only its extracted text is given for this review.',
        'Its extracted text follows between the two marker lines. The [Page N] lines mark where each page begins and '
        'are not part of the text.',
        f'<<<{prompt.marker(NOTE)} BEGIN>>>', '[Page 1]', NOTE[:PAGE_BREAK], '[Page 2]', NOTE[PAGE_BREAK:],
        f'<<<{prompt.marker(NOTE)} END>>>'])


class _PeerContract:
    module = None
    adapter_class = None
    other_class = None
    fixture = ''
    other_fixture = ''

    def setUp(self):
        super().setUp()
        self.adapter = self.adapter_class(self.tmp / 'never-read.env')
        other = self.other_class(self.tmp / 'never-read.env')
        self.own = self.adapter.read(self.adapter.build_request(NOTE, PAGES, 'pdf', ORIGINAL),
                                     fixture_bytes(self.fixture))
        self.other = other.read(other.build_request(NOTE, PAGES, 'pdf', ORIGINAL), fixture_bytes(self.other_fixture))
        self.assertFalse(self.own.refused or self.other.refused)
        self.peers = {'corti': copy.deepcopy(CORTI), other.name: prompt.reading_answer(self.other)}
        self.frozen = self.frozen_for(self.own, self.peers)
        self.request = self.build()

    def frozen_for(self, own, peers, cpt_studio=CPT_STUDIO):
        """The frozen list of exactly what a request shows (HARNESS.md 12.3-12.4; IND-5): the own reading under its
        name, each peer shown (Corti's response bytes, the other model's reading), the revision text and CPT Studio's
        reading, as the pipeline records them."""
        known = {'corti': CORTI_SHA256, self.other.provider: sha256_json(self.other)}
        frozen = [(own.provider, sha256_json(own)), ('revision', hashlib.sha256(NOTE.encode()).hexdigest())]
        frozen += [(name, known.get(name, '0' * 64)) for name in peers]
        try:
            frozen.append(('cpt_studio', sha256_json(cpt_studio)))
        except (TypeError, ValueError):  # a shape the builder refuses before it reads the frozen list
            frozen.append(('cpt_studio', '0' * 64))
        return frozen

    def build(self, **changes):
        arguments = {'text': NOTE, 'pages': PAGES, 'kind': 'pdf', 'own': self.own, 'peers': self.peers,
                     'cpt_studio': copy.deepcopy(CPT_STUDIO)}
        arguments.update(changes)
        if 'frozen' not in changes:
            peers = arguments['peers'] if isinstance(arguments['peers'], dict) else {}
            arguments['frozen'] = self.frozen_for(self.own, peers, arguments['cpt_studio'])
        return self.adapter.build_peer_request(**arguments)

    def document(self, request=None):
        return self.content(request or self.request)[1]['text']

    def answer(self, value, **fields) -> bytes:
        raise NotImplementedError

    def read(self, raw, request=None, refs=frozenset()):
        return self.adapter.read_peer(request or self.request, raw, refs)

    # --- the request --------------------------------------------------------------------

    def test_the_body_is_exactly_the_contract(self):
        document = prompt.peer_document(self.own, self.peers, CPT_STUDIO, self.frozen)
        self.assertEqual(self.request.body, self.expected_body(framed_peer(), document))
        self.assertEqual((self.request.provider, self.request.adapter_version, self.request.contexts),
                         (self.module.NAME, self.module.ADAPTER_VERSION, (NOTE,)))
        self.assertEqual(self.request.canonical_sha256, hashlib.sha256(canonical_body(self.request.body)).hexdigest())

    def test_no_original_file_is_attached_and_the_framing_says_so(self):
        encoded = canonical_body(self.request.body).decode()
        self.assertNotIn('$original_sha256', encoded)
        self.assertNotIn(ORIGINAL['sha256'], encoded)
        framed = self.content(self.request)[0]['text']
        first = prompt.framed_document(NOTE, PAGES, 'pdf')
        self.assertTrue(first.startswith('Document: a PDF; the original file is attached'))
        self.assertEqual(framed.split('\n', 1)[1], first.split('\n', 1)[1])  # every other line is phase 1's framing
        self.assertEqual(framed.split('\n', 1)[0], 'Document: a PDF; only its extracted text is given for this review.')
        for kind in ('docx', 'paste', 'txt', 'addendum'):
            with self.subTest(kind=kind):
                self.assertEqual(prompt.peer_framed_document(NOTE, PAGES, kind), prompt.framed_document(NOTE, PAGES,
                                                                                                         kind))

    def test_the_document_labels_each_section_and_lists_the_question_ids_and_frozen_inputs(self):
        lines = self.document().split('\n')
        own = lines.index('== Your frozen first reading ==')
        peers = lines.index('== Frozen peer conclusions - not authoritative ==')
        studio = lines.index("== CPT Studio's rule-based reading - it can be wrong ==")
        self.assertLess(own, peers)
        self.assertLess(peers, studio)
        self.assertEqual(json.loads(lines[own + 1]), prompt.reading_answer(self.own))
        other = self.other_class.name
        shown = {'corti': ['corti (another coding system):', json.dumps(CORTI, sort_keys=True, separators=(',', ':'))],
                 other: [f'{other} (another model):', json.dumps(self.peers[other], sort_keys=True,
                                                                 separators=(',', ':'), ensure_ascii=False)]}
        self.assertEqual(lines[peers + 1:peers + 5], [line for name in sorted(shown) for line in shown[name]])
        self.assertEqual(json.loads(lines[studio + 1]), CPT_STUDIO)
        self.assertEqual(lines[-5:], [
            '== question_ids ==', '["clar-extent-0001","clar-date-0002"]', '',
            '== Frozen inputs: the sha256 of each frozen output shown above ==',
            json.dumps(sorted([list(pair) for pair in self.frozen]), separators=(',', ':'))])
        self.assertEqual(prompt.peer_document_inputs(self.document()),
                         (('clar-extent-0001', 'clar-date-0002'), tuple(sorted(self.frozen))))
        for sha256 in (sha256_json(self.own), sha256_json(self.other), CORTI_SHA256):
            self.assertIn(sha256, self.document())

    def test_nothing_else_of_cpt_studios_is_sent(self):
        """Outside the fixed schema and tools, every string in the body is the peer instructions, the framed text, the
        peer document or a fixed label; and the document carries the participant's own words, the peers' conclusions
        as given and CPT Studio's labelled reading - none of CPT Studio's checks of any reading."""
        labels = {'gpt-6-astra', 'claude-fable-5-1', 'user', 'input_text', 'json_schema', 'gi_encounter_peer_review',
                  'medium', 'text', 'auto', 'reasoning.encrypted_content'}
        body = copy.deepcopy(self.request.body)
        if self.module is openai_astra:
            self.assertEqual(body['text']['format'].pop('schema'), prompt.PEER_SCHEMA)
            instructions = prompt.PEER_INSTRUCTIONS
        else:  # no format: the peer schema is fixed text in Fable's system prompt (HARNESS.md 12.8)
            self.assertEqual(body['output_config'], {'effort': 'medium'})
            instructions = (prompt.PEER_INSTRUCTIONS + prompt.schema_instruction(prompt.PEER_SCHEMA)
                            + prompt.fields_instruction())  # harness-4 (F-CONTRACT)
        self.assertEqual(body.pop('tools'), self.module.tools())
        strings, pending = [], [body]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
            elif isinstance(node, str):
                strings.append(node)
        self.assertEqual(set(strings) - labels, {instructions, framed_peer(), self.document()})
        lines = self.document().split('\n')
        sections = [json.loads(line) for line in lines if line.startswith(('{', '['))]
        self.assertEqual(sections, [prompt.reading_answer(self.own), *(self.peers[name] for name in sorted(self.peers)),
                                    CPT_STUDIO, ['clar-extent-0001', 'clar-date-0002'],
                                    [list(pair) for pair in sorted(self.frozen)]])
        own_text = json.dumps(sections[0])
        for checked in ('"spans"', '"problems"', '"unverified_quotes"', '"refused"', '"reason"', '"exact"',
                        '"adapter_version"', '"provider"', '"retrieved"'):
            self.assertNotIn(checked, own_text)

    def test_the_own_reading_is_shown_as_the_participant_answered_it(self):
        shown = prompt.reading_answer(self.own)
        self.assertEqual(reading.schema_error(shown), '')
        self.assertEqual(shown, fixture_reading())  # the fixture's own answer, nothing added or dropped

    def test_a_reloaded_frozen_reading_is_the_same_frozen_input(self):
        reloaded = from_jsonable(ParticipantReading, json.loads(json.dumps(to_jsonable(self.own))))
        self.assertEqual(reloaded, self.own)
        self.assertEqual(sha256_json(reloaded), sha256_json(self.own))
        self.assertEqual(self.build(own=reloaded).canonical_sha256, self.request.canonical_sha256)

    def test_the_request_is_deterministic_and_independent_of_input_order(self):
        reordered_peers = dict(reversed(list(self.peers.items())))
        again = self.build(peers=reordered_peers, frozen=list(reversed(self.frozen)))
        self.assertEqual((again.body, again.canonical_sha256), (self.request.body, self.request.canonical_sha256))
        moved = self.build(cpt_studio=dict(CPT_STUDIO, open_questions=list(reversed(CPT_STUDIO['open_questions']))))
        self.assertNotEqual(moved.canonical_sha256, self.request.canonical_sha256)  # question order is as given

    def test_a_review_with_no_peer_conclusion_says_so(self):
        request = self.build(peers={})
        lines = self.document(request).split('\n')
        index = lines.index('== Frozen peer conclusions - not authoritative ==')
        self.assertEqual(lines[index + 1], '(no peer conclusion was recorded)')

    def test_inputs_that_are_not_the_documented_shapes_are_refused(self):
        other = self.other_class.name
        refused = ParticipantReading(**dict(vars(self.own), refused=True))
        foreign = ParticipantReading(**dict(vars(self.own), provider=other))
        question = CPT_STUDIO['open_questions'][0]
        cases = {
            'a refused first reading': ({'own': refused}, ValueError),
            "another participant's reading": ({'own': foreign}, ValueError),
            'a reading that is not one': ({'own': to_jsonable(self.own)}, TypeError),
            'an own reading not among the frozen inputs': ({'frozen': [('corti', CORTI_SHA256)]}, ValueError),
            "Corti's display text": ({'peers': {'corti': {'selected': [{'code': '45385', 'display': 'x'}]}}},
                                     ValueError),
            'a provider_display field': ({'peers': {other: {'items': [[{'provider_display': 'x'}]]}}}, ValueError),
            'the participant as its own peer': ({'peers': {self.module.NAME: {}}}, ValueError),
            'an unknown peer': ({'peers': {'gpt': {}}}, ValueError),
            'a peer that is not a dict': ({'peers': {'corti': ['45385']}}, TypeError),
            'peers that are not a dict': ({'peers': [('corti', CORTI)]}, TypeError),
            'a peer that is not JSON': ({'peers': {'corti': {'score': float('nan')}}}, ValueError),
            'an extra CPT Studio key': ({'cpt_studio': dict(CPT_STUDIO, routing={})}, ValueError),
            'a question missing a field': ({'cpt_studio': dict(CPT_STUDIO, open_questions=[
                {key: value for key, value in question.items() if key != 'reason'}])}, ValueError),
            'a question field that is not text': ({'cpt_studio': dict(CPT_STUDIO, open_questions=[
                dict(question, family=None)])}, ValueError),
            'a question id with a space': ({'cpt_studio': dict(CPT_STUDIO, open_questions=[
                dict(question, question_id='clar extent')])}, ValueError),
            'two questions with one id': ({'cpt_studio': dict(CPT_STUDIO, open_questions=[question, question])},
                                          ValueError),
            'held codes that are not objects': ({'cpt_studio': dict(CPT_STUDIO, held=['45385'])}, ValueError),
            'a display field in CPT Studio\'s codes': ({'cpt_studio': dict(CPT_STUDIO, excluded=[
                {'code': '45380', 'provider_display': 'x'}])}, ValueError),
            'a frozen sha256 that is not one': ({'frozen': self.frozen + [('x', 'ABC')]}, ValueError),
            'two frozen inputs with one name': ({'frozen': self.frozen + [(self.frozen[0][0], CORTI_SHA256)]},
                                                ValueError),
            'no frozen input': ({'frozen': []}, ValueError),
            'frozen inputs that are not pairs': ({'frozen': 'corti'}, TypeError),
            'a frozen input that is not a pair': ({'frozen': self.frozen + [('only-a-name',)]}, TypeError),
        }
        for label, (changes, error) in cases.items():
            with self.subTest(label), self.assertRaises(error):
                self.build(**changes)

    def test_the_frozen_inputs_name_exactly_what_the_request_shows(self):
        # Refutation round 1, IND-5: the stored list heads "the sha256 of each frozen output shown above", so it may
        # list no input that is not shown, must list every one that is, and never files the own reading under another
        # name
        other, own = self.other.provider, self.own.provider
        with_peers = self.frozen_for(self.own, self.peers)
        cases = {
            'peers listed that are not shown': ({'peers': {}, 'frozen': with_peers},
                                                f'listed but not shown: {", ".join(sorted(["corti", other]))}'),
            'a peer shown that is not listed': ({'frozen': [pair for pair in with_peers if pair[0] != other]},
                                                f'not listed: {other}'),
            "the own reading's sha256 under another's name": (
                {'peers': {}, 'frozen': [(other, sha256_json(self.own)), *[
                    pair for pair in self.frozen_for(self.own, {}) if pair[0] != own]]},
                f'not listed: {own}; listed but not shown: {other}'),
            'an own reading that is not the one shown': ({'frozen': [(own, sha256_json(self.other)), *[
                pair for pair in with_peers if pair[0] != own]]}, f'shows for {own}'),
            'a text that is not the one shown': ({'frozen': [('revision', '1' * 64), *[
                pair for pair in with_peers if pair[0] != 'revision']]}, 'shows for revision'),
            "a CPT Studio reading that is not the one shown": ({'frozen': [('cpt_studio', '1' * 64), *[
                pair for pair in with_peers if pair[0] != 'cpt_studio']]}, 'shows for cpt_studio'),
        }
        for label, (changes, message) in cases.items():
            with self.subTest(label), self.assertRaisesMessage(ValueError, message):
                self.build(**changes)
        # what is shown, and only that, is what the review records
        alone = self.build(peers={})
        self.assertEqual([name for name, _ in prompt.peer_document_inputs(self.document(alone))[1]],
                         sorted([own, 'revision', 'cpt_studio']))

    def test_content_that_cannot_be_sent_is_unavailable(self):
        cases = {'pages that leave a gap': {'pages': (PageSpan(1, 0, 10), PageSpan(2, 11, len(NOTE)))},
                 'an empty text': {'text': '  '},
                 'a lone surrogate in a peer': {'peers': {'corti': {'selected': [{'code': '\ud800'}]}}}}
        for label, changes in cases.items():
            with self.subTest(label), self.assertRaises(ProviderUnavailable):
                self.build(**changes)
        size = len(canonical_body(self.request.body))
        tight = self.adapter_class(self.tmp / 'x.env', max_request_bytes=size - 1)
        with self.assertRaises(ProviderUnavailable) as caught:
            tight.build_peer_request(NOTE, PAGES, 'pdf', self.own, self.peers, CPT_STUDIO, self.frozen)
        self.assertIn(f'would be {size:,} bytes, over the {size - 1:,}-byte limit; nothing was truncated or sent',
                      str(caught.exception))
        self.adapter_class(self.tmp / 'x.env', max_request_bytes=size).build_peer_request(
            NOTE, PAGES, 'pdf', self.own, self.peers, CPT_STUDIO, self.frozen)

    def test_the_replay_adapter_builds_the_live_request(self):
        replay = ReplayParticipant(self.module.NAME, self.tmp)
        replayed = replay.build_peer_request(NOTE, PAGES, 'pdf', self.own, self.peers, CPT_STUDIO, self.frozen)
        self.assertEqual((replayed.body, replayed.canonical_sha256), (self.request.body, self.request.canonical_sha256))
        raw = self.answer(GOOD)
        self.assertEqual(replay.read_peer(replayed, raw), self.read(raw))

    # --- the answer -------------------------------------------------------------------------

    def test_a_good_review_is_read_with_its_quotes_located_and_its_references_checked(self):
        review = self.read(self.answer(GOOD), refs={'ncci-2026-ch6-c-1', 'fact:cms-other:1:status'})
        self.assertEqual((review.refused, review.problems, review.unverified_quotes), (False, (), 0))
        self.assertEqual((review.provider, review.adapter_version, review.review_version, review.requested_model,
                          review.returned_model),
                         (self.module.NAME, self.module.ADAPTER_VERSION, 'harness-peer@1', self.module.MODEL,
                          self.module.MODEL))
        self.assertEqual(review.frozen_inputs, tuple(sorted(self.frozen)))
        extent, date = review.answers
        self.assertEqual((extent.question_id, extent.settled, extent.value), ('clar-extent-0001', True, 'cecum'))
        (span,) = extent.evidence[0].spans
        self.assertEqual((NOTE[span.start:span.end], span.exact), (span.text, True))
        self.assertEqual((date.question_id, date.settled, date.value, date.evidence), ('clar-date-0002', False, '', ()))
        (position,) = review.positions
        self.assertEqual((position.code, position.position), ('45380', 'supports'))
        self.assertTrue(position.evidence[0].spans)
        self.assertEqual([(item.ref, item.retrieved) for item in review.references_used],
                         [('ncci-2026-ch6-c-1', True), ('fact:cms-pfs-rvu26d:45385:mult_proc', False)])
        self.assertEqual([item.retrieved for item in self.read(self.answer(GOOD)).references_used], [False, False])

    def test_a_code_added_after_peer_review_is_read_as_a_code(self):
        added = {'code': '45378', 'modifiers': [], 'units': 1, 'service_ids': ['s1'], 'basis': 'Synthetic basis.',
                 'evidence': ['The colonoscope was advanced to the cecum.'], 'confidence': 'low'}
        review = self.read(self.answer(peer_answer(additional_codes=[
            added, dict(added, code='4537', units=2), dict(added, code='45379', units=0)])))
        self.assertEqual([(code.code, code.units) for code in review.additional_codes], [('45378', 1), ('4537', 2)])
        self.assertEqual(review.problems, (
            "additional_codes[1] ('4537') is not a five-character CPT code; it is kept as given.",
            "additional_codes[2] ('45379') gives 0 units, outside 1 to 99; it was dropped."))

    def test_question_ids_the_request_did_not_list_are_dropped_and_non_answers_never_carry_a_value(self):
        answers = [
            {'question_id': 'clar-invented-9999', 'settled': True, 'value': 'cecum', 'evidence': []},
            {'question_id': 'clar-extent-0001', 'settled': True, 'value': '  ', 'evidence': []},
            {'question_id': 'clar-extent-0001', 'settled': False, 'value': 'terminal ileum', 'evidence': []},
            {'question_id': 'clar-date-0002', 'settled': True, 'value': '2026-10-21',
             'evidence': ['Date of service: 2026-10-21', 'not in the document at all, verbatim', 'short']},
        ]
        review = self.read(self.answer(peer_answer(question_answers=answers)))
        self.assertFalse(review.refused)
        self.assertEqual([(item.question_id, item.settled, item.value) for item in review.answers],
                         [('clar-extent-0001', False, ''), ('clar-extent-0001', False, ''),
                          ('clar-date-0002', True, '2026-10-21')])
        # a model-written id is quoted in a problem only in a strict shape (a real question id is a clarification's
        # UUID); these hand-written ids are named by their length (refutation round 3; the pin moved from quoting them)
        self.assertEqual(review.problems, (
            'question_answers[0] answers a question id the request did not list (a value of 18 characters); it was '
            'dropped.',
            'question_answers[1] says the document settles a value of 16 characters but gives no value; it is read as '
            'not settled.',
            'question_answers[2] answers a value of 16 characters again.',
            'question_answers[2] says the document does not settle a value of 16 characters but gives a value; the '
            'value was not kept.'))
        quotes = review.answers[2].evidence
        self.assertEqual([(bool(item.spans), item.reason) for item in quotes],
                         [(True, ''), (False, 'not found'), (False, 'too short')])
        self.assertEqual(review.unverified_quotes, 2)

    # Whether a field outside the peer schema refuses the review whole: a constrained answer's (Astra's) does; a
    # harness-4 Fable answer's is set aside instead (HARNESS.md, "Harness repair 3", F-CONTRACT; FablePeerTests)
    extra_field_refuses = True

    def test_schema_breaches_refuse_the_review_whole(self):
        position = GOOD['code_positions'][0]
        cases = {
            'a missing field': ({key: value for key, value in GOOD.items() if key != 'references_used'},
                                "the peer review lacks the required field 'references_used'"),
            'an extra field': (peer_answer(summary='x'), "the peer review has a field the schema does not allow"),
            'a missing field beside an extra one': (
                dict({key: value for key, value in GOOD.items() if key != 'references_used'}, summary=''),
                "the peer review has a field the schema does not allow" if self.extra_field_refuses
                else "the peer review lacks the required field 'references_used'"),
            'settled that is not true or false': (peer_answer(question_answers=[
                dict(GOOD['question_answers'][0], settled='yes')]), 'question_answers[0].settled is not true or false'),
            'settled as a number': (peer_answer(question_answers=[dict(GOOD['question_answers'][0], settled=1)]),
                                    'question_answers[0].settled is not true or false'),
            'a position the schema does not allow': (peer_answer(code_positions=[dict(position, position='maybe')]),
                                                     'code_positions[0].position is not one of the values'),
            'positions that are not a list': (peer_answer(code_positions={}), 'code_positions is not a list'),
        }
        if not self.extra_field_refuses:
            del cases['an extra field']
        for label, (value, expect) in cases.items():
            with self.subTest(label):
                review = self.read(self.answer(value))
                self.assertTrue(review.refused)
                self.assertEqual((review.answers, review.positions, review.additional_codes), ((), (), ()))
                self.assertIn(f'The peer review was not used: the answer breaks the peer-review schema: {expect}',
                              review.problems[0])
                self.assertEqual(review.frozen_inputs, tuple(sorted(self.frozen)))  # what was shown stays on record
        review = self.read(self.answer([]))  # an answer that is not an object at all
        self.assertTrue(review.refused)
        self.assertEqual(review.problems, (f'The peer review was not used: {self.not_an_object}.',))
        self.assertEqual(review.frozen_inputs, tuple(sorted(self.frozen)))
        review = self.read(self.answer('{"question_answers": [], "question_answers": []}'))
        self.assertIn('repeats a JSON object key', review.problems[0])

    def test_bounds_refuse_the_review_whole(self):
        answer = GOOD['question_answers'][0]
        position = GOOD['code_positions'][0]
        code = {'code': '45378', 'modifiers': [], 'units': 1, 'service_ids': [], 'basis': '', 'evidence': [],
                'confidence': 'low'}
        cases = {
            'it lists 65 question answers, more than the 64 this adapter accepts':
                peer_answer(question_answers=[answer] * 65),
            'it lists 129 code positions, more than the 128 this adapter accepts':
                peer_answer(code_positions=[position] * 129),
            'it lists 65 additional codes, more than the 64 this adapter accepts':
                peer_answer(additional_codes=[code] * 65),
            'it lists 65 references used, more than the 64 this adapter accepts':
                peer_answer(references_used=[GOOD['references_used'][0]] * 65),
            'question_answers[0].evidence lists 17 quotes, more than the 16': peer_answer(question_answers=[
                dict(answer, evidence=['The colonoscope was advanced to the cecum.'] * 17)]),
            'code_positions[0].evidence[0] has 601 characters, more than the 600': peer_answer(code_positions=[
                dict(position, evidence=['x' * 601])]),
            'code_positions[0].reason has 2,001 characters, more than the 2,000': peer_answer(code_positions=[
                dict(position, reason='x' * 2001)]),
        }
        for expect, value in cases.items():
            with self.subTest(expect):
                review = self.read(self.answer(value))
                self.assertTrue(review.refused)
                self.assertTrue(review.problems[0].startswith('The peer review was not used: '), review.problems)
                self.assertIn(expect, review.problems[0])
        self.assertFalse(self.read(self.answer(peer_answer(code_positions=[position] * 128))).refused)

    def test_a_request_that_is_not_this_adapters_peer_review_is_refused(self):
        phase_one = self.adapter.build_request(NOTE, PAGES, 'paste', None)
        altered = copy.deepcopy(self.request)
        self.content(altered)[1]['text'] += '\nappended'
        rehashed = ProviderRequest(provider=altered.provider, adapter_version=altered.adapter_version,
                                   body=altered.body, canonical_sha256=request_sha256(altered.body),
                                   contexts=altered.contexts)
        older = ProviderRequest(provider=self.request.provider, adapter_version=self.module.ADAPTER_VERSION_1,
                                body=self.request.body, canonical_sha256=self.request.canonical_sha256,
                                contexts=self.request.contexts)
        other = self.other_class(self.tmp / 'x.env')
        foreign = other.build_peer_request(NOTE, PAGES, 'pdf', self.other, {'corti': CORTI}, CPT_STUDIO,
                                           self.frozen_for(self.other, {'corti': CORTI}))
        cases = ((phase_one, 'the request is not a peer review this adapter builds'),
                 (altered, 'the request does not match its recorded hash'),
                 (rehashed, 'the request is not a peer review this adapter builds'),
                 (older, f"with adapter {self.module.ADAPTER_VERSION_1!r}, not {self.module.NAME!r} with "
                         f"{self.module.ADAPTER_VERSION!r}"),
                 (foreign, f'it was recorded for {other.name!r}'))
        for request, expect in cases:
            with self.subTest(expect=expect):
                review = self.read(self.answer(GOOD), request)
                self.assertTrue(review.refused)
                self.assertIn(expect, review.problems[0])
                self.assertEqual((review.answers, review.frozen_inputs), ((), ()))

    def test_a_peer_review_run_is_read_only_by_the_peer_reader(self):
        self.assertIs(registry.peer_reader(self.module.NAME, self.module.ADAPTER_VERSION), self.module.read_peer)
        self.assertIs(peer_reader_for(self.module.NAME, self.module.ADAPTER_VERSION), self.module.read_peer)
        for provider, version in ((self.module.NAME, self.module.ADAPTER_VERSION_1), ('corti', 'x'),
                                  (self.module.NAME, None), ([self.module.NAME], self.module.ADAPTER_VERSION)):
            with self.subTest(provider=provider, version=version), self.assertRaises(ProviderUnavailable):
                registry.peer_reader(provider, version)
        review = self.module.read_response(self.request, self.answer(GOOD))  # a first-reading reader never takes it
        self.assertTrue(review.refused)
        self.assertIn('breaks the reading schema', review.problems[0])

    def test_a_string_of_refs_is_a_programming_error(self):
        with self.assertRaises(TypeError):
            self.read(self.answer(GOOD), refs='ncci-2026-ch6-c-1')


class AstraPeerTests(_PeerContract, OfflineTestCase):
    module = openai_astra
    adapter_class = AstraParticipant
    other_class = FableParticipant
    fixture = 'astra-colonoscopy.response.json'
    other_fixture = 'fable-colonoscopy.response.json'
    not_an_object = 'the answer breaks the peer-review schema: the peer review is not an object'

    @staticmethod
    def content(request):
        return request.body['input'][0]['content']

    def expected_body(self, framed, document):
        return {
            'model': 'gpt-6-astra',
            'instructions': prompt.PEER_INSTRUCTIONS,
            'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': framed},
                                                   {'type': 'input_text', 'text': document}]}],
            'text': {'format': {'type': 'json_schema', 'name': 'gi_encounter_peer_review', 'schema': prompt.PEER_SCHEMA,
                                'strict': True}},
            'reasoning': {'effort': 'medium'},
            'max_output_tokens': 16000,
            'store': False,
            'tools': openai_astra.tools(),
            'tool_choice': 'auto',
            'include': ['reasoning.encrypted_content'],
        }

    def answer(self, value, **fields):
        return astra_with(value, **fields)

    def test_refused_truncated_other_model_and_tool_asking_answers_are_refused_whole(self):
        refusal = astra_envelope()
        refusal['output'][1]['content'] = [{'type': 'refusal', 'refusal': 'Synthetic refusal.'}]
        asking = astra_envelope()
        asking['output'].append({'type': 'function_call', 'id': 'fc_x', 'call_id': 'call_x', 'name': 'cms_code_facts',
                                 'arguments': '{}', 'status': 'completed'})
        asking['output'][1]['content'][0]['text'] = json.dumps(GOOD)
        cases = {
            # the model's own words are named by their length, never repeated (refutation round 1, IND-2)
            'the model refused (its message, 18 characters, is not repeated)': json.dumps(refusal).encode(),
            'the response was cut off at the output limit': self.answer(GOOD, status='incomplete',
                                                                        incomplete_details={'reason':
                                                                                            'max_output_tokens'}),
            "it names model 'gpt-6-astra-mini' as the model that answered, not gpt-6-astra":
                self.answer(GOOD, model='gpt-6-astra-mini'),
            'the response still asks for tool calls, so it is not a final answer': json.dumps(asking).encode(),
        }
        for expect, raw in cases.items():
            with self.subTest(expect):
                review = self.read(raw)
                self.assertTrue(review.refused)
                self.assertEqual(review.problems, (f'The peer review was not used: {expect}' +
                                                   ('' if expect.endswith('.') else '.'),))
                self.assertEqual(review.frozen_inputs, tuple(sorted(self.frozen)))


class FablePeerTests(_PeerContract, OfflineTestCase):
    module = anthropic_fable
    adapter_class = FableParticipant
    other_class = AstraParticipant
    fixture = 'fable-colonoscopy.response.json'
    other_fixture = 'astra-colonoscopy.response.json'
    not_an_object = reading.NOT_ONE_OBJECT  # harness-3: an array is not exactly one JSON object (HARNESS.md 12.8)

    @staticmethod
    def content(request):
        return request.body['messages'][0]['content']

    def expected_body(self, framed, document):
        return {
            'model': 'claude-fable-5-1',
            'max_tokens': 16000,
            'system': (prompt.PEER_INSTRUCTIONS + prompt.schema_instruction(prompt.PEER_SCHEMA)
                       + prompt.fields_instruction()),  # harness-4 (F-CONTRACT)
            'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': framed},
                                                      {'type': 'text', 'text': document}]}],
            'output_config': {'effort': 'medium'},  # no format: Anthropic's grammar limit (HARNESS.md 12.8)
            'tools': anthropic_fable.tools(),
            'tool_choice': {'type': 'auto'},
        }

    extra_field_refuses = False  # harness-4 sets it aside (F-CONTRACT)

    # --- harness-4 (as harness-3): an answer nothing at Anthropic constrained (HARNESS.md 12.8) -----------------------

    def test_an_answer_alone_in_a_single_fence_is_read_as_the_bare_one(self):
        bare = self.read(self.answer(GOOD), refs={'ncci-2026-ch6-c-1'})
        self.assertEqual((bare.refused, bare.problems, bare.adapter_version),
                         (False, (), 'anthropic-messages@cptstudio-harness-4'))
        for text in (f'```json\n{json.dumps(GOOD)}\n```', f'```\n{json.dumps(GOOD, indent=2)}\n```',
                     f'\n {json.dumps(GOOD)} \n'):
            with self.subTest(text=text[:10]):
                self.assertEqual(self.read(self.answer(text), refs={'ncci-2026-ch6-c-1'}), bare)

    def test_anything_but_one_object_is_refused_whole_and_what_was_shown_stays_on_record(self):
        good = json.dumps(GOOD)
        for text in (f'SYNTHETIC-MODEL-PROSE-0002 {good}', f'{good}\nSYNTHETIC-MODEL-PROSE-0002',
                     f'```js\n{good}\n```', f'```json\n{good}\n```\nSYNTHETIC-MODEL-PROSE-0002', good[:-30], ''):
            with self.subTest(text=text[:12]):
                review = self.read(self.answer(text))
                self.assertEqual(review.problems, (f'The peer review was not used: {reading.NOT_ONE_OBJECT}.',))
                self.assertEqual((review.answers, review.positions, review.additional_codes), ((), (), ()))
                self.assertEqual(review.frozen_inputs, tuple(sorted(self.frozen)))
        for text in (f'{good}\n{good}', f'```json\n{good}\n```\n```json\n{good}\n```'):  # two objects, two fences
            with self.subTest(text=text[-12:]):
                review = self.read(self.answer(text))
                self.assertTrue(review.problems[0].startswith(
                    'The peer review was not used: the answer is not valid JSON ('), review.problems)
                self.assertNotIn('SYNTHETIC-MODEL-PROSE', review.problems[0])
        review = self.read(self.answer(f'```json\n{json.dumps(peer_answer(summary="x"))}\n```'))
        self.assertEqual((review.refused, review.problems), (False, (
            "top-level field 'summary' is outside the schema; it held 3 characters, kept in the raw response, and it "
            'was set aside and not read (an answer nothing constrained, HARNESS.md F-CONTRACT).',)))
        harness_3 = self.harness_3_request()
        review = anthropic_fable.read_peer(harness_3, self.answer(f'```json\n{json.dumps(peer_answer(summary="x"))}'
                                                                  '\n```'))
        self.assertEqual(review.problems, ("The peer review was not used: the answer breaks the peer-review schema: "
                                           "the peer review has a field the schema does not allow ('summary').",))
        review = self.read(self.answer('SYNTHETIC-MODEL-PROSE-0002', stop_reason='refusal',
                                       stop_details={'category': 'cyber'}))  # the vendor's refusal comes first (I6)
        self.assertEqual(review.problems, ('The peer review was not used: the model refused (category cyber).',))

    def harness_3_request(self):
        """The harness-3 peer request for the inputs harness_2_request uses: its stored runs are read as before."""
        _, current = self.harness_2_request()
        body = fable_harness_3(current.body)
        return ProviderRequest(provider='fable', adapter_version=anthropic_fable.ADAPTER_VERSION_3, body=body,
                               canonical_sha256=request_sha256(body), contexts=(NOTE,))

    def test_a_stored_harness_3_peer_review_is_read_exactly_as_before_and_harness_4_sets_extras_aside(self):
        harness_3 = self.harness_3_request()
        _, current = self.harness_2_request()
        self.assertIs(registry.peer_reader('fable', anthropic_fable.ADAPTER_VERSION_3), anthropic_fable.read_peer)
        then = anthropic_fable.read_peer(harness_3, self.answer(GOOD))
        now = anthropic_fable.read_peer(current, self.answer(GOOD))
        self.assertEqual((then.refused, then.adapter_version), (False, anthropic_fable.ADAPTER_VERSION_3))
        self.assertEqual(dataclasses.replace(then, adapter_version=anthropic_fable.ADAPTER_VERSION), now)
        noted = peer_answer(code_positions=[dict(GOOD['code_positions'][0], reason_detail='')])
        self.assertTrue(anthropic_fable.read_peer(harness_3, self.answer(noted)).refused)
        kept = anthropic_fable.read_peer(current, self.answer(noted))
        self.assertFalse(kept.refused)
        self.assertEqual(dataclasses.replace(kept, problems=()), dataclasses.replace(now, problems=()))
        self.assertEqual(len(kept.problems), 1)
        self.assertTrue(kept.problems[0].startswith('code_positions[0] field a value of 13 characters is outside the '
                                                    'schema; it was empty'), kept.problems)

    def harness_2_request(self):
        """The harness@2 adapter's own peer request for fixed inputs (its body's sha256 is pinned in
        test_participants_requests), and the harness-3 request for the same inputs."""
        own = dataclasses.replace(self.own, adapter_version=anthropic_fable.ADAPTER_VERSION_2)
        frozen = [('fable', sha256_json(own)), ('revision', hashlib.sha256(NOTE.encode()).hexdigest()),
                  ('corti', CORTI_SHA256), ('astra', hashlib.sha256(b'synthetic frozen astra reading').hexdigest()),
                  ('cpt_studio', sha256_json(CPT_STUDIO))]
        current = self.adapter.build_peer_request(NOTE, PAGES, 'pdf', own, {'corti': CORTI, 'astra': fixture_reading()},
                                                  CPT_STUDIO, frozen)
        body = fable_harness_2(current.body)
        return ProviderRequest(provider='fable', adapter_version=anthropic_fable.ADAPTER_VERSION_2, body=body,
                               canonical_sha256=request_sha256(body), contexts=(NOTE,)), current

    def test_a_stored_harness_2_peer_review_is_read_exactly_as_before(self):
        older, current = self.harness_2_request()
        self.assertEqual(older.canonical_sha256, 'c5c4278b192df32a27238f5362ceb01a5b9ed03112515f89549f8d023789e92f')
        self.assertIs(registry.peer_reader('fable', anthropic_fable.ADAPTER_VERSION_2), anthropic_fable.read_peer)
        self.assertEqual(anthropic_fable.PEER_READ_VERSIONS, ('anthropic-messages@cptstudio-harness-4',
                                                              'anthropic-messages@cptstudio-harness-3',
                                                              'anthropic-messages@cptstudio-harness-2'))
        review = anthropic_fable.read_peer(older, self.answer(GOOD))
        self.assertEqual((review.refused, review.adapter_version), (False, anthropic_fable.ADAPTER_VERSION_2))
        # the harness@2 head's own review of it (9d773838c; sha256_json of the whole PeerReview)
        self.assertEqual(sha256_json(review), 'e8c22a689bba8e7eecc041229e7c9240622b3602a9afbf0f92b646c90bde00fd')
        self.assertEqual(dataclasses.replace(review, adapter_version=anthropic_fable.ADAPTER_VERSION),
                         anthropic_fable.read_peer(current, self.answer(GOOD)))
        fenced = anthropic_fable.read_peer(older, self.answer(f'```json\n{json.dumps(GOOD)}\n```'))
        self.assertEqual(fenced.problems, ('The peer review was not used: the answer is not valid JSON (Expecting '
                                           'value at character 0).',))  # as it always was there
        self.assertEqual(sha256_json(fenced), 'd65e324aa8f16528d165577e4984d3148a21f36cc00e7e94ac24d086dd587db9')

    def test_a_body_is_read_only_as_the_version_whose_shape_it_has(self):
        older, current = self.harness_2_request()
        relabelled = (dataclasses.replace(current, adapter_version=anthropic_fable.ADAPTER_VERSION_2),  # harness-4 body
                      dataclasses.replace(current, adapter_version=anthropic_fable.ADAPTER_VERSION_3),  # harness-4 body
                      dataclasses.replace(older, adapter_version=anthropic_fable.ADAPTER_VERSION))  # harness@2 body
        for request in relabelled:
            with self.subTest(version=request.adapter_version):
                review = anthropic_fable.read_peer(request, self.answer(GOOD))
                self.assertEqual((review.refused, review.adapter_version, review.problems),
                                 (True, request.adapter_version,
                                  ('The peer review was not used: the request is not a peer review this adapter '
                                   'builds.',)))
        self.assertIsNone(anthropic_fable._peer_document(older.body))
        self.assertIsNotNone(anthropic_fable._peer_document(older.body, anthropic_fable.ADAPTER_VERSION_2))
        self.assertIsNone(anthropic_fable._peer_document(current.body, anthropic_fable.ADAPTER_VERSION_2))

    def answer(self, value, **fields):
        return fable_with(value, **fields)

    def test_refused_truncated_other_model_fallback_and_tool_use_answers_are_refused_whole(self):
        fallback = fable_envelope()
        fallback['content'][1]['text'] = json.dumps(GOOD)
        fallback['content'].append({'type': 'fallback', 'model': 'claude-other'})
        cases = {
            'the model refused (category cyber)': self.answer(GOOD, stop_reason='refusal',
                                                              stop_details={'category': 'cyber'}),
            'the response was cut off at the output limit': self.answer(GOOD, stop_reason='max_tokens'),
            "it names model 'claude-fable-5-1-preview' as the model that answered, not claude-fable-5-1":
                self.answer(GOOD, model='claude-fable-5-1-preview'),
            'a server-side fallback took part in the answer, which this adapter never asks for':
                json.dumps(fallback).encode(),
            'it stopped for tool_use, not at the end of its turn': self.answer(GOOD, stop_reason='tool_use'),
        }
        for expect, raw in cases.items():
            with self.subTest(expect):
                review = self.read(raw)
                self.assertTrue(review.refused)
                self.assertEqual(review.problems, (f'The peer review was not used: {expect}.',))


class PromptConstantTests(OfflineTestCase):
    def test_the_instructions_say_the_own_reading_is_shown_as_cpt_studio_recorded_it(self):
        # Refutation round 1, IND-4: the own reading shown is CPT Studio's normalized one, which leaves out what CPT
        # Studio could not use, so the instructions may not call it unchanged - a dropped code would read as one a peer
        # proposed and the participant did not
        text = ' '.join(prompt.PEER_INSTRUCTIONS.split())
        self.assertNotIn('unchanged', text)
        self.assertIn('it is shown to you below as CPT Studio recorded it', text)
        for left_out in ('a code whose units fall outside 1 to 99', 'a date of service not written YYYY-MM-DD',
                         'an extraction issue naming no page'):
            self.assertIn(left_out, text)
        adapter = AstraParticipant(self.tmp / 'never-read.env')
        own = adapter.read(adapter.build_request(NOTE, PAGES, 'paste', None), astra_with(changed(
            fixture_reading(), date_of_service={'value': '2026-11-01T09:00', 'evidence': []},
            codes=[dict(fixture_reading()['codes'][0], units=0)], extraction_issues=[{'page': 0, 'issue': 'x'}])))
        self.assertEqual(len(own.problems), 3)  # each item CPT Studio could not use is named in its problems
        shown = prompt.reading_answer(own)  # and left out of what the peer request shows, as the instructions now say
        self.assertEqual((shown['date_of_service']['value'], shown['codes'], shown['extraction_issues']), ('', [], []))

    def test_the_protected_constants_are_unchanged(self):
        for name, expected in PROTECTED.items():
            value = getattr(prompt, name)
            data = value.encode() if isinstance(value, str) else json.dumps(value, sort_keys=True,
                                                                            separators=(',', ':')).encode()
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected)

    def test_the_peer_schema_is_one_cpt_studio_validates_itself(self):
        self.assertEqual(reading.schema_error(GOOD, prompt.PEER_SCHEMA, 'the peer review'), '')
        self.assertEqual(peer.MAX_ANSWERS, 64)

    def test_a_document_that_does_not_end_as_a_peer_document_lists_nothing(self):
        frozen = [['a', '0' * 64]]
        listed = json.dumps(frozen, separators=(',', ':'))
        good = '\n'.join(['x', '== question_ids ==', '["q1"]', '',
                          '== Frozen inputs: the sha256 of each frozen output shown above ==', listed])
        self.assertEqual(prompt.peer_document_inputs(good), (('q1',), (('a', '0' * 64),)))
        for broken in (good.replace('["q1"]', '["q1", "q1"]'), good.replace('["q1"]', '[ "q1"]'),
                       good.replace('== question_ids ==', '== question ids =='), good + '\n',
                       good.replace('0' * 64, 'A' * 64), good.replace(listed, '[]'), None, 7, ''):
            with self.subTest(broken=broken if not isinstance(broken, str) else broken[-60:]):
                self.assertIsNone(prompt.peer_document_inputs(broken))
