"""Refutation round 4, R4-TRUTH (HARNESS.md 5, 7, 11.1, 12.6, 12.9, 12.11; I4, I9): what the page, the API, the owner's
trace and the reports state must be true of the record - a first reading's code with no quote found in the document,
whether or not its peer review then proposed it (truth-2) - and round 3's own repair left the rule's other half: one
account of one frozen first reading.

Each class reproduces one finding of the round (refute-harness-r4/findings.json, verified in
verify-harness-r4/results.json) through the real pipeline - the real jobs, engine, readers, tool executor and tool loop,
the vendors' HTTP replaced by scripted bytes in their own envelopes (tests.test_harness2_pipeline) - then the real API,
the real report renderers and the real app.js run by node. Synthetic data only; nothing is sent.
"""
import json
import re
from types import SimpleNamespace

from django.test import Client, TestCase, override_settings

from studio import models, review
from tests import test_harness2_pipeline as hp
from tests.legacy_chain import applied
from tests.support.operator import OperatorReads
from tests.support import factories as f
from tests.test_harness2_pipeline import BIOPSY, SNARE, TWO_EXTENTS, TWO_EXTENTS_INTERPRETATIONS
from tests.test_harness2_r2_wording import R2WordingCase, browser
from tests.test_pipeline_api import RecordedInterpretation, drain


def _owner(case, name):
    client = Client()
    client.force_login(f.member(case.ws, f.user(name), role=models.Membership.OWNER))
    return client


# --- truth-2: a first reading's code with no located quote is "not proposed" there, whatever peer review did --------

UNLOCATED = 'a hot snare removed it completely without any trouble at all'  # in no document: never located
# What the first reading's position says of a code it listed with no quote found in the document: the same sentence
# whether or not peer review then proposed the code (refutation round 4, truth-2), and where it did, one more sentence.
LISTED = ('Astra listed this code in its first reading, but none of its quotes was found in the document, so that '
          'reading did not propose it.')
LATER = ' It proposed it after peer review.'
# The card's positions (participantPositions: "<label> <position words>: <detail>").
POSITION_LINE = re.compile(r'Astra (proposed it|did not propose it|advised not to code it|gave no reading)\b')


