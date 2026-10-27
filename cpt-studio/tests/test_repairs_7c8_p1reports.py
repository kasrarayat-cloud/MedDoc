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
from django.test import Client, SimpleTestCase, TestCase, override_settings

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


# --- reports-1: a documented visit no proposal accounts for --------------------------------------------------------

EM_AND_COLONOSCOPY = SYNTHETIC + """Riverbend Digestive Health (fictional)
Date of service: 2026-10-20
Place of service: Office, in-person outpatient visit
Patient status: Established patient, last seen 2026-03-02.

Clinic visit
Chief complaint: change in bowel habit. History and examination were performed and documented.
A significant, separately identifiable evaluation and management service was provided today.
Medical decision making: moderate.
Total time on the date of the encounter was 32 minutes.

Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed. No polyps were found.
"""
SEPARATE_EM = 'A significant, separately identifiable evaluation and management service was provided today.\n'
SCOPE = ('45378', 'The colonoscope was advanced to the cecum and the examination was completed.')
VISIT = ('99214', 'Total time on the date of the encounter was 32 minutes.')
EVERY_SERVICE = 'Every documented service has a proposal'
COLONOSCOPY_ALONE = SYNTHETIC + """Colonoscopy report (fictional)
Date of service: 2026-10-21
Place of service: Hospital outpatient department
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
No polyps were seen.
"""


class DocumentedVisitWithoutAProposalTests(Harness):
    """reports-1: an office visit (documented as performed, with or without a significant, separately identifiable E/M)
    beside a same-day colonoscopy; the provider selected only 45378. The reconciliation does not list the visit as
    unresolved beside a same-day procedure (and makes no second review for it), so coding completeness said "Every
    documented service has a proposal with a reviewer's decision" in the reviewed TXT, the CSV and the screen banner,
    and UNRESOLVED closed with "every documented act ... has a selected proposal or is not separately reported". A
    documented service no proposal accounts for keeps coding incomplete, named, on every surface."""

    def reviewed(self, text, *selections):
        from tests.test_pipeline_api import FakeProvider
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        for code, _ in selections:
            self.decide(encounter_id, code, 'approve')
        return encounter_id

    def test_a_visit_beside_a_same_day_procedure_with_no_proposal_keeps_coding_incomplete(self):
        for index, text in enumerate((EM_AND_COLONOSCOPY, EM_AND_COLONOSCOPY.replace(SEPARATE_EM, ''))):
            with self.subTest(separate_em=index == 0):
                self.fresh(f'Synthetic workspace {index}')
                encounter_id = self.reviewed(text, SCOPE)
                assessment = self.assessment(encounter_id)
                visit = next(s for s in assessment.services['services'] if s['family'] == 'gi.office_em')
                self.assertEqual((visit['status'], visit['separate_em']), ('performed', index == 0))
                self.assertEqual(assessment.completeness['covered'][visit['id']], [])
                self.assertEqual(assessment.completeness['unresolved_items'], [])  # still never pushed as unresolved
                detail = self.detail(encounter_id)
                self.assertTrue(detail['readiness']['reviewed'])  # the reviewed report can still be produced
                coding = detail['coding']
                self.assertEqual(coding['state'], 'incomplete')
                self.assertNotIn(EVERY_SERVICE, coding['statement'])
                self.assertIn('without a supported proposal and not listed as unresolved: office / outpatient visit '
                              'beside a procedure done or possibly done the same day', coding['statement'])
                reviewed = self.txt(encounter_id, 'reviewed')
                self.assertIn('State: incomplete', section(reviewed, 'CODING COMPLETENESS'))
                self.assertNotIn(EVERY_SERVICE, reviewed)
                closing = section(reviewed, 'UNRESOLVED')
                self.assertIn('except office / outpatient visit beside a procedure done or possibly done the same '
                              'day, which no proposal accounts for', closing)
                self.assertNotIn('[', closing)  # never read as an unresolved item by the download verifier
                (row,) = [line for line in self.csv_text(encounter_id, 'reviewed').split('\r\n')
                          if '"coding_completeness"' in line]
                self.assertIn('"incomplete"', row)
                self.assertNotIn(EVERY_SERVICE, row)
                self.assertIn('Coding for this encounter is incomplete', page(detail)['codes'])
                self.assertEqual(self.post(f'/api/encounters/{encounter_id}/reports',
                                           {'kind': 'reviewed', 'fmt': 'csv'}).status_code, 201)

    def test_control_a_visit_with_its_own_proposal_and_a_procedure_alone_stay_as_they_were(self):
        encounter_id = self.reviewed(EM_AND_COLONOSCOPY, SCOPE, VISIT)
        assessment = self.assessment(encounter_id)
        visit = next(s for s in assessment.services['services'] if s['family'] == 'gi.office_em')
        self.assertEqual(assessment.completeness['covered'][visit['id']], ['99214'])
        self.assertEqual(assessment.completeness['state'], 'complete_pending_review')
        self.assertEqual(self.detail(encounter_id)['coding']['state'], 'reviewed')
        self.fresh('Synthetic workspace alone')
        alone = self.reviewed(COLONOSCOPY_ALONE, SCOPE)
        coding = self.detail(alone)['coding']
        self.assertEqual(coding['state'], 'reviewed')
        self.assertTrue(coding['statement'].startswith(f"{EVERY_SERVICE} with a reviewer's decision."))
        closing = section(self.txt(alone, 'reviewed'), 'UNRESOLVED')
        self.assertEqual(closing, '  - none: every documented act the catalogue reconciles has a selected proposal or '
                                  'is not separately reported')


