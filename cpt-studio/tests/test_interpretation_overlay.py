"""The new path's read-time overlay (Gemini migration slice S11; design/FINAL.md 8.1), as design v2 rewires it
(docs/gemini-migration/FINAL-V2.md 6.2 and 6.5; step 5c of its 8.1): the overlay reads event_coding@2 only, so the
cpt-studio-events@1 record this module's scenario builds - a v1 row - is UNREADABLE and read as stored. Read time over
v2 records is tests/v2/test_overlay.py's.

- The verbatim copies: each function FINAL 8.1 copies and design v2 keeps is pinned by its AST to its original in
  studio/validation/review_view.py, modulo the declared seam names only (a drift is caught where it is made); its
  constants equal the originals; the copies of checks.py's constants equal theirs.
- A v1 record (event_coding@1) is refused by the versioned reader like every other shape it does not read, and fails
  closed: every stored check and question kept, nothing released, the moved holds marked stale; readiness blocks
  (review.UNREADABLE_EVENTS_BLOCKER, pinned equal to the overlay's), a v1 row whatever its coding.
- The seams that read stored structure still read it on a row read as stored: the reinstatement waits from
  support['reinstatement_waits'] (a missing or unreadable record asks for the documentation: held, never ready), the
  summary from support['summary']; nothing is offered that only the frozen inventory could give (no modifier review, no
  session of a v1 coding).
- What it imports: no legacy reader's module but review_view's three dataclasses, and checks.py only by FINAL 7.1's names.
- S11 runs under the sentinel's strict mode with the RETIRED kind armed (strict(retired=True): FINAL-V2 5.7 measure 1;
  DECISIONS D249, step 6a's request R8), so a retired module's execution at read time fails it like a legacy one.
- DECISIONS D243: the 19 class-B subtests of five retired-module suites (test_interpretation_r3_integration_d87,
  r5c_egd, r5c_currency, r5_egd, r5d_currency) read a cpt-studio-events@1 record through the overlay, which FINAL-V2 6.5
  retires; step q02 removes them. RetiredSuiteRecordTests builds each suite's kind of @1 record and asserts 6.5's
  refusal: event_coding@1 is unreadable, a v1 row is read as stored and blocked, its coverage is never re-run.
Pure, DB-free; synthetic data only.
"""
import ast
import copy
import inspect
import textwrap
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio import review
from studio.interpretation import overlay, sentinel, wording
from studio.validation import checks, questions, review_view

# FINAL 8.1's verbatim copies (and the helpers they need), each with the seams its copy may differ by: a legacy dotted
# name -> the copy's name. Nothing else may differ.
COPIES = {
    'stored_from': {},
    '_decided': {},
    'proposal_answers': {},
    'answered_by_engine': {'engine.answered_away': 'questions.answered_away',
                           'engine.ANSWERED_SUPPORT': 'questions.ANSWERED_SUPPORT'},
    'counts': {},
    'decidable': {},
    '_find': {},
    '_question': {},
    '_reinstatement_clear': {},
    '_sources': {},
    '_passage_sources': {},
    '_example_passage': {'checks.CLAIMS_EXAMPLE_PASSAGE': 'CLAIMS_EXAMPLE_PASSAGE',
                         'checks.CLAIMS_EXAMPLE_TOPIC': 'CLAIMS_EXAMPLE_TOPIC'},
    '_held_blocker': {'checks._join': 'wording.join', 'reconcile.service_label': '_session_label'},
}
# design v2 (step 5c): _open_facts, _unavailable_by, _gated and _same_day_question are no longer copied (the member
# answers bind to the item the code presents, and the same-day hold is the combination's, recomputed over the counted
# set); _pfs_rows reads the field's prefix by a slice (FINAL-V2 5.7 measure 4), proved equal by output in
# tests/v2/test_overlay.py.
CONSTANTS = ('APPROVE', 'REJECT', 'REINSTATE', 'REVOKE', 'CONFIRM', 'SELECTED', 'EXCLUDED', 'ALTERNATIVE', 'READY',
             'NEEDS_CLARIFICATION', 'STATUS_EXCLUDED', 'BASE_CHECK', 'BASE_FACT', 'ENDOSCOPIC_CHECK',
             'REINSTATEMENT_CHECK', 'PRESENCE_CHECK', 'DATE_CHECK', 'SAME_DAY_EM_GATE', 'SAME_DAY_PROCEDURE',
             'SEPARATE_EM_FACT', 'DETAIL_UNAVAILABLE', 'UNAVAILABLE_ANSWERS', 'ANSWER_WORDS',
             'MODIFIER_REVIEW', 'COMPETING_FACT', 'DATE_WAIT', 'DOCUMENTATION_FACT', 'DOCUMENTATION_QUESTION')
