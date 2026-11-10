"""Refutation round 3, R3-CONF: this release offers no reviewer confirmation (HARNESS.md 12.10, the session's D7).

Three rounds of refutation each found blocking defects in the check that called a participant's located passage
"Verified", each in the previous round's repair (round 3: status-1..4, facts-1..8; peer-2 rode on a confirmation into a
later chain's peer requests). A question is asked because CPT Studio's own readers did not establish its answer, so the
check cannot converge. The release default, settings.STUDIO_OFFER_CONFIRMATIONS (a code-level False), is pinned here
as the default:

- the setting is a literal that no environment variable or installation file changes, and only the literal True is on;
- the confirmation endpoint refuses (409) with one fixed sentence, after the session and the encounter's scoping and
  before it reads the body, the member's role, the question or the candidate; nothing is recorded - no
  FindingConfirmation, audit row, job, provider run, exchange, tool call, context or decision;
- review.confirm_finding and jobs.reassess_after_confirmation refuse the same way;
- a stored FindingConfirmation (one a test writes) is never read: the assessment is the one these inputs make with no
  confirmation;
- candidates are still served - the participants' located passages, exact slices of the revision with their whole
  sentences - but unchecked: no check that decided "verified" runs, every one is verified false with one fixed why and
  no attestation, and can_confirm is false for every member (moved by refutation round 4, the session's D8: no
  candidate is served at all - a located passage's value was CPT Studio's own inference from a reading, shown as a
  participant's answer - and can_confirm is false for every member; tests/test_harness2_r4_conf.py);
- a later chain's peer requests carry no confirmation wording (peer-2 is unreachable).

Each test failed on the base 624754eb1 (the endpoint recorded a confirmation and queued its re-assessment, the engine
read a stored row, the candidates were checked and verified, a reviewer could confirm). The dormant path's own tests run
with override_settings(STUDIO_OFFER_CONFIRMATIONS=True) and keep their assertions. The page is pinned by the
'// refutation round 3, R3-CONF' block of tests/frontend/app.test.cjs on the regenerated fixtures.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake; Astra and Fable are the real
replay adapters (tests.test_harness2_api's recorded rows, tests.test_harness2_pipeline's scripted loops).
"""
import ast
import importlib.util
import json
import os
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import Client, SimpleTestCase, override_settings

from studio import candidates, jobs, models, review
from studio.gi import context as gi_context
from studio.types import EvidenceSpan, LocatedQuote, PageSpan, ParticipantReading, ParticipantService, sha256_json
from tests import test_harness2_api as h2
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.test_frontend import candidate_id
from tests.test_harness2_pipeline import HEAD, TWO_EXTENTS, TWO_EXTENTS_INTERPRETATIONS, ColonCase, answered, reading
from tests.test_harness2_pipeline import Harness2Case as PipelineCase
from tests.test_harness2_r2_peer import EMPTY_PEER, posted_bodies
from tests.test_harness_pipeline import TIME_QUOTE
from tests.test_pipeline_api import RecordedInterpretation, drain

ROOT = Path(settings.BASE_DIR)
SETTINGS_FILE = ROOT / 'cptstudio' / 'settings.py'
# What an installation is given (the installer and the image's deployment files): none of it names the setting.
INSTALLATION_FILES = (ROOT / 'ops' / 'install.py', *sorted(p for p in (ROOT / 'deploy').rglob('*') if p.is_file()))
# The one fixed sentence the endpoint, review.confirm_finding and the re-assessment refuse with, and the one why every
# candidate carries - written out here, so a change to either is a change to this pin.
# (moved at integration: a date of service is also answered in the encounter context, so the sentence says so)
# (moved by refutation round 4, d7-3: the sentence says only what happened - an addendum does not settle a documented
# conflict or an included base code, and a member's setting is corrected in the encounter context, so no way a question
# is settled is named; tests/test_harness2_r4_conf.py)
NOT_OFFERED = 'This release offers no reviewer confirmation, so nothing was recorded.'
DORMANT = dict(STUDIO_OFFER_CONFIRMATIONS=True)  # the dormant confirmation path, as its own tests run it
COUNTED = (models.FindingConfirmation, models.AuditEvent, models.Job, models.ProviderRun, models.ProviderExchange,
           models.ToolCall, models.EncounterContext, models.Assessment, models.Clarification, models.Decision)


