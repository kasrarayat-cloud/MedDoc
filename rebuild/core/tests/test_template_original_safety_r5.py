"""P1 round 5 (2026-11-01): the round-4 refutation's findings, pinned.

GR1-EXPORT-OPEN: a failure to OPEN the stored original that says nothing about the file (EMFILE, ENFILE, ENOMEM,
EACCES, EIO) is a check that could not run on the export and the original download ("try again"), never the
permanent "missing or changed" answer. An original that is not there, or that became a symbolic link before the
O_NOFOLLOW open (ELOOP), still is.

FG-GR1-DOCS-LAYER, FG-CODING-UNCHECKED and FG-UNREADABLE-EIO-ONLY: the round-4 proof drove those arms on one
spelling only, so a narrowed guard survived all 48 round-4 tests. CommandEveryStartFailure,
CodingWhenTheCheckCouldNotRun and UnreadableOriginal were written by the refutation lens (refute-p1-r4,
false-green) and are adopted with their assertions unchanged; open_fails_at_check is that pass's removal-gr1 helper.
"""
from contextlib import contextmanager
import errno
from io import StringIO
import json
import os
import subprocess
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.jobs import enqueue, run_one
from core.models import AuditEvent
from core.security import private_path
from core.template_source import PdfTemplateCheckUnavailable, assert_pdf_template_usable, provider_refusal
from core.tests import test_template_original_safety as safety   # module only: its TestCases are not re-collected
from core.tests.test_template_original_safety import (CODING_RETAINED, NOT_SENT, UNCHECKED_JOB, SyntheticPractice,
                                                      check_cannot_start, check_times_out, check_workspace_fails)
from core.tests.test_workflow import TEST_SETTINGS
from documents.test_pdf_active_content import form, p1_trigger

TRY_AGAIN = b"try again in a few minutes"
MISSING_OR_CHANGED = b"missing or changed, so it cannot be checked"


@contextmanager
def open_fails_at_check(code):
    """Only the check's own open of the stored original fails with `code`, as the kernel reports it."""
    import documents.service as service
    real_run, real_open = service._run, os.open
    state = {"in_check": False, "hits": 0}

    def opener(path, flags, *args, **kwargs):
        if state["in_check"] and flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK:
            state["hits"] += 1
            raise OSError(code, os.strerror(code))
        return real_open(path, flags, *args, **kwargs)

    def run(path, operation, *args, **kwargs):
        state["in_check"] = operation == "check"
        try:
            return real_run(path, operation, *args, **kwargs)
        finally:
            state["in_check"] = False

    with patch.object(service, "_run", side_effect=run), patch.object(service.os, "open", side_effect=opener):
        yield state


@override_settings(**TEST_SETTINGS)
class OriginalThatCannotBeOpened(SyntheticPractice, TestCase):
    username = "r5-open-failure"

    def latest(self, action, target):
        return AuditEvent.objects.filter(action=action, target=str(target)).order_by("-pk").first()

    def test_an_open_failure_that_says_nothing_about_the_file_is_try_again(self):
        data = form()
        template, version = self.stored_template(data)
        encounter = self.finalized(version, data)
        for code in (errno.EMFILE, errno.ENFILE, errno.ENOMEM, errno.EACCES, errno.EIO):
            with self.subTest(errno=errno.errorcode[code]):
                with open_fails_at_check(code) as state:
                    exported = self.client.get("/encounters/%s/export/" % encounter.pk)
                self.assertEqual(state["hits"], 1)                                # the injected open did fail
                self.assertEqual(exported.status_code, 503)
                self.assertIn(TRY_AGAIN, exported.content)
                self.assertNotIn(MISSING_OR_CHANGED, exported.content)
                self.assertNotIn(b"%PDF", exported.content)
                self.assertEqual(self.latest("encounter.export_refused", encounter.pk).details,
                                 {"code": "sandbox_unavailable"})
                with open_fails_at_check(code) as state:
                    original = self.client.get("/templates/%s/original/" % template.pk)
                self.assertEqual(state["hits"], 1)
                self.assertEqual(original.status_code, 503)
                self.assertNotIn(b"%PDF", original.content)
                self.assertEqual(self.latest("template.download_refused", template.pk).details,
                                 {"code": "sandbox_unavailable"})
        served = self.client.get("/encounters/%s/export/" % encounter.pk)        # nothing was left behind
        self.assertEqual(served.status_code, 200)
        self.assertEqual(b"".join(served.streaming_content), data)

    def test_an_original_that_is_not_there_or_turned_into_a_link_is_still_missing_or_changed(self):
        data = form()
        template, version = self.stored_template(data)
        encounter = self.finalized(version, data)
        # ENOENT and ENOTDIR: not there. ELOOP: the path became a symbolic link between private_path's resolution
        # and the O_NOFOLLOW open, so it is not the stored file.
        for code in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
            with self.subTest(errno=errno.errorcode[code]):
                with open_fails_at_check(code) as state:
                    exported = self.client.get("/encounters/%s/export/" % encounter.pk)
                self.assertEqual(state["hits"], 1)
                self.assertEqual(exported.status_code, 409)
                self.assertIn(MISSING_OR_CHANGED, exported.content)
                self.assertEqual(self.latest("encounter.export_refused", encounter.pk).details,
                                 {"code": "source_unavailable"})
        private_path(template.original_path).unlink()                     # and a real missing original
        missing = self.client.get("/encounters/%s/export/" % encounter.pk)
        self.assertEqual(missing.status_code, 409)
        self.assertIn(MISSING_OR_CHANGED, missing.content)


