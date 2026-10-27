"""Refutation phase 1 over b611b557a, cluster P1INSTALL: rollback safety (must-fix class 5, and class 1 through a
rollback). Synthetic data only; no network: the provider is an in-process stand-in with the live adapter's name and
version, and the installer's in-image scripts run here, on this test database, exactly as `manage shell -c` runs them.

Every document opens with the synthetic banner.

- migrate-2: the upgrade never recomputed the stored list state, so an encounter whose provider outcome 057a7d39 left
  unknown (and unreconciled) stayed 'Reviewed' and off the review queue under this revision's rule.
"""
import hashlib
from types import SimpleNamespace
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings

from studio import models, review
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_r1_m import NEW_REVISION, install, run_app_script
from tests.test_services_second_review import LIVE, REPORT, TwoPassProvider

VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')
SNARE = ('45385', 'was removed with a cold snare')
BIOPSY = ('45380', 'was sampled with cold biopsy forceps')
UNDATED_NOTE = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', '')
MEMBER_CONFLICT = '2026-09-01'  # differs from OFFICE_NOTE's documented 2026-10-20
NOTE = 'Closed by the installer: undone (revision aaaaaaaaaaaa), so this stage will not run.'
OLD_IMAGE, NEW_IMAGE = 'sha256:' + 'b' * 64, 'sha256:' + 'a' * 64


class Provider(TwoPassProvider):
    """The live adapter's name and version, each outcome scripted ('failed': the provider answered HTTP 500); a
    response names only the quotes the request's own text contains."""

    def send(self, request, *, deadline_s):
        if self.outcomes and self.outcomes[0] == 'failed':
            self.outcomes.pop(0)
            self.requests.append(request)
            data = b'{"error":"synthetic internal server error"}'
            return RawExchange(outcome='failed', sent=True, http_status=500, response_bytes=data,
                               response_sha256=hashlib.sha256(data).hexdigest(),
                               error='HTTP 500 from the provider (synthetic).')
        first, later = self.first, self.later
        self.first = [q for q in first if q[1] in request.contexts[0]]
        self.later = [q for q in later if q[1] in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.first, self.later = first, later


@override_settings(**LIVE)
class Base(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(first=[VISIT, SNARE], later=[VISIT, SNARE, BIOPSY])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, text, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data=None):
        import json
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def set_context(self, encounter_id, **values):
        reply = self.post(f'/api/encounters/{encounter_id}/context', values)
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()

    def sent(self):
        return len(self.provider.requests)

    def encounter(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id)

    def hazards(self):
        return run_app_script(install.UNDO_HAZARDS_READ, {})['hazards']

    def close(self, since, kinds=None):
        """CLOSE_STAGES for a pair undone since ``since``, the next worker running ``kinds`` (default: the kinds every
        revision's worker runs, 057a7d39's STAGES)."""
        kinds = list(install.COMMON_STAGE_KINDS if kinds is None else kinds)
        return run_app_script(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': NOTE, 'kinds': kinds})

    def runs(self, encounter_id):
        return list(models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at'))


# --- migrate-2: no pair is installed over an unknown provider outcome ------------------------------------------------

class UnknownOutcomesTests(Base):
    """Refutation p1, migrate-2: the read the app phase refuses on, and a copy of the live installation's shape."""

    def test_migrate2_the_read_names_an_unreconciled_unknown_outcome_until_it_is_reconciled(self):
        # the finding's shape: a first request succeeded, a date change came back unknown, and clearing it reused the
        # first answer - the stored state then read 'reviewed' under the installed revision's rule
        encounter_id = self.create(UNDATED_NOTE, service_date='2026-10-20')
        drain()
        self.provider.outcomes = ['unknown']
        self.set_context(encounter_id, service_date='2026-10-21')
        self.set_context(encounter_id, service_date='2026-10-20')
        self.assertEqual(self.sent(), 2)
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state=models.ProviderRun.UNKNOWN)
        models.Encounter.objects.filter(pk=encounter_id).update(state='reviewed')  # as 057a7d39 derived it
        self.assertEqual(review._derive_state(self.encounter(encounter_id)), 'provider_unknown')
        self.assertEqual(run_app_script(install.UNKNOWN_OUTCOMES, {}), {'encounters': [encounter_id]})
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(unknown.pk), 'note': 'Checked the provider console: nothing billed.'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(run_app_script(install.UNKNOWN_OUTCOMES, {}), {'encounters': []})
        self.assertEqual(self.sent(), 2)  # the reconciliation's attempt reused the retained answer

    def test_a_copy_of_the_live_installation_is_not_refused_and_has_nothing_to_undo(self):
        # 2026-10-27 16:23Z: 11 encounters, 11 provider runs, all succeeded and sent, no stage active, none unknown
        for number in range(11):
            self.create(OFFICE_NOTE.replace('(fictional)', f'(fictional) {number}'))
            drain()
        runs = models.ProviderRun.objects.all()
        self.assertEqual((runs.count(), runs.filter(state=models.ProviderRun.SUCCEEDED, sent=True).count()), (11, 11))
        self.assertFalse(models.Job.objects.filter(state__in=(models.Job.QUEUED, models.Job.RUNNING)).exists())
        details, replace = app_phase(lambda image_id, env, body, params, **kwargs: run_app_script(body, params))
        self.assertIsInstance(details, dict, details)
        replace.assert_called_once()
        self.assertEqual(details['unknown_outcomes'], {'encounters': []})
        self.assertEqual(details['unrunnable_stages']['stuck'], 0)


def app_phase(app_script):
    """install.phase_app with ``app_script`` answering its in-image reads; no container, no Docker."""
    ctx = SimpleNamespace(revision=NEW_REVISION, log=lambda label, data: 'log',
                          args=SimpleNamespace(provider_mode='disabled', authorization_ref=''))
    with mock.patch.object(install, 'installed_image', return_value=NEW_IMAGE), \
            mock.patch.object(install, 'require_db'), \
            mock.patch.object(install, 'read_protected_env', return_value=b''), \
            mock.patch.object(install, 'oneshot', return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')), \
            mock.patch.object(install, 'app_script', app_script), \
            mock.patch.object(install, 'replace_services', return_value={'started': {}}) as replace:
        try:
            return install.phase_app(ctx), replace
        except install.InstallError as error:
            return error, replace


class AppPhaseRefusesUnknownOutcomesTests(SimpleTestCase):
    def answers(self, unknown):
        def app_script(image_id, env, body, params, **kwargs):
            if body == install.UNKNOWN_OUTCOMES:
                return {'encounters': unknown}
            if body == install.UNRUNNABLE_STAGES:
                return {'known': ['analyze', 'assess', 'extract', 'predict', 'review2'], 'stuck': 0, 'kinds': []}
            raise AssertionError('an unexpected in-image script')
        return app_script

    def test_migrate2_the_app_phase_refuses_while_a_provider_outcome_is_unknown(self):
        error, replace = app_phase(self.answers(['e1', 'e2']))
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('2 encounter(s) have a provider outcome still unknown', str(error))
        self.assertIn('nothing was replaced', str(error))
        self.assertEqual(error.details, {'encounters': ['e1', 'e2']})
        replace.assert_not_called()

    def test_controls_none_unknown_installs(self):
        details, replace = app_phase(self.answers([]))
        replace.assert_called_once()
        self.assertEqual(details['unknown_outcomes'], {'encounters': []})
