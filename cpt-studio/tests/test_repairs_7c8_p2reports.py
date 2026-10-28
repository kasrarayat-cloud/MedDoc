"""Continuation round 7c8, refutation phase 2, cluster P2REPORTS (report truth, class 3): each surface says only what
the stored rows support, worded from the rows; the second review's outcome is stated wherever the primary's "nothing
proposed" would otherwise be said. Synthetic data only; the provider is an in-process fake (no network).

Each class reproduces a finding of the refutation pass over 20568b077 (refute-p2, lens 'reports2', verified) with its
smallest input and asserts the wording that is true of the persisted state, beside a control that must not change.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from studio import models
from studio.gi.profiles import PROFILES
from studio.providers.corti import ADAPTER_VERSION
from studio.types import ProviderRequest, RawExchange
from studio.validation import checks
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_7c8_p1reports import (ASKED, COLONOSCOPY, EM_AND_COLONOSCOPY, NOT_A_FINDING, SCOPE,
                                              SCOPE_SENTENCE, SNARE, Harness, SecondOutcome)
from tests.test_services_reconcile import run, sel, span
from tests.test_services_second_review import TwoPassProvider, ask

APP = Path(settings.BASE_DIR) / 'studio' / 'static' / 'studio' / 'app.js'
SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
NONE_PROPOSED = 'No CPT codes were proposed for this document.'

NODE = r"""
const app = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const data = JSON.parse(input);
  const out = {};
  if (data.detail) {
    const layout = app.documentLayout(data.detail);
    out.codes = app.reviewView(data.detail, layout, 'codes', false);
    out.checks = app.reviewView(data.detail, layout, 'checks', false);
    out.export = app.exportStatusText(data.detail);
  }
  if (data.row) {
    out.row = app.documentRow(data.row);
    out.invite = app.inviteMarkup([data.row]);
  }
  process.stdout.write(JSON.stringify(out));
});
"""


def screen(detail=None, row=None):
    """What the shipped app.js renders (node runs the file): the codes and checks tabs and the export dialog's status for
    an encounter view, the documents-list row and the "Most recent" invite for a list row."""
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the screen checks need it')
    done = subprocess.run([node, '-e', NODE, str(APP)], input=json.dumps({'detail': detail, 'row': row}),
                          capture_output=True, text=True, timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-3000:])
    out = json.loads(done.stdout)
    unescape = (('&#x27;', "'"), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>'), ('&amp;', '&'))
    for key, value in out.items():
        for old, new in unescape:
            value = value.replace(old, new)
        out[key] = value
    return out


# --- reports2:0: services.unproposed never passes beside a performed service routing detected with no proposal ------

EGD_ONLY = SYNTHETIC + """Upper endoscopy report (fictional)
Date of service: 2026-10-16
Procedure: EGD
The upper endoscope was advanced to the second part of the duodenum and the examination was completed.
"""
EGD_AND_COLONOSCOPY = SYNTHETIC + """Endoscopy report (fictional)
Date of service: 2026-10-16
Procedures: EGD and colonoscopy
EGD: The upper endoscope was advanced to the second part of the duodenum and the examination was completed.
Colonoscopy: The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
"""
COLONOSCOPY_ONLY = SYNTHETIC + """Colonoscopy report (fictional)
Date of service: 2026-10-16
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
"""
MISSED_EGD = (f'Possible missed service: {PROFILES["gi.egd"].label} is documented as performed with no selected '
              'proposal.')
MISSED_COLONOSCOPY = 'Possible missed service: Colonoscopy is documented as performed with no selected proposal.'
EVERY_DETECTED = 'Every performed service that routing detected in the document has a selected proposal'


def unproposed(result):
    return next(c for c in result.encounter_checks if c.id == 'services.unproposed')


class UnproposedNamesADetectedServiceWithoutAProposalTests(Harness):
    """reports2:0 (a regression from the installed 057a7d398, introduced by c0f0708f4): routing detected a performed EGD
    (or colonoscopy) and no selected proposal accounts for it, yet services.unproposed passed with "Every performed
    service that routing detected in the document has a selected proposal" - in the stored check, the draft and
    reviewed TXT CHECKS and the Checks tab: engine._missed skipped, with no trace, every family the documented-service
    reading reads as done. The check names such a service, as 057a7d398 did; the reconciliation still lists it."""

    def stored(self, text, *selections):
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def test_an_egd_with_no_selected_proposal_is_named_never_passed(self):
        encounter_id = self.stored(EGD_ONLY)
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('warn', MISSED_EGD))
        draft = self.txt(encounter_id)
        self.assertIn(f'[WARN] services.unproposed', draft)
        self.assertIn(MISSED_EGD, draft)
        self.assertNotIn(EVERY_DETECTED, draft)
        shown = screen(self.detail(encounter_id))['checks']
        self.assertIn(MISSED_EGD, shown)
        self.assertNotIn(EVERY_DETECTED, shown)

    def test_the_reviewed_report_names_the_egd_beside_an_approved_colonoscopy_code(self):
        encounter_id = self.stored(EGD_AND_COLONOSCOPY, SNARE)
        self.decide(encounter_id, '45385', 'approve')
        detail = self.detail(encounter_id)
        self.assertTrue(detail['readiness']['reviewed'], detail['readiness'])
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('warn', MISSED_EGD))
        reviewed = self.txt(encounter_id, 'reviewed')
        self.assertIn('[WARN] services.unproposed', reviewed)
        self.assertIn(MISSED_EGD, reviewed)
        self.assertNotIn(EVERY_DETECTED, reviewed)
        self.assertNotIn('Colonoscopy is documented as performed with no selected proposal', reviewed)
        # the reconciliation still lists the EGD, act by act, as before
        unresolved = self.encounter_check(encounter_id, 'services.unresolved')
        self.assertEqual(unresolved['status'], 'warn')
        self.assertIn('upper endoscopy (documented as performed) has no supported proposal', unresolved['detail'])

    def test_a_colonoscopy_with_no_code_at_all_is_named(self):
        encounter_id = self.stored(COLONOSCOPY_ONLY)
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('warn', MISSED_COLONOSCOPY))

    def test_control_a_colonoscopy_with_its_own_code_still_passes(self):
        encounter_id = self.stored(COLONOSCOPY, SNARE)
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('pass', checks.UNPROPOSED_PASS))


EUS_WITH_EGD = (SYNTHETIC + 'Date of service: 2026-10-14\nIndication: EUS for evaluation of a pancreatic head mass.\n'
                'Procedure: EGD and upper endoscopic ultrasound.\nFindings: The echoendoscope was advanced to the second '
                'portion of the duodenum. A 2 cm hypoechoic mass in the pancreatic head was sampled by fine-needle '
                'aspiration with three passes.\n')
FNA = 'was sampled by fine-needle aspiration with three passes'


class UnproposedKeepsWhatTheReconciliationAccountsForTests(SimpleTestCase):
    """Controls of reports2:0 at the engine: what the reconciliation accounts for without a code of the family's own is
    never named as a possible missed service - an EGD the documented-service reading reads as the endoscopic portion of
    an EUS whose code is selected (the EUS code includes the examination), and an office visit beside a procedure done
    the same day (the visit is not counted: services.unresolved names it)."""

    def test_an_egd_included_in_a_selected_eus_is_not_named(self):
        text = EUS_WITH_EGD
        result = run(text, [sel('43242', span(text, FNA))])
        self.assertEqual([(s['family'], s['included_in']) for s in result.services['services']],
                         [('gi.eus', ''), ('gi.egd', 'S1')])
        check = unproposed(result)
        self.assertNotIn('Upper GI endoscopy', check.detail)
        self.assertEqual((check.status, check.detail), ('pass', checks.UNPROPOSED_PASS))

    def test_an_egd_included_in_an_eus_with_no_code_is_named_with_it(self):
        text = EUS_WITH_EGD
        result = run(text, [])
        check = unproposed(result)
        self.assertEqual(check.status, 'warn')
        self.assertIn('Endoscopic ultrasound', check.detail)
        self.assertNotEqual(check.detail, checks.UNPROPOSED_PASS)

    def test_a_visit_beside_a_same_day_procedure_is_still_not_counted(self):
        text = EM_AND_COLONOSCOPY  # it states a significant, separately identifiable E/M
        result = run(text, [sel(SCOPE[0], span(text, SCOPE[1]))])
        check = unproposed(result)
        self.assertEqual((check.status, check.detail), ('info', checks.VISIT_NOT_MISSED_DOCUMENTED))
        plain = text.replace('A significant, separately identifiable evaluation and management service was provided '
                             'today.\n', '')
        result = run(plain, [sel(SCOPE[0], span(plain, SCOPE[1]))])
        check = unproposed(result)
        self.assertEqual((check.status, check.detail), ('info', checks.VISIT_NOT_MISSED))


# --- reports2:1: the panel states the shown assessment's second review, whatever the current revision ----------------

ADDENDUM = {'text': 'Signed by the fictional endoscopist.', 'synthetic_attestation': 'yes'}


class PanelStatesTheShownAssessmentsSecondReviewTests(Harness):
    """reports2:1: the primary response read with no code, a reviewer asks for the second review and it ends unknown (or
    failed); an addendum (how a clarification is answered) then leaves revision 1's assessment on screen while revision
    2 is not assessed - its predict blocked by the unknown outcome, or stopped. second_review.run was null (it named a
    run only for an assessment of the current revision), so the suggestions panel said "No CPT codes were proposed for
    this document." beside the reconcile card. It names the second review made for the answer the SHOWN assessment
    reads, and the panel states that review's outcome."""

    def asked(self, second):
        self.use(SecondOutcome([], [('45378', SCOPE_SENTENCE)], second))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        return encounter_id, models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review')

    def addendum(self, encounter_id, stop=False):
        reply = self.post(f'/api/encounters/{encounter_id}/addenda', ADDENDUM)
        self.assertEqual(reply.status_code, 201, reply.content)
        if stop:
            self.assertIn(self.post(f'/api/encounters/{encounter_id}/stop').status_code, (200, 201, 202))
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual((encounter.current_revision.number, encounter.current_assessment.revision.number), (2, 1))

    def panel(self, encounter_id):
        """The suggestions panel's paragraph when no code is selected (a stopped revision 2 has no text, so the source
        page shows an empty-card paragraph of its own)."""
        import re
        detail = self.detail(encounter_id)
        (copy,) = re.findall(r'<div class="check-list-card"><p class="card-empty">(.*?)</p></div>',
                             screen(detail)['codes'])
        return detail, copy

    def test_an_unknown_second_review_is_stated_after_an_addendum(self):
        encounter_id, run_ = self.asked('unknown')
        self.addendum(encounter_id)
        detail, copy = self.panel(encounter_id)
        self.assertEqual(detail['state'], 'provider_unknown')
        self.assertEqual(detail['second_review']['run'], str(run_.pk))
        self.assertNotIn(NONE_PROPOSED, copy)
        self.assertIn(f'{ASKED} It was sent, but its outcome is unknown: no response was recorded, so nothing from it '
                      f'was read. {NOT_A_FINDING}', copy)
        self.assertEqual(len(self.provider.requests), 2)  # nothing more was sent

    def test_a_failed_or_unknown_second_review_is_stated_after_an_addendum_and_stop(self):
        for second, said in (('failed', 'It failed: HTTP 500 from the provider. Nothing from it was used.'),
                             ('unknown', 'It was sent, but its outcome is unknown: no response was recorded, so '
                                         'nothing from it was read.')):
            with self.subTest(second):
                self.fresh(f'Synthetic workspace {second}')
                encounter_id, run_ = self.asked(second)
                self.addendum(encounter_id, stop=True)
                detail, copy = self.panel(encounter_id)
                self.assertEqual(detail['state'], 'stopped')
                self.assertEqual(detail['second_review']['run'], str(run_.pk))
                self.assertNotIn(NONE_PROPOSED, copy)
                self.assertIn(f'{ASKED} {said} {NOT_A_FINDING}', copy)

    def test_control_the_new_revisions_assessment_never_reads_the_older_ones_review(self):
        # the primary read with no code, the second review unknown, every later request answered (with no code)
        self.use(TwoPassProvider([], [], outcomes=['succeeded', 'unknown']))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        run_ = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review')
        self.assertEqual(run_.state, 'unknown')
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(run_.pk), 'note': 'Checked the provider console: nothing recorded.'})
        self.assertIn(reply.status_code, (200, 201), reply.content)
        drain()
        reply = self.post(f'/api/encounters/{encounter_id}/addenda', ADDENDUM)
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual((encounter.current_revision.number, encounter.current_assessment.revision.number), (2, 2))
        detail = self.detail(encounter_id)
        self.assertIsNone(detail['second_review']['run'])  # none was made for revision 2's answer

    def test_control_before_the_addendum_the_run_is_named_as_before(self):
        encounter_id, run_ = self.asked('unknown')
        detail, copy = self.panel(encounter_id)
        self.assertEqual(detail['second_review']['run'], str(run_.pk))
        self.assertNotIn(NONE_PROPOSED, copy)


