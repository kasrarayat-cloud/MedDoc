"""Regressions for round 4c-2, the BOX2 items (found by the lead and the round-4c agents before refutation round 6):

- box2:E -- a procedure coordinated with the office visit (or another non-procedure) in one name is no same-day
  procedure: "Office visit and anoscopy were performed today." emitted no gi.other mention at all, so 99214 was ready.
- box2:F -- "Notes: Not attested" under the separately identifiable E/M statement still attested it.
- box2:G -- a row of items in different box states, cited whole, was read by its first box.

Each class reproduces its item from the exact input the lead measured at 51457929c, adds the variants the item names,
and pins the positive controls an over-correction would break. Routing runs for real on the document's own service
date; the engine runs through tests.test_repairs_r3_validation_b.real() (the lead's measurement path: the JSON round
trip, the real span reader, in-memory reference rows).

The hold-only rule (contract-r4c section 1) governs every rule here: a rule may move a reading only to uncertain, with
a non-silent cue; it never newly excludes or releases. Synthetic text only.
"""
import unittest
from datetime import date

from studio.gi import detect
from tests.test_repairs_r3_validation_b import HEAD, check_of, real

D = date(2026, 10, 21)
NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')
SILENT = 'uncertain: no performance evidence'
VISIT = 'Established patient office visit.'
OFFICE = HEAD + ('Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: {cc}\n'
                 'History of present illness: {hpi}\nAssessment and plan: {plan}\nMedical decision making: moderate.\n')


def others(text):
    """The routed gi.other mentions: [(name, status, cues)]."""
    finding = detect.route(text, D).finding(detect.OTHER_FAMILY)
    return [(m.span.text, m.status, m.cues) for m in (finding.mentions if finding else ())]


def outcome(proposal):
    if proposal.bucket == 'excluded':
        return 'excluded'
    return 'ready' if proposal.status == 'ready' else 'held' if proposal.status == 'needs_clarification' else (
        proposal.bucket, proposal.status)


# --- box2:E -- a procedure coordinated with the visit or another non-procedure in one name --------------------------

E_PLAN = 'Office visit and anoscopy were performed today.'
E_OFFICE = OFFICE.format(cc='Rectal bleeding.', hpi='Bleeding for 2 weeks.', plan=E_PLAN + ' Fiber.')
# The same office note with the line outside every section (kind 'other'), where the procedure alone reads performed.
E_BODY = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n{body}\nChief complaint: Rectal '
          'bleeding.\nHistory of present illness: Bleeding for 2 weeks.\nAssessment and plan: Fiber.\n'
          'Medical decision making: moderate.\n')


class Box2ECoordinatedProcedureTests(unittest.TestCase):
    """box2:E (high, declared reading; ARCHITECTURE 5.3 / 5.6). The subject "Office visit and anoscopy" was refused whole
    by _NOT_A_PROCEDURE ("visit"), so routing emitted no gi.other mention and 99214 was ready beside an anoscopy done
    today. Each procedure coordinated with the non-procedure in one name (split at routing's own connector words) is a
    gi.other mention held with a non-silent cue (_B2_COORDINATED), never performed: the E/M is held for the possible
    same-day procedure. The connector parts read exactly as the same name standing alone would, except that a done
    reading is held."""

    def assert_held_part(self, text, part):
        found = [m for m in others(text) if m[0] == part]
        self.assertEqual(len(found), 1, (part, others(text)))
        _, status, cues = found[0]
        self.assertEqual(status, 'uncertain', (part, cues))
        self.assertEqual(cues[0], detect._B2_COORDINATED, cues)
        self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)

    def assert_visit_held(self, text):
        proposals, _ = real(text, ('99214', VISIT))
        visit = proposals['99214']
        self.assertEqual(visit.status, 'needs_clarification', [c.detail for c in visit.checks])
        self.assertIn('separate_em', [c.fact for c in visit.clarifications])
        same = check_of(visit, 'em.same_day_procedure')
        self.assertEqual(same.status, 'warn')
        self.assertIn('Other GI service is possibly performed on the same date', same.detail)

    def test_the_claimed_line_holds_the_visit(self):
        self.assert_held_part(E_OFFICE, 'anoscopy')
        self.assertEqual(detect.route(E_OFFICE, D).finding(detect.OTHER_FAMILY).status, 'uncertain')
        self.assert_visit_held(E_OFFICE)

    def test_every_non_procedure_word_coordinated_with_a_procedure(self):
        for plan, part in (('Physical exam and banding were completed.', 'banding'),
                           ('Consent and anoscopy were done today.', 'anoscopy'),
                           ('History and anoscopy were performed today.', 'anoscopy'),
                           ('Evaluation and rubber band ligation were performed today.', 'rubber band ligation'),
                           ('Counseling and anoscopy were completed today.', 'anoscopy'),
                           ('Labs and paracentesis were done today.', 'paracentesis'),
                           ('Sedation and anoscopy were performed today.', 'anoscopy'),
                           ('Medical management and banding were performed today.', 'banding'),
                           ('Anoscopy and office visit were performed today.', 'Anoscopy'),
                           ('The E/M visit and anoscopy were performed today.', 'anoscopy'),
                           ('Office visit and I&D of a perianal abscess were performed today.',
                            'I&D of a perianal abscess')):
            with self.subTest(plan=plan):
                text = OFFICE.format(cc='Rectal bleeding.', hpi='Bleeding for 2 weeks.', plan=plan + ' Fiber.')
                self.assert_held_part(text, part)
                self.assert_visit_held(text)

    def test_every_connector_routing_defines(self):
        for plan, parts in (('Office visit and anoscopy and banding were performed today.', ('anoscopy', 'banding')),
                            ('Office visit & anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit + anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit plus anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit as well as anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit followed by anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit and then anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit and/or anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit and an anoscopy were performed today.', ('anoscopy',)),
                            ('Office visit/anoscopy were performed today.', ('anoscopy',)),
                            ('Anoscopy/exam were performed today.', ('Anoscopy',))):
            with self.subTest(plan=plan):
                text = OFFICE.format(cc='Rectal bleeding.', hpi='Bleeding for 2 weeks.', plan=plan + ' Fiber.')
                for part in parts:
                    self.assert_held_part(text, part)
                self.assert_visit_held(text)

    def test_every_form_that_names_a_procedure(self):
        for body, part in (('She underwent an office visit and anoscopy today.', 'anoscopy'),
                           ('We performed an exam and anoscopy today.', 'anoscopy'),
                           ('Office visit and hemorrhoids were banded today.', 'hemorrhoids were banded'),
                           ('Today we banded two hemorrhoids and an exam was done.', 'banded two hemorrhoids'),
                           ('Exam and anoscopy: grade 2 internal hemorrhoids.', 'anoscopy'),
                           ('Procedure: Office visit and anoscopy.', 'anoscopy'),
                           ('Procedure note: Office visit and anoscopy were performed today.', 'anoscopy'),
                           ('Exam: Physical exam and banding were completed.', 'banding'),
                           (E_PLAN, 'anoscopy')):
            with self.subTest(body=body):
                text = E_BODY.format(body=body)
                self.assert_held_part(text, part)
                self.assert_visit_held(text)

    def test_a_gi_other_code_citing_the_line_stays_held(self):
        for text, line in ((E_OFFICE, E_PLAN), (E_BODY.format(body=E_PLAN), E_PLAN),
                           (E_BODY.format(body='Procedure note: ' + E_PLAN), 'Procedure note: ' + E_PLAN)):
            for code in ('46600', '46221'):
                with self.subTest(line=line, code=code):
                    proposals, _ = real(text, ('99214', VISIT), (code, line))
                    self.assertEqual(outcome(proposals[code]), 'held', [c.detail for c in proposals[code].checks])
                    self.assertEqual(outcome(proposals['99214']), 'held')

    def test_controls_read_as_before(self):
        # no procedure in the subject: nothing added, the visit ready
        text = OFFICE.format(cc='Rectal bleeding.', hpi='Bleeding for 2 weeks.', plan='Office visit was performed today.')
        self.assertEqual(others(text), [])
        proposals, _ = real(text, ('99214', VISIT))
        self.assertEqual(outcome(proposals['99214']), 'ready')
        # the procedure alone: read exactly as before
        text = OFFICE.format(cc='Rectal bleeding.', hpi='Bleeding for 2 weeks.', plan='Anoscopy was performed today. Fiber.')
        self.assertEqual(others(text), [('Anoscopy', 'uncertain', (
            'performed: was performed', 'performed: performed today', detect.PLAN_TODAY,
            'section: plan (Assessment and plan)'))])
        self.assertEqual(others(E_BODY.format(body='Anoscopy was performed today.')),
                         [('Anoscopy', 'performed', ('performed: was performed', 'performed: performed today'))])
        # a comma already opens the subject (_SUBJECT_BREAK): the names after it are read whole, as before
        self.assertEqual(others(E_BODY.format(body='Office visit, anoscopy and banding were performed today.')),
                         [('anoscopy and banding', 'performed', ('performed: were performed',
                                                                 'performed: performed today'))])
        # told at another time, led by a negation or a plan word, coordinated as history, or no connector at all:
        # nothing is added (the whole name is refused as before)
        for body in ('Office visit and anoscopy were performed at her last visit.',
                     'No exam or anoscopy was performed today.', 'Neither the exam nor the anoscopy was performed.',
                     'Office visit and possible banding were performed today.',
                     'Office visit and prior anoscopy were performed.', 'Consent for banding was completed.',
                     'Office visit and prior anoscopy were performed today.',  # read as "Prior anoscopy ..." alone
                     'Office visit and outside anoscopy were performed today.',
                     'Office visit and colonoscopy were performed today.', 'Office visit and exam were performed today.'):
            with self.subTest(body=body):
                self.assertEqual(others(E_BODY.format(body=body)), [])
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nPast surgical history: '
                'Exam and hemorrhoidectomy were performed.\nMedical decision making: moderate.\n')
        self.assertEqual(others(text), [])  # read historical alone, so it documents nothing today, as before
        proposals, _ = real(text, ('99214', VISIT))
        self.assertEqual(outcome(proposals['99214']), 'ready')

    def test_a_part_is_never_read_performed(self):
        for body in (E_PLAN, 'Procedure: Office visit and anoscopy.', 'Office visit and hemorrhoids were banded today.',
                     'Office visit and anoscopy and banding were performed today.'):
            with self.subTest(body=body):
                for name, status, cues in others(E_BODY.format(body=body)):
                    self.assertEqual(status, 'uncertain', (name, cues))
                    self.assertNotIn(status, NOT_TODAY)

    def test_each_part_is_read_where_the_connector_words_split_it(self):
        """Never inside a procedure's word ("I & D"), never at a bare "/" that touches no non-procedure word ("w/o"), and
        of a stated act's parts only the one holding the act may name no procedure word."""
        for body, parts in (('Office visit and I & D of a perianal abscess were performed today.',
                             ['I & D of a perianal abscess']),
                            ('Office visit and anoscopy w/o complication were performed today.',
                             ['anoscopy w/o complication']),
                            ('Office visit and two hemorrhoids and the columns were banded today.',
                             ['columns were banded'])):
            with self.subTest(body=body):
                self.assertEqual([m[0] for m in others(E_BODY.format(body=body))], parts)

    def test_every_part_break_is_a_connector(self):
        """The parts are split at routing's own connector words (_CONNECTOR), never at a wider class."""
        for gap in (' and ', ' or ', ' and/or ', ' nor ', ' plus ', ' then ', ' followed by ', ' as well as ', ' and the ',
                    ' and an ', ' or a ', ' plus her ', ' & ', ' + ', ' / ', '/', '&', '+'):
            with self.subTest(gap=gap):
                self.assertIsNotNone(detect._CONNECTOR.fullmatch(gap))
                if gap.strip() == gap:
                    self.assertIsNotNone(detect._B2_BARE_BREAK.fullmatch(gap))
                else:
                    self.assertIsNotNone(detect._B2_PART_BREAK.fullmatch(gap))
        for gap in (' with ', ', ', ' for ', ' of ', ' w/ ', ' vs '):
            with self.subTest(gap=gap):
                self.assertIsNone(detect._B2_PART_BREAK.fullmatch(gap))

    def test_a_hedge_naming_a_part_is_never_about_another_service(self):
        """Validation's other-service reading (engine._other_service) skips a held part: beside the code's own performed
        passage, a hedge naming one still holds the code as at the base, never releases it (hold-only); a hedge naming
        a procedure routing reads alone keeps its base reading too."""
        egd = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nProcedure: EGD with '
               'biopsy.\nFindings: The gastroscope was advanced to D2. Two cold forceps biopsies were taken from the '
               'antrum.\n{line}\nAssessment and plan: Fiber.\nMedical decision making: moderate.\n')
        own = 'Two cold forceps biopsies were taken from the antrum.'
        for line, wanted in (('Physical exam and anoscopy were completed?', 'held'),
                             ('Physical exam and anoscopy were completed, unclear if adequate.', 'held'),
                             ('Physical exam and anoscopy were completed (?).', 'held'),
                             ('Anoscopy was completed?', 'ready')):
            with self.subTest(line=line):
                text = egd.format(line=line)
                proposals, _ = real(text, ('43239', own, line))
                self.assertEqual(outcome(proposals['43239']), wanted, [c.detail for c in proposals['43239'].checks])
        from studio.validation import checks
        self.assertTrue(detect._B2_COORDINATED.startswith(checks._B2_COORDINATED_CUE))

    def test_a_coordinated_part_is_no_item_of_a_box_line(self):
        """The parts never join an.other_names (the items box lines and field holds read), so no box reading moves."""
        text = E_BODY.format(body=E_PLAN)
        an = detect._analysis(text, D)[0]
        self.assertEqual(an.other_names, ())
        self.assertEqual([m[0] for m in others(text)], ['anoscopy'])



