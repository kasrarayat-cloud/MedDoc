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


# --- routing:14 -----------------------------------------------------------------------------------------------

def colon_findings(sentence):
    return HEADER + f'Procedure: Colonoscopy\nFindings: {sentence}\n'


class R14ActNeededAfterADeniedFindingTests(unittest.TestCase):
    """routing:14 - a passage that states the act but denies the finding a further act would have needed ("...
    and no polyps were found to remove") is held, as it was at 57b4b3747: the denial is incidental to the stated
    act only when no such act follows it (status:12's readings stay performed)."""

    HELD = ('The colonoscope was advanced to the cecum and no polyps were found to remove.',
            'The colonoscope was advanced to the cecum; there were no polyps to remove.',
            'The colonoscope was advanced to the cecum and no polyps were identified for removal.',
            'The colonoscope was advanced to the cecum and no polyps were seen that required removal.',
            'The colonoscope was advanced to the cecum and no lesions were found to sample.',
            'The colonoscope was advanced to the cecum and no lesions were seen for endoscopic resection.')

    def test_the_claimed_input(self):
        sentence = self.HELD[0]
        text = colon_findings(sentence)
        status, cues = read(text, sentence)
        self.assertEqual(status, 'uncertain', cues)
        self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)
        proposals, _ = run_engine(text, [('45385', sentence)])
        self.assertTrue(held(proposals['45385']), proposals['45385'].status)
        self.assertIn('performed_status', [c.fact for c in proposals['45385'].clarifications])
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')  # the stated act still reaches it

    def test_the_variants(self):
        for sentence in self.HELD[1:]:
            text = colon_findings(sentence)
            with self.subTest(sentence=sentence):
                self.assertEqual(read(text, sentence)[0], 'uncertain')
                self.assertTrue(held(run_engine(text, [('45385', sentence)])[0]['45385']))

    def test_a_denied_finding_beside_the_stated_act_still_reads_performed(self):
        for sentence in ('The colonoscope was advanced to the cecum and no polyps were seen.',
                         'The colonoscope was advanced to the cecum and no polyps were seen on retroflexion in the rectum.',
                         'The colonoscope was advanced to the cecum and no polyps were seen despite an adequate preparation.',
                         'The colonoscope was advanced to the cecum and no polyps were seen throughout the colon.',
                         'The colonoscope was advanced to the terminal ileum without looping.',
                         'The colonoscope was advanced to the cecum without difficulty and no polyps were seen.',
                         'The colonoscope was advanced to the cecum and no polyps were seen, and the scope was withdrawn.'):
            text = colon_findings(sentence)
            with self.subTest(sentence=sentence):
                status, cues = read(text, sentence)
                self.assertEqual(status, 'performed', cues)
                self.assertTrue(ready(run_engine(text, [('45378', sentence)])[0]['45378']))
        sentence = 'The endoscope was advanced to the second part of the duodenum and no ulcers were seen.'
        text = HEADER + f'Procedure: EGD\nFindings: {sentence}\n'
        self.assertEqual(read(text, sentence)[0], 'performed')
        self.assertTrue(ready(run_engine(text, [('43235', sentence)])[0]['43235']))


# --- routing:20 -----------------------------------------------------------------------------------------------

EGD_BIOPSY = 'Two biopsies were taken from the antrum.'


def egd_after(nxt, line='EGD with biopsy.'):
    return (HEADER + f'Procedure: {line}\n{nxt}\nFindings: The gastroscope was advanced to the second part of the '
            f'duodenum. {EGD_BIOPSY}\n')


COLON_SNARE = 'A 6 mm sigmoid polyp was removed with a cold snare.'


def colon_after(nxt):
    return (HEADER + f'Procedure: Colonoscopy with cold snare polypectomy\n{nxt}\nFindings: The colonoscope was advanced '
            f'to the cecum. {COLON_SNARE}\n')


