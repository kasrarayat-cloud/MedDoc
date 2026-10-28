"""Refutation r1 repairs, cluster B: check boxes, consent, modal predicates and the procedure line (studio/gi/services.py).

Each text is a fresh synthetic, fictional paraphrase written for the case under test; the expected readings are written
here, outside the reader. Every finding is read in its own shape, in at least two paraphrases or other positions, in the
other direction where it has one, and beside the controls that must keep reading as they did.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = date(2026, 10, 14)


def read(text):
    facts = gi_context.extract_context(text)
    return services.build(text, service_date=DAY, routing=detect.route(text, DAY), context_facts=facts)


def one(inv, family):
    found = [s for s in inv.services if s.family == family]
    assert len(found) == 1, f'{family}: {[(s.family, s.status) for s in inv.services]}'
    return found[0]


def kinds(svc, status='performed'):
    return sorted({a.kind for a in svc.acts if a.status == status})


def assess_codes(text, *picks):
    """The engine's assessment of ``text`` with the provider selecting each (code, quoted phrase)."""
    codes = []
    for code, phrase in picks:
        start = text.index(phrase)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(phrase), phrase, True),)))
    facts = gi_context.extract_context(text)
    result = assess(text=text, pages=(), context=facts, routing=detect.route(text, DAY),
                    normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=DAY, provider_status='succeeded')
    return {p.code: p.status for p in result.proposals}, [
        (u['family'], u['act'], u['second_review']) for u in result.completeness['unresolved_items']]


class ConsentPredicateTests(SimpleTestCase):
    """boxes-0. The consent rule read clearly done acts as what a consent was for: "After obtaining informed consent, we
    performed cold snare polypectomy ..." took "we performed" as the consent's predicate, "Informed consent was obtained
    and we then biopsied ..." missed the act verb that spans the mention, and "After anesthesia clearance for the
    procedure, hot snare polypectomy ... was performed" read the act's own predicate as the clearance's. The act read
    uncertain, so 45378 went ready, the act was never listed unresolved and no second review was sent. A consent is the
    subject only of an auxiliary predicate and only when no opening word governs it; a governed consent's phrase ends at
    its comma."""

    REPORT = HEAD + ('Colonoscopy report (fictional)\nDate of service: 2026-10-14\n\nPlace of service: Hospital outpatient '
                     'department\nIndication: Average-risk screening.\nProcedure: Colonoscopy\nTechnique: {line} The '
                     'colonoscope was advanced to the cecum and the examination was completed.\nFindings: Small internal '
                     'hemorrhoids.\nImpression: Rectal polyp, see above.\n')
    CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'

    def test_an_act_with_a_predicate_of_its_own_beside_a_consent_is_done(self):
        for line, kind in (
                ('After obtaining informed consent, we performed cold snare polypectomy of a 6 mm polyp in the rectum.',
                 'snare'),
                ("With the patient's consent, we performed cold snare polypectomy of a 6 mm polyp in the rectum.", 'snare'),
                ('Informed consent was obtained and we then biopsied a 10 mm flat lesion in the transverse colon.',
                 'biopsy'),
                ('After anesthesia clearance for the procedure, hot snare polypectomy of the 20 mm sigmoid polyp was '
                 'performed.', 'snare'),
                ('With cardiology approval to hold apixaban, hot snare polypectomy of the 20 mm sigmoid polyp was '
                 'performed.', 'snare'),
                ("Per the patient's permission to proceed, hot snare polypectomy of the 20 mm sigmoid polyp was "
                 "performed.", 'snare'),
                # other paraphrases and positions
                ('After obtaining informed consent, we took biopsies from the sigmoid polyp.', 'biopsy'),
                ("With the patient's consent, we removed the sigmoid polyp with a cold snare.", 'snare'),
                ('Following anesthesia clearance for the procedure, cold snare polypectomy of the sigmoid polyp was '
                 'performed.', 'snare'),
                ('After obtaining informed consent, the 6 mm rectal polyp was removed with a cold snare.', 'snare'),
                ('Once consent for EMR was obtained, the 25 mm lesion was lifted and removed en bloc by EMR.', 'emr'),
                ('Informed consent was obtained and the 6 mm rectal polyp was then snared.', 'snare')):
            with self.subTest(line=line):
                text = self.REPORT.format(line=line)
                self.assertIn(kind, kinds(one(read(text), 'gi.colonoscopy')))
                statuses, unresolved = assess_codes(text, ('45378', self.CECUM))
                self.assertEqual(statuses, {'45378': 'needs_clarification'})
                self.assertEqual(unresolved, [('gi.colonoscopy', kind, True)])

    def test_a_whole_service_with_its_own_predicate_beside_a_consent_is_documented(self):
        text = self.REPORT.format(line="With the patient's consent, we performed an EGD to the second portion of the "
                                       "duodenum with biopsies of the gastric antrum.")
        inv = read(text)
        self.assertEqual(one(inv, 'gi.egd').status, 'performed')
        _, unresolved = assess_codes(text, ('45378', self.CECUM))
        self.assertIn(('gi.egd', '', True), unresolved)

    def test_what_a_consent_is_for_is_still_held(self):
        """The other direction: an item inside what a consent is for is never done (held as uncertain, or no act at all
        where its clause has no act predicate; never excluded, never sent), whether the consent is the clause's subject
        or governed by its opening word."""
        for line, held in (
                ('Consent was obtained for biopsy and cold snare polypectomy.', ['biopsy', 'snare']),
                ('Informed consent was obtained after explaining the risks of colonoscopy with polypectomy.', ['snare']),
                ('Prior authorization was obtained for cold snare polypectomy.', ['snare']),
                ('Informed consent was given for biopsy, cold snare polypectomy and tattoo.', ['biopsy', 'snare',
                                                                                              'tattoo']),
                ('Written consent for biopsy, cold snare polypectomy and tattoo was obtained.', ['biopsy', 'snare',
                                                                                                'tattoo']),
                ('Once consent for EMR was obtained, the 25 mm lesion was marked.', ['emr']),
                ('After obtaining consent for biopsy and cold snare polypectomy, the colonoscope was reinserted.', []),
                ('With consent for cold snare polypectomy, a 6 mm polyp was seen in the rectum.', [])):
            with self.subTest(line=line):
                text = self.REPORT.format(line=line)
                colon = one(read(text), 'gi.colonoscopy')
                self.assertEqual([k for k in kinds(colon) if k in ('biopsy', 'snare', 'tattoo', 'emr')], [])
                self.assertEqual([k for k in kinds(colon, 'uncertain') if k in held], held)
                self.assertEqual(kinds(colon, 'negated'), [])
                self.assertEqual(assess_codes(text, ('45378', self.CECUM)), ({'45378': 'ready'}, []))
