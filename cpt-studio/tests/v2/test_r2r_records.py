"""Repair round r2, lens records (DECISIONS D294 F2 and F3). TEXT-ONLY and SYNTHETIC: the notes below are written here
(no real patient, fictional clinicians), RF-HO8a is the committed synthetic refutation case the refuter measured, and
nothing is sent - the pipeline's interpreter is tests/v2/test_jobs' scripted Fable interpreter.

F2 - K2's widened session_conflict reading is gemini-inventory@3's. The checks are made for an inventory version - the
one the row they settle into is written at (contract/checks.check and consistency.check: ``inventory_version``,
gemini-inventory@3 by default; the pipeline names jobs.V2_VERSIONS') - and gemini-inventory@2, first recorded before
AMENDMENT-2, keeps its rule (D202): a contradicted date relation states no value and the date arm reads the act's and
the examination link's supported sessions, so a row written or re-settled under the recorded label equals what it
produced; under gemini-inventory@3 the arm reads every value a fact states or offers (AMENDMENT-2 4.3.3 [R:truth-T3])
exactly as before this repair. The refuter's rows (RF-HO8a (i) and (ii) through the path that writes the recorded
labels) carry the base tree's sha256 again.

F3 - whenever a stored shape exists only under a newer pair (a list at a slot key under gemini-inventory@3), a
product-level test drives it through the pipeline and every reader of the stored row: the customer detail, the draft
report and its download, the operator detail, trace and report, EventReader.reading and unreadable, the
interpretation section and report.record_problems - an event's slot, a section's slot (each act's inherited per-act
list) and the encounter's slot, beside the control with no slot overfilled."""
from __future__ import annotations

import copy
import json
from unittest import mock

from django.test import Client, SimpleTestCase

from studio import interpretation, jobs, models
from studio.interpretation import readers, report, store
from studio.interpretation.contract import checks, segment
from studio.interpretation.contract import consistency as cs
from studio.interpretation.contract import extract_read as xr
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract import geometry
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import facts as engine_facts
from studio.interpretation.engine.types import Id
from tests.support import operator as ops
import tests.v2.test_consistency as TC
import tests.v2.test_failure_classes as FC
import tests.v2.test_jobs as TJ

F, A, R = xs.Family, ct.Attribute, ct.Reason
INV2, INV3 = interpretation.INVENTORY_VERSION_V2, interpretation.INVENTORY_VERSION_V3
# each inventory version's pass-1 label (store.READ_VERSIONS' pairs): the label an answer of that pair is read under
READ_UNDER = {INV2: interpretation.INTERPRETATION_VERSION_V2, INV3: interpretation.INTERPRETATION_VERSION_V3}
CONFLICT = {'session_conflict'}

# --- F2: a synthetic EGD note (written for these tests) --------------------------------------------------------------

R2R_EGD = ('SYNTHETIC EGD REPORT\n'                                                      # S1
           'Date of service: 05/20/2031\n'                                                 # S2
           'Findings: The gastroscope was advanced to the duodenum.\n'                     # S3
           'A 5 mm polyp in the gastric antrum was removed with a cold snare.\n'           # S4
           'A clip was placed at the polypectomy site.\n')                                 # S5


