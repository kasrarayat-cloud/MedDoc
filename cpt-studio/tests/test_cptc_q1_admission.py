"""Completion repair (owner directive 2026-11-06, items 3 and 5; HARNESS.md "Completion repair (2026-11-06)", criteria
C3 and C5; builder Q1): equal proposal eligibility, evidence-based reconciliation, and truthful statuses and reasons.

- EQUAL ELIGIBILITY (U8). An explicit first-reading code of Astra or Fable - in scope, quoted verbatim with an exact
  span - is admitted and read by the same per-code path as a code Corti selects. Its outcome is that path's, whoever
  proposed it and whatever Corti did with the code: READY where the readers document the act today; held, with the same
  question, where they read it in doubt or cannot find it; excluded with the passage, reinstatable, where the document
  states it not done. Cross-code effects (the base rules, competition) are computed the same way for every proposer. A
  genuine non-proposal (out of scope, unlocated, inexact, peer-only) is the only participant alternative.
- EVIDENCE-BASED RECONCILIATION (item 2). A code several providers propose is read once, over every proposer's exact
  passages: it is never held because one proposer cited text about another act while another proposer's passage shows
  the act, and a passage that doubts the code's own act holds it whoever cited it. Who cited which passage is recorded.
- AN ACT THE DOCUMENT STATES NOT DONE (item 5). Failed, planned, historical or still to be done, as the
  documented-service reader reads it: the code is excluded with the passage that says so, for every proposer, so its
  family's base code is no longer held as included in it. Every other reading keeps the hold - the closed class's
  failure mode is the safe side - and the measured refuters of a wider class are pinned here.
- TRUTHFUL REASONS (U9). Nothing is called "not documented" from a reader's silence: CPT Studio says it could not find,
  or could not confirm, the act.

Real readers and engine, synthetic documents, nothing sent. Expected outcomes are written here, outside the coding
input.
"""
from unittest import expectedFailure

from django.test import SimpleTestCase

from studio.types import ProviderCode
from studio.validation import engine
from tests import test_harness2_pipeline as hp
from tests import test_harness2_r6_meaning as r6m
from tests.test_harness_engine import code, corti, decision, peer, proposal, read, reviewed, run, span, without_record
from tests.test_h3_repairs import EGD_BIOPSY, LABELLED, NET, PLAIN, SNARE

# --- the documents (synthetic) --------------------------------------------------------------------------------------

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
SEEN = 'A 9 mm pedunculated polyp in the sigmoid colon was seen.'


def colon(body, procedure='Colonoscopy with hot snare polypectomy'):
    """The refutation cycle 3 (C3-2) report shape: a colonoscopy to the cecum, a polyp seen, then ``body``."""
    return (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
            'Place of service: Ambulatory surgery center\n' f'Procedure: {procedure}\n' + CECUM + '\n' + SEEN + '\n'
            + body + '\n')


D2 = 'The endoscope was advanced to the second part of the duodenum.'


def egd(body, procedure='EGD with band ligation'):
    return (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
            f'Procedure: {procedure}\n' + D2 + '\n' + body + '\n')


def coded(result, value):
    return [(p.bucket, p.status, [q.fact for q in p.clarifications]) for p in result.proposals if p.code == value]


def shape(item):
    """What a decision rests on, apart from the key and the record (which proposer, which position)."""
    return (item.bucket, item.status, item.reinstatable, item.exclusion_reason, [q.fact for q in item.clarifications],
            [(c.id, c.status) for c in item.checks])


def by_participant(text, act, quote, base='45378', base_quote=CECUM, who=('astra',)):
    """Corti selects only the base code; the participants propose ``act`` on ``quote``."""
    return run(text, corti((base, span(text, base_quote))), [read(name, [code(text, act, quote)]) for name in who])


def by_corti(text, act, quote, base='45378', base_quote=CECUM):
    """Corti selects the base code and ``act`` on ``quote`` itself."""
    return run(text, corti((base, span(text, base_quote)), (act, span(text, quote))))


EXCLUDED = ('excluded', 'excluded', [])
HELD_STATUS = ('selected', 'needs_clarification', ['performed_status'])
READY = ('selected', 'ready', [])
BASE_HELD = ('selected', 'needs_clarification', ['base_included'])


