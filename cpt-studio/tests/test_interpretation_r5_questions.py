"""DECISIONS D126 (the Gemini migration's round-5 repair "questions2"; the review of round 4's "questions" patch, problems
0, 1, 3 and 4): which statements a held code's statement_scope question asks about, and how it quotes them.

- (0) D101 asked, of an act's several same-event contradictions, "the first resting on the target, else the first
  stored", so a same-site denial D102 makes a contradiction ("During withdrawal, no polypectomy was performed in the
  sigmoid colon.", its own time unanchored) beside the prior-segment denial was asked nowhere and shown nowhere, in
  either sentence order. The code's ONE question (FINAL 7.4) now asks every contradiction of the act, in a stated
  precedence: the act's same-site denials (the pairing table's target row reads the statement as the act's own target),
  then the target denials, then the others - stored order within each. Its events and passages are every one's.
- (1) D103 quoted the place that holds the status words: in a hard-wrapped document, one line ("No biopsy, snare
  resection, ablation, or balloon dilation was performed on"). It quotes the places that hold the status words and the
  target's and scope's own words - the whole sentence across the wrap; places apart are joined with an ellipsis.
- (3) A statement_scope question whose statement is no denial (a doubt's unresolved scope) keeps D86's wording - its
  statement_text, cut as before - on the code's arm and on focus_question's service arm. A denial's is quoted whole on
  both, as D103 built it.
- (4) D102 asked the contradiction of a technique relation whose two devices are both verified ("removed with a snare"
  beside "No cold snare was used for the 6 mm sessile polyp."): that is no doubt on the statement's side, and the
  relation keeps its technique question. (DECISIONS D143 (2) withdraws (4): the contradiction is asked again, as
  d353e64df asked it - tests/test_interpretation_r5c_questions.py.)

Only the question changes: status, bucket, READY and the exclusion are untouched. SYNTHETIC: the shared S08 builders
(tests.test_interpretation_events, tests.test_interpretation_identity) over fictional documents, in the shapes of the
review's inputs (FRESH-2 C2MEM-023 r1, FRESH-1 C2MEM-031 r3 with its scope words located, FRESH-2 C2MEM-031 r1).
Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events
from tests.test_interpretation_events import (COLONOSCOPE, POLYP, colonoscopy, exam, inventory, proposal, reached,
                                              removed, run)
from tests.test_interpretation_identity import a, act, les, sc, snare, tg
from tests.test_interpretation_r3_questions import sources
from tests.test_interpretation_r4_questions import (DEVICE, FRAMED, INCIDENTAL, PRIOR, SNARE, SNARE_WORDS, WITHDRAWAL,
                                                    device, framed, prior, relations_of)

DISTAL = 'No polypectomy was performed in the distal segment.'


def withdrawal(eid: str, pid: str) -> dict:
    """Finding 4's S2w (test_interpretation_r4_questions.sigmoid_denial with its time): a sigmoid denial whose own time
    ('During withdrawal') is no present-encounter frame - UNRESOLVED(time) beside the snare, whose own time is verified
    (D102) - and a SAME-SITE denial: the pairing table's target row reads its sigmoid colon as the snare's."""
    return act(eid, pid, 'removal', 'polypectomy', status='not_performed', status_words='no polypectomy was performed',
               time=a('current_encounter', 'During withdrawal', [pid]),
               scope=sc('single_target', 'in the sigmoid colon', [pid]),
               target=tg('', 'sigmoid_colon', 'sigmoid colon', [pid]))


def distal(eid: str, pid: str) -> dict:
    """A second target denial: 'the distal segment' names no landmark, so its rectum is unverified - UNRESOLVED(target,
    site_unresolved) beside the snare, as the prior-segment denial."""
    return act(eid, pid, 'removal', 'polypectomy', status='not_performed', status_words='No polypectomy was performed',
               scope=sc('single_target', 'No polypectomy was performed in the distal segment', [pid]),
               target=tg('', 'rectum', 'the distal segment', [pid]))


def incidental(eid: str, pid: str) -> dict:
    """FRESH-2 C2MEM-031 r2's statement about other findings (an intervention that "required no therapy", its target not
    stated): UNRESOLVED(scope, scope_unresolved) - a contradiction of neither kind above."""
    return act(eid, pid, 'intervention', 'therapy', status='not_performed', status_words='required no therapy',
               scope=sc('single_target', 'Nonbleeding rectal vascular ectasia, mild sigmoid diverticulosis, and small '
                                         'internal hemorrhoids', [pid]))


BUILD = {'withdrawal': (withdrawal, WITHDRAWAL), 'prior': (prior, PRIOR), 'framed': (framed, FRAMED),
         'device': (device, DEVICE), 'distal': (distal, DISTAL), 'incidental': (incidental, INCIDENTAL)}


def snare_beside(*names) -> tuple:
    """(inventory, text): the colonoscopy to the cecum (E1, P1), the sigmoid cold snare 45385 cites (E2, P2), then the
    statements ``names`` in sentence order (E3/P3, E4/P4, ...), listed in document order."""
    lines, more = {}, []
    for index, name in enumerate(names):
        maker, line = BUILD[name]
        lines[f'P{3 + index}'] = line
        more.append(maker(f'E{3 + index}', f'P{3 + index}'))
    return colonoscopy(*more, lines=lines)


def eid_of(names, name: str) -> str:
    return f'E{3 + names.index(name)}'


class Asks(SimpleTestCase):
    def assert_asks(self, p, said, act: str = SNARE, words: str = SNARE_WORDS):
        """Held, unresolved, its one question whether any of ``said`` - each quoted whole, in that order - applies to the
        act, and its reason naming each."""
        self.assertEqual((p.bucket, p.status, [c.fact for c in p.clarifications], p.support['reason']),
                         ('selected', 'needs_clarification', ['statement_scope'], events.UNRESOLVED))
        quoted = [f'“{item}”' for item in said]
        either = quoted[0] if len(quoted) == 1 else ', '.join(quoted[:-1]) + ' or ' + quoted[-1]
        both = quoted[0] if len(quoted) == 1 else ', '.join(quoted[:-1]) + ' and ' + quoted[-1]
        self.assertEqual(p.clarifications[0].question, f'Does {either} apply to the {act} {words}')
        if len(quoted) == 1:
            self.assertEqual(p.clarifications[0].reason, f'The document states {both}; CPT Studio could not confirm '
                                                         f'from the document whether that statement applies to the '
                                                         f'{act}.')
        else:
            self.assertEqual(p.clarifications[0].reason, f'The document states {both}; CPT Studio could not confirm '
                                                         f'from the document whether those statements apply to the '
                                                         f'{act}.')


# --- D126 (0): every same-event contradiction of the act, in a stated precedence ------------------------------------

class D126EveryContradiction(Asks):
    """Problem 0: D101's target-first tie-break hid a same-site contradiction D102 asks."""

    def test_d126_a_same_site_denial_is_asked_first_beside_a_target_denial_in_either_order(self):
        # the review's input: S2w (its own time unanchored, the sigmoid colon its place) and C1CL3-001's prior-segment
        # denial. 437b708bb and d353e64df asked the prior-segment sentence alone and showed S2w nowhere, in both orders
        for names in (('withdrawal', 'prior'), ('prior', 'withdrawal')):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                attributes = {eid_of(names, 'withdrawal'): ('time', 'time_unresolved'),
                              eid_of(names, 'prior'): ('target', 'site_unresolved')}
                self.assertEqual(relations_of(inv), [(eid, 'E2') + attributes[eid] for eid in ('E3', 'E4')])
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
                self.assert_asks(p, [WITHDRAWAL, PRIOR])
                self.assertEqual(p.support['question_events'],
                                 ['E2', eid_of(names, 'withdrawal'), eid_of(names, 'prior')])
                for sentence in (WITHDRAWAL, PRIOR, POLYP):
                    self.assertIn(sentence, sources(p))
        # alone, each asks its own statement, as before
        for name, said in (('withdrawal', WITHDRAWAL), ('prior', PRIOR)):
            with self.subTest(alone=name):
                inv, text = snare_beside(name)
                self.assert_asks(proposal(run(inv, text, [('45385', POLYP)]), '45385'), [said])

    def test_d126_the_precedence_is_same_site_then_target_then_the_rest(self):
        # stored against the precedence: the statement about other findings (scope), the prior-segment denial (target),
        # S2w (the same site)
        names = ('incidental', 'prior', 'withdrawal')
        inv, text = snare_beside(*names)
        self.assertEqual([item[2] for item in relations_of(inv)], ['scope', 'target', 'time'])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_asks(p, [WITHDRAWAL, PRIOR, INCIDENTAL])
        self.assertEqual(p.support['question_events'], ['E2', 'E5', 'E4', 'E3'])
        self.assertEqual([text for text in sources(p) if text != POLYP], [WITHDRAWAL, PRIOR, INCIDENTAL])

    def test_d126_finding_3s_target_denial_is_asked_in_every_order(self):
        # finding 3's inputs, which D101 repaired: the prior-segment denial is never dropped; the framed denial (every
        # polypectomy of the session) and the device denial (the snare's own lesion) are the act's same-site denials
        for names, first in ((('framed', 'prior'), FRAMED), (('prior', 'framed'), FRAMED),
                             (('device', 'prior'), DEVICE), (('prior', 'device'), DEVICE)):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
                self.assert_asks(p, [first, PRIOR])
                other = 'framed' if first == FRAMED else 'device'
                self.assertEqual(p.support['question_events'], ['E2', eid_of(names, other), eid_of(names, 'prior')])
                self.assertIn(PRIOR, sources(p))
                self.assertIn(first, sources(p))

    def test_d126_two_target_denials_are_both_asked_in_the_stored_order(self):
        # D101 asked the first target denial and showed the second nowhere
        for names, said in ((('prior', 'distal'), [PRIOR, DISTAL]), (('distal', 'prior'), [DISTAL, PRIOR])):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                self.assertEqual([item[2] for item in relations_of(inv)], ['target', 'target'])
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
                self.assert_asks(p, said)
                self.assertEqual(p.support['question_events'], ['E2', 'E3', 'E4'])
                self.assertIn(DISTAL, sources(p))

    def test_d126_two_same_site_denials_ask_in_the_stored_order(self):
        # D101's tie (its residual (d)): both are asked now, the first stored first
        for names, said in ((('framed', 'device'), [FRAMED, DEVICE]), (('device', 'framed'), [DEVICE, FRAMED])):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                self.assert_asks(proposal(run(inv, text, [('45385', POLYP)]), '45385'), said)

    def test_d126_one_sentence_two_denials_is_quoted_once(self):
        # two denials Gemini reads from one sentence (FRESH-2 C2MEM-023 r1 reads four from one): the sentence is asked
        # about once, and both events are the question's
        line = 'No polypectomy or snare resection was performed in the prior segment.'
        removal = act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                      status_words='No polypectomy or snare resection was performed',
                      scope=sc('single_target', 'in the prior segment', ['P3']),
                      target=tg('', 'sigmoid_colon', 'the prior segment', ['P3']))
        resection = act('E4', 'P3', 'snare', 'snare resection', status='not_performed',
                        status_words='No polypectomy or snare resection was performed',
                        scope=sc('single_target', 'in the prior segment', ['P3']),
                        target=tg('', 'sigmoid_colon', 'the prior segment', ['P3']))
        inv, text = colonoscopy(removal, resection, lines={'P3': line})
        self.assertEqual([item[:3] for item in relations_of(inv)], [('E3', 'E2', 'target'), ('E4', 'E2', 'target')])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_asks(p, [line])
        self.assertEqual(p.support['question_events'], ['E2', 'E3', 'E4'])