def r2r_answer(*, relation=(), session=None, examination=None, kind=None) -> dict:
    """R2R_EGD's pass-1 answer: one EGD session X1 (a second, X2, beside it) whose examination E1 is told in the Findings
    part N1 and inherits N1's on_date_of_service; the snare E2 in X1 with the date relation ``relation`` of its own;
    ``session``, ``examination`` and ``kind`` replace E2's session fact, X1's examination link and E2's kind."""
    frame = {'link': 'document_frame'}
    snare = TC.event('E2', ['S4'], kind or TC.fact('snare', 'S4', words='cold snare'),
                     TC.fact('performed', 'S4', words='was removed'), kind_words='cold snare',
                     status_words='was removed', session=[session or TC.fact('X1', 'S4')])
    snare['date_relation'] = list(relation)
    return {
        'encounter': {'date_of_service': {'state': 'stated', 'value': '2031-05-20',
                                          'sources': [TC.src('S2', words='05/20/2031', **frame)], 'options': []},
                      'other_dates': [], 'documenting_clinician': []},
        'people': [],
        'sections': [
            TC.section('N0', TC.src(link='section'), TC.fact('documenting_clinician', 'S1', **frame),
                       role=[TC.fact('header', 'S1', link='section')],
                       occasion=[TC.fact('on_date_of_service', 'S2', words='05/20/2031', **frame)]),
            TC.section('N1', TC.src('S3', words='Findings:', link='section'),
                       TC.fact('documenting_clinician', 'S1', **frame),
                       role=[TC.fact('findings', 'S3', words='Findings:', link='section')],
                       occasion=[TC.fact('on_date_of_service', 'S2', **frame)])],
        'sessions': [TC.session('X1', TC.fact('egd', 'S1', words='EGD', **frame),
                                examination=[examination or TC.fact('E1', 'S3')]),
                     TC.session('X2', TC.fact('egd', 'S1', words='EGD', **frame))],
        'anatomy': [], 'lesions': [],
        'events': [TC.event('E1', ['S3'], TC.fact('examination', 'S3', words='gastroscope'), TC.fact('performed', 'S3'),
                            kind_words='gastroscope', status_words='was advanced', session=[TC.fact('X1', 'S3')]),
                   snare,
                   TC.event('E3', ['S5'], TC.fact('clip', 'S5', words='clip'), TC.fact('performed', 'S5'),
                            kind_words='clip', status_words='was placed', session=[TC.fact('X1', 'S5')])],
        'doubts': [],
    }


