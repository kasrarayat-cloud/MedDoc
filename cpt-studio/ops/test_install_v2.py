"""Unit tests for design v2's installer additions (ops/install.py; docs/gemini-migration/FINAL-V2.md 6.2 and 6.4, and
AMENDMENT-1.md 9.4 and 9.5; step 6b of FINAL-V2 8.1 and of the amendment's section 10): the zero-v1-rows assertion of the
app phase, on v1 rows only [R:MO-1]; pass 2's stage kind 'appraise' in CLOSE_STAGES and UNRUNNABLE_STAGES; the install
counts of 9.5 (printed, never a refusal), A21's included, with the provider holds; the undo's 'update_pending' names and
its revert of a pending save's unapplied values [R:legacy-L7], and the note that lists them beside D59's 'reinstatable'
limit; the retired kind in verify's reading of the in-image self-test (step 6a's request R6). No Docker, sudo, nginx or
network.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Every refusal is proven to refuse BEFORE it acts: the replacement is recorded and asserted not to have happened. The
in-image scripts also run, as `manage shell -c` runs them, on a disposable PostgreSQL when one is configured the way CI
configures it (test_install_harness2's DatabaseTest); without one those tests are skipped, never passed. Synthetic
data only: every encounter, run and value here is made in the test.
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import (TemporaryDirectoryTest, clean_counts, clean_v1_rows, guard_host,  # noqa: E402
                          release_host)
from test_install_harness import IMAGE, REVISION, AppWorld, app_args  # noqa: E402
from test_install_harness2 import DatabaseTest, run_in_image  # noqa: E402
from test_install_bluegreen import (KINDS_OLD, OLD, OLD_IMAGE, WORKER, BlueGreenWorld, run_app,  # noqa: E402
                                    run_holding_the_key, switch_back_args)
from test_install_r2 import ReloadActsThenRaises, run_rollback_app, run_switch_back, switched_back_world  # noqa: E402
from test_install_r3 import keep_world  # noqa: E402


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


def in_this_image(image, env, body, params, **kwargs):
    """app_script, as `manage shell -c` runs a body in the image, run here on the test database."""
    return run_in_image(body, params)


# --- pure: the answers judged, the parameters given ------------------------------------------------------------------

class StageKindTests(unittest.TestCase):
    def test_appraise_is_a_reading_kind_no_older_worker_runs(self):
        # FINAL-V2 6.4: the old worker would die on STAGES['appraise'], so it is never among the kinds every worker runs
        self.assertEqual(install.APPRAISE_KIND, 'appraise')
        # round r3 (D322 (5)): the question stage is a reading stage too, which no older worker runs either
        self.assertEqual(install.QUESTION_KIND, 'question')
        self.assertEqual(install.READING_STAGE_KINDS, ('interpret', 'appraise', 'question'))
        self.assertNotIn('appraise', install.COMMON_STAGE_KINDS)
        self.assertNotIn('question', install.COMMON_STAGE_KINDS)
        # both scripts read the kinds from a worker's own jobs.STAGES, never from a list naming them
        self.assertIn('Job.objects.exclude(kind__in=kept)', install.CLOSE_STAGES)
        self.assertIn('Job.objects.exclude(kind__in=known)', install.UNRUNNABLE_STAGES)
        self.assertIn('sorted(jobs.STAGES)', install.UNRUNNABLE_STAGES)

    def test_the_undo_reverts_only_for_a_next_worker_that_runs_no_appraise(self):
        seen = []

        def app_script(image_id, env_bytes, body, params, **kwargs):
            seen.append((body, params))
            return {'closed': 0}
        since = dt.datetime(2026, 11, 13, 10, 0, tzinfo=dt.timezone.utc)
        with mock.patch.object(install, 'app_script', app_script):
            for kinds, revert in ((list(install.COMMON_STAGE_KINDS), True), (KINDS_OLD, True),
                                  (KINDS_OLD + ['interpret'], True), (KINDS_OLD + ['interpret', 'appraise'], False),
                                  (KINDS_OLD + ['interpret', 'appraise', 'question'], False)):
                with self.subTest(kinds=kinds):
                    install.close_undone_stages(IMAGE, b'', since, REVISION, 'undone', kinds)
                    body, params = seen[-1]
                    self.assertIs(body, install.CLOSE_STAGES)
                    self.assertIs(params['revert'], revert)
                    self.assertEqual(params['reading_kinds'], ['interpret', 'appraise', 'question'])
                    self.assertEqual(params['kinds'], sorted(kinds))


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


class CountsAnswerTests(unittest.TestCase):
    def test_a_clean_answer_is_counted_and_reports_the_addendum_bound_with_the_longest_document(self):
        with mock.patch.object(install, 'app_script', return_value=clean_counts()):
            counts = install.install_counts(IMAGE, b'')
        self.assertTrue(counts['counted'])
        self.assertEqual(len(counts['report']), 1)
        self.assertIn('an addendum that would take a document over 20000 characters', counts['report'][0])
        self.assertIn('the longest current document is 0 characters', counts['report'][0])
        summary = install.counts_summary(counts)
        self.assertIn('0 over the character bound, 0 over the page bound, 0 unframed', summary)
        self.assertIn('0 provider hold(s) and 0 interpreter hold(s) standing', summary)

    def test_each_class_b_count_and_a21_are_reported_to_the_owner(self):
        answer = clean_counts()
        answer['size'].update(without_inventory=4, over_chars=1, over_pages=1, unframed=2, unframed_empty=1,
                              unframed_unextracted=1, longest_chars=24000,
                              encounters={'over_chars': ['e1'], 'over_pages': ['e2'], 'unframed': ['e3', 'e4']})
        answer['values'] = {'count': 1, 'first_install': True, 'encounters': ['e5']}
        answer['refused']['corti_sent'] = {'count': 2, 'newest': '2026-11-01T10:00:00+00:00'}
        answer['refused']['corti_token'] = {'count': 1, 'newest': '2026-11-02T10:00:00+00:00'}
        answer['a21'] = {'count': 1, 'encounters': ['e6']}
        report = install.counts_report(answer)
        joined = ' | '.join(report)
        self.assertIn('1 encounter(s) over 20000 characters and 1 over 40 pages', joined)
        # refutation 6b-r1 P8: an empty text whose extraction failed or has not run is no capability loss (the
        # installed release refuses a change of its details too), so class b counts the other unframed text only
        self.assertIn('1 encounter(s) with no inventory at the current versions have a text that cannot be framed: '
                      'their details cannot be changed after the install (A12, class b)', joined)
        self.assertIn('1 encounter(s) have no text because their extraction failed or has not run: the installed '
                      'release refuses a change of their details too, so nothing is lost there (not class b)', joined)
        self.assertIn('the longest current document is 24000 characters', joined)
        self.assertIn('first install, expected 0): they would read an update no save queued - e5', joined)
        self.assertIn('Corti 2 (newest 2026-11-01T10:00:00+00:00) - each stays held against its identical request, '
                      'and an update meeting one ends failed and cannot finish for those details on that encounter',
                      joined)
        # refutation 6b-r1 P8: a participant's refusal never fails an update (amendment 1, 7.1)
        self.assertIn('participants 0 (newest None) - each stays held against its identical request, and an update '
                      'meeting one goes on without that participant\'s check (it completes partial, 7.1)', joined)
        self.assertIn('Corti token refusals 1 (newest 2026-11-02T10:00:00+00:00)', joined)
        self.assertIn('(A21, expected 0): from the install on they read an update no save started - e6', joined)
        # after the first install the saved-values count is printed, never reported with ids
        later = {**answer, 'values': {'count': 3, 'first_install': False, 'encounters': []}}
        self.assertNotIn('first install', ' | '.join(install.counts_report(later)))

    def test_a_read_that_fails_or_says_nothing_is_recorded_as_not_counted_and_never_refuses(self):
        with mock.patch.object(install, 'app_script', side_effect=install.InstallError('exit 1')):
            counts = install.install_counts(IMAGE, b'')
        self.assertEqual((counts['counted'], counts['why']), (False, 'exit 1'))
        self.assertIn('NOT read', install.counts_summary(counts))
        broken = clean_counts()
        broken['refused'].pop('corti_token')
        for answer in (None, {}, broken, {**clean_counts(), 'a21': {'count': 0, 'encounters': ['e1']}},
                       {**clean_counts(), 'values': {'count': 1, 'first_install': False, 'encounters': ['e1']}}):
            with self.subTest(answer=answer), mock.patch.object(install, 'app_script', return_value=answer):
                counts = install.install_counts(IMAGE, b'')
            self.assertFalse(counts['counted'])
            self.assertTrue(counts['why'])
        with mock.patch.object(install, 'app_script', side_effect=KeyboardInterrupt), \
                self.assertRaises(KeyboardInterrupt):
            install.install_counts(IMAGE, b'')  # an interrupt is never swallowed


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


class RetiredKindTests(unittest.TestCase):
    def test_the_retired_kind_must_be_armed_as_pinned_with_its_control_ok(self):
        good = {'retired_size': 1312, 'pinned_retired_size': 1312, 'retired_control': 'ok', 'retired_armed': True}
        self.assertEqual(install.retired_problems(good), [])
        cases = {'size': {**good, 'retired_size': 1311}, 'unpinned': {**good, 'pinned_retired_size': 0},
                 'not int': {**good, 'retired_size': '1312', 'pinned_retired_size': '1312'},
                 'control': {**good, 'retired_control': 'failed'}, 'unarmed': {**good, 'retired_armed': False},
                 'silent': {}}
        for label, found in cases.items():
            with self.subTest(label=label):
                self.assertTrue(install.retired_problems(found))
        self.assertTrue(install.retired_problems(None))


# --- the app phase -----------------------------------------------------------------------------------------------------

class AppPhaseV1RowsTests(TemporaryDirectoryTest):
    """The REAL phase_app in test_install_harness's AppWorld: the two reads after migrate and before the switch."""

    def app(self, world):
        patches = world.patches()
        for patcher in patches:
            patcher.start()
        try:
            return install.phase_app(install.Context(app_args(self.tmp, astra='disabled', fable='disabled'), self.tmp))
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
        self.assertIn('; no design v1 row; install counts: 0 over the character bound', details['summary'])

    def test_the_counts_never_refuse_whatever_they_say(self):
        world = AppWorld(self.tmp)
        heavy = clean_counts()
        heavy['size'].update(without_inventory=2, over_chars=2, encounters={'over_chars': ['e1', 'e2'],
                                                                             'over_pages': [], 'unframed': []})
        heavy['values'] = {'count': 1, 'first_install': True, 'encounters': ['e3']}
        heavy['a21'] = {'count': 1, 'encounters': ['e4']}
        world.answers[('script', install.INSTALL_COUNTS)] = heavy
        details = self.app(world)
        self.assertTrue([event for event in world.timeline if event[0] == 'replace'])
        self.assertIn('item(s) for the owner', details['summary'])
        self.assertTrue(any('e3' in item for item in details['install_counts']['report']))
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


# --- the in-image scripts on real rows ---------------------------------------------------------------------------------

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

    def current_inventory(self, encounter):
        """A read EventInventory at the CURRENT versions (jobs.current_versions: AMENDMENT-2 8.1's
        gemini-events@3/appraisal@2 and gemini-inventory@3), bound to two runs of the current interpreter (Fable:
        PROVIDER_V3, ADAPTER_VERSION_V3)."""
        from studio import interpretation, models
        runs = [self.made_run(encounter, provider=interpretation.PROVIDER_V3, purpose=purpose, request=request,
                              adapter_version=interpretation.ADAPTER_VERSION_V3)
                for purpose, request in ((interpretation.PURPOSE, 'a'), (interpretation.APPRAISAL_PURPOSE, 'b'))]
        return models.EventInventory.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider_run=runs[0], appraisal_run=runs[1],
            interpretation_version=interpretation.INTERPRETATION_PAIR_V3,
            inventory_version=interpretation.INVENTORY_VERSION_V3, text_sha256='a' * 64, request_sha256='e' * 64,
            response_sha256='b' * 64, state='read', events={}, encounter_facts={}, open_questions=[],
            verification={}, sha256='c' * 64)

    def v3(self, tag):
        """An interpreted and appraised upload read at the current versions (AMENDMENT-2 8.1): its cpt-studio-events@3
        assessment current on its gemini context."""
        from studio import interpretation
        encounter = self.extracted(self.encounter(tag))
        made = self.current_inventory(encounter)
        context = self.context(encounter, version=interpretation.CONTEXT_VERSION_V2, inventory=made)
        self.assessment(encounter, context, engine_version=interpretation.ENGINE_VERSION_V3,
                        provider_run=self.made_run(encounter), inventory=made)
        return encounter

    def job(self, encounter, kind, state, *, tag=''):
        from django.utils import timezone
        from studio import models
        return models.Job.objects.create(
            encounter=encounter, revision=encounter.current_revision, kind=kind, state=state,
            idempotency_key=f'{kind}:{encounter.pk}:{state}{tag}', deadline_at=timezone.now() + dt.timedelta(minutes=9),
            started_at=timezone.now() - dt.timedelta(seconds=5) if state == models.Job.RUNNING else None)

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

    def close(self, *, revert, kinds=None):
        from django.utils import timezone
        return run_in_image(install.CLOSE_STAGES, {
            'since': timezone.now().isoformat(), 'note': 'Closed by the installer: synthetic undo.',
            'kinds': kinds if kinds is not None else list(install.COMMON_STAGE_KINDS), 'revert': revert,
            'reading_kinds': list(install.READING_STAGE_KINDS)})


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


class RealRowsWorld(AppWorld):
    """AppWorld whose two pre-switch reads run the REAL scripts on the test database."""

    def app_script(self, image_id, env_bytes, body, params, **kwargs):
        if body in (install.V1_ROWS, install.INSTALL_COUNTS):
            self.timeline.append(('script', body))
            return run_in_image(body, params)
        return super().app_script(image_id, env_bytes, body, params, **kwargs)


