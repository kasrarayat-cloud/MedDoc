"""Harness repair 3 (owner directive 2026-11-05, second message; HARNESS.md "Harness repair 3"): the readings and the
admission rule the owner's 39f0ac49 traced to, and the five admission cases the directive names. Real engine and
readers, no provider or database calls. The documents are synthetic, and the 39f0ac49 one is a paraphrase of its
structure (inline service labels, an impacted meat bolus removed by retrieval net), never the owner's upload.

Refutation cycle 2 (HARNESS.md "Harness repair 3, refutation cycle 2") dropped F-SECTIONS T and L under the two-cycle
rule, and cycle 4 dropped F-ACTS: the titles with an aside, the labelled paragraphs and "the bolus was removed" read as
the base reads them, pinned below as recorded residuals - so 39f0ac49's 43247 has no documented act and is listed. The
admission cases therefore read a plain report (PLAIN) and its documented biopsy, and the labelled one shows the
provider-neutral hold: a participant's code for an act stated done in a doubted service is held as Corti's code is.

Completion repair (2026-11-06, U2): the labelled paragraphs are read as today's procedures by studio.gi.structure, so
the labelled report's codes are READY for Corti and a participant alike (InlineServiceLabelTests' moved pins); the
bolus stays the base's (no foreign-body act for "the bolus was removed")."""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import detect, sections, structure
from studio.gi import services as gi_services
from studio.validation import engine, review_view
from tests.test_harness_engine import DAY, code, corti, decision, not_coded, proposal, read, run, span

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Gastroenterology Procedure Report\n'
        'Date of service: 2026-10-14\n'
        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
INDICATION = ('Indications: Food impaction after a meal the evening before, intermittent dysphagia, and surveillance '
              'after prior adenomas.\n'
              'Risks and benefits of upper endoscopy with possible foreign-body removal and colonoscopy with possible '
              'intervention were discussed.\n')
NET = 'A retrieval net was passed through the working channel and the bolus was removed through the mouth.'
EGD_BIOPSY = 'Cold forceps biopsies were obtained from the mid esophagus.'
UPPER = ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus. A large impacted '
         'meat bolus was found at 34 cm.\n' + NET + '\n' + EGD_BIOPSY + '\n'
         'The stomach and the second portion of the duodenum were then examined and were normal.\n')
SNARE = 'A 9 mm sessile polyp in the transverse colon was removed with a cold snare.'
LOWER = ('Colonoscopy: A colonoscope was introduced through the anus and advanced to the cecum.\n' + SNARE + '\n')
TAIL = 'Impression: Food impaction cleared; esophageal biopsies; transverse colon polyp removed.\nPlan: Await pathology.\n'
LABELLED = HEAD + INDICATION + UPPER + LOWER + TAIL
# the same narrative with no inline labels, under a procedure list and a description heading: both services done today
PLAIN = (HEAD + 'Indications: Food impaction after a meal the evening before, and surveillance after prior adenomas.\n'
         'Procedures performed: Upper endoscopy with foreign-body removal and biopsy; colonoscopy with cold snare '
         'polypectomy.\nDescription of procedure:\n' + UPPER.replace('Upper endoscopy: ', '')
         + LOWER.replace('Colonoscopy: ', '') + TAIL)


def families(text, day=DAY):
    return {f.family: f.status for f in detect.route(text, day).findings if f.family in ('gi.egd', 'gi.colonoscopy')}


def inventory(text, day=DAY):
    return gi_services.build(text, service_date=day, routing=detect.route(text, day))


def acts(text, family):
    svc = next(s for s in inventory(text).services if s.family == family)
    return [(a.kind, a.status) for a in svc.acts]


