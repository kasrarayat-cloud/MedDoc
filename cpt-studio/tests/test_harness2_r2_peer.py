"""Refutation round 2, R2-PEER: what a peer request shows, and how a participant's exchanges are recorded (HARNESS.md
12.4 and 12.7, as amended for the round's design decisions D4 and D5; I5, I8, I9, I10).

- FG2-3: a peer request shows Corti's units as the number of its entries, and CPT Studio's excluded codes with their
  reasons - pinned on a pipeline run whose Corti answer selects one code twice and whose assess #1 excludes one.
- sends-r2-1: a tool call whose arguments are missing or null is recorded with JSON null arguments, and the run is
  recorded whole (succeeded, every exchange and tool call kept), never unknown with nothing of it kept.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake. Astra and Fable are the real
replay adapters on the real tool loop with scripted answers (tests.test_harness2_pipeline), their tool calls answered by
CPT Studio's real CMS tool executor over a synthetic reference store.
"""
import json

from studio import models
from tests.test_harness2_pipeline import (ASTRA_READING, CPT_STUDIO, FABLE_READING, HEAD, LAND, SNARE, ColonCase,
                                          Harness2Case, answered, asks, document_sections, peer_document)
from tests.test_pipeline_api import drain

# --- FG2-3: Corti's units and CPT Studio's excluded codes, as a peer request shows them -------------------------------

SECOND_SNARE = 'A 7 mm sessile polyp in the descending colon was removed with a hot snare'
SURVEILLANCE = 'Plan: Surveillance colonoscopy in three years.'
TWO_SNARES = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
              'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
              + SECOND_SNARE + '.\n' + LAND + '\n' + SURVEILLANCE + '\n')


class PeerMaterialTests(ColonCase):
    """HARNESS.md 11.1, 12.4 and 12.7: Corti's selected codes 'with units as the number of its entries', and CPT
    Studio's held and excluded codes with their reasons. The earlier pins saw only one-entry Corti codes and an empty
    excluded list, so a peer shown units 1 and no excluded code at all stayed green (FG2-3)."""
    corti_codes = (('45385', SNARE), ('45385', SECOND_SNARE), ('45378', SURVEILLANCE), ('G0121', SURVEILLANCE))

    def test_corti_s_units_and_the_excluded_codes_are_shown_as_assess_one_recorded_them(self):
        encounter_id = self.create(TWO_SNARES)
        drain()
        first = self.assessments(encounter_id)[0]
        self.assertEqual((first.proposals.get(key='sel:0').code, first.proposals.get(key='sel:0').units), ('45385', 2))
        excluded = first.proposals.get(key='exc:0')
        self.assertEqual((excluded.code, excluded.status), ('G0121', 'excluded'))
        for name in ('astra', 'fable'):
            with self.subTest(name):
                run = self.runs_of(encounter_id, name, 'peer_review')[0]
                sections = document_sections(peer_document(name, run.request_body))
                corti = {item['code']: item for item in sections['corti (another coding system):']['codes']}
                self.assertEqual(corti['45385'], {'code': '45385', 'modifiers': [], 'units': 2,
                                                  'evidence': [SNARE, SECOND_SNARE]})
                self.assertEqual([corti[c]['units'] for c in ('45378', 'G0121')], [1, 1])
                self.assertEqual(sections[CPT_STUDIO]['excluded'],
                                 [{'code': 'G0121', 'key': 'exc:0', 'status': 'excluded',
                                   'reasons': ['HCPCS Level II code — CPT-only results.']}])
                self.assertEqual(sections[CPT_STUDIO]['excluded'][0]['reasons'],
                                 [c['detail'] for c in excluded.checks if c['status'] != 'pass'])


# --- sends-r2-1: a tool call with missing or null arguments is recorded whole -----------------------------------------

def without_key(data, key):
    """An answer asking for tool calls, each call's ``key`` ('arguments', 'input') removed."""
    envelope = json.loads(data)
    for item in envelope.get('output', envelope.get('content', [])):
        if item.get('type') in ('function_call', 'tool_use'):
            item.pop(key, None)
    return json.dumps(envelope).encode()


