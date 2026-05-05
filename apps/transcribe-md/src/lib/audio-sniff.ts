// ============================================================================
// Audio magic-byte sniff — Round 3 PR-J (audit finding A07-P0)
// ----------------------------------------------------------------------------
// The Content-Type header on /api/visits/[id]/upload is client-supplied
// and trivially spoofable. Browsers happily set Content-Type: audio/wav
// on a renamed `payload.txt` if a malicious script asks them to. The
// allowlist of MIME strings on the upload route is therefore a courtesy
// to honest clients, not a security boundary.
//
// This module performs a server-side magic-byte sniff on the first
// 16 bytes of the uploaded body and returns the actual format. The
// upload route compares the sniffed format against the claimed MIME
// and rejects on mismatch — that's the boundary.
//
// Coverage matches `ALLOWED_MIME` on apps/transcribe-md/src/app/api/
// visits/[id]/upload/route.ts. If a new MIME is added there, add the
// matching signature here.
// ============================================================================

/** Sniff result. `detected` is the canonical MIME we recognised, or
 *  null if the head doesn't match any known signature. */
export interface AudioSniffResult {
  detected: string | null;
  format: string | null;
}

/** Minimum bytes we need to make a decision. Real callers should
 *  pass at least this many; if the upload is shorter it's bogus and
 *  the sniff will return {detected: null}. */
export const SNIFF_MIN_BYTES = 16;

/** Inspect the leading bytes of an audio upload. Returns the canonical
 *  MIME we recognise, or null when no signature matches.
 *
 *  The sniffer is deliberately conservative: an unrecognised header
 *  is a rejection, not a fall-through-to-claimed-MIME. False
 *  negatives (legit format we don't recognise) are acceptable —
 *  the user gets a "format not supported" message and re-encodes.
 *  False positives (accepting a payload that isn't really audio)
 *  are not — they let an attacker bypass the boundary and ship
 *  arbitrary bytes to Deepgram. */
export function sniffAudioMagicBytes(head: Uint8Array): AudioSniffResult {
  if (head.length < SNIFF_MIN_BYTES) {
    return { detected: null, format: null };
  }

  // ── WAV (RIFF/WAVE) ───────────────────────────────────────────
  // bytes 0-3  = "RIFF"   (52 49 46 46)
  // bytes 4-7  = file size (varies — skip)
  // bytes 8-11 = "WAVE"   (57 41 56 45)
  if (
    head[0] === 0x52 &&
    head[1] === 0x49 &&
    head[2] === 0x46 &&
    head[3] === 0x46 &&
    head[8] === 0x57 &&
    head[9] === 0x41 &&
    head[10] === 0x56 &&
    head[11] === 0x45
  ) {
    return { detected: 'audio/wav', format: 'WAV' };
  }

  // ── MP3 ───────────────────────────────────────────────────────
  // ID3v2 tag:  "ID3" at offset 0           (49 44 33)
  // No tag:     MPEG audio frame sync — first byte 0xFF, second
  //             byte top 3 bits set: 0xE0 (MPEG 2.5/2/1, layer III)
  //             We accept the standard MPEG-1/2/2.5 layer 1/2/3
  //             frame syncs (0xFFE0..0xFFFF). Full validation of the
  //             layer + bitrate header is overkill; the frame sync
  //             alone is a strong-enough boundary check.
  if (head[0] === 0x49 && head[1] === 0x44 && head[2] === 0x33) {
    return { detected: 'audio/mpeg', format: 'MP3' };
  }
  if (head[0] === 0xff && (head[1]! & 0xe0) === 0xe0) {
    return { detected: 'audio/mpeg', format: 'MP3' };
  }

  // ── M4A / MP4 audio ───────────────────────────────────────────
  // bytes 0-3  = box size (varies — skip)
  // bytes 4-7  = "ftyp"   (66 74 79 70)
  // bytes 8-11 = brand. Common: "M4A " / "mp42" / "isom" / "isom"
  //             We accept anything with ftyp + a brand we've seen
  //             from real Deepgram-targetable uploads.
  if (
    head[4] === 0x66 &&
    head[5] === 0x74 &&
    head[6] === 0x79 &&
    head[7] === 0x70
  ) {
    // Brand candidates we accept. Browser-recorded m4a is "M4A " or
    // "mp42"; iOS voice memos write "M4A ". Generic mp4 audio is
    // "isom" / "iso2". Reject anything else (e.g. "qt  " QuickTime
    // movie) so a pure-video container can't slip through.
    const brand = String.fromCharCode(
      head[8]!,
      head[9]!,
      head[10]!,
      head[11]!
    );
    const ACCEPTED_BRANDS = new Set([
      'M4A ',
      'M4B ',
      'M4P ',
      'mp41',
      'mp42',
      'isom',
      'iso2',
      'iso5',
    ]);
    if (ACCEPTED_BRANDS.has(brand)) {
      return { detected: 'audio/mp4', format: 'M4A' };
    }
  }

  // ── Ogg ──────────────────────────────────────────────────────
  // bytes 0-3 = "OggS"   (4F 67 67 53)
  if (
    head[0] === 0x4f &&
    head[1] === 0x67 &&
    head[2] === 0x67 &&
    head[3] === 0x53
  ) {
    return { detected: 'audio/ogg', format: 'OGG' };
  }

  // ── WebM / Matroska ──────────────────────────────────────────
  // bytes 0-3 = EBML header (1A 45 DF A3)
  // We can't disambiguate audio-only WebM vs video-bearing WebM
  // from the head alone — that requires parsing EBML to find the
  // Tracks element. Accept either; Deepgram silently ignores
  // the video track if one is present.
  if (
    head[0] === 0x1a &&
    head[1] === 0x45 &&
    head[2] === 0xdf &&
    head[3] === 0xa3
  ) {
    return { detected: 'audio/webm', format: 'WebM' };
  }

  // ── FLAC ─────────────────────────────────────────────────────
  // bytes 0-3 = "fLaC"   (66 4C 61 43)
  if (
    head[0] === 0x66 &&
    head[1] === 0x4c &&
    head[2] === 0x61 &&
    head[3] === 0x43
  ) {
    return { detected: 'audio/flac', format: 'FLAC' };
  }

  return { detected: null, format: null };
}

/** Check whether a sniffed format matches a claimed MIME. Returns
 *  true on a clean match, false on mismatch. The claimed MIME may
 *  carry parameters (`audio/wav; codecs=1`); we strip those before
 *  comparing.
 *
 *  Family equivalences: `audio/mpeg` and `audio/mp3` are the same
 *  thing depending on which RFC/era the client used; treat them as
 *  identical. Same for `audio/m4a` ↔ `audio/mp4` ↔ `audio/x-m4a`,
 *  and `audio/wav` ↔ `audio/x-wav`. */
export function magicBytesMatchClaimedMime(
  sniffed: string | null,
  claimed: string
): boolean {
  if (!sniffed) return false;
  const claim = claimed.split(';')[0]!.trim().toLowerCase();
  const FAMILY: Record<string, ReadonlyArray<string>> = {
    'audio/wav': ['audio/wav', 'audio/x-wav'],
    'audio/mpeg': ['audio/mpeg', 'audio/mp3'],
    'audio/mp4': ['audio/mp4', 'audio/m4a', 'audio/x-m4a'],
    'audio/ogg': ['audio/ogg'],
    'audio/webm': ['audio/webm'],
    'audio/flac': ['audio/flac'],
  };
  const family = FAMILY[sniffed] ?? [sniffed];
  return family.includes(claim);
}
