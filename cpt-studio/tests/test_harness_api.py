"""The harness in the API (HARNESS.md 7, I4): the encounter view's permissions and harness block, each proposal's
proposers, participant positions, reference check and retrieval, the Activity wording, and the owner-only trace.

Synthetic data only; no network. Pipeline-driven cases use the fakes of tests.test_harness_pipeline; the field cases
persist hand-built assessments through review.persist_assessment.
"""
import json
import sys
import types
from dataclasses import replace
from datetime import date
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, operator, review, serializers
from tests.support import factories as f
from tests.support.operator import OperatorReads
from tests.support import operator as operator_access
from tests.support import pipeline_factories as pf
from tests.test_harness_pipeline import BOTH, TIME_QUOTE, HarnessCase, fake_passages
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE

PTP = 'NCCI procedure-to-procedure edits are not connected'
# A synthetic stand-in for wording a participant might write into a field CPT Studio reads as a code or an id (never AMA
# text): a reading keeps a code that is not five characters as given (refutation r1 IND-1).
DESCRIPTOR_LIKE = ('45385 SYNTHETIC-PLACEHOLDER; with removal of lesion(s) by PLACEHOLDER technique, single or '
                   'multiple')
# moved by refutation round 4 (R4-SHAPES, shapes-1): a participant's code is listed only in a CPT or HCPCS code's shape,
# and one it cannot list is counted in the engine's sentence for a participant's codes
UNLISTED_ONE = ('It returned 1 code that cannot be listed: not in the shape of a CPT code (four digits, then a digit or a '
                'capital letter) or of an HCPCS Level II code (a capital letter, then four digits). It is not shown and '
                'never truncated.')


def record(name, state, *, run=None, codes=(), not_coded=(), reason='', unverified=0, model=''):
    """An Assessment.participants entry as the assess stage writes it."""
    return {'name': name, 'state': state, 'run': str(run.pk) if run is not None else None,
            'adapter_version': f'{name}-test@1' if run is not None else '', 'requested_model': model,
            'returned_model': model, 'unverified_quotes': unverified, 'reason': reason,
            'codes': [{'code': code, 'quote': quote} for code, quote in codes],
            'not_coded': [{'code': code, 'reason': why, 'quote': quote} for code, why, quote in not_coded]}


