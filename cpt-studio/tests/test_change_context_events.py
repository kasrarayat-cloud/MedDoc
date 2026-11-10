"""A member's context save on the new path (design/FINAL.md 6.10, 9 and 16.3; DECISIONS D8; slice S10).

On a gemini context the save re-applies the member's values onto the FROZEN interpretation: interpretation.facts.derive
over the context's EventInventory with the new values is recorded as a new gemini-context@1 row bound to that inventory,
here, under the row lock and a new_path sentinel scope whose write gate refuses the save when it ran legacy code.
Nothing is read, built or sent to the interpreter, and the decision afterwards is exactly as before
(_decide_after_save: the run in use re-checked when it answers the request, the participants' chain when one is owed,
otherwise the predict, the member date hold recorded where it stands). On a revision the legacy reader read, the
values are stored and the revision's first interpretation is queued; no context is made. A revision whose reading ended
failed with nothing to resume is refused.

Synthetic data only, no network: the same fixtures as tests/test_pipeline_assess_events.py."""
import json
from datetime import date
from pathlib import Path
from unittest import mock

from django.db import transaction

from studio import interpretation, jobs, models
from studio.context_facts import USER_CONFLICT_NOTE, is_member_conflict
from studio.gi import cues
from studio.interpretation import adapter, sentinel
from tests.test_pipeline_assess_events import (G1, G2, L1, P1, USAGE, EventsCase, a, act, document, envelope, exam,
                                               legacy_encounter, reached, removed, tg, two_procedures, POLYP)

Job = models.Job
Run = models.ProviderRun
NOT_STATED = {'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []}


def undated():
    """two_procedures() as Gemini reads it with no date of service stated: every code waits for the date."""
    return document({'G1': G1, 'G2': G2, 'P1': P1, 'P2': POLYP}, lesions=[L1], events=[
        exam('E0', 'G1', words='gastroscope', procedure=a('egd', 'EGD', ['G1'])),
        act('E5', 'G2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd', 'EGD', ['G2']),
            technique=a('cold_forceps', 'cold forceps', ['G2']),
            target=tg('', 'gastric_antrum', 'gastric antrum', ['G2'])),
        exam('E1', 'P1', words='colonoscope', status_words='was inserted',
             procedure=a('colonoscopy', 'Colonoscopy', ['P1'])),
        removed(procedure=a('colonoscopy', 'polyp', ['P2']))],
        reach=[reached('E0', 'second_portion_duodenum', 'second portion of the duodenum', 'G1')],
        date_of_service=NOT_STATED)


def refused_answer() -> bytes:
    """A 200 answer whose text is not JSON: the reading refuses it whole (its interpret stage fails, the retry door)."""
    return json.dumps({'candidates': [{'content': {'parts': [{'text': 'not json'}], 'role': 'model'},
                                       'finishReason': 'STOP', 'index': 0}],
                       'modelVersion': interpretation.MODEL, 'responseId': 'synthetic-s10-refused',
                       'usageMetadata': USAGE}).encode()


class ContextSaveCase(EventsCase):
    def assessed(self, scenario=two_procedures):
        encounter, revision = self.upload(scenario)
        ran = self.drain()
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in ran), [(j.kind, j.state, j.error) for j in ran])
        encounter.refresh_from_db()
        return encounter, revision

    def save(self, encounter, values):
        """jobs.change_context with the interpreter, the legacy reader and any text reading for meaning patched to
        fail: a save on an inventory builds nothing for the interpreter and reads nothing."""
        with mock.patch.object(adapter, 'get_interpreter', side_effect=AssertionError('the interpreter was built')), \
                mock.patch('studio.gi.context.extract_context', side_effect=AssertionError('the text was read')), \
                self.legacy_reader_fails():
            return jobs.change_context(encounter, self.user, values)

    def queued(self):
        return list(Job.objects.filter(state=Job.QUEUED).order_by('created_at', 'pk'))

    def counts(self, encounter):
        return {'inventories': models.EventInventory.objects.filter(encounter=encounter).count(),
                'interpretations': self.interpretation_runs(encounter)}


