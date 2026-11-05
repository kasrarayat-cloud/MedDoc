"""Refutation round 7, the narrow pass the clinical-path gate requires over de6418fc6..84a48c2f1 (round 6, the owner's
D10/D12 meaning check and the session's D14): the findings it reproduced (refute-harness-r7, each verified in
verify-harness-r7), on their own inputs.

- d14-1, d14-2, display-4: the assess stage traced every prefetched code a proposal row carried, so a participant's
  alternative - never a proposal (D14) - was traced beside Corti's codes. Corti's 45378 card then listed the CMS
  endoscopy-family rule and passages pairing it with the participant's 45385 (in the reviewed TXT too, beside its own
  "No other selected code shares an endoscopic base relationship with 45378"), and reference validation counted the
  alternative as a code checked against the CMS reference files ("Done 1 code checked" where Corti proposed none).
  Only the proposal provider's codes are traced now (jobs._retrieval): Corti's retrieval and reference validation are
  the participants-disabled run's, and a participant's alternative has no retrieval.
- d14-3, display-3: participants.summary's closing sentence (checks.PARTICIPANTS_NEVER_DECIDE) is the engine's rule:
  a provider code excluded for scope or evidence carries no participant's code, and a code in no code's shape is
  counted and never listed.
- display-1, falsegreen-1: a service only a participant reads as performed is worded with the inventory's not-done
  reading of its family only where routing reads it inside the quoted passage - every not-done status named there,
  never a reading of another passage.
- display-2: the participants-only blocker and panel say who gave the codes, never "independent".
- display-5: a participant alternative's rationale never calls its verbatim quote an evidence passage.
- display-6: the source panel never titles "Evidence for" a provider passage its chip says does not show the coded act.
- parity-1: the Final status row's note never says an assessment of the current revision was made where none was.

parity-2 is pinned in ops/test_install_r5_sends.py (TheAccessCheckRequestCountTests), falsegreen-2 in
tests/test_harness2_r6_trace.py (EntryWordingTests) and falsegreen-3 in tests/test_harness2_r6_meaning.py
(D14PipelineTests.test_n1); the page's display-6 and parity-1 branches in the `// refutation round 7` block of
tests/frontend/app.test.cjs. The paths with no participant configured are unchanged (I1): with none configured the
traced codes are exactly the prefetched ones, and tests/test_harness_engine_parity.py and CortiOnlyParityTests pin them.
Synthetic data only; nothing is sent: Corti is the suite's in-process fake read by the real normaliser, and Astra and
Fable are the real replay adapters on the real tool loop (tests.test_harness2_pipeline).

Refutation round 8 amended three of these rules (tests/test_harness2_r8.py): only the codes of the proposals a reviewer
can decide are traced, never an alternative's, the provider's second review's included (retrieval-1, retrieval-2); a
participant's quote is worded with the documented-service reading's own located reading of it, never routing's
(wording-1, wording-2, wording-5; display-1's banding pin below moved with it); and the participants-only blocker and
panel never say "not the provider" (wording-3, page-3).
"""
import json
import re
from html import unescape
from unittest import mock

from django.test import SimpleTestCase

from studio import jobs, models, review
from tests import test_harness2_pipeline as hp
from tests import test_harness2_r6_meaning as r6m
from tests import test_harness2_r6_row as r6row
from tests import test_pipeline_api
from tests.test_harness2_r2_evidence import page
from tests.test_harness2_r2_wording import browser
from tests.test_harness_engine import code, corti, read, run, service, span
from tests.test_pipeline_api import drain

ACK = review.ACKNOWLEDGEMENTS['human']


def participant(p):
    return (p.get('support') or {}).get('origin') == 'participant'


def corti_retrieval(detail):
    """Each of Corti's proposals' retrieval, as the API serves it on its card, by key."""
    return {p['key']: p['retrieval'] for p in r6m.proposals(detail) if not participant(p)}


