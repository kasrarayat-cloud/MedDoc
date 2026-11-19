"""Unit tests for ops/rollback_check.py, the D15 rollback runtime test (design/FINAL.md 12.3; design/ADJUDICATION.md
P-1): the comparison it judges by, and the refusals it makes before anything runs. No Docker or network: the one-shot
transport is replaced where a test reaches it. AMENDMENT-2 8.5 [R:replay-R6]: the record kinds' SQL also runs on a
disposable PostgreSQL the Fable candidate's rows fill, when one is configured the way CI configures it
(test_install_harness2's DatabaseTest); without one those tests are skipped, never passed.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v
"""
import base64
import contextlib
import hashlib
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
        # DECISIONS D294 F1: the declined hold, which only a paid or nondeterministic provider outcome makes, is
        # counted and reported, never required (ops/test_r2r_records.py)
        self.assertEqual(problems, ["fable_run: not counted ('RuntimeError: psql failed')"])
        self.assertEqual(rc.scenario_reported({**found, 'declined_hold': 0}, rc.SCENARIO_V2 + rc.SCENARIO_V3),
                         {'declined_hold': 0})
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


class ScenarioRoundR3(FableRows):
    """Round r3 (DECISIONS D320, D322 (5)): a candidate whose installer knows the question stage is judged on its
    records - a queued or running question job, a question run, a code an established answer released - each SQL
    counting on a database that holds them, and none of them judged for a candidate without the stage."""

    def counts(self, kinds):
        from django.db import connection
        found = {}
        with connection.cursor() as cursor:
            for key, _, statement in kinds:
                cursor.execute(statement)
                found[key] = cursor.fetchone()[0]
        return found

    def test_this_revisions_installer_is_a_question_candidate_and_an_earlier_one_is_not(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import install
        self.assertTrue(rc.question_candidate(install))
        self.assertFalse(rc.question_candidate(SimpleNamespace(READING_STAGE_KINDS=('interpret', 'appraise'))))
        self.assertFalse(rc.question_candidate(SimpleNamespace()))
        self.assertEqual(rc.QUESTION_KIND, install.QUESTION_KIND)
        self.assertEqual([key for key, _, _ in rc.SCENARIO_R3], ['queued_question', 'question_run', 'question_released'])
        for statement in (sql for _, _, sql in rc.SCENARIO_R3):
            self.assertTrue(statement.startswith('select count(*) from studio_'), statement)

    def test_each_question_record_kind_counts_on_a_database_that_holds_it(self):
        self.fill_d15()
        found = self.counts(rc.SCENARIO_R3)
        self.assertEqual(found, {'queued_question': 1, 'question_run': 1, 'question_released': 1})
        self.assertEqual(rc.assertion_7({**self.counts(rc.SCENARIO_V2 + rc.SCENARIO_V3), **found}, True, True, True),
                         ([], {'declined_hold': 1}))

    def test_a_released_code_needs_a_supported_question_naming_it(self):
        """The boundary: the same rows with the question unresolved, or naming another code, count no released code
        (the inventory's events rewritten in SQL: the model refuses an update of its immutable rows)."""
        from django.db import connection
        from studio import models
        self.fill_d15()
        inventory = models.EventInventory.objects.exclude(events={}).get()
        for events in ({'questions': [{'result': 'unresolved', 'witnesses': [{'code': '45378'}]}]},
                       {'questions': [{'result': 'supported', 'witnesses': [{'code': '45385'}]}]}):
            with self.subTest(events=events):
                with connection.cursor() as cursor:
                    cursor.execute('update studio_eventinventory set events = %s::jsonb where id = %s',
                                   [json.dumps(events), inventory.pk])
                self.assertEqual(self.counts(rc.SCENARIO_R3[2:])['question_released'], 0)
                problems, _ = rc.assertion_7({key: 1 for key, _, _ in rc.SCENARIO_V2 + rc.SCENARIO_V3}
                                             | self.counts(rc.SCENARIO_R3), True, True, True)
                self.assertEqual(problems, ['question_released: the run holds no a code an established answer '
                                            'released'])


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


# --- DECISIONS D338 (AMENDMENT-1 9.4 and U17): assertion 2 records the update-pending rows, never fails them ------------
# The D15 run on int7 (d15-r3-20261119T024708Z/d15-c/d15.json, sha256 ca4dd7ed177304a2...; 7 of 8 PASS): assertion 2's 22
# findings, all on the A21 encounter and the one pending after analyze. run_findings() IS d15.json's comparison findings
# (the canonical JSON's sha256 is pinned); previous_views() the previous image's rows of the two as the run rendered them
# (d15-c/out-after); legacy_entry() each encounter's stored legacy state as Check.legacy_rows reads it, its rows as the
# run's candidate rendered the same rows (d15-c/out-before: no decision and no member answer on any row; keys, families,
# reinstatable flags and the review.reinstatement check's status as printed there; the three memberships may review, as
# every customer detail's permissions say). Synthetic test-instance ids and codes only.
A21_ENCOUNTER = '4932708e-3952-4639-93a1-2773f84a4973'  # the close: reconciled_unknown
AFTER_ANALYZE = 'bc47403c-80a5-467d-a70a-b055566d561a'  # the close: assessment_off_context
BEFORE_ANALYZE = '57c110c6-e069-472b-9c1f-9de1aac7f96e'  # the close: values_saved (reverted)
NEW_PATH_ENCOUNTER = 'fb0dd34d-ac68-4218-b893-09f5884e7c89'  # a v2 assessment current
LEGACY_ENCOUNTER = '03c600f4-1602-497c-9fbe-0eb1ba624623'  # legacy, no update
LEGACY_ASSESSMENT = {A21_ENCOUNTER: '528e33f6-4c56-44d4-9ab4-86f187ddaa5d',
                     AFTER_ANALYZE: '389b347e-cdbb-48cd-9931-4a85d04d440d',
                     BEFORE_ANALYZE: '6581282e-52aa-4a82-8165-9ec3fc0f0f29'}
EXCLUDED_99214 = 'd1741fa5-033a-42ea-84e0-6ad7023b7364'  # A21's reinstatable excluded code
V2_PROPOSAL = 'f0e1d2c3-b4a5-4697-8879-6a5b4c3d2e1f'
_ALT = ('informational', 'alternative')
STORED_ROWS = {
    A21_ENCOUNTER: [(EXCLUDED_99214, '99214', 'excluded', 'excluded'),
                    ('8224f81a-0019-4448-9ac5-195cdb2cdc13', 'G8754', 'excluded', 'excluded'),
                    ('bc265da4-99f3-4e0b-bca2-d77661a656a2', 'G8752', 'excluded', 'excluded'),
                    ('aab4f9f7-19b3-4318-a0e2-d13527fd7092', 'G8417', *_ALT),
                    ('894c8e08-c4c5-4c6f-ba1b-575b9324f06a', '99204', *_ALT),
                    ('c4cdf197-5cf3-4a95-ae5e-bd14266e8f94', '99213', *_ALT),
                    ('dfc44d66-c9a6-4e60-a266-57d26d31388b', '99203', *_ALT),
                    ('e3b62ad8-643a-414e-87e1-851de2856a16', '99212', *_ALT),
                    ('52d24616-e442-4784-ab77-3a7d1bced12f', 'G8753', *_ALT),
                    ('22cd60fb-e992-43fb-a8ba-267f9c95dac9', 'G8420', *_ALT),
                    ('9a37adce-abde-4eb6-9d15-64111bf07b64', '43249', *_ALT)],
    AFTER_ANALYZE: [('8f9a8aee-9f31-4026-b2b1-cd16632304ae', '82272', *_ALT),
                    ('86b5341e-0281-4f8a-a5cf-91f564b39828', 'G9903', *_ALT),
                    ('8ca446f7-9f24-49c6-ac47-0bc518b39ffb', '99214', *_ALT),
                    ('0994b6ac-7e9a-4e67-b2f8-2d77b65db012', '1036F', *_ALT),
                    ('34f0ee61-97c3-4cbf-85c1-e1de666a0b21', 'J2405', *_ALT),
                    ('5921442f-1809-474f-be33-0012b795d8cc', '99213', *_ALT),
                    ('dcfd6fea-8e70-4a8e-9aef-580d55f0abb9', '99204', *_ALT),
                    ('d75f8947-f8ea-49b2-8c28-c78feedbd11b', '99284', *_ALT),
                    ('4a8771e1-e035-4e5c-80e9-d5773035e4bc', 'S0119', *_ALT),
                    ('2f620e4d-28be-4209-94a8-ea5296eef1c4', 'G9902', *_ALT),
                    ('6574a2a5-c34f-49d7-b379-ef8f8ef1f3ff', '99203', *_ALT)],
    BEFORE_ANALYZE: [],
}
# each stored row's key and family (d15-c/out-before's operator detail), in STORED_ROWS' order; A21's 99214 is the one
# reinstatable row, its review.reinstatement check passing
RUN_KEYS = {A21_ENCOUNTER: ['exc:0', 'exc:1', 'exc:2'] + [f'alt:{i}' for i in range(8)],
            AFTER_ANALYZE: [f'alt:{i}' for i in range(11)]}
RUN_FAMILIES = {'99214': 'gi.office_em', '99204': 'gi.office_em', '99213': 'gi.office_em', '99203': 'gi.office_em',
                '99212': 'gi.office_em', '43249': 'gi.egd', '99284': 'gi.em_other'}
CLOSE_PENDING = {A21_ENCOUNTER: ['reconciled_unknown'], BEFORE_ANALYZE: ['values_saved'],
                 AFTER_ANALYZE: ['assessment_off_context']}
RUN_FINDINGS_SHA256 = '8f43d318759f1be98a64163d5cc3297405d3c734adbcd2d0501551f01e72b2cb'
DETAIL_VIEWS = ('customer.detail[1]', 'customer.detail[2]', 'customer.detail[3]', 'member.detail[1]', 'member.detail[2]',
                'member.detail[3]', 'operator.detail')
MEMBERSHIPS = {'1': True, '2': True, '3': True}  # the run's workspace: three memberships, each may review


def _offer(pk, where, offer='readiness.draft'):
    return {'encounter': pk, 'finding': 'offer_not_made_before', 'new_path': pk == AFTER_ANALYZE, 'offer': offer,
            'where': where}


def _row_finding(kind, where, before, after='excluded', actions=('confirm', 'reinstate'), pk=A21_ENCOUNTER,
                 proposal=EXCLUDED_99214, code_='99214'):
    found = {'after': after, 'before': before, 'code': code_, 'encounter': pk, 'finding': kind,
             'new_path': pk == AFTER_ANALYZE, 'proposal': proposal, 'where': where}
    if actions is not None:
        found['actions'] = list(actions)
    return found


def run_findings():
    """The D15 run's 22 assertion-2 findings, in d15.json's order."""
    out = []
    for i in (1, 2, 3):
        out += [_offer(A21_ENCOUNTER, f'customer.detail[{i}]'),
                _row_finding('listed_only_after', f'customer.detail[{i}]', None)]
    for i in (1, 2, 3):
        out += [_offer(A21_ENCOUNTER, f'member.detail[{i}]'),
                _row_finding('action_not_allowed_before', f'member.detail[{i}]', 'excluded')]
    out += [_offer(A21_ENCOUNTER, 'operator.detail'), _offer(A21_ENCOUNTER, 'readiness.customer', 'draft')]
    out += [_offer(AFTER_ANALYZE, where) for where in DETAIL_VIEWS] + [_offer(AFTER_ANALYZE, 'readiness.customer', 'draft')]
    return out


def stored_row(status, bucket, *, code='43239', family='gi.egd', key='k0', reinstatable=False, clear=False, marker=None,
               open_facts=()):
    """One proposal of Check.legacy_rows' entry: its stored status and bucket, reinstatable flag, code, family, key,
    whether its review.reinstatement check passes, the engine's answered marker (fact, value) and its open
    proposal-scoped questions [fact, family]."""
    return {'status': status, 'bucket': bucket, 'reinstatable': reinstatable, 'code': code, 'family': family, 'key': key,
            'reinstatement_clear': clear, 'answered_away': marker is not None,
            'answered_fact': marker[0] if marker else '', 'answered_value': marker[1] if marker else '',
            'open_facts': [list(item) for item in open_facts]}


def legacy_entry(pk, **change):
    """Check.legacy_rows' entry for ``pk``: its stored legacy state - no decision, no member answer."""
    rows = {}
    for (pid, code_, status, bucket), key in zip(STORED_ROWS.get(pk, ()), RUN_KEYS.get(pk, ())):
        rows[pid] = stored_row(status, bucket, code=code_, family=RUN_FAMILIES.get(code_, 'gi.unsupported'), key=key,
                               reinstatable=pid == EXCLUDED_99214, clear=pid == EXCLUDED_99214)
    entry = {'assessment': LEGACY_ASSESSMENT.get(pk), 'engine_version': 'cpt-studio-validation@3', 'event_inventory': False,
             'revision_current': True, 'final': True, 'proposals': rows, 'v2_proposals': [], 'decisions': [],
             'answers': [], 'memberships': dict(MEMBERSHIPS)}
    entry.update(change)
    return entry


def legacy_rows_of_the_run():
    return {A21_ENCOUNTER: legacy_entry(A21_ENCOUNTER), AFTER_ANALYZE: legacy_entry(AFTER_ANALYZE),
            BEFORE_ANALYZE: legacy_entry(BEFORE_ANALYZE, engine_version='cpt-studio-validation@4')}


def previous_views(pk):
    """The previous image's views of ``pk`` as the run rendered them (d15-c/out-after): what assertion 2 reads."""
    member_actions = {EXCLUDED_99214: ['reinstate', 'confirm']} if pk == A21_ENCOUNTER else {}

    def rows(actions):
        return [{'id': pid, 'code': code_, 'status': status, 'bucket': bucket, 'allowed_actions': list(actions.get(pid, ()))}
                for pid, code_, status, bucket in STORED_ROWS[pk]]
    codes = ([{'id': EXCLUDED_99214, 'code': '99214', 'status': 'excluded', 'allowed_actions': ['reinstate', 'confirm']}]
             if pk == A21_ENCOUNTER else [])
    views = {'state': {'stored': 'provider_not_run', 'derived': 'provider_not_run'}, 'list.customer_row': {'state': 'failed'},
             'readiness': {'customer': {'draft': True, 'approved': False}, 'review': {'draft': True, 'reviewed': False}}}
    for i in (1, 2, 3):
        views[f'customer.detail[{i}]'] = customer('failed', [dict(row) for row in codes])
        views[f'member.detail[{i}]'] = {'assessment': {'id': LEGACY_ASSESSMENT[pk], 'proposals': rows(member_actions)},
                                        'readiness': {'draft': True, 'reviewed': False}}
    views['operator.detail'] = {'assessment': {'id': LEGACY_ASSESSMENT[pk], 'proposals': rows({})},
                                'readiness': {'draft': True, 'reviewed': False}}
    return views


class D338Case(unittest.TestCase):
    """assertion_2 over the run's comparison, close, note, stored rows and previous views, each replaceable."""

    def judge(self, findings=None, named=None, note=None, legacy=None, views=None, encounters=102):
        comparison = {'encounters': encounters, 'new_path': 13,
                      'findings': run_findings() if findings is None else findings}
        named = {pk: list(reasons) for pk, reasons in CLOSE_PENDING.items()} if named is None else named
        note = {'update_pending': sorted(CLOSE_PENDING)} if note is None else note
        legacy = legacy_rows_of_the_run() if legacy is None else legacy
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)} if views is None else views
        return rc.assertion_2(comparison, named, note, legacy, views)

    def failing_on(self, problems, pk):
        return [problem for problem in problems if problem.startswith(pk)]

    def assert_encounter_fails(self, problems, measurement, pk, count, why):
        """Every finding on ``pk`` (``count``) fails, each saying ``why``; nothing on it is recorded."""
        mine = self.failing_on(problems, pk)
        self.assertEqual(len(mine), count, problems)
        for problem in mine:
            self.assertIn(' - update_pending, not recorded as U17: ', problem)
            self.assertIn(why, problem)
        self.assertFalse([f for f in measurement['recorded'] if f['encounter'] == pk])
        self.assertEqual((measurement['encounters'][pk]['recorded'], measurement['encounters'][pk]['failing']), (0, count))

    def assert_recorded(self, measurement, pk, count):
        self.assertEqual(len([f for f in measurement['recorded'] if f['encounter'] == pk]), count)
        self.assertEqual(measurement['encounters'][pk]['not_recorded'], [])