@applied
class FirstReadingPositionTests(R2WordingCase):
    """Astra's frozen first reading lists 45385 with a quote the document does not hold (and 45380 on the biopsy).
    The engine counts no first-reading entry whose quotes were not found (refutation round 1, EV-2 = IND-3): Astra is
    not among 45385's proposers. Where its peer review proposes nothing, the card said "Astra proposed it: Astra
    proposed this code; none of its quotes was found in the document." beside "Proposed by: Corti, Fable (independent
    reading)"; where its peer review proposed 45385 on the snare passage, the same frozen reading was "not proposed"
    there (refutation round 4, truth-2: one frozen reading, two positions). It is now "not proposed" in both, in one
    sentence, and only the variant whose peer review proposed it says so after it."""

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', UNLOCATED), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]

    def run_variant(self, peer_codes=None):
        """One encounter of TWO_EXTENTS through the pipeline; ``peer_codes``, what Astra's peer review proposes (None:
        the peer loop already scripted)."""
        if peer_codes is not None:
            self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=peer_codes), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        self.assertEqual(detail['harness']['phase'], 2)
        [snare] = self.proposals(detail, '45385', bucket='selected')
        record = self.records(self.encounter(encounter_id).current_assessment)['astra']
        self.assertIn({'code': '45385', 'quote': ''}, record['codes'])  # the frozen first reading listed it, unlocated
        return encounter_id, detail, snare, record

    def card_positions(self, detail, proposal):
        lines = browser(f'visible(cardOf(page(), {json.dumps(proposal["id"])})).split("\\n")', detail)
        return [line for line in lines if POSITION_LINE.match(line)]

    def test_a_first_reading_s_unlocated_code_that_peer_review_did_not_propose_is_not_proposed(self):
        encounter_id, detail, snare, _ = self.run_variant([])
        # the record: Astra proposed 45385 in no phase (the engine names no proposer and no phase for it)
        self.assertEqual((snare['proposed_by'], snare['phases']), (['corti', 'fable'], {'fable': 'independent'}))
        self.assertEqual(snare['participant_positions']['astra'],
                         {'position': 'not_proposed', 'quote': '', 'detail': LISTED})
        self.assertEqual(self.card_positions(detail, snare), [f'Astra did not propose it: {LISTED}'])
        self.assertEqual(browser(f'statusLine(cardOf(page(), {json.dumps(snare["id"])}), "Proposed by")', detail),
                         'Corti, Fable (independent reading)')
        for said in self.card_positions(detail, snare):
            self.assertNotIn('Astra proposed', said)
        # the owner's trace reconciliation says the same
        trace = _owner(self, 'owner_r4truth2').get(f'/ops/api/encounters/{encounter_id}/trace').json()
        (row,) = [item for item in trace['reconciliation'] if item['code'] == '45385'
                  and item['proposed_by'] == snare['proposed_by']]
        self.assertEqual(row['positions']['astra'], {'position': 'not_proposed', 'quote': '', 'detail': LISTED})
        # control: a located first reading keeps its own wording (Astra's 45380, Fable's 45385)
        # moved by refutation round 6 (R6-MEANING, negation-4, ownership-7): the 'proposed' detail is the engine's own
        # wording, "quoting the document verbatim", never "with evidence located in the document"
        [biopsy] = self.proposals(detail, '45380', bucket='selected')
        self.assertEqual(biopsy['participant_positions']['astra'],
                         {'position': 'proposed', 'quote': BIOPSY,
                          'detail': 'Astra proposed this code, quoting the document verbatim.'})
        self.assertEqual(snare['participant_positions']['fable']['detail'],
                         'Fable proposed this code, quoting the document verbatim.')

    def test_one_frozen_first_reading_gets_one_position_whatever_peer_review_did(self):
        # variant A: Astra's peer review proposes 45385 on the snare passage (refutation round 3, truth-2's case);
        # variant B, a second encounter of the same note in the same workspace: its peer review proposes nothing
        self.adapters['astra'].peer_loops = [[hp.answered('astra', hp.peer_answer(codes=[('45385', SNARE)]), number=2)],
                                             [hp.answered('astra', hp.peer_answer(), number=2)]]
        first, detail_a, snare_a, record_a = self.run_variant()
        self.assertEqual((snare_a['proposed_by'], snare_a['phases'].get('astra')),
                         (['corti', 'astra', 'fable'], 'peer_review'))
        second, detail_b, snare_b, record_b = self.run_variant()
        self.assertNotIn('astra', snare_b['phases'])
        self.assertEqual(self.adapters['astra'].peer_loops, [])  # each variant's peer review was its own loop
        # the same frozen first reading: variant B's first reading reuses variant A's retained run, recorded identically
        (retained,) = self.runs_of(first, 'astra', 'independent')
        (reuse,) = self.runs_of(second, 'astra', 'independent')
        self.assertEqual(reuse.reused_from_id, retained.pk)
        self.assertEqual((record_a['reading_sha256'], record_a['codes']),
                         (record_b['reading_sha256'], record_b['codes']))
        position_a, position_b = (snare_a['participant_positions']['astra'], snare_b['participant_positions']['astra'])
        self.assertEqual((position_a['position'], position_a['quote']), (position_b['position'], position_b['quote']))
        self.assertEqual((position_a['detail'], position_b['detail']), (LISTED + LATER, LISTED))
        self.assertEqual(self.card_positions(detail_a, snare_a), [f'Astra did not propose it: {LISTED}{LATER}'])
        self.assertEqual(self.card_positions(detail_b, snare_b), [f'Astra did not propose it: {LISTED}'])

    def test_every_record_reads_a_first_reading_s_unlocated_code_as_not_proposed(self):
        # with no phase recorded for the participant (an independent proposer named by another quote, no phases at all,
        # a harness@1 record), and with one: the first reading's entry with no located quote proposed nothing there
        records = [{'name': 'astra', 'state': 'read', 'codes': [{'code': '45385', 'quote': ''}], 'not_coded': []}]
        for support in ({'proposed_by': ['corti', 'fable'], 'phases': {'fable': 'independent'}},
                        {'proposed_by': ['astra'], 'phases': {'astra': 'independent'}}, {}, None):
            with self.subTest(support=support):
                position = review.participant_positions(SimpleNamespace(code='45385', support=support), records)
                self.assertEqual(position['astra'], {'position': 'not_proposed', 'quote': '', 'detail': LISTED})
        later = review.participant_positions(SimpleNamespace(code='45385', support={
            'proposed_by': ['astra'], 'phases': {'astra': 'peer_review'}}), records)
        self.assertEqual(later['astra'], {'position': 'not_proposed', 'quote': '', 'detail': LISTED + LATER})
        # control: a located quote is a proposal, with or without a later phase
        located = [{'name': 'astra', 'state': 'read', 'codes': [{'code': '45385', 'quote': SNARE}], 'not_coded': []}]
        plain = review.participant_positions(SimpleNamespace(code='45385', support={}), located)
        # moved by refutation round 6 (R6-MEANING, negation-4, ownership-7): the 'proposed' detail is the engine's own
        # wording, "quoting the document verbatim", never "with evidence located in the document"
        self.assertEqual(plain['astra'], {'position': 'proposed', 'quote': SNARE,
                                          'detail': 'Astra proposed this code, quoting the document verbatim.'})


