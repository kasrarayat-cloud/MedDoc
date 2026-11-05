"""Refutation round 2, R2-TRUTH (HARNESS.md 5-7, 11.1-11.3, 12.6, 12.7; I4): what the page, the API, the owner's trace
and the reports state about the participants' positions and references, reference validation, a retrieval that
failed, the reviewer's confirmations and a run's estimated cost must be true of the record.

Synthetic data only; nothing is sent. The encounters are carried through the real pipeline
(tests.test_harness2_pipeline: ScriptedCorti, the real replay adapters and tool loop with CPT Studio's CMS tool
executor, the readers, the engine, the API and the report renderers), as the round's verifiers reproduced each finding.
"""
import csv
import io
import json
from types import SimpleNamespace

from django.test import Client, override_settings

from studio import jobs, models, reports, review, serializers
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_harness2_pipeline import (ASTRA_READING, TWO_EXTENTS, ColonCase, Harness2Case, answered, asks,
                                          facts_call, unknown)
from tests.test_pipeline_api import drain


def _proposal(detail, code):
    return next(item for item in detail['assessment']['proposals'] if item['code'] == code)


# --- truth-2: a code first proposed in peer review is never said to be one its proposer did not propose -------------

PEER_ONLY = 'Fable did not propose this code in its first reading. It proposed it after peer review.'


