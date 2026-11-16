"""Unit tests for ops/rollback_check.py, the D15 rollback runtime test (design/FINAL.md 12.3; design/ADJUDICATION.md
P-1): the comparison it judges by, and the refusals it makes before anything runs. No Docker or network: the one-shot
transport is replaced where a test reaches it. AMENDMENT-2 8.5 [R:replay-R6]: the record kinds' SQL also runs on a
disposable PostgreSQL the Fable candidate's rows fill, when one is configured the way CI configures it
(test_install_harness2's DatabaseTest); without one those tests are skipped, never passed.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v
"""
import base64
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rollback_check as rc  # noqa: E402
from test_install_harness2 import module_constants  # noqa: E402
from test_install_interpreter import FableRows  # noqa: E402  (helpers only: no test of its own)

APP_ROOT = Path(__file__).resolve().parents[1]


def tearDownModule():
    harness2 = sys.modules.get('test_install_harness2')
    if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
        connection = harness2._DATABASE.pop('connection')
        connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)


def labels():
    """studio/interpretation/__init__.py's labels, loaded from its file alone (it imports nothing: its docstring)."""
    spec = importlib.util.spec_from_file_location('cpt_rollback_check_labels',
                                                  APP_ROOT / 'studio' / 'interpretation' / '__init__.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def code(pk, status, actions=()):
    return {'id': pk, 'code': '43239', 'status': status, 'allowed_actions': list(actions)}


def customer(state='ready', codes=(), **offers):
    payload = {'state': state, 'codes': list(codes), 'readiness': {'draft': True, 'approved': False},
               'recheck': {'available': False, 'can_request': False}, 'progress': {'can_resume': False, 'can_stop': False}}
    for path, value in offers.items():
        group, flag = path.split('__')
        payload[group][flag] = value
    return payload


class HeldMove(unittest.TestCase):
    def test_moves(self):
        ranks = rc.PROPOSAL_HELD
        self.assertEqual(rc.held_move(ranks, 'ready', 'ready'), 'same')
        self.assertEqual(rc.held_move(ranks, 'ready', 'needs_detail'), 'toward_held')
        self.assertEqual(rc.held_move(ranks, 'needs_detail', 'excluded'), 'toward_held')
        self.assertEqual(rc.held_move(ranks, 'approved', 'ready'), 'toward_held')  # an approval not carried waits again
        self.assertEqual(rc.held_move(ranks, 'needs_detail', 'ready'), 'toward_release')
        self.assertEqual(rc.held_move(ranks, 'excluded', 'needs_detail'), 'toward_release')
        self.assertEqual(rc.held_move(ranks, 'ready', 'readyish'), 'unknown')
        self.assertEqual(rc.held_move(ranks, None, 'ready'), 'unknown')

    def test_states(self):
        ranks = rc.STORED_STATE_HELD
        self.assertEqual(rc.held_move(ranks, 'ready_for_review', 'needs_clarification'), 'toward_held')
        self.assertEqual(rc.held_move(ranks, 'needs_clarification', 'processing_failed'), 'toward_held')
        self.assertEqual(rc.held_move(ranks, 'processing_failed', 'provider_not_run'), 'held_to_held')
        self.assertEqual(rc.held_move(ranks, 'reviewed', 'no_codes'), 'lateral')  # another meaning: never accepted
        self.assertEqual(rc.held_move(ranks, 'needs_clarification', 'reviewed'), 'toward_release')
        self.assertNotIn('lateral', rc.ACCEPTED_MOVES)
        self.assertNotIn('unknown', rc.ACCEPTED_MOVES)


class CompareRows(unittest.TestCase):
    def test_equal_and_more_held_pass(self):
        before = [code('p1', 'ready', ['approve', 'reject']), code('p2', 'needs_detail', ['reject'])]
        self.assertEqual(rc.compare_rows(before, before, rc.PROPOSAL_HELD, where='x'), [])
        after = [code('p1', 'needs_detail', ['reject']), code('p2', 'excluded', [])]
        self.assertEqual(rc.compare_rows(before, after, rc.PROPOSAL_HELD, where='x'), [])

    def test_ready_where_the_candidate_was_not(self):
        found = rc.compare_rows([code('p1', 'needs_detail')], [code('p1', 'ready')], rc.PROPOSAL_HELD, where='x')
        self.assertEqual([f['finding'] for f in found], ['toward_release'])
        self.assertEqual((found[0]['before'], found[0]['after'], found[0]['proposal']), ('needs_detail', 'ready', 'p1'))

    def test_an_action_the_candidate_did_not_allow(self):
        found = rc.compare_rows([code('p1', 'needs_detail', ['reject'])],
                                [code('p1', 'needs_detail', ['approve', 'reject'])], rc.PROPOSAL_HELD, where='x')
        self.assertEqual([(f['finding'], f['actions']) for f in found], [('action_not_allowed_before', ['approve'])])

    def test_rows_on_one_side_only(self):
        found = rc.compare_rows([code('p1', 'ready')], [code('p2', 'ready', ['approve'])], rc.PROPOSAL_HELD, where='x')
        self.assertEqual(sorted(f['finding'] for f in found), ['listed_only_after', 'not_listed_after'])

    def test_an_unknown_status_is_a_finding(self):
        found = rc.compare_rows([code('p1', 'ready')], [code('p1', 'pending')], rc.PROPOSAL_HELD, where='x')
        self.assertEqual([f['finding'] for f in found], ['unknown'])


class CompareEncounter(unittest.TestCase):
    def test_identical_views_compare_clean(self):
        doc = {'customer.detail[1]': customer('ready', [code('p1', 'ready', ['approve'])]),
               'member.detail[1]': {'assessment': {'proposals': [code('p1', 'ready', ['approve'])]},
                                    'readiness': {'draft': True, 'reviewed': False}},
               'state': {'stored': 'ready_for_review', 'derived': 'ready_for_review'},
               'readiness': {'review': {'reviewed': False}, 'customer': {'draft': True, 'approved': False}},
               'list.customer_row': {'state': 'ready'}}
        result = rc.compare_encounter(doc, json.loads(json.dumps(doc)))
        self.assertEqual((result['findings'], result['errors'], result['compared']), ([], [], 2))

    def test_less_held_state_offers_and_codes_are_found(self):
        before = {'customer.detail[1]': customer('awaiting_detail', [code('p1', 'needs_detail')]),
                  'readiness': {'review': {'reviewed': False}, 'customer': {'approved': False}}}
        after = {'customer.detail[1]': customer('ready', [code('p1', 'ready', ['approve'])], readiness__approved=True,
                                                progress__can_resume=True),
                 'readiness': {'review': {'reviewed': True}, 'customer': {'approved': True}}}
        found = rc.compare_encounter(before, after)['findings']
        kinds = sorted((f['where'], f['finding'], f.get('offer', '')) for f in found)
        self.assertIn(('customer.detail[1]', 'state_toward_release', ''), kinds)
        self.assertIn(('customer.detail[1]', 'offer_not_made_before', 'readiness.approved'), kinds)
        self.assertIn(('customer.detail[1]', 'offer_not_made_before', 'progress.can_resume'), kinds)
        self.assertIn(('customer.detail[1]', 'toward_release', ''), kinds)
        self.assertIn(('customer.detail[1]', 'action_not_allowed_before', ''), kinds)
        self.assertIn(('readiness.review', 'offer_not_made_before', 'reviewed'), kinds)
        self.assertIn(('readiness.customer', 'offer_not_made_before', 'approved'), kinds)

    def test_more_held_everywhere_is_accepted(self):
        before = {'customer.detail[1]': customer('ready', [code('p1', 'ready', ['approve', 'reject'])],
                                                 readiness__approved=True),
                  'state': {'stored': 'ready_for_review', 'derived': 'ready_for_review'},
                  'member.detail[1]': {'assessment': {'proposals': [code('p1', 'ready', ['approve'])]}}}
        after = {'customer.detail[1]': customer('awaiting_detail', [code('p1', 'needs_detail', ['reject'])]),
                 'state': {'stored': 'ready_for_review', 'derived': 'needs_clarification'},
                 'member.detail[1]': {'assessment': {'proposals': [code('p1', 'needs_clarification')]}}}
        self.assertEqual(rc.compare_encounter(before, after)['findings'], [])

    def test_a_view_that_raised_is_an_error_on_its_side(self):
        before = {'customer.detail[1]': customer()}
        after = {'customer.detail[1]': {'__error__': 'KeyError: x', '__where__': []}}
        result = rc.compare_encounter(before, after)
        self.assertEqual([(e['view'], e['side']) for e in result['errors']], [('customer.detail[1]', 'after')])
        self.assertEqual(result['compared'], 0)

    def test_derived_state_released_by_the_previous_image(self):
        before = {'state': {'stored': 'needs_clarification', 'derived': 'needs_clarification'}}
        after = {'state': {'stored': 'needs_clarification', 'derived': 'reviewed'}}
        self.assertEqual([f['finding'] for f in rc.compare_encounter(before, after)['findings']], ['toward_release'])


class Recompute(unittest.TestCase):
    def test_declared_changes(self):
        states = {'a': {'stored': 'ready_for_review', 'derived': 'ready_for_review'},
                  'b': {'stored': 'stopped', 'derived': 'processing_failed'},
                  'c': {'__error__': 'boom'}}
        self.assertEqual(rc.declared_changes(states), {'b': ['stopped', 'processing_failed']})

    def test_as_declared_and_toward_held(self):
        declared = {'n1': ['ready_for_review', 'needs_clarification'], 'n2': ['stopped', 'processing_failed']}
        answer = {'encounters': 3, 'changed': {'n1': ['ready_for_review', 'needs_clarification'],
                                               'n2': ['stopped', 'processing_failed']}}
        self.assertEqual(rc.recompute_problems(answer, answer, declared, ['n1', 'n2']), [])

    def test_an_undeclared_change_or_a_release_fails(self):
        declared = {'n1': ['needs_clarification', 'ready_for_review']}
        answer = {'changed': {'n1': ['needs_clarification', 'ready_for_review'], 'l1': ['reviewed', 'no_codes']}}
        problems = rc.recompute_problems(answer, answer, declared, ['n1'])
        self.assertTrue(any('is not the declared' in p for p in problems))
        self.assertTrue(any('n1 moved needs_clarification -> ready_for_review (toward_release)' in p for p in problems))

    def test_applied_must_equal_read_only_and_answer(self):
        declared = {}
        self.assertTrue(rc.recompute_problems({'changed': {}}, None, declared, []))
        self.assertTrue(rc.recompute_problems({'changed': {}}, {'changed': {'x': ['a', 'b']}}, declared, []))
        self.assertEqual(rc.recompute_problems({'changed': {}}, {'changed': {}}, declared, []), [])


class Note(unittest.TestCase):
    INDEPENDENT = {'assessments': 3, 'encounters': ['e1', 'e2', 'e3'], 'context_only': ['e3']}

    def note(self, **change):
        value = {'assessments': 3, 'encounters': ['e2', 'e1', 'e3'], 'context_only': ['e3'],
                 'note': '3 assessments were made from event inventories; the earlier image reads them fail-closed'}
        value.update(change)
        return value

    def test_exactly_the_new_path_encounters(self):
        self.assertEqual(rc.note_problems(self.note(), self.INDEPENDENT, self.INDEPENDENT), [])

    def test_a_missing_or_extra_encounter_fails(self):
        self.assertTrue(rc.note_problems(self.note(encounters=['e1', 'e3']), self.INDEPENDENT))
        self.assertTrue(rc.note_problems(self.note(encounters=['e1', 'e2', 'e3', 'e4']), self.INDEPENDENT))

    def test_context_only_and_the_count_are_compared(self):
        self.assertTrue(rc.note_problems(self.note(context_only=[]), self.INDEPENDENT))
        self.assertTrue(rc.note_problems(self.note(assessments=4), self.INDEPENDENT))
        declared = dict(self.INDEPENDENT, encounters=['e1', 'e2'])
        self.assertTrue(any('declared' in p for p in rc.note_problems(self.note(), self.INDEPENDENT, declared)))

    def test_a_note_that_did_not_count_fails(self):
        uncounted = {'assessments': None, 'encounters': None, 'context_only': None,
                     'note': 'the assessments made from event inventories ... were not counted (boom); ...'}
        self.assertEqual(rc.note_problems(uncounted, self.INDEPENDENT), ['the note did not count what it read'])
        self.assertTrue(rc.note_problems(self.note(note='were not counted'), self.INDEPENDENT))
        self.assertTrue(rc.note_problems(None, self.INDEPENDENT))


class Markers(unittest.TestCase):
    def item(self, **change):
        value = {'id': 'r1', 'stored_sha256': 'abc', 'before': {'current': True, 'marker_digest': 'd1'},
                 'after': {'current': True, 'marker_digest': 'd1'}, 'download': {'status': 200, 'sha256': 'abc'}}
        value.update(change)
        return value

    def test_equal_digest_and_a_current_download(self):
        self.assertEqual(rc.marker_problems([self.item()]), [])
        stale = self.item(before={'current': False, 'marker_digest': 'd2'}, after={'current': False, 'marker_digest': 'd2'},
                          download={'status': 409, 'sha256': 'x'})
        self.assertEqual(rc.marker_problems([stale]), [])

    def test_failures(self):
        self.assertTrue(rc.marker_problems([self.item(after={'current': True, 'marker_digest': 'd9'})]))
        self.assertTrue(rc.marker_problems([self.item(after={'current': False, 'marker_digest': 'd1'})]))
        self.assertTrue(rc.marker_problems([self.item(download={'status': 409})]))
        self.assertTrue(rc.marker_problems([self.item(download={'status': 200, 'sha256': 'other'})]))
        self.assertTrue(rc.marker_problems([self.item(before={'current': True, 'marker_digest': None},
                                                      after={'current': True, 'marker_digest': None})]))
        self.assertEqual(rc.marker_problems([]), ['no approved export made by the candidate was checked'])

    def test_an_encounter_one_image_did_not_render(self):
        item = self.item(after={'current': None, 'marker_digest': None, 'not_rendered': True})
        self.assertEqual(rc.marker_problems([item]), ['r1: its encounter was not rendered by both images'])


class Targets(unittest.TestCase):
    def test_the_live_ports_containers_and_databases_are_refused(self):
        self.assertEqual(rc.target_problems(9173, 55461, 'gi4-cpt-test-pg', 'cptg_d15'), [])
        for port in (9150, 9151, 80, 0, '9173', True):
            self.assertTrue(rc.target_problems(port, 55461, 'gi4-cpt-test-pg', 'cptg_d15'), port)
        self.assertTrue(rc.target_problems(9173, 55451, 'gi4-cpt-test-pg', 'cptg_d15'))
        self.assertTrue(rc.target_problems(9173, '55451', 'gi4-cpt-test-pg', 'cptg_d15'))
        for container in ('cpt-studio-db', 'cpt-studio-web', 'cpt-studio-worker', 'cpt-studio-web-next'):
            self.assertTrue(rc.target_problems(9173, 55461, container, 'cptg_d15'), container)
        for db in ('cptstudio', 'postgres', 'cptg_', 'cptg_D15', 'cptg_d15; drop', None):
            self.assertTrue(rc.target_problems(9173, 55461, 'gi4-cpt-test-pg', db), db)

    def test_main_refuses_before_any_command(self):
        with mock.patch.object(rc.subprocess, 'run', side_effect=AssertionError('nothing may run')) as run, \
                contextlib.redirect_stderr(io.StringIO()) as said:
            for port, pg_port in ((9150, 55461), (9151, 55461), (9173, 55451)):
                code_ = rc.main(['--db', 'cptg_d15', '--candidate', 'c', '--previous', 'p', '--port', str(port),
                                 '--pg-port', str(pg_port), '--out', '/nonexistent/d15-out', '--since',
                                 '2026-11-10T13:19:00+00:00', '--renderer', '/nonexistent', '--db-env-file', '/x',
                                 '--member-credentials', '/x', '--operator-credentials', '/x'])
                self.assertEqual(code_, 2)
            run.assert_not_called()
        self.assertEqual(said.getvalue().splitlines(), ['refused: port 9150 is a port of the live web',
                                                       'refused: port 9151 is a port of the live web',
                                                       'refused: port 55451 is the live database'])


class Times(unittest.TestCase):
    def test_pg_time(self):
        self.assertEqual(rc.pg_time('2026-11-10 14:18:11.803978+00').isoformat(), '2026-11-10T14:18:11.803978+00:00')
        self.assertEqual(rc.pg_time('2026-11-10T14:18:11+00:00').isoformat(), '2026-11-10T14:18:11+00:00')
        self.assertIsNone(rc.pg_time('2026-11-10 14:18:11'))  # no offset: never compared
        self.assertIsNone(rc.pg_time(''))
        self.assertIsNone(rc.pg_time(None))

    def test_settled_before_the_worker_started(self):
        note = 'Closed by the installer: revision 2fe6efe89c56 was switched back ...'
        rows = [['j1', 'failed', '2026-11-10 14:30:00.5+00', note]]
        self.assertTrue(rc.settled_before(rows, '2026-11-10T14:31:00+00:00'))
        self.assertFalse(rc.settled_before(rows, '2026-11-10T14:29:00+00:00'))  # closed after the start
        self.assertFalse(rc.settled_before([['j1', 'failed', '2026-11-10 14:30:00+00', 'another error']],
                                           '2026-11-10T14:31:00+00:00'))
        self.assertFalse(rc.settled_before(rows + [['j2', 'queued', '', '']], '2026-11-10T14:31:00+00:00'))
        self.assertFalse(rc.settled_before([], '2026-11-10T14:31:00+00:00'))


class InstallError(RuntimeError):
    """install.InstallError's shape: a message, and the output kept as bytes."""

    def __init__(self, message, *, output=b'', details=None):
        super().__init__(message)
        self.output, self.details = output, details


class Transport(unittest.TestCase):
    """The one-shot stands in for the installer's app_script with its signature and its answer rules."""

    def setUp(self):
        self.instance = rc.Instance(db='cptg_test', pg_container='gi4-cpt-test-pg', pg_port=55461,
                                    env_bytes=b'CPT_STUDIO_DB_USER=u\nCPT_STUDIO_DB_PASSWORD=p\n',
                                    files_volume='cptg-files-cptg_test', log=lambda line: None)
        self.installer = SimpleNamespace(APP_SCRIPT_PRELUDE='import base64, json\nP = json.loads(base64.b64decode('
                                                            '{payload!r}))\nANSWER = {answer!r}\n',
                                         APP_SCRIPT_ANSWER='cpt-studio-answer ', InstallError=InstallError)

    def answered(self, stdout, code_=0):
        def oneshot(image, command, **kwargs):
            self.seen = (image, command, kwargs)
            self.instance.calls.append({'what': kwargs.get('what'), 'exit': code_})
            return subprocess.CompletedProcess(command, code_, stdout.encode(), b'traceback tail')
        return oneshot

    def test_the_prelude_parameters_and_the_answer_line(self):
        transport = self.instance.transport(self.installer, {'sha256:' + 'a' * 64: 'cpt-studio-test:x'})
        with mock.patch.object(self.instance, 'oneshot', self.answered('noise\ncpt-studio-answer {"closed": 1}\n')):
            answer = transport('sha256:' + 'a' * 64, b'ignored', 'print(1)\n', {'since': 's', 'kinds': ['a']},
                               what='close', timeout=180)
        self.assertEqual(answer, {'closed': 1})
        image, command, kwargs = self.seen
        self.assertEqual(command[:3], ['manage', 'shell', '-c'])
        payload = base64.b64encode(json.dumps({'since': 's', 'kinds': ['a']}).encode()).decode()
        self.assertTrue(command[3].startswith(f'import base64, json\nP = json.loads(base64.b64decode({payload!r}))\n'))
        self.assertTrue(command[3].endswith("ANSWER = 'cpt-studio-answer '\nprint(1)\n"))
        self.assertEqual(kwargs['what'], 'close')

    def test_no_answer_or_two_answers_or_an_exit_raise(self):
        transport = self.instance.transport(self.installer, {'sha256:' + 'a' * 64: 't'})
        for stdout, code_ in (('nothing\n', 0), ('cpt-studio-answer {}\ncpt-studio-answer {}\n', 0),
                              ('cpt-studio-answer {}\n', 1)):
            with mock.patch.object(self.instance, 'oneshot', self.answered(stdout, code_)):
                with self.assertRaises(RuntimeError):
                    transport('sha256:' + 'a' * 64, b'', 'x', {}, what='w')

    def test_an_image_the_check_does_not_run_is_refused(self):
        transport = self.instance.transport(self.installer, {'sha256:' + 'a' * 64: 't'})
        with mock.patch.object(self.instance, 'oneshot', side_effect=AssertionError('nothing may run')):
            with self.assertRaises(rc.Refused):
                transport('sha256:' + 'b' * 64, b'', 'x', {}, what='w')

    def test_the_env_file_must_name_the_database_user(self):
        with self.assertRaises(rc.Refused):
            rc.Instance(db='cptg_test', pg_container='gi4-cpt-test-pg', pg_port=55461, env_bytes=b'X=1\n',
                        files_volume='v', log=print)


class Installer(unittest.TestCase):
    """The names the runner takes from ops/install.py exist with the signatures it calls them by (a rename there must
    fail here, not in the middle of a D15 run)."""

    def test_the_installer_names_the_runner_uses(self):
        import inspect
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import install
        for name in ('APP_SCRIPT_PRELUDE', 'APP_SCRIPT_ANSWER', 'UNDO_HAZARDS_READ', 'CLOSE_STAGES', 'UNRUNNABLE_STAGES',
                     'RECOMPUTE_STATES', 'INTERPRETATION_MADE'):
            self.assertIsInstance(getattr(install, name), str, name)
        self.assertEqual(list(inspect.signature(install.app_script).parameters)[:4],
                         ['image_id', 'env_bytes', 'body', 'params'])
        for name, params in (('undo_hazards', ['image_id', 'env_bytes', 'revision']),
                             ('interpretation_note', ['image_id', 'env_bytes', 'revision']),
                             ('stage_kinds_of', ['image_id', 'env_bytes']),
                             ('close_undone_stages', ['image_id', 'env_bytes', 'since', 'revision', 'reason', 'kinds']),
                             ('put_back_states', ['closed', 'older_image', 'image_id', 'env_bytes'])):
            self.assertEqual(list(inspect.signature(getattr(install, name)).parameters), params, name)
        self.assertNotIn(rc.LIVE_DB_PORT, ())
        self.assertEqual(install.DB_PORT, rc.LIVE_DB_PORT)
        self.assertEqual(tuple(install.WEB_PORTS), rc.REFUSED_WEB_PORTS)
        self.assertIn(install.DB_CONTAINER, rc.LIVE_CONTAINERS)
        self.assertTrue(set(install.SERVICES.values()) <= set(rc.LIVE_CONTAINERS))
        self.assertIn(install.INCOMING_WEB, rc.LIVE_CONTAINERS)

    def test_the_rolled_back_recompute_wraps_the_body_verbatim(self):
        body = "print(ANSWER + json.dumps({'changed': {}}))\n"
        wrapped = rc.ROLLED_BACK.format(body=body)
        self.assertIn(repr(body), wrapped)
        self.assertIn('set_rollback(True)', wrapped)



# --- design v2 (FINAL-V2 6.4; AMENDMENT-1 9.4, 9.5 and U17; step 6b) ----------------------------------------------------

class ScenarioV2(unittest.TestCase):
    def found(self, **overrides):
        return {**{key: 1 for key, _, _ in rc.SCENARIO_V2}, **overrides}

    def test_the_thirteen_record_kinds_of_6_4_are_each_counted(self):
        self.assertEqual(len(rc.SCENARIO_V2), 14)  # 6.4's list, the approved code's export counted on its own
        self.assertEqual(rc.scenario_problems(self.found()), [])
        keys = [key for key, _, _ in rc.SCENARIO_V2]
        for want in ('interpreted_and_appraised', 'queued_appraise', 'pass2_refusal', 'unhealthy_appraisal',
                     'held_new_fact', 'approved_with_modifier', 'interpreter_hold', 'second_review'):
            self.assertIn(want, keys)
        for statement in (sql for _, _, sql in rc.SCENARIO_V2):
            self.assertTrue(statement.startswith('select count(*) from studio_'), statement)

    def test_a_kind_missing_zero_or_not_counted_fails_naming_it(self):
        problems = rc.scenario_problems(self.found(queued_appraise=0, pass2_refusal='RuntimeError: psql failed'))
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith('queued_appraise: the run holds no a queued appraise job'))
        self.assertTrue(problems[1].startswith('pass2_refusal: not counted'))
        self.assertEqual(len(rc.scenario_problems({})), len(rc.SCENARIO_V2))
        self.assertEqual(len(rc.scenario_problems(None)), len(rc.SCENARIO_V2))


