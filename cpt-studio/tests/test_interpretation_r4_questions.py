"""DECISIONS D101, D102 and D103 (the Gemini migration's round-4 repair "questions"; the round-4 refutation of
437b708bb, findings 3, 4 and 6): which UNRESOLVED relation a held code asks about, which side of it is unknown, and what
its statement_scope question quotes. Finding 5 is RECORDED, not repaired: its pins are the last class here.

- D101 (finding 3): events._h3_unresolved read only an act's FIRST UNRESOLVED relation. C1CL3-001's denial ("No
  polypectomy was performed in the prior segment.") listed after a framed earlier denial ("These were the findings at
  her index colonoscopy: no polypectomy was performed.") or after a denial of another device ("Neither the EMR
  electrosurgical snare nor cautery was used to treat this polyp.") was never asked and never shown: 45385 asked the
  snare's own verified time or technique. EVERY relation is now read: a same-event contradiction is the code's question
  in any stored order, the one resting on the target first.
- D102 (finding 4): D91 narrowed D86 by the relation's ATTRIBUTE. A denial whose OWN time, performer, device or session
  is the unknown side ("During withdrawal, no polypectomy was performed in the sigmoid colon.", its time unanchored)
  made 45385 ask the snare's own verified time, with the reason "could not confirm from the document when the snare
  removal ... was done". On those attributes the SIDE now decides: the act's own value usable - the contradiction
  (statement_scope); the act's own value unusable - that attribute's question (D91). A status, kind or part_of relation
  keeps performed_status (D91).
- D103 (finding 6): the statement_scope question quoted only the statement's status words ("required no therapy", "not
  treated", "not examined endoscopically"), so a statement about other findings read as a denial of the act. It quotes
  the statement whole: the passage its status words are stated in, uncut.

Only the question changes: status, bucket, READY and the exclusion are untouched. SYNTHETIC: the shared S08 builders
(tests.test_interpretation_events, tests.test_interpretation_identity), fictional documents. RECORDED: the committed
FRESH-2 run 1 of fb07 (tests/fixtures/interpretation), read and assessed as score_fresh.py does
(test_interpretation_r3_questions.recorded), citing every code its expectations name. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events, wording
from tests.test_interpretation_events import (COLONOSCOPE, L1, POLYP, colonoscopy, exam, inventory, proposal, reached,
                                              removed, run)
from tests.test_interpretation_identity import a, act, sc, tg
from tests.test_interpretation_r3_questions import recorded, sources, unresolved

SNARE = 'snare removal (cold snare) of the 6 mm sessile polyp in the sigmoid colon'
SNARE_WORDS = '(“was removed with a cold snare”)?'
FRAMED = 'These were the findings at her index colonoscopy: no polypectomy was performed.'
PRIOR = 'No polypectomy was performed in the prior segment.'
DEVICE = 'Neither the EMR electrosurgical snare nor cautery was used to treat this polyp.'


def framed(eid: str, pid: str) -> dict:
    """Finding 3's framed denial: its current time is worded by the framing sentence, so it is current_unanchored -
    UNRESOLVED(time) beside the snare, whose own time is verified."""
    return act(eid, pid, 'removal', 'polypectomy', status='not_performed', status_words='no polypectomy was performed',
               time=a('current_encounter', 'These were the findings at her index colonoscopy', [pid]),
               scope=sc('all_of_kind', 'no polypectomy', [pid]))


def prior(eid: str, pid: str) -> dict:
    """C1CL3-001's denial: its target is a sigmoid colon its words ("the prior segment") never name - UNRESOLVED(target,
    site_unresolved) beside the snare."""
    return act(eid, pid, 'removal', 'polypectomy', status='not_performed', status_words='No polypectomy was performed',
               scope=sc('single_target', 'No polypectomy was performed in the prior segment', [pid]),
               target=tg('', 'sigmoid_colon', 'the prior segment', [pid]))


def device(eid: str, pid: str) -> dict:
    """Finding 3's S4 denial (note8 r3's shape): a hot snare worded 'cautery' (device_missing, unverified) on the same
    polyp - UNRESOLVED(technique) beside the snare's verified cold snare."""
    return act(eid, pid, 'snare', 'EMR electrosurgical snare', status='not_performed',
               status_words='Neither the EMR electrosurgical snare nor cautery was used',
               technique=a('hot_snare', 'cautery', [pid]),
               scope=sc('single_target', 'this polyp', [pid]), target=tg('L1', 'sigmoid_colon', 'this polyp', [pid]))


