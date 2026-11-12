"""The walk round (2026-11-07): what the acceptance walk of the installed completion repair (6f306af1b030) found in the
shared readers, each repaired as a structural rule and pinned here beside its negative controls - and what the round's
refutation (four lenses over 0eda9a02) found in the first forms of those repairs, each pinned beside its control. The
walk's causes are recorded in docs/deploy-reports/20261107-cpt-studio-6f306af1-install-and-walk.md (findings 1 to 5);
the documents below are synthetic paraphrases of the shapes, never the walk sets' own text.

1. The labelled release (studio.gi.structure): a plan's later clinic visit is no office structure (P1); the course may
   follow informed consent and a time-out, or at most two preparation statements - the patient's position, a digital
   rectal examination (P2, the installed rule with closed extensions: the round's first, open form released a hedged
   course, a denial and another time); a procedure line declares, it is no positive body (P3); four ordinary words no
   longer read as another time or place (N1).
2. OPEN (two-cycle rule): a labelled paragraph's binding ends at the first later sentence naming a scope, as installed,
   so in a report of both examinations a site-less dilation past it ("the scope was withdrawn over the wire. Savary
   dilators ... were then passed over the wire") is held. Two approaches were each refuted twice and dropped: the
   binding's exceptions (their wording, then their local form) and a device-tract binding (the device alone is open -
   Savary bougies dilate anastomotic strictures; then a guide wire's brand name read as a dilation where the stricture
   was not dilated, and a paragraph rescan per mention cost 81.8 s on an admitted input).
3. OPEN (two-cycle rule): a coordinated reach after a relative aside ("advanced into the stomach, which was normal ...,
   and through the pylorus to the second portion of the duodenum") keeps the installed incomplete reading; both forms of
   the continuation reader were refuted (a segment named after a later mention; any words as the route) and dropped.
4. OPEN (two-cycle rule): a bolus "captured and brought out through the mouth" is held, as installed. Two approaches
   were each refuted twice and dropped: the out-words as done participles (bare, then route-bound) and the route-bound
   removal as the bolus phrase's own predicate (open, then closed - "taken out ... by the emergency physician", "by Dr.
   <another physician>" and a bolus that fell back still read done). services.py is the installed module.
5. A sub-act's failure stated of its own instrument by a negated passive, inside the closed attempt form, cited beside
   the code's own documented act on another lesion: set aside, so the code reads as with that act's passage cited alone
   (detect.closed_attempt_failure recognises the form; engine._set_aside_attempts decides). The round's first form
   consumed the negation in routing, which released every code citing it - the abandoned another-act release - and the
   pinned cycle-2 cases caught it. The round's selected-passage hold (D1) was dropped after its refutation: it read
   clauses about other acts and held supported codes; the false READY it aimed at is the base's and the installed
   release's, recorded (ACCURACY-RESIDUALS.md, the walk round)."""
from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi import services as gi_services
from studio.gi import structure
from studio.types import ProviderCode
from tests.test_completion_structure import COL, EGD_BIOPSY, HEAD, IND, SNARE, colonoscopy, why
from tests.test_harness_engine import DAY, code, corti, proposal, read, run, span

