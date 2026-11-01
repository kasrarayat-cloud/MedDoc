"""GI round 4 harness, H7: the cost probes (ops/gi4/cost.py). The full doubling series to 400,000 characters runs from the
command line (python -m ops.gi4.cost); here every shape runs at two small sizes through the readers and through the
analyze and assess children under the stage limits (studio/bounded.py; doubling ratios at these sizes are timing noise and
are judged only on the command line's full series), and the ratio judge is pinned on hand-made series: a superlinear
step is reported, noise under the floor is not.
"""
from django.test import SimpleTestCase

from ops.gi4 import cost


class CostProbeTests(SimpleTestCase):
    def test_every_shape_runs_through_the_children_within_the_limits(self):
        m = cost.modules()
        for name, make in cost.SHAPES.items():
            rows = cost.probe(m, name, make, (3000, 6000))
            # small sizes on a shared machine: doubling ratios are noise here (the command line judges them on the
            # full series); the limits on the children are judged
            self.assertEqual([p for p in cost.judge(name, rows) if 'ratio' not in p], [], name)
            for row in rows:
                self.assertNotIn('overrun', row['analyze'], name)
                self.assertNotIn('overrun', row['assess'], name)
                self.assertIn(row['analyze']['outcome'], ('read', 'mentions over the limit'), name)
                self.assertEqual(row['assess']['outcome'], 'assessed', name)

    def test_both_children_read_the_date_of_service_the_context_accepts(self):
        # Round 4 PD asks the date where a wide label stands beside the date of service ('worded date labels'), and
        # accepts only the date of service: the children then read the member's answer, never a dateless path. Every
        # registered shape reads its own PROBE_DATE, as installed read it; a shape whose context accepts no date at all
        # fails loudly instead of measuring another path.
        m = cost.modules()

        def read(text):
            facts = m.context.extract_context(text)
            values = cost.member_values(m, facts, text)
            return values, m.jobs._service_date_of(m.jobs._merged_facts(facts, values))

        for name, make in cost.SHAPES.items():
            values, day = read(make(40))
            self.assertIn(values, ({}, {'service_date': cost.PROBE_DATE}), name)
            self.assertEqual(day, cost.dt.date.fromisoformat(cost.PROBE_DATE), name)
        asked = cost.SHAPES['worded date labels'](40)
        self.assertIsNone(m.jobs._service_date_of(m.jobs._merged_facts(m.context.extract_context(asked), {})))
        self.assertEqual(read(asked)[0], {'service_date': cost.PROBE_DATE})
        rows = cost.probe(m, 'worded date labels', cost.SHAPES['worded date labels'], (3000,))
        self.assertEqual(rows[0]['member_answer'], cost.PROBE_DATE)
        self.assertEqual(rows[0]['assess']['outcome'], 'assessed')
        head = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nNew Patient Evaluation\n'
        self.assertEqual(read(head + 'Date seen: 10/26/2026\n'), ({'service_date': '2026-10-26'},
                                                                   cost.dt.date(2026, 10, 26)))  # its own date
        self.assertEqual(read(cost.B.replace('10/19/2026', '10/18/2026'))[0], {})  # its own documented date
        self.assertEqual(read(cost.B.replace('10/19/2026', '10/17/2026') + 'Date of service: 10/18/2026\n')[0],
                         {'service_date': '2026-10-17'})  # a documented conflict: one of its own dates
        with self.assertRaisesRegex(ValueError, 'neither reads nor accepts'):
            read(head + 'Date of service: 20-Oct-26\n')  # a date no answer can be checked against: every one refused

    def test_the_ratio_judge(self):
        def row(chars, t, child=0.1):
            return {'chars': chars, 'context': t, 'route': 0.0, 'inventory': 0.0, 'ps_helpers': 0.0,
                    'analyze': {'seconds': child}, 'assess': {'seconds': child}}
        self.assertEqual(cost.judge('linear', [row(1000, 0.1), row(2000, 0.2), row(4000, 0.41)]), [])
        self.assertTrue(cost.judge('quadratic', [row(1000, 0.1), row(2000, 0.4)]))
        self.assertEqual(cost.judge('noise', [row(1000, 0.001), row(2000, 0.04)]), [])
        self.assertTrue(cost.judge('slow child', [row(1000, 0.1, child=61.0)]))
        overrun = row(1000, 0.1)
        overrun['assess'] = {'seconds': 120.0, 'overrun': 'memory'}
        self.assertTrue(cost.judge('overrun', [overrun]))
