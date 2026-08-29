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
PORT = 8766

_server = None
_server_thread = None


def _load_token() -> str:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


TOKEN = _load_token()


def _valid_function_rows(rows):
    try:
        rows = list(rows or [])
    except Exception:
        return []
    out = []
    for item in rows:
        try:
            if len(item) < 2:
                continue
            label = str(item[0])
            func_id = int(item[1])
            search = str(item[2]) if len(item) > 2 else label
            out.append((label, func_id, search))
        except Exception:
            continue
    # FUNCTION_OPTIONS in this build has ~320 rows. Requiring a useful amount
    # prevents accidentally treating an unrelated tuple as the catalog.
    return out if len(out) >= 20 else []


def _function_options(app=None):
    """Return the exact FUNCTION_OPTIONS used by the running launcher.

    v0.4 looked only at gui.FUNCTION_OPTIONS. start_task() is inherited from
    gui_tasks.TaskOpsMixin, therefore its globals actually live in gui_tasks.
    On the recovered build this caused the web to display the static names but
    fail START with "Không tìm thấy chức năng ID ...".  Resolve the catalog
    from the bound GUI methods first, then fall back to module/instance data.
    """
    candidates = []

    if app is not None:
        candidates.append(getattr(app, "FUNCTION_OPTIONS", None))
        for method_name in ("start_task", "_handle_stop_task", "setup_gui", "update_function_list"):
            try:
                method = getattr(app, method_name, None)
                candidates.append(getattr(method, "__globals__", {}).get("FUNCTION_OPTIONS"))
            except Exception:
                pass

    for module_name in ("gui_tasks", "gui", "gui_tab_add", "gui_tab_mgmt"):
        try:
            module = __import__(module_name)
            candidates.append(getattr(module, "FUNCTION_OPTIONS", None))
        except Exception:
            pass

    for rows in candidates:
        valid = _valid_function_rows(rows)
        if valid:
            return valid

    # Last-resort recovery from setup_gui's literal tuple. This does not execute
    # bytecode; it only inspects constants already loaded in the running process.
    if app is not None:
        try:
            code = getattr(getattr(app, "setup_gui", None), "__code__", None)
            for const in getattr(code, "co_consts", ()):
                valid = _valid_function_rows(const if isinstance(const, tuple) else None)
                if valid:
                    return valid
        except Exception:
            pass

    return []


def _scenario_data():
    try:
        import automation_desc
        return getattr(automation_desc, "SCENARIO_DATA", {}) or {}
    except Exception:
        return {}


def _clean_text(value):
    import re
    value = re.sub(r"<[^>]+>", "", str(value or ""))
    return " ".join(value.split())


def _catalog(app=None):
    scenarios = _scenario_data()
    out = []
    for index, item in enumerate(_function_options(app)):
        try:
            label, func_id, search = item[:3]
            func_id = int(func_id)
        except Exception:
            continue
        desc = scenarios.get(f"produceItems_{func_id}", [])
        if isinstance(desc, str):
            desc = [desc]
        try:
            desc = [_clean_text(x) for x in list(desc)]
        except Exception:
            desc = []
        out.append({
            "option_index": index,
            "id": func_id,
            "method": f"produceItems_{func_id}",
            "label": str(label),
            "search": str(search or ""),
            "description": desc,
        })
    return out


def _infer_ui_status(tags, values):
    tags_l = {str(x).strip().lower() for x in (tags or [])}
    if "running" in tags_l:
        return "running"
    if "launching" in tags_l:
        return "launching"
    if "offline" in tags_l:
        return "offline"
    if "stopped" in tags_l:
        return "stopped"
    if "ready" in tags_l:
        return "ready"
    text = " ".join(str(x) for x in (values or [])).lower()
    if "đang chạy" in text or "dang chay" in text:
        return "running"
    if "đang mở" in text or "launching" in text:
        return "launching"
    if "offline" in text:
        return "offline"
    if "đã dừng" in text or "da dung" in text:
        return "stopped"
    if "sẵn sàng" in text or "san sang" in text or "ready" in text:
        return "ready"
    return ""


