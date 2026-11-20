"""Unit tests for design v2's installer additions that the Fable coding build keeps (ops/install.py;
docs/gemini-migration/FINAL-V2.md 6.2): the zero-v1-rows assertion of the app phase, on v1 rows only [R:MO-1], and its
place beside the install counts before the switch; and the undo's note plumbing (with_update_note), which this build's
close never feeds (it names no pending update, no set-back value and no reading stage). No Docker, sudo, nginx or
network. The Fable coding build's own in-image scripts are tested in ops/test_install_fable_scripts.py; the design v2
update machinery's scripts (UPDATE_PENDING, REAPPLY_REVERTED) and their tests went with it.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Every refusal is proven to refuse BEFORE it acts: the replacement is recorded and asserted not to have happened. V1_ROWS
also runs, as `manage shell -c` runs it, on a disposable PostgreSQL when one is configured the way CI configures it
(test_install_harness2's DatabaseTest); without one that test is skipped, never passed. Synthetic data only: every
encounter, run and value here is made in the test.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import TemporaryDirectoryTest, clean_counts, clean_v1_rows, guard_host, release_host  # noqa: E402
from test_install_harness import IMAGE, AppWorld, app_args  # noqa: E402
from test_install_harness2 import DatabaseTest, run_in_image  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    try:
        harness2 = sys.modules.get('test_install_harness2')
        if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
            connection = harness2._DATABASE.pop('connection')
            connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)
    finally:
        release_host()


# --- pure: the answers judged, the parameters given ------------------------------------------------------------------

class V1RowsAnswerTests(unittest.TestCase):
    def test_a_clean_answer_passes_and_a_v1_row_of_either_kind_refuses_naming_its_encounters(self):
        self.assertIsNone(install.v1_rows_refusal(clean_v1_rows()))
        for assessments, inventories in ((1, 0), (0, 1), (2, 3)):
            with self.subTest(assessments=assessments, inventories=inventories):
                answer = {**clean_v1_rows(), 'assessments': assessments, 'inventories': inventories,
                          'encounter_count': 2, 'encounters': ['e1', 'e2']}
                refusal = install.v1_rows_refusal(answer)
                self.assertIn('the target holds design v1 rows', refusal)
                self.assertIn('e1, e2', refusal)
                self.assertIn('nothing was replaced', refusal)
                self.assertIn('cpt-studio-events@1', refusal)
                self.assertIn('gemini-events@1', refusal)
        more = {**clean_v1_rows(), 'assessments': 300, 'encounter_count': 250, 'encounters': ['e1']}
        self.assertIn('e1 and 249 more', install.v1_rows_refusal(more))

    def test_an_answer_that_does_not_say_what_it_read_refuses_never_read_as_none(self):
        clean = clean_v1_rows()
        broken = [None, [], {}, {**clean, 'engine_version': 'cpt-studio-events@2'},
                  {**clean, 'interpretation_version': 'gemini-events@2/appraisal@1'}, {**clean, 'assessments': -1},
                  {**clean, 'assessments': True}, {**clean, 'encounters': 'e1'}, {**clean, 'encounters': ['e1', 'e1']},
                  {**clean, 'encounter_count': 1}, {**clean, 'assessments': 1},
                  {**clean, 'encounters': ['e1'], 'encounter_count': 0}]
        for answer in broken:
            with self.subTest(answer=answer):
                self.assertIn('gave no answer it could be judged by', install.v1_rows_refusal(answer))

    def test_the_versions_are_the_designs_literals_given_to_the_script(self):
        seen = []
        with mock.patch.object(install, 'app_script', lambda *args, **kwargs: seen.append(args) or {}):
            install.v1_rows(IMAGE, b'')
        (_, _, body, params), = seen
        self.assertIs(body, install.V1_ROWS)
        self.assertEqual(params, {'engine_version': 'cpt-studio-events@1', 'interpretation_version': 'gemini-events@1',
                                  'limit': install.NAMED_LIMIT})
        self.assertNotIn('startswith', install.V1_ROWS)  # exact versions, never the family


class UpdateNoteTests(unittest.TestCase):
    NOTE = {'assessments': 1, 'encounters': ['e9'], 'context_only': [], 'reinstatable': ['e9'],
            'note': '1 assessment was made from event inventories; the earlier image reads them fail-closed; 1 '
                    'encounter holds an excluded code a reviewer can reinstate: ...'}

    def test_a_close_with_nothing_of_the_update_leaves_the_note_as_it_was(self):
        for closes in ([], [None], [{'closed': 0, 'kinds': [], 'hazards': {}, 'relabel': []}]):
            with self.subTest(closes=closes):
                self.assertEqual(install.with_update_note(self.NOTE, closes), self.NOTE)

    def test_the_pending_updates_the_reverted_saves_and_the_reading_stages_are_listed_and_d59_kept(self):
        first = {'closed': 2, 'reading_closed': {'interpret': 1, 'appraise': 1},
                 'update_pending': {'e1': ['values_saved'], 'e2': ['assessment_off_context'],
                                    'e3': ['reconciled_unknown']},
                 'reverted': {'e1': {'setting': {'saved': 'office', 'restored': None}}}}
        second = {'closed': 1, 'reading_closed': {'appraise': 1}, 'update_pending': {'e4': ['values_saved']},
                  'reverted': {'e4': {'service_date': {'saved': '2026-11-12', 'restored': '2026-11-10'}}}}
        note = install.with_update_note(self.NOTE, [first, second])
        self.assertEqual(note['update_pending'], ['e1', 'e2', 'e3', 'e4'])
        self.assertEqual(note['reverted'], {'e1': {'setting': {'saved': 'office', 'restored': None}},
                                            'e4': {'service_date': {'saved': '2026-11-12', 'restored': '2026-11-10'}}})
        self.assertEqual(note['reading_closed'], {'appraise': 2, 'interpret': 1})
        self.assertEqual(note['reinstatable'], ['e9'])  # D59's limit, kept as interpretation_note gave it
        self.assertTrue(note['note'].startswith(self.NOTE['note'] + '; '))
        self.assertIn('3 reading stages were closed (appraise 2, interpret 1)', note['note'])
        self.assertIn('4 encounters read an update of their codes pending (update_pending)', note['note'])
        self.assertIn('the codes shown predate their change', note['note'])
        self.assertIn('1 of them read an update no save started (a reconciled document review, A21)', note['note'])
        self.assertIn('the unapplied details of 2 encounters were set back to their current context\'s values '
                      '(context.rollback_reverted', note['note'])
        self.assertIn('ask each member to save the change again on the earlier web', note['note'])

    def test_a_next_worker_with_the_update_is_said_to_read_it_itself(self):
        close = {'update_pending': {'e1': ['values_saved']}, 'reading_closed': {'appraise': 1}, 'update_revert': False,
                 'update_reads': {'e1': {'phase': 'paused', 'action': 'none'}}}
        note = install.with_update_note(self.NOTE, [close])
        self.assertEqual(note['update_pending'], ['e1'])
        self.assertIn('the earlier revision reads an update itself (its worker runs appraise)', note['note'])
        # refutation 6b-r2 F2 (D247): what is so - nothing queues the closed stage again, no retry is promised
        self.assertIn('1 reading stage was closed (appraise 1): each was failed with the installer\'s note, and '
                      'nothing queues it again - the earlier revision runs both, but offers no retry and no resume of a '
                      'stage the installer closed', note['note'])
        # refutation w7r 6b-r1 R2: worded by what it reads after the close (update_reads), never one reading for all
        self.assertIn('as this revision\'s page reads each after the close (update_reads; an earlier design v2 revision '
                      'reads an update by the same amendment, 7.1 and 7.2): 1 reads paused, with nothing to resume or '
                      'retry, until its member saves a change of a detail, which queues the update again', note['note'])
        self.assertEqual(note['update_reads'], {'e1': {'phase': 'paused', 'action': 'none'}})
        for promised in ('retry or resume', 'until a member tries it again', 'reads the document again on',
                         'Try updating again', 'Resume processing'):
            self.assertNotIn(promised, note['note'])
        self.assertNotIn('has no update', note['note'])
        self.assertNotIn('runs neither', note['note'])
        self.assertNotIn('reverted', note)
        # a close that does not say is read as the earlier image having none (the stronger warning)
        unsaid = install.with_update_note(self.NOTE, [{'update_pending': {'e1': ['values_saved']}}])
        self.assertIn('the earlier image has no update', unsaid['note'])
        self.assertNotIn('update_reads', unsaid)

    def test_each_pending_update_is_worded_by_the_action_its_page_offers_after_the_close(self):
        # refutation w7r 6b-r1 R2: a closed analysis or assessment reads failed with "Try updating again", a closed
        # reading or document review reads paused with nothing offered, a closed second review reads stopped with Resume
        reads = {'e1': {'phase': 'paused', 'action': 'none'}, 'e2': {'phase': 'failed', 'action': 'retry_update'},
                 'e3': {'phase': 'failed', 'action': 'retry_update'}, 'e4': {'phase': 'stopped', 'action': 'resume'},
                 'e5': {'phase': 'failed', 'action': 'retry_reading'}, 'e6': {'phase': 'being_confirmed',
                                                                             'action': 'none'}, 'e7': None}
        close = {'update_pending': {pk: ['assessment_off_context'] for pk in reads}, 'update_revert': False,
                 'update_reads': reads}
        note = install.with_update_note(self.NOTE, [close])['note']
        for said in ('7 encounters read an update of their codes pending (update_pending)',
                     '2 read failed, and its member\'s "Try updating again" queues the failed stage again',
                     '1 reads paused, with nothing to resume or retry, until its member saves a change of a detail, '
                     'which queues the update again',
                     '1 reads stopped, and its member\'s "Resume processing" runs it again',
                     '1 reads failed, and its member\'s "Try reading again" queues its reading again',
                     '1 reads being confirmed, with nothing offered on its page',
                     '1 could not be read after the close'):
            self.assertIn(said, note)
        self.assertNotIn('such an update reads paused there', note)  # one reading for all (the defect) is gone
        # a later close's reading is the one that stands (the switch-back's B7 after B4's)
        later = {'update_pending': {'e1': ['values_saved']}, 'update_revert': False,
                 'update_reads': {'e1': {'phase': 'failed', 'action': 'retry_update'}}}
        both = install.with_update_note(self.NOTE, [{**close, 'update_pending': {'e1': ['values_saved']},
                                                     'update_reads': {'e1': reads['e1']}}, later])
        self.assertEqual(both['update_reads'], {'e1': {'phase': 'failed', 'action': 'retry_update'}})
        self.assertIn('1 reads failed, and its member\'s "Try updating again"', both['note'])
        # a reading that does not say what it read is said so, never worded as any state
        for broken in ({'e1': {'phase': 'paused'}}, {'e1': {'phase': '', 'action': 'none'}}, {'e9': None}, ['e1'],
                       {'e1': {'phase': 'paused', 'action': 'none', 'extra': 1}}):
            with self.subTest(update_reads=broken):
                said = install.with_update_note(self.NOTE, [{**later, 'update_reads': broken}])
                self.assertIsNone(said['update_pending'])
                self.assertIn('were not read (a close did not say what it read)', said['note'])
        # an A21 update is worded by its own reading there, never with the claim made of an image with no update
        a21 = install.with_update_note(self.NOTE, [{'update_pending': {'e1': ['reconciled_unknown']},
                                                    'update_revert': False, 'update_reads': {'e1': reads['e6']}}])
        self.assertIn('1 of them read an update no save started (a reconciled document review, A21)', a21['note'])
        self.assertNotIn('reads that reconciled run as an outcome still being confirmed', a21['note'])

    def test_an_answer_that_does_not_say_what_it_read_is_said_so_never_read_as_none(self):
        broken = [{'update_pending': ['e1']}, {'update_pending': {'e1': []}}, {'update_pending': {'e1': ['other']}},
                  {'update_pending': {'e1': ['values_saved']}, 'reverted': {'e2': {'setting': {'saved': 1,
                                                                                               'restored': 2}}}},
                  {'update_pending': {'e1': ['assessment_off_context']},
                   'reverted': {'e1': {'setting': {'saved': 1, 'restored': 2}}}},
                  {'update_pending': {'e1': ['values_saved']}, 'reverted': {'e1': {'setting': {'saved': 1}}}},
                  {'reading_closed': {'predict': 1}}, {'reading_closed': {'appraise': 0}}]
        for close in broken:
            with self.subTest(close=close):
                note = install.with_update_note(self.NOTE, [close])
                self.assertIsNone(note['update_pending'])
                self.assertIn('were not read (a close did not say what it read)', note['note'])



# --- the app phase -----------------------------------------------------------------------------------------------------

class AppPhaseV1RowsTests(TemporaryDirectoryTest):
    """The REAL phase_app in test_install_harness's AppWorld: the two reads after migrate and before the switch."""

    def app(self, world):
        patches = world.patches()
        for patcher in patches:
            patcher.start()
        try:
            return install.phase_app(install.Context(app_args(self.tmp, coding='disabled'), self.tmp))
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_a_v1_row_refuses_after_migrate_and_before_the_switch(self):
        world = AppWorld(self.tmp)
        world.answers[('script', install.V1_ROWS)] = {**clean_v1_rows(), 'assessments': 1, 'encounter_count': 1,
                                                      'encounters': ['e1']}
        with self.assertRaises(install.InstallError) as caught:
            self.app(world)
        self.assertIn('The target holds design v1 rows', str(caught.exception))
        self.assertIn('e1', str(caught.exception))
        self.assertFalse([event for event in world.timeline if event[0] == 'replace'])  # nothing was replaced
        migrated = [index for index, event in enumerate(world.timeline) if event[0] == 'oneshot'
                    and event[1] == ('migrate',)]
        read = world.timeline.index(('script', install.V1_ROWS))
        self.assertTrue(migrated and migrated[0] < read)
        self.assertNotIn(('script', install.INSTALL_COUNTS), world.timeline)
        self.assertEqual(caught.exception.details['v1_rows']['encounters'], ['e1'])

    def test_a_clean_target_is_replaced_and_the_receipt_carries_the_v1_read_and_the_counts(self):
        world = AppWorld(self.tmp)
        details = self.app(world)
        order = [event for event in world.timeline if event[0] in ('script', 'replace')]
        self.assertEqual(order[:4], [('script', install.UNRUNNABLE_STAGES), ('script', install.V1_ROWS),
                                     ('script', install.INSTALL_COUNTS), order[3]])
        self.assertEqual(order[3][0], 'replace')  # both reads before the switch
        self.assertEqual(details['v1_rows'], clean_v1_rows())
        self.assertTrue(details['install_counts']['counted'])
        self.assertIn('; no design v1 row; install counts: 0 encounter(s), 0 coded', details['summary'])

    def test_the_counts_never_refuse_whatever_they_say(self):
        world = AppWorld(self.tmp)
        heavy = clean_counts()
        heavy['encounters'] = {'count': 3, 'coded': 0}
        heavy['jobs'] = {'extract': {'queued': 2}, 'interpret': {'running': 1}}
        heavy['unknown'] = {'count': 1, 'encounter_count': 1, 'encounters': ['e4'],
                            'in_flight': {'reserved': 0, 'sending': 1}}
        heavy['holds'] = {'standing': 1}
        world.answers[('script', install.INSTALL_COUNTS)] = heavy
        details = self.app(world)
        self.assertTrue([event for event in world.timeline if event[0] == 'replace'])
        self.assertIn('4 item(s) for the owner', details['summary'])
        self.assertTrue(any('2 stage(s) of the earlier pipeline queued and 1 running' in item
                            for item in details['install_counts']['report']))
        world = AppWorld(self.tmp)
        world.answers[('script', install.INSTALL_COUNTS)] = {'size': 'not counted'}
        details = self.app(world)
        self.assertFalse(details['install_counts']['counted'])
        self.assertIn('install counts NOT read', details['summary'])

    def test_a_failure_after_the_read_keeps_the_counts_in_its_receipt(self):
        world = AppWorld(self.tmp)

        def failing(*args, **kwargs):
            raise install.InstallError('the incoming web did not become ready', details={'started': {}})
        with mock.patch.object(world, 'replace', failing), self.assertRaises(install.InstallError) as caught:
            self.app(world)
        self.assertEqual(caught.exception.details['install_counts']['counted'], True)
        self.assertEqual(caught.exception.details['started'], {})


