"""The new path's read-time overlay (Gemini migration slice S11; design/FINAL.md 8.1): a near-verbatim port of
review_view.review_view's orchestration with named seams, read over the event coding the events engine stores.

- The verbatim copies: each function FINAL 8.1 copies is pinned by its AST to its original in studio/validation/
  review_view.py, modulo the declared seam names only (a drift is caught where it is made); its constants equal the
  originals; the copies of checks.py's constants equal theirs.
- The versioned reader of completeness['event_coding'] refuses an unknown version or shape, and an unreadable record
  fails closed: every stored check kept, the base and the competing checks never released and marked stale once the
  counted set moved, and readiness blocks (review.UNREADABLE_EVENTS_BLOCKER, pinned equal to the overlay's).
- The seams read stored structure, never prose: the reinstatement waits from support['reinstatement_waits'] (a missing or
  unreadable record asks for the documentation: held, never ready), the summary from support['summary'], the session of a
  code and of a reinstated code's family, the separate-lesion modifier review only on lesions verified DISTINCT and only
  from events the coding records (fail-closed), with the legacy review's shape and its claims-manual citation.
- What it imports: no legacy reader's module but review_view's three dataclasses, and checks.py only by FINAL 7.1's names.
Pure, DB-free; synthetic data only.
"""
import ast
import copy
import inspect
import textwrap
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio import review
from studio.interpretation import combination, overlay, sentinel, wording
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
    '_open_facts': {},
    '_unavailable_by': {},
    '_gated': {},
    '_same_day_question': {'checks.SEPARATE_EM_QUESTION': 'SEPARATE_EM_QUESTION', 'checks._join': 'wording.join'},
    '_pfs_rows': {},
    '_sources': {},
    '_passage_sources': {},
    '_example_passage': {'checks.CLAIMS_EXAMPLE_PASSAGE': 'CLAIMS_EXAMPLE_PASSAGE',
                         'checks.CLAIMS_EXAMPLE_TOPIC': 'CLAIMS_EXAMPLE_TOPIC'},
    '_held_blocker': {'checks._join': 'wording.join', 'reconcile.service_label': '_session_label'},
}
CONSTANTS = ('APPROVE', 'REJECT', 'REINSTATE', 'REVOKE', 'CONFIRM', 'SELECTED', 'EXCLUDED', 'ALTERNATIVE', 'READY',
             'NEEDS_CLARIFICATION', 'STATUS_EXCLUDED', 'BASE_CHECK', 'BASE_FACT', 'ENDOSCOPIC_CHECK',
             'REINSTATEMENT_CHECK', 'PRESENCE_CHECK', 'DATE_CHECK', 'SAME_DAY_EM_GATE', 'SAME_DAY_PROCEDURE',
             'SEPARATE_EM_FACT', 'DETAIL_UNAVAILABLE', 'UNAVAILABLE_ANSWERS', 'ANSWER_WORDS', '_AFTER_BASE',
             'MODIFIER_REVIEW', 'COMPETING_CHECK', 'COMPETING_FACT', 'DATE_WAIT', 'DOCUMENTATION_FACT',
             'DOCUMENTATION_QUESTION')
CHECKS_CONSTANTS = ('SEPARATE_EM_QUESTION', 'CLAIMS_EXAMPLE_CODES', 'CLAIMS_EXAMPLE_PASSAGE', 'CLAIMS_EXAMPLE_TOPIC')


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
        with sentinel.strict('S11 the overlay') as opened:
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
    check, spec = combination.base_hold('45378', COLON, 'k-base', included, 'colonoscopy')
    return {'id': check.id, 'label': check.label, 'status': check.status, 'detail': check.detail,
            'source': check.source}, spec


