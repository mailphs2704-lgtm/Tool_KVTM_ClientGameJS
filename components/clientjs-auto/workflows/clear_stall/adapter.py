from __future__ import annotations

import inspect
import threading
import time
from typing import Any, Callable, Iterable


class AutoProNavigationAdapter:
    """Compatibility layer around recovered AUTO PRO navigation methods."""

    FRIEND_METHODS = (
        "GoFiendHome",  # spelling used by the recovered AUTO PRO build
        "GoFriendHome",
        "goFriendHome",
        "go_friend_home",
    )
    HOME_METHODS = (
        "goHome",
        "GoHome",
        "go_home",
        "backHome",
        "BackHome",
    )
    STALL_METHODS = (
        "goKho",
        "GoKho",
        "openKho",
        "OpenKho",
        "openShop",
        "OpenShop",
    )

    def __init__(
        self,
        automation: Any,
        *,
        stop_event: threading.Event,
        logger: Callable[[str], None],
    ) -> None:
        self.automation = automation
        self.controller = getattr(automation, "adb", None)
        if self.controller is None:
            raise RuntimeError("AUTO PRO không tạo được ADBController")
        self.driver = getattr(self.controller, "driver", None)
        if self.driver is None:
            raise RuntimeError("ADBController không có driver ClientJS")
        self.stop_event = stop_event
        self.log = logger
        self._popup_guard_thread: threading.Thread | None = None
        try:
            setattr(self.controller, "_stop_event", self.stop_event)
        except Exception:
            pass

    def start_auto_pro_popup_guard(self) -> bool:
        """Run AUTO PRO's original event/popup task once in the background."""
        method = getattr(self.controller, "eventgame", None)
        if not callable(method):
            self.log("AUTO PRO không có eventgame; bỏ qua popup guard")
            return False
        thread = self._popup_guard_thread
        if thread is not None and thread.is_alive():
            return True

        def runner() -> None:
            try:
                self._invoke(method, {"stop_event": self.stop_event})
            except InterruptedError:
                return
            except Exception as exc:
                if not self.stop_event.is_set():
                    self.log(f"Popup guard Auto Pro dừng: {exc}")

        self._popup_guard_thread = threading.Thread(
            target=runner,
            name="autopro-popup-guard",
            daemon=True,
        )
        self._popup_guard_thread.start()
        self.log("Đã bật cơ chế bỏ popup gốc của Auto Pro (eventgame)")
        return True

    def ensure_main_screen(self, timeout: float = 180.0) -> None:
        """Reach the main screen while AUTO PRO eventgame owns popup handling."""
        self.start_auto_pro_popup_guard()
        deadline = time.monotonic() + float(timeout)
        last_progress = 0.0
        while time.monotonic() < deadline:
            self._ensure_running()
            if self._find_any(("friend_off", "icon_home")):
                self.log("Đã xác nhận màn hình chính ClientJS")
                return

            clicked = False
            try:
                if self.controller.image_processor.find_image(
                    "tai_khoan", threshold=0.82, click=True
                ):
                    self.driver.click(984, 341)
                    self.log("Đã chọn tài khoản ClientJS")
                    clicked = True
                elif self.controller.image_processor.find_image(
                    "tai_khoan_on", threshold=0.82, click=False
                ):
                    self.driver.click(981, 338)
                    self.log("Đã chọn tài khoản đang online")
                    clicked = True
                elif self.controller.image_processor.find_image(
                    "icon_game", threshold=0.80, click=True
                ):
                    self.log("Đã mở game từ màn hình trung gian")
                    clicked = True
            except Exception:
                pass

            now = time.monotonic()
            if now - last_progress >= 5.0:
                remaining = max(0, int(deadline - now))
                self.log(
                    "Auto Pro đang xử lý màn hình vào game/popup • "
                    f"còn {remaining}s"
                )
                last_progress = now
            time.sleep(0.7 if clicked else 1.0)
        raise RuntimeError(
            f"Không nhận được màn hình chính ClientJS sau {timeout:.0f}s"
        )

    def configure_target(self, friend_ordinal: int, stall_id: int) -> None:
        friend = int(friend_ordinal)
        stall = int(stall_id)
        if not 1 <= friend <= 500:
            raise ValueError("Số thứ tự bạn bè phải trong khoảng 1..500")
        if not 1 <= stall <= 4:
            raise ValueError("Số quầy phải trong khoảng 1..4")
        for owner in (self.automation, self.controller):
            setattr(owner, "num_friend_for_bsf", friend)
            setattr(owner, "buy_sell_friend_kho_id", stall)
            setattr(owner, "go_friend_home", True)

    def go_to_friend_home(self, friend_ordinal: int, *, verify: bool = True) -> None:
        """Navigate only; recovered GoFiendHome must never buy during discovery."""
        self._ensure_running()
        friend = int(friend_ordinal)
        method, owner_name = self._resolve(self.FRIEND_METHODS)
        self.log(
            f"Đi tới đúng nhà bạn số {friend} bằng "
            f"{owner_name}.{method.__name__} (visit-only)"
        )
        self._invoke(
            method,
            {
                "friend_ordinal": friend,
                "friend_index": friend,
                "num_friend": friend,
                "num_friend_for_bsf": friend,
                "specific_friend_pos": friend,
                "items": [],
                "purchase_limit": 0,
                "visit_only": True,
                "stop_event": self.stop_event,
            },
        )
        if verify:
            self._wait_for_any(
                ("friend_home", "icon_home", "kho_ban", "shop_friend"),
                timeout=45.0,
                description="nhà bạn",
            )

    def open_target_stall(self, stall_id: int, *, verify: bool = True) -> None:
        self._ensure_running()
        method, owner_name = self._resolve(self.STALL_METHODS)
        self.log(f"Mở quầy {int(stall_id)} bằng {owner_name}.{method.__name__}")
        self._invoke(
            method,
            {
                "kho_id": int(stall_id),
                "stall_id": int(stall_id),
                "shop_id": int(stall_id),
                "buy_sell_friend_kho_id": int(stall_id),
                "stop_event": self.stop_event,
            },
        )
        if verify:
            self._wait_for_any(
                ("shop", "shop_friend", "kho_ban", "buy_item"),
                timeout=30.0,
                description=f"quầy {int(stall_id)}",
            )

    def return_to_clone_home(self) -> None:
        self._ensure_running()
        try:
            method, owner_name = self._resolve(self.HOME_METHODS)
        except RuntimeError:
            method = None
            owner_name = ""
        if method is not None:
            self.log(f"Quay về nhà clone bằng {owner_name}.{method.__name__}")
            self._invoke(method, {"stop_event": self.stop_event})
        else:
            self.log("AUTO PRO không có goHome; dùng press_back có xác nhận")
            press_back = getattr(self.controller, "press_back", None)
            if not callable(press_back):
                raise RuntimeError("Không có method quay về nhà clone")
            for _ in range(8):
                self._ensure_running()
                if self._find_any(("friend_off", "icon_home")):
                    break
                self._invoke(press_back, {"stop_event": self.stop_event})
                time.sleep(0.6)
        self._wait_for_any(
            ("friend_off", "icon_home"),
            timeout=30.0,
            description="màn hình chính của clone",
        )

    def open_clone_stall_for_sale(self, stall_id: int) -> None:
        """Open the clone's own stall after return; never reuse friend state."""
        self._ensure_running()
        if not self._find_any(("friend_off", "icon_home")):
            raise RuntimeError("Chưa xác nhận màn hình chính của clone")
        method, owner_name = self._resolve(self.STALL_METHODS)
        self.log(
            f"Mở quầy bán của clone {int(stall_id)} bằng "
            f"{owner_name}.{method.__name__}"
        )
        self._invoke(
            method,
            {
                "kho_id": int(stall_id),
                "stall_id": int(stall_id),
                "shop_id": int(stall_id),
                "buy_sell_friend_kho_id": int(stall_id),
                "stop_event": self.stop_event,
            },
        )
        self._wait_for_any(
            ("shop", "kho_ban", "sell_item", "ban_vat_pham"),
            timeout=30.0,
            description=f"quầy bán của clone {int(stall_id)}",
        )

    def swipe_next_stall_page(self) -> None:
        self._ensure_running()
        method = getattr(self.controller, "_rollbackItem", None)
        if callable(method):
            self._invoke(method, {"stop_event": self.stop_event})
        else:
            self.driver.swipe(633, 546, 540, 540, duration=0.35)
        time.sleep(0.35)

    def swipe_previous_stall_page(self) -> None:
        self._ensure_running()
        method = getattr(self.controller, "_scroll_back_shop", None)
        if callable(method):
            self._invoke(method, {"stop_event": self.stop_event})
        else:
            self.driver.swipe(540, 540, 633, 546, duration=0.35)
        time.sleep(0.35)

    def screenshot(self):
        self._ensure_running()
        return self.driver.screenshot(format="opencv")

    def _resolve(self, names: Iterable[str]) -> tuple[Callable, str]:
        for owner, owner_name in (
            (self.automation, "FarmAutomation"),
            (self.controller, "ADBController"),
        ):
            for name in names:
                method = getattr(owner, name, None)
                if callable(method):
                    return method, owner_name
        raise RuntimeError(
            "AUTO PRO thiếu method tương thích: " + ", ".join(names)
        )

    def _invoke(self, method: Callable, values: dict[str, Any]):
        signature = inspect.signature(method)
        positional = []
        keyword = {}
        unresolved = []
        for parameter in signature.parameters.values():
            if parameter.name in {"self", "cls"}:
                continue
            if parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue
            if parameter.name in values:
                value = values[parameter.name]
                if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                    positional.append(value)
                else:
                    keyword[parameter.name] = value
            elif parameter.default is inspect.Parameter.empty:
                unresolved.append(parameter.name)
        if unresolved:
            raise RuntimeError(
                f"Không gọi {method.__name__}: thiếu tham số {unresolved}"
            )
        return method(*positional, **keyword)

    def _find_any(self, names: Iterable[str]) -> bool:
        processor = getattr(self.controller, "image_processor", None)
        finder = getattr(processor, "find_image", None)
        if not callable(finder):
            return False
        for name in names:
            try:
                if finder(name, threshold=0.80, click=False):
                    return True
            except Exception:
                continue
        return False

    def _wait_for_any(
        self,
        names: Iterable[str],
        *,
        timeout: float,
        description: str,
    ) -> None:
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self._ensure_running()
            if self._find_any(names):
                self.log(f"Đã xác nhận {description}")
                return
            time.sleep(0.4)
        raise RuntimeError(f"Không xác nhận được {description} sau {timeout:.0f}s")

    def _ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Dọn quầy đã được yêu cầu dừng")