# --- the in-image script on real rows ---------------------------------------------------------------------------------

class V2Rows(DatabaseTest):
    """Synthetic rows of every kind the scripts read: a legacy encounter, a design v1 row (a test instance's), a design
    v2 row (an interpreted and appraised upload), runs of every provider, stages of every reading kind."""

    def extracted(self, encounter, text='Synthetic colonoscopy note.', pages=None):
        from studio import models
        revision = encounter.current_revision
        models.SourceRevision.record_extraction(
            revision.pk, extraction_status=models.SourceRevision.OK, extraction_method='paste', text=text,
            text_sha256='5' * 64, pages=pages if pages is not None else [{'page': 1, 'start': 0, 'end': len(text)}])
        encounter.current_revision = models.SourceRevision.objects.get(pk=revision.pk)
        return encounter

    def made_run(self, encounter, *, provider='corti', purpose='primary', state='succeeded', sent=True, http_status=200,
            error='', reconciled=False, request='e', adapter_version='synthetic@1'):
        from django.utils import timezone
        from studio import models
        return models.ProviderRun.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider=provider,
            adapter_version=adapter_version, purpose=purpose, request_sha256=request * 64, request_body={}, contexts=[],
            state=state, sent=sent, http_status=http_status, error=error, started_at=timezone.now(),
            reconciled_at=timezone.now() if reconciled else None)

    def context(self, encounter, *, version='gi-context@5', user_values=None, inventory=None, earlier=None):
        from studio import models
        return models.EncounterContext.objects.create(
            encounter=encounter, revision=encounter.current_revision, facts={}, sha256='d' * 64,
            user_values=user_values or {}, version=version, event_inventory=inventory, earlier_assessment=earlier)

    def assessment(self, encounter, context, *, engine_version='cpt-studio-validation@10', provider_run=None,
                   inventory=None, current=True):
        from studio import models
        routing = models.RoutingRun.objects.create(revision=encounter.current_revision, version='synthetic',
                                                   result={}, sha256='0' * 64)
        made = models.Assessment.objects.create(
            encounter=encounter, revision=encounter.current_revision, context=context, routing=routing,
            profiles_version='synthetic@1', engine_version=engine_version, sha256='1' * 64,
            provider_run=provider_run, event_inventory=inventory)
        if current:
            models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context, current_assessment=made)
        return made

    def inventory(self, encounter, *, version='gemini-events@2/appraisal@1', inventory_version='gemini-inventory@2'):
        """A read EventInventory of ``encounter``'s current revision; a v2 one is bound to both Gemini runs."""
        from studio import models
        v2 = '/' in version
        first = self.made_run(encounter, provider='gemini', purpose='interpretation', request='a')
        second = self.made_run(encounter, provider='gemini', purpose='appraisal', request='b') if v2 else None
        return models.EventInventory.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider_run=first, appraisal_run=second,
            interpretation_version=version, inventory_version=inventory_version, text_sha256='a' * 64,
            request_sha256='e' * 64, response_sha256='b' * 64, state='read', events={}, encounter_facts={},
            open_questions=[], verification={}, sha256='c' * 64)

    def legacy(self, tag, *, user_values=None, context_values=None):
        """A legacy encounter as the installed release left it: a legacy context, its legacy assessment current."""
        encounter = self.extracted(self.encounter(tag))
        context = self.context(encounter, user_values=context_values)
        self.assessment(encounter, context, provider_run=self.made_run(encounter))
        from studio import models
        models.Encounter.objects.filter(pk=encounter.pk).update(user_values=user_values or {})
        return models.Encounter.objects.get(pk=encounter.pk)

    def v2(self, tag):
        """An interpreted and appraised upload, its v2 assessment current on its gemini context."""
        encounter = self.extracted(self.encounter(tag))
        made = self.inventory(encounter)
        context = self.context(encounter, version='gemini-context@2', inventory=made)
        self.assessment(encounter, context, engine_version='cpt-studio-events@2', provider_run=self.made_run(encounter),
                        inventory=made)
        return encounter
