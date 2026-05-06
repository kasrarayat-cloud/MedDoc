#!/usr/bin/env node
// sweep-marketing-contact.mjs — quillmd.com/contact (form: support/sales/compliance/security).
// v2 stub: smoke-load. Future: walk the routing dropdown + verify each
// destination's POST shape. NEVER submits a real contact form (would
// page sales/support).
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-contact', url: '/contact' });
