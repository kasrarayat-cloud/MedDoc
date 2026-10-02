"""Scratch-only independent reproduction of RR2-ACC-1 (an address longer than username's 150 chars)."""
import json
import re

from django.test import Client, override_settings
from django.utils import timezone

from core.forms import ClinicInvitationForm, InvitationForm, RegisterForm
from core.models import ClinicInvitation, Department, Invitation, Membership, Organization, User
from core.tests.test_v1_invite_only import PASSWORD, InviteFixture


def address(length):
    """A syntactically valid address of exactly `length` characters (local part 64, labels <= 63)."""
    tail = length - (64 + 1 + 63 + 1 + len('.invalid'))
    assert 1 <= tail <= 63
    value = 'a' * 64 + '@' + 'b' * 63 + '.' + 'c' * tail + '.invalid'
    assert len(value) == length
    return value


LONG = 'a' * 64 + '@' + 'b' * 63 + '.' + 'c' * 20 + '.invalid'
assert len(LONG) == 157 and LONG == address(157)


def form(email):
    return {'email': email, 'first_name': 'Synthetic', 'last_name': 'Person', 'password1': PASSWORD,
            'password2': PASSWORD, 'synthetic_only': 'on'}


def outcome(response):
    exc = getattr(response, 'exc_info', None)
    return response.status_code, (type(exc[1]).__module__ + '.' + type(exc[1]).__name__ + ': ' + str(exc[1]).strip().splitlines()[0]) if exc else None


def report(tag, **values):
    print(f'\n[RR2-ACC-1 {tag}] ' + json.dumps({k: str(v) for k, v in values.items()}, sort_keys=True), flush=True)


class LongAddress(InviteFixture):

    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username='dept-owner', email='dept-owner@synthetic.invalid', verified_at=timezone.now())
        self.department = Department.objects.create(organization=Organization.objects.create(name='Existing clinic'), name='Front desk')
        Membership.objects.create(user=self.owner, department=self.department, role='owner')

    def test_forms_accept_the_address(self):
        register = RegisterForm(form(LONG))
        invitation = InvitationForm({'department': self.department.pk, 'email': LONG, 'role': 'employee'}, user=self.owner)
        clinic = ClinicInvitationForm({'email': LONG, 'organization_name': 'Synthetic long clinic', 'department_name': 'Main'})
        report('forms', register=register.is_valid(), register_errors=register.errors.as_json(),
               invitation=invitation.is_valid(), clinic=clinic.is_valid(), length=len(LONG))
        self.assertTrue(register.is_valid(), register.errors)
        self.assertTrue(invitation.is_valid(), invitation.errors)
        self.assertTrue(clinic.is_valid(), clinic.errors)

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_a_register(self):
        results = {}
        for length in (150, 151, 157):
            email = address(length)
            response = Client(raise_request_exception=False).post('/register/', form(email))
            results[length] = (outcome(response), User.objects.filter(email__iexact=email).count())
        report('register', **{str(k): v for k, v in results.items()})
        self.assertEqual(results[150][0][0], 302)  # control: the boundary address registers
        self.assertEqual(results[150][1], 1)
        for length in (151, 157):
            self.assertEqual(results[length][0][0], 500)
            self.assertIn('DataError', results[length][0][1])
            self.assertEqual(results[length][1], 0)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_b_department_invitation(self):
        owner = Client(); owner.force_login(self.owner)
        issued = owner.post('/team/', {'department': self.department.pk, 'email': LONG, 'role': 'employee'})
        invitation = Invitation.objects.get(email=LONG)
        link = re.findall(r'http://localhost:9130(/invite/[^\s/]+/)', self.mail())[-1]
        attempts = []
        for _ in range(3):
            response = Client(raise_request_exception=False).post(link, form(LONG))
            attempts.append(outcome(response))
        invitation.refresh_from_db()
        get_status = Client().get(link).status_code
        report('department', issue_status=issued.status_code, attempts=attempts, accounts=User.objects.filter(email__iexact=LONG).count(),
               accepted_at=invitation.accepted_at, get_after=get_status)
        self.assertEqual(issued.status_code, 302)
        self.assertEqual([a[0] for a in attempts], [500, 500, 500])
        self.assertTrue(all('DataError' in a[1] for a in attempts))
        self.assertEqual(User.objects.filter(email__iexact=LONG).count(), 0)
        self.assertIsNone(invitation.accepted_at)
        self.assertEqual(get_status, 200)
        # Control: the same door with an ordinary address accepts.
        owner.post('/team/', {'department': self.department.pk, 'email': 'nurse@synthetic.invalid', 'role': 'employee'})
        nurse = Invitation.objects.get(email='nurse@synthetic.invalid')
        from core.security import digest
        link = next(l for l in re.findall(r'http://localhost:9130(/invite/[^\s/]+/)', self.mail()) if digest(l.split('/')[-2]) == nurse.token_hash)
        control = Client().post(link, form('nurse@synthetic.invalid'))
        report('department-control', status=control.status_code, accounts=User.objects.filter(email='nurse@synthetic.invalid').count())
        self.assertEqual(control.status_code, 302)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_c_clinic_invitation(self):
        issued = self.invite(email=LONG, organization='Synthetic long clinic', department='Main')
        invitation = ClinicInvitation.objects.get(email=LONG)
        link = self.link()
        response = Client(raise_request_exception=False).post(link, form(LONG))
        invitation.refresh_from_db()
        get_status = Client().get(link).status_code
        report('clinic', issue_status=issued.status_code, attempt=outcome(response),
               accounts=User.objects.filter(email__iexact=LONG).count(), accepted_at=invitation.accepted_at,
               organizations=Organization.objects.filter(name='Synthetic long clinic').count(), get_after=get_status)
        self.assertEqual(issued.status_code, 302)
        self.assertEqual(response.status_code, 500)
        self.assertIn('DataError', outcome(response)[1])
        self.assertEqual(User.objects.filter(email__iexact=LONG).count(), 0)
        self.assertIsNone(invitation.accepted_at)