QUIET = ('pass', 'not_applicable', 'not_verified', 'info')
COURSE = 'The colonoscope was introduced through the anus and advanced to the cecum. '
EGD_COURSE = 'the gastroscope was passed under direct vision and advanced to the second portion of the duodenum. '
EGD_OPEN = 'Upper endoscopy: The ' + EGD_COURSE[len('the '):]


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

    def test_the_course_may_follow_preparation_statements(self):
        for opening in ('The patient was placed in the left lateral position. A digital rectal examination was normal. ',
                        'The patient was turned to the left lateral position. Digital rectal examination was normal. '):
            with self.subTest(opening):
                self.assertEqual(why(colonoscopy('Colonoscopy: ' + opening + COURSE + SNARE + '\n')), [''])
        for label, paragraph in {
            'three preparation statements': 'Colonoscopy: The patient was placed in the left lateral position. A digital '
                                            'rectal examination was normal. The patient was placed in the left lateral '
                                            'position. ' + COURSE + SNARE + '\n',
            'an opening sentence that is no preparation statement': 'Colonoscopy: The lights were dimmed. ' + COURSE
                                                                    + SNARE + '\n',
            'an opening sentence naming an instrument': 'Colonoscopy: The gastroscope was withdrawn. ' + COURSE + SNARE + '\n',
            'an opening sentence naming a service': 'Colonoscopy: An upper endoscopy was done first. ' + COURSE + SNARE + '\n',
            # the round's refutation (structure 1-3): nothing in the release reads status, so none is admitted
            'a denial': 'Colonoscopy: Not performed. ' + COURSE + SNARE + '\n',
            'the patient declined': 'Colonoscopy: The patient declined. ' + COURSE + SNARE + '\n',
            'a hedged course': 'Colonoscopy: It is unclear whether the colonoscope was advanced to the cecum because of poor '
                               'preparation. ' + SNARE + '\n',
            'another time': 'Colonoscopy: The next year, the colonoscope was introduced through the anus and advanced to '
                            'the cecum. ' + SNARE + '\n',
            'a preparation statement denied': 'Colonoscopy: A digital rectal examination was not performed. ' + COURSE
                                              + SNARE + '\n',
        }.items():
            with self.subTest(label):
                reasons = why(colonoscopy(paragraph))
                self.assertTrue(reasons and reasons[0] and reasons[0][:2] in ('P2', 'N1'), reasons)

    def test_informed_consent_and_a_time_out_open_the_course(self):
        text = HEAD + IND + 'Upper endoscopy: After informed consent and a time-out, ' + EGD_COURSE + EGD_BIOPSY + '\n'
        self.assertEqual(why(text), [''])

    def test_a_procedure_line_declares_its_families(self):
        body = ('Procedures: Upper endoscopy with dilation; colonoscopy\n\n' + IND
                + EGD_OPEN + EGD_BIOPSY + '\n' + 'Colonoscopy: ' + COURSE + SNARE + '\n')
        self.assertEqual(why(HEAD + body), ['', ''])
        # a procedure heading that states something is a positive body of its own (P3 as before)
        stating = HEAD + 'Procedure: The colonoscope was advanced to the cecum.\n' + IND + 'Colonoscopy: ' + COURSE \
            + SNARE + '\n'
        self.assertTrue(all(reason.startswith('P3') for reason in why(stating)), why(stating))

    def test_ordinary_words_no_longer_read_as_another_time_or_place(self):
        egd = (EGD_OPEN + 'The wire was removed with the last dilator. On a second look with the gastroscope, the ring was '
               'disrupted, with slight oozing that stopped on its own.\n')
        self.assertEqual(why(HEAD + IND + egd), [''])
        for label, sentence in {
            'last week': 'The esophagus had been dilated last week.',
            'her last colonoscopy': 'A ring was seen at her last endoscopy.',
            'at the outside hospital': 'The ring was dilated at the outside hospital.',
        }.items():
            with self.subTest(label):
                text = HEAD + IND + EGD_OPEN + sentence + '\n'
                self.assertEqual(why(text), ['N1: the paragraph states another time, place, agent or source'])


