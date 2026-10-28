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
- EUS lens 2 (engine._second_review): an EGD-with-EUS code the bounded second review selected for the EGD the primary
  proposals left listed was kept as an alternative that "accounts for no documented service or act the primary
  proposals left unresolved": the merge accepted a code for an open item only inside the item's own family.
- ROLLBACK lens 0 (ops/install.py UNDO_HAZARDS, SHOWN_HAZARDS): an encounter whose second review's outcome is unknown,
  beside a primary answer that proposes nothing, was put back to the installed revision's no_codes and handed over,
  and 057a7d39 then said that no code was proposed beside a request that was sent and that nobody read.
"""
import dataclasses
from unittest import mock

from django.test import SimpleTestCase

from studio import jobs, models, review
from studio.gi.profiles import PROFILES
from studio.providers import ProviderUnavailable
from studio.types import NormalizedResponse
from studio.validation import checks
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_7c8_p1reports import Harness
from tests.test_repairs_7c8_p2install import BANNER, SNARE, VISIT, WEB, WORKER
from tests.test_repairs_7c8_p2install import REPORT as P2_REPORT
from tests.test_repairs_7c8_p2install import Base as P2Base
from tests.test_repairs_7c8_p2install import Provider as P2Provider
from tests.test_repairs_7c8_p2reports import (EGD_LABEL, EGD_WITH_EUS_CODES, EGD_WITH_LIMITED_EUS, EUS_WITH_EGD,
                                              EVERY_DETECTED, FNA, LIMITED_EUS, NO_EGD_PROPOSAL, screen, unproposed,
                                              unresolved_items)
from tests.test_services_reconcile import run, sel, span
from tests.test_repairs_r1_m import install, run_app_script
from tests.test_services_second_review import TwoPassProvider

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


# --- EUS lens 2: a code the second review selects that includes the unresolved service's examination accounts for it -

LIMITED_TITLE = 'Upper endoscopy with limited endoscopic ultrasound'
NOT_ADDED = 'it accounts for no documented service or act the primary proposals left unresolved'
EGD_AND_EUS_DONE = SYNTHETIC + 'Date of service: 2026-10-14\nEGD and EUS were performed.\n'  # the verifier's smallest
DONE_LINE = 'EGD and EUS were performed'


def second_review(text, code, quote):
    return NormalizedResponse('replay', 'test@1', (sel(code, span(text, quote)),))


class ASecondReviewCodeThatIncludesTheExaminationAccountsForItTests(SimpleTestCase):
    """EUS lens 2 (verified must-fix, class 3; not pre-existing at 057a7d398, which had no second review): the primary
    answer selects an esophagoscopy EUS code (43231), which includes no upper endoscopy, so the EGD read as the EUS's
    endoscopic portion is listed without a proposal and offered for the bounded second review. That review selects an
    EGD-with-EUS code (43237, 43259), which includes the EGD - yet the merge accepted a code for an open item only inside
    the item's own family, so it stored the code as a never-selectable alternative "not added as a proposal: it accounts
    for no documented service or act the primary proposals left unresolved", left the EGD listed, and used up the one
    second review. A whole service read as part of another is accounted for by a code of that service that includes its
    examination (reconcile.includes_through), as the reconciliation reads it once the code is selected."""

    def test_a_code_that_includes_the_listed_egd_is_added_for_it(self):
        for text, primary, quote in ((EGD_WITH_LIMITED_EUS, LIMITED_EUS, LIMITED_TITLE),
                                     (EGD_AND_EUS_DONE, DONE_LINE, DONE_LINE)):
            first = run(text, [sel('43231', span(text, primary))])
            self.assertEqual([(u[0], u[2]) for u in unresolved_items(first)], [('S1', 'no_proposal')])
            for code in ('43237', '43259'):
                with self.subTest(code=code, text=text[67:110]):
                    result = run(text, [sel('43231', span(text, primary))], second=second_review(text, code, quote),
                                 second_scope={'items': [NO_EGD_PROPOSAL]})
                    (added,) = [p for p in result.proposals if p.code == code and p.bucket != 'alternative']
                    self.assertEqual((added.bucket, added.support['origin']), ('selected', 'second_review'))
                    self.assertFalse([p for p in result.proposals if p.bucket == 'alternative'])
                    self.assertFalse(any(NOT_ADDED in (p.rationale or '') for p in result.proposals))
                    self.assertEqual(unresolved_items(result), [])
                    self.assertEqual((unproposed(result).status, unproposed(result).detail),
                                     ('pass', checks.UNPROPOSED_PASS))
                    review = next(c for c in result.encounter_checks if c.id == 'provider.second_review')
                    self.assertEqual(review.status, 'info')
                    self.assertIn(f'selected {code}, which accounts for {NO_EGD_PROPOSAL} and is added as a proposal',
                                  review.detail)

    def test_controls_the_egds_own_code_is_added_and_a_code_that_includes_none_stays_an_alternative(self):
        text = EGD_WITH_LIMITED_EUS
        result = run(text, [sel('43231', span(text, LIMITED_EUS))], second=second_review(text, '43235', LIMITED_TITLE),
                     second_scope={'items': [NO_EGD_PROPOSAL]})
        self.assertEqual([(p.code, p.bucket) for p in result.proposals if p.code == '43235'], [('43235', 'selected')])
        self.assertEqual(unresolved_items(result), [])
        for code in ('45342', '43232'):  # an EUS code that includes no upper endoscopy accounts for none
            with self.subTest(code=code):
                result = run(text, [sel('43231', span(text, LIMITED_EUS))],
                             second=second_review(text, code, LIMITED_TITLE), second_scope={'items': [NO_EGD_PROPOSAL]})
                (listed,) = [p for p in result.proposals if p.code == code]
                self.assertEqual(listed.bucket, 'alternative')
                self.assertIn(NOT_ADDED, listed.rationale)
                self.assertEqual([(u[0], u[2]) for u in unresolved_items(result)], [('S1', 'no_proposal')])


class TheSecondReviewsIncludingCodeThroughTheApiTests(Harness):
    """EUS lens 2 through the API, as its verifier ran it: the reviewer asks for the second review the encounter offers
    for the listed EGD (201), the job is drained, and the code it selects that includes the EGD is a proposal marked as
    from the second review - in the stored rows, the draft TXT and the Codes tab - never an alternative said to account
    for nothing."""

    def test_the_code_is_a_proposal_on_every_surface(self):
        self.use(TwoPassProvider(first=[('43231', LIMITED_EUS)], later=[('43237', LIMITED_TITLE)]))
        encounter_id = self.create(EGD_WITH_LIMITED_EUS)
        drain()
        offered = self.detail(encounter_id)['second_review']
        self.assertTrue(offered['available'], offered)
        self.assertEqual(offered['items'], [NO_EGD_PROPOSAL])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.requests), 2)
        assessment = self.assessment(encounter_id)
        proposals = {(p.code, p.bucket): p for p in assessment.proposals.all()}
        self.assertIn(('43237', 'selected'), proposals)
        self.assertEqual(proposals[('43237', 'selected')].support.get('origin'), 'second_review')
        self.assertNotIn(('43237', 'alternative'), proposals)
        self.assertEqual([u['service'] for u in assessment.completeness['unresolved_items']], [])
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('pass', checks.UNPROPOSED_PASS))
        draft = self.txt(encounter_id)
        self.assertNotIn(NOT_ADDED, draft)
        self.assertIn('43237', draft)
        shown = screen(self.detail(encounter_id))
        self.assertNotIn(NOT_ADDED, shown['codes'])
        self.assertIn('43237', shown['codes'])


# --- ROLLBACK lens 0: a second review the shown assessment did not read is named, never handed to an older revision ---

BIOPSY = ('45380', 'was sampled with cold biopsy forceps')


class ExcerptNotBuilt(P2Provider):
    """A request for anything but the whole document (the bounded second review's excerpt) cannot be built: that run is
    recorded as not sent, and nothing is sent."""

    def build_request(self, text, service_date):
        if not text.startswith(BANNER):
            raise ProviderUnavailable('The excerpt cannot be sent (synthetic stand-in for an adapter refusal).')
        return super().build_request(text, service_date)


class AnUnreadSecondReviewIsNamedNeverHandedOverTests(P2Base):
    """ROLLBACK lens 0 (verified must-fix, class 3 reached through a class 5 path; not pre-existing at 057a7d398, which
    has no second review): the bounded second review a reviewer asked for over a primary answer that proposes nothing
    was sent and its outcome is unknown; a member reconciled it, and the re-assessment reads the primary answer alone.
    This revision lists it 'Second review outcome unknown', with the blocker 'No CPT code was proposed in the response
    that was read; the second review has an unknown outcome'. rollback-app, and the failure path of `app`, put it back
    to 057a7d39's own derivation (no_codes) and handed the rows over - and 057a7d39, which reads no second review, then
    listed 'No CPT codes proposed' with the blocker 'No CPT code was proposed' and the page 'No CPT codes were proposed
    for this document.' beside a request that was sent and may have proposed codes nobody read (measured with its real
    code by the verifier; every state it could be handed says the same). Such an encounter is named instead
    ('second_review_unread', a SHOWN_HAZARDS reason, as a response refused whole is): rollback-app refuses before
    stopping anything, and the failure path of `app` leaves the new pair stopped and the previous pair parked. A second
    review that failed or was never sent proposed nothing, so 057a7d39's "no code was proposed" is true of those rows:
    they are put back as before. The live installation's shape is neither refused nor altered
    (RefusedResponseHandedBackTests.test_controls_a_copy_of_the_live_installation_has_nothing_to_put_back)."""

    def asked(self, tag, outcome, *, reconcile=False, primary=(VISIT,), provider=None):
        """A report whose primary answer (HTTP 200) names only the ``primary`` quotes the report holds - none for VISIT
        alone - then the bounded second review a reviewer asks for, ending ``outcome``; a member reconciles an unknown
        one when ``reconcile``, and the re-assessment reads the primary answer again (reused, nothing sent)."""
        if provider is not None:
            self.provider = provider
            patcher = mock.patch('studio.jobs.get_provider', return_value=provider)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.provider.first, self.provider.later = list(primary), list(primary)
        encounter_id = self.create(tag, text=P2_REPORT)
        self.assertTrue(self.client.get(f'/api/encounters/{encounter_id}').json()['second_review']['available'])
        self.provider.outcomes = [outcome]
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        drain()
        if reconcile:
            run = models.ProviderRun.objects.get(encounter_id=encounter_id, state=models.ProviderRun.UNKNOWN,
                                                 reconciled_at__isnull=True)
            sent = self.sent()
            reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                              {'provider_run_id': str(run.pk), 'note': 'Checked the provider console (synthetic).'})
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
            self.assertEqual(self.sent(), sent)  # the primary answer is reused
        return encounter_id

    def hazards(self):
        return run_app_script(install.UNDO_HAZARDS_READ, {})['hazards']

    def close(self):
        since = models.Job.objects.order_by('-created_at').first().created_at.isoformat()
        return run_app_script(install.CLOSE_STAGES, {'since': since, 'note': 'Closed (synthetic).',
                                                     'kinds': list(install.COMMON_STAGE_KINDS)})

    def test_the_read_and_the_close_name_a_reconciled_unknown_outcome_until_an_addendum(self):
        unknown = self.asked('UK', 'unknown', reconcile=True)
        self.assertEqual(self.listed(unknown), ('no_codes', 'Second review outcome unknown'))
        self.assertIn('No CPT code was proposed in the response that was read; the second review has an unknown '
                      'outcome', review.readiness(self.encounter(unknown))['blockers'])
        self.assertEqual(self.hazards(), {unknown: ['second_review_unread']})
        closed = self.close()
        self.assertEqual(closed['hazards'], {unknown: ['second_review_unread']})
        self.assertIn(unknown, closed['relabel'])
        # cleared as ops/INSTALL.md says: an addendum - a newer revision, whose own request is sent and whose
        # assessment has no second review made for its answer until one is asked for
        sent = self.sent()
        reply = self.post(f'/api/encounters/{unknown}/addenda', {'text': 'Addendum (synthetic): no change to the plan.',
                                                                 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.sent(), sent + 1)
        self.assertIsNone(review._unread_second_review(self.encounter(unknown).current_assessment))
        self.assertEqual(self.hazards(), {})

    def test_an_unreconciled_unknown_outcome_is_named_too(self):
        # 057a7d39's blocker says 'No CPT code was proposed' beside it as well; it is also an outcome its worker would
        # reconcile under its own rules ('unknown')
        unknown = self.asked('UU', 'unknown')
        self.assertEqual(self.encounter(unknown).state, 'provider_unknown')
        self.assertEqual(self.hazards(), {unknown: ['second_review_unread', 'unknown']})

    def test_a_second_review_answered_and_not_read_yet_is_named_too(self):
        # the second review succeeded - its answer names the biopsy's code - and the assessment it queued was stopped
        # before it ran: the shown assessment is the one before it, with nothing to decide, beside which 057a7d39's
        # blocker and page would say that no code was proposed
        self.provider.first, self.provider.later = [VISIT], [VISIT, BIOPSY]
        encounter_id = self.create('RN', text=P2_REPORT)
        self.assertTrue(self.client.get(f'/api/encounters/{encounter_id}').json()['second_review']['available'])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.REVIEW2)
        jobs.run_job(job)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.state, 'stopped')
        second = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose=models.ProviderRun.SECOND_REVIEW)
        self.assertEqual((second.state, second.http_status), (models.ProviderRun.SUCCEEDED, 200))
        self.assertEqual(review._unread_second_review(encounter.current_assessment).pk, second.pk)
        self.assertIn('No CPT code was proposed in the response that was read; the second review has not been read yet',
                      review.readiness(encounter)['blockers'])
        self.assertEqual(self.hazards(), {encounter_id: ['second_review_unread']})

    def test_controls_a_second_review_that_failed_or_was_never_sent_is_put_back_as_before(self):
        # it proposed nothing, so what 057a7d39 says of the rows - no code was proposed - is true; a second review
        # unread beside a code to decide is never named either: 057a7d39 shows that code
        failed = self.asked('FL', 'failed')
        self.assertEqual(self.listed(failed), ('no_codes', 'Second review failed'))
        decided = self.asked('DC', 'unknown', reconcile=True, primary=(VISIT, SNARE))
        self.assertNotIn(self.encounter(decided).state, ('no_codes', 'provider_failed'))
        not_sent = self.asked('NS', 'none', provider=ExcerptNotBuilt(first=[VISIT], later=[VISIT]))
        self.assertEqual(self.listed(not_sent), ('no_codes', 'Second review not sent'))
        self.assertEqual(self.hazards(), {})
        closed = self.close()
        self.assertEqual(closed['hazards'], {})
        self.assertEqual(sorted(closed['relabel']), sorted([failed, not_sent]))
        answer, world = self.rollback()
        self.assertNotIsInstance(answer, install.InstallError, answer)
        self.assertEqual(answer['states_put_back'], {'encounters': 2, 'changed': {}})  # 057a7d39's no_codes, as stored
        self.assertEqual({self.encounter(pk).state for pk in (failed, not_sent)}, {'no_codes'})

    def test_rollback_app_refuses_naming_it_before_anything_is_stopped(self):
        unknown = self.asked('UK', 'unknown', reconcile=True)
        sent = self.sent()
        for parked in (None, 'installed', 'same'):
            with self.subTest(parked=parked):
                error, world = self.rollback(parked=parked)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn('nothing was stopped or removed', str(error))
                self.assertIn('1 encounter(s): second_review_unread 1', str(error))
                self.assertEqual(error.details['hazards'], {unknown: ['second_review_unread']})
                self.assertFalse([call for call in world.calls if call[0] in ('stop', 'rm')])
                self.assertEqual([call[2] for call in world.calls if call[0] == 'script'], ['UNDO_HAZARDS_READ'])
                self.assertEqual(self.listed(unknown), ('no_codes', 'Second review outcome unknown'))
        self.assertEqual(self.sent(), sent)

    def test_the_failure_path_leaves_the_new_pair_stopped_and_the_previous_pair_parked(self):
        unknown = self.asked('UK', 'unknown', reconcile=True)
        sent = self.sent()
        error, world = self.fail_install('installed')
        message = str(error)
        self.assertIn('cpt-studio-worker did not become ready', message)
        self.assertIn('1 encounter(s): second_review_unread 1', message)
        self.assertIn('the new pair was left stopped and the previous pair parked', message)
        self.assertEqual(error.details['hazards'], {unknown: ['second_review_unread']})
        self.assertEqual(world.ids(), {WEB + '-previous': 'old-web', WORKER + '-previous': 'old-worker',
                                       WEB: 'new-web', WORKER: 'new-worker'})
        self.assertFalse([call for call in world.calls if call[0] in ('start', 'rm')])
        self.assertFalse([call for call in world.calls if call[0] == 'script'
                          and call[2] in ('RECOMPUTE_STATES', 'INSTALLED_STATES')])  # nothing was put back
        self.assertEqual(self.listed(unknown), ('no_codes', 'Second review outcome unknown'))
        self.assertEqual(self.sent(), sent)

    def test_controls_a_same_revision_re_runs_failure_path_restores_its_pair_as_before(self):
        unknown = self.asked('UK', 'unknown', reconcile=True)
        error, world = self.fail_install('same')
        self.assertIn('cpt-studio-worker did not become ready', str(error))
        self.assertNotIn('left stopped', str(error))
        self.assertEqual(world.ids(), {WEB: 'old-web', WORKER: 'old-worker'})
        self.assertEqual(sorted(call[1] for call in world.calls if call[0] == 'start'), sorted((WEB, WORKER)))
        self.assertEqual(self.listed(unknown), ('no_codes', 'Second review outcome unknown'))