def counts():
    return {model.__name__: model.objects.count() for model in COUNTED}


class SettingTests(SimpleTestCase):
    def test_the_release_default_is_a_code_level_false(self):
        self.assertIs(settings.STUDIO_OFFER_CONFIRMATIONS, False)
        self.assertIs(review.confirmations_offered(), False)
        tree = ast.parse(SETTINGS_FILE.read_text(encoding='utf-8'))
        named = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Name) and node.id == 'STUDIO_OFFER_CONFIRMATIONS']
        assigned = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'STUDIO_OFFER_CONFIRMATIONS' for t in node.targets)]
        # assigned once, a literal, and named nowhere else: nothing reads it from the environment or a file
        self.assertEqual((len(named), len(assigned)), (1, 1))
        self.assertIsInstance(assigned[0].value, ast.Constant)
        self.assertIs(assigned[0].value.value, False)
        # moved by refutation round 4 (the session's D8): the one why every served candidate carried is gone with the
        # candidates
        self.assertEqual(review.CONFIRMATIONS_NOT_OFFERED, NOT_OFFERED)
        self.assertFalse(hasattr(review, 'UNCHECKED_WHY'))

    def test_no_environment_variable_or_installation_file_turns_it_on(self):
        variables = {'CPT_STUDIO_STUDIO_OFFER_CONFIRMATIONS': '1', 'CPT_STUDIO_OFFER_CONFIRMATIONS': 'true',
                     'STUDIO_OFFER_CONFIRMATIONS': 'True', 'CPT_STUDIO_CONFIRMATIONS': '1',
                     'CPT_STUDIO_CONFIRMATION_MODE': 'live'}
        with mock.patch.dict(os.environ, variables):  # the settings module read again, as a process would start
            spec = importlib.util.spec_from_file_location('r3conf_settings_probe', SETTINGS_FILE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        self.assertIs(module.STUDIO_OFFER_CONFIRMATIONS, False)
        self.assertTrue(INSTALLATION_FILES)
        for path in INSTALLATION_FILES:
            with self.subTest(path=path.name):
                self.assertNotIn('OFFER_CONFIRMATIONS', path.read_bytes().decode('utf-8', 'replace'))

    def test_only_the_literal_true_turns_on_the_dormant_path(self):
        self.assertIs(review.confirmations_offered(), False)  # the release default is not it
        for value in ('True', 'true', '1', 1, 'yes', [True], None, object()):
            with self.subTest(value=value), override_settings(STUDIO_OFFER_CONFIRMATIONS=value):
                self.assertIs(review.confirmations_offered(), False)
        with override_settings(**DORMANT):
            self.assertIs(review.confirmations_offered(), True)


# --- the endpoint and the function refuse first; nothing is recorded --------------------------------------------------

@override_settings(**h2.BOTH)
class EndpointTests(h2.Harness2Case):
    def dormant_verified(self, question):
        """The verified candidate the dormant path serves for ``question``: one a reviewer confirmed on the base."""
        with override_settings(**DORMANT):
            return next(c for c in review.assessment_candidates(self.final)[str(question.pk)] if c['verified'])

    def url(self, fact):
        return f'/api/encounters/{self.encounter.pk}/clarifications/{self.questions[fact].pk}/confirm'

    def test_a_reviewer_s_confirmation_of_a_served_candidate_is_refused_and_nothing_is_recorded(self):
        # every question the dormant path offers a verified candidate for: 45385's and 45380's extent and the date
        offered = {key: (question, self.dormant_verified(question))
                   for key, question in self.questions['by_key'].items() if key[0] != 'performed_status'}
        self.assertEqual(sorted(offered), [('extent', 'sel:0'), ('extent', 'sel:1'), ('service_date', '')])
        self.encounter.refresh_from_db()
        before, context, values = counts(), self.encounter.current_context_id, dict(self.encounter.user_values or {})
        for user in (self.reviewer, self.owner):
            for (fact, key), (question, candidate) in offered.items():
                with self.subTest(user=user.username, fact=fact, key=key):
                    response = self.confirm(fact, candidate, user=user, question=question)
                    self.assertEqual(response.status_code, 409, response.content)
                    self.assertEqual(response.json()['error'], NOT_OFFERED)
        self.encounter.refresh_from_db()
        self.assertEqual(counts(), before)
        self.assertEqual((self.encounter.current_context_id, self.encounter.user_values or {}), (context, values))
        self.assertFalse(models.AuditEvent.objects.filter(event__in=('finding.confirmed', 'context.changed')).exists())
        self.assertEqual(review.revision_confirmations(self.revision), [])

    def test_it_refuses_before_it_reads_the_body_the_role_the_question_or_the_candidate(self):
        candidate = self.dormant_verified(self.questions['extent'])
        before = counts()
        read = ('studio.review.confirm_finding', 'studio.review.assessment_candidates', 'studio.review.live_assessment',
                'studio.api._payload', 'studio.api._require_reviewer')
        with ExitStack() as stack:
            for target in read:
                stack.enter_context(mock.patch(target, side_effect=AssertionError(f'{target} was read')))
            for user in (self.reviewer, self.viewer):
                for body in (json.dumps({'candidate_id': candidate['id'],
                                         'attestation': candidates.attestation(candidate['value'])}),
                             '{}', 'not json', json.dumps({'candidate_id': 12})):
                    with self.subTest(user=user.username, body=body[:20]):
                        response = self.client_for(user).post(self.url('extent'), data=body,
                                                              content_type='application/json')
                        self.assertEqual((response.status_code, response.json()['error']), (409, NOT_OFFERED))
            # a question that is not this document's is refused the same way, unread
            response = self.client_for(self.reviewer).post(
                f'/api/encounters/{self.encounter.pk}/clarifications/00000000-0000-4000-8000-000000000000/confirm',
                data='{}', content_type='application/json')
            self.assertEqual((response.status_code, response.json()['error']), (409, NOT_OFFERED))
        # the session and the workspace scoping stand as before: no session 401, another workspace's encounter 404
        self.assertEqual(Client().post(self.url('extent'), data='{}', content_type='application/json').status_code, 401)
        outsider = f.member(f.workspace('Another synthetic workspace'), f.user('outsider3c'),
                            role=models.Membership.OWNER)
        self.assertEqual(self.client_for(outsider).post(self.url('extent'), data='{}',
                                                        content_type='application/json').status_code, 404)
        self.assertEqual(counts(), before)

    def test_review_confirm_finding_refuses_before_it_locks_or_reads_anything(self):
        candidate = self.dormant_verified(self.questions['extent'])
        membership = models.Membership.objects.get(user=self.reviewer, workspace=self.ws)
        before = counts()
        with mock.patch('studio.review._lock', side_effect=AssertionError('the encounter was locked')), \
                mock.patch('studio.review.assessment_candidates', side_effect=AssertionError('a candidate was read')):
            with self.assertRaises(review.ConfirmationRefused) as refused:
                review.confirm_finding(encounter=self.encounter, clarification_id=self.questions['extent'].pk,
                                       candidate_id=candidate['id'],
                                       attestation=candidates.attestation(candidate['value']), user=self.reviewer,
                                       membership=membership)
        self.assertEqual(refused.exception.messages, [NOT_OFFERED])
        self.assertEqual(counts(), before)


class ReassessTests(RecordedInterpretation, ColonCase):
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation.
    interpretations = TWO_EXTENTS_INTERPRETATIONS
    def test_a_re_assessment_after_a_confirmation_is_refused_and_nothing_is_queued(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        final = self.encounter(encounter_id).current_assessment
        self.confirm(encounter_id, final, 'sel:0')  # a row as the endpoint recorded it on the base
        before = counts()
        with self.assertRaises(jobs.Refused) as refused:
            jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        self.assertEqual(str(refused.exception), NOT_OFFERED)
        self.assertEqual(counts(), before)
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, idempotency_key__contains=':c:').exists())
        # the control: the dormant path queues it for the same encounter
        with override_settings(**DORMANT):
            job = jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        self.assertEqual((job.kind, ':c:' in job.idempotency_key), ('assess', True))


