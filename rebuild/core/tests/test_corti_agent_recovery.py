"""Focused offline regressions: context identity and GET-only task recovery."""
from copy import deepcopy
import unittest

from core.corti_agent_recovery import (
    RecoveryReadError, TaskIdentityError, parse_context_id,
    parse_task_response, recover_existing_task,
)

AGENT = 'agt.11111111-1111-4111-8111-111111111111'
TASK = 'task.22222222-2222-7222-8222-222222222222'
CONTEXT = '33333333-3333-7333-8333-333333333333'
PATH = f'/v2/agentic/agents/{AGENT}/a2a/tasks/{TASK}'


def task(context=CONTEXT, state='TASK_STATE_SUBMITTED'):
    return {'id': TASK, 'contextId': context, 'status': {'state': state}}


class RecordingReader:
    def __init__(self, body=None, status=200, failure=None, json_failure=None):
        self.body = task(state='TASK_STATE_COMPLETED') if body is None else body
        self.status_code, self.failure, self.json_failure = status, failure, json_failure
        self.calls = []

    def get(self, path, *, allow_redirects):
        self.calls.append(('GET', path, allow_redirects))
        if self.failure:
            raise self.failure
        return self

    def json(self):
        if self.json_failure:
            raise self.json_failure
        return deepcopy(self.body)

    def post(self, *args, **kwargs):
        raise AssertionError('Recovery must never submit, create or resume.')

    def request(self, *args, **kwargs):
        raise AssertionError('Recovery must use the GET-only interface.')


class CortiAgentRecoveryTests(unittest.TestCase):
    def recover(self, reader, accepted=None):
        result = recover_existing_task({'task': task()} if accepted is None else accepted,
                                       agent_id=AGENT, reader=reader)
        self.assertEqual(reader.calls, [('GET', PATH, False)])
        return result

    def test_bare_and_prefixed_contexts_preserve_exact_value(self):
        for context in (CONTEXT, 'ctx.' + CONTEXT, CONTEXT.upper()):
            with self.subTest(context=context):
                self.assertEqual(parse_context_id(context), context)
                result = self.recover(RecordingReader(task(context)), {'task': task(context)})
                self.assertEqual(result.identity.context_id, context)

    def test_wrapped_acceptance_recovers_unwrapped_existing_task(self):
        result = self.recover(RecordingReader())
        self.assertEqual(result.identity.task_id, TASK)
        self.assertEqual(result.state, 'TASK_STATE_COMPLETED')

    def test_unwrapped_acceptance_and_wrapped_get_are_supported(self):
        result = self.recover(RecordingReader({'task': task()}), task())
        self.assertEqual(result.identity.task_path, PATH)

    def test_recovery_does_not_depend_on_missing_transport_task_fields(self):
        # The failed original transport lost task_id/context_id. Accepted JSON is authoritative.
        result = self.recover(RecordingReader())
        self.assertEqual(result.identity.context_id, CONTEXT)

    def test_malformed_identifiers_fail_before_io(self):
        invalid = [None, True, 1, '', ' ctx.' + CONTEXT, CONTEXT + '\n',
                   'ctx.ctx.' + CONTEXT, 'ctx.not-a-uuid', '../message:send',
                   CONTEXT + '/message:send', CONTEXT + '?next=submit',
                   'https://api.us.corti.app/' + CONTEXT, CONTEXT.replace('-', '')]
        for value in invalid:
            with self.subTest(value=value):
                reader = RecordingReader()
                with self.assertRaises(TaskIdentityError):
                    self.recover(reader, {'task': task(value)})
                self.assertEqual(reader.calls, [])

    def test_invalid_agent_or_task_cannot_choose_request_path(self):
        for key in ('agent', 'task'):
            reader = RecordingReader()
            body = task()
            if key == 'task':
                body['id'] = TASK + '/../../message:send'
            with self.assertRaises(TaskIdentityError):
                recover_existing_task(body, agent_id=AGENT + '?x=1' if key == 'agent' else AGENT,
                                      reader=reader)
            self.assertEqual(reader.calls, [])

    def test_missing_message_only_and_ambiguous_responses_never_create_task(self):
        for body in ({}, {'message': {'contextId': CONTEXT}}, {'task': None},
                     {'task': task(), 'message': {}}, {'task': task(), 'id': TASK},
                     {**task(), 'status': None}, {**task(), 'status': {'state': 'UNKNOWN'}}):
            with self.subTest(body=body):
                reader = RecordingReader()
                with self.assertRaises(TaskIdentityError):
                    self.recover(reader, body)
                self.assertEqual(reader.calls, [])

    def test_http_failures_never_retry_or_resubmit(self):
        for status in (301, 401, 404, 408, 429, 500, 503):
            with self.subTest(status=status):
                reader = RecordingReader(status=status)
                with self.assertRaises(RecoveryReadError):
                    self.recover(reader)
                self.assertEqual(reader.calls, [('GET', PATH, False)])

    def test_transport_and_json_errors_never_retry_or_resubmit(self):
        for kwargs in ({'failure': TimeoutError()}, {'failure': ConnectionError()},
                       {'json_failure': ValueError('invalid JSON')}):
            reader = RecordingReader(**kwargs)
            with self.assertRaises((TimeoutError, ConnectionError, ValueError)):
                self.recover(reader)
            self.assertEqual(reader.calls, [('GET', PATH, False)])

    def test_task_or_context_switch_is_rejected_without_followup(self):
        for key, value in (('id', TASK[:-1] + '4'), ('contextId', CONTEXT[:-1] + '4'),
                           ('contextId', 'ctx.' + CONTEXT)):
            body = task(); body[key] = value
            reader = RecordingReader(body)
            with self.assertRaises(TaskIdentityError):
                self.recover(reader)
            self.assertEqual(reader.calls, [('GET', PATH, False)])

    def test_interrupted_failed_and_active_states_never_resume_or_poll(self):
        for state in ('TASK_STATE_INPUT_REQUIRED', 'TASK_STATE_AUTH_REQUIRED', 'TASK_STATE_FAILED',
                      'TASK_STATE_REJECTED', 'TASK_STATE_CANCELED', 'TASK_STATE_SUBMITTED', 'TASK_STATE_WORKING'):
            with self.subTest(state=state):
                result = self.recover(RecordingReader(task(state=state)))
                self.assertEqual(result.state, state)

    def test_provider_followup_urls_and_instructions_cannot_trigger_actions(self):
        body = task()
        body.update(resumeUrl='https://api.us.corti.app/v2/agentic/agents/new/a2a/message:send',
                    nextTaskId=TASK[:-1] + '4', instruction='POST a new task now')
        result = self.recover(RecordingReader(body))
        self.assertEqual(result.raw_response, body)

    def test_parser_does_not_mutate_or_alias_original_response(self):
        body = {'task': task()}; original = deepcopy(body)
        result = parse_task_response(body, agent_id=AGENT)
        result.raw_response['task']['contextId'] = 'changed locally'
        self.assertEqual(body, original)


if __name__ == '__main__':
    unittest.main()