class AssertionTwoRecordsTheRunsUpdatePendingRows(D338Case):
    """DECISIONS D338, test (1): the run's own 22 findings become U17's recorded differences, and assertion 2 has no
    problem left."""

    def test_the_fixture_is_the_runs_own_comparison(self):
        found = run_findings()
        self.assertEqual(hashlib.sha256(json.dumps(found, sort_keys=True).encode()).hexdigest(), RUN_FINDINGS_SHA256)
        self.assertEqual((len(found), {f['encounter'] for f in found}), (22, {A21_ENCOUNTER, AFTER_ANALYZE}))

    def test_the_22_findings_are_recorded_and_no_problem_is_left(self):
        problems, measurement = self.judge()
        self.assertEqual(problems, [])
        self.assertEqual(measurement['recorded'], run_findings())
        self.assert_recorded(measurement, A21_ENCOUNTER, 14)
        self.assert_recorded(measurement, AFTER_ANALYZE, 8)
        self.assertEqual({pk: (entry['reasons'], entry['listed'], entry['assessment'], entry['failing'])
                          for pk, entry in measurement['encounters'].items()},
                         {A21_ENCOUNTER: (['reconciled_unknown'], True, LEGACY_ASSESSMENT[A21_ENCOUNTER], 0),
                          AFTER_ANALYZE: (['assessment_off_context'], True, LEGACY_ASSESSMENT[AFTER_ANALYZE], 0),
                          BEFORE_ANALYZE: (['values_saved'], True, LEGACY_ASSESSMENT[BEFORE_ANALYZE], 0)})
        self.assertIn('values_saved', measurement['encounters'][BEFORE_ANALYZE]['not_recorded'][0])
        self.assertEqual(rc.legacy_shown_problems(previous_views(A21_ENCOUNTER), legacy_entry(A21_ENCOUNTER)), [])
        self.assertEqual(rc.legacy_shown_problems(previous_views(AFTER_ANALYZE), legacy_entry(AFTER_ANALYZE)), [])

    def test_assess_passes_assertion_2_with_the_measurement_in_its_evidence_and_the_summary(self):
        """Check.assess() over the run's comparison: on int7's runner assertion 2 FAILS with the 22 problems."""
        second, summary = self.assessed()
        self.assertEqual((second['assertion'], second['result'], second['problems']), (2, 'PASS', []))
        self.assertEqual(second['evidence']['findings'], 22)
        self.assertEqual(second['evidence']['u17_measurement']['recorded'], run_findings())
        line = next(line for line in summary.splitlines() if 'U17 measurement' in line)
        self.assertIn('22 difference(s) on 4932708e-3952-4639-93a1-2773f84a4973 (reconciled_unknown) 14; '
                      'bc47403c-80a5-467d-a70a-b055566d561a (assessment_off_context) 8', line)
        self.assertIn('nothing recorded on 57c110c6-e069-472b-9c1f-9de1aac7f96e', line)
        self.assertIn('  2. PASS  per proposal the previous image is equal or strictly more held; no new action', summary)
        # the wiring keeps the rule: a named encounter the note does not list fails there too
        second, _ = self.assessed(note={'update_pending': [AFTER_ANALYZE, BEFORE_ANALYZE]})
        self.assertEqual(second['result'], 'FAIL')
        self.assertEqual(len(second['problems']), 14)
        self.assertTrue(all('the switch-back note does not list it' in problem for problem in second['problems']))

    def assessed(self, note=None):
        import tempfile
        out = Path(tempfile.mkdtemp(prefix='d338-'))
        self.addCleanup(lambda: __import__('shutil').rmtree(out, ignore_errors=True))
        check = rc.Check.__new__(rc.Check)
        check.args, check.out, check.lines = SimpleNamespace(db='cptg_d15r3c'), out, []
        check.instance = SimpleNamespace(calls=[])
        check.candidate = {'tag': 'cpt-studio-test:fe6ba4eb0a74', 'revision': 'fe6ba4eb0a74e04e942bf42b0454655ba6e3fcbe'}
        check.previous = {'tag': 'cpt-studio:c2e53f8e7d33', 'revision': 'c2e53f8e7d33732d5badd4ce9b681f274eb5c471'}
        check.v2 = check.fable = check.question = True
        check.declared = {'update': {'pending_before_analyze': [BEFORE_ANALYZE], 'pending_after_analyze': [AFTER_ANALYZE],
                                     'completed': [], 'a21': [A21_ENCOUNTER]}}
        check.views = {'before': {}, 'after': {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}}
        check.record = {'schema': rc.SCHEMA, 'started_at': '2026-11-19T04:20:20+00:00',
                        'switch_back': {'note': note or {'update_pending': sorted(CLOSE_PENDING)},
                                        'update': {'update_pending': CLOSE_PENDING, 'reverted': {},
                                                   'legacy': legacy_rows_of_the_run()}},
                        'comparison': {'encounters': 102, 'new_path': 13, 'findings': run_findings(), 'errors': [],
                                       'per_encounter': {}}}
        with contextlib.redirect_stdout(io.StringIO()):
            check.assess()
        return check.record['assertions'][1], (out / 'D15-SUMMARY.txt').read_text(encoding='utf-8')


