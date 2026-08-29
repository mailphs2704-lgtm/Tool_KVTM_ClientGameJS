from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import local_function_actions_bridge as base

HOST = "127.0.0.1"
PORT = 8769
_server = None
_thread = None


def _invoke_action_safe(app, option_index, action_id, confirm=False):
    # Selecting the Listbox item, generating Button-3 and reading Menu entries
    # all happen on Tk's GUI thread.
    row, menu, entries, actions = base._call_tk(
        app, lambda: base._open_context_menu(app, option_index), timeout=7.0
    )
    entry = next((e for e in entries if base._action_id(e.get("label")) == action_id), None)
    if entry is None:
        raise RuntimeError(f"Menu gốc không có thao tác {action_id}")
    if entry.get("state") == "disabled":
        raise RuntimeError(f"Thao tác đang bị khóa trong AUTO: {entry.get('label')}")
    if action_id == "delete" and not confirm:
        raise RuntimeError("Xóa yêu cầu xác nhận rõ ràng")

    before = set(base._call_tk(app, lambda: [str(x) for x in base._toplevels(app)]))
    captured, restore = base._patch_messageboxes(confirm=confirm)
    try:
        def schedule():
            def fire():
                try:
                    menu.invoke(int(entry["index"]))
                except Exception as exc:
                    print(f"[FUNCTION-ACTIONS] invoke {action_id}: {exc}")
            app.after(0, fire)
            return True
        base._call_tk(app, schedule)

        popup_path = None
        deadline = time.time() + 2.8
        while time.time() < deadline:
            def detect():
                fresh = [x for x in base._toplevels(app) if str(x) not in before]
                return str(fresh[-1]) if fresh else None
            try:
                popup_path = base._call_tk(app, detect, timeout=1.0)
            except Exception:
                popup_path = None
            if popup_path or captured:
                break
            time.sleep(0.06)

        if popup_path:
            def hide_read():
                popup = base._popup_by_path(app, popup_path)
                if popup is None:
                    raise RuntimeError("Popup vừa mở đã đóng")
                try:
                    popup.update_idletasks()
                    popup.withdraw()
                    popup.grab_release()
                except Exception:
                    pass
                import uuid
                sid = uuid.uuid4().hex
                base._popup_sessions[sid] = {
                    "popup": popup_path,
                    "action_id": action_id,
                    "row": row,
                    "opened_at": time.time(),
                }
                def expire():
                    sess = base._popup_sessions.get(sid)
                    if not sess:
                        return
                    p = base._popup_by_path(app, sess.get("popup", ""))
                    if p is not None:
                        try:
                            p.destroy()
                        except Exception:
                            pass
                    base._popup_sessions.pop(sid, None)
                app.after(5 * 60 * 1000, expire)
                return base._inspect_popup(app, popup, sid, action_id, row)
            return base._call_tk(app, hide_read, timeout=5.0)

        time.sleep(0.18)
        if captured:
            return {
                "ok": True,
                "kind": "message",
                "action_id": action_id,
                "messages": list(captured),
                "row": row,
            }
        return {
            "ok": True,
            "kind": "done",
            "action_id": action_id,
            "label": entry.get("label"),
            "row": row,
        }
    finally:
        restore()
        try:
            base._call_tk(app, lambda: menu.unpost(), timeout=1.0)
        except Exception:
            pass


def start_function_actions_bridge(app, host=HOST, port=PORT):
    global _server, _thread
    if _server is not None:
        return _server
    token = base._token()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AUTO-KVTM-FunctionActions/1.1"
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
            if n > 1024 * 1024:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n).decode("utf-8"))
        def do_GET(self):
            if not self._auth():
                return self._json(403, {"ok": False, "error": "forbidden"})
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            try:
                if u.path == "/health":
                    return self._json(200, {"ok": True, "version": "1.1"})
                if u.path == "/actions":
                    option_index = (qs.get("option_index") or [""])[0]
                    result = base._call_tk(
                        app, lambda: base._snapshot_actions(app, option_index), timeout=7.0
                    )
                    return self._json(200, result)
                return self._json(404, {"ok": False, "error": f"not found: {u.path}"})
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})
        def do_POST(self):
            if not self._auth():
                return self._json(403, {"ok": False, "error": "forbidden"})
            u = urlparse(self.path)
            try:
                body = self._body()
                if u.path == "/action":
                    result = _invoke_action_safe(
                        app,
                        body.get("option_index"),
                        str(body.get("action_id") or ""),
                        bool(body.get("confirm")),
                    )
                    return self._json(200, result)
                if u.path == "/popup":
                    sid = str(body.get("session_id") or "")
                    fields = body.get("fields") if isinstance(body.get("fields"), list) else []
                    action = str(body.get("action") or "update")
                    result = base._call_tk(
                        app, lambda: base._apply_popup(app, sid, fields, action), timeout=8.0
                    )
                    return self._json(200, result)
                return self._json(404, {"ok": False, "error": f"not found: {u.path}"})
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

    try:
        _server = ThreadingHTTPServer((host, int(port)), Handler)
    except OSError as exc:
        raise RuntimeError(
            f"Không mở được Function Actions Bridge {host}:{port}. Hãy đóng RUN_LOCAL cũ. Lỗi: {exc}"
        ) from exc
    _thread = threading.Thread(
        target=_server.serve_forever,
        name="AUTO-KVTM-FunctionActions-v11",
        daemon=True,
    )
    _thread.start()
    print(f"[LOCAL-FUNCTION-ACTIONS] v1.1 real right-click bridge: http://{host}:{port}")
    return _server
