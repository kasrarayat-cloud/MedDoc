"""DECISIONS D114 (the round-4 review of D108: problems 0, 2 and 4, and parity note 1), SYNTHETIC, built from the
review's own documents (repair4/review-enteroscopy/tools/cases.py: the ileoscopy through the ileostomy, the pouchoscopy
into the pre-pouch ileum, the oral double-balloon enteroscopy in an ileostomy and in a J-pouch patient) and the parity
note's EGD and push enteroscopy with a gastric APC (studio/interpretation/classes.py, coverage.coding_family):
- beside the encounter's verified stoma or pouch, an ileal reach fits the oral class 44376-44379 only when the
  examination's own words verify the oral route, and the stoma or pouch classes 44380-44386 only when they verify the
  route through the stoma or the pouch; a route not verified fits neither - held with the route question, never READY.
  Without a stoma or pouch the classes read as D108 built them;
- an act Gemini files under the enteroscopy whose verified target lies in the upper tract an EGD examines, beside a done
  EGD, is the EGD session's for coding: 44369 is held on it (service.act_elsewhere), 43235 is held base_included beside
  it, and the enteroscopy's diagnostic 44360, which the act held base_included, stays held (the act's procedure
  question). An act whose place is not verified keeps Gemini's family.
At 1caaf0609 each held input below was READY (44360 held base_included); the installed release c2e53f8e holds every
route input (extent, with performed_status on the ileoscopy and pouchoscopy documents) and, on the parity input, holds
44369 (performed_status) and 43235 (base_included) and READYs 43270 and 44360. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio import customer_api
from studio.interpretation import classes, coverage, events, normalize
from tests.test_interpretation_events import asked, check, proposal, run
from tests.test_interpretation_identity import a, accepted, act, sc, tg

EXAMINATION_CLASS = 'facts.examination_class'
ELSEWHERE = 'service.act_elsewhere'
HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
DATED = 'Date of service: November 5, 2026'
SIGNED = 'Endoscopist: Tomas Reyes, MD (fictional)'
ILEOSTOMY = 'The patient has an end ileostomy after a total proctocolectomy for Crohn disease.'
J_POUCH = 'The patient has an ileal J-pouch after a restorative proctocolectomy for ulcerative colitis.'
NO_ANATOMY = 'Indication: Suspected small-bowel Crohn disease.'
STOMA_ENTRY = {'state': 'altered', 'landmark': 'stoma', 'words': 'end ileostomy', 'passages': ['P5']}
POUCH_ENTRY = {'state': 'altered', 'landmark': 'pouch', 'words': 'ileal J-pouch', 'passages': ['P5']}
STOMA, POUCH = frozenset({'stoma'}), frozenset({'pouch'})


def document(lines: dict, *, found, lesions=(), reach=(), anatomy=(), open_questions=()):
    """(the normalized inventory, the text) of a synthetic answer over ``lines`` ({passage id: line}, in order), dated
    in P2 and signed in P3, read by read.read and normalized with the real linked steps."""
    text = '\n'.join(lines.values()) + '\n'
    value = {'passages': [{'id': pid, 'text': line} for pid, line in lines.items()],
             'encounter': {'date_of_service': {'value': '2026-11-05', 'state': 'stated', 'words': 'November 5, 2026',
                                               'passages': ['P2'], 'other_dates': []},
                           'documenting_endoscopist': {'words': 'Tomas Reyes, MD (fictional)', 'passages': ['P3']},
                           'team': [], 'anatomy': list(anatomy), 'reach': list(reach), 'visit_facts': []},
             'lesions': list(lesions), 'events': list(found), 'open_questions': list(open_questions)}
    return normalize.normalize(accepted(value), text), text


def lines_of(title: str, procedure_line: str, body) -> dict:
    lines = {'P0': HEADER, 'P1': title, 'P2': DATED, 'P3': SIGNED, 'P4': procedure_line}
    lines.update({f'P{index}': text for index, text in enumerate(body, start=5)})
    return lines


def examined(lines: dict, procedure_words: str, scope_words: str, landmark: str, reach_words: str, target_words: str,
             *, anatomy=(), status_words: str = 'was advanced', procedure=None, completion=None, status=None,
             open_questions=()):
    """The review's exam_and_biopsy: E1 the examination (P6; its procedure words in P4), E2 a cold-forceps biopsy (P7)
    at ``landmark``, and E1's reach there (P6)."""
    procedure = procedure or a('enteroscopy', procedure_words, ['P4'])
    e1 = act('E1', 'P6', 'examination', scope_words, status_words=status_words, procedure=procedure,
             technique=a('endoscope', scope_words, ['P6']))
    if status is not None:
        e1['status'] = status
    e2 = act('E2', 'P7', 'biopsy', 'Biopsies', status_words='were taken', procedure=a('enteroscopy', procedure_words,
                                                                                         ['P4']),
             technique=a('cold_forceps', 'cold forceps', ['P7']), target=tg('', landmark, target_words, ['P7']))
    reach = {'event': 'E1', 'landmark': landmark, 'words': reach_words, 'passages': ['P6'],
             'completion': completion or a('not_stated')}
    return document(lines, found=[e1, e2], anatomy=anatomy, reach=[reach], open_questions=open_questions)


