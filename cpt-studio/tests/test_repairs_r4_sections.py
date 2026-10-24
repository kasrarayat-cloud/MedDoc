"""Regressions for refutation round 4 over GI section structure (round "4b", studio/gi/sections.py).

Each class reproduces one confirmed round-4 finding (structure:N or release:N in the round-4 triage) from its exact
input, adds the wordings its verifier listed, and pins controls in both directions. The rule of round 4b is that a
wording or layout rule may only hold; it may restore the reading an input had at R3B-BASE (d05326ef) or at 57b4b3747,
and never newly excludes or releases otherwise. Where a repair restores R3B-BASE, the test says so.

Routing runs for real, for the document's own service date and through the JSON round trip the pipeline applies; the
real validation engine assesses provider-shaped selections against an empty in-memory reference. Synthetic text only.
"""
import unittest

from studio.gi.context import extract_context
from studio.gi.sections import layout
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode
from studio.validation.engine import assess
from tests.test_repairs_r3_sections import (EMR_LINE, HEADER, NOT_TODAY, OFFICE, POSITIVE, clarified, emr_note, fact_value,
                                            family, read, ready, routed, run_engine, service_date, span, starts_a_sentence,
                                            word_document)


def kind_at(text, phrase):
    return layout(text).section_at(text.index(phrase)).kind


def encounter_warnings(text, picks):
    """The ids of the encounter-level checks that warn or fail, for provider-shaped picks (code, phrase)."""
    codes = []
    for index, (code, phrase) in enumerate(picks):
        start, end = span(text, phrase)
        codes.append(ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED',
                                  evidence=(EvidenceSpan(0, start, end, text[start:end], True),), index=index))
    result = assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=extract_context(text), routing=routed(text),
                    normalized=NormalizedResponse('replay', 'test', codes=tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=service_date(text),
                    provider_status='succeeded', extraction_status='ok')
    return {check.id for check in result.encounter_checks if check.status in ('warn', 'fail')}


# --- structure:17 / release:2: a numbered or bulleted plan label, and a plan label that does not end with its noun ---

STRUCTURE17_EMR = 'EMR of the 3 cm ascending colon lesion at a tertiary center'


def structure17_note(label):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n1. Findings\nThe colonoscope was advanced to the cecum. '
            'A 6 mm polyp was removed with a cold snare. A 3 cm flat ascending colon lesion was tattooed.\n' + label + '\n'
            + STRUCTURE17_EMR + '\n')


RELEASE2_EMR = 'EMR of the ascending colon lesion at a tertiary center.'
RELEASE2_CECUM = '1. The colonoscope was advanced to the cecum.'


def release2_note(label):
    return (HEADER + 'Procedure: Colonoscopy\nIndication: Positive FIT.\nFindings:\n' + RELEASE2_CECUM + '\n2. A 25 mm lateral '
            'spreading tumor in the ascending colon was tattooed and not removed.\n3. Small internal hemorrhoids.\n' + label + '\n'
            + RELEASE2_EMR + '\n')


class PlannedEmrAssertions:
    def assert_planned_emr_not_ready(self, text, emr, code_kind='plan'):
        """The planned EMR reads planned under a plan section, gives no EMR fact and is never a ready 45390 (it is
        excluded as planned, reinstatable, as at R3B-BASE)."""
        self.assertEqual(kind_at(text, emr), code_kind)
        self.assertEqual(read(text, emr)[0], 'planned')
        self.assertNotIn('EMR', fact_value(text, 'gi.colonoscopy', 'interventions') or '')
        proposal = run_engine(text, [('45390', emr)])['45390']
        self.assertFalse(ready(proposal))
        self.assertEqual((proposal.bucket, proposal.reinstatable), ('excluded', True))


class Structure17NumberedPlanLabelTests(PlannedEmrAssertions, unittest.TestCase):
    """structure:17 (a round-3b over-correction, 75a3cfac7) - a numbered, lettered or bulleted line that names a plan
    section ("2. Upcoming procedures") opens a plan section again, as it did at R3B-BASE: the planned EMR on the next
    line is never a ready 45390 with an EMR fact."""

    CLAIMED = ('2. Upcoming procedures', '2. Scheduled procedures', 'B. Future procedures', '2) Upcoming procedures',
               '* Upcoming procedures')

    def test_the_claimed_labels(self):
        for label in self.CLAIMED:
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(structure17_note(label), STRUCTURE17_EMR)

    def test_the_cecum_and_the_polypectomy_above_the_label_still_read(self):
        text = structure17_note('2. Upcoming procedures')
        polyp = 'A 6 mm polyp was removed with a cold snare.'
        self.assertEqual(read(text, polyp)[0], 'performed')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))

    def test_the_controls_still_plan(self):
        for label in ('Upcoming procedures', '2. Upcoming procedures:', '2. Plan', '2. Planned procedures', '## Upcoming procedures',
                      '**Upcoming procedures**'):
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(structure17_note(label), STRUCTURE17_EMR)

    def test_the_lines_round_3b_pinned_as_findings(self):
        """Round 3b's test pinned these before the planned EMR as findings content (its verifier: a false green that never
        asserted the 45390 outcome); they open a plan, as at R3B-BASE."""
        for label in ('3. Upcoming procedures', 'b) Further evaluation', '* Upcoming procedures'):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(text, EMR_LINE)