BUILD = {'framed': (framed, FRAMED), 'prior': (prior, PRIOR), 'device': (device, DEVICE)}


def snare_beside(*names, polyp=None) -> tuple:
    """(inventory, text) of the colonoscopy to the cecum (E1, P1) and the sigmoid cold snare 45385 cites (E2, P2), with
    the statements ``names`` after them in sentence order (E3/P3, E4/P4, ...), listed in document order."""
    lines, more = {}, []
    for index, name in enumerate(names):
        maker, line = BUILD[name]
        pid, eid = f'P{3 + index}', f'E{3 + index}'
        lines[pid] = line
        more.append(maker(eid, pid))
    return colonoscopy(*more, lines=lines, polyp=polyp)


def relations_of(inv) -> list:
    """(statement, event, attribute, reason) of every UNRESOLVED relation, in stored order."""
    return [item[:4] for item in unresolved(inv)]


class Held(SimpleTestCase):
    def assert_scope(self, p, said: str, act: str = SNARE, words: str = SNARE_WORDS):
        """Held, unresolved, its one question whether ``said`` - quoted whole - applies to the act."""
        self.assertEqual((p.bucket, p.status, [c.fact for c in p.clarifications], p.support['reason']),
                         ('selected', 'needs_clarification', ['statement_scope'], events.UNRESOLVED))
        question, reason = p.clarifications[0].question, p.clarifications[0].reason
        self.assertEqual(question, f'Does “{said}” apply to the {act} {words}')
        self.assertEqual(reason, f'The document states “{said}”; CPT Studio could not confirm from the document '
                                 f'whether that statement applies to the {act}.')


# --- D101: every UNRESOLVED relation of the act is read --------------------------------------------------------------

