from __future__ import annotations

import json
import secrets
import threading
import traceback
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "local_data" / "bridge_token.txt"
HOST = "127.0.0.1"
PORT = 8767
_server = None
_thread = None

# These are the auxiliary options visible in the recovered AUTO.  v0.8 does
# not trust these keys blindly: it also discovers the actual Tk Checkbutton
# widgets and their Tcl variable names at runtime, so renamed/moved vars still
# remain controllable from the web.
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


def _norm(value):
    s = unicodedata.normalize("NFD", str(value or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join(s.lower().replace("đ", "d").split())


SPEC_BY_LABEL = {_norm(label): (key, label, popup) for key, label, popup in OPTION_SPECS}
SPEC_BY_KEY = {key: (key, label, popup) for key, label, popup in OPTION_SPECS}


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


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "selected"}


def _checkbox_vars(app):
    value = getattr(app, "checkbox_vars", None)
    return value if isinstance(value, dict) else {}


def _walk(widget):
    yield widget
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield from _walk(child)


def _ancestor_is_options(widget):
    cur = getattr(widget, "master", None)
    for _ in range(8):
        if cur is None:
            break
        try:
            text = _norm(cur.cget("text"))
            if "tuy chon" in text or "option" in text:
                return True
        except Exception:
            pass
        cur = getattr(cur, "master", None)
    return False


def _widget_rows(app):
    vars_map = _checkbox_vars(app)
    var_key_by_name = {}
    for key, var in list(vars_map.items()):
        try:
            var_key_by_name[str(var)] = str(key)
        except Exception:
            pass

    rows = []
    checkbutton_count = 0
    for widget in _walk(app):
        try:
            cls = str(widget.winfo_class() or "").lower()
        except Exception:
            continue
        if "checkbutton" not in cls:
            continue
        checkbutton_count += 1
        try:
            label = str(widget.cget("text") or "").strip()
            var_name = str(widget.cget("variable") or "").strip()
        except Exception:
            continue
        if not label or not var_name:
            continue

        spec = SPEC_BY_LABEL.get(_norm(label))
        # Keep the exact recovered auxiliary options.  If the build moved them
        # into a labelled "Tùy chọn" frame, also accept those widgets even if
        # their label changed slightly in a later build.
        if spec is None and not _ancestor_is_options(widget):
            continue

        mapped_key = var_key_by_name.get(var_name)
        if spec is not None:
            expected_key, canonical_label, has_popup = spec
            try:
                expected_matches = expected_key in vars_map and str(vars_map[expected_key]) == var_name
            except Exception:
                expected_matches = False
            if expected_matches:
                key = expected_key
            elif mapped_key:
                key = mapped_key
            else:
                key = f"tk:{var_name}"
            out_label = label or canonical_label
        else:
            key = mapped_key or f"tk:{var_name}"
            out_label = label
            has_popup = False

        try:
            enabled = _to_bool(app.getvar(var_name))
        except Exception:
            try:
                enabled = _to_bool(vars_map.get(key).get()) if key in vars_map else False
            except Exception:
                enabled = False

        rows.append({
            "key": str(key),
            "label": out_label,
            "enabled": enabled,
            "has_popup": bool(has_popup),
            "source": "REAL_TK_CHECKBUTTON",
            "var_name": var_name,
        })

    return rows, checkbutton_count


def _snapshot(app):
    vars_map = _checkbox_vars(app)
    rows, checkbutton_count = _widget_rows(app)
    seen = {str(x.get("key")) for x in rows}
    seen_labels = {_norm(x.get("label")) for x in rows}

    # Fallback for builds where the Checkbutton is not currently mounted in the
    # active tab but checkbox_vars already exists on the real AutomationGUI.
    for key, label, has_popup in OPTION_SPECS:
        if key in seen or _norm(label) in seen_labels:
            continue
        var = vars_map.get(key)
        if var is None:
            continue
        try:
            enabled = _to_bool(var.get())
            var_name = str(var)
        except Exception:
            enabled = _to_bool(var)
            var_name = ""
        rows.append({
            "key": key,
            "label": label,
            "enabled": enabled,
            "has_popup": bool(has_popup),
            "source": "REAL_LAUNCHER_CHECKBOX_VAR",
            "var_name": var_name,
        })

    # Stable order: recovered known labels first, then any additional widgets
    # that genuinely live in the Tùy chọn group.
    order = {key: i for i, (key, _, _) in enumerate(OPTION_SPECS)}
    rows.sort(key=lambda x: (order.get(str(x.get("key")), 999), _norm(x.get("label"))))
    return {
        "options": rows,
        "diagnostics": {
            "checkbox_vars_count": len(vars_map),
            "checkbutton_count": checkbutton_count,
            "option_count": len(rows),
        },
    }


def _set_option(app, key, enabled):
    key = str(key or "").strip()
    if not key:
        raise ValueError("key required")

    vars_map = _checkbox_vars(app)
    target_var_name = ""

    if key in vars_map:
        var = vars_map[key]
        try:
            var.set(bool(enabled))
            target_var_name = str(var)
        except Exception as exc:
            raise RuntimeError(f"Không set được checkbox_vars[{key!r}]: {exc}") from exc
    elif key.startswith("tk:"):
        target_var_name = key[3:]
        if not target_var_name:
            raise ValueError("Tk variable không hợp lệ")
        try:
            # Directly change the exact Tcl variable instead of invoking the
            # Checkbutton command.  Therefore popup callbacks are not opened on
            # the desktop and existing detailed configuration is preserved.
            app.setvar(target_var_name, bool(enabled))
        except Exception as exc:
            raise RuntimeError(f"Không set được Tk variable {target_var_name}: {exc}") from exc
    else:
        # A runtime-discovered row may map to a different checkbox_vars key.
        snap = _snapshot(app)["options"]
        row = next((x for x in snap if str(x.get("key")) == key), None)
        if not row:
            raise RuntimeError(f"AUTO hiện tại không tìm thấy tùy chọn {key}")
        target_var_name = str(row.get("var_name") or "")
        if not target_var_name:
            raise RuntimeError(f"Tùy chọn {key} không có Tk variable")
        app.setvar(target_var_name, bool(enabled))

    try:
        app.update_idletasks()
    except Exception:
        pass

    snap = _snapshot(app)
    row = next((x for x in snap["options"] if str(x.get("key")) == key), None)
    if row is None and target_var_name:
        row = next((x for x in snap["options"] if str(x.get("var_name")) == target_var_name), None)
    return {
        "ok": True,
        "key": key,
        "enabled": bool(row.get("enabled")) if row else bool(enabled),
        "options": snap["options"],
        "diagnostics": snap["diagnostics"],
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
        server_version = "AUTO-KVTM-OptionsBridge/2.0"

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
                    snap = _call_tk(app, lambda: _snapshot(app))
                    return self._json(200, {"ok": True, "version": "2.0", **snap["diagnostics"]})
                if path == "/options":
                    snap = _call_tk(app, lambda: _snapshot(app))
                    return self._json(200, {
                        "ok": True,
                        "options": snap["options"],
                        "diagnostics": snap["diagnostics"],
                        "source": "REAL_TK_CHECKBUTTONS+CHECKBOX_VARS",
                    })
                return self._json(404, {"ok": False, "error": f"not found: {path}"})
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

        def do_POST(self):
            if not self._auth():
                return self._json(403, {"ok": False, "error": "forbidden"})
            path = urlparse(self.path).path
            try:
                if path != "/options":
                    return self._json(404, {"ok": False, "error": f"not found: {path}"})
                body = self._body()
                result = _call_tk(app, lambda: _set_option(app, body.get("key"), bool(body.get("enabled"))))
                return self._json(200, result)
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

    try:
        _server = ThreadingHTTPServer((host, int(port)), Handler)
    except OSError as exc:
        raise RuntimeError(
            f"Không mở được Options Bridge {host}:{port}. Hãy đóng RUN_LOCAL/AUTO cũ trước khi mở bản mới. Lỗi: {exc}"
        ) from exc
    _thread = threading.Thread(target=_server.serve_forever, name="AUTO-KVTM-OptionsBridge-v08", daemon=True)
    _thread.start()
    print(f"[LOCAL-OPTIONS] v0.8 real Tk options bridge: http://{host}:{port}")
    return _server