class PeerProposedPositionTests(ColonCase):
    """The default colon chain: Fable's peer review adds 45378 (support proposed_by ['fable'], phases {'fable':
    'peer_review'}). participant_positions reads the frozen first readings, so its position there is 'not_proposed' -
    and its detail says that is its first reading's, and that it proposed the code after peer review, in the API and in
    the owner's reconciliation table alike (refutation round 2, truth-2: both said "Fable did not propose this
    code.")."""

    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, f.user('owner_r2truth'), role=models.Membership.OWNER)

    def test_its_proposer_is_never_said_not_to_have_proposed_a_code_it_proposed_after_peer_review(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        added = self.encounter(encounter_id).current_assessment.proposals.get(code='45378')
        self.assertEqual((added.support.get('proposed_by'), added.support.get('phases')),
                         (['fable'], {'fable': 'peer_review'}))
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        positions = _proposal(detail, '45378')['participant_positions']
        self.assertEqual(positions['fable'], {'position': 'not_proposed', 'detail': PEER_ONLY, 'quote': ''})
        # a participant that proposed it in neither phase says so as before
        self.assertEqual(positions['astra'], {'position': 'not_proposed', 'detail': 'Astra did not propose this code.',
                                              'quote': ''})
        owner = Client()
        owner.force_login(self.owner)
        trace = owner.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        row = next(item for item in trace['reconciliation'] if item['code'] == '45378')
        self.assertEqual((row['proposed_by'], row['positions']['fable']['detail']), (['fable'], PEER_ONLY))
        # a code a first reading proposed keeps its first reading's own wording
        # moved by refutation round 6 (R6-MEANING, negation-4, ownership-7): the 'proposed' detail is the engine's own
        # wording, "quoting the document verbatim", never "with evidence located in the document"
        self.assertEqual(_proposal(detail, '45385')['participant_positions']['fable']['detail'],
                         'Fable proposed this code, quoting the document verbatim.')

    def test_each_first_reading_position_says_it_is_the_first_reading_s_beside_a_later_proposal(self):
        later = SimpleNamespace(code='45378', support={'proposed_by': ['astra', 'fable'],
                                                       'phases': {'astra': 'peer_review', 'fable': 'peer_review'}})
        records = [{'name': 'astra', 'state': 'read', 'codes': [{'code': '45378', 'quote': ''}], 'not_coded': []},
                   {'name': 'fable', 'state': 'read', 'codes': [],
                    'not_coded': [{'code': '45378', 'reason': 'not_performed_at_this_encounter', 'quote': 'Q.'}]}]
        positions = review.participant_positions(later, records)
        # moved by refutation round 3, R3-TRUTH truth-2, to what the code now serves: a first reading's entry whose
        # quotes were not found proposed nothing (the engine's phase, EV-2 = IND-3), so the participant that then
        # proposed the code after peer review did not propose it in its first reading, and never "again"
        self.assertEqual(positions['astra'], {
            'position': 'not_proposed', 'quote': '',
            'detail': 'Astra listed this code in its first reading, but none of its quotes was found in the document, '
                      'so that reading did not propose it. It proposed it after peer review.'})
        self.assertEqual(positions['fable'], {
            'position': 'advised_not_to_code', 'quote': 'Q.',
            'detail': 'Fable advised not to code it in its first reading: not performed at this encounter. It '
                      'proposed it after peer review.'})
        # an independent proposer, and a record with no phases (harness@1). Moved by refutation round 4, R4-TRUTH
        # truth-2, to what the code now serves: Astra's first-reading entry has no located quote, so that reading
        # proposed nothing whatever the phases say - 'not_proposed', the sentence above without the later one (it
        # read "Astra proposed this code; none of its quotes was found in the document.") - and Fable's advice reads
        # as before
        for support in ({'proposed_by': ['astra'], 'phases': {'astra': 'independent'}}, {}, None):
            plain = review.participant_positions(SimpleNamespace(code='45378', support=support), records)
            self.assertEqual(plain['astra'], {
                'position': 'not_proposed', 'quote': '',
                'detail': 'Astra listed this code in its first reading, but none of its quotes was found in the '
                          'document, so that reading did not propose it.'})
            self.assertEqual(plain['fable']['detail'], 'Fable advised not to code it: not performed at this encounter.')


# --- truth-3: reference validation never says codes were checked against the CMS files when no file applied ----------

NOT_CONNECTED = list(review.NOT_CONNECTED)
NO_DATE = TWO_EXTENTS.replace('Date of service: 2026-10-14\n', '')
OUTSIDE = TWO_EXTENTS.replace('Date of service: 2026-10-14', 'Date of service: 2025-03-02')  # before every release held
NO_SOURCE_NO_DATE = ('No code was checked against the CMS reference files: no service date is established for this '
                     'encounter, so no dated CMS reference file applies.')
NO_SOURCE_FOR_DATE = ('No code was checked against the CMS reference files: no installed CMS reference file applies '
                      'to the service date, {date}.')


class ReferenceValidationTruthMixin:
    """harness.reference_validation is 'done', with its codes counted as checked against the CMS reference files, only
    when an installed CMS reference file applied to the assessment's service date (Assessment.reference_sources, the
    engine's record of the lookup the retrieval traced); when none did - no service date established, or none covering
    it - it is 'not_verified', counts no code and says why (refutation round 2, truth-3: "Done - 2 codes checked
    against the CMS reference files" beside cards whose every CMS check was "not verified")."""

    def block(self, encounter_id):
        return self.client.get(f'/ops/api/encounters/{encounter_id}').json()['harness']['reference_validation']

    def assertNoCodeChecked(self, encounter_id, detail):
        self.assertEqual(self.block(encounter_id), {'state': 'not_verified', 'detail': detail, 'codes_checked': 0,
                                                    'passages': 0, 'sources': [], 'not_connected': NOT_CONNECTED})
        self.assertEqual((serializers.NO_SOURCE_NO_DATE, serializers.NO_SOURCE_FOR_DATE),
                         (NO_SOURCE_NO_DATE, NO_SOURCE_FOR_DATE))
        for proposal in self.encounter(encounter_id).current_assessment.proposals.exclude(bucket='alternative'):
            statuses = {check['id']: check['status'] for check in proposal.checks}
            self.assertEqual((statuses['pfs.presence'], statuses['mue.units']), ('not_verified', 'not_verified'),
                             proposal.code)


class ReferenceValidationTruthTests(ReferenceValidationTruthMixin, ColonCase):
    def test_a_member_date_conflict_leaves_every_code_unchecked_and_the_row_says_so(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        block = self.block(encounter_id)  # the control: the documented date's release applied
        # moved by refutation round 7 (d14-1, d14-2): Corti's 45385 and 45380 are checked; Fable's peer-review 45378 is
        # a participant's alternative (D14), never traced, so never counted as a code checked (it was 3)
        self.assertEqual((block['state'], block['detail'], block['codes_checked']), ('done', '', 2))
        self.assertTrue(block['passages'] and block['sources'], block)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-20'}).status_code, 201)
        drain()
        # moved by refutation round 7 (d14-2): the member's date conflicts with the document's, so Corti's request is
        # held and Corti selects nothing; every code listed is a participant's alternative (D14), never traced, so
        # nothing was checked and the row reads not run (it read 'not_verified' with the no-date reason, from the
        # alternatives' own traces - the class d14-2 found)
        self.assertEqual(self.block(encounter_id), {'state': 'not_run', 'detail': '', 'codes_checked': 0,
                                                    'passages': 0, 'sources': [], 'not_connected': NOT_CONNECTED})
        listed = self.encounter(encounter_id).current_assessment.proposals.all()
        self.assertTrue(listed)
        # HARNESS.md P-ADMIT (2026-11-05): the participants' first-reading codes are admitted (I10), each held on the
        # date the member must settle, so none is ready - and, untraced while no date applies, none is a code checked
        self.assertEqual({(p.bucket, p.status, (p.support or {}).get('origin')) for p in listed},
                         {('selected', 'needs_clarification', 'participant')})


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyReferenceValidationTruthTests(ReferenceValidationTruthMixin, ColonCase):
    def test_no_documented_date(self):
        encounter_id = self.create(NO_DATE)
        drain()
        self.assertEqual(self.kinds(encounter_id), ['extract', 'analyze', 'predict', 'assess'])  # I1's chain
        self.assertNoCodeChecked(encounter_id, NO_SOURCE_NO_DATE)

    def test_a_documented_date_no_installed_release_covers(self):
        encounter_id = self.create(OUTSIDE)
        drain()
        self.assertNoCodeChecked(encounter_id, NO_SOURCE_FOR_DATE.format(date='2025-03-02'))

    def test_the_documented_date_s_release_applies(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        block = self.block(encounter_id)
        self.assertEqual((block['state'], block['detail'], block['codes_checked']), ('done', '', 2))


# --- truth-4: a retrieval that failed says what failed, never that the CMS checks did not run ------------------------

# The plan's shared wording (verify-harness-r2/REPAIR-PLAN.md): each code's checks read the CMS facts before the
# retrieval (jobs.stage_assess looks them up first), and stand. Moved by refutation round 4, R4-TRUTH truth-5, to what
# the code now serves: the tampered passage below fails the load of the stored passages, so the retrieval never ran,
# and the note says so (jobs.RETRIEVAL_LOAD_FAILED) - it said "CPT Studio could not record which CMS reference facts
# and passages it retrieved for this assessment's codes", when nothing was retrieved.
RETRIEVAL_FAILED = ("Reference validation failed: CPT Studio could not load the stored CMS reference passages "
                    "({error}, logged), so the retrieval for this assessment's codes did not run and no CMS reference "
                    "fact or passage is listed here. Each code's checks read the CMS facts before that and stand as "
                    "shown; retrieval only informs the reviewer and decides no status, so the assessment stands as "
                    "made.")
# The fallback for a failed entry with no note. Moved by refutation round 3, R3-TRUTH truth-1, to what the serializer
# now serves: it is said of any assessment, and where no CMS reference file applied no code's checks read a CMS fact,
# so it claims neither that they did nor that none did (tests/test_harness2_r3_truth.py pins both notes the assess
# stage records).
REFERENCE_FAILED = ("Reference validation failed: CPT Studio's retrieval for this assessment's codes failed, so no CMS "
                    "reference fact or passage is listed here; each code's CMS reference checks stand as shown for "
                    "that code.")


def tamper_one_passage():
    """The integrity failure the passages module anticipates: a stored passage changed after import, which
    load_passages refuses ("does not match its sha256; it was changed after import")."""
    row = models.ReferencePassage.objects.order_by('pk').first()
    models.ReferencePassage.objects.filter(pk=row.pk).update(text=row.text + ' (changed after import)')


class RetrievalFailureWordingMixin:
    """A retrieval whose passages cannot be loaded is recorded as failed (HARNESS.md 5, refutation round 1 parity-1)
    after every proposal was checked against the CMS facts: its note, the API's detail, the page's fallbacks and the
    TXT say what failed and never that no proposal was checked (refutation round 2, truth-4)."""

    def assertSaysWhatFailed(self, encounter_id):
        note = RETRIEVAL_FAILED.format(error='ValueError')
        self.assertEqual(jobs.RETRIEVAL_LOAD_FAILED.format(error='ValueError'), note)
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(final.retrieval, [{'code': '', 'service_date': '2026-10-14', 'facts': [], 'passages': [],
                                            'lookups': [], 'notes': [note], 'failed': True}])
        decidable = list(final.proposals.exclude(bucket='alternative'))
        self.assertTrue(decidable)
        for proposal in decidable:  # what the note says: each code's checks read the CMS facts, and stand
            statuses = {check['id']: check['status'] for check in proposal.checks}
            self.assertEqual((statuses['pfs.presence'], statuses['mue.units']), ('pass', 'pass'), proposal.code)
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['detail'], block['codes_checked']), ('failed', note, 0))
        text = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        self.assertIn(f'  - {note}', text.split('\nREFERENCE RETRIEVAL\n', 1)[1].split('\n\n', 1)[0].splitlines())
        self.assertIn('[PASS] pfs.presence', text)
        for served in (json.dumps(detail), text):
            self.assertNotIn('no proposal was checked against them', served)
        # the fallback where a failed entry carries no note says the same facts
        self.assertEqual(serializers.REFERENCE_FAILED, REFERENCE_FAILED)
        self.assertEqual(serializers.failure_note({'code': '', 'failed': True, 'notes': []}), REFERENCE_FAILED)

    def run_tampered(self):
        tamper_one_passage()
        encounter_id = self.create(TWO_EXTENTS)
        with self.assertLogs('studio.jobs', level='ERROR') as caught:
            drain()
        self.assertTrue(any('does not match its sha256' in line for line in caught.output), caught.output)
        return encounter_id


class RetrievalFailureWordingTests(RetrievalFailureWordingMixin, ColonCase):
    def test_with_both_participants_after_peer_review(self):
        encounter_id = self.run_tampered()
        self.assertEqual(self.client.get(f'/ops/api/encounters/{encounter_id}').json()['harness']['phase'], 2)
        self.assertSaysWhatFailed(encounter_id)


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyRetrievalFailureWordingTests(RetrievalFailureWordingMixin, ColonCase):
    def test_corti_only(self):
        encounter_id = self.run_tampered()
        self.assertEqual(self.kinds(encounter_id), ['extract', 'analyze', 'predict', 'assess'])  # I1's chain
        self.assertSaysWhatFailed(encounter_id)


# --- truth-5: one reading of what the current assessment made of a confirmation, for the page and the reports --------

# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class ConfirmationEffectTests(ColonCase):
    """review.confirmation_effect states what the current assessment made of each reviewer-confirmed finding - read,
    or not read with why - and the API's confirmations (current_effect) and the reports' CONFIRMED FINDINGS ("Effect:")
    both state it. The round's s12: the extent of 45385 confirmed and read, then a member's conflicting date makes an
    assessment that lists it in confirmations.ignored (refutation round 2, truth-5: the page still said "The
    assessment reads it as documented by this passage")."""

    def detail(self, encounter_id):
        return self.client.get(f'/ops/api/encounters/{encounter_id}').json()

    def verified_extent(self, encounter_id):
        detail = self.detail(encounter_id)
        proposals = {item['id']: item for item in detail['assessment']['proposals']}
        for question in detail['clarifications']:
            proposal = proposals.get(question['proposal_id'] or '')
            if question['fact'] == 'extent' and proposal and proposal['key'] == 'sel:0' and question['state'] == 'open':
                return question, next(item for item in question['candidates'] if item['verified'])
        raise AssertionError('no verified extent candidate for sel:0')

    def report_effects(self, encounter_id):
        text = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        lines = text.split('\nCONFIRMED FINDINGS\n', 1)[1].split('\n\n', 1)[0].splitlines()
        return [line[len('    Effect: '):] for line in lines if line.startswith('    Effect: ')]

    def test_what_the_current_assessment_made_of_a_confirmation_is_stated_once_for_the_page_and_the_reports(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        question, candidate = self.verified_extent(encounter_id)
        response = self.post(f'/api/encounters/{encounter_id}/clarifications/{question["id"]}/confirm',
                             {'candidate_id': candidate['id'], 'attestation': candidate['attestation']})
        self.assertEqual((response.status_code, response.json()['effect']), (201, 'reassessment'))
        made_before = {'state': 'not_read', 'detail': 'not read by this assessment, which was made before it'}
        self.assertEqual(response.json()['current_effect'], made_before)  # the assessment it was made on
        drain()
        read = {'state': 'read', 'detail': 'read by this assessment'}
        (served,) = self.detail(encounter_id)['confirmations']
        self.assertEqual((served['current_effect'], self.report_effects(encounter_id)), (read, [read['detail']]))
        self.assertEqual(self.encounter(encounter_id).current_assessment.proposals.get(key='sel:0').status, 'ready')
        # a member's date that conflicts with the document's: the next assessment does not read it, and says why
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-20'}).status_code, 201)
        drain()
        final = self.encounter(encounter_id).current_assessment
        (ignored,) = final.completeness['confirmations']['ignored']
        self.assertEqual(ignored['id'], served['id'])
        expected = {'state': 'not_read', 'detail': f'not read by this assessment: {ignored["why"]}'}
        detail = self.detail(encounter_id)
        (served,) = detail['confirmations']
        self.assertEqual((served['current_effect'], self.report_effects(encounter_id)),
                         (expected, [expected['detail']]))
        checks = {check['id']: check for check in detail['assessment']['encounter_checks']}
        self.assertEqual(checks['confirmations.ignored']['status'], 'warn')
        self.assertNotIn('confirmations.applied', checks)
        # with the member's date in conflict Corti's new request is not sent. Moved by refutation round 6 (D14) to
        # alternatives; HARNESS.md P-ADMIT (2026-11-05): the participants' first-reading codes are admitted as beside an
        # answer (I10; their 45385 was sel:0, held, before D14), each held on the date the member must settle - so
        # nothing reads the confirmation and nothing is ready
        self.assertEqual(sorted((p.code, p.bucket, p.status) for p in final.proposals.all()),
                         [('45380', 'selected', 'needs_clarification'), ('45385', 'selected', 'needs_clarification')])
        self.assertEqual({(p.support or {}).get('origin') for p in final.proposals.all()}, {'participant'})
        self.assertFalse(models.Decision.objects.exists())  # I4: a confirmation is no decision


# --- truth-12: an estimate never covers only some of the exchanges that may have been billed --------------------------

NEVER_SENT = RawExchange(outcome='not_sent', sent=False, requested_model='gpt-6-astra',
                         error='The deadline passed before the request was sent; nothing was sent.')
UNPRICED = ("not estimated: exchange 2 (outcome unknown) reported no usage and may have been billed, so the cost of "
            "this run cannot be estimated from published rates")


class CostCoverageTests(Harness2Case):
    """A tool loop is priced exchange by exchange (pricing.estimate_loop), which counts an exchange that reported no
    usage and prices the rest. An exchange that may have reached the vendor - any not recorded not sent - and reported
    no usage leaves the run's cost unknown, so it has no estimate (the trace, the participant row, the reports), and
    the TXT and the trace say why; one recorded not sent cost nothing (refutation round 2, truth-12: the run of an
    unknown second exchange showed "Estimated cost $0.0310", exchange 1's alone)."""

    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, f.user('owner_r2truth12'), role=models.Membership.OWNER)

    def served_costs(self, encounter_id, run):
        owner = Client()
        owner.force_login(self.owner)
        trace = owner.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        traced = [item for participant in trace['participants'] for item in participant['runs']
                  if item['id'] == str(run.pk)]
        rows = owner.get(f'/ops/api/encounters/{encounter_id}').json()['harness']['participants']
        row = next(item for item in rows if item['name'] == 'astra')
        self.assertEqual(row['run_id'], str(run.pk))  # the row reports the run it names
        return [item['estimated_cost_usd'] for item in traced], row['estimated_cost_usd']

    def cost_line(self, encounter_id):
        text = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        lines = text.split('\nREVIEW PARTICIPANTS\n', 1)[1].split('\n\n', 1)[0].splitlines()
        start = lines.index(next(line for line in lines if line.startswith('  - Astra · ')))
        return next(line for line in lines[start + 1:] if line.startswith('    Estimated cost: '))

    def test_a_sent_exchange_that_reported_no_usage_leaves_the_run_unestimated_and_says_why(self):
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])), unknown()]
        encounter_id = self.create()
        drain()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent), ('unknown', True))
        self.assertEqual([(item.turn, item.state, bool(item.usage)) for item in run.exchanges.order_by('turn')],
                         [(1, 'succeeded', True), (2, 'unknown', False)])
        self.assertTrue(run.usage)  # exchange 1's, which pricing alone would price as the run's
        self.assertIsNone(review.estimated_cost(run))
        self.assertEqual(review.unpriced_exchanges(run), [(2, 'unknown')])
        self.assertEqual(self.served_costs(encounter_id, run), ([None], None))
        self.assertEqual(self.cost_line(encounter_id), f'    Estimated cost: {UNPRICED}')

    def test_an_exchange_recorded_not_sent_cost_nothing_and_the_estimate_stands(self):
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])), NEVER_SENT]
        encounter_id = self.create()
        drain()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual([(item.turn, item.state) for item in run.exchanges.order_by('turn')],
                         [(1, 'succeeded'), (2, 'not_sent')])
        self.assertEqual(review.unpriced_exchanges(run), [])
        self.assertEqual(review.estimated_cost(run), '0.0310')  # 2,500 in x $10/M + 120 out x $50/M, exchange 1's
        self.assertEqual(self.served_costs(encounter_id, run), (['0.0310'], '0.0310'))
        self.assertEqual(self.cost_line(encounter_id),
                         f'    Estimated cost: USD 0.0310 ({review.COST_BASIS})')


