from __future__ import annotations

import json
import secrets
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "local_data" / "bridge_token.txt"
HOST = "127.0.0.1"
PORT = 8768
_server = None
_thread = None
_sessions = {}

OPTION_LABELS = {
    "auto_quay_he": "Tự Động Quay Hề",
    "auto_nang_kho": "Tự Động Nâng Kho",
    "thue_tom": "Tự Động Thuê Tôm",
    "giao_cu": "Tự Động Giao Cú",
    "san_xuat_ngoc": "Tự Động Sản Xuất Ngọc",
}


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


def _walk(widget):
    yield widget
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield from _walk(child)


def _call_tk(app, fn, timeout=4.0):
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


def _checkbox_vars(app):
    value = getattr(app, "checkbox_vars", None)
    return value if isinstance(value, dict) else {}


def _find_option_widget(app, key):
    vars_map = _checkbox_vars(app)
    expected_var = None
    try:
        if key in vars_map:
            expected_var = str(vars_map[key])
    except Exception:
        pass
    wanted_label = _norm(OPTION_LABELS.get(key, ""))

    for widget in _walk(app):
        try:
            cls = str(widget.winfo_class() or "").lower()
            if "checkbutton" not in cls:
                continue
            text = str(widget.cget("text") or "").strip()
            var_name = str(widget.cget("variable") or "").strip()
        except Exception:
            continue
        if expected_var and var_name == expected_var:
            return widget
        if wanted_label and _norm(text) == wanted_label:
            return widget
    return None


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
        if int(widget.winfo_exists()):
            return widget
    except Exception:
        pass
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
        for sib in reversed(siblings[max(0, idx - 4):idx]):
            try:
                cls = str(sib.winfo_class() or "").lower()
                text = str(sib.cget("text") or "").strip()
                if "label" in cls and text:
                    return text
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _field(widget, app):
    try:
        cls = str(widget.winfo_class() or "").lower()
        state = str(widget.cget("state") or "normal").lower() if "label" not in cls else "normal"
    except Exception:
        return None
    if state in {"disabled", "readonlydisabled"}:
        disabled = True
    else:
        disabled = False

    path = str(widget)
    label = _label_for(widget)

    if "combobox" in cls:
        try:
            values = [str(x) for x in list(widget.cget("values"))]
        except Exception:
            values = []
        try:
            value = str(widget.get())
        except Exception:
            value = ""
        return {"id": path, "type": "select", "label": label, "value": value, "options": values, "disabled": disabled}

    if "checkbutton" in cls:
        try:
            var_name = str(widget.cget("variable") or "")
            raw = app.getvar(var_name)
            value = str(raw).lower() in {"1", "true", "yes", "on"}
        except Exception:
            value = False
        return {"id": path, "type": "boolean", "label": label, "value": bool(value), "disabled": disabled}

    if "radiobutton" in cls:
        try:
            var_name = str(widget.cget("variable") or "")
            raw = str(app.getvar(var_name))
            own = str(widget.cget("value"))
            checked = raw == own
        except Exception:
            own, checked = "", False
        return {"id": path, "type": "radio", "label": label, "value": own, "checked": checked, "disabled": disabled}

    if "scale" in cls:
        try:
            value = widget.get()
        except Exception:
            value = 0
        return {"id": path, "type": "number", "label": label, "value": value, "disabled": disabled}

    if "spinbox" in cls:
        try:
            value = str(widget.get())
        except Exception:
            value = ""
        try:
            values = [str(x) for x in list(widget.cget("values"))]
        except Exception:
            values = []
        return {"id": path, "type": "select" if values else "text", "label": label, "value": value, "options": values, "disabled": disabled}

    if cls in {"entry", "tentry"} or cls.endswith("entry"):
        try:
            value = str(widget.get())
        except Exception:
            value = ""
        return {"id": path, "type": "text", "label": label, "value": value, "disabled": disabled}

    return None


def _button_info(widget):
    try:
        cls = str(widget.winfo_class() or "").lower()
        if "button" not in cls or "checkbutton" in cls or "radiobutton" in cls:
            return None
        text = str(widget.cget("text") or "").strip()
        if not text:
            return None
        return {"id": str(widget), "text": text}
    except Exception:
        return None


