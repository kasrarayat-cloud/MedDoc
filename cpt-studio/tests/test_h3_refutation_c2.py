"""Harness repair 3 (owner directive 2026-11-05, second message): refutation cycle 2 over the round-1 repairs, pinned.
This is the second cycle of the programme's two-cycle rule (HARNESS.md "Harness repair 3, refutation cycle 2").

Five lenses ran at 8b186df05: C2-1 the releasing rules, C2-2 the holding rules in both directions, C2-3 sections and the
date, C2-4 admission and competition, C2-5 acts and Stop/Resume. Every engine-level input of C2-1, C2-2, C2-3 and C2-5
is in tests/fixtures/gi4/refutation/h3-c2-cases.json, verbatim, with what the base 406843018, the stage commit
1974c8cb1 and the round-1 tree read, measured before anything was decided. Each is read here as the pipeline reads it -
through its own date of service (jobs._service_date_of), as lens C2-3 read them - on both paths: Corti selecting the
code, and an independent participant's first reading proposing it alone. C2-4's competition inputs and C2-5's database
findings are below. Synthetic documents only; nothing is sent."""
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

import tests.test_harness2_pipeline as h2p
from studio import jobs, reports, serializers
from studio.gi import context as gi_context
from studio.gi import detect
from studio.types import NormalizedResponse, to_jsonable
from studio.validation import engine
from studio.validation.engine import assess
from tests.test_harness_engine import REFERENCE, code, corti, read, run, span

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'gi4' / 'refutation' / 'h3-c2-cases.json')
                   .read_text(encoding='utf-8'))['cases']
SHORT = {('selected', 'ready'): 'READY', ('selected', 'needs_clarification'): 'HELD',
         ('alternative', 'informational'): 'ALT', ('excluded', 'excluded'): 'EXCL'}


def dated_both(text, which, quote, primary=()):
    """Both paths through the pipeline's own date of service: (Corti's reading of ``which``, a participant's, the day)."""
    facts = gi_context.extract_context(text)
    day = jobs._service_date_of(to_jsonable(facts))

    def go(participants, codes):
        result = assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                        normalized=NormalizedResponse('corti', 'test@1', tuple(codes)), reference=REFERENCE,
                        service_date=day, provider_status='succeeded', participants=tuple(participants))
        return [SHORT[(p.bucket, p.status)] for p in result.proposals if p.code == which]
    selected = [(c, span(text, q)) for c, q in primary]
    return (go((), corti(*selected, (which, span(text, quote)))),
            go([read('astra', [code(text, which, quote)])], corti(*selected)), str(day))


class CycleTwoReadingTests(SimpleTestCase):
    """Every cycle-2 input reads as pinned. The rules refuted in both cycles (F-TIME R, F-SECTIONS T and L, F-ACTS'
    round-1 vocabulary) are dropped, so their inputs read as the base reads them; the rebuilt rules and the repaired
    holding rules read the rest. A participant's code is held beside Corti's only for an act stated done inside a
    service documented in doubt (the provider-neutral admission as refutation cycle 3 narrowed it); one for an act read
    in doubt itself, or stated not done, is listed. Each fixture row carries the cycle-2 tree's own reading too."""

    def test_every_input_reads_as_pinned(self):
        for case in CASES:
            with self.subTest(case['id']):
                by_corti, by_participant, day = dated_both(case['text'], case['code'], case['quote'],
                                                           tuple(map(tuple, case['primary'])))
                self.assertEqual((by_corti, by_participant, day),
                                 ([case['corti']], [case['participant']], case['day']), case['read'])

    def test_no_input_is_ready_where_the_base_is_not(self):
        """This diff opens no false READY over the base on either path: every READY pinned here is READY on the base
        too (the base's own false READYs among them are recorded in HARNESS.md)."""
        for case in CASES:
            base_corti, base_participant = case['read']['base'].split('/')
            with self.subTest(case['id']):
                if case['corti'] == 'READY':
                    self.assertEqual(base_corti, 'READY')
                if case['participant'] == 'READY':
                    self.assertEqual(base_participant, 'READY')

    def test_the_fixture_is_the_whole_measured_set(self):
        self.assertEqual(len(CASES), 156)
        self.assertEqual(len({case['id'] for case in CASES}), 156)


SYN = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
EGDP = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
        'Procedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the duodenum.\n')
COLP = (SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
        'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum.\n')
EGD_IND = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
           'Indications: Dysphagia and early satiety.\nProcedure\n'
           'The gastroscope was passed to the second portion of the duodenum.\n')
F4, A4 = 'A Schatzki ring was found in the distal esophagus.', 'It was dilated with an 18 mm through-the-scope balloon.'
F1, A1 = 'Large esophageal varices were seen in the distal esophagus.', 'Three bands were placed on the varices.'
F3, A3 = 'A 9 mm sessile polyp was found in the sigmoid colon.', 'It was removed with a cold snare.'
D1 = 'The Schatzki ring in the distal esophagus was dilated with a through-the-scope balloon to 18 mm.'
D2 = 'Impression: Schatzki ring at the gastroesophageal junction, dilated with a balloon to 18 mm.'
S1 = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
S2 = 'Impression: One polyp in the sigmoid colon, removed by cold snare polypectomy.'
ESO = ('A through-the-scope balloon was positioned across the Schatzki ring in the distal esophagus and inflated to '
       '18 mm under direct visualization.')
PB = ('A second through-the-scope balloon was positioned across the post-bulbar stricture and inflated to 15 mm under '
      'direct visualization.')
GJ = ('A second through-the-scope balloon was positioned across the stricture at the gastrojejunal anastomosis and '
      'inflated to 15 mm under direct visualization.')


