"""Report whether each private setting is configured, without reading or printing it.

`.env` is not a file any session reads, and reading it indirectly through a
script is the same act with an extra step. This command is the approved
alternative: it answers the only question an operator legitimately has — *is it
configured, and does it have the right shape* — from the settings the running
application already holds, and it is constructed so that no branch can emit a
secret. Values are never returned, never logged and never compared to a literal
that would reveal them.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.billing import stripe_test_key_configured


def shape(value, recogniser=None):
    """'absent', 'present' or a recogniser's verdict. Never the value, never its length."""
    if not isinstance(value, str) or not value.strip():
        return 'absent'
    if recogniser is None:
        return 'present'
    return 'present, recognised shape' if recogniser(value) else 'present, UNRECOGNISED shape'


class Command(BaseCommand):
    help = 'Report configuration status without disclosing any secret value.'

    def handle(self, *args, **options):
        rows = [
            ('QUILLMD_AI_MODE', settings.AI_MODE, None),
            ('QUILLMD_AI_PROVIDER', settings.AI_PROVIDER, None),
            ('QUILLMD_EMAIL_MODE', settings.QUILLMD_EMAIL_MODE, None),
            ('QUILLMD_EMAIL_FROM', settings.QUILLMD_EMAIL_FROM, None),
            ('QUILLMD_EMAIL_VERIFIED_DOMAIN', settings.QUILLMD_EMAIL_VERIFIED_DOMAIN, None),
            ('CPT_LICENSE_ID', settings.CPT_LICENSE_ID, None),
            ('CPT_LICENSE_EXPIRY', settings.CPT_LICENSE_EXPIRY, None),
        ]
        secrets = [
            ('RESEND_API_KEY', settings.RESEND_API_KEY, None),
            ('STRIPE_SECRET_KEY', settings.STRIPE_SECRET_KEY, stripe_test_key_configured),
            ('STRIPE_WEBHOOK_SECRET', settings.STRIPE_WEBHOOK_SECRET, None),
        ]
        self.stdout.write('Configuration (no value is read back):')
        for name, value, _ in rows:
            # Mode and identifier settings are not secrets; their value is the answer.
            self.stdout.write(f'  {name}: {value if isinstance(value, str) and value.strip() else "(unset)"}')
        self.stdout.write('Private credentials (status only):')
        for name, value, recogniser in secrets:
            self.stdout.write(f'  {name}: {shape(value, recogniser)}')
        # ffprobe measures the payload submitted to the transcription provider and ffmpeg produces it. Without either,
        # the application degrades honestly — coverage reports UNKNOWN, and the upload is submitted unchanged as it was
        # before normalisation existed — but a DEGRADED path that works is the hardest kind of absence to notice, so it
        # belongs on an operator's screen rather than being discovered in a doctor's note.
        import shutil
        probe, remuxer = shutil.which('ffprobe'), shutil.which('ffmpeg')
        self.stdout.write('Media tools:')
        self.stdout.write('  ffprobe: %s' % (probe if probe else
                          'NOT INSTALLED — transcription coverage will report UNKNOWN for every recording'))
        self.stdout.write('  ffmpeg: %s' % (remuxer if remuxer else
                          'NOT INSTALLED — every recording is submitted exactly as uploaded, unnormalised'))
        self.stdout.write('Release gates:')
        self.stdout.write(f'  SYNTHETIC_ONLY: {settings.SYNTHETIC_ONLY}')
        self.stdout.write(f'  STRIPE_LIVE_ENABLED: {settings.STRIPE_LIVE_ENABLED}')
        self.stdout.write(f'  database: {settings.DATABASES["default"]["NAME"]}')