class AssertionTwoStillFails(D338Case):
    """DECISIONS D338, test (2): anything else on an update-pending encounter still fails, every other encounter keeps
    "never less held", and nothing changes for an encounter the close or the note does not name."""

    def test_a_v2_proposal_shown_on_a_named_encounter(self):
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[A21_ENCOUNTER]['customer.detail[1]']['codes'].append(
            {'id': V2_PROPOSAL, 'code': '43239', 'status': 'ready', 'allowed_actions': ['approve', 'reject']})
        legacy = legacy_rows_of_the_run()
        legacy[A21_ENCOUNTER]['v2_proposals'] = [V2_PROPOSAL]
        found = run_findings() + [_row_finding('listed_only_after', 'customer.detail[1]', None, 'ready',
                                               ('approve', 'reject'), proposal=V2_PROPOSAL, code_='43239')]
        problems, measurement = self.judge(findings=found, legacy=legacy, views=views)
        self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 15, f'shows {V2_PROPOSAL}, a v2 proposal')
        self.assert_recorded(measurement, AFTER_ANALYZE, 8)
        # the finding alone, its views as stored: still not recorded
        views[A21_ENCOUNTER]['customer.detail[1]']['codes'].pop()
        problems, measurement = self.judge(findings=found, legacy=legacy, views=views)
        self.assertEqual(len(problems), 1)
        self.assertIn(f'shows {V2_PROPOSAL}, a v2 proposal', problems[0])
        self.assert_recorded(measurement, A21_ENCOUNTER, 14)

    def test_a_status_differing_from_the_stored_one(self):
        # the previous image shows a stored excluded row as ready, on a row no finding names
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[A21_ENCOUNTER]['member.detail[2]']['assessment']['proposals'][1]['status'] = 'ready'
        problems, measurement = self.judge(views=views)
        self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14,
                                    "8224f81a-0019-4448-9ac5-195cdb2cdc13 shows status 'ready', stored 'excluded'")
        self.assert_recorded(measurement, AFTER_ANALYZE, 8)
        # the customer page shows the stored excluded code as ready
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[A21_ENCOUNTER]['customer.detail[3]']['codes'][0]['status'] = 'ready'
        problems, measurement = self.judge(views=views)
        self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14,
                                    f"customer.detail[3]: {EXCLUDED_99214} shows status 'ready', stored 'excluded'")
        # the stored row is not what the previous image shows (the stored side)
        legacy = legacy_rows_of_the_run()
        legacy[AFTER_ANALYZE]['proposals']['8f9a8aee-9f31-4026-b2b1-cd16632304ae'] = stored_row(
            'needs_clarification', 'selected', code='82272', family='gi.unsupported', key='alt:0')
        problems, measurement = self.judge(legacy=legacy)
        # D339: a stored selected code is one the customer page numbers, so its absence there is named first
        self.assert_encounter_fails(problems, measurement, AFTER_ANALYZE, 8,
                                    "does not number ['8f9a8aee-9f31-4026-b2b1-cd16632304ae'], which the legacy release "
                                    'numbers')
        self.assertTrue(any("member.detail[1]: 8f9a8aee-9f31-4026-b2b1-cd16632304ae shows status 'informational', stored "
                            "'needs_clarification'" in problem
                            for problem in measurement['encounters'][AFTER_ANALYZE]['not_recorded']))
        self.assert_recorded(measurement, A21_ENCOUNTER, 14)
        # a member's row printing another bucket than the stored one
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[A21_ENCOUNTER]['operator.detail']['assessment']['proposals'][2]['bucket'] = 'selected'
        problems, measurement = self.judge(views=views)
        self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14,
                                    "bc265da4-99f3-4e0b-bca2-d77661a656a2 shows bucket 'selected', stored 'excluded'")
        # a finding whose own status is not the stored one, its views as stored
        found = run_findings() + [_row_finding('toward_release', 'member.detail[1]', 'excluded', 'ready', None)]
        problems, measurement = self.judge(findings=found)
        self.assertEqual(len(problems), 1)
        self.assertIn(f"member.detail[1]: {EXCLUDED_99214} shows status 'ready', stored 'excluded'", problems[0])
        self.assert_recorded(measurement, A21_ENCOUNTER, 14)

    def test_a_proposal_not_of_its_legacy_assessment(self):
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[AFTER_ANALYZE]['member.detail[1]']['assessment']['proposals'].append(
            {'id': EXCLUDED_99214, 'code': '99214', 'status': 'excluded', 'bucket': 'excluded', 'allowed_actions': []})
        problems, measurement = self.judge(views=views)
        self.assert_encounter_fails(problems, measurement, AFTER_ANALYZE, 8,
                                    f'shows {EXCLUDED_99214}, not a proposal of its legacy assessment')
        self.assert_recorded(measurement, A21_ENCOUNTER, 14)
        # another assessment shown in its place
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[AFTER_ANALYZE]['operator.detail']['assessment']['id'] = LEGACY_ASSESSMENT[A21_ENCOUNTER]
        problems, measurement = self.judge(views=views)
        self.assert_encounter_fails(problems, measurement, AFTER_ANALYZE, 8,
                                    f'shows assessment {LEGACY_ASSESSMENT[A21_ENCOUNTER]}, not its legacy assessment')
        # a row difference whose proposal is not of the legacy assessment
        found = run_findings() + [_row_finding('listed_only_after', 'customer.detail[2]', None, pk=AFTER_ANALYZE)]
        problems, measurement = self.judge(findings=found)
        self.assertEqual(len(problems), 1)
        self.assertIn(f'shows {EXCLUDED_99214}, not a proposal of its legacy assessment', problems[0])
        self.assert_recorded(measurement, AFTER_ANALYZE, 8)

    def test_an_action_the_legacy_release_does_not_offer(self):
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[AFTER_ANALYZE]['member.detail[3]']['assessment']['proposals'][0]['allowed_actions'] = ['approve']
        problems, measurement = self.judge(views=views)
        self.assert_encounter_fails(problems, measurement, AFTER_ANALYZE, 8,
                                    "allows ['approve'], which the legacy release does not offer on a stored informational "
                                    'alternative row')
        self.assert_recorded(measurement, A21_ENCOUNTER, 14)
        # an action no legacy release offers at all, in the views and in the finding
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
        views[A21_ENCOUNTER]['member.detail[1]']['assessment']['proposals'][0]['allowed_actions'] = [
            'reinstate', 'confirm', 'answer']
        found = [dict(f, actions=['answer', 'confirm', 'reinstate']) if f.get('proposal') and f['where'] == 'member.detail[1]'
                 else f for f in run_findings()]
        problems, measurement = self.judge(findings=found, views=views)
        self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14, "allows ['answer']")
        # the finding's own new action, its views as stored
        found = run_findings() + [_row_finding('action_not_allowed_before', 'member.detail[2]', 'excluded',
                                               actions=('answer',))]
        problems, measurement = self.judge(findings=found)
        self.assertEqual(len(problems), 1)
        self.assertIn("allows ['answer']", problems[0])

    def test_a_named_encounter_the_note_does_not_list(self):
        problems, measurement = self.judge(note={'update_pending': [AFTER_ANALYZE, BEFORE_ANALYZE]})
        self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14, 'the switch-back note does not list it')
        self.assertFalse(measurement['encounters'][A21_ENCOUNTER]['listed'])
        self.assert_recorded(measurement, AFTER_ANALYZE, 8)
        problems, measurement = self.judge(note={})  # a note that lists nothing
        self.assertEqual(len(problems), 22)
        self.assertEqual(measurement['recorded'], [])

    def test_a_listed_encounter_the_close_did_not_name(self):
        named = {pk: reasons for pk, reasons in CLOSE_PENDING.items() if pk != AFTER_ANALYZE}
        problems, measurement = self.judge(named=named)
        self.assert_encounter_fails(problems, measurement, AFTER_ANALYZE, 8, 'the close did not name it update_pending')
        self.assertIsNone(measurement['encounters'][AFTER_ANALYZE]['reasons'])
        self.assert_recorded(measurement, A21_ENCOUNTER, 14)
        problems, _ = self.judge(named={})
        self.assertEqual(len(problems), 22)

    def test_a_difference_on_a_new_path_encounter(self):
        found = [_offer(NEW_PATH_ENCOUNTER, 'customer.detail[1]'),
                 _row_finding('toward_release', 'member.detail[1]', 'needs_clarification', 'ready', None,
                              pk=NEW_PATH_ENCOUNTER, proposal=V2_PROPOSAL, code_='45378')]
        # not named: exactly as before
        problems, measurement = self.judge(findings=run_findings() + found)
        self.assertEqual(problems, [rc.finding_text(finding) for finding in found])
        self.assertNotIn(NEW_PATH_ENCOUNTER, measurement['encounters'])
        self.assertEqual(problems[0], 'fb0dd34d-ac68-4218-b893-09f5884e7c89 customer.detail[1]: offer_not_made_before '
                                      '(None -> None, readiness.draft)')
        # named and listed (a v2 encounter with a pending update), the previous image reading its v2 assessment
        named = {**CLOSE_PENDING, NEW_PATH_ENCOUNTER: ['assessment_off_context']}
        note = {'update_pending': sorted(named)}
        v2_views = {'member.detail[1]': {'assessment': {'id': 'a2a2a2a2-0000-4000-8000-000000000001', 'proposals': [
            {'id': V2_PROPOSAL, 'status': 'ready', 'bucket': 'selected', 'allowed_actions': ['approve', 'reject']}]}}}
        v2_rows = {V2_PROPOSAL: stored_row('ready', 'selected', code='45378', family='gi.colonoscopy', key='sel:0')}
        for entry in (legacy_entry(NEW_PATH_ENCOUNTER, assessment='a2a2a2a2-0000-4000-8000-000000000001',
                                   engine_version='cpt-studio-events@3', event_inventory=True, proposals=v2_rows,
                                   v2_proposals=[V2_PROPOSAL]),
                      legacy_entry(NEW_PATH_ENCOUNTER, assessment='a2a2a2a2-0000-4000-8000-000000000001',
                                   engine_version='cpt-studio-validation@3', event_inventory=True, proposals=v2_rows,
                                   v2_proposals=[V2_PROPOSAL])):
            with self.subTest(engine=entry['engine_version']):
                views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)} | {NEW_PATH_ENCOUNTER: v2_views}
                problems, measurement = self.judge(findings=run_findings() + found, named=named, note=note,
                                                   legacy={**legacy_rows_of_the_run(), NEW_PATH_ENCOUNTER: entry},
                                                   views=views)
                self.assert_encounter_fails(problems, measurement, NEW_PATH_ENCOUNTER, 2, 'is not a legacy assessment')
                self.assertEqual(len(measurement['recorded']), 22)

    def test_a_difference_on_a_legacy_encounter_with_no_pending_update(self):
        found = [_row_finding('listed_only_after', 'customer.detail[1]', None, pk=LEGACY_ENCOUNTER),
                 _row_finding('action_not_allowed_before', 'member.detail[1]', 'excluded', pk=LEGACY_ENCOUNTER),
                 _offer(LEGACY_ENCOUNTER, 'readiness.customer', 'draft')]
        problems, measurement = self.judge(findings=run_findings() + found,
                                           legacy={**legacy_rows_of_the_run(), LEGACY_ENCOUNTER: legacy_entry(A21_ENCOUNTER)},
                                           views={pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)}
                                           | {LEGACY_ENCOUNTER: previous_views(A21_ENCOUNTER)})
        self.assertEqual(problems, [rc.finding_text(finding) for finding in found])  # worded exactly as int7's runner
        self.assertEqual(problems[1], "03c600f4-1602-497c-9fbe-0eb1ba624623 member.detail[1]: action_not_allowed_before "
                                      "(excluded -> excluded, ['confirm', 'reinstate'])")
        self.assertNotIn(LEGACY_ENCOUNTER, measurement['encounters'])
        self.assertEqual(len(measurement['recorded']), 22)
        problems, measurement = self.judge(findings=found, named={}, note={}, legacy={}, views={}, encounters=0)
        self.assertEqual(problems, [rc.finding_text(finding) for finding in found] + ['no encounter was compared'])
        self.assertEqual(measurement, {'recorded': [], 'encounters': {}})

    def test_another_offer_a_state_or_an_unlisted_row_on_a_recorded_encounter(self):
        extra = [_offer(A21_ENCOUNTER, 'customer.detail[1]', 'readiness.approved'),
                 _offer(A21_ENCOUNTER, 'member.detail[1]', 'readiness.reviewed'),
                 _offer(A21_ENCOUNTER, 'readiness.review', 'reviewed'),
                 _offer(A21_ENCOUNTER, 'readiness.customer', 'approved'),
                 _offer(AFTER_ANALYZE, 'customer.detail[2]', 'progress.can_resume'),
                 _offer(AFTER_ANALYZE, 'customer.detail[2]', 'recheck.can_request'),
                 _offer(AFTER_ANALYZE, 'readiness.review', 'readiness.draft'),
                 {'encounter': A21_ENCOUNTER, 'where': 'customer.detail[1]', 'finding': 'state_toward_release',
                  'before': 'failed', 'after': 'ready'},
                 {'encounter': A21_ENCOUNTER, 'where': 'list.customer_row', 'finding': 'state_toward_release',
                  'before': 'failed', 'after': 'ready'},
                 {'encounter': AFTER_ANALYZE, 'where': 'state.derived', 'finding': 'toward_release',
                  'before': 'provider_not_run', 'after': 'reviewed'},
                 _row_finding('not_listed_after', 'member.detail[1]', 'excluded', None, None)]
        problems, measurement = self.judge(findings=run_findings() + extra)
        self.assertEqual(len(problems), len(extra))
        for problem, finding in zip(problems, extra):
            self.assertTrue(problem.startswith(rc.finding_text(finding) + ' - update_pending, not recorded as U17: '),
                            problem)
        self.assertIn("readiness.approved on customer.detail[1] is not the legacy release's draft offer", problems[0])
        self.assertIn('state_toward_release on customer.detail[1] is not a difference U17 records', problems[7])
        self.assertIn('not_listed_after on member.detail[1] is not a difference U17 records', problems[10])
        self.assertEqual(measurement['recorded'], run_findings())

    def test_an_encounter_named_for_values_saved_alone_keeps_never_less_held(self):
        found = [_offer(BEFORE_ANALYZE, 'customer.detail[1]'),
                 _row_finding('listed_only_after', 'customer.detail[1]', None, pk=BEFORE_ANALYZE)]
        legacy = legacy_rows_of_the_run()
        legacy[BEFORE_ANALYZE] = legacy_entry(A21_ENCOUNTER)  # its views as stored, even so
        views = {pk: previous_views(pk) for pk in (A21_ENCOUNTER, AFTER_ANALYZE)} | {
            BEFORE_ANALYZE: previous_views(A21_ENCOUNTER)}
        problems, measurement = self.judge(findings=run_findings() + found, legacy=legacy, views=views)
        self.assert_encounter_fails(problems, measurement, BEFORE_ANALYZE, 2,
                                    "the close named it update_pending ['values_saved'], neither of "
                                    "['assessment_off_context', 'reconciled_unknown']")
        self.assertEqual(len(measurement['recorded']), 22)
        # named for values_saved AND a reading owed after analyze: recorded as the after-analyze row it is
        named = {**CLOSE_PENDING, AFTER_ANALYZE: ['values_saved', 'assessment_off_context']}
        problems, measurement = self.judge(named=named)
        self.assertEqual(problems, [])
        self.assert_recorded(measurement, AFTER_ANALYZE, 8)

    def test_never_recorded_vacuously(self):
        cases = (
            ('the previous image rendered no member or operator detail of it',  # customer details alone
             {A21_ENCOUNTER: {name: view for name, view in previous_views(A21_ENCOUNTER).items()
                              if not name.startswith(('member.detail[', 'operator.detail'))}}),
            ('the previous image rendered no member or operator detail of it', {}),  # no view of it at all
            ("member.detail[1]: the previous image's view could not be read",
             {A21_ENCOUNTER: {**previous_views(A21_ENCOUNTER), 'member.detail[1]': {'__error__': 'KeyError: x'}}}),
            ('member.detail[2]: shows no assessment',
             {A21_ENCOUNTER: {**previous_views(A21_ENCOUNTER), 'member.detail[2]': {'assessment': None}}}),
        )
        for why, views in cases:
            with self.subTest(why=why, views=sorted(views)):
                problems, measurement = self.judge(views={AFTER_ANALYZE: previous_views(AFTER_ANALYZE), **views})
                self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14, why)
                self.assert_recorded(measurement, AFTER_ANALYZE, 8)
        missing = previous_views(A21_ENCOUNTER)
        missing['operator.detail']['assessment']['proposals'].pop()
        problems, measurement = self.judge(views={AFTER_ANALYZE: previous_views(AFTER_ANALYZE), A21_ENCOUNTER: missing})
        self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14,
                                    "operator.detail: does not show ['9a37adce-abde-4eb6-9d15-64111bf07b64']")
        for why, entry in (('its current assessment was not read', None),
                           ('it has no current assessment', legacy_entry(A21_ENCOUNTER, assessment=None)),
                           ('is not a legacy assessment', legacy_entry(A21_ENCOUNTER, event_inventory=None)),
                           ("its legacy assessment's proposals were not read", legacy_entry(A21_ENCOUNTER, proposals=None))):
            with self.subTest(why=why):
                legacy = legacy_rows_of_the_run()
                legacy[A21_ENCOUNTER] = entry
                problems, measurement = self.judge(legacy=legacy)
                self.assert_encounter_fails(problems, measurement, A21_ENCOUNTER, 14, why)

    def test_the_literals_are_the_servers(self):
        """D338's reasons are the installer's; D339's literals are this tree's (models.py, validation/questions.py,
        validation/review_view.py, validation/engine.py, participants/__init__.py) - the runner imports none of them."""
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import install
        studio = APP_ROOT / 'studio'
        self.assertEqual(rc.RECORDED_REASONS, ('assessment_off_context', 'reconciled_unknown'))
        self.assertTrue(set(rc.RECORDED_REASONS) <= set(install.UNDO_PENDING_REASONS))
        self.assertNotIn(rc.UPDATE_REASON_OF['pending_before_analyze'], rc.RECORDED_REASONS)
        decision = module_constants(studio / 'models.py', ('APPROVE', 'REJECT', 'REINSTATE', 'REVOKE', 'CONFIRM'),
                                    within='Decision')
        self.assertEqual((rc.APPROVE, rc.REJECT, rc.REINSTATE, rc.REVOKE, rc.CONFIRM),
                         tuple(decision[name] for name in ('APPROVE', 'REJECT', 'REINSTATE', 'REVOKE', 'CONFIRM')))
        proposal = module_constants(studio / 'models.py', ('SELECTED', 'EXCLUDED', 'READY', 'NEEDS_CLARIFICATION',
                                                           'STATUS_EXCLUDED'), within='Proposal')
        self.assertEqual((rc.SELECTED, rc.EXCLUDED, rc.READY, rc.NEEDS_CLARIFICATION, rc.STATUS_EXCLUDED),
                         tuple(proposal[name] for name in ('SELECTED', 'EXCLUDED', 'READY', 'NEEDS_CLARIFICATION',
                                                           'STATUS_EXCLUDED')))
        membership = module_constants(studio / 'models.py', ('OWNER', 'REVIEWER'), within='Membership')
        self.assertEqual(rc.REVIEWER_ROLES, (membership['OWNER'], membership['REVIEWER']))
        questions = module_constants(studio / 'validation' / 'questions.py', ('UNAVAILABLE', 'KEY_BOUND_FACTS'))
        self.assertEqual((rc.UNAVAILABLE_ANSWERS, rc.KEY_BOUND_FACTS), (questions['UNAVAILABLE'],
                                                                         questions['KEY_BOUND_FACTS']))
        overlay = module_constants(studio / 'validation' / 'review_view.py', ('BASE_FACT', 'SEPARATE_EM_FACT',
                                                                              'REINSTATEMENT_CHECK'))
        self.assertEqual((rc.BASE_FACT, rc.SEPARATE_EM_FACT, rc.REINSTATEMENT_CHECK),
                         (overlay['BASE_FACT'], overlay['SEPARATE_EM_FACT'], overlay['REINSTATEMENT_CHECK']))
        self.assertEqual(rc.COMPETING_FACT, module_constants(studio / 'validation' / 'engine.py',
                                                             ('COMPETING_FACT',))['COMPETING_FACT'])
        self.assertEqual(rc.LEGACY_PARTICIPANTS, module_constants(studio / 'participants' / '__init__.py',
                                                                  ('PARTICIPANTS',))['PARTICIPANTS'])
        self.assertTrue(set(rc.KEY_BOUND_FACTS) <= {rc.BASE_FACT, rc.SEPARATE_EM_FACT})
        self.assertTrue(all(engine.startswith(rc.V2_ENGINE_PREFIX) for engine in rc.V2_ENGINES))
        self.assertFalse(hasattr(rc, 'LEGACY_ACTIONS') or hasattr(rc, 'CUSTOMER_STATUS_OF'))  # no union, no status table

    def test_the_summary_line(self):
        _, measurement = self.judge()
        self.assertEqual(rc.u17_summary(measurement).split(': ', 1)[0], 'U17 measurement (DECISIONS D338, D339; recorded, '
                                                                       'never a problem)')
        self.assertIn('22 difference(s) on ', rc.u17_summary(measurement))
        self.assertEqual(rc.u17_summary({'recorded': [], 'encounters': {}}),
                         'U17 measurement (DECISIONS D338, D339; recorded, never a problem): 0 difference(s)')
        self.assertEqual(rc.u17_summary(None), rc.u17_summary({}))


