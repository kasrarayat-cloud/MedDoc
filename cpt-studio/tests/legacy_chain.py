"""The legacy chain, for TESTS ONLY (design/FINAL.md 14.6 and 16.14; slices S09, S10 and S15).

The Gemini migration makes Gemini the only interpreter: extract queues the interpret stage, analyze derives a
gemini-context@1 context from the event inventory, and a stage given a context that is not a gemini context ends
StageCancelled (FINAL 6.2-6.5, 9). The existing suites that assert the LEGACY reader's outcomes - what gi.context,
gi.detect and the validation engine read in a document - keep running as legacy regression tests through this module:
it puts the legacy chain back, for the test that asks for it and only while it runs, by replacing the seams studio.jobs
names for it. No production switch exists: nothing in the product reads a setting, a variable or a file to take this
path, and the only way to reach it is mock.patch from a test.

The seams (studio/jobs.py), each replaced by its pre-migration behaviour:
- ``_after_extract``: extract queues the legacy analyze ('analyze:<revision>'), as before;
- ``STAGES[Job.ANALYZE]``: ``legacy_stage_analyze``, the pre-migration stage verbatim - the archived bounded children
  (_analyze_child: the mention gate, gi.context.extract_context, gi.detect.route), _record_context and _record_routing;
- ``_earlier_reading``: the legacy ``_remade_context`` (a context an earlier gi-context version recorded is remade),
  where the new image ends such a stage StageCancelled;
- ``_new_path_owed``: never - a Resume or a reconciliation works as before rather than interpreting the revision first;
- ``_legacy_reading_allowed`` (S10): always - the assess, the participants' first readings and peer reviews and the
  second review run their legacy branches on a legacy context (the legacy child, the legacy engine), a context save on a
  revision with no gemini context remakes its context in the web as before, an answer recomputes a legacy final, a
  re-assessment from retained answers takes a legacy final, and the second review is offered on a legacy context.

Nothing else is replaced: the stages, the doors, the send discipline and the read-time consumers are the product's own.
The stage and context branches that dispatch on a gemini context are not seams, so a gemini context met under the chain
still takes them (only nothing under the chain interprets a revision first, or makes a gemini context of its own).

Which suites run here (FINAL 14.6, slice S15): the reading-outcome tests, each class marked where it is defined - what
the legacy reader reads in a document (dates, routing, statuses, the questions it asks, the legacy engine's records and
digests, the legacy reading a peer is shown) and the legacy records (contexts an earlier gi-context version recorded,
the installed revision's rows, the upgrade and the undo). A reading-outcome test kept in a class of mechanics tests is
marked by itself (``applied`` on the test method). The mechanics tests run the production chain instead, with a recorded
synthetic interpretation per fixture document (tests.test_pipeline_api.RecordedInterpretation), their test-structure
assumptions re-pointed to it: the interpret stage among the stages, Corti's runs beside the interpretation's own run,
an addendum revision's own recorded interpretation, and the state a finished chain leaves the office note in
(tests.test_pipeline_api.OFFICE_NOTE_STATE: its visit facts are member values there, DECISIONS D3). The mechanics
classes still marked here are the ones not yet re-pointed; the S15 report lists them.

Usage::

    from tests.legacy_chain import legacy_chain, applied

    with legacy_chain():
        ...drive the pipeline...

    @applied
    class SomeLegacyReadingTests(TestCase):
        ...  # every test of the class runs with the legacy chain, from before its setUpClass (so its setUpTestData)
             # until after its class cleanups; its setUp, its test and its cleanups run inside it

    class OtherLegacyReadingTests(LegacyChain, TestCase):  # the mixin form of the same
        ...

    class SomeMechanicsTests(RecordedInterpretation, TestCase):
        @applied
        def test_a_legacy_reading(self):
            ...  # only this test's body runs inside legacy_chain(); its class's setUp drives no stage

The chain is marked per class (or per test), where it is defined, so a test added later to any of these modules runs
the production chain unless it is marked too.
"""
import contextlib
import functools
from unittest import mock

from django.conf import settings
from django.db import transaction

from studio import jobs, models

Job = models.Job