class BindingTests(SimpleTestCase):
    WIRE = (EGD_OPEN + 'A Savary guidewire was passed through the scope into the gastric antrum, and the scope was '
            'withdrawn over the wire. Savary dilators of 15 and 16 mm were then passed over the wire.\n')

    def test_the_same_scope_over_a_wire_keeps_the_binding(self):
        text = HEAD + IND + self.WIRE + 'Impression: Dilated.\n'
        result = run(text, corti(('43248', span(text, 'Savary dilators of 15 and 16 mm were then passed over the wire'))))
        self.assertEqual(proposal(result, '43248').status, 'ready')

    def test_any_other_scope_sentence_ends_it(self):
        """In a report of both examinations: past a sentence naming a scope outside the two closed forms, a site-less
        removal is neither examination's for certain, so it binds to no label - the installed rule. The round's
        refutation (binding 1-3) supplied the last four: its first form read the switch from its wording."""
        for label, switch in {
            'withdrawn, then another scope': 'The gastroscope was withdrawn. Next, the pediatric scope was introduced and '
                                             'a 6 mm sessile polyp was removed with a cold snare.',
            'the other tract\'s scope': 'The upper tract was normal, and the lower scope was passed. A 6 mm sessile polyp '
                                        'was removed with a cold snare.',
            'another family\'s instrument': 'The colonoscope was then introduced. A 6 mm sessile polyp was removed with a '
                                            'cold snare.',
            'the lower GI scope': 'The upper tract was normal, and the lower GI scope was passed. A 6 mm sessile polyp was '
                                  'removed with a cold snare.',
            'two adverbs and an appositive': 'The gastroscope was then gently withdrawn. Next, the pediatric scope, a '
                                             'PCF-H190, was introduced and a 6 mm sessile polyp was removed with a cold '
                                             'snare.',
            'a nominal withdrawal': 'Withdrawal of the gastroscope was uneventful. Next, a pediatric scope was used, and a '
                                    '6 mm sessile polyp was removed with a cold snare.',
        }.items():
            with self.subTest(label):
                text = HEAD + IND + EGD_OPEN + switch + '\n' + COL + 'Impression: Polyp.\n'
                result = run(text, corti(('43251', span(text, 'removed with a cold snare'))))
                self.assertNotEqual(proposal(result, '43251').status, 'ready')

    def test_a_dilation_past_the_cut_in_a_report_of_both_is_the_recorded_open_defect(self):
        """Walk finding 2 stays OPEN (ACCURACY-RESIDUALS.md, the walk round): the binding's exceptions and the device-tract
        binding were each refuted twice and dropped under the two-cycle rule, so in a report of both examinations a
        site-less dilation past the binding's cut is held, as installed. A repair must move this pin with its own
        evidence."""
        both = HEAD + IND + self.WIRE + COL + 'Impression: Ring dilated; sigmoid polyp removed.\n'
        result = run(both, corti(('43248', span(both, 'Savary dilators of 15 and 16 mm were then passed over the wire'))))
        held = proposal(result, '43248')
        self.assertEqual(held.status, 'needs_clarification')
        self.assertEqual(flags(held), ['service.status'])

    def test_no_device_word_binds_a_dilation_past_the_cut(self):
        """The device-tract binding's refutations, read as installed now that it is dropped: Savary bougies dilate
        anastomotic strictures too; a Savary guidewire carries a colonic balloon; a guide wire's brand name is no
        dilation, least of all where the stricture was not dilated (round 4); nor is a statement of what is usually
        done."""
        quote = 'Savary dilators of 15 and 16 mm were then passed over the wire'
        egd_ok = HEAD + IND + self.WIRE + 'Impression: Dilated.\n'  # one examination: no binding question
        self.assertEqual(proposal(run(egd_ok, corti(('43248', span(egd_ok, quote)))), '43248').status, 'ready')
        for label, sentence, cited in (
                ('a guide wire, not dilated',
                 'A tight peptic stricture was found at 34 cm from the incisors. A Savary-Gilliard guide wire was passed '
                 'through the scope, and the scope was withdrawn over the wire. A deep mucosal tear was then seen, so the '
                 'stricture was not dilated and the wire was removed.',
                 'A Savary-Gilliard guide wire was passed through the scope'),
                ('what is usually done',
                 'A tight peptic stricture was found. The scope was withdrawn. Savary dilation is usually performed for '
                 'such strictures.',
                 'Savary dilation is usually performed for such strictures')):
            with self.subTest(label):
                text = HEAD + IND + EGD_OPEN + sentence + '\n' + COL + 'Impression: Stricture.\n'
                result = run(text, corti(('43248', span(text, cited))))
                self.assertNotEqual(proposal(result, '43248').status, 'ready')
        colon = (HEAD + IND + EGD_OPEN + 'The esophagus, stomach and duodenum were normal.\n'
                 + 'Colonoscopy: ' + COURSE + 'The colonoscope was withdrawn to the colorectal anastomosis, where a tight '
                 'stricture was found. Savary dilators of 15 and 16 mm were then passed over a guidewire across the '
                 'stricture.\nImpression: Anastomotic stricture dilated.\n')
        result = run(colon, corti(('43248', span(colon, 'Savary dilators of 15 and 16 mm were then passed over a guidewire'))))
        self.assertNotEqual(proposal(result, '43248').status, 'ready')
        switched = (HEAD + IND + EGD_OPEN + 'A Savary guidewire was passed through the scope into the gastric antrum, and '
                    'the scope was withdrawn over the wire. The colonoscope was then introduced. Savary bougies were passed '
                    'across the anastomotic stricture.\n' + COL + 'Impression: Dilated.\n')
        result = run(switched, corti(('43248', span(switched, 'Savary bougies were passed across the anastomotic stricture'))))
        self.assertNotEqual(proposal(result, '43248').status, 'ready')

    def test_a_switch_in_the_first_sentence_ends_it_there(self):
        first = ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus and to the '
                 'second portion of the duodenum and then withdrawn, and the pediatric scope was introduced. A 6 mm '
                 'sessile polyp was removed with a cold snare.\n')
        text = HEAD + IND + first + COL + 'Impression: Polyp.\n'
        result = run(text, corti(('43251', span(text, 'removed with a cold snare'))))
        self.assertNotEqual(proposal(result, '43251').status, 'ready')


