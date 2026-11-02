"""Refutation round 3, R3-TRUTH (HARNESS.md 5, 7, 11.1, 11.4, 12.6, 12.7; I4, I9): what the page, the API, the owner's
trace and the reports state must be true of the record - a retrieval that failed where no CMS reference file applied
(truth-1), a first reading's code that only its peer review located (truth-2), Corti's codes that cannot be listed
(truth-3), a reused run's exchanges (truth-4), a code Corti listed without selecting it (truth-5) and the NCCI
procedure-to-procedure limit on a code card (truth-6) - and two rules round 2 left unpinned: no partial estimate for a
failed exchange that reported no usage (falsegreen-9), and Corti's relations 'second_review' and 'selected_apart' as
the serializer serves them from the real engine's own result (falsegreen-10).

Each class reproduces one finding of the round (refute-harness-r3/findings.json, verified in
verify-harness-r3/results.json) through the real pipeline - the real jobs, engine, readers, tool executor and tool loop,
the vendors' HTTP replaced by scripted bytes in their own envelopes (tests.test_harness2_pipeline) - or, where no
pipeline input reaches the case, the real engine's own result persisted as the assess stage persists it; then the real
API, the real report renderers and the real app.js run by node. Synthetic data only; nothing is sent.
"""
import json
import re

from django.test import Client, TestCase, override_settings

from studio import jobs, models, reports, review, serializers
from studio.gi import context as gi_context
from studio.gi import detect
from studio.types import NormalizedResponse, ProviderCode
from studio.validation.engine import assess
from tests import test_harness2_pipeline as hp
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_harness2_pipeline import BIOPSY, LAND, SNARE, TWO_EXTENTS
from tests.test_harness2_r2_truth import NO_DATE, OUTSIDE, tamper_one_passage
from tests.test_harness2_r2_wording import R2WordingCase, browser
from tests.test_pipeline_api import drain


def _txt(encounter):
    return reports.render_txt(reports.snapshot(encounter, 'draft')).decode('utf-8')


def _section(text, title):
    """The lines of the TXT section ``title`` (up to its blank line)."""
    return text.split(f'\n{title}\n', 1)[1].split('\n\n', 1)[0].splitlines()


def _block(lines, head):
    """The lines of one entry of a TXT section: the line starting with ``head`` and those under it."""
    start = next(index for index, line in enumerate(lines) if line.startswith(head))
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith('  - ')), len(lines))
    return lines[start:end]


def _owner(case, name):
    client = Client()
    client.force_login(f.member(case.ws, f.user(name), role=models.Membership.OWNER))
    return client


# --- truth-1: a retrieval that failed where no CMS reference file applied says no code was checked, and why ---------

# What the note says where no installed CMS reference file applied to the service date: the retrieval failed, so nothing
# is listed, and no code was checked against a CMS reference file - with serializers' own reason - never that each
# code's checks read the CMS facts (refutation round 3, truth-1: every check read "not verified" beside that claim).
UNCHECKED = ("Reference validation failed: CPT Studio's retrieval for this assessment's codes failed (ValueError, "
             "logged), so no CMS reference fact or passage is listed here. {why} Retrieval only informs the reviewer "
             "and decides no status, so the assessment stands as made.")
NO_DATE_WHY = ('No code was checked against the CMS reference files: no service date is established for this '
               'encounter, so no dated CMS reference file applies.')
OUTSIDE_WHY = ('No code was checked against the CMS reference files: no installed CMS reference file applies to the '
               'service date, 2025-03-02.')
# The words that claim a code's CMS checks read the CMS facts, or that something was retrieved and not recorded: never
# said where no CMS reference file applied, and never by a sentence the page or the API says in every case.
CLAIMS = ('read the CMS facts', 'read the facts', 'could not record which')


class RetrievalFailureWithoutSourceMixin:
    """A retrieval whose passages cannot be loaded (a stored passage changed after import) on a document for whose
    service date no installed CMS reference file applies - none documented, or one before every installed release -
    so every code's CMS checks read "not verified". The note, the API's reference validation, the page's row and cards
    and the TXT say the retrieval failed and that no code was checked, with why; with a release that applies they say,
    as before, that each code's checks read the CMS facts and stand (refutation round 3, truth-1)."""

    def run_tampered(self, text):
        tamper_one_passage()
        encounter_id = self.create(text)
        with self.assertLogs('studio.jobs', level='ERROR') as caught:
            drain()
        self.assertTrue(any('does not match its sha256' in line for line in caught.output), caught.output)
        return encounter_id

    def assertSaysNoCodeWasChecked(self, encounter_id, day, why):
        note = UNCHECKED.format(why=why)
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(final.retrieval, [{'code': '', 'service_date': day, 'facts': [], 'passages': [],
                                            'lookups': [], 'notes': [note], 'failed': True}])
        # what the note says is the record: no installed CMS reference file applied, and every code's CMS checks read
        # "not verified"
        self.assertFalse([source['key'] for source in final.reference_sources if source.get('applies')])
        decidable = list(final.proposals.exclude(bucket='alternative'))
        self.assertTrue(decidable)
        for proposal in decidable:
            statuses = {check['id']: check['status'] for check in proposal.checks}
            self.assertEqual((statuses['pfs.presence'], statuses['mue.units']), ('not_verified', 'not_verified'),
                             proposal.code)
        detail = self.detail(encounter_id)
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['detail'], block['codes_checked'], block['passages']),
                         ('failed', note, 0, 0))
        retrieval = _section(_txt(self.encounter(encounter_id)), 'REFERENCE RETRIEVAL')
        self.assertIn(f'  - {note}', retrieval)
        row = browser('rowOf(page(), "data-participant", "reference_validation")', detail)
        self.assertIn(note, row)
        cards = browser('cards(page()).map(card => visible(card))', detail)
        self.assertEqual(len(cards), len([p for p in decidable if p.bucket == 'selected']))
        card_note = browser('app.RETRIEVAL_FAILED', {})
        for card in cards:
            self.assertIn(card_note, card)
        for said in (block['detail'], row, '\n'.join(retrieval), *cards):
            for claim in CLAIMS:
                self.assertNotIn(claim, said)