class R2RInventoryGateTests(TC.Case):
    """DECISIONS D294 F2: K2's date arm, for findings made for each inventory version."""

    def read_for(self, value: dict, inventory: str) -> xr.ReadAnswer:
        """``value`` read under the pass-1 label of ``inventory``'s pair."""
        layout = geometry.Layout.of(R2R_EGD)
        found = xr.read(json.dumps(value), len(layout.units), version=READ_UNDER[inventory])
        self.assertIsInstance(found, xr.ReadAnswer, getattr(found, 'reason', ''))
        return found

    def on(self, value: dict, inventory: str | None, key=None) -> set:
        """The reasons consistency finds on ``key`` (E2's session fact) of ``value``, made for ``inventory`` - None: no
        label named, the call every caller made before the repair (read under gemini-events@3)."""
        layout = geometry.Layout.of(R2R_EGD)
        named = {} if inventory is None else {'inventory_version': inventory}
        found = cs.check(self.read_for(value, inventory or INV3), TC.VOCABULARY, TC.located(layout),
                         TC.sections_of(layout, value), **named)
        return {reason.value for reason in found.reasons(key or TC.key(F.EVENT, 'E2', A.SESSION))}

    def test_the_note_and_its_sections(self):
        layout = geometry.Layout.of(R2R_EGD)
        self.assertEqual(len(layout.units), 5)
        self.assertEqual(TC.sections_of(layout, r2r_answer())['E1'], 'N1')  # E1 inherits N1's on_date_of_service

    def test_a_contradicted_own_date_states_no_value_under_the_recorded_label(self):
        """The rule changes this: pass 1's own contradiction of the act's date relation, one side the examination's
        inherited date. gemini-inventory@2: no value stated, the arm off, as recorded; gemini-inventory@3: each side
        read, and the other side conflicts."""
        for sides in ((('on_date_of_service', 'S4'), ('earlier_date', 'S4')),
                      (('later_date', 'S4'), ('earlier_date', 'S4'))):
            with self.subTest(sides=sides):
                value = r2r_answer(relation=[TC.contradicted(*sides)])
                self.assertEqual(self.on(value, INV2), set())
                self.assertEqual(self.on(value, INV3), CONFLICT)

    def test_a_contradicted_session_or_examination_link_names_nothing_for_the_date_arm_under_the_recorded_label(self):
        """gemini-inventory@2's date arm reads the act's SUPPORTED session and that session's SUPPORTED examination
        (the reading before AMENDMENT-2); gemini-inventory@3 reads each side. E2's own earlier_date differs from E1's
        inherited on_date_of_service."""
        earlier = [TC.fact('earlier_date', 'S4')]
        for name, value in (
                ('session', r2r_answer(relation=earlier, session=TC.contradicted(('X1', 'S4'), ('X2', 'S4')))),
                ('examination link', r2r_answer(relation=earlier,
                                                examination=TC.contradicted(('E1', 'S3'), ('E3', 'S5'))))):
            with self.subTest(contradicted=name):
                self.assertEqual(self.on(value, INV2), set())
                self.assertEqual(self.on(value, INV3), CONFLICT)

    STATED = ((TC.fact('earlier_date', 'S4'), CONFLICT), (TC.fact('later_date', 'S4'), CONFLICT),
              (TC.fact('on_date_of_service', 'S4'), set()),
              (TC.fact('on_date_of_service', 'S4', state='negated'), CONFLICT),
              (TC.fact('later_date', 'S4', state='negated'), set()))

    def test_stated_and_denied_relations_are_judged_as_before(self):
        """The boundary the gate leaves alone, as every caller calls it (no label: the current one): a supported or a
        negated relation, a supported session and link; a contradicted relation read on each side."""
        for own, expected in self.STATED:
            with self.subTest(own=(own['value'], own['state'])):
                self.assertEqual(self.on(r2r_answer(relation=[own]), None), expected)
        self.assertEqual(self.on(r2r_answer(), None), set())  # no relation of its own: the arm reads nothing
        contradicted = r2r_answer(relation=[TC.contradicted(('on_date_of_service', 'S4'), ('earlier_date', 'S4'))])
        self.assertEqual(self.on(contradicted, None), CONFLICT)

    def test_stated_and_denied_relations_read_alike_under_both_labels(self):
        """Only a contradiction reads differently: a stated or denied relation is judged alike for either label."""
        for own, expected in self.STATED:
            for inventory in (INV2, INV3):
                with self.subTest(own=(own['value'], own['state']), inventory=inventory):
                    self.assertEqual(self.on(r2r_answer(relation=[own]), inventory), expected)
        self.assertEqual(self.on(r2r_answer(), INV2), set())

    def test_the_kind_arm_reads_every_offered_kind_as_before(self):
        """The boundary: K2's kind arm (session_inconsistent) reads every kind a contradicted kind offers."""
        self.assertFalse(TC.family_admits(ct.SessionKind.EGD, ct.Kind.SPHINCTEROTOMY))
        value = r2r_answer(kind=TC.contradicted(('snare', 'S4'), ('sphincterotomy', 'S4')))
        self.assertEqual(self.on(value, None), {'session_inconsistent'})

    def test_the_gate_moves_the_kind_arm_too(self):
        """AMENDED by repair round r2b (DECISIONS D297 R2RX-1, which widens D294 F2's gate from K2's date arm to every K
        rule AMENDMENT-2 widened): K2's kind arm reads a contradicted kind as gemini-inventory@2 was recorded - no kind
        stated, nothing found - and every offered kind under gemini-inventory@3 (tests/v2/test_r2br_records2.py pins
        every widened rule)."""
        value = r2r_answer(kind=TC.contradicted(('snare', 'S4'), ('sphincterotomy', 'S4')))
        self.assertEqual(self.on(value, INV2), set())
        self.assertEqual(self.on(value, INV3), {'session_inconsistent'})

    def test_the_orchestration_carries_the_label_and_defaults_to_the_current_one(self):
        """contract/checks.check, which builds the claim set and settle's input, makes its findings for the label it is
        given - the session fact found (never claimed) for gemini-inventory@3, left to its appraisal for
        gemini-inventory@2 - and for gemini-inventory@3, the reading that demotes more, when it is given none."""
        value = r2r_answer(relation=[TC.contradicted(('on_date_of_service', 'S4'), ('earlier_date', 'S4'))])
        session = TC.key(F.EVENT, 'E2', A.SESSION)
        older = checks.check(R2R_EGD, (), self.read_for(value, INV2), inventory_version=INV2)
        newer = checks.check(R2R_EGD, (), self.read_for(value, INV3), inventory_version=INV3)
        unnamed = checks.check(R2R_EGD, (), self.read_for(value, INV3))
        self.assertNotIn(R.SESSION_CONFLICT, older.findings.get(session, ()))
        self.assertIn(R.SESSION_CONFLICT, newer.findings.get(session, ()))
        self.assertEqual(unnamed.findings, newer.findings)

    def test_the_pipeline_makes_its_checks_for_the_version_its_rows_are_written_at(self):
        """jobs' check (both stages' claim builds: _extraction_child and _appraisal_child) names jobs.V2_VERSIONS'
        inventory version - the pair every row of the current path is written at."""
        self.assertEqual(jobs.V2_VERSIONS, (interpretation.INTERPRETATION_PAIR_V3, INV3))
        layout = geometry.Layout.of(R2R_EGD)
        read = self.read_for(r2r_answer(), INV3)
        with mock.patch.object(checks, 'check', wraps=checks.check) as spied:
            jobs._checked_findings({})(R2R_EGD, (), read)
        self.assertEqual(spied.call_args.kwargs, {'inventory_version': INV3})
        self.assertEqual(len(layout.units), read.unit_count)