CHECKS_CONSTANTS = ('CLAIMS_EXAMPLE_CODES', 'CLAIMS_EXAMPLE_PASSAGE', 'CLAIMS_EXAMPLE_TOPIC',
                    'DISTINCT_LESION_NOT_CHECKED')


class _Seams(ast.NodeTransformer):
    """Rewrite each declared legacy dotted name to the copy's name, so only the declared seams may differ."""

    def __init__(self, seams):
        self.seams = {tuple(old.split('.')): new for old, new in seams.items()}
        self.used = set()

    def visit_Attribute(self, node):
        parts = []
        value = node
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            dotted = tuple([value.id] + list(reversed(parts)))
            if dotted in self.seams:
                self.used.add(dotted)
                return ast.parse(self.seams[dotted], mode='eval').body
        return self.generic_visit(node)


def tree_of(fn) -> ast.AST:
    return ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0]


def dumped(node) -> str:
    return ast.dump(node, include_attributes=False)


class VerbatimCopyTests(SimpleTestCase):
    def test_each_copy_is_its_original_modulo_its_declared_seams(self):
        for name, seams in COPIES.items():
            with self.subTest(name=name):
                original, copied = getattr(review_view, name), getattr(overlay, name)
                self.assertIsNot(original, copied)  # a copy, never the legacy function itself
                rewrite = _Seams(seams)
                legacy = rewrite.visit(tree_of(original))
                self.assertEqual(rewrite.used, {tuple(old.split('.')) for old in seams}, 'every seam declared is used')
                self.assertEqual(dumped(legacy), dumped(tree_of(copied)))

    def test_the_pin_sees_a_drift(self):
        # the comparison is live: a changed comparison in a copy fails it
        legacy = tree_of(review_view.counts)
        drifted = copy.deepcopy(tree_of(overlay.counts))
        for node in ast.walk(drifted):
            if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.NotEq):
                node.ops[0] = ast.Eq()
                break
        self.assertNotEqual(dumped(legacy), dumped(drifted))

    def test_the_constants_equal_their_originals(self):
        for name in CONSTANTS:
            with self.subTest(name=name):
                self.assertEqual(getattr(overlay, name), getattr(review_view, name))
        for name in CHECKS_CONSTANTS:
            with self.subTest(name=name):
                self.assertEqual(getattr(overlay, name), getattr(checks, name))
        self.assertEqual(overlay.UNREADABLE_BLOCKER, review.UNREADABLE_EVENTS_BLOCKER)
        self.assertEqual(wording.join(['a', 'b', 'c']), checks._join(['a', 'b', 'c']))
        self.assertEqual((overlay.Stored, overlay.Decided, overlay.View),
                         (review_view.Stored, review_view.Decided, review_view.View))
        self.assertIs(overlay.service_answers, review_view.service_answers)  # R-2's one implementation

    def test_it_imports_no_legacy_reader_but_review_views_dataclasses_and_names_checks_by_final_7_1_only(self):
        source = inspect.getsource(overlay)
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported += [(node.module, alias.name) for alias in node.names]
            elif isinstance(node, ast.Import):
                imported += [(alias.name, '') for alias in node.names]
        legacy = [(module, name) for module, name in imported
                  if module and (module.startswith('studio.gi') and module != 'studio.gi.profiles'
                                 or module in ('studio.candidates', 'studio.validation.engine',
                                               'studio.validation.reconcile', 'studio.validation.rationale'))]
        self.assertEqual(legacy, [])
        self.assertEqual(sorted(name for module, name in imported if module == 'studio.validation.review_view'),
                         ['Decided', 'Stored', 'View'])
        names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
                 and isinstance(node.value, ast.Name) and node.value.id == 'checks'}
        self.assertLessEqual(names, set(sentinel.CHECKS_ALLOWLIST))

    def test_the_overlay_runs_no_denied_code(self):
        rows, completeness = scenario()
        with sentinel.strict('S11 the overlay', retired=True) as opened:
            overlay.review_view(rows, {'k-snare': 'reject', 'k-exc': 'reinstate'}, completeness=completeness)
            overlay.review_view(rows, {}, completeness={}, answers=[{'code': '45380', 'family': COLON,
                                                                     'fact': 'performed_status',
                                                                     'value': 'cannot_confirm'}])
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)