class EqualEligibilityMatrixTests(SimpleTestCase):
    """C3's matrix: one per-code validation, whoever proposed the code."""

    def test_only_astra_or_only_fable_proposes_a_documented_act(self):
        alone = proposal(run(PLAIN, corti(('45385', span(PLAIN, SNARE)), ('43239', span(PLAIN, EGD_BIOPSY)))), '43239')
        for name in ('astra', 'fable'):
            with self.subTest(name):
                result = run(PLAIN, corti(('45385', span(PLAIN, SNARE))), [read(name, [code(PLAIN, '43239', EGD_BIOPSY)])])
                item = proposal(result, '43239')
                self.assertEqual((item.bucket, item.status, item.support['origin'], item.support['proposed_by']),
                                 ('selected', 'ready', 'participant', [name]))
                self.assertEqual(decision(item), decision(alone))  # the same per-code path as Corti's own selection

    def test_corti_returns_another_code(self):
        # Corti's 45384 (hot forceps) for the cold-snare removal: Astra's 45385 reaches review ready on the readers'
        # reading, and Corti's own code is read by its own rules
        result = run(PLAIN, corti(('43239', span(PLAIN, EGD_BIOPSY)), ('45384', span(PLAIN, SNARE))),
                     [read('astra', [code(PLAIN, '45385', SNARE)])])
        self.assertEqual(coded(result, '45385'), [READY])
        self.assertEqual(coded(result, '45384'), [HELD_STATUS])

    def test_corti_lists_it_only_as_an_alternative(self):
        candidate = ProviderCode('candidate', 'cpt', '43239', 'UNVERIFIED PROVIDER WORDING', (span(PLAIN, EGD_BIOPSY),))
        result = run(PLAIN, [*corti(('45385', span(PLAIN, SNARE))), candidate],
                     [read('fable', [code(PLAIN, '43239', EGD_BIOPSY)])])
        self.assertEqual(coded(result, '43239'), [READY, ('alternative', 'informational', [])])
        admitted = next(p for p in result.proposals if p.code == '43239' and p.bucket == 'selected')
        self.assertTrue(admitted.rationale.startswith('Proposed by Fable (independent participant); Corti listed this '
                                                      'code as a candidate or an alternative'), admitted.rationale)

    def test_all_three_agree_on_an_unsupported_denied_or_historical_act_is_never_ready(self):
        """Agreement adds nothing: a failed, denied, planned or earlier act is never READY, and its outcome is the same
        whether Corti selected the code too or only the participants proposed it."""
        base = colon('', procedure='Colonoscopy').rstrip('\n') + '\n'
        for line, expected in (('Hot snare polypectomy of the 8 mm descending colon polyp failed.', EXCLUDED),
                               ('No polyps were removed.', EXCLUDED),
                               ('The 12 mm sigmoid polyp will be removed with a snare at a later date.', EXCLUDED),
                               ('At the last colonoscopy a 9 mm polyp was removed with a hot snare.', HELD_STATUS)):
            text = base + line + '\n'
            with self.subTest(line):
                agreed = run(text, corti(('45378', span(text, CECUM)), ('45385', span(text, line))),
                             [read('astra', [code(text, '45385', line)]), read('fable', [code(text, '45385', line)])])
                only = by_participant(text, '45385', line, who=('astra', 'fable'))
                self.assertEqual(coded(agreed, '45385'), [expected])
                self.assertEqual(coded(only, '45385'), [expected])
                self.assertEqual(shape(proposal(agreed, '45385')), shape(proposal(only, '45385')))
                self.assertNotIn('ready', [p.status for p in agreed.proposals if p.code == '45385'])

    def test_corti_selecting_or_omitting_the_code_never_changes_its_outcome(self):
        cases = (colon('Hot snare polypectomy failed.'), colon('It is unknown whether hot snare polypectomy was '
                                                               'performed.'),
                 colon('A 9 mm sessile polyp in the sigmoid colon was removed with a hot snare.', 'Colonoscopy'))
        quotes = ('Hot snare polypectomy failed.', 'It is unknown whether hot snare polypectomy was performed.',
                  'A 9 mm sessile polyp in the sigmoid colon was removed with a hot snare.')
        for text, quote in zip(cases, quotes):
            with self.subTest(quote):
                mine, theirs = by_participant(text, '45385', quote), by_corti(text, '45385', quote)
                self.assertEqual(shape(proposal(mine, '45385')), shape(proposal(theirs, '45385')))
                self.assertEqual(shape(proposal(mine, '45378')), shape(proposal(theirs, '45378')))