def legacy_stage_analyze(job):
    """The analyze stage as it was before the Gemini migration (studio/jobs.py at c2e53f8e, stage_analyze): the document
    read in ONE bounded child (_analyze_child), its context recorded and made current, its routing recorded, and the
    predict queued."""
    revision, encounter = job.revision, job.encounter
    revision.refresh_from_db()
    read = jobs._bounded(jobs._analyze_child, revision.text, dict(encounter.user_values or {}),
                         settings.MAX_SERVICE_MENTIONS, seconds=settings.JOB_DEADLINE_SECONDS['analyze'])
    if isinstance(read, int):  # it names procedures more often than the service reads: not read, nothing recorded
        raise jobs.StageFailure(jobs.MENTIONS_MESSAGE.format(count=read, limit=settings.MAX_SERVICE_MENTIONS))
    document_facts, service_date, data = read
    context = jobs._record_context(encounter, revision, document_facts)
    if jobs.context_service_date(context) != service_date:  # the child read the same facts; never route another date
        raise jobs.StageFailure('The document was routed for another service date than its context; nothing was used.')
    routing = jobs._record_routing(revision, data, service_date)
    with transaction.atomic():
        locked = models.Encounter.objects.select_for_update().get(pk=encounter.pk)
        if locked.current_revision_id == revision.pk:
            locked.current_context = context
            locked.save(update_fields=['current_context', 'updated_at'])
    jobs._queue_predict(encounter, revision, context, key=f'predict:{context.pk}', requested_by=job.requested_by)
    return {'context': str(context.pk), 'routing': str(routing.pk)}


def legacy_after_extract(job, revision):
    """extract's successor before the migration: the legacy analyze, keyed 'analyze:<revision>'."""
    return jobs.enqueue(Job.ANALYZE, encounter=job.encounter, revision=revision, key=f'analyze:{revision.pk}',
                        requested_by=job.requested_by)


def legacy_earlier_reading(job):
    """A stage's handling of an earlier version's context before the migration: remade (jobs._remade_context)."""
    return jobs._remade_context(job)


def legacy_new_path_owed(revision, context=None):
    """Before the migration nothing was ever interpreted first."""
    return False


def legacy_reading_allowed():
    """Before the migration every context was read by the legacy chain (jobs._legacy_reading_allowed's seam, S10)."""
    return True


@contextlib.contextmanager
def legacy_chain():
    """While the block runs, studio.jobs runs the legacy chain (module docstring). Yields nothing."""
    with mock.patch.object(jobs, '_after_extract', legacy_after_extract), \
            mock.patch.object(jobs, '_earlier_reading', legacy_earlier_reading), \
            mock.patch.object(jobs, '_new_path_owed', legacy_new_path_owed), \
            mock.patch.object(jobs, '_legacy_reading_allowed', legacy_reading_allowed), \
            mock.patch.dict(jobs.STAGES, {Job.ANALYZE: legacy_stage_analyze}):
        yield


def _enter_for_class(klass):
    """Enter legacy_chain() for ``klass``'s whole run: left by a class cleanup, which unittest runs after the class's
    tearDownClass - and also when its setUpClass raised."""
    chain = legacy_chain()
    chain.__enter__()
    klass.addClassCleanup(chain.__exit__, None, None, None)


def _enter_for_test(test):
    """Enter legacy_chain() for one test: left by its cleanups, after its tearDown."""
    chain = legacy_chain()
    chain.__enter__()
    test.addCleanup(chain.__exit__, None, None, None)


def applied(cls):
    """A TestCase class decorator: every test of ``cls`` runs inside legacy_chain(). It is entered before the class's
    setUpClass (so Django's setUpTestData reads and writes under it too) and left after its class cleanups, and entered
    again before each test's own setUp - whether or not those call super() - and left after that test's cleanups.

    On a test METHOD instead, only that test's body runs inside legacy_chain() - its class's setUp, setUpClass and
    cleanups take the class's chain - for a reading-outcome test kept in a class of mechanics tests that runs the
    production chain (FINAL 14.6). It is for a test whose class's setUp drives no stage."""
    if not isinstance(cls, type):
        test = cls

        @functools.wraps(test)
        def run(self, *args, **kwargs):
            with legacy_chain():
                return test(self, *args, **kwargs)
        run.legacy_chain = True  # marked, for the triage's own counts
        return run
    own_class_setup = cls.__dict__.get('setUpClass')

    def setUpClass(klass):
        _enter_for_class(klass)
        if own_class_setup is not None:
            own_class_setup.__func__(klass)
        else:
            super(cls, klass).setUpClass()

    cls.setUpClass = classmethod(setUpClass)
    original = cls.setUp

    @functools.wraps(original)
    def setUp(self, *args, **kwargs):
        _enter_for_test(self)
        return original(self, *args, **kwargs)

    cls.setUp = setUp
    return cls


class LegacyChain:
    """The mixin form of ``applied``, first among the bases: ``class X(LegacyChain, TestCase)``. The chain is entered
    before the class's setUpClass and before each test's setUp, as ``applied`` enters it; a subclass that defines its
    own setUpClass or setUp calls super(), as Django's TestCase already requires."""

    @classmethod
    def setUpClass(cls):
        _enter_for_class(cls)
        super().setUpClass()

    def setUp(self):
        _enter_for_test(self)
        super().setUp()