# --- box2:F -- a refusal in the line under the separately identifiable E/M statement ---------------------------------

F_STATEMENT = 'A significant, separately identifiable E/M service was performed.'
F_OFFICE = OFFICE.format(cc='Dysphagia.', hpi='Dysphagia.', plan='EGD with dilation was performed today.')


def separate_em(text):
    finding = detect.route(text, D).finding('gi.office_em')
    fact = next((f for f in finding.facts if f.name == 'separate_em'), None)
    return fact.value if fact else None


class Box2FAttestationLineTests(unittest.TestCase):
    """box2:F (high, declared reading; ARCHITECTURE 5.3, round 4c dc478f567 / fa8b3dbe1). "Notes: Not attested" under the
    statement still attested it: the answer reader reads only marks and answer words, and the attestation-word rule only
    the label, which "Notes" (a field on the closed own-field list) never carries. The line under the statement now reads
    the statement's own contrary words when it speaks of the attestation, and a field or marked line whose value carries
    an attestation word is the statement's answer, which only a checked box or a bare Yes affirms. Refusal only."""

    def assert_refused(self, line, statement=F_STATEMENT):
        text = F_OFFICE + statement + '\n' + line + '\n'
        self.assertIsNone(separate_em(text), line)
        proposals, _ = real(text, ('99214', VISIT))
        visit = proposals['99214']
        self.assertEqual(visit.status, 'needs_clarification', (line, [c.detail for c in visit.checks]))
        self.assertIn('separate_em', [c.fact for c in visit.clarifications])

    def assert_documented(self, line, statement=F_STATEMENT):
        text = F_OFFICE + statement + '\n' + line + '\n'
        self.assertEqual(separate_em(text), 'documented', line)
        proposals, _ = real(text, ('99214', VISIT))
        self.assertNotIn('separate_em', [c.fact for c in proposals['99214'].clarifications], line)

    def test_the_claimed_line_refuses_the_statement(self):
        self.assert_refused('Notes: Not attested')
        self.assert_documented('')  # without it, the statement attests, as before

    def test_every_spelling_of_the_refusal(self):
        for line in ('Notes: Not attested.', 'NOTES: NOT ATTESTED', 'notes: not attested', 'Notes - Not attested',
                     'Notes \u2013 Not attested', 'Notes | Not attested', 'Notes\tNot attested', 'Notes  Not attested',
                     'Notes = Not attested', 'Notes? Not attested', 'Notes?: Not attested', '- Notes: Not attested',
                     '\u2022 Notes: Not attested', '1. Notes: Not attested', '(1) Notes: Not attested',
                     '   Notes: Not attested', 'Note: Not attested', 'Comments: Not attested', 'Remarks: not attested',
                     'Status: Not attested', 'Attestation: Not attested', 'Biopsy: Not attested', 'Not attested',
                     'Not attested.', '\nNotes: Not attested'):
            with self.subTest(line=line):
                self.assert_refused(line)

    def test_other_refusals_that_name_the_attestation(self):
        for line in ('Notes: Attestation declined', 'Notes: E/M not separately identifiable', 'Notes: I do not attest',
                     'Notes: Not agreed', 'Notes: Attestation pending', 'Notes: Not confirmed', 'Notes: no attestation',
                     'Attestation: pending', 'Attested - No', 'Attested | No', 'Attested = No', 'Attested\tNo',
                     'I attest that I did not perform a separate E/M service.', 'Separate E/M not documented.',
                     'Attested?', 'Unattested', 'Notes: Unattested', '☒ Unattested', 'Notes: Disagree',
                     'Unconfirmed.', 'Attestation: non-attested'):
            with self.subTest(line=line):
                self.assert_refused(line)

    def test_boxes_on_the_line_under_it(self):
        for line in ('Notes: \u2610 Attested', 'Notes: [ ] Attested', 'Notes: \u2612 Not attested', '\u2612 Not attested',
                     'Not attested \u2612', '[x] Not attested', '\u2611 I do not attest', '\u2612 Attested (pending)',
                     'Notes: [?] Attested'):
            with self.subTest(line=line):
                self.assert_refused(line)
        for line in ('Notes: \u2612 Attested', '\u2612 Attested', '[x] Attested', 'Attested \u2612', '\u2611 I attest',
                     '\u2612 Yes, I attest', 'Yes, I attest: \U0001f5f9 Yes \u2610 No', 'I attest: \u2612 Yes \u2610 No'):
            with self.subTest(line=line):  # a checked box of its own or a checked Yes, nothing contrary: as before
                self.assert_documented(line)
        for line in ('Yes, I attest: \u2610 Yes \u2612 No', 'I attest: \u2610 Yes \u2610 No', 'I attest: [?] Yes [?] No',
                     '\u2612 Agree \u2610 Disagree'):
            with self.subTest(line=line):  # the denial option is checked, no option is, or a pair it cannot read: refused
                self.assert_refused(line)

    def test_an_affirmative_answer_that_is_no_checked_box_or_bare_yes_refuses(self):
        """The lead's controls: "Notes: Attested" and "Notes: Agree" never newly attest anything; as answers that are no
        checked box and no bare Yes they refuse, as the rule says. A statement that asks, or whose own box is unchecked,
        is still refused whatever is under it."""
        for line in ('Notes: Attested', 'Notes: Agree', 'Comments: Confirmed', 'Notes: Attested - Yes'):
            with self.subTest(line=line):
                self.assert_refused(line)
        for statement in (F_STATEMENT[:-1] + ':', '\u2610 ' + F_STATEMENT):
            for line in ('Notes: Attested', 'Notes: Agree', 'Attested - Yes', 'Notes: patient tolerated the visit'):
                with self.subTest(statement=statement, line=line):
                    self.assert_refused(line, statement)

    def test_lines_that_do_not_refuse_read_as_before(self):
        for line in ('Notes: patient tolerated the visit', 'Notes: No', 'Notes: None', 'Complications: None',
                     'Attested: Yes', 'Attested - Yes', 'Attested | Yes', 'Attested = Yes', 'Attested? Yes',
                     'Patient agrees with the plan.', 'Modifier 25 appended.',
                     'The E/M addressed new dysphagia, separate from the EGD.', 'E/M level: 99214', 'Modifier: 25',
                     'Attested by: Dr. Smith', 'Attested.', 'Same-day E/M documented separately.',
                     'Follow-up in 2 weeks; patient agrees.',
                     'I attest that the above E/M service was significant and separately identifiable.',
                     'Plan: Follow up in 2 weeks.', 'Procedure: Flexible sigmoidoscopy'):
            with self.subTest(line=line):
                self.assert_documented(line)



