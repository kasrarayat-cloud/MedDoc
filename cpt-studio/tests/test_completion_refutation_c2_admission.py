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
    """engine._matched_acts_plain: the another-act release (a doubt in the cited passage about another act of the code's
    kinds moves off the code) stands only where the readers read the matched act plainly - the routing-era reading of its
    own evidence and of the reader's sentence holding it, every act the reader leaves undone lying in a cited passage, and
    every act mention and predicate the reader reads elsewhere in the service done or silent. Cycle 1's window cut at a
    raw '.' or newline and its hedge word list are gone."""

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
        the same in either order, and an unrelated "Possible ..." finding no longer holds the removed polyp (cycle 1's
        window read the next sentence's "attempted" or "Possible" as doubt about it)."""
        for label, body in (('removed, then the attempt', self.B + ' ' + self.P1),
                            ('the attempt, then removed', self.P1 + ' ' + self.B),
                            ('an unrelated possible finding', self.B + ' Possible diverticulosis was noted in the '
                                                                       'sigmoid colon.\n' + self.P1)):
            text = colon(body)
            for who, result in three_ways(text, '45385', self.P1).items():
                with self.subTest(label, who=who):
                    self.assertEqual(outcome(result, '45385')['45385'][:2], READY)

    def test_the_pinned_controls_stay_ready(self):
        """Cycle 2, admission D1 controls (the cycle-1 pinned another-act controls): another polyp plainly removed is
        READY whoever cites the failed attempt, and with the plainly removed polyp's own passage cited beside it."""
        for body in (self.P1 + '\n' + self.B, self.B + '\n' + self.P1):
            text = colon(body)
            for who, result in three_ways(text, '45385', self.P1).items():
                with self.subTest(body[:20], who=who):
                    self.assertEqual(outcome(result, '45385')['45385'][:2], READY)
            joint = run(text, corti(('45385', span(text, self.P1))), [read('astra', [code(text, '45385', self.B)])])
            self.assertEqual(outcome(joint, '45385')['45385'][:2], READY)

    def test_a_doubt_the_reader_binds_to_no_act_holds_too(self):
        """Cycle 2, admission D1 (the class, beyond the lens's variants; found by the builder): a later sentence whose
        act predicate the documented-service reader reads in doubt or of another occasion, though it binds it to no act,
        holds; an unrelated done act does not (the base held all three)."""
        for body, expected in (('It is unknown whether the polyp was removed.', HELD),
                               ('This was done at her colonoscopy in 2023.', HELD),
                               ('Cold forceps biopsies of the rectum were taken.', READY)):
            text = colon(self.P1 + '\n' + self.B + ' ' + body)
            with self.subTest(body):
                result = run(text, corti(('45385', span(text, self.P1))))
                self.assertEqual(outcome(result, '45385')['45385'][:2], expected)

    def test_an_act_the_inventory_leaves_undone_holds_whatever_its_clause_reads(self):
        """Cycle 2, admission D1 (the inventory's own reading, the release's first test): an act the documented-service
        reader's inventory leaves undone outside the cited passages holds the release even where its clause, read alone,
        says it was done - the inventory's final status, not a second reading of its words, decides. (No document the
        reader builds was found where this differs from the reading of each mention; the pin is on the rule itself.)"""
        from dataclasses import replace as replaced
        from studio.gi import detect, services as gi_services
        from studio.types import Span
        from studio.validation import checks
        from tests.test_harness_engine import DAY
        text = colon(self.P1 + '\n' + self.B)
        inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY), context_facts=None,
                                      pages=())
        found = reconcile.match('45385', inventory, inventory.services[0].family)
        cited = checks.evidence_readings(text, [span(text, self.P1)], DAY)
        self.assertTrue(engine._matched_acts_plain(found, text, DAY, (), cited))
        at = text.index(ADVANCED)
        undone = gi_services.Act(id='S1-X1', service=found.service.id, kind='biopsy', status='uncertain',
                                 role='physician', evidence=(Span(at, at + len(ADVANCED), ADVANCED),),
                                 cues=('uncertain: a status this pin gives it',))
        held = replaced(found, service=replaced(found.service, acts=found.service.acts + (undone,)))
        self.assertFalse(engine._matched_acts_plain(held, text, DAY, (), cited))

    def test_an_upper_endoscopy_reads_the_same(self):
        """Cycle 2, admission D1 and D5 in another GI family: an EGD snare code beside a failed attempt at another
        gastric polyp - READY in either order, held where the removed polyp is hedged."""
        p1 = ('Hot snare polypectomy of a 15 mm pedunculated polyp in the gastric body was attempted, but the snare could '
              'not be closed around the stalk, and the polyp was left in place.')
        done = 'A 6 mm polyp in the gastric antrum was removed with a cold snare.'
        hedged = ('A 6 mm polyp in the gastric antrum was removed with a cold snare, but it is\nunclear whether the polyp '
                  'was removed or only biopsied.')
        for body, expected in ((p1 + '\n' + done, READY), (done + ' ' + p1, READY), (p1 + '\n' + hedged, HELD)):
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
    """engine._stated_not_done for a removal kind: excluded only where the service records its lesions and the reader
    states every one of them not removed today (services.NOT_REMOVED); otherwise held. Cycle 1's early return on any
    removal word before the statement is gone."""

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
                     'A 20 mm sessile polyp was found in the sigmoid colon. The polyp was left in place.',
                     'A 10 mm polyp was found in the sigmoid colon and was left in place for surgical resection.'):
            text = colon(body + '\n' + self.FAIL)
            for who, result in three_ways(text, '45385', self.FAIL, base=('45378', span(text, ADVANCED))).items():
                with self.subTest(body, who=who):
                    got = outcome(result, '45385', '45378')
                    self.assertEqual(got['45385'][:2], EXCLUDED)
                    self.assertEqual(got['45378'][:2], READY)
                    item = next(p for p in result.proposals if p.code == '45385' and p.bucket == 'excluded')
                    self.assertIn(self.FAIL, item.exclusion_reason)
                    self.assertTrue(item.reinstatable)

    def test_a_lesion_only_seen_or_unread_holds(self):
        """Cycle 2, admission D4 and D7 ("not performed" needs supporting documentation): a failure beside a lesion the
        reader only records as seen, beside removed stool or another polyp taken with forceps, or with no lesion the
        reader records, establishes nothing about removal - held, the base's reading."""
        for body in ('A 9 mm pedunculated polyp in the sigmoid colon was seen.\nHot snare polypectomy failed.',
                     'Liquid stool was suctioned and removed from the right colon.\n' + self.FAIL,
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
    """engine._supported_units: an entry of the proposal provider's group whose every exact passage lies on an act of
    the code's kinds that the reader does not read as done, and none on a matched act, is no unit."""

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
        polyp's failed attempt is READY with one unit, in either listing order (it read READY with two)."""
        text = colon(self.DONE + '\n' + self.FAILED)
        self.assertEqual(self.units(text, (self.DONE, self.FAILED)), ('ready', 1))
        self.assertEqual(self.units(text, (self.FAILED, self.DONE)), ('ready', 1))
        # a participant citing the same passages adds no unit
        self.assertEqual(self.units(text, (self.DONE, self.FAILED), [read('astra', [code(text, '45385', self.FAILED)])]),
                         ('ready', 1))

    def test_two_done_polypectomies_listed_twice_are_two_units(self):
        """Cycle 2, units control: two cold snare polypectomies, each listed, stay two units."""
        text = colon(self.DONE + '\n' + self.DONE2)
        self.assertEqual(self.units(text, (self.DONE, self.DONE2)), ('ready', 2))

    def test_a_participant_alone_has_one_unit(self):
        """Cycle 2, units with Astra alone: a participant's admitted code is one entry, one unit, as before."""
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
        self.assertEqual(item.units, 1)  # the failed attempt's entry is no unit; the unverifiable one keeps its unit
        alone = colon(self.FAILED)
        result = run(alone, corti(('45385', span(alone, self.FAILED)), ('45385', span(alone, self.FAILED))))
        item = next(p for p in result.proposals if p.code == '45385' and p.bucket == 'selected')
        self.assertNotEqual(item.status, 'ready')
        self.assertEqual(item.units, 2)  # not supported: the group's size, held