# --- DECISIONS D339: "as stored" is what c2e53f8e computes from the stored legacy state --------------------------------
# DECIDED is a legacy encounter pending after analyze whose legacy assessment carries every decision kind and a member's
# answer, rendered as c2e53f8e renders that stored state (the previous image's own rows: customer_api._status and
# code_rows on the customer page, the overlay's status on a member's and the operator's detail, review._allowed's actions,
# none for the operator's read-only access), and compared with the candidate as AMENDMENT-1 9.4 and U10 state it reads
# them while the reading is owed: the same codes deciding nothing, no draft offer. The 03c600f4 rows are D338R-1's input
# (d15-c/out-after: 46221 approved by an agent with ['revoke'], eleven alternatives). Synthetic.
DECIDED = 'dddd0339-0000-4000-8000-000000000001'
DECIDED_ASSESSMENT = 'dddd0339-0000-4000-8000-0000000000a1'
OTHER_ASSESSMENT = 'dddd0339-0000-4000-8000-0000000000a0'  # an older legacy assessment of the same encounter
D339_ROWS = {  # id: (code, stored row, the customer page's status or None (not numbered), the overlay's status)
    'dddd0339-0000-4000-8000-000000000101': ('45378', stored_row('ready', 'selected', code='45378',
                                                                 family='gi.colonoscopy', key='sel:0'),
                                             'ready', 'ready'),
    'dddd0339-0000-4000-8000-000000000102': ('45380', stored_row('ready', 'selected', code='45380',
                                                                 family='gi.colonoscopy', key='sel:1'),
                                             'approved', 'ready'),
    'dddd0339-0000-4000-8000-000000000103': ('45385', stored_row('ready', 'selected', code='45385',
                                                                 family='gi.colonoscopy', key='sel:2'),
                                             'excluded', 'ready'),
    'dddd0339-0000-4000-8000-000000000104': ('43239', stored_row('excluded', 'excluded', code='43239', family='gi.egd',
                                                                 key='exc:0', reinstatable=True),
                                             'excluded', 'excluded'),
    'dddd0339-0000-4000-8000-000000000105': ('43249', stored_row('excluded', 'excluded', code='43249', family='gi.egd',
                                                                 key='exc:1', reinstatable=True, clear=True),
                                             'ready', 'excluded'),
    'dddd0339-0000-4000-8000-000000000106': ('43251', stored_row('excluded', 'excluded', code='43251', family='gi.egd',
                                                                 key='exc:2', reinstatable=True),
                                             'needs_detail', 'needs_clarification'),
    'dddd0339-0000-4000-8000-000000000107': ('45381', stored_row('needs_clarification', 'selected', code='45381',
                                                                 family='gi.colonoscopy', key='sel:3',
                                                                 open_facts=[('extent', 'gi.colonoscopy')]),
                                             'excluded', 'excluded'),
    'dddd0339-0000-4000-8000-000000000108': ('45390', stored_row('excluded', 'excluded', code='45390',
                                                                 family='gi.colonoscopy', key='exc:3',
                                                                 marker=('extent', 'not_documented')),
                                             'excluded', 'excluded'),
    'dddd0339-0000-4000-8000-000000000109': ('G8754', stored_row('excluded', 'excluded', code='G8754',
                                                                 family='gi.unsupported', key='exc:4'),
                                             None, 'excluded'),
    'dddd0339-0000-4000-8000-000000000110': ('99213', stored_row('informational', 'alternative', code='99213',
                                                                 family='gi.office_em', key='alt:0'),
                                             None, 'informational'),
}
R_UNDECIDED, R_APPROVE, R_REJECT, R_CONFIRM, R_REINSTATE_READY, R_REINSTATE_DETAIL, R_ANSWERED, R_MARKER, R_PLAIN, R_ALT = (
    sorted(D339_ROWS))
# what the previous image offers each viewer on each row (c2e53f8e review._allowed): every member may review, the
# operator's read-only access may not
D339_ACTIONS = {R_UNDECIDED: ['approve', 'reject'], R_APPROVE: ['revoke'], R_REJECT: ['revoke'], R_CONFIRM: ['revoke'],
                R_REINSTATE_READY: ['approve', 'reject', 'revoke'], R_REINSTATE_DETAIL: ['reject', 'revoke'],
                R_ANSWERED: [], R_MARKER: [], R_PLAIN: [], R_ALT: []}


def _decision(pk, proposal, action, sequence, *, assessment=DECIDED_ASSESSMENT, carried_from=None, invalidated=False):
    return {'id': pk, 'proposal': proposal, 'assessment': assessment, 'action': action, 'sequence': sequence,
            'carried_from': carried_from, 'invalidated': invalidated}


def _answer(pk, code_, fact, *, family='gi.colonoscopy', value='not_documented', fingerprinted=False, read=False,
            revoked=False):
    return {'id': pk, 'code': code_, 'family': family, 'fact': fact, 'value': value, 'fingerprinted': fingerprinted,
            'read': read, 'revoked': revoked}


def decided_entry(**change):
    """DECIDED's stored legacy state (Check.legacy_rows): an approval revoked and given again, a rejection, a confirmed
    exclusion, two reinstatements (one whose review.reinstatement check passes, one whose does not), a member's answer
    that leaves 45381's documented extent unavailable (no fingerprint: the earlier form, bound by its key), the engine's
    answered marker on 45390, and a withdrawn answer."""
    entry = {'assessment': DECIDED_ASSESSMENT, 'engine_version': 'cpt-studio-validation@10', 'event_inventory': False,
             'revision_current': True, 'final': True,
             'proposals': {pk: dict(item[1], open_facts=[list(f) for f in item[1]['open_facts']])
                           for pk, item in D339_ROWS.items()},
             'v2_proposals': [],
             'decisions': [_decision('dddd0339-0000-4000-8000-0000000000d1', R_APPROVE, 'approve', 101),
                           _decision('dddd0339-0000-4000-8000-0000000000d2', R_APPROVE, 'revoke', 102),
                           _decision('dddd0339-0000-4000-8000-0000000000d3', R_APPROVE, 'approve', 103),
                           _decision('dddd0339-0000-4000-8000-0000000000d4', R_REJECT, 'reject', 104),
                           _decision('dddd0339-0000-4000-8000-0000000000d5', R_CONFIRM, 'confirm', 105),
                           _decision('dddd0339-0000-4000-8000-0000000000d6', R_REINSTATE_READY, 'reinstate', 106),
                           _decision('dddd0339-0000-4000-8000-0000000000d7', R_REINSTATE_DETAIL, 'reinstate', 107)],
             'answers': [_answer('dddd0339-0000-4000-8000-0000000000e1', '45381', 'extent'),
                         _answer('dddd0339-0000-4000-8000-0000000000e2', '45378', 'extent', revoked=True)],
             'memberships': dict(MEMBERSHIPS)}
    entry.update(change)
    return entry


def decided_views(actions=None):
    """DECIDED as c2e53f8e renders its stored state (the previous image)."""
    actions = D339_ACTIONS if actions is None else actions
    numbered = [pk for pk in sorted(D339_ROWS) if D339_ROWS[pk][2] is not None]
    views = {'state': {'stored': 'needs_clarification', 'derived': 'needs_clarification'},
             'list.customer_row': {'state': 'awaiting_detail'},
             'readiness': {'customer': {'draft': True, 'approved': False}, 'review': {'draft': True, 'reviewed': False}}}
    for i in (1, 2, 3):
        views[f'customer.detail[{i}]'] = customer('awaiting_detail', [
            {'id': pk, 'code': D339_ROWS[pk][0], 'status': D339_ROWS[pk][2], 'allowed_actions': list(actions[pk])}
            for pk in numbered])
        views[f'member.detail[{i}]'] = {'assessment': {'id': DECIDED_ASSESSMENT, 'proposals': [
            {'id': pk, 'code': item[0], 'status': item[3], 'bucket': item[1]['bucket'], 'allowed_actions': list(actions[pk])}
            for pk, item in sorted(D339_ROWS.items())]}, 'readiness': {'draft': True, 'reviewed': False}}
    views['operator.detail'] = {'assessment': {'id': DECIDED_ASSESSMENT, 'proposals': [
        {'id': pk, 'code': item[0], 'status': item[3], 'bucket': item[1]['bucket'], 'allowed_actions': []}
        for pk, item in sorted(D339_ROWS.items())]}, 'readiness': {'draft': True, 'reviewed': False}}
    return views


def candidate_reading(views, decide_nothing=True):
    """The candidate's views of an update-pending legacy encounter while the reading is owed (AMENDMENT-1 9.4, U10): the
    same codes and statuses, offering no draft export and - ``decide_nothing`` - no action."""
    before = json.loads(json.dumps(views))
    for name, view in before.items():
        if not isinstance(view, dict):
            continue
        for row in (view.get('codes') or []) + ((view.get('assessment') or {}).get('proposals') or []):
            if decide_nothing:
                row['allowed_actions'] = []
        if isinstance(view.get('readiness'), dict) and 'draft' in view['readiness']:
            view['readiness']['draft'] = False
        if name == 'readiness':
            view['customer']['draft'] = False
    return before


def decided_findings(pk, previous, decide_nothing=True):
    return [{'encounter': pk, 'new_path': False, **item}
            for item in rc.compare_encounter(candidate_reading(previous, decide_nothing), previous)['findings']]


# D338R-1's input: encounter 03c600f4 of the run, as the previous image rendered it (d15-c/out-after)
D338R1_ASSESSMENT = 'f921fc05-aefa-44e6-8e13-a1777063b2d6'
D338R1_APPROVED = '7c0797a7-9e34-4f1b-9c56-ba1ed19c9b3f'
D338R1_ALTERNATIVES = [('3e04e61f-dd6f-4647-b443-c702184a0ffb', '45378'), ('fb9cba91-b08b-499f-8253-35cf46e78770', '45330'),
                       ('2551ee08-3300-417e-b920-446e8627b981', '46600'), ('f04f5bdb-cc5b-419d-8926-9c46a8748bf9', '99213'),
                       ('26aaffed-4e8c-4808-9578-f0f648707d8d', '31575'), ('b97bc1ce-669b-4193-9d85-831e77f0104f', 'G8420'),
                       ('bc16a737-8d56-4b74-ba9d-428628a8226a', '99203'), ('3f9f97b1-245a-4884-858a-2324e0eace5e', '1036F'),
                       ('bdf3fb03-2451-45de-a5dc-58e2b53d1358', 'G8417'), ('92c36197-4204-46bd-b69c-0359cbaee5cd', '99204'),
                       ('7ff17905-ed73-4aa9-96a3-f35628d74e8f', 'G0121')]


def d338r1_entry(**change):
    rows = {D338R1_APPROVED: stored_row('ready', 'selected', code='46221', family='gi.anorectal', key='sel:0')}
    rows.update({pk: stored_row('informational', 'alternative', code=code_, family='gi.unsupported', key=f'alt:{i}')
                 for i, (pk, code_) in enumerate(D338R1_ALTERNATIVES)})
    entry = {'assessment': D338R1_ASSESSMENT, 'engine_version': 'cpt-studio-validation@4', 'event_inventory': False,
             'revision_current': True, 'final': True, 'proposals': rows, 'v2_proposals': [],
             'decisions': [_decision('7c0797a7-0000-4000-8000-0000000000d1', D338R1_APPROVED, 'approve', 9,
                                     assessment=D338R1_ASSESSMENT)],
             'answers': [], 'memberships': dict(MEMBERSHIPS)}
    entry.update(change)
    return entry


def d338r1_views(approved_actions=('revoke',)):
    """03c600f4 as the previous image rendered it (d15-c/out-after): 46221 approved by an agent, ['revoke'] for each
    member (none for the operator's read-only access), and eleven alternatives."""
    alternatives = [{'id': pk, 'code': code_, 'status': 'informational', 'bucket': 'alternative', 'allowed_actions': []}
                    for pk, code_ in D338R1_ALTERNATIVES]
    views = {'state': {'stored': 'reviewed', 'derived': 'reviewed'}, 'list.customer_row': {'state': 'reviewed'},
             'readiness': {'customer': {'draft': True, 'approved': True}, 'review': {'draft': True, 'reviewed': True}}}
    for i in (1, 2, 3):
        views[f'customer.detail[{i}]'] = customer('reviewed', [{'id': D338R1_APPROVED, 'code': '46221', 'status': 'approved',
                                                                'allowed_actions': list(approved_actions)}])
        views[f'member.detail[{i}]'] = {'assessment': {'id': D338R1_ASSESSMENT, 'proposals': [
            {'id': D338R1_APPROVED, 'code': '46221', 'status': 'ready', 'bucket': 'selected',
             'allowed_actions': list(approved_actions)}] + [dict(row) for row in alternatives]},
            'readiness': {'draft': True, 'reviewed': True}}
    views['operator.detail'] = {'assessment': {'id': D338R1_ASSESSMENT, 'proposals': [
        {'id': D338R1_APPROVED, 'code': '46221', 'status': 'ready', 'bucket': 'selected', 'allowed_actions': []}]
        + [dict(row) for row in alternatives]}, 'readiness': {'draft': True, 'reviewed': True}}
    return views


