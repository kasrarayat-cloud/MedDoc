#!/usr/bin/env node
// sweep-visit-record.mjs — /visits/[id]/record (live MediaRecorder).
// v2 stub: smoke-load. Future: simulate getUserMedia + record + stop;
// verify chunked /dictation/upload POSTs land + transcript pipeline kicks.
// Recorder hardware is mocked via Playwright's `granted` permission +
// fake media-stream tracks; never touch real microphones.

import { readSeededIds, smokeWalkAuth, emit } from './lib/walker-base.mjs';

const seeded = readSeededIds();
if (!seeded) {
  emit({
    event: 'walker-skip',
    name: 'visit-record',
    reason: 'seeded-ids.json missing — run scripts/seed-qa-user.ts',
  });
  process.exit(0);
}

// We need a visit id to walk the record route. The agent doesn't keep
// a long-lived QA visit on hand (per the cleanup rule in
// fixtures/test-user.md), so the v2 stub skips when none exists. Future
// iterations will create + tear down a draft-mode visit just for this
// walker.
emit({
  event: 'walker-skip',
  name: 'visit-record',
  reason:
    'route requires a draft visit owned by the test user; v2 stub does not auto-create one',
});
