'use strict';
(() => {
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const api=async(url,opt={})=>{const r=await fetch(url,{cache:'no-store',...opt,headers:{'Content-Type':'application/json',...(opt.headers||{})}});let j={};try{j=await r.json()}catch{}if(!r.ok)throw Error(j.error||`HTTP ${r.status}`);return j;};

  async function loadOptions(card){
    const host=q('.auxOptions',card); if(!host)return;
    if(host.dataset.busy==='1')return; host.dataset.busy='1';
    try{
      const r=await api('/api/options'); const opts=Array.isArray(r.options)?r.options:[];
      if(!opts.length){host.innerHTML='<span class="muted">AUTO chưa trả về công tắc Tùy chọn.</span>';return;}
      host.innerHTML=opts.map(o=>`<label class="auxToggle ${o.enabled?'on':''}" data-key="${esc(o.key)}"><input type="checkbox" ${o.enabled?'checked':''}><span class="switchTrack"><span class="switchKnob"></span></span><span class="auxLabel">${esc(o.label)}${o.has_popup?' <i title="Có popup cấu hình chi tiết trong AUTO">⚙</i>':''}</span></label>`).join('');
      qa('.auxToggle',host).forEach(row=>{const input=q('input',row);input.onchange=async()=>{const wanted=input.checked;input.disabled=true;row.classList.add('saving');try{const x=await api('/api/options',{method:'POST',body:JSON.stringify({key:row.dataset.key,enabled:wanted})});input.checked=!!x.enabled;row.classList.toggle('on',!!x.enabled)}catch(e){input.checked=!wanted;row.classList.toggle('on',input.checked);alert(e.message)}finally{input.disabled=false;row.classList.remove('saving')}};});
    }catch(e){host.innerHTML=`<span class="err">Không đọc được Tùy chọn AUTO: ${esc(e.message)}</span>`}
    finally{host.dataset.busy='0'}
  }

  function enhance(card){
    if(!card||card.dataset.v07==='1')return; card.dataset.v07='1';
    const outer=q('.screenOuter',card), wrap=q('.screenWrap',card), toolbar=q('.screenToolbar',card);
    if(outer&&wrap&&toolbar){
      const stats=q('.streamStats',wrap)||q('.streamStats',card); if(stats){const live=q('.liveState',toolbar); live?.after(stats);}
      const handle=q('.resizeHandle',wrap)||q('.resizeHandle',card); if(handle){handle.textContent='↘ Kéo đổi cỡ';handle.title='Giữ và kéo ngang để phóng to / thu nhỏ';toolbar.append(handle);}
      wrap.after(toolbar);
      const label=q('.viewSizeLabel',outer); if(label){label.innerHTML=`VIEW ONLY • <b class="viewPx">${q('.viewPx',label)?.textContent||''}</b> • thanh trạng thái nằm ngoài video, không che hình`;toolbar.after(label);}
    }
    const controls=q('.controls',card), running=q('.runningInfo',card);
    if(controls&&!q('.auxBox',card)){
      const el=document.createElement('div');el.className='auxBox';el.innerHTML='<div class="row between"><b>Tùy chọn AUTO</b><button class="reloadOptions secondary" type="button">↻ Đồng bộ</button></div><div class="auxOptions"><span class="muted">Đang đọc công tắc thật từ launcher...</span></div><div class="auxHint muted">Công tắc đọc/ghi trực tiếp checkbox_vars của AUTO. Mục ⚙ giữ cấu hình popup đã chọn trong launcher; thay đổi áp dụng chắc chắn từ lần START tiếp theo.</div>';
      running?.after(el); q('.reloadOptions',el).onclick=()=>loadOptions(card); loadOptions(card);
    }
  }

  function scan(){qa('.device').forEach(enhance)}
  const root=document.getElementById('devices'); if(root)new MutationObserver(scan).observe(root,{childList:true,subtree:true});
  scan();
})();
