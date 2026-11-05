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
from studio.validation import engine
from studio.validation.engine import assess
from tests import test_harness2_pipeline as hp
from tests.support.operator import OperatorReads
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
# Where the passages could not be loaded (a stored passage changed after import, the case below), the retrieval never
# ran. Moved by refutation round 4, R4-TRUTH truth-5, to what the code now serves: the tampered passage's note was
# UNCHECKED, "CPT Studio's retrieval ... failed", and now says which step failed, with the same reason why no code was
# checked (UNCHECKED stays the retrieval's own sentence, RetrievalFailureEntryTests below).
LOAD_UNCHECKED = ("Reference validation failed: CPT Studio could not load the stored CMS reference passages "
                  "(ValueError, logged), so the retrieval for this assessment's codes did not run and no CMS reference "
                  "fact or passage is listed here. {why} Retrieval only informs the reviewer and decides no status, so "
                  "the assessment stands as made.")
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
        note = LOAD_UNCHECKED.format(why=why)  # moved by refutation round 4, truth-5 (LOAD_UNCHECKED above)
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
        # moved by refutation round 4, R4-TRUTH truth-5, to what the code now serves: the passages could not be loaded,
        # so the note says that, never jobs.RETRIEVAL_FAILED's retrieval that ran (which had said CPT Studio "could not
        # record which CMS reference facts and passages it retrieved"); the checks' sentence stands
        self.assertEqual(note, jobs.RETRIEVAL_LOAD_FAILED.format(error='ValueError'))
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


class RetrievalFailureEntryTests(OperatorReads, TestCase):
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


# --- truth-2: a first reading's code with no located quote, located in peer review: one account --------------------

UNLOCATED = 'a hot snare removed it completely without any trouble at all'  # in no document: never located
LISTED_FIRST = ('Astra listed this code in its first reading, but none of its quotes was found in the document, so '
                'that reading did not propose it. It proposed it after peer review.')


class FirstReadingUnlocatedTests(R2WordingCase):
    """Astra's frozen first reading lists 45385 with a quote the document does not hold, and its peer review lists it
    again with the snare passage. The engine counts no first-reading entry whose quotes were not found (refutation
    round 1, EV-2 = IND-3), so it records Astra's phase as peer_review, and the peer row, the TXT and the CSV call 45385
    proposed after peer review, never independent. The position said both: "Astra proposed this code in its first
    reading; ... It proposed it again after peer review." (refutation round 3, truth-2). It now says what the record
    holds: the first reading listed it and proposed nothing; Astra proposed it after peer review."""

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', UNLOCATED), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=[('45385', SNARE)]), number=2)]
        self.encounter_id = self.create(TWO_EXTENTS)
        drain()

    def test_the_position_and_the_phase_give_one_account(self):
        detail = self.detail(self.encounter_id)
        [snare] = self.proposals(detail, '45385', bucket='selected')
        self.assertEqual((snare['phases'].get('astra'), 'astra' in snare['proposed_by']), ('peer_review', True))
        self.assertEqual(snare['participant_positions']['astra'],
                         {'position': 'not_proposed', 'quote': '', 'detail': LISTED_FIRST})
        record = self.records(self.encounter(self.encounter_id).current_assessment)['astra']
        self.assertIn({'code': '45385', 'quote': ''}, record['codes'])  # the frozen first reading listed it, unlocated
        peer = next(row['peer'] for row in detail['harness']['participants'] if row['name'] == 'astra')
        self.assertEqual(peer['codes_added'], ['45385'])  # proposed after peer review, never independent
        card = json.dumps(snare['id'])
        lines = browser(f'visible(cardOf(page(), {card})).split("\\n")', detail)
        # the card's positions (participantPositions: "<label> <position words>: <detail>")
        said = [line for line in lines if re.match(r'Astra (proposed it|did not propose it|advised not to code it|gave '
                                                    r'no reading)\b', line)]
        self.assertEqual(said, [f'Astra did not propose it: {LISTED_FIRST}'])
        self.assertEqual(browser(f'statusLine(cardOf(page(), {card}), "Proposed by")', detail),
                         'Corti, Astra (after peer review), Fable (independent reading)')
        trace = _owner(self, 'owner_r3truth2').get(f'/ops/api/encounters/{self.encounter_id}/trace').json()
        (row,) = [item for item in trace['reconciliation'] if item['code'] == '45385' and 'astra' in item['positions']
                  and item['proposed_by'] == snare['proposed_by']]
        self.assertEqual(row['positions']['astra']['detail'], LISTED_FIRST)
        # controls: a located first reading keeps its own wording, Fable's 45385 and Astra's 45380
        # moved by refutation round 6 (R6-MEANING, negation-4, ownership-7): the 'proposed' detail is the engine's own
        # wording, "quoting the document verbatim", never "with evidence located in the document"
        self.assertEqual(snare['participant_positions']['fable']['detail'],
                         'Fable proposed this code, quoting the document verbatim.')
        [biopsy] = self.proposals(detail, '45380', bucket='selected')
        self.assertEqual(biopsy['participant_positions']['astra'],
                         {'position': 'proposed', 'quote': BIOPSY,
                          'detail': 'Astra proposed this code, quoting the document verbatim.'})

    def test_a_first_reading_s_unlocated_code_with_no_later_proposal_reads_as_before(self):
        # a participant whose first reading lists a code it never located, and that proposes it in no later phase: it
        # is not counted as a proposer, and nothing says it proposed it later. Moved by refutation round 4, R4-TRUTH
        # truth-2, to what the code now serves: this pinned harness@1's "Astra proposed this code; none of its quotes
        # was found in the document." ('proposed'), so one frozen first reading had two positions - this one, and
        # 'not_proposed' where peer review then proposed the code. That reading proposed nothing either way, so its
        # position is 'not_proposed' with the same sentence, and nothing more (tests/test_harness2_r4_truth.py)
        records = [{'name': 'astra', 'state': 'read', 'codes': [{'code': '45385', 'quote': ''}], 'not_coded': []}]
        for support in ({'proposed_by': ['corti'], 'phases': {}}, {}, None):
            plain = review.participant_positions(type('P', (), {'code': '45385', 'support': support})(), records)
            self.assertEqual(plain['astra'], {'position': 'not_proposed', 'quote': '',
                                              'detail': 'Astra listed this code in its first reading, but none of its '
                                                        'quotes was found in the document, so that reading did not '
                                                        'propose it.'})