class CourseContinuationTests(SimpleTestCase):
    HEAD_EGD = HEAD + 'Procedure: Upper endoscopy\n'
    HEAD_COL = HEAD + 'Procedure: Colonoscopy\n'

    def extent(self, sentence, head=None, family='gi.egd'):
        text = (head or self.HEAD_EGD) + sentence + '\n'
        finding = detect.route(text, DAY).finding(family)
        return next((f.value for f in finding.facts if f.name == 'extent'), None)

    def test_a_coordinated_reach_after_an_aside_is_the_recorded_open_defect(self):
        """Walk finding 3 was OPEN (ACCURACY-RESIDUALS.md, the walk round): both forms of the continuation reader were
        refuted and dropped under the two-cycle rule, and this read as installed - the first landmark's incomplete extent.
        The structure round (2026-11-08, U14) moves the pin with its own evidence: the sentence is read as one motion of
        the instrument, segment by segment to its end (detect._motion_parse), and its furthest landmark is the extent
        exactly where the installed release reads the sentence's direct-reach twin to it (detect._motion_extent,
        tests.test_completion_motion); every control below still reads as before."""
        self.assertEqual(self.extent('The gastroscope was advanced into the stomach, which was normal on forward view and '
                                     'on retroflexion, and through the pylorus to the second portion of the duodenum.'),
                         'second part of duodenum')

    def test_a_course_stopped_or_doubted_does_not(self):
        for sentence in ('The gastroscope was advanced into the stomach but could not be passed through the pylorus to the '
                         'second portion of the duodenum.',
                         'The gastroscope was advanced into the stomach, which was not distended, and through the pylorus '
                         'to the second portion of the duodenum.',
                         # the round's refutation (acts 1, 2): a segment named after a later mention, a reach unsaid
                         'The gastroscope was advanced into the stomach, which contained a large bezoar, and the duodenum '
                         'from the pylorus to the second portion of the duodenum was inaccessible.',
                         # (long enough that the base's own reach window does not cover it: the short form reads the
                         # second portion on every tree, the recorded residual)
                         'The gastroscope was advanced into the stomach, which contained a moderate amount of retained '
                         'food despite a prolonged fast, and through the pylorus to the second portion of the duodenum, '
                         'but this was not possible.'):
            with self.subTest(sentence):
                self.assertNotEqual(self.extent(sentence), 'second part of duodenum')

    def test_a_segment_left_unexamined_is_no_reach(self):
        for sentence in ('The colonoscope was advanced to the transverse colon, leaving the colon beyond the transverse '
                         'colon to the cecum unexamined.',
                         'The colonoscope was advanced to the transverse colon, which was markedly redundant, and then to '
                         'the cecum, but this could not be confirmed.'):
            with self.subTest(sentence):
                self.assertNotEqual(self.extent(sentence, self.HEAD_COL, 'gi.colonoscopy'), 'cecum')