class FieldCase(OperatorReads, TestCase):
    """A hand-built assessment with participant records, proposals of each origin and a retrieval trace."""

    def setUp(self):
        self.s = pf.scenario()
        self.owner = f.member(self.s.workspace, f.user('ownerx'), role=models.Membership.OWNER)

    def persist(self, result, *, participants=(), retrieval=()):
        enc = self.s.encounter
        enc.refresh_from_db()
        return review.persist_assessment(encounter=enc, revision=enc.current_revision, context=enc.current_context,
                                         routing_run=pf.routing(enc.current_revision),
                                         provider_run=pf.provider_run(enc, enc.current_revision), result=result,
                                         participants=participants, retrieval=retrieval)

    def detail(self, user=None):
        client = Client()
        client.force_login(user or self.s.reviewer)
        response = client.get(f'/ops/api/encounters/{self.s.encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def proposals(self, data):
        return {p['code']: p for p in data['assessment']['proposals']}


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class PermissionsTests(FieldCase):
    def test_is_owner_beside_can_review(self):
        # harness@2 (HARNESS.md 12.6): permissions.can_confirm is can_review
        pf.assess(self.s.encounter, pf.standard_result())
        self.assertEqual(self.detail(self.owner)['permissions'],
                         {'can_review': True, 'is_owner': True, 'can_confirm': True})
        self.assertEqual(self.detail(self.s.reviewer)['permissions'],
                         {'can_review': True, 'is_owner': False, 'can_confirm': True})
        self.assertEqual(self.detail(self.s.viewer)['permissions'],
                         {'can_review': False, 'is_owner': False, 'can_confirm': False})


class ProposalFieldsTests(FieldCase):
    def setUp(self):
        super().setUp()
        self.items = (
            replace(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]), support={'origin': 'primary',
                                                                               'proposed_by': ['astra']}),
            replace(pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE], checks=pf.standard_checks(pfs_presence='warn')),
                    support={'origin': 'participant', 'proposed_by': ['fable', 'astra']}),
            pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                        checks=pf.standard_checks(pfs_presence='not_verified')),
            pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative', checks=()),
        )
        self.records = [record('astra', 'read', run=None, codes=[('43239', pf.EGD_PASSAGE), ('45385', '')],
                               not_coded=[('45378', 'not_performed_at_this_encounter', pf.PLAN_PASSAGE)],
                               model='gpt-6-astra'),
                        record('fable', 'refused', reason='The response was cut off at the output limit.',
                               model='claude-fable-5-1')]
        self.retrieval = [{'code': '43239', 'service_date': '2026-10-21',
                           'facts': [{'source_key': 'cms-pfs-rvu26d', 'release': 'RVU26D',
                                      'effective': ['2026-10-01', '2026-12-31'], 'sha256': '0' * 64,
                                      'field': 'status', 'value': 'A'},
                                     {'source_key': 'cms-mue-test', 'release': '2026-Q4', 'effective': [], 'sha256': '',
                                      'field': 'mai', 'value': {'indicator': '2'}}],
                           'passages': [{'source_key': 'cms-ncci-manual-test', 'release': 'Revision 1/1/2026',
                                         'passage_key': 'vi-c-1', 'section': 'Chapter VI §C', 'page': '12',
                                         'topic': 'pfs.endo_base', 'topic_value': '43235', 'sha256': '1' * 64,
                                         'text': 'Synthetic passage text.'}],
                           'lookups': ['43239: prefetched'], 'notes': []}]
        self.persist(pf.result(*self.items), participants=self.records, retrieval=self.retrieval)

    def test_proposed_by_names_corti_and_the_participants_the_engine_recorded(self):
        proposals = self.proposals(self.detail())
        self.assertEqual(proposals['43239']['proposed_by'], ['corti', 'astra'])
        self.assertEqual(proposals['45385']['proposed_by'], ['astra', 'fable'])  # harness order, origin participant
        self.assertEqual(proposals['45378']['proposed_by'], ['corti'])
        self.assertEqual(proposals['45380']['proposed_by'], ['corti'])

    def test_participant_positions_come_from_the_readings_that_were_used(self):
        proposals = self.proposals(self.detail())
        positions = proposals['43239']['participant_positions']
        # moved by refutation round 6 (R6-MEANING, negation-4, ownership-7): the 'proposed' detail is the engine's own
        # wording, "quoting the document verbatim", never "with evidence located in the document"
        self.assertEqual(positions['astra'], {'position': 'proposed', 'quote': pf.EGD_PASSAGE,
                                              'detail': 'Astra proposed this code, quoting the document verbatim.'})
        self.assertEqual(positions['fable']['position'], 'not_run')
        self.assertIn('the reading was not used: The response was cut off', positions['fable']['detail'])
        self.assertEqual(proposals['45385']['participant_positions']['astra']['quote'], '')
        advised = proposals['45378']['participant_positions']['astra']
        self.assertEqual((advised['position'], advised['quote']), ('advised_not_to_code', pf.PLAN_PASSAGE))
        self.assertIn('not performed at this encounter', advised['detail'])
        self.assertEqual(proposals['45380']['participant_positions']['astra']['position'], 'not_proposed')

    def test_positions_are_empty_when_no_participant_was_configured(self):
        self.persist(pf.result(*self.items[2:]), participants=[jobs.not_configured_record('astra'),
                                                                jobs.not_configured_record('fable')])
        for proposal in self.detail()['assessment']['proposals']:
            self.assertEqual(proposal['participant_positions'], {})

    def test_reference_check_is_passed_attention_or_not_verified_and_always_names_ptp(self):
        proposals = self.proposals(self.detail())
        self.assertEqual(proposals['43239']['reference_check']['state'], 'passed')
        self.assertEqual(proposals['45385']['reference_check']['state'], 'attention')
        self.assertEqual(proposals['45378']['reference_check']['state'], 'not_verified')
        self.assertEqual(proposals['45380']['reference_check']['state'], 'not_verified')  # no CMS check ran
        for proposal in proposals.values():
            self.assertIn(PTP, proposal['reference_check']['detail'])
        self.assertIn('Present in the CMS fee schedule file: passed', proposals['43239']['reference_check']['detail'])

    def test_retrieval_lists_the_code_s_facts_then_its_passages(self):
        proposals = self.proposals(self.detail())
        self.assertEqual(proposals['43239']['retrieval'], [
            {'kind': 'fact', 'source_key': 'cms-pfs-rvu26d', 'release': 'RVU26D', 'label': 'status', 'value': 'A',
             'page': '', 'section': '', 'text': ''},
            {'kind': 'fact', 'source_key': 'cms-mue-test', 'release': '2026-Q4', 'label': 'mai',
             'value': '{"indicator": "2"}', 'page': '', 'section': '', 'text': ''},
            {'kind': 'passage', 'source_key': 'cms-ncci-manual-test', 'release': 'Revision 1/1/2026',
             'label': 'pfs.endo_base 43235', 'value': '', 'page': '12', 'section': 'Chapter VI §C',
             'text': 'Synthetic passage text.'}])
        self.assertEqual(proposals['45385']['retrieval'], [])

    def test_proposed_reference_checked_and_approved_stay_apart(self):
        # I3/I4: two proposers and a passing check approve nothing; the decision is the member's alone
        proposal = self.proposals(self.detail())['43239']
        self.assertEqual((proposal['decision'], proposal['decision_state']), (None, 'undecided'))
        self.s.decide('sel:0', 'approve')
        proposal = self.proposals(self.detail())['43239']
        self.assertEqual(proposal['decision_state'], 'approved')
        self.assertEqual((proposal['proposed_by'], proposal['reference_check']['state']),
                         (['corti', 'astra'], 'passed'))


