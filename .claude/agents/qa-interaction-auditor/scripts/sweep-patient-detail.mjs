#!/usr/bin/env node
// sweep-patient-detail.mjs — /patients/[id] (Visits / Notes / Files / Trash tabs).
// v2 stub: smoke-load using the seeded test patient. Future: walk each
// tab, verify the Notes + Files stub state copy, exercise Trash restore
// when items exist.

import { readSeededIds, smokeWalkAuth, emit } from './lib/walker-base.mjs';

const seeded = readSeededIds();
if (!seeded?.patientId) {
  emit({
    event: 'walker-skip',
    name: 'patient-detail',
    reason: 'seeded patient id missing',
  });
  process.exit(0);
}

await smokeWalkAuth({
  name: 'patient-detail',
  url: `/patients/${seeded.patientId}`,
});
