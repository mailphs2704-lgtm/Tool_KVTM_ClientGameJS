'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn, execFile } = require('child_process');
const { URL } = require('url');

const WEB = __dirname;
const ROOT = path.resolve(WEB, '..');
const PUBLIC = path.join(WEB, 'public');
const DATA = path.join(WEB, 'data');
const USERS_FILE = path.join(DATA, 'users.json');
const FIRST_LOGIN = path.join(DATA, 'FIRST_LOGIN.txt');
const CATALOG_FILE = path.join(WEB, 'function_catalog.json');
const BRIDGE_TOKEN_FILE = path.join(ROOT, 'local_data', 'bridge_token.txt');
const ADB = path.join(ROOT, 'platform-tools', 'adb.exe');
const HOST = process.env.AUTO_WEB_HOST || '127.0.0.1';
const PORT = Number(process.env.AUTO_WEB_PORT || 8080);
const BRIDGE_HOST = '127.0.0.1';
const BRIDGE_PORT = 8766;
const sessions = new Map();
const loginAttempts = new Map();
const logs = new Map();
const maxLogs = 600;

fs.mkdirSync(DATA, { recursive: true });

function hashPassword(password, salt = crypto.randomBytes(16).toString('hex')) {
  const hash = crypto.scryptSync(String(password), salt, 64).toString('hex');
  return { salt, hash };
}
function verifyPassword(password, rec) {
  try {
    const got = crypto.scryptSync(String(password), rec.salt, 64);
    const exp = Buffer.from(rec.passwordHash, 'hex');
    return got.length === exp.length && crypto.timingSafeEqual(got, exp);
  } catch { return false; }
}
function loadUsers() {
  if (!fs.existsSync(USERS_FILE)) {
    const password = crypto.randomBytes(9).toString('base64url');
    const hp = hashPassword(password);
    const users = [{ username: 'admin', role: 'admin', salt: hp.salt, passwordHash: hp.hash, devices: [], enabled: true }];
    fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2), 'utf8');
    fs.writeFileSync(FIRST_LOGIN, `AUTO KVTM WEB - FIRST LOGIN\r\nUsername: admin\r\nPassword: ${password}\r\n\r\nĐổi mật khẩu ngay sau khi đăng nhập.\r\n`, 'utf8');
    console.log('\n=== FIRST LOGIN ===');
    console.log('Username: admin');
    console.log('Password:', password);
    console.log('Saved:', FIRST_LOGIN, '\n');
  }
  return JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
}
function saveUsers(users) {
  const tmp = USERS_FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(users, null, 2), 'utf8');
  fs.renameSync(tmp, USERS_FILE);
}
loadUsers();

