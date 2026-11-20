"""Decision (l) of the core repair (2026-11-03): the customer page's client contract.

The customer page names its own build on every customer API call it makes (static/studio/app.js, ``api()``: the header
CLIENT_HEADER with CLIENT_VERSION). A call that names no build, or another one - a browser tab opened on the previous
release and left open across an install - is answered HTTP 409 with OUTDATED, and the page asks the member to reload,
instead of reading answers it was not built for (studio.api.api_view). A download is a browser navigation, which sends
no header of the page's, so the downloads and the in-page view of the original are outside the contract; the platform
operator's console (/ops/) is too. The tools that call the customer API directly (ops/verify_login.py,
ops/scan_customer.py, ops/walk.cjs) send the same header; tests/test_cux_client_contract.py pins every copy of the value to
this one.

No Django import: tests/__init__.py reads it before any app is loaded.
"""
from __future__ import annotations

HEADER = 'X-CPT-Studio-Client'
# The Fable coding build (BUILD-SPEC 6): the encounter payload is the coding round's codes, questions, answers, notes and
# decisions, and the page draws them - a new build. customer-2026-11-21 (the fix pass, FIX-SPEC section 1): every code
# row carries its line, a question the lines it affects, modifiers may be null (not given), and a decision names the
# round and the line it was made on. customer-2026-11-22 (FIX-SPEC-2 section 5): a decision shown carries its id, an
# undo names the decision it undoes, and an export names the round the page shows.
VERSION = 'customer-2026-11-22'
WSGI_KEY = 'HTTP_' + HEADER.upper().replace('-', '_')
OUTDATED = {'error': 'CPT Studio was updated. Reload this page to continue.', 'error_code': 'client_outdated'}


def current(request) -> bool:
    """Whether ``request`` names this release's customer page build."""
    return request.headers.get(HEADER) == VERSION
