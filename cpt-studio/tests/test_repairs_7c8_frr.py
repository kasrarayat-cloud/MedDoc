"""Continuation round 7c8, the final refutation of the phase-2 repairs (P2FR), reports track: each class reproduces a
finding a refutation lens demonstrated on the integration head c3c034a08 and an independent verifier reproduced, with
its smallest input, and asserts what is true of the persisted state beside a control that must not change. Synthetic
data only; the provider is an in-process fake (no network).

- EUS-SECOND 0 (engine._accounted_elsewhere): services.unproposed passed - "Every performed service that routing
  detected in the document has a selected proposal" - beside a push enteroscopy routing reads as performed under the
  upper GI family, because the documented-service reading held that enteroscopy as uncertain and only the services it
  read as done today were counted: the EGD inside the EUS, which the selected EGD-with-EUS code includes, made the
  whole routing family read as accounted for.
- EUS-SECOND 1 and 2 (review.reviewed_completeness): an excluded code the reviewer reinstated and approved was ignored by
  every documented-service statement - the inclusion line, "accounted for by", the unresolved items, coding
  completeness and the second review's offer were worded from the non-excluded codes the assessment counted.
- EUS-SECOND 3 (reports._services, app.js documentedServices): a code the reviewer rejected still made the included EGD
  read "included in S2: that service's code includes this examination".
"""
from django.test import SimpleTestCase

from studio.gi.profiles import PROFILES
from studio.validation import checks
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_7c8_p1reports import Harness, section
from tests.test_repairs_7c8_p2reports import EGD_LABEL, EVERY_DETECTED, screen, unproposed
from tests.test_services_reconcile import run, sel, span
from tests.test_services_second_review import TwoPassProvider

SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'


# --- EUS-SECOND 0: a service routing reads as performed under a family is accounted for only by what includes it -----

FNA3 = 'was sampled by fine-needle aspiration with three passes'
HEAD = SYNTHETIC + 'Date of service: 2026-10-14\nIndication: pancreatic head mass; iron deficiency anemia.\n'
EUS_PART = ('EUS: The echoendoscope was advanced to the second portion of the duodenum. A 2 cm pancreatic head mass '
            + FNA3 + '.\n')
EGD_PART = 'EGD: The gastroscope was advanced to the second portion of the duodenum.\n'
# (a) the enteroscopy names the EGD's own section; (b) a hedged sentence of its own (the lens's two texts)
ENTEROSCOPY_IN_THE_EGD_HEADING = (HEAD + 'Procedures: EGD and EUS.\nEGD with push enteroscopy: The gastroscope was '
                                  'advanced to the proximal jejunum. No bleeding source was found.\n' + EUS_PART)
ENTEROSCOPY_HEDGED = (HEAD + 'Procedures: EGD and EUS.\n' + EGD_PART + EUS_PART
                      + 'A push enteroscopy to the proximal jejunum was also performed, possibly incomplete.\n')
SAMPLED = 'sampled by fine-needle aspiration'
ENTEROSCOPY_SMALLEST = (SYNTHETIC + 'Date of service: 2026-10-14\nProcedures: EGD and EUS.\n'
                        'A pancreatic mass was sampled by fine-needle aspiration.\n'
                        'Push enteroscopy was performed, possibly incomplete.\n')  # the verifier's smallest input
# controls: routing itself holds the enteroscopy; no enteroscopy at all; one both readers read as performed
ENTEROSCOPY_POSSIBLY = (HEAD + 'Procedures: EGD and EUS.\n' + EGD_PART + EUS_PART
                        + 'A push enteroscopy was possibly performed.\n')
NO_ENTEROSCOPY = HEAD + 'Procedures: EGD and EUS.\n' + EGD_PART + EUS_PART
ENTEROSCOPY_OWN_LINE = (HEAD + 'Procedures: EGD, EUS and push enteroscopy.\n' + EGD_PART + EUS_PART
                        + 'Push enteroscopy: The enteroscope was advanced to the proximal jejunum. No bleeding source '
                          'was found.\n')
ENTEROSCOPY_LABEL = PROFILES['gi.enteroscopy'].label
MISSED_ENTEROSCOPY = (f'Possible missed service: {ENTEROSCOPY_LABEL} is documented as performed with no selected '
                      'proposal.')


