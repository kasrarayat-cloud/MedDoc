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


if __name__ == '__main__':
    unittest.main()
