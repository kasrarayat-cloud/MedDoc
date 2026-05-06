#!/usr/bin/env node
// sweep-marketing-signup.mjs — quillmd.com/signup (meta-refresh redirect).
// Note: this page redirects to app.quillmd.com/signup; we expect the
// initial response to be the marketing redirect page, NOT the app's
// signup form (which is exercised by sweep-signup.mjs).
import { smokeWalkPublic } from './lib/walker-base.mjs';
await smokeWalkPublic({ name: 'marketing-signup', url: '/signup' });