def ileoscopy(*, procedure_words: str = 'Ileoscopy', status_words: str = 'was advanced', anatomy=(STOMA_ENTRY,)):
    """Problem 0's input (the review's stoma_ileoscopy): an ileoscopy through an end ileostomy into the neo-terminal
    ileum, biopsies there; Gemini's procedure words ``procedure_words`` (in 'Procedure: Ileoscopy through the
    ileostomy.') and the examination's status words ``status_words`` (in its P6)."""
    lines = lines_of('ILEOSCOPY THROUGH STOMA REPORT', 'Procedure: Ileoscopy through the ileostomy.',
                     [ILEOSTOMY,
                      'The enteroscope was advanced through the ileostomy into the neo-terminal ileum for 25 cm.',
                      'Biopsies of the neo-terminal ileum were taken with cold forceps.'])
    return examined(lines, procedure_words, 'enteroscope', 'neo_terminal_ileum', 'neo-terminal ileum',
                    'neo-terminal ileum', anatomy=anatomy, status_words=status_words)


def pouchoscopy(*, procedure_words: str = 'Pouchoscopy', procedure_line: str = 'Procedure: Pouchoscopy.',
                landmark: str = 'ileum', place: str = 'pre-pouch ileum'):
    """Problem 0's pouch input (the review's pouch_prepouch): a J-pouch examined through the anus and the pouch inlet
    into the pre-pouch ileum, biopsies there."""
    lines = lines_of('POUCHOSCOPY REPORT', procedure_line,
                     [J_POUCH,
                      f'The endoscope was advanced through the anus into the J-pouch and through the pouch inlet into '
                      f'the {place} for 15 cm.',
                      f'Biopsies of the {place} were taken with cold forceps.'])
    return examined(lines, procedure_words, 'endoscope', landmark, place, place, anatomy=(POUCH_ENTRY,))


def oral_dbe(*, anatomy_line: str = ILEOSTOMY, anatomy=(STOMA_ENTRY,), status_words: str = 'was advanced',
             procedure_line: str = 'Procedure: Double-balloon enteroscopy.',
             procedure_words: str = 'Double-balloon enteroscopy', exam_line: str = '', place: str = 'proximal ileum',
             landmark: str = 'ileum', reach_words: str = '', completion=None, status=None, extra=(),
             open_questions=()):
    """Problem 4's input (the review's oral_dbe): an oral double-balloon enteroscopy to the proximal ileum in a patient
    with an end ileostomy (or, with J_POUCH and POUCH_ENTRY, an ileal J-pouch), biopsies of an ulcer there."""
    lines = lines_of('DOUBLE-BALLOON ENTEROSCOPY REPORT', procedure_line,
                     [anatomy_line, exam_line or f'The double-balloon enteroscope was advanced orally to the {place}.',
                      f'Biopsies of an ulcer in the {place} were taken with cold forceps.', *extra])
    return examined(lines, procedure_words, 'double-balloon enteroscope', landmark, reach_words or place,
                    f'an ulcer in the {place}', anatomy=anatomy, status_words=status_words, completion=completion,
                    status=status, open_questions=open_questions)


def code_of(inv, text: str, code: str, pid: str = 'P7'):
    return proposal(run(inv, text, [(code, line(text, pid))]), code)


def line(text: str, pid: str) -> str:
    return text.splitlines()[int(pid[1:])]


def held(test, p, exam_class: str, reached: str, words: str, form: str, **wording_options) -> None:
    """``p`` is selected and held on its class alone - the class check's warn and one extent question, in ``form``
    (classes.class_hold's, with D114's ``wording_options``) - never excluded and never READY."""
    reason, question = classes.class_hold(p.code, exam_class, reached, words, form, **wording_options)
    test.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                     ('selected', 'needs_clarification', ['extent'], events.SUPPORTED))
    test.assertEqual((check(p, EXAMINATION_CLASS).status, check(p, EXAMINATION_CLASS).label,
                      check(p, EXAMINATION_CLASS).detail, p.clarifications[0].question, p.clarifications[0].reason),
                     ('warn', classes.CHECK[1], reason, question, reason))


def ready(test, p) -> None:
    test.assertEqual((p.bucket, p.status, asked(p), check(p, EXAMINATION_CLASS), check(p, ELSEWHERE)),
                     ('selected', 'ready', [], None, None))


# --- problems 0, 2 and 4: the route is the examination's own --------------------------------------------------------

