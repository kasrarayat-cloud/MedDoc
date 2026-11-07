"""The walk round (2026-11-07): what the acceptance walk of the installed completion repair (6f306af1b030) found in the
shared readers, each repaired as a structural rule and pinned here beside its negative controls. The causes are recorded
in docs/deploy-reports/20261107-cpt-studio-6f306af1-install-and-walk.md (findings 1 to 5); the documents below are
synthetic paraphrases of the shapes, never the walk sets' own text.

1. The labelled release (studio.gi.structure): a plan's later clinic visit is no office structure (P1); the course may
   follow a frame and preparation sentences (P2); a procedure line declares, it is no positive body (P3); four ordinary
   words no longer read as another time or place (N1).
2. A labelled paragraph's binding ends where its narrative leaves its examination, not at every scope word
   (services._scope_switch).
3. A course continued in its sentence reaches its later landmarks (detect._course_continued).
4. A bolus the report names by its food as the subject of an impaction, removed by "brought out" (services).
5. A sub-act's failure stated of its own instrument by a negated passive, inside the closed attempt form, cited beside
   the code's own documented act: set aside, so the code reads as with that act's passage cited alone (detect recognises
   the form; engine._set_aside_attempts decides). The round's first form consumed the negation in routing, which
   released every code citing it - the abandoned another-act release - and the pinned cycle-2 cases caught it.
6. The round's refutation (D1): a code none of whose passages shows its act rests on the act's passage CPT Studio selects,
   which the routing-era second opinion reads in its whole sentence as it reads a cited passage (engine)."""
from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi import services as gi_services
from studio.types import ProviderCode
from tests.test_completion_structure import COL, EGD_BIOPSY, HEAD, IND, SNARE, colonoscopy, why
from tests.test_harness_engine import DAY, code, corti, proposal, read, run, span

QUIET = ('pass', 'not_applicable', 'not_verified', 'info')
COURSE = 'The colonoscope was introduced through the anus and advanced to the cecum. '
EGD_COURSE = 'the gastroscope was passed under direct vision and advanced to the second portion of the duodenum. '


def flags(p):
    return sorted(c.id for c in p.checks if c.status not in QUIET and c.id != 'pfs.presence')


class LabelledReleaseTests(SimpleTestCase):

    def test_a_plan_naming_a_later_clinic_visit_is_no_office_note(self):
        text = colonoscopy('Colonoscopy: ' + COURSE + SNARE + '\n',
                           tail='Impression: Sigmoid polyp removed.\nPlan: Clinic visit in four weeks.\n')
        self.assertEqual(why(text), [''])
        # an office visit named outside a plan still makes the document no procedure report (P1)
        office = colonoscopy('Colonoscopy: ' + COURSE + SNARE + '\n',
                             ind='Indications: Seen at an office visit for dysphagia.\n')
        self.assertTrue(all(reason.startswith('P1') for reason in why(office)), why(office))

    def test_the_course_may_follow_preparation_sentences(self):
        text = colonoscopy('Colonoscopy: The patient was placed in the left lateral position. A digital rectal '
                           'examination was normal. ' + COURSE + SNARE + '\n')
        self.assertEqual(why(text), [''])
        for label, paragraph in {
            'three preparation sentences': 'Colonoscopy: The patient was turned. The lights were dimmed. The monitor was '
                                           'adjusted. ' + COURSE + SNARE + '\n',
            'an opening sentence naming an instrument': 'Colonoscopy: The gastroscope was withdrawn. ' + COURSE + SNARE + '\n',
            'an opening sentence naming a service': 'Colonoscopy: An upper endoscopy was done first. ' + COURSE + SNARE + '\n',
        }.items():
            with self.subTest(label):
                reasons = why(colonoscopy(paragraph))
                self.assertTrue(reasons and reasons[0] and reasons[0][:2] in ('P2', 'N1'), reasons)

    def test_a_frame_with_no_signal_opens_the_course(self):
        text = HEAD + IND + 'Upper endoscopy: After informed consent and a time-out, ' + EGD_COURSE + EGD_BIOPSY + '\n'
        self.assertEqual(why(text), [''])

    def test_a_procedure_line_declares_its_families(self):
        body = ('Procedures: Upper endoscopy with dilation; colonoscopy\n\n' + IND
                + 'Upper endoscopy: The ' + EGD_COURSE + EGD_BIOPSY + '\n' + 'Colonoscopy: ' + COURSE + SNARE + '\n')
        self.assertEqual(why(HEAD + body), ['', ''])
        # a procedure heading that states something is a positive body of its own (P3 as before)
        stating = HEAD + 'Procedure: The colonoscope was advanced to the cecum.\n' + IND + 'Colonoscopy: ' + COURSE \
            + SNARE + '\n'
        self.assertTrue(all(reason.startswith('P3') for reason in why(stating)), why(stating))

    def test_ordinary_words_no_longer_read_as_another_time_or_place(self):
        egd = ('Upper endoscopy: The ' + EGD_COURSE + 'The wire was removed with the last dilator. On a second look with '
               'the gastroscope, the ring was disrupted, with slight oozing that stopped on its own.\n')
        self.assertEqual(why(HEAD + IND + egd), [''])
        for label, sentence in {
            'last week': 'The esophagus had been dilated last week.',
            'her last colonoscopy': 'A ring was seen at her last endoscopy.',
            'at the outside hospital': 'The ring was dilated at the outside hospital.',
        }.items():
            with self.subTest(label):
                text = HEAD + IND + 'Upper endoscopy: The ' + EGD_COURSE + sentence + '\n'
                self.assertEqual(why(text), ['N1: the paragraph states another time, place, agent or source'])