def _inspect_popup(app, popup, key):
    fields = []
    buttons = []
    seen_radio_vars = set()
    for widget in _walk(popup):
        if widget is popup:
            continue
        f = _field(widget, app)
        if f:
            if f["type"] == "radio":
                try:
                    var_name = str(widget.cget("variable") or "")
                except Exception:
                    var_name = ""
                if var_name and var_name in seen_radio_vars:
                    # Individual radio buttons are still useful as choices, so keep them.
                    pass
                seen_radio_vars.add(var_name)
            fields.append(f)
        b = _button_info(widget)
        if b:
            buttons.append(b)
    try:
        title = str(popup.title() or OPTION_LABELS.get(key, key))
    except Exception:
        title = OPTION_LABELS.get(key, key)
    return {"ok": True, "key": key, "title": title, "fields": fields, "buttons": buttons, "source": "REAL_HIDDEN_TK_POPUP"}


def _choose_button(popup, action):
    save_words = ("luu", "xac nhan", "dong y", "ap dung", "ok", "save", "apply", "confirm")
    cancel_words = ("huy", "dong", "cancel", "close")
    candidates = []
    for widget in _walk(popup):
        b = _button_info(widget)
        if b:
            candidates.append((widget, _norm(b["text"])))
    words = save_words if action == "save" else cancel_words
    for widget, text in candidates:
        if any(word in text for word in words):
            return widget
    if action == "save":
        for widget, text in candidates:
            if not any(word in text for word in cancel_words):
                return widget
    return None


def _set_widget_value(app, widget, payload):
    cls = str(widget.winfo_class() or "").lower()
    value = payload.get("value")
    if "checkbutton" in cls:
        var_name = str(widget.cget("variable") or "")
        app.setvar(var_name, bool(value))
        return
    if "radiobutton" in cls:
        if payload.get("checked") or bool(value):
            var_name = str(widget.cget("variable") or "")
            app.setvar(var_name, str(widget.cget("value")))
        return
    if "combobox" in cls or "scale" in cls:
        widget.set(value)
        return
    if "spinbox" in cls or cls in {"entry", "tentry"} or cls.endswith("entry"):
        widget.delete(0, "end")
        widget.insert(0, "" if value is None else str(value))
        return


def _apply(app, key, values, action):
    session = _sessions.get(key) or {}
    popup = _popup_by_path(app, session.get("popup", ""))
    if popup is None:
        raise RuntimeError("Popup cấu hình đã đóng. Bấm Cấu hình lại.")

    for item in values or []:
        wid = str(item.get("id") or "")
        if not wid:
            continue
        try:
            widget = app.nametowidget(wid)
            _set_widget_value(app, widget, item)
        except Exception as exc:
            raise RuntimeError(f"Không ghi được field {wid}: {exc}") from exc

    try:
        app.update_idletasks()
    except Exception:
        pass

    if action in {"save", "cancel"}:
        button = _choose_button(popup, action)
        if button is not None:
            button.invoke()
        elif action == "cancel":
            popup.destroy()
        else:
            raise RuntimeError("Không tìm thấy nút Lưu/Xác nhận trong popup gốc")
        _sessions.pop(key, None)
        return {"ok": True, "key": key, "action": action, "saved": action == "save"}

    return _inspect_popup(app, popup, key)