# --- a synthetic new-path assessment as the overlay reads it --------------------------------------------------------------

COLON = 'gi.colonoscopy'
BASE_Q = 'Is 45378 reported separately from 45385, 45380 for this examination?'


def row(key, code, *, bucket='selected', status='ready', checks_=(), questions_=(), support=None, holds=(),
        reinstatable=False):
    return overlay.Stored(key=key, code=code, family=COLON, bucket=bucket, status=status, reinstatable=reinstatable,
                          checks=tuple(checks_), holds=tuple(holds), questions=tuple(questions_),
                          support=support or {}, evidence=())


def base_check(included):
    """The v1 engine's base_included check and its question (its v1 wording, written out: the record a v1 row
    stores)."""
    reason = (f'The documented colonoscopy has interventions that {", ".join(included)} account for; its diagnostic '
              'examination is normally included in them (internal profile rule; NCCI procedure-to-procedure edits are '
              'not connected). Held for the reviewer, not excluded.')
    spec = SimpleNamespace(scope='proposal', fact='base_included', family=COLON, reason=reason,
                           question=f'Is 45378 reported separately from {", ".join(included)} for this examination?')
    return {'id': overlay.BASE_CHECK, 'label': 'Diagnostic examination beside its interventions', 'status': 'warn',
            'detail': reason, 'source': 'cpt-studio:test'}, spec


def scenario(*, coding_version=None, acts=True):
    """A v1 row (event_coding@1, as the cpt-studio-events@1 engine stored it): a colonoscopy session with a snare
    removal of L1 and a biopsy of L2 (verified distinct), the base code 45378 held beside 45385 and 45380 (stored),
    45385 matched to the snare, 45380 to the biopsy, and an excluded reinstatable 45390 whose gate waits for the
    extent. ``acts``: False leaves the session's acts out of its reportable events."""
    check, spec = base_check(('45385', '45380'))
    waits = [{'fact': 'extent', 'question': 'Colonoscopy: confirm the furthest extent reached.'}]
    reinstatement = {'id': 'review.reinstatement', 'label': 'Approval after reinstatement', 'status': 'warn',
                     'detail': 'Approval waits for: Colonoscopy: confirm the furthest extent reached.', 'source': ''}
    rows = [
        row('k-base', '45378', status='needs_clarification', checks_=[check], holds=['base_included'],
            questions_=[{'id': 'q1', 'scope': 'proposal', 'family': COLON, 'fact': 'base_included',
                         'question': spec.question, 'reason': spec.reason}],
            support={'summary': 'The colonoscopy documents the examination.'}),
        row('k-snare', '45385', support={'acts': [{'id': 'E2', 'kind': 'snare', 'label': 'snare removal',
                                                   'status': 'performed'}], 'summary': 'The colonoscopy documents a snare.'}),
        row('k-biopsy', '45380', support={'acts': [{'id': 'E3', 'kind': 'biopsy', 'label': 'forceps biopsy',
                                                    'status': 'performed'}]}),
        row('k-exc', '45390', bucket='excluded', status='excluded', reinstatable=True, checks_=[reinstatement],
            support={'reinstatement_waits': waits}),
    ]
    entries = [{'event': 'E2', 'kind': 'snare', 'label': 'snare removal', 'lesion': 'L1',
                'describe': 'snare removal of the 6 mm polyp'},
               {'event': 'E3', 'kind': 'biopsy', 'label': 'forceps biopsy', 'lesion': 'L2',
                'describe': 'forceps biopsy of the 3 mm polyp'}]
    coding = {'version': coding_version or 'cpt-studio-events@1',
              'sessions': {COLON: {'family': COLON, 'event': 'E1', 'part_of': '', 'label': 'colonoscopy',
                                   'kind': 'colonoscopy', 'unresolved': False, 'done': True, 'incomplete': False,
                                   'examinations': ['E1'], 'reportable': entries if acts else [], 'doubted': []}},
              'codes': {'k-base': {'session': COLON, 'events': ['E1'], 'lesions': []},
                        'k-snare': {'session': COLON, 'events': ['E2'], 'lesions': ['L1']},
                        'k-biopsy': {'session': COLON, 'events': ['E3'], 'lesions': ['L2']},
                        'k-exc': {'session': COLON, 'events': [], 'lesions': []}},
              'lesions': {'L1': {'words': None, 'landmark': 'sigmoid_colon', 'multiplicity': 'single',
                                 'distinct_from': ['L2'], 'label': '6 mm polyp in the sigmoid colon'},
                          'L2': {'words': None, 'landmark': 'ascending_colon', 'multiplicity': 'single',
                                 'distinct_from': ['L1'], 'label': '3 mm polyp in the ascending colon'}}}
    return rows, {'event_coding': coding}