class TitleAsideTests(SimpleTestCase):
    """F-SECTIONS T, dropped under the two-cycle rule (L3-1, L5-1 to L5-4, then C2-1-4 to C2-1-7): a procedure report's
    title with an aside after it reads as the base reads it - an ordinary line, so the service it names is held
    (uncertain), never READY. A recorded residual (a false hold); the plain title is the procedure's own."""

    def title_kind(self, title):
        text = f'{title}\nDate of service: 2026-10-14\nProcedure\nThe colonoscope was advanced to the cecum.\n'
        return sections.layout(text).sections[0].kind if sections.layout(text).sections[0].start == 0 else None

    def test_an_aside_title_reads_as_the_base_reads_it(self):
        # The layout is the base's for every title (the frozen request side). Completion repair (2026-11-06, builder R2,
        # U4): the colonoscope's own course under the "Procedure" heading is now a mention of today's colonoscopy
        # (detect._instrument_mentions), so under a title whose only addition is an aside about the document itself
        # ("(fictional)", "(Final)") the colonoscopy reads performed - moved from uncertain. The counter-cases stay as
        # the base reads them: a colonoscope's course under an upper endoscopy's title is no colonoscopy of a report that
        # names another family (I6), and "(amended)" or "(corrected)" is outside the closed class of asides (I7).
        for title, family, status in (('Colonoscopy Report (fictional)', 'gi.colonoscopy', 'performed'),
                                      ('Colonoscopy Report (Final)', 'gi.colonoscopy', 'performed'),
                                      ('Upper Endoscopy Report (amended)', 'gi.egd', 'uncertain'),
                                      ('EGD Procedure Note (corrected)', 'gi.egd', 'uncertain')):
            text = f'{title}\nDate of service: 2026-10-14\nProcedure\nThe colonoscope was advanced to the cecum.\n'
            with self.subTest(title):
                self.assertEqual(sections.layout(text).sections[0].kind, 'other')
                self.assertEqual(families(text), {family: status})
        self.assertEqual(self.title_kind('Colonoscopy Report'), 'procedure')

    def test_an_aside_of_another_time_a_plan_a_doubt_or_a_denial_is_no_title(self):
        for title in ('Colonoscopy Report (planned)', 'Colonoscopy Report (prior)', 'Colonoscopy Report (cancelled)',
                      'Colonoscopy Report (not performed)', 'Colonoscopy Report (2019)', 'Colonoscopy Report (draft)',
                      'Colonoscopy Report (outside)', 'Colonoscopy Report (scheduled)', 'Colonoscopy Report (pre-op)'):
            with self.subTest(title):
                self.assertNotEqual(self.title_kind(title), 'procedure')

    def test_the_walks_word_reports_read_as_the_base_reads_them(self):
        # Was a recorded residual (the Word walk's titles with an aside routed their procedure as the base does: h2b
        # historical, h2c uncertain). Completion repair (2026-11-06, builder R2, U4): each report's instrument course
        # under its "Procedure" heading ("The colonoscope was advanced to the cecum ...", "The gastroscope was passed to
        # the second portion of the duodenum.") is today's procedure, so both read performed. The layout itself is
        # unchanged (the title still opens no section).
        from tests.test_participants_support import FIXTURES
        for name, day, family, status in (('h2b', date(2026, 10, 29), 'gi.colonoscopy', 'performed'),
                                          ('h2c', date(2026, 10, 28), 'gi.egd', 'performed')):
            text = (FIXTURES / 'fable-walk' / f'{name}.context.txt').read_text(encoding='utf-8')
            with self.subTest(name):
                self.assertEqual(families(text, day)[family], status)