class AssertionAcrossInstallsTests(V2Rows):
    """FINAL-V2 6.2 and 9.3 (ops): install, one v2 row, switch-back, re-install and a same-revision app all pass the
    assertion - the real phase_app, its two reads run on real rows - and a v1 row refuses before the switch."""

    def setUp(self):
        super().setUp()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = Path(holder.name)
        self.world = RealRowsWorld(self.tmp)

    def app(self):
        patches = self.world.patches()
        for patcher in patches:
            patcher.start()
        try:
            return install.phase_app(install.Context(app_args(self.tmp, astra='disabled', fable='disabled'), self.tmp))
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def replaces(self):
        return [event for event in self.world.timeline if event[0] == 'replace']

    def test_install_v2_row_switch_back_reinstall_and_same_revision_app_pass_and_a_v1_row_refuses(self):
        first = self.app()  # the first install over the installed release: no row of any design yet
        self.assertEqual(first['v1_rows']['encounter_count'], 0)
        self.assertTrue(first['install_counts']['values']['first_install'])
        self.v2('upload')  # one v2 row
        self.assertEqual(self.app()['v1_rows']['encounter_count'], 0)  # a fix release after the walk
        # the switch-back: the installed release serves again and writes its own legacy rows
        switched = self.extracted(self.encounter('after-switch-back'))
        self.assessment(switched, self.context(switched), engine_version='cpt-studio-validation@10')
        reinstall = self.app()  # the re-install after the switch-back
        self.assertEqual(reinstall['v1_rows']['encounter_count'], 0)
        self.assertFalse(reinstall['install_counts']['values']['first_install'])  # a gemini context exists now
        self.assertEqual(self.app()['v1_rows']['encounter_count'], 0)  # a same-revision app re-run
        self.assertEqual(len(self.replaces()), 4)
        held = self.extracted(self.encounter('test-instance'))  # a test instance's v1 row
        self.assessment(held, self.context(held), engine_version='cpt-studio-events@1')
        self.world.timeline.clear()
        with self.assertRaises(install.InstallError) as caught:
            self.app()
        self.assertIn(str(held.pk), str(caught.exception))
        self.assertEqual(self.replaces(), [])  # refused before the switch


class InstallCountsOnTheDatabaseTests(V2Rows):
    def read(self):
        return run_in_image(install.INSTALL_COUNTS, {'limit': install.NAMED_LIMIT,
                                                     'token_sentence': install.CORTI_TOKEN_REFUSAL})

    def test_a_clean_target_counts_nothing_and_says_it_in_its_shape(self):
        self.legacy('legacy')
        answer = self.read()
        self.assertEqual(install.counts_problem(answer), '')
        self.assertEqual((answer['size']['without_inventory'], answer['size']['over_chars'],
                          answer['size']['unframed'], answer['values']['count'], answer['a21']['count']), (1, 0, 0, 0, 0))
        self.assertEqual(answer['size']['longest_chars'], len('Synthetic colonoscopy note.'))
        self.assertTrue(answer['values']['first_install'])
        self.assertEqual(answer['refused'], {name: {'count': 0, 'newest': None}
                                             for name in ('corti_sent', 'participant_sent', 'corti_token')})
        self.assertEqual(answer['holds'], {'provider': {'corti': [], 'astra': [], 'fable': []}, 'interpreter': []})

    def test_size_and_framing_count_only_revisions_with_no_inventory_at_the_current_versions(self):
        from django.test import override_settings
        long_text = 'Synthetic colonoscopy note. ' * 800  # over 20,000 characters
        over = self.extracted(self.encounter('over-chars'), text=long_text)
        labelled = self.extracted(self.encounter('labelled'), text='Synthetic note [S2] with a unit label.')
        unextracted = self.encounter('unextracted')  # no text at all: an extraction that has not run
        blank = self.extracted(self.encounter('blank'), text='')  # extracted, and empty: class b (6b-r1 P8)
        self.v3('read-now')  # an inventory read at the current versions: never counted, whatever its text
        two_pages = 'Synthetic page one.\fSynthetic page two.'
        paged = self.extracted(self.encounter('paged'), text=two_pages,
                               pages=[{'page': 1, 'start': 0, 'end': 19}, {'page': 2, 'start': 20, 'end': 39}])
        with override_settings(INTERPRET_MAX_PAGES=1):
            answer = self.read()
        size = answer['size']
        self.assertEqual(install.counts_problem(answer), '')
        self.assertEqual((size['bound_chars'], size['bound_pages']), (20000, 1))
        self.assertEqual(size['encounters']['over_chars'], [str(over.pk)])
        self.assertEqual(size['encounters']['over_pages'], [str(paged.pk)])
        self.assertEqual(sorted(size['encounters']['unframed']),
                         sorted([str(labelled.pk), str(unextracted.pk), str(blank.pk)]))
        self.assertEqual(size['unframed_empty'], 2)
        self.assertEqual(size['unframed_unextracted'], 1)  # its extraction has not run (refutation 6b-r1 P8)
        self.assertEqual(size['without_inventory'], 5)  # every current revision but the one read now
        report = ' | '.join(install.counts_report(answer))
        self.assertIn('2 encounter(s) with no inventory at the current versions have a text that cannot be framed (1 '
                      'of them an extracted text that is empty): their details cannot be changed', report)
        self.assertIn('1 encounter(s) have no text because their extraction failed or has not run', report)
        self.assertEqual(size['longest_chars'], len(long_text))

    def test_saved_values_not_yet_read_are_counted_and_named_on_the_first_install_only(self):
        pending = self.legacy('pending', user_values={'setting': 'office'})
        self.legacy('same', user_values={'setting': ' office '}, context_values={'setting': 'office'})  # normalized
        noctx = self.extracted(self.encounter('no-context'))  # an upload whose analysis failed: outside the count
        from studio import models
        models.Encounter.objects.filter(pk=noctx.pk).update(user_values={'service_date': '2026-11-10'})
        answer = self.read()
        self.assertEqual(answer['values'], {'count': 1, 'first_install': True, 'encounters': [str(pending.pk)]})
        self.v2('upload')  # v2 has run: a gemini context and a v2 inventory exist
        answer = self.read()
        self.assertEqual(answer['values'], {'count': 1, 'first_install': False, 'encounters': []})

    def test_a_save_whose_current_context_is_of_an_earlier_revision_is_outside_the_count(self):
        # refutation 6b-r1 P5 (mutant X4): 9.5 counts "a current context of their current revision" - an addendum
        # recorded after a case-B save leaves the current context on revision 1 while the current revision is 2
        from django.utils import timezone
        from studio import models
        encounter = self.legacy('addendum-after-save', user_values={'setting': 'asc'},
                                context_values={'setting': 'office'})
        self.assertEqual(self.read()['values']['count'], 1)  # before the addendum: counted
        addendum = models.SourceRevision.objects.create(
            encounter=encounter, number=2, kind=models.SourceRevision.ADDENDUM, addendum_text='Synthetic addendum.',
            parent=encounter.current_revision, synthetic_attested_by=encounter.created_by,
            synthetic_attested_at=timezone.now(), created_by=encounter.created_by)
        models.Encounter.objects.filter(pk=encounter.pk).update(current_revision=addendum)
        answer = self.read()
        self.assertEqual(install.counts_problem(answer), '')
        self.assertEqual(answer['values'], {'count': 0, 'first_install': True, 'encounters': []})

    def test_refusals_recorded_before_the_install_that_no_hold_names(self):
        from studio import models
        encounter = self.legacy('refusals')
        quota = self.made_run(encounter, state='failed', http_status=402, request='1')
        self.made_run(encounter, state='failed', http_status=500, request='2')  # a 5xx: not a hold's status
        self.made_run(encounter, provider='replay', state='failed', http_status=429, request='3')  # Corti's replay
        held = self.made_run(encounter, state='failed', http_status=401, request='4')
        models.ProviderHold.objects.create(provider='corti', reason='auth', http_status=401, run=held)  # v2 named it
        token = self.made_run(encounter, state='not_sent', sent=False, http_status=None, request='5',
                         error='Corti authentication was refused (HTTP 401); no coding request was sent.')
        self.made_run(encounter, state='not_sent', sent=False, http_status=None, request='6',
                 error='Corti could not be reached; no coding request was sent.')
        astra = self.made_run(encounter, provider='astra', purpose='independent', state='failed', http_status=400,
                         request='7')
        models.ProviderExchange.objects.create(run=astra, turn=1, request_body={}, request_sha256='f' * 64,
                                               state='failed', http_status=400)
        fable = self.made_run(encounter, provider='fable', purpose='independent', state='failed', http_status=413,
                         request='8')
        models.ProviderExchange.objects.create(run=fable, turn=1, request_body={}, request_sha256='f' * 64,
                                               state='failed', http_status=413)  # its own size: never a hold
        answer = self.read()
        self.assertEqual(install.counts_problem(answer), '')
        refused = answer['refused']
        self.assertEqual((refused['corti_sent']['count'], refused['participant_sent']['count'],
                          refused['corti_token']['count']), (2, 1, 1))
        self.assertEqual(refused['corti_token']['newest'], token.created_at.isoformat())
        self.assertLessEqual(quota.created_at.isoformat(), refused['corti_sent']['newest'])
        standing = answer['holds']['provider']['corti']
        self.assertEqual([item['run'] for item in standing], [str(held.pk)])  # the provider holds, in the transcript

    def test_a_reconciled_unknown_document_review_while_a_reading_is_owed_is_a21(self):
        from studio import models
        a21 = self.extracted(self.encounter('a21'))
        unknown = self.made_run(a21, state='unknown', http_status=None, reconciled=True)
        self.assessment(a21, self.context(a21), provider_run=unknown)  # a legacy context: a reading is owed
        settled = self.extracted(self.encounter('reconciled-v2'))  # a v2 encounter read at the current versions
        made = self.current_inventory(settled)  # AMENDMENT-2 8.1's (jobs.current_versions)
        self.assessment(settled, self.context(settled, version='gemini-context@2', inventory=made),
                        engine_version='cpt-studio-events@3', inventory=made,
                        provider_run=self.made_run(settled, state='unknown', http_status=None, reconciled=True))
        open_unknown = self.extracted(self.encounter('unreconciled'))
        self.assessment(open_unknown, self.context(open_unknown),
                        provider_run=self.made_run(open_unknown, state='unknown', http_status=None))
        answer = self.read()
        self.assertEqual(answer['a21'], {'count': 1, 'encounters': [str(a21.pk)]})
        self.assertEqual(models.Encounter.objects.count(), 3)


class CloseOnTheDatabaseTests(V2Rows):
    def test_an_appraise_stage_is_closed_by_an_undo_whose_next_worker_does_not_run_it(self):
        from studio import models
        queued, running, stopped = (self.extracted(self.encounter(tag)) for tag in ('queued', 'running', 'stopped'))
        self.job(queued, 'appraise', models.Job.QUEUED)
        self.job(running, 'appraise', models.Job.RUNNING)
        sending = self.made_run(running, provider='gemini', purpose='appraisal', state='sending', http_status=None)
        models.ProviderExchange.objects.create(run=sending, turn=1, request_body={}, request_sha256='f' * 64,
                                               state='succeeded', http_status=200)  # the answer reached CPT Studio
        self.job(stopped, 'interpret', models.Job.SUCCEEDED, tag='-earlier')  # pass 1, finished before it
        self.job(stopped, 'appraise', models.Job.CANCELLED)  # paused or stopped: its encounter's latest stage
        kept = self.close(revert=False, kinds=sorted([*install.COMMON_STAGE_KINDS, 'interpret', 'appraise']))
        self.assertEqual((kept['closed'], kept['kinds']), (0, []))  # a v2 next worker keeps them all
        self.assertNotIn('reading_closed', kept)
        self.assertNotIn('update_revert', kept)  # nothing to say: the answer is as it was
        closed = self.close(revert=True)
        self.assertEqual((closed['closed'], closed['kinds'], closed['encounters']), (3, ['appraise'], 3))
        self.assertEqual(closed['reading_closed'], {'appraise': 3})
        self.assertIs(closed['update_revert'], True)  # the next worker runs no appraise
        self.assertEqual(closed['runs_unknown'], 1)
        self.assertEqual(set(models.Job.objects.filter(kind='appraise').values_list('state', flat=True)),
                         {models.Job.FAILED})
        sending.refresh_from_db()
        self.assertEqual((sending.state, sending.sent), (models.ProviderRun.UNKNOWN, True))  # may have reached Google

    def test_a_worker_that_cannot_run_appraise_counts_it_stuck_and_one_that_can_does_not(self):
        from studio import jobs, models
        encounter = self.extracted(self.encounter('stuck'))
        self.job(encounter, 'appraise', models.Job.QUEUED)
        self.assertIn('appraise', jobs.STAGES)  # this revision's worker runs it
        without = {kind: stage for kind, stage in jobs.STAGES.items() if kind not in install.READING_STAGE_KINDS}
        with mock.patch.object(jobs, 'STAGES', without):  # the installed c2e53f8e's worker
            answer = run_in_image(install.UNRUNNABLE_STAGES, {})
        self.assertEqual((answer['stuck'], answer['kinds']), (1, ['appraise']))
        answer = run_in_image(install.UNRUNNABLE_STAGES, {})
        self.assertEqual((answer['stuck'], answer['kinds']), (0, []))
        self.assertIn('appraise', answer['known'])

    def test_the_undo_names_every_pending_update_and_reverts_a_pending_saves_unapplied_values(self):
        from studio import models
        # U17's states (amendment 1, 9.4): pending before analyze (a legacy encounter whose save is not read yet, its
        # reading stage queued), pending after analyze (a gemini context current, the legacy assessment on the earlier
        # context), completed (a v2 assessment current on its context), and A21's (a reconciled unknown document
        # review, no save)
        before = self.legacy('before-analyze', user_values={'setting': 'office', 'service_date': '2026-11-10',
                                                            'kept': 'synthetic'},
                             context_values={'service_date': '2026-11-10'})
        self.job(before, 'interpret', models.Job.QUEUED)
        after = self.legacy('after-analyze', user_values={'setting': 'asc'}, context_values={'setting': 'asc'})
        made = self.inventory(after)
        current = self.context(after, version='gemini-context@2', inventory=made, user_values={'setting': 'asc'},
                               earlier=models.Encounter.objects.get(pk=after.pk).current_assessment)
        models.Encounter.objects.filter(pk=after.pk).update(current_context=current)
        completed = self.v2('completed')
        a21 = self.extracted(self.encounter('a21'))
        self.assessment(a21, self.context(a21),
                        provider_run=self.made_run(a21, state='unknown', http_status=None, reconciled=True))
        closed = self.close(revert=True)
        self.assertEqual(closed['update_pending'], {str(before.pk): ['values_saved'],
                                                    str(after.pk): ['assessment_off_context'],
                                                    str(a21.pk): ['reconciled_unknown']})
        self.assertNotIn(str(completed.pk), closed['update_pending'])
        self.assertEqual(closed['reverted'], {str(before.pk): {'setting': {'saved': 'office', 'restored': None}}})
        self.assertEqual(closed['hazards'], {})  # never a hazard, so never a refusal
        self.assertIs(closed['update_revert'], True)
        self.assertEqual(closed['reading_closed'], {'interpret': 1})
        reverted = models.Encounter.objects.get(pk=before.pk)
        self.assertEqual(reverted.user_values, {'service_date': '2026-11-10', 'kept': 'synthetic'})
        audit = models.AuditEvent.objects.get(encounter=reverted, event='context.rollback_reverted')
        self.assertEqual((audit.actor_id, audit.actor_kind, audit.data['fields']), (None, 'system', ['setting']))
        self.assertEqual(audit.data['context'], str(reverted.current_context_id))
        self.assertEqual(models.Encounter.objects.get(pk=after.pk).user_values, {'setting': 'asc'})  # not reverted
        again = self.close(revert=True)  # the second close (B7) finds the revert done: named, nothing reverted
        self.assertNotIn('reverted', again)
        self.assertNotIn(str(before.pk), again['update_pending'])
        self.assertEqual(models.AuditEvent.objects.filter(event='context.rollback_reverted').count(), 1)
        # and the note the switch-back writes lists them, D59's clause kept beside them
        with mock.patch.object(install, 'app_script', in_this_image):
            note = install.with_update_note(install.interpretation_note(IMAGE, b'', REVISION), [closed, again])
        self.assertEqual(note['update_pending'], sorted([str(before.pk), str(after.pk), str(a21.pk)]))
        self.assertEqual(note['reverted'], closed['reverted'])
        self.assertIn('3 encounters read an update of their codes pending (update_pending)', note['note'])
        self.assertIn('the unapplied details of 1 encounter were set back', note['note'])

    def test_a_next_worker_with_the_update_has_nothing_reverted(self):
        from studio import models
        pending = self.legacy('pending', user_values={'setting': 'office'})
        closed = self.close(revert=False, kinds=sorted([*install.COMMON_STAGE_KINDS, 'interpret', 'appraise']))
        self.assertEqual(closed['update_pending'], {str(pending.pk): ['values_saved']})
        self.assertNotIn('reverted', closed)
        self.assertIs(closed['update_revert'], False)
        self.assertEqual(models.Encounter.objects.get(pk=pending.pk).user_values, {'setting': 'office'})
        self.assertFalse(models.AuditEvent.objects.filter(event='context.rollback_reverted').exists())

    def test_a_save_on_a_context_of_another_revision_is_named_never_reverted(self):
        from django.utils import timezone
        from studio import models
        encounter = self.legacy('addendum', user_values={'setting': 'office'})
        addendum = models.SourceRevision.objects.create(
            encounter=encounter, number=2, kind=models.SourceRevision.ADDENDUM, addendum_text='Synthetic addendum.',
            parent=encounter.current_revision, synthetic_attested_by=encounter.created_by,
            synthetic_attested_at=timezone.now(), created_by=encounter.created_by)
        models.Encounter.objects.filter(pk=encounter.pk).update(current_revision=addendum)
        closed = self.close(revert=True)
        self.assertEqual(closed['update_pending'], {str(encounter.pk): ['values_saved']})
        self.assertNotIn('reverted', closed)