class V1RowsOnTheDatabaseTests(V2Rows):
    def read(self):
        return run_in_image(install.V1_ROWS, {'engine_version': install.V1_ENGINE_VERSION,
                                              'interpretation_version': install.V1_INTERPRETATION_VERSION,
                                              'limit': install.NAMED_LIMIT})

    def test_v1_rows_only_trip_it_by_exact_version(self):
        self.assertEqual(self.read(), clean_v1_rows())  # the first install
        self.legacy('legacy')
        self.v2('v2')  # one v2 row: an assessment of cpt-studio-events@2 and an inventory of gemini-events@2/appraisal@1
        later = self.extracted(self.encounter('later'))  # a later events version (a later release's row)
        self.assessment(later, self.context(later), engine_version='cpt-studio-events@3')
        self.assertEqual(self.read(), clean_v1_rows())
        self.assertIsNone(install.v1_rows_refusal(self.read()))
        held = self.extracted(self.encounter('v1-assessment'))
        self.assessment(held, self.context(held), engine_version='cpt-studio-events@1')
        answer = self.read()
        self.assertEqual((answer['assessments'], answer['inventories'], answer['encounters']),
                         (1, 0, [str(held.pk)]))
        self.assertIn(str(held.pk), install.v1_rows_refusal(answer))
        inventory_only = self.extracted(self.encounter('v1-inventory'))
        self.inventory(inventory_only, version='gemini-events@1', inventory_version='gemini-inventory@1')
        answer = self.read()
        self.assertEqual((answer['assessments'], answer['inventories'], answer['encounter_count']), (1, 1, 2))
        self.assertEqual(answer['encounters'], sorted([str(held.pk), str(inventory_only.pk)]))


if __name__ == '__main__':
    unittest.main()
