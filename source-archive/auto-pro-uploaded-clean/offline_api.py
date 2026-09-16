"""Stateless offline replacement for AUTO PRO remote key/API calls.

No network, device fingerprinting, analytics, telemetry, or local event database.
"""
from __future__ import annotations

ALL_FUNCTIONS = ",".join(str(index) for index in range(1, 1001))
LOCAL_EXPIRY = "2099-12-31 23:59:59"


def local_profile():
    return {
        "success": True,
        "status": "success",
        "name": "LOCAL USER",
        "expired_at": LOCAL_EXPIRY,
        "expiration": LOCAL_EXPIRY,
        "functions": ALL_FUNCTIONS,
        "wallet": 0,
        "wallet_balance": 0,
        "id": "LOCAL",
        "ref_id": "LOCAL",
        "token": "LOCAL-OFFLINE",
        "device_id": "LOCAL-DEVICE",
        "message": "Local offline mode",
    }


def api_auth_login(*args, **kwargs): return local_profile()
def api_wallet_get(*args, **kwargs): return {"success": True, "wallet": 0, "balance": 0}
def api_wallet_add(*args, **kwargs): return {"success": True, "wallet": 0, "balance": 0}
def api_check_payment(*args, **kwargs): return {"success": True, "paid": False, "status": "local"}
def api_app_latest(*args, **kwargs): return {"success": True, "version": "0.0.0-local", "download_url": ""}
def api_app_versions(*args, **kwargs): return {"success": True, "items": [], "data": []}
def api_app_check_patch(*args, **kwargs): return {"success": True, "has_patch": False}
def api_get_orders(*args, **kwargs): return {"success": True, "orders": [], "data": []}
def api_device_reset(*args, **kwargs): return {"success": True, "message": "Local offline mode"}
def api_license_create(*args, **kwargs): return local_profile()
def api_license_update_expired_at(*args, **kwargs): return local_profile()
def api_license_update_functions(*args, **kwargs): return local_profile()
def api_feature_add(*args, **kwargs): return {"success": True}
def api_feature_remove(*args, **kwargs): return {"success": True}
def api_feature_delete(*args, **kwargs): return {"success": True}
def api_order_feature(*args, **kwargs): return {"success": True, "status": "local"}


def api_request(action, method="GET", params=None, json_data=None, timeout=0):
    del method, params, json_data, timeout
    table = {
        "login": api_auth_login,
        "wallet_get": api_wallet_get,
        "wallet_add": api_wallet_add,
        "check_payment": api_check_payment,
        "app_latest": api_app_latest,
        "app_versions": api_app_versions,
        "app_check_patch": api_app_check_patch,
        "get_orders": api_get_orders,
        "reset_device": api_device_reset,
    }
    function = table.get(str(action))
    return function() if function else {
        "success": True,
        "status": "local",
        "message": f"Local offline stub: {action}",
    }


def install_gui_base(gui_base):
    gui_base.API_BASE = "local://offline"
    gui_base.API_KEY = ""
    gui_base._api_request = api_request
    for name, value in globals().copy().items():
        if name.startswith("api_") and callable(value):
            setattr(gui_base, name, value)
