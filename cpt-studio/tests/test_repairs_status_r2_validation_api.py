"""Regressions for refutation round 2 over validation, through review and the API.

review:0's gate lives in review.py (approve withheld from an E/M while a reinstated same-day procedure stands, and a
readiness blocker when an approved E/M coexists with one). The end-to-end classes run the real pipeline (extraction,
routing, validation, review, reports) through the JSON API with an in-process fake provider: no network. Synthetic
data only.
"""
import hashlib
import json
from unittest import mock

from django.test import TestCase, override_settings

from studio import review
from studio.gi.detect import route
from studio.types import RawExchange
from studio.validation import checks
from tests.support import pipeline_factories as pf
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE, ApiHarness, ScriptedProvider

EM_GATE, MARKER = 'em.same_day_if_reinstated', 'review.same_day_em'


# --- review:0, the review layer on its own ----------------------------------------------------------------------

def gated_result():
    em_gate = pf.check(EM_GATE, 'warn', 'Separately identifiable E/M if a procedure is reinstated')
    marker = pf.check(MARKER, 'warn', 'Same-day E/M after reinstatement')
    reinstatement = pf.check('review.reinstatement', 'pass', 'Approval after reinstatement')
    return pf.result(
        pf.proposal('sel:0', '99213', [pf.DATE_PASSAGE], checks=pf.standard_checks() + (em_gate,)),
        pf.proposal('exc:0', '46221', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                    checks=pf.standard_checks() + (reinstatement, marker)),
        # An excluded code that validation did not mark as a same-day procedure gates nothing.
        pf.proposal('exc:1', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True))


BLOCKER = '99213 needs a separately identifiable E/M: 46221 was reinstated as a same-day procedure'


class Review0GateTests(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.assessment = pf.assess(self.s.encounter, gated_result())

    def actions(self, key):
        return review.allowed_actions(self.s.proposal(key), self.assessment, self.s.membership(self.s.reviewer))

    def ready(self):
        return review.readiness(self.s.encounter)

    def test_a_reinstated_procedure_withholds_approve_until_it_is_rejected_or_revoked(self):
        self.assertEqual(self.actions('sel:0'), ['approve', 'reject'])
        self.s.decide('exc:0', 'reinstate', note='Banding was done today.')
        self.assertEqual(self.actions('sel:0'), ['reject'])
        self.assertIn(BLOCKER, self.ready()['blockers'])
        self.s.decide('exc:0', 'approve')
        self.assertEqual(self.actions('sel:0'), ['reject'])
        with self.assertRaisesRegex(Exception, 'not available'):
            self.s.decide('sel:0', 'approve')
        self.s.decide('exc:0', 'revoke')
        self.assertEqual(self.actions('sel:0'), ['approve', 'reject'])
        self.s.decide('exc:0', 'reinstate')
        self.s.decide('exc:0', 'reject')
        self.assertEqual(self.actions('sel:0'), ['approve', 'reject'])
        self.s.decide('sel:0', 'approve')
        self.assertTrue(self.ready()['reviewed'], self.ready())

    def test_approving_the_e_m_first_blocks_the_reviewed_report(self):
        self.s.decide('sel:0', 'approve')
        self.assertTrue(self.ready()['reviewed'])
        self.s.decide('exc:0', 'reinstate')
        self.s.decide('exc:0', 'approve')
        readiness = self.ready()
        self.assertFalse(readiness['reviewed'])
        self.assertEqual(readiness['blockers'], [BLOCKER])
        self.assertEqual(self.s.encounter.state, 'ready_for_review')
        self.s.decide('sel:0', 'revoke')
        self.s.decide('sel:0', 'reject')
        self.assertTrue(self.ready()['reviewed'])

    def test_an_unmarked_reinstatement_gates_nothing(self):
        self.s.decide('exc:1', 'reinstate')
        self.assertEqual(self.actions('sel:0'), ['approve', 'reject'])
        self.assertNotIn(BLOCKER, self.ready()['blockers'])

    def test_a_reinstated_e_m_is_gated_too(self):
        em_gate = pf.check(EM_GATE, 'warn')
        marker = pf.check(MARKER, 'warn')
        reinstatement = pf.check('review.reinstatement', 'pass')
        result = pf.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
            pf.proposal('exc:0', '99213', [pf.DATE_PASSAGE], bucket='excluded', reinstatable=True,
                        checks=pf.standard_checks() + (reinstatement, em_gate)),
            pf.proposal('exc:1', '46221', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                        checks=pf.standard_checks() + (reinstatement, marker)))
        self.assessment = pf.assess(self.s.encounter, result, ctx=pf.context(self.s.encounter, self.s.revision))
        self.s.decide('exc:0', 'reinstate')
        self.assertEqual(self.actions('exc:0'), ['approve', 'reject', 'revoke'])
        self.s.decide('exc:1', 'reinstate')
        self.assertEqual(self.actions('exc:0'), ['reject', 'revoke'])
        self.s.decide('exc:1', 'reject')
        self.assertEqual(self.actions('exc:0'), ['approve', 'reject', 'revoke'])