class CycleThreeRefuterTests(SimpleTestCase):
    """Refutation cycle 3, C3-2-1 to C3-2-3, read the new way: never an alternative "not documented as done"; the act
    the document states not done is excluded with its passage (Corti's base code READY), a doubted one is held and holds
    the base code, as Corti's own selection does (the corpus's ADM entries)."""

    NOT_DONE = ('Hot snare polypectomy failed.', 'Hot snare polypectomy was unsuccessful.',
                'Hot snare polypectomy was abandoned.', 'Hot snare polypectomy will be performed at a later date.',
                'Hot snare polypectomy is to be performed at a later date.')

    def test_an_act_the_document_states_not_done_is_excluded_with_its_passage(self):
        for line in self.NOT_DONE:
            text = colon(line)
            for quote in (line, 'Colonoscopy with hot snare polypectomy'):
                for who in (('astra',), ('fable',), ('astra', 'fable')):
                    with self.subTest(line=line, quote=quote, who=who):
                        result = by_participant(text, '45385', quote, who=who)
                        item = proposal(result, '45385')
                        self.assertEqual((item.bucket, item.status, item.reinstatable), ('excluded', 'excluded', True))
                        self.assertIn(line, item.exclusion_reason)  # said with the passage that says so
                        self.assertEqual(coded(result, '45378'), [READY])
                        self.assertEqual(shape(item), shape(proposal(by_corti(text, '45385', quote), '45385')))

    def test_the_banding_refuter_in_an_upper_endoscopy(self):
        line = 'Band ligation of the varices was unsuccessful.'
        text = egd('Large esophageal varices were seen in the distal esophagus.\n' + line)
        for quote in (line, 'EGD with band ligation'):
            with self.subTest(quote):
                result = by_participant(text, '43244', quote, base='43235', base_quote=D2)
                self.assertEqual([c[:2] for c in coded(result, '43244')], [EXCLUDED[:2]])
                self.assertEqual([c[:2] for c in coded(result, '43235')], [READY[:2]])

    def test_an_open_question_holds_the_code_and_its_base(self):
        line = 'It is unknown whether hot snare polypectomy was performed.'
        text = colon(line)
        for quote in (line, 'Colonoscopy with hot snare polypectomy'):
            with self.subTest(quote):
                result = by_participant(text, '45385', quote)
                self.assertEqual(coded(result, '45385'), [HELD_STATUS])
                self.assertEqual(coded(result, '45378'), [BASE_HELD])  # F5: never final alone beside a doubted act

    def test_an_attempt_a_consent_or_a_question_is_held_never_listed_as_not_done(self):
        """Recorded residuals against the corpus's required READY base: the reader reads only an attempt, a consent's
        object or a question, which is no statement that the act was not done - and the wider releases were measured
        unsafe (see StatedNotDoneRefuterTests) - so the code is held with its question and holds the base code, exactly
        as Corti's own selection of the passage does. Never an alternative, never READY."""
        for body, act, quote in (
                ('Hot snare polypectomy was attempted but the polyp could not be removed.', '45385', None),
                ('Consent was obtained for biopsy and cold snare polypectomy.', '45380', None),
                ('Written consent was obtained for possible hot snare polypectomy.', '45385', None),
                ('Were biopsies taken from the polyp?', '45380', None),
                ('Was the polyp removed with a cold snare?', '45385', None)):
            procedure = 'Colonoscopy with hot snare polypectomy' if 'attempted' in body else 'Colonoscopy'
            text = colon(body, procedure)
            with self.subTest(body):
                result = by_participant(text, act, quote or body)
                self.assertEqual(coded(result, act), [HELD_STATUS])
                self.assertEqual(coded(result, '45378'), [BASE_HELD])
                item = proposal(result, act)
                self.assertNotIn('not documented', (item.exclusion_reason + item.clarifications[0].reason).lower())
                self.assertEqual(shape(item), shape(proposal(by_corti(text, act, quote or body), act)))


