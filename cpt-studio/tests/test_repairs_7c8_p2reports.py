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
