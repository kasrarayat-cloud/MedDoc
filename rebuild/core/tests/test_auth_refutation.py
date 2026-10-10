"""Independent recovery/invitation probes; synthetic users and no outbound email."""
from datetime import timedelta
from django.contrib.auth.tokens import default_token_generator
from django.test import Client,TestCase,override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.models import User,Organization,Department,Membership,Invitation,LedgerEntry
from core.security import token,digest

@override_settings(ADMIN_SITE=False,STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AuthRefutation(TestCase):
    password='Synthetic-password-proof-78261!'
    def setUp(self):
        self.user=User.objects.create_user(username='independent-reset',email='independent@synthetic.invalid',password=self.password,verified_at=timezone.now())
    def link(self,user):
        return f'/recovery/confirm/{urlsafe_base64_encode(force_bytes(user.pk))}/{default_token_generator.make_token(user)}/'
    def replacement(self):return {'new_password1':'Replacement-synthetic-38170!','new_password2':'Replacement-synthetic-38170!'}
    def test_recovery_session_token_cannot_reset_another_uid(self):
        other=User.objects.create_user(username='other-reset',email='other@synthetic.invalid',password=self.password,verified_at=timezone.now())
        self.client.get(self.link(self.user))
        wrong=f'/recovery/confirm/{urlsafe_base64_encode(force_bytes(other.pk))}/set-password/'
        self.assertContains(self.client.post(wrong,self.replacement()),'Recovery link unavailable')
        other.refresh_from_db();self.assertTrue(other.check_password(self.password))
    def test_account_disabled_after_link_open_cannot_reset(self):
        target=self.client.get(self.link(self.user)).context['continue_url']
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertContains(self.client.post(target,self.replacement()),'Recovery link unavailable')
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(self.password))
    def test_account_promoted_after_link_open_still_requires_mfa(self):
        target=self.client.get(self.link(self.user)).context['continue_url']
        User.objects.filter(pk=self.user.pk).update(is_staff=True)
        self.assertContains(self.client.post(target,self.replacement()),'This field is required')
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(self.password))
    def test_existing_unverified_invitee_has_safe_verification_route_without_password_reset(self):
        organization=Organization.objects.create(name='Synthetic invitation refutation')
        department=Department.objects.create(organization=organization,name='X-ray')
        Membership.objects.create(user=self.user,department=department,role='owner')
        invited=User.objects.create_user(username='already-registered',email='already-registered@synthetic.invalid',password=self.password)
        raw=token();Invitation.objects.create(email=invited.email,department=department,role='employee',invited_by=self.user,token_hash=digest(raw),expires_at=timezone.now()+timedelta(days=1))
        response=self.client.post(f'/invite/{raw}/',{'email':invited.email,'password1':self.password,'password2':self.password,'synthetic_only':'on'})
        self.assertContains(response,'/verification/resend/')
        self.assertContains(response,'/login/')
        invited.refresh_from_db();self.assertIsNone(invited.verified_at)
        self.assertTrue(invited.check_password(self.password))
        self.assertFalse(Membership.objects.filter(user=invited,department=department).exists())
        self.assertFalse(LedgerEntry.objects.filter(wallet__user=invited,kind='welcome').exists())
