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
const SETTINGS_PORT = 8768;
const FUNCTION_ACTIONS_PORT = 8769;
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
  fs.mkdirSync(DATA_DIR, { recursive:true });
  let users=[];
  try { if(fs.existsSync(USERS_FILE)) users=JSON.parse(fs.readFileSync(USERS_FILE,'utf8')); if(!Array.isArray(users))users=[]; } catch { users=[]; }
  let admin=users.find(x=>x&&x.username===FIXED_ADMIN_USERNAME), changed=false;
  if(!admin){admin={username:FIXED_ADMIN_USERNAME,role:'admin',devices:[],enabled:true};users.unshift(admin);changed=true;}
  if(admin.role!=='admin'){admin.role='admin';changed=true;}
  if(admin.enabled===false){admin.enabled=true;changed=true;}
  if(!Array.isArray(admin.devices)){admin.devices=[];changed=true;}
  if(!verifyPassword(FIXED_ADMIN_PASSWORD,admin)){const hp=hashPassword(FIXED_ADMIN_PASSWORD);admin.salt=hp.salt;admin.passwordHash=hp.hash;changed=true;}
  if(changed||!fs.existsSync(USERS_FILE)){const tmp=USERS_FILE+'.tmp';fs.writeFileSync(tmp,JSON.stringify(users,null,2),'utf8');fs.renameSync(tmp,USERS_FILE);}
  fs.writeFileSync(FIRST_LOGIN,`AUTO KVTM WEB - ADMIN FIXED\r\nUsername: ${FIXED_ADMIN_USERNAME}\r\nPassword: ${FIXED_ADMIN_PASSWORD}\r\n`,'utf8');
  console.log(`[AUTH] Fixed admin login: ${FIXED_ADMIN_USERNAME} / ${FIXED_ADMIN_PASSWORD}`);
}
enforceFixedAdminPassword();

// Keep server.js / the proven v0.6 H.264 path untouched. v0.10 adds only
// authenticated localhost bridge routes around it.
const core=spawn(process.execPath,[path.join(__dirname,'server.js')],{
  cwd:ROOT,windowsHide:true,stdio:'inherit',
  env:{...process.env,AUTO_WEB_HOST:'127.0.0.1',AUTO_WEB_PORT:String(CORE_PORT)},
});
core.on('exit',code=>console.error(`[WEB CORE] stopped: ${code}`));

