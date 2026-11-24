"""Release 1, integrated refutation round 1, repair builder D: disposal, the ledger and the export.

- D1 (phileak-0, dataloss-0, and the command half of phileak-1 / dataloss-3): a disposal's reason leaves the database
  only as its digest - in every ledger entry and certificate, so in no receipt or log - while the DisposalEvent rows keep
  its text; a replay's own events name the digest; a ledger is read line by line on the newline alone; a person's name
  holding a line break is refused.

Synthetic practices only, on a test database and originals folders of the tests' own."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from studio import disposal, models, storage
from tests import test_disposal as td

Event = models.DisposalEvent
# the lens's reason (phileak-0): the misfiled-document case D1 is built for, naming the document's patient
PLAN_REASON = ('ZZ-REASON-MARKER Misfiled upload: the colonoscopy note of Jane Roe (DOB 1970-01-02) was uploaded to '
               'the wrong practice; destroy it the same day.\n')
# the lens's separators (dataloss-0), all three in one reason
SEPARATED_REASON = ('Synthetic: the practice ended its contract.\u2028It chose destruction in writing.\u2029Signed by '
                    'both.\u0085Filed the same day.')
REASON_WORDS = ('ZZ-REASON-MARKER', 'Jane Roe', '1970-01-02')


def digest_of(reason) -> str:
    """The digest a ledger and a certificate carry for ``reason`` as read from its file (stripped, as stored)."""
    return 'sha256:' + hashlib.sha256(reason.strip().encode('utf-8')).hexdigest()


def echoes(reason, output) -> list:
    """What of ``reason`` ``output`` repeats, read as the installer's guard reads it (ops/install.py reason_values and
    assert_no_secret): its whole text, and each of its lines of 12 characters or more."""
    text = reason.strip()
    parts = [text, *[line.strip() for line in text.splitlines() if len(line.strip()) >= 12]]
    return [part for part in parts if part in output] + [word for word in REASON_WORDS if word in output]


class ReasonCase(td.RepairCase):
    def destroy_practice(self, reason):
        """Practice A closed, planned and destroyed with ``reason`` (the same file for each step)."""
        self.seed()
        path = td.reason_file(self.scratch.name, reason)
        printed = {'close': self.command('--close', '--workspace', str(self.ws.pk), '--by', 'Ada Lovelace',
                                         '--reason-file', path),
                   'plan': self.command('--plan', '--workspace', str(self.ws.pk), '--by', 'Ada Lovelace',
                                        '--reason-file', path)}
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        printed['execute'], error = self.carry_out(plan)
        self.assertIsNone(error, printed['execute'])
        return printed

    def restore_older_backup(self):
        """What a restore from a backup older than the disposal brings back (tests.test_disposal.LedgerTests): practice A
        open with a document's rows and file and its memberships on - and none of the ledger's rows."""
        self.forget_the_ledger()
        models.Workspace.objects.filter(pk=self.ws.pk).update(closed_at=None)
        models.Membership.objects.filter(workspace=self.ws).update(active=True)
        revision = self.restore_document(self.a_note, 'R')
        return storage.stored_path(revision.source_file.storage_name)

    def assert_destroyed_again(self, stored):
        tomb = models.Encounter._base_manager.get(pk=self.a_note.pk)
        self.assertIsNotNone(tomb.destroyed_at)
        self.assertEqual((tomb.title, tomb.state), ('', disposal.TOMBSTONE_STATE))
        self.assertFalse(stored.exists())
        self.assertIsNotNone(models.Workspace.objects.get(pk=self.ws.pk).closed_at)
        self.assertFalse(models.Membership.objects.filter(workspace=self.ws, active=True).exists())


class ReasonDigestTests(ReasonCase, TestCase):
    """D1, phileak-0 and the command half of phileak-1 / dataloss-3: the reason's words reach no output of dispose or
    export_workspace - not the certificate (whose ledger line carried them into the installer's receipt and log), not
    the ledger - only its digest; the DisposalEvent rows keep the text."""

    def test_the_lenss_execute_certificate_and_ledger_hold_the_reasons_digest_never_its_words(self):
        # the lens's input: the plan's reason names the patient; execute is given a reason file of its own
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        own = td.reason_file(self.scratch.name, 'Ticket 4521: carry out the approved plan.\n')
        printed = {'close': self.command('--close', '--workspace', str(self.ws.pk), '--by', 'Ada Lovelace',
                                         '--reason-file', reason),
                   'plan': self.command('--plan', '--encounter', str(self.a_note.pk), '--by', 'Ada Lovelace',
                                        '--reason-file', reason)}
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        with td.installer_idle():
            printed['execute'], error = self.dispose_command(
                '--execute', '--plan', str(plan.pk), '--by', 'Ada Lovelace', '--approved-by', 'Grace Hopper',
                '--reason-file', own, '--authorization-ref', td.AUTH)
        self.assertIsNone(error, printed['execute'])
        printed['ledger'] = self.command('--ledger')
        for name, output in printed.items():
            with self.subTest(output=name):
                self.assertEqual(echoes(PLAN_REASON, output), [])
        digest = digest_of(PLAN_REASON)
        self.assertIn(f'Reason: {digest} (', printed['execute'])
        line = next(line for line in printed['execute'].splitlines() if line.startswith('Ledger line'))
        self.assertIn(f'"reason":"{digest}"', line)
        entries = disposal.read_ledger(printed['ledger'].split('\n'))
        self.assertEqual([entry['stage'] for entry in entries],
                         [Event.CLOSED, Event.PLANNED, disposal.COMMITTED, Event.COMPLETED])
        self.assertEqual({entry['reason'] for entry in entries}, {digest})
        # the rows keep the text (spec 3.1)
        self.assertEqual(set(Event.objects.values_list('reason', flat=True)), {PLAN_REASON.strip()})

    def test_a_failed_runs_certificate_holds_no_reason_words_either(self):
        # dataloss-3's second shape: the run fails after the commit (the practice's folder read-only) and its
        # certificate says what remains - with the reason only as its digest
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        self.command('--plan', '--encounter', str(self.a_note.pk), '--by', 'Ada Lovelace', '--reason-file', reason)
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        with td.read_only(storage.workspace_folder(self.ws.pk)):
            output, error = self.carry_out(plan)
        self.assertIn('did not complete', error)
        self.assertIn('Files remaining, by storage name', output)
        self.assertEqual(echoes(PLAN_REASON, output + error), [])
        self.assertIn(f'Reason: {digest_of(PLAN_REASON)} (', output)
        self.assertEqual(Event.objects.get(stage=Event.FAILED).reason, PLAN_REASON.strip())

    def test_an_unrecorded_runs_certificate_holds_no_reason_words_either(self):
        # the run's final event cannot be written: its certificate, printed instead, is the record
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        self.command('--plan', '--encounter', str(self.a_note.pk), '--by', 'Ada Lovelace', '--reason-file', reason)
        plan = Event.objects.filter(stage=Event.PLANNED).latest('created_at')
        real = Event.objects.create

        def create(**values):
            if values.get('stage') in (Event.COMPLETED, Event.FAILED):
                raise RuntimeError('synthetic: the final DisposalEvent cannot be written')
            return real(**values)
        with mock.patch.object(Event.objects, 'create', side_effect=create):
            output, error = self.carry_out(plan)
        self.assertIn('NOT RECORDED', output)
        self.assertEqual(echoes(PLAN_REASON, output + error), [])
        self.assertIn(f'Reason: {digest_of(PLAN_REASON)} (', output)

    def test_an_exports_output_and_ledger_entry_hold_only_its_reasons_digest(self):
        self.seed()
        reason = td.reason_file(self.scratch.name, PLAN_REASON)
        printed = io.StringIO()
        call_command('export_workspace', '--workspace', str(self.ws.pk), '--out', str(Path(self.scratch.name) / 'out'),
                     '--by', 'Ada Lovelace', '--reason-file', reason, stdout=printed)
        ledger = self.command('--ledger')
        for output in (printed.getvalue(), ledger):
            self.assertEqual(echoes(PLAN_REASON, output), [])
        event = Event.objects.get(stage=Event.EXPORTED)
        self.assertEqual(event.reason, PLAN_REASON.strip())
        (entry,) = [entry for entry in disposal.read_ledger(ledger.split('\n')) if entry['id'] == str(event.pk)]
        self.assertEqual(entry['reason'], digest_of(PLAN_REASON))

    def test_a_replay_names_the_digest_it_replays_and_the_rows_it_writes_back_hold_it(self):
        self.destroy_practice(PLAN_REASON)
        ledger = self.ledger_file()
        lines = [line for line in ledger.read_text(encoding='utf-8').split('\n') if line]
        original = disposal.read_ledger(lines)
        stored = self.restore_older_backup()
        dry, error = self.dispose_command('--replay-ledger', str(ledger))
        self.assertIsNone(error, dry)
        output, error = self.replay(ledger)
        self.assertIsNone(error, output)
        self.assert_destroyed_again(stored)
        for text in (dry, output):
            self.assertEqual(echoes(PLAN_REASON, text), [])
        digest = digest_of(PLAN_REASON)
        replayed = Event.objects.filter(notes__startswith=f'replay={original[-1]["id"]};')
        self.assertEqual(sorted(replayed.values_list('stage', flat=True)), sorted([disposal.COMMITTED, Event.COMPLETED]))
        self.assertEqual(set(replayed.values_list('reason', flat=True)), {digest})  # the replay's own events
        for entry in original:  # written back from the ledger: the digest where the original held the text
            row = Event.objects.get(pk=entry['id'])
            self.assertEqual(row.reason, digest)
            self.assertEqual(disposal._entry(row), entry)
        again = {json.loads(line)['entry']['id']: line for line in self.command('--ledger').split('\n') if line}
        for line in lines:  # each written-back row's ledger line, MAC included, is the original's, byte for byte
            self.assertEqual(again[json.loads(line)['entry']['id']], line)


class LedgerLineTests(ReasonCase, TestCase):
    """D1, dataloss-0: a genuine ledger replays whatever its reasons hold - U+2028, U+2029, U+0085 - read line by line on
    the newline alone; and a ledger written before this repair, whose lines hold such a reason's text raw, replays too."""

    def test_the_lenss_ledger_whose_reason_holds_line_separators_replays_after_a_restore(self):
        self.destroy_practice(SEPARATED_REASON)
        ledger = self.ledger_file()
        text = ledger.read_text(encoding='utf-8')
        self.assertFalse({'\u2028', '\u2029', '\u0085'} & set(text))  # the digest: nothing of the reason is in it
        stored = self.restore_older_backup()
        dry, error = self.dispose_command('--replay-ledger', str(ledger))
        self.assertIsNone(error, dry)
        output, error = self.replay(ledger)
        self.assertIsNone(error, output)
        self.assertIn('Ledger rows restored: 4', output)
        self.assert_destroyed_again(stored)

    def test_a_ledger_holding_a_reasons_separators_raw_is_read_on_the_newline_alone(self):
        # a ledger as the integration head wrote it (before the digest): each entry's reason is the row's text, raw in
        # its line (json.dumps with ensure_ascii=False), its MAC over that entry - genuine, and cut by str.splitlines()
        self.destroy_practice(SEPARATED_REASON)
        texts = {str(pk): reason for pk, reason in Event.objects.values_list('pk', 'reason')}
        old = []
        for line in self.ledger_file().read_text(encoding='utf-8').split('\n'):
            if line:
                entry = json.loads(line)['entry']
                entry['reason'] = texts[entry['id']]
                old.append(json.dumps({'entry': entry, 'mac': disposal._mac(entry)}, sort_keys=True,
                                      separators=(',', ':'), ensure_ascii=False))
        ledger = Path(self.scratch.name) / 'ledger-before-the-repair.jsonl'
        ledger.write_text('\n'.join(old), encoding='utf-8')
        written = ledger.read_text(encoding='utf-8')
        self.assertTrue({'\u2028', '\u2029', '\u0085'} <= set(written))  # the control: raw in the file
        self.assertGreater(len(written.splitlines()), len(old))  # the control: splitlines() cuts the genuine lines
        self.assertEqual(len(disposal.read_ledger(written.split('\n'))), len(old))
        stored = self.restore_older_backup()
        dry, error = self.dispose_command('--replay-ledger', str(ledger))
        self.assertIsNone(error, dry)
        output, error = self.replay(ledger)
        self.assertIsNone(error, output)
        self.assert_destroyed_again(stored)
        replayed = Event.objects.filter(notes__startswith='replay=')
        self.assertEqual(set(replayed.values_list('reason', flat=True)), {digest_of(SEPARATED_REASON)})
        self.assertNotIn('\u2028', output)


class OneLineNameTests(SimpleTestCase):
    """D1's check of every other output: a name person() accepts is printed in every certificate and ledger line. A
    line break in it used to become a space; it is refused - every character str.splitlines() breaks a line at."""

    BREAKS = '\n\x0b\x0c\r\x1c\x1d\x1e\x85\u2028\u2029'  # in code point order

    def test_a_name_holding_a_line_break_is_refused(self):
        for ch in self.BREAKS:
            with self.subTest(ch=ascii(ch)):
                with self.assertRaisesMessage(disposal.Refused, '--by is one line'):
                    disposal.person(f'Ada{ch}Lovelace')
                with self.assertRaisesMessage(disposal.Refused, '--approved-by is one line'):
                    disposal.two_people('Grace Hopper', f'Ada Lovelace{ch}')

    def test_the_refused_characters_are_exactly_pythons_line_breaks(self):
        found = ''.join(chr(code) for code in range(0x110000) if not 0xD800 <= code <= 0xDFFF
                        and disposal.breaks_a_line(chr(code)))
        self.assertEqual(found, self.BREAKS)

    def test_other_white_space_is_still_one_space_and_names_pass(self):
        self.assertEqual(disposal.person('Ada\tLovelace  '), 'Ada Lovelace')
        self.assertEqual(disposal.two_people('Ada Lovelace', 'Grace Hopper'), ('Ada Lovelace', 'Grace Hopper'))
