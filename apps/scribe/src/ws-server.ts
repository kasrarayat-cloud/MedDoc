// ============================================================================
// apps/scribe — WebSocket sidecar for real-time visits (M3)
// ----------------------------------------------------------------------------
// Runs in its own container (scribe-ws) per the M3 plan decision D1 —
// Next.js 16's standalone output is incompatible with a custom server,
// so the WS upgrade path is served out-of-process. Caddy routes
// scribe.<domain>/api/ws/* → this service on port SCRIBE_WS_PORT.
//
// Responsibilities:
//   - HTTP upgrade handler authenticates via shared NextAuth cookie +
//     verifies visit ownership + acquires the per-user concurrency lock
//   - On accept: transitions visit DRAFT→RECORDING, writes WS_CONNECTED
//     audit, hands the socket to startLiveSession() to run the Deepgram
//     proxy for the lifetime of the connection
//   - /health returns 200 so compose healthchecks pass
// ============================================================================

import 'dotenv/config';
import http from 'node:http';
import { parse as parseUrl } from 'node:url';
import { parse as parseCookie } from 'cookie';
import { decode } from 'next-auth/jwt';
import { WebSocketServer, type WebSocket } from 'ws';
import type { Socket } from 'node:net';
import IORedis from 'ioredis';
import prisma from '@meddoc/db';
import { redactPhi } from '@meddoc/ai';
import { acquireLiveLock } from '@/server/live/concurrency';
import { startLiveSession } from '@/server/live/session';

const PORT = Number(process.env.SCRIBE_WS_PORT ?? 3003);
const REDIS_URL = process.env.REDIS_URL?.trim() || 'redis://redis:6379';
const AUTH_SECRET = process.env.AUTH_SECRET;
const COOKIE_NAME =
  process.env.NODE_ENV === 'production'
    ? '__Secure-authjs.session-token'
    : 'authjs.session-token';

if (!AUTH_SECRET) {
  console.error('[scribe-ws] AUTH_SECRET is not set — refusing to start.');
  process.exit(1);
}

const redis = new IORedis(REDIS_URL, { maxRetriesPerRequest: null });
redis.on('error', (err) => {
  console.error('[scribe-ws] redis error:', redactPhi(err.message));
});

const WS_PATH_RE = /^\/api\/ws\/visit\/([a-zA-Z0-9_-]+)\/?$/;

interface AuthedUpgrade {
  visitId: string;
  userId: string;
  practiceId: string;
}

type UpgradeResult =
  | { ok: true; authed: AuthedUpgrade }
  | { ok: false; status: number; reason: string };

async function authenticateUpgrade(req: http.IncomingMessage): Promise<UpgradeResult> {
  if (!req.url) return { ok: false, status: 400, reason: 'no url' };
  const { pathname } = parseUrl(req.url);
  if (!pathname) return { ok: false, status: 400, reason: 'bad path' };

  const match = WS_PATH_RE.exec(pathname);
  if (!match) return { ok: false, status: 404, reason: 'unknown path' };
  const visitId = match[1];

  const cookieHeader = req.headers.cookie ?? '';
  const cookies = parseCookie(cookieHeader);
  const token = cookies[COOKIE_NAME];
  if (!token) return { ok: false, status: 401, reason: 'no session cookie' };

  const payload = await decode({
    token,
    secret: AUTH_SECRET!,
    salt: COOKIE_NAME,
  });
  if (!payload || typeof payload !== 'object') {
    return { ok: false, status: 401, reason: 'bad session' };
  }
  const userId = (payload as { id?: string }).id;
  const practiceId = (payload as { practiceId?: string }).practiceId;
  if (!userId || !practiceId) {
    return { ok: false, status: 401, reason: 'incomplete session' };
  }

  const visit = await prisma.scribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      practiceId: true,
      userId: true,
      mode: true,
      status: true,
      deletedAt: true,
    },
  });
  if (!visit || visit.deletedAt) {
    return { ok: false, status: 404, reason: 'visit not found' };
  }
  if (visit.practiceId !== practiceId || visit.userId !== userId) {
    // Don't leak existence to a cross-tenant caller — same opaque 404 a
    // direct fetch would get.
    return { ok: false, status: 404, reason: 'visit not found' };
  }
  if (visit.mode !== 'LIVE') {
    return { ok: false, status: 400, reason: 'visit is not LIVE mode' };
  }
  if (visit.status !== 'DRAFT' && visit.status !== 'RECORDING') {
    return { ok: false, status: 409, reason: `status is ${visit.status}` };
  }

  const locked = await acquireLiveLock(redis, userId, visitId);
  if (!locked) {
    return { ok: false, status: 409, reason: 'another live stream active' };
  }

  return { ok: true, authed: { visitId, userId, practiceId } };
}

function rejectUpgrade(socket: Socket, status: number, reason: string): void {
  const body = JSON.stringify({ error: reason });
  const statusText =
    status === 400
      ? 'Bad Request'
      : status === 401
        ? 'Unauthorized'
        : status === 404
          ? 'Not Found'
          : status === 409
            ? 'Conflict'
            : 'Error';
  socket.write(
    `HTTP/1.1 ${status} ${statusText}\r\n` +
      `Content-Type: application/json\r\n` +
      `Content-Length: ${Buffer.byteLength(body)}\r\n` +
      `Connection: close\r\n\r\n` +
      body
  );
  socket.destroy();
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, service: 'scribe-ws' }));
    return;
  }
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'not found' }));
});

const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (req, socket, head) => {
  void (async () => {
    try {
      const result = await authenticateUpgrade(req);
      if (!result.ok) {
        rejectUpgrade(socket as Socket, result.status, result.reason);
        return;
      }
      wss.handleUpgrade(req, socket as Socket, head, (ws) => {
        wss.emit('connection', ws, req, result.authed);
      });
    } catch (err) {
      console.error(
        '[scribe-ws] upgrade handler error:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      rejectUpgrade(socket as Socket, 500, 'internal error');
    }
  })();
});

wss.on('connection', (ws: WebSocket, _req: http.IncomingMessage, authed: AuthedUpgrade) => {
  const { visitId, userId, practiceId } = authed;

  void (async () => {
    try {
      // Transition DRAFT → RECORDING (idempotent for a reconnect into
      // an already-RECORDING visit). Audit the WS accept.
      await prisma.scribeVisit.update({
        where: { id: visitId },
        data: { status: 'RECORDING' },
      });
      await prisma.scribeAuditEvent.create({
        data: {
          practiceId,
          visitId,
          actorId: userId,
          action: 'WS_CONNECTED',
        },
      });
      startLiveSession({ ws, redis, visitId, practiceId, userId });
    } catch (err) {
      console.error(
        `[scribe-ws] visit ${visitId} init failed:`,
        redactPhi(err instanceof Error ? err.message : err)
      );
      try {
        ws.send(JSON.stringify({ type: 'error', code: 'INIT_FAILED' }));
        ws.close();
      } catch {
        /* already closed */
      }
    }
  })();
});

function shutdown(signal: string): void {
  console.log(`[scribe-ws] ${signal} — shutting down…`);
  wss.clients.forEach((ws) => {
    try {
      ws.close(1001, 'server shutdown');
    } catch {
      /* ignored */
    }
  });
  server.close(() => {
    void redis.quit().finally(() => process.exit(0));
  });
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

server.listen(PORT, () => {
  console.log(`[scribe-ws] listening on :${PORT} (path /api/ws/visit/:id)`);
});
