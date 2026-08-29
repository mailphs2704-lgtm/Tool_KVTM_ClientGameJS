'use strict';
(() => {
  function apply(){
    document.querySelectorAll('.functionContextBox').forEach(panel=>{
      const btn=panel.querySelector('.reloadFunctionActions');
      if(btn && btn.textContent!=='Tải thao tác ↻') btn.textContent='Tải thao tác ↻';

      const muted=panel.querySelector('.functionContextHead .muted');
      const wanted='Đọc callback có sẵn trong AUTO, không mở menu desktop.';
      if(muted && muted.textContent!==wanted) muted.textContent=wanted;

      const host=panel.querySelector('.functionActionButtons');
      // IMPORTANT: only replace the old placeholder once. The previous build
      // matched every string containing "Bấm", including the replacement
      // itself, causing MutationObserver -> innerHTML -> MutationObserver in an
      // endless loop that starved the main browser thread and hid device cards.
      if(host){
        const text=host.textContent||'';
        if(text.includes('Bấm “Đọc menu”') || text.includes('Đọc menu ↻')){
          host.innerHTML='<span class="muted">Bấm “Tải thao tác” để lấy các thao tác của chức năng đang chọn.</span>';
        }
      }
    });
  }

  const root=document.getElementById('devices');
  if(root)new MutationObserver(()=>apply()).observe(root,{childList:true,subtree:true});
  apply();
})();