class ReferenceValidationTests(FieldCase):
    def test_done_when_every_decidable_code_is_traced(self):
        models.PassageSource.objects.create(
            key='cms-ncci-manual-test', kind='cms-ncci-policy-manual', publisher='CMS',
            title='NCCI Policy Manual for Medicare Services 2026, Chapter VI', release='Revision 1/1/2026',
            url='https://www.cms.gov/', sha256='2' * 64, retrieved_at=timezone.now(), effective_start=date(2026, 1, 1),
            effective_end=date(2026, 12, 31), license_note='CMS public file.', scope_note='Chapter VI only.')
        items = (pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                 pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative'))
        retrieval = [{'code': '43239', 'service_date': '2026-10-21', 'facts': [],
                      'passages': [{'source_key': 'cms-ncci-manual-test', 'release': 'Revision 1/1/2026',
                                    'section': 'Chapter VI §C', 'page': '12', 'text': 'Synthetic.'}],
                      'lookups': [], 'notes': []}]
        self.persist(pf.result(*items), participants=[jobs.not_configured_record('astra'),
                                                      jobs.not_configured_record('fable')], retrieval=retrieval)
        block = self.detail()['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked'], block['passages']), ('done', 1, 1))
        self.assertEqual(block['sources'], [{'key': 'cms-ncci-manual-test',
                                             'title': 'NCCI Policy Manual for Medicare Services 2026, Chapter VI',
                                             'release': 'Revision 1/1/2026', 'effective_start': '2026-01-01',
                                             'effective_end': '2026-12-31'}])
        self.assertEqual(block['not_connected'], ['NCCI procedure-to-procedure edits (AMA licence agreement not '
                                                  'accepted)', 'AMA CPT descriptors and guidelines (no licence)',
                                                  'Payer policies'])

    def test_a_malformed_trace_shows_only_its_well_formed_items(self):
        from studio import reports

        retrieval = [{'code': '43239', 'service_date': '2026-10-21', 'facts': 'not a list',
                      'passages': [None, 'text', {'source_key': 'cms-ncci-manual-test', 'release': 'Revision 1/1/2026',
                                                  'section': 'Chapter VI §C', 'page': '12', 'text': 'Synthetic.'}],
                      'lookups': 'not a list', 'notes': [3, 'Synthetic note.']}]
        self.persist(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE])), retrieval=retrieval,
                     participants=[jobs.not_configured_record('astra'), jobs.not_configured_record('fable')])
        data = self.detail()
        self.assertEqual([item['kind'] for item in data['assessment']['proposals'][0]['retrieval']], ['passage'])
        self.assertEqual(data['harness']['reference_validation']['passages'], 1)
        text = reports.render_txt(reports.snapshot(self.s.encounter, 'draft')).decode('utf-8')
        retrieval_lines = text.split('\nREFERENCE RETRIEVAL\n', 1)[1].split('\n\n', 1)[0].splitlines()
        self.assertEqual(retrieval_lines[:4], ['  - 43239 · service date 2026-10-21',
                                               '    Passage: cms-ncci-manual-test, release Revision 1/1/2026 · section '
                                               'Chapter VI §C · page 12:', '        "Synthetic."',
                                               '    Note: Synthetic note.'])

    def test_never_done_of_nothing(self):
        # no decidable code and no trace - which is also all an absent passages module leaves - is 'not_run', never a
        # vacuous 'done' over zero codes
        self.persist(pf.result(pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative')),
                     participants=[jobs.not_configured_record('astra'), jobs.not_configured_record('fable')])
        block = self.detail()['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked'], block['passages']), ('not_run', 0, 0))

    def test_not_run_when_a_decidable_code_has_no_trace_or_the_assessment_predates_the_harness(self):
        pf.assess(self.s.encounter, pf.standard_result())  # recorded before the harness: no participant entry
        self.assertEqual(self.detail()['harness']['reference_validation']['state'], 'not_run')
        self.persist(pf.standard_result(), participants=[jobs.not_configured_record('astra'),
                                                         jobs.not_configured_record('fable')])
        self.assertEqual(self.detail()['harness']['reference_validation']['state'], 'not_run')
        self.assertEqual(self.detail()['harness']['reference_validation']['detail'], '')  # said only of 'failed'

    # refutation round 1, parity-1: a retrieval that raised is recorded as one entry marked failed
    # (jobs.retrieval_failure); the page says reference validation failed, never 'not_run' or 'done'

    NOT_CONNECTED = ['NCCI procedure-to-procedure edits (AMA licence agreement not accepted)',
                     'AMA CPT descriptors and guidelines (no licence)', 'Payer policies']

    def test_failed_when_the_retrieval_failed_with_its_note_as_the_detail(self):
        failure = jobs.retrieval_failure(date(2026, 10, 21), 'RuntimeError')
        self.persist(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                               pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded')),
                     participants=[jobs.not_configured_record('astra'), jobs.not_configured_record('fable')],
                     retrieval=[failure])
        (note,) = failure['notes']
        self.assertTrue(note.startswith('Reference validation failed: '), note)
        # the failed entry is no code checked: nothing counted, no source, and the detail is the entry's own note
        self.assertEqual(self.detail()['harness']['reference_validation'],
                         {'state': 'failed', 'detail': note, 'codes_checked': 0, 'passages': 0, 'sources': [],
                          'not_connected': self.NOT_CONNECTED})

    def test_failed_whenever_any_entry_failed_beside_a_trace_and_a_failure_with_no_note_says_so(self):
        trace = {'code': '43239', 'service_date': '2026-10-21', 'facts': [],
                 'passages': [{'source_key': 'cms-ncci-manual-test', 'release': 'Revision 1/1/2026',
                               'section': 'Chapter VI §C', 'page': '12', 'text': 'Synthetic.'}],
                 'lookups': [], 'notes': []}
        unnoted = {**jobs.retrieval_failure(None, 'ValueError'), 'notes': ['', 3]}
        self.persist(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE])),
                     participants=[jobs.not_configured_record('astra'), jobs.not_configured_record('fable')],
                     retrieval=[trace, unnoted])
        block = self.detail()['harness']['reference_validation']
        # every decidable code is traced, which alone would read 'done': one failed entry makes it 'failed'
        self.assertEqual((block['state'], block['detail'], block['codes_checked'], block['passages']),
                         ('failed', serializers.REFERENCE_FAILED, 1, 1))
        self.assertTrue(serializers.REFERENCE_FAILED.startswith('Reference validation failed: '))

    def test_waiting_while_processing_even_after_a_failed_retrieval(self):
        # a stage in flight makes a new assessment, whose retrieval has not run yet
        self.persist(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE])),
                     participants=[jobs.not_configured_record('astra'), jobs.not_configured_record('fable')],
                     retrieval=[jobs.retrieval_failure(date(2026, 10, 21), 'RuntimeError')])
        enc = self.s.encounter
        pf.job(enc, enc.current_revision, models.Job.ASSESS, models.Job.QUEUED, context=enc.current_context)
        block = self.detail()['harness']['reference_validation']
        self.assertEqual((block['state'], block['detail']), ('waiting', ''))