class SaveOnInventoryTests(ContextSaveCase):
    def test_a_setting_save_derives_a_new_gemini_context_on_the_frozen_inventory_and_sends_nothing(self):
        encounter, revision = self.assessed()
        previous, before = encounter.current_context, self.counts(encounter)
        corti = Run.objects.get(encounter=encounter, purpose=Run.PRIMARY)
        context = self.save(encounter, {'setting': 'asc'})
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_context_id, context.pk)
        self.assertNotEqual(context.pk, previous.pk)
        self.assertEqual((context.version, context.event_inventory_id, context.revision_id, context.created_by_id),
                         ('gemini-context@1', previous.event_inventory_id, revision.pk, self.user.pk))
        self.assertEqual(context.user_values, {'setting': 'asc'})
        self.assertEqual({key: context.facts['setting'][key] for key in ('value', 'origin')},
                         {'value': 'asc', 'origin': 'user'})
        self.assertEqual(context.facts['service_date'], previous.facts['service_date'])
        self.assertEqual(self.counts(encounter), before)  # nothing read again, nothing sent to the interpreter
        changed = models.AuditEvent.objects.filter(event='context.changed').get()
        self.assertEqual((changed.data['context'], changed.data['fields']), (str(context.pk), ['setting']))
        # decided as before: the setting is not in Corti's request, so the run in use is re-checked by an assess
        [assess] = self.queued()
        self.assertEqual((assess.kind, assess.context_id, assess.provider_run_id, assess.idempotency_key),
                         ('assess', context.pk, corti.pk, f'assess:{context.pk}:{corti.pk}'))
        with mock.patch.object(adapter, 'get_interpreter', side_effect=AssertionError('the interpreter was built')), \
                self.legacy_reader_fails():
            [job] = self.drain()
        self.assertEqual((job.state, job.result['mode']), (Job.SUCCEEDED, 'first'))
        latest = self.assessments(encounter)[-1]
        self.assert_new_path(latest, encounter, context=context)
        self.assertEqual(len(self.corti.sent), 1)  # Corti's request was unchanged: nothing sent again
        self.assertEqual(self.counts(encounter), before)

    def test_a_date_save_that_changes_corti_request_records_its_stand_in_and_re_predicts(self):
        encounter, revision = self.assessed(undated)
        self.assertIsNone(encounter.current_context.facts['service_date']['value'])
        self.assertEqual(len(self.corti.sent), 1)  # sent with no date
        before = self.counts(encounter)
        context = self.save(encounter, {'service_date': '2026-11-09'})
        self.assertEqual({key: context.facts['service_date'][key] for key in ('value', 'origin', 'state')},
                         {'value': '2026-11-09', 'origin': 'user', 'state': 'supplies'})
        stand_in = models.RoutingRun.objects.get(revision=revision, service_date=date(2026, 11, 9))
        self.assertEqual((stand_in.version, stand_in.result['inventory']),
                         ('gemini-routing@1', str(context.event_inventory_id)))
        [predict] = self.queued()
        self.assertEqual((predict.kind, predict.context_id), ('predict', context.pk))
        with mock.patch.object(adapter, 'get_interpreter', side_effect=AssertionError('the interpreter was built')), \
                self.legacy_reader_fails():
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran], [('predict', 'succeeded'), ('assess', 'succeeded')])
        self.assertEqual(len(self.corti.sent), 2)  # Corti's request now carries the member's date
        dated = Run.objects.filter(encounter=encounter, purpose=Run.PRIMARY).order_by('created_at').last()
        self.assertEqual(dated.service_date, date(2026, 11, 9))
        latest = self.assessments(encounter)[-1]
        self.assert_new_path(latest, encounter, context=context)
        self.assertEqual(latest.routing_id, stand_in.pk)  # the stand-in, looked up
        self.assertEqual(self.counts(encounter), before)

    def test_a_member_date_conflict_holds_as_before_and_clearing_it_re_checks_the_run_in_use(self):
        encounter, revision = self.assessed()
        corti = Run.objects.get(encounter=encounter, purpose=Run.PRIMARY)
        held = self.save(encounter, {'service_date': '2026-11-08'})
        fact = held.facts['service_date']
        self.assertTrue(is_member_conflict(fact))  # the legacy note, read by the one shared predicate
        self.assertEqual((fact['origin'], fact['value']), ('conflict', None))
        self.assertTrue(fact['note'].startswith(USER_CONFLICT_NOTE.split('{', 1)[0]))
        # the hold is recorded where it is decided, and only the assess that reads it is queued: nothing is sent
        [assess] = self.queued()
        hold = Run.objects.get(pk=assess.provider_run_id)
        self.assertEqual((hold.state, hold.scope['held']), (Run.NOT_SENT, Run.HELD_MEMBER_DATE_CONFLICT))
        with self.legacy_reader_fails():
            [job] = self.drain()
        self.assertEqual(job.state, Job.SUCCEEDED, job.error)
        self.assert_new_path(self.assessments(encounter)[-1], encounter, context=held)
        self.assertEqual(len(self.corti.sent), 1)
        # clearing the member's date settles the conflict: the document's date again, and the run in use answers it
        encounter.refresh_from_db()
        settled = self.save(encounter, {'service_date': ''})
        self.assertEqual((settled.facts['service_date']['value'], settled.facts['service_date']['origin']),
                         ('2026-11-09', 'document'))
        [assess] = self.queued()
        self.assertEqual((assess.kind, assess.provider_run_id), ('assess', corti.pk))
        with self.legacy_reader_fails():
            [job] = self.drain()
        self.assertEqual(job.state, Job.SUCCEEDED, job.error)
        self.assertEqual(len(self.corti.sent), 1)
        self.assertEqual(self.interpretation_runs(encounter), 1)

    def test_a_save_after_a_stopped_analyze_derives_from_the_inventory_read(self):
        encounter, revision = self.upload()
        self.run_next('interpret')
        jobs.stop_encounter(encounter, self.user)  # the analyze is cancelled before it ran
        self.assertIsNone(models.Encounter.objects.get(pk=encounter.pk).current_context_id)
        before = self.counts(encounter)
        context = self.save(encounter, {'setting': 'office'})
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((context.version, context.event_inventory_id), ('gemini-context@1', inventory.pk))
        [predict] = self.queued()
        self.assertEqual((predict.kind, predict.context_id), ('predict', context.pk))
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran], [('predict', 'succeeded'), ('assess', 'succeeded')])
        self.assertEqual(self.counts(encounter), before)