class ScenarioAmendment2(unittest.TestCase):
    """AMENDMENT-2 8.5 [R:replay-R6]: the record kinds read both engine versions and every interpreter provider, and a
    Fable candidate's run must hold its new versions' rows; every literal is the server's own label."""

    def test_the_literals_are_the_servers_labels(self):
        found = labels()
        self.assertEqual(rc.V2_ENGINES, (found.ENGINE_VERSION_V2, found.ENGINE_VERSION_V3))
        self.assertEqual(rc.READ_PROVIDERS, found.READ_PROVIDERS)
        self.assertEqual((rc.PAIR_V3, rc.INVENTORY_V3, rc.ENGINE_V3, rc.ADAPTER_V3),
                         (found.INTERPRETATION_PAIR_V3, found.INVENTORY_VERSION_V3, found.ENGINE_VERSION_V3,
                          found.ADAPTER_VERSION_V3))
        self.assertEqual(rc.DECLINED, module_constants(APP_ROOT / 'studio' / 'models.py', ('DECLINED',),
                                                       within='InterpreterHold')['DECLINED'])
        self.assertEqual(rc.READ_PROVIDERS, ('anthropic', 'gemini'))  # Fable's, and Gemini's stored runs

    def test_each_kind_reads_both_engine_versions_and_every_interpreter_provider(self):
        engines, providers = rc.sql_strings(rc.V2_ENGINES), rc.sql_strings(rc.READ_PROVIDERS)
        self.assertEqual((engines, providers), ("('cpt-studio-events@2', 'cpt-studio-events@3')", "('anthropic', 'gemini')"))
        by_key = {key: sql for key, _, sql in rc.SCENARIO_V2}
        for key in ('held_code', 'excluded_code', 'reinstated_code', 'approved_with_modifier', 'approved_export',
                    'member_answer', 'second_review', 'held_new_fact'):
            with self.subTest(key=key):
                self.assertIn(f'engine_version in {engines}', by_key[key])
        for key in ('pass2_refusal', 'unhealthy_appraisal'):
            with self.subTest(key=key):
                self.assertIn(f'provider in {providers}', by_key[key])
        joined = ' '.join(sql for _, _, sql in rc.SCENARIO_V2 + rc.SCENARIO_V3)
        self.assertNotIn("engine_version = '", joined)
        self.assertNotIn("provider = '", joined)
        for statement in (sql for _, _, sql in rc.SCENARIO_V3):
            self.assertTrue(statement.startswith('select count(*) from studio_'), statement)
        self.assertEqual([key for key, _, _ in rc.SCENARIO_V3],
                         ['fable_inventory', 'fable_assessment', 'fable_run', 'declined_hold'])
        for wrong in ((), ("x'); drop table studio_job; --",), ('CPT-STUDIO',), (None,)):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                rc.sql_strings(wrong)

    def test_a_fable_candidate_is_judged_on_its_new_versions_rows_too(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import install
        self.assertTrue(rc.fable_candidate(install))  # this revision's installer installs the Fable interpreter
        self.assertFalse(rc.fable_candidate(SimpleNamespace(INTERPRETER={'name': 'gemini'})))  # an earlier one
        self.assertFalse(rc.fable_candidate(SimpleNamespace()))
        found = {key: 1 for key, _, _ in rc.SCENARIO_V2 + rc.SCENARIO_V3}
        self.assertEqual(rc.scenario_problems(found, rc.SCENARIO_V2 + rc.SCENARIO_V3), [])
        problems = rc.scenario_problems({**found, 'declined_hold': 0, 'fable_run': 'RuntimeError: psql failed'},
                                        rc.SCENARIO_V2 + rc.SCENARIO_V3)
        self.assertEqual(problems, ["fable_run: not counted ('RuntimeError: psql failed')",
                                    'declined_hold: the run holds no an interpreter hold with reason declined'])
        self.assertEqual(rc.scenario_problems({**found, 'declined_hold': 0}), [])  # 6.4's kinds alone: as before


class ScenarioOnAFableFilledDatabase(FableRows):
    """AMENDMENT-2 8.5 [R:replay-R6]: SCENARIO_V2's and SCENARIO_V3's statements run as SQL on a database the Fable
    candidate filled - every record kind on cpt-studio-events@3 rows and anthropic runs only - each count non-zero, so
    assertion 7 passes; with the literals before the repair (cpt-studio-events@2, 'gemini') ten of the thirteen kinds
    counted 0 on the same rows."""

    def counts(self, kinds):
        from django.db import connection
        found = {}
        with connection.cursor() as cursor:
            for key, _, statement in kinds:
                cursor.execute(statement)
                found[key] = cursor.fetchone()[0]
        return found

    def test_every_record_kind_counts_non_zero_and_assertion_7_passes(self):
        self.fill_d15()
        found = self.counts(rc.SCENARIO_V2 + rc.SCENARIO_V3)
        self.assertEqual(len(found), 18)  # 6.4's thirteen kinds (the export counted on its own) and 8.5's four
        self.assertEqual([key for key, count in found.items() if count < 1], [])
        self.assertEqual(rc.scenario_problems(found, rc.SCENARIO_V2 + rc.SCENARIO_V3), [])
        from studio import models
        self.assertFalse(models.Assessment.objects.filter(engine_version='cpt-studio-events@2').exists())  # none @2
        self.assertFalse(models.ProviderRun.objects.filter(provider='gemini').exists())  # and no Gemini run

    def test_the_literals_before_the_repair_count_ten_kinds_zero_on_the_same_rows(self):
        self.fill_d15()
        engines, providers = rc.sql_strings(rc.V2_ENGINES), rc.sql_strings(rc.READ_PROVIDERS)
        before = tuple((key, title, sql.replace(f'engine_version in {engines}', "engine_version = 'cpt-studio-events@2'")
                        .replace(f'provider in {providers}', "provider = 'gemini'"))
                       for key, title, sql in rc.SCENARIO_V2)
        self.assertEqual(sum(old != new for (_, _, old), (_, _, new) in zip(before, rc.SCENARIO_V2)), 10)
        found = self.counts(before)
        self.assertEqual(sorted(key for key, count in found.items() if count == 0),
                         sorted(['held_code', 'excluded_code', 'reinstated_code', 'approved_with_modifier',
                                 'approved_export', 'member_answer', 'second_review', 'held_new_fact', 'pass2_refusal',
                                 'unhealthy_appraisal']))
        self.assertEqual(len(rc.scenario_problems(found)), 10)


class UpdateRows(unittest.TestCase):
    DECLARED = {'pending_before_analyze': ['e1'], 'pending_after_analyze': ['e2'], 'completed': ['e3'], 'a21': ['e4']}
    CLOSE = {'update_pending': {'e1': ['values_saved'], 'e2': ['assessment_off_context'], 'e4': ['reconciled_unknown']},
             'reverted': {'e1': {'setting': {'saved': 'office', 'restored': None}}}}
    AFTER = {'e1': {'user_values': '{"service_date": "2026-11-10", "kept": "x"}', 'context': 'c1',
                    'context_values': '{"service_date": " 2026-11-10 "}'}}
    AUDITS = [['e1', '{"fields": ["setting"], "context": "c1"}']]

    def note(self, **overrides):
        return {'update_pending': ['e1', 'e2', 'e4'], 'reverted': self.CLOSE['reverted'], **overrides}

    def test_the_pending_updates_named_the_save_reverted_audited_listed_and_saved_again(self):
        self.assertEqual(rc.update_problems(self.DECLARED, self.CLOSE, self.note(), self.AFTER, self.AUDITS), [])
        declared = {**self.DECLARED, 'resave': {'encounter': 'e1', 'field': 'setting', 'value': 'office'}}
        resave = {'via': 'details', 'row': 'r1', 'status': 201, 'saved': 1, 'unchanged': 0, 'context_before': 'c1',
                  'context_after': 'c9', 'value_after': 'office'}
        self.assertEqual(rc.update_problems(declared, self.CLOSE, self.note(), self.AFTER, self.AUDITS, resave), [])

    def test_each_failure_is_named(self):
        cases = {
            'did not name it update_pending (values_saved)':
                (self.DECLARED, {**self.CLOSE, 'update_pending': {'e2': ['assessment_off_context'],
                                                                  'e4': ['reconciled_unknown']}}, self.note(), self.AFTER,
                 self.AUDITS),
            'completed e3: the close named it':
                (self.DECLARED, {**self.CLOSE, 'update_pending': {**self.CLOSE['update_pending'], 'e3': ['values_saved']}},
                 self.note(), self.AFTER, self.AUDITS),
            'the close reverted []':
                (self.DECLARED, {**self.CLOSE, 'reverted': {}}, self.note(reverted={}), self.AFTER, self.AUDITS),
            'are not its context':
                (self.DECLARED, self.CLOSE, self.note(), {'e1': {**self.AFTER['e1'], 'user_values': '{"setting": "office"}'}},
                 self.AUDITS),
            'context.rollback_reverted row(s)':
                (self.DECLARED, self.CLOSE, self.note(), self.AFTER, []),
            'the switch-back note lists update_pending':
                (self.DECLARED, self.CLOSE, self.note(update_pending=['e1']), self.AFTER, self.AUDITS),
            'does not list the reverted values':
                (self.DECLARED, self.CLOSE, self.note(reverted={}), self.AFTER, self.AUDITS),
        }
        for want, args in cases.items():
            with self.subTest(want=want):
                problems = rc.update_problems(*args)
                self.assertTrue(any(want in problem for problem in problems), problems)
        declared = {**self.DECLARED, 'resave': {'encounter': 'e1', 'field': 'setting', 'value': 'office'}}
        saved = {'via': 'details', 'row': 'r1', 'status': 201, 'saved': 1, 'unchanged': 0}
        for resave, want in (({**saved, 'status': 409}, 'it answered 409'),
                             # refutation 6b-r1 P4: the hazard itself - 200, nothing saved, the value read "unchanged"
                             ({**saved, 'status': 200, 'saved': 0, 'unchanged': 1, 'context_before': 'c1',
                               'context_after': 'c1', 'value_after': None}, 'saved 0, unchanged 1'),
                             # a save made through /context passes whether or not the revert ran: never accepted
                             ({'status': 201, 'context_before': 'c1', 'context_after': 'c9', 'value_after': 'office'},
                              'not saved again through the previous web\'s details panel'),
                             ({'via': 'details', 'row': None, 'panel_facts': ['date_of_service']},
                              'offers no setting row for e1 (it asks [\'date_of_service\'])'),
                             ({**saved, 'context_before': 'c1', 'context_after': 'c1', 'value_after': 'office'},
                              'did not take effect'),
                             ({**saved, 'context_before': 'c1', 'context_after': 'c9', 'value_after': None},
                              'did not take effect')):
            with self.subTest(resave=resave):
                problems = rc.update_problems(declared, self.CLOSE, self.note(), self.AFTER, self.AUDITS, resave)
                self.assertTrue(any(want in problem for problem in problems), problems)
        self.assertEqual(rc.update_problems(None, self.CLOSE, self.note(), self.AFTER, self.AUDITS),
                         ['the run declared no update encounters (--declared: update)'])

    def test_member_values_read_as_review_values_reads_them(self):
        self.assertEqual(rc.member_values('{"setting": " office ", "kept": "x", "service_date": ""}'),
                         {'setting': 'office'})
        self.assertEqual(rc.member_values(None), {})
        self.assertIn('__unreadable__', rc.member_values('not json'))


class ReadingStages(unittest.TestCase):
    def test_each_reading_kind_is_settled_by_the_close_before_the_worker_starts(self):
        closed = 'Closed by the installer: switched back.'
        rows = [['j1', 'interpret', 'failed', '2026-11-13 10:00:00+00', closed],
                ['j2', 'appraise', 'failed', '2026-11-13 10:00:01+00', closed]]
        self.assertTrue(rc.reading_settled_before(rows, '2026-11-13T10:05:00+00:00'))
        self.assertFalse(rc.reading_settled_before(rows + [['j3', 'appraise', 'queued', None, '']],
                                                   '2026-11-13T10:05:00+00:00'))
        self.assertFalse(rc.reading_settled_before([rows[0], ['j2', 'appraise', 'failed', '2026-11-13 10:00:01+00',
                                                              'another error']], '2026-11-13T10:05:00+00:00'))
        self.assertFalse(rc.reading_settled_before([], '2026-11-13T10:05:00+00:00'))


class CountsCommand(unittest.TestCase):
    def test_it_refuses_before_any_command(self):
        with mock.patch.object(rc.subprocess, 'run', side_effect=AssertionError('nothing may run')) as run, \
                contextlib.redirect_stderr(io.StringIO()) as said:
            for extra in (['--pg-port', '55451'], ['--pg-container', 'cpt-studio-db'], ['--db', 'cptstudio']):
                argv = ['counts', '--db', 'cptg_dump', '--candidate', 'c', '--out', '/nonexistent/counts-out',
                        '--db-env-file', '/x', *extra]
                self.assertEqual(rc.main(argv), 2)
            self.assertEqual(rc.main(['counts', '--db', 'cptg_dump', '--candidate', 'c', '--out', '/',
                                      '--db-env-file', '/x']), 2)  # an --out that exists
            run.assert_not_called()
        lines = said.getvalue().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertIn('port 55451 is the live database', lines[0])
        self.assertIn('cpt-studio-db is a live container', lines[1])
        self.assertIn("'cptstudio' is not a test database", lines[2])
        self.assertIn('/ exists', lines[3])


class CountsOnACopy(unittest.TestCase):
    """Refutation 6b-r1 P3: `counts` reads a migrated COPY of the restored dump - live has no 0014/0015 table, so the
    reads fail on the dump as it stands - writes every failure into counts.json, and never writes the dump."""
    CANDIDATE = {'id': 'sha256:' + 'c' * 64, 'tag': 'cpt-studio-test:cccccccccccc', 'revision': 'c' * 40}

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix='counts-'))
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        self.env = self.tmp / 'db.env'
        self.env.write_bytes(b'CPT_STUDIO_DB_USER=u\nCPT_STUDIO_DB_PASSWORD=p\n')
        self.env.chmod(0o600)
        self.seen, self.migrate_exit, self.raising, self.existing = [], 0, None, '0'

    def installer(self):
        ns = SimpleNamespace(APP_SCRIPT_PRELUDE='P = {payload!r}\nANSWER = {answer!r}\n',
                             APP_SCRIPT_ANSWER='cpt-studio-answer ', InstallError=InstallError)
        ns.app_script = None  # patched by the command with the copy's transport
        ns.v1_rows = lambda image, env: ns.app_script(image, env, 'V1_ROWS', {}, what='v1 rows')
        ns.v1_rows_refusal = lambda answer: None if answer == {'v1': 0} else 'refused'

        def install_counts(image, env):
            try:
                answer = ns.app_script(image, env, 'INSTALL_COUNTS', {}, what='counts')
            except Exception as error:  # the installer's own rule: recorded as not counted
                return {'counted': False, 'why': str(error), 'report': []}
            return {'counted': True, **answer, 'report': ['synthetic']}
        ns.install_counts = install_counts
        return ns

    def run_counts(self, **extra):
        test = self

        def sql(instance, statement, *, db=None, write=False):
            test.seen.append(('sql', instance.db, statement))
            return [[test.existing]]

        def copy_database(instance, source, target):
            test.seen.append(('copy', source, target))

        def oneshot(instance, image, command, *, what, db=None, read_only=False, mounts=(), env=(), timeout=900):
            target = db or instance.db
            test.seen.append(('oneshot', target, command[:2], read_only))
            instance.calls.append({'what': what, 'db': target, 'read_only_session': read_only})
            if command[:2] == ['manage', 'migrate']:
                return subprocess.CompletedProcess(command, test.migrate_exit, b'Applying studio.0015... OK\n', b'')
            body = command[-1]
            if test.raising and test.raising in body:
                return subprocess.CompletedProcess(command, 1, b'', b'ProgrammingError: relation does not exist')
            answer = {'v1': 0} if body.endswith('V1_ROWS') else {'size': 'synthetic'}
            return subprocess.CompletedProcess(command, 0, f'cpt-studio-answer {json.dumps(answer)}\n'.encode(), b'')
        argv = ['counts', '--db', 'cptg_dump', '--candidate', self.CANDIDATE['tag'], '--out', str(self.tmp / 'out'),
                '--db-env-file', str(self.env), *extra.get('argv', [])]
        with mock.patch.object(rc, 'image_info', return_value=dict(self.CANDIDATE)), \
                mock.patch.object(rc, 'load_installer', return_value=self.installer()), \
                mock.patch.object(rc.Instance, 'sql', sql), mock.patch.object(rc.Instance, 'copy_database', copy_database), \
                mock.patch.object(rc.Instance, 'oneshot', oneshot), \
                mock.patch.object(rc.subprocess, 'run', side_effect=AssertionError('no other command may run')), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as said:
            code = rc.main(argv)
        path = self.tmp / 'out' / 'counts.json'
        return code, (json.loads(path.read_text(encoding='utf-8')) if path.exists() else None), said.getvalue()

    def test_the_dump_is_copied_the_copy_migrated_and_only_the_copy_read_read_only(self):
        code, record, _ = self.run_counts()
        self.assertEqual(code, 0)
        self.assertEqual(self.seen[0][:2], ('sql', 'cptg_dump'))  # the copy name is free, read before --out is made
        self.assertEqual(self.seen[1:], [
            ('copy', 'cptg_dump', 'cptg_dump_counts'),
            ('oneshot', 'cptg_dump_counts', ['manage', 'migrate'], False),
            ('oneshot', 'cptg_dump_counts', ['manage', 'shell'], True),
            ('oneshot', 'cptg_dump_counts', ['manage', 'shell'], True)])
        self.assertNotIn('cptg_dump', [entry[1] for entry in self.seen[2:]])  # nothing runs on the dump itself
        self.assertEqual((record['db'], record['copy'], record['db_written']), ('cptg_dump', 'cptg_dump_counts', False))
        self.assertEqual(record['migrate']['exit'], 0)
        self.assertEqual(record['v1_rows'], {'v1': 0})
        self.assertIsNone(record['v1_refusal'])
        self.assertIs(record['install_counts']['counted'], True)
        self.assertNotIn('failed', record)
        self.assertEqual([call['db'] for call in record['calls']], ['cptg_dump_counts'] * 3)

    def test_a_migration_that_fails_is_written_and_nothing_is_read(self):
        self.migrate_exit = 1
        code, record, _ = self.run_counts()
        self.assertEqual(code, 1)
        self.assertIn('could not be migrated with the candidate (exit 1); nothing was read', record['failed'])
        self.assertEqual([entry for entry in self.seen if entry[0] == 'oneshot'],
                         [('oneshot', 'cptg_dump_counts', ['manage', 'migrate'], False)])
        self.assertNotIn('v1_rows', record)

    def test_a_read_that_fails_is_written_never_raised_behind_an_out_that_exists(self):
        self.raising = 'V1_ROWS'
        code, record, _ = self.run_counts()
        self.assertEqual(code, 1)
        self.assertIn('InstallError', record['failed'])
        self.assertNotIn('install_counts', record)
        self.raising, self.seen = 'INSTALL_COUNTS', []
        (self.tmp / 'out' / 'counts.json').unlink()
        (self.tmp / 'out').rmdir()
        code, record, _ = self.run_counts()
        self.assertEqual(code, 1)  # read, but not counted: the owner's counts are not there
        self.assertIs(record['install_counts']['counted'], False)
        self.assertNotIn('failed', record)

    def test_a_copy_that_exists_or_a_copy_name_too_long_refuses_before_out_is_made(self):
        self.existing = '1'
        code, record, said = self.run_counts()
        self.assertEqual((code, record), (2, None))
        self.assertIn('cptg_dump_counts exists', said)
        self.assertFalse((self.tmp / 'out').exists())
        self.assertEqual([entry[0] for entry in self.seen], ['sql'])
        self.seen = []
        long = 'cptg_' + 'a' * 38
        code, record, said = self.run_counts(argv=['--db', long])
        self.assertEqual((code, record, self.seen), (2, None, []))
        self.assertIn('is not a test database name: give a shorter --db', said)


