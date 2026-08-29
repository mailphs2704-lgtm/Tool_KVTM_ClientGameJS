from __future__ import annotations

# v1.3: never synthesize <Button-3> and never call tk_popup().
# The original GUI creates the context Menu up-front; we can select the same
# Listbox row, read that Menu object directly, and invoke its command callback
# without ever posting the visible desktop menu.

import local_function_actions_bridge as base
import local_function_actions_bridge_v2 as bridge_v2


def _all_menu_candidates(app):
    seen = set()
    menus = []

    # Normal Tk widget tree.
    for widget in list(base._walk(app)):
        try:
            if str(widget.winfo_class() or "").lower() != "menu":
                continue
            key = str(widget)
            if key not in seen:
                seen.add(key)
                menus.append(widget)
        except Exception:
            pass

    # Defensive fallback: some recovered GUI builds keep Menu references only
    # as instance attributes and they may not appear where expected in the tree.
    try:
        values = list(vars(app).values())
    except Exception:
        values = []
    for value in values:
        try:
            if str(value.winfo_class() or "").lower() != "menu":
                continue
            key = str(value)
            if key not in seen:
                seen.add(key)
                menus.append(value)
        except Exception:
            pass
    return menus


def _find_existing_context_menu(app):
    candidates = []
    for menu in _all_menu_candidates(app):
        entries = base._menu_entries(menu)
        ids = [base._action_id(x.get("label")) for x in entries]
        score = sum(1 for x in ids if x)
        if score:
            candidates.append((score, len(entries), menu, entries))
    if not candidates:
        return None, []
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2], candidates[0][3]


def _passive_open_context_menu(app, option_index):
    # This name is kept only because bridge_v2 calls base._open_context_menu().
    # Nothing is actually opened/posted here.
    row, box, index = base._select_main_function(app, option_index)

    try:
        app.update_idletasks()
    except Exception:
        pass

    menu, entries = _find_existing_context_menu(app)
    if menu is None:
        raise RuntimeError(
            "Không tìm thấy Menu gốc đã tạo sẵn trong AUTO. "
            "Không phát chuột phải để tránh làm treo GUI."
        )

    # Ensure a menu left visible by an older build is dismissed. This does not
    # post anything and is safe even when the menu is already hidden.
    try:
        menu.unpost()
    except Exception:
        pass

    # The favorite caption is the only label the original right-click handler
    # commonly changes dynamically. Derive it from the actual selected Listbox
    # row instead of opening the menu just to refresh its caption.
    try:
        raw_selected = str(box.get(index))
        selected_is_favorite = raw_selected.lstrip().startswith("⭐") or raw_selected.lstrip().startswith("★")
    except Exception:
        selected_is_favorite = False

    actions = []
    patched_entries = []
    for entry in entries:
        e = dict(entry)
        aid = base._action_id(e.get("label"))
        if aid == "favorite":
            e["label"] = "☆ Bỏ yêu thích" if selected_is_favorite else "☆ Thêm yêu thích"
        patched_entries.append(e)
        if not aid:
            continue
        actions.append(
            {
                "id": aid,
                "label": e.get("label", ""),
                "enabled": e.get("state") != "disabled",
                "danger": aid == "delete",
                "opens_settings": aid in {"wait_time", "delete_items_kc"},
            }
        )

    return row, menu, patched_entries, actions


# bridge_v2 handles HTTP/auth/Tk-thread scheduling and popup mirroring. Replace
# only the menu lookup primitive with the fully passive implementation above.
base._open_context_menu = _passive_open_context_menu


def start_function_actions_bridge(app, host="127.0.0.1", port=8769):
    # Clean up a menu that might have been left posted by v0.10/v0.10.1 before
    # the user restarted the launcher.
    try:
        for menu in _all_menu_candidates(app):
            try:
                menu.unpost()
            except Exception:
                pass
    except Exception:
        pass

    server = bridge_v2.start_function_actions_bridge(app, host=host, port=port)
    print(f"[LOCAL-FUNCTION-ACTIONS] v1.3 PASSIVE menu bridge (no right-click/tk_popup): http://{host}:{port}")
    return server