class Release2PlanLabelsTests(PlannedEmrAssertions, unittest.TestCase):
    """release:2 (a round-3b new defect, 75a3cfac7) - a numbered or bulleted plan label, and a plan label whose first word
    names the plan ("Procedures planned", "Plan going forward"), open a plan section again, as at R3B-BASE: the planned
    EMR is never a ready 45390 with an EMR fact, while the cecum item above it still reads performed."""

    CLAIMED = ('4. Upcoming procedures', '* Upcoming procedures', 'Procedures planned', 'Plan going forward')
    LISTED = ('4) Upcoming procedures', 'D. Upcoming procedures', '4. Procedures planned', '4. Plan going forward',
              'Plan moving forward', 'Procedures recommended', 'Procedures scheduled', 'Plan from here')

    def test_the_claimed_and_listed_labels(self):
        for label in self.CLAIMED + self.LISTED:
            text = release2_note(label)
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(text, RELEASE2_EMR)
                self.assertTrue(ready(run_engine(text, [('45378', RELEASE2_CECUM)])['45378']))

    def test_in_prose_findings(self):
        for label in ('Plan going forward', 'Procedures planned', 'Plan moving forward', 'Procedures recommended',
                      'Procedures scheduled', 'Plan from here', '* Upcoming procedures'):
            text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 25 mm lateral spreading '
                    'tumor in the ascending colon was tattooed and not removed.\n' + label + '\n' + RELEASE2_EMR + '\n')
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(text, RELEASE2_EMR)

    def test_a_word_heading_paragraph(self):
        for label in ('Plan going forward', 'Procedures planned'):
            text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                                  ('Procedure: Colonoscopy', None),
                                  ('Findings: The colonoscope was advanced to the cecum. A 25 mm lateral spreading tumor in the '
                                   'ascending colon was tattooed and not removed.', None),
                                  (label, 'Heading 2'), (RELEASE2_EMR, None)])
            with self.subTest(label=label):
                self.assertIn('\n' + label + '\n', text)
                self.assert_planned_emr_not_ready(text, RELEASE2_EMR)

    def test_lines_that_only_start_with_the_words_stay_content(self):
        """A line whose first word is "Procedure(s)" or "Plan" is a plan label only with a plan word in it, and never a
        title, a service, an act or a sentence."""
        for line in ('Procedures tolerated well', 'Procedure note for next visit', 'Procedure complicated by mild bleeding',
                     'Procedures were uneventful', 'Planning stage', 'Procedure with cold snare polypectomy'):
            text = release2_note(line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, RELEASE2_EMR), 'findings')

    def test_round3_routing2_statements_stay_content(self):
        """routing:2 (round 3): a numbered findings item that is a statement is never a label, so the polypectomy after it
        stays a ready 45385; the noun-last rule keeps these content without the list-item guard."""
        polyp = '6 mm sigmoid polyp removed with cold snare.'
        for item in ('Further workup recommended', 'Further evaluation recommended', 'Surgical management recommended',
                     'Further imaging recommended', 'Follow-up imaging advised', 'Previous treatments failed',
                     'Prior therapy ineffective', 'Prior radiation therapy changes', 'Genetic testing recommended', 'History of AS'):
            text = (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings:\n1. The colonoscope was advanced '
                    'to the cecum.\n2. A 3 cm ascending colon mass, biopsied and tattooed.\n3. ' + item + '\n4. ' + polyp + '\n')
            with self.subTest(item=item):
                self.assertEqual(kind_at(text, polyp), 'findings')
                self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))

    def test_a_numbered_plan_label_item_reads_as_at_r3b_base(self):
        """The cost of restoring R3B-BASE, accepted and stated: a numbered item that is itself a plan label ("3. Upcoming
        procedures", "3. Further evaluation") opens a plan section even when the next line is the next item of the same
        list, so the performed item after it is excluded as planned (reinstatable, for a reviewer), never ready. Round
        3b's list-item guard read it as content, and that guard is what released the planned EMR above."""
        polyp = '6 mm sigmoid polyp removed with cold snare.'
        for item in ('Further evaluation', 'Upcoming procedures'):
            text = (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings:\n1. The colonoscope was advanced '
                    'to the cecum.\n2. A 3 cm ascending colon mass, biopsied and tattooed.\n3. ' + item + '\n4. ' + polyp + '\n')
            with self.subTest(item=item):
                self.assertEqual(kind_at(text, polyp), 'plan')
                proposal = run_engine(text, [('45385', polyp)])['45385']
                self.assertFalse(ready(proposal))
                self.assertNotIn(read(text, polyp)[0], POSITIVE)