class R20ShortLineDenyingAnotherActTests(unittest.TestCase):
    """routing:20 - a short line after a described service line that denies another act or care step after naming
    it ("Sedation was not needed.", "Retroflexion: not performed") is no denial of the service: it reads performed
    and its codes are ready, as at 57b4b3747. Every other short denial still holds the service."""

    OTHER_ACTS = ('Sedation was not needed.', 'The patient did not require sedation.', 'Fluoroscopy was not used.',
                  'Images were not saved.', 'Anesthesia was not required.', 'Photographs were not taken.',
                  'IV sedation not required.', 'Propofol was not used.', 'Moderate sedation was not used.',
                  'Retroflexion could not be performed.', "Sedation wasn't needed.")

    def test_the_claimed_input_and_variants(self):
        for nxt in self.OTHER_ACTS:
            text = egd_after(nxt)
            with self.subTest(nxt=nxt):
                self.assertEqual(family(text, 'gi.egd'), 'performed')
                status, cues = read(text, 'EGD with biopsy.')
                self.assertEqual(status, 'performed', cues)
                self.assertTrue(ready(run_engine(text, [('43239', EGD_BIOPSY)])[0]['43239']))

    def test_the_colonoscopy_retroflexion_lines(self):
        for nxt in ('Retroflexion: not performed', 'Retroflexion was not performed.', 'Retroflexion not performed.'):
            text = colon_after(nxt)
            with self.subTest(nxt=nxt):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assertTrue(ready(run_engine(text, [('45385', COLON_SNARE)])[0]['45385']))

    def test_the_verification_documents_with_another_act_denied(self):
        for name, title, nxt, slug, picks in (
                ('gi-02', 'Esophagogastroduodenoscopy (EGD) with cold forceps biopsy.', 'Fluoroscopy was not used.',
                 'gi.egd', [('43239', 'Two cold forceps biopsies were taken from the gastric antrum for histology and '
                                      'Helicobacter pylori assessment.')]),
                ('gi-02', 'Esophagogastroduodenoscopy (EGD) with cold forceps biopsy.', 'Photographs were not taken.',
                 'gi.egd', [('43239', 'Two cold forceps biopsies were taken from the gastric antrum for histology and '
                                      'Helicobacter pylori assessment.')]),
                ('gi-03', 'Colonoscopy with cold snare polypectomy and cold forceps biopsy.',
                 'Chromoendoscopy was not used.', 'gi.colonoscopy',
                 [('45385', 'were each removed completely with a cold snare and retrieved (jar A)'),
                  ('45380', 'was sampled with cold forceps biopsy for histology (jar B)')])):
            original = doc(name)
            text = original.replace(title, title + '\n' + nxt)
            self.assertNotEqual(text, original)
            with self.subTest(name=name, nxt=nxt):
                self.assertEqual(family(text, slug), 'performed')
                proposals, _ = run_engine(text, picks)
                for code, _evidence in picks:
                    self.assertTrue(ready(proposals[code]), (code, proposals[code].clarifications))

    def test_the_same_denial_as_a_later_clause(self):
        text = HEADER + 'Procedure: EGD with biopsy; sedation was not needed.\nFindings: Biopsies were taken.\n'
        self.assertEqual(family(text, 'gi.egd'), 'performed')

    def test_a_denial_of_the_service_still_holds(self):
        for nxt in ('Not performed.', 'Patient declined.', 'It was not performed.', 'Cancelled.',
                    'Not performed - no sedation available.', 'Sedation was not needed; not performed.',
                    'The patient did not tolerate sedation.', 'Anesthesia was not available.',
                    'Sedation and procedure not performed.'):
            text = egd_after(nxt)
            with self.subTest(nxt=nxt):
                self.assertNotIn(family(text, 'gi.egd'), POSITIVE)
                status, cues = read(text, 'EGD with biopsy.')
                self.assertEqual(status, 'uncertain', cues)
                self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)
                self.assertFalse(ready(run_engine(text, [('43239', EGD_BIOPSY)])[0]['43239']))

    def test_after_a_bare_service_line_the_57b_hold_is_kept(self):
        text = egd_after('Sedation was not needed.', line='EGD')
        self.assertNotIn(family(text, 'gi.egd'), POSITIVE)


# --- routing:9 ------------------------------------------------------------------------------------------------

def procedure_line(line):
    return HEADER + 'Indication: Rectal bleeding.\nProcedure: ' + line + '\n'