class StoredRowTests(RecordedInterpretation, ColonCase):
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation.
    interpretations = TWO_EXTENTS_INTERPRETATIONS
    def test_a_stored_confirmation_is_never_read_and_the_assessment_is_the_one_made_without_it(self):
        twin = self.create(TWO_EXTENTS)  # the same document and answers, with no confirmation anywhere
        drain()
        encounter_id = self.create(TWO_EXTENTS)
        job = self.run_until('astra_peer')
        first = self.encounter(encounter_id).current_assessment
        row = self.confirm(encounter_id, first, 'sel:0')  # sel:0's extent, 'cecum' on the landmark passage
        revision = self.encounter(encounter_id).current_revision
        self.assertEqual(jobs.confirmed_findings(revision), ())
        jobs.run_job(job)
        drain()
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(jobs.assessment_phase(final), 2)
        snare = final.proposals.get(key='sel:0')
        self.assertEqual((snare.code, snare.status), ('45385', 'needs_clarification'))
        self.assertNotIn('confirmed', snare.support)
        self.assertFalse({'confirmations.applied', 'confirmations.ignored'} & {c['id'] for c in final.encounter_checks})
        self.assertNotIn('confirmations', final.completeness or {})
        # the assessment these inputs make with no confirmation: the twin's, digest for digest
        other = self.encounter(twin).current_assessment
        self.assertEqual(jobs.assessment_phase(other), 2)
        self.assertEqual(final.sha256, other.sha256)
        self.assertEqual(review.confirmation_effect(row, final)['state'], review.CONFIRMATION_NOT_READ)
        # the control: the dormant path hands the same row to the engine
        with override_settings(**DORMANT):
            self.assertEqual([item.confirmation_id for item in jobs.confirmed_findings(revision)], [str(row.pk)])