class NullArgumentsTests(Harness2Case):
    """HARNESS.md 11.2 and 12.1: every exchange is a recorded ProviderExchange and every tool call a ToolCall row; the
    loop answers arguments that are not a usable object with CPT Studio's own sentence and goes on (loop.NOT_AN_OBJECT).
    ToolCall.arguments is NOT NULL, and a Python None there was SQL NULL: the record failed, and the whole run - its
    final answer, its usage and every exchange - was recorded unknown with nothing kept, blocking the other participant
    (I8, I10), and a reconciliation sent the identical, already answered request again (sends-r2-1)."""

    def assertRecordedWhole(self, encounter_id, name, call_id, reading):
        run = self.runs_of(encounter_id, name, 'independent')[0]
        self.assertEqual((run.state, run.sent, run.error), ('succeeded', True, ''))
        self.assertEqual([(e.turn, e.state) for e in run.exchanges.order_by('turn')], [(1, 'succeeded'),
                                                                                       (2, 'succeeded')])
        call = models.ToolCall.objects.get(exchange__run=run)
        self.assertEqual((call.call_id, call.tool, call.arguments, call.result),
                         (call_id, 'cms_code_facts', None, {'error': 'The arguments are not a JSON object.'}))
        self.assertEqual(models.ToolCall.objects.filter(exchange__run=run, arguments=None).count(), 1)  # JSON null
        self.assertEqual(bytes(run.response_bytes), answered(name, reading))
        self.assertTrue(run.usage)
        for other in ('astra', 'fable'):
            self.assertEqual([r.state for r in self.runs_of(encounter_id, other, 'independent')], ['succeeded'])
            self.assertEqual([r.state for r in self.runs_of(encounter_id, other, 'peer_review')], ['succeeded'])
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')
        record = self.records(self.encounter(encounter_id).current_assessment)[name]
        self.assertEqual((record['state'], record['exchanges'], record['tool_calls']), ('read', 2, 1))

    def run_first(self, name, data, reading):
        self.adapters[name].first = [data, answered(name, reading)]
        encounter_id = self.create()
        drain()
        self.assertEqual([len(record['bodies']) for record in self.adapters[name].loops_of('first')], [2])
        return encounter_id

    def test_astra_arguments_null_are_recorded_as_json_null(self):
        encounter_id = self.run_first('astra', asks('astra', ('call_astra_null', 'cms_code_facts', 'null')),
                                      ASTRA_READING)
        self.assertRecordedWhole(encounter_id, 'astra', 'call_astra_null', ASTRA_READING)

    def test_astra_arguments_missing_are_recorded_as_json_null(self):
        data = without_key(asks('astra', ('call_astra_none', 'cms_code_facts', '{}')), 'arguments')
        encounter_id = self.run_first('astra', data, ASTRA_READING)
        self.assertRecordedWhole(encounter_id, 'astra', 'call_astra_none', ASTRA_READING)

    def test_fable_input_null_is_recorded_as_json_null(self):
        encounter_id = self.run_first('fable', asks('fable', ('toolu_fable_null', 'cms_code_facts', None)),
                                      FABLE_READING)
        self.assertRecordedWhole(encounter_id, 'fable', 'toolu_fable_null', FABLE_READING)

    def test_fable_input_missing_is_recorded_as_json_null(self):
        data = without_key(asks('fable', ('toolu_fable_none', 'cms_code_facts', {})), 'input')
        encounter_id = self.run_first('fable', data, FABLE_READING)
        self.assertRecordedWhole(encounter_id, 'fable', 'toolu_fable_none', FABLE_READING)

    def test_control_arguments_that_are_a_list_are_recorded_as_given(self):
        self.adapters['astra'].first = [asks('astra', ('call_astra_list', 'cms_code_facts', '["99213"]')),
                                        answered('astra', ASTRA_READING)]
        encounter_id = self.create()
        drain()
        run = self.runs_of(encounter_id, 'astra', 'independent')[0]
        self.assertEqual((run.state, run.exchanges.count()), ('succeeded', 2))
        call = models.ToolCall.objects.get(exchange__run=run)
        self.assertEqual((call.arguments, call.result), (['99213'], {'error': 'The arguments are not a JSON object.'}))
