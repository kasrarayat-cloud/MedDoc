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

    def test_both_children_read_the_date_of_service_the_probe_codes(self):
        # Round 4 PD asks the date where a wide label stands beside the date of service ('worded date labels'), and
        # accepts only the date of service: the children then read the member's answer, never a dateless path, and a
        # shape whose context neither reads nor accepts PROBE_DATE fails loudly instead of measuring another path.
        m = cost.modules()
        day = cost.dt.date.fromisoformat(cost.PROBE_DATE)
        for name, make in cost.SHAPES.items():
            facts = m.context.extract_context(make(40))
            values = cost.member_values(m, facts)
            self.assertIn(values, ({}, {'service_date': cost.PROBE_DATE}), name)
            self.assertEqual(m.jobs._service_date_of(m.jobs._merged_facts(facts, values)), day, name)
            if not values:  # the document gives the date itself: the children read exactly what installed read
                self.assertEqual(facts['service_date'].origin, 'document', name)
        asked = cost.SHAPES['worded date labels'](40)
        self.assertIsNone(m.jobs._service_date_of(m.jobs._merged_facts(m.context.extract_context(asked), {})))
        self.assertEqual(cost.member_values(m, m.context.extract_context(asked)), {'service_date': cost.PROBE_DATE})
        rows = cost.probe(m, 'worded date labels', cost.SHAPES['worded date labels'], (3000,))
        self.assertEqual(rows[0]['member_answer'], cost.PROBE_DATE)
        self.assertEqual(rows[0]['assess']['outcome'], 'assessed')
        for other in (cost.B.replace('10/19/2026', '10/18/2026') + 'The colonoscope reached the cecum.\n',  # refused
                      cost.B.replace('10/19/2026', '10/17/2026') + 'Date of service: 10/18/2026\nThe colonoscope '
                      'reached the cecum.\n'):  # a documented conflict PROBE_DATE is no side of
            with self.assertRaisesRegex(ValueError, 'neither reads nor accepts'):
                cost.member_values(m, m.context.extract_context(other))

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
