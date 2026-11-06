"""Completion repair (2026-11-06), U2 and U12's section fact: labelled procedure paragraphs (studio.gi.structure).

A procedure report that writes each procedure as a paragraph labelled with its service's name, after an Indications
line, reads each paragraph as that procedure: routing reads it as a procedure section of its own (the derived layout),
the documented-service reader opens a report part of the label's family, and the admission's held-section reads the
same layout. sections.layout itself never changes.

Every condition of the release (P1-P4, N1-N3) is pinned here by minimal positive and negative pairs; every F-SECTIONS
L refuter shape is re-read in a generic report, where the title cannot hold it, so that each is held by its own
condition; and equivalent wordings run in an EGD-only report, a flexible sigmoidoscopy, an upper-case label, an
untitled report and a labelled part under a "Procedure:" line. Synthetic documents only: the two retained shapes are
paraphrased as the earlier repairs' tests paraphrase them, never their real lines."""
import time

from django.test import SimpleTestCase

from studio.gi import detect, sections, structure
from studio.gi import services as gi_services
from studio.validation import reconcile
from tests.test_harness_engine import DAY, code, corti, proposal, read, run, span

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Gastroenterology Procedure Report\n'
        'Date of service: 2026-10-14\n'
        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
IND = 'Indications: Dysphagia and surveillance after adenomas.\n'
EGD_BIOPSY = 'Cold forceps biopsies were obtained from the distal esophagus.'
EGD = ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus and to the second '
       'portion of the duodenum. ' + EGD_BIOPSY + '\n')
SNARE = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
COL = 'Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. ' + SNARE + '\n'
TAIL = 'Impression: Esophageal biopsies; sigmoid polyp removed.\nPlan: Await pathology.\n'
REPORT = HEAD + IND + EGD + COL + TAIL


def why(text):
    return [reason for _, reason in structure.decisions(text)]


def families(text):
    return {f.family: f.status for f in detect.route(text, DAY).findings if f.family in detect.PROCEDURE_FAMILIES}


COLON_TAIL = 'Impression: Sigmoid polyp removed.\nPlan: Await pathology.\n'


def colonoscopy(paragraph, ind=IND, head=HEAD, tail=COLON_TAIL):
    """A generic report with one labelled colonoscopy paragraph (the title names no family, there is no procedure line,
    so only the paragraph's own conditions decide)."""
    return head + ind + paragraph + tail


