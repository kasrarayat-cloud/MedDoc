"""Refutation of the integrated completion diff, cycle 2, admission lens (2026-11-06): the another-act release, the
dilation techniques, "not performed" for a removal, and the units of a code listed twice. Every finding the lens
measured (D1, D2, D4, D5, D6, D7; D3 is builder K's) and the owner session's units defect, with the variants each finding
listed, the controls each repair must leave alone, and an equivalent wording in an upper endoscopy where a rule applies
to both. Every document is synthetic. A pin reads the engine as the website reads it (tests.test_harness_engine.run:
real routing, the real documented-service inventory, the participants' readings where the finding used them)."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.validation import engine, reconcile
from studio.types import EvidenceSpan, ProviderCode
from tests.test_harness_engine import code, corti, read, run, span

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
COLON_HEAD = (BANNER + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n')
ADVANCED = 'The colonoscope was advanced to the cecum and the examination was completed.'
UPPER_HEAD = (BANNER + 'EGD report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n')
DUODENUM = 'The endoscope was advanced to the second portion of the duodenum.'
STRICTURE = 'A benign-appearing distal esophageal stricture was found.'


def colon(body: str) -> str:
    return COLON_HEAD + ADVANCED + '\n' + body + '\n'


def upper(body: str, procedure: str = 'Upper endoscopy') -> str:
    return UPPER_HEAD + f'Procedure: {procedure}\n' + DUODENUM + '\n' + body + '\n'


def dilation(line: str) -> str:
    return upper(STRICTURE + '\n' + line, 'Upper endoscopy with dilation')


def outcome(result, *codes):
    """{code: (bucket, status, [facts])} of the selected and excluded proposals (alternatives left out)."""
    return {p.code: (p.bucket, p.status, [c.fact for c in p.clarifications]) for p in result.proposals
            if p.bucket != 'alternative' and (not codes or p.code in codes)}


def three_ways(text, value, quote, base=None):
    """The same code on the same passage proposed by Corti alone, by Astra alone (Corti selecting only ``base``, when
    given) and by both: equal eligibility (C3)."""
    primary = [base] if base else []
    return {'corti': run(text, corti(*primary, (value, span(text, quote)))),
            'astra': run(text, corti(*primary), [read('astra', [code(text, value, quote)])]),
            'both': run(text, corti(*primary, (value, span(text, quote))), [read('astra', [code(text, value, quote)])])}


HELD = ('selected', 'needs_clarification')
READY = ('selected', 'ready')
EXCLUDED = ('excluded', 'excluded')


class AnotherActReleaseTests(SimpleTestCase):
    """The another-act release is abandoned (integration of refutation cycle 2, the owner's two-cycle rule): a doubt the
    routing-era reader reads in the code's own passage about this service holds the code, whichever act of the service it
    is about, for every proposer alike - the base reading. The release (a doubt about another act of the code's kinds
    moved off the code) was refuted in cycle 1 and again in cycle 2 (D1, D5), and its cycle-2 repair
    (_matched_acts_plain, reading the readers' own output) still released doubts no reader binds to an act. Cycle 1's
    window and word list are gone with it. The cost, declared: E|ANOTHER-failed-attempt (corpus) is held."""

    P1 = ('Hot snare polypectomy of a 15 mm pedunculated polyp in the sigmoid colon was attempted, but the snare could not '
          'be closed around the stalk, and the polyp was left in place.')
    B = 'A 6 mm polyp in the transverse colon was removed with a cold snare.'
    DOUBTED = {
        'hard-wrapped hedge': 'A 6 mm polyp in the transverse colon was removed with a cold snare, but it is\nunclear '
                              'whether the polyp was removed or only biopsied.',
        'one-line hedge': 'A 6 mm polyp in the transverse colon was removed with a cold snare, but it is unclear whether '
                          'the polyp was removed or only biopsied.',
        'may only have been biopsied': 'A 6 mm polyp in the transverse colon was removed with a cold snare, but it may '
                                       'only have been biopsied.',
        'doubtful': 'A 6 mm polyp in the transverse colon was removed with a cold snare, though it is doubtful that the '
                    'polyp was actually removed rather than biopsied.',
        'cannot be confirmed': 'A 6 mm polyp in the transverse colon was removed with a cold snare, but removal cannot '
                               'be confirmed.',
        'not certain': 'A 6 mm polyp in the transverse colon was removed with a cold snare, but the endoscopist is not '
                       'certain the polyp was removed rather than biopsied.',
        'the sentence before': 'It is unclear whether the transverse polyp was removed or only biopsied. A 6 mm polyp in '
                               'the transverse colon was removed with a cold snare.',
        'two sentences later': 'A 6 mm polyp in the transverse colon was removed with a cold snare. The specimen was sent '
                               'to pathology. It is unclear whether the transverse polyp was removed or only biopsied.',
        'her last colonoscopy': 'A 6 mm polyp in the transverse colon was removed with a cold snare at her last '
                                'colonoscopy.',
    }

    def test_a_doubted_act_is_never_released_by_another_lesions_failure(self):
        """Cycle 2, admission D1 and its variants: the only snare act the code could rest on is hedged, open to
        question, doubted a sentence before or two sentences later, or of her last colonoscopy; the cited passage is
        another polyp's failed attempt. Held for Corti alone, Astra alone and both (the base held every one)."""
        for label, body in self.DOUBTED.items():
            text = colon(self.P1 + '\n' + body)
            for who, result in three_ways(text, '45385', self.P1).items():
                with self.subTest(label, who=who):
                    self.assertEqual(outcome(result, '45385')['45385'][:2], HELD)

    def test_the_same_passages_read_the_same_in_either_order(self):
        """Cycle 2, admission D5: the plainly removed polyp and the other polyp's failed attempt in one paragraph read
        the same in either order (cycle 1's window read the next sentence's "attempted" or "Possible" as doubt about it):
        held in both orders, the doubt in the cited passage holding the code - the base reading, never order-dependent."""
        for label, body in (('removed, then the attempt', self.B + ' ' + self.P1),
                            ('the attempt, then removed', self.P1 + ' ' + self.B),
                            ('an unrelated possible finding', self.B + ' Possible diverticulosis was noted in the '
                                                                       'sigmoid colon.\n' + self.P1)):
            text = colon(body)
            for who, result in three_ways(text, '45385', self.P1).items():
                with self.subTest(label, who=who):
                    self.assertEqual(outcome(result, '45385')['45385'][:2], HELD)

    def test_a_cited_failed_attempt_holds_beside_another_removed_polyp(self):
        """The cycle-1 another-act controls under the base reading: another polyp plainly removed beside the cited failed
        attempt does not release the code; cited alone, the failure holds it for the reviewer whoever cites it. The
        release this replaced was refuted twice, and the hold was its declared cost (E|ANOTHER-failed-attempt), which
        the acceptance walk met (finding 5). The walk round changes the approach (engine._set_aside_attempts): with the
        removed polyp's own passage cited beside it (one reading over every proposer's passages), the closed-form
        failure is set aside and the code reads as with that passage cited alone - READY."""
        for body in (self.P1 + '\n' + self.B, self.B + '\n' + self.P1):
            text = colon(body)
            for who, result in three_ways(text, '45385', self.P1).items():
                with self.subTest(body[:20], who=who):
                    self.assertEqual(outcome(result, '45385')['45385'][:2], HELD)
            joint = run(text, corti(('45385', span(text, self.P1))), [read('astra', [code(text, '45385', self.B)])])
            self.assertEqual(outcome(joint, '45385')['45385'][:2], READY)
        # the removed polyp's own passage, cited alone, is READY: the hold is the cited failure's, not the code's
        text = colon(self.P1 + '\n' + self.B)
        self.assertEqual(outcome(run(text, corti(('45385', span(text, self.B)))), '45385')['45385'][:2], READY)

    def test_a_doubt_the_reader_binds_to_no_act_holds_too(self):
        """Cycle 2, admission D1 (the class, beyond the lens's variants; found by the builder): a later sentence whose
        act predicate the documented-service reader reads in doubt or of another occasion, though it binds it to no act,
        holds; an unrelated done act does not (the base held all three)."""
        for body, expected in (('It is unknown whether the polyp was removed.', HELD),
                               ('This was done at her colonoscopy in 2023.', HELD),
                               ('Removal could not be confirmed.', HELD),
                               ('The removal was likely incomplete.', HELD),
                               ('It is unknown whether the polyp was actually removed.', HELD),
                               ('Cold forceps biopsies of the rectum were taken.', HELD)):
            text = colon(self.P1 + '\n' + self.B + ' ' + body)
            with self.subTest(body):
                result = run(text, corti(('45385', span(text, self.P1))))
                self.assertEqual(outcome(result, '45385')['45385'][:2], expected)

    def test_the_release_and_its_repair_are_gone(self):
        """The another-act release and its cycle-2 repair are removed, not patched a third time."""
        self.assertFalse(hasattr(engine, '_matched_acts_plain'))
        self.assertFalse(hasattr(engine, '_another_acts_doubt'))

    def test_an_upper_endoscopy_reads_the_same(self):
        """Cycle 2, admission D1 and D5 in another GI family: an EGD snare code cited on a failed attempt at a gastric
        polyp is held in either order and where the removed polyp is hedged - the base reading."""
        p1 = ('Hot snare polypectomy of a 15 mm pedunculated polyp in the gastric body was attempted, but the snare could '
              'not be closed around the stalk, and the polyp was left in place.')
        done = 'A 6 mm polyp in the gastric antrum was removed with a cold snare.'
        hedged = ('A 6 mm polyp in the gastric antrum was removed with a cold snare, but it is\nunclear whether the polyp '
                  'was removed or only biopsied.')
        for body, expected in ((p1 + '\n' + done, HELD), (done + ' ' + p1, HELD), (p1 + '\n' + hedged, HELD)):
            text = upper(body)
            for who, result in three_ways(text, '43251', p1).items():
                with self.subTest(body[-30:], who=who):
                    self.assertEqual(outcome(result, '43251')['43251'][:2], expected)

    def test_cycle_ones_window_and_word_list_are_gone(self):
        """Cycle 2, admission D1 and D5: the refuted cycle-1 patch is abandoned, not patched a third time."""
        self.assertFalse(hasattr(engine, '_matched_act_in_doubt'))
        self.assertFalse(hasattr(engine, '_OPEN_QUESTION'))


class DilationTechniqueTests(SimpleTestCase):
    """reconcile.dilation_techniques, technique_fits and the act_denied branch: a wire-guided dilator and a balloon named
    in one passage are two techniques (cycle 1's deferral to a balloon named anywhere in the passage is abandoned), and a
    dilation code is never excluded as not performed beside a performed dilation."""

    D2 = {
        'after balloon dilation failed': 'The stricture was dilated with wire-guided dilators to 15 mm after balloon '
                                         'dilation failed.',
        'rather than with a balloon': 'The stricture was dilated with wire-guided dilators to 15 mm rather than with a '
                                      'balloon.',
        'balloon unsuccessful, so': 'Balloon dilation was unsuccessful, so the stricture was dilated with wire-guided '
                                    'dilators to 16 mm.',
        'too tight for a balloon': 'The stricture was too tight for a balloon and was dilated with wire-guided dilators '
                                   'to 15 mm.',
        'after air inflation': 'The stricture was dilated with a 15 mm wire-guided dilator after air inflation of the '
                               'esophagus.',
        'instead of balloon dilation': 'The stricture was dilated with wire-guided dilators to 15 mm instead of balloon '
                                       'dilation.',
    }
    D6 = ('Wire-guided dilation to 15 mm was performed instead of balloon dilation.',
          'Rather than balloon dilation, wire-guided dilation to 15 mm was performed.',
          'Over-the-wire dilation to 15 mm was performed instead of balloon dilation.')

    def test_two_techniques_in_one_passage_hold_both_codes_competing(self):
        """Cycle 2, admission D2 and its variants: Corti's 43248 and Astra's 43249 (and the roles swapped) on one passage
        naming wire-guided dilators and a failed or unused balloon are both held as competing - never 43249 READY with
        43248 asked whether a dilation was done."""
        for label, line in self.D2.items():
            text = dilation(line)
            for first, second in (('43248', '43249'), ('43249', '43248')):
                result = run(text, corti((first, span(text, line))), [read('astra', [code(text, second, line)])])
                got = outcome(result, '43248', '43249')
                with self.subTest(label, corti=first):
                    self.assertEqual({c: v[:2] for c, v in got.items()}, {'43248': HELD, '43249': HELD})
                    self.assertTrue(all('competing_codes' in v[2] for v in got.values()))

    def test_a_wire_guided_dilation_beside_a_balloon_not_used_is_never_excluded(self):
        """Cycle 2, admission D6: "Wire-guided dilation ... instead of balloon dilation" and its variants never exclude
        43248 as not performed - held alone (the routing-era reading of "instead of"), competing beside 43249."""
        for line in self.D6:
            text = dilation(line)
            for who, result in three_ways(text, '43248', line).items():
                with self.subTest(line, who=who):
                    self.assertEqual(outcome(result, '43248')['43248'][:2], HELD)
            joint = run(text, corti(('43248', span(text, line))), [read('astra', [code(text, '43249', line)])])
            self.assertEqual({c: v[:2] for c, v in outcome(joint, '43248', '43249').items()},
                             {'43248': HELD, '43249': HELD})

    def test_the_techniques_a_passage_names(self):
        """Cycle 2, admission D2 and D6: the vocabulary - "wire-guided dilation" and "over-the-wire dilation" name the
        wire technique; a wire-guided dilator and a balloon named together are both; an inflation word only adds a
        balloon."""
        for text, named in ((self.D2['after balloon dilation failed'], {'balloon', 'wire_bougie'}),
                            (self.D2['after air inflation'], {'balloon', 'wire_bougie'}),
                            ('Wire-guided dilation to 15 mm was performed.', {'wire_bougie'}),
                            ('Over-the-wire dilation to 15 mm was performed.', {'wire_bougie'}),
                            (self.D6[0], {'balloon', 'wire_bougie'}),
                            ('A through-the-scope balloon was inflated to 18 mm.', {'balloon'}),
                            ('The stricture was dilated with a 15 mm dilator advanced over a guide wire and inflated to '
                             '6 atm for 60 seconds.', {'balloon'})):
            with self.subTest(text):
                self.assertEqual(set(reconcile.dilation_techniques(text)), named)
        self.assertFalse(hasattr(reconcile, 'DILATION_NAMED_BOUGIE'))

    def test_a_dilation_code_is_never_denied_beside_a_performed_dilation(self):
        """Cycle 2, admission D6 at the match: a one-technique code whose only performed dilation is of the other
        technique is unresolved with the technique question (act_missing), never act_denied, whatever the reader reads
        of the technique named as not used."""
        from studio.gi import detect, services as gi_services
        from tests.test_harness_engine import DAY
        line = 'Balloon dilation to 15 mm was performed instead of bougie dilation.'
        text = dilation(line)
        inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY), context_facts=None,
                                      pages=())
        found = reconcile.match('43248', inventory, inventory.services[0].family)
        self.assertEqual((found.state, found.reason), ('uncertain', 'act_missing'))
        self.assertIn('Was a dilation with dilators passed over a guide wire performed on the date of service?',
                      found.question)
        for who, result in three_ways(text, '43248', line).items():
            with self.subTest(who=who):
                self.assertEqual(outcome(result, '43248')['43248'][:2], HELD)