function parseCookies(req) {
  const out = {};
  for (const part of String(req.headers.cookie || '').split(';')) {
    const idx = part.indexOf('=');
    if (idx > 0) out[part.slice(0, idx).trim()] = decodeURIComponent(part.slice(idx + 1).trim());
  }
  return out;
}
function currentUser(req) {
  const sid = parseCookies(req).sid;
  const sess = sid && sessions.get(sid);
  if (!sess || sess.expires < Date.now()) return null;
  return loadUsers().find(u => u.username === sess.username && u.enabled !== false) || null;
}
function json(res, code, obj) {
  const body = Buffer.from(JSON.stringify(obj));
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': body.length, 'Cache-Control': 'no-store' });
  res.end(body);
}
function text(res, code, body) {
  body = Buffer.from(String(body));
  res.writeHead(code, { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Length': body.length, 'Cache-Control': 'no-store' });
  res.end(body);
}
function bodyJson(req) {
  return new Promise((resolve, reject) => {
    const chunks = []; let total = 0;
    req.on('data', c => { total += c.length; if (total > 1024 * 1024) req.destroy(); else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}
function sameOrigin(req) {
  const origin = req.headers.origin;
  if (!origin) return true;
  try { return new URL(origin).host === req.headers.host; } catch { return false; }
}
function allowedDevice(user, deviceId) {
  return user.role === 'admin' || (user.devices || []).includes(deviceId);
}
function pushLog(deviceId, msg, type = 'log') {
  if (!deviceId) return;
  const arr = logs.get(deviceId) || [];
  arr.push({ ts: new Date().toISOString(), type, message: String(msg) });
  if (arr.length > maxLogs) arr.splice(0, arr.length - maxLogs);
  logs.set(deviceId, arr);
}

// ----- Exact function catalog recovered from the launcher's FUNCTION_OPTIONS -----
function functionCatalog() {
  try { return JSON.parse(fs.readFileSync(CATALOG_FILE, 'utf8')); }
  catch { return []; }
}

// ----- REAL launcher bridge -----
// This is deliberately localhost-only. The bridge runs INSIDE local_launcher.py
// and exposes the same TaskManager instance that the visible launcher is using.
function bridgeToken() {
  try { return fs.readFileSync(BRIDGE_TOKEN_FILE, 'utf8').trim(); }
  catch { return ''; }
}
function bridgeCall(method, endpoint, payload = null, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const token = bridgeToken();
    if (!token) return reject(new Error('Launcher bridge chưa chạy. Hãy đóng launcher cũ và chạy RUN_LOCAL.bat bản mới.'));
    const body = payload == null ? null : Buffer.from(JSON.stringify(payload));
    const req = http.request({
      host: BRIDGE_HOST,
      port: BRIDGE_PORT,
      path: endpoint,
      method,
      timeout,
      headers: {
        'X-Auto-Bridge-Token': token,
        ...(body ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {}),
      },
    }, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        let data = {};
        try { data = raw ? JSON.parse(raw) : {}; } catch { return reject(new Error(raw || `Bridge HTTP ${res.statusCode}`)); }
        if ((res.statusCode || 500) >= 400 || data.ok === false) reject(new Error(data.error || `Bridge HTTP ${res.statusCode}`));
        else resolve(data);
      });
    });
    req.on('timeout', () => req.destroy(new Error('Launcher bridge timeout')));
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

// ----- ADB helpers -----
function adb(args, encoding = 'utf8', maxBuffer = 32 * 1024 * 1024) {
  return new Promise((resolve, reject) => execFile(ADB, args, { cwd: ROOT, encoding, windowsHide: true, maxBuffer },
    (err, stdout, stderr) => err ? reject(new Error(String(stderr || err.message).trim())) : resolve(stdout)));
}
async function listAdbDevices() {
  const out = await adb(['devices', '-l']);
  return String(out).split(/\r?\n/).slice(1).map(x => x.trim()).filter(Boolean).map(line => {
    const parts = line.split(/\s+/); const id = parts[0]; const state = parts[1] || 'unknown';
    const meta = {}; for (const p of parts.slice(2)) { const i = p.indexOf(':'); if (i > 0) meta[p.slice(0, i)] = p.slice(i + 1); }
    return { id, state, model: meta.model || '', product: meta.product || '', device: meta.device || '', source:'adb' };
  });
}
async function listDevices() {
  // Merge the bundled ADB view with the exact IDs already loaded by the
  // running launcher. This fixes cases where the GUI sees LD/MEmu aliases but
  // the web-side `adb devices -l` output is incomplete for a moment.
  const [adbResult, launcherResult] = await Promise.allSettled([
    listAdbDevices(),
    bridgeCall('GET','/devices',null,3500),
  ]);
  const map = new Map();
  if (launcherResult.status === 'fulfilled') {
    for (const d of (launcherResult.value.devices || [])) {
      if (!d || !d.id) continue;
      map.set(String(d.id), { id:String(d.id), state:d.state || 'launcher', model:'', product:'', device:'', display_name:d.display_name || '', source:'launcher' });
    }
  }
  if (adbResult.status === 'fulfilled') {
    for (const d of adbResult.value) {
      const prev = map.get(String(d.id)) || {};
      map.set(String(d.id), { ...prev, ...d, display_name:prev.display_name || d.display_name || '', source:prev.source ? 'launcher+adb' : 'adb' });
    }
  }
  if (!map.size) {
    const errors = [];
    if (adbResult.status === 'rejected') errors.push(`ADB: ${adbResult.reason?.message || adbResult.reason}`);
    if (launcherResult.status === 'rejected') errors.push(`Launcher: ${launcherResult.reason?.message || launcherResult.reason}`);
    if (errors.length) throw new Error(errors.join(' | '));
  }
  return [...map.values()].sort((a,b)=>String(a.display_name||a.id).localeCompare(String(b.display_name||b.id),'vi'));
}
function parseWmSize(s) {
  const text = String(s || '');
  const over = text.match(/Override size:\s*(\d+)x(\d+)/i);
  const phys = text.match(/Physical size:\s*(\d+)x(\d+)/i);
  const m = over || phys || text.match(/(\d+)x(\d+)/);
  return m ? { width: Number(m[1]), height: Number(m[2]), overridden: !!over } : { width: null, height: null, overridden: false };
}
function parseWmDensity(s) {
  const text = String(s || '');
  const over = text.match(/Override density:\s*(\d+)/i);
  const phys = text.match(/Physical density:\s*(\d+)/i);
  const m = over || phys || text.match(/(\d+)/);
  return { density: m ? Number(m[1]) : null, overridden: !!over };
}
async function displayInfo(id) {
  const [s, d] = await Promise.all([adb(['-s', id, 'shell', 'wm', 'size']), adb(['-s', id, 'shell', 'wm', 'density'])]);
  return { ...parseWmSize(s), ...parseWmDensity(d), rawSize: String(s).trim(), rawDensity: String(d).trim() };
}
async function setDisplay(id, width, height, density, reset = false) {
  if (reset) {
    await adb(['-s', id, 'shell', 'wm', 'size', 'reset']);
    await adb(['-s', id, 'shell', 'wm', 'density', 'reset']);
    return displayInfo(id);
  }
  width = Math.round(Number(width)); height = Math.round(Number(height)); density = Math.round(Number(density));
  if (!(width >= 480 && width <= 3000 && height >= 480 && height <= 3000 && density >= 120 && density <= 640)) throw new Error('Display không hợp lệ');
  await adb(['-s', id, 'shell', 'wm', 'size', `${width}x${height}`]);
  await adb(['-s', id, 'shell', 'wm', 'density', String(density)]);
  return displayInfo(id);
}

// ----- High-quality passive Live View -----
// Android's hardware screen recorder sends H.264 continuously. The browser
// buffers ~1 second and decodes with WebCodecs, which is much smoother than
// repeatedly replacing PNG screenshots. No tap/swipe endpoint is exposed.
function streamH264(req, res, deviceId, options = {}) {
  let proc = null;
  let closed = false;
  const requestedSize = Math.round(Number(options.size || 720));
  const requestedBitrate = Math.round(Number(options.bitrate || 3200000));
  const size = Math.max(480, Math.min(1000, requestedSize));
  const bitrate = Math.max(1000000, Math.min(6000000, requestedBitrate));
  const stop = () => {
    closed = true;
    if (proc) { try { proc.kill(); } catch {} proc = null; }
  };
  req.on('close', stop); res.on('close', stop);
  res.writeHead(200, {
    'Content-Type': 'application/octet-stream',
    'Cache-Control': 'no-store, no-cache, must-revalidate',
    'Pragma': 'no-cache',
    'Connection': 'keep-alive',
    'X-Content-Type-Options': 'nosniff',
    'X-KVTM-Stream-Size': String(size),
    'X-KVTM-Stream-Bitrate': String(bitrate),
  });

  // Downscale only the VIEW stream. The emulator itself remains at its configured
  // 1000x1000 / 240 DPI. A 720/640 H.264 stream is substantially cheaper for the
  // emulator encoder and browser decoder, which raises real FPS and prevents lag.
  proc = spawn(ADB, ['-s', deviceId, 'exec-out', 'screenrecord', '--output-format=h264', '--size', `${size}x${size}`, '--bit-rate', String(bitrate), '--time-limit', '175', '-'], {
    cwd: ROOT, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
  });
  proc.stdout.on('data', chunk => {
    if (closed || res.writableEnded) return;
    // Respect HTTP backpressure. Node will stop accepting more chunks until drain,
    // instead of growing an unbounded memory/network queue.
    if (!res.write(chunk) && proc?.stdout) proc.stdout.pause();
  });
  res.on('drain', () => { if (!closed && proc?.stdout) proc.stdout.resume(); });
  proc.stderr.on('data', chunk => {
    const msg = chunk.toString('utf8').trim();
    if (msg) pushLog(deviceId, `Live H264 ${size}px/${Math.round(bitrate/100000)/10}Mbps: ${msg}`, 'debug');
  });
  proc.on('exit', code => {
    proc = null;
    if (!closed && !res.writableEnded) res.end();
  });
  proc.on('error', err => {
    pushLog(deviceId, `Live H264 lỗi: ${err.message}`, 'error');
    if (!closed && !res.writableEnded) res.end();
  });
}

function mimeOf(file) {
  const ext = path.extname(file).toLowerCase();
  return ({ '.html':'text/html; charset=utf-8', '.js':'application/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.svg':'image/svg+xml' })[ext] || 'application/octet-stream';
}
function serveStatic(req, res, pathname) {
  let rel = pathname === '/' ? 'index.html' : pathname.slice(1);
  rel = path.normalize(rel).replace(/^([.][.][/\\])+/, '');
  const file = path.join(PUBLIC, rel);
  if (!file.startsWith(PUBLIC) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return false;
  const data = fs.readFileSync(file);
  res.writeHead(200, { 'Content-Type': mimeOf(file), 'Content-Length': data.length, 'Cache-Control': 'no-store, no-cache, must-revalidate' });
  res.end(data); return true;
}

async function route(req, res) {
  const u = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const p = u.pathname;

  if (p === '/api/login' && req.method === 'POST') {
    const ip = req.socket.remoteAddress || 'unknown';
    const rec = loginAttempts.get(ip) || { n:0, until:0 };
    if (rec.until > Date.now()) return json(res, 429, { error:'Thử lại sau ít phút' });
    const b = await bodyJson(req); const user = loadUsers().find(x => x.username === String(b.username || '').trim() && x.enabled !== false);
    if (!user || !verifyPassword(b.password || '', user)) {
      rec.n++; if (rec.n >= 8) { rec.n = 0; rec.until = Date.now() + 5*60*1000; } loginAttempts.set(ip, rec);
      return json(res, 401, { error:'Sai tài khoản hoặc mật khẩu' });
    }
    loginAttempts.delete(ip);
    const sid = crypto.randomBytes(32).toString('base64url'); sessions.set(sid, { username:user.username, expires:Date.now()+7*24*3600*1000 });
    res.setHeader('Set-Cookie', `sid=${sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${7*24*3600}`);
    return json(res, 200, { ok:true, username:user.username, role:user.role });
  }
  if (p === '/api/logout' && req.method === 'POST') {
    const sid = parseCookies(req).sid; if (sid) sessions.delete(sid);
    res.setHeader('Set-Cookie','sid=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'); return json(res,200,{ok:true});
  }
  if (p === '/api/me') {
    const user = currentUser(req); if (!user) return json(res,401,{error:'unauthorized'});
    return json(res,200,{ username:user.username, role:user.role, devices:user.devices || [] });
  }

  const user = currentUser(req);
  if (p.startsWith('/api/') && !user) return json(res,401,{error:'unauthorized'});
  if (req.method === 'POST' && !sameOrigin(req)) return json(res,403,{error:'origin rejected'});

  if (p === '/api/devices' && req.method === 'GET') {
    try { const all = await listDevices(); return json(res,200,{ devices:user.role==='admin' ? all : all.filter(d => allowedDevice(user,d.id)) }); }
    catch(e){ return json(res,500,{error:e.message}); }
  }
  if (p === '/api/engine' && req.method === 'GET') {
    try { return json(res,200,await bridgeCall('GET','/health',null,3500)); }
    catch(e){ return json(res,503,{connected:false,source:'REAL_LAUNCHER_TASK_MANAGER',error:e.message}); }
  }
  if (p === '/api/functions' && req.method === 'GET') {
    let rows = [];
    let source = 'static-recovered-catalog';
    try {
      const live = await bridgeCall('GET','/functions',null,3500);
      if (Array.isArray(live.functions) && live.functions.length) { rows = live.functions; source = 'REAL_LAUNCHER_FUNCTION_OPTIONS'; }
    } catch {}
    if (!rows.length) rows = functionCatalog();
    const ids = rows.map(x=>Number(x.id)).filter(Number.isFinite);
    return json(res,200,{functions:rows,meta:{source,exact_gui_names:true,option_count:rows.length,method_count:new Set(ids).size,min_id:ids.length?Math.min(...ids):null,max_id:ids.length?Math.max(...ids):null,duplicate_ids:rows.length-new Set(ids).size}});
  }
  if (p === '/api/status' && req.method === 'GET') {
    try {
      const r = await bridgeCall('GET','/status',null,3500);
      const status = Array.isArray(r.status) ? r.status.filter(x => allowedDevice(user,x.device_id)) : [];
      return json(res,200,{status,source:'REAL_LAUNCHER_TASK_MANAGER'});
    } catch(e){ return json(res,503,{error:e.message,status:[]}); }
  }
  if (p === '/api/logs' && req.method === 'GET') {
    const deviceId = u.searchParams.get('device'); if (!deviceId || !allowedDevice(user,deviceId)) return json(res,403,{error:'device denied'});
    return json(res,200,{logs:logs.get(deviceId)||[]});
  }
  if (p === '/api/auto/start' && req.method === 'POST') {
    const b=await bodyJson(req); if(!allowedDevice(user,b.device_id)) return json(res,403,{error:'device denied'});
    const catalog=functionCatalog();
    const opt = Number.isFinite(Number(b.option_index)) ? catalog.find(x=>Number(x.option_index)===Number(b.option_index)) : catalog.find(x=>Number(x.id)===Number(b.function_id));
    if(!opt) return json(res,400,{error:'Không tìm thấy chức năng trong catalog'});
    try {
      const r=await bridgeCall('POST','/start',{device_id:b.device_id,function_id:Number(opt.id),label:opt.label},18000);
      pushLog(b.device_id,`Web ${user.username} START #${opt.id} · ${opt.label}`,'audit');
      return json(res,200,r);
    } catch(e){ pushLog(b.device_id,`START lỗi: ${e.message}`,'error'); return json(res,500,{error:e.message}); }
  }
  if (p === '/api/auto/stop' && req.method === 'POST') {
    const b=await bodyJson(req); if(!allowedDevice(user,b.device_id)) return json(res,403,{error:'device denied'});
    try {
      const r=await bridgeCall('POST','/stop',{device_id:b.device_id},7000);
      pushLog(b.device_id,`Web ${user.username} STOP task thật trong launcher`,'audit');
      return json(res,200,r);
    } catch(e){ return json(res,500,{error:e.message}); }
  }

  const mH264 = p.match(/^\/api\/device\/(.+)\/h264$/);
  if (mH264 && req.method === 'GET') {
    const id=decodeURIComponent(mH264[1]); if(!allowedDevice(user,id)) return json(res,403,{error:'device denied'});
    return streamH264(req,res,id,{size:u.searchParams.get('size'),bitrate:u.searchParams.get('bitrate')});
  }
  const mShot = p.match(/^\/api\/device\/(.+)\/screenshot$/);
  if (mShot && req.method === 'GET') {
    const id=decodeURIComponent(mShot[1]); if(!allowedDevice(user,id)) return json(res,403,{error:'device denied'});
    try {
      const buf=await adb(['-s',id,'exec-out','screencap','-p'], null, 24*1024*1024);
      res.writeHead(200,{'Content-Type':'image/png','Cache-Control':'no-store','Content-Length':buf.length}); return res.end(buf);
    } catch(e){ return text(res,503,e.message); }
  }
  const mDisplay = p.match(/^\/api\/device\/(.+)\/display$/);
  if (mDisplay) {
    const id=decodeURIComponent(mDisplay[1]); if(!allowedDevice(user,id)) return json(res,403,{error:'device denied'});
    try {
      if(req.method==='GET') return json(res,200,{display:await displayInfo(id)});
      if(req.method==='POST') {
        const b=await bodyJson(req); const info=await setDisplay(id,b.width,b.height,b.density,!!b.reset);
        pushLog(id,b.reset?`Web ${user.username}: reset display`:`Web ${user.username}: display ${info.width}x${info.height} @ ${info.density} DPI`,'audit');
        return json(res,200,{ok:true,display:info});
      }
    } catch(e){ return json(res,500,{error:e.message}); }
  }

  if (p === '/api/admin/users' && user.role === 'admin') {
    if (req.method === 'GET') return json(res,200,{users:loadUsers().map(({passwordHash,salt,...x})=>x)});
    if (req.method === 'POST') {
      const b=await bodyJson(req); const username=String(b.username||'').trim(); const password=String(b.password||'');
      if(!/^[A-Za-z0-9_.-]{3,32}$/.test(username) || password.length<8) return json(res,400,{error:'Username 3-32 ký tự; password tối thiểu 8 ký tự'});
      const users=loadUsers(); if(users.some(x=>x.username===username)) return json(res,409,{error:'Tài khoản đã tồn tại'});
      const hp=hashPassword(password); users.push({username,role:b.role==='admin'?'admin':'user',salt:hp.salt,passwordHash:hp.hash,devices:Array.isArray(b.devices)?b.devices:[],enabled:true}); saveUsers(users); return json(res,200,{ok:true});
    }
    if (req.method === 'PUT') {
      const b=await bodyJson(req); const users=loadUsers(); const x=users.find(v=>v.username===b.username); if(!x) return json(res,404,{error:'not found'});
      if(Array.isArray(b.devices)) x.devices=b.devices; if(typeof b.enabled==='boolean') x.enabled=b.enabled;
      if(b.password){ if(String(b.password).length<8) return json(res,400,{error:'password >= 8'}); const hp=hashPassword(b.password); x.salt=hp.salt; x.passwordHash=hp.hash; }
      saveUsers(users); return json(res,200,{ok:true});
    }
  }
  if (p === '/api/account/password' && req.method === 'POST') {
    const b=await bodyJson(req); if(String(b.password||'').length<8) return json(res,400,{error:'Mật khẩu tối thiểu 8 ký tự'});
    const users=loadUsers(); const x=users.find(v=>v.username===user.username); const hp=hashPassword(b.password); x.salt=hp.salt; x.passwordHash=hp.hash; saveUsers(users); return json(res,200,{ok:true});
  }

  if (!p.startsWith('/api/') && serveStatic(req,res,p)) return;
  json(res,404,{error:'not found'});
}

const server = http.createServer((req,res)=>route(req,res).catch(e=>{console.error(e); if(!res.headersSent) json(res,500,{error:e.message}); else res.end();}));
server.keepAliveTimeout = 65000;
server.headersTimeout = 70000;
server.listen(PORT,HOST,()=>console.log(`AUTO KVTM WEB v0.6 running at http://${HOST}:${PORT}`));