function readToken(){try{return fs.readFileSync(TOKEN_FILE,'utf8').trim();}catch{return '';}}
function sameOrigin(req){const origin=req.headers.origin;if(!origin)return true;try{return new URL(origin).host===req.headers.host;}catch{return false;}}
function collect(req,limit=1024*1024){return new Promise((resolve,reject)=>{const chunks=[];let n=0,done=false;const fail=e=>{if(done)return;done=true;reject(e)};req.on('data',c=>{if(done)return;n+=c.length;if(n>limit)return fail(Error('request too large'));chunks.push(c)});req.on('end',()=>{if(done)return;done=true;resolve(Buffer.concat(chunks))});req.on('error',fail);});}
function json(res,code,obj){const b=Buffer.from(JSON.stringify(obj));res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Content-Length':b.length,'Cache-Control':'no-store'});res.end(b);}
function parseBody(raw){if(!raw||!raw.length)return {};try{return JSON.parse(raw.toString('utf8'));}catch{throw Error('JSON không hợp lệ');}}

function coreJson(req,pathname){return new Promise((resolve,reject)=>{const r=http.request({host:'127.0.0.1',port:CORE_PORT,path:pathname,method:'GET',headers:{cookie:req.headers.cookie||''},timeout:3500},x=>{const a=[];x.on('data',c=>a.push(c));x.on('end',()=>{const raw=Buffer.concat(a).toString('utf8');let j={};try{j=raw?JSON.parse(raw):{}}catch{return reject(Error(raw||`Core HTTP ${x.statusCode}`))}if((x.statusCode||500)>=400)return reject(Object.assign(Error(j.error||`Core HTTP ${x.statusCode}`),{statusCode:x.statusCode}));resolve(j);});});r.on('timeout',()=>r.destroy(Error('Web core timeout')));r.on('error',reject);r.end();});}
async function coreAuth(req){try{await coreJson(req,'/api/me');return true}catch{return false}}
async function coreAllowsDevice(req,deviceId){try{const r=await coreJson(req,'/api/devices');return Array.isArray(r.devices)&&r.devices.some(d=>String(d.id)===String(deviceId));}catch{return false}}

function bridgeCall(port,method,pathname,payload=null,timeout=9000){return new Promise((resolve,reject)=>{const token=readToken();if(!token)return reject(Error('Launcher bridge chưa chạy. Hãy mở lại RUN_LOCAL.bat v0.10.'));const body=payload==null?null:Buffer.from(JSON.stringify(payload));const r=http.request({host:'127.0.0.1',port,path:pathname,method,timeout,headers:{'X-Auto-Bridge-Token':token,...(body?{'Content-Type':'application/json','Content-Length':body.length}:{})}},x=>{const a=[];x.on('data',c=>a.push(c));x.on('end',()=>{const raw=Buffer.concat(a).toString('utf8');let j={};try{j=raw?JSON.parse(raw):{}}catch{return reject(Error(raw||`Bridge HTTP ${x.statusCode}`))}if((x.statusCode||500)>=400||j.ok===false)return reject(Error(j.error||`Bridge HTTP ${x.statusCode}`));resolve(j);});});r.on('timeout',()=>r.destroy(Error(`Launcher bridge ${port} timeout`)));r.on('error',reject);if(body)r.write(body);r.end();});}

async function requireAuth(req,res){if(!(await coreAuth(req))){json(res,401,{error:'unauthorized'});return false;}return true;}

async function handleOptions(req,res){
  if(!(await requireAuth(req,res)))return;
  if(req.method==='POST'&&!sameOrigin(req))return json(res,403,{error:'origin rejected'});
  try{
    if(req.method==='GET'){const r=await bridgeCall(OPTIONS_PORT,'GET','/options');return json(res,200,{options:r.options||[],source:r.source,diagnostics:r.diagnostics||{}});}
    if(req.method==='POST'){const b=parseBody(await collect(req,65536));const r=await bridgeCall(OPTIONS_PORT,'POST','/options',{key:String(b.key||''),enabled:!!b.enabled});return json(res,200,r);}
    return json(res,405,{error:'method not allowed'});
  }catch(e){return json(res,500,{error:e.message});}
}
async function handleSettings(req,res,u){
  if(!(await requireAuth(req,res)))return;
  if(req.method==='POST'&&!sameOrigin(req))return json(res,403,{error:'origin rejected'});
  try{
    if(req.method==='GET'){const key=String(u.searchParams.get('key')||'').trim();if(!key)return json(res,400,{error:'key required'});return json(res,200,await bridgeCall(SETTINGS_PORT,'GET',`/settings?key=${encodeURIComponent(key)}`,null,10000));}
    if(req.method==='POST'){const b=parseBody(await collect(req,512*1024));return json(res,200,await bridgeCall(SETTINGS_PORT,'POST','/settings',{key:String(b.key||''),fields:Array.isArray(b.fields)?b.fields:[],action:String(b.action||'update')},12000));}
    return json(res,405,{error:'method not allowed'});
  }catch(e){return json(res,500,{error:e.message});}
}
async function handleFunctionActions(req,res,u){
  if(!(await requireAuth(req,res)))return;
  if(req.method==='POST'&&!sameOrigin(req))return json(res,403,{error:'origin rejected'});
  try{
    if(req.method==='GET'){
      const optionIndex=u.searchParams.get('option_index');
      if(optionIndex==null)return json(res,400,{error:'option_index required'});
      return json(res,200,await bridgeCall(FUNCTION_ACTIONS_PORT,'GET',`/actions?option_index=${encodeURIComponent(optionIndex)}`,null,10000));
    }
    if(req.method==='POST'){
      const b=parseBody(await collect(req,1024*1024));
      if(String(b.mode||'action')==='popup'){
        return json(res,200,await bridgeCall(FUNCTION_ACTIONS_PORT,'POST','/popup',{session_id:String(b.session_id||''),fields:Array.isArray(b.fields)?b.fields:[],action:String(b.action||'update')},12000));
      }
      return json(res,200,await bridgeCall(FUNCTION_ACTIONS_PORT,'POST','/action',{option_index:Number(b.option_index),action_id:String(b.action_id||''),confirm:!!b.confirm},12000));
    }
    return json(res,405,{error:'method not allowed'});
  }catch(e){return json(res,500,{error:e.message});}
}
async function handleExactStart(req,res){
  if(req.method!=='POST')return json(res,405,{error:'method not allowed'});
  if(!sameOrigin(req))return json(res,403,{error:'origin rejected'});
  if(!(await requireAuth(req,res)))return;
  try{
    const b=parseBody(await collect(req,65536));const deviceId=String(b.device_id||'').trim();if(!deviceId)return json(res,400,{error:'device_id required'});if(!(await coreAllowsDevice(req,deviceId)))return json(res,403,{error:'device denied'});
    const optionIndex=Number(b.option_index),functionId=Number(b.function_id),requestedLabel=String(b.label||'').trim();
    const live=await bridgeCall(TASK_PORT,'GET','/functions',null,5000),rows=Array.isArray(live.functions)?live.functions:[];let opt=null;
    if(Number.isFinite(optionIndex))opt=rows.find(x=>Number(x.option_index)===optionIndex&&(!requestedLabel||String(x.label)===requestedLabel));
    if(!opt&&Number.isFinite(functionId)&&requestedLabel)opt=rows.find(x=>Number(x.id)===functionId&&String(x.label)===requestedLabel);
    if(!opt&&Number.isFinite(optionIndex))opt=rows.find(x=>Number(x.option_index)===optionIndex);
    if(!opt)return json(res,400,{error:'Chức năng vừa chọn không còn tồn tại trong FUNCTION_OPTIONS thật. Bấm Tải lại ID AUTO rồi chọn lại.'});
    const r=await bridgeCall(TASK_PORT,'POST','/start',{device_id:deviceId,function_id:Number(opt.id),label:String(opt.label)},18000);
    return json(res,200,{...r,selected_option_index:Number(opt.option_index),selected_label:String(opt.label),source:'REAL_LAUNCHER_FUNCTION_OPTIONS'});
  }catch(e){return json(res,500,{error:e.message});}
}
async function handlePasswordChange(req,res){try{const current=await coreJson(req,'/api/me');if(current&&current.username===FIXED_ADMIN_USERNAME)return json(res,409,{error:`Mật khẩu admin được cố định là ${FIXED_ADMIN_PASSWORD}`});}catch{}return proxy(req,res);}

function proxy(req,res){const headers={...req.headers,host:`127.0.0.1:${CORE_PORT}`};delete headers.connection;const up=http.request({host:'127.0.0.1',port:CORE_PORT,path:req.url,method:req.method,headers},ur=>{const h={...ur.headers};delete h.connection;delete h['keep-alive'];delete h['transfer-encoding'];res.writeHead(ur.statusCode||502,h);ur.pipe(res);});up.on('error',e=>{if(!res.headersSent)json(res,502,{error:`Web core chưa sẵn sàng: ${e.message}`});else res.end();});req.on('aborted',()=>up.destroy());res.on('close',()=>{if(!up.destroyed)up.destroy();});req.pipe(up);}

const server=http.createServer((req,res)=>{const u=new URL(req.url,`http://${req.headers.host||'localhost'}`),p=u.pathname;if(p==='/api/options')return handleOptions(req,res);if(p==='/api/options/settings')return handleSettings(req,res,u);if(p==='/api/function-actions')return handleFunctionActions(req,res,u);if(p==='/api/auto/start-v08')return handleExactStart(req,res);if(p==='/api/account/password'&&req.method==='POST')return handlePasswordChange(req,res);return proxy(req,res);});
server.keepAliveTimeout=65000;server.headersTimeout=70000;
server.on('error',err=>{if(err&&err.code==='EADDRINUSE')console.error(`\n[ERROR] Port ${PUBLIC_PORT} đang bị Web AUTO cũ chiếm. Đóng Web cũ rồi chạy lại RUN_WEB.bat.\n`);else console.error(err);try{core.kill();}catch{}process.exit(1);});
setTimeout(()=>server.listen(PUBLIC_PORT,HOST,()=>console.log(`AUTO KVTM WEB v0.10: http://${HOST}:${PUBLIC_PORT} (core ${CORE_PORT})`)),350);
function shutdown(){try{core.kill();}catch{}try{server.close();}catch{}}
process.on('SIGINT',()=>{shutdown();process.exit(0)});process.on('SIGTERM',()=>{shutdown();process.exit(0)});process.on('exit',shutdown);
