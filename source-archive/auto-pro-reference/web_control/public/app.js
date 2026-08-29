const $ = s => document.querySelector(s);
let me = null, functions = [], functionMeta = {}, allUsers = [], activeUser = null;
let statusTimer = null, renderGeneration = 0;
const activeDeviceByUser = new Map();
const viewers = new Map();

const req = async (url, opt = {}) => {
  const r = await fetch(url, { cache:'no-store', ...opt, headers:{'Content-Type':'application/json', ...(opt.headers||{})} });
  let j = {}; try { j = await r.json(); } catch {}
  if (!r.ok) throw Error(j.error || `HTTP ${r.status}`);
  return j;
};

async function boot(){
  try { me = await req('/api/me'); await showApp(); }
  catch { $('#login').classList.remove('hidden'); }
}
$('#loginForm').onsubmit = async e => {
  e.preventDefault(); $('#loginErr').textContent='';
  try { await req('/api/login',{method:'POST',body:JSON.stringify({username:$('#user').value,password:$('#pass').value})}); me=await req('/api/me'); await showApp(); }
  catch(x){ $('#loginErr').textContent=x.message; }
};

async function loadEngineAndFunctions(){
  const dot=$('#engineDot'), txt=$('#engineText');
  dot.className='dot wait'; txt.textContent='LAUNCHER: đang kết nối TaskManager thật...';
  try {
    const [engine,fl]=await Promise.all([req('/api/engine'),req('/api/functions')]);
    functions=fl.functions||[]; functionMeta=fl.meta||{};
    dot.className='dot ok';
    txt.textContent=`LAUNCHER: ĐÃ KẾT NỐI • ${engine.active_count||0} đang chạy / ${engine.task_count||0} task • ${engine.device_count||0} device • ${functionMeta.option_count||functions.length} chức năng`;
  } catch(e){
    try { const fl=await req('/api/functions'); functions=fl.functions||[]; functionMeta=fl.meta||{}; } catch { functions=[]; }
    dot.className='dot bad';
    txt.textContent=`LAUNCHER: CHƯA KẾT NỐI • ${e.message}`;
  }
}

async function showApp(){
  $('#login').classList.add('hidden'); $('#app').classList.remove('hidden');
  $('#who').textContent=`${me.username} · ${me.role}`;
  if(me.role==='admin') $('#adminBtn').classList.remove('hidden');
  await loadEngineAndFunctions(); await refreshTabs();
  clearInterval(statusTimer); statusTimer=setInterval(refreshStatus,1000);
}
$('#reloadFuncs').onclick=async()=>{await loadEngineAndFunctions();await renderDevices();};

async function refreshTabs(){
  if(me.role==='admin'){
    allUsers=(await req('/api/admin/users')).users; activeUser=activeUser||me.username;
    $('#tabs').innerHTML=allUsers.map(u=>`<button class="tab ${u.username===activeUser?'active':''}" data-u="${esc(u.username)}">${esc(u.username)}</button>`).join('');
    document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{activeUser=b.dataset.u;refreshTabs();});
  }else{activeUser=me.username;$('#tabs').innerHTML=`<button class="tab active">${esc(me.username)}</button>`;}
  await renderDevices();
}
function visibleDeviceIds(){
  if(me.role!=='admin') return me.devices||[];
  const u=allUsers.find(x=>x.username===activeUser); return u&&u.role!=='admin'?(u.devices||[]):null;
}

async function renderDevices(){
  const generation=++renderGeneration;
  for(const v of viewers.values()) v.destroy(); viewers.clear();
  let ds=(await req('/api/devices')).devices||[];
  const ids=visibleDeviceIds(); if(ids) ds=ds.filter(d=>ids.includes(d.id));

  const nav=$('#deviceNav');
  if(!ds.length){
    nav.innerHTML='';
    $('#devices').innerHTML=`<div class="panel muted">Không tìm thấy device cho tài khoản này. Hãy bấm Load Devices trên AUTO rồi bấm Tải lại ID AUTO.</div>`;
    return;
  }

  const owner=activeUser||me.username;
  let activeId=activeDeviceByUser.get(owner);
  if(!ds.some(d=>d.id===activeId)) activeId=ds[0].id;
  activeDeviceByUser.set(owner,activeId);

  nav.innerHTML=ds.map(d=>`<button class="deviceTab ${d.id===activeId?'active':''}" data-id="${esc(d.id)}"><b>${esc(d.display_name||d.id)}</b><span>${esc(d.id)}</span><i class="navAuto">...</i></button>`).join('');
  nav.querySelectorAll('.deviceTab').forEach(b=>b.onclick=()=>{activeDeviceByUser.set(owner,b.dataset.id);renderDevices();});

  // Render only one emulator stream at a time. With 6-10 emulators this keeps
  // H.264 decoding smooth instead of opening many screenrecord streams at once.
  const active=ds.find(d=>d.id===activeId)||ds[0];
  $('#devices').innerHTML=deviceCard(active);
  wireDevices([active],generation); await refreshStatus();
}

