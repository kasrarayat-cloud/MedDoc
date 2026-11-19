from django.apps import AppConfig


class StudioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'studio'
    verbose_name = 'CPT Studio'

    def ready(self):
        """Install the legacy-call sentinel in this process (Gemini migration; design/FINAL.md 10.2-10.3 and
        ADJUDICATION.md R-1): every process the app runs in - each web worker, the worker and every one-shot - counts
        the executions of the legacy reader's code from its start. sentinel.install imports its pinned deny modules
        itself (nothing here imports them) and never raises: a process whose install failed records why, logs it and
        refuses every new-path write, and the D22 report shows it."""
        from studio.interpretation import sentinel

        sentinel.install()
