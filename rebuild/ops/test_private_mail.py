"""What the outbox reader may and may not do.

⚠️ NO ASSERTION IN THIS FILE TAKES A MESSAGE BODY OR A TOKEN AS AN OPERAND. `unittest` prints both operands
of a failed assertEqual/assertIn, so an assertion over raw message bytes puts a raw token into the test log
the first time it fails — with no mistake by the author beyond writing a normal assertion. Everything here
asserts over derived booleans, counts and sentinel-substituted strings instead.
"""
import unittest

try:
    from . import private_mail
except ImportError:
    import private_mail

SEP = private_mail.SEPARATOR
MINE = 'run-a@synthetic.quillmd.invalid'
OTHER = 'someone-else@synthetic.quillmd.invalid'


# The shape core/recovery.py actually emits: urlsafe_base64_encode(pk) / <base36>-<hex>.
RECOVERY_TOKEN = 'MTIz/cq8x2-0123456789abcdef0123456789abcdef'


def record(to, token, route='invite'):
    return ('Content-Type: text/plain\nTo: %s\nSubject: x\n\n'
            'Accept your QuillMD department invitation at http://127.0.0.1:9130/%s/%s/\n'
            % (to, route, token)).encode()


def blob(*records):
    return SEP.join(records) + SEP


class Outbox:
    """Stands in for the confined reader, and records which files were actually opened."""

    def __init__(self, files):
        self.files = dict(files)
        self.opened = []

    def inventory(self, root):
        import hashlib
        return {name: {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'mode': '0600'}
                for name, data in self.files.items()}

    def read_file(self, root, relative):
        self.opened.append(relative)
        return self.files[relative]


