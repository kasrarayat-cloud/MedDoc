"""The ``provider_hold`` management command (docs/gemini-migration/AMENDMENT-1.md 7.3, A16 and A20; DECISIONS D208; step 6b
of the amendment's section 10): ``--status`` shows every standing hold of Corti, Astra and Fable and writes nothing;
``--release <provider> --note`` ends every standing hold of that one provider, recorded with the operator (an operator
grant, as ``interpreter_hold``) and the note; every refusal records nothing. Synthetic rows only; no provider is called.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from studio import models, operator, provider_holds
from tests.support import factories as f

NOTE = 'Synthetic release: the account was paid and its credentials renewed (a test).'


def an_operator(username: str = 'synthetic-operator') -> models.User:
    user = f.user(username)
    operator.grant(user, 'Synthetic grant for a provider-hold test.', 'tests')
    return user


class ProviderHoldCommandTests(TestCase):
    def setUp(self) -> None:
        self.ws = f.workspace()
        self.member = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.member)
        self.rev = f.pasted_revision(self.enc, self.member, 'Synthetic colonoscopy note for a provider hold test.')
        self.operator = an_operator()
        self.count = 0

    def run_command(self, *args: str) -> str:
        out = io.StringIO()
        call_command('provider_hold', *args, stdout=out)
        return out.getvalue()

    def refused_run(self, provider: str = 'corti', status: int = 402, *, sent: bool = True) -> models.ProviderRun:
        """A run of ``provider`` whose recorded refusal A20 holds (a participant's on its one exchange)."""
        self.count += 1
        run = models.ProviderRun.objects.create(
            encounter=self.enc, revision=self.rev, provider=provider, adapter_version='synthetic@1',
            purpose=models.ProviderRun.PRIMARY if provider in ('corti', 'replay') else models.ProviderRun.INDEPENDENT,
            request_sha256=f'{self.count:064x}', request_body={}, contexts=[], state=models.ProviderRun.FAILED,
            sent=sent, http_status=status)
        if provider in ('astra', 'fable'):
            models.ProviderExchange.objects.create(run=run, turn=1, request_body={}, request_sha256='f' * 64,
                                                   state='failed', http_status=status)
        return run

    def hold(self, provider: str = 'corti', status: int = 402) -> models.ProviderHold:
        made = provider_holds.record(self.refused_run(provider, status))
        assert made is not None
        return made

    def test_status_shows_every_providers_standing_holds_and_writes_nothing(self) -> None:
        for args in ((), ('--status',)):
            with self.subTest(args=args):
                shown = self.run_command(*args)
                for name in ('corti', 'astra', 'fable'):
                    self.assertIn(f'{name}: no installation-wide hold', shown)
                self.assertNotIn('requests are not held', shown)  # refutation 6b-r2 F6: no general claim
        corti = self.hold('corti', 402)
        astra = self.hold('astra', 400)
        shown = self.run_command('--status')
        self.assertIn('corti hold (installation-wide): 1 standing; no corti request is sent by any encounter until an '
                      'operator releases it (a stored answer is still reused)', shown)
        self.assertIn(f'corti hold {corti.pk}: quota (the provider refused for payment or quota); HTTP 402; set by run '
                      f'{corti.run_id}', shown)
        self.assertIn(f'astra hold {astra.pk}: refused (the provider refused the request in a way that may hold for '
                      'every request); HTTP 400', shown)
        self.assertIn('fable: no installation-wide hold', shown)
        self.assertEqual(models.ProviderHoldRelease.objects.count(), 0)
        self.assertEqual(models.ProviderHold.objects.count(), 2)

    def test_release_ends_every_standing_hold_of_that_provider_only_and_records_who_and_why(self) -> None:
        first, second = self.hold('corti', 402), self.hold('replay', 429)  # Corti's replay is Corti's
        astra = self.hold('astra', 401)
        shown = self.run_command('--release', 'corti', '--username', self.operator.username, '--note', NOTE)
        releases = list(models.ProviderHoldRelease.objects.order_by('created_at', 'pk'))
        self.assertEqual([item.hold for item in releases], [first, second])
        self.assertEqual({(item.released_by, item.note) for item in releases}, {(self.operator, NOTE)})
        self.assertIn('2 corti holds released by synthetic-operator. The next member act - a Resume, or a save that '
                      'queues the stage - sends the held request once.', shown)
        for item in releases:
            self.assertIn(f'(release {item.pk})', shown)
        self.assertFalse(provider_holds.held('corti'))
        self.assertTrue(provider_holds.held('astra'))  # another provider's hold stands
        self.assertEqual(list(provider_holds.active('astra')), [astra])
        status = self.run_command()
        self.assertIn(f'released: corti hold {first.pk} (quota) by synthetic-operator', status)
        self.assertIn('corti: no installation-wide hold', status)
        self.assertEqual(models.ProviderHold.objects.count(), 3)  # the hold rows stay

    def test_with_no_hold_standing_status_makes_no_claim_about_a_request_still_held_per_request(self) -> None:
        # refutation 6b-r2 F6 (DECISIONS D247): a request the installed release recorded failed and sent with 402 set no
        # ProviderHold row, yet jobs._failed_before still holds its identical request (amendment 7.3, A20)
        from types import SimpleNamespace

        from studio import jobs
        run = self.refused_run('corti', 402)
        shown = self.run_command('--status')
        self.assertIn('corti: no installation-wide hold', shown)
        for claim in ('requests are not held', 'not held'):
            self.assertNotIn(claim, shown)
        held = jobs._failed_before(self.enc, SimpleNamespace(name='corti', adapter_version='synthetic@1'),
                                   SimpleNamespace(canonical_sha256=run.request_sha256))
        self.assertEqual(held.pk if held is not None else None, run.pk)  # it is held, per request: never denied
        self.assertFalse(models.ProviderHold.objects.exists())

    def test_release_reads_the_note_from_a_file(self) -> None:
        self.hold('fable', 403)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'
            path.write_text(NOTE + '\n', encoding='utf-8')
            shown = self.run_command('--release', 'fable', '--username', self.operator.username, '--note-file',
                                     str(path))
        self.assertEqual(list(models.ProviderHoldRelease.objects.values_list('note', flat=True)), [NOTE])
        self.assertIn('1 fable hold released by synthetic-operator.', shown)

    def test_every_refusal_records_nothing(self) -> None:
        self.hold('corti', 401)
        member = f.member(self.ws, f.user('synthetic-member'))
        revoked = an_operator('synthetic-revoked')
        operator.revoke(revoked, 'Synthetic revocation for a provider-hold test.', 'tests')
        cases = (
            (('--release', 'corti', '--note', NOTE), '--release needs --username'),
            (('--release', 'corti', '--username', self.operator.username), '--release needs --note-file or --note'),
            (('--username', self.operator.username), 'go with --release'),
            (('--note', NOTE), 'go with --release'),
            (('--status', '--release', 'corti', '--username', self.operator.username, '--note', NOTE),
             'give one of them'),
            (('--release', 'corti', '--username', 'nobody-at-all', '--note', NOTE), "No account is named 'nobody-at-all'"),
            (('--release', 'corti', '--username', member.username, '--note', NOTE),
             'Only an operator may release a provider hold.'),
            (('--release', 'corti', '--username', revoked.username, '--note', NOTE),
             'Only an operator may release a provider hold.'),
            (('--release', 'corti', '--username', self.operator.username, '--note', '   '), 'needs a note'),
            (('--release', 'corti', '--username', self.operator.username, '--note',
              'x' * (provider_holds.MAX_NOTE_CHARS + 1)), 'at most'),
            (('--release', 'gemini', '--username', self.operator.username, '--note', NOTE), 'Unknown provider'),
            (('--release', 'corti', '--username', self.operator.username, '--note-file',
              '/nonexistent/synthetic-note.txt'), 'The note file cannot be read'),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                with self.assertRaises(CommandError) as refused:
                    self.run_command(*args)
                self.assertIn(expected, str(refused.exception))
        self.assertEqual(models.ProviderHoldRelease.objects.count(), 0)
        self.assertTrue(provider_holds.held('corti'))

    def test_releasing_a_provider_with_no_hold_standing_is_refused(self) -> None:
        self.hold('astra', 429)
        with self.assertRaises(CommandError) as refused:
            self.run_command('--release', 'corti', '--username', self.operator.username, '--note', NOTE)
        self.assertIn('No corti hold is standing; nothing was recorded.', str(refused.exception))
        self.assertEqual(models.ProviderHoldRelease.objects.count(), 0)
        self.assertTrue(provider_holds.held('astra'))

    def test_a_hold_released_once_is_never_released_again(self) -> None:
        self.hold('corti', 402)
        self.run_command('--release', 'corti', '--username', self.operator.username, '--note', NOTE)
        with self.assertRaises(CommandError) as refused:
            self.run_command('--release', 'corti', '--username', self.operator.username, '--note', NOTE)
        self.assertIn('No corti hold is standing', str(refused.exception))
        self.assertEqual(models.ProviderHoldRelease.objects.count(), 1)