# --- the switch-back's note, through the real phase ----------------------------------------------------------------

class SwitchBackNoteTests(TemporaryDirectoryTest):
    def switched_in(self):
        world = BlueGreenWorld(self.tmp, live=9151, serving=(REVISION, IMAGE))
        world.stage_kinds[IMAGE] = KINDS_OLD + ['interpret', 'appraise']
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'replaced': {'web': {'id': 'web-old', 'image': OLD_IMAGE, 'revision': OLD},
                         'worker': {'id': 'worker-old', 'image': OLD_IMAGE, 'revision': OLD}}}})
        return world

    def test_the_switch_back_lists_the_pending_updates_and_the_reverted_saves_and_never_refuses_on_them(self):
        world = self.switched_in()
        world.interpretation_answer = {'interpretation': {'assessments': 1, 'encounters': ['e2'],
                                                          'context_only': []}}
        world.close_answer = {'closed': 1, 'kinds': ['appraise'], 'hazards': {}, 'relabel': [],
                              'reading_closed': {'appraise': 1},
                              'update_pending': {'e1': ['values_saved'], 'e2': ['assessment_off_context']},
                              'reverted': {'e1': {'setting': {'saved': 'office', 'restored': 'asc'}}}}
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        self.assertIsNone(error, error and str(error))
        note = details['interpretation']
        self.assertEqual(note['update_pending'], ['e1', 'e2'])
        self.assertEqual(note['reverted'], {'e1': {'setting': {'saved': 'office', 'restored': 'asc'}}})
        self.assertEqual(note['reading_closed'], {'appraise': 2})  # B4's close and B7's, each answering one
        self.assertEqual(details['interpretation_at_b4']['reading_closed'], {'appraise': 1})
        self.assertIn('2 encounters read an update of their codes pending (update_pending)', details['summary'])
        self.assertIn('ask each member to save the change again on the earlier web', details['summary'])
        # the previous worker runs no appraise: every close keeps only its kinds
        self.assertEqual([close['kinds'] for close in world.closes], [KINDS_OLD, KINDS_OLD])



# --- refutation 6b-r1 P2: an undo that hands the site to no earlier pair puts the close's revert back -----------------

# a close (CLOSE_STAGES' answer) that set one pending save back for an earlier image
REVERTED_CLOSE = {'closed': 1, 'kinds': ['interpret'], 'hazards': {}, 'relabel': [], 'reading_closed': {'interpret': 1},
                  'update_pending': {'e1': ['values_saved']}, 'update_revert': True,
                  'reverted': {'e1': {'setting': {'saved': 'asc', 'restored': 'office'}}}}


def reverted_close(**changes):
    return {**json.loads(json.dumps(REVERTED_CLOSE)), **changes}


class ReapplyAnswerTests(unittest.TestCase):
    def test_nothing_set_back_runs_nothing(self):
        with mock.patch.object(install, 'app_script', side_effect=AssertionError('nothing may run')):
            for closes in ([], [None], [{'closed': 0, 'hazards': {}, 'relabel': []}],
                           [reverted_close(reverted={}, update_pending={})]):
                done = install.reapply_reverted(IMAGE, b'', closes)
                self.assertEqual((done['asked'], done['problem'], done['sentence']), ({}, '', ''), closes)

    def test_the_closes_set_back_values_are_given_and_what_it_did_is_read(self):
        seen = []

        def app_script(image_id, env_bytes, body, params, **kwargs):
            seen.append((image_id, body, params))
            return {'reapplied': {'e1': ['setting']}, 'not_reapplied': {'e2': 'values_changed'},
                    'requeued': {'e1': {'kind': 'interpret', 'job': 'j1'}}, 'coalesced': {}, 'not_requeued': {}}
        second = reverted_close(update_pending={'e2': ['values_saved']},
                                reverted={'e2': {'billing_context': {'saved': 'facility', 'restored': None}}})
        with mock.patch.object(install, 'app_script', app_script):
            done = install.reapply_reverted(IMAGE, b'', [reverted_close(), second])
        self.assertEqual(seen, [(IMAGE, install.REAPPLY_REVERTED, {'reverted': {
            'e1': {'setting': {'saved': 'asc', 'restored': 'office'}},
            'e2': {'billing_context': {'saved': 'facility', 'restored': None}}}})])
        self.assertEqual((done['asked'], done['reapplied'], done['not_reapplied'], done['problem']),
                         ({'e1': ['setting'], 'e2': ['billing_context']}, {'e1': ['setting']},
                          {'e2': 'values_changed'}, ''))
        self.assertEqual(done['requeued'], {'e1': {'kind': 'interpret', 'job': 'j1'}})
        self.assertIn('the unapplied details the close had set back on 1 encounter were put back '
                      '(context.rollback_reapplied)', done['sentence'])
        self.assertIn('the first reading stage the update of 1 of them owes was queued again, once each (interpret 1;',
                      done['sentence'])
        self.assertNotIn('until a member tries it again', done['sentence'])  # refutation 6b-r2 F2
        self.assertIn('1 encounter was left as the close set it, having changed since', done['sentence'])

    def test_a_put_back_that_does_not_say_what_it_did_or_fails_is_said_never_read_as_done(self):
        queued = {'coalesced': {}, 'not_requeued': {}}
        for answer in ({}, None, {'reapplied': {}, 'not_reapplied': {}},
                       {'reapplied': {'e1': ['billing_context']}, 'not_reapplied': {}},
                       {'reapplied': {'e1': ['setting']}, 'not_reapplied': {'e1': 'gone'}},
                       {'reapplied': {}, 'not_reapplied': {'e1': ''}},
                       # D247 DQ1: what it queued again must be said for each encounter put back, and for no other
                       {'reapplied': {'e1': ['setting']}, 'not_reapplied': {}},
                       {'reapplied': {'e1': ['setting']}, 'not_reapplied': {}, 'requeued': {}, **queued},
                       {'reapplied': {'e1': ['setting']}, 'not_reapplied': {},
                        'requeued': {'e1': {'kind': 'predict', 'job': 'j1'}}, **queued},
                       {'reapplied': {'e1': ['setting']}, 'not_reapplied': {},
                        'requeued': {'e1': {'kind': 'interpret', 'job': ''}}, **queued},
                       {'reapplied': {'e1': ['setting']}, 'not_reapplied': {}, 'requeued': {},
                        'coalesced': {}, 'not_requeued': {'e1': 'because'}},
                       {'reapplied': {'e1': ['setting']}, 'not_reapplied': {},
                        'requeued': {'e1': {'kind': 'interpret', 'job': 'j1'}}, 'coalesced': {},
                        'not_requeued': {'e1': 'no_save'}},
                       {'reapplied': {}, 'not_reapplied': {'e1': 'gone'},
                        'requeued': {'e1': {'kind': 'interpret', 'job': 'j1'}}, **queued}):
            with mock.patch.object(install, 'app_script', return_value=answer):
                done = install.reapply_reverted(IMAGE, b'', [reverted_close()])
            self.assertEqual(done['problem'], 'the put-back did not say what it did', answer)
            # refutation 6b-r2 F1/F2: the encounters named, and neither "put back" nor "not put back" claimed
            self.assertIn('the unapplied details the close set back on 1 encounter (e1; context.rollback_reverted) may '
                          'not have been put back (the put-back did not say what it did): context.rollback_reapplied '
                          'names each one that was, so ask each of those members to check their details',
                          done['sentence'])
        with mock.patch.object(install, 'app_script',
                               side_effect=install.InstallError('Putting back the details failed (exit 1).')):
            done = install.reapply_reverted(IMAGE, b'', [reverted_close()])
        self.assertIn('(e1; context.rollback_reverted) may not have been put back (Putting back the details failed '
                      '(exit 1).)', done['sentence'])
        with mock.patch.object(install, 'app_script', side_effect=KeyboardInterrupt()), \
                self.assertRaises(KeyboardInterrupt):
            install.reapply_reverted(IMAGE, b'', [reverted_close()])  # an interrupt is never swallowed
        unsaid = reverted_close(update_pending={'e1': ['assessment_off_context']})  # a revert it does not name so
        with mock.patch.object(install, 'app_script', side_effect=AssertionError('nothing may run')):
            done = install.reapply_reverted(IMAGE, b'', [unsaid])
        self.assertEqual(done['problem'], 'a close did not say what it set back')
        self.assertIn('were not put back (a close did not say what it set back)', done['sentence'])

    def test_the_note_of_an_undo_that_handed_nothing_says_so_and_keeps_d59(self):
        counted = {'assessments': 1, 'encounters': ['e2'], 'context_only': [], 'reinstatable': ['e2'],
                   'note': '1 assessment was made from event inventories; the earlier image reads them fail-closed'}
        note = install.undone_note(counted)
        self.assertIs(note['handed'], False)
        self.assertEqual(note['reinstatable'], ['e2'])
        self.assertTrue(note['note'].startswith('handed to no earlier web: the undo kept this revision\'s web serving'))
        self.assertTrue(note['note'].endswith(counted['note']))
        self.assertNotIn('update_pending', note)
        self.assertNotIn('reverted', note)
        self.assertEqual(counted['note'][:1], '1')  # the counted note itself is left as it was