# --- D126 (1): the statement's whole sentence, across a hard wrap ---------------------------------------------------

WRAP = ('No biopsy, snare resection, ablation, or balloon dilation was performed on',
        'this splenic-flexure lesion during the present encounter.')
FLEXURE_POLYP = 'A 9 mm polyp at the splenic flexure was removed with a cold snare.'


class D126TheWholeSentence(Asks):
    """Problem 1: in a hard-wrapped document D103 quoted one wrapped line."""

    def flexure(self):
        """FRESH-2 C2MEM-023 r1's shape: the denial's status words end one line and its target and scope words ("this
        splenic-flexure lesion") begin the next; it names a splenic-flexure lesion whose identity is not established,
        beside a snare at the splenic flexure - UNRESOLVED(target, identity_unresolved)."""
        polyp = les('L1', '9 mm polyp', 'P2', landmark='splenic_flexure', site_words='splenic flexure',
                    size_words='9 mm')
        other = les('L2', '17 mm non-granular splenic-flexure lesion', 'P5', landmark='splenic_flexure',
                    site_words='splenic-flexure', size_words='17 mm')
        lines = {'P1': COLONOSCOPE, 'P2': FLEXURE_POLYP, 'P3': WRAP[0], 'P4': WRAP[1],
                 'P5': 'A 17 mm non-granular splenic-flexure lesion was left in situ.'}
        act_ = snare('E2', 'P2', target=tg('L1', 'splenic_flexure', '9 mm polyp at the splenic flexure', ['P2']))
        denial = act('E3', 'P3', 'snare', 'snare resection', status='not_performed',
                     status_words='No biopsy, snare resection, ablation, or balloon dilation was performed',
                     target=tg('L2', 'splenic_flexure', 'this splenic-flexure lesion', ['P4']),
                     scope=sc('single_target', 'this splenic-flexure lesion', ['P4'], targets=['L2']),
                     time=a('current_encounter', 'during the present encounter', ['P4']))
        return inventory(lines, events=[exam(), act_, denial], lesions=[polyp, other], reach=[reached()])

    def test_d126_a_hard_wrapped_denial_is_quoted_as_its_one_sentence(self):
        inv, text = self.flexure()
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'target', 'identity_unresolved')])
        p = proposal(run(inv, text, [('45385', FLEXURE_POLYP)]), '45385')
        # d353e64df: 'Does “No biopsy, snare resection, ablation, or balloon dilation was performed on” apply ...'
        self.assert_asks(p, [' '.join(WRAP)], act='snare removal (cold snare) of the 9 mm polyp in the splenic flexure')
        # the prior-segment denial wrapped the same way
        lines = {'P3': 'No polypectomy was performed on', 'P4': 'the prior segment of the colon.'}
        wrapped = act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                      status_words='No polypectomy was performed',
                      scope=sc('single_target', 'the prior segment of the colon', ['P4']),
                      target=tg('', 'sigmoid_colon', 'the prior segment', ['P4']))
        inv, text = colonoscopy(wrapped, lines=lines)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'target', 'site_unresolved')])
        self.assert_asks(proposal(run(inv, text, [('45385', POLYP)]), '45385'),
                         ['No polypectomy was performed on the prior segment of the colon.'])

    def test_d126_the_service_question_reads_the_sentence_across_the_wrap(self):
        # FRESH-1 C2MEM-031 r3's shape, with the scope's words LOCATED on the next line: focus_question's
        # statement_scope question about an in_doubt biopsy beside a denial - a denial's, so quoted whole (D103), now
        # the whole sentence. (The recorded E17's scope words are unlocated and its target absent: DECISIONS D143 (3)
        # quotes its scope's own passages, test_d126_recorded_unlocated_scope_words_quote_the_scopes_own_passages.)
        lines = {'P1': COLONOSCOPE, 'P2': 'Biopsies were taken from the ileocolonic anastomosis with cold forceps.',
                 'P3': 'Random biopsies were collected for dysplasia surveillance; they were not taken from any',
                 'P4': 'polyp or lesion described below.'}
        biopsy = act('E2', 'P2', 'biopsy', 'Biopsies', status_words='were taken',
                     technique=a('cold_forceps', 'cold forceps', ['P2']),
                     target=tg('', 'anastomosis', 'ileocolonic anastomosis', ['P2']))
        denial = act('E3', 'P3', 'biopsy', 'biopsies', status='not_performed', status_words='were not taken',
                     scope=sc('single_target', 'polyp or lesion described below', ['P4']))
        inv, _ = inventory(lines, events=[exam(), biopsy, denial], reach=[reached()])
        reading = events.Reading.of(inv)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'scope', 'scope_unresolved')])
        question = events.focus_question(reading, reading.events['E2'])
        said = f'“{lines["P3"]} {lines["P4"]}”'
        self.assertEqual((question.fact, question.events), ('statement_scope', ('E2', 'E3')))
        self.assertEqual(question.question,
                         f'Does {said} apply to the forceps biopsy (cold forceps) at the anastomosis (“were taken”)?')
        self.assertTrue(question.reason.startswith(f'The document states {said};'), question.reason)

    def test_d126_recorded_unlocated_scope_words_quote_the_scopes_own_passages(self):
        # FRESH-1 C2MEM-031 r3's E17 as recorded - its target absent, its scope's words not in the document
        # (words_unlocated), its scope's passages this line and the next. D126 recorded it (residual 1: no place holds
        # a target's or scope's words, so the quote was the status words' line alone, as at d353e64df); DECISIONS D143
        # (3) quotes the scope's own passages whole, the sentence across the wrap
        lines = {'P1': COLONOSCOPE, 'P2': 'Biopsies were taken from the ileocolonic anastomosis with cold forceps.',
                 'P3': 'Random biopsies were collected for dysplasia surveillance; they were not taken from any',
                 'P4': 'polyp or lesion described below.'}
        biopsy = act('E2', 'P2', 'biopsy', 'Biopsies', status_words='were taken',
                     technique=a('cold_forceps', 'cold forceps', ['P2']),
                     target=tg('', 'anastomosis', 'ileocolonic anastomosis', ['P2']))
        denial = act('E3', 'P3', 'biopsy', 'biopsies', status='not_performed', status_words='were not taken',
                     scope=sc('single_target', 'any resected polyp or suspicious lesion', ['P3', 'P4']))
        inv, _ = inventory(lines, events=[exam(), biopsy, denial], reach=[reached()])
        reading = events.Reading.of(inv)
        scope = reading.events['E3']['scope']
        self.assertEqual((scope['state'], scope['words'], scope['passages']), ('unverified', None, ['P3', 'P4']))
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'scope', 'scope_unresolved')])
        question = events.focus_question(reading, reading.events['E2'])
        self.assertEqual(question.question, f'Does “{lines["P3"]} {lines["P4"]}” apply to the forceps biopsy (cold '
                                            'forceps) at the anastomosis (“were taken”)?')

    def test_d126_places_apart_are_joined_with_an_ellipsis(self):
        # FRESH-2 C2MEM-031 r1 E25's shape: the target's words are stated sentences away from the status words
        lines = {'P3': 'A second lesion was seen in the prior segment.', 'P4': 'The cecum was photographed.',
                 'P5': 'It was not removed.'}
        apart = act('E3', 'P5', 'removal', 'removed', status='not_performed', status_words='was not removed',
                    scope=sc('single_target', 'It was not removed', ['P5']),
                    target=tg('', 'sigmoid_colon', 'the prior segment', ['P3']))
        inv, text = colonoscopy(apart, lines=lines)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'target', 'site_unresolved')])
        self.assert_asks(proposal(run(inv, text, [('45385', POLYP)]), '45385'),
                         ['A second lesion was seen in the prior segment. … It was not removed.'])

    def test_d126_a_place_within_or_across_another_is_quoted_once(self):
        # _h3_whole_statement over stored places: a place inside another adds nothing; one overlapping or touching
        # another adds the rest of its own text; a line break away, a space
        sentence = 'No polypectomy was performed in the prior segment of the colon.'

        def reading(spans: dict) -> events.Reading:
            passages = [{'id': pid, 'state': 'located', 'spans': [{'start': s, 'end': e, 'text': t}]}
                        for pid, (s, e, t) in spans.items()]
            return events.Reading({'passages': passages, 'lesions': [], 'events': [], 'relations': []}, {})

        def statement(status: str, target: str, scope: str, words: dict) -> dict:
            return {'status': {'passages': [status], 'words': words['status']},
                    'target': {'passages': [target], 'words': words['target']},
                    'scope': {'passages': [scope], 'words': words['scope']}}

        at = {'status': {'start': 100, 'end': 128, 'text': sentence[:28]},
              'target': {'start': 132, 'end': 149, 'text': sentence[32:49]},
              'scope': {'start': 132, 'end': 163, 'text': sentence[32:]}}
        whole = (100, 163, sentence)
        cases = {
            # the status clause, and the sentence holding the target's and scope's words: the sentence once
            'within': ({'P1': (100, 128, sentence[:28]), 'P2': whole}, ('P1', 'P2', 'P2')),
            # the first half, and the second half overlapping it by "performed in"
            'across': ({'P1': (100, 128, sentence[:28]), 'P2': (119, 163, sentence[19:])}, ('P1', 'P2', 'P2')),
            # the first half, and the rest of the sentence beginning where it ends
            'touching': ({'P1': (100, 128, sentence[:28]), 'P2': (128, 163, sentence[28:])}, ('P1', 'P2', 'P2')),
            # two lines a line break apart
            'wrap': ({'P1': (100, 131, sentence[:31]), 'P2': (132, 163, sentence[32:])}, ('P1', 'P2', 'P2')),
        }
        for label, (spans, (status, target, scope)) in cases.items():
            with self.subTest(case=label):
                found = events._h3_whole_statement(reading(spans), statement(status, target, scope, at))
                self.assertEqual(found, sentence)


