// ============================================================================
// Dictation upload magic-byte sniff (Security Audit P1-D, 2026-05-13)
// ----------------------------------------------------------------------------
// The bulk audio upload route (Round 3 PR-J) buffers the body, sniffs
// the leading bytes, and rejects on MIME mismatch. The dictation
// upload route was missed and trusted the client-supplied
// Content-Type header. This fix lifts the same buffer-and-sniff
// pattern. Source-pin so a future refactor can't drop it.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SRC = readFileSync(
  resolve(
    __dirname,
    '..',
    '..',
    'src',
    'app',
    'api',
    'visits',
    '[id]',
    'dictation',
    'upload',
    'route.ts',
  ),
  'utf-8',
);

describe('dictation upload — magic-byte sniff (P1-D)', () => {
  it('imports the sniff helpers from @/lib/audio-sniff', () => {
    expect(SRC).toMatch(
      /import\s+\{[\s\S]*?sniffAudioMagicBytes[\s\S]*?magicBytesMatchClaimedMime[\s\S]*?\}\s+from\s+['"]@\/lib\/audio-sniff['"]/,
    );
  });

  it('buffers the body to a Buffer before streaming to MinIO', () => {
    expect(SRC).toMatch(/Buffer\.from\(\s*await\s+req\.arrayBuffer\(\)/);
  });

  it('calls sniffAudioMagicBytes on the buffered head', () => {
    expect(SRC).toMatch(
      /sniffAudioMagicBytes\(\s*bodyBuffer\.subarray\(0,/,
    );
  });

  it('rejects with 415 + AUDIO_REJECTED_INVALID_MAGIC_BYTES audit on MIME mismatch', () => {
    expect(SRC).toMatch(
      /magicBytesMatchClaimedMime\(\s*sniff\.detected,\s*mimeType\s*\)/,
    );
    expect(SRC).toMatch(
      /action:\s*['"]AUDIO_REJECTED_INVALID_MAGIC_BYTES['"]/,
    );
    // 415 status returned with the INVALID_MAGIC_BYTES code; the
    // apiError signature is `apiError(msg, 415, { code: 'INVALID_MAGIC_BYTES' })`
    // so 415 lands BEFORE the code literal. Match both orderings to
    // survive future code-shape tweaks.
    expect(SRC).toMatch(
      /415[\s\S]{0,200}?['"]INVALID_MAGIC_BYTES['"]|['"]INVALID_MAGIC_BYTES['"][\s\S]{0,200}?415/,
    );
  });

  it('audits with source=dictation so the bulk-upload + dictation paths are distinguishable', () => {
    expect(SRC).toMatch(/source:\s*['"]dictation['"]/);
  });

  it('streams the BUFFERED body to MinIO (not the raw req.body stream)', () => {
    // The sniff requires a buffered body; the put must use that
    // same buffer (Readable.from(bodyBuffer)), not Readable.fromWeb
    // (which would double-read the request).
    expect(SRC).toMatch(/Readable\.from\(\s*bodyBuffer\s*\)/);
    expect(SRC).not.toMatch(/Readable\.fromWeb\(\s*req\.body/);
  });
});