# --- d14-1, d14-2, display-4: a participant's code is never traced --------------------------------------------------

def with_candidate(value, quote):
    """Corti's fake answer with ``value`` also listed as a candidate citing ``quote``, in Corti's own shape."""
    real = test_pipeline_api.corti_like_response

    def answer(text, selections):
        data = json.loads(real(text, selections))
        start = text.index(quote)
        data['candidates'] = [{'system': 'cpt', 'code': value, 'display': 'UNVERIFIED PROVIDER WORDING',
                               'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(quote),
                                              'text': quote}], 'alternatives': []}]
        return json.dumps(data).encode()
    return mock.patch('tests.test_pipeline_api.corti_like_response', answer)


FAMILY_LOOKUP = 'is the endoscopic base of 45385'
FAMILY_PAIR = '45378, 45385 are one endoscopic family'


class RetrievalTests(r6m.MeaningCase):
    def assert_as_alone(self, text, corti=(), **participants):
        """The input through the pipeline with Astra and Fable configured: each of Corti's proposals has the retrieval
        it has with no participant configured, reference validation is that run's, and no participant's alternative
        has any."""
        encounter_id = self.scenario(text, corti, **participants)
        detail = self.detail(encounter_id)
        self.assertEqual(detail['harness']['phase'], 2)
        alone = self.corti_alone(text, corti)
        self.assertEqual(corti_retrieval(detail), corti_retrieval(alone))
        self.assertEqual(detail['harness']['reference_validation'], alone['harness']['reference_validation'])
        listed = [p for p in r6m.proposals(detail) if participant(p)]
        self.assertTrue(listed)
        for item in listed:
            self.assertEqual((item['bucket'], item['retrieval']), ('alternative', []), item['code'])
        return encounter_id, detail

    def assert_no_family_rule(self, encounter_id, detail, kind='draft'):
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '45378' and not participant(p)]
        self.assertFalse([entry for entry in item['retrieval'] if 'endoscopy' in entry['label']], item['retrieval'])
        card = browser(f'visible(cardOf(page(), {json.dumps(item["id"])}))', detail)
        self.assertNotIn('ncci.endoscopy', card)
        report = self.download(encounter_id, kind)
        self.assertNotIn(FAMILY_LOOKUP, report)
        self.assertNotIn(FAMILY_PAIR, report)
        trace = '\n'.join(self.trace_lines(self.trace(encounter_id)))
        self.assertNotIn(FAMILY_LOOKUP, trace)

    def time_2(self, **participants):
        """d14-1: time-2's own input - Corti's 45378 on the cecum sentence, a participant's 45385 on the history line.
        One variant per test: a workspace reuses an identical participant request's answer (jobs._retained_answer)."""
        encounter_id, detail = self.assert_as_alone(r6m.earlier(r6m.LAST_LABEL), [('45378', r6m.CECUM_LANDMARKS)],
                                                    **participants)
        self.assertEqual(detail['harness']['reference_validation']['codes_checked'], 1)
        self.assert_no_family_rule(encounter_id, detail)
        return detail

    def test_time_2_p4_astra_s_first_reading(self):
        self.time_2(astra=hp.reading(codes=[('45385', r6m.LAST_LABEL)], services=[r6m.colon_service(r6m.LAST_LABEL)]))

    def test_time_2_p6_fable_s_peer_review(self):
        detail = self.time_2(fable_peer=hp.peer_answer(codes=[('45385', r6m.LAST_LABEL)]))
        (item,) = [p for p in r6m.proposals(detail) if participant(p)]
        self.assertEqual((item['code'], item['phases']), ('45385', {'fable': 'peer_review'}))

    def test_n1_in_the_reviewed_report(self):
        """d14-1: N1 - Astra's 45385 on "Hot snare polypectomy failed." - with Corti's 45378 approved: the reviewed
        report a reviewer signs lists no CMS rule pairing 45378 with a code no proposal carries."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r6m.FAILED)
        encounter_id, detail = self.assert_as_alone(text, [('45378', r6m.CECUM)],
                                                    astra=hp.reading(codes=[('45385', r6m.FAILED)]))
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '45378']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        detail = self.detail(encounter_id)
        self.assertTrue(detail['readiness']['reviewed'], detail['readiness'])
        self.assert_no_family_rule(encounter_id, detail, 'reviewed')

    def test_time_1_p1_no_code_is_counted_as_checked(self):
        """d14-2, display-4: Corti selects nothing and Astra's 45385 is the only code listed - an alternative, never
        checked - so reference validation reads as with Corti alone: not run, never "Done 1 code checked"."""
        text = r6m.earlier(r6m.LAST_LABEL)
        _, detail = self.assert_as_alone(
            text, astra=hp.reading(codes=[('45385', r6m.LAST_LABEL)], services=[r6m.colon_service(r6m.LAST_LABEL)]))
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked'], block['passages']), ('not_run', 0, 0))
        row = browser('rowOf(page(), "data-participant", "reference_validation")', detail)
        self.assertIn('No proposal was checked against the CMS references for this revision.', row)
        self.assertNotIn('checked against the CMS reference files', row)

    def test_an_hcpcs_code_beside_corti_s(self):
        """d14-2: Astra's G0121 - outside the GI profiles, an alternative - was counted as a second code checked."""
        self.assert_as_alone(r6m.COLON, [('45378', r6m.CECUM)], astra=hp.reading(codes=[('G0121', r6m.CECUM)]))

    def test_a_corti_candidate_beside_a_participant_s_copy(self):
        """d14-1: a code Corti lists without selecting it is never looked up, and a participant's copy of it changed
        that (its row and the alternative each had the code's facts and passages, and 45378 the family rule)."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r6m.FAILED)
        with with_candidate('45385', r6m.SEEN):
            encounter_id, detail = self.assert_as_alone(text, [('45378', r6m.CECUM)],
                                                        astra=hp.reading(codes=[('45385', r6m.FAILED)]))
        rows = sorted((p['key'].split(':')[0], p['code'], p['retrieval']) for p in r6m.proposals(detail)
                      if p['code'] == '45385')
        self.assertEqual(rows, [('alt', '45385', []), ('altp', '45385', [])])
        self.assert_no_family_rule(encounter_id, detail)


# --- d14-3, display-3: participants.summary's closing sentence ------------------------------------------------------

def inexact(index, value):
    """Corti's fake answer with the evidence of its ``index``-th code rewritten to a passage the text does not hold at
    its position, so the real normaliser reads it as no exact source evidence."""
    real = test_pipeline_api.corti_like_response

    def answer(text, selections):
        data = json.loads(real(text, selections))
        self_code = data['codes'][index]
        assert self_code['code'] == value, self_code
        self_code['evidences'] = [{'contextIndex': 0, 'start': 0, 'end': 9, 'text': 'Not text.'}]
        return json.dumps(data).encode()
    return mock.patch('tests.test_pipeline_api.corti_like_response', answer)


class SummarySentenceTests(r6m.MeaningCase):
    def assert_closing(self, detail):
        self.assertTrue(self.summary(detail).endswith(f' {r6m.NEVER_DECIDE}'), self.summary(detail))

    def test_a_code_in_no_code_s_shape_is_counted_and_never_listed(self):
        """d14-3: 'W/LES(S)' is counted, never listed, beside a sentence that said every other code a participant
        gives is listed as an alternative."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r6m.FAILED)
        encounter_id = self.scenario(text, [('45378', r6m.CECUM)],
                                     astra=hp.reading(codes=[('45385', r6m.FAILED), ('W/LES(S)', r6m.CECUM)]))
        detail = self.detail(encounter_id)
        self.assertEqual([(p['code'], p['bucket']) for p in r6m.proposals(detail)],
                         [('45378', 'selected'), ('45385', 'alternative')])
        self.assertIn('It returned 1 code that cannot be listed', self.summary(detail))
        self.assertIn('one in neither shape is counted and never listed', self.summary(detail))
        self.assert_closing(detail)
        self.assertNotIn('W/LES(S)', json.dumps(r6m.proposals(detail)))
        self.assertIn(r6m.NEVER_DECIDE, self.download(encounter_id))

    def test_a_provider_code_excluded_for_evidence_or_scope_carries_no_participant_s_code(self):
        """display-3 (b): Corti's 45385 with no exact passage is excluded, and Astra's 45385 stands apart from it - a
        code the provider also proposed, which the sentence had said is judged on the provider's passages; and the same
        of an HCPCS code Corti selected, which is outside the GI profiles. HARNESS.md P-ADMIT (2026-11-05): Astra's
        45385, on the snare sentence, is admitted (D14 had listed it); its HCPCS code stays listed."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, 'The polyp was removed with a hot snare.')
        with inexact(1, '45385'):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM), ('45385', r6m.SEEN)],
                                         astra=hp.reading(codes=[('45385', 'The polyp was removed with a hot snare.')]))
        detail = self.detail(encounter_id)
        self.assertEqual(sorted((p['code'], p['bucket'], participant(p)) for p in r6m.proposals(detail)),
                         [('45378', 'selected', False), ('45385', 'excluded', False), ('45385', 'selected', True)])
        self.assert_closing(detail)
        encounter_id = self.scenario(r6m.COLON, [('45378', r6m.CECUM), ('G0121', r6m.CECUM)],
                                     astra=hp.reading(codes=[('G0121', r6m.CECUM)]))
        detail = self.detail(encounter_id)
        self.assertEqual(sorted((p['code'], p['bucket'], participant(p)) for p in r6m.proposals(detail)),
                         [('45378', 'selected', False), ('G0121', 'alternative', True), ('G0121', 'excluded', False)])
        self.assert_closing(detail)


# --- display-1, falsegreen-1: what a participant's quote of a service is said to be read as -------------------------

IN_QUOTE = (('planned', 'An upper endoscopy is planned in six weeks.'),
            ('historical', 'An upper endoscopy was performed in 2019.'),
            ('cancelled', 'The upper endoscopy was cancelled.'))
ELSEWHERE = 'The stomach and duodenum were also examined and were normal.'
PLAN_LINE = 'Plan: Upper endoscopy in 6 months.'
BANDED = 'Two internal hemorrhoids were banded.'
CAPSULE_PLAN = 'Plan: Capsule endoscopy next month.'
# moved by refutation round 10 (wording-2): the fallback says only what makes the service missing, true of every input
# (it was 'that the documented-service reading does not read as performed', false beside a quote of an act's words)
NOT_READ = 'where the documented-service reading reads no performed service of that kind'


def named(status, line):
    return (f'Astra reads a performed upper endoscopy where the documented-service reading reads the upper endoscopy as '
            f'{status} (“{line}”)')


def named_check(status, line):
    return (f'Astra reads a performed upper endoscopy (“{line}”), where the documented-service reading reads the upper '
            f'endoscopy as {status}. The documented-service reading reads no performed service of that kind, so coding '
            'completeness is incomplete.')


class MissingServiceReadingTests(SimpleTestCase):
    def engine(self, text, family, quote):
        return run(text, corti(('45378', span(text, r6m.CECUM))),
                   [read('astra', [code(text, '45378', r6m.CECUM)],
                         services=[service(text, 'colonoscopy', r6m.CECUM), service(text, family, quote)])])

    def test_each_not_done_reading_inside_the_quote_is_named(self):
        """falsegreen-1: the pins named only 'negated', so a rule naming nothing else passed the whole suite."""
        for status, line in IN_QUOTE:
            with self.subTest(status):
                text = r6m.doc(r6m.COLON, line)
                result = self.engine(text, 'egd', line)
                self.assertEqual([(s['family'], s['status']) for s in result.services['services']],
                                 [('gi.colonoscopy', 'performed'), ('gi.egd', status)])
                (entry,) = result.completeness['participant_services']
                self.assertEqual((entry['reason'], entry['read_as']), (named(status, line), f'the upper endoscopy as '
                                                                                             f'{status}'))
                check = next(c for c in result.encounter_checks if c.id == 'participants.services')
                self.assertEqual(check.detail, named_check(status, line))
                self.assertNotIn(NOT_READ, json.dumps(result.completeness))

    def test_a_reading_of_another_passage_is_never_attached_to_the_quote(self):
        """display-1: the inventory's planned upper endoscopy - read from the Plan line - was named beside Astra's quote
        of another sentence; and for a family of many kinds, another service's kind and time ("the capsule endoscopy as
        planned") beside a banding quote. Moved by refutation round 8 (wording-5): the banding quote is the inventory's
        own performed band ligation of the colonoscopy, which the reason named - "does not read as performed" was
        false of it - and the capsule plan, another passage's reading, is still never named beside it. Moved again by
        round 10 (wording-2 to wording-5): no act is named, and the fallback says only what makes the service missing,
        which is true here too."""
        banded = ''
        for name, lines, family, quote, label, documented, read_as in (
                ('the plan line', (ELSEWHERE, PLAN_LINE), 'egd', ELSEWHERE, 'upper endoscopy', 'gi.egd', ''),
                ('a capsule plan', (BANDED, CAPSULE_PLAN), 'other_gi', BANDED, 'other GI service', 'gi.capsule',
                 banded)):
            with self.subTest(name):
                text = r6m.doc(r6m.COLON, *lines)
                result = self.engine(text, family, quote)
                # the inventory still reads a service of that kind as planned - from the other passage
                self.assertIn((documented, 'planned'), [(s['family'], s['status'])
                                                        for s in result.services['services']])
                (entry,) = result.completeness['participant_services']
                reason = (f'Astra reads a performed {label} where the documented-service reading reads {read_as}'
                          if read_as else f'Astra reads a performed {label} {NOT_READ}')
                self.assertEqual((entry['reason'], entry['read_as']), (f'{reason} (“{quote}”)', read_as))
                self.assertNotIn('planned', entry['reason'])
                self.assertEqual(result.completeness['state'], 'incomplete')
                check = next(c for c in result.encounter_checks if c.id == 'participants.services')
                named_here = f', where the documented-service reading reads {read_as}' if read_as else ''
                self.assertEqual(check.detail, f'Astra reads a performed {label} (“{quote}”){named_here}. The '
                                               'documented-service reading reads no performed service of that kind, so '
                                               'coding completeness is incomplete.')


class MissingServiceReadingPipelineTests(r6m.MeaningCase):
    def missing(self, text, quote, family='egd'):
        services = [r6m.colon_service(r6m.CECUM), ('u1', family, 'performed', quote)]
        return self.scenario(text, [('45378', r6m.CECUM)],
                             astra=hp.reading(codes=[('45378', r6m.CECUM)], services=services),
                             fable=hp.reading(codes=[('45378', r6m.CECUM)], services=[r6m.colon_service(r6m.CECUM)]))

    def test_the_plan_line_s_reading_is_never_attached_to_another_quote_in_the_reviewed_report(self):
        """display-1, on the finding's input: the statement, the check and both reports - the reviewed one a reviewer
        signs - say only what is true of the quote."""
        encounter_id = self.missing(r6m.doc(r6m.COLON, ELSEWHERE, PLAN_LINE), ELSEWHERE)
        detail = self.detail(encounter_id)
        reason = f'Astra reads a performed upper endoscopy {NOT_READ} (“{ELSEWHERE}”)'
        self.assertEqual(detail['coding']['state'], 'incomplete')
        self.assertIn(reason, detail['coding']['statement'])
        check = next(c for c in detail['assessment']['encounter_checks'] if c['id'] == 'participants.services')
        self.assertNotIn('as planned', check['detail'])
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '45378']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind):
                report = self.download(encounter_id, kind)
                self.assertIn(reason, report)
                self.assertNotIn('reads the upper endoscopy as planned', report)

    def test_a_reading_inside_the_quote_is_named_on_every_surface(self):
        for status, line in IN_QUOTE:
            with self.subTest(status):
                encounter_id = self.missing(r6m.doc(r6m.COLON, line), line)
                detail = self.detail(encounter_id)
                self.assertIn(named(status, line), detail['coding']['statement'])
                self.assertIn(named(status, line), self.download(encounter_id))
                check = next(c for c in detail['assessment']['encounter_checks'] if c['id'] == 'participants.services')
                self.assertEqual(check['detail'], named_check(status, line))


# --- display-2: whose the listed codes are, never "independent" -----------------------------------------------------

class PeerOnlyBlockerTests(r6m.MeaningCase):
    assert_blocker = r6m.D14BlockerTests.assert_blocker

    def test_a_code_first_given_in_peer_review(self):
        """time-1's peer variant: Corti selects nothing, both first readings are empty, and Fable's peer review adds
        45385 on the history line - "proposed after peer review, never independent" on the same page."""
        encounter_id = self.scenario(r6m.earlier(r6m.LAST_LABEL),
                                     fable_peer=hp.peer_answer(codes=[('45385', r6m.LAST_LABEL)]))
        detail = self.assert_blocker(encounter_id, r6m.PARTICIPANTS_ONLY, 'independent')
        self.assertEqual([(p['code'], p['bucket'], p['phases']) for p in r6m.proposals(detail)],
                         [('45385', 'alternative', {'fable': 'peer_review'})])
        lines = self.page_lines(detail)
        # moved by refutation round 8 (wording-3, page-3): never "not the provider" (it was "... given by Astra or
        # Fable, not the provider, and is offered only as an alternative.")
        self.assertIn('No code is selected for approval. Each code listed below was given by Astra or Fable and is '
                      'offered only as an alternative.', lines)
        self.assertIn('Codes it proposed after peer review, never independent: 45385.', lines)
        self.assertFalse(any("independent participant's" in line for line in lines), lines)


# --- display-5: a participant's verbatim quote is never called an evidence passage ----------------------------------

class AlternativeRationaleTests(r6m.MeaningCase):
    def test_n1_the_failed_act_s_sentence(self):
        encounter_id = self.scenario(r6m.doc(r6m.COLON, r6m.SEEN, r6m.FAILED), [('45378', r6m.CECUM)],
                                     astra=hp.reading(codes=[('45385', r6m.FAILED)]))
        (item,) = [p for p in r6m.proposals(self.detail(encounter_id)) if p['code'] == '45385']
        self.assertEqual([e['text'] for e in item['evidence']], [r6m.FAILED])
        self.assertTrue(item['rationale'].endswith('Informational only. 1 passage of the document quoted verbatim.'),
                        item['rationale'])
        self.assertNotIn('evidence passage', item['rationale'])
        # HARNESS.md P-ADMIT (2026-11-05): the failed act's sentence accounts for nothing left open, and its reason says
        # so (D14's reason before)
        said = r6m.not_added_reason(item['exclusion_reason'])
        self.assertTrue(said, item['exclusion_reason'])
        self.assertIn(said, item['rationale'])


# --- display-6: a provider passage that does not show the coded act is never titled evidence for it -----------------

SNARED = 'The polyp was removed with a hot snare.'


class ProviderPassageTitleTests(r6m.MeaningCase):
    def assert_titled(self, detail):
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '45385']
        self.assertEqual((item['status'], item['support']['reason'], item['support']['unrelated']), ('ready', 'service',
                                                                                                    [0]))
        card = browser(f'visible(cardOf(page(), {json.dumps(item["id"])}))', detail)
        self.assertIn(f'“{r6m.SEEN}” — cited by the provider; does not show the coded act', card)
        titles = {text: title for keys, title, text in r6m.marks(detail) if any(k.startswith(f'{item["id"]}:')
                                                                                 for k in keys)}
        # the finding: 'Evidence for 45385', beside that chip
        self.assertEqual(titles, {r6m.SEEN: 'Passage the provider cited for 45385, which does not show the coded act',
                                  SNARED: 'Evidence for 45385'})

    def test_corti_alone_and_with_participants(self):
        """display-6's input, on the installed Corti-only page and with participants: Corti's Ready 45385 cites only
        the "was seen" sentence; the snare sentence is the act's own source passage."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, SNARED)
        self.assert_titled(self.corti_alone(text, [('45385', r6m.SEEN)]))
        self.assert_titled(self.detail(self.scenario(text, [('45385', r6m.SEEN)])))