class ReapplyOnTheDatabaseTests(V2Rows):
    """REAPPLY_REVERTED on real rows, after the real CLOSE_STAGES set the saves back."""

    def reapply(self, closes):
        with mock.patch.object(install, 'app_script', in_this_image):
            return install.reapply_reverted(IMAGE, b'', closes)

    def pending(self, tag):
        from studio import models
        encounter = self.legacy(tag, user_values={'setting': 'office', 'service_date': '2026-11-10',
                                                  'kept': 'synthetic'},
                                context_values={'service_date': '2026-11-10'})
        self.job(encounter, 'interpret', models.Job.QUEUED)
        return encounter

    def test_an_undone_close_puts_the_saved_values_back_and_the_update_reads_pending_again(self):
        from studio import models, review
        encounter = self.pending('pending')
        closed = self.close(revert=True)
        self.assertEqual(closed['reverted'], {str(encounter.pk): {'setting': {'saved': 'office', 'restored': None}}})
        self.assertFalse(review.update_pending(models.Encounter.objects.get(pk=encounter.pk)))  # 6b-r1 P2's state
        done = self.reapply([closed])
        self.assertEqual((done['asked'], done['reapplied'], done['not_reapplied'], done['problem']),
                         ({str(encounter.pk): ['setting']}, {str(encounter.pk): ['setting']}, {}, ''))
        back = models.Encounter.objects.get(pk=encounter.pk)
        self.assertEqual(back.user_values, {'setting': 'office', 'service_date': '2026-11-10', 'kept': 'synthetic'})
        self.assertTrue(review.update_pending(back))
        self.assertFalse(review.fresh(back))
        audit = models.AuditEvent.objects.get(encounter=back, event='context.rollback_reapplied')
        self.assertEqual((audit.actor_id, audit.actor_kind, audit.data),
                         (None, 'system', {'fields': ['setting'], 'context': str(back.current_context_id)}))
        self.assertIn('were put back (context.rollback_reapplied)', done['sentence'])
        again = self.reapply([closed])  # a second put-back finds the values changed since the revert: nothing done
        self.assertEqual((again['reapplied'], again['not_reapplied']), ({}, {str(encounter.pk): 'values_changed'}))
        self.assertEqual(models.AuditEvent.objects.filter(event='context.rollback_reapplied').count(), 1)

    def test_a_save_or_a_context_made_since_the_revert_is_left_as_it_stands(self):
        from studio import models
        saved, remade = self.pending('saved-since'), self.pending('context-since')
        closed = self.close(revert=True)
        self.assertEqual(sorted(closed['reverted']), sorted([str(saved.pk), str(remade.pk)]))
        changed = {'service_date': '2026-11-10', 'setting': 'hospital'}  # a member's save on the web that serves
        models.Encounter.objects.filter(pk=saved.pk).update(user_values=changed)
        newer = self.context(remade, user_values={'service_date': '2026-11-10'})  # a context written since
        models.Encounter.objects.filter(pk=remade.pk).update(current_context=newer)
        done = self.reapply([closed])
        self.assertEqual(done['reapplied'], {})
        self.assertEqual(done['not_reapplied'], {str(saved.pk): 'values_changed', str(remade.pk): 'context_changed'})
        self.assertEqual(models.Encounter.objects.get(pk=saved.pk).user_values, changed)
        self.assertEqual(models.Encounter.objects.get(pk=remade.pk).user_values,
                         {'service_date': '2026-11-10', 'kept': 'synthetic'})
        self.assertFalse(models.AuditEvent.objects.filter(event='context.rollback_reapplied').exists())
        self.assertIn('2 encounters were left as the close set them, having changed since', done['sentence'])


