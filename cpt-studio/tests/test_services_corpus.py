"""The development corpus as a regression guard (tests/corpus/services, schema cpt-studio-services-corpus@1).

Every document must keep reading as it read when the corpus was added: the readings that agree with the author's
provisional expectations stay in agreement, and the remaining differences are exactly those recorded, with their
reasons, in known_differences.json. The expectations live in the corpus files, outside the reader. No provider is
called: the engine runs with an empty provider response, so the questions and unresolved items are the inventory's own.
"""
import json
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import NormalizedResponse
from studio.validation.engine import assess

CORPUS = Path(__file__).resolve().parent / 'corpus' / 'services'
POSITIVE = ('performed', 'incomplete')


def differences(text, doc):
    """(kind, family-or-subject) pairs where the reading differs from the document's expectations."""
    facts = gi_context.extract_context(text)
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    routing = detect.route(text, day)
    inv = services.build(text, service_date=day, routing=routing, context_facts=facts)
    result = assess(text=text, pages=(), context=facts, routing=routing,
                    normalized=NormalizedResponse('replay', 'corpus@1', ()), reference=InMemoryReferenceLookup((), {}),
                    service_date=day, provider_status='succeeded')
    found = set()
    by_family = {}
    for s in inv.services:
        by_family.setdefault(s.family, []).append(s)

    def done(family):
        return next((s for s in by_family.get(family, []) if s.status in POSITIVE), None)

    if doc.get('service_date') is not None and fact.value != doc['service_date']:
        found.add(('date', 'service_date'))
    expected_families = {e['family'] for e in doc.get('services', [])}
    for exp in doc.get('services', []):
        s = done(exp['family'])
        if s is None:
            found.add(('service.missing', exp['family']))
            continue
        if exp.get('status') and s.status != exp['status']:
            found.add(('service.status', exp['family']))
        if exp.get('completion') and s.completion != exp['completion']:
            found.add(('service.completion', exp['family']))
        for act in exp.get('acts', []):
            hits = [a for a in s.acts if a.kind == act['kind'] and a.status == 'performed']
            if act.get('anatomy_includes'):
                want = act['anatomy_includes'].lower()
                hits = [a for a in hits if any(want in x for x in a.anatomy)
                        or any(want in (l.anatomy or '') for l in s.lesions if l.id == a.lesion)]
            if not hits:
                found.add(('act.missing', f'{exp["family"]} {act["kind"]}'))
    for family, items in by_family.items():
        if family not in expected_families and any(s.status in POSITIVE for s in items):
            found.add(('service.extra', family))
    for exp in doc.get('acts_not_done', []):
        expected_kinds = {a['kind'] for e in doc.get('services', []) if e['family'] == exp['family']
                          for a in e.get('acts', [])}
        if exp['kind'] in expected_kinds:
            continue
        for s in by_family.get(exp['family'], []):
            if s.status in POSITIVE and any(a.kind == exp['kind'] and a.status == 'performed' and a.role == 'physician'
                                            for a in s.acts):
                found.add(('act_not_done.violated', f'{exp["family"]} {exp["kind"]}'))
    want = {(c['family'], c['subject']) for c in doc.get('conflicts', [])}
    got = {(inv.service(c.service).family if inv.service(c.service) else '?', c.subject) for c in inv.conflicts}
    found |= {('conflict.missing', f'{f} {s}') for f, s in want - got}
    found |= {('conflict.extra', f'{f} {s}') for f, s in got - want}
    roles = {a.role for a in inv.attributions}
    found |= {('attribution.missing', role) for role in doc.get('attributions', []) if role not in roles}
    asked = {c.fact for c in result.clarifications}
    found |= {('question.missing', name) for name in doc.get('questions', []) if name not in asked}
    unsupported = {u['act'] for u in result.completeness.get('unresolved_items', []) if u['reason'] == 'unsupported'}
    found |= {('unsupported.missing', act) for act in doc.get('unsupported', []) if act not in unsupported}
    if services.validate(inv, text):
        found.add(('inventory.invalid', ''))
    return found


class CorpusTests(SimpleTestCase):
    def test_every_document_reads_as_recorded(self):
        spec = json.loads((CORPUS / 'expectations.json').read_text(encoding='utf-8'))
        known = json.loads((CORPUS / 'known_differences.json').read_text(encoding='utf-8'))['documents']
        self.assertEqual(len(spec['documents']), 43)
        for doc in spec['documents']:
            with self.subTest(doc['id']):
                text = (CORPUS / doc['file']).read_text(encoding='utf-8')
                self.assertTrue(text.startswith('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT'))
                got = differences(text, doc)
                recorded = {(d['kind'], d['subject']) for d in known.get(doc['id'], {}).get('differences', [])}
                self.assertEqual(got, recorded, 'a reading changed: a new difference is a regression; a recorded one '
                                                'that disappeared must be removed from known_differences.json')

    def test_every_recorded_difference_has_its_reason(self):
        known = json.loads((CORPUS / 'known_differences.json').read_text(encoding='utf-8'))['documents']
        for doc_id, entry in known.items():
            self.assertTrue(entry.get('reason', '').strip(), doc_id)
