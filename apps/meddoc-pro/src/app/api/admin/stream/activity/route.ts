// ============================================================================
// GET /api/admin/stream/activity — Server-Sent Events for live audit feed
// ----------------------------------------------------------------------------
// Browser opens an EventSource against this endpoint; we subscribe to
// the `admin:audit-stream` Redis channel and push each message back as
// an SSE `data:` line. logAudit() in BOTH apps publishes after each
// successful DB write, so the stream sees every audit row landed
// across the whole platform.
//
// Heartbeats every 30s (`: keep-alive\n\n` SSE comment lines) so
// upstream proxies don't time out idle connections.
//
// Important: this is auth-gated by adminApi() like every other admin
// route — non-admins get a 404, not a 401. Only SUPER_ADMIN sessions
// can subscribe.
// ============================================================================

import IORedis from 'ioredis';

import { adminApi } from '@/lib/admin-api-gate';
import { ADMIN_AUDIT_STREAM_CHANNEL } from '@/lib/redis';

export const dynamic = 'force-dynamic';
// Long-lived connection — disable Next's per-request timeout cap.
export const maxDuration = 300;

// Heartbeat cadence. 30s sits comfortably below most proxy idle
// limits (Caddy default 60s) without burning bandwidth.
const HEARTBEAT_MS = 30_000;

export const GET = adminApi('stream:activity', async (req) => {
  // Build a dedicated subscriber. ioredis requires a fresh client for
  // each subscription so this connection can't be the shared one used
  // for publishes elsewhere — the shared client would refuse normal
  // commands while in subscriber mode.
  const redisUrl =
    process.env.REDIS_URL?.trim() || 'redis://localhost:6379';
  const sub = new IORedis(redisUrl, {
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
  });

  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      let heartbeat: ReturnType<typeof setInterval> | null = null;
      let abortHandler: (() => void) | null = null;

      const cleanup = () => {
        if (closed) return;
        closed = true;
        if (heartbeat) clearInterval(heartbeat);
        if (abortHandler) req.signal.removeEventListener('abort', abortHandler);
        sub.unsubscribe(ADMIN_AUDIT_STREAM_CHANNEL).catch(() => {});
        sub.quit().catch(() => {});
        try {
          controller.close();
        } catch {
          // Already closed by the runtime — ignore.
        }
      };

      // Initial open event — clients use this to know the stream is live.
      controller.enqueue(
        encoder.encode(
          `event: open\ndata: ${JSON.stringify({ ts: new Date().toISOString() })}\n\n`
        )
      );

      // Heartbeats so proxies don't drop idle connections.
      heartbeat = setInterval(() => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(': keep-alive\n\n'));
        } catch {
          cleanup();
        }
      }, HEARTBEAT_MS);

      // Subscribe to the channel.
      await sub.subscribe(ADMIN_AUDIT_STREAM_CHANNEL);
      sub.on('message', (channel, payload) => {
        if (closed || channel !== ADMIN_AUDIT_STREAM_CHANNEL) return;
        try {
          controller.enqueue(encoder.encode(`data: ${payload}\n\n`));
        } catch {
          cleanup();
        }
      });
      sub.on('error', (err) => {
        console.warn('[admin:stream] subscriber error:', err.message);
        cleanup();
      });

      // Tear down when the client disconnects.
      abortHandler = () => cleanup();
      if (req.signal.aborted) {
        cleanup();
      } else {
        req.signal.addEventListener('abort', abortHandler);
      }
    },

    cancel() {
      // Reader cancelled — the start() closure's cleanup() handles
      // the rest via the signal listener; no-op here.
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-store, no-transform',
      Connection: 'keep-alive',
      // Disable buffering on Caddy/Nginx-style proxies.
      'X-Accel-Buffering': 'no',
    },
  });
});