# --- truth-3: Corti's row counts the codes it selected that cannot be listed ---------------------------------------

LONG = '45385-SYNTHETIC-LONG-VALUE'
UNLISTED_ONE = ('It returned 1 code that cannot be listed: empty, or longer than 10 characters (a CPT code has five). '
                'It is not shown and never truncated.')


class CortiUnlistedMixin:
    """Corti's answer selects a 'code' longer than any CPT code, which the engine drops with its provider.unlisted
    warning and never shows. Corti's row read "Answered; its codes were checked." and "It proposed no code." beside it,
    and the TXT "answered; its codes were checked" (refutation round 3, truth-3). The row now counts the codes Corti
    selected that cannot be listed (unlisted_codes, as the model rows do since round 2's truth-11) and says none was
    checked; the code itself is never served."""

    def corti_row(self, detail):
        return next(row for row in detail['harness']['participants'] if row['name'] == 'corti')

    def corti_lines(self, encounter_id):
        return _block(_section(_txt(self.encounter(encounter_id)), 'REVIEW PARTICIPANTS'), '  - Corti · ')

    def run_with(self, *selections):
        self.corti.selections = list(selections)
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        return encounter_id, self.detail(encounter_id)

    def test_corti_selected_only_a_code_it_cannot_list(self):
        encounter_id, detail = self.run_with((LONG, SNARE))
        row = self.corti_row(detail)
        self.assertEqual((row['state'], row['detail'], row['codes'], row['unlisted_codes']),
                         ('done', f'Answered; none of its codes can be listed, so none was checked. {UNLISTED_ONE}',
                          [], 1))
        text = browser('rowOf(page(), "data-participant", "corti")', detail)
        self.assertIn('It proposed no code that can be listed.', text)
        for said in ('It proposed no code.', 'its codes were checked'):
            self.assertNotIn(said, text)
        lines = self.corti_lines(encounter_id)
        self.assertEqual(lines[0], '  - Corti · Corti · answered; none of its codes can be listed, so none was checked')
        self.assertIn(f'    Not listed: {UNLISTED_ONE}', lines)
        checks = {check['id']: check for check in detail['assessment']['encounter_checks']}
        self.assertEqual(checks['provider.unlisted']['status'], 'warn')  # the engine's own warning, as before
        self.assertNotIn(LONG, json.dumps(detail))
        self.assertNotIn(LONG, '\n'.join(lines))

    def test_codes_it_can_and_cannot_list(self):
        encounter_id, detail = self.run_with((LONG, SNARE), ('45380', BIOPSY))
        row = self.corti_row(detail)
        self.assertEqual((row['detail'], row['codes'], row['unlisted_codes']),
                         (f'Answered; its codes that can be listed were checked. {UNLISTED_ONE}', ['45380'], 1))
        text = browser('rowOf(page(), "data-participant", "corti")', detail)
        self.assertIn('Codes it proposed that can be listed: 45380.', text)
        self.assertEqual(self.corti_lines(encounter_id)[0],
                         '  - Corti · Corti · answered; its codes that can be listed were checked')

    def test_every_code_listed_reads_as_before(self):
        encounter_id, detail = self.run_with(('45385', SNARE), ('45380', BIOPSY))
        row = self.corti_row(detail)
        self.assertEqual((row['detail'], row['codes'], row['unlisted_codes']),
                         ('Answered; its codes were checked.', ['45380', '45385'], 0))
        lines = self.corti_lines(encounter_id)
        self.assertEqual(lines[0], '  - Corti · Corti · answered; its codes were checked')
        self.assertFalse([line for line in lines if line.startswith('    Not listed: ')])