class StatedNotDoneRuleTests(SimpleTestCase):
    """engine._stated_not_done: equivalent wordings in other layouts and another GI family, and its own conditions."""

    def test_a_labelled_line_and_a_table_like_row(self):
        for line in ('Hot snare polypectomy: unsuccessful.', 'Polypectomy | unsuccessful'):
            text = colon(line, 'Colonoscopy')
            with self.subTest(line):
                for result in (by_participant(text, '45385', line), by_corti(text, '45385', line)):
                    self.assertEqual(coded(result, '45385'), [EXCLUDED])
                    self.assertEqual(coded(result, '45378'), [READY])

    def test_a_failed_dilation_in_an_upper_endoscopy(self):
        line = 'Balloon dilation of the distal esophageal stricture failed.'
        text = egd('A distal esophageal stricture was seen.\n' + line, procedure='EGD with balloon dilation')
        result = by_participant(text, '43249', line, base='43235', base_quote=D2)
        self.assertEqual([c[:2] for c in coded(result, '43249')], [EXCLUDED[:2]])

    def test_a_done_act_is_never_excluded(self):
        line = 'The polyp was removed with a hot snare.'
        text = colon(line, 'Colonoscopy')
        self.assertEqual(coded(by_participant(text, '45385', line), '45385'), [READY])
        self.assertEqual(coded(by_participant(text, '45385', line), '45378'), [BASE_HELD])

    def test_a_base_code_never_reads_the_rule(self):
        from studio.gi import detect
        from studio.gi import services as gi_services
        from studio.validation import reconcile
        from tests.test_harness_engine import DAY
        text = colon('Hot snare polypectomy failed.')
        inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY))
        base = reconcile.match('45378', inventory, 'gi.colonoscopy')
        snare = reconcile.match('45385', inventory, 'gi.colonoscopy')
        self.assertEqual(engine._stated_not_done('45378', base, (), text, DAY), ())  # it accounts for no act
        self.assertTrue(engine._stated_not_done('45385', snare, (), text, DAY))
        self.assertEqual(coded(by_corti(text, '45385', 'Hot snare polypectomy failed.'), '45378'), [READY])


class StatedNotDoneRefuterTests(SimpleTestCase):
    """The rule's conjuncts, each by a refuter measured before it was written: a failure the document later overtakes,
    a consent's object or a question that the document answers, a hedge, and a removal the routing-era reader reads
    done in the same passage all keep the code held - never excluded, so the base code is never released by them."""

    def test_each_refuter_keeps_the_hold(self):
        for body, act, procedure in (
                ('Hot snare polypectomy failed initially but the polyp was then removed.', '45385', 'Colonoscopy'),
                ('Hot snare polypectomy failed initially. The polyp was then removed.', '45385', 'Colonoscopy'),
                ('Hot snare polypectomy failed. It is unclear whether the polyp was removed.', '45385', 'Colonoscopy'),
                ('The polyp was removed, and hot snare polypectomy of the stalk failed.', '45385', 'Colonoscopy'),
                ('Consent was obtained for biopsy, which was performed.', '45380', 'Colonoscopy'),
                ('Were biopsies taken from the polyp? Yes.', '45380', 'Colonoscopy'),
                ('A 6 mm polyp was removed with a cold snare (? complete).', '45385', 'Colonoscopy'),
                ('Hot snare polypectomy was attempted.', '45385', 'Colonoscopy with hot snare polypectomy')):
            text = colon(body, procedure)
            with self.subTest(body):
                for result in (by_participant(text, act, body), by_corti(text, act, body)):
                    self.assertEqual(coded(result, act), [HELD_STATUS])
                    self.assertEqual(coded(result, '45378'), [BASE_HELD])