@override_settings(**TEST_SETTINGS)
class CommandEveryStartFailure(TestCase):
    """Claim 4 / the doc's "GR-1 ... through check_pdf_originals, for every start failure": the command calls
    documents.check_original directly, so only the documents-layer conversion keeps a start failure from
    aborting the report. The round-4 module drives the command with EAGAIN only."""

    setUp = safety.CheckStoredOriginalsCommand.setUp                   # the round-4 module's own setup, verbatim
    stored = safety.CheckStoredOriginalsCommand.stored

    def test_fg_each_start_failure_is_reported_not_raised(self):
        clean = self.stored(form())
        starts = {"spawn ENOMEM": check_cannot_start(OSError(errno.ENOMEM, "Cannot allocate memory")),
                  "pipes EMFILE": check_cannot_start(OSError(errno.EMFILE, "Too many open files")),
                  "child setup": check_cannot_start(subprocess.SubprocessError("Exception occurred in preexec_fn.")),
                  "workspace ENOSPC": check_workspace_fails(errno.ENOSPC),
                  "workspace EDQUOT": check_workspace_fails(errno.EDQUOT)}
        for index, (name, failure) in enumerate(starts.items()):
            with self.subTest(name=name):
                output = self.root / ("report-%d.json" % index)
                with failure:
                    call_command("check_pdf_originals", output=str(output), stdout=StringIO())
                report = json.loads(output.read_text())
                self.assertEqual(report["templates"], [{"template_id": str(clean.pk), "code": "sandbox_unavailable"}])

    def test_an_original_that_cannot_be_read_now_is_could_not_run_and_a_missing_one_is_missing(self):
        if os.geteuid() == 0:
            self.skipTest("root reads a mode-000 file")
        unreadable = self.stored(form())
        path = private_path(unreadable.original_path)
        path.chmod(0)
        self.addCleanup(lambda: path.exists() and path.chmod(0o600))      # the test unlinks it on purpose
        output = self.root / "report-unreadable.json"
        call_command("check_pdf_originals", output=str(output), stdout=StringIO())
        self.assertEqual(json.loads(output.read_text())["templates"],
                         [{"template_id": str(unreadable.pk), "code": "sandbox_unavailable"}])
        path.chmod(0o600)
        path.unlink()
        output = self.root / "report-missing.json"
        call_command("check_pdf_originals", output=str(output), stdout=StringIO())
        self.assertEqual(json.loads(output.read_text())["templates"],
                         [{"template_id": str(unreadable.pk), "code": "source_unavailable"}])


@override_settings(**TEST_SETTINGS)
class CodingWhenTheCheckCouldNotRun(SyntheticPractice, TestCase):
    """Claim 2 for coding: a check that could not run fails the run WITHOUT any provider call.
    The round-4 module drives coding with a REFUSED form only."""

    username = "fg-coding"
    coding_setup = safety.RefusedTemplateNotUsable.coding_setup        # the round-4 module's own setup, verbatim
    save_reviewed = safety.RefusedTemplateNotUsable.save_reviewed

    def test_fg_coding_with_a_check_timeout_sends_nothing(self):
        from core import coding_service
        from core.models import CodingRun
        encounter, provider = self.coding_setup(form())
        self.save_reviewed(encounter)
        run = CodingRun.objects.get(encounter=encounter)
        with check_times_out():
            self.assertTrue(coding_service.run_one())
        run.refresh_from_db()
        self.assertEqual(provider.call_count, 0, "a check that could not run let the coding provider call go out")
        self.assertEqual((run.state, run.error), ("failed", UNCHECKED_JOB + CODING_RETAINED))

    def test_fg_coding_with_a_check_that_cannot_start_sends_nothing(self):
        from core import coding_service
        from core.models import CodingRun
        encounter, provider = self.coding_setup(form())
        self.save_reviewed(encounter)
        run = CodingRun.objects.get(encounter=encounter)
        with check_cannot_start():
            self.assertTrue(coding_service.run_one())
        run.refresh_from_db()
        self.assertEqual(provider.call_count, 0, "a check that could not start let the coding provider call go out")
        self.assertEqual((run.state, run.error), ("failed", UNCHECKED_JOB + CODING_RETAINED))


@override_settings(**TEST_SETTINGS)
class UnreadableOriginal(SyntheticPractice, TestCase):
    """GR-1: "an original that exists but cannot be read (any read error but its absence) is a check that could
    not run". The round-4 module drives EIO through a patched private_path only; here a real permission error."""

    username = "fg-unreadable"

    def test_fg_a_permission_denied_original_is_could_not_run_and_the_worker_sends_nothing(self):
        if os.geteuid() == 0:
            self.skipTest("root reads a mode-000 file")
        template, version = self.stored_template(p1_trigger("type"))      # a form the gate REFUSES
        path = private_path(template.original_path)
        path.chmod(0)
        self.addCleanup(path.chmod, 0o600)
        with self.assertRaises(PdfTemplateCheckUnavailable) as caught:
            assert_pdf_template_usable(template)
        self.assertEqual(caught.exception.code, "source_unavailable")
        self.assertEqual(provider_refusal(template), UNCHECKED_JOB)
        job = enqueue(self.encounter(version), self.user, kind="generation")
        with patch("core.generation.generate") as provider:
            self.assertTrue(run_one())
        self.assertEqual(provider.call_count, 0, "a refused form whose original cannot be read reached the provider")
        self.assert_failed_unsent(job, "Not processed: " + UNCHECKED_JOB + NOT_SENT)