# --- box2:G -- a row of items in different box states, cited whole -----------------------------------------------------

G_REPORT = HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n{row}\n'
G_ROW = 'Interventions: \u2611 Cold snare polypectomy \u2610 Biopsy'


class Box2GRowCitedWholeTests(unittest.TestCase):
    """box2:G (high, declared box reading; ARCHITECTURE 5.3, 5.6). A cited passage holding two or more box-governed items
    whose boxes differ was read by one box: "Interventions: ☑ Cold snare polypectomy ☐ Biopsy" cited whole left 45380
    and 45385 READY, and "Cold snare polypectomy ☐ Biopsy" read negated by its last box. Such a passage is held
    (_B2_ITEMS_DIFFER, a doubt), never ready and never negated: the code's own item cannot be told from it (no CPT
    descriptor knowledge is used). Accepted over-hold: 45385 citing the same whole row."""

    def read(self, text, phrase):
        start = text.index(phrase)
        return detect.status_for_span(text, start, start + len(phrase), D)

    def assert_held(self, text, phrase):
        status, cues = self.read(text, phrase)
        self.assertEqual(status, 'uncertain', (phrase, cues))
        self.assertEqual(cues[0], getattr(detect, '_B2_ITEMS_DIFFER', None), (phrase, cues))

    def test_the_claimed_row_holds_both_codes(self):
        text = G_REPORT.format(row=G_ROW)
        self.assert_held(text, G_ROW)
        for code in ('45380', '45385'):
            with self.subTest(code=code):
                proposals, _ = real(text, (code, G_ROW))
                self.assertEqual(outcome(proposals[code]), 'held', [c.detail for c in proposals[code].checks])

    def test_a_passage_across_differing_items_is_never_ready_or_negated(self):
        for row, cited in ((G_ROW, 'Cold snare polypectomy \u2610 Biopsy'),
                           (G_ROW, '\u2611 Cold snare polypectomy \u2610 Biopsy'),
                           ('Interventions: \u2610 Biopsy \u2611 Cold snare polypectomy', 'Biopsy \u2611 Cold snare polypectomy'),
                           ('Interventions: [x] Cold snare polypectomy [ ] Biopsy', 'Interventions: [x] Cold snare polypectomy [ ] Biopsy'),
                           ('Interventions: Cold snare polypectomy \u2612 | Biopsy \u2610', 'Interventions: Cold snare polypectomy \u2612 | Biopsy \u2610'),
                           ('Interventions: Cold snare polypectomy: \u2612 Biopsy: \u2610', 'Cold snare polypectomy: \u2612 Biopsy: \u2610'),
                           ('Biopsy: \u2612 Yes \u2610 No  Cold snare polypectomy: \u2610 Yes \u2612 No',
                            'Biopsy: \u2612 Yes \u2610 No  Cold snare polypectomy: \u2610 Yes \u2612 No'),
                           ('- \u2611 Cold snare polypectomy \u2610 Biopsy \u2610 Hot snare', '\u2611 Cold snare polypectomy \u2610 Biopsy \u2610 Hot snare'),
                           ('Interventions: \u2611 Cold snare polypectomy \u2611 Hot snare \u2610 Biopsy',
                            'Interventions: \u2611 Cold snare polypectomy \u2611 Hot snare \u2610 Biopsy'),
                           # an item whose own boxes disagree, or one a later unchecked box may govern (BOX_LATER),
                           # beside another item's box: as doubtful as an unread one
                           ('\u2612\u2610 Biopsy \u2611 Cold snare polypectomy', 'Biopsy \u2611 Cold snare polypectomy'),
                           ('Polypectomy with cold snare: \u2610', 'Polypectomy with cold snare: \u2610'),
                           # read by the box of an entry that is no item ("Photos"): that box is no item's of the passage
                           ('Interventions: \u2610 Photos \u2611 Cold snare polypectomy',
                            'Interventions: \u2610 Photos \u2611 Cold snare polypectomy'),
                           ('Interventions: \u2610 Photos \u2611 Biopsy', 'Interventions: \u2610 Photos \u2611 Biopsy')):
            with self.subTest(row=row, cited=cited):
                text = G_REPORT.format(row=row)
                self.assert_held(text, cited)
                for code in ('45380', '45385'):
                    proposals, _ = real(text, (code, cited))
                    self.assertEqual(outcome(proposals[code]), 'held', (code, [c.detail for c in proposals[code].checks]))

    def test_each_item_cited_alone_keeps_its_reading(self):
        text = G_REPORT.format(row=G_ROW)
        self.assertEqual(self.read(text, '\u2611 Cold snare polypectomy')[0], 'performed')
        self.assertEqual(self.read(text, 'Cold snare polypectomy')[0], 'performed')
        self.assertEqual(self.read(text, '\u2610 Biopsy'), ('negated', (detect.UNCHECKED,)))
        self.assertEqual(self.read(text, 'Biopsy'), ('negated', (detect.UNCHECKED,)))
        proposals, _ = real(text, ('45385', '\u2611 Cold snare polypectomy'), ('45380', '\u2610 Biopsy'))
        self.assertEqual((outcome(proposals['45385']), outcome(proposals['45380'])), ('ready', 'excluded'))

    def test_rows_whose_items_agree_read_as_before(self):
        for row in ('Interventions: \u2611 Cold snare polypectomy \u2611 Biopsy', 'Interventions: \u2610 Hot snare \u2610 Biopsy',
                    'Interventions: \u2611 Cold snare polypectomy', 'Interventions: Cold snare polypectomy, biopsy.',
                    'Procedure status: \u2612 Completed \u2610 Cancelled', 'Biopsy taken: \u2612 Yes \u2610 No',
                    # an item no box governs counts for nothing beside a checked one; an entry that is no item, read
                    # after the item, leaves the item's own box reading it
                    'Colonoscopy with biopsy: \u2612', 'Hot snare \u2611 then Biopsy',
                    'Interventions: \u2611 Cold snare polypectomy \u2610 Photos', 'Biopsy: \u2610 Yes \u2612 No'):
            with self.subTest(row=row):
                text = G_REPORT.format(row=row)
                status, cues = self.read(text, row)
                self.assertNotIn(getattr(detect, '_B2_ITEMS_DIFFER', 'absent'), cues)
        text = G_REPORT.format(row='Interventions: \u2611 Cold snare polypectomy \u2611 Biopsy')
        proposals, _ = real(text, ('45385', 'Interventions: \u2611 Cold snare polypectomy \u2611 Biopsy'))
        self.assertEqual(outcome(proposals['45385']), 'ready')
        text = G_REPORT.format(row='Interventions: \u2610 Hot snare \u2610 Biopsy')
        proposals, _ = real(text, ('45380', 'Interventions: \u2610 Hot snare \u2610 Biopsy'))
        self.assertEqual(outcome(proposals['45380']), 'excluded')

    def test_the_hold_is_a_doubt(self):
        """It replaces a denial ("Cold snare polypectomy ☐ Biopsy" read negated), so it counts as doubt (contract-r4c 1)."""
        text = G_REPORT.format(row=G_ROW)
        an = detect._analysis(text, D)[0]
        for cited in (G_ROW, 'Cold snare polypectomy \u2610 Biopsy'):
            start = text.index(cited)
            reading = detect._generic_reading(an, start, start + len(cited))
            self.assertEqual((reading.status, reading.doubt), ('uncertain', True), cited)

    def test_routing_reads_the_row_as_before(self):
        """Routing's own readings (the family, its facts, each item) are unchanged: only a passage read whole moves."""
        route = detect.route(G_REPORT.format(row=G_ROW), D).finding('gi.colonoscopy')
        self.assertEqual(route.status, 'performed')
        self.assertEqual(dict((f.name, f.value) for f in route.facts)['interventions'], 'cold snare')



