"""harness@2 in the API (HARNESS.md 11-12): the confirmation endpoint - every refusal and both success paths - and the
encounter view's and the trace's additions: the phase, each participant's peer review and its three kinds of references
kept apart, each open question's candidates and confirmation, the proposals' phases and confirmations.

Synthetic data only; no network, no credential. The rows are those the pipeline package writes (HARNESS.md 12.3):
runs of purpose independent and peer_review whose stored requests are the real adapters' and whose replayed response
bytes the real readers read, their exchanges and tool calls, and the assessments' participant entries. The
re-assessment a confirmation queues (jobs.reassess_after_confirmation) is built by the pipeline package and mocked here;
a service date goes through the real jobs.change_context.
"""
import hashlib
import json
from dataclasses import replace
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import candidates, customer_api, jobs, models, review
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.gi import context as gi_context
from studio.providers.base import canonical_body
from studio.providers.replay import ReplayProvider
from studio.types import ExtractionResult, PageSpan, to_jsonable
from tests.support import factories as f
from tests.support.operator import OperatorReads
from tests.support import pipeline_factories as pf
from tests.test_harness2_pipeline import TWO_EXTENTS
from tests.test_harness2_pipeline import ColonCase as PipelineColonCase
from tests.test_harness2_pipeline import Harness2Case as PipelineCase
from tests.test_harness_api import DESCRIPTOR_LIKE, UNLISTED_ONE
from tests.test_pipeline_api import corti_like_response, drain
from tests.test_participants_support import astra_with, fable_with, fixture_reading

BOTH = dict(ASTRA_MODE='replay', FABLE_MODE='replay')
MODELS = {'astra': 'gpt-6-astra', 'fable': 'claude-fable-5-1'}
ENDPOINTS = {'astra': 'https://api.openai.com/v1/responses', 'fable': 'https://api.anthropic.com/v1/messages'}
ADAPTERS = {'astra': AstraParticipant, 'fable': FableParticipant}
# The case's document (refutation round 3, falsegreen-11). The participants' fixture note documents its extent, its
# date and both acts plainly, so CPT Studio's readers hold nothing on it: the questions this case asked, 45380's
# performed-status hold with its support and its candidates among them, had been written by hand, rows the readers never
# produce for that note. This one is that note with what the readers do ask about - two documented dates of service that
# disagree, landmarks photographed but no extent reached, and a biopsy left in doubt - and every row the case pins is
# the engine's own (Harness2Case.result). Page 2 starts at its findings.
DATE_QUOTE = 'Date of service: 2026-10-21'
LANDMARK_QUOTE = 'Landmarks photographed: appendiceal orifice and ileocecal valve.'
SNARE_QUOTE = ('A 6 mm sessile polyp in the ascending colon was removed with a cold snare and retrieved for\n'
               'pathology.')
RECTUM_QUOTE = 'A 3 mm polyp in the rectum was possibly biopsied with cold forceps.'
UNLOCATED_QUOTE = 'A submucosal injection was given.'  # quoted by Astra's peer-review code; in no document
PAGE_ONE = ('SYNTHETIC TEST DOCUMENT - not a real patient. Written for CPT Studio harness@2 tests.\n'
            'GI Procedure Report\n' + DATE_QUOTE + '\nProcedure date: 2026-10-22\nProcedure: Colonoscopy.\n'
            'Indication: Average-risk screening.\nTechnique: ' + LANDMARK_QUOTE + ' Bowel preparation was good.\n')
NOTE = (PAGE_ONE + 'Findings: ' + SNARE_QUOTE + ' ' + RECTUM_QUOTE + '\nImpression: Two polyps.\n'
        'Plan: Await pathology. Repeat colonoscopy in 7 years.\n')
PAGES = (PageSpan(page=1, start=0, end=len(PAGE_ONE)), PageSpan(page=2, start=len(PAGE_ONE), end=len(NOTE)))
SNARE = 'was removed with a cold snare'  # the passage Corti's selection of 45385 cites
FACT_REF = 'fact:cms-pfs-rvu26d:45385:mult_proc'
PASSAGE_REF = 'ncci-2026-ch6-c-1'
# Each of them where a run's own tool calls never returned it: the participant's own text, which the API, the trace and
# the reports show only by its length (refutation round 4, R4-SHAPES, shapes-3)
FACT_UNRETRIEVED = 'a value of 35 characters (not shown)'
PASSAGE_UNRETRIEVED = 'a value of 17 characters (not shown)'
# The two tools' stored results in the layout CPT Studio's executor writes them (studio.reference.tools), which the
# API's references read back with its own reader (tools.retrieved_references).
FACTS_RESULT = {'tool': 'cms_code_facts', 'date_of_service': '', 'releases': 'every release held', 'codes': [
    {'code': '45385', 'notes': [], 'sources': [
        {'source_key': 'cms-pfs-rvu26d', 'kind': 'cms-pfs', 'release': 'RVU26D', 'effective_start': '2026-10-01',
         'effective_end': '2026-12-31', 'sha256': '0' * 64,
         'facts': [{'ref': FACT_REF, 'field': 'mult_proc', 'label': 'PFS multiple procedure indicator',
                    'value': '3'}]}]}]}
PASSAGES_RESULT = {'tool': 'cms_policy_passages', 'topic': 'ncci_endoscopy_rules', 'codes': ['45385'], 'notes': [],
                   'passages': [
    {'ref': PASSAGE_REF, 'passage_key': PASSAGE_REF, 'source_key': 'cms-ncci-policy-manual-2026',
     'kind': 'cms-ncci-policy-manual', 'release': 'Revision 2026', 'effective_start': '2026-01-01',
     'effective_end': '2026-12-31', 'section': 'Chapter VI §C.1', 'page': '6', 'topic': 'ncci.endoscopy',
     'topic_value': '', 'sha256': '1' * 64, 'source_sha256': '2' * 64,
     'text': 'Synthetic passage text for the tests.'}]}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_reading(name):
    """The fixture reading (tests/fixtures/participants), quoting this case's NOTE, with references used: one its run
    retrieves, one not."""
    data = fixture_reading()
    data['services'][0]['evidence'] = [LANDMARK_QUOTE, ' '.join(SNARE_QUOTE.split())]
    data['codes'][1]['evidence'] = [RECTUM_QUOTE]
    data['references_used'] = ([{'ref': FACT_REF, 'use': 'The endoscopic base of the snare removal.'},
                                {'ref': PASSAGE_REF, 'use': 'A rule this run never retrieved.'}]
                               if name == 'astra' else [])
    return data


def questions_of(assessment):
    """{fact: question} of ``assessment``'s questions, the first proposal's of each fact - extent is 45385's (sel:0),
    performed_status 45380's (sel:1), service_date the encounter's - and {(fact, proposal key): question} of all of
    them under 'by_key'."""
    every = list(assessment.clarifications.select_related('proposal'))
    by_key = {(c.fact, c.proposal.key if c.proposal_id else ''): c for c in every}
    out = {}
    for (fact, key), question in sorted(by_key.items(), key=lambda item: (item[0][0], item[0][1])):
        out.setdefault(fact, question)
    return {**out, 'by_key': by_key}


