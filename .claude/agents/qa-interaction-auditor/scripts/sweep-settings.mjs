#!/usr/bin/env node
// sweep-settings.mjs — /settings (profile / security / sessions / data / billing / danger zone).
// v2 stub: smoke-load. Future: walk each section nav anchor, verify each
// form's save action persists correctly + writes the audit row.
// Danger-zone routes are READ-ONLY here — the agent NEVER clicks
// "Delete account" or "Revoke all sessions" on the test user.

import { smokeWalkAuth } from './lib/walker-base.mjs';

await smokeWalkAuth({ name: 'settings', url: '/settings' });
