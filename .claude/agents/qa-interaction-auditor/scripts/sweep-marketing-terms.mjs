#!/usr/bin/env node
// sweep-marketing-terms.mjs — quillmd.com/terms.
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-terms', url: '/terms' });
