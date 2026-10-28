"""Continuation round 7c8, the re-attack of the phase-2 fix rounds (P2RA) on the integrated head a62a18c85: each class
reproduces a finding a refutation lens demonstrated and an independent verifier reproduced, with its smallest input,
and asserts what is true of the persisted state beside a control that must not change. Synthetic data only; the
provider is an in-process fake (no network).

- EUS lens 0 (engine._accounted_elsewhere): services.unproposed passed - "Every performed service that routing detected
  in the document has a selected proposal" - beside a performed push enteroscopy with no proposal, because the EGD
  inside the EUS, which an EGD-with-EUS code includes, made the whole upper GI ROUTING family read as accounted for,
  and routing reads an enteroscopy under that family (gi-profiles@3 carved it out; engine.LEGACY_FAMILIES).
- EUS lens 1 (reports._documented_section, app.js documentedServices): an EGD with its own code beside an EUS whose
  selected code includes no upper endoscopy read "included in S2: that service's code includes this examination" (and
  "... so no code of its own is asked"): the line tested whether the reconciliation listed the EGD, not the inclusion
  rule.
"""
import dataclasses
from unittest import mock

from django.test import SimpleTestCase

from studio import jobs
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


# --- EUS lens 1: the documented services' inclusion line follows the inclusion rule itself ----------------------------

GASTROSCOPE = 'The gastroscope was advanced to the second portion of the duodenum'
NODE_FNA = 'was sampled by fine-needle aspiration with two passes'
EGD_AND_LOWER_EUS = (SYNTHETIC + 'Date of service: 2026-10-14\nIndication: dyspepsia; perirectal lymph node.\n'
                     'Procedures: EGD and lower EUS.\n'
                     'EGD: ' + GASTROSCOPE + ' and the examination was completed. The upper examination was normal.\n'
                     'Lower EUS: The echoendoscope was introduced. A 9 mm perirectal lymph node ' + NODE_FNA + '.\n')
EGD_AND_PANCREAS_EUS = (SYNTHETIC + 'Date of service: 2026-10-14\nIndication: dyspepsia; pancreatic head mass.\n'
                        'Procedures: EGD and EUS.\n'
                        'EGD: ' + GASTROSCOPE + ' and the examination was completed. The upper examination was normal.\n'
                        'EUS: The echoendoscope was advanced to the second portion of the duodenum. A 2 cm pancreatic '
                        'head mass ' + FNA + '.\n')
SAMPLED_NODE = 'was sampled by fine-needle aspiration'
EGD_AND_EUS_SMALLEST = (SYNTHETIC + 'Date of service: 2026-10-14\nEGD: ' + GASTROSCOPE + '.\n'
                        'EUS: A lymph node ' + SAMPLED_NODE + '.\n')  # the verifier's smallest input
INCLUDED_TXT = "included in S2: that service's code includes this examination"
INCLUDED_PAGE = "Included in S2: that service's code includes this examination, so no code of its own is asked."
NOT_INCLUDED_TXT = 'read as part of S2, but no selected code of that service includes this examination'
NOT_INCLUDED_PAGE = 'Read as part of S2, but no selected code of that service includes this examination.'


