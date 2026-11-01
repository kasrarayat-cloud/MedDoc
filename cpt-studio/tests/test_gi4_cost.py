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