class NotPerformedNeedsDocumentationTests(SimpleTestCase):
    """engine._stated_not_done for a removal kind: excluded only where the service records its lesions and each is
    stated not removed today (services.NOT_REMOVED) or only observed (engine._observed_only: every sentence the reader
    records it in is an observation in its closed form); otherwise held. Cycle 1's early return on any removal word
    before the statement is gone."""

    FAIL = 'En bloc hot snare polypectomy failed.'
    D4 = ('Piecemeal resection of a 25 mm sessile polyp in the ascending colon was completed.',
          'A 25 mm sessile polyp in the ascending colon was taken out piecemeal and retrieved.',
          'A 25 mm sessile polyp in the ascending colon was extracted piecemeal and retrieved.',
          'Piecemeal removal of a 25 mm sessile polyp in the ascending colon was achieved.',
          'A 25 mm sessile polyp in the ascending colon was cleared piecemeal and retrieved.',
          'A 25 mm sessile polyp in the ascending colon was removed piecemeal and retrieved.')

    def test_a_removal_before_a_failed_technique_is_never_excluded(self):
        """Cycle 2, admission D4 and its variants (and cycle 1's F4 form): a lesion removed piecemeal in any phrasing,
        then the failure of the en bloc technique - 45385 held (never excluded with an untrue reason) and 45378 held, for
        Corti and for Astra."""
        for line in self.D4:
            text = colon(line + '\n' + self.FAIL)
            for who, result in three_ways(text, '45385', self.FAIL, base=('45378', span(text, ADVANCED))).items():
                with self.subTest(line, who=who):
                    got = outcome(result, '45385', '45378')
                    self.assertEqual(got['45385'][:2], HELD)
                    self.assertEqual(got['45378'][:2], HELD)

    def test_a_lesion_the_reader_states_not_removed_still_excludes(self):
        """Cycle 2, admission D7's class: where the reader records the lesion and states it not removed ("The polyp
        could not be removed.", "... was left in place."), the failure excludes 45385 with its passage and 45378 is READY,
        for Corti and for Astra (cycle 1's early return held the first: it read the "removed" of "could not be removed")."""
        for body in ('A 20 mm sessile polyp was found in the sigmoid colon. The polyp could not be removed.',
                     'A 20 mm sessile polyp was found in the sigmoid colon. The polyp was left in place.'):
            text = colon(body + '\n' + self.FAIL)
            for who, result in three_ways(text, '45385', self.FAIL, base=('45378', span(text, ADVANCED))).items():
                with self.subTest(body, who=who):
                    got = outcome(result, '45385', '45378')
                    self.assertEqual(got['45385'][:2], EXCLUDED)
                    self.assertEqual(got['45378'][:2], READY)
                    item = next(p for p in result.proposals if p.code == '45385' and p.bucket == 'excluded')
                    self.assertIn(self.FAIL, item.exclusion_reason)
                    self.assertTrue(item.reinstatable)

    def test_a_coordinated_disposition_keeps_the_base_reading(self):
        """Refutation cycle 3 (closed C3-7): the shared subject is abandoned, so "... was found in the sigmoid colon and
        was left in place for surgical resection" records no disposition for the polyp, and the failure excludes
        nothing: both codes are held, as the installed release holds them."""
        text = colon('A 10 mm polyp was found in the sigmoid colon and was left in place for surgical resection.\n'
                     + self.FAIL)
        for who, result in three_ways(text, '45385', self.FAIL, base=('45378', span(text, ADVANCED))).items():
            with self.subTest(who=who):
                got = outcome(result, '45385', '45378')
                self.assertEqual((got['45385'][:2], got['45378'][:2]), (HELD, HELD))

    def test_a_lesion_only_observed_holds(self):
        """Integration of cycle 2 had a closed observation form: a failed or planned removal beside a lesion the report
        only observes excluded 45385 and released 45378 READY. Refutation cycle 4 (closed 1 and 2) abandoned it under the
        two-cycle rule - a removal stated in words no list holds ("the stalk was transected with the same loop and the
        head was recovered") or inside the failure's own passage was excluded as not performed - so a lesion only
        observed keeps the installed release's hold on both codes, whoever proposed the removal code (the ADM C3-2-1
        corpus entries, FALSE HOLD)."""
        for body, expected, base in (
                ('A 9 mm pedunculated polyp in the sigmoid colon was seen.\nHot snare polypectomy failed.', HELD, HELD),
                ('Findings: A 9 mm pedunculated polyp was found in the sigmoid colon.\nHot snare polypectomy was '
                 'unsuccessful.', HELD, HELD),
                # a removal still to come is the reader's own NOT_REMOVED disposition of the lesion: still excluded
                ('A 9 mm pedunculated polyp in the sigmoid colon was seen.\nHot snare polypectomy will be performed at a '
                 'later date.', EXCLUDED, READY),
                ('A 25 mm sessile polyp in the ascending colon was seen and removed piecemeal.\n' + self.FAIL, HELD, HELD),
                ('A 1.5 cm polyp in the sigmoid colon was seen.\nHot snare polypectomy failed.', HELD, HELD)):
            text = colon(body)
            quote = body.split('\n')[-1]
            for who, result in three_ways(text, '45385', quote, base=('45378', span(text, ADVANCED))).items():
                with self.subTest(body[:40], who=who):
                    got = outcome(result, '45385', '45378')
                    self.assertEqual((got['45385'][:2], got['45378'][:2]), (expected, base))

    def test_a_lesion_unread_or_removed_otherwise_holds(self):
        """Cycle 2, admission D4 and D7 ("not performed" needs supporting documentation): a failure beside removed stool,
        another polyp taken with forceps, or with no lesion the reader records, establishes nothing about removal - held,
        the base's reading."""
        for body in ('Liquid stool was suctioned and removed from the right colon.\n' + self.FAIL,
                     'A 3 mm polyp in the rectum was removed with cold forceps.\n' + self.FAIL,
                     'Hot snare polypectomy failed.'):
            text = colon(body)
            quote = body.split('\n')[-1]
            with self.subTest(body):
                got = outcome(run(text, corti(('45385', span(text, quote)), ('45378', span(text, ADVANCED)))),
                              '45385', '45378')
                self.assertEqual(got['45385'][:2], HELD)
                self.assertEqual(got['45378'][:2], HELD)

    def test_recorded_residual_d7_as_written_is_held(self):
        """Cycle 2, admission D7 as the lens wrote it - "A 20 mm sessile polyp in the sigmoid colon could not be removed
        endoscopically." then the failure - is held, not excluded as 179fdff99 read it: the documented-service reader
        records no lesion in a negated clause, and its plain-form disposition reads neither a subject with a modifier
        before the auxiliary nor "endoscopically" after the predicate. A second disposition reading in the engine would
        read the fact twice (C2); the hold is the base's reading, the safe side. Recorded, never chased by a word list."""
        text = colon('A 20 mm sessile polyp in the sigmoid colon could not be removed endoscopically.\n' + self.FAIL)
        got = outcome(run(text, corti(('45385', span(text, self.FAIL)), ('45378', span(text, ADVANCED)))),
                      '45385', '45378')
        self.assertEqual((got['45385'][:2], got['45378'][:2]), (HELD, HELD))

    def test_an_upper_endoscopy_reads_the_same(self):
        """Cycle 2, admission D4 and D7 in another GI family: an EGD snare code after a piecemeal resection is held; after
        a polyp the reader states could not be removed it is excluded and 43235 READY."""
        for body, expected, base in (
                ('Piecemeal resection of a 25 mm sessile polyp in the gastric antrum was completed.', HELD, HELD),
                ('A 20 mm sessile polyp was found in the gastric antrum. The polyp could not be removed.', EXCLUDED, READY)):
            text = upper(body + '\n' + self.FAIL)
            for who, result in three_ways(text, '43251', self.FAIL, base=('43235', span(text, DUODENUM))).items():
                with self.subTest(body, who=who):
                    got = outcome(result, '43251', '43235')
                    self.assertEqual((got['43251'][:2], got['43235'][:2]), (expected, base))


