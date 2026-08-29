from __future__ import annotations

import json
import secrets
import threading
import time
import unicodedata
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import local_bridge

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "local_data" / "bridge_token.txt"
HOST = "127.0.0.1"
PORT = 8769
_server = None
_thread = None
_popup_sessions = {}


def _norm(value):
    s = unicodedata.normalize("NFD", str(value or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join(s.lower().replace("đ", "d").split())


def _token():
    try:
        value = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    except Exception:
        pass
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(value, encoding="utf-8")
    return value


def _call_tk(app, fn, timeout=5.0):
    done = threading.Event()
    box = {}

    def runner():
        try:
            box["result"] = fn()
        except Exception as exc:
            box["error"] = str(exc)
        finally:
            done.set()

    app.after(0, runner)
    if not done.wait(timeout):
        raise TimeoutError("AUTO GUI không trả lời kịp")
    if "error" in box:
        raise RuntimeError(box["error"])
    return box.get("result")


def _walk(widget):
    yield widget
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield from _walk(child)


def _catalog_row(app, option_index):
    rows = local_bridge._catalog(app)
    try:
        option_index = int(option_index)
    except Exception:
        raise ValueError("option_index không hợp lệ")
    row = next((x for x in rows if int(x.get("option_index", -1)) == option_index), None)
    if row is None:
        raise ValueError("Chức năng không còn tồn tại trong FUNCTION_OPTIONS thật")
    return row


def _select_main_function(app, option_index):
    row = _catalog_row(app, option_index)
    local_bridge._select_function(app, int(row["id"]), str(row["label"]))
    box = getattr(app, "function_list", None)
    if box is None:
        raise RuntimeError("AUTO chưa tạo function_list")
    try:
        selected = list(box.curselection())
        index = int(selected[0]) if selected else int(getattr(app, "last_function_index", 0) or 0)
    except Exception:
        index = int(getattr(app, "last_function_index", 0) or 0)
    return row, box, index


def _menu_entries(menu):
    out = []
    try:
        end = menu.index("end")
    except Exception:
        return out
    if end is None:
        return out
    for i in range(int(end) + 1):
        try:
            typ = str(menu.type(i) or "")
        except Exception:
            continue
        if typ == "separator":
            continue
        try:
            label = str(menu.entrycget(i, "label") or "").strip()
        except Exception:
            label = ""
        if not label:
            continue
        try:
            state = str(menu.entrycget(i, "state") or "normal")
        except Exception:
            state = "normal"
        out.append({"index": i, "label": label, "state": state, "type": typ})
    return out


def _action_id(label):
    n = _norm(label)
    if "yeu thich" in n:
        return "favorite"
    if "thoi gian cho" in n:
        return "wait_time"
    if "vp xoa" in n or ("chon" in n and "xoa" in n and "kc" in n):
        return "delete_items_kc"
    if "chi tiet" in n:
        return "detail"
    if "khong hoan point" in n or "delete" in n:
        return "delete"
    # Keep unknown real menu actions visible for diagnostics, but do not let the
    # browser invoke arbitrary callbacks.
    return ""


def _find_context_menu(app):
    candidates = []
    for widget in _walk(app):
        try:
            if str(widget.winfo_class() or "").lower() != "menu":
                continue
        except Exception:
            continue
        entries = _menu_entries(widget)
        ids = [_action_id(x["label"]) for x in entries]
        score = sum(1 for x in ids if x)
        if score:
            candidates.append((score, len(entries), widget, entries))
    if not candidates:
        return None, []
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2], candidates[0][3]


def _open_context_menu(app, option_index):
    row, box, index = _select_main_function(app, option_index)
    try:
        bbox = box.bbox(index)
    except Exception:
        bbox = None
    x = 8
    y = 8
    if bbox:
        try:
            x = max(3, int(bbox[0]) + 8)
            y = max(3, int(bbox[1]) + max(3, int(bbox[3]) // 2))
        except Exception:
            pass

    # Generate the same right-click event as the desktop user. This keeps all
    # original menu construction logic, including per-function enabled states.
    try:
        box.event_generate("<Button-3>", x=x, y=y, rootx=box.winfo_rootx()+x, rooty=box.winfo_rooty()+y)
    except Exception:
        box.event_generate("<Button-3>", x=x, y=y)
    try:
        app.update_idletasks()
    except Exception:
        pass
    menu, entries = _find_context_menu(app)
    if menu is None:
        raise RuntimeError("Không tìm thấy menu chuột phải gốc của chức năng. Hãy mở tab Dashboard của AUTO rồi thử lại.")
    actions = []
    for entry in entries:
        aid = _action_id(entry["label"])
        if not aid:
            continue
        actions.append({
            "id": aid,
            "label": entry["label"],
            "enabled": entry.get("state") != "disabled",
            "danger": aid == "delete",
            "opens_settings": aid in {"wait_time", "delete_items_kc"},
        })
    try:
        menu.unpost()
    except Exception:
        pass
    return row, menu, entries, actions


def _toplevels(app):
    out = []
    for widget in _walk(app):
        if widget is app:
            continue
        try:
            if str(widget.winfo_class() or "").lower() == "toplevel":
                out.append(widget)
        except Exception:
            pass
    return out


def _popup_by_path(app, path):
    try:
        widget = app.nametowidget(path)
        return widget if int(widget.winfo_exists()) else None
    except Exception:
        return None


def _label_for(widget):
    try:
        own = str(widget.cget("text") or "").strip()
        if own:
            return own
    except Exception:
        pass
    try:
        siblings = list(widget.master.winfo_children())
        idx = siblings.index(widget)
        for sib in reversed(siblings[max(0, idx-4):idx]):
            try:
                text = str(sib.cget("text") or "").strip()
                cls = str(sib.winfo_class() or "").lower()
                if "label" in cls and text:
                    return text
            except Exception:
                pass
    except Exception:
        pass
    return ""


def _field(widget, app):
    try:
        cls = str(widget.winfo_class() or "").lower()
    except Exception:
        return None
    path = str(widget)
    label = _label_for(widget)
    try:
        state = str(widget.cget("state") or "normal").lower()
    except Exception:
        state = "normal"
    disabled = state == "disabled"

    if "combobox" in cls:
        try: values = [str(x) for x in list(widget.cget("values"))]
        except Exception: values = []
        try: value = str(widget.get())
        except Exception: value = ""
        return {"id":path,"type":"select","label":label,"value":value,"options":values,"disabled":disabled}
    if "checkbutton" in cls:
        try:
            var_name = str(widget.cget("variable") or "")
            value = str(app.getvar(var_name)).lower() in {"1","true","yes","on"}
        except Exception: value = False
        return {"id":path,"type":"boolean","label":label,"value":bool(value),"disabled":disabled}
    if "radiobutton" in cls:
        try:
            var_name = str(widget.cget("variable") or "")
            own = str(widget.cget("value"))
            checked = str(app.getvar(var_name)) == own
        except Exception: own,checked="",False
        return {"id":path,"type":"radio","label":label,"value":own,"checked":checked,"disabled":disabled}
    if "listbox" in cls:
        try:
            options = [str(widget.get(i)) for i in range(int(widget.size()))]
            selected = [int(x) for x in widget.curselection()]
        except Exception:
            options, selected = [], []
        return {"id":path,"type":"multiselect","label":label,"options":options,"selected":selected,"disabled":disabled}
    if "treeview" in cls:
        rows=[]
        try:
            chosen=set(widget.selection())
            for iid in widget.get_children():
                info=widget.item(iid) or {}
                text=str(info.get("text","") or "")
                vals=[str(x) for x in (info.get("values",()) or ())]
                rows.append({"iid":str(iid),"text":text,"values":vals,"selected":iid in chosen})
        except Exception:
            pass
        return {"id":path,"type":"tree","label":label,"rows":rows,"disabled":disabled}
    if "text" == cls or cls.endswith("text"):
        try: value=str(widget.get("1.0","end-1c"))
        except Exception: value=""
        return {"id":path,"type":"textarea","label":label,"value":value,"disabled":disabled}
    if "scale" in cls:
        try: value=widget.get()
        except Exception: value=0
        return {"id":path,"type":"number","label":label,"value":value,"disabled":disabled}
    if "spinbox" in cls:
        try: value=str(widget.get())
        except Exception: value=""
        try: values=[str(x) for x in list(widget.cget("values"))]
        except Exception: values=[]
        return {"id":path,"type":"select" if values else "text","label":label,"value":value,"options":values,"disabled":disabled}
    if cls in {"entry","tentry"} or cls.endswith("entry"):
        try: value=str(widget.get())
        except Exception: value=""
        return {"id":path,"type":"text","label":label,"value":value,"disabled":disabled}
    return None


def _button_info(widget):
    try:
        cls=str(widget.winfo_class() or "").lower()
        if "button" not in cls or "checkbutton" in cls or "radiobutton" in cls:
            return None
        text=str(widget.cget("text") or "").strip()
        return {"id":str(widget),"text":text} if text else None
    except Exception:
        return None


def _inspect_popup(app, popup, session_id, action_id, row):
    fields=[]; buttons=[]
    for widget in _walk(popup):
        if widget is popup: continue
        f=_field(widget,app)
        if f: fields.append(f)
        b=_button_info(widget)
        if b: buttons.append(b)
    try: title=str(popup.title() or row.get("label") or action_id)
    except Exception: title=str(row.get("label") or action_id)
    return {
        "ok":True,"kind":"popup","session_id":session_id,"action_id":action_id,
        "option_index":row.get("option_index"),"function_id":row.get("id"),"function_label":row.get("label"),
        "title":title,"fields":fields,"buttons":buttons,"source":"REAL_FUNCTION_CONTEXT_POPUP",
    }


def _choose_button(popup, action):
    save_words=("luu","xac nhan","dong y","ap dung","ok","save","apply","confirm")
    cancel_words=("huy","dong","cancel","close")
    candidates=[]
    for widget in _walk(popup):
        b=_button_info(widget)
        if b: candidates.append((widget,_norm(b["text"])))
    words=save_words if action=="save" else cancel_words
    for widget,text in candidates:
        if any(w in text for w in words): return widget
    if action=="save":
        for widget,text in candidates:
            if not any(w in text for w in cancel_words): return widget
    return None


def _set_widget(app, widget, item):
    cls=str(widget.winfo_class() or "").lower()
    value=item.get("value")
    if "checkbutton" in cls:
        app.setvar(str(widget.cget("variable") or ""),bool(value)); return
    if "radiobutton" in cls:
        if item.get("checked"):
            app.setvar(str(widget.cget("variable") or ""),str(widget.cget("value"))); return
        return
    if "listbox" in cls:
        widget.selection_clear(0,"end")
        for idx in item.get("selected",[]) or []:
            try: widget.selection_set(int(idx))
            except Exception: pass
        return
    if "treeview" in cls:
        iids=[str(x) for x in (item.get("selected",[]) or [])]
        widget.selection_set(iids); return
    if "text" == cls or cls.endswith("text"):
        widget.delete("1.0","end"); widget.insert("1.0","" if value is None else str(value)); return
    if "combobox" in cls or "scale" in cls:
        widget.set(value); return
    if "spinbox" in cls or cls in {"entry","tentry"} or cls.endswith("entry"):
        widget.delete(0,"end"); widget.insert(0,"" if value is None else str(value)); return


def _apply_popup(app, session_id, fields, action):
    session=_popup_sessions.get(str(session_id))
    if not session: raise RuntimeError("Phiên cấu hình đã hết hạn. Mở lại thao tác.")
    popup=_popup_by_path(app,session.get("popup",""))
    if popup is None:
        _popup_sessions.pop(str(session_id),None)
        raise RuntimeError("Popup gốc đã đóng. Mở lại thao tác.")
    for item in fields or []:
        wid=str(item.get("id") or "")
        if not wid: continue
        try:
            widget=app.nametowidget(wid)
            _set_widget(app,widget,item)
        except Exception as exc:
            raise RuntimeError(f"Không ghi được field {wid}: {exc}") from exc
    try: app.update_idletasks()
    except Exception: pass
    if action in {"save","cancel"}:
        button=_choose_button(popup,action)
        if button is not None:
            button.invoke()
        elif action=="cancel":
            popup.destroy()
        else:
            raise RuntimeError("Không tìm thấy nút Lưu/Xác nhận của popup gốc")
        _popup_sessions.pop(str(session_id),None)
        return {"ok":True,"kind":"done","action":action,"saved":action=="save"}
    row=session.get("row",{})
    return _inspect_popup(app,popup,str(session_id),session.get("action_id",""),row)


def _patch_messageboxes(confirm=False):
    """Capture common tkinter message boxes so context actions stay web-only."""
    try:
        import tkinter.messagebox as mb
    except Exception:
        return [], lambda: None
    captured=[]; originals={}
    names=("showinfo","showwarning","showerror","askyesno","askokcancel","askretrycancel","askquestion","askyesnocancel")
    for name in names:
        fn=getattr(mb,name,None)
        if fn is None: continue
        originals[name]=fn
        def make_handler(n):
            def handler(title=None,message=None,*args,**kwargs):
                captured.append({"method":n,"title":str(title or ""),"message":str(message or "")})
                if n in {"showinfo","showwarning","showerror"}: return "ok"
                if n=="askquestion": return "yes" if confirm else "no"
                if n=="askyesnocancel": return True if confirm else False
                return bool(confirm)
            return handler
        setattr(mb,name,make_handler(name))
    # Some recovered modules may have imported the functions directly.
    patched=[]
    for mod_name in ("gui","gui_tasks","gui_tab_add","gui_tab_mgmt","gui_popups"):
        try: mod=__import__(mod_name)
        except Exception: continue
        for name,orig in originals.items():
            try:
                if getattr(mod,name,None) is orig:
                    patched.append((mod,name,orig)); setattr(mod,name,getattr(mb,name))
            except Exception: pass
    def restore():
        for mod,name,orig in patched:
            try: setattr(mod,name,orig)
            except Exception: pass
        for name,orig in originals.items():
            try: setattr(mb,name,orig)
            except Exception: pass
    return captured,restore


def _invoke_action(app, option_index, action_id, confirm=False):
    row,menu,entries,actions=_open_context_menu(app,option_index)
    entry=None
    for e in entries:
        if _action_id(e.get("label"))==action_id:
            entry=e; break
    if entry is None:
        raise RuntimeError(f"Menu gốc không có thao tác {action_id}")
    if entry.get("state")=="disabled":
        raise RuntimeError(f"Thao tác đang bị khóa trong AUTO: {entry.get('label')}")
    if action_id=="delete" and not confirm:
        raise RuntimeError("Xóa yêu cầu xác nhận rõ ràng")

    before=set(str(x) for x in _toplevels(app))
    captured,restore=_patch_messageboxes(confirm=confirm)
    try:
        # Do not wait for the callback. Some original dialogs use wait_window;
        # Tk still runs a nested event loop, allowing this bridge to inspect it.
        def fire():
            try: menu.invoke(int(entry["index"]))
            except Exception as exc: print(f"[FUNCTION-ACTIONS] invoke {action_id}: {exc}")
        app.after(0,fire)

        popup_path=None
        deadline=time.time()+2.8
        while time.time()<deadline:
            def detect():
                fresh=[x for x in _toplevels(app) if str(x) not in before]
                return str(fresh[-1]) if fresh else None
            try: popup_path=_call_tk(app,detect,timeout=1.0)
            except Exception: popup_path=None
            if popup_path or captured: break
            time.sleep(0.06)

        if popup_path:
            def hide_read():
                popup=_popup_by_path(app,popup_path)
                if popup is None: raise RuntimeError("Popup vừa mở đã đóng")
                try:
                    popup.update_idletasks(); popup.withdraw(); popup.grab_release()
                except Exception: pass
                session_id=uuid.uuid4().hex
                _popup_sessions[session_id]={"popup":popup_path,"action_id":action_id,"row":row,"opened_at":time.time()}
                def expire():
                    sess=_popup_sessions.get(session_id)
                    if not sess: return
                    p=_popup_by_path(app,sess.get("popup",""))
                    if p is not None:
                        try: p.destroy()
                        except Exception: pass
                    _popup_sessions.pop(session_id,None)
                app.after(5*60*1000,expire)
                return _inspect_popup(app,popup,session_id,action_id,row)
            return _call_tk(app,hide_read)

        # Give direct actions (favorite/delete) a moment to update the list/data.
        time.sleep(0.18)
        if captured:
            return {"ok":True,"kind":"message","action_id":action_id,"messages":list(captured),"row":row}
        return {"ok":True,"kind":"done","action_id":action_id,"label":entry.get("label"),"row":row}
    finally:
        restore()
        try: menu.unpost()
        except Exception: pass


def _snapshot_actions(app, option_index):
    row,menu,entries,actions=_open_context_menu(app,option_index)
    return {"ok":True,"row":row,"actions":actions,"source":"REAL_FUNCTION_RIGHT_CLICK_MENU"}


def start_function_actions_bridge(app, host=HOST, port=PORT):
    global _server,_thread
    if _server is not None: return _server
    token=_token()

    class Handler(BaseHTTPRequestHandler):
        server_version="AUTO-KVTM-FunctionActions/1.0"
        def log_message(self,fmt,*args): return
        def _auth(self): return secrets.compare_digest(self.headers.get("X-Auto-Bridge-Token",""),token)
        def _json(self,code,payload):
            data=json.dumps(payload,ensure_ascii=False,default=str).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(data)
        def _body(self):
            n=int(self.headers.get("Content-Length","0") or "0")
            if n<=0:return {}
            if n>1024*1024:raise ValueError("request too large")
            return json.loads(self.rfile.read(n).decode("utf-8"))
        def do_GET(self):
            if not self._auth(): return self._json(403,{"ok":False,"error":"forbidden"})
            u=urlparse(self.path); qs=parse_qs(u.query)
            try:
                if u.path=="/health": return self._json(200,{"ok":True,"version":"1.0"})
                if u.path=="/actions":
                    option_index=(qs.get("option_index") or [""])[0]
                    result=_call_tk(app,lambda:_snapshot_actions(app,option_index),timeout=7.0)
                    return self._json(200,result)
                return self._json(404,{"ok":False,"error":f"not found: {u.path}"})
            except Exception as exc: return self._json(500,{"ok":False,"error":str(exc)})
        def do_POST(self):
            if not self._auth(): return self._json(403,{"ok":False,"error":"forbidden"})
            u=urlparse(self.path)
            try:
                body=self._body()
                if u.path=="/action":
                    option_index=body.get("option_index"); action_id=str(body.get("action_id") or ""); confirm=bool(body.get("confirm"))
                    # _invoke_action schedules original callbacks on Tk itself and
                    # then polls the GUI from this HTTP thread.
                    result=_invoke_action(app,option_index,action_id,confirm)
                    return self._json(200,result)
                if u.path=="/popup":
                    sid=str(body.get("session_id") or ""); fields=body.get("fields") if isinstance(body.get("fields"),list) else []; action=str(body.get("action") or "update")
                    result=_call_tk(app,lambda:_apply_popup(app,sid,fields,action),timeout=8.0)
                    return self._json(200,result)
                return self._json(404,{"ok":False,"error":f"not found: {u.path}"})
            except Exception as exc: return self._json(500,{"ok":False,"error":str(exc)})

    try:
        _server=ThreadingHTTPServer((host,int(port)),Handler)
    except OSError as exc:
        raise RuntimeError(f"Không mở được Function Actions Bridge {host}:{port}. Hãy đóng RUN_LOCAL cũ. Lỗi: {exc}") from exc
    _thread=threading.Thread(target=_server.serve_forever,name="AUTO-KVTM-FunctionActions",daemon=True); _thread.start()
    print(f"[LOCAL-FUNCTION-ACTIONS] real right-click bridge: http://{host}:{port}")
    return _server