class UndoneUndoTests(TemporaryDirectoryTest):
    """The REAL phases: every undo that, after its close set saves back, keeps this revision's web serving (or leaves
    neither pair running) puts them back in this revision's image; one that hands the site to the earlier pair does not."""

    def switched_in(self):
        world = BlueGreenWorld(self.tmp, live=9151, serving=(REVISION, IMAGE))
        world.stage_kinds[IMAGE] = KINDS_OLD + ['interpret', 'appraise']
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'replaced': {'web': {'id': 'web-old', 'image': OLD_IMAGE, 'revision': OLD},
                         'worker': {'id': 'worker-old', 'image': OLD_IMAGE, 'revision': OLD}}}})
        return world

    def test_a_switch_back_undone_at_b5_puts_the_saves_back_before_this_worker_resumes(self):
        world = self.switched_in()
        world.close_answer = reverted_close()
        world.fail[('https', 9150)] = install.InstallError('it did not serve the previous revision')
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        message, record = str(error), error.details or {}
        self.assertIn('nothing was switched', message)
        self.assertEqual(world.reapplies, [REVERTED_CLOSE['reverted']])
        reapply = world.events.index(('reapply', IMAGE))
        self.assertLess(world.events.index(('rm', install.INCOMING_WEB)), reapply)  # the previous web is gone first
        self.assertLess(reapply, len(world.events) - 1 - world.events[::-1].index(('start', WORKER)))
        self.assertIn('the unapplied details the close had set back on 1 encounter were put back '
                      '(context.rollback_reapplied)', message)
        self.assertEqual(record['closes']['reapplied']['reapplied'], {'e1': ['setting']})
        note = record['interpretation']
        self.assertIs(note['handed'], False)
        # refutation 6b-r2 F5 (D247): nginx was reloaded with the vhost naming the previous web (port 9150) and then
        # settled back, and the previous web was drained: it may have served in between, and the note says so
        self.assertIn(('reload', 9150), world.events)
        self.assertIn(('drain', 9150), world.events)
        self.assertTrue(note['note'].startswith('the earlier web may have served from the switch ('), note['note'])
        self.assertIn('the undo then kept this revision\'s web serving', note['note'])
        self.assertIn('the members of the 1 encounter with an update of their codes pending (update_pending) who used '
                      'it in that window saw the codes from before their change there', note['note'])
        self.assertEqual(note['update_pending'], ['e1'])
        self.assertEqual(sorted(note['served']), ['from', 'until'])
        self.assertLessEqual(install.utc_moment(note['served']['from']), install.utc_moment(note['served']['until']))
        for said in ('save the change again on the earlier web', 'handed to no earlier web'):
            self.assertNotIn(said, note['note'])
        self.assertNotIn('reverted', note)

    def test_a_switch_back_undone_at_b5_before_nginx_read_the_file_was_handed_to_no_earlier_web(self):
        # the control of F5: nginx -t refused the switched file, so no reload was asked for and nginx never read it
        world = self.switched_in()
        world.close_answer = reverted_close()
        world.nginx_answers = [{}, {'ok': False, 'output': 'synthetic: the switched file does not pass'}]
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        note = error.details['interpretation']
        self.assertNotIn(('reload', 9150), world.events)
        self.assertEqual(world.reapplies, [REVERTED_CLOSE['reverted']])
        self.assertIs(note['handed'], False)
        self.assertTrue(note['note'].startswith('handed to no earlier web: the undo kept this revision\'s web '
                                                'serving'), note['note'])
        self.assertNotIn('served', note)
        self.assertNotIn('update_pending', note)

    def test_a_switch_back_refused_after_b4s_close_puts_the_saves_back(self):
        world = self.switched_in()
        world.close_answer = reverted_close(hazards={'e3': ['outcome']})
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        message = str(error)
        self.assertIn('after this revision\'s worker stopped and its stages were closed', message)
        self.assertIn('nothing was switched', message)
        self.assertEqual(world.reapplies, [REVERTED_CLOSE['reverted']])
        self.assertIn('were put back (context.rollback_reapplied)', message)
        self.assertNotIn('interpretation', error.details)  # refused before B4's note was counted

    def test_a_put_back_that_fails_is_said_and_the_undo_goes_on(self):
        world = self.switched_in()
        world.close_answer = reverted_close()
        world.reapply_answer = install.InstallError('Putting back the details failed (exit 1).')
        world.fail[('https', 9150)] = install.InstallError('it did not serve the previous revision')
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        message = str(error)
        self.assertIn('the unapplied details the close set back on 1 encounter (e1; context.rollback_reverted) may not '
                      'have been put back (Putting back the details failed (exit 1).)', message)
        self.assertIn('this revision\'s worker was put back and started', message)

    def test_a_switch_back_that_completes_puts_nothing_back(self):
        world = self.switched_in()
        world.close_answer = reverted_close()
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.reapplies, [])
        self.assertIn('ask each member to save the change again on the earlier web', details['summary'])

    def test_an_s4_undo_that_keeps_the_new_web_serving_puts_the_saves_back(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = reverted_close(hazards={'e3': ['participant']})
        details, error = run_app(world)
        self.assertIn('the new web keeps serving on 9151', str(error))
        self.assertEqual(world.reapplies, [REVERTED_CLOSE['reverted']])
        self.assertIn('were put back (context.rollback_reapplied)', str(error))
        self.assertEqual(error.details['reapplied']['reapplied'], {'e1': ['setting']})

    def test_an_s4_undo_whose_put_back_fails_keeps_the_new_web_serving_and_puts_the_saves_back(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = reverted_close()
        world.fail[('put_back',)] = install.InstallError('the list states could not be read')
        details, error = run_app(world)
        self.assertIn('could not be put back (the list states could not be read), so the new web keeps serving',
                      str(error))
        self.assertEqual(world.reapplies, [REVERTED_CLOSE['reverted']])
        self.assertIn('were put back (context.rollback_reapplied)', str(error))

    def test_an_s4_undo_that_switches_back_to_the_old_web_puts_nothing_back(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = reverted_close()
        details, error = run_app(world)
        self.assertIn('the vhost was switched back', str(error))
        self.assertEqual(world.reapplies, [])
        # the old web is handed the rows with the saves set back, and the message says so (6b-r1 P2's class)
        self.assertIn('The close set the unapplied details of 1 encounter back to their context\'s values for the '
                      'earlier pair', str(error))

    def test_a_switch_back_undone_at_b5_words_an_a21_encounter_apart_in_the_served_note(self):
        # refutation w7r 6b-r1 R5: an update no save started had no change of its member pending there
        world = self.switched_in()
        world.close_answer = reverted_close(update_pending={'e1': ['values_saved'], 'e2': ['reconciled_unknown']})
        world.fail[('https', 9150)] = install.InstallError('it did not serve the previous revision')
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        note = error.details['interpretation']
        self.assertEqual(note['update_pending'], ['e1', 'e2'])
        self.assertEqual(error.details['closes']['served']['reconciled_unknown'], ['e2'])
        self.assertIn('the members of the 1 encounter with an update of their codes pending (update_pending) who used it '
                      'in that window saw the codes from before their change there', note['note'])
        self.assertIn('1 encounter with an update pending read an update no save started (a reconciled document '
                      'review, A21), so no change of their members was pending', note['note'])
        self.assertNotIn('the members of the 2 encounters', note['note'])  # never said of both

    def test_rollback_app_in_the_keep_layout_that_keeps_this_web_serving_puts_the_saves_back(self):
        world = keep_world(self.tmp)
        world.close_answer = reverted_close(hazards={'e3': ['participant']})
        details, error = run_rollback_app(world)
        self.assertIsNotNone(error)
        self.assertIn('so nothing more was done', str(error))
        self.assertEqual(world.reapplies, [REVERTED_CLOSE['reverted']])
        self.assertIn('were put back (context.rollback_reapplied)', str(error))
        self.assertEqual(error.details['reapplied']['reapplied'], {'e1': ['setting']})

    def swap(self, close, put_back=None, reapply=None):
        """The REAL replace_services on a fresh host (the swap), its new worker never ready: (message, details,
        [(image, params) of each REAPPLY_REVERTED it ran]); ``reapply``: an exception REAPPLY_REVERTED raises."""
        old = {role: {'Id': f'old-{role}', 'Image': 'sha256:' + 'd' * 64, 'Created': '2026-11-01T12:00:00.000000Z',
                      'State': {'Running': True},
                      'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role,
                                            install.REVISION_LABEL: 'b' * 40}}} for role in ('web', 'worker')}
        live = {install.SERVICES[role]: dict(container) for role, container in old.items()}
        asked = []

        def fake_docker(*args, **kwargs):
            if args[0] == 'rename':
                live[args[2]] = live.pop(args[1])
            elif args[0] == 'run':
                name = args[args.index('--name') + 1]
                role = 'web' if name == install.SERVICES['web'] else 'worker'
                live[name] = {**old[role], 'Id': f'new-{role}', 'Image': IMAGE}
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def wait(role, revision, image_id, **kwargs):
            if role == 'worker':
                raise install.InstallError('cpt-studio-worker did not become ready')
            return {'id': 'new-web'}

        def app_script(image_id, env_bytes, body, params, **kwargs):
            self.assertEqual(body, install.REAPPLY_REVERTED)
            asked.append((image_id, params))
            if reapply is not None:
                raise reapply
            return {'reapplied': {pk: sorted(fields) for pk, fields in params['reverted'].items()}, 'not_reapplied': {},
                    'requeued': {pk: {'kind': 'interpret', 'job': f'job-{pk}'} for pk in params['reverted']},
                    'coalesced': {}, 'not_requeued': {}}
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        put = (mock.patch.object(install, 'put_back_states', side_effect=put_back) if put_back is not None else
               mock.patch.object(install, 'put_back_states', return_value={'encounters': 0, 'changed': {}}))
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(name)), \
                mock.patch.object(install, 'docker', fake_docker), mock.patch.object(install, 'wait_service', wait), \
                mock.patch.object(install, 'stage_kinds_of', return_value=list(install.COMMON_STAGE_KINDS)), \
                mock.patch.object(install, 'close_undone_stages', return_value=close), put, \
                mock.patch.object(install, 'app_script', app_script), \
                self.assertRaises(install.InstallError) as caught:
            install.replace_services(ctx, IMAGE, b'', 'disabled', '', {'astra': 'disabled', 'fable': 'disabled'})
        return str(caught.exception), caught.exception.details or {}, asked

    def test_a_swap_left_with_neither_pair_running_puts_the_saves_back(self):
        message, details, asked = self.swap(reverted_close(hazards={'e3': ['participant']}))
        self.assertIn('the new pair was left stopped and the previous pair parked', message)
        self.assertIn('To keep this revision', message)
        self.assertEqual(asked, [(IMAGE, {'reverted': REVERTED_CLOSE['reverted']})])
        self.assertIn('were put back (context.rollback_reapplied)', message)
        self.assertEqual(details['reapplied']['reapplied'], {'e1': ['setting']})

    def test_a_swap_whose_only_way_on_is_back_keeps_the_revert_and_says_so(self):
        message, details, asked = self.swap(reverted_close(),
                                            put_back=install.InstallError('the list states could not be read'))
        self.assertIn('run --phase rollback-app, then rename the parked pair back.', message)
        self.assertEqual(asked, [])  # the previous pair reads them as set back
        self.assertIn('The close set the unapplied details of 1 encounter back to their context\'s values for the '
                      'earlier pair', message)
        self.assertEqual(details['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])

    def test_a_swap_that_restores_the_previous_pair_says_what_its_close_set_back(self):
        # refutation w7r 6b-r1's observation (6b-r1 P2's class): the bare failure was re-raised, the revert in the
        # undo log only - the previous pair serves with the saves set back, so the message and the receipt say it
        message, details, asked = self.swap(reverted_close())
        self.assertTrue(message.startswith('cpt-studio-worker did not become ready; the previous pair was restored. The '
                                           'close set the unapplied details of 1 encounter back to their context\'s '
                                           'values for the earlier pair'), message)
        self.assertIn('ask each of those members to save the change again there', message)
        self.assertEqual(asked, [])  # handed to the previous pair: nothing is put back
        self.assertEqual(details['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])
        held_message, held, asked = self.swap(reverted_close(hazards={'e3': ['outcome']}))
        self.assertIn('its worker (cpt-studio-worker) left stopped, so nothing can be sent', held_message)
        self.assertIn('The close set the unapplied details of 1 encounter back', held_message)
        self.assertEqual((asked, held['stages_closed']['reverted']), ([], REVERTED_CLOSE['reverted']))
        plain, plain_details, _ = self.swap({'closed': 1, 'kinds': ['interpret'], 'hazards': {}, 'relabel': []})
        self.assertEqual(plain, 'cpt-studio-worker did not become ready')  # nothing set back: the failure as it was


# --- refutation 6b-r2 (DECISIONS D247): F1, DQ1, F2, F3 and F4 --------------------------------------------------------

def owned_pair():
    """This revision's web and worker, running (phase_rollback_app outside the keep layout), as Docker inspects them."""
    return {role: {'Id': f'{role}-id', 'Image': IMAGE, 'Created': '2026-11-01T12:00:00.000000Z',
                   'State': {'Running': True},
                   'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role,
                                         install.REVISION_LABEL: REVISION}}}
            for role in ('web', 'worker')}


def rollback_app_outside_keep(tmp, *, close=None, close_raises=None, rm_raises=None, put_back=None, reapply=None,
                              made=None):
    """The REAL phase_rollback_app outside the keep layout, with only Docker, the env file and the in-image reads faked:
    (the InstallError it ends on or None, [(body name, params) of every in-image script after the close], [docker
    verbs]). ``reapply``: what REAPPLY_REVERTED answers (None: every encounter asked put back and its stage queued
    again; an exception: it raises that)."""
    live, scripts, verbs = owned_pair(), [], []
    names = {install.SERVICES[role]: role for role in ('web', 'worker')}

    def fake_docker(*args, **kwargs):
        verbs.append(args[0])
        if args[0] == 'rm' and rm_raises is not None:
            raise rm_raises
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

    def app_script(image_id, env_bytes, body, params, **kwargs):
        if body == install.REAPPLY_REVERTED:
            scripts.append(('REAPPLY_REVERTED', params))
            if isinstance(reapply, BaseException):
                raise reapply
            return reapply if reapply is not None else {
                'reapplied': {pk: sorted(fields) for pk, fields in params['reverted'].items()}, 'not_reapplied': {},
                'requeued': {pk: {'kind': 'interpret', 'job': f'job-{pk}'} for pk in params['reverted']},
                'coalesced': {}, 'not_requeued': {}}
        if body == install.INTERPRETATION_MADE:
            scripts.append(('INTERPRETATION_MADE', params))
            return made or {'interpretation': {'assessments': 0, 'encounters': [], 'context_only': []}}
        raise AssertionError('unexpected in-image script')

    def closing(*args, **kwargs):
        if close_raises is not None:
            raise close_raises
        return json.loads(json.dumps(close))
    with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(names.get(name))), \
            mock.patch.object(install, 'docker', fake_docker), \
            mock.patch.object(install, 'read_protected_env', return_value=b''), \
            mock.patch.object(install, 'require_db'), mock.patch.object(install, 'undo_hazards', return_value={}), \
            mock.patch.object(install, 'close_undone_stages', side_effect=closing), \
            mock.patch.object(install, 'put_back_states', return_value=put_back or {'encounters': 0, 'changed': {}}), \
            mock.patch.object(install, 'app_script', app_script):
        try:
            install.phase_rollback_app(install.Context(SimpleNamespace(phase='rollback-app', revision=REVISION), tmp))
        except install.InstallError as error:
            return error, scripts, verbs
    return None, scripts, verbs


class RollbackAppPutBackTests(TemporaryDirectoryTest):
    """Refutation 6b-r2 F1 (D247): before any message that leaves this revision's pair to serve again, rollback-app puts
    the saves its close set back back (as kept_serving does); when the put-back cannot run, it names the encounters
    whose saves were set back and says they were not put back."""

    def test_a_record_named_after_the_close_puts_the_saves_back_before_start_them_again(self):  # the refuter's Q1
        error, scripts, verbs = rollback_app_outside_keep(self.tmp, close=reverted_close(hazards={'e3': ['outcome']}))
        message, details = str(error), error.details
        self.assertIn('Start them again (docker start cpt-studio-worker cpt-studio-web)', message)
        self.assertEqual(scripts, [('REAPPLY_REVERTED', {'reverted': REVERTED_CLOSE['reverted']})])
        self.assertTrue(message.index('Start them again') < message.index('The unapplied details the close had set back'))
        self.assertIn('The unapplied details the close had set back on 1 encounter were put back '
                      '(context.rollback_reapplied): each reads its update pending again, as before the close; the '
                      'first reading stage the update of 1 of them owes was queued again, once each (interpret 1;',
                      message)
        self.assertEqual(details['reapplied']['reapplied'], {'e1': ['setting']})
        self.assertEqual(details['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])
        self.assertEqual(verbs, ['stop', 'stop'])  # stopped, not removed

    def test_a_put_back_that_cannot_run_names_the_encounters_whose_saves_were_set_back(self):
        failed = install.InstallError('Putting back the details failed (exit 1).')
        error, scripts, _ = rollback_app_outside_keep(self.tmp, close=reverted_close(hazards={'e3': ['outcome']}),
                                                      reapply=failed)
        self.assertEqual(len(scripts), 1)
        self.assertIn('Start them again', str(error))
        self.assertIn('The unapplied details the close set back on 1 encounter (e1; context.rollback_reverted) may not '
                      'have been put back (Putting back the details failed (exit 1).): context.rollback_reapplied names '
                      'each one that was, so ask each of those members to check their details', str(error))
        unsaid = reverted_close(hazards={'e3': ['outcome']}, update_pending={'e1': ['assessment_off_context']})
        error, scripts, _ = rollback_app_outside_keep(self.tmp, close=unsaid)
        self.assertEqual(scripts, [])  # what it set back is not said, so nothing can be asked
        self.assertIn('were not put back (a close did not say what it set back)', str(error))

    def test_a_record_named_after_a_close_that_set_nothing_back_runs_no_put_back(self):
        error, scripts, _ = rollback_app_outside_keep(self.tmp, close={'closed': 1, 'kinds': [], 'relabel': [],
                                                                       'hazards': {'e3': ['outcome']}})
        self.assertEqual(scripts, [])
        self.assertTrue(str(error).endswith('then rerun --phase rollback-app.'), str(error))

    def test_a_removal_that_fails_puts_the_saves_back_before_offering_to_keep_this_revision(self):  # the refuter's Q1b
        error, scripts, _ = rollback_app_outside_keep(
            self.tmp, close=reverted_close(), rm_raises=install.InstallError('synthetic: docker rm failed'),
            put_back={'encounters': 1, 'changed': {'e9': ['provider_failed', 'no_codes']}})
        message, details = str(error), error.details
        self.assertIn('synthetic: docker rm failed; before it, the list states of 1 encounter(s) were put back to what '
                      'the older revision derives, which this revision labels otherwise: rerun --phase rollback-app; or, '
                      'to keep this revision, rerun --phase app, which recomputes them.', message)
        self.assertEqual([name for name, _ in scripts], ['INTERPRETATION_MADE', 'REAPPLY_REVERTED'])
        self.assertIn('were put back (context.rollback_reapplied)', message)
        self.assertEqual(details['reapplied']['reapplied'], {'e1': ['setting']})
        note = details['interpretation']  # no earlier pair was started: none of its members' instructions
        self.assertIs(note['handed'], False)
        self.assertTrue(note['note'].startswith('handed to no earlier web: the removal of this revision\'s pair '
                                                'stopped before any earlier pair was started'), note['note'])
        self.assertNotIn('save the change again on the earlier web', note['note'])

    def test_a_removal_that_fails_with_no_state_put_back_still_puts_the_saves_back_and_says_how_to_go_on(self):
        error, scripts, _ = rollback_app_outside_keep(self.tmp, close=reverted_close(),
                                                      rm_raises=install.InstallError('synthetic: docker rm failed'))
        self.assertIn('synthetic: docker rm failed: rerun --phase rollback-app; or, to keep this revision, rerun --phase '
                      'app. The unapplied details the close had set back on 1 encounter were put back', str(error))
        self.assertEqual([name for name, _ in scripts], ['INTERPRETATION_MADE', 'REAPPLY_REVERTED'])

    def test_an_interrupted_removal_runs_nothing_more_and_names_the_saves_as_not_put_back(self):
        error, scripts, _ = rollback_app_outside_keep(self.tmp, close=reverted_close(), rm_raises=KeyboardInterrupt())
        self.assertEqual([name for name, _ in scripts], ['INTERPRETATION_MADE'])  # no put-back after a Ctrl-C
        self.assertIn('KeyboardInterrupt: rerun --phase rollback-app; or, to keep this revision, rerun --phase app. The '
                      'unapplied details the close set back on 1 encounter (e1; context.rollback_reverted, each field\'s '
                      'saved and restored value in stages_closed.reverted) were not put back (the phase was interrupted '
                      'before they could be)', str(error))
        self.assertIn('save the change again on the earlier web', error.details['interpretation']['note'])

    def test_control_a_removal_that_fails_with_nothing_set_back_or_put_back_raises_as_it_did(self):
        error, scripts, _ = rollback_app_outside_keep(
            self.tmp, close={'closed': 0, 'kinds': [], 'hazards': {}, 'relabel': []},
            rm_raises=install.InstallError('synthetic: docker rm failed'))
        self.assertEqual(str(error), 'synthetic: docker rm failed')  # the original error, as it was
        self.assertEqual([name for name, _ in scripts], ['INTERPRETATION_MADE'])

    def test_a_close_that_raised_names_the_rows_it_may_have_set_back(self):  # refutation 6b-r2 F4's class
        error, scripts, _ = rollback_app_outside_keep(
            self.tmp, close_raises=install.InstallError('Closing the stages failed (exit 1).'))
        started = error.details['close_started_at']
        self.assertIn('Web and worker stopped, not removed: the close of the stages they left open did not finish '
                      '(Closing the stages failed (exit 1).): it may have closed some or all of them before it stopped',
                      str(error))
        self.assertIn(f'and it may have set back the unapplied details of encounters with an update of their codes '
                      f'pending (context.rollback_reverted rows since {started}), which were not put back: ask those '
                      'members to check their details. Rerun --phase rollback-app once that is resolved.', str(error))
        self.assertEqual(scripts, [])


def rollback_app_through_main(receipts, *, close=None, close_raises=None, rm_raises=None, put_back=None, reapply=None,
                              require_db=None, count_raises=None):
    """The REAL install.main() for rollback-app outside the keep layout, with only Docker, the env file, the door and the
    in-image reads faked (refutation w7r 6b-r1 R1: what main() writes is the receipt): (its exit code, or what it let
    through; the receipt as written; [(body name, params) of every in-image script]; [docker verbs])."""
    live, scripts, verbs = owned_pair(), [], []
    names = {install.SERVICES[role]: role for role in ('web', 'worker')}

    def fake_docker(*args, **kwargs):
        verbs.append(args[0])
        if args[0] == 'rm' and rm_raises is not None:
            raise rm_raises
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

    def app_script(image_id, env_bytes, body, params, **kwargs):
        if body == install.REAPPLY_REVERTED:
            scripts.append(('REAPPLY_REVERTED', params))
            if isinstance(reapply, BaseException):
                raise reapply
            return reapply
        if body == install.INTERPRETATION_MADE:
            scripts.append(('INTERPRETATION_MADE', params))
            if count_raises is not None:
                raise count_raises
            return {'interpretation': {'assessments': 0, 'encounters': [], 'context_only': []}}
        raise AssertionError('unexpected in-image script')

    def closing(*args, **kwargs):
        if close_raises is not None:
            raise close_raises
        return json.loads(json.dumps(close))
    lock_fds, real_open = [], install.os.open

    def tracking_open(path, flags, mode=0o777, *, dir_fd=None):
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if str(path).endswith('/.lock'):
            lock_fds.append(fd)
        return fd
    patches = [mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(names.get(name))),
               mock.patch.object(install, 'docker', fake_docker),
               mock.patch.object(install, 'read_protected_env', return_value=b''),
               mock.patch.object(install, 'require_db', side_effect=require_db),
               mock.patch.object(install, 'undo_hazards', return_value={}),
               mock.patch.object(install, 'close_undone_stages', side_effect=closing),
               mock.patch.object(install, 'put_back_states',
                                 **({'side_effect': put_back} if isinstance(put_back, BaseException) else
                                    {'return_value': put_back or {'encounters': 0, 'changed': {}}})),
               mock.patch.object(install, 'app_script', app_script),
               mock.patch.object(install, 'check_door', lambda environ, revision: {'declaration_commit': '0' * 40}),
               mock.patch.object(install, 'check_tree', lambda revision, commit: {'mode': 'exact'}),
               mock.patch.object(install.os, 'open', tracking_open)]
    for patcher in patches:
        patcher.start()
    try:
        with mock.patch('sys.stdout', new_callable=lambda: __import__('io').StringIO()):
            try:
                outcome = install.main(['--phase', 'rollback-app', '--revision', REVISION, '--receipts',
                                        str(receipts)])
            except BaseException as raised:  # noqa: BLE001 - what main() let through is the observation
                outcome = raised
    finally:
        for patcher in reversed(patches):
            patcher.stop()
        for fd in lock_fds:
            install.os.close(fd)
    written = sorted(Path(receipts).glob('rollback-app-*.json'))
    return outcome, (json.loads(written[-1].read_text(encoding='utf-8')) if written else None), scripts, verbs


class InterruptedPutBackTests(TemporaryDirectoryTest):
    """Refutation w7r 6b-r1 R1: a Ctrl-C while the put-back runs never loses the receipt's record of what the close set
    back (the saved values are recorded nowhere else: the close's answer is their only record); the message names the
    encounters as possibly not put back (each is put back in its own transaction), and the phase still stops there."""

    def test_rollback_app_interrupted_while_putting_back_before_start_them_again_keeps_the_receipt(self):  # P1
        receipts = self.tmp / 'receipts-p1'
        close = reverted_close(hazards={'e3': ['outcome']})
        outcome, receipt, scripts, verbs = rollback_app_through_main(receipts, close=close, reapply=KeyboardInterrupt())
        self.assertEqual(outcome, 1)  # the phase stops, failed, with its receipt
        self.assertEqual([name for name, _ in scripts], ['REAPPLY_REVERTED'])
        self.assertFalse(receipt['ok'])
        self.assertIn('Start them again (docker start cpt-studio-worker cpt-studio-web)', receipt['error'])
        self.assertIn('The unapplied details the close set back on 1 encounter (e1; context.rollback_reverted) may not '
                      'have been put back (the put-back was interrupted (KeyboardInterrupt)): context.rollback_reapplied '
                      'names each one that was, so ask each of those members to check their details on whichever web '
                      'serves next.', receipt['error'])
        self.assertEqual(receipt['details']['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])  # 'asc' kept
        self.assertIs(receipt['details']['reapplied']['interrupted'], True)
        self.assertEqual(receipt['details']['reapplied']['asked'], {'e1': ['setting']})
        self.assertEqual(verbs, ['stop', 'stop'])  # stopped, not removed

    def test_rollback_app_interrupted_while_putting_back_after_a_removal_failure_keeps_the_receipt(self):  # P1b
        receipts = self.tmp / 'receipts-p1b'
        outcome, receipt, scripts, verbs = rollback_app_through_main(
            receipts, close=reverted_close(), rm_raises=install.InstallError('synthetic: docker rm failed'),
            put_back={'encounters': 1, 'changed': {'e9': ['provider_failed']}}, reapply=KeyboardInterrupt())
        self.assertEqual(outcome, 1)
        self.assertEqual([name for name, _ in scripts], ['INTERPRETATION_MADE', 'REAPPLY_REVERTED'])
        self.assertIn('synthetic: docker rm failed; before it, the list states of 1 encounter(s) were put back',
                      receipt['error'])
        self.assertIn('may not have been put back (the put-back was interrupted (KeyboardInterrupt))', receipt['error'])
        self.assertEqual(receipt['details']['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])
        self.assertIs(receipt['details']['reapplied']['interrupted'], True)
        # nothing was put back for certain, so the note keeps the earlier web's instructions
        self.assertIn('save the change again on the earlier web', receipt['details']['interpretation']['note'])

    def test_rollback_apps_own_close_interrupted_is_recorded_and_names_the_rows_it_may_have_set_back(self):
        receipts = self.tmp / 'receipts-close'
        outcome, receipt, scripts, _ = rollback_app_through_main(receipts, close_raises=KeyboardInterrupt())
        self.assertEqual(outcome, 1)
        started = receipt['details']['close_started_at']
        self.assertIn('Web and worker stopped, not removed: the close of the stages they left open did not finish '
                      '(KeyboardInterrupt): it may have closed some or all of them before it stopped', receipt['error'])
        self.assertIn(f'and it may have set back the unapplied details of encounters with an update of their codes '
                      f'pending (context.rollback_reverted rows since {started}), which were not put back',
                      receipt['error'])
        self.assertEqual(scripts, [])

    def test_a_database_that_refuses_before_rollback_apps_close_says_the_close_was_not_started(self):  # R4
        receipts = self.tmp / 'receipts-db'
        seen = []

        def require_db():
            seen.append('require_db')
            if len(seen) == 2:  # the first is before undo_hazards; the second, right before the close
                raise install.InstallError(f'{install.DB_CONTAINER} is not running.')
        outcome, receipt, scripts, verbs = rollback_app_through_main(
            receipts, close_raises=AssertionError('the close must not start'), require_db=require_db)
        self.assertEqual(outcome, 1)
        self.assertEqual(receipt['error'], 'Web and worker stopped, not removed: the stages they left open could not be '
                                           'closed (cpt-studio-db is not running.): the close was not started, so '
                                           'nothing was closed or set back. Rerun --phase rollback-app once that is '
                                           'resolved.')
        self.assertNotIn('may have', receipt['error'])
        self.assertEqual((scripts, verbs), ([], ['stop', 'stop']))

    def test_rollback_app_interrupted_after_its_close_keeps_the_record_of_what_it_set_back(self):
        # R1's class past the put-back: the list states' put-back and the count also run after the close, and the
        # close's answer is the only record of each saved value - a Ctrl-C there keeps it in the receipt
        for where, kwargs in (('the list states', {'put_back': KeyboardInterrupt()}),
                              ('the count', {'count_raises': KeyboardInterrupt(),
                                             'put_back': {'encounters': 1, 'changed': {'e9': ['provider_failed']}}})):
            with self.subTest(where=where):
                receipts = self.tmp / f'receipts-after-{where[4:]}'.replace(' ', '-')
                outcome, receipt, scripts, verbs = rollback_app_through_main(receipts, close=reverted_close(),
                                                                             **kwargs)
                self.assertEqual(outcome, 1)
                self.assertEqual(receipt['details']['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])
                self.assertIn('Web and worker stopped, not removed:', receipt['error'])
                self.assertIn('(KeyboardInterrupt)', receipt['error'])
                self.assertIn('The close set the unapplied details of 1 encounter back to their context\'s values for '
                              'the earlier pair', receipt['error'])
                self.assertNotIn('REAPPLY_REVERTED', [name for name, _ in scripts])  # only way on: back
                self.assertEqual(verbs, ['stop', 'stop'])
        self.assertIn('after the list states of 1 encounter(s) were put back to what the older revision derives',
                      receipt['error'])

    def test_a_swap_interrupted_while_putting_back_keeps_its_record_and_says_so(self):
        try:
            message, details, asked = UndoneUndoTests.swap(self, reverted_close(hazards={'e3': ['participant']}),
                                                           reapply=KeyboardInterrupt())
        except KeyboardInterrupt:  # (raised from the test, the interrupt would stop the whole run: failed here instead)
            self.fail('the interrupt escaped the swap, and with it the record of what its close set back')
        self.assertIn('the new pair was left stopped and the previous pair parked', message)
        self.assertIn('(e1; context.rollback_reverted) may not have been put back (the put-back was interrupted '
                      '(KeyboardInterrupt))', message)
        self.assertEqual(details['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])
        self.assertIs(details['reapplied']['interrupted'], True)

    def test_an_s4_undo_interrupted_while_putting_back_names_the_encounters(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = reverted_close(hazards={'e3': ['participant']})
        world.reapply_answer = KeyboardInterrupt()
        details, error = run_app(world)
        self.assertIn('the new web keeps serving on 9151', str(error))
        self.assertIn('may not have been put back (the put-back was interrupted (KeyboardInterrupt))', str(error))
        self.assertEqual(error.details['stages_closed']['reverted'], REVERTED_CLOSE['reverted'])
        self.assertIs(error.details['reapplied']['interrupted'], True)

    def test_rollback_app_in_the_keep_layout_interrupted_while_putting_back_names_the_encounters(self):
        world = keep_world(self.tmp)
        world.close_answer = reverted_close(hazards={'e3': ['participant']})
        world.reapply_answer = KeyboardInterrupt()
        details, error = run_rollback_app(world)
        self.assertIn('so nothing more was done', str(error))
        self.assertIn('may not have been put back (the put-back was interrupted (KeyboardInterrupt))', str(error))
        self.assertIs(error.details['reapplied']['interrupted'], True)

    def test_a_switch_back_undo_interrupted_while_putting_back_stops_and_names_the_encounters(self):
        world = UndoneUndoTests.switched_in(self)
        world.close_answer = reverted_close()
        world.reapply_answer = KeyboardInterrupt()
        world.fail[('https', 9150)] = install.InstallError('it did not serve the previous revision')
        details, error = run_holding_the_key(world, install.phase_switch_back, switch_back_args(self.tmp))
        message = str(error)
        self.assertIn('the undo at B5 stopped too (KeyboardInterrupt)', message)
        self.assertIn('The unapplied details the close set back on 1 encounter (e1; context.rollback_reverted) may not '
                      'have been put back (the put-back was interrupted (KeyboardInterrupt))', message)
        self.assertIs(error.details['closes']['reapplied']['interrupted'], True)
        self.assertEqual(error.details['closes']['first']['reverted'], REVERTED_CLOSE['reverted'])
        reapply = world.events.index(('reapply', IMAGE))
        self.assertNotIn(('start', WORKER), world.events[reapply:])  # the interrupt still stops the undo


class CloseRaisedTests(TemporaryDirectoryTest):
    """Refutation 6b-r2 F4 (D247): a close that raised may have committed its revert first (CLOSE_STAGES commits, then
    reads every encounter); the undos that keep this revision's web serving carry the switch-back's clause naming the
    context.rollback_reverted rows since the close started."""

    def test_an_s4_undo_whose_close_raised_names_the_rows_it_may_have_set_back(self):  # the refuter's Q1c
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.fail[('close',)] = install.InstallError('Closing the stages failed (exit 1).')
        details, error = run_app(world)
        message = str(error)
        started = error.details['close_started_at']
        self.assertIn('the new web keeps serving on 9151', message)
        self.assertIn(f'The close may have set back the unapplied details of encounters with an update of their codes '
                      f'pending (context.rollback_reverted rows since {started}), which were not put back: ask those '
                      'members to check their details.', message)
        self.assertIsNotNone(install.utc_moment(started))
        self.assertEqual(world.reapplies, [])  # what it set back is not known, so nothing is asked

    def test_rollback_app_in_the_keep_layout_whose_close_raised_names_the_rows_it_may_have_set_back(self):
        world = keep_world(self.tmp)
        world.fail[('close',)] = install.InstallError('Closing the stages failed (exit 1).')
        details, error = run_rollback_app(world)
        started = error.details['close_started_at']
        self.assertIn('rollback-app in the S4 keep layout: Closing the stages failed (exit 1).', str(error))
        self.assertIn(f'The close was started and gave no answer: it may have set back the unapplied details of '
                      f'encounters with an update of their codes pending (context.rollback_reverted rows since '
                      f'{started}), which were not put back: ask those members to check their details.', str(error))
        self.assertNotIn('stages_closed', error.details)

    def test_rollback_app_in_the_keep_layout_whose_close_answered_names_no_such_rows(self):
        world = keep_world(self.tmp)
        world.close_answer = reverted_close(hazards={'e3': ['participant']})
        details, error = run_rollback_app(world)
        self.assertNotIn('The close was started and gave no answer', str(error))
        self.assertIn('were put back (context.rollback_reapplied)', str(error))

    def test_a_swap_whose_close_raised_names_the_rows_it_may_have_set_back(self):
        old = {role: {'Id': f'old-{role}', 'Image': 'sha256:' + 'd' * 64, 'Created': '2026-11-01T12:00:00.000000Z',
                      'State': {'Running': True},
                      'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role,
                                            install.REVISION_LABEL: 'b' * 40}}} for role in ('web', 'worker')}
        live = {install.SERVICES[role]: dict(container) for role, container in old.items()}

        def fake_docker(*args, **kwargs):
            if args[0] == 'rename':
                live[args[2]] = live.pop(args[1])
            elif args[0] == 'run':
                name = args[args.index('--name') + 1]
                role = 'web' if name == install.SERVICES['web'] else 'worker'
                live[name] = {**old[role], 'Id': f'new-{role}', 'Image': IMAGE}
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def wait(role, revision, image_id, **kwargs):
            if role == 'worker':
                raise install.InstallError('cpt-studio-worker did not become ready')
            return {'id': 'new-web'}
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(name)), \
                mock.patch.object(install, 'docker', fake_docker), mock.patch.object(install, 'wait_service', wait), \
                mock.patch.object(install, 'stage_kinds_of', return_value=list(install.COMMON_STAGE_KINDS)), \
                mock.patch.object(install, 'close_undone_stages',
                                  side_effect=install.InstallError('the database did not answer')), \
                self.assertRaises(install.InstallError) as caught:
            install.replace_services(ctx, IMAGE, b'', 'disabled', '', {'astra': 'disabled', 'fable': 'disabled'})
        message, started = str(caught.exception), caught.exception.details['close_started_at']
        self.assertIn('could not then be closed (the database did not answer)', message)
        self.assertIn(f'The close was started and gave no answer: it may have set back the unapplied details of '
                      f'encounters with an update of their codes pending (context.rollback_reverted rows since '
                      f'{started}), which were not put back', message)


class HalfwayKeepsTheRevertTests(TemporaryDirectoryTest):
    """Refutation 6b-r2 F3 (D247): an undo left half way - the earlier web may serve - never puts the saves back (its
    details panel shows the context's values while its save compares with Encounter.user_values: 9.4 [R:legacy-L7]).
    Each half-way path whose close answers REVERTED_CLOSE asserts that no REAPPLY_REVERTED runs (mutants MX1 and MX5)."""

    def test_a_switch_back_left_half_way_with_the_vhost_naming_the_previous_web_puts_nothing_back(self):  # MX1
        world = switched_back_world(self.tmp)
        world.close_answer = reverted_close()
        world.fail[('https', 9150)] = install.InstallError('it did not serve the previous revision')
        world.fail[('vhost', 'replace', 9151)] = install.InstallError('Root helper refused: synthetic')  # no restore
        details, error = run_switch_back(world)
        self.assertIn('quillmd-cpt still names the previous revision\'s web (cpt-studio-web-next, port 9150)',
                      str(error))
        self.assertIn('both webs were left running', str(error))
        self.assertEqual(len(world.closes), 1)  # B4's close ran and set e1 back
        self.assertEqual(world.reapplies, [])
        self.assertNotIn('reapplied', error.details['closes'])
        # F1's fallback: the message names the encounters whose saves were set back, as not put back
        self.assertIn('The unapplied details the close set back on 1 encounter (e1; context.rollback_reverted, each '
                      'field\'s saved and restored value in closes.first.reverted) were not put back (an undo left half '
                      'way puts nothing back while the earlier web may serve): whichever web serves next, ask each of '
                      'those members to save the change again there.', str(error))
        self.assertNotIn('handed', error.details['interpretation'])  # the earlier web may serve: B4's note stands
        self.assertIn('ask each member to save the change again on the earlier web',
                      error.details['interpretation']['note'])

    def test_a_switch_back_left_half_way_with_nginx_not_proven_puts_nothing_back(self):
        world = switched_back_world(self.tmp, cls=ReloadActsThenRaises, raising=(1, 2, 3))
        world.close_answer = reverted_close()
        details, error = run_switch_back(world)
        self.assertIn('nginx may still route to the previous revision\'s web', str(error))
        self.assertEqual(world.reapplies, [])
        self.assertNotIn('reapplied', error.details['closes'])
        self.assertIn('(e1; context.rollback_reverted, each field\'s saved and restored value in closes.first.reverted) '
                      'were not put back (an undo left half way', str(error))

    def test_an_s4_switch_back_left_half_way_with_nginx_not_proven_puts_nothing_back(self):  # MX5
        world = ReloadActsThenRaises(self.tmp, raising=(2, 3, 4))
        world.unhealthy.add(WORKER)
        world.close_answer = reverted_close()
        details, error = run_app(world)
        self.assertIn('nginx may route to either web', str(error))
        self.assertEqual(world.reapplies, [])
        self.assertNotIn('reapplied', error.details)
        self.assertIn('(e1; context.rollback_reverted, each field\'s saved and restored value in stages_closed.reverted) '
                      'were not put back (an undo left half way puts nothing back while the earlier web may serve)',
                      str(error))

    def test_control_the_same_s4_switch_back_kept_on_the_new_web_puts_the_saves_back(self):
        world = ReloadActsThenRaises(self.tmp, raising=(2,))  # proven back on the new web: it keeps serving
        world.unhealthy.add(WORKER)
        world.close_answer = reverted_close()
        details, error = run_app(world)
        self.assertIn('the new web keeps serving on 9151', str(error))
        self.assertEqual(world.reapplies, [REVERTED_CLOSE['reverted']])


class PutBackOnTheDatabaseTests(V2Rows):
    """D247 DQ1 (option (a)) and F2 on real rows: the real CLOSE_STAGES sets the save back, the real REAPPLY_REVERTED
    puts it back and queues again the first reading stage the update owes - once, for the member who saved, under the
    save's own key shape - when the serving worker runs that stage; otherwise the update reads paused and the sentence
    says so. Each sentence is checked against what the rows then show."""

    def reapply(self, closes):
        with mock.patch.object(install, 'app_script', in_this_image):
            return install.reapply_reverted(IMAGE, b'', closes)

    def saved(self, tag, *, stage=True, member=True):
        """A legacy encounter whose member saved setting=office - an update pending before its analyze - with the
        'context.changed' row the save writes (naming the interpret stage it queued, when ``stage``)."""
        from studio import models
        encounter = self.legacy(tag, user_values={'setting': 'office', 'service_date': '2026-11-10'},
                                context_values={'service_date': '2026-11-10'})
        queued = self.job(encounter, 'interpret', models.Job.QUEUED) if stage else None
        if member:
            models.AuditEvent.objects.create(
                workspace_id=encounter.workspace_id, encounter=encounter, actor_id=encounter.created_by_id,
                actor_kind='human', event='context.changed',
                data={'fields': ['setting'], **({'reading': str(queued.pk)} if queued is not None else {})})
        return encounter

    def marker(self, encounter):
        from studio import models
        return models.AuditEvent.objects.filter(encounter=encounter, event='context.rollback_reverted').latest(
            'created_at')

    def test_the_put_back_queues_the_first_reading_stage_the_update_owes_once_for_the_member_who_saved(self):
        from studio import jobs, models, progress, review
        encounter = self.saved('requeue')
        closed = self.close(revert=True)
        self.assertEqual(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED).count(), 0)
        done = self.reapply([closed])
        key = f'{jobs._interpret_key(encounter.current_revision)}:{jobs.AFTER_SAVE}:{self.marker(encounter).pk}'
        stage = models.Job.objects.get(idempotency_key=key)
        self.assertEqual((stage.kind, stage.state, stage.requested_by_id, stage.encounter_id, stage.revision_id),
                         ('interpret', models.Job.QUEUED, encounter.created_by_id, encounter.pk,
                          encounter.current_revision_id))
        self.assertEqual(done['requeued'], {str(encounter.pk): {'kind': 'interpret', 'job': str(stage.pk)}})
        self.assertIn('the first reading stage the update of 1 of them owes was queued again, once each (interpret 1;',
                      done['sentence'])
        back = models.Encounter.objects.get(pk=encounter.pk)
        self.assertTrue(review.update_pending(back))
        self.assertEqual(review._state_and_run(back), ('processing', None))  # a target job serves the update
        shown = progress.encounter_progress(back)
        self.assertEqual((shown['phase'], shown['busy'], shown['error']), ('updating', True, None))
        again = self.reapply([closed])  # at most once: the put-back's compare-and-set leaves it as it stands
        self.assertEqual((again['reapplied'], again['requeued']), ({}, {}))
        self.assertEqual(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED).count(), 1)
        self.assertIn(stage.kind, jobs.STAGES)  # the serving worker runs that stage...
        from django.test import override_settings
        with override_settings(GEMINI_MODE='disabled'):  # ...through its own doors (here the interpreter is disabled)
            jobs.run_job(jobs.claim_next())
        self.assertEqual(models.Job.objects.get(pk=stage.pk).state, models.Job.CANCELLED)  # paused, sending nothing
        back = models.Encounter.objects.get(pk=encounter.pk)
        self.assertEqual(review._state_and_run(back), ('stopped', None))
        self.assertTrue(review.can_resume(back))  # unlike the stage the close closed, it leaves a way forward
        self.assertEqual(progress.encounter_progress(back)['error']['action'], 'resume')

    def test_a_reading_stage_still_queued_is_coalesced_and_nothing_more_is_queued(self):
        from studio import models
        encounter = self.saved('coalesced')
        closed = self.close(revert=True)
        waiting = self.job(encounter, 'interpret', models.Job.QUEUED, tag='-after-the-close')
        due = models.Job.objects.get(pk=waiting.pk).deadline_at
        done = self.reapply([closed])
        self.assertEqual(done['coalesced'], {str(encounter.pk): {'kind': 'interpret', 'job': str(waiting.pk)}})
        self.assertEqual(done['requeued'], {})
        self.assertEqual(list(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED)), [waiting])
        self.assertGreater(models.Job.objects.get(pk=waiting.pk).deadline_at, due)  # its deadline renewed (2.3)
        # refutation w7r 6b-r1 R3: it waits for a worker only until that deadline, and the sentence says so
        self.assertIn('1 of them had a reading stage still queued (interpret 1), its deadline renewed: claimed by a '
                      'worker of this revision within 120 minutes of the put-back, it reads the details put back; claimed '
                      'after that, it expires without starting, and the update then reads stopped, with Resume',
                      done['sentence'])

    def test_a_reading_that_failed_before_queues_nothing_and_keeps_showing_that_failure(self):
        from studio import models, review
        encounter = self.saved('failed', stage=False)
        self.job(encounter, 'interpret', models.Job.FAILED)  # the reading stage that failed, then its run
        from studio import interpretation  # the reading path's runs (jobs.retry_target: AMENDMENT-2 section 9)
        self.made_run(encounter, provider=interpretation.PROVIDER_V3, purpose='interpretation', state='failed',
                      http_status=500, request='f', adapter_version=interpretation.ADAPTER_VERSION_V3)
        models.ProviderRun.objects.filter(encounter=encounter, provider=interpretation.PROVIDER_V3).update(
            scope={'effect': 'failed'})
        before = review._state_and_run(models.Encounter.objects.get(pk=encounter.pk))
        closed = self.close(revert=True)
        done = self.reapply([closed])
        self.assertEqual(done['not_requeued'], {str(encounter.pk): 'reading_failed'})
        self.assertFalse(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED).exists())
        self.assertIn('1 of them had a reading that failed before the close, so nothing was queued for it, as a save '
                      'queues nothing then: each shows that failure as it did before the close', done['sentence'])
        self.assertEqual(review._state_and_run(models.Encounter.objects.get(pk=encounter.pk)), before)

    def test_where_the_serving_worker_runs_no_such_stage_the_update_reads_paused_as_the_sentence_says(self):
        from studio import jobs, models, progress, review
        encounter = self.saved('no-stage')
        closed = self.close(revert=True)
        with mock.patch.dict(jobs.STAGES):
            jobs.STAGES.pop('interpret')
            done = self.reapply([closed])
        self.assertEqual(done['not_requeued'], {str(encounter.pk): 'no_stage'})
        self.assertFalse(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED).exists())
        self.assertIn('such an update reads paused, with nothing to resume', done['sentence'])
        back = models.Encounter.objects.get(pk=encounter.pk)
        shown = progress.encounter_progress(back)
        self.assertEqual((shown['phase'], shown['error']['action']), ('paused', 'none'))  # what the sentence says
        self.assertFalse(review.can_resume(back))

    def test_with_no_members_save_found_nothing_is_queued_and_the_sentence_says_how_the_update_moves(self):
        from studio import jobs, models
        encounter = self.saved('no-save', member=False)
        closed = self.close(revert=True)
        done = self.reapply([closed])
        self.assertEqual(done['not_requeued'], {str(encounter.pk): 'no_save'})
        self.assertIn('such an update reads paused, with nothing to resume, until its member changes a detail again, '
                      'which queues its reading', done['sentence'])
        member = models.User.objects.get(pk=encounter.created_by_id)
        jobs.change_context(models.Encounter.objects.get(pk=encounter.pk), member, {'setting': 'asc'})
        self.assertTrue(models.Job.objects.filter(encounter=encounter, kind='interpret',
                                                  state=models.Job.QUEUED).exists())  # what the sentence says

    def test_a_close_for_a_next_worker_that_runs_appraise_says_the_update_reads_paused_and_that_is_so(self):
        # the refuter's Q4: an earlier design v2 pair (its worker runs appraise: nothing is reverted, nothing put back);
        # this tree's review and jobs stand in for that pair's (the same 5b/5d logic)
        from django.utils import timezone
        from studio import jobs, models, progress, review
        encounter = self.saved('next-runs-appraise')
        kinds = list(install.COMMON_STAGE_KINDS) + ['interpret', 'appraise']
        closed = run_in_image(install.CLOSE_STAGES, {
            'since': (timezone.now() - dt.timedelta(hours=1)).isoformat(), 'note': 'Closed by the installer: synthetic.',
            'kinds': kinds, 'revert': install.APPRAISE_KIND not in set(kinds),
            'reading_kinds': list(install.READING_STAGE_KINDS)})
        self.assertEqual((closed.get('update_revert'), closed.get('reverted')), (False, None))
        self.assertEqual(closed['update_reads'], {str(encounter.pk): {'phase': 'paused', 'action': 'none'}})
        note = install.with_update_note({'note': 'counted'}, [closed])['note']
        self.assertIn('nothing queues it again - the earlier revision runs both, but offers no retry and no resume of a '
                      'stage the installer closed', note)
        self.assertIn('1 reads paused, with nothing to resume or retry, until its member saves a change of a detail, '
                      'which queues the update again', note)
        back = models.Encounter.objects.get(pk=encounter.pk)
        shown = progress.encounter_progress(back)
        self.assertEqual((shown['phase'], shown['error']['action']), ('paused', 'none'))  # paused, nothing to resume
        member = models.User.objects.get(pk=encounter.created_by_id)
        with self.assertRaises(jobs.Refused):
            jobs.retry_reading(back, member)  # no retry is offered...
        self.assertIsNone(jobs.resume(models.Encounter.objects.get(pk=encounter.pk), member))  # ...nor a resume
        self.assertFalse(review.can_resume(models.Encounter.objects.get(pk=encounter.pk)))
        jobs.change_context(models.Encounter.objects.get(pk=encounter.pk), member, {'setting': 'asc'})
        self.assertTrue(models.Job.objects.filter(encounter=encounter, kind='interpret',
                                                  state=models.Job.QUEUED).exists())  # ...and a change queues it


class UpdateReadsOnTheDatabaseTests(V2Rows):
    """Refutation w7r 6b-r1 R2 (D247 F2) on real rows: the real CLOSE_STAGES for an earlier design v2 pair (its worker
    runs appraise: nothing reverted, nothing put back) reads what each pending update reads after it, as this tree's page
    reads it ('update_reads'), and the note words each by it - checked against what the page then shows and what each
    action does. This tree's review, progress and jobs stand in for that pair's, as the refuter's P5 does."""

    def v2_pair_close(self):
        from django.utils import timezone
        kinds = list(install.COMMON_STAGE_KINDS) + ['interpret', 'appraise']
        return run_in_image(install.CLOSE_STAGES, {
            'since': (timezone.now() - dt.timedelta(hours=1)).isoformat(), 'note': 'Closed by the installer: synthetic.',
            'kinds': kinds, 'revert': install.APPRAISE_KIND not in set(kinds),
            'reading_kinds': list(install.READING_STAGE_KINDS)})

    def case_a(self, tag, kind):
        """A design v2 encounter's update of case A (2.2: its save made a new context; the assessment is still on the
        earlier one), its ``kind`` stage queued."""
        from django.utils import timezone
        from studio import models
        encounter = models.Encounter.objects.get(pk=self.v2(tag).pk)
        assessment = encounter.current_assessment
        later = self.context(encounter, version=encounter.current_context.version,
                             inventory=encounter.current_context.event_inventory, user_values={'setting': 'asc'})
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=later, user_values={'setting': 'asc'})
        models.Job.objects.create(
            encounter=encounter, revision=encounter.current_revision, kind=kind, state=models.Job.QUEUED, context=later,
            provider_run=assessment.provider_run if kind == 'assess' else None,
            idempotency_key=f'{kind}:{later.pk}:{assessment.provider_run_id}',
            deadline_at=timezone.now() + dt.timedelta(minutes=9), requested_by_id=encounter.created_by_id)
        return models.Encounter.objects.get(pk=encounter.pk)

    def test_a_closed_assessment_reads_failed_and_try_updating_again_queues_it_as_the_note_says(self):  # P5
        from studio import jobs, models, progress
        encounter = self.case_a('reads-assess', 'assess')
        closed = self.v2_pair_close()
        self.assertEqual(closed['update_pending'], {str(encounter.pk): ['assessment_off_context']})
        self.assertEqual(closed['update_reads'], {str(encounter.pk): {'phase': 'failed', 'action': 'retry_update'}})
        note = install.with_update_note({'note': 'counted'}, [closed])['note']
        self.assertIn('1 reads failed, and its member\'s "Try updating again" queues the failed stage again', note)
        self.assertNotIn('with nothing to resume', note)
        back = models.Encounter.objects.get(pk=encounter.pk)
        shown = progress.encounter_progress(back)
        self.assertEqual((shown['phase'], shown['error']['action']), ('failed', 'retry_update'))  # what the note says
        again = jobs.retry_update(back, models.User.objects.get(pk=back.created_by_id))
        self.assertEqual((again.kind, again.state), ('assess', models.Job.QUEUED))  # ...and it does what it says

    def test_a_closed_document_review_reads_paused_with_nothing_to_resume_or_retry_as_the_note_says(self):  # P5b
        from studio import jobs, models, progress, review
        encounter = self.case_a('reads-predict', 'predict')
        closed = self.v2_pair_close()
        self.assertEqual(closed['update_reads'], {str(encounter.pk): {'phase': 'paused', 'action': 'none'}})
        note = install.with_update_note({'note': 'counted'}, [closed])['note']
        self.assertIn('1 reads paused, with nothing to resume or retry, until its member saves a change of a detail, '
                      'which queues the update again', note)
        self.assertNotIn('Try updating again', note)
        back = models.Encounter.objects.get(pk=encounter.pk)
        self.assertEqual(progress.encounter_progress(back)['phase'], 'paused')
        member = models.User.objects.get(pk=back.created_by_id)
        with self.assertRaises(jobs.Refused):
            jobs.retry_update(back, member)  # nothing to retry...
        self.assertIsNone(jobs.resume(models.Encounter.objects.get(pk=encounter.pk), member))  # ...nor to resume
        self.assertFalse(review.can_resume(models.Encounter.objects.get(pk=encounter.pk)))

    def test_pending_updates_of_each_kind_are_each_worded_by_what_they_read(self):
        from studio import jobs, models, progress
        assess = self.case_a('mixed-assess', 'assess')
        predict = self.case_a('mixed-predict', 'predict')
        saved = self.legacy('mixed-analyze', user_values={'setting': 'office', 'service_date': '2026-11-10'},
                            context_values={'service_date': '2026-11-10'})
        self.job(saved, 'analyze', models.Job.QUEUED)  # case B, its analysis closed: failed, retried by its member
        closed = self.v2_pair_close()
        self.assertEqual(closed['update_reads'], {str(assess.pk): {'phase': 'failed', 'action': 'retry_update'},
                                                  str(predict.pk): {'phase': 'paused', 'action': 'none'},
                                                  str(saved.pk): {'phase': 'failed', 'action': 'retry_update'}})
        note = install.with_update_note({'note': 'counted'}, [closed])['note']
        self.assertIn('3 encounters read an update of their codes pending (update_pending)', note)
        self.assertIn('2 read failed, and its member\'s "Try updating again" queues the failed stage again', note)
        self.assertIn('1 reads paused, with nothing to resume or retry', note)
        for encounter, (phase, action) in ((assess, ('failed', 'retry_update')), (predict, ('paused', 'none')),
                                           (saved, ('failed', 'retry_update'))):
            shown = progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))
            self.assertEqual((shown['phase'], shown['error']['action']), (phase, action))
        again = jobs.retry_update(models.Encounter.objects.get(pk=saved.pk),
                                  models.User.objects.get(pk=saved.created_by_id))
        self.assertEqual(again.kind, 'analyze')

    def test_a_close_for_a_next_worker_without_appraise_reads_nothing_of_the_page(self):
        # the earlier image has no update: its own clause applies, and nothing of this image's page is read for it
        encounter = self.case_a('reads-none', 'assess')
        closed = self.close(revert=True)
        self.assertEqual(closed['update_pending'], {str(encounter.pk): ['assessment_off_context']})
        self.assertNotIn('update_reads', closed)


