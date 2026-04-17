// ============================================================================
// M7 — Service-token resolution (file vs env, caching)
// ----------------------------------------------------------------------------
// Locks the fallback contract: SCRIBE_SERVICE_TOKEN_FILE beats
// SCRIBE_SERVICE_TOKEN, empty/missing file falls through, caching holds
// across calls within the same process.
// ============================================================================

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { beforeEach, afterEach, describe, it, expect } from 'vitest';
import {
  readServiceToken,
  resolveServiceToken,
  _resetServiceTokenCache,
} from '@meddoc/auth';

const envSnapshot: Record<string, string | undefined> = {};
let tmpDir: string;

function restoreEnv(): void {
  for (const key of ['SCRIBE_SERVICE_TOKEN', 'SCRIBE_SERVICE_TOKEN_FILE']) {
    const prev = envSnapshot[key];
    if (prev === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = prev;
    }
  }
}

beforeEach(() => {
  envSnapshot.SCRIBE_SERVICE_TOKEN = process.env.SCRIBE_SERVICE_TOKEN;
  envSnapshot.SCRIBE_SERVICE_TOKEN_FILE = process.env.SCRIBE_SERVICE_TOKEN_FILE;
  delete process.env.SCRIBE_SERVICE_TOKEN;
  delete process.env.SCRIBE_SERVICE_TOKEN_FILE;
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'meddoc-token-'));
  _resetServiceTokenCache();
});

afterEach(() => {
  restoreEnv();
  fs.rmSync(tmpDir, { recursive: true, force: true });
  _resetServiceTokenCache();
});

describe('readServiceToken', () => {
  it('returns null when neither file nor env is set', () => {
    expect(readServiceToken()).toBeNull();
  });

  it('reads from SCRIBE_SERVICE_TOKEN env when no file path is configured', () => {
    process.env.SCRIBE_SERVICE_TOKEN = 'env-secret-abc';
    expect(readServiceToken()).toBe('env-secret-abc');
    expect(resolveServiceToken().source).toBe('env');
  });

  it('reads from the file when SCRIBE_SERVICE_TOKEN_FILE is set and file exists', () => {
    const p = path.join(tmpDir, 'token');
    fs.writeFileSync(p, 'file-secret-xyz\n');
    process.env.SCRIBE_SERVICE_TOKEN_FILE = p;
    process.env.SCRIBE_SERVICE_TOKEN = 'env-secret-abc';
    _resetServiceTokenCache();
    expect(readServiceToken()).toBe('file-secret-xyz');
    _resetServiceTokenCache();
    expect(resolveServiceToken().source).toBe('file');
  });

  it('falls back to env when the file path is configured but the file is missing', () => {
    process.env.SCRIBE_SERVICE_TOKEN_FILE = path.join(tmpDir, 'does-not-exist');
    process.env.SCRIBE_SERVICE_TOKEN = 'env-fallback';
    expect(readServiceToken()).toBe('env-fallback');
    _resetServiceTokenCache();
    expect(resolveServiceToken().source).toBe('env');
  });

  it('falls back to env when the file exists but is empty', () => {
    const p = path.join(tmpDir, 'empty');
    fs.writeFileSync(p, '   \n  ');
    process.env.SCRIBE_SERVICE_TOKEN_FILE = p;
    process.env.SCRIBE_SERVICE_TOKEN = 'env-fallback';
    expect(readServiceToken()).toBe('env-fallback');
  });

  it('trims surrounding whitespace from the file contents', () => {
    const p = path.join(tmpDir, 'padded');
    fs.writeFileSync(p, '   padded-secret\n\n');
    process.env.SCRIBE_SERVICE_TOKEN_FILE = p;
    expect(readServiceToken()).toBe('padded-secret');
  });

  it('caches the resolved value — changing the env after first read is a no-op', () => {
    process.env.SCRIBE_SERVICE_TOKEN = 'first';
    expect(readServiceToken()).toBe('first');
    process.env.SCRIBE_SERVICE_TOKEN = 'second';
    expect(readServiceToken()).toBe('first');
    _resetServiceTokenCache();
    expect(readServiceToken()).toBe('second');
  });
});
