"""Unit tests for ops/rollback_check.py, the D15 rollback runtime test (design/FINAL.md 12.3; design/ADJUDICATION.md
P-1): the comparison it judges by, and the refusals it makes before anything runs. No Docker, database or network:
the one-shot transport is replaced where a test reaches it.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v
"""
import base64
import contextlib
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


if __name__ == '__main__':
    unittest.main()
