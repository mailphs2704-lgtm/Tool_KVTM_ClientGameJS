'use strict';

const http = require('http');
const { URL } = require('url');

const HOST = '127.0.0.1';
const PORT = Number(process.env.AUTO_PUBLIC_GATEWAY_PORT || 8081);
const WEB_PROXY_HOST = '127.0.0.1';
const WEB_PROXY_PORT = Number(process.env.AUTO_WEB_PORT || 8080);
const CORE_HOST = '127.0.0.1';
const CORE_PORT = Number(process.env.AUTO_WEB_CORE_PORT || 18080);

const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function parseOrigin(value) {
  if (!value) return null;
  try { return new URL(value); } catch { return null; }
}

function isAllowedBrowserOrigin(value) {
  const u = parseOrigin(value);
  if (!u) return false;
  const h = String(u.hostname || '').toLowerCase();
  if ((h === '127.0.0.1' || h === 'localhost') && (u.protocol === 'http:' || u.protocol === 'https:')) return true;
  return u.protocol === 'https:' && h.endsWith('.trycloudflare.com');
}

function reject(res, message = 'public origin rejected') {
  const body = Buffer.from(JSON.stringify({ error: message }));
  res.writeHead(403, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': body.length,
    'cache-control': 'no-store',
  });
  res.end(body);
}

// These routes exist only in proxy_v10.js. Everything else should go straight
// to server.js on 18080. Routing normal APIs + H264 directly to the core avoids
// a second Host/Origin rewrite and also removes one proxy hop from Live View.
function needsOuterWebProxy(pathname) {
  return pathname === '/api/options' ||
    pathname === '/api/options/settings' ||
    pathname === '/api/function-actions' ||
    pathname === '/api/auto/start-v08' ||
    pathname === '/api/account/password';
}

const server = http.createServer((req, res) => {
  const method = String(req.method || 'GET').toUpperCase();
  const browserOrigin = req.headers.origin;

  // GET/navigation/media requests commonly omit Origin. Mutating browser calls
  // must carry an allowed Origin so an unrelated website cannot POST into AUTO.
  if (browserOrigin) {
    if (!isAllowedBrowserOrigin(browserOrigin)) return reject(res);
  } else if (MUTATING.has(method)) {
    return reject(res, 'public origin required');
  }

  let pathname = '/';
  try { pathname = new URL(req.url, 'http://gateway.local').pathname; } catch {}

  const viaOuterProxy = needsOuterWebProxy(pathname);
  const targetHost = viaOuterProxy ? WEB_PROXY_HOST : CORE_HOST;
  const targetPort = viaOuterProxy ? WEB_PROXY_PORT : CORE_PORT;
  const targetOrigin = `http://${targetHost}:${targetPort}`;

  const headers = { ...req.headers };
  headers.host = `${targetHost}:${targetPort}`;
  if (browserOrigin) headers.origin = targetOrigin;
  headers['x-kvtm-public-gateway'] = '1';
  headers['x-kvtm-public-origin'] = browserOrigin || '';
  delete headers.connection;

  const up = http.request({
    host: targetHost,
    port: targetPort,
    method,
    path: req.url,
    headers,
  }, ur => {
    const out = { ...ur.headers };
    delete out.connection;
    delete out['keep-alive'];
    out['x-kvtm-gateway-target'] = viaOuterProxy ? 'web-proxy-8080' : 'web-core-18080';
    res.writeHead(ur.statusCode || 502, out);
    ur.pipe(res);
  });

  up.on('error', err => {
    if (!res.headersSent) {
      const body = Buffer.from(JSON.stringify({ error: `local web unavailable: ${err.message}` }));
      res.writeHead(502, {
        'content-type': 'application/json; charset=utf-8',
        'content-length': body.length,
        'cache-control': 'no-store',
      });
      res.end(body);
    } else {
      res.end();
    }
  });

  req.on('aborted', () => up.destroy());
  res.on('close', () => {
    if (!up.destroyed) up.destroy();
  });
  req.pipe(up);
});

server.keepAliveTimeout = 65000;
server.headersTimeout = 70000;
server.listen(PORT, HOST, () => {
  console.log(`AUTO KVTM PUBLIC GATEWAY v3: http://${HOST}:${PORT}`);
  console.log(` -> normal/static/H264: http://${CORE_HOST}:${CORE_PORT}`);
  console.log(` -> options/function actions/exact start: http://${WEB_PROXY_HOST}:${WEB_PROXY_PORT}`);
  console.log(' -> allowed browser Origin: https://*.trycloudflare.com');
});

function shutdown() {
  try { server.close(); } catch {}
}
process.on('SIGINT', () => { shutdown(); process.exit(0); });
process.on('SIGTERM', () => { shutdown(); process.exit(0); });
