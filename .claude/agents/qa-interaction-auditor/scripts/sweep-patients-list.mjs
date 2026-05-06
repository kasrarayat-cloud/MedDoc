#!/usr/bin/env node
// sweep-patients-list.mjs — /patients (practice patient list, searchable).
// v2 stub: smoke-load. Future: search-input live filtering + click into
// a patient detail row.

import { smokeWalkAuth } from './lib/walker-base.mjs';

await smokeWalkAuth({ name: 'patients-list', url: '/patients' });