class Harness2Case(OperatorReads, TestCase):
    """One encounter carried through harness@2 as the pipeline records it: the document's context as its reader reads
    it; Corti's run, read by Corti's own normalizer; Astra's and Fable's frozen first readings (Astra's with a tool
    call); assess #1, the engine's, with its open questions; both peer reviews (Astra's with a tool call), built from
    assess #1 by the pipeline's own peer material; and assess #2, the engine's, the final assessment. Refutation round
    3, falsegreen-11: the assessments were hand-built and asked what the readers never ask of their note; every row the
    case pins is now what the assess stage's own engine makes of the case's stored runs (result). Refutation round 4
    (falsegreen-7, falsegreen-4): so are the participants entries beside it (entry: they were written by hand, every
    code's quote '' and the frozen list in another order) and the reconciliation's retrieval (retrieval_of: it was
    [])."""

    def setUp(self):
        self.ws = f.workspace()
        self.owner = f.member(self.ws, f.user('owner2b'), role=models.Membership.OWNER)
        self.reviewer = f.member(self.ws, f.user('reviewer2b'))
        self.viewer = f.member(self.ws, f.user('viewer2b'), role=models.Membership.VIEWER)
        self.encounter = f.encounter(self.ws, self.reviewer, title='Synthetic colonoscopy for harness@2')
        self.document()
        self.now = timezone.now()
        self.adapters = {name: ADAPTERS[name]('/nonexistent/never-read.env') for name in ADAPTERS}
        self.runs, self.readings, self.requests = {}, {}, {}
        for name in ADAPTERS:
            request = self.adapters[name].build_request(NOTE, PAGES, 'paste', None)
            data = (astra_with if name == 'astra' else fable_with)(self.first_reading(name))
            run = self.make_run(name, request, data, purpose=models.ProviderRun.INDEPENDENT)
            calls = [('cms_code_facts', {'codes': ['45385'], 'date_of_service': ''}, FACTS_RESULT, [FACT_REF])]
            self.exchanges(run, request.body, data, calls if name == 'astra' else [])
            self.runs[name], self.requests[name] = run, request
            self.readings[name] = self.adapters[name].read(request, data, frozenset(review.run_refs(run)))
        self.frozen = self.frozen_list()
        self.first = self.persist([self.entry(name) for name in ADAPTERS])
        self.peer_runs, self.reviews = {}, {}
        for name in ADAPTERS:
            self.peer_review(name)
        self.final = self.persist([self.entry(name, peer=True) for name in ADAPTERS])
        self.questions = questions_of(self.final)

    # --- the rows -----------------------------------------------------------------------------------------------------

    def document(self):
        """The revision as the extract stage records a paste; its context as the analyze stage records it (the
        document's facts, read by the context reader: two dates of service that disagree, so no service date); and
        Corti's run as a replayed Corti answer that selects 45385 on the snare passage and 45380 on the rectum's biopsy
        left in doubt, read by Corti's own normalizer.
        """
        self.revision = f.pasted_revision(self.encounter, self.reviewer, NOTE, extract=False)
        f.record(self.revision, ExtractionResult(status='ok', method='paste', text=NOTE, pages=PAGES))
        self.revision.refresh_from_db()
        self.context = jobs._record_context(self.encounter, self.revision, gi_context.extract_context(NOTE))
        self.encounter.current_context = self.context
        self.encounter.save(update_fields=['current_context', 'updated_at'])
        request = ReplayProvider('/nonexistent/never-read').build_request(NOTE, jobs.context_service_date(self.context))
        # moved by refutation round 6 (R6-MEANING, the session's D14): Corti selects 45380 too. A code only the
        # participants propose is never a proposal now - it is their alternative (tests/test_harness2_r6_meaning.py) -
        # so the 45380 hold the case's questions, candidates and fixtures read is Corti's proposal's, with both
        # participants recorded on it; read on the same passage, its hold is the one the participants' code had (I2)
        data = corti_like_response(NOTE, [('45385', SNARE), ('45380', RECTUM_QUOTE)])
        self.corti = models.ProviderRun.objects.create(
            encounter=self.encounter, revision=self.revision, provider=request.provider,
            adapter_version=request.adapter_version, request_sha256=request.canonical_sha256,
            request_body=request.body, contexts=list(request.contexts), state=models.ProviderRun.SUCCEEDED, sent=True,
            http_status=200, response_bytes=data, response_sha256=sha(data), usage={'creditsConsumed': 0.0281},
            usage_basis='provider_reported_credits_not_usd', started_at=timezone.now(), finished_at=timezone.now())

    def first_reading(self, name):
        return first_reading(name)

    def make_run(self, name, request, data, *, purpose, assessment=None):
        return models.ProviderRun.objects.create(
            encounter=self.encounter, revision=self.revision, provider=name, adapter_version=request.adapter_version,
            request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
            state=models.ProviderRun.SUCCEEDED, sent=True, http_status=200, response_bytes=data,
            response_sha256=sha(data), latency_ms=12.5, usage={'input_tokens': 2000, 'output_tokens': 200},
            usage_basis='provider_reported_tokens_summed_over_exchanges', purpose=purpose,
            scope={'mode': 'replay', **({'assessment': str(assessment.pk)} if assessment is not None else {})},
            endpoint=ENDPOINTS[name], requested_model=MODELS[name], returned_model=MODELS[name],
            response_id=f'resp_{name}_{purpose}', provider_request_id=f'req_{name}_{purpose}', started_at=self.now,
            finished_at=self.now)

    def exchanges(self, run, body, data, calls):
        """Turn 1 asks for ``calls`` (each recorded as a ToolCall) and turn 2 is the final answer; one turn without."""
        turns = [(body, b'{"synthetic": "tool call turn"}', calls), (body, data, [])] if calls else [(body, data, [])]
        for turn, (request_body, response, made) in enumerate(turns, start=1):
            exchange = models.ProviderExchange.objects.create(
                run=run, turn=turn, request_body=request_body, request_sha256=sha(canonical_body(request_body)),
                state='succeeded', http_status=200, response_bytes=response, response_sha256=sha(response),
                latency_ms=6.0, usage={'input_tokens': 1000, 'output_tokens': 100},
                provider_request_id=f'req_{run.provider}_{turn}', response_id=f'resp_{run.provider}_{turn}',
                started_at=self.now, finished_at=self.now)
            for number, (tool, arguments, result, refs) in enumerate(made, start=1):
                models.ToolCall.objects.create(exchange=exchange, call_id=f'call_{turn}_{number}', tool=tool,
                                               arguments=arguments, result=result,
                                               result_sha256=sha(canonical_body(result)), refs=refs,
                                               executed_at=self.now)

    def inputs(self, phase):
        """The participants' inputs the assess stage reads, by the pipeline's own readers of the stored runs: each
        frozen first reading (jobs._first_input) and, in phase 2, its peer review (jobs._with_peer)."""
        out = []
        for name in ADAPTERS if phase else ():  # phase 0: no participant configured (I1)
            item, record = jobs._first_input(self.encounter, name, self.runs[name])
            if phase == 2:
                item, record = jobs._with_peer(self.encounter, item, record, self.peer_runs[name])
            out.append(item)
        return tuple(out)

    def result(self, phase=2, confirmed=()):
        """The assessment the assess stage's own engine makes of the case's stored rows (jobs._assess_child, as
        stage_assess calls it, with the reference lookup it prefetches): Corti's run read by its normalizer, the
        context's facts and service date, the participants' inputs of ``phase`` and the ``confirmed`` findings
        (jobs.confirmed_findings). The routing it reads is recorded as the stage records it (self.routing_run)."""
        provider_status, normalized = jobs._provider_inputs(self.corti)
        inputs = self.inputs(phase)
        proposed = {code.code for item in inputs if item.reading is not None for code in item.reading.codes}
        proposed |= {code.code for item in inputs if item.peer is not None for code in item.peer.additional_codes}
        service_date = jobs.context_service_date(self.context)
        prefetched = tuple(sorted(set(jobs.selected_codes(normalized)) | proposed))
        reference = jobs.prefetched_lookup(prefetched)
        data, result = jobs._assess_child(
            self.revision.text, service_date, tuple(PageSpan(**page) for page in self.revision.pages),
            jobs.context_facts(self.context), normalized, reference, provider_status, self.revision.extraction_status,
            tuple(self.revision.messages), None, None, inputs, tuple(confirmed))
        self.routing_run = jobs._record_routing(self.revision, data, service_date)
        self.lookup = (service_date, reference, prefetched)
        return result

    def retrieval_of(self, result):
        """The reconciliation's retrieval the assess stage records beside ``result`` (jobs._retrieval), from the lookup
        the engine read (result: the service date, the prefetched reference and its codes). Refutation round 4,
        falsegreen-4: the website fixtures' was a stand-in of dated CMS facts and a passage, which the stage cannot
        retrieve for this document - its dates of service disagree, so no service date is established - beside a
        Reference validation row that says no code was checked; the API case's was []."""
        return jobs._retrieval(result, *self.lookup)

    def frozen_list(self):
        """assess #1's and #2's frozen list as the stage records it (jobs._frozen): Corti's response, each reading's
        sha256 and the revision's, in harness order (refutation round 4, falsegreen-7: it was written sorted by
        name)."""
        readings = {name: {'reading_sha256': jobs.answer_sha256(self.readings[name])} for name in ADAPTERS}
        return jobs._frozen(self.revision, self.corti, readings)

    def entry(self, name, *, peer=False):
        """An Assessment.participants entry in the 12.3 shape, as the assess stage records it: the record
        jobs._first_input makes of the participant's phase-1 run - harness@1's keys, the codes and not-coded items each
        with its first located quote, the reading's sha256, the exchanges and tool calls - with, on assess #2, its peer
        review's (jobs._with_peer), and the frozen list. Refutation round 4, falsegreen-7: it was written by hand, every
        code's quote '' (the API then said each participant's codes had no quote found in the document) and the frozen
        list in another order."""
        item, record = jobs._first_input(self.encounter, name, self.runs[name])
        if peer:
            record = jobs._with_peer(self.encounter, item, record, self.peer_runs[name])[1]
        return {**record, 'frozen': self.frozen}

    def persist(self, entries, result=None, routing_run=None):
        """Persist an assessment of the case's runs with ``entries`` and the retrieval the stage records beside its
        result (retrieval_of): ``result``, or the engine's of the phase the entries record - 2 when any carries its
        peer review, 0 when none records a configured participant (Corti alone: the engine is given no participant,
        I1), 1 otherwise. A test's variation of an entry (a peer review recorded refused, a reading's sha256) varies
        the record beside the result, never the result. ``routing_run``: a routing record of the test's own, for an
        assessment review._same_assessment would otherwise take for the current one."""
        self.encounter.refresh_from_db()
        if result is None:
            configured = [entry for entry in entries if entry.get('state') != 'not_configured']
            result = self.result(0 if not configured else 2 if any('peer_state' in e for e in entries) else 1)
        return review.persist_assessment(encounter=self.encounter, revision=self.revision, context=self.context,
                                         routing_run=routing_run or self.routing_run, provider_run=self.corti,
                                         result=result, participants=entries, retrieval=self.retrieval_of(result))

    def peer_answer(self, name):
        """The peer answers, to assess #1's questions by (fact, proposal key) - sel:0 is 45385, sel:1 45380."""
        asked = {(c.fact, c.proposal.key if c.proposal_id else ''): str(c.pk)
                 for c in self.first.clarifications.select_related('proposal')}
        if name == 'fable':
            # the participant's own wording, which CPT Studio restates as the landmark it names ('cecum')
            return {'question_answers': [{'question_id': asked['extent', 'sel:0'], 'settled': True,
                                          'value': 'Cecum, appendiceal orifice seen',
                                          'evidence': [LANDMARK_QUOTE]}],
                    'code_positions': [], 'additional_codes': [], 'references_used': []}
        return {'question_answers': [
                    {'question_id': asked['extent', 'sel:0'], 'settled': True, 'value': 'cecum',
                     'evidence': [LANDMARK_QUOTE]},
                    {'question_id': asked['service_date', ''], 'settled': True, 'value': '2026-10-21',
                     'evidence': [DATE_QUOTE]},
                    {'question_id': asked['performed_status', 'sel:1'], 'settled': True, 'value': 'performed',
                     'evidence': [RECTUM_QUOTE]}],
                'code_positions': [{'code': '45380', 'position': 'supports', 'reason': 'Participant wording.',
                                    'evidence': [RECTUM_QUOTE]}],
                'additional_codes': [{'code': '45381', 'modifiers': [], 'units': 1, 'service_ids': ['s1'],
                                      'basis': 'Participant wording.', 'evidence': [UNLOCATED_QUOTE],
                                      'confidence': 'low'}],
                'references_used': [{'ref': PASSAGE_REF, 'use': 'The NCCI endoscopy rule.'},
                                    {'ref': FACT_REF, 'use': 'Retrieved only by its first reading.'}]}

    def peer_review(self, name):
        """``name``'s peer review of assess #1, its request built from the pipeline's own peer material
        (jobs._peer_material: its own frozen reading, Corti's exact passages, the other model's reading as shown and CPT
        Studio's reading after assess #1), its run made for assess #1 as a peer stage records it."""
        own, peers, cpt_studio, frozen = jobs._peer_material(self.revision, self.first, name,
                                                             jobs._records(self.first))
        request = self.adapters[name].build_peer_request(NOTE, PAGES, 'paste', own, peers, cpt_studio, frozen)
        data = (astra_with if name == 'astra' else fable_with)(self.peer_answer(name))
        run = self.make_run(name, request, data, purpose=models.ProviderRun.PEER_REVIEW, assessment=self.first)
        calls = [('cms_policy_passages', {'topic': 'ncci_endoscopy_rules', 'codes': ['45385']}, PASSAGES_RESULT,
                  [PASSAGE_REF])]
        self.exchanges(run, request.body, data, calls if name == 'astra' else [])
        self.peer_runs[name] = run
        self.reviews[name] = self.adapters[name].read_peer(request, data, frozenset(review.run_refs(run)))
        self.assertFalse(self.reviews[name].refused, self.reviews[name].problems)

    # --- helpers ------------------------------------------------------------------------------------------------------

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client

    def candidates_of(self, fact):
        return review.assessment_candidates(self.final)[str(self.questions[fact].pk)]

    def verified(self, fact, text=None):
        return next(c for c in self.candidates_of(fact)
                    if c['verified'] and (text is None or c['spans'][0]['text'] == text))

    def confirm(self, fact, candidate=None, *, user=None, attestation=None, question=None):
        candidate = candidate or self.verified(fact)
        question = question or self.questions[fact]
        body = {'candidate_id': candidate['id'],
                'attestation': candidates.attestation(candidate['value']) if attestation is None else attestation}
        return self.client_for(user or self.reviewer).post(
            f'/api/encounters/{self.encounter.pk}/clarifications/{question.pk}/confirm', data=json.dumps(body),
            content_type='application/json')


