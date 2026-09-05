from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk


DEFAULT_SHOP_DRAG_SPEED = 0.35
MIN_SHOP_DRAG_SPEED = 0.05
MAX_SHOP_DRAG_SPEED = 3.0


def _stopped(stop_event) -> bool:
    return bool(stop_event and stop_event.is_set())


def _shop_speed(controller) -> float:
    value = getattr(controller, "shop_drag_speed", None)
    if value is None:
        try:
            value = controller.gui.new_settings_vars["shop_drag_speed"].get()
        except Exception:
            value = DEFAULT_SHOP_DRAG_SPEED
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = DEFAULT_SHOP_DRAG_SPEED
    return max(MIN_SHOP_DRAG_SPEED, min(MAX_SHOP_DRAG_SPEED, value))


def _shop_drag(controller, stop_event, start, end) -> None:
    if _stopped(stop_event):
        return
    duration = _shop_speed(controller)
    controller.driver.swipe(*start, *end, duration=duration)
    # Wait for the inertial list to settle before scanning or dragging again.
    time.sleep(max(0.18, min(0.8, duration * 0.65)))


def _rollback_item(self, stop_event=None):
    """Scroll one shop page forward without skipping the middle row."""
    for _ in range(2):
        if _stopped(stop_event):
            return
        _shop_drag(self, stop_event, (633, 546), (540, 540))


def _scroll_back_shop(self, stop_event=None):
    """Scroll one shop page backward using the configured drag duration."""
    for _ in range(2):
        if _stopped(stop_event):
            return
        _shop_drag(self, stop_event, (540, 540), (633, 546))


def _rolldown_item(self, stop_event=None):
    """Small vertical shop drag used by the old selling flow."""
    for _ in range(2):
        if _stopped(stop_event):
            return
        _shop_drag(self, stop_event, (210, 535), (210, 475))


def _walk_widgets(root):
    for child in root.winfo_children():
        yield child
        yield from _walk_widgets(child)


def _find_speed_grid(gui):
    target_var = str(gui.new_settings_vars["quay_speed"])
    for widget in _walk_widgets(gui.tab_settings):
        try:
            if widget.winfo_class() == "Entry" and str(widget.cget("textvariable")) == target_var:
                return widget.master.master
        except (tk.TclError, AttributeError):
            continue
    return None