def routed(text):
    """The routing families and their mentions as routing reads them (status, text), through the engine's own run."""
    from datetime import date

    from studio.gi import detect
    return {f.family: [(m.status, m.span.text) for m in f.mentions]
            for f in detect.route(text, date(2026, 10, 14)).findings}


class AnEnteroscopyRoutingReadsAsPerformedIsNamedTests(SimpleTestCase):
    """EUS-SECOND 0 (verified must-fix, class 3; not pre-existing at 057a7d398, which warned "Possible missed service:
    Upper GI endoscopy (EGD, esophagoscopy, enteroscopy) ..."): an EGD read as the EUS's endoscopic portion, an EUS and a
    push enteroscopy that routing reads as performed under the upper GI family while the documented-service reading
    holds it as uncertain (an answer it does not read, or "possibly incomplete"); only 43242, which includes the EGD, is
    selected. A routing family is accounted for elsewhere only when every PERFORMED mention routing reads under it names
    a service done today that a selected code of another service includes; any other is named - the enteroscopy, never
    the EGD the code includes."""

    def test_the_enteroscopy_is_named_whatever_the_documented_service_reading_holds(self):
        for text, quote in ((ENTEROSCOPY_IN_THE_EGD_HEADING, FNA3), (ENTEROSCOPY_HEDGED, FNA3),
                            (ENTEROSCOPY_SMALLEST, SAMPLED)):
            with self.subTest(text=text[150:230]):
                self.assertIn(('performed', 'push enteroscopy'),
                              [(status, said.lower()) for status, said in routed(text)['gi.egd']])
                result = run(text, [sel('43242', span(text, quote))])
                services = {s['id']: (s['family'], s['status'], s['included_in']) for s in result.services['services']}
                self.assertEqual(services, {'S1': ('gi.egd', 'performed', 'S2'), 'S2': ('gi.eus', 'performed', ''),
                                            'S3': ('gi.enteroscopy', 'uncertain', '')})
                check = unproposed(result)
                self.assertEqual((check.status, check.detail), ('warn', MISSED_ENTEROSCOPY))
                self.assertNotIn(EVERY_DETECTED, check.detail)
                self.assertNotIn(EGD_LABEL, check.detail)  # the EGD the code includes is accounted for

    def test_control_an_enteroscopy_routing_holds_too_is_never_called_performed(self):
        # routing reads "A push enteroscopy was possibly performed." as uncertain: no performed service is missed
        self.assertIn(('uncertain', 'push enteroscopy'), routed(ENTEROSCOPY_POSSIBLY)['gi.egd'])
        for text in (ENTEROSCOPY_POSSIBLY, NO_ENTEROSCOPY):
            with self.subTest(text=text[-60:]):
                result = run(text, [sel('43242', span(text, FNA3))])
                self.assertEqual((unproposed(result).status, unproposed(result).detail),
                                 ('pass', checks.UNPROPOSED_PASS))

    def test_control_an_enteroscopy_both_readers_read_as_performed_is_named_as_before(self):
        result = run(ENTEROSCOPY_OWN_LINE, [sel('43242', span(ENTEROSCOPY_OWN_LINE, FNA3))])
        self.assertEqual((unproposed(result).status, unproposed(result).detail), ('warn', MISSED_ENTEROSCOPY))
        enteroscope = 'The enteroscope was advanced to the proximal jejunum'
        result = run(ENTEROSCOPY_OWN_LINE, [sel('43242', span(ENTEROSCOPY_OWN_LINE, FNA3)),
                                            sel('44376', span(ENTEROSCOPY_OWN_LINE, enteroscope))])
        self.assertEqual((unproposed(result).status, unproposed(result).detail), ('pass', checks.UNPROPOSED_PASS))


class TheReportsNameTheEnteroscopyRoutingReadsTests(Harness):
    """EUS-SECOND 0 through the API, on the verifier's smallest input: the stored check, the draft TXT, the Checks tab
    and - once the reviewer approves 43242 - the reviewed TXT name the enteroscopy; none says that every performed
    service routing detected has a selected proposal."""

    def test_every_surface_names_the_enteroscopy(self):
        self.use(FakeProvider(selections=[('43242', SAMPLED)]))
        encounter_id = self.create(ENTEROSCOPY_SMALLEST)
        drain()
        check = self.encounter_check(encounter_id, 'services.unproposed')
        self.assertEqual((check['status'], check['detail']), ('warn', MISSED_ENTEROSCOPY))
        line = f'[WARN] services.unproposed — Performed services without a proposal: {MISSED_ENTEROSCOPY}'
        draft = self.txt(encounter_id)
        self.assertIn(line, draft)
        self.assertNotIn(EVERY_DETECTED, draft)
        shown = screen(self.detail(encounter_id))
        self.assertIn(MISSED_ENTEROSCOPY, shown['checks'])
        self.assertNotIn(EVERY_DETECTED, shown['checks'])
        self.decide(encounter_id, '43242', 'approve')
        reply = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertEqual(reply.status_code, 201, reply.content)
        reviewed = self.txt(encounter_id, 'reviewed')
        self.assertIn(line, reviewed)
        self.assertNotIn(EVERY_DETECTED, reviewed)