# --- structure:4: a colon-less line that ends with a section noun but reads as a phrase ---------------------------------

STRUCTURE4_POLYP = '6 mm sigmoid polyp removed with cold snare'


def structure4_note(line, polyp=STRUCTURE4_POLYP):
    return (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings:\nThe colonoscope was advanced to the '
            'cecum.\nA 3 cm ascending colon mass, biopsied and tattooed\n' + line + '\n' + polyp + '\n')


class Structure4PhraseLinesTests(unittest.TestCase):
    """structure:4 (a round-2b regression that round 3b fixed for one word order) - a findings line or a statement that
    ends with a section noun but reads as a phrase (a comma, a preposition, an -ing word after its first word) opens an
    'other' section, never a history or a plan one: the performed polypectomy after it is never excluded, and 45385 is
    ready as at 57b4b3747."""

    CLAIMED = ('Changes of prior radiation therapy', 'Evidence of past radiation therapy', 'Scarring from prior treatment',
               'Healed scar from previous procedures', 'Specimens sent for further testing', 'Specimen sent for further evaluation',
               'Sent to pathology for further evaluation', 'Awaiting pathology for management', 'Possible stricture, further imaging',
               'Mucosa photographed for future records')
    LISTED = ('Changes consistent with prior radiation therapy', 'Mucosal changes from prior radiation therapy',
              'Telangiectasias from previous radiation therapy', 'Retained stool limiting further evaluation',
              'Stricture precluding further evaluation')

    def test_the_claimed_and_listed_lines(self):
        for line in self.CLAIMED + self.LISTED:
            text = structure4_note(line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, STRUCTURE4_POLYP), 'other')
                self.assertNotIn(read(text, STRUCTURE4_POLYP)[0], ('planned', 'historical', 'cancelled', 'negated'))
                self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE4_POLYP)])['45385']))

    def test_the_cued_polyp_line(self):
        polyp = 'A 6 mm sigmoid polyp was removed with a cold snare.'
        for line in ('Changes of prior radiation therapy', 'Specimens sent for further testing'):
            text = structure4_note(line, polyp)
            with self.subTest(line=line):
                self.assertEqual(read(text, polyp)[0], 'performed')
                self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))

    def test_a_word_bullet_list_whose_bullets_extraction_drops(self):
        for line in ('Changes of prior radiation therapy', 'Specimens sent for further testing'):
            text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                                  ('Procedure: Colonoscopy with biopsy and cold snare polypectomy.', None), ('Findings', 'Heading 2'),
                                  ('The colonoscope was advanced to the cecum', 'List Bullet'),
                                  ('A 3 cm ascending colon mass, biopsied and tattooed', 'List Bullet'), (line, 'List Bullet'),
                                  (STRUCTURE4_POLYP, 'List Bullet')])
            with self.subTest(line=line):
                self.assertIn('\n' + line + '\n', text)
                self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE4_POLYP)])['45385']))

    def test_a_numbered_phrase_item_stays_content(self):
        for line in ('2. Specimens sent for further testing', '* Changes of prior radiation therapy',
                     'b) Retained stool limiting further evaluation'):
            text = structure4_note(line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, STRUCTURE4_POLYP), 'findings')
                self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE4_POLYP)])['45385']))

    def test_labels_that_name_their_section_still_open(self):
        """A label that starts with a section's own name, or whose comma parts all name sections, still opens its plan or
        history section, so the planned EMR under it is still excluded."""
        for label, kind in (('Recommendations for follow-up', 'plan'), ('Instructions for follow-up', 'plan'),
                            ('History of prior procedures', 'history'), ('Summary of recommendations', 'plan'),
                            ('Discussion of future management', 'plan'), ('Impression, plan', 'plan'),
                            ('Findings, recommendations', 'plan'), ('Previously scheduled procedures', 'plan'),
                            ('Plan for further management', 'plan'), ('Upcoming procedures (pending authorization)', 'plan'),
                            ('Further management', 'plan'), ('Earlier endoscopic work-up', 'history'),
                            ('Appointments for follow-up', 'plan'), ('Imaging for further evaluation', 'plan')):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assertEqual(kind_at(text, EMR_LINE), kind)
                self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')

    def test_findings_lines_without_a_phrase_are_unchanged(self):
        for line in ('Prior radiation therapy changes', 'Small internal hemorrhoids', 'Diverticulosis in the sigmoid colon'):
            text = structure4_note(line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, STRUCTURE4_POLYP), 'findings')
                self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE4_POLYP)])['45385']))