class CortiUnlistedTests(CortiUnlistedMixin, R2WordingCase):
    pass


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyUnlistedTests(CortiUnlistedMixin, R2WordingCase):
    def test_the_chain_is_i1_s(self):
        encounter_id, _ = self.run_with((LONG, SNARE))
        self.assertEqual(self.kinds(encounter_id), ['extract', 'analyze', 'predict', 'assess'])


# --- truth-4: a reuse's REVIEW PARTICIPANTS never credits it with the retained run's exchanges ---------------------

class ReuseExchangesTests(hp.Harness2Case):
    """The second encounter of the same synthetic note reuses Astra's retained answer: its run sent nothing and holds
    no exchange, while its Assessment.participants entry counts the exchanges and tool calls of the loop that answered
    for it (jobs.loop_run: the retained run's). The TXT printed "Exchanges: 2 · tool calls: 1" as this run's, beside
    PARTICIPANT REFERENCES' "this run made none" and the trace's 0 exchanges (refutation round 3, truth-4)."""

    def astra_lines(self, encounter_id):
        return _block(_section(_txt(self.encounter(encounter_id)), 'REVIEW PARTICIPANTS'), '  - Astra · ')

    def test_a_reuse_says_whose_exchanges_and_tool_calls_these_are(self):
        first = self.create()
        drain()
        second = self.create()
        drain()
        (retained,) = self.runs_of(first, 'astra', 'independent')
        (reuse,) = self.runs_of(second, 'astra', 'independent')
        self.assertEqual((reuse.reused_from_id, reuse.sent, reuse.exchanges.count()), (retained.pk, False, 0))
        self.assertEqual((retained.exchanges.count(), models.ToolCall.objects.filter(exchange__run=retained).count()),
                         (2, 1))
        lines = self.astra_lines(second)
        self.assertIn(f'    Exchanges: 0 · tool calls: 0 (this run reuses the retained answer of run {retained.pk}, '
                      'which made 2 exchanges and 1 tool call)', lines)
        self.assertNotIn('    Exchanges: 2 · tool calls: 1', lines)
        # control: the retained run's own entry is as before
        self.assertIn('    Exchanges: 2 · tool calls: 1', self.astra_lines(first))
        # and the owner's trace agrees: the reuse holds no exchange of its own
        trace = _owner(self, 'owner_r3truth4').get(f'/ops/api/encounters/{second}/trace').json()
        (traced,) = [item for participant in trace['participants'] for item in participant['runs']
                     if item['id'] == str(reuse.pk)]
        self.assertEqual((traced['exchanges'], traced['reused_from']), ([], str(retained.pk)))


# --- truth-5: a code Corti listed without selecting it is never called only a candidate -----------------------------

LISTED = 'Corti listed this code as a candidate or an alternative, not selected; see Alternatives.'


