"""r2 (DECISIONS D294, member words) - the R2W tests' DB world. SYNTHETIC only: tests/v2's own FactSet builders over
test_assess's synthetic letters; nothing is sent anywhere and no provider is called.

A scene goes the product's own way end to end (as the words lens's and its verifiers' probes did): the FactSet through
the renderer's bounded child (jobs._assess_child_v2, the FactSet handed in where the store's view is read), persisted
with its D22 record (review.persist_assessment), read time (review.effective_view), the customer payload
(customer_api.encounter_json: the codes' qualifications and the member's details rows), the details door
(answers.save_details) and the AGAIN recompute (the same child with jobs.member_answers_of, persisted on the same
encounter so the review decisions carry). Read time reads the stored inventory, a carrier with no event, so
readers.EventReader._load_facts is handed the scene's FactSet after the real load succeeds (the seam harness's e38)."""
from __future__ import annotations

import dataclasses
import hashlib
import json
from unittest import mock

from django.test import TestCase

from studio import answers, customer_api, interpretation, jobs, models, participants, review
from studio.interpretation import overlay, readers, report, sentinel, store
from studio.interpretation.contract import segment
from studio.types import sha256_json
from tests.support import factories as f
from tests.v2 import test_assess as TA
from tests.v2.test_facts import report as zero_report
from tests.v2.test_jobs import D246Reference

VALUES = {'setting': 'office', 'patient_status': 'established'}  # test_assess.ENTERED


def carrier(text):
    """A settled v2 inventory of ``text`` with no event and no claim, every encounter fact silent."""
    silent = {'claim': {'state': None, 'value': '', 'qualifiers': [], 'options': [], 'inherited_from': None},
              'sources': [], 'checks': {'integrity': 'ok', 'geometry': 'ok', 'literal': 'ok', 'consistency': 'ok',
                                        'literals': [], 'qualified': False},
              'appraisal': None, 'result': 'unknown', 'reasons': ['silent']}
    return {'units': [dataclasses.asdict(unit) for unit in segment.units(text)],
            'encounter': {'date_of_service': json.loads(json.dumps(silent)), 'other_dates': [],
                          'documenting_clinician': json.loads(json.dumps(silent))},
            'people': [], 'sections': [], 'sessions': [], 'anatomy': [], 'lesions': [], 'events': [], 'doubts': [],
            'claims': [], 'unlisted': [],
            'lesion_pairs': []}  # as settle writes it at the @3 pair (DECISIONS D296; integrated in r2's int1)


@dataclasses.dataclass
class Scene:
    encounter: object
    revision: object
    context: object
    assessment: object
    R: object
    codes: tuple
    text: str