# --- box2:H -- a box opening a line takes no option label from the line above ------------------------------------------

H_REPORT = HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n{above}\n{line}\n'
H_LINE = '\u2612 Cold snare polypectomy of the 6 mm sigmoid polyp'
H_SILENT = detect.SILENT
H_FINDINGS = 'section: findings (Findings)'


class Box2HOptionLabelAcrossALineTests(unittest.TestCase):
    """box2:H (critical, a regression against R3B-BASE d05326ef). _OPTION_BEFORE read an option word back from a box with
    "$", which also matches before the newline that ends the search window: the last word of the line above ("none",
    "no", "not done") became the option label of a checked box opening the next line, which then read as an unchecked
    option, so "Complications: none / ☒ Cold snare polypectomy ..." was NEGATED and 45385 excluded (d05326ef: silent,
    not excluded). Every option-word lookbehind of that family (_OPTION_BEFORE, _BOX_BESIDE_BEFORE) now ends at the
    window's own end (\\Z): a box governs its own line, and the R3B-BASE readings come back."""

    def read(self, text, phrase):
        start = text.index(phrase)
        return detect.status_for_span(text, start, start + len(phrase), D)

    def test_the_claimed_lines_read_as_at_r3b(self):
        # Routing reads both lines as at r3b. Engine @4 decides 45385 by the documented snare removal: under
        # "Complications: none" (a field with its own answer) the checked box is in no list of what was done and no
        # statement documents the snare, so it is held for the reviewer, never ready and never excluded (the owner's
        # strict-box decision, 2026-10-25; triage round 2 skeptic: checked boxes under consent and equipment lists had
        # been read as done and sent for paid second reviews).
        for above, wanted, want in (('Complications: none', ('uncertain', (H_SILENT,)), 'held'),
                                    ('Procedures performed today: none', ('performed', (H_FINDINGS,)), 'ready')):
            with self.subTest(above=above):
                text = H_REPORT.format(above=above, line=H_LINE)
                self.assertEqual(self.read(text, H_LINE), wanted)
                proposals, _ = real(text, ('45385', H_LINE))
                self.assertEqual(outcome(proposals['45385']), want, [c.detail for c in proposals['45385'].checks])

    def test_every_option_word_ending_the_line_above(self):
        """A checked box opening a line is never negated, and no other rule fires on it for that reason (box2:G)."""
        for above in ('Complications: none', 'EBL: none', 'Biopsy: no', 'Polyps removed: not done', 'Tattoo: Not performed',
                      'Procedures performed today: none', 'Biopsy taken: yes', 'Retroflexion done', 'Biopsy performed',
                      'Complications: none  ', 'Biopsy: no\t'):
            for glyph in ('\u2612', '\u2611', '[x]', '(x)', '\u2713', '[*]'):
                line = glyph + ' Cold snare polypectomy of the 6 mm sigmoid polyp'
                with self.subTest(above=above, glyph=glyph):
                    text = H_REPORT.format(above=above, line=line)
                    status, cues = self.read(text, line)
                    self.assertNotEqual(status, 'negated', cues)
                    self.assertNotIn(detect.UNCHECKED, cues)
                    self.assertNotIn(getattr(detect, '_B2_ITEMS_DIFFER', 'absent'), cues)
                    proposals, _ = real(text, ('45385', line))
                    self.assertNotEqual(outcome(proposals['45385']), 'excluded')

    def test_an_unchecked_box_opening_a_line_denies_its_own_item(self):
        """The R3B-BASE reading, a structural box state: "Complications: none / ☐ Cold snare polypectomy" read silent at
        the base (the "none" above made the box an option with no answer)."""
        for above in ('Complications: none', 'Biopsy: no', 'Cecum reached: yes'):
            for glyph in ('\u2610', '[ ]', '( )'):
                line = glyph + ' Cold snare polypectomy of the 6 mm sigmoid polyp'
                with self.subTest(above=above, glyph=glyph):
                    self.assertEqual(self.read(H_REPORT.format(above=above, line=line), line),
                                     ('negated', (detect.UNCHECKED,)))

    def test_a_selected_denial_option_naming_no_item_is_held(self):
        """Read on its own line, "☒ Not performed" under "Biopsy taken: yes" no longer reads performed (the "yes" above was
        its option label); it reads as round 5 declared:8 holds such a line, never negated: it names nothing it could
        deny (R3B-BASE held it too). The base negated it under any other line."""
        for above in ('Prep: good', 'Biopsy taken: yes', 'Complications: none', 'Retroflexion done'):
            for line in ('\u2612 Not performed', 'Performed \u2610 Not performed \u2612', 'Completed | \u2610 | Not done | \u2612',
                         '[x] Not done'):
                with self.subTest(above=above, line=line):
                    text = H_REPORT.format(above=above, line=line)
                    status, cues = self.read(text, line)
                    self.assertEqual(status, 'uncertain', cues)
                    self.assertTrue(cues[0].startswith('uncertain: a status option on the line'), cues)
                    proposals, _ = real(text, ('45378', line))
                    self.assertEqual(outcome(proposals['45378']), 'held')
        text = H_REPORT.format(above='Prep: good', line='\u2612 Not performed\n\u2612 Not done')
        self.assertEqual(self.read(text, '\u2612 Not performed\n\u2612 Not done')[0], 'uncertain')  # two such lines, cited together
        for line, status in (('Biopsy: [x] Not performed', 'negated'), ('Procedure performed: \u2610 Yes \u2612 No', 'negated'),
                             ('\u2610 Not performed', 'uncertain')):
            with self.subTest(line=line):  # an item's own denial, a done-question answered no, an unchecked option
                self.assertEqual(self.read(H_REPORT.format(above='Prep: good', line=line), line)[0], status)

    def test_options_on_their_own_line_read_as_before(self):
        for line, status in (('Biopsy taken: \u2612 Yes \u2610 No', 'performed'), ('Biopsy taken: \u2610 Yes \u2612 No', 'negated'),
                             ('Biopsy taken: Yes \u2612 No \u2610', 'performed'), ('Biopsy taken: Yes \u2610 No \u2612', 'negated'),
                             ('Biopsy taken: No \u2612', 'negated')):
            with self.subTest(line=line):
                text = H_REPORT.format(above='Cecum reached: yes', line=line)  # a line that keeps the findings section
                self.assertEqual(self.read(text, 'Biopsy')[0], status)

    def test_the_lookbehinds_end_at_their_window(self):
        for pattern, text, at in ((detect._OPTION_BEFORE, 'Complications: none\n\u2612', None),
                                  (detect._OPTION_BEFORE, 'Biopsy taken: No \u2612', 'match'),
                                  (detect._BOX_BESIDE_BEFORE, 'Status: Completed \u2610\nPending', None),
                                  (detect._BOX_BESIDE_BEFORE, 'Status: Completed \u2610 Pending', 'match')):
            with self.subTest(text=text):
                end = len(text) - 1 if text.endswith('\u2612') else text.rindex('Pending')
                found = pattern.search(text, max(0, end - 20), end)
                self.assertEqual(found is not None, at == 'match', (text, found))



# --- box2:I -- an unchecked option's own words state nothing about the service or the item beside it ---------------

I_REPORT = HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n{row}\n'


def family_status(text, slug='gi.colonoscopy'):
    finding = detect.route(text, D).finding(slug)
    return finding.status if finding else None


