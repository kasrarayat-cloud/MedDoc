"""Refutation round 8, the narrow pass over round 7's repair commit (84a48c2f1..268921abe): the findings it reproduced
(refute-harness-r8, each verified in verify-harness-r8), on their own inputs.

- retrieval-1, retrieval-2: the assess stage traced every selection of the provider's, so a code its bounded second
  review selected and CPT Studio did not add - an alternative (alt2) - was traced, with Corti alone too: Corti's 45378
  card and the reviewed report listed the CMS endoscopy-family rule pairing it with that code, and reference validation
  read "Done 1 code checked" where no proposal could be decided on. Only the codes of the proposals a reviewer can
  decide are traced now (jobs._retrieval), and the API reads no other trace (serializers._reference_validation).
- retrieval-3: an alternative's card was joined by code to a decidable proposal's trace. An alternative's card lists no
  retrieval.
- wording-1, wording-2, wording-5: a service only a participant reads is worded with the documented-service reading's
  own reading of the quoted passage, from where that reading read each service mention (gi_services.build's
  ``located``): the inventory's not-done reading of the quote itself ("declined", "could not be performed", and every
  family routing does not route, which round 7's routing gate dropped), named by the mention's own kind (never "the
  peg" for a quoted upper endoscopy), and an act it reads as performed in the quote (a PEG, a banding, a dilation,
  which the fallback had said it does not read as performed). Refutation round 10 removed the act naming and worded the
  fallback as only what makes the service missing (tests/test_harness2_r10.py).
- wording-3, page-3: the participants-only blocker and panel never say "not the provider": a provider response refused
  whole, or a second review not yet read, can carry the same code. A refused provider response is said first.
- wording-4: participants.summary's closing sentence names merge's two kinds of proposal.
- page-1, page-2: one highlight that carries, for one code, both a passage that shows the coded act and a provider
  passage that does not is titled as overlapping passages of both kinds; the title pins cover a passing support too.

The page's branches are pinned in the `// refutation round 8` block of tests/frontend/app.test.cjs. With no participant
configured the engine's result is unchanged (I1): tests/test_harness_engine_parity.py and CortiOnlyParityTests pin it;
the traces and the API's reading of them are records beside it. Synthetic data only; nothing is sent: Corti is the
suite's in-process fake read by the real normaliser, and Astra and Fable are the real replay adapters on the real tool
loop (tests.test_harness2_pipeline).
"""
import json
from unittest import mock

from django.test import SimpleTestCase, override_settings

from studio import models, review, serializers
from studio.gi import context as gi_context
from studio.gi import detect
from studio.gi import services as gi_services
from tests import test_harness2_pipeline as hp
from tests import test_harness2_r6_meaning as r6m
from tests import test_harness2_r7 as r7
from tests import test_harness_engine as he
from tests import test_pipeline_api
from tests.legacy_chain import applied
from tests.test_harness2_r2_wording import browser
from tests.test_pipeline_api import drain

ACK = review.ACKNOWLEDGEMENTS['human']
OFF = dict(ASTRA_MODE='disabled', FABLE_MODE='disabled')

# --- retrieval-1, retrieval-2, retrieval-3: an alternative's code is never traced -----------------------------------

COMBINED = (hp.HEAD + 'Procedure report (fictional)\nDate of service: 2026-10-16\n'
            'Place of service: Hospital outpatient department\nProcedures: EGD and colonoscopy\n'
            'EGD: The gastroscope was advanced to the second portion of the duodenum. The mucosa was normal '
            'throughout.\nColonoscopy: The colonoscope was advanced to the cecum and the examination was completed. '
            'The colon was normal.\n')
GASTRO = 'The gastroscope was advanced to the second portion of the duodenum.'
NORMAL = 'The mucosa was normal throughout.'
EGD_ONLY = (hp.HEAD + 'Upper endoscopy report (fictional)\nDate of service: 2026-10-16\n'
            'Place of service: Hospital outpatient department\n'
            'The gastroscope was advanced to the second portion of the duodenum. The mucosa was normal throughout.\n')
NOT_CHECKED = 'No proposal was checked against the CMS references for this revision.'


def kind(p):
    return p['key'].split(':')[0]


def traced(encounter_id):
    return [entry.get('code') for entry in models.Encounter.objects.get(pk=encounter_id).current_assessment.retrieval]


