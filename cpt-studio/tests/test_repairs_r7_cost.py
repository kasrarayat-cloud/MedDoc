"""Round 7 findings in the must-fix class "stage time or memory limits" (the final round under the owner's decision of
2026-10-25), and the bounded child's answer when memory runs out.

bounded:0 / regression:0 - pairing a strict check-box row reads each option in its own line window and kept every
  read in the analysis memo, and the line's mark cap left the document's unbounded: 64-mark status rows one per line
  overran the analyze stage's memory from about 250,000 characters. A row with a mark past the document's first
  B3_DOCUMENT_MARKS is never paired: held, with a cue that says why.
bounded:1 - the assess stage routes the document again and then validates, under the analyze stage's limits, so a
  document the analyze stage read in time could be sent and then never assessed. The assess stage now has twice the
  analyze stage's time and its memory plus a validation allowance; from_jsonable resolves a dataclass's field types
  once per class.
bounded:2 - a response citing tens of thousands of exact spans inside the 4 MiB cap exhausted the assess child after
  the send: a response citing more than MAX_EVIDENCE passages is refused whole, by count.
bounded:3 - the status-line label hold read and memoised a box window for every performed mention of a box-free text.
bounded:4 - the EGD location reader read a listed clause's locations once per intervention.
bounded:5 - the own-line negation check read a clause window per negation word on the service's line.
bounded:6 - a memory overrun could leave the bounded child without an answer, so the stage said it failed
  unexpectedly instead of naming the memory limit: the answer is now built before the limit is set.
validation:0 - the doubt guard's other-exam test was quadratic in one long sentence, outside every budget.
validation:1, validation:2 - the gi.other opener check rescanned a passage once per routed opener and appended every
  match once per passage.
declared:8 (and the list shapes of bounded:1 and bounded:3) - one service's name repeated in a list overran the
  analyze stage from about 40,000 characters, not the 70,000 recorded: a document naming procedures more than
  MAX_SERVICE_MENTIONS times is not read (the analyze stage fails with a plain message and nothing is sent).

Each cost pin runs the stage's own child on the round's input under a deadline well under the stage's; the reading
pins compare with what the code read before the repair. Synthetic data only; no network.
"""
import bisect
import json
import pickle
import random
import unittest
from dataclasses import replace
from datetime import date
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import bounded, jobs, models
from studio import types as studio_types
from studio.gi import context as gi_context
from studio.gi import cues, detect
from studio.providers import corti
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, ProviderRequest, ReferenceSourceInfo,
                          RoutingResult, from_jsonable, to_jsonable)
from studio.validation import checks, engine
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.test_repairs_r4d_sections2 import S3_QUESTION, HeldOrReadyAssertions, s3_note
from tests.test_repairs_r3_sections import read

HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n\n'
DAY = date(2026, 10, 21)
MIB = 1024 * 1024
LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
# A cost pin's own deadline: well under the stage's, and several times what the repaired code takes here.
PIN_SECONDS = 30