def _tree_snapshot(app):
    tree = getattr(app, "task_tree", None)
    if tree is None:
        return []
    mapping = getattr(app, "task_device_mapping", {}) or {}
    rows = []
    try:
        tids = list(tree.get_children())
    except Exception:
        return []
    for tid in tids:
        try:
            info = tree.item(tid) or {}
            values = list(info.get("values", ()) or ())
            tags = list(info.get("tags", ()) or ())
            device_id = str(mapping.get(tid, "") or "")
            rows.append({
                "task_id": str(tid),
                "device_id": device_id,
                "values": values,
                "tags": tags,
                "ui_status": _infer_ui_status(tags, values),
            })
        except Exception:
            continue
    return rows


def _task_snapshot(app):
    """Read status without mutating TaskManager.

    v0.4 called sync_statuses() every second. That helper is intended as a
    repair routine and may downgrade a status based only on one thread ref.
    The web must be a passive observer, so combine TaskManager + visible tree
    state and never rewrite launcher status while polling.
    """
    manager = getattr(app, "task_manager", None)
    tree_rows = _tree_snapshot(app)
    tree_by_device = {x["device_id"]: x for x in tree_rows if x.get("device_id")}

    try:
        tasks = manager.get_all_tasks() if manager is not None else {}
    except Exception:
        tasks = getattr(manager, "_tasks", {}) or {} if manager is not None else {}

    rows = []
    seen = set()
    for key, task in list((tasks or {}).items()):
        try:
            device_id = str(getattr(task, "device_id", None) or key)
            seen.add(device_id)
            thread = getattr(task, "thread", None)
            alive = bool(thread and thread.is_alive())
            raw_status = str(getattr(task, "status", "ready") or "ready")
            tree_row = tree_by_device.get(device_id, {})
            ui_status = str(tree_row.get("ui_status") or "")
            running = alive or raw_status == "running" or ui_status == "running"
            status = "running" if running else (ui_status or raw_status)
            automation = getattr(task, "automation", None)
            func_id = getattr(automation, "function_id", None) if automation is not None else None
            try:
                func_id = int(func_id) if func_id is not None else None
            except Exception:
                func_id = None
            rows.append({
                "device_id": device_id,
                "task_id": str(getattr(task, "task_id", "") or tree_row.get("task_id") or ""),
                "display_name": str(getattr(task, "display_name", "") or ""),
                "func_text": str(getattr(task, "func_text", "") or ""),
                "function_id": func_id,
                "status": status,
                "manager_status": raw_status,
                "ui_status": ui_status,
                "ui_running": ui_status == "running",
                "thread_alive": alive,
                "generation": int(getattr(task, "generation", 0) or 0),
                "ui_values": tree_row.get("values", []),
                "ui_tags": tree_row.get("tags", []),
            })
        except Exception as exc:
            rows.append({"device_id": str(key), "status": "error", "error": str(exc)})

    # Defensive compatibility for a GUI row that exists before TaskManager has
    # registered it. This also makes the web useful immediately after Load Device.
    for tr in tree_rows:
        device_id = str(tr.get("device_id") or "")
        if not device_id or device_id in seen:
            continue
        values = tr.get("values", [])
        rows.append({
            "device_id": device_id,
            "task_id": tr.get("task_id", ""),
            "display_name": str(values[0]) if values else device_id,
            "func_text": "",
            "function_id": None,
            "status": tr.get("ui_status") or "ready",
            "manager_status": "missing",
            "ui_status": tr.get("ui_status") or "",
            "ui_running": tr.get("ui_status") == "running",
            "thread_alive": False,
            "generation": 0,
            "ui_values": values,
            "ui_tags": tr.get("tags", []),
        })
    return rows


def _device_snapshot(app):
    """Device IDs exactly as the launcher sees them."""
    devices = {}
    mapping = getattr(app, "device_mapping", {}) or {}

    def add(device_id, display_name="", state="device", source="launcher"):
        device_id = str(device_id or "").strip()
        if not device_id:
            return
        rec = devices.setdefault(device_id, {
            "id": device_id,
            "display_name": "",
            "state": state or "device",
            "source": source,
        })
        if display_name and not rec.get("display_name"):
            rec["display_name"] = str(display_name)
        if state == "offline":
            rec["state"] = "offline"

    # Normal build: display name -> adb id.
    for k, v in list(mapping.items()):
        if isinstance(v, str) and v.strip():
            add(v, k)

    manager = getattr(app, "task_manager", None)
    try:
        tasks = manager.get_all_tasks() if manager is not None else {}
    except Exception:
        tasks = getattr(manager, "_tasks", {}) or {} if manager is not None else {}
    for key, task in list((tasks or {}).items()):
        did = str(getattr(task, "device_id", None) or key)
        add(did, getattr(task, "display_name", ""), "offline" if getattr(task, "status", "") == "offline" else "device")

    for row in _tree_snapshot(app):
        did = row.get("device_id")
        if did:
            vals = row.get("values") or []
            add(did, vals[0] if vals else "", "offline" if row.get("ui_status") == "offline" else "device")

    try:
        for display in list(app.device_cb.cget("values")):
            did = mapping.get(display, display)
            add(did, display)
    except Exception:
        pass

    return list(devices.values())


