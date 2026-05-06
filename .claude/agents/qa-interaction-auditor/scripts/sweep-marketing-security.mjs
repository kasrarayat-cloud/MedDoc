#!/usr/bin/env node
// sweep-marketing-security.mjs — quillmd.com/security.
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-security', url: '/security' });