class CompetitionByActIdentityTests(SimpleTestCase):
    """C2-4 (lens C2-4's own inputs): two codes compete exactly where they claim one documented act. Corti's code whose
    passage shows the finding, not the act, claims the one act there is (C2-4-1); an Impression's restatement is the
    narrative act it restates (C2-4-2); two dilations whose second site is unread compete on the safe side (C2-4-3,
    cycle 4)."""

    def outcome(self, text, by_corti, by_participant):
        result = run(text, corti((by_corti[0], span(text, by_corti[1]))),
                     [read('astra', [code(text, by_participant[0], by_participant[1])])])
        out = {}
        for value in (by_corti[0], by_participant[0]):
            (item,) = [p for p in result.proposals if p.code == value]
            out[value] = (item.bucket, item.status, any(c.id == engine.COMPETING_CHECK for c in item.checks))
        return out

    def test_c2_4_1_a_code_on_the_finding_competes_for_the_one_act(self):
        for name, text, by_corti, by_participant in (
                # completion repair (integration): two balloon codes, whose technique the document does not tell
                # apart (a guide-wire code no longer accounts for the balloon dilation: reconcile.technique_fits)
                ('dilation', EGDP + F4 + ' ' + A4 + '\n', ('43249', F4), ('43233', A4)),
                ('band ligation', EGDP + F1 + ' ' + A1 + '\n', ('43244', F1), ('43205', A1)),
                ('snare', COLP + F3 + ' ' + A3 + '\n', ('45385', F3), ('44394', A3))):
            with self.subTest(name):
                self.assertEqual(set(self.outcome(text, by_corti, by_participant).values()),
                                 {('selected', 'needs_clarification', True)})

    def test_c2_4_2_an_impressions_restatement_is_the_act_it_restates(self):
        for name, text, by_corti, by_participant in (
                ('GEJ', EGDP.replace('Procedure: Upper endoscopy\n', 'Procedure\n') + D1 + '\n' + D2 + '\n',
                 ('43249', D1), ('43233', D2)),
                ('one polyp', COLP + S1 + '\n' + S2 + '\n', ('45385', S1), ('44394', S2))):
            with self.subTest(name):
                self.assertEqual(set(self.outcome(text, by_corti, by_participant).values()),
                                 {('selected', 'needs_clarification', True)})

    def test_c2_4_3_two_dilations_whose_second_site_is_unread_compete_on_the_safe_side(self):
        # refutation cycle 4: competition errs toward competing - the second dilation's site ("post-bulbar", "the
        # gastrojejunal anastomosis") is not read, so its code may restate the first and the two compete, held for a
        # reviewer's rejection. A recorded false hold (cycle 2 read both READY); two codes for one act are never both READY
        for name, text in (('post-bulbar', EGD_IND + ESO + '\n' + PB + '\n'),
                           ('GJ anastomosis', EGD_IND + ESO + '\n' + GJ + '\n')):
            with self.subTest(name):
                second = PB if name == 'post-bulbar' else GJ
                self.assertEqual(self.outcome(text, ('43249', ESO), ('43245', second)),
                                 {'43249': ('selected', 'needs_clarification', True),
                                  '43245': ('selected', 'needs_clarification', True)})


class ChainCostAndModeTests(h2p.Harness2Case):
    """C2-5 (lens C2-5's database findings): a stopped and resumed participant's chain is one record on every surface,
    and a chain never mixes a live run and a replay one."""

    def stop_during(self, encounter_id, step):
        def stopped_then(body):
            jobs.stop_encounter(self.encounter(encounter_id), self.reviewer)  # the member's Stop lands mid-loop
            return step
        return stopped_then

    def stopped(self):
        encounter_id = self.create()
        self.adapters['astra'].first = [
            self.stop_during(encounter_id, h2p.asks('astra', h2p.facts_call('call_astra_1', ['99213']))),
            h2p.answered('astra', h2p.ASTRA_READING)]
        h2p.drain()
        (stopped,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((stopped.state, stopped.sent, stopped.scope.get('stopped_after_turn')), ('failed', True, 1))
        return encounter_id, stopped

    def test_c2_5_8_the_api_row_reads_the_chains_usage_and_cost_as_the_report_does(self):
        encounter_id, stopped = self.stopped()
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        h2p.drain()
        first, later = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((first, (later.scope or {}).get('continues')), (stopped, str(stopped.pk)))
        encounter = self.encounter(encounter_id)
        (entry,) = [e for e in reports._participants(encounter.current_assessment) if e['name'] == 'astra']
        current = list(encounter.jobs.filter(revision=encounter.current_revision).order_by('created_at'))
        api = {row['name']: row for row in serializers.harness_json(encounter, current)['participants']}['astra']
        self.assertEqual(api['usage'], entry['usage'])
        self.assertEqual(api['estimated_cost_usd'], entry['estimated_cost_usd'])
        self.assertNotEqual(api['usage'], later.usage)  # the chain's, never the continuation's alone

    def test_c2_5_edge_a_stopped_run_of_the_other_mode_is_no_attempt_to_continue(self):
        encounter_id, stopped = self.stopped()
        own = (stopped.scope or {}).get('mode')
        self.assertEqual(own, 'replay')  # the harness's fake participants answer as replay adapters
        request = SimpleNamespace(canonical_sha256=stopped.request_sha256)
        for mode, found in ((own, stopped), ('live', None)):
            provider = SimpleNamespace(name='astra', adapter_version=stopped.adapter_version, mode=mode)
            with self.subTest(mode):
                self.assertEqual(jobs._stopped_attempt(self.encounter(encounter_id), provider, request,
                                                       stopped.purpose), found)
