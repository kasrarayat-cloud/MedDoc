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

from studio import candidates, jobs, models, review
from studio.participants import prompt
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.providers.base import canonical_body
from studio.types import ClarificationSpec, ExtractionResult, sha256_json
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_participants_support import NOTE, PAGES, astra_with, fable_with, fixture_reading

BOTH = dict(ASTRA_MODE='replay', FABLE_MODE='replay')
MODELS = {'astra': 'gpt-6-astra', 'fable': 'claude-fable-5-1'}
ENDPOINTS = {'astra': 'https://api.openai.com/v1/responses', 'fable': 'https://api.anthropic.com/v1/messages'}
ADAPTERS = {'astra': AstraParticipant, 'fable': FableParticipant}
DATE_QUOTE = 'Date of service: 2026-10-21'
CECUM_QUOTE = 'The colonoscope was advanced to the cecum.'
SNARE_QUOTE = ('A 6 mm sessile polyp in the ascending colon was removed with a cold snare and retrieved for\n'
               'pathology.')
RECTUM_QUOTE = 'A 3 mm polyp in the rectum was biopsied with cold forceps.'
PREP_QUOTE = 'Bowel preparation was good.'
FACT_REF = 'fact:cms-pfs-rvu26d:45385:mult_proc'
PASSAGE_REF = 'ncci-2026-ch6-c-1'
FACTS_RESULT = {'codes': [{'code': '45385', 'facts': [
    {'field': 'pfs.mult_proc', 'value': '3', 'source_key': 'cms-pfs-rvu26d', 'release': 'RVU26D',
     'effective_start': '2026-10-01', 'effective_end': '2026-12-31', 'sha256': '0' * 64}]}]}
PASSAGES_RESULT = {'topic': 'ncci_endoscopy_rules', 'passages': [
    {'passage_key': PASSAGE_REF, 'source_key': 'cms-ncci-policy-manual-2026', 'release': 'Revision 2026',
     'effective_start': '2026-01-01', 'effective_end': '2026-12-31', 'section': 'Chapter VI §C.1', 'page': '6',
     'sha256': '1' * 64, 'text': 'Synthetic passage text for the tests.'}]}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_reading(name):
    """The fixture reading (tests/fixtures/participants) with references used: one its run retrieves, one not."""
    data = fixture_reading()
    data['references_used'] = ([{'ref': FACT_REF, 'use': 'The endoscopic base of the snare removal.'},
                                {'ref': PASSAGE_REF, 'use': 'A rule this run never retrieved.'}]
                               if name == 'astra' else [])
    return data