class D101EveryRelation(Held):
    """Finding 3: a same-event contradiction is the code's question whatever order its relation was stored in."""

    def test_d101_the_prior_segment_denial_after_a_framed_denials_time_relation_is_the_question(self):
        # the finding's input: the framed denial (UNRESOLVED(time)) is stored before the prior-segment denial
        inv, text = snare_beside('framed', 'prior')
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'time', 'time_unresolved'),
                                             ('E4', 'E2', 'target', 'site_unresolved')])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, PRIOR)
        self.assertEqual(p.support['question_events'], ['E2', 'E4'])
        self.assertIn(PRIOR, sources(p))  # shown: at 437b708bb this sentence appeared nowhere in the assessment

    def test_d101_the_prior_segment_denial_after_a_device_denial_is_the_question(self):
        # the finding's S4: the device denial (UNRESOLVED(technique)) is stored before the prior-segment denial
        inv, text = snare_beside('device', 'prior')
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'technique', 'technique_unresolved'),
                                             ('E4', 'E2', 'target', 'site_unresolved')])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, PRIOR)
        self.assertEqual(p.support['question_events'], ['E2', 'E4'])
        self.assertIn(PRIOR, sources(p))

    def test_d101_the_question_is_the_same_in_every_sentence_order(self):
        for names in (('framed', 'prior'), ('prior', 'framed'), ('device', 'prior'), ('prior', 'device')):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
                self.assert_scope(p, PRIOR)
                self.assertIn(PRIOR, sources(p))

    CLIP = 'Oozing at the biopsy site was controlled with a clip.'
    CLIP_DOUBT = 'It is unclear whether a clip was placed at her index colonoscopy.'
    NO_CLIP = 'No clip was placed in the prior segment.'

    def clip_and(self, *statements):
        """D86's boundary shape (test_interpretation_r3_questions.Boundaries.clip_beside): the hemostatic clip 45382
        cites (E2), and clip statements of no stated purpose - each meets it by their one Gemini kind and is no
        candidate of 45382, so FINAL 7.4 h2 never reads them and h3 decides the code's question."""
        clip = act('E2', 'P2', 'clip', 'clip', status_words='was controlled with a clip',
                   purpose=a('hemostasis', 'Oozing at the biopsy site was controlled', ['P2']))
        made = {'doubt': (lambda eid, pid: act(eid, pid, 'clip', 'clip', status='uncertain',
                                               status_words='It is unclear whether a clip was placed',
                                               scope=sc('all_of_kind', 'clip', [pid]), time=a('unknown')),
                          self.CLIP_DOUBT),
                'denial': (lambda eid, pid: act(eid, pid, 'clip', 'clip', status='not_performed',
                                                status_words='No clip was placed',
                                                scope=sc('single_target', 'in the prior segment', [pid]),
                                                target=tg('', 'sigmoid_colon', 'the prior segment', [pid])),
                           self.NO_CLIP)}
        lines, more = {'P1': COLONOSCOPE, 'P2': self.CLIP}, []
        for index, name in enumerate(statements):  # E3/P3, E4/P4, ... in sentence order
            maker, line = made[name]
            lines[f'P{3 + index}'] = line
            more.append(maker(f'E{3 + index}', f'P{3 + index}'))
        inv, text = inventory(lines, events=[exam(), clip, *more], reach=[reached()])
        return inv, proposal(run(inv, text, [('45382', self.CLIP)]), '45382')

    def test_d101_a_doubts_time_relation_stored_first_does_not_take_the_denials_question(self):
        # an aside's doubt (D86 keeps its own attribute's question when it is the only relation); stored first, it had
        # taken the code's one question from the prior-segment denial
        inv, p = self.clip_and('doubt', 'denial')
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'time', 'time_unresolved'),
                                             ('E4', 'E2', 'target', 'site_unresolved')])
        self.assert_scope(p, self.NO_CLIP, act='bleeding control', words='(“was controlled with a clip”)?')
        # alone, the doubt keeps the time question (D86's boundary)
        _, p = self.clip_and('doubt')
        self.assertEqual((p.status, [c.fact for c in p.clarifications]), ('needs_clarification', ['event_time']))

    def test_d101_a_contradiction_stored_after_the_acts_own_unknown_device_is_the_question(self):
        # the snare's own device is unverified (its words are not in its passage), so a denial naming a device leaves
        # UNRESOLVED(technique) on the act's side (C-16); the prior-segment denial names none and rests on the target
        polyp = removed(technique=a('cold_snare', 'cold snare', ['P1']))
        hot = act('E3', 'P3', 'snare', 'hot snare', status='not_performed', status_words='No hot snare was used',
                  technique=a('hot_snare', 'hot snare', ['P3']),
                  scope=sc('single_target', 'the 6 mm sessile polyp', ['P3'], targets=['L1']),
                  target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', ['P3']))
        line = 'No hot snare was used for the 6 mm sessile polyp.'
        inv, text = colonoscopy(hot, prior('E4', 'P4'), lines={'P3': line, 'P4': PRIOR}, polyp=polyp)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'technique', 'technique_unresolved'),
                                             ('E4', 'E2', 'target', 'site_unresolved')])
        self.assertFalse(events.usable(events.Reading.of(inv).events['E2'], 'technique'))
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, PRIOR, act='snare removal of the 6 mm sessile polyp in the sigmoid colon')
        # without the prior-segment denial, the act's own unknown device keeps the technique question (C-16, D91)
        inv, text = colonoscopy(hot, lines={'P3': line}, polyp=polyp)
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual((p.status, [c.fact for c in p.clarifications]), ('needs_clarification', ['technique']))

    def test_d101_two_contradictions_resting_on_no_target_ask_the_first_stored(self):
        # D101's tie: neither denial rests on the target (each on its own unknown side, D102), so the first stored is
        # asked - a statement_scope question in either order, quoting the sentence stored first
        for names, said in ((('framed', 'device'), FRAMED), (('device', 'framed'), DEVICE)):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                self.assertEqual([item[2] for item in relations_of(inv)],
                                 ['time', 'technique'] if names[0] == 'framed' else ['technique', 'time'])
                self.assert_scope(proposal(run(inv, text, [('45385', POLYP)]), '45385'), said)

    def test_d101_with_no_contradiction_the_first_relation_stored_keeps_its_question(self):
        # the snare's own time is unanchored ("During withdrawal"), so both denials' relations rest on the ACT's unknown
        # time: neither is a contradiction, and the first stored asks the act's time, as before
        line = 'During withdrawal, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        polyp = removed(time=a('current_encounter', 'During withdrawal', ['P2']))
        plain = act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                    status_words='No polypectomy was performed', scope=sc('all_of_kind', 'No polypectomy', ['P3']))
        inv, text = colonoscopy(plain, prior('E4', 'P4'), lines={'P2': line, 'P3': 'No polypectomy was performed.',
                                                                 'P4': PRIOR}, polyp=polyp)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'time', 'time_unresolved'),
                                             ('E4', 'E2', 'time', 'time_unresolved')])
        p = proposal(run(inv, text, [('45385', line)]), '45385')
        self.assertEqual((p.status, [c.fact for c in p.clarifications], p.support['question_events']),
                         ('needs_clarification', ['event_time'], ['E2', 'E3']))

    def test_d101_d102_the_service_question_of_an_event_no_code_depends_on_reads_the_first_relation(self):
        # FINAL 7.8's focus_question (code ''): D86's boundary stands - D101 and D102 are the code's question only
        inv, _ = snare_beside('framed', 'prior')
        reading = events.Reading.of(inv)
        question = events.focus_question(reading, reading.events['E2'])
        self.assertEqual((question.fact, question.events), ('event_time', ('E2', 'E3')))


