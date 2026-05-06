#!/usr/bin/env node
// sweep-visits-list.mjs — /visits (filter pills: all/ready/review/signed/processing).
// v2 stub: smoke-load. Future: click each filter pill, snapshot URL +
// rendered count to confirm filtering actually filters.

import { smokeWalkAuth } from './lib/walker-base.mjs';

await smokeWalkAuth({ name: 'visits-list', url: '/visits' });