# --- reports2:2: the list label states the second review's outcome, never "No CPT codes proposed" -----------------

NO_CODES_LABEL = 'No CPT codes proposed'


def list_row(client, encounter_id):
    (row,) = [r for r in client.get('/api/encounters').json()['encounters'] if r['id'] == encounter_id]
    return row


class StateLabelStatesTheSecondReviewOutcomeTests(Harness):
    """reports2:2: the primary response read with no code; the second review a reviewer asked for was sent and its
    outcome is unknown, and a member reconciled it (or it failed: HTTP 500). The state is 'no_codes' - nothing is left
    to decide - and its label "No CPT codes proposed" was the documents-list badge and the "Most recent" line, while the
    same encounter's panel and blocker say the second review's outcome is unknown, or that it failed. The label states
    that outcome from the run's row; the state is unchanged."""

    def ended(self, second, reconcile=False):
        self.use(SecondOutcome([], [('45378', SCOPE_SENTENCE)], second))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        run_ = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review')
        if reconcile:
            reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                              {'provider_run_id': str(run_.pk), 'note': 'Checked the provider console.'})
            self.assertIn(reply.status_code, (200, 201), reply.content)
            drain()
        return encounter_id, run_

    def test_a_reconciled_unknown_or_failed_second_review_is_the_label(self):
        for second, reconcile, label in (('unknown', True, 'Second review outcome unknown'),
                                         ('failed', False, 'Second review failed')):
            with self.subTest(second):
                self.fresh(f'Synthetic workspace {second}')
                encounter_id, run_ = self.ended(second, reconcile)
                self.assertEqual(run_.state, second)
                row = list_row(self.client, encounter_id)
                self.assertEqual((row['state'], row['state_label']), ('no_codes', label))
                detail = self.detail(encounter_id)
                self.assertEqual((detail['state'], detail['state_label']), ('no_codes', label))
                shown = screen(row=row)
                self.assertIn(label, shown['row'])
                self.assertNotIn(NO_CODES_LABEL, shown['row'])
                self.assertIn(f'Most recent · {label} · 16 Oct 2026', shown['invite'])

    def test_control_nothing_asked_and_a_second_review_read_keep_the_label(self):
        self.use(FakeProvider(selections=[]))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(list_row(self.client, encounter_id)['state_label'], NO_CODES_LABEL)
        self.fresh('Synthetic workspace read')
        self.use(SecondOutcome([], [], 'read'))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        row = list_row(self.client, encounter_id)
        self.assertEqual((row['state'], row['state_label']), ('no_codes', NO_CODES_LABEL))