# --- truth-4 and falsegreen-6: Corti's unlisted count is the engine's, per answer, in the row, the TXT and Checks --

LONG_SELECTED, LONG_CANDIDATE = '45385-SYNTHETIC-LONG-VALUE', '45380-SYNTHETIC-CANDIDATE'  # 26 and 25 characters
LISTED_COUNT = re.compile(r'returned (\d+) codes? that cannot be listed')
UNLISTED_TWO = ('It returned 2 codes that cannot be listed: empty, or longer than 10 characters (a CPT code has five). '
                'They are not shown and never truncated.')
UNLISTED_ONE = ('It returned 1 code that cannot be listed: empty, or longer than 10 characters (a CPT code has five). '
                'It is not shown and never truncated.')


def _txt(encounter):
    from studio import reports

    return reports.render_txt(reports.snapshot(encounter, 'draft')).decode('utf-8')


def _section(text, title):
    """The lines of the TXT section ``title`` (up to its blank line)."""
    return text.split(f'\n{title}\n', 1)[1].split('\n\n', 1)[0].splitlines()


def _block(lines, head):
    """The lines of one entry of a TXT section: the line starting with ``head`` and those under it."""
    start = next(index for index, line in enumerate(lines) if line.startswith(head))
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith('  - ')), len(lines))
    return lines[start:end]


def _span(text, quote):
    start = text.index(quote)
    return [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}]


def _corti_item(code, text, quote):
    return {'system': 'cpt', 'code': code, 'display': hp.CORTI_DISPLAY, 'evidences': _span(text, quote),
            'alternatives': []}


