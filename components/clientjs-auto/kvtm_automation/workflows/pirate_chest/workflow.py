from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import time
from typing import Callable

from ...automation import KVAutomation
from ...errors import ScreenTimeout


__all__ = ["PirateChestResult", "PirateChestStatus", "PirateChestWorkflow"]

FILE_FUNCTIONS = (
    "Chỉ vào Kho Báu Hải Tặc từ exact-main bằng hitbox logical, không template-match background",
    "Click đúng hitbox thân thuyền hải tặc, không click bong bóng rương/đèn thần phía trên",
    "Luôn chọn đúng rương đầu tiên/slot 0 và không bao giờ thao tác các slot trả kim cương",
    "Phân loại READY/COOLDOWN bằng màu và hình học ROI, hỗ trợ native 500x500/1000x1000",
    "Chờ chuyển trạng thái có timeout thay vì sleep mù trong animation mở/nhận quà",
    "Bắt modal kho quá tải theo hình học/màu chung, không phụ thuộc Kho 2/Kho 3",
    "Mọi lỗi nhận diện an toàn đều đóng UI nếu có thể và trả caller, không dừng toàn AUTO",
)


class PirateChestStatus(str, Enum):
    OPENED = "OPENED"
    COOLDOWN = "COOLDOWN"
    STORAGE_FULL = "STORAGE_FULL"
    SAFE_ABORT = "SAFE_ABORT"