class UncountedVisitIsNamedWithoutOverstatingTests(SimpleTestCase):
    """reports-1, the wording: the reconciliation also leaves unlisted a visit beside a procedure whose performance today
    is not established (the engine's possible procedure day), so the reason names the visit without saying that a
    procedure was done."""

    def test_a_visit_beside_a_possible_procedure_is_named_without_saying_it_was_done(self):
        from tests.test_services_reconcile import run
        text = (SYNTHETIC + 'Date of service: 2026-10-21\nPlace of service: Office\nEstablished patient office visit '
                'for rectal bleeding.\nMedical decision making: moderate.\nTotal time on the date of the encounter was '
                '32 minutes.\nIt is unclear whether a colonoscopy was performed today.\n')
        result = run(text, [])
        statuses = {s['family']: s['status'] for s in result.services['services']}
        self.assertEqual(statuses, {'gi.colonoscopy': 'uncertain', 'gi.office_em': 'performed'})
        self.assertEqual([n['label'] for n in result.completeness['not_listed']],
                         ['office / outpatient visit beside a procedure done or possibly done the same day'])
        self.assertEqual(result.completeness['state'], 'incomplete')
        self.assertNotIn('same-day procedure', ' '.join(result.completeness['reasons']))


class VisitNotCountedSaysWhyTruthfullyTests(SimpleTestCase):
    """reports-1, the services.unproposed line printed beside it (TXT CHECKS, Checks tab): "An E/M mention beside a
    same-day procedure is not counted as a missed service: a separate E/M needs significant, separately identifiable
    documentation" - its reason is false of a note that states that documentation (the verifier's reading), and it is
    also printed on a day whose procedure is only possibly done. The line says so of a documented separate E/M, and
    never says a procedure was done when the record leaves it possible."""

    def unproposed(self, text):
        from tests.test_services_reconcile import check_encounter, run, sel, span
        result = run(text, [sel('45378', span(text, SCOPE[1]))] if SCOPE[1] in text else [])
        return check_encounter(result, 'services.unproposed')

    def test_a_documented_separate_e_m_is_never_told_it_needs_that_documentation(self):
        line = self.unproposed(EM_AND_COLONOSCOPY)
        self.assertEqual(line.status, 'info')
        self.assertNotIn('needs significant, separately identifiable documentation', line.detail)
        self.assertIn('although the document states a significant, separately identifiable E/M', line.detail)
        self.assertNotIn('same-day procedure', line.detail)

    def test_control_without_that_statement_the_rule_is_given_and_a_possible_procedure_is_not_called_done(self):
        from studio.validation import checks
        for text in (EM_AND_COLONOSCOPY.replace(SEPARATE_EM, ''),
                     SYNTHETIC + 'Date of service: 2026-10-21\nPlace of service: Office\nEstablished patient office '
                     'visit for rectal bleeding.\nMedical decision making: moderate.\nTotal time on the date of the '
                     'encounter was 32 minutes.\nIt is unclear whether a colonoscopy was performed today.\n'):
            with self.subTest(text=text[-60:]):
                line = self.unproposed(text)
                self.assertEqual((line.status, line.detail), ('info', checks.VISIT_NOT_MISSED))
                self.assertIn('a separate E/M needs significant, separately identifiable documentation', line.detail)
                self.assertNotIn('same-day procedure', line.detail)


