"""What `private_mail` still owns after selection moved into the confined helper.

⚠️ THE SELECTION AND BINDING ASSERTIONS ARE NOT MISSING — THEY MOVED, to `test_confined_select.py`, with
the matcher itself. This module no longer opens a file: it decides WHICH files the run may look at, hands
the criteria to `private_storage.select_message`, and turns the helper's fixed refusal codes into prose.
Those are the things tested here.

No assertion takes a message body or a token as an operand. `unittest` prints both operands of a failed
assertEqual, so an assertion over raw bytes puts a token in the test log the first time it fails.
"""
import unittest

try:
    from . import private_mail
except ImportError:
    import private_mail

MINE = 'run-a@synthetic.quillmd.invalid'
ROUTE = '/invite/DUMMY-TOKEN-THIS-RUN-000000/'


class Helper:
    """Stands in for the confined reader, recording what it was asked for."""

    def __init__(self, files, answer=None):
        self.files = dict(files)
        self.answer = answer or {'found': True, 'reason': '', 'route': ROUTE,
                                 'records_for_this_run': 1, 'records_for_others': 0,
                                 'records_outside_synthetic': 0}
        self.asked = []
        self.RECORD_SEPARATOR = private_mail.SEPARATOR
        self.SYNTHETIC_DOMAIN = private_mail.SYNTHETIC_DOMAIN
        self.MAX_SELECT_NAMES = 8

    def inventory(self, root):
        return {name: {'sha256': digest, 'size': 1, 'mode': 0o600} for name, digest in self.files.items()}

    def select_message(self, root, names, address, purpose, pattern, expect_sha256='', expect_prefix=''):
        self.asked.append({'names': list(names), 'address': address, 'purpose': purpose,
                           'expect_sha256': expect_sha256, 'expect_prefix': expect_prefix})
        return dict(self.answer)


class WhichFilesTheRunMayLookAt(unittest.TestCase):
    def use(self, files, answer=None):
        helper = Helper(files, answer)
        self.addCleanup(setattr, private_mail, 'private_storage', private_mail.private_storage)
        private_mail.private_storage = helper
        return helper

    def test_only_the_files_that_changed_are_offered_to_the_helper(self):
        """The run is identified by a before/after diff, never by a clock: the filename's stamp is naive
        local time and `inventory()` exposes no mtime."""
        helper = self.use({'old.log': 'aa', 'new.log': 'bb'})
        before = {'old.log': 'aa'}
        private_mail.route('invite', MINE, before=before)
        self.assertEqual(helper.asked[0]['names'], ['new.log'])

    def test_a_file_whose_contents_moved_is_offered_even_though_its_name_did_not(self):
        """The append-collision a timestamp window cannot see: same name, new record, changed sha256."""
        helper = self.use({'a.log': 'after'})
        private_mail.route('invite', MINE, before={'a.log': 'before'})
        self.assertEqual(helper.asked[0]['names'], ['a.log'])

    def test_a_file_that_did_not_change_is_never_offered(self):
        helper = self.use({'a.log': 'same'})
        with self.assertRaises(private_mail.MailUnavailable) as refusal:
            private_mail.route('invite', MINE, before={'a.log': 'same'})
        self.assertEqual(helper.asked, [], 'an unchanged file was handed to the helper')
        self.assertIn('no outbox file changed', str(refusal.exception))

    def test_an_implausible_number_of_changed_files_refuses_before_asking(self):
        helper = self.use({'f%d.log' % n: str(n) for n in range(40)})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', MINE, before={})
        self.assertEqual(helper.asked, [])

    def test_a_non_synthetic_address_is_refused_before_asking(self):
        helper = self.use({'a.log': 'new'})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', 'doctor@example.com', before={})
        self.assertEqual(helper.asked, [])

    def test_an_unknown_purpose_is_refused_before_asking(self):
        helper = self.use({'a.log': 'new'})
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('verify', MINE, before={})
        self.assertEqual(helper.asked, [])

    def test_the_expectations_are_passed_through_to_the_helper(self):
        """If these did not travel, the binding would not happen and nothing would say so."""
        helper = self.use({'a.log': 'new'})
        private_mail.route('invite', MINE, before={}, expect_sha256='a' * 64)
        self.assertEqual(helper.asked[0]['expect_sha256'], 'a' * 64)
        self.assertEqual(helper.asked[0]['purpose'], 'invite')
        self.assertEqual(helper.asked[0]['address'], MINE)


class TheHelperSRefusalsBecomeProse(unittest.TestCase):
    def use(self, reason):
        helper = Helper({'a.log': 'new'}, answer={'found': False, 'reason': reason, 'route': '',
                                                  'records_for_this_run': 0, 'records_for_others': 1,
                                                  'records_outside_synthetic': 1 if reason == 'outside_synthetic' else 0})
        self.addCleanup(setattr, private_mail, 'private_storage', private_mail.private_storage)
        private_mail.private_storage = helper
        return helper

    def test_every_reason_the_helper_can_return_has_a_sentence(self):
        """⚠️ A CODE WITH NO SENTENCE WOULD SURFACE AS A GENERIC FAILURE, which is how a specific refusal
        becomes 'something went wrong' in a report."""
        for reason in ('outside_synthetic', 'no_record_for_this_run', 'more_than_one_record',
                       'no_link_of_this_purpose', 'token_not_bound'):
            self.use(reason)
            with self.assertRaises(private_mail.MailUnavailable) as refusal:
                private_mail.route('invite', MINE, before={})
            self.assertIn(reason, private_mail.REASONS)
            self.assertEqual(str(refusal.exception), private_mail.REASONS[reason])

    def test_no_refusal_sentence_can_carry_a_token_or_a_filename(self):
        for reason, sentence in private_mail.REASONS.items():
            self.assertNotIn('DUMMY', sentence)
            self.assertNotIn('.log', sentence)