# --- sends-r2-3: a tool result the participant was never sent is never shown as one it retrieved ---------------------

class UndeliveredReferenceTests(Harness2Case):
    """A tool call's refs are references its participant retrieved only when the exchange that carried its result to
    the participant was sent (the next exchange, recorded and not 'not_sent'). The loop records the tool calls it
    answered on exchange N even when it then ends without sending exchange N+1 - not sent, a Stop, a follow-up it could
    not build, the deadline - so those results never reached the participant (refutation round 2, sends-r2-3: the API
    and the reports listed all 8 refs as retrieved). The trace still shows every tool call CPT Studio answered."""

    def astra_row(self, encounter_id):
        rows = self.client.get(f'/ops/api/encounters/{encounter_id}').json()['harness']['participants']
        return next(row for row in rows if row['name'] == 'astra')

    def references_lines(self, encounter_id, run):
        text = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        lines = text.split('\nPARTICIPANT REFERENCES\n', 1)[1].split('\n\n', 1)[0].splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith('  - Astra · independent reading · run '))
        self.assertIn(str(run.pk), lines[start])
        return lines[start + 1:start + 3]

    def answered_refs(self, run):
        (call,) = models.ToolCall.objects.filter(exchange__run=run)
        self.assertEqual(call.exchange.turn, 1)
        self.assertTrue(call.refs)  # CPT Studio executed it and recorded what it returned
        return call.refs

    def test_results_the_next_exchange_never_carried_are_not_retrieved(self):
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])), NEVER_SENT]
        encounter_id = self.create()
        drain()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, [(item.turn, item.state) for item in run.exchanges.order_by('turn')]),
                         ('failed', True, [(1, 'succeeded'), (2, 'not_sent')]))
        refs = self.answered_refs(run)
        self.assertEqual(review.participant_references(run)['retrieved'], [])
        row = self.astra_row(encounter_id)
        self.assertEqual((row['run_id'], row['references']['retrieved']), (str(run.pk), []))
        self.assertEqual(self.references_lines(encounter_id, run), ['    Retrieved: none', '    Used: none'])
        # the owner's trace keeps every tool call CPT Studio answered, with the refs it returned
        owner = Client()
        owner.force_login(f.member(self.ws, f.user('owner_sends_r2_3'), role=models.Membership.OWNER))
        trace = owner.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        (traced,) = [item for participant in trace['participants'] for item in participant['runs']
                     if item['id'] == str(run.pk)]
        self.assertEqual(traced['exchanges'][0]['tool_calls'][0]['refs'], refs)

    def test_results_answered_while_a_member_stopped_the_loop_are_not_retrieved(self):
        encounter_id = self.create()
        adapter = self.adapters['astra']
        original = adapter.send_loop
        adapter.first = [asks('astra', facts_call('call_astra_1', ['99213'])), answered('astra', ASTRA_READING)]

        def send_loop(request, *, execute_tool, **kwargs):
            def tool(name, arguments):
                out = execute_tool(name, arguments)
                jobs.stop_encounter(models.Encounter.objects.get(pk=encounter_id), self.reviewer)  # a member's Stop
                return out
            return original(request, execute_tool=tool, **kwargs)
        adapter.send_loop = send_loop
        drain()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual([(item.turn, item.state) for item in run.exchanges.order_by('turn')], [(1, 'succeeded')])
        self.answered_refs(run)
        self.assertEqual(review.participant_references(run)['retrieved'], [])

    def assertCarried(self, second):
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])), second]
        encounter_id = self.create()
        drain()
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual(run.exchanges.get(turn=2).state, 'succeeded' if isinstance(second, bytes) else 'unknown')
        refs = self.answered_refs(run)
        self.assertEqual([item['ref'] for item in review.participant_references(run)['retrieved']], refs)

    def test_results_the_answering_exchange_carried_are_retrieved(self):
        self.assertCarried(answered('astra', ASTRA_READING))

    def test_results_an_exchange_sent_with_an_unknown_outcome_carried_are_retrieved(self):
        # the request carrying them was written to the vendor: they were sent to the participant
        self.assertCarried(unknown())