class R9RefusalAfterTheInterventionTests(unittest.TestCase):
    """routing:9 - a refusal or "not performed" set off after the intervention of the service's own description
    ("EGD to D2 with biopsy, declined by the patient.") has no subject of its own: it may deny the whole service,
    so the service is held (never negated, never performed) and no extent is read from the line. An intervention
    that is the denial's own subject ("biopsies not taken", ", biopsy declined") still explains it."""

    HELD = (('Flexible sigmoidoscopy to 30 cm with biopsy, declined by the patient.', 'gi.flex_sig', '45330',
             'Flexible sigmoidoscopy'),
            ('EGD to D2 with biopsy, declined by the patient.', 'gi.egd', '43235', 'EGD'),
            ('Colonoscopy with cold snare polypectomy, not performed.', 'gi.colonoscopy', '45378', 'Colonoscopy'))
    VARIANTS = (('Colonoscopy to the cecum with biopsy, not performed.', 'gi.colonoscopy', '45378', 'Colonoscopy'),
                ('EUS with fine-needle biopsy, not performed.', 'gi.eus', '43259', 'EUS'),
                ('Colonoscopy with biopsy, not performed.', 'gi.colonoscopy', '45378', 'Colonoscopy'),
                ('EGD with dilation, patient declined.', 'gi.egd', '43235', 'EGD'),
                ('Flexible sigmoidoscopy to 30 cm with biopsy, patient declined.', 'gi.flex_sig', '45330',
                 'Flexible sigmoidoscopy'),
                ('EGD with biopsy (declined by the patient).', 'gi.egd', '43235', 'EGD'),
                ('EGD with biopsy and dilation - not performed.', 'gi.egd', '43235', 'EGD'))

    def assert_held(self, line, slug, code, cite):
        text = procedure_line(line)
        self.assertNotIn(family(text, slug), POSITIVE)
        status, cues = read(text, cite)
        self.assertEqual(status, 'uncertain', cues)
        self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)
        self.assertIsNone(fact_value(text, slug, 'extent'))
        proposals, _ = run_engine(text, [(code, cite)])
        self.assertFalse(ready(proposals[code]), proposals[code].status)

    def test_the_claimed_inputs(self):
        for line, slug, code, cite in self.HELD:
            with self.subTest(line=line):
                self.assert_held(line, slug, code, cite)

    def test_the_minimal_pairs_and_variants(self):
        for line, slug, code, cite in self.VARIANTS:
            with self.subTest(line=line):
                self.assert_held(line, slug, code, cite)
        text = procedure_line('EUS with fine-needle biopsy, declined by the patient.')
        self.assertNotIn(family(text, 'gi.eus'), POSITIVE)
        self.assertNotEqual(fact_value(text, 'gi.eus', 'tissue_sampling'), 'FNB')

    def test_an_intervention_denied_as_its_own_subject_keeps_the_service_performed(self):
        for line, slug, code, cite in (
                ('Colonoscopy with polypectomy, biopsies not taken.', 'gi.colonoscopy', '45378', 'Colonoscopy'),
                ('EGD to D2, biopsy declined by the patient.', 'gi.egd', '43235', 'EGD'),
                ('EGD to D2 with biopsy.', 'gi.egd', '43239', 'EGD'),
                ('Colonoscopy with polypectomy; however, biopsies were not taken.', 'gi.colonoscopy', '45378',
                 'Colonoscopy'),
                ('Colonoscopy with polypectomy, biopsy: not taken.', 'gi.colonoscopy', '45378', 'Colonoscopy')):
            text = procedure_line(line)
            with self.subTest(line=line):
                self.assertEqual(family(text, slug), 'performed')
                self.assertEqual(read(text, cite)[0], 'performed')
        text = procedure_line('EGD to D2, biopsy declined by the patient.')
        self.assertEqual(read(text, 'biopsy')[0], 'negated')  # the biopsy itself stays denied

    def test_status5_later_clause_holds_are_kept(self):
        for line, slug in (('Colonoscopy with biopsy; not performed.', 'gi.colonoscopy'),
                           ('EGD with dilation; patient declined.', 'gi.egd')):
            with self.subTest(line=line):
                self.assertNotIn(family(procedure_line(line), slug), POSITIVE)


# --- routing:7 ------------------------------------------------------------------------------------------------

EUS_LINE = 'EUS with fine-needle biopsy of the pancreatic head mass.'
EUS_P = f'Procedure: {EUS_LINE}\n'
EUS_I = 'Indication: A 2.4 cm pancreatic head mass on CT.\n'