# --- structure:5: round 3b's plan labels with an answer of their own -------------------------------------------------

STRUCTURE5_INTERVENTION = 'cold snare polypectomy of a 6 mm sigmoid polyp'


def structure5_summary(field, indication=True):
    return (HEADER + 'Procedure: Colonoscopy\n' + ('Indication: Positive FIT\n' if indication else '') + field + '\nExtent: cecum\n'
            'Interventions: ' + STRUCTURE5_INTERVENTION + '\nComplications: none\nImpression: Sigmoid polyp.\n')


class Structure5FieldPlanLabelTests(unittest.TestCase):
    """structure:5 (a round-3b new defect, 75a3cfac7) - "Referral:", "Orders:", "To do:" and the other plan labels round 3b
    added are field labels as often as headings. With an answer of their own they never open a plan section over the field
    lines after them, and a no-answer value ("Orders: none") is a field: the performed polypectomy in the summary is never
    excluded as planned, as at R3B-BASE."""

    FIELDS = ('Referral: Dr. B. Synthetic, primary care', 'Referrals: none', 'Referral: none', 'Orders: none', 'Orders: CBC',
              'To do: none', 'To-do: none', 'Pending orders: none', 'Pending procedures: N/A', 'Procedures to be done: none')

    def test_the_claimed_summary(self):
        """After the indication line the summary reads as at R3B-BASE: the indication section, held for the extent."""
        for field in self.FIELDS:
            text = structure5_summary(field)
            with self.subTest(field=field):
                self.assertNotEqual(kind_at(text, STRUCTURE5_INTERVENTION), 'plan')
                self.assertNotIn(read(text, STRUCTURE5_INTERVENTION)[0], NOT_TODAY)
                proposal = run_engine(text, [('45385', STRUCTURE5_INTERVENTION)])['45385']
                self.assertNotEqual(proposal.bucket, 'excluded')

    def test_the_summary_with_the_field_under_the_procedure_line(self):
        text = structure5_summary('Referral: Dr. B. Synthetic, primary care', indication=False)
        self.assertEqual(kind_at(text, STRUCTURE5_INTERVENTION), 'procedure')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE5_INTERVENTION)])['45385']))
        for field in ('Orders: none', 'Referrals: none'):  # held, as at R3B-BASE (the field reads as denying the procedure)
            text = structure5_summary(field, indication=False)
            with self.subTest(field=field):
                proposal = run_engine(text, [('45385', STRUCTURE5_INTERVENTION)])['45385']
                self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))

    def test_a_findings_list(self):
        for field in ('Orders: none', 'Referral: none', 'To do: none'):
            text = (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings:\nThe colonoscope was advanced '
                    'to the cecum.\n' + field + '\n' + STRUCTURE4_POLYP + '\n')
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, STRUCTURE4_POLYP), 'findings')
                self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE4_POLYP)])['45385']))

    def test_the_labels_still_plan(self):
        """Bare, the labels open a plan section (round 3 routing:12); with an answer they plan their own line, and the lines
        after them while those are not fields."""
        for label in ('Orders:', 'Referrals:', 'To do:', 'Pending procedures'):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assertEqual(kind_at(text, EMR_LINE), 'plan')
                self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')
        for label in ('Orders:', 'To do:', 'Referral:'):
            text = emr_note(label).replace(label + '\n', label + ' ')
            with self.subTest(inline=label):
                self.assertEqual(kind_at(text, EMR_LINE), 'plan')
                self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')
        text = emr_note('Orders: EGD with esophageal dilation')
        self.assertEqual(kind_at(text, EMR_LINE), 'plan')
        self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')
        text = emr_note('Referral: GI surgery\n')  # past a blank line, the next line that is not a field
        self.assertEqual(kind_at(text, EMR_LINE), 'plan')
        self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')
        text = structure5_summary('Referral: Dr. B. Synthetic, primary care\n')  # past a blank line, a field
        self.assertNotEqual(kind_at(text, STRUCTURE5_INTERVENTION), 'plan')

    def test_other_field_labels_are_unchanged(self):
        for field in ('Referring physician: Dr. B. Synthetic', 'Plan: none'):
            text = structure5_summary(field)
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, STRUCTURE5_INTERVENTION), 'indication' if field.startswith('Referring') else 'plan')


