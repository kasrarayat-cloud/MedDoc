// ============================================================================
// docker-compose port-publish posture (Security Audit P1-I, 2026-05-13)
// ----------------------------------------------------------------------------
// Pre-fix, docker-compose.yml published `9010:9010` and `9020:9020`
// without a `127.0.0.1:` loopback prefix. The matching Caddyfile
// MODE A blocks were commented out so no plaintext was actually
// served — but anyone uncommenting MODE A alone would instantly
// expose plaintext HTTP on a public port, bypassing MODE B's HSTS.
//
// Fix: comment out the publishes in lockstep with the Caddyfile MODE A
// blocks. Rollback now requires uncommenting both files, which makes
// "accidentally re-enable plaintext" much harder.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const COMPOSE_SRC = readFileSync(
  resolve(__dirname, '..', '..', '..', '..', 'docker-compose.yml'),
  'utf-8',
);
const CADDY_SRC = readFileSync(
  resolve(__dirname, '..', '..', '..', '..', 'Caddyfile'),
  'utf-8',
);

describe('docker-compose — MODE A ports remain commented (P1-I)', () => {
  it('does NOT publish 9010 on 0.0.0.0 (must be either commented or 127.0.0.1-prefixed)', () => {
    // The negative assertion: no uncommented `- "9010:9010"` line.
    // (Caddy's `ports:` list is a YAML block of `- "X:Y"` entries.)
    const matches = COMPOSE_SRC.match(/^\s*-\s*"9010:9010"/gm);
    expect(matches).toBeNull();
  });

  it('does NOT publish 9020 on 0.0.0.0', () => {
    const matches = COMPOSE_SRC.match(/^\s*-\s*"9020:9020"/gm);
    expect(matches).toBeNull();
  });

  it('keeps a rollback breadcrumb pointing at Caddyfile MODE A', () => {
    // Both port lines are kept as `# - "..."` rollback comments;
    // they reference the matching Caddyfile MODE A block. This is
    // the lockstep coupling — re-enabling plaintext requires
    // editing two files in coordination.
    expect(COMPOSE_SRC).toMatch(/#\s*-\s*"9010:9010"/);
    expect(COMPOSE_SRC).toMatch(/#\s*-\s*"9020:9020"/);
    expect(COMPOSE_SRC).toMatch(/Caddyfile\s*MODE\s*A/i);
  });
});

describe('Caddyfile — MODE A blocks still commented (rollback invariant)', () => {
  it('the :9010 server block is commented out', () => {
    // Active server blocks look like `:9010 {` at the start of a line.
    // Commented rollback shape is `# :9010 {`.
    expect(CADDY_SRC).not.toMatch(/^:9010\s*\{/m);
    expect(CADDY_SRC).toMatch(/^#\s*:9010\s*\{/m);
  });

  it('the :9020 server block is commented out', () => {
    expect(CADDY_SRC).not.toMatch(/^:9020\s*\{/m);
    expect(CADDY_SRC).toMatch(/^#\s*:9020\s*\{/m);
  });
});
