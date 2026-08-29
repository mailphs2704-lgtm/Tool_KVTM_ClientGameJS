'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { URL } = require('url');

const ROOT = path.resolve(__dirname, '..');
const CORE_PORT = Number(process.env.AUTO_WEB_CORE_PORT || 18080);
const PUBLIC_PORT = Number(process.env.AUTO_WEB_PORT || 8080);
const HOST = process.env.AUTO_WEB_HOST || '127.0.0.1';
const TOKEN_FILE = path.join(ROOT, 'local_data', 'bridge_token.txt');
const OPTIONS_PORT = 8767;

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
function collect(req,limit=1024*1024){return new Promise((resolve,reject)=>{const a=[];let n=0;req.on('data',c=>{n+=c.length;if(n>limit)reject(Error('request too large'));else a.push(c)});req.on('end',()=>resolve(Buffer.concat(a)));req.on('error',reject);});}
function json(res,code,obj){const b=Buffer.from(JSON.stringify(obj));res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Content-Length':b.length,'Cache-Control':'no-store'});res.end(b);}
function coreAuth(req){return new Promise(resolve=>{const r=http.request({host:'127.0.0.1',port:CORE_PORT,path:'/api/me',method:'GET',headers:{cookie:req.headers.cookie||''},timeout:3000},x=>{x.resume();resolve(x.statusCode===200)});r.on('timeout',()=>{r.destroy();resolve(false)});r.on('error',()=>resolve(false));r.end();});}
function optionBridge(method,payload){return new Promise((resolve,reject)=>{const token=readToken();if(!token)return reject(Error('Options bridge chưa chạy. Hãy mở lại RUN_LOCAL.bat.'));const body=payload?Buffer.from(JSON.stringify(payload)):null;const r=http.request({host:'127.0.0.1',port:OPTIONS_PORT,path:'/options',method,timeout:5000,headers:{'X-Auto-Bridge-Token':token,...(body?{'Content-Type':'application/json','Content-Length':body.length}:{})}},x=>{const a=[];x.on('data',c=>a.push(c));x.on('end',()=>{const raw=Buffer.concat(a).toString('utf8');let j={};try{j=raw?JSON.parse(raw):{}}catch{return reject(Error(raw||`HTTP ${x.statusCode}`))}if((x.statusCode||500)>=400||j.ok===false)reject(Error(j.error||`HTTP ${x.statusCode}`));else resolve(j);});});r.on('timeout',()=>r.destroy(Error('Options bridge timeout')));r.on('error',reject);if(body)r.write(body);r.end();});}

async function handleOptions(req,res){
  if(!(await coreAuth(req)))return json(res,401,{error:'unauthorized'});
  if(req.method==='POST'&&!sameOrigin(req))return json(res,403,{error:'origin rejected'});
  try{
    if(req.method==='GET'){const r=await optionBridge('GET');return json(res,200,{options:r.options||[],source:r.source});}
    if(req.method==='POST'){const raw=await collect(req,65536);let b={};try{b=raw.length?JSON.parse(raw):{}}catch{return json(res,400,{error:'JSON không hợp lệ'})}const r=await optionBridge('POST',{key:String(b.key||''),enabled:!!b.enabled});return json(res,200,r);}
    return json(res,405,{error:'method not allowed'});
  }catch(e){return json(res,500,{error:e.message});}
}

function proxy(req,res){
  const headers={...req.headers,host:`127.0.0.1:${CORE_PORT}`};
  delete headers.connection;
  const up=http.request({host:'127.0.0.1',port:CORE_PORT,path:req.url,method:req.method,headers},ur=>{
    const h={...ur.headers}; delete h.connection; delete h['keep-alive']; delete h['transfer-encoding'];
    res.writeHead(ur.statusCode||502,h); ur.pipe(res);
  });
  up.on('error',e=>{if(!res.headersSent)json(res,502,{error:`Web core chưa sẵn sàng: ${e.message}`});else res.end();});
  req.on('aborted',()=>up.destroy()); res.on('close',()=>{if(!up.destroyed)up.destroy();}); req.pipe(up);
}

const server=http.createServer((req,res)=>{
  const pathname=new URL(req.url,`http://${req.headers.host||'localhost'}`).pathname;
  if(pathname==='/api/options')return handleOptions(req,res);
  return proxy(req,res);
});
server.keepAliveTimeout=65000;server.headersTimeout=70000;
setTimeout(()=>server.listen(PUBLIC_PORT,HOST,()=>console.log(`AUTO KVTM WEB v0.7 proxy: http://${HOST}:${PUBLIC_PORT} (core ${CORE_PORT})`)),350);
function shutdown(){try{core.kill();}catch{}try{server.close();}catch{}}
process.on('SIGINT',()=>{shutdown();process.exit(0)});process.on('SIGTERM',()=>{shutdown();process.exit(0)});process.on('exit',shutdown);