function deviceCard(d){
  const w=loadViewWidth(d.id);
  return `<section class="device" data-device="${esc(d.id)}">
    <div class="deviceHead">
      <div class="deviceIdentity"><b>${esc(d.display_name||d.id)}</b><div class="deviceId">${esc(d.id)}</div><div class="muted">${esc(d.model||d.product||d.source||'')}</div></div>
      <div class="badges"><span class="state ${d.state==='device'?'on':''}">${esc(d.state)}</span><span class="autoState unknown">AUTO: ĐANG ĐỌC...</span></div>
    </div>

    <div class="screenOuter">
      <div class="screenToolbar">
        <span class="liveState">LIVE: khởi tạo H.264...</span>
        <span class="displayState">đang đọc độ phân giải...</span>
        <button class="preset secondary" title="Đặt emulator 1000x1000, DPI 240">1000² / 240 DPI</button>
        <button class="resetDisplay secondary">Reset display</button>
      </div>
      <div class="screenWrap" style="width:${w}px">
        <canvas class="screen" width="1000" height="1000"></canvas>
        <span class="streamStats">BUFFERING</span>
        <div class="resizeHandle" title="Kéo để phóng to / thu nhỏ khung xem"></div>
      </div>
      <div class="viewSizeLabel">VIEW ONLY • <b class="viewPx">${w}px</b> • LIVE ưu tiên mượt, tự bỏ frame cũ nếu máy/browser chậm</div>
    </div>

    <div class="controls">
      <div class="runningInfo muted">Task thật: đang đọc từ launcher...</div>
      <div class="functionBox">
        <div class="row between"><b>Chức năng đúng tên trong AUTO</b><span class="funcCount">${functionMeta.option_count||functions.length} mục</span></div>
        <input class="funcSearch" placeholder="Tìm ID hoặc tên đúng như AUTO...">
        <select class="func" size="10"></select>
        <div class="selectedFunc"></div>
        <div class="funcDesc muted"></div>
      </div>
      <div class="row mainActions"><button class="start">START</button><button class="stop" disabled>STOP</button><button class="restartStream secondary">LIVE ↻</button></div>
      <div class="logs"></div>
    </div>
  </section>`;
}

function functionText(f){return `#${f.id} · ${f.label}`;}
function fillFunctionSelect(box,q=''){
  const sel=box.querySelector('.func'), query=normalize(q), cur=sel.value;
  let arr=functions;
  if(query) arr=functions.filter(f=>normalize(`${f.id} ${f.label} ${f.search||''} ${(f.description||[]).join(' ')}`).includes(query));
  sel.innerHTML=arr.map(f=>`<option value="${f.option_index}">${esc(functionText(f))}</option>`).join('');
  if(cur&&arr.some(f=>String(f.option_index)===cur)) sel.value=cur; else if(arr.length) sel.selectedIndex=0;
  updateFuncDesc(box);
}
function selectedFunction(box){const idx=Number(box.querySelector('.func').value);return functions.find(x=>Number(x.option_index)===idx);}
function updateFuncDesc(box){
  const f=selectedFunction(box), el=box.querySelector('.funcDesc'), selected=box.querySelector('.selectedFunc');
  if(!f){selected.textContent='CHƯA CHỌN CHỨC NĂNG';el.textContent='Không có chức năng phù hợp.';return;}
  selected.textContent=`ĐÃ CHỌN: #${f.id} · ${f.label}`;
  const d=(f.description||[]).slice(0,4).join(' • ');
  el.textContent=`${f.method}`+(d?` • ${d}`:'');
}

