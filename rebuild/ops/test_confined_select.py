"""The record matcher, tested where it now lives: inside the confined helper's own source.

⚠️ THESE ASSERTIONS USED TO LIVE IN `test_private_mail.py`, AND MOVING THEM IS THE POINT. The matcher was
in the operator process, so the whole file crossed the boundary and unrelated records were rejected
afterwards. It now runs in the helper, over bytes that never leave it, and only a matched route comes back.
Testing it here keeps ONE implementation with ONE test home — a second copy of a matcher is the exact
defect this whole repair exists for.

`_selected` is a pure function over bytes, so every case below runs with no container and no Docker.
"""
import hashlib
import json
import unittest

try:
    from . import private_storage as storage
except ImportError:
    import private_storage as storage

MINE = 'run-a@synthetic.quillmd.invalid'
OTHER = 'someone-else@synthetic.quillmd.invalid'
REAL_PERSON = 'dr.mercer@stpeters-clinic.example'
OURS = 'DUMMY-TOKEN-THIS-RUN-000000'
THEIRS = 'DUMMY-TOKEN-ANOTHER-ACCOUNT'
CANARY = 'DUMMY-CANARY-NEVER-LEAVES-0'
INVITE = r'/invite/(?P<token>[A-Za-z0-9_-]{16,512})/'
RECOVERY = r'/recovery/confirm/(?P<token>[A-Za-z0-9_-]{2,512}/[0-9a-z]{4,12}-[0-9a-z]{16,128})/'
RECOVERY_TOKEN = 'MTIz/cq8x2-0123456789abcdef0123456789abcdef'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def record(to, token, purpose='invite'):
    return ('Content-Type: text/plain\nTo: %s\nSubject: x\n\n'
            'Accept your QuillMD department invitation at http://127.0.0.1:9130/%s/%s/\n'
            % (to, purpose, token)).encode()


def blob(*records):
    return storage.RECORD_SEPARATOR.join(records) + storage.RECORD_SEPARATOR


def select(blobs, address=MINE, purpose='invite', pattern=INVITE, **expect):
    criteria = {'names': ['x.log'], 'address': address, 'purpose': purpose, 'pattern': pattern}
    criteria.update(expect)
    return storage._selected(blobs, criteria)


