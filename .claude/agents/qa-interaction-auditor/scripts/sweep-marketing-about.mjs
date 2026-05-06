#!/usr/bin/env node
// sweep-marketing-about.mjs — quillmd.com/about.
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-about', url: '/about' });
