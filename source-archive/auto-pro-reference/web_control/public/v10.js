'use strict';
(() => {
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const norm=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/Đ/g,'D').toLowerCase();
  const api=async(url,opt={})=>{const r=await fetch(url,{cache:'no-store',...opt,headers:{'Content-Type':'application/json',...(opt.headers||{})}});let j={};try{j=await r.json()}catch{}if(!r.ok)throw Error(j.error||`HTTP ${r.status}`);return j;};
  const currentUser=()=>{try{return me?.username||'local'}catch{return 'local'}};
  const favoriteKey=()=>`auto-kvtm:favorites:v1:${currentUser()}`;

  function selectedFunction(card){
    const sel=q('.func',card); if(!sel||!sel.value)return null;
    try{return functions.find(f=>String(f.option_index)===String(sel.value))||null}catch{return null}
  }
  function syncFavoriteCache(optionIndex,isFavorite){
    try{
      let arr=JSON.parse(localStorage.getItem(favoriteKey())||'[]'); if(!Array.isArray(arr))arr=[];
      const set=new Set(arr.map(String)),k=String(optionIndex);
      if(isFavorite)set.add(k);else set.delete(k);
      localStorage.setItem(favoriteKey(),JSON.stringify([...set]));
    }catch{}
  }

  function ensurePanel(card){
    const box=q('.functionBox',card); if(!box)return null;
    let panel=q('.functionContextBox',box);
    if(panel)return panel;
    panel=document.createElement('div');panel.className='functionContextBox';
    panel.innerHTML=`
      <div class="row between functionContextHead"><div><b>Thao tác chức năng</b><div class="muted">Đọc trực tiếp menu chuột phải gốc của AUTO</div></div><button type="button" class="reloadFunctionActions secondary">↻</button></div>
      <div class="functionActionButtons"><span class="muted">Chọn một chức năng để đọc menu...</span></div>
      <div class="functionActionResult hidden"></div>
      <div class="functionActionPopup hidden">
        <div class="row between"><div><b class="functionPopupTitle">Cấu hình</b><div class="muted functionPopupSource">Popup gốc của AUTO</div></div><button type="button" class="functionPopupClose secondary">Đóng</button></div>
        <div class="functionPopupFields"></div>
        <div class="row functionPopupActions"><button type="button" class="functionPopupSave">Lưu</button><button type="button" class="functionPopupCancel secondary">Hủy</button></div>
      </div>`;
    const desc=q('.funcDesc',box); if(desc)desc.after(panel); else box.append(panel);
    q('.reloadFunctionActions',panel).onclick=()=>loadActions(card,true);
    q('.functionPopupClose',panel).onclick=()=>closePopup(card,true);
    q('.functionPopupCancel',panel).onclick=()=>closePopup(card,true);
    q('.functionPopupSave',panel).onclick=()=>savePopup(card);
    return panel;
  }

  function showResult(card,html,kind='info'){
    const panel=ensurePanel(card),el=q('.functionActionResult',panel);if(!el)return;
    el.className=`functionActionResult ${kind}`;el.innerHTML=html;el.classList.remove('hidden');
  }
  function clearResult(card){const el=q('.functionActionResult',ensurePanel(card));if(el){el.classList.add('hidden');el.innerHTML='';}}

  async function loadActions(card,force=false){
    const panel=ensurePanel(card),host=q('.functionActionButtons',panel),f=selectedFunction(card);
    if(!f){host.innerHTML='<span class="muted">Chọn một chức năng để đọc menu chuột phải.</span>';q('.functionActionPopup',panel)?.classList.add('hidden');return;}
    const cacheKey=String(f.option_index);
    if(!force&&panel.dataset.loadedOption===cacheKey)return;
    panel.dataset.loadedOption=cacheKey;host.innerHTML='<span class="muted">Đang đọc menu chuột phải thật...</span>';
    try{
      const data=await api(`/api/function-actions?option_index=${encodeURIComponent(f.option_index)}`);
      if(String(selectedFunction(card)?.option_index)!==cacheKey)return;
      const actions=Array.isArray(data.actions)?data.actions:[];
      if(!actions.length){host.innerHTML='<span class="muted">Chức năng này không có thao tác chuột phải khả dụng.</span>';return;}
      host.innerHTML=actions.map(a=>`<button type="button" class="functionActionBtn ${a.danger?'danger':''}" data-action="${esc(a.id)}" ${a.enabled?'':'disabled'}>${esc(a.label)}</button>`).join('');
      const fav=actions.find(a=>a.id==='favorite');
      if(fav){const isFavorite=/bo\s+yeu\s+thich/i.test(norm(fav.label));syncFavoriteCache(f.option_index,isFavorite);}
      qa('.functionActionBtn',host).forEach(btn=>btn.onclick=()=>runAction(card,btn.dataset.action,btn.textContent));
    }catch(e){host.innerHTML=`<span class="err">${esc(e.message)}</span>`;}
  }

  async function runAction(card,actionId,label){
    const f=selectedFunction(card);if(!f)return;
    let confirmed=false;
    if(actionId==='delete'){
      confirmed=window.confirm(`XÓA chức năng này khỏi AUTO?\n\n#${f.id} · ${f.label}\n\nTheo menu gốc: Delete - KHÔNG hoàn Point. Thao tác không thể hoàn tác từ web.`);
      if(!confirmed)return;
    }
    const panel=ensurePanel(card),buttons=qa('.functionActionBtn',panel);buttons.forEach(x=>x.disabled=true);
    showResult(card,`<span class="muted">Đang gọi thao tác gốc: ${esc(label)}...</span>`);
    try{
      const data=await api('/api/function-actions',{method:'POST',body:JSON.stringify({option_index:Number(f.option_index),action_id:actionId,confirm:confirmed})});
      if(data.kind==='popup')renderPopup(card,data);
      else if(data.kind==='message'){
        const messages=(data.messages||[]).map(m=>`<div class="functionMessage"><b>${esc(m.title||label)}</b><div>${esc(m.message||'')}</div></div>`).join('');
        showResult(card,messages||'<div>Đã thực hiện.</div>','message');
      } else {
        showResult(card,`<b>Đã thực hiện:</b> ${esc(label)}`,'success');
      }
      if(actionId==='favorite'){
        panel.dataset.loadedOption='';await loadActions(card,true);
        try{q('.funcSearch',card)?.dispatchEvent(new Event('input',{bubbles:true}));}catch{}
      }
      if(actionId==='delete'){
        // Reload the live catalog because the original callback may remove a
        // user-created function from the launcher immediately.
        try{if(typeof loadEngineAndFunctions==='function')await loadEngineAndFunctions();}catch{}
        try{if(typeof renderDevices==='function')await renderDevices();}catch{}
      }
    }catch(e){showResult(card,`<span class="err">${esc(e.message)}</span>`,'error');}
    finally{buttons.forEach(x=>x.disabled=false);}
  }

  function fieldHtml(f,index,session){
    const label=esc(f.label||`Setting ${index+1}`),disabled=f.disabled?'disabled':'';
    if(f.type==='boolean')return `<label class="ctxField ctxBool" data-id="${esc(f.id)}" data-type="boolean"><input type="checkbox" ${f.value?'checked':''} ${disabled}><span>${label}</span></label>`;
    if(f.type==='radio')return `<label class="ctxField ctxBool" data-id="${esc(f.id)}" data-type="radio"><input type="radio" name="ctxRadio-${esc(session)}" value="${esc(f.value)}" ${f.checked?'checked':''} ${disabled}><span>${label}</span></label>`;
    if(f.type==='select'){
      const opts=(f.options||[]).map(v=>`<option value="${esc(v)}" ${String(v)===String(f.value)?'selected':''}>${esc(v)}</option>`).join('');
      return `<label class="ctxField" data-id="${esc(f.id)}" data-type="select"><span>${label}</span><select ${disabled}>${opts}</select></label>`;
    }
    if(f.type==='multiselect'){
      const selected=new Set((f.selected||[]).map(Number));
      const opts=(f.options||[]).map((v,i)=>`<option value="${i}" ${selected.has(i)?'selected':''}>${esc(v)}</option>`).join('');
      return `<label class="ctxField ctxWide" data-id="${esc(f.id)}" data-type="multiselect"><span>${label||'Danh sách lựa chọn'} <i>Ctrl/Shift để chọn nhiều</i></span><select multiple size="${Math.min(12,Math.max(5,(f.options||[]).length))}" ${disabled}>${opts}</select></label>`;
    }
    if(f.type==='tree'){
      const opts=(f.rows||[]).map(r=>`<option value="${esc(r.iid)}" ${r.selected?'selected':''}>${esc([r.text,...(r.values||[])].filter(Boolean).join(' · '))}</option>`).join('');
      return `<label class="ctxField ctxWide" data-id="${esc(f.id)}" data-type="tree"><span>${label||'Danh sách'}</span><select multiple size="10" ${disabled}>${opts}</select></label>`;
    }
    if(f.type==='textarea')return `<label class="ctxField ctxWide" data-id="${esc(f.id)}" data-type="textarea"><span>${label}</span><textarea rows="5" ${disabled}>${esc(f.value??'')}</textarea></label>`;
    const type=f.type==='number'?'number':'text';
    return `<label class="ctxField" data-id="${esc(f.id)}" data-type="${esc(f.type||'text')}"><span>${label}</span><input type="${type}" value="${esc(f.value??'')}" ${disabled}></label>`;
  }

  function renderPopup(card,data){
    const panel=ensurePanel(card),pop=q('.functionActionPopup',panel),fields=q('.functionPopupFields',pop);
    pop.dataset.session=data.session_id||'';pop.dataset.action=data.action_id||'';
    q('.functionPopupTitle',pop).textContent=data.title||'Cấu hình chức năng';
    q('.functionPopupSource',pop).textContent=`#${data.function_id??''} · ${data.function_label||''} · popup gốc đang được giữ ẩn`;
    const arr=Array.isArray(data.fields)?data.fields:[];
    fields.innerHTML=arr.length?arr.map((f,i)=>fieldHtml(f,i,data.session_id)).join(''):'<div class="muted ctxWide">Popup gốc đã mở nhưng chưa phát hiện control nhập liệu. Nếu bạn thấy popup này trên AUTO có control đặc biệt, gửi ảnh để map thêm.</div>';
    pop.classList.remove('hidden');clearResult(card);pop.scrollIntoView({behavior:'smooth',block:'nearest'});
  }

  function collectPopup(pop){
    return qa('.ctxField',pop).map(row=>{
      const id=row.dataset.id,type=row.dataset.type;
      if(type==='boolean'){return {id,type,value:!!q('input',row)?.checked};}
      if(type==='radio'){const input=q('input',row);return {id,type,value:input?.value||'',checked:!!input?.checked};}
      if(type==='multiselect'){return {id,type,selected:[...q('select',row).selectedOptions].map(o=>Number(o.value))};}
      if(type==='tree'){return {id,type,selected:[...q('select',row).selectedOptions].map(o=>o.value)};}
      const ctl=q('input,select,textarea',row);return {id,type,value:ctl?.value??''};
    });
  }
  async function savePopup(card){
    const pop=q('.functionActionPopup',ensurePanel(card)),sid=pop?.dataset.session;if(!sid)return;
    const btn=q('.functionPopupSave',pop);btn.disabled=true;btn.textContent='Đang lưu...';
    try{
      await api('/api/function-actions',{method:'POST',body:JSON.stringify({mode:'popup',session_id:sid,action:'save',fields:collectPopup(pop)})});
      pop.classList.add('hidden');showResult(card,'<b>Đã lưu bằng nút Lưu/Xác nhận gốc của AUTO.</b>','success');await loadActions(card,true);
    }catch(e){showResult(card,`<span class="err">${esc(e.message)}</span>`,'error');}
    finally{btn.disabled=false;btn.textContent='Lưu';}
  }
  async function closePopup(card,cancel){
    const pop=q('.functionActionPopup',ensurePanel(card)),sid=pop?.dataset.session;if(!pop)return;
    if(cancel&&sid){try{await api('/api/function-actions',{method:'POST',body:JSON.stringify({mode:'popup',session_id:sid,action:'cancel',fields:[]})});}catch{}}
    pop.dataset.session='';pop.classList.add('hidden');
  }

  function enhance(card){
    if(!card)return;const panel=ensurePanel(card),sel=q('.func',card);if(!sel)return;
    if(sel.dataset.v10wired!=='1'){
      sel.dataset.v10wired='1';
      sel.addEventListener('change',()=>{panel.dataset.loadedOption='';q('.functionActionPopup',panel)?.classList.add('hidden');clearResult(card);loadActions(card,true);});
    }
    loadActions(card,false);
  }
  function scan(){qa('.device').forEach(enhance)}
  const root=document.getElementById('devices');if(root)new MutationObserver(scan).observe(root,{childList:true,subtree:true});
  scan();setInterval(()=>{if(!document.hidden)scan();},1200);
})();