function wireDevices(ds,generation){
  for(const d of ds){
    const box=document.querySelector(`[data-device="${cssEsc(d.id)}"]`), wrap=box.querySelector('.screenWrap'), canvas=box.querySelector('.screen');
    fillFunctionSelect(box);
    box.querySelector('.funcSearch').oninput=e=>fillFunctionSelect(box,e.target.value);
    box.querySelector('.func').onchange=()=>updateFuncDesc(box);

    const viewer=new SmoothH264Viewer(d.id,canvas,box.querySelector('.liveState'),box.querySelector('.streamStats'));
    viewers.set(d.id,viewer); viewer.start();
    box.querySelector('.restartStream').onclick=()=>viewer.restart();

    wireResize(d.id,wrap,box.querySelector('.resizeHandle'),box.querySelector('.viewPx'));
    refreshDisplay(box,d.id);
    box.querySelector('.preset').onclick=async()=>{try{await req(`/api/device/${encodeURIComponent(d.id)}/display`,{method:'POST',body:JSON.stringify({width:1000,height:1000,density:240})});await refreshDisplay(box,d.id);viewer.restart();}catch(e){alert(e.message)}};
    box.querySelector('.resetDisplay').onclick=async()=>{try{await req(`/api/device/${encodeURIComponent(d.id)}/display`,{method:'POST',body:JSON.stringify({reset:true})});await refreshDisplay(box,d.id);viewer.restart();}catch(e){alert(e.message)}};

    box.querySelector('.start').onclick=async()=>{
      const f=selectedFunction(box); if(!f)return alert('Chọn chức năng');
      try{box.querySelector('.start').disabled=true;await req('/api/auto/start',{method:'POST',body:JSON.stringify({device_id:d.id,function_id:f.id,option_index:f.option_index})});await sleep(500);await refreshStatus();}
      catch(e){alert(e.message)}finally{await refreshStatus();}
    };
    box.querySelector('.stop').onclick=async()=>{
      try{box.querySelector('.stop').disabled=true;box.querySelector('.autoState').textContent='AUTO: ĐANG DỪNG...';await req('/api/auto/stop',{method:'POST',body:JSON.stringify({device_id:d.id})});}
      catch(e){alert(e.message)}finally{await sleep(400);await refreshStatus();}
    };
  }
}

async function refreshDisplay(box,id){
  try{const r=await req(`/api/device/${encodeURIComponent(id)}/display`),d=r.display;box.querySelector('.displayState').textContent=`${d.width||'?'}×${d.height||'?'} @ ${d.density||'?'} DPI`;}
  catch(e){box.querySelector('.displayState').textContent='display ?';}
}

async function refreshStatus(){
  let status=[]; let engine=null;
  try{
    const r=await req('/api/status'); status=r.status||[];
    engine=await req('/api/engine');
    $('#engineDot').className='dot ok';
    $('#engineText').textContent=`LAUNCHER: ĐÃ KẾT NỐI • ${engine.active_count||0} đang chạy / ${engine.task_count||0} task • ${engine.device_count||0} device • ${engine.function_count||functions.length} chức năng`;
  }catch(e){
    $('#engineDot').className='dot bad'; $('#engineText').textContent=`LAUNCHER: CHƯA KẾT NỐI • ${e.message}`;
  }

  document.querySelectorAll('.device').forEach(box=>{
    const id=box.dataset.device, s=status.find(x=>x.device_id===id), badge=box.querySelector('.autoState'), info=box.querySelector('.runningInfo');
    const running=!!(s&&(s.thread_alive||s.ui_running||s.status==='running'||s.manager_status==='running'));
    badge.className=`autoState ${running?'running':s?'idle':'unknown'}`;
    badge.textContent=running?'AUTO: ĐANG CHẠY':s?`AUTO: ${String(s.status||'DỪNG').toUpperCase()}`:'AUTO: CHƯA CÓ TASK';
    box.querySelector('.start').disabled=running;
    box.querySelector('.stop').disabled=!running;
    if(s){
      const fid=s.function_id!=null?`#${s.function_id} · `:'';
      const ui=s.ui_status&&s.ui_status!==s.manager_status?` • UI:${s.ui_status}`:'';
      info.textContent=running?`ĐANG CHẠY THẬT: ${fid}${s.func_text||'(launcher chưa lưu tên)'}${ui}`:`Task thật: ${s.display_name||id} • ${s.status||'ready'}${ui}`;
    }else info.textContent='Chưa có TaskInfo cho device này — vẫn có thể chọn chức năng và START từ web.';
  });

  document.querySelectorAll('.deviceTab').forEach(tab=>{
    const id=tab.dataset.id, s=status.find(x=>x.device_id===id), running=!!(s&&(s.thread_alive||s.ui_running||s.status==='running'||s.manager_status==='running'));
    const el=tab.querySelector('.navAuto'); if(el){el.textContent=running?'ĐANG CHẠY':s?(s.status||'ready').toUpperCase():'CHƯA TASK';el.className=`navAuto ${running?'running':''}`;}
  });
  await refreshLogs();
}
async function refreshLogs(){
  for(const box of document.querySelectorAll('.device')){
    const id=box.dataset.device; try{const r=await req(`/api/logs?device=${encodeURIComponent(id)}`);const el=box.querySelector('.logs');el.innerHTML=(r.logs||[]).slice(-80).map(x=>`<div class="logline ${esc(x.type)}">${esc(new Date(x.ts).toLocaleTimeString())} ${esc(x.message)}</div>`).join('');el.scrollTop=el.scrollHeight;}catch{}
  }
}