class R2RRecordedRowsTests(SimpleTestCase):
    """DECISIONS D294 F2, with the refuter's rows: RF-HO8a (i) and (ii) through tests/v2/test_failure_classes.pipeline,
    the path that writes the RECORDED labels (extract_read at gemini-events@2, the checks for gemini-inventory@2,
    settle, store.row_v2 at the @2 pair), give the base tree's rows byte for byte (the refuter measured these sha256 on
    0a5f3283b; the AMENDMENT-2 tree gave 217a632b... and 930398da..., E2's session fact unresolved on
    session_conflict). The same pass-1 answer read and checked for gemini-inventory@3 keeps the stated-or-offered
    reading."""
    BASE = {'i': '391d93e7aa270da718033e8a19e3925d4cd5830b66e371feaeaa4673b0b5a471',
            'ii': 'e4eb8e5df3b8cf49614d1c25e7dd852b103190918f284cd24e32fb93f6e69beb'}

    def row(self, variant: str) -> dict:
        data = FC.case('RF-HO8a')
        seen = {}
        real = store.row_v2

        def spy(**kwargs):
            seen['fields'] = real(**kwargs)
            return seen['fields']
        with mock.patch.object(store, 'row_v2', spy):
            FC.pipeline(FC.document('RF-HO8a'), data['pass1'][FC.filing_of(data, variant)], data['pass2'][variant],
                        data)
        return seen['fields']

    def test_the_refuters_rows_equal_the_base_trees_at_the_recorded_labels(self):
        for variant, sha in self.BASE.items():
            with self.subTest(variant=variant):
                fields = self.row(variant)
                self.assertEqual((fields['interpretation_version'], fields['inventory_version']),
                                 (interpretation.INTERPRETATION_PAIR, INV2))
                e2 = next(item for item in fields['events']['events'] if item['id'] == 'E2')
                self.assertEqual((e2['session']['result'], e2['session']['reasons']), ('supported', []))
                self.assertEqual(fields['sha256'], sha)

    def test_the_same_answer_checked_for_inventory_3_keeps_the_widened_reading(self):
        data = FC.case('RF-HO8a')
        text = FC.document('RF-HO8a')
        for variant in ('i', 'ii'):
            with self.subTest(variant=variant):
                read = xr.read(json.dumps(data['pass1'][FC.filing_of(data, variant)]), len(segment.units(text)),
                               version=READ_UNDER[INV3])
                self.assertIsInstance(read, xr.ReadAnswer)
                found = checks.check(text, (), read).findings
                self.assertIn(R.SESSION_CONFLICT, found.get(TC.key(F.EVENT, 'E2', A.SESSION), ()))


# --- F3: an @3 slot list through the pipeline and every reader of the stored row ------------------------------------