class InlineServiceLabelTests(SimpleTestCase):
    """F-SECTIONS L, dropped under the two-cycle rule (L5-1 to L5-3, then C2-3-1 to C2-3-8), changed sections.py
    itself. The completion repair (2026-11-06, U2) reads the same shape without touching the layout:
    studio.gi.structure releases a labelled procedure paragraph only on the structural conditions P1-P4 and N1-N3, and
    the clinical readers read the derived layout (tests/test_completion_structure.py pins each condition).

    MOVED PINS (completion repair, U2; these were the residual pins of the dropped rule): 39f0ac49's shape - a
    "Gastroenterology Procedure Report" whose "Upper endoscopy:" and "Colonoscopy:" paragraphs narrate each scope's own
    course after an Indications line with content of its own - now reads both services performed, each paragraph a
    report part of its family, and its codes READY for Corti and for a participant alike (the provider-neutral
    admission: one evaluation, whoever proposed the code). sections.layout itself is unchanged: the frozen layout still
    opens no procedure section there. Every counter-case pin below is kept, and now also asserts that nothing is
    released."""

    def test_the_labelled_parts_read_as_todays_procedures(self):
        # moved (U2): was {'gi.egd': 'uncertain', 'gi.colonoscopy': 'uncertain'} and no report part, as the base read it
        self.assertEqual(families(LABELLED), {'gi.egd': 'performed', 'gi.colonoscopy': 'performed'})
        kinds = [(s.kind, s.label) for s in sections.layout(LABELLED).sections]
        self.assertNotIn(('procedure', 'upper endoscopy'), kinds)  # the frozen layout is unchanged
        self.assertNotIn(('procedure', 'colonoscopy'), kinds)
        derived = [(s.kind, s.label) for s in structure.clinical_layout(LABELLED).sections]
        self.assertIn(('procedure', 'upper endoscopy'), derived)
        self.assertIn(('procedure', 'colonoscopy'), derived)
        self.assertEqual([part.family for part in gi_services.parts(LABELLED, service_date=DAY) if part.kind == 'report'],
                         ['gi.egd', 'gi.colonoscopy'])

    def test_a_participants_code_reads_as_cortis_code_for_the_same_act(self):
        # moved (U2): the biopsy is stated done inside today's EGD, so Corti's 43239 is READY, and a participant's 43239
        # for the same passage reads exactly as Corti's (was: both held, the service's doubt)
        codes = corti(('45385', span(LABELLED, SNARE)))
        by_corti = proposal(run(LABELLED, codes + corti(('43239', span(LABELLED, EGD_BIOPSY)))), '43239')
        self.assertEqual((by_corti.bucket, by_corti.status), ('selected', 'ready'))
        for name in ('astra', 'fable'):
            with self.subTest(name):
                item = proposal(run(LABELLED, codes, [read(name, [code(LABELLED, '43239', EGD_BIOPSY)])]), '43239')
                self.assertEqual((item.bucket, item.status, item.support['origin'], item.support['proposed_by']),
                                 ('selected', 'ready', 'participant', [name]))

    def test_39f0ac49s_bolus_removal_is_the_egds_foreign_body_act(self):
        # MOVED PIN (completion repair 2026-11-06, integration of builders R1 and A). Was: F-ACTS refuted in cycles 3
        # and 4 and dropped, so "the bolus was removed" named no foreign-body act, Corti's 43247 was held by the
        # service's doubt and a participant's was listed. Now the bolus resolves to its documented antecedent ("A large
        # impacted meat bolus was found at 34 cm") and is the structural subject of its removal (U1, builder A), inside
        # the report's own labelled "Upper endoscopy:" part (U2, builder R1): one foreign-body act today, so Corti's
        # 43247 is READY and a participant's 43247 for the same passage reads exactly as Corti's
        codes = corti(('43239', span(LABELLED, EGD_BIOPSY)), ('45385', span(LABELLED, SNARE)))
        by_corti = proposal(run(LABELLED, codes + corti(('43247', span(LABELLED, NET)))), '43247')
        self.assertEqual((by_corti.bucket, by_corti.status), ('selected', 'ready'))
        for name in ('astra', 'fable'):
            with self.subTest(name):
                item = proposal(run(LABELLED, codes, [read(name, [code(LABELLED, '43247', NET)])]), '43247')
                self.assertEqual((item.bucket, item.status, item.support['origin'], item.support['proposed_by']),
                                 ('selected', 'ready', 'participant', [name]))
                self.assertEqual(decision(item), decision(by_corti))  # builder Q1: one evaluation, whoever proposed

    def test_without_its_reading_the_installed_reader_held_both(self):
        flat = LABELLED.replace('Upper endoscopy: ', '').replace('Colonoscopy: ', '')
        self.assertEqual(families(flat), {'gi.egd': 'uncertain', 'gi.colonoscopy': 'uncertain'})

    def test_a_history_a_date_no_course_no_report_or_a_run_on_line_opens_nothing(self):
        cases = {
            'under a history heading': HEAD + 'Prior procedures:\nColonoscopy: The colonoscope was advanced to the cecum '
                                              'and two adenomas were removed.\n',
            'a dated account': HEAD + INDICATION + 'Colonoscopy: In 2019 the colonoscope was advanced to the cecum and two '
                                                   'adenomas were removed.\n',
            'no course': HEAD + INDICATION + 'Colonoscopy: two adenomas were removed.\n',
            'not a procedure report': 'Office visit note\nDate of service: 2026-10-14\n' + INDICATION
                                      + 'Colonoscopy: The colonoscope was advanced to the cecum.\n',
            'a run-on line': HEAD + 'Indications: Surveillance after an outside\nColonoscopy: The colonoscope was '
                                    'advanced to the cecum.\n',
            'another occurrence above': HEAD + 'Outside records\nColonoscopy: The colonoscope was advanced to the cecum.\n',
            'a plan': HEAD + 'Plan:\nColonoscopy: The colonoscope will be advanced to the cecum next month.\n',
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assertNotIn(('procedure', 'colonoscopy'), [(s.kind, s.label) for s in sections.layout(text).sections])
                # the completion repair's release opens nothing here either (U2: each counter-case keeps the base)
                self.assertEqual(structure.released(text), ())
                self.assertNotIn(('procedure', 'colonoscopy'),
                                 [(s.kind, s.label) for s in structure.clinical_layout(text).sections])


class ForeignBodyActTests(SimpleTestCase):
    """F-ACTS (a bolus named by its food, or "the bolus", read as the foreign-body act where its clause states it
    removed) was refuted in refutation cycles 3 and 4 and dropped under the two-cycle rule. The completion repair
    (2026-11-06, U1, builder A) changed the approach rather than the requirement: a definite bolus phrase resolves to
    its documented antecedent, and a removal is the bolus's only when the bolus is the removal predicate's structural
    subject or object (services._removal_subject, _bolus_index). The F-ACTS refuters below stay non-removals."""

    def test_the_bolus_the_net_removed_is_the_foreign_body_act(self):
        # MOVED PIN (integration of builders R1 and A): was assertNotIn - the base read no act there
        self.assertIn(('foreign_body', 'performed'), acts(LABELLED, 'gi.egd'))

    def test_a_medication_bolus_a_finding_or_a_push_is_no_removal(self):
        egd = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nUpper endoscopy report\n'
               'Date of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nProcedure\n'
               'The gastroscope was passed to the second portion of the duodenum.\n')
        for sentence in ('A 50 mg bolus of propofol was given.', 'A saline bolus was injected to lift the lesion.',
                         'An impacted meat bolus was found at 34 cm.', 'The food bolus was pushed into the stomach.',
                         'No food impaction was seen.'):
            with self.subTest(sentence):
                self.assertNotIn(('foreign_body', 'performed'), acts(egd + sentence + '\n', 'gi.egd'))


