"""That the binding refuses everything it should, without Django and without a token in any output.

The application models are stubbed rather than imported: `unittest discover -s ops` runs with no
DJANGO_SETTINGS_MODULE, and these assertions are about the BINDING's logic, not about Django's.
"""
import hashlib
import sys
import types
import unittest

try:
    from . import account_mail
except ImportError:
    import account_mail

OURS = 'TOKEN-BELONGING-TO-THIS-RUN'
THEIRS = 'TOKEN-BELONGING-TO-ANOTHER'


def sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, **kwargs):
        return Rows([r for r in self.rows
                     if all(getattr(r, k.replace('__isnull', '')) is None if k.endswith('__isnull')
                            else getattr(r, k) == v for k, v in kwargs.items())])

    def get(self, **kwargs):
        found = self.filter(**kwargs).rows
        if len(found) != 1:
            raise LookupError('no unique row')
        return found[0]

    def __iter__(self):
        return iter(self.rows)


class Invitation:
    def __init__(self, email, token_hash, accepted_at=None):
        self.email, self.token_hash, self.accepted_at = email, token_hash, accepted_at


def install(invitations=(), users=()):
    """Stand in for core.models / core.security for the duration of one test."""
    models = types.ModuleType('core.models')
    models.Invitation = types.SimpleNamespace(objects=Rows(list(invitations)))
    models.User = types.SimpleNamespace(objects=Rows(list(users)))
    security = types.ModuleType('core.security')
    security.digest = sha256
    core = types.ModuleType('core')
    saved = {name: sys.modules.get(name) for name in ('core', 'core.models', 'core.security')}
    sys.modules.update({'core': core, 'core.models': models, 'core.security': security})
    return saved


class InvitationBinding(unittest.TestCase):
    def use(self, *invitations):
        saved = install(invitations=invitations)
        self.addCleanup(lambda: [sys.modules.__setitem__(k, v) if v else sys.modules.pop(k, None)
                                 for k, v in saved.items()])

    def test_the_expectation_handed_to_the_helper_identifies_our_record_exactly(self):
        """⚠️ THE BINDING IS NOW A VALUE, NOT A CALLABLE, BECAUSE IT HAS TO CROSS INTO THE CONTAINER.

        The helper compares sha256(token) against this. That is an exact identity check on the record, and
        the value handed over is a DIGEST — so the operator process never holds a credential in order to
        recognise one, and the comparison happens on the service side of the boundary.
        """
        self.use(Invitation('run@synthetic.quillmd.invalid', sha256(OURS)))
        expectations, final = account_mail.binding('invite', 'run@synthetic.quillmd.invalid')
        self.assertEqual(expectations, {'expect_sha256': sha256(OURS)})
        self.assertIsNone(final, 'an invitation needs no host-side check; it is fully bound in the helper')
        # The expectation is the digest of OUR token and of nothing else.
        self.assertNotEqual(expectations['expect_sha256'], sha256(THEIRS))

    def test_the_address_is_matched_case_insensitively_like_the_application_stores_it(self):
        self.use(Invitation('run@synthetic.quillmd.invalid', sha256(OURS)))
        expectations, _ = account_mail.binding('invite', 'RUN@Synthetic.QuillMD.invalid')
        self.assertEqual(expectations, {'expect_sha256': sha256(OURS)})

    def test_an_accepted_invitation_is_not_a_record_this_run_is_expecting(self):
        """A consumed row is stale by definition; binding to it would accept a spent link."""
        self.use(Invitation('run@synthetic.quillmd.invalid', sha256(OURS), accepted_at='2026-09-19'))
        with self.assertRaises(account_mail.NoBinding):
            account_mail.binding('invite', 'run@synthetic.quillmd.invalid')

    def test_two_open_invitations_refuse_rather_than_picking_one(self):
        """Guessing here would put first-match behaviour back one layer above where it was removed."""
        self.use(Invitation('run@synthetic.quillmd.invalid', sha256(OURS)),
                 Invitation('run@synthetic.quillmd.invalid', sha256(THEIRS)))
        with self.assertRaises(account_mail.NoBinding) as refusal:
            account_mail.binding('invite', 'run@synthetic.quillmd.invalid')
        self.assertIn('found 2', str(refusal.exception))

    def test_no_invitation_at_all_refuses(self):
        self.use()
        with self.assertRaises(account_mail.NoBinding):
            account_mail.binding('invite', 'run@synthetic.quillmd.invalid')

    def test_an_unknown_purpose_is_refused_before_any_lookup(self):
        with self.assertRaises(account_mail.NoBinding):
            account_mail.binding('verify', 'run@synthetic.quillmd.invalid')

    def test_no_refusal_message_can_carry_a_token(self):
        self.use(Invitation('run@synthetic.quillmd.invalid', sha256(OURS), accepted_at='2026-09-19'))
        for purpose in ('invite', 'verify'):
            try:
                account_mail.binding(purpose, 'run@synthetic.quillmd.invalid')
            except account_mail.NoBinding as refusal:
                self.assertNotIn('TOKEN', str(refusal))


class LocateWiresTheBindingIn(unittest.TestCase):
    def test_locate_passes_the_predicate_to_the_reader(self):
        """Without this, `locate` would be `route` with extra steps and no binding at all."""
        seen = {}

        def fake_route(purpose, address, before, notes=None, verify=None, **expectations):
            seen.update({'purpose': purpose, 'address': address, 'verify': verify, **expectations})
            return '/%s/x/' % purpose
        saved_route, account_mail.private_mail.route = account_mail.private_mail.route, fake_route
        saved = install(invitations=[Invitation('run@synthetic.quillmd.invalid', sha256(OURS))])
        self.addCleanup(lambda: setattr(account_mail.private_mail, 'route', saved_route))
        self.addCleanup(lambda: [sys.modules.__setitem__(k, v) if v else sys.modules.pop(k, None)
                                 for k, v in saved.items()])
        account_mail.locate('invite', 'run@synthetic.quillmd.invalid', before={})
        self.assertEqual(seen.get('expect_sha256'), sha256(OURS),
                         'locate passed no expectation, so the helper would bind nothing')
        self.assertIsNone(seen['verify'])


if __name__ == '__main__':
    unittest.main()
