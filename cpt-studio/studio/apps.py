from django.apps import AppConfig
from django.core import checks


class StudioConfig(AppConfig):
    """CPT Studio. Nothing is installed at start but one system check: the earlier pipeline's legacy-call sentinel went
    with the code it watched (BUILD-SPEC 0: the coding path is Fable's reads, studio.jobs and studio.fable). Release 1
    (F1): with stored-file encryption on, studio.file_crypto.check_files_key refuses `manage.py check` and the worker's
    start without a usable key-encryption key."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'studio'
    verbose_name = 'CPT Studio'

    def ready(self):
        from . import file_crypto
        checks.register(file_crypto.check_files_key, checks.Tags.security)
