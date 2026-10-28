"""Continuation round 7c8, the re-attack of the phase-2 fix rounds (P2RA) on the integrated head a62a18c85: each class
reproduces a finding a refutation lens demonstrated and an independent verifier reproduced, with its smallest input,
and asserts what is true of the persisted state beside a control that must not change. Synthetic data only; the
provider is an in-process fake (no network).

- EUS lens 0 (engine._accounted_elsewhere): services.unproposed passed - "Every performed service that routing detected
  in the document has a selected proposal" - beside a performed push enteroscopy with no proposal, because the EGD
  inside the EUS, which an EGD-with-EUS code includes, made the whole upper GI ROUTING family read as accounted for,
  and routing reads an enteroscopy under that family (gi-profiles@3 carved it out; engine.LEGACY_FAMILIES).
"""
from django.test import SimpleTestCase

from studio.gi.profiles import PROFILES
from studio.validation import checks
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_7c8_p1reports import Harness
from tests.test_repairs_7c8_p2reports import (EGD_LABEL, EGD_WITH_EUS_CODES, EUS_WITH_EGD, EVERY_DETECTED, FNA,
                                              screen, unproposed, unresolved_items)
from tests.test_services_reconcile import run, sel, span

SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'


# --- EUS lens 0: a performed service routing reads under a family an included EGD belongs to is still named ----------

ENTEROSCOPY_BESIDE_EUS = (SYNTHETIC + 'Date of service: 2026-10-14\n'
                          'Indication: pancreatic head mass; iron deficiency anemia.\n'
                          'Procedures: EGD, upper endoscopic ultrasound and push enteroscopy.\n'
                          'EGD: The gastroscope was advanced to the second portion of the duodenum and the examination '
                          'was completed.\n'
                          'EUS: The echoendoscope was advanced to the second portion of the duodenum. A 2 cm hypoechoic '
                          'mass in the pancreatic head ' + FNA + '.\n'
                          'Push enteroscopy: The enteroscope was advanced to the proximal jejunum. No bleeding source '
                          'was found.\n')
ENTEROSCOPY_LINE = SYNTHETIC + 'Procedures: EGD, EUS and push enteroscopy.\n'  # the verifier's smallest input
SAMPLED = 'A pancreatic mass was sampled by fine-needle aspiration.'
ENTEROSCOPY_REVIEWABLE = (SYNTHETIC + 'Date of service: 2026-10-14\nProcedures: EGD, EUS and push enteroscopy.\n'
                          + SAMPLED + '\n')
ENTEROSCOPE = 'The enteroscope was advanced to the proximal jejunum'
ENTEROSCOPY_LABEL = PROFILES['gi.enteroscopy'].label
MISSED_ENTEROSCOPY = (f'Possible missed service: {ENTEROSCOPY_LABEL} is documented as performed with no selected '
                      'proposal.')
NO_ENTEROSCOPY_PROPOSAL = 'enteroscopy (documented as performed) has no supported proposal'


class AnEnteroscopyBesideAnEgdInsideAnEusIsNamedTests(SimpleTestCase):
    """EUS lens 0 (verified must-fix, class 3; not pre-existing at 057a7d398, which warned "Possible missed service:
    Upper GI endoscopy (EGD, esophagoscopy, enteroscopy) ..."): an EGD, an upper EUS and a push enteroscopy, with only an
    EGD-with-EUS code selected. The code includes the EGD, so _accounted_elsewhere read the upper GI family as accounted
    for - by the inventory's own family, gi.egd, which holds the EGD alone - and _missed skipped the whole ROUTING family
    of that name, which also reads the enteroscopy. A routing family is accounted for elsewhere only when every service
    done today that routing reads under it (engine.legacy_family) is; when only some are, what is left is named - the
    enteroscopy, never the examination the code includes."""

    def test_the_enteroscopy_is_named_beside_every_code_that_includes_the_egd(self):
        for text, quote in ((ENTEROSCOPY_BESIDE_EUS, FNA), (ENTEROSCOPY_LINE, 'EUS')):
            for code in EGD_WITH_EUS_CODES:
                with self.subTest(code=code, text=text[67:110]):
                    result = run(text, [sel(code, span(text, quote))])
                    including = {s['id']: (s['family'], s['included_in']) for s in result.services['services']}
                    self.assertEqual(including, {'S1': ('gi.egd', 'S2'), 'S2': ('gi.eus', ''),
                                                 'S3': ('gi.enteroscopy', '')})
                    check = unproposed(result)
                    self.assertEqual((check.status, check.detail), ('warn', MISSED_ENTEROSCOPY))
                    self.assertNotIn(EVERY_DETECTED, check.detail)
                    self.assertNotIn(EGD_LABEL, check.detail)  # the EGD the code includes is accounted for
                    self.assertIn(('S3', '', 'no_proposal', NO_ENTEROSCOPY_PROPOSAL), unresolved_items(result))

    def test_control_its_own_enteroscopy_code_beside_passes(self):
        text = ENTEROSCOPY_BESIDE_EUS
        for code in ('44376', '44360'):
            with self.subTest(code=code):
                result = run(text, [sel('43242', span(text, FNA)), sel(code, span(text, ENTEROSCOPE))])
                self.assertEqual((unproposed(result).status, unproposed(result).detail),
                                 ('pass', checks.UNPROPOSED_PASS))

    def test_control_an_egd_inside_an_eus_with_no_enteroscopy_still_passes(self):
        result = run(EUS_WITH_EGD, [sel('43242', span(EUS_WITH_EGD, FNA))])
        self.assertEqual((unproposed(result).status, unproposed(result).detail), ('pass', checks.UNPROPOSED_PASS))

    def test_control_with_no_code_for_the_eus_the_upper_family_is_named_as_before(self):
        # nothing is accounted for elsewhere: the routing family is named by its own label, as before this repair
        result = run(ENTEROSCOPY_LINE, [])
        self.assertEqual(unproposed(result).detail, f'Possible missed service: {EGD_LABEL} and '
                         f'{PROFILES["gi.eus"].label} are documented as performed with no selected proposal.')


class TheReportsNameTheEnteroscopyTests(Harness):
    """EUS lens 0 through the API, as its verifier ran it: the stored check, the draft TXT, the Checks tab and - once the
    reviewer approves the EGD-with-EUS code - the reviewed TXT name the enteroscopy; none says that every performed
    service routing detected has a selected proposal."""

    def test_every_surface_names_the_enteroscopy(self):
        self.use(FakeProvider(selections=[('43242', SAMPLED)]))
        encounter_id = self.create(ENTEROSCOPY_REVIEWABLE)
        drain()
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('warn', MISSED_ENTEROSCOPY))
        draft = self.txt(encounter_id)
        self.assertIn(f'[WARN] services.unproposed — Performed services without a proposal: {MISSED_ENTEROSCOPY}',
                      draft)
        self.assertNotIn(EVERY_DETECTED, draft)
        shown = screen(self.detail(encounter_id))
        self.assertIn(MISSED_ENTEROSCOPY, shown['checks'])
        self.assertNotIn(EVERY_DETECTED, shown['checks'])
        self.decide(encounter_id, '43242', 'approve')
        reply = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertEqual(reply.status_code, 201, reply.content)
        reviewed = self.txt(encounter_id, 'reviewed')
        self.assertIn(f'[WARN] services.unproposed — Performed services without a proposal: {MISSED_ENTEROSCOPY}',
                      reviewed)
        self.assertNotIn(EVERY_DETECTED, reviewed)