class BindingTests(SimpleTestCase):
    WIRE = ('Upper endoscopy: The ' + EGD_COURSE + 'A Savary guidewire was passed through the scope into the gastric '
            'antrum, and the scope was withdrawn over the wire. Savary dilators of 15 and 16 mm were then passed over the '
            'wire.\n')

    def test_the_same_scope_over_a_wire_keeps_the_binding(self):
        text = HEAD + IND + self.WIRE + 'Impression: Dilated.\n'
        result = run(text, corti(('43248', span(text, 'Savary dilators of 15 and 16 mm were then passed over the wire'))))
        self.assertEqual(proposal(result, '43248').status, 'ready')

    def test_a_scope_withdrawn_or_another_introduced_ends_it(self):
        """In a report of both examinations (as cycle 4's structure-2 inputs): past the switch, a site-less removal is
        neither examination's for certain, so it binds to no label. (In an EGD-only report the heading twin binds it to
        the one examination there, and so does the labelled form.)"""
        for label, switch in {
            'withdrawn, then another scope': 'The gastroscope was withdrawn. Next, the pediatric scope was introduced and '
                                             'a 6 mm sessile polyp was removed with a cold snare.',
            'the other tract\'s scope': 'The upper tract was normal, and the lower scope was passed. A 6 mm sessile polyp '
                                        'was removed with a cold snare.',
            'another family\'s instrument': 'The colonoscope was then introduced. A 6 mm sessile polyp was removed with a '
                                            'cold snare.',
        }.items():
            with self.subTest(label):
                text = HEAD + IND + 'Upper endoscopy: The ' + EGD_COURSE + switch + '\n' + COL + 'Impression: Polyp.\n'
                result = run(text, corti(('43251', span(text, 'removed with a cold snare'))))
                self.assertNotEqual(proposal(result, '43251').status, 'ready')


class CourseContinuationTests(SimpleTestCase):
    HEAD_EGD = HEAD + 'Procedure: Upper endoscopy\n'

    def extent(self, sentence):
        text = self.HEAD_EGD + sentence + '\n'
        finding = detect.route(text, DAY).finding('gi.egd')
        return next((f.value for f in finding.facts if f.name == 'extent'), None)

    def test_a_continued_course_reaches_its_later_landmark(self):
        self.assertEqual(self.extent('The gastroscope was advanced into the stomach, which was normal on forward view and '
                                     'on retroflexion, and through the pylorus to the second portion of the duodenum.'),
                         'second part of duodenum')

    def test_a_course_stopped_or_doubted_does_not(self):
        for sentence in ('The gastroscope was advanced into the stomach but could not be passed through the pylorus to the '
                         'second portion of the duodenum.',
                         'The gastroscope was advanced into the stomach, which was not distended, and through the pylorus '
                         'to the second portion of the duodenum.'):
            with self.subTest(sentence):
                self.assertNotEqual(self.extent(sentence), 'second part of duodenum')


