// ============================================================================
// media-mocks.mjs — Playwright addInitScript payload that stubs the browser
// MediaRecorder + getUserMedia surface for the visit-record walker (v3.3).
// ----------------------------------------------------------------------------
// Why a string-encoded init script instead of a Playwright page.evaluate?
// addInitScript runs BEFORE any page script, including React hydration.
// The recording page (apps/transcribe-md/src/app/visits/[id]/record/
// recording-client.tsx) reads `navigator.mediaDevices.getUserMedia` and
// `window.MediaRecorder` lazily inside its `start()` handler, so we need
// the stubs in place before the user clicks "Start recording" but well
// after page load is fine — the stubs land at document-start regardless.
//
// What this script does:
//   1. Replaces navigator.mediaDevices.getUserMedia with a stub that
//      returns a deterministic MediaStream from an AudioContext sink
//      whose oscillator is never started. The stream is structurally
//      valid (the page can call .getTracks() and stop them) but
//      produces no audio data — so MediaRecorder never receives chunks.
//   2. Replaces enumerateDevices with a single mock-mic entry so the
//      page's device-select dropdown (if any) renders without errors.
//   3. Replaces window.MediaRecorder with a class that mimics the API
//      (.start, .stop, .pause, .resume, state, ondataavailable, onstop)
//      but never fires `ondataavailable`. When .stop() is called the
//      class fires `onstop` synchronously via queueMicrotask so the
//      page's finalize-and-upload logic runs in its expected order.
//
// What this script DOES NOT do:
//   - It does not stub fetch. The page's finalizeAndUpload still POSTs
//     to /api/visits/[id]/dictation/upload after `onstop`. The walker
//     handles that by NOT clicking "Stop & process" — only "Start
//     recording" + observation of state transitions. Letting the
//     real fetch happen on Stop would create a real (empty-body)
//     server-side error and is out of the walker's read-only scope.
//   - It does not stub WebRTC / RTCPeerConnection. The recording page
//     today is batch-only (uploads after stop); if a future iteration
//     adds live streaming, the walker (and this mock) need to grow.
//
// Reference for callers (the walker):
//   await context.addInitScript(MEDIA_MOCK_SCRIPT);
//   await page.goto('/visits/<id>/record');
// ============================================================================