class ReaderTests(SimpleTestCase):
    def test_a_v1_record_is_refused_with_every_shape_the_reader_does_not_read(self):
        rows, completeness = scenario()
        broken = {
            'the v1 record itself (event_coding@1)': completeness,
            'no record': {},
            'not a mapping': {'event_coding': ['sessions']},
            'another version': scenario(coding_version='cpt-studio-events@9')[1],
            'no lesions': {'event_coding': {**completeness['event_coding'], 'lesions': None}},
        }
        for label, value in broken.items():
            with self.subTest(label):
                with self.assertRaises(overlay.UnreadableCoding):
                    overlay.read_coding(value)
                self.assertIsNone(overlay.coding_of(value))

    def test_a_v1_record_fails_closed_and_releases_nothing(self):
        rows, completeness = scenario(acts=False)
        competing = {'id': overlay.COMPETING_CHECK, 'label': 'Codes proposed for the same documented act',
                     'status': 'warn', 'detail': 'held', 'source': ''}
        rows[1] = overlay.Stored(**{**rows[1].__dict__, 'checks': (competing,), 'holds': ('competing_codes',),
                                    'status': 'needs_clarification', 'support': {**rows[1].support,
                                                                                 'competes': ['45380']},
                                    'questions': ({'id': 'q2', 'scope': 'proposal', 'family': COLON,
                                                   'fact': 'competing_codes', 'question': 'which?',
                                                   'reason': 'held'},)})
        decisions = {'k-snare': 'reject', 'k-biopsy': 'reject'}
        for label, value in (('v1', completeness), ('absent', {}),
                             ('another version', scenario(coding_version='x@9')[1])):
            with self.subTest(label):
                views = overlay.review_view(rows, decisions, completeness=value)
                base = views['k-base']
                self.assertEqual((base.status, base.released, base.stale),
                                 ('needs_clarification', (), (overlay.BASE_CHECK,)))
                self.assertEqual([c['id'] for c in base.checks], [overlay.BASE_CHECK])  # kept as stored
                self.assertEqual([q['question'] for q in base.questions], [BASE_Q])
                still = overlay.review_view(rows, {'k-biopsy': 'reject'}, completeness=value)['k-snare']
                self.assertEqual((still.status, still.released, still.stale),
                                 ('needs_clarification', (), (overlay.COMPETING_CHECK,)))
                # with no decision every view is its stored row
                for p in rows:
                    view = overlay.review_view(rows, {}, completeness=value)[p.key]
                    self.assertEqual((view.status, view.checks, view.stale), (p.status, p.checks, ()))

    def test_readiness_blocks_a_v1_row_whatever_its_record(self):
        from studio.interpretation import readers
        for completeness in ({'event_coding': None}, scenario()[1]):
            row = SimpleNamespace(engine_version='cpt-studio-events@1', completeness=completeness)
            with self.subTest(completeness=bool(completeness['event_coding'])):
                self.assertTrue(readers.for_assessment(row).unreadable(row))


