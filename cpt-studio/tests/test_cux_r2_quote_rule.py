"""The server's ONE quotation rule (the page's "Why this code?" and the approved export's evidence: review.evidence_spans)
and the tools' rule (ops/verify_downloads.py allowed_passages, which ops/verify_browser.cjs allowedPassages mirrors) are
the same passages, for each shape (refutation round 2, L3-7 and L3-10). Written by the round-2 tools owner as a probe for
the integration; it failed on the denied page and the 46600 export before the server and tools rules were unified.
Synthetic data only."""
import importlib.util
import json
import sys
from pathlib import Path

from django.test import Client, TestCase

from studio import review
from studio.gi import context as gi_context
from studio.types import to_jsonable
from tests.support import factories as f
from tests.support import operator as ops
from tests.support import pipeline_factories as pf
from tests.test_cux_review import assess, persist, retrieval_for

TREE = Path(review.__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('vd_r2d_quote_rule', TREE / 'ops' / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['vd_r2d_quote_rule'] = vd
_spec.loader.exec_module(vd)
ANOSCOPY = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nAnoscopy note (fictional)\n'
            'Date of service: 2026-11-03\nPlace of service: Office\nProcedure: Anoscopy\n'
            'Anoscopy was performed and showed grade 2 internal hemorrhoids.\n')


def persist_text(text, codes):
    s = pf.scenario(text=text)
    facts = {name: to_jsonable(fact) for name, fact in gi_context.extract_context(text).items()}
    ctx = pf.context(s.encounter, s.revision, fact_values=facts)
    result = assess(text, codes)
    review.persist_assessment(encounter=s.encounter, revision=s.revision, context=ctx, routing_run=pf.routing(s.revision),
                              provider_run=pf.provider_run(s.encounter, s.revision), result=result,
                              retrieval=retrieval_for(result, [c for c, _ in codes]))
    s.encounter.refresh_from_db()
    return s


class QuoteRule(TestCase):
    def signed(self, user):
        c = Client(enforce_csrf_checks=False)
        c.force_login(user)
        return c

    def decide(self, s, user, code, action):
        doc = self.signed(user).get(f'/api/encounters/{s.encounter.pk}').json()
        pid = next(c['id'] for c in doc['codes'] if c['code'] == code)
        body = {'proposal_id': pid, 'action': action, 'note': 'Synthetic: agent-executed synthetic verification review.'}
        if action == 'approve':
            body['acknowledgement'] = review.ACKNOWLEDGEMENTS[user.actor_kind]
        r = self.signed(user).post(f'/api/encounters/{s.encounter.pk}/decisions', data=json.dumps(body), content_type='application/json')
        self.assertEqual(r.status_code, 201, r.content)

    def agree(self, s, user, code):
        page = {c['code']: c for c in self.signed(user).get(f'/api/encounters/{s.encounter.pk}').json()['codes']}[code]
        op = ops.client(f.user(f'ops-quote-{str(s.encounter.pk)[:8]}')).get(f'/ops/api/encounters/{s.encounter.pk}').json()
        p = next(item for item in op['assessment']['proposals'] if item['code'] == code)
        allowed, _ = vd.allowed_passages(p, op['revision']['text'], vd.act_index(op), vd.customer_status(p))
        exported = {item['code']: item for item in review.approved_items(s.encounter.current_assessment)}.get(code)
        spans = lambda items: sorted((q['start'], q['end']) for q in items)  # noqa: E731
        print(f'[{code}] page {spans(page["why"]["quotes"])} export {spans(exported["evidence"]) if exported else "-"} tools {spans(allowed)}')
        self.assertTrue(set(spans(page['why']['quotes'])) <= set(spans(allowed)), 'the page quotes a passage the rule does not hold')
        if exported is not None:
            self.assertTrue(set(spans(exported['evidence'])) <= set(spans(allowed)), 'the export quotes a passage the rule does not hold')
            self.assertEqual(spans(exported['evidence']), spans(page['why']['quotes']), 'the page and the export disagree')

    def test_pair_pass_reading(self):
        s = persist('pair')
        self.decide(s, s.agent, '45380', 'approve')
        self.agree(s, s.agent, '45380')

    def test_denied_reinstated_not_applicable_reading(self):
        s = persist('denied')
        self.decide(s, s.agent, '45385', 'reinstate')
        self.decide(s, s.reviewer, '45378', 'reject')
        self.decide(s, s.reviewer, '45385', 'approve')
        self.agree(s, s.reviewer, '45385')

    def test_no_support_reading_46600(self):
        s = persist_text(ANOSCOPY, [('46600', 'Anoscopy was performed and showed grade 2 internal hemorrhoids.')])
        doc = self.signed(s.agent).get(f'/api/encounters/{s.encounter.pk}').json()
        if not any(c['code'] == '46600' and 'approve' in c['allowed_actions'] for c in doc['codes']):
            self.skipTest(f'46600 is not approvable in this shape: {[(c["code"], c["status"]) for c in doc["codes"]]}')
        self.decide(s, s.agent, '46600', 'approve')
        self.agree(s, s.agent, '46600')
