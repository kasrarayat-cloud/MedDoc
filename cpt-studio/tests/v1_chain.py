"""The v1 chain, for TESTS ONLY (docs/gemini-migration/FINAL-V2.md 8.0 and 8.1 step 5b, the switch; as
tests/legacy_chain.py is for the legacy reader).

Step 5b switches the pipeline to design v2: the interpret stage reads pass 1 (gemini-events@2), the appraise stage pass
2, and an EventInventory is read at the v2 version pair; v1's one-pass reading (gemini-events@1, design/FINAL.md 6.3)
no longer runs on the product, and nothing in the product reads a setting, a variable or a file to take it. The
mechanics suites written against v1 - the doors, the send discipline, Stop, Resume, reconcile, the retry door, the
member's saves and the reports, each over ONE RECORDED v1 SYNTHETIC INTERPRETATION PER FIXTURE DOCUMENT
(tests.test_pipeline_api.RecordedInterpretation, tests.test_pipeline_interpret.InterpretCase) - keep running as the
record of v1's mechanics through this module: it puts v1's reading back, for the test that asks for it and only while
it runs, by replacing ONE seam studio.jobs names for it (``_v1_chain``: the reading's versions, its interpreter, its
read child and its derive and assess read v1's). Everything else is the product's own: the amendment's automatic update
(FINAL-V2 amendment 1) runs on the v1 chain exactly as on v2's.

The sentinel (FINAL-V2 5.7 measure 1, step 6a) denies the 17 retired v1 modules whole as the RETIRED kind, and the v1
chain's stages run them under new_path scopes as v1 did; so while the chain is on, its retired code objects are not
armed (sentinel.retired_unarmed, the sentinel's test-only seam for this module), and this record of v1's mechanics
counts what v1's sentinel counted - the legacy reader - with the D22 record v1 wrote.

Usage::

    from tests.v1_chain import v1_chain

    with v1_chain():
        ...drive the pipeline...

    class SomeMechanicsTests(V1Chain, TestCase):  # the mixin form: every test of the class, from its setUp on
        ...
"""
import contextlib
from unittest import mock

from studio import jobs
from studio.interpretation import sentinel


@contextlib.contextmanager
def v1_chain():
    """The v1 chain while the block runs (the seam studio.jobs._v1_chain answers True)."""
    with mock.patch.object(jobs, '_v1_chain', return_value=True), sentinel.retired_unarmed():
        yield


def start(test_case):
    """Enter the v1 chain for ``test_case``'s test, until its cleanups run (a setUp's or a mixin's call)."""
    patcher = mock.patch.object(jobs, '_v1_chain', return_value=True)
    patcher.start()
    test_case.addCleanup(patcher.stop)
    test_case.enterContext(sentinel.retired_unarmed())  # the retired codes armed again at the test's cleanup


class V1Chain:
    """A TestCase mixin: every test of the class runs the v1 chain, from before its setUp runs."""

    def _callSetUp(self):
        start(self)
        super()._callSetUp()