class AdmissionCaseTests(SimpleTestCase):
    """The directive's item 3, case by case: an explicit, source-supported proposal reaches review whoever proposed it
    and whatever Corti did with the code; an unsupported one stays out with an accurate reason; a number only listed is
    never promoted."""

    def test_only_astra_or_only_fable_proposes_the_supported_service(self):
        codes = corti(('45385', span(PLAIN, SNARE)))
        for name in ('astra', 'fable'):
            with self.subTest(name):
                item = proposal(run(PLAIN, codes, [read(name, [code(PLAIN, '43239', EGD_BIOPSY)])]), '43239')
                self.assertEqual((item.bucket, item.status, item.support['origin'], item.support['proposed_by']),
                                 ('selected', 'ready', 'participant', [name]))

    def test_corti_disagrees_and_the_document_supports_the_independent_proposal(self):
        # Corti's 45384 (hot forceps) for the cold-snare removal: the document supports Astra's 45385, which reaches
        # review ready; Corti's code is read by its own rules (its act is not documented), and nothing is chosen for it
        codes = corti(('43239', span(PLAIN, EGD_BIOPSY)), ('45384', span(PLAIN, SNARE)))
        result = run(PLAIN, codes, [read('astra', [code(PLAIN, '45385', SNARE)])])
        snare = proposal(result, '45385')
        self.assertEqual((snare.bucket, snare.status, snare.support['origin']), ('selected', 'ready', 'participant'))
        self.assertNotEqual(proposal(result, '45384').status, 'ready')

    def test_models_agree_on_an_unsupported_denied_or_historical_service(self):
        colon = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report\n'
                 'Date of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nProcedure\n'
                 'The colonoscope was advanced to the cecum.\n')
        biopsy = 'Cold forceps biopsies of the cecum were obtained.'
        for line in ('Hot snare polypectomy of the 8 mm descending colon polyp failed.', 'No polyps were removed.',
                     'The 12 mm sigmoid polyp will be removed with a snare at a later date.',
                     'At the last colonoscopy a 9 mm polyp was removed with a hot snare.'):
            text = colon + biopsy + '\n' + line + '\n'
            with self.subTest(line):
                result = run(text, corti(('45380', span(text, biopsy))),
                             [read('astra', [code(text, '45385', line)]), read('fable', [code(text, '45385', line)])])
                found = [p for p in result.proposals if p.code == '45385']
                # moved by the completion repair (builder Q1, equal eligibility): never READY, and read exactly as
                # Corti's own selection of the passage - excluded with the passage that states the act failed, denied
                # or planned (reinstatable), held for the earlier colonoscopy's - never an alternative
                self.assertEqual(len(found), 1)
                self.assertNotEqual(found[0].status, 'ready')
                self.assertIn((found[0].bucket, found[0].status),
                              (('excluded', 'excluded'), ('selected', 'needs_clarification')))
                by_corti = proposal(run(text, corti(('45380', span(text, biopsy)), ('45385', span(text, line)))),
                                    '45385')
                self.assertEqual((found[0].bucket, found[0].status, found[0].exclusion_reason),
                                 (by_corti.bucket, by_corti.status, by_corti.exclusion_reason))

    def test_a_number_only_in_an_alternative_list_is_never_promoted(self):
        codes = corti(('45385', span(PLAIN, SNARE))) + [engine.ProviderCode('candidate', 'cpt', '43239', '', ())]
        result = run(PLAIN, codes, [read('astra', advised=[not_coded(PLAIN, '43239', EGD_BIOPSY)]),
                                    read('fable', [code(PLAIN, '45385', SNARE)])])
        self.assertFalse([p for p in result.proposals if p.code == '43239' and p.bucket == 'selected'])
        self.assertIn(('S1', 'gi.egd', '', 'no_proposal'),
                      [(u['service'], u['family'], u['act'], u['reason'])
                       for u in result.completeness['unresolved_items']])