class ReleasedReadingTests(SimpleTestCase):
    """The release and its three readers: routing, the documented-service reader and the admission."""

    def test_both_paragraphs_are_todays_procedures(self):
        self.assertEqual(why(REPORT), ['', ''])
        self.assertEqual(families(REPORT), {'gi.egd': 'performed', 'gi.colonoscopy': 'performed'})
        finding = {f.family: f for f in detect.route(REPORT, DAY).findings}
        self.assertEqual(finding['gi.egd'].missing, ())
        self.assertEqual(finding['gi.colonoscopy'].missing, ())

    def test_the_frozen_layout_is_unchanged_and_the_derived_one_carries_the_paragraphs(self):
        frozen = [(s.kind, s.label) for s in sections.layout(REPORT).sections]
        self.assertNotIn(('procedure', 'colonoscopy'), frozen)
        derived = structure.clinical_layout(REPORT)
        self.assertIn(('procedure', 'upper endoscopy'), [(s.kind, s.label) for s in derived.sections])
        self.assertIn(('procedure', 'colonoscopy'), [(s.kind, s.label) for s in derived.sections])
        self.assertEqual(derived.sentences, sections.layout(REPORT).sentences)
        self.assertEqual(derived.clauses, sections.layout(REPORT).clauses)
        self.assertEqual(derived.section_at(REPORT.index('Indications')).kind, 'indication')
        self.assertEqual(derived.section_at(REPORT.index('Impression')).kind, 'impression')

    def test_with_nothing_released_the_derived_layout_is_the_layout_itself(self):
        plain = HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum.\n'
        self.assertIs(structure.clinical_layout(plain), sections.layout(plain))
        self.assertEqual(structure.released(plain), ())

    def test_the_services_reader_opens_a_report_part_per_paragraph(self):
        reports = [(p.family, REPORT[p.start:p.end].split(':')[0])
                   for p in gi_services.parts(REPORT, service_date=DAY) if p.kind == 'report']
        self.assertEqual(reports, [('gi.egd', 'Upper endoscopy'), ('gi.colonoscopy', 'Colonoscopy')])
        inventory = gi_services.build(REPORT, service_date=DAY, routing=detect.route(REPORT, DAY))
        statuses = {s.family: (s.status, [(a.kind, a.status) for a in s.acts]) for s in inventory.services}
        self.assertEqual(statuses['gi.egd'], ('performed', [('biopsy', 'performed')]))
        self.assertEqual(statuses['gi.colonoscopy'], ('performed', [('snare', 'performed')]))

    def test_the_indications_other_lines_stay_the_indications_to_both_readers(self):
        # one section fact: an act told in the Indications the paragraph stood in is held by routing and the services
        # reader alike (a titled report's services part read it as the report's own), never READY on the release
        act = 'A polyp was removed from the sigmoid colon with a hot snare.'
        for title in ('Gastroenterology Procedure Report', 'Colonoscopy Report'):
            with self.subTest(title):
                text = (HEAD.replace('Gastroenterology Procedure Report', title) + 'Indications: Surveillance.\n'
                        'Preprocedure assessment: ASA II.\n' + act + '\n' + COL + 'Impression: Sigmoid polyp removed.\n')
                self.assertEqual(why(text), [''])
                pos = text.index(act)
                part = next(p for p in gi_services.parts(text, service_date=DAY) if p.start <= pos < p.end)
                self.assertEqual(part.kind, 'indication')
                self.assertEqual(reconcile.held_section(text, pos, pos + len(act)), 'indication')
                self.assertNotEqual(proposal(run(text, corti(('45385', span(text, act)))), '45385').status, 'ready')
                listed = proposal(run(text, corti(('45378', span(text, 'The colonoscope was introduced'))),
                                      [read('astra', [code(text, '45385', act)])]), '45385')
                self.assertNotEqual(listed.status, 'ready')

    def test_the_admissions_held_section_reads_the_same_layout(self):
        start = REPORT.index(EGD_BIOPSY)
        self.assertEqual(reconcile.held_section(REPORT, start, start + len(EGD_BIOPSY)), '')
        lo = REPORT.index('Dysphagia')
        self.assertEqual(reconcile.held_section(REPORT, lo, lo + 9), 'indication')

    def test_codes_are_ready_for_corti_and_a_participant_alike(self):
        codes = corti(('43239', span(REPORT, EGD_BIOPSY)), ('45385', span(REPORT, SNARE)))
        result = run(REPORT, codes)
        self.assertEqual([(proposal(result, c).bucket, proposal(result, c).status) for c in ('43239', '45385')],
                         [('selected', 'ready'), ('selected', 'ready')])
        for name in ('astra', 'fable'):
            with self.subTest(name):
                item = proposal(run(REPORT, corti(('45385', span(REPORT, SNARE))),
                                    [read(name, [code(REPORT, '43239', EGD_BIOPSY)])]), '43239')
                self.assertEqual((item.bucket, item.status, item.support['origin']), ('selected', 'ready', 'participant'))

    def test_side_1_the_doubt_quoted_is_the_cue_that_holds_the_mention(self):
        # a paragraph the release holds (N1: another place): the services reader's cue names the section that holds
        # the mention, never its own performance cue ("routing holds the family: performed: was introduced")
        held = colonoscopy('Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. '
                           'That examination was performed at an outside hospital. ' + SNARE + '\n')
        self.assertTrue(why(held)[0].startswith('N1'))
        inventory = gi_services.build(held, service_date=DAY, routing=detect.route(held, DAY))
        service = next(s for s in inventory.services if s.family == 'gi.colonoscopy')
        doubt = [c for c in service.cues if c.startswith(gi_services.ROUTING_DOUBT_CUE)]
        self.assertTrue(doubt)
        self.assertNotIn('performed:', doubt[0][len(gi_services.ROUTING_DOUBT_CUE):])
        self.assertIn('section: indication', doubt[0])