# --- reports-3: "each still needs a reviewer's decision" -------------------------------------------------------------

STILL_NEEDS = "each still needs a reviewer's decision"
DECIDED = "Every documented service has a proposal with a reviewer's decision, but the review is not complete."
CONTEXT_PENDING = 'The encounter context changed; re-assessment has not finished.'


class PendingReviewSaysWhatIsMissingTests(Harness):
    """reports-3: both proposals approved, then a context change (the re-assessment queued) and a Stop. Coding
    completeness said "Every documented service has a proposal; each still needs a reviewer's decision" in the draft
    TXT, the draft CSV row, the API and the banner, while every proposal carried a current approval - which carried
    unchanged once resumed. pending_review names a missing decision only for the proposals that have none (counted as
    readiness counts them); when every proposal is decided it says what readiness still waits for."""

    def approved(self, *codes):
        from tests.test_pipeline_api import FakeProvider
        self.use(FakeProvider(selections=[SNARE, BIOPSY]))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        for code in codes:
            self.decide(encounter_id, code, 'approve')
        return encounter_id

    def coding_row(self, encounter_id):
        (row,) = [line for line in self.csv_text(encounter_id).split('\r\n') if '"coding_completeness"' in line]
        return row

    def test_every_proposal_decided_is_never_told_it_needs_a_decision(self):
        encounter_id = self.approved('45385', '45380')
        self.assertEqual(self.detail(encounter_id)['coding']['state'], 'reviewed')
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'setting': 'hospital_outpatient'}).status_code, 201)
        for step in ('queued', 'stopped'):
            if step == 'stopped':
                self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
            with self.subTest(step=step):
                detail = self.detail(encounter_id)
                coding = detail['coding']
                self.assertEqual(coding['state'], 'pending_review')
                self.assertNotIn(STILL_NEEDS, coding['statement'])
                self.assertTrue(coding['statement'].startswith(DECIDED), coding['statement'])
                self.assertIn(CONTEXT_PENDING, coding['statement'])
                self.assertIn(coding['statement'], section(self.txt(encounter_id), 'CODING COMPLETENESS'))
                self.assertNotIn(STILL_NEEDS, self.coding_row(encounter_id))
                self.assertIn(DECIDED, self.coding_row(encounter_id))
                codes = page(detail)['codes'].replace('&#x27;', "'")
                self.assertNotIn(STILL_NEEDS, codes)
                self.assertNotIn('Every documented service has a proposal to review', codes)
                self.assertIn('Every documented service has a proposal; the review is not complete', codes)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'stopped')
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(self.detail(encounter_id)['coding']['state'], 'reviewed')  # the approvals carried unchanged

    def test_a_partly_decided_set_counts_what_still_needs_a_decision(self):
        coding = self.detail(self.approved('45385'))['coding']
        self.assertEqual(coding['state'], 'pending_review')
        self.assertNotIn(STILL_NEEDS, coding['statement'])
        self.assertTrue(coding['statement'].startswith(
            "Every documented service has a proposal; 1 of 2 still needs a reviewer's decision."), coding['statement'])

    def test_control_an_undecided_set_still_needs_each_decision(self):
        encounter_id = self.approved()
        coding = self.detail(encounter_id)['coding']
        self.assertEqual(coding['state'], 'pending_review')
        self.assertTrue(coding['statement'].startswith(f'Every documented service has a proposal; {STILL_NEEDS}.'))
        self.assertIn(STILL_NEEDS, self.coding_row(encounter_id))


# --- reports-4: passages of a support that was not checked ---------------------------------------------------------

