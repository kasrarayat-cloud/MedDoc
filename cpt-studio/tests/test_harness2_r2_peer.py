"""Refutation round 2, R2-PEER: what a peer request shows, and how a participant's exchanges are recorded (HARNESS.md
12.4 and 12.7, as amended for the round's design decisions D4 and D5; I5, I8, I9, I10).

- FG2-3: a peer request shows Corti's units as the number of its entries, and CPT Studio's excluded codes with their
  reasons - pinned on a pipeline run whose Corti answer selects one code twice and whose assess #1 excludes one.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake. Astra and Fable are the real
replay adapters on the real tool loop with scripted answers (tests.test_harness2_pipeline), their tool calls answered by
CPT Studio's real CMS tool executor over a synthetic reference store.
"""
from tests.test_harness2_pipeline import CPT_STUDIO, HEAD, LAND, SNARE, ColonCase, document_sections, peer_document
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