class RouteOfTheExamination(SimpleTestCase):
    def test_d114_44377_on_an_ileoscopy_through_the_ileostomy_is_held(self):
        """Problem 0: 44377 ('including ileum', an oral enteroscopy) was READY beside the correct 44382 on the author's
        own READY control. Its words naming no route, it asks the route question; naming the ileostomy, the class
        question, the route named."""
        inv, text = ileoscopy()
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
        p = code_of(inv, text, '44377')
        held(self, p, classes.ILEAL, 'neo terminal ileum', 'neo-terminal ileum', classes.ROUTE_FORM, through=STOMA)
        self.assertEqual(p.clarifications[0].question,
                         'The documented enteroscopy (“neo-terminal ileum”) reached the neo terminal ileum; CPT Studio '
                         'could not confirm from the document whether it was passed through the mouth or through the '
                         'documented stoma. Was a small-bowel enteroscopy past the second portion of the duodenum that '
                         'reaches the ileum performed on the date of service?')
        for words in ({'procedure_words': 'Ileoscopy through the ileostomy'},
                      {'status_words': 'was advanced through the ileostomy'}):
            inv, text = ileoscopy(**words)
            route = classes.examination_route(events.Reading.of(inv).events['E1'])
            with self.subTest(**words):
                self.assertEqual(route[0], classes.THROUGH_STOMA)
                held(self, code_of(inv, text, '44377'), classes.ILEAL, 'neo terminal ileum', 'neo-terminal ileum',
                     classes.CLASS_FORM, route=classes.THROUGH_STOMA, route_words=route[1])
        inv, text = ileoscopy(procedure_words='Ileoscopy through the ileostomy')
        self.assertEqual(code_of(inv, text, '44377').clarifications[0].question,
                         'The documented enteroscopy (“neo-terminal ileum”) reached the neo terminal ileum through a '
                         'stoma (“Ileoscopy through the ileostomy”). Was a small-bowel enteroscopy past the second '
                         'portion of the duodenum that reaches the ileum performed on the date of service?')

    def test_d114_44382_on_the_ileoscopy_is_ready_only_through_its_verified_stoma_route(self):
        """Problem 0's other half: the stoma code is READY when the examination's own words name the ileostomy - in
        its procedure or its status words - and held with the route question when they name no route."""
        for words in ({'procedure_words': 'Ileoscopy through the ileostomy'},
                      {'status_words': 'was advanced through the ileostomy'}):
            inv, text = ileoscopy(**words)
            with self.subTest(**words):
                ready(self, code_of(inv, text, '44382'))
        inv, text = ileoscopy()
        held(self, code_of(inv, text, '44382'), classes.STOMA, 'neo terminal ileum', 'neo-terminal ileum',
             classes.ROUTE_FORM, through=STOMA)

    def test_d114_44377_on_a_pouchoscopy_into_the_pre_pouch_ileum_is_held(self):
        """Problem 0's pouch input. DECISIONS D141 (the round-5 review of D114, problems 0 and 4) changes this pin's
        expectation: 'Pouchoscopy' names the pouch in no route phrase, so it verifies no route - 44377 and 44386 both
        ask the route question, never READY (c2e53f8e holds both, extent and performed_status). Its READY control, the
        route named in a route phrase ('was advanced through the anus into the J-pouch'), is
        tests/test_interpretation_r5c_enteroscopy.py's. With no route in its words ('Endoscopy'), both ask the route
        question too."""
        inv, text = pouchoscopy()
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
        for code, exam_class in (('44377', classes.ILEAL), ('44386', classes.POUCH)):
            with self.subTest(code=code, words='Pouchoscopy'):
                held(self, code_of(inv, text, code), exam_class, 'ileum', 'pre-pouch ileum', classes.ROUTE_FORM,
                     through=POUCH)
        inv, text = pouchoscopy(landmark='neo_terminal_ileum', place='neo-terminal ileum')
        held(self, code_of(inv, text, '44377'), classes.ILEAL, 'neo terminal ileum', 'neo-terminal ileum',
             classes.ROUTE_FORM, through=POUCH)
        inv, text = pouchoscopy(procedure_words='Endoscopy', procedure_line='Procedure: Endoscopy.')
        for code, exam_class in (('44377', classes.ILEAL), ('44386', classes.POUCH)):
            with self.subTest(code=code):
                held(self, code_of(inv, text, code), exam_class, 'ileum', 'pre-pouch ileum', classes.ROUTE_FORM,
                     through=POUCH)

    def test_d114_the_oral_dbe_in_an_ileostomy_patient_holds_44382_and_readies_44377_only_orally(self):
        """Problem 4: an oral double-balloon enteroscopy to the proximal ileum beside an end ileostomy made 44382 READY.
        44382 is held whatever its words say; 44377 is READY only when they verify the oral route."""
        inv, text = oral_dbe()
        for code, exam_class in (('44382', classes.STOMA), ('44377', classes.ILEAL)):
            with self.subTest(code=code, words='no route'):
                held(self, code_of(inv, text, code), exam_class, 'ileum', 'proximal ileum', classes.ROUTE_FORM,
                     through=STOMA)
        inv, text = oral_dbe(status_words='was advanced orally')
        ready(self, code_of(inv, text, '44377'))
        p = code_of(inv, text, '44382')
        held(self, p, classes.STOMA, 'ileum', 'proximal ileum', classes.CLASS_FORM, route=classes.ORAL,
             route_words='was advanced orally')
        self.assertEqual(p.clarifications[0].question,
                         'The documented enteroscopy (“proximal ileum”) reached the ileum through the mouth (“was '
                         'advanced orally”). Was an examination of the ileum through a stoma performed on the date of '
                         'service?')

    def test_d114_the_oral_dbe_in_a_j_pouch_patient_holds_44386_and_readies_44377_only_orally(self):
        """Problem 4's pouch analogue: the same oral examination beside an ileal J-pouch made 44386 READY."""
        options = dict(anatomy_line=J_POUCH, anatomy=(POUCH_ENTRY,))
        inv, text = oral_dbe(**options)
        for code, exam_class in (('44386', classes.POUCH), ('44377', classes.ILEAL)):
            with self.subTest(code=code):
                held(self, code_of(inv, text, code), exam_class, 'ileum', 'proximal ileum', classes.ROUTE_FORM,
                     through=POUCH)
        inv, text = oral_dbe(status_words='was advanced orally', **options)
        ready(self, code_of(inv, text, '44377'))
        held(self, code_of(inv, text, '44386'), classes.POUCH, 'ileum', 'proximal ileum', classes.CLASS_FORM,
             route=classes.ORAL, route_words='was advanced orally')

    def test_d114_the_specs_oral_words_verify_the_oral_route(self):
        """'peroral' and 'antegrade' in the procedure words, 'per os' and 'through the mouth' in the status words."""
        for name, options in (
                ('peroral', dict(procedure_line='Procedure: Peroral double-balloon enteroscopy.',
                                 procedure_words='Peroral double-balloon enteroscopy')),
                ('antegrade', dict(procedure_line='Procedure: Antegrade double-balloon enteroscopy.',
                                   procedure_words='Antegrade double-balloon enteroscopy')),
                ('per os', dict(exam_line='The double-balloon enteroscope was advanced per os to the proximal ileum.',
                                status_words='was advanced per os')),
                ('through the mouth', dict(exam_line='The double-balloon enteroscope was advanced through the mouth to '
                                                     'the proximal ileum.',
                                           status_words='was advanced through the mouth'))):
            inv, text = oral_dbe(**options)
            with self.subTest(words=name):
                self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1'])[0], classes.ORAL)
                ready(self, code_of(inv, text, '44377'))
                self.assertEqual(code_of(inv, text, '44382').status, 'needs_clarification')

    def test_d114_a_route_named_two_ways_is_not_verified(self):
        """A route named in its statement and another named anywhere in its own words is a doubt (D87): 'orally' in the
        status words and the J-pouch named in the reach words ('pre-pouch ileum'), or the ileostomy ('20 cm proximal to
        the ileostomy'). Every class is held with the route question."""
        jpouch = oral_dbe(anatomy_line=J_POUCH, anatomy=(POUCH_ENTRY,), place='pre-pouch ileum',
                          status_words='was advanced orally')
        stoma = oral_dbe(place='distal ileum', status_words='was advanced orally',
                         exam_line='The double-balloon enteroscope was advanced orally to the distal ileum, 20 cm '
                                   'proximal to the ileostomy.',
                         reach_words='distal ileum, 20 cm proximal to the ileostomy')
        for name, (inv, text), other, through, words in (
                ('pre-pouch', jpouch, ('44386', classes.POUCH), POUCH, 'pre-pouch ileum'),
                ('proximal to the ileostomy', stoma, ('44382', classes.STOMA), STOMA,
                 'distal ileum, 20 cm proximal to the ileostomy')):
            self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''), name)
            for code, exam_class in (('44377', classes.ILEAL), other):
                with self.subTest(case=name, code=code):
                    held(self, code_of(inv, text, code), exam_class, 'ileum', words, classes.ROUTE_FORM,
                         through=through)

    def test_d114_reach_words_never_verify_a_route(self):
        """The reach names the point reached, and may name the stoma only as a place: 'distal ileum, 20 cm proximal to
        the ileostomy' with no other route word verifies no stoma route - 44382 is held, never READY."""
        inv, text = oral_dbe(place='distal ileum', reach_words='distal ileum, 20 cm proximal to the ileostomy',
                             exam_line='The double-balloon enteroscope was advanced to the distal ileum, 20 cm '
                                       'proximal to the ileostomy.')
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
        for code, exam_class in (('44382', classes.STOMA), ('44377', classes.ILEAL)):
            with self.subTest(code=code):
                held(self, code_of(inv, text, code), exam_class, 'ileum',
                     'distal ileum, 20 cm proximal to the ileostomy', classes.ROUTE_FORM, through=STOMA)

    def test_d114_words_of_an_unusable_attribute_never_verify_a_route(self):
        """Procedure words Gemini's own open question opens ('Peroral double-balloon enteroscopy', the procedure asked
        about) are located but not usable: their 'peroral' verifies no route, so 44377 is held with the route question,
        never READY."""
        inv, text = oral_dbe(procedure_line='Procedure: Peroral double-balloon enteroscopy.',
                             procedure_words='Peroral double-balloon enteroscopy',
                             open_questions=[{'about': 'procedure', 'events': ['E1'], 'lesions': [],
                                              'passages': ['P4']}])
        examination = events.Reading.of(inv).events['E1']
        self.assertEqual((examination['procedure']['open'], examination['procedure']['words']['text']),
                         (True, 'Peroral double-balloon enteroscopy'))
        self.assertEqual(classes.examination_route(examination), ('', ''))
        held(self, code_of(inv, text, '44377'), classes.ILEAL, 'ileum', 'proximal ileum', classes.ROUTE_FORM,
             through=STOMA)

    def test_d114_an_incomplete_examination_asks_one_route_question_naming_both(self):
        """D43, D56 and D72 keep the ileal class from an examination stated incomplete. With the route not verified as
        well, the one question names both doubts; with the oral route verified, D108's incomplete form."""
        looped = a('incomplete', 'incomplete', ['P8'])
        extra = ('The examination was incomplete because of looping.',)
        inv, text = oral_dbe(completion=looped, extra=extra)
        self.assertTrue(classes.incomplete(events.Reading.of(inv).events['E1']))
        p = code_of(inv, text, '44377')
        held(self, p, classes.ILEAL, 'ileum', 'proximal ileum', classes.ROUTE_FORM, through=STOMA,
             stated_incomplete=True)
        self.assertIn('reached the ileum and is stated to be incomplete; CPT Studio could not confirm',
                      p.clarifications[0].question)
        inv, text = oral_dbe(completion=looped, extra=extra, status_words='was advanced orally')
        held(self, code_of(inv, text, '44377'), classes.ILEAL, 'ileum', 'proximal ileum', classes.INCOMPLETE_FORM)


