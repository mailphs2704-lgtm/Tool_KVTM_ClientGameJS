(() => {
  'use strict';

  // v0.10.3 UI cleanup.
  // IMPORTANT: do not run a second DOM polling loop. The original app already
  // refreshes status once per second; fighting that loop caused old/new labels
  // to flash continuously. Override the render/status functions once instead.

  const cleanName = d => String((d && d.display_name) || '').trim() || 'CHƯA ĐẶT TÊN';
  const isRunning = s => !!(s && (s.thread_alive || s.ui_running || s.status === 'running' || s.manager_status === 'running'));

  document.title = 'AUTO KVTM';

  loadEngineAndFunctions = async function(){
    const dot=$('#engineDot'), txt=$('#engineText');
    dot.className='dot wait'; txt.textContent='ĐANG KẾT NỐI...';
    try {
      const [engine,fl]=await Promise.all([req('/api/engine'),req('/api/functions')]);
      functions=fl.functions||[]; functionMeta=fl.meta||{};
      dot.className='dot ok';
      txt.textContent=`${engine.device_count||0} DEVICE • ${engine.active_count||0} ĐANG CHẠY`;
    } catch(e){
      try { const fl=await req('/api/functions'); functions=fl.functions||[]; functionMeta=fl.meta||{}; } catch { functions=[]; }
      dot.className='dot bad';
      txt.textContent='0 DEVICE • 0 ĐANG CHẠY';
    }
  };

  renderDevices = async function(){
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

    nav.innerHTML=ds.map(d=>`<button class="deviceTab ${d.id===activeId?'active':''}" data-id="${esc(d.id)}"><b>${esc(cleanName(d))}</b><i class="navAuto">DỪNG</i></button>`).join('');
    nav.querySelectorAll('.deviceTab').forEach(b=>b.onclick=()=>{activeDeviceByUser.set(owner,b.dataset.id);renderDevices();});

    const active=ds.find(d=>d.id===activeId)||ds[0];
    $('#devices').innerHTML=deviceCard(active);
    wireDevices([active],generation); await refreshStatus();
  };

  deviceCard = function(d){
    const w=loadViewWidth(d.id);
    return `<section class="device" data-device="${esc(d.id)}">
      <div class="deviceHead">
        <div class="deviceIdentity"><b>${esc(cleanName(d))}</b></div>
        <div class="badges"><span class="autoState unknown">DỪNG</span></div>
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
        <div class="runningInfo muted">Đang đọc trạng thái...</div>
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
  };

  refreshStatus = async function(){
    let status=[]; let engine=null;
    try{
      const r=await req('/api/status'); status=r.status||[];
      engine=await req('/api/engine');
      $('#engineDot').className='dot ok';
      $('#engineText').textContent=`${engine.device_count||0} DEVICE • ${engine.active_count||0} ĐANG CHẠY`;
    }catch(e){
      $('#engineDot').className='dot bad';
      $('#engineText').textContent='0 DEVICE • 0 ĐANG CHẠY';
    }

    document.querySelectorAll('.device').forEach(box=>{
      const id=box.dataset.device, s=status.find(x=>x.device_id===id), badge=box.querySelector('.autoState'), info=box.querySelector('.runningInfo');
      const running=isRunning(s);
      if(badge){
        badge.className=`autoState ${running?'running':s?'idle':'unknown'}`;
        badge.textContent=running?'ĐANG CHẠY':'DỪNG';
      }
      const start=box.querySelector('.start'), stop=box.querySelector('.stop');
      if(start) start.disabled=running;
      if(stop) stop.disabled=!running;
      if(info){
        if(running){
          const fid=s&&s.function_id!=null?`#${s.function_id} · `:'';
          info.textContent=`ĐANG CHẠY: ${fid}${(s&&s.func_text)||''}`.trim();
        }else info.textContent='DỪNG';
      }
    });

    document.querySelectorAll('.deviceTab').forEach(tab=>{
      const id=tab.dataset.id, s=status.find(x=>x.device_id===id), running=isRunning(s);
      const el=tab.querySelector('.navAuto');
      if(el){el.textContent=running?'ĐANG CHẠY':'DỪNG';el.className=`navAuto ${running?'running':''}`;}
    });
    await refreshLogs();
  };

  // app.js created its first interval before this compatibility layer loaded.
  // Replace that one interval with the clean status function; no extra polling.
  if(statusTimer) clearInterval(statusTimer);
  statusTimer=setInterval(refreshStatus,1000);

  // Re-render once so any old markup created during initial boot is replaced.
  Promise.resolve().then(async()=>{
    try{
      const title=document.querySelector('header > div:first-child > b');
      if(title){
        const version=title.querySelector('.version');
        title.childNodes[0].nodeValue='AUTO KVTM ';
        if(version) version.textContent='v0.10.5';
      }
      await loadEngineAndFunctions();
      await renderDevices();
    }catch{}
  });
})();