class BolusRemovalTests(SimpleTestCase):
    FOUND = ('Procedure: Upper endoscopy\nThe gastroscope was passed into the esophagus and advanced to the second portion '
             'of the duodenum. A large piece of partly chewed meat was impacted in the distal esophagus at 34 cm. A '
             'retrieval net was passed through the working channel. ')

    def acts(self, tail):
        text = HEAD + self.FOUND + tail + '\n'
        inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY), context_facts=None,
                                      pages=())
        return [(a.kind, a.status) for svc in inventory.services for a in svc.acts if a.kind == 'foreign_body']

    def test_the_bolus_brought_out_is_removed(self):
        self.assertEqual(self.acts('The bolus was captured and brought out through the mouth.'),
                         [('foreign_body', 'performed')])
        text = HEAD + self.FOUND + 'The bolus was captured and brought out through the mouth.\n'
        result = run(text, (), [read('astra', [code(text, '43247', 'The bolus was captured and brought out')])])
        self.assertEqual(proposal(result, '43247').status, 'ready')

    def test_a_bolus_not_brought_out_or_pushed_is_not(self):
        for tail in ('The bolus could not be brought out.', 'The bolus was not brought out.',
                     'The bolus was unable to be brought out.', 'The bolus was captured but could not be brought out.',
                     'The bolus was pushed into the stomach.'):
            with self.subTest(tail):
                self.assertNotIn(('foreign_body', 'performed'), self.acts(tail))


class NegatedPassiveFailureTests(SimpleTestCase):
    DONE = 'A 7 mm polyp in the transverse colon was removed with a cold snare.'
    ATTEMPT = ('Hot snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon was attempted, but the snare '
               'could not be closed around the stalk, and the polyp was left in place.')

    def reading(self, attempt):
        text = HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the terminal ileum. ' + self.DONE + ' ' \
            + attempt + '\n'
        # one selection citing both passages, as a provider cites a code (never two selections: that is two units)
        selected = ProviderCode('selected', 'cpt', '45385', 'UNVERIFIED PROVIDER WORDING',
                                (span(text, self.DONE), span(text, attempt)))
        p = proposal(run(text, [selected]), '45385')
        return p.status, flags(p)

    def test_the_other_polyps_failed_attempt_no_longer_holds_the_done_removal(self):
        self.assertEqual(self.reading(self.ATTEMPT)[0], 'ready')

    def text(self, done=None):
        return HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the terminal ileum. ' + (done or self.DONE) \
            + ' ' + self.ATTEMPT + '\n'

    def test_the_same_passages_read_the_same_whoever_cited_which(self):
        text = self.text()
        done, attempt = span(text, self.DONE), span(text, self.ATTEMPT)
        corti_done = run(text, corti(('45385', done)), [read('astra', [code(text, '45385', self.ATTEMPT)])])
        corti_attempt = run(text, corti(('45385', attempt)), [read('astra', [code(text, '45385', self.DONE)])])
        self.assertEqual((proposal(corti_done, '45385').status, proposal(corti_done, '45385').units), ('ready', 1))
        self.assertEqual((proposal(corti_attempt, '45385').status, proposal(corti_attempt, '45385').units), ('ready', 1))
        detail = next(c.detail for c in proposal(corti_done, '45385').checks if c.id == 'service.status')
        self.assertIn("states another attempt's own failure", detail)

    def test_the_failed_attempt_cited_alone_keeps_the_installed_hold(self):
        """Nothing the code is matched to is cited beside the failure: the installed hold (the declared cost of the
        abandoned another-act release) stands, for every proposer."""
        text = self.text()
        for result in (run(text, corti(('45385', span(text, self.ATTEMPT)))),
                       run(text, (), [read('astra', [code(text, '45385', self.ATTEMPT)])])):
            self.assertEqual(proposal(result, '45385').status, 'needs_clarification')

    def test_a_unit_resting_on_the_failed_attempt_is_never_ready(self):
        """Corti lists the code twice, once on the failed attempt: two units, one documented act - held, in either
        order (the owner session's units defect, pinned since cycle 2)."""
        text = self.text()
        for first, second in ((self.DONE, self.ATTEMPT), (self.ATTEMPT, self.DONE)):
            p = proposal(run(text, corti(('45385', span(text, first)), ('45385', span(text, second)))), '45385')
            self.assertEqual((p.status, p.units), ('needs_clarification', 2))

    def test_a_doubt_of_the_done_removal_itself_still_holds(self):
        """Set aside, the failure takes nothing else with it: the done removal's own sentence is read as before."""
        hedged = ('A 7 mm polyp in the transverse colon was removed with a cold snare, but it is unclear whether the '
                  'polyp was removed or only biopsied.')
        text = self.text(hedged)
        selected = ProviderCode('selected', 'cpt', '45385', 'UNVERIFIED PROVIDER WORDING',
                                (span(text, hedged), span(text, self.ATTEMPT)))
        self.assertEqual(proposal(run(text, [selected]), '45385').status, 'needs_clarification')

    def test_outside_the_closed_form_the_doubt_stays(self):
        for attempt in ('The snare could not be closed around the stalk of the 12 mm sigmoid polyp.',
                        'Hot snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon was attempted, but the '
                        'snare could not be closed around the stalk, and the remainder of the examination was abandoned.'):
            with self.subTest(attempt):
                self.assertNotEqual(self.reading(attempt)[0], 'ready')