class D339Case(D338Case):
    """assertion_2 over one update-pending legacy encounter (the close named it assessment_off_context, the note lists
    it), its stored state and the previous image's views; the candidate as 9.4 states it reads them."""

    def judge_one(self, pk, entry, views, findings=None, reason='assessment_off_context'):
        found = decided_findings(pk, views) if findings is None else findings
        return rc.assertion_2({'encounters': 1, 'findings': found}, {pk: [reason]}, {'update_pending': [pk]}, {pk: entry},
                              {pk: views})

    def assert_one_fails(self, pk, entry, views, why, findings=None):
        problems, measurement = self.judge_one(pk, entry, views, findings)
        self.assertTrue(problems)
        self.assertTrue(all(why in problem for problem in problems), (why, problems))
        self.assertEqual(measurement['recorded'], [])
        return problems

    def assert_one_recorded(self, pk, entry, views, count, findings=None):
        problems, measurement = self.judge_one(pk, entry, views, findings)
        self.assertEqual(problems, [])
        self.assertEqual(len(measurement['recorded']), count)
        return measurement


class D339RecordedAsC2e53f8eShowsTheStoredState(D339Case):
    """DECISIONS D339, test (1): a difference on an update-pending legacy encounter is recorded when the previous image
    shows each row as c2e53f8e shows its stored state - its current decision and the member answers its overlay reads
    included (D338R-1)."""

    def test_d338r1_an_approved_legacy_row_with_revoke_and_only_the_draft_offer_differing(self):
        views = d338r1_views()
        draft_only = decided_findings(LEGACY_ENCOUNTER, views, decide_nothing=False)  # the verifier's candidate side
        self.assertEqual(sorted(f['where'] for f in draft_only), sorted(DETAIL_VIEWS + ('readiness.customer',)))
        self.assertEqual({f['finding'] for f in draft_only}, {'offer_not_made_before'})
        problems, measurement = self.judge_one(LEGACY_ENCOUNTER, d338r1_entry(), views, draft_only)
        self.assertEqual((problems, len(measurement['recorded'])), ([], 8))
        self.assertEqual(measurement['encounters'][LEGACY_ENCOUNTER]['exercised'], {'approve': 1})
        self.assertIn('(assessment_off_context) 8 [approve 1]', rc.u17_summary(measurement))
        # A21's reason, and the candidate reading the earlier codes deciding nothing (its revoke a recorded difference)
        problems, measurement = self.judge_one(LEGACY_ENCOUNTER, d338r1_entry(), views, None, 'reconciled_unknown')
        self.assertEqual(problems, [])
        self.assertEqual(sorted({(f['where'], f['finding'], tuple(f.get('actions') or ())) for f in measurement['recorded']
                                 if f['finding'] != 'offer_not_made_before'}),
                         sorted({(f'{side}.detail[{i}]', 'action_not_allowed_before', ('revoke',))
                                 for side in ('customer', 'member') for i in (1, 2, 3)}))

    def test_reject_confirm_reinstate_and_an_unavailable_answer_each_as_c2e53f8e_shows_them(self):
        views = decided_views()
        measurement = self.assert_one_recorded(DECIDED, decided_entry(), views, len(decided_findings(DECIDED, views)))
        self.assertEqual(measurement['encounters'][DECIDED]['exercised'],
                         {'answer_unavailable': 2, 'approve': 1, 'confirm': 1, 'reinstate': 2, 'reject': 1})
        expected = rc.legacy_expected(decided_entry())
        for pk, (code_, _, shown, overlay) in D339_ROWS.items():
            with self.subTest(code=code_):
                self.assertEqual((expected[pk]['status'] if expected[pk]['numbered'] else None, expected[pk]['view_status']),
                                 (shown, overlay))
        # the reinstated code whose check passes may be shown without approve (exact evidence and the same-day hold are
        # not read: approve is allowed, never required); its revoke and reject are required
        actions = dict(D339_ACTIONS, **{R_REINSTATE_READY: ['reject', 'revoke']})
        views = decided_views(actions)
        self.assert_one_recorded(DECIDED, decided_entry(), views, len(decided_findings(DECIDED, views)))
        # and an undecided ready code without approve, for the same reason
        actions = dict(D339_ACTIONS, **{R_UNDECIDED: ['reject']})
        views = decided_views(actions)
        self.assert_one_recorded(DECIDED, decided_entry(), views, len(decided_findings(DECIDED, views)))

    def test_a_gate_the_sql_cannot_read_requires_nothing(self):
        # a finality that turns on the participants configured now: the previous image may show no action at all
        views = decided_views({pk: [] for pk in D339_ROWS})
        self.assert_one_recorded(DECIDED, decided_entry(final=None), views, len(decided_findings(DECIDED, views)))
        # an assessment off the current revision: c2e53f8e numbers no code and allows nothing (customer_api.py:996,
        # review.py:650)
        views = decided_views({pk: [] for pk in D339_ROWS})
        for i in (1, 2, 3):
            views[f'customer.detail[{i}]']['codes'] = []
        self.assert_one_recorded(DECIDED, decided_entry(revision_current=False), views,
                                 len(decided_findings(DECIDED, views)))
        # a membership that may not review is offered nothing
        views = decided_views()
        for i in (2,):
            for row in views[f'customer.detail[{i}]']['codes'] + views[f'member.detail[{i}]']['assessment']['proposals']:
                row['allowed_actions'] = []
        self.assert_one_recorded(DECIDED, decided_entry(memberships={'1': True, '2': False, '3': True}), views,
                                 len(decided_findings(DECIDED, views)))


class D339StillFails(D339Case):
    """DECISIONS D339, test (2): a shown status or action that c2e53f8e does not produce on the stored state fails."""

    def mutate(self, views, pk, status=None, actions=None, where=('customer.detail[1]',)):
        for name in where:
            rows = views[name]['codes'] if name.startswith('customer.') else views[name]['assessment']['proposals']
            for row in rows:
                if row['id'] == pk:
                    if status is not None:
                        row['status'] = status
                    if actions is not None:
                        row['allowed_actions'] = list(actions)
        return views

    def test_a_status_other_than_c2e53f8es_status_over_the_stored_state(self):
        # 'approved' with no current approve
        views = self.mutate(decided_views(), R_UNDECIDED, 'approved', ['revoke'])
        self.assert_one_fails(DECIDED, decided_entry(), views,
                              f"customer.detail[1]: {R_UNDECIDED} shows status 'approved', stored 'ready' (selected): the "
                              "legacy release shows 'ready'")
        # 'ready' where a reject stands
        views = self.mutate(decided_views(), R_REJECT, 'ready')
        self.assert_one_fails(DECIDED, decided_entry(), views,
                              f"{R_REJECT} shows status 'ready', stored 'ready' (selected): the legacy release shows "
                              "'excluded' for its stored state (stored ready selected, current decision reject)")
        # a revoked approve counted as current: approve then revoke leaves no current decision
        entry = decided_entry()
        entry['decisions'] = [item for item in entry['decisions'] if item['sequence'] != 103]
        views = decided_views()
        self.assert_one_fails(DECIDED, entry, views,
                              f"{R_APPROVE} shows status 'approved', stored 'ready' (selected): the legacy release "
                              "shows 'ready' for its stored state (stored ready selected, current decision none)")
        # an invalidated approve is no current decision either
        entry = decided_entry()
        for item in entry['decisions']:
            if item['sequence'] == 103:
                item['invalidated'] = True
        self.assert_one_fails(DECIDED, entry, decided_views(), f"{R_APPROVE} shows status 'approved'")
        # a decision of another assessment's proposal decides nothing here
        entry = decided_entry()
        for item in entry['decisions']:
            if item['proposal'] == R_APPROVE:
                item.update(assessment=OTHER_ASSESSMENT, proposal='dddd0339-0000-4000-8000-000000000999')
        self.assert_one_fails(DECIDED, entry, decided_views(), f"{R_APPROVE} shows status 'approved'")
        # a carried approval is current on the assessment it was carried onto, never on its root's
        entry = decided_entry()
        entry['decisions'] = [_decision('dddd0339-0000-4000-8000-0000000000c0', 'dddd0339-0000-4000-8000-000000000999',
                                        'approve', 50, assessment=OTHER_ASSESSMENT)] + [
            dict(item, carried_from='dddd0339-0000-4000-8000-0000000000c0') if item['sequence'] == 103 else item
            for item in entry['decisions']]
        self.assert_one_recorded(DECIDED, entry, decided_views(), len(decided_findings(DECIDED, decided_views())))
        self.assertEqual(rc.legacy_decision_root(entry['decisions'], entry['decisions'][3])['id'],
                         'dddd0339-0000-4000-8000-0000000000c0')
        # the overlay's status on a member's detail: a reinstated code still waiting on its check is not 'excluded'
        views = self.mutate(decided_views(), R_REINSTATE_DETAIL, 'excluded', where=('member.detail[2]',))
        self.assert_one_fails(DECIDED, decided_entry(), views,
                              f"member.detail[2]: {R_REINSTATE_DETAIL} shows status 'excluded', stored 'excluded' "
                              "(excluded): the legacy release shows 'needs_clarification'")

    def test_an_action_c2e53f8es_actions_cannot_produce_on_the_stored_state(self):
        cases = (
            # D338R-3: approve on an undecided, non-reinstatable excluded row
            (R_PLAIN, ['approve'], "allows ['approve'], which the legacy release does not offer on a stored excluded "
                                   "excluded row"),
            # approve or reject on a row with a current approve
            (R_APPROVE, ['approve', 'revoke'], "allows ['approve']"),
            (R_APPROVE, ['reject', 'revoke'], "allows ['reject']"),
            # reinstate on a decided row (a confirmation, a reinstatement)
            (R_CONFIRM, ['reinstate', 'revoke'], "allows ['reinstate']"),
            (R_REINSTATE_READY, ['reinstate', 'reject', 'revoke'], "allows ['reinstate']"),
            # approve on a reinstated code whose review.reinstatement check does not pass
            (R_REINSTATE_DETAIL, ['approve', 'reject', 'revoke'], "allows ['approve']"),
            # anything on a code a member's answer leaves detail_unavailable, or one the engine excluded by an answer
            (R_ANSWERED, ['reject'], "allows ['reject']"),
            (R_MARKER, ['revoke'], "allows ['revoke']"),
            # an action c2e53f8e requires missing: a decided code's revoke, an undecided reinstatable exclusion's confirm
            (R_APPROVE, [], "does not allow ['revoke']"),
            (R_REJECT, ['reject'], "does not allow ['revoke']"),
            (R_UNDECIDED, ['approve'], "does not allow ['reject']"),
        )
        for pk, actions, why in cases:
            with self.subTest(code=D339_ROWS[pk][0], actions=actions):
                views = self.mutate(decided_views(), pk, actions=actions, where=('member.detail[1]',))
                self.assert_one_fails(DECIDED, decided_entry(), views, why)
        entry = decided_entry(proposals={**decided_entry()['proposals'],
                                         R_CONFIRM: dict(D339_ROWS[R_CONFIRM][1], open_facts=[])})
        entry['decisions'] = [item for item in entry['decisions'] if item['proposal'] != R_CONFIRM]
        views = self.mutate(decided_views(), R_CONFIRM, actions=['reinstate'], where=('member.detail[1]',))
        self.assert_one_fails(DECIDED, entry, views, "does not allow ['confirm']")
        # the operator's read-only access never makes an action required, and allows none c2e53f8e cannot produce
        views = self.mutate(decided_views(), R_PLAIN, actions=['approve'], where=('operator.detail',))
        self.assert_one_fails(DECIDED, decided_entry(), views, "operator.detail: dddd0339-0000-4000-8000-000000000109 "
                                                               "allows ['approve']")
        # a membership that may not review offered anything; a viewer that is no membership of the workspace
        self.assert_one_fails(DECIDED, decided_entry(memberships={'1': True, '2': False, '3': True}), decided_views(),
                              "customer.detail[2]: ")
        views = decided_views()
        views['member.detail[9]'] = views.pop('member.detail[3]')
        self.assert_one_fails(DECIDED, decided_entry(), views, "member.detail[9]: its viewer '9' is not a membership")
        # off the current revision nothing is offered (and the customer page numbers nothing)
        self.assert_one_fails(DECIDED, decided_entry(revision_current=False), decided_views(), 'not on the current revision')

    def test_an_answer_the_overlay_may_apply_reads_as_stored(self):
        # a fingerprinted answer: whether it binds turns on the question's fingerprint (passages of the revision text),
        # which the runner does not read - the stored reading is expected, so the overlay's exclusion fails
        entry = decided_entry(answers=[_answer('dddd0339-0000-4000-8000-0000000000e1', '45381', 'extent',
                                               fingerprinted=True)])
        self.assertEqual(rc.legacy_expected(entry)[R_ANSWERED]['unavailable'], ('unread', 'extent', 'not_documented'))
        problems = self.assert_one_fails(DECIDED, entry, decided_views(), 'the stored reading is expected (DECISIONS D339)')
        self.assertIn(f"{R_ANSWERED} shows status 'excluded', stored 'needs_clarification' (selected): the legacy release "
                      "shows 'needs_detail'", problems[0])
        # an answer the assessment read itself, a withdrawn one, one of another code: the overlay applies none
        for answer in (_answer('e1', '45381', 'extent', read=True), _answer('e1', '45381', 'extent', revoked=True),
                       _answer('e1', '45380', 'extent'), _answer('e1', '45381', 'extent', family='gi.egd'),
                       _answer('e1', '45381', 'extent', value='documented'), _answer('e1', '45381', 'completion')):
            with self.subTest(answer=answer):
                entry = decided_entry(answers=[answer])
                self.assertEqual(rc.legacy_expected(entry)[R_ANSWERED]['unavailable'][0], 'available')
                self.assert_one_fails(DECIDED, entry, decided_views(), f"{R_ANSWERED} shows status 'excluded'")

    def test_the_customer_page_numbers_exactly_what_c2e53f8e_numbers(self):
        views = decided_views()
        views['customer.detail[1]']['codes'].append({'id': R_ALT, 'code': '99213', 'status': 'ready',
                                                     'allowed_actions': []})
        self.assert_one_fails(DECIDED, decided_entry(), views, f'numbers {R_ALT}, which the legacy release does not number')
        views = decided_views()
        views['customer.detail[2]']['codes'] = [row for row in views['customer.detail[2]']['codes'] if row['id'] != R_CONFIRM]
        self.assert_one_fails(DECIDED, decided_entry(), views, f"does not number ['{R_CONFIRM}']")

    def test_a_stored_state_not_read_whole_is_never_as_stored(self):
        for why, change in (
                ('its decisions were not read', {'decisions': None}),
                ('its decisions were not read', {'decisions': [dict(_decision('x', R_APPROVE, 'approve', 1), sequence='1')]}),
                ('its decisions were not read', {'decisions': [_decision('x', R_APPROVE, 'approve', 1),
                                                               _decision('y', R_APPROVE, 'revoke', 1)]}),
                ('its member answers were not read', {'answers': None}),
                ('its member answers were not read', {'answers': [dict(_answer('e', '45381', 'extent'), revoked=None)]}),
                ("its workspace's memberships were not read", {'memberships': None}),
                ('whether its assessment can be decided on was not read', {'final': False}),
                ('whether its assessment can be decided on was not read', {'final': 1}),
                ('whether its assessment can be decided on was not read', {'revision_current': None}),
                ('its stored state was not read whole: its current assessment was read more than once',
                 {'unread': 'its current assessment was read more than once'}),
                (f'its proposal {R_UNDECIDED} was not read whole',
                 {'proposals': {**decided_entry()['proposals'], R_UNDECIDED: {'status': 'ready', 'bucket': 'selected'}}})):
            with self.subTest(why=why):
                self.assert_one_fails(DECIDED, decided_entry(**change), decided_views(), why)