class EquivalentLayoutTests(SimpleTestCase):
    """Equivalent wordings in other layouts and families: each released, each code READY."""

    def assertReady(self, text, value, quote):
        self.assertEqual(set(why(text)), {''}, why(text))
        item = proposal(run(text, corti((value, span(text, quote)))), value)
        self.assertEqual((item.bucket, item.status), ('selected', 'ready'))

    def test_an_egd_only_report(self):
        text = (HEAD.replace('Gastroenterology Procedure Report', 'Upper Endoscopy Report') + IND + EGD
                + 'Impression: Esophageal biopsies.\n')
        self.assertReady(text, '43239', EGD_BIOPSY)

    def test_a_flexible_sigmoidoscopy(self):
        text = colonoscopy('Flexible sigmoidoscopy: The sigmoidoscope was advanced to the descending colon. ' + SNARE
                           + '\n', tail='Impression: Sigmoid polyp removed.\n')
        self.assertReady(text, '45338', SNARE)

    def test_an_upper_case_label(self):
        self.assertReady(colonoscopy(COL.replace('Colonoscopy:', 'COLONOSCOPY:')), '45385', SNARE)

    def test_an_emphasised_label(self):
        self.assertReady(colonoscopy(COL.replace('Colonoscopy:', '**Colonoscopy:**')), '45385', SNARE)

    def test_an_untitled_report_of_fields_only(self):
        text = ('Date of service: 2026-10-14\nIndications: Dysphagia.\nUpper endoscopy: The gastroscope was advanced to '
                'the second portion of the duodenum. ' + EGD_BIOPSY + '\n')
        self.assertReady(text, '43239', EGD_BIOPSY)

    def test_the_retained_shape_paraphrased_a_frame_of_todays_steps(self):
        # 39f0ac49's colonoscopy opens on today's step ("After repositioning,") and an instrument kind ("pediatric")
        text = colonoscopy('Colonoscopy: After repositioning, a pediatric colonoscope was introduced through the anus and '
                           'advanced to the cecum, identified by the appendiceal orifice and ileocecal valve; photographs '
                           'were obtained. ' + SNARE + ' The examination was otherwise normal on direct and retroflexed '
                           'views. The patient tolerated both procedures and was transferred to recovery in stable '
                           'condition.\n')
        self.assertReady(text, '45385', SNARE)

    def test_the_retained_shape_paraphrased_a_future_word_about_a_sub_act(self):
        # d44a77b3's "not resected today; it will be referred ...": the resection's future, never the examination's
        text = colonoscopy('Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. '
                           + SNARE + ' A separate 25 mm flat lesion in the transverse colon was marked with submucosal '
                           'tattoo and not resected today; it will be referred for endoscopic mucosal resection.\n')
        self.assertReady(text, '45385', SNARE)

    def test_a_labelled_part_under_a_procedure_line(self):
        text = (HEAD.replace('Gastroenterology Procedure Report', 'Procedure report (fictional)')
                + 'Procedure: Upper endoscopy and colonoscopy\n'
                'UPPER ENDOSCOPY: The gastroscope was advanced to the second part of the duodenum.\n' + EGD_BIOPSY + '\n'
                'COLONOSCOPY: The colonoscope was advanced to the cecum.\n'
                'A foreign body was seen in the transverse colon. The foreign body was removed with a Roth net.\n')
        self.assertReady(text, '45379', 'The foreign body was removed with a Roth net.')

    def test_the_consent_sentence_naming_both_families_holds_nothing(self):
        text = colonoscopy(COL, ind=IND + 'Risks and benefits of upper endoscopy and colonoscopy were discussed.\n')
        self.assertEqual(why(text), [''])

    def test_a_plan_or_an_impression_naming_the_family_holds_nothing(self):
        text = colonoscopy(COL, tail='Impression: Normal colonoscopy apart from the polyp.\n'
                                     'Plan: Repeat colonoscopy in 3 years.\n')
        self.assertEqual(why(text), [''])