def sized(prefix, unit, chars, suffix=''):
    return HEADER + prefix + unit * max(1, (chars - len(HEADER) - len(prefix) - len(suffix)) // len(unit)) + suffix


def analyze_child(text, seconds=PIN_SECONDS):
    """The analyze stage's child as stage_analyze runs it, under the pin's deadline and the stage's memory."""
    return bounded.run_bounded(jobs._analyze_child, text, {}, settings.MAX_SERVICE_MENTIONS, seconds=seconds,
                               memory_bytes=settings.BOUNDED_MEMORY_BYTES)


def assess_child(text, code, spans, seconds=PIN_SECONDS):
    """The assess stage's child as stage_assess runs it, with ``code`` selected and citing ``spans``."""
    source = ReferenceSourceInfo(key='cms-pfs-rvu26d', kind='cms-pfs', publisher='CMS', title='PFS', release='RVU26D',
                                 url='', sha256='', effective_start='2026-01-01', effective_end='2026-12-31',
                                 license_note='', scope_note='')
    reference = InMemoryReferenceLookup([source], {source.key: {(code, ''): {
        'status': 'A', 'global_days': '000', 'mult_proc': '2', 'endo_base': None, 'pctc': '0'}}})
    evidence = tuple(EvidenceSpan(0, s, e, text[s:e], True) for s, e in spans)
    normalized = NormalizedResponse('corti', corti.ADAPTER_VERSION, codes=(
        ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED', evidence=evidence, index=0),))
    facts = {name: from_jsonable(type(fact), to_jsonable(fact)) for name, fact in gi_context.extract_context(text).items()}
    detect._analysis.cache_clear()
    _, result = bounded.run_bounded(
        jobs._assess_child, text, DAY, (PageSpan(1, 0, len(text)),), facts, normalized, reference, 'succeeded', 'ok', (),
        seconds=seconds, memory_bytes=settings.ASSESS_MEMORY_BYTES)
    return {p.code: p for p in result.proposals}


def quote(text, phrase):
    at = text.index(phrase)
    return [(at, at + len(phrase))]


# --- bounded:0 / regression:0: the document's marks are paired up to a cap ----------------------------------------

FILLER = 'Consent signed: ☒ Yes ☐ No\n'  # two marks, no service, intervention or option a reader holds
CAP_HEAD = HEADER + 'Procedure: Colonoscopy with biopsy.\nFindings: The colonoscope was advanced to the cecum.\n'
CAP_ROWS = (('Biopsy: ☒ Done ☐ Not done', 'Biopsy', 'performed'),
            ('☒ Biopsy ☐ Cold snare polypectomy', 'Biopsy', 'performed'),
            ('Biopsy ☒ | Cold snare polypectomy ☐', 'Cold snare polypectomy', 'negated'),
            ('Colonoscopy: ☒ Completed ☐ Incomplete', 'Colonoscopy:', 'performed'))


def late_row_status(row, phrase, fillers):
    text = CAP_HEAD + FILLER * fillers + row + '\n'
    start = text.rindex(phrase)
    return detect.status_for_span(text, start, start + len(phrase), DAY)


class DocumentMarkCapTests(SimpleTestCase):
    def test_a_row_before_the_cap_reads_as_it_did(self):
        fillers = detect.B3_DOCUMENT_MARKS // 2 - 2  # two marks each: with the row's own two, still within the cap
        for row, phrase, status in CAP_ROWS:
            with self.subTest(row=row):
                self.assertEqual(late_row_status(row, phrase, fillers)[0], status)
                self.assertEqual(late_row_status(row, phrase, 0)[0], status)

    def test_a_row_with_a_mark_past_the_cap_is_held_and_says_why(self):
        for row, phrase, _ in CAP_ROWS:
            with self.subTest(row=row):
                status, row_cues = late_row_status(row, phrase, detect.B3_DOCUMENT_MARKS // 2 + 1)
                self.assertEqual(status, 'uncertain', row_cues)
                self.assertIn(f'the document has more than {detect.B3_DOCUMENT_MARKS:,} check boxes up to it',
                              row_cues[0])
                self.assertTrue(row_cues[0].startswith(detect._B3_HOLD_PREFIX), row_cues[0])

    def test_one_plain_box_past_the_cap_keeps_its_reading(self):
        """A row of one plain box is never paired anywhere, so the cap changes nothing for it."""
        for row, status in (('Biopsy ☒', 'performed'), ('☐ Biopsy', 'negated')):
            with self.subTest(row=row):
                self.assertEqual(late_row_status(row, 'Biopsy', detect.B3_DOCUMENT_MARKS // 2 + 1)[0], status)

    def test_the_cap_is_where_the_text_puts_it_whatever_is_read_first(self):
        text = CAP_HEAD + FILLER * (detect.B3_DOCUMENT_MARKS // 2 + 3)
        an = detect._analysis(text, DAY)[0]
        marks = [m.start() for m in detect._B3_MARK_GLYPH.finditer(text)]
        self.assertEqual(detect._B3_document_cap(an), marks[detect.B3_DOCUMENT_MARKS])
        short = CAP_HEAD + FILLER * 3
        self.assertGreater(detect._B3_document_cap(detect._analysis(short, DAY)[0]), len(short))

    def test_64_mark_status_rows_one_per_line_are_read_within_the_analyze_limits(self):
        """The round's input: 300,000 characters of 64-mark rows, which overran the analyze child's memory."""
        text = sized('Procedure: Colonoscopy\nFindings:\n', 'Colonoscopy: ' + '☒ TBD ☐ Done ' * 32 + '\n', 300_000)
        self.assertGreater(len(text), 299_000)
        facts, service_date, data = analyze_child(text)
        self.assertEqual(service_date, DAY)


# --- bounded:3: no box window is read for a box-free label --------------------------------------------------------

class LabelHoldReadsNoBoxFreeWindowTests(SimpleTestCase):
    def test_a_box_free_list_memoises_no_status_line(self):
        text = HEADER + 'Procedure: EUS\nFindings: ' + ('EUS; ' * 199 + 'EUS. ') * 10 + '\n'
        detect._analysis.cache_clear()
        detect.route(text, DAY)
        an = detect._analysis(text, DAY)[0]
        self.assertGreater(len(an.services), 1900)
        self.assertEqual([k for k in an.memo if isinstance(k, tuple) and k and k[0] == 'b2-status-line'], [])

    def test_a_label_beside_a_mark_still_reads_its_hold_word(self):
        text = HEADER + 'Procedure: Colonoscopy\nColonoscopy: ☒ Incomplete ☐ Completed\n'
        start = text.index('Colonoscopy:')
        self.assertEqual(detect.status_for_span(text, start, start + len('Colonoscopy'), DAY)[0], 'uncertain')


# --- bounded:4: a listed clause's locations are read once ---------------------------------------------------------

def egd_location_before(an, interventions):
    """_egd_location as it read before round 7: every clause once per intervention it holds."""
    found = []
    for span in interventions.evidence:
        for cs, ce in an.lay.clauses_for(span.start, span.end):
            hits = sorted(((m.start(), -(m.end() - m.start()), m.end(), label) for label, p in cues.UPPER_LOCATIONS
                           for m in p.finditer(an.text, cs, ce)))
            last_end = -1
            for start, _, end, label in hits:
                if start >= last_end:
                    found.append((label, detect._span(an.text, start, end)))
                    last_end = end
    found.sort(key=lambda item: item[1].start)
    return detect._joined('location', found)


class EgdLocationOnceTests(SimpleTestCase):
    def test_the_location_fact_is_the_one_read_clause_by_intervention_gave(self):
        body = ('Findings: Band ligation of the distal esophageal varix and band ligation of the mid esophageal varix '
                'were performed today; biopsy of the gastric antrum and biopsy of the duodenum were taken.\n'
                'A second band ligation of the gastroesophageal junction varix was performed.\n')
        for text in (HEADER + 'Procedure: EGD with band ligation and biopsy\n' + body,
                     HEADER + 'Procedure: EGD\nFindings: ' + 'band ligation of the distal esophageal varix and ' * 40
                     + 'was performed today.\n'):
            an = detect._analysis(text, DAY)[0]
            facts = {fact.name: fact for fact in detect.route(text, DAY).finding('gi.egd').facts}
            with self.subTest(text=text[len(HEADER):60]):
                self.assertGreater(len(facts['interventions'].evidence), 1)
                self.assertEqual(detect._egd_location(an, facts['interventions']),
                                 egd_location_before(an, facts['interventions']))

    def test_an_egd_report_listing_band_ligations_is_read_within_the_analyze_limits(self):
        """The round's input at 75,000 characters, which overran the analyze child's memory. It names the ligation
        about 1,500 times, past MAX_SERVICE_MENTIONS, so since WIP 8k the child refuses it with the count, in time
        and memory (refutation r1 reran this pin at 9086a427: it had unpacked the count as a reading). A list just
        under the cap is still read, and its location is still the esophagus."""
        unit = 'band ligation of the distal esophageal varix and '
        text = sized('Procedure: EGD\nFindings: ', unit, 75_000, 'was performed today.\n')
        refused = analyze_child(text)
        self.assertIsInstance(refused, int)
        self.assertGreater(refused, settings.MAX_SERVICE_MENTIONS)
        text = sized('Procedure: EGD\nFindings: ', unit, len(unit) * (settings.MAX_SERVICE_MENTIONS // 2),
                     'was performed today.\n')
        facts, _, data = analyze_child(text)
        egd = from_jsonable(RoutingResult, data).finding('gi.egd')
        self.assertIn('esophagus', next(f.value for f in egd.facts if f.name == 'location'))


# --- bounded:5: a service line of many negation words -------------------------------------------------------------

class OwnLineNegationWordsTests(HeldOrReadyAssertions, unittest.TestCase):
    def test_a_line_of_up_to_the_cap_still_reads_its_own_denial(self):
        for line in ('No biopsies were taken.', 'Biopsies were not taken; no bleeding, no perforation, no pain.',
                     'No biopsies were taken; ' + ', '.join(['no'] * (detect._S2_OWN_LINE_TOKENS - 1)) + '.'):
            with self.subTest(line=line):
                self.assertEqual(read(s3_note(S3_QUESTION, line), line)[0], 'negated')

    def test_a_line_of_more_is_held_by_the_answer_above_never_excluded(self):
        line = 'No biopsies were taken; ' + ', '.join(['no'] * detect._S2_OWN_LINE_TOKENS) + '.'
        text = s3_note(S3_QUESTION, line)
        self.assertIn('the line above it ends in an answer', read(text, line)[1][0])
        self.assert_held_never_excluded(text, '43239', line)

    def test_a_service_line_of_many_negation_words_is_read_within_the_analyze_limits(self):
        """The round's input without the question above (every later line joins the sentence): it overran the
        analyze stage from about 200,000 characters."""
        text = sized('Procedure: EGD\nFindings:\n', 'Biopsies were taken' + ', no' * 100 + '\n', 300_000)
        analyze_child(text)
        text = sized('Procedure: EGD\nFindings:\n', S3_QUESTION + '\nBiopsies were taken' + ', no' * 100 + '\n', 300_000)
        analyze_child(text)


# --- declared:8, bounded:1, bounded:3: a document naming procedures past the cap is not read ----------------------

@override_settings(**LIVE)
class MentionCapStageTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(f.member(self.ws, f.user('reviewer')))
        self.provider = FakeProvider(selections=[('43237', 'Procedure: EUS')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_paste(self, text):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def test_a_document_naming_procedures_past_the_cap_is_not_read_and_nothing_is_sent(self):
        limit = settings.MAX_SERVICE_MENTIONS
        encounter_id = self.run_paste(HEADER + 'Procedure: EUS\nFindings: ' + 'EUS, ' * limit + 'done.\n')
        job = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.ANALYZE)
        self.assertEqual(job.state, models.Job.FAILED)
        self.assertEqual(job.error, jobs.MENTIONS_MESSAGE.format(count=limit + 1, limit=limit))
        self.assertIn('nothing was sent', job.error)
        self.assertEqual(self.provider.sent, [])
        self.assertFalse(models.RoutingRun.objects.filter(revision__encounter_id=encounter_id).exists())
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id).exists())

    def test_at_the_cap_the_document_is_read(self):
        limit = settings.MAX_SERVICE_MENTIONS
        encounter_id = self.run_paste(HEADER + 'Procedure: EUS\nFindings:\n' + 'EUS\n' * (limit - 1))
        self.assertEqual(models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.ANALYZE).state,
                         models.Job.SUCCEEDED)
        self.assertEqual(len(self.provider.sent), 1)

    def test_the_child_counts_before_reading(self):
        text = HEADER + 'Procedure: EUS\nFindings: ' + 'EUS, ' * 20 + 'done.\n'
        self.assertEqual(jobs._analyze_child(text, {}, 20), 21)
        self.assertEqual(detect.service_mention_count(text), 21)
        self.assertEqual(len(jobs._analyze_child(text, {}, 21)), 3)

    def test_the_list_shapes_of_the_round_are_refused_at_once(self):
        for prefix, unit in (('Findings: ', 'EUS, '), ('Findings:\n', 'EUS\n'), ('Findings: ', 'EUS; ' * 199 + 'EUS. '),
                             ('Findings:\n', 'EGD ' * 237 + '\n')):
            text = sized('Procedure: EUS\n' + prefix, unit, 230_000)
            with self.subTest(unit=unit[:12]):
                self.assertIsInstance(analyze_child(text, seconds=10), int)


# --- bounded:1: the assess stage has the analyze stage's limits and as much again for the validation ---------------

@override_settings(**LIVE)
class AssessLimitsTests(TestCase):
    def test_the_assess_stage_has_twice_the_analyze_stages_time_and_a_validation_allowance(self):
        deadlines = settings.JOB_DEADLINE_SECONDS
        self.assertGreaterEqual(deadlines['assess'], 2 * deadlines['analyze'])
        self.assertGreaterEqual(settings.ASSESS_MEMORY_BYTES, settings.BOUNDED_MEMORY_BYTES + 256 * MIB)

    def test_each_stage_runs_its_child_under_its_own_limits(self):
        ws = f.workspace()
        self.client.force_login(f.member(ws, f.user('reviewer')))
        provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        calls = []
        real = bounded.run_bounded

        def spy(fn, *args, seconds, memory_bytes):
            calls.append((fn.__name__, seconds, memory_bytes))
            return real(fn, *args, seconds=seconds, memory_bytes=memory_bytes)

        with mock.patch('studio.jobs.get_provider', return_value=provider), mock.patch.object(bounded, 'run_bounded', spy):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
            drain()
        self.assertIn(('_analyze_child', settings.JOB_DEADLINE_SECONDS['analyze'], settings.BOUNDED_MEMORY_BYTES), calls)
        self.assertIn(('_assess_child', settings.JOB_DEADLINE_SECONDS['assess'], settings.ASSESS_MEMORY_BYTES), calls)

    def test_from_jsonable_resolves_each_dataclass_once_and_rebuilds_the_same_routing(self):
        text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope was advanced to '
                'the cecum. A 6 mm polyp was removed with a cold snare.\n')
        routing = detect.route(text, DAY)
        data = to_jsonable(routing)
        studio_types._fields_of.cache_clear()
        self.assertEqual(from_jsonable(RoutingResult, data), routing)
        first = studio_types._fields_of.cache_info()
        self.assertEqual(from_jsonable(RoutingResult, data), routing)
        second = studio_types._fields_of.cache_info()
        self.assertEqual(second.misses, first.misses)
        self.assertGreater(second.hits, first.hits)


# --- bounded:2: a response citing more passages than the cap is refused whole -------------------------------------

def response(text, *, selected=0, candidate=0, alternative=0):
    def evidences(count):
        return [{'contextIndex': 0, 'start': 0, 'end': 9, 'text': text[:9]} for _ in range(count)]
    return json.dumps({'codes': [{'system': 'cpt', 'code': '45378', 'evidences': evidences(selected),
                                  'alternatives': [{'code': '45380', 'evidences': evidences(alternative)}]}],
                       'candidates': [{'system': 'cpt', 'code': '45385', 'evidences': evidences(candidate)}]}).encode()


class EvidenceCapTests(SimpleTestCase):
    def normalize(self, data, text=HEADER):
        request = ProviderRequest(provider='corti', adapter_version=corti.ADAPTER_VERSION, body={}, canonical_sha256='0',
                                  contexts=(text,))
        return corti.normalize_coding_response('corti', request, data)

    def test_a_response_citing_more_passages_than_the_cap_is_refused_by_count(self):
        cap = corti.MAX_EVIDENCE
        for split in ((cap + 1, 0, 0), (cap - 10, 6, 5), (1, cap, 0), (0, 0, cap + 1)):
            with self.subTest(split=split):
                result = self.normalize(response(HEADER, selected=split[0], candidate=split[1], alternative=split[2]))
                self.assertTrue(result.refused)
                self.assertEqual(result.codes, ())
                self.assertIn(f'it cites {cap + 1} evidence passages, more than the {cap} this adapter accepts',
                              result.problems[0])

    def test_at_the_cap_the_response_is_read(self):
        cap = corti.MAX_EVIDENCE
        result = self.normalize(response(HEADER, selected=cap - 2, candidate=1, alternative=1))
        self.assertFalse(result.refused)
        self.assertEqual(sum(len(code.evidence) for code in result.codes), cap)

    def test_a_malformed_entry_is_counted_without_failing(self):
        data = json.dumps({'codes': ['not an object', {'system': 'cpt', 'code': '45378', 'evidences': 'not a list',
                                                       'alternatives': ['x', {'code': '45380'}]}],
                           'candidates': []}).encode()
        result = self.normalize(data)
        self.assertFalse(result.refused)
        self.assertEqual([c.code for c in result.codes], ['45378', '45380'])


# --- validation:0: the doubt guard's containment test is a bisection ----------------------------------------------

class DoubtGuardContainmentTests(SimpleTestCase):
    def test_inside_answers_what_the_scan_it_replaces_answered(self):
        rng = random.Random(7)
        for _ in range(300):
            spans = []
            for _ in range(rng.randrange(0, 12)):
                start = rng.randrange(0, 60)
                spans.append((start, start + rng.randrange(0, 15)))
            inside = checks._V2_inside(list(spans))
            for p in range(-2, 80):
                self.assertEqual(inside(p), any(a <= p < b for a, b in spans), (spans, p))

    def test_one_long_sentence_of_other_exam_phrases_is_assessed_within_the_limits(self):
        """The round's inputs, which overran the assess child after the request was sent (aaf517e took 1.3 s)."""
        for unit, count in (('physical exam ', 20_000), ('DRE exam ', 15_000)):
            text = (HEADER + 'Procedure: Anoscopy\nFindings: Anoscopy revealed grade 2 internal hemorrhoids; '
                    + unit * count + 'normal.\n')
            with self.subTest(unit=unit):
                proposal = assess_child(text, '46600', quote(text, 'Procedure: Anoscopy'))['46600']
                self.assertEqual((proposal.bucket, proposal.status), ('selected', 'ready'))


# --- validation:1, validation:2: the opener check reads a passage once ---------------------------------------------

def opens_with_before(text, start, end, code, names, day):
    """checks._VAL_opens_with as it read before round 7: every overlapped sentence, per call."""
    if not names or start >= end:
        return False
    an = detect._analysis(text, day)[0]
    sentences = an.lay.sentences
    index = max(bisect.bisect_right(sentences, (start, 1 << 62)) - 1, 0)
    while index < len(sentences) and sentences[index][0] < end:
        if sentences[index][1] > start:
            name = checks._VAL_lead_name(an, text, index, day)
            if name and checks._VAL_owns(code, name):
                said = checks._VAL_name(name)
                if any(said == checks._VAL_name(other) or said.startswith(checks._VAL_name(other) + ' ')
                       or checks._VAL_same_procedure(code, other, name) for other in names):
                    return True
        index += 1
    return False


def unnamed_other_before(own, text, routing, day, code):
    """engine._unnamed_other as it read before round 7: the opener check name by name, every match per passage."""
    if not any(r.status in checks.POSITIVE and checks._VAL_states_no_procedure_of_its_own(text, r, day) for r in own):
        return own, ()
    other = routing.finding(engine.OTHER_GI)
    done = [m for m in (other.mentions if other else ())
            if m.status in checks.POSITIVE and checks._VAL_owns(code, m.span.text)
            and not checks._VAL_told_act(text, m.span.start, m.span.end, day)]
    names = engine._VAL_overlap_test([(m.span.start, m.span.end) for m in done])
    openings = [sentence for sentence in checks._VAL_opening_sentences(text, day) if names(*sentence)]
    opened = engine._VAL_overlap_test(openings)
    openers = [m for m in done if opened(m.span.start, m.span.end)]
    opening_names = [m.span.text for m in openers]
    doubted = None
    marked, speaks = [], []
    for reading in own:
        if (reading.status in checks.POSITIVE and checks._VAL_states_no_procedure_of_its_own(text, reading, day)
                and not checks.names_procedure(text, reading.start, reading.end, code, day)):
            routed_done = names(reading.start, reading.end) or opened(reading.start, reading.end)
            counted = False
            if routed_done or (opening_names and checks.by_section_alone(reading)):
                doubted = checks._VAL_doubted(text, code, day) if doubted is None else doubted
                counted = not doubted and routed_done
                if not routed_done:
                    matched = [m for m in openers
                               if opens_with_before(text, reading.start, reading.end, code, [m.span.text], day)]
                    counted = not doubted and bool(matched)
                    speaks += [(m.span.start, m.span.end) for m in matched]
            if not counted:
                reading = replace(reading, unnamed=True, judged_by=checks._V2_judged_by(text, reading, day))
        marked.append(reading)
    return tuple(marked), tuple(dict.fromkeys(speaks))


OPENER_DOCUMENTS = (
    'Procedure: Anoscopy\nFindings: Anoscopy revealed grade 2 internal hemorrhoids. Banding sites well healed.\n',
    'Procedure: Anoscopy\nProcedure: Anoscopy with hemorrhoid banding\nFindings: Anoscopy with hemorrhoid banding was '
    'uneventful. Anoscopy revealed grade 2 internal hemorrhoids. Grade 2 internal hemorrhoids were seen.\n',
    'Procedure: Hemorrhoid banding\nProcedure: Anoscopy\nFindings: Hemorrhoid banding of the right posterior column. '
    'Anoscopy showed grade 3 internal hemorrhoids. Banding sites well healed.\n',
    ('Procedure: Anoscopy\nFindings: Anoscopy revealed grade 2 internal hemorrhoids.\n') * 6,
    'Procedure: Anoscopy\n' * 5 + 'Indication: Rectal bleeding.\nFindings: Biopsy and anoscopy revealed grade 2 internal '
    'hemorrhoids. Anoscopy revealed grade 2 internal hemorrhoids. Anoscopy was not performed.\n',
    # a lead and an opener that are the same single procedure under other names (_VAL_same_procedure)
    'Procedure: High-resolution anoscopy\nFindings: Anoscopy revealed grade 2 internal hemorrhoids. Banding sites well '
    'healed.\n',
    'Procedure: Rubber band ligation of internal hemorrhoids\nFindings: Hemorrhoid banding of the right posterior column. '
    'Grade 2 internal hemorrhoids were seen.\n',
    'Procedure: Anoscopy\nProcedure: High resolution anoscopy\nFindings: High resolution anoscopy showed grade 3 internal '
    'hemorrhoids. Anoscopy revealed grade 2 internal hemorrhoids.\n',
    'Procedure: RBL\nFindings: Rubber band ligation of the left lateral column was performed. Banding of the right '
    'anterior column.\n',
)


class OpenerCheckTests(SimpleTestCase):
    def test_the_marked_readings_and_the_mentions_spoken_for_are_those_the_name_by_name_check_gave(self):
        compared = 0
        for body in OPENER_DOCUMENTS:
            text = HEADER + body
            routing = detect.route(text, DAY)
            spans = [(s, e) for s, e in detect._analysis(text, DAY)[0].lay.sentences if e > s and text[s:e].strip()]
            evidence = tuple(EvidenceSpan(0, s, e, text[s:e], True) for s, e in spans)
            for code in ('46600', '46221'):
                own = checks._V2_judged_away(text, checks.evidence_readings(text, evidence, DAY), DAY)
                with self.subTest(body=body[:40], code=code):
                    self.assertEqual(engine._unnamed_other(own, text, routing, DAY, code),
                                     unnamed_other_before(own, text, routing, DAY, code))
                    compared += 1
        self.assertEqual(compared, 2 * len(OPENER_DOCUMENTS))

    def test_the_opener_check_answers_as_it_did(self):
        for body in OPENER_DOCUMENTS:
            text = HEADER + body
            finding = detect.route(text, DAY).finding(engine.OTHER_GI)
            names = [m.span.text for m in finding.mentions] if finding else []
            for s, e in detect._analysis(text, DAY)[0].lay.sentences:
                for code in ('46600', '46221'):
                    with self.subTest(body=body[:30], sentence=text[s:e][:30], code=code):
                        self.assertEqual(checks._VAL_opens_with(text, s, e, code, names, DAY),
                                         opens_with_before(text, s, e, code, names, DAY))

    def test_a_code_citing_every_findings_sentence_beside_many_openers_is_assessed_within_the_limits(self):
        """The round's input (b): 3,500 short reports in one paste, 46600 citing each findings sentence."""
        text = HEADER + ('Procedure: Anoscopy\nFindings: Anoscopy revealed grade 2 internal hemorrhoids.\n') * 3500
        phrase = 'Anoscopy revealed grade 2 internal hemorrhoids.'
        spans, at = [], text.find(phrase)
        while at >= 0:
            spans.append((at, at + len(phrase)))
            at = text.find(phrase, at + 1)
        assess_child(text, '46600', spans)

    def test_one_cited_paragraph_beside_many_openers_is_assessed_within_the_limits(self):
        text = (HEADER + 'Procedure: Anoscopy\n' * 2200 + 'Indication: Rectal bleeding.\nFindings: '
                + 'Biopsy and anoscopy revealed grade 2 internal hemorrhoids. ' * 2200
                + 'Anoscopy revealed grade 2 internal hemorrhoids.\n')
        start = text.index('Biopsy and anoscopy')
        assess_child(text, '46600', [(start, len(text) - 1)])


# --- bounded:6: a memory overrun is always answered as one -------------------------------------------------------

def _memory_error_with_no_memory_left():
    """MemoryError in the child with pickling failing too, as it does while the failed call's frames still hold the
    address space (round 7 bounded:6 measured it on some worker histories and not others: a heap with free room let
    the answer be pickled after all). The stub replaces the child's own copy of the module; the parent is untouched."""
    class NoMemoryPickle:
        HIGHEST_PROTOCOL = pickle.HIGHEST_PROTOCOL

        @staticmethod
        def dumps(*args, **kwargs):
            raise MemoryError

    bounded.pickle = NoMemoryPickle
    raise MemoryError


class BoundedMemoryAnswerTests(SimpleTestCase):
    def test_a_memory_overrun_is_answered_as_one_when_nothing_more_can_be_pickled(self):
        """The handler pickled ('memory', None) itself, so the child exited without an answer: RuntimeError, and the
        stage said it "failed unexpectedly" instead of naming the memory limit."""
        with self.assertRaises(bounded.Overrun) as caught:
            bounded.run_bounded(_memory_error_with_no_memory_left, seconds=30, memory_bytes=64 * MIB)
        self.assertEqual(caught.exception.reason, 'memory')
        self.assertIs(bounded.pickle, pickle)  # the parent's module was never replaced

    def test_the_stage_names_the_memory_limit(self):
        with self.assertRaises(jobs.StageFailure) as caught:
            jobs._bounded(_memory_error_with_no_memory_left, seconds=30)
        self.assertEqual(str(caught.exception), jobs.OVERRUN_MESSAGES['memory'])
