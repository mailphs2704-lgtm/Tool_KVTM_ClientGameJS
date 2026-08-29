from __future__ import annotations

# v1.4: refresh the original right-click context without ever posting a menu.
# Some callbacks (notably "Chọn VP xóa (KC)") depend on the index/context that
# the original <Button-3> handler stores. Merely selecting the Listbox row is
# not enough. We therefore run that handler while temporarily suppressing
# Menu.tk_popup()/Menu.post(), then invoke the already-configured callback.

import time
import tkinter as tk
import uuid

import local_function_actions_bridge as base
import local_function_actions_bridge_v2 as bridge_v2
import local_function_actions_bridge_v4 as passive


def _build_actions(box, index, entries):
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
    return patched_entries, actions


def _refresh_context_without_popup(app, option_index):
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

    # Suppress every normal Tk path that can make a context Menu visible.
    # The event handler still runs synchronously, so it can set its private
    # right-click index and reconfigure all menu commands/labels.
    orig_tk_popup = tk.Menu.tk_popup
    orig_post = tk.Menu.post

    def _no_popup(self, *args, **kwargs):
        return None

    tk.Menu.tk_popup = _no_popup
    tk.Menu.post = _no_popup
    try:
        try:
            box.event_generate(
                "<Button-3>",
                x=x,
                y=y,
                rootx=box.winfo_rootx() + x,
                rooty=box.winfo_rooty() + y,
                when="now",
            )
        except Exception:
            box.event_generate("<Button-3>", x=x, y=y, when="now")
    finally:
        tk.Menu.tk_popup = orig_tk_popup
        tk.Menu.post = orig_post

    try:
        app.update_idletasks()
    except Exception:
        pass

    menu, entries = passive._find_existing_context_menu(app)
    if menu is None:
        raise RuntimeError(
            "Không tìm thấy Menu gốc sau khi cập nhật context. "
            "AUTO không bị mở menu desktop; hãy gửi ảnh Dashboard nếu lỗi tiếp diễn."
        )
    try:
        menu.unpost()
    except Exception:
        pass

    patched_entries, actions = _build_actions(box, index, entries)
    return row, menu, patched_entries, actions


# GET /actions and every action invocation now refresh the exact context safely.
base._open_context_menu = _refresh_context_without_popup


def _widget_signature(widget):
    # Lightweight signature used to detect a Toplevel that already existed but
    # was reconfigured/reused by the original callback.
    classes = []
    try:
        for child in list(base._walk(widget))[:120]:
            if child is widget:
                continue
            try:
                classes.append(str(child.winfo_class() or ""))
            except Exception:
                pass
    except Exception:
        pass
    return tuple(classes)


def _window_snapshot(app):
    out = {}
    for w in base._toplevels(app):
        try:
            path = str(w)
            out[path] = {
                "state": str(w.state() or ""),
                "mapped": bool(w.winfo_ismapped()),
                "viewable": bool(w.winfo_viewable()),
                "title": str(w.title() or ""),
                "geometry": str(w.geometry() or ""),
                "signature": _widget_signature(w),
            }
        except Exception:
            pass
    return out


def _pick_changed_window(app, before):
    current = _window_snapshot(app)
    grab_path = None
    try:
        grabbed = app.grab_current()
        if grabbed is not None:
            # climb to its Toplevel
            top = grabbed.winfo_toplevel()
            if top is not app:
                grab_path = str(top)
    except Exception:
        pass

    candidates = []
    for path, now in current.items():
        old = before.get(path)
        score = 0
        if old is None:
            score += 100
        else:
            if old.get("state") != now.get("state"):
                score += 60
            if old.get("mapped") != now.get("mapped"):
                score += 50
            if old.get("viewable") != now.get("viewable"):
                score += 50
            if old.get("title") != now.get("title"):
                score += 25
            if old.get("signature") != now.get("signature"):
                score += 25
            if old.get("geometry") != now.get("geometry"):
                score += 8
        if grab_path == path:
            score += 80
        # Prefer windows that contain actual form/list controls.
        sig = now.get("signature") or ()
        if any(x in sig for x in ("Listbox", "Treeview", "TEntry", "Entry", "TCombobox", "Checkbutton", "TCheckbutton")):
            score += 12
        if score > 0:
            candidates.append((score, path))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _invoke_action_v14(app, option_index, action_id, confirm=False):
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

    before = base._call_tk(app, lambda: _window_snapshot(app), timeout=3.0)
    captured, restore = base._patch_messageboxes(confirm=confirm)
    try:
        def schedule():
            def fire():
                try:
                    menu.invoke(int(entry["index"]))
                except Exception as exc:
                    print(f"[FUNCTION-ACTIONS v1.4] invoke {action_id}: {exc}")
            app.after(0, fire)
            return True

        base._call_tk(app, schedule, timeout=2.0)

        popup_path = None
        # KC item picker can build/reuse a larger dialog a little more slowly.
        deadline = time.time() + (5.5 if action_id == "delete_items_kc" else 3.2)
        while time.time() < deadline:
            try:
                popup_path = base._call_tk(
                    app, lambda: _pick_changed_window(app, before), timeout=1.0
                )
            except Exception:
                popup_path = None
            if popup_path or captured:
                break
            time.sleep(0.06)

        if popup_path:
            def hide_read():
                popup = base._popup_by_path(app, popup_path)
                if popup is None:
                    raise RuntimeError("Popup cấu hình vừa mở đã đóng")
                try:
                    popup.update_idletasks()
                    popup.withdraw()
                    popup.grab_release()
                except Exception:
                    pass
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
                data = base._inspect_popup(app, popup, sid, action_id, row)
                data["source"] = "REAL_CONTEXT_CALLBACK_REUSED_POPUP_V14"
                return data

            return base._call_tk(app, hide_read, timeout=6.0)

        time.sleep(0.15)
        if captured:
            return {
                "ok": True,
                "kind": "message",
                "action_id": action_id,
                "messages": list(captured),
                "row": row,
            }

        if action_id == "delete_items_kc":
            raise RuntimeError(
                "Callback Chọn VP xóa (KC) đã chạy nhưng chưa bắt được bảng chọn VP. "
                "Bản này đã set đúng right-click context; nếu còn lỗi hãy gửi ảnh popup gốc khi mở bằng AUTO desktop."
            )

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


# bridge_v2's HTTP server resolves this module global at request time, so
# replacing it before start_function_actions_bridge() is sufficient.
bridge_v2._invoke_action_safe = _invoke_action_v14


def start_function_actions_bridge(app, host="127.0.0.1", port=8769):
    try:
        for menu in passive._all_menu_candidates(app):
            try:
                menu.unpost()
            except Exception:
                pass
    except Exception:
        pass

    server = bridge_v2.start_function_actions_bridge(app, host=host, port=port)
    print(
        f"[LOCAL-FUNCTION-ACTIONS] v1.4 context-synced + reused-popup bridge: http://{host}:{port}"
    )
    return server