class R2WWorld(TestCase):
    """The DB world every R2W scene runs in (see the module docstring)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        status = sentinel.install()
        assert status['state'] == 'ok', status

    def setUp(self):
        super().setUp()
        self.ws = f.workspace('R2W member words (synthetic)')
        self.user = f.member(self.ws, f.user('r2wreviewer'))
        self.membership = models.Membership.objects.get(workspace=self.ws, user=self.user)

    # --- the scene ---------------------------------------------------------------------------------------------------

    def run_row(self, encounter, revision, purpose, body):
        request = {'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'r2w synthetic scene'}]}],
                   'purpose': purpose}
        return models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=interpretation.PROVIDER_V3,
            adapter_version=interpretation.ADAPTER_VERSION_V3, purpose=purpose, request_sha256=sha256_json(request),
            request_body=request, contexts=[], state='succeeded', sent=True, http_status=200, response_bytes=body,
            response_sha256=hashlib.sha256(body).hexdigest(),
            usage={'input_tokens': 1, 'output_tokens': 1, 'cache_creation_input_tokens': 0,
                   'cache_read_input_tokens': 0},
            requested_model=interpretation.MODEL_V3, returned_model=interpretation.MODEL_V3,
            scope={'effect': 'answered', 'api_version': interpretation.API_VERSION_V3})

    def child(self, R, text, codes, context, answers_given=()):
        """The renderer's own bounded child (in-process) over ``R`` (dated), the proposal provider selecting ``codes``."""
        view, real = object(), overlay.reading

        def reading(given, day):
            return R if given is view else real(given, day)
        with mock.patch.object(overlay, 'reading', reading):
            return jobs._assess_child_v2(view, TA.DAY, text, (), 'succeeded', TA.corti(*codes, text=text),
                                         D246Reference(), TA.ENTERED, (), None, tuple(answers_given),
                                         jobs.context_facts(context), 'ok', ())

    def persist(self, scene, result):
        with sentinel.scope(sentinel.NEW_PATH, entry=jobs.ASSESS_SCOPE):
            inventory = scene.context.event_inventory
            record = report.interpretation_record(
                inventory=inventory, context=scene.context, member_date_state={'state': 'agrees'},
                sentinel_record=sentinel.record(name=jobs.ASSESS_SCOPE), engine_version=result.engine_version)
            routing = models.RoutingRun.objects.filter(revision=scene.revision).order_by('-pk').first()
            assessment = review.persist_assessment(
                encounter=models.Encounter.objects.get(pk=scene.encounter.pk), revision=scene.revision,
                context=scene.context, routing_run=routing, provider_run=None, result=result, retrieval=(),
                event_inventory=inventory, interpretation=record,
                participants=[jobs.not_configured_record(name) for name in participants.PARTICIPANTS])
        return models.Assessment.objects.get(pk=assessment.pk)

    def scene(self, R0, codes, text=TA.TEXT):
        """``R0`` (a FactSet, dated here) assessed for ``codes`` by the renderer's child and persisted: a Scene."""
        R = TA.dated(R0, TA.DAY)
        encounter = models.Encounter.objects.create(workspace=self.ws, title='R2W scene (synthetic)',
                                                    created_by=self.user, user_values=dict(VALUES))
        revision = f.pasted_revision(encounter, self.user, text)
        first = self.run_row(encounter, revision, interpretation.PURPOSE, b'{"synthetic": "r2w pass 1"}')
        second = self.run_row(encounter, revision, interpretation.APPRAISAL_PURPOSE, b'{"synthetic": "r2w pass 2"}')
        fields = store.row_v2(encounter_id=encounter.pk, revision_id=revision.pk, provider_run_id=first.pk,
                              appraisal_run_id=second.pk, revision_text=text, text_sha256=revision.text_sha256,
                              request_sha256=first.request_sha256, response_sha256=first.response_sha256,
                              appraisal_request_sha256=second.request_sha256,
                              appraisal_response_sha256=second.response_sha256, events=carrier(text),
                              verification=zero_report(), versions=jobs.V2_VERSIONS)
        inventory = models.EventInventory.objects.create(**json.loads(json.dumps(fields)))
        inventory = models.EventInventory.objects.get(pk=inventory.pk)
        facts = {'service_date': {'name': 'service_date', 'value': TA.DAY.isoformat(), 'origin': 'document',
                                  'evidence': [], 'note': ''}}
        for name, value in VALUES.items():
            facts[name] = {'name': name, 'value': value, 'origin': 'user', 'evidence': [], 'note': ''}
        context = models.EncounterContext.objects.create(
            encounter=encounter, revision=revision, facts=facts, version=interpretation.CONTEXT_VERSION_V2,
            sha256=sha256_json(facts), event_inventory=inventory, user_values=dict(VALUES))
        models.RoutingRun.objects.create(revision=revision, version=interpretation.ROUTING_VERSION_V2,
                                         result={'inventory': str(inventory.pk)}, sha256='1' * 64,
                                         service_date=TA.DAY)
        encounter.current_context = context
        encounter.save(update_fields=['current_context', 'updated_at'])
        scene = Scene(encounter=encounter, revision=revision, context=context, assessment=None, R=R, codes=codes,
                      text=text)
        with sentinel.scope(sentinel.NEW_PATH, entry=jobs.ASSESS_SCOPE):
            result = self.child(R, text, codes, context)
        scene.assessment = self.persist(scene, result)
        return scene

    def again(self, scene):
        """The AGAIN recompute: the child with the revision's standing member answers, persisted on the same encounter
        (the review decisions carry); the scene's assessment is the new one."""
        given = jobs.member_answers_of(scene.revision)
        with sentinel.scope(sentinel.NEW_PATH, entry=jobs.ASSESS_SCOPE):
            result = self.child(scene.R, scene.text, scene.codes, scene.context, given)
        scene.assessment = self.persist(scene, result)
        return scene.assessment

    # --- reading it ------------------------------------------------------------------------------------------------

    def reads(self, scene):
        """Read time over the scene's FactSet (the carrier row loads, then the scene's FactSet is handed in)."""
        real = readers.EventReader._load_facts

        def load(reader, given):
            found = real(reader, given)
            return None if found is None else scene.R
        return mock.patch.object(readers.EventReader, '_load_facts', load)

    def fresh(self, scene):
        return models.Encounter.objects.get(pk=scene.encounter.pk)

    def payload(self, scene):
        with self.reads(scene):
            return customer_api.encounter_json(self.fresh(scene), self.membership)

    def views(self, scene):
        with self.reads(scene):
            return {view.code: view for view in review.effective_view(
                models.Assessment.objects.get(pk=scene.assessment.pk)).values()}

    @staticmethod
    def rows_of(payload, code):
        return [row for row in payload['details_needed'] if code in row['affects']]

    @staticmethod
    def code_row(payload, code):
        return next(row for row in payload['codes'] if row['code'] == code)

    def save(self, scene, row, value=models.MemberAnswer.NOT_DOCUMENTED):
        """The door: ``value`` saved on ``row`` (a details row); the MemberAnswer rows it recorded."""
        with self.reads(scene):
            saved = answers.save_details(self.fresh(scene), self.user, [{'id': row['id'], 'fact': row['fact'],
                                                                        'value': value}])
        return [models.MemberAnswer.objects.get(pk=pk) for pk in saved['answer_ids']]

    def decide(self, scene, code, action):
        proposal = scene.assessment.proposals.get(code=code)
        with self.reads(scene):
            return review.record_decision(encounter=self.fresh(scene), proposal=proposal, action=action,
                                          user=self.user, membership=self.membership, note='r2w synthetic decision')

    def proposal(self, scene, code):
        return models.Assessment.objects.get(pk=scene.assessment.pk).proposals.get(code=code)

    def blockers(self, scene):
        with self.reads(scene):
            return review._assessment_blockers(self.fresh(scene), models.Assessment.objects.get(pk=scene.assessment.pk))