@override_settings(**BOTH)
class FixtureTests(Harness2Case):
    def test_the_rows_read_as_the_pipeline_records_them(self):
        self.assertEqual((review.assessment_phase(self.first), review.assessment_phase(self.final)), (1, 2))
        self.assertEqual((review.is_final(self.first), review.is_final(self.final)), (False, True))
        readings, reviews = review.frozen_inputs(self.final)
        self.assertEqual([r.name for r in readings], ['astra', 'fable'])
        self.assertEqual([name for name, _, _ in reviews], ['astra', 'fable'])
        # Astra's first reading checks its references against its own run's tool calls only
        used = {item.ref: item.retrieved for item in self.readings['astra'].references_used}
        self.assertEqual(used, {FACT_REF: True, PASSAGE_REF: False})


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(**BOTH)
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class CandidateTests(Harness2Case):
    def test_each_open_question_of_the_final_assessment_has_its_candidates(self):
        extent = self.candidates_of('extent')
        self.assertEqual([(c['value'], c['verified'], c['located_by'], c['phase']) for c in extent],
                         [('cecum', True, ['astra', 'fable'], 'independent'),
                          ('cecum', False, ['astra', 'fable'], 'independent')])
        self.assertEqual(set(extent[0]['runs']), {str(self.runs['astra'].pk), str(self.runs['fable'].pk),
                                                  str(self.peer_runs['astra'].pk), str(self.peer_runs['fable'].pk)})
        self.assertEqual(extent[1]['why'], 'The passage does not name the cecum.')
        (date_candidate,) = self.candidates_of('service_date')
        self.assertEqual((date_candidate['value'], date_candidate['verified'], date_candidate['spans'][0]['text']),
                         ('2026-10-21', True, DATE_QUOTE))
        status = self.candidates_of('performed_status')
        # refutation round 2, EV2-1: a status is verified only on a sentence the readers read as 45380's own biopsy done
        # - never on the landmark or the snare sentence its participants also quoted. Moved by refutation round 3
        # (falsegreen-11): the readers leave this note's biopsy in doubt, so no status candidate verifies: the rectum
        # sentence the peer review quotes is the doubt itself, where the hand-built hold had verified it
        self.assertEqual([(c['value'], c['verified'], c['phase'], c['spans'][0]['text']) for c in status],
                         [('performed', False, 'independent', LANDMARK_QUOTE),
                          ('performed', False, 'independent', SNARE_QUOTE),
                          ('performed', False, 'peer_review', RECTUM_QUOTE)])
        self.assertEqual([c['why'] for c in status], ['The passage does not name the forceps biopsy.'] * 2
                         + ['The passage leaves the forceps biopsy in doubt.'])
        # the engine asks 45380's extent too, and its candidates are 45385's: the same landmark passage
        biopsy_extent = review.assessment_candidates(self.final)[str(self.questions['by_key']['extent', 'sel:1'].pk)]
        self.assertEqual([(c['value'], c['verified'], c['spans'][0]['text']) for c in biopsy_extent],
                         [('cecum', True, LANDMARK_QUOTE), ('cecum', False, SNARE_QUOTE)])

    def test_none_before_the_final_assessment_nor_for_a_corti_only_one(self):
        self.assertEqual(review.assessment_candidates(self.first), {})
        corti_only = self.persist([jobs.not_configured_record('astra'), jobs.not_configured_record('fable')])
        self.assertEqual(review.assessment_phase(corti_only), 0)
        self.assertEqual(review.assessment_candidates(corti_only), {})

    def test_a_peer_answer_never_answers_a_question_whose_proposal_changed(self):
        # assess #2 selected another code under the key assess #1's question named: the peer answered about 45380, so
        # its answer is no candidate for the question about 45381 (sel:1 there)
        result = self.result()
        biopsy = next(p for p in result.proposals if p.key == 'sel:1')
        other = replace(biopsy, code='45381', clarifications=tuple(replace(q, question='Colonoscopy: confirm whether '
                                                                                'the injection was performed.')
                                                                   for q in biopsy.clarifications))
        changed = self.persist([self.entry(name, peer=True) for name in ADAPTERS],
                               replace(result, proposals=tuple(other if p.key == 'sel:1' else p
                                                               for p in result.proposals)))
        question = changed.clarifications.get(fact='performed_status')
        offered = review.assessment_candidates(changed)[str(question.pk)]
        self.assertEqual([c['phase'] for c in offered], ['independent', 'independent'])  # no peer-review candidate
        self.assertNotIn(str(self.peer_runs['astra'].pk), {run for c in offered for run in c['runs']})

    def test_a_frozen_reading_that_no_longer_matches_its_recorded_sha256_is_not_used(self):
        entries = [self.entry(name, peer=True) for name in ADAPTERS]
        entries[1]['reading_sha256'] = '0' * 64
        # moved by refutation round 3 (falsegreen-11): the routing record is the engine's, so identical rows would be
        # taken for the final assessment (review._same_assessment never compares a reading's sha256): a routing record
        # of its own
        changed = self.persist(entries, routing_run=pf.routing(self.revision))
        self.assertNotEqual(changed, self.final)
        with self.assertLogs('studio.review', level='WARNING'):
            readings, reviews = review.frozen_inputs(changed)
        self.assertEqual(([r.name for r in readings], [name for name, _, _ in reviews]), (['astra'], ['astra']))


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(**BOTH)
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class ConfirmationRefusalTests(Harness2Case):
    def assertRefused(self, response, status, words):
        self.assertEqual(response.status_code, status, response.content)
        self.assertIn(words, response.json()['error'])
        self.assertFalse(models.FindingConfirmation.objects.exists())
        self.assertFalse(models.AuditEvent.objects.filter(event='finding.confirmed').exists())

    def test_a_viewer_cannot_and_another_workspace_sees_nothing(self):
        self.assertRefused(self.confirm('extent', user=self.viewer), 403, 'cannot')
        outsider = f.member(f.workspace('Another synthetic workspace'), f.user('outsider2b'),
                            role=models.Membership.OWNER)
        response = self.confirm('extent', user=outsider)
        self.assertEqual(response.status_code, 404)
        anonymous = Client().post(f'/api/encounters/{self.encounter.pk}/clarifications/'
                                  f'{self.questions["extent"].pk}/confirm', data='{}', content_type='application/json')
        self.assertEqual(anonymous.status_code, 401)
        get = self.client_for(self.reviewer).get(f'/api/encounters/{self.encounter.pk}/clarifications/'
                                                 f'{self.questions["extent"].pk}/confirm')
        self.assertEqual(get.status_code, 405)

    def test_a_question_of_another_document_is_not_found(self):
        other = f.encounter(self.ws, self.reviewer, title='Another synthetic document')
        response = self.client_for(self.reviewer).post(
            f'/api/encounters/{other.pk}/clarifications/{self.questions["extent"].pk}/confirm',
            data=json.dumps({'candidate_id': '0' * 16, 'attestation': 'x'}), content_type='application/json')
        self.assertRefused(response, 404, 'not part of this document')

    def test_a_question_of_an_earlier_assessment(self):
        earlier = self.first.clarifications.get(fact='extent', proposal__key='sel:0')  # 45380 asks its extent too
        self.assertEqual(earlier.state, models.Clarification.OPEN)  # re-raised by assess #2, still open on assess #1
        self.assertRefused(self.confirm('extent', question=earlier), 409, 'earlier assessment')

    def test_before_the_final_assessment(self):
        phase_one = self.persist([self.entry(name) for name in ADAPTERS])  # an assess #1 whose peer stages follow
        self.assertFalse(review.is_final(phase_one))
        question = phase_one.clarifications.get(fact='extent', proposal__key='sel:0')
        # moved by the customer interface change (CORE-UX-DESIGN.md 5): a refusal reaches a member in the customer vocabulary
        self.assertRefused(self.confirm('extent', question=question), 409,
                           'independent checks for this document have not finished')

    def test_a_question_that_is_not_open(self):
        candidate = self.verified('extent')
        models.Clarification.objects.filter(pk=self.questions['extent'].pk).update(
            state=models.Clarification.WITHDRAWN)
        self.assertRefused(self.confirm('extent', candidate), 409, 'not open')

    def test_a_candidate_that_is_not_verified_or_not_offered(self):
        unverified = next(c for c in self.candidates_of('extent') if not c['verified'])
        self.assertRefused(self.confirm('extent', unverified), 409, 'not verified')
        self.assertRefused(self.confirm('extent', dict(self.verified('extent'), id='0123456789abcdef')), 409,
                           "not one of this question's candidates")
        # a verified candidate of another question is not this question's
        self.assertRefused(self.confirm('extent', self.verified('service_date')), 409,
                           "not one of this question's candidates")
        for bad in ('', 'ABCDEF0123456789', 'not-hex', 12):
            response = self.client_for(self.reviewer).post(
                f'/api/encounters/{self.encounter.pk}/clarifications/{self.questions["extent"].pk}/confirm',
                data=json.dumps({'candidate_id': bad, 'attestation': 'x'}), content_type='application/json')
            self.assertRefused(response, 400, 'candidate_id')

    def test_the_attestation_must_be_exactly_the_candidate_s(self):
        candidate = self.verified('extent')
        exact = candidates.attestation('cecum')
        for wrong in ('', exact.lower(), exact + ' ', candidates.attestation('terminal ileum'), exact[:-1]):
            self.assertRefused(self.confirm('extent', candidate, attestation=wrong), 400, 'must read exactly')
        response = self.confirm('extent', candidate, attestation=['not', 'text'])
        self.assertRefused(response, 400, 'must be text')

    def test_one_confirmation_per_question(self):
        with mock.patch('studio.jobs.reassess_after_confirmation') as reassess:
            self.assertEqual(self.confirm('extent').status_code, 201)
            again = self.confirm('extent', self.verified('extent'))
        self.assertEqual(again.status_code, 409, again.content)
        self.assertIn('confirmed already', again.json()['error'])
        self.assertEqual(models.FindingConfirmation.objects.count(), 1)
        self.assertEqual(reassess.call_count, 1)

    def test_not_while_processing(self):
        pf.job(self.encounter, self.revision, models.Job.ASSESS, models.Job.QUEUED)
        self.assertRefused(self.confirm('extent'), 409, 'Wait for processing to finish')

    def test_a_refusal_of_the_effect_records_nothing(self):
        # moved by the customer interface change (CORE-UX-DESIGN.md 5): a refusal reaches a member in the customer vocabulary
        # (a refusal the vocabulary does not know, such as these, is "This action is not available right now.")
        with mock.patch('studio.jobs.reassess_after_confirmation', side_effect=jobs.Refused('Synthetic refusal.')):
            self.assertRefused(self.confirm('extent'), 409, customer_api.GENERIC_ERROR)
        with mock.patch('studio.jobs.change_context', side_effect=jobs.Refused('Synthetic context refusal.')):
            self.assertRefused(self.confirm('service_date'), 409, customer_api.GENERIC_ERROR)


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(**BOTH)
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class ConfirmationTests(Harness2Case):
    def test_a_required_fact_is_recorded_audited_and_re_assessed_never_approved(self):
        candidate = self.verified('extent')
        with mock.patch('studio.jobs.reassess_after_confirmation') as reassess:
            response = self.confirm('extent', candidate)
        self.assertEqual(response.status_code, 201, response.content)
        confirmation = models.FindingConfirmation.objects.get()
        question = self.questions['extent']
        self.assertEqual(
            (confirmation.clarification_id, confirmation.revision_id, confirmation.scope, confirmation.fact,
             confirmation.family, confirmation.proposal_key, confirmation.value, confirmation.spans,
             confirmation.located_by, confirmation.runs, confirmation.confirmed_by_id, confirmation.attestation),
            (question.pk, self.revision.pk, 'proposal', 'extent', 'gi.colonoscopy', 'sel:0', 'cecum',
             candidate['spans'], ['astra', 'fable'], candidate['runs'], self.reviewer.pk,
             candidates.attestation('cecum')))
        self.assertEqual(NOTE[candidate['spans'][0]['start']:candidate['spans'][0]['end']], LANDMARK_QUOTE)
        data = response.json()
        self.assertEqual((data['id'], data['effect'], data['value'], data['confirmed_by'], data['clarification_id']),
                         (str(confirmation.pk), 'reassessment', 'cecum', self.reviewer.label(), str(question.pk)))
        reassess.assert_called_once()
        (called_encounter, called_user), _ = reassess.call_args
        self.assertEqual((called_encounter.pk, called_user.pk), (self.encounter.pk, self.reviewer.pk))
        event = models.AuditEvent.objects.get(event='finding.confirmed')
        self.assertEqual((event.actor_id, event.data['confirmation'], event.data['clarification'], event.data['fact'],
                          event.data['effect'], event.data['located_by']),
                         (self.reviewer.pk, str(confirmation.pk), str(question.pk), 'extent', 'reassessment',
                          ['astra', 'fable']))
        self.assertNotIn('cecum', json.dumps(event.data))  # ids and names, never the confirmed text
        self.assertFalse(models.Decision.objects.exists())  # nothing is approved (I3, I4)

    def test_the_row_is_built_from_the_recomputed_candidate_never_from_the_request(self):
        """Refutation round 1, EV-3: the endpoint reads only the candidate's id and the attestation. The passage, value,
        participants and runs it records are those of the candidate CPT Studio recomputes from its own located quotes,
        and the question and its proposal those of the clarification - whatever else a request carries."""
        candidate = self.verified('extent')
        question = self.questions['extent']
        forged = {'candidate_id': candidate['id'], 'attestation': candidates.attestation(candidate['value']),
                  'value': 'terminal ileum', 'spans': [{'start': 0, 'end': 3, 'text': NOTE[:3], 'page': 1}],
                  'located_by': ['corti'], 'runs': ['run-forged'], 'proposal_key': 'sel:1', 'proposal_code': '45380',
                  'scope': 'service', 'fact': 'performed_status', 'family': 'gi.egd'}
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            response = self.client_for(self.reviewer).post(
                f'/api/encounters/{self.encounter.pk}/clarifications/{question.pk}/confirm', data=json.dumps(forged),
                content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        row = models.FindingConfirmation.objects.get()
        self.assertEqual((row.clarification_id, row.scope, row.fact, row.family, row.proposal_key, row.value, row.spans,
                          row.located_by, row.runs),
                         (question.pk, 'proposal', 'extent', 'gi.colonoscopy', 'sel:0', candidate['value'],
                          candidate['spans'], candidate['located_by'], candidate['runs']))
        offered = {c['id']: c for c in self.candidates_of('extent')}  # recomputed again: the same verified candidate
        self.assertTrue(offered[candidate['id']]['verified'])
        (finding,) = jobs.confirmed_findings(self.revision)
        self.assertEqual((finding.proposal_code, finding.proposal_identity),
                         (question.proposal.code, question.proposal.support['identity']))

    def test_an_owner_may_confirm_and_a_status_the_readers_leave_in_doubt_offers_nothing_to_confirm(self):
        # moved by refutation round 3 (falsegreen-11): the readers leave this note's biopsy in doubt, so no status
        # candidate verifies and none is confirmed (refused, 409); the owner confirms 45380's other open question, its
        # extent
        status = self.candidates_of('performed_status')
        self.assertFalse(any(c['verified'] for c in status))
        doubt = next(c for c in status if c['spans'][0]['text'] == RECTUM_QUOTE)
        self.assertEqual(self.confirm('performed_status', doubt, user=self.owner).status_code, 409)
        question = self.questions['by_key']['extent', 'sel:1']
        candidate = next(c for c in review.assessment_candidates(self.final)[str(question.pk)] if c['verified'])
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            response = self.confirm('extent', candidate, user=self.owner, question=question)
        self.assertEqual(response.status_code, 201, response.content)
        confirmation = models.FindingConfirmation.objects.get()
        self.assertEqual((confirmation.fact, confirmation.value, confirmation.located_by, confirmation.proposal_key,
                          confirmation.confirmed_by_id),
                         ('extent', 'cecum', ['astra', 'fable'], 'sel:1', self.owner.pk))

    def test_a_service_date_enters_as_the_member_s_date_through_the_context_path(self):
        candidate = self.verified('service_date')
        before = self.encounter.current_context_id
        with mock.patch('studio.jobs.reassess_after_confirmation') as reassess:
            response = self.confirm('service_date', candidate)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['effect'], 'context')
        reassess.assert_not_called()
        self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.current_context_id, before)
        self.assertEqual(self.encounter.user_values, {'service_date': '2026-10-21'})
        self.assertEqual(self.encounter.current_context.user_values, {'service_date': '2026-10-21'})
        confirmation = models.FindingConfirmation.objects.get()
        self.assertEqual((confirmation.scope, confirmation.fact, confirmation.family, confirmation.value),
                         ('encounter', 'service_date', '', '2026-10-21'))
        events = list(models.AuditEvent.objects.filter(event__in=('finding.confirmed', 'context.changed'))
                      .order_by('created_at'))
        self.assertEqual([e.event for e in events], ['finding.confirmed', 'context.changed'])
        self.assertEqual(events[1].data['fields'], ['service_date'])
        # the context's own audit row names the confirmation the date entered by (HARNESS.md 12.5)
        self.assertEqual((events[1].data['confirmation'], events[1].data['context']),
                         (str(confirmation.pk), str(self.encounter.current_context_id)))
        self.assertFalse(models.Decision.objects.exists())


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(**BOTH)
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class DetailTests(Harness2Case):
    def detail(self, user=None):
        response = self.client_for(user or self.reviewer).get(f'/ops/api/encounters/{self.encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def rows(self, data):
        return {row['name']: row for row in data['harness']['participants']}

    def test_the_phase_and_the_permission_to_confirm(self):
        data = self.detail()
        self.assertEqual((data['harness']['phase'], data['permissions']['can_confirm']), (2, True))
        self.assertFalse(self.detail(self.viewer)['permissions']['can_confirm'])
        self.persist([self.entry(name) for name in ADAPTERS])  # an assess #1 again: phase 1
        self.assertEqual(self.detail()['harness']['phase'], 1)
        self.persist([jobs.not_configured_record('astra'), jobs.not_configured_record('fable')])
        self.assertEqual(self.detail()['harness']['phase'], 0)

    def test_each_participant_s_peer_review_and_its_references_kept_apart(self):
        data = self.detail()
        rows = self.rows(data)
        astra, fable, corti = rows['astra'], rows['fable'], rows['corti']
        # moved by refutation round 3 (falsegreen-11): Astra's peer-review code quotes a sentence in no document (45381
        # is listed apart, as the engine lists a code with no located quote), which its row counts; and moved by round 5
        # (R5-ACCOUNT, the session's D12): with no located quote its peer review listed 45381 and proposed no code there,
        # so codes_added - the codes it first proposed in peer review - holds none (it held 45381)
        self.assertEqual(astra['peer'], {'state': 'done', 'run_id': str(self.peer_runs['astra'].pk),
                                         'codes_added': [], 'unverified_quotes': 1,
                                         'detail': 'Answered in peer review, after its first reading was frozen; the '
                                                   'review was used. 1 of its quotes was not found in the document, '
                                                   'so it is never used as evidence.'})
        self.assertEqual((fable['peer']['state'], fable['peer']['codes_added']), ('done', []))
        self.assertEqual((corti['peer'], corti['references'], corti['peer_references']),
                         ({}, {'retrieved': [], 'used': []}, {'retrieved': [], 'used': []}))
        # 1: what each participant retrieved, by phase; 2: what it says it used, checked against that run's own tools -
        # moved by refutation round 4 (R4-SHAPES, shapes-3): a ref its own tool calls never returned is the
        # participant's own text, served only as a short id or by its length
        self.assertEqual(astra['references'], {
            'retrieved': [{'ref': FACT_REF, 'kind': 'fact', 'source_key': 'cms-pfs-rvu26d', 'release': 'RVU26D',
                           'effective_start': '2026-10-01', 'effective_end': '2026-12-31', 'tool': 'cms_code_facts'}],
            'used': [{'ref': FACT_REF, 'use': 'The endoscopic base of the snare removal.', 'retrieved': True},
                     {'ref': PASSAGE_UNRETRIEVED, 'use': 'A rule this run never retrieved.', 'retrieved': False}]})
        self.assertEqual(astra['peer_references'], {
            'retrieved': [{'ref': PASSAGE_REF, 'kind': 'passage', 'source_key': 'cms-ncci-policy-manual-2026',
                           'release': 'Revision 2026', 'effective_start': '2026-01-01', 'effective_end': '2026-12-31',
                           'tool': 'cms_policy_passages'}],
            'used': [{'ref': PASSAGE_REF, 'use': 'The NCCI endoscopy rule.', 'retrieved': True},
                     # its first reading's retrieval never counts for its peer review: cited, not retrieved
                     {'ref': FACT_UNRETRIEVED, 'use': 'Retrieved only by its first reading.', 'retrieved': False}]})
        self.assertEqual(fable['references'], {'retrieved': [], 'used': []})
        # 3: the reconciliation's own retrieval stays reference_validation's, never merged with either
        self.assertEqual(data['harness']['reference_validation']['codes_checked'], 0)

    def test_open_questions_carry_their_candidates_and_their_confirmation(self):
        # moved by refutation round 3 (falsegreen-11): the engine asks 45380's extent too: the questions are told apart
        # by id
        served = {c['id']: c for c in self.detail()['clarifications']}
        clarifications = {fact: served[str(self.questions[fact].pk)]
                          for fact in ('extent', 'service_date', 'performed_status')}
        self.assertEqual({fact: len(c['candidates']) for fact, c in clarifications.items()},
                         {'extent': 2, 'service_date': 1, 'performed_status': 3})
        self.assertEqual(len(served[str(self.questions['by_key']['extent', 'sel:1'].pk)]['candidates']), 2)
        self.assertEqual(clarifications['extent']['candidates'], self.candidates_of('extent'))
        # the exact attestation is served with a verified candidate, never with an unverified one
        self.assertEqual([c['attestation'] for c in clarifications['extent']['candidates']],
                         [candidates.attestation('cecum'), ''])
        self.assertTrue(all(c['confirmation'] is None for c in served.values()))
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            self.assertEqual(self.confirm('extent').status_code, 201)
        data = self.detail()
        extent = next(c for c in data['clarifications'] if c['id'] == str(self.questions['extent'].pk))
        confirmation = models.FindingConfirmation.objects.get()
        self.assertEqual({key: extent['confirmation'][key] for key in ('id', 'value', 'fact', 'located_by',
                                                                       'confirmed_by', 'attestation')},
                         {'id': str(confirmation.pk), 'value': 'cecum', 'fact': 'extent',
                          'located_by': ['astra', 'fable'], 'confirmed_by': self.reviewer.label(),
                          'attestation': candidates.attestation('cecum')})
        self.assertEqual(extent['confirmation']['spans'], confirmation.spans)
        self.assertEqual([c['id'] for c in data['confirmations']], [str(confirmation.pk)])
        summaries = [row['summary'] for row in data['activity']]
        self.assertIn("Finding confirmed from a participant's located passage (not a decision)", summaries)
        event = next(row for row in data['activity'] if row['event'] == 'finding.confirmed')
        self.assertEqual(event['data'], {'fact': 'extent', 'effect': 'reassessment'})

    def test_no_candidate_before_the_final_assessment(self):
        self.persist([self.entry(name) for name in ADAPTERS])
        self.assertTrue(all(c['candidates'] == [] for c in self.detail()['clarifications']))

    def test_proposals_carry_their_phases_and_confirmations_beside_the_three_statuses(self):
        proposals = {p['code']: p for p in self.detail()['assessment']['proposals']}
        snare, biopsy = proposals['45385'], proposals['45380']
        self.assertEqual((snare['phases'], snare['confirmed']), ({'astra': 'independent', 'fable': 'independent'}, []))
        # moved by refutation round 3 (falsegreen-11): the engine records 45380's phases from the readings: this case's
        # Fable proposes it in its first reading (the website fixtures' Fable first proposes it in its peer review)
        self.assertEqual(biopsy['phases'], {'astra': 'independent', 'fable': 'independent'})
        # moved by refutation round 6 (R6-MEANING, the session's D14): 11.4's participant's own proposal ("Corti did not
        # propose this code.") is never a proposal now - tests/test_harness2_r6_meaning.py pins its alternative - and
        # this case's 45380 is Corti's selection, with both participants recorded on it and its origin Corti's own
        self.assertEqual((biopsy['proposed_by'], biopsy['support']['origin']), (['corti', 'astra', 'fable'], 'primary'))
        self.assertNotIn('Corti did not propose this code.', biopsy['rationale'])
        # I4: proposed, reference-checked and approved stay apart; a candidate or a confirmation approves nothing
        self.assertEqual((biopsy['decision_state'], biopsy['decision']), ('undecided', None))
        # moved by refutation round 3 (falsegreen-11): no status candidate verifies on this note: 45380's extent is
        # confirmed instead
        question = self.questions['by_key']['extent', 'sel:1']
        candidate = next(c for c in review.assessment_candidates(self.final)[str(question.pk)] if c['verified'])
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            self.assertEqual(self.confirm('extent', candidate, question=question).status_code, 201)
        biopsy = next(p for p in self.detail()['assessment']['proposals'] if p['code'] == '45380')
        self.assertEqual((biopsy['decision_state'], biopsy['status']), ('undecided', 'needs_clarification'))

    def test_a_peer_stage_under_way(self):
        self.persist([self.entry(name) for name in ADAPTERS])  # assess #1 again: the peer stages follow it
        job = pf.job(self.encounter, self.revision, models.Job.ASTRA_PEER, models.Job.QUEUED)
        rows = self.rows(self.detail())
        self.assertEqual((rows['astra']['peer']['state'], rows['fable']['peer']['state']), ('waiting', 'waiting'))
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.RUNNING)
        rows = self.rows(self.detail())
        self.assertEqual((rows['astra']['peer']['state'], rows['fable']['peer']['state']), ('running', 'waiting'))
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.SUCCEEDED)
        fable_job = pf.job(self.encounter, self.revision, models.Job.FABLE_PEER, models.Job.RUNNING)
        rows = self.rows(self.detail())
        self.assertEqual((rows['astra']['peer'], rows['fable']['peer']['state']), ({}, 'running'))
        models.Job.objects.filter(pk=fable_job.pk).update(state=models.Job.FAILED)
        self.assertEqual(self.rows(self.detail())['fable']['peer'], {})

    def test_a_peer_review_that_was_not_used_says_why(self):
        entries = [self.entry(name, peer=True) for name in ADAPTERS]
        entries[1].update(peer_state='refused', peer_reason='The peer review was not used: it was cut off.',
                          peer_sha256='')
        self.persist(entries)
        fable = self.rows(self.detail())['fable']
        self.assertEqual((fable['peer']['state'], fable['peer']['codes_added']), ('refused', []))
        self.assertEqual(fable['peer']['detail'], 'Peer review: answered; the review was not used: The peer review '
                                                  'was not used: it was cut off.')

    def test_a_corti_only_encounter_reads_as_before_with_empty_additions(self):
        self.persist([jobs.not_configured_record('astra'), jobs.not_configured_record('fable')])
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'):
            data = self.detail()
        self.assertEqual(data['harness']['phase'], 0)
        for row in data['harness']['participants']:
            self.assertEqual((row['peer'], row['references'], row['peer_references']),
                             ({}, {'retrieved': [], 'used': []}, {'retrieved': [], 'used': []}), row['name'])
        self.assertTrue(all(c['candidates'] == [] and c['confirmation'] is None for c in data['clarifications']))
        self.assertEqual(data['confirmations'], [])