class HeldConditionTests(SimpleTestCase):
    """Each condition holds its own minimal counterexample, beside a control that is released."""

    def assertHeld(self, text, condition):
        reasons = why(text)
        self.assertTrue(reasons and all(r.startswith(condition) for r in reasons), reasons)
        self.assertEqual(structure.released(text), ())
        self.assertIs(structure.clinical_layout(text), sections.layout(text))

    def test_p1_never_a_clinic_office_telehealth_anesthesia_or_preoperative_note(self):
        for title in ('Gastroenterology Clinic Note', 'Gastroenterology office visit', 'Gastroenterology Telehealth Note',
                      'Anesthesia Procedure Note', 'Gastroenterology Note', 'Colonoscopy Report (Preop)',
                      'Colonoscopy Report (Copy)', 'Pre-procedure History and Physical', 'Colonoscopy Orders'):
            with self.subTest(title):
                self.assertHeld(colonoscopy(COL, head=HEAD.replace('Gastroenterology Procedure Report', title)), 'P1')

    def test_p1_an_untitled_head_must_be_a_procedure_reports_own_fields(self):
        ok = 'Date of service: 2026-10-14\nIndications: Dysphagia.\n' + COL
        self.assertEqual(why(ok), [''])
        self.assertHeld('Date of service: 2026-10-14\nReferral source: Outside clinic\nIndications: Dysphagia.\n' + COL,
                        'P1')
        self.assertHeld('Date of service: 2026-10-14\nFollow-up visit\nIndications: Dysphagia.\n' + COL, 'P1')

    def test_p1_an_office_e_m_structure(self):
        self.assertHeld(colonoscopy(COL, tail='Medical decision making: Moderate.\nPlan: Await pathology.\n'), 'P1')
        self.assertHeld(colonoscopy(COL, ind='Reason for visit: Follow-up.\n'), 'P1')

    def test_p2_the_first_sentence_is_the_scopes_own_course(self):
        for label, paragraph in {
            'fronted place': 'Colonoscopy: At the referring hospital, the colonoscope was advanced to the cecum.\n',
            'fronted time': 'Colonoscopy: Previously, the colonoscope was introduced through the anus.\n',
            'aside after the label': 'Colonoscopy: (outside) The colonoscope was advanced to the cecum.\n',
            'proper-named place': 'Colonoscopy: At Synthetic Valley Medical Center, the colonoscope was advanced to the '
                                  'cecum.\n',
            'future': 'Colonoscopy: The colonoscope will be advanced to the cecum.\n',
            'negated': 'Colonoscopy: The colonoscope was not advanced beyond the sigmoid colon.\n',
            'no course': 'Colonoscopy: Two adenomas were removed.\n',
            'a bare endoscope': 'Colonoscopy: The endoscope was advanced to the cecum.\n',
            'another family\'s instrument': 'Colonoscopy: The gastroscope was advanced to the cecum.\n',
        }.items():
            with self.subTest(label):
                self.assertHeld(colonoscopy(paragraph + SNARE + '\n'), 'P2')

    def test_p2_a_label_line_run_on_from_the_line_above(self):
        self.assertEqual(structure.released(HEAD + 'Indications: Surveillance after an outside\n' + COL), ())

    def test_p3_the_title_and_the_procedure_line_name_the_family(self):
        egd_report = HEAD.replace('Gastroenterology Procedure Report', 'Upper Endoscopy Report')
        self.assertHeld(colonoscopy(COL, head=egd_report), 'P3')
        self.assertHeld(HEAD + 'Procedure: Upper endoscopy\n' + IND + COL, 'P3')
        self.assertHeld(HEAD + 'Procedure: Colonoscopy (2019)\n' + IND + COL, 'P3')

    def test_p3_a_second_narrative_or_another_section_of_the_family(self):
        self.assertHeld(colonoscopy(COL + COL), 'P3')
        own = HEAD + IND + COL + 'Findings:\nThe colonoscope was advanced to the cecum and the polyp was seen.\n'
        self.assertHeld(own, 'P3')
        undeclared = HEAD + IND + COL + 'Procedure:\nThe gastroscope was advanced to the second portion of the duodenum.\n'
        self.assertHeld(undeclared, 'P3')

    def test_p3_the_tract_the_paragraphs_and_the_report_narrate(self):
        # the refuter L5-7: an EGD paragraph, then a Findings line about the colon, held (no 43251 READY)
        findings = (HEAD + 'Indications: Dysphagia and anemia.\nUpper endoscopy: The gastroscope was advanced into the '
                    'esophagus and to the second portion of the duodenum.\nFindings: A 9 mm sigmoid colon polyp was '
                    'removed with a cold snare.\nImpression: Sigmoid polyp removed.\n')
        self.assertHeld(findings, 'P3')
        quote = 'A 9 mm sigmoid colon polyp was removed with a cold snare.'
        self.assertNotEqual(proposal(run(findings, corti(('43251', span(findings, quote)))), '43251').status, 'ready')
        own_misfit = (HEAD + IND + 'Upper endoscopy: The gastroscope was advanced to the second portion of the '
                      'duodenum. A polyp in the sigmoid colon was removed with a cold snare.\n')
        self.assertHeld(own_misfit, 'P3')
        quote = 'A polyp in the sigmoid colon was removed with a cold snare.'
        self.assertNotEqual(proposal(run(own_misfit, corti(('43251', span(own_misfit, quote)))), '43251').status, 'ready')

    def test_p4_where_the_paragraph_stands(self):
        self.assertHeld(HEAD + 'Reason for referral:\n' + COL, 'P4')
        self.assertHeld(HEAD + 'Prior procedures:\n' + COL, 'P4')
        self.assertHeld(HEAD + 'Plan:\n' + COL, 'P4')
        self.assertHeld(HEAD + 'Indications:\n' + COL, 'P4')
        self.assertHeld(HEAD + 'Sedation: Monitored anesthesia care.\n' + COL, 'P4')
        self.assertHeld(HEAD + 'Indications: Surveillance.\nHer earlier study:\n' + COL, 'P4')
        # a paragraph after one that is not released stays held, whatever it says
        blocked_first = HEAD + IND + EGD.replace('esophagus and', 'esophagus at an outside hospital and') + COL
        self.assertEqual([r[:2] for r in why(blocked_first)], ['N1', 'P4'])

    def test_n1_the_f_sections_l_refuters_each_held_by_their_own_condition(self):
        for label, later in {
            'a date': 'This examination was performed on 2026-09-02.',
            'today\'s own date (the safe side)': 'This examination was performed on 2026-10-14.',
            'a month': 'This examination was performed in March.',
            'weeks earlier': 'This examination was performed three weeks earlier.',
            'months before': 'This examination was performed two months before.',
            'a last visit': 'This examination was performed at her last visit.',
            'the week before': 'This examination was performed the week before.',
            'a separate day': 'This examination was performed on a separate day.',
            'last Tuesday': 'That examination took place last Tuesday.',
            'an outside hospital': 'That examination was performed at an outside hospital.',
            'another agent': 'The polyp was removed by a different gastroenterologist.',
            'a named agent and a year': 'It was reviewed by Dr. Jones in 2019.',
            'another source': 'The findings are as documented in her chart.',
            'the examination named with its time': 'The patient had this colonoscopy when she was 50.',
            'a clause about the examination': 'The polyp was removed; the examination took place on a separate day.',
        }.items():
            with self.subTest(label):
                paragraph = ('Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. '
                             + later + ' ' + SNARE + '\n')
                self.assertHeld(colonoscopy(paragraph), 'N1')

    def test_n2_a_later_sentence_refers_back_to_the_family(self):
        self.assertHeld(colonoscopy(COL + 'Note: the colonoscopy above was performed in 2025 and is copied for '
                                          'reference.\n'), 'N2')
        self.assertHeld(colonoscopy(COL + 'Note: this colonoscopy belongs to another patient.\n'), 'N2')

    def test_n3_the_indication_announces_the_paragraph(self):
        for label, ind in {
            'the index occasion follows': 'Indications: Surveillance; the findings of the index colonoscopy follow.\n',
            'see below': 'Indications: Surveillance; see below.\n',
            'a past account named by routing': 'Indications: Surveillance. She had a colonoscopy, described next.\n',
            'an introducing line': 'Indications: Surveillance, as recounted:\n',
            'an unterminated run-on': 'Indications: Surveillance after an outside\n',
        }.items():
            with self.subTest(label):
                self.assertHeld(colonoscopy(COL, ind=ind), 'N3')


