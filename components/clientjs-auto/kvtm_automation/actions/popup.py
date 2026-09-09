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

    # LEGACY DIAGNOSTIC ONLY. Different accounts can render different farm
    # backgrounds/world objects, so quay_hang must never gate exact-main again.
    # Keep the old metadata temporarily for offline diagnostics/contracts while
    # runtime exact-main is proved only by navigation state + goDown boundary.
    LEGACY_EXACT_MAIN_STALL_TEMPLATE = "quay_hang"
    EXACT_MAIN_STALL_ZONE = (430, 680, 410, 300)
    EXACT_MAIN_STALL_THRESHOLD = 0.74
    EXACT_MAIN_STALL_SCALES = (0.85, 0.90, 1.00, 1.10, 1.20)

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter

    @staticmethod
    def _blocking_modal_geometry(frame) -> tuple[bool, float, float]:
        """Detect a blocking center modal without depending on popup names/text."""
        try:
            height, width = frame.shape[:2]
            # Geometry below is fully proportional. Native AUTO MULTI DEV capture
            # is 500x500, so rejecting every frame below the old 900px reference
            # silently disabled this blocker detector after the resolution migration.
            if width < 200 or height < 200:
                return False, 0.0, 255.0
            center = frame[
                int(height * 0.28):int(height * 0.72),
                int(width * 0.15):int(width * 0.85),
            ]
            outer_samples = (
                frame[int(height * 0.08):int(height * 0.24), int(width * 0.28):int(width * 0.72)],
                frame[int(height * 0.76):int(height * 0.92), int(width * 0.28):int(width * 0.72)],
                frame[int(height * 0.25):int(height * 0.75), int(width * 0.02):int(width * 0.14)],
                frame[int(height * 0.25):int(height * 0.75), int(width * 0.86):int(width * 0.98)],
            )
            center_luma = center.astype("float32").mean(axis=2)
            bright_ratio = float((center_luma >= 165.0).mean())
            outer_mean = float(sum(
                sample.astype("float32").mean() for sample in outer_samples
            ) / len(outer_samples))
            center_mean = float(center_luma.mean())
            blocked = (
                outer_mean <= 105.0
                and center_mean >= outer_mean + 22.0
                and bright_ratio >= 0.10
            )
            return blocked, bright_ratio, outer_mean
        except Exception:
            return False, 0.0, 255.0

    def _dismiss_unknown_center_modal(self) -> bool:
        """Close a no-X center modal by backdrop and verify the blocker is gone."""
        before = self.vision.frame()
        detected, bright_ratio, background_mean = self._blocking_modal_geometry(before)
        if not detected:
            return False

        # The board has no X. AUTO PRO/game behavior closes it by touching the
        # dimmed backdrop. This point is above the board in 1000x1000 space.
        self.vision.driver.click(500, 185)
        self.waiter.sleep(0.65)
        after = self.vision.frame()
        still_open, _bright_after, _background_after = self._blocking_modal_geometry(after)
        if still_open:
            self.context.log(
                "Modal trung tâm còn mở sau click nền; không xác nhận PASS"
            )
            return False
        self.context.log(
            "Đã đóng modal không tên bằng vùng nền "
            f"(bright={bright_ratio:.2f}, bg={background_mean:.1f})"
        )
        return True

    def is_own_main_screen(self) -> bool:
        """Confirm own-farm HUD, regardless of the current vertical farm floor.

        friend_off/cua_hang are fixed HUD anchors shared across account
        backgrounds. They prove "own farm" but intentionally do not prove the
        vertical camera is at the bottom/main boundary.
        """
        frame = self.vision.frame()
        if self._blocking_modal_geometry(frame)[0]:
            return False
        if self.vision.find(
            "icon_home", threshold=0.80, zone=self.HOME_ZONE, frame=frame
        ) is not None:
            return False
        return bool(
            self.vision.find(
                "friend_off", threshold=0.76, zone=self.FRIEND_ZONE, frame=frame
            )
            or self.vision.find(
                "cua_hang", threshold=0.78, zone=self.HOME_ZONE, frame=frame
            )
        )

    def is_own_exact_main_screen(self) -> bool:
        """Confirm own farm plus runtime-proved bottom/main camera state.

        Exact-main is no longer inferred from any world/background template.
        Navigation marks ``camera_exact_main_proven`` after a deterministic route
        to main or after consecutive goDown no-motion boundary observations.
        """
        if not bool(self.context.camera_exact_main_proven):
            return False
        return self.is_own_main_screen()

    # Compatibility name used by a few generic callers.
    def is_main_screen(self) -> bool:
        return self.is_own_main_screen()

    def dismiss_one(self) -> bool:
        """Close one known modal using AUTO PRO guards plus verified geometry."""
        if self._dismiss_unknown_center_modal():
            return True

        level_up = self.vision.find("lv_up", threshold=0.69, click=True)
        if level_up is not None:
            self.context.log(
                f"Đóng popup Lên cấp (score={level_up.score:.3f})"
            )
            self.waiter.sleep(0.55)
            return True

        generic_x = self.vision.find(
            "x",
            threshold=0.80,
            zone=(471, 3, 525, 429),
            click=True,
        )
        if generic_x is not None:
            self.context.log(
                f"Đóng popup ClientJS bằng x (score={generic_x.score:.3f})"
            )
            self.waiter.sleep(0.45)
            return True

        shop_modal = self.vision.find(
            "quay_hang_on",
            threshold=0.90,
            zone=(319, 249, 386, 120),
        )
        if shop_modal is not None:
            # AUTO PRO fixerr exact guarded exit coordinate.
            self.vision.driver.click(965, 198)
            self.context.log("Thoát popup/quầy hàng đang chắn giao diện")
            self.waiter.sleep(0.50)
            return True

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
            self.context.invalidate_camera_main("portal-account-select")
            self.waiter.sleep(0.35)
            # AUTO_PRO_REFERENCE: account row after opening account selector.
            self.vision.driver.click(984, 341)
            self.context.log("Đã chọn tài khoản ClientJS")
            self.waiter.sleep(0.8)
            return True
        match = self.vision.find("tai_khoan_on", threshold=0.78)
        if match is not None:
            self.context.invalidate_camera_main("portal-online-account-select")
            self.vision.driver.click(981, 338)
            self.context.log("Đã chọn tài khoản đang online")
            self.waiter.sleep(0.8)
            return True
        match = self.vision.find("icon_game", threshold=0.76, click=True)
        if match is not None:
            self.context.invalidate_camera_main("portal-open-game")
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
        self.context.invalidate_camera_main("return-from-visited-home")
        self.context.log("ClientJS đang ở nhà bạn • quay về nhà clone trước")
        self.waiter.sleep(0.8)
        return True

    def ensure_main_screen(self, timeout: float = 90.0) -> None:
        """Ensure own farm/home UI is reachable; camera floor is not normalized."""
        # This entry point deliberately makes no camera-floor promise. Clearing
        # any prior proof here prevents an exception on a directly-swiped stage
        # (for example planting) from carrying stale exact-main state into worker
        # recovery. The worker must re-prove the lower boundary behaviorally.
        self.context.invalidate_camera_main("ensure-farm-hud-camera-unknown")
        deadline = time.monotonic() + float(timeout)
        last_status = 0.0
        while time.monotonic() < deadline:
            self.context.ensure_running()

            # A modal can leave farm HUD visible/dimmed behind it. Always give
            # modal dismissal priority so HUD templates cannot create a false
            # farm-ready success while input is still blocked.
            if self.dismiss_one():
                continue
            if self._return_from_visited_home():
                continue
            if self.is_own_main_screen():
                self.context.log("Đã xác nhận farm HUD của clone")
                return
            if self._handle_portal_entry():
                continue

            now = time.monotonic()
            if now - last_status >= 5.0:
                self.context.log(
                    "Đang đưa ClientJS về farm của clone • "
                    f"còn {max(0, int(deadline - now))}s"
                )
                last_status = now
            self.waiter.sleep(0.65)
        raise ScreenTimeout(
            f"Không đưa được ClientJS về farm của clone sau {timeout:.0f}s"
        )