def _find_device_display(app, device_id: str):
    mapping = getattr(app, "device_mapping", {}) or {}
    for key, value in list(mapping.items()):
        if str(value) == str(device_id):
            return str(key)
    if str(device_id) in mapping:
        value = mapping.get(str(device_id))
        if isinstance(value, str):
            return value
    try:
        values = list(app.device_cb.cget("values"))
        for candidate in values:
            if str(candidate) == str(device_id):
                return str(candidate)
            if str(mapping.get(candidate, "")) == str(device_id):
                return str(candidate)
            if str(device_id) in str(candidate):
                return str(candidate)
    except Exception:
        pass
    return str(device_id)


def _select_function(app, function_id: int, requested_label: str | None = None):
    options = _function_options(app)
    candidates = []
    for item in options:
        try:
            label, fid = str(item[0]), int(item[1])
        except Exception:
            continue
        if fid == int(function_id) and (not requested_label or label == requested_label):
            candidates.append(label)
    if not candidates:
        for item in options:
            try:
                label, fid = str(item[0]), int(item[1])
            except Exception:
                continue
            if fid == int(function_id):
                candidates.append(label)
    if not candidates:
        raise ValueError(
            f"Không tìm thấy chức năng ID {function_id} trong FUNCTION_OPTIONS thật "
            f"({len(options)} mục đã đọc từ launcher)"
        )

    box = getattr(app, "function_list", None)
    if box is None:
        raise RuntimeError("GUI chưa tạo danh sách chức năng")

    # Ensure the dashboard list is current. The recovered GUI has
    # update_function_list(); older patches looked for non-existent filter names.
    try:
        if hasattr(app, "update_function_list"):
            app.update_function_list()
    except Exception:
        pass

    size = int(box.size())
    chosen_index = None
    chosen_label = None
    for i in range(size):
        raw = str(box.get(i))
        normalized = raw.removeprefix("⭐ ").strip()
        for label in candidates:
            if normalized == label.strip():
                chosen_index = i
                chosen_label = label
                break
        if chosen_index is not None:
            break

    if chosen_index is None:
        raise RuntimeError(
            f"Đã đọc được ID {function_id} = {candidates[0]!r}, nhưng tên này chưa có trong "
            "Dashboard launcher. Bấm Load Devices/Tải lại danh sách chức năng trên AUTO một lần."
        )

    box.selection_clear(0, "end")
    box.selection_set(chosen_index)
    try:
        box.activate(chosen_index)
        box.see(chosen_index)
    except Exception:
        pass
    try:
        app.last_function_index = chosen_index
    except Exception:
        pass
    return chosen_label


def _start_from_gui(app, device_id: str, function_id: int, label: str | None):
    manager = getattr(app, "task_manager", None)
    if manager is None:
        raise RuntimeError("TaskManager của launcher chưa sẵn sàng")
    try:
        if manager.is_device_busy(device_id):
            task = manager.get_task(device_id)
            return {
                "ok": False,
                "error": f"{device_id} đang chạy: {getattr(task, 'func_text', '')}",
                "status": _task_snapshot(app),
            }
    except Exception:
        pass

    chosen_label = _select_function(app, int(function_id), label)
    display_name = _find_device_display(app, device_id)
    device_cb = getattr(app, "device_cb", None)
    if device_cb is None:
        raise RuntimeError("GUI chưa tạo danh sách thiết bị")
    device_cb.set(display_name)

    try:
        mapping = getattr(app, "task_device_mapping", {}) or {}
        task_id = next((tid for tid, did in mapping.items() if str(did) == str(device_id)), None)
        if task_id and getattr(app, "task_tree", None) is not None:
            app.task_tree.selection_set(task_id)
            app.task_tree.focus(task_id)
    except Exception:
        pass

    app.start_task()
    return {
        "ok": True,
        "device_id": device_id,
        "function_id": int(function_id),
        "label": chosen_label,
        "status": _task_snapshot(app),
    }