# --- end to end through the API --------------------------------------------------------------------------------

def office_note(plan_lines, *, procedure_lines=(), time_line='Total time on the date of the encounter was 24 minutes.'):
    procedure = ('\nProcedure\n' + '\n'.join(procedure_lines) + '\n') if procedure_lines else ''
    return ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\n'
            'Date of service: 2026-10-20\nPlace of service: Office, in-person outpatient visit\n'
            'Patient status: Established patient, last seen 2026-03-02.\n\nChief complaint\nRectal bleeding.\n'
            f'{procedure}\nAssessment and plan\n' + '\n'.join(plan_lines) + '\n\n'
            'Medical decision making\nLow: one stable chronic illness; prescription drug management.\n\n'
            f'Time\n{time_line}\n')


TIME = 'Total time on the date of the encounter was 24 minutes.'
SCHEDULED = 'Rubber band ligation of an internal hemorrhoid is scheduled for 2026-11-03.'
BAND_NOTE = office_note(['Grade II internal hemorrhoids.', SCHEDULED])
ACK = 'Reviewed the source evidence (synthetic test).'


class MultiEvidenceProvider(ScriptedProvider):
    """Selections as (code, quote, quote, ...): one Corti code with several evidences, as Corti's list allows."""

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        text = request.contexts[0]
        codes = [{'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING', 'alternatives': [],
                  'evidences': [{'contextIndex': 0, 'start': text.index(q), 'end': text.index(q) + len(q), 'text': q}
                                for q in quotes]}
                 for code, *quotes in self.selections]
        data = json.dumps({'codes': codes, 'candidates': [], 'usageInfo': {'creditsConsumed': 0.02}}).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=12.5,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


class ApiCase(ApiHarness):
    def run_note(self, text, *selections):
        self.provider.selections = list(selections)
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def detail(self, encounter_id):
        response = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def proposal(self, encounter_id, code):
        (found,) = [p for p in self.detail(encounter_id)['assessment']['proposals'] if p['code'] == code]
        return found

    def decide(self, encounter_id, code, action, **extra):
        data = {'proposal_id': self.proposal(encounter_id, code)['id'], 'action': action, 'note': 'Synthetic test.',
                **({'acknowledgement': ACK} if action == 'approve' else {}), **extra}
        return self.post(f'/api/encounters/{encounter_id}/decisions', data)

    def report(self, encounter_id, kind):
        return self.post(f'/api/encounters/{encounter_id}/reports', {'kind': kind, 'fmt': 'txt'})

    def report_text(self, encounter_id, kind='draft'):
        response = self.report(encounter_id, kind)
        self.assertEqual(response.status_code, 201, response.content)
        download = self.client.get(f'/api/reports/{response.json()["id"]}/download')
        self.assertEqual(download.status_code, 200)
        return b''.join(download.streaming_content if download.streaming else [download.content]).decode('utf-8')


