#!/usr/bin/env node
// sweep-marketing-pricing.mjs — quillmd.com/pricing.
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-pricing', url: '/pricing' });