# --- structure:9: a performed-today procedure label answered "none" ---------------------------------------------------

STRUCTURE9_ITEM = '2. Upper endoscopy to D2 with balloon dilation at the hospital endoscopy unit.'
STRUCTURE9_VISIT = 'Established patient office visit for dysphagia.'


def structure9_note(line, item=STRUCTURE9_ITEM):
    return (HEADER + 'Place of service: Office (POS 11)\n' + STRUCTURE9_VISIT + '\nChief complaint: Dysphagia.\nAssessment and '
            'plan:\n1. Dysphagia, likely peptic stricture.\n' + line + '\n' + item + '\n3. Continue omeprazole.\nMedical decision '
            'making: moderate.\nTotal time: 32 minutes.\n')


class Structure9TodayLabelAnsweredNoneTests(unittest.TestCase):
    """structure:9 (a round-3b over-correction, e7bc88a) - a performed-today procedure label that answers nothing
    ("Procedures performed today: none", or the bare label with "None" on the next line) opens no procedure section: the
    planned EGD on the next plan line stays planned (43249 excluded, as at R3B-BASE), the office E/M is not held for a
    same-day procedure, and no missed service is reported."""

    LINES = ('Procedures performed today: none', 'Interventions performed: none', 'Procedures done today: N/A',
             'Procedures performed today: None.', 'Procedures performed today:\nNone', 'Procedures performed today:\n\nNone')

    def assert_planned_egd(self, text, item):
        self.assertEqual(kind_at(text, item), 'plan')
        self.assertNotIn(family(text, 'gi.egd'), POSITIVE)
        proposals = run_engine(text, [('43249', item), ('99214', STRUCTURE9_VISIT)])
        self.assertFalse(ready(proposals['43249']))
        self.assertEqual(proposals['43249'].bucket, 'excluded')
        self.assertTrue(ready(proposals['99214']))
        self.assertNotIn('services.unproposed', encounter_warnings(text, [('99214', STRUCTURE9_VISIT)]))

    def test_the_claimed_lines(self):
        for line in self.LINES:
            with self.subTest(line=line):
                self.assert_planned_egd(structure9_note(line), STRUCTURE9_ITEM)
        item = '2. EGD to the duodenum with balloon dilation, at the hospital endoscopy unit.'
        self.assert_planned_egd(structure9_note('Procedures performed today: none', item), item)

    def test_the_line_at_the_top_of_the_plan(self):
        item = 'upper endoscopy to the duodenum with balloon dilation at the hospital endoscopy unit.'
        text = (HEADER + 'Place of service: Office (POS 11)\n' + STRUCTURE9_VISIT + '\nChief complaint: Dysphagia.\nAssessment and '
                'plan:\nProcedures performed today: None\n1. Dysphagia, likely peptic stricture - ' + item + '\nMedical decision '
                'making: moderate.\nTotal time: 32 minutes.\n')
        self.assert_planned_egd(text, item)

    def test_a_label_with_its_procedures_still_opens(self):
        """contract:8 (round 3): with items of its own the label still opens a procedure section."""
        for line in ('Procedures performed today: flexible sigmoidoscopy to 30 cm', 'Procedures performed today:\n'
                     '☒ Flexible sigmoidoscopy to 30 cm',
                     'Procedures performed today: no sedation; flexible sigmoidoscopy to 30 cm'):  # a value, not "no"
            text = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: Rectal '
                    'bleeding.\nMedical decision making: Moderate.\nTotal time on the date of the encounter was 32 minutes.\n'
                    'Assessment and plan: Grade II internal hemorrhoids.\n' + line + '\n')
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, 'lexible sigmoidoscopy to 30 cm'), 'procedure')
                self.assertEqual(family(text, 'gi.flex_sig'), 'performed')


# --- structure:1 / structure:2 / structure:3: a line that ends with an answer --------------------------------------

STRUCTURE1_BIOPSY = 'Biopsies were taken from the mid esophagus to evaluate for eosinophilic esophagitis.'


def structure1_note(line):
    return (HEADER + 'Procedure: EGD with biopsy.\nIndication: Dysphagia.\nFindings:\nEsophagus: normal\n' + line + '\n'
            + STRUCTURE1_BIOPSY + '\nThe gastroscope was advanced to the second part of the duodenum.\n')