class WhatAReportMayRecord(unittest.TestCase):
    def use(self, answer=None):
        helper = Helper({'a.log': 'new'}, answer)
        self.addCleanup(setattr, private_mail, 'private_storage', private_mail.private_storage)
        private_mail.private_storage = helper
        return helper

    def test_notes_are_counts_and_booleans_only(self):
        self.use()
        notes = {}
        private_mail.route('invite', MINE, before={}, notes=notes, expect_sha256='a' * 64)
        self.assertEqual(notes, {'changed_paths': 1, 'records_for_this_run': 1, 'records_for_others': 0,
                                 'records_outside_synthetic': 0, 'token_bound': True})
        self.assertTrue(all(v is None or isinstance(v, (int, bool)) for v in notes.values()))

    def test_a_run_with_no_expectation_records_unbound_rather_than_true(self):
        """A caller that asked for no binding must not read as one whose token bound."""
        self.use()
        notes = {}
        private_mail.route('invite', MINE, before={}, notes=notes)
        self.assertIsNone(notes['token_bound'])

    def test_a_refusal_still_leaves_the_counts_behind(self):
        """The counts are the only thing a failed run can report, so they must survive the raise."""
        self.use({'found': False, 'reason': 'outside_synthetic', 'route': '',
                  'records_for_this_run': 0, 'records_for_others': 2, 'records_outside_synthetic': 1})
        notes = {}
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', MINE, before={}, notes=notes, expect_sha256='a' * 64)
        self.assertEqual(notes['records_outside_synthetic'], 1)
        self.assertIs(notes['token_bound'], False)


class TheHostSideFinalCheck(unittest.TestCase):
    """`check_token` needs the secret key and the user's password hash, so it cannot run in the helper.
    It runs last, on a token that has already satisfied the in-container binding."""

    def use(self):
        helper = Helper({'a.log': 'new'})
        self.addCleanup(setattr, private_mail, 'private_storage', private_mail.private_storage)
        private_mail.private_storage = helper
        return helper

    def test_it_receives_the_token_without_its_route_wrapper(self):
        self.use()
        seen = {}
        private_mail.route('invite', MINE, before={}, verify=lambda t: seen.setdefault('token', t) or True)
        self.assertEqual(seen['token'], 'DUMMY-TOKEN-THIS-RUN-000000')

    def test_a_token_it_rejects_is_refused(self):
        self.use()
        notes = {}
        with self.assertRaises(private_mail.MailUnavailable) as refusal:
            private_mail.route('invite', MINE, before={}, notes=notes, verify=lambda t: False)
        self.assertIn('does not belong to the record this run created', str(refusal.exception))
        self.assertIs(notes['token_bound'], False)
        self.assertNotIn('DUMMY', str(refusal.exception))

    def test_a_predicate_that_raises_refuses_rather_than_admitting_the_token(self):
        self.use()
        notes = {}

        def explode(_token):
            raise RuntimeError('the record lookup failed')
        with self.assertRaises(private_mail.MailUnavailable):
            private_mail.route('invite', MINE, before={}, notes=notes, verify=explode)
        self.assertIs(notes['token_bound'], False)


class Describe(unittest.TestCase):
    def test_it_records_that_a_route_was_found_without_recording_it(self):
        described = private_mail.describe('/invite/SUPERSECRETTOKENVALUE/')
        self.assertEqual(described, {'found': True, 'kind': 'invite',
                                     'token_characters': len('SUPERSECRETTOKENVALUE')})
        self.assertNotIn('SUPERSECRET', repr(described))
        self.assertEqual(private_mail.describe(''), {'found': False, 'kind': '', 'token_characters': 0})

    def test_it_keeps_the_two_segment_recovery_kind_whole(self):
        described = private_mail.describe('/recovery/confirm/MTIz/cq8x2-0123456789abcdef/')
        self.assertEqual(described['kind'], 'recovery/confirm')
        self.assertEqual(described['token_characters'], len('MTIz/cq8x2-0123456789abcdef'))

    def test_it_refuses_to_name_a_kind_it_does_not_know(self):
        self.assertEqual(private_mail.describe('/verify/SOMETOKENVALUE0000/'),
                         {'found': False, 'kind': '', 'token_characters': 0})


class TheInstrumentSOwnPositiveControl(unittest.TestCase):
    def test_a_reader_that_cannot_answer_raises_rather_than_reporting_an_empty_outbox(self):
        """Every private_storage failure collapses to one generic string, so an empty return must never be
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