class Box2IUnselectedOptionTests(unittest.TestCase):
    """box2:I (high, a declared misread at every tree; ARCHITECTURE 5.3, round 4c regression:4: an option every denying
    option of which has its own unchecked box states nothing, in every reader of the line). _box_own_option_off reached
    the status references and the called-off reader, not the clause cues a service or an item is read by: "Colonoscopy:
    ☒ Completed ☐ Cancelled" read CANCELLED (family, mention, row; 45378 excluded), and "☑ Cold snare polypectomy ☐
    Repeat in 3 years" read PLANNED, the checked polypectomy cited alone too (45385 excluded). A denying or plan option
    whose own box is unchecked now states nothing about a target outside its own words; one whose box cannot be read or
    disagrees holds it. Never newly negated or excluded. The mirrored rows read so too: a status line's label is read by
    its options, not by the first box after it (an option's), the words of an unchecked option right after the label
    deny nothing, and an item an option's box was taken for is held; a line that selects nothing holds."""

    def read(self, text, phrase, within=None):
        start = text.index(phrase) if within is None else text.index(within) + within.index(phrase)
        return detect.status_for_span(text, start, start + len(phrase), D)

    def test_an_unchecked_status_option_cancels_nothing(self):
        for row in ('Colonoscopy: \u2612 Completed \u2610 Cancelled', 'Colonoscopy: Completed \u2612 | Cancelled \u2610',
                    'Colonoscopy: \u2612 Completed \u2610 Deferred', 'Colonoscopy: \u2612 Completed \u2610 Postponed',
                    'Colonoscopy: \u2612 Completed \u2610 Not done', 'Colonoscopy: \u2612 Completed \u2610 Rescheduled',
                    'Colonoscopy: \u2612 Completed \u2610 Aborted \u2610 Cancelled', '- Colonoscopy: [x] Completed [ ] Cancelled',
                    'Colonoscopy | \u2612 Completed | \u2610 Cancelled', 'Colonoscopy: \u2612 Completed \u2610 Incomplete \u2610 Aborted',
                    'Colonoscopy status: \u2612 Completed \u2610 Aborted', 'Colonoscopy: \u2612 Completed \u2610 Pending'):
            with self.subTest(row=row):
                text = I_REPORT.format(row=row)
                self.assertEqual(family_status(text), 'performed')  # read as the rest of the report reads it
                label = row.lstrip('- ')
                status, cues = self.read(text, 'Colonoscopy', within=label)  # the row's own label, not the heading's
                self.assertEqual(status, 'performed', cues)
                status, cues = self.read(text, label)  # the row cited whole runs across the unchecked option: held
                self.assertEqual(status, 'uncertain', cues)
                proposals, _ = real(text, ('45378', label))
                self.assertEqual(outcome(proposals['45378']), 'held')
                proposals, _ = real(text, ('45378', 'The colonoscope was advanced to the cecum.'))
                self.assertEqual(outcome(proposals['45378']), 'ready')

    def test_an_unchecked_plan_option_plans_nothing_beside_it(self):
        for row, item, wanted in (('\u2611 Cold snare polypectomy \u2610 Repeat in 3 years', '\u2611 Cold snare polypectomy', 'ready'),
                                  ('\u2611 Biopsy \u2610 Not done', '\u2611 Biopsy', 'ready'),
                                  # a row opening with an item, its boxes trailing: read by its entries, not its options
                                  ('Cold snare polypectomy \u2612 | Repeat in 3 years \u2610', 'Cold snare polypectomy \u2612',
                                   'ready'),
                                  # held, never planned: "next visit" is a time another reader holds
                                  ('\u2611 Cold snare polypectomy \u2610 Planned for next visit', '\u2611 Cold snare polypectomy',
                                   ('ready', 'held'))):
            with self.subTest(row=row):
                text = I_REPORT.format(row=row)
                status, cues = self.read(text, item)
                self.assertEqual(status, 'performed', cues) if wanted == 'ready' else self.assertIn(
                    status, ('performed', 'uncertain'), cues)
                code = '45380' if 'Biopsy' in item else '45385'
                proposals, _ = real(text, (code, item))
                if wanted == 'ready':
                    self.assertEqual(outcome(proposals[code]), 'ready', [c.detail for c in proposals[code].checks])
                else:
                    self.assertIn(outcome(proposals[code]), wanted)
                status, cues = self.read(text, row)  # the row cited whole: held, never planned or cancelled
                self.assertEqual(status, 'uncertain', cues)

    def test_an_option_whose_box_cannot_be_read_holds(self):
        for row in ('Colonoscopy: \u2612 Completed [?] Cancelled', 'Colonoscopy: \u2612 Completed \u2612\u2610 Cancelled',
                    'Colonoscopy: \u2612 Completed (\u2022) Cancelled'):
            with self.subTest(row=row):
                text = I_REPORT.format(row=row)
                status, cues = self.read(text, 'Colonoscopy:')
                self.assertEqual(status, 'uncertain', cues)
                self.assertNotEqual(family_status(text), 'cancelled')
                proposals, _ = real(text, ('45378', row))
                self.assertEqual(outcome(proposals['45378']), 'held')

    def test_the_mirrored_status_row_reads_by_its_options(self):
        """The denying option first: the label was read by the first box after it, the option's, NEGATED at every tree
        (int2, 4347acd, d05326ef); an act denial right after the label ("Not performed ☐") denied it as a member's."""
        for row, label in (('Colonoscopy: \u2610 Cancelled \u2612 Completed', 'Colonoscopy:'),
                           ('Colonoscopy: Cancelled \u2610 | Completed \u2612', 'Colonoscopy:'),
                           ('Colonoscopy status: \u2610 Aborted \u2612 Completed', 'Colonoscopy status:'),
                           ('Colonoscopy | \u2610 Incomplete | \u2612 Completed', 'Colonoscopy |'),
                           ('Colonoscopy: Not performed \u2610 | Performed \u2612', 'Colonoscopy:'),
                           ('Colonoscopy: Incomplete \u2610 | Completed \u2612', 'Colonoscopy:'),
                           ('Colonoscopy: [ ] Postponed [x] Done', 'Colonoscopy:'),
                           ('Colonoscopy: \u2610 Pending \u2612 Completed', 'Colonoscopy:'),
                           ('Colonoscopy: \u2610 Aborted \u2610 Cancelled \u2612 Completed', 'Colonoscopy:')):
            with self.subTest(row=row):
                text = I_REPORT.format(row=row)
                self.assertEqual(family_status(text), 'performed')
                status, cues = self.read(text, 'Colonoscopy', within=row)
                self.assertEqual(status, 'performed', cues)
                status, cues = self.read(text, row)  # the row cited whole runs from the label across the options: held
                self.assertEqual(status, 'uncertain', cues)
                proposals, _ = real(text, ('45378', label))
                self.assertEqual(outcome(proposals['45378']), 'ready', [c.detail for c in proposals['45378'].checks])
                proposals, _ = real(text, ('45378', row))
                self.assertEqual(outcome(proposals['45378']), 'held')
        text = I_REPORT.format(row='Cold snare polypectomy: \u2610 Planned \u2612 Done')  # an item's label
        self.assertEqual(self.read(text, 'Cold snare polypectomy')[0], 'performed')
        proposals, _ = real(text, ('45385', 'Cold snare polypectomy:'))
        self.assertEqual(outcome(proposals['45385']), 'ready', [c.detail for c in proposals['45385'].checks])

    def test_an_item_read_by_an_options_box_holds(self):
        """The box reader sees no option word: "Repeat in 3 years ☐ | Cold snare polypectomy ☒" looks as if its boxes
        lead, so the polypectomy was read by the option's ☐ (NEGATED, 45385 excluded). Read by the line's entries, its
        own box is checked: the readers disagree, so it is held (never ready by this rule). A line that can be read
        both ways, or a label whose option cannot be read, holds too."""
        for row, item, whole in (('Repeat in 3 years \u2610 | Cold snare polypectomy \u2612', 'Cold snare polypectomy', 'held'),
                                 ('Planned \u2610 | Cold snare polypectomy \u2612', 'Cold snare polypectomy', 'held'),
                                 # the row cited whole read performed at every tree (no reader takes its "Not"); round 4d
                                 # BOXES3 (strict check-box rows): the box reader leads and the entries trail, so the row
                                 # cannot be paired and is held whole
                                 ('Not performed [ ] | Cold snare polypectomy [x]', 'Cold snare polypectomy', 'held'),
                                 ('Colonoscopy \u2610 Cancelled \u2612 Completed', 'Colonoscopy', 'held'),
                                 ('Colonoscopy: \u2610 Cancelled [?] Completed', 'Colonoscopy', 'held')):
            with self.subTest(row=row):
                text = I_REPORT.format(row=row)
                status, cues = self.read(text, item, within=row)
                self.assertEqual(status, 'uncertain', cues)
                status, cues = self.read(text, row)
                self.assertEqual(status, 'uncertain' if whole == 'held' else 'performed', cues)
                code = '45385' if 'polypectomy' in item else '45378'
                proposals, _ = real(text, (code, row))
                self.assertEqual(outcome(proposals[code]), whole, [c.detail for c in proposals[code].checks])
        for row in ('\u2610 Repeat in 3 years \u2611 Cold snare polypectomy', '\u2610 Planned \u2611 Cold snare polypectomy'):
            with self.subTest(row=row):  # its boxes lead: the polypectomy's own box is checked and read so
                text = I_REPORT.format(row=row)
                self.assertEqual(self.read(text, 'Cold snare polypectomy')[0], 'performed')

    def test_an_unchecked_option_never_releases_an_item_not_itself_checked(self):
        """The option's words are dropped only for a target whose own items are checked: the box reader, which sees no
        option word, reads "Planned ☐ | Biopsy ☒ | Cold snare polypectomy ☐" as if its boxes lead, so the unchecked
        polypectomy took the biopsy's ☒, and only the "Planned" cue kept it from reading performed (planned at the
        base). It is held, never performed and never ready."""
        for row in ('Planned \u2610 | Biopsy \u2612 | Cold snare polypectomy \u2610',
                    'Repeat in 3 years \u2610 | Biopsy \u2612 | Cold snare polypectomy \u2610',
                    'Rescheduled [ ] | Biopsy [x] | Cold snare polypectomy [ ]'):
            with self.subTest(row=row):
                text = I_REPORT.format(row=row)
                status, cues = self.read(text, 'Cold snare polypectomy', within=row)
                self.assertNotEqual(status, 'performed', cues)
                self.assertEqual(status, 'uncertain', cues)
                proposals, _ = real(text, ('45385', 'Cold snare polypectomy'))
                self.assertNotEqual(outcome(proposals['45385']), 'ready')
                self.assertEqual(outcome(proposals['45385']), 'held')

    def test_an_item_read_by_another_entrys_checked_box_holds(self):
        """The false-ready direction of the same misreading: on a status line the box reader, which sees no option word,
        gave the unchecked polypectomy of "Not performed ☐ Biopsy ☒ Cold snare polypectomy ☐" the biopsy's ☒ (PERFORMED
        at int2 and 4347acd, 45385 ready; negated at d05326ef). Read by the line's entries, its own box is unchecked: it
        is held, never ready."""
        for row in ('Not performed \u2610 Biopsy \u2612 Cold snare polypectomy \u2610',
                    'Not performed [ ] | Biopsy [x] | Cold snare polypectomy [ ]',
                    'Repeat in 3 years \u2612 | Cold snare polypectomy \u2610'):
            with self.subTest(row=row):
                text = I_REPORT.format(row=row)
                status, cues = self.read(text, 'Cold snare polypectomy', within=row)
                self.assertEqual(status, 'uncertain', cues)
                proposals, _ = real(text, ('45385', 'Cold snare polypectomy'))
                self.assertEqual(outcome(proposals['45385']), 'held')

    def test_a_remark_in_an_unchecked_option_holds(self):
        """Self-review of box2:I: every denying word of a boxed line is an option word to _box_denying_options, so a
        remark after an unchecked option ("☐ Cancelled - aborted at the splenic flexure") took the option's box and was
        dropped, and the colonoscopy read PERFORMED (cancelled or incomplete at int2: 45378 ready). An unchecked option
        whose text holds more than one run of denying words is held, never dropped; one run reads as the option."""
        bare = HEAD + 'Procedure note\n{row}\nThe patient tolerated it well.\n'
        for frame, row in ((bare, 'Colonoscopy: \u2612 Completed \u2610 Cancelled - aborted at the splenic flexure'),
                           (bare, 'Colonoscopy: \u2612 Completed \u2610 Cancelled; patient declined further sedation'),
                           (I_REPORT, 'Colonoscopy: \u2612 Completed \u2610 Incomplete - unable to reach the cecum'),
                           (I_REPORT, 'Colonoscopy: \u2612 Completed \u2610 Cancelled (aborted)'),
                           (I_REPORT, 'Colonoscopy: \u2612 Completed \u2610 Cancelled, scope could not pass the sigmoid'),
                # the remark after an unchecked completion: a hold keeps the rank of the abort it stands for, so the
                # checked rescheduling alone never reads it planned (incomplete at int2)
                (I_REPORT, 'Colonoscopy: \u2612 Rescheduled \u2610 Completed - aborted at the splenic flexure'),
                # a status label whose unchecked option may hold a remark is held, not read by its options
                (I_REPORT, 'Colonoscopy: \u2610 Incomplete - patient declined further sedation \u2612 Completed')):
            with self.subTest(row=row):
                text = frame.format(row=row)
                status, cues = self.read(text, 'Colonoscopy', within=row)
                self.assertEqual(status, 'uncertain', cues)
                self.assertNotEqual(family_status(text), 'performed')
                proposals, _ = real(text, ('45378', 'Colonoscopy:'))
                self.assertNotEqual(outcome(proposals['45378']), 'ready')
        for row in ('Colonoscopy: \u2612 Completed \u2610 Cancelled (patient preference)',
                    'Colonoscopy: \u2612 Completed \u2610 Repeat colonoscopy in 5 years',
                    'Colonoscopy: \u2612 Completed \u2610 Not done today'):
            with self.subTest(control=row):  # one run of denying words: the option's own, read as box2:I reads it
                text = I_REPORT.format(row=row)
                self.assertEqual(self.read(text, 'Colonoscopy', within=row)[0], 'performed')

    def test_an_unchecked_hold_or_hedge_option_holds_nothing(self):
        """An unselected option neither denies nor holds (_unchecked_option): an unchecked hold word, hedge or abort with
        no start statement held the service at every tree ("☐ Pending" by ending its section's reach; "☐ If needed",
        "☐ Aborted" as clause cues). A blank frame shows the abort case: nothing there says the scope went in."""
        bare = HEAD + 'Procedure note\n{row}\nThe patient tolerated it well.\n'
        for frame, row in ((I_REPORT, 'Colonoscopy: \u2612 Completed \u2610 Pending'),
                           (I_REPORT, 'Colonoscopy: \u2612 Completed \u2610 On hold'),
                           (I_REPORT, 'Colonoscopy: \u2612 Completed \u2610 If needed'),
                           (I_REPORT, 'Colonoscopy: Pending \u2610 | Completed \u2612'),
                           (bare, 'Colonoscopy: \u2612 Completed \u2610 Aborted'),
                           (bare, 'Colonoscopy: \u2612 Completed \u2610 If needed')):
            with self.subTest(row=row, bare=frame is bare):
                text = frame.format(row=row)
                self.assertEqual(family_status(text), 'performed')
                status, cues = self.read(text, 'Colonoscopy', within=row)
                self.assertEqual(status, 'performed', cues)
        for row, status in (('Colonoscopy: \u2612 Completed. Repeat if needed.', 'uncertain'),  # prose: no option
                            ('Colonoscopy: \u2612 Completed \u2612 Pending', 'uncertain'),     # a checked hold holds
                            ('Colonoscopy: \u2612 Completed \u2610 Declined', 'uncertain')):   # a negation doubt stays
            with self.subTest(control=row):
                cited = 'Repeat if needed.' if 'Repeat' in row else 'Colonoscopy'
                self.assertEqual(self.read(I_REPORT.format(row=row), cited, within=row)[0], status)

    def test_a_line_that_selects_nothing_holds(self):
        """Both boxes unchecked: the line says nothing either way, so an unchecked option's words are held, never
        dropped ("Colonoscopy: ☐ Not done ☐ Completed" read CANCELLED at the base). The label read by its own unchecked
        box stays denied, as at the base."""
        text = I_REPORT.format(row='Colonoscopy: \u2610 Not done \u2610 Completed')
        self.assertEqual(family_status(text), 'uncertain')
        status, cues = self.read(text, 'Colonoscopy', within='Colonoscopy: \u2610 Not done')
        self.assertEqual(status, 'uncertain', cues)
        self.assertIn("uncertain: 'Not done' is an unchecked option on a line that selects nothing", cues)
        text = I_REPORT.format(row='Colonoscopy: \u2610 Cancelled \u2610 Completed')
        self.assertEqual(family_status(text), 'negated')

    def test_controls_read_as_before(self):
        """A checked denying option, prose after a box, an option whose own words hold the target, and a hold."""
        for row in ('Colonoscopy: \u2612 Cancelled \u2610 Completed', 'Colonoscopy: Cancelled \u2612 | Completed \u2610',
                    'Colonoscopy | \u2612 Cancelled | \u2610 Completed'):
            with self.subTest(row=row):  # a checked cancellation still cancels, whichever way its boxes are written
                text = I_REPORT.format(row=row)
                self.assertEqual(family_status(text), 'cancelled')
                self.assertEqual(self.read(text, row)[0], 'cancelled')
        text = I_REPORT.format(row='Colonoscopy: \u2610 Completed \u2612 Cancelled')
        self.assertEqual(family_status(text), 'negated')
        self.assertEqual(self.read(text, 'Colonoscopy: \u2610 Completed \u2612 Cancelled')[0], 'negated')
        text = I_REPORT.format(row='\u2610 Cold snare polypectomy \u2612 Repeat in 3 years')
        self.assertEqual(self.read(text, '\u2610 Cold snare polypectomy')[0], 'negated')
        for row, cited, status in (('\u2610 Cold snare polypectomy. Repeat colonoscopy in 3 years.', 'Repeat colonoscopy in 3 years.',
                                    'planned'),
                                   ('\u2611 Cold snare polypectomy \u2610 Biopsy. Repeat colonoscopy in 3 years.',
                                    'Repeat colonoscopy in 3 years.', 'planned'),
                                   ('\u2611 Cold snare polypectomy. Repeat colonoscopy in 3 years.', 'Repeat colonoscopy in 3 years.',
                                    'planned'),
                                   ('\u2610 Repeat colonoscopy in 3 years', '\u2610 Repeat colonoscopy in 3 years', 'negated'),
                                   ('Colonoscopy: \u2612 Done \u2610 Declined', 'Colonoscopy:', 'uncertain')):
            with self.subTest(row=row):
                self.assertEqual(self.read(I_REPORT.format(row=row), cited)[0], status)
        text = HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\nPlan: Repeat colonoscopy in 3 years.\n'
        self.assertEqual(self.read(text, 'Repeat colonoscopy in 3 years.')[0], 'planned')
        for row, cited, status in (('Colonoscopy attempted?: \u2610 Yes \u2612 No', 'Colonoscopy', 'negated'),
                                   ('Colonoscopy completed? \u2610 Yes \u2611 No', 'Colonoscopy', 'negated'),
                                   ('Follow-up colonoscopy in 3 years ( )', 'colonoscopy', 'negated'),
                                   ('Colonoscopy cancelled: [ ] Yes [x] No', 'Colonoscopy', 'negated'),
                                   # round 4d BOXES3 (strict check-box rows): the option readers take the checked plan
                                   # option's box for the polypectomy's ☐, so the row cannot be paired: held, never negated
                                   ('Cold snare polypectomy \u2610 | Repeat in 3 years \u2612', 'Cold snare polypectomy', 'uncertain'),
                                   ('Colonoscopy: \u2612 Cancelled \u2610 Completed', 'Colonoscopy', 'cancelled')):
            with self.subTest(control=row):  # yes / no questions, a plan line, an item's own unchecked box
                self.assertEqual(self.read(I_REPORT.format(row=row), cited, within=row)[0], status)