# --- EUS-SECOND 1-3: the documented services count the codes as the review leaves them -----------------------------

INCLUDED_TXT = "included in S2: that service's code includes this examination"
INCLUDED_PAGE = "Included in S2: that service's code includes this examination, so no code of its own is asked."
NOT_INCLUDED_TXT = 'read as part of S2, but no selected code of that service includes this examination'
NOT_INCLUDED_PAGE = 'Read as part of S2, but no selected code of that service includes this examination.'
CANCELLED_FNA = 'was sampled by fine-needle aspiration with three passes, the core biopsy having been cancelled'
EGD_AND_EUS_CANCEL_WORD = (SYNTHETIC + 'Date of service: 2026-10-14\nIndication: pancreatic head mass.\n'
                           'Procedures: EGD and upper endoscopic ultrasound.\n'
                           'EGD: The gastroscope was advanced to the second portion of the duodenum and the examination '
                           'was completed.\n'
                           'EUS: An endoscopic ultrasound of the pancreas was performed. The echoendoscope was advanced '
                           'to the second portion of the duodenum. A 2 cm pancreatic head mass ' + CANCELLED_FNA + '.\n')
DEFERRED_FNA = 'sampled by fine-needle aspiration because the surgery was deferred'
EUS_DEFER_WORD = (SYNTHETIC + 'Date of service: 2026-10-14\nEUS of the pancreas was performed. The mass was '
                  + DEFERRED_FNA + '.\n')  # the verifier's smallest input (EUS-SECOND 2)
EUS_NO_PROPOSAL = 'endoscopic ultrasound (documented as performed) has no supported proposal'
SECOND_REVIEW_OFFER = 'Second provider review available'
COUNTED = 'with the code the reviewer reinstated (43242) counted as selected'
PREDATES = ('The documented-service checks were made when the assessment ran, before the reviewer reinstated 43242, '
            'and do not count it')


class ReviewHarness(Harness):
    def stored(self, text, *selections):
        self.use(FakeProvider(selections=list(selections)))
        encounter_id = self.create(text)
        drain()
        return encounter_id

    def reviewed(self, encounter_id):
        reply = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertEqual(reply.status_code, 201, reply.content)
        return self.txt(encounter_id, 'reviewed')

    def excluded_and_reinstatable(self, encounter_id, code='43242'):
        (proposal,) = [p for p in self.detail(encounter_id)['assessment']['proposals'] if p['code'] == code]
        self.assertEqual((proposal['bucket'], proposal['reinstatable']), ('excluded', True))
        self.assertIn(('review.reinstatement', 'pass'), [(c['id'], c['status']) for c in proposal['checks']])


