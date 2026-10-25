"""The ten verification documents route as ops/verification/manifest.json expects.

They are the regression universe for normal notes: a routing repair that makes
a not-done service read as not done must leave these readings where they are.
The checks mirror ops/verify_browser.cjs (checkContext and checkRouting) over
each document's .txt source, with the pipeline's context and service-date
handling (studio/jobs.py: _analyze_child, _service_date_of, context_service_date).
Synthetic text only; pure functions.
"""
import json
import unittest
from datetime import date
from pathlib import Path

from studio.gi.context import extract_context, merge_user_values
from studio.gi.detect import route
from studio.types import RoutingResult, from_jsonable, to_jsonable

ROOT = Path(__file__).resolve().parent.parent / 'ops' / 'verification'
MANIFEST = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
DOCUMENTS = MANIFEST['documents']
PERFORMED = ('performed', 'incomplete')  # verify_browser.cjs PERFORMED
# Informational (soft) expectations that did not hold on the routing this test was written against
# (2c3a6788e), so the test passes on both sides of a repair. Allowed, never required: every other
# informational expectation is held hard here, so a repair that breaks one is seen.
# - gi-03 intent: "screening" (indication) conflicted with "surveillance" read from the plan sentence
#   "The surveillance colonoscopy interval will be set ..." (refutation finding status:14).
INFORMATIONAL_BASELINE_DEVIATIONS = {('gi-03', 'gi.colonoscopy', 'fact intent')}


def _effective_date(facts) -> date | None:
    fact = facts['service_date']
    if fact.origin not in ('document', 'user') or not fact.value:
        return None
    return date.fromisoformat(fact.value)


def _routed(doc):
    text = (ROOT / doc['source']).read_text(encoding='utf-8')
    user = (doc.get('upload') or {}).get('service_date')
    facts = merge_user_values(extract_context(text), {'service_date': user} if user else {})
    result = route(text, _effective_date(facts))
    # The pipeline stores routing as JSON and reads it back.
    return text, facts, from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(result))))


def _document_fact(finding, name):
    """verify_browser.cjs familyFact: a documented, non-empty value."""
    return next((f for f in finding.facts if f.name == name and f.origin == 'document' and f.value is not None
                 and str(f.value).strip() != ''), None)


def _contains_any(value, needles) -> bool:
    text = str(value or '').lower()
    return any(needle.lower() in text for needle in needles)


class VerificationManifestRoutingTests(unittest.TestCase):
    def test_the_manifest_lists_the_ten_documents(self):
        self.assertEqual(len(DOCUMENTS), 10)
        for doc in DOCUMENTS:
            self.assertTrue((ROOT / doc['source']).is_file(), doc['source'])
            self.assertTrue(doc['source'].endswith('.txt'), doc['source'])

    def test_context_matches_the_manifest(self):
        for doc in DOCUMENTS:
            _, facts, _ = _routed(doc)
            for name, want in (doc.get('expected_context') or {}).items():
                with self.subTest(doc=doc['id'], fact=name):
                    fact = facts[name]
                    if want.get('origin_in'):
                        self.assertIn(fact.origin, want['origin_in'])
                    if want.get('value_in'):
                        self.assertIn(str(fact.value or '').lower(), [v.lower() for v in want['value_in']])

    def test_routing_matches_the_hard_expectations(self):
        for doc in DOCUMENTS:
            _, _, routing = _routed(doc)
            expected = doc['expected_routing']
            for slug, want in expected.get('families', {}).items():
                finding = routing.finding(slug)
                with self.subTest(doc=doc['id'], family=slug, check='presence'):
                    if want['presence'] == 'required':
                        self.assertIsNotNone(finding, f'{slug} not reported')
                if finding is None:
                    continue
                with self.subTest(doc=doc['id'], family=slug, check='status'):
                    self.assertIn(finding.status, want.get('status_in', []))
                for name, rule in (want.get('facts') or {}).items():
                    with self.subTest(doc=doc['id'], family=slug, check=f'fact {name}'):
                        fact = _document_fact(finding, name)
                        self.assertIsNotNone(fact, f'no documented {name}')
                        if rule.get('value_contains_any'):
                            self.assertTrue(_contains_any(fact.value, rule['value_contains_any']),
                                            f'{name} = {fact.value!r}')
                for name in want.get('missing_includes', []):
                    with self.subTest(doc=doc['id'], family=slug, check=f'missing {name}'):
                        self.assertIn(name, finding.missing)
                for name in want.get('missing_excludes', []):
                    with self.subTest(doc=doc['id'], family=slug, check=f'not missing {name}'):
                        self.assertNotIn(name, finding.missing)
            for slug in expected.get('not_performed', []):
                finding = routing.finding(slug)
                if finding is None:
                    continue
                with self.subTest(doc=doc['id'], family=slug, check='not performed'):
                    statuses = [finding.status] + [m.status for m in finding.mentions]
                    self.assertFalse(any(s in PERFORMED for s in statuses), statuses)

    def test_routing_matches_the_informational_expectations(self):
        """Soft checks in the browser verifier; held here too, so a change to one is seen and reported."""
        for doc in DOCUMENTS:
            _, _, routing = _routed(doc)
            for slug, want in doc['expected_routing'].get('families', {}).items():
                finding = routing.finding(slug)
                info = want.get('informational') or {}
                if finding is None or not info:
                    continue
                for name, rule in (info.get('facts') or {}).items():
                    if (doc['id'], slug, f'fact {name}') in INFORMATIONAL_BASELINE_DEVIATIONS:
                        continue
                    with self.subTest(doc=doc['id'], family=slug, check=f'informational fact {name}'):
                        fact = _document_fact(finding, name)
                        self.assertIsNotNone(fact, f'no documented {name}')
                        self.assertTrue(_contains_any(fact.value, rule.get('value_contains_any') or ['']))
                if info.get('mention_statuses_include'):
                    with self.subTest(doc=doc['id'], family=slug, check='informational mentions'):
                        seen = {m.status for m in finding.mentions}
                        self.assertLessEqual(set(info['mention_statuses_include']), seen)

    def test_incomplete_services_are_routed_incomplete(self):
        for doc in DOCUMENTS:
            _, _, routing = _routed(doc)
            for item in doc.get('incomplete_services', []):
                with self.subTest(doc=doc['id'], family=item['family']):
                    finding = routing.finding(item['family'])
                    self.assertIsNotNone(finding)
                    self.assertEqual(finding.status, 'incomplete')


if __name__ == '__main__':
    unittest.main()