class SeamTests(SimpleTestCase):
    def views(self, decisions=None, answers=(), rows=None, completeness=None):
        stored, coding = scenario()
        return overlay.review_view(rows if rows is not None else stored, decisions or {},
                                   completeness=completeness if completeness is not None else coding, answers=answers)

    def test_a_reinstated_code_asks_its_structured_waits_and_never_parses_prose(self):
        reinstated = self.views({'k-exc': 'reinstate'})['k-exc']
        self.assertEqual((reinstated.status, reinstated.withheld_by, [q['fact'] for q in reinstated.questions]),
                         ('needs_clarification', 'review.reinstatement', ['extent']))
        stored, coding = scenario()
        # the check's prose names the extent, but nothing structured is recorded: the documentation is asked (held)
        stored[3] = overlay.Stored(**{**stored[3].__dict__, 'support': {}})
        bare = self.views({'k-exc': 'reinstate'}, rows=stored)['k-exc']
        self.assertEqual([q['fact'] for q in bare.questions], [overlay.DOCUMENTATION_FACT])
        stored[3] = overlay.Stored(**{**stored[3].__dict__, 'support': {'reinstatement_waits': 'extent'}})
        self.assertEqual([q['fact'] for q in self.views({'k-exc': 'reinstate'}, rows=stored)['k-exc'].questions],
                         [overlay.DOCUMENTATION_FACT])
        # the date of service's wait is the encounter's own question: not asked again, and no documentation either
        stored[3] = overlay.Stored(**{**stored[3].__dict__, 'support': {'reinstatement_waits': [
            {'fact': 'service_date', 'question': overlay.DATE_WAIT}]}})
        dated = self.views({'k-exc': 'reinstate'}, rows=stored)['k-exc']
        self.assertEqual((dated.questions, dated.status), ((), 'needs_clarification'))
        # a passing gate waits for nothing
        passing = dict(stored[3].checks[0], status='pass')
        stored[3] = overlay.Stored(**{**stored[3].__dict__, 'checks': (passing,)})
        clear = self.views({'k-exc': 'reinstate'}, rows=stored)['k-exc']
        self.assertEqual((clear.questions, clear.reinstatement_clear), ((), True))

    def test_the_summary_is_the_stored_sentence(self):
        views = self.views()
        self.assertEqual((views['k-snare'].summary, views['k-biopsy'].summary),
                         ('The colonoscopy documents a snare.', ''))

    def test_nothing_only_the_frozen_inventory_gives_is_offered_on_a_v1_row(self):
        views = self.views()
        self.assertIsNone(views['k-snare'].modifier_review)  # no FactSet, no modifier review
        stored, completeness = scenario()
        self.assertIsNone(overlay._service(stored[3], overlay.coding_of(completeness), overlay.Decided('reinstate')))

    def test_an_answer_the_engine_read_is_read_through_the_one_marker(self):
        stored, completeness = scenario()
        marker = {questions.ANSWERED_SUPPORT: {'fact': 'extent', 'value': 'cannot_confirm', 'answers': ['a1']}}
        stored[2] = overlay.Stored(**{**stored[2].__dict__, 'bucket': 'excluded', 'status': 'excluded',
                                      'support': {**stored[2].support, **marker}})
        views = overlay.review_view(stored, {}, completeness=completeness)
        self.assertEqual((views['k-biopsy'].reason, views['k-biopsy'].answer, views['k-biopsy'].answered),
                         ('detail_unavailable', 'cannot_confirm', 'extent'))
        self.assertTrue(views['k-biopsy'].active)  # it still counts where its presence held another code


# --- DECISIONS D243: the class-B subtests' kind of cpt-studio-events@1 record, refused at read time (FINAL-V2 6.5) ----

V1 = 'cpt-studio-events@1'
EGD = 'gi.egd'
OFFICE = 'gi.office_em'
EUS = 'gi.eus'