def _install_settings_ui(gui_tab_settings_module) -> None:
    cls = gui_tab_settings_module.SettingsTabMixin
    if getattr(cls, "_clientjs_shop_ui_installed", False):
        return

    original_setup = cls._setup_settings_tab
    original_apply = cls.save_and_apply_settings
    # This method belongs to AutomationGUI in some recovered AUTO PRO builds,
    # while other builds expose it on the mixin. It is optional here.
    original_reset = getattr(cls, "reset_settings_to_default", None)

    def setup_with_shop_speed(self):
        self.new_settings_vars.setdefault(
            "shop_drag_speed", tk.StringVar(master=self, value=str(DEFAULT_SHOP_DRAG_SPEED))
        )
        original_setup(self)
        grid = _find_speed_grid(self)
        if grid is None:
            return
        frame = ttk.Frame(grid)
        frame.grid(row=3, column=3, padx=8, pady=6, sticky="w")
        tk.Entry(
            frame,
            textvariable=self.new_settings_vars["shop_drag_speed"],
            width=5,
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(frame, text="Tốc Độ Kéo Quầy", font=("Segoe UI", 9)).pack(side=tk.LEFT)

    def apply_with_shop_speed(self):
        try:
            value = float(self.new_settings_vars["shop_drag_speed"].get())
            if not MIN_SHOP_DRAG_SPEED <= value <= MAX_SHOP_DRAG_SPEED:
                raise ValueError
        except (TypeError, ValueError):
            messagebox.showerror(
                "Lỗi", "Tốc Độ Kéo Quầy phải từ 0.05 đến 3.0 giây.", parent=self
            )
            return

        result = original_apply(self)
        for task_info in self.task_manager.get_all_tasks().values():
            automation = getattr(task_info, "automation", None)
            controller = getattr(automation, "adb", None)
            if controller is not None:
                controller.shop_drag_speed = value
        return result

    def reset_with_shop_speed(self):
        result = original_reset(self) if original_reset is not None else None
        self.new_settings_vars["shop_drag_speed"].set(str(DEFAULT_SHOP_DRAG_SPEED))
        return result

    cls._setup_settings_tab = setup_with_shop_speed
    cls.save_and_apply_settings = apply_with_shop_speed
    if original_reset is not None:
        cls.reset_settings_to_default = reset_with_shop_speed
    cls._clientjs_shop_ui_installed = True


def _find(controller, name, threshold=0.85, click=False):
    try:
        return bool(
            controller.image_processor.find_image(name, threshold=threshold, click=click)
        )
    except Exception:
        return False


def _blocking_game_overlay(controller) -> bool:
    """Reject chest screens that leave farm anchors visible behind a dark modal."""
    return any(
        _find(controller, name, 0.74)
        for name in ("mo_ruong", "ruong_go")
    )


def _game_anchor(controller) -> bool:
    if _blocking_game_overlay(controller):
        return False
    return any(
        _find(controller, name, 0.78)
        for name in (
            "friend_off", "friend", "icon_home", "quay_hang",
            "cua_hang", "clock",
        )
    )


def _rendered_client_frame(controller):
    """Return one valid 1000x1000 ClientJS frame, or None while bridge/loading fails."""
    try:
        import cv2
        frame = controller.driver.screenshot(format="opencv")
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        height, width = frame.shape[:2]
        if width < 800 or height < 750:
            return None
        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGRA2GRAY
            if len(frame.shape) == 3 and frame.shape[2] == 4
            else cv2.COLOR_BGR2GRAY,
        )
        mean = float(gray.mean())
        deviation = float(gray.std())
        if 5.0 < mean < 250.0 and deviation >= 18.0:
            return frame
    except Exception:
        return None
    return None