class ResaveThroughTheDetailsPanel(unittest.TestCase):
    """Refutation 6b-r1 P4: U17's resave is made as a member makes it on the previous web - its details panel's own
    row, POST .../details (answers.save_details) - never through /context, which passes whatever the revert did."""
    PK = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f'

    def browser(self, panel, answer=(201, {'saved': 1, 'unchanged': 0, 'answer_ids': [], 'reassessing': True})):
        calls = []

        def call(method, path, payload=None, **kwargs):
            calls.append((method, path, payload))
            if method == 'GET':
                return 200, {'details_needed': panel}, {}
            return answer[0], answer[1], {}
        return SimpleNamespace(call=call), calls

    def check(self, contexts):
        check = rc.Check.__new__(rc.Check)
        statements = []

        def sql(statement, **kwargs):
            statements.append(statement)
            return [contexts.pop(0)]
        check.instance = SimpleNamespace(sql=sql)
        return check, statements

    def test_the_value_is_saved_with_the_panels_own_row_through_details(self):
        member, calls = self.browser([{'id': 'd-date', 'fact': 'service_date'},
                                      {'id': 'd-setting', 'fact': 'setting', 'entered_value': 'office'}])
        check, statements = self.check([['c1'], ['c9', 'asc']])
        got = check.resave(member, {'encounter': self.PK, 'field': 'setting', 'value': 'asc'})
        self.assertEqual(calls, [('GET', f'/api/encounters/{self.PK}', None),
                                 ('POST', f'/api/encounters/{self.PK}/details',
                                  {'answers': [{'id': 'd-setting', 'fact': 'setting', 'value': 'asc'}]})])
        self.assertNotIn(f'/api/encounters/{self.PK}/context', [path for _, path, _ in calls])
        self.assertEqual({key: got[key] for key in ('via', 'row', 'status', 'saved', 'context_before', 'context_after',
                                                     'value_after')},
                         {'via': 'details', 'row': 'd-setting', 'status': 201, 'saved': 1, 'context_before': 'c1',
                          'context_after': 'c9', 'value_after': 'asc'})
        self.assertTrue(all(self.PK in statement for statement in statements))
        declared = {**UpdateRows.DECLARED, 'resave': {'encounter': self.PK, 'field': 'setting', 'value': 'asc'}}
        problems = rc.update_problems(declared, UpdateRows.CLOSE, UpdateRows().note(), UpdateRows.AFTER,
                                      UpdateRows.AUDITS, got)
        self.assertFalse([problem for problem in problems if 'saved again' in problem or 'panel' in problem], problems)

    def test_the_hazard_answer_and_a_panel_without_the_row_each_fail_assertion_8(self):
        declared = {**UpdateRows.DECLARED, 'resave': {'encounter': self.PK, 'field': 'setting', 'value': 'asc'}}
        member, _ = self.browser([{'id': 'd-setting', 'fact': 'setting'}],
                                 answer=(200, {'saved': 0, 'unchanged': 1, 'answer_ids': [], 'reassessing': False}))
        check, _ = self.check([['c1'], ['c1', 'office']])
        hazard = check.resave(member, {'encounter': self.PK, 'field': 'setting', 'value': 'asc'})
        member, calls = self.browser([{'id': 'd-date', 'fact': 'service_date'}])
        check, statements = self.check([])
        unasked = check.resave(member, {'encounter': self.PK, 'field': 'setting', 'value': 'asc'})
        self.assertEqual([method for method, _, _ in calls], ['GET'])  # nothing posted, no SQL
        self.assertEqual(statements, [])
        self.assertEqual((unasked['row'], unasked['panel_facts']), (None, ['service_date']))
        for got, want in ((hazard, 'saved 0, unchanged 1'), (unasked, 'offers no setting row')):
            problems = rc.update_problems(declared, UpdateRows.CLOSE, UpdateRows().note(), UpdateRows.AFTER,
                                          UpdateRows.AUDITS, got)
            self.assertTrue(any(want in problem for problem in problems), problems)