@applied
class SecondReviewRetrievalTests(r6m.MeaningCase):
    assert_no_family_rule = r7.RetrievalTests.assert_no_family_rule

    def second(self, text, first, later, **participants):
        """``text`` through the pipeline with Corti selecting ``first``, then the bounded second review a reviewer asks
        for, answered with ``later``. Astra's and Fable's readings are ``participants``' (none by default)."""
        encounter_id = self.scenario(text, first, **participants)
        offered = self.detail(encounter_id)['second_review']
        self.assertTrue(offered['available'], offered)
        self.corti.selections = list(later)
        reply = self.client.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        detail = self.detail(encounter_id)
        self.assertEqual([r.purpose for r in models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                                                 provider='corti')
                          .order_by('created_at')], ['primary', 'second_review'])
        return encounter_id, detail

    def assert_the_second_review_s_alternative_untraced(self, encounter_id, detail):
        """retrieval-1: 45378 READY, the second review's 45385 an alternative (alt2) - only 45378 is traced and
        checked, and the reviewed report a reviewer signs lists no CMS rule pairing 45378 with 45385."""
        self.assertEqual(sorted((kind(p), p['code'], p['bucket']) for p in r6m.proposals(detail)),
                         [('alt2', '45385', 'alternative'), ('sel', '45378', 'selected')])
        self.assertEqual(traced(encounter_id), ['45378'])
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked']), ('done', 1))
        (alternative,) = [p for p in r6m.proposals(detail) if kind(p) == 'alt2']
        self.assertEqual(alternative['retrieval'], [])
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '45378']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        detail = self.detail(encounter_id)
        self.assertTrue(detail['readiness']['reviewed'], detail['readiness'])
        self.assert_no_family_rule(encounter_id, detail, 'reviewed')

    def test_retrieval_1_corti_alone(self):
        with override_settings(**OFF):
            encounter_id, detail = self.second(COMBINED, [('45378', r6m.CECUM)], [('45385', GASTRO)])
            self.assertEqual(detail['harness']['phase'], 0)
            self.assert_the_second_review_s_alternative_untraced(encounter_id, detail)

    def test_retrieval_1_with_participants(self):
        encounter_id, detail = self.second(COMBINED, [('45378', r6m.CECUM)], [('45385', GASTRO)])
        self.assertEqual(detail['harness']['phase'], 2)
        self.assert_the_second_review_s_alternative_untraced(encounter_id, detail)

    def assert_nothing_checked(self, encounter_id, detail):
        """retrieval-2: the only code listed is the second review's 43239, an alternative: no proposal can be decided
        on, so reference validation is not run - never "Done 1 code checked"."""
        self.assertEqual([(kind(p), p['code'], p['bucket']) for p in r6m.proposals(detail)],
                         [('alt2', '43239', 'alternative')])
        self.assertEqual(traced(encounter_id), [])
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked'], block['passages']), ('not_run', 0, 0))
        row = browser('rowOf(page(), "data-participant", "reference_validation")', detail)
        self.assertIn(NOT_CHECKED, row)
        self.assertNotIn('checked against the CMS reference files', row)

    def test_retrieval_2_corti_alone(self):
        with override_settings(**OFF):
            encounter_id, detail = self.second(EGD_ONLY, [], [('43239', NORMAL)])
            self.assert_nothing_checked(encounter_id, detail)

    def test_retrieval_2_with_participants(self):
        encounter_id, detail = self.second(EGD_ONLY, [], [('43239', NORMAL)])
        self.assert_nothing_checked(encounter_id, detail)

    def test_retrieval_2_a_recorded_trace_of_an_alternative_is_never_counted(self):
        """What the assess stage recorded for retrieval-2's input before this round - the alternative's own trace - is
        never read as a code checked: an assessment keeps the retrieval it recorded (HARNESS.md 9, I1)."""
        with override_settings(**OFF):
            encounter_id, _ = self.second(EGD_ONLY, [], [('43239', NORMAL)])
        # the stored assessment, its proposals (the one alternative) and its reference sources (a CMS file applies to
        # the date) as recorded, with the trace the assess stage recorded before this round in place of its own:
        # Assessment rows are immutable, so the reader is given it in memory
        assessment = models.Encounter.objects.get(pk=encounter_id).current_assessment
        self.assertTrue(serializers.source_applied(assessment.reference_sources))
        assessment.retrieval = [{'code': '43239', 'service_date': '2026-10-16',
                                 'facts': [{'source_key': hp.PFS_KEY, 'release': 'RVU26D', 'field': 'status',
                                            'value': 'A'}],
                                 'passages': [], 'lookups': ['reference lookup 43239'], 'notes': []}]
        block = serializers._reference_validation(assessment, False)
        self.assertEqual((block['state'], block['codes_checked'], block['passages'], block['sources']),
                         ('not_run', 0, 0, []))

    def test_retrieval_3_a_participant_s_copy_of_a_second_review_alternative(self):
        """retrieval-3 (b): Astra's 43239, the code the second review selected and CPT Studio did not add, has no
        retrieval on its card, and neither has the second review's own alternative. Moved by the completion repair
        (owner directive 2026-11-06, item 3: equal eligibility; builder Q1): a first reading's 43239 is admitted now - a
        proposal held as Corti's own selection of the passage is, which accounts for the upper endoscopy, so no second
        review is offered beside it - so Astra's alternative copy is a peer review's addition."""
        encounter_id, detail = self.second(COMBINED, [('45378', r6m.CECUM)], [('43239', GASTRO)],
                                           astra_peer=hp.peer_answer(codes=[('43239', GASTRO)]))
        rows = sorted((kind(p), p['code'], p['bucket'], p['retrieval']) for p in r6m.proposals(detail)
                      if p['code'] == '43239')
        self.assertEqual(rows, [('alt2', '43239', 'alternative', []), ('altp', '43239', 'alternative', [])])
        self.assertEqual(traced(encounter_id), ['45378'])

    def test_retrieval_3_a_participant_s_copy_of_corti_s_code_excluded_for_evidence(self):
        """retrieval-3 (a): Corti's 45378 has no exact passage and is excluded; Astra's 45378 stands apart from it,
        and had carried the excluded code's 12 facts and passages beside its own "No CMS reference check ran". Moved by
        refutation round 9 (retrieval-1): a code excluded with no reinstatement is no code a reviewer can decide, so it
        is not traced either, with Corti alone or with participants (its card kept 12 facts and passages). HARNESS.md
        P-ADMIT (2026-11-05): Astra's 45378 accounts for the colonoscopy left without a proposal and is admitted (D14 had
        listed it), so it is a code a reviewer decides, and it alone is traced - never the excluded one's."""
        text = r6m.doc(r6m.COLON, r6m.SEEN)
        with r7.inexact(0, '45378'):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM)], astra=hp.reading(codes=[('45378', r6m.CECUM)]))
            detail = self.detail(encounter_id)
            alone = self.corti_alone(text, [('45378', r6m.CECUM)])
        rows = {kind(p): p for p in r6m.proposals(detail)}
        self.assertEqual(sorted((key, p['bucket'], p['reinstatable']) for key, p in rows.items()),
                         [('exc', 'excluded', False), ('sel', 'selected', False)])
        (excluded,) = [p for p in r6m.proposals(alone) if kind(p) == 'exc']
        self.assertEqual((rows['exc']['retrieval'], excluded['retrieval']), ([], []))
        self.assertEqual(traced(encounter_id), ['45378'])


