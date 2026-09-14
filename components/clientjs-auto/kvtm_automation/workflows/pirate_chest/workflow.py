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
    REWARD_CLAIM_POINT = (500, 610)
    PANEL_CLOSE_POINT = (840, 305)
    STORAGE_MODAL_CLOSE_POINT = (718, 392)
    REWARD_BACK_POINT = (30, 28)

    PANEL_HEADER_ZONE = (300, 285, 400, 45)
    OPEN_ACTION_ZONE = (438, 535, 124, 47)
    COOLDOWN_ZONE = (448, 548, 104, 22)
    STORAGE_GREEN_ZONE = (300, 405, 400, 190)
    OPEN_PROMPT_CHEST_ZONE = (395, 500, 210, 170)
    REWARD_COIN_ZONE = (460, 430, 80, 80)

    POLL_SECONDS = 0.12
    ENTER_TIMEOUT_SECONDS = 4.0
    TRANSITION_TIMEOUT_SECONDS = 5.0
    REWARD_TIMEOUT_SECONDS = 6.0
    RETURN_TIMEOUT_SECONDS = 6.0

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

    def _reward_ready(self, frame) -> bool:
        if self._panel_normal(frame) or self._storage_full(frame):
            return False
        header = self._crop(frame, self.PANEL_HEADER_ZONE)
        if float(header.mean()) > 70.0:
            return False
        roi = self._crop(frame, self.REWARD_COIN_ZONE)
        ratio = self._color_ratio(
            roi,
            lambda r, g, b: (r >= 210) & (g >= 160) & (b <= 130),
        )
        return ratio >= 0.20

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

    def _wait_for_reward_claimable(self, open_prompt_frame) -> tuple[str, object | None]:
        """Prove the reward screen without depending only on one coin color ROI."""
        deadline = time.monotonic() + self.REWARD_TIMEOUT_SECONDS
        previous = None
        stable_frames = 0
        best_prompt_change = 0.0
        while time.monotonic() < deadline:
            self.context.ensure_running()
            frame = self.vision.frame()
            if self._storage_full(frame):
                return "STORAGE_FULL", frame
            if self._reward_ready(frame):
                self.context.detail(
                    "Pirate chest reward claimable | proof=reward-coin-roi"
                )
                return "PASS", frame

            prompt_change = self._frame_change_score(open_prompt_frame, frame)
            best_prompt_change = max(best_prompt_change, prompt_change)
            known_non_reward = self._open_prompt(frame) or self._panel_normal(frame)
            if not known_non_reward and prompt_change >= 8.0:
                frame_change = (
                    self._frame_change_score(previous, frame)
                    if previous is not None
                    else 999.0
                )
                stable_frames = stable_frames + 1 if frame_change <= 6.0 else 0
                if stable_frames >= 2:
                    self.context.detail(
                        "Pirate chest reward claimable | "
                        "proof=stable-screen-transition | "
                        f"prompt_change={prompt_change:.2f} | "
                        f"frame_change={frame_change:.2f}"
                    )
                    return "PASS", frame
            else:
                stable_frames = 0
            previous = frame.copy()
            self.auto.wait.sleep(self.POLL_SECONDS)

        self.context.detail(
            "Pirate chest wait timeout | state=reward-claimable | "
            f"best_prompt_change={best_prompt_change:.2f}"
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

    def _back_out_of_unclassified_chest_overlay(self, *, reason: str) -> None:
        """One safe back action; scheduler owns the later friend-house reset."""
        self.context.stage("pirate-chest-safe-abort-back")
        self.context.log(
            "AUTO rương hải tặc • trạng thái overlay không xác định • "
            "thoát UI một lần trước recovery qua nhà bạn • "
            f"reason={reason}"
        )
        self.driver.click(*self.REWARD_BACK_POINT)
        self.auto.wait.sleep(0.25)
        self._close_panel_if_visible()

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

            self._tap(self.OPEN_NOW_POINT, "pirate-chest-open-now-slot-0")
            transition, _ = self._wait_for(
                self._open_prompt,
                timeout=self.TRANSITION_TIMEOUT_SECONDS,
                label="tap-to-open",
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

        open_prompt_frame = self.vision.frame().copy()
        self._tap(self.CHEST_CENTER_POINT, "pirate-chest-tap-chest")
        reward_state, _ = self._wait_for_reward_claimable(open_prompt_frame)
        if reward_state == "STORAGE_FULL":
            self._exit_after_storage_full()
            return self._result(
                PirateChestStatus.STORAGE_FULL,
                started,
                "storage-full-before-claim",
            )
        if reward_state != "PASS":
            self._back_out_of_unclassified_chest_overlay(reason="reward-timeout")
            return self._result(
                PirateChestStatus.SAFE_ABORT,
                started,
                "reward-timeout",
            )

        # Exactly one additional tap claims/closes the reward presentation.
        # Never retry this action because the reward may already be credited.
        self._tap(self.REWARD_CLAIM_POINT, "pirate-chest-claim-reward-once")
        final_state, final_frame = self._wait_for(
            self._panel_normal,
            timeout=self.RETURN_TIMEOUT_SECONDS,
            label="panel-after-reward-claim",
            storage_interrupt=True,
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
            # Never hand an unclassified reward/panel overlay to the next
            # Function. Exit once; the scheduler then owns the error-only
            # friend-house scene reset and exact-main proof.
            self._back_out_of_unclassified_chest_overlay(
                reason="cooldown-confirm-timeout"
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
        self._close_panel_if_visible()
        self.context.stage("pirate-chest-finished")
        return self._result(
            PirateChestStatus.OPENED,
            started,
            "slot-0-opened",
        )