class TransportReadOnly(unittest.TestCase):
    def test_a_read_only_transport_runs_its_one_shots_in_a_read_only_session(self):
        instance = rc.Instance(db='cptg_test', pg_container='gi4-cpt-test-pg', pg_port=55461,
                               env_bytes=b'CPT_STUDIO_DB_USER=u\nCPT_STUDIO_DB_PASSWORD=p\n',
                               files_volume='cptg-files-cptg_test', log=lambda line: None)
        installer = SimpleNamespace(APP_SCRIPT_PRELUDE='P = {payload!r}\nANSWER = {answer!r}\n',
                                    APP_SCRIPT_ANSWER='cpt-studio-answer ', InstallError=InstallError)
        seen = []

        def oneshot(image, command, **kwargs):
            seen.append(kwargs)
            instance.calls.append({'what': kwargs.get('what'), 'exit': 0})
            return subprocess.CompletedProcess(command, 0, b'cpt-studio-answer {}\n', b'')
        image = 'sha256:' + 'a' * 64
        with mock.patch.object(instance, 'oneshot', oneshot):
            instance.transport(installer, {image: 't'}, read_only=True)(image, b'', 'x', {}, what='counts')
            instance.transport(installer, {image: 't'})(image, b'', 'x', {}, what='close')
        self.assertEqual([item['read_only'] for item in seen], [True, False])