# --- wording-1, wording-2, wording-5: what a participant's quote of a service is said to be read as -----------------

def reason(label, read_as, quote):
    return (f'Astra reads a performed {label} where the documented-service reading reads {read_as} (“{quote}”)'
            if read_as else f'Astra reads a performed {label} {r7.NOT_READ} (“{quote}”)')


def check_detail(label, read_as, quote):
    named = f', where the documented-service reading reads {read_as}' if read_as else ''
    return (f'Astra reads a performed {label} (“{quote}”){named}. The documented-service reading reads no performed '
            'service of that kind, so coding completeness is incomplete.')


# (the line appended, the participant's family, its label, the reading named) - wording-1's lines: each the document's
# only mention of its family, read by the inventory as not done; round 7 had named none of them
NOT_DONE_HERE = (
    ('The patient declined EGD.', 'egd', 'upper endoscopy', 'the upper endoscopy as cancelled'),
    ('The patient refused EGD.', 'egd', 'upper endoscopy', 'the upper endoscopy as cancelled'),
    ('Upper endoscopy could not be performed.', 'egd', 'upper endoscopy', 'the upper endoscopy as negated'),
    ('Plan: capsule endoscopy in 6 months.', 'other_gi', 'other GI service', 'the capsule endoscopy as planned'),
    ('Esophageal manometry was not performed.', 'other_gi', 'other GI service', 'the manometry as negated'),
    ('Esophageal pH monitoring was cancelled.', 'other_gi', 'other GI service',
     'the pH / impedance study as cancelled'),
    ('Plan: push enteroscopy next month.', 'other_gi', 'other GI service', 'the enteroscopy as planned'),
)
# wording-2: a PEG line, then the quoted upper-endoscopy line, read alike
PEG_FIRST = (('planned', 'PEG tube placement is planned next month.', 'An upper endoscopy is planned in six weeks.'),
             ('historical', 'Status post PEG tube placement in 2024.', 'Prior upper endoscopy in 2019 was normal.'),
             ('negated', 'No PEG tube was placed.', 'An upper endoscopy was not performed.'),
             ('cancelled', 'The PEG tube placement was cancelled.', 'The upper endoscopy was cancelled.'))
