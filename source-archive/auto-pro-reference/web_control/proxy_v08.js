'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');
const { URL } = require('url');

const ROOT = path.resolve(__dirname, '..');
const CORE_PORT = Number(process.env.AUTO_WEB_CORE_PORT || 18080);
const PUBLIC_PORT = Number(process.env.AUTO_WEB_PORT || 8080);
const HOST = process.env.AUTO_WEB_HOST || '127.0.0.1';
const TOKEN_FILE = path.join(ROOT, 'local_data', 'bridge_token.txt');
const DATA_DIR = path.join(__dirname, 'data');
const USERS_FILE = path.join(DATA_DIR, 'users.json');
const FIRST_LOGIN = path.join(DATA_DIR, 'FIRST_LOGIN.txt');
const TASK_PORT = 8766;
const OPTIONS_PORT = 8767;
const FIXED_ADMIN_USERNAME = 'admin';
const FIXED_ADMIN_PASSWORD = 'sukafe01';

function hashPassword(password, salt = crypto.randomBytes(16).toString('hex')) {
  const hash = crypto.scryptSync(String(password), salt, 64).toString('hex');
  return { salt, hash };
}
function verifyPassword(password, rec) {
  try {
    const got = crypto.scryptSync(String(password), rec.salt, 64);
    const exp = Buffer.from(String(rec.passwordHash || ''), 'hex');
    return got.length === exp.length && crypto.timingSafeEqual(got, exp);
  } catch { return false; }
}
function enforceFixedAdminPassword() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  let users = [];
  try {
    if (fs.existsSync(USERS_FILE)) users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
    if (!Array.isArray(users)) users = [];
  } catch { users = []; }

  let admin = users.find(x => x && x.username === FIXED_ADMIN_USERNAME);
  let changed = false;
  if (!admin) {
    admin = { username: FIXED_ADMIN_USERNAME, role: 'admin', devices: [], enabled: true };
    users.unshift(admin);
    changed = true;
  }
  if (admin.role !== 'admin') { admin.role = 'admin'; changed = true; }
  if (admin.enabled === false) { admin.enabled = true; changed = true; }
  if (!Array.isArray(admin.devices)) { admin.devices = []; changed = true; }
  if (!verifyPassword(FIXED_ADMIN_PASSWORD, admin)) {
    const hp = hashPassword(FIXED_ADMIN_PASSWORD);
    admin.salt = hp.salt;
    admin.passwordHash = hp.hash;
    changed = true;
  }

  if (changed || !fs.existsSync(USERS_FILE)) {
    const tmp = USERS_FILE + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(users, null, 2), 'utf8');
    fs.renameSync(tmp, USERS_FILE);
  }
  // Keep this local-only helper accurate. web_control/data is not source code.
  fs.writeFileSync(FIRST_LOGIN,
    `AUTO KVTM WEB - ADMIN FIXED\r\nUsername: ${FIXED_ADMIN_USERNAME}\r\nPassword: ${FIXED_ADMIN_PASSWORD}\r\n`,
    'utf8');
  console.log(`[AUTH] Fixed admin login: ${FIXED_ADMIN_USERNAME} / ${FIXED_ADMIN_PASSWORD}`);
}

// Do this BEFORE server.js starts, so server.js never gets a chance to create a
// new random admin password when users.json is missing.
enforceFixedAdminPassword();

// Keep the proven v0.6 H.264 server untouched. v0.8.1 is only a very small
// authenticated proxy layer for exact task selection + auxiliary options.
const core = spawn(process.execPath, [path.join(__dirname, 'server.js')], {
  cwd: ROOT,
  windowsHide: true,
  stdio: 'inherit',
  env: { ...process.env, AUTO_WEB_HOST: '127.0.0.1', AUTO_WEB_PORT: String(CORE_PORT) },
});
core.on('exit', code => console.error(`[WEB CORE] stopped: ${code}`));

