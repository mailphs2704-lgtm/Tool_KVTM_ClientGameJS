from __future__ import annotations

# v1.2 safety shim for the original right-click bridge.
# The recovered GUI's <Button-3> handler uses tk_popup(), which enters a nested
# Tk event loop. Calling event_generate() synchronously therefore blocked the
# HTTP bridge until a human dismissed the visible menu. Arm a short Tk timer
# BEFORE generating the event so the real menu is built/updated, then unpost it
# inside that nested event loop. This keeps the original callbacks and dynamic
# labels without leaving a visible/blocking menu on screen.

import local_function_actions_bridge as base
import local_function_actions_bridge_v2 as bridge_v2


def _dismiss_context_menus(app):
    for widget in list(base._walk(app)):
        try:
            if str(widget.winfo_class() or "").lower() == "menu":
                widget.unpost()
        except Exception:
            pass
    try:
        grabbed = app.grab_current()
        if grabbed is not None and str(grabbed.winfo_class() or "").lower() == "menu":
            grabbed.grab_release()
    except Exception:
        pass


def _safe_open_context_menu(app, option_index):
    row, box, index = base._select_main_function(app, option_index)
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

    # Critical ordering: timer first, then the real Button-3 event. If the
    # original binding enters tk_popup(), this timer runs in its nested loop and
    # releases it automatically.
    try:
        app.after(25, lambda: _dismiss_context_menus(app))
    except Exception:
        pass

    try:
        box.event_generate(
            "<Button-3>",
            x=x,
            y=y,
            rootx=box.winfo_rootx() + x,
            rooty=box.winfo_rooty() + y,
        )
    except Exception:
        box.event_generate("<Button-3>", x=x, y=y)

    try:
        app.update_idletasks()
    except Exception:
        pass

    menu, entries = base._find_context_menu(app)
    if menu is None:
        raise RuntimeError(
            "Không đọc được menu chuột phải gốc. Hãy để AUTO ở Dashboard rồi bấm Đọc menu lại."
        )

    actions = []
    for entry in entries:
        aid = base._action_id(entry.get("label"))
        if not aid:
            continue
        actions.append(
            {
                "id": aid,
                "label": entry.get("label", ""),
                "enabled": entry.get("state") != "disabled",
                "danger": aid == "delete",
                "opens_settings": aid in {"wait_time", "delete_items_kc"},
            }
        )

    try:
        menu.unpost()
    except Exception:
        pass
    return row, menu, entries, actions


# v2 resolves all GUI calls on Tk's main thread. Replace only the unsafe popup
# opening primitive; v2's HTTP/auth/popup handling stays unchanged.
base._open_context_menu = _safe_open_context_menu


def start_function_actions_bridge(app, host="127.0.0.1", port=8769):
    server = bridge_v2.start_function_actions_bridge(app, host=host, port=port)
    print(f"[LOCAL-FUNCTION-ACTIONS] v1.2 non-blocking context bridge: http://{host}:{port}")
    return server