class CompetitionReviewTests(SimpleTestCase):
    """P-ADMIT2's competition through the review overlay: both codes for one act are held while both are counted; a
    reviewer's rejection of one releases the other, and a member's answer never does."""
    EGD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nUpper endoscopy report\n'
           'Date of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nProcedure\n'
           'The gastroscope was passed to the second portion of the duodenum.\n')
    DILATION = ('A through-the-scope balloon was positioned across the Schatzki ring and inflated to 18 mm under direct '
                'visualization.')

    def setUp(self):
        self.text = self.EGD + self.DILATION + '\n'
        self.result = run(self.text, corti(('43248', span(self.text, self.DILATION))),
                          [read('astra', [code(self.text, '43249', self.DILATION)])])
        self.rows = [review_view.stored_from(p) for p in self.result.proposals]
        self.keys = {p.code: p.key for p in self.result.proposals if p.bucket == 'selected'}

    def views(self, decisions=None, answers=()):
        return review_view.review_view(self.rows, decisions or {}, services=self.result.services,
                                       reference_sources=self.result.reference_sources, answers=answers)

    def test_both_are_held_until_one_is_rejected_then_the_other_is_ready(self):
        views = self.views()
        self.assertEqual({views[k].status for k in self.keys.values()}, {'needs_clarification'})
        after = self.views({self.keys['43248']: 'reject'})
        kept = after[self.keys['43249']]
        self.assertEqual((kept.status, kept.released), ('ready', (engine.COMPETING_FACT,)))
        self.assertFalse(any(c.get('id') == engine.COMPETING_CHECK for c in kept.checks))
        other = self.views({self.keys['43249']: 'reject'})[self.keys['43248']]
        self.assertEqual(other.status, 'ready')  # the same rule for Corti's code: neither is preferred

    def test_a_member_answer_never_lifts_the_hold_on_the_other_code(self):
        answers = [{'code': '43248', 'family': 'gi.egd', 'fact': engine.COMPETING_FACT, 'value': 'not_documented'}]
        views = self.views(answers=answers)
        self.assertEqual(views[self.keys['43249']].status, 'needs_clarification')


