"""The legacy chain, for TESTS ONLY (design/FINAL.md 14.6 and 16.14; slices S09 and S15).

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
- ``_new_path_owed``: never - a Resume or a reconciliation works as before rather than interpreting the revision first.

Later slices that add a seam for the legacy chain (S10's assess dispatch, its context save) extend this module (S15).

Usage::

    from tests.legacy_chain import legacy_chain, applied

    with legacy_chain():
        ...drive the pipeline...

    @applied
    class SomeLegacyReadingTests(TestCase):
        ...  # every test of the class runs with the legacy chain (entered before its own setUp)
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


@contextlib.contextmanager
def legacy_chain():
    """While the block runs, studio.jobs runs the legacy chain (module docstring). Yields nothing."""
    with mock.patch.object(jobs, '_after_extract', legacy_after_extract), \
            mock.patch.object(jobs, '_earlier_reading', legacy_earlier_reading), \
            mock.patch.object(jobs, '_new_path_owed', legacy_new_path_owed), \
            mock.patch.dict(jobs.STAGES, {Job.ANALYZE: legacy_stage_analyze}):
        yield


def applied(cls):
    """A TestCase class decorator: every test of ``cls`` runs inside legacy_chain(), entered before the class's own
    setUp runs and left after its cleanups - whether or not that setUp calls super()."""
    original = cls.setUp

    @functools.wraps(original)
    def setUp(self, *args, **kwargs):
        chain = legacy_chain()
        chain.__enter__()
        self.addCleanup(chain.__exit__, None, None, None)
        return original(self, *args, **kwargs)

    cls.setUp = setUp
    return cls


class LegacyChain:
    """A mixin form of ``applied`` for a class that calls super().setUp(): ``class X(LegacyChain, TestCase)``."""

    def setUp(self):
        chain = legacy_chain()
        chain.__enter__()
        self.addCleanup(chain.__exit__, None, None, None)
        super().setUp()
