"""Declared, production-target-pinned first account creation and later elevation.

Creation grants no staff access, verification, MFA, wallet or clinic. The owner
uses the normal verification-resend and doctor MFA flows. Elevation then requires
both proofs. No phase sends mail, resets credentials or overwrites an account.
"""
import json
import os
import subprocess
import uuid
from django.apps import apps
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import connection, transaction, DatabaseError
from django_otp.plugins.otp_totp.models import TOTPDevice
from core.forms import account_email
from core.models import User
from core.security import audit
from ops import deployment_profile
from ops.production_operator import authority, describe_target, private_json, require, OperatorError


def validated_context(action):
    profile = deployment_profile.load_production()
    declaration = authority(profile, 'first_admin')
    require(action in declaration.get('actions', []), 'declaration_action')
    require(os.environ.get('QUILLMD_DEPLOYMENT_PROFILE') == 'production'
            and not settings.SYNTHETIC_ONLY and settings.QUILLMD_REGISTRATION == 'invite'
            and settings.QUILLMD_MFA_REQUIRED_ALL and settings.QUILLMD_WELCOME_CREDIT == 0
            and settings.RELEASE_SHA == declaration['release_sha']
            and settings.STATE_DIR == profile.state_root, 'application_profile')
    from ops.service_launcher import verified_ca_bundle
    verified_ca_bundle(profile.ca_bundle, profile.ca_bundle_sha256)
    describe_target(profile, declaration)
    db = connection.settings_dict
    require(db['HOST'] == profile.database_host and str(db['PORT']) == str(profile.database_port)
            and db['NAME'] == profile.database_name and db['USER'] == profile.roles['runtime'], 'application_database')
    connection.ensure_connection()
    actual = connection.connection.info.get_parameters()
    require(actual.get('host') == profile.database_host and actual.get('sslmode') == 'verify-full'
            and actual.get('sslrootcert') == str(profile.ca_bundle), 'application_tls')
    with connection.cursor() as cursor:
        cursor.execute('''SELECT current_database(),current_user,current_setting('session_replication_role'),
            (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())''')
        require(cursor.fetchone() == (profile.database_name, profile.roles['runtime'], 'origin', True), 'application_connection')
    identity = declaration.get('first_admin', {})
    require(set(identity) == {'id', 'email'}, 'first_admin_identity')
    identifier = uuid.UUID(identity['id'])
    email = identity['email']
    validate_email(email)
    require(email == email.strip().lower() and not email.endswith('.invalid'), 'first_admin_email')
    return profile, declaration, identifier, email


def empty_clinical_state():
    # Explicit exceptions: public terminology and operational/authentication
    # records. Any new clinical/billing model is refused by default.
    allowed = {'User', 'Code', 'CodeSet', 'AuditEvent', 'LoginAttempt', 'ServiceHealth', 'Verification'}
    require(all(not model.objects.exists() for model in apps.get_app_config('core').get_models()
                if model.__name__ not in allowed), 'bootstrap_database_not_empty')


def bootstrap(action, profile, declaration, identifier, email):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(748413910342)')
        if action == 'inspect':
            user = User.objects.filter(pk=identifier, email=email).first()
            return {'exists': user is not None, 'sole_user': User.objects.count() == 1,
                    'verified': bool(user and user.verified_at), 'staff': bool(user and user.is_staff),
                    'confirmed_mfa': bool(user and TOTPDevice.objects.filter(user=user, confirmed=True).exists())}
        empty_clinical_state()
        if action == 'create':
            # The one rule every account-creating door applies to an address (core.forms.account_email, RA-LOW-1).
            try:
                canonical = account_email(email)
            except ValidationError:
                canonical = None
            require(canonical == email, 'first_admin_email')
            require(not User.objects.exists(), 'bootstrap_user_exists')
            secret = private_json(profile.operator_directory / 'first-admin-password.json')
            require(set(secret) == {'password'} and isinstance(secret['password'], str), 'password_file')
            user = User(id=identifier, username=email, email=email, is_staff=False, is_superuser=False,
                        is_active=True, verified_at=None)
            validate_password(secret['password'], user)
            user.set_password(secret['password'])
            user.save(force_insert=True)
            audit(user, 'account.bootstrap_created', user.pk, release_sha=declaration['release_sha'],
                  profile_sha256=profile.sha256, declaration_commit=os.environ['RULED_MUTATION_DECL_COMMIT'])
            return {'created': True, 'staff': False, 'verified': False, 'credit_granted': False, 'email_sent': False}
        require(action == 'elevate', 'bootstrap_action')
        require(User.objects.count() == 1, 'bootstrap_user_count')
        user = User.objects.select_for_update().filter(pk=identifier, email=email, username=email).first()
        require(user is not None and user.is_active and not user.is_staff and not user.is_superuser
                and user.verified_at and user.has_usable_password(), 'bootstrap_user_state')
        require(TOTPDevice.objects.select_for_update().filter(user=user, confirmed=True).exists(), 'bootstrap_mfa_required')
        # Only the account originally created by this command can be elevated.
        from core.models import AuditEvent
        require(AuditEvent.objects.filter(actor=user, action='account.bootstrap_created', target=str(user.pk)).exists(),
                'bootstrap_creation_evidence')
        user.is_staff = True
        user.session_version += 1  # Existing nonstaff sessions cannot become administrator sessions.
        user.save(update_fields=['is_staff', 'session_version'])
        audit(user, 'account.bootstrap_elevated', user.pk, release_sha=declaration['release_sha'],
              profile_sha256=profile.sha256, declaration_commit=os.environ['RULED_MUTATION_DECL_COMMIT'])
        return {'elevated': True, 'superuser': False, 'credit_granted': False, 'email_sent': False,
                'sessions_invalidated': True}


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['inspect', 'create', 'elevate'])

    def handle(self, *args, **options):
        try:
            context = validated_context(options['action'])
            result = bootstrap(options['action'], *context)
        except (OperatorError, deployment_profile.ProfileError, ValueError, KeyError, OSError, ValidationError,
                DatabaseError, subprocess.SubprocessError) as exc:
            # Do not emit values from settings, provider errors, passwords or identities.
            label = str(exc) if isinstance(exc, (OperatorError, deployment_profile.ProfileError)) else type(exc).__name__
            raise CommandError('First administrator refused: ' + label) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