# found while repairing wording-2: the inventory reads this line itself as uncertain; its service's 'planned' is the PEG
# plan line's, another passage (round 7's routing gate named it, as round 6 did: routing reads the line as planned)
REPEAT = 'Repeat upper endoscopy in 6 weeks.'
PEG_PLAN = 'Plan: PEG tube placement next week.'
PEG_PLACED = 'A PEG tube was placed in the stomach.'
DILATED = 'Balloon dilation of the esophagus to 18 mm was performed.'
# wording-5: (the base report, its code and anchor, the line, the act named)
PERFORMED_HERE = (
    (r6m.EGD, '43235', r6m.D2, 'egd', PEG_PLACED,
     'the gastrostomy (PEG) placement at the stomach in the upper endoscopy as performed'),
    (r6m.COLON, '45378', r6m.CECUM, 'colonoscopy', r7.BANDED, 'the band ligation in the colonoscopy as performed'),
    (r6m.EGD, '43235', r6m.D2, 'egd', DILATED,
     'the dilation (balloon) at the esophagus in the upper endoscopy as performed'),
)


def engine(text, family, quote, head_code='45378', anchor=r6m.CECUM, head_family='colonoscopy'):
    return he.run(text, he.corti((head_code, he.span(text, anchor))),
                  [he.read('astra', [he.code(text, head_code, anchor)],
                           services=[he.service(text, head_family, anchor), he.service(text, family, quote)])])