class TheInclusionLineFollowsTheInclusionRuleTests(Harness):
    """EUS lens 1 (verified must-fix, class 3; not pre-existing at 057a7d398, which has no documented-services section):
    an EGD with its own code beside an EUS whose selected code includes no upper endoscopy - 43235 with 45342 or 43232,
    the correct pair - read "included in S2: that service's code includes this examination" in the stored TXT, and "...
    so no code of its own is asked" on the page, beside the approved 43235: the line tested whether the reconciliation
    listed the EGD, not whether a selected code of the EUS includes it. It is worded from the inclusion rule itself, the
    test reconcile.inclusion_asks_no_code reads (catalogue.includes_examination over the including service's selected,
    non-excluded codes), recorded with the assessment (completeness.included_by)."""

    def stored(self, text, *selections):
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def test_a_code_of_the_eus_that_includes_no_upper_endoscopy_is_never_said_to_include_it(self):
        for text, egd, eus, code in ((EGD_AND_LOWER_EUS, GASTROSCOPE, NODE_FNA, '45342'),
                                     (EGD_AND_PANCREAS_EUS, GASTROSCOPE, FNA, '43232'),
                                     (EGD_AND_PANCREAS_EUS, GASTROSCOPE, FNA, '45342'),
                                     (EGD_AND_EUS_SMALLEST, GASTROSCOPE, SAMPLED_NODE, '45342'),
                                     (EGD_AND_EUS_SMALLEST, GASTROSCOPE, SAMPLED_NODE, '43232')):
            with self.subTest(code=code, text=text[67:120]):
                self.fresh(f'Synthetic workspace {code} {len(text)}')
                encounter_id = self.stored(text, ('43235', egd), (code, eus))
                assessment = self.assessment(encounter_id)
                self.assertEqual([(s['id'], s['family'], s['included_in']) for s in assessment.services['services']],
                                 [('S1', 'gi.egd', 'S2'), ('S2', 'gi.eus', '')])
                for selected in ('43235', code):
                    self.decide(encounter_id, selected, 'approve')
                reply = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
                self.assertEqual(reply.status_code, 201, reply.content)
                reviewed = self.txt(encounter_id, 'reviewed')
                self.assertIn(f'accounted for by: 43235\n      {NOT_INCLUDED_TXT}\n', reviewed)
                self.assertNotIn("that service's code includes this examination", reviewed)
                shown = screen(self.detail(encounter_id))
                self.assertIn(f'Accounted for by: 43235. {NOT_INCLUDED_PAGE}', shown['codes'] + shown['checks'])
                self.assertNotIn('no code of its own is asked', shown['codes'] + shown['checks'])

    def test_controls_a_code_that_includes_the_egd_keeps_the_inclusion_line(self):
        # 43242 alone, and 43242 beside the EGD's own 43235 (the r1 missed-14 shape): the EUS's code includes the EGD
        for selections in ((('43242', FNA),), (('43235', GASTROSCOPE), ('43242', FNA))):
            with self.subTest(codes=[code for code, _ in selections]):
                self.fresh(f'Synthetic workspace {len(selections)}')
                encounter_id = self.stored(EGD_AND_PANCREAS_EUS, *selections)
                draft = self.txt(encounter_id)
                self.assertIn(INCLUDED_TXT, draft)
                self.assertNotIn('read as part of', draft)
                shown = screen(self.detail(encounter_id))
                self.assertIn(INCLUDED_PAGE, shown['codes'] + shown['checks'])

    def test_an_eus_with_no_code_is_never_said_to_have_one_that_includes_the_egd(self):
        # the EGD's own code alone: the EUS has no selected code (it is listed itself), so none of its codes includes
        # the EGD - never "that service's code includes this examination" about a service with no code
        encounter_id = self.stored(EGD_AND_PANCREAS_EUS, ('43235', GASTROSCOPE))
        draft = self.txt(encounter_id)
        self.assertIn(f'accounted for by: 43235\n      {NOT_INCLUDED_TXT}\n', draft)
        self.assertNotIn("that service's code includes this examination", draft)
        shown = screen(self.detail(encounter_id))
        self.assertIn(NOT_INCLUDED_PAGE, shown['codes'] + shown['checks'])
        self.assertNotIn("that service's code includes this examination", shown['codes'] + shown['checks'])

    def test_an_assessment_that_recorded_no_inclusion_states_the_reading_alone(self):
        # an assessment stored before completeness.included_by existed (assessments are immutable: one is made by the
        # engine of that time, which recorded no such key): the line states what the rows hold - the inventory read the
        # EGD as part of the EUS - and nothing about a code
        real = jobs.run_assessment

        def earlier(**kwargs):
            result = real(**kwargs)
            completeness = {k: v for k, v in result.completeness.items() if k != 'included_by'}
            return dataclasses.replace(result, completeness=completeness)
        with mock.patch('studio.jobs.run_assessment', earlier):
            encounter_id = self.stored(EGD_AND_PANCREAS_EUS, ('43242', FNA))
        self.assertNotIn('included_by', self.assessment(encounter_id).completeness)
        draft = self.txt(encounter_id)
        self.assertIn('      read as part of S2\n', draft)
        self.assertNotIn('includes this examination', draft)
        shown = screen(self.detail(encounter_id))
        self.assertIn('Read as part of S2.', shown['codes'] + shown['checks'])
        self.assertNotIn('includes this examination', shown['codes'] + shown['checks'])

    def test_the_assessment_records_which_selected_codes_include_the_examination(self):
        # completeness.included_by: the included service -> the selected, non-excluded codes of the service it is read
        # as part of that include its examination, as the reconciliation read them
        for selections, included_by in (((('43235', GASTROSCOPE), ('45342', FNA)), {'S1': []}),
                                        ((('43235', GASTROSCOPE),), {'S1': []}),
                                        ((('43235', GASTROSCOPE), ('43242', FNA)), {'S1': ['43242']}),
                                        ((('43242', FNA), ('45342', FNA)), {'S1': ['43242']})):
            with self.subTest(codes=[code for code, _ in selections]):
                result = run(EGD_AND_PANCREAS_EUS, [sel(code, span(EGD_AND_PANCREAS_EUS, quote))
                                                    for code, quote in selections])
                self.assertEqual(result.completeness['included_by'], included_by)
        result = run(EGD_AND_LOWER_EUS.replace('Lower EUS: The echoendoscope was introduced.',
                                               'Lower EUS: The echoendoscope was introduced into the rectum.'),
                     [sel('45342', span(EGD_AND_LOWER_EUS, NODE_FNA))])
        self.assertEqual(result.completeness['included_by'], {})  # a rectal EUS includes no upper endoscopy