# --- candidates: none is served; no member may confirm ----------------------------------------------------------------
#
# Moved by refutation round 4 (HARNESS.md 12.10 as amended, the session's D8; d7-1, d7-2, truth-1): round 3 served each
# open question's located passages, unchecked, and the page drew each as "Their answer: <value>" - a value that was CPT
# Studio's own inference from a participant's reading, never its answer to the question. No candidate is served now.

@override_settings(**h2.BOTH)
class CandidateTests(h2.Harness2Case):
    CHECKS = ('studio.candidates._why', 'studio.candidates._inconsistent', 'studio.candidates._qualified',
              'studio.validation.reconcile.status_stated', 'studio.review.recorded_inventory')
    # moved by refutation round 4 (D8): the source readers round 3's located passages came from run no more either
    READERS = ('studio.candidates._reading_sources', 'studio.candidates._answer_sources',
               'studio.candidates._basis_stated', 'studio.review.frozen_inputs', 'studio.review.peer_answers')

    def test_each_open_question_s_candidates_are_located_passages_never_checked(self):
        """Moved by refutation round 4 (D8): no open question is served a candidate, and no check and no reader of a
        participant's reading runs for one (round 3: each was served its located passages, never checked)."""
        with ExitStack() as stack:
            for target in self.CHECKS + self.READERS:
                stack.enter_context(mock.patch(target, side_effect=AssertionError(f'{target} ran')))
            served = review.assessment_candidates(self.final)
        questions = {str(q.pk): q for q in self.final.clarifications.filter(state=models.Clarification.OPEN)}
        self.assertEqual(len(questions), 4)
        self.assertEqual(served, {})
        # the control: the dormant path offers each open question candidates from the same rows, and verifies one
        with override_settings(**DORMANT):
            dormant = review.assessment_candidates(self.final)
        self.assertEqual(set(dormant), set(questions))
        self.assertTrue(all(dormant.values()), dormant)
        self.assertTrue(any(c['verified'] for items in dormant.values() for c in items), 'the control verifies one')

    def test_no_member_may_confirm_and_the_page_is_served_the_unchecked_candidates(self):
        """Moved by refutation round 4 (D8): no member may confirm and none is served a candidate (round 3: each was
        served the unchecked located passages)."""
        for user, can_review in ((self.owner, True), (self.reviewer, True), (self.viewer, False)):
            with self.subTest(user=user.username):
                response = self.client_for(user).get(f'/ops/api/encounters/{self.encounter.pk}')
                self.assertEqual(response.status_code, 200, response.content)
                data = response.json()
                self.assertEqual((data['permissions']['can_review'], data['permissions']['can_confirm']),
                                 (can_review, False))
                served = {c['id']: c['candidates'] for c in data['clarifications'] if c['state'] == 'open'}
                self.assertEqual(len(served), 4)
                self.assertEqual(served, {key: [] for key in served})
        # the control: the dormant path lets a reviewer confirm and serves the reviewer the candidates; the viewer still
        # may not confirm, and (moved by refutation round 4, D8: candidates go only to a member who may confirm one) is
        # served none
        with override_settings(**DORMANT):
            for user, allowed in ((self.reviewer, True), (self.viewer, False)):
                data = self.client_for(user).get(f'/ops/api/encounters/{self.encounter.pk}').json()
                self.assertEqual(data['permissions']['can_confirm'], allowed)
                self.assertEqual(all(c['candidates'] for c in data['clarifications'] if c['state'] == 'open'),
                                 allowed)