class GateTests(ContextSaveCase):
    def test_the_write_gate_refuses_a_save_whose_scope_ran_legacy_code_and_nothing_is_kept(self):
        encounter, revision = self.assessed()
        previous = encounter.current_context
        contexts = models.EncounterContext.objects.count()
        real = jobs.derived_facts

        def planted(*args, **kwargs):
            cues.page_number_line('3')  # a denied function, run in the save's scope before its first row
            return real(*args, **kwargs)

        with mock.patch.object(jobs, 'derived_facts', side_effect=planted), \
                self.assertRaises(jobs.Refused) as refused:
            self.save(encounter, {'setting': 'asc'})
        self.assertEqual(str(refused.exception), sentinel.MESSAGES['executed'])
        encounter.refresh_from_db()
        self.assertEqual((encounter.current_context_id, encounter.user_values), (previous.pk, {}))
        self.assertEqual(models.EncounterContext.objects.count(), contexts)
        self.assertEqual(self.queued(), [])
        [trip] = models.AuditEvent.objects.filter(event=sentinel.TRIPPED)
        self.assertEqual((trip.data['entry'], trip.data['reason'], trip.data['refused'], trip.data['label']),
                         ('context.save', 'executed', True, 'new_path'))
        self.assertEqual((trip.encounter_id, trip.actor_id), (encounter.pk, self.user.pk))
        self.assertEqual(refused.exception.trip, trip.data)  # the refusal carries the row it recorded
        self.assertFalse(models.AuditEvent.objects.filter(event='context.changed').exists())

    def test_a_save_refused_inside_a_callers_transaction_carries_its_trip_for_that_caller_to_record(self):
        """FINAL 10.3 asks for a recorded refusal. change_context records the trip after its own save rolled back, but
        a caller that holds a transaction of its own around the call - answers.save_details and review.confirm_finding
        do - rolls that row back with its own work when it lets the refusal propagate: the Refused carries the trip
        (``trip``), so such a caller records it once it has left its transaction (S10 review round 2, finding 3; the
        callers are slice S11's)."""
        encounter, revision = self.assessed()
        real = jobs.derived_facts

        def planted(*args, **kwargs):
            cues.page_number_line('3')  # a denied function, run in the save's scope before its first row
            return real(*args, **kwargs)

        with mock.patch.object(jobs, 'derived_facts', side_effect=planted), \
                self.assertRaises(jobs.Refused) as refused:
            with transaction.atomic():  # a caller's own transaction around the save, as save_details holds one
                self.save(encounter, {'setting': 'asc'})
        self.assertEqual(str(refused.exception), sentinel.MESSAGES['executed'])
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())  # rolled back with it
        trip = refused.exception.trip
        self.assertEqual((trip['entry'], trip['reason'], trip['refused'], trip['label'], trip['scope']),
                         ('context.save', 'executed', True, 'new_path', jobs.CONTEXT_SAVE))
        self.assertTrue(any('studio/gi/cues.py' in line for line in trip['executed']), trip)
        # the caller, outside its transaction, records the row the gate would have kept
        from studio import audit

        audit.record(encounter.workspace, sentinel.TRIPPED, encounter=encounter, actor=self.user, **trip)
        [row] = models.AuditEvent.objects.filter(event=sentinel.TRIPPED)
        self.assertEqual((row.data, row.encounter_id, row.actor_id), (trip, encounter.pk, self.user.pk))

    def test_a_clean_save_runs_in_its_own_new_path_scope_with_nothing_counted(self):
        encounter, revision = self.assessed()
        seen = []
        real = jobs.record_derived_context

        def spy(*args, **kwargs):
            scope = sentinel.current()
            seen.append((scope.label, scope.entry, scope.total(sentinel.NEW_PATH), sentinel.refusal(scope)))
            return real(*args, **kwargs)

        with sentinel.call_checks(), mock.patch.object(jobs, 'record_derived_context', side_effect=spy):
            self.save(encounter, {'billing_context': 'professional'})
        self.assertEqual(seen, [('new_path', 'context.save', 0, None)])