function readToken(){ try{return fs.readFileSync(TOKEN_FILE,'utf8').trim();}catch{return '';} }
function sameOrigin(req){
  const origin=req.headers.origin; if(!origin)return true;
  try{return new URL(origin).host===req.headers.host;}catch{return false;}
}
function collect(req,limit=1024*1024){return new Promise((resolve,reject)=>{const a=[];let n=0;let done=false;const fail=e=>{if(done)return;done=true;reject(e)};req.on('data',c=>{if(done)return;n+=c.length;if(n>limit)return fail(Error('request too large'));a.push(c)});req.on('end',()=>{if(done)return;done=true;resolve(Buffer.concat(a))});req.on('error',fail);});}
function json(res,code,obj){const b=Buffer.from(JSON.stringify(obj));res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Content-Length':b.length,'Cache-Control':'no-store'});res.end(b);}

function coreJson(req,pathname){
  return new Promise((resolve,reject)=>{
    const r=http.request({host:'127.0.0.1',port:CORE_PORT,path:pathname,method:'GET',headers:{cookie:req.headers.cookie||''},timeout:3500},x=>{
      const a=[];x.on('data',c=>a.push(c));x.on('end',()=>{
        const raw=Buffer.concat(a).toString('utf8');let j={};
        try{j=raw?JSON.parse(raw):{}}catch{return reject(Error(raw||`Core HTTP ${x.statusCode}`))}
        if((x.statusCode||500)>=400)return reject(Object.assign(Error(j.error||`Core HTTP ${x.statusCode}`),{statusCode:x.statusCode}));
        resolve(j);
      });
    });
    r.on('timeout',()=>r.destroy(Error('Web core timeout')));r.on('error',reject);r.end();
  });
}
async function coreAuth(req){try{await coreJson(req,'/api/me');return true}catch{return false}}
async function coreAllowsDevice(req,deviceId){
  try{const r=await coreJson(req,'/api/devices');return Array.isArray(r.devices)&&r.devices.some(d=>String(d.id)===String(deviceId));}catch{return false}
}

function bridgeCall(port,method,pathname,payload=null,timeout=6000){
  return new Promise((resolve,reject)=>{
    const token=readToken();
    if(!token)return reject(Error('Launcher bridge chưa chạy. Hãy đóng AUTO cũ rồi mở RUN_LOCAL.bat v0.8.'));
    const body=payload==null?null:Buffer.from(JSON.stringify(payload));
    const r=http.request({host:'127.0.0.1',port,path:pathname,method,timeout,headers:{'X-Auto-Bridge-Token':token,...(body?{'Content-Type':'application/json','Content-Length':body.length}:{})}},x=>{
      const a=[];x.on('data',c=>a.push(c));x.on('end',()=>{
        const raw=Buffer.concat(a).toString('utf8');let j={};
        try{j=raw?JSON.parse(raw):{}}catch{return reject(Error(raw||`Bridge HTTP ${x.statusCode}`))}
        if((x.statusCode||500)>=400||j.ok===false)return reject(Error(j.error||`Bridge HTTP ${x.statusCode}`));
        resolve(j);
      });
    });
    r.on('timeout',()=>r.destroy(Error(`Launcher bridge ${port} timeout`)));r.on('error',reject);if(body)r.write(body);r.end();
  });
}

async function handleOptions(req,res){
  if(!(await coreAuth(req)))return json(res,401,{error:'unauthorized'});
  if(req.method==='POST'&&!sameOrigin(req))return json(res,403,{error:'origin rejected'});
  try{
    if(req.method==='GET'){
      const r=await bridgeCall(OPTIONS_PORT,'GET','/options');
      return json(res,200,{options:r.options||[],source:r.source,diagnostics:r.diagnostics||{}});
    }
    if(req.method==='POST'){
      const raw=await collect(req,65536);let b={};
      try{b=raw.length?JSON.parse(raw):{}}catch{return json(res,400,{error:'JSON không hợp lệ'})}
      const r=await bridgeCall(OPTIONS_PORT,'POST','/options',{key:String(b.key||''),enabled:!!b.enabled});
      return json(res,200,r);
    }
    return json(res,405,{error:'method not allowed'});
  }catch(e){return json(res,500,{error:e.message});}
}

async function handleExactStart(req,res){
  if(req.method!=='POST')return json(res,405,{error:'method not allowed'});
  if(!sameOrigin(req))return json(res,403,{error:'origin rejected'});
  if(!(await coreAuth(req)))return json(res,401,{error:'unauthorized'});
  try{
    const raw=await collect(req,65536);let b={};
    try{b=raw.length?JSON.parse(raw):{}}catch{return json(res,400,{error:'JSON không hợp lệ'})}
    const deviceId=String(b.device_id||'').trim();
    if(!deviceId)return json(res,400,{error:'device_id required'});
    if(!(await coreAllowsDevice(req,deviceId)))return json(res,403,{error:'device denied'});

    const optionIndex=Number(b.option_index);
    const functionId=Number(b.function_id);
    const requestedLabel=String(b.label||'').trim();
    const live=await bridgeCall(TASK_PORT,'GET','/functions',null,5000);
    const rows=Array.isArray(live.functions)?live.functions:[];

    // Resolve against FUNCTION_OPTIONS in the running launcher, not the static
    // recovered JSON. This guarantees the browser selection is the item STARTed.
    let opt=null;
    if(Number.isFinite(optionIndex))opt=rows.find(x=>Number(x.option_index)===optionIndex&&(!requestedLabel||String(x.label)===requestedLabel));
    if(!opt&&Number.isFinite(functionId)&&requestedLabel)opt=rows.find(x=>Number(x.id)===functionId&&String(x.label)===requestedLabel);
    if(!opt&&Number.isFinite(optionIndex))opt=rows.find(x=>Number(x.option_index)===optionIndex);
    if(!opt)return json(res,400,{error:'Chức năng vừa chọn không còn tồn tại trong FUNCTION_OPTIONS thật. Bấm Tải lại ID AUTO rồi chọn lại.'});

    const r=await bridgeCall(TASK_PORT,'POST','/start',{
      device_id:deviceId,
      function_id:Number(opt.id),
      label:String(opt.label),
    },18000);
    return json(res,200,{...r,selected_option_index:Number(opt.option_index),selected_label:String(opt.label),source:'REAL_LAUNCHER_FUNCTION_OPTIONS'});
  }catch(e){return json(res,500,{error:e.message});}
}

async function handlePasswordChange(req,res){
  // The main admin credential is intentionally fixed by owner request.
  try {
    const current = await coreJson(req, '/api/me');
    if (current && current.username === FIXED_ADMIN_USERNAME) {
      return json(res, 409, { error:`Mật khẩu admin được cố định là ${FIXED_ADMIN_PASSWORD}` });
    }
  } catch {}
  return proxy(req,res);
}

function proxy(req,res){
  const headers={...req.headers,host:`127.0.0.1:${CORE_PORT}`};
  delete headers.connection;
  const up=http.request({host:'127.0.0.1',port:CORE_PORT,path:req.url,method:req.method,headers},ur=>{
    const h={...ur.headers}; delete h.connection; delete h['keep-alive']; delete h['transfer-encoding'];
    res.writeHead(ur.statusCode||502,h); ur.pipe(res);
  });
  up.on('error',e=>{if(!res.headersSent)json(res,502,{error:`Web core chưa sẵn sàng: ${e.message}`});else res.end();});
  req.on('aborted',()=>up.destroy());
  res.on('close',()=>{if(!up.destroyed)up.destroy();});
  req.pipe(up);
}

const server=http.createServer((req,res)=>{
  const pathname=new URL(req.url,`http://${req.headers.host||'localhost'}`).pathname;
  if(pathname==='/api/options')return handleOptions(req,res);
  if(pathname==='/api/auto/start-v08')return handleExactStart(req,res);
  if(pathname==='/api/account/password' && req.method==='POST')return handlePasswordChange(req,res);
  return proxy(req,res);
});
server.keepAliveTimeout=65000;
server.headersTimeout=70000;
server.on('error',err=>{
  if(err&&err.code==='EADDRINUSE'){
    console.error(`\n[ERROR] Port ${PUBLIC_PORT} đang bị Web AUTO cũ chiếm. Đóng cửa sổ AUTO KVTM WEB cũ rồi chạy lại RUN_WEB.bat.\n`);
  } else console.error(err);
  try{core.kill();}catch{}
  process.exit(1);
});
setTimeout(()=>server.listen(PUBLIC_PORT,HOST,()=>console.log(`AUTO KVTM WEB v0.8.1: http://${HOST}:${PUBLIC_PORT} (core ${CORE_PORT})`)),350);
function shutdown(){try{core.kill();}catch{}try{server.close();}catch{}}
process.on('SIGINT',()=>{shutdown();process.exit(0)});
process.on('SIGTERM',()=>{shutdown();process.exit(0)});
process.on('exit',shutdown);