class MissingServiceReadingTests(SimpleTestCase):
    def assert_named(self, result, label, read_as, quote):
        (entry,) = result.completeness['participant_services']
        self.assertEqual((entry['reason'], entry['read_as']), (reason(label, read_as, quote), read_as))
        self.assertEqual(result.completeness['state'], 'incomplete')
        check = next(c for c in result.encounter_checks if c.id == 'participants.services')
        self.assertEqual(check.detail, check_detail(label, read_as, quote))
        return entry

    def test_wording_1_the_inventory_s_own_reading_of_the_quote_is_named(self):
        for line, family, label, read_as in NOT_DONE_HERE:
            with self.subTest(line):
                text = r6m.doc(r6m.COLON, line)
                self.assert_named(engine(text, family, line), label, read_as, line)

    def test_wording_2_the_quoted_mention_s_own_kind_never_another_line_s(self):
        for status, peg, line in PEG_FIRST:
            for order in ((peg, line), (line, peg)):
                with self.subTest(status=status, peg_first=order[0] == peg):
                    text = r6m.doc(r6m.COLON, *order)
                    entry = self.assert_named(engine(text, 'egd', line), 'upper endoscopy',
                                              f'the upper endoscopy as {status}', line)
                    self.assertNotIn('peg', entry['reason'])

    def test_wording_2_another_line_s_reading_is_never_the_quote_s(self):
        """The inventory gives the upper-endoscopy service 'planned' from the PEG plan line; it reads the quoted line
        itself as uncertain, so nothing is named beside it, in either order."""
        for order in ((PEG_PLAN, REPEAT), (REPEAT, PEG_PLAN)):
            with self.subTest(order[0]):
                text = r6m.doc(r6m.COLON, *order)
                result = engine(text, 'egd', REPEAT)
                self.assertIn(('gi.egd', 'planned'), [(s['family'], s['status']) for s in result.services['services']])
                entry = self.assert_named(result, 'upper endoscopy', '', REPEAT)
                self.assertNotIn('planned', entry['reason'])

    def test_a_status_the_inventory_does_not_give_the_service_is_never_named(self):
        """A mention's own reading is named only where the inventory gives that family's service the same status: with
        a cancelled upper endoscopy beside a plan line, the inventory's upper endoscopy is cancelled, so the quoted plan
        line is named nothing - neither its own 'planned', which the inventory's conclusion did not adopt, nor the
        other line's 'cancelled' (display-1) - while the cancelled line itself is named, in either order."""
        planned, cancelled = r7.IN_QUOTE[0][1], r7.IN_QUOTE[2][1]
        for order in ((planned, cancelled), (cancelled, planned)):
            with self.subTest(first=order[0]):
                text = r6m.doc(r6m.COLON, *order)
                result = engine(text, 'egd', planned)
                self.assertIn(('gi.egd', 'cancelled'), [(s['family'], s['status'])
                                                        for s in result.services['services']])
                entry = self.assert_named(result, 'upper endoscopy', '', planned)
                self.assertNotIn('cancelled', entry['reason'])
                self.assert_named(engine(text, 'egd', cancelled), 'upper endoscopy',
                                  'the upper endoscopy as cancelled', cancelled)

    def test_wording_5_an_act_read_as_performed_is_never_said_not_to_be_read(self):
        """wording-5: a PEG, a banding or a dilation the inventory files under the endoscopy, quoted as another GI
        service, had been said not to be read as performed. Round 8 named the act; moved by refutation round 10
        (wording-2 to wording-5): no act is named, and the reason says what makes the service missing - the
        documented-service reading reads no performed service of that kind - which is true here. Moved by round 11
        (wording-1): the PEG line is itself a service mention the reading reads as performed, under the upper GI
        endoscopy family, so the reason says so; the banding and dilation lines name no service and keep the
        fallback alone."""
        upper = 'a performed service under Upper GI endoscopy (EGD, esophagoscopy, POEM)'
        for base, head_code, anchor, head_family, line, _ in PERFORMED_HERE:
            with self.subTest(line):
                text = r6m.doc(base, line)
                result = engine(text, 'other_gi', line, head_code, anchor, head_family)
                if line == PEG_PLACED:
                    (entry,) = result.completeness['participant_services']
                    self.assertEqual((entry['read_as'], entry['read_in']), ('', upper))
                    self.assertEqual(entry['reason'], f'Astra reads a performed other GI service {r7.NOT_READ}, and '
                                                      f'reads in the quoted words {upper} (“{line}”)')
                    check = next(c for c in result.encounter_checks if c.id == 'participants.services')
                    self.assertEqual(check.detail, f'Astra reads a performed other GI service (“{line}”), where the '
                                                   f'documented-service reading reads in the quoted words {upper}. The '
                                                   'documented-service reading reads no performed service of that '
                                                   'kind, so coding completeness is incomplete.')
                else:
                    entry = self.assert_named(result, 'other GI service', '', line)
                    self.assertEqual(entry['read_in'], '')
                self.assertNotIn('does not read as performed', entry['reason'])
                self.assertNotIn(' as performed', entry['reason'])

    def test_the_located_readings_change_no_inventory(self):
        """gi_services.build's ``located`` is a record beside the inventory, never an input: the same inventory with it
        and without it, on every input above (I1: with no participant configured the engine passes none)."""
        texts = ([r6m.doc(r6m.COLON, line) for line, *_ in NOT_DONE_HERE]
                 + [r6m.doc(r6m.COLON, peg, line) for _, peg, line in PEG_FIRST]
                 + [r6m.doc(r6m.COLON, PEG_PLAN, REPEAT)] + [r6m.doc(base, line) for base, _, _, _, line, _ in
                                                            PERFORMED_HERE])
        for text in texts:
            with self.subTest(text[-60:]):
                routing = detect.route(text, he.DAY)
                facts = gi_context.extract_context(text)
                located = []
                with_record = gi_services.build(text, service_date=he.DAY, routing=routing, context_facts=facts,
                                                located=located)
                self.assertEqual(with_record, gi_services.build(text, service_date=he.DAY, routing=routing,
                                                                context_facts=facts))
                self.assertTrue(located)
                # moved by refutation round 9 (wording-1): each entry names what it is; round 10 removed the act
                # mentions, and round 11 (wording-2) records an instrument as one, never as a service's own name
                for what, family, kind_, status, start, end in located:
                    self.assertTrue(0 <= start < end <= len(text))
                    self.assertIn(what, ('service', 'instrument'))
                    self.assertIn(status, gi_services.SERVICE_STATUSES)