# --- D126 (3): a statement_scope question whose statement is no denial ---------------------------------------------

CLIP = 'Oozing at the biopsy site was controlled with a clip.'
DOUBT = ('It is unclear from the nursing record whether a second hemostatic clip was deployed at the biopsy site in the '
         'sigmoid colon before withdrawal, as the device log is incomplete.')
DOUBT_WORDS = ('It is unclear from the nursing record whether a second hemostatic clip was deployed at the biopsy site '
               'in the sigmoid colon before withdrawal')


class D126ADoubtsScopeQuestion(SimpleTestCase):
    """Problem 3: D103 quoted a doubt's statement_scope question whole too; D103 is about denials."""

    def doubt_beside_clip(self):
        """D86's boundary shape (test_interpretation_r3_questions.Boundaries.clip_beside): the hemostatic clip 45382 cites
        (E2), and a doubt about a clip whose scope names no target - UNRESOLVED(scope, scope_unresolved). It is no
        candidate of 45382, so h3 decides the code's question, and no denial, so it is no contradiction."""
        clip = act('E2', 'P2', 'clip', 'clip', status_words='was controlled with a clip',
                   purpose=a('hemostasis', 'Oozing at the biopsy site was controlled', ['P2']))
        doubt = act('E3', 'P3', 'clip', 'clip', status='uncertain', status_words=DOUBT_WORDS,
                    scope=sc('single_target', 'a second hemostatic clip', ['P3']))
        return inventory({'P1': COLONOSCOPE, 'P2': CLIP, 'P3': DOUBT}, events=[exam(), clip, doubt], reach=[reached()])

    def test_d126_a_doubts_scope_question_keeps_d86s_wording(self):
        inv, text = self.doubt_beside_clip()
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'scope', 'scope_unresolved')])
        p = proposal(run(inv, text, [('45382', CLIP)]), '45382')
        self.assertEqual((p.status, [c.fact for c in p.clarifications], p.support['reason']),
                         ('needs_clarification', ['statement_scope'], events.UNRESOLVED))
        # D86's wording: the doubt's status words (statement_text), cut at 120 and 140 - never its whole passage
        self.assertEqual(p.clarifications[0].question,
                         f'Does “{DOUBT_WORDS[:119]}…” apply to the bleeding control (“was controlled with a clip”)?')
        self.assertEqual(p.clarifications[0].reason,
                         f'The document states “{DOUBT_WORDS[:139]}…”; CPT Studio could not confirm from the document '
                         'whether that statement applies to the bleeding control.')
        self.assertEqual(p.support['question_events'], ['E2', 'E3'])

    def test_d126_the_service_question_of_a_doubts_scope_keeps_d86s_wording(self):
        inv, _ = self.doubt_beside_clip()
        reading = events.Reading.of(inv)
        question = events.focus_question(reading, reading.events['E2'])
        self.assertEqual((question.fact, question.events), ('statement_scope', ('E2', 'E3')))
        self.assertEqual(question.question,
                         f'Does “{DOUBT_WORDS[:119]}…” apply to the bleeding control (“was controlled with a clip”)?')
        # a denial in its place is quoted whole on the service arm too (D103, kept)
        denied = ('No second hemostatic clip was deployed at the biopsy site in the sigmoid colon before withdrawal, '
                  'according to the nursing record and the device log.')
        denial = act('E3', 'P3', 'clip', 'clip', status='not_performed',
                     status_words='No second hemostatic clip was deployed',
                     scope=sc('single_target', 'a second hemostatic clip', ['P3']))
        clip = act('E2', 'P2', 'clip', 'clip', status_words='was controlled with a clip',
                   purpose=a('hemostasis', 'Oozing at the biopsy site was controlled', ['P2']))
        inv, _ = inventory({'P1': COLONOSCOPE, 'P2': CLIP, 'P3': denied}, events=[exam(), clip, denial],
                           reach=[reached()])
        reading = events.Reading.of(inv)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'scope', 'scope_unresolved')])
        question = events.focus_question(reading, reading.events['E2'])
        self.assertEqual(question.question, f'Does “{denied}” apply to the bleeding control (“was controlled with a clip”)?')