@override_settings(**LIVE)
class Review0ReinstatedProcedureApiTests(ApiCase, TestCase):
    """review:0 — a reinstated same-day procedure gates the selected E/M, whichever is decided first."""

    def test_a_reinstate_then_approve_both(self):
        encounter_id = self.run_note(BAND_NOTE, ('99213', TIME), ('46221', SCHEDULED))
        visit, band = self.proposal(encounter_id, '99213'), self.proposal(encounter_id, '46221')
        self.assertEqual((visit['status'], band['bucket']), ('ready', 'excluded'))
        self.assertEqual(visit['allowed_actions'], ['approve', 'reject'])
        self.assertIn(EM_GATE, [c['id'] for c in visit['checks']])
        self.assertIn(MARKER, [c['id'] for c in band['checks']])
        self.assertEqual(self.decide(encounter_id, '46221', 'reinstate').status_code, 201)
        self.assertEqual(self.proposal(encounter_id, '99213')['allowed_actions'], ['reject'])
        self.assertEqual(self.decide(encounter_id, '46221', 'approve').status_code, 201)
        self.assertEqual(self.decide(encounter_id, '99213', 'approve').status_code, 409)
        blocked = self.report(encounter_id, 'reviewed')
        self.assertEqual(blocked.status_code, 409)
        self.assertIn('99213 needs a separately identifiable E/M: 46221 was reinstated as a same-day procedure',
                      blocked.json()['details']['blockers'])

    def test_b_approving_the_e_m_first_keeps_it_out_of_the_reviewed_report(self):
        encounter_id = self.run_note(BAND_NOTE, ('99213', TIME), ('46221', SCHEDULED))
        self.assertEqual(self.decide(encounter_id, '99213', 'approve').status_code, 201)
        self.assertEqual(self.decide(encounter_id, '46221', 'reinstate').status_code, 201)
        self.assertEqual(self.decide(encounter_id, '46221', 'approve').status_code, 201)
        detail = self.detail(encounter_id)
        self.assertFalse(detail['readiness']['reviewed'])
        self.assertEqual(self.report(encounter_id, 'reviewed').status_code, 409)
        # Revoking the procedure's approval returns it to the exclusion (nothing earlier is resurrected), which
        # releases the E/M.
        self.assertEqual(self.decide(encounter_id, '46221', 'revoke').status_code, 201)
        self.assertTrue(self.detail(encounter_id)['readiness']['reviewed'])
        self.assertEqual(self.report(encounter_id, 'reviewed').status_code, 201)

    def test_f_a_correcting_reinstatement_of_a_procedure_done_as_scheduled(self):
        done = 'Rubber band ligation of an internal hemorrhoid was performed today as scheduled.'
        encounter_id = self.run_note(office_note(['Grade II internal hemorrhoids.', done]), ('99213', TIME),
                                     ('46221', done))
        band = self.proposal(encounter_id, '46221')
        if band['bucket'] == 'excluded':  # read as planned today; integrated routing may read it performed
            self.assertEqual(self.decide(encounter_id, '46221', 'reinstate').status_code, 201)
            self.assertEqual(self.decide(encounter_id, '99213', 'approve').status_code, 409)
        else:
            self.assertEqual(self.proposal(encounter_id, '99213')['status'], 'needs_clarification')

    def test_d_the_reverse_pair_stays_refused(self):
        note = office_note(['Return office visit is scheduled for 2026-12-01.'],
                           procedure_lines=['Rubber band ligation of an internal hemorrhoid was performed today '
                                            'without complication.'])
        encounter_id = self.run_note(note, ('99213', 'Return office visit is scheduled for 2026-12-01.'),
                                     ('46221', 'Rubber band ligation of an internal hemorrhoid was performed today '
                                               'without complication.'))
        visit = self.proposal(encounter_id, '99213')
        self.assertEqual(visit['bucket'], 'excluded')
        gate = next(c for c in visit['checks'] if c['id'] == 'review.reinstatement')
        self.assertEqual(gate['status'], 'warn')
        self.assertEqual(self.decide(encounter_id, '99213', 'reinstate').status_code, 201)
        self.assertEqual(self.decide(encounter_id, '99213', 'approve').status_code, 409)


@override_settings(**LIVE)
class Review1PlanDiscussionApiTests(ApiCase, TestCase):
    """review:1 — an office visit whose plan only discusses a procedure can be approved and reported."""

    def test_discussed_procedure_does_not_block_approval(self):
        for plan in ('Discussed colonoscopy; the patient will think about it.', 'Colonoscopy? Will decide after labs.'):
            with self.subTest(plan=plan):
                encounter_id = self.run_note(office_note(['Chronic constipation, improved.', plan]), ('99213', TIME))
                visit = self.proposal(encounter_id, '99213')
                self.assertEqual((visit['status'], visit['allowed_actions']), ('ready', ['approve', 'reject']))
                self.assertEqual(self.decide(encounter_id, '99213', 'approve').status_code, 201)
                self.assertEqual(self.report(encounter_id, 'reviewed').status_code, 201)