class AReinstatedCodeCountsAsASelectedOneTests(ReviewHarness):
    """EUS-SECOND 1 and 2 (verified must-fix, class 3): a documentation check excludes the EUS's code - 43242, which
    includes the EGD read as the EUS's endoscopic portion - on another act's cancel or defer word (a misreading
    interpretation 27 leaves to the reviewer's reinstatement); the reviewer reinstates and approves it. The reviewed
    report and the page still read the reconciliation the assessment recorded without it: the EGD "read as part of S2,
    but no selected code of that service includes this examination" (P2RA's wording, worded from the non-excluded codes
    only), the EUS with no "accounted for by" and listed "has no supported proposal", coding incomplete for it, and a
    second review offered for it - all beside "APPROVED SELECTIONS 43242 ... Reinstated from exclusion". A code a
    reviewer reinstated is decided like a selected one, so the documented services count it as one: the reconciliation
    the reports, the page, coding completeness and the second review read is the assessment's with that code counted
    (review.reviewed_completeness), said where it is shown; the checks the assessment made say they predate it."""

    def test_the_egd_is_included_and_the_eus_accounted_for_once_the_code_is_reinstated_and_approved(self):
        encounter_id = self.stored(EGD_AND_EUS_CANCEL_WORD, ('43242', CANCELLED_FNA))
        self.excluded_and_reinstatable(encounter_id)
        self.decide(encounter_id, '43242', 'reinstate', bucket='excluded')
        self.decide(encounter_id, '43242', 'approve', bucket='excluded')
        reviewed = self.reviewed(encounter_id)
        self.assertIn('Reinstated from exclusion', reviewed)
        documented = section(reviewed, 'DOCUMENTED SERVICES')
        self.assertIn(f'      {INCLUDED_TXT}\n', documented + '\n')
        self.assertNotIn(NOT_INCLUDED_TXT, reviewed)
        self.assertIn('      accounted for by: 43242\n', documented + '\n')
        self.assertIn(COUNTED, documented)
        self.assertNotIn(EUS_NO_PROPOSAL, section(reviewed, 'UNRESOLVED DOCUMENTED SERVICES'))
        self.assertIn('  State: reviewed', section(reviewed, 'CODING COMPLETENESS'))
        self.assertIn(PREDATES, section(reviewed, 'CHECKS'))
        detail = self.detail(encounter_id)
        self.assertEqual(detail['coding']['state'], 'reviewed')
        self.assertFalse(detail['second_review']['available'])
        self.assertEqual(detail['assessment']['completeness']['reinstated'], ['43242'])
        shown = screen(detail)
        self.assertIn(INCLUDED_PAGE, shown['codes'])
        self.assertIn('Accounted for by: 43242.', shown['codes'])
        self.assertNotIn(NOT_INCLUDED_PAGE, shown['codes'] + shown['checks'])
        self.assertNotIn(SECOND_REVIEW_OFFER, shown['codes'] + shown['checks'])
        self.assertIn('Made before the reviewer', shown['checks'])
        # the assessment's own record is unchanged: the review's reading is derived, never written back
        self.assertEqual(self.assessment(encounter_id).completeness['included_by'], {'S1': []})

    def test_the_eus_alone_is_accounted_for_and_no_second_review_is_offered(self):
        encounter_id = self.stored(EUS_DEFER_WORD, ('43242', DEFERRED_FNA))
        self.excluded_and_reinstatable(encounter_id)
        self.assertTrue(self.detail(encounter_id)['second_review']['available'])  # before the reviewer's decision
        self.decide(encounter_id, '43242', 'reinstate', bucket='excluded')
        self.decide(encounter_id, '43242', 'approve', bucket='excluded')
        reviewed = self.reviewed(encounter_id)
        self.assertIn('      accounted for by: 43242\n', section(reviewed, 'DOCUMENTED SERVICES') + '\n')
        self.assertNotIn(EUS_NO_PROPOSAL, section(reviewed, 'UNRESOLVED DOCUMENTED SERVICES'))
        self.assertIn(PREDATES, section(reviewed, 'CHECKS'))  # the assessment's own check still names it, and says why
        self.assertIn('  State: reviewed', section(reviewed, 'CODING COMPLETENESS'))
        detail = self.detail(encounter_id)
        self.assertEqual(detail['second_review']['items'], [])
        self.assertFalse(detail['second_review']['available'])
        self.assertNotIn(SECOND_REVIEW_OFFER, screen(detail)['codes'])
        sent = list(self.provider.sent)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        drain()
        self.assertEqual(self.provider.sent, sent)  # nothing is sent

    def test_controls_a_confirmed_exclusion_and_a_rejection_after_reinstatement_count_nothing(self):
        for actions in (('confirm',), ('reinstate', 'reject')):
            with self.subTest(actions=actions):
                self.fresh(f'Synthetic workspace {"-".join(actions)}')
                encounter_id = self.stored(EGD_AND_EUS_CANCEL_WORD, ('43242', CANCELLED_FNA))
                for action in actions:
                    self.decide(encounter_id, '43242', action, bucket='excluded')
                reviewed = self.reviewed(encounter_id)
                self.assertIn(NOT_INCLUDED_TXT, reviewed)
                self.assertNotIn(INCLUDED_TXT, reviewed)
                self.assertIn(EUS_NO_PROPOSAL, section(reviewed, 'UNRESOLVED DOCUMENTED SERVICES'))
                self.assertNotIn('reinstated (43242) counted', reviewed)
                self.assertNotIn('do not count it', reviewed)
                detail = self.detail(encounter_id)
                self.assertEqual(detail['coding']['state'], 'incomplete')
                self.assertTrue(detail['second_review']['available'])
                self.assertNotIn('reinstated', detail['assessment']['completeness'])