class D339Port(unittest.TestCase):
    """DECISIONS D339: the port of c2e53f8e's legacy path, pinned to c2e53f8e7d33 branch by branch. Each table row is
    (c2e53f8e FILE:LINE, the source line that decides it, the inputs, what the port gives). The branch tables are the pin
    where this tree's own function differs from c2e53f8e's (the NOTES' source diff: customer_api._status and
    review._actions, _allowed and the answer reading differ; current_decisions, _current_decision, decision_root,
    is_final, review_view.review_view and questions.bind/answered_away do not, and D339ParityOnTheDatabase runs this
    tree's own against the port on real rows)."""

    STATUS = (  # customer_api.py:543-562 (_status), with the overlay's status it reads at :559
        ('customer_api.py:549-550', 'if action == Decision.APPROVE:', stored_row('ready', 'selected'), 'approve',
         'available', 'approved'),
        ('customer_api.py:551-552', 'if action == Decision.REJECT:', stored_row('ready', 'selected'), 'reject', 'available',
         'excluded'),
        ('customer_api.py:553-554', 'if action == Decision.CONFIRM:', stored_row('excluded', 'excluded', reinstatable=True),
         'confirm', 'available', 'excluded'),
        ('customer_api.py:555-556', 'if view is not None and view.reason == review.DETAIL_UNAVAILABLE:',
         stored_row('needs_clarification', 'selected'), None, 'unavailable', 'excluded'),
        ('customer_api.py:557-558', 'if proposal.bucket == Proposal.EXCLUDED and action != Decision.REINSTATE:',
         stored_row('excluded', 'excluded', reinstatable=True), None, 'available', 'excluded'),
        ('customer_api.py:560-561', 'if status == Proposal.NEEDS_CLARIFICATION:',
         stored_row('needs_clarification', 'selected'), None, 'available', 'needs_detail'),
        ('customer_api.py:560-561', 'if status == Proposal.NEEDS_CLARIFICATION:',
         stored_row('excluded', 'excluded', reinstatable=True), 'reinstate', 'available', 'needs_detail'),
        ('customer_api.py:562', "return 'ready', REINSTATED_SUB_LABEL if action == Decision.REINSTATE else ''",
         stored_row('excluded', 'excluded', reinstatable=True, clear=True), 'reinstate', 'available', 'ready'),
        ('customer_api.py:562', "return 'ready', REINSTATED_SUB_LABEL if action == Decision.REINSTATE else ''",
         stored_row('ready', 'selected'), None, 'available', 'ready'),
        ('customer_api.py:562', "return 'ready', REINSTATED_SUB_LABEL if action == Decision.REINSTATE else ''",
         stored_row('ready', 'selected'), None, 'unread', 'ready'),  # an answer whose binding is not read: as stored
        ('customer_api.py:562', "return 'ready', REINSTATED_SUB_LABEL if action == Decision.REINSTATE else ''",
         stored_row('excluded', 'excluded'), 'reinstate', 'available', 'ready'),  # not reinstatable: never counted
    )
    VIEW_STATUS = (  # validation/review_view.py: the status a member's and the operator's detail print
        ('validation/review_view.py:584', 'status=STATUS_EXCLUDED,', stored_row('ready', 'selected'), None, 'unavailable',
         'excluded'),
        ('validation/review_view.py:680', 'elif p.bucket == EXCLUDED and active and (base_added or not stored_clear):',
         stored_row('excluded', 'excluded', reinstatable=True), 'reinstate', 'available', 'needs_clarification'),
        ('validation/review_view.py:680', 'elif p.bucket == EXCLUDED and active and (base_added or not stored_clear):',
         stored_row('excluded', 'excluded', reinstatable=True), 'approve', 'available', 'needs_clarification'),
        ('validation/review_view.py:685', 'status = p.status', stored_row('excluded', 'excluded', reinstatable=True,
                                                                          clear=True), 'reinstate', 'available', 'excluded'),
        ('validation/review_view.py:685', 'status = p.status', stored_row('excluded', 'excluded', reinstatable=True),
         'reject', 'available', 'excluded'),
        ('validation/review_view.py:685', 'status = p.status', stored_row('needs_clarification', 'selected'), 'approve',
         'available', 'needs_clarification'),
        ('validation/review_view.py:685', 'status = p.status', stored_row('ready', 'selected'), None, 'unread', 'ready'),
    )
    ACTIONS = (  # review.py:562-584 (_actions): (required, optional)
        ('review.py:566-567', 'if current is not None and current.action in (APPROVE, REJECT, CONFIRM):',
         stored_row('ready', 'selected'), 'approve', 'available', 'ready', ({'revoke'}, set())),
        ('review.py:566-567', 'if current is not None and current.action in (APPROVE, REJECT, CONFIRM):',
         stored_row('excluded', 'excluded', reinstatable=True), 'confirm', 'available', 'excluded', ({'revoke'}, set())),
        ('review.py:568-569', "return [REVOKE] if current else []  # a needed detail is answered as unavailable: nothing to decide",
         stored_row('needs_clarification', 'selected'), None, 'unavailable', 'excluded', (set(), set())),
        ('review.py:568-569', "return [REVOKE] if current else []  # a needed detail is answered as unavailable: nothing to decide",
         stored_row('excluded', 'excluded', reinstatable=True), 'reinstate', 'unavailable', 'excluded', ({'revoke'}, set())),
        ('review.py:572-574', 'actions = [APPROVE] if status == Proposal.READY and exact and not same_day_held else []',
         stored_row('ready', 'selected'), None, 'available', 'ready', ({'reject'}, {'approve'})),
        ('review.py:572-574', 'return actions + [REJECT] + ([REVOKE] if current else [])',
         stored_row('needs_clarification', 'selected'), None, 'available', 'needs_clarification', ({'reject'}, set())),
        ('review.py:572-574', 'return actions + [REJECT] + ([REVOKE] if current else [])',
         stored_row('ready', 'selected'), 'reinstate', 'available', 'ready', ({'reject', 'revoke'}, {'approve'})),
        ('review.py:579-580', 'return []', stored_row('excluded', 'excluded'), None, 'available', 'excluded',
         (set(), set())),
        ('review.py:581', 'return ([REINSTATE] if exact else []) + [CONFIRM]',
         stored_row('excluded', 'excluded', reinstatable=True), None, 'available', 'excluded', ({'confirm'}, {'reinstate'})),
        ('review.py:582-583', 'return ([APPROVE] if exact and clear and not same_day_held else []) + [REJECT, REVOKE]',
         stored_row('excluded', 'excluded', reinstatable=True, clear=True), 'reinstate', 'available', 'excluded',
         ({'reject', 'revoke'}, {'approve'})),
        ('review.py:582-583', 'return ([APPROVE] if exact and clear and not same_day_held else []) + [REJECT, REVOKE]',
         stored_row('excluded', 'excluded', reinstatable=True), 'reinstate', 'available', 'needs_clarification',
         ({'reject', 'revoke'}, set())),
        ('review.py:584', 'return [REVOKE] if current else []', stored_row('informational', 'alternative'), None,
         'available', 'informational', (set(), set())),
        ('review.py:584', 'return [REVOKE] if current else []', stored_row('informational', 'alternative'), 'reinstate',
         'available', 'informational', ({'revoke'}, set())),
    )
    NUMBERED = (  # customer_api.py:605-617 (code_rows)
        ('customer_api.py:610-613', 'if (proposal.bucket == Proposal.SELECTED or questions.answered_away(proposal)',
         stored_row('ready', 'selected'), None, True),
        ('customer_api.py:610-613', 'if (proposal.bucket == Proposal.SELECTED or questions.answered_away(proposal)',
         stored_row('excluded', 'excluded', marker=('extent', 'cannot_confirm')), None, True),
        ('customer_api.py:610-613', 'or (proposal.bucket == Proposal.EXCLUDED and decision is not None',
         stored_row('excluded', 'excluded'), 'reinstate', True),
        ('customer_api.py:614-615', 'elif proposal.bucket == Proposal.EXCLUDED and (proposal.reinstatable or decision is not None):',
         stored_row('excluded', 'excluded', reinstatable=True), None, True),
        ('customer_api.py:614-615', 'elif proposal.bucket == Proposal.EXCLUDED and (proposal.reinstatable or decision is not None):',
         stored_row('excluded', 'excluded'), 'confirm', True),
        ('customer_api.py:616-617', 'others.append(proposal)', stored_row('excluded', 'excluded'), None, False),
        ('customer_api.py:616-617', 'others.append(proposal)', stored_row('informational', 'alternative'), 'approve', False),
    )
    COUNTED = (  # validation/review_view.py:212-222 (counts)
        ('validation/review_view.py:218-219', 'if answered_by_engine(p)[0]:',
         stored_row('excluded', 'excluded', marker=('extent', 'not_documented')), None, True),
        ('validation/review_view.py:220-221', 'return action != REJECT', stored_row('ready', 'selected'), None, True),
        ('validation/review_view.py:220-221', 'return action != REJECT', stored_row('ready', 'selected'), 'reject', False),
        ('validation/review_view.py:222', 'return p.bucket == EXCLUDED and p.reinstatable and action in (REINSTATE, APPROVE)',
         stored_row('excluded', 'excluded', reinstatable=True), 'approve', True),
        ('validation/review_view.py:222', 'return p.bucket == EXCLUDED and p.reinstatable and action in (REINSTATE, APPROVE)',
         stored_row('excluded', 'excluded'), 'reinstate', False),
        ('validation/review_view.py:222', 'return p.bucket == EXCLUDED and p.reinstatable and action in (REINSTATE, APPROVE)',
         stored_row('excluded', 'excluded', reinstatable=True), 'confirm', False),
    )
    _EXTENT = [('extent', 'gi.colonoscopy')]
    _ROW = stored_row('needs_clarification', 'selected', code='45381', family='gi.colonoscopy', open_facts=_EXTENT)
    UNAVAILABLE = (  # the DETAIL_UNAVAILABLE derivation: (row, answers, counted) -> state
        ('validation/review_view.py:541-544', 'if answered_by_engine(p)[0]:',
         stored_row('excluded', 'excluded', code='45381', family='gi.colonoscopy', marker=('extent', 'cannot_confirm')), [],
         True, ('unavailable', 'extent', 'cannot_confirm')),
        ('validation/review_view.py:545-551', 'by = _unavailable_by(p, bases.get(p.code), readable, answered, counted=True,',
         _ROW, [_answer('a', '45381', 'extent')], True, ('unavailable', 'extent', 'not_documented')),
        ('validation/questions.py:286-287', 'if _field(answer, \'fact\') in KEY_BOUND_FACTS:',
         stored_row('ready', 'selected', code='45378', family='gi.colonoscopy', open_facts=[('base_included', '')]),
         [_answer('a', '45378', 'base_included', fingerprinted=True)], False, ('unavailable', 'base_included', 'not_documented')),
        ('validation/questions.py:290-293', 'elif not given or given == now:', _ROW,
         [_answer('a', '45381', 'extent', fingerprinted=True)], True, ('unread', 'extent', 'not_documented')),
        ('review.py:250', 'return list(MemberAnswer.objects.filter(revision_id=assessment.revision_id, revocation__isnull=True)',
         _ROW,
         [_answer('a', '45381', 'extent', revoked=True)], True, ('available', '', '')),
        ('review.py:332-333', 'rest = [answer for answer in standing if answer.pk not in read]', _ROW,
         [_answer('a', '45381', 'extent', read=True)], True, ('available', '', '')),
        ('validation/questions.py:282-283', "if _field(answer, 'value') not in UNAVAILABLE:", _ROW,
         [_answer('a', '45381', 'extent', value='documented')], True, ('available', '', '')),
        ('validation/review_view.py:191', 'if code and value in UNAVAILABLE_ANSWERS:', _ROW,
         [_answer('a', '', 'extent')], True, ('available', '', '')),
        ('validation/review_view.py:325', 'value = answered.get((p.code, p.family, fact))', _ROW,
         [_answer('a', '45381', 'extent', family='gi.egd')], True, ('available', '', '')),
        ('validation/review_view.py:312-313', 'facts = [fact for fact in facts if fact != BASE_FACT] + ([BASE_FACT] if held else [])',
         stored_row('ready', 'selected', code='45378', family='gi.colonoscopy', open_facts=[('base_included', '')]),
         [_answer('a', '45378', 'base_included')], True, ('unread', 'base_included', 'not_documented')),
        ('validation/review_view.py:314-315', 'facts += [q[\'fact\'] for q in _reinstatement_waits(p)]',
         stored_row('excluded', 'excluded', code='43251', family='gi.egd', reinstatable=True),
         [_answer('a', '43251', 'documentation', family='gi.egd')], True, ('unread', 'documentation', 'not_documented')),
        ('validation/review_view.py:316-317', 'if same_day and SEPARATE_EM_FACT not in facts:',
         stored_row('ready', 'selected', code='99213', family='gi.office_em'),
         [_answer('a', '99213', 'separate_em', family='gi.office_em')], True, ('unread', 'separate_em', 'not_documented')),
        ('validation/review_view.py:549', 'by = _unavailable_by(p, None, False, answered)',
         stored_row('ready', 'selected', code='99213', family='gi.office_em'),
         [_answer('a', '99213', 'separate_em', family='gi.office_em')], False, ('available', '', '')),
    )

    def row(self, item, fields=None):
        return item if fields is None else dict(item, **fields)

    def test_status(self):
        for line, source, row, action, unavailable, expected in self.STATUS:
            with self.subTest(line=line, source=source, action=action, unavailable=unavailable):
                self.assertEqual(rc.legacy_status(row, action, unavailable), expected)

    def test_view_status(self):
        for line, source, row, action, unavailable, expected in self.VIEW_STATUS:
            with self.subTest(line=line, source=source, action=action, unavailable=unavailable):
                self.assertEqual(rc.legacy_view_status(row, action, unavailable), expected)

    def test_actions(self):
        for line, source, row, current, unavailable, status, expected in self.ACTIONS:
            with self.subTest(line=line, source=source, current=current, unavailable=unavailable):
                self.assertEqual(rc.legacy_actions(row, current, unavailable, status), expected)

    def test_allowed(self):
        """review.py:646-654 (_allowed): the gates in front of _actions."""
        row, entry = stored_row('ready', 'selected'), {'revision_current': True, 'final': True}
        self.assertEqual(rc.legacy_allowed(True, entry, row, None, 'available', 'ready'), ({'reject'}, {'approve'}))
        self.assertEqual(rc.legacy_allowed(False, entry, row, 'approve', 'available', 'ready'), (set(), set()))  # :647
        self.assertEqual(rc.legacy_allowed(True, dict(entry, revision_current=False), row, 'approve', 'available',
                                           'ready'), (set(), set()))  # :650
        self.assertEqual(rc.legacy_allowed(None, entry, row, 'approve', 'available', 'ready'), (set(), {'revoke'}))
        self.assertEqual(rc.legacy_allowed(True, dict(entry, final=None), row, None, 'available', 'ready'),
                         (set(), {'reject', 'approve'}))

    def test_numbered(self):
        for line, source, row, action, expected in self.NUMBERED:
            with self.subTest(line=line, source=source, action=action):
                self.assertEqual(rc.legacy_numbered(row, action), expected)

    def test_counted(self):
        for line, source, row, action, expected in self.COUNTED:
            with self.subTest(line=line, source=source, action=action):
                self.assertEqual(rc.legacy_counted(row, action), expected)

    def test_unavailable(self):
        for line, source, row, answers, counted, expected in self.UNAVAILABLE:
            with self.subTest(line=line, source=source):
                self.assertEqual(rc.legacy_unavailable(row, answers, counted), expected)

    def test_current_decisions_and_finality(self):
        """review.py:219-234 and :1529-1534; review.py:2077-2084 with jobs.py:298-301, :322-346 and :417-427."""
        a, b, p, q = 'a0', 'b0', 'p0', 'q0'
        chain = [_decision('d1', p, 'approve', 1, assessment=a), _decision('d2', p, 'revoke', 2, assessment=a),
                 _decision('d3', p, 'reject', 3, assessment=a), _decision('d4', q, 'approve', 4, assessment=a),
                 _decision('d5', q, 'revoke', 5, assessment=a), _decision('d6', q, 'approve', 6, assessment=b,
                                                                          carried_from='d4')]
        self.assertEqual({k: v['id'] for k, v in rc.legacy_current_decisions(chain, a).items()}, {p: 'd3'})
        self.assertEqual(rc.legacy_current_decisions(chain, b), {q: chain[5]})
        self.assertEqual(rc.legacy_current_decision(chain, q)['id'], 'd6')  # whichever assessment it was recorded on
        self.assertIsNone(rc.legacy_current_decision(chain[:5], q))  # a revoke is no current decision
        self.assertIsNone(rc.legacy_current_decision([dict(chain[0], invalidated=True)], p))
        self.assertEqual(rc.legacy_current_decisions([dict(chain[0], invalidated=True)], a), {})
        self.assertEqual(rc.legacy_decision_root(chain, chain[5])['id'], 'd4')
        self.assertEqual(rc.legacy_decision_root(chain, chain[0])['id'], 'd1')
        self.assertEqual(rc.legacy_decision_root(chain[5:], chain[5])['id'], 'd6')  # a link out of them ends the walk
        for records, expected in (([], True), ([('astra', 'not_configured', False)], True),
                                  ([('astra', 'read', False)], None), ([('astra', 'read', True)], True),
                                  ([('astra', 'failed', False), ('fable', 'read', False)], None),
                                  ([('astra', 'read', False), ('astra', 'failed', False)], True),
                                  ([('corti', 'read', False)], True), ([('fable', 'read', True), ('fable', 'read', False)],
                                                                       None)):
            with self.subTest(records=records):
                self.assertEqual(rc.legacy_final(records), expected)


