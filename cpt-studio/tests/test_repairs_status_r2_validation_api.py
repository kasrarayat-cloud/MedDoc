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
from studio.types import RawExchange
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
                'Procedure: EGD\nFindings: The endoscope was advanced to the second part of the duodenum. Normal EGD.\n')
        encounter_id = self.run_note(note, ('43259', 'The endoscope was advanced to the second part of the duodenum.'))
        eus = self.proposal(encounter_id, '43259')
        self.assertEqual((eus['status'], eus['allowed_actions']), ('needs_clarification', ['reject']))
        self.assertEqual(self.decide(encounter_id, '43259', 'approve').status_code, 409)