SNARE_ONLY = SYNTHETIC + """Colonoscopy report (fictional)
Date of service: 2026-10-16
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
"""
SHOWS_THE_ACT = 'Source passages that show the coded act'
SERVICE_PASSAGES = 'Passages of the documented service (not checked against the coded act)'


def mark_title(html, text):
    """The title of the source panel's highlight around exactly ``text`` (None when it is not highlighted)."""
    import re
    found = re.search(r'title="([^"]*)">' + re.escape(text) + '</button>', html)
    return found.group(1) if found else None


class NotCheckedPassagesAreNeverEvidenceTests(Harness):
    """reports-4: a biopsy code proposed for a colonoscopy where no biopsy is documented is held (act_missing); its stored
    support says "Not checked: the documented service or act is not established as performed" and keeps the service's
    passages as its source. The card labelled them "Source passages that show the coded act" and the source panel
    marked them "Evidence for 45380". A support that was not checked is shown as the documented service's passages,
    not checked, and never as evidence for the code; its provider passages carry no check result either."""

    def held(self, text, *selections):
        from tests.test_pipeline_api import FakeProvider
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def test_a_not_checked_support_never_says_its_passages_show_the_coded_act(self):
        encounter_id = self.held(SNARE_ONLY, SNARE, ('45380', 'A 6 mm polyp in the rectum was removed with a cold snare.'))
        biopsy = self.assessment(encounter_id).proposals.get(code='45380')
        self.assertEqual((biopsy.status, biopsy.support['status'], biopsy.support['reason']),
                         ('needs_clarification', 'not_applicable', 'act_missing'))
        sources = [s['text'] for s in biopsy.support['source']]
        self.assertIn('Colonoscopy report (fictional)', sources)  # stored as it was: the documented service's passages
        html = page(self.detail(encounter_id))['codes']
        self.assertNotIn(SHOWS_THE_ACT, html)
        self.assertIn(SERVICE_PASSAGES, html)
        self.assertNotIn('does not show the coded act', html)
        title = mark_title(html, 'Colonoscopy report (fictional)')
        self.assertIsNotNone(title, 'the service passage is still highlighted for the reviewer')
        self.assertNotIn('Evidence for', title)
        self.assertIn('45380', title)

    def test_control_a_checked_support_still_shows_the_passage_that_shows_the_act(self):
        text = SNARE_ONLY + 'A separate 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps.\n'
        encounter_id = self.held(text, SNARE, ('45380', 'The colonoscope was advanced to the cecum'))
        biopsy = self.assessment(encounter_id).proposals.get(code='45380')
        self.assertEqual(biopsy.support['status'], 'warn')
        html = page(self.detail(encounter_id))['codes']
        self.assertIn(SHOWS_THE_ACT, html)
        self.assertNotIn(SERVICE_PASSAGES, html)
        self.assertIn('cited by the provider; does not show the coded act', html)
        sampled = 'A separate 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps.'
        self.assertEqual(mark_title(html, sampled), 'Evidence for 45380')


# --- reports-5 (pre-existing at 057a7d398): "No CPT codes were proposed" of a response never read ------------------

NONE_PROPOSED = 'No CPT codes were proposed for this document.'