class BolusRemovalTests(SimpleTestCase):
    FOUND = ('Procedure: Upper endoscopy\nThe gastroscope was passed into the esophagus and advanced to the second portion '
             'of the duodenum. A large piece of partly chewed meat was impacted in the distal esophagus at 34 cm. A '
             'retrieval net was passed through the working channel. ')

    def acts(self, tail):
        text = HEAD + self.FOUND + tail + '\n'
        inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY), context_facts=None,
                                      pages=())
        return [(a.kind, a.status) for svc in inventory.services for a in svc.acts if a.kind == 'foreign_body']

    def test_the_bolus_brought_out_is_the_recorded_open_defect(self):
        """Walk finding 4 stays OPEN (ACCURACY-RESIDUALS.md, the walk round): the out-words as done participles and the
        route-bound removal were each refuted twice and dropped under the two-cycle rule, so "brought out through the
        mouth" states no removal the reader reads, as installed, and the code is held. A repair must move this pin with
        its own evidence."""
        self.assertEqual(self.acts('The bolus was captured and brought out through the mouth.'), [])
        text = HEAD + self.FOUND + 'The bolus was captured and brought out through the mouth.\n'
        result = run(text, corti(('43247', span(text, 'The bolus was captured and brought out'))))
        held = proposal(result, '43247')
        self.assertEqual(held.status, 'needs_clarification')
        self.assertEqual(flags(held), ['service.status'])

    def test_a_bolus_not_brought_out_or_pushed_is_not(self):
        for tail in ('The bolus could not be brought out.', 'The bolus was not brought out.',
                     'The bolus was unable to be brought out.', 'The bolus was captured but could not be brought out.',
                     'The bolus was pushed into the stomach.',
                     # the round's refutation (acts 3): the particle without its route out of the body
                     'The bolus pulled out of the Roth net and fell back into the esophagus.',
                     'The bolus pulled out of the net and remained impacted in the distal esophagus.',
                     # the third refutation: no endoscopic capture, a hedge, an intention, another agent
                     'The bolus was nearly brought out through the mouth, but it slipped from the net and fell back.',
                     'The bolus was regurgitated and brought out through the mouth.',
                     'The bolus was seemingly brought out through the mouth.',
                     'The bolus was to be brought out through the mouth, but it fragmented and passed into the stomach.',
                     'The bolus was grasped and brought out through the mouth by the emergency physician.',
                     # the fourth refutation: another named physician, "taken out", a bolus that fell back
                     'The bolus was grasped and brought out through the mouth by Dr. Synthetic Surgeon of '
                     'otolaryngology.',
                     'The bolus was taken out through the mouth by the emergency physician.',
                     'The bolus was captured and brought out through the mouth, but it slipped from the net in the '
                     'hypopharynx and fell back into the esophagus.'):
            with self.subTest(tail):
                self.assertNotIn(('foreign_body', 'performed'), self.acts(tail))

    def test_an_image_brought_out_is_no_act(self):
        """The round's refutation (acts 4): "brought out" in its imaging sense names no act done today."""
        text = (HEAD + 'Procedures: Upper endoscopy; colonoscopy\n' + IND + EGD_OPEN + EGD_BIOPSY + '\n'
                + 'Colonoscopy: ' + COURSE + 'The polypectomy scar was brought out with narrow band imaging.\n')
        result = run(text, corti(('45385', span(text, 'The polypectomy scar was brought out with narrow band imaging'))))
        self.assertNotEqual(proposal(result, '45385').status, 'ready')


