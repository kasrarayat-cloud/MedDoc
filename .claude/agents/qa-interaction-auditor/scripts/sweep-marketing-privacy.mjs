#!/usr/bin/env node
// sweep-marketing-privacy.mjs — quillmd.com/privacy.
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-privacy', url: '/privacy' });