# --- box2:J -- an E/M visit statement governed by an unread mark or an unchecked box ---------------------------------

J_OFFICE = HEAD + ('Place of service: Office (POS 11)\n{line}\nChief complaint: Heartburn.\nAssessment and plan: PPI.\n'
                   'Medical decision making: moderate.\n')


def em_mentions(text):
    finding = detect.route(text, D).finding('gi.office_em')
    return [(m.span.text, m.status, m.cues) for m in (finding.mentions if finding else ())]


class Box2JVisitStatementBoxTests(unittest.TestCase):
    """box2:J (critical, a regression against 9a9f403 and 4347acd from round 4c's extraction:8). The "?" of an unread
    mark is no hedge any more, and the item the mark governs is held, but only for the box reader's items: an E/M
    visit statement is none, so "[?] Established patient office visit." read PERFORMED (the span and the office-visit
    mention), and 99214 citing it was READY (held at both bases, by the old "?" hedge). "☐ Established patient office
    visit." read performed at every tree (a declared box-vocabulary misread). A visit statement a box governs (its own
    line or cell, before or after it, as any passage is read) is held when that box is unread, unchecked or
    disagreeing; a checked box, or none, reads as before. Never excluded."""

    def read(self, text, phrase, within=None):
        start = text.index(phrase) if within is None else text.index(within) + within.index(phrase)
        return detect.status_for_span(text, start, start + len(phrase), D)

    def test_an_unread_mark_holds_the_visit_statement(self):
        for line in ('[?] Established patient office visit.', 'Established patient office visit [?]',
                     '\u25a2 Established patient office visit.', 'Established patient office visit | [?]',
                     '[?] Office visit'):
            with self.subTest(line=line):
                text = J_OFFICE.format(line=line)
                status, cues = self.read(text, line)
                self.assertEqual(status, 'uncertain', cues)
                self.assertTrue(any('visit statement' in c for c in cues), cues)
                visit = [m for m in em_mentions(text) if 'visit' in m[0].lower()]
                self.assertTrue(visit and all(m[1] == 'uncertain' for m in visit), visit)
                proposals, _ = real(text, ('99214', line))
                self.assertEqual(outcome(proposals['99214']), 'held')

    def test_an_unchecked_box_holds_the_visit_statement(self):
        for line in ('\u2610 Established patient office visit.', '[ ] Established patient office visit',
                     'Established patient office visit | \u2610', 'Established patient office visit: \u2610 Yes \u2612 No',
                     '\u2612 Anoscopy \u2610 Established patient office visit', 'Established patient office visit \u2610 Anoscopy \u2612',
                     # boxes of the statement that disagree; a form line that marks it off
                     '\u2612\u2610 Established patient office visit.', 'Established patient office visit \u2612 \u2610',
                     'Established patient office visit: not checked'):
            with self.subTest(line=line):
                text = J_OFFICE.format(line=line)
                visit = 'Established patient office visit'
                status, cues = self.read(text, visit, within=line)
                self.assertEqual(status, 'uncertain', cues)  # held, never negated
                proposals, _ = real(text, ('99214', visit))
                self.assertEqual(outcome(proposals['99214']), 'held')
                self.assertEqual(detect.route(text, D).finding('gi.office_em').status, 'performed')  # by its other mentions

    def test_a_checked_box_or_none_reads_as_before(self):
        for line in ('\u2612 Established patient office visit.', '[x] Established patient office visit',
                     'Established patient office visit: \u2612 Yes \u2610 No', 'Established patient office visit | \u2611',
                     'Established patient office visit.', '\u2610 Anoscopy. Established patient office visit.',
                     '\u2610 Anoscopy \u2612 Established patient office visit'):
            with self.subTest(line=line):
                text = J_OFFICE.format(line=line)
                phrase = 'Established patient office visit'
                status, cues = self.read(text, phrase, within=line)
                self.assertEqual(status, 'performed', cues)
                proposals, _ = real(text, ('99214', phrase))
                self.assertEqual(outcome(proposals['99214']), 'ready', [c.detail for c in proposals['99214'].checks])

    def test_a_status_label_reads_by_its_options(self):
        """The visit statement as a status line's label is read by the line's options (box2:I): an unchecked
        cancellation states nothing (it read CANCELLED at the base), and the label is not read by the option's box.
        ("Office visit" alone lacks the patient-status fact, which holds 99214 by itself.)"""
        for line in ('Established patient office visit: \u2612 Completed \u2610 Cancelled',
                     'Established patient office visit: \u2610 Cancelled \u2612 Completed'):
            with self.subTest(line=line):
                text = J_OFFICE.format(line=line)
                status, cues = self.read(text, 'Established patient office visit', within=line)
                self.assertEqual(status, 'performed', cues)
                proposals, _ = real(text, ('99214', 'Established patient office visit'))
                self.assertEqual(outcome(proposals['99214']), 'ready', [c.detail for c in proposals['99214'].checks])
        text = J_OFFICE.format(line='Established patient office visit: \u2610 Cancelled [?] Completed')
        self.assertEqual(self.read(text, 'Established patient office visit')[0], 'uncertain')

    def test_option_rows_read_option_by_option(self):
        """The unchecked option of another visit type never holds the checked one: each statement is read by its own
        box, also where the boxes trail. (99214 stays held there by the context facts, which read the unchecked
        option's "New patient" as documented too: "conflicting values", at every tree; the visit statement itself
        documents the visit, as the service.status check says.)"""
        for line, checked, unchecked in (
                ('Visit type: \u2610 New patient visit \u2612 Established patient visit', 'Established patient visit',
                 'New patient visit'),
                ('Visit type: New patient visit \u2610 | Established patient visit \u2612', 'Established patient visit',
                 'New patient visit'),
                ('Visit type: \u2612 New patient visit \u2610 Established patient visit', 'New patient visit',
                 'Established patient visit')):
            with self.subTest(line=line):
                text = J_OFFICE.format(line=line)
                self.assertEqual(self.read(text, checked, within=line)[0], 'performed')
                self.assertEqual(self.read(text, unchecked, within=line)[0], 'uncertain')
                # engine @4: the status check describes the documented visit; whether the cited statement documents it
                # is that check's status and the performed-status question (99214 is held by the context facts alone)
                proposals, _ = real(text, ('99214', checked))
                self.assertEqual(check_of(proposals['99214'], 'service.status').status, 'pass')
                self.assertNotIn('performed_status', [c.fact for c in proposals['99214'].clarifications])
                self.assertNotEqual(outcome(proposals['99214']), 'excluded')
                proposals, _ = real(text, ('99214', unchecked))
                self.assertEqual(check_of(proposals['99214'], 'service.status').status, 'warn')
                self.assertIn('performed_status', [c.fact for c in proposals['99214'].clarifications])
                self.assertEqual(outcome(proposals['99214']), 'held')

    def test_controls_read_as_before(self):
        """A denial in the statement's own words stays; a plan visit stays planned; the visit and a procedure in one
        name is box2:E's; a status label whose cancellation is checked stays cancelled."""
        text = J_OFFICE.format(line='Office visit: \u2610 Completed \u2612 Cancelled')
        self.assertEqual(self.read(text, 'Office visit')[0], 'cancelled')
        for line in ('Plan: \u2610 Follow-up office visit in 3 months.', 'Plan: \u2610 Follow-up office visit.'):
            with self.subTest(line=line):  # a visit the plan section reads planned is not held by its box
                text = J_OFFICE.format(line=line)
                self.assertEqual(self.read(text, 'Follow-up office visit')[0], 'planned')
        text = J_OFFICE.format(line='Established patient office visit was cancelled.')
        self.assertEqual(self.read(text, 'Established patient office visit')[0], 'cancelled')