@dataclass(frozen=True)
class PirateChestResult:
    profile_id: str
    status: str
    elapsed_seconds: float
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class PirateChestWorkflow:
    """Safe Pirate Chest maintenance.

    Coordinates below are logical 1000x1000 coordinates. VisionEngine maps
    logical ROIs to the native capture (500x500 or 1000x1000), while the driver
    owns logical->client input scaling.

    Safety contract:
    - entry clicks the Pirate ship body, never either bubble above the ship;
    - only slot 0 is selectable;
    - no paid-chest coordinate exists in this module;
    - an unclassified action state is a SAFE_ABORT, never a speculative click.
    """

    # Operator-confirmed logical 1000x1000 entry geometry. The interactive
    # target is the ship body below both bubbles; keeping y=620 deliberately
    # excludes the Pirate Chest/Genie bubble row around y=549.
    ENTRY_POINT = (363, 620)
    SLOT_ZERO_POINT = (263, 632)
    OPEN_NOW_POINT = (500, 558)
    CHEST_CENTER_POINT = (500, 580)
    # Empty hitbox immediately below “Chạm để nhận quà”; the chest/reward art
    # itself does not dismiss the reward presentation.
    REWARD_CLAIM_POINT = (500, 715)
    PANEL_CLOSE_POINT = (840, 305)
    STORAGE_MODAL_CLOSE_POINT = (718, 392)
    REWARD_BACK_POINT = (30, 28)

    PANEL_HEADER_ZONE = (300, 285, 400, 45)
    OPEN_ACTION_ZONE = (438, 535, 124, 47)
    COOLDOWN_ZONE = (448, 548, 104, 22)
    STORAGE_GREEN_ZONE = (300, 405, 400, 190)
    OPEN_PROMPT_CHEST_ZONE = (395, 500, 210, 170)
    CENTER_CHEST_ZONE = (420, 400, 165, 130)
    REWARD_CLAIM_TEXT_ZONE = (420, 675, 160, 40)
    CENTER_CHEST_HIDDEN_CHANGE = 12.0
    CENTER_CHEST_RETURN_MIN_CHANGE = 12.0
    REWARD_TEXT_WHITE_RATIO = 0.045
    REWARD_TEXT_MAX_MEAN = 100.0
    REWARD_TEXT_STABLE_MAX_CHANGE = 3.5
    REWARD_TEXT_STABLE_SECONDS = 0.60
    RETURN_STABLE_SECONDS = 0.60
    ANIMATION_SETTLE_SECONDS = 4.0
    POST_CLAIM_QUIET_SECONDS = 4.0
    MAIN_AFTER_CLOSE_TIMEOUT_SECONDS = 4.0

    POLL_SECONDS = 0.12
    ENTER_TIMEOUT_SECONDS = 4.0
    TRANSITION_TIMEOUT_SECONDS = 5.0
    REWARD_TIMEOUT_SECONDS = 10.0
    RETURN_TIMEOUT_SECONDS = 12.0

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.vision = automation.vision
        self.driver = automation.vision.driver

    def _crop(self, frame, zone: tuple[int, int, int, int]):
        x, y, w, h = self.vision.logical_zone_to_frame(zone, frame)
        return frame[y : y + h, x : x + w]

    @staticmethod
    def _color_ratio(
        roi,
        predicate: Callable[[object, object, object], object],
    ) -> float:
        if roi is None or getattr(roi, "size", 0) == 0:
            return 0.0
        # OpenCV capture order is BGR.
        blue = roi[..., 0]
        green = roi[..., 1]
        red = roi[..., 2]
        mask = predicate(red, green, blue)
        if getattr(mask, "size", 0) == 0:
            return 0.0
        return float(mask.mean())

    def _panel_normal(self, frame) -> bool:
        roi = self._crop(frame, self.PANEL_HEADER_ZONE)
        ratio = self._color_ratio(
            roi,
            lambda r, g, b: (
                (r < 70)
                & (g >= 90)
                & (g <= 180)
                & (b >= 120)
                & (b <= 220)
            ),
        )
        return ratio >= 0.55

    def _ready(self, frame) -> bool:
        if not self._panel_normal(frame):
            return False
        roi = self._crop(frame, self.OPEN_ACTION_ZONE)
        ratio = self._color_ratio(
            roi,
            lambda r, g, b: (
                (r >= 180)
                & (g >= 85)
                & (g <= 200)
                & (b <= 80)
            ),
        )
        return ratio >= 0.35

    def _cooldown(self, frame) -> bool:
        if not self._panel_normal(frame):
            return False
        roi = self._crop(frame, self.COOLDOWN_ZONE)
        ratio = self._color_ratio(
            roi,
            lambda r, g, b: (
                (r <= 90)
                & (g >= 130)
                & (g <= 230)
                & (b >= 180)
            ),
        )
        return ratio >= 0.22

    def _storage_full(self, frame) -> bool:
        roi = self._crop(frame, self.STORAGE_GREEN_ZONE)
        ratio = self._color_ratio(
            roi,
            lambda r, g, b: (
                (r >= 70)
                & (r <= 160)
                & (g >= 100)
                & (g <= 190)
                & (b <= 70)
                & (g >= r + 15)
            ),
        )
        return ratio >= 0.45

    def _open_prompt(self, frame) -> bool:
        if self._panel_normal(frame) or self._storage_full(frame):
            return False
        header = self._crop(frame, self.PANEL_HEADER_ZONE)
        if float(header.mean()) > 70.0:
            return False
        roi = self._crop(frame, self.OPEN_PROMPT_CHEST_ZONE)
        ratio = self._color_ratio(
            roi,
            lambda r, g, b: (
                (r >= 180)
                & (g >= 85)
                & (g <= 200)
                & (b <= 80)
            ),
        )
        return ratio >= 0.30

    @staticmethod
    def _frame_change_score(before, after) -> float:
        if (
            before is None
            or after is None
            or getattr(before, "shape", None) != getattr(after, "shape", None)
            or getattr(before, "size", 0) == 0
        ):
            return 0.0
        return float(abs(after.astype("int16") - before.astype("int16")).mean())

    def _center_chest_change(self, reference_frame, frame) -> float:
        reference = self._crop(reference_frame, self.CENTER_CHEST_ZONE)
        current = self._crop(frame, self.CENTER_CHEST_ZONE)
        return self._frame_change_score(reference, current)

    def _center_chest_hidden(self, reference_frame, frame) -> bool:
        return (
            self._open_prompt(frame)
            and self._center_chest_change(reference_frame, frame)
            >= self.CENTER_CHEST_HIDDEN_CHANGE
        )

    def _center_chest_returned(self, reward_frame, frame) -> bool:
        """Prove reward overlay gone against the immediately preceding reward."""
        if reward_frame is None or not self._panel_normal(frame):
            return False
        return (
            self._center_chest_change(reward_frame, frame)
            >= self.CENTER_CHEST_RETURN_MIN_CHANGE
        )

    def _wait_open_prompt_animation(self) -> tuple[str, object | None]:
        """Keep the proven tap-to-open modal stable for the operator-set 4s."""
        deadline = time.monotonic() + self.ANIMATION_SETTLE_SECONDS
        last_frame = None
        while time.monotonic() < deadline:
            self.context.ensure_running()
            frame = self.vision.frame()
            if self._storage_full(frame):
                return "STORAGE_FULL", frame
            if not self._open_prompt(frame):
                self.context.detail(
                    "Pirate chest animation interrupted | "
                    "state=tap-to-open-before-chest-tap"
                )
                return "INTERRUPTED", frame
            last_frame = frame
            self.auto.wait.sleep(
                min(self.POLL_SECONDS, max(0.0, deadline - time.monotonic()))
            )
        self.context.detail(
            "Pirate chest animation settled | "
            f"state=tap-to-open | waited={self.ANIMATION_SETTLE_SECONDS:.1f}s"
        )
        return "PASS", last_frame

    def _reward_claim_prompt(self, frame) -> tuple[bool, float, float]:
        """Recognize the stable white claim text, independent of reward art."""
        if (
            self._panel_normal(frame)
            or self._open_prompt(frame)
            or self._storage_full(frame)
        ):
            return False, 0.0, 255.0
        roi = self._crop(frame, self.REWARD_CLAIM_TEXT_ZONE)
        white_ratio = self._color_ratio(
            roi,
            lambda r, g, b: (
                (r >= 180)
                & (g >= 180)
                & (b >= 180)
                & ((r.astype("int16") - b.astype("int16")) < 55)
            ),
        )
        mean = float(roi.mean()) if getattr(roi, "size", 0) else 255.0
        ready = (
            white_ratio >= self.REWARD_TEXT_WHITE_RATIO
            and mean <= self.REWARD_TEXT_MAX_MEAN
        )
        return ready, white_ratio, mean

    def _wait_for_reward_claimable(self, open_prompt_frame) -> tuple[str, object | None]:
        """Wait until “Chạm để nhận quà” is visible and animation-safe."""
        started = time.monotonic()
        deadline = started + self.REWARD_TIMEOUT_SECONDS
        previous_text_roi = None
        stable_since = None
        best_prompt_change = 0.0
        best_white_ratio = 0.0
        while time.monotonic() < deadline:
            self.context.ensure_running()
            frame = self.vision.frame()
            if self._storage_full(frame):
                return "STORAGE_FULL", frame

            prompt_change = self._frame_change_score(open_prompt_frame, frame)
            best_prompt_change = max(best_prompt_change, prompt_change)
            ready, white_ratio, text_mean = self._reward_claim_prompt(frame)
            best_white_ratio = max(best_white_ratio, white_ratio)
            text_roi = self._crop(frame, self.REWARD_CLAIM_TEXT_ZONE).copy()
            text_change = (
                self._frame_change_score(previous_text_roi, text_roi)
                if previous_text_roi is not None
                else 999.0
            )

            if (
                ready
                and prompt_change >= 8.0
                and text_change <= self.REWARD_TEXT_STABLE_MAX_CHANGE
            ):
                if stable_since is None:
                    stable_since = time.monotonic()
                stable_seconds = time.monotonic() - stable_since
                animation_seconds = time.monotonic() - started
                if (
                    stable_seconds >= self.REWARD_TEXT_STABLE_SECONDS
                    and animation_seconds >= self.ANIMATION_SETTLE_SECONDS
                ):
                    self.context.detail(
                        "Pirate chest reward claimable | "
                        "proof=claim-text-stable | "
                        f"white_ratio={white_ratio:.3f} | "
                        f"text_mean={text_mean:.1f} | "
                        f"text_change={text_change:.2f} | "
                        f"stable={stable_seconds:.2f}s | "
                        f"animation={animation_seconds:.2f}s"
                    )
                    return "PASS", frame.copy()
            else:
                stable_since = None

            previous_text_roi = text_roi
            self.auto.wait.sleep(self.POLL_SECONDS)

        self.context.detail(
            "Pirate chest wait timeout | state=reward-claimable | "
            f"best_prompt_change={best_prompt_change:.2f} | "
            f"best_white_ratio={best_white_ratio:.3f}"
        )
        return "TIMEOUT", None

    def _wait_for_center_chest_returned(
        self,
        reward_frame,
    ) -> tuple[str, object | None]:
        """Wait for a stable normal panel after the one authorized claim tap."""
        deadline = time.monotonic() + self.RETURN_TIMEOUT_SECONDS
        stable_since = None
        last_change = 0.0
        while time.monotonic() < deadline:
            self.context.ensure_running()
            frame = self.vision.frame()
            if self._storage_full(frame):
                return "STORAGE_FULL", frame
            if self._center_chest_returned(reward_frame, frame):
                last_change = self._center_chest_change(reward_frame, frame)
                if stable_since is None:
                    stable_since = time.monotonic()
                stable_seconds = time.monotonic() - stable_since
                if stable_seconds >= self.RETURN_STABLE_SECONDS:
                    self.context.detail(
                        "Pirate chest panel returned | "
                        "proof=center-chest-stable | "
                        f"reward_change={last_change:.2f} | "
                        f"stable={stable_seconds:.2f}s"
                    )
                    return "PASS", frame
            else:
                stable_since = None
            self.auto.wait.sleep(self.POLL_SECONDS)

        self.context.detail(
            "Pirate chest wait timeout | "
            "state=panel-after-reward-claim-center-chest-returned | "
            f"last_reward_change={last_change:.2f}"
        )
        return "TIMEOUT", None

    def _wait_for(
        self,
        predicate: Callable[[object], bool],
        *,
        timeout: float,
        label: str,
        storage_interrupt: bool = False,
    ) -> tuple[str, object | None]:
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self.context.ensure_running()
            frame = self.vision.frame()
            if storage_interrupt and self._storage_full(frame):
                return "STORAGE_FULL", frame
            if predicate(frame):
                return "PASS", frame
            self.auto.wait.sleep(self.POLL_SECONDS)
        self.context.detail(f"Pirate chest wait timeout | state={label}")
        return "TIMEOUT", None

    def _tap(self, point: tuple[int, int], stage: str) -> None:
        self.context.ensure_running()
        self.context.stage(stage)
        if stage.startswith("pirate-chest-open-entry"):
            try:
                frame = self.vision.frame()
                height, width = frame.shape[:2]
                native_point = self.vision.logical_point_to_frame(point, frame)
                self.context.log(
                    "AUTO rương hải tặc • click thân thuyền • "
                    f"stage={stage} • logical={point} • native={native_point} • "
                    f"content={width}x{height}"
                )
            except Exception as exc:
                self.context.log(
                    "AUTO rương hải tặc • click thân thuyền • "
                    f"stage={stage} • logical={point} • "
                    f"không đọc được content geometry: {type(exc).__name__}"
                )
        self.driver.click(*point)

    def _close_panel_if_visible(self) -> None:
        try:
            frame = self.vision.frame()
        except Exception:
            return
        if not self._panel_normal(frame):
            return
        self.driver.click(*self.PANEL_CLOSE_POINT)
        self.auto.wait.sleep(0.20)

    def _close_panel_and_prove_main(self) -> bool:
        """Close the returned chest panel and require exact-main before handoff."""
        try:
            frame = self.vision.frame()
        except Exception:
            return False
        if not self._panel_normal(frame):
            return False
        self.context.stage("pirate-chest-close-panel-to-main")
        self.driver.click(*self.PANEL_CLOSE_POINT)
        deadline = time.monotonic() + self.MAIN_AFTER_CLOSE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self.auto.popup.is_own_exact_main_screen():
                self.context.detail(
                    "Pirate chest panel closed | proof=exact-main"
                )
                return True
            self.auto.wait.sleep(self.POLL_SECONDS)
        self.context.detail(
            "Pirate chest wait timeout | state=exact-main-after-panel-close"
        )
        return False

    def _fail_close_reward_overlay(self, *, reason: str) -> None:
        """Do not click Back: only a completed claim can dismiss this modal."""
        self.context.stage("pirate-chest-safe-abort-reward-overlay")
        self.context.log(
            "AUTO rương hải tặc • reward overlay chưa hoàn tất • "
            "fail-close, không dùng nút quay lại và không giao MAIN ảo • "
            f"reason={reason}"
        )

    def _exit_after_storage_full(self) -> None:
        """Close the generic overload modal and leave Pirate Chest best-effort."""
        self.context.stage("pirate-chest-storage-full-close-modal")
        self.driver.click(*self.STORAGE_MODAL_CLOSE_POINT)
        self.auto.wait.sleep(0.25)

        # The overload modal can be raised on the reward/claim overlay. That
        # overlay owns a back arrow at top-left, while the normal panel owns X.
        try:
            frame = self.vision.frame()
        except Exception:
            return
        if self._panel_normal(frame):
            self.driver.click(*self.PANEL_CLOSE_POINT)
            self.auto.wait.sleep(0.20)
            return

        if self._storage_full(frame):
            # Never spam the modal. One close attempt per cycle is enough.
            return

        self.driver.click(*self.REWARD_BACK_POINT)
        status, _ = self._wait_for(
            self._panel_normal,
            timeout=2.5,
            label="panel-after-storage-back",
        )
        if status == "PASS":
            self.driver.click(*self.PANEL_CLOSE_POINT)
            self.auto.wait.sleep(0.20)

    def _result(self, status: PirateChestStatus, started: float, detail: str) -> PirateChestResult:
        return PirateChestResult(
            profile_id=self.context.profile_id,
            status=status.value,
            elapsed_seconds=round(time.monotonic() - started, 3),
            detail=str(detail),
        )

    def run(self) -> PirateChestResult:
        started = time.monotonic()
        self.context.ensure_running()
        self.context.stage("pirate-chest-start")

        # Entry is coordinate/hitbox based by design. Different farm templates
        # may change the background art, so no entry image matching is allowed.
        if not self.auto.popup.is_own_exact_main_screen():
            try:
                self.auto.ensure_main_screen(timeout=12.0)
            except ScreenTimeout as exc:
                self.context.log(
                    "AUTO rương hải tặc • bỏ lượt an toàn • chưa về MAIN: "
                    f"{type(exc).__name__}: {exc}"
                )
                return self._result(
                    PirateChestStatus.SAFE_ABORT,
                    started,
                    "main-not-ready",
                )
        if not self.auto.popup.is_own_exact_main_screen():
            return self._result(
                PirateChestStatus.SAFE_ABORT,
                started,
                "exact-main-not-proven",
            )

        self._tap(self.ENTRY_POINT, "pirate-chest-open-entry")
        status, entry_frame = self._wait_for(
            lambda frame: self._panel_normal(frame) or self._open_prompt(frame),
            timeout=self.ENTER_TIMEOUT_SECONDS,
            label="panel-open",
        )
        if status != "PASS" or entry_frame is None:
            self.context.log(
                "AUTO rương hải tặc • không xác nhận được panel/modal • "
                "bỏ lượt an toàn"
            )
            return self._result(
                PirateChestStatus.SAFE_ABORT,
                started,
                "panel-or-open-prompt-timeout",
            )

        # The game persists an already-selected chest. A later ship entry can
        # therefore reopen directly at "Chạm để mở rương" without showing the
        # normal slot panel. This is a valid resumable state: never click slot 0
        # or MỞ NGAY again, because that could target a different/paid chest.
        center_chest_reference = None
        if self._open_prompt(entry_frame):
            self.context.log(
                "AUTO rương hải tặc • entry vào modal rương đang chờ mở • "
                "tiếp tục rương hiện tại, bỏ qua chọn slot và MỞ NGAY"
            )
        else:
            # Slot 0 is the only authorized slot. No coordinates for slots 1..4
            # are defined anywhere in this workflow.
            self._tap(self.SLOT_ZERO_POINT, "pirate-chest-select-slot-0")
            self.auto.wait.sleep(0.18)
            frame = self.vision.frame()

            if self._storage_full(frame):
                self._exit_after_storage_full()
                return self._result(
                    PirateChestStatus.STORAGE_FULL,
                    started,
                    "storage-full-before-open",
                )

            if self._cooldown(frame):
                self.context.log("AUTO rương hải tặc • slot 0 đang cooldown")
                self._close_panel_if_visible()
                return self._result(
                    PirateChestStatus.COOLDOWN,
                    started,
                    "slot-0-cooldown",
                )

            if not self._ready(frame):
                self.context.log(
                    "AUTO rương hải tặc • slot 0 không ở READY/COOLDOWN • "
                    "không click MỞ NGAY"
                )
                self._close_panel_if_visible()
                return self._result(
                    PirateChestStatus.SAFE_ABORT,
                    started,
                    "slot-0-unclassified",
                )

            center_chest_reference = frame.copy()
            self._tap(self.OPEN_NOW_POINT, "pirate-chest-open-now-slot-0")
            transition, _ = self._wait_for(
                lambda current: self._center_chest_hidden(
                    center_chest_reference, current
                ),
                timeout=self.TRANSITION_TIMEOUT_SECONDS,
                label="tap-to-open-center-chest-hidden",
                storage_interrupt=True,
            )
            if transition == "STORAGE_FULL":
                self._exit_after_storage_full()
                return self._result(
                    PirateChestStatus.STORAGE_FULL,
                    started,
                    "storage-full-after-open-now",
                )
            if transition != "PASS":
                self._close_panel_if_visible()
                return self._result(
                    PirateChestStatus.SAFE_ABORT,
                    started,
                    "open-prompt-timeout",
                )

        settle_state, _ = self._wait_open_prompt_animation()
        if settle_state == "STORAGE_FULL":
            self._exit_after_storage_full()
            return self._result(
                PirateChestStatus.STORAGE_FULL,
                started,
                "storage-full-before-chest-tap",
            )
        if settle_state != "PASS":
            self._fail_close_reward_overlay(reason="open-prompt-animation-interrupted")
            return self._result(
                PirateChestStatus.SAFE_ABORT,
                started,
                "open-prompt-animation-interrupted",
            )

        open_prompt_frame = self.vision.frame().copy()
        self._tap(self.CHEST_CENTER_POINT, "pirate-chest-tap-chest")
        reward_state, reward_frame = self._wait_for_reward_claimable(open_prompt_frame)
        if reward_state == "STORAGE_FULL":
            self._exit_after_storage_full()
            return self._result(
                PirateChestStatus.STORAGE_FULL,
                started,
                "storage-full-before-claim",
            )
        if reward_state != "PASS":
            self._fail_close_reward_overlay(reason="reward-timeout")
            return self._result(
                PirateChestStatus.SAFE_ABORT,
                started,
                "reward-timeout",
            )

        # Exactly one additional tap claims/closes the reward presentation.
        # Never retry this action because the reward may already be credited.
        # The return proof compares against this exact reward frame, not the
        # earlier panel frame whose animation/cooldown art can legitimately vary.
        self._tap(self.REWARD_CLAIM_POINT, "pirate-chest-claim-reward-once")

        # INPUT4 claim and CAPTURE3 verification must not overlap. During this
        # operator-approved quiet window no frame is requested, so the game can
        # finish the claim/close animation before the first return-state check.
        self.context.stage("pirate-chest-post-claim-quiet")
        self.context.log(
            "AUTO rương hải tặc • đã gửi nhận quà đúng 1 lần • "
            f"quiet={self.POST_CLAIM_QUIET_SECONDS:.1f}s • "
            "không CAPTURE/check trong animation"
        )
        self.auto.wait.sleep(self.POST_CLAIM_QUIET_SECONDS)
        self.context.ensure_running()

        final_state, final_frame = self._wait_for_center_chest_returned(
            reward_frame
        )
        if final_state == "STORAGE_FULL":
            self.context.log(
                "AUTO rương hải tặc • KHO QUÁ TẢI • đóng modal, thoát rương, "
                "tiếp tục Function kế tiếp"
            )
            self._exit_after_storage_full()
            return self._result(
                PirateChestStatus.STORAGE_FULL,
                started,
                "storage-full-on-claim",
            )
        if final_state != "PASS":
            # Back cannot dismiss the reward modal. Fail closed without
            # another click; the next Function must not receive a false MAIN.
            self._fail_close_reward_overlay(
                reason="center-chest-return-timeout"
            )
            return self._result(
                PirateChestStatus.SAFE_ABORT,
                started,
                "cooldown-confirm-timeout",
            )

        cooldown_proven = (
            final_frame is not None and self._cooldown(final_frame)
        )
        self.context.log(
            "AUTO rương hải tặc • nhận thưởng PASS • panel đã quay lại • "
            f"cooldown={'PASS' if cooldown_proven else 'UNCLASSIFIED'} • "
            "đóng panel về MAIN"
        )
        if not self._close_panel_and_prove_main():
            return self._result(
                PirateChestStatus.SAFE_ABORT,
                started,
                "panel-close-main-timeout",
            )
        self.context.stage("pirate-chest-finished")
        return self._result(
            PirateChestStatus.OPENED,
            started,
            "slot-0-opened",
        )
