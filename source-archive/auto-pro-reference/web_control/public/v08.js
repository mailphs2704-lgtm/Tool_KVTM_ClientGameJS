'use strict';
(() => {
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const wait=ms=>new Promise(r=>setTimeout(r,ms));
  const api=async(url,opt={})=>{const r=await fetch(url,{cache:'no-store',...opt,headers:{'Content-Type':'application/json',...(opt.headers||{})}});let j={};try{j=await r.json()}catch{}if(!r.ok)throw Error(j.error||`HTTP ${r.status}`);return j;};

  function username(){try{return (typeof me!=='undefined'&&me&&me.username)||'local';}catch{return 'local';}}
  function favKey(){return `auto-kvtm:favorites:v1:${username()}`;}
  function selectedKey(deviceId){return `auto-kvtm:selected:v1:${username()}:${deviceId}`;}
  function loadFavs(){try{const a=JSON.parse(localStorage.getItem(favKey())||'[]');return new Set(Array.isArray(a)?a.map(String):[]);}catch{return new Set();}}
  function saveFavs(set){localStorage.setItem(favKey(),JSON.stringify([...set]));}
  function getFunctions(){try{return Array.isArray(functions)?functions:[];}catch{return [];}}
  function optionKey(f){return String(f.option_index);}
  function textOf(f){return `#${f.id} · ${f.label}`;}
  function findByOption(value){return getFunctions().find(f=>optionKey(f)===String(value));}

  function updateSelectedInfo(card){
    const sel=q('.func',card), selected=q('.selectedFunc',card), desc=q('.funcDesc',card); if(!sel)return;
    const f=findByOption(sel.value);
    if(!f){
      if(selected)selected.textContent='CHƯA CHỌN CHỨC NĂNG';
      if(desc)desc.textContent='Chọn một chức năng trong menu rồi bấm START.';
      return;
    }
    if(selected)selected.textContent=`ĐÃ CHỌN: #${f.id} · ${f.label}`;
    if(desc){const d=(f.description||[]).slice(0,4).join(' • ');desc.textContent=`${f.method||''}${d?` • ${d}`:''}`;}
  }

  function sortedFunctions(){
    const favs=loadFavs();
    return getFunctions().map((f,i)=>({f,i,fav:favs.has(optionKey(f))}))
      .sort((a,b)=>Number(b.fav)-Number(a.fav)||a.i-b.i)
      .map(x=>x.f);
  }

  function renderMenu(card){
    const picker=q('.funcPicker',card), menu=q('.funcMenu',card), sel=q('.func',card); if(!picker||!menu||!sel)return;
    const favs=loadFavs(), current=String(sel.value||'');
    const rows=sortedFunctions();
    menu.innerHTML=rows.map(f=>{
      const key=optionKey(f), fav=favs.has(key), selected=key===current;
      return `<div class="funcMenuRow ${fav?'favorite':''} ${selected?'selected':''}" data-option="${esc(key)}">
        <button type="button" class="funcStar ${fav?'on':''}" title="${fav?'Bỏ ưu tiên':'Đưa lên đầu danh sách'}" aria-label="${fav?'Bỏ ưu tiên':'Đưa lên đầu danh sách'}">${fav?'★':'☆'}</button>
        <button type="button" class="funcChoice"><span class="funcId">#${esc(f.id)}</span><span class="funcLabel">${esc(f.label)}</span></button>
      </div>`;
    }).join('');

    qa('.funcMenuRow',menu).forEach(row=>{
      const key=String(row.dataset.option);
      q('.funcChoice',row).onclick=()=>{
        sel.value=key;
        localStorage.setItem(selectedKey(card.dataset.device||'device'),key);
        sel.dispatchEvent(new Event('change',{bubbles:true}));
        updateSelectedInfo(card);
        updateTrigger(card);
        picker.classList.remove('open');
        renderMenu(card);
      };
      q('.funcStar',row).onclick=e=>{
        e.preventDefault();e.stopPropagation();
        const favs=loadFavs();
        if(favs.has(key))favs.delete(key);else favs.add(key);
        saveFavs(favs);
        renderMenu(card);
        updateTrigger(card);
      };
    });
  }

  function updateTrigger(card){
    const sel=q('.func',card), trigger=q('.funcPickerTrigger',card); if(!sel||!trigger)return;
    const f=findByOption(sel.value), favs=loadFavs();
    if(!f){trigger.innerHTML='<span class="funcTriggerText">Chọn chức năng</span><span class="funcChevron">⌄</span>';return;}
    const star=favs.has(optionKey(f))?'★ ':'';
    trigger.innerHTML=`<span class="funcTriggerText"><span class="funcTriggerId">#${esc(f.id)}</span> ${star}${esc(f.label)}</span><span class="funcChevron">⌄</span>`;
  }

  function restoreSelection(card){
    const sel=q('.func',card);if(!sel)return;
    const remembered=String(localStorage.getItem(selectedKey(card.dataset.device||'device'))||sel.value||'');
    if(remembered&&getFunctions().some(f=>optionKey(f)===remembered))sel.value=remembered;
    else if(!sel.value&&getFunctions().length)sel.value=optionKey(getFunctions()[0]);
    updateSelectedInfo(card);updateTrigger(card);renderMenu(card);
  }

  function buildPicker(card){
    const box=q('.functionBox',card), sel=q('.func',card);if(!box||!sel)return;
    if(card.dataset.v08picker==='1')return;card.dataset.v08picker='1';

    const search=q('.funcSearch',card);if(search)search.remove();
    qa('.favoriteTools',card).forEach(x=>x.remove());

    sel.removeAttribute('size');sel.multiple=false;sel.classList.add('funcNativeHidden');

    const picker=document.createElement('div');
    picker.className='funcPicker';
    picker.innerHTML='<button type="button" class="funcPickerTrigger"><span class="funcTriggerText">Chọn chức năng</span><span class="funcChevron">⌄</span></button><div class="funcMenu"></div>';
    sel.before(picker);

    const trigger=q('.funcPickerTrigger',picker);
    trigger.onclick=e=>{e.preventDefault();e.stopPropagation();picker.classList.toggle('open');if(picker.classList.contains('open'))renderMenu(card);};
    picker.onclick=e=>e.stopPropagation();

    sel.addEventListener('change',()=>{if(sel.value)localStorage.setItem(selectedKey(card.dataset.device||'device'),String(sel.value));updateSelectedInfo(card);updateTrigger(card);renderMenu(card);});
    restoreSelection(card);
    wireExactStart(card,sel);
  }

  function wireExactStart(card,sel){
    const start=q('.start',card);if(!start)return;
    start.onclick=async()=>{
      const f=findByOption(sel.value);if(!f)return alert('Hãy chọn một chức năng trước khi START.');
      try{
        start.disabled=true;
        const result=await api('/api/auto/start-v08',{method:'POST',body:JSON.stringify({device_id:card.dataset.device,function_id:Number(f.id),option_index:Number(f.option_index),label:String(f.label)})});
        if(result&&Number.isFinite(Number(result.selected_option_index))){
          const accepted=String(result.selected_option_index);localStorage.setItem(selectedKey(card.dataset.device||'device'),accepted);sel.value=accepted;updateSelectedInfo(card);updateTrigger(card);renderMenu(card);
        }
        await wait(350);try{if(typeof refreshStatus==='function')await refreshStatus();}catch{}
      }catch(e){alert(e.message)}finally{try{if(typeof refreshStatus==='function')await refreshStatus();}catch{start.disabled=false}}
    };
  }

  function improveOptionsError(card){
    const host=q('.auxOptions',card);if(!host)return;
    if(/not found/i.test(host.textContent||''))host.innerHTML='<span class="err">Bridge Tùy chọn cũ đang bị Web cũ chiếm port. Đóng cửa sổ RUN_WEB và RUN_LOCAL cũ, sau đó mở lại.</span>';
  }

  function scan(){qa('.device').forEach(card=>{buildPicker(card);improveOptionsError(card);});}
  const root=document.getElementById('devices');if(root)new MutationObserver(scan).observe(root,{childList:true,subtree:true});
  document.addEventListener('click',()=>qa('.funcPicker.open').forEach(x=>x.classList.remove('open')));
  scan();
})();
