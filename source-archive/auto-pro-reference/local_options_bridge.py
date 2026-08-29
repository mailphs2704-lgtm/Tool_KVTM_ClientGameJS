from __future__ import annotations

import json
import secrets
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "local_data" / "bridge_token.txt"
HOST = "127.0.0.1"
PORT = 8767
_server = None
_thread = None

OPTION_SPECS = (
    ("Xoa_vp_kc", "Xóa Vật Phẩm Bằng KC", False),
    ("open_chest", "Tự Động Mở Rương Gỗ", False),
    ("auto_quay_he", "Tự Động Quay Hề", True),
    ("auto_nang_kho", "Tự Động Nâng Kho", True),
    ("thue_tom", "Tự Động Thuê Tôm", True),
    ("giao_cu", "Tự Động Giao Cú", True),
    ("san_xuat_ngoc", "Tự Động Sản Xuất Ngọc", True),
    ("sx_event_cam", "Sản Xuất Cám (Event)", False),
    ("sell_all", "Bán Hết Vật Phẩm Cào", False),
)


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


def _get_bool(var):
    try:
        return bool(var.get())
    except Exception:
        return bool(var)


def _snapshot(app):
    vars_map = getattr(app, "checkbox_vars", {}) or {}
    rows = []
    for key, label, has_popup in OPTION_SPECS:
        var = vars_map.get(key)
        if var is None:
            continue
        rows.append({
            "key": key,
            "label": label,
            "enabled": _get_bool(var),
            "has_popup": has_popup,
            "source": "REAL_LAUNCHER_CHECKBOX_VAR",
        })
    return rows


def _set(app, key, enabled):
    spec = next((x for x in OPTION_SPECS if x[0] == key), None)
    if spec is None:
        raise ValueError(f"Tùy chọn không hợp lệ: {key}")
    vars_map = getattr(app, "checkbox_vars", {}) or {}
    var = vars_map.get(key)
    if var is None:
        raise RuntimeError(f"AUTO hiện tại chưa có tùy chọn {key}")

    # Set the exact Tk BooleanVar. We intentionally do not invoke the original
    # Checkbutton command here because several callbacks open a blocking desktop
    # popup. Existing popup configuration is preserved and used when START runs.
    var.set(bool(enabled))
    try:
        app.update_idletasks()
    except Exception:
        pass
    return {
        "ok": True,
        "key": key,
        "label": spec[1],
        "enabled": _get_bool(var),
        "options": _snapshot(app),
    }


def _call_tk(app, fn, timeout=5.0):
    done = threading.Event()
    box = {}

    def runner():
        try:
            box["result"] = fn()
        except Exception as exc:
            box["error"] = str(exc)
            box["traceback"] = traceback.format_exc()
        finally:
            done.set()

    app.after(0, runner)
    if not done.wait(timeout):
        raise TimeoutError("AUTO GUI không trả lời kịp")
    if "error" in box:
        raise RuntimeError(box["error"])
    return box.get("result")


def start_options_bridge(app, host=HOST, port=PORT):
    global _server, _thread
    if _server is not None:
        return _server
    token = _token()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AUTO-KVTM-OptionsBridge/1.0"

        def log_message(self, fmt, *args):
            return

        def _json(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _auth(self):
            return secrets.compare_digest(self.headers.get("X-Auto-Bridge-Token", ""), token)

        def _body(self):
            n = int(self.headers.get("Content-Length", "0") or "0")
            if n <= 0:
                return {}
            if n > 65536:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n).decode("utf-8"))

        def do_GET(self):
            if not self._auth():
                return self._json(403, {"ok": False, "error": "forbidden"})
            path = urlparse(self.path).path
            try:
                if path == "/health":
                    return self._json(200, {"ok": True, "version": "1.0", "option_count": len(_call_tk(app, lambda: _snapshot(app)))})
                if path == "/options":
                    return self._json(200, {"ok": True, "options": _call_tk(app, lambda: _snapshot(app)), "source": "REAL_LAUNCHER_CHECKBOX_VARS"})
                return self._json(404, {"ok": False, "error": "not found"})
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

        def do_POST(self):
            if not self._auth():
                return self._json(403, {"ok": False, "error": "forbidden"})
            path = urlparse(self.path).path
            try:
                if path != "/options":
                    return self._json(404, {"ok": False, "error": "not found"})
                body = self._body()
                key = str(body.get("key") or "").strip()
                if not key:
                    raise ValueError("key required")
                result = _call_tk(app, lambda: _set(app, key, bool(body.get("enabled"))))
                return self._json(200, result)
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

    _server = ThreadingHTTPServer((host, int(port)), Handler)
    _thread = threading.Thread(target=_server.serve_forever, name="AUTO-KVTM-OptionsBridge", daemon=True)
    _thread.start()
    print(f"[LOCAL-OPTIONS] launcher options bridge: http://{host}:{port}")
    return _server
