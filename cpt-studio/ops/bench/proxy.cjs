// The bench's loopback proxy (RELEASE-2-SPEC R2-2): it stands where nginx stands in production, between the browser and a
// tree's gunicorn, on 127.0.0.1 only. It never touches the request or answer bodies.
//
//   node proxy.cjs --listen <port> --upstream <port> --control <port> [--log <file>] [--host-header <name>]
//
// - Every request gets an X-Request-ID of 32 hex characters (as nginx gives one), unless it already has one, so each
//   served request can be joined to the access record the application writes with that id; the answer carries it back
//   as X-Bench-Request-Id, so the browser side can join what the page received to that record too.
// - Every request is logged when its answer ends: sequence, start and end (ms since the epoch, fractional), method, the
//   path with its query, status, the answer's body bytes, the request body's bytes, the request headers (the Cookie
//   server's own cookies replaced: the session's by a short digest that names the member and nothing else, the CSRF
//   and device cookies by <redacted>; any other cookie logged as sent, for the marker scan) and the answer's
//   headers. The log is the bench's server-side truth for counts, in-flight requests, cache headers and the marker scan.
// - Rules, set on the control port: `delay` holds a matching request `ms` before it is sent upstream (the planted-delay
//   control); `hold` holds a matching request `ms` before it is sent (a hung document). Each applies `times` times.
// - `upstream` flips where the next requests go (blue/green, X1 and X2). Requests already sent finish where they began.
// - `--host-header` sends every request with that Host, its Origin and Referer rewritten to it (the admin host for the
//   walk: the application chooses its urlconf by Host).
// Control port (127.0.0.1): GET /log?since=<seq>, GET /state, POST /upstream {port}, POST /rule {kind, match, ms, times},
// POST /clear. It prints `proxy up <listen> <control>` once both ports listen.
'use strict';
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const { performance } = require('perf_hooks');

const arg = (name, fallback) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : fallback; };
const LISTEN = Number(arg('listen')); let UPSTREAM = Number(arg('upstream')); const CONTROL = Number(arg('control'));
const LOG = arg('log', ''); const HOST_HEADER = arg('host-header', '');
for (const [name, value] of [['listen', LISTEN], ['upstream', UPSTREAM], ['control', CONTROL]]) {
  if (!Number.isInteger(value) || value < 1024 || value > 65535) { console.error(`proxy: --${name} must be a port`); process.exit(2); }
}
const now = () => performance.timeOrigin + performance.now();
const entries = []; let seq = 0; let inFlight = 0; let rules = [];
const logStream = LOG ? fs.createWriteStream(LOG, { flags: 'a', mode: 0o600 }) : null;

// records[4]: the server's own cookies are not logged (the session's value as its member's digest); every other cookie
// is logged as the page sent it, so a search word a page put into a cookie reaches the marker scan
function cookieLog(value, memberId) {
  return String(value).split(/;\s*/).map(pair => { const name = pair.split('=', 1)[0];
    if (/^(?:__Host-)?cptstudio_session$/.test(name)) return `${name}=session:${memberId}`;
    return /^(?:__Host-)?cptstudio_(?:csrf|device)$/.test(name) ? `${name}=<redacted>` : pair; }).join('; ');
}

function member(cookie) {
  const match = /(?:^|;\s*)((?:__Host-)?cptstudio_session)=([^;]+)/.exec(cookie || '');
  return match ? crypto.createHash('sha256').update(match[2]).digest('hex').slice(0, 12) : '';
}

function ruleFor(path) {
  const rule = rules.find(r => r.times > 0 && new RegExp(r.match).test(path));
  if (rule) rule.times -= 1;
  return rule || null;
}

