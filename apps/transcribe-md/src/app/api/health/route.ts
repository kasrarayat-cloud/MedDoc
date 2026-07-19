// ============================================================================
// GET /api/health (T-M16.3)
// ----------------------------------------------------------------------------
// Probe endpoint for external uptime monitors + docker healthcheck.
// Unauthenticated by design — if your monitor needs auth, the "auth
// lookup is healthy" signal is a separate problem from "the app is
// up at all".
//
// Response:
//   200 { status: "healthy",   uptime_seconds, checks: {...}, version }
//   503 { status: "unhealthy", uptime_seconds, checks: {...}, version }
//
// Status aggregation:
//   - Any REQUIRED check failing → 503 unhealthy.
//   - Optional checks returning `ok: null` mean "unknown / not a
//     failure" (e.g. worker liveness — we don't have a cheap "alive"
//     signal and returning 503 on a quiet queue is worse UX than
//     returning unknown).
//
// Every check is raced against a 2-second timeout so a hung dependency
// never stretches the probe past 3 seconds total.
// ============================================================================

import { NextResponse } from "next/server";

import prisma from "@meddoc/db";
import { getSharedRedisConnection } from "@/lib/queue";
import { getMinio, TRANSCRIBE_MD_BUCKET } from "@/lib/minio";
import { readCleanupHeartbeats } from "@/lib/cleanup-heartbeat";
import {
  QUILLMD_RUNTIME_PROTOCOL_EPOCH,
  resolveTemplateTwinRuntimeMode,
} from "@/lib/runtime-protocol";
import { refreshTemplateTwinRuntimeAttestation } from "@/lib/template-twin/runtime-attestation";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Skip Next's caching for this route so monitors see live state.
export const revalidate = 0;

const PROCESS_START_AT = Date.now();
const CHECK_TIMEOUT_MS = 2_000;
// T-M18.3 A15: version is read from APP_VERSION at runtime so a deploy
// doesn't require a source-tree edit to bump the reported string. The
// fallback tracks the latest milestone this code is known to ship
// against, so an unset env var still produces a semi-useful answer
// rather than "unknown". docker-compose.yml passes APP_VERSION through
// from the host environment; CI populates it with the git tag at
// build time.
//
// T-M19.1: `||` rather than `??` because docker-compose's default
// pattern is `${APP_VERSION:-}` which substitutes an empty string when
// the host var is unset. Empty string is a defined value — `??` would
// propagate it through and we'd report `"version":""` instead of the
// fallback. `||` treats empty string as falsy and falls back correctly.
const VERSION = process.env.APP_VERSION || "T-M19.1";

interface CheckResult {
  ok: boolean | null;
  latency_ms?: number;
  error?: string;
}

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error(`timeout after ${ms}ms`)), ms),
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
      error: err instanceof Error ? err.message : "unknown",
    };
  }
}

async function checkRedis(): Promise<CheckResult> {
  const started = Date.now();
  try {
    const redis = getSharedRedisConnection();
    const reply = await withTimeout(redis.ping(), CHECK_TIMEOUT_MS);
    return {
      ok: reply === "PONG",
      latency_ms: Date.now() - started,
    };
  } catch (err) {
    return {
      ok: false,
      latency_ms: Date.now() - started,
      error: err instanceof Error ? err.message : "unknown",
    };
  }
}

async function checkMinio(): Promise<CheckResult> {
  const started = Date.now();
  try {
    // bucketExists catches "MinIO up but our bucket missing" which is
    // a distinct failure mode from "MinIO down" — same 503 though.
    const client = getMinio();
    const exists = await withTimeout(
      client.bucketExists(TRANSCRIBE_MD_BUCKET),
      CHECK_TIMEOUT_MS,
    );
    return { ok: exists === true, latency_ms: Date.now() - started };
  } catch (err) {
    return {
      ok: false,
      latency_ms: Date.now() - started,
      error: err instanceof Error ? err.message : "unknown",
    };
  }
}

async function checkTemplateTwinRuntimeIdentity(): Promise<CheckResult> {
  const started = Date.now();
  try {
    const state = await withTimeout(
      refreshTemplateTwinRuntimeAttestation({ tx: prisma }),
      CHECK_TIMEOUT_MS,
    );
    return {
      ok: state === "READY" ? true : null,
      latency_ms: Date.now() - started,
    };
  } catch {
    return {
      ok: false,
      latency_ms: Date.now() - started,
      error: "runtime deployment attestation unavailable",
    };
  }
}

export async function GET(): Promise<NextResponse> {
  const [
    postgres,
    redis,
    minio,
    templateTwinRuntimeIdentity,
    cleanupHeartbeats,
  ] = await Promise.all([
    checkPostgres(),
    checkRedis(),
    checkMinio(),
    checkTemplateTwinRuntimeIdentity(),
    // T-M18.2 A13 — best-effort; a Redis hiccup here should NOT
    // fail the health check (Redis itself has its own check line).
    readCleanupHeartbeats().catch(() => []),
  ]);

  const allOk =
    postgres.ok === true &&
    redis.ok === true &&
    minio.ok === true &&
    templateTwinRuntimeIdentity.ok !== false;

  const body = {
    status: allOk ? "healthy" : "unhealthy",
    uptime_seconds: Math.floor((Date.now() - PROCESS_START_AT) / 1000),
    checks: {
      postgres,
      redis,
      minio,
      template_twin_runtime_identity: templateTwinRuntimeIdentity,
    },
    // Each cron reports `ageSeconds: null` until its first run. An
    // external monitor can alert on `ageSeconds > 26 * 3600` (24h
    // expected cadence + 2h grace) — but this probe stays 200 even
    // when a cron is stale, because "app up, cron sleepy" shouldn't
    // take the container out of Docker's healthcheck loop.
    cleanup_crons: cleanupHeartbeats,
    version: VERSION,
    runtime_protocol_epoch: QUILLMD_RUNTIME_PROTOCOL_EPOCH,
    runtime_mode: resolveTemplateTwinRuntimeMode(process.env),
  };

  return NextResponse.json(body, {
    status: allOk ? 200 : 503,
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
}