class NegatedPassiveFailureTests(SimpleTestCase):
    DONE = 'A 7 mm polyp in the transverse colon was removed with a cold snare.'
    ATTEMPT = ('Hot snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon was attempted, but the snare '
               'could not be closed around the stalk, and the polyp was left in place.')

    def text(self, done=None, attempt=None):
        return HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the terminal ileum. ' + (done or self.DONE) \
            + ' ' + (attempt or self.ATTEMPT) + '\n'

    def reading(self, attempt=None, done=None):
        text = self.text(done, attempt)
        # one selection citing both passages, as a provider cites a code (never two selections: that is two units)
        selected = ProviderCode('selected', 'cpt', '45385', 'UNVERIFIED PROVIDER WORDING',
                                (span(text, done or self.DONE), span(text, attempt or self.ATTEMPT)))
        p = proposal(run(text, [selected]), '45385')
        return p.status, flags(p)

    def test_the_other_polyps_failed_attempt_no_longer_holds_the_done_removal(self):
        self.assertEqual(self.reading()[0], 'ready')

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

    def test_units_beyond_the_acts_shown_are_never_ready(self):
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
        self.assertEqual(self.reading(done=hedged)[0], 'needs_clarification')

    def test_outside_the_closed_form_the_doubt_stays(self):
        for attempt in ('The snare could not be closed around the stalk of the 12 mm sigmoid polyp.',
                        'Hot snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon was attempted, but the '
                        'snare could not be closed around the stalk, and the remainder of the examination was abandoned.',
                        # the round's refutation (set-aside notes): the examination's own failure is no sub-act's
                        'Snare polypectomy of a 15 mm polyp during the examination was attempted, but the examination '
                        'could not be completed, and the polyp was left in place.'):
            with self.subTest(attempt):
                self.assertNotEqual(self.reading(attempt=attempt)[0], 'ready')

    def test_a_failure_the_reader_cannot_tell_from_the_done_act_holds(self):
        """The round's refutation (set-aside notes): a removal and a failed attempt the reader cannot tell apart - the
        same site and size - are a contradiction about one lesion, never set aside."""
        for done in ('The 12 mm pedunculated sigmoid polyp was removed with a hot snare.',
                     'A 12 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'):
            with self.subTest(done):
                self.assertEqual(self.reading(done=done)[0], 'needs_clarification')
        # the same segment, another size: told apart
        self.assertEqual(self.reading(done='A 5 mm polyp in the sigmoid colon was removed with a cold snare.')[0],
                         'ready')


class DroppedSelectedPassageTests(SimpleTestCase):
    """The round's selected-passage hold is dropped: its refutation found it reading clauses about other acts in the
    act's sentence ("but was not retrieved", "and no clip was placed") and holding codes both releases read READY. These
    read as on the installed release again."""

    def test_a_clause_about_another_act_holds_nothing(self):
        for sentence in ('It was removed with a cold snare but was not retrieved.',
                         'It was removed with a cold snare, and no clip was placed.'):
            with self.subTest(sentence):
                text = (HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the terminal ileum. A 7 mm '
                        'sessile polyp was found in the transverse colon. ' + sentence + '\n')
                p = proposal(run(text, corti(('45385', span(text, 'A 7 mm sessile polyp was found in the transverse '
                                                                  'colon.')))), '45385')
                self.assertEqual(p.status, 'ready')
                self.assertEqual(next(c.status for c in p.checks if c.id == 'evidence.support'), 'warn')

    def test_the_recorded_residual_reads_as_both_releases_read_it(self):
        """ACCURACY-RESIDUALS.md (the walk round): another lesion's failure in a form the base already reads as that
        attempt's own ("..., but the snare failed; the polyp was left in place."), cited alone, beside a removal hedged in
        its own sentence - READY on the base, the installed release and this head alike."""
        hedged = ('A 6 mm polyp in the transverse colon was removed with a cold snare, but it is unclear whether the polyp '
                  'was removed or only biopsied.')
        attempt = ('Hot snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon was attempted, but the snare '
                   'failed; the polyp was left in place.')
        text = HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the terminal ileum. ' + attempt + '\n' \
            + hedged + '\n'
        self.assertEqual(proposal(run(text, corti(('45385', span(text, attempt)))), '45385').status, 'ready')


class StructureCostTests(SimpleTestCase):
    def test_the_release_is_read_once_per_paragraph(self):
        """The binding reads one scope-word pass per sentence (the round's refutation, binding 4: its first form re-read
        a sentence's tract for every scope word)."""
        repeated = ', and the scope was rotated' * 400
        text = (HEAD + IND + EGD_OPEN + 'The esophagus was inspected and the scope was rotated' + repeated
                + '. Cold forceps biopsies were obtained from the distal esophagus.\n' + COL + 'Impression: Biopsies.\n')
        self.assertTrue(structure.released(text) is not None)
        result = run(text, corti(('43239', span(text, 'Cold forceps biopsies were obtained from the distal esophagus'))))
        self.assertIsNotNone(proposal(result, '43239'))
