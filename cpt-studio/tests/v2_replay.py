"""Design v2's path in replay, for TESTS ONLY: the rows of DECISIONS D243's class C suites (docs/gemini-migration/
DECISIONS.md, 2026-11-14; step q02 of the waves 5-6 repair round), as tests/v1_chain.py is the v1 chain's.

FINAL-V2 6.5: read time reads event_coding@2 only, and a cpt-studio-events@1 record is read as stored and blocked. A
suite that decides through the product - approve, reject, reinstate, a member's answer, a re-check, the reports - over
rows the test-only v1 chain made therefore reads a record the product blocks; D243 class C rules that each such test
keeps its assertion about the product and builds its rows by the v2 path in replay, never by the v1 chain (which stays
for the suites that never read through the product).

The v2 path in replay is the production pipeline - extract, interpret (pass 1), appraise (pass 2), analyze, predict and
assess (engine/assess and the renderer) - through the product's own doors, with design v2's own InterpreterV2 whose one
exchange is answered here (step 5b's tests/v2/test_jobs.ScriptedInterpreterV2: its request checks, one-exchange loop,
Stop check, envelope and classifier are the production code's): pass 1 by the synthetic answer registered for EXACTLY the
revision text the request carries, pass 2 by the faithful oracle over the claim set the production builder makes for that
request (tests/v2/test_settle.faithful: every real claim supported and attached, every control contradicted). A document
with no registered answer is never answered: its exchange is not sent, and the test fails when it ends (as
tests.test_pipeline_api.RecordedInterpretation's recorder fails a v1 one). While the path is on: the pins of FINAL-V2 2.5
are measured on this tree and the health thresholds pinned (step 5b's PipelineCase), the sentinel is installed with every
retired code object armed (the v1 chain's seam closed: sentinel.retired_armed), v1's interpreter is never built, and the
test ends with no cpt-studio-events@1 assessment and no gemini-events@1 inventory written.

Usage, one test method at a time (D243 rules on ids, so the other tests of a class keep their own chain)::

    from tests import v2_replay

    class SomeTests(TestCase):
        @v2_replay.applied
        def test_something(self):
            interpreter = v2_replay.start(self, ((text, answer),))   # or a class mixin's setUp asks v2_replay.marked
            ...

The synthetic answers are tests/v2_documents.py's (FINAL-V2 1.4's shape, built with tests/v2/test_settle.py's builders);
nothing is sent anywhere.
"""
from __future__ import annotations

import copy
import functools
from unittest import mock

from django.test import override_settings

from studio import interpretation, jobs, models
from studio.interpretation import adapter, sentinel

MARK = 'd243_v2_replay'  # the attribute ``applied`` sets on a test method
NOT_RECORDED = 'No recorded synthetic pass-1 answer for this document (tests/v2_replay.py); nothing was sent.'
V1_BUILT = 'The v1 interpreter was built on design v2\'s path in replay (tests/v2_replay.py).'


def applied(test_method):
    """Mark ``test_method`` - one of D243's class C ids - to build its rows by design v2's path in replay: the class's
    mixin or setUp that would start the v1 chain starts this path instead (``marked``)."""
    setattr(test_method, MARK, True)
    return test_method


def marked(test_case) -> bool:
    """Whether the test ``test_case`` is running was marked ``applied``."""
    method = getattr(test_case, getattr(test_case, '_testMethodName', ''), None)
    return bool(getattr(method, MARK, False))