class CortiListedTests(R2WordingCase):
    """Corti selects 45385 and nests 45380 under it as an alternative; Astra proposes 45380 from the biopsy passage. The
    card, the rationale and corti_relation called 45380 "listed only as a candidate", while the Alternatives row it
    points to says "alternative to 45385" (refutation round 3, truth-5). The engine reads only that Corti listed the
    code without selecting it, so the engine's rationale, the API's relation and the page say that, in one sentence true
    of a candidate and of an alternative, and the Alternatives row says which. Moved by refutation round 6 (R6-MEANING,
    the session's D14) to Astra's alternative; restored as it stood before D14 by HARNESS.md P-ADMIT (owner directive
    2026-11-05): Astra's first-reading 45380 on the biopsy passage is admitted, a selected card beside Corti's listing."""

    def listed(self, edit):
        self.corti.selections = [('45385', SNARE)]
        with self.corti_answer(edit):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        detail = self.detail(encounter_id)
        [own] = self.proposals(detail, '45380', bucket='selected')
        [alternative] = self.proposals(detail, '45380', bucket='alternative')
        self.assertEqual((self.origin(own), own['proposed_by'], self.origin(alternative)),
                         ('participant', ['astra'], 'primary'))
        line = browser(f'statusLine(cardOf(page(), {json.dumps(own["id"])}), "Proposed by")', detail)
        self.assertEqual(own['corti_relation'], 'candidate')
        self.assertEqual(line, f'Astra (independent reading); {LISTED}')
        self.assertTrue(own['rationale'].startswith(f'Proposed by Astra (independent participant); {LISTED}'),
                        own['rationale'])
        for said in (line, own['rationale']):
            self.assertNotIn('only as a candidate', said)
        return alternative

    def test_an_alternative_nested_under_a_selected_code(self):
        def nested(answer, text):
            start = text.index(BIOPSY)
            for item in answer['codes']:
                if item['code'] == '45385':
                    item['alternatives'] = [{'system': 'cpt', 'code': '45380', 'display': hp.CORTI_DISPLAY,
                                             'evidences': [{'contextIndex': 0, 'start': start,
                                                            'end': start + len(BIOPSY), 'text': BIOPSY}]}]
        alternative = self.listed(nested)
        self.assertTrue(alternative['exclusion_reason'].startswith('Provider alternative to 45385; not selected.'),
                        alternative['exclusion_reason'])

    def test_a_candidate(self):
        def candidate(answer, text):
            start = text.index(BIOPSY)
            answer['candidates'] = [{'system': 'cpt', 'code': '45380', 'display': hp.CORTI_DISPLAY,
                                     'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(BIOPSY),
                                                    'text': BIOPSY}], 'alternatives': []}]
        alternative = self.listed(candidate)
        self.assertTrue(alternative['exclusion_reason'].startswith('Provider candidate; not selected.'),
                        alternative['exclusion_reason'])


# --- truth-6: a code card states the NCCI procedure-to-procedure limit once ----------------------------------------

# A statement of the limit: "NCCI procedure-to-procedure edits are not connected", "NCCI edits are not connected", "NCCI
# procedure-to-procedure edits not verified", or the edits named in a "Not verified:" list. "If an NCCI
# procedure-to-procedure edit pairs the two codes" is a consideration, not a statement of the limit.
LIMIT = re.compile(r'NCCI (?:procedure-to-procedure )?edits (?:are )?not (?:connected|verified)')
# The engine's services.base_included detail (I1-pinned engine output): it restates the limit where that check warns,
# on its warning line and in its question's details - recorded as a residual, counted apart.
BASE_INCLUDED = 'internal profile rule; NCCI procedure-to-procedure edits are not connected'


def _statements(line):
    if line.startswith('Not verified: '):
        return int('NCCI procedure-to-procedure edits' in line)
    return len(LIMIT.findall(line))