class LegacyRowsSql(unittest.TestCase):
    """DECISIONS D338 and D339: Check.legacy_rows reads each update-pending encounter's stored legacy state by the
    runner's own SQL; only UUIDs reach it, and no statement runs without one. (Its statements run on real rows in
    LegacyRowsOnTheDatabase.)"""

    def test_only_uuids_reach_the_sql_and_none_runs_without_one(self):
        check = rc.Check.__new__(rc.Check)
        statements = []

        def sql(statement, **kwargs):
            statements.append((statement, kwargs))
            return []
        check.instance = SimpleNamespace(sql=sql)
        got = check.legacy_rows([A21_ENCOUNTER, BEFORE_ANALYZE, "x'); drop table studio_proposal; --", 'e1', None])
        self.assertEqual(got, {})
        self.assertEqual(len(statements), 7)
        for statement, kwargs in statements:
            self.assertNotIn('drop table', statement)
            self.assertEqual(kwargs, {})  # the read-only session, as every other read
            self.assertIn(f"'{A21_ENCOUNTER}','{BEFORE_ANALYZE}'", statement)
        statements.clear()
        self.assertEqual(check.legacy_rows(['e1', None]), {})
        self.assertEqual(statements, [])

    def test_the_switch_back_reads_every_encounter_the_close_names_or_the_note_lists(self):
        self.assertEqual(rc.pending_sets({A21_ENCOUNTER: ['reconciled_unknown']},
                                         {'update_pending': [AFTER_ANALYZE, A21_ENCOUNTER]}),
                         ({A21_ENCOUNTER: ['reconciled_unknown']}, [A21_ENCOUNTER, AFTER_ANALYZE]))
        self.assertEqual(rc.pending_sets(None, None), ({}, []))
        self.assertEqual(rc.pending_sets({A21_ENCOUNTER: 'reconciled_unknown'}, {'update_pending': 'x'}),
                         ({A21_ENCOUNTER: []}, []))


def _psql(value) -> str:
    """A value as psql -At prints it: NULL as nothing, a boolean t or f, anything else its text."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 't' if value else 'f'
    return str(value)


class LegacyStateRows(FableRows):
    """A legacy encounter of every decision kind on the ops suite's test database, pending after analyze (9.4 row 2: a
    gemini context current, its legacy assessment on the earlier context), beside an OLDER legacy assessment of its
    revision and a v2 assessment of it; its workspace's memberships; and Check.legacy_rows run on it, its statements
    executed on those rows exactly as written (psql's text). Synthetic. Helpers only: no test of its own."""

    def sql(self, statement, **kwargs):
        from django.db import connection
        self.statements.append(statement)
        with connection.cursor() as cursor:
            cursor.execute(statement)
            return [[_psql(value) for value in row] for row in cursor.fetchall()]

    def read(self, *encounters):
        check = rc.Check.__new__(rc.Check)
        self.statements = []
        check.instance = SimpleNamespace(sql=self.sql)
        return check.legacy_rows([str(encounter.pk) for encounter in encounters])

    def legacy_assessment(self, encounter, context, *, participants=(), current=True, request='e'):
        from studio import models
        routing = models.RoutingRun.objects.create(revision=encounter.current_revision, version='synthetic', result={},
                                                   sha256='0' * 64)
        made = models.Assessment.objects.create(
            encounter=encounter, revision=encounter.current_revision, context=context, routing=routing,
            profiles_version='synthetic@1', engine_version='cpt-studio-validation@10', sha256='1' * 64,
            provider_run=self.made_run(encounter, request=request), participants=list(participants))
        if current:
            models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context, current_assessment=made)
        return made

    def proposal(self, assessment, key, code, bucket, status, position, *, family='gi.colonoscopy', reinstatable=False,
                 checks=(), support=None):
        from studio import models
        return models.Proposal.objects.create(
            assessment=assessment, key=key, code=code, code_kind='cpt', family=family, profile_version='synthetic@1',
            fingerprint=f'{code}{key}'.ljust(64, '0')[:64], position=position, bucket=bucket, status=status,
            reinstatable=reinstatable, checks=list(checks), support=support or {})

    def decide(self, proposal, action, *, assessment=None, carried_from=None, invalidated=False):
        from studio import models
        assessment = assessment or proposal.assessment
        made = models.Decision.objects.create(
            encounter=assessment.encounter, assessment=assessment, revision=assessment.revision, proposal=proposal,
            action=action, reviewer=self.user, reviewer_kind='human', profile_version='synthetic@1',
            proposal_fingerprint=proposal.fingerprint, carried_from=carried_from)
        if invalidated:
            models.DecisionInvalidation.objects.create(decision=made, reason='Synthetic invalidation.')
        return made

    def ask(self, proposal, fact, *, family=None, state='open', answer=None, scope='proposal'):
        from studio import models
        return models.Clarification.objects.create(
            encounter=proposal.assessment.encounter, assessment=proposal.assessment, proposal=proposal, scope=scope,
            family=proposal.family if family is None else family, fact=fact, question='Synthetic?', reason='Synthetic.',
            state=state, answer=answer)

    def answer(self, assessment, code, fact, *, family='gi.colonoscopy', value='not_documented', question='',
               revoked=False):
        from studio import models
        made = models.MemberAnswer.objects.create(encounter=assessment.encounter, revision=assessment.revision,
                                                  assessment=assessment, fact=fact, family=family, code=code, value=value,
                                                  answered_by=self.user, question=question)
        if revoked:
            models.MemberAnswerRevocation.objects.create(answer=made, reason='withdrawn', revoked_by=self.user)
        return made

    def build(self, tag='d339'):
        """The encounter (module docstring); returns (encounter, current assessment, {name: proposal},
        {name: decision}, {name: membership})."""
        from studio import interpretation, models
        encounter = self.extracted(self.encounter(tag))
        self.user = encounter.created_by
        workspace = encounter.workspace
        people = {name: models.User.objects.create(username=f'synthetic-{tag}-{name}') for name in ('r', 'v', 'g')}
        memberships = {'owner': models.Membership.objects.create(user=self.user, workspace=workspace, role='owner'),
                       'reviewer': models.Membership.objects.create(user=people['r'], workspace=workspace, role='reviewer'),
                       'viewer': models.Membership.objects.create(user=people['v'], workspace=workspace, role='viewer'),
                       'inactive': models.Membership.objects.create(user=people['g'], workspace=workspace,
                                                                    role='reviewer', active=False)}
        context = self.context(encounter)
        older = self.legacy_assessment(encounter, context, current=False, request='o')
        current = self.legacy_assessment(encounter, context, participants=[
            {'name': 'astra', 'state': 'read', 'peer_state': 'read'}, {'name': 'corti', 'state': 'read'}])
        made = self.current_inventory(encounter)
        gemini = self.context(encounter, version=interpretation.CONTEXT_VERSION_V2, inventory=made)
        v2 = self.assessment(encounter, gemini, engine_version=interpretation.ENGINE_VERSION_V3,
                             provider_run=self.made_run(encounter, request='v'), inventory=made, current=False)
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=gemini)  # 9.4: pending after analyze
        o = {'old': self.proposal(older, 'sel:0', '45378', 'selected', 'ready', 0),
             'old2': self.proposal(older, 'sel:1', '45380', 'selected', 'ready', 1)}
        self.proposal(v2, 'sel:0', '45378', 'selected', 'ready', 0)
        p = {'undecided': self.proposal(current, 'sel:0', '45378', 'selected', 'ready', 0),
             'approved': self.proposal(current, 'sel:1', '45380', 'selected', 'ready', 1),
             'rejected': self.proposal(current, 'sel:2', '45385', 'selected', 'ready', 2),
             'confirmed': self.proposal(current, 'exc:0', '43239', 'excluded', 'excluded', 3, family='gi.egd',
                                        reinstatable=True),
             'reinstated': self.proposal(current, 'exc:1', '43249', 'excluded', 'excluded', 4, family='gi.egd',
                                         reinstatable=True,
                                         checks=[{'id': 'review.reinstatement', 'status': 'pass', 'label': 'x'}]),
             'waiting': self.proposal(current, 'exc:2', '43251', 'excluded', 'excluded', 5, family='gi.egd',
                                      reinstatable=True,
                                      checks=[{'id': 'review.reinstatement', 'status': 'fail', 'detail': 'Synthetic.'}]),
             'revoked': self.proposal(current, 'sel:3', '45390', 'selected', 'ready', 6),
             'answered': self.proposal(current, 'sel:4', '45381', 'selected', 'needs_clarification', 7),
             'withdrawn': self.proposal(current, 'sel:5', '45388', 'selected', 'needs_clarification', 8),
             'fingerprinted': self.proposal(current, 'sel:6', '45384', 'selected', 'needs_clarification', 9),
             'read': self.proposal(current, 'sel:7', '45386', 'selected', 'needs_clarification', 10),
             'marker': self.proposal(current, 'exc:3', '45391', 'excluded', 'excluded', 11, support={
                 'answered': {'fact': 'extent', 'value': 'cannot_confirm', 'answers': ['synthetic']}}),
             'plain': self.proposal(current, 'exc:4', 'G8754', 'excluded', 'excluded', 12, family='gi.unsupported'),
             'carried': self.proposal(current, 'sel:8', '45392', 'selected', 'ready', 13),
             'crossed': self.proposal(current, 'sel:9', '45393', 'selected', 'ready', 14),
             'invalidated': self.proposal(current, 'sel:10', '45394', 'selected', 'ready', 15),
             'alternative': self.proposal(current, 'alt:0', '99213', 'alternative', 'informational', 16,
                                          family='gi.office_em')}
        d = {'old': self.decide(o['old'], 'approve')}
        d['carry_root'] = self.decide(o['old2'], 'approve')
        d['approved'] = self.decide(p['approved'], 'approve')
        d['rejected'] = self.decide(p['rejected'], 'reject')
        d['confirmed'] = self.decide(p['confirmed'], 'confirm')
        d['reinstated'] = self.decide(p['reinstated'], 'reinstate')
        d['waiting'] = self.decide(p['waiting'], 'reinstate')
        d['revoked'] = self.decide(p['revoked'], 'approve')
        d['revoke'] = self.decide(p['revoked'], 'revoke')
        d['carried'] = self.decide(p['carried'], 'approve', carried_from=d['carry_root'])
        d['crossed'] = self.decide(p['crossed'], 'approve', assessment=older)  # recorded on another assessment
        d['invalidated'] = self.decide(p['invalidated'], 'approve', invalidated=True)
        for name in ('answered', 'withdrawn', 'fingerprinted'):
            self.ask(p[name], 'extent')
        self.ask(p['plain'], 'extent', state='withdrawn')
        self.ask(p['undecided'], 'completion', scope='service')
        self.answer(current, '45381', 'extent')
        self.answer(current, '45388', 'extent', revoked=True)
        self.answer(current, '45384', 'extent', question='f' * 64)
        read = self.answer(current, '45386', 'extent')
        self.ask(p['read'], 'extent', state='answered', answer=read)
        return encounter, current, p, d, memberships