def _stop_from_gui(app, device_id: str):
    manager = getattr(app, "task_manager", None)
    if manager is None:
        raise RuntimeError("TaskManager của launcher chưa sẵn sàng")
    found = bool(manager.stop(device_id))
    try:
        app.after(10, app._update_task_ui_by_device, device_id)
    except Exception:
        pass
    return {"ok": found, "device_id": device_id, "status": _task_snapshot(app)}


def _call_tk(app, fn, timeout=15.0):
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
        raise TimeoutError(
            "Launcher chưa trả lời trong thời gian chờ. "
            "Có thể chức năng vừa mở popup cấu hình trên PC; hãy xử lý popup đó rồi thử lại."
        )
    if "error" in box:
        raise RuntimeError(box["error"])
    return box.get("result")


def start_bridge(app, host=HOST, port=PORT):
    """Start localhost IPC inside the exact running AutomationGUI process."""
    global _server, _server_thread
    if _server is not None:
        return _server

    class Handler(BaseHTTPRequestHandler):
        server_version = "AUTO-KVTM-LocalBridge/1.1"

        def log_message(self, fmt, *args):
            return

        def _authorized(self):
            return secrets.compare_digest(self.headers.get("X-Auto-Bridge-Token", ""), TOKEN)

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
            if not self._authorized():
                return self._json(403, {"ok": False, "error": "forbidden"})
            path = urlparse(self.path).path
            try:
                if path == "/health":
                    snap = _call_tk(app, lambda: _task_snapshot(app), timeout=3)
                    active = sum(1 for x in snap if x.get("thread_alive") or x.get("ui_running") or x.get("status") == "running")
                    funcs = _call_tk(app, lambda: len(_function_options(app)), timeout=3)
                    devices = _call_tk(app, lambda: _device_snapshot(app), timeout=3)
                    return self._json(200, {
                        "ok": True,
                        "connected": True,
                        "source": "REAL_LAUNCHER_TASK_MANAGER",
                        "active_count": active,
                        "task_count": len(snap),
                        "device_count": len(devices),
                        "function_count": funcs,
                        "bridge_version": "1.1",
                    })
                if path == "/status":
                    return self._json(200, {"ok": True, "status": _call_tk(app, lambda: _task_snapshot(app), timeout=3)})
                if path == "/devices":
                    return self._json(200, {"ok": True, "devices": _call_tk(app, lambda: _device_snapshot(app), timeout=3)})
                if path == "/functions":
                    return self._json(200, {"ok": True, "functions": _call_tk(app, lambda: _catalog(app), timeout=3)})
                return self._json(404, {"ok": False, "error": "not found"})
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

        def do_POST(self):
            if not self._authorized():
                return self._json(403, {"ok": False, "error": "forbidden"})
            path = urlparse(self.path).path
            try:
                body = self._body()
                if path == "/start":
                    device_id = str(body.get("device_id") or "").strip()
                    function_id = int(body.get("function_id"))
                    label = body.get("label")
                    if not device_id:
                        raise ValueError("device_id required")
                    result = _call_tk(app, lambda: _start_from_gui(app, device_id, function_id, label), timeout=15)
                    return self._json(200, result)
                if path == "/stop":
                    device_id = str(body.get("device_id") or "").strip()
                    if not device_id:
                        raise ValueError("device_id required")
                    result = _call_tk(app, lambda: _stop_from_gui(app, device_id), timeout=5)
                    return self._json(200, result)
                return self._json(404, {"ok": False, "error": "not found"})
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})

    try:
        _server = ThreadingHTTPServer((host, int(port)), Handler)
    except OSError as exc:
        raise RuntimeError(f"Không mở được Local Bridge {host}:{port}: {exc}") from exc

    _server_thread = threading.Thread(target=_server.serve_forever, name="AUTO-KVTM-LocalBridge", daemon=True)
    _server_thread.start()
    print(f"[LOCAL-BRIDGE] REAL launcher bridge v1.1: http://{host}:{port}")
    return _server