class RequeueDeadlineOnTheDatabaseTests(V2Rows):
    """Refutation w7r 6b-r1 R3 on real rows: the stage the put-back queues again waits for a worker only until its queue
    deadline; claimed after it, it expires before it starts and the update reads stopped, with Resume - which the
    put-back's sentence says, never that the worker simply runs it."""

    def test_the_installers_deadline_is_this_images_queue_deadline(self):
        from studio import jobs
        self.assertEqual(dt.timedelta(minutes=install.QUEUE_DEADLINE_MINUTES), jobs.QUEUE_DEADLINE)

    def test_a_stage_queued_again_and_not_claimed_by_its_deadline_reads_as_the_sentence_says(self):  # the refuter's P3
        from django.utils import timezone
        from studio import jobs, models, progress, review
        encounter = self.legacy('deadline', user_values={'setting': 'office', 'service_date': '2026-11-10'},
                                context_values={'service_date': '2026-11-10'})
        stage = self.job(encounter, 'interpret', models.Job.QUEUED)
        models.AuditEvent.objects.create(workspace_id=encounter.workspace_id, encounter=encounter,
                                         actor_id=encounter.created_by_id, actor_kind='human', event='context.changed',
                                         data={'fields': ['setting'], 'reading': str(stage.pk)})
        closed = self.close(revert=True)
        with mock.patch.object(install, 'app_script', in_this_image):
            done = install.reapply_reverted(IMAGE, b'', [closed])
        self.assertIn('while it waits for a worker of this revision the update reads updating; claimed within the '
                      'queue deadline (120 minutes from the put-back), it runs, its doors sending the save\'s request at '
                      'most once; claimed after it, it expires without starting, and the update then reads stopped, with '
                      'Resume', done['sentence'])
        shown = progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))
        self.assertEqual((shown['phase'], shown['busy']), ('updating', True))  # while it waits, as said
        self.assertNotIn('runs it once it runs', done['sentence'])
        queued = models.Job.objects.get(pk=done['requeued'][str(encounter.pk)]['job'])
        self.assertLessEqual(queued.deadline_at, timezone.now() + jobs.QUEUE_DEADLINE)
        later = timezone.now() + jobs.QUEUE_DEADLINE + dt.timedelta(minutes=1)
        with mock.patch.object(jobs.timezone, 'now', return_value=later):
            claimed = jobs.claim_next()
            jobs.run_job(claimed)
        claimed.refresh_from_db()
        self.assertEqual((claimed.pk, claimed.state, claimed.started_at), (queued.pk, models.Job.CANCELLED, None))
        back = models.Encounter.objects.get(pk=encounter.pk)
        self.assertEqual(review._state_and_run(back), ('stopped', None))  # what the sentence says: stopped...
        self.assertTrue(review.can_resume(back))
        self.assertEqual(progress.encounter_progress(back)['error']['action'], 'resume')  # ...with Resume