class LegacyRowsOnTheDatabase(LegacyStateRows):
    """DECISIONS D338R-2: Check.legacy_rows' statements run on real rows - an encounter whose current legacy assessment
    stands beside an older legacy assessment of the same revision and a v2 assessment of it, with decisions including a
    revoked chain, a carry and an invalidation, member answers and its workspace's memberships. Only the current
    assessment's rows are its stored rows (round 1's SQL mutants ML1 and ML2 read another assessment's)."""

    def test_the_stored_legacy_state_is_the_current_assessments_alone(self):
        encounter, current, p, d, memberships = self.build()
        lone = self.extracted(self.encounter('lone'))  # no current assessment
        entry = self.read(encounter, lone)[str(encounter.pk)]
        self.assertEqual(len(self.statements), 7)
        self.assertEqual(rc._entry_problems(entry), [])
        self.assertEqual((entry['assessment'], entry['engine_version'], entry['event_inventory'], entry['revision_current'],
                          entry['final']), (str(current.pk), 'cpt-studio-validation@10', False, True, True))
        self.assertEqual(set(entry['proposals']), {str(item.pk) for item in p.values()})  # neither the older nor the v2's
        self.assertEqual(len(entry['v2_proposals']), 1)
        self.assertNotIn(entry['v2_proposals'][0], entry['proposals'])
        rows = {name: entry['proposals'][str(item.pk)] for name, item in p.items()}
        self.assertEqual(rows['answered'], {'status': 'needs_clarification', 'bucket': 'selected', 'reinstatable': False,
                                            'code': '45381', 'family': 'gi.colonoscopy', 'key': 'sel:4',
                                            'reinstatement_clear': False, 'answered_away': False, 'answered_fact': '',
                                            'answered_value': '', 'open_facts': [['extent', 'gi.colonoscopy']]})
        self.assertEqual([name for name, row in rows.items() if row['reinstatement_clear']], ['reinstated'])
        self.assertEqual([(name, row['answered_fact'], row['answered_value']) for name, row in rows.items()
                          if row['answered_away']], [('marker', 'extent', 'cannot_confirm')])
        self.assertEqual(rows['plain']['open_facts'], [])  # a withdrawn question is not open
        self.assertEqual(rows['undecided']['open_facts'], [])  # a service-scoped question is not the code's own
        self.assertEqual({item['id'] for item in entry['decisions']}, {str(item.pk) for item in d.values()})
        self.assertEqual([item['sequence'] for item in entry['decisions']], sorted(item['sequence'] for item in entry['decisions']))
        by_id = {item['id']: item for item in entry['decisions']}
        self.assertEqual(by_id[str(d['carried'].pk)]['carried_from'], str(d['carry_root'].pk))
        self.assertTrue(by_id[str(d['invalidated'].pk)]['invalidated'])
        self.assertEqual(by_id[str(d['crossed'].pk)]['assessment'], str(d['old'].assessment_id))
        self.assertEqual(sorted((item['code'], item['fingerprinted'], item['read'], item['revoked'])
                                for item in entry['answers']),
                         [('45381', False, False, False), ('45384', True, False, False), ('45386', False, True, False),
                          ('45388', False, False, True)])
        self.assertEqual(entry['memberships'], {str(memberships['owner'].pk): True, str(memberships['reviewer'].pk): True,
                                                str(memberships['viewer'].pk): False,
                                                str(memberships['inactive'].pk): False})
        self.assertEqual(self.read(lone)[str(lone.pk)]['assessment'], None)
        self.assertEqual(rc._entry_problems(self.read(lone)[str(lone.pk)]), ['it has no current assessment'])

    def test_free_text_reads_whole_and_finality_follows_the_stored_entries(self):
        from studio import models
        encounter = self.extracted(self.encounter('text'))
        self.user = encounter.created_by
        context = self.context(encounter)
        current = self.legacy_assessment(encounter, context, participants=[{'name': 'astra', 'state': 'read'}])
        self.proposal(current, 'sel:0\tx', '45\n378', 'selected', 'ready', 0, family='gi.colon\toscopy')
        entry = self.read(encounter)[str(encounter.pk)]
        self.assertEqual(rc._entry_problems(entry), [])
        self.assertEqual([(row['code'], row['family'], row['key']) for row in entry['proposals'].values()],
                         [('45\n378', 'gi.colon\toscopy', 'sel:0\tx')])
        self.assertIsNone(entry['final'])  # owed only if Astra is configured now: not read
        models.Encounter.objects.filter(pk=encounter.pk).update(current_revision=None)
        self.assertFalse(self.read(encounter)[str(encounter.pk)]['revision_current'])


class D339ParityOnTheDatabase(LegacyStateRows):
    """DECISIONS D339: where this tree's legacy path is c2e53f8e's own (the NOTES' source diff: current_decisions differs
    only by annotations; _current_decision, decision_root, is_final, review_view.review_view and stored_from,
    questions.answered_away, review._reinstatement_clear and _standing are identical), the port equals this tree's own
    functions on real legacy rows of every decision kind - none, approve, reject, confirm, reinstate (check passing and
    not), a revoked approve, an invalidated one, a carried one, one recorded on another assessment, an answer that leaves
    a needed detail unavailable, a withdrawn answer, a fingerprinted one, one the assessment read, the engine's marker."""

    def test_the_port_equals_the_trees_own_functions_on_every_row(self):
        from studio import models, review
        from studio.validation import questions, review_view
        encounter, current, p, d, _ = self.build()
        entry = self.read(encounter)[str(encounter.pk)]
        self.assertEqual(rc._entry_problems(entry), [])
        # current_decisions (review.py:219-227)
        port = {proposal: item['id'] for proposal, item in rc.legacy_current_decisions(entry['decisions'],
                                                                                      entry['assessment']).items()}
        tree = {str(proposal): str(item.pk) for proposal, item in review.current_decisions(current).items()}
        self.assertEqual(port, tree)
        self.assertEqual(set(tree), {str(p[name].pk) for name in ('approved', 'rejected', 'confirmed', 'reinstated',
                                                                   'waiting', 'carried')})
        for name, proposal in p.items():
            with self.subTest(proposal=name):
                # _current_decision (review.py:230-234)
                mine = rc.legacy_current_decision(entry['decisions'], str(proposal.pk))
                theirs = review._current_decision(proposal)
                self.assertEqual(mine['id'] if mine else None, str(theirs.pk) if theirs else None)
                row = entry['proposals'][str(proposal.pk)]
                # questions.answered_away (questions.py:94-103) and review._reinstatement_clear (review.py:587-590)
                self.assertEqual(row['answered_away'], questions.answered_away(proposal))
                self.assertEqual(row['reinstatement_clear'], review._reinstatement_clear(proposal))
        self.assertEqual(rc.legacy_current_decision(entry['decisions'], str(p['crossed'].pk))['id'], str(d['crossed'].pk))
        # decision_root (review.py:1529-1534)
        for item in entry['decisions']:
            self.assertEqual(rc.legacy_decision_root(entry['decisions'], item)['id'],
                             str(review.decision_root(models.Decision.objects.get(pk=item['id'])).pk))
        # _standing (review.py:247-251) and the answers the assessment read itself (review.py:330-331)
        self.assertEqual({item['id'] for item in entry['answers'] if not item['revoked']},
                         {str(item.pk) for item in review._standing(current)})
        read = {str(pk) for pk in current.clarifications.filter(state=models.Clarification.ANSWERED,
                                                                answer__isnull=False).values_list('answer_id', flat=True)}
        self.assertEqual({item['id'] for item in entry['answers'] if item['read']}, read)
        # is_final (review.py:2077-2084): where the stored entries settle it, the port is the tree's
        self.assertTrue(entry['final'])
        self.assertTrue(review.is_final(current))
        # the DETAIL_UNAVAILABLE derivation (review_view.py:505-717, identical): the tree's own overlay over the tree's own
        # stored rows, the current decisions and the answers c2e53f8e's bind gives it (questions.bind, identical: the
        # standing answers the assessment did not read, bound by their key when they carry no fingerprint)
        current_map = review.current_decisions(current)
        clarifications = {}
        for row in current.clarifications.all():
            clarifications.setdefault(row.proposal_id, []).append(row)
        stored = [review_view.stored_from(item, clarifications.get(item.pk, [])) for item in current.proposals.all()]
        decided = {item.key: review_view.Decided(current_map[item.pk].action) for item in current.proposals.all()
                   if item.pk in current_map}
        standing = [item for item in review._standing(current) if str(item.pk) not in read]
        bound = [{'code': item.code, 'family': item.family, 'fact': item.fact, 'value': item.value} for item in standing
                 if not item.question or item.fact in questions.KEY_BOUND_FACTS]
        views = review_view.review_view(stored, decided, services=None, answers=bound)
        unbound = review_view.review_view(stored, decided, services=None, answers=[
            {'code': item.code, 'family': item.family, 'fact': item.fact, 'value': item.value} for item in standing])
        expected = rc.legacy_expected(entry)
        for name, proposal in p.items():
            with self.subTest(overlay=name):
                state = expected[str(proposal.pk)]['unavailable'][0]
                reason = views[proposal.key].reason
                if state == 'unread':  # it turns on the binding the runner does not read: either way is c2e53f8e's
                    self.assertEqual(name, 'fingerprinted')
                    self.assertEqual((reason, unbound[proposal.key].reason), ('', 'detail_unavailable'))
                    continue
                self.assertEqual(reason == 'detail_unavailable', state == 'unavailable')
                if state == 'available' and proposal.bucket == 'selected':
                    self.assertEqual(views[proposal.key].status, expected[str(proposal.pk)]['view_status'])
        self.assertEqual({name for name, proposal in p.items() if expected[str(proposal.pk)]['unavailable'][0] ==
                          'unavailable'}, {'answered', 'marker'})

    def test_finality_the_stored_entries_do_not_settle_turns_on_the_configured_participants(self):
        from studio import review
        encounter = self.extracted(self.encounter('final'))
        self.user = encounter.created_by
        current = self.legacy_assessment(encounter, self.context(encounter),
                                         participants=[{'name': 'astra', 'state': 'read'}])
        self.assertIsNone(self.read(encounter)[str(encounter.pk)]['final'])
        self.assertTrue(review.is_final(current))  # no participant configured here
        with mock.patch('studio.participants.configured', return_value=('astra',)):
            self.assertFalse(review.is_final(current))  # Astra configured: its peer stage is owed


if __name__ == '__main__':
    unittest.main()