EGD_LINE = 'EGD: The gastroscope was advanced to the duodenum.'
SAMPLED_FNA = 'was sampled by fine-needle aspiration'
EGD_AND_EUS_PAIR = (SYNTHETIC + 'Date of service: 2026-10-14\n' + EGD_LINE + '\n'
                    'EUS: A pancreatic mass ' + SAMPLED_FNA + '.\n')  # the verifier's smallest input (EUS-SECOND 3)


class ARejectedCodeIncludesNothingTests(ReviewHarness):
    """EUS-SECOND 3 (verified must-fix, class 3): an esophagoscopy EUS code (43232), which includes no upper endoscopy,
    and an EGD-with-EUS code (43242) - from the primary answer, or added by the second review for the listed EGD; the
    reviewer approves 43232 and rejects 43242. The reviewed report said "included in S2: that service's code includes
    this examination" and the page "... so no code of its own is asked" beside "accounted for by: 43232 / rejected by
    the reviewer: 43242": a code the reviewer rejected accounts for nothing (refutation r1, report-6), and includes
    nothing either - the inclusion line drops it, as "accounted for by" does. This also settles the row "ec5
    REPORTFACTS skeptic, included in" (the including service's only code rejected)."""

    def assert_not_included(self, encounter_id):
        reviewed = self.reviewed(encounter_id)
        self.assertIn(f'      {NOT_INCLUDED_TXT}\n', section(reviewed, 'DOCUMENTED SERVICES') + '\n')
        self.assertNotIn(INCLUDED_TXT, reviewed)
        shown = screen(self.detail(encounter_id))
        self.assertIn(NOT_INCLUDED_PAGE, shown['codes'])
        self.assertNotIn('no code of its own is asked', shown['codes'] + shown['checks'])
        return reviewed

    def test_the_primary_pair_with_the_including_code_rejected(self):
        encounter_id = self.stored(EGD_AND_EUS_PAIR, ('43232', SAMPLED_FNA), ('43242', SAMPLED_FNA))
        self.decide(encounter_id, '43232', 'approve')
        self.decide(encounter_id, '43242', 'reject')
        reviewed = self.assert_not_included(encounter_id)
        self.assertIn('accounted for by: 43232\n      rejected by the reviewer: 43242\n', reviewed)

    def test_the_second_reviews_including_code_rejected(self):
        self.use(TwoPassProvider(first=[('43232', SAMPLED_FNA)], later=[('43242', EGD_LINE)]))
        encounter_id = self.create(EGD_AND_EUS_PAIR)
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        drain()
        self.assertEqual(self.assessment(encounter_id).completeness['included_by'], {'S1': ['43242']})
        self.decide(encounter_id, '43232', 'approve')
        self.decide(encounter_id, '43242', 'reject')
        self.assert_not_included(encounter_id)

    def test_the_including_services_only_code_rejected(self):
        encounter_id = self.stored(EGD_AND_EUS_PAIR, ('43242', SAMPLED_FNA))
        self.decide(encounter_id, '43242', 'reject')
        reviewed = self.assert_not_included(encounter_id)
        self.assertIn('rejected by the reviewer: 43242 — no other selected code accounts for this service', reviewed)

    def test_controls_the_including_code_approved_keeps_the_inclusion_line(self):
        for approved, rejected in (('43242', '43232'), ('43242', None)):
            with self.subTest(approved=approved, rejected=rejected):
                self.fresh(f'Synthetic workspace {approved} {rejected}')
                selections = [('43242', SAMPLED_FNA)] + ([(rejected, SAMPLED_FNA)] if rejected else [])
                encounter_id = self.stored(EGD_AND_EUS_PAIR, *selections)
                self.decide(encounter_id, approved, 'approve')
                if rejected:
                    self.decide(encounter_id, rejected, 'reject')
                reviewed = self.reviewed(encounter_id)
                self.assertIn(f'      {INCLUDED_TXT}\n', section(reviewed, 'DOCUMENTED SERVICES') + '\n')
                self.assertIn(INCLUDED_PAGE, screen(self.detail(encounter_id))['codes'])