class CortiUnlistedCountMixin:
    """Corti's answer returns codes the engine cannot list beside codes it can: the engine's provider.unlisted check
    counts every one of them, whatever its role (selected, a candidate, an alternative), "The provider returned 2 codes
    that cannot be listed". Corti's row and its REVIEW PARTICIPANTS entry counted only the selected ones, "It returned 1
    code that cannot be listed", so the Checks tab showed both sentences one after the other (refutation round 4,
    truth-4). They now count what the engine counts, and say the same number."""

    def corti_row(self, detail):
        return next(row for row in detail['harness']['participants'] if row['name'] == 'corti')

    def run_with(self, edit):
        with self.corti_answer(edit):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        return encounter_id, self.detail(encounter_id)

    def engine_count(self, detail):
        (check,) = [c for c in detail['assessment']['encounter_checks'] if c['id'] == 'provider.unlisted']
        self.assertEqual(check['status'], 'warn')
        (count,) = LISTED_COUNT.findall(check['detail'])
        return int(count)

    def assertSaysTheEngineCount(self, encounter_id, detail, count, words, state):
        """The row, the page's row and Checks tab, and the TXT's REVIEW PARTICIPANTS and checks say ``count``."""
        self.assertEqual(self.engine_count(detail), count)
        row = self.corti_row(detail)
        self.assertEqual((row['detail'], row['unlisted_codes']), (f'{state[:1].upper()}{state[1:]}. {words}', count))
        self.assertEqual([int(n) for n in LISTED_COUNT.findall(row['detail'])], [count])
        page_row = browser('rowOf(page(), "data-participant", "corti")', detail)
        self.assertEqual([int(n) for n in LISTED_COUNT.findall(page_row)], [count])
        checks_tab = browser('visible(page("checks")).split("\\n").filter(l => /cannot be listed/.test(l))', detail)
        self.assertTrue(checks_tab)
        self.assertEqual({int(n) for line in checks_tab for n in LISTED_COUNT.findall(line)}, {count})
        text = _txt(self.encounter(encounter_id))
        lines = _block(_section(text, 'REVIEW PARTICIPANTS'), '  - Corti · ')
        self.assertEqual(lines[0], f'  - Corti · Corti · {state}')
        self.assertIn(f'    Not listed: {words}', lines)
        self.assertEqual({int(n) for line in text.splitlines() if 'cannot be listed' in line
                          for n in LISTED_COUNT.findall(line)}, {count})
        for value in (LONG_SELECTED, LONG_CANDIDATE):  # never served, never printed (I9)
            self.assertNotIn(value, json.dumps(detail))
            self.assertNotIn(value, text)

    def test_a_selected_code_and_a_candidate_it_cannot_list_are_two(self):
        def edit(answer, text):
            answer['codes'].append(_corti_item(LONG_SELECTED, text, SNARE))
            answer['candidates'] = [_corti_item(LONG_CANDIDATE, text, SNARE)]
        encounter_id, detail = self.run_with(edit)
        self.assertEqual(self.corti_row(detail)['codes'], ['45380', '45385'])
        self.assertSaysTheEngineCount(encounter_id, detail, 2, UNLISTED_TWO,
                                      'answered; its codes that can be listed were checked')

    def test_a_candidate_it_cannot_list_beside_selections_it_can(self):
        # every code it selected can be listed: the row said "Answered; its codes were checked." with no count, beside
        # the engine's "The provider returned 1 code that cannot be listed"
        def edit(answer, text):
            answer['candidates'] = [_corti_item(LONG_CANDIDATE, text, SNARE)]
        encounter_id, detail = self.run_with(edit)
        self.assertEqual(self.corti_row(detail)['codes'], ['45380', '45385'])
        self.assertSaysTheEngineCount(encounter_id, detail, 1, UNLISTED_ONE,
                                      'answered; its codes that can be listed were checked')

    def test_it_selected_only_a_code_it_cannot_list_beside_a_candidate_it_can(self):
        # the row said "none of its codes can be listed", beside the candidate the Alternatives list shows; it proposed
        # none that can be listed, and none was checked
        def edit(answer, text):
            answer['codes'] = [_corti_item(LONG_SELECTED, text, SNARE)]
            answer['candidates'] = [_corti_item('45380', text, BIOPSY)]
        encounter_id, detail = self.run_with(edit)
        [listed] = [p for p in self.proposals(detail, '45380', bucket='alternative') if self.origin(p) == 'primary']
        self.assertTrue(listed['exclusion_reason'].startswith('Provider candidate; not selected.'),
                        listed['exclusion_reason'])
        self.assertEqual(self.corti_row(detail)['codes'], [])
        self.assertSaysTheEngineCount(encounter_id, detail, 1, UNLISTED_ONE,
                                      'answered; it proposed no code that can be listed, so none was checked')
        page_row = browser('rowOf(page(), "data-participant", "corti")', detail)
        self.assertIn('It proposed no code that can be listed.', page_row)
        self.assertNotIn('none of its codes can be listed', page_row)

    def test_codes_it_returned_that_can_all_be_listed_read_as_before(self):
        def edit(answer, text):
            answer['candidates'] = [_corti_item('45378', text, hp.LAND)]
        encounter_id, detail = self.run_with(edit)
        row = self.corti_row(detail)
        self.assertEqual((row['detail'], row['codes'], row['unlisted_codes']),
                         ('Answered; its codes were checked.', ['45380', '45385'], 0))
        self.assertFalse([c for c in detail['assessment']['encounter_checks'] if c['id'] == 'provider.unlisted'])
        lines = _block(_section(_txt(self.encounter(encounter_id)), 'REVIEW PARTICIPANTS'), '  - Corti · ')
        self.assertEqual(lines[0], '  - Corti · Corti · answered; its codes were checked')
        self.assertFalse([line for line in lines if line.startswith('    Not listed: ')])