# --- truth-13: a reuse's references are said to be the retained run's, retrieved by its tool calls --------------------

class ReusedRunReferenceTests(Harness2Case):
    """A run that reuses a retained answer made no tool call: its references are the retained run's (HARNESS.md 12.7, a
    reuse shows the calls of the run it reuses), and the API names that run (references.reused_from, and each of the
    trace's references used), so the page, the trace and the reports say they were retrieved by the retained run's tool
    calls, never "by its own tool calls in this run" (refutation round 2, truth-13)."""

    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, f.user('owner_r2truth13'), role=models.Membership.OWNER)
        self.owner_client = Client()
        self.owner_client.force_login(self.owner)

    def astra(self, encounter_id):
        rows = self.owner_client.get(f'/ops/api/encounters/{encounter_id}').json()['harness']['participants']
        return next(row for row in rows if row['name'] == 'astra')

    def references_lines(self, encounter_id, run):
        text = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        lines = text.split('\nPARTICIPANT REFERENCES\n', 1)[1].split('\n\n', 1)[0].splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith('  - Astra · independent reading · run '))
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('  - ')), len(lines))
        self.assertIn(str(run.pk), lines[start])
        return lines[start], [line for line in lines[start + 1:end] if line.startswith('    Used: ')]

    def csv_checks(self, encounter_id):
        data = reports.render_csv(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8')
        rows = list(csv.DictReader(io.StringIO(data)))
        return {row['checks'] for row in rows if row['item_list'] == 'participant_reference'
                and row['proposed_by'] == 'astra' and row['proposal_origin'] == 'independent'}

    def trace_used(self, encounter_id, run):
        trace = self.owner_client.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        (traced,) = [item for participant in trace['participants'] for item in participant['runs']
                     if item['id'] == str(run.pk)]
        return traced['reading']['references_used']

    def test_a_reuse_names_the_retained_run_whose_tool_calls_it_shows(self):
        first = self.create()
        drain()
        second = self.create()
        drain()
        (retained,) = self.runs_of(first, 'astra', 'independent')
        (reuse,) = self.runs_of(second, 'astra', 'independent')
        self.assertEqual((reuse.reused_from_id, reuse.sent, reuse.exchanges.count()), (retained.pk, False, 0))
        # the TXT: the run says whose tool calls these are, and a used reference was retrieved by that run
        head, used = self.references_lines(first, retained)
        self.assertEqual(head, f'  - Astra · independent reading · run {retained.pk}')
        self.assertIn('    Used: fact:cms-pfs-rvu26d:99213:status — retrieved by this run', used)
        head, used = self.references_lines(second, reuse)
        self.assertEqual(head, f'  - Astra · independent reading · run {reuse.pk} · reuses the retained answer of run '
                               f'{retained.pk}, whose tool calls these are; this run made none')
        self.assertIn('    Used: fact:cms-pfs-rvu26d:99213:status — retrieved by the retained run it reuses', used)
        # moved by refutation round 4 (R4-SHAPES, shapes-3): 'rule-01', never retrieved, is printed only by its length
        self.assertIn('    Used: a value of 7 characters (not shown) — cited, not retrieved by the retained run it '
                      'reuses, so never shown as retrieved', used)
        self.assertEqual(self.csv_checks(first), {f'run={retained.pk}'})
        self.assertEqual(self.csv_checks(second), {f'run={reuse.pk};reused_from={retained.pk}'})
        # the API: the same references, and the run whose tool calls they are
        own, reused = self.astra(first)['references'], self.astra(second)['references']
        self.assertTrue(own['retrieved'] and own['used'])
        self.assertEqual(('reused_from' in own, reused['reused_from']), (False, str(retained.pk)))  # a reuse's only
        self.assertEqual((reused['retrieved'], reused['used']), (own['retrieved'], own['used']))
        # the owner's trace: each reference used names the run whose tool calls it was checked against
        self.assertEqual({'reused_from' in item for item in self.trace_used(first, retained)}, {False})
        self.assertEqual({item['reused_from'] for item in self.trace_used(second, reuse)}, {str(retained.pk)})