class TimePlaceConditionTests(SimpleTestCase):
    """F-TIME (HARNESS.md, "Harness repair 3"): negation, time, place, source and condition bound to the act. Each form
    below read as an act done today, READY on Corti's selection and on a participant's first reading, before the
    repair; each is now held or excluded on both paths. Every class keeps a control that stays READY."""

    def never_ready(self, lines, which, head=None):
        from tests.test_h2_refutation_r1 import COLON as HEAD_COLON, READY as OK, both
        for line in lines:
            with self.subTest(line):
                by_corti, by_astra = both((head or HEAD_COLON) + line + '\n', which, line)
                self.assertNotIn(OK, by_corti)
                self.assertNotIn(OK, by_astra)

    def ready(self, line, which, head=None):
        from tests.test_h2_refutation_r1 import COLON as HEAD_COLON, READY as OK, both
        self.assertEqual(both((head or HEAD_COLON) + line + '\n', which, line), ([OK], [OK]), line)

    def test_n_a_fragments_own_negation(self):
        self.never_ready(('Ink never injected into the ascending colon.',
                          'Saline not yet injected into the ascending colon.'), '45381')
        self.never_ready(('Biopsies never obtained from the ascending colon.',
                          'Biopsies not yet obtained from the ascending colon.'), '45380')
        self.ready('Biopsies obtained from the ascending colon.', '45380')

    def test_b_before_this_procedure_and_other_days(self):
        self.never_ready(('Prior to this procedure, a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'Before this procedure, a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'Before referral, a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'Last wk. a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'Yesterday a 6 mm polyp in the ascending colon was removed with a cold snare.'), '45385')
        # a predicate of its own after the reference: a clause of today's procedure
        self.ready('Before this examination was completed, a 6 mm polyp in the ascending colon was removed with a cold '
                   'snare.', '45385')

    def test_c_a_condition_or_an_open_question(self):
        self.never_ready(('If a 6 mm polyp in the ascending colon was removed with a cold snare, surgery would follow.',
                          'It is unknown whether the 6 mm polyp in the ascending colon was removed with a cold snare.'),
                         '45385')
        self.ready('Biopsies were obtained from the ascending colon to determine whether this represents colitis.',
                   '45380')

    def test_p_another_facility_provider_or_source(self):
        self.never_ready(('At the referring facility, a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'A 6 mm polyp in the ascending colon was removed with a cold snare at the referring facility.',
                          'Per outside report, a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'A 6 mm polyp in the ascending colon was removed with a cold snare (outside report).',
                          'Elsewhere, a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'Per Dr. Smith a 6 mm polyp in the ascending colon was removed with a cold snare.',
                          'A 6 mm polyp in the ascending colon was removed with a cold snare by Dr. Synthetic Surgeon.'),
                         '45385')
        # the report's own physician named as the agent, by the surname its physician line gives
        own = HEAD.replace('Gastroenterology Procedure Report', 'Colonoscopy report') + 'Procedure: Colonoscopy\n' \
            'The colonoscope was advanced to the cecum and the examination was completed.\n'
        self.ready('A 6 mm polyp in the ascending colon was removed with a cold snare by Dr. Synthetic Endoscopist.',
                   '45385', head=own)

    def test_i_an_infinitive_states_nothing_done(self):
        self.never_ready(('Tattoo ink is to be injected into the transverse colon submucosa.',
                          'Tattoo ink has yet to be injected into the transverse colon submucosa.',
                          'Tattoo ink needs to get injected into the transverse colon submucosa.'), '45381')
        # a finite done predicate beside an infinitive of another verb (main holds "... to be sent to pathology" by
        # routing's own plan cue, before and after this repair)
        self.ready('Biopsies were taken from the ascending colon to rule out colitis.', '45380')

    def test_f_a_later_clause_says_the_same_act_failed(self):
        self.never_ready(('A 6 mm polyp in the ascending colon was removed with a cold snare, but the polypectomy was '
                          'unsuccessful.',), '45385')
        self.never_ready(('The lesion in the ascending colon was tattooed and not resected; the tattoo did not take.',),
                         '45381')
        self.ready('A 6 mm polyp in the ascending colon was removed with a cold snare, and the polypectomy site was '
                   'inspected.', '45385')

    def test_a_fronted_frame_is_read_with_its_clause(self):
        self.never_ready(('Previously, the lesion in the ascending colon was tattooed.',
                          'Per outside report, the lesion in the ascending colon was tattooed.'), '45381')
        self.ready('In the ascending colon, the lesion was tattooed.', '45381')