@override_settings(**BOTH)
class TraceTests(Harness2Case):
    def test_the_trace_shows_exchanges_tool_calls_peer_reviews_and_each_assessment_s_frozen_list(self):
        response = self.client_for(self.owner).get(f'/ops/api/encounters/{self.encounter.pk}/trace')
        self.assertEqual(response.status_code, 200, response.content)
        trace = response.json()
        astra = next(p for p in trace['participants'] if p['name'] == 'astra')
        first, peer_run = astra['runs']
        self.assertEqual((first['purpose'], peer_run['purpose'], first['mode'], peer_run['mode']),
                         ('independent', 'peer_review', 'replay', 'replay'))
        self.assertEqual([e['turn'] for e in first['exchanges']], [1, 2])
        self.assertEqual(first['exchanges'][0]['tool_calls'], [{
            'call_id': 'call_1_1', 'tool': 'cms_code_facts', 'arguments': {'codes': ['45385'], 'date_of_service': ''},
            'refs': [FACT_REF], 'result_sha256': sha(canonical_body(FACTS_RESULT)),
            'executed_at': first['exchanges'][0]['tool_calls'][0]['executed_at']}])
        self.assertEqual(first['exchanges'][1]['tool_calls'], [])
        # moved by refutation round 4 (R4-SHAPES, shapes-3): a ref its own tool calls never returned, by its length
        self.assertEqual(first['reading']['references_used'],
                         [{'ref': FACT_REF, 'use': 'The endoscopic base of the snare removal.', 'retrieved': True},
                          {'ref': PASSAGE_UNRETRIEVED, 'use': 'A rule this run never retrieved.', 'retrieved': False}])
        self.assertIsNone(first['review'])
        self.assertIsNone(peer_run['reading'])
        expected = json.loads(json.dumps(to_jsonable(review.stored_peer_review(self.peer_runs['astra'])[0])))
        # each additional code with the phase its participant first proposed it in (R2-WORDING truth-8) - moved by
        # refutation round 5 (R5-ACCOUNT, the session's D12): 45381's quote is in no document, so it was proposed in
        # neither phase, '' (listed in peer review), where it was 'peer_review'
        expected['additional_codes'] = [dict(item, phase='') for item in expected['additional_codes']]
        # moved by refutation round 4 (R4-SHAPES, shapes-3): FACT_REF, which only its first reading retrieved, is
        # served by its length
        self.assertEqual([(item['ref'], item['retrieved']) for item in expected['references_used']],
                         [(PASSAGE_REF, True), (FACT_REF, False)])
        expected['references_used'][1]['ref'] = FACT_UNRETRIEVED
        self.assertEqual(peer_run['review'], expected)
        self.assertEqual([a['question_id'] for a in peer_run['review']['answers']],
                         [str(self.first.clarifications.get(fact=fact, proposal__key=key).pk) for fact, key in
                          (('extent', 'sel:0'), ('service_date', None), ('performed_status', 'sel:1'))])
        self.assertEqual([c['code'] for c in peer_run['review']['additional_codes']], ['45381'])
        self.assertEqual(sorted(name for name, _ in peer_run['review']['frozen_inputs']),
                         ['astra', 'corti', 'cpt_studio', 'fable', 'revision'])
        corti = next(p for p in trace['participants'] if p['name'] == 'corti')
        self.assertEqual(corti['runs'][0]['exchanges'], [])
        assessments = trace['assessments']
        self.assertEqual([(a['id'], a['phase'], a['final'], a['current']) for a in assessments],
                         [(str(self.first.pk), 1, False, False), (str(self.final.pk), 2, True, True)])
        self.assertEqual(assessments[0]['frozen'], self.frozen)
        self.assertEqual(assessments[1]['frozen'], self.frozen)