class NothingIsSaidOfAResponseNeverReadTests(Harness):
    """reports-5: with the provider outcome unknown (a request sent, no complete response read), and still after a
    member reconciled it and stopped the one new attempt, the suggestions panel said "No CPT codes were proposed for this
    document" beside the stored provider check "...its outcome is unknown, so there are no CPT proposals... This is not a
    finding that no codes apply" (the export said "nothing from it was used"). The panel says nothing was proposed only
    of a response the assessment read; otherwise it shows the provider check's own wording - for an unknown outcome,
    a failure and a provider that was not run alike."""

    def codes_tab(self, encounter_id):
        return page(self.detail(encounter_id))['codes'].replace('&#x27;', "'")

    def test_an_unknown_outcome_is_never_read_as_nothing_proposed(self):
        from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider
        self.use(FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')],
                              outcome='unknown'))
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        (run,) = models.ProviderRun.objects.filter(encounter_id=encounter_id)
        self.assertEqual((run.state, run.sent), ('unknown', True))
        check = self.encounter_check(encounter_id, 'provider.status')
        self.assertEqual(check['status'], 'warn')
        self.assertIn('outcome is unknown', check['detail'])
        html = self.codes_tab(encounter_id)
        self.assertNotIn(NONE_PROPOSED, html)
        self.assertIn(check['detail'], html)
        # reconciled, then the one new attempt stopped before it sent: the assessment still read no response
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(run.pk), 'note': 'Checked the provider console: nothing recorded.'})
        self.assertIn(reply.status_code, (200, 201), reply.content)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'stopped')
        html = self.codes_tab(encounter_id)
        self.assertNotIn(NONE_PROPOSED, html)
        self.assertIn('outcome is unknown', html)

    def test_a_provider_that_was_not_run_gives_its_own_wording(self):
        from tests.test_pipeline_api import OFFICE_NOTE
        patcher = mock.patch('studio.jobs.get_provider', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id).exists())
        check = self.encounter_check(encounter_id, 'provider.status')
        self.assertEqual(check['status'], 'not_verified')
        html = self.codes_tab(encounter_id)
        self.assertNotIn(NONE_PROPOSED, html)
        self.assertIn(check['detail'], html)

    def test_control_a_response_read_with_no_selected_code_still_says_none_were_proposed(self):
        from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider
        self.use(FakeProvider(selections=[]))
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        self.assertEqual(self.assessment(encounter_id).summary['provider_status'], 'succeeded')
        self.assertIn(NONE_PROPOSED, self.codes_tab(encounter_id))


# --- skeptic of the first repair, reports-1: the services.unresolved check beside a visit no proposal accounts for ---

UNLISTED_VISIT = 'office / outpatient visit beside a procedure done or possibly done the same day'
EVERY_ACT = 'Every documented act that the coverage catalogue reconciles has a selected proposal'
NAMED_VISIT = (f'1 documented service has no supported proposal and is not listed as unresolved: {UNLISTED_VISIT}; no '
               'proposal accounts for it.')
FLAT_LESION_BIOPSY = 'A 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps.\n'


def visit_beside_findings_read_in_part():
    """The reports-1 visit, then a colonoscopy whose findings sentence is longer than the 1,200 characters read for
    acts (the ec5 REPORTFACTS report-8 shape): the reading records a problem, and the visit is read."""
    from tests.test_repairs_ec5_reportfacts import LONG_FINDINGS
    return EM_AND_COLONOSCOPY.split('Procedure: Colonoscopy')[0] + 'Procedure: Colonoscopy\n' + LONG_FINDINGS + '\n'


CECUM = ('45378', 'The colonoscope was advanced to the cecum')