class Structure1LastFieldOnTheLineTests(unittest.TestCase):
    """structure:1 (a round-2b regression from status:16, under-corrected by round 3b) - a line whose LAST field answers
    "no" ends its sentence whatever comes before that field (two fields, a comma, a tab, a run of spaces), and so does a
    column answer without a colon: the performed biopsy on the next line is never negated, as at 57b4b3747."""

    CLAIMED = ('Hiatal hernia: no, Schatzki ring: no', 'Hiatal hernia: no   Schatzki ring: no', 'Hiatal hernia: no\tSchatzki ring: no',
               'Mucosa: normal, hiatal hernia: no', 'Hiatal hernia      no', 'Hiatal hernia\tno')

    def test_the_claimed_lines(self):
        for line in self.CLAIMED:
            text = structure1_note(line)
            with self.subTest(line=line):
                self.assertTrue(starts_a_sentence(text, STRUCTURE1_BIOPSY))
                self.assertEqual(read(text, STRUCTURE1_BIOPSY)[0], 'performed')
                self.assertTrue(ready(run_engine(text, [('43239', STRUCTURE1_BIOPSY)])['43239']))

    def test_the_office_note(self):
        flex = 'Flexible sigmoidoscopy to 30 cm with cold forceps biopsy was performed today.'
        text = OFFICE + 'Procedure note\nAnal fissure: no, external hemorrhoids: no\n' + flex + '\n'
        proposals = run_engine(text, [('99214', 'Established patient office visit.'), ('45331', flex)])
        self.assertTrue(ready(proposals['45331']))
        self.assertEqual(proposals['99214'].status, 'needs_clarification')
        self.assertIn('separate_em', clarified(proposals['99214']))

    def test_a_real_word_document(self):
        for line in ('Hiatal hernia: no, Schatzki ring: no', 'Hiatal hernia\tno', 'Hiatal hernia: no   Schatzki ring: no'):
            text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                                  ('Procedure: EGD with biopsy.', None), ('Indication: Dysphagia.', None), ('Findings:', None),
                                  ('Esophagus: normal', None), (line, None), (STRUCTURE1_BIOPSY, None),
                                  ('The gastroscope was advanced to the second part of the duodenum.', None)])
            with self.subTest(line=line):
                self.assertIn('\n' + line + '\n', text)
                self.assertTrue(ready(run_engine(text, [('43239', STRUCTURE1_BIOPSY)])['43239']))

    def test_cut_prose_still_runs_on(self):
        """status:16 (round 2): a value that is cut prose is no answer, however its spaces or commas fall."""
        for cut in ('Comment: because of time constraints, no', 'Comment: patient had no',
                    'Comment: because of time constraints,   no', 'The patient asked about the cyst; because of time constraints, no',
                    'Because of time constraints,   no', 'In the end there was   no'):  # no column answer: a comma, a clause
            text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n' + cut + '\nEUS of the '
                    'pancreatic cyst was performed today.\n')
            with self.subTest(cut=cut):
                self.assertFalse(starts_a_sentence(text, 'EUS of the pancreatic cyst'))
                self.assertEqual(family(text, 'gi.eus'), 'negated')


class Structure2LowerCaseAfterAnAnswerTests(unittest.TestCase):
    """structure:2 is NOT repaired here: a lower-case line after an answered field still runs on, as it has since
    57b4b3747. Splitting it would release the wrapped negation below, and a layout rule may only hold; the hold the
    verifier asked for needs a cue that detect owns. This pins the direction any later change must keep."""

    def test_a_wrapped_negation_is_never_released(self):
        text = (HEADER + 'Procedure: EGD with biopsy.\nFindings:\nEsophagus: normal\nComment: no\nbiopsies were taken because the '
                'patient takes apixaban.\nThe gastroscope was advanced to the second part of the duodenum.\n')
        proposal = run_engine(text, [('43239', 'biopsies were taken because the patient takes apixaban.')])['43239']
        self.assertFalse(ready(proposal))


STRUCTURE3_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