# --- D126 (4): a technique relation whose two devices are both verified --------------------------------------------

SNARE_ONLY = 'A 6 mm sessile polyp in the sigmoid colon was removed with a snare.'
NO_COLD = 'No cold snare was used for the 6 mm sessile polyp.'
WIDER = 'snare removal of the 6 mm sessile polyp in the sigmoid colon'


def no_cold(eid: str = 'E3', pid: str = 'P3') -> dict:
    return act(eid, pid, 'snare', 'cold snare', status='not_performed', status_words='No cold snare was used',
               technique=a('cold_snare', 'cold snare', [pid]),
               scope=sc('single_target', 'the 6 mm sessile polyp', [pid], targets=['L1']),
               target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', [pid]))


class D126BothDevicesVerified(Asks):
    """Problem 4: D102's "the act's own value is usable" caught a technique relation whose devices are both verified.
    DECISIONS D143 (2) withdraws D126 (4): that relation asks the contradiction again, as d353e64df did."""

    def test_d126_a_technique_relation_whose_two_devices_are_verified_asks_the_contradiction(self):
        # the review's input: the act's snare (verified) is wider than the denial's cold snare (verified). D126 (4)
        # asked which technique was used; DECISIONS D143 (2): whether the denial applies to the snare removal
        polyp = removed(technique=a('snare', 'snare', ['P2']), status_words='was removed with a snare')
        inv, text = colonoscopy(no_cold(), lines={'P2': SNARE_ONLY, 'P3': NO_COLD}, polyp=polyp)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'technique', 'technique_unresolved')])
        reading = events.Reading.of(inv)
        self.assertTrue(events.usable(reading.events['E2'], 'technique'))
        self.assertTrue(events.usable(reading.events['E3'], 'technique'))
        p = proposal(run(inv, text, [('45385', SNARE_ONLY)]), '45385')
        self.assert_asks(p, [NO_COLD], act=WIDER, words='(“was removed with a snare”)?')
        # the statement's own device unverified is still the contradiction (D102, kept: note8 r3's shape)
        line = 'The EMR snare was not used on this polyp in the sigmoid colon.'
        denial = act('E3', 'P3', 'snare', 'snare', status='not_performed', status_words='was not used',
                     technique=a('hot_snare', 'EMR electrosurgical snare', ['P3']),
                     scope=sc('single_target', 'this polyp', ['P3'], targets=['L1']),
                     target=tg('L1', 'sigmoid_colon', 'this polyp in the sigmoid colon', ['P3']))
        inv, text = colonoscopy(denial, lines={'P3': line})
        self.assertFalse(events.usable(events.Reading.of(inv).events['E3'], 'technique'))
        self.assert_asks(proposal(run(inv, text, [('45385', POLYP)]), '45385'), [line])

    def test_d126_beside_a_target_denial_the_contradiction_is_the_question(self):
        # one question per code: the contradictions are asked (D101, D126 (0)) - since DECISIONS D143 (2) the
        # technique denial is one of them again (the act's own lesion: a same-site denial, first), then the
        # prior-segment denial; under D126 (4) it was no contradiction and was not among the statements
        polyp = removed(technique=a('snare', 'snare', ['P2']), status_words='was removed with a snare')
        inv, text = colonoscopy(no_cold(), prior('E4', 'P4'), lines={'P2': SNARE_ONLY, 'P3': NO_COLD, 'P4': PRIOR},
                                polyp=polyp)
        self.assertEqual([item[2] for item in relations_of(inv)], ['technique', 'target'])
        p = proposal(run(inv, text, [('45385', SNARE_ONLY)]), '45385')
        self.assert_asks(p, [NO_COLD, PRIOR], act=WIDER, words='(“was removed with a snare”)?')
        self.assertEqual(p.support['question_events'], ['E2', 'E3', 'E4'])