class UnresolvedCheckNamesTheUnlistedVisitTests(Harness):
    """Skeptic of the reports-1 repair (bc261aee3): completeness.not_listed held the office visit (covered [], never
    listed as unresolved beside a same-day procedure), and coding completeness and UNRESOLVED named it - yet the stored
    services.unresolved check passed with "Every documented act that the coverage catalogue reconciles has a selected
    proposal, or is not separately reported under a profile rule" (reviewed TXT CHECKS, the Checks tab), and over a
    reading read in part it warned "Among what was read, every documented act ... has a selected proposal" of a visit
    that was read. The check is about documented services without a supported proposal: it names one no proposal
    accounts for, never passes beside it and never says every act has one."""

    def assessed(self, text, *selections):
        from tests.test_pipeline_api import FakeProvider
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def reviewed(self, text, *selections):
        encounter_id = self.assessed(text, *selections)
        for code, _ in selections:
            self.decide(encounter_id, code, 'approve')
        return encounter_id

    def not_listed(self, encounter_id):
        return [n['label'] for n in self.assessment(encounter_id).completeness['not_listed']]

    def test_the_check_never_passes_beside_an_unlisted_visit_and_names_it(self):
        for index, text in enumerate((EM_AND_COLONOSCOPY, EM_AND_COLONOSCOPY.replace(SEPARATE_EM, ''))):
            with self.subTest(separate_em=index == 0):
                self.fresh(f'Synthetic workspace {index}')
                encounter_id = self.reviewed(text, SCOPE)
                self.assertEqual(self.not_listed(encounter_id), [UNLISTED_VISIT])
                self.assertEqual(self.assessment(encounter_id).completeness['unresolved_items'], [])
                check = self.encounter_check(encounter_id, 'services.unresolved')
                self.assertEqual(check['status'], 'warn')
                self.assertNotIn(EVERY_ACT, check['detail'])
                self.assertTrue(check['detail'].startswith(NAMED_VISIT), check['detail'])
                self.assertIn('Every other documented act that the coverage catalogue reconciles has a selected '
                              'proposal', check['detail'])
                reviewed = self.txt(encounter_id, 'reviewed')
                self.assertIn('[WARN] services.unresolved — Documented services without a supported proposal: '
                              + check['detail'], reviewed)
                self.assertNotIn('[PASS] services.unresolved', reviewed)
                checks_tab = page(self.detail(encounter_id))['checks'].replace('&#x27;', "'")
                self.assertIn(check['detail'], checks_tab)
                self.assertNotIn(EVERY_ACT, checks_tab)

    def test_a_reading_read_in_part_names_the_visit_it_read(self):
        encounter_id = self.reviewed(visit_beside_findings_read_in_part(), CECUM)
        assessment = self.assessment(encounter_id)
        self.assertTrue(any('was read for acts only in its first 1,200 characters' in p
                            for p in assessment.services['problems']), assessment.services['problems'])
        self.assertEqual(self.not_listed(encounter_id), [UNLISTED_VISIT])
        check = self.encounter_check(encounter_id, 'services.unresolved')
        self.assertEqual(check['status'], 'warn')
        self.assertNotIn('Among what was read, every documented act', check['detail'])
        self.assertTrue(check['detail'].startswith(f'Among what was read, {NAMED_VISIT}'), check['detail'])
        self.assertIn('so a service or act in the part it did not read is not covered by this check', check['detail'])
        self.assertIn(check['detail'], self.txt(encounter_id, 'reviewed'))

    def test_an_item_listed_beside_the_visit_is_named_with_it(self):
        encounter_id = self.assessed(EM_AND_COLONOSCOPY + FLAT_LESION_BIOPSY, SCOPE)  # 45378 is held beside it
        listed = [u['label'] for u in self.assessment(encounter_id).completeness['unresolved_items']]
        self.assertEqual(len(listed), 1)
        self.assertTrue(listed[0].startswith('forceps biopsy'), listed)
        self.assertEqual(self.not_listed(encounter_id), [UNLISTED_VISIT])
        check = self.encounter_check(encounter_id, 'services.unresolved')
        self.assertEqual(check['status'], 'warn')
        self.assertTrue(check['detail'].startswith(f'Unresolved: {listed[0]}'), check['detail'])
        self.assertIn(f'No code is added for them and no alternative is promoted. {NAMED_VISIT}', check['detail'])

    def test_control_without_an_unlisted_service_the_check_reads_as_before(self):
        encounter_id = self.reviewed(EM_AND_COLONOSCOPY, SCOPE, VISIT)  # the visit has its own proposal
        self.assertEqual(self.not_listed(encounter_id), [])
        check = self.encounter_check(encounter_id, 'services.unresolved')
        self.assertEqual(check['status'], 'pass')
        self.assertTrue(check['detail'].startswith(EVERY_ACT), check['detail'])
        self.fresh('Synthetic workspace alone')
        alone = self.reviewed(COLONOSCOPY_ALONE, SCOPE)
        self.assertEqual(self.encounter_check(alone, 'services.unresolved')['status'], 'pass')
        self.fresh('Synthetic workspace listed alone')
        listed = self.assessed(COLONOSCOPY_ALONE + FLAT_LESION_BIOPSY, SCOPE)
        check = self.encounter_check(listed, 'services.unresolved')
        self.assertEqual(check['status'], 'warn')
        self.assertTrue(check['detail'].endswith('No code is added for them and no alternative is promoted.'),
                        check['detail'])


# --- skeptic of the first repair, reports-1: the UNRESOLVED closing line over a reading read in part ---------------

PROBLEM_TAIL = ('the documented-service reading reported a problem, listed under DOCUMENTED SERVICES, so a service or act '
                'in the part it did not read is not listed')