class CostTests(SimpleTestCase):
    """The release is linear in the text: every per-paragraph question is answered by bisection."""

    def timed(self, text):
        started = time.monotonic()
        structure.decisions(text)
        structure.clinical_layout(text)
        return time.monotonic() - started

    def test_many_label_lines_and_a_long_paragraph(self):
        many = HEAD + IND + COL * 4000 + TAIL
        self.assertLess(self.timed(many), 8.0)
        self.assertEqual(structure.released(many), ())  # P3: a second narrative of the family
        long = HEAD + IND + 'Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. ' \
            + (SNARE + ' ') * 4000 + '\n' + COLON_TAIL
        self.assertLess(self.timed(long), 8.0)
        self.assertEqual(len(structure.released(long)), 1)

    def test_doubling_the_text_at_most_about_doubles_the_work(self):
        def build(n):
            return HEAD + IND + (EGD.replace('Upper endoscopy: ', '') * n) + COL + TAIL
        small, large = build(1500), build(3000)
        self.timed(small)  # warm the regex caches
        a = self.timed(small + ' ')
        b = self.timed(large + ' ')
        self.assertLess(b, max(0.5, a * 3.0))


class SelfRefutationTests(SimpleTestCase):
    """The author's own refutation pass over the release (a differential battery read on this tree and on the base
    b452c6c4): every wording that leaked a READY the base did not have is pinned held here by the rule that now holds
    it, and every real-world shape that must keep releasing is pinned released."""

    def assertHeldBy(self, text, condition):
        reasons = why(text)
        self.assertTrue(reasons and all(r.startswith(condition) for r in reasons), reasons)

    def test_n1_other_times_by_an_age_a_past_then_or_a_life_event(self):
        for later in ('All of this happened when she lived abroad.', 'Those polyps were removed then.',
                      'He had this done at age 50.', 'The patient was 50 years old at the time.'):
            with self.subTest(later):
                self.assertHeldBy(colonoscopy(COL.rstrip('\n') + ' ' + later + '\n'), 'N1')
        for first in ('Colonoscopy: The colonoscope was advanced to the cecum back then.',
                      'Colonoscopy: The colonoscope was advanced to the cecum when she was 50.',
                      'Colonoscopy: The colonoscope was advanced to the cecum at another site.'):
            with self.subTest(first):
                self.assertHeldBy(colonoscopy(first + ' ' + SNARE + '\n'), 'N1')
        self.assertHeldBy(colonoscopy('Colonoscopy: The colonoscope was introduced through the anus and advanced to the '
                                      'cecum. Back then, a 6 mm polyp in the sigmoid colon was removed with a cold '
                                      'snare.\n'), 'N1')

    def test_n1_a_performed_examination_says_nothing_after_its_allow_listed_manner(self):
        self.assertHeldBy(colonoscopy(COL.rstrip('\n') + ' It was performed under general anesthesia in the ICU.\n'),
                          'N1')
        self.assertEqual(why(colonoscopy(COL.rstrip('\n') + ' The procedure was performed under monitored anesthesia '
                                                            'care.\n')), [''])

    def test_n2_a_later_denial_or_another_occasion_of_the_family(self):
        for tail in ('Impression: No colonoscopy was performed today.\n', 'Impression: Colonoscopy aborted.\n',
                     'Impression: Colonoscopy pending.\n', 'Impression: Colonoscopy deferred.\n',
                     'Plan: The colonoscopy above was done last year.\n'):
            with self.subTest(tail):
                self.assertHeldBy(colonoscopy(COL, tail=tail), 'N2')

    def test_n3_an_indication_that_reviews_discusses_or_records(self):
        for ind in ('Indications: Review of colonoscopy.\n', 'Indications: Second opinion on her colonoscopy.\n',
                    'Indications: To review the colonoscopy she had.\n', 'Indications: Discussion of colonoscopy '
                    'results.\n', 'Indications: Records review.\n', 'Indications: Colonoscopy images reviewed.\n',
                    'Indications: Hx colonoscopy.\n', 'Indications: Follow-up after colonoscopy.\n'):
            with self.subTest(ind):
                self.assertHeldBy(colonoscopy(COL, ind=ind), 'N3')

    def test_the_indications_ordinary_shapes_still_release(self):
        egd_and_tail = (EGD, 'Impression: Esophageal biopsies; sigmoid polyp removed.\n')
        for ind, two in (('Indications: Screening colonoscopy.\n', False),
                         ('Indications: Colonoscopy for iron deficiency anemia.\n', False),
                         ('Indications: Diagnostic colonoscopy for hematochezia.\n', False),
                         ('Indications: Screening; no prior colonoscopy.\n', False),
                         ('Indications: Upper endoscopy and colonoscopy for anemia.\n', True),
                         ('Indications: Anemia.\nInformed consent was obtained for upper endoscopy and colonoscopy.\n',
                          True)):
            with self.subTest(ind):
                text = (HEAD + ind + egd_and_tail[0] + COL + egd_and_tail[1]) if two else colonoscopy(COL, ind=ind)
                self.assertEqual(set(why(text)), {''})
                self.assertEqual(proposal(run(text, corti(('45385', span(text, SNARE)))), '45385').status, 'ready')

    def test_closing_sentences_and_a_wrapped_instrument_kind_still_release(self):
        closing = colonoscopy(COL.rstrip('\n') + ' The quality of the bowel preparation was good. There were no '
                              'complications from the procedure. The patient tolerated the procedure well.\n')
        wrapped = colonoscopy('Colonoscopy: After repositioning, a pediatric\ncolonoscope was introduced through the '
                              'anus and advanced to the cecum. ' + SNARE + '\n')
        for text in (closing, wrapped):
            with self.subTest(text[200:260]):
                self.assertEqual(why(text), [''])
                self.assertEqual(proposal(run(text, corti(('45385', span(text, SNARE)))), '45385').status, 'ready')

    def test_an_eus_paragraph(self):
        text = ('EUS Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
                'Indications: Pancreatic cyst.\nEUS: The echoendoscope was advanced to the second portion of the '
                'duodenum. Fine-needle aspiration of the pancreatic head cyst was performed.\n'
                'Impression: Pancreatic head cyst sampled.\n')
        self.assertEqual(why(text), [''])
        quote = 'Fine-needle aspiration of the pancreatic head cyst was performed.'
        self.assertEqual(proposal(run(text, corti(('43242', span(text, quote)))), '43242').status, 'ready')

    def test_n1_another_familys_service_named_inside_the_paragraph(self):
        # the derived layout reads the paragraph as the label's procedure section: another service named there would
        # read as performed too, so the paragraph is held (its frame of today's steps apart)
        for later in ('Sigmoidoscopy showed diverticula.', 'An EGD was also performed.', 'FS was not needed.'):
            with self.subTest(later):
                text = colonoscopy(COL.rstrip('\n') + ' ' + later + '\n')
                self.assertHeldBy(text, 'N1')
                self.assertNotIn('performed', {f.family: f.status for f in detect.route(text, DAY).findings}.values())

    def test_p2_a_frame_naming_a_procedure_whose_paragraph_is_not_released(self):
        # "After the upper endoscopy," is today's sequence only beside today's EGD paragraph: with that paragraph held
        # (N1, another place), the colonoscopy's frame lends the EGD nothing and is held too
        frame = ('Colonoscopy: After the upper endoscopy, the colonoscope was introduced through the anus and advanced '
                 'to the cecum. ' + SNARE + '\n')
        both = HEAD + IND + EGD + frame + 'Impression: Esophageal biopsies; sigmoid polyp removed.\n'
        self.assertEqual(why(both), ['', ''])
        # the EGD paragraph held by its own P2 (a bare "endoscope" names no family), with no hold signal of its own
        held_egd = EGD.replace('The gastroscope', 'The endoscope')
        first = HEAD + IND + frame + held_egd + 'Impression: Esophageal biopsies; sigmoid polyp removed.\n'
        reasons = why(first)
        self.assertEqual([r[:2] for r in reasons], ['P2', 'P2'], reasons)
        self.assertIn('its frame names a procedure', reasons[0])
        self.assertEqual(structure.released(first), ())