class MultiEvidenceApiCase(ApiCase):
    def setUp(self):
        super().setUp()
        self.provider = MultiEvidenceProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)


@override_settings(**LIVE)
class Status4ApiTests(MultiEvidenceApiCase, TestCase):
    """status:4 — EUS named only as requested: the EGD passage does not make 43259 approvable."""

    def test_status4_an_uncertain_family_is_not_approvable(self):
        note = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
                'Indication: Dysphagia. Pancreatic cyst on CT; EUS requested by the referring physician.\n'
                'Procedure: EGD\nFindings: The endoscope was advanced to the second part of the duodenum. '
                'Normal EGD.\n')
        encounter_id = self.run_note(note, ('43259', 'The endoscope was advanced to the second part of the duodenum.'))
        eus = self.proposal(encounter_id, '43259')
        self.assertEqual((eus['status'], eus['allowed_actions']), ('needs_clarification', ['reject']))
        self.assertEqual(self.decide(encounter_id, '43259', 'approve').status_code, 409)


@override_settings(**LIVE)
class Status13ApiTests(MultiEvidenceApiCase, TestCase):
    """status:13 — one Corti code with a performed and a hedged evidence passage is not approvable."""

    def test_status13_a_hedged_second_passage_is_not_approvable(self):
        note = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\nProcedure: Colonoscopy\n'
                'Findings: The colonoscope was advanced to the cecum. A 5 mm cecal lesion was seen. It is unclear '
                'whether biopsies were taken.\n')
        encounter_id = self.run_note(note, ('45380', 'The colonoscope was advanced to the cecum.',
                                            'It is unclear whether biopsies were taken.'))
        biopsy = self.proposal(encounter_id, '45380')
        self.assertEqual((biopsy['status'], biopsy['allowed_actions']), ('needs_clarification', ['reject']))
        status = next(c for c in biopsy['checks'] if c['id'] == 'service.status')
        self.assertIn('It is unclear whether biopsies were taken.', status['detail'])
        self.assertEqual(self.decide(encounter_id, '45380', 'approve').status_code, 409)


@override_settings(**LIVE)
class Status19ApiTests(ApiCase, TestCase):
    """status:19 (b) — the report never certifies coverage routing does not have."""

    def test_the_report_carries_no_false_coverage_pass(self):
        note = office_note(['Grade II internal hemorrhoids.'],
                           procedure_lines=['Rubber band ligation of an internal hemorrhoid was performed today '
                                            'without complication.'])
        encounter_id = self.run_note(note, ('99213', TIME))
        text = self.report_text(encounter_id)
        self.assertNotIn('Every performed service has a selected proposal.', text)
        self.assertNotIn('No performed service falls outside the GI profiles.', text)
        # Asserted, not branched on (round 3 evidence:0): routing detects the banding, so the visit is held; the
        # coverage lines are pinned on an undetected input below.
        self.assertIsNotNone(route(note).finding('gi.other'))
        self.assertEqual(self.proposal(encounter_id, '99213')['status'], 'needs_clarification')
        self.assertIn('[WARN] em.same_day_procedure', text)

    def test_a_plain_office_visit_reports_coverage_as_not_verified(self):
        """Round 3 evidence:0 — the draft and the reviewed report of an office visit with no procedure line carry the
        not-verified coverage lines and neither old PASS sentence."""
        note = office_note(['Gastroesophageal reflux disease, controlled.', 'Return in 3 months.'])
        self.assertEqual([f.family for f in route(note).findings], ['gi.office_em'])
        encounter_id = self.run_note(note, ('99213', TIME))
        self.assertEqual(self.decide(encounter_id, '99213', 'approve').status_code, 201)
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind=kind):
                text = self.report_text(encounter_id, kind)
                self.assertIn('[NOT_VERIFIED] em.same_day_coverage', text)
                self.assertIn('[NOT_VERIFIED] services.unsupported — Services outside the GI profiles: '
                              + checks.UNSUPPORTED_NONE, text)
                self.assertIn('[PASS] services.unproposed — Performed services without a proposal: '
                              + checks.UNPROPOSED_PASS, text)
                self.assertNotIn('Every performed service has a selected proposal.', text)
                self.assertNotIn('No performed service falls outside the GI profiles.', text)