@applied
class MissingServiceReadingPipelineTests(r6m.MeaningCase):
    missing = r7.MissingServiceReadingPipelineTests.missing

    def assert_reviewed(self, encounter_id, said, unsaid):
        detail = self.detail(encounter_id)
        self.assertEqual(detail['coding']['state'], 'incomplete')
        self.assertIn(said, detail['coding']['statement'])
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '45378']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        self.assertTrue(self.detail(encounter_id)['readiness']['reviewed'])
        for report_kind in ('draft', 'reviewed'):
            with self.subTest(report_kind):
                report = self.download(encounter_id, report_kind)
                self.assertIn(said, report)
                self.assertNotIn(unsaid, report)

    def test_wording_1_declined_in_the_reviewed_report(self):
        line = 'The patient declined EGD.'
        encounter_id = self.missing(r6m.doc(r6m.COLON, line), line)
        self.assert_reviewed(encounter_id, reason('upper endoscopy', 'the upper endoscopy as cancelled', line),
                             r7.NOT_READ)

    def test_wording_2_peg_first_in_the_reviewed_report(self):
        status, peg, line = PEG_FIRST[0]
        encounter_id = self.missing(r6m.doc(r6m.COLON, peg, line), line)
        self.assert_reviewed(encounter_id, reason('upper endoscopy', f'the upper endoscopy as {status}', line),
                             'reads the peg as')


# --- wording-3, page-3: the participants-only blocker and panel never say "not the provider" ------------------------

def refused_whole():
    """Corti's fake answer with its 'candidates' list removed: the real normaliser refuses the response whole, so its
    selections are never read (page-3's input)."""
    real = test_pipeline_api.corti_like_response

    def answer(text, selections):
        data = json.loads(real(text, selections))
        del data['candidates']
        return json.dumps(data).encode()
    return mock.patch('tests.test_pipeline_api.corti_like_response', answer)


PANEL = 'Each code listed below was given by Astra or Fable and is offered only as an alternative.'