class R7CancelledOrRescheduledFurtherDownTests(unittest.TestCase):
    """routing:7 - a denying status line one line further down (after the indication), a status value with a
    reason, "Rescheduled." under the procedure line, or a next line that names the same service and reschedules
    it holds the section-read service: never performed, no FNB fact, 43242 never ready, and held (never newly
    cancelled or negated)."""

    def assert_held(self, body):
        text = HEADER + body
        self.assertNotIn(family(text, 'gi.eus'), POSITIVE)
        self.assertNotEqual(fact_value(text, 'gi.eus', 'tissue_sampling'), 'FNB')
        status, cues = read(text, EUS_LINE)
        self.assertEqual(status, 'uncertain', cues)
        self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)
        proposals, _ = run_engine(text, [('43242', EUS_LINE)])
        self.assertFalse(ready(proposals['43242']), proposals['43242'].status)

    def assert_performed(self, body):
        text = HEADER + body
        self.assertEqual(family(text, 'gi.eus'), 'performed')
        self.assertEqual(read(text, EUS_LINE)[0], 'performed')

    def test_a_status_line_one_line_further_down(self):
        for line in ('Status: Cancelled - the patient had eaten breakfast.', 'Procedure status: Not performed.',
                     'Status: Cancelled.', 'Status: Not performed.', 'Status: Postponed until the INR is corrected.',
                     'The procedure was cancelled because the patient had eaten breakfast.'):
            with self.subTest(line=line):
                self.assert_held(EUS_P + EUS_I + line + '\n')

    def test_a_status_value_with_a_reason(self):
        for line in ('Status: Cancelled - the patient had eaten breakfast.',
                     'Status: Cancelled because the patient had eaten breakfast.',
                     'Status: Rescheduled to next week because the patient had eaten breakfast.',
                     'Procedure status: Rebooked for next week because of a scheduling conflict.'):
            with self.subTest(line=line):
                self.assert_held(EUS_P + line + '\n' + EUS_I)

    def test_rescheduled_under_the_procedure_line(self):
        for line in ('Rescheduled.', 'Rescheduled to next week.', 'Rebooked.', 'Moved to next week.'):
            with self.subTest(line=line):
                self.assert_held(EUS_P + line + '\n' + EUS_I)

    def test_a_next_line_naming_the_service_and_rescheduling_it(self):
        for line in ('The EUS will be rescheduled because the patient had eaten breakfast.',
                     'The EUS was rescheduled because the patient had eaten breakfast.', 'EUS will be rescheduled.',
                     'The procedure was rescheduled because the patient had eaten breakfast.'):
            with self.subTest(line=line):
                self.assert_held(EUS_P + line + '\n' + EUS_I)

    def test_ordinary_lines_keep_the_service_performed(self):
        for body in (EUS_P + EUS_I + 'Status: Completed.\n', EUS_P + 'Repeat EUS in 3 months.\n' + EUS_I,
                     EUS_P + EUS_I + 'Plan: Repeat EUS in 3 months.\n', EUS_P + 'No complications.\n' + EUS_I,
                     EUS_P + EUS_I + 'Status: stable.\n', EUS_P + 'Moved to recovery in stable condition.\n' + EUS_I,
                     EUS_P + 'This EUS was rescheduled from last week.\n' + EUS_I,
                     EUS_P + 'Rescheduled from last week; performed today without difficulty.\n' + EUS_I,
                     EUS_P + EUS_I + 'Plan: Status: pending pathology review.\n',
                     EUS_P + EUS_I + 'History: The procedure was cancelled once last year.\n',
                     EUS_P + 'ERCP with stent placement will be rescheduled to next week.\n' + EUS_I):
            with self.subTest(body=body):
                self.assert_performed(body)

    def test_a_status_line_speaks_for_the_nearest_service_line_above_it(self):
        text = (HEADER + 'Procedures:\nEGD with biopsy of the antrum.\nColonoscopy with cold snare polypectomy.\n'
                'Status: Cancelled - inadequate preparation.\n')
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        self.assertNotIn(family(text, 'gi.colonoscopy'), POSITIVE)
        self.assertEqual(read(text, 'Colonoscopy with cold snare polypectomy.')[0], 'uncertain')

    def test_heading_lines_are_not_counted_as_sentences_between(self):
        self.assert_held(EUS_P + 'Indication:\nA 2.4 cm pancreatic head mass on CT.\nWeight loss of 5 kg.\nPainless '
                                 'jaundice.\nSedation:\nMonitored anesthesia care.\nStatus: Cancelled - the patient had '
                                 'eaten breakfast.\n')

    def test_a_rescheduling_to_today_is_no_denial(self):
        self.assert_performed(EUS_P + 'Rescheduled to today; performed without difficulty.\n' + EUS_I)

    def test_an_abort_after_the_start_in_a_long_status_value_stays_incomplete(self):
        text = HEADER + ('Procedure: Colonoscopy with biopsy.\nStatus: Aborted at 30 cm because of looping in the '
                         'sigmoid colon.\n')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')
        status, cues = read(text, 'Colonoscopy with biopsy.')
        self.assertEqual(status, 'incomplete', cues)