class RetrievalFailureWithoutSourceTests(RetrievalFailureWithoutSourceMixin, R2WordingCase):
    def test_no_documented_date_after_peer_review(self):
        encounter_id = self.run_tampered(NO_DATE)
        self.assertEqual(self.detail(encounter_id)['harness']['phase'], 2)
        self.assertSaysNoCodeWasChecked(encounter_id, None, NO_DATE_WHY)

    def test_a_release_that_applies_keeps_the_note_that_the_checks_read_the_cms_facts(self):
        # control: the documented date's release applies, every check read the CMS facts, and the note says so
        encounter_id = self.run_tampered(TWO_EXTENTS)
        final = self.encounter(encounter_id).current_assessment
        (note,) = final.retrieval[0]['notes']
        self.assertEqual(note, jobs.RETRIEVAL_FAILED.format(error='ValueError'))
        self.assertIn("Each code's checks read the CMS facts before that and stand as shown", note)
        for proposal in final.proposals.exclude(bucket='alternative'):
            statuses = {check['id']: check['status'] for check in proposal.checks}
            self.assertEqual((statuses['pfs.presence'], statuses['mue.units']), ('pass', 'pass'), proposal.code)


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyRetrievalFailureWithoutSourceTests(RetrievalFailureWithoutSourceMixin, R2WordingCase):
    def test_no_documented_date(self):
        encounter_id = self.run_tampered(NO_DATE)
        self.assertEqual(self.kinds(encounter_id), ['extract', 'analyze', 'predict', 'assess'])  # I1's chain
        self.assertSaysNoCodeWasChecked(encounter_id, None, NO_DATE_WHY)

    def test_a_documented_date_no_installed_release_covers(self):
        encounter_id = self.run_tampered(OUTSIDE)
        self.assertSaysNoCodeWasChecked(encounter_id, '2025-03-02', OUTSIDE_WHY)


class RetrievalFailureEntryTests(TestCase):
    """jobs.retrieval_failure states what the engine's record says of the codes: that their checks read the CMS facts
    only when told an installed CMS reference file applied (the assess stage reads it from the engine's
    reference_sources); otherwise that none was checked, and why. The fallbacks the API and the page say for every
    assessment - a failed entry with no note, the row's plain sentence, the card's - claim neither."""

    def test_the_note_follows_whether_a_cms_reference_file_applied(self):
        from datetime import date

        day = date(2026, 10, 21)
        applied = jobs.retrieval_failure(day, 'RuntimeError', applied=True)
        self.assertEqual(applied['notes'], [jobs.RETRIEVAL_FAILED.format(error='RuntimeError')])
        dated = jobs.retrieval_failure(day, 'RuntimeError', applied=False)
        self.assertEqual(dated['notes'], [UNCHECKED.replace('ValueError', 'RuntimeError').format(
            why='No code was checked against the CMS reference files: no installed CMS reference file applies to the '
                'service date, 2026-10-21.')])
        self.assertEqual(jobs.retrieval_failure(None, 'ValueError', applied=False)['notes'],
                         [UNCHECKED.format(why=NO_DATE_WHY)])
        # fail closed: a caller that does not say a file applied never has the note claim a check read a CMS fact
        self.assertEqual(jobs.retrieval_failure(day, 'RuntimeError'), dated)
        for entry in (applied, dated):
            self.assertEqual({key: value for key, value in entry.items() if key != 'notes'},
                             {'code': '', 'service_date': '2026-10-21', 'facts': [], 'passages': [], 'lookups': [],
                              'failed': True})

    def test_the_sentences_said_of_every_failed_retrieval_claim_no_check(self):
        page = browser('[app.REFERENCE_STATES.failed[2], app.RETRIEVAL_FAILED]', {})
        for said in (serializers.REFERENCE_FAILED, *page):
            self.assertTrue(said.startswith('Reference validation failed'), said)
            for claim in CLAIMS + ('No code was checked', 'no proposal was checked'):
                self.assertNotIn(claim, said)
        self.assertEqual(serializers.failure_note({'code': '', 'failed': True, 'notes': []}),
                         serializers.REFERENCE_FAILED)
