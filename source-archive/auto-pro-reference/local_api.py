"""Local replacement for the original remote license/API layer.
No HTTP calls are made from this module.
"""
from __future__ import annotations
import json, sqlite3, threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "local_data" / "local.db"
LOCK = threading.RLock()
ALL_FUNCTIONS = ",".join(str(i) for i in range(1, 1001))
LOCAL_EXPIRY = "2099-12-31 23:59:59"


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      action TEXT NOT NULL,
      payload TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'local'
    );
    """)
    conn.commit()
    return conn


def _get(key, default=None):
    with LOCK, _db() as c:
        r = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return default if r is None else json.loads(r[0])


def _set(key, value):
    with LOCK, _db() as c:
        c.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, json.dumps(value, ensure_ascii=False)))
        c.commit()


def local_profile():
    return {
        "success": True,
        "status": "success",
        "name": _get("name", "LOCAL USER"),
        "expired_at": LOCAL_EXPIRY,
        "expiration": LOCAL_EXPIRY,
        "functions": _get("functions", ALL_FUNCTIONS),
        "wallet": int(_get("wallet", 0)),
        "wallet_balance": int(_get("wallet", 0)),
        "id": "LOCAL",
        "ref_id": "LOCAL",
        "token": "LOCAL-OFFLINE",
        "device_id": "LOCAL-DEVICE",
        "message": "Local mode",
    }


def _record(action, payload):
    with LOCK, _db() as c:
        c.execute("INSERT INTO orders(created_at,action,payload,status) VALUES(?,?,?,?)",
                  (datetime.now().isoformat(timespec="seconds"), action, json.dumps(payload, ensure_ascii=False), "local"))
        c.commit()


def api_auth_login(*args, **kwargs): return local_profile()
def api_wallet_get(*args, **kwargs): return {"success": True, "wallet": int(_get("wallet", 0)), "balance": int(_get("wallet", 0))}
def api_wallet_add(license_key=None, amount=0, *args, **kwargs):
    value = int(_get("wallet", 0)) + int(amount or 0); _set("wallet", value)
    return {"success": True, "wallet": value, "balance": value}
def api_check_payment(*args, **kwargs): return {"success": True, "paid": False, "status": "local"}
def api_app_latest(*args, **kwargs): return {"success": True, "version": "0.0.0-local", "download_url": "", "release_notes": "Local/offline build", "release_date": ""}
def api_app_versions(*args, **kwargs): return {"success": True, "items": [], "data": []}
def api_app_check_patch(*args, **kwargs): return {"success": True, "has_patch": False, "patch_number": 0, "download_url": "", "release_notes": ""}
def api_get_orders(*args, **kwargs): return {"success": True, "orders": [], "data": []}
def api_device_reset(*args, **kwargs): return {"success": True, "message": "Local mode"}
def api_license_create(*args, **kwargs): return local_profile()
def api_license_update_expired_at(*args, **kwargs): return local_profile()
def api_license_update_functions(license_key=None, functions=None, *args, **kwargs):
    if functions is not None: _set("functions", functions)
    return local_profile()
def api_feature_add(license_key=None, func_id=None, func_name=None, *args, **kwargs):
    _record("feature_add", {"func_id": func_id, "func_name": func_name}); return {"success": True}
def api_feature_remove(license_key=None, func_id=None, func_name=None, *args, **kwargs):
    _record("feature_remove", {"func_id": func_id, "func_name": func_name}); return {"success": True}
def api_feature_delete(*args, **kwargs): return api_feature_remove(*args, **kwargs)
def api_order_feature(license_key=None, func_name=None, func_desc=None, *args, **kwargs):
    _record("order_feature", {"func_name": func_name, "func_desc": func_desc}); return {"success": True, "status": "local"}


def api_request(action, method="GET", params=None, json_data=None, timeout=0):
    table = {
        "login": api_auth_login, "wallet_get": api_wallet_get, "wallet_add": api_wallet_add,
        "check_payment": api_check_payment, "app_latest": api_app_latest, "app_versions": api_app_versions,
        "app_check_patch": api_app_check_patch, "get_orders": api_get_orders, "reset_device": api_device_reset,
    }
    fn = table.get(action)
    if fn: return fn()
    return {"success": True, "status": "local", "message": f"Local stub: {action}"}


def install_gui_base(gb):
    gb.API_BASE = "local://offline"
    gb.API_KEY = ""
    gb._api_request = api_request
    for name, value in globals().copy().items():
        if name.startswith("api_") and callable(value): setattr(gb, name, value)