class EstimatedCostTests(FieldCase):
    """A participant run's estimated cost (HARNESS.md 6, 11.2) is the installed pricing module's estimate, in four
    decimals; a tool loop is priced exchange by exchange, never its summed usage as one request (refutation r1 FG-3 and
    sends-4: review read a key pricing never returns, so no cost was ever shown)."""

    def make_run(self, name='astra', *, usage, basis='provider_reported_tokens', exchanges=()):
        enc = self.s.encounter
        run = pf.provider_run(enc, enc.current_revision, provider=name, usage=usage)
        models.ProviderRun.objects.filter(pk=run.pk).update(
            purpose='independent', usage_basis=basis,
            requested_model={'astra': 'gpt-6-astra', 'fable': 'claude-fable-5-1'}.get(name, ''))
        for turn, reported in enumerate(exchanges, start=1):
            models.ProviderExchange.objects.create(run=run, turn=turn, request_body={}, request_sha256='0' * 64,
                                                   state='succeeded', http_status=200, usage=reported)
        run.refresh_from_db()
        return run

    def test_the_cost_is_the_installed_pricing_estimate_in_four_decimals(self):
        from studio.participants import pricing

        usage = {'input_tokens': 1200, 'output_tokens': 300}
        self.assertEqual(pricing.estimate('gpt-6-astra', usage)['estimated_usd'], '0.027000')
        self.assertEqual(review.estimated_cost(self.make_run(usage=usage)), '0.0270')
        self.assertEqual(review.estimated_cost(self.make_run('fable', usage={'input_tokens': 1000,
                                                                              'output_tokens': 100})), '0.0150')
        # rounded half up, as pricing rounds: $0.000050 is never shown as $0.0000
        self.assertEqual(review.estimated_cost(self.make_run(usage={'input_tokens': 5, 'output_tokens': 0})),
                         '0.0001')

    def test_a_tool_loop_is_priced_exchange_by_exchange_never_as_one_request(self):
        from studio.participants import loop

        exchanges = [{'input_tokens': 150_000, 'output_tokens': 1000}, {'input_tokens': 150_000, 'output_tokens': 1000}]
        summed = loop.summed_usage(exchanges)
        self.assertEqual(summed, {'input_tokens': 300_000, 'output_tokens': 2000})
        run = self.make_run(usage=summed, basis=loop.LOOP_USAGE_BASIS, exchanges=exchanges)
        # two requests below Astra's long-context threshold: 2 x (150,000 x $10/M + 1,000 x $50/M); as one request of
        # 300,000 input tokens it would be priced long context, at $6.1500
        self.assertEqual(review.estimated_cost(run), '3.1000')

    def test_a_loop_whose_exchanges_do_not_add_up_to_its_usage_has_no_estimate(self):
        from studio.participants import loop

        usage = {'input_tokens': 300_000, 'output_tokens': 2000}
        partial = self.make_run(usage=usage, basis=loop.LOOP_USAGE_BASIS,
                                exchanges=[{'input_tokens': 150_000, 'output_tokens': 1000}])
        missing = self.make_run(usage=usage, basis=loop.LOOP_USAGE_BASIS)
        self.assertEqual((review.estimated_cost(partial), review.estimated_cost(missing)), (None, None))

    def test_no_estimate_for_corti_for_no_usage_or_for_usage_pricing_cannot_price(self):
        corti = pf.provider_run(self.s.encounter, self.s.encounter.current_revision)
        self.assertIsNone(review.estimated_cost(corti))  # credits, not USD
        self.assertIsNone(review.estimated_cost(self.make_run(usage={})))  # a reuse: no new usage
        self.assertIsNone(review.estimated_cost(self.make_run(usage={'input_tokens': '1200', 'output_tokens': 300})))
        with mock.patch.dict(sys.modules, {'studio.participants.pricing': None}):  # no pricing module installed
            self.assertIsNone(review.estimated_cost(self.make_run(usage={'input_tokens': 1200, 'output_tokens': 300})))