def v1_entry(event, kind, label, lesion=None, describe=''):
    """An entry of an event_coding@1 session as the cpt-studio-events@1 engine stored it (its kind's label and the
    document's description in words)."""
    return {'event': event, 'kind': kind, 'label': label, 'lesion': lesion, 'describe': describe or label}


def v1_session(family, kind, label, *, examinations=('E1',), possible=(), unresolved=False, done=True, reportable=(),
               doubted=()):
    """An event_coding@1 session (studio/interpretation/coverage.event_coding, v1's): keyed by its family slug, with its
    label in words and v1's flags and entries."""
    return {'family': family, 'event': examinations[0] if examinations else None, 'part_of': '', 'label': label,
            'possibly_part_of': '', 'kind': kind, 'unresolved': unresolved, 'done': done, 'incomplete': False,
            'examinations': list(examinations), 'possible': list(possible), 'reportable': list(reportable),
            'doubted': list(doubted)}


def v1_completeness(sessions, codes, *, unresolved_items=(), not_listed=(), reasons=()):
    """A cpt-studio-events@1 assessment's completeness (studio/interpretation/assess.py, v1's): v1's coverage sentences
    with no structured counts, its unresolved items and not-listed services labelled in words, its covered map, and
    event_coding@1."""
    reasons = list(reasons)
    covered = {}
    for key, code in codes.items():
        covered.setdefault(code['session'], []).append(code['code'])
    return {'state': 'incomplete' if reasons else 'complete_pending_review', 'reasons': reasons, 'services': 1,
            'unresolved': len(unresolved_items), 'conflicts': 0,
            'statement': ('Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.') if reasons else
            'Every documented service has a proposal to review.',
            'unresolved_items': list(unresolved_items), 'bundled': [], 'not_listed': list(not_listed),
            'covered': covered, 'included_by': {}, 'inventory_problems': [],
            'event_coding': {'version': V1, 'sessions': sessions,
                             'codes': {key: {'session': code['session'], 'events': code['events'], 'lesions': []}
                                       for key, code in codes.items()},
                             'lesions': {}}}


def v1_row(key, code, family, *, status='ready', questions_=(), support=None):
    """A stored proposal of a cpt-studio-events@1 assessment: v1's support, never event_reading@2's record."""
    return overlay.Stored(key=key, code=code, family=family, bucket='selected', status=status, reinstatable=False,
                          checks=(), holds=tuple(q['fact'] for q in questions_), questions=tuple(questions_),
                          support=support or {'acts': []}, evidence=())


def v1_assessment(completeness):
    """A test instance's v1 row as read time meets it (FINAL-V2 6.2: the V1 branch)."""
    return SimpleNamespace(engine_version=V1, completeness=completeness, event_inventory_id=None, pk=None)