class TodaysStepsAndStructureTests(SimpleTestCase):
    """Patch 4 of the author's own pass: a temporal adjunct anchors to today's procedure steps, decades and life stages
    are other times, and the report's own structure resumes where a released paragraph ends."""

    def assertHeldBy(self, text, condition):
        reasons = why(text)
        self.assertTrue(reasons and all(r.startswith(condition) for r in reasons), reasons)

    def test_a_temporal_adjunct_no_step_of_today_anchors_holds(self):
        for adjunct in ('during her pregnancy', 'after her surgery', 'while traveling', 'following her transplant',
                        'upon her arrival from abroad', 'at the time of her diagnosis', 'in the 1990s', 'in childhood'):
            with self.subTest(adjunct):
                self.assertHeldBy(colonoscopy('Colonoscopy: The colonoscope was advanced to the cecum ' + adjunct + '. '
                                              + SNARE + '\n'), 'N1')

    def test_a_temporal_adjunct_of_todays_own_steps_still_releases(self):
        for later in ('The cecum was photographed after lavage.', 'A second polyp was seen during withdrawal.',
                      'Retroflexion was performed upon withdrawal of the scope.',
                      'The mucosa was inspected after the polypectomy.'):
            with self.subTest(later):
                text = colonoscopy(COL.rstrip('\n') + ' ' + later + '\n')
                self.assertEqual(why(text), [''])

    def test_the_reports_structure_resumes_after_the_paragraph(self):
        # a free line right after the paragraph may speak of it: held; a heading, a label or the end: released
        # the paragraph runs to the next layout section or label line, a blank line included: what lies after a blank
        # line is the paragraph's own text, read by N1 ("The above is not mine.": a back-reference subject)
        self.assertHeldBy(colonoscopy(COL + 'Not from this visit.\n'), 'N1')
        self.assertHeldBy(colonoscopy(COL + '\nThe above is not mine.\n'), 'N1')
        # a label line ends it, and the report's structure does not resume there
        self.assertHeldBy(colonoscopy(COL + 'Note: not from this visit.\n'), 'N2')
        self.assertHeldBy(colonoscopy(COL + 'Comment: copied.\n'), 'N2')
        self.assertEqual(why(colonoscopy(COL, tail='')), [''])
        self.assertEqual(why(colonoscopy(COL, tail='Withdrawal time: 8 minutes.\nImpression: Polyp removed.\n')), [''])
        self.assertHeldBy(colonoscopy(COL, tail='Prior colonoscopy: 2019, adenomas.\nImpression: Polyp removed.\n'), 'N2')
        self.assertEqual(why(colonoscopy(COL, tail='\n\nImpression: Polyp removed.\n')), [''])