class EvidenceReconciliationTests(SimpleTestCase):
    """Item 2: one code, read once over every proposer's exact passages."""

    L44 = (HEAD + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
           'Procedure\nThe colonoscope was advanced to the cecum.\n'
           'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n'
           'At the last colonoscopy in 2019 a 12 mm polyp was removed with a hot snare.\n')
    TODAY = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
    EARLIER = 'At the last colonoscopy in 2019 a 12 mm polyp was removed with a hot snare.'

    def test_another_proposers_passage_showing_the_act_releases_the_evidence_hold(self):
        # L4-4 (recorded open in harness repair 3): Corti's passage is the 2019 polypectomy, Astra's today's snare
        alone = run(self.L44, corti(('45385', span(self.L44, self.EARLIER))))
        self.assertEqual(coded(alone, '45385'), [HELD_STATUS])
        both = run(self.L44, corti(('45385', span(self.L44, self.EARLIER))),
                   [read('astra', [code(self.L44, '45385', self.TODAY)])])
        item = proposal(both, '45385')
        self.assertEqual((item.bucket, item.status), ('selected', 'ready'))
        self.assertEqual([e.text for e in item.evidence], [self.TODAY, self.EARLIER])  # document order, each once
        self.assertEqual([(p['by'], self.L44[p['start']:p['end']]) for p in item.support['provenance']],
                         [(['astra'], self.TODAY), (['corti'], self.EARLIER)])
        self.assertEqual((item.support['supporting'], item.support['unrelated']), ([0], [1]))
        self.assertEqual(item.support['proposed_by'], ['corti', 'astra'])
        # the same passages give the same reading whoever cited which: Astra alone citing both
        own = run(self.L44, corti(), [read('astra', [code(self.L44, '45385', self.TODAY, self.EARLIER)])])
        self.assertEqual(coded(own, '45385'), [READY])

    def test_a_passage_doubting_the_codes_own_act_still_holds_it_whoever_cited_it(self):
        text = (HEAD + 'Colonoscopy report\nDate of service: 2026-10-14\nProcedure\nThe colonoscope was advanced to the '
                'cecum.\nA 12 mm flat lesion in the ascending colon was biopsied with cold forceps.\nIt is unclear '
                'whether further biopsies were taken from the ascending colon lesion.\n')
        done, hedge = 'was biopsied with cold forceps', 'further biopsies were taken from the ascending colon lesion'
        for corti_quote, theirs in ((done, hedge), (hedge, done)):
            with self.subTest(corti=corti_quote):
                result = run(text, corti(('45380', span(text, corti_quote))), [read('fable', [code(text, '45380', theirs)])])
                self.assertEqual(coded(result, '45380'), [HELD_STATUS])

    def test_a_proposer_adding_no_passage_changes_nothing_but_the_record(self):
        text = PLAIN
        alone = run(text, corti(('45385', span(text, SNARE))))
        agreed = run(text, corti(('45385', span(text, SNARE))), [read('astra', [code(text, '45385', SNARE)]),
                                                                 read('fable', [code(text, '45385', SNARE)])])
        self.assertEqual(without_record(proposal(agreed, '45385')), proposal(alone, '45385'))
        self.assertNotIn('provenance', proposal(agreed, '45385').support)

    def test_a_peer_reviews_additional_code_and_a_peer_only_quote_add_no_passage(self):
        extra = 'A separate 12 mm flat lesion'
        text = (HEAD + 'Colonoscopy report\nDate of service: 2026-10-14\nProcedure\nThe colonoscope was advanced to the '
                'cecum.\nA 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n' + extra
                + ' in the ascending colon was biopsied with cold forceps.\n')
        snare = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        alone = run(text, corti(('45385', span(text, snare))))
        late = reviewed('astra', [], peer('astra', additional=[code(text, '45385', extra)]))
        result = run(text, corti(('45385', span(text, snare))), [late])
        self.assertEqual(without_record(proposal(result, '45385')), proposal(alone, '45385'))