EXCEPT_VISIT = f', except {UNLISTED_VISIT}, which no proposal accounts for and which is not listed as unresolved'


class UnresolvedSectionNamesTheUnlistedVisitTests(Harness):
    """Skeptic of the reports-1 repair (bc261aee3): the repair named the unlisted visit only on the closing line of a
    fully reconciled reading. Over a reading read in part (the visit, then a findings sentence of 1,315 characters),
    _unresolved_section returned the partial-reading line first, so UNRESOLVED read only "none among what was read: the
    documented-service reading reported a problem, ... so a service or act in the part it did not read is not listed" -
    that nothing READ lacks a supported proposal - while the visit was read, has none and coding completeness named it.
    Every closing line names the documented services no proposal accounts for that are not listed."""

    def assessed(self, text, *selections):
        from tests.test_pipeline_api import FakeProvider
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def unresolved(self, encounter_id, kind='draft'):
        return section(self.txt(encounter_id, kind), 'UNRESOLVED')

    def test_a_reading_read_in_part_names_the_visit_it_read_on_its_closing_line(self):
        encounter_id = self.assessed(visit_beside_findings_read_in_part(), CECUM)
        self.assertEqual([n['label'] for n in self.assessment(encounter_id).completeness['not_listed']],
                         [UNLISTED_VISIT])
        self.assertEqual(self.detail(encounter_id)['coding']['state'], 'incomplete')
        expected = f'  - none among what was read{EXCEPT_VISIT}: {PROBLEM_TAIL}'
        self.assertEqual(self.unresolved(encounter_id), expected)
        self.decide(encounter_id, '45378', 'approve')
        self.assertEqual(self.unresolved(encounter_id, 'reviewed'), expected)
        self.assertNotIn('[', expected)  # never read as an unresolved item by the download verifier

    def test_an_item_listed_beside_the_visit_keeps_the_visit_named(self):
        read_in_part = visit_beside_findings_read_in_part().replace(
            'Procedure: Colonoscopy\n', 'Procedure: Colonoscopy\n' + FLAT_LESION_BIOPSY)
        for name, text, closing in (
                ('read in part', read_in_part, f'  - no other among what was read{EXCEPT_VISIT}: {PROBLEM_TAIL}'),
                ('read whole', EM_AND_COLONOSCOPY + FLAT_LESION_BIOPSY,
                 '  - no other: every other documented act the catalogue reconciles has a selected proposal or is not '
                 f'separately reported{EXCEPT_VISIT}')):
            with self.subTest(name):
                self.fresh(f'Synthetic workspace {name}')
                encounter_id = self.assessed(text, CECUM)
                completeness = self.assessment(encounter_id).completeness
                self.assertEqual(len(completeness['unresolved_items']), 1)
                self.assertEqual([n['label'] for n in completeness['not_listed']], [UNLISTED_VISIT])
                lines = self.unresolved(encounter_id).split('\n')
                self.assertTrue(lines[0].startswith('  - forceps biopsy'), lines)
                self.assertTrue(lines[0].endswith('[not_covered]'), lines)
                self.assertEqual(lines[-1], closing)
                self.assertNotIn(' [', closing)

    def test_control_without_an_unlisted_service_the_closing_lines_stay_as_they_were(self):
        from tests.test_repairs_ec5_reportfacts import LONG_FINDINGS
        read_in_part = COLONOSCOPY_ALONE.replace('No polyps were seen.\n', LONG_FINDINGS + '\n')
        encounter_id = self.assessed(read_in_part, CECUM)
        self.assertEqual(self.assessment(encounter_id).completeness['not_listed'], [])
        self.assertEqual(self.unresolved(encounter_id), f'  - none among what was read: {PROBLEM_TAIL}')
        self.fresh('Synthetic workspace listed')
        listed = self.assessed(COLONOSCOPY_ALONE + FLAT_LESION_BIOPSY, CECUM)
        lines = self.unresolved(listed).split('\n')
        self.assertTrue(lines[0].endswith('[not_covered]'), lines)
        self.assertFalse(any(line.startswith('  - no other') for line in lines), lines)