# --- box2:K -- a row whose first word is neither an item nor an option -------------------------------------------------

K_REPORT = HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n{row}\n'


class Box2KNonItemFirstWordTests(unittest.TestCase):
    """box2:K (critical, a regression against d05326ef). The box reader orients a row by its items: a first word that
    is neither an item nor an option ("Photos ☐ | Biopsy ☒ | Cold snare polypectomy ☐") puts the first box before the
    first item, so the row read as leading and every item took the box of the entry before it: the unchecked
    polypectomy read PERFORMED (45385 ready), the checked biopsy negated; d05326ef read each by its own box. Read with
    every word run between the boxes as an entry, the row trails; where that reading and the box reader's give an item
    different boxes (ARCHITECTURE 5.3: a row whose boxes can be read as leading or trailing holds the items the
    readings disagree on), the item is held: never performed, never newly negated."""

    def read(self, text, phrase, within):
        start = text.index(within) + within.index(phrase)
        return detect.status_for_span(text, start, start + len(phrase), D)

    def test_the_claimed_rows_never_read_the_unchecked_item_performed(self):
        for row in ('Photos \u2610 | Biopsy \u2612 | Cold snare polypectomy \u2610', 'Photos \u2610 Biopsy \u2612 Cold snare polypectomy \u2610',
                    'Retroflexion \u2610 | Biopsy \u2612 | Cold snare polypectomy \u2610',
                    'Photos taken [ ] | Biopsy [x] | Cold snare polypectomy [ ]', 'Photos \u2612 | Cold snare polypectomy \u2610'):
            with self.subTest(row=row):
                text = K_REPORT.format(row=row)
                status, cues = self.read(text, 'Cold snare polypectomy', row)
                self.assertEqual(status, 'uncertain', cues)
                proposals, _ = real(text, ('45385', 'Cold snare polypectomy'))
                self.assertEqual(outcome(proposals['45385']), 'held')

    def test_the_checked_item_is_held_never_negated(self):
        for row, item in (('Photos \u2610 | Biopsy \u2612 | Cold snare polypectomy \u2610', 'Biopsy'),
                          ('Photos \u2610 | Biopsy \u2612', 'Biopsy'),
                          ('Photos \u2610 | Cold snare polypectomy \u2612', 'Cold snare polypectomy'),
                          ('Photos \u2612 | Biopsy \u2610 | Cold snare polypectomy \u2612', 'Cold snare polypectomy')):
            with self.subTest(row=row):
                text = K_REPORT.format(row=row)
                status, cues = self.read(text, item, row)
                self.assertEqual(status, 'uncertain', cues)
        text = K_REPORT.format(row='Photos \u2612 | Biopsy \u2610 | Cold snare polypectomy \u2612')
        self.assertEqual(self.read(text, 'Biopsy', 'Photos \u2612 | Biopsy')[0], 'uncertain')  # the false ready: held

    def test_rows_both_readings_agree_on_read_as_before(self):
        for row, item, status in (('Tattoo \u2610 | Biopsy \u2612 | Cold snare polypectomy \u2610', 'Cold snare polypectomy', 'negated'),
                                  ('Tattoo \u2610 | Biopsy \u2612 | Cold snare polypectomy \u2610', 'Biopsy', 'performed'),
                                  ('Biopsy \u2612 | Cold snare polypectomy \u2610', 'Cold snare polypectomy', 'negated'),
                                  ('\u2610 Photos \u2612 Biopsy \u2610 Cold snare polypectomy', 'Cold snare polypectomy', 'negated'),
                                  ('\u2610 Photos \u2612 Biopsy \u2610 Cold snare polypectomy', 'Biopsy', 'performed'),
                                  ('Biopsy | \u2610 | Cold snare polypectomy | \u2612', 'Cold snare polypectomy', 'performed'),
                                  ('Biopsy | \u2610 | Cold snare polypectomy | \u2612', 'Biopsy', 'negated'),
                                  ('Colonoscopy: \u2610 biopsy \u2612 cold snare polypectomy', 'cold snare polypectomy', 'performed'),
                                  ('Colonoscopy: \u2610 biopsy \u2612 cold snare polypectomy', 'biopsy', 'negated'),
                                  # one box fewer than the entries: the readings cannot be told apart (read as at
                                  # d05326ef before round 4d); BOXES3's strict rows hold it: the last entry may be a remark
                                  # or the checked box's item
                                  ('Photos \u2610 Biopsy \u2612 Cold snare polypectomy', 'Cold snare polypectomy', 'uncertain'),
                                  ('\u2611 Cold snare polypectomy \u2610 Biopsy', 'Cold snare polypectomy', 'performed'),
                                  # a yes / no answer is read by the option it marks; entries labelled "X:" are round 4c's
                                  ('Biopsy No \u2612', 'Biopsy', 'negated'),
                                  ('Colonoscopy: \u2610 EGD: \u2612 dilation to 15 mm', 'EGD', 'performed')):
            with self.subTest(row=row, item=item):
                self.assertEqual(self.read(K_REPORT.format(row=row), item, row)[0], status)

    def test_a_status_reference_reads_as_before(self):
        """Only a passage that names an item is read so: a status reference keeps its reading (round 4's
        Routing0CheckedCancelOptionTests: "Procedure cancelled" of "Procedure completed ☐ | Procedure cancelled ☒" is
        held, the code citing the EUS line held, not excluded)."""
        text = (HEAD + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\nIndication: Pancreatic head mass '
                'on CT.\nHistory reviewed.\nConsent obtained.\nASA class II.\nAirway assessed.\nAllergies: none known.\n'
                'Anticoagulants: none.\nNPO since midnight.\nProcedure completed \u2610 | Procedure cancelled \u2612\n')
        self.assertEqual(family_status(text, 'gi.eus'), 'uncertain')
        proposals, _ = real(text, ('43242', 'EUS with fine-needle biopsy of the pancreatic head mass.'))
        self.assertEqual(outcome(proposals['43242']), 'held')

    def test_a_visit_statement_in_such_a_row_is_held(self):
        """The E/M visit statement is read by its own box too (box2:J): in such a row it took the box of the entry
        before it ("Photos ☒ | Established patient office visit ☐" read performed, 99214 ready)."""
        for line in ('Photos \u2612 | Established patient office visit \u2610', 'Photos \u2612 Established patient office visit \u2610'):
            with self.subTest(line=line):
                text = J_OFFICE.format(line=line)
                status, cues = self.read(text, 'Established patient office visit', line)
                self.assertEqual(status, 'uncertain', cues)
                proposals, _ = real(text, ('99214', 'Established patient office visit'))
                self.assertEqual(outcome(proposals['99214']), 'held')