NOT_SHOWN = f'a value of {len(DESCRIPTOR_LIKE)} characters (not shown)'


@override_settings(**BOTH)
class DescriptorLikeTextTests(Harness2Case):
    """A participant can write any text into a field CPT Studio reads as a code or an id: the reading schemas leave them
    plain strings, and the readers keep a code that is not five characters as given. Such text is served nowhere (I9;
    refutation r1 IND-1): a participant row lists only the codes the engine lists, saying how many it does not, and the
    owner's trace names each longer code, modifier or service id by its length, as the reader's own problems do."""

    def first_reading(self, name):
        data = super().first_reading(name)
        if name == 'astra':
            data['codes'][0]['code'] = DESCRIPTOR_LIKE
            data['codes'][1].update(modifiers=['59', DESCRIPTOR_LIKE], service_ids=['s1', DESCRIPTOR_LIKE])
            data['services'].append(dict(data['services'][0], id=DESCRIPTOR_LIKE))
            data['not_coded'] = [{'service_ids': [DESCRIPTOR_LIKE], 'code': DESCRIPTOR_LIKE, 'reason': 'other',
                                  'evidence': []}]
            data['clarifications'] = [{'question': 'Synthetic question.', 'why': 'Synthetic reason.',
                                       'service_ids': [DESCRIPTOR_LIKE], 'evidence': []}]
        return data

    def peer_answer(self, name):
        data = super().peer_answer(name)
        if name == 'astra':
            data['code_positions'].append({'code': DESCRIPTOR_LIKE, 'position': 'disputes',
                                           'reason': 'Synthetic reason.', 'evidence': []})
            data['additional_codes'].append({'code': DESCRIPTOR_LIKE, 'modifiers': [DESCRIPTOR_LIKE], 'units': 1,
                                             'service_ids': [DESCRIPTOR_LIKE], 'basis': 'Synthetic basis.',
                                             'evidence': [], 'confidence': 'low'})
        return data

    def test_the_readings_keep_it_as_given(self):
        self.assertEqual(self.readings['astra'].codes[0].code, DESCRIPTOR_LIKE)
        self.assertIn(DESCRIPTOR_LIKE, [item['code'] for item in self.final.participants[0]['codes']])

    def test_a_participant_row_lists_only_the_codes_the_engine_lists_for_every_role(self):
        for user in (self.reviewer, self.viewer, self.owner):
            with self.subTest(user=user.username):
                response = self.client_for(user).get(f'/ops/api/encounters/{self.encounter.pk}')
                self.assertEqual(response.status_code, 200, response.content)
                self.assertNotIn(DESCRIPTOR_LIKE, response.content.decode('utf-8'))
                astra = next(row for row in response.json()['harness']['participants'] if row['name'] == 'astra')
                self.assertEqual(astra['codes'], ['45380'])
                self.assertTrue(astra['detail'].endswith(UNLISTED_ONE), astra['detail'])

    def test_the_owner_s_trace_names_each_long_code_like_value_by_its_length(self):
        response = self.client_for(self.owner).get(f'/ops/api/encounters/{self.encounter.pk}/trace')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn(DESCRIPTOR_LIKE, response.content.decode('utf-8'))
        first, peer_run = next(p for p in response.json()['participants'] if p['name'] == 'astra')['runs']
        reading = first['reading']
        self.assertEqual([item['code'] for item in reading['codes']], [NOT_SHOWN, '45380'])
        # a withheld service id keeps one name of CPT Studio's own wherever the reading mentions it (refutation round 3:
        # the trace shows code-like fields in the strict shapes a peer request does, participants.peer.ShownIds - this
        # pin moved from the bare length to that name)
        withheld_id = f'id 1: {NOT_SHOWN}'
        self.assertEqual((reading['codes'][1]['modifiers'], reading['codes'][1]['service_ids']),
                         (['59', NOT_SHOWN], ['s1', withheld_id]))
        self.assertEqual([service['id'] for service in reading['services']], ['s1', withheld_id])
        self.assertEqual([(item['code'], item['service_ids']) for item in reading['not_coded']],
                         [(NOT_SHOWN, [withheld_id])])
        self.assertEqual([item['service_ids'] for item in reading['questions']], [[withheld_id]])
        added = peer_run['review']['additional_codes']
        self.assertEqual([(item['code'], item['modifiers'], item['service_ids']) for item in added],
                         [('45381', [], ['s1']), (NOT_SHOWN, [NOT_SHOWN], [withheld_id])])
        self.assertEqual([item['code'] for item in peer_run['review']['positions']], ['45380', NOT_SHOWN])
        # the reader's own problems already name it by its length
        self.assertIn(f'codes[0] (a value of {len(DESCRIPTOR_LIKE)} characters) is not a five-character CPT code; it '
                      'is kept as given.', reading['problems'])

    def test_neither_report_carries_it(self):
        from studio import reports

        snap = reports.snapshot(self.encounter, 'draft')
        for content in (reports.render_txt(snap), reports.render_csv(snap)):
            self.assertNotIn(DESCRIPTOR_LIKE, content.decode('utf-8'))