class CortiUnlistedCountTests(RecordedInterpretation, CortiUnlistedCountMixin, R2WordingCase):
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation.
    interpretations = TWO_EXTENTS_INTERPRETATIONS
    pass


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyUnlistedCountTests(RecordedInterpretation, CortiUnlistedCountMixin, R2WordingCase):
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation, and I1's chain is extract, interpret, analyze, predict and assess.
    interpretations = TWO_EXTENTS_INTERPRETATIONS
    def test_the_chain_is_i1_s(self):
        def edit(answer, text):
            answer['candidates'] = [_corti_item(LONG_CANDIDATE, text, SNARE)]
        encounter_id, detail = self.run_with(edit)
        self.assertEqual(self.kinds(encounter_id), ['extract', 'interpret', 'analyze', 'predict', 'assess'])
        self.assertEqual(detail['harness']['phase'], 0)


@applied
@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class SecondReviewUnlistedTests(OperatorReads, TestCase):
    """falsegreen-6: Corti's row counts the codes its answers returned that cannot be listed - "its primary run and any
    bounded second review" - yet no test had a second review return one: a mutant counting the primary run alone made
    the row read "Answered; its codes were checked." with 0, and every gate stayed green. The second review's count is
    pinned here, through the real ask and drain (tests.test_services_second_review's two-pass Corti, read by the real
    normalizer), as the engine's provider.second_review check says it: "The second review returned 1 code ...", and the
    row and the TXT say it of the second review ("Its second review returned 1 code ..."), apart from the primary's."""

    SECOND_LONG = '45380-SYNTHETIC-LONG-VALUE'  # 26 characters
    FIRST_LONG = '45385-SYNTHETIC-LONG-VALUE'

    def setUp(self):
        from unittest import mock

        from tests.test_services_second_review import TwoPassProvider

        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer_r4fg6'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = TwoPassProvider(first=[('45385', 'was removed with a cold snare')],
                                        later=[('45380', 'was sampled with cold biopsy forceps'),
                                               (self.SECOND_LONG, 'was sampled with cold biopsy forceps'),
                                               ('45385', 'was removed with a cold snare')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_second_review(self):
        from tests.test_services_second_review import REPORT, ask

        reply = self.client.post('/api/encounters', {'text': REPORT, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        encounter_id = reply.json()['id']
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertIsNotNone(encounter.current_assessment.second_run_id)
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        return encounter, detail

    def checks(self, detail):
        return {c['id']: c for c in detail['assessment']['encounter_checks']}

    def corti_lines(self, encounter):
        return _block(_section(_txt(encounter), 'REVIEW PARTICIPANTS'), '  - Corti · ')

    def test_a_code_the_second_review_returned_that_cannot_be_listed_is_counted_as_its_own(self):
        encounter, detail = self.run_second_review()
        checks = self.checks(detail)
        self.assertNotIn('provider.unlisted', checks)  # the primary answer returned none
        self.assertEqual(LISTED_COUNT.findall(checks['provider.second_review']['detail']), ['1'])
        self.assertIn('The second review returned 1 code that cannot be listed',
                      checks['provider.second_review']['detail'])
        row = next(r for r in detail['harness']['participants'] if r['name'] == 'corti')
        second = UNLISTED_ONE.replace('It returned', 'Its second review returned', 1)
        self.assertEqual((row['state'], row['detail'], row['codes'], row['unlisted_codes']),
                         ('done', f'Answered; its codes that can be listed were checked. {second}', ['45380', '45385'],
                          1))
        lines = self.corti_lines(encounter)
        self.assertEqual(lines[0], '  - Corti · Corti · answered; its codes that can be listed were checked')
        self.assertIn(f'    Not listed: {second}', lines)
        self.assertNotIn(self.SECOND_LONG, json.dumps(detail))
        self.assertNotIn(self.SECOND_LONG, '\n'.join(lines))

    def test_each_answer_s_count_is_said_as_its_own_check_says_it(self):
        self.provider.first = [('45385', 'was removed with a cold snare'),
                               (self.FIRST_LONG, 'was removed with a cold snare')]
        encounter, detail = self.run_second_review()
        checks = self.checks(detail)
        self.assertEqual(LISTED_COUNT.findall(checks['provider.unlisted']['detail']), ['1'])
        self.assertEqual(LISTED_COUNT.findall(checks['provider.second_review']['detail']), ['1'])
        row = next(r for r in detail['harness']['participants'] if r['name'] == 'corti')
        second = UNLISTED_ONE.replace('It returned', 'Its second review returned', 1)
        self.assertEqual((row['detail'], row['unlisted_codes']),
                         (f'Answered; its codes that can be listed were checked. {UNLISTED_ONE} {second}', 2))
        self.assertIn(f'    Not listed: {UNLISTED_ONE} {second}', self.corti_lines(encounter))

    def test_a_second_review_the_engine_did_not_read_is_not_counted(self):
        # the engine reads the second review only where its documented-service reading is consistent, and then records
        # its provider.second_review check; read without that record (the same runs), none of its codes is counted, as
        # the engine counted none
        from studio import serializers

        encounter, _ = self.run_second_review()
        assessment = encounter.current_assessment
        self.assertEqual(serializers.corti_unlisted_counts(assessment), (0, 1))
        unread = SimpleNamespace(provider_run=assessment.provider_run, second_run=assessment.second_run,
                                 encounter_checks=[c for c in assessment.encounter_checks
                                                   if c['id'] != 'provider.second_review'])
        self.assertEqual(serializers.corti_unlisted_counts(unread), (0, 0))
        self.assertEqual(serializers.corti_unlisted(unread), 0)


# --- truth-5: the retrieval-failure note says what failed - loading the stored passages, or the retrieval itself ----

# Where the stored CMS passages cannot be loaded (a passage changed after import), the retrieval never runs: nothing is
# retrieved, so the note never says CPT Studio could not record which facts and passages it retrieved (refutation
# round 4, truth-5). One sentence for each kind of failure, with what it leaves of the checks: where an installed CMS
# reference file applied, the checks read the CMS facts before that; where none did, none was checked, and why.
LOAD_APPLIED = ("Reference validation failed: CPT Studio could not load the stored CMS reference passages ({error}, "
                "logged), so the retrieval for this assessment's codes did not run and no CMS reference fact or "
                "passage is listed here. Each code's checks read the CMS facts before that and stand as shown; "
                "retrieval only informs the reviewer and decides no status, so the assessment stands as made.")
LOAD_UNCHECKED = ("Reference validation failed: CPT Studio could not load the stored CMS reference passages ({error}, "
                  "logged), so the retrieval for this assessment's codes did not run and no CMS reference fact or "
                  "passage is listed here. {why} Retrieval only informs the reviewer and decides no status, so the "
                  "assessment stands as made.")
RETRIEVE_APPLIED = ("Reference validation failed: CPT Studio's retrieval for this assessment's codes failed "
                    "({error}, logged), so no CMS reference fact or passage is listed here. Each code's checks read "
                    "the CMS facts before that and stand as shown; retrieval only informs the reviewer and decides no "
                    "status, so the assessment stands as made.")
RETRIEVE_UNCHECKED = ("Reference validation failed: CPT Studio's retrieval for this assessment's codes failed "
                      "({error}, logged), so no CMS reference fact or passage is listed here. {why} Retrieval only "
                      "informs the reviewer and decides no status, so the assessment stands as made.")
NO_DATE_WHY = ('No code was checked against the CMS reference files: no service date is established for this '
               'encounter, so no dated CMS reference file applies.')
# The words that claim something was retrieved before the failure, or recorded: false where the retrieval never ran.
RETRIEVED_CLAIMS = ('could not record', 'it retrieved', 'were retrieved', 'was retrieved')


class RetrievalFailureStepMixin:
    """The assess stage's retrieval: the stored passages are loaded, then the facts and passages are retrieved for the
    codes. A stored passage changed after import fails the load (its sha256 check), so the retrieval never runs - and
    the note, the API's reference validation, the page's row and the TXT said "CPT Studio could not record which CMS
    reference facts and passages it retrieved", while every card pointed to that row for what failed (refutation round
    4, truth-5). Each now says the failure it is."""

    def run_failing(self, text, *, retrieve_raises=False):
        from unittest import mock

        from studio import jobs
        from tests.test_harness2_r2_truth import tamper_one_passage

        if not retrieve_raises:
            tamper_one_passage()
        loads = mock.patch.object(jobs.reference_passages, 'load_passages',
                                  wraps=jobs.reference_passages.load_passages)
        retrieves = mock.patch.object(jobs.reference_passages, 'retrieve',
                                      **({'side_effect': RuntimeError('synthetic retrieval defect')}
                                         if retrieve_raises else {'wraps': jobs.reference_passages.retrieve}))
        encounter_id = self.create(text)
        with loads as load, retrieves as retrieve, self.assertLogs('studio.jobs', level='ERROR') as caught:
            drain()
        self.assertTrue(load.called)
        self.calls = (load.call_count, retrieve.call_count)
        self.logged = caught.output
        return encounter_id

    def assertSaysWhatFailed(self, encounter_id, note, day):
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(final.retrieval, [{'code': '', 'service_date': day, 'facts': [], 'passages': [],
                                            'lookups': [], 'notes': [note], 'failed': True}])
        detail = self.detail(encounter_id)
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['detail'], block['codes_checked'], block['passages']),
                         ('failed', note, 0, 0))
        row = browser('rowOf(page(), "data-participant", "reference_validation")', detail)
        self.assertIn(note, row)
        retrieval = _section(_txt(self.encounter(encounter_id)), 'REFERENCE RETRIEVAL')
        self.assertIn(f'  - {note}', retrieval)
        # every card points to the row for what failed, and the row says it
        cards = browser('cards(page()).map(card => visible(card))', detail)
        self.assertTrue(cards)
        pointer = browser('app.RETRIEVAL_FAILED', {})
        self.assertTrue(pointer.endswith('the Reference validation row says what failed.'), pointer)
        for card in cards:
            self.assertIn(pointer, card)
        return final, detail, row, retrieval

    def assertTheChecksReadTheCmsFacts(self, final):
        decidable = list(final.proposals.exclude(bucket='alternative'))
        self.assertTrue(decidable)
        for proposal in decidable:  # what the note's second sentence says: each code's checks read the CMS facts
            statuses = {check['id']: check['status'] for check in proposal.checks}
            self.assertEqual((statuses['pfs.presence'], statuses['mue.units']), ('pass', 'pass'), proposal.code)

    def test_a_passage_that_cannot_be_loaded_is_said_so_where_a_cms_file_applied(self):
        encounter_id = self.run_failing(TWO_EXTENTS)
        self.assertTrue(any('does not match its sha256' in line for line in self.logged), self.logged)
        self.assertEqual(self.calls[1], 0)  # the retrieval never ran
        final, detail, row, retrieval = self.assertSaysWhatFailed(encounter_id, LOAD_APPLIED.format(error='ValueError'),
                                                                  '2026-10-14')
        self.assertTrue([source['key'] for source in final.reference_sources if source.get('applies')])
        self.assertTheChecksReadTheCmsFacts(final)
        for said in (detail['harness']['reference_validation']['detail'], row, '\n'.join(retrieval)):
            for claim in RETRIEVED_CLAIMS:
                self.assertNotIn(claim, said)

    def test_a_passage_that_cannot_be_loaded_is_said_so_where_no_cms_file_applied(self):
        from tests.test_harness2_r2_truth import NO_DATE

        encounter_id = self.run_failing(NO_DATE)
        self.assertEqual(self.calls[1], 0)
        final, detail, row, retrieval = self.assertSaysWhatFailed(
            encounter_id, LOAD_UNCHECKED.format(error='ValueError', why=NO_DATE_WHY), None)
        self.assertFalse([source['key'] for source in final.reference_sources if source.get('applies')])
        for said in (detail['harness']['reference_validation']['detail'], row, '\n'.join(retrieval)):
            for claim in RETRIEVED_CLAIMS + ('read the CMS facts', 'read the facts'):
                self.assertNotIn(claim, said)

    def test_a_retrieval_that_fails_after_the_passages_loaded_is_said_so(self):
        encounter_id = self.run_failing(TWO_EXTENTS, retrieve_raises=True)
        self.assertEqual(self.calls, (self.calls[0], self.calls[0]))  # loaded, then the retrieval ran and raised
        self.assertGreater(self.calls[0], 0)
        final, _, _, _ = self.assertSaysWhatFailed(encounter_id, RETRIEVE_APPLIED.format(error='RuntimeError'),
                                                   '2026-10-14')
        self.assertTheChecksReadTheCmsFacts(final)
        self.assertNotIn('synthetic retrieval defect', json.dumps(final.retrieval))  # logged, never recorded


class RetrievalFailureStepTests(RecordedInterpretation, RetrievalFailureStepMixin, R2WordingCase):
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation.
    interpretations = TWO_EXTENTS_INTERPRETATIONS
    pass


@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyRetrievalFailureStepTests(RecordedInterpretation, RetrievalFailureStepMixin, R2WordingCase):
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation, and I1's chain is extract, interpret, analyze, predict and assess.
    interpretations = TWO_EXTENTS_INTERPRETATIONS
    def test_the_chain_is_i1_s(self):
        encounter_id = self.run_failing(TWO_EXTENTS)
        self.assertEqual(self.kinds(encounter_id), ['extract', 'interpret', 'analyze', 'predict', 'assess'])


class RetrievalFailureEntryStepTests(OperatorReads, TestCase):
    """jobs.retrieval_failure words the step that failed - loading the stored passages, or the retrieval - and what it
    leaves of the checks; a caller that names no step, or one it does not know, is given the retrieval's own sentence,
    which claims nothing was loaded or read (fail closed)."""

    def test_one_sentence_for_each_step_and_each_reading_of_the_checks(self):
        from datetime import date

        from studio import jobs

        day = date(2026, 10, 21)
        why = ('No code was checked against the CMS reference files: no installed CMS reference file applies to the '
               'service date, 2026-10-21.')
        cases = [((jobs.RETRIEVAL_STEP_LOAD, True), LOAD_APPLIED.format(error='ValueError')),
                 ((jobs.RETRIEVAL_STEP_LOAD, False), LOAD_UNCHECKED.format(error='ValueError', why=why)),
                 ((jobs.RETRIEVAL_STEP_RETRIEVE, True), RETRIEVE_APPLIED.format(error='ValueError')),
                 ((jobs.RETRIEVAL_STEP_RETRIEVE, False), RETRIEVE_UNCHECKED.format(error='ValueError', why=why))]
        for (step, applied), note in cases:
            with self.subTest(step=step, applied=applied):
                entry = jobs.retrieval_failure(day, 'ValueError', applied=applied, step=step)
                self.assertEqual(entry, {'code': '', 'service_date': '2026-10-21', 'facts': [], 'passages': [],
                                         'lookups': [], 'notes': [note], 'failed': True})
        self.assertEqual(len({note for _, note in cases}), 4)
        self.assertEqual((jobs.RETRIEVAL_LOAD_FAILED, jobs.RETRIEVAL_LOAD_FAILED_UNCHECKED, jobs.RETRIEVAL_FAILED,
                          jobs.RETRIEVAL_FAILED_UNCHECKED),
                         (LOAD_APPLIED, LOAD_UNCHECKED, RETRIEVE_APPLIED, RETRIEVE_UNCHECKED))
        # fail closed: no step named, or one not known, is the retrieval's own sentence
        for kwargs in ({}, {'step': 'unknown'}):
            for applied in (True, False):
                self.assertEqual(jobs.retrieval_failure(day, 'ValueError', applied=applied, **kwargs),
                                 jobs.retrieval_failure(day, 'ValueError', applied=applied,
                                                        step=jobs.RETRIEVAL_STEP_RETRIEVE))
        for note in (RETRIEVE_APPLIED, RETRIEVE_UNCHECKED, LOAD_APPLIED, LOAD_UNCHECKED):
            for claim in RETRIEVED_CLAIMS:
                self.assertNotIn(claim, note)