def overfilled_device() -> dict:
    """POLYP's answer with E2's device slot holding two written facts: cold_snare stated, hot_snare denied."""
    answer = TJ.polyp_answer()
    device = answer['events'][1]['technique']['device']
    device.append({**copy.deepcopy(device[0]), 'state': 'negated', 'value': 'hot_snare'})
    return answer


def overfilled_occasion() -> dict:
    """POLYP's answer with the Findings part N1's occasion holding two written facts, and no act a date relation of its
    own, so each act anchored in N1 inherits one per-act fact per written section fact (settle, AMENDMENT-2 4.3.5)."""
    answer = TJ.polyp_answer()
    section = next(item for item in answer['sections'] if item['id'] == 'N1')
    section['occasion'].append({**copy.deepcopy(section['occasion'][0]), 'value': 'earlier_date'})
    for item in answer['events']:
        item['date_relation'] = []
    return answer


def overfilled_clinician() -> dict:
    """POLYP's answer with the encounter's documenting clinician slot holding two written facts."""
    answer = TJ.polyp_answer()
    written = answer['encounter']['documenting_clinician']
    written.append({**copy.deepcopy(written[0]), 'value': 'P9'})
    return answer


class R2ROverfilledRowReadersTests(TJ.PipelineCase):
    """DECISIONS D294 F3: an @3 row holding a list at a slot key, written by the production pipeline (every stage the
    production code's; only the interpreter's one exchange scripted), then read by every reader of the stored row a
    member or an operator reaches."""
    STAGES = ['extract', 'interpret', 'appraise', 'analyze', 'predict', 'assess']

    def read_everything(self, build) -> dict:
        """Upload POLYP answered by ``build``, drain the worker, and read the stored row through every reader: what each
        gives (statuses, the stored row, the FactSet, the verdicts)."""
        if build is not None:
            self.interpreter.answers[TJ.POLYP] = build
        encounter, revision = self.upload(TJ.POLYP)
        done = self.drain()
        self.assertEqual([(job.kind, job.state) for job in done], [(kind, 'succeeded') for kind in self.STAGES],
                         [(job.kind, job.state, job.error) for job in done])
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((inventory.state, inventory.interpretation_version, inventory.inventory_version),
                         ('read', interpretation.INTERPRETATION_PAIR_V3, INV3))
        assessment = models.Encounter.objects.get(pk=encounter.pk).current_assessment
        self.assertEqual((assessment.engine_version, assessment.event_inventory_id),
                         (interpretation.ENGINE_VERSION_V3, inventory.pk))
        reader = readers.for_assessment(assessment)
        seen = {'inventory': inventory, 'facts': reader.reading(assessment),
                'unreadable': reader.unreadable(assessment), 'record_problems': report.record_problems(assessment),
                'section_problems': reader.interpretation_section(assessment).get('problems')}
        member = Client(enforce_csrf_checks=False)
        member.force_login(self.user)
        detail = member.get(f'/api/encounters/{encounter.pk}')
        seen['detail'] = (detail.status_code, sorted((code['code'], code['status']) for code in detail.json()['codes']))
        made = member.post(f'/api/encounters/{encounter.pk}/reports', data=json.dumps({'kind': 'draft', 'fmt': 'txt'}),
                           content_type='application/json')
        download = member.get(made.json()['download_url']) if made.status_code == 201 else None
        seen['draft'] = (made.status_code, download.status_code if download is not None else None,
                         b'45378' in download.content if download is not None else None)
        operator = ops.client(models.User.objects.create(username='ops-r2r-records', actor_kind=models.User.AGENT))
        seen['operator'] = tuple(operator.get(path).status_code for path in (
            f'/ops/api/encounters/{encounter.pk}', f'/ops/api/encounters/{encounter.pk}/trace'))
        made = operator.post(f'/ops/api/encounters/{encounter.pk}/reports',
                             data=json.dumps({'kind': 'draft', 'fmt': 'txt'}), content_type='application/json')
        seen['operator_report'] = made.status_code
        return seen

    def assertEveryReaderReads(self, seen: dict):
        self.assertIsNotNone(seen['facts'], 'EventReader.reading gave no FactSet')
        self.assertEqual((seen['unreadable'], seen['record_problems'], seen['section_problems']), (False, [], []))
        self.assertEqual(seen['detail'], (200, [('45378', 'needs_detail')]))
        self.assertEqual(seen['draft'], (201, 200, True))
        self.assertEqual((seen['operator'], seen['operator_report']), ((200, 200), 201))

    def assertStoredList(self, stored, values, *, inherited_from=None):
        """A slot key holding the written facts as a list, each settled unresolved with slot_overfull (4.3.5, 4.3.6)."""
        self.assertIsInstance(stored, list)
        self.assertEqual([item['claim']['value'] for item in stored], list(values))
        for item in stored:
            self.assertEqual(item['result'], 'unresolved')
            self.assertIn('slot_overfull', item['reasons'])
            self.assertEqual(item['claim']['inherited_from'], inherited_from)

    def assertMergedView(self, fact, options, negated=()):
        """The engine's one fact for the slot (4.3.3): contradicted, unresolved, no value, every written value an
        option in written order, the denied ones its negated_values, slot_overfull its reason."""
        self.assertEqual((fact.state, fact.result, fact.value), (ct.FactState.CONTRADICTED, ct.Result.UNRESOLVED, None))
        self.assertEqual((fact.options, fact.negated_values), (tuple(options), tuple(negated)))
        self.assertIn(R.SLOT_OVERFULL, fact.reasons)

    def test_the_control_holds_one_fact_at_each_slot_key(self):
        seen = self.read_everything(None)
        self.assertEveryReaderReads(seen)
        e2 = seen['inventory'].events['events'][1]
        self.assertIsInstance(e2['technique']['device'], dict)
        found = engine_facts.fact(seen['facts'], Id.parse('E2'), A.TECHNIQUE_DEVICE)
        self.assertEqual((found.state, found.options, found.negated_values),
                         (ct.FactState.SUPPORTED, (), ()))
        self.assertEqual(found.value, ct.Device.COLD_SNARE)

    def test_an_event_slots_list_reads_through_every_reader(self):
        seen = self.read_everything(overfilled_device)
        self.assertEveryReaderReads(seen)
        e2 = seen['inventory'].events['events'][1]
        self.assertStoredList(e2['technique']['device'], ['cold_snare', 'hot_snare'])
        self.assertIsInstance(e2['session'], dict)  # every other slot one fact
        self.assertMergedView(engine_facts.fact(seen['facts'], Id.parse('E2'), A.TECHNIQUE_DEVICE),
                              (ct.Device.COLD_SNARE, ct.Device.HOT_SNARE), (ct.Device.HOT_SNARE,))

    def test_a_section_slots_list_and_each_acts_inherited_list_read_through_every_reader(self):
        seen = self.read_everything(overfilled_occasion)
        self.assertEveryReaderReads(seen)
        events = seen['inventory'].events
        n1 = next(item for item in events['sections'] if item['id'] == 'N1')
        self.assertStoredList(n1['occasion'], ['on_date_of_service', 'earlier_date'])
        for item in events['events']:
            with self.subTest(act=item['id']):
                self.assertStoredList(item['date_relation'], ['on_date_of_service', 'earlier_date'],
                                      inherited_from='N1')
                self.assertMergedView(engine_facts.fact(seen['facts'], Id.parse(item['id']), A.DATE_RELATION),
                                      (ct.DateRelation.ON_DATE_OF_SERVICE, ct.DateRelation.EARLIER_DATE))

    def test_the_encounters_slot_list_reads_through_every_reader(self):
        seen = self.read_everything(overfilled_clinician)
        self.assertEveryReaderReads(seen)
        stored = seen['inventory'].events['encounter']['documenting_clinician']
        self.assertStoredList(stored, ['P1', 'P9'])
        found = engine_facts.fact(seen['facts'], None, A.DOCUMENTING_CLINICIAN)
        self.assertEqual((found.state, found.result, found.value), (ct.FactState.CONTRADICTED, ct.Result.UNRESOLVED,
                                                                   None))
        self.assertEqual([str(option) for option in found.options], ['P1', 'P9'])
        self.assertIn(R.SLOT_OVERFULL, found.reasons)
