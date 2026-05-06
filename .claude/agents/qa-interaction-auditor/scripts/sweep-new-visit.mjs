#!/usr/bin/env node
// sweep-new-visit.mjs — /visits/new (patient picker + capture-mode wizard).
// v2 stub: smoke-load with the seeded patient pre-selected via ?patientId.
// Future: walk patient picker → mode tile → capture submit; verify each
// tile's POST shape (audio_upload / voice_dictation / text_notes).

import { smokeWalkAuth } from './lib/walker-base.mjs';
import { readSeededIds } from './lib/walker-base.mjs';

const seeded = readSeededIds();
const url = seeded?.patientId
  ? `/visits/new?patientId=${seeded.patientId}`
  : '/visits/new';

await smokeWalkAuth({ name: 'new-visit', url });