# --- parity-1: the Final status row's note with no assessment of this revision --------------------------------------

def final_notes(html):
    at = html.index('data-participant="final"')
    start = html.rindex('<div class="check-item', 0, at)
    end = html.find('<div class="check-item', at)
    row = html[start:end if end > 0 else len(html)]
    return [unescape(note) for note in re.findall(r'<small class="check-source">(.*?)</small>', row)]


NONE_MADE = ['No assessment of this revision was made.']
COMING = ['The peer reviews and the second assessment follow the first assessment.']


class FinalRowTests(r6row.StaleMixin, r6m.MeaningCase):
    """R6-ROW's input (TWO_EXTENTS, ColonCase's participants), without ColonCase's own tests."""
    corti_codes = (('45385', hp.SNARE), ('45380', hp.BIOPSY))

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [hp.answered('astra', hp.ASTRA_COLON)]
        self.adapters['fable'].first = [hp.answered('fable', hp.FABLE_COLON)]
        self.adapters['astra'].peer = [hp.answers_extent('astra')]
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(codes=[('45378', hp.LAND)]), number=2)]

    def test_the_addendum_window_busy_then_stopped(self):
        encounter_id = self.create(hp.TWO_EXTENTS)
        drain()
        before = self.detail(encounter_id)
        self.assertEqual(final_notes(page(before)), ['Assessed after peer review: both phases reconciled from source '
                                                     'evidence and rules, never by counting agreement.'])
        codes = {p['id']: p['code'] for p in before['assessment']['proposals']}
        (question,) = [item for item in before['clarifications'] if item['state'] == 'open'
                       and item['fact'] == 'extent' and codes.get(item['proposal_id']) == '45385']
        self.addendum(encounter_id, question['id'])
        busy = self.detail(encounter_id)
        self.assertEqual((busy['pipeline']['busy'], busy['harness']['clarification']), (True, {'open': None}))
        self.assertEqual(final_notes(page(busy)), COMING)
        self.stop(encounter_id)
        stopped = self.detail(encounter_id)
        self.assertEqual((stopped['state'], stopped['revision']['number'], stopped['harness']['phase'],
                          stopped['harness']['clarification']), ('stopped', 2, 1, {'open': None}))
        # the served assessment is revision 1's, which read both peer reviews
        self.assertIsNone(review.live_assessment(self.encounter(encounter_id)))
        # the finding: ['Assessed from the frozen first readings; no peer review was read by this assessment.']
        self.assertEqual(final_notes(page(stopped)), NONE_MADE)

    def test_stopped_before_the_first_assessment(self):
        encounter_id = self.create(hp.TWO_EXTENTS)
        job = jobs.claim_next()
        self.assertEqual(job.kind, 'extract')
        jobs.run_job(job)
        self.stop(encounter_id)
        stopped = self.detail(encounter_id)
        self.assertEqual((stopped['state'], stopped['assessment'], stopped['harness']['phase']), ('stopped', None, 1))
        self.assertFalse(models.Assessment.objects.filter(encounter_id=encounter_id).exists())
        self.assertEqual(final_notes(page(stopped)), NONE_MADE)
