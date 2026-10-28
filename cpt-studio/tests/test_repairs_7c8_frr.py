"""Continuation round 7c8, the final refutation of the phase-2 repairs (P2FR), reports track: each class reproduces a
finding a refutation lens demonstrated on the integration head c3c034a08 and an independent verifier reproduced, with
its smallest input, and asserts what is true of the persisted state beside a control that must not change. Synthetic
data only; the provider is an in-process fake (no network).

- EUS-SECOND 0 (engine._accounted_elsewhere): services.unproposed passed - "Every performed service that routing
  detected in the document has a selected proposal" - beside a push enteroscopy routing reads as performed under the
  upper GI family, because the documented-service reading held that enteroscopy as uncertain and only the services it
  read as done today were counted: the EGD inside the EUS, which the selected EGD-with-EUS code includes, made the
  whole routing family read as accounted for.
"""
from django.test import SimpleTestCase

from studio.gi.profiles import PROFILES
from studio.validation import checks
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_7c8_p1reports import Harness
from tests.test_repairs_7c8_p2reports import EGD_LABEL, EVERY_DETECTED, screen, unproposed
from tests.test_services_reconcile import run, sel, span

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