# --- decisions carry between FINAL assessments only (refutation r1 repair plan, Q1) -----------------------------------
#
# The real pipeline (tests.test_harness2_pipeline's replayed participants, scripted loops, the real engine): a context
# change makes a new assess #1, which owes the peer stages, then its assess #2. Persisted, assess #1 used to carry or
# invalidate the decisions of the final assessment before it - and assess #1 does not have the codes a peer review adds,
# so a code whose checks read them (45385's endoscopic base reads 45378, which Fable adds in peer review) had its
# approval invalidated there, and assess #2 had nothing left to carry.

NOT_FINAL = 'The peer reviews of this document have not finished: a decision is recorded on its final assessment.'
NOT_FINAL_BLOCKER = 'The peer reviews have not finished: decisions are recorded on the final assessment'


class _Decisions:
    def detail(self, encounter_id):
        response = self.client.get(f'/ops/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def proposal_of(self, encounter_id, code):
        return next(p for p in self.detail(encounter_id)['assessment']['proposals'] if p['code'] == code)

    def decide(self, encounter_id, code, action='approve'):
        proposal = self.proposal_of(encounter_id, code)
        body = {'proposal_id': proposal['id'], 'action': action}
        if action == 'approve':
            body['acknowledgement'] = review.ACKNOWLEDGEMENTS['human']
        return self.post(f'/api/encounters/{encounter_id}/decisions', body)

    def approve(self, encounter_id, code):
        response = self.decide(encounter_id, code)
        self.assertEqual(response.status_code, 201, response.content)
        return models.Decision.objects.get(pk=response.json()['id'])

    def created(self, assessment):
        """(carried, invalidated) as persisting ``assessment`` recorded them (its 'assessment.created' audit row)."""
        event = models.AuditEvent.objects.get(event='assessment.created', data__assessment=str(assessment.pk))
        return event.data['carried'], event.data['invalidated']

    def change_context(self, encounter_id, **values):
        before = len(self.assessments(encounter_id))
        response = self.post(f'/api/encounters/{encounter_id}/context', values)
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        later = self.assessments(encounter_id)[before:]
        self.assertEqual([jobs.assessment_phase(a) for a in later], [1, 2])  # a new assess #1, then its assess #2
        return later


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class DecisionCarryTests(_Decisions, PipelineColonCase):
    def confirm_extent(self, encounter_id):
        """A reviewer confirms sel:0's extent (45385) through the endpoint, from the verified candidate Astra's peer
        review located (HARNESS.md 12.5); the re-assessment it queues runs."""
        detail = self.detail(encounter_id)
        snare = next(p['id'] for p in detail['assessment']['proposals'] if p['key'] == 'sel:0')
        question = next(c for c in detail['clarifications'] if c['proposal_id'] == snare and c['fact'] == 'extent')
        candidate = next(c for c in question['candidates'] if c['verified'])
        attestation = candidates.attestation(candidate['value'])
        response = self.post(f'/api/encounters/{encounter_id}/clarifications/{question["id"]}/confirm',
                             {'candidate_id': candidate['id'], 'attestation': attestation})
        self.assertEqual(response.status_code, 201, response.content)
        drain()

    def test_an_approval_crosses_the_intermediate_assess_one_and_the_next_final_assessment_carries_it(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        self.confirm_extent(encounter_id)
        approved = self.approve(encounter_id, '45385')  # on the final assessment, which reads Fable's 45378
        first, final = self.change_context(encounter_id, billing_context='professional')
        # assess #1 owed the peer stages: it neither carried nor invalidated a decision, and none is recorded on it
        self.assertEqual(self.created(first), (0, 0))
        self.assertFalse(first.decisions.exists())
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision=approved).exists())
        # the final assessment carried it from the last final one, where its fingerprint is unchanged
        carried = final.decisions.get()
        self.assertEqual((carried.action, carried.carried_from_id, carried.proposal.code, self.created(final)),
                         ('approve', approved.pk, '45385', (1, 0)))
        self.assertEqual(self.proposal_of(encounter_id, '45385')['decision_state'], 'approved')