class PtpOncePerCardTests(R2WordingCase):
    """Every real code card of the colon chain stated the limit in its status line, again in "Not verified: ...; NCCI
    procedure-to-procedure edits." and, where separate lesions are documented, again in its modifier considerations
    ("NCCI edits are not connected; no modifier is assigned."), while round 2's test counted the status line alone
    (refutation round 3, truth-6). The status line, the "Not verified" note and the modifier line now state it once."""

    def test_the_status_line_the_not_verified_note_and_the_modifier_line_state_it_once(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        cards = browser('cards(page()).map(card => visible(card).split("\\n"))', detail)
        # moved by refutation round 6 (R6-MEANING, the session's D14): two cards, Corti's 45385 and 45380 - Fable's
        # peer-review 45378 is its alternative now, with no card
        self.assertEqual(len(cards), 2)
        modifier_lines = 0
        for lines in cards:
            status = [line for line in lines if line.startswith('CMS reference checks: ')]
            noted = [line for line in lines if line.startswith('Not verified: ')]
            modifiers = [line for line in lines if line.startswith('Modifier considerations, never assigned')]
            self.assertEqual(len(status), 1, lines)
            surfaces = status + noted + modifiers
            self.assertEqual(sum(_statements(line) for line in surfaces), 1, surfaces)
            self.assertEqual(_statements(status[0]), 1, status)  # the status line is where it is stated (I4)
            for line in modifiers:
                modifier_lines += 1
                # the consideration itself stands, and no modifier is assigned
                self.assertIn('If an NCCI procedure-to-procedure edit pairs the two codes', line)
                self.assertTrue(line.endswith('No modifier is assigned.'), line)
            # the whole card: once, and once more for each line of the services.base_included residual
            residual = sum(BASE_INCLUDED in line for line in lines)
            self.assertEqual(sum(_statements(line) for line in lines), 1 + residual, lines)
        self.assertEqual(modifier_lines, 2)  # 45385 and 45380: separate lesions are documented


# --- falsegreen-9: no partial estimate where a failed exchange reported no usage ----------------------------------

class FailedExchangeCostTests(hp.Harness2Case):
    """truth-12's rule (HARNESS.md 12.9; review._unpriced): an exchange that may have been billed - any not recorded not
    sent - and reported no usage leaves the run with no estimate. Round 2 pinned it for an unknown exchange and for one
    not sent; a mutant that read only 'unknown' priced exchange 1 alone as the run's ("0.0310") for an exchange that
    FAILED (HTTP 529) with no usage, and every gate stayed green (refutation round 3, falsegreen-9)."""

    def setUp(self):
        super().setUp()
        self.owner = _owner(self, 'owner_r3fg9')

    def test_a_failed_exchange_that_reported_no_usage_leaves_the_run_unestimated(self):
        self.adapters['astra'].first = [hp.asks('astra', hp.facts_call('call_astra_1', ['99213'])), hp.failed()]
        encounter_id = self.create()
        drain()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent), ('failed', True))
        self.assertEqual([(item.turn, item.state, item.http_status, bool(item.usage))
                          for item in run.exchanges.order_by('turn')], [(1, 'succeeded', 200, True), (2, 'failed', 529,
                                                                                                        False)])
        self.assertTrue(run.usage)  # exchange 1's, which pricing alone would price as the run's
        self.assertIsNone(review.estimated_cost(run))
        self.assertEqual(review.unpriced_exchanges(run), [(2, 'failed')])
        trace = self.owner.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        traced = [item['estimated_cost_usd'] for participant in trace['participants'] for item in participant['runs']
                  if item['id'] == str(run.pk)]
        row = next(item for item in self.owner.get(f'/ops/api/encounters/{encounter_id}').json()['harness']['participants']
                   if item['name'] == 'astra')
        self.assertEqual((traced, row['run_id'], row['estimated_cost_usd']), ([None], str(run.pk), None))
        lines = _block(_section(_txt(self.encounter(encounter_id)), 'REVIEW PARTICIPANTS'), '  - Astra · ')
        self.assertIn('    Estimated cost: not estimated: exchange 2 (failed) reported no usage and may have been '
                      'billed, so the cost of this run cannot be estimated from published rates', lines)


# --- falsegreen-10: corti_relation 'second_review' and 'selected_apart' as the serializer serves them ---------------

