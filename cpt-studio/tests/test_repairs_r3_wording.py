"""Regressions for refutation round 3 over GI routing wording (round "3b", WORDING).

Each class reproduces one confirmed round-3 finding (routing:N or validation:N in the
round-3 triage) from its exact input, adds the variants the finding and its verifier list,
and pins the positive controls that keep ordinary notes working. Every new wording rule
here holds (an uncertain reading, with a non-silent cue); a regression from round 2b is
restored to the reading it had at 57b4b3747.

Routing runs for real, for the document's own service date and through the JSON round trip
the pipeline applies; the real validation engine assesses provider-shaped selections
against an empty in-memory reference. Synthetic text only.
"""
import json
import time
import unittest
from datetime import date
from pathlib import Path

from studio.gi.context import extract_context
from studio.gi.detect import route, status_for_span
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, RoutingResult, from_jsonable,
                          to_jsonable)
from studio.validation.engine import assess

HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
DOCS = Path(__file__).resolve().parent.parent / 'ops' / 'verification' / 'documents'
POSITIVE = ('performed', 'incomplete')
SILENT = 'uncertain: no performance evidence'


def doc(name):
    return next(DOCS.glob(f'{name}-*.txt')).read_text(encoding='utf-8')


def span(text, phrase, occurrence=0):
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(phrase, start + 1)
    return start, start + len(phrase)


def service_date(text):
    fact = extract_context(text)['service_date']
    return date.fromisoformat(fact.value) if fact.origin == 'document' and fact.value else None


def routed(text):
    """Routing as the pipeline stores it: for the document's own date, through JSON and back."""
    result = route(text, service_date(text))
    return from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(result))))


def read(text, phrase, occurrence=0):
    return status_for_span(text, *span(text, phrase, occurrence), service_date(text))


def family(text, slug):
    finding = routed(text).finding(slug)
    return finding.status if finding else None


def fact_value(text, slug, name):
    finding = routed(text).finding(slug)
    return next((f.value for f in (finding.facts if finding else ()) if f.name == name), None)


def run_engine(text, picks):
    """picks: (code, evidence phrase[, occurrence]). The proposals by code, and the whole result."""
    codes = []
    for index, pick in enumerate(picks):
        start, end = span(text, pick[1], pick[2] if len(pick) > 2 else 0)
        codes.append(ProviderCode(role='selected', system='cpt', code=pick[0], display='UNVERIFIED',
                                  evidence=(EvidenceSpan(0, start, end, text[start:end], True),), index=index))
    result = assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=extract_context(text), routing=routed(text),
                    normalized=NormalizedResponse('replay', 'test', codes=tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=service_date(text),
                    provider_status='succeeded', extraction_status='ok')
    return {p.code: p for p in result.proposals}, result


def check(proposal, check_id):
    return next((c for c in proposal.checks if c.id == check_id), None)


def ready(proposal):
    return (proposal.bucket, proposal.status) == ('selected', 'ready')


def held(proposal):
    return (proposal.bucket, proposal.status) == ('selected', 'needs_clarification')


# --- routing:3 ------------------------------------------------------------------------------------------------

def stopped_colonoscopy(label):
    return (HEADER + f'Procedure: Colonoscopy\nFindings:\n{label}\nThe colonoscope was advanced to the splenic flexure, '
            'where an obstructing mass was biopsied.\n')


STOPPED_BIOPSY = 'where an obstructing mass was biopsied'


