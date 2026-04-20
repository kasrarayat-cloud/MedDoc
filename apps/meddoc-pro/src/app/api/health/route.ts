// ============================================================================
// GET /api/health (T-M16.3)
// ----------------------------------------------------------------------------
// Probe endpoint for external uptime monitors + docker healthcheck.
// meddoc-pro's dependency surface is smaller than transcribe-md's —
// postgres is the only thing the app can't run without. Sentry /
// Dropbox / Resend are all "degrade gracefully when unavailable" at
// the feature level, not "the app can't serve requests" concerns.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const revalidate = 0;

const PROCESS_START_AT = Date.now();
const CHECK_TIMEOUT_MS = 2_000;
const VERSION = 'T-M16.3';

interface CheckResult {
  ok: boolean | null;
  latency_ms?: number;
  error?: string;
}

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error(`timeout after ${ms}ms`)), ms)
    ),
  ]);
}

async function checkPostgres(): Promise<CheckResult> {
  const started = Date.now();
  try {
    await withTimeout(prisma.$queryRaw`SELECT 1`, CHECK_TIMEOUT_MS);
    return { ok: true, latency_ms: Date.now() - started };
  } catch (err) {
    return {
      ok: false,
      latency_ms: Date.now() - started,
      error: err instanceof Error ? err.message : 'unknown',
    };
  }
}

export async function GET(): Promise<NextResponse> {
  const postgres = await checkPostgres();
  const allOk = postgres.ok === true;

  const body = {
    status: allOk ? 'healthy' : 'unhealthy',
    uptime_seconds: Math.floor((Date.now() - PROCESS_START_AT) / 1000),
    checks: { postgres },
    version: VERSION,
  };

  return NextResponse.json(body, {
    status: allOk ? 200 : 503,
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate',
    },
  });
}
