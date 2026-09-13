from __future__ import annotations

import json
import time

from ...errors import AutomationStopped
from ...recovery import RecoveryManager
from ..pirate_chest import PirateChestWorkflow
from .boundary_delay import AutoMainResult, AutoMainWorkflow as _BoundaryAutoMainWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]


class AutoMainWorkflow(_BoundaryAutoMainWorkflow):
    """AUTO Main with optional Pirate Chest maintenance at safe boundaries.

    The first Pirate Chest check is attached to the first completed sale. After
    that, a 20-minute deadline only marks the maintenance as due; the click flow
    itself runs from a post-Function safe boundary and never interrupts a
    Function in progress.

    Pirate Chest is an overlay maintenance flow, while every production Function
    starts only from exact-main. The scheduler therefore owns an explicit public
    boundary recovery before and after chest maintenance. Recipes keep their
    strict fail-close contract and never hide recovery/navigation internally.
    """

    PIRATE_CHEST_INTERVAL_SECONDS = 1200.0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pirate_chest_enabled = self._load_pirate_chest_enabled()
        self.pirate_chest_calls = 0
        self._pirate_chest_initialized = False
        self._pirate_chest_next_check_at = 0.0
        self._pirate_chest_boundary_recovery = RecoveryManager(
            self.auto,
            function_id=self.spec.function_id,
        )

    def _load_pirate_chest_enabled(self) -> bool:
        """Read option #1 without coupling AUTO Main to one GUI serialization."""
        marker = self.context.work_dir / "auto-main-config.json"
        try:
            raw = json.loads(marker.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False
        if not isinstance(raw, dict):
            return False

        if "pirate_chest_enabled" in raw:
            return bool(raw.get("pirate_chest_enabled"))

        # AUTO MULTI DEV historically serializes the option checkboxes as an
        # ordered flag vector. Pirate Chest is option #1 => index 0.
        for key in ("option_flags", "options", "auto_options"):
            flags = raw.get(key)
            if isinstance(flags, (list, tuple)) and flags:
                return bool(flags[0])
            if isinstance(flags, dict):
                if 0 in flags:
                    return bool(flags[0])
                if "0" in flags:
                    return bool(flags["0"])
        return False

    def _pirate_chest_due(self) -> bool:
        return bool(
            self.pirate_chest_enabled
            and self._pirate_chest_initialized
            and self._pirate_chest_next_check_at > 0.0
            and time.monotonic() >= self._pirate_chest_next_check_at
        )

    def _schedule_next_pirate_chest_check(self) -> None:
        self._pirate_chest_initialized = True
        self._pirate_chest_next_check_at = (
            time.monotonic() + self.PIRATE_CHEST_INTERVAL_SECONDS
        )

    def _prove_exact_main_boundary(self, *, reason: str) -> None:
        """Explicitly restore the caller contract before/after optional UI work."""
        self.context.ensure_running()
        if self.auto.popup.is_own_exact_main_screen():
            self.context.detail(
                "AUTO rương hải tặc | exact-main boundary already proven | "
                f"reason={reason}"
            )
            return

        self.context.stage("auto-main-pirate-chest-exact-main-recovery")
        self.context.log(
            "AUTO rương hải tặc • boundary chưa có exact-main • "
            f"recovery công khai trước Function • reason={reason}"
        )

        # First remove/recover any overlay or visited-home state and reach the
        # clone farm HUD. PopupActions intentionally invalidates camera proof;
        # NavigationRecovery then re-proves the bottom/main boundary by behavior.
        self.auto.ensure_main_screen(timeout=12.0)
        if not self.auto.popup.is_own_exact_main_screen():
            self._pirate_chest_boundary_recovery.recover_unknown_to_main(
                f"rương hải tặc boundary {reason}",
                reason=f"pirate-chest-boundary-{reason}",
            )
        self._pirate_chest_boundary_recovery.ensure_main(
            f"rương hải tặc boundary {reason}"
        )
        self.context.stage("auto-main-pirate-chest-exact-main-ready")
        self.context.log(
            "AUTO rương hải tặc • boundary exact-main PASS • "
            f"reason={reason}"
        )

    def _run_pirate_chest(self, *, reason: str) -> None:
        if not self.pirate_chest_enabled:
            return

        self.context.ensure_running()
        ordinal = self.pirate_chest_calls + 1
        self.context.stage(f"auto-main-pirate-chest-{ordinal}-start")
        self.context.log(
            "AUTO rương hải tặc • bắt đầu check hậu Function • "
            f"lần={ordinal} • reason={reason}"
        )

        # The optional flow must never inherit an unproved camera from sale or
        # another maintenance action. Prove exact-main before touching the ship.
        self._prove_exact_main_boundary(reason=f"{reason}-before-chest")

        status = "ERROR"
        detail = ""
        try:
            result = PirateChestWorkflow(self.auto).run()
            status = str(result.status)
            detail = str(result.detail)
        except AutomationStopped:
            raise
        except Exception as exc:
            # Pirate Chest business/capture errors remain non-blocking. The
            # boundary recovery below is separate: if exact-main cannot be
            # restored, the main pipeline still fail-closes before a Recipe.
            status = "SAFE_ABORT"
            detail = f"{type(exc).__name__}: {exc}"
            self.context.detail(
                "AUTO rương hải tặc | non-blocking error | " + detail
            )
        finally:
            self.pirate_chest_calls += 1
            self._schedule_next_pirate_chest_check()

        # Critical handoff: closing a panel/overlay is not itself proof that the
        # farm camera is at exact-main. Re-establish the caller contract before
        # AUTO Main is allowed to start Táo sấy or any other Function recipe.
        self._prove_exact_main_boundary(reason=f"{reason}-after-chest")

        self.context.stage(f"auto-main-pirate-chest-{ordinal}-finished")
        self.context.log(
            "AUTO rương hải tặc • kết thúc lượt check • "
            f"lần={ordinal} • status={status} • detail={detail} • "
            f"exact-main=PASS • check_lại_sau={self.PIRATE_CHEST_INTERVAL_SECONDS:.0f}s"
        )

    def _pirate_chest_checkpoint(self, *, reason: str) -> None:
        if not self._pirate_chest_due():
            return
        # This is called only from scheduler boundaries. Mark the activity so
        # boundary_delay counts chest time toward the configured loop delay.
        self._mark_boundary_activity_started()
        self._run_pirate_chest(reason=reason)

    def _sale_once(self, *, ordinal: int) -> None:
        super()._sale_once(ordinal=ordinal)

        # Exact user contract: first chest check starts only after the first
        # completed sale. It also starts the 20-minute countdown.
        if self.pirate_chest_enabled and not self._pirate_chest_initialized:
            self._run_pirate_chest(reason=f"first-completed-sale-{ordinal}")

    def _request_client_restart_at_safe_boundary(self) -> None:
        # If the 20-minute deadline matured during the just-finished Function,
        # consume it before the scheduled 3h restart while we are still at a
        # proven safe boundary.
        self._pirate_chest_checkpoint(reason="pre-client-restart-boundary")
        super()._request_client_restart_at_safe_boundary()

    def _wait_before_next_function_loop(self) -> None:
        # Base run calls this only after the current Function, optional sale and
        # friend maintenance have completed. Therefore a due timer can never
        # inject UI input into an in-progress Function.
        self._pirate_chest_checkpoint(reason="post-function-boundary")
        super()._wait_before_next_function_loop()
