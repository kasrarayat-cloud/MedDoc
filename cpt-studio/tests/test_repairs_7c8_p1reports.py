"""Continuation round 7c8, refutation phase 1, cluster P1REPORTS (report truth, class 3): each surface says only what
the stored rows support, worded from the rows. Synthetic data only; the provider is an in-process fake (no network).

Each class reproduces a finding of the refutation pass over b611b557a (refute-p1, lens 'reports', verified) with its
smallest input and asserts the wording that is true of the persisted state, beside a control that must not change.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import Client, TestCase, override_settings

from studio import models, reports
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import drain
from tests.test_services_second_review import TwoPassProvider, ask

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
APP = Path(settings.BASE_DIR) / 'studio' / 'static' / 'studio' / 'app.js'
SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'

COLONOSCOPY = SYNTHETIC + """Colonoscopy report (fictional)
Date of service: 2026-10-16
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
A separate 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps; it was not removed.
"""
COLONOSCOPY_THREE = COLONOSCOPY + 'A 20 mm sessile lesion in the ascending colon was dilated with a balloon to 15 mm.\n'
SNARE = ('45385', 'was removed with a cold snare')
BIOPSY = ('45380', 'was sampled with cold biopsy forceps')
DILATION = ('45386', 'was dilated with a balloon to 15 mm')

NODE = r"""
const app = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const doc = JSON.parse(input);
  const layout = app.documentLayout(doc);
  process.stdout.write(JSON.stringify({
    codes: app.reviewView(doc, layout, 'codes', false),
    checks: app.reviewView(doc, layout, 'checks', false),
  }));
});
"""


def page(detail):
    """The review page as app.js renders it (node runs the shipped file), for the codes and checks tabs."""
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the screen checks need it')
    done = subprocess.run([node, '-e', NODE, str(APP)], input=json.dumps(detail), capture_output=True, text=True,
                          timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-3000:])
    return json.loads(done.stdout)


def section(text, title):
    """The body of a report section: the lines after its title, up to the blank line that ends it."""
    lines = text.split('\n')
    start = next(i for i, line in enumerate(lines) if line.startswith(title))
    body = []
    for line in lines[start + 1:]:
        if not line:
            break
        body.append(line)
    return '\n'.join(body)


@override_settings(**LIVE)
class Harness(TestCase):
    def setUp(self):
        self.fresh()

    def fresh(self, name='Synthetic workspace'):
        """A new workspace and reviewer: an identical request answered in the same workspace is reused, never resent,
        so a variant run in the workspace of another would read the other's stored response."""
        self.ws = f.workspace(name)
        self.reviewer = f.member(self.ws, f.user())
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)

    def use(self, provider):
        patcher = mock.patch('studio.jobs.get_provider', return_value=provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.provider = provider
        return provider

    def create(self, text):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def detail(self, encounter_id):
        reply = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(reply.status_code, 200, reply.content)
        return reply.json()

    def decide(self, encounter_id, code, action, bucket='selected'):
        proposals = self.detail(encounter_id)['assessment']['proposals']
        (proposal,) = [p for p in proposals if p['code'] == code and p['bucket'] == bucket]
        body = {'proposal_id': proposal['id'], 'action': action}
        if action == 'approve':
            body['acknowledgement'] = self.client.get('/api/session').json()['acknowledgement']
        reply = self.post(f'/api/encounters/{encounter_id}/decisions', body)
        self.assertEqual(reply.status_code, 201, reply.content)

    def txt(self, encounter_id, kind='draft'):
        return reports.render_txt(reports.snapshot(models.Encounter.objects.get(pk=encounter_id), kind)).decode()

    def csv_text(self, encounter_id, kind='draft'):
        return reports.render_csv(reports.snapshot(models.Encounter.objects.get(pk=encounter_id), kind)).decode()

    def assessment(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id).current_assessment

    def encounter_check(self, encounter_id, check_id):
        (found,) = [c for c in self.assessment(encounter_id).encounter_checks if c['id'] == check_id]
        return found


# --- reports-0 and reports-2: the second review's check and what it adds ---------------------------------------------

class PrimaryInexact(TwoPassProvider):
    """The primary response also selects 45380, with a passage that is not in the document (``passage``) or with no
    passage at all (``passage`` None): it has no exact evidence. The second review selects ``later`` exactly."""

    def __init__(self, first, later, passage):
        super().__init__(first, later)
        self.passage = passage

    def send(self, request, *, deadline_s):
        if self.requests:
            return super().send(request, deadline_s=deadline_s)
        self.requests.append(request)
        context = request.contexts[0]
        start = context.index(SNARE[1])
        codes = [{'system': 'cpt', 'code': '45385', 'display': 'UNVERIFIED PROVIDER WORDING',
                  'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(SNARE[1]), 'text': SNARE[1]}],
                  'alternatives': []},
                 {'system': 'cpt', 'code': '45380', 'display': 'UNVERIFIED PROVIDER WORDING', 'alternatives': []}]
        if self.passage is not None:
            codes[1]['evidences'] = [{'contextIndex': 0, 'start': 5, 'end': 5 + len(self.passage),
                                      'text': self.passage}]
        data = json.dumps({'codes': codes, 'candidates': [], 'usageInfo': {'creditsConsumed': 0.02}}).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


class SecondReviewSelectionIsNeverDroppedTests(Harness):
    """reports-0: the primary response selected 45380 without an exact passage, so 45380 was excluded early ("No exact
    source evidence", not reinstatable) and the biopsy stayed unresolved. The second review a reviewer asked for
    selected 45380 with an exact passage - and the engine skipped it because the primary had "selected" that code: it
    was neither a proposal nor an alternative, and the stored check said the review "selected no code that accounts
    for them". A primary selection excluded for scope or evidence is no proposal a reviewer can decide, so it never
    hides the second review's selection; and a code a decidable primary proposal already carries is listed with why,
    never dropped unseen (ARCHITECTURE 5.11: every code the second review selects is a proposal or an alternative)."""

    def asked(self, provider):
        self.use(provider)
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        return encounter_id

    def test_a_second_review_code_the_primary_had_without_exact_evidence_is_added(self):
        for index, passage in enumerate(('biopsies taken in the colon', None)):
            with self.subTest(passage=passage):
                self.fresh(f'Synthetic workspace {index}')
                encounter_id = self.asked(PrimaryInexact([SNARE], [BIOPSY], passage))
                self.assertEqual(len(self.provider.requests), 2)  # this variant's own primary and second review
                second = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review')
                assessment = self.assessment(encounter_id)
                self.assertEqual(assessment.second_run_id, second.pk)
                rows = [(p.code, p.bucket, p.exclusion_reason, (p.support or {}).get('origin'))
                        for p in assessment.proposals.filter(code='45380').order_by('position')]
                self.assertIn(('45380', 'excluded', 'No exact source evidence', None), rows)  # the primary's, as stored
                self.assertIn(('45380', 'selected', '', 'second_review'), rows)  # the second review's, never dropped
                self.assertEqual(assessment.completeness['unresolved_items'], [])
                check = self.encounter_check(encounter_id, 'provider.second_review')
                self.assertEqual(check['status'], 'info')
                self.assertNotIn('selected no code', check['detail'])
                self.assertIn('selected 45380, which accounts for forceps biopsy', check['detail'])
                self.assertIn(check['detail'], self.txt(encounter_id))
                # the reviewer decides it like any proposal; the reviewed report follows
                self.decide(encounter_id, '45385', 'approve')
                self.decide(encounter_id, '45380', 'approve')
                reviewed = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
                self.assertEqual(reviewed.status_code, 201, reviewed.content)

    def test_a_code_a_primary_proposal_already_carries_is_listed_with_why(self):
        encounter_id = self.asked(TwoPassProvider([SNARE], [BIOPSY, SNARE]))
        assessment = self.assessment(encounter_id)
        selected = sorted(p.code for p in assessment.proposals.filter(bucket='selected'))
        self.assertEqual(selected, ['45380', '45385'])  # never added twice
        (listed,) = assessment.proposals.filter(bucket='alternative', code='45385')
        self.assertIn('not added as a proposal: a primary proposal already carries it', listed.exclusion_reason)
        detail = self.encounter_check(encounter_id, 'provider.second_review')['detail']
        self.assertIn('It also listed 45385, shown as an alternative only.', detail)

    def test_control_a_second_review_code_the_primary_never_selected_is_added_as_before(self):
        encounter_id = self.asked(TwoPassProvider([SNARE], [BIOPSY]))
        assessment = self.assessment(encounter_id)
        (added,) = assessment.proposals.filter(code='45380')
        self.assertEqual((added.bucket, added.support['origin']), ('selected', 'second_review'))
        self.assertEqual(assessment.completeness['unresolved_items'], [])
        check = self.encounter_check(encounter_id, 'provider.second_review')
        self.assertEqual(check['status'], 'info')
        self.assertFalse(assessment.proposals.filter(bucket='alternative').exists())


class SecondReviewCheckNamesWhatItAccountsForTests(Harness):
    """reports-2: two asked items (a forceps biopsy and a balloon dilation); the second review selected only 45380. The
    stored check said 45380 "account[s] for them" - both asked items - while the same assessment still lists the
    dilation as unresolved. The check names only the items the added codes account for, and the asked items that stay
    unresolved (a warning while any does)."""

    def asked(self, later):
        self.use(TwoPassProvider([SNARE], later))
        encounter_id = self.create(COLONOSCOPY_THREE)
        drain()
        offered = self.detail(encounter_id)['second_review']['items']
        self.assertEqual(len(offered), 2, offered)
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        return encounter_id

    def test_an_asked_item_left_unresolved_is_named_never_accounted_for(self):
        encounter_id = self.asked([BIOPSY])
        still = [u['label'] for u in self.assessment(encounter_id).completeness['unresolved_items']]
        self.assertEqual(len(still), 1)
        self.assertTrue(still[0].startswith('dilation (balloon)'), still)
        check = self.encounter_check(encounter_id, 'provider.second_review')
        self.assertEqual(check['status'], 'warn')
        detail = check['detail']
        self.assertNotIn('which account for them', detail)
        accounted = detail.split('which accounts for ', 1)[1].split(' and is added', 1)[0]
        self.assertTrue(accounted.startswith('forceps biopsy'), detail)
        self.assertNotIn('dilation', accounted)
        self.assertIn(f'Still unresolved: {still[0]}.', detail)
        self.assertIn(detail, self.txt(encounter_id))
        self.assertIn(detail, page(self.detail(encounter_id))['checks'].replace('&#x27;', "'"))

    def test_control_codes_for_every_asked_item_account_for_each(self):
        encounter_id = self.asked([BIOPSY, DILATION])
        self.assertEqual(self.assessment(encounter_id).completeness['unresolved_items'], [])
        check = self.encounter_check(encounter_id, 'provider.second_review')
        self.assertEqual(check['status'], 'info')
        self.assertIn('selected 45380, 45386, which account for forceps biopsy', check['detail'])
        self.assertIn('dilation (balloon)', check['detail'])
        self.assertNotIn('Still unresolved', check['detail'])