class ScopeOfTheRoute(SimpleTestCase):
    def test_d114_without_a_stoma_or_pouch_the_oral_classes_read_as_d108_built_them(self):
        """The spec's control: no stoma, no pouch - 44377 is READY on a verified ileal reach, its words naming no route
        or the oral one."""
        for status_words in ('was advanced', 'was advanced orally'):
            inv, text = oral_dbe(anatomy_line=NO_ANATOMY, anatomy=(), status_words=status_words)
            with self.subTest(status_words=status_words):
                self.assertEqual(classes.routes(events.Reading.of(inv).encounter), frozenset())
                ready(self, code_of(inv, text, '44377'))

    def test_d114_a_reach_at_the_pouch_is_the_pouchs_whatever_the_words(self):
        """D114 reads the route for an ileal reach only: a reach at the J-pouch itself, its words naming no route, keeps
        D108's pouch class - 44386 READY."""
        lines = lines_of('POUCHOSCOPY REPORT', 'Procedure: Endoscopy.',
                         [J_POUCH, 'The endoscope was advanced through the anus into the J-pouch.',
                          'Biopsies of the pouch body were taken with cold forceps.'])
        inv, text = examined(lines, 'Endoscopy', 'endoscope', 'pouch', 'J-pouch', 'pouch body', anatomy=(POUCH_ENTRY,))
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
        ready(self, code_of(inv, text, '44386'))

    def test_d114_the_jejunal_class_reads_its_reach_only_beside_a_stoma(self):
        """The spec reads the route for an ileal reach: an oral double-balloon enteroscopy to the mid jejunum beside an
        end ileostomy keeps D108's jejunal class (44361 READY), and 44361 on an ileal reach whose route is not verified
        keeps D108's class question (its reach fits the ileal classes), never R6's extent question."""
        inv, text = oral_dbe(place='mid jejunum', landmark='jejunum')
        ready(self, code_of(inv, text, '44361'))
        inv, text = oral_dbe()
        held(self, code_of(inv, text, '44361'), classes.JEJUNAL, 'ileum', 'proximal ileum', classes.CLASS_FORM)

    def test_d114_the_route_words_are_the_specs_and_no_sentence_names_a_vendor(self):
        for route, words in ((classes.ORAL, ('orally', 'peroral', 'per os', 'through the mouth', 'antegrade')),
                             (classes.THROUGH_STOMA, ('ileostomy', 'stoma')), (classes.THROUGH_POUCH, ('pouch',))):
            with self.subTest(route=route):
                self.assertLessEqual(set(words), set(classes.ROUTE_WORDS[route]))
        self.assertEqual(dict(classes.CLASS_ROUTE), {classes.ILEAL: classes.ORAL, classes.STOMA: classes.THROUGH_STOMA,
                                                     classes.POUCH: classes.THROUGH_POUCH})
        sentences = []
        for exam_class in classes.CLASSES:
            sentences += classes.class_hold('44377', exam_class, 'ileum', 'proximal ileum', classes.ROUTE_FORM,
                                            through=STOMA | POUCH, stated_incomplete=True)
            for route in (classes.ORAL, classes.THROUGH_STOMA, classes.THROUGH_POUCH):
                sentences += classes.class_hold('44382', exam_class, 'ileum', 'proximal ileum', classes.CLASS_FORM,
                                                route=route, route_words='was advanced orally')
        inv, text = egd_push()
        sentences += [code_of(inv, text, '44369').clarifications[0].question,
                      code_of(inv, text, '44369').clarifications[0].reason, classes.ELSEWHERE_CHECK[1]]
        for sentence in sentences:
            with self.subTest(sentence=sentence[:60]):
                self.assertIsNone(customer_api.FORBIDDEN.search(sentence), sentence)
                self.assertNotIn('gemini', sentence.lower())