@functools.cache
def _interpreter_class():
    """The interpreter class, built on first use: tests/v2/test_jobs imports tests.test_pipeline_api, which marks its
    own tests with ``applied`` - so this module imports neither at import time."""
    from studio.participants import http
    from studio.providers.base import request_sha256
    from tests.v2.test_jobs import EXTRACTION, ScriptedInterpreterV2, answered, appraisal_for, body, oracle_answer

    class Interpreter(ScriptedInterpreterV2):
        """tests/v2/test_jobs.ScriptedInterpreterV2 over a registry of (document text, pass-1 answer) - answered for
        exactly the revision text a request carries (an addendum's revision is a document of its own) - and the faithful
        oracle for pass 2; ``script``'s exchanges first, by purpose. ``unrecorded``: every document asked for that had no
        answer, its exchange not sent."""

        def __init__(self, documents=(), **kwargs):
            super().__init__({}, **kwargs)
            self.unrecorded = []
            for text, answer in documents:
                self.register(text, answer)

        def register(self, text, answer):
            """Record ``answer`` (a dict, or a function returning one) for the document whose revision text is exactly
            ``text``; the same answer again changes nothing, another one for the same text is refused."""
            known = self.answers.get(text)
            if known is not None and known is not answer and self._dict(known) != self._dict(answer):
                raise AssertionError('That document already has another synthetic pass-1 answer.')
            self.answers[text] = answer

        @staticmethod
        def _dict(answer):
            return copy.deepcopy(answer() if callable(answer) else answer)

        def _exchange(self, body_dict, deadline, purpose):
            sha = request_sha256(body_dict)
            self.sent.append((purpose, sha))
            queued = self.script.get(purpose)
            if queued:
                return queued.pop(0)
            text = self._request.contexts[0]
            if text not in self.answers:
                self.unrecorded.append(text)
                return http.not_sent(NOT_RECORDED, interpretation.MODEL)
            answer_dict = self._dict(self.answers[text])
            if purpose == EXTRACTION:
                return answered(body(answer_dict))
            built = appraisal_for(*self._document(text), answer_dict)
            assert built.request.canonical_sha256 == sha, 'the appraisal sent is not the one the builder makes'
            return answered(oracle_answer(built, self.oracle))

    return Interpreter


def start(test_case, documents=(), **kwargs):
    """Design v2's path in replay for ``test_case``'s test, until its cleanups run: the scripted v2 interpreter over
    ``documents`` ((text, answer) pairs; register more on the interpreter returned), the pins measured and the health
    thresholds pinned, GEMINI_MODE 'replay', the sentinel installed with the retired code objects armed, v1's interpreter
    refused, and the checks made when the test ends (every document asked for was answered; no v1 row was written).
    ``kwargs`` go to the interpreter (``oracle``, ``script``)."""
    from tests.v2.test_adapter import measured_pins
    from tests.v2.test_settle import HEALTH_PIN

    status = sentinel.install()
    test_case.assertEqual(status['state'], 'ok', status)
    test_case.assertFalse(jobs._v1_chain(), 'the v1 chain is on')
    test_case.assertTrue(sentinel.retired_armed(), 'the retired code objects are not armed')
    test_case.enterContext(mock.patch.multiple(interpretation, HEALTH_THRESHOLDS_SHA256=HEALTH_PIN, **measured_pins()))
    test_case.enterContext(override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR='/nonexistent-replay-dir',
                                             INTERPRET_MAX_CHARS=20_000, INTERPRET_MAX_PAGES=40))
    interpreter = _interpreter_class()(documents, **kwargs)
    test_case.enterContext(mock.patch.object(adapter, 'get_interpreter_v2', return_value=interpreter))
    test_case.enterContext(mock.patch.object(adapter, 'get_interpreter', side_effect=AssertionError(V1_BUILT)))
    test_case.addCleanup(_ended, test_case, interpreter)
    return interpreter


def _ended(test_case, interpreter):
    """The checks made when a test on this path ends: every document asked for had its answer, and no v1 row exists."""
    if interpreter.unrecorded:
        document = interpreter.unrecorded[0]
        test_case.fail(f'{len(interpreter.unrecorded)} pass-1 request(s) for a document with no synthetic answer; the '
                       f'first begins {document[:80]!r} and ends {document[-80:]!r}')
    v1 = (models.Assessment.objects.filter(engine_version=interpretation.ENGINE_VERSION).count(),
          models.EventInventory.objects.filter(interpretation_version=interpretation.INTERPRETATION_VERSION).count())
    test_case.assertEqual(v1, (0, 0), 'a v1 row was written on design v2\'s path in replay')