class NarrativePlaceTests(SimpleTestCase):
    """Patch 5 of the author's own pass (N1): a labelled paragraph's place adjuncts anchor to today's anatomy, lesions
    or handling, and nobody's reported speech is in it. Read in the paragraph only: an indication, impression or plan
    keeps its own readers ("in a patient with", "follow up in clinic", "at the time of examination")."""

    def assertHeldBy(self, text, condition):
        reasons = why(text)
        self.assertTrue(reasons and all(r.startswith(condition) for r in reasons), reasons)

    def paragraph(self, sentence):
        return colonoscopy('Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. '
                           + sentence + '\n')

    def test_another_place_time_or_source_in_the_paragraph_holds(self):
        for tail in ('on the cruise ship', 'in her twenties', 'at home', 'at the edge of the city', 'in high school',
                     'in the area where she was traveling', "in the patient's home", 'on vacation', 'aboard the ship',
                     'in her twenties from the sigmoid colon', 'in the endoscopy suite of the ship', 'at the bedside',
                     'at that point', 'on the way to the airport', 'at the site where she works',
                     # the object is read to a word's end, never a cut word ("base|ment" is not "base")
                     'in the satisfactory satisfactory satisfactory satisfactory basement',
                     # other place prepositions, a coordinated object, and an idiom's own object
                     'from her home', 'inside the ambulance', 'into the ICU', 'within her house', 'toward the airport',
                     'in the sigmoid colon and the basement', 'in the sigmoid colon wall and her home',
                     'in the endoscopy suite and the cruise ship', 'in the context of her vacation'):
            with self.subTest(tail):
                self.assertHeldBy(self.paragraph('A 6 mm polyp was removed with a cold snare ' + tail + '.'), 'N1')
        for sentence in ('A 6 mm polyp in the sigmoid colon was removed with a cold snare, as she recalls.',
                         'The patient reports that a 6 mm polyp in the sigmoid colon was removed with a cold snare.',
                         'Her husband states a 6 mm polyp in the sigmoid colon was removed with a cold snare.'):
            with self.subTest(sentence):
                self.assertHeldBy(self.paragraph(sentence), 'N1')

    def test_todays_anatomy_handling_and_measurements_still_release(self):
        for sentence in ('Polyps were removed in the right colon, in the transverse colon, and in the left colon.',
                         'The rectum was examined on direct and retroflexed views.',
                         'A 6 mm polyp was removed in two pieces and sent in separate jars.',
                         'The patient was placed in the left lateral decubitus position.',
                         'A 20 mm polyp was removed in a piecemeal fashion; clips were placed at the polypectomy site.',
                         'A clip was placed at the base of the polyp.',
                         'Small erosions were seen in the mid and distal rectum.',
                         'A 6 mm polyp was removed in the rest of the colon, measuring 6 mm in maximal dimension.',
                         'At the end of withdrawal, the patient was in stable condition.',
                         'A tattoo was placed at 30 cm in the 3 o\'clock position, in addition to the clip.',
                         'Surveillance is recommended in 3 to 5 years.',
                         'The cecum was identified by the appendiceal orifice, at this time, on NBI.',
                         'On careful inspection, biopsies were taken in a random fashion; clips were placed at the site.',
                         'The cecum was reached at 10:05 and the lesion was removed en bloc in a single piece.',
                         'Saline was injected into the submucosa and the polyp was retrieved from the suction trap.',
                         'The polyp was captured in a Roth net; biopsies were taken from multiple sites.',
                         'The mucosa was within normal limits from the rectum to the cecum.',
                         'Polyps were removed in the sigmoid colon and the remainder of the colon was normal.',
                         'Two polyps were removed in the cecum and the ascending colon in order to clear the colon.'):
            with self.subTest(sentence):
                self.assertEqual(why(self.paragraph(sentence)), [''])

    def test_the_indication_impression_and_plan_keep_their_own_readers(self):
        # the retained shapes paraphrased: an indication timing the request to the examination, a patient on a drug in
        # the impression, home in the plan; none of them is the paragraph's own account, and each would hold inside it
        text = colonoscopy(COL, ind='Indications: Iron deficiency anemia noted at the time of examination planning, '
                                    'in a patient with a family history.\n',
                           tail='Impression: Normal colonoscopy in a patient on aspirin; polyp removed.\n'
                                'Plan: Resume diet at home after the procedure.\n')
        self.assertEqual(why(text), [''])
        for inside in ('in a patient on aspirin', 'at home'):
            with self.subTest(inside):
                self.assertHeldBy(self.paragraph('A 6 mm polyp was removed with a cold snare ' + inside + '.'), 'N1')

    def test_the_time_reader_still_reads_a_time_heading_the_object(self):
        for tail in ('in 2019', 'at that time', 'in March', 'in the past'):
            with self.subTest(tail):
                self.assertHeldBy(self.paragraph('A 6 mm polyp was removed with a cold snare ' + tail + '.'), 'N1')

    def test_the_place_reading_is_bounded(self):
        sentence = 'A polyp was removed in the sigmoid colon. ' * 400
        text = self.paragraph(sentence)
        started = time.perf_counter()
        structure._unanchored_place(text, 0, len(text))
        self.assertLess(time.perf_counter() - started, 2.0)