class SelectedPassageHoldTests(SimpleTestCase):
    """The cited passage is another polyp's failed attempt in a form the base and the installed release already read as
    that attempt's own failure ("..., but the snare failed; the polyp was left in place."), so the code rests on the act
    CPT Studio selects. Its sentence is read by the routing-era second opinion exactly as a cited passage: a hedge or
    another time there holds the code - which both releases read READY - and a plain act stays READY with the citation
    flagged, as before. (The negated-passive form cited alone keeps the installed hold: NegatedPassiveFailureTests.)"""
    HEDGED = ('A 6 mm polyp in the transverse colon was removed with a cold snare, but it is unclear whether the polyp '
              'was removed or only biopsied.')
    ATTEMPTS = ('Hot snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon was attempted, but the snare '
                'failed; the polyp was left in place.',
                'Snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon failed.')

    def reading(self, attempt, other):
        text = HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the terminal ileum. ' + attempt + '\n' \
            + other + '\n'
        return proposal(run(text, corti(('45385', span(text, attempt)))), '45385')

    def test_an_act_its_own_sentence_doubts_is_held(self):
        for other in (self.HEDGED, self.HEDGED.replace('it is unclear', 'it is\nunclear'),
                      'A 6 mm polyp in the transverse colon was removed with a cold snare at her last colonoscopy.'):
            for attempt in self.ATTEMPTS:
                with self.subTest(other=other, attempt=attempt):
                    p = self.reading(attempt, other)
                    self.assertEqual(p.status, 'needs_clarification')
                    asked = ' '.join(c.question for c in p.clarifications)
                    self.assertIn('Confirm whether 45385 is supported: the passage that documents its act', asked)
                    status = next(c for c in p.checks if c.id == 'service.status')
                    self.assertIn('which CPT Studio selected', status.detail)

    def test_a_plain_act_stays_ready_with_the_citation_flagged(self):
        for attempt in self.ATTEMPTS:
            with self.subTest(attempt):
                p = self.reading(attempt, 'A 6 mm polyp in the transverse colon was removed with a cold snare.')
                self.assertEqual(p.status, 'ready')
                self.assertEqual(next(c.status for c in p.checks if c.id == 'evidence.support'), 'warn')
