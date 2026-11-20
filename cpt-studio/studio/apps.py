from django.apps import AppConfig


class StudioConfig(AppConfig):
    """CPT Studio. Nothing is installed at start: the earlier pipeline's legacy-call sentinel went with the code it
    watched (BUILD-SPEC 0: the coding path is Fable's reads, studio.jobs and studio.fable)."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'studio'
    verbose_name = 'CPT Studio'