class RetiredSuiteRecordTests(SimpleTestCase):
    """DECISIONS D243's 5c half: one case per class-B suite, each the same kind of cpt-studio-events@1 record that suite
    read through the overlay, each asserting FINAL-V2 6.5's refusal - read time reads event_coding@2 only."""

    def assert_refused(self, completeness, R, rows=()):
        """6.5: the coding is UNREADABLE; read time re-runs no coverage from the record (UnreadableCoding before
        anything is read, whatever FactSet is at hand), counts no stored v1 proposal (UnreadableRecord), and the V1
        branch blocks the row and says its coverage was not re-run."""
        from studio.interpretation import readers

        with self.assertRaises(overlay.UnreadableCoding):
            overlay.read_coding(completeness)
        self.assertIsNone(overlay.coding_of(completeness))
        for name, call in (('reviewed_completeness', lambda: overlay.reviewed_completeness(completeness, R, [], ())),
                           ('assessment_counts', lambda: overlay.assessment_counts(completeness, R, list(rows))),
                           ('reviewed_coverage', lambda: overlay.reviewed_coverage(
                               completeness, R, [], (), {'open_questions': 0, 'unverified': 0, 'provider_ok': True,
                                                         'conflicts': 0}))):
            with self.subTest(refused=name), self.assertRaises(overlay.UnreadableCoding):
                call()
        for row in rows:
            with self.subTest(record=row.code), self.assertRaises(overlay.UnreadableRecord):
                overlay.counted_codes([row], set(), R)
        assessment = v1_assessment(completeness)
        reader = readers.for_assessment(assessment)
        self.assertEqual(reader.branch(assessment), readers.V1)
        self.assertTrue(reader.unreadable(assessment))
        self.assertIsNone(reader.reading(assessment))
        reviewed = reader.reviewed_completeness(assessment, completeness, list(rows), [])
        self.assertEqual(reviewed['reasons'][-1], overlay.UNREADABLE_COVERAGE_REASON)

    def test_d87_an_eus_session_listing_a_possible_examination(self):
        """test_interpretation_r3_integration_d87.D87PossibleExaminationIsNoFactSource (12 subtests): the stored
        event_coding@1 lists the EUS session's possible examination E2 apart from its done examination E1, and the
        suite read it with overlay.read_coding. 6.5: unreadable, whatever its sessions say."""
        from tests.v2 import test_assess as TA

        drainage = v1_entry('E3', 'drainage', 'drainage', describe='EUS-guided drainage')
        completeness = v1_completeness(
            {EUS: v1_session(EUS, 'eus', 'endoscopic ultrasound', possible=('E2',), unresolved=True,
                             reportable=(drainage,))},
            {'k-43240': {'session': EUS, 'events': ['E3'], 'code': '43240'}},
            reasons=('1 open question',))
        coding = completeness['event_coding']['sessions'][EUS]
        self.assertEqual((coding['examinations'], coding['possible'], coding['unresolved']), (['E1'], ['E2'], True))
        self.assert_refused(completeness, TA.dated(TA.two_sessions().build()),
                            rows=[v1_row('k-43240', '43240', EUS, status='needs_clarification')])

    def test_r5_egd_d118_two_dilations_of_one_stricture_after_a_rejection(self):
        """test_interpretation_r5_egd.D118DilationsOfOneStricture.test_d118_the_competing_hold_is_released_once_the_
        other_code_is_rejected: two dilations of one stricture, 43249 and 43248 held competing; the suite rejected 43248
        and read 43249 READY, its competing hold released, from the v1 rows. 6.5: the v1 row is read AS STORED - nothing
        released, the moved hold marked stale - and blocked."""
        from tests.v2 import test_assess as TA

        question = {'id': 'q1', 'scope': 'proposal', 'family': EGD, 'fact': overlay.COMPETING_FACT,
                    'question': '43249 and 43248 are proposed for the same documented act.', 'reason': 'held'}
        rows = [v1_row('k-43249', '43249', EGD, status='needs_clarification', questions_=(question,),
                       support={'acts': [{'id': 'E2', 'kind': 'dilation'}], 'competes': ['43248']}),
                v1_row('k-43248', '43248', EGD, status='needs_clarification',
                       questions_=({**question, 'id': 'q2'},),
                       support={'acts': [{'id': 'E3', 'kind': 'dilation'}], 'competes': ['43249']})]
        dilations = (v1_entry('E2', 'dilation', 'dilation', describe='balloon dilation of the stricture'),
                     v1_entry('E3', 'dilation', 'dilation', describe='Savary dilation of the stricture'))
        completeness = v1_completeness(
            {EGD: v1_session(EGD, 'egd', 'upper endoscopy', reportable=dilations)},
            {'k-43249': {'session': EGD, 'events': ['E2'], 'code': '43249'},
             'k-43248': {'session': EGD, 'events': ['E3'], 'code': '43248'}}, reasons=('2 open questions',))
        R = TA.dated(TA.one_dilation().build())
        view = overlay.review_view(rows, {'k-43248': 'reject'}, completeness=completeness, facts=R)['k-43249']
        self.assertEqual((view.status, view.released, view.recomputed, view.stale),
                         ('needs_clarification', (), (), (overlay.COMPETING_CHECK,)))
        self.assertEqual(view.questions, rows[0].questions)
        self.assert_refused(completeness, R, rows=rows)

    def test_r5c_currency_d134_a_visit_beside_a_possible_procedure(self):
        """test_interpretation_r5c_currency.D134VisitItemBesideAPossibleProcedure.test_d134_the_read_time_overlay_keeps_
        the_assessments_reading (2 subtests): an office visit beside a digital rectal examination (listed: no proposal)
        and beside a banding done in the office (set apart: not listed); the suite re-read each coverage with
        overlay.reviewed_completeness. 6.5: refused before anything is read."""
        from tests.v2 import test_assess as TA

        R = TA.dated(TA.office_and_sigmoidoscopy().build())
        dre = v1_completeness(
            {OFFICE: v1_session(OFFICE, 'office_em', 'office / outpatient visit')}, {},
            unresolved_items=({'service': OFFICE, 'family': OFFICE, 'act': None, 'reason': 'no_proposal',
                               'label': 'office / outpatient visit', 'second_review': True},),
            reasons=('1 documented service or act without a supported proposal',))
        banding = v1_completeness(
            {OFFICE: v1_session(OFFICE, 'office_em', 'office / outpatient visit',
                                reportable=(v1_entry('E1', 'band_ligation', 'band ligation'),))}, {},
            not_listed=({'service': OFFICE, 'family': OFFICE,
                         'label': 'office / outpatient visit beside a procedure done or possibly done the same day'},),
            reasons=('1 documented service without a supported proposal and not listed as unresolved: office / '
                     'outpatient visit beside a procedure done or possibly done the same day',))
        for name, completeness in (('the DRE', dre), ('the done banding', banding)):
            with self.subTest(name):
                self.assert_refused(completeness, R)

    def test_r5c_egd_d142_a_stent_listed_not_covered(self):
        """test_interpretation_r5c_egd.D142ListedNotCovered (3 subtests): an EUS (or an EGD beside 43239) whose stent no
        code accounts for, listed not_covered; the suite re-read the items at read time with overlay.counted_codes over
        the v1 rows and overlay.reviewed_completeness. 6.5: the v1 proposal is no record read time counts
        (UnreadableRecord) and the coverage is refused (UnreadableCoding)."""
        from tests.v2 import test_assess as TA

        stent = v1_entry('E2', 'stent', 'stent placement', describe='a 20 mm lumen-apposing metal stent was deployed')
        completeness = v1_completeness(
            {EUS: v1_session(EUS, 'eus', 'endoscopic ultrasound', reportable=(stent,))},
            {'k-43259': {'session': EUS, 'events': ['E1'], 'code': '43259'}},
            unresolved_items=({'service': EUS, 'family': EUS, 'act': 'stent', 'reason': 'not_covered',
                               'label': 'stent placement', 'second_review': True},),
            reasons=('1 documented service or act without a supported proposal',))
        rows = [v1_row('k-43259', '43259', EUS, support={'acts': [{'id': 'E1', 'kind': 'eus_exam'}]})]
        self.assertEqual([(item['act'], item['reason'], item['second_review'])
                          for item in completeness['unresolved_items']], [('stent', 'not_covered', True)])
        self.assert_refused(completeness, TA.dated(TA.two_sessions().build()), rows=rows)

    def test_r5d_currency_d144_a_visit_beside_an_act_done_but_for_its_procedure(self):
        """test_interpretation_r5d_currency.D144VisitBesideAnActDoneButForItsProcedure.test_d144_the_other_readers_of_
        labels_and_possible_are_unchanged: an office visit beside a banding whose time is unknown, listed no_proposal;
        the suite re-read it with overlay.reviewed_completeness. 6.5: refused before anything is read."""
        from tests.v2 import test_assess as TA

        completeness = v1_completeness(
            {OFFICE: v1_session(OFFICE, 'office_em', 'office / outpatient visit',
                                doubted=(v1_entry('E1', 'band_ligation', 'band ligation'),))}, {},
            unresolved_items=({'service': OFFICE, 'family': OFFICE, 'act': None, 'reason': 'no_proposal',
                               'label': 'office / outpatient visit', 'second_review': True},),
            reasons=('1 documented service or act without a supported proposal',))
        self.assert_refused(completeness, TA.dated(TA.office_and_sigmoidoscopy().build()))
