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
