#!/usr/bin/env node
// sweep-marketing-home.mjs — quillmd.com/ landing page.
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-home', url: '/' });