def _pc_open_game(self, stop_event=None):
    """Reuse a live game first; restart only when no usable frame is available."""
    self.update_progress("Kiểm tra giao diện ClientJS đang chạy")
    attached_frame_streak = 0
    for _attempt in range(12):
        if _stopped(stop_event):
            return
        if _game_anchor(self):
            self.update_progress("Bắt Đầu AUTO • đã nhận giao diện hiện tại")
            return
        blocking_overlay = _blocking_game_overlay(self)
        attached_frame_streak = (
            attached_frame_streak + 1
            if not blocking_overlay and _rendered_client_frame(self) is not None
            else 0
        )
        if blocking_overlay:
            self.update_progress(
                "ClientJS còn kẹt màn hình rương • chuẩn bị reset"
            )
        if attached_frame_streak >= 3:
            self.update_progress("Bắt Đầu AUTO • bridge có 3 frame ổn định")
            try:
                self.driver._trace(
                    "clientjs_attached_game_ready",
                    pid=int(getattr(self.driver, "pid", 0)),
                    consecutive_frames=attached_frame_streak,
                    restart_skipped=True,
                )
            except Exception:
                pass
            return
        time.sleep(0.5)

    self.update_progress("Không có frame ổn định • khởi động lại ClientJS")
    self.driver.app_stop("vn.kvtm.js")
    if _stopped(stop_event):
        return
    time.sleep(1.0)
    self.driver.app_start("vn.kvtm.js")

    deadline = time.monotonic() + 180.0
    started = time.monotonic()
    clicked_intermediate = False
    rendered_streak = 0
    ready_by_capture = False
    reopen_clicks = 0
    last_reopen_click = 0.0
    while time.monotonic() < deadline:
        if _stopped(stop_event):
            return
        if _game_anchor(self):
            self.update_progress("Đã vào game ClientJS")
            break

        # Some accounts still show one intermediary screen. It is optional:
        # ClientJS may open directly into the game and never expose icon_game.
        if _find(self, "tai_khoan", 0.82, click=True):
            self.driver.click(984, 341)
            clicked_intermediate = True
            rendered_streak = 0
        elif _find(self, "tai_khoan_on", 0.82):
            self.driver.click(981, 338)
            clicked_intermediate = True
            rendered_streak = 0
        elif _find(self, "icon_game", 0.80, click=True):
            clicked_intermediate = True
            rendered_streak = 0
        elif (
            time.monotonic() - started >= 2.0
            and time.monotonic() - last_reopen_click >= 2.5
            and reopen_clicks < 2
        ):
            # AUTO PRO always taps this account/reopen position while waiting,
            # even when the tai_khoan asset is not recognised. ClientJS shows
            # an untemplated "mở lại" popup after a process replacement; merely
            # receiving bridge frames does not mean that popup was dismissed.
            self.driver.click(981, 338)
            reopen_clicks += 1
            last_reopen_click = time.monotonic()
            clicked_intermediate = True
            # Do not reset rendered_streak here. Resetting it on every popup
            # tap prevented the three-frame readiness condition forever.
            try:
                self.driver._trace(
                    "clientjs_reopen_popup_probe",
                    attempt=reopen_clicks,
                    logical=[981, 338],
                )
            except Exception:
                pass
        elif time.monotonic() - started >= 10.0 and reopen_clicks >= 2:
            # Templates can change independently of the game. A replacement
            # PID with three consecutive nonblank bridge frames is sufficient
            # to hand control to the popup cleanup below.
            rendered_streak = (
                rendered_streak + 1
                if (
                    not _blocking_game_overlay(self)
                    and _rendered_client_frame(self) is not None
                )
                else 0
            )
            if rendered_streak >= 3:
                ready_by_capture = True
                self.update_progress("ClientJS đã render game • tiếp tục AUTO")
                try:
                    self.driver._trace(
                        "clientjs_game_ready_by_live_capture",
                        profile_id=getattr(self.driver, "profile_id", None),
                        pid=int(getattr(self.driver, "pid", 0)),
                        consecutive_frames=rendered_streak,
                    )
                except Exception:
                    pass
                break

        self.update_progress(
            "Chờ giao diện game" if clicked_intermediate else "Chờ ClientJS vào game"
        )
        time.sleep(1.0)
    else:
        raise RuntimeError(
            "ClientJS/PID mới không có template game và bridge không trả 3 frame hợp lệ"
        )

    delay = max(0, int(getattr(self, "delay_vao_game", 0)))
    for remaining in range(delay, 0, -1):
        if _stopped(stop_event):
            return
        self.update_progress(f"Chờ : {remaining}s")
        time.sleep(1.0)

    post_popup_frame_streak = 0
    cleanup_actions = 0
    for cleanup_attempt in range(12):
        if _stopped(stop_event):
            return
        if _game_anchor(self):
            self.update_progress("Bắt Đầu AUTO trên PID ClientJS mới")
            return

        closed_popup = (
            _find(self, "close_game", 0.80, click=True)
            or _find(self, "x_popup_event", 0.76, click=True)
            or _find(self, "dong_y", 0.76, click=True)
        )
        if closed_popup:
            cleanup_actions += 1
            post_popup_frame_streak = 0
            time.sleep(0.7)
            continue

        if cleanup_attempt < 2:
            # A restarted ClientJS commonly needs the untemplated reopen tap.
            self.driver.click(981, 338)
            cleanup_actions += 1
            post_popup_frame_streak = 0
            action = "reopen_click"
            time.sleep(1.0)
        elif ready_by_capture and cleanup_actions > 0:
            post_popup_frame_streak = (
                post_popup_frame_streak + 1
                if (
                    not _blocking_game_overlay(self)
                    and _rendered_client_frame(self) is not None
                )
                else 0
            )
            action = "verify_post_cleanup_frame"
            if post_popup_frame_streak >= 3:
                self.update_progress("Bắt Đầu AUTO trên PID ClientJS mới")
                try:
                    self.driver._trace(
                        "clientjs_post_reset_ready",
                        pid=int(getattr(self.driver, "pid", 0)),
                        consecutive_frames=post_popup_frame_streak,
                        cleanup_actions=cleanup_actions,
                    )
                except Exception:
                    pass
                return
            time.sleep(0.5)
        else:
            self.press_back(stop_event)
            cleanup_actions += 1
            post_popup_frame_streak = 0
            action = "back"
            time.sleep(0.5)
        try:
            self.driver._trace(
                "clientjs_post_reset_cleanup",
                attempt=cleanup_attempt + 1,
                action=action,
                live_frame=bool(_rendered_client_frame(self) is not None),
                home_ready=bool(_game_anchor(self)),
            )
        except Exception:
            pass

    # No anchor and no stable post-popup frame: stop explicitly instead of
    # leaving the account indefinitely in a misleading waiting state.
    raise RuntimeError(
        "ClientJS đã nhận PID mới nhưng chưa đóng được popup mở lại để vào màn hình chính"
    )