class UnitsTests(SimpleTestCase):
    """Units are the provider group's, as the installed release counts them, with its units.duplicate prompt
    (refutation cycle 3, admission C3-4: cycle 2's engine._supported_units, which dropped a unit wherever the reader read
    an act anything but done, is abandoned - a modifier misread as "historical" silently dropped a placed stent)."""

    DONE = 'A 7 mm polyp in the transverse colon was removed with a cold snare and retrieved.'
    FAILED = ('Hot snare polypectomy of a 12 mm pedunculated polyp in the sigmoid colon was attempted, but the snare could '
              'not be closed around the stalk, and the polyp was left in place.')
    DONE2 = 'A 5 mm polyp in the sigmoid colon was removed with a cold snare and retrieved.'

    def units(self, text, quotes, participants=()):
        result = run(text, corti(*[('45385', span(text, q)) for q in quotes]), list(participants))
        item = next(p for p in result.proposals if p.code == '45385' and p.bucket == 'selected')
        return item.status, item.units

    def test_a_failed_attempt_listed_beside_a_done_polypectomy_is_no_unit(self):
        """Cycle 2, the owner session's units defect: Corti's 45385 listed for the done polypectomy and for another
        polyp's failed attempt read READY with two units under the another-act release. With that release abandoned the
        cited failure holds the code for the reviewer, and its units, counted against the documented match before the
        hold, were one under cycle 2's units rule; cycle 3 abandons that rule, and the held code carries the group's two
        units, as the installed release counts them - never READY on them, in either listing order."""
        text = colon(self.DONE + '\n' + self.FAILED)
        self.assertEqual(self.units(text, (self.DONE, self.FAILED)), ('needs_clarification', 2))
        self.assertEqual(self.units(text, (self.FAILED, self.DONE)), ('needs_clarification', 2))
        # a participant citing the same passages adds no unit
        self.assertEqual(self.units(text, (self.DONE, self.FAILED), [read('astra', [code(text, '45385', self.FAILED)])]),
                         ('needs_clarification', 2))

    def test_two_done_polypectomies_listed_twice_are_two_units(self):
        """Cycle 2, units control: two cold snare polypectomies, each listed, stay two units."""
        text = colon(self.DONE + '\n' + self.DONE2)
        self.assertEqual(self.units(text, (self.DONE, self.DONE2)), ('ready', 2))

    def test_a_participant_alone_has_one_unit(self):
        """Cycle 2, units with Astra alone: a participant's admitted code is one entry, one unit, as before. Held until
        the walk round, because one of its passages is the failed attempt; that failure, cited beside the done
        polypectomy's own passage, is now set aside (engine._set_aside_attempts), and the one unit rests on the one
        documented act - READY."""
        text = colon(self.DONE + '\n' + self.FAILED)
        result = run(text, [], [read('astra', [code(text, '45385', self.DONE), code(text, '45385', self.FAILED)])])
        item = next(p for p in result.proposals if p.code == '45385' and p.bucket == 'selected')
        self.assertEqual((item.status, item.units), ('ready', 1))

    def test_an_entry_with_no_exact_passage_keeps_its_unit(self):
        """Cycle 2, units bounds: never fewer than one, and an entry with no exact passage keeps its unit (an empty test
        proves nothing); a code the documented service does not support keeps the group's size."""
        text = colon(self.DONE + '\n' + self.FAILED)
        failed = span(text, self.FAILED)
        unverifiable = EvidenceSpan(1, failed.start, failed.end, failed.text, True)  # points into another context
        group = [ProviderCode('selected', 'cpt', '45385', '', (failed,)),
                 ProviderCode('selected', 'cpt', '45385', '', (unverifiable,))]
        result = run(text, group)
        item = next(p for p in result.proposals if p.code == '45385' and p.bucket == 'selected')
        self.assertEqual(item.units, 2)  # the group's units (refutation cycle 3: no entry is dropped from the count)
        alone = colon(self.FAILED)
        result = run(alone, corti(('45385', span(alone, self.FAILED)), ('45385', span(alone, self.FAILED))))
        item = next(p for p in result.proposals if p.code == '45385' and p.bucket == 'selected')
        self.assertNotEqual(item.status, 'ready')
        self.assertEqual(item.units, 2)  # not supported: the group's size, held
