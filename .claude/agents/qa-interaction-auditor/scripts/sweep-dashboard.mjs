#!/usr/bin/env node
// sweep-dashboard.mjs — /dashboard (Patients + All Visits tabs).
// v2 stub: smoke-loads the page; future iterations exercise tab clicks
// + the search palette + new-visit CTA per quillmd-workflows.md.

import { smokeWalkAuth } from './lib/walker-base.mjs';

await smokeWalkAuth({ name: 'dashboard', url: '/dashboard' });