def _install_controller_patch(adb_controller_module) -> None:
    cls = adb_controller_module.ADBController
    if getattr(cls, "_clientjs_shop_patch_installed", False):
        return
    cls._rollbackItem = _rollback_item
    cls._scroll_back_shop = _scroll_back_shop
    cls._rolldownItem = _rolldown_item

    original_open_game = cls.openGame
    original_open_chests = cls.openChests
    original_vong_quay = cls.VongQuay

    def open_game(self, stop_event=None):
        if str(getattr(self, "device_id", "")).startswith(("PC:", "PCID:")):
            return _pc_open_game(self, stop_event)
        return original_open_game(self, stop_event)

    def open_chests(self, stop_event=None):
        """Keep AUTO PRO navigation; patch only the two ClientJS modal states."""
        if not str(getattr(self, "device_id", "")).startswith(("PC:", "PCID:")):
            return original_open_chests(self, stop_event)

        processor = self.image_processor
        original_find = processor.find_image
        original_click = self.driver.click
        modal_ready = False
        chest_opened = False

        def chest_region():
            frame = self.driver.screenshot(format="opencv")
            return frame[350:760, 180:820].copy()

        def difference(before, after):
            try:
                import cv2
                return float(cv2.absdiff(before, after).mean())
            except Exception:
                return 0.0

        def silver_visible_exact() -> bool:
            try:
                return bool(original_find("ruong_bac", threshold=1.0, click=False))
            except Exception:
                return False

        def wait_silver_disappeared() -> bool:
            absent_streak = 0
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                if _stopped(stop_event):
                    return False
                if not silver_visible_exact():
                    absent_streak += 1
                    if absent_streak >= 2:
                        return True
                else:
                    absent_streak = 0
                time.sleep(0.20)
            return False

        def click_with_chest_state(x, y, *args, **kwargs):
            nonlocal modal_ready
            # This is AUTO PRO's wooden-chest selection click. Let AUTO PRO
            # navigate into the chest interface first; patch only this click.
            if abs(float(x) - 371.0) < 1.0 and abs(float(y) - 647.0) < 1.0:
                if not silver_visible_exact():
                    modal_ready = True
                    try:
                        self.driver._trace(
                            "clientjs_chest_modal_ready",
                            entry_state="MODAL_ALREADY_OPEN",
                            silver_threshold=1.0,
                            selection_skipped=True,
                        )
                    except Exception:
                        pass
                    return None
                result = original_click(x, y, *args, **kwargs)
                if not wait_silver_disappeared():
                    raise RuntimeError(
                        "Đã chọn Rương gỗ nhưng Rương bạc chưa biến mất ở ngưỡng 1.0"
                    )
                modal_ready = True
                try:
                    self.driver._trace(
                        "clientjs_chest_modal_ready",
                        entry_state="CHOOSER",
                        silver_threshold=1.0,
                    )
                except Exception:
                    pass
                return result
            if (
                chest_opened
                and abs(float(x) - 433.0) < 1.0
                and abs(float(y) - 557.0) < 1.0
            ):
                return None
            return original_click(x, y, *args, **kwargs)

        def find_with_chest_state(*args, **kwargs):
            nonlocal modal_ready, chest_opened
            name = str(args[0]) if args else str(kwargs.get("tree_type", ""))
            if name == "ruong_go" and chest_opened:
                return True
            if name != "mo_ruong" or not kwargs.get("click"):
                return original_find(*args, **kwargs)

            # Never let AUTO PRO click the LD coordinate. Probe its template,
            # then execute the ClientJS modal action at the verified center.
            probe_kwargs = dict(kwargs)
            probe_kwargs["click"] = False
            legacy_result = original_find(*args, **probe_kwargs)
            if not modal_ready:
                if silver_visible_exact():
                    return legacy_result
                modal_ready = True
                try:
                    self.driver._trace(
                        "clientjs_chest_modal_ready",
                        entry_state="MODAL_ALREADY_OPEN",
                        silver_threshold=1.0,
                        selection_skipped=True,
                    )
                except Exception:
                    pass

            before = chest_region()
            for attempt in range(1, 6):
                if _stopped(stop_event):
                    return False
                original_click(500, 470)
                time.sleep(1.0)
                after = chest_region()
                score = difference(before, after)
                try:
                    self.driver._trace(
                        "clientjs_chest_open_probe",
                        logical=[500, 470],
                        attempt=attempt,
                        screen_change=round(score, 3),
                        completion_threshold=8.0,
                    )
                except Exception:
                    pass
                if score >= 8.0:
                    chest_opened = True
                    return True
                before = after
            return False

        processor.find_image = find_with_chest_state
        self.driver.click = click_with_chest_state
        try:
            # AUTO PRO remains responsible for entering the chest UI and for
            # its normal workflow ordering. Only selection/open are patched.
            result = original_open_chests(self, stop_event)
        finally:
            self.driver.click = original_click
            processor.find_image = original_find

        if not chest_opened or _stopped(stop_event):
            return result

        self.update_progress("Rương đã mở • đang thoát về màn hình chính")
        for attempt in range(1, 13):
            if _stopped(stop_event):
                return result
            if _game_anchor(self):
                self.update_progress("Mở rương hoàn tất • đã về màn hình chính")
                return result
            action = "back"
            for name in ("close_game", "x_popup_event", "dong_y"):
                if _find(self, name, 0.72, click=True):
                    action = name
                    break
            else:
                self.press_back(stop_event)
            time.sleep(0.45)
            try:
                self.driver._trace(
                    "clientjs_chest_exit_probe",
                    attempt=attempt,
                    action=action,
                    home_ready=_game_anchor(self),
                    blocking_overlay=_blocking_game_overlay(self),
                )
            except Exception:
                pass
        raise RuntimeError("Rương đã mở nhưng chưa xác nhận thoát về màn hình chính")

    def vong_quay(self, luotquay, stop_event=None):
        """Run AUTO PRO spins, then always return ClientJS to the farm screen."""
        result = original_vong_quay(self, luotquay, stop_event)
        if not str(getattr(self, "device_id", "")).startswith(("PC:", "PCID:")):
            return result
        for attempt in range(1, 9):
            if _stopped(stop_event) or _game_anchor(self):
                return result
            # Reward and wheel overlays do not close consistently with a
            # single Android BACK on ClientJS. Prefer their visible close
            # controls, then use the fixed top-right close and BACK fallback.
            for name in ("close_game", "x_popup_event", "dong_y"):
                if _find(self, name, 0.72, click=True):
                    time.sleep(0.45)
                    break
            else:
                self.driver.click(965, 198)
                time.sleep(0.35)
                self.press_back(stop_event)
                time.sleep(0.45)
            try:
                self.driver._trace(
                    "clientjs_wheel_exit_probe",
                    attempt=attempt,
                    home_ready=_game_anchor(self),
                )
            except Exception:
                pass
        try:
            self.gui.log(
                "ClientJS: đã quay/nhận quà nhưng chưa xác nhận thoát màn hình quay",
                device_id=self.device_id,
            )
        except Exception:
            pass
        return result

    cls.openGame = open_game
    cls.openChests = open_chests
    cls.VongQuay = vong_quay
    cls._clientjs_shop_patch_installed = True


def install_clientjs_auto_patch() -> None:
    import adb_controller
    import gui_tab_settings

    _install_controller_patch(adb_controller)
    _install_settings_ui(gui_tab_settings)
