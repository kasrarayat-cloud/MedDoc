"""The CPT Studio test package.

Decision (l) (2026-11-03; studio.client_contract): every request a test makes through Django's test client or request
factory acts as the current customer page build - which names itself on every customer API call it makes
(static/studio/app.js, api()) - unless the test says otherwise. tests/test_cux_client_contract.py removes or changes the
header to prove what a call without it is answered.
"""
from django.test import client as _client

from studio import client_contract as _contract

_factory_init = _client.RequestFactory.__init__


def _as_the_current_page(self, *args, **defaults):
    defaults.setdefault(_contract.WSGI_KEY, _contract.VERSION)
    _factory_init(self, *args, **defaults)


_client.RequestFactory.__init__ = _as_the_current_page