class Structure3SpokenAnswerTests(unittest.TestCase):
    """structure:3 (a round-2b regression from status:16) - a spoken answer ("the patient said no", "answered no", "chose
    neither") ends its sentence when the next line opens a clause of its own: the performed colonoscopy family is not
    negated and 45385 is ready, as at 57b4b3747. Cut prose and a verbless next line still run on."""

    def test_the_claimed_inputs(self):
        polyp = 'A 6 mm polyp was removed with a cold snare.'
        a = (HEADER + 'Procedure: Colonoscopy.\nTechnique: Sedation was offered; the patient said no\nColonoscopy was then performed '
             'without sedation and the colonoscope was advanced to the cecum.\nFindings: ' + polyp + '\n')
        self.assertTrue(starts_a_sentence(a, 'Colonoscopy was then performed'))
        self.assertEqual(family(a, 'gi.colonoscopy'), 'performed')
        self.assertEqual(fact_value(a, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertTrue(ready(run_engine(a, [('45385', polyp)])['45385']))
        snare = 'Cold snare polypectomy of a 6 mm sigmoid polyp was performed.'
        b = (HEADER + 'Procedure: Colonoscopy.\nFindings: The colonoscope was advanced to the cecum. She was asked whether she wanted '
             'a biopsy of the hemorrhoid and said no\n' + snare + '\n')
        self.assertTrue(ready(run_engine(b, [('45385', snare)])['45385']))

    def test_the_listed_variants(self):
        for line in ('Asked about a biopsy of the hemorrhoid, she said no', 'Asked about a biopsy of the hemorrhoid, she answered no',
                     'Asked about a biopsy of the hemorrhoid, she replied no', 'Asked about a biopsy of the hemorrhoid, patient says no',
                     'Asked about a biopsy or a tattoo, the patient chose neither'):
            text = (HEADER + 'Procedure: Colonoscopy.\nFindings: The colonoscope was advanced to the cecum. ' + line + '\n'
                    + STRUCTURE3_POLYP + '\n')
            with self.subTest(line=line):
                self.assertTrue(starts_a_sentence(text, STRUCTURE3_POLYP))
                self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE3_POLYP)])['45385']))
        egd = (HEADER + 'Procedure: EGD.\nFindings: The gastroscope was advanced to the second part of the duodenum. The patient was '
               'asked whether she wanted propofol and said no\nBiopsies were taken from the gastric antrum.\n')
        self.assertTrue(ready(run_engine(egd, [('43239', 'Biopsies were taken from the gastric antrum.')])['43239']))
        extent = ('The colonoscope was advanced to the cecum and a 6 mm polyp was removed with a cold snare.')
        text = HEADER + 'Procedure: Colonoscopy.\nTechnique: Propofol was offered and the patient said no\n' + extent + '\n'
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertTrue(ready(run_engine(text, [('45385', extent)])['45385']))

    def test_a_real_word_document(self):
        text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                              ('Procedure: Colonoscopy.', None),
                              ('Findings: The colonoscope was advanced to the cecum. Asked about a biopsy of the hemorrhoid, she '
                               'said no', None), (STRUCTURE3_POLYP, None)])
        self.assertTrue(ready(run_engine(text, [('45385', STRUCTURE3_POLYP)])['45385']))

    def test_cut_prose_and_a_verbless_next_line_still_run_on(self):
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\nComment: because of time '
                'constraints, no\nEUS of the pancreatic cyst was performed today.\n')
        self.assertEqual(family(text, 'gi.eus'), 'negated')
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Asked about the pancreatic '
                'cyst, she said no\nEUS of the pancreatic cyst.\n')
        self.assertFalse(starts_a_sentence(text, 'EUS of the pancreatic cyst.'))
        self.assertNotIn(family(text, 'gi.eus'), POSITIVE)


# --- structure:11: a line cut after a verb the closed lists do not know ----------------------------------------------

STRUCTURE11_EUS = 'EUS with fine-needle aspiration of the pancreatic head mass.'


def structure11_note(cut, after=''):
    return (HEADER + 'Procedure: EGD.\nIndication: Dysphagia; pancreatic head mass on CT.\nFindings: The gastroscope was advanced to '
            'the second portion of the duodenum. The esophagus was normal. ' + cut + '\n' + STRUCTURE11_EUS + '\n' + after)


def line_pdf(lines):
    """A real PDF, one drawString per line, through the real extractor."""
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen.canvas import Canvas

    from studio.ingest import extract_document
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=letter, invariant=1)
    canvas.setFont('Helvetica', 10)
    for n, line in enumerate(lines):
        canvas.drawString(72, 740 - 16 * n, line)
    canvas.showPage()
    canvas.save()
    result = extract_document(buffer.getvalue(), 'report.pdf', 'application/pdf', ocr=None)
    assert result.status == 'ok', result.messages
    return result.text