# --- reports2:3: a response whose codes were excluded or are only alternatives is never "no code proposed" -----------

NOTE_45378 = SYNTHETIC + """Lakeside Endoscopy Unit (fictional)
Procedure report
Date of service: 2026-10-16
Procedure: Colonoscopy
Indication: Screening, average risk.
The colonoscope was advanced to the cecum and the examination was completed.
No polyps were seen. No biopsies were taken.
Impression: Normal colonoscopy to the cecum.
"""
QUOTE = 'The colonoscope was advanced to the cecum and the examination was completed.'
NOT_REVIEWABLE = ('No code is selected for approval: the provider proposed only codes that were excluded or offered as '
                  'alternatives')
NOT_REVIEWABLE_LABEL = 'No code selected for approval'


class Scripted:
    """The live adapter's name and version (the real normaliser reads the stored run); send() never leaves the process
    and answers with ``codes`` and ``candidates`` in Corti's shape, an evidence quote placed at its exact offsets."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self, codes=(), candidates=()):
        self.codes, self.candidates, self.requests = list(codes), list(candidates), []

    def build_request(self, text, service_date):
        contexts = [text] + ([f'Date of service: {service_date.isoformat()}'] if service_date else [])
        body = {'system': ['icd10cm-outpatient', 'cpt'], 'context': [{'type': 'text', 'text': c} for c in contexts]}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False).encode()).hexdigest()
        return ProviderRequest(provider=self.name, adapter_version=self.adapter_version, body=body,
                               canonical_sha256=digest, contexts=tuple(contexts))

    @staticmethod
    def _item(system, code, context, quote):
        item = {'system': system, 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING', 'alternatives': []}
        if quote:
            start = context.index(quote)
            item['evidences'] = [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}]
        return item

    def send(self, request, *, deadline_s):
        self.requests.append(request)
        context = request.contexts[0]
        data = json.dumps({'codes': [self._item(*c, context=context, quote=q) for *c, q in self.codes],
                           'candidates': [self._item(*c, context=context, quote=q) for *c, q in self.candidates],
                           'usageInfo': {'creditsConsumed': 0.02}}).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=7.0,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


class CandidateThenFailed(Scripted):
    """The primary request is answered as scripted; every later request (the second review) fails with HTTP 500."""

    def send(self, request, *, deadline_s):
        if not self.requests:
            return super().send(request, deadline_s=deadline_s)
        self.requests.append(request)
        return RawExchange(outcome='failed', sent=True, http_status=500, error='HTTP 500 from the provider.')


class NothingProposedIsSaidOnlyOfAResponseThatProposedNothingTests(Harness):
    """reports2:3 (pre-existing at 057a7d398): the provider SELECTED 45378 citing no passage (stored as excluded, "No
    exact source evidence", not reinstatable), or listed it only as a candidate (an alternative). The readiness blocker
    "No CPT code was proposed" (API, the draft TXT's review status, the export dialog) and the label "No CPT codes
    proposed" contradicted the stored response, the stored Proposal row and the report's own provider.status line. They
    say that no proposed code can be reviewed, as the panel does; a response that proposed no CPT code keeps them."""

    def stored(self, provider):
        self.use(provider)
        encounter_id = self.create(NOTE_45378)
        drain()
        return encounter_id

    def test_a_selected_code_excluded_for_no_exact_evidence_or_a_candidate_only(self):
        for name, provider, row in (
                ('selected without a passage', Scripted(codes=[('cpt', '45378', None)]),
                 ('excluded', '45378', False)),
                ('candidate only', Scripted(candidates=[('cpt', '45378', QUOTE)]), ('alternative', '45378', False))):
            with self.subTest(name):
                self.fresh(f'Synthetic workspace {name}')
                encounter_id = self.stored(provider)
                assessment = self.assessment(encounter_id)
                self.assertEqual([(p.bucket, p.code, p.reinstatable) for p in assessment.proposals.all()], [row])
                detail = self.detail(encounter_id)
                self.assertEqual(detail['state'], 'no_codes')
                self.assertEqual(detail['readiness']['blockers'], [NOT_REVIEWABLE])
                self.assertEqual(detail['state_label'], NOT_REVIEWABLE_LABEL)
                self.assertEqual(list_row(self.client, encounter_id)['state_label'], NOT_REVIEWABLE_LABEL)
                draft = self.txt(encounter_id)
                self.assertIn(f'Review status: not complete\n  - {NOT_REVIEWABLE}', draft)
                self.assertNotIn('No CPT code was proposed', draft)
                shown = screen(detail)
                self.assertEqual(shown['export'], f'Draft — not reviewed. Still needed: {NOT_REVIEWABLE}.')
                self.assertIn(NOT_REVIEWABLE_LABEL, screen(row=list_row(self.client, encounter_id))['row'])
                self.assertNotIn(NO_CODES_LABEL, screen(row=list_row(self.client, encounter_id))['row'])

    def test_beside_a_second_review_never_read_the_blocker_says_both(self):
        self.use(CandidateThenFailed(candidates=[('cpt', '45378', SCOPE_SENTENCE)]))
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        self.assertEqual(models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review').state,
                         'failed')
        self.assertEqual([(p.bucket, p.code) for p in self.assessment(encounter_id).proposals.all()],
                         [('alternative', '45378')])
        blockers = self.detail(encounter_id)['readiness']['blockers']
        self.assertEqual(blockers, ['No code is selected for approval: the response that was read proposed only codes '
                                    'that were excluded or offered as alternatives; the second review failed'])
        self.assertEqual(list_row(self.client, encounter_id)['state_label'], 'Second review failed')

    def test_control_a_response_with_no_cpt_code_keeps_the_blocker_and_the_label(self):
        for name, provider in (('none', Scripted()), ('icd only', Scripted(codes=[('icd10cm-outpatient', 'Z12.11',
                                                                                     QUOTE)]))):
            with self.subTest(name):
                self.fresh(f'Synthetic workspace {name}')
                encounter_id = self.stored(provider)
                self.assertEqual(list(self.assessment(encounter_id).proposals.all()), [])
                detail = self.detail(encounter_id)
                self.assertEqual(detail['readiness']['blockers'], ['No CPT code was proposed'])
                self.assertEqual((detail['state'], detail['state_label']), ('no_codes', NO_CODES_LABEL))
                self.assertIn('Review status: not complete\n  - No CPT code was proposed', self.txt(encounter_id))


# --- reports2:4: the walk's verifier reads the support.source marks app.js renders as known exact spans --------------

VB = Path(settings.BASE_DIR) / 'ops' / 'verify_browser.cjs'
MARKS_NODE = r"""
const app = require(process.argv[1]);
const vb = require(process.argv[2]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const doc = JSON.parse(input);
  const html = app.reviewView(doc, app.documentLayout(doc), 'codes', false);
  // read as ops/verify_browser.cjs readDom reads the page: every .evidence-mark's data-keys, every code card
  const UNESCAPE = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#x60;': '`' };
  const unescape = text => text.replace(/&(amp|lt|gt|quot|#x27|#x60);/g, m => UNESCAPE[m]);
  const attr = (attrs, name) => unescape((new RegExp(`\\b${name}="([^"]*)"`).exec(attrs) || [])[1] || '');
  const marks = [...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)]
    .filter(m => (attr(m[1], 'class') || '').split(' ').includes('evidence-mark'))
    .map(m => ({ keys: (attr(m[1], 'data-keys') || attr(m[1], 'data-evidence')).split(' ').filter(Boolean),
                 text: unescape(m[2].replace(/<[^>]*>/g, '')) }));
  const cards = [...html.matchAll(/<article\b([^>]*)>([\s\S]*?)<\/article>/g)]
    .filter(m => (attr(m[1], 'class') || '').split(' ').includes('code-card'))
    .map(m => ({ id: attr(m[1], 'id'), unlocated: (m[2].match(/class="evidence-chip unlocated"/g) || []).length }));
  process.stdout.write(JSON.stringify({ keys: marks.map(m => m.keys), results: vb.checkEvidenceMarks(doc, marks, cards) }));
});
"""
MARKS_NOTE = SYNTHETIC + """Colonoscopy report (fictional)
Date of service: 2026-10-14
Procedure: Colonoscopy with cold snare polypectomy.
The colonoscope was advanced to the cecum.
Sigmoid colon: a 6 mm sessile polyp was removed completely with a cold snare and retrieved.
Transverse colon: a separate 10 mm flat lesion was sampled with cold biopsy forceps for histology.
"""
# The colonoscopy named only in the title: its performance is not established, so a support is not checked
# (not_applicable) and its source passages are the documented service's, marked as not checked (refutation 7c8,
# reports-4) - the verifier's second trigger.
HELD_NOTE = MARKS_NOTE.replace('Date of service: 2026-10-14\nProcedure: Colonoscopy with cold snare polypectomy.',
                               'Date of procedure: 2026-10-14\nColonoscopy with cold snare polypectomy.')
SNARE_SENTENCE = 'Sigmoid colon: a 6 mm sessile polyp was removed completely with a cold snare and retrieved.'
CECUM_CLAUSE = 'The colonoscope was advanced to the cecum.'
FLAT_BIOPSY = 'Transverse colon: a separate 10 mm flat lesion was sampled with cold biopsy forceps for histology.'


def judged_marks(detail):
    """(the marks' keys as the page renders them, the verifier's evidence-mark results) for an encounter view."""
    done = subprocess.run([shutil.which('node'), '-e', MARKS_NODE, str(APP), str(VB)], input=json.dumps(detail),
                          capture_output=True, text=True, timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-3000:])
    out = json.loads(done.stdout)
    return out['keys'], out['results']


class WalkReadsSupportSourceMarksTests(Harness):
    """reports2:4 (verified real; the post-install walk depends on it): app.js marks a selected proposal's exact
    support.source passages as '<id>:s<n>' (since c0f0708f4), and ops/verify_browser.cjs checkEvidenceMarks failed hard
    on them - "dom.marks.known: marks for unknown or inexact spans" - although they are exact spans of a selected
    proposal. Through the API: 45380 citing the cecum clause is held with support 'warn' and CPT Studio's exact source
    passage (the biopsy sentence); the page app.js renders is judged by the shipped verifier."""

    def view(self, text, *selections):
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return self.detail(encounter_id)

    def test_a_support_source_mark_is_a_known_exact_span(self):
        for note, status in ((MARKS_NOTE, 'warn'), (HELD_NOTE, 'not_applicable')):
            with self.subTest(status):
                self.fresh(f'Synthetic workspace {status}')
                detail = self.view(note, ('45385', SNARE_SENTENCE), ('45380', CECUM_CLAUSE))
                (biopsy,) = [p for p in detail['assessment']['proposals']
                             if p['code'] == '45380' and p['bucket'] == 'selected']
                self.assertEqual(biopsy['support']['status'], status)
                text = detail['revision']['text']
                source = biopsy['support']['source']
                self.assertTrue(source)
                self.assertTrue(all(text[s['start']:s['end']] == s['text'] for s in source), source)
                keys, results = judged_marks(detail)
                self.assertIn(f'{biopsy["id"]}:s0', [key for group in keys for key in group])
                known = next(r for r in results if r['id'] == 'dom.marks.known')
                self.assertEqual(known['status'], 'pass', known)
                self.assertEqual([r['id'] for r in results if r['status'] == 'fail'], [])

    def test_control_without_source_passages_the_marks_read_as_before(self):
        detail = self.view(MARKS_NOTE, ('45385', SNARE_SENTENCE), ('45380', FLAT_BIOPSY))
        (biopsy,) = [p for p in detail['assessment']['proposals'] if p['code'] == '45380' and p['bucket'] == 'selected']
        self.assertEqual(biopsy['support'].get('source') or [], [])
        keys, results = judged_marks(detail)
        self.assertFalse(any(':s' in key for group in keys for key in group), keys)
        self.assertEqual([r['id'] for r in results if r['status'] == 'fail'], [])


# --- reports2:0, round 2 (the skeptic of 5bb28ad85): an EGD is accounted for only by a code that includes it ---------

RECTAL_FNA = 'was sampled by fine-needle aspiration with two passes'
EGD_AND_RECTAL_EUS = (SYNTHETIC + 'Date of service: 2026-10-14\nIndication: staging of a rectal mass; dyspepsia.\n'
                      'Procedure: EGD and lower endoscopic ultrasound.\n'
                      'EGD: The gastroscope was advanced to the second portion of the duodenum and the examination was '
                      'completed. The upper examination was normal.\n'
                      'Rectal EUS: The echoendoscope was advanced to the rectosigmoid junction. A 12 mm perirectal lymph '
                      'node ' + RECTAL_FNA + '.\n')
# The lower-tract site is named only by the EUS's own act (its passage names none).
EGD_AND_EUS_OF_A_RECTAL_MASS = (SYNTHETIC + 'Date of service: 2026-10-14\nProcedures: EGD and endoscopic ultrasound.\n'
                                'EGD: The gastroscope was advanced to the second portion of the duodenum and the '
                                'examination was completed. The upper examination was normal.\n'
                                'EUS: The radial echoendoscope was then introduced. A 2 cm hypoechoic mass in the rectum '
                                + RECTAL_FNA + '.\n')
# An upper EUS whose own passage names no site at all: the EGD stays its endoscopic portion.
EGD_WITH_LIMITED_EUS = (SYNTHETIC + 'Date of service: 2026-10-14\n'
                        'Procedure: Upper endoscopy with limited endoscopic ultrasound.\n'
                        'Endoscopic portion: A standard gastroscope was advanced to the second portion of the duodenum. '
                        'The stomach and duodenum were normal.\n\n'
                        'Ultrasound portion: The radial echoendoscope was then introduced. The sonographic evaluation '
                        'was limited to the esophageal wall; a 14 mm hypoechoic lesion arose from the fourth layer.\n')
LIMITED_EUS = 'The radial echoendoscope was then introduced.'
LOWER_TRACT_EUS_CODES = ('45341', '45342', '45391', '45392', '44406', '44407')
ESOPHAGOSCOPY_EUS_CODES = ('43231', '43232')
EGD_WITH_EUS_CODES = ('43237', '43238', '43240', '43242', '43253', '43259')
EGD_LABEL = PROFILES['gi.egd'].label
NO_EGD_PROPOSAL = 'upper endoscopy (documented as performed) has no supported proposal'


def unresolved_items(result):
    return [(u['service'], u['act'], u['reason'], u['label']) for u in result.completeness['unresolved_items']]


class AnEgdBesideALowerTractEusIsItsOwnServiceTests(SimpleTestCase):
    """reports2:0, round 2 (the skeptic of 5bb28ad85, at bf9367d65): services._included marked every performed EGD
    included in the first performed EUS, whatever tract that EUS examines, and _accounted_elsewhere then counted ANY
    selected code of that EUS as accounting for the EGD. An EGD beside a rectal EUS whose sigmoidoscopy EUS code was
    selected and approved read "Every performed service that routing detected in the document has a selected
    proposal" (services.unproposed), "Every documented service has a proposal" (coding completeness) and "included in
    S2: that service's code includes this examination" (documented services) - the original false PASS on a
    paraphrase. An EUS whose own documentation names a lower-tract site includes no upper endoscopy, so the EGD is a
    service of its own whatever code the EUS has; 057a7d398 named it."""

    def test_the_egd_is_never_read_as_part_of_a_rectal_eus(self):
        for text in (EGD_AND_RECTAL_EUS, EGD_AND_EUS_OF_A_RECTAL_MASS):
            with self.subTest(text[100:140]):
                result = run(text, [sel('45342', span(text, RECTAL_FNA))])
                self.assertEqual([(s['family'], s['included_in']) for s in result.services['services']],
                                 [('gi.egd', ''), ('gi.eus', '')])
                inventory = next(c for c in result.encounter_checks if c.id == 'services.inventory')
                self.assertNotIn('included in', inventory.detail)

    def test_no_selected_code_of_a_rectal_eus_accounts_for_the_egd(self):
        # a sigmoidoscopy, colonoscopy, stoma or esophagoscopy EUS code includes no upper endoscopy; nor does an
        # EGD-with-EUS code selected for this EUS, which the document places in the rectum
        for text in (EGD_AND_RECTAL_EUS, EGD_AND_EUS_OF_A_RECTAL_MASS):
            for code in LOWER_TRACT_EUS_CODES + ESOPHAGOSCOPY_EUS_CODES + EGD_WITH_EUS_CODES:
                with self.subTest(code=code, text=text[100:140]):
                    result = run(text, [sel(code, span(text, RECTAL_FNA))])
                    check = unproposed(result)
                    self.assertEqual(check.status, 'warn')
                    self.assertTrue(check.detail.startswith(f'Possible missed service: {EGD_LABEL}'), check.detail)
                    self.assertNotIn(EVERY_DETECTED, check.detail)
                    self.assertIn(('S1', '', 'no_proposal', NO_EGD_PROPOSAL), unresolved_items(result))
                    self.assertEqual(result.completeness['state'], 'incomplete')
                    self.assertFalse(result.completeness['statement'].startswith('Every documented service'))

    def test_control_the_codes_of_the_rectal_eus_with_the_egd_code_pass(self):
        text = EGD_AND_RECTAL_EUS
        egd = 'The gastroscope was advanced to the second portion of the duodenum'
        result = run(text, [sel('45342', span(text, RECTAL_FNA)), sel('43235', span(text, egd))])
        self.assertEqual((unproposed(result).status, unproposed(result).detail), ('pass', checks.UNPROPOSED_PASS))
        self.assertEqual(unresolved_items(result), [])


class AnIncludedEgdIsAccountedForOnlyByACodeThatIncludesItTests(SimpleTestCase):
    """reports2:0, round 2: an EGD the inventory reads as the endoscopic portion of an upper EUS is accounted for only
    by a selected code of that EUS that includes the examination - an EGD-with-EUS code (catalogue
    includes_examination). A sigmoidoscopy, colonoscopy, stoma or esophagoscopy EUS code selected for it includes none:
    the EGD is then named by services.unproposed and listed by the reconciliation, and the documented services never
    say that service's code includes it. While the EUS has no code at all, the EGD asks for none of its own (the EUS is
    listed itself), as before."""

    def test_a_code_that_includes_no_upper_endoscopy_leaves_the_egd_without_a_proposal(self):
        for text, quote, egd in ((EUS_WITH_EGD, FNA, 'S2'), (EGD_WITH_LIMITED_EUS, LIMITED_EUS, 'S1')):
            for code in LOWER_TRACT_EUS_CODES + ESOPHAGOSCOPY_EUS_CODES:
                with self.subTest(code=code, egd=egd):
                    result = run(text, [sel(code, span(text, quote))])
                    including = {s['id']: s['included_in'] for s in result.services['services']}
                    self.assertTrue(including[egd])  # the document reading is unchanged: an upper EUS's portion
                    check = unproposed(result)
                    self.assertEqual((check.status, check.detail), ('warn', MISSED_EGD))
                    self.assertIn((egd, '', 'no_proposal', NO_EGD_PROPOSAL), unresolved_items(result))
                    self.assertEqual(result.completeness['state'], 'incomplete')

    def test_control_an_egd_with_eus_code_accounts_for_the_egd(self):
        for text, quote in ((EUS_WITH_EGD, FNA), (EGD_WITH_LIMITED_EUS, LIMITED_EUS)):
            for code in EGD_WITH_EUS_CODES:
                with self.subTest(code=code, text=text[100:140]):
                    result = run(text, [sel(code, span(text, quote))])
                    self.assertTrue(any(s['included_in'] for s in result.services['services']))
                    check = unproposed(result)
                    self.assertEqual((check.status, check.detail), ('pass', checks.UNPROPOSED_PASS))
                    self.assertFalse([u for u in unresolved_items(result) if u[1] == '' and u[2] == 'no_proposal'])

    def test_control_an_eus_with_no_code_is_listed_and_its_egd_asks_for_none(self):
        result = run(EGD_WITH_LIMITED_EUS, [])
        self.assertEqual([(u[0], u[2]) for u in unresolved_items(result)], [('S2', 'no_proposal')])
        self.assertEqual(unproposed(result).status, 'warn')

    def test_which_codes_include_an_upper_endoscopy(self):
        from studio.gi import catalogue
        self.assertEqual(sorted(c for c in catalogue.CODES if catalogue.includes_examination(c, 'egd')),
                         sorted(EGD_WITH_EUS_CODES))
        for code in LOWER_TRACT_EUS_CODES + ESOPHAGOSCOPY_EUS_CODES + ('43235', '45378', '99999', ''):
            self.assertFalse(catalogue.includes_examination(code, 'egd'), code)
        self.assertFalse(catalogue.includes_examination('43242', 'esophagoscopy'))

    def test_the_reconciliation_rule_on_a_constructed_inventory(self):
        from studio.gi.services import DocumentedService, ServiceInventory
        from studio.validation import reconcile
        eus = DocumentedService('S1', 'gi.eus', 'eus', 'performed')
        egd = DocumentedService('S2', 'gi.egd', 'egd', 'performed', included_in='S1')
        inventory = ServiceInventory('test', services=(eus, egd))
        self.assertTrue(reconcile.inclusion_asks_no_code(inventory, egd, []))
        self.assertTrue(reconcile.inclusion_asks_no_code(inventory, egd, [('43259', 'gi.eus')]))
        self.assertTrue(reconcile.inclusion_asks_no_code(inventory, egd, [('45342', 'gi.eus'), ('43242', 'gi.eus')]))
        self.assertFalse(reconcile.inclusion_asks_no_code(inventory, egd, [('45342', 'gi.eus')]))
        self.assertFalse(reconcile.inclusion_asks_no_code(inventory, eus, [('43259', 'gi.eus')]))  # included in none
        unresolved, _, covered = reconcile.reconcile(inventory, [('43231', 'gi.eus')])
        self.assertEqual([(u.service, u.reason) for u in unresolved], [('S2', 'no_proposal')])
        self.assertEqual(covered, {'S1': ['43231'], 'S2': []})


class TheReportsNeverAccountForAnEgdBesideARectalEusTests(Harness):
    """reports2:0, round 2, through the API as the skeptic ran it: the provider selects only 45342 for the rectal EUS's
    sampling, the reviewer approves it, and the reviewed report is produced (201). The stored check, the reviewed TXT and
    the Checks tab name the EGD; coding completeness says the encounter is incomplete; nothing says the EGD is included
    in the EUS or that the EUS's code includes it."""

    def stored(self, text, *selections):
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def test_the_reviewed_report_names_the_egd(self):
        encounter_id = self.stored(EGD_AND_RECTAL_EUS, ('45342', RECTAL_FNA))
        self.decide(encounter_id, '45342', 'approve')
        reply = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertEqual(reply.status_code, 201, reply.content)
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('warn', MISSED_EGD))
        reviewed = self.txt(encounter_id, 'reviewed')
        self.assertIn('[WARN] services.unproposed', reviewed)
        self.assertIn(MISSED_EGD, reviewed)
        self.assertNotIn(EVERY_DETECTED, reviewed)
        self.assertIn('State: incomplete', reviewed)
        self.assertNotIn('Every documented service has a proposal', reviewed)
        self.assertNotIn('included in S2', reviewed)
        self.assertNotIn('included in endoscopic ultrasound', reviewed)
        shown = screen(self.detail(encounter_id))
        self.assertIn(MISSED_EGD, shown['checks'])
        self.assertNotIn(EVERY_DETECTED, shown['checks'])
        self.assertNotIn('Included in S2', shown['codes'] + shown['checks'])

    def test_an_eus_code_that_includes_no_upper_endoscopy_is_never_said_to_include_it(self):
        encounter_id = self.stored(EUS_WITH_EGD, ('45342', FNA))
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('warn', MISSED_EGD))
        draft = self.txt(encounter_id)
        self.assertIn('read as part of S1, but no selected code of that service includes this examination', draft)
        self.assertNotIn("included in S1: that service's code includes this examination", draft)
        shown = screen(self.detail(encounter_id))
        self.assertIn('Read as part of S1, but no selected code of that service includes this examination.',
                      shown['codes'] + shown['checks'])
        self.assertNotIn("Included in S1: that service's code includes this examination",
                         shown['codes'] + shown['checks'])

    def test_control_an_egd_with_eus_code_still_includes_the_egd(self):
        encounter_id = self.stored(EUS_WITH_EGD, ('43242', FNA))
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('pass', checks.UNPROPOSED_PASS))
        draft = self.txt(encounter_id)
        self.assertIn("included in S1: that service's code includes this examination", draft)
        self.assertNotIn('read as part of', draft)
        shown = screen(self.detail(encounter_id))
        self.assertIn("Included in S1: that service's code includes this examination, so no code of its own is asked.",
                      shown['codes'] + shown['checks'])