@override_settings(**LIVE, **BOTH)
class HarnessBlockTests(OperatorReads, HarnessCase):
    def detail(self, encounter_id):
        response = self.client.get(f'/ops/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def rows(self, encounter_id):
        return {row['name']: row for row in self.detail(encounter_id)['harness']['participants']}

    def test_three_rows_in_order_with_each_participant_s_outcome(self):
        # the installed pricing module, never a stand-in (refutation r1 FG-3: a fake hid that no cost was ever shown)
        encounter_id = self.create()
        drain()
        harness = self.detail(encounter_id)['harness']
        rows = harness['participants']
        self.assertEqual([(r['name'], r['label'], r['vendor'], r['model']) for r in rows],
                         [('corti', 'Corti', 'Corti', ''), ('astra', 'Astra', 'OpenAI', 'gpt-6-astra'),
                          ('fable', 'Fable', 'Anthropic', 'claude-fable-5-1')])
        corti, astra, fable = rows
        self.assertEqual((corti['state'], corti['codes'], corti['estimated_cost_usd']), ('done', ['99213'], None))
        # 99214's only quote was not found in the document, so the reading did not propose it (refutation round 4,
        # truth-2: the row named it among the codes proposed; this pin moved with it)
        self.assertEqual((astra['state'], astra['codes'], astra['unverified_quotes'], astra['returned_model']),
                         ('done', ['99213'], 1, 'gpt-6-astra'))
        self.assertIn('1 of its quotes was not found', astra['detail'])
        self.assertEqual(astra['estimated_cost_usd'], '0.0270')  # 1,200 in x $10/M + 300 out x $50/M
        stored = self.runs_of(encounter_id, 'astra')[0]  # the row serves its run's usage and basis as recorded
        self.assertEqual((astra['usage'], astra['usage_basis'], astra['reused']),
                         ({'input_tokens': 1200, 'output_tokens': 300}, stored.usage_basis, False))
        self.assertEqual(astra['run_id'], str(stored.pk))
        self.assertEqual(fable['state'], 'done')
        self.assertEqual(harness['clarification'], {'open': 0})
        self.assertEqual(harness['final'], {'state': 'ready_for_review', 'label': 'Ready for review'})
        # harness@2 (HARNESS.md 12.6): the final assessment read both peer reviews; each row names its own, and the
        # row's first-reading run stays the one it reports (its usage is that run's, never the peer review's)
        self.assertEqual(harness['phase'], 2)
        for row in (astra, fable):
            peer = self.runs_of(encounter_id, row['name'], 'peer_review')[0]
            self.assertEqual((row['peer']['state'], row['peer']['run_id'], row['peer']['codes_added']),
                             ('done', str(peer.pk), []))
        self.assertEqual((corti['peer'], corti['references'], corti['peer_references']),
                         ({}, {'retrieved': [], 'used': []}, {'retrieved': [], 'used': []}))
        # retrieval ran and traced every decidable code: 99213 only (Astra's 99214 quotes nothing in the note, so it is
        # no proposal); this test database installs no CMS source, so no CMS reference file applied and no code was
        # checked against one: 'not_verified', never 'done' of a code no file was read for (refutation round 2, truth-3)
        validation = harness['reference_validation']
        self.assertEqual({key: validation[key] for key in ('state', 'codes_checked', 'passages', 'sources')},
                         {'state': 'not_verified', 'codes_checked': 0, 'passages': 0, 'sources': []})

    def test_a_pricing_error_shows_no_estimate_and_never_fails_the_page(self):
        broken = types.ModuleType('studio.participants.pricing')

        def estimate(model, usage):
            raise ValueError('synthetic pricing defect')
        broken.estimate = estimate
        with mock.patch.dict(sys.modules, {'studio.participants.pricing': broken}):
            encounter_id = self.create()
            drain()
            with self.assertLogs('studio.review', level='ERROR'):
                rows = self.rows(encounter_id)
        self.assertEqual((rows['astra']['estimated_cost_usd'], rows['astra']['usage']),
                         (None, {'input_tokens': 1200, 'output_tokens': 300}))

    def test_rows_while_processing(self):
        encounter_id = self.create()
        rows = self.rows(encounter_id)
        self.assertEqual({name: row['state'] for name, row in rows.items()},
                         {'corti': 'waiting', 'astra': 'waiting', 'fable': 'waiting'})
        self.assertEqual(self.detail(encounter_id)['harness']['reference_validation']['state'], 'waiting')
        for _ in range(3):
            jobs.run_job(jobs.claim_next())  # extract, analyze, predict
        rows = self.rows(encounter_id)
        self.assertEqual((rows['corti']['state'], rows['astra']['state'], rows['fable']['state']),
                         ('done', 'waiting', 'waiting'))
        self.assertIn('have not read the answer yet', rows['corti']['detail'])
        job = jobs.claim_next()
        self.assertEqual(job.kind, 'astra')
        self.assertEqual(self.rows(encounter_id)['astra']['state'], 'running')

    def test_unknown_blocked_and_failed_rows_say_so(self):
        self.adapters['astra'].outcomes = ['unknown']
        encounter_id = self.create()
        drain()
        rows = self.rows(encounter_id)
        self.assertEqual((rows['astra']['state'], rows['fable']['state']), ('unknown', 'blocked'))
        self.assertIn('Reconcile', rows['astra']['detail'])
        self.assertIn('unknown outcome', rows['fable']['detail'])
        self.assertEqual(self.detail(encounter_id)['harness']['final']['state'], 'provider_unknown')

    def test_a_failed_participant_row(self):
        self.adapters['astra'].outcome = 'failed'
        encounter_id = self.create()
        drain()
        row = self.rows(encounter_id)['astra']
        self.assertEqual((row['state'], row['detail']),
                         ('failed', 'The request failed (HTTP 529): Overloaded (synthetic).'))
        self.assertEqual(self.detail(encounter_id)['harness']['final']['state'], 'ready_for_review')
        # a failed first assessment takes no part in peer review, and its row says so (HARNESS.md 11.1, 12.6)
        self.assertEqual((row['peer']['state'], row['peer']['run_id']), ('not_sent', None))
        self.assertTrue(row['peer']['detail'].startswith('Peer review: '), row['peer']['detail'])
        self.assertIn(jobs.PEER_FIRST_NOT_READ.rstrip('.'), row['peer']['detail'])

    def test_a_participant_code_the_engine_cannot_list_is_never_served(self):
        # refutation r1 IND-1: the assessment's record copies every code the reading kept, a descriptor-like one
        # included; the row lists only the codes the engine lists (engine._listable) and says how many it does not
        self.adapters['astra'].codes = [(DESCRIPTOR_LIKE, TIME_QUOTE), ('99213', TIME_QUOTE)]
        encounter_id = self.create()
        drain()
        stored = self.encounter(encounter_id).current_assessment.participants
        self.assertIn(DESCRIPTOR_LIKE, [item['code'] for record in stored if record['name'] == 'astra'
                                        for item in record['codes']])
        response = self.client.get(f'/ops/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        data['assessment'].pop('summary')  # this suite's engine wrapper notes there what it was given
        self.assertNotIn(DESCRIPTOR_LIKE, json.dumps(data))
        astra = {row['name']: row for row in data['harness']['participants']}['astra']
        self.assertEqual((astra['state'], astra['codes']), ('done', ['99213']))
        self.assertTrue(astra['detail'].endswith(UNLISTED_ONE), astra['detail'])
        # a row whose codes are all listable says nothing more
        self.assertNotIn('cannot be listed', self.rows(encounter_id)['fable']['detail'])

    def test_a_refused_reading_row(self):
        self.adapters['fable'].returned_model = 'claude-other-model'
        encounter_id = self.create()
        drain()
        row = self.rows(encounter_id)['fable']
        self.assertEqual((row['state'], row['returned_model'], row['codes']), ('refused', 'claude-other-model', []))
        self.assertTrue(row['detail'].startswith('Answered; the reading was not used: '), row['detail'])

    def test_a_stopped_chain_says_stopped(self):
        encounter_id = self.create()
        for _ in range(3):
            jobs.run_job(jobs.claim_next())  # extract, analyze, predict: the Astra stage waits in the queue
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        rows = self.rows(encounter_id)
        self.assertEqual((rows['corti']['state'], rows['astra']['state'], rows['fable']['state']),
                         ('done', 'stopped', 'stopped'))

    def test_a_participant_disabled_since_reads_not_configured_never_an_unread_answer(self):
        encounter_id = self.create()
        drain()
        with override_settings(FABLE_MODE='disabled'):
            response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
            self.assertEqual(response.status_code, 201, response.content)
            drain()
            rows = self.rows(encounter_id)
        self.assertEqual((rows['astra']['state'], rows['fable']['state'], rows['fable']['detail'],
                          rows['fable']['run_id']), ('done', 'not_configured', 'Not configured on this installation.',
                                                     None))

    def test_not_configured_rows_with_corti_only(self):
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'):
            encounter_id = self.create()
            drain()
            rows = self.rows(encounter_id)
        self.assertEqual({name: row['state'] for name, row in rows.items()},
                         {'corti': 'done', 'astra': 'not_configured', 'fable': 'not_configured'})


@override_settings(**LIVE, **BOTH)
class FrontendContractTests(OperatorReads, HarnessCase):
    """The operator console's contract constants (tests.test_frontend) are the operator serializer's own keys as /ops/
    serves them (refutation r1 FG-5; CORE-UX-DESIGN.md 5), and the customer contract (tests.test_customer_surface, the
    contract of CORE-UX-DESIGN.md 7) is exactly what /api/ serves the same member - none of the operator's keys."""

    def test_the_contract_constants_are_the_keys_the_api_serves(self):
        from tests import test_frontend as contract
        from tests.test_customer_surface import OPERATOR_ONLY, assert_contract

        owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        client = operator_access.client(owner)
        with mock.patch('studio.jobs.reference_passages', fake_passages([])):
            encounter_id = self.create()
            drain()
        customer = client.get(f'/api/encounters/{encounter_id}').json()
        assert_contract(self, customer)
        self.assertFalse(OPERATOR_ONLY & set(customer))
        self.assertEqual(client.get(f'/api/encounters/{encounter_id}/trace').status_code, 404)
        detail = client.get(f'/ops/api/encounters/{encounter_id}').json()
        trace = client.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        runs = [run for participant in trace['participants'] for run in participant['runs']]
        readings = [run['reading'] for run in runs if run['reading'] is not None]
        retrieval = [item for proposal in detail['assessment']['proposals'] for item in proposal['retrieval']]
        self.assertTrue(runs and readings and retrieval and trace['reconciliation'] and detail['provider_runs'])
        shapes = ([('harness', detail['harness'], contract.HARNESS_KEYS),
                   ('permissions', detail['permissions'], contract.PERMISSION_KEYS),
                   ('reference validation', detail['harness']['reference_validation'],
                    contract.REFERENCE_VALIDATION_KEYS), ('trace', trace, contract.TRACE_KEYS)]
                  + [('participant row', row, contract.PARTICIPANT_KEYS) for row in detail['harness']['participants']]
                  + [('provider run', run, contract.PROVIDER_RUN_KEYS) for run in detail['provider_runs']]
                  + [('retrieval item', item, contract.RETRIEVAL_ITEM_KEYS) for item in retrieval]
                  + [('trace run', run, contract.TRACE_RUN_KEYS) for run in runs]
                  + [('reading', reading, contract.READING_KEYS) for reading in readings]
                  + [('reconciliation row', row, contract.RECONCILIATION_ROW_KEYS) for row in trace['reconciliation']])
        for label, served, keys in shapes:
            with self.subTest(label):
                self.assertEqual(set(served), keys)
        # the Activity tab names the model a participant's run asked for and the one that answered (refutation r1 FG-5:
        # the provider runs never carried them, so its "Model requested" line never rendered from the real API)
        astra = next(run for run in detail['provider_runs'] if run['provider'] == 'astra')
        self.assertEqual((astra['requested_model'], astra['returned_model']), ('gpt-6-astra', 'gpt-6-astra'))


class FailedRetrievalTests(OperatorReads, HarnessCase):
    """A retrieval that raises (refutation round 1, parity-1) through the real pipeline: the assessment stands as made,
    and the harness block says reference validation failed with the note the assessment recorded - never 'not_run' or
    'done' - with Corti only (I1) and with both participants after peer review; the owner's trace serves the one failed
    entry as recorded, and no code's retrieval reads it as its own."""

    def failing(self):
        owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        with mock.patch('studio.jobs.reference_passages.retrieve', side_effect=RuntimeError('synthetic defect')), \
                self.assertLogs('studio.jobs', level='ERROR'):
            encounter_id = self.create()
            drain()
        client = Client()
        client.force_login(owner)
        detail = client.get(f'/ops/api/encounters/{encounter_id}').json()
        trace = client.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        return self.encounter(encounter_id), detail, trace

    def assertShownFailed(self, encounter, detail, trace):
        assessment = encounter.current_assessment
        self.assertEqual(assessment.retrieval, [jobs.retrieval_failure(date(2026, 10, 20), 'RuntimeError')])
        (note,) = assessment.retrieval[0]['notes']
        self.assertEqual(detail['harness']['reference_validation'],
                         {'state': 'failed', 'detail': note, 'codes_checked': 0, 'passages': 0, 'sources': [],
                          'not_connected': ReferenceValidationTests.NOT_CONNECTED})
        self.assertNotIn('synthetic defect', json.dumps(detail))  # the exception's text is logged, never served
        self.assertEqual(trace['retrieval'], assessment.retrieval)
        self.assertTrue(detail['assessment']['proposals'])
        for proposal in detail['assessment']['proposals']:
            self.assertEqual(proposal['retrieval'], [], proposal['code'])

    @override_settings(**LIVE)
    def test_corti_only(self):
        encounter, detail, trace = self.failing()
        self.assertShownFailed(encounter, detail, trace)
        self.assertEqual((detail['harness']['phase'], encounter.state), (0, 'ready_for_review'))

    @override_settings(**LIVE, **BOTH)
    def test_both_participants_after_peer_review(self):
        encounter, detail, trace = self.failing()
        self.assertShownFailed(encounter, detail, trace)
        self.assertEqual((detail['harness']['phase'], encounter.state), (2, 'ready_for_review'))


@override_settings(**LIVE, **BOTH)
class ActivityTests(OperatorReads, HarnessCase):
    def test_participant_attempts_are_named_and_corti_s_read_as_before(self):
        self.adapters['astra'].outcome = 'failed'
        encounter_id = self.create()
        drain()
        summaries = [row['summary'] for row in self.client.get(f'/ops/api/encounters/{encounter_id}').json()['activity']]
        self.assertIn('Astra request started', summaries)
        self.assertIn('Astra request failed (HTTP 529)', summaries)
        self.assertIn('Fable response recorded', summaries)
        self.assertIn('Provider request started', summaries)
        self.assertIn('Provider response recorded', summaries)


@override_settings(**LIVE, **BOTH)
class TraceTests(OperatorReads, HarnessCase):
    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        self.viewer = f.member(self.ws, f.user('viewer'), role=models.Membership.VIEWER)

    def get(self, user, encounter_id):
        client = Client()
        if user is not None:
            client.force_login(user)
        return client.get(f'/ops/api/encounters/{encounter_id}/trace')

    def test_the_trace_is_an_operator_s_never_a_workspace_role_s(self):
        # moved by the customer interface change (CORE-UX-DESIGN.md 5; owner directive 2026-11-03, section 2: a tenant
        # owner must not automatically gain platform-operator access): this pinned the owner-only trace at /api/ (owner
        # 200, reviewer and viewer 403); the trace is now an operator's at /ops/, and every role without a grant gets
        # the answer an unknown URL gets (tests.test_operator.MatrixTests holds every role and URL to it)
        encounter_id = self.create()
        drain()
        self.assertEqual(self.get(self.owner, encounter_id).status_code, 200)  # an owner who is an operator
        outsider = f.member(f.workspace('Other synthetic workspace'), f.user('outsider'),
                            role=models.Membership.OWNER)
        for user in (self.owner, self.reviewer, self.viewer, outsider):
            client = Client()
            client.force_login(user)  # granted by OperatorReads, then the grant ends: a member and nothing more
            operator.revoke(user, 'Synthetic test: the member holds no operator grant.', 'tests')
            self.assertEqual(client.get(f'/ops/api/encounters/{encounter_id}/trace').status_code, 404, user.username)
            self.assertEqual(client.get(f'/api/encounters/{encounter_id}/trace').status_code, 404, user.username)
        self.assertEqual(Client().get(f'/ops/api/encounters/{encounter_id}/trace').status_code, 404)
        client = Client()
        client.force_login(self.owner)  # granted again
        self.assertEqual(client.post(f'/ops/api/encounters/{encounter_id}/trace').status_code, 405)

    def test_the_trace_shows_each_run_its_reading_the_retrieval_and_the_reconciliation(self):
        recorded = []
        with mock.patch('studio.jobs.reference_passages', fake_passages(recorded)):  # the installed pricing module
            encounter_id = self.create()
            drain()
            trace = self.get(self.owner, encounter_id).json()
        encounter = self.encounter(encounter_id)
        self.assertEqual(trace['encounter'], {'id': encounter_id, 'title': encounter.title})
        self.assertEqual(trace['revision']['number'], 1)
        self.assertEqual([p['name'] for p in trace['participants']], ['corti', 'astra', 'fable'])
        corti, astra, fable = trace['participants']
        self.assertEqual([run['purpose'] for run in corti['runs']], ['primary'])
        self.assertIsNone(corti['runs'][0]['reading'])
        run = astra['runs'][0]
        stored = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((run['id'], run['endpoint'], run['requested_model'], run['returned_model'], run['request_id'],
                          run['response_id'], run['response_sha256'], run['response_bytes'], run['mode']),
                         (str(stored.pk), 'https://api.openai.com/v1/responses', 'gpt-6-astra', 'gpt-6-astra',
                          stored.provider_request_id, stored.response_id, stored.response_sha256,
                          len(bytes(stored.response_bytes)), 'replay'))
        self.assertEqual(run['estimated_cost_usd'], '0.0270')
        self.assertEqual((run['run_identity'], run['sent'], run['requested_by']),
                         (str(stored.run_identity), True, self.reviewer.label()))
        self.assertEqual(self.adapters['astra'].sent[0]['client_request_id'], run['run_identity'])
        reading = run['reading']
        self.assertEqual(reading['unverified_quotes'], 1)
        self.assertEqual([code['code'] for code in reading['codes']], ['99213', '99214'])
        unverified = reading['codes'][1]['evidence'][0]
        self.assertEqual((unverified['spans'], unverified['reason']), ([], 'not found in the document'))
        located = reading['codes'][0]['evidence'][0]['spans'][0]
        self.assertEqual(encounter.current_revision.text[located['start']:located['end']], TIME_QUOTE)
        # harness@2 (HARNESS.md 12.6): each participant's first reading, then its peer review, with its exchanges
        self.assertEqual([(run['purpose'], run['state']) for run in fable['runs']],
                         [('independent', 'succeeded'), ('peer_review', 'succeeded')])
        self.assertEqual([len(run['exchanges']) for run in astra['runs']], [1, 1])
        peer_run = astra['runs'][1]
        self.assertEqual((peer_run['reading'], peer_run['review']['refused'], peer_run['mode']),
                         (None, False, 'replay'))
        self.assertEqual(self.adapters['astra'].peer_sent[0]['client_request_id'], peer_run['run_identity'])
        self.assertEqual([(a['phase'], a['final'], a['current']) for a in trace['assessments']],
                         [(1, False, False), (2, True, True)])
        self.assertEqual([entry['code'] for entry in trace['retrieval']], ['99213'])
        # moved by refutation round 5 (R5-ACCOUNT, the session's D12): a row also serves listed_by, the participants that
        # only listed a participant's alternative's code (none for a proposal); and by refutation round 6 (R6-MEANING,
        # negation-4, ownership-7): a first reading's 'proposed' detail is the engine's own wording, "quoting the
        # document verbatim" - "with evidence located in the document" called a denial, or another procedure's
        # sentence, evidence for the code
        self.assertEqual(trace['reconciliation'], [{
            'code': '99213', 'family': trace['reconciliation'][0]['family'], 'bucket': 'selected', 'status': 'ready',
            'proposed_by': ['corti'], 'listed_by': [], 'positions': {
                'astra': {'position': 'proposed', 'quote': TIME_QUOTE,
                          'detail': 'Astra proposed this code, quoting the document verbatim.'},
                'fable': {'position': 'proposed', 'quote': TIME_QUOTE,
                          'detail': 'Fable proposed this code, quoting the document verbatim.'}},
            'reference_check': trace['reconciliation'][0]['reference_check'], 'approved': False}])