class Harness2Case(TestCase):
    """One encounter carried through harness@2 as the pipeline records it: Corti's run; Astra's and Fable's frozen first
    readings (Astra's with a tool call); assess #1 with three open questions; both peer reviews (Astra's with a tool
    call), built from assess #1's questions; and assess #2, the final assessment."""

    def setUp(self):
        self.ws = f.workspace()
        self.owner = f.member(self.ws, f.user('owner2b'), role=models.Membership.OWNER)
        self.reviewer = f.member(self.ws, f.user('reviewer2b'))
        self.viewer = f.member(self.ws, f.user('viewer2b'), role=models.Membership.VIEWER)
        self.encounter = f.encounter(self.ws, self.reviewer, title='Synthetic colonoscopy for harness@2')
        self.revision = f.pasted_revision(self.encounter, self.reviewer, NOTE, extract=False)
        f.record(self.revision, ExtractionResult(status='ok', method='paste', text=NOTE, pages=PAGES))
        self.revision.refresh_from_db()
        self.context = pf.context(self.encounter, self.revision)
        self.corti = pf.provider_run(self.encounter, self.revision)
        self.now = timezone.now()
        self.adapters = {name: ADAPTERS[name]('/nonexistent/never-read.env') for name in ADAPTERS}
        self.runs, self.readings, self.requests = {}, {}, {}
        for name in ADAPTERS:
            request = self.adapters[name].build_request(NOTE, PAGES, 'paste', None)
            data = (astra_with if name == 'astra' else fable_with)(first_reading(name))
            run = self.make_run(name, request, data, purpose=models.ProviderRun.INDEPENDENT)
            calls = [('cms_code_facts', {'codes': ['45385'], 'date_of_service': ''}, FACTS_RESULT, [FACT_REF])]
            self.exchanges(run, request.body, data, calls if name == 'astra' else [])
            self.runs[name], self.requests[name] = run, request
            self.readings[name] = self.adapters[name].read(request, data, frozenset(review.run_refs(run)))
        self.frozen = sorted([['astra', sha256_json(self.readings['astra'])], ['corti', self.corti.response_sha256],
                              ['fable', sha256_json(self.readings['fable'])],
                              ['revision', self.revision.text_sha256]])
        self.first = self.persist([self.entry(name) for name in ADAPTERS])
        self.peer_runs, self.reviews = {}, {}
        for name in ADAPTERS:
            self.peer_review(name)
        self.final = self.persist([self.entry(name, peer=True) for name in ADAPTERS])
        self.questions = {c.fact: c for c in self.final.clarifications.all()}

    # --- the rows -----------------------------------------------------------------------------------------------------

    def make_run(self, name, request, data, *, purpose):
        return models.ProviderRun.objects.create(
            encounter=self.encounter, revision=self.revision, provider=name, adapter_version=request.adapter_version,
            request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
            state=models.ProviderRun.SUCCEEDED, sent=True, http_status=200, response_bytes=data,
            response_sha256=sha(data), latency_ms=12.5, usage={'input_tokens': 2000, 'output_tokens': 200},
            usage_basis='provider_reported_tokens_summed_over_exchanges', purpose=purpose, scope={'mode': 'replay'},
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

    def result(self):
        extent = pf.clarification('extent', family='gi.colonoscopy', proposal_key='sel:0',
                                  question='Colonoscopy: confirm the furthest extent reached.',
                                  reason='The extent reached is not documented; the Colonoscopy profile requires it.')
        status = pf.clarification('performed_status', family='gi.colonoscopy', proposal_key='sel:1',
                                  question='Colonoscopy: confirm whether 45380 was performed at this encounter.',
                                  reason='Whether the biopsy was performed at this encounter is in doubt.')
        date_question = ClarificationSpec(scope='encounter', fact='service_date',
                                          question='Confirm the date of service.',
                                          reason='The date of service is in question.')
        snare = replace(pf.proposal('sel:0', '45385', ['was removed with a cold snare'], text=NOTE,
                                    status='needs_clarification', clarifications=(extent,)),
                        support={'origin': 'primary', 'proposed_by': ['corti', 'astra', 'fable'],
                                 'phases': {'astra': 'independent', 'fable': 'independent'}})
        biopsy = replace(pf.proposal('sel:1', '45380', [RECTUM_QUOTE], text=NOTE, status='needs_clarification',
                                     clarifications=(status,),
                                     rationale='Proposed by Astra (independent participant) and Fable after peer '
                                               'review; Corti did not propose this code.'),
                         support={'origin': 'participant', 'proposed_by': ['astra', 'fable'],
                                  'phases': {'astra': 'independent', 'fable': 'peer_review'}, 'confirmed': []})
        return pf.result(snare, biopsy, clarifications=(date_question,))

    def entry(self, name, *, peer=False):
        """An Assessment.participants entry in the 12.3 shape: harness@1's keys, the frozen record, and on assess #2 the
        peer review."""
        run, reading = self.runs[name], self.readings[name]
        out = {'name': name, 'state': 'read', 'run': str(run.pk), 'adapter_version': run.adapter_version,
               'requested_model': MODELS[name], 'returned_model': MODELS[name],
               'unverified_quotes': reading.unverified_quotes, 'reason': '',
               'codes': [{'code': item.code, 'quote': ''} for item in reading.codes], 'not_coded': [],
               'reading_sha256': sha256_json(reading), 'exchanges': run.exchanges.count(),
               'tool_calls': models.ToolCall.objects.filter(exchange__run=run).count(), 'frozen': self.frozen}
        if peer:
            peer_run, peer_review = self.peer_runs[name], self.reviews[name]
            out.update(peer_state='read', peer_run=str(peer_run.pk), peer_reason='',
                       peer_sha256=sha256_json(peer_review), peer_unverified_quotes=peer_review.unverified_quotes)
        return out

    def persist(self, entries, result=None):
        self.encounter.refresh_from_db()
        return review.persist_assessment(encounter=self.encounter, revision=self.revision, context=self.context,
                                         routing_run=pf.routing(self.revision), provider_run=self.corti,
                                         result=result or self.result(), participants=entries, retrieval=[])

    def cpt_studio(self):
        held = [{'key': p.key, 'code': p.code, 'status': p.status,
                 'reasons': [c['detail'] for c in p.checks if c['status'] != 'pass']}
                for p in self.first.proposals.filter(status='needs_clarification')]
        return {'open_questions': [{'question_id': str(c.pk), 'scope': c.scope, 'fact': c.fact, 'family': c.family,
                                    'proposal_key': c.proposal.key if c.proposal_id else '', 'question': c.question,
                                    'reason': c.reason} for c in self.first.clarifications.order_by('created_at')],
                'held': held, 'excluded': []}

    def peer_answer(self, name):
        asked = {c.fact: str(c.pk) for c in self.first.clarifications.all()}
        if name == 'fable':
            return {'question_answers': [{'question_id': asked['extent'], 'settled': True, 'value': 'Cecum',
                                          'evidence': [CECUM_QUOTE]}],
                    'code_positions': [], 'additional_codes': [], 'references_used': []}
        return {'question_answers': [
                    {'question_id': asked['extent'], 'settled': True, 'value': 'cecum', 'evidence': [CECUM_QUOTE]},
                    {'question_id': asked['service_date'], 'settled': True, 'value': '2026-10-21',
                     'evidence': [DATE_QUOTE]},
                    {'question_id': asked['performed_status'], 'settled': True, 'value': 'performed',
                     'evidence': [RECTUM_QUOTE]}],
                'code_positions': [{'code': '45380', 'position': 'supports', 'reason': 'Participant wording.',
                                    'evidence': [RECTUM_QUOTE]}],
                'additional_codes': [{'code': '45381', 'modifiers': [], 'units': 1, 'service_ids': ['s1'],
                                      'basis': 'Participant wording.', 'evidence': [PREP_QUOTE],
                                      'confidence': 'low'}],
                'references_used': [{'ref': PASSAGE_REF, 'use': 'The NCCI endoscopy rule.'},
                                    {'ref': FACT_REF, 'use': 'Retrieved only by its first reading.'}]}

    def peer_review(self, name):
        other = 'fable' if name == 'astra' else 'astra'
        cpt_studio = self.cpt_studio()
        peers = {'corti': {'codes': [{'code': '45385', 'modifiers': [], 'units': 1,
                                      'evidence': ['was removed with a cold snare']}]},
                 other: prompt.reading_answer(self.readings[other])}
        frozen = self.frozen + [['cpt_studio', sha256_json(cpt_studio)]]
        request = self.adapters[name].build_peer_request(NOTE, PAGES, 'paste', self.readings[name], peers, cpt_studio,
                                                         frozen)
        data = (astra_with if name == 'astra' else fable_with)(self.peer_answer(name))
        run = self.make_run(name, request, data, purpose=models.ProviderRun.PEER_REVIEW)
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


@override_settings(**BOTH)
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
        self.assertEqual([(c['value'], c['verified'], c['phase']) for c in status],
                         [('performed', True, 'independent'), ('performed', True, 'independent'),
                          ('performed', True, 'peer_review')])

    def test_none_before_the_final_assessment_nor_for_a_corti_only_one(self):
        self.assertEqual(review.assessment_candidates(self.first), {})
        corti_only = self.persist([jobs.not_configured_record('astra'), jobs.not_configured_record('fable')])
        self.assertEqual(review.assessment_phase(corti_only), 0)
        self.assertEqual(review.assessment_candidates(corti_only), {})

    def test_a_frozen_reading_that_no_longer_matches_its_recorded_sha256_is_not_used(self):
        entries = [self.entry(name, peer=True) for name in ADAPTERS]
        entries[1]['reading_sha256'] = '0' * 64
        changed = self.persist(entries)
        with self.assertLogs('studio.review', level='WARNING'):
            readings, reviews = review.frozen_inputs(changed)
        self.assertEqual(([r.name for r in readings], [name for name, _, _ in reviews]), (['astra'], ['astra']))


@override_settings(**BOTH)
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
        earlier = self.first.clarifications.get(fact='extent')
        self.assertEqual(earlier.state, models.Clarification.OPEN)  # re-raised by assess #2, still open on assess #1
        self.assertRefused(self.confirm('extent', question=earlier), 409, 'earlier assessment')

    def test_before_the_final_assessment(self):
        phase_one = self.persist([self.entry(name) for name in ADAPTERS])  # an assess #1 whose peer stages follow
        self.assertFalse(review.is_final(phase_one))
        question = phase_one.clarifications.get(fact='extent')
        self.assertRefused(self.confirm('extent', question=question), 409, 'peer reviews of this document have not')

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
        with mock.patch('studio.jobs.reassess_after_confirmation', side_effect=jobs.Refused('Synthetic refusal.')):
            self.assertRefused(self.confirm('extent'), 409, 'Synthetic refusal.')
        with mock.patch('studio.jobs.change_context', side_effect=jobs.Refused('Synthetic context refusal.')):
            self.assertRefused(self.confirm('service_date'), 409, 'Synthetic context refusal.')


@override_settings(**BOTH)
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
        self.assertEqual(NOTE[candidate['spans'][0]['start']:candidate['spans'][0]['end']], CECUM_QUOTE)
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

    def test_an_owner_may_confirm_a_status(self):
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            response = self.confirm('performed_status', self.verified('performed_status', RECTUM_QUOTE),
                                    user=self.owner)
        self.assertEqual(response.status_code, 201, response.content)
        confirmation = models.FindingConfirmation.objects.get()
        self.assertEqual((confirmation.fact, confirmation.value, confirmation.located_by, confirmation.proposal_key),
                         ('performed_status', 'performed', ['astra'], 'sel:1'))

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
        self.assertFalse(models.Decision.objects.exists())