// -------- Passive smooth H.264 viewer --------
// v0.6: no long playback buffer. Keep only a tiny jitter queue, continuously
// discard stale frames, and pace playback using the measured decoder rate.
// This prevents the old BUFFER -> burst -> REBUFFER loop that looked extremely laggy.
class SmoothH264Viewer{
  constructor(deviceId,canvas,stateEl,statsEl){
    this.deviceId=deviceId;this.canvas=canvas;this.ctx=canvas.getContext('2d',{alpha:false,desynchronized:true});this.stateEl=stateEl;this.statsEl=statsEl;
    this.abort=null;this.decoder=null;this.parser=null;this.queue=[];this.au=[];this.hasVcl=false;this.configured=false;this.seenKey=false;this.ts=0;this.destroyed=false;
    this.renderTimer=null;this.fallbackTimer=null;this.watchdogTimer=null;this.decoded=0;this.drawn=0;this.dropped=0;this.startedAt=performance.now();
    this.lastFrameAt=0;this.sourceInterval=50;this.failures=0;this.profile='smooth';this.profileDowngraded=false;this.lowFpsSince=0;
  }
  start(){
    this.destroyed=false;this.startedAt=performance.now();this.decoded=0;this.drawn=0;this.dropped=0;this.lastFrameAt=0;this.sourceInterval=50;this.lowFpsSince=0;
    if(!('VideoDecoder'in window)){this.startPngFallback('WebCodecs không hỗ trợ');return;}
    this.connect();
    clearTimeout(this.watchdogTimer);
    this.watchdogTimer=setTimeout(()=>{if(!this.destroyed&&this.drawn===0)this.startPngFallback('H.264 không ra frame sau 7s');},7000);
  }
  restart(){this.stopStream(false);this.stateEl.textContent='LIVE: khởi động lại...';setTimeout(()=>this.start(),120);}
  destroy(){this.destroyed=true;this.stopStream(true);}
  stopStream(final){
    if(this.abort){this.abort.abort();this.abort=null;}
    if(this.decoder){try{this.decoder.close();}catch{}this.decoder=null;}
    if(this.renderTimer){clearTimeout(this.renderTimer);this.renderTimer=null;}
    if(this.fallbackTimer){clearTimeout(this.fallbackTimer);this.fallbackTimer=null;}
    if(this.watchdogTimer){clearTimeout(this.watchdogTimer);this.watchdogTimer=null;}
    for(const f of this.queue){try{f.close();}catch{}}
    this.queue=[];this.au=[];this.hasVcl=false;this.configured=false;this.seenKey=false;
    if(!final)this.destroyed=false;
  }
  streamUrl(){
    // `smooth` is intentionally lower than the emulator's 1000x1000 display.
    // screenrecord downscales only the VIEW stream; the emulator remains 1000x1000/240.
    const q=this.profile==='lite'?'size=640&bitrate=2200000':'size=720&bitrate=3200000';
    return `/api/device/${encodeURIComponent(this.deviceId)}/h264?${q}&x=${Date.now()}`;
  }
  async connect(){
    if(this.destroyed)return;
    this.abort=new AbortController();this.resetDecoder();this.parser=new AnnexBParser(n=>this.onNal(n));
    this.stateEl.textContent=this.profile==='lite'?'LIVE H.264 • 640p mượt':'LIVE H.264 • 720p mượt';
    try{
      const r=await fetch(this.streamUrl(),{cache:'no-store',signal:this.abort.signal});
      if(!r.ok||!r.body)throw Error(`H264 HTTP ${r.status}`);
      const reader=r.body.getReader();
      while(!this.destroyed){const {done,value}=await reader.read();if(done)break;if(value)this.parser.push(value);}
      if(!this.destroyed)setTimeout(()=>this.connect(),250);
    }catch(e){
      if(this.destroyed||e.name==='AbortError')return;
      this.failures++;
      if(this.failures>=3){this.startPngFallback(`H.264 fallback: ${e.message}`);return;}
      this.stateEl.textContent='LIVE H.264: reconnect...';setTimeout(()=>this.connect(),400);
    }
  }
  resetDecoder(){
    if(this.decoder){try{this.decoder.close();}catch{}}
    for(const f of this.queue){try{f.close();}catch{}}
    this.queue=[];this.au=[];this.hasVcl=false;this.configured=false;this.seenKey=false;this.ts=0;
    this.decoder=new VideoDecoder({
      output:f=>this.onFrame(f),
      error:e=>{this.failures++;this.stateEl.textContent=`LIVE decode lỗi: ${e.message||e}`;if(this.failures>=3&&!this.destroyed)setTimeout(()=>this.startPngFallback('decoder H.264 lỗi'),0);}
    });
    this.scheduleRender(30);
  }
  configureFromSps(nal){
    const sc=startCodeLength(nal),p=nal.subarray(sc+1);if(p.length<3)return;
    const codec=`avc1.${hex2(p[0])}${hex2(p[1])}${hex2(p[2])}`;
    this.decoder.configure({codec,hardwareAcceleration:'prefer-hardware',optimizeForLatency:true});
    this.configured=true;this.stateEl.textContent=`LIVE H.264 • ${this.profile==='lite'?'640':'720'}p • ${codec}`;
  }
  onNal(nal){
    const sc=startCodeLength(nal);if(sc<=0||nal.length<=sc)return;const type=nal[sc]&31;
    if(type===7){if(this.hasVcl)this.flushAu();try{this.configureFromSps(nal);}catch{}this.au.push(nal);return;}
    if(type===8){if(this.hasVcl)this.flushAu();this.au.push(nal);return;}
    if(type===9){this.flushAu();this.au=[nal];this.hasVcl=false;return;}
    if(type===1||type===5){const first=firstMbInSlice(nal.subarray(sc+1));if(first===0&&this.hasVcl)this.flushAu();this.hasVcl=true;}
    this.au.push(nal);
  }
  flushAu(){
    if(!this.au.length)return;
    const hasVcl=this.au.some(n=>{const s=startCodeLength(n),t=s>0?(n[s]&31):0;return t===1||t===5;});
    if(!hasVcl){this.au=[];this.hasVcl=false;return;}
    const key=this.au.some(n=>{const s=startCodeLength(n);return s>0&&(n[s]&31)===5;});
    const data=concatMany(this.au);this.au=[];this.hasVcl=false;
    if(!this.configured)return;if(!this.seenKey&&!key)return;if(key)this.seenKey=true;
    // Never let the decoder build seconds of hidden work. Delta frames are cheap
    // to discard here; the next key frame re-synchronizes if the machine is busy.
    if(this.decoder.decodeQueueSize>8&&!key){this.dropped++;return;}
    try{this.decoder.decode(new EncodedVideoChunk({type:key?'key':'delta',timestamp:this.ts,duration:33333,data}));this.ts+=33333;}catch{}
  }
  onFrame(frame){
    const now=performance.now();
    if(this.lastFrameAt){
      const dt=clamp(now-this.lastFrameAt,16,250);
      this.sourceInterval=this.sourceInterval*.88+dt*.12;
    }
    this.lastFrameAt=now;this.decoded++;this.queue.push(frame);
    // Tiny jitter buffer only. Old frames are useless for a monitor view; keeping
    // them is exactly what made v0.5 accumulate delay and then play catch-up.
    while(this.queue.length>6){const old=this.queue.shift();try{old.close();}catch{}this.dropped++;}
  }
  scheduleRender(ms){
    if(this.destroyed)return;
    if(this.renderTimer)clearTimeout(this.renderTimer);
    this.renderTimer=setTimeout(()=>this.renderTick(),Math.max(16,ms));
  }
  renderTick(){
    if(this.destroyed)return;
    // Pace close to the real decoded frame rate instead of assuming 30 FPS.
    // Keep 1-2 frames of jitter headroom and drop stale backlog immediately.
    if(this.queue.length>3){while(this.queue.length>2){const old=this.queue.shift();try{old.close();}catch{}this.dropped++;}}
    const frame=this.queue.shift();
    if(frame){
      try{
        if(this.canvas.width!==frame.displayWidth||this.canvas.height!==frame.displayHeight){this.canvas.width=frame.displayWidth;this.canvas.height=frame.displayHeight;}
        this.ctx.drawImage(frame,0,0,this.canvas.width,this.canvas.height);this.drawn++;
      }finally{try{frame.close();}catch{}}
    }
    const srcFps=1000/Math.max(1,this.sourceInterval);
    const sec=Math.max(.5,(performance.now()-this.startedAt)/1000);
    const outFps=this.drawn/sec;
    this.statsEl.textContent=`LIVE ${outFps.toFixed(1)} FPS • nguồn ~${srcFps.toFixed(0)} • Q${this.queue.length} • bỏ ${this.dropped}`;

    // If the 720 stream itself stays very slow, reconnect once at 640. This only
    // changes stream encoding, not the emulator display resolution/DPI.
    if(!this.profileDowngraded&&sec>5&&srcFps<12){
      if(!this.lowFpsSince)this.lowFpsSince=performance.now();
      if(performance.now()-this.lowFpsSince>3000){
        this.profileDowngraded=true;this.profile='lite';this.stateEl.textContent='LIVE: tự giảm stream 640p để tăng FPS...';
        this.stopStream(false);setTimeout(()=>this.start(),150);return;
      }
    }else if(srcFps>=12){this.lowFpsSince=0;}

    const interval=clamp(this.sourceInterval,24,100);
    this.scheduleRender(interval);
  }
  startPngFallback(reason){
    this.stopStream(false);this.stateEl.textContent=`LIVE ẢNH • ${reason}`;
    const tick=async()=>{
      if(this.destroyed)return;
      try{
        const r=await fetch(`/api/device/${encodeURIComponent(this.deviceId)}/screenshot?t=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw Error(`HTTP ${r.status}`);
        const blob=await r.blob();const bmp=await createImageBitmap(blob);
        if(this.canvas.width!==bmp.width||this.canvas.height!==bmp.height){this.canvas.width=bmp.width;this.canvas.height=bmp.height;}
        this.ctx.drawImage(bmp,0,0);bmp.close();this.statsEl.textContent='ẢNH 2 FPS • fallback';
      }catch(e){this.statsEl.textContent='LIVE lỗi';}
      if(!this.destroyed)this.fallbackTimer=setTimeout(tick,500);
    };tick();
  }
}
class AnnexBParser{
  constructor(cb){this.cb=cb;this.buf=new Uint8Array(0);}
  push(chunk){this.buf=concat2(this.buf,chunk);const starts=findStarts(this.buf);if(!starts.length){if(this.buf.length>8*1024*1024)this.buf=this.buf.slice(-4);return;}if(starts.length===1){if(starts[0]>0)this.buf=this.buf.slice(starts[0]);return;}for(let i=0;i<starts.length-1;i++){const n=this.buf.slice(starts[i],starts[i+1]);if(n.length>4)this.cb(n);}this.buf=this.buf.slice(starts[starts.length-1]);}
}
function findStarts(b){const a=[];for(let i=0;i<b.length-3;i++){if(b[i]===0&&b[i+1]===0&&b[i+2]===1){a.push(i);i+=2;}else if(b[i]===0&&b[i+1]===0&&b[i+2]===0&&b[i+3]===1){a.push(i);i+=3;}}return a;}
function startCodeLength(n){if(n.length>=3&&n[0]===0&&n[1]===0&&n[2]===1)return 3;if(n.length>=4&&n[0]===0&&n[1]===0&&n[2]===0&&n[3]===1)return 4;return 0;}
function rbsp(bytes){const out=[];for(let i=0;i<bytes.length;i++){if(i>=2&&bytes[i]===3&&bytes[i-1]===0&&bytes[i-2]===0)continue;out.push(bytes[i]);}return new Uint8Array(out);}
function firstMbInSlice(payload){try{const b=rbsp(payload);let bit=0;const readBit=()=>{const v=(b[bit>>3]>>(7-(bit&7)))&1;bit++;return v;};let zeros=0;while(bit<b.length*8&&readBit()===0)zeros++;let v=(1<<zeros)-1;for(let i=0;i<zeros;i++)v+=readBit()<<(zeros-1-i);return v;}catch{return null;}}
function concat2(a,b){const o=new Uint8Array(a.length+b.length);o.set(a);o.set(b,a.length);return o;}
function concatMany(arr){let n=0;for(const a of arr)n+=a.length;const o=new Uint8Array(n);let p=0;for(const a of arr){o.set(a,p);p+=a.length;}return o;}
function hex2(v){return Number(v).toString(16).padStart(2,'0').toUpperCase();}

function wireResize(id,wrap,handle,label){
  let startX=0,startW=0,drag=false;
  const move=e=>{if(!drag)return;const x=e.clientX??e.touches?.[0]?.clientX??startX;const w=clamp(startW+(x-startX),220,1100);wrap.style.width=`${w}px`;label.textContent=`${Math.round(w)}px`;};
  const up=()=>{if(!drag)return;drag=false;saveViewWidth(id,parseFloat(wrap.style.width)||wrap.clientWidth);window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);};
  handle.onpointerdown=e=>{drag=true;startX=e.clientX;startW=wrap.getBoundingClientRect().width;handle.setPointerCapture?.(e.pointerId);window.addEventListener('pointermove',move);window.addEventListener('pointerup',up);e.preventDefault();};
}

$('#logoutBtn').onclick=async()=>{await req('/api/logout',{method:'POST'});location.reload();};
$('#pwdBtn').onclick=()=>$('#pwdDlg').showModal();
$('#savePwd').onclick=async()=>{try{await req('/api/account/password',{method:'POST',body:JSON.stringify({password:$('#newPwd').value})});$('#pwdDlg').close();alert('Đã đổi mật khẩu')}catch(e){alert(e.message)}};
$('#adminBtn').onclick=async()=>{await loadAdmin();$('#userDlg').showModal();};
async function loadAdmin(){allUsers=(await req('/api/admin/users')).users;const ds=(await req('/api/devices')).devices;$('#userList').innerHTML=allUsers.map(u=>`<div class="userRow"><div><b>${esc(u.username)}</b><div class="muted">${esc(u.role)}</div></div><div class="checks">${ds.map(d=>`<label><input type="checkbox" data-du="${esc(u.username)}" value="${esc(d.id)}" ${(u.devices||[]).includes(d.id)?'checked':''}> ${esc(d.display_name||d.id)} (${esc(d.id)})</label>`).join('')}</div><button type="button" class="saveUser secondary" data-u="${esc(u.username)}">Lưu quyền</button></div>`).join('');document.querySelectorAll('.saveUser').forEach(b=>b.onclick=async()=>{const user=b.dataset.u,devices=[...document.querySelectorAll(`input[data-du="${cssEsc(user)}"]:checked`)].map(x=>x.value);await req('/api/admin/users',{method:'PUT',body:JSON.stringify({username:user,devices})});await loadAdmin();await refreshTabs();});}
$('#createUser').onclick=async()=>{try{await req('/api/admin/users',{method:'POST',body:JSON.stringify({username:$('#newUser').value,password:$('#newPass').value,role:'user',devices:[]})});$('#newUser').value='';$('#newPass').value='';await loadAdmin();await refreshTabs();}catch(e){alert(e.message)}};

function loadViewWidth(id){return clamp(Number(localStorage.getItem(`viewWidth:${id}`))||360,220,1100);}
function saveViewWidth(id,w){localStorage.setItem(`viewWidth:${id}`,String(Math.round(w)));}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const normalize=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function cssEsc(s){return window.CSS?.escape?CSS.escape(String(s)):String(s).replace(/([ #;?%&,.+*~\\':"!^$[\]()=>|/@])/g,'\\$1');}
boot();