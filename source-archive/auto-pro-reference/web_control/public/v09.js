'use strict';
(() => {
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const api=async(url,opt={})=>{const r=await fetch(url,{cache:'no-store',...opt,headers:{'Content-Type':'application/json',...(opt.headers||{})}});let j={};try{j=await r.json()}catch{}if(!r.ok)throw Error(j.error||`HTTP ${r.status}`);return j;};

  function slotForRow(row){return row?.closest?.('.auxSettingSlot')||null;}
  function panelForRow(row){return q('.subSettings',slotForRow(row));}

  function closeOtherPanels(card,except=null){
    qa('.auxSettingSlot',card).forEach(slot=>{
      const panel=q('.subSettings',slot), row=q('.auxToggle',slot);
      if(panel!==except){panel?.classList.add('hidden');slot.classList.remove('isOpen');row?.classList.remove('settingsOpen');}
    });
  }

  function ensureSlot(row){
    if(!row)return null;
    let slot=slotForRow(row);
    if(slot)return slot;
    slot=document.createElement('div');
    slot.className='auxSettingSlot';
    row.before(slot);
    slot.append(row);
    return slot;
  }

  function settingsPanel(card,row){
    const slot=ensureSlot(row); if(!slot)return null;
    let panel=q('.subSettings',slot);
    if(!panel){
      panel=document.createElement('div');
      panel.className='subSettings hidden';
      panel.dataset.key=row.dataset.key||'';
      panel.innerHTML='<div class="subSettingsHead"><div><b class="subSettingsTitle">Cấu hình</b><div class="muted subSettingsSource"></div></div><button type="button" class="subSettingsClose secondary" aria-label="Đóng cấu hình">×</button></div><div class="subSettingsBody"></div><div class="subSettingsActions"><button type="button" class="subSettingsSave">Lưu</button><button type="button" class="subSettingsCancel secondary">Hủy</button></div>';
      slot.append(panel);
      q('.subSettingsClose',panel).onclick=()=>closeSettings(card,panel,true);
      q('.subSettingsCancel',panel).onclick=()=>closeSettings(card,panel,true);
      q('.subSettingsSave',panel).onclick=()=>saveSettings(card,panel);
    }
    return panel;
  }

  function fieldHtml(f,index){
    const label=esc(f.label||`Setting ${index+1}`), disabled=f.disabled?'disabled':'';
    if(f.type==='boolean')return `<label class="settingBool settingField" data-id="${esc(f.id)}" data-type="boolean"><input type="checkbox" ${f.value?'checked':''} ${disabled}><span>${label}</span></label>`;
    if(f.type==='select'){
      const opts=(f.options||[]).map(v=>`<option value="${esc(v)}" ${String(v)===String(f.value)?'selected':''}>${esc(v)}</option>`).join('');
      return `<label class="settingField" data-id="${esc(f.id)}" data-type="select"><span>${label}</span><select ${disabled}>${opts}</select></label>`;
    }
    if(f.type==='radio')return `<label class="settingBool settingField" data-id="${esc(f.id)}" data-type="radio"><input type="radio" name="popupRadio" value="${esc(f.value)}" ${f.checked?'checked':''} ${disabled}><span>${label}</span></label>`;
    const type=f.type==='number'?'number':'text';
    return `<label class="settingField" data-id="${esc(f.id)}" data-type="${esc(f.type||'text')}"><span>${label}</span><input type="${type}" value="${esc(f.value??'')}" ${disabled}></label>`;
  }

  function renderSettings(card,row,panel,data){
    const slot=slotForRow(row);
    panel.dataset.key=data.key||row.dataset.key||'';
    q('.subSettingsTitle',panel).textContent=data.title||'Cấu hình';
    q('.subSettingsSource',panel).textContent='Thiết lập của mục đang chọn';
    const body=q('.subSettingsBody',panel);
    const fields=Array.isArray(data.fields)?data.fields:[];
    body.innerHTML=fields.length?fields.map(fieldHtml).join(''):'<div class="muted inlineSettingEmpty">Không có trường cấu hình.</div>';
    closeOtherPanels(card,panel);
    panel.classList.remove('hidden');
    slot?.classList.add('isOpen');
    row.classList.add('settingsOpen');
  }

  async function openSettings(card,row){
    const key=row?.dataset.key||''; if(!key)return;
    const panel=settingsPanel(card,row); if(!panel)return;
    const slot=slotForRow(row);
    if(!panel.classList.contains('hidden')){await closeSettings(card,panel,true);return;}
    closeOtherPanels(card,panel);
    panel.classList.remove('hidden');
    slot?.classList.add('isOpen');
    row.classList.add('settingsOpen');
    q('.subSettingsTitle',panel).textContent='Đang tải cấu hình...';
    q('.subSettingsSource',panel).textContent='';
    q('.subSettingsBody',panel).innerHTML='<div class="inlineSettingLoading">Đang đọc...</div>';
    try{
      const data=await api(`/api/options/settings?key=${encodeURIComponent(key)}`);
      renderSettings(card,row,panel,data);
    }catch(e){
      q('.subSettingsTitle',panel).textContent='Không đọc được cấu hình';
      q('.subSettingsBody',panel).innerHTML=`<div class="err inlineSettingError">${esc(e.message)}</div>`;
    }
  }

  function collectFields(panel){
    return qa('.settingField',panel).map(row=>{
      const type=row.dataset.type,id=row.dataset.id;
      if(type==='boolean'){const input=q('input',row);return {id,type,value:!!input?.checked};}
      if(type==='radio'){const input=q('input',row);return {id,type,value:input?.value||'',checked:!!input?.checked};}
      const control=q('input,select',row);return {id,type,value:control?.value??''};
    });
  }

  async function saveSettings(card,panel){
    const key=panel?.dataset.key; if(!panel||!key)return;
    const btn=q('.subSettingsSave',panel); btn.disabled=true; btn.textContent='Đang lưu...';
    try{
      await api('/api/options/settings',{method:'POST',body:JSON.stringify({key,action:'save',fields:collectFields(panel)})});
      const slot=panel.closest('.auxSettingSlot'),row=q('.auxToggle',slot);
      panel.classList.add('hidden');slot?.classList.remove('isOpen');
      if(row){row.classList.add('configured');row.classList.remove('settingsOpen');}
    }catch(e){alert(e.message)}finally{btn.disabled=false;btn.textContent='Lưu';}
  }

  async function closeSettings(card,panel,cancel){
    const key=panel?.dataset.key; if(!panel)return;
    if(cancel&&key){try{await api('/api/options/settings',{method:'POST',body:JSON.stringify({key,action:'cancel',fields:[]})});}catch{}}
    const slot=panel.closest('.auxSettingSlot'),row=q('.auxToggle',slot);
    panel.classList.add('hidden');slot?.classList.remove('isOpen');row?.classList.remove('settingsOpen');
  }

  function enhanceOptionRows(card){
    const host=q('.auxOptions',card); if(!host)return;
    qa('.auxToggle',host).forEach(row=>{
      const gear=q('.auxLabel i',row);
      const hasPopup=!!gear||row.dataset.hasSettings==='1';
      if(gear)gear.remove();
      if(!hasPopup)return;
      row.dataset.hasSettings='1';row.classList.add('hasSettings');
      ensureSlot(row);
      if(!q('.settingsBtn',row)){
        const btn=document.createElement('button');
        btn.type='button';btn.className='settingsBtn secondary';
        btn.innerHTML='<span class="settingsGear">⚙</span><span class="settingsText">Cấu hình</span><span class="settingsChevron">⌄</span>';
        btn.onclick=e=>{e.preventDefault();e.stopPropagation();openSettings(card,row);};
        row.append(btn);
      }
    });
  }

  function scan(){qa('.device').forEach(enhanceOptionRows)}
  const root=document.getElementById('devices');
  if(root)new MutationObserver(scan).observe(root,{childList:true,subtree:true});
  scan();
})();
