'use strict';
(() => {
  function syncFixedAdminUi(){
    const who=document.getElementById('who');
    const btn=document.getElementById('pwdBtn');
    if(!who||!btn)return;
    const isFixedAdmin=/^admin\s*·\s*admin\b/i.test(String(who.textContent||'').trim());
    btn.classList.toggle('hidden',isFixedAdmin);
    if(isFixedAdmin) btn.title='Admin dùng mật khẩu cố định do chủ hệ thống đặt';
  }
  const who=document.getElementById('who');
  if(who)new MutationObserver(syncFixedAdminUi).observe(who,{childList:true,subtree:true,characterData:true});
  syncFixedAdminUi();
  setInterval(syncFixedAdminUi,1500);
})();