class AttachedReportTitleTests(SimpleTestCase):
    """F-SECTIONS T (the battery's R8 D10), dropped under the two-cycle rule: an attached prior report under a history
    heading reads as the base reads it. With an aside its title is an ordinary line and this report's date stands, so
    45378 is READY; with a plain title its date of service competes with this report's, so the date is in conflict and
    nothing is READY (a recorded residual, a false hold; L5-4's variants with no competing date are the base's own false
    READYs, recorded in HARNESS.md)."""

    def body(self, title):
        return (f'\nAttached prior report:\n{title}\nDate of service: 2025-03-01\nProcedure: EGD\n'
                'The gastroscope was advanced to the second portion of the duodenum. The duodenum was normal.')

    def test_an_attached_prior_reports_title_reads_as_the_base_reads_it(self):
        from studio.gi import context as gi_context
        from tests.test_h2_refutation_r1 import COLON as HEAD_COLON, CECUM, READY as OK, both
        aside = HEAD_COLON + self.body('Upper endoscopy report (fictional)') + '\n'
        self.assertEqual(both(aside, '45378', CECUM), ([OK], [OK]))
        plain = HEAD_COLON + self.body('Upper endoscopy report') + '\n'
        self.assertEqual(gi_context.extract_context(plain)['service_date'].origin, 'conflict')