# --- D102: which side of the relation is unknown ---------------------------------------------------------------------

WITHDRAWAL = 'During withdrawal, no polypectomy was performed in the sigmoid colon.'


def sigmoid_denial(**changes) -> dict:
    options = dict(status='not_performed', status_words='no polypectomy was performed',
                   scope=sc('single_target', 'in the sigmoid colon', ['P3']),
                   target=tg('', 'sigmoid_colon', 'sigmoid colon', ['P3']))
    options.update(changes)
    return act('E3', 'P3', 'removal', 'polypectomy', **options)


class D102TheStatementsSide(Held):
    """Finding 4: a denial whose own time, performer, device or session is the unknown side asks the contradiction."""

    def test_d102_a_denial_whose_own_time_is_unanchored_asks_the_contradiction(self):
        # the finding's S2w: 'During withdrawal' is no present-encounter frame, so the denial's time is unverified
        inv, text = colonoscopy(sigmoid_denial(time=a('current_encounter', 'During withdrawal', ['P3'])),
                                lines={'P3': WITHDRAWAL})
        reading = events.Reading.of(inv)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'time', 'time_unresolved')])
        self.assertTrue(events.usable(reading.events['E2'], 'time'))  # the snare's own time is verified
        self.assertFalse(events.usable(reading.events['E3'], 'time'))
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, WITHDRAWAL)
        self.assertNotIn('could not confirm from the document when', p.clarifications[0].reason)
        self.assertEqual(p.support['question_events'], ['E2', 'E3'])

    def test_d102_a_denial_whose_own_device_is_unverified_asks_the_contradiction(self):
        # note8 r3's shape (FRESH-2 A/note8 r3 45385 asked "Which technique was used for the snare removal (cold
        # snare)..." beside its verified cold snare): the denial names an EMR snare its own words do not state
        line = 'The EMR snare was not used on this polyp in the sigmoid colon.'
        denial = act('E3', 'P3', 'snare', 'snare', status='not_performed', status_words='was not used',
                     technique=a('hot_snare', 'EMR electrosurgical snare', ['P3']),
                     scope=sc('single_target', 'this polyp', ['P3'], targets=['L1']),
                     target=tg('L1', 'sigmoid_colon', 'this polyp in the sigmoid colon', ['P3']))
        inv, text = colonoscopy(denial, lines={'P3': line})
        reading = events.Reading.of(inv)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'technique', 'technique_unresolved')])
        self.assertTrue(events.usable(reading.events['E2'], 'technique'))
        self.assertFalse(events.usable(reading.events['E3'], 'technique'))
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, line)

    def test_d102_a_broad_denial_beside_two_examinations_asks_the_contradiction(self):
        # the finding's S3: two done colonoscopy examinations leave the session unresolved, so the broad denial rests on
        # the procedure (session_unresolved) - the snare's own procedure is verified
        lines = {'P1': COLONOSCOPE, 'P2': POLYP, 'P3': 'The colonoscope was reinserted and advanced to the cecum.',
                 'P4': 'No polypectomy was performed.'}
        broad = act('E4', 'P4', 'removal', 'polypectomy', status='not_performed',
                    status_words='No polypectomy was performed', scope=sc('all_of_kind', 'No polypectomy', ['P4']))
        inv, text = inventory(lines, events=[exam(), removed(), exam('E3', 'P3', status_words='was reinserted'), broad],
                              lesions=[L1], reach=[reached(), reached('E3', 'cecum', 'cecum', 'P3')])
        self.assertEqual(relations_of(inv), [('E4', 'E2', 'procedure', 'session_unresolved')])
        self.assertTrue(events.usable(events.Reading.of(inv).events['E2'], 'procedure'))
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        # the unresolved session's own extent question stays beside it
        self.assertEqual([c.fact for c in p.clarifications], ['statement_scope', 'extent'])
        self.assertEqual(p.clarifications[0].question, f'Does “No polypectomy was performed.” apply to the {SNARE} '
                                                       f'{SNARE_WORDS}')

    def test_d102_a_denial_whose_own_performer_is_unknown_asks_the_contradiction(self):
        line = 'No polypectomy was performed in the sigmoid colon.'
        inv, text = colonoscopy(sigmoid_denial(performer=a('unknown')), lines={'P3': line})
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'performer', 'performer_unresolved')])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, line)

    def test_d102_the_acts_own_unknown_keeps_its_attribute_question(self):
        # D91, kept: where the ACT's own value is the unusable one, its question asks what is really missing
        line = 'During withdrawal, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        plain = 'No polypectomy was performed in the sigmoid colon.'
        cases = {
            'event_time': (removed(time=a('current_encounter', 'During withdrawal', ['P2'])), sigmoid_denial(),
                           {'P2': line, 'P3': plain}, line, 'time'),
            'event_performer': (removed(performer=a('unknown')), sigmoid_denial(), {'P3': plain}, POLYP, 'performer'),
            'technique': (removed(technique=a('cold_snare', 'cold snare', ['P1'])),
                          act('E3', 'P3', 'snare', 'hot snare', status='not_performed',
                              status_words='No hot snare was used', technique=a('hot_snare', 'hot snare', ['P3']),
                              scope=sc('single_target', 'the 6 mm sessile polyp', ['P3'], targets=['L1']),
                              target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', ['P3'])),
                          {'P3': 'No hot snare was used for the 6 mm sessile polyp.'}, POLYP, 'technique'),
        }
        for fact, (polyp, denial, lines, cited, attribute) in cases.items():
            with self.subTest(fact=fact):
                inv, text = colonoscopy(denial, lines=lines, polyp=polyp)
                self.assertEqual([item[2] for item in relations_of(inv)], [attribute])
                self.assertFalse(events.usable(events.Reading.of(inv).events['E2'], attribute))
                p = proposal(run(inv, text, [('45385', cited)]), '45385')
                self.assertEqual((p.status, [c.fact for c in p.clarifications], p.support['reason']),
                                 ('needs_clarification', [fact], events.UNRESOLVED))

    def test_d102_a_status_or_kind_relation_keeps_performed_status(self):
        # D91, kept: Gemini's claimed contradiction whose statuses it opened, and a claim between two kinds
        base = dict(status='not_performed', status_words='No polyp was removed', scope=sc('all_of_kind', 'No', ['P3']))
        contradiction = {'about': 'contradiction', 'events': ['E2', 'E3'], 'lesions': [], 'passages': ['P2', 'P3']}
        claim = [{'event': 'E2', 'passages': ['P2', 'P3']}]
        cases = {
            'status': (act('E3', 'P3', 'removal', 'removed', contradicts=claim, **base), 'No polyp was removed.',
                       [contradiction]),
            'kind': (act('E3', 'P3', 'emr', 'EMR', status='not_performed', status_words='No EMR was performed',
                         scope=sc('all_of_kind', 'No', ['P3']), contradicts=claim), 'No EMR was performed.', []),
        }
        for attribute, (denial, line, questions) in cases.items():
            with self.subTest(attribute=attribute):
                inv, text = colonoscopy(denial, lines={'P3': line}, open_questions=questions)
                self.assertEqual([item[2] for item in relations_of(inv)], [attribute])
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
                self.assertEqual((p.status, [c.fact for c in p.clarifications]),
                                 ('needs_clarification', ['performed_status']))


# --- D103: the statement quoted whole --------------------------------------------------------------------------------

INCIDENTAL = ('Nonbleeding rectal vascular ectasia, mild sigmoid diverticulosis, and small internal hemorrhoids were '
              'incidental findings and required no therapy.')


class D103TheStatementWhole(Held):
    """Finding 6: a statement_scope question quotes the statement whole, never its status words alone."""

    def test_d103_a_statement_about_other_findings_is_quoted_whole_and_uncut(self):
        # FRESH-2 C2MEM-031 r2's statement (E39, 146 characters - longer than the 120 and 140 a quote used to be cut
        # at, which cut its denial off the end): an intervention that "required no therapy", whose target is not stated
        statement = act('E3', 'P3', 'intervention', 'therapy', status='not_performed',
                        status_words='required no therapy',
                        scope=sc('single_target', 'Nonbleeding rectal vascular ectasia, mild sigmoid diverticulosis, '
                                                  'and small internal hemorrhoids', ['P3']))
        inv, text = colonoscopy(statement, lines={'P3': INCIDENTAL})
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'scope', 'scope_unresolved')])
        self.assertGreater(len(INCIDENTAL), 140)
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, INCIDENTAL)
        self.assertNotIn('…', p.clarifications[0].question + p.clarifications[0].reason)

    def test_d103_a_limited_examination_is_quoted_as_the_document_states_it(self):
        # the finding's S5 (fb07's shape): the extent limitation is a not_performed examination with a target
        line = 'The terminal ileum was not examined.'
        limit = act('E3', 'P3', 'examination', 'examined', status='not_performed', status_words='was not examined',
                    scope=sc('single_target', 'The terminal ileum', ['P3']),
                    target=tg('', 'terminal_ileum', 'terminal ileum', ['P3']))
        inv, text = inventory({'P1': COLONOSCOPE, 'P3': line}, events=[exam(), limit], reach=[reached()])
        p = proposal(run(inv, text, [('45378', COLONOSCOPE)]), '45378')
        self.assert_scope(p, line, act='colonoscopy', words='(“was advanced”)?')

    def test_d103_fb07_r1_quotes_the_roux_limb_line_whole(self):
        # FRESH-2 fb07 r1, recorded: 43235 asked 'Does “not examined endoscopically” apply to the upper endoscopy'
        cited = [('43245', 'A wire-guided balloon was positioned across the stricture and inflated to 6, 7 and 8 mm.',
                  None),
                 ('43249', 'At the gastrojejunal anastomosis there was a tight stricture', None),
                 ('43248', 'A guidewire was passed through the stricture under direct vision into the Roux limb.',
                  None),
                 ('44360', 'only the guidewire entered the Roux limb', None),
                 ('43235', 'The gastroscope was advanced through a normal esophagus into the gastric pouch.', None)]
        _, result = recorded('fb07', cited)
        p = proposal(result, '43235')
        said = 'The Roux limb was therefore not examined endoscopically.'
        scope = [c for c in p.clarifications if c.fact == 'statement_scope']
        self.assertEqual((p.status, [c.fact for c in p.clarifications]),
                         ('needs_clarification', ['statement_scope', 'base_included']))
        self.assertTrue(scope[0].question.startswith(f'Does “{said}” apply to the upper endoscopy'), scope[0].question)
        self.assertTrue(scope[0].reason.startswith(f'The document states “{said}”;'), scope[0].reason)
        self.assertEqual(proposal(result, '43245').status, 'ready')  # nothing else moves

    def test_d103_status_words_not_located_quote_the_status_passage(self):
        # status words Gemini gave that are not in the document (words_unlocated): the statement is quoted by its
        # status's own passage, never its kind words
        line = 'No polypectomy was performed in the prior segment of the colon.'
        denial = prior('E3', 'P3')
        denial['status'] = a('not_performed', 'polypectomy was not done', ['P3'])
        inv, text = colonoscopy(denial, lines={'P3': line})
        status = events.Reading.of(inv).events['E3']['status']
        self.assertEqual((status['state'], status['words']), ('unverified', None))
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'target', 'site_unresolved')])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_scope(p, line)

    def test_d103_the_c10_question_keeps_its_cut(self):
        # wording.scope_question and scope_reason quote whole only for h3 (whole=True); ADJUDICATION C-10's question
        # (events._exclusion) is unchanged
        long = 'x' * 200
        self.assertIn('…', wording.scope_question(long, 'snare removal'))
        self.assertIn('…', wording.scope_reason(long, 'snare removal'))
        self.assertNotIn('…', wording.scope_question(long, 'snare removal', whole=True))
        self.assertNotIn('…', wording.scope_reason(long, 'snare removal', whole=True))