class TruthfulReasonTests(SimpleTestCase):
    """U9: no reason says "not documented" from a reader's silence."""

    ABSENCE = ('not documented as done', 'no documentation establishes', 'is documented as done in it',
               'does not establish the')

    def assertTruthful(self, item):
        words = ' '.join([item.exclusion_reason] + [q.question + ' ' + q.reason for q in item.clarifications]
                         + [c.detail for c in item.checks]).lower()
        for phrase in self.ABSENCE:
            self.assertNotIn(phrase, words)

    def test_the_bolus_removal_is_a_held_proposal_never_listed_as_not_done(self):
        """39f0ac49's and d44a77b3's shape: the participants' exactly quoted 43247 for "the bolus was removed" reaches
        review held - by the labelled report's service doubt (U2), and on a plain report by the act CPT Studio could not
        find (U1, the readers' repair) - never an alternative "not documented as done"."""
        for text in (LABELLED, PLAIN):
            with self.subTest('labelled' if text is LABELLED else 'plain'):
                result = run(text, corti(('43239', span(text, EGD_BIOPSY)), ('45385', span(text, SNARE))),
                             [read('astra', [code(text, '43247', NET)]), read('fable', [code(text, '43247', NET)])])
                item = proposal(result, '43247')
                self.assertEqual((item.bucket, item.status, item.support['origin'], item.support['proposed_by']),
                                 ('selected', 'needs_clarification', 'participant', ['astra', 'fable']))
                self.assertTruthful(item)
        plain = proposal(run(PLAIN, (), [read('astra', [code(PLAIN, '43247', NET)])], provider_status='failed'),
                         '43247')
        self.assertIn('CPT Studio could not find a foreign-body removal', plain.clarifications[0].question)

    def test_the_routing_era_doubt_is_worded_as_what_cpt_studio_could_not_confirm(self):
        text = colon('Possibly a hot snare polypectomy was performed.', 'Colonoscopy')
        item = proposal(by_corti(text, '45385', 'Possibly a hot snare polypectomy was performed.'), '45385')
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
        self.assertTruthful(item)

    def test_only_a_genuine_non_proposal_is_a_participant_alternative(self):
        text = PLAIN
        result = run(text, corti(('45385', span(text, SNARE))), [
            read('astra', [code(text, 'G0105', SNARE), code(text, '45378', 'not in the document')]),
            reviewed('fable', [], peer('fable', additional=[code(text, '43239', EGD_BIOPSY)]))])
        alternatives = {p.code: p for p in result.proposals if p.bucket == 'alternative'}
        self.assertEqual(sorted(alternatives), ['43239', '45378', 'G0105'])  # peer-only, unlocated, out of scope
        self.assertIn(engine.PARTICIPANT_PEER_ONLY, alternatives['43239'].exclusion_reason)
        self.assertIn(engine.UNLOCATED, alternatives['45378'].exclusion_reason)
        for item in alternatives.values():
            self.assertFalse(item.reinstatable)
        failed = colon('Hot snare polypectomy failed.')
        excluded = proposal(by_participant(failed, '45385', 'Hot snare polypectomy failed.'), '45385')
        self.assertTrue(excluded.reinstatable)  # an admitted code excluded with its passage is reinstatable


class OtherRoleHoldTests(SimpleTestCase):
    """The owner's protection of other-provider acts (directive 2026-11-06, item 2), now on the shared path: an act
    documented only in another role's entry never makes a code READY, whoever proposed it. Before, only a participant's
    code was kept out (own-3's admission rule) and Corti's own selection of the same passage was READY."""

    OTHER_ROLE = (
        ('A 6 mm polyp was seen in the sigmoid colon.\n\nPATHOLOGY ADDENDUM - 2026-10-16\nSpecimen A, sigmoid colon '
         'polyp, removed by cold snare polypectomy: tubular adenoma.', '45385',
         'Specimen A, sigmoid colon polyp, removed by cold snare polypectomy: tubular adenoma.'),
        ('A 15 mm lesion was seen in the transverse colon.\n\nNursing note\nTattoo ink was injected into the transverse '
         'colon submucosa by the endoscopist.', '45381',
         'Tattoo ink was injected into the transverse colon submucosa by the endoscopist.'),
        ('A 6 mm polyp was seen in the sigmoid colon.\n\nAnesthesia record\nThe 6 mm sigmoid polyp was removed with a cold '
         'snare during propofol sedation.', '45385',
         'The 6 mm sigmoid polyp was removed with a cold snare during propofol sedation.'))

    def text(self, body):
        return (HEAD + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                '(fictional)\nProcedure\nThe colonoscope was advanced to the cecum.\n' + body + '\n')

    def test_another_roles_act_alone_holds_the_code_on_both_paths(self):
        for body, act, quote in self.OTHER_ROLE:
            text = self.text(body)
            with self.subTest(act=act, quote=quote[:30]):
                mine = run(text, corti(), [read('astra', [code(text, act, quote)])], provider_status='failed')
                theirs = run(text, corti((act, span(text, quote))))
                for result in (mine, theirs):
                    item = proposal(result, act)
                    self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                    self.assertIn('documented only in the', item.clarifications[0].question)

    def test_the_physicians_own_act_is_unchanged(self):
        text = self.text('A 6 mm polyp in the sigmoid colon was removed with a cold snare.')
        quote = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        self.assertEqual(coded(run(text, corti(('45385', span(text, quote)))), '45385'), [READY])

    def test_recorded_residual_an_impression_after_a_pathology_line_is_held(self):
        # refutation round 2's over-6: the role reader reads an Impression right after "Pathology results: pending." as
        # the pathology entry's, so the physician's own polypectomy is held (a false hold, the safe side) - the reason
        # round 2 dropped the role rule from the shared path, and why the rule holds rather than excludes
        text = self.text('Pathology results: pending.\nImpression: A 6 mm polyp in the sigmoid colon was removed with a '
                         'cold snare.')
        quote = 'Impression: A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        self.assertEqual(coded(run(text, corti(('45385', span(text, quote)))), '45385'), [HELD_STATUS])


