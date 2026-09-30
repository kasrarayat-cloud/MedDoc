"""Report whether each private setting is configured, without reading or printing it.

`.env` is not a file any session reads, and reading it indirectly through a
script is the same act with an extra step. This command is the approved
alternative: it answers the only question an operator legitimately has — *is it
configured, and does it have the right shape* — from the settings the running
application already holds, and it is constructed so that no branch can emit a
secret. Values are never returned, never logged and never compared to a literal
that would reveal them.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.billing import stripe_key_configured


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
            # ⚠️ THE TWO PROVIDER KEYS WERE MISSING FROM THIS SCREEN, and they are the ones that decide whether a
            # recording can be transcribed or a document generated at all. Without the first, every transcription
            # stops with 'Transcription provider is not connected' — correct, and impossible to diagnose from the
            # operator's side, which is the only side that can fix it. Status only: `shape()` never reads a value back.
            ('DEEPGRAM_API_KEY', os.getenv('DEEPGRAM_API_KEY'), None),
            ('ANTHROPIC_API_KEY', os.getenv('ANTHROPIC_API_KEY'), None),
            ('RESEND_API_KEY', settings.RESEND_API_KEY, None),
            ('STRIPE_SECRET_KEY', settings.STRIPE_SECRET_KEY, stripe_key_configured),
            ('STRIPE_WEBHOOK_SECRET', settings.STRIPE_WEBHOOK_SECRET, None),
        ]
        self.stdout.write('Configuration (no value is read back):')
        for name, value, _ in rows:
            # Mode and identifier settings are not secrets; their value is the answer.
            self.stdout.write(f'  {name}: {value if isinstance(value, str) and value.strip() else "(unset)"}')
        self.stdout.write('Private credentials (status only):')
        for name, value, recogniser in secrets:
            self.stdout.write(f'  {name}: {shape(value, recogniser)}')
        self.language_model()
        # ⚠️ THESE TWO SENTENCES SAID THE OPPOSITE OF WHAT THE CODE DOES, in the same change that removed the
        # fallback they described. They promised a degraded-but-working submission path; there is no such path now.
        # During an incident where every recording is failing, this is the one screen built to localise it — and it
        # was telling the operator the submission path still worked, which is exactly the sentence that stops someone
        # looking at ffmpeg. Without either tool NOTHING is submitted: every recording is refused, nothing is charged,
        # and the reason is on each job.
        import shutil
        probe, remuxer = shutil.which('ffprobe'), shutil.which('ffmpeg')
        self.stdout.write('Media tools:')
        self.stdout.write('  ffprobe: %s' % (probe if probe else
                          'NOT INSTALLED — EVERY recording is refused before the provider; nothing is charged'))
        self.stdout.write('  ffmpeg: %s' % (remuxer if remuxer else
                          'NOT INSTALLED — EVERY recording is refused before the provider; nothing is charged'))
        self.stdout.write('Release gates:')
        self.stdout.write(f'  SYNTHETIC_ONLY: {settings.SYNTHETIC_ONLY}')
        self.stdout.write(f'  STRIPE_LIVE_ENABLED: {settings.STRIPE_LIVE_ENABLED}')
        self.stdout.write(f'  QUILLMD_DATA_MODE: {settings.QUILLMD_DATA_MODE}')
        self.stdout.write(f'  QUILLMD_REGISTRATION: {settings.QUILLMD_REGISTRATION}')
        self.stdout.write(f'  QUILLMD_STRIPE_MODE: {settings.QUILLMD_STRIPE_MODE}')
        self.stdout.write(f'  QUILLMD_MFA_REQUIRED_ALL: {settings.QUILLMD_MFA_REQUIRED_ALL}')
        self.stdout.write(f'  database: {settings.DATABASES["default"]["NAME"]}')
        self.worker()

    def worker(self):
        """Whether a worker holds the single-worker lock, and the role's session timeouts, which must be 0 (blockers.txt
        item 3). The rows come from core.worker_lock.worker_status(), whose rows the services page renders too, and the
        exit from the same single read. A non-zero timeout makes this command exit non-zero after printing everything,
        exactly as the worker refuses to start. A database that cannot be read prints UNKNOWN rows and exits 0, as the
        rest of this report degrades: it is the screen an operator reads during an incident."""
        from core.worker_lock import worker_status
        self.stdout.write('Worker (one per database; it refuses to start unless every timeout below is 0):')
        rows, refused = worker_status()
        for row in rows:
            self.stdout.write(f'  {row["name"]}: {row["value"]}')
        if refused is not None:
            raise CommandError(str(refused))

    def language_model(self):
        """The model, its rates, the request profile and the pricing version a generation queued NOW would carry.

        None of these is a secret — they are the answer to "which model, at which price" — and without them an operator
        switching the model could not confirm the switch from the one screen built for it. Every value is computed by
        `core.generation.configuration()`, the function enqueue snapshots, so this screen cannot describe a different
        request from the one a job would make. The rows come from `core.admin_console.language_model_rows()`, which the
        services page renders too: one implementation, so the terminal and the browser cannot disagree.
        """
        from core.admin_console import language_model_rows
        self.stdout.write('Language model (plain configuration values, shown so a model switch can be confirmed):')
        for row in language_model_rows():
            self.stdout.write(f'  {row["name"]}: {row["value"]}')
