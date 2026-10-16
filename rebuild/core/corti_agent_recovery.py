"""Parse retained Corti task identities and recover one existing task via GET.

No authentication, network client, creation, submission, polling or retry logic.
The reader is injected; offline callers supply a saved response, never a client.
"""
from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Protocol

_UUID = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
_STATES = frozenset({
    'TASK_STATE_SUBMITTED', 'TASK_STATE_WORKING', 'TASK_STATE_COMPLETED',
    'TASK_STATE_FAILED', 'TASK_STATE_CANCELED', 'TASK_STATE_REJECTED',
    'TASK_STATE_INPUT_REQUIRED', 'TASK_STATE_AUTH_REQUIRED',
})


class TaskIdentityError(ValueError):
    pass


def _identifier(value, prefix, *, bare_allowed=False):
    pattern = (rf'(?:{re.escape(prefix)}\.)?' if bare_allowed else rf'{re.escape(prefix)}\.') + _UUID
    if type(value) is not str or not re.fullmatch(pattern, value):
        raise TaskIdentityError(f'Invalid {prefix} identifier.')
    # Preserve the server's value exactly: do not add a prefix or normalize case.
    return value


def parse_context_id(value):
    """Accept the observed bare UUID and documented ctx.UUID form, unchanged."""
    return _identifier(value, 'ctx', bare_allowed=True)


@dataclass(frozen=True)
class TaskIdentity:
    agent_id: str
    task_id: str
    context_id: str

    def __post_init__(self):
        _identifier(self.agent_id, 'agt')
        _identifier(self.task_id, 'task')
        parse_context_id(self.context_id)

    @property
    def task_path(self):
        return f'/v2/agentic/agents/{self.agent_id}/a2a/tasks/{self.task_id}'


@dataclass(frozen=True)
class TaskSnapshot:
    identity: TaskIdentity
    state: str
    raw_response: dict


def parse_task_response(response, *, agent_id, expected=None):
    """Parse either a message:send task wrapper or a direct task GET response."""
    if type(response) is not dict or 'message' in response:
        raise TaskIdentityError('An accepted task response is required.')
    if 'task' in response:
        if any(key in response for key in ('id', 'contextId', 'status')):
            raise TaskIdentityError('Ambiguous task response.')
        task = response['task']
    else:
        task = response
    if type(task) is not dict or type(task.get('status')) is not dict:
        raise TaskIdentityError('Task identity and status are required.')
    identity = TaskIdentity(agent_id, task.get('id'), task.get('contextId'))
    if expected is not None and identity != expected:
        raise TaskIdentityError('Response does not belong to the existing task/context.')
    state = task['status'].get('state')
    if type(state) is not str or state not in _STATES:
        raise TaskIdentityError('Unknown task state; no recovery action inferred.')
    return TaskSnapshot(identity, state, deepcopy(response))


class TaskReadResponse(Protocol):
    status_code: int

    def json(self) -> dict: ...


class TaskReader(Protocol):
    def get(self, path: str, *, allow_redirects: bool) -> TaskReadResponse: ...


class RecoveryReadError(RuntimeError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__('Existing-task read failed; no retry or resubmission.')


def recover_existing_task(accepted_response, *, agent_id, reader: TaskReader):
    """Exactly one GET of the accepted identity, or zero I/O for invalid input.

    A reader must itself disable transport retries. HTTP/transport/JSON failures
    propagate without fallback; interrupted/failed states never trigger messages.
    No provider-supplied URL or follow-up instruction can choose the read target.
    """
    accepted = parse_task_response(accepted_response, agent_id=agent_id)
    response = reader.get(accepted.identity.task_path, allow_redirects=False)
    if response.status_code != 200:
        raise RecoveryReadError(response.status_code)
    return parse_task_response(response.json(), agent_id=agent_id, expected=accepted.identity)
