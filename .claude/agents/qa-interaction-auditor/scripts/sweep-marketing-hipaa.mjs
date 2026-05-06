#!/usr/bin/env node
// sweep-marketing-hipaa.mjs — quillmd.com/hipaa (DRAFT — pending legal).
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-hipaa', url: '/hipaa' });