class CompetitionTests(SimpleTestCase):
    """C4: no act has two READY codes, and an excluded code competes with none."""

    def test_an_excluded_code_of_another_proposer_never_holds_a_ready_one(self):
        balloon = 'The Schatzki ring in the distal esophagus was dilated with a through-the-scope balloon to 18 mm.'
        failed = 'Dilation with a Savary bougie failed.'
        text = (HEAD + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\n' + balloon
                + '\n' + failed + '\n')
        result = run(text, corti(('43249', span(text, balloon))), [read('astra', [code(text, '43248', failed)])])
        self.assertEqual([c[:2] for c in coded(result, '43249')], [READY[:2]])
        self.assertNotIn('ready', [p.status for p in result.proposals if p.code == '43248'])

    def test_two_codes_for_one_act_still_compete(self):
        balloon = 'The Schatzki ring in the distal esophagus was dilated with a through-the-scope balloon to 18 mm.'
        text = (HEAD + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                '(fictional)\nProcedure: Upper endoscopy with balloon dilation\nThe gastroscope was passed to the second '
                'portion of the duodenum.\n' + balloon + '\n')
        result = run(text, corti(('43249', span(text, balloon))),
                     [read('astra', [code(text, '43233', 'Procedure: Upper endoscopy with balloon dilation')])])
        for value in ('43249', '43233'):
            self.assertEqual([c[:2] for c in coded(result, value)], [('selected', 'needs_clarification')])
            self.assertIn(engine.COMPETING_FACT, coded(result, value)[0][2])


# --- through the pipeline: an admitted code is a proposal a member decides, as Corti's own selection is ---------------

SNARED = 'The polyp was removed with a hot snare.'


class AdmittedCodePipelineTests(r6m.MeaningCase):
    """Corti's 45378 and Astra's first-reading 45385 on the snare sentence, against Corti selecting both on the same
    document (another request, a trailing blank line: an identical Corti request reuses the workspace's retained
    result). The real pipeline offline, nothing sent."""

    def pair(self):
        text = r6m.doc(r6m.COLON, r6m.SEEN, SNARED)
        mine = self.detail(self.scenario(text, [('45378', r6m.CECUM)], astra=hp.reading(codes=[('45385', SNARED)])))
        theirs = self.corti_alone(text + '\n', [('45378', r6m.CECUM), ('45385', SNARED)])
        return mine, theirs

    def test_an_admitted_code_is_decided_as_corti_s_selection_is(self):
        """Its bucket, status, reinstatability, allowed actions and questions are those of Corti's own selection of the
        passage, and so are Corti's base code's."""
        mine, theirs = self.pair()

        def read_as(view):
            asked = {}
            for question in view['clarifications']:
                asked.setdefault(question['proposal_id'], []).append(question['question'])
            return sorted((p['code'], p['bucket'], p['status'], p['reinstatable'], tuple(p['allowed_actions']),
                           tuple(sorted(asked.get(p['id'], ())))) for p in r6m.proposals(view))
        self.assertEqual(read_as(mine), read_as(theirs))
        (item,) = [p for p in r6m.proposals(mine) if p['code'] == '45385']
        self.assertEqual(((item.get('support') or {}).get('origin'), item['bucket'], item['status']),
                         ('participant', 'selected', 'ready'))

    @expectedFailure
    def test_an_admitted_code_is_traced_as_corti_s_selection_is(self):
        """RECORDED CROSS-FILE DEPENDENCY, failing on this branch by design. The assess stage traces the CMS references
        only for the decidable codes among the provider's own selections (jobs._retrieval's ``& set(provider_codes)``,
        jobs.py:2187, builder Q2's file), so an admitted participant code is untraced and reference validation reads
        'not_run' ("No proposal was checked against the CMS references for this revision.") beside Corti's checked
        45378. With every decidable proposal's code traced, whoever proposed it - review.decidable already keeps every
        alternative out - this passes: remove the decorator then (an unexpected success fails the suite)."""
        mine, theirs = self.pair()
        block = mine['harness']['reference_validation']
        other = theirs['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked']), (other['state'], other['codes_checked']))
        self.assertEqual({p['code']: p['retrieval'] for p in r6m.proposals(mine)},
                         {p['code']: p['retrieval'] for p in r6m.proposals(theirs)})