def _open_settings(app, key):
    key = str(key or "").strip()
    if key not in OPTION_LABELS:
        raise ValueError(f"Tùy chọn {key} chưa khai báo có setting phụ")

    existing = _sessions.get(key)
    if existing:
        popup = _call_tk(app, lambda: _popup_by_path(app, existing.get("popup", "")))
        if popup is not None:
            return _call_tk(app, lambda: _inspect_popup(app, popup, key))
        _sessions.pop(key, None)

    before = set(_call_tk(app, lambda: [str(x) for x in _toplevels(app)]))
    option_widget = _call_tk(app, lambda: _find_option_widget(app, key))
    if option_widget is None:
        raise RuntimeError(f"Không tìm thấy Checkbutton thật của {OPTION_LABELS[key]}")

    def prepare_and_fire():
        vars_map = _checkbox_vars(app)
        try:
            if key in vars_map:
                vars_map[key].set(True)
            else:
                var_name = str(option_widget.cget("variable") or "")
                if var_name:
                    app.setvar(var_name, True)
        except Exception:
            pass
        cmd = str(option_widget.cget("command") or "").strip()
        if not cmd:
            raise RuntimeError("Checkbutton này không có callback mở cấu hình")

        def fire():
            try:
                app.tk.call(cmd)
            except Exception as exc:
                print(f"[SETTINGS-BRIDGE] popup callback {key}: {exc}")
        app.after(0, fire)
        return True

    _call_tk(app, prepare_and_fire)

    popup_path = None
    deadline = time.time() + 3.0
    while time.time() < deadline:
        def detect():
            current = _toplevels(app)
            fresh = [x for x in current if str(x) not in before]
            if fresh:
                return str(fresh[-1])
            # Some builds reuse a hidden Toplevel. Prefer a non-root popup whose title matches.
            wanted = _norm(OPTION_LABELS[key])
            for x in reversed(current):
                try:
                    title = _norm(x.title())
                    if title and (title in wanted or wanted in title):
                        return str(x)
                except Exception:
                    pass
            return None
        popup_path = _call_tk(app, detect, timeout=1.0)
        if popup_path:
            break
        time.sleep(0.08)

    if not popup_path:
        raise RuntimeError("AUTO không mở popup cấu hình. Có thể mục này dùng loại setting khác; gửi ảnh popup gốc để mình map riêng.")

    def hide_and_read():
        popup = _popup_by_path(app, popup_path)
        if popup is None:
            raise RuntimeError("Popup vừa mở đã đóng")
        try:
            popup.update_idletasks()
            popup.withdraw()
        except Exception:
            pass
        _sessions[key] = {"popup": popup_path, "opened_at": time.time()}

        def expire():
            sess = _sessions.get(key)
            if not sess or sess.get("popup") != popup_path:
                return
            p = _popup_by_path(app, popup_path)
            if p is not None:
                try:
                    p.destroy()
                except Exception:
                    pass
            _sessions.pop(key, None)
        app.after(5 * 60 * 1000, expire)
        return _inspect_popup(app, popup, key)

    return _call_tk(app, hide_and_read)


def start_settings_bridge(app, host=HOST, port=PORT):
    global _server, _thread
    if _server is not None:
        return _server
    token = _token()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AUTO-KVTM-SettingsBridge/1.0"

        def log_message(self, fmt, *args):
            return

        def _auth(self):
            return secrets.compare_digest(self.headers.get("X-Auto-Bridge-Token", ""), token)

        def _json(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length", "0") or "0")
            if n <= 0:
                return {}
            if n > 512 * 1024:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n).decode("utf-8"))

        def do_GET(self):
            if not self._auth():
                return self._json(403, {"ok": False, "error": "forbidden"})
            u = urlparse(self.path)
            try:
                if u.path == "/health":
                    return self._json(200, {"ok": True, "version": "1.0", "sessions": len(_sessions)})
                if u.path == "/settings":
                    key = (parse_qs(u.query).get("key") or [""])[0]
                    return self._json(200, _open_settings(app, key))
                return self._json(404, {"ok": False, "error": f"not found: {u.path}"})
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

        def do_POST(self):
            if not self._auth():
                return self._json(403, {"ok": False, "error": "forbidden"})
            u = urlparse(self.path)
            try:
                if u.path != "/settings":
                    return self._json(404, {"ok": False, "error": f"not found: {u.path}"})
                body = self._body()
                key = str(body.get("key") or "").strip()
                action = str(body.get("action") or "update").strip().lower()
                result = _call_tk(app, lambda: _apply(app, key, body.get("fields") or [], action), timeout=8.0)
                return self._json(200, result)
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

    try:
        _server = ThreadingHTTPServer((host, int(port)), Handler)
    except OSError as exc:
        raise RuntimeError(f"Không mở được Settings Bridge {host}:{port}: {exc}") from exc
    _thread = threading.Thread(target=_server.serve_forever, name="AUTO-KVTM-SettingsBridge", daemon=True)
    _thread.start()
    print(f"[LOCAL-SETTINGS] real hidden popup bridge: http://{host}:{port}")
    return _server