class RollbackAppOnTheDatabaseTests(V2Rows):
    """The refuter's Q2 on real rows: rollback-app's REAL close sets the pending save back, a record named after it stops
    the phase with "Start them again" - and the put-back runs first, so the restart keeps the member's save (its update
    pending, its reading queued again), and the rerun's close names the revert again."""

    def test_the_restart_after_a_record_named_after_the_close_keeps_the_members_save(self):
        from studio import jobs, models, review
        encounter = self.legacy('q2', user_values={'setting': 'office', 'service_date': '2026-11-10'},
                                context_values={'service_date': '2026-11-10'})
        stage = self.job(encounter, 'interpret', models.Job.QUEUED)
        models.AuditEvent.objects.create(workspace_id=encounter.workspace_id, encounter=encounter,
                                         actor_id=encounter.created_by_id, actor_kind='human', event='context.changed',
                                         data={'fields': ['setting'], 'reading': str(stage.pk)})
        real_close = install.close_undone_stages

        def close_naming_a_record(*args, **kwargs):  # the real close, then a record named on another encounter
            with mock.patch.object(install, 'app_script', in_this_image):
                answer = real_close(*args, **kwargs)
            return {**answer, 'hazards': {**answer['hazards'], 'synthetic-other': ['outcome']}}
        live = owned_pair()
        names = {install.SERVICES[role]: role for role in ('web', 'worker')}
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(names.get(name))), \
                mock.patch.object(install, 'docker', return_value=SimpleNamespace(returncode=0, stdout=b'',
                                                                                  stderr=b'')), \
                mock.patch.object(install, 'read_protected_env', return_value=b''), \
                mock.patch.object(install, 'require_db'), mock.patch.object(install, 'undo_hazards', return_value={}), \
                mock.patch.object(install, 'close_undone_stages', side_effect=close_naming_a_record), \
                mock.patch.object(install, 'app_script', in_this_image), \
                tempfile.TemporaryDirectory() as receipts, self.assertRaises(install.InstallError) as caught:
            install.phase_rollback_app(install.Context(SimpleNamespace(phase='rollback-app', revision=REVISION),
                                                       Path(receipts)))
        self.assertIn('Start them again', str(caught.exception))
        self.assertEqual(caught.exception.details['stages_closed']['reverted'],
                         {str(encounter.pk): {'setting': {'saved': 'office', 'restored': None}}})
        back = models.Encounter.objects.get(pk=encounter.pk)
        self.assertEqual(back.user_values, {'setting': 'office', 'service_date': '2026-11-10'})  # the save kept
        self.assertTrue(review.update_pending(back))
        self.assertFalse(review.fresh(back))  # the earlier codes are not current: neither approvable nor exportable
        self.assertEqual(models.Job.objects.get(pk=stage.pk).state, models.Job.FAILED)  # the close closed the save's
        self.assertTrue(models.Job.objects.filter(  # ... and the put-back queued it again (D247 DQ1)
            encounter=encounter, kind='interpret', state=models.Job.QUEUED, requested_by_id=encounter.created_by_id,
            idempotency_key__startswith=f'{jobs._interpret_key(back.current_revision)}:{jobs.AFTER_SAVE}:').exists())
        rerun = self.close(revert=True)  # the operator clears the record and reruns rollback-app: its close
        self.assertEqual(rerun['reverted'], {str(encounter.pk): {'setting': {'saved': 'office', 'restored': None}}})
        self.assertIn('ask each member to save the change again on the earlier web',
                      install.with_update_note({'note': 'counted'}, [rerun])['note'])


