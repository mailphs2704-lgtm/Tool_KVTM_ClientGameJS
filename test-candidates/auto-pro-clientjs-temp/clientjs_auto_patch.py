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


def _pc_open_game(self, stop_event=None):
    """Restart ClientJS directly; never require the Android launcher icon."""
    self.update_progress("Khởi động lại ClientJS")
    self.driver.app_stop("vn.kvtm.js")
    if _stopped(stop_event):
        return
    time.sleep(1.0)
    self.driver.app_start("vn.kvtm.js")

    deadline = time.monotonic() + 180.0
    clicked_intermediate = False
    while time.monotonic() < deadline:
        if _stopped(stop_event):
            return
        if _find(self, "friend_off", 0.84) or _find(self, "icon_home", 0.84):
            self.update_progress("Đã vào game ClientJS")
            break

        # Some accounts still show one intermediary screen. It is optional:
        # ClientJS may open directly into the game and never expose icon_game.
        if _find(self, "tai_khoan", 0.82, click=True):
            self.driver.click(984, 341)
            clicked_intermediate = True
        elif _find(self, "tai_khoan_on", 0.82):
            self.driver.click(981, 338)
            clicked_intermediate = True
        elif _find(self, "icon_game", 0.80, click=True):
            clicked_intermediate = True

        self.update_progress(
            "Chờ giao diện game" if clicked_intermediate else "Chờ ClientJS vào game"
        )
        time.sleep(1.0)
    else:
        raise RuntimeError("ClientJS đã mở nhưng không nhận được màn hình game sau 180 giây")

    delay = max(0, int(getattr(self, "delay_vao_game", 0)))
    for remaining in range(delay, 0, -1):
        if _stopped(stop_event):
            return
        self.update_progress(f"Chờ : {remaining}s")
        time.sleep(1.0)

    for _ in range(10):
        if _stopped(stop_event):
            return
        if _find(self, "close_game", 0.80, click=True):
            time.sleep(0.3)
            continue
        if _find(self, "friend_off", 0.84) or _find(self, "icon_home", 0.84):
            self.update_progress("Bắt Đầu Cào")
            return
        self.press_back(stop_event)
        time.sleep(0.5)


def _install_controller_patch(adb_controller_module) -> None:
    cls = adb_controller_module.ADBController
    if getattr(cls, "_clientjs_shop_patch_installed", False):
        return
    cls._rollbackItem = _rollback_item
    cls._scroll_back_shop = _scroll_back_shop
    cls._rolldownItem = _rolldown_item

    original_open_game = cls.openGame
    original_open_chests = cls.openChests

    def open_game(self, stop_event=None):
        if str(getattr(self, "device_id", "")).startswith(("PC:", "PCID:")):
            return _pc_open_game(self, stop_event)
        return original_open_game(self, stop_event)

    def open_chests(self, stop_event=None):
        """Keep the legacy chest flow but handle ClientJS's text-only open prompt."""
        if not str(getattr(self, "device_id", "")).startswith(("PC:", "PCID:")):
            return original_open_chests(self, stop_event)

        processor = self.image_processor
        original_find = processor.find_image
        original_click = self.driver.click
        fallback_used = False
        chest_screen_changed = False

        def click_without_post_open_replay(x, y, *args, **kwargs):
            # AUTO PRO replays its LD confirmation point after mo_ruong
            # succeeds. Once ClientJS has visibly opened the chest, suppress
            # that one legacy replay so it cannot leak into the home screen.
            if (
                chest_screen_changed
                and abs(float(x) - 433.0) < 1.0
                and abs(float(y) - 557.0) < 1.0
            ):
                try:
                    self.driver._trace(
                        "clientjs_chest_post_open_click_suppressed",
                        logical=[float(x), float(y)],
                    )
                except Exception:
                    pass
                return None
            return original_click(x, y, *args, **kwargs)

        def _chest_region():
            frame = self.driver.screenshot(format="opencv")
            return frame[430:760, 270:730].copy()

        def _difference(before, after):
            try:
                import cv2
                return float(cv2.absdiff(before, after).mean())
            except Exception:
                return 0.0

        def find_with_clientjs_prompt(*args, **kwargs):
            nonlocal fallback_used, chest_screen_changed
            name = str(args[0]) if args else str(kwargs.get("tree_type", ""))
            result = original_find(*args, **kwargs)

            # ruong_go is visible both before and after opening. It is not a
            # valid success signal by itself on ClientJS.
            if name == "ruong_go" and fallback_used:
                # Feed the legacy loop a deterministic completion signal.
                # Its ruong_go template is not a valid post-open signal on
                # ClientJS, while the captured modal change is.
                return bool(chest_screen_changed)
            if name != "mo_ruong" or fallback_used:
                return result
            # Even when the LD template matches, its built-in click/legacy
            # coordinate is not a reliable ClientJS confirmation. Continue
            # with the ClientJS selected-chest center below.
            if not kwargs.get("click"):
                return result

            fallback_used = True
            try:
                self.gui.log(
                    "ClientJS: template mo_ruong đã đổi; xác nhận bằng thay đổi màn hình",
                    device_id=self.device_id,
                )
            except Exception:
                pass

            before = _chest_region()
            # AUTO PRO/LD clicks (433, 557), but the live ClientJS
            # capture places the selected chest center around (500, 470).
            # Tap the chest itself first, then retain the LD point as fallback.
            # Repeat a point like
            # AUTO PRO (up to five taps), and stop immediately after a real
            # modal change so no tap can leak into the game behind it.
            for x, y in ((500, 470), (433, 557)):
                for attempt in range(5):
                    if _stopped(stop_event):
                        return False
                    self.driver.click(x, y)
                    time.sleep(0.65)
                    after = _chest_region()
                    score = _difference(before, after)
                    try:
                        self.driver._trace(
                            "clientjs_chest_probe",
                            logical=[x, y],
                            attempt=attempt + 1,
                            screen_change=round(score, 3),
                        )
                    except Exception:
                        pass
                    if score >= 2.0:
                        chest_screen_changed = True
                        return True
                    before = after

            try:
                self.gui.log(
                    "ClientJS: đã nhấn vùng rương nhưng màn hình không thay đổi",
                    device_id=self.device_id,
                )
            except Exception:
                pass
            return False

        processor.find_image = find_with_clientjs_prompt
        self.driver.click = click_without_post_open_replay
        try:
            return original_open_chests(self, stop_event)
        finally:
            self.driver.click = original_click
            processor.find_image = original_find

    cls.openGame = open_game
    cls.openChests = open_chests
    cls._clientjs_shop_patch_installed = True


def install_clientjs_auto_patch() -> None:
    import adb_controller
    import gui_tab_settings

    _install_controller_patch(adb_controller)
    _install_settings_ui(gui_tab_settings)