# --- peer-2 is unreachable: a later chain's peer requests carry no confirmation wording -------------------------------

HEDGE = 'It is unclear whether the flexible sigmoidoscopy was performed today.'
BIOPSIES = 'Cold forceps biopsies of the sigmoid colon lesion were taken.'
SAME_DAY = (HEAD + 'Office visit and same-day procedure (fictional)\nDate of service: 2026-10-14\n'
            'Place of service: Office\nEstablished patient seen for rectal bleeding.\n' + HEDGE + '\n' + BIOPSIES + '\n'
            + TIME_QUOTE + '\n')
READERS = 'possibly performed on the same date (its performance is not established)'
CONFIRMED = 'documented as performed on the same date'
REVIEWER = 'Rowan Synthetic-Reviewer Zq'


@applied
class PeerRequestTests(PipelineCase):
    """Refutation round 3's peer-2 (verifier v3-peer-rest): a reviewer's confirmation of 45331's status, after a
    member's save, reached the next chain's peer requests as CPT Studio's own reading of 99213's same-day rule, and
    45331's reasons as jobs.PEER_CONFIRMED_REASON. No confirmation is taken or read now, so the next chain's peer
    requests show the readers' own reading, as the first chain's did."""
    corti_codes = (('99213', TIME_QUOTE), ('45331', BIOPSIES))

    def setUp(self):
        super().setUp()
        self.reviewer.display_name = REVIEWER
        self.reviewer.save()
        self.adapters['astra'].first = [answered('astra', reading(
            codes=[('45331', BIOPSIES)], services=[('f1', 'flexible_sigmoidoscopy', 'performed', BIOPSIES)]))]
        self.adapters['fable'].first = [answered('fable', reading(codes=[('99213', TIME_QUOTE)]))]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]

    def first_chain(self):
        encounter_id = self.create(SAME_DAY)
        drain()
        final = self.encounter(encounter_id).current_assessment
        question = final.clarifications.get(fact='performed_status', proposal__code='45331',
                                            state=models.Clarification.OPEN)
        with override_settings(**DORMANT):  # the candidate the base served verified, and a reviewer confirmed
            detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        served = next(c for c in detail['clarifications'] if c['id'] == str(question.pk))['candidates']
        candidate = next(c for c in served if c['verified'] and c['value'] == 'performed')
        for run in self.runs_of(encounter_id, purpose='peer_review'):
            self.assertIn(READERS, json.dumps(run.request_body, ensure_ascii=False))  # chain 1: the readers' reading
        return encounter_id, question, candidate

    def second_chain(self, encounter_id):
        """A member's save of ordinary metadata starts the next chain; its peer runs and the bodies posted for them."""
        before = len(self.runs_of(encounter_id, purpose='peer_review'))
        posted = {name: len(posted_bodies(self, name)) for name in ('astra', 'fable')}
        response = self.post(f'/api/encounters/{encounter_id}/context', {'billing_context': 'professional'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        runs = self.runs_of(encounter_id, purpose='peer_review')[before:]
        self.assertEqual(sorted(run.provider for run in runs), ['astra', 'fable'])
        return runs, {name: posted_bodies(self, name)[count:] for name, count in posted.items()}

    def assertReadersOnly(self, runs, posted):
        bodies = [json.dumps(run.request_body, ensure_ascii=False) for run in runs]
        bodies += [body for items in posted.values() for body in items]
        for body in bodies:
            for words in (jobs.PEER_CONFIRMED_REASON, CONFIRMED, REVIEWER, 'located passage by'):
                self.assertNotIn(words, body)
        for run in runs:  # what each shows is the readers' own reading of the same-day rule
            self.assertIn(READERS, json.dumps(run.request_body, ensure_ascii=False))

    def test_a_refused_confirmation_leaves_the_next_chain_s_peer_requests_as_the_readers_read(self):
        encounter_id, question, candidate = self.first_chain()
        response = self.post(f'/api/encounters/{encounter_id}/clarifications/{question.pk}/confirm',
                             {'candidate_id': candidate['id'], 'attestation': candidate['attestation']})
        self.assertEqual((response.status_code, response.json()['error']), (409, NOT_OFFERED))
        self.assertFalse(models.FindingConfirmation.objects.exists())
        self.assertReadersOnly(*self.second_chain(encounter_id))

    def test_a_stored_confirmation_reaches_no_peer_request(self):
        encounter_id, question, candidate = self.first_chain()
        revision = self.encounter(encounter_id).current_revision
        row = models.FindingConfirmation.objects.create(  # as the endpoint recorded it on the base
            encounter_id=encounter_id, revision=revision, clarification=question, scope=question.scope,
            fact=question.fact, family=question.family, proposal_key=question.proposal.key, value=candidate['value'],
            spans=candidate['spans'], located_by=candidate['located_by'], runs=candidate['runs'],
            confirmed_by=self.reviewer, attestation=candidate['attestation'])
        self.assertReadersOnly(*self.second_chain(encounter_id))
        later = self.encounter(encounter_id).current_assessment
        self.assertFalse([p.code for p in later.proposals.all() if 'confirmed' in (p.support or {})])
        with override_settings(**DORMANT):  # the control: the dormant path would read it
            self.assertEqual([item.confirmation_id for item in jobs.confirmed_findings(revision)], [str(row.pk)])


# --- falsegreen-11: the rows the API tests and the website fixtures pin are the pipeline's own ----------------------

@applied
@override_settings(**h2.BOTH)
class CaseFidelityTests(h2.Harness2Case):
    """Refutation round 3's falsegreen-11: tests.test_harness2_api.Harness2Case - whose assessments the API tests pin
    and tests/test_frontend_harness2.py serializes into the website's fixtures - persisted rows written by hand, a 45380
    performed-status hold among them that CPT Studio's readers never produce for its note. The assessments it pins are
    the ones the assess stage makes of the case's own stored rows."""

    def test_the_assess_stage_makes_the_first_assessment_the_case_pins(self):
        job = jobs.enqueue(models.Job.ASSESS, encounter=self.encounter, revision=self.revision, context=self.context,
                           provider_run=self.corti, requested_by=self.reviewer,
                           key=jobs._assess_key(f'assess:{self.context.pk}:{self.corti.pk}', self.revision))
        self.assertEqual(jobs.claim_next(), job)
        job.refresh_from_db()
        jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        made = models.Assessment.objects.get(pk=job.result['assessment'])
        self.assertEqual([(p.key, p.code, p.status) for p in made.proposals.order_by('position')],
                         [(p.key, p.code, p.status) for p in self.first.proposals.order_by('position')])
        self.assertEqual(made.sha256, self.first.sha256)

    def test_the_final_assessment_is_the_engine_s_for_the_stored_runs(self):
        """assess #2 as stage_assess reads it: each participant's newest finished first-reading run and the peer run
        made for assess #1 (jobs._peer_run: its scope names that assessment), read by the pipeline's readers, Corti's
        run read by its normalizer, the context the analyze stage records - through the stage's own engine child."""
        inputs = []
        for name in h2.ADAPTERS:
            item, record = jobs._first_input(self.encounter, name, jobs._participant_run(self.revision, name))
            item, record = jobs._with_peer(self.encounter, item, record,
                                           jobs._peer_run(self.revision, name, self.first))
            inputs.append(item)
        self.assertEqual([(item.state, item.peer_state) for item in inputs], [('read', 'read')] * 2)
        provider_status, normalized = jobs._provider_inputs(self.final.provider_run)
        self.assertEqual((provider_status, normalized.refused), ('succeeded', False))
        context = self.final.context
        proposed = {code.code for item in inputs for code in item.reading.codes}
        proposed |= {code.code for item in inputs for code in item.peer.additional_codes}
        _, result = jobs._assess_child(
            self.revision.text, jobs.context_service_date(context), tuple(PageSpan(**p) for p in self.revision.pages),
            jobs.context_facts(context), normalized,
            jobs.prefetched_lookup(tuple(sorted(set(jobs.selected_codes(normalized)) | proposed))), provider_status,
            self.revision.extraction_status, tuple(self.revision.messages), None, None, tuple(inputs), ())
        self.assertEqual(sha256_json(result), self.final.sha256)
        # and the context is the one the document's own reader reads
        self.assertEqual(context.facts, jobs._merged_facts(gi_context.extract_context(self.revision.text), {}))


class LocatedPassageTests(SimpleTestCase):
    """review.located_passages, the candidates this release serves (HARNESS.md 12.10): a participant's passage is
    served only as exact slices of the revision text - one that cites no passage, one its quote was not located for,
    and one whose span is not the text's are not served - and never as checked, whatever it says.

    Moved by refutation round 4 (HARNESS.md 12.10 as amended, the session's D8): located_passages is removed, with
    UNCHECKED_WHY - no candidate is served while confirmations are not offered (tests/test_harness2_r4_conf.py pins it
    on the pipeline's rows), so nothing serves a located passage unchecked; falsegreen-5, its unpinned copy of the
    candidates' merge, is moot. The dormant path's check of the same sources is the control, unchanged."""
    TEXT = ('Colonoscopy report (fictional)\nThe cecum was not reached.\n'
            'Landmarks photographed: appendiceal orifice and ileocecal valve.\n')

    def quote(self, passage, *, exact=True):
        start = self.TEXT.index(passage)
        text = passage if exact else passage.upper()
        return LocatedQuote(passage, (EvidenceSpan(0, start, start + len(passage), text, True),))

    def reading(self, *services):
        return ParticipantReading(provider='astra', adapter_version='astra-test@1', reading_version='test',
                                  requested_model='gpt-6-astra', returned_model='gpt-6-astra', services=services)

    def service(self, extent, *quotes):
        return ParticipantService('s1', 'colonoscopy', 'performed', 'A colonoscopy.', '', extent, '',
                                  evidence=tuple(quotes))

    def test_only_exact_slices_are_served_and_none_is_checked(self):
        question = candidates.Question(id='q-extent', scope='proposal', fact='extent', family='gi.colonoscopy',
                                       proposal_key='sel:0', code='45385', service='S1')
        denied = 'The cecum was not reached.'
        landmarks = 'Landmarks photographed: appendiceal orifice and ileocecal valve.'
        readings = [candidates.FrozenReading('astra', 'run-1', self.reading(
            self.service('cecum', self.quote(denied), self.quote(landmarks, exact=False),
                         LocatedQuote('A sentence in no document.', (), 'not found')),
            self.service('cecum'),  # cites no passage
            self.service('cecum, not reached', self.quote(landmarks))))]  # a value CPT Studio cannot restate
        # moved by refutation round 4 (D8): nothing serves these sources as located passages - neither the reader that
        # served them, unchecked, nor its fixed why exists
        self.assertFalse(hasattr(review, 'located_passages'))
        self.assertFalse(hasattr(review, 'UNCHECKED_WHY'))
        # the dormant path checks the same sources: the denial is refused there, never verified (and the passage that is
        # not the text's slice is refused as one)
        dormant = candidates.candidates(question, self.TEXT, (), readings)
        self.assertTrue(dormant)
        self.assertFalse(any(c['verified'] for c in dormant))
        self.assertIn('A passage is not an exact slice of the document text.', [c['why'] for c in dormant])
        self.assertEqual([c['id'] for c in dormant], [candidate_id(question.id, c) for c in dormant])
        # a question no candidate answers is served none
        other = candidates.Question(id='q', scope='proposal', fact='base_included', family='gi.colonoscopy',
                                    proposal_key='sel:0', code='45385')
        self.assertEqual(candidates.candidates(other, self.TEXT, (), readings), [])