# --- finding 5, RECORDED (not repaired) -------------------------------------------------------------------------------

EGD_REACH = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
GJ = 'A tight stricture at the gastrojejunal anastomosis was dilated with a through-the-scope balloon to 12 mm.'
NO_ESOPHAGEAL = 'No dilation of the esophagus was performed.'


class Finding5Recorded(SimpleTestCase):
    """Finding 5 (D86's target arm displaces D29's site question of a site-specific dilation code) is recorded, not
    repaired: both codes stay held, and statement_scope asks the contradiction the installed release asks as
    conflict:dilation - now quoting the denial whole."""

    def test_finding_5_both_dilation_codes_stay_held_asking_the_denial(self):
        dilation = act('E2', 'G2', 'dilation', 'dilated', procedure=a('egd'),
                       target=tg('', 'anastomosis', 'gastrojejunal anastomosis', ['G2']),
                       technique=a('balloon', 'through-the-scope balloon', ['G2']))
        denial = act('E3', 'G3', 'dilation', 'dilation', status='not_performed',
                     status_words='No dilation of the esophagus was performed', procedure=a('egd'),
                     scope=sc('single_target', 'of the esophagus', ['G3']),
                     target=tg('', 'esophagus', 'esophagus', ['G3']))
        entry = {'state': 'altered', 'landmark': 'anastomosis', 'words': 'gastrojejunal anastomosis',
                 'passages': ['G2']}
        inv, text = inventory({'G1': EGD_REACH, 'G2': GJ, 'G3': NO_ESOPHAGEAL}, anatomy=[entry],
                              events=[exam('E1', 'G1', words='gastroscope', procedure=a('egd')), dilation, denial],
                              reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'G1')])
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'target', 'site_overlap')])
        result = run(inv, text, [('43249', GJ), ('43245', GJ)])
        for code in ('43249', '43245'):
            with self.subTest(code=code):
                p = proposal(result, code)
                self.assertEqual((p.bucket, p.status, [c.fact for c in p.clarifications]),
                                 ('selected', 'needs_clarification', ['statement_scope']))
                question = p.clarifications[0].question
                self.assertTrue(question.startswith(f'Does “{NO_ESOPHAGEAL}” apply to the dilation'), question)