class Reader(unittest.TestCase):
    def use(self, files):
        outbox = Outbox(files)
        self.addCleanup(setattr, private_mail, 'private_storage', private_mail.private_storage)
        private_mail.private_storage = outbox
        return outbox

    # ---- the demonstrated defect this module was rewritten for ----------------------------------

    def test_one_file_holding_three_recipients_yields_this_run_s_token_not_the_first_one(self):
        """The refutation pass produced exactly this file and watched first-match return a stranger's token.

        Django names outbox files `%Y%m%d-%H%M%S-abs(id(self))` and the application opens them O_APPEND, and
        `abs(id(self))` is a recycled address that does not vary. Three sends in one second share one file.
        """
        self.use({'20260919-043525-1.log': blob(record(OTHER, 'TOKEN-OTHER-ACCOUNT-0000'),
                                                record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'),
                                                record('third@synthetic.quillmd.invalid', 'TOKEN-THIRD-0000000'))})
        found = private_mail.route('invite', MINE, before={})
        # Sentinel comparison, not the token: a failure here prints 'mine'/'stranger', never the secret.
        self.assertEqual('mine' if found.endswith('/TOKEN-BELONGING-TO-THIS-RUN/') else 'stranger', 'mine')

    def test_a_record_for_a_longer_address_that_contains_ours_is_not_ours(self):
        self.use({'a.log': blob(record('run-a2@synthetic.quillmd.invalid', 'TOKEN-FOR-THE-OTHER-RUN'))})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', MINE, before={})

    def test_two_records_for_this_run_refuse_rather_than_taking_the_first(self):
        self.use({'a.log': blob(record(MINE, 'TOKEN-ONE-AAAAAAAAAAAAA'), record(MINE, 'TOKEN-TWO-BBBBBBBBBBBBB'))})
        with self.assertRaises(private_mail.MailUnavailable) as refusal:
            private_mail.route('invite', MINE, before={})
        self.assertIn('more than one message', str(refusal.exception))

    # ---- the run is selected by change, not by a clock ------------------------------------------

    def test_a_file_that_did_not_change_is_never_opened(self):
        outbox = self.use({'old.log': blob(record(OTHER, 'TOKEN-FROM-BEFORE-THE-RUN')),
                           'new.log': blob(record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'))})
        before = dict(private_mail.snapshot())
        before.pop('new.log')
        private_mail.route('invite', MINE, before=before)
        self.assertEqual(outbox.opened, ['new.log'])

    def test_a_pre_existing_file_that_was_appended_to_is_still_considered(self):
        """The append-collision a timestamp window cannot see: same name, new record, changed sha256."""
        outbox = self.use({'a.log': blob(record(OTHER, 'TOKEN-FROM-BEFORE-THE-RUN'))})
        before = private_mail.snapshot()
        outbox.files['a.log'] = blob(record(OTHER, 'TOKEN-FROM-BEFORE-THE-RUN'),
                                     record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'))
        found = private_mail.route('invite', MINE, before=before)
        self.assertEqual('mine' if found.endswith('/TOKEN-BELONGING-TO-THIS-RUN/') else 'stranger', 'mine')

    def test_an_implausible_number_of_changed_files_refuses_before_reading_any(self):
        outbox = self.use({'f%d.log' % n: blob(record(MINE, 'TOKEN-%013d' % n)) for n in range(40)})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', MINE, before={})
        self.assertEqual(outbox.opened, [])

    # ---- refusals that happen before a single byte is read --------------------------------------

    def test_a_non_synthetic_address_is_refused_before_anything_is_read(self):
        outbox = self.use({'a.log': blob(record('doctor@example.com', 'TOKEN-A-REAL-PERSONS-000'))})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', 'doctor@example.com', before={})
        self.assertEqual(outbox.opened, [])

    def test_an_unknown_route_kind_is_refused_before_anything_is_read(self):
        outbox = self.use({'a.log': blob(record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'))})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('verify', MINE, before={})
        self.assertEqual(outbox.opened, [])

    # ---- honest reporting ------------------------------------------------------------------------

    def test_the_right_message_without_the_right_link_is_a_finding(self):
        self.use({'a.log': ('To: %s\n\nNo link here at all.\n' % MINE).encode() + SEP})
        with self.assertRaises(private_mail.MailUnavailable) as refusal:
            private_mail.route('invite', MINE, before={})
        self.assertIn('carries no invite link', str(refusal.exception))

    def test_a_recovery_link_is_not_found_by_the_invitation_pattern(self):
        self.use({'a.log': blob(record(MINE, RECOVERY_TOKEN, route='recovery/confirm'))})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', MINE, before={})
        self.assertTrue(private_mail.route('recovery/confirm', MINE, before={}).startswith('/recovery/confirm/'))

    def test_the_recovery_token_is_two_segments_and_a_one_segment_pattern_would_miss_it(self):
        """core/recovery.py builds `<uidb64>/<token>` and urls.py routes it as two path segments. A pattern
        that stops at the first slash matches the invitation fine and never matches this at all."""
        self.use({'a.log': blob(record(MINE, RECOVERY_TOKEN, route='recovery/confirm'))})
        found = private_mail.route('recovery/confirm', MINE, before={})
        self.assertEqual(found.strip('/').count('/'), 3)          # recovery / confirm / uidb64 / token
        self.assertEqual(private_mail.describe(found),
                         {'found': True, 'kind': 'recovery/confirm',
                          'token_characters': len(RECOVERY_TOKEN)})

    def test_notes_publish_counts_and_never_a_name_or_a_token(self):
        self.use({'a.log': blob(record(OTHER, 'TOKEN-OTHER-ACCOUNT-0000'),
                                record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'))})
        notes = {}
        private_mail.route('invite', MINE, before={}, notes=notes)
        self.assertEqual(notes, {'changed_paths': 1, 'records_for_this_run': 1, 'records_for_others': 1,
                                 'records_outside_synthetic': 0, 'files_unreadable': 0})
        self.assertTrue(all(isinstance(value, int) for value in notes.values()))

    def test_a_message_for_a_real_address_in_the_same_file_stops_the_run(self):
        """read_file is all-or-nothing, so the stranger's bytes are already here by the time this fires.

        The guard cannot prevent the read and does not claim to. What it prevents is CONTINUING QUIETLY:
        a refutation pass put a real-shaped verification token for a non-synthetic address into the same
        file as the run's own message, and the counts reported it truthfully as `records_for_others: 1` —
        which reads like "left alone" and is exactly what a reader would not question.
        """
        self.use({'a.log': blob(record('dr.mercer@stpeters-clinic.example', 'TOKEN-A-REAL-PERSONS-000'),
                                record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'))})
        notes = {}
        with self.assertRaises(private_mail.MailUnavailable) as refusal:
            private_mail.route('invite', MINE, before={}, notes=notes)
        self.assertIn('outside the synthetic test domain', str(refusal.exception))
        self.assertEqual(notes['records_outside_synthetic'], 1)
        # The refusal names a count and nothing else: no address, no filename, no content.
        self.assertNotIn('mercer', str(refusal.exception))
        self.assertNotIn('a.log', str(refusal.exception))

    def test_another_synthetic_run_sharing_the_file_is_counted_but_does_not_stop_this_one(self):
        """The append-collision is the normal case this module exists for and must still work."""
        notes = {}
        self.use({'a.log': blob(record(OTHER, 'TOKEN-OTHER-ACCOUNT-0000'),
                                record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'))})
        found = private_mail.route('invite', MINE, before={}, notes=notes)
        self.assertEqual('mine' if found.endswith('/TOKEN-BELONGING-TO-THIS-RUN/') else 'stranger', 'mine')
        self.assertEqual((notes['records_for_others'], notes['records_outside_synthetic']), (1, 0))

    def test_a_record_with_no_to_header_at_all_stops_the_run(self):
        self.use({'a.log': blob(b'Subject: no addressee\n\nnothing here\n',
                                record(MINE, 'TOKEN-BELONGING-TO-THIS-RUN'))})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', MINE, before={})

    def test_describe_records_that_a_route_was_found_without_recording_it(self):
        described = private_mail.describe('/invite/SUPERSECRETTOKENVALUE/')
        self.assertEqual(described, {'found': True, 'kind': 'invite',
                                     'token_characters': len('SUPERSECRETTOKENVALUE')})
        self.assertNotIn('SUPERSECRET', repr(described))
        self.assertEqual(private_mail.describe(''), {'found': False, 'kind': '', 'token_characters': 0})

    def test_describe_keeps_the_two_segment_recovery_kind_whole(self):
        described = private_mail.describe('/recovery/confirm/MTIz/cq8x2-0123456789abcdef/')
        self.assertEqual(described['kind'], 'recovery/confirm')
        self.assertEqual(described['token_characters'], len('MTIz/cq8x2-0123456789abcdef'))

    def test_describe_refuses_to_name_a_kind_it_does_not_know(self):
        self.assertEqual(private_mail.describe('/verify/SOMETOKENVALUE0000/'),
                         {'found': False, 'kind': '', 'token_characters': 0})

    # ---- the instrument's own positive control ---------------------------------------------------

    def test_a_reader_that_cannot_answer_raises_rather_than_reporting_an_empty_outbox(self):
        """Every private_storage failure collapses to one generic string, so an empty return must not be
        confused with 'the application sent nothing'. snapshot() is the caller's control for that."""
        class Broken:
            def inventory(self, root):
                raise RuntimeError('Private storage inventory failed')
        self.addCleanup(setattr, private_mail, 'private_storage', private_mail.private_storage)
        private_mail.private_storage = Broken()
        with self.assertRaises(RuntimeError):
            private_mail.snapshot()


if __name__ == '__main__':
    unittest.main()
