"""Decision (l) of the core repair (2026-11-03): the customer page's client contract.

The customer page names its own build on every customer API call it makes (static/studio/app.js, ``api()``: the header
CLIENT_HEADER with CLIENT_VERSION). A call that names no build, or another one - a browser tab opened on the previous
release and left open across an install - is answered HTTP 409 with OUTDATED, and the page asks the member to reload,
instead of reading answers it was not built for (studio.api.api_view). A download is a browser navigation, which sends
no header of the page's, so the two download views are outside the contract; the platform operator's API (/ops/) is
too. The tools that call the customer API directly (ops/verify_login.py, ops/scan_customer.py, ops/verify_browser.cjs)
send the same header; tests/test_cux_client_contract.py pins every copy of the value to this one.

No Django import: tests/__init__.py reads it before any app is loaded.
"""
from __future__ import annotations

HEADER = 'X-CPT-Studio-Client'
VERSION = 'customer-2026-11-03'
WSGI_KEY = 'HTTP_' + HEADER.upper().replace('-', '_')
OUTDATED = {'error': 'CPT Studio was updated. Reload this page to continue.', 'error_code': 'client_outdated'}


def current(request) -> bool:
    """Whether ``request`` names this release's customer page build."""
    return request.headers.get(HEADER) == VERSION
