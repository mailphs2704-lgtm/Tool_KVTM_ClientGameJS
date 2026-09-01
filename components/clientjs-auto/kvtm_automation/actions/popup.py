from __future__ import annotations

import time

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


class PopupActions:
    """Recover ClientJS to the clone's own farm/home screen."""

    # AUTO_PRO_REFERENCE + LIVE_VERIFIED: current hot-deal modal uses the old
    # x_popup_event shape at a different scale/color. Non-modal trace frames
    # remained below the 0.58 fallback threshold in this constrained region.
    X_ZONE = (550, 150, 450, 350)
    X_SCALES = (0.70, 0.75, 0.80, 0.85, 0.90, 1.00, 1.10, 1.20, 1.30)
    HOME_ZONE = (900, 900, 100, 100)
    FRIEND_ZONE = (0, 920, 100, 80)

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter

    def is_own_main_screen(self) -> bool:
        """Confirm the clone's own farm, not a friend's visited home."""
        if self.vision.find("icon_home", threshold=0.80, zone=self.HOME_ZONE) is not None:
            return False
        return bool(
            self.vision.find("friend_off", threshold=0.76, zone=self.FRIEND_ZONE)
            or self.vision.find("cua_hang", threshold=0.78, zone=self.HOME_ZONE)
        )

    # Compatibility name used by a few generic callers.
    def is_main_screen(self) -> bool:
        return self.is_own_main_screen()

    def dismiss_one(self) -> bool:
        """Close one modal with the reference x_popup_event at verified scales."""
        match = self.vision.find(
            "x_popup_event",
            threshold=0.80,
            zone=self.X_ZONE,
            click=True,
        )
        if match is None:
            match = self.vision.find(
                "x_popup_event",
                threshold=0.58,
                zone=self.X_ZONE,
                scales=self.X_SCALES,
                click=True,
            )
        if match is None:
            return False
        self.context.log(
            f"Đóng popup ClientJS bằng x_popup_event "
            f"(score={match.score:.3f}, scale={match.scale:.2f})"
        )
        self.waiter.sleep(0.45)
        return True

    def _handle_portal_entry(self) -> bool:
        """Enter the game/account using only template-guarded portal actions."""
        match = self.vision.find("tai_khoan", threshold=0.78, click=True)
        if match is not None:
            self.waiter.sleep(0.35)
            # AUTO_PRO_REFERENCE: account row after opening account selector.
            self.vision.driver.click(984, 341)
            self.context.log("Đã chọn tài khoản ClientJS")
            self.waiter.sleep(0.8)
            return True
        match = self.vision.find("tai_khoan_on", threshold=0.78)
        if match is not None:
            self.vision.driver.click(981, 338)
            self.context.log("Đã chọn tài khoản đang online")
            self.waiter.sleep(0.8)
            return True
        match = self.vision.find("icon_game", threshold=0.76, click=True)
        if match is not None:
            self.context.log("Đã mở KVTM từ portal ClientJS")
            self.waiter.sleep(1.0)
            return True
        return False

    def _return_from_visited_home(self) -> bool:
        """Recover a clone reopened while still visiting somebody else's home."""
        match = self.vision.find(
            "icon_home",
            threshold=0.80,
            zone=self.HOME_ZONE,
            click=True,
        )
        if match is None:
            return False
        self.context.log("ClientJS đang ở nhà bạn • quay về nhà clone trước")
        self.waiter.sleep(0.8)
        return True

    def ensure_main_screen(self, timeout: float = 90.0) -> None:
        deadline = time.monotonic() + float(timeout)
        last_status = 0.0
        while time.monotonic() < deadline:
            self.context.ensure_running()

            # A modal can leave farm HUD visible/dimmed behind it. Always give
            # modal dismissal priority so HUD templates cannot create a false
            # main-screen success while input is still blocked.
            if self.dismiss_one():
                continue
            if self._return_from_visited_home():
                continue
            if self.is_own_main_screen():
                self.context.log("Đã xác nhận màn hình farm của clone")
                return
            if self._handle_portal_entry():
                continue

            now = time.monotonic()
            if now - last_status >= 5.0:
                self.context.log(
                    "Đang đưa ClientJS về màn hình farm • "
                    f"còn {max(0, int(deadline - now))}s"
                )
                last_status = now
            self.waiter.sleep(0.65)
        raise ScreenTimeout(
            f"Không đưa được ClientJS về màn hình farm sau {timeout:.0f}s"
        )
