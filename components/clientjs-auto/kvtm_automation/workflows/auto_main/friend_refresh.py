from __future__ import annotations

from typing import TYPE_CHECKING

from ...errors import AutomationStopped, ScreenTimeout
from ...recovery import RecoveryManager

if TYPE_CHECKING:
    from ...automation import KVAutomation


__all__ = ["FriendRefreshWorkflow"]
FILE_FUNCTIONS = (
    "Sau mỗi ba vòng Function, nếu GUI bật thì sang nhà bạn số 1 rồi quay về nhà",
    "Dùng đúng NavigationActions/Dọn quầy hiện có và thư viện ảnh Multi DEV chung",
    "Không mở quầy bạn, không mua VP và không thay đổi business logic của Function",
    "Sau khi quay về nhà, ghi lại exact-main bằng bằng chứng route deterministic",
    "Nếu thao tác refresh lỗi nhưng vẫn recovery được exact-main thì tiếp tục AUTO non-blocking",
    "Nếu không thể recovery về exact-main thì fail-close để worker xử lý an toàn",
)


class FriendRefreshWorkflow:
    """Common anti-stuck maintenance shared by every AUTO Main Function.

    The game can occasionally leave a floating/stale item layer that blocks later
    clicks. A friend-house round trip forces the game scene to rebuild. This
    workflow intentionally reuses the already-live Dọn-quầy navigation primitives
    and their shared Multi DEV image assets instead of introducing new templates
    or coordinates.
    """

    FRIEND_ORDINAL = 1
    FRIEND_TIMEOUT_SECONDS = 45.0
    VISIT_SETTLE_SECONDS = 0.65
    RECOVERY_MAIN_PASSES = 6

    def __init__(self, automation: KVAutomation, *, function_id: str) -> None:
        self.auto = automation
        self.context = automation.context
        self.function_id = str(function_id)
        self.recovery = RecoveryManager(
            automation,
            function_id=self.function_id,
        )

    def _ensure_exact_main_before_visit(self) -> None:
        if self.auto.popup.is_own_exact_main_screen():
            return
        self.recovery.recover_unknown_to_main(
            "refresh nhà bạn: preflight",
            reason="friend-refresh-preflight-camera-not-exact-main",
            max_passes=self.RECOVERY_MAIN_PASSES,
        )

    def _recover_after_failure(self, error: BaseException) -> None:
        self.context.log(
            "AUTO refresh item treo • qua nhà bạn lỗi • thử đưa clone về exact-main "
            f"để tiếp tục an toàn • {type(error).__name__}: {error}"
        )
        try:
            # This helper also recognizes the case where ClientJS is still at a
            # visited house and clicks icon_home using the proven shared asset.
            self.auto.ensure_main_screen(timeout=20.0)
            self.recovery.recover_unknown_to_main(
                "refresh nhà bạn: recovery sau lỗi",
                reason="friend-refresh-failed",
                max_passes=self.RECOVERY_MAIN_PASSES,
            )
        except AutomationStopped:
            raise
        except Exception as recovery_error:
            raise ScreenTimeout(
                "Refresh item treo thất bại và không recovery được exact-main; "
                "dừng để worker không tiếp tục từ camera không xác định"
            ) from recovery_error

    def run(self, *, completed_loops: int) -> bool:
        """Visit friend #1 and return home once; return False only after safe recovery."""
        self.context.ensure_running()
        self.context.stage("auto-main-friend-refresh-start")
        self._ensure_exact_main_before_visit()
        self.context.log(
            "AUTO refresh item treo • bắt đầu sau "
            f"{int(completed_loops)} vòng Function • sang nhà bạn mặc định #1"
        )

        # Leaving the own farm invalidates all previous exact-main proof. The
        # successful return-home route below is what creates a new proof.
        self.context.invalidate_camera_main("friend-refresh-leave-own-home")
        try:
            self.auto.navigation.go_to_friend(
                self.FRIEND_ORDINAL,
                timeout=self.FRIEND_TIMEOUT_SECONDS,
            )
            self.context.stage("auto-main-friend-refresh-friend-1-ready")
            self.context.log(
                "AUTO refresh item treo • đã sang nhà bạn #1 • chờ scene ổn định rồi quay về"
            )
            self.auto.wait.sleep(self.VISIT_SETTLE_SECONDS)
            self.context.ensure_running()

            self.auto.navigation.return_home(timeout=self.FRIEND_TIMEOUT_SECONDS)
            self.context.ensure_running()

            # go_to_friend/return_home is a deterministic world transition: the
            # game's Home action returns to the clone's bottom/main scene. Keep
            # exact-main background-independent by recording the route itself,
            # then require the fixed own-farm HUD before accepting PASS.
            self.context.mark_camera_exact_main(
                "friend-refresh friend#1 -> own-home deterministic route"
            )
            if not self.auto.popup.is_own_exact_main_screen():
                raise ScreenTimeout(
                    "Đã bấm quay về nhà sau refresh nhưng chưa xác nhận own exact-main"
                )

        except AutomationStopped:
            raise
        except Exception as exc:
            self._recover_after_failure(exc)
            self.context.stage("auto-main-friend-refresh-recovered")
            self.context.log(
                "AUTO refresh item treo • lượt refresh chưa PASS nhưng exact-main đã recovery • "
                "bỏ qua maintenance lần này và tiếp tục vòng AUTO"
            )
            return False

        self.context.stage("auto-main-friend-refresh-finished")
        self.context.log(
            "AUTO refresh item treo • PASS • nhà bạn #1 → nhà mình → exact-main • "
            "scene đã được làm mới"
        )
        return True