class R3IntendedExtentLabelTests(unittest.TestCase):
    """routing:3 - an extent label led by an aim ("Intended extent: cecum") names the extent planned, never
    the extent reached: the incomplete colonoscopy stays incomplete, as it was at 57b4b3747. Only a label
    led by nothing but a determiner, a listed qualifier or the service's name reads as reached."""

    def assert_incomplete(self, text, slug='gi.colonoscopy', code='45380', evidence=STOPPED_BIOPSY,
                          extent='incomplete: splenic flexure'):
        self.assertEqual(fact_value(text, slug, 'extent'), extent)
        self.assertEqual(family(text, slug), 'incomplete')
        proposals, _ = run_engine(text, [(code, evidence)])
        self.assertIsNotNone(check(proposals[code], 'service.incomplete'))
        self.assertTrue(any('52' in c and '53' in c for c in proposals[code].modifier_considerations),
                        proposals[code].modifier_considerations)

    def test_the_claimed_inputs(self):
        for label in ('Intended extent: cecum', 'Expected extent: cecum', 'Target extent: cecum'):
            with self.subTest(label=label):
                self.assert_incomplete(stopped_colonoscopy(label))

    def test_the_listed_variants(self):
        for label in ('Goal extent: cecum', 'Desired extent: cecum', 'Planned extent: cecum',
                      'Intended extent of exam: cecum', 'Intended extent of the examination: cecum',
                      'The intended extent was the cecum.', 'Anticipated depth of insertion: cecum',
                      'Expected furthest extent: cecum', 'Maximal intended extent: cecum',
                      'Intended extent: cecum\nExtent reached: splenic flexure'):
            with self.subTest(label=label):
                self.assert_incomplete(stopped_colonoscopy(label))

    def test_the_egd_analog(self):
        text = (HEADER + 'Procedure: EGD\nFindings:\nIntended extent: second part of the duodenum\nThe gastroscope was '
                'advanced to the stomach, where a mass was biopsied.\n')
        self.assertEqual(fact_value(text, 'gi.egd', 'extent'), 'incomplete: stomach')
        self.assertEqual(family(text, 'gi.egd'), 'incomplete')

    def test_an_intended_depth_in_cm_is_not_the_depth_reached(self):
        text = (HEADER + 'Procedure: Flexible sigmoidoscopy\nFindings: Intended depth of insertion: 60 cm. The '
                'sigmoidoscope was advanced to 25 cm.\n')
        self.assertEqual(fact_value(text, 'gi.flex_sig', 'extent'), '25 cm')
        text = HEADER + 'Procedure: Flexible sigmoidoscopy\nFindings: Target depth of insertion: 60 cm.\n'
        self.assertIsNone(fact_value(text, 'gi.flex_sig', 'extent'))

    def test_reached_labels_still_read(self):
        """Positive controls: a plain label, a listed qualifier, a determiner, a separator or the service's name
        before it, and the intended + reached pair whose reached value is the cecum."""
        for label, extent in (('Extent: cecum', 'cecum'), ('Extent reached: terminal ileum', 'terminal ileum'),
                              ('Furthest extent reached: cecum.', 'cecum'),
                              ('The furthest extent reached was the cecum.', 'cecum'),
                              ('Colonoscopy extent: cecum', 'cecum'), ('Colonoscopy, extent: cecum', 'cecum'),
                              ('Actual extent: cecum', 'cecum'), ('Extent of exam: cecum', 'cecum'),
                              ('Prep adequate, extent: cecum', 'cecum'), ('Good prep - extent reached: cecum', 'cecum'),
                              ('- Extent: cecum', 'cecum'), ('1) Extent reached: cecum', 'cecum'),
                              ('Intended extent: cecum\nExtent reached: cecum', 'cecum'),
                              ('Intended extent: cecum\nActual extent reached: cecum', 'cecum')):
            text = HEADER + f'Procedure: Colonoscopy with cold snare polypectomy.\nFindings:\n{label}\nA 6 mm polyp was ' \
                            'removed with a cold snare.\n'
            with self.subTest(label=label):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), extent)
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assertTrue(ready(run_engine(text, [('45385', 'A 6 mm polyp was removed with a cold snare.')])[0]
                                      ['45385']))
        text = HEADER + 'Procedure: Flexible sigmoidoscopy\nFindings: Depth of insertion: 30 cm.\n'
        self.assertEqual(fact_value(text, 'gi.flex_sig', 'extent'), '30 cm')