# --- parity note 1: an act's region decides its session for coding ---------------------------------------------------

EGD_PUSH = {'P0': HEADER, 'P1': 'EGD AND PUSH ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
            'P4': 'Procedure: EGD and push enteroscopy.',
            'P5': 'EGD: The gastroscope was advanced to the second portion of the duodenum.',
            'P6': 'Push enteroscopy: The enteroscope was then advanced to the proximal jejunum.',
            'P7': 'Two gastric antral angioectasias were treated with argon plasma coagulation.'}
GASTRIC = 'Two gastric antral angioectasias'


def egd_push(*, apc_procedure: str = 'enteroscopy', landmark: str = 'gastric_antrum', words: str = GASTRIC,
             apc_line: str = '', egd_status: str = 'performed', egd: bool = True, push_line: str = '',
             push_reach=('jejunum', 'proximal jejunum'), denial: bool = False):
    """The parity note's input: an EGD to the second portion (E1, P5), a push enteroscopy to the proximal jejunum (E2,
    P6) and argon plasma coagulation of ``words`` (E3, P7) at ``landmark``, filed under ``apc_procedure``
    ('enteroscopy': its procedure words 'Push enteroscopy' in P6; 'egd': 'EGD' in P5). ``egd`` False: no EGD at all;
    ``push_line`` and ``push_reach`` (landmark, words): the push enteroscopy's line and reach; ``denial``: E3 is instead
    the statement 'No gastric biopsies were taken.' (P7), filed under the enteroscopy, at the stomach."""
    lines = dict(EGD_PUSH)
    if apc_line:
        lines['P7'] = apc_line
    if push_line:
        lines['P6'] = push_line
    if not egd:
        lines['P5'] = 'Indication: Iron-deficiency anemia.'
    upper, push = a('egd', 'EGD', ['P5']), a('enteroscopy', 'Push enteroscopy', ['P6'])
    found = [act('E2', 'P6', 'examination', 'enteroscope', status_words='was then advanced', procedure=push,
                 technique=a('endoscope', 'enteroscope', ['P6'])),
             act('E3', 'P7', 'ablation', 'argon plasma coagulation', status_words='were treated',
                 procedure=push if apc_procedure == 'enteroscopy' else upper,
                 technique=a('argon_plasma', 'argon plasma coagulation', ['P7']),
                 target=tg('L1', landmark, words, ['P7']))]
    reach = [{'event': 'E2', 'landmark': push_reach[0], 'words': push_reach[1], 'passages': ['P6'],
              'completion': a('not_stated')}]
    if egd:
        found.insert(0, act('E1', 'P5', 'examination', 'gastroscope', status=egd_status, status_words='was advanced',
                            procedure=upper, technique=a('endoscope', 'gastroscope', ['P5'])))
        reach.insert(0, {'event': 'E1', 'landmark': 'second_portion_duodenum',
                         'words': 'second portion of the duodenum', 'passages': ['P5'], 'completion': a('not_stated')})
    group = {'id': 'L1', 'words': words, 'landmark': landmark, 'site_words': '', 'size_words': '',
             'multiplicity': 'group', 'passages': ['P7']}
    if denial:
        lines['P7'] = 'No gastric biopsies were taken.'
        found[-1] = act('E3', 'P7', 'biopsy', 'biopsies', status='not_performed',
                        status_words='No gastric biopsies were taken', procedure=push,
                        scope=sc('all_of_kind', 'No', ['P7']), target=tg('', 'stomach', 'gastric', ['P7']))
        return document(lines, found=found, reach=reach)
    return document(lines, found=found, lesions=[group], reach=reach)


