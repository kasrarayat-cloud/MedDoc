"""Repairs made while integrating repair round ec5 (session ec5e7910), for issues a cluster handed back outside its
territory. Synthetic text only."""
from datetime import date

import json
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings

from studio import models
from studio.gi import context as gi_context
from studio.types import RawExchange
from studio.validation import checks
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_services_second_review import LIVE, TwoPassProvider

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
NOTE = BANNER + '{line}\nOffice follow-up visit for rectal bleeding.\nMedical decision making: moderate.\n'


def date_wording(text):
    facts = gi_context.extract_context(text)
    fact = facts.get('service_date')
    try:
        day = date.fromisoformat(fact.value) if fact is not None and fact.origin in checks.DOCUMENTED else None
    except (TypeError, ValueError):
        day = None
    state = checks.service_date_state(facts, day)
    check = checks.service_date_check(state)
    return state, check.status, check.detail


class UnusableLabelledDateWordingTests(SimpleTestCase):
    """CONTEXT handed back new:missing-date-wording: a labelled date kept as evidence but not usable as the date of
    service was worded "No date of service is documented" in the check and the question's reason."""

    def test_a_kept_labelled_date_is_quoted_never_called_undocumented(self):
        for line in ('Date of service: Tuesday, October 20, 2026', 'Referring visit date: 09/30/2026.',
                     'Date of service: 2026-02-30'):
            with self.subTest(line=line):
                state, status, detail = date_wording(NOTE.format(line=line))
                self.assertIsNone(state.value)
                self.assertEqual(status, 'fail')
                self.assertNotIn('No date of service is documented', detail)
                self.assertIn('No usable date of service was read', detail)

    def test_control_a_note_without_any_date_is_still_undocumented(self):
        state, status, detail = date_wording(NOTE.format(line='Chief complaint: rectal bleeding.'))
        self.assertEqual(status, 'fail')
        self.assertIn('No date of service is documented', detail)

    def test_control_a_readable_date_is_documented(self):
        # (refutation phase 2, P2DATES rule 1: a header block - the date line, then a blank line - states it)
        _, status, detail = date_wording(NOTE.format(line='Date of service: 2026-10-20\n'))
        self.assertEqual(status, 'pass')
        self.assertIn('2026-10-20 is documented', detail)


class FailingProvider(TwoPassProvider):
    """Answers each request with a scripted outcome; "failed" is an HTTP 500 the provider returned."""

    def send(self, request, *, deadline_s):
        if self.outcomes and self.outcomes[0] == 'failed':
            self.outcomes.pop(0)
            self.requests.append(request)
            return RawExchange(outcome='failed', sent=True, http_status=500,
                               error='HTTP 500 from the provider (synthetic).')
        return super().send(request, deadline_s=deadline_s)


@override_settings(**LIVE)
class HeldRunIsNoRequestOutcomeTests(TestCase):
    """REPORTRUNS' skeptic, routed to sends (must-fix class 1, ARCHITECTURE 5.4: a failed or not-sent request is never
    re-sent behind a metadata save): a request failed, a member date conflict was held (a not-sent run with no
    request), and clearing the conflict SENT the byte-identical failed request again, because the held run stood as
    the run in use and answers no request."""

    def setUp(self):
        self.ws = f.workspace()
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(f.member(self.ws, f.user('reviewer')))

    def context(self, encounter_id, **values):
        reply = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps(values),
                                 content_type='application/json')
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()

    def upload(self, provider, text):
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
        return reply.json()['id']

    def test_clearing_a_held_conflict_never_resends_the_failed_request(self):
        provider = FailingProvider(first=[], later=[], outcomes=['failed', 'failed'])
        encounter_id = self.upload(provider, OFFICE_NOTE)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'provider_failed')
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            self.context(encounter_id, service_date='1998-01-01')  # a member conflict: held, nothing sent
            self.assertEqual(len(provider.requests), 1)
            self.context(encounter_id, service_date='')  # cleared: the request is the failed one, byte for byte
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'provider_failed')

    def test_control_a_date_that_changes_the_request_still_sends_it(self):
        provider = FailingProvider(first=[], later=[], outcomes=['failed'])
        undated = '\n'.join(line for line in OFFICE_NOTE.split('\n') if 'Date of service' not in line)
        encounter_id = self.upload(provider, undated)
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            self.context(encounter_id, service_date='2026-10-20')  # an undated note: the member's date is the date
        self.assertEqual(len(provider.requests), 2)
        self.assertIn('Date of service: 2026-10-20', provider.requests[1].contexts)
