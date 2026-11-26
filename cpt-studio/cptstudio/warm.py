"""Release 2 (R2-5, web WEB-2): what the web's first requests would load, loaded once, before any request.

gunicorn's master imports cptstudio.wsgi once, before it forks a worker (deploy/gunicorn.conf.py, preload_app), and that
module calls warm_up() after the application is built. So every worker - the first four and each one that replaces a
recycled worker - starts from a fork of a master that already holds both hosts' URLconfs, with every view module they
import and their patterns compiled; every page template, compiled; the static files' manifest; the password hasher's
library; and the password rules. No request waits for any of it, and the workers share its memory.

Specification 2.4: it reads no database, starts no thread and needs no network (the image phase imports cptstudio.wsgi
with no network). What is open in the master when a worker is forked is shared with that worker, and the master never
serves a request, so it never holds a document's data. A part that cannot be loaded raises: a broken release stops at
the image phase's smoke check or at the switch's first step (S1), never at a member's request.
"""
from pathlib import Path

from django.conf import settings


def warm_up():
    import argon2  # noqa: F401 - the hasher's library, which Django otherwise loads at the first sign-in
    from django.contrib.auth.hashers import get_hashers
    from django.contrib.auth.password_validation import get_default_password_validators
    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.template.loader import get_template
    from django.urls import get_resolver

    from studio import hosts

    for urlconf in (settings.ROOT_URLCONF, hosts.ADMIN_URLCONF):
        # imports the URLconf and every view module it names, and compiles its patterns
        get_resolver(urlconf).reverse_dict
    templates = Path(settings.BASE_DIR) / 'studio' / 'templates'
    for path in sorted(templates.rglob('*.html')):
        get_template(path.relative_to(templates).as_posix())  # into the cached loader every request reads
    getattr(staticfiles_storage, 'hashed_files', None)  # the manifest, where the storage has one
    get_hashers()
    get_default_password_validators()
