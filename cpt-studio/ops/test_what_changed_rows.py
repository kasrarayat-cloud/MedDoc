"""The differential check of "what changed" end to end (AMENDMENT-1 11.3; DECISIONS D247 O22, step 6b): the operator
view's ``what_changed_rows`` (studio/serializers.py, step 6b's block this round) read through the REAL operator route
(GET /ops/api/encounters/<id> by an operator) and the page's ``what_changed`` through the REAL member route (GET
/api/encounters/<id> by a member), written as the two JSON files ops/verification/what_changed.py reads, and the
command run over them: exit 0 when its independent reading of 6.2 agrees with the page's (W7's check), 1 when they
differ, 2 when the operator view serves no rows. Synthetic rows only, made in the test; nothing is sent.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

On a disposable PostgreSQL configured the way CI configures it (test_install_harness2's DatabaseTest); skipped, never
passed, without one.
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_install import guard_host, release_host  # noqa: E402
from test_install_harness2 import DatabaseTest  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('cpt_what_changed_rows_check',
                                               APP_ROOT / 'ops' / 'verification' / 'what_changed.py')
wc = importlib.util.module_from_spec(_spec)
sys.modules.setdefault('cpt_what_changed_rows_check', wc)
_spec.loader.exec_module(wc)


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    try:
        harness2 = sys.modules.get('test_install_harness2')
        if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
            connection = harness2._DATABASE.pop('connection')
            connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)
    finally:
        release_host()


class WhatChangedRowsTests(DatabaseTest):
    """A legacy encounter's update, finished: the earlier codes E (a legacy assessment on context C1, office) and the
    update's final N (a design v2 assessment on context C2, an ambulatory surgery center, recording E as its earlier
    assessment): a code kept with its units changed and its approval carried, one listed only as an alternative now,
    one excluded by a documentation check now, one added needing a detail, an approval cleared by the change, and a
    member's earlier answer that N does not read."""

    def scene(self):
        from django.utils import timezone
        from studio import models, operator
        from tests.support import factories as f
        ws = f.workspace()
        self.member = f.member(ws, role=models.Membership.OWNER)
        self.operator = f.user('synthetic-o22-operator')
        operator.grant(self.operator, 'Synthetic grant for the what-changed rows test.', 'tests')
        encounter = f.encounter(ws, self.member)
        revision = f.pasted_revision(encounter, self.member, 'Synthetic colonoscopy note for the what-changed check.')

        def context(setting, version, earlier=None):
            return models.EncounterContext.objects.create(
                encounter=encounter, revision=revision, sha256='d' * 64, version=version, earlier_assessment=earlier,
                user_values={'setting': setting},
                facts={'service_date': {'value': '2026-11-10', 'origin': 'document'},
                       'setting': {'value': setting, 'origin': 'user'}})

        def assessment(holder, engine):
            routing = models.RoutingRun.objects.create(revision=revision, version='synthetic', result={},
                                                       sha256='0' * 64)
            return models.Assessment.objects.create(encounter=encounter, revision=revision, context=holder,
                                                    routing=routing, profiles_version='synthetic@1',
                                                    engine_version=engine, sha256='1' * 64)

        def proposal(holder, code, position, *, bucket='selected', status='ready', units=1, checks=()):
            return models.Proposal.objects.create(
                assessment=holder, key=f'k{position}', bucket=bucket, code=code, code_kind='cpt',
                family='gi.colonoscopy', profile_version='synthetic@1', status=status, units=units,
                fingerprint=f'{code}{position}'.ljust(64, '0'), position=position, checks=list(checks))

        def decision(holder, item, *, carried_from=None):
            return models.Decision.objects.create(
                encounter=encounter, assessment=holder, revision=revision, proposal=item, action='approve',
                reviewer=self.member, reviewer_kind='human', profile_version='synthetic@1',
                proposal_fingerprint=item.fingerprint, carried_from=carried_from)
        c1 = context('office', 'gi-context@5')
        earlier = assessment(c1, 'cpt-studio-validation@10')
        kept, _, cleared, _ = (proposal(earlier, '45380', 0), proposal(earlier, '43239', 1),
                               proposal(earlier, '45378', 2), proposal(earlier, '45384', 3))
        first, gone = decision(earlier, kept), decision(earlier, cleared)
        models.MemberAnswer.objects.create(encounter=encounter, revision=revision, assessment=earlier, fact='extent',
                                           family='gi.colonoscopy', code='45378', value='not_documented',
                                           answered_by=self.member)
        c2 = context('asc', 'gemini-context@2', earlier=earlier)
        final = assessment(c2, 'cpt-studio-events@2')
        carried = proposal(final, '45380', 0, units=2)
        proposal(final, '43239', 1, bucket='alternative')
        proposal(final, '45385', 2, status='needs_clarification')
        proposal(final, '45384', 3, bucket='excluded', status='excluded',
                 checks=[{'id': 'synthetic.documentation', 'status': 'fail'}])
        models.Clarification.objects.create(encounter=encounter, assessment=final, scope='service',
                                            family='gi.colonoscopy', fact='extent', question='Synthetic?',
                                            reason='Synthetic.')
        decision(final, carried, carried_from=first)
        models.DecisionInvalidation.objects.create(decision=gone, reason='Synthetic: the details changed.', by_context=c2)
        models.Encounter.objects.filter(pk=encounter.pk).update(current_revision=revision, current_context=c2,
                                                                current_assessment=final, user_values={'setting': 'asc'},
                                                                updated_at=timezone.now())
        return models.Encounter.objects.get(pk=encounter.pk)

    def read(self, user, path):
        from django.test import Client
        client = Client()
        client.force_login(user)
        response = client.get(path)
        self.assertEqual(response.status_code, 200, response.content[:400])
        return json.loads(response.content)

    def check(self, operator_view, customer_view):
        """what_changed.py run as the operator runs it, over the two files: (exit code, its JSON answer)."""
        with tempfile.TemporaryDirectory(prefix='o22-') as folder:
            op, cust = Path(folder) / 'op.json', Path(folder) / 'cust.json'
            op.write_text(json.dumps(operator_view), encoding='utf-8')
            cust.write_text(json.dumps(customer_view), encoding='utf-8')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = wc.main(['--operator', str(op), '--customer', str(cust), '--app-root', str(APP_ROOT)])
        return code, json.loads(out.getvalue())

    def test_the_command_exits_0_on_the_real_operator_and_customer_views_of_an_update(self):
        encounter = self.scene()
        operator_view = self.read(self.operator, f'/ops/api/encounters/{encounter.pk}')
        customer_view = self.read(self.member, f'/api/encounters/{encounter.pk}')
        rows = operator_view['what_changed_rows']
        self.assertEqual(wc.rows_problem(rows), '')  # served in ROWS_SCHEMA's shape
        self.assertEqual((rows['schema'], rows['fresh'], rows['current_assessment']),
                         (wc.ROWS_SCHEMA, True, str(encounter.current_assessment_id)))
        page = customer_view['what_changed']
        self.assertIsNotNone(page)
        # the fixture reaches every part 6.2 lists: details (and the new reading), the codes' four changes, a kept and a
        # cleared approval, and the answers line
        self.assertEqual(sorted(item['change'] for item in page['codes']),
                         ['added', 'removed', 'removed', 'removed', 'units'])
        self.assertIn('The document was read again with the current reading.', page['details'])
        self.assertEqual(sorted(item['outcome'] for item in page['decisions']), ['cleared', 'kept'])
        self.assertIsNotNone(page['answers'])
        removed = [item['text'] for item in page['codes'] if item['code'] == '45384']
        self.assertEqual(len(removed), 1)
        self.assertIn('Not suggested: ', removed[0])  # the other_reason the rows serve beside the stored rows
        code, answer = self.check(operator_view, customer_view)
        self.assertEqual((code, answer['result'], answer['differences']), (0, 'pass', []), answer)
        self.assertEqual(answer['independent']['what_changed']['codes'], page['codes'])

    def test_a_page_that_differs_fails_and_a_view_without_the_rows_is_unusable(self):
        encounter = self.scene()
        operator_view = self.read(self.operator, f'/ops/api/encounters/{encounter.pk}')
        customer_view = self.read(self.member, f'/api/encounters/{encounter.pk}')
        changed = json.loads(json.dumps(customer_view))
        changed['what_changed']['codes'] = changed['what_changed']['codes'][1:]  # a page that drops one change
        code, answer = self.check(operator_view, changed)
        self.assertEqual((code, answer['result']), (1, 'fail'))
        self.assertTrue(answer['differences'])
        bare = {key: value for key, value in operator_view.items() if key != 'what_changed_rows'}
        code, answer = self.check(bare, customer_view)
        self.assertEqual((code, answer['result']), (2, 'unusable'))
        self.assertIn('serves no what_changed_rows', answer['error'])

    def test_the_rows_are_the_stored_rows_as_6_2_reads_them(self):
        from studio import models, serializers
        encounter = self.scene()
        rows = serializers.what_changed_rows(encounter)
        self.assertEqual(set(rows['assessments']), {str(pk) for pk in models.Assessment.objects.filter(
            encounter=encounter).values_list('pk', flat=True)})
        excluded = next(item for holder in rows['assessments'].values() for item in holder['proposals']
                        if item['id'] == str(models.Proposal.objects.get(assessment=encounter.current_assessment,
                                                                         code='45384').pk))
        self.assertTrue(excluded['other_reason'].startswith('Not suggested: '))
        alternative = next(item for item in rows['assessments'][str(encounter.current_assessment_id)]['proposals']
                           if item['bucket'] == 'alternative')
        self.assertEqual(alternative['other_reason'], 'Listed as an alternative only; not suggested for approval.')
        selected = next(item for item in rows['assessments'][str(encounter.current_assessment_id)]['proposals']
                        if item['code'] == '45380')
        self.assertIsNone(selected['other_reason'])
        self.assertEqual([item['standing'] for item in rows['member_answers']], [True])
        self.assertEqual(len(rows['invalidations']), 1)
        self.assertEqual([item['sequence'] for item in rows['decisions']],
                         sorted(item['sequence'] for item in rows['decisions']))
        self.assertEqual(rows['contexts'][str(encounter.current_context_id)]['earlier_assessment'],
                         str(models.Assessment.objects.filter(encounter=encounter).order_by('created_at').first().pk))


if __name__ == '__main__':
    unittest.main()
