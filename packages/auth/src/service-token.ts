// ============================================================================
// @meddoc/auth — service-to-service token resolution (M7 D4)
// ----------------------------------------------------------------------------
// The Scribe ↔ MedDoc Pro internal API is authenticated by a shared bearer
// token (`SCRIBE_SERVICE_TOKEN`). M7 adds a file-based alternative so
// rotation can be done via a mounted secret file + container restart,
// without editing the top-level .env.
//
// Resolution order (first non-empty wins):
//   1. SCRIBE_SERVICE_TOKEN_FILE → file contents (trimmed)
//   2. SCRIBE_SERVICE_TOKEN       → env var value
//
// Result is cached in-memory for the process lifetime. See
// docs/ROTATION_RUNBOOK.md for the rotation procedure.
// ============================================================================

import { readFileSync } from 'node:fs';

let cached: string | null | undefined; // undefined = not yet resolved

interface ResolveResult {
  token: string | null;
  source: 'file' | 'env' | 'none';
}

function resolveOnce(): ResolveResult {
  const filePath = process.env.SCRIBE_SERVICE_TOKEN_FILE?.trim();
  if (filePath) {
    try {
      const contents = readFileSync(filePath, 'utf8').trim();
      if (contents) {
        return { token: contents, source: 'file' };
      }
      console.error(
        `[service-token] SCRIBE_SERVICE_TOKEN_FILE=${filePath} is empty; falling back to env var.`
      );
    } catch (err) {
      console.error(
        `[service-token] failed to read ${filePath}:`,
        err instanceof Error ? err.message : err
      );
      // Fall through to env.
    }
  }

  const fromEnv = process.env.SCRIBE_SERVICE_TOKEN?.trim();
  if (fromEnv) return { token: fromEnv, source: 'env' };

  return { token: null, source: 'none' };
}

/**
 * Returns the resolved token or null when neither file nor env var is
 * set. Cached after the first call — rotating without a restart is
 * intentionally unsupported in M7 (see runbook; SIGHUP reload is M7.1).
 */
export function readServiceToken(): string | null {
  if (cached !== undefined) return cached;
  const { token } = resolveOnce();
  cached = token;
  return cached;
}

/**
 * Same as readServiceToken() but returns { token, source }. Health
 * checks use this to surface whether rotation is configured via file
 * or still falls through to env.
 */
export function resolveServiceToken(): ResolveResult {
  const r = resolveOnce();
  cached = r.token;
  return r;
}

/** Test helper — resets the in-memory cache so each test sees a fresh resolve. */
export function _resetServiceTokenCache(): void {
  cached = undefined;
}