def scenario(*, coding_version=None, acts=True):
    """A colonoscopy session (S) with a snare removal of L1 and a biopsy of L2 (verified distinct), the base code 45378
    held beside 45385 and 45380 (stored), 45385 matched to the snare, 45380 to the biopsy, and an excluded reinstatable
    45390 whose gate waits for the extent. ``acts``: False leaves the session's acts out of its reportable events, so only
    the other codes hold the base."""
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
    coding = {'version': coding_version or overlay.CODING_VERSION,
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
    def test_the_event_coding_is_read_only_at_its_version_and_shape(self):
        rows, completeness = scenario()
        self.assertIs(overlay.read_coding(completeness), completeness['event_coding'])
        broken = {
            'no record': {},
            'not a mapping': {'event_coding': ['sessions']},
            'another version': scenario(coding_version='cpt-studio-events@2')[1],
            'no lesions': {'event_coding': {**completeness['event_coding'], 'lesions': None}},
            'a session without its label': {'event_coding': {**completeness['event_coding'], 'sessions': {
                COLON: {**completeness['event_coding']['sessions'][COLON], 'label': None}}}},
            'a code without its events': {'event_coding': {**completeness['event_coding'], 'codes': {
                'k-base': {'session': COLON, 'lesions': []}}}},
            'a lesion without its distinctness': {'event_coding': {**completeness['event_coding'], 'lesions': {
                'L1': {'label': 'x', 'distinct_from': 'L2'}}}},
            'an event entry of the wrong shape': {'event_coding': {**completeness['event_coding'], 'sessions': {
                COLON: {**completeness['event_coding']['sessions'][COLON], 'reportable': [{'event': 'E2'}]}}}},
        }
        for label, value in broken.items():
            with self.subTest(label):
                with self.assertRaises(overlay.UnreadableCoding):
                    overlay.read_coding(value)
                self.assertIsNone(overlay.coding_of(value))

    def test_an_unreadable_record_fails_closed_and_releases_nothing(self):
        rows, completeness = scenario(acts=False)
        competing = {'id': combination.COMPETING_CHECK, 'label': 'Codes proposed for the same documented act',
                     'status': 'warn', 'detail': 'held', 'source': ''}
        rows[1] = overlay.Stored(**{**rows[1].__dict__, 'checks': (competing,), 'holds': ('competing_codes',),
                                    'status': 'needs_clarification', 'support': {**rows[1].support,
                                                                                 'competes': ['45380']}})
        decisions = {'k-snare': 'reject', 'k-biopsy': 'reject'}
        readable = overlay.review_view(rows, decisions, completeness=completeness)
        self.assertEqual((readable['k-base'].status, readable['k-base'].released), ('ready', ('base_included',)))
        for label, value in (('absent', {}), ('another version', scenario(coding_version='x@9')[1])):
            with self.subTest(label):
                views = overlay.review_view(rows, decisions, completeness=value)
                base = views['k-base']
                self.assertEqual((base.status, base.released, base.stale), ('needs_clarification', (), ('services.base_included',)))
                self.assertEqual([c['id'] for c in base.checks], ['services.base_included'])  # kept as stored
                self.assertEqual([q['question'] for q in base.questions], [BASE_Q])
                still = overlay.review_view(rows, {'k-biopsy': 'reject'}, completeness=value)['k-snare']
                self.assertEqual((still.status, still.released, still.stale),
                                 ('needs_clarification', (), (combination.COMPETING_CHECK,)))

    def test_readiness_blocks_an_unreadable_new_path_record(self):
        events = overlay.coding_of
        new = SimpleNamespace(engine_version='cpt-studio-events@1', completeness={'event_coding': None})
        from studio.interpretation import readers
        self.assertTrue(readers.for_assessment(new).unreadable(new))
        self.assertFalse(readers.for_assessment(new).unreadable(SimpleNamespace(
            engine_version='cpt-studio-events@1', completeness=scenario()[1])))
        self.assertIs(events, overlay.coding_of)


class SeamTests(SimpleTestCase):
    def views(self, decisions=None, answers=(), rows=None, completeness=None):
        stored, coding = scenario()
        return overlay.review_view(rows if rows is not None else stored, decisions or {},
                                   completeness=completeness if completeness is not None else coding, answers=answers)

    def test_the_base_rule_reads_the_counted_set_and_a_rejection_releases_it(self):
        held = self.views()['k-base']
        self.assertEqual((held.status, held.recomputed, held.released), ('needs_clarification', (), ()))
        # the documented acts keep it held once both codes are rejected - beside the acts now (the engine's rule)
        acts = self.views({'k-snare': 'reject', 'k-biopsy': 'reject'})['k-base']
        self.assertEqual((acts.status, acts.recomputed, acts.released),
                         ('needs_clarification', ('services.base_included',), ()))
        self.assertIn('forceps biopsy, snare removal', acts.checks[0]['detail'])
        # with no documented act of its own, the rejections release it
        stored, coding = scenario(acts=False)
        released = self.views({'k-snare': 'reject', 'k-biopsy': 'reject'}, rows=stored, completeness=coding)['k-base']
        self.assertEqual((released.status, released.released), ('ready', ('base_included',)))
        # a member's answer never lifts the hold another code's presence makes (L7-01)
        answered = self.views(answers=[{'code': '45385', 'family': COLON, 'fact': 'base_included',
                                        'value': 'not_documented'}])
        self.assertEqual(answered['k-base'].status, 'needs_clarification')

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

    def test_the_modifier_review_pairs_only_lesions_verified_distinct(self):
        review_ = self.views()['k-snare'].modifier_review
        self.assertEqual((review_['kind'], review_['codes'], review_['service'], review_['options']),
                         ('distinct_lesion', ['45385', '45380'], COLON, ['59', 'XS']))
        self.assertEqual(review_['lesions'], {'45385': ['6 mm polyp in the sigmoid colon'],
                                              '45380': ['3 mm polyp in the ascending colon']})
        self.assertEqual(review_['text'], checks.distinct_lesion_review_text(
            '45385', ['snare removal of the 6 mm polyp'], [('45380', ['forceps biopsy of the 3 mm polyp'])], ''))
        # dropped once the other code leaves the effective set
        self.assertIsNone(self.views({'k-biopsy': 'reject'})['k-snare'].modifier_review)
        # an identity not verified distinct never pairs (E15)
        stored, completeness = scenario()
        completeness['event_coding']['lesions']['L1']['distinct_from'] = []
        self.assertIsNone(self.views(completeness=completeness)['k-snare'].modifier_review)
        # an event the coding does not record with its lesion: nothing is offered (fail-closed)
        stored, completeness = scenario()
        completeness['event_coding']['sessions'][COLON]['reportable'] = \
            completeness['event_coding']['sessions'][COLON]['reportable'][:1]
        self.assertIsNone(self.views(completeness=completeness)['k-snare'].modifier_review)

    def test_the_claims_manual_example_is_cited_from_the_retrieval_trace(self):
        stored, completeness = scenario()
        retrieval = [{'code': '45380', 'passages': [{'passage_key': overlay.CLAIMS_EXAMPLE_PASSAGE,
                                                      'topic': overlay.CLAIMS_EXAMPLE_TOPIC, 'release': 'R1',
                                                      'source_key': 'not-bundled', 'section': '13', 'page': '4'}]}]
        cited = overlay.review_view(stored, {}, completeness=completeness, retrieval=retrieval)['k-snare'].modifier_review
        self.assertEqual(cited['sources'][0]['release'], 'R1')
        self.assertEqual(cited['sources'][0]['title'], '')  # a source this release does not bundle names no title
        self.assertIn('R1', cited['text'])

    def test_a_reinstated_code_with_no_session_of_its_own_reads_its_familys(self):
        stored, completeness = scenario()
        completeness['event_coding']['codes']['k-exc']['session'] = ''
        session = overlay._service(stored[3], completeness['event_coding'], overlay.Decided('reinstate'))
        self.assertEqual((session['id'], session['label']), (COLON, 'colonoscopy'))
        self.assertIsNone(overlay._service(stored[3], completeness['event_coding'], None))
        self.assertIsNone(overlay._service(stored[3], None, overlay.Decided('reinstate')))

    def test_an_answer_the_engine_read_is_read_through_the_one_marker(self):
        stored, completeness = scenario()
        marker = {questions.ANSWERED_SUPPORT: {'fact': 'extent', 'value': 'cannot_confirm', 'answers': ['a1']}}
        stored[2] = overlay.Stored(**{**stored[2].__dict__, 'bucket': 'excluded', 'status': 'excluded',
                                      'support': {**stored[2].support, **marker}})
        views = overlay.review_view(stored, {}, completeness=completeness)
        self.assertEqual((views['k-biopsy'].reason, views['k-biopsy'].answer, views['k-biopsy'].answered),
                         ('detail_unavailable', 'cannot_confirm', 'extent'))
        self.assertTrue(views['k-biopsy'].active)  # it still counts where its presence held another code