class BeforeReadingTests(ContextSaveCase):
    def test_a_save_on_a_legacy_revision_stores_the_values_and_has_it_read_with_no_context_made(self):
        encounter, revision, legacy_context, legacy = legacy_encounter(self.ws, self.user)
        contexts = models.EncounterContext.objects.count()
        returned = self.save(encounter, {'setting': 'asc'})
        self.assertEqual(returned.pk, legacy_context.pk)  # no context is made here: the current one is returned
        encounter.refresh_from_db()
        self.assertEqual((encounter.user_values, encounter.current_context_id), ({'setting': 'asc'}, legacy_context.pk))
        self.assertEqual(models.EncounterContext.objects.count(), contexts)
        self.assertFalse(Run.objects.filter(encounter=encounter).exists())  # nothing was sent
        [job] = self.queued()
        self.assertEqual((job.kind, job.context_id), ('interpret', None))
        self.assertTrue(job.idempotency_key.startswith(f'interpret:{revision.pk}:gemini-events@1:{jobs.AFTER_SAVE}:'))
        changed = models.AuditEvent.objects.get(event='context.changed')
        self.assertEqual((changed.data['reading'], changed.data['fields']), (str(job.pk), ['setting']))
        self.assertNotIn('context', changed.data)
        # the revision's first interpretation: read, and the context derived with the stored values
        value, _ = two_procedures()
        request = adapter.build_request(revision.text, jobs._participant_pages(revision),
                                        jobs._participant_document(revision)[0])
        folder = Path(self.replay) / adapter.NAME
        folder.mkdir(exist_ok=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(envelope(value))
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran],
                         [('interpret', 'succeeded'), ('analyze', 'succeeded'), ('predict', 'succeeded'),
                          ('assess', 'succeeded')])
        encounter.refresh_from_db()
        context = encounter.current_context
        self.assertEqual((context.version, context.user_values['setting'], context.facts['setting']['origin']),
                         ('gemini-context@1', 'asc', 'user'))
        latest = self.assessments(encounter)[-1]
        self.assert_new_path(latest, encounter, context=context)

    def test_a_save_after_the_reading_ended_failed_is_refused_and_nothing_is_stored(self):
        encounter, revision = self.upload()
        request = adapter.build_request(revision.text, jobs._participant_pages(revision),
                                        jobs._participant_document(revision)[0])
        (Path(self.replay) / adapter.NAME / f'{request.canonical_sha256}.json').write_bytes(refused_answer())
        job = self.run_next('interpret')
        self.assertEqual(job.state, Job.FAILED)
        self.assertFalse(models.EventInventory.objects.filter(revision=revision, state='read').exists())
        with self.assertRaises(jobs.Refused) as refused:
            self.save(encounter, {'setting': 'asc'})
        self.assertEqual(str(refused.exception), jobs.CONTEXT_UNREAD_MESSAGE)
        encounter.refresh_from_db()
        self.assertEqual(encounter.user_values, {})
        self.assertEqual(self.queued(), [])

    def test_a_save_while_the_first_reading_is_paused_queues_it_again(self):
        encounter, revision, legacy_context, _ = legacy_encounter(self.ws, self.user)
        # the revision's first interpretation, as a member's explicit act on a legacy encounter queues it (S09)
        jobs.enqueue('interpret', encounter=encounter, revision=revision, key=jobs._interpret_key(revision),
                     requested_by=self.user)
        with self.settings(GEMINI_MODE='disabled'):
            job = self.run_next('interpret')
        self.assertEqual(job.state, Job.CANCELLED)  # paused: resumable
        returned = self.save(encounter, {'setting': 'asc'})
        self.assertEqual(returned.pk, legacy_context.pk)
        [queued] = self.queued()
        self.assertEqual((queued.kind, queued.context_id), ('interpret', None))
        self.assertNotEqual(queued.pk, job.pk)
        self.assertIn(f':{jobs.AFTER_SAVE}:', queued.idempotency_key)

    def test_a_save_on_an_encounter_with_no_context_at_all_is_refused(self):
        encounter, revision = self.upload()
        with self.settings(GEMINI_MODE='disabled'):
            job = self.run_next('interpret')
        self.assertEqual(job.state, Job.CANCELLED)  # paused before it was ever read: no context exists
        with self.assertRaises(jobs.Refused) as refused:
            self.save(encounter, {'setting': 'asc'})
        self.assertEqual(str(refused.exception), jobs.CONTEXT_NONE_MESSAGE)
        encounter.refresh_from_db()
        self.assertEqual((encounter.user_values, encounter.current_context_id), ({}, None))
        self.assertEqual(self.queued(), [])