export const MEDIA_MOCK_SCRIPT = `
(() => {
  // ── getUserMedia ───────────────────────────────────────────────────────
  // Build a silent MediaStream once, on first call. Reusing the same
  // stream avoids leaking AudioContexts across multiple invocations
  // (the page's start() can be retried on error).
  let cachedStream = null;
  function buildSilentStream() {
    if (cachedStream) return cachedStream;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) {
      // Hard fallback: synthesize an empty MediaStream-like object.
      // Won't satisfy MediaRecorder's track requirement but at least
      // the page's getUserMedia call resolves rather than rejecting.
      const stream = { getTracks: () => [], getAudioTracks: () => [] };
      cachedStream = stream;
      return stream;
    }
    const ctx = new Ctx();
    const dst = ctx.createMediaStreamDestination();
    const osc = ctx.createOscillator();
    osc.connect(dst);
    // Deliberately NOT started — silent track. The MediaRecorder mock
    // below ignores dataavailable anyway, so even if a real recorder
    // is somehow constructed, no audio leaks.
    cachedStream = dst.stream;
    return cachedStream;
  }

  const fakeMediaDevices = {
    getUserMedia: async (_constraints) => buildSilentStream(),
    enumerateDevices: async () => [
      {
        deviceId: 'qa-mock-microphone',
        kind: 'audioinput',
        label: 'QA Mock Microphone',
        groupId: 'qa-mock-group',
        toJSON() { return { ...this }; },
      },
    ],
    // No-op event listener surface — page may call addEventListener
    // on devicechange. Polyfill these so the page's defensive code
    // doesn't blow up on undefined.
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  };

  // Some browsers expose mediaDevices as a non-configurable property.
  // Try defineProperty first; fall back to direct assignment if not.
  try {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      enumerable: true,
      writable: true,
      value: fakeMediaDevices,
    });
  } catch {
    try {
      // eslint-disable-next-line no-restricted-syntax
      navigator.mediaDevices = fakeMediaDevices;
    } catch {
      // Last resort: leave the real mediaDevices but override
      // getUserMedia in place. Playwright runs in headless Chromium
      // where mediaDevices is configurable, so we never expect to hit
      // this branch.
      navigator.mediaDevices.getUserMedia = fakeMediaDevices.getUserMedia;
      navigator.mediaDevices.enumerateDevices = fakeMediaDevices.enumerateDevices;
    }
  }

  // ── MediaRecorder ──────────────────────────────────────────────────────
  class MockMediaRecorder {
    constructor(stream, opts) {
      this.stream = stream;
      this.mimeType = (opts && opts.mimeType) || 'audio/webm';
      this.state = 'inactive';
      this.audioBitsPerSecond = (opts && opts.audioBitsPerSecond) || 0;
      this.videoBitsPerSecond = 0;
      this.ondataavailable = null;
      this.onstop = null;
      this.onstart = null;
      this.onerror = null;
      this.onpause = null;
      this.onresume = null;
      // EventTarget surface for any code that calls addEventListener.
      this._listeners = Object.create(null);
    }
    addEventListener(type, fn) {
      (this._listeners[type] = this._listeners[type] || []).push(fn);
    }
    removeEventListener(type, fn) {
      const arr = this._listeners[type] || [];
      const i = arr.indexOf(fn);
      if (i >= 0) arr.splice(i, 1);
    }
    dispatchEvent(event) {
      const arr = this._listeners[event.type] || [];
      for (const fn of arr.slice()) {
        try { fn.call(this, event); } catch { /* swallow */ }
      }
      const handler = this['on' + event.type];
      if (typeof handler === 'function') {
        try { handler.call(this, event); } catch { /* swallow */ }
      }
      return true;
    }
    start(_timesliceMs) {
      this.state = 'recording';
      // Fire start synchronously so the page's UI can transition into
      // 'recording' phase without a microtask gap.
      this.dispatchEvent(new Event('start'));
      // Deliberately do NOT schedule periodic dataavailable events —
      // chunksRef stays empty, finalizeAndUpload sees a 0-byte blob.
    }
    stop() {
      if (this.state === 'inactive') return;
      this.state = 'inactive';
      // Fire stop on the next microtask so the page has a chance to
      // tear down its tick interval before finalizeAndUpload reads
      // chunksRef. Mirrors real-MediaRecorder ordering closely enough
      // that the page's finalize handler runs in its expected sequence.
      queueMicrotask(() => this.dispatchEvent(new Event('stop')));
    }
    pause() {
      if (this.state !== 'recording') return;
      this.state = 'paused';
      this.dispatchEvent(new Event('pause'));
    }
    resume() {
      if (this.state !== 'paused') return;
      this.state = 'recording';
      this.dispatchEvent(new Event('resume'));
    }
    requestData() { /* no-op — we never produce chunks */ }
    static isTypeSupported(_type) { return true; }
  }

  try {
    // eslint-disable-next-line no-restricted-syntax
    window.MediaRecorder = MockMediaRecorder;
  } catch {
    // Platforms where window.MediaRecorder is non-configurable —
    // unlikely in headless Chromium but degrade gracefully.
  }

  // ── Breadcrumb ─────────────────────────────────────────────────────────
  // The walker reads __qaMediaMockInjected to confirm the init script
  // ran (proves the addInitScript landed before page hydration).
  try {
    Object.defineProperty(window, '__qaMediaMockInjected', {
      configurable: false,
      enumerable: false,
      writable: false,
      value: { at: Date.now(), version: 'v3.3' },
    });
  } catch { /* ignore */ }
})();
`;