def elsewhere_words(place: str, words: str) -> tuple:
    """(reason, question) of 44369's act_elsewhere hold on the APC of ``words`` at ``place``."""
    return ((f'The ablation (argon plasma) of the {words} is documented at the {place} (“{words}”), which the upper '
             'endoscopy of this encounter examines, so CPT Studio reads it as an act of the upper endoscopy; 44369 '
             'accounts for ablation in a small-bowel enteroscopy, which CPT Studio could not find in the document.'),
            (f'The documented ablation (“{words}”) is at the {place}, which the upper endoscopy of this encounter '
             'examines. Was ablation performed in the small-bowel enteroscopy on the date of service?'))


def elsewhere(test, p, place: str, words: str) -> None:
    """``p`` is held by D114's act_elsewhere alone: the service.act_elsewhere warn and one performed_status question."""
    reason, question = elsewhere_words(place, words)
    test.assertEqual((p.bucket, p.status, asked(p), check(p, ELSEWHERE).status, check(p, ELSEWHERE).label,
                      check(p, ELSEWHERE).detail, p.clarifications[0].question, p.clarifications[0].reason,
                      check(p, EXAMINATION_CLASS)),
                     ('selected', 'needs_clarification', ['performed_status'], 'warn', classes.ELSEWHERE_CHECK[1],
                      reason, question, reason, None))