class UpdateRowsSql(unittest.TestCase):
    def test_only_uuids_reach_the_sql_and_a_field_must_be_a_context_field(self):
        check = rc.Check.__new__(rc.Check)
        statements = []
        check.instance = SimpleNamespace(sql=lambda statement, **kwargs: statements.append(statement) or [])
        pk = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f'
        self.assertEqual(check.update_rows([pk, "x'); drop table studio_encounter; --", 'e1']), {})
        self.assertEqual(len(statements), 1)
        self.assertIn(f"'{pk}'", statements[0])
        self.assertNotIn('drop table', statements[0])
        statements.clear()
        self.assertEqual(check.update_rows(['e1']), {})
        self.assertEqual(statements, [])  # nothing left to read: no SQL at all
        self.assertEqual(rc.CONTEXT_FIELDS, ('service_date', 'setting', 'billing_context', 'patient_status'))


class InstallerV2(unittest.TestCase):
    def test_the_v2_names_the_runner_uses_exist_with_their_signatures(self):
        import inspect
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import install
        self.assertEqual(install.APPRAISE_KIND, 'appraise')
        for name in ('V1_ROWS', 'INSTALL_COUNTS'):
            self.assertIsInstance(getattr(install, name), str, name)
        for name, params in (('v1_rows', ['image_id', 'env_bytes']), ('v1_rows_refusal', ['answer']),
                             ('install_counts', ['image_id', 'env_bytes']), ('with_update_note', ['note', 'closes'])):
            self.assertEqual(list(inspect.signature(getattr(install, name)).parameters), params, name)
        self.assertEqual(rc.UPDATE_REASON_OF, {'pending_before_analyze': 'values_saved',
                                               'pending_after_analyze': 'assessment_off_context',
                                               'a21': 'reconciled_unknown'})
        self.assertEqual(set(rc.UPDATE_REASON_OF.values()), set(install.UNDO_PENDING_REASONS))
        self.assertEqual(rc.SCHEMA, 'cpt-studio-d15-rollback@2')


if __name__ == '__main__':
    unittest.main()