class DecisionInvalidationTests(_Decisions, PipelineCase):
    def test_an_approval_whose_final_fingerprint_changed_is_invalidated_by_the_final_assessment_with_its_reason(self):
        encounter_id = self.create()
        drain()
        approved = self.approve(encounter_id, '99213')
        first, final = self.change_context(encounter_id, billing_context='facility')  # an E/M reads the billing context
        self.assertEqual(self.created(first), (0, 0))  # assess #1 invalidates nothing
        self.assertEqual(self.created(final), (0, 1))
        invalidation = models.DecisionInvalidation.objects.get(decision=approved)
        self.assertEqual(invalidation.by_context_id, final.context_id)
        self.assertTrue(invalidation.reason.startswith('Re-assessed after changes (billing context'),
                        invalidation.reason)
        self.assertFalse(final.decisions.exists())
        self.assertEqual(self.proposal_of(encounter_id, '99213')['decision_state'], 'undecided')

    def stop_after_assess_one(self, encounter_id):
        """Run the chain to its assess #1, whose first peer stage is then queued, and Stop it there."""
        jobs.run_job(self.run_until('assess'))
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        first = self.encounter(encounter_id).current_assessment
        self.assertEqual((jobs.assessment_phase(first), review.is_final(first), self.jobs_of(encounter_id)[-1].kind),
                         (1, False, 'astra_peer'))
        return first

    def test_an_addendum_invalidates_the_decisions_the_last_final_assessment_holds(self):
        # while an assess #1 that owes peer stages is current, the current decisions are still the final one's: a new
        # revision invalidates them there, at once (never left current until a later final assessment)
        encounter_id = self.create()
        drain()
        approved = self.approve(encounter_id, '99213')
        response = self.post(f'/api/encounters/{encounter_id}/context', {'billing_context': 'facility'})
        self.assertEqual(response.status_code, 201, response.content)
        self.stop_after_assess_one(encounter_id)
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision=approved).exists())
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': 'Addendum (synthetic): no change to the visit.', 'clarification_id': None,
                              'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.encounter(encounter_id).current_revision
        invalidation = models.DecisionInvalidation.objects.get(decision=approved)
        self.assertEqual((invalidation.by_revision_id, invalidation.reason),
                         (revision.pk, review.revised_reason(revision)))

    def test_no_decision_is_recorded_on_an_assessment_whose_peer_reviews_have_not_finished(self):
        encounter_id = self.create()
        self.stop_after_assess_one(encounter_id)
        detail = self.detail(encounter_id)
        self.assertEqual([p['allowed_actions'] for p in detail['assessment']['proposals']],
                         [[] for _ in detail['assessment']['proposals']])
        response = self.decide(encounter_id, '99213')
        # moved by the customer interface change (CORE-UX-DESIGN.md 5): a refusal reaches a member in the customer vocabulary
        self.assertEqual((response.status_code, response.json()['error']), (409, customer_api.customer_error(NOT_FINAL)))
        self.assertFalse(models.Decision.objects.filter(encounter_id=encounter_id).exists())
        self.assertIn(NOT_FINAL_BLOCKER, detail['readiness']['blockers'])
        # once the peer reviews are assessed, the final assessment takes the decision
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertTrue(review.is_final(self.encounter(encounter_id).current_assessment))
        self.approve(encounter_id, '99213')
        self.assertNotIn(NOT_FINAL_BLOCKER, self.detail(encounter_id)['readiness']['blockers'])