const server = http.createServer((req, res) => {
  const entry = { seq: ++seq, t0: now(), tEnd: null, method: req.method, url: req.url, status: 0, bytes: 0, inBytes: 0,
    upstream: UPSTREAM, member: member(req.headers.cookie), rule: null, reqHeaders: {}, resHeaders: {} };
  const headers = { ...req.headers, connection: 'close' };
  if (!/^[0-9a-f]{32}$/.test(headers['x-request-id'] || '')) headers['x-request-id'] = crypto.randomBytes(16).toString('hex');
  if (HOST_HEADER) {
    const own = `http://${req.headers.host}`; const target = `http://${HOST_HEADER}`;
    headers.host = HOST_HEADER;
    for (const name of ['origin', 'referer']) if (headers[name]) headers[name] = headers[name].replace(own, target);
  }
  for (const [k, v] of Object.entries(headers)) entry.reqHeaders[k] = k === 'cookie' ? cookieLog(v, entry.member) : v;
  const rule = ruleFor(req.url);
  if (rule) entry.rule = `${rule.kind}:${rule.ms}`;
  inFlight += 1;
  const body = [];
  req.on('data', chunk => { entry.inBytes += chunk.length; body.push(chunk); });
  req.on('end', () => {
    const send = () => {
      const out = http.request({ host: '127.0.0.1', port: entry.upstream, method: req.method, path: req.url, headers, agent: false }, answer => {
        entry.status = answer.statusCode;
        entry.resHeaders = answer.headers;
        // hop-by-hop headers stay on their hop, as nginx keeps them: gunicorn's `Connection: close` must not close the
        // browser's kept-alive connection to this proxy
        const back = { ...answer.headers, 'x-bench-request-id': headers['x-request-id'] };
        for (const name of ['connection', 'keep-alive', 'transfer-encoding', 'proxy-connection']) delete back[name];
        res.writeHead(answer.statusCode, back);
        answer.on('data', chunk => { entry.bytes += chunk.length; });
        answer.pipe(res);
        answer.on('end', () => finish());
        answer.on('error', () => finish());
      });
      out.on('error', error => {
        entry.status = 502; entry.error = String(error.code || error.message).slice(0, 80);
        if (!res.headersSent) res.writeHead(502, { 'content-type': 'text/plain' });
        res.end('bench proxy: upstream error'); finish();
      });
      out.end(Buffer.concat(body));
    };
    if (rule) setTimeout(send, rule.ms); else send();
  });
  let done = false;
  const finish = () => {
    if (done) return; done = true; inFlight -= 1; entry.tEnd = now();
    entries.push(entry);
    if (logStream) logStream.write(JSON.stringify(entry) + '\n');
  };
  res.on('close', () => { if (!done) { entry.status = entry.status || 499; finish(); } });
});
server.keepAliveTimeout = 5000;

const control = http.createServer((req, res) => {
  const reply = (code, value) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(JSON.stringify(value)); };
  const url = new URL(req.url, 'http://127.0.0.1');
  let raw = '';
  req.on('data', chunk => { raw += chunk; });
  req.on('end', () => {
    let body = {};
    try { body = raw ? JSON.parse(raw) : {}; } catch (error) { reply(400, { error: 'json' }); return; }
    if (req.method === 'GET' && url.pathname === '/log') {
      const since = Number(url.searchParams.get('since') || 0);
      reply(200, { seq, inFlight, entries: entries.filter(e => e.seq > since) }); return;
    }
    if (req.method === 'GET' && url.pathname === '/state') { reply(200, { seq, inFlight, upstream: UPSTREAM, rules }); return; }
    if (req.method === 'POST' && url.pathname === '/upstream') {
      const port = Number(body.port);
      if (!Number.isInteger(port) || port < 1024 || port > 65535) { reply(400, { error: 'port' }); return; }
      UPSTREAM = port; reply(200, { upstream: UPSTREAM }); return;
    }
    if (req.method === 'POST' && url.pathname === '/rule') {
      if (!['delay', 'hold'].includes(body.kind) || typeof body.match !== 'string' || !(body.ms >= 0)) { reply(400, { error: 'rule' }); return; }
      rules.push({ kind: body.kind, match: body.match, ms: Number(body.ms), times: Number(body.times || 1) });
      reply(200, { rules }); return;
    }
    if (req.method === 'POST' && url.pathname === '/clear') { rules = []; reply(200, { rules }); return; }
    reply(404, { error: 'unknown' });
  });
});

let up = 0;
const ready = () => { up += 1; if (up === 2) console.log(`proxy up ${LISTEN} ${CONTROL}`); };
server.listen(LISTEN, '127.0.0.1', ready);
control.listen(CONTROL, '127.0.0.1', ready);
const stop = () => { server.close(); control.close(); if (logStream) logStream.end(() => process.exit(0)); else process.exit(0); };
process.on('SIGTERM', stop);
process.on('SIGINT', stop);