class OnlyTheMatchedRouteCrossesTheBoundary(unittest.TestCase):
    def assertCarriesNothingElse(self, result, *forbidden):
        """The return value is what leaves the container. Nothing unrelated may be in it."""
        rendered = json.dumps(result)
        for value in forbidden:
            self.assertNotIn(value, rendered, 'an unrelated value reached the returned result')

    def test_one_file_three_recipients_returns_this_run_s_token_and_nothing_else(self):
        """The shape a refutation pass used to break the old reader: one file, three records, three tokens."""
        result = select([blob(record(OTHER, THEIRS), record(MINE, OURS),
                              record('third@synthetic.quillmd.invalid', CANARY))],
                        expect_sha256=digest(OURS))
        self.assertTrue(result['found'])
        self.assertEqual('mine' if result['route'].endswith('/%s/' % OURS) else 'stranger', 'mine')
        self.assertEqual((result['records_for_this_run'], result['records_for_others']), (1, 2))
        self.assertCarriesNothingElse(result, THEIRS, CANARY)

    def test_a_stranger_token_delivered_to_our_address_is_refused_inside_the_helper(self):
        """Selection alone cannot catch this; the binding can, and it does so before anything is returned."""
        result = select([blob(record(MINE, THEIRS))], expect_sha256=digest(OURS))
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'token_not_bound')
        self.assertEqual(result['route'], '')
        self.assertCarriesNothingElse(result, THEIRS)

    def test_a_message_for_a_real_address_stops_the_run_and_never_leaves(self):
        """⚠️ THE CANARY. Under the previous arrangement this record's complete bytes — a live token for a
        NON-synthetic address — were exported into the operator process and rejected there. Now it is
        counted and dropped on the service side, and the result carries no trace of it."""
        result = select([blob(record(REAL_PERSON, CANARY), record(MINE, OURS))], expect_sha256=digest(OURS))
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'outside_synthetic')
        self.assertEqual(result['records_outside_synthetic'], 1)
        self.assertCarriesNothingElse(result, CANARY, 'mercer', 'stpeters')

    def test_two_records_for_our_address_refuse_rather_than_taking_either(self):
        result = select([blob(record(MINE, OURS), record(MINE, THEIRS))], expect_sha256=digest(OURS))
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'more_than_one_record')
        self.assertCarriesNothingElse(result, OURS, THEIRS)

    def test_no_record_for_us_at_all(self):
        result = select([blob(record(OTHER, THEIRS))], expect_sha256=digest(OURS))
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'no_record_for_this_run')
        self.assertCarriesNothingElse(result, THEIRS)

    def test_the_right_record_without_the_right_purpose(self):
        result = select([blob(record(MINE, RECOVERY_TOKEN, purpose='recovery/confirm'))],
                        expect_sha256=digest(OURS))
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'no_link_of_this_purpose')
        self.assertCarriesNothingElse(result, RECOVERY_TOKEN)

    def test_a_longer_address_that_contains_ours_is_not_ours(self):
        result = select([blob(record('run-a2@synthetic.quillmd.invalid', THEIRS))],
                        expect_sha256=digest(OURS))
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'no_record_for_this_run')

    def test_a_record_with_no_addressee_at_all_stops_the_run(self):
        result = select([blob(b'Subject: no addressee\n\nnothing here\n', record(MINE, OURS))],
                        expect_sha256=digest(OURS))
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'outside_synthetic')

    def test_the_two_segment_recovery_shape_binds_on_its_prefix(self):
        """`core/recovery.py` emits `<uidb64>/<token>`, and the helper can check the uidb64 without a
        database — which is why the prefix is the part that crosses into the container."""
        result = select([blob(record(MINE, RECOVERY_TOKEN, purpose='recovery/confirm'))],
                        purpose='recovery/confirm', pattern=RECOVERY, expect_prefix='MTIz')
        self.assertTrue(result['found'])
        self.assertTrue(result['route'].startswith('/recovery/confirm/MTIz/'))

    def test_a_recovery_token_for_a_different_user_is_refused_on_its_prefix(self):
        result = select([blob(record(MINE, RECOVERY_TOKEN, purpose='recovery/confirm'))],
                        purpose='recovery/confirm', pattern=RECOVERY, expect_prefix='OTHERUID')
        self.assertFalse(result['found'])
        self.assertEqual(result['reason'], 'token_not_bound')
        self.assertCarriesNothingElse(result, RECOVERY_TOKEN)

    def test_the_result_shape_is_fixed_so_nothing_can_ride_along(self):
        """The host validates this shape too. A matcher that grew a field would be caught on both sides."""
        result = select([blob(record(MINE, OURS))], expect_sha256=digest(OURS))
        self.assertEqual(set(result), {'found', 'reason', 'route', 'records_for_this_run',
                                       'records_for_others', 'records_outside_synthetic'})

    def test_an_implausible_number_of_records_in_one_file_refuses(self):
        many = blob(*[record(OTHER, THEIRS) for _ in range(storage.MAX_RECORDS + 1)])
        with self.assertRaises(RuntimeError):
            select([many], expect_sha256=digest(OURS))


class TheHelperSourceActuallyCarriesTheMatcher(unittest.TestCase):
    """⚠️ A MATCHER THAT IS NOT IN THE SHIPPED SOURCE RUNS NOWHERE. The helper is assembled by
    `inspect.getsource`, so a function added to this module but left out of that tuple would pass every
    test above and do nothing in the container."""

    def test_the_selection_functions_are_in_the_shipped_helper(self):
        source = storage._helper_source()
        for name in ('_records', '_recipients', '_selected'):
            self.assertIn('def %s(' % name, source, name)
        self.assertIn(repr(storage.RECORD_SEPARATOR), source)
        self.assertIn(repr(storage.SYNTHETIC_DOMAIN), source)
        compile(source, 'helper', 'exec')

    def test_the_invocation_silences_its_own_logging_and_keeps_every_other_control(self):
        """⚠️ MEASURED, NOT ASSUMED: the daemon records an attached container's stdout under the default
        json-file driver, and for a 'read' that stdout IS the file. `--rm` deletes the log at exit; it does
        not prevent the recording."""
        import inspect
        source = inspect.getsource(storage._execute)
        self.assertIn("'--log-driver=none'", source)
        for control in ("'--rm'", "'--pull=never'", "'--network=none'", "'--read-only'",
                        "'--cap-drop=ALL'", "'--security-opt=no-new-privileges:true'"):
            self.assertIn(control, source, control)

    def test_the_criteria_never_become_command_line_arguments(self):
        """argv is world-readable in `ps`. The request travels on stdin and must keep doing so."""
        import inspect
        source = inspect.getsource(storage._execute)
        self.assertIn('input=request', source)
        self.assertNotIn('criteria)', source.split('args = [')[1].split(']')[0])


if __name__ == '__main__':
    unittest.main()
