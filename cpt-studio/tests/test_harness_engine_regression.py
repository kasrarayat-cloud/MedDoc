"""HARNESS.md 11.3 on the retained regression documents (tests/fixtures/gi4/regression/, synthetic): a reviewer-confirmed
finding built from each document's own passage, read by the real readers and the engine exactly as ops.gi4.replay reads
the assess stage (the member's answer merged, the request rebuilt, the retained Corti answer that request received, the
synthetic reference rows), offline.

The rows (ROWS) are the record. For each: without the confirmation the proposal stays held exactly as today (the
proposals equal the committed replay pin of installed 80df1831d168, state by state, and the stage's own assess child
gives the same result); with it, the hold changes only as the confirmed fact allows - READY, or still held for its
stated other reason (the encounter's unknown date) - nothing becomes approved, and nothing else moves (only the answered
question, the proposal's required-facts check, its status, rationale, fingerprint and support record, the open-question
count in completeness, and the confirmations' own encounter check and record).
"""
import json
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import regression, replay
from studio.gi import detect
from studio.types import ConfirmedFinding, EvidenceSpan, RoutingResult, from_jsonable, to_jsonable
from studio.validation import checks
from studio.validation.engine import assess

PIN = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'pins' / 'replay.json').read_text())
REVIEWER = 'Rowan Synthetic-Reviewer (fictional)'
# What each document's open question asks and the passage of the document itself that answers it.
CONFIRMATIONS = {
    'h4-01': ('em_basis', 'gi.office_em', 'sel:0', 'total time on the date of the visit: 52 minutes',
              'Total time I spent on her care on the date of this visit: 52 minutes'),
    'h4-06': ('extent', 'gi.colonoscopy', 'sel:0', 'ileocolic anastomosis',
              'Reach of the examination: ileocolic anastomosis, with 6 cm of neoterminal ileum viewed through it.'),
    'h4-03': ('extent', 'gi.egd', 'sel:0', 'descending duodenum',
              'passed down the esophagus, through the stomach and pylorus, into the descending duodenum'),
}
# The record: (document, member state) -> (code, (status, its questions) without the confirmation, the same with it,
# the encounter's questions in both, completeness state without -> with). 'walk' is the walk's answered date of service;
# 'none' is no member answer: the date is unknown, and every proposal waits on the encounter's date question.
ROWS = {
    ('h4-01', 'walk'): ('99204', ('needs_clarification', ['em_basis']), ('ready', []), [],
                        ('incomplete', 'complete_pending_review')),
    ('h4-01', 'none'): ('99204', ('needs_clarification', ['em_basis']), ('needs_clarification', []),
                        [('encounter', '', 'service_date'), ('service', 'gi.egd', 'extent')],
                        ('incomplete', 'incomplete')),
    ('h4-06', 'walk'): ('45385', ('needs_clarification', ['extent']), ('ready', []), [],
                        ('incomplete', 'complete_pending_review')),
    ('h4-06', 'none'): ('45385', ('needs_clarification', ['extent']), ('needs_clarification', []),
                        [('encounter', '', 'service_date')], ('incomplete', 'incomplete')),
    ('h4-03', 'walk'): ('43244', ('needs_clarification', ['extent']), ('ready', []), [],
                        ('incomplete', 'complete_pending_review')),
    ('h4-03', 'none'): ('43244', ('needs_clarification', ['extent']), ('needs_clarification', []),
                        [('encounter', '', 'service_date')], ('incomplete', 'incomplete')),
}
# What a read confirmation may change on the proposal it answers, and on the assessment.
PROPOSAL_MAY_MOVE = {'status', 'checks', 'clarifications', 'rationale', 'fingerprint', 'support'}
ASSESSMENT_MAY_MOVE = {'proposals', 'encounter_checks', 'summary', 'completeness'}


class RegressionConfirmationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.m = replay.modules()
        cls.docs = regression.load_fixtures()

    @classmethod
    def tearDownClass(cls):
        cls.m.jobs.release_routing_caches()
        super().tearDownClass()

    def inputs(self, doc, state):
        m, text = self.m, doc['text']
        answer = doc['walk_answer'] if state == 'walk' else None
        facts = m.jobs._merged_facts(m.context.extract_context(text), {'service_date': answer} if answer else {})
        self.assertFalse(m.context.is_member_conflict(facts['service_date']))
        day = m.jobs._service_date_of(facts)
        request = replay._request(m, text, day)
        retained = {r['request_sha256']: r for r in doc['runs'] if r['request_sha256'] and r['response'] is not None}
        normalized = m.normalize('corti', request, json.dumps(retained[request.canonical_sha256]['response']).encode())
        return SimpleNamespace(text=text, day=day, pages=(m.PageSpan(1, 0, len(text)),), normalized=normalized,
                               context=m.jobs.context_facts(SimpleNamespace(facts=facts)),
                               reference=replay._reference(m, doc, normalized))

    def assessed(self, i, confirmed=()):
        routing = from_jsonable(RoutingResult, to_jsonable(detect.route(i.text, i.day)))  # as the assess child reads it
        return assess(text=i.text, pages=i.pages, context=i.context, routing=routing, normalized=i.normalized,
                      reference=i.reference, service_date=i.day, provider_status='succeeded', extraction_status='ok',
                      extraction_messages=(), confirmed=confirmed)

    def confirmation(self, doc_id, text):
        fact, family, key, value, passage = CONFIRMATIONS[doc_id]
        start = text.index(passage)
        self.assertEqual(text.count(passage), 1, doc_id)
        return ConfirmedFinding('proposal', fact, family, key, value, (EvidenceSpan(0, start, start + len(passage),
                                                                                    passage, True),),
                                ('fable',), REVIEWER, f'confirmation-{doc_id}')

    def test_the_rows(self):
        for (doc_id, state), (code, held, after_row, asked, complete) in ROWS.items():
            label = f'{doc_id} [{state}]'
            doc = self.docs[doc_id]
            i = self.inputs(doc, state)
            before = self.assessed(i)
            # the harness reads as the stage reads: the assess child gives the same result
            self.assertEqual(before, self.m.jobs._assess_child(i.text, i.day, i.pages, i.context, i.normalized,
                                                               i.reference, 'succeeded', 'ok', ())[1], label)
            # without the confirmation: held exactly as today (installed's pinned replay of this state)
            pinned = PIN['documents'][doc_id]['states'][state]['proposals']
            self.assertEqual(sorted([p.code, p.bucket, p.status, p.fingerprint[:12]] for p in before.proposals
                                    if p.bucket != 'alternative'), pinned, label)
            fact, family, key = CONFIRMATIONS[doc_id][:3]
            item = next(p for p in before.proposals if p.key == key)
            self.assertEqual((item.code, item.status, sorted(q.fact for q in item.clarifications)), (code, *held), label)

            after = self.assessed(i, (self.confirmation(doc_id, i.text),))
            answered = next(p for p in after.proposals if p.key == key)
            self.assertEqual((answered.code, answered.status, sorted(q.fact for q in answered.clarifications)),
                             (code, *after_row), label)
            self.assertEqual([(q.scope, q.family, q.fact) for q in before.clarifications], asked, label)
            self.assertEqual(after.clarifications, before.clarifications, label)  # never another question
            self.assertEqual((before.completeness['state'], after.completeness['state']), complete, label)
            # nothing becomes approved: ready to decide at most, and approval is a member's separate decision
            self.assertTrue({p.status for p in after.proposals} <= {'ready', 'needs_clarification', 'excluded',
                                                                   'informational'}, label)
            # what it uses says so, and records the confirmation
            words = f"confirmed from Fable's located passage by {REVIEWER}"
            self.assertIn(f'{checks.CONFIRMED_HEADING}: {checks.fact_label(fact)} = {CONFIRMATIONS[doc_id][3]}, '
                          f'{words}', next(c for c in answered.checks if c.id == 'facts.required').detail, label)
            self.assertIn(words, answered.rationale, label)
            self.assertEqual(answered.support['confirmed'], [f'confirmation-{doc_id}'], label)

            # nothing else moves
            moved = {f.name for f in fields(before) if getattr(before, f.name) != getattr(after, f.name)}
            self.assertTrue(moved <= ASSESSMENT_MAY_MOVE, (label, moved))
            others = [(p, q) for p, q in zip(before.proposals, after.proposals) if p.key != key]
            self.assertEqual([p for p, _ in others], [q for _, q in others], label)
            self.assertEqual([p.key for p in before.proposals], [p.key for p in after.proposals], label)
            changed = {f.name for f in fields(item) if getattr(item, f.name) != getattr(answered, f.name)}
            self.assertTrue(changed <= PROPOSAL_MAY_MOVE, (label, changed))
            self.assertEqual([c for c in item.checks if c.id != 'facts.required'],
                             [c for c in answered.checks if c.id != 'facts.required'], label)
            self.assertEqual([q for q in item.clarifications if q.fact != fact], list(answered.clarifications), label)
            self.assertEqual({k: v for k, v in item.support.items()},
                             {k: v for k, v in answered.support.items() if k != 'confirmed'}, label)
            self.assertEqual([c for c in after.encounter_checks if c.id != 'confirmations.applied'],
                             list(before.encounter_checks), label)
            kept = ('state', 'reasons', 'statement', 'confirmations')
            self.assertEqual({k: v for k, v in before.completeness.items() if k not in kept},
                             {k: v for k, v in after.completeness.items() if k not in kept}, label)
            self.assertEqual({k: v for k, v in before.summary.items() if k not in ('ready', 'needs_clarification')},
                             {k: v for k, v in after.summary.items() if k not in ('ready', 'needs_clarification')}, label)
            self.m.jobs.release_routing_caches()

    def test_a_confirmation_from_another_passage_of_the_same_document_moves_the_fingerprint_not_the_hold_release(self):
        """The decision basis is the confirmed value and passage: two passages that both state the reach release the
        same hold, with fingerprints that differ, so a decision made on one never carries to the other."""
        doc = self.docs['h4-06']
        i = self.inputs(doc, 'walk')
        one = self.confirmation('h4-06', i.text)
        other_passage = 'Anastomosis: widely patent, with healthy mucosa'
        start = i.text.index(other_passage)
        other = ConfirmedFinding('proposal', 'extent', 'gi.colonoscopy', 'sel:0', 'ileocolic anastomosis',
                                 (EvidenceSpan(0, start, start + len(other_passage), other_passage, True),),
                                 ('astra',), REVIEWER, 'other')
        a, b = self.assessed(i, (one,)), self.assessed(i, (other,))
        pa, pb = (next(p for p in r.proposals if p.key == 'sel:0') for r in (a, b))
        self.assertEqual((pa.status, pb.status), ('ready', 'ready'))
        self.assertNotEqual(pa.fingerprint, pb.fingerprint)
