from __future__ import annotations

import inspect
import threading
import time
from typing import Any, Callable, Iterable


class AutoProNavigationAdapter:
    """Safe compatibility layer around recovered AUTO PRO navigation methods."""

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

    def go_to_friend_home(self, friend_ordinal: int) -> None:
        self._ensure_running()
        method, owner_name = self._resolve(self.FRIEND_METHODS)
        self.log(f"Đi tới nhà bạn số {int(friend_ordinal)} bằng {owner_name}.{method.__name__}")
        self._invoke(
            method,
            {
                "friend_ordinal": int(friend_ordinal),
                "friend_index": int(friend_ordinal),
                "num_friend": int(friend_ordinal),
                "num_friend_for_bsf": int(friend_ordinal),
                "stop_event": self.stop_event,
            },
        )
        self._wait_for_any(
            ("friend_home", "icon_home", "kho_ban", "shop_friend"),
            timeout=45.0,
            description="nhà bạn",
        )

    def open_target_stall(self, stall_id: int) -> None:
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

    def swipe_next_stall_page(self) -> None:
        self._ensure_running()
        method = getattr(self.controller, "_rollbackItem", None)
        if callable(method):
            self._invoke(method, {"stop_event": self.stop_event})
        else:
            self.driver.swipe(633, 546, 540, 540, duration=0.35)
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