class Structure11CutAfterAnUnknownVerbTests(unittest.TestCase):
    """structure:11 (an under-correction of round 3b's routing:11, an open class) - a line cut after a plan,
    cancellation or denial verb the closed lists do not know ("Dr. Smith recommended", "the endoscopist deferred",
    "The family declined to authorize") no longer lets the service line after it read performed: that line is held (an
    'other' section of its own), so a planned or refused EUS is never a ready 43242. It is never joined, so the hold
    never becomes an exclusion; the section in force resumes on the line after it."""

    CUTS = ('Dr. Smith recommended', 'The family declined to authorize', 'The surgeon recommended', 'Patient deferred',
            'Pt deferred', 'The endoscopist deferred', 'Dr. Smith ordered', 'Insurance declined to cover',
            'Given the mass on CT, Dr. Smith recommended',
            # a service named in an earlier sentence or an earlier clause of the line is not the verb's object
            'The EGD was otherwise unremarkable. Dr. Smith recommended', 'After the colonoscopy, Dr. Smith recommended')

    def test_the_claimed_and_listed_cuts(self):
        for cut in self.CUTS:
            text = structure11_note(cut)
            with self.subTest(cut=cut):
                self.assertTrue(starts_a_sentence(text, STRUCTURE11_EUS))
                self.assertNotIn(read(text, STRUCTURE11_EUS)[0], POSITIVE + NOT_TODAY)
                self.assertNotIn(family(text, 'gi.eus'), POSITIVE)
                proposal = run_engine(text, [('43242', STRUCTURE11_EUS)])['43242']
                self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))

    def test_the_routing11_note(self):
        text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope was advanced to the cecum. A '
                '6 mm sigmoid polyp was removed with a cold snare. The patient asked about the pancreatic cyst; given the time '
                'constraints, the endoscopist deferred\nEUS of the pancreatic cyst.\n')
        self.assertFalse(ready(run_engine(text, [('43259', 'EUS of the pancreatic cyst.')])['43259']))
        self.assertTrue(ready(run_engine(text, [('45385', 'A 6 mm sigmoid polyp was removed with a cold snare.')])['45385']))

    def test_a_real_pdf(self):
        text = line_pdf(['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'Date of service: 2026-10-21', 'Procedure: EGD.',
                         'Indication: Dysphagia; pancreatic head mass on CT.',
                         'Findings: The gastroscope was advanced to the second portion of the duodenum. The esophagus was',
                         'normal. Dr. Smith recommended', STRUCTURE11_EUS])
        self.assertIn('Dr. Smith recommended\n' + STRUCTURE11_EUS, text)
        self.assertFalse(ready(run_engine(text, [('43242', STRUCTURE11_EUS)])['43242']))

    def test_the_section_resumes_after_the_held_line(self):
        biopsy = 'Biopsies were taken from the gastric antrum.'
        text = structure11_note('Dr. Smith recommended', biopsy + '\n')
        self.assertEqual(kind_at(text, biopsy), 'findings')
        self.assertTrue(ready(run_engine(text, [('43239', biopsy)])['43239']))

    def test_a_planned_intervention_gives_no_fact(self):
        """The same hold for an intervention line: no EMR fact is read from it. (Its code can still be ready through the
        colonoscopy performed in the same note: a silent passage takes its family's reading.)"""
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 30 mm laterally spreading '
                'polyp was tattooed. Dr. Smith recommended\nEMR of the ascending colon lesion at a tertiary center.\n')
        self.assertNotIn(read(text, 'EMR of the ascending')[0], POSITIVE)
        self.assertNotIn('EMR', fact_value(text, 'gi.colonoscopy', 'interventions') or '')

    def test_lines_that_end_their_sentence_still_read_performed(self):
        base = HEADER + 'Procedure: EGD with biopsy.\nFindings: The gastroscope was advanced to the second part of the duodenum.\n'
        for prev, nxt in (('The polyp was removed with the snare', 'EGD was performed.'),
                          ('Retroflexion not performed', 'EGD with biopsy of the antrum.'),
                          ('Repeat colonoscopy recommended', 'EGD with biopsy of the antrum.'),
                          ('Patient referred to surgery', 'EGD with biopsy of the antrum.'),
                          ('Biopsy of the duodenum deferred', 'EGD with biopsy of the antrum.'),
                          ('Dr. Smith performed', 'EGD with biopsy of the antrum.'),
                          ('No change compared to prior', 'EGD with biopsy of the antrum.')):
            text = base + prev + '\n' + nxt + '\n'
            with self.subTest(prev=prev):
                self.assertEqual(read(text, nxt)[0], 'performed')

    def test_only_a_line_that_names_a_service_or_an_intervention_is_held(self):
        for line in ('Mild erythema of the gastric antrum.', 'Small hiatal hernia without esophagitis.'):
            text = structure11_note('Dr. Smith recommended').replace(STRUCTURE11_EUS, line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, line), 'findings')

    def test_the_closed_lists_still_join(self):
        for cut, status in (('We recommend', 'planned'), ('The patient deferred', 'cancelled'), ('Dr. Smith will perform', 'planned')):
            text = structure11_note(cut)
            with self.subTest(cut=cut):
                self.assertFalse(starts_a_sentence(text, STRUCTURE11_EUS))
                self.assertEqual(family(text, 'gi.eus'), status)


if __name__ == '__main__':
    unittest.main()