# --- box2:L -- a service-labelled status row with a hold word checked -------------------------------------------------

class Box2LHoldWordLabelTests(unittest.TestCase):
    """box2:L (high, a declared misread at every tree). "Colonoscopy: ☒ Incomplete ☐ Completed" and "Colonoscopy: ☒
    Incomplete" read PERFORMED (the row cited whole, the name, the family: 45378 ready) where "Status: ☒ Incomplete ☐
    Completed" is held; so did a checked "Unknown", "Unclear" or "Requested" in some layouts, and "Colonoscopy status:"
    as the label. A status line's hold words are options beside their own mark (round 4c regression:0) and its label is
    read by its options (box2:I): a checked hold word holds the service the label names, as under "Status:". Never
    performed; a reading that is not performed (the row's own "Incomplete" read incomplete) stays."""

    def read(self, text, phrase, within):
        start = text.index(within) + within.index(phrase)
        return detect.status_for_span(text, start, start + len(phrase), D)

    def test_a_checked_hold_word_holds_the_labelled_service(self):
        for word in ('Incomplete', 'Unknown', 'Unclear', 'Requested', 'Pending', 'On hold', 'TBD', 'TBA'):
            for row in (f'Colonoscopy: \u2612 {word} \u2610 Completed', f'Colonoscopy: \u2612 {word}',
                        f'Colonoscopy status: \u2612 {word} \u2610 Completed', f'Colonoscopy: {word} \u2612 | Completed \u2610',
                        f'Colonoscopy: [x] {word} [ ] Completed'):
                with self.subTest(row=row):
                    text = I_REPORT.format(row=row)
                    whole = self.read(text, row, row)[0]
                    self.assertIn(whole, ('uncertain', 'incomplete'))  # held; an incompleteness read as such stays
                    self.assertIn(self.read(text, 'Colonoscopy', row)[0], ('uncertain', 'incomplete'))
                    self.assertIn(family_status(text), ('uncertain', 'incomplete'))
                    proposals, _ = real(text, ('45378', row))
                    self.assertNotEqual(outcome(proposals['45378']), 'excluded')
                    if whole == 'uncertain':
                        self.assertEqual(outcome(proposals['45378']), 'held')

    def test_the_hold_names_the_option(self):
        text = I_REPORT.format(row='Colonoscopy: \u2612 Incomplete \u2610 Completed')
        status, cues = self.read(text, 'Colonoscopy', 'Colonoscopy: \u2612 Incomplete')
        self.assertEqual(status, 'uncertain')
        self.assertTrue(any("'Incomplete'" in c for c in cues), cues)

    def test_a_visit_statement_as_the_label_is_held(self):
        """The visit statement's reader (box2:J) reads its status line's hold words too: "Established patient office
        visit: ☒ Incomplete ☐ Completed" read performed (99214 ready)."""
        for line in ('Established patient office visit: \u2612 Incomplete \u2610 Completed', 'Established patient office visit: \u2612 Unknown'):
            with self.subTest(line=line):
                text = J_OFFICE.format(line=line)
                status, cues = self.read(text, 'Established patient office visit', line)
                self.assertEqual(status, 'uncertain', cues)
                proposals, _ = real(text, ('99214', 'Established patient office visit'))
                self.assertEqual(outcome(proposals['99214']), 'held')

    def test_unchecked_hold_words_and_status_lines_read_as_before(self):
        for row, status in (('Colonoscopy: \u2610 Incomplete \u2612 Completed', 'performed'),
                            ('Colonoscopy: \u2612 Completed \u2610 Incomplete', 'performed'),
                            ('Colonoscopy: \u2612 Completed \u2610 Unknown', 'performed'),
                            ('Colonoscopy: Incomplete \u2612 | Completed \u2610', 'incomplete')):
            with self.subTest(row=row):
                self.assertEqual(self.read(I_REPORT.format(row=row), 'Colonoscopy', row)[0], status)
        # only a passage in the line's label: an item with a checked hold word beside it reads as before
        row = '\u2611 Cold snare polypectomy \u2612 Pending pathology'
        self.assertEqual(self.read(I_REPORT.format(row=row), 'Cold snare polypectomy', row)[0], 'performed')
        line = 'Status: \u2612 Incomplete \u2610 Completed'
        text = I_REPORT.format(row=line)
        self.assertEqual(self.read(text, line, line)[0], 'uncertain')
        self.assertEqual(family_status(text), 'uncertain')


if __name__ == '__main__':
    unittest.main()