# --- refutation 6b-r1 P1: the walk's routing checks on the operator view the real serializer and report build -------

WALK = Path(__file__).resolve().parent / 'verify_browser.cjs'
WALK_ROUTING = """
const vb = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const { expected, view } = JSON.parse(input);
  process.stdout.write(JSON.stringify(vb.checkRouting(expected, view).map(item => [item.id, item.status, item.reason])));
});
"""
EXPECTED_ROUTING = {'families': {'gi.colonoscopy': {
    'presence': 'required', 'status_in': ['performed'],
    'facts': {'extent': {'value_contains_any': ['cecum']}, 'target': {'value_contains_any': ['cecum']}},
    'informational': {'facts': {'em_basis': {'value_contains_any': ['time']}}}}}}


def walk_routing(expected, view):
    """[[id, status, reason]] of ops/verify_browser.cjs checkRouting over ``view`` (node runs the file)."""
    import shutil
    import subprocess
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the walk checks need it')
    done = subprocess.run([node, '-e', WALK_ROUTING, str(WALK)], input=json.dumps({'expected': expected, 'view': view},
                                                                                  default=str),
                          capture_output=True, text=True, timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-3000:])
    return json.loads(done.stdout)


def labelled_as_requested(routing, result):
    """The routing serializers._routing_json serves, with request R-SER applied (6b-3 NOTES: a ROUTING_VERSION_V2 run is
    labelled derived and names its inventory, exactly as the ROUTING_VERSION branch labels it); unchanged once served so."""
    from studio import interpretation
    if routing.get('version') == interpretation.ROUTING_VERSION_V2 and routing.get('derived') is not True:
        routing = {**routing, 'derived': True, 'derived_from': 'the event inventory',
                   'inventory': result.get('inventory'), 'inventory_sha256': result.get('inventory_sha256')}
    return routing


class WalkV2StandInOnRealRowsTests(V2Rows):
    """The operator view of a v2 encounter as the REAL serializers._routing_json and report.interpretation_section_v2
    build it, judged by the walk's own checkRouting: the stand-in and each status judged, no per-fact expectation failed
    (refutation 6b-r1 P1: every one failed, and the walk's own v2 tests passed only on a hand-drawn sample)."""

    def operator_view(self):
        from studio import models, serializers
        from studio.interpretation import report
        encounter = self.extracted(self.encounter('v2-walk'))
        made = self.inventory(encounter)
        context = self.context(encounter, version='gemini-context@2', inventory=made)
        # engine/derive.routing_stand_in's shape: one finding per family an act names, nothing a reading carries
        result = {'version': 'gemini-routing@2', 'document_kind': '', 'findings': [
            {'family': 'gi.colonoscopy', 'status': 'performed', 'mentions': [], 'facts': [], 'missing': []}],
            'inventory': str(made.pk), 'inventory_sha256': made.sha256}
        routing = models.RoutingRun.objects.create(revision=encounter.current_revision, version=result['version'],
                                                   result=result, sha256='0' * 64)
        assessment = models.Assessment.objects.create(
            encounter=encounter, revision=encounter.current_revision, context=context, routing=routing,
            profiles_version='synthetic@1', engine_version='cpt-studio-events@2', sha256='1' * 64,
            provider_run=self.made_run(encounter), event_inventory=made)
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context, current_assessment=assessment)
        served = serializers._routing_json(models.Encounter.objects.get(pk=encounter.pk))
        section = json.loads(json.dumps(report.interpretation_section_v2(assessment), default=str))
        return served, section, result

    def test_the_walk_judges_the_real_v2_operator_view_and_fails_no_fact_on_it(self):
        served, section, result = self.operator_view()
        view = {'routing': labelled_as_requested(served, result), 'assessment': {'interpretation': section}}
        judged = walk_routing(EXPECTED_ROUTING, view)
        self.assertEqual([(item_id, status) for item_id, status, _ in judged], [
            ('routing.stand_in', 'pass'), ('routing.gi.colonoscopy.status', 'pass'),
            ('routing.gi.colonoscopy.fact.extent', 'skipped'), ('routing.gi.colonoscopy.fact.target', 'skipped'),
            ('routing.gi.colonoscopy.info.fact.em_basis', 'skipped')])
        self.assertTrue(all('not judged on a design v2 stand-in' in reason for _, status, reason in judged
                            if status == 'skipped'))
        # as served now: until request R-SER lands the stand-in fails on its label alone; no fact fails either way
        as_served = walk_routing(EXPECTED_ROUTING, {'routing': served, 'assessment': {'interpretation': section}})
        failing = [(item_id, reason) for item_id, status, reason in as_served if status == 'fail']
        if served.get('derived') is True:
            self.assertEqual(failing, [])
        else:
            self.assertEqual([item_id for item_id, _ in failing], ['routing.stand_in'])
            self.assertIn('it is not labelled derived; it names no event inventory', failing[0][1])


if __name__ == '__main__':
    unittest.main()