@applied
class ParticipantsOnlyWordingTests(r6m.MeaningCase):
    assert_blocker = r6m.D14BlockerTests.assert_blocker

    def test_page_3_a_provider_response_refused_whole(self):
        """page-3: Corti's stored response selects 45385 and is refused whole; Astra's 45385 is the only code listed.
        The provider check says its own sentence, never that the provider did not give the code. HARNESS.md P-ADMIT
        (2026-11-05): Astra's first-reading 45385 on the snare sentence is admitted (D14 had listed it), so the provider
        check says the proposals come only from the independent participants, and the refused response blocks only
        itself: a member decides the code, and coding completeness says the provider response was not available."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r7.SNARED)
        with refused_whole():
            encounter_id = self.scenario(text, [('45385', r7.SNARED)], astra=hp.reading(codes=[('45385', r7.SNARED)]))
        detail = self.detail(encounter_id)
        self.assertEqual([(p['code'], p['bucket'], (p.get('support') or {}).get('origin'))
                          for p in r6m.proposals(detail)], [('45385', 'selected', 'participant')])
        # I10: the provider's refusal blocks only itself - a member decides the admitted code, and coding completeness
        # still says the provider response was not available (the blocker below is raised only where no code can be
        # decided at all)
        self.assertEqual(detail['readiness']['blockers'], ['45385 has no decision'])
        self.assertEqual(detail['assessment']['completeness']['state'], 'incomplete')
        self.assertIn('the provider response was not available', detail['assessment']['completeness']['reasons'])
        (provider,) = [c for c in detail['assessment']['encounter_checks'] if c['id'] == 'provider.status']
        self.assertEqual(provider['status'], 'fail')
        self.assertIn('so it proposed no codes. The proposals listed come only from the independent participants '
                      '(Astra)', provider['detail'])
        lines = self.page_lines(detail)
        self.assertFalse(any('not the provider' in line for line in lines), lines)
        (run,) = models.ProviderRun.objects.filter(encounter_id=encounter_id, provider='corti')
        self.assertIn('"45385"', bytes(run.response_bytes).decode())

    def test_wording_3_a_second_review_not_yet_read(self):
        """wording-3 (b): Corti selects nothing, Astra's 45385 is listed, and the second review a reviewer asks for
        selects 45385; Stop is pressed before the assessment that would read it. The blocker on every surface says
        who gave the code and that the second review is unread, never "not the provider"."""
        from studio import jobs  # noqa: PLC0415 - the test steps the queue itself
        # moved by the completion repair (builder Q1, equal eligibility): a first reading's 45385 on the failed
        # polypectomy is admitted and excluded with that passage now (a code a member decides), so the participants-only
        # state is reached by a peer review's addition, which stays an alternative
        encounter_id = self.scenario(r6m.doc(r6m.COLON, r6m.SEEN, r6m.FAILED), [],
                                     astra_peer=hp.peer_answer(codes=[('45385', r6m.FAILED)]))
        self.corti.selections = [('45385', r6m.FAILED)]
        reply = self.client.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(reply.status_code, 201, reply.content)
        while True:
            job = jobs.claim_next()
            self.assertIsNotNone(job)
            stage = job.kind
            jobs.run_job(job)
            if stage == 'review2':
                break
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        (second,) = models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose='second_review')
        self.assertEqual(second.state, models.ProviderRun.SUCCEEDED)
        self.assertIn('"45385"', bytes(second.response_bytes).decode())
        said = f'{r6m.PARTICIPANTS_ONLY}; the second review has not been read yet'
        self.assert_blocker(encounter_id, said, 'not the provider')


# --- wording-4: participants.summary's closing sentence ------------------------------------------------------------

@applied
class SummarySentenceTests(r6m.MeaningCase):
    def ask_second(self, encounter_id, later):
        self.corti.selections = list(later)
        reply = self.client.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        return self.detail(encounter_id)

    def test_a_code_the_second_review_listed_without_adding(self):
        """wording-4: the second review selects 45381, which accounts for nothing left unresolved, so it is not added
        (alt2) - and Astra's 45381 is listed as an alternative of its own, never recorded on a proposal. Moved by the
        completion repair (owner directive 2026-11-06, item 3: equal eligibility; builder Q1): a first reading's 45381
        is admitted now (held, as Corti's own selection of the biopsy sentence is), so Astra gives it in peer review,
        which is never admitted."""
        encounter_id = self.scenario(he.COLON, [('45378', he.CECUM)], astra=hp.reading(codes=[('45378', he.CECUM)]),
                                     astra_peer=hp.peer_answer(codes=[('45381', he.BIOPSY)]))
        detail = self.ask_second(encounter_id, [('45381', he.BIOPSY)])
        rows = sorted((kind(p), p['code'], p['bucket']) for p in r6m.proposals(detail) if p['code'] == '45381')
        self.assertEqual(rows, [('alt2', '45381', 'alternative'), ('altp', '45381', 'alternative')])
        self.assertFalse([p for p in r6m.proposals(detail) if p['code'] == '45381'
                          and 'astra' in (p.get('proposed_by') or []) and p['bucket'] != 'alternative'])
        summary = self.summary(detail)
        self.assertTrue(summary.endswith(f' {r6m.NEVER_DECIDE}'), summary)
        # the sentence of HARNESS.md P-ADMIT2 (harness repair 3, the owner's second message of 2026-11-05): such a code
        # is read whatever any other proposer did with it (the gap-filling sentence of P-ADMIT is withdrawn)
        self.assertIn('whatever any other proposer did with it, and added as a proposal of its own where they read it as '
                      'accounting for a documented service or act done on the date of service', summary)
        self.assertNotIn('left unresolved', summary)

    def test_a_code_the_second_review_added_carries_the_participant_s_code(self):
        """The sentence's first clause, the other kind: the second review's 45385 accounts for the snare removal the
        primary proposals left unresolved, so it is added - and Astra's 45385 is recorded on it, never listed apart.
        HARNESS.md P-ADMIT (2026-11-05): a first-reading 45385 would be admitted before any second review is asked
        (there is then nothing left unresolved to ask about), so Astra gives it in peer review, which is never admitted:
        the snare stays open for the second review."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r7.SNARED)
        encounter_id = self.scenario(text, [('45378', r6m.CECUM)], astra=hp.reading(codes=[('45378', r6m.CECUM)]),
                                     astra_peer=hp.peer_answer(codes=[('45385', r7.SNARED)]))
        detail = self.ask_second(encounter_id, [('45385', r7.SNARED)])
        rows = [(p['code'], p['bucket'], (p.get('support') or {}).get('origin'), p.get('proposed_by'))
                for p in r6m.proposals(detail) if p['code'] == '45385']
        self.assertEqual(len(rows), 1, rows)
        self.assertNotEqual(rows[0][1], 'alternative', rows)
        self.assertIn('astra', rows[0][3], rows)
        self.assertTrue(self.summary(detail).endswith(f' {r6m.NEVER_DECIDE}'))


# --- page-1, page-2: a highlight carrying both kinds of passage for one code ----------------------------------------

EM_TIME = ('Total time spent on the date of the encounter was 30 minutes, including review of the 2026-03-02 EGD '
           'report.')
EM_NOTE = (hp.HEAD + 'Office visit (fictional)\nDate of service: 2026-10-14\nPlace of service: Office\n'
           'Established patient seen today for follow-up of GERD.\nShe reports heartburn twice weekly on omeprazole.\n'
           + EM_TIME + '\nAssessment: GERD, partially controlled.\nPlan: increase omeprazole; return in 3 months.\n')
NOT_THE_ACT = 'Passage the provider cited for {code}, which does not show the coded act'
# moved by refutation round 9 (page-3): "Overlapping passages" was false of two separate passages another code's passage
# joins into one highlight (it was "Overlapping passages for {code}: evidence for {code}, and ...")
OVERLAPPING = ('Passages for {code} in this highlight: evidence for {code}, and a passage the provider cited for {code} '
               'that does not show the coded act')


def titles_of(detail, value):
    (item,) = [p for p in r6m.proposals(detail) if p['code'] == value and p['bucket'] == 'selected']
    return item, {text: title for keys, title, text in r6m.marks(detail)
                  if any(key.startswith(f'{item["id"]}:') for key in keys)}


@applied
class OverlappingPassageTitleTests(r6m.MeaningCase):
    def both(self, text, corti):
        return [self.corti_alone(text, corti), self.detail(self.scenario(text, corti))]

    def test_page_2_a_passing_support_with_a_passage_that_does_not_show_the_act(self):
        """page-2: Corti's Ready 45385 cites the "was seen" sentence and the snare sentence; the support passes on the
        second and says the first does not show the coded act. Display-6's pins checked only a warning support."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r7.SNARED)
        for detail in self.both(text, [('45385', r6m.SEEN), ('45385', r7.SNARED)]):
            item, titles = titles_of(detail, '45385')
            self.assertEqual((item['status'], item['support']['status'], item['support']['supporting'],
                              item['support']['unrelated']), ('ready', 'pass', [1], [0]))
            self.assertEqual(titles, {r6m.SEEN: NOT_THE_ACT.format(code='45385'), r7.SNARED: 'Evidence for 45385'})

    def test_page_1_b_a_longer_provider_passage_that_holds_it(self):
        """page-1 (b): Corti cites the "was seen" sentence and the whole line holding it; the layout merges the two
        into one highlight, which was titled "Evidence for 45385; Passage the provider cited for 45385, which does not
        show the coded act"."""
        line = f'{r6m.SEEN} {r7.SNARED}'
        text = r6m.doc(r6m.COLON, line)
        for detail in self.both(text, [('45385', r6m.SEEN), ('45385', line)]):
            item, titles = titles_of(detail, '45385')
            self.assertEqual((item['support']['status'], item['support']['unrelated']), ('pass', [0]))
            self.assertEqual(titles, {line: OVERLAPPING.format(code='45385')})

    def test_page_1_a_a_source_passage_at_the_same_place(self):
        """page-1 (a): the office visit's time sentence reviews an earlier, dated EGD report; Corti's Ready 99213 cites
        only it. The support reads it as not showing the visit and also selects it as one of the visit's own source
        passages (reconcile.support's office-visit arm: recorded for the shared-reader repair, an I1 change), so one
        highlight carries both - never titled "Evidence for 99213" beside its own "does not show the coded act"."""
        for detail in self.both(EM_NOTE, [('99213', EM_TIME)]):
            item, titles = titles_of(detail, '99213')
            self.assertEqual((item['status'], item['support']['status'], item['support']['unrelated']),
                             ('ready', 'warn', [0]))
            self.assertIn(EM_TIME, [s['text'] for s in item['support']['source']])
            self.assertEqual(titles[EM_TIME], OVERLAPPING.format(code='99213'))
            self.assertFalse(any(title.startswith('Evidence for 99213;') for title in titles.values()), titles)
