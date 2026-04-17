// ============================================================================
// Internal service-token auth — token + IP gate
// ----------------------------------------------------------------------------
// Covers the two layers protecting /api/internal/*:
//   1. Bearer token equality vs SCRIBE_SERVICE_TOKEN env
//   2. Rejecting requests that came through an external proxy (Caddy
//      adds x-forwarded-for; if present the call didn't originate on
//      the Docker internal network)
// ============================================================================

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import type { NextRequest } from 'next/server';
import { verifyInternalRequest } from '../../src/lib/internal-auth';

const VALID = 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEF';

function mkReq(opts: {
  token?: string;
  xff?: string;
  xRealIp?: string;
}): NextRequest {
  const headers = new Map<string, string>();
  if (opts.token != null) headers.set('authorization', `Bearer ${opts.token}`);
  if (opts.xff != null) headers.set('x-forwarded-for', opts.xff);
  if (opts.xRealIp != null) headers.set('x-real-ip', opts.xRealIp);
  return {
    headers: {
      get: (k: string) => headers.get(k.toLowerCase()) ?? null,
    },
  } as unknown as NextRequest;
}

describe('verifyInternalRequest', () => {
  const origToken = process.env.SCRIBE_SERVICE_TOKEN;
  beforeEach(() => {
    process.env.SCRIBE_SERVICE_TOKEN = VALID;
  });
  afterEach(() => {
    if (origToken == null) delete process.env.SCRIBE_SERVICE_TOKEN;
    else process.env.SCRIBE_SERVICE_TOKEN = origToken;
  });

  it('rejects when no token is set on the server', () => {
    delete process.env.SCRIBE_SERVICE_TOKEN;
    const res = verifyInternalRequest(mkReq({ token: VALID, xRealIp: '172.18.0.5' }));
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.status).toBe(403);
  });

  it('rejects a missing Authorization header', () => {
    const res = verifyInternalRequest(mkReq({ xRealIp: '172.18.0.5' }));
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.status).toBe(401);
  });

  it('rejects a bad token (constant-time compare)', () => {
    const res = verifyInternalRequest(mkReq({ token: 'wrong', xRealIp: '172.18.0.5' }));
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.status).toBe(401);
  });

  it('rejects when x-forwarded-for is present (came through Caddy)', () => {
    const res = verifyInternalRequest(
      mkReq({ token: VALID, xff: '1.2.3.4', xRealIp: '172.18.0.5' })
    );
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.status).toBe(403);
  });

  it('accepts a private-network caller with a valid token and no x-forwarded-for', () => {
    const res = verifyInternalRequest(mkReq({ token: VALID, xRealIp: '172.18.0.5' }));
    expect(res.ok).toBe(true);
  });

  it('accepts loopback IPv4 + v6', () => {
    expect(verifyInternalRequest(mkReq({ token: VALID, xRealIp: '127.0.0.1' })).ok).toBe(true);
    expect(verifyInternalRequest(mkReq({ token: VALID, xRealIp: '::1' })).ok).toBe(true);
  });

  it('rejects a public-range IP even with a valid token', () => {
    const res = verifyInternalRequest(mkReq({ token: VALID, xRealIp: '8.8.8.8' }));
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.status).toBe(403);
  });
});