class SecondReviewRelationTests(OperatorReads, TestCase):
    """corti_relation 'second_review' through the real engine: Corti selects 45385; its bounded second review lists
    45380 only as a candidate (alt2:0); Astra proposes 45380 from the biopsy passage. The engine's result is persisted
    as the assess stage persists it and served by the real API; the page words the relation as the engine's rationale
    does. A mutant returning 'none' here made the page say "Corti did not propose this code." beside the rationale's
    second review, and every gate stayed green (refutation round 3, falsegreen-10)."""

    def setUp(self):
        from tests.test_harness_engine import DAY, REFERENCE, code, read, span

        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer_r3fg10'))
        self.encounter = f.encounter(self.ws, self.reviewer, title='Synthetic colonoscopy, second review')
        revision = f.pasted_revision(self.encounter, self.reviewer, TWO_EXTENTS)
        text = revision.text
        second = NormalizedResponse('corti', 'test@1', (ProviderCode('candidate', 'cpt', '45380', '',
                                                                     (span(text, BIOPSY),)),))
        scope = {'start': text.index('Procedure: Colonoscopy'), 'end': len(text), 'items': ['the flat lesion biopsy']}
        selected = (ProviderCode('selected', 'cpt', '45385', hp.CORTI_DISPLAY, (span(text, SNARE),)),)
        result = assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, DAY),
                        normalized=NormalizedResponse('corti', 'test@1', selected), reference=REFERENCE,
                        service_date=DAY, provider_status='succeeded',
                        participants=[read('astra', [code(text, '45380', BIOPSY)])], second=second, second_scope=scope)
        record = {'name': 'astra', 'state': 'read', 'run': None, 'adapter_version': 'astra-test@1',
                  'requested_model': 'gpt-6-astra', 'returned_model': 'gpt-6-astra', 'unverified_quotes': 0,
                  'reason': '', 'codes': [{'code': '45380', 'quote': BIOPSY}], 'not_coded': []}
        self.assessment = review.persist_assessment(
            encounter=self.encounter, revision=revision, context=pf.context(self.encounter, revision),
            routing_run=pf.routing(revision), provider_run=pf.provider_run(self.encounter, revision), result=result,
            participants=[record, jobs.not_configured_record('fable')], retrieval=[])

    @override_settings(ASTRA_MODE='replay', FABLE_MODE='disabled')
    def test_the_serializer_serves_second_review_and_the_page_words_it_as_the_rationale_does(self):
        listed = self.assessment.proposals.get(key='alt2:0')
        self.assertEqual((listed.code, listed.support.get('origin')), ('45380', 'second_review'))
        client = Client()
        client.force_login(self.reviewer)
        detail = client.get(f'/ops/api/encounters/{self.encounter.pk}').json()
        # HARNESS.md P-ADMIT (2026-11-05) restores this pin as it stood before D14 (which listed Astra's 45380): its
        # first-reading 45380 is admitted, a selected card whose rationale and status line word the second review
        [own] = [p for p in detail['assessment']['proposals'] if p['code'] == '45380' and p['bucket'] == 'selected']
        self.assertEqual((own['support']['origin'], own['proposed_by'], own['corti_relation']),
                         ('participant', ['astra'], 'second_review'))
        words = "Corti's second review also listed this code without adding it as a proposal; see Alternatives."
        self.assertTrue(own['rationale'].startswith(f'Proposed by Astra (independent participant); {words}'),
                        own['rationale'])
        line = browser(f'statusLine(cardOf(page(), {json.dumps(own["id"])}), "Proposed by")', detail)
        self.assertEqual(line, f'Astra (independent reading); {words}')
        relations = {p['key']: p['corti_relation'] for p in detail['assessment']['proposals']}
        self.assertEqual((relations['sel:0'], relations['alt2:0']), ('proposer', 'proposer'))


# A CPT Category II code: a five-character code the reading keeps, which the engine excludes as out of scope.
CATEGORY_II = '3017F'


class SelectedApartRelationTests(R2WordingCase):
    """corti_relation 'selected_apart' through the real pipeline: Corti selects 3017F (a CPT Category II code, out of
    this release's scope) with an exact passage, and Astra proposes it too. Corti's selection is excluded for its scope
    - not for want of an exact passage - and Astra's own entry of the code is an alternative saying why, so the
    serializer serves Astra's 'selected_apart': Corti selected it, and its selection is listed apart. The engine adds a
    participant's own proposal only for a code no decidable Corti selection carries, so this - a participant's
    alternative beside Corti's excluded selection - is where the relation is served (refutation round 3,
    falsegreen-10)."""

    def test_the_serializer_serves_selected_apart_for_a_participant_s_code_beside_corti_s_excluded_selection(self):
        self.corti.selections = [('45385', SNARE), ('45380', BIOPSY), (CATEGORY_II, SNARE)]
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', SNARE), ('45380', BIOPSY), (CATEGORY_II, SNARE)],
            services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        [corti] = self.proposals(detail, CATEGORY_II, bucket='excluded')
        [astra] = self.proposals(detail, CATEGORY_II, bucket='alternative')
        self.assertEqual((corti['proposed_by'], corti['corti_relation'], corti['reinstatable']),
                         (['corti'], 'proposer', False))
        self.assertTrue(corti['exclusion_reason'].startswith('CPT Category II'), corti['exclusion_reason'])
        self.assertEqual((self.origin(astra), astra['proposed_by'], astra['corti_relation']),
                         ('participant', ['astra'], 'selected_apart'))
        line = browser(f'visible(app.codeStatusLines(data.assessment.proposals.find(p => p.id === '
                       f'{json.dumps(astra["id"])}))).split("\\n")[0]', detail)
        self.assertEqual(line, 'Proposed by: Astra (independent reading); Corti also selected this code; its selection '
                               'is listed apart.')