class RegionOfTheAct(SimpleTestCase):
    def test_d114_the_gastric_apc_filed_under_the_enteroscopy_is_the_egd_sessions(self):
        """The parity note's input, Gemini filing the APC under the push enteroscopy: for coding it is the done
        EGD's."""
        inv, _ = egd_push()
        reading = events.Reading.of(inv)
        self.assertEqual(reading.events['E3']['family'], 'gi.enteroscopy')
        self.assertEqual([coverage.coding_family(reading, reading.events[eid]) for eid in ('E1', 'E2', 'E3')],
                         ['gi.egd', 'gi.enteroscopy', 'gi.egd'])
        found = coverage.sessions(reading)
        self.assertEqual((found['gi.egd'].events, found['gi.enteroscopy'].events), (('E1', 'E3'), ('E2',)))

    def test_d114_44369_is_held_on_the_gastric_apc_and_43235_base_included_beside_it(self):
        """44369 (enteroscopy with ablation) and 43235 were READY; the installed release holds 44369 (performed_status)
        and 43235 (base_included). 43270 stays held: this repair turns nothing READY."""
        inv, text = egd_push()
        elsewhere(self, code_of(inv, text, '44369'), 'gastric antrum', GASTRIC)
        for picks in ((('43235', 'P5'),), (('44369', 'P7'), ('43235', 'P5'))):
            result = run(inv, text, [(code, line(text, pid)) for code, pid in picks])
            with self.subTest(picks=[code for code, _ in picks]):
                p = proposal(result, '43235')
                self.assertEqual((p.status, asked(p), check(p, 'services.base_included').status),
                                 ('needs_clarification', ['base_included'], 'warn'))
                if len(picks) == 2:
                    elsewhere(self, proposal(result, '44369'), 'gastric antrum', GASTRIC)
        self.assertEqual((code_of(inv, text, '43270').status, asked(code_of(inv, text, '43270'))),
                         ('needs_clarification', ['performed_status']))

    def test_d114_the_esophagus_and_the_duodenum_are_the_egds_regions_too(self):
        """The installed release's FAMILY_REGIONS: the EGD's are the esophagus, the stomach and the duodenum; the
        enteroscopy's the small bowel alone."""
        from studio.gi import services  # test-only: the legacy table pinned to (as test_interpretation_mapping)
        self.assertEqual(coverage.EGD_REGIONS, services.FAMILY_REGIONS['gi.egd'])
        self.assertEqual(services.FAMILY_REGIONS['gi.enteroscopy'], frozenset({'small_bowel'}))
        for place, landmark, words in (('distal esophagus', 'distal_esophagus', 'Two distal esophageal angioectasias'),
                                       ('duodenal bulb', 'duodenal_bulb', 'Two duodenal bulb angioectasias')):
            inv, text = egd_push(landmark=landmark, words=words,
                                 apc_line=f'{words} were treated with argon plasma coagulation.')
            with self.subTest(place=place):
                elsewhere(self, code_of(inv, text, '44369'), place, words)

    def test_d114_a_small_bowel_act_stays_the_enteroscopys(self):
        """The control: two jejunal angioectasias treated in the push enteroscopy - 44369 READY, 43235 READY beside
        it."""
        words = 'Two jejunal angioectasias'
        inv, text = egd_push(landmark='jejunum', words=words, apc_line=f'{words} were treated with argon plasma '
                                                                        'coagulation.')
        result = run(inv, text, [('44369', line(text, 'P7')), ('43235', line(text, 'P5'))])
        ready(self, proposal(result, '44369'))
        ready(self, proposal(result, '43235'))

    def test_d114_an_act_whose_place_is_not_verified_keeps_geminis_family(self):
        """Target words that do not stand in their passage leave the place unverified: the act stays the enteroscopy's
        (44369 READY, as before)."""
        inv, text = egd_push(words='Two gastric fundic angioectasias')
        reading = events.Reading.of(inv)
        self.assertNotEqual(reading.events['E3']['target']['state'], 'verified')
        self.assertEqual(coverage.coding_family(reading, reading.events['E3']), 'gi.enteroscopy')
        ready(self, code_of(inv, text, '44369'))

    def test_d114_without_a_done_egd_the_act_keeps_its_family(self):
        """No EGD, or an EGD planned and not done: the gastric act stays the enteroscopy's (44369 READY, as before)."""
        for name, options in (('no EGD', dict(egd=False)), ('planned EGD', dict(egd_status='planned'))):
            inv, text = egd_push(**options)
            reading = events.Reading.of(inv)
            with self.subTest(case=name):
                self.assertEqual(coverage.coding_family(reading, reading.events['E3']), 'gi.enteroscopy')
                ready(self, code_of(inv, text, '44369'))

    def test_d114_a_code_held_by_its_class_and_by_its_acts_region_asks_both_in_one_question(self):
        """D89 (questions are never displaced): the push enteroscopy stopped at the third portion of the duodenum (the
        second portion's landmark, which no class fits) held 44369 with R6's extent question at 1caaf0609; its gastric
        APC is the EGD's as well. The one question asks both - the extent first, then the act's - and the class check
        carries both reasons."""
        inv, text = egd_push(push_line='Push enteroscopy: The enteroscope was then advanced to the third portion of '
                                       'the duodenum.',
                             push_reach=('second_portion_duodenum', 'third portion of the duodenum'))
        p = code_of(inv, text, '44369')
        reason, question = classes.class_hold('44369', classes.JEJUNAL, 'second portion duodenum',
                                              'third portion of the duodenum', classes.EXTENT_FORM)
        region_reason, region_question = elsewhere_words('gastric antrum', GASTRIC)
        self.assertEqual((p.bucket, p.status, asked(p), check(p, EXAMINATION_CLASS).status,
                          check(p, EXAMINATION_CLASS).detail, check(p, ELSEWHERE), p.clarifications[0].question,
                          p.clarifications[0].reason),
                         ('selected', 'needs_clarification', ['extent'], 'warn', f'{reason} {region_reason}', None,
                          f'{question} {region_question}', f'{reason} {region_reason}'))
        self.assertTrue(p.clarifications[0].question.startswith('Small-bowel enteroscopy: confirm the furthest extent '
                                                                'reached. The documented ablation'))

    def test_d114_the_enteroscopys_base_code_stays_held_beside_its_moved_act(self):
        """At 1caaf0609 the gastric APC filed under the enteroscopy held 44360 (its diagnostic code) base_included.
        Moved to the EGD for coding, it would have left 44360 READY (as c2e53f8e READYs it); Gemini's own reading of the
        act as the enteroscopy's stays a doubt, so 44360 is held with the act's procedure question - beside 44369's
        base_included too. A denial at the stomach holds nothing (as at 1caaf0609), and a jejunal act keeps D108's
        base_included alone. DECISIONS D141 (the round-5 review of D114, problem 5) changes the question's expectation:
        the act's question is added beside the base rule's, never in its place - the move took the base rule's only act
        of the enteroscopy, so the one question asks the base rule's question first ('Is 44360 reported separately
        from ablation for this examination?', as at 1caaf0609), then the act's."""
        inv, text = egd_push()
        reason = ('The ablation (argon plasma) of the Two gastric antral angioectasias is filed under the small-bowel '
                  'enteroscopy and documented at the gastric antrum (“Two gastric antral angioectasias”), which the '
                  'upper endoscopy of this encounter examines, so CPT Studio reads it as an act of the upper '
                  'endoscopy; if it was done in the enteroscopy, 44360 is included in the code for it.')
        question = ('Is 44360 reported separately from ablation for this examination? In which procedure was the '
                    'ablation (“Two gastric antral angioectasias”) done?')
        for picks, facts in (((('44360', 'P6'),), ['procedure']), ((('44360', 'P6'), ('43235', 'P5')), ['procedure']),
                             ((('44360', 'P6'), ('44369', 'P7')), ['base_included', 'procedure'])):
            p = proposal(run(inv, text, [(code, line(text, pid)) for code, pid in picks]), '44360')
            with self.subTest(picks=[code for code, _ in picks]):
                self.assertEqual((p.status, asked(p), check(p, ELSEWHERE).status, check(p, ELSEWHERE).detail,
                                  p.clarifications[-1].question, p.clarifications[-1].reason),
                                 ('needs_clarification', facts, 'warn', reason, question, reason))
        inv, text = egd_push(denial=True)
        reading = events.Reading.of(inv)
        self.assertEqual((reading.events['E3']['status']['value'], reading.events['E3']['status']['state'],
                          reading.events['E3']['target']['state']), ('not_performed', 'verified', 'verified'))
        self.assertEqual(coverage.coding_family(reading, reading.events['E3']), 'gi.egd')
        ready(self, code_of(inv, text, '44360', 'P6'))
        words = 'Two jejunal angioectasias'
        inv, text = egd_push(landmark='jejunum', words=words, apc_line=f'{words} were treated with argon plasma '
                                                                        'coagulation.')
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((p.status, asked(p), check(p, ELSEWHERE)), ('needs_clarification', ['base_included'], None))

    def test_d114_an_examination_and_an_egds_own_act_never_move(self):
        """Only an act Gemini files under the enteroscopy moves: an examination (the session itself) keeps its family
        whatever its target, and the APC filed under the EGD stays the EGD's (43270 READY, as before)."""
        inv, text = egd_push(apc_procedure='egd')
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.coding_family(reading, reading.events['E3']), 'gi.egd')
        ready(self, code_of(inv, text, '43270'))
        examination = dict(reading.events['E2'], target=dict(reading.events['E3']['target']))
        self.assertEqual(coverage.coding_family(reading, examination), 'gi.enteroscopy')
